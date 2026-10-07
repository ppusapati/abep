//! CI replay of the captured reference outputs of the two SC-WP-11 parity contracts: every scored request is
//! re-evaluated by the Rust implementation and compared with the reference output after the registered DIV
//! transformations (`expected_rust_outputs.json.gz`), so the parity evidence keeps holding after Python is retired.

use abep_assess::parity::{eval_calls, Ctx};
use abep_provenance::{sha256_hex, workspace_repo_root};
use abep_types::pyjson::{dumps, loads, DumpOptions, Value};
use flate2::read::GzDecoder;
use std::io::Read;

const MESSAGE_CLASSES: [&str; 6] =
    ["A913RuleError", "BoundaryA9Error", "OptimizerError", "RuntimeError", "RvmError", "IcpGateError"];

fn gz(dir: &std::path::Path, name: &str, manifest: &Value) -> Value {
    let bytes = std::fs::read(dir.join(name)).unwrap();
    let want = manifest.as_dict().unwrap().get("files").unwrap().as_dict().unwrap().get(name).unwrap();
    assert_eq!(want.as_str().unwrap(), sha256_hex(&bytes), "{name} differs from its MANIFEST pin");
    let mut s = String::new();
    GzDecoder::new(&bytes[..]).read_to_string(&mut s).unwrap();
    loads(&s).unwrap()
}

fn field<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.as_dict().unwrap().get(k).unwrap()
}

fn text(v: &Value) -> String {
    dumps(v, &DumpOptions::default()).unwrap()
}

fn replay(contract_dir: &str) -> usize {
    let repo = workspace_repo_root().unwrap();
    let dir = repo.join(contract_dir).join("reference_outputs");
    let manifest = loads(&std::fs::read_to_string(dir.join("MANIFEST.json")).unwrap()).unwrap();
    let requests = gz(&dir, "requests.json.gz", &manifest);
    let expected = gz(&dir, "expected_rust_outputs.json.gz", &manifest);
    let calls = Value::List(
        requests
            .as_list()
            .unwrap()
            .iter()
            .map(|c| abep_types::pydict! { "fn" => field(c, "fn").clone(), "args" => field(c, "args").clone() })
            .collect(),
    );
    let ctx = Ctx::load(&repo).unwrap();
    let got = eval_calls(&ctx, &calls).unwrap();
    let (got, want) = (got.as_list().unwrap(), expected.as_list().unwrap());
    assert_eq!(got.len(), want.len());
    let mut bad = Vec::new();
    for ((r, e), c) in got.iter().zip(want).zip(requests.as_list().unwrap()) {
        let ok = match (field(e, "outcome").as_str().unwrap(), field(r, "outcome").as_str().unwrap()) {
            ("RETURNED", "RETURNED") => text(field(e, "value")) == text(field(r, "value")),
            ("RAISED", "RAISED") => {
                let cls = field(e, "class").as_str().unwrap();
                !MESSAGE_CLASSES.contains(&cls)
                    || (text(field(e, "class")) == text(field(r, "class"))
                        && text(field(e, "message")) == text(field(r, "message")))
            }
            _ => false,
        };
        if !ok {
            bad.push(field(c, "id").as_str().unwrap().to_string());
        }
    }
    assert!(bad.is_empty(), "{} replay mismatches: {:?}", bad.len(), &bad[..bad.len().min(10)]);
    got.len()
}

#[test]
fn design_gates_contract_replays() {
    let n = replay("docs/rust_migration/contracts/C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY");
    assert_eq!(n, 5199);
}

#[test]
fn rvm_and_icp_gate_contract_replays() {
    let n = replay("docs/rust_migration/contracts/C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE");
    assert_eq!(n, 2813);
}
