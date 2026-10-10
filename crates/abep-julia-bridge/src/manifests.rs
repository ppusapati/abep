//! P5-N2 launch manifests (port of scripts/make_p5_n2_launch_manifests.py): every follow-on dataset's expected
//! record keys, pinned chemistry, mode and exact driver command lines (4 shards), and the structural gate `check`.
//! Nothing here launches anything or decides a configuration after results.

use abep_hall::py::{self, Dump, PyValue};
use abep_hall::{HallError, HallResult};
use abep_provenance::sha256_hex;

pub const DRIVER: &str = "hallthruster_bridge/campaign/p5_n2_campaign.jl";
pub const CRITERIA_REL: &str = "hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json";
pub const LOCK_REL: &str = "hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json";
pub const ENSEMBLE_REL: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";
pub const CASES_REL: &str = "hallthruster_bridge/cases/p5_n2.json";
pub const MANIFEST_DIR_REL: &str = "hallthruster_bridge/campaign/manifests";
pub const SHARDS: usize = 4;

fn h(repo: &str, rel: &str) -> HallResult<String> {
    Ok(sha256_hex(&py::read_file(&py::join(repo, rel))?))
}

fn strs(v: &PyValue, field: &str) -> HallResult<Vec<String>> {
    py::iterate(v)?.iter().map(|x| Ok(py::py_str(py::getitem(x, field)?))).collect()
}

/// `_inputs()`: (criteria, screening-candidate ids, case ids) in file order.
pub fn inputs(repo: &str) -> HallResult<(PyValue, Vec<String>, Vec<String>)> {
    let crit = py::load_json_file(&py::join(repo, CRITERIA_REL))?;
    let ens = py::load_json_file(&py::join(repo, ENSEMBLE_REL))?;
    let cases = py::load_json_file(&py::join(repo, CASES_REL))?;
    let cands = strs(py::getitem(&ens, "screening_candidates")?, "ensemble_member_id")?;
    let case_ids = strs(py::getitem(&cases, "cases")?, "id")?;
    Ok((crit, cands, case_ids))
}

/// Driver command line of shard `i` (the manifest's `commands` entry, `<out>` left as a placeholder).
pub fn command(mode: &str, shard: usize, chems: &[String]) -> String {
    format!(
        "julia --project=hallthruster_bridge {DRIVER} <out>/s{shard}.jsonl {mode} {shard} {SHARDS} {}",
        chems.join(",")
    )
}

#[allow(clippy::too_many_arguments)]
fn manifest(
    repo: &str,
    name: &str,
    chems: &[String],
    mode: &str,
    role: &str,
    crit: &PyValue,
    cands: &[String],
    cases: &[String],
    extra: Vec<(&'static str, PyValue)>,
) -> HallResult<PyValue> {
    let pins = py::getitem(py::getitem(crit, "inputs_pinned")?, "chemistry_configs_sha256")?;
    let mut keys = Vec::new();
    for cd in cands {
        for ch in chems {
            for cs in cases {
                keys.push(format!("{cd}|{ch}|{cs}|{mode}"));
            }
        }
    }
    keys.sort();
    let mut chemistry = Vec::new();
    for c in chems {
        chemistry.push((py::s(c.as_str()), py::getitem(pins, c)?.clone()));
    }
    let mut m = vec![
        (py::s("name"), py::s(name)),
        (py::s("role"), py::s(role)),
        (py::s("mode"), py::s(mode)),
        (py::s("chemistry"), PyValue::Dict(chemistry)),
        (py::s("n_runs"), PyValue::Int(keys.len() as i128)),
        (py::s("expected_keys"), py::list_of_strs(&keys)),
        (py::s("driver"), py::s(DRIVER)),
        (py::s("driver_sha256"), py::s(h(repo, DRIVER)?)),
        (py::s("prereg_lock_sha256"), py::s(h(repo, LOCK_REL)?)),
        (py::s("commands"), PyValue::List((0..SHARDS).map(|i| py::s(command(mode, i, chems))).collect())),
        (
            py::s("structural_gate"),
            py::s("python scripts/make_p5_n2_launch_manifests.py --check <manifest> <out>/s*.jsonl"),
        ),
    ];
    m.extend(extra.into_iter().map(|(k, v)| (py::s(k), v)));
    Ok(PyValue::Dict(m))
}

fn strip_toml(name: &str) -> String {
    let c: Vec<char> = name.chars().collect();
    c[..c.len().saturating_sub(5)].iter().collect()
}

/// `build()`: every launch manifest, in the script's order.
pub fn build(repo: &str) -> HallResult<Vec<PyValue>> {
    let (crit, cands, cases) = inputs(repo)?;
    let mandatory: Vec<String> =
        py::iterate(py::getitem(&crit, "mandatory_chemistry")?)?.iter().map(py::py_str).collect();
    let mut ms = vec![manifest(
        repo,
        "facility_mandatory",
        &mandatory,
        "facility",
        "secondary consistency evidence; launch after the vacuum promotion result (execution_order)",
        &crit,
        &cands,
        &cases,
        Vec::new(),
    )?];
    let PyValue::Dict(staged) = py::getitem(&crit, "staged_sensitivities")? else {
        return Err(HallError::type_error("staged_sensitivities is not a mapping"));
    };
    for (sens, spec) in staged {
        let sens = py::py_str(sens);
        ms.push(manifest(
            repo,
            &format!("staged_{}", strip_toml(&sens)),
            std::slice::from_ref(&sens),
            "vacuum",
            "O4 first stage (compare with its baseline)",
            &crit,
            &cands,
            &cases,
            vec![("baseline", py::getitem(spec, "baseline")?.clone())],
        )?);
        let PyValue::Dict(esc) = py::getitem(spec, "escalation")? else {
            return Err(HallError::type_error("escalation is not a mapping"));
        };
        for (prim, e) in esc {
            let e = py::py_str(e);
            ms.push(manifest(
                repo,
                &format!("escalation_{}", strip_toml(&e)),
                std::slice::from_ref(&e),
                "vacuum",
                &format!("O4 escalation of {sens}: launch only if its trigger fires"),
                &crit,
                &cands,
                &cases,
                vec![("compare_with", prim.clone()), ("sensitivity", py::s(sens.as_str()))],
            )?);
        }
    }
    Ok(ms)
}

/// The bytes the script writes for one manifest: `json.dump(m, f, indent=1)` (no trailing newline).
pub fn to_json_bytes(m: &PyValue) -> Vec<u8> {
    py::dumps(m, &Dump::indented(1)).into_bytes()
}

pub fn name_of(m: &PyValue) -> HallResult<String> {
    Ok(py::py_str(py::getitem(m, "name")?))
}

/// A committed manifest by name.
pub fn load_committed(repo: &str, name: &str) -> HallResult<PyValue> {
    py::load_json_file(&py::join(&py::join(repo, MANIFEST_DIR_REL), &format!("{name}.json")))
}

/// `[(first occurrence order) k for k, n in Counter(items).items() if n > 1]`.
fn duplicates(items: &[PyValue]) -> Vec<PyValue> {
    let mut seen: Vec<(PyValue, usize)> = Vec::new();
    for x in items {
        match seen.iter_mut().find(|(k, _)| k.py_eq(x)) {
            Some(slot) => slot.1 += 1,
            None => seen.push((x.clone(), 1)),
        }
    }
    seen.into_iter().filter(|(_, n)| *n > 1).map(|(k, _)| k).collect()
}

/// `check(man, paths)`: the structural gate of a dataset (keys, mode, smoke, lock hash, HallThruster commit, return
/// codes counted only). `bridge_dir` holds the PINNED.toml read for the commit.
pub fn check(man: &PyValue, paths: &[String], bridge_dir: &str) -> HallResult<PyValue> {
    let pin = crate::pin::load_toml(&py::join(bridge_dir, "PINNED.toml"))?;
    let commit = if py::contains(&pin, &py::s("commit"))? {
        py::getitem(&pin, "commit")?.clone()
    } else {
        py::getitem(py::getitem(&pin, "hallthruster")?, "commit")?.clone()
    };
    let mut recs = Vec::new();
    for p in paths {
        for line in py::read_text(p)?.split_inclusive('\n') {
            if !py::py_strip(line).is_empty() {
                recs.push(py::load_json_bytes(line.as_bytes())?);
            }
        }
    }
    let mut keys = Vec::new();
    for r in &recs {
        keys.push(py::getitem(r, "key")?.clone());
    }
    let got = py::set_from(keys.clone())?;
    let exp = py::set_from(py::iterate(py::getitem(man, "expected_keys")?)?)?;
    let missing: Vec<PyValue> = exp.iter().filter(|k| !got.iter().any(|g| g.py_eq(k))).cloned().collect();
    let unexpected: Vec<PyValue> = got.iter().filter(|k| !exp.iter().any(|e| e.py_eq(k))).cloned().collect();
    let dups = duplicates(&keys);
    let field_eq = |r: &PyValue, f: &str, want: &PyValue| -> HallResult<bool> {
        Ok(py::get(r, f)?.unwrap_or(&PyValue::None).py_eq(want))
    };
    let mut mode_ok = true;
    let mut smoke_false = true;
    let mut lock_ok = true;
    let mut commit_ok = true;
    let mut counts: Vec<(PyValue, PyValue)> = Vec::new();
    for r in &recs {
        mode_ok &= field_eq(r, "mode", py::getitem(man, "mode")?)?;
        smoke_false &= matches!(py::get(r, "smoke")?, Some(PyValue::Bool(false)));
        lock_ok &= field_eq(r, "prereg_lock_sha256", py::getitem(man, "prereg_lock_sha256")?)?;
        commit_ok &= field_eq(r, "hallthruster_commit", &commit)?;
        let label = if field_eq(r, "retcode", &py::s("success"))? { "success" } else { "non-success" };
        match counts.iter_mut().find(|(k, _)| k.py_eq(&py::s(label))) {
            Some((_, PyValue::Int(n))) => *n += 1,
            _ => counts.push((py::s(label), PyValue::Int(1))),
        }
    }
    let pass = recs.len() == exp.len()
        && dups.is_empty()
        && missing.is_empty()
        && unexpected.is_empty()
        && mode_ok
        && smoke_false
        && lock_ok
        && commit_ok;
    Ok(PyValue::Dict(vec![
        (py::s("n_records"), PyValue::Int(recs.len() as i128)),
        (py::s("n_expected"), PyValue::Int(exp.len() as i128)),
        (py::s("duplicates"), PyValue::List(dups)),
        (py::s("missing"), PyValue::List(py::sorted(missing)?)),
        (py::s("unexpected"), PyValue::List(py::sorted(unexpected)?)),
        (py::s("mode_ok"), PyValue::Bool(mode_ok)),
        (py::s("smoke_false"), PyValue::Bool(smoke_false)),
        (py::s("lock_hash_ok"), PyValue::Bool(lock_ok)),
        (py::s("hallthruster_commit_ok"), PyValue::Bool(commit_ok)),
        (py::s("retcode_counts"), PyValue::Dict(counts)),
        (py::s("PASS"), PyValue::Bool(pass)),
    ]))
}
