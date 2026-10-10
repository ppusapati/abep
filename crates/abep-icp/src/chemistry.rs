//! IN-16 chemistry: species, reactions, rate sources, validity entries and the process-class completeness gate
//! (prereg sec. 8). Nothing here comes from `abep_sim/plasma_chem.py` (EX-01).
//!
//! Rate coefficients (EQ-06) are the direct Maxwellian integral of each registered source representation, through the
//! admitted abep-chem port of `rate_tables.maxwellian_rate` (`abep_chem::checked`) and the IF-CHEM-REG-v1 registry
//! (`data/chemistry/icp/`, NP-ICP-NEUTRALIZER addendum 02). No rate is computed in abep-icp. A registered table without
//! a registered representation has no rate (INCOMPLETE_EVIDENCE); its 1 eV `.dat` interpolation exists only as the
//! NV-06 / UQ-06 cross-check. Synthetic analytic rates exist for the SYNTHETIC_TEST_ONLY verification cases.

use abep_types::{AbepError, AbepResult};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

/// A heavy species (neutral when `charge` = 0). Electrons are implicit.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SpeciesDef {
    pub name: String,
    pub mass_kg: f64,
    pub charge: u32,
    /// Element composition, e.g. {"N": 2}.
    pub elements: BTreeMap<String, u32>,
    /// Supports negative ions (no balance exists in v1: DOM-12).
    pub electronegative: bool,
    /// Ions: neutral products of wall neutralization (EQ-02 w_s,k), element-conserving.
    pub wall_products: Vec<(String, u32)>,
    /// Atoms: the molecule credited by wall recombination (EQ-02).
    pub recombines_to: Option<String>,
}

/// Reaction classes of the registered sets.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ReactionKind {
    Ionization,
    DissociativeIonization,
    Dissociation,
    ExcitationElectronic,
    ExcitationVibrational,
    ExcitationRotational,
    ElasticMomentumTransfer,
}

impl ReactionKind {
    /// Changes the heavy-species composition (enters the particle balances).
    pub fn changes_species(self) -> bool {
        matches!(self, ReactionKind::Ionization | ReactionKind::DissociativeIonization | ReactionKind::Dissociation)
    }

    pub fn process_class(self) -> ProcessClass {
        match self {
            ReactionKind::Ionization => ProcessClass::Ionization,
            ReactionKind::DissociativeIonization => ProcessClass::DissociativeIonization,
            ReactionKind::Dissociation => ProcessClass::Dissociation,
            ReactionKind::ExcitationElectronic => ProcessClass::ExcitationElectronic,
            ReactionKind::ExcitationVibrational => ProcessClass::ExcitationVibrational,
            ReactionKind::ExcitationRotational => ProcessClass::ExcitationRotational,
            ReactionKind::ElasticMomentumTransfer => ProcessClass::ElasticLoss,
        }
    }
}

/// SYNTHETIC_TEST_ONLY analytic rate k = k0 (T_e/t_ref)^power exp(-e_act/T_e - T_e/t_cut) [m^3/s]. Never evidence.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SyntheticRate {
    pub k0_m3_s: f64,
    pub t_ref_ev: f64,
    pub power: f64,
    pub e_act_ev: f64,
    pub t_cut_ev: Option<f64>,
}

impl SyntheticRate {
    pub fn eval(&self, t_e_ev: f64) -> f64 {
        let cut = self.t_cut_ev.map_or(0.0, |c| t_e_ev / c);
        self.k0_m3_s * (t_e_ev / self.t_ref_ev).powf(self.power) * (-self.e_act_ev / t_e_ev - cut).exp()
    }
}

/// Where a rate coefficient comes from.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RateSource {
    Synthetic {
        rate: SyntheticRate,
    },
    /// A table registered as an IF-CHEM-REG-v1 channel, named by its `.dat` file: the rate is the direct integral of the
    /// channel's representation through `abep_chem::checked` (EQ-06); the `.dat` is a cross-check only.
    RegisteredTable {
        file: String,
    },
}

/// The `rate_validity.toml` entry of a reaction's table (prereg sec. 8 semantics).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Validity {
    Verified { max_mean_energy_ev: f64 },
    Unresolved,
    MissingEntry,
}

/// One electron-impact reaction r: e + target -> products (+ electrons).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReactionDef {
    pub id: String,
    pub kind: ReactionKind,
    pub target: String,
    pub products: Vec<(String, u32)>,
    /// E_r [eV]: the registered threshold (table header).
    pub threshold_ev: f64,
    pub rate: RateSource,
    pub validity: Validity,
}

/// Process classes of the completeness gate (prereg chemistry.process_class_completeness_gate).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ProcessClass {
    Ionization,
    ExcitationElectronic,
    ExcitationVibrational,
    ExcitationRotational,
    Dissociation,
    DissociativeIonization,
    ElasticLoss,
    IonNeutralMomentumTransfer,
    WallAtomRecombination,
    WallMetastableDeexcitation,
    VolumeRecombination,
    AttachmentNegativeIons,
}

impl ProcessClass {
    pub const ALL: [ProcessClass; 12] = [
        ProcessClass::Ionization,
        ProcessClass::ExcitationElectronic,
        ProcessClass::ExcitationVibrational,
        ProcessClass::ExcitationRotational,
        ProcessClass::Dissociation,
        ProcessClass::DissociativeIonization,
        ProcessClass::ElasticLoss,
        ProcessClass::IonNeutralMomentumTransfer,
        ProcessClass::WallAtomRecombination,
        ProcessClass::WallMetastableDeexcitation,
        ProcessClass::VolumeRecombination,
        ProcessClass::AttachmentNegativeIons,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            ProcessClass::Ionization => "IONIZATION",
            ProcessClass::ExcitationElectronic => "EXCITATION_ELECTRONIC",
            ProcessClass::ExcitationVibrational => "EXCITATION_VIBRATIONAL",
            ProcessClass::ExcitationRotational => "EXCITATION_ROTATIONAL",
            ProcessClass::Dissociation => "DISSOCIATION",
            ProcessClass::DissociativeIonization => "DISSOCIATIVE_IONIZATION",
            ProcessClass::ElasticLoss => "ELASTIC_LOSS",
            ProcessClass::IonNeutralMomentumTransfer => "ION_NEUTRAL_MOMENTUM_TRANSFER",
            ProcessClass::WallAtomRecombination => "WALL_ATOM_RECOMBINATION",
            ProcessClass::WallMetastableDeexcitation => "WALL_METASTABLE_DEEXCITATION",
            ProcessClass::VolumeRecombination => "VOLUME_RECOMBINATION",
            ProcessClass::AttachmentNegativeIons => "ATTACHMENT_NEGATIVE_IONS",
        }
    }
}

/// How a process class is addressed for a species: modelled with a registered source, or excluded with a written
/// justification (a source or a bound).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ClassAddress {
    Modelled { by: String },
    Excluded { justification: String },
}

/// A chemistry set with its registered T_e domain (DOM-02).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ChemistrySet {
    pub set_id: String,
    pub species: Vec<SpeciesDef>,
    pub reactions: Vec<ReactionDef>,
    pub process_classes: BTreeMap<String, BTreeMap<ProcessClass, ClassAddress>>,
    pub t_e_domain_ev: [f64; 2],
    /// Lower T_e bound of vibrational / rotational tables (DOM-02: 0.2 eV for the N2/N set).
    pub vibrot_t_e_min_ev: f64,
}

/// IN-16 registration of a case's chemistry.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ChemistryRegistration {
    /// SYNTHETIC_TEST_ONLY set (LC / CC / NV / FC verification).
    Synthetic { set: ChemistrySet },
    /// A registered set named by its Hall configuration: `n2_n.toml` is the registry scenario EM-N2-NOMINAL (the same
    /// tables, NP-ICP-NEUTRALIZER addendum 02 IN-16), built from `data/chemistry/icp/`.
    RegisteredSet { config_file: String },
    /// A gas with no registered rate set (Xe, Ar, O / O2): INCOMPLETE_EVIDENCE.
    NotRegistered { gas: String },
}

impl ChemistrySet {
    pub fn species_index(&self, name: &str) -> Option<usize> {
        self.species.iter().position(|s| s.name == name)
    }

    /// Structural contract checks (element / charge conservation, references). Violations are MODEL_ERROR.
    pub fn contract_violations(&self) -> Vec<String> {
        let mut v = Vec::new();
        let mut names = BTreeSet::new();
        for s in &self.species {
            if !names.insert(s.name.as_str()) {
                v.push(format!("duplicate species {}", s.name));
            }
            if !(s.mass_kg.is_finite() && s.mass_kg > 0.0) {
                v.push(format!("species {}: mass must be finite and > 0", s.name));
            }
        }
        let elem = |name: &str| self.species.iter().find(|s| s.name == name).map(|s| s.elements.clone());
        let add = |acc: &mut BTreeMap<String, u32>, e: &BTreeMap<String, u32>, n: u32| {
            for (k, c) in e {
                *acc.entry(k.clone()).or_insert(0) += c * n;
            }
        };
        for s in &self.species {
            if s.charge > 0 {
                let mut acc = BTreeMap::new();
                for (p, n) in &s.wall_products {
                    match self.species.iter().find(|x| x.name == *p) {
                        Some(x) if x.charge == 0 => add(&mut acc, &x.elements, *n),
                        _ => v.push(format!("ion {}: wall product {p} is not a registered neutral", s.name)),
                    }
                }
                if s.wall_products.is_empty() || acc != s.elements {
                    v.push(format!("ion {}: wall products must conserve its elements", s.name));
                }
            } else if !s.wall_products.is_empty() {
                v.push(format!("neutral {}: wall products are defined only for ions", s.name));
            }
            if let Some(m) = &s.recombines_to {
                let doubled: BTreeMap<String, u32> = s.elements.iter().map(|(k, c)| (k.clone(), 2 * c)).collect();
                match self.species.iter().find(|x| x.name == *m) {
                    Some(x) if x.charge == 0 && s.charge == 0 && x.elements == doubled => {}
                    _ => v.push(format!("atom {}: recombines_to {m} must be a neutral of two such atoms", s.name)),
                }
            }
        }
        let mut ids = BTreeSet::new();
        for r in &self.reactions {
            if !ids.insert(r.id.as_str()) {
                v.push(format!("duplicate reaction id {}", r.id));
            }
            if !(r.threshold_ev.is_finite() && r.threshold_ev >= 0.0) {
                v.push(format!("reaction {}: threshold must be finite and >= 0", r.id));
            }
            let Some(t) = self.species.iter().find(|s| s.name == r.target) else {
                v.push(format!("reaction {}: unknown target {}", r.id, r.target));
                continue;
            };
            let mut acc = BTreeMap::new();
            let mut z_out = 0u32;
            let mut ok = true;
            for (p, n) in &r.products {
                match self.species.iter().find(|s| s.name == *p) {
                    Some(ps) => {
                        add(&mut acc, &ps.elements, *n);
                        z_out += ps.charge * n;
                    }
                    None => {
                        v.push(format!("reaction {}: unknown product {p}", r.id));
                        ok = false;
                    }
                }
            }
            if !ok {
                continue;
            }
            if acc != t.elements {
                v.push(format!("reaction {}: products do not conserve the target's elements", r.id));
            }
            if z_out < t.charge {
                v.push(format!("reaction {}: charge decreases (attachment is not represented in v1)", r.id));
            }
            let n_products: u32 = r.products.iter().map(|(_, n)| n).sum();
            let n_ion_products: u32 = r
                .products
                .iter()
                .filter(|(p, _)| self.species.iter().any(|s| s.name == *p && s.charge > 0))
                .map(|(_, n)| n)
                .sum();
            let shape_ok = match r.kind {
                ReactionKind::Ionization => n_products == 1 && z_out > t.charge,
                ReactionKind::DissociativeIonization => n_products >= 2 && n_ion_products >= 1 && z_out > t.charge,
                ReactionKind::Dissociation => n_products >= 2 && z_out == t.charge,
                _ => r.products == vec![(r.target.clone(), 1)] && t.charge == 0,
            };
            if !shape_ok {
                v.push(format!("reaction {}: products do not match kind {:?}", r.id, r.kind));
            }
            if elem(&r.target).is_none() {
                v.push(format!("reaction {}: target has no element record", r.id));
            }
        }
        if !(self.t_e_domain_ev[0].is_finite()
            && self.t_e_domain_ev[1].is_finite()
            && 0.0 < self.t_e_domain_ev[0]
            && self.t_e_domain_ev[0] < self.t_e_domain_ev[1])
        {
            v.push("t_e_domain_ev must be an increasing positive pair".into());
        }
        v
    }

    /// Unaddressed (species, class) pairs of the completeness gate.
    pub fn unaddressed_classes(&self) -> Vec<(String, ProcessClass)> {
        let mut out = Vec::new();
        for s in &self.species {
            let m = self.process_classes.get(&s.name);
            for c in ProcessClass::ALL {
                if m.is_none_or(|m| !m.contains_key(&c)) {
                    out.push((s.name.clone(), c));
                }
            }
        }
        out
    }

    /// Formation energy of every ion relative to ground-state neutrals (EQ-18), from the ionization chains. Ions with
    /// two routes of different energy give an error naming them (formation bookkeeping is then not exact).
    pub fn ion_formation_energies(&self) -> Result<BTreeMap<String, f64>, String> {
        let mut eps: BTreeMap<String, f64> = BTreeMap::new();
        for s in &self.species {
            if s.charge == 0 {
                eps.insert(s.name.clone(), 0.0);
            }
        }
        let ion_routes: Vec<&ReactionDef> =
            self.reactions.iter().filter(|r| r.kind == ReactionKind::Ionization).collect();
        for _ in 0..=ion_routes.len() {
            for r in &ion_routes {
                if let Some(&e_t) = eps.get(&r.target) {
                    let (p, _) = &r.products[0];
                    let cand = e_t + r.threshold_ev;
                    match eps.get(p) {
                        None => {
                            eps.insert(p.clone(), cand);
                        }
                        Some(&e) if (e - cand).abs() > 1e-12 * e.abs().max(cand.abs()) => {
                            return Err(format!("ion {p}: formation energy {e} eV vs {cand} eV via {}", r.id));
                        }
                        Some(_) => {}
                    }
                }
            }
        }
        Ok(eps)
    }
}

/// A registered `.dat` rate table (HallThruster.jl format: header line with the threshold, then mean energy 3/2 T_e
/// [eV] vs rate [m^3/s]). Used only for the NV-06 / UQ-06 cross-check and the threshold header.
#[derive(Debug, Clone, PartialEq)]
pub struct DatTable {
    pub file: String,
    pub header: String,
    pub threshold_ev: f64,
    pub mean_energy_ev: Vec<f64>,
    pub rate_m3_s: Vec<f64>,
}

impl DatTable {
    pub fn parse(file: &str, bytes: &[u8]) -> AbepResult<Self> {
        let err = |m: String| AbepError::Schema { path: file.to_string(), message: m };
        let text = std::str::from_utf8(bytes).map_err(|e| err(e.to_string()))?;
        let mut lines = text.lines();
        let header = lines.next().ok_or_else(|| err("empty table".into()))?.to_string();
        let threshold_ev: f64 = header
            .rsplit_once(':')
            .and_then(|(_, v)| v.trim().parse().ok())
            .ok_or_else(|| err(format!("header without a numeric value: {header}")))?;
        lines.next().ok_or_else(|| err("missing column header".into()))?;
        let (mut e, mut k) = (Vec::new(), Vec::new());
        for (i, line) in lines.enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let mut it = line.split_whitespace();
            let (Some(a), Some(b), None) = (it.next(), it.next(), it.next()) else {
                return Err(err(format!("row {}: expected two columns", i + 3)));
            };
            let (a, b): (f64, f64) = (
                a.parse().map_err(|_| err(format!("row {}: energy", i + 3)))?,
                b.parse().map_err(|_| err(format!("row {}: rate", i + 3)))?,
            );
            if !(a.is_finite() && b.is_finite() && b >= 0.0) || e.last().is_some_and(|&p| a <= p) {
                return Err(err(format!("row {}: energies must increase and rates be finite >= 0", i + 3)));
            }
            e.push(a);
            k.push(b);
        }
        if e.len() < 2 {
            return Err(err("fewer than two rows".into()));
        }
        Ok(DatTable { file: file.to_string(), header, threshold_ev, mean_energy_ev: e, rate_m3_s: k })
    }

    /// Linear interpolation in mean energy; None outside the tabulated range (no extrapolation).
    pub fn rate_at_mean_energy(&self, eps_ev: f64) -> Option<f64> {
        let e = &self.mean_energy_ev;
        if !(eps_ev >= e[0] && eps_ev <= e[e.len() - 1]) {
            return None;
        }
        let i = e.partition_point(|&x| x <= eps_ev).clamp(1, e.len() - 1);
        let (e0, e1, k0, k1) = (e[i - 1], e[i], self.rate_m3_s[i - 1], self.rate_m3_s[i]);
        Some(k0 + (k1 - k0) * (eps_ev - e0) / (e1 - e0))
    }

    /// The table at T_e (mean energy 3/2 T_e).
    pub fn rate_at_te(&self, t_e_ev: f64) -> Option<f64> {
        self.rate_at_mean_energy(1.5 * t_e_ev)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dat_parse_and_interpolate() {
        let t = DatTable::parse(
            "x.dat",
            b"Ionization energy (eV): 15.58\nEnergy (eV)\tRate\n0.0\t0.0\n1.0\t2.0\n2.0\t6.0\n",
        )
        .unwrap();
        assert_eq!(t.threshold_ev, 15.58);
        assert_eq!(t.rate_at_mean_energy(1.5), Some(4.0));
        assert_eq!(t.rate_at_mean_energy(2.0), Some(6.0));
        assert_eq!(t.rate_at_mean_energy(2.5), None);
        assert_eq!(t.rate_at_te(1.0), Some(4.0));
        assert!(DatTable::parse("x.dat", b"h: 1\nE\tk\n1.0\t1.0\n0.5\t1.0\n").is_err());
    }
}
