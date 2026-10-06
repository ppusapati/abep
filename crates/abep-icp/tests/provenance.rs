//! The frozen preregistration, its A9.30 addendum and the NP-ICP-CHEM-AIR contract are lock-verified on load; every
//! data file the model reads is sha256-pinned by one of them; outputs carry OUT-14 provenance and the lifecycle labels.

mod common;

use abep_icp::context::{CHEM_AIR_LOCK_SHA256, ICP_CHEM_PINNED, PREREG_LOCK_SHA256};
use abep_icp::testkit::*;
use common::model;

#[test]
fn locks_and_pinned_files_verify() {
    let m = model();
    assert_eq!(m.prereg_lock_sha256, PREREG_LOCK_SHA256);
    assert_eq!(m.prereg_sha256, "5d496ea6538ef65999c3cb8b1f4274622dc060889b1cf14f46a0a02a855a91a8");
    assert_eq!(m.prereg_md_sha256, "3af97940032b2ebff530d92c886a6690ceca30a21ed6d8bf5354d7cca79f36cc");
    assert_eq!(m.chem_air_lock_sha256, CHEM_AIR_LOCK_SHA256);
    let paths: Vec<&str> = m.files_read.iter().map(|f| f.path.as_str()).collect();
    for p in [
        "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_v1.json",
        "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/addendum_01_a9_30.json",
        "docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/prereg_v1.json",
        "hallthruster_bridge/propellants/rate_validity.toml",
        "hallthruster_bridge/propellants/n2_n.toml",
        "hallthruster_bridge/ensemble/transport_ensemble_v0.json",
        "config/architecture/hall_icp_neutralizer_v1.json",
        "hallthruster_bridge/propellants/ionization_N_to_N_Z2plus_hms2017.dat",
        "data/chemistry/icp/ICP_CHEM_PINNED.toml",
        "data/chemistry/icp/registry_air.toml",
        "data/chemistry/icp/registry_xe.toml",
        "data/chemistry/icp/rate_validity_icp.toml",
        "data/chemistry/icp/reuse_pins.json",
        "data/chemistry/icp/xs/ionization_N2_song2023.json",
        "docs/rust_migration/contracts/C-ABEP_SIM_RATE_TABLES_PY/parity_report_v1.json",
    ] {
        assert!(paths.contains(&p), "{p} not read through a pin");
    }
    for f in &m.files_read {
        let actual = abep_icp::context::sha256_of(&m.repo_root.join(&f.path)).unwrap();
        assert_eq!(actual, f.sha256, "{}", f.path);
        assert!(!f.pinned_by.is_empty());
    }
    assert_eq!(m.reaction_set_version, "abep-n2n-0.11");
    // The consumer's registry pin (labels abep-icp-air-0.0 / abep-icp-xe-0.0).
    assert_eq!(ICP_CHEM_PINNED, "074daff90b00dd1dd6ca776c845c7897bbd84b4217ec014e70fb374a16f16eb2");
    assert_eq!(m.chem_registry.pinned_sha256, ICP_CHEM_PINNED);
    assert_eq!(
        (m.chem_registry.air.label.as_str(), m.chem_registry.xe.label.as_str()),
        ("abep-icp-air-0.0", "abep-icp-xe-0.0")
    );
    assert_eq!(m.icp_feed_gas_primary, "G-REUSE");
    assert_eq!(m.supply_modes, vec!["AIR_PRIMARY".to_string(), "XE_CONTINGENCY".to_string()]);
}

#[test]
fn registered_n2_set_structure() {
    let s = &model().n2_set;
    assert_eq!(s.set_id, "abep-icp-air-0.0/EM-N2-NOMINAL");
    assert_eq!(s.reactions.len(), 29);
    let names: Vec<&str> = s.species.iter().map(|x| x.name.as_str()).collect();
    assert_eq!(names, vec!["N2", "N", "N2^+", "N^+", "N^2+"]);
    // Masses as n2_n.toml registers them (ion mass = neutral mass).
    let mass = |n: &str| s.species[s.species_index(n).unwrap()].mass_kg / abep_icp::constants::AMU;
    assert_eq!((mass("N2"), mass("N2^+"), mass("N"), mass("N^2+")), (28.0134, 28.0134, 14.0067, 14.0067));
    assert!(s.reactions.iter().all(|r| matches!(r.rate, abep_icp::chemistry::RateSource::RegisteredTable { .. })));
    assert!(s.reactions.iter().all(|r| r.id.contains('/')), "registry channel ids (OUT-12)");
    let ion = s.reactions.iter().find(|r| r.id.ends_with("ionization_N2_song2023")).unwrap();
    assert_eq!(ion.threshold_ev, 15.58);
    assert_eq!(ion.products, vec![("N2^+".to_string(), 1)]);
    let di = s.reactions.iter().find(|r| r.id.ends_with("dissociative_ionization_N2_upper")).unwrap();
    assert_eq!(di.kind, abep_icp::chemistry::ReactionKind::DissociativeIonization);
    assert!(s.contract_violations().is_empty());
    // Observation (reported, not corrected): the direct N -> N^2+ header (44.1354 eV) and the sequential chain
    // 14.534 + 29.60125 eV differ by 1.5e-4 eV, so the N^2+ formation energy is route-dependent (EQ-18 bookkeeping).
    let e = s.ion_formation_energies().unwrap_err();
    assert!(e.contains("N^2+"), "{e}");
}

#[test]
fn outputs_carry_provenance_and_lifecycle_labels() {
    let m = model();
    let r = m.evaluate(&capoff_case(50.0, 0.0, 30.0));
    let p = &r.provenance;
    assert_eq!(p.model_id, "NP-ICP-NEUTRALIZER");
    assert_eq!(p.model_version, "1");
    assert_eq!(p.prereg_lock_sha256, PREREG_LOCK_SHA256);
    assert_eq!(p.contract_id, "NP-ICP-NEUTRALIZER/prereg_v1+addendum_01_a9_30");
    assert_eq!(p.data_files_sha256.len(), m.files_read.len());
    assert_eq!(p.chem_registry["icp_chem_pinned_sha256"], ICP_CHEM_PINNED);
    assert_eq!(p.chem_registry["contract_lock_sha256"], CHEM_AIR_LOCK_SHA256);
    assert_eq!(p.chem_registry["air_label"], "abep-icp-air-0.0");
    assert_eq!(p.chem_registry["xe_label"], "abep-icp-xe-0.0");
    assert!(p.input_sha256.contains_key("case"));
    assert_eq!(r.verification_status, "IMPLEMENTED_UNVERIFIED");
    assert_eq!(r.validation_status, "NOT_VALIDATED");
    assert_eq!(r.if_icp_hall_v1.validation_status, "NOT_VALIDATED");
    assert!(r.flags.contains("MAXWELLIAN_ASSUMED"));
    assert!(r.verify_items_on_path.contains("VER-01"));
    let u = &r.if_icp_hall_v1.uncertainty;
    assert!(u["nominal"].value.is_some());
    for k in ["p2_5", "p97_5", "min", "max", "u_input", "u_model_form"] {
        assert!(u[k].value.is_none(), "{k}");
    }
}
