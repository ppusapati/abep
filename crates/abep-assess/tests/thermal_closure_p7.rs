//! P7 thermal closure (A9.38 priority 7): the preregistration lock verifies, every registered case assembles, and the
//! committed closure record reproduces (governing and registered cases at its selected design levers, same
//! preregistration and load inputs).

use abep_assess::thermal_closure::assess::{run_named, Variant, K0};
use abep_assess::thermal_closure::record::dry_assemble;
use abep_assess::thermal_closure::{Context, PREREG_PATH};
use abep_provenance::git::Git;
use abep_provenance::workspace_repo_root;
use abep_subsystems::thermal::RunContext;
use serde_json::Value;
use std::sync::OnceLock;

const RECORD: &str = "docs/closure/thermal/thermal_closure_v1.json";
const INPUTS: &str = "docs/closure/thermal/thermal_load_inputs_v1.json";

fn ctx() -> &'static Context {
    static C: OnceLock<Context> = OnceLock::new();
    C.get_or_init(|| {
        let root = workspace_repo_root().unwrap();
        let git = Git::new(&root);
        let commit = git.stdout(&["rev-parse", "--verify", "HEAD^{commit}"]).unwrap();
        Context::load(&root, INPUTS, RunContext { rust_commit: commit, rust_tree_dirty: false }).unwrap()
    })
}

fn record() -> Value {
    let root = workspace_repo_root().unwrap();
    serde_json::from_slice(&std::fs::read(root.join(RECORD)).unwrap()).unwrap()
}

#[test]
fn every_registered_case_assembles_without_a_reason() {
    for (case, reasons) in dry_assemble(ctx()).unwrap() {
        assert!(reasons.is_empty(), "{case}: {reasons:?}");
    }
}

#[test]
fn a_changed_preregistration_is_refused() {
    let root = workspace_repo_root().unwrap();
    let dir = std::env::temp_dir().join(format!("p7_lock_{}", std::process::id()));
    for rel in [PREREG_PATH, abep_assess::thermal_closure::LOCK_PATH, INPUTS] {
        let to = dir.join(rel);
        std::fs::create_dir_all(to.parent().unwrap()).unwrap();
        std::fs::copy(root.join(rel), &to).unwrap();
    }
    let mut bytes = std::fs::read(dir.join(PREREG_PATH)).unwrap();
    bytes.push(b' ');
    std::fs::write(dir.join(PREREG_PATH), bytes).unwrap();
    let run = RunContext { rust_commit: "x".into(), rust_tree_dirty: false };
    let e = Context::load(&dir, INPUTS, run).err().expect("refused");
    assert!(e.0.contains("differs from the lock"), "{e}");
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn the_committed_record_reproduces() {
    let c = ctx();
    let rec = record();
    assert_eq!(rec["preregistration"]["sha256"].as_str(), Some(c.prereg.sha256.as_str()));
    assert_eq!(rec["load_inputs"]["sha256"].as_str(), Some(c.inputs_sha256.as_str()));
    let sel = &rec["design_lever_search"]["selected"];
    let v = Variant {
        a_rh: sel["A_RH_m2"].as_f64().unwrap(),
        g_rh: sel["G_RH_W_K"].as_f64().unwrap(),
        ..Default::default()
    };
    let runs = rec["governing_and_registered_runs"].as_object().unwrap();
    for (id, want) in runs {
        let got = run_named(c, id, &v).unwrap();
        assert_eq!(serde_json::to_value(got.status).unwrap(), want["run_status"], "{id}");
        for (key, map) in [("T_max_C", &got.t_max_k), ("T_min_C", &got.t_min_k)] {
            let w = want[key].as_object().unwrap();
            assert_eq!(w.len(), map.len(), "{id} {key}");
            for (n, t) in map {
                let e = w[n].as_f64().unwrap();
                assert!((t - K0 - e).abs() < 1e-6, "{id} {key} {n}: {} vs {e}", t - K0);
            }
        }
    }
    // XE_CONTINGENCY carries the identical registered load set: identical temperatures.
    assert_eq!(runs["TC7-HOT-H-BSTAR-XE"]["T_max_C"], runs["TC1-HOT-H-BSTAR"]["T_max_C"]);
}
