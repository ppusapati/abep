//! Two-layer Hall uncertainty structure (port of abep_sim/hall_ensemble.py; file
//! `hallthruster_bridge/ensemble/transport_ensemble_v0.json`).
//!
//! Layer 1 (calibration nuisance) is provenance of the P5 evidence and never a transport parameter or map axis. Layer
//! 2 is the credible set of transport closures (unweighted; EMPTY since 2026-09-26). Screening candidates never produce
//! design Hall maps. An admitted member needs an offline-verifiable admission record and complete O4 dispositions.

use crate::error::{HallError, HallResult};
use crate::py::{self, PyValue};
use abep_provenance::sha256_hex;

pub const ENSEMBLE_REL: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";

pub const ADMISSION_FIELDS: [&str; 12] = [
    "promoted_from_screening_id",
    "campaign_id",
    "preregistration",
    "decision_file",
    "decision_sha256",
    "scores_provenance_file",
    "scores_provenance_sha256",
    "passing_layer1_members",
    "admitted_utc",
    "decided_by",
    "o4_dispositions_file",
    "o4_dispositions_sha256",
];

fn err(message: String) -> HallError {
    HallError::value("ENS", message)
}

/// `os.path.join(base, v)` where `v` must be a string.
fn join_value(base: &str, v: &PyValue) -> HallResult<String> {
    match v {
        PyValue::Str(rel) => Ok(py::join(base, rel)),
        other => {
            Err(HallError::type_error(format!("expected str, bytes or os.PathLike object, not {}", other.type_name())))
        }
    }
}

/// `x or default`.
fn or_default(v: Option<&PyValue>, default: PyValue) -> PyValue {
    match v {
        Some(x) if x.truthy() => x.clone(),
        _ => default,
    }
}

/// `d.get(key)` for any hashable key (Python dict lookup).
fn get_any<'a>(d: &'a PyValue, key: &PyValue) -> HallResult<Option<&'a PyValue>> {
    match d {
        PyValue::Dict(entries) => {
            py::require_hashable(key)?;
            Ok(entries.iter().find(|(k, _)| k.py_eq(key)).map(|(_, v)| v))
        }
        other => Err(HallError::type_error(format!("'{}' object has no attribute 'get'", other.type_name()))),
    }
}

fn dict_items(d: &PyValue) -> HallResult<&Vec<(PyValue, PyValue)>> {
    match d {
        PyValue::Dict(entries) => Ok(entries),
        other => Err(HallError::type_error(format!("'{}' object has no attribute 'items'", other.type_name()))),
    }
}

fn opt_eq(a: Option<&PyValue>, b: &PyValue) -> bool {
    a.unwrap_or(&PyValue::None).py_eq(b)
}

/// `_sha_ok(path, sha)`.
fn sha_ok(path: &str, sha: Option<&PyValue>) -> HallResult<bool> {
    let Some(sha) = sha.filter(|v| v.truthy()) else { return Ok(false) };
    if !py::isfile(path) {
        return Ok(false);
    }
    Ok(py::s(sha256_hex(&py::read_file(path)?)).py_eq(sha))
}

/// The default ensemble path of the repository.
pub fn default_path(repo: &str) -> String {
    py::join(repo, ENSEMBLE_REL)
}

/// `{m["ensemble_member_id"] for m in e["members"]}`: ADMITTED members only.
pub fn member_ids(e: &PyValue) -> HallResult<Vec<PyValue>> {
    let mut out = Vec::new();
    for m in py::iterate(py::getitem(e, "members")?)? {
        out.push(py::getitem(&m, "ensemble_member_id")?.clone());
    }
    py::set_from(out)
}

/// `{m["ensemble_member_id"] for m in e.get("screening_candidates", [])}`.
pub fn screening_ids(e: &PyValue) -> HallResult<Vec<PyValue>> {
    let list = py::get(e, "screening_candidates")?.cloned().unwrap_or(PyValue::List(Vec::new()));
    let mut out = Vec::new();
    for m in py::iterate(&list)? {
        out.push(py::getitem(&m, "ensemble_member_id")?.clone());
    }
    py::set_from(out)
}

/// Gate for any Hall-map generator: screening candidates and unknown ids are refused.
pub fn require_admitted(member_id: &str, e: &PyValue) -> HallResult<()> {
    let id = py::s(member_id);
    if screening_ids(e)?.iter().any(|x| x.py_eq(&id)) {
        return Err(HallError::value(
            "REQ_SCREENING",
            format!("{member_id} is a SCREENING candidate: screening candidates never produce design Hall maps"),
        ));
    }
    if !member_ids(e)?.iter().any(|x| x.py_eq(&id)) {
        return Err(HallError::value(
            "REQ_NOT_ADMITTED",
            format!("{member_id} is not an admitted transport-ensemble member"),
        ));
    }
    Ok(())
}

/// `load_ensemble(path)`: the validated ensemble document (`None` = the repository file).
pub fn load_ensemble(repo: &str, path: Option<&str>) -> HallResult<PyValue> {
    let path = path.map_or_else(|| default_path(repo), str::to_string);
    let e = py::load_json_file(&path)?;
    if !opt_eq(py::get(&e, "schema")?, &py::s("transport_ensemble_v0")) {
        return Err(err(format!("{path} is not transport_ensemble_v0")));
    }
    if !opt_eq(py::get(&e, "weighting")?, &py::s("unweighted")) {
        return Err(err("members must stay unweighted until evidence-based weighting is justified and logged".into()));
    }
    let nuisance_doc = py::getitem(&e, "calibration_nuisance")?;
    let members_doc = py::getitem(&e, "members")?;
    let screening_doc = py::get(&e, "screening_candidates")?.cloned().unwrap_or(PyValue::List(Vec::new()));
    let all: Vec<PyValue> = match (members_doc, &screening_doc) {
        (PyValue::List(a), PyValue::List(b)) => a.iter().chain(b).cloned().collect(),
        (a, b) => {
            return Err(HallError::type_error(format!(
                "can only concatenate {} (not \"{}\") to {}",
                a.type_name(),
                b.type_name(),
                a.type_name()
            )))
        }
    };
    let mut ids: Vec<PyValue> = Vec::new();
    for m in &all {
        let mut missing = Vec::new();
        for f in py::iterate(py::getitem(&e, "member_fields")?)? {
            if !py::contains(m, &f)? {
                missing.push(py::py_str(&f));
            }
        }
        if !missing.is_empty() {
            let id = py::get(m, "ensemble_member_id")?.cloned().unwrap_or(PyValue::None);
            return Err(err(format!("ensemble member {} missing fields {}", py::py_str(&id), py::repr_strs(&missing))));
        }
        let mid = py::getitem(m, "ensemble_member_id")?;
        py::require_hashable(mid)?;
        if ids.iter().any(|x| x.py_eq(mid)) {
            return Err(err(format!("duplicate ensemble_member_id {}", py::py_str(mid))));
        }
        ids.push(mid.clone());
        let nuisance = py::set_from(py::iterate(nuisance_doc)?)?;
        let params = py::set_from(py::iterate(py::getitem(m, "transport_parameters")?)?)?;
        let leaked = py::intersection(&nuisance, &params);
        if !leaked.is_empty() {
            return Err(err(format!(
                "member {}: calibration nuisance {} used as a parameter",
                py::py_str(mid),
                py::repr(&PyValue::List(py::sorted(leaked)?))
            )));
        }
        for hyp in py::iterate(py::getitem(m, "calibration_hypotheses")?)? {
            let keys = py::set_from(py::iterate(&hyp)?)?;
            let unknown: Vec<PyValue> = keys.into_iter().filter(|k| !nuisance.iter().any(|n| n.py_eq(k))).collect();
            if !unknown.is_empty() {
                return Err(err(format!(
                    "member {}: unknown calibration hypotheses {}",
                    py::py_str(mid),
                    py::repr(&PyValue::List(py::sorted(unknown)?))
                )));
            }
            let mut bad = Vec::new();
            for (k, v) in dict_items(&hyp)? {
                let spec = get_any(nuisance_doc, k)?
                    .ok_or_else(|| HallError::new(crate::error::Kind::Key, "KEY", py::repr(k)))?;
                if !py::contains(py::getitem(spec, "values")?, v)? {
                    bad.push((k.clone(), v.clone()));
                }
            }
            if !bad.is_empty() {
                return Err(err(format!(
                    "member {}: undeclared nuisance values {}",
                    py::py_str(mid),
                    py::repr(&PyValue::Dict(bad))
                )));
            }
        }
    }
    if members_doc.truthy() && opt_eq(py::get(&e, "admission_rule")?, &PyValue::None) {
        return Err(err("members present but no admission_rule recorded".into()));
    }
    let screening = screening_ids(&e)?;
    let bridge_dir = py::dirname(&py::dirname(&py::abspath(&path)));
    for m in py::iterate(members_doc)? {
        check_admission(&m, &bridge_dir)?;
        let mid = py::getitem(&m, "ensemble_member_id")?;
        py::require_hashable(mid)?;
        if screening.iter().any(|x| x.py_eq(mid)) {
            return Err(err(format!(
                "{} is listed both as admitted member and as screening candidate",
                py::py_str(mid)
            )));
        }
    }
    Ok(e)
}

/// `_check_admission(member, bridge_dir)`.
fn check_admission(member: &PyValue, bridge_dir: &str) -> HallResult<()> {
    let mid = py::getitem(member, "ensemble_member_id")?;
    let m = py::py_str(mid);
    let adm = py::get(member, "admission")?;
    let Some(adm) = adm.filter(|a| py::is_dict(a)) else {
        return Err(err(format!("admitted member {m} has no admission record (evidence-based promotion only)")));
    };
    let missing: Vec<&str> =
        ADMISSION_FIELDS.iter().copied().filter(|f| !matches!(py::get(adm, f), Ok(Some(_)))).collect();
    if !missing.is_empty() {
        return Err(err(format!("admitted member {m}: admission record missing {}", py::repr_strs(&missing))));
    }
    let promoted = py::getitem(adm, "promoted_from_screening_id")?;
    if !promoted.py_eq(mid) {
        return Err(err(format!("admitted member {m}: promoted_from_screening_id {} differs", py::repr(promoted))));
    }
    for f in ["decision", "scores_provenance"] {
        let p = join_value(bridge_dir, py::getitem(adm, &format!("{f}_file"))?)?;
        let ok =
            py::isfile(&p) && py::s(sha256_hex(&py::read_file(&p)?)).py_eq(py::getitem(adm, &format!("{f}_sha256"))?);
        if !ok {
            return Err(err(format!("admitted member {m}: {f} file missing or its sha256 does not match")));
        }
    }
    let dec = py::load_json_file(&join_value(bridge_dir, py::getitem(adm, "decision_file")?)?)?;
    let prov = py::load_json_file(&join_value(bridge_dir, py::getitem(adm, "scores_provenance_file")?)?)?;
    let source = py::get(&dec, "source_scores_sha256")?;
    let bound = match source {
        Some(s) if s.truthy() => s.py_eq(py::get(&prov, "output_sha256")?.unwrap_or(&PyValue::None)),
        _ => false,
    };
    if !bound {
        return Err(err(format!(
            "admitted member {m}: decision is not bound to the scores output named by the provenance manifest"
        )));
    }
    let output = py::get(&prov, "output")?;
    let scores = join_value(bridge_dir, &or_default(output, py::s("")))?;
    let scores_ok = output.is_some_and(PyValue::truthy)
        && py::isfile(&scores)
        && py::s(sha256_hex(&py::read_file(&scores)?)).py_eq(py::getitem(&prov, "output_sha256")?);
    if !scores_ok {
        return Err(err(format!(
            "admitted member {m}: the scores file named by the provenance manifest is missing or modified"
        )));
    }
    let candidates = py::get(&dec, "candidates")?.cloned().unwrap_or(PyValue::Dict(Vec::new()));
    if !opt_eq(get_any(&candidates, mid)?, &py::s("PROMOTABLE")) {
        return Err(err(format!("admitted member {m}: the referenced decision does not list it as PROMOTABLE")));
    }
    let pm = py::get(&dec, "passing_members")?.cloned().unwrap_or(PyValue::Dict(Vec::new()));
    let passing_doc = get_any(&pm, mid)?.cloned().unwrap_or(PyValue::List(Vec::new()));
    let passing = py::set_from(py::iterate(&passing_doc)?)?;
    let layer1 = py::getitem(adm, "passing_layer1_members")?;
    let supported = layer1.truthy() && {
        let mine = py::set_from(py::iterate(layer1)?)?;
        mine.iter().all(|x| passing.iter().any(|y| y.py_eq(x)))
    };
    if !supported {
        return Err(err(format!("admitted member {m}: passing_layer1_members not supported by the decision")));
    }
    check_o4(&m, mid, adm, bridge_dir, &prov)
}

/// `_o4_result(mid, ref, chem, bridge_dir, mandatory_prov)`: the scorer's trigger_fired for `chem`.
fn o4_result(m: &str, rf: Option<&PyValue>, chem: &PyValue, bridge_dir: &str, mandatory: &PyValue) -> HallResult<bool> {
    let c = py::py_str(chem);
    let Some(rf) = rf.filter(|r| py::is_dict(r)) else {
        return Err(err(format!("admitted member {m}: no scored O4 result recorded for {c}")));
    };
    let pp = join_value(bridge_dir, &or_default(py::get(rf, "scores_provenance_file")?, py::s("")))?;
    if !sha_ok(&pp, py::get(rf, "scores_provenance_sha256")?)? {
        return Err(err(format!("admitted member {m}: O4 provenance for {c} missing or its sha256 does not match")));
    }
    let prov = py::load_json_file(&pp)?;
    let mandatory_input = py::get(mandatory, "input_sha256_canonical_jsonl")?;
    let scored_against = opt_eq(py::get(&prov, "mode")?, &py::s("vacuum"))
        && mandatory_input.is_some_and(PyValue::truthy)
        && opt_eq(py::get(&prov, "input_mandatory_sha256")?, mandatory_input.unwrap_or(&PyValue::None))
        && opt_eq(
            py::get(&prov, "mandatory_scores_sha256")?,
            py::get(mandatory, "output_sha256")?.unwrap_or(&PyValue::None),
        );
    if !scored_against {
        return Err(err(format!(
            "admitted member {m}: O4 result for {c} is not scored against this admission's mandatory dataset"
        )));
    }
    let sp = join_value(bridge_dir, &or_default(py::get(&prov, "output")?, py::s("")))?;
    if !sha_ok(&sp, py::get(&prov, "output_sha256")?)? {
        return Err(err(format!("admitted member {m}: O4 scores file for {c} missing or modified")));
    }
    let scores = py::load_json_file(&sp)?;
    let staged = or_default(py::get(&scores, "staged_escalation")?, PyValue::Dict(Vec::new()));
    match get_any(&staged, chem)? {
        Some(ev) if py::is_dict(ev) => match py::get(ev, "trigger_fired")? {
            Some(PyValue::Bool(b)) => Ok(*b),
            _ => Err(err(format!("admitted member {m}: O4 scores contain no trigger evaluation for {c}"))),
        },
        _ => Err(err(format!("admitted member {m}: O4 scores contain no trigger evaluation for {c}"))),
    }
}

/// `_check_o4(mid, adm, bridge_dir, mandatory_prov)`: every pre-registered O4 staged sensitivity (and every escalation
/// its trigger requires) is scored against the admission's mandatory dataset and dispositioned by the owner.
fn check_o4(m: &str, mid: &PyValue, adm: &PyValue, bridge_dir: &str, mandatory: &PyValue) -> HallResult<()> {
    let p = join_value(bridge_dir, py::getitem(adm, "o4_dispositions_file")?)?;
    if !sha_ok(&p, Some(py::getitem(adm, "o4_dispositions_sha256")?))? {
        return Err(err(format!("admitted member {m}: O4 dispositions file missing or its sha256 does not match")));
    }
    let d = py::load_json_file(&p)?;
    let bound = opt_eq(py::get(&d, "schema")?, &py::s("o4_dispositions_v1"))
        && opt_eq(py::get(&d, "mandatory_decision_sha256")?, py::getitem(adm, "decision_sha256")?);
    if !bound {
        return Err(err(format!("admitted member {m}: O4 dispositions are not bound to this admission's decision")));
    }
    let prereg = py::getitem(adm, "preregistration")?;
    let crit_path = join_value(bridge_dir, prereg)?;
    let staged = if py::isfile(&crit_path) {
        py::get(&py::load_json_file(&crit_path)?, "staged_sensitivities")?.cloned()
    } else {
        None
    };
    let Some(staged) = staged.filter(PyValue::truthy) else {
        return Err(err(format!(
            "admitted member {m}: pre-registration {} declares no staged sensitivities",
            py::py_str(prereg)
        )));
    };
    let ents = or_default(py::get(&d, "sensitivities")?, PyValue::Dict(Vec::new()));
    for (sens, spec) in dict_items(&staged)? {
        let sname = py::py_str(sens);
        let e = get_any(&ents, sens)?;
        let valid = match e {
            Some(e) if py::is_dict(e) => {
                opt_eq(py::get(e, "baseline")?, py::getitem(spec, "baseline")?)
                    && matches!(py::get(e, "trigger_fired")?, Some(PyValue::Bool(_)))
            }
            _ => false,
        };
        let Some(e) = e.filter(|_| valid) else {
            return Err(err(format!(
                "admitted member {m}: O4 disposition for {sname} missing or not against its baseline"
            )));
        };
        let fired = o4_result(m, py::get(e, "first_stage")?, sens, bridge_dir, mandatory)?;
        if !PyValue::Bool(fired).py_eq(py::getitem(e, "trigger_fired")?) {
            return Err(err(format!(
                "admitted member {m}: recorded O4 trigger for {sname} differs from the scored evaluation"
            )));
        }
        if fired {
            let escalations = or_default(py::get(e, "escalations")?, PyValue::Dict(Vec::new()));
            for (_, combo) in dict_items(py::getitem(spec, "escalation")?)? {
                o4_result(m, get_any(&escalations, combo)?, combo, bridge_dir, mandatory)?;
            }
        }
        let disposition = or_default(py::get(e, "disposition")?, py::s(""));
        if py::py_strip(&py::py_str(&disposition)).is_empty() {
            return Err(err(format!("admitted member {m}: no owner disposition recorded for {sname}")));
        }
    }
    let cleared = or_default(py::get(&d, "cleared_for_admission")?, PyValue::List(Vec::new()));
    let ok = py::contains(&cleared, mid)?
        && py::get(&d, "decided_by")?.is_some_and(PyValue::truthy)
        && py::get(&d, "decided_utc")?.is_some_and(PyValue::truthy);
    if !ok {
        return Err(err(format!("admitted member {m}: not cleared for admission by a recorded O4 disposition")));
    }
    Ok(())
}
