//! `bid_source_guard`: protects the frozen bid record (A9.29 sec. 3, RM-OQ-11; CI_PLAN.md § 3).
//!
//! Technical source `5eee4b8`, terminal package state `2de86ab`, lineage `b5849af -> 2de86ab`, mission scenario v2.
//! Semantics, finding codes and tamper cases are preregistered in
//! `docs/rust_migration/contracts/BID_SOURCE_GUARD/acceptance_v1.json`; the manifest is
//! `docs/bid/bid_source_manifest_v1.json`. Two parts:
//! * files: the working tree only (no git);
//! * history: a full-history git repository. Without one the part is NOT_EVALUATED, and so is the overall result:
//!   the guard never passes silently.

use crate::git::{BatchItem, Git};
use crate::sha256_hex;
use serde::Serialize;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

pub mod acceptance;

pub const TECHNICAL_SOURCE: &str = "5eee4b8c82a9403b6bb82d5f8d324526f5d6399b";
pub const TERMINAL_PACKAGE_STATE: &str = "2de86abefacbd36ce7516d3cf017f6258bd7e7a2";
pub const PACKAGE_LINEAGE: [&str; 2] = ["b5849affae22a6709ad217a184f6fe896d15410a", TERMINAL_PACKAGE_STATE];
pub const MISSION_SCENARIO_PATH: &str = "config/mission/mission_scenario_v2.json";
pub const MISSION_SCENARIO_SHA256: &str = "885b1f70a1a44389e088837fd37bb79390b63132e3c81f17923103b2f9b5fc49";
pub const MANIFEST_PATH: &str = "docs/bid/bid_source_manifest_v1.json";
pub const MANIFEST_SCHEMA: &str = "abep_bid_source_manifest_v1";
pub const PROTECTED_ROOT: &str = "docs/bid/";
pub const BASELINE_PATH: &str = "docs/bid/bid_technical_baseline_v2.json";
pub const IGNORED_PATTERN: &str = "**/__pycache__/*.pyc";
const DECISION_PREFIX: &str = "docs/decisions/OD_";

/// Result of one part, and of the guard as a whole.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GuardStatus {
    Pass,
    Fail,
    NotEvaluated,
}

impl GuardStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            GuardStatus::Pass => "PASS",
            GuardStatus::Fail => "FAIL",
            GuardStatus::NotEvaluated => "NOT_EVALUATED",
        }
    }
}

/// Preregistered finding codes (acceptance_v1 semantics.finding_codes).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Code {
    ManifestInvalid,
    LineageRecordMismatch,
    BidFileMissing,
    BidFileModified,
    BidFileUnlisted,
    MissionScenarioChanged,
    TechnicalSourcePinChanged,
    AuthorizationInvalid,
    HistoryNotAvailable,
    LineageCommitMissing,
    LineageAncestryBroken,
    TreeHashMismatch,
    LineageFilesMismatch,
    TechnicalSourceFileMismatch,
    GitError,
}

impl Code {
    pub fn as_str(self) -> &'static str {
        match self {
            Code::ManifestInvalid => "MANIFEST_INVALID",
            Code::LineageRecordMismatch => "LINEAGE_RECORD_MISMATCH",
            Code::BidFileMissing => "BID_FILE_MISSING",
            Code::BidFileModified => "BID_FILE_MODIFIED",
            Code::BidFileUnlisted => "BID_FILE_UNLISTED",
            Code::MissionScenarioChanged => "MISSION_SCENARIO_CHANGED",
            Code::TechnicalSourcePinChanged => "TECHNICAL_SOURCE_PIN_CHANGED",
            Code::AuthorizationInvalid => "AUTHORIZATION_INVALID",
            Code::HistoryNotAvailable => "HISTORY_NOT_AVAILABLE",
            Code::LineageCommitMissing => "LINEAGE_COMMIT_MISSING",
            Code::LineageAncestryBroken => "LINEAGE_ANCESTRY_BROKEN",
            Code::TreeHashMismatch => "TREE_HASH_MISMATCH",
            Code::LineageFilesMismatch => "LINEAGE_FILES_MISMATCH",
            Code::TechnicalSourceFileMismatch => "TECHNICAL_SOURCE_FILE_MISMATCH",
            Code::GitError => "GIT_ERROR",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Finding {
    pub code: Code,
    pub path: String,
    pub detail: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct PartReport {
    pub status: GuardStatus,
    pub findings: Vec<Finding>,
}

impl PartReport {
    fn from_findings(mut findings: Vec<Finding>) -> Self {
        findings.sort_by(|a, b| (a.code.as_str(), &a.path, &a.detail).cmp(&(b.code.as_str(), &b.path, &b.detail)));
        let status = if findings.is_empty() { GuardStatus::Pass } else { GuardStatus::Fail };
        PartReport { status, findings }
    }

    fn not_evaluated(detail: String) -> Self {
        PartReport {
            status: GuardStatus::NotEvaluated,
            findings: vec![Finding { code: Code::HistoryNotAvailable, path: String::new(), detail }],
        }
    }

    /// Distinct finding codes, sorted.
    pub fn codes(&self) -> BTreeSet<&'static str> {
        self.findings.iter().map(|f| f.code.as_str()).collect()
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct GuardReport {
    pub overall: GuardStatus,
    pub files: PartReport,
    pub history: PartReport,
}

impl GuardReport {
    fn new(files: PartReport, history: PartReport) -> Self {
        let overall = if files.status == GuardStatus::Fail || history.status == GuardStatus::Fail {
            GuardStatus::Fail
        } else if history.status == GuardStatus::NotEvaluated {
            GuardStatus::NotEvaluated
        } else {
            GuardStatus::Pass
        };
        GuardReport { overall, files, history }
    }

    /// Plain-text report, one finding per line.
    pub fn render(&self) -> String {
        let mut s = format!(
            "bid_source_guard: overall {} (files {}, history {})\n",
            self.overall.as_str(),
            self.files.status.as_str(),
            self.history.status.as_str()
        );
        for (part, r) in [("files", &self.files), ("history", &self.history)] {
            for f in &r.findings {
                s.push_str(&format!("  [{part}] {} {}: {}\n", f.code.as_str(), f.path, f.detail));
            }
        }
        s
    }
}

/// Where the history part reads git objects from.
#[derive(Debug, Clone)]
pub enum HistorySource {
    None,
    Repository(PathBuf),
}

/// Inputs of one guard evaluation.
#[derive(Debug, Clone)]
pub struct GuardInputs {
    /// Root of the working tree that holds docs/bid/**, the mission scenario and the manifest.
    pub tree_root: PathBuf,
    pub history: HistorySource,
    /// Revision whose committed state is checked and which must descend from the terminal state.
    pub head: String,
}

impl GuardInputs {
    /// The repository itself: its working tree, its full history, HEAD.
    pub fn repository(root: &Path) -> Self {
        GuardInputs {
            tree_root: root.to_path_buf(),
            history: HistorySource::Repository(root.to_path_buf()),
            head: "HEAD".into(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct FileRecord {
    sha256: String,
    bytes: Option<u64>,
}

#[derive(Debug, Clone)]
struct LineageEntry {
    commit: String,
    docs_bid_tree: String,
    files: BTreeMap<String, FileRecord>,
}

#[derive(Debug, Clone)]
struct Manifest {
    technical_source: String,
    technical_source_tree: String,
    technical_source_files: BTreeMap<String, FileRecord>,
    lineage: Vec<LineageEntry>,
    terminal: String,
    manifest_path: String,
    mission_path: String,
    mission_sha256: String,
    authorizations: Vec<Value>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum Expect {
    Present(FileRecord),
    Absent,
}

fn is_hex(s: &str, n: usize) -> bool {
    s.len() == n && s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn safe_rel(p: &str) -> bool {
    !p.is_empty()
        && !p.starts_with('/')
        && !p.contains('\\')
        && p.split('/').all(|seg| !seg.is_empty() && seg != "." && seg != "..")
}

fn get<'a>(v: &'a Value, key: &str) -> Result<&'a Value, String> {
    v.get(key).ok_or_else(|| format!("missing field {key}"))
}

fn get_str<'a>(v: &'a Value, key: &str) -> Result<&'a str, String> {
    get(v, key)?.as_str().ok_or_else(|| format!("field {key} is not a string"))
}

fn hex_field(v: &Value, key: &str, n: usize) -> Result<String, String> {
    let s = get_str(v, key)?;
    if !is_hex(s, n) {
        return Err(format!("field {key} is not {n} lower-case hex digits"));
    }
    Ok(s.to_string())
}

fn file_map(v: &Value, key: &str, prefix: &str) -> Result<BTreeMap<String, FileRecord>, String> {
    let obj = get(v, key)?.as_object().ok_or_else(|| format!("field {key} is not an object"))?;
    if obj.is_empty() {
        return Err(format!("field {key} is empty"));
    }
    let mut out = BTreeMap::new();
    for (path, rec) in obj {
        if !safe_rel(path) || !path.starts_with(prefix) {
            return Err(format!("{key}: path {path:?} is not a safe relative path under {prefix:?}"));
        }
        let sha256 = hex_field(rec, "sha256", 64).map_err(|e| format!("{key}[{path}]: {e}"))?;
        let bytes = match rec.get("bytes") {
            None => None,
            Some(b) => Some(b.as_u64().ok_or_else(|| format!("{key}[{path}]: bytes is not a non-negative integer"))?),
        };
        out.insert(path.clone(), FileRecord { sha256, bytes });
    }
    Ok(out)
}

fn parse_manifest(bytes: &[u8]) -> Result<Manifest, String> {
    let v: Value = serde_json::from_slice(bytes).map_err(|e| format!("not JSON: {e}"))?;
    if get_str(&v, "schema")? != MANIFEST_SCHEMA {
        return Err(format!("schema is not {MANIFEST_SCHEMA}"));
    }
    let ts = get(&v, "technical_source")?;
    let lineage_v = get(&v, "package_lineage")?.as_array().ok_or("package_lineage is not a list")?;
    if lineage_v.is_empty() {
        return Err("package_lineage is empty".into());
    }
    let mut lineage = Vec::new();
    for (i, e) in lineage_v.iter().enumerate() {
        lineage.push(LineageEntry {
            commit: hex_field(e, "commit", 40).map_err(|m| format!("package_lineage[{i}]: {m}"))?,
            docs_bid_tree: hex_field(e, "docs_bid_tree", 40).map_err(|m| format!("package_lineage[{i}]: {m}"))?,
            files: file_map(e, "files", PROTECTED_ROOT).map_err(|m| format!("package_lineage[{i}]: {m}"))?,
        });
    }
    let mission = get(&v, "mission_scenario_v2")?;
    let ignored =
        get(&v, "ignored_generated_artifacts")?.as_array().ok_or("ignored_generated_artifacts is not a list")?;
    let patterns: Vec<Option<&str>> = ignored.iter().map(|x| x.get("pattern").and_then(Value::as_str)).collect();
    if patterns != [Some(IGNORED_PATTERN)] {
        return Err(format!("ignored_generated_artifacts must be exactly [{IGNORED_PATTERN}]"));
    }
    let authorizations =
        get(&v, "owner_change_authorizations")?.as_array().ok_or("owner_change_authorizations is not a list")?.clone();
    Ok(Manifest {
        technical_source: hex_field(ts, "commit", 40).map_err(|m| format!("technical_source: {m}"))?,
        technical_source_tree: hex_field(ts, "tree", 40).map_err(|m| format!("technical_source: {m}"))?,
        technical_source_files: file_map(ts, "files", "").map_err(|m| format!("technical_source: {m}"))?,
        lineage,
        terminal: hex_field(get(&v, "terminal_package_state")?, "commit", 40)
            .map_err(|m| format!("terminal_package_state: {m}"))?,
        manifest_path: get_str(&v, "manifest_path")?.to_string(),
        mission_path: get_str(mission, "path")?.to_string(),
        mission_sha256: hex_field(mission, "sha256", 64).map_err(|m| format!("mission_scenario_v2: {m}"))?,
        authorizations,
    })
}

fn finding(code: Code, path: &str, detail: impl Into<String>) -> Finding {
    Finding { code, path: path.to_string(), detail: detail.into() }
}

/// F-02: the manifest records exactly the governed constants.
fn check_record(m: &Manifest, out: &mut Vec<Finding>) {
    let mut chk = |ok: bool, field: &str, detail: String| {
        if !ok {
            out.push(finding(Code::LineageRecordMismatch, field, detail));
        }
    };
    chk(
        m.technical_source == TECHNICAL_SOURCE,
        "technical_source.commit",
        format!("{} != {TECHNICAL_SOURCE}", m.technical_source),
    );
    chk(
        m.terminal == TERMINAL_PACKAGE_STATE,
        "terminal_package_state.commit",
        format!("{} != {TERMINAL_PACKAGE_STATE}", m.terminal),
    );
    let commits: Vec<&str> = m.lineage.iter().map(|e| e.commit.as_str()).collect();
    chk(commits == PACKAGE_LINEAGE, "package_lineage", format!("{commits:?} != {PACKAGE_LINEAGE:?}"));
    let last = m.lineage.last().map(|e| e.commit.as_str()).unwrap_or("");
    chk(
        last == m.terminal,
        "terminal_package_state.commit",
        format!("last lineage entry {last} != terminal {}", m.terminal),
    );
    chk(m.mission_path == MISSION_SCENARIO_PATH, "mission_scenario_v2.path", m.mission_path.clone());
    chk(m.mission_sha256 == MISSION_SCENARIO_SHA256, "mission_scenario_v2.sha256", m.mission_sha256.clone());
    chk(m.manifest_path == MANIFEST_PATH, "manifest_path", m.manifest_path.clone());
}

/// F-08: validate owner_change_authorizations and build the expected docs/bid state.
fn expected_state(m: &Manifest, root: &Path, out: &mut Vec<Finding>) -> BTreeMap<String, Expect> {
    let protected = &m.lineage.last().expect("non-empty lineage").files;
    let mut expected: BTreeMap<String, Expect> =
        protected.iter().map(|(p, r)| (p.clone(), Expect::Present(r.clone()))).collect();
    let mut claimed: BTreeSet<String> = BTreeSet::new();
    for (i, a) in m.authorizations.iter().enumerate() {
        match validate_authorization(a, root, protected, &claimed) {
            Ok(changes) => {
                for (path, e) in changes {
                    claimed.insert(path.clone());
                    expected.insert(path, e);
                }
            }
            Err(e) => out.push(finding(Code::AuthorizationInvalid, &format!("owner_change_authorizations[{i}]"), e)),
        }
    }
    expected
}

fn validate_authorization(
    a: &Value,
    root: &Path,
    protected: &BTreeMap<String, FileRecord>,
    claimed: &BTreeSet<String>,
) -> Result<Vec<(String, Expect)>, String> {
    let rec = get(a, "decision_record")?;
    let rpath = get_str(rec, "path")?;
    let rsha = hex_field(rec, "sha256", 64)?;
    if !rpath.starts_with(DECISION_PREFIX) || !safe_rel(rpath) {
        return Err(format!("decision record {rpath:?} is not under {DECISION_PREFIX}"));
    }
    let bytes = fs::read(root.join(rpath)).map_err(|e| format!("decision record {rpath}: {e}"))?;
    if sha256_hex(&bytes) != rsha {
        return Err(format!("decision record {rpath}: sha256 differs from the authorization"));
    }
    let changes = get(a, "changes")?.as_array().ok_or("changes is not a list")?;
    if changes.is_empty() {
        return Err("changes is empty".into());
    }
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    for c in changes {
        let path = get_str(c, "path")?;
        let action = get_str(c, "action")?;
        if !safe_rel(path) || !path.starts_with(PROTECTED_ROOT) || path == MANIFEST_PATH {
            return Err(format!("{path:?} is not an authorizable docs/bid path"));
        }
        if claimed.contains(path) || !seen.insert(path.to_string()) {
            return Err(format!("{path} is authorized twice"));
        }
        let after = c.get("sha256_after");
        let e = match action {
            "MODIFY" | "ADD" => {
                let is_protected = protected.contains_key(path);
                if (action == "MODIFY") != is_protected {
                    return Err(format!("{action} of {path}: protected = {is_protected}"));
                }
                let sha = after.and_then(Value::as_str).filter(|s| is_hex(s, 64));
                Expect::Present(FileRecord {
                    sha256: sha.ok_or_else(|| format!("{action} of {path} needs a 64-hex sha256_after"))?.to_string(),
                    bytes: None,
                })
            }
            "REMOVE" => {
                if !protected.contains_key(path) {
                    return Err(format!("REMOVE of {path}: not a protected file"));
                }
                if after.is_some() {
                    return Err(format!("REMOVE of {path} carries sha256_after"));
                }
                Expect::Absent
            }
            other => return Err(format!("action {other:?} is not MODIFY / ADD / REMOVE")),
        };
        out.push((path.to_string(), e));
    }
    Ok(out)
}

fn compare(rec: &FileRecord, data: &[u8]) -> Option<String> {
    let sha = sha256_hex(data);
    if sha != rec.sha256 {
        return Some(format!("sha256 {sha} != {}", rec.sha256));
    }
    match rec.bytes {
        Some(n) if n != data.len() as u64 => Some(format!("{} bytes != {n}", data.len())),
        _ => None,
    }
}

fn is_ignored_artifact(rel: &str, is_file: bool) -> bool {
    let mut segs: Vec<&str> = rel.split('/').collect();
    let name = segs.pop().unwrap_or("");
    is_file && segs.last() == Some(&"__pycache__") && name.ends_with(".pyc")
}

fn walk(dir: &Path, rel: &str, out: &mut Vec<(String, bool)>) {
    let Ok(rd) = fs::read_dir(dir) else { return };
    let mut entries: Vec<_> = rd.filter_map(Result::ok).collect();
    entries.sort_by_key(|e| e.file_name());
    for e in entries {
        let name = e.file_name().to_string_lossy().to_string();
        let r = format!("{rel}/{name}");
        match fs::symlink_metadata(e.path()) {
            Ok(md) if md.is_dir() => walk(&e.path(), &r, out),
            Ok(md) => out.push((r, md.is_file())),
            Err(_) => out.push((r, false)),
        }
    }
}

/// Files part (F-01..F-08). Returns the expected state for the history part.
fn files_part(root: &Path, m: &Manifest) -> (PartReport, BTreeMap<String, Expect>) {
    let mut out = Vec::new();
    check_record(m, &mut out);
    let expected = expected_state(m, root, &mut out);
    for (path, e) in &expected {
        let p = root.join(path);
        match (e, fs::symlink_metadata(&p)) {
            (Expect::Present(_), Err(_)) => {
                out.push(finding(Code::BidFileMissing, path, "absent from the working tree"))
            }
            (Expect::Present(_), Ok(md)) if !md.is_file() => {
                out.push(finding(Code::BidFileModified, path, "not a regular file"))
            }
            (Expect::Present(rec), Ok(_)) => match fs::read(&p) {
                Ok(data) => {
                    if let Some(d) = compare(rec, &data) {
                        out.push(finding(Code::BidFileModified, path, d));
                    }
                }
                Err(e) => out.push(finding(Code::BidFileModified, path, format!("unreadable: {e}"))),
            },
            (Expect::Absent, Ok(_)) => {
                out.push(finding(Code::BidFileUnlisted, path, "removed by authorization but present"))
            }
            (Expect::Absent, Err(_)) => {}
        }
    }
    let mut entries = Vec::new();
    walk(&root.join(PROTECTED_ROOT.trim_end_matches('/')), PROTECTED_ROOT.trim_end_matches('/'), &mut entries);
    for (rel, is_file) in entries {
        if expected.contains_key(&rel) || rel == MANIFEST_PATH || is_ignored_artifact(&rel, is_file) {
            continue;
        }
        out.push(finding(Code::BidFileUnlisted, &rel, "not a file of the terminal package state"));
    }
    match fs::read(root.join(MISSION_SCENARIO_PATH)) {
        Ok(d) if sha256_hex(&d) == MISSION_SCENARIO_SHA256 => {}
        Ok(d) => {
            out.push(finding(Code::MissionScenarioChanged, MISSION_SCENARIO_PATH, format!("sha256 {}", sha256_hex(&d))))
        }
        Err(e) => out.push(finding(Code::MissionScenarioChanged, MISSION_SCENARIO_PATH, format!("unreadable: {e}"))),
    }
    let pin = fs::read(root.join(BASELINE_PATH))
        .ok()
        .and_then(|b| serde_json::from_slice::<Value>(&b).ok())
        .and_then(|v| v.pointer("/bid_technical_source/commit").and_then(Value::as_str).map(str::to_string));
    if pin.as_deref() != Some(TECHNICAL_SOURCE) {
        out.push(finding(
            Code::TechnicalSourcePinChanged,
            BASELINE_PATH,
            format!("bid_technical_source.commit = {pin:?}"),
        ));
    }
    (PartReport::from_findings(out), expected)
}

fn blob_requests(git: &Git, rev: &str) -> Result<BTreeMap<String, String>, String> {
    Ok(git.ls_tree(rev, PROTECTED_ROOT.trim_end_matches('/'))?.into_iter().collect())
}

/// History part (H-00..H-07).
fn history_part(source: &HistorySource, head: &str, m: &Manifest, expected: &BTreeMap<String, Expect>) -> PartReport {
    let repo = match source {
        HistorySource::None => return PartReport::not_evaluated("no git repository given".into()),
        HistorySource::Repository(p) => p,
    };
    let git = Git::new(repo);
    match git.output(&["rev-parse", "--is-shallow-repository"]) {
        Err(e) => return PartReport::not_evaluated(e),
        Ok(o) if !o.status.success() => {
            return PartReport::not_evaluated(format!(
                "not a git repository: {}",
                String::from_utf8_lossy(&o.stderr).trim()
            ))
        }
        Ok(o) => match String::from_utf8_lossy(&o.stdout).trim() {
            "false" => {}
            "true" => return PartReport::not_evaluated(
                "shallow clone: the lineage cannot be verified; fetch full history (actions/checkout fetch-depth: 0)"
                    .into(),
            ),
            other => {
                return PartReport::from_findings(vec![finding(
                    Code::GitError,
                    "",
                    format!("rev-parse --is-shallow-repository printed {other:?}"),
                )])
            }
        },
    }
    match history_checks(&git, head, m, expected) {
        Ok(f) => PartReport::from_findings(f),
        Err(e) => PartReport::from_findings(vec![finding(Code::GitError, "", e)]),
    }
}

fn history_checks(
    git: &Git,
    head: &str,
    m: &Manifest,
    expected: &BTreeMap<String, Expect>,
) -> Result<Vec<Finding>, String> {
    let mut out = Vec::new();
    // H-01: every recorded commit and the head resolve to commits.
    let mut revs: Vec<(String, String)> = vec![("technical_source.commit".into(), m.technical_source.clone())];
    for (i, e) in m.lineage.iter().enumerate() {
        revs.push((format!("package_lineage[{i}].commit"), e.commit.clone()));
    }
    revs.push(("terminal_package_state.commit".into(), m.terminal.clone()));
    revs.push(("head".into(), head.to_string()));
    let reqs: Vec<String> = revs.iter().map(|(_, r)| format!("{r}^{{commit}}")).collect();
    for ((label, rev), item) in revs.iter().zip(git.cat_file(&reqs, false)?) {
        if item == BatchItem::Missing {
            let code = if label == "head" { Code::GitError } else { Code::LineageCommitMissing };
            out.push(finding(code, label, format!("{rev} is not a commit of this repository")));
        }
    }
    if !out.is_empty() {
        return Ok(out);
    }
    // H-02: ancestry technical source -> lineage[0] -> ... -> lineage[-1]; terminal -> head.
    let mut pairs = vec![(m.technical_source.clone(), m.lineage[0].commit.clone())];
    for w in m.lineage.windows(2) {
        pairs.push((w[0].commit.clone(), w[1].commit.clone()));
    }
    pairs.push((m.terminal.clone(), head.to_string()));
    for (a, b) in pairs {
        if !git.is_ancestor(&a, &b)? {
            out.push(finding(
                Code::LineageAncestryBroken,
                &format!("{a}..{b}"),
                format!("{a} is not an ancestor of {b}"),
            ));
        }
    }
    // H-03: tree ids.
    let mut trees = vec![(format!("{}^{{tree}}", m.technical_source), m.technical_source_tree.clone())];
    for e in &m.lineage {
        trees.push((format!("{}:docs/bid", e.commit), e.docs_bid_tree.clone()));
    }
    let reqs: Vec<String> = trees.iter().map(|(r, _)| r.clone()).collect();
    for ((req, want), item) in trees.iter().zip(git.cat_file(&reqs, false)?) {
        let got = match item {
            BatchItem::Object { oid, .. } => oid,
            BatchItem::Missing => "missing".into(),
        };
        if &got != want {
            out.push(finding(Code::TreeHashMismatch, req, format!("{got} != recorded {want}")));
        }
    }
    // H-04 (lineage files), H-05 (technical-source files), H-06 (head docs/bid), H-07 (head mission): one batch read.
    let mut reqs: Vec<String> = Vec::new();
    let mut lineage_trees = Vec::new();
    for e in &m.lineage {
        let t = blob_requests(git, &e.commit)?;
        let listed: BTreeSet<&String> = t.keys().collect();
        let recorded: BTreeSet<&String> = e.files.keys().collect();
        for p in recorded.symmetric_difference(&listed) {
            out.push(finding(Code::LineageFilesMismatch, p, format!("file sets differ at {}", e.commit)));
        }
        lineage_trees.push(t);
    }
    let head_tree = blob_requests(git, head)?;
    for (e, t) in m.lineage.iter().zip(&lineage_trees) {
        for p in e.files.keys().filter(|p| t.contains_key(*p)) {
            reqs.push(t[p].clone());
        }
    }
    for p in m.technical_source_files.keys() {
        reqs.push(format!("{}:{p}", m.technical_source));
    }
    for (p, e) in expected {
        if matches!(e, Expect::Present(_)) && head_tree.contains_key(p) {
            reqs.push(head_tree[p].clone());
        }
    }
    reqs.push(format!("{head}:{MISSION_SCENARIO_PATH}"));
    let mut items = git.cat_file(&reqs, true)?.into_iter();
    let mut next = || -> Option<Vec<u8>> {
        match items.next() {
            Some(BatchItem::Object { kind, content, .. }) if kind == "blob" => content,
            _ => None,
        }
    };
    for (e, t) in m.lineage.iter().zip(&lineage_trees) {
        for (p, rec) in e.files.iter().filter(|(p, _)| t.contains_key(*p)) {
            match next() {
                Some(d) => {
                    if let Some(diff) = compare(rec, &d) {
                        out.push(finding(Code::LineageFilesMismatch, p, format!("at {}: {diff}", e.commit)));
                    }
                }
                None => out.push(finding(Code::LineageFilesMismatch, p, format!("unreadable at {}", e.commit))),
            }
        }
    }
    for (p, rec) in &m.technical_source_files {
        match next() {
            Some(d) => {
                if let Some(diff) = compare(rec, &d) {
                    out.push(finding(Code::TechnicalSourceFileMismatch, p, diff));
                }
            }
            None => out.push(finding(Code::TechnicalSourceFileMismatch, p, "absent at the technical source")),
        }
    }
    for (p, e) in expected {
        match e {
            Expect::Present(rec) if head_tree.contains_key(p) => match next() {
                Some(d) => {
                    if let Some(diff) = compare(rec, &d) {
                        out.push(finding(Code::BidFileModified, p, format!("committed at {head}: {diff}")));
                    }
                }
                None => out.push(finding(Code::BidFileModified, p, format!("unreadable at {head}"))),
            },
            Expect::Present(_) => out.push(finding(Code::BidFileMissing, p, format!("not committed at {head}"))),
            Expect::Absent if head_tree.contains_key(p) => {
                out.push(finding(Code::BidFileUnlisted, p, format!("removed by authorization but committed at {head}")))
            }
            Expect::Absent => {}
        }
    }
    for p in head_tree.keys() {
        if !expected.contains_key(p) && p != MANIFEST_PATH {
            out.push(finding(Code::BidFileUnlisted, p, format!("committed at {head}, not a terminal package file")));
        }
    }
    match next() {
        Some(d) if sha256_hex(&d) == MISSION_SCENARIO_SHA256 => {}
        Some(d) => out.push(finding(
            Code::MissionScenarioChanged,
            MISSION_SCENARIO_PATH,
            format!("committed at {head}: sha256 {}", sha256_hex(&d)),
        )),
        None => out.push(finding(Code::MissionScenarioChanged, MISSION_SCENARIO_PATH, format!("absent at {head}"))),
    }
    Ok(out)
}

/// Evaluate the guard. Never panics on bad input: an unreadable or invalid manifest fails both parts.
pub fn evaluate(inputs: &GuardInputs) -> GuardReport {
    let mpath = inputs.tree_root.join(MANIFEST_PATH);
    let parsed = fs::read(&mpath).map_err(|e| format!("{}: {e}", mpath.display())).and_then(|b| parse_manifest(&b));
    let m = match parsed {
        Ok(m) => m,
        Err(e) => {
            let f = || PartReport::from_findings(vec![finding(Code::ManifestInvalid, MANIFEST_PATH, e.clone())]);
            return GuardReport::new(f(), f());
        }
    };
    let (files, expected) = files_part(&inputs.tree_root, &m);
    let history = history_part(&inputs.history, &inputs.head, &m, &expected);
    GuardReport::new(files, history)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hex_and_path_rules() {
        assert!(is_hex(TECHNICAL_SOURCE, 40) && is_hex(MISSION_SCENARIO_SHA256, 64));
        assert!(!is_hex(&TECHNICAL_SOURCE.to_uppercase(), 40) && !is_hex("abc", 3 + 1));
        assert!(safe_rel("docs/bid/x.md"));
        for bad in ["", "/etc/passwd", "docs/../x", "docs//x", "docs\\x", "./x"] {
            assert!(!safe_rel(bad), "{bad}");
        }
    }

    #[test]
    fn only_bytecode_under_pycache_is_ignored() {
        assert!(is_ignored_artifact("docs/bid/package/__pycache__/a.cpython-311.pyc", true));
        assert!(!is_ignored_artifact("docs/bid/package/__pycache__/a.cpython-311.pyc", false));
        assert!(!is_ignored_artifact("docs/bid/package/__pycache__/notes.txt", true));
        assert!(!is_ignored_artifact("docs/bid/package/a.pyc", true));
    }

    #[test]
    fn overall_never_passes_without_history() {
        let pass = || PartReport::from_findings(Vec::new());
        assert_eq!(GuardReport::new(pass(), pass()).overall, GuardStatus::Pass);
        assert_eq!(GuardReport::new(pass(), PartReport::not_evaluated("x".into())).overall, GuardStatus::NotEvaluated);
        let fail = PartReport::from_findings(vec![finding(Code::BidFileMissing, "p", "d")]);
        assert_eq!(GuardReport::new(fail, PartReport::not_evaluated("x".into())).overall, GuardStatus::Fail);
    }

    #[test]
    fn invalid_manifests_are_refused() {
        assert!(parse_manifest(b"{").is_err());
        assert!(parse_manifest(br#"{"schema": "other"}"#).is_err());
        assert!(parse_manifest(br#"{"schema": "abep_bid_source_manifest_v1"}"#).is_err());
    }
}
