//! RFP constraint-matrix evaluator (A9.31 sec. 17; acceptance ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1): the assessment
//! half of the decisive architecture run. Eight requirements, each with four separate fields: RAW PHYSICS RESULT,
//! UNCERTAINTY / MODEL DOMAIN, EVIDENCE STATUS and RFP ASSESSMENT STATUS. The raw records come from the admitted
//! crates and are only borrowed; thresholds come from the frozen configuration (abep-config).
//!
//! COMPLIES needs determining evidence (measured, or a model validated in its domain cell) at every required state /
//! governed case; nothing today provides it, so no row can read COMPLIES. DOES_NOT_CLOSE is a governed model / budget
//! evaluation on the wrong side of the limit at every governed case, never a demonstrated non-compliance.

use crate::error::{AssessError, AssessResult};
use crate::gates::evaluate_constraints;
use crate::icp_gate;
use crate::neutralization::{hc05, neutralization_quantities, NeutralizationInputs};
use crate::power_gate::rfp_power_gate;
use crate::propellant::{propellant_paths_check, AIR_PATH, XE_PATH};
use crate::py::{dget, dict, eq_str, fmt_g, get, s, strs};
use crate::rvm::RvmRecord;
use crate::statewise::statewise_drag_compensation;
use crate::thresholds::Thresholds;
use abep_config::architecture::ArchitectureDefinition;
use abep_config::ConfigPaths;
use abep_data::design_states::DesignStateSet;
use abep_hall::status::HallGate;
use abep_types::pyjson::{dumps, py_str, DumpOptions, Value};
use abep_types::EvalStatus;
use std::path::Path;

pub const SCHEMA: &str = "abep_assess_rfp_constraint_matrix_v1";
pub const ROW_FIELDS: [&str; 7] = [
    "id",
    "requirement",
    "threshold",
    "raw_physics_result",
    "uncertainty_model_domain",
    "evidence_status",
    "rfp_assessment_status",
];
pub const ASSESSMENT_VOCABULARY: [&str; 7] = [
    "COMPLIES",
    "DOES_NOT_COMPLY",
    "DOES_NOT_CLOSE",
    "INCOMPLETE_EVIDENCE",
    "NOT_EVALUATED",
    "OUT_OF_DOMAIN",
    "MODEL_ERROR",
];
/// Words that belong to assessment and never appear in a raw_physics_result field (AC-01).
pub const ASSESSMENT_WORDS: [&str; 9] = [
    "COMPLIES",
    "DOES_NOT_COMPLY",
    "DOES_NOT_CLOSE",
    "CLOSES",
    "MET_ON_SUPPLIED_VALUES",
    "VIOLATED",
    "PASS",
    "FAIL",
    "NOT_EVALUABLE",
];
pub const HOST_DRAG_ABSENT: &str = "host-spacecraft drag ICD absent (S6.18 / F1-ID-08: no spacecraft geometry)";
pub const NO_DELIVERED_FLOW: &str =
    "no delivered-flow record for a selected design point (F7 / F8 robust selection, SC-WP-10)";
pub const ICP_FLIGHT_HALL_ON: &str = "CFG-FLIGHT-HALL-ON NOT_EVALUATED: needs an admitted HallThruster.jl member \
(NP-ICP NE-08) and a registered I_d,max,H1";

/// Raw-physics records of the admitted crates (each load is fail closed: an error marks the dependent rows
/// MODEL_ERROR, never a silent value).
#[derive(Debug, Clone)]
pub struct RawPhysics {
    pub design_states: AssessResult<DesignStateSet>,
    pub hall_gate: AssessResult<HallGate>,
    pub architecture: AssessResult<ArchitectureDefinition>,
    /// Official flight ledger (bus_power_boundary_a9_v2), Python-shaped.
    pub bus_ledger: AssessResult<Value>,
    /// `bus_power` objective of the official path.
    pub bus_objective: AssessResult<Value>,
    /// Registered start-up step ledgers (none today).
    pub startup_ledgers: Vec<Value>,
    /// The pinned mass_power_a9_v5 record and its fail-closed gates.
    pub mass_record: AssessResult<Value>,
    pub mass_gates: AssessResult<Value>,
    pub wet_mass_objective: AssessResult<Value>,
    pub rvm: AssessResult<RvmRecord>,
    /// ICP CHEM-AIR tier-1 processes not IN_REPO_VERIFIED, per mode.
    pub icp_chemistry_gaps: AssessResult<Vec<(String, usize)>>,
    /// IF-ICP-HALL-v1 neutralization inputs at a registered point (none today).
    pub neutralization: Option<NeutralizationInputs>,
    /// Objective records not produced today (None): thrust, thrust capability, propellant capability.
    pub thrust: Value,
    pub thrust_capability: Value,
    pub propellant_capability: Value,
    pub delivered_flow: Value,
}

fn err<E: Into<AssessError>>(e: E) -> AssessError {
    e.into()
}

impl RawPhysics {
    /// Today's admitted raw results of the repository at `repo`.
    pub fn load_repository(repo: &Path) -> Self {
        use abep_subsystems::mass::{rules::FLIGHT, v5, wet_mass};
        use abep_subsystems::power::{
            objective::bus_power_official, official::official_flight_ledger, official::MassPowerA9V5,
        };
        let design_states =
            abep_data::pins::FrozenPins::load(repo).and_then(|p| DesignStateSet::load(repo, &p)).map_err(err);
        let hall_gate = HallGate::from_repository(&repo.to_string_lossy()).map_err(err);
        let architecture = ArchitectureDefinition::load(&ConfigPaths::repository(repo)).map_err(err);
        let mp = MassPowerA9V5::load(repo).map_err(|e| AssessError::new("MODEL_ERROR", e.to_string()));
        let bus_ledger = mp.clone().and_then(|m| {
            official_flight_ledger(&m).map(|l| l.to_value()).map_err(|e| AssessError::new("MODEL_ERROR", e.to_string()))
        });
        let bus_objective = mp.and_then(|m| {
            bus_power_official(&m, FLIGHT, None).map_err(|e| AssessError::new("MODEL_ERROR", e.to_string()))
        });
        let mass_record = v5::load_record_pinned(repo).map_err(err);
        let mass_gates = v5::mass_gates(repo, &v5::MissionXeLoad::NotAdmitted).map_err(err);
        let wet_mass_objective = wet_mass::wet_mass_pinned(repo, &s(FLIGHT), &Value::Null, &Value::Null).map_err(err);
        let rvm = RvmRecord::load(repo);
        let icp_chemistry_gaps = abep_icp::IcpModel::load(repo)
            .map_err(err)
            .map(|m| ["AIR", "XE"].iter().map(|k| (k.to_string(), m.chem_air_tier1_gaps(k).len())).collect());
        RawPhysics {
            design_states,
            hall_gate,
            architecture,
            bus_ledger,
            bus_objective,
            startup_ledgers: Vec::new(),
            mass_record,
            mass_gates,
            wet_mass_objective,
            rvm,
            icp_chemistry_gaps,
            neutralization: None,
            thrust: Value::Null,
            thrust_capability: Value::Null,
            propellant_capability: Value::Null,
            delivered_flow: Value::Null,
        }
    }

    /// Canonical serialization of every raw record (immutability check AC-08, provenance digests).
    pub fn canonical(&self) -> String {
        fn r<T: std::fmt::Debug>(x: &T) -> String {
            format!("{x:?}")
        }
        [
            r(&self.design_states.as_ref().map(|d| (&d.sha256, d.n_states, &d.states))),
            r(&self.hall_gate),
            r(&self.architecture),
            r(&self.bus_ledger),
            r(&self.bus_objective),
            r(&self.startup_ledgers),
            r(&self.mass_record),
            r(&self.mass_gates),
            r(&self.wet_mass_objective),
            r(&self.rvm.as_ref().map(|x| &x.sha256)),
            r(&self.icp_chemistry_gaps),
            r(&self.neutralization),
            r(&self.thrust),
            r(&self.thrust_capability),
            r(&self.propellant_capability),
            r(&self.delivered_flow),
        ]
        .join("\n")
    }
}

fn st(x: EvalStatus) -> Value {
    s(x.as_str())
}

fn model_error_row(id: &str, requirement: &str, threshold: Value, e: &AssessError) -> Value {
    let me = dict(vec![("status", st(EvalStatus::ModelError)), ("error", s(e.to_string()))]);
    dict(vec![
        ("id", s(id)),
        ("requirement", s(requirement)),
        ("threshold", threshold),
        ("raw_physics_result", me.clone()),
        ("uncertainty_model_domain", dict(vec![("status", st(EvalStatus::ModelError))])),
        ("evidence_status", me.clone()),
        (
            "rfp_assessment_status",
            dict(vec![("status", s("MODEL_ERROR")), ("basis", s(format!("raw record failed verification: {e}")))]),
        ),
    ])
}

fn row(id: &str, requirement: &str, threshold: Value, raw: Value, dom: Value, ev: Value, rfp: Value) -> Value {
    dict(vec![
        ("id", s(id)),
        ("requirement", s(requirement)),
        ("threshold", threshold),
        ("raw_physics_result", raw),
        ("uncertainty_model_domain", dom),
        ("evidence_status", ev),
        ("rfp_assessment_status", rfp),
    ])
}

fn evidence(status: EvalStatus, class: &str, basis: &str) -> Value {
    dict(vec![("status", st(status)), ("evidence_class", s(class)), ("basis", s(basis))])
}

fn assessment(status: &str, basis: String, gates: Vec<Value>) -> Value {
    dict(vec![("status", s(status)), ("basis", s(basis)), ("gates", Value::List(gates))])
}

fn gate_row<'a>(evals: &'a Value, id: &str) -> AssessResult<&'a Value> {
    crate::py::as_list(evals)?
        .iter()
        .find(|r| eq_str(&dget(r, "id").unwrap_or(Value::Null), id))
        .ok_or_else(|| AssessError::new("MODEL_ERROR", format!("{id} missing")))
}

/// Map a hard-constraint row onto the assessment vocabulary: only EVALUATED MET / VIOLATED decide; a synthetic
/// value is never evidence (NOT_EVALUATED); a parametric comparison is sensitivity only (INCOMPLETE_EVIDENCE).
fn from_constraint(c: &Value) -> AssessResult<&'static str> {
    use abep_mission::objective::{EVALUATED, SYNTHETIC_ONLY};
    let cs = get(c, "status")?;
    let vs = dget(c, "value_status")?;
    Ok(if eq_str(cs, crate::gates::C_MET) && eq_str(&vs, EVALUATED) {
        "COMPLIES"
    } else if eq_str(cs, crate::gates::C_VIOLATED) && eq_str(&vs, EVALUATED) {
        "DOES_NOT_COMPLY"
    } else if eq_str(cs, crate::gates::C_NOT_EVALUATED) || eq_str(&vs, SYNTHETIC_ONLY) {
        "NOT_EVALUATED"
    } else {
        "INCOMPLETE_EVIDENCE"
    })
}

fn hall_reason(raw: &RawPhysics) -> Value {
    match &raw.hall_gate {
        Ok(g) => dict(vec![
            ("status", st(g.status)),
            ("reason", g.reason.as_deref().map_or(Value::Null, s)),
            ("admitted_members", Value::List(g.admitted_members.iter().map(|m| s(m.as_str())).collect())),
            ("source", s("abep_hall::status::HallGate (hallthruster_bridge/ensemble/transport_ensemble_v0.json)")),
        ]),
        Err(e) => dict(vec![("status", st(EvalStatus::ModelError)), ("reason", s(e.to_string()))]),
    }
}

fn hall_open(raw: &RawPhysics) -> bool {
    matches!(&raw.hall_gate, Ok(g) if g.status.is_evaluated())
}

/// Threshold record of a row (configured values only).
fn threshold(t: &Thresholds, gate: &str, extra: Vec<(&str, Value)>) -> Value {
    let mut v = vec![("gate", s(gate))];
    if gate.starts_with("HC-") {
        v.push(("value", t.limit(gate).map_or(Value::Null, Value::Float)));
        v.push(("provenance", t.provenance(gate)));
    }
    v.extend(extra);
    dict(v)
}

/// The statewise HC-08 assessment over the required states with the governed thrust / drag records.
fn hc08(t: &Thresholds, raw: &RawPhysics, ds: &DesignStateSet) -> AssessResult<Value> {
    let states: Vec<Value> =
        ds.states.iter().filter(|x| x.required).map(|x| dict(vec![("state_id", s(x.state_id.as_str()))])).collect();
    let tbd = |_: usize, stt: &Value| -> AssessResult<Value> {
        Ok(dict(vec![("state_id", dget(stt, "state_id")?), ("status", s("TBD")), ("value_N", Value::Null)]))
    };
    let mut tf = tbd;
    let mut df = tbd;
    statewise_drag_compensation(t, &states, &mut tf, &mut df, hall_open(raw))
}

fn summarize_hc08(q: &Value) -> AssessResult<Value> {
    Ok(dict(vec![
        ("gate", s("HC-08")),
        ("status", get(q, "status")?.clone()),
        ("value_status", get(q, "value_status")?.clone()),
        ("n_required_states", get(q, "n_required_states")?.clone()),
        ("reason", dget(q, "reason")?),
    ]))
}

fn row_alt(t: &Thresholds, raw: &RawPhysics) -> AssessResult<Value> {
    let (lo, hi) = t.altitude_band_km()?;
    let thr = threshold(
        t,
        "altitude_band_km",
        vec![
            ("value_km", Value::List(vec![Value::Float(lo), Value::Float(hi)])),
            ("source", s("config/constraints/engineering_constraints_v1.json altitude_band_km")),
        ],
    );
    let req = "altitude 180-230 km";
    let ds = match &raw.design_states {
        Ok(d) => d,
        Err(e) => return Ok(model_error_row("RFP-ALT", req, thr, e)),
    };
    let req_states: Vec<_> = ds.states.iter().filter(|x| x.required).collect();
    let (mut amin, mut amax) = (f64::INFINITY, f64::NEG_INFINITY);
    for x in &req_states {
        amin = amin.min(x.alt_km);
        amax = amax.max(x.alt_km);
    }
    let outside: Vec<Value> =
        req_states.iter().filter(|x| x.alt_km < lo || x.alt_km > hi).map(|x| s(x.state_id.as_str())).collect();
    let raw_v = dict(vec![
        ("design_state_set", s(abep_data::design_states::DESIGN_STATE_SET_ID)),
        ("design_state_set_sha256", s(ds.sha256.as_str())),
        ("n_states", Value::int(ds.n_states as i64)),
        ("n_required_states", Value::int(req_states.len() as i64)),
        ("alt_km_min", Value::Float(amin)),
        ("alt_km_max", Value::Float(amax)),
        ("thrust", hall_reason(raw)),
        ("spacecraft_drag", dict(vec![("status", st(EvalStatus::NotEvaluated)), ("reason", s(HOST_DRAG_ABSENT))])),
        ("status", st(EvalStatus::Evaluated)),
        ("source", s("abep_data::design_states::DesignStateSet::load (frozen, hash-verified)")),
    ]);
    let dom = dict(vec![
        ("states_inside_band", Value::int((req_states.len() - outside.len()) as i64)),
        ("states_outside_band", Value::List(outside.clone())),
        ("atmosphere_model", s("frozen NRLMSIS 2.1 design-state set v2 (hash-verified; no live MSIS)")),
        (
            "uncertainty",
            s("solar / geomagnetic / season / local-time envelope represented by the frozen states; unweighted"),
        ),
    ]);
    let q = hc08(t, raw, ds)?;
    let mut status =
        if eq_str(get(&q, "status")?, crate::gates::C_NOT_EVALUATED) { "NOT_EVALUATED" } else { "INCOMPLETE_EVIDENCE" };
    let mut basis = format!(
        "operation over the band is assessed statewise (HC-08 over {} required states): {}",
        req_states.len(),
        py_str(&dget(&q, "reason")?)
    );
    if !outside.is_empty() {
        status = "OUT_OF_DOMAIN";
        basis = format!("{} design state(s) outside the configured band", outside.len());
    }
    Ok(row(
        "RFP-ALT",
        req,
        thr,
        raw_v,
        dom,
        evidence(
            EvalStatus::NotEvaluated,
            "model-derived environment; no operating evidence",
            "operation over the band needs thrust and spacecraft drag at every required state",
        ),
        assessment(status, basis, vec![summarize_hc08(&q)?]),
    ))
}

fn composition(ds: &DesignStateSet) -> Value {
    let mut out = Vec::new();
    for k in ["x_O", "x_N2", "x_O2"] {
        let (mut lo, mut hi) = (f64::INFINITY, f64::NEG_INFINITY);
        for x in ds.states.iter().filter(|x| x.required) {
            lo = lo.min(x.thermo(k));
            hi = hi.max(x.thermo(k));
        }
        out.push((k, Value::List(vec![Value::Float(lo), Value::Float(hi)])));
    }
    dict(out)
}

fn chem_status(raw: &RawPhysics, mode: &str) -> Value {
    match &raw.icp_chemistry_gaps {
        Ok(g) => {
            let n = g.iter().find(|(k, _)| k == mode).map_or(0, |x| x.1);
            dict(vec![
                ("status", st(if n == 0 { EvalStatus::Evaluated } else { EvalStatus::IncompleteEvidence })),
                ("tier1_processes_not_verified", Value::int(n as i64)),
                ("source", s("abep_icp::IcpModel::chem_air_tier1_gaps (NP-ICP-CHEM-AIR registry)")),
            ])
        }
        Err(e) => dict(vec![("status", st(EvalStatus::ModelError)), ("error", s(e.to_string()))]),
    }
}

fn paths_value() -> Value {
    dict(vec![("air", strs(&AIR_PATH)), ("xe", strs(&XE_PATH))])
}

fn row_atm(t: &Thresholds, raw: &RawPhysics) -> AssessResult<Value> {
    let pc = get(&t.engineering, "propellant_capability")?.clone();
    let thr = threshold(
        t,
        "propellant_capability.ambient_atmosphere",
        vec![
            ("value", get(&pc, "ambient_atmosphere")?.clone()),
            ("source", s("config/constraints/engineering_constraints_v1.json propellant_capability")),
        ],
    );
    let req = "primary propellant: ambient atmospheric gas";
    let (arch, ds) = match (&raw.architecture, &raw.design_states) {
        (Ok(a), Ok(d)) => (a, d),
        (Err(e), _) | (_, Err(e)) => return Ok(model_error_row("RFP-ATM-PRIMARY", req, thr, e)),
    };
    let ne = |r: &str| dict(vec![("status", st(EvalStatus::NotEvaluated)), ("reason", s(r))]);
    let raw_v = dict(vec![
        ("supply_mode", arch.supply_mode_air.clone()),
        ("path_role", arch.air_path_role.clone()),
        ("air_path", strs(&AIR_PATH)),
        ("composition_range_required_states", composition(ds)),
        (
            "delivered_atmospheric_mass_flow",
            if raw.delivered_flow.truthy() { raw.delivered_flow.clone() } else { ne(NO_DELIVERED_FLOW) },
        ),
        ("hall_on_delivered_air", hall_reason(raw)),
        ("icp_air_chemistry", chem_status(raw, "AIR")),
        ("status", st(EvalStatus::NotEvaluated)),
    ]);
    let dom = dict(vec![
        (
            "chemistry_domain",
            s("AIR_PRIMARY and XE_CONTINGENCY are separate modes; mixed Xe / air compositions are OUT_OF_DOMAIN in \
               chemistry v1 (A9.31 OQ-CHEM-10); AIR chemistry INCOMPLETE_EVIDENCE until the NO materiality bound \
               exists (OQ-CHEM-02)"),
        ),
        ("uncertainty", s("not quantified: no delivered flow and no Hall operation on the delivered air evaluated")),
    ]);
    let pp = propellant_paths_check(arch, &paths_value())?;
    Ok(row(
        "RFP-ATM-PRIMARY",
        req,
        thr,
        raw_v,
        dom,
        evidence(
            EvalStatus::NotEvaluated,
            "none (declared path and supply mode only)",
            "a declared path is not determining evidence (S6.22)",
        ),
        assessment(
            "NOT_EVALUATED",
            "needs a delivered-flow record, an admitted Hall evaluation on the delivered air and an admitted ICP AIR \
             chemistry"
                .into(),
            vec![dict(vec![
                ("check", s("propellant_paths_check")),
                ("structure", get(&pp, "structure")?.clone()),
                ("status", get(&pp, "status")?.clone()),
            ])],
        ),
    ))
}

fn row_xe(t: &Thresholds, raw: &RawPhysics) -> AssessResult<Value> {
    let pc = get(&t.engineering, "propellant_capability")?.clone();
    let thr = threshold(
        t,
        "propellant_capability.xe",
        vec![
            ("value", get(&pc, "xe")?.clone()),
            ("source", s("config/constraints/engineering_constraints_v1.json propellant_capability")),
        ],
    );
    let req = "contingency capability: Xe";
    let (arch, gates) = match (&raw.architecture, &raw.mass_gates) {
        (Ok(a), Ok(g)) => (a, g),
        (Err(e), _) | (_, Err(e)) => return Ok(model_error_row("RFP-XE-CONTINGENCY", req, thr, e)),
    };
    let g2 = &crate::py::as_list(gates)?[1];
    let cases: Vec<Value> = crate::py::as_dict(get(g2, "hard_40_wet_state_by_loaded_case")?)?
        .keys()
        .map(|k| Value::Float(k.parse::<f64>().unwrap_or(f64::NAN)))
        .collect();
    let raw_v = dict(vec![
        ("supply_mode", arch.supply_mode_xe.clone()),
        ("path_role", arch.xe_path_role.clone()),
        ("xe_path", strs(&XE_PATH)),
        ("xe_planning_cases_kg", Value::List(cases)),
        ("mission_xe_load", get(get(g2, "xe_input")?, "mission_xe_load")?.clone()),
        ("hall_on_xe", hall_reason(raw)),
        ("icp_xe_chemistry", chem_status(raw, "XE")),
        ("status", st(EvalStatus::NotEvaluated)),
    ]);
    let dom = dict(vec![
        ("role", s("Xe is the contingency / emergency supply mode (A9.19); the loaded cases are planning / sensitivity cases, not a selected load")),
        ("uncertainty", s("not quantified: Xe operation not evaluated")),
    ]);
    Ok(row(
        "RFP-XE-CONTINGENCY",
        req,
        thr,
        raw_v,
        dom,
        evidence(
            EvalStatus::NotEvaluated,
            "none (declared supply mode and path only)",
            "Xe operation of the Hall + ICP not evaluated",
        ),
        assessment("NOT_EVALUATED", "Xe capability not demonstrated (HC-10 capability evidence absent)".into(), vec![]),
    ))
}

fn row_thrust(
    t: &Thresholds,
    raw: &RawPhysics,
    evals: &Value,
    hc08q: Option<&Value>,
    sustained: bool,
) -> AssessResult<Value> {
    let (id, gate, req) = if sustained {
        ("RFP-THRUST-12MN-SUSTAINED", "HC-01", "sustained thrust basis >= 12 mN")
    } else {
        ("RFP-THRUST-25MN-CAPABILITY", "HC-02", "demonstrated / capability target 25 mN")
    };
    let thr = threshold(t, gate, vec![("units", s("N"))]);
    let rec = if sustained { &raw.thrust } else { &raw.thrust_capability };
    let raw_v = dict(vec![
        ("thrust_N", dget(rec, "value").unwrap_or(Value::Null)),
        ("objective_record", rec.clone()),
        ("hall", hall_reason(raw)),
        ("status", st(if rec.truthy() { EvalStatus::IncompleteEvidence } else { EvalStatus::NotEvaluated })),
    ]);
    let dom = dict(vec![
        ("hall_model_domain", s("credible Hall transport set EMPTY (P5-Xe not identifiable; P5-N2 v1 INCONCLUSIVE, permanent); no design-specific Hall map")),
        ("uncertainty", s("two-layer Hall uncertainty: layer 2 (transferable closures) is empty")),
    ]);
    let c = gate_row(evals, gate)?;
    let mut gates = vec![c.clone()];
    let mut status = from_constraint(c)?;
    if sustained {
        if let Some(q) = hc08q {
            gates.push(summarize_hc08(q)?);
            if !eq_str(get(q, "status")?, crate::gates::C_MET) && status == "COMPLIES" {
                status = "INCOMPLETE_EVIDENCE";
            }
        }
    }
    Ok(row(
        id,
        req,
        thr,
        raw_v,
        dom,
        evidence(
            EvalStatus::NotEvaluated,
            "none",
            "thrust exists only from an admitted Hall member with a design-specific map, or a measured H-1 thrust",
        ),
        assessment(
            status,
            if sustained {
                format!("{gate} and HC-08 statewise; {}", py_str(get(c, "basis")?))
            } else {
                format!("{gate}; {}", py_str(get(c, "basis")?))
            },
            gates,
        ),
    ))
}

fn row_power(t: &Thresholds, raw: &RawPhysics, evals: &Value) -> AssessResult<Value> {
    let thr = threshold(
        t,
        "HC-03",
        vec![("units", s("W")), ("note", s("A9.30 sec. 5: assessment only; bus_power_boundary_a9_v2"))],
    );
    let req = "bus power < 1.5 kW";
    let (led, _obj) = match (&raw.bus_ledger, &raw.bus_objective) {
        (Ok(l), Ok(o)) => (l, o),
        (Err(e), _) | (_, Err(e)) => return Ok(model_error_row("RFP-PBUS-LT-1500W", req, thr, e)),
    };
    let lower = crate::py::float(get(led, "P_bus_lower_bound_W")?)?;
    let led_status = py_str(get(led, "status")?);
    let raw_status = if led_status == "COMPLETE" { EvalStatus::Evaluated } else { EvalStatus::IncompleteEvidence };
    let raw_v = dict(vec![
        ("boundary", get(led, "boundary_version")?.clone()),
        ("configuration", get(led, "configuration")?.clone()),
        ("ledger_status", get(led, "status")?.clone()),
        ("P_bus_W", get(led, "P_bus_W")?.clone()),
        ("P_bus_lower_bound_W", get(led, "P_bus_lower_bound_W")?.clone()),
        ("n_tbd_terms", Value::int(crate::py::as_list(get(led, "tbd")?)?.len() as i64)),
        ("power_basis", get(led, "power_basis")?.clone()),
        ("load_evidence_classes", get(led, "load_evidence_classes")?.clone()),
        ("startup_step_ledgers_registered", Value::int(raw.startup_ledgers.len() as i64)),
        ("flight_cathode_heater_keeper_loads", s("NONE (A9.30; C1 GROUND_REFERENCE_ONLY)")),
        ("status", st(raw_status)),
        ("source", s("abep_subsystems::power::official_flight_ledger / objective::bus_power_official")),
    ]);
    let limit = t.limit("HC-03").ok_or_else(|| AssessError::new("ConfigurationError", "HC-03 missing"))?;
    let dom = dict(vec![
        ("uncertainty", s("TBD loads and supply efficiencies; the lower bound sums the evidenced terms only")),
        ("lower_bound_reaches_limit", Value::Bool(lower >= limit)),
    ]);
    let c = gate_row(evals, "HC-03")?;
    let mut gates = vec![c.clone()];
    let gate_rec = if raw.startup_ledgers.is_empty() {
        dict(vec![
            ("check", s("rfp_power_gate")),
            ("run", Value::Bool(false)),
            ("reason", s("no registered start-up step ledger (row 108: the gate covers start-up transients)")),
        ])
    } else {
        let g = rfp_power_gate(t, led, &Value::List(raw.startup_ledgers.clone()))?;
        dict(vec![("check", s("rfp_power_gate")), ("run", Value::Bool(true)), ("verdict", get(&g, "verdict")?.clone())])
    };
    gates.push(gate_rec);
    let mut status = from_constraint(c)?;
    let mut basis = format!("HC-03: {}", py_str(get(c, "basis")?));
    if status != "COMPLIES" && status != "DOES_NOT_COMPLY" && lower >= limit {
        status = "DOES_NOT_CLOSE";
        basis = format!(
            "the parametric lower bound {} W reaches the {} W limit (not a measured P_bus,1ms,max)",
            fmt_g(lower),
            fmt_g(limit)
        );
    }
    Ok(row(
        "RFP-PBUS-LT-1500W",
        req,
        thr,
        raw_v,
        dom,
        evidence(raw_status, "ledger load classes (TBD terms present)", "official ledger status and TBD terms"),
        assessment(status, basis, gates),
    ))
}

fn row_mass(t: &Thresholds, raw: &RawPhysics, evals: &Value) -> AssessResult<Value> {
    let thr = threshold(t, "HC-04", vec![("units", s("kg"))]);
    let req = "complete wet mass < 40 kg";
    let (rec, gates, wm) = match (&raw.mass_record, &raw.mass_gates, &raw.wet_mass_objective) {
        (Ok(r), Ok(g), Ok(w)) => (r, g, w),
        (Err(e), _, _) | (_, Err(e), _) | (_, _, Err(e)) => {
            return Ok(model_error_row("RFP-WET-MASS-LT-40KG", req, thr, e))
        }
    };
    let roll = &crate::py::as_list(get(rec, "rollups")?)?[0];
    let mut wet = abep_types::pyjson::Dict::new();
    let mut per_case = Vec::new();
    let mut ref_kg = Vec::new();
    let limit = t.limit("HC-04").ok_or_else(|| AssessError::new("ConfigurationError", "HC-04 missing"))?;
    for w in crate::py::as_list(get(roll, "wet")?)? {
        if !eq_str(get(w, "reference")?, "HARD_40_WET") {
            continue;
        }
        let case = crate::py::float(get(w, "xe_case_kg")?)?;
        let wk = crate::py::float(get(w, "wet_known_kg")?)?;
        wet.insert(abep_types::pyjson::float_repr(case), Value::Float(wk));
        per_case.push(dict(vec![
            ("xe_case_kg", Value::Float(case)),
            ("wet_planning_kg", Value::Float(wk)),
            ("closes_on_planning_basis", Value::Bool(wk < limit)),
            ("governed_record_state", get(w, "state")?.clone()),
        ]));
        ref_kg.push(crate::py::float(get(w, "reference_kg")?)?);
    }
    if per_case.is_empty() {
        return Err(AssessError::new("MODEL_ERROR", "no governed HARD_40_WET case in the mass record"));
    }
    let g2 = &crate::py::as_list(gates)?[1];
    let raw_v = dict(vec![
        ("record", s(abep_subsystems::mass::v5::RECORD_REL)),
        ("record_sha256", s(abep_subsystems::mass::v5::RECORD_SHA256)),
        ("dry_known_kg", get(roll, "dry_known_kg")?.clone()),
        ("wet_known_kg_by_xe_case_kg", Value::Dict(wet)),
        ("mission_xe_load", get(get(g2, "xe_input")?, "mission_xe_load")?.clone()),
        (
            "wet_mass_objective",
            dict(vec![("status", get(wm, "status")?.clone()), ("value", get(wm, "value")?.clone())]),
        ),
        ("status", st(EvalStatus::IncompleteEvidence)),
        ("source", s("abep_subsystems::mass::v5 (pinned record), mass_gates, wet_mass::wet_mass_pinned")),
    ]);
    let dom = dict(vec![
        ("uncertainty", s("planning MEV values with the 10 % bid system margin (A9.26); no CBE and no measured mass; AL-07 PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT (AFI-02-RA1 open)")),
        ("governed_cases", s("the loaded Xe planning cases of the record; no favourable Xe load is selected (A9.31 sec. 18 Q6; mission Xe load not admitted)")),
    ]);
    let n_close =
        per_case.iter().filter(|c| matches!(dget(c, "closes_on_planning_basis"), Ok(Value::Bool(true)))).count();
    let (status, basis) = if n_close == 0 {
        (
            "DOES_NOT_CLOSE",
            format!(
                "wet planning mass >= {} kg at every governed Xe case ({} of {})",
                fmt_g(limit),
                per_case.len(),
                per_case.len()
            ),
        )
    } else if n_close == per_case.len() {
        ("INCOMPLETE_EVIDENCE", "closes on planning values at every governed case; planning values never establish compliance (no CBE / measured mass)".to_string())
    } else {
        (
            "INCOMPLETE_EVIDENCE",
            format!(
                "closes on planning values at {n_close} of {} governed cases; no Xe load is selected",
                per_case.len()
            ),
        )
    };
    let consistent = ref_kg.iter().all(|r| *r == limit);
    let hc04 = gate_row(evals, "HC-04")?.clone();
    let mut a = assessment(status, basis, vec![hc04, g2.clone()]);
    if let Value::Dict(d) = &mut a {
        d.insert("per_case", Value::List(per_case));
        d.insert(
            "governed_record_reference",
            dict(vec![
                ("reference_kg", Value::List(ref_kg.iter().map(|x| Value::Float(*x)).collect())),
                ("equals_configured_limit", Value::Bool(consistent)),
                ("note", s("the record's own HARD_40_WET states are carried as context, never rewritten")),
            ]),
        );
    }
    Ok(row(
        "RFP-WET-MASS-LT-40KG",
        req,
        thr,
        raw_v,
        dom,
        evidence(
            EvalStatus::IncompleteEvidence,
            "planning-allocation (owner MEV allocations / MEV planning floors)",
            "budget evaluation without CBE or measured mass (RVM-06 INCOMPLETE_EVIDENCE)",
        ),
        a,
    ))
}

fn row_compat(t: &Thresholds, raw: &RawPhysics, evals: &Value) -> AssessResult<Value> {
    let thr = threshold(t, "HC-10", vec![("units", s("-"))]);
    let req = "atmospheric + Xe compatibility";
    let arch = match &raw.architecture {
        Ok(a) => a,
        Err(e) => return Ok(model_error_row("RFP-ATM-XE-COMPATIBILITY", req, thr, e)),
    };
    let raw_v = dict(vec![
        ("supply_modes", Value::List(arch.supply_modes.clone())),
        ("air_path", strs(&AIR_PATH)),
        ("xe_path", strs(&XE_PATH)),
        ("hall_on_air_and_xe", hall_reason(raw)),
        ("icp_air_chemistry", chem_status(raw, "AIR")),
        ("icp_xe_chemistry", chem_status(raw, "XE")),
        ("propellant_capability_record", raw.propellant_capability.clone()),
        ("status", st(EvalStatus::NotEvaluated)),
    ]);
    let dom = dict(vec![
        (
            "mode_separation",
            s("separate supply modes; mixed Xe / air compositions OUT_OF_DOMAIN in chemistry v1 (A9.31 OQ-CHEM-10)"),
        ),
        ("uncertainty", s("not quantified: neither mode is evaluated end to end")),
    ]);
    let pp = propellant_paths_check(arch, &paths_value())?;
    let c = gate_row(evals, "HC-10")?;
    let status = from_constraint(c)?;
    Ok(row(
        "RFP-ATM-XE-COMPATIBILITY",
        req,
        thr,
        raw_v,
        dom,
        evidence(EvalStatus::NotEvaluated, "none (structure declared)", "air AND Xe operation not demonstrated"),
        assessment(
            status,
            format!("HC-10: {}; paths {}", py_str(get(c, "basis")?), py_str(get(&pp, "structure")?)),
            vec![
                c.clone(),
                dict(vec![
                    ("check", s("propellant_paths_check")),
                    ("structure", get(&pp, "structure")?.clone()),
                    ("status", get(&pp, "status")?.clone()),
                    ("reason", get(&pp, "reason")?.clone()),
                ]),
            ],
        ),
    ))
}

/// The objective records today: the admitted bus and wet-mass objectives; nothing else is produced.
fn objective_values(raw: &RawPhysics) -> Value {
    let ok = |r: &AssessResult<Value>| r.as_ref().cloned().unwrap_or(Value::Null);
    dict(vec![
        ("thrust_N", raw.thrust.clone()),
        ("thrust_capability_N", raw.thrust_capability.clone()),
        ("P_bus_W", ok(&raw.bus_objective)),
        ("m_wet_kg", ok(&raw.wet_mass_objective)),
        ("propellant_capability", raw.propellant_capability.clone()),
    ])
}

/// The constraint matrix on the given raw records.
pub fn constraint_matrix(t: &Thresholds, raw: &RawPhysics, repo: &Path) -> AssessResult<Value> {
    let evals = evaluate_constraints(t, &objective_values(raw))?;
    let hc08q = match &raw.design_states {
        Ok(ds) => Some(hc08(t, raw, ds)?),
        Err(_) => None,
    };
    let rows = vec![
        row_alt(t, raw)?,
        row_atm(t, raw)?,
        row_xe(t, raw)?,
        row_thrust(t, raw, &evals, hc08q.as_ref(), true)?,
        row_thrust(t, raw, &evals, None, false)?,
        row_power(t, raw, &evals)?,
        row_mass(t, raw, &evals)?,
        row_compat(t, raw, &evals)?,
    ];
    let gng = match &raw.rvm {
        Ok(r) => {
            let g = r.gng_icp_01()?;
            let ev = icp_gate::evaluate(get(g, "criteria")?, get(g, "evidence")?, repo, &r.proposal_text()?)?;
            let replay = r.replay_cells()?;
            let n_ok =
                replay.iter().filter(|x| matches!(dget(x, "reproduces_committed"), Ok(Value::Bool(true)))).count();
            dict(vec![
                ("GNG-ICP-01", ev.clone()),
                (
                    "lock1_release_reportable",
                    Value::Bool(icp_gate::lock1_release_reportable(&Value::List(vec![dict(vec![
                        ("status", get(&ev, "status")?.clone()),
                        ("mandatory", Value::Bool(true)),
                    ])]))?),
                ),
                ("rvm_gate_snapshot", r.gate_snapshot()?),
                (
                    "rvm_replay",
                    dict(vec![
                        ("cells", Value::int(replay.len() as i64)),
                        ("reproduce_committed", Value::int(n_ok as i64)),
                    ]),
                ),
                ("rvm_sha256", s(r.sha256.as_str())),
            ])
        }
        Err(e) => dict(vec![("status", st(EvalStatus::ModelError)), ("error", s(e.to_string()))]),
    };
    let mut counts = abep_types::pyjson::Dict::new();
    for v in ASSESSMENT_VOCABULARY {
        let n = rows
            .iter()
            .filter(|r| eq_str(&get(get(r, "rfp_assessment_status").unwrap(), "status").unwrap().clone(), v))
            .count();
        counts.insert(v, Value::int(n as i64));
    }
    Ok(dict(vec![
        ("schema", s(SCHEMA)),
        ("architecture", s("hall_icp_neutralizer")),
        ("acceptance", s("docs/rust_migration/contracts/NI-ABEP-ASSESS-RFP-MATRIX/acceptance_v1.json")),
        ("config_manifest_sha256", s(t.manifest_sha256.as_str())),
        ("row_fields", strs(&ROW_FIELDS)),
        ("assessment_vocabulary", strs(&ASSESSMENT_VOCABULARY)),
        ("rows", Value::List(rows)),
        (
            "engineering_gates",
            dict(vec![
                ("hard_constraints", evals),
                ("HC-05", hc05(t, raw.neutralization.as_ref())?),
                ("rvm_and_icp_gate", gng),
            ]),
        ),
        (
            "neutralization",
            dict(vec![
                ("quantities", neutralization_quantities(raw.neutralization.as_ref())),
                ("icp_flight_hall_on", s(ICP_FLIGHT_HALL_ON)),
            ]),
        ),
        ("assessment_status_counts", Value::Dict(counts)),
        ("raw_inputs_digest_sha256", s(abep_provenance::sha256_hex(raw.canonical().as_bytes()))),
        (
            "what_this_is_not",
            strs(&[
                "not the architecture conclusion (A9.31 sec. 20 belongs to the decisive run with SC-WP-09 / SC-WP-10)",
                "not a relabelling of any raw status",
                "not a threshold change and not RFP document work",
            ]),
        ),
    ]))
}

/// Deterministic JSON of a matrix record.
pub fn to_json(v: &Value) -> AssessResult<String> {
    let mut out = dumps(v, &DumpOptions { indent: Some(1), ensure_ascii: false, ..Default::default() })?;
    out.push('\n');
    Ok(out)
}
