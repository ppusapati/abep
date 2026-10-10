//! NP-HALL-PARAMETRIC-ENVELOPE addendum A5 in harness v2: the M2 intake closure under A9.35
//! (`docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a5_m2_intake_closure.json`).
//!
//! No current intake design is registered, so every registered design set is evaluated: the F1 grid (captured flow of
//! the IF-A1 TPMC records as the admitted F7 chain reads them), its F1-admissible subset, the F7 Pareto members
//! (delivered flow and composition from the admitted steady chain, cross-checked bit for bit against the committed F7
//! values) and their F8 status (carried unchanged). Each is compared with the A4 required area and flow (necessary
//! conditions at the favorable limit). A level that fails in every surface scenario at a required AIR state adds the
//! constraint A5-NH-INTAKE (DESIGN_VARIABLE_LIMIT, never eligible); nothing else changes the classification.

use super::conservation::{A4Inputs, A4Outcome, AreaLimit};
use super::*;
use crate::closure::NON_CLOSING;
use crate::error::{model_error, AssessResult};
use abep_gaspath::plenum_feed::{intake_side, steady_sweep, IntakeState};
use abep_provenance::read_verified;
use abep_types::constants::{M_N2, M_O, M_O2};
use abep_types::EvalStatus;
use std::path::Path;

pub const A5_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a5_m2_intake_closure.json";
pub const A5_SHA256: &str = "45e6013d30c57d80ed0f39af2428e53ada24b6c36ca8020d7f58392f5d3b57ed";
pub const A5_MD_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/PREREG_ADDENDUM_A5_M2_INTAKE_CLOSURE.md";
pub const A5_MD_SHA256: &str = "27195ed9ec526cc152fc6ef45288595b485436deefbb72dfde75827765f3e547";
pub const A5_LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a5_lock.json";
pub const A5_LOCK_SHA256: &str = "d143fd4c97909f06717e1f993ee800bb3e6a610681acaf5fa30c7c715359b544";
/// Addendum A5.1: the F7 cross-check tolerance (amends A5 Q-MDOT-DEL.cross_check only).
pub const A5_1_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a5_1_f7_crosscheck.json";
pub const A5_1_SHA256: &str = "803b9eaaa1107fbabe00a128ac302c3c09ca4731a2d1015a9cbcf5f4e599c0da";
pub const A5_1_MD_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/PREREG_ADDENDUM_A5_1_F7_CROSSCHECK.md";
pub const A5_1_MD_SHA256: &str = "97cb6607541464b6437c71ea9ba87a78091e623aa4a76bbae87b30337e687fd4";
pub const A5_1_LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a5_1_lock.json";
pub const A5_1_LOCK_SHA256: &str = "d56e34f99277aa8dabcbf614d2e7c3d3427be011356a0db4485558ba611bbddd";
/// A5.1 cross-check: |rerun - committed| <= max(K_ULP ulp, R_REL |committed|).
pub const CROSSCHECK_K_ULP: u64 = 4;
pub const CROSSCHECK_R_REL: f64 = 1e-9;

pub const RECORD_SCHEMA: &str = "abep_assess_intake_closure_a5_v1";
pub const A5_CONSTRAINT_ID: &str = "A5-NH-INTAKE";

pub const A5_AREA_BELOW_REQUIRED_T12: &str = "A5_AREA_BELOW_REQUIRED_T12";
pub const A5_AREA_BELOW_REQUIRED_T25: &str = "A5_AREA_BELOW_REQUIRED_T25";
pub const A5_CAPTURE_BELOW_REQUIRED_T12: &str = "A5_CAPTURE_BELOW_REQUIRED_T12";
pub const A5_CAPTURE_BELOW_REQUIRED_T25: &str = "A5_CAPTURE_BELOW_REQUIRED_T25";
pub const A5_DELIVERED_BELOW_REQUIRED_T12: &str = "A5_DELIVERED_BELOW_REQUIRED_T12";
pub const A5_DELIVERED_BELOW_REQUIRED_T25: &str = "A5_DELIVERED_BELOW_REQUIRED_T25";
pub const A5_SCENARIO_DEPENDENT: &str = "A5_SCENARIO_DEPENDENT";
pub const A5_NO_DESIGN_IN_SCENARIO: &str = "A5_NO_DESIGN_IN_SCENARIO";
pub const A5_OUTSIDE_REGISTERED_AREA_LIMIT: &str = "A5_OUTSIDE_REGISTERED_AREA_LIMIT";
pub const A5_NECESSARY_CONDITION_MET_NOTHING_ESTABLISHED: &str = "A5_NECESSARY_CONDITION_MET_NOTHING_ESTABLISHED";
pub const A5_NOT_APPLICABLE_STORED_XE: &str = "A5_NOT_APPLICABLE_STORED_XE";

/// The A5 cell codes (all DESIGN_VARIABLE_LIMIT).
pub const A5_CELL_CODES: [&str; 6] = [
    A5_AREA_BELOW_REQUIRED_T12,
    A5_AREA_BELOW_REQUIRED_T25,
    A5_CAPTURE_BELOW_REQUIRED_T12,
    A5_CAPTURE_BELOW_REQUIRED_T25,
    A5_DELIVERED_BELOW_REQUIRED_T12,
    A5_DELIVERED_BELOW_REQUIRED_T25,
];

/// State verdicts of a level (A5 sec. statewise).
pub const FAILS_IN_EVERY_SCENARIO: &str = "FAILS_IN_EVERY_SCENARIO";
pub const PASSES_IN_EVERY_SCENARIO: &str = "PASSES_IN_EVERY_SCENARIO";
pub const SCENARIO_DEPENDENT: &str = "SCENARIO_DEPENDENT";
pub const NOT_ESTABLISHED_ROBUST_SET_EMPTY: &str = "NOT_ESTABLISHED_ROBUST_SET_EMPTY";
pub const NECESSARY_CONDITION_MET_IN_EVERY_SCENARIO: &str = "NECESSARY_CONDITION_MET_IN_EVERY_SCENARIO";

pub const FEASIBLE_AT_STATE: &str = "FEASIBLE_AT_STATE";
pub const AREA_EFF_LABEL: &str = "AREA_EFF_EQUALS_APERTURE_NO_SPACECRAFT_GEOMETRY_REGISTERED";

/// Comparison levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Level {
    Area,
    Cap,
    Del,
}

impl Level {
    pub const ALL: [Level; 3] = [Level::Area, Level::Cap, Level::Del];

    pub fn as_str(self) -> &'static str {
        match self {
            Level::Area => "L-AREA",
            Level::Cap => "L-CAP",
            Level::Del => "L-DEL",
        }
    }

    /// The cell code of a failing (level, T) (k = 0: T12, 1: T25).
    pub fn code(self, k: usize) -> &'static str {
        A5_CELL_CODES[(self as usize) * 2 + k]
    }
}

pub const TESTS: [&str; 2] = ["T12", "T25"];

// ------------------------------------------------------------------------------------------------ inputs

/// One d-collapsed F1 intake candidate (DS-F1-GRID).
#[derive(Debug, Clone, PartialEq)]
pub struct Candidate {
    pub id: String,
    pub area_m2: f64,
    pub l_over_d: f64,
    pub phi: f64,
}

/// The F1 IF-A1 record of a candidate at one state (harness order).
#[derive(Debug, Clone, PartialEq)]
pub struct Capture {
    /// O, N2, O2 captured flow, kg/s.
    pub species_kg_s: [f64; 3],
    pub f1_status: String,
}

impl Capture {
    pub fn mdot(&self) -> f64 {
        self.species_kg_s.iter().sum()
    }
}

/// One candidate in one surface scenario.
#[derive(Debug, Clone, PartialEq)]
pub struct CandScenario {
    pub candidate: usize,
    pub scenario: String,
    pub rows: Vec<Capture>,
}

impl CandScenario {
    /// F1 envelope feasibility: FEASIBLE_AT_STATE at every required state.
    pub fn f1_feasible(&self, required: &[bool]) -> bool {
        self.rows.iter().zip(required).all(|(r, q)| !q || r.f1_status == FEASIBLE_AT_STATE)
    }
}

/// One F7 Pareto member with its per-state delivered flow from the admitted steady chain (DS-F7-PARETO).
#[derive(Debug, Clone, PartialEq)]
pub struct Member {
    pub design_id: String,
    pub context_id: String,
    pub scenario: String,
    pub filter: String,
    pub wall: String,
    pub context_role: String,
    pub candidate: String,
    pub area_m2: f64,
    pub compressor: String,
    pub v_m3: f64,
    pub p_set_pa: f64,
    /// Harness order, kg/s.
    pub mdot_del: Vec<f64>,
    /// Harness order, O / N2 / O2 mole fractions of the delivered flow.
    pub x_mole: Vec<[f64; 3]>,
    /// Committed F7 values (statewise minimum over the F7 state list, which includes the design-case reference).
    pub mdot_delivered_min_kgps: f64,
    /// The same minimum of the Rust rerun (A5.1 cross-check).
    pub mdot_delivered_min_rerun_kgps: f64,
    pub mdot_captured_min_kgps: f64,
    pub f8_status: String,
}

/// Everything A5 reads besides the A4 quantities and the harness state evaluations.
#[derive(Debug, Clone, PartialEq)]
pub struct IntakeInputs {
    /// Harness state ids (order of the harness).
    pub states: Vec<String>,
    pub candidates: Vec<Candidate>,
    pub scenarios: Vec<String>,
    pub capture: Vec<CandScenario>,
    pub members: Vec<Member>,
    /// The F8 carried robust set (design ids).
    pub robust_members: Vec<String>,
    /// F8 per-survivor scenario records, carried unchanged (design id -> f8_study.scenario entry).
    pub f8_survivors: BTreeMap<String, Value>,
    pub f8_decomposition: Value,
    pub provenance: Vec<(String, String)>,
}

// ------------------------------------------------------------------------------------------------ gather

fn verify_lock(repo: &Path, lock_rel: &str, lock_sha: &str, files: [(&str, &str, &str, &str); 2]) -> AssessResult<()> {
    for (_, rel, sha, _) in files {
        read_verified(&repo.join(rel), sha)?;
    }
    let lock = abep_types::pyjson::loads(
        std::str::from_utf8(&read_verified(&repo.join(lock_rel), lock_sha)?)
            .map_err(|e| model_error(format!("{lock_rel}: {e}")))?,
    )?;
    let names = lock.as_dict().and_then(|d| d.get("files")).and_then(Value::as_dict);
    for (k, _, want, _) in files {
        if names.and_then(|f| f.get(k)).and_then(Value::as_str) != Some(want) {
            return Err(model_error(format!("{lock_rel}: files.{k} != {want}")));
        }
    }
    Ok(())
}

/// A5 and A5.1 identity: json, md and lock verify and each lock names both of its files.
pub fn verify_a5(repo: &Path) -> AssessResult<()> {
    verify_lock(
        repo,
        A5_LOCK_REL,
        A5_LOCK_SHA256,
        [
            ("prereg_addendum_a5_m2_intake_closure.json", A5_REL, A5_SHA256, ""),
            ("PREREG_ADDENDUM_A5_M2_INTAKE_CLOSURE.md", A5_MD_REL, A5_MD_SHA256, ""),
        ],
    )?;
    verify_lock(
        repo,
        A5_1_LOCK_REL,
        A5_1_LOCK_SHA256,
        [
            ("prereg_addendum_a5_1_f7_crosscheck.json", A5_1_REL, A5_1_SHA256, ""),
            ("PREREG_ADDENDUM_A5_1_F7_CROSSCHECK.md", A5_1_MD_REL, A5_1_MD_SHA256, ""),
        ],
    )
}

/// Units in the last place between two finite values of the same sign (A5.1 report).
pub fn ulp_distance(a: f64, b: f64) -> u64 {
    if a.is_sign_negative() != b.is_sign_negative() {
        return u64::MAX;
    }
    a.to_bits().abs_diff(b.to_bits())
}

/// A5.1 cross-check of a rerun statewise minimum against the committed F7 value.
pub fn crosscheck_ok(rerun: f64, committed: f64) -> bool {
    let ulp = f64::from_bits(committed.abs().to_bits() + 1) - committed.abs();
    let tol = (CROSSCHECK_K_ULP as f64 * ulp).max(CROSSCHECK_R_REL * committed.abs());
    rerun.is_finite() && committed.is_finite() && (rerun - committed).abs() <= tol
}

/// Intake-side coefficients of one (candidate, scenario, filter) over the F7 state list, with the F1 feasibility.
type IntakeSide = (Vec<[f64; 3]>, Vec<[f64; 3]>, Vec<bool>);

fn de(e: abep_design::err::DesignError) -> crate::error::AssessError {
    model_error(format!("A5 design chain: {e}"))
}

fn vstr(v: &Value, k: &str) -> AssessResult<String> {
    v.as_dict()
        .and_then(|x| x.get(k))
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| model_error(format!("F7 member: {k}")))
}

fn vnum(v: &Value, k: &str) -> AssessResult<f64> {
    v.as_dict()
        .and_then(|x| x.get(k))
        .and_then(|x| x.to_f64().ok())
        .filter(|x| x.is_finite())
        .ok_or_else(|| model_error(format!("F7 member: {k}")))
}

/// The A5 inputs of the repository (fail closed: any pin, state-set or F7 cross-check mismatch refuses).
pub fn gather_a5(repo: &Path, ti: &crate::closure::TodayInputs) -> AssessResult<IntakeInputs> {
    use super::gather::{
        gz_json, json, F7_PARETO_JSON_SHA256, F7_PARETO_REL, F7_PARETO_SHA256, F8_REPORT_REL, F8_REPORT_SHA256,
        F8_STUDY_JSON_SHA256, F8_STUDY_REL, F8_STUDY_SHA256,
    };
    verify_a5(repo)?;
    let up = abep_design::inputs::load_upstream_inputs(repo).map_err(de)?;
    let states: Vec<String> = ti.states.iter().map(|s| s.state_id.clone()).collect();
    let harness: BTreeSet<&str> = states.iter().map(String::as_str).collect();
    let f1_required: BTreeSet<&str> = up.required_states.iter().map(String::as_str).collect();
    if harness != f1_required {
        return Err(model_error("A5: the F1 required state set differs from the harness state set"));
    }
    let mut candidates: Vec<Candidate> = up
        .candidates
        .iter()
        .map(|c| {
            let (a, ld, phi) = up.geometry[c];
            Candidate { id: c.clone(), area_m2: a, l_over_d: ld, phi }
        })
        .collect();
    candidates.sort_by(|a, b| {
        (a.area_m2, a.l_over_d, a.phi).partial_cmp(&(b.area_m2, b.l_over_d, b.phi)).expect("finite geometry")
    });
    let mut capture = vec![];
    for (ci, c) in candidates.iter().enumerate() {
        if !(c.area_m2.is_finite() && c.area_m2 > 0.0) {
            return Err(model_error(format!("A5: candidate {} area {}", c.id, c.area_m2)));
        }
        for sc in &up.scenarios {
            let mut rows = Vec::with_capacity(states.len());
            for st in &states {
                let r = up.record(&c.id, sc, st).map_err(de)?;
                if r.mdot_fwd_kgps.iter().any(|x| !x.is_finite() || *x < 0.0)
                    || r.mdot_fwd_kgps.iter().sum::<f64>() <= 0.0
                {
                    return Err(model_error(format!("A5: captured flow of {} {sc} {st} not finite / positive", c.id)));
                }
                rows.push(Capture { species_kg_s: r.mdot_fwd_kgps, f1_status: r.f1_status.clone() });
            }
            capture.push(CandScenario { candidate: ci, scenario: sc.clone(), rows });
        }
    }
    // F8: robust set, survivors and their per-scenario records (carried unchanged).
    let study = gz_json(repo, F8_STUDY_REL, F8_STUDY_SHA256, F8_STUDY_JSON_SHA256)?;
    let sd = study.as_dict().ok_or_else(|| model_error("F8 study: not a mapping"))?;
    let robust: Vec<String> = sd
        .get("carried_robust_set")
        .and_then(|x| x.as_dict())
        .and_then(|x| x.get("members"))
        .and_then(Value::as_list)
        .ok_or_else(|| model_error("F8 study: carried_robust_set.members"))?
        .iter()
        .map(|x| x.as_str().map(str::to_string).ok_or_else(|| model_error("F8 robust member id")))
        .collect::<AssessResult<_>>()?;
    let scen = sd.get("scenario").and_then(Value::as_dict).ok_or_else(|| model_error("F8 study: scenario"))?;
    let mut survivors = BTreeMap::new();
    for s in sd.get("survivors").and_then(Value::as_list).ok_or_else(|| model_error("F8 study: survivors"))? {
        let id = vstr(s, "design_id")?;
        let e = scen.get(&id).cloned().ok_or_else(|| model_error(format!("F8 study: no scenario record of {id}")))?;
        survivors.insert(id, e);
    }
    let f8r = json(repo, F8_REPORT_REL, F8_REPORT_SHA256)?;
    let decomposition = f8r
        .as_dict()
        .and_then(|x| x.get("decomposition_rust"))
        .cloned()
        .ok_or_else(|| model_error("F8 report: decomposition_rust"))?;
    // F7 Pareto members and their per-state delivered flow (admitted steady chain).
    let pareto = gz_json(repo, F7_PARETO_REL, F7_PARETO_SHA256, F7_PARETO_JSON_SHA256)?;
    let ctxs = pareto.as_dict().ok_or_else(|| model_error("F7 pareto blocks: not a mapping"))?;
    let f7_index: BTreeMap<&str, usize> = up.states.iter().enumerate().map(|(i, s)| (s.as_str(), i)).collect();
    let h_idx: Vec<usize> = states.iter().map(|s| f7_index[s.as_str()]).collect();
    let mut sides: BTreeMap<(String, String, String), IntakeSide> = BTreeMap::new();
    let mut members = vec![];
    for (ctx, blocks) in ctxs.iter() {
        let parts: Vec<&str> = ctx.split('|').collect();
        let [scenario, filter, wall] = parts[..] else {
            return Err(model_error(format!("F7 context id {ctx}")));
        };
        for b in blocks.as_list().ok_or_else(|| model_error("F7 pareto: blocks"))? {
            let block = b.as_dict().and_then(|x| x.get("block")).ok_or_else(|| model_error("F7 pareto: block"))?;
            let context_id = vstr(block, "context_id")?;
            let ms = block.as_dict().and_then(|x| x.get("members")).and_then(Value::as_list).unwrap_or(&[]);
            for mm in ms {
                let candidate = vstr(mm, "candidate")?;
                let compressor = vstr(mm, "compressor")?;
                let (v_m3, p_set) = (vnum(mm, "V_m3")?, vnum(mm, "P_set_Pa")?);
                let design_id = vstr(mm, "design_id")?;
                if design_id != abep_design::optimizer::design_id(&candidate, filter, &compressor, v_m3, p_set) {
                    return Err(model_error(format!("F7 member {design_id}: design id does not match its fields")));
                }
                let area = up.geometry.get(&candidate).ok_or_else(|| model_error(format!("F7 member {candidate}")))?.0;
                let key = (candidate.clone(), scenario.to_string(), filter.to_string());
                if !sides.contains_key(&key) {
                    let fc = up.filters.get(filter).ok_or_else(|| model_error(format!("F7 filter {filter}")))?;
                    let recs: Vec<IntakeState> = up
                        .states
                        .iter()
                        .map(|st| up.record(&candidate, scenario, st).cloned())
                        .collect::<Result<_, _>>()
                        .map_err(de)?;
                    let (f, e) = intake_side(&recs, fc, 1.0)?;
                    let ok = recs.iter().map(|r| r.f1_status == FEASIBLE_AT_STATE).collect();
                    sides.insert(key.clone(), (f, e, ok));
                }
                let (f, e, ok) = &sides[&key];
                let plant = up.plant(&compressor).map_err(de)?;
                let pl = abep_design::optimizer::plenum(&up, v_m3, wall).map_err(de)?;
                let sw = steady_sweep(&(f.clone(), e.clone()), plant, &pl, &up.materials, &[p_set], Some(ok))?;
                if sw.bits.iter().any(|b| *b != 0) {
                    return Err(model_error(format!("F7 member {design_id} ({ctx}): a state is out of domain")));
                }
                let committed = vnum(mm, "mdot_delivered_min_kgps")?;
                let min = sw.mdot_total_kgps.iter().copied().fold(f64::INFINITY, f64::min);
                if !crosscheck_ok(min, committed) {
                    return Err(model_error(format!(
                        "F7 member {design_id} ({ctx}): statewise minimum {min:e} differs from committed {committed:e} \
                         beyond max({CROSSCHECK_K_ULP} ulp, {CROSSCHECK_R_REL:e} relative) (A5.1)"
                    )));
                }
                let f8_status = if robust.contains(&design_id) {
                    "ROBUST_MEMBER"
                } else if survivors.contains_key(&design_id) {
                    "F8_SURVIVOR_NOT_ROBUST"
                } else {
                    "NOT_AN_F8_SURVIVOR"
                };
                members.push(Member {
                    design_id,
                    context_id: context_id.clone(),
                    scenario: scenario.to_string(),
                    filter: filter.to_string(),
                    wall: wall.to_string(),
                    context_role: vstr(mm, "context_role")?,
                    candidate,
                    area_m2: area,
                    compressor,
                    v_m3,
                    p_set_pa: p_set,
                    mdot_del: h_idx.iter().map(|i| sw.mdot_total_kgps[*i]).collect(),
                    x_mole: h_idx
                        .iter()
                        .map(|i| [sw.x_s_flow_mole[0][*i], sw.x_s_flow_mole[1][*i], sw.x_s_flow_mole[2][*i]])
                        .collect(),
                    mdot_delivered_min_kgps: committed,
                    mdot_delivered_min_rerun_kgps: min,
                    mdot_captured_min_kgps: vnum(mm, "mdot_captured_min_kgps")?,
                    f8_status: f8_status.into(),
                });
            }
        }
    }
    let mut provenance = vec![
        (A5_REL.to_string(), A5_SHA256.to_string()),
        (A5_MD_REL.to_string(), A5_MD_SHA256.to_string()),
        (A5_LOCK_REL.to_string(), A5_LOCK_SHA256.to_string()),
        (A5_1_REL.to_string(), A5_1_SHA256.to_string()),
        (A5_1_MD_REL.to_string(), A5_1_MD_SHA256.to_string()),
        (A5_1_LOCK_REL.to_string(), A5_1_LOCK_SHA256.to_string()),
        (abep_mission::intake_drag::F1_CORE_REL.to_string(), abep_mission::intake_drag::F1_CORE_SHA256.to_string()),
        (F7_PARETO_REL.to_string(), F7_PARETO_SHA256.to_string()),
        (F8_STUDY_REL.to_string(), F8_STUDY_SHA256.to_string()),
        (F8_REPORT_REL.to_string(), F8_REPORT_SHA256.to_string()),
    ];
    for (p, s) in abep_design::inputs::PINNED {
        provenance.push((p.to_string(), s.to_string()));
    }
    Ok(IntakeInputs {
        states,
        candidates,
        scenarios: up.scenarios.clone(),
        capture,
        members,
        robust_members: robust,
        f8_survivors: survivors,
        f8_decomposition: decomposition,
        provenance,
    })
}

// ------------------------------------------------------------------------------------------------ evaluate

/// The per-state requirement inputs (A4 quantities and the admitted free stream).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Req {
    pub p_avail_w: f64,
    pub phi_max: f64,
    pub q_max: f64,
    pub phi_adm: f64,
    /// sum over O, N2, O2 of rho_i V_adm, kg m^-2 s^-1.
    pub phi_3: f64,
    pub a_req: [f64; 2],
    /// A9.35 carried-forward requirement (electric power only), kg/s.
    pub mdot_req: [f64; 2],
}

impl Req {
    /// mdot_req,in(A, T): A4 K-MDOT-REQ at P_avail + q_max A.
    pub fn mdot_req_in(&self, area_m2: f64, k: usize, t_req: [f64; 2]) -> AssessResult<f64> {
        Ok(abep_mission::conservation_bounds::mdot_required(t_req[k], self.p_avail_w + self.q_max * area_m2)?)
    }
}

/// The best design of one scenario at one state for one (level, T).
#[derive(Debug, Clone, PartialEq)]
pub struct Best {
    pub scenario: String,
    /// None: no design of the set in this scenario.
    pub k: Option<f64>,
    pub design: Option<String>,
}

/// One (level, T) at one state.
#[derive(Debug, Clone, PartialEq)]
pub struct LevelState {
    pub verdict: &'static str,
    pub per_scenario: Vec<Best>,
    pub k_fav: Option<f64>,
    pub fav: Option<(String, String)>,
    /// None when some scenario has no design (unbounded) or none is evaluated.
    pub k_unfav: Option<f64>,
    pub unfav: Option<(String, String)>,
    pub no_design_scenarios: Vec<String>,
}

/// (state index, multiplier there; None: unbounded).
pub type WorstState = (usize, Option<f64>);

/// The values of one design at one state (for the worst-state report).
#[derive(Debug, Clone, PartialEq)]
pub struct DesignValues {
    pub mdot_cap: f64,
    pub eta_c: f64,
    pub eta_tot: f64,
    pub eta_vs_bound: f64,
    pub a_cap_eq: f64,
    pub species_mass_fraction: [f64; 3],
}

#[derive(Debug, Clone, PartialEq)]
pub struct StateA5 {
    pub state_id: String,
    pub required: bool,
    pub status: EvalStatus,
    pub codes: Vec<String>,
    pub req: Option<Req>,
    /// mdot_req,in at the admissible area(s) is design-dependent; reported at the largest admissible area.
    pub levels: BTreeMap<(Level, usize), LevelState>,
    /// Best captured flow over the admissible designs and scenarios: (mdot, candidate, scenario).
    pub best_cap: Option<(f64, String, String)>,
    /// Best delivered flow over the F7 members: (mdot, design id, scenario, x_O).
    pub best_del: Option<(f64, String, String, f64)>,
    /// L-HALL: smallest mdot of an AIR envelope point passing T12 / T25 (None: none).
    pub hall_min_mdot: [Option<f64>; 2],
    /// Cell codes added at this state (required AIR only).
    pub cell_codes: Vec<String>,
}

/// One design row (candidate x scenario, or F7 member) per T.
#[derive(Debug, Clone, PartialEq)]
pub struct DesignRow {
    pub id: String,
    pub scenario: String,
    pub admissible: bool,
    pub codes: Vec<String>,
    /// per T: (worst state index, multiplier there (None: unbounded), number of failing evaluated required states)
    pub worst: [Option<(usize, Option<f64>, usize)>; 2],
    pub n_f1_infeasible_states: usize,
    pub f1_reason_example: Option<String>,
}

/// One-hardware verdict of one (level, T).
#[derive(Debug, Clone, PartialEq)]
pub struct OneHardware {
    pub verdict: &'static str,
    /// scenario -> designs passing at every evaluated required state
    pub per_scenario: Vec<(String, usize)>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct IntakeOutcome {
    pub states: Vec<StateA5>,
    pub t_req_n: [f64; 2],
    /// (candidate x scenario) rows: L-AREA and L-CAP multipliers (k_cap for the worst state).
    pub cand_rows: Vec<(DesignRow, DesignRow)>,
    /// F7 member rows (L-DEL).
    pub member_rows: Vec<DesignRow>,
    pub one_hardware: BTreeMap<(Level, usize), OneHardware>,
    /// Worst required state per (level, T): (state index, k_fav (None: unbounded)).
    pub worst: BTreeMap<(Level, usize), Option<WorstState>>,
    /// Candidates excluded by a FROZEN area limit; candidates above a PROVISIONAL one (flagged only).
    pub excluded: Vec<String>,
    pub flagged: Vec<String>,
    pub area_limit: String,
    /// Required AIR states with A5-NH-INTAKE.
    pub cells: BTreeSet<String>,
}

fn values(c: &Capture, area: f64, r: &Req) -> DesignValues {
    let m = c.mdot();
    DesignValues {
        mdot_cap: m,
        eta_c: m / (area * r.phi_3),
        eta_tot: m / (area * r.phi_adm),
        eta_vs_bound: m / (area * r.phi_max),
        a_cap_eq: m / r.phi_max,
        species_mass_fraction: [c.species_kg_s[0] / m, c.species_kg_s[1] / m, c.species_kg_s[2] / m],
    }
}

/// The values of candidate `ci` in `scenario` at harness state index `i` (None: unknown candidate / scenario).
pub fn design_values(
    a5: &IntakeInputs,
    out: &IntakeOutcome,
    ci: usize,
    scenario: &str,
    i: usize,
) -> Option<DesignValues> {
    let r = out.states.get(i)?.req.as_ref()?;
    let cs = a5.capture.iter().find(|c| c.candidate == ci && c.scenario == scenario)?;
    Some(values(&cs.rows[i], a5.candidates[ci].area_m2, r))
}

fn requirement(e: &conservation::StateEnv, sb: &conservation::StateBound) -> Option<Req> {
    let air = sb.modes.get(&Mode::AirPrimary)?;
    let fl = sb.flux.as_ref()?;
    let phi_adm = sb.phi_adm?;
    let v = e.v_adm_m_s;
    let phi_3 = (e.n_o_m3 * M_O + e.n_n2_m3 * M_N2 + e.n_o2_m3 * M_O2) * v;
    let ok = |x: f64| x.is_finite() && x > 0.0;
    let r = Req {
        p_avail_w: air.p_avail_w?,
        phi_max: fl.phi_max_kg_m2_s,
        q_max: fl.q_max_w_m2,
        phi_adm,
        phi_3,
        a_req: air.a_req?,
        mdot_req: air.mdot_req?,
    };
    (ok(r.p_avail_w) && ok(r.phi_max) && ok(r.phi_adm) && ok(r.phi_3) && r.q_max.is_finite() && r.q_max >= 0.0)
        .then_some(r)
}

fn level_state(level: Level, per: Vec<Best>, robust_pass_every: Option<bool>) -> LevelState {
    let fails = |b: &Best| b.k.is_none_or(|k| k > 1.0);
    let all_fail = per.iter().all(fails);
    let none_fail = !per.iter().any(fails);
    let verdict = if all_fail {
        FAILS_IN_EVERY_SCENARIO
    } else {
        match level {
            Level::Area | Level::Cap if none_fail => PASSES_IN_EVERY_SCENARIO,
            Level::Area | Level::Cap => SCENARIO_DEPENDENT,
            Level::Del => match robust_pass_every {
                None => NOT_ESTABLISHED_ROBUST_SET_EMPTY,
                Some(true) => PASSES_IN_EVERY_SCENARIO,
                Some(false) => SCENARIO_DEPENDENT,
            },
        }
    };
    let with: Vec<(&Best, f64)> = per.iter().filter_map(|b| b.k.map(|k| (b, k))).collect();
    let fav = with.iter().min_by(|a, b| a.1.total_cmp(&b.1)).map(|x| x.0);
    let unf = with.iter().max_by(|a, b| a.1.total_cmp(&b.1)).map(|x| x.0);
    let no_design: Vec<String> = per.iter().filter(|b| b.design.is_none()).map(|b| b.scenario.clone()).collect();
    let pair = |b: &Best| (b.design.clone().unwrap_or_default(), b.scenario.clone());
    LevelState {
        verdict,
        k_fav: fav.and_then(|b| b.k),
        fav: fav.map(pair),
        k_unfav: if no_design.is_empty() { unf.and_then(|b| b.k) } else { None },
        unfav: if no_design.is_empty() { unf.map(pair) } else { None },
        no_design_scenarios: no_design,
        per_scenario: per,
    }
}

fn better(a: &mut Option<(f64, String)>, k: f64, id: &str) {
    if a.as_ref().is_none_or(|(x, _)| k < *x) {
        *a = Some((k, id.to_string()));
    }
}

/// Every A5 quantity and verdict (pure). `hall` is the L-HALL information per harness state.
pub fn evaluate_a5(
    a5: &IntakeInputs,
    a4in: &A4Inputs,
    a4: &A4Outcome,
    lim: &HallLimits,
    required: &[bool],
    hall: &[[Option<f64>; 2]],
) -> AssessResult<IntakeOutcome> {
    let n = a5.states.len();
    if a4in.states.len() != n
        || a4.states.len() != n
        || required.len() != n
        || hall.len() != n
        || a4in.states.iter().zip(&a5.states).any(|(e, s)| &e.state_id != s)
        || a4.states.iter().zip(&a5.states).any(|(e, s)| &e.state_id != s)
    {
        return Err(model_error("A5: state lists of A5, A4 and the harness differ"));
    }
    let t_req = [lim.thrust_min_n, lim.thrust_capability_n];
    let (limit, frozen, area_limit) = match &a4in.area {
        AreaLimit::NotRegistered => (None, false, "NOT_REGISTERED (A4-REG-01 OPEN): nothing excluded".to_string()),
        AreaLimit::Registered { value_m2, status, provenance } => {
            (Some(*value_m2), status == "FROZEN", format!("{value_m2} m^2 {status} ({provenance})"))
        }
    };
    let over = |a: f64| limit.is_some_and(|l| a > l);
    let excluded: Vec<String> =
        a5.candidates.iter().filter(|c| frozen && over(c.area_m2)).map(|c| c.id.clone()).collect();
    let flagged: Vec<String> =
        a5.candidates.iter().filter(|c| !frozen && over(c.area_m2)).map(|c| c.id.clone()).collect();
    let admissible: Vec<bool> = a5
        .capture
        .iter()
        .map(|cs| cs.f1_feasible(required) && !excluded.contains(&a5.candidates[cs.candidate].id))
        .collect();
    let member_ok: Vec<bool> = a5.members.iter().map(|m| !(frozen && over(m.area_m2))).collect();
    let robust_empty = a5.robust_members.is_empty();
    let mut states = Vec::with_capacity(n);
    for i in 0..n {
        let (e, sb) = (&a4in.states[i], &a4.states[i]);
        let req = requirement(e, sb);
        let mut st = StateA5 {
            state_id: a5.states[i].clone(),
            required: required[i],
            status: if req.is_some() { EvalStatus::Evaluated } else { EvalStatus::NotEvaluated },
            codes: vec![],
            req,
            levels: BTreeMap::new(),
            best_cap: None,
            best_del: None,
            hall_min_mdot: hall[i],
            cell_codes: vec![],
        };
        let Some(r) = req else {
            let mut c = sb.codes.clone();
            if let Some(m) = sb.modes.get(&Mode::AirPrimary) {
                c.extend(m.codes.iter().cloned());
            }
            c.sort();
            c.dedup();
            st.codes = c;
            states.push(st);
            continue;
        };
        for k in 0..2 {
            let mut per_area = vec![];
            let mut per_cap = vec![];
            let mut per_del = vec![];
            let mut robust_pass: Vec<bool> = vec![];
            for sc in &a5.scenarios {
                let (mut ba, mut bc, mut bd, mut br) = (None, None, None, None::<(f64, String)>);
                for (cs, _) in a5.capture.iter().zip(&admissible).filter(|(cs, ok)| **ok && &cs.scenario == sc) {
                    let c = &a5.candidates[cs.candidate];
                    better(&mut ba, r.a_req[k] / c.area_m2, &c.id);
                    let need = r.mdot_req_in(c.area_m2, k, t_req)?;
                    better(&mut bc, need / cs.rows[i].mdot(), &c.id);
                }
                for (m, _) in a5.members.iter().zip(&member_ok).filter(|(m, ok)| **ok && &m.scenario == sc) {
                    let need = r.mdot_req_in(m.area_m2, k, t_req)?;
                    let kd = if m.mdot_del[i] > 0.0 { need / m.mdot_del[i] } else { f64::INFINITY };
                    better(&mut bd, kd, &m.design_id);
                    if a5.robust_members.contains(&m.design_id) {
                        better(&mut br, kd, &m.design_id);
                    }
                }
                let mk = |b: Option<(f64, String)>| Best {
                    scenario: sc.clone(),
                    k: b.as_ref().map(|x| x.0),
                    design: b.map(|x| x.1),
                };
                robust_pass.push(br.as_ref().is_some_and(|x| x.0 <= 1.0));
                per_area.push(mk(ba));
                per_cap.push(mk(bc));
                per_del.push(mk(bd));
            }
            let robust = (!robust_empty).then(|| robust_pass.iter().all(|x| *x));
            st.levels.insert((Level::Area, k), level_state(Level::Area, per_area, None));
            st.levels.insert((Level::Cap, k), level_state(Level::Cap, per_cap, None));
            st.levels.insert((Level::Del, k), level_state(Level::Del, per_del, robust));
        }
        for (cs, _) in a5.capture.iter().zip(&admissible).filter(|(_, ok)| **ok) {
            let m = cs.rows[i].mdot();
            if st.best_cap.as_ref().is_none_or(|b| m > b.0) {
                st.best_cap = Some((m, a5.candidates[cs.candidate].id.clone(), cs.scenario.clone()));
            }
        }
        for (m, _) in a5.members.iter().zip(&member_ok).filter(|(_, ok)| **ok) {
            if st.best_del.as_ref().is_none_or(|b| m.mdot_del[i] > b.0) {
                st.best_del = Some((m.mdot_del[i], m.design_id.clone(), m.scenario.clone(), m.x_mole[i][0]));
            }
        }
        if required[i] {
            for k in 0..2 {
                for l in Level::ALL {
                    if st.levels[&(l, k)].verdict == FAILS_IN_EVERY_SCENARIO {
                        st.cell_codes.push(l.code(k).to_string());
                    }
                }
            }
            st.cell_codes.sort();
        }
        states.push(st);
    }
    // Per-design rows.
    let eval_req: Vec<usize> = (0..n).filter(|i| required[*i] && states[*i].status == EvalStatus::Evaluated).collect();
    let row = |id: &str, sc: &str, adm: bool, codes: Vec<String>, kf: &dyn Fn(usize, usize) -> AssessResult<f64>| {
        let mut worst = [None, None];
        for (k, w) in worst.iter_mut().enumerate() {
            let mut acc: Option<(usize, f64)> = None;
            let mut n_fail = 0;
            for &i in &eval_req {
                let x = kf(i, k)?;
                if x > 1.0 {
                    n_fail += 1;
                }
                if acc.is_none_or(|(_, a)| x > a) {
                    acc = Some((i, x));
                }
            }
            *w = acc.map(|(i, x)| (i, x.is_finite().then_some(x), n_fail));
        }
        Ok::<DesignRow, crate::error::AssessError>(DesignRow {
            id: id.to_string(),
            scenario: sc.to_string(),
            admissible: adm,
            codes,
            worst,
            n_f1_infeasible_states: 0,
            f1_reason_example: None,
        })
    };
    let mut cand_rows = vec![];
    for (j, cs) in a5.capture.iter().enumerate() {
        let c = &a5.candidates[cs.candidate];
        let mut codes = vec![];
        if excluded.contains(&c.id) || flagged.contains(&c.id) {
            codes.push(A5_OUTSIDE_REGISTERED_AREA_LIMIT.to_string());
        }
        let infeasible: Vec<&Capture> = cs
            .rows
            .iter()
            .zip(required)
            .filter(|(r, q)| **q && r.f1_status != FEASIBLE_AT_STATE)
            .map(|x| x.0)
            .collect();
        let ka =
            |i: usize, k: usize| -> AssessResult<f64> { Ok(states[i].req.expect("evaluated").a_req[k] / c.area_m2) };
        let kc = |i: usize, k: usize| -> AssessResult<f64> {
            let r = states[i].req.expect("evaluated");
            Ok(r.mdot_req_in(c.area_m2, k, t_req)? / cs.rows[i].mdot())
        };
        let mut ra = row(&c.id, &cs.scenario, admissible[j], codes.clone(), &ka)?;
        let mut rc = row(&c.id, &cs.scenario, admissible[j], codes, &kc)?;
        for r in [&mut ra, &mut rc] {
            r.n_f1_infeasible_states = infeasible.len();
            r.f1_reason_example = infeasible.first().map(|x| x.f1_status.clone());
        }
        cand_rows.push((ra, rc));
    }
    let mut member_rows = vec![];
    for (m, ok) in a5.members.iter().zip(&member_ok) {
        let kd = |i: usize, k: usize| -> AssessResult<f64> {
            let r = states[i].req.expect("evaluated");
            let need = r.mdot_req_in(m.area_m2, k, t_req)?;
            Ok(if m.mdot_del[i] > 0.0 { need / m.mdot_del[i] } else { f64::INFINITY })
        };
        let codes = if *ok { vec![] } else { vec![A5_OUTSIDE_REGISTERED_AREA_LIMIT.to_string()] };
        member_rows.push(row(&m.design_id, &m.scenario, *ok, codes, &kd)?);
    }
    // One hardware per (level, T): per scenario, the designs passing at every evaluated required state.
    let mut one_hardware = BTreeMap::new();
    for k in 0..2 {
        for l in Level::ALL {
            let mut per = vec![];
            let mut robust_every = true;
            for sc in &a5.scenarios {
                let (count, robust_count) = match l {
                    Level::Area | Level::Cap => {
                        let c = cand_rows
                            .iter()
                            .filter(|(ra, rc)| {
                                let r = if l == Level::Area { ra } else { rc };
                                r.admissible && &r.scenario == sc && r.worst[k].is_some_and(|w| w.2 == 0)
                            })
                            .count();
                        (c, 0)
                    }
                    Level::Del => {
                        let pass: Vec<&DesignRow> = member_rows
                            .iter()
                            .filter(|r| r.admissible && &r.scenario == sc && r.worst[k].is_some_and(|w| w.2 == 0))
                            .collect();
                        let rc = pass.iter().filter(|r| a5.robust_members.contains(&r.id)).count();
                        (pass.len(), rc)
                    }
                };
                robust_every &= robust_count > 0;
                per.push((sc.clone(), count));
            }
            let all = per.iter().all(|x| x.1 > 0);
            let none = per.iter().all(|x| x.1 == 0);
            let verdict = if none {
                FAILS_IN_EVERY_SCENARIO
            } else if l == Level::Del && robust_empty {
                NOT_ESTABLISHED_ROBUST_SET_EMPTY
            } else if (l != Level::Del && all) || (l == Level::Del && robust_every) {
                NECESSARY_CONDITION_MET_IN_EVERY_SCENARIO
            } else {
                SCENARIO_DEPENDENT
            };
            one_hardware.insert((l, k), OneHardware { verdict, per_scenario: per });
        }
    }
    // Worst required state per (level, T).
    let mut worst = BTreeMap::new();
    for k in 0..2 {
        for l in Level::ALL {
            let mut acc: Option<(usize, f64)> = None;
            for &i in &eval_req {
                let x = states[i].levels[&(l, k)].k_fav.unwrap_or(f64::INFINITY);
                if acc.is_none_or(|(_, a)| x > a) {
                    acc = Some((i, x));
                }
            }
            worst.insert((l, k), acc.map(|(i, x)| (i, x.is_finite().then_some(x))));
        }
    }
    let cells = states.iter().filter(|s| !s.cell_codes.is_empty()).map(|s| s.state_id.clone()).collect();
    Ok(IntakeOutcome {
        states,
        t_req_n: t_req,
        cand_rows,
        member_rows,
        one_hardware,
        worst,
        excluded,
        flagged,
        area_limit,
        cells,
    })
}

/// The constraint A5 adds to a required AIR cell (A5 classification_effect.cell_constraint).
pub fn a5_constraint(codes: &[String], state: &StateA5) -> Constraint {
    let what: Vec<String> = Level::ALL
        .iter()
        .flat_map(|l| {
            (0..2).filter_map(move |k| {
                state.levels.get(&(*l, k)).filter(|x| x.verdict == FAILS_IN_EVERY_SCENARIO).map(|x| {
                    format!(
                        "{} {} (k_fav {})",
                        l.as_str(),
                        TESTS[k],
                        x.k_fav.map_or("unbounded".to_string(), |v| format!("{v:.4}"))
                    )
                })
            })
        })
        .collect();
    Constraint {
        id: A5_CONSTRAINT_ID.into(),
        hall_specific: false,
        status: NON_CLOSING,
        eligible_close: false,
        eligible_non_close: false,
        codes: codes.to_vec(),
        detail: format!(
            "the registered intake / gas-path designs miss the A4 necessary condition in every surface scenario: {}; \
             DESIGN_VARIABLE_LIMIT (A9.35), never eligible (A4-REG-01 OPEN)",
            what.join(", ")
        ),
        evidence_conditions: vec![],
    }
}

/// Apply the A5 cell constraints to the harness states (pure; A5 classification_effect).
pub fn apply_cells(out: &IntakeOutcome, states: &mut [(StateRef, BTreeMap<Mode, StateModeEval>)]) {
    for ((st, ms), a) in states.iter_mut().zip(&out.states) {
        if !st.required || a.cell_codes.is_empty() {
            continue;
        }
        let Some(e) = ms.get_mut(&Mode::AirPrimary) else { continue };
        e.eval.constraints.push(a5_constraint(&a.cell_codes, a));
        if e.eval.status != PHYSICS_NON_CLOSING {
            e.eval.status = NOT_DETERMINABLE;
            let mut b: BTreeSet<String> = e.eval.blockers.iter().cloned().collect();
            b.extend(a.cell_codes.iter().cloned());
            e.eval.blockers = b.into_iter().collect();
        }
    }
}

/// L-HALL information: per harness state, the smallest mdot of an AIR envelope point passing T12 / T25 at the
/// state's P_nonHall,LB (none today).
pub fn hall_min_mdot(inp: &M1Inputs, states: &[(StateRef, BTreeMap<Mode, StateModeEval>)]) -> Vec<[Option<f64>; 2]> {
    let pts = mode_points(inp, Mode::AirPrimary);
    states
        .iter()
        .map(|(st, ms)| {
            let excluded = match &inp.air {
                AirHall::Ingested(a) => a.state_exclusions.contains_key(&st.state_id),
                AirHall::NotAvailable(_) => true,
            };
            let Some(e) = ms.get(&Mode::AirPrimary) else { return [None, None] };
            if excluded {
                return [None, None];
            }
            let lim = HallLimits { p_non_hall_lb_w: e.bus.lb_w, ..inp.today.limits };
            let f = |t: HallTest| {
                pts.iter()
                    .filter(|x| v1::point_passes(t, x.p, &lim))
                    .map(|x| x.p.case.mdot_kg_s)
                    .fold(None, |a: Option<f64>, m| Some(a.map_or(m, |a| a.min(m))))
            };
            [f(HallTest::T12), f(HallTest::T25)]
        })
        .collect()
}
