//! Owner-question state reader (`design_gates.owner_state`, `status_label`, `apply_to_questions`; contract E14): the
//! current answered status of an owner question from `owner_questions_state_v5.json` (sha256-pinned), never
//! fabricated. Design / physics code never reads this state; records receive the status text from here.

use crate::error::{AssessError, AssessResult};
use crate::py::{dget, dget_or, dict, eq_str, get, s};
use abep_provenance::sha256_hex;
use abep_types::pyjson::{loads, py_str, read_text_utf8, Value};
use std::path::Path;

pub const OQ5_REL: &str = "docs/budgets/owner_decisions/owner_questions_state_v5.json";
pub const OQ5_SHA256: &str = "8a29c4180f4387afb6168986442ddb1c08b1f9a692ad85cdf0630799de3cd4fd";
pub const TBD_OWNER: &str = "TBD_OWNER";

/// The owner-question state v5 rows, one per id (an answered row wins over a TBD_OWNER row of the same id).
#[derive(Debug, Clone)]
pub struct OwnerState {
    rows: Vec<(String, Value)>,
}

/// `re.search(r"decision code ([A-Z0-9_]+)", text)`.
fn find_code(text: &str) -> Option<String> {
    let pat = "decision code ";
    let mut from = 0;
    while let Some(i) = text[from..].find(pat) {
        let start = from + i + pat.len();
        let run: String =
            text[start..].chars().take_while(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || *c == '_').collect();
        if !run.is_empty() {
            return Some(run);
        }
        from = from + i + 1;
    }
    None
}

/// `re.search(r"\((A9\.\d+ S[\d.]+)", text)`.
fn find_decision(text: &str) -> Option<String> {
    let mut from = 0;
    while let Some(i) = text[from..].find("(A9.") {
        let start = from + i + 1;
        let rest = &text[start + 3..];
        let digits: String = rest.chars().take_while(char::is_ascii_digit).collect();
        if !digits.is_empty() {
            let after = &rest[digits.len()..];
            if let Some(tail) = after.strip_prefix(" S") {
                let run: String = tail.chars().take_while(|c| c.is_ascii_digit() || *c == '.').collect();
                if !run.is_empty() {
                    return Some(format!("A9.{digits} S{run}"));
                }
            }
        }
        from = from + i + 1;
    }
    None
}

impl OwnerState {
    pub fn load(repo: &Path) -> AssessResult<Self> {
        let bytes = std::fs::read(repo.join(OQ5_REL))
            .map_err(|e| AssessError::new("MODEL_ERROR", format!("cannot read {OQ5_REL}: {e}")))?;
        let sha = sha256_hex(&bytes);
        if sha != OQ5_SHA256 {
            return Err(AssessError::new("MODEL_ERROR", format!("{OQ5_REL} sha256 {sha} != pinned {OQ5_SHA256}")));
        }
        let doc = loads(&read_text_utf8(&bytes)?)?;
        let mut rows: Vec<(String, Value)> = Vec::new();
        for r in crate::py::as_list(get(&doc, "rows")?)? {
            let id = py_str(get(r, "id")?);
            let st = get(r, "status")?;
            match rows.iter_mut().find(|(k, _)| *k == id) {
                None => rows.push((id, r.clone())),
                Some((_, prev)) => {
                    if eq_str(get(prev, "status")?, TBD_OWNER) && !eq_str(st, TBD_OWNER) {
                        *prev = r.clone();
                    }
                }
            }
        }
        Ok(OwnerState { rows })
    }

    fn row(&self, qid: &Value) -> Option<&Value> {
        match qid {
            Value::Str(q) => self.rows.iter().find(|(k, _)| k == q).map(|(_, v)| v),
            _ => None,
        }
    }

    /// `owner_state(qid)`.
    pub fn owner_state(&self, qid: &Value) -> AssessResult<Value> {
        let q = py_str(qid);
        let r = self.row(qid);
        let tbd = match r {
            None => true,
            Some(r) => eq_str(get(r, "status")?, TBD_OWNER),
        };
        if tbd {
            let detail = match r {
                None => s(TBD_OWNER),
                Some(r) => dget_or(r, "status_detail", s(TBD_OWNER))?,
            };
            let source = format!("{OQ5_REL} rows[id={q}]{}", if r.is_some() { "" } else { " (absent)" });
            return Ok(dict(vec![
                ("id", qid.clone()),
                ("status", s(TBD_OWNER)),
                ("answered", Value::Bool(false)),
                ("decision", Value::Null),
                ("decision_code", Value::Null),
                ("status_detail", detail),
                ("source", s(source)),
            ]));
        }
        let r = r.expect("answered row");
        let sd = dget(r, "status_detail")?;
        let detail = if sd.truthy() { sd } else { get(r, "status")?.clone() };
        let text = py_str(&detail);
        Ok(dict(vec![
            ("id", qid.clone()),
            ("status", get(r, "status")?.clone()),
            ("answered", Value::Bool(true)),
            ("decision", find_decision(&text).map_or(Value::Null, s)),
            ("decision_code", find_code(&text).map_or(Value::Null, s)),
            ("status_detail", detail),
            ("source", s(format!("{OQ5_REL} rows[id={q}]"))),
        ]))
    }

    /// `status_label(qid)`: 'ANSWERED <decision> <code>' or 'TBD_OWNER'.
    pub fn status_label(&self, qid: &Value) -> AssessResult<String> {
        let st = self.owner_state(qid)?;
        if !get(&st, "answered")?.truthy() {
            return Ok(TBD_OWNER.into());
        }
        let mut parts = vec!["ANSWERED".to_string()];
        for k in ["decision", "decision_code"] {
            let v = get(&st, k)?;
            if v.truthy() {
                parts.push(py_str(v));
            }
        }
        Ok(parts.join(" "))
    }

    /// `apply_to_questions(questions)`: the as-raised status kept as history, the current v5 state applied.
    pub fn apply_to_questions(&self, questions: &[Value]) -> AssessResult<Value> {
        let mut out = Vec::new();
        for q in questions {
            let st = self.owner_state(get(q, "id")?)?;
            let mut d = crate::py::as_dict(q)?.clone();
            let answered = get(&st, "answered")?.truthy();
            d.insert("status_as_raised", dget_or(q, "status", s(TBD_OWNER))?);
            d.insert("status", if answered { get(&st, "status_detail")?.clone() } else { s(TBD_OWNER) });
            d.insert("owner_decision", get(&st, "decision")?.clone());
            d.insert("decision_code", get(&st, "decision_code")?.clone());
            d.insert("owner_state_source", get(&st, "source")?.clone());
            out.push(Value::Dict(d));
        }
        Ok(Value::List(out))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn regex_equivalents() {
        assert_eq!(find_code("x decision code AB_1 y").as_deref(), Some("AB_1"));
        assert_eq!(find_code("decision code ab decision code CD").as_deref(), Some("CD"));
        assert_eq!(find_code("no code"), None);
        assert_eq!(find_decision("ANSWERED (A9.13 S6.4) x").as_deref(), Some("A9.13 S6.4"));
        assert_eq!(find_decision("(A9. S1) (A9.14 S9.7.1)").as_deref(), Some("A9.14 S9.7.1"));
        assert_eq!(find_decision("(A9.13 X)"), None);
    }
}
