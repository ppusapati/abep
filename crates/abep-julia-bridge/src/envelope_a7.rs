//! NP-HALL-PARAMETRIC-ENVELOPE addendum A7 (Hall numerical method; `prereg_addendum_a7_hall_numerical_method_v1.json`,
//! locked by `prereg_addendum_a7_hall_numerical_method_lock_v1.json`): the A7 levels, the demonstration case file and
//! its single scoring pass, and the XE grid stages at the production level (Stage 1: G-RP1, Stage 2: the rest; A9.37).
//! Only numerical fields of the frozen v1 cases change. The run-status rule and the per-case comparison are
//! `abep_hall::envelope_a7`. PARAMETRIC / NOT_VALIDATED.

use crate::envelope_a3 as a3;
use crate::envelope_cases::{self as ec, BRIDGE_LIB_REL, THREAD_PIN};
use crate::jobs::{child_env, JobSpec, ThreadSettings};
use abep_hall::envelope::{self as env, case_hash, Family};
use abep_hall::envelope_a7::{self as h7, A7Status, CaseOutcome, GridStage};
use abep_provenance::{read_verified, sha256_hex};
use abep_types::pyjson::{self, Dict, DumpOptions, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::BTreeMap;
use std::io::Read;
use std::path::{Path, PathBuf};

pub const NP: &str = h7::NP;
pub const ADDENDUM_REL: &str = h7::ADDENDUM_REL;
pub const ADDENDUM_SHA256: &str = h7::ADDENDUM_SHA256;
pub const LOCK_REL: &str = h7::LOCK_REL;
pub const LOCK_SHA256: &str = h7::LOCK_SHA256;
pub const DRIVER_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_a7_driver.jl";
pub const A7_BRIDGE_REL: &str = h7::A7_BRIDGE_REL;
pub const SEED: &str = "NP-HALL-PARAMETRIC-ENVELOPE/A7/v1";
pub const CASES_SCHEMA: &str = "np_hall_parametric_envelope_a7_cases_v1";
pub const LAUNCH_SCHEMA: &str = "np_hall_parametric_envelope_a7_launch_manifest_v1";
pub const RAW_SCHEMA: &str = h7::RAW_SCHEMA;
pub const DEMO_RESULT_SCHEMA: &str = h7::DEMO_RESULT_SCHEMA;
pub const CONTRACT_ID: &str = "NP-HALL-PARAMETRIC-ENVELOPE-A7-V1";
pub const DEMO_RESULT_REL: &str = h7::DEMO_RESULT_REL;
pub const DEMO_RP1_RESULT_REL: &str = h7::DEMO_RP1_RESULT_REL;
/// The DBF-1 hardware configuration (A9.37 / A9.38): H1 geometry RP-1, magnetic target BZ-P5B16 (surrogate shape).
pub const RP1_GEOMETRY: &str = "G-RP1";
pub const DBF1_BZ_SHAPE: &str = "BZ-P5B16";
pub const A6_ADDENDUM_REL: &str = crate::envelope_a6::ADDENDUM_REL;
pub const V1_DT_S: f64 = 5e-9;
/// Registered A7 numerics (addendum method): duration = DURATION_FACTOR x v1 duration, averaging window from
/// WINDOW_START_FACTOR x v1 duration to the end, NUM_SAVE evenly spaced frames, solver step control at the pinned
/// HallThruster.jl defaults (stated explicitly in every case).
pub const DURATION_FACTOR: f64 = 4.0;
pub const WINDOW_START_FACTOR: f64 = 1.0;
pub const NUM_SAVE: i64 = 4000;

/// One of the A7 case sets.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    /// The demonstration cases on G-RP1 (scored first; gates Stage 1).
    DemoRp1,
    /// The other demonstration cases (scored with DemoRp1 as the full demonstration; gates Stage 2).
    DemoRest,
    Grid(GridStage),
}

impl Kind {
    pub fn parse(s: &str) -> Option<Kind> {
        match s {
            "demo-rp1" => Some(Kind::DemoRp1),
            "demo-rest" => Some(Kind::DemoRest),
            "stage1" => Some(Kind::Grid(GridStage::Stage1)),
            "stage2" => Some(Kind::Grid(GridStage::Stage2)),
            _ => None,
        }
    }

    pub fn cases_rel(self) -> &'static str {
        match self {
            Kind::DemoRp1 => "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a7_demo_rp1_cases_v1.json",
            Kind::DemoRest => "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a7_demo_rest_cases_v1.json",
            Kind::Grid(s) => s.cases_rel(),
        }
    }

    pub fn launch_rel(self) -> &'static str {
        match self {
            Kind::DemoRp1 => {
                "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_a7_demo_rp1_v1.json"
            }
            Kind::DemoRest => {
                "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_a7_demo_rest_v1.json"
            }
            Kind::Grid(s) => s.launch_rel(),
        }
    }

    pub fn launch_name(self) -> &'static str {
        self.launch_rel().rsplit('/').next().expect("path")
    }

    pub fn raw_kind(self) -> &'static str {
        match self {
            Kind::DemoRp1 => "DEMONSTRATION_RP1",
            Kind::DemoRest => "DEMONSTRATION_REST",
            Kind::Grid(s) => s.kind(),
        }
    }

    pub fn n_shards(self) -> usize {
        match self {
            Kind::DemoRp1 | Kind::DemoRest => 3,
            Kind::Grid(_) => 48,
        }
    }
}

/// An A7 level: P (production, 2 x v1 cells) or C (check, 4 x v1 cells); both at the registered duration and window.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Level {
    P,
    C,
}

impl Level {
    pub fn id(self) -> &'static str {
        match self {
            Level::P => "A7-P",
            Level::C => "A7-C",
        }
    }

    pub fn cell_factor(self) -> i64 {
        match self {
            Level::P => 2,
            Level::C => 4,
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

/// The verified addendum (A7 lock and every file it locks).
pub fn load_addendum(repo: &Path) -> AbepResult<Value> {
    let lock = loads(&read_verified(&repo.join(LOCK_REL), LOCK_SHA256)?, LOCK_REL)?;
    let files = get(&lock, "files").and_then(Value::as_dict).ok_or_else(|| schema(LOCK_REL, "files"))?;
    for (f, h) in files.iter() {
        read_verified(&repo.join(NP).join(f), h.as_str().ok_or_else(|| schema(LOCK_REL, f.clone()))?)?;
    }
    loads(&read_verified(&repo.join(ADDENDUM_REL), ADDENDUM_SHA256)?, ADDENDUM_REL)
}

/// The registered numerics block written into every A7 case (the pinned HallThruster.jl v0.23.1 SimParams / Config
/// defaults, stated explicitly so the A7 bridge reads them from the case and never from a default).
pub fn numerics_block() -> Value {
    dict(vec![
        ("CFL", fval(0.799)),
        ("min_dt_s", fval(1e-10)),
        ("max_dt_s", fval(1e-7)),
        ("max_small_steps", Value::int(100)),
        ("adaptive", Value::Bool(true)),
        ("reconstruct", Value::Bool(true)),
        ("implicit_energy", fval(1.0)),
    ])
}

/// The v1 case at A7 level `lv` (cells, dt_s, duration_s, average_start_s, num_save and the numerics block change),
/// with the A7 identity fields and a recomputed case hash.
pub fn at_level(base: &Value, v1_key: &str, lv: Level) -> AbepResult<Value> {
    let Value::Dict(d) = base else { return Err(model("case is not an object")) };
    let label = env::CASES_REL;
    let v1_sha = get_str(base, "case_sha256", label)?.to_string();
    let cells = get(base, "cells").and_then(|v| if let Value::Int(i) = v { i.as_i64() } else { None });
    let cells = cells.ok_or_else(|| schema(label, "cells"))?;
    let dur = finite(get(base, "duration_s")).ok_or_else(|| schema(label, "duration_s"))?;
    let f = lv.cell_factor();
    let mut n = d.clone();
    n.remove("case_sha256");
    let key = format!("{v1_key}|{}", lv.id());
    n.insert("key", sval(&key));
    n.insert("id", sval(&key));
    n.insert("cells", Value::int(cells * f));
    n.insert("dt_s", fval(V1_DT_S / f as f64));
    n.insert("duration_s", fval(DURATION_FACTOR * dur));
    n.insert("average_start_s", fval(WINDOW_START_FACTOR * dur));
    n.insert("num_save", Value::int(NUM_SAVE));
    n.insert("numerics", numerics_block());
    n.insert("a7_level", sval(lv.id()));
    n.insert("v1_key", sval(v1_key));
    n.insert("v1_case_sha256", sval(&v1_sha));
    let h = case_hash(&Value::Dict(n.clone()))?;
    n.insert("case_sha256", sval(&h));
    Ok(Value::Dict(n))
}

/// The fresh seeded demonstration keys: one per hardware configuration (geometry x B shape, v1 file order), the
/// operating point and transport picked by `a3::pick` on `SEED|XE|<geometry>|<shape>|<axis>[|r<j>]`, re-picked with
/// j = 1, 2, ... while the key is in `exclude` (the A3 check set and the A6 study set).
pub fn fresh_seeded_keys(cs: &env::CaseSet, exclude: &[String]) -> Vec<String> {
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
            let mut j = 0usize;
            loop {
                let base = format!("{SEED}|XE|{gi}|{si}");
                let sfx = if j == 0 { String::new() } else { format!("|r{j}") };
                let p = |axis: &str, v: &Vec<String>| v[a3::pick(&format!("{base}|{axis}{sfx}"), v.len())].clone();
                let key = format!(
                    "XE|{gi}|{si}|{}|{}|{}|{}",
                    p("B_peak", &b),
                    p("V_d", &vd),
                    p("mdot", &m),
                    p("transport", &t)
                );
                if !exclude.contains(&key) {
                    out.push(key);
                    break;
                }
                j += 1;
            }
        }
    }
    out
}

/// The A3 check-set keys and the A6 study keys (excluded from the fresh seeded set).
pub fn prior_keys(repo: &Path) -> AbepResult<(Vec<String>, Vec<String>)> {
    let a6 = crate::envelope_a6::load_addendum(repo)?;
    let cst = get(&a6, "convergence_study").ok_or_else(|| schema(A6_ADDENDUM_REL, "convergence_study"))?;
    let mut a6k = strings(get(cst, "seeded_keys"), A6_ADDENDUM_REL)?;
    a6k.extend(strings(get(cst, "mandatory_keys"), A6_ADDENDUM_REL)?);
    let (_, cs, cells) = a3::v1_case_set_and_cells(repo)?;
    let a3k: Vec<String> = a3::select_check_set(&cs, Family::Xe, &cells)?.into_iter().map(|c| c.key).collect();
    Ok((a3k, a6k))
}

/// The RP-1 seeded keys on the DBF-1 hardware (G-RP1, BZ-P5B16): one per B_peak x mdot level (v1 order), V_d and
/// transport picked by `a3::pick` on `SEED|RP1|XE|G-RP1|BZ-P5B16|<B_peak>|<mdot>|<axis>[|r<j>]`, re-picked with
/// j = 1, 2, ... while the key is in `exclude`.
pub fn rp1_seeded_keys(cs: &env::CaseSet, exclude: &[String]) -> Vec<String> {
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
    let (b, vd, m, t) =
        (order(|c| &c.b_peak_id), order(|c| &c.vd_id), order(|c| &c.mdot_id), order(|c| &c.transport_id));
    let mut out: Vec<String> = Vec::new();
    for bi in &b {
        for mi in &m {
            let mut j = 0usize;
            loop {
                let base = format!("{SEED}|RP1|XE|{RP1_GEOMETRY}|{DBF1_BZ_SHAPE}|{bi}|{mi}");
                let sfx = if j == 0 { String::new() } else { format!("|r{j}") };
                let p = |axis: &str, v: &Vec<String>| v[a3::pick(&format!("{base}|{axis}{sfx}"), v.len())].clone();
                let key =
                    format!("XE|{RP1_GEOMETRY}|{DBF1_BZ_SHAPE}|{bi}|{}|{mi}|{}", p("V_d", &vd), p("transport", &t));
                if !exclude.contains(&key) && !out.contains(&key) {
                    out.push(key);
                    break;
                }
                j += 1;
            }
        }
    }
    out
}

/// The demonstration keys: the A6 study keys (A6 order), the fresh seeded keys and the RP-1 seeded keys.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DemoKeys {
    pub a6: Vec<String>,
    pub fresh: Vec<String>,
    pub rp1: Vec<String>,
}

impl DemoKeys {
    /// Every key in registration order.
    pub fn all(&self) -> Vec<String> {
        self.a6.iter().chain(&self.fresh).chain(&self.rp1).cloned().collect()
    }

    /// The keys of a demonstration case file (DemoRp1: geometry G-RP1; DemoRest: the others), registration order.
    pub fn of(&self, kind: Kind) -> Vec<String> {
        let rp1 = |k: &String| k.contains(&format!("|{RP1_GEOMETRY}|"));
        self.all()
            .into_iter()
            .filter(|k| match kind {
                Kind::DemoRp1 => rp1(k),
                Kind::DemoRest => !rp1(k),
                Kind::Grid(_) => false,
            })
            .collect()
    }

    /// Which registered set a key belongs to.
    pub fn set_of(&self, k: &str) -> &'static str {
        if self.a6.iter().any(|x| x == k) {
            "A6_STUDY"
        } else if self.fresh.iter().any(|x| x == k) {
            "FRESH_SEEDED"
        } else {
            "RP1_SEEDED"
        }
    }
}

/// The demonstration keys computed from the frozen inputs.
pub fn demo_keys(repo: &Path) -> AbepResult<DemoKeys> {
    let (a3k, a6k) = prior_keys(repo)?;
    let (_, cs, _) = a3::v1_case_set_and_cells(repo)?;
    let mut ex = a3k;
    ex.extend(a6k.iter().cloned());
    let fresh = fresh_seeded_keys(&cs, &ex);
    ex.extend(fresh.iter().cloned());
    let rp1 = rp1_seeded_keys(&cs, &ex);
    Ok(DemoKeys { a6: a6k, fresh, rp1 })
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
        ("addendum", sval("A7 Hall numerical method")),
        ("kind", sval(kind.raw_kind())),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(LOCK_SHA256)),
        ("prereg_lock_sha256", sval(env::LOCK_SHA256)),
    ];
    v.extend(extra);
    v.push(("generated_by", sval("abep-h1-envelope-a7 generate (crates/abep-julia-bridge/src/envelope_a7.rs)")));
    v.push(("n_cases", Value::int(cases.len() as i64)));
    v.push(("cases", Value::List(cases)));
    dict(v)
}

/// The registered demonstration keys (addendum), checked against [`demo_keys`].
pub fn registered_demo_keys(repo: &Path, add: &Value) -> AbepResult<DemoKeys> {
    let d = get(add, "demonstration_subset").ok_or_else(|| schema(ADDENDUM_REL, "demonstration_subset"))?;
    let reg = DemoKeys {
        a6: strings(get(d, "a6_study_keys"), ADDENDUM_REL)?,
        fresh: strings(get(d, "fresh_seeded_keys"), ADDENDUM_REL)?,
        rp1: strings(get(d, "rp1_seeded_keys"), ADDENDUM_REL)?,
    };
    if demo_keys(repo)? != reg {
        return Err(model("the A7 demonstration keys differ from the keys registered in the addendum"));
    }
    Ok(reg)
}

/// A demonstration case file (`kind` DemoRp1 or DemoRest): each of its registered keys at A7-P and A7-C.
pub fn build_demo_doc(repo: &Path, kind: Kind) -> AbepResult<Value> {
    let add = load_addendum(repo)?;
    let keys = registered_demo_keys(repo, &add)?.of(kind);
    let (v1doc, cs, _) = a3::v1_case_set_and_cells(repo)?;
    let by = v1_by_key(&v1doc)?;
    let mut cases = Vec::new();
    for k in &keys {
        let base = by.get(k).ok_or_else(|| model(format!("demonstration case {k} not in v1")))?;
        for lv in [Level::P, Level::C] {
            cases.push(at_level(base, k, lv)?);
        }
    }
    Ok(header(kind, vec![("seed", sval(SEED)), ("v1_cases_sha256", sval(&cs.sha256))], cases))
}

/// Scope of a demonstration scoring pass.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Scope {
    /// The RP-1 subset (gates Stage 1).
    Rp1,
    /// Every demonstration case (gates Stage 2).
    All,
}

impl Scope {
    pub fn result_rel(self) -> &'static str {
        match self {
            Scope::Rp1 => DEMO_RP1_RESULT_REL,
            Scope::All => DEMO_RESULT_REL,
        }
    }

    pub fn page_name(self) -> &'static str {
        match self {
            Scope::Rp1 => "A7_DEMONSTRATION_RP1_RESULT.md",
            Scope::All => "A7_DEMONSTRATION_RESULT.md",
        }
    }

    pub fn kinds(self) -> &'static [Kind] {
        match self {
            Scope::Rp1 => &[Kind::DemoRp1],
            Scope::All => &[Kind::DemoRp1, Kind::DemoRest],
        }
    }

    pub fn for_stage(stage: GridStage) -> Scope {
        match stage {
            GridStage::Stage1 => Scope::Rp1,
            GridStage::Stage2 => Scope::All,
        }
    }
}

/// The committed demonstration result's outcome of `scope` (the grid stages refuse unless it was demonstrated).
pub fn demo_outcome(repo: &Path, scope: Scope) -> AbepResult<String> {
    let rel = scope.result_rel();
    let v = loads(
        &std::fs::read(repo.join(rel)).map_err(|e| AbepError::IncompleteEvidence {
            message: format!("A7 demonstration result not committed: {e}"),
        })?,
        rel,
    )?;
    if get_str(&v, "schema", rel)? != DEMO_RESULT_SCHEMA || get_str(&v, "addendum_lock_sha256", rel)? != LOCK_SHA256 {
        return Err(schema(rel, "not an A7 demonstration result under the A7 lock"));
    }
    Ok(get_str(&v, "outcome", rel)?.to_string())
}

/// An XE grid stage case file at A7-P (refused unless the gating demonstration outcome is demonstrated).
pub fn build_grid_doc(repo: &Path, stage: GridStage) -> AbepResult<Value> {
    load_addendum(repo)?;
    let scope = Scope::for_stage(stage);
    let o = demo_outcome(repo, scope)?;
    if o != OUTCOME_DEMONSTRATED {
        return Err(model(format!(
            "A7 {scope:?} demonstration outcome is {o}: the A7 {} grid is not run",
            stage.as_str()
        )));
    }
    let (v1doc, cs, _) = a3::v1_case_set_and_cells(repo)?;
    let by = v1_by_key(&v1doc)?;
    let mut cases = Vec::new();
    for c in cs.cases.iter().filter(|c| c.family == Family::Xe && stage.contains(c)) {
        cases.push(at_level(&by[&c.key], &c.key, Level::P)?);
    }
    let rs = abep_provenance::sha256_file(&repo.join(scope.result_rel()))?;
    Ok(header(
        Kind::Grid(stage),
        vec![
            ("stage", sval(stage.as_str())),
            ("production_level", sval(Level::P.id())),
            ("demonstration_result", sval(scope.result_rel())),
            ("demonstration_result_sha256", sval(&rs)),
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
        ("a7_bridge", sval(A7_BRIDGE_REL)),
        ("a7_bridge_sha256", sval(&sha(A7_BRIDGE_REL)?)),
        ("n_cases", Value::int(n as i64)),
        ("n_shards", Value::int(kind.n_shards() as i64)),
        ("shard_rule", sval("case index i (0-based, file order) belongs to shard i mod n_shards")),
        ("thread_env", dict(THREAD_PIN.iter().map(|(k, v)| (*k, sval(v))).collect())),
        ("mode", sval("vacuum")),
    ]))
}

pub fn generate(repo: &Path, kind: Kind) -> AbepResult<(String, String)> {
    let doc = match kind {
        Kind::DemoRp1 | Kind::DemoRest => build_demo_doc(repo, kind)?,
        Kind::Grid(s) => build_grid_doc(repo, s)?,
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
    for (rel, t) in [(kind.cases_rel(), &cases), (kind.launch_rel(), &lm)] {
        std::fs::write(repo.join(rel), t).map_err(|e| io(rel, e))?;
    }
    Ok(())
}

pub fn check(repo: &Path, kind: Kind) -> AbepResult<usize> {
    let (cases, lm) = generate(repo, kind)?;
    for (rel, t) in [(kind.cases_rel(), &cases), (kind.launch_rel(), &lm)] {
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
    loads(&std::fs::read(repo.join(lr)).map_err(|e| io(lr, e))?, lr)
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
    let s = |k: &str| -> AbepResult<String> { Ok(get_str(&lm, k, lr)?.to_string()) };
    let out = format!("{out_dir}/a7_s{shard:02}.jsonl");
    let threads = ThreadSettings::pinned(THREAD_PIN);
    let mut inputs = vec![
        (DRIVER_REL.to_string(), s("driver_sha256")?),
        (kind.cases_rel().to_string(), s("cases_sha256")?),
        (LOCK_REL.to_string(), LOCK_SHA256.to_string()),
        (ADDENDUM_REL.to_string(), ADDENDUM_SHA256.to_string()),
        (env::LOCK_REL.to_string(), env::LOCK_SHA256.to_string()),
        (env::PREREG_REL.to_string(), env::PREREG_SHA256.to_string()),
        (BRIDGE_LIB_REL.to_string(), s("bridge_lib_sha256")?),
        (A7_BRIDGE_REL.to_string(), s("a7_bridge_sha256")?),
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

/// Freeze A7 shard outputs (the raw manifest pins the A7 lock, the case file, the driver and the A7 bridge of `kind`).
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
        ("kind", sval(kind.raw_kind())),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_lock_sha256", sval(LOCK_SHA256)),
        ("prereg_lock_sha256", sval(env::LOCK_SHA256)),
        ("cases_file_sha256", sval(get_str(&lm, "cases_sha256", lr)?)),
        ("driver_sha256", sval(get_str(&lm, "driver_sha256", lr)?)),
        ("a7_bridge_sha256", sval(get_str(&lm, "a7_bridge_sha256", lr)?)),
    ];
    crate::air_cases::freeze_records(name, shards, out_dir, header, "abep-h1-envelope-a7 freeze")
}

/// Read and verify a frozen A7 raw file of `kind`; returns (records by key, raw sha256).
pub fn read_frozen(
    repo: &Path,
    kind: Kind,
    manifest: &Path,
    manifest_sha256: &str,
) -> AbepResult<(BTreeMap<String, Value>, String)> {
    let label = manifest.to_string_lossy().to_string();
    let m = loads(&read_verified(manifest, manifest_sha256)?, &label)?;
    if get_str(&m, "schema", &label)? != RAW_SCHEMA
        || get_str(&m, "addendum_lock_sha256", &label)? != LOCK_SHA256
        || get_str(&m, "kind", &label)? != kind.raw_kind()
    {
        return Err(schema(&label, "not an A7 raw manifest of this kind under the A7 lock"));
    }
    let lm = launch_manifest(repo, kind)?;
    let cases_sha = get_str(&lm, "cases_sha256", kind.launch_rel())?.to_string();
    if get_str(&m, "cases_file_sha256", &label)? != cases_sha {
        return Err(schema(&label, "produced from another A7 case file"));
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
    let a7b = get_str(&lm, "a7_bridge_sha256", kind.launch_rel())?.to_string();
    let mut recs = BTreeMap::new();
    for line in text.lines().filter(|l| !l.trim().is_empty()) {
        let r = pyjson::loads(line).map_err(|e| schema(raw_name, e.to_string()))?;
        let key = get_str(&r, "key", raw_name)?.to_string();
        let h = want.get(&key).ok_or_else(|| model(format!("unexpected A7 record {key}")))?;
        for (f, w) in [
            ("case_sha256", h.as_str()),
            ("hallthruster_commit", commit.as_str()),
            ("addendum_lock_sha256", LOCK_SHA256),
            ("prereg_lock_sha256", env::LOCK_SHA256),
            ("cases_file_sha256", cases_sha.as_str()),
            ("a7_bridge_sha256", a7b.as_str()),
        ] {
            if get(&r, f).and_then(Value::as_str) != Some(w) {
                return Err(model(format!("A7 record {key}: {f} != {w}")));
            }
        }
        if recs.insert(key.clone(), r).is_some() {
            return Err(model(format!("duplicate A7 record {key}")));
        }
    }
    if recs.len() != want.len() || finite(get(&m, "n_records")) != Some(recs.len() as f64) {
        return Err(schema(&label, "n_records != records or records missing"));
    }
    Ok((recs, raw_sha))
}

pub const OUTCOME_DEMONSTRATED: &str = h7::OUTCOME_DEMONSTRATED;
pub const OUTCOME_NOT_DEMONSTRATED: &str = h7::OUTCOME_NOT_DEMONSTRATED;

/// The demonstration pass rule (addendum pass_rule) over the case outcomes: no NOT_CONVERGED case, and at least one
/// CONVERGED_EVALUATED case. Persistent unknowns never fail it; they are counted and stay unknowns.
pub fn pass_rule(outcomes: &[CaseOutcome]) -> &'static str {
    let bad = outcomes.contains(&CaseOutcome::NotConverged);
    let some = outcomes.contains(&CaseOutcome::ConvergedEvaluated);
    if !bad && some {
        OUTCOME_DEMONSTRATED
    } else {
        OUTCOME_NOT_DEMONSTRATED
    }
}

fn ov(x: Option<(f64, f64, bool)>) -> (Value, Value, Value) {
    match x {
        Some((d, a, b)) => (
            if d.is_finite() { fval(d) } else { Value::Null },
            if a.is_finite() { fval(a) } else { Value::Null },
            Value::Bool(b),
        ),
        None => (Value::Null, Value::Null, Value::Null),
    }
}

/// Score the frozen demonstration of `scope` once: (result JSON, page). `frozen` holds the frozen raw manifest and its
/// sha256 for each demonstration case file of the scope (Rp1: DemoRp1; All: DemoRp1 and DemoRest), in that order.
pub fn score_demo(
    repo: &Path,
    scope: Scope,
    frozen: &[(&Path, &str)],
    rust_commit: &str,
) -> AbepResult<(Value, String)> {
    let add = load_addendum(repo)?;
    let dk = registered_demo_keys(repo, &add)?;
    let kinds = scope.kinds();
    if frozen.len() != kinds.len() {
        return Err(model(format!("{scope:?} scoring needs {} frozen demonstration files", kinds.len())));
    }
    let mut recs: BTreeMap<String, Value> = BTreeMap::new();
    let mut raw_shas = Vec::new();
    let mut man_shas = Vec::new();
    let mut keys = Vec::new();
    for (kind, (m, h)) in kinds.iter().zip(frozen) {
        let (r, rs) = read_frozen(repo, *kind, m, h)?;
        recs.extend(r);
        raw_shas.push(rs);
        man_shas.push(h.to_string());
        keys.extend(dk.of(*kind));
    }
    let raw_sha = raw_shas.join("+");
    let manifest_sha256 = man_shas.join("+");
    let (_, cs, _) = a3::v1_case_set_and_cells(repo)?;
    let by = cs.by_key();
    let mut rows = Vec::new();
    let mut outcomes = Vec::new();
    let mut md_rows = String::new();
    let mut counts: BTreeMap<&'static str, usize> = BTreeMap::new();
    for key in keys.iter() {
        let ci = by.get(key.as_str()).ok_or_else(|| model(format!("{key} not in v1")))?;
        let p = recs.get(&format!("{key}|{}", Level::P.id()));
        let c = recs.get(&format!("{key}|{}", Level::C.id()));
        let cmp = h7::compare(p, c, ci.mdot_kg_s);
        let o = cmp.outcome();
        outcomes.push(o);
        *counts.entry(o.as_str()).or_default() += 1;
        let (td, ta, tb) = ov(cmp.thrust);
        let (id, ia, ib) = ov(cmp.current);
        let val = |r: Option<&Value>, k: &str| r.and_then(|r| finite(get(r, k))).map_or(Value::Null, fval);
        rows.push(dict(vec![
            ("v1_key", sval(key)),
            ("set", sval(dk.set_of(key))),
            ("dbf1_hardware", Value::Bool(key.contains(&format!("|{RP1_GEOMETRY}|{DBF1_BZ_SHAPE}|")))),
            ("status_p", sval(cmp.status_p.as_str())),
            ("status_c", sval(cmp.status_c.as_str())),
            ("thrust_p_N", val(p, "thrust_N")),
            ("thrust_c_N", val(c, "thrust_N")),
            ("thrust_se_p_N", val(p, "thrust_se_N")),
            ("thrust_se_c_N", val(c, "thrust_se_N")),
            ("discharge_current_p_A", val(p, "discharge_current_A")),
            ("discharge_current_c_A", val(c, "discharge_current_A")),
            ("Id_rms_rel_p", val(p, "Id_rms_rel")),
            ("Id_rms_rel_c", val(c, "Id_rms_rel")),
            ("thrust_avgstate_p_N", val(p, "thrust_avgstate_N")),
            ("C-STATUS", Value::Bool(cmp.c_status)),
            ("C-QUIET", cmp.c_quiet.map_or(Value::Null, Value::Bool)),
            ("rel_thrust", td),
            ("allowance_thrust_rel", ta),
            ("C-T", tb),
            ("rel_discharge_current", id),
            ("allowance_discharge_current_rel", ia),
            ("C-ID", ib),
            ("case_outcome", sval(o.as_str())),
        ]));
        let pct = |x: Option<(f64, f64, bool)>| match x {
            Some((d, a, _)) if d.is_finite() => format!("{:.2} % ({:.2} %)", 100.0 * d, 100.0 * a),
            _ => "-".into(),
        };
        md_rows.push_str(&format!(
            "| `{key}` | {} / {} | {} | {} | {} |\n",
            cmp.status_p.as_str(),
            cmp.status_c.as_str(),
            pct(cmp.thrust),
            pct(cmp.current),
            o.as_str()
        ));
    }
    let outcome = pass_rule(&outcomes);
    let mut status_counts = Vec::new();
    for lv in [Level::P, Level::C] {
        for s in A7Status::ALL {
            let n = keys
                .iter()
                .filter(|k| {
                    let r = recs.get(&format!("{k}|{}", lv.id()));
                    let st = r.map_or(A7Status::NumericalFailure, |r| h7::a7_status(r, by[k.as_str()].mdot_kg_s));
                    st == s
                })
                .count();
            status_counts.push(dict(vec![
                ("level", sval(lv.id())),
                ("status", sval(s.as_str())),
                ("n", Value::int(n as i64)),
            ]));
        }
    }
    let result = dict(vec![
        ("schema", sval(DEMO_RESULT_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("addendum", sval("A7 Hall numerical method: demonstration")),
        (
            "scope",
            sval(match scope {
                Scope::Rp1 => "RP1_SUBSET (demonstration cases on G-RP1; gates Stage 1)",
                Scope::All => "ALL (every demonstration case; gates Stage 2)",
            }),
        ),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(LOCK_SHA256)),
        ("raw_manifest_sha256", sval(&manifest_sha256)),
        ("raw_sha256", sval(&raw_sha)),
        ("rust_commit", sval(rust_commit)),
        ("scored_once", Value::Bool(true)),
        ("tolerance_rel", fval(h7::TOL_REL)),
        ("k_sigma", fval(h7::K_SIGMA)),
        ("se_cap_rel", fval(h7::SE_CAP_REL)),
        ("n_cases", Value::int(keys.len() as i64)),
        ("case_outcome_counts", dict(counts.iter().map(|(k, v)| (*k, Value::int(*v as i64))).collect())),
        ("status_counts", Value::List(status_counts)),
        ("outcome", sval(outcome)),
        ("cases", Value::List(rows)),
    ]);
    let mut page = format!(
        "# NP-HALL-PARAMETRIC-ENVELOPE addendum A7: demonstration result{} (XE)\n\n",
        if scope == Scope::Rp1 { ", RP-1 subset" } else { "" }
    );
    let jname = scope.result_rel().rsplit('/').next().unwrap_or("");
    page.push_str(&format!(
        "`{jname}` is authoritative. PARAMETRIC / NOT_VALIDATED. Scored once from the frozen \
         demonstration (manifest sha256 `{manifest_sha256}`, raw `{raw_sha}`).\n\n**Outcome: {outcome}.** Case outcomes: {}.\n\n\
         | v1 key | status P / C | thrust diff (allowance) | I_d diff (allowance) | case outcome |\n|---|---|---|---|---|\n",
        counts.iter().map(|(k, v)| format!("{k} {v}")).collect::<Vec<_>>().join(", ")
    ));
    page.push_str(&md_rows);
    page.push_str(
        "\nP = 2 x v1 cells, C = 4 x v1 cells, both at 4 x v1 duration with the window from 1 x v1 duration. Allowance = \
         2 % of the check value + 2 x the combined batch-means SE. A case converges when its status class (PASS, \
         NOT_SUSTAINED, UNKNOWN) and quiet class agree and thrust and I_d agree within the allowance; unknown at both \
         levels is a persistent unknown. Demonstrated: no NOT_CONVERGED case and at least one CONVERGED_EVALUATED case.\n",
    );
    Ok((result, page))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn levels_and_pass_rule() {
        assert_eq!(Level::P.id(), "A7-P");
        assert_eq!(Level::C.cell_factor(), 4);
        use CaseOutcome::*;
        assert_eq!(pass_rule(&[ConvergedEvaluated, PersistentUnknown]), OUTCOME_DEMONSTRATED);
        assert_eq!(pass_rule(&[ConvergedEvaluated, NotConverged]), OUTCOME_NOT_DEMONSTRATED);
        assert_eq!(pass_rule(&[PersistentUnknown]), OUTCOME_NOT_DEMONSTRATED);
        assert_eq!(Kind::parse("stage1"), Some(Kind::Grid(GridStage::Stage1)));
        assert_eq!(Kind::DemoRp1.launch_name(), "launch_manifest_a7_demo_rp1_v1.json");
    }
}
