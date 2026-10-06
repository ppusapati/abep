//! CI replay of the captured Python reference outputs of the seven SC-WP-08 materials / life contracts (v1 reports
//! PARITY_PASS / ADMITTED): every scored call is evaluated again through `abep_subsystems::life::eval` and compared,
//! under the registered tolerance classes (EXACT_VALUE structure / strings / ints, ULP_BOUNDED floats: 4 ulp or 1e-12
//! relative, messages of the registered classes), with the Python outcome captured at the reference commit or, for
//! the registered divergence DIV-I01, with the registered Rust outcome. The captured files are read with the sha256
//! recorded in each parity report. Keeps the parity after the Python reference retires.

use abep_provenance::{read_verified, workspace_repo_root};
use abep_subsystems::life::{eval, indicators};
use abep_types::pyjson::{self, Value};
use std::io::Read;

const CONTRACTS: [(&str, &[&str]); 7] = [
    ("C-ABEP_SIM_AOCHEM_PY", &[]),
    ("C-ABEP_SIM_MATERIALS_PY", &[]),
    ("C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1-YIELD_KERNELS", &["ValueError"]),
    ("C-DOCS_EXPERIMENTS_LIFETIME_AO-AO_REGISTER_KERNELS", &["RuntimeError"]),
    ("C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS-SCREENING_KERNELS", &["ScreeningError"]),
    ("C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-LIFE_MATERIAL_KERNEL", &["NotEvaluatedDependency"]),
    ("C-ABEP_SIM_THERMAL_LIFE_PY-HALLMAP_WALL_INPUTS", &["ValueError"]),
];

fn get<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.as_dict().and_then(|d| d.get(k)).unwrap_or_else(|| panic!("missing {k}"))
}

fn load_gz(contract: &str, name: &str) -> Value {
    let root = workspace_repo_root().unwrap();
    let dir = root.join("docs/rust_migration/contracts").join(contract);
    let report =
        pyjson::loads(&pyjson::read_text_utf8(&std::fs::read(dir.join("parity_report_v1.json")).unwrap()).unwrap())
            .unwrap();
    let sha = get(get(get(&report, "captured_reference_outputs"), "files"), name);
    let gz = read_verified(&dir.join("reference_outputs").join(name), get(sha, "sha256").as_str().unwrap()).unwrap();
    let mut raw = String::new();
    flate2::read::GzDecoder::new(gz.as_slice()).read_to_string(&mut raw).unwrap();
    pyjson::loads(&raw).unwrap()
}

fn float_ok(p: f64, r: f64) -> bool {
    if p.is_nan() || r.is_nan() {
        return p.is_nan() && r.is_nan();
    }
    if p.is_infinite() || r.is_infinite() {
        return p == r;
    }
    let ulp = if p == 0.0 { f64::from_bits(1) } else { (f64::from_bits(p.abs().to_bits() + 1) - p.abs()).abs() };
    let d = (r - p).abs();
    d <= 4.0 * ulp || d <= 1e-12 * p.abs().max(1.0)
}

fn same(p: &Value, r: &Value) -> bool {
    match (p, r) {
        (Value::Float(a), Value::Float(b)) => float_ok(*a, *b),
        (Value::Dict(a), Value::Dict(b)) => {
            a.len() == b.len() && a.iter().zip(b.iter()).all(|((ka, va), (kb, vb))| ka == kb && same(va, vb))
        }
        (Value::List(a), Value::List(b)) => a.len() == b.len() && a.iter().zip(b).all(|(x, y)| same(x, y)),
        _ => p == r,
    }
}

fn agrees(want: &Value, got: &Value, message_classes: &[&str]) -> bool {
    let o = |v: &Value| get(v, "outcome").as_str().unwrap().to_string();
    if o(want) != o(got) {
        return false;
    }
    if o(want) == "RETURNED" {
        return same(get(want, "value"), get(got, "value"));
    }
    let class = get(want, "class").as_str().unwrap();
    class == get(got, "class").as_str().unwrap()
        && (!message_classes.contains(&class) || get(want, "message") == get(got, "message"))
}

#[test]
fn captured_python_outcomes_replay_in_rust() {
    let root = workspace_repo_root().unwrap();
    let rotor = pyjson::loads(&format!(
        r#"{{"outcome": "RAISED", "class": "{}", "message": "{}"}}"#,
        indicators::NOT_EVALUATED_DEPENDENCY,
        indicators::ROTOR_REFUSAL
    ))
    .unwrap();
    for (contract, classes) in CONTRACTS {
        let calls = load_gz(contract, "calls_v1.json.gz");
        let results = load_gz(contract, "python_results_v1.json.gz");
        let (calls, results) = (calls.as_list().unwrap(), results.as_list().unwrap());
        assert_eq!(calls.len(), results.len(), "{contract}");
        let mut failures = Vec::new();
        for (c, r) in calls.iter().zip(results) {
            let case = get(c, "case").as_str().unwrap();
            let mut call = pyjson::Dict::new();
            call.insert("fn", get(c, "fn").clone());
            call.insert("args", get(c, "args").clone());
            let got = eval::eval_call(&Value::Dict(call), &root);
            let want = if case.starts_with("E-I04") { &rotor } else { get(r, "result") };
            if !agrees(want, &got, classes) {
                failures.push(case.to_string());
            }
        }
        assert!(
            failures.is_empty(),
            "{contract}: {} replay mismatches, e.g. {:?}",
            failures.len(),
            &failures[..failures.len().min(5)]
        );
        assert!(!calls.is_empty(), "{contract}");
    }
}
