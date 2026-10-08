//! NP-HALL-PARAMETRIC-ENVELOPE prereg addendum A1 (AIR family): the case file reproduces from Rust, every case is a v1
//! N2_PROXY row with a registered composition and feed, the bridge reads what the cases carry, LP-COMPLETE is closed while
//! the AIR reaction set is not admitted, and LP-BOUNDED opens only for the registered BV-AIR-LL-NOM pins, with the label on
//! the manifest (asserted, never skipped). No test spawns Julia.

use abep_julia_bridge::air_cases::{
    air_launch_manifest, check_air, check_bounded_variant, v1_n2_rows, LaunchPath, AIR_CASES_REL, AIR_CONFIG,
    AIR_LAUNCH_MANIFEST_REL, AIR_RATE_DIR, BV_BLOCKER, BV_LABEL, BV_MEMBER, BV_SET_ID, ENV_ADDENDUM_ID,
    ENV_ADDENDUM_LOCK_SHA256, V1_FIELDS,
};
use abep_julia_bridge::envelope_cases::check_rate_files;
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::{self, DumpOptions, Value};
use abep_types::EvalStatus;
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn s<'a>(v: &'a Value, k: &str) -> &'a str {
    v.as_dict().unwrap().get(k).unwrap().as_str().unwrap()
}

#[test]
fn air_case_file_reproduces_byte_for_byte() {
    assert_eq!(check_air(&repo()).unwrap(), 9072);
}

#[test]
fn every_air_case_is_a_v1_row_with_a_registered_corner_and_feed() {
    let rows: BTreeMap<String, Value> = v1_n2_rows(&repo())
        .unwrap()
        .into_iter()
        .map(|r| {
            let k = ["geometry_id", "bz_shape_id", "B_peak_id", "Vd_id", "mdot_id", "transport_id"]
                .map(|f| s(&r, f))
                .join("|");
            (k, r)
        })
        .collect();
    let doc = pyjson::loads(&std::fs::read_to_string(repo().join(AIR_CASES_REL)).unwrap()).unwrap();
    let cases = doc.as_dict().unwrap().get("cases").unwrap().as_list().unwrap();
    let mut per_row: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for c in cases {
        let d = c.as_dict().unwrap();
        assert_eq!(s(c, "family"), "AIR");
        assert_eq!(s(c, "propellant_config"), AIR_CONFIG);
        assert_eq!(s(c, "rate_dir"), AIR_RATE_DIR);
        assert!(!d.contains_key("measured") && !d.contains_key("background_pressure_Torr"), "vacuum, no target");
        let k =
            ["geometry_id", "bz_shape_id", "B_peak_id", "Vd_id", "mdot_id", "transport_id"].map(|f| s(c, f)).join("|");
        for f in V1_FIELDS {
            assert_eq!(d.get(f), rows[&k].as_dict().unwrap().get(f), "{k} {f}");
        }
        let mdot = d.get("mdot_kgps").unwrap().to_f64().unwrap();
        let sum: f64 = d
            .get("feed")
            .unwrap()
            .as_list()
            .unwrap()
            .iter()
            .map(|f| f.as_dict().unwrap().get("flow_rate_kg_s").unwrap().to_f64().unwrap())
            .sum();
        assert!((sum - mdot).abs() <= 1e-15 * mdot);
        assert!(per_row.entry(k).or_default().insert(s(c, "composition_id").to_string()));
    }
    assert_eq!(per_row.len(), 2268);
    assert!(per_row.values().all(|c| c.len() == 4), "every v1 row at every corner");
}

#[test]
fn the_air_configuration_passes_the_bridge_rate_file_guards() {
    assert_eq!(check_rate_files(&repo(), AIR_CONFIG, AIR_RATE_DIR).unwrap(), 34);
}

#[test]
fn run_case_air_reads_what_the_cases_carry() {
    let lib = std::fs::read_to_string(repo().join("hallthruster_bridge/air_bridge_lib.jl")).unwrap();
    for f in [
        "c.L_m",
        "c.r_in_m",
        "c.r_out_m",
        "c.domain_m",
        "c.Vd",
        "c.transport",
        "c.cells",
        "c.dt_s",
        "c.duration_s",
        "c.average_start_s",
        "c.feed",
        "c.propellant_config",
        "c.rate_dir",
        "c.thruster",
    ] {
        assert!(lib.contains(f), "air_bridge_lib.jl does not read {f}");
    }
    for f in ["f.species", "f.flow_rate_kg_s", "f.velocity_m_s", "f.temperature_K"] {
        assert!(lib.contains(f), "air_bridge_lib.jl does not read the feed field {f}");
    }
    let bridge = std::fs::read_to_string(repo().join("hallthruster_bridge/bridge_lib.jl")).unwrap();
    for f in ["c.B_profile", "c.B_ref_T"] {
        assert!(bridge.contains(f), "measured_bfield does not read {f}");
    }
}

#[test]
fn lp_complete_is_closed_while_the_air_set_is_not_admitted() {
    let e = air_launch_manifest(&repo(), LaunchPath::Complete).unwrap_err();
    assert_eq!(e.status(), EvalStatus::IncompleteEvidence, "{e}");
    assert!(e.to_string().contains("HA-O-EL-01"));
}

#[test]
fn the_case_file_header_names_addendum_a1() {
    let text = std::fs::read_to_string(repo().join(AIR_CASES_REL)).unwrap();
    let head = &text[..text.find("\"cases\"").unwrap()];
    assert!(head.contains(&format!("\"addendum\": \"{ENV_ADDENDUM_ID}\"")));
    assert!(head.contains(ENV_ADDENDUM_LOCK_SHA256));
}

#[test]
fn lp_bounded_opens_only_for_the_registered_bv_air_ll_nominal_member() {
    let set = abep_chem::hall_air::AirSet::load(&repo()).unwrap();
    check_bounded_variant(&repo(), &set).unwrap();
    let lm = air_launch_manifest(&repo(), LaunchPath::Bounded).unwrap();
    let d = lm.as_dict().unwrap();
    let get = |k: &str| d.get(k).unwrap().as_str().unwrap().to_string();
    assert_eq!(get("chemistry_mode"), "BOUNDED_VARIANT");
    assert_eq!(get("chemistry_bound_set"), BV_SET_ID);
    assert_eq!(get("chemistry_bound_member"), BV_MEMBER);
    assert_eq!(get("chemistry_bound_label"), BV_LABEL);
    assert_eq!(get("chemistry_bound_blocker"), BV_BLOCKER);
    assert_eq!(get("air_label"), "abep-air-0.7");
    assert_eq!(get("air_config"), AIR_CONFIG);
    // the committed manifest is exactly the LP-BOUNDED regeneration
    let mut t = pyjson::dumps(&lm, &DumpOptions::config_writer()).unwrap();
    t.push('\n');
    assert_eq!(std::fs::read_to_string(repo().join(AIR_LAUNCH_MANIFEST_REL)).unwrap(), t);
}

#[test]
fn lp_bounded_refuses_another_reaction_set_label() {
    let mut set = abep_chem::hall_air::AirSet::load(&repo()).unwrap();
    set.label = "abep-air-9.9".into();
    let e = check_bounded_variant(&repo(), &set).unwrap_err();
    assert_eq!(e.status(), EvalStatus::ModelError, "{e}");
    assert!(e.to_string().contains("BV-AIR-LL"));
}
