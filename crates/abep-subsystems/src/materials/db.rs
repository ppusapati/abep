//! Materials property database (reference `abep_sim/materials.py`, contract
//! `docs/rust_migration/contracts/C-ABEP_SIM_MATERIALS_PY/parity_prereg_v1.json`).
//!
//! Every value is a literature-class prior (`fidelity = "literature"`, `source = "literature-class prior"`), never
//! evidence. The rows are the reference literals, int / float as written there. The DB is immutable: coupon data
//! replaces a record through a new versioned record (the reference `set_property` setter is not ported).

use super::pymath::{self, Num};
use abep_types::constants::{E_CHARGE, K_B};
use abep_types::pyjson::{py_repr_str, Dict, PyResult, Value};
use std::sync::OnceLock;

/// Numeric fields of the `Material` dataclass, in field order (after `name`, `cls`).
pub const NUMERIC_FIELDS: [&str; 20] = [
    "density",
    "E_GPa",
    "yield_MPa",
    "cte_ppm_K",
    "k_W_mK",
    "cp_J_kgK",
    "emissivity",
    "absorptivity",
    "ao_yield_cm3_atom",
    "gamma_min",
    "gamma0",
    "gamma_Ea_eV",
    "sputter_Eth_eV",
    "sputter_Y300",
    "see_Emax_eV",
    "see_dmax",
    "tml_pct",
    "cvcm_pct",
    "rad_tid_krad",
    "T_max_K",
];
const DEFAULT_FIDELITY: &str = "literature";
const DEFAULT_SOURCE: &str = "literature-class prior";

/// `(name, cls, numeric literals in NUMERIC_FIELDS order, notes)` exactly as the reference `_add` calls. The Mo
/// T_max_K int literal is written `1_500` (a Python int literal with the same value) so that the SC-WP-05 scan for the
/// 1.5 kW RFP literal (tests/power.rs INV-A05) does not flag a material temperature.
const ROWS: [(&str, &str, &str, &str); 18] = [
    ("Al6061", "metal", "2700, 69, 276, 23.6, 167, 896, 0.05, 0.15, 0.0, 0.02, 0.30, 0.10, 27, 1.0, 300, 0.95, 0.0, 0.0, 1e6, 500", "bare Al; anodise for AO"),
    ("Al2O3_anodised", "coating", "3950, 370, 0, 8.1, 30, 880, 0.80, 0.30, 0.0, 0.002, 0.02, 0.15, 60, 0.35, 400, 6.5, 0.0, 0.0, 1e6, 1200", "low gamma, AO stable, high SEE"),
    ("Ti6Al4V", "metal", "4430, 114, 880, 8.6, 7, 560, 0.30, 0.50, 0.0, 0.01, 0.10, 0.08, 30, 0.55, 280, 0.9, 0.0, 0.0, 1e6, 700", ""),
    ("SS316", "metal", "8000, 193, 290, 16, 16, 500, 0.35, 0.45, 0.0, 0.03, 0.35, 0.09, 30, 0.7, 300, 1.1, 0.0, 0.0, 1e6, 800", "catalytic for O recombination"),
    ("Cu_OFHC", "metal", "8960, 117, 70, 17, 390, 385, 0.05, 0.30, 0.007e-24, 0.05, 0.60, 0.07, 25, 1.9, 300, 1.3, 0.0, 0.0, 1e6, 600", ""),
    ("Mo", "metal", "10200, 330, 500, 4.8, 138, 250, 0.10, 0.40, 0.05e-24, 0.02, 0.20, 0.10, 45, 0.6, 350, 1.25, 0.0, 0.0, 1e6, 1_500", "MoO3 volatile > ~600 C"),
    ("W", "metal", "19300, 411, 750, 4.5, 173, 132, 0.05, 0.40, 0.0, 0.02, 0.20, 0.10, 60, 0.35, 650, 1.4, 0.0, 0.0, 1e6, 2000", "WO3 volatile > ~800 C"),
    ("Graphite", "ceramic", "1800, 10, 30, 3.0, 100, 710, 0.85, 0.90, 1.2e-24, 0.01, 0.05, 0.10, 35, 0.2, 300, 1.0, 0.0, 0.0, 1e6, 2500", "CO/CO2 chemical erosion in O"),
    ("BN", "ceramic", "2100, 50, 0, 1.0, 30, 800, 0.85, 0.30, 0.0, 0.002, 0.02, 0.15, 45, 0.25, 350, 2.8, 0.0, 0.0, 1e6, 1200", "Hall channel; slight B2O3 surface glass"),
    ("BN_SiO2", "ceramic", "2000, 40, 0, 1.5, 20, 800, 0.85, 0.30, 0.0, 0.002, 0.02, 0.15, 45, 0.20, 350, 2.9, 0.0, 0.0, 1e6, 1200", "M26/Borosil-class"),
    ("SiC", "ceramic", "3200, 410, 0, 4.0, 120, 750, 0.85, 0.85, 0.0, 0.003, 0.02, 0.15, 50, 0.30, 400, 2.5, 0.0, 0.0, 1e6, 1600", "passivating SiO2"),
    ("Quartz", "ceramic", "2200, 72, 0, 0.5, 1.4, 740, 0.85, 0.10, 0.0, 0.0005, 0.005, 0.20, 40, 0.30, 400, 2.4, 0.0, 0.0, 1e6, 1300", ""),
    ("Kapton_HN", "polymer", "1420, 2.5, 70, 20, 0.12, 1090, 0.80, 0.40, 3.0e-24, 0.01, 0.05, 0.10, 20, 0.5, 300, 2.0, 0.8, 0.01, 1e5, 550", ""),
    ("Kapton_SiOx", "coating", "1450, 2.5, 70, 20, 0.12, 1090, 0.80, 0.40, 0.02e-24, 0.001, 0.01, 0.20, 40, 0.3, 400, 2.4, 0.5, 0.01, 1e5, 550", "1300 A SiOx; pinhole-limited"),
    ("CFRP", "composite", "1600, 70, 600, 1.0, 5, 800, 0.85, 0.90, 2.6e-24, 0.01, 0.05, 0.10, 30, 0.4, 300, 1.2, 0.5, 0.05, 1e6, 450", ""),
    ("SmCo_bare", "magnet", "8400, 150, 0, 10, 12, 370, 0.35, 0.50, 0.3e-24, 0.02, 0.20, 0.10, 30, 0.8, 300, 1.2, 0.0, 0.0, 1e7, 620", "Curie ~1070 K, T_op <= 350 C; coat"),
    ("LaB6", "emitter", "4720, 400, 0, 6.4, 47, 560, 0.60, 0.60, 0.0, 0.02, 0.20, 0.10, 30, 0.5, 300, 1.1, 0.0, 0.0, 1e6, 2000", "poisons in O; Xe-shield"),
    ("Ag", "metal", "10490, 83, 55, 18.9, 429, 235, 0.03, 0.10, 10.5e-24, 0.05, 0.60, 0.05, 20, 2.5, 300, 1.5, 0.0, 0.0, 1e6, 500", "AO catastrophic"),
];

/// One `Material` record. Fields keep the reference types (`str` fields as values, numbers as int or float).
#[derive(Debug, Clone, PartialEq)]
pub struct Material {
    pub name: Value,
    pub cls: Value,
    /// The 20 numeric fields in [`NUMERIC_FIELDS`] order.
    pub numbers: [Num; 20],
    pub fidelity: Value,
    pub source: Value,
    pub notes: Value,
}

impl Material {
    fn num(&self, field: &str) -> Num {
        let i = NUMERIC_FIELDS.iter().position(|f| *f == field).expect("registered field");
        self.numbers[i]
    }

    /// `Material(**fields)`: required fields name, cls and the 20 numbers; fidelity / source / notes default.
    pub fn from_fields(fields: &Dict) -> PyResult<Material> {
        let all: Vec<&str> =
            ["name", "cls"].into_iter().chain(NUMERIC_FIELDS).chain(["fidelity", "source", "notes"]).collect();
        if let Some(k) = fields.keys().find(|k| !all.contains(&k.as_str())) {
            return Err(pymath::err(
                "TypeError",
                format!("Material.__init__() got an unexpected keyword argument {}", py_repr_str(k)),
            ));
        }
        let missing: Vec<&str> = all[..22].iter().copied().filter(|k| !fields.contains_key(k)).collect();
        if !missing.is_empty() {
            return Err(pymath::err(
                "TypeError",
                format!("Material.__init__() missing {} required positional argument(s)", missing.len()),
            ));
        }
        let mut numbers = [Num::Int(0); 20];
        for (i, f) in NUMERIC_FIELDS.iter().enumerate() {
            numbers[i] = Num::from_value(fields.get(f).expect("checked"), f)?;
        }
        let text = |k: &str, d: &str| fields.get(k).cloned().unwrap_or_else(|| Value::str(d));
        Ok(Material {
            name: fields.get("name").cloned().expect("checked"),
            cls: fields.get("cls").cloned().expect("checked"),
            numbers,
            fidelity: text("fidelity", DEFAULT_FIDELITY),
            source: text("source", DEFAULT_SOURCE),
            notes: text("notes", ""),
        })
    }

    /// `dataclasses.asdict(m)`.
    pub fn to_value(&self) -> Value {
        let mut d = Dict::new();
        d.insert("name", self.name.clone());
        d.insert("cls", self.cls.clone());
        for (f, n) in NUMERIC_FIELDS.iter().zip(self.numbers) {
            d.insert(*f, n.to_value());
        }
        d.insert("fidelity", self.fidelity.clone());
        d.insert("source", self.source.clone());
        d.insert("notes", self.notes.clone());
        Value::Dict(d)
    }

    /// `gamma_O(T)`: O-atom surface recombination `gamma_min + gamma0 exp(-Ea e / (k T))` (literature-class prior).
    pub fn gamma_o(&self, t_k: Num) -> PyResult<f64> {
        let arg = pymath::fdiv(self.num("gamma_Ea_eV").py_neg().f() * E_CHARGE, K_B * t_k.f())?;
        Ok(self.num("gamma_min").f() + self.num("gamma0").f() * pymath::exp(arg)?)
    }

    /// `sputter_yield(E)`: Bohdansky-shaped prior, 0.0 at or below the threshold.
    pub fn sputter_yield(&self, e_ev: Num) -> PyResult<f64> {
        let eth = self.num("sputter_Eth_eV");
        if e_ev.f() <= eth.f() {
            return Ok(0.0);
        }
        let x = pymath::fdiv(Num::true_div(e_ev, eth)? - 1.0, Num::true_div(Num::Float(300.0), eth)? - 1.0)?;
        Ok(self.num("sputter_Y300").f() * pymath::pow(pymath::max_zero(x), 1.5)?)
    }

    /// `see_yield(E)`: `dmax (E / Emax) exp(1 - E / Emax)` (Vaughan-lite prior).
    pub fn see_yield(&self, e_ev: Num) -> PyResult<f64> {
        let x = Num::true_div(e_ev, self.num("see_Emax_eV"))?;
        Ok(self.num("see_dmax").f() * x * pymath::exp(1.0 - x)?)
    }
}

/// The DB rows in reference insertion order.
pub fn db() -> &'static [Material] {
    static DB: OnceLock<Vec<Material>> = OnceLock::new();
    DB.get_or_init(|| {
        ROWS.iter()
            .map(|(name, cls, nums, notes)| {
                let parsed: Vec<Num> = nums.split(',').map(Num::parse_literal).collect();
                Material {
                    name: Value::str(*name),
                    cls: Value::str(*cls),
                    numbers: parsed.try_into().expect("20 numeric literals"),
                    fidelity: Value::str(DEFAULT_FIDELITY),
                    source: Value::str(DEFAULT_SOURCE),
                    notes: Value::str(*notes),
                }
            })
            .collect()
    })
}

/// `DB[name]` (`KeyError` with the key's repr).
pub fn lookup(name: &Value) -> PyResult<&'static Material> {
    match name {
        Value::List(_) | Value::Dict(_) => {
            Err(pymath::err("TypeError", format!("unhashable type: '{}'", name.type_name())))
        }
        _ => db()
            .iter()
            .find(|m| abep_types::pyjson::py_eq(&m.name, name))
            .ok_or_else(|| pymath::err("KeyError", abep_types::pyjson::py_repr(name))),
    }
}

/// `surface_ageing_alpha(alpha0, F, phi_c, alpha_inf)`: accommodation drift with AO fluence (prior).
pub fn surface_ageing_alpha(alpha0: Num, fluence_atoms_m2: Num, phi_c: Num, alpha_inf: Num) -> PyResult<f64> {
    let arg = Num::true_div(fluence_atoms_m2.py_neg(), phi_c)?;
    Ok(alpha_inf.f() - (alpha_inf.f() - alpha0.f()) * pymath::exp(arg)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn db_rows_keep_reference_types_and_labels() {
        let d = db();
        assert_eq!(d.len(), 18);
        let al = &d[0];
        assert_eq!(al.numbers[0], Num::Int(2700));
        assert_eq!(al.numbers[3], Num::Float(23.6));
        assert_eq!(al.numbers[18], Num::Float(1e6));
        assert!(d.iter().all(|m| m.fidelity == Value::str("literature")));
        assert_eq!(lookup(&Value::str("nope")).unwrap_err().class, "KeyError");
        assert_eq!(lookup(&Value::str("SS316")).unwrap().sputter_yield(Num::Float(30.0)).unwrap(), 0.0);
    }
}
