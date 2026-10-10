//! The decisive 196-state two-layer closure run and the A9.32 classification (NP-HALL-PARAMETRIC-ENVELOPE v1,
//! `docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_v1.json`).
//!
//! Layer (a), physics-feasible, PARAMETRIC / NOT_VALIDATED: the frozen HallThruster.jl parametric envelope of H-1
//! (abep_hall::envelope) under the preregistered favorable-but-defensible rules, plus the non-Hall inputs as registered
//! open conditions or bounds. Layer (b), evidence-qualified / admitted: only admitted components (HallGate, the mission
//! run hook, the RFP constraint matrix, the official power ledger, the mass record). Nothing of layer (a) is copied
//! into layer (b). The classification ([`classify`]) is the preregistered procedure C0..C4; it never manufactures a
//! closure from missing evidence and never a non-closure from missing evidence or planning allocations.

use crate::error::{model_error, AssessError, AssessResult};
use crate::matrix::{constraint_matrix, RawPhysics};
use crate::py::{dict, s, strs};
use crate::thresholds::Thresholds;
use abep_hall::envelope::{self as env, A3Overlay, BzFamilyKind, Envelope, EnvelopePoint, Family, RunStatus};
use abep_mission::integration::today::{run_admitted, TodayOptions};
use abep_mission::integration::{MissionRecord, Mode};
use abep_types::pyjson::{Dict, DumpOptions, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

pub const SCHEMA: &str = "abep_assess_hall_parametric_closure_v1";
pub const MODEL_ID: &str = "NP-HALL-PARAMETRIC-ENVELOPE";

pub const PHYSICALLY_NON_CLOSING: &str = "PHYSICALLY_NON_CLOSING";
pub const SELECT_WITH_EVIDENCE_CONDITIONS: &str = "SELECT_WITH_EVIDENCE_CONDITIONS";
pub const NOT_DETERMINABLE: &str = "NOT_DETERMINABLE";

pub const PHYSICS_FEASIBLE: &str = "PHYSICS_FEASIBLE";
pub const PHYSICS_NON_CLOSING: &str = "PHYSICS_NON_CLOSING";

pub const CLOSES_IN_ENVELOPE: &str = "CLOSES_IN_ENVELOPE";
pub const NON_CLOSING_IN_ENVELOPE: &str = "NON_CLOSING_IN_ENVELOPE";
pub const NOT_DETERMINABLE_IN_ENVELOPE: &str = "NOT_DETERMINABLE_IN_ENVELOPE";
pub const CLOSES: &str = "CLOSES";
pub const NON_CLOSING: &str = "NON_CLOSING";
pub const OPEN: &str = "OPEN";
pub const NOT_EVALUATED: &str = "NOT_EVALUATED";

// Reason codes (prereg classification_rule.a9_31_sec_21_category).
pub const HALL_ENVELOPE_NOT_RUN: &str = "HALL_ENVELOPE_NOT_RUN";
pub const AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED: &str = "AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED";
pub const HALL_NON_CLOSING_UNDER_SURROGATE_BZ: &str = "HALL_NON_CLOSING_UNDER_SURROGATE_BZ";
pub const H1_BZ_NOT_REGISTERED: &str = "H1_BZ_NOT_REGISTERED";
pub const HALL_ENVELOPE_OUT_OF_DOMAIN_POINTS: &str = "HALL_ENVELOPE_OUT_OF_DOMAIN_POINTS";
pub const HALL_ENVELOPE_NUMERICAL_FAILURE_POINTS: &str = "HALL_ENVELOPE_NUMERICAL_FAILURE_POINTS";
pub const HALL_NON_CLOSING_EVALUATED: &str = "HALL_NON_CLOSING_EVALUATED";
pub const HALL_NO_COMMON_HARDWARE: &str = "HALL_NO_COMMON_HARDWARE";
pub const CREDIBLE_SET_NON_EMPTY: &str = "CREDIBLE_SET_NON_EMPTY_NEW_PREREGISTRATION_REQUIRED";
pub const BUS_LEDGER_NOT_COMPLETE: &str = "BUS_LEDGER_NOT_COMPLETE";
pub const PBUS_NON_HALL_LOWER_BOUND_AT_LIMIT: &str = "PBUS_NON_HALL_LOWER_BOUND_AT_LIMIT";
pub const MASS_INCOMPLETE_EVIDENCE: &str = "MASS_INCOMPLETE_EVIDENCE";
pub const LIFE_NOT_EVALUATED: &str = "LIFE_NOT_EVALUATED";
pub const NON_HALL_EVALUABLE_NEEDS_HARNESS_V2: &str = "NON_HALL_EVALUABLE_NEEDS_HARNESS_V2";

/// A9.31 sec. 21 category of a blocker code.
pub fn category(code: &str) -> &'static str {
    match code {
        HALL_NON_CLOSING_EVALUATED | PBUS_NON_HALL_LOWER_BOUND_AT_LIMIT => "FUNDAMENTAL_ARCHITECTURE_LIMIT",
        HALL_NON_CLOSING_UNDER_SURROGATE_BZ | H1_BZ_NOT_REGISTERED | HALL_NO_COMMON_HARDWARE => "DESIGN_VARIABLE_LIMIT",
        AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED | HALL_ENVELOPE_OUT_OF_DOMAIN_POINTS => "MODEL_DOMAIN_LIMIT",
        _ => "MISSING_EVIDENCE",
    }
}

/// Hall-specific point tests (prereg hall_specific_closure.point_tests).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum HallTest {
    T12,
    T25,
    XeFunc,
    /// Addendum A6 XE tests (non-degenerate): T >= HC-01 / HC-02 at P_bus,fav < HC-03.
    XeT12,
    XeT25,
}

impl HallTest {
    pub fn constraint_id(self) -> &'static str {
        match self {
            HallTest::T12 => "HALL_T12_AT_PBUS",
            HallTest::T25 => "HALL_T25_CAPABILITY",
            HallTest::XeFunc => "HALL_XE_FUNCTIONAL_AT_PBUS",
            HallTest::XeT12 => "HALL_XE_T12_AT_PBUS",
            HallTest::XeT25 => "HALL_XE_T25_CAPABILITY_AT_PBUS",
        }
    }

    /// The XE_CONTINGENCY tests when an addendum A6 XE envelope is supplied.
    pub fn of_xe_a6() -> &'static [HallTest] {
        &[HallTest::XeT12, HallTest::XeT25]
    }

    /// The tests of a required mode.
    pub fn of_mode(m: Mode) -> &'static [HallTest] {
        match m {
            Mode::AirPrimary => &[HallTest::T12, HallTest::T25],
            _ => &[HallTest::XeFunc],
        }
    }
}

/// The configured limits used by the point tests (HC-01, HC-02, HC-03) and the non-Hall power lower bound.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct HallLimits {
    pub thrust_min_n: f64,
    pub thrust_capability_n: f64,
    pub p_bus_max_w: f64,
    pub p_non_hall_lb_w: f64,
}

/// Does PASS point `p` pass `test`?
pub fn point_passes(test: HallTest, p: &EnvelopePoint, lim: &HallLimits) -> bool {
    if p.status != RunStatus::Pass {
        return false;
    }
    let (Some(t), Some(pd)) = (p.thrust_n, p.discharge_power_w) else { return false };
    let power_ok = pd + lim.p_non_hall_lb_w < lim.p_bus_max_w;
    power_ok
        && match test {
            HallTest::T12 | HallTest::XeT12 => t >= lim.thrust_min_n,
            HallTest::T25 | HallTest::XeT25 => t >= lim.thrust_capability_n,
            HallTest::XeFunc => t > 0.0,
        }
}

/// One evaluated constraint of a (state, mode).
#[derive(Debug, Clone, PartialEq)]
pub struct Constraint {
    pub id: String,
    pub hall_specific: bool,
    pub status: &'static str,
    /// Closes and may support SELECT_WITH_EVIDENCE_CONDITIONS.
    pub eligible_close: bool,
    /// Non-closing by evaluated physics and may support PHYSICALLY_NON_CLOSING.
    pub eligible_non_close: bool,
    pub codes: Vec<String>,
    pub detail: String,
    /// Evidence conditions a closure under this constraint carries.
    pub evidence_conditions: Vec<String>,
}

impl Constraint {
    pub fn open(id: &str, codes: Vec<String>, detail: impl Into<String>) -> Self {
        Constraint {
            id: id.into(),
            hall_specific: false,
            status: OPEN,
            eligible_close: false,
            eligible_non_close: false,
            codes,
            detail: detail.into(),
            evidence_conditions: vec![],
        }
    }

    fn blocks(&self) -> bool {
        !self.eligible_close && !self.eligible_non_close
    }
}

/// The result of one Hall test over one family's envelope points.
#[derive(Debug, Clone, PartialEq)]
pub struct HallTestResult {
    pub test: HallTest,
    pub family: Option<Family>,
    pub constraint: Constraint,
    pub n_points: usize,
    pub status_counts: Vec<(RunStatus, usize)>,
    pub n_closing: usize,
    /// Hardware configuration (geometry, B shape) -> transport candidates under which some point closes.
    pub closing: BTreeMap<(String, String), BTreeSet<String>>,
    pub best_margin_n: Option<(f64, String)>,
    pub min_pbus_fav_w: Option<(f64, String)>,
    /// Distinct transport candidates among the family's points (robustness denominator).
    pub n_transports: usize,
}

/// A Hall test that cannot be evaluated (no envelope, or a family with no classification role).
pub fn hall_not_evaluated(test: HallTest, code: &str, detail: &str) -> HallTestResult {
    HallTestResult {
        test,
        family: None,
        constraint: Constraint {
            id: test.constraint_id().into(),
            hall_specific: true,
            status: NOT_EVALUATED,
            eligible_close: false,
            eligible_non_close: false,
            codes: vec![code.into()],
            detail: detail.into(),
            evidence_conditions: vec![],
        },
        n_points: 0,
        status_counts: vec![],
        n_closing: 0,
        closing: BTreeMap::new(),
        best_margin_n: None,
        min_pbus_fav_w: None,
        n_transports: 0,
    }
}

/// Evaluate `test` over the envelope points of one family (prereg hall_specific_closure.constraint_status), v1 rules.
pub fn evaluate_hall_test(
    test: HallTest,
    family: Family,
    points: &[&EnvelopePoint],
    lim: &HallLimits,
    bz: BzFamilyKind,
) -> HallTestResult {
    evaluate_hall_test_a3(test, family, points, lim, bz, A3Overlay::NotRun)
}

/// Does PASS point `p` pass `test` at the A3 numerical margin (thrust x (1 - delta_t), P_d x (1 + delta_i))?
pub fn point_passes_at_margin(test: HallTest, p: &EnvelopePoint, lim: &HallLimits, delta_t: f64, delta_i: f64) -> bool {
    let mut q = p.clone();
    q.thrust_n = p.thrust_n.map(|t| t * (1.0 - delta_t));
    q.discharge_power_w = p.discharge_power_w.map(|w| w * (1.0 + delta_i));
    point_passes(test, &q, lim)
}

/// [`evaluate_hall_test`] under the family's addendum A3 overlay: A3_NOT_ADEQUATE makes every PASS and NOT_SUSTAINED
/// point NUMERICS_NOT_CONVERGED (an unknown: never a closure, never an evaluated non-closure); the margin outcome
/// counts a point only if it passes at the margin, and a nominal-only pass is NUMERICS_NOT_CONVERGED.
pub fn evaluate_hall_test_a3(
    test: HallTest,
    family: Family,
    points: &[&EnvelopePoint],
    lim: &HallLimits,
    bz: BzFamilyKind,
    a3: A3Overlay,
) -> HallTestResult {
    if points.is_empty() {
        return hall_not_evaluated(test, HALL_ENVELOPE_NOT_RUN, "no frozen envelope point of this family");
    }
    let threshold = match test {
        HallTest::T12 | HallTest::XeT12 => lim.thrust_min_n,
        HallTest::T25 | HallTest::XeT25 => lim.thrust_capability_n,
        HallTest::XeFunc => 0.0,
    };
    let mut closing: BTreeMap<(String, String), BTreeSet<String>> = BTreeMap::new();
    let mut n_closing = 0;
    let mut best: Option<(f64, String)> = None;
    let mut minp: Option<(f64, String)> = None;
    let mut n_nnc = 0;
    for p in points {
        let nominal = point_passes(test, p, lim);
        let counts = match a3 {
            A3Overlay::NotRun | A3Overlay::Adequate => nominal,
            A3Overlay::Margin { delta_t, delta_i } => nominal && point_passes_at_margin(test, p, lim, delta_t, delta_i),
            A3Overlay::NotAdequate => false,
        };
        if counts {
            n_closing += 1;
            closing.entry(p.case.hardware()).or_default().insert(p.case.transport_id.clone());
        } else if nominal {
            n_nnc += 1;
        }
        if let (RunStatus::Pass, Some(t), Some(pd)) = (p.status, p.thrust_n, p.discharge_power_w) {
            let pf = pd + lim.p_non_hall_lb_w;
            if pf < lim.p_bus_max_w && best.as_ref().is_none_or(|b| t - threshold > b.0) {
                best = Some((t - threshold, p.case.key.clone()));
            }
            let thrust_ok = if test == HallTest::XeFunc { t > 0.0 } else { t >= threshold };
            if thrust_ok && minp.as_ref().is_none_or(|m| pf < m.0) {
                minp = Some((pf, p.case.key.clone()));
            }
        }
    }
    let counts: Vec<(RunStatus, usize)> =
        RunStatus::ALL.iter().map(|s| (*s, points.iter().filter(|p| p.status == *s).count())).collect();
    let n_unknown = points.iter().filter(|p| !a3.evaluated_physics(p.status)).count();
    let mut c = Constraint {
        id: test.constraint_id().into(),
        hall_specific: true,
        status: NOT_DETERMINABLE_IN_ENVELOPE,
        eligible_close: false,
        eligible_non_close: false,
        codes: vec![],
        detail: String::new(),
        evidence_conditions: vec![],
    };
    if n_closing > 0 {
        c.status = CLOSES_IN_ENVELOPE;
        c.eligible_close = true;
        c.detail = format!("{n_closing} of {} grid points pass ({})", points.len(), env::LAYER_A_LABEL);
        c.evidence_conditions = evidence_conditions_hall(bz);
    } else if n_unknown == 0 && n_nnc == 0 {
        c.status = NON_CLOSING_IN_ENVELOPE;
        c.detail = format!("no grid point passes; all {} points are evaluated physics", points.len());
        match bz {
            BzFamilyKind::H1Registered => {
                c.eligible_non_close = true;
                c.codes = vec![HALL_NON_CLOSING_EVALUATED.into()];
            }
            BzFamilyKind::SourcedSurrogate => {
                c.codes = vec![HALL_NON_CLOSING_UNDER_SURROGATE_BZ.into(), H1_BZ_NOT_REGISTERED.into()];
            }
        }
    } else {
        let count = |s: RunStatus| points.iter().filter(|p| p.status == s).count();
        if count(RunStatus::OutOfDomain) > 0 {
            c.codes.push(HALL_ENVELOPE_OUT_OF_DOMAIN_POINTS.into());
        }
        if count(RunStatus::NumericalFailure) > 0 {
            c.codes.push(HALL_ENVELOPE_NUMERICAL_FAILURE_POINTS.into());
        }
        let nnc = match a3 {
            A3Overlay::NotAdequate => points.iter().filter(|p| p.status.is_evaluated_physics()).count(),
            _ => n_nnc,
        };
        if nnc > 0 {
            c.codes.push(env::NUMERICS_NOT_CONVERGED.into());
        }
        c.detail = format!(
            "no grid point passes; {} OUT_OF_DOMAIN, {} NUMERICAL_FAILURE and {nnc} {} points are unknowns ({})",
            count(RunStatus::OutOfDomain),
            count(RunStatus::NumericalFailure),
            env::NUMERICS_NOT_CONVERGED,
            a3.as_str()
        );
    }
    HallTestResult {
        test,
        family: Some(family),
        constraint: c,
        n_points: points.len(),
        status_counts: counts,
        n_closing,
        closing,
        best_margin_n: best,
        min_pbus_fav_w: minp,
        n_transports: points.iter().map(|p| p.case.transport_id.as_str()).collect::<BTreeSet<_>>().len(),
    }
}

/// Evidence conditions of a Hall closure in the parametric layer (prereg classification_rule C3).
pub fn evidence_conditions_hall(bz: BzFamilyKind) -> Vec<String> {
    let mut v = vec![
        "EC-TRANSPORT: an admitted Hall transport member (credible set EMPTY; screening candidates extrapolated to H-1)"
            .to_string(),
    ];
    if bz == BzFamilyKind::SourcedSurrogate {
        v.push("EC-BZ: the H-1 B(z) (FEMM / measured) realises a field of the sourced P5-shape surrogate class".into());
    }
    v.push("EC-DIV: plume divergence beyond the solver's 1-D treatment is not added".into());
    v.push("EC-NUM: numerical adequacy for the H-1 geometry not verified (RG-04)".into());
    v.push("EC-GEOM: geometry is an authorised FEMM analysis point, not a design selection".into());
    v
}

/// One (state, mode) evaluation of layer (a).
#[derive(Debug, Clone, PartialEq)]
pub struct ModeEval {
    pub constraints: Vec<Constraint>,
    pub status: &'static str,
    pub blockers: Vec<String>,
}

/// A required or optional design state.
#[derive(Debug, Clone, PartialEq)]
pub struct StateRef {
    pub state_id: String,
    pub required: bool,
}

/// Inputs of the classification procedure (pure; every file read happens before).
#[derive(Debug, Clone, PartialEq)]
pub struct ClosureInputs {
    pub credible_set_empty: bool,
    pub envelope_ingested: bool,
    pub bz_family_kind: Option<BzFamilyKind>,
    /// Hall tests per required mode (AIR: T12, T25; XE: XE_FUNC).
    pub hall: BTreeMap<Mode, Vec<HallTestResult>>,
    /// Non-Hall constraints per required mode (v1: identical for every state).
    pub non_hall: BTreeMap<Mode, Vec<Constraint>>,
    pub states: Vec<StateRef>,
}

/// Output of the classification procedure.
#[derive(Debug, Clone, PartialEq)]
pub struct ClosureOutcome {
    pub classification: &'static str,
    pub step: &'static str,
    /// (code, number of required (state, mode) cells it blocks), sorted by code.
    pub blockers: Vec<(String, usize)>,
    pub evidence_conditions: Vec<String>,
    pub common_hardware: Vec<(String, String)>,
    pub states: Vec<(StateRef, BTreeMap<Mode, ModeEval>)>,
}

pub const REQUIRED_MODES: [Mode; 2] = [Mode::AirPrimary, Mode::XeContingency];

/// The layer (a) evaluation of one (state, mode) (prereg state_evaluation.state_status_a).
pub fn evaluate_mode(hall: &[HallTestResult], non_hall: &[Constraint]) -> ModeEval {
    let constraints: Vec<Constraint> =
        hall.iter().map(|h| h.constraint.clone()).chain(non_hall.iter().cloned()).collect();
    let status = if constraints.iter().any(|c| c.eligible_non_close) {
        PHYSICS_NON_CLOSING
    } else if !constraints.is_empty() && constraints.iter().all(|c| c.eligible_close) {
        PHYSICS_FEASIBLE
    } else {
        NOT_DETERMINABLE
    };
    let mut blockers: BTreeSet<String> = BTreeSet::new();
    if status == NOT_DETERMINABLE {
        for c in constraints.iter().filter(|c| c.blocks()) {
            blockers.extend(c.codes.iter().cloned());
        }
    }
    ModeEval { constraints, status, blockers: blockers.into_iter().collect() }
}

/// Hardware configurations closing every Hall test of every required mode.
pub fn common_hardware(hall: &BTreeMap<Mode, Vec<HallTestResult>>) -> Vec<(String, String)> {
    let mut acc: Option<BTreeSet<(String, String)>> = None;
    for m in REQUIRED_MODES {
        for t in hall.get(&m).map(Vec::as_slice).unwrap_or_default() {
            let hw: BTreeSet<(String, String)> = t.closing.keys().cloned().collect();
            acc = Some(match acc {
                None => hw,
                Some(a) => a.intersection(&hw).cloned().collect(),
            });
        }
    }
    acc.unwrap_or_default().into_iter().collect()
}

/// The preregistered classification procedure C0..C4.
pub fn classify(inp: &ClosureInputs) -> ClosureOutcome {
    let mut states = Vec::new();
    let mut tally: BTreeMap<String, usize> = BTreeMap::new();
    let (mut any_non_closing, mut all_feasible) = (false, true);
    for st in &inp.states {
        let mut modes = BTreeMap::new();
        for m in REQUIRED_MODES {
            let h = inp.hall.get(&m).map(Vec::as_slice).unwrap_or_default();
            let nh = inp.non_hall.get(&m).map(Vec::as_slice).unwrap_or_default();
            let e = evaluate_mode(h, nh);
            if st.required {
                any_non_closing |= e.status == PHYSICS_NON_CLOSING;
                all_feasible &= e.status == PHYSICS_FEASIBLE;
                for b in &e.blockers {
                    *tally.entry(b.clone()).or_default() += 1;
                }
            }
            modes.insert(m, e);
        }
        states.push((st.clone(), modes));
    }
    let n_required = inp.states.iter().filter(|s| s.required).count();
    let hw = common_hardware(&inp.hall);
    let mut out = ClosureOutcome {
        classification: NOT_DETERMINABLE,
        step: "C4",
        blockers: vec![],
        evidence_conditions: vec![],
        common_hardware: hw.clone(),
        states,
    };
    let cells = n_required * REQUIRED_MODES.len();
    if !inp.credible_set_empty {
        out.step = "C0";
        out.blockers = vec![(CREDIBLE_SET_NON_EMPTY.into(), cells)];
        return out;
    }
    if !inp.envelope_ingested {
        out.step = "C1";
        tally.insert(HALL_ENVELOPE_NOT_RUN.into(), cells);
        out.blockers = tally.into_iter().collect();
        return out;
    }
    if n_required > 0 && any_non_closing {
        out.classification = PHYSICALLY_NON_CLOSING;
        out.step = "C2";
        return out;
    }
    if n_required > 0 && all_feasible {
        if hw.is_empty() {
            out.blockers = vec![(HALL_NO_COMMON_HARDWARE.into(), cells)];
            return out;
        }
        out.classification = SELECT_WITH_EVIDENCE_CONDITIONS;
        out.step = "C3";
        let mut ec: BTreeSet<String> = BTreeSet::new();
        for m in REQUIRED_MODES {
            for h in inp.hall.get(&m).map(Vec::as_slice).unwrap_or_default() {
                ec.extend(h.constraint.evidence_conditions.iter().cloned());
            }
            for c in inp.non_hall.get(&m).map(Vec::as_slice).unwrap_or_default() {
                ec.extend(c.evidence_conditions.iter().cloned());
            }
        }
        out.evidence_conditions = ec.into_iter().collect();
        return out;
    }
    out.blockers = tally.into_iter().collect();
    out
}

// ------------------------------------------------------------------------------------------------ production inputs

pub(crate) fn quantity_codes(
    rec: &MissionRecord,
    state: &str,
    mode: Mode,
    key: &str,
) -> AssessResult<(bool, Vec<String>)> {
    let f = rec.field(state, mode, key).ok_or_else(|| model_error(format!("mission field {key} absent at {state}")))?;
    let q = f.quantity().ok_or_else(|| model_error(format!("mission field {key} NOT_APPLICABLE at {state}")))?;
    let mut codes: Vec<String> = q.reasons.iter().map(|r| r.code.clone()).collect();
    codes.sort();
    codes.dedup();
    Ok((q.status.is_evaluated(), codes))
}

/// Non-Hall constraint read from a mission-record field: OPEN with the field's reason codes; an EVALUATED field is
/// outside what harness v1 evaluates (prereg state_evaluation.non_hall_at_closing_points) and is refused.
fn from_mission(rec: &MissionRecord, states: &[StateRef], mode: Mode, id: &str, key: &str) -> AssessResult<Constraint> {
    let mut codes: BTreeSet<String> = BTreeSet::new();
    for st in states {
        let (evaluated, c) = quantity_codes(rec, &st.state_id, mode, key)?;
        if evaluated {
            return Err(model_error(format!(
                "{NON_HALL_EVALUABLE_NEEDS_HARNESS_V2}: {key} is EVALUATED at {}; harness v1 only carries open inputs",
                st.state_id
            )));
        }
        codes.extend(c);
    }
    Ok(Constraint::open(
        id,
        codes.into_iter().collect(),
        format!("mission run hook field {key}: not evaluated (open condition)"),
    ))
}

/// The registered non-Hall power lower bound and ledger state.
#[derive(Debug, Clone, PartialEq)]
pub struct LedgerBound {
    pub status: String,
    pub n_tbd: usize,
    pub p_non_hall_lb_w: f64,
}

pub fn ledger_bound(repo: &Path) -> AssessResult<LedgerBound> {
    use abep_subsystems::power::official::{official_flight_ledger, MassPowerA9V5};
    use abep_subsystems::power::slots::Slot;
    let mp = MassPowerA9V5::load(repo).map_err(|e| model_error(e.to_string()))?;
    let led = official_flight_ledger(&mp).map_err(|e| model_error(e.to_string()))?;
    let lb = led.items.iter().filter(|i| i.slot != Slot::HallDischarge).map(|i| i.lower_bound_w.unwrap_or(0.0)).sum();
    Ok(LedgerBound { status: led.status.as_str().into(), n_tbd: led.tbd.len(), p_non_hall_lb_w: lb })
}

fn row<'a>(matrix: &'a Value, id: &str) -> AssessResult<&'a Value> {
    matrix
        .as_dict()
        .and_then(|d| d.get("rows"))
        .and_then(Value::as_list)
        .and_then(|rows| {
            rows.iter().find(|r| r.as_dict().and_then(|d| d.get("id")).and_then(Value::as_str) == Some(id))
        })
        .ok_or_else(|| model_error(format!("matrix row {id} absent")))
}

pub(crate) fn row_status(matrix: &Value, id: &str, field: &str) -> AssessResult<String> {
    row(matrix, id)?
        .as_dict()
        .and_then(|d| d.get(field))
        .and_then(Value::as_dict)
        .and_then(|d| d.get("status"))
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| model_error(format!("matrix row {id} {field}.status absent")))
}

/// Matrix rows each required mode needs for layer (b).
pub fn layer_b_rows(m: Mode) -> &'static [&'static str] {
    match m {
        Mode::AirPrimary => &[
            "RFP-ALT",
            "RFP-ATM-PRIMARY",
            "RFP-THRUST-12MN-SUSTAINED",
            "RFP-THRUST-25MN-CAPABILITY",
            "RFP-PBUS-LT-1500W",
            "RFP-WET-MASS-LT-40KG",
            "RFP-ATM-XE-COMPATIBILITY",
        ],
        _ => &["RFP-XE-CONTINGENCY", "RFP-PBUS-LT-1500W", "RFP-WET-MASS-LT-40KG", "RFP-ATM-XE-COMPATIBILITY"],
    }
}

/// Layer (b) status of a (state, mode): EVIDENCE_QUALIFIED_FEASIBLE only when every required RFP matrix row reads
/// COMPLIES (determining evidence) and an admitted Hall member exists; otherwise NOT_EVALUATED.
pub fn layer_b_status(matrix: &Value, m: Mode, credible_set_empty: bool) -> &'static str {
    let comply =
        layer_b_rows(m).iter().all(|id| row_status(matrix, id, "rfp_assessment_status").is_ok_and(|x| x == "COMPLIES"));
    if comply && !credible_set_empty {
        "EVIDENCE_QUALIFIED_FEASIBLE"
    } else {
        NOT_EVALUATED
    }
}

/// Everything the record needs, gathered from the admitted components.
#[derive(Clone)]
pub struct TodayInputs {
    pub thresholds: Thresholds,
    pub limits: HallLimits,
    pub ledger: LedgerBound,
    pub mission: MissionRecord,
    /// (layer, status, detail) of the mission run hook's admitted layers.
    pub mission_layers: Vec<(String, String, String)>,
    pub matrix: Value,
    pub credible_set_empty: bool,
    pub admitted_members: Vec<String>,
    pub states: Vec<StateRef>,
}

pub fn gather(repo: &Path, rust_commit: &str) -> AssessResult<TodayInputs> {
    let t = Thresholds::load(&abep_config::ConfigPaths::repository(repo))?;
    let lim = |id: &str| t.limit(id).ok_or_else(|| model_error(format!("threshold {id} not configured")));
    let ledger = ledger_bound(repo)?;
    let limits = HallLimits {
        thrust_min_n: lim("HC-01")?,
        thrust_capability_n: lim("HC-02")?,
        p_bus_max_w: lim("HC-03")?,
        p_non_hall_lb_w: ledger.p_non_hall_lb_w,
    };
    let gate = abep_hall::status::HallGate::from_repository(&repo.to_string_lossy())?;
    let run = run_admitted(repo, &TodayOptions { design_point: None, rust_commit: rust_commit.into() })?;
    let mission_layers =
        run.layers.iter().map(|l| (l.layer.clone(), l.status.as_str().to_string(), l.detail.clone())).collect();
    let mission = run.record;
    let states =
        mission.states.iter().map(|s| StateRef { state_id: s.state_id.clone(), required: s.required }).collect();
    let matrix = constraint_matrix(&t, &RawPhysics::load_repository(repo), repo)?;
    Ok(TodayInputs {
        thresholds: t,
        limits,
        ledger,
        mission,
        mission_layers,
        matrix,
        credible_set_empty: gate.admitted_members.is_empty(),
        admitted_members: gate.admitted_members,
        states,
    })
}

/// Non-Hall constraints of a required mode (prereg non_hall_inputs), from the admitted components.
pub fn non_hall_constraints(ti: &TodayInputs, m: Mode) -> AssessResult<Vec<Constraint>> {
    let rec = &ti.mission;
    let st = &ti.states;
    let mut v = vec![
        from_mission(
            rec,
            st,
            m,
            "NH-FLOW",
            if m == Mode::AirPrimary { "mdot_atm_delivered_kg_s" } else { "p_feed_Pa" },
        )?,
        from_mission(rec, st, m, "NH-ICP", "I_ecap_A")?,
    ];
    let pb = if ti.ledger.p_non_hall_lb_w >= ti.limits.p_bus_max_w {
        Constraint {
            id: "NH-PBUS".into(),
            hall_specific: false,
            status: NON_CLOSING,
            eligible_close: false,
            eligible_non_close: true,
            codes: vec![PBUS_NON_HALL_LOWER_BOUND_AT_LIMIT.into()],
            detail: format!(
                "non-Hall ledger lower bound {} W >= {} W",
                ti.ledger.p_non_hall_lb_w, ti.limits.p_bus_max_w
            ),
            evidence_conditions: vec![],
        }
    } else if ti.ledger.status != "COMPLETE" {
        Constraint::open(
            "NH-PBUS",
            vec![BUS_LEDGER_NOT_COMPLETE.into()],
            format!(
                "official flight ledger {} ({} TBD terms); non-Hall lower bound {} W used inside the Hall point tests",
                ti.ledger.status, ti.ledger.n_tbd, ti.ledger.p_non_hall_lb_w
            ),
        )
    } else {
        return Err(model_error(format!(
            "{NON_HALL_EVALUABLE_NEEDS_HARNESS_V2}: the official ledger is COMPLETE; harness v1 only carries open inputs"
        )));
    };
    v.push(pb);
    if m == Mode::AirPrimary {
        v.push(from_mission(rec, st, m, "NH-TD", "drag_body_N")?);
    }
    let mass_rfp = row_status(&ti.matrix, "RFP-WET-MASS-LT-40KG", "rfp_assessment_status")?;
    let mass_ev = row_status(&ti.matrix, "RFP-WET-MASS-LT-40KG", "evidence_status")?;
    v.push(Constraint::open(
        "NH-MASS",
        vec![MASS_INCOMPLETE_EVIDENCE.into()],
        format!(
            "RFP matrix wet-mass row: assessment {mass_rfp} on planning values, evidence {mass_ev}; planning allocations \
             are not eligible for PHYSICALLY_NON_CLOSING (HR-07)"
        ),
    ));
    v.push(from_mission(rec, st, m, "NH-THERMAL", "thermal_t_max_K")?);
    v.push(Constraint::open(
        "NH-LIFE",
        vec![LIFE_NOT_EVALUATED.into()],
        "no admitted H-1 erosion / AO / life evaluation (wall_life_trustworthy needs ion_wall_losses = true)",
    ));
    Ok(v)
}

/// Hall tests per required mode: AIR is NOT_EVALUATED (no Hall O / O2 chemistry); XE from the envelope.
pub fn hall_results(env: Option<&Envelope>, lim: &HallLimits) -> BTreeMap<Mode, Vec<HallTestResult>> {
    hall_results_a3(env, lim, A3Overlay::NotRun)
}

/// [`hall_results`] with the XE family's addendum A3 overlay.
pub fn hall_results_a3(
    env: Option<&Envelope>,
    lim: &HallLimits,
    xe_a3: A3Overlay,
) -> BTreeMap<Mode, Vec<HallTestResult>> {
    let mut out = BTreeMap::new();
    out.insert(
        Mode::AirPrimary,
        HallTest::of_mode(Mode::AirPrimary)
            .iter()
            .map(|t| {
                let mut h = hall_not_evaluated(
                    *t,
                    AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED,
                    "no Hall O / O2 chemistry: the AIR layer (a) Hall is NOT_EVALUATED; N2_PROXY is diagnostic only",
                );
                if env.is_none() {
                    h.constraint.codes.push(HALL_ENVELOPE_NOT_RUN.into());
                    h.constraint.codes.sort();
                }
                h
            })
            .collect(),
    );
    let xe = HallTest::of_mode(Mode::XeContingency)
        .iter()
        .map(|t| match env {
            None => hall_not_evaluated(*t, HALL_ENVELOPE_NOT_RUN, "no frozen HallThruster.jl envelope ingested"),
            Some(e) => {
                let pts: Vec<&EnvelopePoint> = e.family_points(Family::Xe).collect();
                evaluate_hall_test_a3(*t, Family::Xe, &pts, lim, e.bz_family_kind, xe_a3)
            }
        })
        .collect();
    out.insert(Mode::XeContingency, xe);
    out
}

// ------------------------------------------------------------------------------------------------ record

fn f(x: f64) -> Value {
    Value::Float(x)
}

fn opt_pair(x: &Option<(f64, String)>) -> Value {
    match x {
        Some((v, k)) => dict(vec![("value", f(*v)), ("key", s(k.clone()))]),
        None => Value::Null,
    }
}

fn constraint_value(c: &Constraint) -> Value {
    dict(vec![
        ("id", s(c.id.clone())),
        ("hall_specific", Value::Bool(c.hall_specific)),
        ("status", s(c.status)),
        ("eligible_close", Value::Bool(c.eligible_close)),
        ("eligible_non_close", Value::Bool(c.eligible_non_close)),
        ("codes", Value::List(c.codes.iter().map(|x| s(x.clone())).collect())),
        ("detail", s(c.detail.clone())),
    ])
}

pub(crate) fn hall_value(h: &HallTestResult) -> Value {
    let closing: Vec<Value> = h
        .closing
        .iter()
        .map(|((g, b), ts)| {
            dict(vec![
                ("geometry_id", s(g.clone())),
                ("bz_shape_id", s(b.clone())),
                ("transports", Value::List(ts.iter().map(|t| s(t.clone())).collect())),
                ("robust_under_transport_set", Value::Bool(h.n_transports > 0 && ts.len() == h.n_transports)),
            ])
        })
        .collect();
    dict(vec![
        ("layer", s(env::LAYER_A_LABEL)),
        ("test", s(h.test.constraint_id())),
        ("family", h.family.map_or(Value::Null, |x| s(x.as_str()))),
        ("constraint", constraint_value(&h.constraint)),
        ("n_points", Value::int(h.n_points as i64)),
        ("run_status_counts", dict(h.status_counts.iter().map(|(k, n)| (k.as_str(), Value::int(*n as i64))).collect())),
        ("n_closing_points", Value::int(h.n_closing as i64)),
        ("closing_hardware", Value::List(closing)),
        ("best_margin_N_at_pbus", opt_pair(&h.best_margin_n)),
        ("min_pbus_fav_W_at_threshold", opt_pair(&h.min_pbus_fav_w)),
        ("evidence_conditions", strs(&h.constraint.evidence_conditions.iter().map(String::as_str).collect::<Vec<_>>())),
    ])
}

fn range(points: &[&EnvelopePoint], get: impl Fn(&EnvelopePoint) -> Option<f64>) -> Value {
    let v: Vec<f64> = points.iter().filter_map(|p| get(p)).collect();
    if v.is_empty() {
        return s(NOT_EVALUATED);
    }
    let mn = v.iter().cloned().fold(f64::INFINITY, f64::min);
    let mx = v.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    dict(vec![("min", f(mn)), ("max", f(mx))])
}

pub(crate) fn envelope_summary(e: Option<&Envelope>) -> Value {
    let Some(e) = e else { return dict(vec![("status", s(NOT_EVALUATED)), ("reason", s(HALL_ENVELOPE_NOT_RUN))]) };
    let mut fams = Dict::new();
    for fam in Family::ALL {
        let pts: Vec<&EnvelopePoint> = e.family_points(fam).collect();
        let pass: Vec<&EnvelopePoint> = pts.iter().copied().filter(|p| p.status == RunStatus::Pass).collect();
        fams.insert(
            fam.as_str(),
            dict(vec![
                ("labels", strs(&fam.labels())),
                ("n_points", Value::int(pts.len() as i64)),
                (
                    "run_status_counts",
                    dict(e.status_counts(fam).iter().map(|(k, n)| (k.as_str(), Value::int(*n as i64))).collect()),
                ),
                ("pass_thrust_N", range(&pass, |p| p.thrust_n)),
                ("pass_discharge_power_W", range(&pass, |p| p.discharge_power_w)),
                ("pass_discharge_current_A", range(&pass, |p| p.discharge_current_a)),
                ("pass_mdot_kg_s", range(&pass, |p| Some(p.case.mdot_kg_s))),
                ("pass_Te_max_eV", range(&pass, |p| p.te_max_ev)),
            ]),
        );
    }
    dict(vec![
        ("status", s("INGESTED")),
        ("layer", s(env::LAYER_A_LABEL)),
        ("manifest", s(e.manifest_rel.clone())),
        ("manifest_sha256", s(e.manifest_sha256.clone())),
        ("raw_sha256", s(e.raw_sha256.clone())),
        ("cases_sha256", s(e.cases_sha256.clone())),
        ("bz_family_kind", s(e.bz_family_kind.as_str())),
        ("families", Value::Dict(fams)),
    ])
}

pub(crate) fn n2_proxy(e: Option<&Envelope>, lim: &HallLimits) -> Value {
    let role = s("NONE: N2_PROXY never enters feasibility or classification (prereg families N2_PROXY)");
    let Some(e) = e else {
        return dict(vec![
            ("label", s(env::N2_PROXY_LABEL)),
            ("classification_role", role),
            ("status", s(NOT_EVALUATED)),
            ("reason", s(HALL_ENVELOPE_NOT_RUN)),
        ]);
    };
    let pts: Vec<&EnvelopePoint> = e.family_points(Family::N2Proxy).collect();
    let tests: Vec<Value> = [HallTest::T12, HallTest::T25]
        .iter()
        .map(|t| hall_value(&evaluate_hall_test(*t, Family::N2Proxy, &pts, lim, e.bz_family_kind)))
        .collect();
    dict(vec![("label", s(env::N2_PROXY_LABEL)), ("classification_role", role), ("tests", Value::List(tests))])
}

/// The closure record of the repository (today: no envelope unless `envelope` is given).
pub fn closure_record(repo: &Path, envelope: Option<&Envelope>, rust_commit: &str) -> AssessResult<Value> {
    let ti = gather(repo, rust_commit)?;
    let (xe_a3, a3_sha) = match envelope {
        Some(_) => env::a3_overlay(repo, Family::Xe).map_err(|e| model_error(e.to_string()))?,
        None => (A3Overlay::NotRun, None),
    };
    let hall = hall_results_a3(envelope, &ti.limits, xe_a3);
    let mut non_hall = BTreeMap::new();
    for m in REQUIRED_MODES {
        non_hall.insert(m, non_hall_constraints(&ti, m)?);
    }
    let inputs = ClosureInputs {
        credible_set_empty: ti.credible_set_empty,
        envelope_ingested: envelope.is_some(),
        bz_family_kind: envelope.map(|e| e.bz_family_kind),
        hall: hall.clone(),
        non_hall: non_hall.clone(),
        states: ti.states.clone(),
    };
    let out = classify(&inputs);
    let mut rec = record_value(&ti, &inputs, &out, envelope);
    if let Value::Dict(d) = &mut rec {
        let mut a3 = Dict::new();
        a3.insert("XE", s(xe_a3.as_str()));
        a3.insert("result", s(env::A3_RESULT_REL));
        a3.insert("result_sha256", a3_sha.map_or(Value::Null, |h| s(&h)));
        a3.insert(
            "rule",
            s("NP-HALL-PARAMETRIC-ENVELOPE addendum A3: A3_NOT_ADEQUATE makes every PASS / NOT_SUSTAINED point of the family NUMERICS_NOT_CONVERGED (unknown); margin: tests at T (1 - delta_T), P_d (1 + delta_I)"),
        );
        d.insert("numerics_a3", Value::Dict(a3));
    }
    Ok(rec)
}

fn mode_key(m: Mode) -> &'static str {
    m.as_str()
}

fn record_value(ti: &TodayInputs, inp: &ClosureInputs, out: &ClosureOutcome, envelope: Option<&Envelope>) -> Value {
    let required: Vec<&(StateRef, BTreeMap<Mode, ModeEval>)> = out.states.iter().filter(|(s, _)| s.required).collect();
    let count = |m: Mode, st: &str| required.iter().filter(|(_, ms)| ms[&m].status == st).count() as i64;
    // Layer (b): admitted components only.
    let mut lb_rows = Dict::new();
    let mut lb_feasible = Dict::new();
    for m in REQUIRED_MODES {
        let mut rows = Dict::new();
        let mut all_comply = true;
        for id in layer_b_rows(m) {
            let st = row_status(&ti.matrix, id, "rfp_assessment_status").unwrap_or_else(|_| "MODEL_ERROR".into());
            all_comply &= st == "COMPLIES";
            rows.insert(*id, s(st));
        }
        lb_rows.insert(mode_key(m), Value::Dict(rows));
        let n = if all_comply && !inp.credible_set_empty { required.len() as i64 } else { 0 };
        lb_feasible.insert(mode_key(m), Value::int(n));
    }
    let lb_keys = ["thrust_N", "I_d_A", "I_ecap_A", "P_bus_W", "drag_body_N", "mdot_atm_delivered_kg_s"];
    let states: Vec<Value> = out
        .states
        .iter()
        .map(|(st, modes)| {
            let mut md = Dict::new();
            for (m, e) in modes {
                let mut cs = Dict::new();
                for c in &e.constraints {
                    cs.insert(c.id.as_str(), s(c.status));
                }
                let mut mf = Dict::new();
                for k in lb_keys {
                    let v = ti.mission.field(&st.state_id, *m, k).and_then(|f| f.quantity()).map(|q| q.status.as_str());
                    if let Some(v) = v {
                        mf.insert(k, s(v));
                    }
                }
                md.insert(
                    mode_key(*m),
                    dict(vec![
                        (
                            "layer_a",
                            dict(vec![
                                ("label", s(env::LAYER_A_LABEL)),
                                ("status", s(e.status)),
                                ("blockers", Value::List(e.blockers.iter().map(|b| s(b.clone())).collect())),
                                ("constraints", Value::Dict(cs)),
                            ]),
                        ),
                        (
                            "layer_b",
                            dict(vec![
                                ("status", s(layer_b_status(&ti.matrix, *m, inp.credible_set_empty))),
                                (
                                    "hall",
                                    s(if inp.credible_set_empty {
                                        "NOT_EVALUATED: credible Hall transport set EMPTY"
                                    } else {
                                        "admitted members present"
                                    }),
                                ),
                                ("mission_fields", Value::Dict(mf)),
                            ]),
                        ),
                    ]),
                );
            }
            let env_status =
                ti.mission.state(&st.state_id).map(|r| r.environment_status.as_str()).unwrap_or("MODEL_ERROR");
            dict(vec![
                ("state_id", s(st.state_id.clone())),
                ("required", Value::Bool(st.required)),
                ("environment_status", s(env_status)),
                ("modes", Value::Dict(md)),
            ])
        })
        .collect();
    let mut hall_v = Dict::new();
    let mut nh_v = Dict::new();
    let mut binding = Dict::new();
    let mut per_mode = Dict::new();
    for m in REQUIRED_MODES {
        hall_v.insert(mode_key(m), Value::List(inp.hall[&m].iter().map(hall_value).collect()));
        nh_v.insert(mode_key(m), Value::List(inp.non_hall[&m].iter().map(constraint_value).collect()));
        let mut rows = Vec::new();
        let mut first: Option<String> = None;
        if let Some((_, ms)) = required.first() {
            for c in &ms[&m].constraints {
                let close = required
                    .iter()
                    .filter(|(_, x)| x[&m].constraints.iter().any(|y| y.id == c.id && y.eligible_close))
                    .count();
                let nonc = required
                    .iter()
                    .filter(|(_, x)| x[&m].constraints.iter().any(|y| y.id == c.id && y.eligible_non_close))
                    .count();
                if first.is_none() && close < required.len() {
                    first = Some(c.id.clone());
                }
                rows.push(dict(vec![
                    ("constraint", s(c.id.clone())),
                    ("hall_specific", Value::Bool(c.hall_specific)),
                    ("n_required_closes", Value::int(close as i64)),
                    ("n_required_non_closing_eligible", Value::int(nonc as i64)),
                    ("n_required_open_or_unknown", Value::int((required.len() - close - nonc) as i64)),
                    ("codes", Value::List(c.codes.iter().map(|x| s(x.clone())).collect())),
                    ("categories", Value::List(c.codes.iter().map(|x| s(category(x))).collect())),
                ]));
            }
        }
        binding.insert(
            mode_key(m),
            dict(vec![("first_blocking_constraint", first.map_or(Value::Null, s)), ("constraints", Value::List(rows))]),
        );
        per_mode.insert(
            mode_key(m),
            dict(vec![
                ("n_required_states", Value::int(required.len() as i64)),
                ("n_physics_feasible_a", Value::int(count(m, PHYSICS_FEASIBLE))),
                ("n_physics_non_closing_a", Value::int(count(m, PHYSICS_NON_CLOSING))),
                ("n_not_determinable_a", Value::int(count(m, NOT_DETERMINABLE))),
            ]),
        );
    }
    let blockers: Vec<Value> = out
        .blockers
        .iter()
        .map(|(c, n)| {
            dict(vec![
                ("code", s(c.clone())),
                ("category", s(category(c))),
                ("n_required_state_modes", Value::int(*n as i64)),
            ])
        })
        .collect();
    let statement = match out.classification {
        PHYSICALLY_NON_CLOSING => {
            "Hall + RF/ICP is physically non-closing under the preregistered favorable-but-defensible envelope"
        }
        SELECT_WITH_EVIDENCE_CONDITIONS => {
            "physically feasible in the parametric layer but not yet experimentally proven (credible Hall set EMPTY)"
        }
        _ => "the A9.32 classification is not determinable with today's inputs; see the blocking list",
    };
    dict(vec![
        ("schema", s(SCHEMA)),
        ("model_id", s(MODEL_ID)),
        ("prereg", dict(vec![("path", s(env::PREREG_REL)), ("sha256", s(env::PREREG_SHA256)), ("lock_sha256", s(env::LOCK_SHA256))])),
        ("architecture", s("hall_icp_neutralizer")),
        ("rust_commit", s(ti.mission.provenance.rust_commit.clone())),
        (
            "inputs",
            dict(vec![
                ("config_manifest_sha256", s(ti.thresholds.manifest_sha256.clone())),
                ("thresholds", dict(vec![
                    ("HC-01_N", f(ti.limits.thrust_min_n)),
                    ("HC-02_N", f(ti.limits.thrust_capability_n)),
                    ("HC-03_W", f(ti.limits.p_bus_max_w)),
                    ("HC-04_kg", ti.thresholds.limit("HC-04").map_or(Value::Null, f)),
                ])),
                ("credible_set", s(if inp.credible_set_empty { "EMPTY" } else { "NON_EMPTY" })),
                ("admitted_members", strs(&ti.admitted_members.iter().map(String::as_str).collect::<Vec<_>>())),
                ("bus_ledger", dict(vec![
                    ("status", s(ti.ledger.status.clone())),
                    ("n_tbd_terms", Value::int(ti.ledger.n_tbd as i64)),
                    ("P_nonHall_LB_W", f(ti.ledger.p_non_hall_lb_w)),
                ])),
                ("mission_prereg_sha256", s(ti.mission.prereg_sha256)),
                (
                    "mission_run_hook_layers",
                    Value::List(
                        ti.mission_layers
                            .iter()
                            .map(|(l, st, d)| dict(vec![("layer", s(l.clone())), ("status", s(st.clone())), ("detail", s(d.clone()))]))
                            .collect(),
                    ),
                ),
                ("n_states", Value::int(out.states.len() as i64)),
                ("n_required_states", Value::int(required.len() as i64)),
            ]),
        ),
        (
            "classification",
            dict(vec![
                ("result", s(out.classification)),
                ("procedure_step", s(out.step)),
                ("statement", s(statement)),
                ("blockers", Value::List(blockers)),
                ("evidence_conditions", strs(&out.evidence_conditions.iter().map(String::as_str).collect::<Vec<_>>())),
                ("common_hardware", Value::List(out.common_hardware.iter().map(|(g, b)| s(format!("{g}|{b}"))).collect())),
            ]),
        ),
        ("envelope", envelope_summary(envelope)),
        ("hall_specific_closure_a", Value::Dict(hall_v)),
        ("non_hall_closure_a", Value::Dict(nh_v)),
        ("binding_constraint", Value::Dict(binding)),
        ("layer_a_counts", Value::Dict(per_mode)),
        ("n2_proxy_diagnostic", n2_proxy(envelope, &ti.limits)),
        ("a9_31_sec_23", sec23(inp, out, envelope, &required)),
        (
            "layer_b",
            dict(vec![
                ("label", s("EVIDENCE_QUALIFIED / ADMITTED ONLY")),
                ("credible_set", s(if inp.credible_set_empty { "EMPTY" } else { "NON_EMPTY" })),
                ("hall", s(if inp.credible_set_empty { "NOT_EVALUATED: credible Hall transport set EMPTY" } else { "admitted members present" })),
                ("rfp_matrix_rows", Value::Dict(lb_rows)),
                ("n_states_evidence_qualified_b", Value::Dict(lb_feasible)),
            ]),
        ),
        ("states", Value::List(states)),
        (
            "what_this_is_not",
            strs(&[
                "not a validation or admission: the credible Hall transport set stays EMPTY and layer (a) never enters layer (b)",
                "not the A9.31 sec. 20 conclusion by itself (the coordinator states it)",
                "not a relabelling of any raw or admitted status",
            ]),
        ),
    ])
}

/// A9.31 sec. 23 items A-H as far as this record can state them (layer (a) unless named; J is the coordinator's).
fn sec23(
    inp: &ClosureInputs,
    out: &ClosureOutcome,
    envelope: Option<&Envelope>,
    required: &[&(StateRef, BTreeMap<Mode, ModeEval>)],
) -> Value {
    let n_req = required.len() as i64;
    let feasible = |m: Mode| required.iter().filter(|(_, x)| x[&m].status == PHYSICS_FEASIBLE).count() as i64;
    let robust = |m: Mode| -> i64 {
        let hall = inp.hall.get(&m).map(Vec::as_slice).unwrap_or_default();
        let robust_hw = !hall.is_empty()
            && hall.iter().all(|h| h.n_transports > 0 && h.closing.values().any(|ts| ts.len() == h.n_transports));
        if robust_hw {
            feasible(m)
        } else {
            0
        }
    };
    let mut per = Dict::new();
    for m in REQUIRED_MODES {
        per.insert(
            m.as_str(),
            dict(vec![
                ("n_required_states", Value::int(n_req)),
                ("B_n_physics_feasible_a", Value::int(feasible(m))),
                ("C_n_robust_under_transport_set_a", Value::int(robust(m))),
            ]),
        );
    }
    let rank = |c: &str| match category(c) {
        "FUNDAMENTAL_ARCHITECTURE_LIMIT" => 0,
        "MODEL_DOMAIN_LIMIT" => 1,
        "DESIGN_VARIABLE_LIMIT" => 2,
        _ => 3,
    };
    let mut ordered: Vec<&(String, usize)> = out.blockers.iter().collect();
    ordered.sort_by(|a, b| (rank(&a.0), std::cmp::Reverse(a.1), &a.0).cmp(&(rank(&b.0), std::cmp::Reverse(b.1), &b.0)));
    let first_codes: Vec<Value> = ordered.iter().map(|(c, _)| s(c.clone())).collect();
    dict(vec![
        (
            "A_feasible_region_a",
            s(match out.classification {
                SELECT_WITH_EVIDENCE_CONDITIONS => "YES (parametric layer)",
                PHYSICALLY_NON_CLOSING => "NO (eligible evaluated non-closure)",
                _ => "NOT_DETERMINABLE",
            }),
        ),
        ("B_C_counts", Value::Dict(per)),
        (
            "D_worst_case_state",
            s("NOT_DETERMINABLE: the Hall envelope is state-independent (vacuum) and every state-dependent input is open"),
        ),
        (
            "E_ranges",
            dict(vec![
                ("hall_envelope_layer_a", s(if envelope.is_some() { "see envelope.families (PASS points)" } else { NOT_EVALUATED })),
                ("drag_T_minus_D", s("NOT_EVALUATED: host-spacecraft drag ICD absent")),
                ("bus_power", s("NOT_EVALUATED: official ledger not complete (lower bound used in the Hall point tests)")),
                ("atmospheric_mass_flow", s("NOT_EVALUATED: no frozen design point")),
                ("icp_electron_current_margin", s("NOT_EVALUATED: NP-ICP-NEUTRALIZER not admitted")),
                ("wet_mass", s("NOT_EVALUATED as physics: planning-value DOES_NOT_CLOSE only (INCOMPLETE_EVIDENCE)")),
            ]),
        ),
        ("F_constraints_closing_a", s("see binding_constraint (n_required_closes per constraint)")),
        ("G_evidence_limited", Value::List(out.blockers.iter().map(|(c, _)| s(c.clone())).collect())),
        (
            "H_dominant_blockers",
            dict(vec![
                ("order", s("A9.31 sec. 21 category (FUNDAMENTAL, MODEL_DOMAIN, DESIGN_VARIABLE, MISSING_EVIDENCE), then blocked cells")),
                ("codes", Value::List(first_codes)),
            ]),
        ),
        ("J_engineering_statement", s("not stated here: the coordinator states the A9.31 sec. 20 / 23 J conclusion")),
    ])
}

/// Deterministic JSON of a closure record.
pub fn to_json(v: &Value) -> AssessResult<String> {
    let mut out =
        abep_types::pyjson::dumps(v, &DumpOptions { indent: Some(1), ensure_ascii: false, ..Default::default() })
            .map_err(AssessError::from)?;
    out.push('\n');
    Ok(out)
}
