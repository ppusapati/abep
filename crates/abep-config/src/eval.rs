//! `abep-config eval <calls.json>`: the harness interface of the parity contracts. Each call names an entry point and
//! its arguments; each result is `{"outcome": "RETURNED", "value": ...}` or
//! `{"outcome": "RAISED", "class": ..., "message": ...}` with Python-shaped values (`abep_types::pyjson`).

use crate::architecture::{hollow_cathode_elements, ArchitectureDefinition};
use crate::assessment::{assessment_configuration, load_requirements_snapshot};
use crate::builder::Builder;
use crate::loaders::*;
use crate::{ConfigError, ConfigPaths, ConfigResult};
use abep_types::pydict;
use abep_types::pyjson::{Dict, Value};
use std::path::Path;

fn arg<'a>(call: &'a Value, key: &str) -> ConfigResult<&'a Value> {
    call.as_dict()
        .and_then(|d| d.get(key))
        .ok_or_else(|| ConfigError::new("HarnessError", format!("call argument {key:?} missing")))
}

fn arg_str<'a>(call: &'a Value, key: &str) -> ConfigResult<&'a str> {
    arg(call, key)?.as_str().ok_or_else(|| ConfigError::new("HarnessError", format!("call argument {key:?} not a str")))
}

fn arg_bool(call: &Value, key: &str, default: bool) -> ConfigResult<bool> {
    match call.as_dict().and_then(|d| d.get(key)) {
        None | Some(Value::Null) => Ok(default),
        Some(Value::Bool(b)) => Ok(*b),
        Some(_) => Err(ConfigError::new("HarnessError", format!("call argument {key:?} not a bool"))),
    }
}

/// The paths of a call: `root` (config root) when given, else the `env` value of ABEP_CONFIG_ROOT (or the default).
fn paths_of(call: &Value) -> ConfigResult<ConfigPaths> {
    let repo = Path::new(arg_str(call, "repo")?);
    let d = call.as_dict().expect("calls are dicts");
    let mut p = match d.get("root") {
        Some(Value::Str(root)) => ConfigPaths::with_config_root(repo, Path::new(root)),
        _ => ConfigPaths::from_env_value(repo, d.get("env").and_then(Value::as_str)),
    };
    if let Some(Value::Str(sha)) = d.get("pin_sha256") {
        p.scenario_pin.sha256 = sha.clone();
    }
    Ok(p)
}

fn list(v: Vec<String>) -> Value {
    Value::List(v.into_iter().map(Value::Str).collect())
}

/// Evaluate one call.
pub fn eval_call(call: &Value) -> ConfigResult<Value> {
    let f = arg_str(call, "fn")?;
    match f {
        "build_all" | "build_check" => {
            let b = Builder::new(Path::new(arg_str(call, "repo")?));
            if f == "build_check" {
                let c = b.check()?;
                return Ok(pydict! { "exit" => c.exit as i64, "line" => c.line });
            }
            let mut out = Dict::new();
            for (k, v) in b.build_all()? {
                out.insert(k, pydict! { "sha256" => abep_provenance::sha256_hex(&v), "bytes" => v.len() as i64 });
            }
            return Ok(Value::Dict(out));
        }
        _ => {}
    }
    let p = paths_of(call)?;
    match f {
        "load_manifest" => load_manifest(&p),
        "load_verified" => load_verified(arg_str(call, "rel")?, &p),
        "load_architecture" => load_architecture(&p),
        "load_requirements_snapshot" => load_requirements_snapshot(&p),
        "load_engineering_constraints_file" => load_engineering_constraints_file(&p),
        "load_engineering_constraints" => load_engineering_constraints(&p),
        "load_mission_scenario" => load_mission_scenario(&p, arg_bool(call, "verify_constraints", true)?),
        "load_operating_inputs" => load_operating_inputs(&p),
        "load_gate_thresholds" => load_gate_thresholds(&p),
        "load_design_state_set_ref" => load_design_state_set_ref(&p, arg_bool(call, "verify_target", true)?),
        "load_hardware_bounds" => load_hardware_bounds(&p, arg_bool(call, "verify_targets", true)?),
        "load_model_set" => load_model_set(&p),
        "model_set_drift" => Ok(list(model_set_drift(&p)?)),
        "physics_configuration" => Ok(physics_configuration(&p)?.as_value()),
        "assessment_configuration" => Ok(assessment_configuration(&p)?.as_value()),
        "builder_constants" => Ok(crate::builder::constants_value()),
        "arch_definition" => Ok(ArchitectureDefinition::load(&p)?.constants_value()),
        "require_flight_configuration" => {
            Ok(Value::Str(ArchitectureDefinition::load(&p)?.require_flight_configuration(arg_str(call, "config")?)?))
        }
        "refuse_hollow_cathode_elements" => {
            let els = arg(call, "elements")?.as_list().unwrap_or_default().to_vec();
            ArchitectureDefinition::load(&p)?.refuse_hollow_cathode_elements(arg_str(call, "config")?, &els)
        }
        "hollow_cathode_elements" => {
            let els = arg(call, "elements")?.as_list().unwrap_or_default().to_vec();
            Ok(list(hollow_cathode_elements(&els)))
        }
        "ground_reference" => {
            ArchitectureDefinition::load(&p)?.ground_reference(arg_str(call, "config")?, arg(call, "purpose")?)
        }
        "verify_decision_records" => {
            ArchitectureDefinition::load(&p)?.verify_decision_records(Path::new(arg_str(call, "decision_repo")?))
        }
        other => Err(ConfigError::new("HarnessError", format!("unknown entry point {other:?}"))),
    }
}

/// Evaluate a list of calls; every call yields a result record (a refusal is a result, not a harness failure).
pub fn eval_calls(calls: &Value) -> Value {
    let empty = Vec::new();
    let calls = calls.as_list().map(|l| l.to_vec()).unwrap_or(empty);
    Value::List(
        calls
            .iter()
            .map(|c| match eval_call(c) {
                Ok(v) => pydict! { "outcome" => "RETURNED", "value" => v },
                Err(e) => pydict! { "outcome" => "RAISED", "class" => e.class, "message" => e.message },
            })
            .collect(),
    )
}
