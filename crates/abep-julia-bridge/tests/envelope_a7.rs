//! NP-HALL-PARAMETRIC-ENVELOPE addendum A7: the registered demonstration keys are recomputed from the frozen inputs, the
//! committed demonstration case files reproduce, every A7 case differs from its v1 case only in the numerical fields,
//! and a grid stage is refused unless its gating demonstration result is committed and demonstrated. No test spawns
//! Julia.

use abep_hall::envelope as env;
use abep_julia_bridge::envelope_a7::{self as a7, Kind, Level};
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::{self, Value};
use std::path::PathBuf;

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn obj(v: &Value) -> &pyjson::Dict {
    v.as_dict().unwrap()
}

#[test]
fn registered_demonstration_keys_are_recomputed() {
    let r = repo();
    let add = a7::load_addendum(&r).unwrap();
    let dk = a7::registered_demo_keys(&r, &add).unwrap();
    assert_eq!((dk.a6.len(), dk.fresh.len(), dk.rp1.len()), (22, 14, 6));
    let (a3k, _) = a7::prior_keys(&r).unwrap();
    for k in dk.fresh.iter().chain(&dk.rp1) {
        assert!(!dk.a6.contains(k) && !a3k.contains(k), "fresh / RP-1 key {k} reuses an A3 or A6 case");
    }
    assert!(dk.rp1.iter().all(|k| k.contains("|G-RP1|BZ-P5B16|")), "RP-1 seeded keys on the DBF-1 hardware");
    let rp1 = dk.of(Kind::DemoRp1);
    assert_eq!(rp1.len(), 11);
    assert!(rp1.iter().all(|k| k.contains("|G-RP1|")));
    assert_eq!(rp1.len() + dk.of(Kind::DemoRest).len(), dk.all().len());
}

#[test]
fn committed_demonstration_case_files_reproduce() {
    let r = repo();
    assert_eq!(a7::check(&r, Kind::DemoRp1).unwrap(), 22);
    assert_eq!(a7::check(&r, Kind::DemoRest).unwrap(), 62);
}

#[test]
fn a7_cases_change_only_numerical_fields() {
    let r = repo();
    let (v1doc, _, _) = abep_julia_bridge::envelope_a3::v1_case_set_and_cells(&r).unwrap();
    let base = &v1doc.as_dict().unwrap().get("cases").unwrap().as_list().unwrap()[0];
    let key = obj(base).get("key").unwrap().as_str().unwrap();
    let changed = [
        "key",
        "id",
        "cells",
        "dt_s",
        "duration_s",
        "average_start_s",
        "num_save",
        "numerics",
        "a7_level",
        "v1_key",
        "v1_case_sha256",
        "case_sha256",
    ];
    for lv in [Level::P, Level::C] {
        let c = a7::at_level(base, key, lv).unwrap();
        for (k, v) in obj(base).iter() {
            if !changed.contains(&k.as_str()) {
                assert_eq!(obj(&c).get(k), Some(v), "{k} changed at {}", lv.id());
            }
        }
        let n = |x: &Value, k: &str| obj(x).get(k).unwrap().to_f64().unwrap();
        assert_eq!(n(&c, "cells"), n(base, "cells") * lv.cell_factor() as f64);
        assert_eq!(n(&c, "duration_s"), 4.0 * n(base, "duration_s"));
        assert_eq!(n(&c, "average_start_s"), n(base, "duration_s"));
        assert_eq!(env::case_hash(&c).unwrap(), obj(&c).get("case_sha256").unwrap().as_str().unwrap());
    }
}

#[test]
fn grid_stages_need_their_demonstrated_gating_result() {
    let r = repo();
    for (kind, rel) in [(Kind::Grid(abep_hall::envelope_a7::GridStage::Stage1), a7::DEMO_RP1_RESULT_REL)] {
        if !r.join(rel).is_file() {
            assert!(a7::generate(&r, kind).is_err(), "no stage case file without its demonstration result");
        }
    }
    if !r.join(a7::DEMO_RESULT_REL).is_file() {
        assert!(a7::generate(&r, Kind::Grid(abep_hall::envelope_a7::GridStage::Stage2)).is_err());
    }
}
