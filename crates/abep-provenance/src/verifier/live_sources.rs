//! Consumed values against their live sources, driven by a versioned spec (`abep_live_source_spec_v1`).
//!
//! The registered spec `h2_6_live_sources_v1` carries the check semantics of the H2-6 builder's `verify_sources()`.
//! The consumed values and the evidence pins come from the immutable record the spec binds by sha256; the verifier
//! itself holds no H2-6 value.

use super::load::{abs_path, exists, parse_json, read, sha256_of, OpenError};
use super::pyliteral::{self, LiteralRules};
use super::pyvalue::{isclose, PyValue};
use super::{normpath, Finding, FindingKind, Py, Raised};
use crate::sha256_hex;
use serde::Deserialize;
use std::path::Path;

/// Repository path of the registered H2-6 spec.
pub const H2_6_SPEC_PATH: &str = "docs/ci/provenance_specs/h2_6_live_sources_v1.json";
/// The spec, compiled in so that a tree under verification cannot change the verifier's semantics.
pub const H2_6_SPEC_JSON: &str = include_str!("../../../../docs/ci/provenance_specs/h2_6_live_sources_v1.json");
/// sha256 of [`H2_6_SPEC_JSON`]; a spec change without updating it fails closed.
pub const H2_6_SPEC_SHA256: &str = "3be115493fd0b3a3c8f880e30576df6ab027b95558a0b5c5db59647a2c84db8c";

const SPEC_SCHEMA: &str = "abep_live_source_spec_v1";

#[derive(Debug, Deserialize)]
struct Spec {
    schema: String,
    id: String,
    consumed_record: Record,
    pin_label: String,
    groups: Vec<Group>,
}

#[derive(Debug, Deserialize)]
struct Record {
    path: String,
    sha256: String,
    pin_lists: Vec<String>,
    inputs_key: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Format {
    Json,
    PythonLiterals,
}

#[derive(Debug, Deserialize)]
struct NameTemplate {
    name: String,
    key_template: String,
}

#[derive(Debug, Deserialize)]
struct ClassTemplate {
    class: String,
    key_template: String,
}

#[derive(Debug, Deserialize)]
struct LiteralSpec {
    assign_names: Vec<String>,
    dict_binop_left: Option<NameTemplate>,
    class_annassign: Option<ClassTemplate>,
}

#[derive(Debug, Deserialize)]
struct Group {
    label: String,
    source: String,
    format: Format,
    catch_key_error: bool,
    #[serde(default)]
    python_literals: Option<LiteralSpec>,
    checks: Vec<ValueCheck>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Op {
    Compare,
    Contains,
    EqualsLiteral,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Absent {
    Error,
    None,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Step {
    Key(String),
    Get(String),
    ById { field: String, equals: String },
    Map { key_field: String, value_field: String, value_absent: Absent },
    FloatKeysSorted(bool),
}

#[derive(Debug, Default, Deserialize)]
struct Consumed {
    input: Option<String>,
    index: Option<String>,
    #[serde(default)]
    as_float_list: bool,
    record_path: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
struct ValueCheck {
    name: String,
    op: Op,
    live: Vec<Step>,
    #[serde(default)]
    consumed: Option<Consumed>,
    #[serde(default)]
    rel_tol: Option<f64>,
    #[serde(default)]
    needle: Option<String>,
    #[serde(default)]
    literal: Option<String>,
}

fn spec_error(detail: impl Into<String>) -> Raised {
    Raised::Spec { detail: detail.into() }
}

fn parse_spec(json: &str) -> Py<Spec> {
    let spec: Spec = serde_json::from_str(json).map_err(|e| spec_error(format!("live-source spec: {e}")))?;
    if spec.schema != SPEC_SCHEMA {
        return Err(spec_error(format!("live-source spec schema {:?}, expected {SPEC_SCHEMA:?}", spec.schema)));
    }
    Ok(spec)
}

/// The registered `h2_6_live_sources` check.
pub(crate) fn h2_6_live_sources(root: &Path) -> Py<(Vec<Finding>, String)> {
    let actual = sha256_hex(H2_6_SPEC_JSON.as_bytes());
    if actual != H2_6_SPEC_SHA256 {
        return Err(spec_error(format!("embedded spec sha256 {actual} != registered {H2_6_SPEC_SHA256}")));
    }
    run_spec(root, &parse_spec(H2_6_SPEC_JSON)?)
}

/// Run any `abep_live_source_spec_v1` spec on a tree. `Err` is the single RAISED finding of an aborted check.
pub fn verify_live_sources(root: &Path, spec_json: &str) -> Result<Vec<Finding>, Finding> {
    parse_spec(spec_json).and_then(|s| run_spec(root, &s)).map(|r| r.0).map_err(Raised::into_finding)
}

fn run_spec(root: &Path, spec: &Spec) -> Py<(Vec<Finding>, String)> {
    let rec = &spec.consumed_record;
    let rec_file = normpath(&rec.path);
    let bytes = match read(&abs_path(root, &rec.path)) {
        Ok(b) => b,
        Err(_) => {
            let f = Finding::new(FindingKind::Missing, rec_file, "consumed record", "consumed-value record missing");
            return Ok((vec![f], String::new()));
        }
    };
    if sha256_hex(&bytes) != rec.sha256 {
        let f = Finding::new(
            FindingKind::Sha256Mismatch,
            rec_file,
            "consumed record",
            "consumed-value record differs from the sha256 the spec binds",
        );
        return Ok((vec![f], String::new()));
    }
    let record = parse_json(&bytes, &rec.path).map_err(|_| spec_error("consumed record does not parse"))?;
    let inputs = record.getitem_str(&rec.inputs_key).map_err(|_| spec_error("consumed record has no inputs"))?;

    let mut errs = Vec::new();
    let mut n_pins = 0;
    for list in &rec.pin_lists {
        let entries = record.getitem_str(list).and_then(|l| l.iterate()).map_err(|_| spec_error("pin list"))?;
        for entry in entries {
            let (Ok(PyValue::Str(rel)), Ok(PyValue::Str(want))) =
                (entry.getitem_str("path"), entry.getitem_str("sha256"))
            else {
                return Err(spec_error("pin entry without path / sha256"));
            };
            n_pins += 1;
            let path = abs_path(root, &rel);
            if !exists(&path) {
                errs.push(Finding::new(
                    FindingKind::Missing,
                    normpath(&rel),
                    &spec.pin_label,
                    format!("pinned file missing: {rel}"),
                ));
            } else if sha256_of(&path, &rel)? != want {
                errs.push(Finding::new(
                    FindingKind::Sha256Mismatch,
                    normpath(&rel),
                    &spec.pin_label,
                    format!("pinned file altered (re-pin deliberately): {rel}"),
                ));
            }
        }
    }
    let mut n_checks = 0;
    for group in &spec.groups {
        n_checks += group.checks.len();
        errs.extend(eval_group(root, group, &record, &inputs)?);
    }
    Ok((errs, format!("{}: {n_pins} evidence pins, {n_checks} value checks", spec.id)))
}

fn load_group_source(root: &Path, group: &Group) -> Result<PyValue, Result<Finding, Raised>> {
    let bytes = match read(&abs_path(root, &group.source)) {
        Ok(b) => b,
        Err(OpenError::NotFound) => {
            return Err(Ok(Finding::new(
                FindingKind::SourceMissing,
                normpath(&group.source),
                &group.label,
                format!("{} source: FileNotFoundError", group.label),
            )))
        }
        Err(e) => return Err(Err(e.raised(&group.source))),
    };
    match group.format {
        Format::Json => parse_json(&bytes, &group.source).map_err(Err),
        Format::PythonLiterals => {
            let lit = group.python_literals.as_ref().ok_or_else(|| Err(spec_error("python_literals rules missing")))?;
            let rules = LiteralRules {
                assign_names: lit.assign_names.clone(),
                dict_binop_left: lit.dict_binop_left.as_ref().map(|d| (d.name.clone(), d.key_template.clone())),
                class_annassign: lit.class_annassign.as_ref().map(|c| (c.class.clone(), c.key_template.clone())),
            };
            let text = String::from_utf8(bytes).map_err(|e| {
                Err(Raised::Decode { file: group.source.clone(), detail: format!("UnicodeDecodeError: {e}") })
            })?;
            let map = pyliteral::extract(&text, &rules, &group.source).map_err(Err)?;
            Ok(PyValue::Dict(map.into_iter().map(|(k, v)| (PyValue::Str(k), v)).collect()))
        }
    }
}

/// One group: its findings, a caught group finding, or an error escaping the whole check.
fn eval_group(root: &Path, group: &Group, record: &PyValue, inputs: &PyValue) -> Py<Vec<Finding>> {
    let doc = match load_group_source(root, group) {
        Ok(d) => d,
        Err(Ok(finding)) => return Ok(vec![finding]),
        Err(Err(raised)) => return Err(raised),
    };
    let mut found = Vec::new();
    for check in &group.checks {
        match eval_check(group, check, &doc, record, inputs) {
            Ok(None) => {}
            Ok(Some(f)) => found.push(f),
            Err(Raised::KeyMissing { key }) if group.catch_key_error => {
                found.push(Finding::new(
                    FindingKind::SourceKeyMissing,
                    normpath(&group.source),
                    key.clone(),
                    format!("{} source: KeyError({key:?})", group.label),
                ));
                return Ok(found);
            }
            Err(r) => return Err(r),
        }
    }
    Ok(found)
}

fn eval_check(
    group: &Group,
    check: &ValueCheck,
    doc: &PyValue,
    record: &PyValue,
    inputs: &PyValue,
) -> Py<Option<Finding>> {
    let live = locate(doc, &check.live)?;
    let mismatch =
        |detail: String| Some(Finding::new(FindingKind::ValueMismatch, normpath(&group.source), &check.name, detail));
    match check.op {
        Op::Compare => {
            let want = consumed(check.consumed.as_ref(), record, inputs)?;
            let rel = check.rel_tol.unwrap_or(1e-9);
            let same = if want.is_number() && live.is_number() {
                isclose(live.py_float()?, want.py_float()?, rel)
            } else {
                live.py_eq(&want)
            };
            Ok(if same {
                None
            } else {
                mismatch(format!(
                    "{}: live source {} != consumed {}",
                    check.name,
                    live.to_compact_json(),
                    want.to_compact_json()
                ))
            })
        }
        Op::Contains => {
            let needle = check.needle.as_ref().ok_or_else(|| spec_error("contains without needle"))?;
            Ok(if live.contains(&PyValue::str(needle.clone()))? {
                None
            } else {
                mismatch(format!("{}: live source no longer contains {needle:?}", check.name))
            })
        }
        Op::EqualsLiteral => {
            let literal = check.literal.as_ref().ok_or_else(|| spec_error("equals_literal without literal"))?;
            Ok(if live.py_eq(&PyValue::str(literal.clone())) {
                None
            } else {
                mismatch(format!("{}: live source text changed (expected {literal:?})", check.name))
            })
        }
    }
}

fn locate(doc: &PyValue, steps: &[Step]) -> Py<PyValue> {
    let mut cur = doc.clone();
    for step in steps {
        cur = match step {
            Step::Key(k) => cur.getitem_str(k)?,
            Step::Get(k) => cur.get(k)?.unwrap_or(PyValue::None),
            Step::ById { field, equals } => {
                let mut hit = None;
                for x in cur.iterate()? {
                    if matches!(x, PyValue::Dict(_))
                        && x.get(field)?.is_some_and(|v| v.py_eq(&PyValue::str(equals.clone())))
                    {
                        hit = Some(x);
                        break;
                    }
                }
                hit.ok_or_else(|| Raised::key(equals.clone()))?
            }
            Step::Map { key_field, value_field, value_absent } => {
                let mut entries: Vec<(PyValue, PyValue)> = Vec::new();
                for x in cur.iterate()? {
                    let k = x.getitem_str(key_field)?;
                    let v = match value_absent {
                        Absent::Error => x.getitem_str(value_field)?,
                        Absent::None => x.get(value_field)?.unwrap_or(PyValue::None),
                    };
                    if !k.hashable() {
                        return Err(Raised::type_error(format!("unhashable type: '{}'", k.type_name())));
                    }
                    match entries.iter_mut().find(|(ek, _)| ek.py_eq(&k)) {
                        Some(slot) => slot.1 = v,
                        None => entries.push((k, v)),
                    }
                }
                PyValue::Dict(entries)
            }
            Step::FloatKeysSorted(false) => return Err(spec_error("float_keys_sorted must be true")),
            Step::FloatKeysSorted(true) => {
                let mut keys = cur.iterate()?.iter().map(PyValue::py_float).collect::<Py<Vec<f64>>>()?;
                keys.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
                PyValue::List(keys.into_iter().map(PyValue::Float).collect())
            }
        };
    }
    Ok(cur)
}

fn consumed(c: Option<&Consumed>, record: &PyValue, inputs: &PyValue) -> Py<PyValue> {
    let c = c.ok_or_else(|| spec_error("compare without consumed"))?;
    let bad = |what: &str| spec_error(format!("consumed record lacks {what}"));
    if let Some(path) = &c.record_path {
        return path.iter().try_fold(record.clone(), |v, k| v.getitem_str(k)).map_err(|_| bad(&path.join(".")));
    }
    let name = c.input.as_ref().ok_or_else(|| spec_error("consumed without input"))?;
    let mut v = inputs.getitem_str(name).and_then(|i| i.getitem_str("value")).map_err(|_| bad(name))?;
    if let Some(index) = &c.index {
        v = v.getitem_str(index).map_err(|_| bad(&format!("{name}[{index}]")))?;
    }
    if c.as_float_list {
        let items = v.iterate().map_err(|_| bad(name))?;
        v = PyValue::List(
            items.iter().map(|x| x.py_float().map(PyValue::Float)).collect::<Py<Vec<_>>>().map_err(|_| bad(name))?,
        );
    }
    Ok(v)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_spec_is_the_registered_one() {
        assert_eq!(sha256_hex(H2_6_SPEC_JSON.as_bytes()), H2_6_SPEC_SHA256);
        let spec = parse_spec(H2_6_SPEC_JSON).unwrap();
        assert_eq!(spec.id, "h2_6_live_sources_v1");
        assert_eq!(spec.groups.iter().map(|g| g.checks.len()).sum::<usize>(), 44);
        let labels: Vec<&str> = spec.groups.iter().map(|g| g.label.as_str()).collect();
        assert_eq!(labels, ["constants", "A5", "W1", "W4", "W3", "lane 25", "capability demo"]);
    }

    #[test]
    fn locator_steps_follow_python() {
        let doc: PyValue = serde_json::from_str(
            r#"{"t": [{"id": "a", "value": 1}, {"id": "b"}, {"id": "a", "value": 2}],
                "r": ["x", {"id": "k", "v": 3}, {"id": "k", "v": 4}],
                "g": {"0.01": 1, "0.005": 2}}"#,
        )
        .unwrap();
        let map_none = Step::Map { key_field: "id".into(), value_field: "value".into(), value_absent: Absent::None };
        let m = locate(&doc, &[Step::Key("t".into()), map_none]).unwrap();
        assert_eq!(m.getitem_str("a").unwrap(), PyValue::Int(2));
        assert_eq!(m.getitem_str("b").unwrap(), PyValue::None);
        let map_err = Step::Map { key_field: "id".into(), value_field: "value".into(), value_absent: Absent::Error };
        assert_eq!(locate(&doc, &[Step::Key("t".into()), map_err]).unwrap_err(), Raised::key("value"));
        let by_id = Step::ById { field: "id".into(), equals: "k".into() };
        let hit = locate(&doc, &[Step::Key("r".into()), by_id, Step::Key("v".into())]).unwrap();
        assert_eq!(hit, PyValue::Int(3));
        let missing = Step::ById { field: "id".into(), equals: "zz".into() };
        assert_eq!(locate(&doc, &[Step::Key("r".into()), missing]).unwrap_err(), Raised::key("zz"));
        let grid = locate(&doc, &[Step::Key("g".into()), Step::FloatKeysSorted(true)]).unwrap();
        assert_eq!(grid, PyValue::List(vec![PyValue::Float(0.005), PyValue::Float(0.01)]));
    }
}
