//! Case construction of the P7 thermal closure: the preregistered DBF-1 network (prereg `nodes`, `surfaces`,
//! `enclosures`, `links`, `materials`, `optics`) plus one case's environment, boundary temperatures, design-lever values
//! and loads, as an `abep_np_thermal_case_v1` document for NP-THERMAL-CATHODELESS 2.0.0 (PARAMETRIC).

use super::env::{self, EnvType};
use super::loads::{IcpKeys, Loads};
use super::{num, s, ClosureError, Prereg};
use abep_subsystems::thermal::case::*;
use abep_subsystems::thermal::governance::{KEY_TABLE_V2_SHA256, PRODUCER_LOCK_SHA256};
use abep_subsystems::thermal::vocab;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

pub const HALL_PRODUCER: &str = "P7-PARAMETRIC-HALL-LOADS";
const NOT_VALIDATED: &str = "NOT_VALIDATED";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Beta {
    Star,
    Zero,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Solver {
    Steady,
    OrbitAverage,
    Periodic,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Flux {
    Hot,
    Cold,
}

/// One case to build: environment, boundaries, design levers, network overrides and loads.
#[derive(Debug, Clone)]
pub struct Spec {
    pub id: String,
    pub alt_km: f64,
    pub beta: Beta,
    pub solver: Solver,
    pub flux: Flux,
    pub t_sc_k: f64,
    pub supply_mode: String,
    pub a_rh: f64,
    pub g_rh: f64,
    /// link id -> field -> value (prereg `sensitivities.overrides.*.links`).
    pub link_overrides: BTreeMap<String, BTreeMap<String, Value>>,
    pub loads: Loads,
    pub t_init: BTreeMap<String, f64>,
    /// Thermal-control dissipation on a node [W] (heater sizing).
    pub heater: Option<(String, f64)>,
}

struct B<'a> {
    p: &'a Prereg,
    c: ThermalCase,
}

impl B<'_> {
    #[allow(clippy::too_many_arguments)]
    fn rec(&mut self, id: &str, q: &str, value: Value, source: &str, ec: &str, unc: Value, range: Option<(f64, f64)>) {
        let (units, _) = vocab::quantity(q).expect("registered quantity");
        let optical = q == "emittance_IR" || q == "absorptance_solar";
        self.c.records.push(InputRecord {
            id: Some(id.into()),
            quantity: Some(q.into()),
            value: Some(value),
            units: Some(units.into()),
            source: Some(source.into()),
            evidence_class: Some(ec.into()),
            uncertainty: Some(unc),
            applicability_domain: Some(ApplicabilityDomain {
                t_min_k: range.map(|r| r.0),
                t_max_k: range.map(|r| r.1),
                gray_in_band: optical.then_some(true),
                text: Some(
                    "P7 thermal-closure PARAMETRIC case (docs/closure/thermal/thermal_cases_prereg_v1.json)".into(),
                ),
            }),
            validation_status: Some(NOT_VALIDATED.into()),
            status: Some("REGISTERED".into()),
        });
    }

    fn scalar(&mut self, id: &str, q: &str, v: f64, source: &str, ec: &str) {
        self.rec(id, q, json!(v), source, ec, json!("see the preregistration"), None);
    }

    fn ranged(&mut self, id: &str, q: &str, v: f64, source: &str, ec: &str) {
        let r = self.p.range;
        self.rec(id, q, json!(v), source, ec, json!("see the preregistration"), Some(r));
    }

    fn tvalue(&mut self, id: &str, q: &str, tv: &Tv, source: &str) {
        let v = match tv {
            Tv::C(x) => json!(x),
            Tv::Z(t, v) => json!({"breakpoints_s": t, "values": v}),
        };
        self.rec(id, q, v, source, "model-derived", json!("see the preregistration"), None);
    }
}

pub enum Tv {
    C(f64),
    Z(Vec<f64>, Vec<f64>),
}

fn vr(v: f64, units: &str, source: &str) -> ValueRecord {
    ValueRecord {
        value: Some(json!(v)),
        units: Some(units.into()),
        status: Some("EVALUATED".into()),
        evidence_class: Some("assumed".into()),
        source: Some(source.into()),
        uncertainty: Some(json!(
            "registered engineering assumption; see docs/closure/thermal/thermal_load_inputs_v1.json"
        )),
        applicability_domain: Some(json!("P7 thermal-closure PARAMETRIC case")),
        validation_status: Some(NOT_VALIDATED.into()),
        hall_map: None,
    }
}

fn link_ep(x: &str) -> Endpoint {
    match x {
        "B_SC" => Endpoint { node: None, boundary: Some("B_SC".into()), temperature_record_id: Some("T_SC".into()) },
        "B_PPU_RF" => {
            Endpoint { node: None, boundary: Some("B_PPU_RF".into()), temperature_record_id: Some("T_PPU".into()) }
        }
        n => Endpoint { node: Some(n.into()), boundary: None, temperature_record_id: None },
    }
}

/// Every interface key a registered node may receive (v1 Hall keys and v2 ICP keys), declared on the node.
fn receives(id: &str) -> Vec<String> {
    let mut out: BTreeSet<String> = BTreeSet::new();
    if let Some(n) = vocab::registered_node(id) {
        for k in n.receives {
            if k.starts_with("Q_hall_") {
                out.insert(k.to_string());
            }
        }
    }
    for (n, ks) in vocab::ICP_V2_RECEIVES.iter() {
        if *n == id {
            out.extend(ks.iter().map(|k| k.to_string()));
        }
    }
    out.into_iter().collect()
}

/// Build the case document of `spec`.
pub fn build(p: &Prereg, spec: &Spec) -> Result<ThermalCase, ClosureError> {
    let solver_mode = match spec.solver {
        Solver::Steady => "STEADY",
        Solver::OrbitAverage => "ORBIT_AVERAGE_STEADY",
        Solver::Periodic => "ORBIT_TRANSIENT_PERIODIC",
    };
    let period = env::period(spec.alt_km);
    let (orbit_period_s, dt_s) = match spec.solver {
        Solver::Steady => (None, None),
        Solver::OrbitAverage => (Some(period), None),
        Solver::Periodic => (Some(period), Some(period / 144.0)),
    };
    let m = &p.model;
    let c = ThermalCase {
        schema: CASE_SCHEMA.into(),
        case_id: spec.id.clone(),
        case_class: s(m, "case_class")?,
        topology_scope: s(m, "topology_scope")?,
        configuration: s(m, "configuration")?,
        supply_mode: spec.supply_mode.clone(),
        design_state_id: None,
        installed_variants: vec![],
        match_colocated: Some(m["match_colocated"].as_bool().unwrap_or(false)),
        magnet_load_mode: Some(s(m, "magnet_load_mode")?),
        anode_material_candidate_id: Some(s(m, "anode_material_candidate_id")?),
        collector_material_candidate_id: Some(s(m, "collector_material_candidate_id")?),
        bench_vacuum: None,
        solver: SolverSpec {
            mode: solver_mode.into(),
            t_init_k: spec.t_init.clone(),
            t_start_s: None,
            t_end_s: None,
            dt_s,
            orbit_period_s,
        },
        records: vec![],
        nodes: vec![],
        links: vec![],
        enclosures: vec![],
        boundary_fluxes: vec![],
        environment: vec![],
        thermal_control: vec![],
        coil_resistance_relations: BTreeMap::new(),
        interfaces: Interfaces::default(),
        partitions: BTreeMap::new(),
        model_version: Some(vocab::MODEL_VERSION_V2.into()),
    };
    let mut b = B { p, c };
    let range = p.range;

    // Materials and optics (temperature-dependent property records).
    for (id, mrec) in p.materials.iter().chain(p.optics.iter()) {
        let r = (num(mrec, "T_min_K")?, num(mrec, "T_max_K")?);
        let src = format!(
            "{}; validation {}",
            s(mrec, "source")?,
            mrec["validation_status"].as_str().unwrap_or(NOT_VALIDATED)
        );
        b.rec(
            id,
            &s(mrec, "quantity")?,
            mrec["form"].clone(),
            &src,
            &s(mrec, "evidence_class")?,
            mrec["uncertainty"].clone(),
            Some(r),
        );
    }
    // Nodes.
    let surfaces = p.surfaces.clone();
    for n in &p.nodes {
        let id = s(n, "id")?;
        let mut parts = Vec::new();
        for (k, part) in n["parts"].as_array().cloned().unwrap_or_default().iter().enumerate() {
            let mass = match part.get("mass_kg").and_then(Value::as_f64) {
                Some(x) => x,
                None => num(part, "mass_kg_per_m2_of_A_RH")? * spec.a_rh,
            };
            let mid = format!("M.{id}.{k}");
            b.scalar(&mid, "mass", mass, &s(part, "mass_source")?, "assumed");
            parts.push(Part {
                part_id: s(part, "part_id")?,
                material_record_id: s(part, "material_record_id")?,
                mass_kg_record_id: mid,
            });
        }
        let bi = &n["biot"];
        let (vol, area) = match bi.get("volume_m3").and_then(Value::as_f64) {
            Some(v) => (v, num(bi, "conduction_area_m2")?),
            None => (
                num(bi, "volume_m3_per_m2_of_A_RH")? * spec.a_rh,
                num(bi, "conduction_area_m2_per_m2_of_A_RH")? * spec.a_rh,
            ),
        };
        b.scalar(&format!("BV.{id}"), "volume", vol, "prereg nodes[].biot", "assumed");
        b.scalar(&format!("BA.{id}"), "area", area, "prereg nodes[].biot (exchange surface area)", "assumed");
        let mut node_surfaces = Vec::new();
        for sf in surfaces.iter().filter(|x| x["node"].as_str() == Some(id.as_str())) {
            let sid = s(sf, "id")?;
            let a = match sf["area_m2"].as_f64() {
                Some(a) => a,
                None => spec.a_rh,
            };
            b.scalar(&format!("A.{sid}"), "area", a, "prereg surfaces[]", "model-derived");
            node_surfaces.push(Surface {
                surface_id: sid.clone(),
                area_record_id: format!("A.{sid}"),
                eps_ir_record_id: s(sf, "eps_record_id")?,
                alpha_solar_record_id: sf["alpha_record_id"].as_str().map(String::from),
                enclosure_id: s(sf, "enclosure")?,
                external: sf["external"].as_bool().unwrap_or(false),
            });
        }
        let reg = vocab::registered_node(&id).ok_or_else(|| ClosureError(format!("node {id} is not registered")))?;
        b.c.nodes.push(NodeRecord {
            id: id.clone(),
            group: s(n, "group")?,
            represents: s(n, "represents")?,
            presence: s(n, "presence")?,
            role: "REGISTERED".into(),
            refines: None,
            thermal_mass: "LUMPED_C_OF_T".into(),
            parts,
            surfaces: node_surfaces,
            biot_geometry: Some(BiotGeometry {
                volume_record_id: format!("BV.{id}"),
                conduction_area_record_id: format!("BA.{id}"),
                k_record_id: s(bi, "k_record_id")?,
            }),
            receives_interface_keys: receives(reg.id),
            case_classes_allowed: vec!["PARAMETRIC".into()],
        });
    }
    // Links.
    for l in &p.links {
        let id = s(l, "id")?;
        let ov = spec.link_overrides.get(&id);
        let field = |f: &str| -> Option<Value> { ov.and_then(|o| o.get(f).cloned()).or_else(|| l.get(f).cloned()) };
        let ty = s(l, "type")?;
        let src = s(l, "derivation")?;
        let ec = l["evidence_class"].as_str().unwrap_or("assumed").to_string();
        let mut rec = LinkRecord {
            id: id.clone(),
            link_type: ty.clone(),
            a: link_ep(&s(l, "a")?),
            b: link_ep(&s(l, "b")?),
            k_record_id: None,
            shape: None,
            h_c_record_id: None,
            contact_area_record_id: None,
            g_record_id: None,
        };
        match ty.as_str() {
            "LUMPED_G" => {
                let g = if id == "L_BP_RH" {
                    spec.g_rh
                } else {
                    field("G_W_K").and_then(|v| v.as_f64()).ok_or_else(|| ClosureError(format!("{id}: G_W_K")))?
                };
                b.ranged(&format!("G.{id}"), "conductance", g, &src, &ec);
                rec.g_record_id = Some(format!("G.{id}"));
            }
            "CONTACT" => {
                let h =
                    field("h_c_W_m2K").and_then(|v| v.as_f64()).ok_or_else(|| ClosureError(format!("{id}: h_c")))?;
                b.ranged(&format!("HC.{id}"), "contact_conductance_coefficient", h, &src, &ec);
                b.scalar(&format!("AC.{id}"), "area", num(l, "A_c_m2")?, &src, &ec);
                rec.h_c_record_id = Some(format!("HC.{id}"));
                rec.contact_area_record_id = Some(format!("AC.{id}"));
            }
            "CONDUCTION" => {
                let k = field("k_record_id")
                    .and_then(|v| v.as_str().map(String::from))
                    .ok_or_else(|| ClosureError(format!("{id}: k")))?;
                let shape = &l["shape"];
                let len = ov.and_then(|o| o.get("length_m")).and_then(Value::as_f64).unwrap_or(num(shape, "length_m")?);
                b.scalar(&format!("SA.{id}"), "area", num(shape, "area_m2")?, &src, &ec);
                b.scalar(&format!("SL.{id}"), "length", len, &src, &ec);
                rec.k_record_id = Some(k);
                rec.shape = Some(ShapeSpec {
                    kind: "SLAB".into(),
                    area_record_id: Some(format!("SA.{id}")),
                    length_record_id: Some(format!("SL.{id}")),
                    r_outer_record_id: None,
                    r_inner_record_id: None,
                    s_record_id: None,
                });
            }
            other => return Err(ClosureError(format!("{id}: link type {other}"))),
        }
        b.c.links.push(rec);
    }
    b.scalar(
        "T_SC",
        "temperature",
        spec.t_sc_k,
        "SCI-A reference interface temperature (REFERENCE_PENDING_ICD)",
        "assumed",
    );
    b.scalar(
        "T_PPU",
        "temperature",
        num(&p.raw["boundary_temperatures"]["T_PPU_K"], "value")?,
        "PPU / RF generator baseplate design allowable",
        "assumed",
    );
    b.scalar("T_SPACE", "temperature", 0.0, "deep-space sink 0 K (cosmic background neglected, H2-5)", "assumed");
    // Enclosures.
    for e in &p.enclosures {
        let id = s(e, "id")?;
        b.rec(
            &format!("VF.{id}"),
            "view_factor_matrix",
            json!({"view_factors": e["view_factors"].clone()}),
            &s(e, "note")?,
            "model-derived",
            json!("see the preregistration"),
            None,
        );
        let sinks = e["sinks"]
            .as_array()
            .cloned()
            .unwrap_or_default()
            .iter()
            .map(|x| SinkMember {
                surface_id: x["surface_id"].as_str().unwrap_or("").into(),
                kind: x["kind"].as_str().unwrap_or("").into(),
                temperature_record_id: "T_SPACE".into(),
            })
            .collect();
        b.c.enclosures.push(EnclosureRecord {
            id: id.clone(),
            view_factor_record_id: format!("VF.{id}"),
            sinks,
            host_surfaces: vec![],
        });
    }
    // Environment.
    let fl = match spec.flux {
        Flux::Hot => &p.raw["environment"]["fluxes"]["hot"],
        Flux::Cold => &p.raw["environment"]["fluxes"]["cold"],
    };
    let (s_w, alb, olr) = (num(fl, "S_W_m2")?, num(fl, "albedo")?, num(fl, "OLR_W_m2")?);
    let beta = match spec.beta {
        Beta::Star => env::beta_star(spec.alt_km),
        Beta::Zero => 0.0,
    };
    let alpha_of =
        |rid: &str| -> f64 { p.optics.get(rid).and_then(|o| o["form"]["value"].as_f64()).unwrap_or(f64::NAN) };
    let flux_src = format!(
        "{} {} ({})",
        fl["source"]["path"].as_str().unwrap_or(""),
        fl["source"]["pointer"].as_str().unwrap_or(""),
        fl["source"]["note"].as_str().unwrap_or("")
    );
    b.scalar("ENV.S", "solar_flux", s_w, &flux_src, "measured");
    b.scalar("ENV.a", "albedo", alb, &flux_src, "measured");
    b.scalar("ENV.olr", "olr_flux", olr, &flux_src, "measured");
    b.scalar(
        "ENV.rho",
        "density",
        spec.loads.rho_kg_m3,
        "max design-state density at the case altitude (design states v2)",
        "model-derived",
    );
    b.scalar("ENV.V", "velocity", env::speed(spec.alt_km), "circular orbital speed", "model-derived");
    b.scalar("ENV.alphaE", "energy_accommodation", 1.0, "bound (aero term inactive: A_ram = 0)", "assumed");
    b.scalar("ENV.Aram0", "projected_area", 0.0, "wake-facing: A_ram = 0 (prereg environment.attitude)", "assumed");
    for sf in &surfaces {
        let Some(t) = sf["env_type"].as_str().and_then(EnvType::parse) else { continue };
        let sid = s(sf, "id")?;
        let fe = p.earth_factor(t, spec.alt_km);
        let (fsun, nu, falb) = match spec.solver {
            Solver::Steady => {
                let alpha = alpha_of(sf["alpha_record_id"].as_str().unwrap_or(""));
                let eps = alpha_of(sf["eps_record_id"].as_str().unwrap_or(""));
                let (_, fs, nu, fa, _) = env::steady_max(t, fe, spec.alt_km, beta, alpha, eps, s_w, alb, olr);
                (Tv::C(fs), Tv::C(nu), Tv::C(fa))
            }
            _ => {
                let (bp, v) = env::periodic_series(t, fe, spec.alt_km, beta);
                (
                    Tv::Z(bp.clone(), v.iter().map(|x| x.0).collect()),
                    Tv::Z(bp.clone(), v.iter().map(|x| x.1).collect()),
                    Tv::Z(bp, v.iter().map(|x| x.2).collect()),
                )
            }
        };
        let vsrc = "prereg environment.view_factor_method / steady_hot_rule / periodic_rule";
        b.tvalue(&format!("ENV.{sid}.Fsun"), "view_factor_env", &fsun, vsrc);
        b.tvalue(&format!("ENV.{sid}.nu"), "illumination", &nu, vsrc);
        b.tvalue(&format!("ENV.{sid}.Falb"), "view_factor_env", &falb, vsrc);
        b.tvalue(&format!("ENV.{sid}.Fe"), "view_factor_env", &Tv::C(fe), vsrc);
        b.c.environment.push(EnvSurface {
            surface_id: sid.clone(),
            solar_flux_record_id: "ENV.S".into(),
            f_sun_record_id: format!("ENV.{sid}.Fsun"),
            illumination_record_id: format!("ENV.{sid}.nu"),
            albedo_record_id: "ENV.a".into(),
            f_alb_record_id: format!("ENV.{sid}.Falb"),
            olr_flux_record_id: "ENV.olr".into(),
            f_earth_record_id: format!("ENV.{sid}.Fe"),
            rho_record_id: "ENV.rho".into(),
            v_rel_record_id: "ENV.V".into(),
            alpha_e_record_id: "ENV.alphaE".into(),
            a_ram_record_id: "ENV.Aram0".into(),
        });
    }
    let _ = range;
    if let Some((node, q)) = &spec.heater {
        b.scalar("Q_TC.heater", "power", *q, "heater sizing (prereg margin_rule.cold)", "assumed");
        b.c.thermal_control.push(ThermalControl { node: node.clone(), record_id: "Q_TC.heater".into() });
    }
    // Partitions.
    let l = &spec.loads;
    let part = |b: &mut B, key: &str, rid: &str, w: &BTreeMap<String, f64>, src: &str| {
        b.rec(rid, "partition", json!({ "weights": w }), src, "assumed", json!("registered RI-PART assumption"), None);
        b.c.partitions.insert(key.into(), rid.into());
    };
    let one = |k: &str| -> BTreeMap<String, f64> { [(k.to_string(), 1.0)].into() };
    part(&mut b, "Q_hall_pole_W", "PART.hall_pole", &one("H1_POLE_IN"), "EXT-MYERS2016 inner front pole");
    part(
        &mut b,
        "Q_hall_plasma_radiation_W",
        "PART.hall_rad",
        &one("EXPORT"),
        "contained in the calorimetric fractions (value 0)",
    );
    part(
        &mut b,
        "Q_hall_plume_to_icp_W",
        "PART.hall_plume",
        &l.plume_partition,
        "input file discharge.plume_partition",
    );
    part(&mut b, "Q_icp_coil_ohmic_W", "PART.tk06", &l.icp_coil_split, "input file icp.coil_ohmic_split");
    part(&mut b, "Q_icp_radiation_W", "PART.frad", &l.icp_f_rad, "input file icp.f_rad");
    part(&mut b, "Q_icp_outflow_upstream_W", "PART.fup", &l.icp_f_up, "input file icp.f_up");
    // Interfaces.
    let hsrc = "P7 load inputs (allocation / analog fractions; docs/closure/thermal/thermal_load_inputs_v1.json)";
    let mut hk: BTreeMap<String, ValueRecord> = BTreeMap::new();
    for (k, v) in [
        ("P_hall_discharge_W", l.p_d_ref_w),
        ("P_hall_jet_W", 0.0),
        ("Q_hall_anode_W", l.q_anode_w),
        ("Q_hall_wall_inner_W", l.q_wall_in_w),
        ("Q_hall_wall_outer_W", l.q_wall_out_w),
        ("Q_hall_pole_W", l.q_pole_w),
        ("Q_hall_plasma_radiation_W", 0.0),
        ("Q_hall_return_to_icp_W", l.q_return_w),
        ("Q_hall_plume_to_icp_W", l.q_plume_w),
        ("Q_hall_coil_inner_W", l.q_coil_in_w),
        ("Q_hall_coil_outer_W", l.q_coil_out_w),
        ("Q_hall_coil_trim_W", l.q_coil_trim_w),
    ] {
        hk.insert(k.into(), vr(v, "W", hsrc));
    }
    b.c.interfaces.hall = Some(InterfaceRecord {
        interface_id: vocab::HALL_INTERFACE_ID.into(),
        interface_version: vocab::INTERFACE_VERSION.into(),
        producer_id: HALL_PRODUCER.into(),
        producer_version: "1".into(),
        producer_prereg_sha256: p.sha256.clone(),
        case_id: spec.id.clone(),
        case_class: "PARAMETRIC".into(),
        supply_mode: spec.supply_mode.clone(),
        design_state_id: None,
        operating_point_id: spec.id.clone(),
        time_basis: TimeBasis { kind: "STEADY".into(), breakpoints_s: None },
        keys: hk,
        partitions: BTreeMap::new(),
        rf_powered_only: None,
    });
    let ik: &IcpKeys = &l.icp;
    let isrc =
        "P7 load inputs (Takahashi-anchored RF partition; registered engineering assumptions; not an NP-ICP output)";
    let keys: BTreeMap<String, ValueRecord> =
        ik.keys().into_iter().map(|(k, v)| (k.to_string(), vr(v, "W", isrc))).collect();
    let shares = |m: &BTreeMap<String, f64>| -> BTreeMap<String, Value> {
        m.iter().map(|(k, v)| (k.clone(), json!(v))).collect()
    };
    b.c.interfaces.icp_v2 = Some(InterfaceRecordV2 {
        interface_id: vocab::ICP_V2_INTERFACE_ID.into(),
        producer_id: vocab::ICP_PRODUCER_ID.into(),
        producer_version: "2".into(),
        producer_lock_sha256: PRODUCER_LOCK_SHA256.into(),
        key_table_sha256: KEY_TABLE_V2_SHA256.into(),
        case_id: spec.id.clone(),
        case_class: "PARAMETRIC".into(),
        supply_mode: spec.supply_mode.clone(),
        design_state_id: None,
        operating_point_id: spec.id.clone(),
        configuration: "PARAMETRIC".into(),
        scenario_member_id: format!("P7-PARAMETRIC/{}", spec.id),
        time_basis: TimeBasis { kind: "STEADY".into(), breakpoints_s: None },
        keys,
        node_shares_w: [
            ("Q_icp_plasma_wall_W".to_string(), shares(&ik.plasma_wall_shares_w)),
            ("Q_icp_bias_collector_W".to_string(), shares(&[("N_COLLECTOR".to_string(), 0.0)].into())),
        ]
        .into(),
    });
    Ok(b.c)
}
