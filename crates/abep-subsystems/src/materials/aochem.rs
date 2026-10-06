//! Atomic-oxygen chemistry (reference `abep_sim/aochem.py`, contract
//! `docs/rust_migration/contracts/C-ABEP_SIM_AOCHEM_PY/parity_prereg_v1.json`).
//!
//! Ram AO flux and fluence, Kapton-referenced erosion depth and heterogeneous wall recombination O + O(ads) -> O2
//! (mass conserving: recombined O mass goes to O2). The yields and recombination coefficients are literature-class
//! priors, to be replaced by AO coupon / AO-beam data. The reference's descriptive MATERIAL_CLASS text table (no
//! consumer; emitter rows) is not ported.

use super::pymath::{self, Num};
use abep_types::constants::{E_CHARGE, M_N2, M_O, M_O2};
use abep_types::pyjson::{py_repr, Dict, PyResult, Value};

/// Erosion yield, cm^3 per O atom (5 eV ram O; Kapton reference 3.0e-24), reference insertion order.
pub const EROSION_YIELD_CM3_PER_ATOM: [(&str, f64); 15] = [
    ("kapton_HN", 3.0e-24),
    ("teflon_FEP", 0.05e-24),
    ("epoxy_CFRP", 2.6e-24),
    ("polyimide_coated_SiOx", 0.02e-24),
    ("silver", 10.5e-24),
    ("copper", 0.007e-24),
    ("aluminium", 0.0),
    ("titanium", 0.0),
    ("molybdenum", 0.05e-24),
    ("graphite", 1.2e-24),
    ("carbon_carbon", 0.9e-24),
    ("boron_nitride", 0.0),
    ("alumina", 0.0),
    ("SiC", 0.0),
    ("SmCo_bare", 0.3e-24),
];

/// Effective wall recombination coefficient of O per collision, reference insertion order.
pub const RECOMB_GAMMA: [(&str, f64); 9] = [
    ("aluminium_oxide", 0.005),
    ("stainless_steel", 0.07),
    ("titanium", 0.02),
    ("copper", 0.2),
    ("silver", 0.25),
    ("boron_nitride", 0.003),
    ("alumina", 0.003),
    ("quartz", 0.0005),
    ("gold", 0.03),
];

const AO_FIELDS: [&str; 7] = [
    "intake_wall",
    "compressor_wall",
    "n_wall_collisions_intake",
    "n_wall_collisions_compressor",
    "n_wall_collisions_reservoir",
    "reservoir_wall",
    "wall_T_K",
];

/// `AOParams`: wall materials and wall-collision counts of the gas path (fields keep their Python values).
#[derive(Debug, Clone, PartialEq)]
pub struct AoParams {
    fields: Dict,
}

impl Default for AoParams {
    fn default() -> Self {
        let mut d = Dict::new();
        d.insert("intake_wall", Value::str("aluminium_oxide"));
        d.insert("compressor_wall", Value::str("stainless_steel"));
        d.insert("n_wall_collisions_intake", Value::Float(20.0));
        d.insert("n_wall_collisions_compressor", Value::Float(300.0));
        d.insert("n_wall_collisions_reservoir", Value::Float(50.0));
        d.insert("reservoir_wall", Value::str("titanium"));
        d.insert("wall_T_K", Value::Float(350.0));
        AoParams { fields: d }
    }
}

impl AoParams {
    /// `AOParams(**fields)`: unknown keywords raise `TypeError`; absent fields take the defaults.
    pub fn from_fields(fields: &Dict) -> PyResult<AoParams> {
        let mut p = AoParams::default();
        for (k, v) in fields.iter() {
            if !AO_FIELDS.contains(&k.as_str()) {
                return Err(pymath::err(
                    "TypeError",
                    format!("AOParams.__init__() got an unexpected keyword argument '{k}'"),
                ));
            }
            p.fields.insert(k.clone(), v.clone());
        }
        Ok(p)
    }

    /// `dataclasses.asdict(ao)`.
    pub fn to_value(&self) -> Value {
        Value::Dict(self.fields.clone())
    }

    fn get(&self, k: &str) -> &Value {
        self.fields.get(k).expect("every AOParams field is present")
    }
}

fn table_lookup(table: &[(&str, f64)], key: &Value) -> PyResult<f64> {
    if matches!(key, Value::List(_) | Value::Dict(_)) {
        return Err(pymath::err("TypeError", format!("unhashable type: '{}'", key.type_name())));
    }
    match key {
        Value::Str(s) => table.iter().find(|(k, _)| k == s).map(|(_, v)| *v),
        _ => None,
    }
    .ok_or_else(|| pymath::err("KeyError", py_repr(key)))
}

fn atm_num(atm: &Dict, key: &str) -> PyResult<f64> {
    let v = atm.get(key).ok_or_else(|| pymath::err("KeyError", format!("'{key}'")))?;
    Ok(Num::from_value(v, key)?.f())
}

/// `ao_flux(atm)`: ram AO number density [m^-3], flux [m^-2 s^-1] and kinetic energy [eV].
pub fn ao_flux(atm: &Dict) -> PyResult<Value> {
    let n_o = atm_num(atm, "rho")? * atm_num(atm, "fO")? / M_O;
    let v = atm_num(atm, "V")?;
    let flux = n_o * v;
    let e_ev = 0.5 * M_O * pymath::pow(v, 2.0)? / E_CHARGE;
    let mut d = Dict::new();
    d.insert("n_O", Value::Float(n_o));
    d.insert("ao_flux", Value::Float(flux));
    d.insert("ao_energy_eV", Value::Float(e_ev));
    Ok(Value::Dict(d))
}

fn flux_of(atm: &Dict) -> PyResult<f64> {
    let n_o = atm_num(atm, "rho")? * atm_num(atm, "fO")? / M_O;
    let v = atm_num(atm, "V")?;
    let _ = pymath::pow(v, 2.0)?;
    Ok(n_o * v)
}

/// `fluence(atm, hours)` [atoms m^-2].
pub fn fluence(atm: &Dict, hours: f64) -> PyResult<f64> {
    Ok(flux_of(atm)? * hours * 3600.0)
}

/// `erosion_depth_um(material, fluence, exposure_factor)`: yield x fluence [atoms cm^-2] x exposure factor, in um.
pub fn erosion_depth_um(material: &Value, fl_atoms_m2: f64, exposure_factor: f64) -> PyResult<f64> {
    let y = table_lookup(&EROSION_YIELD_CM3_PER_ATOM, material)?;
    Ok(y * (fl_atoms_m2 * 1e-4) * exposure_factor * 1e4)
}

/// `recombination_fraction(ao)`: fraction of the incoming O that reaches the thruster as atomic O,
/// prod over the intake / compressor / reservoir walls of (1 - gamma)^N.
pub fn recombination_fraction(ao: &AoParams) -> PyResult<f64> {
    let mut surv = 1.0;
    for (wall, n) in [
        ("intake_wall", "n_wall_collisions_intake"),
        ("compressor_wall", "n_wall_collisions_compressor"),
        ("reservoir_wall", "n_wall_collisions_reservoir"),
    ] {
        let g = table_lookup(&RECOMB_GAMMA, ao.get(wall))?;
        let n = Num::from_value(ao.get(n), n)?.f();
        surv *= pymath::pow(1.0 - g, n)?;
    }
    Ok(surv)
}

/// `inlet_composition(atm, ao)`: mass fractions delivered to the thruster after wall recombination (O -> O2).
pub fn inlet_composition(atm: &Dict, ao: &AoParams) -> PyResult<Value> {
    let s = recombination_fraction(ao)?;
    let f_o = atm_num(atm, "fO")? * s;
    let f_o2 = atm_num(atm, "fO2")? + atm_num(atm, "fO")? * (1.0 - s);
    let f_n2_value = atm.get("fN2").ok_or_else(|| pymath::err("KeyError", "'fN2'"))?.clone();
    let f_n2 = Num::from_value(&f_n2_value, "fN2")?.f();
    let m_mean = pymath::fdiv(1.0, f_o / M_O + f_n2 / M_N2 + f_o2 / M_O2)?;
    // O2 -> 2 O costs 5.12 eV per molecule before O+ can form, if the discharge dissociates it.
    let diss = f_o2 * (5.12 * E_CHARGE) / M_O2;
    let mut d = Dict::new();
    d.insert("fO", Value::Float(f_o));
    d.insert("fN2", f_n2_value);
    d.insert("fO2", Value::Float(f_o2));
    d.insert("O_survival", Value::Float(s));
    d.insert("m_mean_inlet", Value::Float(m_mean));
    d.insert("diss_sink_J_per_kg", Value::Float(diss));
    Ok(Value::Dict(d))
}

/// `material_report(atm, hours, materials, exposure_factor)`: erosion depth per material at the mission fluence.
/// An absent or empty material list means every material of the yield table.
pub fn material_report(atm: &Dict, hours: f64, materials: &[Value], exposure_factor: f64) -> PyResult<Value> {
    let fl = fluence(atm, hours)?;
    let all: Vec<Value> = EROSION_YIELD_CM3_PER_ATOM.iter().map(|(k, _)| Value::str(*k)).collect();
    let names = if materials.is_empty() { &all[..] } else { materials };
    let mut rows = Vec::with_capacity(names.len());
    for m in names {
        let mut d = Dict::new();
        d.insert("material", m.clone());
        d.insert("erosion_um", Value::Float(erosion_depth_um(m, fl, exposure_factor)?));
        d.insert("fluence_atoms_m2", Value::Float(fl));
        rows.push(Value::Dict(d));
    }
    Ok(Value::List(rows))
}

/// The two numeric tables and the AOParams defaults.
pub fn tables() -> Value {
    let table = |t: &[(&str, f64)]| {
        let mut d = Dict::new();
        for (k, v) in t {
            d.insert(*k, Value::Float(*v));
        }
        Value::Dict(d)
    };
    let mut d = Dict::new();
    d.insert("EROSION_YIELD_CM3_PER_ATOM", table(&EROSION_YIELD_CM3_PER_ATOM));
    d.insert("RECOMB_GAMMA", table(&RECOMB_GAMMA));
    d.insert("AOParams", AoParams::default().to_value());
    Value::Dict(d)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recombination_split_conserves_mass() {
        let mut atm = Dict::new();
        for (k, v) in [("rho", 2.5e-10), ("fO", 0.6), ("fN2", 0.35), ("fO2", 0.05), ("V", 7784.0)] {
            atm.insert(k, Value::Float(v));
        }
        let r = inlet_composition(&atm, &AoParams::default()).unwrap();
        let d = r.as_dict().unwrap();
        let get = |k: &str| match d.get(k).unwrap() {
            Value::Float(x) => *x,
            _ => panic!(),
        };
        assert!((get("fO") + get("fO2") + get("fN2") - 1.0).abs() < 1e-14);
        assert!(get("O_survival") > 0.0 && get("O_survival") < 1.0);
    }
}
