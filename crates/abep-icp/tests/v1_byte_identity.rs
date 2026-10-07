//! The admitted-path guard of the model_version 2 work: every v1 result is byte-identical to the result the v1
//! implementation gave at base 1c9e87f (sha256 of the deterministic JSON, NV-01), so model_version 2 changed nothing on
//! the v1 path.

mod common;

use abep_icp::testkit::*;
use abep_provenance::sha256_hex;
use common::model;

fn cases() -> Vec<(&'static str, abep_icp::IcpCase)> {
    let exc = with_excitation(x_set(x_rate()));
    let dbl = with_double_ion(x_set(x_rate()));
    vec![
        ("floating_7W", floating_case(7.0)),
        ("capoff_20W", capoff_case(20.0, 0.0, 30.0)),
        ("capoff_excitation", synthetic_case("SYN_EXC", exc, capoff_surfaces(), &[("ic", 0.0), ("ec", 30.0)], 20.0)),
        ("double_ion", synthetic_case("SYN_DI", dbl, floating_surfaces(), &[], 20.0)),
        ("flow", flow_case(20.0, 1e-8, 0.5)),
        ("not_sustained", capoff_case(0.0, 0.0, 30.0)),
    ]
}

/// sha256 of `IcpResult::to_json()` at base 1c9e87f (v1 implementation e404c15 lineage).
const PINNED: [(&str, &str); 6] = [
    ("floating_7W", "9f1ac67dff9bd644ad57e597ca749823bb1449b90f99ca3cf875e52eafe06a14"),
    ("capoff_20W", "7a711b4a5781a278b7ec461291dbac6e3defef3fc19ab862a1a396eb1350a726"),
    ("capoff_excitation", "5c7bd3bd97be0e3c60f3e72edf7379c2a228b728058d6bdc8399c174ce18cb1f"),
    ("double_ion", "5d1bd0b4bcdc948b8a41d5b161bd5f683cce206e2ba71c25189dc93d4fb7f0e4"),
    ("flow", "9bb070bba755c74b3354fd9f9360a0060c3257fff403b510fec510bd57dd1811"),
    ("not_sustained", "ba104a37173c0232f656be879134e0b4cc9f457d159c5513b4c5f350dc68ba53"),
];

#[test]
fn v1_results_are_byte_identical_to_base() {
    let m = model();
    let mut got = Vec::new();
    for (id, c) in cases() {
        got.push((id, sha256_hex(m.evaluate(&c).to_json().as_bytes())));
    }
    for ((id, h), (pid, ph)) in got.iter().zip(PINNED) {
        assert_eq!(*id, pid);
        assert_eq!(h, ph, "{id}: v1 result changed");
    }
}
