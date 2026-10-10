//! IF-MIS-DECISIVE: the mission integration over the frozen 196-state set with today's admitted inputs (A9.31 sec. 16).
//!
//! [`run_admitted`] reads each admitted layer and fills the IN-STATE / IN-MASS records with exactly what the layer
//! supplies today, then calls [`integrate`]. Nothing is invented: a layer that cannot supply a quantity gives its
//! fail-closed status and reason. The F1 intake-face drag is added only at a caller-supplied F1 design point, as
//! PARAMETRIC_SENSITIVITY_ONLY (the surface scenario is a TBD context axis).
//!
//! Layers: environment (abep_atmos::execution, SC-WP-01), operating scenario (abep_config::OperatingInputs), Hall gate
//! (abep_hall::status::HallGate), NP-ICP-NEUTRALIZER (abep_icp, governed by its ledger admission status), bus ledger
//! (abep_subsystems::power::official, SC-WP-05), wet-mass objective (abep_subsystems::mass::wet_mass, SC-WP-07), the
//! mass_power_a9_v5 Xe planning cases, and the F1 drag table (crate::intake_drag, SC-WP-04).

use super::model::{
    integrate, EnvState, EnvValues, Horizons, IcpGasMode, MassInputs, MissionInputs, MissionRecord, Mode, PlanningCase,
    Provenance, StateModeInputs, INPUT_KEYS, XE_LOAD_NOT_FROZEN,
};
use super::quantity::{worst, Label, Quantity, Reason, PARAMETRIC_SENSITIVITY_ONLY};
use super::{
    ADDENDUM_01_REL, ADDENDUM_01_SHA256, ARCHITECTURE, PREREG_MD_REL, PREREG_MD_SHA256, PREREG_REL, PREREG_SHA256,
};
use crate::statewise_td::{
    DesignPoint, CREDIBLE_HALL_TRANSPORT_SET_EMPTY, HALL_MAP_NOT_REGISTERED, HOST_SPACECRAFT_DRAG_ICD_ABSENT,
};
use abep_provenance::{read_verified, sha256_hex};
use abep_types::{AbepError, AbepResult, EvalStatus};
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::Path;

pub const NO_FROZEN_DESIGN_POINT: &str = "NO_FROZEN_DESIGN_POINT";
pub const NP_ICP_NOT_ADMITTED: &str = "NP_ICP_NOT_ADMITTED";
pub const NP_ICP_CRATE_STATUS: &str = "NP_ICP_CRATE_STATUS";
pub const BUS_LEDGER_NOT_COMPLETE: &str = "BUS_LEDGER_NOT_COMPLETE";
pub const NON_FIRING_LOAD_NOT_REGISTERED: &str = "NON_FIRING_LOAD_NOT_REGISTERED";
pub const THERMAL_LOADS_NOT_EVALUATED: &str = "THERMAL_LOADS_NOT_EVALUATED";
pub const MASS_CBE_ABSENT: &str = "MASS_CBE_ABSENT";

pub const LEDGER_REL: &str = "docs/rust_migration/migration_state_v1.json";
pub const MASS_POWER_V5_REL: &str = "docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json";

/// Options of the run.
#[derive(Debug, Clone, Default)]
pub struct TodayOptions {
    /// An F1 design point at which the intake-face drag is added as PARAMETRIC_SENSITIVITY_ONLY (None: NOT_EVALUATED).
    pub design_point: Option<DesignPoint>,
    pub rust_commit: String,
    /// The ICP chemistry registry the RF/ICP layer reads (None: the live registry). Frozen records name the pinned
    /// snapshot they regenerate from (coordinator decision 2026-10-09).
    pub icp_registry: Option<abep_chem::registry::RegistrySource>,
}

/// Status of one admitted layer as read today.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LayerStatus {
    pub layer: String,
    pub status: EvalStatus,
    pub detail: String,
}

/// The run: the record, the layer statuses and the declared file list (FT-10).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct TodayRun {
    pub record: MissionRecord,
    pub layers: Vec<LayerStatus>,
    pub files_read: Vec<String>,
}

fn absent(units: &str, code: &str, status: EvalStatus, detail: impl Into<String>) -> AbepResult<Quantity> {
    Quantity::absent(units, Reason::new(code, status, detail))
}

fn absent_many(units: &str, reasons: &[Reason]) -> AbepResult<Quantity> {
    let mut q = Quantity::absent(units, reasons[0].clone())?;
    q.status = reasons.iter().map(|r| r.status).fold(EvalStatus::Evaluated, worst);
    q.reasons = reasons.to_vec();
    q.validate()?;
    Ok(q)
}

fn json_at<'a>(v: &'a serde_json::Value, path: &[&str]) -> Option<&'a serde_json::Value> {
    path.iter().try_fold(v, |x, k| x.get(*k))
}

/// The admission status of a new item in the migration ledger (read only).
fn ledger_status(repo: &Path, id: &str) -> AbepResult<String> {
    let bytes = std::fs::read(repo.join(LEDGER_REL))
        .map_err(|e| AbepError::Io { path: LEDGER_REL.into(), message: e.to_string() })?;
    let v: serde_json::Value = serde_json::from_slice(&bytes)
        .map_err(|e| AbepError::Schema { path: LEDGER_REL.into(), message: e.to_string() })?;
    v.get("new_items")
        .and_then(|x| x.as_array())
        .and_then(|a| a.iter().find(|x| x.get("id").and_then(|i| i.as_str()) == Some(id)))
        .and_then(|x| x.get("status"))
        .and_then(|s| s.as_str())
        .map(str::to_string)
        .ok_or_else(|| AbepError::Schema { path: LEDGER_REL.into(), message: format!("new item {id} has no status") })
}

/// Run the mission integration over the frozen 196-state set with today's admitted inputs.
pub fn run_admitted(repo: &Path, opts: &TodayOptions) -> AbepResult<TodayRun> {
    let mut files: Vec<String> = Vec::new();
    let mut layers = Vec::new();
    // Preregistration identity (DET-02).
    for (rel, sha) in
        [(PREREG_REL, PREREG_SHA256), (PREREG_MD_REL, PREREG_MD_SHA256), (ADDENDUM_01_REL, ADDENDUM_01_SHA256)]
    {
        read_verified(&repo.join(rel), sha)?;
        files.push(rel.to_string());
    }

    // IN-SCN: the operating scenario through the admitted loader (manifest + code pin).
    let paths = abep_config::ConfigPaths::repository(repo);
    let oi = abep_config::loaders::OperatingInputs::load(&paths).map_err(AbepError::from)?;
    files.extend(["config/MANIFEST.json".to_string(), "config/mission/mission_scenario_v2.json".to_string()]);
    let horizons = Horizons {
        mission_hours_h: oi.mission_hours,
        mission_hours_label: "MISSION_DURATION_BASIS".into(),
        firing_hours_h: oi.firing_hours,
        firing_hours_label: oi.firing_hours_label.clone(),
        source: oi.source.clone(),
    };

    // IN-ENV: the 196-state execution (SC-WP-01).
    let env = abep_atmos::execution::Environment::load(repo)?;
    let run = abep_atmos::execution::run(&env)?;
    files.extend(
        [
            "config/model_set/physics_model_set_v1.json",
            "config/environment/design_state_set_ref_v1.json",
            "config/constraints/engineering_constraints_v1.json (environment layer: altitude-band domain pin, A9.22 G5; addendum 01)",
            "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json",
            "abep_sim/data/atmosphere_msis21_orbit_v1.* (orbit dataset and sidecar)",
            "abep_sim/data/hwm14 orbit wind dataset v2 (environment layer)",
        ]
        .map(String::from),
    );
    layers.push(LayerStatus {
        layer: "environment (abep_atmos::execution)".into(),
        status: if run.n_evaluated == run.n_states { EvalStatus::Evaluated } else { EvalStatus::ModelError },
        detail: format!(
            "{} states, {} EVALUATED, {} OUT_OF_DOMAIN, {} MODEL_ERROR",
            run.n_states, run.n_evaluated, run.n_out_of_domain, run.n_model_error
        ),
    });
    let mut env_states = Vec::with_capacity(run.records.len());
    for r in &run.records {
        let rec = env
            .set
            .select(&r.state_id)
            .ok_or_else(|| AbepError::Model { message: format!("state {} not in the set", r.state_id) })?;
        let values = r.environment.as_ref().map(|a| EnvValues {
            alt_km: a.alt_km,
            rho_kg_m3: a.rho,
            fO: a.fO,
            fN2: a.fN2,
            fO2: a.fO2,
            n_O_m3: a.n_O,
            T_K: a.T,
            v_orbital_m_s: a.V,
        });
        let reasons = match &r.error {
            Some(e) => vec![Reason::new("ENVIRONMENT_EXECUTION", r.status, e.clone())],
            None => vec![],
        };
        env_states.push(EnvState {
            state_id: r.state_id.clone(),
            required: rec.required,
            nominal_mission_scenario: rec.nominal_mission_scenario,
            labels: rec.labels.clone(),
            status: r.status,
            reasons,
            source: r.environment.as_ref().map(|a| a.source.clone()).unwrap_or_default(),
            values,
        });
    }

    // Hall (SC-WP-03): the governed gate.
    let repo_str = repo.to_string_lossy().to_string();
    let gate = abep_hall::status::HallGate::from_repository(&repo_str)?;
    files.push(abep_hall::status::ENS_REL.to_string());
    let hall_reason = if gate.admitted_members.is_empty() {
        Reason::new(
            CREDIBLE_HALL_TRANSPORT_SET_EMPTY,
            EvalStatus::NotEvaluated,
            "credible Hall transport set EMPTY (no admitted member, no Hall map)",
        )
    } else {
        Reason::new(
            HALL_MAP_NOT_REGISTERED,
            EvalStatus::NotEvaluated,
            "no design-specific Hall map of an admitted member is registered",
        )
    };
    layers.push(LayerStatus {
        layer: "Hall (abep_hall::status::HallGate)".into(),
        status: gate.status,
        detail: format!("admitted members {:?}; {}", gate.admitted_members, hall_reason.detail),
    });

    // RF/ICP (SC-WP-03): ledger admission plus the crate status of the case holding today's registrations.
    let icp_admission = ledger_status(repo, "NP-ICP-NEUTRALIZER")?;
    files.push(LEDGER_REL.to_string());
    let icp_model = match &opts.icp_registry {
        Some(src) => abep_icp::IcpModel::load_with(repo, src)?,
        None => abep_icp::IcpModel::load(repo)?,
    };
    files.extend(icp_model.files_read.iter().map(|f| f.path.clone()));
    let mut icp_reasons: BTreeMap<Mode, Vec<Reason>> = BTreeMap::new();
    for (mode, sm, gas) in [
        (Mode::AirPrimary, abep_icp::case::SupplyMode::AirPrimary, "AIR"),
        (Mode::XeContingency, abep_icp::case::SupplyMode::XeContingency, "XE"),
    ] {
        let case = abep_icp::testkit::registered_today_case(
            sm,
            abep_icp::chemistry::ChemistryRegistration::NotRegistered { gas: gas.into() },
        );
        let r = icp_model.evaluate(&case);
        let crate_status: EvalStatus = r.status.into();
        let codes: Vec<String> = r.reason_codes().into_iter().collect();
        let mut rs = vec![Reason::new(
            NP_ICP_CRATE_STATUS,
            if crate_status.is_evaluated() { EvalStatus::NotEvaluated } else { crate_status },
            format!(
                "NP-ICP-NEUTRALIZER crate status {} for the registered-today {} case; reason codes {}",
                r.status.as_str(),
                mode.as_str(),
                codes.join(", ")
            ),
        )];
        if icp_admission != "ADMITTED" {
            rs.insert(
                0,
                Reason::new(
                    NP_ICP_NOT_ADMITTED,
                    EvalStatus::NotEvaluated,
                    format!("NP-ICP-NEUTRALIZER ledger status {icp_admission} (not ADMITTED)"),
                ),
            );
        }
        layers.push(LayerStatus {
            layer: format!("RF/ICP {} (abep_icp)", mode.as_str()),
            status: rs.iter().map(|x| x.status).fold(EvalStatus::Evaluated, worst),
            detail: rs.iter().map(|x| x.detail.clone()).collect::<Vec<_>>().join("; "),
        });
        icp_reasons.insert(mode, rs);
    }

    // Electrical (SC-WP-05): the official flight ledger of bus_power_boundary_a9_v2.
    let mp = abep_subsystems::power::official::MassPowerA9V5::load(repo)
        .map_err(|e| AbepError::Model { message: e.to_string() })?;
    let led = abep_subsystems::power::official::official_flight_ledger(&mp)
        .map_err(|e| AbepError::Model { message: e.to_string() })?;
    files.push(MASS_POWER_V5_REL.to_string());
    let bus_reason = Reason::new(
        BUS_LEDGER_NOT_COMPLETE,
        led.status.eval_status(),
        format!(
            "official flight ledger {} ({} TBD terms; bus_power_boundary_a9_v2)",
            led.status.as_str(),
            led.tbd.len()
        ),
    );
    layers.push(LayerStatus {
        layer: "electrical (official_flight_ledger)".into(),
        status: led.status.eval_status(),
        detail: bus_reason.detail.clone(),
    });

    // Mass (SC-WP-07): the wet-mass objective and the registered Xe planning cases.
    let wm = abep_subsystems::mass::wet_mass::wet_mass_pinned(
        repo,
        &abep_types::pyjson::Value::str(ARCHITECTURE),
        &abep_types::pyjson::Value::Null,
        &abep_types::pyjson::Value::Null,
    )
    .map_err(|e| AbepError::Model { message: format!("{e:?}") })?;
    let wm_get = |k: &str| wm.as_dict().and_then(|d| d.get(k)).cloned();
    let wm_status =
        wm_get("status").and_then(|v| v.as_str().map(str::to_string)).unwrap_or_else(|| "MODEL_ERROR".into());
    let wm_reason = wm_get("reason").map(|r| abep_types::pyjson::py_str(&r)).unwrap_or_default();
    let m_dry_status = match wm_status.as_str() {
        "NOT_EVALUATED" => EvalStatus::NotEvaluated,
        "INCOMPLETE_EVIDENCE" => EvalStatus::IncompleteEvidence,
        "PARAMETRIC_SENSITIVITY_ONLY" => EvalStatus::IncompleteEvidence,
        _ => EvalStatus::NotEvaluated,
    };
    layers.push(LayerStatus {
        layer: "mass (wet_mass objective)".into(),
        status: m_dry_status,
        detail: format!("m_wet objective {wm_status}: {wm_reason}"),
    });
    let v5_bytes = read_verified(&repo.join(MASS_POWER_V5_REL), abep_subsystems::mass::v5::RECORD_SHA256)?;
    let v5: serde_json::Value = serde_json::from_slice(&v5_bytes)
        .map_err(|e| AbepError::Schema { path: MASS_POWER_V5_REL.into(), message: e.to_string() })?;
    let cases = json_at(&v5, &["xe_v3_import", "loaded_split"]).and_then(|x| x.as_array()).ok_or_else(|| {
        AbepError::Schema { path: MASS_POWER_V5_REL.into(), message: "xe_v3_import.loaded_split missing".into() }
    })?;
    let mut planning = Vec::new();
    for c in cases {
        let kg = c.get("case_kg").and_then(|x| x.as_f64()).ok_or_else(|| AbepError::Schema {
            path: MASS_POWER_V5_REL.into(),
            message: "loaded_split[].case_kg".into(),
        })?;
        planning.push(PlanningCase {
            m_xe_kg: kg,
            source: format!("{MASS_POWER_V5_REL} xe_v3_import.loaded_split case {kg} kg (A9.25 msg 8 sec. 7)"),
        });
    }
    let xe_nf = || {
        absent("kg", XE_LOAD_NOT_FROZEN, EvalStatus::NotEvaluated, "the flight Xe load is NOT YET FROZEN (A9.25 msg 8 sec. 7); reserve / residual are booked on the frozen load")
    };
    let mass = MassInputs {
        m_dry_kg: absent("kg", MASS_CBE_ABSENT, m_dry_status, format!("wet-mass objective {wm_status}: {wm_reason}"))?,
        m_xe_loaded_kg: xe_nf()?,
        xe_planning_cases: planning,
        xe_reserve_kg: xe_nf()?,
        xe_residual_kg: xe_nf()?,
    };

    // SC-WP-04 intake-face drag at a caller-supplied F1 design point (parametric only).
    let drag = match &opts.design_point {
        Some(_) => {
            files.push(crate::intake_drag::F1_CORE_REL.to_string());
            Some(crate::intake_drag::load_drag_table(repo)?.0)
        }
        None => None,
    };

    // IN-STATE.
    let nodesign = |units: &str, what: &str| {
        absent(
            units,
            NO_FROZEN_DESIGN_POINT,
            EvalStatus::NotEvaluated,
            format!("{what}: no frozen design point (F7 / F8, SC-WP-10); intake surface scenario TBD"),
        )
    };
    let hall = |units: &str| absent_many(units, std::slice::from_ref(&hall_reason));
    let mut states = BTreeMap::new();
    for st in &env_states {
        for mode in Mode::ALL {
            let mut q: BTreeMap<String, Quantity> = BTreeMap::new();
            let firing = mode != Mode::NonFiring;
            for (k, u) in INPUT_KEYS {
                let v = match k {
                    "intake_capture_kg_s" => nodesign(u, "intake capture")?,
                    "drag_intake_N" => match (&opts.design_point, &drag) {
                        (Some(p), Some(t)) => {
                            let e = t.get(&p.scenario, p.l_over_d, p.phi, &st.state_id).ok_or_else(|| {
                                AbepError::OutOfDomain {
                                    message: format!(
                                        "design point {} L/d {} phi {} not in the F1 drag table at {}",
                                        p.scenario, p.l_over_d, p.phi, st.state_id
                                    ),
                                }
                            })?;
                            absent(u, "INTAKE_DRAG_PARAMETRIC", crate::intake_drag::INTAKE_DRAG_STATUS, "F1 intake-face drag: surface scenario is a TBD context axis (PARAMETRIC_SENSITIVITY_ONLY)")?
                                .with_parametric(p.area_m2 * e.drag_per_area_n_m2, PARAMETRIC_SENSITIVITY_ONLY, crate::statewise_td::intake_record_source(p, &st.state_id))?
                        }
                        _ => nodesign(u, "intake-face drag")?,
                    },
                    "p_feed_Pa" | "T_feed_K" | "mdot_atm_delivered_kg_s" => {
                        if mode == Mode::XeContingency && k != "mdot_atm_delivered_kg_s" {
                            absent(
                                u,
                                NO_FROZEN_DESIGN_POINT,
                                EvalStatus::NotEvaluated,
                                "Xe feed state: no frozen Xe feed design point",
                            )?
                        } else {
                            nodesign(u, "feed state / delivered atmospheric flow")?
                        }
                    }
                    "mdot_hall_anode_kg_s" | "I_d_A" | "thrust_N" => hall(u)?,
                    "mdot_icp_dedicated_kg_s" | "I_ecap_A" => match icp_reasons.get(&mode) {
                        Some(rs) => absent_many(u, rs)?,
                        None => absent(u, NP_ICP_NOT_ADMITTED, EvalStatus::NotEvaluated, "no ICP case for this mode")?,
                    },
                    "P_bus_W" => {
                        if firing {
                            absent_many(u, &[hall_reason.clone(), bus_reason.clone()])?
                        } else {
                            absent(
                                u,
                                NON_FIRING_LOAD_NOT_REGISTERED,
                                EvalStatus::NotEvaluated,
                                "NON_FIRING standby bus load is not registered (OQ-MI-05)",
                            )?
                        }
                    }
                    "drag_body_N" => absent(
                        u,
                        HOST_SPACECRAFT_DRAG_ICD_ABSENT,
                        EvalStatus::NotEvaluated,
                        "host-spacecraft drag ICD absent (F1-ID-08; S6.18)",
                    )?,
                    "thermal_t_max_K" => {
                        if firing {
                            absent(
                                u,
                                THERMAL_LOADS_NOT_EVALUATED,
                                EvalStatus::NotEvaluated,
                                "NP-THERMAL-CATHODELESS NE-01 / NE-02: Hall and ICP heat loads NOT_EVALUATED",
                            )?
                        } else {
                            absent(
                                u,
                                NON_FIRING_LOAD_NOT_REGISTERED,
                                EvalStatus::NotEvaluated,
                                "NON_FIRING thermal state is not registered (OQ-MI-05)",
                            )?
                        }
                    }
                    other => return Err(AbepError::Model { message: format!("today: unhandled input {other}") }),
                };
                q.insert(k.to_string(), v);
            }
            let required = super::model::required_inputs(mode);
            q.retain(|k, _| required.contains(&k.as_str()));
            let hall_state = firing.then(|| Label {
                status: hall_reason.status,
                label: None,
                source: "abep_hall::status::HallGate".into(),
                reasons: vec![hall_reason.clone()],
            });
            states.insert((st.state_id.clone(), mode), StateModeInputs { quantities: q, hall_state });
        }
    }

    let mut input_hashes = BTreeMap::new();
    input_hashes.insert("design_state_set_sha256".into(), run.design_state_set_sha256.clone());
    input_hashes.insert("orbit_dataset_sha256".into(), run.dataset_sha256.clone());
    input_hashes.insert("config_manifest_sha256".into(), run.config_manifest_sha256.clone());
    input_hashes.insert("model_set_sha256".into(), run.model_set_sha256.clone());
    input_hashes.insert(
        "mission_scenario_sha256".into(),
        sha256_hex(&std::fs::read(repo.join("config/mission/mission_scenario_v2.json")).map_err(|e| {
            AbepError::Io { path: "config/mission/mission_scenario_v2.json".into(), message: e.to_string() }
        })?),
    );
    input_hashes.insert("mass_power_a9_v5_sha256".into(), abep_subsystems::mass::v5::RECORD_SHA256.into());
    input_hashes.insert("addendum_01_sha256".into(), ADDENDUM_01_SHA256.into());
    let inputs = MissionInputs {
        configuration: ARCHITECTURE.into(),
        horizons,
        env: env_states,
        icp_gas_mode: IcpGasMode::GReuse,
        states,
        mass,
        schedule: None,
        provenance: Provenance { rust_commit: opts.rust_commit.clone(), input_hashes },
    };
    let record = integrate(&inputs)?;
    Ok(TodayRun { record, layers, files_read: files })
}
