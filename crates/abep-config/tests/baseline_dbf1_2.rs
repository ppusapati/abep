//! The DBF-1.2 baseline loader (DCR-DBF1-001 resolution, A9.39 item 3): the upstream items, the variable-capture
//! mechanism and the operating window differ from DBF-1.1; everything else equals DBF-1.1; changed files are refused
//! (fail closed). DBF-1 and DBF-1.1 load unchanged alongside.

mod common;

use abep_config::baseline::*;
use abep_types::pyjson::loads;
use abep_types::EvalStatus;
use std::path::Path;

fn copy_tree(tmp: &Path, extra: &[String]) {
    let repo = common::repo();
    let mut rels: Vec<String> =
        [DBF1_2_CONFIG_REL, DBF1_2_LOCK_REL, DBF1_2_RECORD_REL].iter().map(|s| s.to_string()).collect();
    rels.extend(extra.iter().cloned());
    for rel in rels {
        let dst = tmp.join(&rel);
        std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
        std::fs::copy(repo.join(&rel), dst).unwrap();
    }
}

#[test]
fn dbf1_2_loads_with_the_dcr001_selection_and_otherwise_equals_dbf1_1() {
    let repo = common::repo();
    let c = load_dbf1_2(&repo).unwrap();
    let p = load_dbf1_1(&repo).unwrap();
    assert_eq!(c.base.bz_shape_id, "BZ-H1FE-V1");
    assert_eq!(c.bz_profiles, p.bz_profiles);
    assert_eq!(c.base.geometry_id, p.base.geometry_id);
    assert_eq!(c.base.icp, p.base.icp);
    assert_eq!(c.base.drag, p.base.drag);
    assert_eq!(c.base.power_mass, p.base.power_mass);
    assert_eq!(c.base.upstream.scenarios, p.base.upstream.scenarios);
    assert_ne!(c.base.upstream.design_id, p.base.upstream.design_id);
    assert_eq!(c.base.upstream.area_m2, c.variable_capture.a_max_m2);
    assert!(c.variable_capture.n_segments >= 1 && c.variable_capture.c_closed > 0.0);
    assert!(c.window.phi_hi_kg_m2_s > c.window.phi_lo_kg_m2_s && c.window.phi_lo_kg_m2_s > 0.0);
    assert_eq!(c.window.altitude_schedule.len(), 4);
    for (_, nodes) in &c.window.altitude_schedule {
        assert!(nodes.iter().all(|h| (180.0..=230.0).contains(h)));
    }
    assert_eq!(c.parent_lock_sha256, DBF1_1_LOCK_SHA256);
    assert_eq!(c.dcr_resolution_sha256, DCR_DBF1_001_RESOLUTION_SHA256);
    assert!(c.closed_deficiencies.contains(&"DBF1-BD-05".to_string()));
    for d in c.closed_deficiencies.iter().chain(&c.transferred_deficiencies) {
        assert!(!c.base.baseline_deficiencies.contains(d), "{d}");
    }
}

#[test]
fn a_changed_dbf1_2_file_or_profile_is_refused() {
    let repo = common::repo();
    let c = load_dbf1_2(&repo).unwrap();
    let profiles: Vec<String> = c.bz_profiles.iter().map(|b| b.file.clone()).collect();
    let tmp = common::scratch("dbf1_2");
    copy_tree(&tmp, &profiles);
    assert!(load_dbf1_2(&tmp).is_ok());
    let p = tmp.join(DBF1_2_CONFIG_REL);
    let text = std::fs::read_to_string(&p).unwrap().replace("\"DBF-1.2\"", "\"DBF-1.1\"");
    std::fs::write(&p, text).unwrap();
    let e = load_dbf1_2(&tmp).unwrap_err();
    assert_eq!((e.class, e.status()), ("ConfigurationError", EvalStatus::ModelError));
    assert!(e.message.contains(DBF1_2_CONFIG_REL));
    copy_tree(&tmp, &profiles);
    std::fs::remove_file(tmp.join(DBF1_2_LOCK_REL)).unwrap();
    assert!(load_dbf1_2(&tmp).unwrap_err().message.contains("no fallback"));
    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn the_parsers_refuse_each_others_documents() {
    let repo = common::repo();
    let raw12 = std::fs::read_to_string(repo.join(DBF1_2_CONFIG_REL)).unwrap();
    let raw11 = std::fs::read_to_string(repo.join(DBF1_1_CONFIG_REL)).unwrap();
    assert!(parse_dbf1_2(loads(&raw12).unwrap()).is_ok());
    assert!(parse_dbf1_1(loads(&raw12).unwrap()).is_err());
    assert!(parse(loads(&raw12).unwrap()).is_err());
    assert!(parse_dbf1_2(loads(&raw11).unwrap()).is_err());
    let bad = raw12.replace(DCR_DBF1_001_RESOLUTION_SHA256, &"0".repeat(64));
    assert!(parse_dbf1_2(loads(&bad).unwrap()).unwrap_err().message.contains("lineage"));
}
