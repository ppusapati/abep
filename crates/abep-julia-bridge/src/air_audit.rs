//! CA-HALL-AIR-v1 verdicts (NP-HALL-CHEM-AIR v1 + addendum 01) from a frozen, sha-pinned audit record file.
//!
//! The Julia state envelope (`hallthruster_bridge/audit_air/air_state_envelope.jl`) writes, per run, the window sums of
//! the included channel classes and of every bound process, and the per-frame maxima of the addendum-01 metrics. This
//! module recomputes the window metrics from the sums with the same formulas, takes the per-frame maxima as recorded,
//! applies the eligibility rule and the ambiguity rule literally, and returns the verdict document. It never reads an
//! unfrozen file and changes no chemistry: promotion is a later, separate reaction-set change.

use crate::air_cases::{composition_points, AUDIT_CASES_REL, AUDIT_MANIFEST_REL, AUDIT_RAW_SCHEMA};
use abep_hall::envelope::F_OUT_TOL;
use abep_provenance::read_verified;
use abep_types::pyjson::{self, Dict, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;
use std::path::Path;

/// The addendum-01 metrics: (process, metric, threshold). Thresholds copied from n2_completeness_audit_v1 (F_P, F_ion
/// 0.01; F_S 0.05) and F_ion (F_e_loss 0.01).
pub const METRICS: [(&str, &str, f64); 14] = [
    ("HA-O2-DI-02", "F_ion", 0.01),
    ("HA-O2-DI-02", "F_P", 0.01),
    ("HA-O2-DI-02", "F_S(O2 destruction)", 0.05),
    ("HA-O2-ATT-01", "F_e_loss", 0.01),
    ("HA-O2-ATT-01", "F_S(O2 destruction)", 0.05),
    ("HA-WALL-02", "F_S(O destruction)", 0.05),
    ("HA-WALL-03", "F_S(N destruction)", 0.05),
    ("HA-N2N-R1", "F_ion", 0.01),
    ("HA-N2N-R1", "F_P", 0.01),
    ("HA-N2N-R1", "F_S(N^2+ destruction)", 0.05),
    ("HA-N2N-R2", "F_ion", 0.01),
    ("HA-N2N-R2", "F_P", 0.01),
    ("HA-N2N-R3", "F_ion", 0.01),
    ("HA-N2N-R3", "F_S(N2+ destruction)", 0.05),
];

/// Processes with no evaluable bound today (addendum 01 `no_bound_today`): UNBOUNDED_OMISSION.
pub const NO_BOUND_TODAY: [&str; 15] = [
    "HA-O-EXC-02",
    "HA-O-ION-02",
    "HA-O-ION-03",
    "HA-O2-ION-02",
    "HA-O2-ROT-01",
    "HA-O2-EXC-03",
    "HA-O2-VIB-01",
    "HA-O2P-DIS-01",
    "HA-N2P-DIS-01",
    "HA-DR-01",
    "HA-REC-02",
    "HA-IM-01",
    "HA-HN-01",
    "HA-MS-01",
    "HA-SUP-01",
];

/// Window sums every eligible record must carry.
pub const SUM_KEYS: [&str; 16] = [
    "R_ion",
    "R_e",
    "P_inel",
    "D_O2",
    "D_O",
    "D_N",
    "S_NZ2",
    "S_N2Z1",
    "W:HA-WALL-02",
    "W:HA-WALL-03",
    "R:HA-O2-DI-02",
    "R:HA-O2-ATT-01",
    "R:HA-N2N-R1",
    "R:HA-N2N-R2:nominal",
    "R:HA-N2N-R2:upper",
    "R:HA-N2N-R3",
];

pub const MEMBERS: [&str; 3] = ["lower", "nominal", "upper"];

fn model(m: impl Into<String>) -> AbepError {
    AbepError::Model { message: m.into() }
}

fn ratio(a: f64, b: f64) -> f64 {
    if b > 0.0 {
        a / b
    } else if a > 0.0 {
        f64::INFINITY
    } else {
        0.0
    }
}

/// The addendum-01 metric of one member from window (or frame) sums and the bound tables' header energies; `None` where
/// the member is not defined (the wall processes have no nominal recombination probability).
pub fn metric(
    process: &str,
    metric: &str,
    member: &str,
    s: &BTreeMap<String, f64>,
    headers: &BTreeMap<String, f64>,
) -> AbepResult<Option<f64>> {
    let g = |k: &str| s.get(k).copied().ok_or_else(|| model(format!("record sum {k} missing")));
    let h = |k: &str| headers.get(k).copied().ok_or_else(|| model(format!("record header {k} missing")));
    let scale = |lo: f64, hi: f64| match member {
        "lower" => lo,
        "upper" => hi,
        _ => 1.0,
    };
    let v = match (process, metric) {
        ("HA-O2-DI-02", m) => {
            let r = scale(0.9, 1.1) * g("R:HA-O2-DI-02")?;
            match m {
                "F_ion" => ratio(r, g("R_ion")? + r),
                "F_P" => ratio(r * h("HA-O2-DI-02")?, g("P_inel")? + r * h("HA-O2-DI-02")?),
                "F_S(O2 destruction)" => ratio(r, g("D_O2")? + r),
                _ => return Err(model(format!("{process}: no metric {m}"))),
            }
        }
        ("HA-O2-ATT-01", m) => {
            let r = scale(0.8, 1.2) * g("R:HA-O2-ATT-01")?;
            match m {
                "F_e_loss" => ratio(r, g("R_e")?),
                "F_S(O2 destruction)" => ratio(r, g("D_O2")? + r),
                _ => return Err(model(format!("{process}: no metric {m}"))),
            }
        }
        ("HA-WALL-02" | "HA-WALL-03", _) => {
            let (w, d) = if process == "HA-WALL-02" { ("W:HA-WALL-02", "D_O") } else { ("W:HA-WALL-03", "D_N") };
            match member {
                "lower" => 0.0,
                "upper" => ratio(g(w)?, g(d)? + g(w)?),
                _ => return Ok(None),
            }
        }
        ("HA-N2N-R1", m) => {
            let r = scale(0.9, 1.1) * g("R:HA-N2N-R1")?;
            match m {
                "F_ion" => ratio(r, g("R_ion")? + r),
                "F_P" => ratio(r * h("HA-N2N-R1")?, g("P_inel")? + r * h("HA-N2N-R1")?),
                "F_S(N^2+ destruction)" => ratio(r, g("S_NZ2")?),
                _ => return Err(model(format!("{process}: no metric {m}"))),
            }
        }
        ("HA-N2N-R2", m) => {
            let key = if member == "upper" { "HA-N2N-R2:upper" } else { "HA-N2N-R2:nominal" };
            let r = g(&format!("R:{key}"))?;
            match m {
                "F_ion" => ratio(r, g("R_ion")? + r),
                "F_P" => ratio(r * h(key)?, g("P_inel")? + r * h(key)?),
                _ => return Err(model(format!("{process}: no metric {m}"))),
            }
        }
        ("HA-N2N-R3", m) => {
            let r = scale(0.86, 1.11) * g("R:HA-N2N-R3")?;
            match m {
                "F_ion" => ratio(r, g("R_ion")? + r),
                "F_S(N2+ destruction)" => ratio(r, g("S_N2Z1")?),
                _ => return Err(model(format!("{process}: no metric {m}"))),
            }
        }
        _ => return Err(model(format!("no bound process {process}"))),
    };
    Ok(Some(v))
}

/// The ambiguity rule (n2_completeness_audit_v1_addendum1), applied literally.
pub fn ambiguity_verdict(lower: f64, upper: f64, threshold: f64) -> &'static str {
    if upper < threshold {
        "EXCLUDE"
    } else if lower > threshold {
        "PROMOTE"
    } else {
        "UNCERTAINTY VARIANT"
    }
}

fn severity(v: &str) -> u8 {
    match v {
        "PROMOTE" => 2,
        "UNCERTAINTY VARIANT" => 1,
        _ => 0,
    }
}

fn get<'a>(v: &'a Value, k: &str) -> Option<&'a Value> {
    v.as_dict().and_then(|d| d.get(k))
}

fn num_map(v: Option<&Value>) -> Option<BTreeMap<String, f64>> {
    let d = v?.as_dict()?;
    let mut m = BTreeMap::new();
    for (k, x) in d.iter() {
        m.insert(k.clone(), x.to_f64().ok()?);
    }
    Some(m)
}

/// Why a record is not eligible (addendum 01), or `None` when it counts toward the bounds.
pub fn ineligible(rec: &Value) -> Option<String> {
    let flag = |k: &str| matches!(get(rec, k), Some(Value::Bool(true)));
    for k in ["converged", "finite", "sustained"] {
        if !flag(k) {
            return Some(format!("{k} != true"));
        }
    }
    match get(rec, "chemistry_unresolved_rate_files").and_then(Value::as_list) {
        Some([]) => {}
        _ => return Some("unresolved rate file (DOM-AIR-01)".into()),
    }
    for k in ["chemistry_extrapolated_fraction_max", "audit_domain_fraction_max"] {
        match get(rec, k).and_then(|x| x.to_f64().ok()) {
            Some(f) if f <= F_OUT_TOL => {}
            _ => return Some(format!("{k} > 1e-12 or absent (DOM-AIR-01 / DOM-AIR-02)")),
        }
    }
    let sums = num_map(get(rec, "sums"));
    if sums.as_ref().is_none_or(|s| SUM_KEYS.iter().any(|k| !s.contains_key(*k))) {
        return Some("window sums missing".into());
    }
    None
}

/// Read a frozen audit record file through its raw manifest (sha256-pinned), check every record's pins against the
/// committed case file and MANIFEST, and return the records by key. A foreign key, a duplicate or a pin mismatch is
/// MODEL_ERROR (no partial audit).
pub fn read_frozen(repo: &Path, manifest: &Path, manifest_sha256: &str) -> AbepResult<BTreeMap<String, Value>> {
    let mtext = String::from_utf8(read_verified(manifest, manifest_sha256)?).map_err(|e| model(e.to_string()))?;
    let m = pyjson::loads(&mtext).map_err(|e| model(e.to_string()))?;
    let s = |k: &str| {
        get(&m, k).and_then(Value::as_str).map(str::to_string).ok_or_else(|| model(format!("raw manifest {k}")))
    };
    if s("schema")? != AUDIT_RAW_SCHEMA {
        return Err(model("not an audit raw manifest"));
    }
    let cases_sha = abep_provenance::sha256_file(&repo.join(AUDIT_CASES_REL))?;
    let man_sha = abep_provenance::sha256_file(&repo.join(AUDIT_MANIFEST_REL))?;
    if s("cases_file_sha256")? != cases_sha || s("manifest_sha256")? != man_sha {
        return Err(model("frozen audit records were produced for another case file or MANIFEST"));
    }
    let raw = manifest.parent().unwrap_or(Path::new(".")).join(s("raw_file")?);
    let gz = read_verified(&raw, &s("raw_sha256")?)?;
    let mut text = String::new();
    flate2::read::GzDecoder::new(&gz[..]).read_to_string(&mut text).map_err(|e| model(format!("gunzip: {e}")))?;
    let doc = pyjson::loads(&std::fs::read_to_string(repo.join(AUDIT_CASES_REL)).map_err(|e| model(e.to_string()))?)
        .map_err(|e| model(e.to_string()))?;
    let mut case_sha: BTreeMap<String, String> = BTreeMap::new();
    for c in get(&doc, "cases").and_then(Value::as_list).ok_or_else(|| model("audit cases"))? {
        let k = get(c, "key").and_then(Value::as_str).ok_or_else(|| model("case key"))?;
        let h = get(c, "case_sha256").and_then(Value::as_str).ok_or_else(|| model("case sha"))?;
        case_sha.insert(k.to_string(), h.to_string());
    }
    let mut out = BTreeMap::new();
    for line in text.lines().filter(|l| !l.trim().is_empty()) {
        let v = pyjson::loads(line).map_err(|e| model(e.to_string()))?;
        let key = get(&v, "key").and_then(Value::as_str).ok_or_else(|| model("record without key"))?.to_string();
        let want = case_sha.get(&key).ok_or_else(|| model(format!("record {key} is not an audit case")))?;
        let pins = [
            ("case_sha256", want.as_str()),
            ("cases_file_sha256", cases_sha.as_str()),
            ("manifest_sha256", man_sha.as_str()),
        ];
        for (k, w) in pins {
            if get(&v, k).and_then(Value::as_str) != Some(w) {
                return Err(model(format!("record {key}: {k} differs from the frozen value")));
            }
        }
        if out.insert(key.clone(), v).is_some() {
            return Err(model(format!("duplicate record {key}")));
        }
    }
    Ok(out)
}

/// The verdict document of a set of audit records (keyed by case key).
pub fn verdicts(repo: &Path, records: &BTreeMap<String, Value>) -> AbepResult<Value> {
    let set = abep_chem::hall_air::AirSet::load(repo)?;
    let corners: Vec<String> = composition_points(repo)?.into_iter().map(|c| c.id).collect();
    let doc = pyjson::loads(&std::fs::read_to_string(repo.join(AUDIT_CASES_REL)).map_err(|e| model(e.to_string()))?)
        .map_err(|e| model(e.to_string()))?;
    let all_keys: Vec<String> = get(&doc, "cases")
        .and_then(Value::as_list)
        .ok_or_else(|| model("audit cases"))?
        .iter()
        .filter_map(|c| get(c, "key").and_then(Value::as_str).map(str::to_string))
        .collect();
    let mut eligible: Vec<(&String, &Value)> = Vec::new();
    let mut excluded = Dict::new();
    let mut covered: BTreeSet<String> = BTreeSet::new();
    for k in &all_keys {
        match records.get(k) {
            None => {
                excluded.insert(k.as_str(), Value::str("record absent"));
            }
            Some(r) => match ineligible(r) {
                Some(why) => {
                    excluded.insert(k.as_str(), Value::str(&why));
                }
                None => {
                    eligible.push((k, r));
                    if let Some(c) = get(r, "composition_id").and_then(Value::as_str) {
                        covered.insert(c.to_string());
                    }
                }
            },
        }
    }
    let uncovered: Vec<&String> = corners.iter().filter(|c| !covered.contains(*c)).collect();
    let mut rows = Dict::new();
    let mut not_representable = Vec::new();
    let mut proc_verdicts: BTreeMap<&str, &str> = BTreeMap::new();
    for (process, metric_id, threshold) in METRICS {
        for form in ["window", "frame_max"] {
            let (mut lo, mut hi) = (f64::INFINITY, f64::NEG_INFINITY);
            let (mut nlo, mut nhi) = (f64::INFINITY, f64::NEG_INFINITY);
            let mut worst = String::new();
            for (k, r) in &eligible {
                let vals: [Option<f64>; 3] = if form == "window" {
                    let s = num_map(get(r, "sums")).unwrap_or_default();
                    let h = num_map(get(r, "headers")).unwrap_or_default();
                    [
                        metric(process, metric_id, "lower", &s, &h)?,
                        metric(process, metric_id, "nominal", &s, &h)?,
                        metric(process, metric_id, "upper", &s, &h)?,
                    ]
                } else {
                    let fm = num_map(get(r, "frame_max")).unwrap_or_default();
                    MEMBERS.map(|m| fm.get(&format!("{process}|{metric_id}|{m}")).copied())
                };
                let (Some(l), Some(u)) = (vals[0], vals[2]) else {
                    return Err(model(format!("{k}: {process} {metric_id} {form} lower / upper missing")));
                };
                lo = lo.min(l);
                if u > hi {
                    hi = u;
                    worst = (*k).clone();
                }
                if let Some(n) = vals[1] {
                    nlo = nlo.min(n);
                    nhi = nhi.max(n);
                }
            }
            let verdict = if !uncovered.is_empty() || eligible.is_empty() {
                "NOT_EVALUABLE"
            } else {
                ambiguity_verdict(lo, hi, threshold)
            };
            let e = proc_verdicts.entry(process).or_insert("EXCLUDE");
            if verdict == "NOT_EVALUABLE" || *e == "NOT_EVALUABLE" {
                *e = "NOT_EVALUABLE";
            } else if severity(verdict) > severity(e) {
                *e = verdict;
            }
            let fin = |x: f64| if x.is_finite() { Value::Float(x) } else { Value::Null };
            let mut d = Dict::new();
            d.insert("threshold", Value::Float(threshold));
            d.insert("lower_min", fin(lo));
            d.insert("nominal_range", Value::List(vec![fin(nlo), fin(nhi)]));
            d.insert("upper_max", fin(hi));
            d.insert("worst_case", Value::str(&worst));
            d.insert("verdict", Value::str(verdict));
            rows.insert(format!("{process}|{metric_id}|{form}").as_str(), Value::Dict(d));
        }
    }
    let mut pv = Dict::new();
    for (p, v) in &proc_verdicts {
        pv.insert(*p, Value::str(*v));
        if *v == "PROMOTE" || *v == "UNCERTAINTY VARIANT" {
            not_representable.push(Value::str(*p));
        }
    }
    for p in NO_BOUND_TODAY {
        pv.insert(p, Value::str("UNBOUNDED_OMISSION"));
    }
    let set_outcome = if !uncovered.is_empty() || eligible.is_empty() {
        "NOT_EVALUABLE"
    } else if !not_representable.is_empty() {
        "NOT_REPRESENTABLE_IN_PINNED_SOLVER"
    } else {
        "INCOMPLETE_EVIDENCE"
    };
    let mut out = Dict::new();
    out.insert("schema", Value::str("np_hall_chem_air_audit_verdicts_v1"));
    out.insert("audit", Value::str("CA-HALL-AIR-v1 (NP-HALL-CHEM-AIR v1 + addendum 01)"));
    out.insert("reaction_set", Value::str(&set.label));
    out.insert("provisional", Value::Bool(!set.tier1_gaps.is_empty()));
    out.insert("tier1_gaps", Value::List(set.tier1_gaps.iter().map(Value::str).collect()));
    out.insert("n_cases", Value::int(all_keys.len() as i64));
    out.insert("n_eligible", Value::int(eligible.len() as i64));
    out.insert("corners_without_eligible_run", Value::List(uncovered.iter().map(|c| Value::str(c.as_str())).collect()));
    out.insert("rows", Value::Dict(rows));
    out.insert("process_verdicts", Value::Dict(pv));
    out.insert("not_representable_promoted_or_variant", Value::List(not_representable));
    out.insert("set_outcome", Value::str(set_outcome));
    out.insert(
        "note",
        Value::str("every bound process is not representable in the pinned solver (capability audit L-01..L-06); UNBOUNDED_OMISSION processes block completeness unless sourced or disposed (OQ-HA-06); verdicts are PROVISIONAL while tier-1 gaps exist"),
    );
    Ok(Value::Dict(out))
}
