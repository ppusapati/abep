//! NP-HALL-PARAMETRIC-ENVELOPE addendum A6 (XE grid at study-converged numerics;
//! `prereg_addendum_a6_xe_converged_grid_v1.json`, locked by `prereg_addendum_a6_xe_converged_grid_lock_v1.json`):
//! the numerics ladder, the convergence-study case file, its single scoring pass and production-level rule, and the XE
//! grid case file at the production level. Only numerical fields of the frozen v1 cases change. PARAMETRIC / NOT_VALIDATED.

use crate::envelope_a3::{self as a3, Delta};
use crate::envelope_cases::{self as ec, BRIDGE_LIB_REL, THREAD_PIN};
use crate::jobs::{child_env, JobSpec, ThreadSettings};
use abep_hall::envelope::{self as env, case_hash, Family, RunStatus};
use abep_provenance::{read_verified, sha256_hex};
use abep_types::pyjson::{self, Dict, DumpOptions, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::BTreeMap;
use std::io::Read;
use std::path::{Path, PathBuf};

pub const NP: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE";
pub const ADDENDUM_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a6_xe_converged_grid_v1.json";
pub const ADDENDUM_SHA256: &str = "004643cc2c0306ba44d096387d430600503ce3b9e5e3064d11a37c929e257281";
pub const LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a6_xe_converged_grid_lock_v1.json";
pub const LOCK_SHA256: &str = "e0a97161f8599ab0c11770751d95fac9cbd68a50b24de3bc6201d9ab6d2b089a";
pub const DRIVER_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_a6_driver.jl";
pub const SEED: &str = "NP-HALL-PARAMETRIC-ENVELOPE/A6/v1";
pub const CASES_SCHEMA: &str = "np_hall_parametric_envelope_a6_cases_v1";
pub const LAUNCH_SCHEMA: &str = "np_hall_parametric_envelope_a6_launch_manifest_v1";
pub const RAW_SCHEMA: &str = "np_hall_parametric_envelope_a6_raw_manifest_v1";
pub const STUDY_RESULT_SCHEMA: &str = "np_hall_parametric_envelope_a6_study_result_v1";
pub const CONTRACT_ID: &str = "NP-HALL-PARAMETRIC-ENVELOPE-A6-V1";
pub const STUDY_RESULT_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/a6_convergence_study_result_v1.json";
pub const V1_DT_S: f64 = 5e-9;

/// One of the two A6 case sets.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Study,
    Grid,
}

impl Kind {
    pub fn parse(s: &str) -> Option<Kind> {
        match s {
            "study" => Some(Kind::Study),
            "grid" => Some(Kind::Grid),
            _ => None,
        }
    }

    pub fn cases_rel(self) -> &'static str {
        match self {
            Kind::Study => "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a6_study_cases_v1.json",
            Kind::Grid => "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a6_xe_grid_v1.json",
        }
    }

    pub fn launch_name(self) -> &'static str {
        match self {
            Kind::Study => "launch_manifest_a6_study_v1.json",
            Kind::Grid => "launch_manifest_a6_xe_grid_v1.json",
        }
    }

    pub fn launch_rel(self) -> String {
        format!("{NP}/{}", self.launch_name())
    }

    pub fn n_shards(self) -> usize {
        match self {
            Kind::Study => 3,
            Kind::Grid => 64,
        }
    }
}

fn schema(path: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.into(), message: m.into() }
}

fn model(m: impl Into<String>) -> AbepError {
    AbepError::Model { message: m.into() }
}

fn io(path: &str, e: impl ToString) -> AbepError {
    AbepError::Io { path: path.into(), message: e.to_string() }
}

fn sval(x: &str) -> Value {
    Value::str(x)
}

fn fval(x: f64) -> Value {
    Value::Float(x)
}

fn dict(pairs: Vec<(&str, Value)>) -> Value {
    let mut d = Dict::new();
    for (k, v) in pairs {
        d.insert(k, v);
    }
    Value::Dict(d)
}

fn get<'a>(v: &'a Value, k: &str) -> Option<&'a Value> {
    v.as_dict().and_then(|d| d.get(k))
}

fn get_str<'a>(v: &'a Value, k: &str, label: &str) -> AbepResult<&'a str> {
    get(v, k).and_then(Value::as_str).ok_or_else(|| schema(label, format!("{k} missing or not a string")))
}

fn finite(v: Option<&Value>) -> Option<f64> {
    match v {
        Some(x @ (Value::Int(_) | Value::Float(_))) => x.to_f64().ok().filter(|f| f.is_finite()),
        _ => None,
    }
}

fn loads(bytes: &[u8], label: &str) -> AbepResult<Value> {
    let text = std::str::from_utf8(bytes).map_err(|e| schema(label, e.to_string()))?;
    pyjson::loads(text).map_err(|e| schema(label, e.to_string()))
}

fn strings(v: Option<&Value>, label: &str) -> AbepResult<Vec<String>> {
    v.and_then(Value::as_list)
        .ok_or_else(|| schema(label, "list missing"))?
        .iter()
        .map(|x| x.as_str().map(str::to_string).ok_or_else(|| schema(label, "not a string")))
        .collect()
}

/// The verified addendum (A6 lock and every file it locks).
pub fn load_addendum(repo: &Path) -> AbepResult<Value> {
    let lock = loads(&read_verified(&repo.join(LOCK_REL), LOCK_SHA256)?, LOCK_REL)?;
    let files = get(&lock, "files").and_then(Value::as_dict).ok_or_else(|| schema(LOCK_REL, "files"))?;
    for (f, h) in files.iter() {
        read_verified(&repo.join(NP).join(f), h.as_str().ok_or_else(|| schema(LOCK_REL, f.clone()))?)?;
    }
    loads(&read_verified(&repo.join(ADDENDUM_REL), ADDENDUM_SHA256)?, ADDENDUM_REL)
}

/// A numerics level of the ladder: cell factor 2^k and duration factor (1 or 2).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Level {
    pub k: u32,
    pub long: bool,
}

impl Level {
    pub fn id(self) -> String {
        format!("A6-L{}{}", self.k, if self.long { "D" } else { "" })
    }
}

/// The study levels in file order: L0, L1, L2, L3, L0D, L1D, L2D.
pub const STUDY_LEVELS: [Level; 7] = [
    Level { k: 0, long: false },
    Level { k: 1, long: false },
    Level { k: 2, long: false },
    Level { k: 3, long: false },
    Level { k: 0, long: true },
    Level { k: 1, long: true },
    Level { k: 2, long: true },
];

/// The v1 case at level `lv` (only cells, dt_s, duration_s, average_start_s change), with the A6 identity fields.
pub fn at_level(base: &Value, v1_key: &str, lv: Level) -> AbepResult<Value> {
    let Value::Dict(d) = base else { return Err(model("case is not an object")) };
    let label = env::CASES_REL;
    let v1_sha = get_str(base, "case_sha256", label)?.to_string();
    let cells = get(base, "cells").and_then(|v| if let Value::Int(i) = v { i.as_i64() } else { None });
    let cells = cells.ok_or_else(|| schema(label, "cells"))?;
    let dur = finite(get(base, "duration_s")).ok_or_else(|| schema(label, "duration_s"))?;
    let f = 1_i64 << lv.k;
    let mut n = d.clone();
    n.remove("case_sha256");
    let key = format!("{v1_key}|{}", lv.id());
    n.insert("key", sval(&key));
    n.insert("id", sval(&key));
    n.insert("cells", Value::int(cells * f));
    n.insert("dt_s", fval(V1_DT_S / f as f64));
    let d_mul = if lv.long { 2.0 } else { 1.0 };
    n.insert("duration_s", fval(d_mul * dur));
    n.insert("average_start_s", fval(d_mul * dur / 2.0));
    n.insert("a6_level", sval(&lv.id()));
    n.insert("v1_key", sval(v1_key));
    n.insert("v1_case_sha256", sval(&v1_sha));
    let h = case_hash(&Value::Dict(n.clone()))?;
    n.insert("case_sha256", sval(&h));
    Ok(Value::Dict(n))
}

/// The seeded study keys (addendum convergence_study.check_set_rule): one per hardware configuration.
pub fn seeded_keys(cs: &env::CaseSet) -> Vec<String> {
    let xe: Vec<&env::CaseInfo> = cs.cases.iter().filter(|c| c.family == Family::Xe).collect();
    let order = |f: fn(&env::CaseInfo) -> &str| {
        let mut v: Vec<String> = Vec::new();
        for c in &xe {
            if !v.iter().any(|s| s == f(c)) {
                v.push(f(c).to_string());
            }
        }
        v
    };
    let (g, s, b, vd, m, t) = (
        order(|c| &c.geometry_id),
        order(|c| &c.bz_shape_id),
        order(|c| &c.b_peak_id),
        order(|c| &c.vd_id),
        order(|c| &c.mdot_id),
        order(|c| &c.transport_id),
    );
    let mut out = Vec::new();
    for gi in &g {
        for si in &s {
            let base = format!("{SEED}|XE|{gi}|{si}");
            let p = |suffix: &str, v: &Vec<String>| v[a3::pick(&format!("{base}|{suffix}"), v.len())].clone();
            out.push(format!(
                "XE|{gi}|{si}|{}|{}|{}|{}",
                p("B_peak", &b),
                p("V_d", &vd),
                p("mdot", &m),
                p("transport", &t)
            ));
        }
    }
    out
}

fn v1_by_key(v1doc: &Value) -> AbepResult<BTreeMap<String, Value>> {
    let mut m = BTreeMap::new();
    for c in get(v1doc, "cases").and_then(Value::as_list).ok_or_else(|| schema(env::CASES_REL, "cases"))? {
        m.insert(get_str(c, "key", env::CASES_REL)?.to_string(), c.clone());
    }
    Ok(m)
}

fn header(kind: Kind, extra: Vec<(&str, Value)>, cases: Vec<Value>) -> Value {
    let mut v = vec![
        ("schema", sval(CASES_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("addendum", sval("A6 XE grid at study-converged numerics")),
        ("kind", sval(if kind == Kind::Study { "CONVERGENCE_STUDY" } else { "XE_GRID_PRODUCTION_LEVEL" })),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(LOCK_SHA256)),
        ("prereg_lock_sha256", sval(env::LOCK_SHA256)),
    ];
    v.extend(extra);
    v.push(("generated_by", sval("abep-h1-envelope-a6 generate (crates/abep-julia-bridge/src/envelope_a6.rs)")));
    v.push(("n_cases", Value::int(cases.len() as i64)));
    v.push(("cases", Value::List(cases)));
    dict(v)
}

/// The study case file: 22 cases (seeded + mandatory, checked against the addendum) x the 7 study levels.
pub fn build_study_doc(repo: &Path) -> AbepResult<Value> {
    let add = load_addendum(repo)?;
    let (v1doc, cs, _) = a3::v1_case_set_and_cells(repo)?;
    let cst = get(&add, "convergence_study").ok_or_else(|| schema(ADDENDUM_REL, "convergence_study"))?;
    let seeded = strings(get(cst, "seeded_keys"), ADDENDUM_REL)?;
    let mandatory = strings(get(cst, "mandatory_keys"), ADDENDUM_REL)?;
    if seeded_keys(&cs) != seeded {
        return Err(model("the seeded A6 check set differs from the keys registered in the addendum"));
    }
    let by = v1_by_key(&v1doc)?;
    let mut cases = Vec::new();
    for k in seeded.iter().chain(mandatory.iter()) {
        let base = by.get(k).ok_or_else(|| model(format!("study case {k} not in v1")))?;
        for lv in STUDY_LEVELS {
            cases.push(at_level(base, k, lv)?);
        }
    }
    Ok(header(Kind::Study, vec![("seed", sval(SEED)), ("v1_cases_sha256", sval(&cs.sha256))], cases))
}

/// The committed study result's production level (None: STOP).
pub fn production_level(repo: &Path) -> AbepResult<Option<u32>> {
    let v = loads(
        &std::fs::read(repo.join(STUDY_RESULT_REL))
            .map_err(|e| AbepError::IncompleteEvidence { message: format!("A6 study result not committed: {e}") })?,
        STUDY_RESULT_REL,
    )?;
    if get_str(&v, "schema", STUDY_RESULT_REL)? != STUDY_RESULT_SCHEMA
        || get_str(&v, "addendum_lock_sha256", STUDY_RESULT_REL)? != LOCK_SHA256
    {
        return Err(schema(STUDY_RESULT_REL, "not an A6 study result under the A6 lock"));
    }
    Ok(match get(&v, "production_level") {
        Some(Value::Int(i)) => Some(i.as_i64().ok_or_else(|| schema(STUDY_RESULT_REL, "production_level"))? as u32),
        _ => None,
    })
}

/// The XE grid case file at the committed production level (refused when the study says STOP).
pub fn build_grid_doc(repo: &Path) -> AbepResult<Value> {
    load_addendum(repo)?;
    let k = production_level(repo)?
        .ok_or_else(|| model("A6 study result is STOP: no production level, the A6 grid is not run"))?;
    let (v1doc, cs, _) = a3::v1_case_set_and_cells(repo)?;
    let by = v1_by_key(&v1doc)?;
    let lv = Level { k, long: false };
    let mut cases = Vec::new();
    for c in cs.cases.iter().filter(|c| c.family == Family::Xe) {
        cases.push(at_level(&by[&c.key], &c.key, lv)?);
    }
    let rs = abep_provenance::sha256_file(&repo.join(STUDY_RESULT_REL))?;
    Ok(header(
        Kind::Grid,
        vec![
            ("production_level", sval(&lv.id())),
            ("study_result_sha256", sval(&rs)),
            ("v1_cases_sha256", sval(&cs.sha256)),
        ],
        cases,
    ))
}

pub fn build_launch_manifest(repo: &Path, kind: Kind, cases_text: &str, n: usize) -> AbepResult<Value> {
    let sha = |rel: &str| abep_provenance::sha256_file(&repo.join(rel));
    Ok(dict(vec![
        ("schema", sval(LAUNCH_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(LOCK_SHA256)),
        ("prereg_lock_sha256", sval(env::LOCK_SHA256)),
        ("cases", sval(kind.cases_rel())),
        ("cases_sha256", sval(&sha256_hex(cases_text.as_bytes()))),
        ("driver", sval(DRIVER_REL)),
        ("driver_sha256", sval(&sha(DRIVER_REL)?)),
        ("bridge_lib", sval(BRIDGE_LIB_REL)),
        ("bridge_lib_sha256", sval(&sha(BRIDGE_LIB_REL)?)),
        ("n_cases", Value::int(n as i64)),
        ("n_shards", Value::int(kind.n_shards() as i64)),
        ("shard_rule", sval("case index i (0-based, file order) belongs to shard i mod n_shards")),
        ("thread_env", dict(THREAD_PIN.iter().map(|(k, v)| (*k, sval(v))).collect())),
        ("mode", sval("vacuum")),
    ]))
}

pub fn generate(repo: &Path, kind: Kind) -> AbepResult<(String, String)> {
    let doc = match kind {
        Kind::Study => build_study_doc(repo)?,
        Kind::Grid => build_grid_doc(repo)?,
    };
    ec::validate_cases(repo, &doc)?;
    let text = ec::render_case_doc(&doc)?;
    let n = get(&doc, "cases").and_then(Value::as_list).map_or(0, <[Value]>::len);
    let lm = build_launch_manifest(repo, kind, &text, n)?;
    let mut lm_text = pyjson::dumps(&lm, &DumpOptions::config_writer()).map_err(|e| model(e.to_string()))?;
    lm_text.push('\n');
    Ok((text, lm_text))
}

pub fn write_generated(repo: &Path, kind: Kind) -> AbepResult<()> {
    let (cases, lm) = generate(repo, kind)?;
    let lr = kind.launch_rel();
    for (rel, t) in [(kind.cases_rel(), &cases), (lr.as_str(), &lm)] {
        std::fs::write(repo.join(rel), t).map_err(|e| io(rel, e))?;
    }
    Ok(())
}

pub fn check(repo: &Path, kind: Kind) -> AbepResult<usize> {
    let (cases, lm) = generate(repo, kind)?;
    let lr = kind.launch_rel();
    for (rel, t) in [(kind.cases_rel(), &cases), (lr.as_str(), &lm)] {
        let have = std::fs::read(repo.join(rel)).map_err(|e| io(rel, e))?;
        if have != t.as_bytes() {
            return Err(model(format!("{rel} differs from its deterministic regeneration")));
        }
    }
    let doc = loads(cases.as_bytes(), kind.cases_rel())?;
    Ok(get(&doc, "cases").and_then(Value::as_list).map_or(0, <[Value]>::len))
}

fn launch_manifest(repo: &Path, kind: Kind) -> AbepResult<Value> {
    let lr = kind.launch_rel();
    loads(&std::fs::read(repo.join(&lr)).map_err(|e| io(&lr, e))?, &lr)
}

pub fn shard_job(
    repo: &Path,
    kind: Kind,
    shard: usize,
    out_dir: &str,
    lookup: &dyn Fn(&str) -> Option<String>,
) -> AbepResult<JobSpec> {
    if shard >= kind.n_shards() {
        return Err(model(format!("shard {shard} outside 0..{}", kind.n_shards())));
    }
    let lm = launch_manifest(repo, kind)?;
    let lr = kind.launch_rel();
    let s = |k: &str| -> AbepResult<String> { Ok(get_str(&lm, k, &lr)?.to_string()) };
    let out = format!("{out_dir}/a6_s{shard:02}.jsonl");
    let threads = ThreadSettings::pinned(THREAD_PIN);
    let mut inputs = vec![
        (DRIVER_REL.to_string(), s("driver_sha256")?),
        (kind.cases_rel().to_string(), s("cases_sha256")?),
        (LOCK_REL.to_string(), LOCK_SHA256.to_string()),
        (ADDENDUM_REL.to_string(), ADDENDUM_SHA256.to_string()),
        (env::LOCK_REL.to_string(), env::LOCK_SHA256.to_string()),
        (env::PREREG_REL.to_string(), env::PREREG_SHA256.to_string()),
        (BRIDGE_LIB_REL.to_string(), s("bridge_lib_sha256")?),
    ];
    let prereg = ec::load_prereg(repo)?;
    if let Some(Value::Dict(p)) = ec::pointer(&prereg, "/pinned_inputs") {
        for (f, h) in p.iter() {
            if f != BRIDGE_LIB_REL {
                inputs.push((f.clone(), h.as_str().ok_or_else(|| schema(env::PREREG_REL, f.clone()))?.to_string()));
            }
        }
    }
    Ok(JobSpec {
        program: "julia".into(),
        args: vec![
            "--project=hallthruster_bridge".into(),
            DRIVER_REL.into(),
            kind.launch_name().into(),
            out.clone(),
            shard.to_string(),
            kind.n_shards().to_string(),
        ],
        cwd: repo.to_string_lossy().to_string(),
        env: child_env(lookup, &threads, &[]),
        threads,
        inputs,
        outputs: vec![out],
    })
}

pub fn run_shard(repo: &Path, kind: Kind, shard: usize, out_dir: &str) -> AbepResult<crate::sidecar::JuliaRunSidecar> {
    let lookup = |k: &str| std::env::var(k).ok();
    let job = shard_job(repo, kind, shard, out_dir, &lookup)?;
    crate::launch::launch(&repo.to_string_lossy(), &job, CONTRACT_ID)
}

/// Freeze A6 shard outputs (the raw manifest pins the A6 lock, the case file and the driver of `kind`).
pub fn freeze(
    repo: &Path,
    kind: Kind,
    name: &str,
    shards: &[PathBuf],
    out_dir: &Path,
) -> AbepResult<(PathBuf, String)> {
    let lm = launch_manifest(repo, kind)?;
    let lr = kind.launch_rel();
    let header = vec![
        ("schema", sval(RAW_SCHEMA)),
        ("kind", sval(if kind == Kind::Study { "CONVERGENCE_STUDY" } else { "XE_GRID_PRODUCTION_LEVEL" })),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_lock_sha256", sval(LOCK_SHA256)),
        ("prereg_lock_sha256", sval(env::LOCK_SHA256)),
        ("cases_file_sha256", sval(get_str(&lm, "cases_sha256", &lr)?)),
        ("driver_sha256", sval(get_str(&lm, "driver_sha256", &lr)?)),
    ];
    crate::air_cases::freeze_records(name, shards, out_dir, header, "abep-h1-envelope-a6 freeze")
}

/// Read and verify a frozen A6 raw file of `kind`; returns (records by key, raw sha256).
pub fn read_frozen(
    repo: &Path,
    kind: Kind,
    manifest: &Path,
    manifest_sha256: &str,
) -> AbepResult<(BTreeMap<String, Value>, String)> {
    let label = manifest.to_string_lossy().to_string();
    let m = loads(&read_verified(manifest, manifest_sha256)?, &label)?;
    if get_str(&m, "schema", &label)? != RAW_SCHEMA || get_str(&m, "addendum_lock_sha256", &label)? != LOCK_SHA256 {
        return Err(schema(&label, "not an A6 raw manifest under the A6 lock"));
    }
    let lm = launch_manifest(repo, kind)?;
    let cases_sha = get_str(&lm, "cases_sha256", &kind.launch_rel())?.to_string();
    if get_str(&m, "cases_file_sha256", &label)? != cases_sha {
        return Err(schema(&label, "produced from another A6 case file"));
    }
    let raw_name = get_str(&m, "raw_file", &label)?;
    let raw_sha = get_str(&m, "raw_sha256", &label)?.to_string();
    let gz = read_verified(&manifest.parent().unwrap_or(Path::new(".")).join(raw_name), &raw_sha)?;
    let mut text = String::new();
    flate2::read::GzDecoder::new(gz.as_slice())
        .read_to_string(&mut text)
        .map_err(|e| schema(raw_name, e.to_string()))?;
    let cr = kind.cases_rel();
    let doc = loads(&read_verified(&repo.join(cr), &cases_sha)?, cr)?;
    let mut want: BTreeMap<String, String> = BTreeMap::new();
    for c in get(&doc, "cases").and_then(Value::as_list).ok_or_else(|| schema(cr, "cases"))? {
        let h = case_hash(c)?;
        if get_str(c, "case_sha256", cr)? != h {
            return Err(schema(cr, "case_sha256 mismatch"));
        }
        want.insert(get_str(c, "key", cr)?.to_string(), h);
    }
    let commit = abep_hall::hall_map::pinned_commit(&repo.to_string_lossy(), None).map_err(AbepError::from)?;
    let mut recs = BTreeMap::new();
    for line in text.lines().filter(|l| !l.trim().is_empty()) {
        let r = pyjson::loads(line).map_err(|e| schema(raw_name, e.to_string()))?;
        let key = get_str(&r, "key", raw_name)?.to_string();
        let h = want.get(&key).ok_or_else(|| model(format!("unexpected A6 record {key}")))?;
        for (f, w) in [
            ("case_sha256", h.as_str()),
            ("hallthruster_commit", commit.as_str()),
            ("addendum_lock_sha256", LOCK_SHA256),
            ("prereg_lock_sha256", env::LOCK_SHA256),
            ("cases_file_sha256", cases_sha.as_str()),
        ] {
            if get(&r, f).and_then(Value::as_str) != Some(w) {
                return Err(model(format!("A6 record {key}: {f} != {w}")));
            }
        }
        if recs.insert(key.clone(), r).is_some() {
            return Err(model(format!("duplicate A6 record {key}")));
        }
    }
    if finite(get(&m, "n_records")) != Some(recs.len() as f64) {
        return Err(schema(&label, "n_records != records"));
    }
    Ok((recs, raw_sha))
}

fn xe_status(r: &Value) -> RunStatus {
    env::run_status(Family::Xe, r)
}

/// Observed order and Richardson estimate of one observable over three successive levels (report only).
pub fn observed_order(f0: f64, f1: f64, f2: f64) -> (Option<f64>, Option<f64>, &'static str) {
    let (d1, d2) = ((f1 - f0).abs(), (f2 - f1).abs());
    if d1 == 0.0 || d2 == 0.0 {
        return (None, None, "zero difference");
    }
    let p = (d1 / d2).log2();
    if !(p.is_finite() && p > 0.0) {
        return (Some(p), None, "order not positive");
    }
    (Some(p), Some(f2 + (f2 - f1) / (2f64.powf(p) - 1.0)), "")
}

/// Score the frozen study once: (result JSON, page). Production level = coarsest k in {0,1,2} with Pass(k).
pub fn score_study(
    repo: &Path,
    manifest: &Path,
    manifest_sha256: &str,
    rust_commit: &str,
) -> AbepResult<(Value, String)> {
    let add = load_addendum(repo)?;
    let (recs, raw_sha) = read_frozen(repo, Kind::Study, manifest, manifest_sha256)?;
    let cst = get(&add, "convergence_study").ok_or_else(|| schema(ADDENDUM_REL, "convergence_study"))?;
    let mut keys = strings(get(cst, "seeded_keys"), ADDENDUM_REL)?;
    keys.extend(strings(get(cst, "mandatory_keys"), ADDENDUM_REL)?);
    let rec = |k: &str, lv: Level| recs.get(&format!("{k}|{}", lv.id()));
    let lvl = |k: u32, long: bool| Level { k, long };
    let mut rows = Vec::new();
    let mut pass = [true; 3];
    let mut worst: [(Delta, Delta); 3] = Default::default();
    let mut md = String::new();
    for k in 0..3u32 {
        for (kind, finer) in [("G", lvl(k + 1, false)), ("D", lvl(k, true))] {
            let coarse = lvl(k, false);
            let mut n_fail = 0;
            for key in &keys {
                let c = a3::compare_with(xe_status, key, &finer.id(), rec(key, coarse), rec(key, finer));
                if !c.passes() {
                    pass[k as usize] = false;
                    n_fail += 1;
                }
                let upd = |w: &mut Delta, x: Option<f64>| {
                    if let Some(x) = x {
                        if w.as_ref().is_none_or(|(v, _)| x > *v) {
                            *w = Some((x, format!("{key}|{}->{}", coarse.id(), finer.id())));
                        }
                    }
                };
                upd(&mut worst[k as usize].0, c.rel_thrust);
                upd(&mut worst[k as usize].1, c.rel_id);
                rows.push(dict(vec![
                    ("comparison", sval(&format!("{kind}({k})"))),
                    ("v1_key", sval(key)),
                    ("coarse", sval(&coarse.id())),
                    ("fine", sval(&finer.id())),
                    ("status_coarse", sval(c.status_r0.as_str())),
                    ("status_fine", sval(c.status_rk.as_str())),
                    ("rel_thrust", c.rel_thrust.map_or(Value::Null, fval)),
                    ("rel_discharge_current", c.rel_id.map_or(Value::Null, fval)),
                    ("C-STATUS", Value::Bool(c.c_status)),
                    ("C-QUIET", c.c_quiet.map_or(Value::Null, Value::Bool)),
                    ("C-T", c.c_t.map_or(Value::Null, Value::Bool)),
                    ("C-ID", c.c_id.map_or(Value::Null, Value::Bool)),
                    ("passes", Value::Bool(c.passes())),
                ]));
            }
            md.push_str(&format!(
                "| {kind}({k}) | {} vs {} | {n_fail} of {} fail |\n",
                coarse.id(),
                finer.id(),
                keys.len()
            ));
        }
    }
    let production = (0..3u32).find(|k| pass[*k as usize]);
    // observed-order diagnostic (report only)
    let mut diag = Vec::new();
    for key in &keys {
        for obs in ["thrust_N", "discharge_current_A"] {
            for start in [0u32, 1] {
                let v: Vec<Option<f64>> = (start..start + 3)
                    .map(|k| {
                        rec(key, lvl(k, false))
                            .filter(|r| xe_status(r) == RunStatus::Pass)
                            .and_then(|r| finite(get(r, obs)))
                    })
                    .collect();
                let (p, rich, why) = match (v[0], v[1], v[2]) {
                    (Some(a), Some(b), Some(c)) => observed_order(a, b, c),
                    _ => (None, None, "a level is not PASS"),
                };
                diag.push(dict(vec![
                    ("v1_key", sval(key)),
                    ("observable", sval(obs)),
                    ("levels", sval(&format!("L{start}-L{}", start + 2))),
                    ("observed_order", p.map_or(Value::Null, fval)),
                    ("richardson_estimate", rich.map_or(Value::Null, fval)),
                    ("finest_value", v[2].map_or(Value::Null, fval)),
                    ("note", if why.is_empty() { Value::Null } else { sval(why) }),
                ]));
            }
        }
    }
    let agg = |d: &Delta| match d {
        Some((x, k)) => dict(vec![("value", fval(*x)), ("at", sval(k))]),
        None => Value::Null,
    };
    let per_level: Vec<Value> = (0..3)
        .map(|k| {
            dict(vec![
                ("level", sval(&lvl(k, false).id())),
                ("passes", Value::Bool(pass[k as usize])),
                ("max_rel_thrust", agg(&worst[k as usize].0)),
                ("max_rel_discharge_current", agg(&worst[k as usize].1)),
            ])
        })
        .collect();
    let outcome = match production {
        Some(k) => format!("PRODUCTION_LEVEL_A6-L{k}"),
        None => "STOP_NO_LEVEL_CONVERGED".into(),
    };
    let result = dict(vec![
        ("schema", sval(STUDY_RESULT_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("addendum", sval("A6 convergence study")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(LOCK_SHA256)),
        ("raw_manifest_sha256", sval(manifest_sha256)),
        ("raw_sha256", sval(&raw_sha)),
        ("rust_commit", sval(rust_commit)),
        ("scored_once", Value::Bool(true)),
        ("tolerance_rel", fval(a3::TOL_REL)),
        ("n_check_cases", Value::int(keys.len() as i64)),
        ("levels", Value::List(per_level)),
        ("production_level", production.map_or(Value::Null, |k| Value::int(k as i64))),
        ("outcome", sval(&outcome)),
        ("comparisons", Value::List(rows)),
        ("observed_order_diagnostic", Value::List(diag)),
    ]);
    let mut page = String::from("# NP-HALL-PARAMETRIC-ENVELOPE addendum A6: convergence study result (XE)\n\n");
    page.push_str(&format!(
        "`a6_convergence_study_result_v1.json` is authoritative. PARAMETRIC / NOT_VALIDATED. Scored once from the frozen \
         study (manifest sha256 `{manifest_sha256}`, raw `{raw_sha}`).\n\n**Outcome: {outcome}.**\n\n| comparison | levels | failures |\n|---|---|---|\n"
    ));
    page.push_str(&md);
    page.push_str("\nPass(k) needs every case to pass G(k) and D(k) (status, quiet class, thrust and I_d within 2 %). Production level = coarsest passing k in {0, 1, 2}; none: STOP.\n");
    Ok((result, page))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn observed_order_of_a_second_order_sequence() {
        let (p, r, _) = observed_order(1.0 + 1.0, 1.0 + 0.25, 1.0 + 0.0625);
        assert!((p.unwrap() - 2.0).abs() < 1e-12);
        assert!((r.unwrap() - 1.0).abs() < 1e-12);
        assert_eq!(observed_order(1.0, 1.0, 2.0).0, None);
    }

    #[test]
    fn level_ids() {
        assert_eq!(Level { k: 2, long: true }.id(), "A6-L2D");
        assert_eq!(STUDY_LEVELS.len(), 7);
    }
}
