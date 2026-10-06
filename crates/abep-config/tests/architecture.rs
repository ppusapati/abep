//! The active-architecture invariant: flight hollow cathode NONE, C1 ground test / reference only, the architecture
//! hash pin, and the refusal of every hollow-cathode / C1 marker in a flight configuration.

mod common;

use abep_config::architecture::*;
use abep_config::ConfigPaths;
use abep_types::pydict;
use abep_types::pyjson::Value;
use abep_types::EvalStatus;

fn def() -> ArchitectureDefinition {
    ArchitectureDefinition::load(&ConfigPaths::repository(&common::repo())).expect("definition loads")
}

fn field<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.as_dict().unwrap().get(k).unwrap()
}

#[test]
fn flight_hollow_cathode_is_none_and_c1_is_ground_only() {
    let d = def();
    assert_eq!(d.flight_configuration, "hall_icp_neutralizer");
    assert_eq!(field(&d.flight_architecture, "conventional_hollow_cathode"), &Value::str("NONE"));
    assert_eq!(field(&d.c1_role, "status"), &Value::str("GROUND_ONLY_LAB_EQUIPMENT"));
    let e = d.require_flight_configuration("hall_c1_reference").unwrap_err();
    assert_eq!((e.class, e.status()), ("ArchitectureRuleError", EvalStatus::ModelError));
    assert!(e.message.starts_with("REFUSED: hall_c1_reference is not a flight configuration"));
    let e = d.require_flight_configuration("hall_icp").unwrap_err();
    assert_eq!(e.message, "unknown configuration 'hall_icp'; flight configurations ('hall_icp_neutralizer',)");
    let g = d.ground_reference("hall_c1_reference", &Value::str("  C1-vs-ICP bench control ")).unwrap();
    assert_eq!(field(&g, "label"), &Value::str("GROUND_REFERENCE"));
    assert_eq!(field(&g, "flight_candidate"), &Value::Bool(false));
    assert_eq!(field(&g, "in_flight_budgets"), &Value::Bool(false));
    assert_eq!(field(&g, "purpose"), &Value::str("C1-vs-ICP bench control"));
    assert!(d.ground_reference("hall_c1_reference", &Value::str("\u{1c} ")).is_err());
    assert!(d.ground_reference("hall_icp_neutralizer", &Value::str("x")).is_err());
}

#[test]
fn hollow_cathode_markers_are_refused_in_flight() {
    let d = def();
    let clean =
        vec![Value::str("icp_rf_source"), pydict! { "id" => "AL-07", "name" => "Hall PPU", "kind" => "mass_line" }];
    let rec = d.refuse_hollow_cathode_elements("hall_icp_neutralizer", &clean).unwrap();
    assert_eq!(field(&rec, "check"), &Value::str(CHECK_CLEAN));
    for bad in [
        Value::str("c1_heater"),
        Value::str("c1_keeper"),
        Value::str("AL-C1"),
        Value::str("hollow cathode"),
        Value::str("LaB6 emitter"),
        pydict! { "id" => "X", "name" => "C1" },
        pydict! { "id" => "C-1" },
        Value::str("cathode_heater"),
        Value::str("C1 Xe branch"),
        pydict! { "id" => "X", "name" => "C1 heater", "kind" => "mass_line", "booking" => C1_DECLARED_ABSENT },
    ] {
        let mut els = clean.clone();
        els.push(bad.clone());
        let e = d.refuse_hollow_cathode_elements("hall_icp_neutralizer", &els).unwrap_err();
        assert!(e.message.starts_with("REFUSED: hollow-cathode element(s) ["), "{bad:?}: {}", e.message);
    }
    let flagged = pydict! {
        "kind" => "mass_line", "id" => "AL-07", "name" => "Hall PPU (C1 heater/keeper electronics if C1 selected)",
        "booking" => C1_BOOKING_CONDITIONAL,
    };
    let rec = d.refuse_hollow_cathode_elements("hall_icp_neutralizer", &[flagged]).unwrap();
    assert_eq!(field(&rec, "check"), &Value::str(CHECK_FLAGGED));
    let absent = pydict! {
        "kind" => "mass_line", "id" => "AL-07", "name" => "No C1 electronics - C1 is ground-only", "booking" => C1_DECLARED_ABSENT,
    };
    let rec = d.refuse_hollow_cathode_elements("hall_icp_neutralizer", &[absent]).unwrap();
    assert_eq!(field(&rec, "check"), &Value::str(CHECK_CLEAN));
    assert_eq!(field(&rec, "c1_absence_statements").as_list().unwrap().len(), 1);
    assert!(d.refuse_hollow_cathode_elements("hall_c1_reference", &[]).is_err());
}

#[test]
fn decision_records_verify_on_the_repository() {
    let d = def();
    let v = d.verify_decision_records(&common::repo()).unwrap();
    for k in ["A9.19", "A9.20", "A9.15"] {
        assert_eq!(field(&v, k), &Value::Bool(true), "{k}");
    }
}

#[test]
fn architecture_hash_pin_refuses_a_changed_definition_even_with_a_refreshed_manifest() {
    let cfg = common::config_copy("archpin");
    let arch = cfg.join("architecture/hall_icp_neutralizer_v1.json");
    let b = std::fs::read(&arch).unwrap();
    std::fs::write(&arch, [&b[..b.len() - 1], b" \n"].concat()).unwrap();
    common::remanifest(&cfg);
    let p = ConfigPaths::with_config_root(&common::repo(), &cfg);
    assert!(abep_config::loaders::load_architecture(&p).is_ok(), "the manifest-only loader accepts it");
    let e = ArchitectureDefinition::load(&p).unwrap_err();
    let got = abep_provenance::sha256_file(&arch).unwrap();
    assert_eq!(
        e.message,
        format!(
            "config/architecture/hall_icp_neutralizer_v1.json sha256 {got} != pinned {ARCHITECTURE_SHA256} (A9.29 \
             architecture hash pin: a changed architecture needs a new architecture version and pin)"
        )
    );
    assert_eq!(e.status(), EvalStatus::ModelError);
}
