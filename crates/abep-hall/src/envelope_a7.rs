//! NP-HALL-PARAMETRIC-ENVELOPE addendum A7 (Hall numerical method;
//! `prereg_addendum_a7_hall_numerical_method_v1.json`, locked by `prereg_addendum_a7_hall_numerical_method_lock_v1.json`):
//! the A7 run-status rule, the per-case convergence comparison and the ingestion of a frozen A7 XE grid stage.
//! PARAMETRIC / NOT_VALIDATED. Raw observables come from `hallthruster_bridge/a7_numerics.jl` (time-means of the
//! per-frame instantaneous thrust and discharge current over the registered window, with batch-means standard errors);
//! this module applies the registered rules only. Thresholds and verdicts of the closure stay in abep-assess.

use crate::envelope::{
    case_hash, load_case_set, BzFamilyKind, CaseInfo, Envelope, EnvelopePoint, Family, RunStatus,
    LOCK_SHA256 as V1_LOCK_SHA256,
};
use crate::hall_map::pinned_commit;
use abep_provenance::read_verified;
use abep_types::pyjson::{self, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::BTreeMap;
use std::io::Read;
use std::path::Path;

pub const NP: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE";
pub const ADDENDUM_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a7_hall_numerical_method_v1.json";
pub const LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a7_hall_numerical_method_lock_v1.json";
pub const ADDENDUM_SHA256: &str = "58b0c20c977907c0aa23b420f28ff569081a40415907584df1bc3c52bb1adaa4";
pub const LOCK_SHA256: &str = "26fc6d53548a63ac792b013673d047753b79f3280cf1f6240232c13142e79299";
pub const A7_BRIDGE_REL: &str = "hallthruster_bridge/a7_numerics.jl";
pub const RAW_SCHEMA: &str = "np_hall_parametric_envelope_a7_raw_manifest_v1";

/// Relative tolerance of the A3 / A6 basis (thrust and I_d).
pub const TOL_REL: f64 = 0.02;
/// Coverage factor on the combined batch-means standard error.
pub const K_SIGMA: f64 = 2.0;
/// Largest relative batch-means standard error of thrust or I_d for a run to be statistically resolved.
pub const SE_CAP_REL: f64 = 0.025;
/// Quiet class: window RMS / mean of I_d below this (v1 / A3).
pub const QUIET_RMS: f64 = 0.5;
/// Extinct: window-mean I_d below this fraction of the singly-charged equivalent current e mdot / m_Xe.
pub const EXTINCT_FRACTION: f64 = 1e-3;
/// Xenon atomic mass (kg): 131.293 u (IUPAC 2021 standard atomic weight) x 1.66053906660e-27 kg.
pub const M_XE_KG: f64 = 131.293 * 1.660_539_066_60e-27;
pub const E_CHARGE_C: f64 = 1.602_176_634e-19;

/// A7 run status, in precedence order. PASS and NOT_SUSTAINED are evaluated physics; the others are unknowns (never
/// feasible, never an evaluated non-closure).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum A7Status {
    NumericalFailure,
    Extinct,
    NotSustained,
    NonStationary,
    StatisticallyUnresolved,
    Pass,
}

impl A7Status {
    pub const ALL: [A7Status; 6] = [
        A7Status::NumericalFailure,
        A7Status::Extinct,
        A7Status::NotSustained,
        A7Status::NonStationary,
        A7Status::StatisticallyUnresolved,
        A7Status::Pass,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            A7Status::NumericalFailure => "NUMERICAL_FAILURE",
            A7Status::Extinct => "EXTINCT",
            A7Status::NotSustained => "NOT_SUSTAINED",
            A7Status::NonStationary => "NON_STATIONARY",
            A7Status::StatisticallyUnresolved => "STATISTICALLY_UNRESOLVED",
            A7Status::Pass => "PASS",
        }
    }

    pub fn is_evaluated_physics(self) -> bool {
        matches!(self, A7Status::Pass | A7Status::NotSustained)
    }

    /// Status class compared by C-STATUS: PASS, NOT_SUSTAINED or UNKNOWN.
    pub fn class(self) -> &'static str {
        match self {
            A7Status::Pass => "PASS",
            A7Status::NotSustained => "NOT_SUSTAINED",
            _ => "UNKNOWN",
        }
    }

    /// The v1 run status an A7 point carries into the envelope (every unknown as NUMERICAL_FAILURE: never feasible,
    /// never evaluated physics).
    pub fn envelope_status(self) -> RunStatus {
        match self {
            A7Status::Pass => RunStatus::Pass,
            A7Status::NotSustained => RunStatus::NotSustained,
            _ => RunStatus::NumericalFailure,
        }
    }
}

fn get<'a>(v: &'a Value, k: &str) -> Option<&'a Value> {
    v.as_dict().and_then(|d| d.get(k))
}

fn num(v: &Value, k: &str) -> Option<f64> {
    match get(v, k) {
        Some(x @ (Value::Int(_) | Value::Float(_))) => x.to_f64().ok().filter(|f| f.is_finite()),
        _ => None,
    }
}

fn pair(v: &Value, k: &str) -> Option<(f64, f64)> {
    let l = get(v, k).and_then(Value::as_list)?;
    if l.len() != 2 {
        return None;
    }
    let f = |x: &Value| x.to_f64().ok().filter(|f| f.is_finite());
    Some((f(&l[0])?, f(&l[1])?))
}

fn is_true(v: &Value, k: &str) -> bool {
    matches!(get(v, k), Some(Value::Bool(true)))
}

/// One windowed observable of a record: mean, batch-means SE, half-window means.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Obs {
    pub mean: f64,
    pub se: f64,
    pub half: (f64, f64),
}

impl Obs {
    fn read(r: &Value, mean: &str, se: &str, half: &str) -> Option<Obs> {
        Some(Obs { mean: num(r, mean)?, se: num(r, se)?, half: pair(r, half)? })
    }

    pub fn se_rel(&self) -> f64 {
        self.se / self.mean.abs()
    }

    /// Stationarity: the half-window means agree within TOL_REL |mean| + K_SIGMA x 2 SE (the SE of a half-window mean
    /// is ~ sqrt(2) SE, so their difference has SE ~ 2 SE).
    pub fn stationary(&self) -> bool {
        (self.half.0 - self.half.1).abs() <= TOL_REL * self.mean.abs() + K_SIGMA * 2.0 * self.se
    }
}

pub fn thrust_obs(r: &Value) -> Option<Obs> {
    Obs::read(r, "thrust_N", "thrust_se_N", "thrust_half_means_N")
}

pub fn current_obs(r: &Value) -> Option<Obs> {
    Obs::read(r, "discharge_current_A", "discharge_current_se_A", "discharge_current_half_means_A")
}

/// The A7 run status of one raw A7 record of a case with anode flow `mdot_kg_s` (precedence order).
pub fn a7_status(r: &Value, mdot_kg_s: f64) -> A7Status {
    let (t, i) = (thrust_obs(r), current_obs(r));
    let numeric_ok = get(r, "retcode").and_then(Value::as_str) == Some("success")
        && is_true(r, "converged")
        && is_true(r, "finite")
        && num(r, "discharge_power_W").is_some()
        && num(r, "Id_rms_rel").is_some();
    let (Some(t), Some(i), true) = (t, i, numeric_ok) else {
        return A7Status::NumericalFailure;
    };
    if i.mean < EXTINCT_FRACTION * E_CHARGE_C * mdot_kg_s / M_XE_KG {
        return A7Status::Extinct;
    }
    if !is_true(r, "sustained") {
        return A7Status::NotSustained;
    }
    if !(t.stationary() && i.stationary()) {
        return A7Status::NonStationary;
    }
    if t.se_rel() > SE_CAP_REL || i.se_rel() > SE_CAP_REL {
        return A7Status::StatisticallyUnresolved;
    }
    A7Status::Pass
}

/// Agreement of one observable between the production level `p` and the check level `c`:
/// |X_p - X_c| <= TOL_REL |X_c| + K_SIGMA sqrt(SE_p^2 + SE_c^2). Returns (relative difference, allowance / |X_c|, ok).
pub fn agree(p: &Obs, c: &Obs) -> (f64, f64, bool) {
    let d = (p.mean - c.mean).abs();
    let allow = TOL_REL * c.mean.abs() + K_SIGMA * (p.se * p.se + c.se * c.se).sqrt();
    (d / c.mean.abs(), allow / c.mean.abs(), d <= allow)
}

/// The convergence comparison of one case (production level vs check level).
#[derive(Debug, Clone, PartialEq)]
pub struct A7Comparison {
    pub status_p: A7Status,
    pub status_c: A7Status,
    pub c_status: bool,
    pub c_quiet: Option<bool>,
    pub thrust: Option<(f64, f64, bool)>,
    pub current: Option<(f64, f64, bool)>,
}

/// Case outcome of a comparison.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CaseOutcome {
    /// Evaluated at both levels and every criterion passes.
    ConvergedEvaluated,
    /// Unknown at both levels (never feasible; reported, counted).
    PersistentUnknown,
    /// Any criterion fails.
    NotConverged,
}

impl CaseOutcome {
    pub fn as_str(self) -> &'static str {
        match self {
            CaseOutcome::ConvergedEvaluated => "CONVERGED_EVALUATED",
            CaseOutcome::PersistentUnknown => "PERSISTENT_UNKNOWN",
            CaseOutcome::NotConverged => "NOT_CONVERGED",
        }
    }
}

impl A7Comparison {
    pub fn outcome(&self) -> CaseOutcome {
        if !self.c_status {
            return CaseOutcome::NotConverged;
        }
        if self.status_p.class() == "UNKNOWN" {
            return CaseOutcome::PersistentUnknown;
        }
        let ok = |x: &Option<(f64, f64, bool)>| x.is_none_or(|(_, _, b)| b);
        if self.c_quiet == Some(false) || !ok(&self.thrust) || !ok(&self.current) {
            CaseOutcome::NotConverged
        } else {
            CaseOutcome::ConvergedEvaluated
        }
    }
}

fn quiet(r: &Value) -> Option<bool> {
    num(r, "Id_rms_rel").map(|x| x < QUIET_RMS)
}

/// Compare the production-level and check-level records of one case (an absent record is NUMERICAL_FAILURE).
pub fn compare(p: Option<&Value>, c: Option<&Value>, mdot_kg_s: f64) -> A7Comparison {
    let st = |r: Option<&Value>| r.map_or(A7Status::NumericalFailure, |r| a7_status(r, mdot_kg_s));
    let (sp, sc) = (st(p), st(c));
    let c_status = sp.class() == sc.class();
    let both_eval = sp.is_evaluated_physics() && sc.is_evaluated_physics();
    let c_quiet = both_eval.then(|| match (p.and_then(quiet), c.and_then(quiet)) {
        (Some(a), Some(b)) => a == b,
        _ => false,
    });
    let (mut thrust, mut current) = (None, None);
    if sp == A7Status::Pass && sc == A7Status::Pass {
        if let (Some(p), Some(c)) = (p, c) {
            thrust = match (thrust_obs(p), thrust_obs(c)) {
                (Some(a), Some(b)) => Some(agree(&a, &b)),
                _ => Some((f64::NAN, f64::NAN, false)),
            };
            current = match (current_obs(p), current_obs(c)) {
                (Some(a), Some(b)) => Some(agree(&a, &b)),
                _ => Some((f64::NAN, f64::NAN, false)),
            };
        }
    }
    A7Comparison { status_p: sp, status_c: sc, c_status, c_quiet, thrust, current }
}

fn schema(path: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.into(), message: m.into() }
}

fn model(m: impl Into<String>) -> AbepError {
    AbepError::Model { message: m.into() }
}

fn get_str<'a>(v: &'a Value, k: &str, label: &str) -> AbepResult<&'a str> {
    get(v, k).and_then(Value::as_str).ok_or_else(|| schema(label, format!("{k} missing or not a string")))
}

fn loads(bytes: &[u8], label: &str) -> AbepResult<Value> {
    let text = std::str::from_utf8(bytes).map_err(|e| schema(label, e.to_string()))?;
    pyjson::loads(text).map_err(|e| schema(label, e.to_string()))
}

/// One A7 grid stage: the case file (pinned by its launch manifest) and the stage's v1 key selection.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GridStage {
    /// All G-RP1 cases of the registered v1 XE grid (A9.37 DBF-1 geometry).
    Stage1,
    /// The other XE cases of the registered grid.
    Stage2,
}

impl GridStage {
    pub fn as_str(self) -> &'static str {
        match self {
            GridStage::Stage1 => "STAGE_1_G_RP1",
            GridStage::Stage2 => "STAGE_2_REST",
        }
    }

    pub fn cases_rel(self) -> &'static str {
        match self {
            GridStage::Stage1 => "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a7_xe_grid_stage1_v1.json",
            GridStage::Stage2 => "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a7_xe_grid_stage2_v1.json",
        }
    }

    pub fn launch_rel(self) -> &'static str {
        match self {
            GridStage::Stage1 => {
                "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_a7_xe_grid_stage1_v1.json"
            }
            GridStage::Stage2 => {
                "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_a7_xe_grid_stage2_v1.json"
            }
        }
    }

    pub fn kind(self) -> &'static str {
        match self {
            GridStage::Stage1 => "XE_GRID_STAGE_1",
            GridStage::Stage2 => "XE_GRID_STAGE_2",
        }
    }

    /// Whether a v1 XE case belongs to the stage.
    pub fn contains(self, c: &CaseInfo) -> bool {
        (c.geometry_id == "G-RP1") == (self == GridStage::Stage1)
    }
}

/// An ingested A7 point: the envelope point (status mapped by [`A7Status::envelope_status`]) and its A7 status.
#[derive(Debug, Clone, PartialEq)]
pub struct A7Point {
    pub point: EnvelopePoint,
    pub a7_status: A7Status,
    pub thrust_se_n: Option<f64>,
    pub current_se_a: Option<f64>,
}

/// Ingest frozen A7 grid stages (each a sha-pinned raw manifest under the A7 lock). Every record is
/// checked against its stage case file (pinned by the launch manifest), the HallThruster.jl pin and the A7 and v1
/// locks; each supplied stage must be complete. The returned envelope holds the supplied stages only (Stage 1 alone is
/// the G-RP1 hardware family); each point carries the v1 case identity and the A7 status.
pub fn ingest_a7(repo: &Path, stages: &[(GridStage, &Path, &str)]) -> AbepResult<A7Ingested> {
    let lock_sha256 = LOCK_SHA256;
    if stages.is_empty() {
        return Err(model("no A7 grid stage supplied"));
    }
    read_verified(&repo.join(LOCK_REL), lock_sha256)?;
    let v1 = load_case_set(repo)?;
    let v1_by = v1.by_key();
    let commit = pinned_commit(&repo.to_string_lossy(), None).map_err(AbepError::from)?;
    let mut pts: BTreeMap<String, A7Point> = BTreeMap::new();
    let (mut msha, mut rsha, mut csha) = (Vec::new(), Vec::new(), Vec::new());
    let mut demo_shas: Vec<String> = Vec::new();
    let mut overlay = crate::envelope::A3Overlay::Adequate;
    for (stage, manifest, manifest_sha256) in stages {
        if stages.iter().filter(|(s, _, _)| s == stage).count() != 1 {
            return Err(model(format!("A7 stage {} supplied more than once", stage.as_str())));
        }
        let label = manifest.to_string_lossy().to_string();
        let m = loads(&read_verified(manifest, manifest_sha256)?, &label)?;
        if get_str(&m, "schema", &label)? != RAW_SCHEMA
            || get_str(&m, "addendum_lock_sha256", &label)? != lock_sha256
            || get_str(&m, "kind", &label)? != stage.kind()
        {
            return Err(schema(&label, format!("not a frozen A7 {} under the A7 lock", stage.as_str())));
        }
        let lr = stage.launch_rel();
        let lm = loads(&std::fs::read(repo.join(lr)).map_err(|e| schema(lr, e.to_string()))?, lr)?;
        let cases_sha = get_str(&lm, "cases_sha256", lr)?.to_string();
        if get_str(&m, "cases_file_sha256", &label)? != cases_sha {
            return Err(schema(&label, "frozen from another A7 case file"));
        }
        let cr = stage.cases_rel();
        let doc = loads(&read_verified(&repo.join(cr), &cases_sha)?, cr)?;
        if get_str(&doc, "demonstration_result", cr)? != gating_result_rel(*stage) {
            return Err(schema(cr, "stage case file not gated by its registered demonstration result"));
        }
        let ds = get_str(&doc, "demonstration_result_sha256", cr)?.to_string();
        overlay = demonstration_overlay(repo, gating_result_rel(*stage), &ds)?;
        demo_shas.push(ds);
        let mut want: BTreeMap<String, (String, &CaseInfo)> = BTreeMap::new();
        for c in get(&doc, "cases").and_then(Value::as_list).ok_or_else(|| schema(cr, "cases"))? {
            let h = case_hash(c)?;
            if get_str(c, "case_sha256", cr)? != h {
                return Err(schema(cr, "case_sha256 mismatch"));
            }
            let v1_key = get_str(c, "v1_key", cr)?;
            let ci = v1_by.get(v1_key).ok_or_else(|| model(format!("A7 case without a v1 case {v1_key}")))?;
            if ci.family != Family::Xe || !stage.contains(ci) || get_str(c, "v1_case_sha256", cr)? != ci.case_sha256 {
                return Err(model(format!("A7 case {v1_key} does not derive from a frozen v1 XE case of its stage")));
            }
            want.insert(get_str(c, "key", cr)?.to_string(), (h, ci));
        }
        let n_stage = v1.cases.iter().filter(|c| c.family == Family::Xe && stage.contains(c)).count();
        if want.len() != n_stage {
            return Err(model(format!("A7 {} case file has {} of {n_stage} cases", stage.as_str(), want.len())));
        }
        let raw_name = get_str(&m, "raw_file", &label)?;
        let raw_sha = get_str(&m, "raw_sha256", &label)?.to_string();
        let gz = read_verified(&manifest.parent().unwrap_or(Path::new(".")).join(raw_name), &raw_sha)?;
        let mut text = String::new();
        flate2::read::GzDecoder::new(gz.as_slice())
            .read_to_string(&mut text)
            .map_err(|e| schema(raw_name, format!("gzip: {e}")))?;
        let mut n = 0usize;
        for line in text.lines().filter(|l| !l.trim().is_empty()) {
            let rec = pyjson::loads(line).map_err(|e| schema(raw_name, e.to_string()))?;
            let key = get_str(&rec, "key", raw_name)?.to_string();
            let (h, ci) = want.get(&key).ok_or_else(|| model(format!("unexpected A7 record {key}")))?;
            for (field, w) in [
                ("case_sha256", h.as_str()),
                ("hallthruster_commit", commit.as_str()),
                ("addendum_lock_sha256", lock_sha256),
                ("prereg_lock_sha256", V1_LOCK_SHA256),
                ("cases_file_sha256", cases_sha.as_str()),
                ("family", "XE"),
            ] {
                if get(&rec, field).and_then(Value::as_str) != Some(w) {
                    return Err(model(format!("A7 record {key}: {field} != {w}")));
                }
            }
            let st = a7_status(&rec, ci.mdot_kg_s);
            let pass = st == A7Status::Pass;
            let pick = |k: &str| if pass { num(&rec, k) } else { None };
            let point = EnvelopePoint {
                case: (*ci).clone(),
                status: st.envelope_status(),
                thrust_n: pick("thrust_N"),
                discharge_power_w: pick("discharge_power_W"),
                discharge_current_a: pick("discharge_current_A"),
                ion_current_a: pick("ion_current_A"),
                te_max_ev: pick("Te_max_eV"),
            };
            let a7p = A7Point {
                point,
                a7_status: st,
                thrust_se_n: pick("thrust_se_N"),
                current_se_a: pick("discharge_current_se_A"),
            };
            if pts.insert(ci.key.clone(), a7p).is_some() {
                return Err(model(format!("duplicate A7 record {key}")));
            }
            n += 1;
        }
        if n != want.len() {
            return Err(model(format!("{} of {} A7 {} records missing", want.len() - n, want.len(), stage.as_str())));
        }
        if num(&m, "n_records") != Some(n as f64) {
            return Err(schema(&label, "n_records != records"));
        }
        msha.push(manifest_sha256.to_string());
        rsha.push(raw_sha);
        csha.push(cases_sha);
    }
    let a7: Vec<A7Point> = pts.into_values().collect();
    let points = a7.iter().map(|p| p.point.clone()).collect();
    let env = Envelope {
        manifest_rel: stages.iter().map(|(_, m, _)| m.to_string_lossy().to_string()).collect::<Vec<_>>().join(" + "),
        manifest_sha256: msha.join("+"),
        raw_sha256: rsha.join("+"),
        cases_sha256: csha.join("+"),
        bz_family_kind: v1.bz_family_kind,
        points,
    };
    Ok(A7Ingested { envelope: env, points: a7, overlay, demonstration_result_sha256: demo_shas.join("+") })
}

/// The RP-1 demonstration result (gates Stage 1) and the full demonstration result (gates Stage 2).
pub const DEMO_RP1_RESULT_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/a7_demonstration_rp1_result_v1.json";
pub const DEMO_RESULT_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/a7_demonstration_result_v1.json";
pub const DEMO_RESULT_SCHEMA: &str = "np_hall_parametric_envelope_a7_demonstration_result_v1";
pub const OUTCOME_DEMONSTRATED: &str = "A7_CONVERGED_SUBSET_DEMONSTRATED";
pub const OUTCOME_NOT_DEMONSTRATED: &str = "A7_STOP_NOT_DEMONSTRATED";

/// The demonstration result that gates a grid stage (Stage 1: the RP-1 result; Stage 2: the full result).
pub fn gating_result_rel(stage: GridStage) -> &'static str {
    match stage {
        GridStage::Stage1 => DEMO_RP1_RESULT_REL,
        GridStage::Stage2 => DEMO_RESULT_REL,
    }
}

/// The overlay an A7 grid point carries, from the committed demonstration result `rel` (sha-pinned by the caller):
/// Adequate when the converged subset was demonstrated; refused otherwise (an A7 grid is never run or ingested after a
/// STOP).
pub fn demonstration_overlay(repo: &Path, rel: &str, result_sha256: &str) -> AbepResult<crate::envelope::A3Overlay> {
    let v = loads(&read_verified(&repo.join(rel), result_sha256)?, rel)?;
    if get_str(&v, "schema", rel)? != DEMO_RESULT_SCHEMA || get_str(&v, "addendum_lock_sha256", rel)? != LOCK_SHA256 {
        return Err(schema(rel, "not an A7 demonstration result under the A7 lock"));
    }
    match get_str(&v, "outcome", rel)? {
        OUTCOME_DEMONSTRATED => Ok(crate::envelope::A3Overlay::Adequate),
        o => Err(model(format!("A7 demonstration outcome {o}: no A7 envelope is admitted to the closure"))),
    }
}

/// An ingested A7 envelope: the envelope (supplied stages), the A7 points, and the overlay of the committed
/// demonstration result the stage case files were generated from.
#[derive(Debug, Clone, PartialEq)]
pub struct A7Ingested {
    pub envelope: Envelope,
    pub points: Vec<A7Point>,
    pub overlay: crate::envelope::A3Overlay,
    pub demonstration_result_sha256: String,
}

/// The bz family kind of the v1 case set (an A7 envelope inherits it).
pub fn bz_family_kind(repo: &Path) -> AbepResult<BzFamilyKind> {
    Ok(load_case_set(repo)?.bz_family_kind)
}

#[cfg(test)]
mod tests {
    use super::*;
    use abep_types::pyjson::Dict;

    fn rec(t: (f64, f64, f64, f64), i: (f64, f64, f64, f64), rms: f64, sustained: bool) -> Value {
        let mut d = Dict::new();
        d.insert("retcode", Value::str("success"));
        d.insert("converged", Value::Bool(true));
        d.insert("finite", Value::Bool(true));
        d.insert("sustained", Value::Bool(sustained));
        d.insert("thrust_N", Value::Float(t.0));
        d.insert("thrust_se_N", Value::Float(t.1));
        d.insert("thrust_half_means_N", Value::List(vec![Value::Float(t.2), Value::Float(t.3)]));
        d.insert("discharge_current_A", Value::Float(i.0));
        d.insert("discharge_current_se_A", Value::Float(i.1));
        d.insert("discharge_current_half_means_A", Value::List(vec![Value::Float(i.2), Value::Float(i.3)]));
        d.insert("discharge_power_W", Value::Float(i.0 * 300.0));
        d.insert("Id_rms_rel", Value::Float(rms));
        Value::Dict(d)
    }

    const MDOT: f64 = 1.287e-6;

    #[test]
    fn status_precedence() {
        let ok = rec((0.05, 1e-5, 0.05, 0.05), (3.0, 1e-3, 3.0, 3.0), 0.01, true);
        assert_eq!(a7_status(&ok, MDOT), A7Status::Pass);
        let ext = rec((1e-14, 0.0, 1e-14, 1e-14), (1e-16, 0.0, 1e-16, 1e-16), 0.1, true);
        assert_eq!(a7_status(&ext, MDOT), A7Status::Extinct);
        let ns = rec((0.05, 1e-5, 0.05, 0.05), (3.0, 1e-3, 3.0, 3.0), 0.9, false);
        assert_eq!(a7_status(&ns, MDOT), A7Status::NotSustained);
        let drift = rec((0.05, 1e-4, 0.045, 0.055), (3.0, 1e-3, 3.0, 3.0), 0.3, true);
        assert_eq!(a7_status(&drift, MDOT), A7Status::NonStationary);
        let noisy = rec((0.05, 2e-3, 0.05, 0.05), (3.0, 1e-3, 3.0, 3.0), 0.6, true);
        assert_eq!(a7_status(&noisy, MDOT), A7Status::StatisticallyUnresolved);
        let mut bad = ok.clone();
        if let Value::Dict(d) = &mut bad {
            d.insert("retcode", Value::str("failure"));
        }
        assert_eq!(a7_status(&bad, MDOT), A7Status::NumericalFailure);
        assert!(A7Status::NotSustained.is_evaluated_physics());
        assert_eq!(A7Status::NonStationary.envelope_status(), RunStatus::NumericalFailure);
    }

    #[test]
    fn agreement_allowance() {
        let a = Obs { mean: 1.0, se: 0.0, half: (1.0, 1.0) };
        let b = Obs { mean: 1.019, se: 0.0, half: (1.019, 1.019) };
        assert!(agree(&a, &b).2);
        let c = Obs { mean: 1.03, se: 0.0, half: (1.03, 1.03) };
        assert!(!agree(&a, &c).2);
        let d = Obs { mean: 1.0, se: 0.005, half: (1.0, 1.0) };
        let e = Obs { mean: 1.03, se: 0.005, half: (1.03, 1.03) };
        // allowance 0.02 * 1.03 + 2 * sqrt(2) * 0.005 = 0.0347 >= 0.03
        assert!(agree(&d, &e).2);
    }

    #[test]
    fn comparison_outcomes() {
        let p = rec((0.050, 1e-5, 0.05, 0.05), (3.00, 1e-3, 3.0, 3.0), 0.01, true);
        let c = rec((0.0505, 1e-5, 0.0505, 0.0505), (3.03, 1e-3, 3.03, 3.03), 0.01, true);
        assert_eq!(compare(Some(&p), Some(&c), MDOT).outcome(), CaseOutcome::ConvergedEvaluated);
        assert_eq!(compare(None, None, MDOT).outcome(), CaseOutcome::PersistentUnknown);
        assert_eq!(compare(Some(&p), None, MDOT).outcome(), CaseOutcome::NotConverged);
        let far = rec((0.06, 1e-5, 0.06, 0.06), (3.0, 1e-3, 3.0, 3.0), 0.01, true);
        assert_eq!(compare(Some(&p), Some(&far), MDOT).outcome(), CaseOutcome::NotConverged);
        let loud = rec((0.0505, 1e-5, 0.0505, 0.0505), (3.03, 1e-3, 3.03, 3.03), 0.7, true);
        assert_eq!(compare(Some(&p), Some(&loud), MDOT).outcome(), CaseOutcome::NotConverged);
    }
}
