//! Runner of the NI-ABEP-CLI acceptance cases (acceptance_v2 `acceptance_cases`, `checks`, `decision_rules`).
//!
//! It executes the cases registered in the preregistration file against a built `abep` binary, as separate processes,
//! and evaluates every check. `Mode::Acceptance` is the single scored run (clean committed tree required; the caller
//! writes the report); `Mode::Development` runs the same cases as cargo-test regression and is never a report.

use abep_provenance::sha256_hex;
use abep_types::pyjson::{self, Value as Py};
use serde_json::{json, Value as Js};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;

pub const PREREG_REL: &str = "docs/rust_migration/contracts/NI-ABEP-CLI/acceptance_v2.json";
/// The files behind the governing hashes (result record `governing_hashes`).
const GOVERNING_FILES: [(&str, &str); 5] = [
    ("config_manifest", "config/MANIFEST.json"),
    ("architecture", "config/architecture/hall_icp_neutralizer_v1.json"),
    ("model_set", "config/model_set/physics_model_set_v1.json"),
    ("design_state_set_reference", "config/environment/design_state_set_ref_v1.json"),
    ("design_state_set", "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json"),
];
/// Run set entry (acceptance_v2 `run_set`): label, `--threads` value (None = default), extra environment.
type RunSpec = (&'static str, Option<&'static str>, &'static [(&'static str, &'static str)]);
const THREAD_ENV: [&str; 3] = ["OMP_NUM_THREADS", "RAYON_NUM_THREADS", "OPENBLAS_NUM_THREADS"];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Acceptance,
    Development,
}

pub struct Config {
    pub repo: PathBuf,
    pub abep: PathBuf,
    /// Scratch directory outside the repository (clone, outputs).
    pub work: PathBuf,
    pub mode: Mode,
}

/// One process run of the binary.
#[derive(Debug, Clone)]
struct RunOut {
    label: String,
    argv: Vec<String>,
    code: Option<i32>,
    stderr: String,
    out: PathBuf,
    files: Vec<String>,
    result: Option<Vec<u8>>,
    sidecar: Option<Vec<u8>>,
}

fn git(dir: &Path, args: &[&str]) -> Result<String, String> {
    let o = Command::new("git").arg("-C").arg(dir).args(args).output().map_err(|e| format!("git: {e}"))?;
    if !o.status.success() {
        return Err(format!("git {args:?} in {}: {}", dir.display(), String::from_utf8_lossy(&o.stderr).trim()));
    }
    Ok(String::from_utf8_lossy(&o.stdout).trim().to_string())
}

fn invoke(abep: &Path, label: &str, argv: Vec<String>, out: &Path, env: &[(&str, &str)]) -> RunOut {
    let mut cmd = Command::new(abep);
    cmd.args(&argv);
    for k in THREAD_ENV {
        cmd.env_remove(k);
    }
    for (k, v) in env {
        cmd.env(k, v);
    }
    let o = cmd.output();
    let (code, stderr) = match o {
        Ok(o) => (o.status.code(), String::from_utf8_lossy(&o.stderr).into_owned()),
        Err(e) => (None, format!("spawn failed: {e}")),
    };
    let mut files: Vec<String> = std::fs::read_dir(out)
        .map(|rd| rd.filter_map(|e| e.ok()).map(|e| e.file_name().to_string_lossy().into_owned()).collect())
        .unwrap_or_default();
    files.sort();
    let pick = |suffix: &str| files.iter().find(|f| f.ends_with(suffix)).and_then(|f| std::fs::read(out.join(f)).ok());
    RunOut {
        label: label.to_string(),
        argv,
        code,
        stderr,
        out: out.to_path_buf(),
        result: pick(".result.json"),
        sidecar: pick(".run_record.json"),
        files,
    }
}

fn get<'a>(v: &'a Py, path: &[&str]) -> Option<&'a Py> {
    let mut cur = v;
    for k in path {
        cur = cur.as_dict()?.get(k)?;
    }
    Some(cur)
}

fn get_str<'a>(v: &'a Py, path: &[&str]) -> Option<&'a str> {
    get(v, path).and_then(Py::as_str)
}

fn get_num(v: &Py, path: &[&str]) -> Option<f64> {
    get(v, path).and_then(|x| x.to_f64().ok())
}

/// Every string value (not key) anywhere in `v`.
fn string_values(v: &Py, out: &mut Vec<String>) {
    match v {
        Py::Str(s) => out.push(s.clone()),
        Py::List(l) => l.iter().for_each(|x| string_values(x, out)),
        Py::Dict(d) => d.values().for_each(|x| string_values(x, out)),
        _ => {}
    }
}

fn all_keys(v: &Py, out: &mut Vec<String>) {
    match v {
        Py::List(l) => l.iter().for_each(|x| all_keys(x, out)),
        Py::Dict(d) => {
            for (k, x) in d.iter() {
                out.push(k.clone());
                all_keys(x, out);
            }
        }
        _ => {}
    }
}

/// The payload text spliced into a result record (the value of its last key).
pub fn payload_text(result: &str) -> Option<&str> {
    let i = result.find("\n  \"payload\": ")?;
    result[i + 14..].strip_suffix("\n}\n")
}

struct Ctx<'a> {
    cfg: &'a Config,
    prereg: &'a Js,
    expected_hashes: BTreeMap<String, String>,
}

impl Ctx<'_> {
    fn command_components(&self, command: &str) -> Vec<(String, String)> {
        let registry = &self.prereg["admission_registry"]["entries"];
        let mut out = Vec::new();
        for c in self.prereg["commands"].as_array().into_iter().flatten() {
            if c["command"] == command {
                for id in c["components"].as_array().into_iter().flatten() {
                    let contract = registry
                        .as_array()
                        .into_iter()
                        .flatten()
                        .find(|e| e["component"] == *id)
                        .and_then(|e| e["contract_id"].as_str())
                        .unwrap_or("?");
                    out.push((id.as_str().unwrap_or("?").to_string(), contract.to_string()));
                }
            }
        }
        out
    }
}

/// Registered exit code of a status or refusal.
fn registered_exit(status: &str, reason_code: Option<&str>) -> Option<i32> {
    match (status, reason_code) {
        ("NOT_EVALUATED", Some("UNREGISTERED_INPUT")) => Some(3),
        ("MODEL_ERROR", Some("REPOSITORY_NOT_FOUND" | "CONFIG_MANIFEST_UNVERIFIED" | "RUN_RECORD_UNAVAILABLE")) => {
            Some(4)
        }
        ("EVALUATED", _) => Some(0),
        ("NOT_EVALUATED", _) => Some(10),
        ("INCOMPLETE_EVIDENCE", _) => Some(11),
        ("OUT_OF_DOMAIN", _) => Some(12),
        ("MODEL_ERROR", _) => Some(13),
        _ => None,
    }
}

const PROVENANCE_REFUSALS: [&str; 3] = ["REPOSITORY_NOT_FOUND", "CONFIG_MANIFEST_UNVERIFIED", "RUN_RECORD_UNAVAILABLE"];

/// Payload checks of a case (acceptance_v2 `payload_checks`), by case id.
fn payload_checks(id: &str, rec: &Py, payload_raw: &str) -> Vec<String> {
    let mut p = Vec::new();
    let pl = get(rec, &["payload"]).cloned().unwrap_or(Py::Null);
    let mut need = |ok: bool, what: &str| {
        if !ok {
            p.push(format!("payload check failed: {what}"));
        }
    };
    let list_len = |path: &[&str]| get(&pl, path).and_then(Py::as_list).map(<[Py]>::len);
    let each = |path: &[&str], inner: &[&str], want: &str| -> bool {
        get(&pl, path).and_then(Py::as_list).is_some_and(|l| l.iter().all(|x| get_str(x, inner) == Some(want)))
    };
    match id {
        "CMD-01" => {
            need(get_num(&pl, &["build_check", "exit"]) == Some(0.0), "build_check.exit == 0");
            need(get_num(&pl, &["manifest_files_verified"]) == Some(11.0), "manifest_files_verified == 11");
        }
        "CMD-02" => {
            need(list_len(&["checks"]) == Some(4), "4 checks");
            need(each(&["checks"], &["status"], "EVALUATED"), "every check EVALUATED");
            let no_findings = get(&pl, &["checks"]).and_then(Py::as_list).is_some_and(|l| {
                l.iter().all(|c| get(c, &["findings"]).and_then(Py::as_list).is_some_and(<[Py]>::is_empty))
            });
            need(no_findings, "no finding");
        }
        "CMD-03" => {
            need(get_num(&pl, &["n_states"]) == Some(196.0), "n_states == 196");
            need(get_num(&pl, &["n_evaluated"]) == Some(196.0), "n_evaluated == 196");
            need(list_len(&["records"]) == Some(196), "len(records) == 196");
        }
        "CMD-04" => {
            let fin = |k: &str| get_num(&pl, &["surface_v1", k]).is_some_and(f64::is_finite);
            need(fin("eta_c") && fin("c_d"), "surface_v1 eta_c and c_d finite");
            need(
                get_str(&pl, &["surface_v2_gate", "status"]) == Some("NOT_EVALUATED"),
                "surface_v2_gate NOT_EVALUATED",
            );
        }
        "CMD-05" => {
            need(get_num(&pl, &["n_states"]) == Some(196.0), "n_states == 196");
            need(get_num(&pl, &["n_t_minus_d_evaluated"]) == Some(0.0), "n_t_minus_d_evaluated == 0");
            need(get_str(&pl, &["credible_set"]) == Some("EMPTY"), "credible_set == EMPTY");
            need(each(&["states"], &["thrust", "status"], "NOT_EVALUATED"), "every thrust NOT_EVALUATED");
            need(
                each(&["states"], &["drag_intake", "status"], "INCOMPLETE_EVIDENCE"),
                "every drag_intake INCOMPLETE_EVIDENCE",
            );
        }
        "CMD-06" => {
            need(get(&pl, &["record", "reproduced"]) == Some(&Py::Bool(true)), "record.reproduced");
            let st: Vec<&str> = get(&pl, &["mass_gates"])
                .and_then(Py::as_list)
                .map(|l| l.iter().filter_map(|g| get_str(g, &["status"])).collect())
                .unwrap_or_default();
            need(st == ["NOT_EVALUATED", "INCOMPLETE_EVIDENCE", "INCOMPLETE_EVIDENCE"], "mass gate statuses");
        }
        "CMD-07" => {
            let mut keys = Vec::new();
            all_keys(&pl, &mut keys);
            let bad: Vec<&String> = keys
                .iter()
                .filter(|k| {
                    let l = k.to_lowercase();
                    l.starts_with("p_bus_max") || l.contains("limit")
                })
                .collect();
            need(bad.is_empty() && pl.as_dict().is_some(), "no p_bus_max* / *limit* key");
        }
        "CMD-08" => {
            need(get_str(&pl, &["gate", "reason"]) == Some("credible Hall transport set EMPTY"), "gate.reason");
            need(list_len(&["gate", "admitted_members"]) == Some(0), "admitted_members == []");
            need(get_str(&pl, &["hall_response_status", "credible_set"]) == Some("EMPTY"), "credible_set EMPTY");
        }
        "CMD-09" => {
            need(
                get_str(&pl, &["pin_report", "commit"]) == Some("bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5"),
                "pin commit",
            );
            need(get_str(&pl, &["pin_report", "version"]) == Some("0.23.1"), "pin version");
            need(get(&pl, &["pin_report", "verify_pin_ok"]) == Some(&Py::Bool(true)), "verify_pin_ok");
            need(get_str(&pl, &["julia_check_pin"]) == Some("NOT_EXECUTED_PLATFORM_TEST"), "julia_check_pin");
        }
        "CMD-10" | "CMD-11" => {
            let code = if id == "CMD-10" { "NP_ICP_CHEM_AIR_NOT_ADMITTED" } else { "CHG-04_NO_XE_RATE_SET" };
            need(get_str(&pl, &["status"]) == Some("INCOMPLETE_EVIDENCE"), "payload status INCOMPLETE_EVIDENCE");
            need(payload_raw.contains(&format!("\"{code}\"")), code);
            let adm = get(rec, &["components"])
                .and_then(Py::as_list)
                .and_then(|l| l.first())
                .and_then(|c| get_str(c, &["admission"]));
            need(adm == Some("NOT_ADMITTED"), "components[0].admission == NOT_ADMITTED");
        }
        "REF-02" => {
            need(get_num(&pl, &["build_check", "exit"]).is_some_and(|x| x != 0.0), "build_check.exit != 0");
        }
        _ => {}
    }
    p
}

/// Per-run checks EXIT, STATUS, PAYLOAD, FILES, PROV, NO_VERDICT.
fn check_run(ctx: &Ctx, case: &Js, command: Option<&str>, tree: &Path, r: &RunOut) -> Vec<String> {
    let id = case["id"].as_str().unwrap_or("?");
    let exp = &case["expected"];
    let mut p = Vec::new();
    let want_exit = exp["exit"].as_i64().map(|x| x as i32);
    if r.code != want_exit {
        p.push(format!("EXIT: {:?} != expected {:?} ({})", r.code, want_exit, r.stderr.trim()));
    }
    // Files.
    if let Some(n) = exp["files_written"].as_u64() {
        if r.files.len() as u64 != n || (n == 0 && r.out.exists()) {
            p.push(format!("FILES: {:?} written, expected {n} (and no output directory)", r.files));
        }
        return p;
    }
    let want_sidecar = exp["sidecar"].as_bool().unwrap_or(true);
    let expect_files = if want_sidecar { 2 } else { 1 };
    if r.files.len() != expect_files || r.result.is_none() || (want_sidecar != r.sidecar.is_some()) {
        p.push(format!("FILES: {:?}, expected result{}", r.files, if want_sidecar { " + sidecar" } else { " only" }));
    }
    let Some(bytes) = &r.result else {
        p.push("no result record".into());
        return p;
    };
    let text = String::from_utf8_lossy(bytes).into_owned();
    let rec = match pyjson::loads(&text) {
        Ok(v) => v,
        Err(e) => {
            p.push(format!("result record does not parse: {}", e.message));
            return p;
        }
    };
    // Status / reason / exit consistency.
    let status = get_str(&rec, &["status"]).unwrap_or("?").to_string();
    let reason_code = get_str(&rec, &["reason", "code"]).map(str::to_string);
    if Some(status.as_str()) != exp["status"].as_str() {
        p.push(format!("STATUS: {status} != expected {}", exp["status"]));
    }
    if let Some(want) = exp["reason_code"].as_str() {
        if reason_code.as_deref() != Some(want) {
            p.push(format!("STATUS: reason.code {reason_code:?} != expected {want}"));
        }
    }
    if (status == "EVALUATED") != (get(&rec, &["reason"]) == Some(&Py::Null)) {
        p.push("STATUS: reason must be null iff EVALUATED".into());
    }
    if let Some(want) = exp["reason_message_contains"].as_str() {
        if !get_str(&rec, &["reason", "message"]).is_some_and(|m| m.contains(want)) {
            p.push(format!("STATUS: reason.message does not contain {want:?}"));
        }
    }
    let rec_exit = get_num(&rec, &["exit_code"]).map(|x| x as i32);
    if rec_exit != r.code || registered_exit(&status, reason_code.as_deref()) != r.code {
        p.push(format!(
            "EXIT: record exit_code {rec_exit:?} / registered {:?} / process {:?}",
            registered_exit(&status, reason_code.as_deref()),
            r.code
        ));
    }
    // Payload.
    let payload_raw = payload_text(&text).unwrap_or("");
    if exp.get("payload").is_some_and(Js::is_null) && payload_raw != "null" {
        p.push("PAYLOAD: expected null".into());
    }
    p.extend(payload_checks(id, &rec, payload_raw));
    // Provenance.
    if !PROVENANCE_REFUSALS.contains(&reason_code.as_deref().unwrap_or("")) {
        let head = git(tree, &["rev-parse", "HEAD"]).unwrap_or_default();
        let s = |k: &str| get_str(&rec, &[k]);
        if s("implementation") != Some("rust") || s("contract_id") != Some("ACCEPT-NI-ABEP-CLI-V2") {
            p.push("PROV: implementation / contract_id".into());
        }
        if s("rust_commit") != Some(head.as_str()) || head.len() != 40 {
            p.push(format!("PROV: rust_commit {:?} != tree HEAD {head}", s("rust_commit")));
        }
        let gh = |path: &[&str]| get_str(&rec, &[&["governing_hashes"], path].concat()).map(str::to_string);
        let got: BTreeMap<String, Option<String>> = [
            ("config_manifest", gh(&["config_manifest", "sha256"])),
            ("architecture", gh(&["architecture", "sha256"])),
            ("model_set", gh(&["model_set", "sha256"])),
            ("design_state_set_reference", gh(&["design_state_set", "reference", "sha256"])),
            ("design_state_set", gh(&["design_state_set", "sha256"])),
        ]
        .into_iter()
        .map(|(k, v)| (k.to_string(), v))
        .collect();
        // The five files as they are in the evaluated tree (REPOSITORY: the registered expected values, checked as a
        // precondition; CLONE: the same unless a tamper operation rewrote one, as REF-02 does to the manifest).
        for (k, rel) in GOVERNING_FILES {
            let want = sha_file(&tree.join(rel));
            if got.get(k).cloned().flatten() != want {
                p.push(format!("PROV: governing hash {k} {:?} != tree {want:?}", got.get(k)));
            }
            if tree == ctx.cfg.repo && want.as_ref() != ctx.expected_hashes.get(k) {
                p.push(format!("PROV: repository {k} differs from the registered expected value"));
            }
        }
        if let Some(cmd) = command {
            let comps: Vec<(String, String)> = get(&rec, &["components"])
                .and_then(Py::as_list)
                .map(|l| {
                    l.iter()
                        .map(|c| {
                            (
                                get_str(c, &["component"]).unwrap_or("").to_string(),
                                get_str(c, &["contract_id"]).unwrap_or("").to_string(),
                            )
                        })
                        .collect()
                })
                .unwrap_or_default();
            if comps != ctx.command_components(cmd) {
                p.push(format!("PROV: components {comps:?} != registered"));
            }
        }
        if let Some(sc) = &r.sidecar {
            match serde_json::from_slice::<Js>(sc) {
                Err(e) => p.push(format!("PROV: sidecar does not parse: {e}")),
                Ok(sc) => {
                    let rr = &sc["run_record"];
                    if sc["result_sha256"] != sha256_hex(bytes) {
                        p.push("PROV: sidecar result_sha256 != sha256(result)".into());
                    }
                    if rr["schema"] != "abep_run_record_v1"
                        || rr["implementation"] != "rust"
                        || rr["git_commit"] != head
                    {
                        p.push("PROV: sidecar run_record schema / implementation / commit".into());
                    }
                    let same = [
                        ("config_manifest", rr["config_manifest"]["sha256"].as_str()),
                        ("architecture", rr["architecture"]["sha256"].as_str()),
                        ("model_set", rr["model_set"]["sha256"].as_str()),
                        ("design_state_set_reference", rr["design_state_set"]["reference"]["sha256"].as_str()),
                        ("design_state_set", rr["design_state_set"]["sha256"].as_str()),
                    ];
                    for (k, v) in same {
                        if got.get(k).cloned().flatten().as_deref() != v {
                            p.push(format!("PROV: sidecar governing hash {k} differs from the result record"));
                        }
                    }
                }
            }
        }
    }
    // No verdict values.
    let mut strings = Vec::new();
    string_values(&rec, &mut strings);
    if strings.iter().any(|s| s == "PASS" || s == "FAIL") {
        p.push("NO_VERDICT: a string value equals PASS or FAIL".into());
    }
    p
}

fn base_args(tree: &Path, out: &Path) -> Vec<String> {
    vec!["--repo".into(), tree.display().to_string(), "--out".into(), out.display().to_string()]
}

fn strs(v: &Js) -> Vec<String> {
    v.as_array().into_iter().flatten().filter_map(|x| x.as_str().map(str::to_string)).collect()
}

fn command_of(argv: &[String]) -> Option<String> {
    (argv.len() >= 2).then(|| format!("{} {}", argv[0], argv[1]))
}

/// The sidecar with the thread fields removed (DET-THREADS).
fn sidecar_sans_threads(b: &[u8]) -> Option<Js> {
    let mut v: Js = serde_json::from_slice(b).ok()?;
    let o = v.as_object_mut()?;
    o.remove("threads_requested");
    o.remove("threads_used");
    o.get_mut("run_record")?.as_object_mut()?.remove("threads");
    Some(v)
}

fn apply_tamper(tree: &Path, op: &Js) -> Result<(), String> {
    let path = |k: &str| tree.join(op[k].as_str().unwrap_or(""));
    match op["op"].as_str() {
        Some("append_text") => {
            let p = path("path");
            let mut b = std::fs::read(&p).map_err(|e| format!("{}: {e}", p.display()))?;
            b.extend_from_slice(op["text"].as_str().unwrap_or("").as_bytes());
            std::fs::write(&p, b).map_err(|e| e.to_string())
        }
        Some("delete") => std::fs::remove_file(path("path")).map_err(|e| e.to_string()),
        Some("manifest_rehash") => {
            let rel = op["rel"].as_str().unwrap_or("");
            let mp = tree.join("config/MANIFEST.json");
            let mut m: Js =
                serde_json::from_slice(&std::fs::read(&mp).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
            let bytes = std::fs::read(tree.join("config").join(rel)).map_err(|e| e.to_string())?;
            let entry = m["files"].get_mut(rel).ok_or_else(|| format!("{rel} not in the manifest"))?;
            entry["sha256"] = json!(sha256_hex(&bytes));
            entry["bytes"] = json!(bytes.len());
            std::fs::write(&mp, serde_json::to_string_pretty(&m).map_err(|e| e.to_string())? + "\n")
                .map_err(|e| e.to_string())
        }
        other => Err(format!("unknown tamper operation {other:?}")),
    }
}

/// The scratch clone of the repository at its HEAD (CLONE tree), restored to a pristine checkout.
fn fresh_clone(cfg: &Config, head: &str) -> Result<PathBuf, String> {
    let dir = cfg.work.join("clone");
    if !dir.join(".git").exists() {
        let o = Command::new("git")
            .args(["clone", "--shared", "--no-checkout", "-q"])
            .arg(&cfg.repo)
            .arg(&dir)
            .output()
            .map_err(|e| e.to_string())?;
        if !o.status.success() {
            return Err(format!("git clone: {}", String::from_utf8_lossy(&o.stderr)));
        }
    }
    git(&dir, &["checkout", "-q", "-f", "--detach", head])?;
    git(&dir, &["clean", "-fdq"])?;
    Ok(dir)
}

fn sha_file(p: &Path) -> Option<String> {
    std::fs::read(p).ok().map(|b| sha256_hex(&b))
}

/// Execute every registered case and check; returns the report body (without the report-level provenance the caller
/// adds) and the list of problems (empty iff ACCEPTED).
pub fn run(cfg: &Config) -> Result<(Js, Vec<String>), String> {
    let prereg_bytes = std::fs::read(cfg.repo.join(PREREG_REL)).map_err(|e| format!("{PREREG_REL}: {e}"))?;
    let prereg: Js = serde_json::from_slice(&prereg_bytes).map_err(|e| e.to_string())?;
    let mut problems: Vec<String> = Vec::new();

    // Input preconditions: the governing hashes and (scored run) a clean committed tree.
    let exp = &prereg["expected_on_the_acceptance_tree"]["governing_hashes"];
    let expected_hashes: BTreeMap<String, String> = exp
        .as_object()
        .ok_or("expected governing hashes missing")?
        .iter()
        .map(|(k, v)| (k.clone(), v.as_str().unwrap_or("").to_string()))
        .collect();
    let mut mismatch = Vec::new();
    for (k, rel) in GOVERNING_FILES {
        if sha_file(&cfg.repo.join(rel)).as_deref() != expected_hashes.get(k).map(String::as_str) {
            mismatch.push(rel);
        }
    }
    let head = git(&cfg.repo, &["rev-parse", "HEAD"])?;
    let dirty = !git(&cfg.repo, &["status", "--porcelain", "--untracked-files=no"])?.is_empty();
    if !mismatch.is_empty() || (cfg.mode == Mode::Acceptance && dirty) {
        return Ok((
            json!({"verdict": "NOT_RUN_INPUT_MISMATCH", "governing_hash_mismatch": mismatch, "git_dirty": dirty}),
            vec!["NOT_RUN_INPUT_MISMATCH".into()],
        ));
    }
    let ctx = Ctx { cfg, prereg: &prereg, expected_hashes };
    std::fs::create_dir_all(&cfg.work).map_err(|e| e.to_string())?;
    let outs = cfg.work.join("out");
    let _ = std::fs::remove_dir_all(&outs);

    // Command cases: R1..R4 on the repository.
    let mut case_reports = Vec::new();
    let mut env_payloads: Vec<(String, String)> = Vec::new();
    let mut det_run = Vec::new();
    let mut det_threads = Vec::new();
    for case in prereg["acceptance_cases"]["command_cases"].as_array().into_iter().flatten() {
        let id = case["id"].as_str().unwrap_or("?");
        let argv = strs(&case["argv"]);
        let command = command_of(&argv);
        let runs: [RunSpec; 4] = [
            ("R1", Some("1"), &[]),
            ("R2", Some("1"), &[]),
            ("R3", None, &[("OMP_NUM_THREADS", "4"), ("RAYON_NUM_THREADS", "4"), ("OPENBLAS_NUM_THREADS", "4")]),
            ("R4", Some("4"), &[]),
        ];
        let mut results = Vec::new();
        let mut run_reports = Vec::new();
        let mut case_problems = Vec::new();
        for (label, threads, env) in runs {
            let out = outs.join(id).join(label);
            let mut a = base_args(&cfg.repo, &out);
            if let Some(t) = threads {
                a.extend(["--threads".to_string(), t.to_string()]);
            }
            a.extend(argv.iter().cloned());
            let r = invoke(&cfg.abep, label, a, &out, env);
            let probs = check_run(&ctx, case, command.as_deref(), &cfg.repo, &r);
            case_problems.extend(probs.iter().map(|x| format!("{id} {label}: {x}")));
            run_reports.push(run_report(&r, &probs));
            results.push(r);
        }
        let eq = |a: &Option<Vec<u8>>, b: &Option<Vec<u8>>| a.is_some() && a == b;
        let (r1, r2, r3, r4) = (&results[0], &results[1], &results[2], &results[3]);
        let run_ok = eq(&r1.result, &r2.result) && eq(&r1.sidecar, &r2.sidecar);
        let threads_ok = eq(&r1.result, &r3.result)
            && eq(&r1.result, &r4.result)
            && [r3, r4].iter().all(|r| {
                r1.sidecar.as_deref().and_then(sidecar_sans_threads).is_some()
                    && r1.sidecar.as_deref().and_then(sidecar_sans_threads)
                        == r.sidecar.as_deref().and_then(sidecar_sans_threads)
            });
        if !run_ok {
            case_problems.push(format!("{id}: DET-RUN failed"));
        }
        if !threads_ok {
            case_problems.push(format!("{id}: DET-THREADS failed"));
        }
        det_run.push(json!({"case": id, "holds": run_ok}));
        det_threads.push(json!({"case": id, "holds": threads_ok}));
        if id == "CMD-03" {
            for r in [r1, r4] {
                let t = r.result.as_ref().map(|b| String::from_utf8_lossy(b).into_owned()).unwrap_or_default();
                env_payloads.push((r.label.clone(), payload_text(&t).unwrap_or("").to_string()));
            }
        }
        case_reports.push(json!({
            "id": id, "argv": argv, "expected": case["expected"], "runs": run_reports,
            "det_run": run_ok, "det_threads": threads_ok, "meets_expectation": case_problems.is_empty(),
            "problems": case_problems,
        }));
        problems.extend(case_problems);
    }

    // DET-ENV-CRATE.
    let crate_payload = abep_atmos::execution::run_design_state_set(&cfg.repo)
        .map_err(|e| e.to_string())
        .and_then(|r| serde_json::to_string(&r).map_err(|e| e.to_string()));
    let env_crate_ok = match &crate_payload {
        Ok(t) => env_payloads.len() == 2 && env_payloads.iter().all(|(_, p)| p == t),
        Err(_) => false,
    };
    if !env_crate_ok {
        problems.push("DET-ENV-CRATE failed".into());
    }

    // Refusal cases.
    let mut clone: Option<PathBuf> = None;
    for case in prereg["acceptance_cases"]["refusal_cases"].as_array().into_iter().flatten() {
        let id = case["id"].as_str().unwrap_or("?");
        let out = outs.join(id).join("R1");
        let tree: PathBuf = match case["tree"].as_str() {
            Some("CLONE") => {
                let c = match &clone {
                    Some(c) => {
                        git(c, &["checkout", "-q", "-f", "--detach", &head])?;
                        git(c, &["clean", "-fdq"])?;
                        c.clone()
                    }
                    None => {
                        let c = fresh_clone(cfg, &head)?;
                        clone = Some(c.clone());
                        c
                    }
                };
                for op in case["tamper"].as_array().into_iter().flatten() {
                    apply_tamper(&c, op)?;
                }
                c
            }
            Some("EMPTY_DIRECTORY") => {
                let d = cfg.work.join("empty_repo");
                let _ = std::fs::remove_dir_all(&d);
                std::fs::create_dir_all(&d).map_err(|e| e.to_string())?;
                d
            }
            _ => cfg.repo.clone(),
        };
        let mut a: Vec<String>;
        let argv: Vec<String>;
        if case.get("argv_without_out").is_some() {
            argv = strs(&case["argv_without_out"]);
            a = vec!["--repo".into(), tree.display().to_string()];
        } else if case.get("out").is_some() {
            argv = strs(&case["argv"]);
            let inside = cfg.repo.join("target").join("abep_cli_ref15");
            a = vec!["--repo".into(), tree.display().to_string(), "--out".into(), inside.display().to_string()];
            let r =
                invoke(&cfg.abep, "R1", [a, vec!["--threads".into(), "1".into()], argv.clone()].concat(), &inside, &[]);
            let probs = check_run(&ctx, case, command_of(&argv).as_deref(), &tree, &r);
            let cp: Vec<String> = probs.iter().map(|x| format!("{id}: {x}")).collect();
            case_reports.push(json!({"id": id, "argv": argv, "expected": case["expected"], "runs": [run_report(&r, &probs)], "meets_expectation": cp.is_empty(), "problems": cp}));
            problems.extend(cp);
            continue;
        } else {
            argv = strs(&case["argv"]);
            a = base_args(&tree, &out);
        }
        a.extend(["--threads".to_string(), "1".to_string()]);
        a.extend(argv.iter().cloned());
        let r = invoke(&cfg.abep, "R1", a, &out, &[]);
        let probs = check_run(&ctx, case, command_of(&argv).as_deref(), &tree, &r);
        let cp: Vec<String> = probs.iter().map(|x| format!("{id}: {x}")).collect();
        case_reports.push(json!({"id": id, "argv": argv, "expected": case["expected"], "runs": [run_report(&r, &probs)], "meets_expectation": cp.is_empty(), "problems": cp}));
        problems.extend(cp);
    }
    if let Some(c) = clone {
        let _ = std::fs::remove_dir_all(c);
    }

    // Static checks.
    let (dep_ok, dep_note) = static_dep(&cfg.repo);
    if !dep_ok {
        problems.push(format!("STATIC-DEP failed: {dep_note}"));
    }
    let nopy = static_nopy(&cfg.repo);
    if !nopy.is_empty() {
        problems.push(format!("STATIC-NOPY failed: {nopy:?}"));
    }

    let n_cases = case_reports.len();
    let n_ok = case_reports.iter().filter(|c| c["meets_expectation"] == true).count();
    let body = json!({
        "cases": case_reports,
        "determinism": {
            "DET-RUN": det_run,
            "DET-THREADS": det_threads,
            "DET-ENV-CRATE": {
                "holds": env_crate_ok,
                "crate_payload_sha256": crate_payload.as_ref().map(|t| sha256_hex(t.as_bytes())).ok(),
                "cli_payload_sha256": env_payloads.iter().map(|(l, p)| json!({"run": l, "sha256": sha256_hex(p.as_bytes())})).collect::<Vec<_>>(),
            },
        },
        "static": {
            "STATIC-DEP": {"holds": dep_ok, "note": dep_note},
            "STATIC-NOPY": {"holds": nopy.is_empty(), "offending_files": nopy},
        },
        "counts": {"cases": n_cases, "cases_meeting_expectation": n_ok, "runs": case_reports.iter().map(|c| c["runs"].as_array().map_or(0, Vec::len)).sum::<usize>()},
        "git_head": head,
        "git_dirty": dirty,
        "verdict": if problems.is_empty() { "ACCEPTED" } else { "NOT_ACCEPTED" },
    });
    Ok((body, problems))
}

fn run_report(r: &RunOut, problems: &[String]) -> Js {
    json!({
        "run": r.label,
        "argv_tail": r.argv.iter().skip_while(|a| a.starts_with("--") || a.starts_with('/')).cloned().collect::<Vec<_>>(),
        "exit": r.code,
        "files": r.files,
        "result_sha256": r.result.as_ref().map(|b| sha256_hex(b)),
        "sidecar_sha256": r.sidecar.as_ref().map(|b| sha256_hex(b)),
        "status": r.result.as_ref().and_then(|b| pyjson::loads(&String::from_utf8_lossy(b)).ok()).and_then(|v| get_str(&v, &["status"]).map(str::to_string)),
        "reason_code": r.result.as_ref().and_then(|b| pyjson::loads(&String::from_utf8_lossy(b)).ok()).and_then(|v| get_str(&v, &["reason", "code"]).map(str::to_string)),
        "checks_passed": problems.is_empty(),
        "problems": problems,
    })
}

/// STATIC-DEP: abep-cli's resolved dependency closure has no pyo3 / maturin, and no package depends on abep-cli.
fn static_dep(repo: &Path) -> (bool, String) {
    let o = Command::new("cargo")
        .args(["metadata", "--format-version", "1", "--locked", "--offline"])
        .current_dir(repo)
        .output();
    let meta: Js = match o {
        Ok(o) if o.status.success() => match serde_json::from_slice(&o.stdout) {
            Ok(v) => v,
            Err(e) => return (false, format!("cargo metadata output: {e}")),
        },
        Ok(o) => return (false, format!("cargo metadata: {}", String::from_utf8_lossy(&o.stderr).trim())),
        Err(e) => return (false, format!("cargo metadata: {e}")),
    };
    let name_of: BTreeMap<String, String> = meta["packages"]
        .as_array()
        .into_iter()
        .flatten()
        .map(|p| (p["id"].as_str().unwrap_or("").to_string(), p["name"].as_str().unwrap_or("").to_string()))
        .collect();
    let nodes = meta["resolve"]["nodes"].as_array().cloned().unwrap_or_default();
    let deps_of: BTreeMap<String, Vec<String>> = nodes
        .iter()
        .map(|n| {
            (
                n["id"].as_str().unwrap_or("").to_string(),
                n["dependencies"]
                    .as_array()
                    .into_iter()
                    .flatten()
                    .filter_map(|d| d.as_str().map(str::to_string))
                    .collect(),
            )
        })
        .collect();
    let Some(cli) = name_of.iter().find(|(_, n)| *n == "abep-cli").map(|(id, _)| id.clone()) else {
        return (false, "abep-cli not in cargo metadata".into());
    };
    let mut seen = std::collections::BTreeSet::new();
    let mut stack = vec![cli.clone()];
    while let Some(id) = stack.pop() {
        if seen.insert(id.clone()) {
            stack.extend(deps_of.get(&id).cloned().unwrap_or_default());
        }
    }
    let forbidden: Vec<&String> = seen
        .iter()
        .filter_map(|id| name_of.get(id))
        .filter(|n| n.starts_with("pyo3") || n.starts_with("maturin"))
        .collect();
    let dependents: Vec<&String> =
        deps_of.iter().filter(|(_, d)| d.contains(&cli)).filter_map(|(id, _)| name_of.get(id)).collect();
    let ok = forbidden.is_empty() && dependents.is_empty();
    (ok, format!("{} packages in the closure; forbidden {forbidden:?}; dependents {dependents:?}", seen.len()))
}

/// STATIC-NOPY: no abep-cli source spawns Python.
fn static_nopy(repo: &Path) -> Vec<String> {
    let needle = format!("Command::new(\"{}", "python");
    let mut bad = Vec::new();
    let mut stack = vec![repo.join("crates/abep-cli")];
    while let Some(d) = stack.pop() {
        for e in std::fs::read_dir(&d).into_iter().flatten().flatten() {
            let p = e.path();
            if p.is_dir() {
                stack.push(p);
            } else if p.extension().is_some_and(|x| x == "rs")
                && std::fs::read_to_string(&p).is_ok_and(|t| t.contains(&needle))
            {
                bad.push(p.display().to_string());
            }
        }
    }
    bad.sort();
    bad
}

/// sha256 of every file under crates/abep-cli (sorted, repository-relative).
pub fn source_sha256(repo: &Path) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    let mut stack = vec![repo.join("crates/abep-cli")];
    while let Some(d) = stack.pop() {
        for e in std::fs::read_dir(&d).into_iter().flatten().flatten() {
            let p = e.path();
            if p.is_dir() {
                stack.push(p);
            } else if let (Ok(rel), Some(sha)) = (p.strip_prefix(repo), sha_file(&p)) {
                out.insert(rel.display().to_string(), sha);
            }
        }
    }
    out
}
