//! CI replay of the captured Python reference outputs of PARITY-C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION-V1 (ADMITTED,
//! parity_report_v1.json): every registered vector is re-run through `abep_mission::propagation` and compared with the
//! Python output. The scoring run was bit-identical (0 ulp) on every float, so the replay requires bit equality; the
//! Python exception classes and the DIV-P-01 refusals must match. The closure families are the contract's registered
//! SYNTHETIC_TEST_DATA_NOT_EVIDENCE families.

use abep_atmos::mission_env_kernel::Spacecraft;
use abep_atmos::pyfloat::py_pow;
use abep_data::gz::gunzip;
use abep_mission::propagation::*;
use abep_provenance::{read_verified, sha256_hex, workspace_repo_root};
use abep_types::constants::{MU_EARTH, R_EARTH};
use abep_types::{AbepError, AbepResult};
use serde_json::Value;

const DIR: &str = "docs/rust_migration/contracts/C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION/reference_outputs";

fn f(v: &Value) -> f64 {
    match v {
        Value::Number(n) => n.as_f64().unwrap(),
        Value::String(s) => match s.as_str() {
            "NaN" => f64::NAN,
            "+inf" => f64::INFINITY,
            "-inf" => f64::NEG_INFINITY,
            o => panic!("{o}"),
        },
        o => panic!("{o:?}"),
    }
}

fn opt(v: &Value) -> Option<f64> {
    if v.is_null() {
        None
    } else {
        Some(f(v))
    }
}

fn sc(a: &Value) -> Spacecraft {
    let mut s = Spacecraft::default();
    if let Some(m) = a.get("sc").and_then(Value::as_object) {
        for (k, v) in m {
            let x = f(v);
            match k.as_str() {
                "mass_kg" => s.mass_kg = x,
                "array_area_m2" => s.array_area_m2 = x,
                "array_eff" => s.array_eff = x,
                "array_deg_per_yr" => s.array_deg_per_yr = x,
                "eps_eff" => s.eps_eff = x,
                "bus_housekeeping_W" => s.bus_housekeeping_W = x,
                "inc_deg" => s.inc_deg = x,
                "ltan_h" => s.ltan_h = x,
                o => panic!("unregistered field {o}"),
            }
        }
    }
    s
}

fn drag_of(rho: f64, alt: f64, cda: f64) -> f64 {
    let a = R_EARTH + alt * 1e3;
    0.5 * rho * py_pow((MU_EARTH / a).sqrt(), 2.0) * cda
}

enum Out {
    Scalar(f64),
    Prop(Propagation),
}

fn run(entry: &str, a: &Value, p_cap_default: f64) -> AbepResult<Out> {
    let g = |k: &str| f(&a[k]);
    Ok(match entry {
        "SOLAR_CONST" => Out::Scalar(SOLAR_CONST),
        "beta_angle" => Out::Scalar(beta_angle(g("inc"), g("raan"), g("sun_lon"), g("dec"))?),
        "eclipse_fraction" => Out::Scalar(eclipse_fraction(g("alt"), g("beta"))?),
        "worst_eclipse_fraction" => Out::Scalar(worst_eclipse_fraction(&sc(a), g("alt"))?),
        "array_area_for" => {
            let cap = opt(&a["cap"]).unwrap_or(p_cap_default);
            Out::Scalar(array_area_for(g("P"), &sc(a), g("alt"), g("years"), g("rho_ratio"), cap)?)
        }
        "propagate" => {
            let d = &a["drag"];
            let t = &a["thrust"];
            let (rho0, h0, hh, cda) = (f(&d["rho0"]), f(&d["h0"]), f(&d["H"]), f(&d["CdA"]));
            let fam = t["family"].as_str().unwrap().to_string();
            let p = propagate(
                &sc(a),
                g("alt0"),
                g("hours"),
                g("dt_h"),
                |alt, _| {
                    let rho = rho0 * (-(alt - h0) / hh).exp();
                    Ok(DragSample { d_n: drag_of(rho, alt, cda), rho })
                },
                |alt, _, c| {
                    Ok(match fam.as_str() {
                        "TF-CONST" => ThrustSample { t_n: f(&t["T0"]), p_bus_w: f(&t["P0"]) },
                        "TF-POWER" => {
                            let pmax = f(&t["Pmax"]);
                            let pw = if c.p_avail_w < pmax { c.p_avail_w } else { pmax };
                            ThrustSample { t_n: f(&t["k"]) * pw, p_bus_w: pw }
                        }
                        _ => ThrustSample { t_n: f(&t["f"]) * drag_of(c.rho, alt, f(&t["CdA"])), p_bus_w: f(&t["P0"]) },
                    })
                },
                opt(&a["raan0"]),
                g("epoch_day"),
            )?;
            Out::Prop(p)
        }
        o => panic!("{o}"),
    })
}

fn same(a: f64, b: f64) -> bool {
    a.to_bits() == b.to_bits() || (a == b) || (a.is_nan() && b.is_nan())
}

#[test]
fn captured_python_outputs_replay_bit_identically() {
    let root = workspace_repo_root().unwrap();
    let manifest: Value =
        serde_json::from_slice(&std::fs::read(root.join(DIR).join("MANIFEST.json")).unwrap()).unwrap();
    let gz_sha = manifest["python_outputs_v1.json.gz"].as_str().unwrap();
    let gz = read_verified(&root.join(DIR).join("python_outputs_v1.json.gz"), gz_sha).unwrap();
    assert_eq!(sha256_hex(&gz), gz_sha);
    let doc: Value = serde_json::from_slice(&gunzip(&gz, DIR).unwrap()).unwrap();
    let cap =
        abep_config::loaders::OperatingInputs::load(&abep_config::ConfigPaths::repository(&root)).unwrap().p_bus_max_w;
    let vectors = doc["vectors"].as_array().unwrap();
    let python = doc["python"].as_array().unwrap();
    assert_eq!(vectors.len(), 1222);
    let mut fails = Vec::new();
    for (v, py) in vectors.iter().zip(python) {
        let id = v["id"].as_str().unwrap();
        let rs = run(v["entry"].as_str().unwrap(), &v["args"], cap);
        let divergent = v.get("divergent").and_then(Value::as_bool).unwrap_or(false);
        match (py["outcome"].as_str().unwrap(), rs) {
            (_, Err(AbepError::OutOfDomain { message })) if divergent => {
                if !message.starts_with("DIV-P-01") {
                    fails.push(format!("{id}: {message}"));
                }
            }
            ("RAISED", Err(AbepError::OutOfDomain { message })) => {
                let class = py["class"].as_str().unwrap();
                if !message.starts_with(&format!("{class}:")) {
                    fails.push(format!("{id}: class {class} vs {message}"));
                }
            }
            ("RETURNED", Ok(Out::Scalar(x))) if !divergent => {
                if !same(f(&py["value"]), x) {
                    fails.push(format!("{id}: {} vs {x}", py["value"]));
                }
            }
            ("RETURNED", Ok(Out::Prop(p))) if !divergent => {
                let pv = &py["value"];
                let rows = pv["rows"].as_array().unwrap();
                if rows.len() != p.rows.len() {
                    fails.push(format!("{id}: n_rows"));
                    continue;
                }
                for (r, row) in rows.iter().zip(&p.rows) {
                    for (k, x) in PROPAGATION_COLUMNS.iter().zip(row.values()) {
                        if !same(f(&r[*k]), x) {
                            fails.push(format!("{id}: {k}"));
                        }
                    }
                }
                let summ =
                    [p.min_alt_km, p.mean_eclipse, p.min_power_margin_W, p.hours_power_short, p.raan_drift_deg_per_day];
                for (k, x) in PROPAGATION_SUMMARY_KEYS[1..].iter().zip(summ) {
                    if !same(f(&pv[*k]), x) {
                        fails.push(format!("{id}: {k}"));
                    }
                }
                if pv["reentered"].as_bool() != Some(p.reentered) {
                    fails.push(format!("{id}: reentered"));
                }
            }
            (o, r) => fails.push(format!("{id}: python {o} vs rust {:?}", r.is_ok())),
        }
    }
    assert!(fails.is_empty(), "{} failures: {:?}", fails.len(), &fails[..fails.len().min(10)]);
}
