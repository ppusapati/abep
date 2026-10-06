//! Parity CLI of PARITY-C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION-V1: reads `{"repo_root": ..., "calls": [...]}` as JSON
//! on stdin and writes `{"results": [...]}` on stdout. Floats travel as JSON numbers (shortest round trip) or the
//! strings "NaN", "+inf", "-inf". Each result is `{"outcome": "RETURNED", "value": ...}` or
//! `{"outcome": "RAISED", "class": <text before ':'>, "message": ...}`.
//!
//! The propagate closure families DF-EXP, TF-CONST, TF-POWER, TF-TRACK are the contract's registered synthetic families
//! (SYNTHETIC_TEST_DATA_NOT_EVIDENCE), written in the reference harness's operation order.

use abep_atmos::mission_env_kernel::Spacecraft;
use abep_atmos::pyfloat::py_pow;
use abep_mission::propagation::{
    array_area_for, beta_angle, eclipse_fraction, propagate, worst_eclipse_fraction, DragSample, ThrustSample,
    SOLAR_CONST,
};
use abep_types::constants::{MU_EARTH, R_EARTH};
use abep_types::{AbepError, AbepResult};
use serde_json::{json, Map, Value};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

fn num(v: &Value, k: &str) -> f64 {
    match v.get(k) {
        Some(Value::Number(n)) => n.as_f64().expect("number"),
        Some(Value::String(s)) => match s.as_str() {
            "NaN" => f64::NAN,
            "+inf" => f64::INFINITY,
            "-inf" => f64::NEG_INFINITY,
            other => panic!("bad float string {other}"),
        },
        other => panic!("argument {k}: {other:?}"),
    }
}

fn opt(v: &Value, k: &str) -> Option<f64> {
    match v.get(k) {
        None | Some(Value::Null) => None,
        Some(_) => Some(num(v, k)),
    }
}

fn jf(x: f64) -> Value {
    if x.is_nan() {
        json!("NaN")
    } else if x == f64::INFINITY {
        json!("+inf")
    } else if x == f64::NEG_INFINITY {
        json!("-inf")
    } else {
        json!(x)
    }
}

fn spacecraft(v: &Value) -> Spacecraft {
    let mut sc = Spacecraft::default();
    let Some(obj) = v.get("sc").filter(|o| o.is_object()) else { return sc };
    for (k, x) in obj.as_object().expect("object") {
        let f = || num(obj, k);
        match k.as_str() {
            "mass_kg" => sc.mass_kg = f(),
            "bus_frontal_m2" => sc.bus_frontal_m2 = f(),
            "bus_cd" => sc.bus_cd = f(),
            "array_area_m2" => sc.array_area_m2 = f(),
            "array_edge_on" => sc.array_edge_on = x.as_bool().expect("bool"),
            "array_thickness_m" => sc.array_thickness_m = f(),
            "array_span_m" => sc.array_span_m = f(),
            "array_eff" => sc.array_eff = f(),
            "array_deg_per_yr" => sc.array_deg_per_yr = f(),
            "array_angle_from_thrust_axis_deg" => sc.array_angle_from_thrust_axis_deg = f(),
            "array_distance_m" => sc.array_distance_m = f(),
            "pointing_sigma_deg" => sc.pointing_sigma_deg = f(),
            "eps_eff" => sc.eps_eff = f(),
            "bus_housekeeping_W" => sc.bus_housekeeping_W = f(),
            "inc_deg" => sc.inc_deg = f(),
            "ltan_h" => sc.ltan_h = f(),
            "intake_cd_ref" => sc.intake_cd_ref = f(),
            other => panic!("unknown Spacecraft field {other}"),
        }
    }
    sc
}

/// DF-EXP / TF-TRACK drag: 0.5 * rho * V ** 2 * CdA with V = sqrt(MU_EARTH / a), a = R_EARTH + alt * 1e3.
fn drag_of(rho: f64, alt: f64, cda: f64) -> f64 {
    let a = R_EARTH + alt * 1e3;
    let v = (MU_EARTH / a).sqrt();
    0.5 * rho * py_pow(v, 2.0) * cda
}

fn call(repo: &Path, c: &Value) -> AbepResult<Value> {
    let a = c.get("args").cloned().unwrap_or(Value::Null);
    match c.get("entry").and_then(Value::as_str).expect("entry") {
        "SOLAR_CONST" => Ok(jf(SOLAR_CONST)),
        "beta_angle" => beta_angle(num(&a, "inc"), num(&a, "raan"), num(&a, "sun_lon"), num(&a, "dec")).map(jf),
        "eclipse_fraction" => eclipse_fraction(num(&a, "alt"), num(&a, "beta")).map(jf),
        "worst_eclipse_fraction" => worst_eclipse_fraction(&spacecraft(&a), num(&a, "alt")).map(jf),
        "array_area_for" => {
            let cap = match opt(&a, "cap") {
                Some(x) => x,
                None => {
                    let paths = abep_config::ConfigPaths::repository(repo);
                    abep_config::loaders::OperatingInputs::load(&paths).map_err(AbepError::from)?.p_bus_max_w
                }
            };
            array_area_for(num(&a, "P"), &spacecraft(&a), num(&a, "alt"), num(&a, "years"), num(&a, "rho_ratio"), cap)
                .map(jf)
        }
        "propagate" => {
            let d = a.get("drag").cloned().expect("drag");
            let t = a.get("thrust").cloned().expect("thrust");
            assert_eq!(d.get("family").and_then(Value::as_str), Some("DF-EXP"));
            let (rho0, h0, hh, cda) = (num(&d, "rho0"), num(&d, "h0"), num(&d, "H"), num(&d, "CdA"));
            let drag_fn = |alt: f64, _t: f64| -> AbepResult<DragSample> {
                let rho = rho0 * (-(alt - h0) / hh).exp();
                Ok(DragSample { d_n: drag_of(rho, alt, cda), rho })
            };
            let fam = t.get("family").and_then(Value::as_str).expect("family").to_string();
            let thrust_fn =
                |alt: f64, _t: f64, ctx: &abep_mission::propagation::ThrustContext| -> AbepResult<ThrustSample> {
                    Ok(match fam.as_str() {
                        "TF-CONST" => ThrustSample { t_n: num(&t, "T0"), p_bus_w: num(&t, "P0") },
                        "TF-POWER" => {
                            let pmax = num(&t, "Pmax");
                            let p = if ctx.p_avail_w < pmax { ctx.p_avail_w } else { pmax };
                            ThrustSample { t_n: num(&t, "k") * p, p_bus_w: p }
                        }
                        "TF-TRACK" => ThrustSample {
                            t_n: num(&t, "f") * drag_of(ctx.rho, alt, num(&t, "CdA")),
                            p_bus_w: num(&t, "P0"),
                        },
                        other => panic!("unknown thrust family {other}"),
                    })
                };
            let p = propagate(
                &spacecraft(&a),
                num(&a, "alt0"),
                num(&a, "hours"),
                num(&a, "dt_h"),
                drag_fn,
                thrust_fn,
                opt(&a, "raan0"),
                num(&a, "epoch_day"),
            )?;
            let rows: Vec<Value> = p
                .rows
                .iter()
                .map(|r| {
                    let mut m = Map::new();
                    for (k, v) in [
                        ("t_h", r.t_h),
                        ("alt_km", r.alt_km),
                        ("raan_deg", r.raan_deg),
                        ("beta_deg", r.beta_deg),
                        ("eclipse_frac", r.eclipse_frac),
                        ("D_mN", r.D_mN),
                        ("T_mN", r.T_mN),
                        ("P_bus_W", r.P_bus_W),
                        ("P_need_W", r.P_need_W),
                        ("P_avail_W", r.P_avail_W),
                        ("power_margin_W", r.power_margin_W),
                        ("rho", r.rho),
                    ] {
                        m.insert(k.into(), jf(v));
                    }
                    Value::Object(m)
                })
                .collect();
            Ok(json!({
                "rows": rows,
                "reentered": p.reentered,
                "min_alt_km": jf(p.min_alt_km),
                "mean_eclipse": jf(p.mean_eclipse),
                "min_power_margin_W": jf(p.min_power_margin_W),
                "hours_power_short": jf(p.hours_power_short),
                "raan_drift_deg_per_day": jf(p.raan_drift_deg_per_day),
            }))
        }
        other => panic!("unknown entry {other}"),
    }
}

fn main() {
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).expect("stdin");
    let req: Value = serde_json::from_str(&input).expect("request JSON");
    let repo = match req.get("repo_root").and_then(Value::as_str) {
        Some(s) => PathBuf::from(s),
        None => abep_provenance::workspace_repo_root().expect("repository root"),
    };
    let results: Vec<Value> = req
        .get("calls")
        .and_then(Value::as_array)
        .expect("calls")
        .iter()
        .map(|c| match call(&repo, c) {
            Ok(v) => json!({"outcome": "RETURNED", "value": v}),
            Err(e) => {
                let msg = match &e {
                    AbepError::OutOfDomain { message }
                    | AbepError::Model { message }
                    | AbepError::IncompleteEvidence { message } => message.clone(),
                    other => other.to_string(),
                };
                let class = msg.split_once(':').map(|(k, _)| k.to_string()).unwrap_or_default();
                json!({"outcome": "RAISED", "status": e.status().as_str(), "class": class, "message": msg})
            }
        })
        .collect();
    let text = serde_json::to_string(&json!({ "results": results })).expect("serializable");
    std::io::stdout().write_all(text.as_bytes()).expect("stdout");
}
