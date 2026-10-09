//! DCR-DBF1-003 (co-located RF match, P7): the preregistration lock verifies, both route networks assemble without a
//! reason, the R-2 line relation has its closed-form limits, and the committed evaluation record reproduces at its
//! selected R-1 design and for R-2.

use abep_assess::thermal_closure::assess::{run_named, Variant, K0};
use abep_assess::thermal_closure::build::build;
use abep_assess::thermal_closure::dcr003::*;
use abep_assess::thermal_closure::Context;
use abep_provenance::workspace_repo_root;
use abep_subsystems::thermal::assemble::assemble_v2;
use abep_subsystems::thermal::RunContext;
use serde_json::Value;

const RECORD: &str = "docs/closure/thermal/dcr003_evaluation_v1.json";

fn run_ctx() -> RunContext {
    RunContext { rust_commit: "test".into(), rust_tree_dirty: false }
}

fn load() -> (Dcr, Context) {
    let root = workspace_repo_root().unwrap();
    (Dcr::load(&root).unwrap(), Context::load(&root, INPUTS_PATH, run_ctx()).unwrap())
}

fn record() -> Value {
    let root = workspace_repo_root().unwrap();
    serde_json::from_slice(&std::fs::read(root.join(RECORD)).unwrap()).unwrap()
}

fn hall() -> Variant {
    Variant { a_rh: 0.02, g_rh: 2.0, ..Default::default() }
}

fn assembles(ctx: &Context, id: &str) -> Vec<String> {
    let c = abep_assess::thermal_closure::assess::case_def(ctx, id).unwrap();
    let mut sp = abep_assess::thermal_closure::assess::spec_for(ctx, &c, &hall()).unwrap();
    sp.t_init = ctx.prereg.nodes.iter().filter_map(|n| n["id"].as_str().map(|x| (x.to_string(), 400.0))).collect();
    let case = build(&ctx.prereg, &sp).unwrap();
    assemble_v2(&case, &ctx.gov).reasons.iter().map(|r| format!("{:?}:{}:{}", r.status, r.code, r.subject)).collect()
}

#[test]
fn line_relation_limits() {
    // Matched load: the matched-line loss only.
    let ml = 0.3;
    assert!((line_efficiency(50.0, 0.0, ml) - 10f64.powf(-ml / 10.0)).abs() < 1e-12);
    // Lossless line: everything reaches the load, whatever the mismatch.
    assert!((line_efficiency(1.0, 164.0, 0.0) - 1.0).abs() < 1e-12);
    // More loss or a worse mismatch never helps.
    assert!(line_efficiency(1.0, 164.0, 0.1) < line_efficiency(5.0, 164.0, 0.1));
    assert!(line_efficiency(1.0, 164.0, 0.2) < line_efficiency(1.0, 164.0, 0.1));
    // Wheeler: 3 turns, r 75 mm, l 36 mm.
    let l = wheeler_inductance_h(0.075, 0.036, 3.0);
    assert!((l * 1e6 - 1.9258).abs() < 1e-3, "{l}");
}

#[test]
fn a_changed_preregistration_is_refused() {
    let root = workspace_repo_root().unwrap();
    let dir = std::env::temp_dir().join(format!("dcr003_lock_{}", std::process::id()));
    let lock: Value = serde_json::from_slice(&std::fs::read(root.join(DCR_LOCK_PATH)).unwrap()).unwrap();
    let mut rels: Vec<String> = lock["files"].as_object().unwrap().keys().cloned().collect();
    rels.push(DCR_LOCK_PATH.into());
    for rel in &rels {
        let to = dir.join(rel);
        std::fs::create_dir_all(to.parent().unwrap()).unwrap();
        std::fs::copy(root.join(rel), &to).unwrap();
    }
    assert!(Dcr::load(&dir).is_ok());
    let mut bytes = std::fs::read(dir.join(DCR_PREREG_PATH)).unwrap();
    bytes.push(b' ');
    std::fs::write(dir.join(DCR_PREREG_PATH), bytes).unwrap();
    let e = Dcr::load(&dir).err().expect("refused");
    assert!(e.0.contains("differs from the lock"), "{e}");
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn both_route_networks_assemble_without_a_reason() {
    let (_, mut ctx) = load();
    let base = Base::of(&ctx);
    apply_r1(&mut ctx, &base, R1Point { a_ma: 0.2, g_iso: 0.04, g_lead: 0.025, q_match_frac: 0.06 }).unwrap();
    assert!(ctx.prereg.links.iter().any(|l| l["id"] == "L_MA_ANT"));
    for id in ["TC1-HOT-H-BSTAR", "TC4-HOT-I-B0", "TC6-COLD-NONOP-B0"] {
        assert_eq!(assembles(&ctx, id), Vec::<String>::new(), "R-1 {id}");
    }
    apply_r2(&mut ctx, &base);
    assert!(!ctx.prereg.nodes.iter().any(|n| n["id"] == "N_MATCH"));
    for id in ["TC1-HOT-H-BSTAR", "TC4-HOT-I-B0", "TC6-COLD-NONOP-B0"] {
        assert_eq!(assembles(&ctx, id), Vec::<String>::new(), "R-2 {id}");
    }
}

fn same(got: &abep_assess::thermal_closure::assess::CaseRun, want: &Value, what: &str) {
    assert_eq!(serde_json::to_value(got.status).unwrap(), want["run_status"], "{what}");
    let w = want["T_max_C"].as_object().unwrap();
    assert_eq!(w.len(), got.t_max_k.len(), "{what}");
    for (n, t) in &got.t_max_k {
        let e = w[n].as_f64().unwrap();
        assert!((t - K0 - e).abs() < 1e-6, "{what} {n}: {} vs {e}", t - K0);
    }
}

#[test]
fn the_committed_record_reproduces() {
    let rec = record();
    let (dcr, mut ctx) = load();
    assert_eq!(rec["preregistration"]["sha256"].as_str(), Some(dcr.sha256.as_str()));
    assert_eq!(rec["load_inputs"]["sha256"].as_str(), Some(ctx.inputs_sha256.as_str()));
    let base = Base::of(&ctx);
    let r1 = &rec["R-1"];
    let hot = &r1["hot_corner"];
    let p = R1Point {
        a_ma: r1["selected"]["A_MA_m2"].as_f64().unwrap(),
        g_iso: hot["G_iso"].as_f64().unwrap(),
        g_lead: hot["G_lead"].as_f64().unwrap(),
        q_match_frac: hot["Q_match_frac"].as_f64().unwrap(),
    };
    apply_r1(&mut ctx, &base, p).unwrap();
    for id in ["TC1-HOT-H-BSTAR", "TC3-HOT-I-BSTAR"] {
        same(&run_named(&ctx, id, &hall()).unwrap(), &r1["runs"][id], &format!("R-1 {id}"));
    }
    apply_r2(&mut ctx, &base);
    same(&run_named(&ctx, "TC3-HOT-I-BSTAR", &hall()).unwrap(), &rec["R-2"]["runs"]["TC3-HOT-I-BSTAR"], "R-2 TC3");
    // The R-2 RF penalty is pure arithmetic on the preregistration: identical.
    let (dcr, ctx) = load();
    assert_eq!(r2_rf_penalty(&dcr, &ctx).unwrap(), rec["R-2"]["rf_penalty"]);
    // The selection follows the preregistered rule.
    let route = rec["selection"]["route"].as_str().unwrap();
    let r1_ok = rec["R-1"]["admissible"].as_bool().unwrap();
    let r2_ok = rec["R-2"]["admissible"].as_bool().unwrap();
    assert_eq!(
        route,
        if r1_ok {
            "R-1"
        } else if r2_ok {
            "R-2"
        } else {
            "BLOCKED"
        }
    );
}
