//! NP-HALL-PARAMETRIC-ENVELOPE v1 (A9.32): deterministic generation of the H-1 HallThruster.jl case file and launch
//! manifest from the locked preregistration, the bridge dry-run validation of every case, the shard job (launched
//! through [`crate::launch::launch`], which writes the nine-field sidecar) and the freeze of the shard outputs into one
//! sha-pinned raw file. Nothing here runs Julia except [`run_shard`]; nothing here judges a result.
//!
//! Every axis value is read from the preregistration and re-checked against the record it cites (H-1 freeze candidate,
//! H2-1, the transport ensemble, the two sourced P5 B(z) files); a mismatch refuses generation.

use crate::jobs::{child_env, JobSpec, ThreadSettings};
use abep_hall::envelope::{
    self as env, case_hash, BzFamilyKind, CASES_REL, CASES_SCHEMA, DRIVER_REL, LAUNCH_MANIFEST_REL, LAUNCH_SCHEMA,
    LOCK_REL, LOCK_SHA256, PREREG_REL, PREREG_SHA256, RAW_MANIFEST_SCHEMA,
};
use abep_provenance::{read_verified, sha256_hex};
use abep_types::pyjson::{self, Dict, DumpOptions, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Write;
use std::path::{Path, PathBuf};

/// Shards of the launch manifest (prereg runtime_estimate: 64 single-thread shards).
pub const N_SHARDS: usize = 64;
/// Contract id recorded in every envelope shard sidecar.
pub const ENVELOPE_CONTRACT_ID: &str = "NP-HALL-PARAMETRIC-ENVELOPE-V1";
pub const BRIDGE_LIB_REL: &str = "hallthruster_bridge/bridge_lib.jl";
pub const H1_REL: &str = "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json";
pub const H21_REL: &str = "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json";
pub const ENS_REL: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";
pub const BRIDGE_DIR: &str = "hallthruster_bridge";
/// P5-N2 campaign numerics carried to H-1 (prereg numerical_settings).
pub const CELL_M: f64 = 5e-4;
pub const DT_S: f64 = 5e-9;
pub const P5_DOMAIN_M: f64 = 0.1;
pub const P5_DURATION_S: f64 = 2e-3;
pub const THRUSTER_NAME: &str = "H-1-PARAMETRIC";
/// Physical prior of the transport ensemble (anom_scale <= 1/16).
pub const ANOM_SCALE_MAX: f64 = 0.0625;

/// Fields bridge_lib.jl `run_case` reads unconditionally on this path (vacuum, measured B profile): `c.<field>`.
pub const RUN_CASE_FIELDS: [&str; 15] = [
    "id",
    "thruster",
    "L_m",
    "r_in_m",
    "r_out_m",
    "domain_m",
    "Vd",
    "B_profile",
    "B_ref_T",
    "transport",
    "mdot_kgps",
    "cells",
    "dt_s",
    "duration_s",
    "average_start_s",
];
/// `bp.<field>` of `measured_bfield`.
pub const B_PROFILE_FIELDS: [&str; 4] = ["file", "align", "z_ref_in_file_mm", "scale_to"];
/// `tr.<field>` of the ScaledGaussianBohm branch.
pub const TRANSPORT_FIELDS: [&str; 5] = ["model", "anom_scale", "barrier_scale", "center", "width"];

fn schema(path: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.into(), message: m.into() }
}

fn model(m: impl Into<String>) -> AbepError {
    AbepError::Model { message: m.into() }
}

fn load(repo: &Path, rel: &str, sha: Option<&str>) -> AbepResult<Value> {
    let bytes = match sha {
        Some(s) => read_verified(&repo.join(rel), s)?,
        None => {
            std::fs::read(repo.join(rel)).map_err(|e| AbepError::Io { path: rel.into(), message: e.to_string() })?
        }
    };
    let text = std::str::from_utf8(&bytes).map_err(|e| schema(rel, e.to_string()))?;
    pyjson::loads(text).map_err(|e| schema(rel, e.to_string()))
}

/// JSON pointer (`/a/0/b`) into a value.
pub fn pointer<'a>(v: &'a Value, ptr: &str) -> Option<&'a Value> {
    ptr.split('/').skip(1).try_fold(v, |x, k| match x {
        Value::Dict(d) => d.get(k),
        Value::List(l) => k.parse::<usize>().ok().and_then(|i| l.get(i)),
        _ => None,
    })
}

fn at<'a>(v: &'a Value, ptr: &str, path: &str) -> AbepResult<&'a Value> {
    pointer(v, ptr).ok_or_else(|| schema(path, format!("{ptr} missing")))
}

fn num(v: &Value, what: &str) -> AbepResult<f64> {
    match v {
        Value::Int(_) | Value::Float(_) => v.to_f64().map_err(|e| model(format!("{what}: {e}"))),
        _ => Err(model(format!("{what} is not a number"))),
    }
}

fn text<'a>(v: &'a Value, what: &str) -> AbepResult<&'a str> {
    v.as_str().ok_or_else(|| model(format!("{what} is not a string")))
}

fn list<'a>(v: &'a Value, what: &str) -> AbepResult<&'a [Value]> {
    v.as_list().ok_or_else(|| model(format!("{what} is not a list")))
}

fn same(a: f64, b: f64, what: &str) -> AbepResult<()> {
    if a == b {
        Ok(())
    } else {
        Err(model(format!("{what}: preregistered {a} != cited source {b}")))
    }
}

/// One sourced B(z) shape: first maximum and data extent (file z in mm).
#[derive(Debug, Clone, PartialEq)]
pub struct BShape {
    pub id: String,
    pub file: String,
    pub z_peak_mm: f64,
    pub z_last_mm: f64,
    pub b_max_g: f64,
}

/// Parse a bridge B-field CSV (`#` comments, one header line, `z_mm,B_G`) as bridge_lib.jl measured_bfield does.
pub fn read_bshape(repo: &Path, id: &str, file: &str, sha: &str) -> AbepResult<BShape> {
    let rel = format!("{BRIDGE_DIR}/{file}");
    let bytes = read_verified(&repo.join(&rel), sha)?;
    let txt = String::from_utf8(bytes).map_err(|e| schema(&rel, e.to_string()))?;
    let rows: Vec<&str> = txt.lines().filter(|l| !l.starts_with('#') && !l.trim().is_empty()).collect();
    let mut pts = Vec::new();
    for r in rows.iter().skip(1) {
        let mut it = r.split(',');
        let z: f64 = it.next().and_then(|x| x.trim().parse().ok()).ok_or_else(|| schema(&rel, format!("row {r}")))?;
        let b: f64 = it.next().and_then(|x| x.trim().parse().ok()).ok_or_else(|| schema(&rel, format!("row {r}")))?;
        pts.push((z, b));
    }
    let (mut zp, mut bm) = pts.first().copied().ok_or_else(|| schema(&rel, "no data rows"))?;
    for &(z, b) in &pts {
        if b > bm {
            bm = b;
            zp = z;
        }
    }
    Ok(BShape { id: id.into(), file: file.into(), z_peak_mm: zp, z_last_mm: pts.last().unwrap().0, b_max_g: bm })
}

fn sval(x: &str) -> Value {
    Value::str(x)
}

fn dict(pairs: Vec<(&str, Value)>) -> Value {
    let mut d = Dict::new();
    for (k, v) in pairs {
        d.insert(k, v);
    }
    Value::Dict(d)
}

/// An axis entry of the preregistration (id, value).
#[derive(Debug, Clone)]
struct Axis {
    id: String,
    value: f64,
}

fn axis(prereg: &Value, name: &str) -> AbepResult<Vec<Axis>> {
    list(at(prereg, &format!("/case_grid/{name}"), PREREG_REL)?, name)?
        .iter()
        .map(|e| Ok(Axis { id: text(at(e, "/id", name)?, name)?.into(), value: num(at(e, "/value", name)?, name)? }))
        .collect()
}

/// The verified preregistration (lock checked: prereg_v1.json, PREREG.md and the input audit).
pub fn load_prereg(repo: &Path) -> AbepResult<Value> {
    let lock = load(repo, LOCK_REL, Some(LOCK_SHA256))?;
    let Value::Dict(files) = at(&lock, "/files", LOCK_REL)? else { return Err(schema(LOCK_REL, "files")) };
    for (f, h) in files.iter() {
        read_verified(&repo.join(env::NP_DIR).join(f), text(h, f)?)?;
    }
    let prereg = load(repo, PREREG_REL, Some(PREREG_SHA256))?;
    let Value::Dict(pins) = at(&prereg, "/pinned_inputs", PREREG_REL)? else {
        return Err(schema(PREREG_REL, "pinned_inputs"));
    };
    for (f, h) in pins.iter() {
        read_verified(&repo.join(f), text(h, f)?)?;
    }
    Ok(prereg)
}

fn pinned<'a>(prereg: &'a Value, rel: &str) -> AbepResult<&'a str> {
    prereg
        .as_dict()
        .and_then(|d| d.get("pinned_inputs"))
        .and_then(|p| p.as_dict())
        .and_then(|p| p.get(rel))
        .and_then(Value::as_str)
        .ok_or_else(|| schema(PREREG_REL, format!("{rel} not pinned")))
}

/// Build the case-file document (deterministic; every axis value checked against its cited source).
pub fn build_case_doc(repo: &Path) -> AbepResult<Value> {
    let prereg = load_prereg(repo)?;
    let h1 = load(repo, H1_REL, Some(pinned(&prereg, H1_REL)?))?;
    let h21 = load(repo, H21_REL, Some(pinned(&prereg, H21_REL)?))?;
    let ens = load(repo, ENS_REL, Some(pinned(&prereg, ENS_REL)?))?;

    // Geometry: the authorised FEMM analysis points, nominal-assumption probe rows.
    let authorised: BTreeMap<String, bool> = list(at(&h1, "/femm_analysis_points/points", H1_REL)?, "points")?
        .iter()
        .map(|p| {
            Ok((
                text(at(p, "/probe", H1_REL)?, "probe")?.to_string(),
                matches!(at(p, "/authorised_analysis_point", H1_REL)?, Value::Bool(true)),
            ))
        })
        .collect::<AbepResult<_>>()?;
    let mut geoms = Vec::new();
    for g in list(at(&prereg, "/case_grid/geometry/points", PREREG_REL)?, "geometry")? {
        let id = text(at(g, "/id", PREREG_REL)?, "id")?;
        let row = at(&h1, text(at(g, "/pointer", PREREG_REL)?, "pointer")?, H1_REL)?;
        let probe = text(at(row, "/probe", H1_REL)?, "probe")?;
        if probe != text(at(g, "/probe", PREREG_REL)?, "probe")?
            || text(at(row, "/assumptions", H1_REL)?, "assumptions")? != "nominal_assumptions"
            || !authorised.get(probe).copied().unwrap_or(false)
        {
            return Err(model(format!("geometry {id}: cited row is not the authorised nominal probe {probe}")));
        }
        let mut v = [0.0; 3];
        for (i, k) in ["h_mm", "d_mean_mm", "L_mm"].iter().enumerate() {
            v[i] = num(at(g, &format!("/{k}"), PREREG_REL)?, k)?;
            same(v[i], num(at(row, &format!("/{k}"), H1_REL)?, k)?, &format!("{id} {k}"))?;
        }
        geoms.push((id.to_string(), v[0], v[1], v[2]));
    }

    // B(z) shapes (sourced surrogate, rigid peak-at-exit).
    if text(at(&prereg, "/bz_family/kind", PREREG_REL)?, "kind")? != BzFamilyKind::SourcedSurrogate.as_str() {
        return Err(model("v1 B(z) family must be SOURCED_SURROGATE"));
    }
    let mut shapes = Vec::new();
    for b in list(at(&prereg, "/case_grid/bz_shape", PREREG_REL)?, "bz_shape")? {
        let file = text(at(b, "/file", PREREG_REL)?, "file")?;
        let sha = pinned(&prereg, &format!("{BRIDGE_DIR}/{file}"))?;
        shapes.push(read_bshape(repo, text(at(b, "/id", PREREG_REL)?, "id")?, file, sha)?);
    }

    // Operating axes, each checked against its cited value.
    let bpk = axis(&prereg, "B_peak_G")?;
    let band = list(at(&h1, "/parameters/36/value", H1_REL)?, "H1F-BZ-03")?;
    if text(at(&h1, "/parameters/36/id", H1_REL)?, "id")? != "H1F-BZ-03" || bpk.len() != 2 {
        return Err(model("B_peak axis must be the two ends of H1F-BZ-03"));
    }
    same(bpk[0].value, num(&band[0], "BZ-03 lo")?, "BP-LO")?;
    same(bpk[1].value, num(&band[1], "BZ-03 hi")?, "BP-HI")?;
    let vds = axis(&prereg, "V_d_V")?;
    let vband = list(at(&h21, "/channel/V_d_band_V", H21_REL)?, "V_d band")?;
    let (vlo, vhi) = (num(&vband[0], "V_d lo")?, num(&vband[1], "V_d hi")?);
    if vds.len() != 3 {
        return Err(model("V_d axis must have three values"));
    }
    same(vds[0].value, vlo, "VD lo")?;
    same(vds[1].value, (vlo + vhi) / 2.0, "VD mid")?;
    same(vds[2].value, vhi, "VD hi")?;
    let mds = axis(&prereg, "mdot_kg_s")?;
    let flows = at(&h21, "/channel/flows_kgps", H21_REL)?;
    for (a, k) in mds.iter().zip(["design_case_min", "design_case_max", "delivered_max_A5"]) {
        same(a.value, num(at(flows, &format!("/{k}"), H21_REL)?, k)?, &a.id)?;
    }
    if mds.len() != 3 {
        return Err(model("mdot axis must have three values"));
    }

    // Transport: the screening candidates in file order, exactly the preregistered ids.
    let want: Vec<&str> = list(at(&prereg, "/case_grid/transport/ids", PREREG_REL)?, "ids")?
        .iter()
        .map(|x| text(x, "id"))
        .collect::<AbepResult<_>>()?;
    let cands = list(at(&ens, "/screening_candidates", ENS_REL)?, "screening_candidates")?;
    let mut transports = Vec::new();
    for c in cands {
        let id = text(at(c, "/ensemble_member_id", ENS_REL)?, "id")?;
        if text(at(c, "/transport_family", ENS_REL)?, "family")? != "ScaledGaussianBohm" {
            return Err(model(format!("{id}: not ScaledGaussianBohm")));
        }
        let tp = at(c, "/transport_parameters", ENS_REL)?;
        let p = |k: &str| num(at(tp, &format!("/{k}"), ENS_REL)?, k);
        transports.push((id.to_string(), p("anom_scale")?, p("barrier_scale")?, p("center_L")?, p("width_L")?));
    }
    let got: Vec<&str> = transports.iter().map(|t| t.0.as_str()).collect();
    if got != want {
        return Err(model(format!("transport ids {got:?} != preregistered {want:?}")));
    }

    let n2_cfg = text(at(&prereg, "/families/1/propellant_config", PREREG_REL)?, "propellant_config")?;
    let n2_dir = text(at(&prereg, "/families/1/rate_dir", PREREG_REL)?, "rate_dir")?;
    let mut cases = Vec::new();
    for fam in env::Family::ALL {
        for (gid, h, d, l) in &geoms {
            let (l_m, r_in, r_out) = (l / 1000.0, (d - h) / 2.0 / 1000.0, (d + h) / 2.0 / 1000.0);
            for sh in &shapes {
                let domain = l_m + (sh.z_last_mm - sh.z_peak_mm) / 1000.0;
                let cells = (domain / CELL_M).ceil() as i64;
                let duration = P5_DURATION_S * f64::max(1.0, domain / P5_DOMAIN_M);
                for bp in &bpk {
                    for vd in &vds {
                        for md in &mds {
                            for (tid, a, b, c, w) in &transports {
                                let key =
                                    format!("{}|{gid}|{}|{}|{}|{}|{tid}", fam.as_str(), sh.id, bp.id, vd.id, md.id);
                                let mut pairs = vec![
                                    ("key", sval(&key)),
                                    ("id", sval(&key)),
                                    ("family", sval(fam.as_str())),
                                    ("thruster", sval(THRUSTER_NAME)),
                                    ("geometry_id", sval(gid)),
                                    ("bz_shape_id", sval(&sh.id)),
                                    ("B_peak_id", sval(&bp.id)),
                                    ("Vd_id", sval(&vd.id)),
                                    ("mdot_id", sval(&md.id)),
                                    ("transport_id", sval(tid)),
                                    ("L_m", Value::Float(l_m)),
                                    ("r_in_m", Value::Float(r_in)),
                                    ("r_out_m", Value::Float(r_out)),
                                    ("domain_m", Value::Float(domain)),
                                    ("cells", Value::int(cells)),
                                    ("dt_s", Value::Float(DT_S)),
                                    ("duration_s", Value::Float(duration)),
                                    ("average_start_s", Value::Float(duration / 2.0)),
                                    ("Vd", Value::Float(vd.value)),
                                    ("mdot_kgps", Value::Float(md.value)),
                                    ("B_ref_T", Value::Float(bp.value / 1e4)),
                                    (
                                        "B_profile",
                                        dict(vec![
                                            ("file", sval(&sh.file)),
                                            ("align", sval("exit")),
                                            ("z_ref_in_file_mm", Value::Float(sh.z_peak_mm)),
                                            ("scale_to", sval("max")),
                                        ]),
                                    ),
                                    (
                                        "transport",
                                        dict(vec![
                                            ("model", sval("ScaledGaussianBohm")),
                                            ("anom_scale", Value::Float(*a)),
                                            ("barrier_scale", Value::Float(*b)),
                                            ("center", Value::Float(*c)),
                                            ("width", Value::Float(*w)),
                                        ]),
                                    ),
                                ];
                                match fam {
                                    env::Family::Xe => pairs.push(("gas", sval("Xe"))),
                                    env::Family::N2Proxy => {
                                        pairs.push(("gas", sval("N2")));
                                        pairs.push(("propellant_config", sval(n2_cfg)));
                                        pairs.push(("rate_dir", sval(n2_dir)));
                                    }
                                }
                                pairs.push(("compact", Value::Bool(true)));
                                let mut case = dict(pairs);
                                let h = case_hash(&case)?;
                                if let Value::Dict(d) = &mut case {
                                    d.insert("case_sha256", sval(&h));
                                }
                                cases.push(case);
                            }
                        }
                    }
                }
            }
        }
    }
    Ok(dict(vec![
        ("schema", sval(CASES_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("prereg_sha256", sval(PREREG_SHA256)),
        ("prereg_lock_sha256", sval(LOCK_SHA256)),
        ("bz_family_kind", sval(BzFamilyKind::SourcedSurrogate.as_str())),
        ("bz_family_label", sval(env::BZ_SURROGATE_LABEL)),
        ("mode", sval("vacuum")),
        (
            "labels_by_family",
            dict(
                env::Family::ALL
                    .iter()
                    .map(|f| (f.as_str(), Value::List(f.labels().into_iter().map(sval).collect())))
                    .collect(),
            ),
        ),
        ("generated_by", sval("abep-h1-envelope-cases generate (crates/abep-julia-bridge/src/envelope_cases.rs)")),
        ("n_cases", Value::int(cases.len() as i64)),
        ("cases", Value::List(cases)),
    ]))
}

/// The case file text: header keys, then one compact case per line (valid JSON, diff-friendly, deterministic).
pub fn render_case_doc(doc: &Value) -> AbepResult<String> {
    let Value::Dict(d) = doc else { return Err(model("case document is not an object")) };
    let compact = DumpOptions { ensure_ascii: false, ..Default::default() };
    let dump = |v: &Value| pyjson::dumps(v, &compact).map_err(|e| model(e.to_string()));
    let mut out = String::from("{\n");
    for (k, v) in d.iter() {
        if k == "cases" {
            continue;
        }
        out.push_str(&format!("{}: {},\n", dump(&Value::str(k.as_str()))?, dump(v)?));
    }
    out.push_str("\"cases\": [\n");
    let cases = d.get("cases").and_then(Value::as_list).ok_or_else(|| model("cases missing"))?;
    for (i, c) in cases.iter().enumerate() {
        out.push_str(&dump(c)?);
        out.push_str(if i + 1 < cases.len() { ",\n" } else { "\n" });
    }
    out.push_str("]\n}\n");
    Ok(out)
}

/// The launch manifest of a rendered case file.
pub fn build_launch_manifest(repo: &Path, cases_text: &str, n_by_family: &[(String, usize)]) -> AbepResult<Value> {
    let driver_sha = abep_provenance::sha256_file(&repo.join(DRIVER_REL))?;
    let lib_sha = abep_provenance::sha256_file(&repo.join(BRIDGE_LIB_REL))?;
    let n: usize = n_by_family.iter().map(|x| x.1).sum();
    let commands: Vec<Value> = (0..N_SHARDS)
        .map(|i| {
            sval(&format!(
                "julia --project=hallthruster_bridge {DRIVER_REL} <out>/s{i:02}.jsonl {i} {N_SHARDS} <family: XE | N2_PROXY | ALL>"
            ))
        })
        .collect();
    let mut fam = Dict::new();
    for (k, v) in n_by_family {
        fam.insert(k.as_str(), Value::int(*v as i64));
    }
    Ok(dict(vec![
        ("schema", sval(LAUNCH_SCHEMA)),
        ("model_id", sval("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("prereg_sha256", sval(PREREG_SHA256)),
        ("prereg_lock_sha256", sval(LOCK_SHA256)),
        ("cases", sval(CASES_REL)),
        ("cases_sha256", sval(&sha256_hex(cases_text.as_bytes()))),
        ("driver", sval(DRIVER_REL)),
        ("driver_sha256", sval(&driver_sha)),
        ("bridge_lib", sval(BRIDGE_LIB_REL)),
        ("bridge_lib_sha256", sval(&lib_sha)),
        ("n_cases", Value::int(n as i64)),
        ("n_cases_by_family", Value::Dict(fam)),
        ("n_shards", Value::int(N_SHARDS as i64)),
        ("shard_rule", sval("case index i (0-based, file order) belongs to shard i mod n_shards; an optional family filter runs one family")),
        ("thread_env", dict(THREAD_PIN.iter().map(|(k, v)| (*k, sval(v))).collect())),
        ("commands", Value::List(commands)),
        ("run_shard", sval("abep-h1-envelope-cases run-shard --shard <i> --out <dir> [--family XE|N2_PROXY|ALL] (Rust launch: pin check, input hashes, julia --version, nine-field sidecar)")),
        ("freeze", sval("abep-h1-envelope-cases freeze --name <name> --out <dir> <shard .jsonl files>")),
        ("mode", sval("vacuum")),
    ]))
}

/// Thread / BLAS settings pinned for every shard (prereg seeds).
pub const THREAD_PIN: [(&str, &str); 4] =
    [("JULIA_NUM_THREADS", "1"), ("MKL_NUM_THREADS", "1"), ("OMP_NUM_THREADS", "1"), ("OPENBLAS_NUM_THREADS", "1")];

/// (case text, launch-manifest text) as `generate` writes them.
pub fn generate(repo: &Path) -> AbepResult<(String, String)> {
    let doc = build_case_doc(repo)?;
    let n = validate_cases(repo, &doc)?;
    let text = render_case_doc(&doc)?;
    let lm = build_launch_manifest(repo, &text, &n)?;
    let mut lm_text = pyjson::dumps(&lm, &DumpOptions::config_writer()).map_err(|e| model(e.to_string()))?;
    lm_text.push('\n');
    Ok((text, lm_text))
}

/// Write the case file and launch manifest.
pub fn write_generated(repo: &Path) -> AbepResult<()> {
    let (cases, lm) = generate(repo)?;
    for (rel, t) in [(CASES_REL, &cases), (LAUNCH_MANIFEST_REL, &lm)] {
        let p = repo.join(rel);
        if let Some(parent) = p.parent() {
            std::fs::create_dir_all(parent).map_err(|e| AbepError::Io { path: rel.into(), message: e.to_string() })?;
        }
        std::fs::write(&p, t).map_err(|e| AbepError::Io { path: rel.into(), message: e.to_string() })?;
    }
    Ok(())
}

/// Regenerate in memory and require byte equality with the committed case file and launch manifest; then the
/// committed case set must parse (every case hash) through the ingestion reader.
pub fn check(repo: &Path) -> AbepResult<usize> {
    let (cases, lm) = generate(repo)?;
    for (rel, t) in [(CASES_REL, &cases), (LAUNCH_MANIFEST_REL, &lm)] {
        let have =
            std::fs::read(repo.join(rel)).map_err(|e| AbepError::Io { path: rel.into(), message: e.to_string() })?;
        if have != t.as_bytes() {
            return Err(model(format!("{rel} differs from its deterministic regeneration")));
        }
    }
    Ok(env::load_case_set(repo)?.cases.len())
}

/// Dry-run validation of every case against the bridge `run_case` input contract (fields, types, files, rate tables,
/// transport family and prior, geometry and timing sanity). Returns the case count per family.
pub fn validate_cases(repo: &Path, doc: &Value) -> AbepResult<Vec<(String, usize)>> {
    let cases = list(at(doc, "/cases", CASES_REL)?, "cases")?;
    let mut counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut keys = BTreeSet::new();
    let mut rate_ok: BTreeSet<String> = BTreeSet::new();
    for c in cases {
        let key = text(at(c, "/key", CASES_REL)?, "key")?;
        let bad = |m: String| model(format!("case {key}: {m}"));
        if !keys.insert(key.to_string()) {
            return Err(bad("duplicate key".into()));
        }
        for f in RUN_CASE_FIELDS {
            pointer(c, &format!("/{f}")).ok_or_else(|| bad(format!("run_case field {f} missing")))?;
        }
        let f = |k: &str| -> AbepResult<f64> { num(at(c, &format!("/{k}"), CASES_REL)?, k) };
        let (l, ri, ro, dom) = (f("L_m")?, f("r_in_m")?, f("r_out_m")?, f("domain_m")?);
        if !(l > 0.0 && ri > 0.0 && ro > ri && dom > l) {
            return Err(bad("geometry: need L > 0, 0 < r_in < r_out, domain > L".into()));
        }
        let (dt, dur, avg) = (f("dt_s")?, f("duration_s")?, f("average_start_s")?);
        if !(dt > 0.0 && avg > 0.0 && avg < dur) {
            return Err(bad("timing: need dt > 0 and 0 < average_start < duration".into()));
        }
        if !matches!(at(c, "/cells", CASES_REL)?, Value::Int(i) if i.as_i64().is_some_and(|n| n >= 1)) {
            return Err(bad("cells must be a positive integer".into()));
        }
        if !(f("Vd")? > 0.0 && f("mdot_kgps")? > 0.0 && f("B_ref_T")? > 0.0) {
            return Err(bad("Vd, mdot_kgps and B_ref_T must be positive".into()));
        }
        let bp = at(c, "/B_profile", CASES_REL)?;
        for k in B_PROFILE_FIELDS {
            pointer(bp, &format!("/{k}")).ok_or_else(|| bad(format!("B_profile.{k} missing")))?;
        }
        let file = text(at(bp, "/file", CASES_REL)?, "file")?;
        if !repo.join(BRIDGE_DIR).join(file).is_file() {
            return Err(bad(format!("B_profile file {file} absent")));
        }
        if !["exit", "anode"].contains(&text(at(bp, "/align", CASES_REL)?, "align")?)
            || !["exit", "max"].contains(&text(at(bp, "/scale_to", CASES_REL)?, "scale_to")?)
        {
            return Err(bad("B_profile align / scale_to outside the bridge vocabulary".into()));
        }
        let tr = at(c, "/transport", CASES_REL)?;
        for k in TRANSPORT_FIELDS {
            pointer(tr, &format!("/{k}")).ok_or_else(|| bad(format!("transport.{k} missing")))?;
        }
        if text(at(tr, "/model", CASES_REL)?, "model")? != "ScaledGaussianBohm" {
            return Err(bad("transport model is not the registered ScaledGaussianBohm".into()));
        }
        let a = num(at(tr, "/anom_scale", CASES_REL)?, "anom_scale")?;
        if !(a > 0.0 && a <= ANOM_SCALE_MAX) {
            return Err(bad(format!("anom_scale {a} outside the physical prior (0, 1/16]")));
        }
        let fam = text(at(c, "/family", CASES_REL)?, "family")?;
        let has_cfg = pointer(c, "/propellant_config").is_some();
        match (fam, text(at(c, "/gas", CASES_REL)?, "gas")?, has_cfg) {
            ("XE", "Xe", false) => {}
            ("N2_PROXY", "N2", true) => {
                let cfg = text(at(c, "/propellant_config", CASES_REL)?, "propellant_config")?;
                let dir = text(at(c, "/rate_dir", CASES_REL)?, "rate_dir")?;
                if rate_ok.insert(format!("{cfg}|{dir}")) {
                    check_rate_files(repo, cfg, dir).map_err(|e| bad(e.to_string()))?;
                }
            }
            other => return Err(bad(format!("family / gas / propellant_config {other:?} inconsistent"))),
        }
        *counts.entry(fam.to_string()).or_default() += 1;
    }
    Ok(counts.into_iter().collect())
}

/// bridge_lib.jl `missing_rate_files` + `chemistry_reactions` guards: every rate file named in the propellant config
/// exists and has a `verified | unresolved` entry in rate_validity.toml.
pub fn check_rate_files(repo: &Path, cfg: &str, dir: &str) -> AbepResult<usize> {
    let read = |rel: &str| -> AbepResult<toml::Table> {
        let t = std::fs::read_to_string(repo.join(BRIDGE_DIR).join(rel))
            .map_err(|e| AbepError::Io { path: rel.into(), message: e.to_string() })?;
        toml::from_str(&t).map_err(|e| schema(rel, e.to_string()))
    };
    let conf = read(cfg)?;
    let val = read(&format!("{dir}/rate_validity.toml"))?;
    let reactions = conf.get("reactions").and_then(|r| r.as_array()).ok_or_else(|| schema(cfg, "no reactions"))?;
    let mut n = 0;
    for r in reactions {
        let Some(f) = r.get("rate_coeff_file").and_then(|x| x.as_str()) else { continue };
        if !repo.join(BRIDGE_DIR).join(dir).join(f).is_file() {
            return Err(model(format!("rate file {f} missing in {dir}")));
        }
        let st = val.get(f).and_then(|e| e.get("status")).and_then(|s| s.as_str());
        if !matches!(st, Some("verified") | Some("unresolved")) {
            return Err(model(format!("rate file {f} has no verified|unresolved entry in rate_validity.toml")));
        }
        n += 1;
    }
    Ok(n)
}

/// The shard job: `julia --project=hallthruster_bridge <driver> <out>/sNN.jsonl <shard> 64 <family>` with the pinned
/// thread settings and every input hash the driver relies on.
pub fn shard_job(
    repo: &Path,
    shard: usize,
    family: &str,
    out_dir: &str,
    lookup: &dyn Fn(&str) -> Option<String>,
) -> AbepResult<JobSpec> {
    if shard >= N_SHARDS {
        return Err(model(format!("shard {shard} outside 0..{N_SHARDS}")));
    }
    if !["XE", "N2_PROXY", "ALL"].contains(&family) {
        return Err(model(format!("family {family} not XE | N2_PROXY | ALL")));
    }
    let lm = load(repo, LAUNCH_MANIFEST_REL, None)?;
    let s =
        |k: &str| -> AbepResult<String> { Ok(text(at(&lm, &format!("/{k}"), LAUNCH_MANIFEST_REL)?, k)?.to_string()) };
    let out = format!("{out_dir}/s{shard:02}.jsonl");
    let threads = ThreadSettings::pinned(THREAD_PIN);
    let mut inputs = vec![
        (DRIVER_REL.to_string(), s("driver_sha256")?),
        (CASES_REL.to_string(), s("cases_sha256")?),
        (LOCK_REL.to_string(), LOCK_SHA256.to_string()),
        (PREREG_REL.to_string(), PREREG_SHA256.to_string()),
        (BRIDGE_LIB_REL.to_string(), s("bridge_lib_sha256")?),
    ];
    let prereg = load(repo, PREREG_REL, Some(PREREG_SHA256))?;
    if let Some(Value::Dict(p)) = pointer(&prereg, "/pinned_inputs") {
        for (f, h) in p.iter() {
            if f != BRIDGE_LIB_REL {
                inputs.push((f.clone(), text(h, f)?.to_string()));
            }
        }
    }
    Ok(JobSpec {
        program: "julia".into(),
        args: vec![
            "--project=hallthruster_bridge".into(),
            DRIVER_REL.into(),
            out.clone(),
            shard.to_string(),
            N_SHARDS.to_string(),
            family.into(),
        ],
        cwd: repo.to_string_lossy().to_string(),
        env: child_env(lookup, &threads, &[]),
        threads,
        inputs,
        outputs: vec![out],
    })
}

/// Launch one shard (the only Julia spawn of this module): pin, inputs, Julia version, sidecar.
pub fn run_shard(
    repo: &Path,
    shard: usize,
    family: &str,
    out_dir: &str,
) -> AbepResult<crate::sidecar::JuliaRunSidecar> {
    let lookup = |k: &str| std::env::var(k).ok();
    let job = shard_job(repo, shard, family, out_dir, &lookup)?;
    crate::launch::launch(&repo.to_string_lossy(), &job, ENVELOPE_CONTRACT_ID)
}

/// Freeze shard outputs: records sorted by key (unique), one gzip JSONL (mtime 0) and its manifest with every shard and
/// sidecar sha256. Returns (manifest path, manifest sha256). The freeze judges nothing; ingestion checks the records.
pub fn freeze(repo: &Path, name: &str, shards: &[PathBuf], out_dir: &Path) -> AbepResult<(PathBuf, String)> {
    let lm = load(repo, LAUNCH_MANIFEST_REL, None)?;
    let mut by_key: BTreeMap<String, String> = BTreeMap::new();
    let mut shard_rows = Vec::new();
    for p in shards {
        let label = p.to_string_lossy().to_string();
        let bytes = std::fs::read(p).map_err(|e| AbepError::Io { path: label.clone(), message: e.to_string() })?;
        let txt = String::from_utf8(bytes.clone()).map_err(|e| schema(&label, e.to_string()))?;
        let mut n = 0usize;
        for line in txt.lines().filter(|l| !l.trim().is_empty()) {
            let v = pyjson::loads(line).map_err(|e| schema(&label, e.to_string()))?;
            let key = text(at(&v, "/key", &label)?, "key")?.to_string();
            if by_key.insert(key.clone(), line.trim().to_string()).is_some() {
                return Err(model(format!("duplicate record {key} across shards")));
            }
            n += 1;
        }
        let side = PathBuf::from(crate::sidecar::JuliaRunSidecar::path_for(&label));
        let side_sha = if side.is_file() { sval(&abep_provenance::sha256_file(&side)?) } else { Value::Null };
        let fname = |q: &Path| q.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default();
        shard_rows.push(dict(vec![
            ("file", sval(&fname(p))),
            ("sha256", sval(&sha256_hex(&bytes))),
            ("n_records", Value::int(n as i64)),
            ("sidecar", if side.is_file() { sval(&fname(&side)) } else { Value::Null }),
            ("sidecar_sha256", side_sha),
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
    std::fs::create_dir_all(out_dir)
        .map_err(|e| AbepError::Io { path: out_dir.to_string_lossy().into(), message: e.to_string() })?;
    let raw_name = format!("{name}_raw.jsonl.gz");
    std::fs::write(out_dir.join(&raw_name), &gz)
        .map_err(|e| AbepError::Io { path: raw_name.clone(), message: e.to_string() })?;
    let cases_sha = text(at(&lm, "/cases_sha256", LAUNCH_MANIFEST_REL)?, "cases_sha256")?;
    let driver_sha = text(at(&lm, "/driver_sha256", LAUNCH_MANIFEST_REL)?, "driver_sha256")?;
    let m = dict(vec![
        ("schema", sval(RAW_MANIFEST_SCHEMA)),
        ("name", sval(name)),
        ("layer", sval(env::LAYER_A_LABEL)),
        ("prereg_lock_sha256", sval(LOCK_SHA256)),
        ("cases_file_sha256", sval(cases_sha)),
        ("driver_sha256", sval(driver_sha)),
        ("n_records", Value::int(by_key.len() as i64)),
        ("raw_file", sval(&raw_name)),
        ("raw_sha256", sval(&sha256_hex(&gz))),
        ("shards", Value::List(shard_rows)),
        ("frozen_by", sval("abep-h1-envelope-cases freeze")),
    ]);
    let mut mt = pyjson::dumps(&m, &DumpOptions::config_writer()).map_err(|e| model(e.to_string()))?;
    mt.push('\n');
    let mp = out_dir.join(format!("{name}_raw_manifest.json"));
    std::fs::write(&mp, &mt)
        .map_err(|e| AbepError::Io { path: mp.to_string_lossy().into(), message: e.to_string() })?;
    Ok((mp, sha256_hex(mt.as_bytes())))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pointer_walks_objects_and_lists() {
        let v = pyjson::loads(r#"{"a": [{"b": 2}]}"#).unwrap();
        assert!(matches!(pointer(&v, "/a/0/b"), Some(Value::Int(_))));
        assert!(pointer(&v, "/a/1").is_none());
    }
}
