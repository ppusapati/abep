//! The NP-MISSION-INTEGRATION v1 model: typed inputs, the per-state record, statewise envelopes, the schedule
//! integration with exact time / propellant accounting, and the mass ledger (prereg sections inputs, state_fields,
//! applicability, derivation_rules, schedule_semantics, equations, status_propagation, conservation).
//!
//! [`integrate`] is a pure function of its inputs: it reads no file (addendum 01, FT-10 (a)).

use super::exact::ExactSum;
use super::quantity::{
    derive, severity, worst, worst_of, Field, Label, Parametric, Quantity, Reason, Uncertainty, PARAMETRIC_BOUND,
    PARAMETRIC_PLANNING_CASE,
};
use super::{ARCHITECTURE, MODEL_ID, MODEL_VERSION, PREREG_SHA256};
use abep_types::{AbepError, AbepResult, EvalStatus};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

/// Seconds per hour (EQ-01).
pub const S_PER_H: f64 = 3600.0;

pub const MISSION_SCHEDULE_NOT_REGISTERED: &str = "MISSION_SCHEDULE_NOT_REGISTERED";
pub const STRUCTURAL_ZERO_BY_ROUTING: &str = "STRUCTURAL_ZERO_BY_ROUTING";
pub const STRUCTURAL_ZERO_NON_FIRING: &str = "STRUCTURAL_ZERO_NON_FIRING";
pub const ROUTING_NOT_REGISTERED: &str = "ROUTING_NOT_REGISTERED";
pub const XE_LOAD_NOT_FROZEN: &str = "XE_LOAD_NOT_FROZEN";

/// Segment / record modes (AS-02). NON_FIRING is not a supply mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
pub enum Mode {
    #[serde(rename = "AIR_PRIMARY")]
    AirPrimary,
    #[serde(rename = "XE_CONTINGENCY")]
    XeContingency,
    #[serde(rename = "NON_FIRING")]
    NonFiring,
}

impl Mode {
    pub const ALL: [Mode; 3] = [Mode::AirPrimary, Mode::XeContingency, Mode::NonFiring];

    pub fn as_str(self) -> &'static str {
        match self {
            Mode::AirPrimary => "AIR_PRIMARY",
            Mode::XeContingency => "XE_CONTINGENCY",
            Mode::NonFiring => "NON_FIRING",
        }
    }

    pub fn parse(s: &str) -> Option<Mode> {
        Mode::ALL.into_iter().find(|m| m.as_str() == s)
    }

    pub fn firing(self) -> bool {
        self != Mode::NonFiring
    }
}

/// ICP gas routing (AS-04; A9.1 HIQ-06).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum IcpGasMode {
    #[serde(rename = "G-REUSE")]
    GReuse,
    #[serde(rename = "G-ATM")]
    GAtm,
    #[serde(rename = "G-XE")]
    GXe,
}

impl IcpGasMode {
    pub fn as_str(self) -> &'static str {
        match self {
            IcpGasMode::GReuse => "G-REUSE",
            IcpGasMode::GAtm => "G-ATM",
            IcpGasMode::GXe => "G-XE",
        }
    }
}

/// INPUT field keys of IN-STATE (SF-05..SF-17), units in the same order.
pub const INPUT_KEYS: [(&str, &str); 13] = [
    ("intake_capture_kg_s", "kg s-1"),
    ("drag_intake_N", "N"),
    ("p_feed_Pa", "Pa"),
    ("T_feed_K", "K"),
    ("mdot_atm_delivered_kg_s", "kg s-1"),
    ("mdot_hall_anode_kg_s", "kg s-1"),
    ("mdot_icp_dedicated_kg_s", "kg s-1"),
    ("I_d_A", "A"),
    ("I_ecap_A", "A"),
    ("P_bus_W", "W"),
    ("thrust_N", "N"),
    ("drag_body_N", "N"),
    ("thermal_t_max_K", "K"),
];

/// ENV and environment-derived keys (SF-01..SF-04).
pub const ENV_KEYS: [(&str, &str); 9] = [
    ("rho_kg_m3", "kg m-3"),
    ("fO", "1"),
    ("fN2", "1"),
    ("fO2", "1"),
    ("n_O_m3", "m-3"),
    ("T_K", "K"),
    ("v_orbital_m_s", "m s-1"),
    ("freestream_mass_flux_kg_m2_s", "kg m-2 s-1"),
    ("ao_flux_m2_s", "m-2 s-1"),
];

/// DERIVED keys (SF-18..SF-22).
pub const DERIVED_KEYS: [(&str, &str); 5] = [
    ("drag_total_N", "N"),
    ("t_minus_d_N", "N"),
    ("mdot_xe_tank_kg_s", "kg s-1"),
    ("mdot_atm_consumed_kg_s", "kg s-1"),
    ("feed_balance_kg_s", "kg s-1"),
];

/// Applicability table: fields NOT_APPLICABLE in `mode`.
pub fn not_applicable(mode: Mode) -> &'static [&'static str] {
    match mode {
        Mode::AirPrimary => &[],
        Mode::XeContingency => &["mdot_atm_delivered_kg_s", "feed_balance_kg_s"],
        Mode::NonFiring => &[
            "mdot_atm_delivered_kg_s",
            "feed_balance_kg_s",
            "p_feed_Pa",
            "T_feed_K",
            "I_d_A",
            "I_ecap_A",
            "mdot_hall_anode_kg_s",
            "mdot_icp_dedicated_kg_s",
        ],
    }
}

/// INPUT keys that a (state, mode) record must carry.
pub fn required_inputs(mode: Mode) -> Vec<&'static str> {
    let na = not_applicable(mode);
    INPUT_KEYS
        .iter()
        .map(|(k, _)| *k)
        .filter(|k| !(na.contains(k) || (mode == Mode::NonFiring && *k == "thrust_N")))
        .collect()
}

fn units_of(key: &str) -> &'static str {
    INPUT_KEYS
        .iter()
        .chain(ENV_KEYS.iter())
        .chain(DERIVED_KEYS.iter())
        .find(|(k, _)| *k == key)
        .map(|(_, u)| *u)
        .unwrap_or("-")
}

fn model(msg: impl Into<String>) -> AbepError {
    AbepError::Model { message: msg.into() }
}

/// Refuse conventional-cathode vocabulary in an identifier (AS-03, FT-15). Tokens are assembled at run time.
pub fn refuse_cathode_vocabulary(what: &str, s: &str) -> AbepResult<()> {
    let low = s.to_lowercase().replace(&["cath", "odeless"].concat(), "");
    let tokens = [
        ["cath", "ode"].concat(),
        ["kee", "per"].concat(),
        ["hea", "ter"].concat(),
        ["la", "b6"].concat(),
        ["c1", "_"].concat(),
        ["hol", "low"].concat(),
    ];
    match tokens.iter().find(|t| low.contains(t.as_str())) {
        Some(t) => Err(model(format!("AS-03: {what} {s:?} carries the excluded vocabulary {t:?} (no flight cathode)"))),
        None => Ok(()),
    }
}

/// Mission horizons (IN-SCN).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Horizons {
    pub mission_hours_h: f64,
    pub mission_hours_label: String,
    pub firing_hours_h: f64,
    pub firing_hours_label: String,
    pub source: String,
}

/// Environment values of one state (IN-ENV, the design layer's view).
#[derive(Debug, Clone, PartialEq, Serialize)]
#[allow(non_snake_case)]
pub struct EnvValues {
    pub alt_km: f64,
    pub rho_kg_m3: f64,
    pub fO: f64,
    pub fN2: f64,
    pub fO2: f64,
    pub n_O_m3: f64,
    pub T_K: f64,
    pub v_orbital_m_s: f64,
}

/// One state of the frozen environment.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct EnvState {
    pub state_id: String,
    pub required: bool,
    pub nominal_mission_scenario: bool,
    pub labels: Vec<String>,
    pub status: EvalStatus,
    pub reasons: Vec<Reason>,
    pub values: Option<EnvValues>,
    pub source: String,
}

/// Inputs of one (state, mode) cell (IN-STATE).
#[derive(Debug, Clone, PartialEq)]
pub struct StateModeInputs {
    pub quantities: BTreeMap<String, Quantity>,
    /// Required unless the mode is NON_FIRING (where it is NOT_APPLICABLE and must be None).
    pub hall_state: Option<Label>,
}

/// One registered planning value of the Xe load (GR-15), carried as a parametric case.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct PlanningCase {
    pub m_xe_kg: f64,
    pub source: String,
}

/// Mission-level mass inputs (IN-MASS).
#[derive(Debug, Clone, PartialEq)]
pub struct MassInputs {
    pub m_dry_kg: Quantity,
    pub m_xe_loaded_kg: Quantity,
    pub xe_planning_cases: Vec<PlanningCase>,
    pub xe_reserve_kg: Quantity,
    pub xe_residual_kg: Quantity,
}

/// One schedule segment (SCH-01). `mode` is kept as text so that an unknown / mixed mode can be refused.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Segment {
    pub segment_id: String,
    pub mode: String,
    pub state_id: String,
    pub duration_h: f64,
}

/// One schedule event (SCH-02).
#[derive(Debug, Clone, PartialEq)]
pub struct Event {
    pub event_id: String,
    pub segment_id: String,
    pub kind: String,
    pub count: i64,
    pub xe_kg_per_event: Quantity,
    pub atm_kg_per_event: Quantity,
}

/// A registered mission schedule (IN-SCHED).
#[derive(Debug, Clone, PartialEq)]
pub struct Schedule {
    pub segments: Vec<Segment>,
    pub events: Vec<Event>,
    pub evidence_class: String,
    pub source: String,
}

/// Provenance carried by the record (DET-02).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Provenance {
    pub rust_commit: String,
    pub input_hashes: BTreeMap<String, String>,
}

/// Every input of one integration.
#[derive(Debug, Clone, PartialEq)]
pub struct MissionInputs {
    pub configuration: String,
    pub horizons: Horizons,
    pub env: Vec<EnvState>,
    pub icp_gas_mode: IcpGasMode,
    pub states: BTreeMap<(String, Mode), StateModeInputs>,
    pub mass: MassInputs,
    pub schedule: Option<Schedule>,
    pub provenance: Provenance,
}

// ------------------------------------------------------------------------------------------------ record

/// One (state, mode) cell of the record.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ModeRecord {
    pub fields: BTreeMap<String, Field>,
    pub hall_state: Option<Label>,
    pub state_status: EvalStatus,
    pub domain_status: EvalStatus,
    pub evidence_status: EvalStatus,
}

/// One state of the record.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct StateRecord {
    pub state_id: String,
    pub required: bool,
    pub nominal_mission_scenario: bool,
    pub labels: Vec<String>,
    pub environment_status: EvalStatus,
    pub environment_source: String,
    pub modes: BTreeMap<String, ModeRecord>,
}

/// EQ-12 statewise envelope of one field and mode.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Envelope {
    pub field: String,
    pub mode: String,
    pub units: String,
    pub n_states: usize,
    pub status_counts: BTreeMap<String, usize>,
    pub worst_status: EvalStatus,
    pub min: Option<f64>,
    pub min_state: Option<String>,
    pub max: Option<f64>,
    pub max_state: Option<String>,
    pub parametric_min: Option<f64>,
    pub parametric_max: Option<f64>,
}

/// One conservation result (a numerical self-check, never a requirement).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ConservationCheck {
    pub id: String,
    pub evaluated: bool,
    pub holds: Option<bool>,
    pub detail: String,
}

/// EQ-03 time totals and the SCH-03 accounting.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct TimeAccounting {
    pub h_sched_h: f64,
    pub h_fire_h: f64,
    pub h_air_h: f64,
    pub h_xe_h: f64,
    pub h_coast_h: f64,
    pub residual_vs_mission_hours_h: f64,
    pub residual_vs_firing_hours_h: f64,
    pub closes_mission_hours_exactly: bool,
    pub closes_firing_hours_exactly: bool,
}

/// The schedule block of the record.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ScheduleRecord {
    pub registered: bool,
    pub status: EvalStatus,
    pub reasons: Vec<Reason>,
    pub source: Option<String>,
    pub n_segments: usize,
    pub n_events: usize,
    pub time_accounting: Option<TimeAccounting>,
    pub totals: BTreeMap<String, Quantity>,
    pub conservation: Vec<ConservationCheck>,
}

/// One Xe planning-case ledger (EQ-06).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct PlanningLedger {
    pub m_xe_loaded_kg: f64,
    pub source: String,
    pub m_xe_end_kg: Quantity,
    pub m_wet_end_kg: Quantity,
}

/// The mass block (EQ-05..EQ-07).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct MassRecord {
    pub m_dry_kg: Quantity,
    pub m_xe_loaded_kg: Quantity,
    pub xe_reserve_kg: Quantity,
    pub xe_residual_kg: Quantity,
    pub m_xe_end_kg: Quantity,
    pub m_xe_usable_end_kg: Quantity,
    pub m_wet_start_kg: Quantity,
    pub m_wet_end_kg: Quantity,
    pub planning_cases: Vec<PlanningLedger>,
    pub conservation: Vec<ConservationCheck>,
}

/// The parametric bound PB-AO (EQ-13).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct AoBound {
    pub status: EvalStatus,
    pub label: &'static str,
    pub lower_m2: Option<f64>,
    pub upper_m2: Option<f64>,
    pub min_flux_state: Option<String>,
    pub max_flux_state: Option<String>,
    pub basis: String,
    pub evidence_status_of_fluence: EvalStatus,
    pub reasons: Vec<Reason>,
}

/// Status summary.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct StatusSummary {
    pub n_states: usize,
    pub n_cells: usize,
    pub field_status_counts: BTreeMap<String, BTreeMap<String, usize>>,
    pub worst_state_status: EvalStatus,
    pub reason_codes: BTreeSet<String>,
}

/// The mission record (IF-MIS-v1).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct MissionRecord {
    pub model_id: &'static str,
    pub model_version: &'static str,
    pub prereg_sha256: &'static str,
    pub implementation: &'static str,
    pub validation_status: &'static str,
    pub architecture: &'static str,
    pub icp_gas_mode: IcpGasMode,
    pub horizons: Horizons,
    pub provenance: Provenance,
    pub states: Vec<StateRecord>,
    pub envelopes: Vec<Envelope>,
    pub ao_fluence_bound: AoBound,
    pub schedule: ScheduleRecord,
    pub mass: MassRecord,
    pub status_summary: StatusSummary,
}

impl MissionRecord {
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("record serializes")
    }

    pub fn state(&self, state_id: &str) -> Option<&StateRecord> {
        self.states.iter().find(|s| s.state_id == state_id)
    }

    /// The field of (state, mode), if present.
    pub fn field(&self, state_id: &str, mode: Mode, key: &str) -> Option<&Field> {
        self.state(state_id)?.modes.get(mode.as_str())?.fields.get(key)
    }
}

// ------------------------------------------------------------------------------------------------ state records

fn env_field(st: &EnvState, key: &str) -> AbepResult<Quantity> {
    let units = units_of(key);
    match (&st.values, st.status) {
        (Some(v), EvalStatus::Evaluated) => {
            let x = match key {
                "rho_kg_m3" => v.rho_kg_m3,
                "fO" => v.fO,
                "fN2" => v.fN2,
                "fO2" => v.fO2,
                "n_O_m3" => v.n_O_m3,
                "T_K" => v.T_K,
                "v_orbital_m_s" => v.v_orbital_m_s,
                "freestream_mass_flux_kg_m2_s" => v.rho_kg_m3 * v.v_orbital_m_s,
                "ao_flux_m2_s" => v.n_O_m3 * v.v_orbital_m_s,
                _ => return Err(model(format!("unknown environment key {key}"))),
            };
            Quantity::evaluated(units, x, "model-derived", st.source.clone())
        }
        _ => {
            let status = if st.status == EvalStatus::Evaluated { EvalStatus::ModelError } else { st.status };
            let mut q = Quantity::absent(
                units,
                Reason::new(
                    "ENVIRONMENT_STATE_NOT_EVALUATED",
                    status,
                    format!("state {}: environment {status}", st.state_id),
                ),
            )?;
            q.reasons.extend(st.reasons.iter().cloned());
            Ok(q)
        }
    }
}

fn routed(
    units: &str,
    mode: Mode,
    gas: IcpGasMode,
    table: &str,
    q: &BTreeMap<String, Quantity>,
) -> AbepResult<Quantity> {
    let get = |k: &str| q.get(k).ok_or_else(|| model(format!("routing {table}: input {k} missing")));
    let sum = |keys: &[&str]| -> AbepResult<Quantity> {
        let ops: Vec<&Quantity> = keys.iter().map(|k| get(k)).collect::<AbepResult<_>>()?;
        derive(units, &format!("{table} {} {}: {}", mode.as_str(), gas.as_str(), keys.join(" + ")), &ops, |v| {
            v.iter().skip(1).fold(v[0], |a, b| a + b)
        })
    };
    let unregistered = || {
        Quantity::absent(
            units,
            Reason::new(
                ROUTING_NOT_REGISTERED,
                EvalStatus::IncompleteEvidence,
                format!("{table}: {} in {} has no registered routing (AS-04)", gas.as_str(), mode.as_str()),
            ),
        )
    };
    match (table, mode, gas) {
        (_, Mode::NonFiring, _) => Ok(Quantity::structural_zero(units, STRUCTURAL_ZERO_NON_FIRING)),
        ("R-XE", Mode::XeContingency, IcpGasMode::GReuse) => sum(&["mdot_hall_anode_kg_s"]),
        ("R-XE", Mode::XeContingency, IcpGasMode::GAtm) => unregistered(),
        ("R-XE", Mode::XeContingency, IcpGasMode::GXe) => sum(&["mdot_hall_anode_kg_s", "mdot_icp_dedicated_kg_s"]),
        ("R-XE", Mode::AirPrimary, IcpGasMode::GXe) => sum(&["mdot_icp_dedicated_kg_s"]),
        ("R-XE", Mode::AirPrimary, _) => Ok(Quantity::structural_zero(units, STRUCTURAL_ZERO_BY_ROUTING)),
        ("R-ATM", Mode::AirPrimary, IcpGasMode::GAtm) => sum(&["mdot_hall_anode_kg_s", "mdot_icp_dedicated_kg_s"]),
        ("R-ATM", Mode::AirPrimary, _) => sum(&["mdot_hall_anode_kg_s"]),
        ("R-ATM", Mode::XeContingency, IcpGasMode::GAtm) => unregistered(),
        ("R-ATM", Mode::XeContingency, _) => Ok(Quantity::structural_zero(units, STRUCTURAL_ZERO_BY_ROUTING)),
        _ => Err(model(format!("unknown routing table {table}"))),
    }
}

fn mode_record(st: &EnvState, mode: Mode, gas: IcpGasMode, inp: &StateModeInputs) -> AbepResult<ModeRecord> {
    let tag = format!("{}/{}", st.state_id, mode.as_str());
    let na = not_applicable(mode);
    let required = required_inputs(mode);
    for k in inp.quantities.keys() {
        refuse_cathode_vocabulary("input key", k)?;
        if !required.contains(&k.as_str()) {
            return Err(model(format!("{tag}: input {k} is not a registered input of this mode")));
        }
    }
    let mut q: BTreeMap<String, Quantity> = BTreeMap::new();
    for k in &required {
        let x = inp.quantities.get(*k).ok_or_else(|| model(format!("{tag}: input {k} missing (no default)")))?;
        x.validate().map_err(|e| model(format!("{tag}/{k}: {e}")))?;
        if x.units != units_of(k) {
            return Err(model(format!("{tag}/{k}: units {:?} != registered {:?}", x.units, units_of(k))));
        }
        q.insert((*k).to_string(), x.clone());
    }
    let hall_state = match (mode, &inp.hall_state) {
        (Mode::NonFiring, None) => None,
        (Mode::NonFiring, Some(_)) => return Err(model(format!("{tag}: hall_state is NOT_APPLICABLE in NON_FIRING"))),
        (_, None) => return Err(model(format!("{tag}: hall_state missing (no default)"))),
        (_, Some(l)) => {
            l.validate().map_err(|e| model(format!("{tag}/hall_state: {e}")))?;
            if let Some(s) = &l.label {
                refuse_cathode_vocabulary("hall_state label", s)?;
            }
            Some(l.clone())
        }
    };
    if mode == Mode::NonFiring {
        q.insert("thrust_N".into(), Quantity::structural_zero("N", STRUCTURAL_ZERO_NON_FIRING));
    }
    let mut fields: BTreeMap<String, Field> = BTreeMap::new();
    for (k, _) in ENV_KEYS {
        fields.insert(k.to_string(), Field::Q(env_field(st, k)?));
    }
    let drag_total =
        derive("N", "SF-18 drag_intake_N + drag_body_N", &[&q["drag_intake_N"], &q["drag_body_N"]], |v| v[0] + v[1])?;
    let t_minus_d = derive("N", "SF-19 thrust_N - drag_total_N", &[&q["thrust_N"], &drag_total], |v| v[0] - v[1])?;
    let xe = routed("kg s-1", mode, gas, "R-XE", &q)?;
    let atm = routed("kg s-1", mode, gas, "R-ATM", &q)?;
    if mode == Mode::AirPrimary {
        let bal = derive(
            "kg s-1",
            "SF-22 mdot_atm_delivered_kg_s - mdot_atm_consumed_kg_s",
            &[&q["mdot_atm_delivered_kg_s"], &atm],
            |v| v[0] - v[1],
        )?;
        fields.insert("feed_balance_kg_s".into(), Field::Q(bal));
    }
    fields.insert("drag_total_N".into(), Field::Q(drag_total));
    fields.insert("t_minus_d_N".into(), Field::Q(t_minus_d));
    fields.insert("mdot_xe_tank_kg_s".into(), Field::Q(xe));
    fields.insert("mdot_atm_consumed_kg_s".into(), Field::Q(atm));
    for (k, v) in q {
        fields.insert(k, Field::Q(v));
    }
    for k in na {
        fields.insert(
            k.to_string(),
            Field::NotApplicable { not_applicable: format!("{} (prereg applicability table)", mode.as_str()) },
        );
    }
    let mut statuses: Vec<EvalStatus> = fields.values().filter_map(Field::quantity).map(|x| x.status).collect();
    if let Some(l) = &hall_state {
        statuses.push(l.status);
    }
    let state_status = worst_of(statuses.iter().copied());
    let domain_status = worst_of(
        statuses
            .iter()
            .copied()
            .filter(|s| matches!(s, EvalStatus::OutOfDomain | EvalStatus::ModelError))
            .chain([st.status]),
    );
    let evidence_status = worst_of(
        statuses.iter().copied().filter(|s| matches!(s, EvalStatus::NotEvaluated | EvalStatus::IncompleteEvidence)),
    );
    Ok(ModeRecord { fields, hall_state, state_status, domain_status, evidence_status })
}

fn envelopes(states: &[StateRecord]) -> Vec<Envelope> {
    let mut out = Vec::new();
    for mode in Mode::ALL {
        let keys: BTreeSet<String> =
            states.iter().filter_map(|s| s.modes.get(mode.as_str())).flat_map(|m| m.fields.keys().cloned()).collect();
        for key in keys {
            let cells: Vec<(&str, &Quantity)> = states
                .iter()
                .filter_map(|s| {
                    s.modes
                        .get(mode.as_str())
                        .and_then(|m| m.fields.get(&key))
                        .and_then(Field::quantity)
                        .map(|q| (s.state_id.as_str(), q))
                })
                .collect();
            if cells.is_empty() {
                continue;
            }
            let mut counts = BTreeMap::new();
            for (_, q) in &cells {
                *counts.entry(q.status.as_str().to_string()).or_insert(0) += 1;
            }
            let worst_status = worst_of(cells.iter().map(|(_, q)| q.status));
            let ext = |f: &dyn Fn(&Quantity) -> Option<f64>| -> Option<(f64, &str, f64, &str)> {
                let mut it = cells.iter();
                let (s0, q0) = it.next()?;
                let v0 = f(q0)?;
                let (mut lo, mut los, mut hi, mut his) = (v0, *s0, v0, *s0);
                for (s, q) in it {
                    let v = f(q)?;
                    if v < lo {
                        lo = v;
                        los = s;
                    }
                    if v > hi {
                        hi = v;
                        his = s;
                    }
                }
                Some((lo, los, hi, his))
            };
            let ev = if worst_status.is_evaluated() { ext(&|q: &Quantity| q.value) } else { None };
            let par = if worst_status.is_evaluated() { None } else { ext(&|q: &Quantity| q.value_or_parametric()) };
            out.push(Envelope {
                field: key.clone(),
                mode: mode.as_str().to_string(),
                units: cells[0].1.units.clone(),
                n_states: cells.len(),
                status_counts: counts,
                worst_status,
                min: ev.map(|e| e.0),
                min_state: ev.map(|e| e.1.to_string()),
                max: ev.map(|e| e.2),
                max_state: ev.map(|e| e.3.to_string()),
                parametric_min: par.map(|e| e.0),
                parametric_max: par.map(|e| e.2),
            });
        }
    }
    out
}

fn ao_bound(env: &[EnvState], h_m: f64) -> AbepResult<AoBound> {
    let basis = "PB-AO: [min_s, max_s] ao_flux_m2_s x (H_M x 3600 s/h); bounds the fluence of every schedule whose \
                 segments use states of the frozen set; the states carry no time weights (A9.14 S9.7)"
        .to_string();
    let fluxes: Vec<(&str, AbepResult<Quantity>)> =
        env.iter().map(|s| (s.state_id.as_str(), env_field(s, "ao_flux_m2_s"))).collect();
    let mut reasons = vec![Reason::new(
        MISSION_SCHEDULE_NOT_REGISTERED,
        EvalStatus::NotEvaluated,
        "the evidence-qualified fluence needs a registered schedule (SCH-05)",
    )];
    let mut vals = Vec::new();
    let mut status = EvalStatus::Evaluated;
    for (sid, q) in fluxes {
        let q = q?;
        status = worst(status, q.status);
        match q.value {
            Some(v) => vals.push((sid, v)),
            None => reasons.extend(q.reasons.iter().map(|r| r.tagged(sid))),
        }
    }
    if !status.is_evaluated() || vals.is_empty() {
        return Ok(AoBound {
            status: if vals.is_empty() { worst(status, EvalStatus::ModelError) } else { status },
            label: PARAMETRIC_BOUND,
            lower_m2: None,
            upper_m2: None,
            min_flux_state: None,
            max_flux_state: None,
            basis,
            evidence_status_of_fluence: EvalStatus::NotEvaluated,
            reasons,
        });
    }
    let (mut lo, mut hi) = (vals[0], vals[0]);
    for &(s, v) in &vals[1..] {
        if v < lo.1 {
            lo = (s, v);
        }
        if v > hi.1 {
            hi = (s, v);
        }
    }
    let seconds = h_m * S_PER_H;
    Ok(AoBound {
        status: EvalStatus::Evaluated,
        label: PARAMETRIC_BOUND,
        lower_m2: Some(lo.1 * seconds),
        upper_m2: Some(hi.1 * seconds),
        min_flux_state: Some(lo.0.to_string()),
        max_flux_state: Some(hi.0.to_string()),
        basis,
        evidence_status_of_fluence: EvalStatus::NotEvaluated,
        reasons,
    })
}

// ------------------------------------------------------------------------------------------------ schedule

/// Accumulator of one schedule total (EQ-02, SP-03).
#[derive(Debug, Clone, Default)]
struct Acc {
    ev: ExactSum,
    par: ExactSum,
    status: Option<EvalStatus>,
    reasons: Vec<Reason>,
    par_complete: bool,
    any_par: bool,
    classes: BTreeSet<String>,
}

impl Acc {
    fn new() -> Self {
        Acc { par_complete: true, ..Default::default() }
    }

    fn status(&self) -> EvalStatus {
        self.status.unwrap_or(EvalStatus::Evaluated)
    }

    /// Add `q * factor` (factor = seconds, or an event count).
    fn push(&mut self, q: &Quantity, factor: f64, tag: &str) -> AbepResult<()> {
        self.status = Some(worst(self.status(), q.status));
        self.reasons.extend(q.reasons.iter().map(|r| r.tagged(tag)));
        if let Some(v) = q.value {
            let c = v * factor;
            self.ev.add(c)?;
            self.par.add(c)?;
            self.classes.insert(q.evidence_class.clone());
        } else if let Some(p) = &q.parametric {
            self.any_par = true;
            self.par.add(p.value * factor)?;
        } else {
            self.par_complete = false;
        }
        Ok(())
    }

    /// `sum_i sign_i * acc_i` (exact).
    fn combine(terms: &[(&Acc, f64)]) -> AbepResult<Acc> {
        let mut out = Acc::new();
        for (a, sign) in terms {
            out.status = Some(worst(out.status(), a.status()));
            out.reasons.extend(a.reasons.iter().cloned());
            out.par_complete &= a.par_complete;
            out.any_par |= a.any_par;
            out.classes.extend(a.classes.iter().cloned());
            if *sign > 0.0 {
                out.ev.add_sum(&a.ev)?;
                out.par.add_sum(&a.par)?;
            } else {
                out.ev.sub_sum(&a.ev)?;
                out.par.sub_sum(&a.par)?;
            }
        }
        Ok(out)
    }

    fn finish(&self, units: &str, source: &str) -> AbepResult<Quantity> {
        let status = self.status();
        let mut reasons = self.reasons.clone();
        reasons.sort();
        reasons.dedup();
        let evidence_class = if status.is_evaluated() {
            let c: Vec<&String> = self.classes.iter().filter(|c| c.as_str() != "structural").collect();
            match c.as_slice() {
                [] => "structural".to_string(),
                [one] => (*one).clone(),
                _ => "model-derived".to_string(),
            }
        } else {
            "none".to_string()
        };
        let q = Quantity {
            units: units.to_string(),
            status,
            value: status.is_evaluated().then(|| self.ev.value()),
            parametric: (!status.is_evaluated() && self.any_par && self.par_complete).then(|| Parametric {
                value: self.par.value(),
                label: super::quantity::PARAMETRIC.to_string(),
                basis: "schedule integral of evidence values and parametric values (DR-02 / SP-03)".to_string(),
            }),
            evidence_class,
            uncertainty: Uncertainty::NotQuantified,
            source: source.to_string(),
            reasons,
        };
        q.validate()?;
        Ok(q)
    }
}

fn absent_totals(status: EvalStatus, reasons: &[Reason]) -> AbepResult<BTreeMap<String, Quantity>> {
    let mut out = BTreeMap::new();
    for (k, u) in TOTAL_KEYS {
        let mut q =
            Quantity::absent(u, reasons.first().cloned().unwrap_or_else(|| Reason::new("SCHEDULE", status, "")))?;
        q.status = status;
        q.reasons = reasons.to_vec();
        q.validate()?;
        out.insert(k.to_string(), q);
    }
    Ok(out)
}

/// Schedule totals (EQ-03..EQ-11), key and units.
pub const TOTAL_KEYS: [(&str, &str); 18] = [
    ("H_sched_h", "h"),
    ("H_fire_h", "h"),
    ("H_air_h", "h"),
    ("H_xe_h", "h"),
    ("H_coast_h", "h"),
    ("M_atm_delivered_kg", "kg"),
    ("M_atm_consumed_kg", "kg"),
    ("M_atm_events_kg", "kg"),
    ("M_atm_balance_kg", "kg"),
    ("M_xe_continuous_kg", "kg"),
    ("M_xe_events_kg", "kg"),
    ("M_xe_total_kg", "kg"),
    ("E_bus_J", "J"),
    ("J_thrust_Ns", "N s"),
    ("J_drag_Ns", "N s"),
    ("J_net_Ns", "N s"),
    ("Phi_AO_m2", "m-2"),
    ("n_start_attempts", "1"),
];

/// Validated schedule pieces.
struct Validated<'a> {
    segs: Vec<(&'a Segment, Mode)>,
    reasons: Vec<Reason>,
    status: EvalStatus,
}

fn validate_schedule<'a>(sch: &'a Schedule, members: &BTreeSet<&str>) -> AbepResult<Validated<'a>> {
    let mut reasons = Vec::new();
    let mut ids = BTreeSet::new();
    let mut segs = Vec::new();
    let mut bad = |code: &str, st: EvalStatus, d: String| reasons.push(Reason::new(code, st, d));
    if !super::quantity::EVIDENCE_CLASSES.contains(&sch.evidence_class.as_str()) {
        bad(
            "SCHEDULE_EVIDENCE_CLASS",
            EvalStatus::ModelError,
            format!("unknown evidence class {:?}", sch.evidence_class),
        );
    }
    for s in &sch.segments {
        refuse_cathode_vocabulary("segment id", &s.segment_id)?;
        refuse_cathode_vocabulary("segment mode", &s.mode)?;
        if s.segment_id.is_empty() || !ids.insert(s.segment_id.as_str()) {
            bad("SEGMENT_ID", EvalStatus::ModelError, format!("segment id {:?} empty or duplicated", s.segment_id));
        }
        let mode = Mode::parse(&s.mode);
        if mode.is_none() {
            bad(
                "SEGMENT_MODE",
                EvalStatus::OutOfDomain,
                format!("segment {}: mode {:?} is not a registered single mode", s.segment_id, s.mode),
            );
        }
        if !members.contains(s.state_id.as_str()) {
            bad(
                "SEGMENT_STATE",
                EvalStatus::OutOfDomain,
                format!("segment {}: state {:?} is not in the frozen set", s.segment_id, s.state_id),
            );
        }
        if !(s.duration_h.is_finite() && s.duration_h > 0.0) {
            bad(
                "SEGMENT_DURATION",
                EvalStatus::OutOfDomain,
                format!("segment {}: duration {} h", s.segment_id, s.duration_h),
            );
        }
        if let Some(m) = mode {
            segs.push((s, m));
        }
    }
    let mut eids = BTreeSet::new();
    for e in &sch.events {
        refuse_cathode_vocabulary("event id", &e.event_id)?;
        refuse_cathode_vocabulary("event kind", &e.kind)?;
        if e.event_id.is_empty() || !eids.insert(e.event_id.as_str()) {
            bad("EVENT_ID", EvalStatus::ModelError, format!("event id {:?} empty or duplicated", e.event_id));
        }
        if !ids.contains(e.segment_id.as_str()) {
            bad(
                "EVENT_SEGMENT",
                EvalStatus::ModelError,
                format!("event {}: unknown segment {:?}", e.event_id, e.segment_id),
            );
        }
        if e.kind != "START_ATTEMPT" {
            bad("EVENT_KIND", EvalStatus::OutOfDomain, format!("event {}: kind {:?}", e.event_id, e.kind));
        }
        if e.count < 0 {
            bad("EVENT_COUNT", EvalStatus::OutOfDomain, format!("event {}: count {}", e.event_id, e.count));
        }
        for (k, q) in [("xe_kg_per_event", &e.xe_kg_per_event), ("atm_kg_per_event", &e.atm_kg_per_event)] {
            q.validate().map_err(|x| model(format!("event {}/{k}: {x}", e.event_id)))?;
            if q.units != "kg" {
                return Err(model(format!("event {}/{k}: units {:?} != kg", e.event_id, q.units)));
            }
        }
    }
    let status = worst_of(reasons.iter().map(|r| r.status));
    Ok(Validated { segs, reasons, status })
}

fn hours_quantity(s: &ExactSum, sch: &Schedule) -> AbepResult<Quantity> {
    Quantity::evaluated("h", s.value(), &sch.evidence_class, format!("schedule {}", sch.source))
}

fn schedule_record(
    inp: &MissionInputs,
    cells: &BTreeMap<(String, Mode), ModeRecord>,
) -> AbepResult<(ScheduleRecord, Option<Acc>)> {
    let Some(sch) = &inp.schedule else {
        let r = vec![Reason::new(
            MISSION_SCHEDULE_NOT_REGISTERED,
            EvalStatus::NotEvaluated,
            "no mission mode / state schedule is registered (OQ-MI-01); the design states carry no time weights",
        )];
        return Ok((
            ScheduleRecord {
                registered: false,
                status: EvalStatus::NotEvaluated,
                reasons: r.clone(),
                source: None,
                n_segments: 0,
                n_events: 0,
                time_accounting: None,
                totals: absent_totals(EvalStatus::NotEvaluated, &r)?,
                conservation: vec![],
            },
            None,
        ));
    };
    let members: BTreeSet<&str> = inp.env.iter().map(|s| s.state_id.as_str()).collect();
    let v = validate_schedule(sch, &members)?;
    let (mut h_all, mut h_fire, mut h_air, mut h_xe) =
        (ExactSum::new(), ExactSum::new(), ExactSum::new(), ExactSum::new());
    for (s, m) in &v.segs {
        if s.duration_h.is_finite() {
            h_all.add(s.duration_h)?;
            if m.firing() {
                h_fire.add(s.duration_h)?;
            }
            match m {
                Mode::AirPrimary => h_air.add(s.duration_h)?,
                Mode::XeContingency => h_xe.add(s.duration_h)?,
                Mode::NonFiring => {}
            }
        }
    }
    let mut r_m = h_all.clone();
    r_m.sub(inp.horizons.mission_hours_h)?;
    let mut r_f = h_fire.clone();
    r_f.sub(inp.horizons.firing_hours_h)?;
    let mut h_coast = h_all.clone();
    h_coast.sub_sum(&h_fire)?;
    let mut id_fire = h_air.clone();
    id_fire.add_sum(&h_xe)?;
    id_fire.sub_sum(&h_fire)?;
    let mut id_coast = h_coast.clone();
    id_coast.add_sum(&h_fire)?;
    id_coast.sub_sum(&h_all)?;
    let ta = TimeAccounting {
        h_sched_h: h_all.value(),
        h_fire_h: h_fire.value(),
        h_air_h: h_air.value(),
        h_xe_h: h_xe.value(),
        h_coast_h: h_coast.value(),
        residual_vs_mission_hours_h: r_m.value(),
        residual_vs_firing_hours_h: r_f.value(),
        closes_mission_hours_exactly: r_m.is_zero(),
        closes_firing_hours_exactly: r_f.is_zero(),
    };
    let mut reasons = v.reasons.clone();
    let mut status = v.status;
    if v.status.is_evaluated() && !(r_m.is_zero() && r_f.is_zero()) {
        status = worst(status, EvalStatus::OutOfDomain);
        reasons.push(Reason::new(
            "SCHEDULE_OUTSIDE_MISSION_SCENARIO",
            EvalStatus::OutOfDomain,
            format!(
                "SCH-03: schedule hours {} (residual {} h vs H_M) / firing hours {} (residual {} h vs H_F) do not realise \
                 mission_scenario_v2 exactly",
                ta.h_sched_h, ta.residual_vs_mission_hours_h, ta.h_fire_h, ta.residual_vs_firing_hours_h
            ),
        ));
    }
    let cons_t = ConservationCheck {
        id: "CONS-T1".into(),
        evaluated: true,
        holds: Some(r_m.is_zero() && r_f.is_zero() && id_fire.is_zero() && id_coast.is_zero()),
        detail: "exact: sum dt = H_M, sum firing dt = H_F, H_AIR + H_XE = H_fire, H_coast + H_fire = H_sched".into(),
    };
    let base = ScheduleRecord {
        registered: true,
        status,
        reasons: reasons.clone(),
        source: Some(sch.source.clone()),
        n_segments: sch.segments.len(),
        n_events: sch.events.len(),
        time_accounting: Some(ta),
        totals: BTreeMap::new(),
        conservation: vec![cons_t],
    };
    if !status.is_evaluated() {
        return Ok((ScheduleRecord { totals: absent_totals(status, &reasons)?, ..base }, None));
    }
    // EQ-01 / EQ-02 over the segments.
    let mut acc: BTreeMap<&str, Acc> = BTreeMap::new();
    for (k, _) in TOTAL_KEYS {
        acc.insert(k, Acc::new());
    }
    for (s, m) in &v.segs {
        let cell = cells
            .get(&(s.state_id.clone(), *m))
            .ok_or_else(|| model(format!("no record cell for {}/{}", s.state_id, m.as_str())))?;
        let seconds = s.duration_h * S_PER_H;
        let tag = format!("segment {}", s.segment_id);
        for (total, field) in [
            ("M_atm_delivered_kg", "mdot_atm_delivered_kg_s"),
            ("M_atm_consumed_kg", "mdot_atm_consumed_kg_s"),
            ("M_xe_continuous_kg", "mdot_xe_tank_kg_s"),
            ("E_bus_J", "P_bus_W"),
            ("J_thrust_Ns", "thrust_N"),
            ("J_drag_Ns", "drag_total_N"),
            ("J_net_Ns", "t_minus_d_N"),
            ("Phi_AO_m2", "ao_flux_m2_s"),
        ] {
            match cell.fields.get(field) {
                Some(Field::Q(q)) => acc.get_mut(total).expect("registered total").push(q, seconds, &tag)?,
                Some(Field::NotApplicable { .. }) => {}
                None => return Err(model(format!("record cell {}/{} lacks {field}", s.state_id, m.as_str()))),
            }
        }
    }
    let mut n_starts = 0i64;
    for e in &sch.events {
        let tag = format!("event {}", e.event_id);
        acc.get_mut("M_xe_events_kg").expect("registered").push(&e.xe_kg_per_event, e.count as f64, &tag)?;
        acc.get_mut("M_atm_events_kg").expect("registered").push(&e.atm_kg_per_event, e.count as f64, &tag)?;
        n_starts += e.count;
    }
    let xe_total = Acc::combine(&[(&acc["M_xe_continuous_kg"], 1.0), (&acc["M_xe_events_kg"], 1.0)])?;
    let atm_bal = Acc::combine(&[
        (&acc["M_atm_delivered_kg"], 1.0),
        (&acc["M_atm_consumed_kg"], -1.0),
        (&acc["M_atm_events_kg"], -1.0),
    ])?;
    // CONS-F1: delivered - consumed - events - balance == 0 (exact).
    let mut f1 = atm_bal.ev.clone();
    f1.sub_sum(&acc["M_atm_delivered_kg"].ev)?;
    f1.add_sum(&acc["M_atm_consumed_kg"].ev)?;
    f1.add_sum(&acc["M_atm_events_kg"].ev)?;
    let mut totals = BTreeMap::new();
    let src = format!("schedule {}", sch.source);
    for (k, u) in TOTAL_KEYS {
        let q = match k {
            "H_sched_h" => hours_quantity(&h_all, sch)?,
            "H_fire_h" => hours_quantity(&h_fire, sch)?,
            "H_air_h" => hours_quantity(&h_air, sch)?,
            "H_xe_h" => hours_quantity(&h_xe, sch)?,
            "H_coast_h" => hours_quantity(&h_coast, sch)?,
            "n_start_attempts" => Quantity::evaluated("1", n_starts as f64, &sch.evidence_class, src.clone())?,
            "M_xe_total_kg" => xe_total.finish(u, &format!("EQ-04 {src}"))?,
            "M_atm_balance_kg" => atm_bal.finish(u, &format!("EQ-08 {src}"))?,
            _ => acc[k].finish(u, &format!("EQ-02 {src}"))?,
        };
        totals.insert(k.to_string(), q);
    }
    let mut conservation = base.conservation.clone();
    conservation.push(ConservationCheck {
        id: "CONS-F1".into(),
        evaluated: atm_bal.status().is_evaluated(),
        holds: atm_bal.status().is_evaluated().then(|| f1.is_zero()),
        detail: "exact: M_atm,del - M_atm,cons - M_atm,ev - M_atm,bal = 0".into(),
    });
    Ok((ScheduleRecord { totals, conservation, ..base }, Some(xe_total)))
}

// ------------------------------------------------------------------------------------------------ mass

fn sum_quantity(
    units: &str,
    status: EvalStatus,
    reasons: Vec<Reason>,
    s: &ExactSum,
    class: &str,
    source: &str,
) -> AbepResult<Quantity> {
    let mut reasons = reasons;
    reasons.sort();
    reasons.dedup();
    let q = Quantity {
        units: units.to_string(),
        status,
        value: status.is_evaluated().then(|| s.value()),
        parametric: None,
        evidence_class: if status.is_evaluated() { class.to_string() } else { "none".to_string() },
        uncertainty: Uncertainty::NotQuantified,
        source: source.to_string(),
        reasons,
    };
    q.validate()?;
    Ok(q)
}

fn mass_record(
    mass: &MassInputs,
    xe_total: Option<&Acc>,
    schedule_status: EvalStatus,
    schedule_reasons: &[Reason],
) -> AbepResult<MassRecord> {
    for q in [&mass.m_dry_kg, &mass.m_xe_loaded_kg, &mass.xe_reserve_kg, &mass.xe_residual_kg] {
        q.validate()?;
        if q.units != "kg" {
            return Err(model(format!("mass input units {:?} != kg", q.units)));
        }
    }
    let (m_status, m_reasons, m_ev, m_par): (EvalStatus, Vec<Reason>, Option<&ExactSum>, Option<&ExactSum>) =
        match xe_total {
            Some(a) => {
                let st = a.status();
                (
                    st,
                    a.reasons.clone(),
                    st.is_evaluated().then_some(&a.ev),
                    (a.par_complete && (st.is_evaluated() || a.any_par)).then_some(&a.par),
                )
            }
            None => (schedule_status, schedule_reasons.to_vec(), None, None),
        };
    let reasons_of = |qs: &[&Quantity]| -> Vec<Reason> {
        let mut r: Vec<Reason> = qs.iter().flat_map(|q| q.reasons.iter().cloned()).collect();
        r.extend(m_reasons.iter().cloned());
        r
    };
    // EQ-05: m_xe,end = m_xe,0 - M_xe (exact).
    let st_end = worst(mass.m_xe_loaded_kg.status, m_status);
    let mut end = ExactSum::new();
    if let (Some(m0), Some(mx)) = (mass.m_xe_loaded_kg.value, m_ev) {
        end.add(m0)?;
        end.sub_sum(mx)?;
    }
    let m_xe_end =
        sum_quantity("kg", st_end, reasons_of(&[&mass.m_xe_loaded_kg]), &end, "model-derived", "EQ-05 m_xe,0 - M_xe")?;
    let st_use = worst_of([st_end, mass.xe_reserve_kg.status, mass.xe_residual_kg.status]);
    let mut usable = end.clone();
    if st_use.is_evaluated() {
        usable.sub(mass.xe_reserve_kg.value.unwrap_or(0.0))?;
        usable.sub(mass.xe_residual_kg.value.unwrap_or(0.0))?;
    }
    let m_xe_usable = sum_quantity(
        "kg",
        st_use,
        reasons_of(&[&mass.m_xe_loaded_kg, &mass.xe_reserve_kg, &mass.xe_residual_kg]),
        &usable,
        "model-derived",
        "EQ-05 m_xe,end - reserve - residual (raw, may be negative)",
    )?;
    let st_w0 = worst(mass.m_dry_kg.status, mass.m_xe_loaded_kg.status);
    let mut w0 = ExactSum::new();
    if st_w0.is_evaluated() {
        w0.add(mass.m_dry_kg.value.unwrap_or(0.0))?;
        w0.add(mass.m_xe_loaded_kg.value.unwrap_or(0.0))?;
    }
    let mut w0r = vec![];
    w0r.extend(mass.m_dry_kg.reasons.iter().cloned());
    w0r.extend(mass.m_xe_loaded_kg.reasons.iter().cloned());
    let m_wet_start = sum_quantity("kg", st_w0, w0r, &w0, "model-derived", "EQ-07 m_dry + m_xe,0")?;
    let st_w1 = worst(mass.m_dry_kg.status, st_end);
    let mut w1 = end.clone();
    if st_w1.is_evaluated() {
        w1.add(mass.m_dry_kg.value.unwrap_or(0.0))?;
    }
    let m_wet_end = sum_quantity(
        "kg",
        st_w1,
        reasons_of(&[&mass.m_dry_kg, &mass.m_xe_loaded_kg]),
        &w1,
        "model-derived",
        "EQ-07 m_dry + m_xe,end",
    )?;
    let mut conservation = Vec::new();
    // CONS-M1 (exact expansion closure and reported-value residual within 1 ulp).
    let m1 = if let (true, Some(m0), Some(mx)) = (st_end.is_evaluated(), mass.m_xe_loaded_kg.value, m_ev) {
        let mut r = ExactSum::of(&[m0])?;
        r.sub_sum(mx)?;
        r.sub_sum(&end)?;
        let (mxv, endv) = (mx.value(), end.value());
        let mut rr = ExactSum::of(&[m0, -mxv, -endv])?;
        let scale = m0.abs().max(mxv.abs()).max(endv.abs());
        let ulp = if scale == 0.0 { f64::from_bits(1) } else { f64::from_bits(scale.to_bits() + 1) - scale };
        rr.sub(0.0)?;
        Some(r.is_zero() && rr.value().abs() <= ulp)
    } else {
        None
    };
    conservation.push(ConservationCheck {
        id: "CONS-M1".into(),
        evaluated: m1.is_some(),
        holds: m1,
        detail: "exact: m_xe,0 - M_xe,cont - M_xe,ev - m_xe,end = 0; reported values within 1 ulp".into(),
    });
    let m2 = if st_w0.is_evaluated() && st_w1.is_evaluated() {
        let mut r = w0.clone();
        r.sub_sum(&w1)?;
        if let Some(mx) = m_ev {
            r.sub_sum(mx)?;
        }
        Some(r.is_zero())
    } else {
        None
    };
    conservation.push(ConservationCheck {
        id: "CONS-M2".into(),
        evaluated: m2.is_some(),
        holds: m2,
        detail: "exact: m_wet,0 - m_wet,end - M_xe = 0".into(),
    });
    // EQ-06 planning cases: parametric only, none selected.
    let mut planning_cases = Vec::new();
    for c in &mass.xe_planning_cases {
        if !c.m_xe_kg.is_finite() {
            return Err(model("Q-3: non-finite planning case"));
        }
        let r = Reason::new(
            XE_LOAD_NOT_FROZEN,
            EvalStatus::NotEvaluated,
            format!(
                "planning case {} kg is a SENSITIVITY / PLANNING CASE, not the selected Xe load (A9.25 msg 8 sec. 7)",
                c.m_xe_kg
            ),
        );
        let mut end_q = Quantity::absent("kg", r.clone())?;
        end_q.status = worst(EvalStatus::NotEvaluated, m_status);
        end_q.reasons.extend(m_reasons.iter().cloned());
        let mut wet_q = end_q.clone();
        wet_q.status = worst(end_q.status, mass.m_dry_kg.status);
        wet_q.reasons.extend(mass.m_dry_kg.reasons.iter().cloned());
        if let Some(mp) = m_par {
            let mut e = ExactSum::of(&[c.m_xe_kg])?;
            e.sub_sum(mp)?;
            end_q = end_q.with_parametric(e.value(), PARAMETRIC_PLANNING_CASE, format!("{} - M_xe", c.source))?;
            if let Some(md) = mass.m_dry_kg.value_or_parametric() {
                let mut w = e.clone();
                w.add(md)?;
                wet_q = wet_q.with_parametric(
                    w.value(),
                    PARAMETRIC_PLANNING_CASE,
                    format!("m_dry + {} - M_xe", c.source),
                )?;
            }
        }
        planning_cases.push(PlanningLedger {
            m_xe_loaded_kg: c.m_xe_kg,
            source: c.source.clone(),
            m_xe_end_kg: end_q,
            m_wet_end_kg: wet_q,
        });
    }
    Ok(MassRecord {
        m_dry_kg: mass.m_dry_kg.clone(),
        m_xe_loaded_kg: mass.m_xe_loaded_kg.clone(),
        xe_reserve_kg: mass.xe_reserve_kg.clone(),
        xe_residual_kg: mass.xe_residual_kg.clone(),
        m_xe_end_kg: m_xe_end,
        m_xe_usable_end_kg: m_xe_usable,
        m_wet_start_kg: m_wet_start,
        m_wet_end_kg: m_wet_end,
        planning_cases,
        conservation,
    })
}

// ------------------------------------------------------------------------------------------------ integrate

/// IF-MIS-v1: integrate the mission. Whole-call refusals (MODEL_ERROR): another configuration, malformed inputs,
/// cathode vocabulary, missing (state, mode) cells. Schedule defects give the schedule block their status instead.
pub fn integrate(inp: &MissionInputs) -> AbepResult<MissionRecord> {
    if inp.configuration != ARCHITECTURE {
        return Err(model(format!(
            "AS-01: configuration {:?} refused; NP-MISSION-INTEGRATION v1 covers {ARCHITECTURE} only",
            inp.configuration
        )));
    }
    for (what, v) in [("H_M", inp.horizons.mission_hours_h), ("H_F", inp.horizons.firing_hours_h)] {
        if !(v.is_finite() && v > 0.0) {
            return Err(model(format!("IN-SCN: {what} = {v} is not a finite positive horizon")));
        }
    }
    if inp.env.is_empty() {
        return Err(model("IN-ENV: empty environment"));
    }
    let mut seen = BTreeSet::new();
    for s in &inp.env {
        if !seen.insert(s.state_id.as_str()) {
            return Err(model(format!("IN-ENV: state {} duplicated", s.state_id)));
        }
    }
    for (sid, _) in inp.states.keys() {
        if !seen.contains(sid.as_str()) {
            return Err(model(format!("IN-STATE: inputs for {sid}, which is not in the environment")));
        }
    }
    let mut states = Vec::with_capacity(inp.env.len());
    let mut cells: BTreeMap<(String, Mode), ModeRecord> = BTreeMap::new();
    for st in &inp.env {
        let mut modes = BTreeMap::new();
        for mode in Mode::ALL {
            let i = inp.states.get(&(st.state_id.clone(), mode)).ok_or_else(|| {
                model(format!("IN-STATE: no inputs for {}/{} (CONS-S1; no default)", st.state_id, mode.as_str()))
            })?;
            let r = mode_record(st, mode, inp.icp_gas_mode, i)?;
            cells.insert((st.state_id.clone(), mode), r.clone());
            modes.insert(mode.as_str().to_string(), r);
        }
        states.push(StateRecord {
            state_id: st.state_id.clone(),
            required: st.required,
            nominal_mission_scenario: st.nominal_mission_scenario,
            labels: st.labels.clone(),
            environment_status: st.status,
            environment_source: st.source.clone(),
            modes,
        });
    }
    let envelopes = envelopes(&states);
    let ao = ao_bound(&inp.env, inp.horizons.mission_hours_h)?;
    let (schedule, xe_total) = schedule_record(inp, &cells)?;
    let mass = mass_record(&inp.mass, xe_total.as_ref(), schedule.status, &schedule.reasons)?;
    let mut field_status_counts: BTreeMap<String, BTreeMap<String, usize>> = BTreeMap::new();
    let mut codes = BTreeSet::new();
    let mut worst_state = EvalStatus::Evaluated;
    for s in &states {
        for (m, r) in &s.modes {
            worst_state = worst(worst_state, r.state_status);
            for (k, f) in &r.fields {
                if let Some(q) = f.quantity() {
                    *field_status_counts
                        .entry(format!("{m}/{k}"))
                        .or_default()
                        .entry(q.status.as_str().to_string())
                        .or_insert(0) += 1;
                    codes.extend(q.reasons.iter().map(|x| x.code.clone()));
                }
            }
            if let Some(l) = &r.hall_state {
                *field_status_counts
                    .entry(format!("{m}/hall_state"))
                    .or_default()
                    .entry(l.status.as_str().to_string())
                    .or_insert(0) += 1;
                codes.extend(l.reasons.iter().map(|x| x.code.clone()));
            }
        }
    }
    codes.extend(schedule.reasons.iter().map(|x| x.code.clone()));
    let n_states = states.len();
    Ok(MissionRecord {
        model_id: MODEL_ID,
        model_version: MODEL_VERSION,
        prereg_sha256: PREREG_SHA256,
        implementation: "rust",
        validation_status: "NOT_VALIDATED",
        architecture: ARCHITECTURE,
        icp_gas_mode: inp.icp_gas_mode,
        horizons: inp.horizons.clone(),
        provenance: inp.provenance.clone(),
        states,
        envelopes,
        ao_fluence_bound: ao,
        schedule,
        mass,
        status_summary: StatusSummary {
            n_states,
            n_cells: n_states * Mode::ALL.len(),
            field_status_counts,
            worst_state_status: worst_state,
            reason_codes: codes,
        },
    })
}

/// Severity helper re-exported for callers that merge statuses the same way (SP-01).
pub fn status_severity(s: EvalStatus) -> u8 {
    severity(s)
}
