//! Energy disposition ED-01..ED-09 (operational EQ-16 v2) for one converged solve member.
//!
//! Classes (ED-01): ION / ELEC per surface (L_j and the ion formation energy F_j, computed, no choice); X (electronic
//! excitation, fragment and route excess); N (elastic recoil, vibrational, rotational, and (1 - beta) of the wall
//! recombination energy); A (atom formation energy, 1/2 D0 per atom created). Destinations (ED-02): RAD, WALL[m]
//! (area-weighted inside material m, or proportional to c_j A_j when the class coefficient is sourced for every wall
//! surface, ED-04), OUT (split A_j tau_j when every tau_j is registered, else the OUT[UP] / OUT[DOWN] vertex, ED-05).
//! A partition member is one vertex of every factor (ED-08); members are unweighted and never averaged. A class with
//! exactly zero energy has one (empty) vertex: every destination gives the same allocation.

use super::formation::{parent_molecule, FormationTable};
use crate::case::Disposition;
use crate::chemistry::ReactionKind;
use crate::constants::E_CHARGE;
use crate::geometry::SurfaceKind;
use crate::physics;
use crate::solver::{Equilibrium, PreparedCase};
use std::collections::BTreeMap;

/// A destination vertex (ED-02).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub enum Dest {
    Rad,
    /// All of it on the wall surfaces of one material, area-weighted inside it.
    Wall(String),
    /// Proportional to c_j A_j over every wall surface (the class coefficient is sourced everywhere).
    WallCoef,
    Out,
}

impl Dest {
    pub fn label(&self) -> String {
        match self {
            Dest::Rad => "RAD".into(),
            Dest::Wall(m) => format!("WALL[{m}]"),
            Dest::WallCoef => "WALL[c_j A_j]".into(),
            Dest::Out => "OUT".into(),
        }
    }
}

/// The open-end split of OUT energy (ED-05).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum EndSplit {
    /// proportional to A_j tau_j (every tau_j registered; flag UNIFORM_ISOTROPIC_NEUTRAL_EXIT).
    Tau,
    /// All OUT energy through the open ends of one kind (vertex OUT[UP] / OUT[DOWN]).
    Kind(SurfaceKind),
}

impl EndSplit {
    pub fn label(&self) -> &'static str {
        match self {
            EndSplit::Tau => "A_TAU",
            EndSplit::Kind(SurfaceKind::OpenUpstream) => "OUT[UP]",
            EndSplit::Kind(_) => "OUT[DOWN]",
        }
    }
}

/// A sourced value or the unweighted vertex set of a wall coefficient (IN-18 v2).
#[derive(Debug, Clone, PartialEq)]
pub enum Coef {
    Sourced(f64),
    Vertices(Vec<f64>),
}

impl Coef {
    pub fn options(&self) -> Vec<f64> {
        match self {
            Coef::Sourced(v) => vec![*v],
            Coef::Vertices(v) => v.clone(),
        }
    }
}

/// Wall coefficients per (species, material): gamma, beta, quench probability.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct WallCoefs {
    pub gamma: BTreeMap<(String, String), Coef>,
    pub beta: BTreeMap<(String, String), Coef>,
    pub quench: BTreeMap<(String, String), Coef>,
}

impl WallCoefs {
    fn get(m: &BTreeMap<(String, String), Coef>, s: &str, mat: &str) -> Coef {
        m.get(&(s.to_string(), mat.to_string())).cloned().unwrap_or(Coef::Vertices(vec![0.0, 1.0]))
    }
    pub fn gamma(&self, s: &str, mat: &str) -> Coef {
        Self::get(&self.gamma, s, mat)
    }
    pub fn beta(&self, s: &str, mat: &str) -> Coef {
        Self::get(&self.beta, s, mat)
    }
    pub fn quench(&self, s: &str, mat: &str) -> Coef {
        Self::get(&self.quench, s, mat)
    }
}

/// Inputs of the disposition of one solve member.
pub struct PartitionInput<'a> {
    pub p: &'a PreparedCase,
    pub e: &'a Equilibrium,
    pub formation: &'a FormationTable,
    /// Electronic-excitation channel id -> disposition (absent = UNRESOLVED).
    pub dispositions: &'a BTreeMap<String, Disposition>,
    /// Wall material per surface (index-aligned with `p.surfaces`).
    pub materials: &'a [String],
    pub coefs: &'a WallCoefs,
    /// FLOW_BALANCE: the solve member's gamma per (atom species, material).
    pub flow_gamma: Option<&'a BTreeMap<(String, String), f64>>,
    /// Every open end has a registered tau.
    pub tau_registered: bool,
}

/// One partition member's choices (ED-08).
#[derive(Debug, Clone, PartialEq)]
pub struct Choice {
    pub x: Option<Dest>,
    /// Material vertex of sourced WALL_QUENCHED channels whose quench probability is not sourced everywhere.
    pub xq: Option<Dest>,
    pub n: Option<Dest>,
    /// REGISTERED_PRESSURE class A destination.
    pub a: Option<Dest>,
    pub beta: BTreeMap<(String, String), f64>,
    pub end: Option<EndSplit>,
}

impl Choice {
    pub fn id(&self) -> String {
        let d = |x: &Option<Dest>| x.as_ref().map_or("EMPTY".to_string(), Dest::label);
        let b: Vec<String> = self.beta.iter().map(|((s, m), v)| format!("{s}@{m}={v}")).collect();
        format!(
            "X={};XQ={};N={};A={};BETA=[{}];END={}",
            d(&self.x),
            d(&self.xq),
            d(&self.n),
            d(&self.a),
            b.join(","),
            self.end.map_or("NONE", |e| e.label())
        )
    }
}

/// Class energies of a solve member, before any destination choice.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct ClassEnergies {
    /// Unresolved class X (incl. every fragment / route excess) [W].
    pub x_unresolved_w: f64,
    /// Sourced dispositions of electronic channels: (channel, disposition, target species, W).
    pub x_sourced: Vec<(String, Disposition, String, f64)>,
    pub n_base_w: f64,
    /// Per atom species: class A [W] (1/2 D0 x net atoms created, incl. wall-neutralization products).
    pub a_by_atom_w: BTreeMap<String, f64>,
    /// Route / fragment excess per reaction [W] (INT-17; OUT-12 route_excess_W).
    pub route_excess_w: BTreeMap<String, f64>,
    /// sum_r e R_r Delta E_form,r [W] (CC-07 v2 left-hand side).
    pub formation_created_w: f64,
    /// Ion formation energy per surface [W] (F_j).
    pub f_w: Vec<f64>,
}

fn is_wall(k: SurfaceKind) -> bool {
    !k.is_open()
}

/// Class energies (ED-01) and F_j. Errors name a CC-07 breach (a channel whose products carry more formation energy
/// than its header) or an unresolved formation energy.
pub fn class_energies(inp: &PartitionInput) -> Result<ClassEnergies, String> {
    let (p, e, ft) = (inp.p, inp.e, inp.formation);
    let set = &p.set;
    let ns = set.species.len();
    let mut out = ClassEnergies { f_w: vec![0.0; p.surfaces.len()], ..Default::default() };
    let rate = |ri: usize| {
        let t = set.species_index(&set.reactions[ri].target).expect("checked");
        p.volume_m3 * e.kin.n_e * e.kin.n[t] * e.kin.k[ri]
    };
    let mut netvol = vec![0.0; ns];
    for (ri, r) in set.reactions.iter().enumerate() {
        let pw = e.p_reaction_w[ri];
        match r.kind {
            ReactionKind::ElasticMomentumTransfer
            | ReactionKind::ExcitationVibrational
            | ReactionKind::ExcitationRotational => out.n_base_w += pw,
            ReactionKind::ExcitationElectronic => match inp.dispositions.get(&r.id) {
                None | Some(Disposition::Unresolved) => out.x_unresolved_w += pw,
                Some(d) => out.x_sourced.push((r.id.clone(), *d, r.target.clone(), pw)),
            },
            ReactionKind::Ionization | ReactionKind::DissociativeIonization | ReactionKind::Dissociation => {
                let d = ft.delta(set, ri).ok_or_else(|| format!("EQ-18 formation energy unresolved for {}", r.id))?;
                let mut ex = r.threshold_ev - d;
                if ex.abs() <= 1e-12 * r.threshold_ev.abs() {
                    ex = 0.0;
                }
                if ex < 0.0 {
                    return Err(format!("CC-07: {} products carry {d} eV > E_r = {} eV", r.id, r.threshold_ev));
                }
                let rr = rate(ri);
                out.formation_created_w += E_CHARGE * rr * d;
                let xw = E_CHARGE * rr * ex;
                out.x_unresolved_w += xw;
                out.route_excess_w.insert(r.id.clone(), xw);
                let t = set.species_index(&r.target).expect("checked");
                netvol[t] -= rr;
                for (pn, cnt) in &r.products {
                    netvol[set.species_index(pn).expect("checked")] += f64::from(*cnt) * rr;
                }
            }
        }
    }
    let ef = |s: usize| ft.e_form_ev[s].ok_or_else(|| format!("EQ-18 E_form of {} unresolved", set.species[s].name));
    let mut wallprod = vec![0.0; ns];
    for (j, (sf, st)) in p.surfaces.iter().zip(&e.surfaces).enumerate() {
        let mut fj = 0.0;
        for (s, sp) in set.species.iter().enumerate() {
            if sp.charge == 0 || st.gamma_i[s] == 0.0 {
                continue;
            }
            let flux = sf.area_m2 * st.gamma_i[s];
            if sf.kind.is_open() {
                fj += flux * ef(s)?;
            } else {
                let mut prod = 0.0;
                for (wp, cnt) in &sp.wall_products {
                    let k = set.species_index(wp).expect("checked");
                    prod += f64::from(*cnt) * ef(k)?;
                    wallprod[k] += f64::from(*cnt) * flux;
                }
                fj += flux * (ef(s)? - prod);
            }
        }
        out.f_w[j] = E_CHARGE * fj;
    }
    for (a, sp) in set.species.iter().enumerate() {
        if parent_molecule(set, a).is_none() {
            continue;
        }
        let ea = ef(a)?;
        out.a_by_atom_w.insert(sp.name.clone(), E_CHARGE * ea * (netvol[a] + wallprod[a]));
    }
    Ok(out)
}

/// Spread `energy` over the surfaces of a destination into `w` (per surface). `coef` = c_j for WallCoef.
fn spread(
    w: &mut [f64],
    energy: f64,
    dest: &Dest,
    end: Option<EndSplit>,
    inp: &PartitionInput,
    coef: Option<&[f64]>,
) -> Result<(), String> {
    if energy == 0.0 {
        return Ok(());
    }
    let s = &inp.p.surfaces;
    let weights: Vec<f64> = match dest {
        Dest::Rad => return Err("RAD is not a surface destination".into()),
        Dest::Wall(m) => s
            .iter()
            .zip(inp.materials)
            .map(|(x, mm)| if is_wall(x.kind) && mm == m { x.area_m2 } else { 0.0 })
            .collect(),
        Dest::WallCoef => {
            let c = coef.ok_or("WALL[c_j A_j] without coefficients")?;
            s.iter().enumerate().map(|(j, x)| if is_wall(x.kind) { c[j] * x.area_m2 } else { 0.0 }).collect()
        }
        Dest::Out => match end {
            Some(EndSplit::Tau) => {
                s.iter().map(|x| if x.kind.is_open() { x.area_m2 * x.tau.unwrap_or(f64::NAN) } else { 0.0 }).collect()
            }
            Some(EndSplit::Kind(k)) => s.iter().map(|x| if x.kind == k { x.area_m2 } else { 0.0 }).collect(),
            None => return Err("OUT without an open end".into()),
        },
    };
    let tot: f64 = weights.iter().sum();
    if !(tot.is_finite() && tot > 0.0) {
        return Err(format!("destination {} has no receiving surface (sum of weights {tot})", dest.label()));
    }
    for (wj, x) in w.iter_mut().zip(&weights) {
        *wj += energy * x / tot;
    }
    Ok(())
}

/// The allocation of one partition member.
#[derive(Debug, Clone, PartialEq)]
pub struct Allocation {
    pub id: String,
    pub w_x: Vec<f64>,
    pub w_n: Vec<f64>,
    pub w_a: Vec<f64>,
    pub rad_w: f64,
    /// Class energies and their allocated totals (CC-08).
    pub class_x_w: f64,
    pub class_n_w: f64,
    pub class_a_w: f64,
    pub allocated_x_w: f64,
    pub allocated_n_w: f64,
    pub allocated_a_w: f64,
}

/// Wall materials present (sorted), open-end kinds present.
pub fn wall_materials(inp: &PartitionInput) -> Vec<String> {
    let mut m: Vec<String> =
        inp.p.surfaces.iter().zip(inp.materials).filter(|(s, _)| is_wall(s.kind)).map(|(_, mm)| mm.clone()).collect();
    m.sort();
    m.dedup();
    m
}

fn all_sourced(inp: &PartitionInput, f: impl Fn(&str) -> Coef) -> Option<Vec<f64>> {
    inp.p
        .surfaces
        .iter()
        .zip(inp.materials)
        .map(|(s, m)| {
            if !is_wall(s.kind) {
                return Some(0.0);
            }
            match f(m) {
                Coef::Sourced(v) => Some(v),
                Coef::Vertices(_) => None,
            }
        })
        .collect()
}

/// Atom loss channels in FLOW_BALANCE for one atom species: (surface, loss rate [1/s], is recombination).
fn atom_losses(inp: &PartitionInput, atom: usize, gam: &BTreeMap<(String, String), f64>) -> Vec<(usize, f64, bool)> {
    let p = inp.p;
    let sp = &p.set.species[atom];
    let flux = 0.25 * inp.e.kin.n[atom] * physics::neutral_mean_speed(p.t_g_k, sp.mass_kg);
    p.surfaces
        .iter()
        .enumerate()
        .map(|(j, s)| {
            if s.kind.is_open() {
                (j, flux * s.area_m2 * s.tau.unwrap_or(f64::NAN), false)
            } else {
                let g = gam.get(&(sp.name.clone(), inp.materials[j].clone())).copied().unwrap_or(0.0);
                (j, flux * s.area_m2 * g, true)
            }
        })
        .collect()
}

/// Every partition member of one solve member (ED-08).
pub fn choices(inp: &PartitionInput, ce: &ClassEnergies) -> Vec<Choice> {
    let mats = wall_materials(inp);
    let has_open = inp.p.surfaces.iter().any(|s| s.kind.is_open());
    let ends: Vec<Option<EndSplit>> = if !has_open {
        vec![None]
    } else if inp.tau_registered {
        vec![Some(EndSplit::Tau)]
    } else {
        let mut k: Vec<SurfaceKind> = inp.p.surfaces.iter().filter(|s| s.kind.is_open()).map(|s| s.kind).collect();
        k.sort();
        k.dedup();
        k.into_iter().map(|x| Some(EndSplit::Kind(x))).collect()
    };
    let mut wall_or_out: Vec<Dest> = mats.iter().map(|m| Dest::Wall(m.clone())).collect();
    if has_open {
        wall_or_out.push(Dest::Out);
    }
    let x_opts: Vec<Option<Dest>> = if ce.x_unresolved_w != 0.0 {
        std::iter::once(Dest::Rad).chain(wall_or_out.iter().cloned()).map(Some).collect()
    } else {
        vec![None]
    };
    let quench_needed = ce.x_sourced.iter().any(|(_, d, s, w)| {
        *d == Disposition::WallQuenched && *w != 0.0 && all_sourced(inp, |m| inp.coefs.quench(s, m)).is_none()
    });
    let xq_opts: Vec<Option<Dest>> =
        if quench_needed { mats.iter().map(|m| Some(Dest::Wall(m.clone()))).collect() } else { vec![None] };
    let atoms: Vec<&String> = ce.a_by_atom_w.keys().collect();
    let a_nonzero = ce.a_by_atom_w.values().any(|v| *v != 0.0);
    let flow = inp.flow_gamma.is_some();
    let a_opts: Vec<Option<Dest>> = if flow || !a_nonzero {
        vec![None]
    } else if atoms.iter().all(|a| all_sourced(inp, |m| inp.coefs.gamma(a, m)).is_some()) {
        let mut v = vec![Some(Dest::WallCoef)];
        if has_open {
            v.push(Some(Dest::Out));
        }
        v
    } else {
        wall_or_out.iter().cloned().map(Some).collect()
    };
    let n_possible = ce.n_base_w != 0.0 || a_nonzero;
    let n_opts: Vec<Option<Dest>> =
        if n_possible { wall_or_out.iter().cloned().map(Some).collect() } else { vec![None] };
    let mut out = Vec::new();
    for x in &x_opts {
        for xq in &xq_opts {
            for n in &n_opts {
                for a in &a_opts {
                    for end in &ends {
                        // beta pairs that receive recombination energy in this member.
                        let mut pairs: Vec<(String, String)> = Vec::new();
                        for at in &atoms {
                            for m in &mats {
                                let gets = if let Some(g) = inp.flow_gamma {
                                    g.get(&((*at).clone(), m.clone())).is_some_and(|v| *v != 0.0)
                                        && ce.a_by_atom_w[*at] != 0.0
                                } else {
                                    ce.a_by_atom_w[*at] != 0.0
                                        && match a {
                                            Some(Dest::Wall(mm)) => mm == m,
                                            Some(Dest::WallCoef) => true,
                                            _ => false,
                                        }
                                };
                                if gets {
                                    pairs.push(((*at).clone(), m.clone()));
                                }
                            }
                        }
                        let mut betas: Vec<BTreeMap<(String, String), f64>> = vec![BTreeMap::new()];
                        for (at, m) in &pairs {
                            let opts = inp.coefs.beta(at, m).options();
                            betas = betas
                                .into_iter()
                                .flat_map(|b| {
                                    opts.iter().map(move |v| {
                                        let mut b2 = b.clone();
                                        b2.insert((at.clone(), m.clone()), *v);
                                        b2
                                    })
                                })
                                .collect();
                        }
                        for beta in betas {
                            out.push(Choice {
                                x: x.clone(),
                                xq: xq.clone(),
                                n: n.clone(),
                                a: a.clone(),
                                beta,
                                end: *end,
                            });
                        }
                    }
                }
            }
        }
    }
    out
}

/// Allocate every class of one member (ED-02..ED-07).
pub fn allocate(inp: &PartitionInput, ce: &ClassEnergies, ch: &Choice) -> Result<Allocation, String> {
    let ns = inp.p.surfaces.len();
    let (mut w_x, mut w_n, mut w_a) = (vec![0.0; ns], vec![0.0; ns], vec![0.0; ns]);
    let mut rad = 0.0;
    let mut n_from_a = 0.0;
    // Class A.
    let class_a: f64 = ce.a_by_atom_w.values().sum();
    for (at, a_w) in &ce.a_by_atom_w {
        if *a_w == 0.0 {
            continue;
        }
        if *a_w < 0.0 {
            return Err(format!("class A of {at} is {a_w} W < 0 (net atom consumption)"));
        }
        match inp.flow_gamma {
            Some(g) => {
                let ai = inp.p.set.species_index(at).expect("atom");
                let losses = atom_losses(inp, ai, g);
                let tot: f64 = losses.iter().map(|x| x.1).sum();
                if !(tot.is_finite() && tot > 0.0) {
                    return Err(format!("class A of {at}: no atom loss channel"));
                }
                for (j, l, recomb) in losses {
                    let share = a_w * l / tot;
                    if recomb {
                        let b = ch.beta.get(&(at.clone(), inp.materials[j].clone())).copied().unwrap_or(1.0);
                        w_a[j] += b * share;
                        n_from_a += (1.0 - b) * share;
                    } else {
                        w_a[j] += share;
                    }
                }
            }
            None => {
                let dest = ch.a.as_ref().ok_or("class A without a destination")?;
                match dest {
                    Dest::Out => spread(&mut w_a, *a_w, dest, ch.end, inp, None)?,
                    Dest::Wall(_) | Dest::WallCoef => {
                        let coef = all_sourced(inp, |m| inp.coefs.gamma(at, m));
                        let mut tmp = vec![0.0; ns];
                        spread(&mut tmp, *a_w, dest, ch.end, inp, coef.as_deref())?;
                        for j in 0..ns {
                            if tmp[j] != 0.0 {
                                let b = ch.beta.get(&(at.clone(), inp.materials[j].clone())).copied().unwrap_or(1.0);
                                w_a[j] += b * tmp[j];
                                n_from_a += (1.0 - b) * tmp[j];
                            }
                        }
                    }
                    Dest::Rad => return Err("class A cannot be radiated".into()),
                }
            }
        }
    }
    // Class N.
    let class_n = ce.n_base_w + n_from_a;
    if class_n != 0.0 {
        let dest = ch.n.as_ref().ok_or("class N without a destination")?;
        spread(&mut w_n, class_n, dest, ch.end, inp, None)?;
    }
    // Class X.
    let mut class_x = ce.x_unresolved_w;
    if ce.x_unresolved_w != 0.0 {
        match ch.x.as_ref().ok_or("class X without a destination")? {
            Dest::Rad => rad += ce.x_unresolved_w,
            d => spread(&mut w_x, ce.x_unresolved_w, d, ch.end, inp, None)?,
        }
    }
    for (_, disp, target, pw) in &ce.x_sourced {
        class_x += pw;
        match disp {
            Disposition::RadiatedOpticallyThin => rad += pw,
            Disposition::CarriedOut => spread(&mut w_x, *pw, &Dest::Out, ch.end, inp, None)?,
            Disposition::WallQuenched => match all_sourced(inp, |m| inp.coefs.quench(target, m)) {
                Some(c) => spread(&mut w_x, *pw, &Dest::WallCoef, ch.end, inp, Some(&c))?,
                None => {
                    spread(&mut w_x, *pw, ch.xq.as_ref().ok_or("quench material vertex missing")?, ch.end, inp, None)?
                }
            },
            Disposition::Unresolved => unreachable!("unresolved channels are in x_unresolved_w"),
        }
    }
    let sx: f64 = w_x.iter().sum::<f64>() + rad;
    let sn: f64 = w_n.iter().sum();
    let sa: f64 = w_a.iter().sum::<f64>() + n_from_a;
    Ok(Allocation {
        id: ch.id(),
        w_x,
        w_n,
        w_a,
        rad_w: rad,
        class_x_w: class_x,
        class_n_w: class_n,
        class_a_w: class_a,
        allocated_x_w: sx,
        allocated_n_w: sn,
        allocated_a_w: sa,
    })
}
