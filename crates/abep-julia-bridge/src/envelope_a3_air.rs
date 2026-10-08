//! NP-HALL-PARAMETRIC-ENVELOPE addendum A3 (numerics adequacy, RG-04), AIR scope: the same seeded rule, refinements,
//! criteria and outcome as the XE check, applied to the AIR family of addendum A1 (seed texts with family AIR, the
//! composition corner picked by the seed), run through the A1 AIR bridge (`air_bridge_lib.jl` run_case_air) under the
//! committed A1 AIR launch manifest (LP-BOUNDED BV-AIR-LL-NOM today). AIR results are information only (A1).

use crate::air_cases::{AIR_BRIDGE_LIB_REL, AIR_CASES_REL, AIR_LAUNCH_MANIFEST_REL};
use crate::envelope_a3::{self as a3, Spec, A3_LOCK_REL, A3_LOCK_SHA256, A3_SHARDS, ADDENDUM_REL, ADDENDUM_SHA256};
use crate::envelope_cases::{self as ec, BRIDGE_LIB_REL, THREAD_PIN};
use crate::jobs::{child_env, JobSpec, ThreadSettings};
use abep_hall::envelope::{self as env, Family, RunStatus, F_OUT_TOL};
use abep_provenance::{read_verified, sha256_file, sha256_hex};
use abep_types::pyjson::{self, Dict, DumpOptions, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

pub const A3_AIR_CASES_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/cases/h1_parametric_envelope_a3_numerics_air_cases_v1.json";
pub const A3_AIR_LAUNCH_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/launch_manifest_a3_numerics_air_v1.json";
pub const A3_AIR_DRIVER_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/driver/h1_envelope_a3_air_driver.jl";
pub const A3_AIR_CASES_SCHEMA: &str = "np_hall_parametric_envelope_a3_numerics_air_cases_v1";
pub const A3_AIR_LAUNCH_SCHEMA: &str = "np_hall_parametric_envelope_a3_numerics_air_launch_manifest_v1";
pub const A3_AIR_RAW_SCHEMA: &str = "np_hall_parametric_envelope_a3_numerics_air_raw_manifest_v1";
pub const A3_AIR_CONTRACT_ID: &str = "NP-HALL-PARAMETRIC-ENVELOPE-A3-NUMERICS-AIR-V1";
/// Record fields that must equal the A1 AIR launch manifest (A1 run_status_rule.record_rejection).
pub const AIR_RECORD_PINS: [&str; 7] = [
    "air_label",
    "air_pinned_sha256",
    "air_config_sha256",
    "chemistry_mode",
    "chemistry_bound_set",
    "chemistry_bound_member",
    "chemistry_bound_label",
];

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

fn get<'a>(v: &'a Value, k: &str) -> Option<&'a Value> {
    v.as_dict().and_then(|d| d.get(k))
}

fn get_str<'a>(v: &'a Value, k: &str, label: &str) -> AbepResult<&'a str> {
    get(v, k).and_then(Value::as_str).ok_or_else(|| schema(label, format!("{k} missing or not a string")))
}

fn loads(bytes: &[u8], label: &str) -> AbepResult<Value> {
    let text = std::str::from_utf8(bytes).map_err(|e| schema(label, e.to_string()))?;
    pyjson::loads(text).map_err(|e| schema(label, e.to_string()))
}

fn dict(pairs: Vec<(&str, Value)>) -> Value {
    let mut d = Dict::new();
    for (k, v) in pairs {
        d.insert(k, v);
    }
    Value::Dict(d)
}

fn small(v: Option<&Value>) -> bool {
    v.and_then(|x| x.to_f64().ok()).is_some_and(|f| f.is_finite() && f <= F_OUT_TOL)
}

/// The A1 AIR run-status rule: v1 NUMERICAL_FAILURE / NOT_SUSTAINED, OUT_OF_DOMAIN by DOM-AIR-01 (unresolved table, or any
/// per-reaction extrapolated fraction null or > 1e-12) or DOM-AIR-02 (audit_domain_fraction_max null or > 1e-12).
pub fn air_run_status(rec: &Value) -> RunStatus {
    let s = env::run_status(Family::Xe, rec);
    if s == RunStatus::NumericalFailure {
        return s;
    }
    let unresolved_ok = matches!(get(rec, "chemistry_unresolved_rate_files"), Some(Value::List(l)) if l.is_empty());
    let per_ok = match get(rec, "chemistry_per_reaction") {
        Some(Value::List(l)) if !l.is_empty() => l.iter().all(|r| small(get(r, "extrapolated_fraction"))),
        _ => false,
    };
    if !(unresolved_ok && per_ok && small(get(rec, "audit_domain_fraction_max"))) {
        return RunStatus::OutOfDomain;
    }
    s
}

pub const AIR: Spec = Spec {
    family: "AIR",
    cases_rel: A3_AIR_CASES_REL,
    launch_rel: A3_AIR_LAUNCH_REL,
    driver_rel: A3_AIR_DRIVER_REL,
    raw_schema: A3_AIR_RAW_SCHEMA,
    shard_prefix: "a3air_s",
    frozen_by: "abep-h1-envelope-a3 freeze --family AIR",
    status: air_run_status,
};

/// The committed A1 AIR launch manifest (the launch gate must be open) and its sha256.
pub fn air_launch(repo: &Path) -> AbepResult<(Value, String)> {
    let bytes = std::fs::read(repo.join(AIR_LAUNCH_MANIFEST_REL)).map_err(|e| AbepError::IncompleteEvidence {
        message: format!("no AIR launch manifest (A1 launch gate closed): {e}"),
    })?;
    Ok((loads(&bytes, AIR_LAUNCH_MANIFEST_REL)?, sha256_hex(&bytes)))
}

/// The AIR check set (addendum A3 scope.AIR) and the A3 AIR case-file document.
pub fn build_case_doc(repo: &Path) -> AbepResult<Value> {
    a3::load_addendum(repo)?;
    let (_, cs, cells) = a3::v1_case_set_and_cells(repo)?;
    let (lm, lm_sha) = air_launch(repo)?;
    let cases_sha = get_str(&lm, "cases_sha256", AIR_LAUNCH_MANIFEST_REL)?;
    let doc = loads(&read_verified(&repo.join(AIR_CASES_REL), cases_sha)?, AIR_CASES_REL)?;
    // composition corners in the A1 corner order, as the AIR case file records them
    let comps: Vec<String> = get(&doc, "composition_points")
        .and_then(Value::as_list)
        .ok_or_else(|| schema(AIR_CASES_REL, "composition_points"))?
        .iter()
        .map(|p| Ok(get_str(p, "id", AIR_CASES_REL)?.to_string()))
        .collect::<AbepResult<_>>()?;
    let sel = a3::select_check_set_as(&cs, Family::N2Proxy, "AIR", Some(&comps), &cells)?;
    let mut by_key: BTreeMap<&str, &Value> = BTreeMap::new();
    for c in get(&doc, "cases").and_then(Value::as_list).ok_or_else(|| schema(AIR_CASES_REL, "cases"))? {
        by_key.insert(get_str(c, "key", AIR_CASES_REL)?, c);
    }
    let mut out = Vec::new();
    for c in &sel {
        let base =
            by_key.get(c.key.as_str()).ok_or_else(|| model(format!("check case {} not in the AIR file", c.key)))?;
        out.extend(a3::refine(base, c, AIR_CASES_REL)?);
    }
    Ok(dict(vec![
        ("schema", sval(A3_AIR_CASES_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("addendum", sval("A3 numerics adequacy (RG-04), AIR scope by reference")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(A3_LOCK_SHA256)),
        ("air_cases_sha256", sval(cases_sha)),
        ("air_launch_manifest_sha256", sval(&lm_sha)),
        ("chemistry_mode", sval(get_str(&lm, "chemistry_mode", AIR_LAUNCH_MANIFEST_REL)?)),
        ("seed", sval(a3::SEED)),
        ("refinements", Value::List(a3::REFINEMENTS.iter().map(|r| sval(r)).collect())),
        (
            "generated_by",
            sval("abep-h1-envelope-a3 generate --family AIR (crates/abep-julia-bridge/src/envelope_a3_air.rs)"),
        ),
        ("n_cases", Value::int(out.len() as i64)),
        ("cases", Value::List(out)),
    ]))
}

/// The A3 AIR launch manifest of a rendered A3 AIR case file.
pub fn build_launch_manifest(repo: &Path, cases_text: &str, n: usize) -> AbepResult<Value> {
    let (_, lm_sha) = air_launch(repo)?;
    let sha = |rel: &str| sha256_file(&repo.join(rel));
    Ok(dict(vec![
        ("schema", sval(A3_AIR_LAUNCH_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("addendum_sha256", sval(ADDENDUM_SHA256)),
        ("addendum_lock_sha256", sval(A3_LOCK_SHA256)),
        ("air_launch_manifest", sval(AIR_LAUNCH_MANIFEST_REL)),
        ("air_launch_manifest_sha256", sval(&lm_sha)),
        ("cases", sval(A3_AIR_CASES_REL)),
        ("cases_sha256", sval(&sha256_hex(cases_text.as_bytes()))),
        ("driver", sval(A3_AIR_DRIVER_REL)),
        ("driver_sha256", sval(&sha(A3_AIR_DRIVER_REL)?)),
        ("n_cases", Value::int(n as i64)),
        ("n_shards", Value::int(A3_SHARDS as i64)),
        ("shard_rule", sval("case index i (0-based, file order) belongs to shard i mod n_shards")),
        ("thread_env", dict(THREAD_PIN.iter().map(|(k, v)| (*k, sval(v))).collect())),
        ("mode", sval("vacuum")),
    ]))
}

pub fn generate(repo: &Path) -> AbepResult<(String, String)> {
    let doc = build_case_doc(repo)?;
    let text = ec::render_case_doc(&doc)?;
    let n = get(&doc, "cases").and_then(Value::as_list).map_or(0, <[Value]>::len);
    let lm = build_launch_manifest(repo, &text, n)?;
    let mut lm_text = pyjson::dumps(&lm, &DumpOptions::config_writer()).map_err(|e| model(e.to_string()))?;
    lm_text.push('\n');
    Ok((text, lm_text))
}

pub fn write_generated(repo: &Path) -> AbepResult<()> {
    let (cases, lm) = generate(repo)?;
    for (rel, t) in [(A3_AIR_CASES_REL, &cases), (A3_AIR_LAUNCH_REL, &lm)] {
        std::fs::write(repo.join(rel), t).map_err(|e| io(rel, e))?;
    }
    Ok(())
}

pub fn check(repo: &Path) -> AbepResult<usize> {
    let (cases, lm) = generate(repo)?;
    for (rel, t) in [(A3_AIR_CASES_REL, &cases), (A3_AIR_LAUNCH_REL, &lm)] {
        let have = std::fs::read(repo.join(rel)).map_err(|e| io(rel, e))?;
        if have != t.as_bytes() {
            return Err(model(format!("{rel} differs from its deterministic regeneration")));
        }
    }
    let doc = loads(cases.as_bytes(), A3_AIR_CASES_REL)?;
    Ok(get(&doc, "cases").and_then(Value::as_list).map_or(0, <[Value]>::len))
}

/// The A3 AIR shard job: the A3 AIR driver and case file, the A3 lock, the A1 AIR launch manifest and every file it pins.
pub fn shard_job(
    repo: &Path,
    shard: usize,
    out_dir: &str,
    lookup: &dyn Fn(&str) -> Option<String>,
) -> AbepResult<JobSpec> {
    if shard >= A3_SHARDS {
        return Err(model(format!("shard {shard} outside 0..{A3_SHARDS}")));
    }
    let lm =
        loads(&std::fs::read(repo.join(A3_AIR_LAUNCH_REL)).map_err(|e| io(A3_AIR_LAUNCH_REL, e))?, A3_AIR_LAUNCH_REL)?;
    let s = |k: &str| -> AbepResult<String> { Ok(get_str(&lm, k, A3_AIR_LAUNCH_REL)?.to_string()) };
    let (air_lm, _) = air_launch(repo)?;
    let a = |k: &str| -> AbepResult<String> { Ok(get_str(&air_lm, k, AIR_LAUNCH_MANIFEST_REL)?.to_string()) };
    let out = format!("{out_dir}/a3air_s{shard:02}.jsonl");
    let threads = ThreadSettings::pinned(THREAD_PIN);
    let mut inputs = vec![
        (A3_AIR_DRIVER_REL.to_string(), s("driver_sha256")?),
        (A3_AIR_CASES_REL.to_string(), s("cases_sha256")?),
        (A3_LOCK_REL.to_string(), A3_LOCK_SHA256.to_string()),
        (ADDENDUM_REL.to_string(), ADDENDUM_SHA256.to_string()),
        (AIR_LAUNCH_MANIFEST_REL.to_string(), s("air_launch_manifest_sha256")?),
        (AIR_CASES_REL.to_string(), a("cases_sha256")?),
        (AIR_BRIDGE_LIB_REL.to_string(), a("air_bridge_lib_sha256")?),
        (BRIDGE_LIB_REL.to_string(), a("bridge_lib_sha256")?),
        ("hallthruster_bridge/propellants_air/AIR_PINNED.toml".to_string(), a("air_pinned_sha256")?),
        (format!("hallthruster_bridge/{}", a("air_config")?), a("air_config_sha256")?),
        ("hallthruster_bridge/propellants_air/rate_validity.toml".to_string(), a("rate_validity_sha256")?),
    ];
    if let Some(Value::Dict(rf)) = get(&air_lm, "rate_files") {
        for (f, h) in rf.iter() {
            let h = h.as_str().ok_or_else(|| schema(AIR_LAUNCH_MANIFEST_REL, f.clone()))?;
            inputs.push((
                Path::new("hallthruster_bridge/propellants_air").join(f).to_string_lossy().to_string(),
                h.to_string(),
            ));
        }
    }
    Ok(JobSpec {
        program: "julia".into(),
        args: vec![
            "--project=hallthruster_bridge".into(),
            A3_AIR_DRIVER_REL.into(),
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

pub fn run_shard(repo: &Path, shard: usize, out_dir: &str) -> AbepResult<crate::sidecar::JuliaRunSidecar> {
    let lookup = |k: &str| std::env::var(k).ok();
    let job = shard_job(repo, shard, out_dir, &lookup)?;
    crate::launch::launch(&repo.to_string_lossy(), &job, A3_AIR_CONTRACT_ID)
}

pub fn freeze(repo: &Path, name: &str, shards: &[PathBuf], out_dir: &Path) -> AbepResult<(PathBuf, String)> {
    a3::freeze_with(repo, &AIR, name, shards, out_dir)
}

/// The A1 record pins every AIR A3 record must carry (from the committed AIR launch manifest).
pub fn record_pins(repo: &Path) -> AbepResult<Vec<(String, String)>> {
    let (lm, _) = air_launch(repo)?;
    let mut v = Vec::new();
    for k in AIR_RECORD_PINS {
        let have = match k {
            "air_config_sha256" | "air_pinned_sha256" | "air_label" | "chemistry_mode" => {
                Some(get_str(&lm, k, AIR_LAUNCH_MANIFEST_REL)?.to_string())
            }
            _ => get(&lm, k).and_then(Value::as_str).map(str::to_string),
        };
        if let Some(x) = have {
            v.push((k.to_string(), x));
        }
    }
    Ok(v)
}

pub fn score(repo: &Path, manifest: &Path, manifest_sha256: &str, rust_commit: &str) -> AbepResult<(Value, String)> {
    let pins = record_pins(repo)?;
    a3::score_with(repo, &AIR, &pins, manifest, manifest_sha256, rust_commit)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(extra: Vec<(&str, Value)>) -> Value {
        let mut d = Dict::new();
        for (k, v) in [
            ("retcode", sval("success")),
            ("converged", Value::Bool(true)),
            ("finite", Value::Bool(true)),
            ("sustained", Value::Bool(true)),
            ("thrust_N", Value::Float(0.01)),
            ("discharge_current_A", Value::Float(2.0)),
            ("discharge_power_W", Value::Float(600.0)),
        ] {
            d.insert(k, v);
        }
        for (k, v) in extra {
            d.insert(k, v);
        }
        Value::Dict(d)
    }

    fn chem(f: f64, audit: Option<f64>) -> Vec<(&'static str, Value)> {
        let mut r = Dict::new();
        r.insert("extrapolated_fraction", Value::Float(f));
        let mut v = vec![
            ("chemistry_unresolved_rate_files", Value::List(vec![])),
            ("chemistry_per_reaction", Value::List(vec![Value::Dict(r)])),
        ];
        if let Some(a) = audit {
            v.push(("audit_domain_fraction_max", Value::Float(a)));
        }
        v
    }

    #[test]
    fn air_status_rule() {
        assert_eq!(air_run_status(&rec(chem(0.0, Some(0.0)))), RunStatus::Pass);
        assert_eq!(air_run_status(&rec(chem(2e-12, Some(0.0)))), RunStatus::OutOfDomain, "DOM-AIR-01");
        assert_eq!(air_run_status(&rec(chem(0.0, Some(1e-3)))), RunStatus::OutOfDomain, "DOM-AIR-02");
        assert_eq!(air_run_status(&rec(chem(0.0, None))), RunStatus::OutOfDomain, "null audit fraction");
        assert_eq!(air_run_status(&rec(vec![])), RunStatus::OutOfDomain, "no chemistry record");
        let mut ns = chem(0.0, Some(0.0));
        ns.push(("sustained", Value::Bool(false)));
        assert_eq!(air_run_status(&rec(ns)), RunStatus::NotSustained);
        let mut nf = chem(0.0, Some(0.0));
        nf.push(("retcode", sval("failure")));
        assert_eq!(air_run_status(&rec(nf)), RunStatus::NumericalFailure);
    }
}
