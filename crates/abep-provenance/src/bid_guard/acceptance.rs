//! The preregistered acceptance cases of `bid_source_guard` (acceptance_v1.json): tamper engine and expectation check.
//!
//! cargo test runs every case as a regression test; the single acceptance run that produces
//! `acceptance_report_v1.json` uses the same engine (`abep-ci bid-guard-acceptance`).

use super::{evaluate, GuardInputs, GuardReport, HistorySource, MANIFEST_PATH, MISSION_SCENARIO_PATH};
use crate::git::Git;
use crate::read_verified;
use abep_types::{AbepError, AbepResult};
use serde_json::{json, Value};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

pub const ACCEPTANCE_PATH: &str = "docs/rust_migration/contracts/BID_SOURCE_GUARD/acceptance_v1.json";
/// sha256 of acceptance_v1.json as committed alone in 1a852c5 (before any implementation).
pub const ACCEPTANCE_SHA256: &str = "8d23e1f16d63dcbe2ce27f1ad48712d118808270d0ae5ab2ab2a2a6eb60ab1c6";

/// A temporary directory removed on drop.
pub struct TempDir(PathBuf);

impl TempDir {
    pub fn new(tag: &str) -> AbepResult<Self> {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let nanos =
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
        let p = std::env::temp_dir().join(format!(
            "abep-{tag}-{}-{nanos}-{}",
            std::process::id(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&p).map_err(|e| io_err(&p, e))?;
        Ok(TempDir(p))
    }

    pub fn path(&self) -> &Path {
        &self.0
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn io_err(p: &Path, e: impl ToString) -> AbepError {
    AbepError::Io { path: p.display().to_string(), message: e.to_string() }
}

fn case_err(id: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: ACCEPTANCE_PATH.into(), message: format!("{id}: {}", m.into()) }
}

#[derive(Debug, Clone)]
pub struct Expected {
    pub overall: String,
    pub files: String,
    pub history: String,
    pub files_codes: Vec<String>,
    pub history_codes: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct Case {
    pub id: String,
    pub title: String,
    pub tree: String,
    pub history: String,
    pub head: String,
    pub tamper: Vec<Value>,
    pub expected: Expected,
}

fn s(v: &Value, key: &str, id: &str) -> AbepResult<String> {
    v.get(key).and_then(Value::as_str).map(str::to_string).ok_or_else(|| case_err(id, format!("missing {key}")))
}

fn codes(v: &Value, part: &str, id: &str) -> AbepResult<Vec<String>> {
    v.pointer(&format!("/required_codes/{part}"))
        .and_then(Value::as_array)
        .ok_or_else(|| case_err(id, format!("missing required_codes.{part}")))?
        .iter()
        .map(|c| c.as_str().map(str::to_string).ok_or_else(|| case_err(id, "non-string code")))
        .collect()
}

/// Load the cases from the preregistered file, refusing any byte change to it (sha256 pinned above).
pub fn load_cases(repo_root: &Path) -> AbepResult<Vec<Case>> {
    let bytes = read_verified(&repo_root.join(ACCEPTANCE_PATH), ACCEPTANCE_SHA256)?;
    let v: Value = serde_json::from_slice(&bytes).map_err(|e| case_err("file", e.to_string()))?;
    let list =
        v.pointer("/acceptance_cases/cases").and_then(Value::as_array).ok_or_else(|| case_err("file", "no cases"))?;
    let mut out = Vec::new();
    for c in list {
        let id = s(c, "id", "?")?;
        let e = c.get("expected").ok_or_else(|| case_err(&id, "missing expected"))?;
        out.push(Case {
            title: s(c, "title", &id)?,
            tree: s(c, "tree", &id)?,
            history: s(c, "history", &id)?,
            head: s(c, "head", &id)?,
            tamper: c
                .get("tamper")
                .and_then(Value::as_array)
                .cloned()
                .ok_or_else(|| case_err(&id, "missing tamper"))?,
            expected: Expected {
                overall: s(e, "overall", &id)?,
                files: s(e, "files", &id)?,
                history: s(e, "history", &id)?,
                files_codes: codes(e, "files", &id)?,
                history_codes: codes(e, "history", &id)?,
            },
            id,
        });
    }
    Ok(out)
}

/// The two scratch repositories of the history kinds SCRATCH_FULL and SCRATCH_SHALLOW.
pub struct ScratchRepos {
    _dir: TempDir,
    pub full: PathBuf,
    pub shallow: PathBuf,
}

fn git_ok(dir: &Path, args: &[&str]) -> AbepResult<()> {
    let o = Git::new(dir).output(args).map_err(|e| io_err(dir, e))?;
    if !o.status.success() {
        return Err(io_err(dir, format!("git {}: {}", args.join(" "), String::from_utf8_lossy(&o.stderr).trim())));
    }
    Ok(())
}

impl ScratchRepos {
    pub fn create() -> AbepResult<Self> {
        let dir = TempDir::new("bidguard-scratch")?;
        let full = dir.path().join("full");
        git_ok(dir.path(), &["init", "-q", "full"])?;
        for i in 0..2 {
            fs::write(full.join("f.txt"), format!("{i}\n")).map_err(|e| io_err(&full, e))?;
            git_ok(&full, &["add", "f.txt"])?;
            git_ok(
                &full,
                &[
                    "-c",
                    "user.name=abep-acceptance",
                    "-c",
                    "user.email=abep-acceptance@invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-q",
                    "-m",
                    "scratch",
                ],
            )?;
        }
        let url = format!("file://{}", full.display());
        git_ok(dir.path(), &["clone", "-q", "--depth", "1", &url, "shallow"])?;
        let shallow = dir.path().join("shallow");
        Ok(ScratchRepos { _dir: dir, full, shallow })
    }
}

fn copy_tree(repo_root: &Path, dest: &Path) -> AbepResult<()> {
    let mpath = repo_root.join(MANIFEST_PATH);
    let m: Value =
        serde_json::from_slice(&fs::read(&mpath).map_err(|e| io_err(&mpath, e))?).map_err(|e| io_err(&mpath, e))?;
    let files = m
        .get("package_lineage")
        .and_then(Value::as_array)
        .and_then(|l| l.last())
        .and_then(|e| e.get("files"))
        .and_then(Value::as_object)
        .ok_or_else(|| io_err(&mpath, "no terminal lineage file map"))?;
    let mut paths: Vec<&str> = files.keys().map(String::as_str).collect();
    paths.extend([MANIFEST_PATH, MISSION_SCENARIO_PATH]);
    for p in paths {
        let dst = dest.join(p);
        fs::create_dir_all(dst.parent().expect("relative path has a parent")).map_err(|e| io_err(&dst, e))?;
        fs::copy(repo_root.join(p), &dst).map_err(|e| io_err(&dst, e))?;
    }
    Ok(())
}

fn decode_hex(h: &str) -> Option<Vec<u8>> {
    if !h.len().is_multiple_of(2) {
        return None;
    }
    (0..h.len()).step_by(2).map(|i| u8::from_str_radix(&h[i..i + 2], 16).ok()).collect()
}

fn apply(dest: &Path, op: &Value, id: &str) -> AbepResult<()> {
    let kind = s(op, "op", id)?;
    let target = |key: &str| -> AbepResult<PathBuf> { Ok(dest.join(s(op, key, id)?)) };
    let res = match kind.as_str() {
        "append_bytes" => {
            let bytes = decode_hex(&s(op, "hex", id)?).ok_or_else(|| case_err(id, "bad hex"))?;
            let p = target("path")?;
            fs::OpenOptions::new().append(true).open(&p).and_then(|mut f| f.write_all(&bytes))
        }
        "delete" => fs::remove_file(target("path")?),
        "create" => {
            let p = target("path")?;
            let text = s(op, "text", id)?;
            fs::create_dir_all(p.parent().expect("relative path has a parent")).and_then(|_| fs::write(&p, text))
        }
        "replace_all" => {
            let p = target("path")?;
            let text = fs::read_to_string(&p).map_err(|e| io_err(&p, e))?;
            fs::write(&p, text.replace(&s(op, "old", id)?, &s(op, "new", id)?))
        }
        "manifest_set" | "manifest_reverse" => {
            let p = dest.join(MANIFEST_PATH);
            let mut m: Value =
                serde_json::from_slice(&fs::read(&p).map_err(|e| io_err(&p, e))?).map_err(|e| io_err(&p, e))?;
            let ptr = s(op, "pointer", id)?;
            let slot = m.pointer_mut(&ptr).ok_or_else(|| case_err(id, format!("pointer {ptr} not in the manifest")))?;
            if kind == "manifest_set" {
                *slot = op.get("value").cloned().ok_or_else(|| case_err(id, "missing value"))?;
            } else {
                slot.as_array_mut().ok_or_else(|| case_err(id, format!("{ptr} is not an array")))?.reverse();
            }
            fs::write(&p, serde_json::to_vec_pretty(&m).expect("serializable"))
        }
        other => return Err(case_err(id, format!("unknown op {other}"))),
    };
    res.map_err(|e| case_err(id, format!("{kind}: {e}")))
}

/// Run one case against the repository at `repo_root`.
pub fn run_case(repo_root: &Path, case: &Case, scratch: &ScratchRepos) -> AbepResult<GuardReport> {
    let copy;
    let tree_root = match case.tree.as_str() {
        "REPOSITORY" if case.tamper.is_empty() => repo_root.to_path_buf(),
        "REPOSITORY" => return Err(case_err(&case.id, "the repository tree is never tampered")),
        "COPY" => {
            copy = TempDir::new("bidguard-case")?;
            copy_tree(repo_root, copy.path())?;
            for op in &case.tamper {
                apply(copy.path(), op, &case.id)?;
            }
            copy.path().to_path_buf()
        }
        other => return Err(case_err(&case.id, format!("unknown tree {other}"))),
    };
    let history = match case.history.as_str() {
        "REPOSITORY" => HistorySource::Repository(repo_root.to_path_buf()),
        "NONE" => HistorySource::None,
        "SCRATCH_SHALLOW" => HistorySource::Repository(scratch.shallow.clone()),
        "SCRATCH_FULL" => HistorySource::Repository(scratch.full.clone()),
        other => return Err(case_err(&case.id, format!("unknown history {other}"))),
    };
    Ok(evaluate(&GuardInputs { tree_root, history, head: case.head.clone() }))
}

/// Deviations of a report from the case's preregistered expectation (empty = the case holds).
pub fn expectation_problems(case: &Case, r: &GuardReport) -> Vec<String> {
    let e = &case.expected;
    let mut p = Vec::new();
    for (what, got, want) in [
        ("overall", r.overall.as_str(), &e.overall),
        ("files", r.files.status.as_str(), &e.files),
        ("history", r.history.status.as_str(), &e.history),
    ] {
        if got != want {
            p.push(format!("{what} {got}, expected {want}"));
        }
    }
    for (part, report, want) in [("files", &r.files, &e.files_codes), ("history", &r.history, &e.history_codes)] {
        let got = report.codes();
        for c in want {
            if !got.contains(c.as_str()) {
                p.push(format!("{part}: required code {c} not reported (got {got:?})"));
            }
        }
    }
    p
}

/// Compact, implementation-comparable result of one case: statuses and code sets per part.
pub fn case_summary(id: &str, r: &GuardReport) -> Value {
    let part = |p: &super::PartReport| json!({"status": p.status.as_str(), "codes": p.codes()});
    json!({"id": id, "overall": r.overall.as_str(), "files": part(&r.files), "history": part(&r.history)})
}

/// One executed case.
pub struct CaseOutcome {
    pub case: Case,
    pub report: GuardReport,
    pub problems: Vec<String>,
}

/// Run every preregistered case.
pub fn run_all(repo_root: &Path) -> AbepResult<Vec<CaseOutcome>> {
    let cases = load_cases(repo_root)?;
    let scratch = ScratchRepos::create()?;
    let mut out = Vec::new();
    for case in cases {
        let report = run_case(repo_root, &case, &scratch)?;
        let problems = expectation_problems(&case, &report);
        out.push(CaseOutcome { case, report, problems });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hex_decoding() {
        assert_eq!(decode_hex("0a00ff"), Some(vec![10, 0, 255]));
        assert_eq!(decode_hex("0"), None);
        assert_eq!(decode_hex("zz"), None);
    }
}
