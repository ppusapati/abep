//! The two computed blocks of the H-1 lifetime / atomic-oxygen register (reference
//! `docs/experiments/lifetime_ao/build_ao_lifetime_register.py::compute_ao_environment` /
//! `compute_wall_sputter_index`, contract
//! `docs/rust_migration/contracts/C-DOCS_EXPERIMENTS_LIFETIME_AO-AO_REGISTER_KERNELS/parity_prereg_v1.json`).
//!
//! * The external ram AO environment at the register altitudes from the FROZEN NRLMSIS 2.1 table (read through
//!   `abep-data`, plus the register's own sha256 pin) times circular orbital velocity, and illustrative recession
//!   equivalents from MISSE 2 flight erosion yields (NASA/TM-2006-214482 Table 4). Model-derived, ILLUSTRATIVE,
//!   evidence level 6: never a design value or a verdict. `RFP_MISSION_H` is the register's labelled exposure horizon
//!   (data); no comparison against it is made here.
//! * An index (no yield values) of the lane 32 sputter-yield database.

use crate::materials::pymath;
use crate::power::pyfmt::round_sig;
use abep_types::pyjson::{float_repr, loads, read_text_utf8, Dict, PyException, PyResult, Value};
use std::path::Path;

pub const ATMOSPHERE_CSV_REL: &str = "abep_sim/data/atmosphere_msis21_v1.csv";
pub const ATMOSPHERE_CSV_SHA256: &str = "5e108c6e5cb7c03ed9b741233fafbc71c7813987e1ff3d0596b04c99c4a9bff7";
pub const WALL_LIFE_DB_REL: &str = "docs/evidence/wall_life/sputter_yield_db_v1.json";
pub const WALL_LIFE_DB_SHA256: &str = "315fbd44da2ee16246edb95830be09e0f05b9237cd5ca0a4c86a02a7e25bfffa";
/// RFP envelope 180-230 km.
pub const ALTITUDES_KM: [i64; 3] = [180, 200, 230];

// Constants transcribed by the reference from abep_sim/constants.py.
const AMU_KG: f64 = 1.66053906660e-27;
const M_O_AMU: f64 = 16.0;
const MU_EARTH_M3_S2: f64 = 3.986004418e14;
const R_EARTH_M: f64 = 6371.0e3;
const E_CHARGE_C: f64 = 1.602176634e-19;
/// The register's RFP mission exposure horizon (26,000 h), a labelled input of the fluence column.
const RFP_MISSION_H: f64 = 26000.0;
/// NASA/TM-2006-214482 p. 15 (Kapton H witness mass loss), atoms / cm^2.
const MISSE2_FLUENCE_ATOMS_CM2: f64 = 8.43e21;

/// MISSE 2 PEACE flight erosion yields, NASA/TM-2006-214482 Table 4 (printed p. 17):
/// (id, material, abbreviation, erosion yield cm^3 / atom, role on an EP unit).
const MISSE2_YIELDS: [(&str, &str, &str, f64, &str); 8] = [
    ("MISSE2-2-E5-30", "Polyimide (PMDA)", "PI (Kapton H)", 3.00e-24, "MLI / harness film; the AO fluence witness"),
    ("MISSE2-2-E5-31", "Polyimide (PMDA)", "PI (Kapton HN)", 2.81e-24, "MLI / harness film"),
    ("MISSE2-2-E5-32", "Polyimide (BPDA)", "PI (Upilex-S)", 9.22e-25, "MLI / harness film"),
    ("MISSE2-2-E5-37", "Polyetheretherkeytone", "PEEK", 2.99e-24, "structural / connector polymer"),
    ("MISSE2-2-E5-42", "Fluorinated ethylene propylene", "FEP", 2.00e-25, "MLI outer layer / wire insulation"),
    ("MISSE2-2-E5-43", "Polytetrafluoroethylene", "PTFE", 1.42e-25, "wire insulation / spacers"),
    ("MISSE2-2-E5-41", "Tetrafluorethylene-ethylene copolymer", "ETFE (Tefzel)", 9.61e-25, "wire insulation"),
    ("MISSE2-2-E5-25", "Graphite", "PG", 4.15e-25, "graphite / carbon parts (pyrolytic graphite sample)"),
];

const FLAGS: [&str; 6] = [
    "RAM_NORMAL_UPPER_BOUND: flux onto a surface facing the ram direction at normal incidence. An ABEP thruster sits \
     behind the intake; the actual exposure of each H-1 exterior surface is TBD - requires the spacecraft layout and a \
     free-molecular / DSMC view-factor analysis (owner/system design).",
    "NO_COROTATION_NO_THERMAL: atmospheric co-rotation and O thermal motion are neglected (they change the relative \
     speed and let non-ram surfaces receive flux).",
    "FROZEN_SCENARIO_ONLY: one epoch, orbit-averaged; no solar-cycle-averaged mission profile. The F10.7 70-230 columns \
     bracket activity; the mission F10.7 history is TBD - requires the mission profile.",
    "COMPOSITION_SUM: fO is the O mass fraction of O+N2+O2 while rho includes the dropped species (He, H, Ar, N; < 2 % \
     by mass at 180-230 km per the frozen metadata), so n_O is high by at most that share.",
    "OTHER_ENVIRONMENT (recession only): MISSE 2 yields are ISS-exterior values (planning orbit 400 km, 51.6 deg; AO \
     with solar UV and charged particles). The source states an average ram impact energy of 4.5 eV at ISS altitude \
     (DEGROH2006 printed p. 1, review statement citing its ref. [1]); E_ram here is model-derived for 180-230 km (see \
     table, ~5 eV). The ~0.5 eV difference and any energy dependence of the yield are NOT corrected for; no energy or \
     synergy correction is applied, so the MISSE yields transfer only as an uncorrected illustration.",
    "FLUENCE_EXTRAPOLATION (recession only): mission fluences exceed the MISSE 2 fluence by the \
     'ratio_to_misse2_fluence' factor; a linear yield beyond the tested fluence is ASSUMED.",
];

fn runtime(message: String) -> PyException {
    pymath::err("RuntimeError", message)
}

fn sha256_of(root: &Path, rel: &str) -> PyResult<(Vec<u8>, String)> {
    let path = root.join(rel);
    let bytes = std::fs::read(&path)
        .map_err(|e| pymath::err("FileNotFoundError", format!("[Errno 2] {e}: '{}'", path.display())))?;
    let sha = abep_provenance::sha256_hex(&bytes);
    Ok((bytes, sha))
}

/// `round(x, 6)` for the grid keys (decimal rounding of the exact binary value).
fn round6(x: f64) -> f64 {
    format!("{x:.6}").parse().expect("decimal")
}

fn s(text: &str) -> Value {
    Value::str(text)
}

fn f(x: f64) -> Value {
    Value::Float(x)
}

fn dict<const N: usize>(items: [(&str, Value); N]) -> Value {
    let mut d = Dict::new();
    for (k, v) in items {
        d.insert(k, v);
    }
    Value::Dict(d)
}

/// An altitude of the register list (int or float, as given).
#[derive(Debug, Clone, Copy)]
pub enum Altitude {
    Int(i64),
    Float(f64),
}

impl Altitude {
    fn km(self) -> f64 {
        match self {
            Altitude::Int(i) => i as f64,
            Altitude::Float(x) => x,
        }
    }

    fn value(self) -> Value {
        match self {
            Altitude::Int(i) => Value::int(i),
            Altitude::Float(x) => Value::Float(x),
        }
    }

    fn text(self) -> String {
        match self {
            Altitude::Int(i) => i.to_string(),
            Altitude::Float(x) => float_repr(x),
        }
    }
}

/// `compute_ao_environment()` with the register altitudes and the pinned atmosphere sha256 as arguments.
pub fn compute_ao_environment(root: &Path, csv_sha256: &str, altitudes: &[Altitude]) -> PyResult<Value> {
    let (_, sha) = sha256_of(root, ATMOSPHERE_CSV_REL)?;
    if sha != csv_sha256 {
        return Err(runtime(format!(
            "{ATMOSPHERE_CSV_REL} sha256 {sha} != pinned {csv_sha256}; the frozen atmosphere changed. Re-pin only \
             after an intentional, logged rebuild (CLAUDE.md rule 1)."
        )));
    }
    let pins = abep_data::pins::FrozenPins::load(root).map_err(|e| runtime(e.to_string()))?;
    let atm = abep_data::msis21_v1::load(root, &pins).map_err(|e| runtime(e.to_string()))?;
    let m_o = M_O_AMU * AMU_KG;
    let mut table = Vec::new();
    let mut fl_unrounded = Vec::new();
    for &alt in altitudes {
        let v = pymath::sqrt(MU_EARTH_M3_S2 / (R_EARTH_M + alt.km() * 1e3))?;
        let e_ram_ev = 0.5 * m_o * v * v / E_CHARGE_C;
        for col in &atm.columns {
            let f107 = round6(col.f107);
            let i = col.alt_km.iter().position(|a| round6(*a) == round6(alt.km())).ok_or_else(|| {
                runtime(format!(
                    "frozen atmosphere has no grid row at {} km / F10.7 {}; no interpolation is performed by this \
                     builder",
                    alt.text(),
                    float_repr(f107)
                ))
            })?;
            let (rho, fo) = (col.rho[i], col.f_o[i]);
            let n_o_m3 = rho * fo / m_o;
            let flux_cm2s = n_o_m3 * v * 1e-4;
            let fl_1000h = flux_cm2s * 1000.0 * 3600.0;
            let fl_mission = flux_cm2s * RFP_MISSION_H * 3600.0;
            fl_unrounded.push(fl_mission);
            table.push(dict([
                ("alt_km", alt.value()),
                ("f107", f(f107)),
                ("rho_kg_m3", f(round_sig(rho, 6))),
                ("fO_mass_fraction", f(round_sig(fo, 6))),
                ("n_O_m3", f(round_sig(n_o_m3, 6))),
                ("V_orb_m_s", f(round_sig(v, 6))),
                ("E_ram_O_eV", f(round_sig(e_ram_ev, 4))),
                ("ram_flux_atoms_cm2_s", f(round_sig(flux_cm2s, 4))),
                ("fluence_per_1000h_atoms_cm2", f(round_sig(fl_1000h, 4))),
                ("fluence_rfp_mission_26000h_atoms_cm2", f(round_sig(fl_mission, 4))),
                ("ratio_to_misse2_fluence", f(round_sig(fl_mission / MISSE2_FLUENCE_ATOMS_CM2, 6))),
            ]));
        }
    }
    // Recession equivalents at the envelope extremes, from the UNROUNDED mission fluences.
    let first_min = |better: fn(f64, f64) -> bool| -> PyResult<f64> {
        let mut it = fl_unrounded.iter();
        let mut m = *it.next().ok_or_else(|| pymath::err("ValueError", "min() arg is an empty sequence"))?;
        for &x in it {
            if better(x, m) {
                m = x;
            }
        }
        Ok(m)
    };
    let fl_min = first_min(|x, m| x < m)?;
    let fl_max = first_min(|x, m| x > m)?;
    let recession: Vec<Value> = MISSE2_YIELDS
        .iter()
        .map(|(mid, mat, abbr, ey, role)| {
            dict([
                ("id", s(mid)),
                ("material", s(mat)),
                ("abbreviation", s(abbr)),
                ("role_on_ep_unit", s(role)),
                ("misse2_erosion_yield_cm3_per_atom", f(*ey)),
                (
                    "yield_source",
                    dict([
                        ("source_id", s("DEGROH2006")),
                        ("locator", s("Table 4, p. 17")),
                        ("evidence_level", Value::int(3)),
                        ("evidence_class", s("measured")),
                        (
                            "note",
                            s("flight mass loss / (area x density x Kapton-H-witness fluence), Eq. (1)-(3) p. 2; \
                               Kapton H yield itself is the reference 3.0e-24 cm3/atom (p. 2, citing Banks 1997 [4]), \
                               so every yield is relative to that calibration"),
                        ),
                    ]),
                ),
                ("illustrative_recession_um_at_min_mission_fluence", f(round_sig(ey * fl_min * 1e4, 3))),
                ("illustrative_recession_um_at_max_mission_fluence", f(round_sig(ey * fl_max * 1e4, 3))),
            ])
        })
        .collect();
    Ok(dict([
        (
            "status",
            s("model-derived; ILLUSTRATIVE (sets the witness-exposure target scale; not a design value, not a verdict)"),
        ),
        ("evidence_class", s("model-derived")),
        ("evidence_level", Value::int(6)),
        (
            "inputs",
            dict([
                (
                    "atmosphere",
                    dict([
                        ("path", s(ATMOSPHERE_CSV_REL)),
                        ("sha256", s(csv_sha256)),
                        (
                            "model",
                            s("NRLMSIS 2.1 frozen scenario (abep_sim/data/atmosphere_msis21_v1.json): epoch \
                               2028-03-21T12:00, ap 15, F10.7A = F10.7, orbit-averaged lat -60..60 x 4 longitudes"),
                        ),
                    ]),
                ),
                (
                    "constants",
                    dict([
                        ("amu_kg", f(AMU_KG)),
                        ("m_O_amu", f(M_O_AMU)),
                        ("mu_earth_m3_s2", f(MU_EARTH_M3_S2)),
                        ("R_earth_m", f(R_EARTH_M)),
                        ("e_C", f(E_CHARGE_C)),
                        ("source", s("abep_sim/constants.py (read-only)")),
                    ]),
                ),
                ("rfp_mission_h", f(RFP_MISSION_H)),
                (
                    "misse2_fluence_atoms_cm2",
                    dict([
                        ("value", f(MISSE2_FLUENCE_ATOMS_CM2)),
                        ("source_id", s("DEGROH2006")),
                        ("locator", s("p. 15")),
                        ("evidence_class", s("measured")),
                        ("note", s("from two Kapton H witness samples; ISS exterior, ~4 years")),
                    ]),
                ),
            ]),
        ),
        (
            "equations",
            dict([
                ("n_O", s("n_O = rho * fO / m_O  (same relation as abep_sim.atmosphere 'n_O')")),
                ("V_orb", s("V = sqrt(mu / (R_E + h))  (abep_sim.atmosphere.orbital_velocity)")),
                (
                    "E_ram",
                    s("E = 0.5 * m_O * V^2 / e  (kinetic energy of an O atom in the spacecraft frame, co-rotation and \
                       thermal motion neglected; compare DEGROH2006 p. 1: 4.5 eV average at ISS altitude, review \
                       statement)"),
                ),
                ("flux", s("Gamma = n_O * V  (ram-normal surface)")),
                ("fluence", s("F = Gamma * t")),
                ("recession_equivalent", s("x = E_y * F  (linear, fluence-independent yield ASSUMED)")),
            ]),
        ),
        ("flags", Value::List(FLAGS.iter().map(|t| s(t)).collect())),
        ("table", Value::List(table)),
        (
            "illustrative_recession_equivalents",
            dict([
                (
                    "status",
                    s("ILLUSTRATIVE, OUT_OF_DOMAIN (flags above). Shows only that polymer exterior parts on a \
                       ram-exposed surface would not survive the mission fluence unprotected; it is never a design \
                       margin, a coating thickness or a verdict. Metals, BN, alumina and other ceramics: no open \
                       erosion yield accessed by this lane -> TBD (AOL-EX-01)."),
                ),
                (
                    "mission_fluence_range_atoms_cm2",
                    Value::List(vec![f(round_sig(fl_min, 6)), f(round_sig(fl_max, 6))]),
                ),
                (
                    "rounding",
                    s("computed from unrounded fluences; stored fluence 4 significant figures, ratio and range 6, \
                       recession 3"),
                ),
                ("rows", Value::List(recession)),
            ]),
        ),
    ]))
}

fn key_error(k: &str) -> PyException {
    pymath::err("KeyError", format!("'{k}'"))
}

fn item<'a>(v: &'a Value, k: &str) -> PyResult<&'a Value> {
    match v {
        Value::Dict(d) => d.get(k).ok_or_else(|| key_error(k)),
        Value::List(_) => Err(pymath::err("TypeError", "list indices must be integers or slices, not str")),
        Value::Str(_) => Err(pymath::err("TypeError", "string indices must be integers")),
        other => Err(pymath::err("TypeError", format!("'{}' object is not subscriptable", other.type_name()))),
    }
}

fn get<'a>(v: &'a Value, k: &str) -> PyResult<Option<&'a Value>> {
    match v {
        Value::Dict(d) => Ok(d.get(k)),
        other => Err(pymath::err("AttributeError", format!("'{}' object has no attribute 'get'", other.type_name()))),
    }
}

fn items(v: &Value) -> PyResult<Vec<(String, Value)>> {
    match v {
        Value::Dict(d) => Ok(d.iter().map(|(k, v)| (k.clone(), v.clone())).collect()),
        other => Err(pymath::err("AttributeError", format!("'{}' object has no attribute 'items'", other.type_name()))),
    }
}

fn py_len(v: &Value) -> PyResult<i64> {
    match v {
        Value::List(l) => Ok(l.len() as i64),
        Value::Dict(d) => Ok(d.len() as i64),
        Value::Str(t) => Ok(t.chars().count() as i64),
        other => Err(pymath::err("TypeError", format!("object of type '{}' has no len()", other.type_name()))),
    }
}

fn iterate(v: &Value) -> PyResult<Vec<Value>> {
    match v {
        Value::List(l) => Ok(l.clone()),
        Value::Dict(d) => Ok(d.keys().map(|k| Value::str(k.clone())).collect()),
        Value::Str(t) => Ok(t.chars().map(|c| Value::str(c.to_string())).collect()),
        other => Err(pymath::err("TypeError", format!("'{}' object is not iterable", other.type_name()))),
    }
}

/// `compute_wall_sputter_index()` over the database at `db_rel` (bytes `db_bytes` when given, else the file under
/// `root`) with its pinned sha256.
pub fn compute_wall_sputter_index(
    root: &Path,
    db_rel: &str,
    db_sha256: &str,
    db_bytes: Option<&[u8]>,
) -> PyResult<Value> {
    let (bytes, sha) = match db_bytes {
        Some(b) => (b.to_vec(), abep_provenance::sha256_hex(b)),
        None => sha256_of(root, db_rel)?,
    };
    if sha != db_sha256 {
        return Err(runtime(format!(
            "{db_rel} sha256 {sha} != pinned {db_sha256}; lane 32 changed. Re-read it and re-pin deliberately."
        )));
    }
    let db = loads(&read_text_utf8(&bytes)?)?;
    let mut entries = Vec::new();
    for e in iterate(item(&db, "entries")?)? {
        let er = item(&e, "energy_range_eV")?;
        let data = get(&e, "data")?;
        let n_rows = match data {
            Some(d @ Value::Dict(_)) => match get(d, "rows")? {
                Some(Value::List(rows)) => Value::int(rows.len() as i64),
                _ => Value::Null,
            },
            _ => Value::Null,
        };
        let opt = |v: PyResult<Option<&Value>>| -> PyResult<Value> { Ok(v?.cloned().unwrap_or(Value::Null)) };
        let mut d = Dict::new();
        d.insert("entry_id", item(&e, "id")?.clone());
        d.insert("projectile", item(&e, "projectile")?.clone());
        d.insert("target", item(&e, "target")?.clone());
        d.insert("energy_min_eV", opt(get(er, "min"))?);
        d.insert("energy_max_eV", opt(get(er, "max"))?);
        d.insert("energy_note", opt(get(er, "tbd"))?);
        d.insert("incidence_angles_deg", item(&e, "incidence_angles_deg")?.clone());
        d.insert("evidence_level", item(&e, "evidence_level")?.clone());
        d.insert("evidence_class", item(&e, "evidence_class")?.clone());
        d.insert("units", item(&e, "units")?.clone());
        d.insert("n_rows_transcribed", n_rows);
        d.insert("values_status", item(&e, "values_status")?.clone());
        d.insert("source_ids_lane32", item(&e, "source")?.clone());
        d.insert("source_locator", item(&e, "source_locator")?.clone());
        entries.push(Value::Dict(d));
    }
    let mut coverage = Vec::new();
    for (proj, targets) in items(item(&db, "coverage_matrix")?)? {
        if proj == "legend" {
            continue;
        }
        for (tgt, c) in items(&targets)? {
            let status = item(&c, "status")?.clone();
            let ents = item(&c, "entries")?;
            let mut d = Dict::new();
            d.insert("projectile", Value::str(proj.clone()));
            d.insert("target", Value::str(tgt));
            d.insert("status", status);
            d.insert("n_entries", Value::int(py_len(ents)?));
            d.insert("entries", ents.clone());
            coverage.push(Value::Dict(d));
        }
    }
    let input = dict([
        ("path", s(db_rel)),
        ("sha256", s(db_sha256)),
        ("db_id", item(&db, "id")?.clone()),
        ("db_version", item(&db, "version")?.clone()),
        ("db_date", item(&db, "date")?.clone()),
    ]);
    let legend = item(item(&db, "coverage_matrix")?, "legend")?.clone();
    Ok(dict([
        (
            "status",
            s("INDEX of a referenced lane record (lane 32). Yield values are not copied: look them up in the lane 32 \
               database by entry_id. Every Xe+ entry is another projectile and every O+ entry is on a proxy target \
               (B, B2O3, C) or closed-access (Al2O3); none is an H-1 wall-grade N/O yield."),
        ),
        ("input", input),
        ("coverage_legend", legend),
        ("coverage", Value::List(coverage)),
        ("entries", Value::List(entries)),
    ]))
}
