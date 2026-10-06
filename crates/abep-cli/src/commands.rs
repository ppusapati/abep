//! The registered commands (acceptance_v2 `commands`). Each one calls the owning crate's API, keeps the crate's values and
//! statuses verbatim in its payload and summarises the command status from its registered status sources. No physics
//! is computed here.

use crate::args::Command;
use crate::output::{parse_status, worst, Outcome, Payload, Reason};
use crate::registry::{self, Component};
use abep_types::pyjson::{self, Dict, DumpOptions, Value};
use abep_types::{pydict, AbepError, EvalStatus};
use std::collections::BTreeMap;
use std::path::Path;

/// Execution context of one command.
pub struct Ctx<'a> {
    pub root: &'a Path,
    /// `--threads` value or the default (available parallelism).
    pub threads: usize,
}

/// What a command produced, plus the thread count it actually used.
pub struct Executed {
    pub outcome: Outcome,
    pub threads_used: usize,
}

fn single(outcome: Outcome) -> Executed {
    Executed { outcome, threads_used: 1 }
}

fn abep_err(e: AbepError) -> Outcome {
    Outcome::crate_error(e.status(), e.to_string())
}

fn py_payload(v: &Value) -> Result<Payload, Outcome> {
    pyjson::dumps(v, &DumpOptions::default())
        .map(Payload::python)
        .map_err(|e| Outcome::crate_error(EvalStatus::ModelError, format!("{}: {}", e.class, e.message)))
}

fn hall_payload(v: &abep_hall::py::PyValue) -> Payload {
    Payload::python(abep_hall::py::dumps(v, &abep_hall::py::Dump::DEFAULT))
}

/// The components a command uses, in registered order.
pub fn components(c: &Command) -> &'static [Component] {
    use registry::*;
    match c {
        Command::ConfigCheck => &[CONFIGURATION, ARCHITECTURE],
        Command::ProvenanceVerify => &[PROVENANCE_VERIFIER],
        Command::EnvRunDesignStates => &[ATMOSPHERE_ORBIT],
        Command::IntakeSurfaceV1 { .. } => &[INTAKE_TPMC, ATMOSPHERE, ATMOSPHERE_ORBIT],
        Command::DragStatewise { .. } => &[DRAG_KERNEL, ATMOSPHERE, ATMOSPHERE_ORBIT],
        Command::MassRollup => &[MASS_RULES, MASS_POWER_V5],
        Command::PowerLedger => &[BUS_BOUNDARY],
        Command::HallStatus => &[HALL_REGISTRY],
        Command::HallPinCheck => &[JULIA_BRIDGE],
        Command::IcpStatus { .. } => &[ICP],
    }
}

/// The two flight supply modes (CLAUDE.md: AIR_PRIMARY and XE_CONTINGENCY).
pub const ICP_SUPPLY_MODES: [&str; 2] = ["AIR_PRIMARY", "XE_CONTINGENCY"];

/// Pipeline S-6: inputs outside their registered vocabularies. `Ok(Err(msg))` is UNREGISTERED_INPUT; `Err` is a
/// crate error while reading the vocabulary.
pub fn check_registered(root: &Path, c: &Command) -> Result<Result<(), String>, Outcome> {
    match c {
        Command::IntakeSurfaceV1 { state, .. } => {
            let set = design_state_set(root).map_err(abep_err)?;
            Ok(if set.states.iter().any(|s| &s.state_id == state) {
                Ok(())
            } else {
                Err(format!(
                    "--state {state:?} is not a state of the frozen design-state set {}",
                    abep_data::design_states::DESIGN_STATE_SET_ID
                ))
            })
        }
        Command::IcpStatus { supply_mode } => Ok(if ICP_SUPPLY_MODES.contains(&supply_mode.as_str()) {
            Ok(())
        } else {
            Err(format!("--supply-mode {supply_mode:?} is not a flight supply mode {ICP_SUPPLY_MODES:?}"))
        }),
        _ => Ok(Ok(())),
    }
}

fn design_state_set(root: &Path) -> Result<abep_data::design_states::DesignStateSet, AbepError> {
    let pins = abep_data::pins::FrozenPins::load(root)?;
    abep_data::design_states::DesignStateSet::load(root, &pins)
}

/// Pipeline S-8.
pub fn execute(ctx: &Ctx, c: &Command) -> Executed {
    match c {
        Command::ConfigCheck => single(config_check(ctx.root)),
        Command::ProvenanceVerify => single(provenance_verify(ctx.root)),
        Command::EnvRunDesignStates => env_run(ctx.root, ctx.threads),
        Command::IntakeSurfaceV1 { state, scattering, l_over_d, phi, alpha, theta_deg } => {
            single(intake_surface_v1(ctx.root, state, scattering, [*l_over_d, *phi, *alpha, *theta_deg]))
        }
        Command::DragStatewise { area_m2, l_over_d, phi, scenario } => {
            single(drag_statewise(ctx.root, *area_m2, *l_over_d, *phi, scenario))
        }
        Command::MassRollup => single(mass_rollup(ctx.root)),
        Command::PowerLedger => single(power_ledger(ctx.root)),
        Command::HallStatus => single(hall_status(ctx.root)),
        Command::HallPinCheck => single(hall_pin_check(ctx.root)),
        Command::IcpStatus { supply_mode } => single(icp_status(ctx.root, supply_mode)),
    }
}

// ------------------------------------------------------------------------------------------------ config check

fn config_check(root: &Path) -> Outcome {
    use abep_config::{architecture::ArchitectureDefinition, builder::Builder, loaders, ConfigPaths};
    let cfg_err = |e: abep_config::ConfigError| Outcome::crate_error(e.status(), e.to_string());
    let check = match Builder::new(root).check() {
        Ok(c) => c,
        Err(e) => return cfg_err(e),
    };
    let verified = match abep_provenance::ConfigManifest::load(root).and_then(|m| m.verify_all(root)) {
        Ok(n) => n,
        Err(e) => return abep_err(e),
    };
    // The CLI always reads <repo>/config: ABEP_CONFIG_ROOT is not consulted.
    let paths = ConfigPaths::repository(root);
    let physics = match loaders::physics_configuration(&paths) {
        Ok(p) => p,
        Err(e) => return cfg_err(e),
    };
    if let Err(e) = ArchitectureDefinition::load(&paths) {
        return cfg_err(e);
    }
    let arch_id = match loaders::load_architecture(&paths) {
        Ok(a) => a.as_dict().and_then(|d| d.get("id")).cloned().unwrap_or(Value::Null),
        Err(e) => return cfg_err(e),
    };
    let payload = pydict! {
        "build_check" => pydict! { "exit" => Value::int(check.exit as i64), "line" => check.line.as_str() },
        "manifest_files_verified" => Value::int(verified as i64),
        "physics_configuration" => physics.as_value(),
        "architecture" => pydict! {
            "id" => arch_id,
            "sha256" => abep_config::architecture::ARCHITECTURE_SHA256,
        },
    };
    let payload = match py_payload(&payload) {
        Ok(p) => p,
        Err(o) => return o,
    };
    if check.exit == 0 {
        Outcome::evaluated(payload)
    } else {
        Outcome::status(EvalStatus::ModelError, Some(Reason::new("CONFIG_BUILD_STALE", check.line)), Some(payload))
    }
}

// ------------------------------------------------------------------------------------------------ provenance verify

#[derive(serde::Serialize)]
struct Checks<'a> {
    checks: &'a [abep_provenance::verifier::CheckReport],
}

fn provenance_verify(root: &Path) -> Outcome {
    use abep_provenance::verifier::{run_checks, CheckName};
    let reports = run_checks(root, &CheckName::ALL);
    let payload = match Payload::serde(&Checks { checks: &reports }) {
        Ok(p) => p,
        Err(e) => return Outcome::crate_error(EvalStatus::ModelError, e),
    };
    let failed: Vec<String> = reports.iter().filter(|r| !r.verified()).map(|r| r.check.as_str().to_string()).collect();
    Outcome::summarised(
        worst(reports.iter().map(|r| r.status)),
        "CRATE_STATUS",
        format!("provenance checks with findings: {}", failed.join(", ")),
        payload,
    )
}

// ------------------------------------------------------------------------------------------------ env

/// The 196-state execution. One thread: `abep_atmos::execution::run`. N threads: contiguous chunks of the required
/// states through `execute_states`, concatenated in file order with the global index restored, under the header
/// `run` builds. The bytes do not depend on N.
pub fn env_design_state_run(
    root: &Path,
    threads: usize,
) -> Result<(abep_atmos::execution::DesignStateRun, usize), AbepError> {
    use abep_atmos::execution::{execute_states, run, DesignStateRun, Environment};
    let env = Environment::load(root)?;
    if threads <= 1 {
        return Ok((run(&env)?, 1));
    }
    let states = abep_atmos::design_state_set::required_states(&env.set)?;
    let chunk = states.len().div_ceil(threads).max(1);
    let mut records = Vec::with_capacity(states.len());
    let mut used = 0;
    let joined: Vec<std::thread::Result<Vec<_>>> = std::thread::scope(|s| {
        let env = &env;
        let handles: Vec<_> = states
            .chunks(chunk)
            .enumerate()
            .map(|(ci, ch)| {
                s.spawn(move || {
                    let mut v = execute_states(env, ch);
                    for r in &mut v {
                        r.index += ci * chunk;
                    }
                    v
                })
            })
            .collect();
        handles.into_iter().map(|h| h.join()).collect()
    });
    for part in joined {
        used += 1;
        records.extend(part.map_err(|_| AbepError::Model { message: "a design-state worker thread panicked".into() })?);
    }
    let count = |st: EvalStatus| records.iter().filter(|r| r.status == st).count();
    let out = DesignStateRun {
        design_state_set_id: abep_data::design_states::DESIGN_STATE_SET_ID,
        design_state_set_sha256: env.set.sha256.clone(),
        dataset_sha256: env.orbit.data.meta.sha256.clone(),
        wind_dataset_sha256: env.wind.data.sha256.clone(),
        wind_disturbance_sha256: env.wind.data.disturbance_sha256.clone(),
        config_manifest_sha256: env.orbit.pins.config_manifest_sha256.clone(),
        model_set_sha256: env.orbit.pins.model_set_sha256.clone(),
        n_states: env.set.n_states,
        n_evaluated: count(EvalStatus::Evaluated),
        n_out_of_domain: count(EvalStatus::OutOfDomain),
        n_model_error: count(EvalStatus::ModelError),
        records,
    };
    Ok((out, used))
}

fn env_run(root: &Path, threads: usize) -> Executed {
    match env_design_state_run(root, threads) {
        Err(e) => single(abep_err(e)),
        Ok((run, used)) => {
            let outcome = match Payload::serde(&run) {
                Err(e) => Outcome::crate_error(EvalStatus::ModelError, e),
                Ok(p) => Outcome::summarised(
                    worst(run.records.iter().map(|r| r.status)),
                    "CRATE_STATUS",
                    format!(
                        "{} of {} states evaluated ({} OUT_OF_DOMAIN, {} MODEL_ERROR)",
                        run.n_evaluated, run.n_states, run.n_out_of_domain, run.n_model_error
                    ),
                    p,
                ),
            };
            Executed { outcome, threads_used: used }
        }
    }
}

// ------------------------------------------------------------------------------------------------ intake

fn intake_surface_v1(root: &Path, state: &str, scattering: &str, x: [f64; 4]) -> Outcome {
    use abep_atmos::msis21::{atmosphere, Msis21Frozen, Solar};
    use abep_intake::surface::{surface_v2_gate, FrozenIntakeSurfaces};
    let r = (|| -> Result<Value, AbepError> {
        let set = design_state_set(root)?;
        let rec =
            set.states.iter().find(|s| s.state_id == state).ok_or_else(|| AbepError::Model {
                message: format!("state {state} vanished from the design-state set"),
            })?;
        let atm = abep_atmos::design_state_set::DesignState::from_record(rec).atm()?;
        let fractions: BTreeMap<String, f64> =
            [("N2".to_string(), atm.fN2), ("O".to_string(), atm.fO), ("O2".to_string(), atm.fO2)].into_iter().collect();
        // The frozen surface v1 build state (reference intake_tpmc.frozen_surface_build_atmosphere: 200 km, 'mean').
        let build = atmosphere(&Msis21Frozen::load(root)?, 200.0, Solar::Label("mean".into()))?;
        let surfaces = FrozenIntakeSurfaces::load(root, build.m_mean)?;
        let surface = surfaces.get(scattering)?;
        let e = surface.eval(x[0], x[1], x[2], x[3], Some(&fractions))?;
        let mut species = Dict::new();
        for (name, s) in &e.species {
            species.insert(
                name.as_str(),
                pydict! {
                    "eta_c" => s.eta_c,
                    "c_d_row" => s.c_d_row,
                    "c_d_species" => s.c_d_species,
                    "cr_passive" => s.cr_passive,
                    "k_back" => s.k_back,
                    "mass_fraction" => s.mass_fraction,
                    "mole_fraction" => s.mole_fraction,
                    "collected_mass_fraction" => s.collected_mass_fraction,
                    "collected_mole_fraction" => s.collected_mole_fraction,
                },
            );
        }
        let mut fr = Dict::new();
        for (k, v) in &fractions {
            fr.insert(k.as_str(), Value::Float(*v));
        }
        let gate = surface_v2_gate();
        Ok(pydict! {
            "state_id" => state,
            "mass_fractions" => Value::Dict(fr),
            "m_mean_build_kg" => build.m_mean,
            "surface_v1" => pydict! {
                "scattering" => surface.scattering(),
                "eta_c" => e.eta_c,
                "c_d" => e.c_d,
                "k_back" => e.k_back,
                "mass_kg" => e.mass_kg,
                "cr_passive" => e.cr_passive,
                "recombination" => e.recombination,
                "species" => Value::Dict(species),
            },
            "surface_v2_gate" => pydict! {
                "status" => gate.status.as_str(),
                "label" => gate.label,
                "primary_blocker" => gate.primary_blocker,
                "unregistered" => Value::List(gate.unregistered.iter().map(|s| Value::str(*s)).collect()),
            },
        })
    })();
    match r {
        Err(e) => abep_err(e),
        Ok(v) => match py_payload(&v) {
            Ok(p) => Outcome::evaluated(p),
            Err(o) => o,
        },
    }
}

// ------------------------------------------------------------------------------------------------ drag

fn term(status: EvalStatus, reason_key: &str, reason: &str) -> Value {
    pydict! { "status" => status.as_str(), "reason_key" => reason_key, "reason" => reason }
}

fn drag_statewise(root: &Path, area_m2: f64, l_over_d: f64, phi: f64, scenario: &str) -> Outcome {
    use abep_mission::intake_drag::load_drag_table;
    use abep_mission::objective::HallResponseStatus;
    use abep_mission::statewise_td::{statewise_t_minus_d, DesignPoint};
    let r = (|| -> Result<abep_mission::statewise_td::StatewiseTMinusD, AbepError> {
        let (table, atm) = load_drag_table(root)?;
        let hall = HallResponseStatus::load(root)?;
        let point = DesignPoint { area_m2, l_over_d, phi, scenario: scenario.to_string() };
        statewise_t_minus_d(&table, &hall, &point, &atm.required_ids)
    })();
    let rec = match r {
        Ok(rec) => rec,
        Err(e) => return abep_err(e),
    };
    let states: Vec<Value> = rec
        .states
        .iter()
        .map(|s| {
            pydict! {
                "state_id" => s.state_id.as_str(),
                "thrust" => term(s.thrust.status, s.thrust.reason_key, &s.thrust.reason),
                "drag_intake" => pydict! {
                    "value_n" => s.drag_intake.value_n,
                    "se_n" => s.drag_intake.se_n,
                    "status" => s.drag_intake.status.as_str(),
                    "label" => s.drag_intake.label,
                    "source" => s.drag_intake.source.as_str(),
                },
                "drag_body" => term(s.drag_body.status, s.drag_body.reason_key, &s.drag_body.reason),
                "t_minus_d_status" => s.t_minus_d_status.as_str(),
                "objective" => s.objective.clone(),
            }
        })
        .collect();
    let p = &rec.design_point;
    let v = pydict! {
        "design_point" => pydict! {
            "area_m2" => p.area_m2, "l_over_d" => p.l_over_d, "phi" => p.phi, "scenario" => p.scenario.as_str(),
        },
        "credible_set" => rec.credible_set,
        "n_states" => Value::int(rec.n_states as i64),
        "n_t_minus_d_evaluated" => Value::int(rec.n_t_minus_d_evaluated as i64),
        "states" => Value::List(states),
    };
    match py_payload(&v) {
        Err(o) => o,
        Ok(payload) => Outcome::summarised(
            worst(rec.states.iter().map(|s| s.t_minus_d_status)),
            "CRATE_STATUS",
            format!(
                "T - D evaluated at {} of {} states (credible Hall transport set {})",
                rec.n_t_minus_d_evaluated, rec.n_states, rec.credible_set
            ),
            payload,
        ),
    }
}

// ------------------------------------------------------------------------------------------------ mass

fn mass_rollup(root: &Path) -> Outcome {
    use abep_subsystems::mass::{py::refusal_status, v5};
    let py_err =
        |e: pyjson::PyException| Outcome::crate_error(refusal_status(&e), format!("{}: {}", e.class, e.message));
    let r = (|| -> Result<(Vec<&'static str>, Value, Value, Value), pyjson::PyException> {
        let stale = v5::check(root)?;
        let doc = v5::build_doc(root)?;
        let gates = v5::mass_gates(root, &v5::MissionXeLoad::NotAdmitted)?;
        let al07 = v5::al07_value_status(root)?;
        Ok((stale, doc, gates, al07))
    })();
    let (stale, doc, gates, al07) = match r {
        Ok(x) => x,
        Err(e) => return py_err(e),
    };
    let field = |k: &str| doc.as_dict().and_then(|d| d.get(k)).cloned().unwrap_or(Value::Null);
    let mut statuses = Vec::new();
    for g in gates.as_list().unwrap_or(&[]) {
        let st = g.as_dict().and_then(|d| d.get("status")).and_then(Value::as_str).and_then(parse_status);
        match st {
            Some(s) => statuses.push(s),
            None => return Outcome::crate_error(EvalStatus::ModelError, "a mass gate carries no registered status"),
        }
    }
    let v = pydict! {
        "record" => pydict! {
            "path" => v5::RECORD_REL,
            "reproduced" => stale.is_empty(),
            "stale" => Value::List(stale.iter().map(|s| Value::str(*s)).collect()),
        },
        "rollups" => field("rollups"),
        "mass_status" => field("mass_status"),
        "mass_gates" => gates.clone(),
        "al07_value_status" => al07,
    };
    let payload = match py_payload(&v) {
        Ok(p) => p,
        Err(o) => return o,
    };
    if !stale.is_empty() {
        return Outcome::status(
            EvalStatus::ModelError,
            Some(Reason::new("RECORD_NOT_REPRODUCED", format!("{} does not reproduce: {stale:?}", v5::RECORD_REL))),
            Some(payload),
        );
    }
    Outcome::summarised(worst(statuses), "CRATE_STATUS", v5::MASS_STATUS, payload)
}

// ------------------------------------------------------------------------------------------------ power

fn power_ledger(root: &Path) -> Outcome {
    use abep_subsystems::power::official::{official_flight_ledger, MassPowerA9V5};
    let r = MassPowerA9V5::load(root).and_then(|mp| official_flight_ledger(&mp));
    match r {
        Err(e) => Outcome::crate_error(e.status, e.to_string()),
        Ok(ledger) => match py_payload(&ledger.to_value()) {
            Err(o) => o,
            Ok(p) => Outcome::summarised(
                ledger.status.eval_status(),
                "CRATE_STATUS",
                format!("ledger status {} ({} TBD terms)", ledger.status.as_str(), ledger.tbd.len()),
                p,
            ),
        },
    }
}

// ------------------------------------------------------------------------------------------------ hall

fn root_str(root: &Path) -> String {
    root.display().to_string()
}

fn hall_status(root: &Path) -> Outcome {
    use abep_hall::py::{self as hpy, PyValue};
    use abep_hall::status::{hall_response_status, HallGate};
    let repo = root_str(root);
    let gate = match HallGate::from_repository(&repo) {
        Ok(g) => g,
        Err(e) => return abep_err(e),
    };
    let response = match hall_response_status(&repo) {
        Ok(v) => v,
        Err(e) => return abep_err(e.into()),
    };
    let reason = gate.reason.clone().map_or(PyValue::None, hpy::s);
    let members = PyValue::List(gate.admitted_members.iter().map(|m| hpy::s(m.clone())).collect());
    let v = hpy::dict([
        (
            "gate",
            hpy::dict([("status", hpy::s(gate.status.as_str())), ("reason", reason), ("admitted_members", members)]),
        ),
        ("hall_response_status", response),
    ]);
    Outcome::summarised(gate.status, "CRATE_STATUS", gate.reason.unwrap_or_default(), hall_payload(&v))
}

/// The Julia-side check_pin() needs the pinned Julia: it stays the registered platform test of C-JULIA-BRIDGE-LAUNCH.
pub const JULIA_CHECK_PIN: &str = "NOT_EXECUTED_PLATFORM_TEST";

fn hall_pin_check(root: &Path) -> Outcome {
    use abep_hall::py as hpy;
    use abep_julia_bridge::pin::{pin_report, verify_pin};
    let repo = root_str(root);
    let report = match pin_report(&repo) {
        Ok(r) => r,
        Err(e) => return abep_err(e.into()),
    };
    let payload = hall_payload(&hpy::dict([("pin_report", report), ("julia_check_pin", hpy::s(JULIA_CHECK_PIN))]));
    match verify_pin(&repo) {
        Ok(_) => Outcome::evaluated(payload),
        Err(e) => Outcome::status(e.status(), Some(Reason::new("PIN_UNVERIFIED", e.to_string())), Some(payload)),
    }
}

// ------------------------------------------------------------------------------------------------ icp

fn icp_status(root: &Path, supply_mode: &str) -> Outcome {
    use abep_icp::case::SupplyMode;
    use abep_icp::chemistry::ChemistryRegistration;
    use abep_icp::status::IcpStatus;
    let (mode, gas) = match supply_mode {
        "AIR_PRIMARY" => (SupplyMode::AirPrimary, "AIR"),
        "XE_CONTINGENCY" => (SupplyMode::XeContingency, "XE"),
        other => {
            return Outcome::crate_error(EvalStatus::ModelError, format!("supply mode {other} passed registration"))
        }
    };
    let model = match abep_icp::IcpModel::load(root) {
        Ok(m) => m,
        Err(e) => return abep_err(e),
    };
    // The case holding only what the repository registers today (every other input unregistered).
    let case = abep_icp::testkit::registered_today_case(mode, ChemistryRegistration::NotRegistered { gas: gas.into() });
    let r = model.evaluate(&case);
    let codes: Vec<String> = r.reason_codes().into_iter().collect();
    let payload = Payload { format: "serde_json", text: r.to_json() };
    let (status, code) = match r.status {
        IcpStatus::Converged => (EvalStatus::NotEvaluated, "COMPONENT_NOT_ADMITTED"),
        IcpStatus::NotEvaluated => (EvalStatus::NotEvaluated, "CRATE_STATUS"),
        IcpStatus::IncompleteEvidence => (EvalStatus::IncompleteEvidence, "CRATE_STATUS"),
        IcpStatus::OutOfDomain => (EvalStatus::OutOfDomain, "CRATE_STATUS"),
        IcpStatus::ModelError => (EvalStatus::ModelError, "CRATE_STATUS"),
    };
    let message = format!(
        "NP-ICP-NEUTRALIZER is NOT_ADMITTED; crate status {}; reason codes: {}",
        r.status.as_str(),
        codes.join(", ")
    );
    Outcome::status(status, Some(Reason::new(code, message)), Some(payload))
}
