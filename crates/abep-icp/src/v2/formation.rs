//! EQ-18 v2 formation-energy bookkeeping (GAP-02, INT-17, IN-25).
//!
//! Reference state: the ground-state neutral molecules of the delivered feed. A neutral atom of an element that also
//! forms a registered diatomic neutral E2 in the set carries E_form = 1/2 D0(E2) (IN-25); a neutral whose element has
//! no registered molecule is its own reference (E_form = 0). An ion takes the least-energy registered formation route
//! (INT-17): min over the ionization channels producing it of E_form(target) + E_r, and over the dissociative channels
//! producing it as their only ion of E_form(target) + E_r - sum E_form(other products). Every event keeps its route;
//! the route excess E_r - Delta E_form >= 0 of each channel is reported and booked in energy class X.

use crate::chemistry::{ChemistrySet, ReactionKind};
use std::collections::{BTreeMap, BTreeSet};

/// Per species E_form [eV] and the ion routes. `None` means unresolved (a missing D0 or no registered route).
#[derive(Debug, Clone, PartialEq)]
pub struct FormationTable {
    pub e_form_ev: Vec<Option<f64>>,
    /// Per ion: the reaction ids attaining the least-energy route (route identity, INT-17).
    pub least_routes: Vec<Vec<String>>,
    /// Molecules whose D0 is needed but not registered (IN-25, FC-29).
    pub missing_d0: BTreeSet<String>,
}

/// The diatomic neutral of an atom species (elements {E: 1} -> the neutral with {E: 2}), if registered in the set.
pub fn parent_molecule(set: &ChemistrySet, atom: usize) -> Option<usize> {
    let s = &set.species[atom];
    if s.charge != 0 || s.elements.values().sum::<u32>() != 1 {
        return None;
    }
    let doubled: BTreeMap<String, u32> = s.elements.iter().map(|(k, n)| (k.clone(), 2 * n)).collect();
    set.species.iter().position(|x| x.charge == 0 && x.elements == doubled)
}

pub fn formation_table(set: &ChemistrySet, d0_ev: &BTreeMap<String, f64>) -> FormationTable {
    let ns = set.species.len();
    let mut e: Vec<Option<f64>> = vec![None; ns];
    let mut missing_d0 = BTreeSet::new();
    for (i, s) in set.species.iter().enumerate() {
        if s.charge != 0 {
            continue;
        }
        e[i] = match parent_molecule(set, i) {
            Some(m) => match d0_ev.get(&set.species[m].name) {
                Some(d) => Some(0.5 * d),
                None => {
                    missing_d0.insert(set.species[m].name.clone());
                    None
                }
            },
            None => Some(0.0),
        };
    }
    let mut routes: Vec<Vec<String>> = vec![Vec::new(); ns];
    // Fixed point over the route graph: each pass may resolve ions one step further along a chain.
    for _ in 0..=set.reactions.len() {
        let mut changed = false;
        for r in &set.reactions {
            let ions: Vec<usize> = r
                .products
                .iter()
                .filter_map(|(p, _)| set.species_index(p))
                .filter(|&p| set.species[p].charge > 0)
                .collect();
            let cand = match r.kind {
                ReactionKind::Ionization if ions.len() == 1 => {
                    let t = set.species_index(&r.target).expect("checked");
                    e[t].map(|et| (ions[0], et + r.threshold_ev))
                }
                ReactionKind::DissociativeIonization if ions.len() == 1 => {
                    let t = set.species_index(&r.target).expect("checked");
                    let others: Option<f64> = r
                        .products
                        .iter()
                        .filter_map(|(p, n)| set.species_index(p).map(|i| (i, *n)))
                        .filter(|(i, _)| *i != ions[0])
                        .map(|(i, n)| e[i].map(|x| f64::from(n) * x))
                        .sum();
                    match (e[t], others) {
                        (Some(et), Some(o)) => Some((ions[0], et + r.threshold_ev - o)),
                        _ => None,
                    }
                }
                _ => None,
            };
            let Some((ion, v)) = cand else { continue };
            match e[ion] {
                Some(cur) if v > cur => {}
                Some(cur) if v == cur => {
                    if !routes[ion].contains(&r.id) {
                        routes[ion].push(r.id.clone());
                        changed = true;
                    }
                }
                _ => {
                    e[ion] = Some(v);
                    routes[ion] = vec![r.id.clone()];
                    changed = true;
                }
            }
        }
        if !changed {
            break;
        }
    }
    for r in routes.iter_mut() {
        r.sort();
    }
    FormationTable { e_form_ev: e, least_routes: routes, missing_d0 }
}

impl FormationTable {
    /// Delta E_form of one event of reaction `ri` [eV] (products minus target), if every species is resolved.
    pub fn delta(&self, set: &ChemistrySet, ri: usize) -> Option<f64> {
        let r = &set.reactions[ri];
        let t = set.species_index(&r.target)?;
        let mut d = -self.e_form_ev[t]?;
        for (p, n) in &r.products {
            d += f64::from(*n) * self.e_form_ev[set.species_index(p)?]?;
        }
        Some(d)
    }

    /// Route / fragment excess E_r - Delta E_form of reaction `ri` [eV] (class X for formation-changing channels).
    pub fn excess(&self, set: &ChemistrySet, ri: usize) -> Option<f64> {
        self.delta(set, ri).map(|d| set.reactions[ri].threshold_ev - d)
    }
}
