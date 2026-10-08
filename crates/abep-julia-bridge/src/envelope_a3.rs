//! NP-HALL-PARAMETRIC-ENVELOPE addendum A3 (numerics adequacy, RG-04;
//! `docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a3_numerics_v1.json`, locked by
//! `prereg_addendum_a3_numerics_lock_v1.json`): the seeded check set, the refined case file (R0 = v1 numerics,
//! R1 = 2 x cells, R3 = 2 x duration), the shard job, the freeze and the one scoring pass.
//!
//! PARAMETRIC / NOT_VALIDATED. The check never changes a v1 grid case, its numerics or a frozen record; its outcome is an
//! overlay label on the family's points (consequence registered in the addendum).

use crate::envelope_cases::{self as ec, BRIDGE_LIB_REL, THREAD_PIN};
use crate::jobs::{child_env, JobSpec, ThreadSettings};
use abep_hall::envelope::{self as env, case_hash, Family, RunStatus};
use abep_provenance::{read_verified, sha256_hex};
use abep_types::pyjson::{self, Dict, DumpOptions, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::{BTreeMap, BTreeSet};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

pub const ADDENDUM_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a3_numerics_v1.json";
pub const ADDENDUM_SHA256: &str = "ca1b895efbf5c469fb0fe26951acf695bf4b39685e7cac65fcc708d0a8a7b20f";
pub const A3_LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a3_numerics_lock_v1.json";
pub const A3_LOCK_SHA256: &str = "b840f1b080c94be58472ccb07f6cf35cc9ad8822161ff9a1440ecb55c76e04bd";
pub const A3_CASES_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a3_numerics_cases_v1.json";
pub const A3_LAUNCH_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_a3_numerics_v1.json";
pub const A3_DRIVER_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_a3_driver.jl";
pub const A3_CASES_SCHEMA: &str = "np_hall_parametric_envelope_a3_numerics_cases_v1";
pub const A3_LAUNCH_SCHEMA: &str = "np_hall_parametric_envelope_a3_numerics_launch_manifest_v1";
pub const A3_RAW_SCHEMA: &str = "np_hall_parametric_envelope_a3_numerics_raw_manifest_v1";
pub const A3_RESULT_SCHEMA: &str = "np_hall_parametric_envelope_a3_numerics_result_v1";
pub const A3_CONTRACT_ID: &str = "NP-HALL-PARAMETRIC-ENVELOPE-A3-NUMERICS-V1";
/// Seed of the check-set selection (addendum check_set.seed).
pub const SEED: &str = "NP-HALL-PARAMETRIC-ENVELOPE/A3/v1";
pub const A3_SHARDS: usize = 3;
/// C-T / C-ID relative tolerance and the margin cap (addendum criteria / outcome).
pub const TOL_REL: f64 = 0.02;
pub const MARGIN_CAP: f64 = 0.10;
/// Quiet class: Id_rms_rel below this (bridge internal diagnostic).
pub const QUIET_RMS: f64 = 0.5;
pub const R0: &str = "A3-R0";
pub const R1: &str = "A3-R1";
pub const R3: &str = "A3-R3";
pub const REFINEMENTS: [&str; 3] = [R0, R1, R3];

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

fn loads(bytes: &[u8], label: &str) -> AbepResult<Value> {
    let text = std::str::from_utf8(bytes).map_err(|e| schema(label, e.to_string()))?;
    pyjson::loads(text).map_err(|e| schema(label, e.to_string()))
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

/// `pick(text, n)`: the first 8 bytes of sha256(text) as a big-endian u64, mod n (addendum check_set.selection_rule).
pub fn pick(text: &str, n: usize) -> usize {
    let h = sha256_hex(text.as_bytes());
    let u = u64::from_str_radix(&h[..16], 16).expect("hex digest");
    (u % n as u64) as usize
}

/// The verified addendum (A3 lock and every file it locks).
pub fn load_addendum(repo: &Path) -> AbepResult<Value> {
    let lock = loads(&read_verified(&repo.join(A3_LOCK_REL), A3_LOCK_SHA256)?, A3_LOCK_REL)?;
    let files = get(&lock, "files").and_then(Value::as_dict).ok_or_else(|| schema(A3_LOCK_REL, "files"))?;
    for (f, h) in files.iter() {
        let h = h.as_str().ok_or_else(|| schema(A3_LOCK_REL, f.clone()))?;
        read_verified(&repo.join(env::NP_DIR).join(f), h)?;
    }
    loads(&read_verified(&repo.join(ADDENDUM_REL), ADDENDUM_SHA256)?, ADDENDUM_REL)
}

/// The frozen v1 case-file document (sha256 pinned by the v1 launch manifest).
fn v1_case_doc(repo: &Path) -> AbepResult<(Value, String)> {
    let lm = loads(
        &std::fs::read(repo.join(env::LAUNCH_MANIFEST_REL)).map_err(|e| io(env::LAUNCH_MANIFEST_REL, e))?,
        env::LAUNCH_MANIFEST_REL,
    )?;
    let sha = get_str(&lm, "cases_sha256", env::LAUNCH_MANIFEST_REL)?.to_string();
    let doc = loads(&read_verified(&repo.join(env::CASES_REL), &sha)?, env::CASES_REL)?;
    Ok((doc, sha))
}

/// What differs between the A3 check of the XE family and of the AIR family (addendum A3 scope).
pub struct Spec {
    pub family: &'static str,
    pub cases_rel: &'static str,
    pub launch_rel: &'static str,
    pub driver_rel: &'static str,
    pub raw_schema: &'static str,
    pub shard_prefix: &'static str,
    pub frozen_by: &'static str,
    /// The family's registered run-status rule.
    pub status: fn(&Value) -> RunStatus,
}

fn xe_status(r: &Value) -> RunStatus {
    env::run_status(Family::Xe, r)
}

pub const XE: Spec = Spec {
    family: "XE",
    cases_rel: A3_CASES_REL,
    launch_rel: A3_LAUNCH_REL,
    driver_rel: A3_DRIVER_REL,
    raw_schema: A3_RAW_SCHEMA,
    shard_prefix: "a3_s",
    frozen_by: "abep-h1-envelope-a3 freeze",
    status: xe_status,
};

/// One selected check case.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CheckCase {
    pub role: &'static str,
    pub key: String,
}

/// Axis ids of a family in file order of first appearance.
fn axis_order(cases: &[&env::CaseInfo], f: fn(&env::CaseInfo) -> &str) -> Vec<String> {
    let mut seen = Vec::<String>::new();
    for c in cases {
        if !seen.iter().any(|s| s == f(c)) {
            seen.push(f(c).to_string());
        }
    }
    seen
}

/// The check set of `family` by the addendum's selection rule, computed from the frozen v1 case set.
pub fn select_check_set(
    cs: &env::CaseSet,
    family: Family,
    cells: &BTreeMap<String, i64>,
) -> AbepResult<Vec<CheckCase>> {
    select_check_set_as(cs, family, family.as_str(), None, cells)
}

/// The selection rule on the axes of the v1 family `family`, with `fam` in the seed texts and keys; `compositions`
/// (AIR scope) adds the composition corner picked by the seed before the transport id in the key.
pub fn select_check_set_as(
    cs: &env::CaseSet,
    family: Family,
    fam: &str,
    compositions: Option<&[String]>,
    cells: &BTreeMap<String, i64>,
) -> AbepResult<Vec<CheckCase>> {
    let cases: Vec<&env::CaseInfo> = cs.cases.iter().filter(|c| c.family == family).collect();
    if cases.is_empty() {
        return Err(model(format!("no v1 case of family {fam}")));
    }
    let geoms = axis_order(&cases, |c| &c.geometry_id);
    let bz = axis_order(&cases, |c| &c.bz_shape_id);
    let bp = axis_order(&cases, |c| &c.b_peak_id);
    let vd = axis_order(&cases, |c| &c.vd_id);
    let mf = axis_order(&cases, |c| &c.mdot_id);
    let tr = axis_order(&cases, |c| &c.transport_id);
    if geoms.len() % 2 == 0 || bp.len() != 2 || vd.len() % 2 == 0 || mf.len() % 2 == 0 {
        return Err(model("axis lengths do not define the A3 corners and centre"));
    }
    // geometry by v1 cell count (min over shapes), ties by file order
    let mut by_cells: Vec<(i64, usize, String)> = Vec::new();
    for (i, g) in geoms.iter().enumerate() {
        let n = *cells.get(g).ok_or_else(|| model(format!("no cell count for {g}")))?;
        by_cells.push((n, i, g.clone()));
    }
    by_cells.sort();
    let gmin = by_cells[0].2.clone();
    let gmax = by_cells[by_cells.len() - 1].2.clone();
    let gmid = by_cells[by_cells.len() / 2].2.clone();
    let last = |v: &Vec<String>| v[v.len() - 1].clone();
    let mut sel: Vec<(&'static str, String, String, String, String)> = Vec::new();
    for g in [&gmin, &gmax] {
        for b in [&bp[0], &bp[1]] {
            for v in [vd[0].clone(), last(&vd)] {
                for m in [mf[0].clone(), last(&mf)] {
                    sel.push(("CORNER", g.clone(), b.clone(), v.clone(), m));
                }
            }
        }
    }
    let (v, m) = (vd[vd.len() / 2].clone(), mf[mf.len() / 2].clone());
    let b = bp[pick(&format!("{SEED}|{fam}|{gmid}|{v}|{m}|B_peak"), 2)].clone();
    sel.push(("CENTRE", gmid, b, v, m));
    Ok(sel
        .into_iter()
        .map(|(role, g, b, v, m)| {
            let base = format!("{SEED}|{fam}|{g}|{b}|{v}|{m}");
            let s = &bz[pick(&format!("{base}|bz_shape"), bz.len())];
            let t = &tr[pick(&format!("{base}|transport"), tr.len())];
            let key = match compositions {
                Some(cp) => {
                    format!("{fam}|{g}|{s}|{b}|{v}|{m}|{}|{t}", cp[pick(&format!("{base}|composition"), cp.len())])
                }
                None => format!("{fam}|{g}|{s}|{b}|{v}|{m}|{t}"),
            };
            CheckCase { role, key }
        })
        .collect())
}

/// The R0 / R1 / R3 cases of one check case (`base` is its frozen case object from `label`): only cells (R1) or
/// duration and averaging start (R3) change; identity fields are added and the case hash is recomputed.
pub fn refine(base: &Value, c: &CheckCase, label: &str) -> AbepResult<Vec<Value>> {
    let Value::Dict(d) = base else { return Err(model("case is not an object")) };
    let base_sha = get_str(base, "case_sha256", label)?.to_string();
    let cells = get(base, "cells").and_then(|v| if let Value::Int(i) = v { i.as_i64() } else { None });
    let cells = cells.ok_or_else(|| schema(label, "cells"))?;
    let dur = finite(get(base, "duration_s")).ok_or_else(|| schema(label, "duration_s"))?;
    let mut out = Vec::new();
    for r in REFINEMENTS {
        let mut n = d.clone();
        n.remove("case_sha256");
        let key = format!("{}|{r}", c.key);
        n.insert("key", sval(&key));
        n.insert("id", sval(&key));
        match r {
            R1 => n.insert("cells", Value::int(2 * cells)),
            R3 => {
                n.insert("duration_s", fval(2.0 * dur));
                n.insert("average_start_s", fval(dur));
            }
            _ => {}
        }
        n.insert("a3_refinement", sval(r));
        n.insert("a3_role", sval(c.role));
        n.insert("v1_key", sval(&c.key));
        n.insert("v1_case_sha256", sval(&base_sha));
        let h = case_hash(&Value::Dict(n.clone()))?;
        n.insert("case_sha256", sval(&h));
        out.push(Value::Dict(n));
    }
    Ok(out)
}

/// The frozen v1 case set and the v1 cell count per geometry (minimum over shapes).
pub fn v1_case_set_and_cells(repo: &Path) -> AbepResult<(Value, env::CaseSet, BTreeMap<String, i64>)> {
    let (v1doc, v1sha) = v1_case_doc(repo)?;
    let cs = env::parse_case_set(&v1doc, &v1sha)?;
    let mut cells = BTreeMap::new();
    for c in get(&v1doc, "cases").and_then(Value::as_list).ok_or_else(|| schema(env::CASES_REL, "cases"))? {
        let n = get(c, "cells").and_then(|v| if let Value::Int(i) = v { i.as_i64() } else { None });
        let n = n.ok_or_else(|| schema(env::CASES_REL, "cells"))?;
        let e = cells.entry(get_str(c, "geometry_id", env::CASES_REL)?.to_string()).or_insert(n);
        *e = (*e).min(n);
    }
    Ok((v1doc, cs, cells))
}

/// Build the A3 case-file document: every check case at R0 / R1 / R3, the selection checked against the addendum.
pub fn build_case_doc(repo: &Path) -> AbepResult<Value> {
    let add = load_addendum(repo)?;
    ec::load_prereg(repo)?;
    let (v1doc, v1sha) = v1_case_doc(repo)?;
    let cs = env::parse_case_set(&v1doc, &v1sha)?;
    let raw: Vec<&Value> =
        get(&v1doc, "cases").and_then(Value::as_list).ok_or_else(|| schema(env::CASES_REL, "cases"))?.iter().collect();
    let mut cells = BTreeMap::new();
    let mut by_key: BTreeMap<&str, &Value> = BTreeMap::new();
    for c in &raw {
        let k = get_str(c, "key", env::CASES_REL)?;
        let n = get(c, "cells").and_then(|v| if let Value::Int(i) = v { i.as_i64() } else { None });
        let n = n.ok_or_else(|| schema(env::CASES_REL, format!("{k}: cells")))?;
        let g = get_str(c, "geometry_id", env::CASES_REL)?.to_string();
        let e = cells.entry(g).or_insert(n);
        *e = (*e).min(n);
        by_key.insert(k, c);
    }
    let sel = select_check_set(&cs, Family::Xe, &cells)?;
    let registered: Vec<String> = get(&add, "check_set")
        .and_then(|c| get(c, "xe_keys"))
        .and_then(Value::as_list)
        .ok_or_else(|| schema(ADDENDUM_REL, "check_set.xe_keys"))?
        .iter()
        .map(|v| v.as_str().map(str::to_string).ok_or_else(|| schema(ADDENDUM_REL, "xe_keys")))
        .collect::<AbepResult<_>>()?;
    let got: Vec<String> = sel.iter().map(|c| c.key.clone()).collect();
    if got != registered {
        return Err(model("the seeded check set differs from the keys registered in the addendum"));
    }
    let mut out = Vec::new();
    for c in &sel {
        let v1 = by_key.get(c.key.as_str()).ok_or_else(|| model(format!("check case {} not in v1", c.key)))?;
        out.extend(refine(v1, c, env::CASES_REL)?);
    }
    Ok(dict(vec![
        ("schema", sval(A3_CASES_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("addendum", sval("A3 numerics adequacy (RG-04)")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(A3_LOCK_SHA256)),
        ("prereg_lock_sha256", sval(env::LOCK_SHA256)),
        ("v1_cases_sha256", sval(&v1sha)),
        ("seed", sval(SEED)),
        ("refinements", Value::List(REFINEMENTS.iter().map(|r| sval(r)).collect())),
        ("generated_by", sval("abep-h1-envelope-a3 generate (crates/abep-julia-bridge/src/envelope_a3.rs)")),
        ("n_cases", Value::int(out.len() as i64)),
        ("cases", Value::List(out)),
    ]))
}

/// The A3 launch manifest of a rendered A3 case file.
pub fn build_launch_manifest(repo: &Path, cases_text: &str, n: usize) -> AbepResult<Value> {
    let driver_sha = abep_provenance::sha256_file(&repo.join(A3_DRIVER_REL))?;
    let lib_sha = abep_provenance::sha256_file(&repo.join(BRIDGE_LIB_REL))?;
    Ok(dict(vec![
        ("schema", sval(A3_LAUNCH_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(A3_LOCK_SHA256)),
        ("prereg_lock_sha256", sval(env::LOCK_SHA256)),
        ("cases", sval(A3_CASES_REL)),
        ("cases_sha256", sval(&sha256_hex(cases_text.as_bytes()))),
        ("driver", sval(A3_DRIVER_REL)),
        ("driver_sha256", sval(&driver_sha)),
        ("bridge_lib", sval(BRIDGE_LIB_REL)),
        ("bridge_lib_sha256", sval(&lib_sha)),
        ("n_cases", Value::int(n as i64)),
        ("n_shards", Value::int(A3_SHARDS as i64)),
        ("shard_rule", sval("case index i (0-based, file order) belongs to shard i mod n_shards")),
        ("thread_env", dict(THREAD_PIN.iter().map(|(k, v)| (*k, sval(v))).collect())),
        ("run_shard", sval("abep-h1-envelope-a3 run-shard --shard <i> --out <dir> (Rust launch: pin check, input hashes, julia --version, nine-field sidecar)")),
        ("freeze", sval("abep-h1-envelope-a3 freeze --name <name> --out <dir> <shard .jsonl files>")),
        ("score", sval("abep-h1-envelope-a3 score --manifest <raw manifest> --manifest-sha256 <hex> --rust-commit <sha> --out <dir>")),
        ("mode", sval("vacuum")),
    ]))
}

/// (case text, launch-manifest text) as `generate` writes them.
pub fn generate(repo: &Path) -> AbepResult<(String, String)> {
    let doc = build_case_doc(repo)?;
    ec::validate_cases(repo, &doc)?;
    let text = ec::render_case_doc(&doc)?;
    let n = get(&doc, "cases").and_then(Value::as_list).map_or(0, <[Value]>::len);
    let lm = build_launch_manifest(repo, &text, n)?;
    let mut lm_text = pyjson::dumps(&lm, &DumpOptions::config_writer()).map_err(|e| model(e.to_string()))?;
    lm_text.push('\n');
    Ok((text, lm_text))
}

pub fn write_generated(repo: &Path) -> AbepResult<()> {
    let (cases, lm) = generate(repo)?;
    for (rel, t) in [(A3_CASES_REL, &cases), (A3_LAUNCH_REL, &lm)] {
        std::fs::write(repo.join(rel), t).map_err(|e| io(rel, e))?;
    }
    Ok(())
}

/// Regenerate in memory and require byte equality with the committed A3 case file and launch manifest.
pub fn check(repo: &Path) -> AbepResult<usize> {
    let (cases, lm) = generate(repo)?;
    for (rel, t) in [(A3_CASES_REL, &cases), (A3_LAUNCH_REL, &lm)] {
        let have = std::fs::read(repo.join(rel)).map_err(|e| io(rel, e))?;
        if have != t.as_bytes() {
            return Err(model(format!("{rel} differs from its deterministic regeneration")));
        }
    }
    let doc = loads(cases.as_bytes(), A3_CASES_REL)?;
    Ok(get(&doc, "cases").and_then(Value::as_list).map_or(0, <[Value]>::len))
}

fn launch_manifest(repo: &Path) -> AbepResult<Value> {
    launch_manifest_of(repo, &XE)
}

fn launch_manifest_of(repo: &Path, spec: &Spec) -> AbepResult<Value> {
    loads(&std::fs::read(repo.join(spec.launch_rel)).map_err(|e| io(spec.launch_rel, e))?, spec.launch_rel)
}

/// The A3 shard job with every input hash the driver relies on.
pub fn shard_job(
    repo: &Path,
    shard: usize,
    out_dir: &str,
    lookup: &dyn Fn(&str) -> Option<String>,
) -> AbepResult<JobSpec> {
    if shard >= A3_SHARDS {
        return Err(model(format!("shard {shard} outside 0..{A3_SHARDS}")));
    }
    let lm = launch_manifest(repo)?;
    let s = |k: &str| -> AbepResult<String> { Ok(get_str(&lm, k, A3_LAUNCH_REL)?.to_string()) };
    let out = format!("{out_dir}/a3_s{shard:02}.jsonl");
    let threads = ThreadSettings::pinned(THREAD_PIN);
    let mut inputs = vec![
        (A3_DRIVER_REL.to_string(), s("driver_sha256")?),
        (A3_CASES_REL.to_string(), s("cases_sha256")?),
        (A3_LOCK_REL.to_string(), A3_LOCK_SHA256.to_string()),
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
            A3_DRIVER_REL.into(),
            out.clone(),
            shard.to_string(),
            A3_SHARDS.to_string(),
        ],
        cwd: repo.to_string_lossy().to_string(),
        env: child_env(lookup, &threads, &[]),
        threads,
        inputs,
        outputs: vec![out],
    })
}

/// Launch one A3 shard (pin, inputs, Julia version, sidecar).
pub fn run_shard(repo: &Path, shard: usize, out_dir: &str) -> AbepResult<crate::sidecar::JuliaRunSidecar> {
    let lookup = |k: &str| std::env::var(k).ok();
    let job = shard_job(repo, shard, out_dir, &lookup)?;
    crate::launch::launch(&repo.to_string_lossy(), &job, A3_CONTRACT_ID)
}

/// Freeze A3 shard outputs: records sorted by key (unique), one gzip JSONL (mtime 0) and its manifest.
pub fn freeze(repo: &Path, name: &str, shards: &[PathBuf], out_dir: &Path) -> AbepResult<(PathBuf, String)> {
    freeze_with(repo, &XE, name, shards, out_dir)
}

/// [`freeze`] for the family `spec`.
pub fn freeze_with(
    repo: &Path,
    spec: &Spec,
    name: &str,
    shards: &[PathBuf],
    out_dir: &Path,
) -> AbepResult<(PathBuf, String)> {
    let lm = launch_manifest_of(repo, spec)?;
    let mut by_key: BTreeMap<String, String> = BTreeMap::new();
    let mut rows = Vec::new();
    for p in shards {
        let label = p.to_string_lossy().to_string();
        let bytes = std::fs::read(p).map_err(|e| io(&label, e))?;
        let txt = String::from_utf8(bytes.clone()).map_err(|e| schema(&label, e.to_string()))?;
        let mut n = 0usize;
        for line in txt.lines().filter(|l| !l.trim().is_empty()) {
            let v = pyjson::loads(line).map_err(|e| schema(&label, e.to_string()))?;
            let key = get_str(&v, "key", &label)?.to_string();
            if by_key.insert(key.clone(), line.trim().to_string()).is_some() {
                return Err(model(format!("duplicate record {key} across shards")));
            }
            n += 1;
        }
        let side = PathBuf::from(crate::sidecar::JuliaRunSidecar::path_for(&label));
        let fname = |q: &Path| q.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default();
        rows.push(dict(vec![
            ("file", sval(&fname(p))),
            ("sha256", sval(&sha256_hex(&bytes))),
            ("n_records", Value::int(n as i64)),
            ("sidecar", if side.is_file() { sval(&fname(&side)) } else { Value::Null }),
            ("sidecar_sha256", if side.is_file() { sval(&abep_provenance::sha256_file(&side)?) } else { Value::Null }),
        ]));
    }
    let mut body = String::new();
    for line in by_key.values() {
        body.push_str(line);
        body.push('\n');
    }
    let mut gz = flate2::GzBuilder::new().mtime(0).write(Vec::new(), flate2::Compression::new(9));
    gz.write_all(body.as_bytes()).map_err(|e| model(format!("gzip: {e}")))?;
    let gz = gz.finish().map_err(|e| model(format!("gzip: {e}")))?;
    std::fs::create_dir_all(out_dir).map_err(|e| io(&out_dir.to_string_lossy(), e))?;
    let raw_name = format!("{name}_raw.jsonl.gz");
    std::fs::write(out_dir.join(&raw_name), &gz).map_err(|e| io(&raw_name, e))?;
    let m = dict(vec![
        ("schema", sval(spec.raw_schema)),
        ("name", sval(name)),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_lock_sha256", sval(A3_LOCK_SHA256)),
        ("prereg_lock_sha256", sval(env::LOCK_SHA256)),
        ("cases_file_sha256", sval(get_str(&lm, "cases_sha256", spec.launch_rel)?)),
        ("driver_sha256", sval(get_str(&lm, "driver_sha256", spec.launch_rel)?)),
        ("n_records", Value::int(by_key.len() as i64)),
        ("raw_file", sval(&raw_name)),
        ("raw_sha256", sval(&sha256_hex(&gz))),
        ("shards", Value::List(rows)),
        ("frozen_by", sval(spec.frozen_by)),
    ]);
    let mut mt = pyjson::dumps(&m, &DumpOptions::config_writer()).map_err(|e| model(e.to_string()))?;
    mt.push('\n');
    let mp = out_dir.join(format!("{name}_raw_manifest.json"));
    std::fs::write(&mp, &mt).map_err(|e| io(&mp.to_string_lossy(), e))?;
    Ok((mp, sha256_hex(mt.as_bytes())))
}

/// The scored comparison of one refined run with R0.
#[derive(Debug, Clone, PartialEq)]
pub struct Comparison {
    pub v1_key: String,
    pub refinement: String,
    pub status_r0: RunStatus,
    pub status_rk: RunStatus,
    pub c_status: bool,
    pub c_quiet: Option<bool>,
    pub rel_thrust: Option<f64>,
    pub rel_id: Option<f64>,
    pub c_t: Option<bool>,
    pub c_id: Option<bool>,
}

impl Comparison {
    pub fn passes(&self) -> bool {
        self.c_status && self.c_quiet != Some(false) && self.c_t != Some(false) && self.c_id != Some(false)
    }

    pub fn categorical_ok(&self) -> bool {
        self.c_status && self.c_quiet != Some(false)
    }
}

/// A3 outcome (addendum outcome).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    Adequate,
    AdequateWithMargin,
    NotAdequate,
}

impl Outcome {
    pub fn as_str(self) -> &'static str {
        match self {
            Outcome::Adequate => "A3_ADEQUATE",
            Outcome::AdequateWithMargin => "A3_ADEQUATE_WITH_NUMERICAL_MARGIN",
            Outcome::NotAdequate => "A3_NOT_ADEQUATE",
        }
    }
}

fn rel(a: f64, b: f64) -> f64 {
    (a - b).abs() / b.abs()
}

fn quiet(rec: Option<&Value>) -> Option<bool> {
    rec.and_then(|r| finite(get(r, "Id_rms_rel"))).map(|x| x < QUIET_RMS)
}

/// Compare one refined record with its R0 record (either may be absent: absent is NUMERICAL_FAILURE, v1 rule).
pub fn compare(v1_key: &str, refinement: &str, r0: Option<&Value>, rk: Option<&Value>) -> Comparison {
    compare_with(xe_status, v1_key, refinement, r0, rk)
}

/// [`compare`] under the run-status rule `status`.
pub fn compare_with(
    status: fn(&Value) -> RunStatus,
    v1_key: &str,
    refinement: &str,
    r0: Option<&Value>,
    rk: Option<&Value>,
) -> Comparison {
    let st = |r: Option<&Value>| r.map_or(RunStatus::NumericalFailure, status);
    let (s0, sk) = (st(r0), st(rk));
    let c_status = s0 == sk;
    let c_quiet = (s0 != RunStatus::NumericalFailure && sk != RunStatus::NumericalFailure)
        .then(|| matches!((quiet(r0), quiet(rk)), (Some(a), Some(b)) if a == b));
    let num = |r: Option<&Value>, k: &str| r.and_then(|r| finite(get(r, k)));
    let (mut rel_t, mut rel_i, mut c_t, mut c_id) = (None, None, None, None);
    if s0 == RunStatus::Pass {
        match (num(r0, "thrust_N"), num(rk, "thrust_N"), sk == RunStatus::Pass) {
            (Some(a), Some(b), true) => {
                rel_t = Some(rel(b, a));
                c_t = Some(rel(b, a) <= TOL_REL);
            }
            _ => c_t = Some(false),
        }
        match (num(r0, "discharge_current_A"), num(rk, "discharge_current_A"), sk == RunStatus::Pass) {
            (Some(a), Some(b), true) => {
                rel_i = Some(rel(b, a));
                c_id = Some(rel(b, a) <= TOL_REL);
            }
            _ => c_id = Some(false),
        }
    }
    Comparison {
        v1_key: v1_key.into(),
        refinement: refinement.into(),
        status_r0: s0,
        status_rk: sk,
        c_status,
        c_quiet,
        rel_thrust: rel_t,
        rel_id: rel_i,
        c_t,
        c_id,
    }
}

/// The addendum outcome of a family's comparisons and (delta_T, delta_I) with their keys.
pub fn outcome(cmp: &[Comparison]) -> (Outcome, Option<(f64, String)>, Option<(f64, String)>) {
    let argmax = |f: fn(&Comparison) -> Option<f64>| {
        cmp.iter().filter_map(|c| f(c).map(|x| (x, format!("{}|{}", c.v1_key, c.refinement)))).fold(
            None,
            |acc: Option<(f64, String)>, x| match acc {
                Some(a) if a.0 >= x.0 => Some(a),
                _ => Some(x),
            },
        )
    };
    let dt = argmax(|c| c.rel_thrust);
    let di = argmax(|c| c.rel_id);
    let within = |d: &Option<(f64, String)>| d.as_ref().is_none_or(|x| x.0 <= MARGIN_CAP);
    let o = if cmp.iter().all(Comparison::passes) {
        Outcome::Adequate
    } else if cmp.iter().all(Comparison::categorical_ok)
        && cmp.iter().all(|c| c.c_t.is_none() || c.rel_thrust.is_some())
        && cmp.iter().all(|c| c.c_id.is_none() || c.rel_id.is_some())
        && within(&dt)
        && within(&di)
    {
        Outcome::AdequateWithMargin
    } else {
        Outcome::NotAdequate
    };
    (o, dt, di)
}

/// Read and verify a frozen A3 raw envelope; returns (records by key, raw sha256).
pub fn read_frozen(
    repo: &Path,
    manifest: &Path,
    manifest_sha256: &str,
) -> AbepResult<(BTreeMap<String, Value>, String)> {
    read_frozen_with(repo, &XE, &[], manifest, manifest_sha256)
}

/// [`read_frozen`] for the family `spec`; every record must also carry each `(field, value)` of `pins`.
pub fn read_frozen_with(
    repo: &Path,
    spec: &Spec,
    pins: &[(String, String)],
    manifest: &Path,
    manifest_sha256: &str,
) -> AbepResult<(BTreeMap<String, Value>, String)> {
    let label = manifest.to_string_lossy().to_string();
    let m = loads(&read_verified(manifest, manifest_sha256)?, &label)?;
    if get_str(&m, "schema", &label)? != spec.raw_schema {
        return Err(schema(&label, "not an A3 raw manifest"));
    }
    if get_str(&m, "addendum_lock_sha256", &label)? != A3_LOCK_SHA256 {
        return Err(schema(&label, "produced under another A3 lock"));
    }
    let lm = launch_manifest_of(repo, spec)?;
    let cases_sha = get_str(&lm, "cases_sha256", spec.launch_rel)?.to_string();
    if get_str(&m, "cases_file_sha256", &label)? != cases_sha {
        return Err(schema(&label, "produced from another A3 case file"));
    }
    let raw_name = get_str(&m, "raw_file", &label)?;
    let raw_sha = get_str(&m, "raw_sha256", &label)?.to_string();
    let gz = read_verified(&manifest.parent().unwrap_or(Path::new(".")).join(raw_name), &raw_sha)?;
    let mut text = String::new();
    flate2::read::GzDecoder::new(gz.as_slice())
        .read_to_string(&mut text)
        .map_err(|e| schema(raw_name, e.to_string()))?;
    let cr = spec.cases_rel;
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
        let h = want.get(&key).ok_or_else(|| model(format!("unexpected A3 record {key}")))?;
        for (f, w) in [
            ("case_sha256", h.as_str()),
            ("hallthruster_commit", commit.as_str()),
            ("addendum_lock_sha256", A3_LOCK_SHA256),
            ("prereg_lock_sha256", env::LOCK_SHA256),
            ("cases_file_sha256", cases_sha.as_str()),
        ] {
            if get(&r, f).and_then(Value::as_str) != Some(w) {
                return Err(model(format!("A3 record {key}: {f} != {w}")));
            }
        }
        for (f, w) in pins {
            if get(&r, f).and_then(Value::as_str) != Some(w.as_str()) {
                return Err(model(format!("A3 record {key}: {f} != {w}")));
            }
        }
        if recs.insert(key.clone(), r).is_some() {
            return Err(model(format!("duplicate A3 record {key}")));
        }
    }
    let n = finite(get(&m, "n_records")).ok_or_else(|| schema(&label, "n_records"))?;
    if n != recs.len() as f64 {
        return Err(schema(&label, "n_records != records"));
    }
    Ok((recs, raw_sha))
}

fn opt(x: Option<f64>) -> Value {
    x.map_or(Value::Null, fval)
}

fn optb(x: Option<bool>) -> Value {
    x.map_or(Value::Null, Value::Bool)
}

/// Score the frozen A3 raw envelope once: (result JSON value, markdown summary).
pub fn score(repo: &Path, manifest: &Path, manifest_sha256: &str, rust_commit: &str) -> AbepResult<(Value, String)> {
    score_with(repo, &XE, &[], manifest, manifest_sha256, rust_commit)
}

/// The check cases (v1 keys) of an A3 case file, in file order.
fn check_keys(repo: &Path, spec: &Spec) -> AbepResult<Vec<String>> {
    let doc = loads(&std::fs::read(repo.join(spec.cases_rel)).map_err(|e| io(spec.cases_rel, e))?, spec.cases_rel)?;
    let mut keys: Vec<String> = Vec::new();
    for c in get(&doc, "cases").and_then(Value::as_list).ok_or_else(|| schema(spec.cases_rel, "cases"))? {
        let k = get_str(c, "v1_key", spec.cases_rel)?;
        if keys.last().map(String::as_str) != Some(k) {
            keys.push(k.to_string());
        }
    }
    Ok(keys)
}

/// [`score`] for the family `spec` (record pins as in [`read_frozen_with`]).
pub fn score_with(
    repo: &Path,
    spec: &Spec,
    pins: &[(String, String)],
    manifest: &Path,
    manifest_sha256: &str,
    rust_commit: &str,
) -> AbepResult<(Value, String)> {
    let add = load_addendum(repo)?;
    let (recs, raw_sha) = read_frozen_with(repo, spec, pins, manifest, manifest_sha256)?;
    let keys = check_keys(repo, spec)?;
    let rec = |k: &str, r: &str| recs.get(&format!("{k}|{r}"));
    let mut cmp = Vec::new();
    let mut rows = Vec::new();
    for k in &keys {
        let r0 = rec(k, R0);
        for r in [R1, R3] {
            let rk = rec(k, r);
            let c = compare_with(spec.status, k, r, r0, rk);
            let report: Vec<(&str, Value)> = [
                "ion_current_A",
                "mass_eff",
                "current_eff",
                "voltage_eff",
                "anode_eff",
                "Te_max_eV",
                "ne_max_m3",
                "Id_rms_rel",
                "Id_pp_rel",
                "Id_f_dominant_Hz",
                "wall_s",
            ]
            .iter()
            .map(|f| {
                let a = r0.and_then(|x| finite(get(x, f)));
                let b = rk.and_then(|x| finite(get(x, f)));
                (*f, dict(vec![("r0", opt(a)), ("rk", opt(b))]))
            })
            .collect();
            let v = |x: Option<&Value>, f: &str| opt(x.and_then(|x| finite(get(x, f))));
            rows.push(dict(vec![
                ("v1_key", sval(k)),
                ("refinement", sval(r)),
                ("status_r0", sval(c.status_r0.as_str())),
                ("status_rk", sval(c.status_rk.as_str())),
                ("thrust_N_r0", v(r0, "thrust_N")),
                ("thrust_N_rk", v(rk, "thrust_N")),
                ("discharge_current_A_r0", v(r0, "discharge_current_A")),
                ("discharge_current_A_rk", v(rk, "discharge_current_A")),
                ("discharge_power_W_r0", v(r0, "discharge_power_W")),
                ("discharge_power_W_rk", v(rk, "discharge_power_W")),
                ("rel_thrust", opt(c.rel_thrust)),
                ("rel_discharge_current", opt(c.rel_id)),
                ("C-STATUS", Value::Bool(c.c_status)),
                ("C-QUIET", optb(c.c_quiet)),
                ("C-T", optb(c.c_t)),
                ("C-ID", optb(c.c_id)),
                ("passes", Value::Bool(c.passes())),
                ("report_only", dict(report)),
            ]));
            cmp.push(c);
        }
    }
    let (o, dt, di) = outcome(&cmp);
    let agg = |d: &Option<(f64, String)>| match d {
        Some((x, k)) => dict(vec![("value", fval(*x)), ("at", sval(k))]),
        None => Value::Null,
    };
    let consequence = get(&add, "consequence").and_then(|c| get(c, o.as_str())).cloned().unwrap_or(Value::Null);
    let n_fail = cmp.iter().filter(|c| !c.passes()).count();
    let status_counts: Vec<(&str, Value)> = REFINEMENTS
        .iter()
        .map(|r| {
            let counts: Vec<(&str, Value)> = RunStatus::ALL
                .iter()
                .map(|s| {
                    let n = keys
                        .iter()
                        .filter(|k| rec(k, r).map_or(RunStatus::NumericalFailure, spec.status) == *s)
                        .count();
                    (s.as_str(), Value::int(n as i64))
                })
                .collect();
            (*r, dict(counts))
        })
        .collect();
    let result = dict(vec![
        ("schema", sval(A3_RESULT_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("addendum", sval("A3 numerics adequacy (RG-04)")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("family", sval(spec.family)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(A3_LOCK_SHA256)),
        ("raw_manifest_sha256", sval(manifest_sha256)),
        ("raw_sha256", sval(&raw_sha)),
        ("rust_commit", sval(rust_commit)),
        ("scored_once", Value::Bool(true)),
        ("tolerance_rel", fval(TOL_REL)),
        ("margin_cap", fval(MARGIN_CAP)),
        ("n_check_cases", Value::int(keys.len() as i64)),
        ("n_comparisons", Value::int(cmp.len() as i64)),
        ("n_comparisons_failing", Value::int(n_fail as i64)),
        ("status_counts", dict(status_counts)),
        ("delta_T", agg(&dt)),
        ("delta_I", agg(&di)),
        ("outcome", sval(o.as_str())),
        ("consequence", consequence),
        ("comparisons", Value::List(rows)),
    ]);
    let md = render_md(&result, &cmp, o, &dt, &di);
    Ok((result, md))
}

fn pct(x: Option<f64>) -> String {
    x.map_or("-".into(), |v| format!("{:.2} %", 100.0 * v))
}

fn yn(x: Option<bool>) -> &'static str {
    match x {
        Some(true) => "ok",
        Some(false) => "FAIL",
        None => "-",
    }
}

/// (result JSON, result page) file names of a family's A3 result.
pub fn result_files(family: &str) -> (&'static str, &'static str) {
    match family {
        "XE" => ("a3_numerics_result_v1.json", "A3_NUMERICS_RESULT.md"),
        _ => ("a3_numerics_result_air_v1.json", "A3_NUMERICS_RESULT_AIR.md"),
    }
}

fn render_md(
    result: &Value,
    cmp: &[Comparison],
    o: Outcome,
    dt: &Option<(f64, String)>,
    di: &Option<(f64, String)>,
) -> String {
    let g = |k: &str| get(result, k).and_then(Value::as_str).unwrap_or("").to_string();
    let mut s = String::new();
    let fam = g("family");
    s.push_str(&format!("# NP-HALL-PARAMETRIC-ENVELOPE addendum A3: numerics adequacy result ({fam})\n\n"));
    s.push_str(&format!(
        "`{}` is authoritative; this page restates it. PARAMETRIC / NOT_VALIDATED. Scored once ",
        result_files(&fam).0
    ));
    s.push_str(&format!(
        "from the frozen A3 raw envelope (manifest sha256 `{}`, raw `{}`).\n\n",
        g("raw_manifest_sha256"),
        g("raw_sha256")
    ));
    s.push_str(&format!("**Outcome: {}**. ", o.as_str()));
    let d = |x: &Option<(f64, String)>| x.as_ref().map_or("-".into(), |(v, k)| format!("{:.2} % at `{k}`", 100.0 * v));
    s.push_str(&format!("delta_T = {}; delta_I = {}.\n\n", d(dt), d(di)));
    s.push_str("| v1 key | ref | status R0 / Rk | dT | dI | C-STATUS | C-QUIET | C-T | C-ID |\n|---|---|---|---|---|---|---|---|---|\n");
    for c in cmp {
        s.push_str(&format!(
            "| `{}` | {} | {} / {} | {} | {} | {} | {} | {} | {} |\n",
            c.v1_key,
            c.refinement,
            c.status_r0.as_str(),
            c.status_rk.as_str(),
            pct(c.rel_thrust),
            pct(c.rel_id),
            yn(Some(c.c_status)),
            yn(c.c_quiet),
            yn(c.c_t),
            yn(c.c_id)
        ));
    }
    s.push_str(
        "\nCriteria (addendum): C-STATUS v1 run status identical; C-QUIET quiet class (Id_rms_rel < 0.5) identical; ",
    );
    s.push_str(
        "C-T / C-ID relative thrust / I_d change <= 2 % when R0 is PASS. The consequence of the outcome is the ",
    );
    s.push_str("addendum's, copied into the JSON; v1 records and numerics are unchanged.\n");
    s
}

/// Report-only determinism diagnostic: R0 records against the frozen grid records of the same keys.
pub fn determinism(a3: &BTreeMap<String, Value>, grid: &BTreeMap<String, Value>) -> Vec<(String, bool, String)> {
    let mut out = Vec::new();
    let keys: BTreeSet<&String> = a3.keys().filter(|k| k.ends_with(&format!("|{R0}"))).collect();
    for k in keys {
        let v1 = k.trim_end_matches(&format!("|{R0}")).to_string();
        let a = &a3[k];
        let Some(g) = grid.get(&v1) else {
            out.push((v1, false, "grid record absent".into()));
            continue;
        };
        let f = |r: &Value, n: &str| get(r, n).map(|v| pyjson::dumps(v, &DumpOptions::default()).unwrap_or_default());
        let fields = ["retcode", "thrust_N", "discharge_current_A"];
        let diff: Vec<&str> = fields.iter().copied().filter(|n| f(a, n) != f(g, n)).collect();
        out.push((v1, diff.is_empty(), diff.join(",")));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(pairs: Vec<(&str, Value)>) -> Value {
        dict(pairs)
    }

    fn ok(t: f64, i: f64, rms: f64, sustained: bool) -> Value {
        rec(vec![
            ("retcode", sval("success")),
            ("converged", Value::Bool(true)),
            ("finite", Value::Bool(true)),
            ("sustained", Value::Bool(sustained)),
            ("thrust_N", fval(t)),
            ("discharge_current_A", fval(i)),
            ("discharge_power_W", fval(300.0 * i)),
            ("Id_rms_rel", fval(rms)),
        ])
    }

    #[test]
    fn pick_is_the_registered_hash_rule() {
        // sha256("a") = ca978112ca1bbdca...: 0xca978112ca1bbdca mod 9 / mod 2
        assert_eq!(pick("a", 2), (0xca978112ca1bbdca_u64 % 2) as usize);
        assert_eq!(pick("a", 9), (0xca978112ca1bbdca_u64 % 9) as usize);
    }

    #[test]
    fn comparison_rules() {
        let a = ok(0.010, 2.0, 0.1, true);
        let c = compare("k", R1, Some(&a), Some(&ok(0.0101, 2.01, 0.1, true)));
        assert!(c.passes());
        let c = compare("k", R1, Some(&a), Some(&ok(0.0105, 2.0, 0.1, true)));
        assert_eq!(c.c_t, Some(false));
        assert!(c.categorical_ok());
        let c = compare("k", R1, Some(&a), Some(&ok(0.010, 2.0, 0.6, true)));
        assert_eq!(c.c_quiet, Some(false));
        let c = compare("k", R3, Some(&a), Some(&ok(0.010, 2.0, 0.1, false)));
        assert!(!c.c_status);
        // a missing refined run is NUMERICAL_FAILURE
        let c = compare("k", R3, Some(&a), None);
        assert_eq!(c.status_rk, RunStatus::NumericalFailure);
        assert!(!c.passes());
        // both failed: status identical, no continuous criterion
        let f = rec(vec![("retcode", sval("failure"))]);
        let c = compare("k", R1, Some(&f), Some(&f));
        assert!(c.passes());
        assert_eq!(c.c_quiet, None);
    }

    #[test]
    fn outcome_tiers() {
        let a = ok(0.010, 2.0, 0.1, true);
        let pass = compare("k", R1, Some(&a), Some(&ok(0.0101, 2.0, 0.1, true)));
        assert_eq!(outcome(std::slice::from_ref(&pass)).0, Outcome::Adequate);
        let margin = compare("k", R3, Some(&a), Some(&ok(0.0108, 2.0, 0.1, true)));
        let (o, dt, _) = outcome(&[pass.clone(), margin]);
        assert_eq!(o, Outcome::AdequateWithMargin);
        assert!((dt.unwrap().0 - 0.08).abs() < 1e-9);
        let big = compare("k", R3, Some(&a), Some(&ok(0.0115, 2.0, 0.1, true)));
        assert_eq!(outcome(&[pass.clone(), big]).0, Outcome::NotAdequate);
        let flip = compare("k", R3, Some(&a), Some(&ok(0.010, 2.0, 0.1, false)));
        assert_eq!(outcome(&[pass, flip]).0, Outcome::NotAdequate);
    }
}
