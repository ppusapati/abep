//! P4 anode / collector materials: the fail-closed hard-gate kernels (reference
//! `docs/experiments/hall_icp/p4_anode_materials/p4_screening.py` and `p4_a9_16_rules.validation_stage_record`,
//! contract
//! `docs/rust_migration/contracts/C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS-SCREENING_KERNELS/parity_prereg_v1.json`).
//!
//! A gate is applied only when both the requirement and the property are evidenced; otherwise INCOMPLETE_EVIDENCE
//! (never PASS). A property whose applicability domain does not cover the requirement's gives OUT_OF_DOMAIN. The
//! continuous-use-temperature gate needs an explicitly resolved thermal closure and an evidenced T_operating record in
//! K; a T_validated_continuous property needs a stage-2 / stage-3 record that classifies under the owner's staged
//! hierarchy (A9.12 P4-OQ-01, A9.16 COR-06). A satisfied gate is GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN; a candidate
//! is at most NOT_SCREENED_OUT; the final material is OPEN for every input (anode material OPEN, 316L
//! REJECTED_AS_CURRENT_BASELINE). Records are JSON-shaped Python values; messages reproduce the reference text.

use crate::materials::pymath;
use abep_types::pyjson::{
    dumps, py_eq, py_repr, py_str, py_strip, py_upper, DumpOptions, PyException, PyResult, Value,
};
use std::collections::BTreeSet;

pub const GATE_OUTCOMES: [&str; 4] =
    ["INCOMPLETE_EVIDENCE", "OUT_OF_DOMAIN", "GATE_VIOLATED_BY_EVIDENCE", "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN"];
pub const FINAL_MATERIAL_STATUS: &str = "OPEN";
const INCOMPLETE: &str = "INCOMPLETE_EVIDENCE";
const EVIDENCED_REQUIREMENT_STATUSES: [&str; 2] = ["OWNER_GIVEN", "DEFINED_FROM_EVIDENCE"];
const RESOLVED_THERMAL_STATUSES: [&str; 1] = ["CLOSED_BY_EVIDENCE"];
const T_OPERATING_FIELDS: [&str; 4] = ["value_si", "unit_si", "evidence_class", "source"];
const T_OPERATING_EVIDENCE_CLASSES: [&str; 2] = ["measured", "model-derived"];
const T_VALIDATED_PROPERTY: &str = "T_validated_continuous";
const T_VALIDATED_RECORD_KEYS: [&str; 3] =
    ["validation_stage_record", "validation_stage_record_id", "validation_stage_record_sha256"];
const REQUIREMENT_FIELDS: [&str; 10] =
    ["id", "criterion", "application", "property", "kind", "value", "unit", "status", "source", "domain"];
const PROPERTY_FIELDS: [&str; 13] = [
    "id",
    "candidate",
    "property",
    "value_si",
    "unit_si",
    "condition",
    "domain",
    "source_id",
    "locator",
    "quantity_type",
    "evidence_level",
    "admissible_for_gate",
    "synthetic",
];
const GATE_KINDS: [&str; 3] = ["min", "max", "min_with_margin"];

// p4_a9_16_rules (A9.12 S5.10 P4-OQ-01): staged evidence hierarchy for T_validated,continuous.
pub const STAGE_1: &str = "STAGE_1_COUPON_SCREENING";
pub const STAGE_2: &str = "STAGE_2_INTEGRATED_REPLACEABLE_COMPONENT_CONFIRMATION";
pub const STAGE_3: &str = "STAGE_3_QUALIFICATION_LIFE_EVIDENCE";
const STAGES: [&str; 3] = [STAGE_1, STAGE_2, STAGE_3];
const T_VALIDATED_GATE_STAGES: [&str; 2] = [STAGE_2, STAGE_3];
const STAGE_RESULT: [&str; 3] =
    ["COUPON_SUPPORTED_PROVISIONAL_LIMIT", "T_VALIDATED_CONTINUOUS", "FLIGHT_LIFE_QUALIFIED_LIMIT"];
const STAGE_1_CONDITIONS: [&str; 5] =
    ["atmosphere_species", "temperature", "electrical_bias_current_condition", "exposure_duration", "thermal_cycling"];
const STAGE_1_METRICS: [&str; 4] = ["electrical", "oxidation_recession", "mass_loss", "surface_material"];
const STAGE_2_ENVIRONMENT: [&str; 3] = ["plasma_environment", "electrical_environment", "thermal_environment"];
const NON_VALIDATION_BASES: [&str; 5] = [
    "MELTING_POINT",
    "SHORT_VENDOR_EXPOSURE",
    "GENERIC_AIR_USE_TEMPERATURE",
    "BRIEF_COUPON_TEST",
    "SUPPLIER_CONTINUOUS_RATING",
];
const LIMIT_USES: [(&str, &str); 3] = [
    ("design_screening", STAGE_1),
    ("p3_lock1_material_temperature_closure", STAGE_2),
    ("final_flight_life_claim", STAGE_3),
];

fn screening(message: impl Into<String>) -> PyException {
    pymath::err("ScreeningError", message)
}

fn in_strs(v: &Value, set: &[&str]) -> bool {
    set.iter().any(|s| py_eq(v, &Value::str(*s)))
}

fn tuple_repr(set: &[&str]) -> String {
    let items: Vec<Value> = set.iter().map(|s| Value::str(*s)).collect();
    abep_types::pyjson::py_repr_tuple(&items)
}

fn list_repr<S: AsRef<str>>(items: &[S]) -> String {
    py_repr(&Value::List(items.iter().map(|s| Value::str(s.as_ref())).collect()))
}

/// `rec[k]` of a dict already checked by `_require` (KeyError otherwise).
fn at<'a>(rec: &'a Value, k: &str) -> PyResult<&'a Value> {
    rec.as_dict().and_then(|d| d.get(k)).ok_or_else(|| pymath::err("KeyError", format!("'{k}'")))
}

/// `rec.get(k)` (`None` when absent); rec is a dict.
fn get<'a>(rec: &'a Value, k: &str) -> &'a Value {
    static NONE: Value = Value::Null;
    rec.as_dict().and_then(|d| d.get(k)).unwrap_or(&NONE)
}

fn require(rec: &Value, fields: &[&str], what: &str) -> PyResult<()> {
    let d = rec.as_dict().ok_or_else(|| screening(format!("{what}: record must be a dict")))?;
    let missing: Vec<&str> = fields.iter().copied().filter(|f| !d.contains_key(f)).collect();
    if !missing.is_empty() {
        let id = d.get("id").map(py_str).unwrap_or_else(|| "?".into());
        return Err(screening(format!("{what} {id}: missing fields {}", list_repr(&missing))));
    }
    Ok(())
}

/// A finite real number (bool, NaN and +/-inf are never evidence).
fn finite_number(v: &Value) -> PyResult<bool> {
    match v {
        Value::Int(i) => Ok(i.to_f64()?.is_finite()),
        Value::Float(x) => Ok(x.is_finite()),
        _ => Ok(false),
    }
}

fn num(v: &Value) -> f64 {
    match v {
        Value::Int(i) => i.to_f64().unwrap_or(f64::NAN),
        Value::Float(x) => *x,
        Value::Bool(b) => f64::from(u8::from(*b)),
        _ => f64::NAN,
    }
}

/// `_check_domain`: a non-empty list of non-empty strings.
fn check_domain(dom: &Value, what: &str) -> PyResult<BTreeSet<String>> {
    let ok = match dom {
        Value::List(l) if !l.is_empty() => l.iter().all(|x| matches!(x, Value::Str(s) if !py_strip(s).is_empty())),
        _ => false,
    };
    if !ok {
        return Err(screening(format!(
            "{what}: domain must be a non-empty list of non-empty strings, got {}",
            py_repr(dom)
        )));
    }
    Ok(dom.as_list().expect("checked").iter().map(|x| x.as_str().expect("checked").to_string()).collect())
}

fn sorted_repr(dom: &Value) -> String {
    let mut v: Vec<String> =
        dom.as_list().expect("checked").iter().map(|x| x.as_str().expect("checked").into()).collect();
    v.sort();
    list_repr(&v)
}

/// `requirement_evidenced(req)`: a finite numeric value, an evidenced status and a source.
pub fn requirement_evidenced(req: &Value) -> PyResult<bool> {
    require(req, &REQUIREMENT_FIELDS, "requirement")?;
    let kind = at(req, "kind")?;
    if !in_strs(kind, &GATE_KINDS) {
        return Err(screening(format!("requirement {}: unknown gate kind {}", py_str(at(req, "id")?), py_repr(kind))));
    }
    Ok(finite_number(at(req, "value")?)?
        && in_strs(at(req, "status")?, &EVIDENCED_REQUIREMENT_STATUSES)
        && at(req, "source")?.truthy())
}

/// `property_evidenced(prop)`: a finite SI value, a source, a locator and `admissible_for_gate is True`.
pub fn property_evidenced(prop: &Value) -> PyResult<bool> {
    require(prop, &PROPERTY_FIELDS, "property")?;
    Ok(finite_number(at(prop, "value_si")?)?
        && at(prop, "source_id")?.truthy()
        && at(prop, "locator")?.truthy()
        && matches!(at(prop, "admissible_for_gate")?, Value::Bool(true)))
}

/// `operating_temperature_evidenced(t_op)` -> (ok, reason).
fn operating_temperature_evidenced(t_op: &Value) -> PyResult<(bool, String)> {
    let d = match t_op {
        Value::Null => return Ok((false, "T_operating not evidenced (no quantity record)".into())),
        Value::Dict(d) => d,
        other => {
            return Ok((
                false,
                format!(
                    "T_operating must be a quantity record {}, got {}",
                    list_repr(&T_OPERATING_FIELDS),
                    other.type_name()
                ),
            ))
        }
    };
    let miss: Vec<&str> = T_OPERATING_FIELDS
        .iter()
        .copied()
        .filter(|k| match d.get(k) {
            None | Some(Value::Null) => true,
            Some(v) => py_eq(v, &Value::str("")),
        })
        .collect();
    if !miss.is_empty() {
        return Ok((false, format!("T_operating record lacks {}", list_repr(&miss))));
    }
    let unit = d.get("unit_si").expect("checked");
    if !py_eq(unit, &Value::str("K")) {
        return Ok((false, format!("T_operating unit {} is not K (no silent conversion)", py_repr(unit))));
    }
    let v = d.get("value_si").expect("checked");
    if !finite_number(v)? || num(v) <= 0.0 {
        return Ok((false, format!("T_operating value {} is not a finite absolute temperature", py_repr(v))));
    }
    let ec = d.get("evidence_class").expect("checked");
    if !in_strs(ec, &T_OPERATING_EVIDENCE_CLASSES) {
        return Ok((
            false,
            format!("T_operating evidence class {} not in {}", py_repr(ec), tuple_repr(&T_OPERATING_EVIDENCE_CLASSES)),
        ));
    }
    Ok((true, String::new()))
}

/// Canonical sha256 of a validation-stage record (sorted keys, compact separators, UTF-8).
pub fn stage_record_sha256(rec: &Value) -> PyResult<String> {
    Ok(abep_provenance::sha256_hex(dumps(rec, &DumpOptions::canonical_hash())?.as_bytes()))
}

/// A refusal of `p4_a9_16_rules.validation_stage_record` (`RuleRefusal`): its fail-closed code and message.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuleRefusal {
    pub code: &'static str,
    pub message: String,
}

fn refusal(code: &'static str, message: impl Into<String>) -> RuleRefusal {
    RuleRefusal { code, message: message.into() }
}

/// `_filled`: None, empty / whitespace and TBD / PENDING / NOT_ / OPEN strings are not filled.
fn filled(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Str(s) => {
            let t = py_strip(s);
            let up = py_upper(t);
            !t.is_empty() && !["TBD", "PENDING", "NOT_", "OPEN"].iter().any(|p| up.starts_with(p))
        }
        _ => true,
    }
}

fn missing(rec: &Value, fields: &[&'static str]) -> Vec<&'static str> {
    match rec {
        Value::Dict(_) => fields.iter().copied().filter(|f| !filled(get(rec, f))).collect(),
        _ => fields.to_vec(),
    }
}

fn rule_num(v: &Value, ctx: &str) -> Result<f64, RuleRefusal> {
    let ok = match v {
        Value::Int(i) => i.to_f64().map(|x| x.is_finite()).unwrap_or(false),
        Value::Float(x) => x.is_finite(),
        _ => false,
    };
    if !ok {
        return Err(refusal(INCOMPLETE, format!("{ctx}: not a finite real number ({})", py_repr(v))));
    }
    Ok(num(v))
}

/// `p4_a9_16_rules.validation_stage_record(rec)`: classify one continuous-use-temperature evidence record.
/// `Ok(Err(refusal))` is a `RuleRefusal`; `Err` is any other Python exception (`AttributeError` on a non-mapping
/// stage-1 `conditions`).
pub fn validation_stage_record(rec: &Value) -> PyResult<Result<Value, RuleRefusal>> {
    if !matches!(rec, Value::Dict(_)) {
        return Ok(Err(refusal(INCOMPLETE, "no evidence record")));
    }
    let basis = get(rec, "basis");
    if in_strs(basis, &NON_VALIDATION_BASES) {
        return Ok(Err(refusal(
            "NOT_CONTINUOUS_USE_VALIDATION",
            format!("{} is never continuous-use validation", py_str(basis)),
        )));
    }
    let Some(stage_ix) = STAGES.iter().position(|s| py_eq(basis, &Value::str(*s))) else {
        return Ok(Err(refusal(INCOMPLETE, format!("unknown evidence basis {}", py_repr(basis)))));
    };
    let b = STAGES[stage_ix];
    let miss = missing(rec, &["material", "source", "preregistered_acceptance"]);
    if !miss.is_empty() {
        let code = if miss.contains(&"preregistered_acceptance") {
            "NOT_EVALUATED_ACCEPTANCE_NOT_PREREGISTERED"
        } else {
            INCOMPLETE
        };
        return Ok(Err(refusal(code, format!("{b}: missing {}", list_repr(&miss)))));
    }
    let t = match rule_num(get(rec, "T_limit_K"), &format!("{b} T_limit_K")) {
        Ok(t) => t,
        Err(r) => return Ok(Err(r)),
    };
    if t <= 0.0 {
        return Ok(Err(refusal(INCOMPLETE, "T_limit_K must be an absolute temperature")));
    }
    if !matches!(get(rec, "criteria_met"), Value::Bool(true)) {
        return Ok(Err(refusal(
            "NOT_EVALUATED_CRITERIA_NOT_MET",
            format!("{b}: the pre-registered criteria are not shown met"),
        )));
    }
    let material = get(rec, "material");
    match stage_ix {
        0 => {
            let cond = get(rec, "conditions");
            let cond_get = |c: &str| -> PyResult<Value> {
                if !cond.truthy() {
                    return Ok(Value::Null);
                }
                match cond {
                    Value::Dict(d) => Ok(d.get(c).cloned().unwrap_or(Value::Null)),
                    other => Err(pymath::err(
                        "AttributeError",
                        format!("'{}' object has no attribute 'get'", other.type_name()),
                    )),
                }
            };
            let mut cmiss = Vec::new();
            for c in STAGE_1_CONDITIONS {
                let v = cond_get(c)?;
                let ok = filled(&v) || (c == "thermal_cycling" && py_eq(&cond_get(c)?, &Value::str("NOT_APPLICABLE")));
                if !ok {
                    cmiss.push(c);
                }
            }
            let mmiss = missing(get(rec, "metrics"), &STAGE_1_METRICS);
            if !cmiss.is_empty() || !mmiss.is_empty() {
                return Ok(Err(refusal("NOT_EVALUATED_STAGE_1_CONDITIONS_TBD", "conditions / metrics not registered")));
            }
            let pre = match rule_num(get(rec, "preregistered_exposure_duration_h"), "pre-registered exposure duration")
            {
                Ok(x) => x,
                Err(r) => return Ok(Err(r)),
            };
            let got = match rule_num(get(rec, "exposure_duration_h"), "exposure duration") {
                Ok(x) => x,
                Err(r) => return Ok(Err(r)),
            };
            if pre <= 0.0 || got < pre {
                return Ok(Err(refusal("NOT_CONTINUOUS_USE_VALIDATION", "a brief coupon test")));
            }
        }
        1 => {
            let s1 = get(rec, "stage_1_record");
            if !matches!(s1, Value::Dict(_)) || !py_eq(get(s1, "stage"), &Value::str(STAGE_1)) {
                return Ok(Err(refusal(
                    "NOT_EVALUATED_STAGE_1_MISSING",
                    "stage 2 confirms a down-selected stage-1 material",
                )));
            }
            if !py_eq(get(s1, "material"), material) {
                return Ok(Err(refusal(INCOMPLETE, "stage-1 record is for a different material")));
            }
            if !matches!(get(rec, "down_selected"), Value::Bool(true)) {
                return Ok(Err(refusal(
                    "NOT_EVALUATED_NOT_DOWN_SELECTED",
                    "stage 2 is for the down-selected material only",
                )));
            }
            if !in_strs(get(rec, "configuration"), &["REPLACEABLE_ANODE", "REPLACEABLE_COLLECTOR"])
                || !in_strs(get(rec, "article"), &["H-1", "H-1/ICP"])
            {
                return Ok(Err(refusal(INCOMPLETE, "stage 2 needs a replaceable anode / collector configuration")));
            }
            let emiss = missing(get(rec, "environment"), &STAGE_2_ENVIRONMENT);
            if !emiss.is_empty() || !matches!(get(rec, "at_intended_continuous_use_condition"), Value::Bool(true)) {
                return Ok(Err(refusal(INCOMPLETE, "stage 2 environment / intended continuous-use condition")));
            }
        }
        _ => {
            let s2 = get(rec, "stage_2_record");
            if !matches!(s2, Value::Dict(_))
                || !py_eq(get(s2, "stage"), &Value::str(STAGE_2))
                || !py_eq(get(s2, "material"), material)
            {
                return Ok(Err(refusal("NOT_EVALUATED_STAGE_2_MISSING", "stage 3 follows stage-2 confirmation")));
            }
            let lb = get(rec, "life_basis");
            if !in_strs(lb, &["FULL_DURATION", "JUSTIFIED_ACCELERATED"])
                || (py_eq(lb, &Value::str("JUSTIFIED_ACCELERATED")) && !filled(get(rec, "justification")))
            {
                return Ok(Err(refusal(
                    INCOMPLETE,
                    "stage 3 needs full-duration or justified accelerated-life evidence",
                )));
            }
        }
    }
    let mut d = abep_types::pyjson::Dict::new();
    d.insert("stage", Value::str(b));
    d.insert("material", material.clone());
    d.insert("limit_class", Value::str(STAGE_RESULT[stage_ix]));
    d.insert("T_limit_K", Value::Float(t));
    let usable: Vec<Value> = LIMIT_USES
        .iter()
        .filter(|(_, need)| STAGES.iter().position(|s| s == need).expect("stage") <= stage_ix)
        .map(|(u, _)| Value::str(*u))
        .collect();
    d.insert("usable_for", Value::List(usable));
    Ok(Ok(Value::Dict(d)))
}

/// `t_validated_stage_refusal(prop)`: `None` when the property is backed by a classified stage-2 / stage-3 record.
fn t_validated_stage_refusal(prop: &Value) -> PyResult<Option<String>> {
    let id = py_str(at(prop, "id")?);
    let miss: Vec<&str> = T_VALIDATED_RECORD_KEYS.iter().copied().filter(|k| !get(prop, k).truthy()).collect();
    if !miss.is_empty() {
        return Ok(Some(format!(
            "property {id}: no validation-stage record reference ({} missing) - a declared validation_stage {} alone \
             is not evidence (A9.12 P4-OQ-01)",
            miss.join(", "),
            py_repr(get(prop, "validation_stage"))
        )));
    }
    let rec = at(prop, "validation_stage_record")?;
    let sha_ok = match rec {
        Value::Dict(_) => py_eq(&Value::str(stage_record_sha256(rec)?), at(prop, "validation_stage_record_sha256")?),
        _ => false,
    };
    if !sha_ok {
        return Ok(Some(format!("property {id}: validation-stage record sha256 does not match the referenced record")));
    }
    let rid = py_str(at(prop, "validation_stage_record_id")?);
    let c = match validation_stage_record(rec)? {
        Ok(c) => c,
        Err(r) => return Ok(Some(format!("property {id}: validation-stage record {rid} refused ({})", r.code))),
    };
    let stage = get(&c, "stage").clone();
    if !in_strs(&stage, &T_VALIDATED_GATE_STAGES) {
        return Ok(Some(format!(
            "property {id}: record {rid} classifies as {} - only stage 2 (integrated replaceable-component \
             confirmation) or later gives T_validated,continuous (A9.12 P4-OQ-01); stage 1 is screening only",
            py_str(&stage)
        )));
    }
    if !py_eq(get(prop, "validation_stage"), &stage) {
        return Ok(Some(format!(
            "property {id}: declared stage {} != record stage {}",
            py_repr(get(prop, "validation_stage")),
            py_str(&stage)
        )));
    }
    let pm = get(prop, "material");
    if !matches!(pm, Value::Null) && !py_eq(pm, get(&c, "material")) {
        return Ok(Some(format!(
            "property {id}: material {} != stage-record material {}",
            py_repr(pm),
            py_repr(get(&c, "material"))
        )));
    }
    let v = at(prop, "value_si")?;
    let lim = get(&c, "T_limit_K");
    if !py_eq(v, lim) {
        return Ok(Some(format!("property {id}: value {} K != stage-record limit {} K", py_str(v), py_str(lim))));
    }
    Ok(None)
}

fn pair(outcome: &str, reason: impl Into<String>) -> Value {
    Value::List(vec![Value::str(outcome), Value::str(reason.into())])
}

/// `evaluate_gate(req, prop, thermal_closure_status, operating_temperature)` -> [outcome, reason].
///
/// kind 'min': property >= requirement; 'max': property <= requirement; 'min_with_margin': T_operating <=
/// property - requirement (requirement = margin in K), only with a resolved thermal closure.
pub fn evaluate_gate(
    req: &Value,
    prop: &Value,
    thermal_closure_status: &Value,
    operating_temperature: &Value,
) -> PyResult<Value> {
    require(req, &REQUIREMENT_FIELDS, "requirement")?;
    if matches!(prop, Value::Null) {
        return Ok(pair(INCOMPLETE, "property value missing (no record)"));
    }
    require(prop, &PROPERTY_FIELDS, "property")?;
    let rid = py_str(at(req, "id")?);
    if !py_eq(at(prop, "property")?, at(req, "property")?) {
        return Err(screening(format!(
            "gate {rid}: property {} does not match the requirement",
            py_str(at(prop, "property")?)
        )));
    }
    if !requirement_evidenced(req)? {
        return Ok(pair(
            INCOMPLETE,
            format!("requirement {rid} not evidenced (status {})", py_str(at(req, "status")?)),
        ));
    }
    let pid = py_str(at(prop, "id")?);
    if !property_evidenced(prop)? {
        return Ok(pair(INCOMPLETE, format!("property {pid} not admissible/evidenced for a gate")));
    }
    if !py_eq(at(req, "unit")?, at(prop, "unit_si")?) {
        return Err(screening(format!(
            "gate {rid}: unit {} != property unit {} (no silent conversion)",
            py_repr(at(req, "unit")?),
            py_repr(at(prop, "unit_si")?)
        )));
    }
    let rdom = check_domain(at(req, "domain")?, &format!("requirement {rid}"))?;
    let pdom = check_domain(at(prop, "domain")?, &format!("property {pid}"))?;
    if !rdom.is_subset(&pdom) {
        return Ok(pair(
            "OUT_OF_DOMAIN",
            format!(
                "property domain {} does not cover requirement domain {}",
                sorted_repr(at(prop, "domain")?),
                sorted_repr(at(req, "domain")?)
            ),
        ));
    }
    let is_tv = py_eq(at(prop, "property")?, &Value::str(T_VALIDATED_PROPERTY));
    if is_tv && !in_strs(get(prop, "validation_stage"), &T_VALIDATED_GATE_STAGES) {
        return Ok(pair(
            INCOMPLETE,
            format!(
                "property {pid}: validation stage {} - only stage 2 (integrated replaceable-component confirmation) or \
                 later gives T_validated,continuous (A9.12 P4-OQ-01); stage 1 is screening only",
                py_repr(get(prop, "validation_stage"))
            ),
        ));
    }
    if is_tv {
        if let Some(why) = t_validated_stage_refusal(prop)? {
            return Ok(pair(INCOMPLETE, why));
        }
    }
    let kind = at(req, "kind")?;
    let pv = num(at(prop, "value_si")?);
    let rv = num(at(req, "value")?);
    let ok = if py_eq(kind, &Value::str("min_with_margin")) {
        if matches!(thermal_closure_status, Value::Null) {
            return Err(screening(format!("gate {rid}: thermal closure status must be supplied (no default)")));
        }
        if !in_strs(thermal_closure_status, &RESOLVED_THERMAL_STATUSES) {
            return Ok(pair(
                INCOMPLETE,
                format!(
                    "thermal closure {} not in {}: T_operating not evidenced",
                    py_repr(thermal_closure_status),
                    tuple_repr(&RESOLVED_THERMAL_STATUSES)
                ),
            ));
        }
        let (ok_t, why_t) = operating_temperature_evidenced(operating_temperature)?;
        if !ok_t {
            return Ok(pair(INCOMPLETE, why_t));
        }
        num(at(operating_temperature, "value_si")?) <= pv - rv
    } else if py_eq(kind, &Value::str("min")) {
        pv >= rv
    } else {
        pv <= rv
    };
    if ok {
        return Ok(pair("GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN", "both sides evidenced; not a selection"));
    }
    Ok(pair("GATE_VIOLATED_BY_EVIDENCE", "both sides evidenced; gate violated"))
}

/// `candidate_screening_state(outcomes)`: violated -> SCREENED_OUT_BY_EVIDENCE; any other non-satisfied (or none)
/// -> INCOMPLETE_EVIDENCE; else NOT_SCREENED_OUT. Never PASS / SELECTED.
pub fn candidate_screening_state(outcomes: &[Value]) -> PyResult<&'static str> {
    for o in outcomes {
        if !in_strs(o, &GATE_OUTCOMES) {
            return Err(screening(format!("unknown gate outcome {}", py_repr(o))));
        }
    }
    if outcomes.is_empty() {
        return Ok(INCOMPLETE);
    }
    if outcomes.iter().any(|o| py_eq(o, &Value::str("GATE_VIOLATED_BY_EVIDENCE"))) {
        return Ok("SCREENED_OUT_BY_EVIDENCE");
    }
    if outcomes.iter().any(|o| !py_eq(o, &Value::str("GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN"))) {
        return Ok(INCOMPLETE);
    }
    Ok("NOT_SCREENED_OUT")
}

/// `final_material_status(states)`: OPEN for every input (A9.2, A9.6 fixed statuses; owner row 106).
pub fn final_material_status(_screening_states: &Value) -> &'static str {
    FINAL_MATERIAL_STATUS
}
