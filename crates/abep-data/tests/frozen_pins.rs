//! Every pin of the frozen environment datasets agrees with the bytes on disk and with the other pins of the same
//! file (contract PARITY-C-ABEP_SIM_ATMOSPHERE_ORBIT_PY-V1 INV-D-05).

use abep_data::design_states::{DesignStateSet, DESIGN_STATE_DATASET_SHA256, DESIGN_STATE_SET_SHA256};
use abep_data::pins::FrozenPins;
use abep_data::{data_rel, hwm14_v2, msis21_v1, orbit_v1};
use abep_provenance::{sha256_file, workspace_repo_root};

#[test]
fn model_set_and_reference_pins_match_the_frozen_files() {
    let root = workspace_repo_root().unwrap();
    let pins = FrozenPins::load(&root).unwrap();
    for f in [
        msis21_v1::CSV_FILE,
        msis21_v1::JSON_FILE,
        orbit_v1::GZ_FILE,
        orbit_v1::JSON_FILE,
        orbit_v1::DESIGN_V1_FILE,
        orbit_v1::DESIGN_V2_FILE,
        hwm14_v2::GZ_FILE,
        hwm14_v2::DIST_GZ_FILE,
        hwm14_v2::JSON_FILE,
    ] {
        let rel = data_rel(f);
        assert_eq!(sha256_file(&root.join(&rel)).unwrap(), pins.pin(&rel).unwrap(), "{rel}");
    }
    let r = &pins.design_state_set_ref;
    assert_eq!((r.sha256.as_str(), r.n_states), (DESIGN_STATE_SET_SHA256, 196));
    assert_eq!(r.dataset_sha256, DESIGN_STATE_DATASET_SHA256);
    assert_eq!(r.manifest.sha256, pins.pin(&data_rel(orbit_v1::JSON_FILE)).unwrap());
    assert_eq!(pins.mission_altitude_band_km, (180.0, 230.0));

    let set = DesignStateSet::load(&root, &pins).unwrap();
    assert_eq!((set.n_states, set.states.len()), (196, 196));
    assert!(set.states.iter().all(|s| s.required && s.source.contains(DESIGN_STATE_DATASET_SHA256)));
    assert!(set.select("ds2:bogus").is_none());
}
