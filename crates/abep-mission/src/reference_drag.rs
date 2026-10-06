//! Reference spacecraft drag basis for INTERIM PARAMETRIC drag studies (owner decision A9.13 S6.18, OQ-F78-04):
//! `abep_sim/spacecraft_reference_drag.py` (PARITY-C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY-V1).
//!
//! A register of documented / public / official spacecraft and published ABEP reference geometry with the
//! drag-coefficient basis each source states, and the evaluator
//!
//! ```text
//! D = 0.5 rho v_rel^2 C_D A_ref        (Romano et al. 2018, arXiv:2103.02328v2, Eq. 1)
//! ```
//!
//! for a DECLARED reference case plus a caller-supplied intake term (F1 owns intake drag). Every result is
//! REFERENCE_PARAMETRIC_NOT_FLIGHT with freeze_status NOT_EVALUATED: not the host spacecraft, not an ICD, not an AG-13
//! closure. The register is `data/spacecraft_reference_register_v1.json`, captured verbatim from the reference module
//! (`scripts/rust_migration/capture_reference_drag_register.py`) and sha256-pinned here.
//!
//! This module compares no thrust with a drag and reads no file: the thrust band (12 / 25 mN) is register data with
//! requirement_status FROZEN_REQUIREMENTS_SNAPSHOT, echoed and used only for the orientation q* = T_band / (C_D A_ref);
//! the S6.15 margin indication lives in [`crate::statewise`].

use crate::pyval::{get, get_or_null, nonblank_str, py_err, py_float, req_pos};
use abep_types::pyjson::{loads, py_eq, py_repr, py_repr_str, read_text_utf8, Dict, Value};
use abep_types::{AbepError, AbepResult, EvalStatus};
use std::sync::OnceLock;

pub const SCHEMA: &str = "abep.spacecraft_reference_drag.v1";
pub const STATUS: &str = "REFERENCE_PARAMETRIC_NOT_FLIGHT";
pub const FREEZE_STATUS: &str = "NOT_EVALUATED";
pub const LABEL: &str = "REFERENCE/PARAMETRIC";
pub const RETRIEVAL_DATE: &str = "2026-10-01";
/// Evidence status of every reference drag result for freeze purposes (S6.18).
pub const FREEZE_EVAL_STATUS: EvalStatus = EvalStatus::NotEvaluated;

/// The reference module the register was captured from, and its sha256 at capture (the v1 record's module_sha256).
pub const MODULE_REL: &str = "abep_sim/spacecraft_reference_drag.py";
pub const MODULE_SHA256: &str = "28bcc6bda5e45947ed3bc72e9561a8efbde59f8e9707c7fb864d8d88fa2eaa8d";
pub const REGISTER_REL: &str = "crates/abep-mission/data/spacecraft_reference_register_v1.json";
pub const REGISTER_SHA256: &str = "4952eb745b201a57406dc6fe0513f6217f654ddb6d2ad7300c5334112a42ffa3";
const REGISTER_BYTES: &[u8] = include_bytes!("../data/spacecraft_reference_register_v1.json");

const SCOPE_INCLUDES: &str = "includes_intake";
const SCOPE_EXCLUDES: &str = "body_excluding_intake";
const SCOPE_UNSTATED: &str = "unstated";
const SEPARATE_TERM: &str = "separate_term";
const CONTAINED: &str = "contained_in_reference";

/// One declared reference case: an (A_ref, C_D) pair that the SAME source states together.
#[derive(Debug, Clone, PartialEq)]
pub struct ReferenceCase {
    pub case_id: String,
    pub record_id: String,
    pub a_ref_m2: f64,
    pub cd: f64,
    /// includes_intake | body_excluding_intake | unstated
    pub a_ref_scope: String,
    pub source: String,
    pub evidence_level: i64,
    pub quantity_type: String,
    pub array_treatment: String,
    pub note: String,
}

impl ReferenceCase {
    /// `case.__dict__` (dataclass field order).
    pub fn to_value(&self) -> Value {
        abep_types::pydict! {
            "case_id" => self.case_id.as_str(),
            "record_id" => self.record_id.as_str(),
            "a_ref_m2" => self.a_ref_m2,
            "cd" => self.cd,
            "a_ref_scope" => self.a_ref_scope.as_str(),
            "source" => self.source.as_str(),
            "evidence_level" => self.evidence_level,
            "quantity_type" => self.quantity_type.as_str(),
            "array_treatment" => self.array_treatment.as_str(),
            "note" => self.note.as_str(),
        }
    }
}

/// One owner decision record the register is based on (path + companion-json sha256).
#[derive(Debug, Clone, PartialEq)]
pub struct DecisionRef {
    pub path: String,
    pub md_sha256: String,
    pub json_path: String,
    pub json_sha256: String,
}

/// The verified register.
#[derive(Debug, Clone)]
pub struct Register {
    /// build_document() without density_free_table, in the reference order.
    pub document: Dict,
    pub document_key_order: Vec<String>,
    pub cases: Vec<ReferenceCase>,
    pub decisions: Vec<DecisionRef>,
    pub intake_accounting: Vec<String>,
    pub scopes: Vec<String>,
    pub band_min_mn: f64,
    pub band_max_mn: f64,
    pub band_requirement_status: String,
}

fn schema(msg: impl Into<String>) -> AbepError {
    AbepError::Schema { path: REGISTER_REL.to_string(), message: msg.into() }
}

fn str_of<'a>(d: &'a Dict, k: &str) -> AbepResult<&'a str> {
    d.get(k).and_then(Value::as_str).ok_or_else(|| schema(format!("{k}: string expected")))
}

fn num_of(d: &Dict, k: &str) -> AbepResult<f64> {
    match d.get(k) {
        Some(Value::Float(f)) => Ok(*f),
        _ => Err(schema(format!("{k}: float expected"))),
    }
}

fn parse_register() -> AbepResult<Register> {
    let sha = abep_provenance::sha256_hex(REGISTER_BYTES);
    if sha != REGISTER_SHA256 {
        return Err(AbepError::HashMismatch {
            path: REGISTER_REL.to_string(),
            expected: REGISTER_SHA256.to_string(),
            actual: sha,
        });
    }
    let text = read_text_utf8(REGISTER_BYTES).map_err(|e| schema(e.to_string()))?;
    let top = loads(&text).map_err(|e| schema(e.to_string()))?;
    let top = top.as_dict().ok_or_else(|| schema("top level is not an object"))?;
    if top.get("captured_from").and_then(Value::as_dict).and_then(|c| c.get("module_sha256")).and_then(Value::as_str)
        != Some(MODULE_SHA256)
    {
        return Err(schema("captured_from.module_sha256 differs from MODULE_SHA256"));
    }
    let document = top.get("register").and_then(Value::as_dict).ok_or_else(|| schema("register"))?.clone();
    let strings = |k: &str| -> AbepResult<Vec<String>> {
        top.get(k)
            .and_then(Value::as_list)
            .ok_or_else(|| schema(k.to_string()))?
            .iter()
            .map(|v| v.as_str().map(str::to_string).ok_or_else(|| schema(format!("{k}: string expected"))))
            .collect()
    };
    let document_key_order = strings("document_key_order")?;
    let intake_accounting = strings("intake_accounting")?;
    let scopes = strings("a_ref_scopes")?;
    for (k, want) in [("schema", SCHEMA), ("status", STATUS), ("freeze_status", FREEZE_STATUS), ("label", LABEL)] {
        if str_of(&document, k)? != want {
            return Err(schema(format!("register {k} is not {want}")));
        }
    }
    if str_of(&document, "retrieval_date")? != RETRIEVAL_DATE {
        return Err(schema("retrieval_date"));
    }
    let mut cases = Vec::new();
    for c in document.get("cases").and_then(Value::as_list).ok_or_else(|| schema("cases"))? {
        let c = c.as_dict().ok_or_else(|| schema("case is not an object"))?;
        let evidence_level = match c.get("evidence_level") {
            Some(Value::Int(i)) => i.as_i64().ok_or_else(|| schema("evidence_level"))?,
            _ => return Err(schema("evidence_level: int expected")),
        };
        cases.push(ReferenceCase {
            case_id: str_of(c, "case_id")?.to_string(),
            record_id: str_of(c, "record_id")?.to_string(),
            a_ref_m2: num_of(c, "a_ref_m2")?,
            cd: num_of(c, "cd")?,
            a_ref_scope: str_of(c, "a_ref_scope")?.to_string(),
            source: str_of(c, "source")?.to_string(),
            evidence_level,
            quantity_type: str_of(c, "quantity_type")?.to_string(),
            array_treatment: str_of(c, "array_treatment")?.to_string(),
            note: str_of(c, "note")?.to_string(),
        });
    }
    let mut decisions = Vec::new();
    for d in document.get("decisions").and_then(Value::as_list).ok_or_else(|| schema("decisions"))? {
        let d = d.as_dict().ok_or_else(|| schema("decision is not an object"))?;
        decisions.push(DecisionRef {
            path: str_of(d, "path")?.to_string(),
            md_sha256: str_of(d, "md_sha256")?.to_string(),
            json_path: str_of(d, "json_path")?.to_string(),
            json_sha256: str_of(d, "json_sha256")?.to_string(),
        });
    }
    let band = document.get("rfp_thrust_band").and_then(Value::as_dict).ok_or_else(|| schema("rfp_thrust_band"))?;
    let reg = Register {
        band_min_mn: num_of(band, "min_mN")?,
        band_max_mn: num_of(band, "max_mN")?,
        band_requirement_status: str_of(band, "requirement_status")?.to_string(),
        document,
        document_key_order,
        cases,
        decisions,
        intake_accounting,
        scopes,
    };
    check_integrity(&reg)?;
    Ok(reg)
}

/// `_integrity()`: every case maps to a record whose stated (A_ref, C_D) contains the case pair (no cross-source
/// pairing); a_ref_scope in the vocabulary. A failure is MODEL_ERROR.
fn check_integrity(reg: &Register) -> AbepResult<()> {
    let model = |m: String| AbepError::Model { message: format!("ValueError: {m}") };
    let records = reg.document.get("records").and_then(Value::as_list).ok_or_else(|| schema("records"))?;
    for c in &reg.cases {
        if !reg.scopes.contains(&c.a_ref_scope) {
            return Err(model(format!("{}: bad a_ref_scope", c.case_id)));
        }
        let rec = records
            .iter()
            .filter_map(Value::as_dict)
            .find(|r| r.get("id").and_then(Value::as_str) == Some(c.record_id.as_str()))
            .ok_or_else(|| model(format!("{}: unknown record {}", c.case_id, c.record_id)))?;
        let value_of =
            |k: &str| rec.get(k).and_then(Value::as_dict).and_then(|v| v.get("value")).cloned().unwrap_or(Value::Null);
        let (a, cd) = (value_of("frontal_area_m2"), value_of("cd"));
        let cds = match &cd {
            Value::List(l) => l.clone(),
            other => vec![other.clone()],
        };
        if !py_eq(&a, &Value::Float(c.a_ref_m2)) || !cds.iter().any(|x| py_eq(x, &Value::Float(c.cd))) {
            return Err(model(format!("{}: (A_ref, C_D) not stated together by record {}", c.case_id, c.record_id)));
        }
    }
    Ok(())
}

/// The verified register (parsed and integrity-checked once).
pub fn register() -> AbepResult<&'static Register> {
    static REG: OnceLock<AbepResult<Register>> = OnceLock::new();
    REG.get_or_init(parse_register).as_ref().map_err(Clone::clone)
}

/// `_integrity()` of the reference (run at import there; here on first use of the register).
pub fn integrity() -> AbepResult<()> {
    register().map(|_| ())
}

/// The declared cases in declared order (`CASES`).
pub fn cases() -> AbepResult<&'static [ReferenceCase]> {
    Ok(&register()?.cases)
}

/// `case(case_id)`: the declared case or None.
pub fn case(case_id: &str) -> Option<&'static ReferenceCase> {
    register().ok()?.cases.iter().find(|c| c.case_id == case_id)
}

/// Inputs of [`reference_drag`] as the reference receives them (JSON-shaped values: missing / mistyped inputs are
/// refused with the reference exception classes).
#[derive(Debug, Clone, PartialEq)]
pub struct DragArgs {
    pub rho_kg_m3: Value,
    pub v_rel_m_s: Value,
    pub intake_projected_area_m2: Value,
    pub intake_cd: Value,
    pub intake_source: Value,
    /// `{"source": ..., "state_id": ...}` naming the orbit-resolved state, so thrust and drag can be paired (S6.15)
    pub atmosphere_state: Value,
    /// separate_term | contained_in_reference
    pub intake_accounting: Value,
}

impl DragArgs {
    /// Typed constructor for Rust callers.
    #[allow(clippy::too_many_arguments)]
    pub fn numeric(
        rho_kg_m3: f64,
        v_rel_m_s: f64,
        intake_projected_area_m2: f64,
        intake_cd: f64,
        intake_source: &str,
        atmosphere_state: Dict,
        intake_accounting: &str,
    ) -> DragArgs {
        DragArgs {
            rho_kg_m3: Value::Float(rho_kg_m3),
            v_rel_m_s: Value::Float(v_rel_m_s),
            intake_projected_area_m2: Value::Float(intake_projected_area_m2),
            intake_cd: Value::Float(intake_cd),
            intake_source: Value::str(intake_source),
            atmosphere_state: Value::Dict(atmosphere_state),
            intake_accounting: Value::str(intake_accounting),
        }
    }
}

/// One reference drag result (the reference dict, typed).
#[derive(Debug, Clone, PartialEq)]
pub struct ReferenceDrag {
    pub case: ReferenceCase,
    pub atmosphere_state: Dict,
    pub rho_kg_m3: f64,
    pub v_rel_m_s: f64,
    pub intake_projected_area_m2: f64,
    pub intake_cd: f64,
    pub intake_source: String,
    pub intake_accounting: String,
    pub q_pa: f64,
    pub d_reference_n: f64,
    pub d_intake_n: f64,
    pub intake_added_to_total: bool,
    pub d_total_n: f64,
    pub flags: Vec<String>,
    pub band_min_mn: f64,
    pub band_max_mn: f64,
    pub band_requirement_status: String,
}

impl ReferenceDrag {
    pub fn d_total_mn(&self) -> f64 {
        self.d_total_n * 1e3
    }

    /// The reference result dict (key order as the reference).
    pub fn to_value(&self) -> Value {
        let c = &self.case;
        abep_types::pydict! {
            "schema" => SCHEMA,
            "status" => STATUS,
            "freeze_status" => FREEZE_STATUS,
            "label" => LABEL,
            "case_id" => c.case_id.as_str(),
            "record_id" => c.record_id.as_str(),
            "atmosphere_state" => self.atmosphere_state.clone(),
            "inputs" => abep_types::pydict! {
                "rho_kg_m3" => self.rho_kg_m3,
                "v_rel_m_s" => self.v_rel_m_s,
                "intake_projected_area_m2" => self.intake_projected_area_m2,
                "intake_cd" => self.intake_cd,
                "intake_source" => self.intake_source.as_str(),
                "intake_accounting" => self.intake_accounting.as_str(),
            },
            "q_Pa" => self.q_pa,
            "reference_term" => abep_types::pydict! {
                "cd" => c.cd,
                "a_ref_m2" => c.a_ref_m2,
                "a_ref_scope" => c.a_ref_scope.as_str(),
                "D_N" => self.d_reference_n,
                "source" => c.source.as_str(),
                "evidence_level" => c.evidence_level,
                "quantity_type" => c.quantity_type.as_str(),
                "array_treatment" => c.array_treatment.as_str(),
            },
            "intake_term" => abep_types::pydict! {
                "D_N" => self.d_intake_n,
                "added_to_total" => self.intake_added_to_total,
                "owner" => "F1 (caller-supplied)",
            },
            "D_total_N" => self.d_total_n,
            "D_total_mN" => self.d_total_mn(),
            "flags" => self.flags.iter().map(|f| Value::str(f.as_str())).collect::<Vec<_>>(),
            "rfp_thrust_band_mN" => abep_types::pydict! {
                "min" => self.band_min_mn,
                "max" => self.band_max_mn,
                "requirement_status" => self.band_requirement_status.as_str(),
            },
        }
    }
}

fn lookup_case<'a>(reg: &'a Register, case_id: &Value) -> AbepResult<&'a ReferenceCase> {
    if let Value::List(_) | Value::Dict(_) = case_id {
        return Err(py_err("TypeError", format!("unhashable type: '{}'", case_id.type_name())));
    }
    let found = match case_id {
        Value::Str(s) => reg.cases.iter().find(|c| &c.case_id == s),
        _ => None,
    };
    found.ok_or_else(|| {
        let mut ids: Vec<&str> = reg.cases.iter().map(|c| c.case_id.as_str()).collect();
        ids.sort_unstable();
        let declared = ids.iter().map(|s| py_repr_str(s)).collect::<Vec<_>>().join(", ");
        let msg = format!("unknown reference case {}; declared: [{declared}]", py_repr(case_id));
        py_err("KeyError", py_repr_str(&msg))
    })
}

/// `reference_drag(case_id, ...)`: parametric drag of a declared reference case at ONE caller-supplied atmospheric /
/// orbit state. `intake_accounting` "separate_term": D_total = D_reference + D_intake (refused for a case whose A_ref
/// includes the intake); "contained_in_reference": D_intake reported, not added (refused for a case whose A_ref
/// excludes it); a case with unstated scope accepts either and is flagged INTAKE_OVERLAP_UNRESOLVED.
///
/// A non-finite q or drag (overflow, inf * 0) is refused (contract DIV-A-01) where the reference returns it.
pub fn reference_drag(case_id: &Value, args: &DragArgs) -> AbepResult<ReferenceDrag> {
    let reg = register()?;
    let case = lookup_case(reg, case_id)?;
    evaluate(reg, case, args)
}

/// Typed entry for Rust callers: `reference_drag(case_id, DragArgs)`.
pub fn reference_drag_for(case_id: &str, args: &DragArgs) -> AbepResult<ReferenceDrag> {
    reference_drag(&Value::str(case_id), args)
}

fn evaluate(reg: &Register, case: &ReferenceCase, args: &DragArgs) -> AbepResult<ReferenceDrag> {
    let rho = req_pos("rho_kg_m3", &args.rho_kg_m3, false)?;
    let v = req_pos("v_rel_m_s", &args.v_rel_m_s, false)?;
    let a_int = req_pos("intake_projected_area_m2", &args.intake_projected_area_m2, true)?;
    let cd_int = req_pos("intake_cd", &args.intake_cd, true)?;
    if !nonblank_str(&args.intake_source) {
        return Err(py_err(
            "ValueError",
            "intake_source is required: cite the F1 record that supplies the intake area and C_D",
        ));
    }
    let state = match &args.atmosphere_state {
        Value::Dict(d) if get_or_null(d, "source").truthy() && get_or_null(d, "state_id").truthy() => d,
        _ => {
            return Err(py_err(
                "ValueError",
                "atmosphere_state must be a dict with non-empty 'source' and 'state_id' (orbit-resolved state)",
            ))
        }
    };
    let accounting = match &args.intake_accounting {
        Value::Str(s) if reg.intake_accounting.contains(s) => s.as_str(),
        other => {
            let tuple = reg.intake_accounting.iter().map(|s| py_repr_str(s)).collect::<Vec<_>>().join(", ");
            return Err(py_err(
                "ValueError",
                format!("intake_accounting must be one of ({tuple}); got {}", py_repr(other)),
            ));
        }
    };
    if accounting == SEPARATE_TERM && case.a_ref_scope == SCOPE_INCLUDES {
        return Err(py_err(
            "ValueError",
            format!("{}: A_ref already includes the intake; adding a separate intake term double-counts", case.case_id),
        ));
    }
    if accounting == CONTAINED && case.a_ref_scope == SCOPE_EXCLUDES {
        return Err(py_err(
            "ValueError",
            format!("{}: A_ref excludes the intake; the intake term must be added separately", case.case_id),
        ));
    }
    let q = 0.5 * rho * v * v;
    let d_ref = q * case.cd * case.a_ref_m2;
    let d_int = q * cd_int * a_int;
    let added = accounting == SEPARATE_TERM;
    let d_tot = d_ref + if added { d_int } else { 0.0 };
    if ![q, d_ref, d_int, d_tot, d_tot * 1e3].iter().all(|x| x.is_finite()) {
        return Err(py_err(
            "ValueError",
            format!(
                "non-finite drag result (q_Pa {q}, D_reference {d_ref}, D_intake {d_int}, D_total {d_tot}); refused \
                 (contract DIV-A-01)"
            ),
        ));
    }
    let mut flags = Vec::new();
    if case.a_ref_scope == SCOPE_UNSTATED {
        flags.push("INTAKE_OVERLAP_UNRESOLVED".to_string());
    }
    if case.quantity_type == "as-reported (secondary)" || case.quantity_type == "assumed" {
        let kind = if case.quantity_type.starts_with("as-reported") { "SECONDARY" } else { "ASSUMED" };
        flags.push(format!("CD_{kind}"));
    }
    Ok(ReferenceDrag {
        case: case.clone(),
        atmosphere_state: state.clone(),
        rho_kg_m3: rho,
        v_rel_m_s: v,
        intake_projected_area_m2: a_int,
        intake_cd: cd_int,
        intake_source: args.intake_source.as_str().unwrap_or_default().to_string(),
        intake_accounting: accounting.to_string(),
        q_pa: q,
        d_reference_n: d_ref,
        d_intake_n: d_int,
        intake_added_to_total: added,
        d_total_n: d_tot,
        flags,
        band_min_mn: reg.band_min_mn,
        band_max_mn: reg.band_max_mn,
        band_requirement_status: reg.band_requirement_status.clone(),
    })
}

/// Python `round(x, ndigits)` for a float: the correctly rounded decimal (round-half-even on exact ties), parsed
/// back with correct rounding.
pub fn py_round(x: f64, ndigits: usize) -> f64 {
    if !x.is_finite() || x == x.trunc() {
        return x;
    }
    format!("{x:.ndigits$}").parse().expect("formatted float parses")
}

/// One row of [`density_free_table`].
#[derive(Debug, Clone, PartialEq)]
pub struct DensityFreeRow {
    pub case_id: String,
    pub record_id: String,
    pub cd: f64,
    pub a_ref_m2: f64,
    pub cd_a_m2: f64,
    pub a_ref_scope: String,
    pub q_at_12mn_pa: f64,
    pub q_at_25mn_pa: f64,
    pub evidence_level: i64,
    pub quantity_type: String,
}

impl DensityFreeRow {
    pub fn to_value(&self) -> Value {
        abep_types::pydict! {
            "case_id" => self.case_id.as_str(),
            "record_id" => self.record_id.as_str(),
            "cd" => self.cd,
            "a_ref_m2" => self.a_ref_m2,
            "cd_a_m2" => self.cd_a_m2,
            "a_ref_scope" => self.a_ref_scope.as_str(),
            "q_at_12mN_Pa" => self.q_at_12mn_pa,
            "q_at_25mN_Pa" => self.q_at_25mn_pa,
            "evidence_level" => self.evidence_level,
            "quantity_type" => self.quantity_type.as_str(),
        }
    }
}

/// `density_free_table()`: per declared case C_D * A_ref and the dynamic pressure q* at which the reference term alone
/// equals the 12 and 25 mN band edges (q* = T / (C_D A_ref)); intake term excluded; orientation only.
pub fn density_free_table() -> AbepResult<Vec<DensityFreeRow>> {
    let reg = register()?;
    Ok(reg
        .cases
        .iter()
        .map(|c| {
            let cda = c.cd * c.a_ref_m2;
            DensityFreeRow {
                case_id: c.case_id.clone(),
                record_id: c.record_id.clone(),
                cd: c.cd,
                a_ref_m2: c.a_ref_m2,
                cd_a_m2: py_round(cda, 6),
                a_ref_scope: c.a_ref_scope.clone(),
                q_at_12mn_pa: py_round(reg.band_min_mn * 1e-3 / cda, 9),
                q_at_25mn_pa: py_round(reg.band_max_mn * 1e-3 / cda, 9),
                evidence_level: c.evidence_level,
                quantity_type: c.quantity_type.clone(),
            }
        })
        .collect())
}

/// `build_document()`: the deterministic register document (no timestamps beyond the fixed retrieval date).
pub fn build_document() -> AbepResult<Value> {
    let reg = register()?;
    let mut doc = Dict::new();
    for k in &reg.document_key_order {
        if k == "density_free_table" {
            let rows = density_free_table()?.iter().map(DensityFreeRow::to_value).collect::<Vec<_>>();
            doc.insert(k.as_str(), Value::List(rows));
        } else {
            doc.insert(k.as_str(), get(&reg.document, k)?.clone());
        }
    }
    Ok(Value::Dict(doc))
}

/// Numeric value of a register field (float), for typed readers.
pub fn register_float(v: &Value) -> AbepResult<f64> {
    py_float(v)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state() -> Dict {
        let mut d = Dict::new();
        d.insert("source", Value::str("test-orbit-resolved-stub"));
        d.insert("state_id", Value::str("s0"));
        d
    }

    #[test]
    fn register_is_verified_and_consistent() {
        let reg = register().unwrap();
        assert_eq!(reg.cases.len(), 8);
        assert_eq!(reg.decisions.len(), 3);
        assert_eq!((reg.band_min_mn, reg.band_max_mn), (12.0, 25.0));
        assert_eq!(reg.band_requirement_status, "FROZEN_REQUIREMENTS_SNAPSHOT");
        assert_eq!(reg.intake_accounting, [SEPARATE_TERM, CONTAINED]);
        assert!(case("RC-DIAMANT").is_some() && case("RC-FLIGHT").is_none());
    }

    #[test]
    fn drag_equation_and_labels() {
        let args = DragArgs::numeric(2.5e-10, 7800.0, 0.1, 2.0, "F1 test stub", state(), SEPARATE_TERM);
        let r = reference_drag_for("RC-DIAMANT", &args).unwrap();
        let q = 0.5 * 2.5e-10 * 7800.0 * 7800.0;
        assert_eq!(r.q_pa, q);
        assert_eq!(r.d_reference_n, q * 2.2 * 0.5);
        assert_eq!(r.d_intake_n, q * 2.0 * 0.1);
        assert_eq!(r.d_total_n, r.d_reference_n + r.d_intake_n);
        assert_eq!(r.flags, ["INTAKE_OVERLAP_UNRESOLVED", "CD_SECONDARY"]);
        let v = r.to_value();
        let d = v.as_dict().unwrap();
        assert_eq!(d.get("status").unwrap().as_str(), Some(STATUS));
        assert_eq!(d.get("freeze_status").unwrap().as_str(), Some(FREEZE_STATUS));
        assert_eq!(FREEZE_EVAL_STATUS, EvalStatus::NotEvaluated);
    }

    #[test]
    fn intake_accounting_guards_double_counting() {
        let args = DragArgs::numeric(2.5e-10, 7800.0, 0.1, 2.0, "F1", state(), SEPARATE_TERM);
        let e = reference_drag_for("RC-ROMANO2018", &args).unwrap_err().to_string();
        assert!(e.contains("ValueError: RC-ROMANO2018: A_ref already includes the intake"), "{e}");
        let args = DragArgs::numeric(2.5e-10, 7800.0, 0.1, 2.0, "F1", state(), CONTAINED);
        let r = reference_drag_for("RC-ROMANO2018", &args).unwrap();
        assert!(!r.intake_added_to_total && r.d_total_n == r.d_reference_n);
    }

    #[test]
    fn excluded_scope_refuses_contained_accounting() {
        // DIV-A-03: no declared case has scope body_excluding_intake; the branch is exercised on a test-only case.
        let reg = register().unwrap();
        let mut c = reg.cases[3].clone();
        c.a_ref_scope = SCOPE_EXCLUDES.to_string();
        let args = DragArgs::numeric(2.5e-10, 7800.0, 0.1, 2.0, "F1", state(), CONTAINED);
        let e = evaluate(reg, &c, &args).unwrap_err().to_string();
        assert!(e.ends_with("A_ref excludes the intake; the intake term must be added separately"), "{e}");
        let args = DragArgs::numeric(2.5e-10, 7800.0, 0.1, 2.0, "F1", state(), SEPARATE_TERM);
        assert!(evaluate(reg, &c, &args).unwrap().intake_added_to_total);
    }

    #[test]
    fn non_finite_results_are_refused() {
        let args = DragArgs::numeric(1e300, 1e200, 0.0, 0.0, "F1", state(), SEPARATE_TERM);
        let e = reference_drag_for("RC-DIAMANT", &args).unwrap_err();
        assert_eq!(e.status(), EvalStatus::OutOfDomain);
        assert!(e.to_string().contains("non-finite drag result"));
    }

    #[test]
    fn unknown_case_message_is_the_reference_keyerror() {
        let args = DragArgs::numeric(2.5e-10, 7800.0, 0.1, 2.0, "F1", state(), SEPARATE_TERM);
        let e = reference_drag_for("RC-X", &args).unwrap_err().to_string();
        assert!(
            e.ends_with(
                "KeyError: \"unknown reference case 'RC-X'; declared: ['RC-DIAMANT', 'RC-DICARA-ESA', 'RC-NISHIYAMA', \
                 'RC-ROMANO2018', 'RC-SCHONHERR', 'RC-TISAEV-HIGH', 'RC-TISAEV-LOW', 'RC-VAIDYA-GOCELIKE']\""
            ),
            "{e}"
        );
    }

    #[test]
    fn density_free_table_rounds_like_python() {
        let rows = density_free_table().unwrap();
        assert_eq!(rows[0].case_id, "RC-ROMANO2018");
        assert_eq!(rows[0].cd_a_m2, 2.2);
        assert_eq!(rows[0].q_at_12mn_pa, 0.005454545);
        assert_eq!(rows[0].q_at_25mn_pa, 0.011363636);
        // Python: round(0.5, 0) == 0.0, round(1.5, 0) == 2.0, round(2.675, 2) == 2.67, round(-0.0, 6) == -0.0
        assert_eq!(py_round(0.5, 0), 0.0);
        assert_eq!(py_round(1.5, 0), 2.0);
        assert_eq!(py_round(2.675, 2), 2.67);
        assert!(py_round(-0.0, 6).is_sign_negative());
    }
}
