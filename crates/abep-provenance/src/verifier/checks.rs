//! `check_prereg_lock`, `check_audit_manifest` and `check_hallthruster_pin` of `scripts/ci_checks.py`.

use super::load::{abs_path, is_file, load_json, load_toml};
use super::pyvalue::PyValue;
use super::sha_map::{verify_pairs, verify_pins};
use super::{Finding, FindingKind, Py, Raised};
use std::path::Path;

const BR: &str = "hallthruster_bridge";
const PROP: &str = "hallthruster_bridge/propellants";
const LOCK: &str = "hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json";
const CRITERIA: &str = "hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json";
const AUDIT_DIR: &str = "hallthruster_bridge/audit/configs";
const AUDIT_MANIFEST: &str = "hallthruster_bridge/audit/configs/MANIFEST.json";
const PINNED: &str = "hallthruster_bridge/PINNED.toml";
const JULIA_MANIFEST: &str = "hallthruster_bridge/Manifest.toml";
const JULIA_PROJECT: &str = "hallthruster_bridge/Project.toml";

fn get_or(v: &PyValue, key: &str, default: PyValue) -> Py<PyValue> {
    Ok(v.get(key)?.unwrap_or(default))
}

fn empty_dict() -> PyValue {
    PyValue::Dict(Vec::new())
}

/// The P5-N2 prereg lock: every locked file, the criteria's pinned inputs and chemistry configs match their sha256, and
/// every mandatory chemistry config is pinned.
pub(crate) fn prereg_lock(root: &Path) -> Py<(Vec<Finding>, String)> {
    let lock = load_json(root, LOCK)?;
    let files = lock.get("files")?.unwrap_or(PyValue::None);
    if !files.truthy() {
        return Ok((
            vec![Finding::new(FindingKind::EmptyPinSet, LOCK, "files", "prereg lock lists no files")],
            String::new(),
        ));
    }
    let mut bad = verify_pins(root, BR, &files, "prereg lock")?;
    let crit = load_json(root, CRITERIA)?;
    let pin = crit.getitem_str("inputs_pinned")?;
    for k in ["measurement_audit", "cases", "transport_candidates"] {
        let file = pin.getitem_str(k)?.getitem_str("file")?;
        let sha = pin.getitem_str(k)?.getitem_str("sha256")?;
        file.hashable().then_some(()).ok_or_else(|| Raised::type_error("unhashable type"))?;
        bad.extend(verify_pairs(root, BR, &[(file, sha)], &format!("criteria inputs_pinned.{k}"))?);
    }
    let chem = pin.getitem_str("chemistry_configs_sha256")?;
    bad.extend(verify_pins(root, PROP, &chem, "criteria chemistry_configs_sha256")?);
    for c in get_or(&crit, "mandatory_chemistry", PyValue::List(Vec::new()))?.iterate()? {
        if !chem.contains(&c)? {
            let name = c.py_str();
            bad.push(Finding::new(
                FindingKind::Unpinned,
                CRITERIA,
                name.clone(),
                format!("mandatory chemistry {name} has no pinned sha256"),
            ));
        }
    }
    let note =
        format!("{} locked files, 3 pinned inputs, {} pinned chemistry configs", files.py_len()?, chem.py_len()?);
    Ok((bad, note))
}

/// `set.add(x)` on a first-seen-order vector.
fn py_set_add(mut set: Vec<PyValue>, x: PyValue) -> Py<Vec<PyValue>> {
    if !x.hashable() {
        return Err(Raised::type_error(format!("unhashable type: '{}'", x.type_name())));
    }
    if !set.iter().any(|y| y.py_eq(&x)) {
        set.push(x);
    }
    Ok(set)
}

/// `set(items)`.
fn py_set(items: Vec<PyValue>) -> Py<Vec<PyValue>> {
    items.into_iter().try_fold(Vec::new(), py_set_add)
}

/// `sorted(a ^ b)`.
fn sorted_symmetric_difference(a: &[PyValue], b: &[PyValue]) -> Py<Vec<PyValue>> {
    let mut diff: Vec<PyValue> = a.iter().filter(|x| !b.iter().any(|y| y.py_eq(x))).cloned().collect();
    diff.extend(b.iter().filter(|y| !a.iter().any(|x| x.py_eq(y))).cloned());
    if diff.iter().all(|x| matches!(x, PyValue::Str(_))) {
        diff.sort_by_key(PyValue::py_str);
    } else if diff.iter().all(PyValue::is_number) {
        let mut keyed: Vec<(f64, PyValue)> = diff.into_iter().map(|x| (x.py_float().unwrap_or(f64::NAN), x)).collect();
        keyed.sort_by(|x, y| x.0.partial_cmp(&y.0).unwrap_or(std::cmp::Ordering::Equal));
        diff = keyed.into_iter().map(|(_, x)| x).collect();
    } else {
        return Err(Raised::type_error("'<' not supported between instances of mixed types"));
    }
    Ok(diff)
}

/// The immutable audit configuration snapshots: snapshot sha256, rate-file set and rate-table sha256 of every config,
/// and the case-file snapshots.
pub(crate) fn audit_manifest(root: &Path) -> Py<(Vec<Finding>, String)> {
    let man = load_json(root, AUDIT_MANIFEST)?;
    let mut bad = Vec::new();
    if !man.get("configs")?.unwrap_or(PyValue::None).truthy() {
        bad.push(Finding::new(FindingKind::EmptyPinSet, AUDIT_MANIFEST, "configs", "MANIFEST lists no configs"));
    }
    let mut n_tables = 0usize;
    let configs = get_or(&man, "configs", empty_dict())?.items()?;
    for (f, m) in &configs {
        let sha = m.getitem_str("sha256")?;
        bad.extend(verify_pairs(root, AUDIT_DIR, &[(f.clone(), sha)], "audit snapshot")?);
        let f = match f {
            PyValue::Str(s) => s.clone(),
            other => return Err(Raised::type_error(format!("expected str, got {}", other.type_name()))),
        };
        if !is_file(&abs_path(root, AUDIT_DIR).join(&f)) {
            continue;
        }
        let snapshot = load_toml(root, &format!("{AUDIT_DIR}/{f}"))?;
        let mut used = Vec::new();
        for r in get_or(&snapshot, "reactions", PyValue::List(Vec::new()))?.iterate()? {
            used = py_set_add(used, r.getitem_str("rate_coeff_file")?)?;
        }
        let listed = py_set(m.getitem_str("rate_files")?.iterate()?)?;
        let same = used.len() == listed.len() && used.iter().all(|x| listed.iter().any(|y| y.py_eq(x)));
        if !same {
            let diff = PyValue::List(sorted_symmetric_difference(&used, &listed)?);
            let key = diff.to_compact_json();
            bad.push(Finding::new(
                FindingKind::SetMismatch,
                super::join_norm(AUDIT_DIR, &f),
                key.clone(),
                format!("audit snapshot {f}: rate files {key} differ between snapshot and MANIFEST"),
            ));
        }
        let rate_files = m.getitem_str("rate_files")?;
        bad.extend(verify_pins(root, PROP, &rate_files, &format!("audit snapshot {f} rate table"))?);
        n_tables += rate_files.py_len()?;
    }
    let cases = get_or(&man, "case_files", empty_dict())?.items()?;
    for (f, m) in &cases {
        let sha = m.getitem_str("sha256")?;
        bad.extend(verify_pairs(root, AUDIT_DIR, &[(f.clone(), sha)], "audit case snapshot")?);
    }
    let note = format!(
        "{} config snapshots, {n_tables} pinned rate-table references, {} case snapshots",
        configs.len(),
        cases.len()
    );
    Ok((bad, note))
}

/// HallThruster.jl pin: PINNED.toml commit / version / repository == the Manifest.toml HallThruster entry, and the
/// Project.toml compat bound is `=<version>`.
pub(crate) fn hallthruster_pin(root: &Path) -> Py<(Vec<Finding>, String)> {
    let pin = load_toml(root, PINNED)?.getitem_str("hallthruster")?;
    let man = load_toml(root, JULIA_MANIFEST)?;
    let proj = load_toml(root, JULIA_PROJECT)?;
    let entries = get_or(&get_or(&man, "deps", empty_dict())?, "HallThruster", PyValue::List(Vec::new()))?;
    let n = entries.py_len()?;
    if n != 1 {
        return Ok((
            vec![Finding::new(
                FindingKind::EntryCount,
                JULIA_MANIFEST,
                "deps.HallThruster",
                format!("Manifest.toml has {n} HallThruster entries (expected 1)"),
            )],
            String::new(),
        ));
    }
    let e = entries.getitem(&PyValue::Int(0))?;
    let mut bad = Vec::new();
    for (mkey, pkey) in [("repo-rev", "commit"), ("version", "version"), ("repo-url", "repository")] {
        let got = e.get(mkey)?.unwrap_or(PyValue::None);
        let want = pin.getitem_str(pkey)?;
        if !got.py_eq(&want) {
            bad.push(Finding::new(
                FindingKind::ValueMismatch,
                JULIA_MANIFEST,
                mkey,
                format!("Manifest.toml HallThruster {mkey} {} != PINNED.toml {pkey} {}", got.py_str(), want.py_str()),
            ));
        }
    }
    let compat = get_or(&proj, "compat", empty_dict())?.get("HallThruster")?.unwrap_or(PyValue::None);
    let version = match pin.getitem_str("version")? {
        PyValue::Str(s) => s,
        other => {
            return Err(Raised::type_error(format!("can only concatenate str (not \"{}\") to str", other.type_name())))
        }
    };
    if !compat.py_eq(&PyValue::Str(format!("={version}"))) {
        bad.push(Finding::new(
            FindingKind::ValueMismatch,
            JULIA_PROJECT,
            "compat.HallThruster",
            format!("Project.toml compat HallThruster {} != '={version}'", compat.py_str()),
        ));
    }
    let commit = match pin.getitem_str("commit")? {
        PyValue::Str(s) => s.chars().take(12).collect::<String>(),
        PyValue::List(_) => String::from("<list>"),
        other => return Err(Raised::type_error(format!("'{}' object is not subscriptable", other.type_name()))),
    };
    Ok((bad, format!("HallThruster.jl {version} @ {commit}")))
}
