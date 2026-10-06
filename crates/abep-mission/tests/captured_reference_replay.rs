//! CI replay of the captured Python reference outputs of the SC-WP-04 contracts (ADMITTED, parity_report_v1.json):
//! every registered request is re-run through the Rust dispatcher and compared with the Python output under the
//! contract tolerance classes (EXACT_VALUE with bit-equal floats; ULP_BOUNDED 4 ulp on the registered paths, plus
//! 1e-12 relative where the input passes the atmosphere readers), so parity stays checked after the Python reference
//! is retired. The record builder contract is replayed by `record_and_layers::builder_check_reproduces_the_committed_record`.

use abep_data::gz::gunzip;
use abep_mission::parity::{arg, decode, run_request, ParityContext};
use abep_provenance::{read_verified, sha256_hex, workspace_repo_root};
use abep_types::pyjson::{loads, read_text_utf8, Value};

const DIR: &str = "docs/rust_migration/contracts";

struct Contract {
    dir: &'static str,
    manifest_sha256: &'static str,
    n: usize,
    /// ids whose registered outcome diverges (DIV-A-01: Python returns a non-finite result, Rust refuses)
    div: &'static [&'static str],
}

const CONTRACTS: [Contract; 3] = [
    Contract {
        dir: "C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY",
        manifest_sha256: "336cbb42440f1a27b525800abe2c6608c54ae21e8aade0ac62321175b8d2e2bd",
        n: 4492,
        div: &["DE-A-26", "DE-A-27", "DE-A-28"],
    },
    Contract {
        dir: "C-ABEP_SIM_STATEWISE_PY",
        manifest_sha256: "7ffedd4fcb90b1ce1ebc3c54d4c90351edcb533cdbe377928f6b8e1ecc95a858",
        n: 432,
        div: &[],
    },
    Contract {
        dir: "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL",
        manifest_sha256: "50f4090a132ad71c1116b48da650dbaded32572d997aca6e8c843fb15a69b75a",
        n: 1686,
        div: &[],
    },
];

/// Registered ULP paths per entry point ("*" = any list element): (path, k_ulp, r_rel).
fn rules(entry: &str) -> Vec<(Vec<&'static str>, f64, Option<f64>)> {
    let k4 = |p: &[&'static str]| (p.to_vec(), 4.0, None);
    let k4r = |p: &[&'static str]| (p.to_vec(), 4.0, Some(1e-12));
    match entry {
        "reference_drag" => vec![
            k4(&["q_Pa"]),
            k4(&["reference_term", "D_N"]),
            k4(&["intake_term", "D_N"]),
            k4(&["D_total_N"]),
            k4(&["D_total_mN"]),
        ],
        "statewise_margin" => vec![k4(&["margin_N"])],
        "statewise_quantifier" => vec![k4(&["orbit_average_margin"])],
        "drag_table" => vec![k4r(&["*", "D_per_area_N_m2"]), k4r(&["*", "SE_per_area_N_m2"])],
        "thrust_minus_drag" => vec![k4(&["value"]), k4(&["drag_total_N"])],
        "statewise_t_minus_d" => vec![k4r(&["*", "objectives", "*", "partial", "D_intake_N"])],
        _ => vec![],
    }
}

fn ulp(x: f64) -> f64 {
    let a = x.abs();
    if a < f64::MIN_POSITIVE {
        return f64::from_bits(1);
    }
    2f64.powi(((a.to_bits() >> 52) & 0x7ff) as i32 - 1023 - 52)
}

fn walk(
    py: &Value,
    rs: &Value,
    rules: &[(Vec<&str>, f64, Option<f64>)],
    path: &mut Vec<String>,
    out: &mut Vec<String>,
) {
    let here = path.join("/");
    match (py, rs) {
        (Value::Dict(a), Value::Dict(b)) => {
            if a.keys().collect::<Vec<_>>() != b.keys().collect::<Vec<_>>() {
                out.push(format!("{here}: keys differ"));
                return;
            }
            for (k, v) in a.iter() {
                path.push(k.clone());
                walk(v, b.get(k).unwrap(), rules, path, out);
                path.pop();
            }
        }
        (Value::List(a), Value::List(b)) => {
            if a.len() != b.len() {
                out.push(format!("{here}: length {} != {}", a.len(), b.len()));
                return;
            }
            for (x, y) in a.iter().zip(b) {
                path.push("*".into());
                walk(x, y, rules, path, out);
                path.pop();
            }
        }
        (Value::Float(p), Value::Float(r)) => {
            let rule = rules
                .iter()
                .find(|(rp, _, _)| rp.len() == path.len() && rp.iter().zip(path.iter()).all(|(a, b)| a == b));
            let ok = p.to_bits() == r.to_bits()
                || rule.is_some_and(|(_, k, rr)| {
                    let d = (r - p).abs();
                    d <= k * ulp(*p) || rr.is_some_and(|rr| d <= rr * p.abs())
                });
            if !ok {
                out.push(format!("{here}: rust {r:e} python {p:e}"));
            }
        }
        (a, b) if a == b => {}
        (a, b) => out.push(format!("{here}: rust {b:?} python {a:?}")),
    }
}

fn load_gz(root: &std::path::Path, dir: &str, name: &str, sha: &str) -> Vec<Value> {
    let path = root.join(DIR).join(dir).join("reference_outputs").join(name);
    let raw = gunzip(&read_verified(&path, sha).unwrap(), name).unwrap();
    match loads(&read_text_utf8(&raw).unwrap()).unwrap() {
        Value::List(l) => l,
        _ => panic!("{name}: list expected"),
    }
}

#[test]
fn rust_reproduces_the_captured_python_reference_outputs() {
    let root = workspace_repo_root().unwrap();
    for c in &CONTRACTS {
        let mpath = root.join(DIR).join(c.dir).join("reference_outputs/MANIFEST.json");
        let manifest = read_verified(&mpath, c.manifest_sha256).unwrap();
        let manifest = loads(&read_text_utf8(&manifest).unwrap()).unwrap();
        let sha = |name: &str| arg(arg(&manifest, "files"), name).as_str().unwrap().to_string();
        let requests = load_gz(&root, c.dir, "requests.json.gz", &sha("requests.json.gz"));
        let python = load_gz(&root, c.dir, "python_outputs.json.gz", &sha("python_outputs.json.gz"));
        assert_eq!((requests.len(), python.len()), (c.n, c.n), "{}", c.dir);
        let mut ctx = ParityContext::new(root.clone());
        let mut failures = Vec::new();
        for (req, py) in requests.iter().zip(&python) {
            let req = decode(req.clone());
            let id = arg(&req, "id").as_str().unwrap_or_default().to_string();
            assert_eq!(arg(py, "id").as_str(), Some(id.as_str()));
            let rs = run_request(&mut ctx, &req);
            let (po, ro) = (arg(py, "outcome").as_str().unwrap(), arg(&rs, "outcome").as_str().unwrap());
            if c.div.contains(&id.as_str()) {
                let ok = po == "RETURNED"
                    && ro == "RAISED"
                    && arg(&rs, "status").as_str() == Some("OUT_OF_DOMAIN")
                    && arg(&rs, "message").as_str().unwrap_or_default().starts_with("non-finite drag result");
                if !ok {
                    failures.push(format!("{id}: registered divergence not met"));
                }
                continue;
            }
            if po != ro {
                failures.push(format!("{id}: outcome python {po} rust {ro}"));
                continue;
            }
            if po == "RAISED" {
                if arg(py, "class") != arg(&rs, "class")
                    || arg(py, "message") != arg(&rs, "message")
                    || arg(&rs, "status").as_str() != Some("OUT_OF_DOMAIN")
                {
                    failures.push(format!(
                        "{id}: error python {:?} rust {:?}",
                        arg(py, "message"),
                        arg(&rs, "message")
                    ));
                }
                continue;
            }
            let mut out = Vec::new();
            walk(
                arg(py, "value"),
                arg(&rs, "value"),
                &rules(arg(&req, "entry").as_str().unwrap()),
                &mut vec![],
                &mut out,
            );
            if !out.is_empty() {
                failures.push(format!("{id}: {}", out[..out.len().min(3)].join("; ")));
            }
        }
        assert!(
            failures.is_empty(),
            "{}: {} failures, first: {:?}",
            c.dir,
            failures.len(),
            &failures[..failures.len().min(5)]
        );
        // the manifest pins the replayed files themselves
        assert_eq!(sha256_hex(&std::fs::read(&mpath).unwrap()), c.manifest_sha256);
    }
}
