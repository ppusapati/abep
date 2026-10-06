//! Parity CLI of the ES-3 gas-path contracts (filter, compressor group, plenum / feed group): JSON request on stdin
//! `{repo_root, materials, requests: [{id, entry, args}]}`, JSON results on stdout `{results: [{id, entry, outcome,
//! value | error_class, error_message}]}`, per-request timing on stderr. Python-ordered dicts arrive as lists of
//! `[key, value]` pairs; non-finite floats as the strings "NaN", "+inf", "-inf".

use abep_gaspath::compressor::{Ctx, DragCompressor, FIELDS};
use abep_gaspath::compressor_synthesis as cs;
use abep_gaspath::error::{value_error, GasPathError, PyClass, PyResult};
use abep_gaspath::filter::{self as fs, Ev, FilterStage, InletState, LevelInput, SensitivityCase};
use abep_gaspath::materials::MaterialsView;
use abep_gaspath::plenum_feed::{self as pf, Chain, CompressorPlant, FilterCase, IntakeState, Plenum, Sp3};
use abep_gaspath::rec::{as_f64, fmap, fnum, onum, slist, Obj};
use abep_gaspath::reservoir::{self, Reservoir};
use abep_gaspath::rotor_strength::{self as rs, Arg, Field, Registry, RotorStrengthBasis};
use abep_gaspath::transient::{self as tr, Controller, Segment};
use abep_gaspath::upstream as u13;
use abep_gaspath::SPECIES;
use serde_json::{json, Map, Value};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

fn bad(msg: &str) -> GasPathError {
    GasPathError::new(PyClass::RuntimeError, format!("harness request malformed: {msg}"))
}

// ------------------------------------------------------------------------------------------------ parsers
fn num(v: &Value) -> PyResult<f64> {
    as_f64(v).ok_or_else(|| bad(&format!("number expected, got {v}")))
}
fn onumv(v: Option<&Value>) -> PyResult<Option<f64>> {
    match v {
        None | Some(Value::Null) => Ok(None),
        Some(x) => Ok(Some(num(x)?)),
    }
}
fn s<'a>(v: &'a Value, k: &str) -> PyResult<&'a str> {
    v.get(k).and_then(|x| x.as_str()).ok_or_else(|| bad(&format!("string {k} expected")))
}
fn ostr(v: &Value, k: &str) -> Option<String> {
    v.get(k).and_then(|x| x.as_str()).map(String::from)
}
fn f(v: &Value, k: &str) -> PyResult<f64> {
    num(v.get(k).ok_or_else(|| bad(&format!("field {k} missing")))?)
}
fn i(v: &Value, k: &str) -> PyResult<i64> {
    v.get(k).and_then(|x| x.as_f64()).map(|x| x as i64).ok_or_else(|| bad(&format!("int {k} expected")))
}
fn arr<'a>(v: &'a Value, k: &str) -> PyResult<&'a Vec<Value>> {
    v.get(k).and_then(|x| x.as_array()).ok_or_else(|| bad(&format!("list {k} expected")))
}
fn strs(v: &Value) -> Vec<String> {
    v.as_array().map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect()).unwrap_or_default()
}

/// A Python-ordered dict sent as [[key, value], ...].
fn spmap(v: &Value) -> PyResult<Vec<(String, f64)>> {
    let a = v.as_array().ok_or_else(|| bad("pair list expected"))?;
    let mut out = vec![];
    for p in a {
        let p = p.as_array().ok_or_else(|| bad("pair expected"))?;
        out.push((p[0].as_str().ok_or_else(|| bad("key"))?.to_string(), num(&p[1])?));
    }
    Ok(out)
}
fn vpairs(v: &Value) -> PyResult<Vec<(String, Value)>> {
    let a = v.as_array().ok_or_else(|| bad("pair list expected"))?;
    let mut out = vec![];
    for p in a {
        let p = p.as_array().ok_or_else(|| bad("pair expected"))?;
        out.push((p[0].as_str().ok_or_else(|| bad("key"))?.to_string(), p[1].clone()));
    }
    Ok(out)
}
fn sp3(v: &Value) -> PyResult<Sp3> {
    let m = spmap(v)?;
    let mut o = [0.0; 3];
    for (k, s_) in SPECIES.iter().enumerate() {
        o[k] = m.iter().find(|(x, _)| x == s_).map(|(_, y)| *y).ok_or_else(|| bad("species"))?;
    }
    Ok(o)
}
fn obj(v: &Value) -> Map<String, Value> {
    v.as_object().cloned().unwrap_or_default()
}

fn ev(v: &Value) -> PyResult<Ev> {
    let (value, is_num) = match v.get("value") {
        None | Some(Value::Null) => (None, true),
        Some(Value::Number(n)) => (n.as_f64(), true),
        Some(Value::String(x)) if ["NaN", "+inf", "-inf"].contains(&x.as_str()) => {
            (as_f64(&Value::String(x.clone())), true)
        }
        Some(_) => (None, false),
    };
    let level = match v.get("evidence_level") {
        None | Some(Value::Null) => LevelInput::None,
        Some(Value::Number(n)) if n.is_i64() || n.is_u64() => LevelInput::Int(n.as_i64().unwrap_or(i64::MIN)),
        Some(_) => LevelInput::Invalid,
    };
    Ev::new(
        value,
        is_num,
        v.get("units").and_then(|x| x.as_str()).unwrap_or(""),
        v.get("status").and_then(|x| x.as_str()).unwrap_or(""),
        v.get("evidence_class").and_then(|x| x.as_str()),
        v.get("source").and_then(|x| x.as_str()),
        v.get("uncertainty").and_then(|x| x.as_str()),
        v.get("basis").and_then(|x| x.as_str()).unwrap_or(""),
        level,
        v.get("domain").and_then(|x| x.as_str()),
        v.get("requires").and_then(|x| x.as_str()),
    )
}

fn protection(v: &Value) -> PyResult<fs::ProtectionFunction> {
    fs::ProtectionFunction::new(
        s(v, "target")?,
        s(v, "mechanism")?,
        ev(&v["capture_efficiency"])?,
        ostr(v, "evidence_note").as_deref().unwrap_or(""),
    )
}

fn material_app(v: &Value) -> PyResult<fs::MaterialApplicability> {
    let orp = match v.get("o_recombination_probability") {
        Some(x) if !x.is_null() => Some(ev(x)?),
        _ => None,
    };
    let aoe = match v.get("ao_erosion_yield") {
        Some(x) if !x.is_null() => Some(ev(x)?),
        _ => None,
    };
    fs::MaterialApplicability::new(
        s(v, "material")?,
        ostr(v, "ao_compatibility").as_deref().unwrap_or("INCOMPLETE_EVIDENCE"),
        ostr(v, "surrogate_label").as_deref().unwrap_or("NONE"),
        orp,
        aoe,
        v.get("evidence_refs").map(strs).unwrap_or_default(),
        ostr(v, "note").as_deref().unwrap_or(""),
    )
}

fn species_list(v: &Value) -> Vec<String> {
    v.get("species").map(strs).unwrap_or_else(|| vec!["O".into(), "N2".into(), "O2".into()])
}

fn stage(v: &Value) -> PyResult<FilterStage> {
    let sp = species_list(v);
    let spr: Vec<&str> = sp.iter().map(|x| x.as_str()).collect();
    let fi = ostr(v, "forward_incidence").unwrap_or_else(|| "diffuse_thermal".into());
    let desc = ostr(v, "description").unwrap_or_default();
    let prot: Vec<_> = v
        .get("protection")
        .and_then(|x| x.as_array())
        .map(|a| a.iter().map(protection).collect::<PyResult<Vec<_>>>())
        .transpose()?
        .unwrap_or_default();
    let mats: Vec<_> = v
        .get("materials")
        .and_then(|x| x.as_array())
        .map(|a| a.iter().map(material_app).collect::<PyResult<Vec<_>>>())
        .transpose()?
        .unwrap_or_default();
    let rve: Vec<(String, String)> = v
        .get("research_variant_evidence")
        .and_then(|x| x.as_array())
        .map(|a| {
            a.iter()
                .map(|p| (p[0].as_str().unwrap_or("").to_string(), p[1].as_str().unwrap_or("").to_string()))
                .collect()
        })
        .unwrap_or_default();
    let factory = s(v, "factory")?;
    let mut st = match factory {
        "none" => FilterStage::none(&spr),
        "tbd" => FilterStage::tbd(
            &ostr(v, "stage_id").unwrap_or_default(),
            &ostr(v, "concept_id").unwrap_or_default(),
            &spr,
            &fi,
            &desc,
            prot,
            mats,
            ostr(v, "role").as_deref().unwrap_or(fs::ROLE_BASELINE),
        )?,
        "catalytic" => FilterStage::catalytic_research_variant(
            &ostr(v, "stage_id").unwrap_or_default(),
            &ostr(v, "concept_id").unwrap_or_default(),
            &spr,
            &fi,
            &desc,
            mats,
            rve,
        )?,
        "custom" => {
            // a stage built field by field (records replace the tbd records), validated as constructed
            let mut st = FilterStage {
                stage_id: ostr(v, "stage_id").unwrap_or_default(),
                concept_id: ostr(v, "concept_id").unwrap_or_default(),
                kind: ostr(v, "kind").unwrap_or_else(|| "element".into()),
                transport: spr.iter().map(|x| (x.to_string(), fs::tbd_species_transport(x))).collect(),
                forward_incidence: fi.clone(),
                regime: ostr(v, "regime").unwrap_or_else(|| "free_molecular".into()),
                face_area_m2: fs::default_face_area(),
                areal_mass_kg_m2: fs::default_areal_mass(),
                protection: prot,
                materials: mats,
                description: desc.clone(),
                role: ostr(v, "role").unwrap_or_else(|| fs::ROLE_BASELINE.into()),
                element_temperature_k: fs::default_element_temperature(),
                energy_accommodation: fs::default_energy_accommodation(),
                contaminant_capacity_kg: fs::default_contaminant_capacity(),
                research_variant_evidence: rve,
            };
            if let Some(Value::Array(drop)) = v.get("drop_routing") {
                for d in drop {
                    let sp_ = d.as_str().unwrap_or("");
                    for (k, t) in st.transport.iter_mut() {
                        if k == sp_ {
                            t.product_to_outlet_f = None;
                            t.product_to_outlet_b = None;
                        }
                    }
                }
            }
            for (pid, rv) in obj(&v["records"]) {
                let e = ev(&rv)?;
                if pid == "face_area_m2" {
                    st.face_area_m2 = e;
                } else if pid == "areal_mass_kg_m2" {
                    st.areal_mass_kg_m2 = e;
                } else {
                    let (k, sp_) = pid.split_once('.').ok_or_else(|| bad("record id"))?;
                    let t = st.transport.iter_mut().find(|(x, _)| x == sp_).ok_or_else(|| bad("record species"))?;
                    if !t.1.set_record(k, e) {
                        return Err(bad("record key"));
                    }
                }
            }
            st
        }
        _ => return Err(bad("factory")),
    };
    if let Some(er) = v.get("element_records").and_then(|x| x.as_object()) {
        for (k, rv) in er {
            let e = ev(rv)?;
            match k.as_str() {
                "element_temperature_K" => st.element_temperature_k = e,
                "energy_accommodation" => st.energy_accommodation = e,
                "contaminant_capacity_kg" => st.contaminant_capacity_kg = e,
                "face_area_m2" => st.face_area_m2 = e,
                "areal_mass_kg_m2" => st.areal_mass_kg_m2 = e,
                _ => return Err(bad("element record")),
            }
        }
    }
    st.validate()?;
    Ok(st)
}

fn inlet(v: &Value) -> PyResult<InletState> {
    let ip = match v.get("incident_power_W") {
        None | Some(Value::Null) => None,
        Some(x) => Some(spmap(x)?),
    };
    let st = InletState {
        mdot_forward_kgps: spmap(&v["mdot_forward_kgps"])?,
        mdot_back_incident_kgps: spmap(&v["mdot_back_incident_kgps"])?,
        back_incident_basis: ostr(v, "back_incident_basis").unwrap_or_default(),
        t_gas_k: onumv(v.get("T_gas_K"))?,
        incidence: ostr(v, "incidence").unwrap_or_default(),
        knudsen_number: onumv(v.get("knudsen_number"))?,
        label: ostr(v, "label").unwrap_or_default(),
        provenance: ostr(v, "provenance").unwrap_or_default(),
        incident_power_w: ip,
        incident_power_source: ostr(v, "incident_power_source").unwrap_or_default(),
    };
    st.validate()?;
    Ok(st)
}

fn case(v: &Value) -> PyResult<Option<SensitivityCase>> {
    if v.is_null() {
        return Ok(None);
    }
    let c = SensitivityCase {
        case_id: ostr(v, "case_id").unwrap_or_default(),
        label: ostr(v, "label").unwrap_or_default(),
        overrides: spmap(&v["overrides"])?,
        rationale: ostr(v, "rationale").unwrap_or_default(),
        regime_assumption: ostr(v, "regime_assumption"),
        temperature_override_k: onumv(v.get("temperature_override_K"))?,
    };
    c.validate()?;
    Ok(Some(c))
}

fn field(v: Option<&Value>) -> Field {
    match v {
        Some(Value::String(x)) if ["NaN", "+inf", "-inf"].contains(&x.as_str()) => {
            Field::Num(as_f64(&Value::String(x.clone())).unwrap_or(f64::NAN))
        }
        Some(Value::String(x)) => Field::Text(x.clone()),
        Some(Value::Number(n)) => Field::Num(n.as_f64().unwrap_or(f64::NAN)),
        Some(_) | None => Field::Other,
    }
}

fn basis(v: &Value) -> RotorStrengthBasis {
    let fl = |k: &str| field(v.get(k));
    let st = match v.get("section_thickness_range_m") {
        Some(Value::Array(a)) if a.len() == 2 => Some((field(a.first()), field(a.get(1)))),
        _ => None,
    };
    let allow = match v.get("allowables") {
        Some(Value::Array(a)) => Some(a.iter().map(|p| (field(p.get(0)), field(p.get(1)), field(p.get(2)))).collect()),
        _ => None,
    };
    RotorStrengthBasis {
        basis_id: fl("basis_id"),
        materials_db_key: fl("materials_db_key"),
        material_spec: fl("material_spec"),
        product_form: fl("product_form"),
        condition: fl("condition"),
        section_thickness_range_m: st,
        design_temperature_k: fl("design_temperature_K"),
        allowable_basis: fl("allowable_basis"),
        allowable_source: fl("allowable_source"),
        allowables: allow,
        density_kg_m3: fl("density_kg_m3"),
        density_source: fl("density_source"),
        factor_yield: fl("factor_yield"),
        factor_ultimate: fl("factor_ultimate"),
        factors_source: fl("factors_source"),
        max_design_speed_rpm: fl("max_design_speed_rpm"),
        proof_spin_basis: fl("proof_spin_basis"),
        registration: fl("registration"),
        proof_spin_not_applicable_reason: fl("proof_spin_not_applicable_reason"),
        notes: ostr(v, "notes").unwrap_or_default(),
    }
}

fn registry(v: Option<&Value>) -> PyResult<Registry> {
    let mut r = Registry::default();
    if let Some(Value::Array(a)) = v {
        for b in a {
            r.register_basis(basis(b))?;
        }
    }
    Ok(r)
}

fn coeffs(v: &Value) -> PyResult<DragCompressor> {
    let mut c = DragCompressor::default();
    for name in FIELDS {
        let Some(x) = v.get(name) else { continue };
        match name {
            "turbo_rows" => c.turbo_rows = x.as_f64().ok_or_else(|| bad("turbo_rows"))? as i64,
            "n_stages" => c.n_stages = x.as_f64().ok_or_else(|| bad("n_stages"))? as i64,
            "rotor_material" => c.rotor_material = x.as_str().ok_or_else(|| bad("material"))?.into(),
            other => {
                c.set_float(other, num(x)?);
            }
        }
    }
    c.rotor_strength_basis_id = ostr(v, "rotor_strength_basis_id");
    c.rotor_stock_thickness_m = onumv(v.get("rotor_stock_thickness_m"))?;
    Ok(c)
}

fn arg(v: Option<&Value>) -> Arg {
    match v {
        None | Some(Value::Null) => Arg::None,
        Some(Value::Number(n)) if n.is_i64() || n.is_u64() => Arg::Int(n.as_i64().unwrap_or(0)),
        Some(x) => as_f64(x).map(Arg::Num).unwrap_or(Arg::Other),
    }
}

fn inlet_record(v: &Value) -> PyResult<cs::InletRecord> {
    let ps = match v.get("p_species_Pa") {
        None | Some(Value::Null) => None,
        Some(x) => Some(spmap(x)?),
    };
    let r = cs::InletRecord {
        record_id: ostr(v, "record_id").unwrap_or_default(),
        mdot_kgps: spmap(&v["mdot_kgps"])?,
        p_total_pa: f(v, "p_total_Pa")?,
        t_k: f(v, "T_K")?,
        label: ostr(v, "label").unwrap_or_default(),
        source: ostr(v, "source").unwrap_or_default(),
        evidence_class: ostr(v, "evidence_class").unwrap_or_default(),
        status: ostr(v, "status").unwrap_or_default(),
        p_species_pa: ps,
        extra: obj(&v["extra"]),
    };
    r.validate()?;
    Ok(r)
}

fn grid(v: &Value) -> PyResult<Option<cs::SearchGrid>> {
    if v.is_null() {
        return Ok(None);
    }
    let d = cs::SearchGrid::default_grid()?;
    let ints = |k: &str, dv: &Vec<i64>| -> Vec<i64> {
        v.get(k)
            .and_then(|x| x.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_f64()).map(|x| x as i64).collect())
            .unwrap_or_else(|| dv.clone())
    };
    Ok(Some(cs::SearchGrid {
        n_turbo: ints("n_turbo", &d.n_turbo),
        a_turbo_m2: v
            .get("a_turbo_m2")
            .and_then(|x| x.as_array())
            .map(|a| a.iter().filter_map(as_f64).collect())
            .unwrap_or(d.a_turbo_m2.clone()),
        n_tip_speeds: v.get("n_tip_speeds").and_then(|x| x.as_i64()).unwrap_or(d.n_tip_speeds),
        n_drag: ints("n_drag", &d.n_drag),
        materials: v.get("materials").map(strs).unwrap_or(d.materials.clone()),
        hub_ratios: v.get("hub_ratios").and_then(|x| x.as_array()).cloned().unwrap_or(d.hub_ratios.clone()),
    }))
}

fn intake_state(v: &Value) -> PyResult<IntakeState> {
    Ok(IntakeState {
        candidate: s(v, "candidate")?.into(),
        area_m2: f(v, "area_m2")?,
        state: s(v, "state")?.into(),
        scenario: s(v, "scenario")?.into(),
        t_k: f(v, "T_K")?,
        mdot_fwd_kgps: sp3(&v["mdot_fwd_kgps"])?,
        p_passive_pa: sp3(&v["p_passive_Pa"])?,
        k_back: sp3(&v["K_back"])?,
        f1_status: s(v, "f1_status")?.into(),
        source: ostr(v, "source").unwrap_or_default(),
        alt_km: f(v, "alt_km")?,
    })
}

fn filter_case(v: &Value) -> PyResult<FilterCase> {
    match s(v, "factory")? {
        "none" => pf::filter_none(),
        "parametric" => pf::filter_parametric(f(v, "tau")?),
        "placeholder" => pf::filter_placeholder(),
        "stage" => pf::filter_case_from_stage(
            s(v, "case_id")?,
            &stage(&v["stage"])?,
            case(&v["case"])?.as_ref(),
            ostr(v, "note").as_deref().unwrap_or(""),
        ),
        _ => Err(bad("filter case factory")),
    }
}

fn plenum(v: &Value) -> PyResult<Plenum> {
    let n = |k: &str| -> PyResult<f64> {
        match v.get(k) {
            Some(Value::Number(x)) => Ok(x.as_f64().unwrap_or(f64::NAN)),
            Some(Value::String(x)) if ["NaN", "+inf", "-inf"].contains(&x.as_str()) => {
                Ok(as_f64(&Value::String(x.clone())).unwrap_or(f64::NAN))
            }
            _ => Err(value_error(format!("Plenum.{k} must be a finite number"))),
        }
    };
    let t = if v.get("T_K").is_some() { n("T_K")? } else { pf::T_CHAIN_K };
    Plenum::new(n("volume_m3")?, n("gamma_wall")?, ostr(v, "wall_case").as_deref().unwrap_or(""), n("leak_area_m2")?, t)
}

fn plant(ctx: Ctx, v: &Value) -> PyResult<CompressorPlant> {
    let t = v.get("T_K").and_then(as_f64).unwrap_or(pf::T_CHAIN_K);
    CompressorPlant::from_design(ctx, &obj(&v["design"]), t)
}

fn chain(ctx: Ctx, v: &Value) -> PyResult<Chain> {
    Ok(Chain {
        intake: intake_state(&v["intake"])?,
        filt: filter_case(&v["filter"])?,
        plant: plant(ctx, &v["plant"])?,
        plenum: plenum(&v["plenum"])?,
    })
}

fn controller(v: &Value) -> PyResult<Controller> {
    Ok(Controller {
        kp: f(v, "Kp")?,
        ti_s: f(v, "Ti_s")?,
        f_valve_hz: f(v, "f_valve_hz")?,
        authority: f(v, "authority")?,
    })
}

fn reservoir_of(v: &Value) -> PyResult<Reservoir> {
    let d = Reservoir::default();
    let g = |k: &str, dv: f64| v.get(k).and_then(as_f64).unwrap_or(dv);
    Ok(Reservoir {
        volume_m3: g("volume_m3", d.volume_m3),
        wall_area_m2: g("wall_area_m2", d.wall_area_m2),
        wall_material: ostr(v, "wall_material").unwrap_or(d.wall_material),
        t_k: g("T_K", d.t_k),
        anode_orifice_area_m2: g("anode_orifice_area_m2", d.anode_orifice_area_m2),
        anode_orifice_k: g("anode_orifice_K", d.anode_orifice_k),
        leak_area_m2: g("leak_area_m2", d.leak_area_m2),
        upstream_collisions: g("upstream_collisions", d.upstream_collisions),
        upstream_material: ostr(v, "upstream_material").unwrap_or(d.upstream_material),
    })
}

fn schedule_input(v: &Value) -> PyResult<u13::ScheduleInput> {
    u13::ScheduleInput::new(s(v, "name")?, s(v, "kind")?, s(v, "source")?)
}

fn control(v: &Value) -> PyResult<u13::Control> {
    match s(v, "mode")? {
        "schedule" => Ok(u13::Control::Schedule(u13::SetpointSchedule::new(
            s(v, "schedule_id")?,
            schedule_input(&v["input"])?,
            arr(v, "breakpoints")?.iter().map(|b| Ok((num(&b[0])?, num(&b[1])?))).collect::<PyResult<Vec<_>>>()?,
            s(v, "label")?,
            s(v, "basis")?,
            ostr(v, "status").as_deref().unwrap_or(u13::SCHEDULE_STATUS),
        )?)),
        "fixed" => {
            Ok(u13::Control::Fixed(u13::FixedSetpoint::new(f(v, "setpoint_Pa")?, s(v, "label")?, s(v, "basis")?)?))
        }
        _ => Err(value_error("control must be an upstream_a9_13.SetpointSchedule or FixedSetpoint")),
    }
}

fn controller_states(v: &Value) -> PyResult<Option<Vec<(String, u13::ControllerState)>>> {
    match v {
        Value::Null => Ok(None),
        Value::Array(a) => {
            let mut out = vec![];
            for p in a {
                out.push((p[0].as_str().unwrap_or("").to_string(), vpairs(&p[1])?));
            }
            Ok(Some(out))
        }
        _ => Err(bad("controller states")),
    }
}

fn segment(v: &Value) -> PyResult<Segment> {
    let fl = |k: &str| -> PyResult<Vec<f64>> { arr(v, k)?.iter().map(num).collect() };
    Ok(Segment {
        event: ostr(v, "event").unwrap_or_default(),
        kind: s(v, "kind")?.into(),
        t_start_s: 0.0,
        duration_s: 0.0,
        t: fl("t")?,
        p: fl("p")?,
        mdot: fl("mdot")?,
        u: fl("u")?,
        x_o: fl("xO")?,
        setpoint_pa: f(v, "setpoint_Pa")?,
        saturated_end: v.get("saturated_end").and_then(|x| x.as_bool()).unwrap_or(false),
        ucmd_end: f64::NAN,
        intake_state: String::new(),
        k_min: v.get("K_min").and_then(as_f64).unwrap_or(f64::NAN),
        k_over_k0_max: v.get("K_over_K0_max").and_then(as_f64).unwrap_or(f64::NAN),
        p_stage_max_pa: v.get("p_stage_max_Pa").and_then(as_f64).unwrap_or(f64::NAN),
        p_inlet_max_pa: v.get("p_inlet_max_Pa").and_then(as_f64).unwrap_or(f64::NAN),
        p_el_max_w: f64::NAN,
        t_comp_max_k: v.get("T_comp_max_K").and_then(as_f64).unwrap_or(f64::NAN),
        t_comp_limit_k: v.get("T_comp_limit_K").and_then(as_f64).unwrap_or(f64::NAN),
    })
}

fn sp3v(v: &Sp3) -> Value {
    fmap(SPECIES.iter().copied().zip(v.iter().copied()))
}

fn case_record(c: &SensitivityCase) -> Value {
    Obj::new()
        .s("case_id", &c.case_id)
        .s("label", &c.label)
        .set("overrides", fmap(c.overrides.iter().map(|(k, v)| (k.as_str(), *v))))
        .s("rationale", &c.rationale)
        .set("regime_assumption", c.regime_assumption.clone().map(Value::String).unwrap_or(Value::Null))
        .set("temperature_override_K", onum(c.temperature_override_k))
        .build()
}

fn err_or<T>(r: PyResult<T>, f: impl FnOnce(T) -> Value) -> Value {
    match r {
        Ok(v) => f(v),
        Err(e) => json!({"__error__": e.class.name()}),
    }
}

// ------------------------------------------------------------------------------------------------ dispatch
struct Env {
    repo: PathBuf,
    mats: MaterialsView,
}

fn dispatch(env: &Env, entry: &str, a: &Value) -> PyResult<Value> {
    let empty = Registry::default();
    let reg_holder;
    let reg = match a.get("registry") {
        Some(r) if !r.is_null() => {
            reg_holder = registry(Some(r))?;
            &reg_holder
        }
        _ => &empty,
    };
    let ctx = Ctx { materials: &env.mats, registry: reg };
    let mats = &env.mats;
    Ok(match entry {
        // ------------------------------------------------------------------ filter
        "filter.cole" => fs::cole_transmission_probability(f(a, "l_over_d")?)?.to_dict(),
        "filter.plate" => fs::perforated_plate_alpha(f(a, "l_over_d")?, f(a, "open_fraction")?)?.to_dict(),
        "filter.mean_speed" => fnum(fs::mean_speed_m_s(s(a, "species")?, f(a, "T_K")?)?),
        "filter.tbd_transport" => {
            let t = fs::tbd_species_transport(s(a, "species")?);
            let mut m = Map::new();
            for (k, e) in t.records() {
                m.insert(k.into(), e.to_dict());
            }
            Value::Object(m)
        }
        "filter.stage_parameters" => {
            let st = stage(&a["stage"])?;
            Obj::new().set("parameter_ids", slist(st.parameter_ids())).set("to_dict", st.to_dict()).build()
        }
        "filter.apply" => {
            let st = stage(&a["stage"])?;
            let inl = inlet(&a["inlet"])?;
            let c = case(&a["case"])?;
            let r = st.apply(&inl, c.as_ref())?;
            let ri = err_or(fs::retained_inventory_kg(&r, f(a, "duration_s")?), |v| v);
            Obj::new()
                .set("result", r.to_dict())
                .set("species_transmission", r.species_transmission())
                .set("to_f3_record", r.to_f3_record())
                .set("to_f1_record", r.to_f1_record())
                .set("retained_inventory", ri)
                .build()
        }
        "filter.backflow" => {
            let st = stage(&a["stage"])?;
            let c = case(&a["case"])?;
            st.backflow_coupling(onumv(a.get("T_gas_K"))?, c.as_ref())?
        }
        "filter.placeholder" => {
            let st = stage(&a["stage"])?;
            let c = fs::placeholder_sensitivity_case(&st)?;
            Obj::new().set("values", fs::repository_placeholder_values()).set("case", case_record(&c)).build()
        }
        "filter.construct" => {
            let sp = &a["spec"];
            match s(a, "what")? {
                "ev" => {
                    ev(sp)?;
                }
                "protection" => {
                    protection(sp)?;
                }
                "material" => {
                    material_app(sp)?;
                }
                "inlet" => {
                    inlet(sp)?;
                }
                "case" => {
                    case(sp)?;
                }
                "stage" => {
                    stage(sp)?;
                }
                _ => return Err(bad("construct what")),
            }
            Value::String("CONSTRUCTED".into())
        }
        // ------------------------------------------------------------------ compressor
        "compressor.run" => {
            let c = coeffs(&a["coeffs"])?;
            Value::Object(c.run(
                ctx,
                f(a, "p_in_Pa")?,
                &spmap(&a["mdot"])?,
                a.get("self_consistent").and_then(|x| x.as_bool()).unwrap_or(true),
            )?)
        }
        "compressor.size_for" => {
            let mut c = coeffs(&a["coeffs"])?;
            Value::Object(c.size_for(
                ctx,
                f(a, "p_in_Pa")?,
                &spmap(&a["mdot"])?,
                f(a, "CR_target")?,
                f(a, "rpm_max")?,
                i(a, "max_turbo_rows")?,
                i(a, "max_drag_stages")?,
            )?)
        }
        "compressor.basis_problems" => slist(rs::basis_problems(&basis(&a["basis"]))),
        "compressor.allowables_at" => match rs::allowables_at(&basis(&a["basis"]), f(a, "T_K")?) {
            Some((y, u)) => Value::Array(vec![fnum(y), fnum(u)]),
            None => Value::Null,
        },
        "compressor.tip_speed_allowable" => fnum(rs::tip_speed_allowable(&basis(&a["basis"]))?),
        "compressor.qualify_rotor" => rs::qualify_rotor(
            reg,
            a.get("basis_id").and_then(|x| x.as_str()),
            s(a, "rotor_material")?,
            arg(a.get("tip_speed_mps")),
            arg(a.get("rpm")),
            arg(a.get("T_rotor_K")),
            arg(a.get("stock_thickness_m")),
        )?,
        "compressor.register_basis" => {
            let mut r = registry(a.get("registry_before"))?;
            r.register_basis(basis(&a["basis"]))?;
            Value::String("REGISTERED".into())
        }
        "compressor.inlet_record" => {
            let r = inlet_record(&a["inlet"])?;
            let mp = r.module_partial_pressures()?;
            Obj::new()
                .set("as_dict", r.as_dict())
                .set("module_partial_pressures", fmap(mp.iter().map(|(k, v)| (k.as_str(), *v))))
                .build()
        }
        "compressor.search_grid" => {
            let g = match grid(&a["grid"])? {
                Some(g) => g,
                None => cs::SearchGrid::default_grid()?,
            };
            g.validate(ctx)?;
            Value::Array(g.designs()?.into_iter().map(Value::Object).collect())
        }
        "compressor.r_turbo_from_area" => fnum(cs::r_turbo_from_area(f(a, "a_m2")?, f(a, "hub_ratio")?)?),
        "compressor.hub_geometry" => Value::Object(cs::hub_geometry(f(a, "a_m2")?, f(a, "hub_ratio")?)?),
        "compressor.rpm_from_tip" => fnum(cs::rpm_from_tip(f(a, "u_mps")?, f(a, "r_m")?)?),
        "compressor.material_admission" => {
            let extra = a.get("extra").and_then(|x| x.as_object()).cloned();
            cs::material_admission(ctx, s(a, "material")?, extra.as_ref())?
        }
        "compressor.validate_coefficient" => fnum(cs::validate_coefficient(s(a, "name")?, a.get("value"))?),
        "compressor.validate_design" => {
            cs::validate_design(ctx, &obj(&a["design"]))?;
            Value::String("VALID".into())
        }
        "compressor.strict_blockers" => {
            let inl = inlet_record(&a["inlet"])?;
            let evm = a.get("coefficient_evidence").and_then(|x| x.as_object()).cloned();
            Value::Array(cs::strict_blockers(ctx, &inl, evm.as_ref())?)
        }
        "compressor.evaluate_design" => {
            let inl = inlet_record(&a["inlet"])?;
            let evm = a.get("coefficient_evidence").and_then(|x| x.as_object()).cloned();
            cs::evaluate_design(ctx, &obj(&a["design"]), &inl, s(a, "mode")?, evm.as_ref())?
        }
        "compressor.stage_trace" => cs::stage_trace(&coeffs(&a["coeffs"])?, f(a, "p_in_Pa")?, &spmap(&a["mdot"])?)?,
        "compressor.drag_knudsen" => {
            fnum(cs::drag_knudsen_upper(&spmap(&a["p_species"])?, f(a, "T_K")?, f(a, "h_m")?)?)
        }
        "compressor.pareto_front" => {
            let recs = arr(a, "records")?;
            let ids = if s(a, "objectives")? == "secondary" {
                cs::pareto_front(recs, &cs::SECONDARY_OBJECTIVES)
            } else {
                cs::pareto_front(recs, &cs::PRIMARY_OBJECTIVES)
            };
            slist(ids)
        }
        "compressor.synthesize" => {
            let inl = inlet_record(&a["inlet"])?;
            let g = grid(&a["grid"])?;
            let evm = a.get("coefficient_evidence").and_then(|x| x.as_object()).cloned();
            cs::synthesize(ctx, &inl, s(a, "mode")?, g.as_ref(), evm.as_ref())?
        }
        "compressor.size_for_comparison" => {
            let inl = inlet_record(&a["inlet"])?;
            cs::size_for_comparison(
                ctx,
                &inl,
                f(a, "cr_target")?,
                f(a, "a_turbo_m2")?,
                arr(a, "front_records")?,
                s(a, "material")?,
                s(a, "mode")?,
            )?
        }
        "compressor.ledger_slot" => cs::compressor_ledger_slot(
            onumv(a.get("compressor_P_W"))?,
            ostr(a, "compressor_source").as_deref().unwrap_or(""),
        ),
        "compressor.constants" => compressor_constants(),
        // ------------------------------------------------------------------ plenum
        "plenum.orbital_period" => fnum(pf::orbital_period_s(f(a, "alt_km")?)?),
        "plenum.cbar" => fnum(pf::cbar(s(a, "species")?, f(a, "T_K")?)?),
        "plenum.kt_over_m" => fnum(pf::kt_over_m(s(a, "species")?, f(a, "T_K")?)?),
        "plenum.f1_candidate_id" => {
            Value::String(pf::f1_candidate_id(f(a, "area_m2")?, f(a, "L_over_d")?, f(a, "phi")?))
        }
        "plenum.status_from_reasons" => Value::String(pf::status_from_reasons(&strs(&a["reasons"])).into()),
        "plenum.reasons_from_bits" => slist(pf::reasons_from_bits(i(a, "bits")?)),
        "plenum.intake" => {
            let it = intake_state(&a["intake"])?;
            Obj::new()
                .set("q_fwd", sp3v(&it.q_fwd()?))
                .set("e_f1", sp3v(&it.e_f1()?))
                .set("escape_probability", sp3v(&it.escape_probability()?))
                .build()
        }
        "plenum.filter_case" => {
            let fc = filter_case(&a["filter"])?;
            let mut o = Obj::new().set("case", fc.to_dict());
            if let Some(av) = a.get("a") {
                let (d, e) = fc.coefficients(&sp3(av)?)?;
                o = o.set("D", sp3v(&d)).set("E", sp3v(&e));
            }
            o.build()
        }
        "plenum.filter_cases" => {
            let taus: Vec<f64> = arr(a, "taus")?.iter().map(num).collect::<PyResult<_>>()?;
            Value::Array(pf::filter_cases(&taus)?.iter().map(|c| c.to_dict()).collect())
        }
        "plenum.plant" => {
            let p = plant(ctx, &a["plant"])?;
            let stages: Vec<Value> = p
                .stages()?
                .iter()
                .map(|st| {
                    Obj::new()
                        .s("kind", st.kind)
                        .f("S", st.s)
                        .f("u", st.u)
                        .f("A_term", st.a_term)
                        .set("K0", sp3v(&st.k0))
                        .build()
                })
                .collect();
            let ch = p.characteristic()?;
            let mut chm = Map::new();
            for (k, sp_) in SPECIES.iter().enumerate() {
                chm.insert(sp_.to_string(), Value::Array(vec![fnum(ch[k].0), fnum(ch[k].1)]));
            }
            let cas =
                err_or(p.cascade(mats, &sp3(&a["p_in"])?, &sp3(&a["Q"])?), |c| CompressorPlant::cascade_record(&c));
            Obj::new()
                .s("design_id", &p.design_id)
                .set("stages", Value::Array(stages))
                .set("characteristic", Value::Object(chm))
                .f("leak_m3_s", p.leak_m3_s())
                .f("shaft_hz", p.shaft_hz())
                .set("cascade", cas)
                .build()
        }
        "plenum.plenum" => {
            let p = plenum(&a["plenum"])?;
            let r = p.reservoir(1e-6)?;
            Obj::new()
                .f("wall_area_m2", p.wall_area_m2()?)
                .f("k_rec_m3_s", p.k_rec_m3_s()?)
                .set("leak_m3_s", sp3v(&p.leak3()?))
                .set("feed_c", sp3v(&p.feed3()?))
                .set(
                    "reservoir",
                    Obj::new()
                        .f("volume_m3", r.volume_m3)
                        .f("wall_area_m2", r.wall_area_m2)
                        .s("wall_material", &r.wall_material)
                        .f("T_K", r.t_k)
                        .f("anode_orifice_area_m2", r.anode_orifice_area_m2)
                        .f("anode_orifice_K", r.anode_orifice_k)
                        .f("leak_area_m2", r.leak_area_m2)
                        .f("upstream_collisions", r.upstream_collisions)
                        .s("upstream_material", &r.upstream_material)
                        .build(),
                )
                .build()
        }
        "plenum.chain" => Chain::coeffs_record(&chain(ctx, &a["chain"])?.node_coefficients(f(a, "density_factor")?)?),
        "plenum.solve_pressures" => {
            let ch = chain(ctx, &a["chain"])?;
            let co = ch.node_coefficients(1.0)?;
            let pl = &ch.plenum;
            let (p3, p2) = pf::solve_pressures(&co, f(a, "a_eq")?, pl.k_rec_m3_s()?, &pl.leak3()?, &pl.feed3()?, true)?;
            Obj::new().set("p3", sp3v(&p3)).set("p2", sp3v(&p2)).build()
        }
        "plenum.area_for_pressure" => {
            let ch = chain(ctx, &a["chain"])?;
            let co = ch.node_coefficients(1.0)?;
            let pl = &ch.plenum;
            let sol = pf::area_for_pressure(&co, f(a, "target")?, pl.k_rec_m3_s()?, &pl.leak3()?, &pl.feed3()?, true)?;
            Obj::new()
                .f("a_eq", sol.a_eq)
                .f("p_dead", sol.p_dead)
                .f("resid", sol.resid)
                .b("ok", sol.ok)
                .b("bisection_failed", pf::bisection_failed(sol.a_eq, sol.resid))
                .build()
        }
        "plenum.bisection_failed" => Value::Bool(pf::bisection_failed(f(a, "a_eq")?, f(a, "resid")?)),
        "plenum.lambda_upper" => fnum(pf::lambda_upper_m(&sp3(&a["p3"])?, f(a, "T_K")?)?),
        "plenum.steady" => pf::steady_operating_point(
            &chain(ctx, &a["chain"])?,
            mats,
            f(a, "target")?,
            a.get("density_factor").and_then(as_f64).unwrap_or(1.0),
            a.get("feed_factor").and_then(as_f64).unwrap_or(1.0),
        )?,
        "plenum.evaluate" => pf::evaluate(&chain(ctx, &a["chain"])?, mats, f(a, "target")?, s(a, "mode")?)?,
        "plenum.sweep" => {
            let intakes: Vec<IntakeState> = arr(a, "intakes")?.iter().map(intake_state).collect::<PyResult<_>>()?;
            let fc = filter_case(&a["filter"])?;
            let p = plant(ctx, &a["plant"])?;
            let pl = plenum(&a["plenum"])?;
            let targets: Vec<f64> = arr(a, "targets")?.iter().map(num).collect::<PyResult<_>>()?;
            let f1ok: Option<Vec<bool>> = a
                .get("f1_ok")
                .and_then(|x| x.as_array())
                .map(|v| v.iter().map(|b| b.as_bool().unwrap_or(false)).collect());
            let side = pf::intake_side(&intakes, &fc, a.get("density_factor").and_then(as_f64).unwrap_or(1.0))?;
            let sw = pf::steady_sweep(&side, &p, &pl, mats, &targets, f1ok.as_deref())?;
            // INV-P-02: the scalar twin at every point (Rust only)
            let mut scalar = vec![];
            for it in &intakes {
                let ch = Chain { intake: it.clone(), filt: fc.clone(), plant: p.clone(), plenum: pl.clone() };
                let row: Vec<Value> = targets
                    .iter()
                    .map(|t| err_or(pf::steady_operating_point(&ch, mats, *t, 1.0, 1.0), |v| v))
                    .collect();
                scalar.push(Value::Array(row));
            }
            let sidev = Obj::new()
                .set("f", Value::Array(side.0.iter().map(sp3v).collect()))
                .set("e", Value::Array(side.1.iter().map(sp3v).collect()))
                .build();
            Obj::new().set("side", sidev).set("sweep", sw.to_value()).set("_scalar", Value::Array(scalar)).build()
        }
        "plenum.ripple" => pf::ripple_transfer(&chain(ctx, &a["chain"])?, f(a, "a_eq")?, f(a, "f_hz")?)?,
        "plenum.inlet_tau" => fnum(pf::inlet_node_tau_per_m3(&chain(ctx, &a["chain"])?)?),
        "plenum.settling" => {
            let t: Vec<f64> = arr(a, "t")?.iter().map(num).collect::<PyResult<_>>()?;
            let y: Vec<f64> = arr(a, "y")?.iter().map(num).collect::<PyResult<_>>()?;
            onum(tr::settling_time(&t, &y, f(a, "final")?, f(a, "band")?))
        }
        "plenum.segment_metrics" => tr::segment_metrics(&segment(&a["segment"])?, f(a, "p_prev_final")?),
        "plenum.domain_reasons" => {
            let segs: Vec<Segment> = arr(a, "segments")?.iter().map(segment).collect::<PyResult<_>>()?;
            slist(tr::domain_reasons(&segs))
        }
        "plenum.event_sequence" => Value::Array(
            tr::event_sequence(&intake_state(&a["intake"])?, f(a, "r0")?, f(a, "window_s")?)
                .iter()
                .map(|e| e.to_dict())
                .collect(),
        ),
        "plenum.transient_run" | "plenum.transient_case" => {
            let fc = filter_case(&a["filter"])?;
            let p = plant(ctx, &a["plant"])?;
            let pl = plenum(&a["plenum"])?;
            let c = controller(&a["controller"])?;
            let design = intake_state(&a["intake"])?;
            let r0 = f(a, "r0")?;
            let rtol = a.get("rtol").and_then(as_f64).unwrap_or(pf::RTOL);
            let method = ostr(a, "method");
            let window = a.get("window_s").and_then(as_f64).unwrap_or(tr::WINDOW_S);
            if entry == "plenum.transient_run" {
                let run = tr::TransientRun::new(&fc, &p, &pl, c, mats, &design, r0, rtol, method.as_deref())?;
                run.run(&tr::event_sequence(&design, r0, window), 150, None)?.to_value(true)
            } else {
                let oc: Option<Vec<String>> = a.get("orbit_check").and_then(|x| x.get("reasons")).map(strs);
                tr::transient_case(&fc, &p, &pl, c, mats, &design, r0, oc.as_deref(), window, rtol, method.as_deref())?
                    .0
            }
        }
        "plenum.orbit_qs" => {
            let fc = filter_case(&a["filter"])?;
            let p = plant(ctx, &a["plant"])?;
            let pl = plenum(&a["plenum"])?;
            let states: Vec<IntakeState> = arr(a, "states")?.iter().map(intake_state).collect::<PyResult<_>>()?;
            tr::orbit_quasi_static(
                &fc,
                &p,
                &pl,
                mats,
                &states,
                f(a, "r0")?,
                f(a, "amplitude")?,
                f(a, "a_max_m2")?,
                i(a, "n_phase")? as usize,
            )?
        }
        "plenum.orbit_sim" => {
            let fc = filter_case(&a["filter"])?;
            let p = plant(ctx, &a["plant"])?;
            let pl = plenum(&a["plenum"])?;
            tr::orbit_simulated(
                &fc,
                &p,
                &pl,
                controller(&a["controller"])?,
                mats,
                &intake_state(&a["design"])?,
                &intake_state(&a["state"])?,
                f(a, "r0")?,
                f(a, "amplitude")?,
            )?
        }
        "plenum.strict_blockers" => pf::strict_blockers(),
        "plenum.pareto_ids" => {
            let objs = strs(&a["objectives"]);
            let o: Vec<&str> = objs.iter().map(|x| x.as_str()).collect();
            slist(pf::pareto_ids(arr(a, "rows")?, &o))
        }
        "plenum.controller_state" => {
            let cs_ = pf::intake_controller_state(&intake_state(&a["intake"])?, &[pf::nav_altitude_input()])?;
            Value::Array(cs_.into_iter().map(|(k, v)| Value::Array(vec![Value::String(k), v])).collect())
        }
        "plenum.scheduled" | "plenum.compare_modes" => {
            let fc = filter_case(&a["filter"])?;
            let p = plant(ctx, &a["plant"])?;
            let pl = plenum(&a["plenum"])?;
            let intakes: Vec<IntakeState> = arr(a, "intakes")?.iter().map(intake_state).collect::<PyResult<_>>()?;
            let cst = controller_states(&a["controller_states"])?;
            let req = strs(&a["required"]);
            if entry == "plenum.scheduled" {
                pf::scheduled_operation(&fc, &p, &pl, mats, &intakes, &control(&a["control"])?, cst.as_deref(), &req)?
            } else {
                let sch = match control(&a["schedule"])? {
                    u13::Control::Schedule(s_) => s_,
                    _ => {
                        return Err(value_error(
                            "compare_control_modes(schedule=SetpointSchedule, fixed=FixedSetpoint)",
                        ))
                    }
                };
                let fx = match control(&a["fixed"])? {
                    u13::Control::Fixed(f_) => f_,
                    _ => {
                        return Err(value_error(
                            "compare_control_modes(schedule=SetpointSchedule, fixed=FixedSetpoint)",
                        ))
                    }
                };
                pf::compare_control_modes(&fc, &p, &pl, mats, &intakes, &sch, &fx, cst.as_deref(), &req)?
            }
        }
        "plenum.constants" => plenum_constants(),
        // ------------------------------------------------------------------ reservoir
        "reservoir.conductance" => {
            fnum(reservoir_of(&a["res"])?.conductance(s(a, "species")?, f(a, "area")?, f(a, "K")?)?)
        }
        "reservoir.steady" => Value::Object(reservoir_of(&a["res"])?.steady_state(mats, &spmap(&a["mdot"])?)?),
        "reservoir.size_orifice" => {
            let mut r = reservoir_of(&a["res"])?;
            let rec = reservoir::size_orifice_for_pressure(&mut r, mats, &spmap(&a["mdot"])?, f(a, "p_target")?)?;
            Obj::new().set("report", rec).f("area_after", r.anode_orifice_area_m2).build()
        }
        "reservoir.startup" => reservoir::startup_transient(
            &reservoir_of(&a["res"])?,
            mats,
            &spmap(&a["mdot"])?,
            f(a, "p_ignite")?,
            f(a, "spinup_s")?,
            f(a, "t_end_s")?,
            f(a, "dt_s")?,
        )?,
        // ------------------------------------------------------------------ upstream
        "upstream.pressure_domain" => {
            let p = match &a["p"] {
                Value::Number(n) => u13::Num::F(n.as_f64().unwrap_or(f64::NAN)),
                Value::String(x) if ["NaN", "+inf", "-inf"].contains(&x.as_str()) => {
                    u13::Num::F(as_f64(&a["p"]).unwrap_or(f64::NAN))
                }
                _ => u13::Num::Other,
            };
            Value::String(u13::pressure_domain_status(p).into())
        }
        // a non-number target is not finite for the reference (_finite) -> A913RuleError, as for NaN
        "upstream.classify" => u13::classify_pressure_target(as_f64(&a["p"]).unwrap_or(f64::NAN))?,
        "upstream.schedule_input" => {
            let si = schedule_input(&a["input"])?;
            json!({"name": si.name, "kind": si.kind, "source": si.source})
        }
        "upstream.control" => {
            let c = control(&a["control"])?;
            Obj::new().s("mode", c.mode()).set("to_dict", c.to_dict()).build()
        }
        "upstream.setpoint" => control(&a["control"])?.setpoint(&vpairs(&a["state"])?)?,
        "upstream.controller_view" => {
            let inputs: Vec<u13::ScheduleInput> =
                arr(a, "inputs")?.iter().map(schedule_input).collect::<PyResult<_>>()?;
            let mapping: Vec<(String, String)> =
                vpairs(&a["mapping"])?.into_iter().map(|(k, v)| (k, v.as_str().unwrap_or("").to_string())).collect();
            let out = u13::controller_view(&vpairs(&a["full_state"])?, &inputs, &mapping)?;
            Value::Array(out.into_iter().map(|(k, v)| Value::Array(vec![Value::String(k), v])).collect())
        }
        "upstream.combine" => {
            let st = strs(&a["statuses"]);
            let r: Vec<&str> = st.iter().map(|x| x.as_str()).collect();
            Value::String(u13::combine_value_status(&r)?.into())
        }
        "upstream.constraint" => Value::String(u13::constraint_status(a["ok"].as_bool(), s(a, "value_status")?).into()),
        "upstream.h1_tolerance" => {
            // a non-number value_frac (e.g. a bool) is not finite for the reference (_finite)
            let vf = match a.get("value_frac") {
                None | Some(Value::Null) => None,
                Some(x) => Some(as_f64(x).unwrap_or(f64::NAN)),
            };
            let h = u13::H1Tolerance::new(s(a, "quantity")?, vf, s(a, "status")?, s(a, "source")?)?;
            json!({"quantity": h.quantity, "value_frac": onum(h.value_frac), "status": h.status, "source": h.source})
        }
        "upstream.governing_band" => {
            let h = match a.get("h1") {
                Some(v) if !v.is_null() => {
                    if v.get("tbd").and_then(|x| x.as_bool()) == Some(true) {
                        Some(u13::H1Tolerance::tbd(s(v, "quantity")?)?)
                    } else {
                        Some(u13::H1Tolerance::new(
                            s(v, "quantity")?,
                            onumv(v.get("value_frac"))?,
                            s(v, "status")?,
                            s(v, "source")?,
                        )?)
                    }
                }
                _ => None,
            };
            u13::governing_band(s(a, "quantity")?, f(a, "f4")?, h.as_ref())?
        }
        "upstream.coverage" => {
            let m = match &a["mdot"] {
                Value::Number(n) => u13::Num::F(n.as_f64().unwrap_or(f64::NAN)),
                Value::String(x) if ["NaN", "+inf", "-inf"].contains(&x.as_str()) => {
                    u13::Num::F(as_f64(&a["mdot"]).unwrap_or(f64::NAN))
                }
                _ => u13::Num::Other,
            };
            u13::characterization_coverage(m)
        }
        "upstream.fixed_gate" => {
            u13::refuse_fixed_mass_flow_gate(!a["gate"].is_null())?;
            Value::String("OK".into())
        }
        "upstream.flight_requirement" => u13::flight_feed_requirement(a.get("status").and_then(|x| x.as_str())),
        "upstream.flow_gap" => u13::flow_gap_record(),
        "upstream.lowering" => {
            let v = match a.get("value_mgps") {
                None | Some(Value::Null) => None,
                Some(Value::Number(n)) => Some(u13::Num::F(n.as_f64().unwrap_or(f64::NAN))),
                Some(x) if as_f64(x).is_some() => Some(u13::Num::F(as_f64(x).unwrap_or(f64::NAN))),
                Some(_) => Some(u13::Num::Other),
            };
            u13::refuse_feed_requirement_lowering(s(a, "basis")?, v)?;
            Value::String("OK".into())
        }
        "upstream.state_coverage" => Value::Object(u13::state_coverage(&strs(&a["used"]), &strs(&a["required"]))?),
        "upstream.dense" => u13::dense_state_only_operation(
            &strs(&a["used"]),
            &strs(&a["required"]),
            a.get("s615").and_then(|x| x.as_str()),
        )?,
        "upstream.robust_set" => {
            let sp = &a["set"];
            let set = u13::RobustParetoSet::new(
                s(sp, "set_id")?,
                s(sp, "version")?,
                strs(&sp["members"]),
                strs(&sp["objectives"]),
                s(sp, "label")?,
                s(sp, "provenance")?,
                sp.get("regeneration_triggers").filter(|x| !x.is_null()).map(strs),
                sp.get("regenerated_after").map(strs).unwrap_or_default(),
            )?;
            match s(a, "op")? {
                "to_dict" => set.to_dict()?,
                "representative" => set.representative()?,
                "engineering_reference" => set.engineering_reference(s(a, "member")?, s(a, "purpose")?)?,
                "pending" => slist(set.pending_triggers()),
                _ => return Err(bad("robust op")),
            }
        }
        "upstream.cite" => {
            let k = strs(&a["keys"]);
            let r: Vec<&str> = k.iter().map(|x| x.as_str()).collect();
            u13::cite(&r)?
        }
        "upstream.verify_decisions" => u13::verify_decision_records(&env.repo),
        "upstream.candidate" => {
            let o = &a["obj"];
            let c = if s(o, "kind")? == "mapping" {
                u13::CandidateObj::Mapping { evidence_status: ostr(o, "evidence_status") }
            } else {
                u13::CandidateObj::Object {
                    evidence_status: ostr(o, "evidence_status"),
                    valid_design_evidence: o.get("valid_design_evidence").and_then(|x| x.as_bool()),
                }
            };
            u13::refuse_candidate_evidence(&c)?;
            Value::String("OK".into())
        }
        "upstream.constants" => upstream_constants(),
        _ => return Err(bad(&format!("unknown entry {entry}"))),
    })
}

fn compressor_constants() -> Value {
    let roles: Vec<Value> = cs::FIELD_ROLES.iter().map(|(f_, r, n, u, t)| json!([f_, r, n, u, t])).collect();
    let dom: Vec<Value> = cs::COEFFICIENT_DOMAIN.iter().map(|(k, d)| json!([k, d])).collect();
    Obj::new()
        .set("module_defaults", cs::module_defaults())
        .set("FIELD_ROLES", Value::Array(roles))
        .set("COEFFICIENT_DOMAIN", Value::Array(dom))
        .set("REASONS", slist(cs::REASONS))
        .set("DOMAIN_REASONS", slist(cs::DOMAIN_REASONS))
        .set("INLET_INDEPENDENT_REASONS", slist(cs::INLET_INDEPENDENT_REASONS))
        .set("HUB_RATIO_PARAMETRIC", abep_gaspath::rec::flist(&cs::HUB_RATIO_PARAMETRIC))
        .set("HUB_BOUND_SOURCES", slist(cs::HUB_BOUND_SOURCES))
        .set("CFRP_EXTRA_BASIS_KEYS", slist(cs::CFRP_EXTRA_BASIS_KEYS))
        .f("P_MOLECULAR_LIMIT_PA", cs::P_MOLECULAR_LIMIT_PA)
        .f("KN_FREE_MOLECULAR_MIN", cs::KN_FREE_MOLECULAR_MIN)
        .set("SIGMA_C_M2", fmap(cs::SIGMA_C_M2))
        .f("U_TIP_PUBLISHED_MAX_MPS", cs::U_TIP_PUBLISHED_MAX_MPS)
        .f("TI64_FTY_A_BASIS_PA", cs::TI64_FTY_A_BASIS_PA)
        .f("RECIRC_RTOL", cs::RECIRC_RTOL)
        .f("MIRROR_RTOL", cs::MIRROR_RTOL)
        .f("RPM_SEARCH_MIN", cs::RPM_SEARCH_MIN)
        .set("SIZE_FOR_MAX_TURBO_ROWS", cs::SIZE_FOR_MAX_TURBO_ROWS)
        .set("SIZE_FOR_MAX_DRAG_STAGES", cs::SIZE_FOR_MAX_DRAG_STAGES)
        .f("OWNER_MASS_ALLOCATION_KG", cs::OWNER_MASS_ALLOCATION_KG)
        .f("LI2015_INLET_DIAMETER_M", cs::LI2015_INLET_DIAMETER_M)
        .set("A_INLET_MIN_B025_RANGE_M2", json!([cs::A_INLET_MIN_B025_RANGE_M2.0, cs::A_INLET_MIN_B025_RANGE_M2.1]))
        .set("CITED_ALLOWABLES_PA", fmap(cs::CITED_ALLOWABLES_PA))
        .set("MATERIALS_EXCLUDED", json!({"Al6061": cs::MATERIALS_EXCLUDED[0].1, "CFRP": cs::MATERIALS_EXCLUDED[1].1}))
        .s("LEGACY_SENSITIVITY_LABEL", rs::LEGACY_SENSITIVITY_LABEL)
        .s("OWNER_DECISION_ID", rs::OWNER_DECISION_ID)
        .set("REFERENCE_RECORDS", rs::reference_records())
        .set("RECIRC_MAX_ITER", abep_gaspath::compressor::RECIRC_MAX_ITER)
        .f("DragCompressor.RECIRC_RTOL", abep_gaspath::compressor::RECIRC_RTOL)
        .s("GAEDE_IN_DOMAIN", abep_gaspath::compressor::GAEDE_IN_DOMAIN)
        .s("GAEDE_OUT_OF_DOMAIN", abep_gaspath::compressor::GAEDE_OUT_OF_DOMAIN)
        .build()
}

fn plenum_constants() -> Value {
    Obj::new()
        .set("REASONS", slist(pf::REASONS))
        .set("OOD_REASONS", slist(pf::OOD_REASONS))
        .set("MODEL_ERROR_REASONS", slist(pf::MODEL_ERROR_REASONS))
        .f("P_DOMAIN_PA", pf::P_DOMAIN_PA)
        .f("KN_MIN", pf::KN_MIN)
        .f("K_TOL", pf::K_TOL)
        .f("SETTLE_BAND", pf::SETTLE_BAND)
        .f("RTOL", pf::RTOL)
        .f("RTOL_REFERENCE", pf::RTOL_REFERENCE)
        .f("ATOL_SCALED", pf::ATOL_SCALED)
        .f("MASS_TOL", pf::MASS_TOL)
        .set("BISECT_ITERS", pf::BISECT_ITERS)
        .set("A_EQ_BRACKET_M2", json!([pf::A_EQ_BRACKET_M2.0, pf::A_EQ_BRACKET_M2.1]))
        .f("BISECT_RTOL", pf::BISECT_RTOL)
        .s("INTEGRATOR_METHOD", pf::INTEGRATOR_METHOD)
        .s("INTEGRATOR_REFERENCE", pf::INTEGRATOR_REFERENCE)
        .f("T_CHAIN_K", pf::T_CHAIN_K)
        .f("RES_DEFAULT_LEAK_AREA_M2", pf::RES_DEFAULT_LEAK_AREA_M2)
        .f("WINDOW_S", tr::WINDOW_S)
        .f("SETPOINT_STEP", tr::SETPOINT_STEP)
        .f("FEED_PATH_STEP", tr::FEED_PATH_STEP)
        .f("SUPPLY_STEP", tr::SUPPLY_STEP)
        .set("OBJECTIVES", slist(tr::OBJECTIVES))
        .set("REPORTED_NOT_OPTIMISED", slist(tr::REPORTED_NOT_OPTIMISED))
        .set("TRANSIENT_FRAMEWORK", tr::transient_framework())
        .set("SS_MAX_ITER", reservoir::SS_MAX_ITER)
        .f("SS_RTOL", reservoir::SS_RTOL)
        .set("ORIFICE_BRACKET_M2", json!([reservoir::ORIFICE_BRACKET_M2.0, reservoir::ORIFICE_BRACKET_M2.1]))
        .set("ORIFICE_BISECTION_STEPS", reservoir::ORIFICE_BISECTION_STEPS)
        .f("ORIFICE_P_RTOL", reservoir::ORIFICE_P_RTOL)
        .build()
}

fn upstream_constants() -> Value {
    let dec: Vec<Value> = u13::DECISIONS.iter().map(|d| json!([d.key, d.md, d.json, d.json_sha256, d.ids])).collect();
    Obj::new()
        .set("DECISIONS", Value::Array(dec))
        .set("RFP_CLAUSES", Value::Array(u13::RFP_CLAUSES.iter().map(|(k, v)| json!([k, v])).collect()))
        .set("VALUE_STATUSES", slist(u13::VALUE_STATUSES))
        .f("P_FREE_MOLECULAR_LIMIT_PA", u13::P_FREE_MOLECULAR_LIMIT_PA)
        .set("TRANSITIONAL_MODEL", u13::transitional_model())
        .set("DESIGN_DIRECTIONS", u13::design_directions())
        .set("INPUT_KINDS", slist(u13::INPUT_KINDS))
        .set("ORACLE_KEYS", slist(u13::ORACLE_KEYS))
        .set("F4_TRANSIENT_FRAMEWORK", u13::f4_transient_framework())
        .set(
            "CHARACTERIZATION_COVERAGE_MGPS",
            json!([u13::CHARACTERIZATION_COVERAGE_MGPS.0, u13::CHARACTERIZATION_COVERAGE_MGPS.1]),
        )
        .set("FEED_STATE_FIELDS", slist(u13::FEED_STATE_FIELDS))
        .set("FLOW_GAP_ORDER", u13::flow_gap_order())
        .set("FORBIDDEN_FEED_REQUIREMENT_BASES", slist(u13::FORBIDDEN_FEED_REQUIREMENT_BASES))
        .set("REGENERATION_TRIGGERS", slist(u13::REGENERATION_TRIGGERS))
        .build()
}

fn main() {
    let mut raw = String::new();
    if std::io::stdin().read_to_string(&mut raw).is_err() {
        std::process::exit(2);
    }
    let req: Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("bad request: {e}");
            std::process::exit(2);
        }
    };
    let mats: MaterialsView = serde_json::from_value(req["materials"].clone()).unwrap_or_default();
    let repo = req["repo_root"].as_str().map(PathBuf::from).unwrap_or_else(|| Path::new(".").to_path_buf());
    let env = Env { repo, mats };
    let mut results = vec![];
    let mut err = std::io::stderr();
    for r in req["requests"].as_array().cloned().unwrap_or_default() {
        let id = r["id"].clone();
        let entry = r["entry"].as_str().unwrap_or("").to_string();
        let t0 = Instant::now();
        // a panic is a Rust defect of that request: recorded as its outcome (never a Python class), the run goes on
        let out = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| dispatch(&env, &entry, &r["args"])));
        let el = t0.elapsed().as_secs_f64();
        let _ = writeln!(err, "{}", json!({"id": id, "entry": entry, "elapsed_s": el}));
        results.push(match out {
            Ok(Ok(v)) => json!({"id": id, "entry": entry, "outcome": "OK", "value": v}),
            Ok(Err(e)) => json!({"id": id, "entry": entry, "outcome": "ERROR", "error_class": e.class.name(), "error_message": e.message}),
            Err(p) => {
                let msg = p
                    .downcast_ref::<&str>()
                    .map(|x| x.to_string())
                    .or_else(|| p.downcast_ref::<String>().cloned())
                    .unwrap_or_default();
                json!({"id": id, "entry": entry, "outcome": "ERROR", "error_class": "RUST_PANIC", "error_message": msg})
            }
        });
    }
    let out = json!({"results": results});
    let stdout = std::io::stdout();
    let mut h = stdout.lock();
    let _ = serde_json::to_writer(&mut h, &out);
    let _ = h.write_all(b"\n");
}
