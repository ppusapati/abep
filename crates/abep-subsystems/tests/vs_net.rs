//! VS-NET v1 cases: registration (sha256), AL-05, AL-06, AL-10 and the determinism checks DET-01..DET-03.

mod support;

use abep_provenance::{sha256_hex, workspace_repo_root};
use serde_json::Value;
use support::{verify, vs_net};

const REGISTRATION: &str =
    "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/verification/vs_net_registration_v1.json";

#[test]
fn vs_net_file_is_the_registered_builder_output() {
    let root = workspace_repo_root().unwrap();
    let bytes = std::fs::read(root.join(vs_net::VS_NET_REL_PATH)).unwrap();
    let reg: Value = serde_json::from_slice(&std::fs::read(root.join(REGISTRATION)).unwrap()).unwrap();
    assert_eq!(reg["vs_net_sha256"].as_str().unwrap(), sha256_hex(&bytes), "VS-NET differs from its registration");
    assert_eq!(reg["evidence_class"], "SYNTHETIC_TEST_DATA_NOT_EVIDENCE");
    assert_eq!(bytes, vs_net::to_bytes(&vs_net::build()), "the builder no longer reproduces the registered VS-NET");
    let c = vs_net::load_registered();
    assert!(c.records.iter().all(|r| r.evidence_class.as_deref() == Some(support::SYN)));
    for n in abep_subsystems::thermal::vocab::NODES.iter() {
        assert!(c.nodes.iter().any(|x| x.id == n.id), "{} missing from VS-NET", n.id);
    }
}

#[test]
fn al_05_and_al_06_zero_load_equilibrium_and_step_load_energy() {
    let (al05, tau_max) = verify::al_05();
    assert!(al05.met, "{al05:#?}");
    assert!(tau_max.is_finite() && tau_max > 0.0);
    let al06 = verify::al_06(tau_max);
    assert!(al06.met, "{al06:#?}");
}

#[test]
fn al_10_interface_bookkeeping_and_refusals() {
    let ch = verify::al_10();
    assert!(ch.met, "{ch:#?}");
}

#[test]
fn det_01_02_03_determinism_and_provenance() {
    let (d1, d2, d3) = verify::det(&verify::det_cases());
    for ch in [d1, d2, d3] {
        assert!(ch.met, "{ch:#?}");
    }
}
