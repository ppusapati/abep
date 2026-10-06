//! Immutable, append-only registry of design Hall maps (port of abep_sim/hallmap_registry.py; record format
//! `schemas/hallmap/hallmap_registry_v1.json`).
//!
//! A REGISTRATION record binds by sha256 every file a design Hall map depends on and must name an ADMITTED member
//! (screening candidates are refused); a WITHDRAWAL retires one. Records form a hash chain and are created exclusively
//! (hard link of a fully written, read-only temporary file), never edited or overwritten. `verify` re-hashes every
//! bound file and re-checks the pin and the member's admission against the current repository. No admitted member
//! exists today (credible set EMPTY), so `register` refuses every real member id.

use crate::ensemble;
use crate::error::{HallError, HallResult, Kind};
use crate::hall_map;
use crate::py::{self, Dump, PyValue};
use abep_provenance::sha256_hex;
use std::io::{Read, Write};

pub const RECORD_SCHEMA: &str = "hallmap_registry_record_v1";
pub const MAP_SCHEMAS: [&str; 2] = ["hall_map_schema_v1", "hall_map_schema_v2"];
pub const KINDS: [&str; 2] = ["REGISTRATION", "WITHDRAWAL"];
pub const RECORDS_SUBDIR: &str = "records";
pub const SCHEMA_V2_REL: &str = "schemas/hallmap/hall_map_schema_v2.json";

pub const REGISTRATION_KEYS: [&str; 16] = [
    "schema",
    "kind",
    "seq",
    "prev_record_sha256",
    "registered_utc",
    "registered_by",
    "map",
    "raw_records",
    "ensemble_member",
    "chemistry",
    "hallthruster",
    "geometry",
    "magnetic_field",
    "convergence_prereg",
    "o4_dispositions",
    "admission_decision",
];
pub const WITHDRAWAL_KEYS: [&str; 9] = [
    "schema",
    "kind",
    "seq",
    "prev_record_sha256",
    "registered_utc",
    "registered_by",
    "withdraws_record_sha256",
    "reason",
    "decision",
];
pub const BLOCK_KEYS: [(&str, &[&str]); 11] = [
    ("map", &["file", "sha256", "schema_version", "map_meta_sha256"]),
    ("raw_records", &["file", "sha256", "sha256_canonical_jsonl"]),
    ("ensemble_member", &["ensemble_member_id", "ensemble_file", "ensemble_sha256_at_registration"]),
    ("chemistry", &["config_id", "file", "sha256"]),
    ("hallthruster", &["commit", "pinned_toml_sha256_at_registration"]),
    ("geometry", &["id", "file", "sha256"]),
    ("magnetic_field", &["id", "file", "sha256"]),
    ("convergence_prereg", &["id", "file", "sha256"]),
    ("o4_dispositions", &["file", "sha256"]),
    ("admission_decision", &["file", "sha256"]),
    ("decision", &["file", "sha256"]),
];
/// Blocks whose file `verify` re-hashes (the ensemble file and PINNED.toml are living files; their currency is
/// re-checked instead).
pub const REHASHED_BLOCKS: [&str; 8] = [
    "map",
    "raw_records",
    "chemistry",
    "geometry",
    "magnetic_field",
    "convergence_prereg",
    "o4_dispositions",
    "admission_decision",
];
/// (registry path, meta.provenance path) pairs that must agree.
pub const PROVENANCE_EQUALITIES: [(&str, &str); 10] = [
    ("map.schema_version", "hall_map_schema.name"),
    ("ensemble_member.ensemble_member_id", "ensemble_member.ensemble_member_id"),
    ("hallthruster.commit", "hallthruster.pinned_commit"),
    ("hallthruster.commit", "hallthruster.installed_commit"),
    ("geometry.sha256", "geometry.sha256"),
    ("magnetic_field.sha256", "magnetic_field.sha256"),
    ("convergence_prereg.sha256", "numerics.convergence.prereg_sha256"),
    ("admission_decision.sha256", "ensemble_member.admission.decision_sha256"),
    ("o4_dispositions.sha256", "ensemble_member.admission.o4_dispositions_sha256"),
    ("raw_records.sha256_canonical_jsonl", "raw_records.sha256_canonical_jsonl"),
];

fn rerr(message: impl Into<String>) -> HallError {
    HallError::registry(message)
}

fn is_hex(s: &str, n: usize) -> bool {
    s.len() == n && s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn is_utc(s: &str) -> bool {
    let b = s.as_bytes();
    b.len() == 20
        && b.iter().enumerate().all(|(i, c)| match i {
            4 | 7 => *c == b'-',
            10 => *c == b'T',
            13 | 16 => *c == b':',
            19 => *c == b'Z',
            _ => c.is_ascii_digit(),
        })
}

/// `^(\d{6})_([0-9a-f]{16})\.json$`: (seq, sha prefix).
fn record_name(name: &str) -> Option<(usize, &str)> {
    let stem = name.strip_suffix(".json")?;
    let (seq, sha) = stem.split_once('_')?;
    (seq.len() == 6 && seq.bytes().all(|b| b.is_ascii_digit()) && is_hex(sha, 16))
        .then(|| (seq.parse().ok(), sha))
        .and_then(|(s, h)| s.map(|s| (s, h)))
}

/// `(^|[^A-Za-z0-9])[Pp]5([^0-9]|$)|[Ee][Cc][Hh][Tt]|[Bb]rabston|[Pp]eterson` (re.search).
fn looks_like_evidence_file(s: &str) -> bool {
    let c: Vec<char> = s.chars().collect();
    let p5 = (0..c.len().saturating_sub(1)).any(|i| {
        (c[i] == 'P' || c[i] == 'p')
            && c[i + 1] == '5'
            && (i == 0 || !c[i - 1].is_ascii_alphanumeric())
            && c.get(i + 2).is_none_or(|n| !n.is_ascii_digit())
    });
    let ci = |w: &str| {
        let w: Vec<char> = w.chars().collect();
        c.windows(w.len()).any(|x| x.iter().zip(&w).all(|(a, b)| a.eq_ignore_ascii_case(b)))
    };
    let first_ci = |w: &str| {
        let w: Vec<char> = w.chars().collect();
        c.windows(w.len()).any(|x| x[0].eq_ignore_ascii_case(&w[0]) && x[1..] == w[1..])
    };
    p5 || ci("echt") || first_ci("brabston") || first_ci("peterson")
}

// ------------------------------------------------------------------------------------------------ hashing / paths

pub fn sha256_file(path: &str) -> HallResult<String> {
    Ok(sha256_hex(&py::read_file(path)?))
}

/// sha256 of the dataset content: the file, or its decompressed content for a `.gz` file.
pub fn sha256_canonical_jsonl(path: &str) -> HallResult<String> {
    if !path.ends_with(".gz") {
        return sha256_file(path);
    }
    let file = std::fs::File::open(path).map_err(|e| py::os_error(&e, path))?;
    let mut data = Vec::new();
    flate2::read::MultiGzDecoder::new(file)
        .read_to_end(&mut data)
        .map_err(|e| HallError::new(Kind::Os, "GZIP", e.to_string()))?;
    Ok(sha256_hex(&data))
}

/// `json.dumps(obj, sort_keys=True, separators=(",", ":"))` sha256 (map_meta_sha256 of admitted_hallmap records).
pub fn canonical_json_sha256(v: &PyValue) -> String {
    let o = Dump { sort_keys: true, item_sep: ",", key_sep: ":", ..Dump::DEFAULT };
    sha256_hex(py::dumps(v, &o).as_bytes())
}

/// `_rel(root, rel, what)`: absolute path of a repository-relative POSIX path inside `root`.
pub fn rel_path(root: &str, rel: &PyValue, what: &str) -> HallResult<String> {
    let rel = match rel {
        PyValue::Str(r) if !py::py_strip(r).is_empty() => r.as_str(),
        _ => return Err(rerr(format!("{what}: a repository-relative file path is required"))),
    };
    if py::isabs(rel) || rel.contains('\\') {
        return Err(rerr(format!("{what}: {} must be a repository-relative POSIX path", py::repr_str(rel))));
    }
    let norm = py::normpath(rel);
    if norm.starts_with("..") || norm != rel.trim_end_matches('/') {
        return Err(rerr(format!("{what}: {} is not a normalised path inside the repository", py::repr_str(rel))));
    }
    let p = py::join(&py::abspath(root), &norm);
    if !py::isfile(&p) {
        return Err(rerr(format!("{what}: file {} does not exist under {}", py::repr_str(rel), py::repr_str(root))));
    }
    Ok(p)
}

fn nonempty<'a>(v: Option<&'a PyValue>, what: &str) -> HallResult<&'a PyValue> {
    match v {
        Some(x @ PyValue::Str(s)) if !py::py_strip(s).is_empty() => Ok(x),
        _ => Err(rerr(format!("{what} must be a non-empty string (no default)"))),
    }
}

/// `_get(d, "a.b.c")`.
pub fn get_path<'a>(d: &'a PyValue, path: &str) -> Option<&'a PyValue> {
    let mut node = d;
    for part in path.split('.') {
        node = match node {
            PyValue::Dict(_) => py::get(node, part).ok().flatten()?,
            _ => return None,
        };
    }
    Some(node)
}

fn opt_eq(a: Option<&PyValue>, b: Option<&PyValue>) -> bool {
    a.unwrap_or(&PyValue::None).py_eq(b.unwrap_or(&PyValue::None))
}

fn item<'a>(d: &'a PyValue, k: &str) -> HallResult<&'a PyValue> {
    py::getitem(d, k)
}

fn item2<'a>(d: &'a PyValue, a: &str, b: &str) -> HallResult<&'a PyValue> {
    py::getitem(py::getitem(d, a)?, b)
}

fn str_of(v: &PyValue) -> HallResult<&str> {
    py::as_str(v).ok_or_else(|| HallError::type_error(format!("'{}' object is not a string", v.type_name())))
}

// ------------------------------------------------------------------------------------------------ schema v2 helper

/// `load_hall_map_schema_v2(root)`: schema v2 merged with the v1 it inherits (v1 must be byte-identical).
pub fn load_hall_map_schema_v2(root: &str, path: Option<&str>) -> HallResult<PyValue> {
    let path = path.unwrap_or(SCHEMA_V2_REL);
    let s2 = py::load_json_file(&rel_path(root, &py::s(path), "hall_map_schema_v2")?)?;
    let inh = item(&s2, "inherits")?;
    let v1_path = rel_path(root, item(inh, "file")?, "hall_map_schema_v1")?;
    if !py::s(sha256_file(&v1_path)?).py_eq(item(inh, "sha256")?) {
        return Err(rerr("hall_map_schema_v1.json differs from the version hall_map_schema_v2 inherits"));
    }
    let v1 = py::load_json_file(&v1_path)?;
    let set = |v: &PyValue| -> HallResult<Vec<PyValue>> { py::set_from(py::iterate(v)?) };
    let mut clash = py::intersection(&set(item(&v1, "fields")?)?, &set(item(&s2, "fields_added")?)?);
    for x in py::intersection(&set(item(&v1, "meta_required")?)?, &set(item(&s2, "meta_added")?)?) {
        if !clash.iter().any(|y| y.py_eq(&x)) {
            clash.push(x);
        }
    }
    if !clash.is_empty() {
        return Err(rerr(format!("v2 redefines v1 keys {}", py::repr(&PyValue::List(py::sorted(clash)?)))));
    }
    let merge = |a: &PyValue, b: &PyValue| -> HallResult<PyValue> {
        let mut out = PyValue::Dict(Vec::new());
        for x in [a, b] {
            let PyValue::Dict(entries) = x else {
                return Err(HallError::type_error(format!("'{}' object is not a mapping", x.type_name())));
            };
            for (k, v) in entries {
                py::set_item(&mut out, &py::py_str(k), v.clone());
            }
        }
        Ok(out)
    };
    let fields = merge(item(&v1, "fields")?, item(&s2, "fields_added")?)?;
    let mut map_fields = py::iterate(item(&v1, "fields")?)?;
    let PyValue::Dict(added) = item(&s2, "fields_added")? else {
        return Err(HallError::type_error("fields_added is not a mapping"));
    };
    for (k, v) in added {
        if str_of(item(v, "level")?)?.starts_with("map field") {
            map_fields.push(k.clone());
        }
    }
    Ok(PyValue::Dict(vec![
        (py::s("schema"), item(&s2, "schema")?.clone()),
        (py::s("meta_required"), merge(item(&v1, "meta_required")?, item(&s2, "meta_added")?)?),
        (py::s("fields"), fields),
        (py::s("map_fields"), PyValue::List(map_fields)),
        (py::s("not_supplied"), item(&s2, "not_supplied")?.clone()),
    ]))
}

// ------------------------------------------------------------------------------------------------ record validation

/// `validate_record(rec)`: the structural rules of `schemas/hallmap/hallmap_registry_v1.json`.
pub fn validate_record(rec: &PyValue) -> HallResult<()> {
    if !py::is_dict(rec) || !opt_eq(py::get(rec, "schema")?, Some(&py::s(RECORD_SCHEMA))) {
        return Err(rerr(format!("record schema must be {}", py::repr_str(RECORD_SCHEMA))));
    }
    let kind = py::get(rec, "kind")?.cloned().unwrap_or(PyValue::None);
    let registration = kind.py_eq(&py::s(KINDS[0]));
    if !registration && !kind.py_eq(&py::s(KINDS[1])) {
        return Err(rerr(format!("record kind must be one of {}", py::repr_tuple(&KINDS))));
    }
    let keys: &[&str] = if registration { &REGISTRATION_KEYS } else { &WITHDRAWAL_KEYS };
    let have = py::set_from(py::iterate(rec)?)?;
    let same = have.len() == keys.len() && keys.iter().all(|k| have.iter().any(|h| h.py_eq(&py::s(*k))));
    if !same {
        let mut want: Vec<&str> = keys.to_vec();
        want.sort_unstable();
        return Err(rerr(format!(
            "{} record keys {} != {}",
            py::py_str(&kind),
            py::repr(&PyValue::List(py::sorted(have)?)),
            py::repr_strs(&want)
        )));
    }
    let seq = item(rec, "seq")?;
    let seq_ok = matches!(seq, PyValue::Int(i) if *i >= 1);
    if !seq_ok {
        return Err(rerr("seq must be an integer >= 1"));
    }
    let prev = item(rec, "prev_record_sha256")?;
    let first = matches!(seq, PyValue::Int(1));
    let prev_none = matches!(prev, PyValue::None);
    if first != prev_none || (!prev_none && !is_hex(&py::py_str(prev), 64)) {
        return Err(rerr("prev_record_sha256 must be null for seq 1 and a sha256 otherwise"));
    }
    match item(rec, "registered_utc")? {
        PyValue::Str(u) if is_utc(u) => {}
        _ => return Err(rerr("registered_utc must be YYYY-MM-DDTHH:MM:SSZ")),
    }
    nonempty(Some(item(rec, "registered_by")?), "registered_by")?;
    for (b, bkeys) in BLOCK_KEYS {
        let Some(blk) = py::get(rec, b)? else { continue };
        let exact = match blk {
            PyValue::Dict(entries) => {
                let ks = py::set_from(entries.iter().map(|(k, _)| k.clone()).collect())?;
                ks.len() == bkeys.len() && bkeys.iter().all(|k| ks.iter().any(|h| h.py_eq(&py::s(*k))))
            }
            _ => false,
        };
        if !exact {
            return Err(rerr(format!("block {} must have exactly {}", py::repr_str(b), py::repr_tuple(bkeys))));
        }
        let PyValue::Dict(entries) = blk else { unreachable!() };
        let file_is_none = matches!(py::get(blk, "file")?, Some(PyValue::None));
        for (k, v) in entries {
            let k = py::py_str(k);
            if k.starts_with("sha256") || k.ends_with("sha256") || k.contains("_sha256_") {
                if k == "sha256" && b == "chemistry" && matches!(v, PyValue::None) && file_is_none {
                    continue;
                }
                if !matches!(v, PyValue::Str(x) if is_hex(x, 64)) {
                    return Err(rerr(format!("{b}.{k} must be a 64-hex sha256")));
                }
            } else if k == "file" {
                if b == "chemistry" && matches!(v, PyValue::None) {
                    continue;
                }
                nonempty(Some(v), &format!("{b}.file"))?;
            } else {
                nonempty(Some(v), &format!("{b}.{k}"))?;
            }
        }
    }
    if registration {
        let sv = item2(rec, "map", "schema_version")?;
        if !MAP_SCHEMAS.iter().any(|m| sv.py_eq(&py::s(*m))) {
            return Err(rerr(format!("map.schema_version must be one of {}", py::repr_tuple(&MAP_SCHEMAS))));
        }
        if !is_hex(str_of(item2(rec, "hallthruster", "commit")?)?, 40) {
            return Err(rerr("hallthruster.commit must be a 40-hex git commit"));
        }
        let chem = item(rec, "chemistry")?;
        let file_none = matches!(item(chem, "file")?, PyValue::None);
        if file_none && !str_of(item(chem, "config_id")?)?.starts_with("builtin-") {
            return Err(rerr("chemistry.file may be null only for a built-in chemistry (config_id 'builtin-...')"));
        }
        if file_none && !matches!(item(chem, "sha256")?, PyValue::None) {
            return Err(rerr("a built-in chemistry has no file sha256"));
        }
    } else {
        if !is_hex(&py::py_str(item(rec, "withdraws_record_sha256")?), 64) {
            return Err(rerr("withdraws_record_sha256 must be a sha256"));
        }
        nonempty(Some(item(rec, "reason")?), "reason")?;
    }
    Ok(())
}

/// The bytes a record is written as.
pub fn record_bytes(rec: &PyValue) -> Vec<u8> {
    let o = Dump { sort_keys: true, ensure_ascii: false, ..Dump::indented(1) };
    (py::dumps(rec, &o) + "\n").into_bytes()
}

// ------------------------------------------------------------------------------------------------ reading

/// `read_records(registry_dir)`: [(file name, sha256 of the bytes, record)] in file-name order.
pub fn read_records(registry_dir: &str) -> HallResult<Vec<(String, String, PyValue)>> {
    let d = py::join(registry_dir, RECORDS_SUBDIR);
    if !py::isdir(&d) {
        return Ok(Vec::new());
    }
    let mut names: Vec<String> = std::fs::read_dir(&d)
        .map_err(|e| py::os_error(&e, &d))?
        .map(|e| e.map(|e| e.file_name().to_string_lossy().into_owned()).map_err(|e| py::os_error(&e, &d)))
        .collect::<HallResult<_>>()?;
    names.sort();
    let mut out = Vec::new();
    for name in names {
        if record_name(&name).is_none() {
            return Err(rerr(format!("foreign file {} in the registry records directory", py::repr_str(&name))));
        }
        let raw = py::read_file(&py::join(&d, &name))?;
        let rec = py::load_json_bytes(&raw).map_err(|_| rerr(format!("record {name} is not valid JSON")))?;
        out.push((name, sha256_hex(&raw), rec));
    }
    Ok(out)
}

// ------------------------------------------------------------------------------------------------ registration checks

fn require_admitted_block(member_id: &str, ens: &PyValue) -> HallResult<PyValue> {
    // hallmap_registry._require_admitted: a ValueError of require_admitted becomes a RegistryError with its text;
    // KeyError / TypeError propagate unchanged.
    ensemble::require_admitted(member_id, ens).map_err(|e| if e.kind == Kind::Value { rerr(e.message) } else { e })?;
    let members = py::get(ens, "members")?.cloned().unwrap_or(PyValue::List(Vec::new()));
    for m in py::iterate(&members)? {
        if opt_eq(py::get(&m, "ensemble_member_id")?, Some(&py::s(member_id))) {
            return match py::get(&m, "admission")? {
                Some(adm) if py::is_dict(adm) => Ok(adm.clone()),
                _ => Err(rerr(format!("admitted member {member_id} has no admission record"))),
            };
        }
    }
    Err(rerr(format!("{member_id} not found among admitted members")))
}

fn caught_registry_value_os(e: &HallError) -> bool {
    e.kind.is_value_error() || e.kind.is_os_error()
}

/// `_check_registration(rec, root, ensemble)`: (integrity problems, currency problems).
fn check_registration(rec: &PyValue, root: &str, ensemble: Option<&PyValue>) -> HallResult<(Vec<String>, Vec<String>)> {
    let mut problems = Vec::new();
    let mut currency = Vec::new();
    for b in REHASHED_BLOCKS {
        let blk = item(rec, b)?;
        let file = item(blk, "file")?;
        if matches!(file, PyValue::None) {
            continue;
        }
        let p = match rel_path(root, file, &format!("{b}.file")) {
            Ok(p) => p,
            Err(e) if e.kind == Kind::Registry => {
                problems.push(e.message);
                continue;
            }
            Err(e) => return Err(e),
        };
        if !py::s(sha256_file(&p)?).py_eq(item(blk, "sha256")?) {
            problems.push(format!("{b}: {} no longer matches its registered sha256", py::py_str(file)));
        }
        if b == "raw_records" && !py::s(sha256_canonical_jsonl(&p)?).py_eq(item(blk, "sha256_canonical_jsonl")?) {
            problems.push("raw_records: dataset content no longer matches sha256_canonical_jsonl".into());
        }
    }
    for b in ["geometry", "magnetic_field"] {
        let f = item2(rec, b, "file")?;
        if looks_like_evidence_file(str_of(f)?) {
            problems.push(format!("{b}.file {} looks like P5/ECHT evidence, not a Vyovrinda design file", py::repr(f)));
        }
    }
    let cp = item(rec, "convergence_prereg")?;
    if str_of(item(cp, "file")?)?.to_uppercase().contains("DRAFT")
        || str_of(item(cp, "id")?)?.to_uppercase().contains("DRAFT")
    {
        problems.push(
            "convergence_prereg: a DRAFT pre-registration is never valid (frozen pre-registration required)".into(),
        );
    }
    match hall_map::pinned_commit(&py::abspath(root), Some(&py::join(&py::abspath(root), "hallthruster_bridge"))) {
        Ok(pin) => {
            let commit = item2(rec, "hallthruster", "commit")?;
            if !commit.py_eq(&py::s(pin.as_str())) {
                currency.push(format!("hallthruster.commit {} != PINNED.toml commit {pin}", py::py_str(commit)));
            }
        }
        Err(e) if e.kind.is_os_error() || e.kind.is_value_error() => {
            currency.push(format!("PINNED.toml unreadable: {}", e.message))
        }
        Err(e) => return Err(e),
    }
    let mid_v = item2(rec, "ensemble_member", "ensemble_member_id")?;
    let mid = py::py_str(mid_v);
    let membership = (|| -> HallResult<Vec<String>> {
        let loaded;
        let ens = match ensemble {
            Some(e) => e,
            None => {
                let p =
                    rel_path(root, item2(rec, "ensemble_member", "ensemble_file")?, "ensemble_member.ensemble_file")?;
                loaded = ensemble::load_ensemble(root, Some(&p))?;
                &loaded
            }
        };
        let adm = require_admitted_block(str_of(mid_v)?, ens)?;
        let mut cur = Vec::new();
        let norm_join = |v: Option<&PyValue>| {
            py::normpath(&py::join("hallthruster_bridge", &py::py_str(v.unwrap_or(&PyValue::None))))
        };
        if !opt_eq(py::get(&adm, "decision_sha256")?, Some(item2(rec, "admission_decision", "sha256")?)) {
            cur.push(format!("admission_decision sha256 differs from member {mid}'s admission decision_sha256"));
        }
        if norm_join(py::get(&adm, "decision_file")?)
            != py::normpath(str_of(item2(rec, "admission_decision", "file")?)?)
        {
            cur.push(format!("admission_decision.file is not member {mid}'s admission decision_file"));
        }
        if !opt_eq(py::get(&adm, "o4_dispositions_sha256")?, Some(item2(rec, "o4_dispositions", "sha256")?)) {
            cur.push(format!("o4_dispositions sha256 differs from member {mid}'s admission o4_dispositions_sha256"));
        }
        if norm_join(py::get(&adm, "o4_dispositions_file")?)
            != py::normpath(str_of(item2(rec, "o4_dispositions", "file")?)?)
        {
            cur.push(format!("o4_dispositions.file is not member {mid}'s admission o4_dispositions_file"));
        }
        Ok(cur)
    })();
    match membership {
        Ok(cur) => currency.extend(cur),
        Err(e) if caught_registry_value_os(&e) => currency.push(format!("ensemble member {mid}: {}", e.message)),
        Err(e) => return Err(e),
    }
    let map_check = (|| -> HallResult<Vec<String>> {
        let mp = rel_path(root, item2(rec, "map", "file")?, "map.file")?;
        Ok(check_map_meta(&py::load_json_file(&mp)?, rec))
    })();
    match map_check {
        Ok(p) => problems.extend(p),
        Err(e) if caught_registry_value_os(&e) => problems.push(format!("map: {}", e.message)),
        Err(e) => return Err(e),
    }
    Ok((problems, currency))
}

/// `_check_map_meta(doc, rec)`.
fn check_map_meta(doc: &PyValue, rec: &PyValue) -> Vec<String> {
    let mut problems = Vec::new();
    let meta = match doc {
        PyValue::Dict(_) => py::get(doc, "meta").ok().flatten(),
        _ => None,
    };
    let Some(meta) = meta.filter(|m| py::is_dict(m)) else { return vec!["map file has no meta object".into()] };
    let r = |p: &str| get_path(rec, p);
    let m = |k: &str| py::get(meta, k).ok().flatten();
    if !opt_eq(Some(&py::s(canonical_json_sha256(meta))), r("map.map_meta_sha256")) {
        problems.push("map meta no longer matches map_meta_sha256".into());
    }
    if !opt_eq(m("schema"), r("map.schema_version")) {
        problems.push(format!(
            "meta.schema {} != map.schema_version {}",
            py::repr(m("schema").unwrap_or(&PyValue::None)),
            py::repr(r("map.schema_version").unwrap_or(&PyValue::None))
        ));
    }
    if !opt_eq(m("ensemble_member_id"), r("ensemble_member.ensemble_member_id")) {
        problems.push("meta.ensemble_member_id differs from the registered member".into());
    }
    if !opt_eq(m("hallthruster_commit"), r("hallthruster.commit")) {
        problems.push("meta.hallthruster_commit differs from the registered pin".into());
    }
    if !matches!(m("facility_ingestion"), Some(PyValue::Bool(false))) {
        problems.push("meta.facility_ingestion must be false for a design (flight) map".into());
    }
    let Some(prov) = m("provenance").filter(|p| py::is_dict(p)) else {
        problems
            .push("meta.provenance missing (docs/hallmap/HALLMAP_PRODUCTION_SPEC.md section 10 requires it)".into());
        return problems;
    };
    if !opt_eq(get_path(prov, "map_set.status"), Some(&py::s("FROZEN"))) {
        problems.push("meta.provenance.map_set.status must be FROZEN to register a design map".into());
    }
    if !opt_eq(get_path(prov, "numerics.convergence.verdict"), Some(&py::s("PASS"))) {
        problems.push("meta.provenance.numerics.convergence.verdict must be PASS".into());
    }
    for (rpath, ppath) in PROVENANCE_EQUALITIES {
        if !opt_eq(r(rpath), get_path(prov, ppath)) {
            problems.push(format!("registry {rpath} != meta.provenance.{ppath}"));
        }
    }
    let chem_file = r("chemistry.file");
    if !matches!(chem_file, Some(PyValue::None))
        && !opt_eq(get_path(prov, "chemistry.config_sha256"), r("chemistry.sha256"))
    {
        problems.push("registry chemistry.sha256 != meta.provenance.chemistry.config_sha256".into());
    }
    problems
}

// ------------------------------------------------------------------------------------------------ verify / lookup

struct Entry {
    sha: String,
    value: PyValue,
}

fn entry_get<'a>(out: &'a [Entry], sha: &str) -> Option<&'a PyValue> {
    out.iter().find(|e| e.sha == sha).map(|e| &e.value)
}

fn entry_set(out: &mut Vec<Entry>, sha: &str, value: PyValue) {
    match out.iter_mut().find(|e| e.sha == sha) {
        Some(e) => e.value = value,
        None => out.push(Entry { sha: sha.to_string(), value }),
    }
}

fn strs(v: &PyValue) -> Vec<String> {
    match v {
        PyValue::List(items) => items.iter().map(py::py_str).collect(),
        _ => Vec::new(),
    }
}

/// `verify(registry_dir, root, ensemble=None)`: the report {ok, n_records, chain_ok, problems, records}.
pub fn verify(registry_dir: &str, root: &str, ensemble: Option<&PyValue>) -> HallResult<PyValue> {
    let recs = match read_records(registry_dir) {
        Ok(r) => r,
        Err(e) if e.kind == Kind::Registry => {
            return Ok(py::dict([
                ("ok", PyValue::Bool(false)),
                ("n_records", PyValue::Int(0)),
                ("chain_ok", PyValue::Bool(false)),
                ("problems", py::list_of_strs(&[e.message])),
                ("records", PyValue::Dict(Vec::new())),
            ]))
        }
        Err(e) => return Err(e),
    };
    let mut out: Vec<Entry> = Vec::new();
    let (mut chain_ok, mut prev): (bool, Option<String>) = (true, None);
    let mut maps_active: Vec<PyValue> = Vec::new();
    for (i, (name, sha, rec)) in recs.iter().enumerate() {
        let i = i + 1;
        let mut rp: Vec<String> = Vec::new();
        let (nseq, nsha) = record_name(name).expect("read_records checked the name");
        if nseq != i || nsha != &sha[..16] {
            rp.push(format!("file name {name} does not match seq {i} / content sha256"));
            chain_ok = false;
        }
        match validate_record(rec) {
            Err(e) if e.kind == Kind::Registry => {
                rp.push(e.message);
                let kind = if py::is_dict(rec) {
                    py::get(rec, "kind")?.cloned().unwrap_or(PyValue::None)
                } else {
                    PyValue::None
                };
                entry_set(
                    &mut out,
                    sha,
                    py::dict([
                        ("seq", PyValue::Int(i as i128)),
                        ("kind", kind),
                        ("status", py::s("INVALID")),
                        ("problems", py::list_of_strs(&rp)),
                    ]),
                );
                chain_ok = false;
                prev = Some(sha.clone());
                continue;
            }
            Err(e) => return Err(e),
            Ok(()) => {}
        }
        let prev_v = prev.as_ref().map_or(PyValue::None, |p| py::s(p.as_str()));
        if !item(rec, "seq")?.py_eq(&PyValue::Int(i as i128)) || !item(rec, "prev_record_sha256")?.py_eq(&prev_v) {
            rp.push("hash chain broken (seq or prev_record_sha256)".into());
            chain_ok = false;
        }
        if item(rec, "kind")?.py_eq(&py::s("REGISTRATION")) {
            let (integ, cur) = check_registration(rec, root, ensemble)?;
            rp.extend(integ);
            let map_sha = item2(rec, "map", "sha256")?.clone();
            if maps_active.iter().any(|m| m.py_eq(&map_sha)) {
                rp.push("map file already registered by an earlier record".into());
            } else {
                maps_active.push(map_sha);
            }
            let status = if rp.is_empty() && cur.is_empty() { "ACTIVE" } else { "INVALID" };
            entry_set(
                &mut out,
                sha,
                py::dict([
                    ("seq", PyValue::Int(i as i128)),
                    ("kind", py::s("REGISTRATION")),
                    ("status", py::s(status)),
                    ("problems", py::list_of_strs(&rp)),
                    ("currency", py::list_of_strs(&cur)),
                ]),
            );
        } else {
            let target_sha = py::py_str(item(rec, "withdraws_record_sha256")?);
            let target = entry_get(&out, &target_sha).cloned();
            match target {
                Some(t) if opt_eq(py::get(&t, "kind")?, Some(&py::s("REGISTRATION"))) => {
                    if py::get(&t, "withdrawn")?.is_some_and(PyValue::truthy) {
                        rp.push("target registration already withdrawn".into());
                    } else {
                        let mut t = t;
                        py::set_item(&mut t, "withdrawn", PyValue::Bool(true));
                        let has_problems = py::get(&t, "problems")?.is_some_and(PyValue::truthy);
                        py::set_item(&mut t, "status", py::s(if has_problems { "INVALID" } else { "WITHDRAWN" }));
                        entry_set(&mut out, &target_sha, t);
                    }
                }
                _ => rp.push("WITHDRAWAL names no earlier REGISTRATION record".into()),
            }
            let decision = item(rec, "decision")?;
            match rel_path(root, item(decision, "file")?, "decision.file") {
                Ok(p) => {
                    if !py::s(sha256_file(&p)?).py_eq(item(decision, "sha256")?) {
                        rp.push("withdrawal decision file no longer matches its sha256".into());
                    }
                }
                Err(e) if e.kind == Kind::Registry => rp.push(e.message),
                Err(e) => return Err(e),
            }
            let status = if rp.is_empty() { "WITHDRAWAL" } else { "INVALID" };
            entry_set(
                &mut out,
                sha,
                py::dict([
                    ("seq", PyValue::Int(i as i128)),
                    ("kind", py::s("WITHDRAWAL")),
                    ("status", py::s(status)),
                    ("problems", py::list_of_strs(&rp)),
                ]),
            );
        }
        prev = Some(sha.clone());
    }
    let mut problems: Vec<String> = Vec::new();
    for e in &out {
        let seq = py::py_str(py::get(&e.value, "seq")?.unwrap_or(&PyValue::None));
        let tag = format!("record {seq} ({})", &e.sha[..16]);
        for p in strs(py::get(&e.value, "problems")?.unwrap_or(&PyValue::None)) {
            problems.push(format!("{tag}: {p}"));
        }
        if !py::get(&e.value, "withdrawn")?.is_some_and(PyValue::truthy) {
            for p in strs(py::get(&e.value, "currency")?.unwrap_or(&PyValue::None)) {
                problems.push(format!("{tag}: {p}"));
            }
        }
    }
    let records = PyValue::Dict(out.into_iter().map(|e| (py::s(e.sha), e.value)).collect());
    Ok(py::dict([
        ("ok", PyValue::Bool(problems.is_empty() && chain_ok)),
        ("n_records", PyValue::Int(recs.len() as i128)),
        ("chain_ok", PyValue::Bool(chain_ok)),
        ("problems", py::list_of_strs(&problems)),
        ("records", records),
    ]))
}

/// `lookup_map_meta(registry_dir, root, map_meta_sha256)`: the ACTIVE, re-verified registration of that map meta.
pub fn lookup_map_meta(
    registry_dir: &str,
    root: &str,
    map_meta_sha256: &PyValue,
    ensemble: Option<&PyValue>,
) -> HallResult<PyValue> {
    let wanted = match map_meta_sha256 {
        PyValue::Str(s) if is_hex(s, 64) => s.as_str(),
        _ => return Err(rerr("map_meta_sha256 must be a 64-hex sha256")),
    };
    let rep = verify(registry_dir, root, ensemble)?;
    if !matches!(py::get(&rep, "chain_ok")?, Some(PyValue::Bool(true))) {
        return Err(rerr(format!("registry chain does not verify: {}", py::repr(item(&rep, "problems")?))));
    }
    let records = item(&rep, "records")?;
    let mut hits: Vec<(String, PyValue)> = Vec::new();
    for (_, sha, rec) in read_records(registry_dir)? {
        if opt_eq(py::get(&rec, "kind")?, Some(&py::s("REGISTRATION")))
            && opt_eq(get_path(&rec, "map.map_meta_sha256"), Some(&py::s(wanted)))
        {
            hits.push((sha, rec));
        }
    }
    if hits.is_empty() {
        return Err(rerr("no registered map has this map_meta_sha256"));
    }
    for (sha, rec) in &hits {
        let st = item(records, sha)?;
        if item(st, "status")?.py_eq(&py::s("ACTIVE")) {
            return Ok(py::dict([("record_sha256", py::s(sha.as_str())), ("record", rec.clone())]));
        }
    }
    let mut statuses = Vec::new();
    let mut lists = Vec::new();
    for (sha, _) in &hits {
        let st = item(records, sha)?;
        statuses.push(item(st, "status")?.clone());
        let mut all = strs(item(st, "problems")?);
        all.extend(strs(py::get(st, "currency")?.unwrap_or(&PyValue::List(Vec::new()))));
        lists.push(py::list_of_strs(&all));
    }
    Err(rerr(format!(
        "registered map is not ACTIVE: {} {}",
        py::repr(&PyValue::List(statuses)),
        py::repr(&PyValue::List(lists))
    )))
}

// ------------------------------------------------------------------------------------------------ appending

static TMP_COUNTER: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

fn tmp_name() -> String {
    let n = TMP_COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    let nanos = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.subsec_nanos());
    format!(".tmp_{}_{n}_{nanos:08x}", std::process::id())
}

/// `_append(registry_dir, rec)`: exclusive, atomic create of the next record file; its sha256. Never overwrites.
fn append(registry_dir: &str, rec: &PyValue) -> HallResult<String> {
    use std::os::unix::fs::PermissionsExt;
    validate_record(rec)?;
    let data = record_bytes(rec);
    let sha = sha256_hex(&data);
    let d = py::join(registry_dir, RECORDS_SUBDIR);
    std::fs::create_dir_all(&d).map_err(|e| py::os_error(&e, &d))?;
    let seq = match item(rec, "seq")? {
        PyValue::Int(i) => *i,
        _ => unreachable!("validated"),
    };
    let prefix = format!("{seq:06}_");
    let final_path = py::join(&d, &format!("{prefix}{}.json", &sha[..16]));
    let tmp = py::join(registry_dir, &tmp_name());
    let result = (|| -> HallResult<()> {
        let mut f =
            std::fs::OpenOptions::new().write(true).create_new(true).open(&tmp).map_err(|e| py::os_error(&e, &tmp))?;
        f.write_all(&data).map_err(|e| py::os_error(&e, &tmp))?;
        f.flush().map_err(|e| py::os_error(&e, &tmp))?;
        f.sync_all().map_err(|e| py::os_error(&e, &tmp))?;
        std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o444)).map_err(|e| py::os_error(&e, &tmp))?;
        let mut existing: Vec<String> = std::fs::read_dir(&d)
            .map_err(|e| py::os_error(&e, &d))?
            .filter_map(|e| e.ok().map(|e| e.file_name().to_string_lossy().into_owned()))
            .filter(|n| n.starts_with(&prefix))
            .collect();
        existing.sort();
        if let Some(first) = existing.first() {
            return Err(rerr(format!("seq {seq} already exists ({first}): the registry is append-only")));
        }
        match std::fs::hard_link(&tmp, &final_path) {
            Ok(()) => Ok(()),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
                Err(rerr(format!("{final_path} exists: records are never overwritten")))
            }
            Err(e) => Err(py::os_error(&e, &final_path)),
        }
    })();
    let _ = std::fs::remove_file(&tmp);
    result.map(|()| sha)
}

fn next(registry_dir: &str, root: &str, ensemble: Option<&PyValue>) -> HallResult<(i128, PyValue)> {
    let rep = verify(registry_dir, root, ensemble)?;
    if !matches!(py::get(&rep, "chain_ok")?, Some(PyValue::Bool(true))) {
        return Err(rerr(format!(
            "refusing to append to a registry whose chain does not verify: {}",
            py::repr(item(&rep, "problems")?)
        )));
    }
    let recs = read_records(registry_dir)?;
    let prev = recs.last().map_or(PyValue::None, |(_, sha, _)| py::s(sha.as_str()));
    Ok((recs.len() as i128 + 1, prev))
}

/// Keyword arguments of `register` / `build_registration` (Python dynamic values; a missing one is a TypeError where
/// Python's signature raises it).
#[derive(Debug, Clone)]
pub struct RegistrationArgs(pub PyValue);

pub const REGISTRATION_ARGS: [&str; 16] = [
    "map_file",
    "raw_records_file",
    "ensemble_member_id",
    "ensemble_file",
    "chemistry_config_id",
    "chemistry_file",
    "geometry_id",
    "geometry_file",
    "bfield_id",
    "bfield_file",
    "convergence_prereg_id",
    "convergence_prereg_file",
    "o4_dispositions_file",
    "admission_decision_file",
    "registered_by",
    "registered_utc",
];

impl RegistrationArgs {
    pub fn from_strs(pairs: &[(&str, Option<&str>)]) -> Self {
        RegistrationArgs(PyValue::Dict(
            pairs.iter().map(|(k, v)| (py::s(*k), v.map_or(PyValue::None, py::s))).collect(),
        ))
    }

    fn get(&self, k: &str) -> Option<&PyValue> {
        py::get(&self.0, k).ok().flatten()
    }

    fn need(&self, k: &str) -> HallResult<&PyValue> {
        self.get(k).ok_or_else(|| {
            HallError::type_error(format!("build_registration() missing 1 required keyword-only argument: '{k}'"))
        })
    }

    fn check_signature(&self) -> HallResult<()> {
        for k in py::iterate(&self.0)? {
            let k = py::py_str(&k);
            if !REGISTRATION_ARGS.contains(&k.as_str()) {
                return Err(HallError::type_error(format!(
                    "build_registration() got an unexpected keyword argument '{k}'"
                )));
            }
        }
        for k in REGISTRATION_ARGS {
            self.need(k)?;
        }
        Ok(())
    }
}

/// `build_registration(root, ..., seq, prev_record_sha256)`: a REGISTRATION record hashing every bound file.
pub fn build_registration(root: &str, kw: &RegistrationArgs, seq: i128, prev: PyValue) -> HallResult<PyValue> {
    kw.check_signature()?;
    let fblock = |k: &str| -> HallResult<String> { sha256_file(&rel_path(root, kw.need(k)?, k)?) };
    let mp = rel_path(root, kw.need("map_file")?, "map_file")?;
    let doc = py::load_json_file(&mp)?;
    let meta = match &doc {
        PyValue::Dict(_) => py::get(&doc, "meta")?.cloned(),
        _ => None,
    };
    let Some(meta) = meta.filter(py::is_dict) else { return Err(rerr("map_file has no meta object")) };
    let raw_p = rel_path(root, kw.need("raw_records_file")?, "raw_records_file")?;
    let ens_p = rel_path(root, kw.need("ensemble_file")?, "ensemble_file")?;
    let pinned_p = py::join(&py::join(&py::abspath(root), "hallthruster_bridge"), "PINNED.toml");
    if !py::isfile(&pinned_p) {
        return Err(rerr("hallthruster_bridge/PINNED.toml not found under root"));
    }
    let config_id = nonempty(kw.get("chemistry_config_id"), "chemistry_config_id")?.clone();
    let chem_file = kw.need("chemistry_file")?;
    let chem = if matches!(chem_file, PyValue::None) {
        py::dict([("config_id", config_id), ("file", PyValue::None), ("sha256", PyValue::None)])
    } else {
        py::dict([("config_id", config_id), ("file", chem_file.clone()), ("sha256", py::s(fblock("chemistry_file")?))])
    };
    let map = py::dict([
        ("file", kw.need("map_file")?.clone()),
        ("sha256", py::s(sha256_file(&mp)?)),
        ("schema_version", py::get(&meta, "schema")?.cloned().unwrap_or(PyValue::None)),
        ("map_meta_sha256", py::s(canonical_json_sha256(&meta))),
    ]);
    let raw = py::dict([
        ("file", kw.need("raw_records_file")?.clone()),
        ("sha256", py::s(sha256_file(&raw_p)?)),
        ("sha256_canonical_jsonl", py::s(sha256_canonical_jsonl(&raw_p)?)),
    ]);
    let member = py::dict([
        ("ensemble_member_id", kw.need("ensemble_member_id")?.clone()),
        ("ensemble_file", kw.need("ensemble_file")?.clone()),
        ("ensemble_sha256_at_registration", py::s(sha256_file(&ens_p)?)),
    ]);
    let ht = py::dict([
        ("commit", py::get(&meta, "hallthruster_commit")?.cloned().unwrap_or(PyValue::None)),
        ("pinned_toml_sha256_at_registration", py::s(sha256_file(&pinned_p)?)),
    ]);
    let block3 = |id: &str, file: &str| -> HallResult<PyValue> {
        Ok(py::dict([("id", kw.need(id)?.clone()), ("file", kw.need(file)?.clone()), ("sha256", py::s(fblock(file)?))]))
    };
    let geometry = block3("geometry_id", "geometry_file")?;
    let bfield = block3("bfield_id", "bfield_file")?;
    let prereg = block3("convergence_prereg_id", "convergence_prereg_file")?;
    let block2 = |file: &str| -> HallResult<PyValue> {
        Ok(py::dict([("file", kw.need(file)?.clone()), ("sha256", py::s(fblock(file)?))]))
    };
    let o4 = block2("o4_dispositions_file")?;
    let decision = block2("admission_decision_file")?;
    Ok(py::dict([
        ("schema", py::s(RECORD_SCHEMA)),
        ("kind", py::s("REGISTRATION")),
        ("seq", PyValue::Int(seq)),
        ("prev_record_sha256", prev),
        ("registered_utc", kw.need("registered_utc")?.clone()),
        ("registered_by", kw.need("registered_by")?.clone()),
        ("map", map),
        ("raw_records", raw),
        ("ensemble_member", member),
        ("chemistry", chem),
        ("hallthruster", ht),
        ("geometry", geometry),
        ("magnetic_field", bfield),
        ("convergence_prereg", prereg),
        ("o4_dispositions", o4),
        ("admission_decision", decision),
    ]))
}

/// `register(registry_dir, root, ensemble=None, **kw)`: append a REGISTRATION after every check passes.
pub fn register(
    registry_dir: &str,
    root: &str,
    kw: &RegistrationArgs,
    ensemble: Option<&PyValue>,
) -> HallResult<String> {
    for k in
        ["registered_by", "registered_utc", "ensemble_member_id", "geometry_id", "bfield_id", "convergence_prereg_id"]
    {
        nonempty(kw.get(k), k)?;
    }
    let cp = match kw.get("convergence_prereg_file") {
        Some(v) if v.truthy() => str_of(v)?.to_string(),
        _ => String::new(),
    };
    if cp.to_uppercase().contains("DRAFT") {
        return Err(rerr("convergence_prereg_file: a DRAFT pre-registration is never valid"));
    }
    let (seq, prev) = next(registry_dir, root, ensemble)?;
    let rec = build_registration(root, kw, seq, prev)?;
    validate_record(&rec)?;
    let (integ, cur) = check_registration(&rec, root, ensemble)?;
    let mut problems: Vec<String> = integ.into_iter().chain(cur).collect();
    let map_sha = item2(&rec, "map", "sha256")?.clone();
    for (_, _, old) in read_records(registry_dir)? {
        if opt_eq(py::get(&old, "kind")?, Some(&py::s("REGISTRATION")))
            && opt_eq(get_path(&old, "map.sha256"), Some(&map_sha))
        {
            problems.push("this map file is already registered".into());
        }
    }
    if !problems.is_empty() {
        return Err(rerr(format!("registration refused: {}", problems.join("; "))));
    }
    append(registry_dir, &rec)
}

/// `withdraw(...)`: append a WITHDRAWAL of an earlier registration, binding the owner decision file by sha256.
#[allow(clippy::too_many_arguments)]
pub fn withdraw(
    registry_dir: &str,
    root: &str,
    record_sha256: &str,
    reason: &PyValue,
    decision_file: &PyValue,
    registered_by: &PyValue,
    registered_utc: &PyValue,
    ensemble: Option<&PyValue>,
) -> HallResult<String> {
    let (seq, prev) = next(registry_dir, root, ensemble)?;
    let targets = read_records(registry_dir)?;
    let target = targets.iter().rev().find(|(_, sha, _)| sha == record_sha256).map(|(_, _, r)| r);
    let is_registration = match target {
        Some(r) => opt_eq(py::get(r, "kind")?, Some(&py::s("REGISTRATION"))),
        None => false,
    };
    if !is_registration {
        return Err(rerr("record_sha256 names no REGISTRATION in this registry"));
    }
    for (_, _, r) in &targets {
        if opt_eq(py::get(r, "kind")?, Some(&py::s("WITHDRAWAL")))
            && opt_eq(py::get(r, "withdraws_record_sha256")?, Some(&py::s(record_sha256)))
        {
            return Err(rerr("registration already withdrawn"));
        }
    }
    let decision_sha = sha256_file(&rel_path(root, decision_file, "decision_file")?)?;
    let rec = py::dict([
        ("schema", py::s(RECORD_SCHEMA)),
        ("kind", py::s("WITHDRAWAL")),
        ("seq", PyValue::Int(seq)),
        ("prev_record_sha256", prev),
        ("registered_utc", registered_utc.clone()),
        ("registered_by", registered_by.clone()),
        ("withdraws_record_sha256", py::s(record_sha256)),
        ("reason", reason.clone()),
        ("decision", py::dict([("file", decision_file.clone()), ("sha256", py::s(decision_sha))])),
    ]);
    append(registry_dir, &rec)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn name_and_pattern_helpers_follow_the_python_regexes() {
        assert_eq!(record_name("000001_0123456789abcdef.json"), Some((1, "0123456789abcdef")));
        assert_eq!(record_name("notes.txt"), None);
        assert_eq!(record_name("00001_0123456789abcdef.json"), None);
        for (f, hit) in [
            ("design/p5_geometry.json", true),
            ("bfield/P5_x.csv", true),
            ("design/p55.json", false),
            ("cases/echt_n2.json", true),
            ("x/Brabston.json", true),
            ("x/BRABSTON.json", false),
            ("design/TEST_vy_geometry_rev0.json", false),
            ("ap5.json", false),
        ] {
            assert_eq!(looks_like_evidence_file(f), hit, "{f}");
        }
        assert!(is_utc("2026-09-27T00:00:00Z"));
        assert!(!is_utc("2026-09-27 00:00:00"));
    }
}
