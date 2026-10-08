//! The DBF-1 baseline loader (A9.37): the pinned values as frozen, and fail-closed refusals of a changed file.

mod common;

use abep_config::baseline::*;
use abep_types::pyjson::{loads, Value};
use abep_types::EvalStatus;
use std::path::Path;

fn copy_tree(tmp: &Path) {
    let repo = common::repo();
    for rel in [DBF1_CONFIG_REL, DBF1_LOCK_REL, DBF1_RECORD_REL] {
        let dst = tmp.join(rel);
        std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
        std::fs::copy(repo.join(rel), dst).unwrap();
    }
}

#[test]
fn the_frozen_dbf1_values_load_as_registered() {
    let c = load_dbf1(&common::repo()).unwrap();
    assert_eq!((c.geometry_id.as_str(), c.bz_shape_id.as_str()), ("G-RP1", "BZ-P5B16"));
    assert_eq!(c.b_peak_band_g, [69.93, 268.6]);
    assert_eq!(c.upstream.design_id, "A0.25_Ld20_phi0.9|F4-FIL-T0.9|T6-A1-U2-D0-Ti6Al4V-H0.5|V0.001|P0.02");
    assert_eq!((c.upstream.area_m2, c.upstream.p_set_pa, c.upstream.scenarios.len()), (0.25, 0.02, 10));
    assert_eq!((c.upstream.controller.kp, c.upstream.controller.ti_s), (0.3, 3.0));
    assert_eq!((c.icp.radius_m, c.icp.length_m, c.icp.f_rf_hz), (0.06, 0.15, 13.56e6));
    assert_eq!((c.drag.case_id.as_str(), c.drag.a_ref_m2, c.drag.cd), ("RC-DIAMANT", 0.5, 2.2));
    let pm = &c.power_mass;
    assert_eq!((pm.design_allocation_w, pm.common_allocation_w), (1350.0, 300.0));
    assert_eq!((pm.mass_margin_fraction, pm.nominal_dry_target_kg, pm.xe_reference_load_kg), (0.1, 34.0, 2.0));
    assert_eq!(c.anode_primary, "CAND-02A");
    assert_eq!(c.baseline_deficiencies.len(), 6);
}

#[test]
fn a_changed_config_or_lock_is_refused() {
    let tmp = common::scratch("dbf1");
    copy_tree(&tmp);
    assert!(load_dbf1(&tmp).is_ok());
    let p = tmp.join(DBF1_CONFIG_REL);
    let text = std::fs::read_to_string(&p).unwrap().replace("\"P_set_Pa\": 0.02", "\"P_set_Pa\": 0.05");
    std::fs::write(&p, text).unwrap();
    let e = load_dbf1(&tmp).unwrap_err();
    assert_eq!((e.class, e.status()), ("ConfigurationError", EvalStatus::ModelError));
    assert!(e.message.contains("needs a DCR"), "{}", e.message);
    copy_tree(&tmp);
    std::fs::write(tmp.join(DBF1_LOCK_REL), "{}\n").unwrap();
    assert!(load_dbf1(&tmp).unwrap_err().message.contains(DBF1_LOCK_REL));
    std::fs::remove_file(tmp.join(DBF1_LOCK_REL)).unwrap();
    assert!(load_dbf1(&tmp).unwrap_err().message.contains("no fallback"));
    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn parse_refuses_inconsistent_documents() {
    let raw = std::fs::read_to_string(common::repo().join(DBF1_CONFIG_REL)).unwrap();
    let ok = loads(&raw).unwrap();
    assert!(parse(ok.clone()).is_ok());
    let mut v = ok.clone();
    if let Value::Dict(d) = &mut v {
        d.insert("baseline", Value::str("DBF-2"));
    }
    assert!(parse(v).is_err());
    let bad = loads(&raw.replace("\"collector_axial_length_m\": 0.1", "\"collector_axial_length_m\": 0.2")).unwrap();
    assert!(parse(bad).unwrap_err().message.contains("icp"));
    let bad = loads(&raw.replace("\"area_m2\": 0.25", "\"area_m2\": 0.0")).unwrap();
    assert!(parse(bad).is_err());
}
