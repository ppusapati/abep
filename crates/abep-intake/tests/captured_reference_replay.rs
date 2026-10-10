//! CI replay of the captured Python reference outputs of PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1, entry point E4 (the
//! frozen intake surface; ADMITTED, parity_report_v1.json): the Rust surface must keep reproducing all 528 reference
//! evaluations within the contract tolerance (4 ulp or 1e-11 relative, NaN only where the reference is NaN), with the
//! same species set and order, after the Python reference is retired from active execution.

use abep_intake::surface::FrozenIntakeSurfaces;
use abep_provenance::{read_verified, workspace_repo_root};
use serde_json::Value;
use std::collections::BTreeMap;

const DIR: &str = "docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_TPMC_PY/reference_outputs";
const E4_SHA256: &str = "61d8c27df493e2fb8b1928f84c6fe890ad311b6cb52cdab75ed06a428ea37a66";
const MB_SHA256: &str = "e74256303c083f12018e12d72e2c2e4590e87c117e7d65d3ebc57941b9ff1f00";
const MIX: [&str; 5] = ["eta_c", "C_D", "K_back", "CR_passive", "mass_kg"];

fn num(v: &Value) -> f64 {
    match v {
        Value::String(s) if s == "NaN" => f64::NAN,
        v => v.as_f64().expect("number"),
    }
}

/// Contract ULP_BOUNDED rule: |r - p| <= 4 ulp(p) or <= 1e-11 max(1, |p|); NaN agrees only with NaN.
fn within(r: f64, p: f64) -> bool {
    if r.is_nan() || p.is_nan() {
        return r.is_nan() && p.is_nan();
    }
    let d = (r - p).abs();
    let ulp = p.abs().next_up() - p.abs();
    d <= 4.0 * ulp || d <= 1e-11 * p.abs().max(1.0)
}

#[test]
fn surface_reproduces_the_captured_reference() {
    let root = workspace_repo_root().unwrap();
    let mb: f64 = serde_json::from_slice::<Value>(
        &read_verified(&root.join(DIR).join("m_mean_build_kg.json"), MB_SHA256).unwrap(),
    )
    .map(|v| num(&v))
    .unwrap();
    let cases: Vec<Value> =
        serde_json::from_slice(&read_verified(&root.join(DIR).join("E4_evaluations.json"), E4_SHA256).unwrap())
            .unwrap();
    assert_eq!(cases.len(), 528);
    let s = FrozenIntakeSurfaces::load(&root, mb).unwrap();
    let mut failures = Vec::new();
    for c in &cases {
        let inp = &c["inputs"];
        let p: Vec<f64> = inp["point"].as_array().unwrap().iter().map(num).collect();
        let fr: BTreeMap<String, f64> =
            inp["fractions"].as_object().unwrap().iter().map(|(k, v)| (k.clone(), num(v))).collect();
        let py = &c["python"]["ok"];
        let r = s.get(inp["scattering"].as_str().unwrap()).unwrap().eval(p[0], p[1], p[2], p[3], Some(&fr)).unwrap();
        let rv = [r.eta_c, r.c_d, r.k_back, r.cr_passive, r.mass_kg];
        for (k, v) in MIX.iter().zip(rv) {
            if !within(v, num(&py[*k])) {
                failures.push(format!("{} {k}: rust {v} python {}", c["id"], py[*k]));
            }
        }
        let py_sp = py["species"].as_object().unwrap();
        let order: Vec<&str> = r.species.iter().map(|(k, _)| k.as_str()).collect();
        let py_order: Vec<&str> = py_sp.keys().map(String::as_str).collect();
        let mut sorted = order.clone();
        sorted.sort();
        // serde_json maps are key-sorted; the table order N2, O, O2 is sorted too
        assert_eq!(order, sorted);
        assert_eq!(order, py_order, "{}", c["id"]);
        for (name, e) in &r.species {
            let q = &py_sp[name];
            for (k, v) in [
                ("eta_c", e.eta_c),
                ("C_D_row", e.c_d_row),
                ("C_D_species", e.c_d_species),
                ("CR_passive", e.cr_passive),
                ("K_back", e.k_back),
                ("mass_fraction", e.mass_fraction),
                ("mole_fraction", e.mole_fraction),
                ("collected_mass_fraction", e.collected_mass_fraction),
                ("collected_mole_fraction", e.collected_mole_fraction),
            ] {
                if !within(v, num(&q[k])) {
                    failures.push(format!("{} {name}.{k}: rust {v} python {}", c["id"], q[k]));
                }
            }
        }
        assert_eq!(py["recombination"], r.recombination);
    }
    assert!(failures.is_empty(), "{} deviations, first: {:?}", failures.len(), &failures[..failures.len().min(5)]);
}
