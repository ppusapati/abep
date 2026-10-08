//! NP-HALL-PARAMETRIC-ENVELOPE v1 (A9.32): the frozen case set and the ingestion of the frozen raw HallThruster.jl
//! envelope of H-1 (`docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_v1.json`, locked in
//! `prereg_lock_v1.json`).
//!
//! Everything here is PARAMETRIC / NOT_VALIDATED. It is never a Hall map: nothing in this module touches HallMap, the
//! ensemble members, admission or the HallGate, and no point read here can enter the evidence-qualified layer (b).
//! The run-status rule is the preregistered one (NUMERICAL_FAILURE > OUT_OF_DOMAIN > NOT_SUSTAINED > PASS); thresholds
//! and verdicts belong to assessment (abep-assess::closure), not to this module.

use crate::hall_map::pinned_commit;
use abep_provenance::{read_verified, sha256_hex};
use abep_types::pyjson::{self, DumpOptions, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;
use std::path::Path;

pub const NP_DIR: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE";
pub const PREREG_REL: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_v1.json";
pub const PREREG_SHA256: &str = "3275f85752fae258e4e4124cbe43d8756e8dfede70f560f8b2e7d66a40164b4d";
pub const LOCK_REL: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_lock_v1.json";
pub const LOCK_SHA256: &str = "25ecfa880e9d115800821bcb2dfe5bab333323b214c3668a6fb8a9a54d53ebd3";
pub const CASES_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_cases_v1.json";
pub const LAUNCH_MANIFEST_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_v1.json";
pub const DRIVER_REL: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_driver.jl";
pub const CASES_SCHEMA: &str = "np_hall_parametric_envelope_cases_v1";
pub const LAUNCH_SCHEMA: &str = "np_hall_parametric_envelope_launch_manifest_v1";
pub const RAW_MANIFEST_SCHEMA: &str = "np_hall_parametric_envelope_raw_manifest_v1";

/// Label carried by every layer (a) field.
pub const LAYER_A_LABEL: &str = "PARAMETRIC / NOT_VALIDATED";
pub const BZ_SURROGATE_LABEL: &str = "SOURCED_SURROGATE_P5_SHAPE_NOT_H1_BZ";
pub const TRANSPORT_EXTRAPOLATED: &str = "TRANSPORT_EXTRAPOLATED";
pub const NUMERICS_NOT_VERIFIED: &str = "NUMERICAL_ADEQUACY_NOT_VERIFIED_FOR_H1";
pub const GEOMETRY_LABEL: &str = "ANALYSIS_POINT_NOT_DESIGN_SELECTION";
pub const XE_NO_MANIFEST: &str = "XE_CHEMISTRY_NO_VALIDITY_MANIFEST";
pub const XE_FLOW_LABEL: &str = "XE_FLOW_FROM_H1_ATM_RANGE";
pub const N2_PROXY_LABEL: &str = "N2_PROXY";
/// The f_out rule of p5_n2_run_status_rule_v1 (never relaxed).
pub const F_OUT_TOL: f64 = 1e-12;

fn schema(path: &str, message: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.to_string(), message: message.into() }
}

fn model(message: impl Into<String>) -> AbepError {
    AbepError::Model { message: message.into() }
}

fn py_err(path: &str, e: pyjson::PyException) -> AbepError {
    schema(path, format!("{e:?}"))
}

/// Envelope family (prereg `families`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Family {
    Xe,
    N2Proxy,
}

impl Family {
    pub const ALL: [Family; 2] = [Family::Xe, Family::N2Proxy];

    pub fn as_str(self) -> &'static str {
        match self {
            Family::Xe => "XE",
            Family::N2Proxy => "N2_PROXY",
        }
    }

    pub fn parse(s: &str) -> Option<Family> {
        Family::ALL.into_iter().find(|f| f.as_str() == s)
    }

    /// Family labels carried by every point (prereg envelope_output_schema.labels).
    pub fn labels(self) -> Vec<&'static str> {
        let mut v =
            vec![LAYER_A_LABEL, BZ_SURROGATE_LABEL, TRANSPORT_EXTRAPOLATED, NUMERICS_NOT_VERIFIED, GEOMETRY_LABEL];
        match self {
            Family::Xe => v.extend([XE_NO_MANIFEST, XE_FLOW_LABEL]),
            Family::N2Proxy => v.push(N2_PROXY_LABEL),
        }
        v
    }
}

/// Kind of the B(z) family of an envelope (prereg bz_family.kind). v1 is a sourced surrogate.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BzFamilyKind {
    SourcedSurrogate,
    H1Registered,
}

impl BzFamilyKind {
    pub fn as_str(self) -> &'static str {
        match self {
            BzFamilyKind::SourcedSurrogate => "SOURCED_SURROGATE",
            BzFamilyKind::H1Registered => "H1_REGISTERED",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        [BzFamilyKind::SourcedSurrogate, BzFamilyKind::H1Registered].into_iter().find(|k| k.as_str() == s)
    }
}

/// Preregistered run status, in precedence order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum RunStatus {
    NumericalFailure,
    OutOfDomain,
    NotSustained,
    Pass,
}

impl RunStatus {
    pub const ALL: [RunStatus; 4] =
        [RunStatus::NumericalFailure, RunStatus::OutOfDomain, RunStatus::NotSustained, RunStatus::Pass];

    pub fn as_str(self) -> &'static str {
        match self {
            RunStatus::NumericalFailure => "NUMERICAL_FAILURE",
            RunStatus::OutOfDomain => "OUT_OF_DOMAIN",
            RunStatus::NotSustained => "NOT_SUSTAINED",
            RunStatus::Pass => "PASS",
        }
    }

    /// PASS and NOT_SUSTAINED are evaluated physics; OUT_OF_DOMAIN and NUMERICAL_FAILURE are unknowns.
    pub fn is_evaluated_physics(self) -> bool {
        matches!(self, RunStatus::Pass | RunStatus::NotSustained)
    }
}

/// sha256 of `json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`.
pub fn canonical_sha256(v: &Value) -> AbepResult<String> {
    let text = pyjson::dumps(v, &DumpOptions::canonical_hash()).map_err(|e| model(format!("{e:?}")))?;
    Ok(sha256_hex(text.as_bytes()))
}

/// The preregistered case hash: the canonical sha256 of the case without its `case_sha256` field.
pub fn case_hash(case: &Value) -> AbepResult<String> {
    let Value::Dict(d) = case else { return Err(model("a case is not an object")) };
    let mut d = d.clone();
    d.remove("case_sha256");
    canonical_sha256(&Value::Dict(d))
}

fn get<'a>(v: &'a Value, k: &str) -> Option<&'a Value> {
    v.as_dict().and_then(|d| d.get(k))
}

fn get_str<'a>(v: &'a Value, k: &str, path: &str) -> AbepResult<&'a str> {
    get(v, k).and_then(Value::as_str).ok_or_else(|| schema(path, format!("field {k} missing or not a string")))
}

fn get_f64(v: &Value, k: &str, path: &str) -> AbepResult<f64> {
    match get(v, k) {
        Some(x @ (Value::Int(_) | Value::Float(_))) => x.to_f64().map_err(|e| py_err(path, e)),
        _ => Err(schema(path, format!("field {k} missing or not a number"))),
    }
}

/// One case of the frozen case file (the identity and the axis values; the solver inputs stay in the file).
#[derive(Debug, Clone, PartialEq)]
pub struct CaseInfo {
    pub key: String,
    pub family: Family,
    pub geometry_id: String,
    pub bz_shape_id: String,
    pub b_peak_id: String,
    pub vd_id: String,
    pub mdot_id: String,
    pub transport_id: String,
    pub vd_v: f64,
    pub mdot_kg_s: f64,
    pub b_peak_t: f64,
    pub case_sha256: String,
}

impl CaseInfo {
    /// Hardware configuration (geometry, B shape): the operating variables are B_peak, V_d and mdot.
    pub fn hardware(&self) -> (String, String) {
        (self.geometry_id.clone(), self.bz_shape_id.clone())
    }
}

/// The frozen case set.
#[derive(Debug, Clone, PartialEq)]
pub struct CaseSet {
    pub sha256: String,
    pub bz_family_kind: BzFamilyKind,
    pub cases: Vec<CaseInfo>,
}

impl CaseSet {
    pub fn keys(&self) -> BTreeSet<String> {
        self.cases.iter().map(|c| c.key.clone()).collect()
    }

    pub fn by_key(&self) -> BTreeMap<&str, &CaseInfo> {
        self.cases.iter().map(|c| (c.key.as_str(), c)).collect()
    }
}

/// Parse and verify a case-file document: schema, preregistration lock, every case hash, unique keys.
pub fn parse_case_set(doc: &Value, sha256: &str) -> AbepResult<CaseSet> {
    let p = CASES_REL;
    if get_str(doc, "schema", p)? != CASES_SCHEMA {
        return Err(schema(p, "not a v1 envelope case file"));
    }
    if get_str(doc, "prereg_lock_sha256", p)? != LOCK_SHA256 {
        return Err(schema(p, "case file was generated under another preregistration lock"));
    }
    let kind =
        BzFamilyKind::parse(get_str(doc, "bz_family_kind", p)?).ok_or_else(|| schema(p, "unknown bz_family_kind"))?;
    let list = get(doc, "cases").and_then(Value::as_list).ok_or_else(|| schema(p, "cases missing"))?;
    let mut cases = Vec::with_capacity(list.len());
    let mut seen = BTreeSet::new();
    for c in list {
        let key = get_str(c, "key", p)?.to_string();
        let recorded = get_str(c, "case_sha256", p)?;
        let h = case_hash(c)?;
        if h != recorded {
            return Err(schema(p, format!("case {key}: case_sha256 {recorded} != recomputed {h}")));
        }
        if !seen.insert(key.clone()) {
            return Err(schema(p, format!("duplicate case key {key}")));
        }
        let family = Family::parse(get_str(c, "family", p)?).ok_or_else(|| schema(p, "unknown family"))?;
        cases.push(CaseInfo {
            family,
            geometry_id: get_str(c, "geometry_id", p)?.into(),
            bz_shape_id: get_str(c, "bz_shape_id", p)?.into(),
            b_peak_id: get_str(c, "B_peak_id", p)?.into(),
            vd_id: get_str(c, "Vd_id", p)?.into(),
            mdot_id: get_str(c, "mdot_id", p)?.into(),
            transport_id: get_str(c, "transport_id", p)?.into(),
            vd_v: get_f64(c, "Vd", p)?,
            mdot_kg_s: get_f64(c, "mdot_kgps", p)?,
            b_peak_t: get_f64(c, "B_ref_T", p)?,
            case_sha256: h,
            key,
        });
    }
    Ok(CaseSet { sha256: sha256.to_string(), bz_family_kind: kind, cases })
}

/// The committed case file of the repository (verified against the launch manifest's pin).
pub fn load_case_set(repo: &Path) -> AbepResult<CaseSet> {
    let lm = load_json(&repo.join(LAUNCH_MANIFEST_REL), LAUNCH_MANIFEST_REL)?;
    let pinned = get_str(&lm, "cases_sha256", LAUNCH_MANIFEST_REL)?;
    let bytes = read_verified(&repo.join(CASES_REL), pinned)?;
    let doc = loads_bytes(&bytes, CASES_REL)?;
    parse_case_set(&doc, pinned)
}

fn loads_bytes(bytes: &[u8], path: &str) -> AbepResult<Value> {
    let text = std::str::from_utf8(bytes).map_err(|e| schema(path, e.to_string()))?;
    pyjson::loads(text).map_err(|e| py_err(path, e))
}

fn load_json(p: &Path, label: &str) -> AbepResult<Value> {
    let bytes = std::fs::read(p).map_err(|e| AbepError::Io { path: label.into(), message: e.to_string() })?;
    loads_bytes(&bytes, label)
}

fn finite_num(v: Option<&Value>) -> Option<f64> {
    match v {
        Some(x @ (Value::Int(_) | Value::Float(_))) => x.to_f64().ok().filter(|f| f.is_finite()),
        _ => None,
    }
}

fn is_true(v: Option<&Value>) -> bool {
    matches!(v, Some(Value::Bool(true)))
}

/// The preregistered run status of one raw record (prereg run_status_rule), applied in precedence order.
pub fn run_status(family: Family, rec: &Value) -> RunStatus {
    let numeric_ok = get(rec, "retcode").and_then(Value::as_str) == Some("success")
        && is_true(get(rec, "converged"))
        && is_true(get(rec, "finite"))
        && ["thrust_N", "discharge_current_A", "discharge_power_W"].iter().all(|k| finite_num(get(rec, k)).is_some());
    if !numeric_ok {
        return RunStatus::NumericalFailure;
    }
    if family == Family::N2Proxy && !n2_chemistry_in_domain(rec) {
        return RunStatus::OutOfDomain;
    }
    if !is_true(get(rec, "sustained")) {
        return RunStatus::NotSustained;
    }
    RunStatus::Pass
}

/// f_out rule: no unresolved table and every reaction's extrapolated fraction present and <= 1e-12.
fn n2_chemistry_in_domain(rec: &Value) -> bool {
    let unresolved = match get(rec, "chemistry_unresolved_rate_files") {
        Some(Value::List(l)) => l.is_empty(),
        _ => false,
    };
    let per = match get(rec, "chemistry_per_reaction") {
        Some(Value::List(l)) if !l.is_empty() => l,
        _ => return false,
    };
    unresolved && per.iter().all(|r| finite_num(get(r, "extrapolated_fraction")).is_some_and(|f| f <= F_OUT_TOL))
}

/// One ingested envelope point (raw observables of PASS points only; others carry their status).
#[derive(Debug, Clone, PartialEq)]
pub struct EnvelopePoint {
    pub case: CaseInfo,
    pub status: RunStatus,
    pub thrust_n: Option<f64>,
    pub discharge_power_w: Option<f64>,
    pub discharge_current_a: Option<f64>,
    /// Time-averaged ion (beam) current of a PASS point (raw `ion_current_A`); read by the closure's P-CPL path.
    pub ion_current_a: Option<f64>,
    pub te_max_ev: Option<f64>,
}

/// Values every raw record must carry exactly.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecordPins {
    pub hallthruster_commit: String,
    pub prereg_lock_sha256: String,
    pub cases_file_sha256: String,
}

/// Check a record list against the frozen case set and pins (each family complete or absent); any defect refuses the
/// whole envelope.
pub fn ingest_records(cases: &CaseSet, records: &[Value], pins: &RecordPins) -> AbepResult<Vec<EnvelopePoint>> {
    let by_key = cases.by_key();
    let mut got: BTreeMap<String, EnvelopePoint> = BTreeMap::new();
    for rec in records {
        let key = get(rec, "key").and_then(Value::as_str).ok_or_else(|| model("raw record without key"))?;
        let case = by_key.get(key).ok_or_else(|| model(format!("unexpected raw record key {key}")))?;
        for (field, want) in [
            ("case_sha256", case.case_sha256.as_str()),
            ("hallthruster_commit", pins.hallthruster_commit.as_str()),
            ("prereg_lock_sha256", pins.prereg_lock_sha256.as_str()),
            ("cases_file_sha256", pins.cases_file_sha256.as_str()),
            ("family", case.family.as_str()),
        ] {
            let have = get(rec, field).and_then(Value::as_str);
            if have != Some(want) {
                return Err(model(format!("record {key}: {field} {have:?} != frozen {want}")));
            }
        }
        let status = run_status(case.family, rec);
        let pass = status == RunStatus::Pass;
        let pick = |k: &str| if pass { finite_num(get(rec, k)) } else { None };
        let point = EnvelopePoint {
            case: (*case).clone(),
            status,
            thrust_n: pick("thrust_N"),
            discharge_power_w: pick("discharge_power_W"),
            discharge_current_a: pick("discharge_current_A"),
            ion_current_a: pick("ion_current_A"),
            te_max_ev: pick("Te_max_eV"),
        };
        if got.insert(key.to_string(), point).is_some() {
            return Err(model(format!("duplicate raw record key {key}")));
        }
    }
    // A family is run completely or not at all (a family-filtered run, launch manifest `--family`): every key of a
    // family with at least one record is expected; a family without records is absent (its Hall tests are
    // NOT_EVALUATED, HALL_ENVELOPE_NOT_RUN). A partial family is MODEL_ERROR.
    let present: BTreeSet<Family> = got.values().map(|p| p.case.family).collect();
    if present.is_empty() {
        return Err(model("raw envelope without records"));
    }
    let missing: Vec<&str> = cases
        .cases
        .iter()
        .filter(|c| present.contains(&c.family) && !got.contains_key(&c.key))
        .map(|c| c.key.as_str())
        .collect();
    if !missing.is_empty() {
        return Err(model(format!("{} expected records missing (first {})", missing.len(), missing[0])));
    }
    Ok(cases
        .cases
        .iter()
        .filter(|c| present.contains(&c.family))
        .map(|c| got.remove(&c.key).expect("present"))
        .collect())
}

/// Committed result of addendum A3 (numerics adequacy, RG-04) for the XE family.
pub const A3_RESULT_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/a3_numerics_result_v1.json";
pub const A3_RESULT_SCHEMA: &str = "np_hall_parametric_envelope_a3_numerics_result_v1";
pub const A3_LOCK_SHA256: &str = "b840f1b080c94be58472ccb07f6cf35cc9ad8822161ff9a1440ecb55c76e04bd";
/// Label / blocker of a point whose numerics the A3 check did not support (never feasible, never a non-closure).
pub const NUMERICS_NOT_CONVERGED: &str = "NUMERICS_NOT_CONVERGED";

/// The A3 overlay of a family (addendum A3 consequence). Raw records and v1 run statuses are never changed.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum A3Overlay {
    /// No committed A3 result: the v1 rules apply unchanged.
    NotRun,
    /// A3_ADEQUATE: the v1 numerics stand.
    Adequate,
    /// A3_ADEQUATE_WITH_NUMERICAL_MARGIN: point tests evaluated at T (1 - delta_t) and P_d (1 + delta_i).
    Margin { delta_t: f64, delta_i: f64 },
    /// A3_NOT_ADEQUATE: every PASS and NOT_SUSTAINED point is NUMERICS_NOT_CONVERGED (an unknown).
    NotAdequate,
}

impl A3Overlay {
    pub fn as_str(self) -> &'static str {
        match self {
            A3Overlay::NotRun => "A3_NOT_RUN",
            A3Overlay::Adequate => "A3_ADEQUATE",
            A3Overlay::Margin { .. } => "A3_ADEQUATE_WITH_NUMERICAL_MARGIN",
            A3Overlay::NotAdequate => "A3_NOT_ADEQUATE",
        }
    }

    /// Is a point of this status evaluated physics under the overlay?
    pub fn evaluated_physics(self, s: RunStatus) -> bool {
        s.is_evaluated_physics() && self != A3Overlay::NotAdequate
    }
}

/// The committed A3 overlay of `family` and the sha256 of the result it was read from (fail closed: a result file that
/// exists but does not parse, carries another lock or an unknown outcome is an error).
pub fn a3_overlay(repo: &Path, family: Family) -> AbepResult<(A3Overlay, Option<String>)> {
    let p = repo.join(A3_RESULT_REL);
    if family != Family::Xe || !p.is_file() {
        return Ok((A3Overlay::NotRun, None));
    }
    let bytes = std::fs::read(&p).map_err(|e| AbepError::Io { path: A3_RESULT_REL.into(), message: e.to_string() })?;
    let sha = sha256_hex(&bytes);
    let v = loads_bytes(&bytes, A3_RESULT_REL)?;
    if get_str(&v, "schema", A3_RESULT_REL)? != A3_RESULT_SCHEMA
        || get_str(&v, "addendum_lock_sha256", A3_RESULT_REL)? != A3_LOCK_SHA256
        || get_str(&v, "family", A3_RESULT_REL)? != family.as_str()
    {
        return Err(schema(A3_RESULT_REL, "not an A3 result of this family under the A3 lock"));
    }
    let delta = |k: &str| get(&v, k).and_then(|d| finite_num(get(d, "value")));
    let o = match get_str(&v, "outcome", A3_RESULT_REL)? {
        "A3_ADEQUATE" => A3Overlay::Adequate,
        "A3_ADEQUATE_WITH_NUMERICAL_MARGIN" => A3Overlay::Margin {
            delta_t: delta("delta_T").ok_or_else(|| schema(A3_RESULT_REL, "delta_T"))?,
            delta_i: delta("delta_I").ok_or_else(|| schema(A3_RESULT_REL, "delta_I"))?,
        },
        "A3_NOT_ADEQUATE" => A3Overlay::NotAdequate,
        other => return Err(schema(A3_RESULT_REL, format!("unknown A3 outcome {other}"))),
    };
    Ok((o, Some(sha)))
}

/// An ingested, frozen envelope.
#[derive(Debug, Clone, PartialEq)]
pub struct Envelope {
    pub manifest_rel: String,
    pub manifest_sha256: String,
    pub raw_sha256: String,
    pub cases_sha256: String,
    pub bz_family_kind: BzFamilyKind,
    pub points: Vec<EnvelopePoint>,
}

impl Envelope {
    pub fn family_points(&self, f: Family) -> impl Iterator<Item = &EnvelopePoint> {
        self.points.iter().filter(move |p| p.case.family == f)
    }

    /// Run-status counts of a family, in precedence order.
    pub fn status_counts(&self, f: Family) -> Vec<(RunStatus, usize)> {
        RunStatus::ALL.iter().map(|s| (*s, self.family_points(f).filter(|p| p.status == *s).count())).collect()
    }
}

/// Ingest the frozen raw envelope whose manifest is `manifest` (sha256 `manifest_sha256`): manifest pin, raw file
/// pin, gzip JSONL, every record checked against the committed case set, the pin and the preregistration lock.
pub fn ingest(repo: &Path, manifest: &Path, manifest_sha256: &str) -> AbepResult<Envelope> {
    let label = manifest.to_string_lossy().to_string();
    let mbytes = read_verified(manifest, manifest_sha256)?;
    let m = loads_bytes(&mbytes, &label)?;
    if get_str(&m, "schema", &label)? != RAW_MANIFEST_SCHEMA {
        return Err(schema(&label, "not a v1 raw envelope manifest"));
    }
    if get_str(&m, "prereg_lock_sha256", &label)? != LOCK_SHA256 {
        return Err(schema(&label, "raw envelope produced under another preregistration lock"));
    }
    read_verified(&repo.join(LOCK_REL), LOCK_SHA256)?;
    let cases = load_case_set(repo)?;
    if get_str(&m, "cases_file_sha256", &label)? != cases.sha256 {
        return Err(schema(&label, "raw envelope produced from another case file"));
    }
    let raw_name = get_str(&m, "raw_file", &label)?;
    let raw_path = manifest.parent().unwrap_or(Path::new(".")).join(raw_name);
    let raw_sha = get_str(&m, "raw_sha256", &label)?.to_string();
    let gz = read_verified(&raw_path, &raw_sha)?;
    let mut text = String::new();
    flate2::read::GzDecoder::new(gz.as_slice())
        .read_to_string(&mut text)
        .map_err(|e| schema(raw_name, format!("gzip: {e}")))?;
    let mut records = Vec::new();
    for line in text.lines().filter(|l| !l.trim().is_empty()) {
        records.push(pyjson::loads(line).map_err(|e| py_err(raw_name, e))?);
    }
    let n = get_f64(&m, "n_records", &label)?;
    if n != records.len() as f64 {
        return Err(schema(&label, format!("n_records {n} != {} lines", records.len())));
    }
    let commit = pinned_commit(&repo.to_string_lossy(), None).map_err(AbepError::from)?;
    let pins = RecordPins {
        hallthruster_commit: commit,
        prereg_lock_sha256: LOCK_SHA256.into(),
        cases_file_sha256: cases.sha256.clone(),
    };
    let points = ingest_records(&cases, &records, &pins)?;
    Ok(Envelope {
        manifest_rel: label,
        manifest_sha256: manifest_sha256.into(),
        raw_sha256: raw_sha,
        cases_sha256: cases.sha256.clone(),
        bz_family_kind: cases.bz_family_kind,
        points,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(pairs: Vec<(&str, Value)>) -> Value {
        let mut d = pyjson::Dict::new();
        for (k, v) in pairs {
            d.insert(k, v);
        }
        Value::Dict(d)
    }

    fn ok_record(sustained: bool) -> Vec<(&'static str, Value)> {
        vec![
            ("retcode", Value::str("success")),
            ("converged", Value::Bool(true)),
            ("finite", Value::Bool(true)),
            ("sustained", Value::Bool(sustained)),
            ("thrust_N", Value::Float(0.01)),
            ("discharge_current_A", Value::Float(3.0)),
            ("discharge_power_W", Value::Float(900.0)),
        ]
    }

    #[test]
    fn run_status_precedence() {
        assert_eq!(run_status(Family::Xe, &rec(ok_record(true))), RunStatus::Pass);
        assert_eq!(run_status(Family::Xe, &rec(ok_record(false))), RunStatus::NotSustained);
        let mut r = ok_record(true);
        r[0].1 = Value::str("failure");
        assert_eq!(run_status(Family::Xe, &rec(r)), RunStatus::NumericalFailure);
        let mut r = ok_record(true);
        r[4].1 = Value::Float(f64::NAN);
        assert_eq!(run_status(Family::Xe, &rec(r)), RunStatus::NumericalFailure);
        // N2 without a chemistry audit is OUT_OF_DOMAIN, before sustainment.
        assert_eq!(run_status(Family::N2Proxy, &rec(ok_record(false))), RunStatus::OutOfDomain);
        let chem = |f: f64| {
            let mut r = ok_record(true);
            r.push(("chemistry_unresolved_rate_files", Value::List(vec![])));
            r.push((
                "chemistry_per_reaction",
                Value::List(vec![rec(vec![("file", Value::str("a.dat")), ("extrapolated_fraction", Value::Float(f))])]),
            ));
            rec(r)
        };
        assert_eq!(run_status(Family::N2Proxy, &chem(0.0)), RunStatus::Pass);
        assert_eq!(run_status(Family::N2Proxy, &chem(1e-12)), RunStatus::Pass);
        assert_eq!(run_status(Family::N2Proxy, &chem(2e-12)), RunStatus::OutOfDomain);
    }

    #[test]
    fn case_hash_ignores_its_own_field_and_sorts_keys() {
        let a = rec(vec![("b", Value::int(1)), ("a", Value::Float(0.5))]);
        let b = rec(vec![("a", Value::Float(0.5)), ("b", Value::int(1)), ("case_sha256", Value::str("x"))]);
        assert_eq!(case_hash(&a).unwrap(), case_hash(&b).unwrap());
    }
}
