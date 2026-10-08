//! NP-HALL-CHEM-AIR (A9.33 Q2): Rust generation of the AIR HallThruster.jl cases.
//!
//! Every AIR case is a frozen NP-HALL-PARAMETRIC-ENVELOPE v1 N2_PROXY row (geometry, B(z) registration, operating point,
//! transport and numerics unchanged; the v1 case file is read through its sha256 pin) combined with one composition point
//! of the preregistered hull (CE-AIR, recomputed from the hash-verified frozen design-state set and required to equal the
//! preregistered values exactly) and the neutral-inlet rule NI-01 (addendum 01). Nothing here runs Julia or judges a
//! result.
//!
//! * [`build_audit_doc`]: the 576-case CA-HALL-AIR-v1 blind state envelope (addendum 01), with the snapshot
//!   [`audit_manifest`] that pins its configurations, rate files, bound tables and case file.
//! * [`freeze_audit`]: shard outputs -> one sorted gzip JSONL and its sha256 manifest (read by `air_audit`).

use crate::envelope_cases::render_case_doc;
use abep_data::design_states::DesignStateSet;
use abep_data::pins::FrozenPins;
use abep_hall::envelope::{case_hash, CASES_REL as V1_CASES_REL};
use abep_provenance::{read_verified, sha256_hex};
use abep_types::pyjson::{self, Dict, DumpOptions, Value};
use abep_types::{AbepError, AbepResult};
use std::collections::BTreeMap;
use std::io::Write;
use std::path::{Path, PathBuf};

/// sha256 of the frozen v1 case file (launch_manifest_v1.json `cases_sha256`).
pub const V1_CASES_SHA256: &str = "c4a73dbbc1f7cbf25add986211e2e4ad945a91b7328ab0b99663de35e6021b12";
pub const CHEM_PREREG_REL: &str = "docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/prereg_v1.json";
pub const CHEM_PREREG_SHA256: &str = "306712f78bbbf17e8aa50e804559c36a80680dbebc8ecf0f47f2c244443ea70f";
pub const CHEM_ADDENDUM01_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/addendum_01_audit_spec_inlet_erratum.json";
pub const CHEM_ADDENDUM01_SHA256: &str = "8e5617bf86c21e7f8418ba744b875e1750e02ba0035419e2614f2151b0f9dcf3";
pub const CHEM_ADDENDUM01_LOCK_REL: &str = "docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/addendum_01_lock.json";
pub const CHEM_ADDENDUM01_LOCK_SHA256: &str = "bf1f743cd1c9efc1ed6a3b9c6c8c6183553887d9bee7b8934547f4821dddca42";
pub const AUDIT_DIR: &str = "hallthruster_bridge/audit_air";
pub const AUDIT_CASES_REL: &str = "hallthruster_bridge/audit_air/air_state_envelope_cases_v1.json";
pub const AUDIT_MANIFEST_REL: &str = "hallthruster_bridge/audit_air/configs/MANIFEST.json";
pub const AUDIT_CASES_SCHEMA: &str = "np_hall_chem_air_audit_cases_v1";
pub const AUDIT_RAW_SCHEMA: &str = "np_hall_chem_air_audit_raw_manifest_v1";
/// Snapshot configurations of the audit (addendum 01): id -> (snapshot file, production file it copies, label).
pub const AUDIT_CHEMISTRY: [(&str, &str, &str); 2] = [
    ("AIR-NOM", "air_nom_abep-air-0.7.toml", "air_nominal.toml"),
    ("AIR-ALT", "air_alt_abep-air-0.7.toml", "air_alt.toml"),
];
pub const AUDIT_LABEL: &str = "abep-air-0.7";
/// Bound tables of the audit (bridge-relative), addendum 01.
pub const AUDIT_BOUND_TABLES: [&str; 6] = [
    "audit_air/bound_tables/dissociative_ionization_O2_to_O_Z2plus_song2026.dat",
    "audit_air/bound_tables/attachment_O2_song2026.dat",
    "audit/bound_tables/ionization_N_Z2plus_to_N_Z3plus_bell1983.dat",
    "audit/bound_tables/ionization_N2_to_N2_Z2plus_nominal.dat",
    "audit/bound_tables/ionization_N2_to_N2_Z2plus_upper.dat",
    "audit/bound_tables/ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat",
];
/// Audit selection of the v1 axes (addendum 01).
pub const AUDIT_GEOMETRY: &str = "G-RP1";
pub const AUDIT_SHAPE: &str = "BZ-P5B16";
pub const AUDIT_B_PEAK: [&str; 2] = ["BP-LO", "BP-HI"];
pub const AUDIT_VD: [&str; 2] = ["VD-180", "VD-350"];
pub const AUDIT_MDOT: [&str; 2] = ["MF-LO", "MF-HI"];

/// The solver's element masses (HallThruster.jl v0.23.1 src/physics/elements.jl), used by NI-01 and CE-AIR.
pub const M_N: f64 = 14.007;
pub const M_O: f64 = 15.999;
/// NI-01: HallThruster.jl default neutral velocity and temperature (src/physics/constants.jl), the v1 N2_PROXY inlet.
pub const V_N2_DEFAULT_M_S: f64 = 150.0;
pub const T_INLET_K: f64 = 500.0;
pub const INLET_LABEL: &str = "NEUTRAL_INLET_EQUAL_T_SCALED_FROM_V1_DEFAULT";
pub const COMPOSITION_LABEL: &str = "COMPOSITION_HULL_CORNERS_NOT_INTERIOR_BOUNDS";
pub const BRIDGE_DIR: &str = "hallthruster_bridge";

fn model(m: impl Into<String>) -> AbepError {
    AbepError::Model { message: m.into() }
}

fn schema(path: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.into(), message: m.into() }
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

fn load_json(repo: &Path, rel: &str, sha: &str) -> AbepResult<Value> {
    let bytes = read_verified(&repo.join(rel), sha)?;
    let text = std::str::from_utf8(&bytes).map_err(|e| schema(rel, e.to_string()))?;
    pyjson::loads(text).map_err(|e| schema(rel, e.to_string()))
}

fn ptr<'a>(v: &'a Value, path: &str, what: &str) -> AbepResult<&'a Value> {
    crate::envelope_cases::pointer(v, path).ok_or_else(|| model(format!("{what}: {path} missing")))
}

fn f64_at(v: &Value, path: &str, what: &str) -> AbepResult<f64> {
    ptr(v, path, what)?.to_f64().map_err(|e| model(format!("{what} {path}: {e}")))
}

fn str_at<'a>(v: &'a Value, path: &str, what: &str) -> AbepResult<&'a str> {
    ptr(v, path, what)?.as_str().ok_or_else(|| model(format!("{what} {path}: not a string")))
}

/// Molar mass of a configured neutral with the solver's element masses.
pub fn molar_mass(species: &str) -> AbepResult<f64> {
    match species {
        "N" => Ok(M_N),
        "N2" => Ok(2.0 * M_N),
        "O" => Ok(M_O),
        "O2" => Ok(2.0 * M_O),
        other => Err(model(format!("no AIR neutral {other}"))),
    }
}

/// One composition point of the CE-AIR hull (mass fractions of N2, N, O2, O).
#[derive(Debug, Clone, PartialEq)]
pub struct Composition {
    pub id: String,
    pub y_o: f64,
    pub f_o: f64,
    pub f_n: f64,
    /// `[(species, mass fraction)]` in the order N2, N, O2, O.
    pub w: Vec<(&'static str, f64)>,
}

fn corner(id: &str, y: f64, fo: f64, fnn: f64) -> Composition {
    let m = y * M_O + (1.0 - y) * M_N;
    let w = vec![
        ("N2", (1.0 - fnn) * (1.0 - y) * M_N / m),
        ("N", fnn * (1.0 - y) * M_N / m),
        ("O2", (1.0 - fo) * y * M_O / m),
        ("O", fo * y * M_O / m),
    ];
    Composition { id: id.into(), y_o: y, f_o: fo, f_n: fnn, w }
}

/// CE-AIR: the four hull corners, recomputed from the frozen design-state set (same operation order as the registration
/// script) and required to equal `prereg_v1.json /composition/hall_composition_points` exactly.
pub fn composition_points(repo: &Path) -> AbepResult<Vec<Composition>> {
    let pins = FrozenPins::load(repo)?;
    let set = DesignStateSet::load(repo, &pins)?;
    if set.states.len() != 196 || !set.states.iter().all(|s| s.required) {
        return Err(model("CE-AIR is registered on 196 required design states"));
    }
    let (mut ymin, mut ymax, mut fomax, mut fnmax) = (f64::INFINITY, f64::NEG_INFINITY, 0.0_f64, 0.0_f64);
    for s in &set.states {
        let o_nuc = s.n_o_m3() + 2.0 * s.n_o2_m3();
        let n_nuc = s.thermo("n_N_m3") + 2.0 * s.n_n2_m3();
        let y = o_nuc / (o_nuc + n_nuc);
        ymin = ymin.min(y);
        ymax = ymax.max(y);
        fomax = fomax.max(s.n_o_m3() / o_nuc);
        fnmax = fnmax.max(s.thermo("n_N_m3") / n_nuc);
    }
    let pts = vec![
        corner("CP-YLO-REC", ymin, 0.0, 0.0),
        corner("CP-YLO-DIS", ymin, fomax, fnmax),
        corner("CP-YHI-REC", ymax, 0.0, 0.0),
        corner("CP-YHI-DIS", ymax, fomax, fnmax),
    ];
    let prereg = load_json(repo, CHEM_PREREG_REL, CHEM_PREREG_SHA256)?;
    let reg = ptr(&prereg, "/composition/hall_composition_points/points", "prereg")?
        .as_list()
        .ok_or_else(|| model("prereg composition points is not a list"))?;
    if reg.len() != pts.len() {
        return Err(model("prereg registers another number of composition points"));
    }
    for (p, r) in pts.iter().zip(reg) {
        let same = |path: &str, x: f64| -> AbepResult<()> {
            let v = f64_at(r, path, &p.id)?;
            if v.to_bits() == x.to_bits() {
                Ok(())
            } else {
                Err(model(format!("{} {path}: recomputed {x:e} != preregistered {v:e}", p.id)))
            }
        };
        if str_at(r, "/id", "prereg point")? != p.id {
            return Err(model(format!("composition point order: {} expected", p.id)));
        }
        same("/y_O", p.y_o)?;
        same("/f_O", p.f_o)?;
        same("/f_N", p.f_n)?;
        for (sp, w) in &p.w {
            same(&format!("/mass_fractions/{sp}"), *w)?;
        }
    }
    Ok(pts)
}

/// NI-01 inlet velocity of a neutral [m/s].
pub fn inlet_velocity(species: &str) -> AbepResult<f64> {
    Ok(V_N2_DEFAULT_M_S * (molar_mass("N2")? / molar_mass(species)?).sqrt())
}

/// NI-01 feed of a delivered mass flow at a composition point: one entry per configured neutral (zero flow allowed).
pub fn feed(comp: &Composition, mdot_kg_s: f64) -> AbepResult<Value> {
    let mut v = Vec::new();
    for (sp, w) in &comp.w {
        v.push(dict(vec![
            ("species", sval(sp)),
            ("flow_rate_kg_s", Value::Float(mdot_kg_s * w)),
            ("velocity_m_s", Value::Float(inlet_velocity(sp)?)),
            ("temperature_K", Value::Float(T_INLET_K)),
        ]));
    }
    Ok(Value::List(v))
}

/// Fields copied from a v1 row (geometry, B registration, operating point, transport, numerics).
pub const V1_FIELDS: [&str; 20] = [
    "thruster",
    "geometry_id",
    "bz_shape_id",
    "B_peak_id",
    "Vd_id",
    "mdot_id",
    "transport_id",
    "L_m",
    "r_in_m",
    "r_out_m",
    "domain_m",
    "cells",
    "dt_s",
    "duration_s",
    "average_start_s",
    "Vd",
    "mdot_kgps",
    "B_ref_T",
    "B_profile",
    "transport",
];

/// The N2_PROXY rows of the frozen v1 case file, in file order.
pub fn v1_n2_rows(repo: &Path) -> AbepResult<Vec<Value>> {
    let doc = load_json(repo, V1_CASES_REL, V1_CASES_SHA256)?;
    let cases = ptr(&doc, "/cases", "v1 case file")?.as_list().ok_or_else(|| model("v1 cases is not a list"))?;
    Ok(cases.iter().filter(|c| str_at(c, "/family", "v1 row").ok() == Some("N2_PROXY")).cloned().collect())
}

/// One AIR case: the v1 row's fields, then the AIR identity, chemistry and feed; `case_sha256` last.
pub fn air_case(
    row: &Value,
    family: &str,
    comp: &Composition,
    chemistry: Option<&str>,
    config: &str,
    rate_dir: &str,
) -> AbepResult<Value> {
    let get = |k: &str| ptr(row, &format!("/{k}"), "v1 row").cloned();
    let id = |k: &str| -> AbepResult<String> { Ok(str_at(row, &format!("/{k}"), "v1 row")?.to_string()) };
    let mut key = format!(
        "{family}|{}|{}|{}|{}|{}|{}|{}",
        id("geometry_id")?,
        id("bz_shape_id")?,
        id("B_peak_id")?,
        id("Vd_id")?,
        id("mdot_id")?,
        comp.id,
        id("transport_id")?
    );
    if let Some(ch) = chemistry {
        key.push('|');
        key.push_str(ch);
    }
    let mut d = Dict::new();
    d.insert("key", sval(&key));
    d.insert("id", sval(&key));
    d.insert("family", sval(family));
    for f in V1_FIELDS {
        d.insert(f, get(f)?);
    }
    let mdot = f64_at(row, "/mdot_kgps", "v1 row")?;
    d.insert("composition_id", sval(&comp.id));
    if let Some(ch) = chemistry {
        d.insert("chemistry_id", sval(ch));
    }
    d.insert("propellant_config", sval(config));
    d.insert("rate_dir", sval(rate_dir));
    d.insert("feed", feed(comp, mdot)?);
    d.insert("compact", Value::Bool(true));
    let mut case = Value::Dict(d);
    let h = case_hash(&case)?;
    if let Value::Dict(d) = &mut case {
        d.insert("case_sha256", sval(&h));
    }
    Ok(case)
}

fn composition_value(pts: &[Composition]) -> Value {
    Value::List(
        pts.iter()
            .map(|p| {
                dict(vec![
                    ("id", sval(&p.id)),
                    ("y_O", Value::Float(p.y_o)),
                    ("f_O", Value::Float(p.f_o)),
                    ("f_N", Value::Float(p.f_n)),
                    ("mass_fractions", dict(p.w.iter().map(|(s, w)| (*s, Value::Float(*w))).collect())),
                ])
            })
            .collect(),
    )
}

fn inlet_value() -> AbepResult<Value> {
    let mut d = Dict::new();
    for sp in ["N2", "N", "O2", "O"] {
        d.insert(sp, Value::Float(inlet_velocity(sp)?));
    }
    Ok(dict(vec![
        ("rule", sval("NI-01 (NP-HALL-CHEM-AIR addendum 01)")),
        ("label", sval(INLET_LABEL)),
        ("temperature_K", Value::Float(T_INLET_K)),
        ("velocity_m_s", Value::Dict(d)),
    ]))
}

/// The CA-HALL-AIR-v1 audit case document (addendum 01): v1 rows of the audit selection x 4 corners x AIR-NOM / AIR-ALT.
pub fn build_audit_doc(repo: &Path) -> AbepResult<Value> {
    load_json(repo, CHEM_ADDENDUM01_REL, CHEM_ADDENDUM01_SHA256)?;
    read_verified(&repo.join(CHEM_ADDENDUM01_LOCK_REL), CHEM_ADDENDUM01_LOCK_SHA256)?;
    let pts = composition_points(repo)?;
    let rows: Vec<Value> = v1_n2_rows(repo)?
        .into_iter()
        .filter(|r| {
            let s = |k: &str| str_at(r, &format!("/{k}"), "row").unwrap_or("");
            s("geometry_id") == AUDIT_GEOMETRY
                && s("bz_shape_id") == AUDIT_SHAPE
                && AUDIT_B_PEAK.contains(&s("B_peak_id"))
                && AUDIT_VD.contains(&s("Vd_id"))
                && AUDIT_MDOT.contains(&s("mdot_id"))
        })
        .collect();
    if rows.len() != 8 * 9 {
        return Err(model(format!("audit selection gives {} v1 rows, 72 registered", rows.len())));
    }
    let mut cases = Vec::new();
    for row in &rows {
        for comp in &pts {
            for (ch, snap, _) in AUDIT_CHEMISTRY {
                cases.push(air_case(
                    row,
                    "AIR_AUDIT",
                    comp,
                    Some(ch),
                    &format!("audit_air/configs/{snap}"),
                    "propellants_air",
                )?);
            }
        }
    }
    Ok(dict(vec![
        ("schema", sval(AUDIT_CASES_SCHEMA)),
        ("model_id", sval("NP-HALL-CHEM-AIR")),
        ("audit", sval("CA-HALL-AIR-v1 blind state envelope (addendum 01); not a validation, no measured target")),
        ("status", sval("PREPARED_NOT_RUN")),
        ("prereg_sha256", sval(CHEM_PREREG_SHA256)),
        ("addendum_01_sha256", sval(CHEM_ADDENDUM01_SHA256)),
        ("v1_cases_sha256", sval(V1_CASES_SHA256)),
        ("design_state_set_sha256", sval(abep_data::design_states::DESIGN_STATE_SET_SHA256)),
        ("composition_label", sval(COMPOSITION_LABEL)),
        ("composition_points", composition_value(&pts)),
        ("inlet", inlet_value()?),
        ("mode", sval("vacuum")),
        ("generated_by", sval("abep-air-cases audit-generate (crates/abep-julia-bridge/src/air_cases.rs)")),
        ("n_cases", Value::int(cases.len() as i64)),
        ("cases", Value::List(cases)),
    ]))
}

/// The snapshot MANIFEST of the audit: snapshot configurations (sha256, label, the production file they copy, every rate
/// file's sha256), the bound tables, the case file and the addendum lock.
pub fn audit_manifest(repo: &Path, cases_text: &str) -> AbepResult<Value> {
    let bridge = repo.join(BRIDGE_DIR);
    let mut configs = Dict::new();
    for (id, snap, prod) in AUDIT_CHEMISTRY {
        let rel = format!("{AUDIT_DIR}/configs/{snap}");
        let text = std::fs::read_to_string(repo.join(&rel))
            .map_err(|e| AbepError::Io { path: rel.clone(), message: e.to_string() })?;
        let t: toml::Table = text.parse().map_err(|e: toml::de::Error| schema(&rel, e.to_string()))?;
        let mut rates = BTreeMap::new();
        for r in t.get("reactions").and_then(|x| x.as_array()).ok_or_else(|| schema(&rel, "no reactions"))? {
            let f = r.get("rate_coeff_file").and_then(|x| x.as_str()).ok_or_else(|| schema(&rel, "rate_coeff_file"))?;
            let p = bridge.join("propellants_air").join(f);
            rates.insert(f.to_string(), abep_provenance::sha256_file(&p)?);
        }
        let mut rd = Dict::new();
        for (f, h) in rates {
            rd.insert(f.as_str(), sval(&h));
        }
        configs.insert(
            snap,
            dict(vec![
                ("chemistry_id", sval(id)),
                ("reaction_set", sval(AUDIT_LABEL)),
                ("copy_of", sval(&format!("hallthruster_bridge/propellants_air/{prod} at {AUDIT_LABEL}"))),
                ("sha256", sval(&sha256_hex(text.as_bytes()))),
                ("rate_files", Value::Dict(rd)),
            ]),
        );
    }
    let mut bound = Dict::new();
    for b in AUDIT_BOUND_TABLES {
        bound.insert(b, sval(&abep_provenance::sha256_file(&bridge.join(b))?));
    }
    Ok(dict(vec![
        ("purpose", sval("Immutable CA-HALL-AIR-v1 audit inputs (NP-HALL-CHEM-AIR addendum 01): the state envelope reads these snapshots, never the mutable production configurations; every rate file, bound table and the case file are sha256-pinned; the Julia script refuses any mismatch")),
        ("addendum_lock", sval(CHEM_ADDENDUM01_LOCK_REL)),
        ("addendum_lock_sha256", sval(CHEM_ADDENDUM01_LOCK_SHA256)),
        ("cases", sval(AUDIT_CASES_REL)),
        ("cases_sha256", sval(&sha256_hex(cases_text.as_bytes()))),
        ("configs", Value::Dict(configs)),
        ("bound_tables", Value::Dict(bound)),
        ("status", sval("PREPARED_NOT_RUN")),
    ]))
}

/// (audit case text, audit MANIFEST text).
pub fn generate_audit(repo: &Path) -> AbepResult<(String, String)> {
    let doc = build_audit_doc(repo)?;
    let text = render_case_doc(&doc)?;
    let m = audit_manifest(repo, &text)?;
    let mut mt = pyjson::dumps(&m, &DumpOptions::config_writer()).map_err(|e| model(e.to_string()))?;
    mt.push('\n');
    Ok((text, mt))
}

/// Snapshot rule: every snapshot equals its production configuration at the audit label and names none of the assessed
/// processes' tables.
pub fn check_snapshots(repo: &Path) -> AbepResult<()> {
    let set = abep_chem::hall_air::AirSet::load(repo)?;
    let assessed =
        ["O2_to_O_Z2plus", "attachment_O2", "N_Z2plus_to_N_Z3plus", "N2_to_N2_Z2plus", "N2_Z1plus_to_N2_Z2plus"];
    for (_, snap, prod) in AUDIT_CHEMISTRY {
        let rel = format!("{AUDIT_DIR}/configs/{snap}");
        let text =
            std::fs::read(repo.join(&rel)).map_err(|e| AbepError::Io { path: rel.clone(), message: e.to_string() })?;
        if let Some(a) = assessed.iter().find(|a| String::from_utf8_lossy(&text).contains(*a)) {
            return Err(model(format!("{rel} contains assessed process {a}: snapshot rule")));
        }
        if set.label == AUDIT_LABEL {
            let cur = set.configs.get(prod).ok_or_else(|| model(format!("{prod} not registered")))?;
            if cur.sha256 != sha256_hex(&text) {
                return Err(model(format!("{rel} is not a byte copy of {prod} at {AUDIT_LABEL}")));
            }
        }
    }
    Ok(())
}

/// Write the audit case file and MANIFEST.
pub fn write_audit(repo: &Path) -> AbepResult<()> {
    check_snapshots(repo)?;
    let (cases, man) = generate_audit(repo)?;
    for (rel, t) in [(AUDIT_CASES_REL, &cases), (AUDIT_MANIFEST_REL, &man)] {
        std::fs::write(repo.join(rel), t).map_err(|e| AbepError::Io { path: rel.into(), message: e.to_string() })?;
    }
    Ok(())
}

/// Regenerate in memory; require byte equality with the committed audit case file and MANIFEST. Returns the case count.
pub fn check_audit(repo: &Path) -> AbepResult<usize> {
    check_snapshots(repo)?;
    let (cases, man) = generate_audit(repo)?;
    for (rel, t) in [(AUDIT_CASES_REL, &cases), (AUDIT_MANIFEST_REL, &man)] {
        let have =
            std::fs::read(repo.join(rel)).map_err(|e| AbepError::Io { path: rel.into(), message: e.to_string() })?;
        if have != t.as_bytes() {
            return Err(model(format!("{rel} differs from its deterministic regeneration")));
        }
    }
    let doc = pyjson::loads(&cases).map_err(|e| model(e.to_string()))?;
    Ok(ptr(&doc, "/cases", "audit cases")?.as_list().map(|l| l.len()).unwrap_or(0))
}

/// Freeze audit shard outputs: records sorted by key (unique), gzip (mtime 0), manifest with every shard sha256.
pub fn freeze_audit(repo: &Path, name: &str, shards: &[PathBuf], out_dir: &Path) -> AbepResult<(PathBuf, String)> {
    let cases_sha = abep_provenance::sha256_file(&repo.join(AUDIT_CASES_REL))?;
    let manifest_sha = abep_provenance::sha256_file(&repo.join(AUDIT_MANIFEST_REL))?;
    let mut by_key: BTreeMap<String, String> = BTreeMap::new();
    let mut rows = Vec::new();
    for p in shards {
        let label = p.to_string_lossy().to_string();
        let bytes = std::fs::read(p).map_err(|e| AbepError::Io { path: label.clone(), message: e.to_string() })?;
        let txt = String::from_utf8(bytes.clone()).map_err(|e| schema(&label, e.to_string()))?;
        let mut n = 0usize;
        for line in txt.lines().filter(|l| !l.trim().is_empty()) {
            let v = pyjson::loads(line).map_err(|e| schema(&label, e.to_string()))?;
            let key = str_at(&v, "/key", &label)?.to_string();
            if by_key.insert(key.clone(), line.trim().to_string()).is_some() {
                return Err(model(format!("duplicate record {key} across shards")));
            }
            n += 1;
        }
        let fname = p.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default();
        rows.push(dict(vec![
            ("file", sval(&fname)),
            ("sha256", sval(&sha256_hex(&bytes))),
            ("n_records", Value::int(n as i64)),
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
    let raw = format!("{name}_raw.jsonl.gz");
    std::fs::write(out_dir.join(&raw), &gz).map_err(|e| AbepError::Io { path: raw.clone(), message: e.to_string() })?;
    let m = dict(vec![
        ("schema", sval(AUDIT_RAW_SCHEMA)),
        ("name", sval(name)),
        ("cases_file_sha256", sval(&cases_sha)),
        ("manifest_sha256", sval(&manifest_sha)),
        ("n_records", Value::int(by_key.len() as i64)),
        ("raw_file", sval(&raw)),
        ("raw_sha256", sval(&sha256_hex(&gz))),
        ("shards", Value::List(rows)),
        ("frozen_by", sval("abep-air-cases audit-freeze")),
    ]);
    let mut mt = pyjson::dumps(&m, &DumpOptions::config_writer()).map_err(|e| model(e.to_string()))?;
    mt.push('\n');
    let mp = out_dir.join(format!("{name}_raw_manifest.json"));
    std::fs::write(&mp, &mt)
        .map_err(|e| AbepError::Io { path: mp.to_string_lossy().into(), message: e.to_string() })?;
    Ok((mp, sha256_hex(mt.as_bytes())))
}
