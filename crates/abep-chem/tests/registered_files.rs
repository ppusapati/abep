//! The readers on the real, pinned repository files: rate_validity.toml (pin of NP-ICP-NEUTRALIZER prereg_v1) and the
//! HallThruster-format tables of NP-ICP-CHEM-AIR prereg_v1 reuse_pins; the checked API against the real validity
//! limits (contract INV-06 semantics).

use abep_chem::checked::{self, CrossSection, Validity};
use abep_chem::dat::DatTable;
use abep_chem::reference::{self, Tail};
use abep_chem::validity::RateValidityTable;
use abep_provenance::workspace_repo_root;
use abep_types::{AbepError, EvalStatus};
use serde_json::Value;
use std::path::PathBuf;

const RATE_VALIDITY: &str = "hallthruster_bridge/propellants/rate_validity.toml";
const NP_ICP_PREREG: &str = "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_v1.json";
const CHEM_AIR_PREREG: &str = "docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/prereg_v1.json";

fn root() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn json(rel: &str) -> Value {
    serde_json::from_slice(&std::fs::read(root().join(rel)).unwrap()).unwrap()
}

/// The sha256 a document pins for `path` (first object with that `path`).
fn pin_of(doc: &Value, path: &str) -> Option<String> {
    match doc {
        Value::Object(m) => {
            if m.get("path").and_then(Value::as_str) == Some(path) {
                return m.get("sha256").and_then(Value::as_str).map(String::from);
            }
            m.values().find_map(|v| pin_of(v, path))
        }
        Value::Array(a) => a.iter().find_map(|v| pin_of(v, path)),
        _ => None,
    }
}

fn validity_table() -> RateValidityTable {
    let pin = pin_of(&json(NP_ICP_PREREG), RATE_VALIDITY).expect("NP-ICP-NEUTRALIZER pins rate_validity.toml");
    RateValidityTable::load(&root().join(RATE_VALIDITY), &pin).expect("pinned rate_validity.toml loads")
}

fn reuse_pins() -> Vec<(String, String)> {
    json(CHEM_AIR_PREREG)["reuse_pins"]["hall_propellant_tables"]
        .as_array()
        .unwrap()
        .iter()
        .map(|e| (e["path"].as_str().unwrap().to_string(), e["sha256"].as_str().unwrap().to_string()))
        .collect()
}

#[test]
fn every_reused_table_reads_under_its_pin_and_has_a_verified_entry() {
    let v = validity_table();
    let pins = reuse_pins();
    assert_eq!(pins.len(), 43);
    for (path, sha) in &pins {
        let t = DatTable::read_verified(&root().join(path), sha).unwrap_or_else(|e| panic!("{path}: {e}"));
        assert_eq!(t.rows.first().map(|r| r.0), Some(0.0), "{path}");
        assert!(t.rows.iter().all(|&(_, k)| k >= 0.0), "{path}");
        let file = path.rsplit('/').next().unwrap();
        assert!(matches!(v.validity(file), Validity::Verified { .. }), "{file}");
    }
}

#[test]
fn a_changed_pin_is_refused() {
    let (path, sha) = &reuse_pins()[0];
    let wrong: String = sha.chars().rev().collect();
    assert!(matches!(DatTable::read_verified(&root().join(path), &wrong), Err(AbepError::HashMismatch { .. })));
    assert!(matches!(
        RateValidityTable::load(&root().join(RATE_VALIDITY), &wrong),
        Err(AbepError::HashMismatch { .. })
    ));
}

#[test]
fn validity_limits_of_the_registered_set() {
    let v = validity_table();
    assert_eq!(v.validity("dissociation_N2.dat"), Validity::Verified { max_mean_energy_ev: 45.0 });
    assert_eq!(v.validity("ionization_N2_song2023.dat"), Validity::Verified { max_mean_energy_ev: 255.0 });
    assert_eq!(v.validity("ionization_N2_N2+.dat"), Validity::Unresolved);
    assert_eq!(v.validity("elastic_N2.dat"), Validity::Unresolved);
    assert_eq!(v.validity("no_such_table.dat"), Validity::MissingEntry);
}

#[test]
fn checked_rates_follow_the_real_validity_entries() {
    let v = validity_table();
    let xs = CrossSection::new(vec![0.0, 14.99, 15.0, 1000.0], vec![0.0, 0.0, 1e-20, 1e-20], Tail::Hold).unwrap();
    let diss = v.validity("dissociation_N2.dat");
    let k = checked::maxwellian_rate(&xs, 30.0, &diss).unwrap();
    let r = reference::maxwellian_rate(xs.energies_ev(), xs.sigma_m2(), 30.0, Tail::Hold).unwrap();
    assert_eq!(k.k_m3_s.to_bits(), r.to_bits());
    assert_eq!(checked::maxwellian_rate(&xs, 30.0f64.next_up(), &diss).unwrap_err().status(), EvalStatus::OutOfDomain);
    assert!(checked::maxwellian_rate(&xs, 170.0, &v.validity("ionization_N2_song2023.dat")).is_ok());
    assert_eq!(
        checked::maxwellian_rate(&xs, 3.0, &v.validity("elastic_N2.dat")).unwrap_err().status(),
        EvalStatus::IncompleteEvidence
    );
    assert_eq!(
        checked::maxwellian_rate(&xs, 3.0, &v.validity("no_such_table.dat")).unwrap_err().status(),
        EvalStatus::ModelError
    );
}
