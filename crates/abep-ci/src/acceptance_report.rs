//! The single acceptance run of `bid_source_guard` (acceptance_v1.json decision_rules): runs every case in Rust, reads
//! the Python implementation's results (`python3 scripts/ci_checks.py --bid-guard-acceptance`, a file; this crate
//! never runs Python), applies the preregistered decision rules and writes acceptance_report_v1.json + .md.

use abep_provenance::bid_guard::acceptance::{case_summary, run_all, Case, ACCEPTANCE_PATH, ACCEPTANCE_SHA256};
use abep_provenance::bid_guard::MANIFEST_PATH;
use abep_provenance::git::Git;
use abep_provenance::run_record::RUSTC_VERSION;
use abep_provenance::{sha256_file, sha256_hex};
use abep_types::{AbepError, AbepResult};
use serde_json::{json, Value};
use std::collections::BTreeSet;
use std::path::Path;

pub const REPORT_JSON: &str = "docs/rust_migration/contracts/BID_SOURCE_GUARD/acceptance_report_v1.json";
pub const REPORT_MD: &str = "docs/rust_migration/contracts/BID_SOURCE_GUARD/acceptance_report_v1.md";
const IMPLEMENTATION_FILES: [&str; 5] = [
    "crates/abep-provenance/src/bid_guard.rs",
    "crates/abep-provenance/src/bid_guard/acceptance.rs",
    "crates/abep-provenance/src/git.rs",
    "scripts/ci_checks.py",
    "docs/bid/bid_source_manifest_v1.json",
];

/// Deviations of an implementation-comparable summary from the case's expectation (same rule for both languages).
pub fn summary_problems(case: &Case, s: &Value) -> Vec<String> {
    let e = &case.expected;
    let mut p = Vec::new();
    for (what, ptr, want) in [
        ("overall", "/overall", &e.overall),
        ("files", "/files/status", &e.files),
        ("history", "/history/status", &e.history),
    ] {
        let got = s.pointer(ptr).and_then(Value::as_str).unwrap_or("<missing>");
        if got != want {
            p.push(format!("{what} {got}, expected {want}"));
        }
    }
    for (part, want) in [("files", &e.files_codes), ("history", &e.history_codes)] {
        let got: BTreeSet<&str> = s
            .pointer(&format!("/{part}/codes"))
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(Value::as_str).collect())
            .unwrap_or_default();
        for c in want {
            if !got.contains(c.as_str()) {
                p.push(format!("{part}: required code {c} not reported"));
            }
        }
    }
    p
}

fn utc_now() -> String {
    let secs = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
    let (days, rem) = ((secs / 86_400) as i64, secs % 86_400);
    // civil-from-days (H. Hinnant)
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + i64::from(m <= 2);
    format!("{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z", rem / 3600, rem % 3600 / 60, rem % 60)
}

fn err(m: impl Into<String>) -> AbepError {
    AbepError::IncompleteEvidence { message: m.into() }
}

/// Build the report (JSON value and Markdown) from the Rust run and the Python results file.
pub fn build(repo_root: &Path, python_results: &[u8]) -> AbepResult<(Value, String)> {
    let git = Git::new(repo_root);
    let shallow = git.stdout(&["rev-parse", "--is-shallow-repository"]).map_err(err)?;
    let head = git.stdout(&["rev-parse", "HEAD"]).map_err(err)?;
    let dirty = git.stdout(&["status", "--porcelain", "--untracked-files=no"]).map_err(err)?;
    let py: Value = serde_json::from_slice(python_results).map_err(|e| err(format!("python results: {e}")))?;
    let mut files = serde_json::Map::new();
    for f in IMPLEMENTATION_FILES {
        files.insert(f.into(), json!(sha256_file(&repo_root.join(f))?));
    }
    let provenance = json!({
        "utc": utc_now(),
        "git_head": head,
        "git_dirty_tracked": !dirty.is_empty(),
        "rustc": RUSTC_VERSION,
        "python": py.get("python").cloned().unwrap_or(Value::Null),
        "python_results_sha256": sha256_hex(python_results),
        "source_sha256": files,
        "commands": [
            "python3 scripts/ci_checks.py --bid-guard-acceptance > python_results.json",
            "cargo run --locked -q -p abep-ci -- bid-guard-acceptance --python-results python_results.json",
        ],
    });
    let base = json!({
        "schema": "abep_new_infrastructure_acceptance_report_v1",
        "id": "ACCEPT-NI-BID-SOURCE-GUARD-V1-REPORT",
        "item": "NI-BID-SOURCE-GUARD",
        "prereg": {"path": ACCEPTANCE_PATH, "sha256": ACCEPTANCE_SHA256, "id": "ACCEPT-NI-BID-SOURCE-GUARD-V1"},
        "manifest": {"path": MANIFEST_PATH, "sha256": sha256_file(&repo_root.join(MANIFEST_PATH))?},
        "provenance": provenance,
    });
    if shallow != "false" {
        let mut v = base;
        v["verdict"] = json!("NOT_RUN_HISTORY_UNAVAILABLE");
        v["reason"] = json!(format!("rev-parse --is-shallow-repository printed {shallow:?}"));
        let md = format!("# bid_source_guard acceptance v1: NOT_RUN_HISTORY_UNAVAILABLE\n\n{}\n", v["reason"]);
        return Ok((v, md));
    }
    let outcomes = run_all(repo_root)?;
    let py_cases: Vec<&Value> =
        py.get("cases").and_then(Value::as_array).map(|a| a.iter().collect()).unwrap_or_default();
    let mut rows = Vec::new();
    let mut all_ok = py_cases.len() == outcomes.len();
    for (n, o) in outcomes.iter().enumerate() {
        let rust = case_summary(&o.case.id, &o.report);
        let python = py_cases.get(n).copied().cloned().unwrap_or(Value::Null);
        let python_problems = if python.get("id").and_then(Value::as_str) == Some(o.case.id.as_str()) {
            summary_problems(&o.case, &python)
        } else {
            vec!["no Python result for this case".to_string()]
        };
        let agree = rust == python;
        all_ok &= o.problems.is_empty() && python_problems.is_empty() && agree;
        rows.push(json!({
            "id": o.case.id,
            "title": o.case.title,
            "expected": {
                "overall": o.case.expected.overall, "files": o.case.expected.files, "history": o.case.expected.history,
                "required_codes": {"files": o.case.expected.files_codes, "history": o.case.expected.history_codes},
            },
            "rust": rust,
            "python": python,
            "rust_meets_expectation": o.problems.is_empty(),
            "rust_problems": o.problems,
            "python_meets_expectation": python_problems.is_empty(),
            "python_problems": python_problems,
            "implementations_agree": agree,
            "rust_findings": {"files": o.report.files.findings, "history": o.report.history.findings},
        }));
    }
    let verdict = if all_ok { "ACCEPTED" } else { "NOT_ACCEPTED" };
    let current = outcomes.iter().find(|o| o.case.id == "BASE-00").map(|o| o.report.overall.as_str());
    let mut v = base;
    v["verdict"] = json!(verdict);
    v["decision_rules_applied"] = json!([
        "per_case: overall / files / history equal the expected values and every required code is reported, in each \
         implementation",
        "agreement: Rust and Python report the same statuses and finding-code sets per part for every case",
        "verdict: ACCEPTED iff per_case and agreement hold for all cases",
    ]);
    v["counts"] = json!({
        "cases": outcomes.len(),
        "python_cases": py_cases.len(),
        "rust_meets_expectation": rows.iter().filter(|r| r["rust_meets_expectation"] == true).count(),
        "python_meets_expectation": rows.iter().filter(|r| r["python_meets_expectation"] == true).count(),
        "implementations_agree": rows.iter().filter(|r| r["implementations_agree"] == true).count(),
    });
    v["current_tree_result"] = json!({"case": "BASE-00", "overall": current});
    v["cases"] = json!(rows);
    v["ledger_update"] = json!(if all_ok {
        "NI-BID-SOURCE-GUARD -> ADMITTED in docs/rust_migration/migration_state_v1.json (admission evidence: this report)"
    } else {
        "none: NOT_ACCEPTED (code fix + acceptance_v2 only)"
    });
    v["what_this_is_not"] = json!([
        "not physics and not a gate verdict; it protects the frozen bid record only",
        "not a re-freeze: the bid record stays 5eee4b8 / 2de86ab",
    ]);
    let md = render_md(&v);
    Ok((v, md))
}

fn render_md(v: &Value) -> String {
    let s = |p: &str| {
        v.pointer(p).map(|x| x.as_str().map(str::to_string).unwrap_or_else(|| x.to_string())).unwrap_or_default()
    };
    let mut md = format!(
        "# bid_source_guard acceptance v1: {}\n\nGenerated from `acceptance_report_v1.json` (do not edit). Preregistration \
         `{}` (sha256 `{}`), manifest sha256 `{}`.\n\n* Run: {} at `{}` (tracked tree dirty: {}), {}, Python {}.\n\
         * Current repository tree (BASE-00): **{}**.\n* Cases: {} ; Rust meets expectation {} ; Python meets expectation \
         {} ; implementations agree {}.\n\n| case | title | expected (overall / files / history) | Rust | Python | agree |\n\
         |---|---|---|---|---|---|\n",
        s("/verdict"),
        s("/prereg/path"),
        s("/prereg/sha256"),
        s("/manifest/sha256"),
        s("/provenance/utc"),
        s("/provenance/git_head"),
        s("/provenance/git_dirty_tracked"),
        s("/provenance/rustc"),
        s("/provenance/python"),
        s("/current_tree_result/overall"),
        s("/counts/cases"),
        s("/counts/rust_meets_expectation"),
        s("/counts/python_meets_expectation"),
        s("/counts/implementations_agree"),
    );
    let fmt = |x: &Value| {
        let codes = |p: &str| {
            x.pointer(p)
                .and_then(Value::as_array)
                .map(|a| a.iter().filter_map(Value::as_str).collect::<Vec<_>>().join(", "))
                .unwrap_or_default()
        };
        format!(
            "{} / {} / {} [{}] [{}]",
            x.pointer("/overall").and_then(Value::as_str).unwrap_or("-"),
            x.pointer("/files/status").and_then(Value::as_str).unwrap_or("-"),
            x.pointer("/history/status").and_then(Value::as_str).unwrap_or("-"),
            codes("/files/codes"),
            codes("/history/codes")
        )
    };
    for r in v["cases"].as_array().into_iter().flatten() {
        let e = &r["expected"];
        md.push_str(&format!(
            "| {} | {} | {} / {} / {} | {} | {} | {} |\n",
            r["id"].as_str().unwrap_or(""),
            r["title"].as_str().unwrap_or("").replace('|', "/"),
            e["overall"].as_str().unwrap_or(""),
            e["files"].as_str().unwrap_or(""),
            e["history"].as_str().unwrap_or(""),
            fmt(&r["rust"]),
            fmt(&r["python"]),
            if r["implementations_agree"] == true { "yes" } else { "NO" },
        ));
    }
    md.push_str(&format!("\nLedger: {}\n", s("/ledger_update")));
    md
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn utc_formatting_is_iso8601() {
        let t = utc_now();
        assert_eq!(t.len(), 20);
        assert!(t.ends_with('Z') && t.as_bytes()[10] == b'T');
    }
}
