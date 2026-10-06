//! A9 requirement-verification matrix: the status-assignment rules (`docs/requirements/rvm_a9/rvm_rules.py`, A9.6
//! sec. 15; contract PARITY-C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE-V1 R1-R6) and the RVM-derived evidence-gate
//! snapshot (`design_gates.rvm_gate_snapshot`, contract E13), over the committed, sha256-pinned record.
//!
//! Implementation completeness is never compliance: PASS needs a verified, measured, in-domain determining measurement
//! that meets and covers the requirement with a frozen requirement basis.

use crate::error::{AssessError, AssessResult};
use crate::py::{as_list, dget, dict, eq_str, get, in_strs, s, strs};
use abep_provenance::sha256_hex;
use abep_types::pyjson::{loads, py_repr, py_repr_tuple, py_str, read_text_utf8, Dict, Value};
use std::path::Path;

pub const RVM_REL: &str = "docs/requirements/rvm_a9/rvm_a9_v1.json";
pub const RVM_SHA256: &str = "f91a00b40e24a66ceec8fd16dba3ad5ecb249ae186cc39bf717efe083223a5c4";
pub const FLIGHT_CONFIGURATIONS: [&str; 1] = ["hall_icp_neutralizer"];
pub const GROUND_REFERENCE_CONFIGURATIONS: [&str; 1] = ["hall_c1_reference"];

pub const STATUSES: [&str; 6] =
    ["PASS", "FAIL", "NOT_EVALUATED", "OUT_OF_DOMAIN", "INCOMPLETE_EVIDENCE", "NUMERICAL_FAILURE"];
pub const ROLES: [&str; 3] = ["DETERMINING", "SUPPORTING", "CONTEXT"];
pub const ARTIFACT_KINDS: [&str; 9] = [
    "MEASUREMENT",
    "VALIDATED_ANALYSIS",
    "BUDGET_EVALUATION",
    "FRAMEWORK_EVALUATION",
    "PLAN_OR_FRAMEWORK",
    "PUBLISHED_ANALOG",
    "PROCUREMENT",
    "VERIFICATION_ARTIFACT_ABSENT",
    "NOT_APPLICABLE_GROUND_REFERENCE",
];
pub const NOT_APPLICABLE_KIND: &str = "NOT_APPLICABLE_GROUND_REFERENCE";
pub const EVALUATING_KINDS: [&str; 4] =
    ["MEASUREMENT", "VALIDATED_ANALYSIS", "BUDGET_EVALUATION", "FRAMEWORK_EVALUATION"];

/// Field type of ARTIFACT_FIELDS.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FieldType {
    Str,
    Bool,
    OptBool,
    NonNegInt,
}

impl FieldType {
    pub fn name(self) -> &'static str {
        match self {
            FieldType::Str => "str",
            FieldType::Bool => "bool",
            FieldType::OptBool => "(bool, NoneType)",
            FieldType::NonNegInt => "int",
        }
    }
}

pub const ARTIFACT_FIELDS: [(&str, FieldType); 16] = [
    ("path", FieldType::Str),
    ("id", FieldType::Str),
    ("role", FieldType::Str),
    ("kind", FieldType::Str),
    ("evidence_state", FieldType::Str),
    ("evaluated", FieldType::Bool),
    ("verified", FieldType::Bool),
    ("measured", FieldType::Bool),
    ("synthetic", FieldType::Bool),
    ("in_domain", FieldType::OptBool),
    ("meets", FieldType::OptBool),
    ("coverage_complete", FieldType::Bool),
    ("evidenced_terms", FieldType::NonNegInt),
    ("numerical_failure", FieldType::Bool),
    ("lower_bound_verified", FieldType::Bool),
    ("exceeds_limit_every_reading", FieldType::OptBool),
];

pub const RULES: [(&str, &str); 10] = [
    ("R0-SYNTHETIC", "synthetic evidence is refused (raises); synthetic and measured evidence are never mixed"),
    (
        "R1-NUMERICAL",
        "a determining evaluation reports non-convergence and no verified measurement exists -> NUMERICAL_FAILURE",
    ),
    ("R2-FAIL-MEASURED", "a verified, measured, in-domain determining measurement violates the requirement -> FAIL"),
    (
        "R3-PASS",
        "every verified, measured, in-domain determining measurement meets the requirement, at least one covers it \
         completely, and the requirement basis is frozen -> PASS",
    ),
    (
        "R3b-BASIS-NOT-FROZEN",
        "measurements would pass but the requirement basis is not frozen (official RFP not obtained, owner rows 1-3) \
         -> INCOMPLETE_EVIDENCE",
    ),
    ("R3c-COVERAGE", "verified measurements exist but none covers the requirement completely -> INCOMPLETE_EVIDENCE"),
    (
        "R4-FAIL-FLOOR",
        "a determining budget evaluation whose floor is a VERIFIED lower bound exceeds the limit under EVERY \
         admissible open reading -> FAIL",
    ),
    (
        "R5-OUT-OF-DOMAIN",
        "determining evaluations exist and every one lies outside its applicability domain -> OUT_OF_DOMAIN",
    ),
    (
        "R6-INCOMPLETE",
        "a determining evaluation was run in domain with at least one evidenced (non-allocation, non-TBD) term but \
         cannot conclude -> INCOMPLETE_EVIDENCE",
    ),
    (
        "R7-NOT-EVALUATED",
        "no determining evaluation with evidenced terms exists (plans, frameworks, allocations, analogs or \
         unavailable analyses only) -> NOT_EVALUATED",
    ),
];

fn rvm_error(message: impl Into<String>) -> AssessError {
    AssessError::new("RvmError", message)
}

fn tuple(xs: &[&str]) -> String {
    py_repr_tuple(&xs.iter().map(|x| s(*x)).collect::<Vec<_>>())
}

fn field_ok(v: &Value, t: FieldType) -> bool {
    match t {
        FieldType::Str => matches!(v, Value::Str(_)),
        FieldType::Bool => matches!(v, Value::Bool(_)),
        FieldType::OptBool => matches!(v, Value::Bool(_) | Value::Null),
        FieldType::NonNegInt => matches!(v, Value::Int(i) if !i.is_negative()),
    }
}

fn b(a: &Value, k: &str) -> bool {
    matches!(dget(a, k), Ok(Value::Bool(true)))
}

fn is_false(a: &Value, k: &str) -> bool {
    matches!(dget(a, k), Ok(Value::Bool(false)))
}

/// `validate_artifact(a)`: returns the artifact unchanged or refuses (RvmError).
pub fn validate_artifact(a: &Value) -> AssessResult<Value> {
    let d = match a {
        Value::Dict(d) => d,
        other => return Err(rvm_error(format!("artifact must be a dict, got {}", other.type_name()))),
    };
    let id_or = |dflt: &str| d.get("id").map_or(dflt.to_string(), py_str);
    for (k, t) in ARTIFACT_FIELDS {
        let Some(v) = d.get(k) else {
            return Err(rvm_error(format!("artifact {}: missing field {} (no default)", id_or("?"), py_repr(&s(k)))));
        };
        if !field_ok(v, t) {
            return Err(if t == FieldType::NonNegInt {
                rvm_error(format!("artifact {}: {k} must be a non-negative int", id_or("None")))
            } else {
                rvm_error(format!("artifact {}: {k} has type {}", id_or("None"), v.type_name()))
            });
        }
    }
    let id = py_str(get(a, "id")?);
    if !get(a, "path")?.truthy() || !get(a, "id")?.truthy() {
        return Err(rvm_error("artifact path and id must be non-empty"));
    }
    let role = get(a, "role")?;
    if !in_strs(role, &ROLES) {
        return Err(rvm_error(format!("artifact {id}: role {} not in {}", py_repr(role), tuple(&ROLES))));
    }
    let kind = get(a, "kind")?;
    if !in_strs(kind, &ARTIFACT_KINDS) {
        return Err(rvm_error(format!("artifact {id}: kind {} not in {}", py_repr(kind), tuple(&ARTIFACT_KINDS))));
    }
    let is_meas = eq_str(kind, "MEASUREMENT");
    let is_budget = eq_str(kind, "BUDGET_EVALUATION");
    if b(a, "synthetic") {
        return Err(rvm_error(format!("artifact {id}: synthetic evidence refused (R0-SYNTHETIC)")));
    }
    if b(a, "measured") && !is_meas {
        return Err(rvm_error(format!("artifact {id}: measured=True only for kind MEASUREMENT")));
    }
    if is_meas && !b(a, "measured") {
        return Err(rvm_error(format!("artifact {id}: kind MEASUREMENT requires measured=True")));
    }
    if b(a, "evaluated") && !in_strs(kind, &EVALUATING_KINDS) {
        return Err(rvm_error(format!("artifact {id}: kind {} cannot be an evaluation", py_str(kind))));
    }
    if !matches!(get(a, "meets")?, Value::Null) && !b(a, "evaluated") {
        return Err(rvm_error(format!("artifact {id}: meets set on an artifact that evaluated nothing")));
    }
    if !is_meas && b(a, "meets") {
        return Err(rvm_error(format!(
            "artifact {id}: only a measurement can meet a requirement (implementation completeness is never \
             compliance)"
        )));
    }
    if b(a, "lower_bound_verified") && !is_budget {
        return Err(rvm_error(format!("artifact {id}: lower_bound_verified applies to BUDGET_EVALUATION only")));
    }
    if !matches!(get(a, "exceeds_limit_every_reading")?, Value::Null) && !is_budget {
        return Err(rvm_error(format!("artifact {id}: exceeds_limit_every_reading applies to BUDGET_EVALUATION only")));
    }
    Ok(a.clone())
}

fn ids(xs: &[&Value]) -> String {
    xs.iter().map(|a| py_str(&dget(a, "id").unwrap_or(Value::Null))).collect::<Vec<_>>().join(", ")
}

/// `assign_status(artifacts, requirement_frozen)` -> (status, rule_id, reason).
pub fn assign_status(artifacts: &[Value], requirement_frozen: &Value) -> AssessResult<(String, String, String)> {
    let frozen = match requirement_frozen {
        Value::Bool(x) => *x,
        _ => return Err(rvm_error("requirement_frozen must be bool")),
    };
    if artifacts.is_empty() {
        return Err(rvm_error("no artifacts: every row/configuration needs at least one determining artifact"));
    }
    for a in artifacts {
        validate_artifact(a)?;
    }
    let na = artifacts.iter().filter(|a| eq_str(&dget(a, "kind").unwrap_or(Value::Null), NOT_APPLICABLE_KIND)).count();
    if na > 0 && na != artifacts.len() {
        return Err(rvm_error("a NOT_APPLICABLE_GROUND_REFERENCE marker is never mixed with evidence artifacts"));
    }
    let det: Vec<&Value> =
        artifacts.iter().filter(|a| eq_str(&dget(a, "role").unwrap_or(Value::Null), "DETERMINING")).collect();
    if det.is_empty() {
        return Err(rvm_error("no DETERMINING artifact (a row must name what would verify it)"));
    }
    let kind_is = |a: &Value, k: &str| eq_str(&dget(a, "kind").unwrap_or(Value::Null), k);
    let meas: Vec<&Value> = det
        .iter()
        .copied()
        .filter(|a| kind_is(a, "MEASUREMENT") && b(a, "evaluated") && b(a, "verified") && b(a, "in_domain"))
        .collect();
    let num: Vec<&Value> = det.iter().copied().filter(|a| b(a, "evaluated") && b(a, "numerical_failure")).collect();
    let r = |st: &str, rule: &str, reason: String| Ok((st.to_string(), rule.to_string(), reason));
    if !num.is_empty() && meas.is_empty() {
        return r("NUMERICAL_FAILURE", "R1-NUMERICAL", format!("non-converged evaluation: {}", ids(&num)));
    }
    if !meas.is_empty() {
        let bad: Vec<&Value> = meas.iter().copied().filter(|a| is_false(a, "meets")).collect();
        if !bad.is_empty() {
            return r(
                "FAIL",
                "R2-FAIL-MEASURED",
                format!("verified measurement violates the requirement: {}", ids(&bad)),
            );
        }
        if meas.iter().all(|a| b(a, "meets")) && meas.iter().any(|a| b(a, "coverage_complete")) {
            if frozen {
                return r(
                    "PASS",
                    "R3-PASS",
                    format!("verified measurement meets and covers the requirement: {}", ids(&meas)),
                );
            }
            return r(
                "INCOMPLETE_EVIDENCE",
                "R3b-BASIS-NOT-FROZEN",
                "measurements meet the recorded requirement but its basis is not frozen".into(),
            );
        }
        return r(
            "INCOMPLETE_EVIDENCE",
            "R3c-COVERAGE",
            "verified measurements exist but do not cover the requirement completely".into(),
        );
    }
    let floor: Vec<&Value> = det
        .iter()
        .copied()
        .filter(|a| {
            kind_is(a, "BUDGET_EVALUATION")
                && b(a, "evaluated")
                && b(a, "lower_bound_verified")
                && b(a, "exceeds_limit_every_reading")
        })
        .collect();
    if !floor.is_empty() {
        return r(
            "FAIL",
            "R4-FAIL-FLOOR",
            format!("verified lower bound exceeds the limit under every admissible reading: {}", ids(&floor)),
        );
    }
    let evals: Vec<&Value> = det.iter().copied().filter(|a| b(a, "evaluated")).collect();
    if !evals.is_empty() && evals.iter().all(|a| is_false(a, "in_domain")) {
        return r(
            "OUT_OF_DOMAIN",
            "R5-OUT-OF-DOMAIN",
            format!("every determining evaluation is outside its domain: {}", ids(&evals)),
        );
    }
    let terms = |a: &Value| match dget(a, "evidenced_terms") {
        Ok(Value::Int(i)) => i.to_string(),
        _ => "0".into(),
    };
    let partial: Vec<&Value> = evals.iter().copied().filter(|a| !is_false(a, "in_domain") && terms(a) != "0").collect();
    if !partial.is_empty() {
        let txt = partial
            .iter()
            .map(|a| format!("{} ({} evidenced term(s))", py_str(&dget(a, "id").unwrap_or(Value::Null)), terms(a)))
            .collect::<Vec<_>>()
            .join(", ");
        return r(
            "INCOMPLETE_EVIDENCE",
            "R6-INCOMPLETE",
            format!("evaluation run with evidenced terms but inconclusive: {txt}"),
        );
    }
    let txt = det
        .iter()
        .map(|a| {
            format!(
                "{} [{}]",
                py_str(&dget(a, "id").unwrap_or(Value::Null)),
                py_str(&dget(a, "kind").unwrap_or(Value::Null))
            )
        })
        .collect::<Vec<_>>()
        .join(", ");
    r("NOT_EVALUATED", "R7-NOT-EVALUATED", format!("no determining evaluation with evidenced terms: {txt}"))
}

/// `is_not_applicable_cell(artifacts)`.
pub fn is_not_applicable_cell(artifacts: &[Value]) -> AssessResult<bool> {
    if artifacts.is_empty() {
        return Ok(false);
    }
    for a in artifacts {
        if !eq_str(get(a, "kind")?, NOT_APPLICABLE_KIND) {
            return Ok(false);
        }
    }
    Ok(true)
}

/// `floor_fail_check(readings, limit, strict)`.
pub fn floor_fail_check(readings: &[Value], limit: f64, strict: bool) -> AssessResult<Value> {
    if readings.is_empty() {
        return Err(rvm_error("floor_fail_check: no readings"));
    }
    let mut vals = Vec::new();
    for r in readings {
        let v = get(r, "floor_only_kg")?;
        let ok = match v {
            Value::Int(_) => true,
            Value::Float(f) => f.is_finite(),
            _ => false,
        };
        if !ok {
            return Err(rvm_error(format!("floor_fail_check: bad value in reading {}", py_str(&dget(r, "reading")?))));
        }
        vals.push(v.to_f64()?);
    }
    let n_exc = vals.iter().filter(|v| if strict { **v >= limit } else { **v > limit }).count();
    let mut mn = vals[0];
    let mut mx = vals[0];
    for v in &vals[1..] {
        if *v < mn {
            mn = *v;
        }
        if *v > mx {
            mx = *v;
        }
    }
    Ok(dict(vec![
        ("exceeds_every_reading", Value::Bool(n_exc == vals.len())),
        ("n_readings", Value::int(vals.len() as i64)),
        ("n_exceeding", Value::int(n_exc as i64)),
        ("min_floor_kg", Value::Float(abep_atmos::pyfloat::py_round6(mn))),
        ("max_floor_kg", Value::Float(abep_atmos::pyfloat::py_round6(mx))),
    ]))
}

fn rows(doc: &Value) -> AssessResult<&[Value]> {
    as_list(get(doc, "rows")?)
}

fn cells(row: &Value) -> AssessResult<&Dict> {
    get(row, "configurations")?.as_dict().ok_or_else(|| AssessError::new("AttributeError", "configurations"))
}

/// `assert_status_vocabulary(doc)`.
pub fn assert_status_vocabulary(doc: &Value) -> AssessResult<()> {
    let v = as_list(get(doc, "status_vocabulary")?)?;
    if v.len() != STATUSES.len() || !v.iter().zip(STATUSES).all(|(x, y)| eq_str(x, y)) {
        return Err(rvm_error("status vocabulary differs from the six A9.6 states"));
    }
    for row in rows(doc)? {
        for (cfg, cell) in cells(row)?.iter() {
            let st = get(cell, "status")?;
            if !in_strs(st, &STATUSES) {
                return Err(rvm_error(format!(
                    "{}/{cfg}: status {} not allowed",
                    py_str(get(row, "id")?),
                    py_repr(st)
                )));
            }
        }
    }
    Ok(())
}

/// `assert_no_pass_without_measurement(doc)`.
pub fn assert_no_pass_without_measurement(doc: &Value) -> AssessResult<()> {
    for row in rows(doc)? {
        for (cfg, cell) in cells(row)?.iter() {
            if !eq_str(get(cell, "status")?, "PASS") {
                continue;
            }
            let mut ok = false;
            for a in as_list(get(cell, "artifacts")?)? {
                if eq_str(get(a, "role")?, "DETERMINING")
                    && eq_str(get(a, "kind")?, "MEASUREMENT")
                    && get(a, "measured")?.truthy()
                    && get(a, "verified")?.truthy()
                    && get(a, "evaluated")?.truthy()
                    && matches!(get(a, "meets")?, Value::Bool(true))
                    && !get(a, "synthetic")?.truthy()
                {
                    ok = true;
                }
            }
            if !ok {
                return Err(rvm_error(format!(
                    "{}/{cfg}: PASS without a cited verified measurement artifact",
                    py_str(get(row, "id")?)
                )));
            }
        }
    }
    Ok(())
}

/// The committed RVM record, sha256-verified on load (a changed file is MODEL_ERROR, never read silently).
#[derive(Debug, Clone)]
pub struct RvmRecord {
    pub doc: Value,
    pub sha256: String,
}

impl RvmRecord {
    pub fn load(repo: &Path) -> AssessResult<Self> {
        Self::load_pinned(repo, RVM_SHA256)
    }

    pub fn load_pinned(repo: &Path, pin: &str) -> AssessResult<Self> {
        let bytes = std::fs::read(repo.join(RVM_REL))
            .map_err(|e| AssessError::new("MODEL_ERROR", format!("cannot read {RVM_REL}: {e}")))?;
        let sha = sha256_hex(&bytes);
        if sha != pin {
            return Err(AssessError::new(
                "MODEL_ERROR",
                format!(
                    "{RVM_REL} sha256 {sha} != pinned {pin} (committed RVM record; a changed record needs a new pin)"
                ),
            ));
        }
        Ok(RvmRecord { doc: loads(&read_text_utf8(&bytes)?)?, sha256: sha })
    }

    /// `rvm_gate_snapshot`: the flight configuration's RVM counts; the C1 column only as the labelled ground reference.
    pub fn gate_snapshot(&self) -> AssessResult<Value> {
        let counts = get(&self.doc, "status_counts")?;
        let mut flight = Dict::new();
        for c in FLIGHT_CONFIGURATIONS {
            flight.insert(c, get(counts, c)?.clone());
        }
        let mut snap = vec![
            ("rvm_hall_status", get(&self.doc, "hall_status")?.clone()),
            ("rvm_status_counts", Value::Dict(flight)),
        ];
        let mut ground = Dict::new();
        for c in GROUND_REFERENCE_CONFIGURATIONS {
            if let Some(v) = counts.as_dict().and_then(|d| d.get(c)) {
                ground.insert(c, v.clone());
            }
        }
        if !ground.is_empty() {
            snap.push((
                "ground_reference_rvm_status_counts",
                dict(vec![
                    (
                        "label",
                        s("GROUND_ONLY_LAB_REFERENCE (A9.20): RVM cells of the C1 ground / laboratory reference; never \
                           a flight configuration (A9.19) and never flight compliance evidence"),
                    ),
                    ("counts", Value::Dict(ground)),
                ]),
            ));
        }
        Ok(dict(snap))
    }

    /// Replay of every committed cell: assign_status(artifacts without 'detail', requirement_frozen) per row x
    /// configuration, with the committed (status, rule, reason).
    pub fn replay_cells(&self) -> AssessResult<Vec<Value>> {
        let mut out = Vec::new();
        for row in rows(&self.doc)? {
            for (cfg, cell) in cells(row)?.iter() {
                let mut arts = Vec::new();
                for a in as_list(get(cell, "artifacts")?)? {
                    let mut d = a.as_dict().ok_or_else(|| AssessError::new("TypeError", "artifact"))?.clone();
                    d.remove("detail");
                    arts.push(Value::Dict(d));
                }
                let (st, rule, reason) = assign_status(&arts, get(row, "requirement_frozen")?)?;
                let same = eq_str(get(cell, "status")?, &st)
                    && eq_str(get(cell, "rule")?, &rule)
                    && eq_str(get(cell, "reason")?, &reason);
                out.push(dict(vec![
                    ("row", get(row, "id")?.clone()),
                    ("configuration", s(cfg.as_str())),
                    ("status", s(st)),
                    ("rule", s(rule)),
                    ("reason", s(reason)),
                    ("committed_status", get(cell, "status")?.clone()),
                    ("reproduces_committed", Value::Bool(same)),
                ]));
            }
        }
        Ok(out)
    }

    /// The committed GNG-ICP-01 gate record.
    pub fn gng_icp_01(&self) -> AssessResult<&Value> {
        for g in as_list(get(&self.doc, "owner_approved_gates")?)? {
            if eq_str(get(g, "id")?, "GNG-ICP-01") {
                return Ok(g);
            }
        }
        Err(AssessError::new("MODEL_ERROR", "GNG-ICP-01 not registered in the RVM"))
    }

    /// The preserved recorder proposal RP-A919-01 text (DIV-R01).
    pub fn proposal_text(&self) -> AssessResult<String> {
        let mut found = Vec::new();
        for p in as_list(get(&self.doc, "recorder_proposals_open_for_owner")?)? {
            if eq_str(get(p, "id")?, "RP-A919-01") {
                found.push(py_str(get(p, "proposal")?));
            }
        }
        match found.len() {
            1 => Ok(found.remove(0)),
            _ => Err(AssessError::new("IcpGateError", "RP-A919-01: recorder proposal not found exactly once")),
        }
    }

    /// The RVM row of a key (e.g. MASS_LT_40KG_WET).
    pub fn row_by_key(&self, key: &str) -> AssessResult<&Value> {
        rows(&self.doc)?
            .iter()
            .find(|r| eq_str(&dget(r, "key").unwrap_or(Value::Null), key))
            .ok_or_else(|| AssessError::new("MODEL_ERROR", format!("RVM row {key} not found")))
    }
}

/// The vocabularies and the rule table (R1), for parity and records.
pub fn vocabularies() -> Value {
    let mut fields = Dict::new();
    for (k, t) in ARTIFACT_FIELDS {
        fields.insert(k, s(t.name()));
    }
    let mut rules = Dict::new();
    for (k, v) in RULES {
        rules.insert(k, s(v));
    }
    dict(vec![
        ("STATUSES", strs(&STATUSES)),
        ("ROLES", strs(&ROLES)),
        ("ARTIFACT_KINDS", strs(&ARTIFACT_KINDS)),
        ("NOT_APPLICABLE_KIND", s(NOT_APPLICABLE_KIND)),
        ("EVALUATING_KINDS", strs(&EVALUATING_KINDS)),
        ("ARTIFACT_FIELDS", Value::Dict(fields)),
        ("RULES", Value::Dict(rules)),
    ])
}
