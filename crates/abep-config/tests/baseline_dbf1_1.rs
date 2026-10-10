//! The DBF-1.1 baseline loader (DCR-DBF1-002): only DBF1-BZ-04 / BD-05 differ from DBF-1, every B(z) profile is
//! pinned, and changed files are refused (fail closed). DBF-1 loads unchanged alongside.

mod common;

use abep_config::baseline::*;
use abep_types::pyjson::loads;
use abep_types::EvalStatus;
use std::path::Path;

fn copy_tree(tmp: &Path, extra: &[String]) {
    let repo = common::repo();
    let mut rels: Vec<String> =
        [DBF1_1_CONFIG_REL, DBF1_1_LOCK_REL, DBF1_1_RECORD_REL].iter().map(|s| s.to_string()).collect();
    rels.extend(extra.iter().cloned());
    for rel in rels {
        let dst = tmp.join(&rel);
        std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
        std::fs::copy(repo.join(&rel), dst).unwrap();
    }
}

#[test]
fn dbf1_1_loads_with_the_fe_field_and_otherwise_equals_dbf1() {
    let repo = common::repo();
    let c = load_dbf1_1(&repo).unwrap();
    let p = load_dbf1(&repo).unwrap();
    assert_eq!(p.bz_shape_id, "BZ-P5B16");
    assert_eq!(c.base.bz_shape_id, "BZ-H1FE-V1");
    assert_eq!(c.base.geometry_id, p.geometry_id);
    assert_eq!(c.base.b_peak_band_g, p.b_peak_band_g);
    assert_eq!(c.base.upstream, p.upstream);
    assert_eq!(c.base.icp, p.icp);
    assert_eq!(c.base.drag, p.drag);
    assert_eq!(c.base.power_mass, p.power_mass);
    assert_eq!((&c.base.anode_primary, &c.base.anode_backup), (&p.anode_primary, &p.anode_backup));
    let open: Vec<_> = p.baseline_deficiencies.iter().filter(|d| d.as_str() != "DBF1-BD-05").cloned().collect();
    assert_eq!(c.base.baseline_deficiencies, open);
    assert_eq!(c.closed_deficiencies, vec!["DBF1-BD-05".to_string()]);
    assert_eq!(c.parent_lock_sha256, DBF1_LOCK_SHA256);
    assert_eq!(c.dcr_approval_sha256, DCR_DBF1_002_APPROVAL_SHA256);
    let ids: Vec<_> = c.bz_profiles.iter().map(|b| (b.role.as_str(), b.id.as_str())).collect();
    assert_eq!(
        ids,
        vec![("nominal", "BP-LO"), ("nominal", "BP-HI"), ("envelope", "CORNER-A"), ("envelope", "CORNER-B")]
    );
    for b in &c.bz_profiles {
        assert!(b.file.starts_with("hallthruster_bridge/bfield/h1_fe_v1/") && b.ni_total_a > 0.0, "{b:?}");
    }
}

#[test]
fn a_changed_dbf1_1_file_or_profile_is_refused() {
    let repo = common::repo();
    let c = load_dbf1_1(&repo).unwrap();
    let profiles: Vec<String> = c.bz_profiles.iter().map(|b| b.file.clone()).collect();
    let tmp = common::scratch("dbf1_1");
    copy_tree(&tmp, &profiles);
    assert!(load_dbf1_1(&tmp).is_ok());
    // a changed profile file
    let f = tmp.join(&profiles[1]);
    let text = std::fs::read_to_string(&f).unwrap() + "1.0,1.0\n";
    std::fs::write(&f, text).unwrap();
    let e = load_dbf1_1(&tmp).unwrap_err();
    assert_eq!((e.class, e.status()), ("ConfigurationError", EvalStatus::ModelError));
    assert!(e.message.contains(&profiles[1]) && e.message.contains("needs a DCR"), "{}", e.message);
    // a changed config
    copy_tree(&tmp, &profiles);
    let p = tmp.join(DBF1_1_CONFIG_REL);
    let text = std::fs::read_to_string(&p)
        .unwrap()
        .replace("\"bz_shape_id\": \"BZ-H1FE-V1\"", "\"bz_shape_id\": \"BZ-P5B16\"");
    std::fs::write(&p, text).unwrap();
    assert!(load_dbf1_1(&tmp).unwrap_err().message.contains(DBF1_1_CONFIG_REL));
    // a missing lock
    copy_tree(&tmp, &profiles);
    std::fs::remove_file(tmp.join(DBF1_1_LOCK_REL)).unwrap();
    assert!(load_dbf1_1(&tmp).unwrap_err().message.contains("no fallback"));
    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn the_two_parsers_refuse_each_others_documents() {
    let repo = common::repo();
    let raw11 = std::fs::read_to_string(repo.join(DBF1_1_CONFIG_REL)).unwrap();
    let raw1 = std::fs::read_to_string(repo.join(DBF1_CONFIG_REL)).unwrap();
    assert!(parse_dbf1_1(loads(&raw11).unwrap()).is_ok());
    assert!(parse(loads(&raw11).unwrap()).is_err());
    assert!(parse_dbf1_1(loads(&raw1).unwrap()).is_err());
    let bad = raw11.replace(DCR_DBF1_002_APPROVAL_SHA256, &"0".repeat(64));
    assert!(parse_dbf1_1(loads(&bad).unwrap()).unwrap_err().message.contains("lineage"));
    let bad = raw11.replace("\"CORNER-B\"", "\"CORNER-C\"");
    assert!(parse_dbf1_1(loads(&bad).unwrap()).unwrap_err().message.contains(DBF1_1_CONFIG_REL));
}
