//! The configuration loaders on the repository tree, their fail-closed refusals, and the A9.22 / A9.23 separation:
//! the physics seam reads the operating scenario only; requirement thresholds are assessment data.

mod common;

use abep_config::assessment::{assessment_configuration, load_requirements_snapshot};
use abep_config::loaders::*;
use abep_config::{ConfigPaths, ScenarioPin};
use abep_types::pyjson::{loads, Value};
use abep_types::EvalStatus;

fn f(v: &Value, k: &str) -> Value {
    v.as_dict().unwrap().get(k).unwrap().clone()
}

#[test]
fn reference_tree_values() {
    let p = ConfigPaths::repository(&common::repo());
    let oi = load_operating_inputs(&p).unwrap();
    for (k, want) in [
        ("mission_hours", 26280.0),
        ("historical_mission_hours", 26000.0),
        ("firing_hours", 15000.0),
        ("thrust_min_mN", 12.0),
        ("thrust_max_mN", 25.0),
        ("P_bus_max_W", 1500.0),
    ] {
        assert_eq!(f(&oi, k), Value::Float(want), "{k}");
    }
    assert_eq!(f(&oi, "source"), Value::str("config/mission/mission_scenario_v2.json"));
    let typed = OperatingInputs::load(&p).unwrap();
    assert_eq!((typed.mission_hours, typed.firing_hours_label.as_str()), (26280.0, "SUBSYSTEM_FIRING_LIFE_ASSUMPTION"));

    let ec = load_engineering_constraints(&p).unwrap();
    assert_eq!(f(&ec, "mass_max_kg"), Value::Float(40.0));
    assert_eq!(f(&ec, "alt_min_km"), Value::Float(180.0));
    assert_eq!(f(&ec, "intake_drag_generation_limit_mN"), Value::Float(25.0));

    let g = load_gate_thresholds(&p).unwrap();
    let limits = f(&g, "limits");
    assert_eq!(f(&limits, "HC-07"), Value::Float(15000.0));
    assert_eq!(f(&limits, "HC-09"), Value::Float(0.025));
    assert_eq!(f(&limits, "HC-12"), Value::Null, "HC-12 TBD: no value, evaluated NOT_EVALUATED by assessment");

    assert!(model_set_drift(&p).unwrap().is_empty());
    let sc = physics_configuration(&p).unwrap();
    assert_eq!(sc.architecture_sha256, Value::str("7ab04af49340bf24be316fe7cd83eca20f2aeb692b00a43c02fa44043a5825f3"));
    assert_eq!(
        sc.design_state_set_sha256,
        Value::str("60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049")
    );
    assert_eq!(sc.requirements_snapshot_id, Value::Null);
    let ac = assessment_configuration(&p).unwrap();
    assert_eq!(ac.requirements_snapshot_id, Value::str("rfp_constraints_v1"));
    assert_eq!(load_requirements_snapshot(&p).map(|_| ()), Ok(()));
}

#[test]
fn physics_seam_reads_the_operating_scenario_only() {
    let cfg = common::config_copy("seam");
    for rel in [REQUIREMENTS_REL, CONSTRAINTS_REL, GATE_THRESHOLDS_REL] {
        std::fs::remove_file(cfg.join(rel)).unwrap();
    }
    let p = ConfigPaths::with_config_root(&common::repo(), &cfg);
    assert!(load_operating_inputs(&p).is_ok());
    let e = load_gate_thresholds(&p).unwrap_err();
    assert_eq!(e.class, "ConfigurationError");
    assert_eq!(
        e.message,
        format!("config/{GATE_THRESHOLDS_REL} missing (listed in config/MANIFEST.json; no fallback)")
    );

    let cfg = common::config_copy("seam2");
    std::fs::remove_file(cfg.join(REQUIREMENTS_REL)).unwrap();
    let p = ConfigPaths::with_config_root(&common::repo(), &cfg);
    assert!(physics_configuration(&p).is_ok(), "raw physics never opens the requirements snapshot");
    assert_eq!(assessment_configuration(&p).unwrap_err().class, "ConfigurationError");
}

#[test]
fn hash_mismatch_unpinned_and_missing_files_are_refused() {
    let cfg = common::config_copy("refuse");
    let p = ConfigPaths::with_config_root(&common::repo(), &cfg);
    let e = load_verified("requirements/other.json", &p).unwrap_err();
    assert_eq!(e.message, "config/requirements/other.json is not listed in config/MANIFEST.json");
    let arch = cfg.join(ARCHITECTURE_REL);
    let b = std::fs::read(&arch).unwrap();
    std::fs::write(&arch, [&b[..b.len() - 1], b" \n"].concat()).unwrap();
    let e = load_architecture(&p).unwrap_err();
    assert_eq!((e.class, e.status()), ("ConfigurationError", EvalStatus::ModelError));
    assert!(
        e.message.contains(" != MANIFEST 7ab04af4") && e.message.contains("an edited configuration file is refused")
    );
    let abep: abep_types::AbepError = e.into();
    assert_eq!(abep.status(), EvalStatus::ModelError);

    std::fs::remove_file(cfg.join(MANIFEST_REL)).unwrap();
    let e = load_model_set(&p).unwrap_err();
    assert_eq!(
        e.message,
        format!(
            "{}/MANIFEST.json missing: the configuration manifest is required (no fallback); build it with python \
             scripts/config/build_config.py",
            cfg.display()
        )
    );
}

#[test]
fn operating_scenario_pin_is_enforced_even_with_a_refreshed_manifest() {
    let cfg = common::config_copy("pin");
    let ms = cfg.join(MISSION_REL);
    let mut d = loads(&std::fs::read_to_string(&ms).unwrap()).unwrap();
    if let Value::Dict(dd) = &mut d {
        if let Some(Value::Dict(inp)) = dd.get_mut("inputs") {
            if let Some(Value::Dict(mh)) = inp.get_mut("mission_hours") {
                mh.insert("g1_status", Value::str("PENDING"));
            }
        }
    }
    std::fs::write(&ms, abep_types::pyjson::dumps_config_file(&d).unwrap()).unwrap();
    common::remanifest(&cfg);
    let mut p = ConfigPaths::with_config_root(&common::repo(), &cfg);
    let e = load_operating_inputs(&p).unwrap_err();
    assert!(e.message.contains("does not match its pin {'id': 'mission_scenario_v2', 'scenario_version': 2,"));
    p.scenario_pin =
        ScenarioPin { sha256: abep_provenance::sha256_file(&ms).unwrap(), ..ScenarioPin::mission_scenario_v2() };
    let e = load_operating_inputs(&p).unwrap_err();
    assert_eq!(
        e.message,
        "mission_scenario.inputs.mission_hours: A9.22 G1 not recorded as APPLIED (label 'MISSION_DURATION_BASIS')"
    );
}

#[test]
fn gate_threshold_schema_violations_are_refused() {
    let cfg = common::config_copy("gates");
    let g = cfg.join(GATE_THRESHOLDS_REL);
    let mut d = loads(&std::fs::read_to_string(&g).unwrap()).unwrap();
    if let Value::Dict(dd) = &mut d {
        if let Some(Value::Dict(gates)) = dd.get_mut("gates") {
            if let Some(Value::Dict(hc12)) = gates.get_mut("HC-12") {
                hc12.insert("value", Value::Float(1.0));
            }
        }
    }
    std::fs::write(&g, abep_types::pyjson::dumps_config_file(&d).unwrap()).unwrap();
    common::remanifest(&cfg);
    let p = ConfigPaths::with_config_root(&common::repo(), &cfg);
    let e = load_gate_thresholds(&p).unwrap_err();
    assert_eq!(e.message, "gate_thresholds.gates.HC-12: a TBD threshold carries no value (no default is invented)");
}

#[test]
fn config_root_from_the_environment_value() {
    let repo = common::repo();
    assert_eq!(ConfigPaths::from_env_value(&repo, Some("")).config_root, repo.join("config"));
    assert_eq!(ConfigPaths::from_env_value(&repo, None).config_root, repo.join("config"));
    assert_eq!(ConfigPaths::from_env_value(&repo, Some("/x/cfg")).config_root, std::path::PathBuf::from("/x/cfg"));
}
