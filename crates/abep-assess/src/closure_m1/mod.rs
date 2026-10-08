//! Harness v2 of the decisive 196-state closure run (NP-HALL-PARAMETRIC-ENVELOPE addendum A2,
//! `docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a2_m1_closure_paths.json`).
//!
//! Every required physics path of the M1 exit item is consumed per (state, mode): environment, the F7 / F8 delivered
//! flow (robust set carried unchanged), feed-loop stability, NP-ICP v2 (I_e,cap, bus loads, feed), CPL-HALL-ON-v1 at
//! parametric envelope points, a layer (a) bus_power_boundary_a9_v2 ledger, thermal 2.0.0, mass v5, life, T - D, the
//! XE envelope (v1) and the AIR family (A1). Non-Hall inputs evaluated at points are joint conditions on the Hall
//! closing points. The classification is the v1 procedure C0..C4 verbatim, over per-(state, mode) constraint lists.
//! Layer (a) is PARAMETRIC / NOT_VALIDATED; layer (b) is the v1 admitted-only layer, unchanged.
//!
//! [`gather`] reads the repository (fail closed: a pin that does not verify refuses the record); [`evaluate`] is pure;
//! [`record`] renders the deterministic record and the readiness listing. [`conservation`] adds the addendum A4
//! conservation bounds (step CA4 between C0 and C1; additive: without an eligible A4 failure nothing changes).
//! [`intake`] adds the addendum A5 M2 intake closure (A9.35): a registered intake / gas-path design that misses the A4
//! necessary condition in every surface scenario adds A5-NH-INTAKE (DESIGN_VARIABLE_LIMIT, never eligible).

pub mod conservation;
pub mod conservation_record;
pub mod gather;
pub mod intake;
pub mod intake_record;
pub mod record;

use crate::closure::{
    self as v1, category, evaluate_hall_test, evaluate_mode, evidence_conditions_hall, hall_not_evaluated,
    ClosureOutcome, Constraint, HallLimits, HallTest, HallTestResult, ModeEval, StateRef, TodayInputs,
    CLOSES_IN_ENVELOPE, NON_CLOSING, NOT_DETERMINABLE, NOT_DETERMINABLE_IN_ENVELOPE, NOT_EVALUATED,
    PHYSICALLY_NON_CLOSING, PHYSICS_FEASIBLE, PHYSICS_NON_CLOSING, REQUIRED_MODES, SELECT_WITH_EVIDENCE_CONDITIONS,
};
use abep_hall::envelope::{BzFamilyKind, Envelope, EnvelopePoint, Family, RunStatus};
use abep_mission::integration::Mode;
use abep_subsystems::power::official::MassPowerA9V5;
use abep_subsystems::power::slots::Slot;
use abep_types::pyjson::Value;
use std::collections::{BTreeMap, BTreeSet};

pub const SCHEMA: &str = "abep_assess_hall_parametric_closure_v2";
pub const NP_DIR: &str = abep_hall::envelope::NP_DIR;
pub const A2_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a2_m1_closure_paths.json";
pub const A2_SHA256: &str = "0c9a6b7b00fff125c9338b32c6b0426f8331b290e903a0e1ba6e3a2364e21aa4";
pub const A2_MD_REL: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/PREREG_ADDENDUM_A2.md";
pub const A2_MD_SHA256: &str = "8fe091b4dbb08715d18db28b03e3315d3cfa9ee443ff3af9aa4794ca21ffa8ac";
pub const A2_LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a2_lock.json";
pub const A2_LOCK_SHA256: &str = "774bf7618e0afafa40fe252d782d3112c71f2958ed7fe51b33e9c5d3dba617dd";
/// A1 (AIR family). A2 named it by `addendum_01_air_family` (lane-hall-chem-air, sha256 below); that record was
/// superseded before any AIR run by `prereg_addendum_a1_air_family` (A1 proper, which carries its rules verbatim and adds
/// the bounded launch path). The harness reads A1 proper and checks that it supersedes the A2-named identity.
pub const A1_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a1_air_family.json";
pub const A1_SHA256: &str = "7d7a7ba91f382775a1eed842af83587b0f1fc5b762f85ef68022ac03d23c7b0d";
pub const A1_MD_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/PREREG_ADDENDUM_A1_AIR_FAMILY.md";
pub const A1_MD_SHA256: &str = "d1a3e26b86ddd629aeaa8c3a2f6b0db6ac85a3463c2923f40e29dc5be21a1183";
pub const A1_LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a1_air_family_lock.json";
pub const A1_LOCK_SHA256: &str = "35388e247ffdcc7af2a605e46f29d955ec29875893d3f7342e6411110f3d17a6";
/// The A1 identity A2 names (addendum_01_air_family.json), superseded by A1 proper.
pub const A1_NAMED_IN_A2_SHA256: &str = "4988bdfd4aad30a171c4dae9ffa8d3436ee94c1aaaedcb56a3c06ffe1533dd90";

pub const LAYER_A: &str = abep_hall::envelope::LAYER_A_LABEL;
pub const SYNTHETIC: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";

// Reason codes registered by A2 (classification.category_of_new_codes) and A1.
pub const GAS_PATH_ROBUST_SET_EMPTY: &str = "GAS_PATH_ROBUST_SET_EMPTY";
pub const GAS_PATH_FLOW_BELOW_HALL_CLOSING_MDOT: &str = "GAS_PATH_FLOW_BELOW_HALL_CLOSING_MDOT";
pub const FEED_LOOP_UNSTABLE_EQUILIBRIUM: &str = "FEED_LOOP_UNSTABLE_EQUILIBRIUM";
pub const FEED_CONTROLLER_NOT_REGISTERED: &str = "FEED_CONTROLLER_NOT_REGISTERED";
pub const GASPATH_PER_STATE_VALUES_NOT_SUPPLIED: &str = "GASPATH_PER_STATE_VALUES_NOT_SUPPLIED";
pub const XE_FEED_FLOW_NOT_REGISTERED: &str = "XE_FEED_FLOW_NOT_REGISTERED";
pub const ICP_CAPACITY_NOT_EVALUATED: &str = "ICP_CAPACITY_NOT_EVALUATED";
pub const ICP_CAPACITY_BELOW_HALL_I_D: &str = "ICP_CAPACITY_BELOW_HALL_I_D";
pub const NO_HALL_CLOSING_POINT: &str = "NO_HALL_CLOSING_POINT";
pub const JOINT_CLOSING_POINT_ABSENT: &str = "JOINT_CLOSING_POINT_ABSENT";
pub const THERMAL_LOADS_NOT_EVALUATED: &str = "THERMAL_LOADS_NOT_EVALUATED";
pub const THERMAL_FLIGHT_CASE_NOT_REGISTERED: &str = "THERMAL_FLIGHT_CASE_NOT_REGISTERED";
pub const HALL_WALL_LIFE_INPUTS_NOT_TRUSTWORTHY: &str = "HALL_WALL_LIFE_INPUTS_NOT_TRUSTWORTHY";
pub const ANODE_MATERIAL_OPEN: &str = "ANODE_MATERIAL_OPEN";
pub const ENVIRONMENT_NOT_EVALUATED: &str = "ENVIRONMENT_NOT_EVALUATED";
pub const T_MINUS_D_RULE_NOT_REGISTERED: &str = "T_MINUS_D_EVALUATION_NOT_REGISTERED_IN_A2";
pub const BUS_LEDGER_ABOVE_LIMIT_AT_JOINT_POINTS: &str = "BUS_LEDGER_ABOVE_LIMIT_AT_JOINT_POINTS";
pub const AIR_FAMILY_ADDENDUM_A1_NOT_ON_LINE: &str = "AIR_FAMILY_ADDENDUM_A1_NOT_ON_LINE";
pub const AIR_CHEMISTRY_BOUNDED_NOT_COMPLETE: &str = "AIR_CHEMISTRY_BOUNDED_NOT_COMPLETE";
pub const HALL_NON_CLOSING_UNDER_AIR_ENVELOPE: &str = "HALL_NON_CLOSING_UNDER_AIR_ENVELOPE";
pub const AIR_COMPOSITION_NOT_REGISTERED: &str = "AIR_COMPOSITION_NOT_REGISTERED";
pub const AIR_CHEMISTRY_NOMINAL_ONLY: &str = "AIR_CHEMISTRY_NOMINAL_ONLY";
pub const MATERIALITY_BOUND_REQUIRED_HE: &str = "MATERIALITY_BOUND_REQUIRED_HE";
pub const MATERIALITY_BOUND_REQUIRED_AR: &str = "MATERIALITY_BOUND_REQUIRED_AR";
pub const MASS_CBE_LOWER_BOUND_AT_LIMIT: &str = "MASS_CBE_LOWER_BOUND_AT_LIMIT";
pub const MASS_CBE_ABOVE_LIMIT: &str = "MASS_CBE_ABOVE_LIMIT";
pub const THERMAL_MARGIN_BELOW_HC06: &str = "THERMAL_MARGIN_BELOW_HC06";
pub const LIFE_BELOW_HC07: &str = "LIFE_BELOW_HC07";

/// A9.31 sec. 21 category of a code: A2 / A1 codes first, then the v1 rule.
pub fn category_a2(code: &str) -> &'static str {
    match code {
        GAS_PATH_ROBUST_SET_EMPTY
        | GAS_PATH_FLOW_BELOW_HALL_CLOSING_MDOT
        | FEED_LOOP_UNSTABLE_EQUILIBRIUM
        | ICP_CAPACITY_BELOW_HALL_I_D
        | JOINT_CLOSING_POINT_ABSENT => "DESIGN_VARIABLE_LIMIT",
        HALL_NON_CLOSING_UNDER_AIR_ENVELOPE => "DESIGN_VARIABLE_LIMIT / MODEL_DOMAIN_LIMIT",
        AIR_CHEMISTRY_BOUNDED_NOT_COMPLETE => "MODEL_DOMAIN_LIMIT",
        ENVIRONMENT_NOT_EVALUATED | MATERIALITY_BOUND_REQUIRED_HE | MATERIALITY_BOUND_REQUIRED_AR => {
            "MODEL_DOMAIN_LIMIT"
        }
        MASS_CBE_LOWER_BOUND_AT_LIMIT | conservation::A4_CONSERVATION_BOUND_NON_CLOSING => {
            "FUNDAMENTAL_ARCHITECTURE_LIMIT"
        }
        conservation::A4_INPUT_OUT_OF_DOMAIN => "MODEL_DOMAIN_LIMIT",
        c if intake::A5_CELL_CODES.contains(&c) => "DESIGN_VARIABLE_LIMIT",
        other => category(other),
    }
}

/// Rank of a category for the dominant-blocker order (A9.31 sec. 23 H).
pub fn category_rank(c: &str) -> u8 {
    match c {
        "FUNDAMENTAL_ARCHITECTURE_LIMIT" => 0,
        "MODEL_DOMAIN_LIMIT" => 1,
        "DESIGN_VARIABLE_LIMIT" | "DESIGN_VARIABLE_LIMIT / MODEL_DOMAIN_LIMIT" => 2,
        _ => 3,
    }
}

// ------------------------------------------------------------------------------------------------ path inputs

/// Feed-loop class of one robust upstream member at one state (contract v8 typed status, R2).
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum FeedLoop {
    Stable,
    UnstableEquilibrium { re_lambda_max: f64 },
    ControllerNotRegistered,
}

/// The F7 chain values of one robust upstream member at one state.
#[derive(Debug, Clone, PartialEq)]
pub struct MemberState {
    pub mdot_kg_s: f64,
    pub x_o: Option<f64>,
    pub p_compressor_w: Option<f64>,
    pub feed: FeedLoop,
}

/// P-FLOW (AIR delivered flow and composition) and P-FEED-STABILITY.
#[derive(Debug, Clone, PartialEq)]
pub struct FlowPath {
    /// The F8 robust set, carried unchanged (design ids).
    pub robust_members: Vec<String>,
    /// state -> member -> values (present only when the robust set is non-empty and the per-state values exist).
    pub per_state: Option<BTreeMap<String, BTreeMap<String, MemberState>>>,
    /// Whether the compressor values of `per_state` come from an ADMITTED / VERIFIED producer (eligible lower bound).
    pub compressor_eligible: bool,
    pub provenance: String,
    /// Raw report: F7 frontier, F8 decomposition, Hall grid floor (no verdict).
    pub report: Value,
}

/// P-ICP of one mode.
#[derive(Debug, Clone, PartialEq)]
pub struct IcpMode {
    pub case_id: String,
    pub status: String,
    pub codes: Vec<String>,
    pub i_e_cap_fav_a: Option<f64>,
    pub member_id: Option<String>,
    /// Load-plane values of the member giving I_e,cap,fav (IF-ICP-BUS-v2, model-derived).
    pub loads: Vec<(Slot, f64, String)>,
    pub load_codes: Vec<String>,
    pub feed: Value,
    pub summary: Value,
}

/// P-ICP (and the model used by P-CPL).
#[derive(Debug, Clone)]
pub struct IcpPath {
    pub modes: BTreeMap<Mode, IcpMode>,
    pub producer_status: String,
    pub provenance: String,
    pub model: Option<abep_icp::v2::IcpModelV2>,
}

/// P-THERMAL result of one (state, mode) from a thermal 2.0.0 flight output.
#[derive(Debug, Clone, PartialEq)]
pub struct ThermalState {
    pub converged: bool,
    /// Minimum over the heated nodes of (registered validated limit - T_max); None when not every heated node has one.
    pub margin_k: Option<f64>,
    pub t_max_k: Option<f64>,
    pub codes: Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ThermalPath {
    pub codes: Vec<String>,
    pub per_state: Option<BTreeMap<(String, Mode), ThermalState>>,
    pub producer_status: String,
    pub provenance: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct MassPath {
    /// EVALUATED current-best-estimate wet mass (dry CBE + frozen Xe load), never a planning allocation.
    pub cbe_wet_kg: Option<f64>,
    pub cbe_lower_bound_kg: Option<f64>,
    pub codes: Vec<String>,
    pub info: Value,
}

#[derive(Debug, Clone, PartialEq)]
pub struct LifePath {
    pub firing_life_h: Option<f64>,
    pub codes: Vec<String>,
    pub info: Value,
}

/// P-TD: the mission drag_body_N codes per state (EVALUATED drag has no A2 rule and stays OPEN).
#[derive(Debug, Clone, PartialEq)]
pub struct TdPath {
    pub per_state_codes: BTreeMap<String, Vec<String>>,
}

/// One AIR envelope point with its composition corner (A1).
#[derive(Debug, Clone, PartialEq)]
pub struct AirPoint {
    pub composition_id: String,
    pub point: EnvelopePoint,
}

/// The ingested AIR family (A1 execution.ingestion supplies it).
#[derive(Debug, Clone, PartialEq)]
pub struct AirHallInput {
    pub points: Vec<AirPoint>,
    pub corners: Vec<String>,
    /// state -> A1 state_applicability code (SB-He / SB-Ar).
    pub state_exclusions: BTreeMap<String, String>,
    pub bz_family_kind: BzFamilyKind,
    /// Ingested under A1 LP-BOUNDED (BV-AIR-LL): information only, never a closure or a non-closure.
    pub bounded: bool,
    pub provenance: String,
}

#[derive(Debug, Clone, PartialEq)]
pub enum AirHall {
    NotAvailable(Vec<String>),
    Ingested(AirHallInput),
}

/// Everything harness v2 reads; [`evaluate`] is a pure function of it.
#[derive(Clone)]
pub struct M1Inputs {
    pub today: TodayInputs,
    pub xe: Option<Envelope>,
    pub air: AirHall,
    pub a1_on_line: bool,
    /// The Hall AIR reaction set (NP-HALL-CHEM-AIR) label and admission state, as read.
    pub air_chemistry: Value,
    pub flow: FlowPath,
    pub icp: IcpPath,
    pub mp: MassPowerA9V5,
    pub thermal: ThermalPath,
    pub mass: MassPath,
    pub life: LifePath,
    pub td: TdPath,
    pub hc06_k: Option<f64>,
    pub hc07_h: Option<f64>,
    pub hc08_n: Option<f64>,
    /// Addendum A4 inputs (None: A4 not evaluated).
    pub a4: Option<conservation::A4Inputs>,
    /// Addendum A5 inputs (None: A5 not evaluated; the M1 dry run v1 is the harness without A5).
    pub a5: Option<intake::IntakeInputs>,
}

// ------------------------------------------------------------------------------------------------ P-PBUS

/// The layer (a) bus ledger of one (state, mode) without the Hall discharge (P-PBUS).
#[derive(Debug, Clone, PartialEq)]
pub struct NonHallBus {
    /// Sum of the non-Hall items' lower_bound_W (TBD load -> 0, TBD efficiency -> 1).
    pub lb_w: f64,
    /// The same over loads of ADMITTED / VERIFIED producers only (the eligible non-closure bound).
    pub lb_eligible_w: f64,
    /// (slot, what, requires) of every TBD term other than the Hall discharge load.
    pub tbd: Vec<(String, String, String)>,
    /// Known non-Hall spacecraft-side draw when no non-Hall term is TBD.
    pub p_nonhall_w: Option<f64>,
    /// Hall discharge efficiency x front end (known only when registered).
    pub hall_path_eff: Option<f64>,
    pub overrides: Vec<(String, f64, String)>,
}

/// One non-Hall override of the layer (a) ledger: (slot, P_W at the load plane, source, eligible for a non-closure).
pub type BusOverride = (Slot, f64, String, bool);

pub fn non_hall_bus(mp: &MassPowerA9V5, overrides: &[BusOverride]) -> crate::AssessResult<NonHallBus> {
    use abep_subsystems::power::official::{ledger_with_loads, LoadOverride};
    let lo: Vec<LoadOverride> = overrides
        .iter()
        .map(|(s, p, src, _)| LoadOverride {
            slot: *s,
            p_w: *p,
            evidence_class: "model-derived".into(),
            source: src.clone(),
        })
        .collect();
    let led = ledger_with_loads(mp, abep_subsystems::power::slots::FLIGHT_CONFIGURATION, &lo, LAYER_A)
        .map_err(|e| crate::error::model_error(e.to_string()))?;
    let mut lb = 0.0;
    let mut lb_el = 0.0;
    for it in led.items.iter().filter(|i| i.slot != Slot::HallDischarge) {
        let x = it.lower_bound_w.unwrap_or(0.0);
        lb += x;
        if overrides.iter().any(|(s, _, _, el)| *s == it.slot && *el) {
            lb_el += x;
        }
    }
    let tbd: Vec<(String, String, String)> = led
        .tbd
        .iter()
        .filter(|t| !(t.slot == Slot::HallDischarge && t.what == "load"))
        .map(|t| (t.slot.name().to_string(), t.what.to_string(), t.requires.clone()))
        .collect();
    let hall = led.item(Slot::HallDischarge);
    let hall_eff = match (hall.efficiency, hall.eta_front_end) {
        (Some(a), Some(b)) => Some(a * b),
        _ => None,
    };
    let non_hall_tbd = tbd.iter().any(|t| t.0 != Slot::HallDischarge.name());
    let p_nonhall = if non_hall_tbd {
        None
    } else {
        Some(led.items.iter().filter(|i| i.slot != Slot::HallDischarge).map(|i| i.p_bus_w.unwrap_or(0.0)).sum())
    };
    Ok(NonHallBus {
        lb_w: lb,
        lb_eligible_w: lb_el,
        tbd,
        p_nonhall_w: p_nonhall,
        hall_path_eff: hall_eff,
        overrides: overrides.iter().map(|(s, p, src, _)| (s.name().to_string(), *p, src.clone())).collect(),
    })
}

// ------------------------------------------------------------------------------------------------ Hall points

/// A Hall envelope point of a mode with its composition corner (AIR) or none (XE).
#[derive(Debug, Clone, Copy)]
pub struct Pt<'a> {
    pub p: &'a EnvelopePoint,
    pub corner: Option<&'a str>,
}

/// The Hall points of a mode at a state (AIR: empty when the state is under an A1 species bound).
pub fn mode_points<'a>(inp: &'a M1Inputs, m: Mode) -> Vec<Pt<'a>> {
    match m {
        Mode::AirPrimary => match &inp.air {
            AirHall::Ingested(a) => {
                a.points.iter().map(|x| Pt { p: &x.point, corner: Some(&x.composition_id) }).collect()
            }
            AirHall::NotAvailable(_) => vec![],
        },
        _ => inp
            .xe
            .as_ref()
            .map(|e| e.family_points(Family::Xe).map(|p| Pt { p, corner: None }).collect())
            .unwrap_or_default(),
    }
}

/// Hardware configurations on which `pts` covers every corner (no corner: any point).
pub fn hardware_covering(pts: &[Pt], corners: &[String]) -> BTreeSet<(String, String)> {
    let mut by: BTreeMap<(String, String), BTreeSet<&str>> = BTreeMap::new();
    for x in pts {
        by.entry(x.p.case.hardware()).or_default().insert(x.corner.unwrap_or(""));
    }
    by.into_iter()
        .filter(|(_, cs)| corners.is_empty() || corners.iter().all(|c| cs.contains(c.as_str())))
        .map(|(h, _)| h)
        .collect()
}

/// A1 evaluation of one AIR test over the AIR points (composition rule: closes on a hardware only if every corner has a
/// passing point of that hardware).
pub fn evaluate_air_test(t: HallTest, a: &AirHallInput, lim: &HallLimits) -> HallTestResult {
    let pts: Vec<Pt> = a.points.iter().map(|x| Pt { p: &x.point, corner: Some(&x.composition_id) }).collect();
    if pts.is_empty() {
        return hall_not_evaluated(t, v1::HALL_ENVELOPE_NOT_RUN, "no frozen AIR envelope point");
    }
    let refs: Vec<&EnvelopePoint> = pts.iter().map(|x| x.p).collect();
    // Margins, counts and transports from the v1 evaluation; status replaced by the A1 composition rule.
    let mut r = evaluate_hall_test(t, Family::N2Proxy, &refs, lim, a.bz_family_kind);
    r.family = None;
    let passing: Vec<Pt> = pts.iter().copied().filter(|x| v1::point_passes(t, x.p, lim)).collect();
    let hw = hardware_covering(&passing, &a.corners);
    let mut closing: BTreeMap<(String, String), BTreeSet<String>> = BTreeMap::new();
    for h in &hw {
        // transports closing at every corner on this hardware
        let mut acc: Option<BTreeSet<String>> = None;
        for c in &a.corners {
            let ts: BTreeSet<String> = passing
                .iter()
                .filter(|x| &x.p.case.hardware() == h && x.corner == Some(c.as_str()))
                .map(|x| x.p.case.transport_id.clone())
                .collect();
            acc = Some(match acc {
                None => ts,
                Some(p) => p.intersection(&ts).cloned().collect(),
            });
        }
        closing.insert(h.clone(), acc.unwrap_or_default());
    }
    r.closing = closing;
    r.n_closing = passing.len();
    let c = &mut r.constraint;
    c.eligible_non_close = false;
    if a.bounded {
        // A1 bounded_variant_outcome: reported as labelled information; NOT_DETERMINABLE whatever it says.
        c.status = NOT_DETERMINABLE_IN_ENVELOPE;
        c.eligible_close = false;
        c.codes = vec![AIR_CHEMISTRY_BOUNDED_NOT_COMPLETE.to_string()];
        if a.bz_family_kind == BzFamilyKind::SourcedSurrogate {
            c.codes.push(v1::H1_BZ_NOT_REGISTERED.into());
        }
        c.codes.sort();
        c.detail = format!(
            "{} (BOUNDED_ONE_SIDED_LOWER_ELECTRON_IMPACT_LOSS_NOT_COMPLETE; A1 LP-BOUNDED, information only)",
            if hw.is_empty() {
                "BOUNDED_INFORMATION_NO_CLOSURE_FOUND"
            } else {
                "BOUNDED_INFORMATION_CLOSES_AT_ALL_CORNERS"
            }
        );
        c.evidence_conditions = vec![];
        return r;
    }
    if !hw.is_empty() {
        c.status = CLOSES_IN_ENVELOPE;
        c.eligible_close = true;
        c.codes = vec![];
        c.detail = format!("closes at every composition corner on {} hardware configuration(s) ({LAYER_A})", hw.len());
        let mut ec = evidence_conditions_hall(a.bz_family_kind);
        ec.extend(air_evidence_conditions());
        c.evidence_conditions = ec;
    } else {
        c.status = NOT_DETERMINABLE_IN_ENVELOPE;
        c.eligible_close = false;
        let mut codes = vec![HALL_NON_CLOSING_UNDER_AIR_ENVELOPE.to_string()];
        let count = |s: RunStatus| refs.iter().filter(|p| p.status == s).count();
        if count(RunStatus::OutOfDomain) > 0 {
            codes.push(v1::HALL_ENVELOPE_OUT_OF_DOMAIN_POINTS.into());
        }
        if count(RunStatus::NumericalFailure) > 0 {
            codes.push(v1::HALL_ENVELOPE_NUMERICAL_FAILURE_POINTS.into());
        }
        if a.bz_family_kind == BzFamilyKind::SourcedSurrogate {
            codes.push(v1::H1_BZ_NOT_REGISTERED.into());
        }
        codes.push(AIR_COMPOSITION_NOT_REGISTERED.into());
        codes.push(AIR_CHEMISTRY_NOMINAL_ONLY.into());
        codes.sort();
        c.codes = codes;
        c.detail = "no hardware closes at every composition corner; AIR non-closure is never eligible (A1)".into();
        c.evidence_conditions = vec![];
    }
    r
}

pub fn air_evidence_conditions() -> Vec<String> {
    vec![
        "EC-COMP: the delivered composition is registered for each required state, lies inside the CE-AIR hull and the \
         Hall closes at it (A1)"
            .into(),
        "EC-CHEM: the closure holds under the registered chemistry variants of the admitted AIR set (A1)".into(),
        "EC-INLET: the registered delivered feed temperature and velocity replace NI-01 and the closure holds (A1)".into(),
    ]
}

/// The Hall tests of a mode at one P_nonHall,LB (state-independent apart from the bound and the AIR exclusions).
pub fn hall_tests(inp: &M1Inputs, m: Mode, lim: &HallLimits) -> Vec<HallTestResult> {
    let tests = HallTest::of_mode(m);
    match m {
        Mode::AirPrimary => match &inp.air {
            AirHall::NotAvailable(codes) => tests
                .iter()
                .map(|t| {
                    let mut h = hall_not_evaluated(
                        *t,
                        v1::AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED,
                        "no admitted Hall AIR family ingested: the AIR layer (a) Hall is NOT_EVALUATED",
                    );
                    h.constraint.codes = codes.clone();
                    h
                })
                .collect(),
            AirHall::Ingested(a) => {
                let mut rs: Vec<HallTestResult> = tests.iter().map(|t| evaluate_air_test(*t, a, lim)).collect();
                // A1: T12 and T25 must close on the same hardware configuration.
                let common: Option<BTreeSet<(String, String)>> = rs.iter().fold(None, |acc, r| {
                    let k: BTreeSet<(String, String)> = r.closing.keys().cloned().collect();
                    Some(match acc {
                        None => k,
                        Some(a) => a.intersection(&k).cloned().collect(),
                    })
                });
                if rs.iter().all(|r| r.constraint.eligible_close) && common.is_some_and(|c| c.is_empty()) {
                    for r in &mut rs {
                        r.constraint.status = NOT_DETERMINABLE_IN_ENVELOPE;
                        r.constraint.eligible_close = false;
                        r.constraint.codes =
                            vec![v1::HALL_NO_COMMON_HARDWARE.to_string(), HALL_NON_CLOSING_UNDER_AIR_ENVELOPE.into()];
                        r.constraint.evidence_conditions = vec![];
                    }
                }
                rs
            }
        },
        _ => tests
            .iter()
            .map(|t| match &inp.xe {
                None => {
                    hall_not_evaluated(*t, v1::HALL_ENVELOPE_NOT_RUN, "no frozen HallThruster.jl envelope ingested")
                }
                Some(e) => {
                    let pts: Vec<&EnvelopePoint> = e.family_points(Family::Xe).collect();
                    evaluate_hall_test(*t, Family::Xe, &pts, lim, e.bz_family_kind)
                }
            })
            .collect(),
    }
}

// ------------------------------------------------------------------------------------------------ evaluation

/// The evaluation of one (state, mode) in layer (a).
#[derive(Debug, Clone, PartialEq)]
pub struct StateModeEval {
    pub eval: ModeEval,
    pub hall: Vec<HallTestResult>,
    pub bus: NonHallBus,
    /// Hardware configurations with a joint closing point for every Hall test of the mode.
    pub joint_hardware: BTreeSet<(String, String)>,
    /// Best joint point per Hall test: (test id, key, thrust, P_bus,fav, I_d, mdot).
    pub joint_best: Vec<(String, String, f64, f64, Option<f64>, f64)>,
    /// Available delivered flow at the state (AIR; max over stable robust members) and its x_O.
    pub delivered: Option<(f64, Option<f64>)>,
    pub binding_constraint: Option<String>,
}

fn open(id: &str, codes: Vec<String>, detail: impl Into<String>) -> Constraint {
    let mut c = Constraint::open(id, codes, detail);
    c.codes.sort();
    c.codes.dedup();
    c
}

fn closes(id: &str, detail: String, ec: &str) -> Constraint {
    Constraint {
        id: id.into(),
        hall_specific: false,
        status: v1::CLOSES,
        eligible_close: true,
        eligible_non_close: false,
        codes: vec![],
        detail,
        evidence_conditions: vec![ec.to_string()],
    }
}

fn non_closing(id: &str, code: &str, eligible: bool, detail: String) -> Constraint {
    Constraint {
        id: id.into(),
        hall_specific: false,
        status: NON_CLOSING,
        eligible_close: false,
        eligible_non_close: eligible,
        codes: vec![code.to_string()],
        detail,
        evidence_conditions: vec![],
    }
}

pub const EC_FLOW: &str =
    "EC-FLOW: delivered flow from the F7 / F8 chain under PARAMETRIC_SENSITIVITY inputs (code-default \
compressor coefficients, TBD surface-scenario set); compressor T-1 / T-2 data, DI-1.3 accommodation evidence and an \
admitted plenum / feed transient (v8 PARITY_FAIL) remain";
pub const EC_ICP: &str =
    "EC-ICP: I_e,cap from NP-ICP v2 (IMPLEMENTED_UNVERIFIED, NOT_VALIDATED); HC-05 (M_n,LB > 0 with a \
VALIDATED_BENCH I_e,cap) and CPL-HALL-ON-v1 not evaluated";
pub const EC_PBUS: &str =
    "EC-PBUS: bus power from a layer (a) ledger at model-derived loads and registered efficiencies; \
start-up / simultaneous peaks (P_bus,1ms,max) not evaluated";
pub const EC_THERMAL: &str = "EC-THERMAL: thermal 2.0.0 NOT_VALIDATED; validated limits";
pub const EC_MASS: &str = "EC-MASS: current-best-estimate mass, not a measurement";
pub const EC_LIFE: &str = "EC-LIFE: evaluated life is model-derived";

/// Joint filter of a point at (state, mode): the point-evaluated non-Hall inputs that are evaluable.
struct PointFilter {
    ie: Option<f64>,
    flows: Option<Vec<f64>>,
}

impl PointFilter {
    fn icp_ok(&self, p: &EnvelopePoint) -> bool {
        match (self.ie, p.discharge_current_a) {
            (Some(ie), Some(id)) => id <= ie,
            (Some(_), None) => false,
            (None, _) => true,
        }
    }
    fn flow_ok(&self, p: &EnvelopePoint) -> bool {
        match &self.flows {
            Some(f) => f.iter().any(|m| *m >= p.case.mdot_kg_s),
            None => true,
        }
    }
}

/// Evaluate every (state, mode) of the record and classify (pure).
pub fn evaluate(inp: &M1Inputs) -> crate::AssessResult<M1Outcome> {
    let ti = &inp.today;
    let mut bus_cache: BTreeMap<String, NonHallBus> = BTreeMap::new();
    let mut hall_cache: BTreeMap<(Mode, u64, bool), Vec<HallTestResult>> = BTreeMap::new();
    let mut states = Vec::with_capacity(ti.states.len());
    let mut lb_groups: BTreeMap<Mode, BTreeMap<u64, Vec<HallTestResult>>> = BTreeMap::new();
    for st in &ti.states {
        let env_ok =
            ti.mission.state(&st.state_id).is_some_and(|r| r.environment_status == abep_types::EvalStatus::Evaluated);
        let mut modes = BTreeMap::new();
        for m in REQUIRED_MODES {
            // P-FLOW values at the state (AIR).
            let members = if m == Mode::AirPrimary {
                inp.flow.per_state.as_ref().and_then(|ps| ps.get(&st.state_id))
            } else {
                None
            };
            let stable: Vec<(&String, &MemberState)> =
                members.map(|ms| ms.iter().filter(|(_, v)| v.feed == FeedLoop::Stable).collect()).unwrap_or_default();
            // P-PBUS overrides: ICP loads of the mode, compressor (favorable minimum over stable members).
            let mut ov: Vec<BusOverride> = vec![];
            if let Some(im) = inp.icp.modes.get(&m) {
                for (s, p, src) in &im.loads {
                    ov.push((*s, *p, src.clone(), false));
                }
            }
            if m == Mode::AirPrimary {
                let pc = stable
                    .iter()
                    .filter_map(|(_, v)| v.p_compressor_w)
                    .fold(None, |a: Option<f64>, x| Some(a.map_or(x, |a| a.min(x))));
                if let Some(pc) = pc {
                    ov.push((
                        Slot::Compressor,
                        pc,
                        format!("P-FLOW robust member compressor draw at {} ({})", st.state_id, inp.flow.provenance),
                        inp.flow.compressor_eligible,
                    ));
                }
            }
            let key = format!("{ov:?}");
            let bus = match bus_cache.get(&key) {
                Some(b) => b.clone(),
                None => {
                    let b = non_hall_bus(&inp.mp, &ov)?;
                    bus_cache.insert(key, b.clone());
                    b
                }
            };
            let lim = HallLimits { p_non_hall_lb_w: bus.lb_w, ..ti.limits };
            let excluded = match (&inp.air, m) {
                (AirHall::Ingested(a), Mode::AirPrimary) => a.state_exclusions.get(&st.state_id).cloned(),
                _ => None,
            };
            let hall = match &excluded {
                Some(code) => HallTest::of_mode(m)
                    .iter()
                    .map(|t| hall_not_evaluated(*t, code, "A1 state_applicability: unresolved species bound"))
                    .collect(),
                None => {
                    let k = (m, bus.lb_w.to_bits(), false);
                    hall_cache
                        .entry(k)
                        .or_insert_with(|| {
                            let h = hall_tests(inp, m, &lim);
                            lb_groups.entry(m).or_default().insert(bus.lb_w.to_bits(), h.clone());
                            h
                        })
                        .clone()
                }
            };
            let filter = PointFilter {
                ie: inp.icp.modes.get(&m).and_then(|x| x.i_e_cap_fav_a),
                flows: (!stable.is_empty()).then(|| stable.iter().map(|(_, v)| v.mdot_kg_s).collect()),
            };
            let pts: Vec<Pt> = if excluded.is_some() { vec![] } else { mode_points(inp, m) };
            let corners: Vec<String> = match (&inp.air, m) {
                (AirHall::Ingested(a), Mode::AirPrimary) => a.corners.clone(),
                _ => vec![],
            };
            let tests = HallTest::of_mode(m);
            let passing: Vec<Vec<Pt>> = tests
                .iter()
                .map(|t| pts.iter().copied().filter(|x| v1::point_passes(*t, x.p, &lim)).collect())
                .collect();
            let hall_closes = hall.iter().all(|h| h.constraint.eligible_close);
            let any_points = passing.iter().all(|v| !v.is_empty()) && hall_closes;
            let covered = |f: &dyn Fn(&EnvelopePoint) -> bool| -> bool {
                passing.iter().all(|v| {
                    let sel: Vec<Pt> = v.iter().copied().filter(|x| f(x.p)).collect();
                    !hardware_covering(&sel, &corners).is_empty()
                })
            };
            let mut nh: Vec<Constraint> = vec![];
            // NH-FLOW
            nh.push(if m == Mode::AirPrimary {
                if inp.flow.robust_members.is_empty() {
                    open(
                        "NH-FLOW",
                        vec![GAS_PATH_ROBUST_SET_EMPTY.into()],
                        "F8 robust set EMPTY (admitted, carried unchanged): no upstream hardware is feasible in every \
                         admitted surface scenario",
                    )
                } else if members.is_none() {
                    open(
                        "NH-FLOW",
                        vec![GASPATH_PER_STATE_VALUES_NOT_SUPPLIED.into()],
                        "robust members exist; no per-state chain values supplied",
                    )
                } else if stable.is_empty() {
                    let ms = members.expect("checked");
                    let unstable: Vec<f64> = ms
                        .values()
                        .filter_map(|v| match v.feed {
                            FeedLoop::UnstableEquilibrium { re_lambda_max } => Some(re_lambda_max),
                            _ => None,
                        })
                        .collect();
                    if !unstable.is_empty() && ms.values().all(|v| v.feed != FeedLoop::ControllerNotRegistered) {
                        non_closing(
                            "NH-FLOW",
                            FEED_LOOP_UNSTABLE_EQUILIBRIUM,
                            false,
                            format!(
                                "every robust member's feed loop is UNSTABLE_EQUILIBRIUM at this state (max Re lambda \
                                 {:e}); the time-domain flow is never a held number",
                                unstable.iter().cloned().fold(f64::NEG_INFINITY, f64::max)
                            ),
                        )
                    } else {
                        let mut codes = vec![FEED_CONTROLLER_NOT_REGISTERED.to_string()];
                        if !unstable.is_empty() {
                            codes.push(FEED_LOOP_UNSTABLE_EQUILIBRIUM.into());
                        }
                        open("NH-FLOW", codes, "no robust member with a stable feed loop under a registered controller")
                    }
                } else if !any_points {
                    open(
                        "NH-FLOW",
                        vec![NO_HALL_CLOSING_POINT.into()],
                        "no AIR Hall closing point to evaluate the flow at",
                    )
                } else if covered(&|p| filter.flow_ok(p)) {
                    closes("NH-FLOW", format!("a robust member delivers the closing point's mdot ({LAYER_A})"), EC_FLOW)
                } else {
                    non_closing(
                        "NH-FLOW",
                        GAS_PATH_FLOW_BELOW_HALL_CLOSING_MDOT,
                        false,
                        "delivered flow below every Hall closing point's mdot (never eligible in A2)".into(),
                    )
                }
            } else {
                open(
                    "NH-FLOW",
                    vec![XE_FEED_FLOW_NOT_REGISTERED.into()],
                    "no H-1 Xe flow registered (XV2-17 / XV2-18 TBD, OQ-HPE-03)",
                )
            });
            // NH-ICP
            let im = inp.icp.modes.get(&m);
            nh.push(match im.and_then(|x| x.i_e_cap_fav_a) {
                None => {
                    let mut codes = vec![ICP_CAPACITY_NOT_EVALUATED.to_string()];
                    if let Some(x) = im {
                        codes.extend(x.codes.iter().cloned());
                    }
                    open("NH-ICP", codes, format!("NP-ICP v2 ({}) gives no converged I_e,cap", inp.icp.producer_status))
                }
                Some(ie) => {
                    if !any_points {
                        open(
                            "NH-ICP",
                            vec![NO_HALL_CLOSING_POINT.into()],
                            "no Hall closing point to evaluate I_e,cap against",
                        )
                    } else if covered(&|p| filter.icp_ok(p)) {
                        closes("NH-ICP", format!("I_e,cap,fav {ie} A >= I_d at a closing point ({LAYER_A})"), EC_ICP)
                    } else {
                        non_closing(
                            "NH-ICP",
                            ICP_CAPACITY_BELOW_HALL_I_D,
                            false,
                            format!("I_e,cap,fav {ie} A below I_d of every closing point (never eligible in A2)"),
                        )
                    }
                }
            });
            // Joint points and hardware.
            let joint: Vec<Vec<Pt>> = passing
                .iter()
                .map(|v| v.iter().copied().filter(|x| filter.icp_ok(x.p) && filter.flow_ok(x.p)).collect())
                .collect();
            let mut joint_hw: Option<BTreeSet<(String, String)>> = None;
            for v in &joint {
                let h = hardware_covering(v, &corners);
                joint_hw = Some(match joint_hw {
                    None => h,
                    Some(a) => a.intersection(&h).cloned().collect(),
                });
            }
            let joint_hw = if hall_closes { joint_hw.unwrap_or_default() } else { BTreeSet::new() };
            let mut joint_best = vec![];
            for (t, v) in tests.iter().zip(&joint) {
                let best = v.iter().filter(|x| joint_hw.contains(&x.p.case.hardware())).max_by(|a, b| {
                    a.p.thrust_n.unwrap_or(f64::NEG_INFINITY).total_cmp(&b.p.thrust_n.unwrap_or(f64::NEG_INFINITY))
                });
                if let Some(x) = best {
                    joint_best.push((
                        t.constraint_id().to_string(),
                        x.p.case.key.clone(),
                        x.p.thrust_n.unwrap_or(f64::NAN),
                        x.p.discharge_power_w.unwrap_or(f64::NAN) + bus.lb_w,
                        x.p.discharge_current_a,
                        x.p.case.mdot_kg_s,
                    ));
                }
            }
            // NH-PBUS
            let hc03 = ti.limits.p_bus_max_w;
            nh.push(if bus.lb_eligible_w >= hc03 {
                Constraint {
                    id: "NH-PBUS".into(),
                    hall_specific: false,
                    status: NON_CLOSING,
                    eligible_close: false,
                    eligible_non_close: true,
                    codes: vec![v1::PBUS_NON_HALL_LOWER_BOUND_AT_LIMIT.into()],
                    detail: format!(
                        "non-Hall lower bound of admitted / verified loads {} W >= {hc03} W",
                        bus.lb_eligible_w
                    ),
                    evidence_conditions: vec![],
                }
            } else if let (Some(pnh), Some(eff)) = (bus.p_nonhall_w, bus.hall_path_eff) {
                if joint_best.is_empty() {
                    open("NH-PBUS", vec![NO_HALL_CLOSING_POINT.into()], "complete ledger; no joint Hall closing point")
                } else {
                    let ok = joint.iter().all(|v| {
                        v.iter().any(|x| {
                            joint_hw.contains(&x.p.case.hardware())
                                && x.p.discharge_power_w.is_some_and(|pd| pd / eff + pnh < hc03)
                        })
                    });
                    if ok {
                        closes("NH-PBUS", format!("complete layer (a) ledger below {hc03} W at a joint point"), EC_PBUS)
                    } else {
                        non_closing(
                            "NH-PBUS",
                            BUS_LEDGER_ABOVE_LIMIT_AT_JOINT_POINTS,
                            false,
                            "complete layer (a) ledger at or above the limit at every joint point".into(),
                        )
                    }
                }
            } else {
                open(
                    "NH-PBUS",
                    vec![v1::BUS_LEDGER_NOT_COMPLETE.into()],
                    format!(
                        "layer (a) ledger: {} TBD term(s) at their favorable lower bound (load 0 W, efficiency 1); \
                         P_nonHall,LB {} W used in the Hall point tests",
                        bus.tbd.len(),
                        bus.lb_w
                    ),
                )
            });
            // NH-TD (AIR)
            if m == Mode::AirPrimary {
                let mut codes =
                    inp.td.per_state_codes.get(&st.state_id).cloned().unwrap_or_else(|| vec![v1::NOT_EVALUATED.into()]);
                if codes.is_empty() {
                    codes.push(T_MINUS_D_RULE_NOT_REGISTERED.into());
                }
                nh.push(open(
                    "NH-TD",
                    codes,
                    "HC-08 needs the host-spacecraft drag ICD; no T - D evaluation is registered in A2 (R5)",
                ));
            }
            // NH-MASS
            let hc04 = ti.thresholds.limit("HC-04");
            nh.push(match (inp.mass.cbe_lower_bound_kg, inp.mass.cbe_wet_kg, hc04) {
                (Some(lb), _, Some(l)) if lb >= l => non_closing(
                    "NH-MASS",
                    MASS_CBE_LOWER_BOUND_AT_LIMIT,
                    true,
                    format!("evaluated CBE wet-mass lower bound {lb} kg >= {l} kg"),
                ),
                (_, Some(w), Some(l)) if w < l => {
                    closes("NH-MASS", format!("evaluated CBE wet mass {w} kg < {l} kg"), EC_MASS)
                }
                (_, Some(w), Some(l)) => non_closing(
                    "NH-MASS",
                    MASS_CBE_ABOVE_LIMIT,
                    false,
                    format!("evaluated CBE wet mass {w} kg >= {l} kg (point estimate; not a lower bound)"),
                ),
                _ => open(
                    "NH-MASS",
                    inp.mass.codes.clone(),
                    "no evaluated current-best-estimate wet mass (planning allocations are not eligible, HR-07)",
                ),
            });
            // NH-THERMAL
            let ts = inp.thermal.per_state.as_ref().and_then(|p| p.get(&(st.state_id.clone(), m)));
            nh.push(match (ts, inp.hc06_k) {
                (Some(t), Some(h)) if t.converged => match t.margin_k {
                    Some(mk) if mk >= h => closes("NH-THERMAL", format!("thermal margin {mk} K >= {h} K"), EC_THERMAL),
                    Some(mk) => non_closing(
                        "NH-THERMAL",
                        THERMAL_MARGIN_BELOW_HC06,
                        false,
                        format!("thermal margin {mk} K < {h} K (never eligible in A2)"),
                    ),
                    None => open("NH-THERMAL", t.codes.clone(), "a heated node has no registered validated limit"),
                },
                (Some(t), _) => open("NH-THERMAL", t.codes.clone(), "thermal 2.0.0 output not CONVERGED"),
                _ => open("NH-THERMAL", inp.thermal.codes.clone(), "no thermal 2.0.0 flight output"),
            });
            // NH-LIFE
            nh.push(match (inp.life.firing_life_h, inp.hc07_h) {
                (Some(l), Some(b)) if l > b => {
                    closes("NH-LIFE", format!("evaluated firing life {l} h > {b} h"), EC_LIFE)
                }
                (Some(l), Some(b)) => {
                    non_closing("NH-LIFE", LIFE_BELOW_HC07, false, format!("evaluated firing life {l} h <= {b} h"))
                }
                _ => open("NH-LIFE", inp.life.codes.clone(), "no evaluated H-1 / ICP firing life"),
            });
            if !env_ok {
                for c in &mut nh {
                    if !c.eligible_non_close {
                        *c = open(&c.id.clone(), vec![ENVIRONMENT_NOT_EVALUATED.into()], "environment not EVALUATED");
                    }
                }
            }
            let eval = finalize_mode(&hall, &nh, &joint_hw);
            let binding = eval
                .constraints
                .iter()
                .find(|c| c.eligible_non_close)
                .or_else(|| eval.constraints.iter().find(|c| !c.eligible_close))
                .map(|c| c.id.clone())
                .or_else(|| (eval.status == NOT_DETERMINABLE).then(|| JOINT_CLOSING_POINT_ABSENT.to_string()));
            let delivered = (!stable.is_empty()).then(|| {
                let best = stable.iter().max_by(|a, b| a.1.mdot_kg_s.total_cmp(&b.1.mdot_kg_s)).expect("non-empty");
                (best.1.mdot_kg_s, best.1.x_o)
            });
            modes.insert(
                m,
                StateModeEval {
                    eval,
                    hall,
                    bus,
                    joint_hardware: joint_hw,
                    joint_best,
                    delivered,
                    binding_constraint: binding,
                },
            );
        }
        states.push((st.clone(), modes));
    }
    let a4 = match &inp.a4 {
        Some(a) => Some(conservation::evaluate_a4(a, &ti.limits, &states)?),
        None => None,
    };
    if let Some(o) = &a4 {
        for (st, ms) in states.iter_mut().filter(|(s, _)| s.required && o.eligible_air_states.contains(&s.state_id)) {
            let failing: Vec<&str> = o
                .verdicts
                .iter()
                .filter(|v| v.eligible && v.failing_states.contains(&st.state_id))
                .map(|v| v.id)
                .collect();
            if let Some(e) = ms.get_mut(&Mode::AirPrimary) {
                e.eval.constraints.push(conservation::a4_constraint(&failing));
                e.eval.status = PHYSICS_NON_CLOSING;
                e.eval.blockers.clear();
                e.binding_constraint = Some(conservation::A4_CONSTRAINT_ID.into());
            }
        }
    }
    let a5 = match (&inp.a5, &inp.a4, &a4) {
        (Some(x), Some(ai), Some(ao)) => {
            let hall = intake::hall_min_mdot(inp, &states);
            let required: Vec<bool> = states.iter().map(|s| s.0.required).collect();
            let o = intake::evaluate_a5(x, ai, ao, &ti.limits, &required, &hall)?;
            intake::apply_cells(&o, &mut states);
            Some(o)
        }
        (Some(_), _, _) => return Err(crate::error::model_error("A5 needs the A4 evaluation of the same run")),
        _ => None,
    };
    let outcome = classify_v2(ti.credible_set_empty, inp.xe.is_some(), &states);
    Ok(M1Outcome { outcome, states, lb_groups, a4, a5 })
}

/// The layer (a) status of a (state, mode) (A2 joint_point_conditions.state_status): the v1 rule, and
/// JOINT_CLOSING_POINT_ABSENT when every constraint closes but no hardware has a joint point for every Hall test.
pub fn finalize_mode(hall: &[HallTestResult], nh: &[Constraint], joint_hw: &BTreeSet<(String, String)>) -> ModeEval {
    let mut eval = evaluate_mode(hall, nh);
    if eval.status == PHYSICS_FEASIBLE && joint_hw.is_empty() {
        eval.status = NOT_DETERMINABLE;
        eval.blockers = vec![JOINT_CLOSING_POINT_ABSENT.into()];
    }
    eval
}

/// The evaluated states and the classification.
#[derive(Debug, Clone)]
pub struct M1Outcome {
    pub outcome: ClosureOutcome,
    pub states: Vec<(StateRef, BTreeMap<Mode, StateModeEval>)>,
    /// Hall test results per mode and distinct P_nonHall,LB (bits).
    pub lb_groups: BTreeMap<Mode, BTreeMap<u64, Vec<HallTestResult>>>,
    /// Addendum A4 quantities and verdicts.
    pub a4: Option<conservation::A4Outcome>,
    /// Addendum A5 quantities and verdicts.
    pub a5: Option<intake::IntakeOutcome>,
}

/// The v1 procedure C0..C4 over per-(state, mode) evaluations (A2 classification.procedure), with the A4 step CA4
/// between C0 and C1.
pub fn classify_v2(
    credible_set_empty: bool,
    envelope_ingested: bool,
    states: &[(StateRef, BTreeMap<Mode, StateModeEval>)],
) -> ClosureOutcome {
    let mut tally: BTreeMap<String, usize> = BTreeMap::new();
    let (mut any_non_closing, mut all_feasible) = (false, true);
    let mut hw: Option<BTreeSet<(String, String)>> = None;
    let mut ec: BTreeSet<String> = BTreeSet::new();
    let mut out_states = Vec::with_capacity(states.len());
    for (st, modes) in states {
        let mut ms = BTreeMap::new();
        for m in REQUIRED_MODES {
            let Some(e) = modes.get(&m) else { continue };
            if st.required {
                any_non_closing |= e.eval.status == PHYSICS_NON_CLOSING;
                all_feasible &= e.eval.status == PHYSICS_FEASIBLE;
                for b in &e.eval.blockers {
                    *tally.entry(b.clone()).or_default() += 1;
                }
                hw = Some(match hw {
                    None => e.joint_hardware.clone(),
                    Some(a) => a.intersection(&e.joint_hardware).cloned().collect(),
                });
                for c in &e.eval.constraints {
                    ec.extend(c.evidence_conditions.iter().cloned());
                }
            }
            ms.insert(m, e.eval.clone());
        }
        out_states.push((st.clone(), ms));
    }
    let n_required = states.iter().filter(|s| s.0.required).count();
    let cells = n_required * REQUIRED_MODES.len();
    let common: Vec<(String, String)> = hw.unwrap_or_default().into_iter().collect();
    let mut out = ClosureOutcome {
        classification: NOT_DETERMINABLE,
        step: "C4",
        blockers: vec![],
        evidence_conditions: vec![],
        common_hardware: if all_feasible { common.clone() } else { vec![] },
        states: out_states,
    };
    if !credible_set_empty {
        out.step = "C0";
        out.blockers = vec![(v1::CREDIBLE_SET_NON_EMPTY.into(), cells)];
        return out;
    }
    // CA4 (addendum A4): an eligible conservation-bound non-closure needs no Hall envelope.
    let n_a4 = conservation::ca4_cells(states);
    if n_a4 > 0 {
        out.classification = PHYSICALLY_NON_CLOSING;
        out.step = "CA4";
        out.blockers = vec![(conservation::A4_CONSERVATION_BOUND_NON_CLOSING.into(), n_a4)];
        return out;
    }
    if !envelope_ingested {
        out.step = "C1";
        tally.insert(v1::HALL_ENVELOPE_NOT_RUN.into(), cells);
        out.blockers = tally.into_iter().collect();
        return out;
    }
    if n_required > 0 && any_non_closing {
        out.classification = PHYSICALLY_NON_CLOSING;
        out.step = "C2";
        return out;
    }
    if n_required > 0 && all_feasible {
        if common.is_empty() {
            out.blockers = vec![(v1::HALL_NO_COMMON_HARDWARE.into(), cells)];
            return out;
        }
        out.classification = SELECT_WITH_EVIDENCE_CONDITIONS;
        out.step = "C3";
        out.evidence_conditions = ec.into_iter().collect();
        return out;
    }
    out.blockers = tally.into_iter().collect();
    out
}
