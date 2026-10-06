//! The selected-flight architecture mass record `mass_power_a9_v5` (A9.26 bid mass policy; successor of the immutable
//! v4): Rust port of `docs/budgets/mass_power_a9_v5/build_mass_power_a9_v5.py` (build_doc / render_md and its record
//! functions). Contract `docs/rust_migration/contracts/C-DOCS_BUDGETS_MASS_POWER_A9_V5/`.
//!
//! The six pinned inputs are read as pinned inputs: the v4 record and Markdown as data, the A9.26 records as the owner
//! authorization, and the v3 / v4 builder files by sha256 only (their rule functions are ported in
//! [`super::rules`]; they are never executed). The record bytes reproduce the committed record exactly; the frozen bid
//! files are never written by this module.
//!
//! A9.28 msg 1 sec. 2: the record is ACTIVE_SELECTED_ARCHITECTURE_ENGINEERING_ASSESSMENT; AL-07 6.0 kg stays
//! PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT with AFI-02-RA1 open ([`al07_value_status`]). Mass compliance stays
//! INCOMPLETE_EVIDENCE / NOT_YET_CLOSED ([`mass_gates`]); nothing here returns PASS.

use super::py::{self, dict, err, f, list, s, strs};
use super::pyfmt::{format_fixed, format_g};
use super::rules::{
    self, Margin, Refs, RollupSpec, XeSplit, FLIGHT, HARNESS_FRACTION, SYSTEM_MARGIN, SYSTEM_MARGIN_BID,
};
use abep_provenance::sha256_hex;
use abep_types::pyjson::{self, py_eq, py_repr, py_str, DumpOptions, PyException, PyResult, Value};
use abep_types::EvalStatus;
use std::path::Path;

pub const LANE_REL: &str = "docs/budgets/mass_power_a9_v5";
pub const SCRIPT_REL: &str = "docs/budgets/mass_power_a9_v5/build_mass_power_a9_v5.py";
pub const JSON_NAME: &str = "mass_power_a9_v5.json";
pub const MD_NAME: &str = "MASS_POWER_A9_V5.md";
pub const TEST_REL: &str = "tests/test_mass_power_a9_v5.py";
pub const SCHEMA_ID: &str = "mass_power_a9_v5";
pub const BASE_COMMIT: &str = "7fdc9db0a6fa696b532f4f11b1a8f982a8d03ed5";
pub const DATE: &str = "2026-10-05";
/// sha256 of the committed record (frozen bid technical source 5eee4b8): the pinned production input.
pub const RECORD_SHA256: &str = "3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a";
pub const RECORD_REL: &str = "docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json";
pub const MD_REL: &str = "docs/budgets/mass_power_a9_v5/MASS_POWER_A9_V5.md";

/// The builder's PINS, in order: (key, path, sha256).
pub const PINS: [(&str, &str, &str); 6] = [
    (
        "V4_JSON",
        "docs/budgets/mass_power_a9_v4/mass_power_a9_v4.json",
        "37264ab6c7cf5c422cb93356fcd9a8e67323f73b1257e1eb1426410229c8a6c4",
    ),
    (
        "V4_MD",
        "docs/budgets/mass_power_a9_v4/MASS_POWER_A9_V4.md",
        "cd68ed11de08183efe2a3698ed87f62959ec7d4b84db307378dcca2769472de7",
    ),
    (
        "V4_BUILDER",
        "docs/budgets/mass_power_a9_v4/build_mass_power_a9_v4.py",
        "6eccc6e7ee443bee77513ad51f141cb36e6ad9fe40949bb5d0a2809d59fe6597",
    ),
    (
        "V3_BUILDER",
        "docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py",
        "b1df7537456d5334e8b051bb6ed9bca9626933497b3b52e916c9997338e6a572",
    ),
    (
        "A9_26_MD",
        "docs/decisions/OD_2026_10_05_A9_26_MASS_BUDGET_OWNER_DECISIONS.md",
        "5f40294de9ab736cedd7a24a393b0333823c2624e3469f6b1f775250a85803e5",
    ),
    (
        "A9_26_JSON",
        "docs/decisions/OD_2026_10_05_A9_26_mass_budget_owner_decisions.json",
        "18dada24a90fb1a5d17e903bf8eb9f77af622106f9ddfc59ea1f182054b80b76",
    ),
];

fn pin(key: &str) -> (&'static str, &'static str) {
    let p = PINS.iter().find(|p| p.0 == key).expect("registered pin key");
    (p.1, p.2)
}

const MSG_N: i64 = 2;
const MSG_KEY: &str = "MASS_BUDGET_DECISIONS_PRE_BID_FREEZE";
const MSG_SHA: &str = "c240fca3b8109078ac0113cdb3526d729e3f13c41a8e8639b802b463f535633f";

/// Verbatim owner text applied (A9.26 message 2), whitespace-normalised: (key, section, quote).
pub const Q: [(&str, i64, &str); 27] = [
    ("margin", 1, "SYSTEM-LEVEL MASS MARGIN = 10%"),
    (
        "historical",
        1,
        "The earlier 20% system-margin treatment remains historical / conservative internal provenance only and must \
         not remain the active bid mass-margin policy.",
    ),
    (
        "line_uplift",
        1,
        "Keep the existing 20% LINE-LEVEL planning uplift on floor-derived lines: AL-04 AL-07 AL-08 for this bid \
         freeze.",
    ),
    ("factor", 1, "1.20 x 1.10 = 1.32"),
    ("floors_unchanged", 1, "Do not alter the line-floor values themselves in this step."),
    ("sensitivity", 1, "HISTORICAL / CONSERVATIVE SENSITIVITY"),
    ("al09", 2, "AL-09 controls / electronics / valve drivers / flight sensors = 1.0 kg"),
    ("al09_status", 2, "PROVISIONAL_OWNER_ALLOCATION NOT_CBE NOT_MEASURED"),
    ("harness", 2, "Harness remains separate under the existing 5/95 rule."),
    ("mpv3q01", 2, "Close: MPV3Q-01 accordingly."),
    ("no_compensation", 2, "Do not reduce another line to compensate for this allocation."),
    ("al09_cbe", 2, "Replace AL-09 with a design-derived CBE when available."),
    ("recompute", 3, "Recompute these from the builder; do not hard-code these rounded values."),
    ("stop", 3, "If the governed builder gives materially different results, STOP and report."),
    ("status", 4, "INCOMPLETE_EVIDENCE / NOT_YET_CLOSED"),
    ("no_pass", 4, "Do not claim PASS."),
    ("target", 5, "nominal dry <= 34.0 kg"),
    ("target_arith", 5, "34.0 x 1.10 + 2.0 = 39.4 kg wet"),
    ("target_label", 5, "This is a DESIGN TARGET, not achieved evidence."),
    ("xe_reference", 5, "The 2 kg Xe case is a planning/reference case only."),
    ("xe_not_selected", 5, "Do not call it the final selected Xe load."),
    ("xe_sensitivities", 5, "Continue carrying 5 kg and 10 kg as sensitivities."),
    ("row54", 6, "24 kg + 20% = 28.8 kg"),
    ("row54_history", 6, "Preserve that as historical/internal allocation provenance."),
    ("alloc_label", 6, "INTERNAL ALLOCATION TARGET NOT EVIDENCE OF MASS COMPLIANCE"),
    ("alloc_not_target", 6, "Do not confuse it with the <=34 kg proposal nominal-dry target."),
    ("no_compliance", 7, "Do not claim current mass compliance."),
];

fn quotes() -> impl Iterator<Item = &'static (&'static str, i64, &'static str)> {
    Q.iter()
}

fn quote(key: &str) -> &'static str {
    quotes().find(|q| q.0 == key).expect("registered quote").2
}

/// `q(key)`: {section, quote}.
fn q(key: &str) -> Value {
    let e = quotes().find(|x| x.0 == key).expect("registered quote");
    dict(vec![("section", Value::int(e.1)), ("quote", s(e.2))])
}

/// A9.26 section 3: the owner's approximate arithmetic (cross-check only; every value is computed).
pub const EXPECTED_ROLLUP: [(&str, f64); 5] = [
    ("nonharness_known_kg", 33.1196),
    ("harness_kg", 1.7431),
    ("nominal_dry_known_kg", 34.8627),
    ("system_margin_kg", 3.4863),
    ("dry_known_kg", 38.3490),
];
pub const EXPECTED_WET: [(f64, f64); 3] = [(2.0, 40.3490), (5.0, 43.3490), (10.0, 48.3490)];
pub const MATERIAL_KG: f64 = 6e-5;
pub const LINE_UPLIFT_LINES: [(&str, f64); 3] = [("AL-04", 4.2048), ("AL-07", 6.0), ("AL-08", 5.9148)];
pub const AL09_KG: f64 = 1.0;
pub const AL09_STATUS: [&str; 3] = ["PROVISIONAL_OWNER_ALLOCATION", "NOT_CBE", "NOT_MEASURED"];
const PT_NOMINAL_DRY_MAX_KG: f64 = 34.0;
const PT_XE_REFERENCE_KG: f64 = 2.0;
const PT_WET_REFERENCE_KG: f64 = 39.4;
pub const HARD: &str = "HARD_40_WET";
pub const MASS_STATUS: &str = "MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED";

/// A9.26 section 7 mass-closure actions: (id, line, action, verbatim quote, detail).
pub const CLOSURE_ACTIONS: [(&str, &str, &str, &str, &str); 6] = [
    (
        "MCA-01",
        "AL-07",
        "current cathodeless PPU CBE / requote",
        "AL-07 current cathodeless PPU CBE/requote;",
        "AFI-02-RA1 (OPEN): re-base the 6.0 kg owner analog floor on the hall_icp_neutralizer load / converter CBE or \
         a cathodeless PPU quotation (RFQ3-HALLEL)",
    ),
    (
        "MCA-02",
        "AL-08",
        "quote / design rebase",
        "AL-08 quote/design rebase;",
        "the 5.9148 kg MEV planning floor (A9.21 PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN) is replaced by quotations / \
         design (RFQ3-GAS rev1; tank, regulator, valves, plumbing, mounting / thermal)",
    ),
    (
        "MCA-03",
        "AL-04",
        "completed Hall-head CBE",
        "AL-04 completed Hall-head CBE;",
        "the 4.2048 kg MEV planning floor covers magnetic parts only (channel ceramics, anode / distributor, body, \
         fasteners TBD); replaced by 1.20 x the completed H-1 CBE (MQ-03)",
    ),
    (
        "MCA-04",
        "AL-09",
        "design-derived CBE",
        "AL-09 design-derived CBE;",
        "the 1.0 kg PROVISIONAL_OWNER_ALLOCATION is replaced by a design-derived CBE when available (A9.26 section 2)",
    ),
    (
        "MCA-05",
        "AL-HAR",
        "actual routed harness",
        "actual routed harness;",
        "the row-60 5/95 harness rule (MQ-06) is replaced by the routed-harness mass",
    ),
    (
        "MCA-06",
        "system",
        "subsystem integration / structural optimisation",
        "subsystem integration / structural optimization.",
        "integration and structural optimisation across AL-01 .. AL-10 (MQ-10: reduce actual subsystem CBE; no \
         requirement relaxation, no removal of qualified hardware solely to force < 40 kg)",
    ),
];

fn policy(message: impl Into<String>) -> PyException {
    rules::policy_error(message)
}

fn g<'a>(v: &'a Value, key: &str) -> PyResult<&'a Value> {
    py::gi(v, key)
}

fn gn(v: &Value, key: &str) -> PyResult<f64> {
    py::num(g(v, key)?)
}

fn rk(x: f64) -> Value {
    rules::rkf(x)
}

// ======================================================================== pins and the A9.26 owner record
/// `verify_pins()`: every pinned input must match its sha256 (PinError lists the changed ones in PINS order).
pub fn verify_pins(repo: &Path) -> PyResult<()> {
    let mut bad = Vec::new();
    for (_, p, want) in PINS {
        let got = sha256_hex(&py::read_bytes(repo, p)?);
        if got != want {
            bad.push(format!("{p} (expected {}, got {})", &want[..12], &got[..12]));
        }
    }
    if !bad.is_empty() {
        return Err(err("PinError", format!("pinned immutable inputs changed: {}", bad.join("; "))));
    }
    Ok(())
}

/// `a9_26_message2()`: the A9.26 message-2 owner record, every quote checked verbatim (fail closed).
pub fn a9_26_message2(repo: &Path) -> PyResult<Value> {
    let (md_rel, md_sha) = pin("A9_26_MD");
    let (js_rel, js_sha) = pin("A9_26_JSON");
    let md = py::read_text(repo, md_rel)?;
    let head = format!("## Message {MSG_N} \u{2014} {MSG_KEY} \u{2014} ");
    if md.matches(head.as_str()).count() != 1 {
        return Err(policy("A9.26 message 2 heading not found exactly once"));
    }
    let body = py::after(&md, &head)?;
    if !py::first_line(&body)?.contains(&format!("text sha256 `{MSG_SHA}`")) {
        return Err(policy("A9.26 message 2 text sha256 changed"));
    }
    let text = py::before(&py::after(&body, "````text\n")?, "\n````");
    if sha256_hex(text.as_bytes()) != MSG_SHA {
        return Err(policy("A9.26 message 2 verbatim text does not reproduce its recorded sha256"));
    }
    let flat = py::norm_ws(&text);
    for (k, _sec, qt) in quotes() {
        if !flat.contains(qt) {
            return Err(policy(format!(
                "A9.26 message 2 quote {} not found verbatim: {}",
                pyjson::py_repr_str(k),
                pyjson::py_repr_str(qt)
            )));
        }
    }
    for (_i, _l, _a, qt, _d) in CLOSURE_ACTIONS {
        if !flat.contains(qt) {
            return Err(policy(format!(
                "A9.26 message 2 closure action not found verbatim: {}",
                pyjson::py_repr_str(qt)
            )));
        }
    }
    let js = py::load_json(repo, js_rel)?;
    let mut m2 = Vec::new();
    for m in py::iter(g(&js, "messages")?)? {
        if py_eq(g(&m, "n")?, &Value::int(MSG_N)) {
            m2.push(m);
        }
    }
    if m2.len() != 1 || !py::eq_str(g(&m2[0], "key")?, MSG_KEY) || !py::eq_str(g(&m2[0], "text_sha256")?, MSG_SHA) {
        return Err(policy("A9.26 JSON message 2 record does not match the verbatim record"));
    }
    if !py::eq_str(g(g(&js, "verbatim")?, "sha256")?, md_sha) {
        return Err(policy("A9.26 JSON does not pin the verbatim record"));
    }
    Ok(dict(vec![
        ("decision", s("A9.26")),
        ("id", g(&js, "id")?.clone()),
        ("message", Value::int(MSG_N)),
        ("key", s(MSG_KEY)),
        ("utc", g(&m2[0], "utc")?.clone()),
        ("text_sha256", s(MSG_SHA)),
        ("md", s(md_rel)),
        ("md_sha256", s(md_sha)),
        ("json", s(js_rel)),
        ("json_sha256", s(js_sha)),
        ("supersedes", g(&js, "supersedes")?.clone()),
    ]))
}

fn cite_a926(sections: &[i64]) -> String {
    let (md_rel, md_sha) = pin("A9_26_MD");
    let (js_rel, js_sha) = pin("A9_26_JSON");
    let sec = sections.iter().map(|x| x.to_string()).collect::<Vec<_>>().join("/");
    format!(
        "A9.26 message 2 section {sec} ({js_rel} sha256 {}; verbatim {md_rel} sha256 {})",
        &js_sha[..12],
        &md_sha[..12]
    )
}

// ======================================================================== fail-closed rule functions (A9.26)
const V5_READING: &str =
    "MEV_LEVEL_EVIDENCE_BASED (the single owner reading; A9.26: 10 % system margin, active proposal / bid basis)";
const V5_RULE: &str = "MQ-10 / A9.26: reduce actual subsystem CBE (redesign, integration, lighter qualified parts); \
                       the 40 kg requirement and the A9.26 margin policy are not relaxed further";

fn v5_loaded_error() -> PyException {
    policy("Xe case is not LOADED (the residual would be counted twice)")
}

fn reading_with(fraction: &Value) -> Value {
    dict(vec![
        ("allocations", s("MEV")),
        ("system_margin", fraction.clone()),
        ("reserve_kg", f(0.0)),
        ("xe_case", s("LOADED")),
    ])
}

/// `rollup_v5(m, cfg, lines, xe_split, refs, fraction)`: the v3 roll-up arithmetic with the system-margin fraction as
/// the only free input: 0.10 (A9.26 bid basis) or 0.20 (historical / conservative sensitivity).
pub fn rollup_v5(cfg: &Value, lines: &[Value], split: &XeSplit, refs: &Refs, fraction: &Value) -> PyResult<Value> {
    let historical = py_eq(fraction, &f(SYSTEM_MARGIN));
    if historical {
        rules::assert_no_margin_relaxation(&reading_with(fraction))?;
    } else {
        rules::assert_bid_margin_reading(&reading_with(fraction))?;
    }
    let spec = if historical {
        RollupSpec {
            margin: Margin::V3Historical,
            fraction: SYSTEM_MARGIN,
            reading: rules::OWNER_READING,
            rule: rules::RULE_MQ10_TEXT,
            loaded_error: v5_loaded_error,
            unresolved: rules::unresolved,
        }
    } else {
        RollupSpec {
            margin: Margin::Bid,
            fraction: SYSTEM_MARGIN_BID,
            reading: V5_READING,
            rule: V5_RULE,
            loaded_error: v5_loaded_error,
            unresolved: unresolved_v5,
        }
    };
    rules::rollup_core(cfg, lines, split, refs, &spec)
}

/// `unresolved_v5(m, rec)`: v3 `_unresolved` with the A9.26 AL-09 provisional owner allocation named for what it is.
pub fn unresolved_v5(rec: &Value) -> PyResult<Vec<Value>> {
    if py::eq_str(g(rec, "line")?, "AL-09") {
        let v = g(g(rec, "value")?, "value_kg")?;
        if !py::is_none(v) {
            return Ok(vec![s(format!(
                "AL-09: {} {} kg (A9.26 section 2); replace with a design-derived CBE",
                AL09_STATUS.join(" / "),
                py::fmt_g_value(v)?
            ))]);
        }
    }
    rules::unresolved(rec)
}

/// `set_al09(line, m)`: A9.26 section 2, AL-09 = 1.0 kg PROVISIONAL_OWNER_ALLOCATION (harness separate).
pub fn set_al09(line: &Value) -> PyResult<Value> {
    let refused = !py::eq_str(g(line, "line")?, "AL-09")
        || !py::is_none(g(g(line, "value")?, "value_kg")?)
        || !py_eq(&py::get_or_none(line, "row54_combined_allocation_kg")?, &f(1.0));
    if refused {
        return Err(policy("v4 AL-09 is not the TBD_OWNER (MPV3Q-01) line this decision answers"));
    }
    let v = rules::line_mev_value(&f(AL09_KG), &Value::Null, &Value::Null, &f(rules::EQUIPMENT_MARGIN))?;
    if !py::eq_str(g(&v, "governs")?, "ALLOCATION_MEV") || !py_eq(g(&v, "value_kg")?, &f(AL09_KG)) {
        return Err(policy(format!(
            "AL-09 owner allocation did not become a {} kg MEV allocation: {}",
            py::repr_f(AL09_KG),
            py_repr(&v)
        )));
    }
    let status_v4 = g(line, "allocation_status")?.clone();
    let mut new = py::updated(
        line,
        vec![
            ("owner_allocation_kg", f(AL09_KG)),
            ("owner_allocation_status", strs(&AL09_STATUS)),
            (
                "allocation_status",
                s(format!(
                    "PROVISIONAL_OWNER_ALLOCATION / NOT_CBE / NOT_MEASURED: {} kg owner allocation for controls / \
                     electronics / valve drivers / flight sensors (A9.26 message 2 section 2; MPV3Q-01 OWNER_DECIDED \
                     A9.26); harness separate (AL-HAR, row-60 5/95 rule); not a row-54 value (row 54 gave 1.0 kg to \
                     controls + harness combined, kept in row54_combined_allocation_kg as history)",
                    format_g(AL09_KG, 6)
                )),
            ),
            ("allocation_status_v4", status_v4),
            ("cbe_status", s("TBD - replace with a design-derived CBE when available (A9.26 section 2)")),
            ("harness", s("SEPARATE: AL-HAR by the row-60 5/95 rule (A9.26 section 2; MQ-06); never inside AL-09")),
            ("value", v),
            (
                "evidence_class_of_value",
                s("owner-allocation (A9.26 PROVISIONAL_OWNER_ALLOCATION, MEV-level per MQ-01; not a CBE, not \
                   measured)"),
            ),
        ],
    );
    let mut answers = match g(line, "owner_answers_applied")? {
        Value::List(l) => l.clone(),
        other => {
            return Err(err("TypeError", format!("can only concatenate list (not \"{}\") to list", other.type_name())))
        }
    };
    answers.push(s(cite_a926(&[2])));
    py::as_dict_mut(&mut new).insert("owner_answers_applied", Value::List(answers));
    Ok(new)
}

// ======================================================================== v4 helpers (pinned v4 builder)
/// `_split_and_refs(v4)`: the LOADED Xe cases and the closure references of the committed flight roll-up.
pub fn split_and_refs(v4: &Value) -> PyResult<(XeSplit, Refs, Value)> {
    let mut roll = None;
    for r in py::iter(g(v4, "rollups")?)? {
        if py::eq_str(g(&r, "configuration")?, FLIGHT) {
            roll = Some(r);
            break;
        }
    }
    let roll = roll.ok_or_else(|| err("StopIteration", ""))?;
    let mut pairs = Vec::new();
    let mut refs: Refs = Vec::new();
    for w in py::iter(g(&roll, "wet")?)? {
        pairs.push((
            g(&w, "xe_case_kg")?.clone(),
            dict(vec![
                ("loaded_kg", g(&w, "xe_loaded_kg")?.clone()),
                ("residual_kg", g(&w, "residual_inside_case_kg")?.clone()),
            ]),
        ));
        let r = (
            g(&w, "reference")?.clone(),
            g(&w, "reference_kg")?.clone(),
            Value::Bool(py::eq_str(g(&w, "comparator")?, "<")),
        );
        if !refs.iter().any(|x| py_eq(&x.0, &r.0) && py_eq(&x.1, &r.1) && py_eq(&x.2, &r.2)) {
            refs.push(r);
        }
    }
    Ok((py::dict_pairs(pairs), refs, roll))
}

fn strip(r: &Value) -> Value {
    let mut out = r.clone();
    py::as_dict_mut(&mut out).remove("note");
    out
}

/// `{w["xe_case_kg"]: w for w in wet if w["reference"] == HARD}` as (key, row) pairs.
fn hard_rows(roll: &Value) -> PyResult<Vec<(Value, Value)>> {
    let mut pairs = Vec::new();
    for w in py::iter(g(roll, "wet")?)? {
        if py::eq_str(g(&w, "reference")?, HARD) {
            pairs.push((g(&w, "xe_case_kg")?.clone(), w.clone()));
        }
    }
    Ok(py::dict_pairs(pairs))
}

/// `sorted(d)` of a key -> row mapping.
fn sorted_rows(rows: &[(Value, Value)]) -> PyResult<Vec<(Value, Value)>> {
    let keys: Vec<Value> = rows.iter().map(|r| r.0.clone()).collect();
    let mut out = Vec::new();
    for k in py::sorted(&keys)? {
        let row = rows.iter().find(|r| py_eq(&r.0, &k)).expect("key present");
        out.push((k, row.1.clone()));
    }
    Ok(out)
}

fn lookup(rows: &[(Value, Value)], key: f64) -> PyResult<&Value> {
    rows.iter().find(|r| py_eq(&r.0, &f(key))).map(|r| &r.1).ok_or_else(|| err("KeyError", py::repr_f(key)))
}

fn case_role(c: &Value, planning: &str) -> Value {
    s(if py_eq(c, &f(2.0)) { planning } else { "SENSITIVITY CASE" })
}

// ======================================================================== build_doc
/// `build_doc()`: the mass_power_a9_v5 record.
pub fn build_doc(repo: &Path) -> PyResult<Value> {
    verify_pins(repo)?;
    let v4 = py::load_json(repo, pin("V4_JSON").0)?;
    let a926 = a9_26_message2(repo)?;
    let (split, refs, roll_v4) = split_and_refs(&v4)?;
    let lines_v4 = py::iter(g(g(&v4, "lines")?, FLIGHT)?)?;
    let cfg = s(FLIGHT);

    // identity 1: the v5 arithmetic at the v3 0.20 fraction reproduces the committed v4 roll-up
    let again = rollup_v5(&cfg, &lines_v4, &split, &refs, &f(SYSTEM_MARGIN))?;
    if !py_eq(&strip(&again), &strip(&roll_v4)) {
        return Err(policy("identity check failed: rollup_v5(0.20) does not reproduce the committed v4 roll-up"));
    }
    let mut lines = Vec::new();
    for ln in &lines_v4 {
        lines.push(if py::eq_str(g(ln, "line")?, "AL-09") { set_al09(ln)? } else { ln.clone() });
    }
    for (a, b) in lines.iter().zip(lines_v4.iter()) {
        let al = g(a, "line")?;
        if !py_eq(al, g(b, "line")?) || (!py::eq_str(al, "AL-09") && !py_eq(a, b)) {
            return Err(policy(format!(
                "{}: a line other than AL-09 changed (A9.26: no compensating reduction)",
                py_str(al)
            )));
        }
    }
    for (lid, kgv) in LINE_UPLIFT_LINES {
        let mut found = None;
        for x in &lines {
            if py::eq_str(g(x, "line")?, lid) {
                found = Some(x);
                break;
            }
        }
        let ln = found.ok_or_else(|| err("StopIteration", ""))?;
        let v = g(ln, "value")?;
        if !py_eq(g(v, "value_kg")?, &f(kgv)) || !py::eq_str(g(v, "governs")?, "MEV_PLANNING_FLOOR") {
            return Err(policy(format!(
                "{lid}: line-floor value {} != {} kg MEV planning floor (A9.26 s1)",
                py_repr(v),
                py::repr_f(kgv)
            )));
        }
    }

    let mut roll = rollup_v5(&cfg, &lines, &split, &refs, &f(SYSTEM_MARGIN_BID))?;
    {
        let note =
            format!("{}; v5: AL-09 1.0 kg (A9.26), 10 % system margin (A9.26 bid basis)", py_str(g(&roll_v4, "note")?));
        let d = py::as_dict_mut(&mut roll);
        d.insert("note", s(note));
        d.insert("system_margin_fraction", f(SYSTEM_MARGIN_BID));
        d.insert(
            "system_margin_basis",
            s("A9.26 message 2 section 1: 10 % system-level mass margin for the proposal / bid baseline (supersedes \
               the A9.14 MQ-02 20 % reading for the bid baseline only)"),
        );
    }
    // identity 2: the historical / conservative 20 % sensitivity is the pinned v3 rollup() on the v5 lines
    let hist = rollup_v5(&cfg, &lines, &split, &refs, &f(SYSTEM_MARGIN))?;
    let hist_v3 = rules::rollup(&cfg, &lines, &split, &refs)?;
    if !py_eq(&strip(&hist), &strip(&hist_v3)) {
        return Err(policy("identity check failed: rollup_v5(0.20) != pinned v3 rollup() on the v5 lines"));
    }

    // A9.26 section 3: owner arithmetic cross-check (STOP if materially different)
    let hard = hard_rows(&roll)?;
    let mut diffs: Vec<Value> = Vec::new();
    for (k, v) in EXPECTED_ROLLUP {
        let got = gn(&roll, k)?;
        if (got - v).abs() > MATERIAL_KG {
            diffs.push(s(format!("{k} {} vs ~{}", py::repr_f(got), py::repr_f(v))));
        }
    }
    for (c, v) in EXPECTED_WET {
        let w = gn(lookup(&hard, c)?, "wet_known_kg")?;
        if (w - v).abs() > MATERIAL_KG {
            diffs.push(s(format!("wet {} kg Xe {} vs ~{}", py::repr_f(c), py::repr_f(w), py::repr_f(v))));
        }
    }
    let lwv = g(&roll, "lines_without_value")?.clone();
    if !diffs.is_empty() || lwv.truthy() {
        let shown = if diffs.is_empty() { lwv } else { Value::List(diffs) };
        return Err(policy(format!(
            "STOP (A9.26 section 3): the governed builder differs materially from the owner's arithmetic: {}",
            py_repr(&shown)
        )));
    }
    for (_, w) in &hard {
        if !py::eq_str(g(w, "state")?, "DOES_NOT_CLOSE") {
            return Err(policy(
                "STOP: a HARD_40_WET case no longer DOES_NOT_CLOSE (A9.26 section 4 expects all three)",
            ));
        }
    }
    let hard_v4 = hard_rows(&roll_v4)?;
    let hard_hist = hard_rows(&hist)?;
    let hard_sorted = sorted_rows(&hard)?;
    let dry = gn(&roll, "dry_known_kg")?;
    let nominal = gn(&roll, "nominal_dry_known_kg")?;
    let bid = 1.0 + SYSTEM_MARGIN_BID;

    // ---- closure vs 40 kg per loaded Xe case (A9.26 section 4)
    let mut closure = Vec::new();
    for (c, w) in &hard_sorted {
        let cn = py::num(c)?;
        let max_dry = crate::mass::pyfmt::rk(gn(w, "reference_kg")? - cn);
        let max_nominal = crate::mass::pyfmt::rk(max_dry / bid);
        closure.push(dict(vec![
            ("xe_case_kg", c.clone()),
            ("xe_case_role", case_role(c, "PLANNING / REFERENCE CASE (not the selected Xe load)")),
            ("requirement", s("complete flight wet mass < 40 kg (HARD_40_WET; not relaxed)")),
            ("max_allowable_dry_kg_strictly_below", f(max_dry)),
            ("max_allowable_nominal_dry_kg_strictly_below", f(max_nominal)),
            ("dry_planning_kg", g(&roll, "dry_known_kg")?.clone()),
            ("wet_planning_kg", g(w, "wet_known_kg")?.clone()),
            ("state", g(w, "state")?.clone()),
            ("exceedance_kg", py::get_or_none(w, "exceedance_kg")?),
            ("dry_reduction_needed_kg_more_than", rk(dry - max_dry)),
            ("nominal_dry_reduction_needed_kg_more_than", rk(nominal - max_nominal)),
            (
                "nonharness_nominal_reduction_kg_at_least",
                g(g(w, "redesign_need")?, "nonharness_nominal_reduction_kg_at_least")?.clone(),
            ),
            (
                "rule",
                s("the reduction comes from CBE / quotation / design re-base, integration and structural optimisation \
                   (mass-closure actions); never from requirement relaxation, margin relaxation or selecting the Xe \
                   load to make compliance easier"),
            ),
        ]));
    }

    // ---- proposal design target (A9.26 section 5)
    let pt_dry = crate::mass::pyfmt::rk(PT_NOMINAL_DRY_MAX_KG * bid);
    let mut pt_cases = Vec::new();
    for (c, _) in &hard_sorted {
        let cn = py::num(c)?;
        let wet = crate::mass::pyfmt::rk(pt_dry + cn);
        pt_cases.push(dict(vec![
            ("xe_case_kg", c.clone()),
            ("role", case_role(c, "PLANNING / REFERENCE CASE (not the selected Xe load)")),
            ("wet_target_kg", f(wet)),
            ("vs_40kg", s(if wet < 40.0 { "BELOW_40_KG" } else { "AT_OR_ABOVE_40_KG" })),
            ("difference_to_40kg_kg", rk(40.0 - wet)),
            ("nominal_dry_needed_for_lt_40kg_kg_strictly_below", rk((40.0 - cn) / bid)),
        ]));
    }
    let mut pt_ref = None;
    for x in &pt_cases {
        if py_eq(g(x, "xe_case_kg")?, &f(PT_XE_REFERENCE_KG)) {
            pt_ref = Some(x.clone());
            break;
        }
    }
    let pt_ref = pt_ref.ok_or_else(|| err("StopIteration", ""))?;
    let pt_wet = gn(&pt_ref, "wet_target_kg")?;
    if pt_wet != PT_WET_REFERENCE_KG {
        return Err(policy(format!("proposal target arithmetic {} != owner 39.4 kg (A9.26 s5)", py::repr_f(pt_wet))));
    }
    let proposal_target = dict(vec![
        ("label", s("PROPOSAL DESIGN TARGET - DESIGN TARGET, NOT ACHIEVED EVIDENCE (A9.26 section 5)")),
        ("nominal_dry_max_kg", f(PT_NOMINAL_DRY_MAX_KG)),
        ("comparator", s("<=")),
        ("system_margin_fraction", f(SYSTEM_MARGIN_BID)),
        ("dry_target_kg", f(pt_dry)),
        ("xe_reference_case_kg", f(PT_XE_REFERENCE_KG)),
        ("wet_target_at_reference_kg", f(pt_wet)),
        (
            "arithmetic",
            s(format!(
                "{} x 1.10 + {} = {} kg wet",
                format_g(PT_NOMINAL_DRY_MAX_KG, 6),
                format_g(PT_XE_REFERENCE_KG, 6),
                format_g(pt_wet, 6)
            )),
        ),
        ("by_xe_case", Value::List(pt_cases.clone())),
        (
            "gap_from_current_planning_rollup",
            dict(vec![
                ("nominal_dry_reduction_needed_kg", rk(nominal - PT_NOMINAL_DRY_MAX_KG)),
                ("dry_reduction_needed_kg", rk(dry - pt_dry)),
                ("basis", s("current provisional planning / evidence roll-up (this record) minus the design target")),
            ]),
        ),
        (
            "xe_rule",
            s("the 2 kg Xe case is a planning / reference case only, not the final selected Xe load; 5 kg and 10 kg \
               are carried as sensitivities (the flight Xe load is not yet frozen)"),
        ),
        (
            "not",
            strs(&[
                "achieved evidence",
                "a CBE",
                "a mass-compliance PASS",
                "the internal allocation target",
                "a selected Xe load",
            ]),
        ),
        (
            "owner_quotes",
            list(
                ["target", "target_arith", "target_label", "xe_reference", "xe_not_selected", "xe_sensitivities"]
                    .map(q),
            ),
        ),
    ]);

    // ---- internal allocation target (A9.26 section 6)
    let br = g(&v4, "budget_reference")?.clone();
    let mut alloc = Vec::new();
    for ln in &lines {
        let lid = g(ln, "line")?;
        if py::eq_str(lid, "AL-HAR") {
            continue;
        }
        let is09 = py::eq_str(lid, "AL-09");
        let kgv = if is09 { g(ln, "owner_allocation_kg")? } else { g(ln, "row54_allocation_kg")? };
        alloc.push(dict(vec![
            ("line", lid.clone()),
            ("allocation_kg", kgv.clone()),
            (
                "basis",
                s(if is09 {
                    "A9.26 PROVISIONAL_OWNER_ALLOCATION (controls only; harness separate)"
                } else {
                    "owner row-54 allocation (MEV-level, MQ-01)"
                }),
            ),
        ]));
    }
    let a_vals: Vec<Value> = alloc.iter().map(|a| g(a, "allocation_kg").cloned()).collect::<PyResult<_>>()?;
    let a_sum = crate::mass::pyfmt::rk(py::sum(&a_vals)?);
    let br_sum = g(&br, "row54_allocation_sum_kg")?;
    if !py_eq(&f(a_sum), br_sum) {
        return Err(policy(format!(
            "allocation sum {} != row-54 sum {} (AL-09 controls 1.0 kg replaces the row-54 controls + harness 1.0 kg \
             one for one)",
            py::repr_f(a_sum),
            py_str(br_sum)
        )));
    }
    let a_har = rules::harness_row60(&f(a_sum), &f(HARNESS_FRACTION))?;
    let a_nom = crate::mass::pyfmt::rk(a_sum + a_har);
    let a_sm = rules::system_margin_bid(&f(a_nom), &f(SYSTEM_MARGIN_BID), &f(0.0))?;
    let a_total = gn(&a_sm, "total_kg")?;
    let mut wet_alloc = Vec::new();
    for (c, _) in &hard_sorted {
        wet_alloc.push(dict(vec![("xe_case_kg", c.clone()), ("wet_kg", rk(a_total + py::num(c)?))]));
    }
    let internal_target = dict(vec![
        ("label", s("INTERNAL ALLOCATION TARGET - NOT EVIDENCE OF MASS COMPLIANCE (A9.26 section 6)")),
        ("lines", Value::List(alloc)),
        ("nonharness_allocation_sum_kg", f(a_sum)),
        ("harness_kg", f(a_har)),
        ("harness_rule", s("row 60 / MQ-06: 0.05/0.95 x the non-harness allocation sum (harness separate from AL-09)")),
        ("nominal_dry_kg", f(a_nom)),
        ("system_margin_fraction", f(SYSTEM_MARGIN_BID)),
        ("system_margin_kg", g(&a_sm, "system_margin_kg")?.clone()),
        ("dry_kg", g(&a_sm, "total_kg")?.clone()),
        ("wet_by_loaded_case", Value::List(wet_alloc)),
        (
            "not",
            strs(&[
                "evidence of mass compliance",
                "the <= 34 kg proposal nominal-dry target",
                "a CBE",
                "the current planning / evidence roll-up (the AL-04 / AL-07 / AL-08 evidence floors exceed their \
                 row-54 allocations)",
            ]),
        ),
        (
            "historical_provenance",
            dict(vec![
                (
                    "label",
                    s("HISTORICAL / INTERNAL ALLOCATION PROVENANCE (A9.26 section 6; not the active bid mass basis)"),
                ),
                ("row54_allocation_sum_kg", br_sum.clone()),
                ("system_margin_kg", g(&br, "system_margin_kg")?.clone()),
                ("dry_budget_kg", g(&br, "dry_budget_kg")?.clone()),
                (
                    "arithmetic",
                    s("24 kg + 20 % = 28.8 kg (A9.14 MQ-02; row-54 controls + harness 1.0 kg line, no separate \
                       harness)"),
                ),
                ("source", s("budget_reference (carried from v4 unchanged)")),
            ]),
        ),
        ("owner_quotes", list(["row54", "row54_history", "alloc_label", "alloc_not_target"].map(q))),
    ]);
    let budget_reference = py::updated(
        &br,
        vec![(
            "a9_26_status",
            s("HISTORICAL / INTERNAL ALLOCATION PROVENANCE (A9.26 section 6): the 24 kg + 20 % = 28.8 kg owner budget \
               reference is not the active bid mass basis; the current allocation view is internal_allocation_target"),
        )],
    );

    // ---- margin audit (A9.26 section 1)
    let fac_bid = crate::mass::pyfmt::rk((1.0 + rules::EQUIPMENT_MARGIN) * (1.0 + SYSTEM_MARGIN_BID));
    let fac_hist = crate::mass::pyfmt::rk((1.0 + rules::EQUIPMENT_MARGIN) * (1.0 + SYSTEM_MARGIN));
    if (fac_bid, fac_hist) != (1.32, 1.44) {
        return Err(policy(format!(
            "effective factors {} / {} != owner 1.32 / 1.44 (A9.26 section 1)",
            py::repr_f(fac_bid),
            py::repr_f(fac_hist)
        )));
    }
    let mut audit = Vec::new();
    for ln in &lines {
        let v = g(ln, "value")?;
        let lid = g(ln, "line")?;
        if py::eq_str(lid, "AL-HAR") {
            audit.push(dict(vec![
                ("line", s("AL-HAR")),
                ("value_kg", g(&roll, "harness_kg")?.clone()),
                ("governs", s("HARNESS_POLICY_ROW60")),
                ("contains_line_uplift", Value::Bool(false)),
                ("line_uplift_factor", Value::Null),
                ("system_margin_factor", f(1.0 + SYSTEM_MARGIN_BID)),
                ("effective_factor", Value::Null),
                ("note", s("rule value (5/95 of the non-harness nominal), then the 10 % system margin")),
            ]));
            continue;
        }
        let floor = py::eq_str(g(v, "governs")?, "MEV_PLANNING_FLOOR");
        let contained = if floor {
            "20 % LINE-LEVEL planning uplift (MEV planning floor = 1.20 x evidence floor; not a CBE)".to_string()
        } else {
            format!(
                "owner MEV allocation (MQ-01: equipment margin inside; no row-57 uplift added){}",
                if py::eq_str(lid, "AL-09") { " - A9.26 PROVISIONAL_OWNER_ALLOCATION" } else { "" }
            )
        };
        audit.push(dict(vec![
            ("line", lid.clone()),
            ("value_kg", g(v, "value_kg")?.clone()),
            ("governs", g(v, "governs")?.clone()),
            ("evidence_floor_cbe_kg", g(ln, "evidence_floor_cbe_kg")?.clone()),
            ("contains_line_uplift", Value::Bool(floor)),
            ("line_uplift_factor", if floor { f(1.0 + rules::EQUIPMENT_MARGIN) } else { Value::Null }),
            ("system_margin_factor", f(1.0 + SYSTEM_MARGIN_BID)),
            ("effective_factor", f(if floor { fac_bid } else { 1.0 + SYSTEM_MARGIN_BID })),
            ("effective_factor_historical_20pct", f(if floor { fac_hist } else { 1.0 + SYSTEM_MARGIN })),
            ("value_after_system_margin_kg", rk(gn(v, "value_kg")? * (1.0 + SYSTEM_MARGIN_BID))),
            ("margin_contained", s(contained)),
        ]));
    }
    let margin_audit = dict(vec![
        (
            "decision",
            s(format!(
                "INTENTIONAL_GOVERNANCE (A9.26 section 1): the 20 % line-level uplift is kept on the floor-derived \
                 lines AL-04 / AL-07 / AL-08 and the system margin is 10 % for the bid basis; effective line x system \
                 factor {} (not {}, the historical 20 % reading)",
                format_g(fac_bid, 6),
                format_g(fac_hist, 6)
            )),
        ),
        ("line_uplift_lines", strs(&["AL-04", "AL-07", "AL-08"])),
        ("line_uplift_fraction", f(rules::EQUIPMENT_MARGIN)),
        ("system_margin_fraction", f(SYSTEM_MARGIN_BID)),
        ("effective_factor_floor_lines", f(fac_bid)),
        ("effective_factor_floor_lines_historical", f(fac_hist)),
        ("harness_note", s("the row-60 harness (5/95) applies to every line before the system margin")),
        ("lines", Value::List(audit)),
        ("owner_quotes", list(["line_uplift", "factor", "floors_unchanged", "margin", "historical"].map(q))),
    ]);

    // ---- historical / conservative sensitivity (20 %)
    let mut rec_hist = vec![];
    for k in [
        "nonharness_known_kg",
        "harness_kg",
        "nominal_dry_known_kg",
        "system_margin_kg",
        "dry_known_kg",
        "lines_without_value",
    ] {
        rec_hist.push((k, g(&hist, k)?.clone()));
    }
    let mut hist_wet = Vec::new();
    for (c, w) in sorted_rows(&hard_hist)? {
        hist_wet.push(dict(vec![
            ("xe_case_kg", c),
            ("wet_known_kg", g(&w, "wet_known_kg")?.clone()),
            ("state", g(&w, "state")?.clone()),
            ("exceedance_kg", py::get_or_none(&w, "exceedance_kg")?),
        ]));
    }
    rec_hist.push(("reading", s(format!("HISTORICAL / CONSERVATIVE SENSITIVITY - {}", py_str(g(&hist, "reading")?)))));
    rec_hist.push((
        "role",
        s("HISTORICAL / CONSERVATIVE SENSITIVITY (never the active roll-up; the active bid roll-up is rollups[0])"),
    ));
    rec_hist.push(("system_margin_fraction", f(SYSTEM_MARGIN)));
    rec_hist.push(("wet_by_loaded_case", Value::List(hist_wet)));
    rec_hist.push((
        "basis",
        s("pinned v3 rollup() (0.20 system margin, row-60 harness, LOADED Xe) on the v5 lines (AL-09 = 1.0 kg); \
           identical to the v5 arithmetic at 0.20"),
    ));
    let mut v4_wet = Vec::new();
    for (c, w) in sorted_rows(&hard_v4)? {
        v4_wet.push(dict(vec![
            ("xe_case_kg", c),
            ("wet_known_kg", g(&w, "wet_known_kg")?.clone()),
            ("state", g(&w, "state")?.clone()),
        ]));
    }
    let (v4_json_rel, v4_json_sha) = pin("V4_JSON");
    let historical = dict(vec![
        (
            "label",
            s("HISTORICAL / CONSERVATIVE SENSITIVITY (A9.14 MQ-02 20 % system margin; superseded for the proposal / \
               bid baseline by A9.26 section 1; NOT the active bid basis)"),
        ),
        ("recomputed_with_al09", dict(rec_hist)),
        (
            "v4_al09_excluded_history",
            dict(vec![
                ("dry_known_kg", g(&roll_v4, "dry_known_kg")?.clone()),
                ("nonharness_known_kg", g(&roll_v4, "nonharness_known_kg")?.clone()),
                ("harness_kg", g(&roll_v4, "harness_kg")?.clone()),
                ("nominal_dry_known_kg", g(&roll_v4, "nominal_dry_known_kg")?.clone()),
                ("system_margin_kg", g(&roll_v4, "system_margin_kg")?.clone()),
                ("lines_without_value", g(&roll_v4, "lines_without_value")?.clone()),
                ("wet_by_loaded_case", Value::List(v4_wet)),
                (
                    "label",
                    s("HISTORICAL (mass_power_a9_v4): dry_known_partial - AL-09 had no value and was excluded; not a \
                       complete dry mass; never the active roll-up"),
                ),
                ("source", dict(vec![("path", s(v4_json_rel)), ("sha256", s(v4_json_sha))])),
            ]),
        ),
        ("owner_quotes", list(["sensitivity", "historical"].map(q))),
    ]);

    // ---- old -> new (v4 -> v5)
    let mut changes = vec![
        dict(vec![
            ("quantity", s("AL-09 value (kg)")),
            ("old", Value::Null),
            ("new", f(AL09_KG)),
            ("basis", s("A9.26 section 2 (MPV3Q-01 closed)")),
        ]),
        dict(vec![
            ("quantity", s("system margin fraction (active bid basis)")),
            ("old", f(SYSTEM_MARGIN)),
            ("new", f(SYSTEM_MARGIN_BID)),
            ("basis", s("A9.26 section 1 (20 % kept as historical / conservative sensitivity)")),
        ]),
        dict(vec![
            ("quantity", s("lines_without_value")),
            ("old", g(&roll_v4, "lines_without_value")?.clone()),
            ("new", g(&roll, "lines_without_value")?.clone()),
        ]),
    ];
    for k in ["nonharness_known_kg", "harness_kg", "nominal_dry_known_kg", "system_margin_kg", "dry_known_kg"] {
        changes.push(dict(vec![("quantity", s(k)), ("old", g(&roll_v4, k)?.clone()), ("new", g(&roll, k)?.clone())]));
    }
    let wet_old = py::iter(g(&roll_v4, "wet")?)?;
    let wet_new = py::iter(g(&roll, "wet")?)?;
    for (w_old, w_new) in wet_old.iter().zip(wet_new.iter()) {
        if !py_eq(g(w_old, "xe_case_kg")?, g(w_new, "xe_case_kg")?)
            || !py_eq(g(w_old, "reference")?, g(w_new, "reference")?)
        {
            return Err(policy("v4 / v5 wet rows are not aligned"));
        }
        let tag = format!("({}, {} kg Xe)", py_str(g(w_new, "reference")?), py::fmt_g_value(g(w_new, "xe_case_kg")?)?);
        changes.push(dict(vec![
            ("quantity", s(format!("wet_known_kg {tag}"))),
            ("old", g(w_old, "wet_known_kg")?.clone()),
            ("new", g(w_new, "wet_known_kg")?.clone()),
            ("state_old", g(w_old, "state")?.clone()),
            ("state_new", g(w_new, "state")?.clone()),
        ]));
        for k in ["exceedance_kg", "margin_to_reference_kg"] {
            let (o, n) = (py::get(w_old, k)?, py::get(w_new, k)?);
            if o.is_some() || n.is_some() {
                changes.push(dict(vec![
                    ("quantity", s(format!("{k} {tag}"))),
                    ("old", o.cloned().unwrap_or(Value::Null)),
                    ("new", n.cloned().unwrap_or(Value::Null)),
                ]));
            }
        }
        let ro = py::get(w_old, "redesign_need")?.filter(|x| x.truthy()).cloned();
        let rn = py::get(w_new, "redesign_need")?.filter(|x| x.truthy()).cloned();
        if ro.is_some() || rn.is_some() {
            let pick = |r: &Option<Value>| -> PyResult<Value> {
                match r {
                    Some(x) => py::get_or_none(x, "nonharness_nominal_reduction_kg_at_least"),
                    None => Ok(Value::Null),
                }
            };
            changes.push(dict(vec![
                ("quantity", s(format!("non-harness nominal reduction needed {tag}"))),
                ("old", pick(&ro)?),
                ("new", pick(&rn)?),
            ]));
        }
    }

    let hard_wets: Vec<f64> = hard_sorted.iter().map(|(_, w)| gn(w, "wet_known_kg")).collect::<PyResult<_>>()?;
    let hierarchy = dict(vec![
        ("requirement", s("complete flight wet mass < 40 kg (HARD_40_WET; not relaxed)")),
        (
            "proposal_design_target",
            s(format!(
                "nominal dry <= {} kg, 10 % system margin, {} kg Xe planning reference -> ~{} kg wet (DESIGN TARGET, not \
                 achieved evidence)",
                format_g(PT_NOMINAL_DRY_MAX_KG, 6),
                format_g(PT_XE_REFERENCE_KG, 6),
                format_g(pt_wet, 6)
            )),
        ),
        (
            "current_provisional_planning_rollup",
            s(format!(
                "~{} kg dry after the 10 % system margin; ~{} kg wet for {} kg Xe planning cases",
                format_fixed(dry, 2),
                hard_wets.iter().map(|w| format_fixed(*w, 2)).collect::<Vec<_>>().join(" / "),
                hard_sorted
                    .iter()
                    .map(|(c, _)| py::fmt_g_value(c))
                    .collect::<PyResult<Vec<_>>>()?
                    .join(" / ")
            )),
        ),
        ("current_status", s(MASS_STATUS)),
        (
            "mass_closure_actions",
            list(CLOSURE_ACTIONS.iter().map(|a| {
                if a.1 == "AL-HAR" || a.1 == "system" {
                    s(a.2)
                } else {
                    s(format!("{} {}", a.1, a.2))
                }
            })),
        ),
        ("rule", s("do not claim current mass compliance (A9.26 section 7)")),
    ]);
    let exceed_2 = gn(lookup(&hard, 2.0)?, "exceedance_kg")?;
    let mass_status = dict(vec![
        ("status", s(MASS_STATUS)),
        (
            "reading",
            s("CURRENT PROVISIONAL PLANNING / EVIDENCE FLOOR (not a complete CBE: the lines are owner MEV allocations, \
               MEV planning floors from analog / preliminary-design floors and the A9.26 provisional AL-09 allocation; \
               no CBE, no measured mass; A9.26 sections 3-4, 7)"),
        ),
        (
            "mass_compliance",
            s(format!(
                "INCOMPLETE_EVIDENCE / NOT_YET_CLOSED: no PASS; the requirement complete flight wet mass < 40 kg is not \
                 relaxed; the 2 kg Xe planning / reference case is {} kg above it under the present preliminary \
                 roll-up (A9.26 section 4)",
                format_fixed(exceed_2, 4)
            )),
        ),
        (
            "xe_cases",
            s("loaded Xe 2 / 5 / 10 kg: 2 kg is a PLANNING / REFERENCE CASE, 5 and 10 kg are SENSITIVITY CASES; the \
               flight Xe load is NOT YET FROZEN and none of them is the selected Xe load (A9.26 section 5; A9.25 \
               message 8 section 7)"),
        ),
        ("bid_hierarchy", hierarchy),
        ("source", s("A9.26 message 2 (mass_power_a9_v5 is the active flight mass source)")),
        ("v4_mass_status_history", g(&v4, "mass_status")?.clone()),
        ("owner_quotes", list(["status", "no_pass", "no_compliance"].map(q))),
    ]);

    let mut items_v3 = py::iter(g(&v4, "items_v3")?)?;
    for it in items_v3.iter_mut() {
        let id = g(it, "id")?.clone();
        if py::eq_str(&id, "MPV3-01") {
            py::as_dict_mut(it).insert(
                "v5_status",
                s("SUPERSEDED_FOR_THE_PROPOSAL_BID_BASELINE_ONLY by MPV5-01 (A9.26 section 1: 10 %); the 0.20 reading \
                   is the HISTORICAL / CONSERVATIVE SENSITIVITY"),
            );
        } else if py::eq_str(&id, "MPV3-06") {
            py::as_dict_mut(it).insert(
                "v5_status",
                s("ANSWERED by MPV5-02 (A9.26 section 2: 1.0 kg PROVISIONAL_OWNER_ALLOCATION; MPV3Q-01 closed)"),
            );
        }
    }
    let items_v5 = list([
        dict(vec![
            ("id", s("MPV5-01")),
            ("name", s("system margin, active proposal / bid basis (fraction of the current pre-margin nominal dry)")),
            ("value", f(SYSTEM_MARGIN_BID)),
            ("units", s("1")),
            ("evidence_class", s("owner-allocation")),
            ("source", list([s(cite_a926(&[1]))])),
            (
                "status",
                s("OWNER_DECIDED_A9_26 (bid basis; the 20 % MPV3-01 reading is kept as historical / conservative \
                   sensitivity)"),
            ),
            ("replaces", s("MPV3-01 (0.2) for the proposal / bid baseline only")),
        ]),
        dict(vec![
            ("id", s("MPV5-02")),
            ("name", s("AL-09 controls / electronics / valve drivers / flight sensors allocation (harness separate)")),
            ("value", f(AL09_KG)),
            ("units", s("kg")),
            ("evidence_class", s("owner-allocation")),
            ("source", list([s(cite_a926(&[2]))])),
            ("status", s(AL09_STATUS.join(" / "))),
            ("replaces", s("MPV3-06 (TBD_OWNER, MPV3Q-01)")),
        ]),
        dict(vec![
            ("id", s("MPV5-03")),
            ("name", s("proposal design target: nominal dry mass")),
            ("value", f(PT_NOMINAL_DRY_MAX_KG)),
            ("units", s("kg (<=)")),
            ("evidence_class", s("owner-allocation")),
            ("source", list([s(cite_a926(&[5]))])),
            ("status", s("DESIGN_TARGET_NOT_ACHIEVED_EVIDENCE")),
        ]),
    ]);
    let margin_convention = py::updated(
        g(&v4, "margin_convention")?,
        vec![
            (
                "system_margin",
                s("0.10 x the current nominal dry (A9.26 section 1, active proposal / bid basis); no reserve"),
            ),
            (
                "system_margin_historical",
                s("0.20 x the current nominal dry (A9.14 MQ-02): HISTORICAL / CONSERVATIVE SENSITIVITY only \
                   (historical_conservative_sensitivity_20pct)"),
            ),
            (
                "line_uplift",
                s("20 % line-level planning uplift kept on the floor-derived lines AL-04 / AL-07 / AL-08 (MEV planning \
                   floors, not CBEs); effective line x system factor 1.32 (A9.26 section 1)"),
            ),
        ],
    );
    let open_register = py::updated(
        g(&v4, "open_register_status")?,
        vec![
            (
                "MQ-02",
                s("OWNER_DECIDED (A9.14); SUPERSEDED_FOR_THE_PROPOSAL_BID_BASELINE_ONLY by A9.26 section 1 (10 % \
                   system margin); the 20 % reading is kept as historical / conservative sensitivity"),
            ),
            (
                "MPV3Q-01",
                s("OWNER_DECIDED (A9.26 message 2 section 2: AL-09 = 1.0 kg PROVISIONAL_OWNER_ALLOCATION / NOT_CBE / \
                   NOT_MEASURED; harness separate)"),
            ),
        ],
    );
    let mut oq = py::iter(g(&v4, "open_owner_questions")?)?;
    for x in oq.iter_mut() {
        if py::eq_str(g(x, "id")?, "MPV3Q-01") {
            let d = py::as_dict_mut(x);
            d.insert("status", s("CLOSED_OWNER_DECIDED_A9_26"));
            d.insert(
                "answer",
                s(format!(
                    "AL-09 = {} kg, {}; harness separate under the 5/95 rule; no compensating reduction on another \
                     line; replace with a design-derived CBE when available",
                    format_g(AL09_KG, 6),
                    AL09_STATUS.join(" / ")
                )),
            );
            d.insert("decided_by", s(cite_a926(&[2])));
        }
    }
    let (md_rel, md_sha) = pin("A9_26_MD");
    let (js_rel, js_sha) = pin("A9_26_JSON");
    let mut owner_answers = py::iter(g(&v4, "owner_answers_applied")?)?;
    let applied: [(i64, &str, &str); 6] = [
        (
            1,
            quote("margin"),
            "rollup_v5 / system_margin_bid: 10 % of the current pre-margin nominal dry (active bid basis); 20 % \
             roll-up kept as historical_conservative_sensitivity_20pct",
        ),
        (
            1,
            quote("line_uplift"),
            "AL-04 / AL-07 / AL-08 MEV planning floors unchanged (4.2048 / 6.0 / 5.9148 kg); margin_audit effective \
             factor 1.32",
        ),
        (2, quote("al09"), "AL-09 value 1.0 kg ALLOCATION_MEV (owner_allocation_kg); MPV3Q-01 closed"),
        (2, quote("harness"), "AL-HAR stays the row-60 5/95 rule on the non-harness nominal"),
        (5, quote("target"), "proposal_design_target"),
        (6, quote("alloc_label"), "internal_allocation_target; budget_reference relabelled historical provenance"),
    ];
    for (sec, qt, how) in applied {
        owner_answers.push(dict(vec![
            ("key", s("A9.26")),
            ("id", s(format!("message 2 section {sec}"))),
            ("quote", s(qt)),
            ("path", s(md_rel)),
            ("md_sha256", s(md_sha)),
            ("json_path", s(js_rel)),
            ("json_sha256", s(js_sha)),
            ("how_applied", s(how)),
        ]));
    }

    let mut quotes_rec = Vec::new();
    for (k, _, _) in quotes() {
        quotes_rec.push((*k, q(k)));
    }
    let a926_full = py::updated(&a926, vec![("quotes", dict(quotes_rec))]);
    let (v4_md_rel, v4_md_sha) = pin("V4_MD");
    let (v4b_rel, v4b_sha) = pin("V4_BUILDER");
    let mut wet_by_case = Vec::new();
    let mut state_by_case = Vec::new();
    for (c, w) in &hard_sorted {
        wet_by_case.push((py_str(c), g(w, "wet_known_kg")?.clone()));
        state_by_case.push((py_str(c), g(w, "state")?.clone()));
    }
    let mut v4_wet_by_case = Vec::new();
    for (c, w) in sorted_rows(&hard_v4)? {
        v4_wet_by_case.push((py_str(&c), g(&w, "wet_known_kg")?.clone()));
    }
    let flight_rollup = dict(vec![
        ("configuration", s(FLIGHT)),
        ("dry_known_kg", g(&roll, "dry_known_kg")?.clone()),
        ("nominal_dry_known_kg", g(&roll, "nominal_dry_known_kg")?.clone()),
        ("system_margin_fraction", f(SYSTEM_MARGIN_BID)),
        ("wet_known_kg_by_loaded_case", owned_dict(wet_by_case)),
        ("hard_40_wet_state_by_loaded_case", owned_dict(state_by_case)),
        ("label", s("CURRENT PROVISIONAL PLANNING / EVIDENCE FLOOR (not a complete CBE)")),
        ("numerically_unchanged_vs_v4", Value::Bool(false)),
        (
            "v4",
            dict(vec![
                ("dry_known_kg", g(&roll_v4, "dry_known_kg")?.clone()),
                ("label", s("HISTORICAL (mass_power_a9_v4): dry_known_partial (AL-09 excluded; 20 % margin)")),
                ("wet_known_kg_by_loaded_case", owned_dict(v4_wet_by_case)),
            ]),
        ),
        ("basis", s("rollup_v5 (v3 rule functions, 10 % system margin, A9.26) on the v4 lines with AL-09 = 1.0 kg")),
    ]);
    let mut actions = Vec::new();
    for (i, ln, a, qt, det) in CLOSURE_ACTIONS {
        actions.push(dict(vec![
            ("id", s(i)),
            ("line", s(ln)),
            ("action", s(a)),
            ("owner_quote", s(qt)),
            ("detail", s(det)),
            ("state", s("OPEN")),
        ]));
    }

    let mut d = v4.clone();
    {
        let dd = py::as_dict_mut(&mut d);
        let entries: Vec<(&str, Value)> = vec![
            ("schema", s(SCHEMA_ID)),
            ("id", s(SCHEMA_ID)),
            ("lane", s("a9_26_mass_budget_policy")),
            (
                "directive",
                s("A9.26 message 2 MASS_BUDGET_DECISIONS_PRE_BID_FREEZE (owner 2026-10-05): 10 % system margin for the \
                   proposal / bid basis (20 % kept as historical / conservative sensitivity), 20 % line uplift kept on \
                   AL-04 / AL-07 / AL-08, AL-09 = 1.0 kg PROVISIONAL_OWNER_ALLOCATION (MPV3Q-01 closed), 40 kg wet \
                   requirement not relaxed, proposal design target, internal allocation target"),
            ),
            (
                "title",
                s("A9 mass + power integration v5: v4 with the A9.26 bid mass policy (10 % system margin, AL-09 1.0 kg \
                   provisional owner allocation); roll-ups recomputed; MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED"),
            ),
            ("status", s("A9_26_MASS_POLICY_APPLIED_PROVISIONAL_PLANNING_FLOOR_MASS_NOT_YET_CLOSED")),
            ("date", s(DATE)),
            ("base_commit", s(BASE_COMMIT)),
            ("generated_by", s(SCRIPT_REL)),
            ("companion_document", s(format!("{LANE_REL}/{MD_NAME}"))),
            ("test", s(TEST_REL)),
            (
                "revision_of",
                dict(vec![
                    ("path", s(v4_json_rel)),
                    ("sha256", s(v4_json_sha)),
                    ("md", s(v4_md_rel)),
                    ("md_sha256", s(v4_md_sha)),
                    ("builder", s(v4b_rel)),
                    ("builder_sha256", s(v4b_sha)),
                    (
                        "rule",
                        s("v4 immutable history: read as data (JSON); v3 rule functions reused (pinned builder); v4 / \
                           v3 / v2 never edited"),
                    ),
                    ("v4_revision_of", g(&v4, "revision_of")?.clone()),
                ]),
            ),
            ("a9_26", a926_full),
            ("items_v3", Value::List(items_v3)),
            ("items_v5", items_v5),
            ("margin_convention", margin_convention),
            ("lines", dict(vec![(FLIGHT, Value::List(lines.clone()))])),
            ("rollups", list([roll.clone()])),
            ("flight_rollup_vs_40kg", list([flight_rollup])),
            ("closure_vs_40kg", Value::List(closure)),
            ("proposal_design_target", proposal_target),
            ("internal_allocation_target", internal_target),
            ("budget_reference", budget_reference),
            ("margin_audit", margin_audit),
            ("historical_conservative_sensitivity_20pct", historical),
            ("mass_closure_actions", Value::List(actions)),
            ("a9_26_changes_old_new", Value::List(changes)),
            ("mass_status", mass_status),
            ("open_register_status", open_register),
            ("open_owner_questions", Value::List(oq)),
            ("owner_answers_applied", Value::List(owner_answers)),
        ];
        for (k, v) in entries {
            dd.insert(k, v);
        }
        let mut wtin = Vec::new();
        for x in py::iter(g(&v4, "what_this_is_not")?)? {
            let t = py_str(&x)
                .replace(
                    "not a CBE: every value is an owner MEV allocation, an owner-stated MEV planning floor or TBD",
                    "not a CBE: every value is an owner MEV allocation, an owner-stated MEV planning floor or the A9.26 \
                     AL-09 provisional owner allocation",
                )
                .replace(
                    "not a margin relaxation: the 40 kg exceedance is reported with the redesign need (MQ-10)",
                    "not a builder-side margin relaxation: the 10 % system margin is the owner's A9.26 bid-basis policy \
                     (the 20 % roll-up is kept as historical / conservative sensitivity); the 40 kg exceedance is \
                     reported with the reduction needed (MQ-10)",
                );
            wtin.push(s(t));
        }
        wtin.push(s("not a mass-compliance claim: MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED (A9.26 sections 4 and 7)"));
        dd.insert("what_this_is_not", Value::List(wtin));
        let mut flags = py::iter(g(&v4, "recorder_flags")?)?;
        flags.push(s(
            "A9.26 (v5): MPV3Q-01 is closed here (OWNER_DECIDED A9.26); the owner-question state record \
             docs/budgets/owner_decisions/owner_questions_state_v5.json (built from the immutable mass / power v3) \
             still lists it as TBD_OWNER until an owner-question state successor applies A9.26 (not done in this lane)",
        ));
        flags.push(s(
            "A9.26 (v5): the AL-04 / AL-07 / AL-08 line uplift (1.20) plus the 10 % system margin is intentional \
             governance (effective 1.32), not an accidental double margin",
        ));
        dd.insert("recorder_flags", Value::List(flags));
    }
    let compliance = py::updated(
        g(&v4, "compliance")?,
        vec![
            (
                "no_new_numbers",
                s("every number is copied from pinned v4 / A9.26 or is deterministic arithmetic on those (v3 rule \
                   functions; the owner's approximate values are only cross-checked)"),
            ),
            (
                "no_margin_relaxation",
                s("assert_bid_margin_reading admits only the A9.26 10 % bid reading; the pinned v3 \
                   assert_no_margin_relaxation governs the 20 % sensitivity"),
            ),
            ("no_compensating_reduction", s("every line other than AL-09 is byte-identical to v4 (fail closed)")),
            (
                "no_pass",
                s("no mass PASS (MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED); no PASS for thermal, RF ratings, anode, \
                   ICP capacity; the power gate stays NOT_EVALUABLE"),
            ),
            (
                "pure",
                s("not wired into archengine; no frozen data, goldens, abep_sim physics module or v4 / v3 / v2 file \
                   touched"),
            ),
        ],
    );
    py::as_dict_mut(&mut d).insert("compliance", compliance);
    Ok(d)
}

fn owned_dict(entries: Vec<(String, Value)>) -> Value {
    let mut d = pyjson::Dict::new();
    for (k, v) in entries {
        d.insert(k, v);
    }
    Value::Dict(d)
}

// ======================================================================== markdown (v4 _table / _cell)
/// v4 `_cell(v)`: None -> '-', float -> format(v, 'g'), list / dict -> compact JSON, else str with '|' escaped.
pub fn cell(v: &Value) -> PyResult<String> {
    Ok(match v {
        Value::Null => "-".into(),
        Value::Float(x) => format_g(*x, 6),
        Value::List(_) | Value::Dict(_) => {
            pyjson::dumps(v, &DumpOptions { ensure_ascii: false, ..Default::default() })?
        }
        other => py_str(other).replace('|', "\\|").replace('\n', " "),
    })
}

/// v4 `_table(headers, rows)`.
pub fn table(headers: &[&str], rows: &[Vec<Value>]) -> PyResult<Vec<String>> {
    let mut out = vec![format!("| {} |", headers.join(" | ")), format!("|{}", "---|".repeat(headers.len()))];
    for r in rows {
        let cells = r.iter().map(cell).collect::<PyResult<Vec<_>>>()?;
        out.push(format!("| {} |", cells.join(" | ")));
    }
    out.push(String::new());
    Ok(out)
}

fn fg(v: &Value) -> PyResult<String> {
    py::fmt_g_value(v)
}

/// `render_md(d)`.
pub fn render_md(d: &Value) -> PyResult<String> {
    let r = &py::iter(g(d, "rollups")?)?[0];
    let a = g(d, "a9_26")?;
    let ms = g(d, "mass_status")?;
    let h = g(ms, "bid_hierarchy")?;
    let mut l: Vec<String> = vec![
        "# A9 mass + power integration v5 (A9.26 bid mass policy)".into(),
        String::new(),
        format!(
            "Generated by `{}` from `{LANE_REL}/{JSON_NAME}` (do not edit by hand; `--check` verifies). Status `{}`. \
             Base commit `{}`. Successor of `{}` (sha256 `{}`, immutable; every section not listed here is v4's). \
             Test `{}`.",
            py_str(g(d, "generated_by")?),
            py_str(g(d, "status")?),
            py_str(g(d, "base_commit")?),
            py_str(g(g(d, "revision_of")?, "path")?),
            py_str(g(g(d, "revision_of")?, "sha256")?),
            py_str(g(d, "test")?)
        ),
        String::new(),
        format!(
            "Authorization: {} message {} {} ({}, text sha256 `{}...`; `{}`, `{}`).",
            py_str(g(a, "decision")?),
            py_str(g(a, "message")?),
            py_str(g(a, "key")?),
            py_str(g(a, "utc")?),
            &py_str(g(a, "text_sha256")?)[..12],
            py_str(g(a, "md")?),
            py_str(g(a, "json")?)
        ),
        String::new(),
        format!("## Mass status: **{}**", py_str(g(ms, "status")?)),
        String::new(),
        format!("* Requirement: {}.", py_str(g(h, "requirement")?)),
        format!("* Proposal design target: {}.", py_str(g(h, "proposal_design_target")?)),
        format!(
            "* Current provisional planning / evidence roll-up: {}.",
            py_str(g(h, "current_provisional_planning_rollup")?)
        ),
        format!("* Current status: **{}** - {}.", py_str(g(h, "current_status")?), py_str(g(ms, "mass_compliance")?)),
        format!("* Xe cases: {}.", py_str(g(ms, "xe_cases")?)),
        format!("* Reading: {}.", py_str(g(ms, "reading")?)),
        format!("* Mass-closure actions: {}.", py::join_strs("; ", &py::iter(g(h, "mass_closure_actions")?)?)?),
        format!("* Rule: {}.", py_str(g(h, "rule")?)),
        String::new(),
        format!("## Current provisional planning / evidence roll-up - `{FLIGHT}` (10 % system margin, A9.26)"),
        String::new(),
    ];
    let audit = py::iter(g(g(d, "margin_audit")?, "lines")?)?;
    let mut rows = Vec::new();
    for ln in py::iter(g(g(d, "lines")?, FLIGHT)?)? {
        let lid = g(&ln, "line")?;
        let x = audit
            .iter()
            .rev()
            .find(|a| a.as_dict().and_then(|dd| dd.get("line")).is_some_and(|v| py_eq(v, lid)))
            .ok_or_else(|| err("KeyError", py_repr(lid)))?;
        if py::eq_str(lid, "AL-HAR") {
            rows.push(vec![
                lid.clone(),
                g(&ln, "name")?.clone(),
                g(r, "harness_kg")?.clone(),
                s("HARNESS_POLICY_ROW60 (5/95)"),
                s("-"),
                s("rule (not a CBE)"),
                s("-"),
            ]);
            continue;
        }
        let luf = g(x, "line_uplift_factor")?;
        rows.push(vec![
            lid.clone(),
            g(&ln, "name")?.clone(),
            g(g(&ln, "value")?, "value_kg")?.clone(),
            g(g(&ln, "value")?, "governs")?.clone(),
            if luf.truthy() { s(format!("x{} line uplift", fg(luf)?)) } else { s("none (MEV allocation)") },
            py::get_or_none(&ln, "evidence_class_of_value")?,
            g(&ln, "evidence_floor_cbe_kg")?.clone(),
        ]);
    }
    l.extend(table(
        &["line", "name", "value used (kg)", "basis", "line uplift", "evidence class", "evidence floor (CBE level)"],
        &rows,
    )?);
    let lwv = py::iter(g(r, "lines_without_value")?)?;
    l.push(format!(
        "non-harness {} kg + harness {} kg = nominal dry {} kg; + 10 % system margin {} kg = **dry planning mass {} kg** \
         (reserve 0). Lines without a value: {}.",
        fg(g(r, "nonharness_known_kg")?)?,
        fg(g(r, "harness_kg")?)?,
        fg(g(r, "nominal_dry_known_kg")?)?,
        fg(g(r, "system_margin_kg")?)?,
        fg(g(r, "dry_known_kg")?)?,
        if lwv.is_empty() { "none".to_string() } else { py::join_strs(", ", &lwv)? }
    ));
    l.push(String::new());
    let mut wrows = Vec::new();
    for w in py::iter(g(r, "wet")?)? {
        wrows.push(vec![
            g(&w, "xe_case_kg")?.clone(),
            g(&w, "residual_inside_case_kg")?.clone(),
            g(&w, "wet_known_kg")?.clone(),
            s(format!(
                "{} ({} {})",
                py_str(g(&w, "reference")?),
                py_str(g(&w, "comparator")?),
                fg(g(&w, "reference_kg")?)?
            )),
            g(&w, "state")?.clone(),
            py::get_or_none(&w, "exceedance_kg")?,
            match py::get(&w, "redesign_need")?.filter(|x| x.truthy()) {
                Some(rn) => py::get_or_none(rn, "nonharness_nominal_reduction_kg_at_least")?,
                None => Value::Null,
            },
        ]);
    }
    l.extend(table(
        &[
            "loaded Xe kg",
            "residual inside",
            "wet kg",
            "reference",
            "state",
            "exceedance kg",
            "non-harness nominal reduction needed (kg, at least)",
        ],
        &wrows,
    )?);
    l.push("## 40 kg closure per loaded Xe case (HARD_40_WET, not relaxed)".into());
    l.push(String::new());
    let closure = py::iter(g(d, "closure_vs_40kg")?)?;
    let mut crows = Vec::new();
    for c in &closure {
        crows.push(vec![
            g(c, "xe_case_kg")?.clone(),
            g(c, "xe_case_role")?.clone(),
            g(c, "max_allowable_dry_kg_strictly_below")?.clone(),
            g(c, "dry_planning_kg")?.clone(),
            g(c, "wet_planning_kg")?.clone(),
            g(c, "state")?.clone(),
            g(c, "dry_reduction_needed_kg_more_than")?.clone(),
            g(c, "max_allowable_nominal_dry_kg_strictly_below")?.clone(),
            g(c, "nominal_dry_reduction_needed_kg_more_than")?.clone(),
        ]);
    }
    l.extend(table(
        &[
            "Xe kg",
            "role",
            "max dry (kg, <)",
            "dry planning kg",
            "wet kg",
            "state",
            "dry reduction needed (kg, >)",
            "nominal dry max (kg, <)",
            "nominal reduction needed (kg, >)",
        ],
        &crows,
    )?);
    l.push(format!("{}.", py_str(g(&closure[0], "rule")?)));
    l.push(String::new());
    let p = g(d, "proposal_design_target")?;
    let gap = g(p, "gap_from_current_planning_rollup")?;
    l.push(format!("## {}", py_str(g(p, "label")?)));
    l.push(String::new());
    l.push(format!(
        "nominal dry <= {} kg, 10 % system margin -> dry {} kg; {} at the {} kg Xe planning / reference case. {}. Gap \
         from the current planning roll-up: nominal dry {} kg, dry {} kg. Not: {}.",
        fg(g(p, "nominal_dry_max_kg")?)?,
        fg(g(p, "dry_target_kg")?)?,
        py_str(g(p, "arithmetic")?),
        fg(g(p, "xe_reference_case_kg")?)?,
        py_str(g(p, "xe_rule")?),
        fg(g(gap, "nominal_dry_reduction_needed_kg")?)?,
        fg(g(gap, "dry_reduction_needed_kg")?)?,
        py::join_strs(", ", &py::iter(g(p, "not")?)?)?
    ));
    l.push(String::new());
    let mut prows = Vec::new();
    for x in py::iter(g(p, "by_xe_case")?)? {
        prows.push(vec![
            g(&x, "xe_case_kg")?.clone(),
            g(&x, "role")?.clone(),
            g(&x, "wet_target_kg")?.clone(),
            g(&x, "vs_40kg")?.clone(),
            g(&x, "difference_to_40kg_kg")?.clone(),
            g(&x, "nominal_dry_needed_for_lt_40kg_kg_strictly_below")?.clone(),
        ]);
    }
    l.extend(table(
        &[
            "Xe kg",
            "role",
            "wet target kg",
            "vs 40 kg",
            "40 kg minus wet target",
            "nominal dry needed for < 40 kg (kg, <)",
        ],
        &prows,
    )?);
    let t = g(d, "internal_allocation_target")?;
    l.push(format!("## {}", py_str(g(t, "label")?)));
    l.push(String::new());
    let mut trows = Vec::new();
    for x in py::iter(g(t, "lines")?)? {
        trows.push(vec![g(&x, "line")?.clone(), g(&x, "allocation_kg")?.clone(), g(&x, "basis")?.clone()]);
    }
    l.extend(table(&["line", "allocation kg", "basis"], &trows)?);
    let twet = py::iter(g(t, "wet_by_loaded_case")?)?;
    let hp = g(t, "historical_provenance")?;
    l.push(format!(
        "non-harness allocation sum {} kg + harness {} kg ({}) = nominal {} kg; + 10 % {} kg = dry {} kg; wet {} kg at \
         {} kg Xe. Not: {}.",
        fg(g(t, "nonharness_allocation_sum_kg")?)?,
        fg(g(t, "harness_kg")?)?,
        py_str(g(t, "harness_rule")?),
        fg(g(t, "nominal_dry_kg")?)?,
        fg(g(t, "system_margin_kg")?)?,
        fg(g(t, "dry_kg")?)?,
        twet.iter().map(|x| fg(g(x, "wet_kg")?)).collect::<PyResult<Vec<_>>>()?.join(" / "),
        twet.iter().map(|x| fg(g(x, "xe_case_kg")?)).collect::<PyResult<Vec<_>>>()?.join(" / "),
        py::join_strs("; ", &py::iter(g(t, "not")?)?)?
    ));
    l.push(String::new());
    l.push(format!(
        "{}: {} (dry budget {} kg).",
        py_str(g(hp, "label")?),
        py_str(g(hp, "arithmetic")?),
        fg(g(hp, "dry_budget_kg")?)?
    ));
    l.push(String::new());
    let ma = g(d, "margin_audit")?;
    l.push("## Margin audit (line uplift vs system margin)".into());
    l.push(String::new());
    l.push(format!("{}.", py_str(g(ma, "decision")?)));
    l.push(String::new());
    let mut arows = Vec::new();
    for x in py::iter(g(ma, "lines")?)? {
        let contained = match py::get(&x, "margin_contained")? {
            Some(v) => v.clone(),
            None => py::get_or_none(&x, "note")?,
        };
        arows.push(vec![
            g(&x, "line")?.clone(),
            g(&x, "value_kg")?.clone(),
            g(&x, "governs")?.clone(),
            g(&x, "contains_line_uplift")?.clone(),
            g(&x, "line_uplift_factor")?.clone(),
            g(&x, "system_margin_factor")?.clone(),
            g(&x, "effective_factor")?.clone(),
            py::get_or_none(&x, "effective_factor_historical_20pct")?,
            contained,
        ]);
    }
    l.extend(table(
        &[
            "line",
            "value kg",
            "governs",
            "contains line uplift",
            "line factor",
            "system factor",
            "effective factor",
            "historical 20 % effective",
            "margin contained",
        ],
        &arows,
    )?);
    let hs = g(d, "historical_conservative_sensitivity_20pct")?;
    let hr = g(hs, "recomputed_with_al09")?;
    let hv = g(hs, "v4_al09_excluded_history")?;
    l.push(format!("## {}", py_str(g(hs, "label")?)));
    l.push(String::new());
    l.push(format!(
        "* Recomputed with AL-09 = 1.0 kg: nominal {} kg + 20 % {} kg = dry {} kg; wet {} kg. {}.",
        fg(g(hr, "nominal_dry_known_kg")?)?,
        fg(g(hr, "system_margin_kg")?)?,
        fg(g(hr, "dry_known_kg")?)?,
        py::iter(g(hr, "wet_by_loaded_case")?)?
            .iter()
            .map(|x| Ok(format!("{} ({})", fg(g(x, "wet_known_kg")?)?, py_str(g(x, "state")?))))
            .collect::<PyResult<Vec<_>>>()?
            .join(" / "),
        py_str(g(hr, "basis")?)
    ));
    l.push(format!(
        "* {}: dry {} kg; wet {} kg.",
        py_str(g(hv, "label")?),
        fg(g(hv, "dry_known_kg")?)?,
        py::iter(g(hv, "wet_by_loaded_case")?)?
            .iter()
            .map(|x| fg(g(x, "wet_known_kg")?))
            .collect::<PyResult<Vec<_>>>()?
            .join(" / ")
    ));
    l.push(String::new());
    l.push("## Old -> new (v4 -> v5)".into());
    l.push(String::new());
    let mut orows = Vec::new();
    for c in py::iter(g(d, "a9_26_changes_old_new")?)? {
        orows.push(vec![
            g(&c, "quantity")?.clone(),
            g(&c, "old")?.clone(),
            g(&c, "new")?.clone(),
            py::get_or_none(&c, "state_old")?,
            py::get_or_none(&c, "state_new")?,
        ]);
    }
    l.extend(table(&["quantity", "old (v4)", "new (v5)", "state old", "state new"], &orows)?);
    l.push("## Mass-closure actions (A9.26 section 7)".into());
    l.push(String::new());
    let mut mrows = Vec::new();
    for x in py::iter(g(d, "mass_closure_actions")?)? {
        mrows.push(vec![
            g(&x, "id")?.clone(),
            g(&x, "line")?.clone(),
            g(&x, "action")?.clone(),
            g(&x, "detail")?.clone(),
            g(&x, "state")?.clone(),
        ]);
    }
    l.extend(table(&["id", "line", "action", "detail", "state"], &mrows)?);
    l.push("## Unresolved mass terms".into());
    l.push(String::new());
    for x in py::iter(g(r, "tbd")?)? {
        l.push(format!("* {}", py_str(&x)));
    }
    l.push(String::new());
    let ors = g(d, "open_register_status")?;
    l.push("## Carried unchanged from v4".into());
    l.push(String::new());
    l.push(format!(
        "* AFI-01-S1: {}; AFI-02-RA1: {}; MPV3Q-01: {}.",
        py_str(g(ors, "AFI-01-S1")?),
        py_str(g(ors, "AFI-02-RA1")?),
        py_str(g(ors, "MPV3Q-01")?)
    ));
    l.push(format!("* AL-07: {}.", py_str(g(g(g(d, "afi_corrections")?, "AFI-02")?, "a9_25_confirmation")?)));
    l.push(format!("* C1: {}.", py_str(g(g(g(d, "statuses")?, "current_statuses")?, "C1 conventional reference")?)));
    l.push(String::new());
    l.push("## Recorder flags".into());
    l.push(String::new());
    for fl in py::iter(g(d, "recorder_flags")?)? {
        l.push(format!("* {}", cell(&fl)?));
    }
    l.push(String::new());
    Ok(l.join("\n"))
}

/// `render()`: (JSON text, Markdown text) of the record.
pub fn render(repo: &Path) -> PyResult<(String, String)> {
    let doc = build_doc(repo)?;
    let js = String::from_utf8(pyjson::dumps_config_file(&doc)?).expect("utf-8 JSON");
    Ok((js, render_md(&doc)?))
}

/// `build.py --check`: the names of the committed outputs that differ from a fresh build (empty = reproduced).
pub fn check(repo: &Path) -> PyResult<Vec<&'static str>> {
    let (js, md) = render(repo)?;
    let mut stale = Vec::new();
    for (name, rel, text) in [(JSON_NAME, RECORD_REL, &js), (MD_NAME, MD_REL, &md)] {
        match py::read_text(repo, rel) {
            Ok(t) if &t == text => {}
            _ => stale.push(name),
        }
    }
    Ok(stale)
}

// ======================================================================== value status and fail-closed gates (Rust)
pub const A9_28_MD: &str =
    "docs/decisions/OD_2026_10_05_A9_28_RUST_PLAN_RULINGS_AND_SIMULATION_COMPLETION_DIRECTIVE.md";
pub const A9_28_MD_SHA256: &str = "7877bdc923fb07876b211924965767800f4f3a8efc46095f4dc3d471733fb54c";
pub const A9_28_JSON: &str =
    "docs/decisions/OD_2026_10_05_A9_28_rust_plan_rulings_and_simulation_completion_directive.json";
pub const A9_28_JSON_SHA256: &str = "928e0588a635c7df5795b917863cd2035875da6d39cbee2756164deecc2e41e2";
pub const AL07_VALUE_STATUS: &str = "PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT";
pub const AL07_OPEN_ACTION: &str = "AFI-02-RA1_OPEN";
pub const AL07_LABELS: [&str; 3] = [
    "PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR",
    "CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_ARCHITECTURE",
    "REBASE_REQUIRED_FROM_CURRENT_LOAD_CONVERTER_CBE",
];
pub const NEVER_PROMOTED_TO: [&str; 3] = ["CBE", "measured mass", "frozen flight truth"];
const A9_28_MSG1_SHA: &str = "4987b0d204583e7569154cf33f8b4d52c578667f600fc785fd1aef42b8c16d57";
const A9_28_RULING: &str = "AL-07_VALUE_STATUS = PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT AFI-02-RA1_OPEN";
const A9_28_NO_PROMOTION: &str =
    "The 6.0 kg AL-07 value must NOT be promoted by migration into: CBE measured mass frozen flight truth.";

fn model(message: impl Into<String>) -> PyException {
    err("ValueStatusError", message)
}

/// The A9.28 msg 1 sec. 2 ruling, read from the sha256-verified verbatim record (fail closed).
fn a9_28_ruling(repo: &Path) -> PyResult<()> {
    let md_bytes = py::read_bytes(repo, A9_28_MD)?;
    if sha256_hex(&md_bytes) != A9_28_MD_SHA256 {
        return Err(err("PinError", format!("{A9_28_MD} sha256 changed (A9.28 verbatim record is immutable)")));
    }
    if sha256_hex(&py::read_bytes(repo, A9_28_JSON)?) != A9_28_JSON_SHA256 {
        return Err(err("PinError", format!("{A9_28_JSON} sha256 changed")));
    }
    let js = py::load_json(repo, A9_28_JSON)?;
    if !py::eq_str(g(g(&js, "verbatim")?, "sha256")?, A9_28_MD_SHA256) {
        return Err(model("A9.28 JSON does not pin the verbatim record"));
    }
    let md = pyjson::read_text_utf8(&md_bytes)?;
    let head = "## Message 1 \u{2014} RUST_PLAN_V2_RULINGS \u{2014} ";
    let body = py::after(&md, head)?;
    let text = py::before(&py::after(&body, "````text\n")?, "\n````");
    if sha256_hex(text.as_bytes()) != A9_28_MSG1_SHA {
        return Err(model("A9.28 message 1 verbatim text does not reproduce its recorded sha256"));
    }
    let flat = py::norm_ws(&text);
    for qt in [A9_28_RULING, A9_28_NO_PROMOTION] {
        if !flat.contains(qt) {
            return Err(model(format!("A9.28 message 1 ruling not found verbatim: {qt}")));
        }
    }
    Ok(())
}

fn flight_line<'a>(record: &'a Value, lid: &str) -> PyResult<&'a Value> {
    let lines = g(g(record, "lines")?, FLIGHT)?.as_list().ok_or_else(|| model("flight lines are not a list"))?;
    lines
        .iter()
        .find(|x| x.as_dict().and_then(|d| d.get("line")).is_some_and(|v| py::eq_str(v, lid)))
        .ok_or_else(|| model(format!("{lid} missing from the flight lines")))
}

/// VS-01 (RM-R27): AL-07 = 6.0 kg with its committed labels and the A9.28 status PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT
/// / AFI-02-RA1_OPEN; status INCOMPLETE_EVIDENCE. Any CBE / measured / frozen promotion of AL-07 is refused.
pub fn al07_value_status_of(record: &Value, repo: &Path) -> PyResult<Value> {
    a9_28_ruling(repo)?;
    let ln = flight_line(record, "AL-07")?;
    let v = g(ln, "value")?;
    let labels = g(ln, "afi_02_labels")?;
    let ra = g(ln, "open_rebase_action")?;
    let checks = [
        (py_eq(g(v, "value_kg")?, &f(6.0)) && matches!(g(v, "value_kg")?, Value::Float(_)), "value_kg is not 6.0"),
        (py::eq_str(g(v, "governs")?, "MEV_PLANNING_FLOOR"), "value does not govern as MEV_PLANNING_FLOOR"),
        (py::is_none(g(ln, "cbe_kg")?), "AL-07 carries a CBE"),
        (py::is_none(g(ln, "measured_kg")?), "AL-07 carries a measured mass"),
        (labels == &strs(&AL07_LABELS), "afi_02_labels differ from the committed three"),
        (py::eq_str(g(ra, "id")?, "AFI-02-RA1") && py::eq_str(g(ra, "state")?, "OPEN"), "AFI-02-RA1 is not OPEN"),
    ];
    for (ok, why) in checks {
        if !ok {
            return Err(model(format!(
                "AL-07 value-status preservation failed (RM-R27; A9.28: never promoted by migration to CBE, measured \
                 mass or frozen flight truth): {why}"
            )));
        }
    }
    Ok(dict(vec![
        ("line", s("AL-07")),
        ("value_kg", f(6.0)),
        ("governs", s("MEV_PLANNING_FLOOR")),
        ("cbe_kg", Value::Null),
        ("measured_kg", Value::Null),
        ("committed_labels", strs(&AL07_LABELS)),
        ("open_rebase_action", dict(vec![("id", s("AFI-02-RA1")), ("state", s("OPEN"))])),
        ("a9_28_value_status", s(AL07_VALUE_STATUS)),
        ("a9_28_open_action", s(AL07_OPEN_ACTION)),
        ("never_promoted_by_migration_to", strs(&NEVER_PROMOTED_TO)),
        ("status", s(EvalStatus::IncompleteEvidence.as_str())),
    ]))
}

/// The committed record, sha256-verified (the production read; the frozen bid record is never rewritten).
pub fn load_record_pinned(repo: &Path) -> PyResult<Value> {
    let bytes = py::read_bytes(repo, RECORD_REL)?;
    let actual = sha256_hex(&bytes);
    if actual != RECORD_SHA256 {
        return Err(err(
            "PinError",
            format!(
                "{RECORD_REL} sha256 {actual} != pinned {RECORD_SHA256} (frozen mass / power v5 record, read as a \
                 pinned input)"
            ),
        ));
    }
    pyjson::loads(&pyjson::read_text_utf8(&bytes)?)
}

/// VS-01 on the pinned committed record.
pub fn al07_value_status(repo: &Path) -> PyResult<Value> {
    al07_value_status_of(&load_record_pinned(repo)?, repo)
}

/// Upstream mission Xe load (SC-WP-09, not admitted): an explicit typed input of the mass gates.
#[derive(Debug, Clone, PartialEq)]
pub enum MissionXeLoad {
    /// No admitted mission Xe load: the record's 2 / 5 / 10 kg LOADED cases are planning / sensitivity cases only.
    NotAdmitted,
    /// An admitted mission Xe load with its evidence source.
    Admitted { loaded_kg: f64, source: String },
}

/// SC-WP-07 determining-evidence gates, fail closed (never PASS): G1 NOT_EVALUATED (no CBE / measured line mass),
/// G2 mass compliance INCOMPLETE_EVIDENCE with the HARD_40_WET states visible, G3 AL-07 value status
/// INCOMPLETE_EVIDENCE. A record outside these premises is MODEL_ERROR (a successor record needs a new contract).
pub fn mass_gates_of(record: &Value, repo: &Path, xe: &MissionXeLoad) -> PyResult<Value> {
    let lines = py::iter(g(g(record, "lines")?, FLIGHT)?)?;
    for ln in &lines {
        if !py::is_none(&py::get_or_none(ln, "cbe_kg")?) || !py::is_none(&py::get_or_none(ln, "measured_kg")?) {
            return Err(model(format!(
                "{}: a CBE / measured line mass is present; the mass gates need a successor record and contract",
                py_str(g(ln, "line")?)
            )));
        }
    }
    let rolls = py::iter(g(record, "rollups")?)?;
    if rolls.len() != 1 || !py::eq_str(g(&rolls[0], "configuration")?, FLIGHT) {
        return Err(model("the record must carry exactly one flight roll-up (hall_icp_neutralizer)"));
    }
    let roll = &rolls[0];
    if g(roll, "all_terms_resolved")?.truthy() || !py::eq_str(g(g(record, "mass_status")?, "status")?, MASS_STATUS) {
        return Err(model(
            "mass status is not MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED; a successor record is needed",
        ));
    }
    let vs = al07_value_status_of(record, repo)?;
    let mut states = Vec::new();
    for (c, w) in sorted_rows(&hard_rows(roll)?)? {
        let st = g(&w, "state")?;
        if !py::in_strs(st, &rules::CLOSURE_STATES) || py::eq_str(st, "CLOSES") {
            return Err(model("a HARD_40_WET row claims closure without resolved terms"));
        }
        states.push((py_str(&c), st.clone()));
    }
    let xe_input = match xe {
        MissionXeLoad::NotAdmitted => dict(vec![
            ("mission_xe_load", s("NOT_ADMITTED")),
            ("reading", s("the 2 / 5 / 10 kg LOADED cases are planning / sensitivity cases; no Xe load is selected")),
        ]),
        MissionXeLoad::Admitted { loaded_kg, source } => {
            dict(vec![("mission_xe_load", s("ADMITTED")), ("loaded_kg", f(*loaded_kg)), ("source", s(source.clone()))])
        }
    };
    Ok(list([
        dict(vec![
            ("gate", s("no CBE or measured mass for any BOM line")),
            ("status", s(EvalStatus::NotEvaluated.as_str())),
            (
                "reason",
                s("every flight line is an owner MEV allocation or an MEV planning floor; no CBE, no measured mass"),
            ),
            ("source", s("abep_sim/design/architecture_optimizer.py::wet_mass")),
        ]),
        dict(vec![
            ("gate", s("mass compliance")),
            ("status", s(EvalStatus::IncompleteEvidence.as_str())),
            ("record_status", s(MASS_STATUS)),
            ("hard_40_wet_state_by_loaded_case", owned_dict(states)),
            ("dry_known_kg", g(roll, "dry_known_kg")?.clone()),
            ("xe_input", xe_input),
            ("source", s("A9.25 msg 8 sec. 8; A9.26 sections 4 and 7 (DOES_NOT_CLOSE stays visible; no PASS)")),
        ]),
        dict(vec![
            ("gate", s("AL-07 value status (PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT, AFI-02-RA1 open)")),
            ("status", g(&vs, "status")?.clone()),
            ("value_status", vs),
            (
                "source",
                s(format!(
                    "A9.28 msg 1 sec. 2 ({A9_28_MD} sha256 {}); record {RECORD_REL} sha256 {}",
                    &A9_28_MD_SHA256[..12],
                    &RECORD_SHA256[..12]
                )),
            ),
        ]),
    ]))
}

/// The gates on the pinned committed record.
pub fn mass_gates(repo: &Path, xe: &MissionXeLoad) -> PyResult<Value> {
    mass_gates_of(&load_record_pinned(repo)?, repo, xe)
}
