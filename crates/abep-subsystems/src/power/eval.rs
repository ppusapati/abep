//! JSON call interface of the SC-WP-05 parity harnesses (`examples/power_eval.rs`): one call
//! `{"fn": name, "args": {...}}` in, one outcome `{"outcome": "RETURNED", "value": v}` or
//! `{"outcome": "RAISED", "class": c, "message": m}` out, with the argument encodings registered in the three
//! SC-WP-05 contracts. A call outside those encodings is answered with class `HarnessError` (never a value).

use super::allocation::{allocation_checks, icp_power_allocation_check};
use super::cplx::C;
use super::ledger::{ledger, Ledger, LedgerArgs};
use super::magnet::{self as mg, MaterialArg, SegmentElem, SegmentsArg};
use super::objective::{bus_power_official, bus_power_supplied};
use super::official::{official_ledger, MassPowerA9V5};
use super::rf_match as rf;
use super::rf_planes::rf_power_planes;
use super::sampling::p_bus_1ms_max;
use super::sequence::check_startup_sequence;
use super::slots::{installed_slots, BOUNDARY_VERSION};
use super::{PowerError, PowerResult};
use abep_types::pyjson::{Dict, Value};
use std::path::Path;

fn harness(m: impl Into<String>) -> PowerError {
    PowerError::new("HarnessError", m)
}

fn arg<'a>(args: &'a Dict, k: &str) -> &'a Value {
    args.get(k).unwrap_or(&Value::Null)
}

fn ledger_args(a: &Dict) -> LedgerArgs {
    LedgerArgs {
        config: arg(a, "config").clone(),
        loads: arg(a, "loads").clone(),
        efficiencies: arg(a, "efficiencies").clone(),
        front_end: arg(a, "front_end").clone(),
        variant: a.get("variant").cloned().unwrap_or(Value::List(vec![])),
        label: a.get("label").cloned().unwrap_or_else(|| Value::str("")),
        power_basis: arg(a, "power_basis").clone(),
        gate_measurement: arg(a, "gate_measurement").clone(),
    }
}

/// A ledger reference: `{"call": ledger args}` (built here) or `{"raw": v}` (passed unchanged).
enum LedgerRef {
    Built(Box<Ledger>),
    Raw(Value),
}

fn ledger_ref(v: &Value) -> PowerResult<LedgerRef> {
    let d = v.as_dict().ok_or_else(|| harness("ledger reference must be {'call'} or {'raw'}"))?;
    if let Some(Value::Dict(c)) = d.get("call") {
        return Ok(LedgerRef::Built(Box::new(ledger(&ledger_args(c))?)));
    }
    d.get("raw").cloned().map(LedgerRef::Raw).ok_or_else(|| harness("ledger reference must be {'call'} or {'raw'}"))
}

fn ledger_value(r: &LedgerRef) -> Value {
    match r {
        LedgerRef::Built(l) => l.to_value(),
        LedgerRef::Raw(v) => v.clone(),
    }
}

/// The allocation checks' own input refusals (`not isinstance(led, Mapping) or boundary_version != v2`, and the ICP
/// configuration check) on a raw value; a raw value that passes them is outside the harness domain.
fn raw_allocation_refusal(fname: &str, v: &Value, icp: bool) -> PowerError {
    let d = match v {
        Value::Dict(d) if d.get("boundary_version").and_then(Value::as_str) == Some(BOUNDARY_VERSION) => d,
        _ => return PowerError::boundary(format!("{fname} needs a {BOUNDARY_VERSION} ledger")),
    };
    if icp && d.get("configuration").and_then(Value::as_str) != Some("hall_icp_neutralizer") {
        return PowerError::boundary("icp_power_allocation_check applies to hall_icp_neutralizer ledgers only");
    }
    harness("raw ledger value outside the registered domain")
}

fn bus_boundary_call(fname: &str, a: &Dict, mp: &MassPowerA9V5) -> PowerResult<Value> {
    match fname {
        "installed_slots" => {
            let s = installed_slots(arg(a, "config"), a.get("variant").unwrap_or(&Value::List(vec![])))?;
            Ok(Value::List(s.iter().map(|s| Value::str(s.name())).collect()))
        }
        "ledger" => Ok(ledger(&ledger_args(a))?.to_value()),
        "p_bus_1ms_max" => Ok(p_bus_1ms_max(
            arg(a, "samples_W"),
            arg(a, "sample_rate_Sa_s"),
            arg(a, "bandwidth_Hz"),
            arg(a, "anti_alias_documented"),
            arg(a, "synchronized"),
        )?
        .to_value()),
        "rf_power_planes" => Ok(rf_power_planes(
            arg(a, "P_dc_in_W"),
            arg(a, "P_forward_W"),
            arg(a, "P_reflected_W"),
            arg(a, "P_delivered_W"),
            arg(a, "u_W"),
        )?
        .to_value()),
        "allocation_checks" | "icp_power_allocation_check" => {
            let icp = fname == "icp_power_allocation_check";
            match ledger_ref(arg(a, "ledger"))? {
                LedgerRef::Built(l) => {
                    if icp {
                        icp_power_allocation_check(&l)
                    } else {
                        allocation_checks(&l)
                    }
                }
                LedgerRef::Raw(v) => Err(raw_allocation_refusal(fname, &v, icp)),
            }
        }
        "check_startup_sequence" => {
            let r = check_startup_sequence(
                arg(a, "config"),
                arg(a, "steps"),
                arg(a, "front_end"),
                a.get("variant").unwrap_or(&Value::List(vec![])),
            )?;
            let mut d = Dict::new();
            d.insert("boundary_version", Value::str(BOUNDARY_VERSION));
            d.insert("configuration", arg(a, "config").clone());
            d.insert("variant", Value::List(r.variant.clone()));
            d.insert("sequence_status", Value::str(r.sequence_status.as_str()));
            d.insert("violations", Value::List(r.violations.clone()));
            d.insert("not_evaluable", Value::List(r.not_evaluable.clone()));
            d.insert("dependent_rises", Value::List(r.dependent_rises.clone()));
            d.insert("steady_allocation_checks", allocation_checks(r.steady())?);
            d.insert("steady_icp_power_allocation", icp_power_allocation_check(r.steady())?);
            d.insert("steps", r.steps_value());
            Ok(Value::Dict(d))
        }
        "official_ledger" => {
            let config = arg(a, "config").as_str().ok_or_else(|| harness("config must be a string"))?;
            let comp = match arg(a, "compressor_P_W") {
                Value::Null => None,
                v => Some(v.to_f64().map_err(PowerError::from)?),
            };
            let src = arg(a, "compressor_source").as_str().unwrap_or("");
            Ok(official_ledger(mp, config, comp, src)?.to_value())
        }
        "bus_power" => {
            let config = arg(a, "config").as_str().ok_or_else(|| harness("config must be a string"))?;
            match arg(a, "supplied") {
                Value::Null => {
                    let comp = match arg(a, "compressor_P_W") {
                        Value::Null => None,
                        v => Some(v.to_f64().map_err(PowerError::from)?),
                    };
                    bus_power_official(mp, config, comp)
                }
                Value::Dict(s) => {
                    let mut sup = Dict::new();
                    for (k, v) in s.iter() {
                        let val = match k.as_str() {
                            "steady" => ledger_value(&ledger_ref(v)?),
                            "startup" => match v.as_dict() {
                                Some(d) if d.contains_key("list") => Value::List(
                                    d.get("list")
                                        .and_then(Value::as_list)
                                        .unwrap_or(&[])
                                        .iter()
                                        .map(|x| ledger_ref(x).map(|r| ledger_value(&r)))
                                        .collect::<PowerResult<Vec<_>>>()?,
                                ),
                                Some(d) => d.get("raw").cloned().unwrap_or(Value::Null),
                                None => return Err(harness("startup must be {'list'} or {'raw'}")),
                            },
                            _ => v.clone(),
                        };
                        sup.insert(k.clone(), val);
                    }
                    bus_power_supplied(&sup)
                }
                _ => Err(harness("supplied must be null or a record")),
            }
        }
        _ => Err(harness(format!("unknown function {fname}"))),
    }
}

fn material(v: &Value) -> PowerResult<MaterialArg> {
    let d = v.as_dict().ok_or_else(|| harness("material must be {'ref'}, {'fields'} or {'raw'}"))?;
    if d.get("ref").and_then(Value::as_str) == Some("ANNEALED_COPPER_IACS") {
        return Ok(MaterialArg::Material(mg::annealed_copper_iacs()));
    }
    if let Some(Value::Dict(f)) = d.get("fields") {
        return Ok(MaterialArg::Material(mg::ConductorMaterial::from_fields(f)?));
    }
    d.get("raw")
        .cloned()
        .map(MaterialArg::Raw)
        .ok_or_else(|| harness("material must be {'ref'}, {'fields'} or {'raw'}"))
}

fn segments(v: &Value) -> PowerResult<SegmentsArg> {
    match v {
        Value::List(items) => Ok(SegmentsArg::List(
            items
                .iter()
                .map(|e| {
                    let d = e.as_dict().ok_or_else(|| harness("segment element must be {'segment'} or {'raw'}"))?;
                    if let Some(Value::Dict(f)) = d.get("segment") {
                        return Ok(SegmentElem::Segment(mg::CoreSegment::from_fields(f)?));
                    }
                    d.get("raw").cloned().map(SegmentElem::Raw).ok_or_else(|| harness("bad segment element"))
                })
                .collect::<PowerResult<Vec<_>>>()?,
        )),
        Value::Dict(d) => d.get("raw").cloned().map(SegmentsArg::Raw).ok_or_else(|| harness("bad core_segments")),
        _ => Err(harness("bad core_segments")),
    }
}

fn magnet_call(fname: &str, a: &Dict) -> PowerResult<Value> {
    let f = |k: &str| arg(a, k);
    match fname {
        "constants" => {
            let mut d = Dict::new();
            d.insert("MU0_N_PER_A2", Value::Float(mg::MU0_N_PER_A2));
            d.insert("MAGNET_POWER_VERSION", Value::str(mg::MAGNET_POWER_VERSION));
            d.insert("ANNEALED_COPPER_IACS", mg::annealed_copper_iacs().to_value());
            Ok(Value::Dict(d))
        }
        "material" => match material(f("material"))? {
            MaterialArg::Material(m) => Ok(m.to_value()),
            MaterialArg::Raw(_) => Err(harness("material call needs a material")),
        },
        "segment" => {
            let d = f("segment")
                .as_dict()
                .and_then(|d| d.get("segment"))
                .and_then(Value::as_dict)
                .ok_or_else(|| harness("segment call needs {'segment'}"))?;
            Ok(mg::CoreSegment::from_fields(d)?.to_value())
        }
        "resistance_factor" => Ok(Value::Float(mg::resistance_factor(&material(f("material"))?, f("T_C"))?)),
        "wire_resistance_ohm" => {
            let m = material(f("material"))?;
            Ok(Value::Float(mg::wire_resistance_ohm(f("length_m"), f("area_m2"), &m, f("T_C"))?))
        }
        "awg_diameter_m" => Ok(Value::Float(mg::awg_diameter_m(f("gauge"))?)),
        "ampere_turns" => {
            let s = segments(f("core_segments"))?;
            Ok(mg::ampere_turns(f("B_gap_T"), f("gap_length_m"), f("gap_area_m2"), &s, f("leakage_factor"))?.1)
        }
        "coil_power_continuous_W" => {
            let m = material(f("material"))?;
            Ok(Value::Float(mg::coil_power_continuous_w(
                f("NI_A"),
                f("window_area_m2"),
                f("fill_factor"),
                f("mean_turn_length_m"),
                &m,
                f("T_C"),
            )?))
        }
        "coil_design" => {
            let m = material(f("material"))?;
            mg::coil_design(
                f("NI_A"),
                f("window_area_m2"),
                f("fill_factor"),
                f("mean_turn_length_m"),
                f("wire_diameter_m"),
                &m,
                f("T_C"),
            )
        }
        "electromagnet" => {
            let s = segments(f("core_segments"))?;
            let m = material(f("material"))?;
            mg::electromagnet(
                f("B_gap_T"),
                f("gap_length_m"),
                f("gap_area_m2"),
                &s,
                f("leakage_factor"),
                f("window_area_m2"),
                f("fill_factor"),
                f("mean_turn_length_m"),
                f("wire_diameter_m"),
                &m,
                f("T_C"),
            )
        }
        "remanence_at_T" => {
            Ok(Value::Float(mg::remanence_at_t(f("B_r_ref_T"), f("alpha_Br_per_K"), f("T_ref_C"), f("T_C"))?))
        }
        "permanent_magnet" => {
            let s = segments(f("core_segments"))?;
            mg::permanent_magnet(
                f("B_gap_T"),
                f("gap_length_m"),
                f("gap_area_m2"),
                &s,
                f("leakage_factor"),
                f("magnet_area_m2"),
                f("B_r_T"),
                f("mu_rec"),
                f("H_knee_A_per_m"),
                f("magnet_density_kg_m3"),
            )
        }
        _ => Err(harness(format!("unknown magnet function {fname}"))),
    }
}

/// A converted complex argument: [re, im] -> complex(re, im); a number -> complex(number) where the reference
/// calls complex(), refused otherwise.
fn cnum(v: &Value, allow_real: bool) -> PowerResult<C> {
    match v {
        Value::List(l) if l.len() == 2 => Ok(C::new(l[0].to_f64()?, l[1].to_f64()?)),
        Value::Int(_) | Value::Float(_) if allow_real => Ok(C::real(v.to_f64()?)),
        _ => Err(harness("complex argument must be [re, im]")),
    }
}

fn abcd(v: &Value) -> PowerResult<rf::Abcd> {
    let l = v.as_list().filter(|l| l.len() == 4).ok_or_else(|| harness("ABCD must be four [re, im]"))?;
    Ok([cnum(&l[0], false)?, cnum(&l[1], false)?, cnum(&l[2], false)?, cnum(&l[3], false)?])
}

fn real_arg(v: &Value) -> PowerResult<f64> {
    match v {
        Value::Int(_) | Value::Float(_) => Ok(v.to_f64()?),
        _ => Err(harness("real argument expected")),
    }
}

fn abcd_value(m: rf::Abcd) -> Value {
    Value::List(m.iter().map(|z| rf::cval(*z)).collect())
}

fn rf_call(fname: &str, a: &Dict) -> PowerResult<Value> {
    let f = |k: &str| arg(a, k);
    let fl = |x: f64| Value::Float(x);
    match fname {
        "parse_touchstone" => rf::parse_touchstone(
            f("text"),
            f("n_ports"),
            a.get("allow_spec_defaults").unwrap_or(&Value::Bool(false)),
            f("source"),
        ),
        "sol_error_terms" => rf::sol_error_terms(f("standards")),
        "sol_correct" => {
            let g = cnum(f("gamma_measured"), true)?;
            let t = f("terms").as_dict().ok_or_else(|| harness("terms must be a record"))?;
            let term = |k: &str| {
                t.get(k).ok_or_else(|| PowerError::new("KeyError", format!("'{k}'"))).and_then(|v| cnum(v, false))
            };
            let (e00, e11, e10) = (term("e00")?, term("e11")?, term("e10e01")?);
            Ok(rf::cval(rf::sol_correct(g, e00, e11, e10)?))
        }
        "ladder_abcd" => Ok(abcd_value(rf::ladder_abcd(f("elements"))?)),
        "dissipated_fraction_matched" => {
            Ok(fl(rf::dissipated_fraction_matched(cnum(f("s11"), true)?, cnum(f("s21"), true)?)?))
        }
        "vi_power_and_impedance" => {
            rf::vi_power_and_impedance(f("V_raw"), f("I_raw"), f("k_V"), f("k_I"), f("amplitude_convention"))
        }
        "cx" => {
            let what = f("what").as_str().ok_or_else(|| harness("what must be a string"))?;
            Ok(rf::cval(rf::cx(f("v"), what)?))
        }
        "gamma_from_z" => Ok(rf::cval(rf::gamma_from_z(cnum(f("z"), false)?, real_arg(f("z0"))?)?)),
        "z_from_gamma" => Ok(rf::cval(rf::z_from_gamma(cnum(f("g"), false)?, real_arg(f("z0"))?)?)),
        "vswr" => Ok(fl(rf::vswr(real_arg(f("gmag"))?)?)),
        "gamma_mag_from_powers" => Ok(fl(rf::gamma_mag_from_powers(real_arg(f("p_fwd"))?, real_arg(f("p_ref"))?)?)),
        "s_to_abcd" => Ok(abcd_value(rf::s_to_abcd(
            cnum(f("s11"), false)?,
            cnum(f("s12"), false)?,
            cnum(f("s21"), false)?,
            cnum(f("s22"), false)?,
            real_arg(f("z0"))?,
        )?)),
        "abcd_to_s" => Ok(abcd_value(rf::abcd_to_s(abcd(f("abcd"))?, real_arg(f("z0"))?)?)),
        "cascade" => Ok(abcd_value(rf::cascade(abcd(f("m1"))?, abcd(f("m2"))?))),
        "z_in" => Ok(rf::cval(rf::z_in(abcd(f("abcd"))?, cnum(f("z_load"), false)?)?)),
        "deembed_load" => Ok(rf::cval(rf::deembed_load(abcd(f("abcd"))?, cnum(f("z_input"), false)?)?)),
        "transfer_efficiency" => Ok(fl(rf::transfer_efficiency(abcd(f("abcd"))?, cnum(f("z_load"), false)?)?)),
        "correct_reflection" => Ok(rf::cval(rf::correct_reflection(
            cnum(f("m_raw"), false)?,
            cnum(f("e00"), false)?,
            cnum(f("e11"), false)?,
            cnum(f("e10e01"), false)?,
        )?)),
        "fixture_to_plane" => {
            let (v, i) = rf::fixture_to_plane(abcd(f("abcd_fix"))?, cnum(f("v_p"), false)?, cnum(f("i_p"), false)?)?;
            Ok(Value::List(vec![rf::cval(v), rf::cval(i)]))
        }
        "line_peak_stress" => {
            let (v, i) = rf::line_peak_stress(real_arg(f("p_fwd"))?, real_arg(f("gmag"))?, real_arg(f("z0"))?)?;
            Ok(Value::List(vec![fl(v), fl(i)]))
        }
        "p_bus_from_generator_input" => Err(rf::p_bus_from_generator_input(f("record"))),
        _ => Err(harness(format!("unknown RF function {fname}"))),
    }
}

/// Evaluate one call against the repository at `repo_root` (the mass/power record is loaded once by the caller).
pub fn eval_call(call: &Value, mp: &MassPowerA9V5) -> Value {
    let out = (|| -> PowerResult<Value> {
        let c = call.as_dict().ok_or_else(|| harness("call must be a record"))?;
        let name = c.get("fn").and_then(Value::as_str).ok_or_else(|| harness("call needs 'fn'"))?;
        let empty = Dict::new();
        let a = c.get("args").and_then(Value::as_dict).unwrap_or(&empty);
        if let Some(n) = name.strip_prefix("magnet.") {
            magnet_call(n, a)
        } else if let Some(n) = name.strip_prefix("rf.") {
            rf_call(n, a)
        } else {
            bus_boundary_call(name, a, mp)
        }
    })();
    let mut d = Dict::new();
    match out {
        Ok(v) => {
            d.insert("outcome", Value::str("RETURNED"));
            d.insert("value", v);
        }
        Err(e) => {
            d.insert("outcome", Value::str("RAISED"));
            d.insert("class", Value::str(e.class));
            d.insert("message", Value::str(e.message));
        }
    }
    Value::Dict(d)
}

/// Load the pinned mass/power record for a batch of calls.
pub fn load_context(repo_root: &Path) -> PowerResult<MassPowerA9V5> {
    MassPowerA9V5::load(repo_root)
}
