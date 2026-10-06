//! Steady 0-D plasma solve (EQ-01..EQ-11): species balances, quasi-neutrality, Bohm-flux losses with registered h,
//! electrode current balance and the electron energy balance in CM-ABS form (P_abs given).
//!
//! Root finding follows the prereg `numerical_verification` rules: T_e is bracketed on the full registered scan grid
//! before refinement; every sign change is refined by bisection to adjacent doubles and reported; phi_p is solved in
//! closed form inside each collection regime (the regimes cover the whole real line); no root is chosen silently.

use crate::chemistry::{ChemistrySet, RateSource, ReactionKind};
use crate::constants::{NumericalSettings, E_CHARGE, M_E};
use crate::geometry::{Orientation, SurfaceKind, ThermalNode};
use crate::physics;
use serde::Serialize;

/// A solver failure. Every variant is reported as MODEL_ERROR with all physics values null (FC-09, NV-05).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct SolveFailure {
    pub code: String,
    pub detail: String,
}

fn fail<T>(code: &str, detail: impl Into<String>) -> Result<T, SolveFailure> {
    Err(SolveFailure { code: code.into(), detail: detail.into() })
}

/// Edge-to-centre factor model after registration checks.
#[derive(Debug, Clone, PartialEq)]
pub enum PreparedH {
    /// h_j per surface (index-aligned with `PreparedCase::surfaces`).
    Explicit(Vec<f64>),
    /// One ion-neutral cross section shared by every ion species (multi-species H-LIEB with distinct sigma is refused
    /// before this point: the prereg defines one h per surface).
    Lieberman { sigma_i_m2: f64 },
}

#[derive(Debug, Clone, PartialEq)]
pub struct PreparedSurface {
    pub id: String,
    pub kind: SurfaceKind,
    pub area_m2: f64,
    pub orientation: Orientation,
    pub node: ThermalNode,
    /// Registered potential (biased surfaces only).
    pub potential_v: Option<f64>,
    /// Free-molecular transmission (open ends).
    pub tau: Option<f64>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum PreparedNeutrals {
    /// EQ-01: fixed densities per species index (0 for ions).
    Fixed(Vec<f64>),
    /// EQ-02: particle inflow [1/s] per species index (feed x f_in plus background inflow).
    Flow { inflow_per_s: Vec<f64> },
}

/// A fully registered, contract-checked case reduced to numbers.
#[derive(Debug, Clone)]
pub struct PreparedCase {
    pub set: ChemistrySet,
    pub volume_m3: f64,
    pub radius_m: f64,
    pub length_m: f64,
    pub surfaces: Vec<PreparedSurface>,
    pub h: PreparedH,
    pub neutrals: PreparedNeutrals,
    pub t_g_k: f64,
    pub p_abs_w: f64,
}

impl PreparedCase {
    fn n_species(&self) -> usize {
        self.set.species.len()
    }

    fn is_ion(&self, s: usize) -> bool {
        self.set.species[s].charge > 0
    }

    /// n_e cancels from the balances (REGISTERED_PRESSURE and every reaction targets a neutral): T_e and phi_p are then
    /// power-independent and n_e follows linearly from P_abs (LC-01, LC-02).
    pub fn is_linear(&self) -> bool {
        matches!(self.neutrals, PreparedNeutrals::Fixed(_))
            && self.set.reactions.iter().all(|r| {
                let t = self.set.species_index(&r.target).expect("checked");
                self.set.species[t].charge == 0
            })
    }

    fn biased_levels(&self) -> Vec<f64> {
        let mut v: Vec<f64> = self.surfaces.iter().filter_map(|s| s.potential_v).collect();
        v.sort_by(f64::total_cmp);
        v.dedup();
        v
    }

    fn rates(&self, t_e: f64) -> Vec<f64> {
        self.set
            .reactions
            .iter()
            .map(|r| match &r.rate {
                RateSource::Synthetic { rate } => rate.eval(t_e),
                // Never reached: registered tables are gated (EQ-06 needs the admitted abep-chem integrator).
                RateSource::RegisteredTable { .. } => f64::NAN,
            })
            .collect()
    }

    fn h_values(&self, n_g_total: f64) -> Vec<f64> {
        match &self.h {
            PreparedH::Explicit(h) => h.clone(),
            PreparedH::Lieberman { sigma_i_m2 } => {
                let lam = physics::ion_mean_free_path(n_g_total, *sigma_i_m2);
                self.surfaces
                    .iter()
                    .map(|s| match s.orientation {
                        Orientation::Radial => physics::h_radial_lieberman(self.radius_m, lam),
                        Orientation::Axial => physics::h_axial_lieberman(self.length_m, lam),
                    })
                    .collect()
            }
        }
    }
}

/// Which surfaces collect ions: zero-current surfaces always, a biased surface iff V_j <= `level` (phi_p above it).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Regime {
    pub id: String,
    pub lower_v: Option<f64>,
    pub upper_v: Option<f64>,
    pub collecting: Vec<bool>,
}

fn regimes(c: &PreparedCase) -> Vec<Regime> {
    let levels = c.biased_levels();
    if levels.is_empty() {
        return vec![Regime {
            id: "ALL_ZERO_CURRENT".into(),
            lower_v: None,
            upper_v: None,
            collecting: c.surfaces.iter().map(|_| true).collect(),
        }];
    }
    // Regime 0 (phi_p <= lowest level: every biased surface electron-saturated) has a strictly negative current sum
    // and no root; it is enumerated for completeness and skipped by the phi_p solve.
    let mut out = Vec::new();
    for i in 0..=levels.len() {
        let lower = if i == 0 { None } else { Some(levels[i - 1]) };
        let upper = levels.get(i).copied();
        let collecting = c
            .surfaces
            .iter()
            .map(|s| match s.potential_v {
                None => true,
                Some(v) => lower.is_some_and(|l| v <= l),
            })
            .collect();
        out.push(Regime { id: format!("R{i}"), lower_v: lower, upper_v: upper, collecting });
    }
    out
}

/// Densities and fluxes at one (T_e, n_e, regime).
#[derive(Debug, Clone, PartialEq)]
pub struct Kinetics {
    pub t_e: f64,
    pub n_e: f64,
    pub k: Vec<f64>,
    /// Densities per species index.
    pub n: Vec<f64>,
    pub h: Vec<f64>,
    pub u_b: Vec<f64>,
    /// Max |residual| / largest term over every balance row.
    pub balance_residual: f64,
    pub fixed_point_iterations: usize,
}

/// Dense Gaussian elimination with partial pivoting (deterministic order).
fn solve_linear(mut a: Vec<Vec<f64>>, mut b: Vec<f64>) -> Option<Vec<f64>> {
    let n = b.len();
    for col in 0..n {
        let p = (col..n).max_by(|&i, &j| a[i][col].abs().total_cmp(&a[j][col].abs()))?;
        if a[p][col] == 0.0 || !a[p][col].is_finite() {
            return None;
        }
        a.swap(col, p);
        b.swap(col, p);
        let (top, bottom) = a.split_at_mut(col + 1);
        let pivot = &top[col];
        for (i, row) in bottom.iter_mut().enumerate() {
            let f = row[col] / pivot[col];
            if f != 0.0 {
                for (x, y) in row[col..].iter_mut().zip(&pivot[col..]) {
                    *x -= f * y;
                }
                b[col + 1 + i] -= f * b[col];
            }
        }
    }
    let mut x = vec![0.0; n];
    for r in (0..n).rev() {
        let mut s = b[r];
        for c2 in r + 1..n {
            s -= a[r][c2] * x[c2];
        }
        x[r] = s / a[r][r];
    }
    Some(x)
}

/// Balance rows for the unknown species (ions; plus neutrals in FLOW_BALANCE) at fixed T_e, n_e, h and regime.
/// Returns (matrix, rhs, unknown species indices). Row i: sum_j a_ij n_j = b_i with every gain on the left as
/// positive and every loss negative.
fn balance_system(
    c: &PreparedCase,
    t_e: f64,
    n_e: f64,
    k: &[f64],
    h: &[f64],
    collecting: &[bool],
) -> (Vec<Vec<f64>>, Vec<f64>, Vec<usize>) {
    let ns = c.n_species();
    let unknown: Vec<usize> = match &c.neutrals {
        PreparedNeutrals::Fixed(_) => (0..ns).filter(|&s| c.is_ion(s)).collect(),
        PreparedNeutrals::Flow { .. } => (0..ns).collect(),
    };
    let pos = |s: usize| unknown.iter().position(|&u| u == s);
    let m = unknown.len();
    let mut a = vec![vec![0.0; m]; m];
    let mut b = vec![0.0; m];
    let v = c.volume_m3;
    // Volume reactions that change the heavy-species composition.
    for (ri, r) in c.set.reactions.iter().enumerate() {
        if !r.kind.changes_species() {
            continue;
        }
        let t = c.set.species_index(&r.target).expect("checked");
        let coef = v * n_e * k[ri];
        let mut add = |row_s: usize, nu: f64| {
            if let Some(ri2) = pos(row_s) {
                match pos(t) {
                    Some(tc) => a[ri2][tc] += nu * coef,
                    None => {
                        if let PreparedNeutrals::Fixed(nf) = &c.neutrals {
                            b[ri2] -= nu * coef * nf[t];
                        }
                    }
                }
            }
        };
        add(t, -1.0);
        for (p, cnt) in &r.products {
            let ps = c.set.species_index(p).expect("checked");
            add(ps, f64::from(*cnt));
        }
    }
    let gamma_e = |s: usize| physics::bohm_speed(t_e, c.set.species[s].charge, c.set.species[s].mass_kg);
    for s in 0..ns {
        if !c.is_ion(s) {
            continue;
        }
        let row = pos(s).expect("ions are unknown");
        let ub = gamma_e(s);
        let mut h_all = 0.0;
        let mut h_wall = 0.0;
        for (j, sf) in c.surfaces.iter().enumerate() {
            if collecting[j] {
                h_all += h[j] * sf.area_m2;
                if !sf.kind.is_open() {
                    h_wall += h[j] * sf.area_m2;
                }
            }
        }
        a[row][row] -= ub * h_all;
        // EQ-02: walls return every incident ion as its neutral wall products.
        if let PreparedNeutrals::Flow { .. } = c.neutrals {
            for (p, cnt) in &c.set.species[s].wall_products {
                let k_idx = c.set.species_index(p).expect("checked");
                let r2 = pos(k_idx).expect("neutrals are unknown in FLOW_BALANCE");
                a[r2][row] += f64::from(*cnt) * ub * h_wall;
            }
        }
    }
    if let PreparedNeutrals::Flow { inflow_per_s } = &c.neutrals {
        let open_a_tau: f64 =
            c.surfaces.iter().filter(|s| s.kind.is_open()).map(|s| s.area_m2 * s.tau.unwrap_or(f64::NAN)).sum();
        for (s, sp) in c.set.species.iter().enumerate() {
            if sp.charge > 0 {
                continue;
            }
            let row = pos(s).expect("unknown");
            let vbar = physics::neutral_mean_speed(c.t_g_k, sp.mass_kg);
            a[row][row] -= 0.25 * vbar * open_a_tau;
            b[row] -= inflow_per_s[s];
        }
    }
    (a, b, unknown)
}

fn row_residual(a: &[Vec<f64>], b: &[f64], x: &[f64]) -> f64 {
    let mut worst: f64 = 0.0;
    for (row, bi) in a.iter().zip(b) {
        let mut s = -bi;
        let mut big = bi.abs();
        for (aij, xj) in row.iter().zip(x) {
            s += aij * xj;
            big = big.max((aij * xj).abs());
        }
        let rel = if big == 0.0 { s.abs() } else { s.abs() / big };
        worst = worst.max(rel);
    }
    worst
}

/// Species densities at (T_e, n_e) in one regime. FLOW_BALANCE with H-LIEB iterates on the total neutral density.
pub fn kinetics(
    c: &PreparedCase,
    t_e: f64,
    n_e: f64,
    collecting: &[bool],
    num: &NumericalSettings,
) -> Result<Kinetics, SolveFailure> {
    let k = c.rates(t_e);
    if k.iter().any(|x| !x.is_finite() || *x < 0.0) {
        return fail(
            "NV-05_NON_FINITE_RATE",
            format!("a rate coefficient is non-finite or negative at T_e = {t_e} eV"),
        );
    }
    let ns = c.n_species();
    let n_g_fixed: f64 = match &c.neutrals {
        PreparedNeutrals::Fixed(nf) => nf.iter().sum(),
        PreparedNeutrals::Flow { .. } => f64::NAN,
    };
    let mut n_g_guess = if n_g_fixed.is_nan() { 0.0 } else { n_g_fixed };
    let iterate = matches!(c.h, PreparedH::Lieberman { .. }) && matches!(c.neutrals, PreparedNeutrals::Flow { .. });
    let mut it = 0;
    loop {
        it += 1;
        let h = c.h_values(n_g_guess);
        let (a, b, unknown) = balance_system(c, t_e, n_e, &k, &h, collecting);
        let Some(x) = solve_linear(a.clone(), b.clone()) else {
            return fail("SINGULAR_BALANCE", format!("species balance singular at T_e = {t_e} eV"));
        };
        let mut n = match &c.neutrals {
            PreparedNeutrals::Fixed(nf) => nf.clone(),
            PreparedNeutrals::Flow { .. } => vec![0.0; ns],
        };
        for (i, &s) in unknown.iter().enumerate() {
            n[s] = x[i];
        }
        if n.iter().any(|v| !v.is_finite()) {
            return fail("NV-05_NON_FINITE_DENSITY", format!("non-finite density at T_e = {t_e} eV"));
        }
        let n_g_new: f64 = (0..ns).filter(|&s| !c.is_ion(s)).map(|s| n[s]).sum();
        let done = !iterate || (n_g_new - n_g_guess).abs() <= num.fixed_point_rel_tol * n_g_new.abs();
        if done {
            let u_b = (0..ns)
                .map(|s| {
                    let sp = &c.set.species[s];
                    if sp.charge > 0 {
                        physics::bohm_speed(t_e, sp.charge, sp.mass_kg)
                    } else {
                        0.0
                    }
                })
                .collect();
            return Ok(Kinetics {
                t_e,
                n_e,
                k,
                n,
                h,
                u_b,
                balance_residual: row_residual(&a, &b, &x),
                fixed_point_iterations: it,
            });
        }
        if it >= num.fixed_point_max_iter {
            return fail("ITERATION_LIMIT_FIXED_POINT", format!("H-LIEB neutral fixed point at T_e = {t_e} eV"));
        }
        n_g_guess = n_g_new;
    }
}

fn quasi_residual(c: &PreparedCase, kin: &Kinetics) -> f64 {
    let zn: f64 = (0..c.n_species()).map(|s| f64::from(c.set.species[s].charge) * kin.n[s]).sum();
    (zn - kin.n_e) / kin.n_e
}

/// Bisection to adjacent doubles; the iteration limit is MODEL_ERROR (FC-09).
fn bisect<F: FnMut(f64) -> Result<f64, SolveFailure>>(
    mut f: F,
    mut lo: f64,
    mut hi: f64,
    mut f_lo: f64,
    num: &NumericalSettings,
    what: &str,
) -> Result<(f64, usize), SolveFailure> {
    let mut it = 0;
    let mut f_hi = f(hi)?;
    loop {
        let mid = 0.5 * (lo + hi);
        if mid <= lo || mid >= hi {
            let x = if f_lo.abs() <= f_hi.abs() { lo } else { hi };
            return Ok((x, it));
        }
        it += 1;
        if it > num.bisection_max_iter {
            return fail(
                "ITERATION_LIMIT_BISECTION",
                format!("{what}: bisection limit {} reached", num.bisection_max_iter),
            );
        }
        let fm = f(mid)?;
        if !fm.is_finite() {
            return fail("NV-05_NON_FINITE_RESIDUAL", format!("{what}: non-finite residual at {mid}"));
        }
        if fm == 0.0 {
            return Ok((mid, it));
        }
        if (fm < 0.0) == (f_lo < 0.0) {
            lo = mid;
            f_lo = fm;
        } else {
            hi = mid;
            f_hi = fm;
        }
    }
}

fn log_grid(lo: f64, hi: f64, n: usize) -> Vec<f64> {
    let (a, b) = (lo.ln(), hi.ln());
    (0..n).map(|i| if i + 1 == n { hi } else { (a + (b - a) * i as f64 / (n - 1) as f64).exp() }).collect()
}

/// Every sign change of `f` on the grid, refined. Exact zeros on grid nodes count once.
fn all_roots<F: FnMut(f64) -> Result<f64, SolveFailure>>(
    mut f: F,
    grid: &[f64],
    num: &NumericalSettings,
    what: &str,
) -> Result<Vec<(f64, usize)>, SolveFailure> {
    let mut vals = Vec::with_capacity(grid.len());
    for &x in grid {
        let v = f(x)?;
        if !v.is_finite() {
            return fail("NV-05_NON_FINITE_RESIDUAL", format!("{what}: non-finite residual at grid point {x}"));
        }
        vals.push(v);
    }
    let mut roots = Vec::new();
    for i in 0..grid.len() {
        if vals[i] == 0.0 {
            roots.push((grid[i], 0));
            continue;
        }
        if i + 1 < grid.len() && vals[i + 1] != 0.0 && (vals[i] < 0.0) != (vals[i + 1] < 0.0) {
            roots.push(bisect(&mut f, grid[i], grid[i + 1], vals[i], num, what)?);
        }
    }
    Ok(roots)
}

/// Surface-resolved state of one equilibrium (EQ-08..EQ-11, EQ-16 per-surface terms).
#[derive(Debug, Clone, PartialEq)]
pub struct SurfaceState {
    pub collecting_ions: bool,
    pub electron_saturated: bool,
    /// Ion particle flux per species index [m^-2 s^-1].
    pub gamma_i: Vec<f64>,
    /// sum_s Z_s Gamma_i,s [m^-2 s^-1].
    pub gamma_z: f64,
    pub gamma_e: f64,
    /// max(0, phi_p - V_j) [V].
    pub barrier_v: f64,
    pub potential_v: Option<f64>,
    /// I_j = e A_j (Gamma_Z - Gamma_e) [A], positive = net positive charge into the surface.
    pub current_a: f64,
    pub current_ion_a: f64,
    pub current_electron_a: f64,
    /// L_j [W] (EQ-07 / EQ-16).
    pub l_w: f64,
    /// C_j = I_j (phi_p - V_j) [W]; exactly 0 for zero-current surfaces.
    pub c_w: f64,
    /// Formation energy released (walls, electron sink) or carried out (open ends) by the ions reaching j [W].
    pub formation_w: f64,
}

/// One equilibrium: a refined root in one regime.
#[derive(Debug, Clone, PartialEq)]
pub struct Equilibrium {
    pub regime: Regime,
    pub kin: Kinetics,
    pub phi_p_v: Option<f64>,
    pub v_s_float_v: f64,
    pub surfaces: Vec<SurfaceState>,
    /// Volume power per reaction V e n_e n_t k_r E_r (inelastic) or the elastic recoil term [W].
    pub p_reaction_w: Vec<f64>,
    pub p_loss_w: f64,
    pub quasi_residual: f64,
    pub current_residual: f64,
    pub bisection_iterations: usize,
}

/// Ion formation energies relative to the neutral each ion neutralizes to (EQ-18), indexed by species.
pub fn formation_by_species(set: &ChemistrySet) -> Vec<Option<f64>> {
    match set.ion_formation_energies() {
        Ok(m) => set.species.iter().map(|s| m.get(&s.name).copied()).collect(),
        Err(_) => set.species.iter().map(|_| None).collect(),
    }
}

/// Build the full surface / power state for a refined (T_e, regime) root at density n_e.
pub fn equilibrium_state(
    c: &PreparedCase,
    regime: &Regime,
    kin: Kinetics,
    bisection_iterations: usize,
) -> Result<Option<Equilibrium>, SolveFailure> {
    let t_e = kin.t_e;
    let n_e = kin.n_e;
    let ns = c.n_species();
    let vbar_e = physics::electron_mean_speed(t_e);
    let zflux_density: f64 = (0..ns).map(|s| f64::from(c.set.species[s].charge) * kin.n[s] * kin.u_b[s]).sum::<f64>();
    let arg = 0.25 * n_e * vbar_e / zflux_density;
    if !(arg.is_finite() && arg > 1.0) {
        return fail("FLOATING_SHEATH_UNDEFINED", format!("(1/4) n_e vbar_e / sum Z n u_B = {arg} (must exceed 1)"));
    }
    let v_s = t_e * arg.ln();
    // phi_p in closed form (EQ-10 over the biased surfaces).
    let phi_p = if regime.lower_v.is_none() && regime.upper_v.is_none() {
        None
    } else {
        let mut s_val = 0.0;
        let mut terms = Vec::new();
        for (j, sf) in c.surfaces.iter().enumerate() {
            let Some(vj) = sf.potential_v else { continue };
            let edge = kin.h[j] * sf.area_m2;
            if regime.collecting[j] {
                s_val += edge * zflux_density;
                terms.push((0.25 * edge * n_e * vbar_e).ln() + vj / t_e);
            } else {
                s_val -= edge * 0.25 * n_e * vbar_e;
            }
        }
        if terms.is_empty() || s_val <= 0.0 {
            return Ok(None);
        }
        let mx = terms.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let ln_k = mx + terms.iter().map(|t| (t - mx).exp()).sum::<f64>().ln();
        let phi = t_e * (ln_k - s_val.ln());
        let inside = regime.lower_v.is_none_or(|l| phi > l) && regime.upper_v.is_none_or(|u| phi <= u);
        if !inside {
            return Ok(None);
        }
        Some(phi)
    };
    let eps = formation_by_species(&c.set);
    let mut surfaces = Vec::with_capacity(c.surfaces.len());
    for (j, sf) in c.surfaces.iter().enumerate() {
        let edge = kin.h[j];
        let (collecting, barrier, potential) = match (sf.potential_v, phi_p) {
            (Some(vj), Some(phi)) => (vj < phi, (phi - vj).max(0.0), Some(vj)),
            (Some(_), None) => unreachable!("biased surfaces imply a referenced phi_p"),
            (None, phi) => (true, v_s, phi.map(|p| p - v_s)),
        };
        let gamma_i: Vec<f64> =
            (0..ns).map(|s| if collecting && c.is_ion(s) { edge * kin.n[s] * kin.u_b[s] } else { 0.0 }).collect();
        let gamma_z: f64 = (0..ns).map(|s| f64::from(c.set.species[s].charge) * gamma_i[s]).sum();
        let saturated = !collecting;
        let gamma_e = 0.25 * edge * n_e * vbar_e * if saturated { 1.0 } else { (-barrier / t_e).exp() };
        let current_ion_a = E_CHARGE * sf.area_m2 * gamma_z;
        let current_electron_a = E_CHARGE * sf.area_m2 * gamma_e;
        let current_a = current_ion_a - current_electron_a;
        let l_w = E_CHARGE * sf.area_m2 * (gamma_e * (2.0 * t_e + barrier) + gamma_z * 0.5 * t_e);
        let c_w = match (sf.potential_v, phi_p) {
            (Some(vj), Some(phi)) => current_a * (phi - vj),
            _ => 0.0,
        };
        let formation_w = E_CHARGE * sf.area_m2 * (0..ns).map(|s| eps[s].unwrap_or(0.0) * gamma_i[s]).sum::<f64>();
        surfaces.push(SurfaceState {
            collecting_ions: collecting,
            electron_saturated: saturated,
            gamma_i,
            gamma_z,
            gamma_e,
            barrier_v: barrier,
            potential_v: potential,
            current_a,
            current_ion_a,
            current_electron_a,
            l_w,
            c_w,
            formation_w,
        });
    }
    let t_g_ev = physics::kelvin_to_ev(c.t_g_k);
    let p_reaction_w: Vec<f64> = c
        .set
        .reactions
        .iter()
        .enumerate()
        .map(|(ri, r)| {
            let t = c.set.species_index(&r.target).expect("checked");
            let base = c.volume_m3 * E_CHARGE * n_e * kin.n[t] * kin.k[ri];
            if r.kind == ReactionKind::ElasticMomentumTransfer {
                base * 3.0 * M_E / c.set.species[t].mass_kg * (t_e - t_g_ev)
            } else {
                base * r.threshold_ev
            }
        })
        .collect();
    let p_loss_w = p_reaction_w.iter().sum::<f64>() + surfaces.iter().map(|s| s.l_w).sum::<f64>();
    let big = surfaces.iter().map(|s| s.current_ion_a.abs().max(s.current_electron_a.abs())).fold(0.0, f64::max);
    let sum_i: f64 = surfaces.iter().map(|s| s.current_a).sum();
    let current_residual = if big == 0.0 { sum_i.abs() } else { sum_i.abs() / big };
    let quasi = quasi_residual(c, &kin);
    Ok(Some(Equilibrium {
        regime: regime.clone(),
        kin,
        phi_p_v: phi_p,
        v_s_float_v: v_s,
        surfaces,
        p_reaction_w,
        p_loss_w,
        quasi_residual: quasi,
        current_residual,
        bisection_iterations,
    }))
}

/// All equilibria at fixed n_e over every regime (inner problem: quasi-neutrality in T_e, current balance in phi_p).
pub fn inner_equilibria(c: &PreparedCase, n_e: f64, num: &NumericalSettings) -> Result<Vec<Equilibrium>, SolveFailure> {
    let grid = log_grid(num.t_e_scan_min_ev, num.t_e_scan_max_ev, num.t_e_scan_points);
    let mut out = Vec::new();
    for reg in regimes(c) {
        // Regime 0 of a biased case (every biased surface electron-saturated) has no current-balance root.
        if !reg.collecting.iter().any(|&x| x) || (reg.lower_v.is_none() && reg.upper_v.is_some()) {
            continue;
        }
        let f = |t: f64| kinetics(c, t, n_e, &reg.collecting, num).map(|k| quasi_residual(c, &k));
        for (t_root, iters) in all_roots(f, &grid, num, "quasi-neutrality in T_e")? {
            let kin = kinetics(c, t_root, n_e, &reg.collecting, num)?;
            if let Some(eq) = equilibrium_state(c, &reg, kin, iters)? {
                out.push(eq);
            }
        }
    }
    Ok(out)
}

/// Rescale a state computed at n_e = 1 to density n_e (linear case): recompute from scaled densities.
fn rescaled(c: &PreparedCase, eq: &Equilibrium, n_e: f64) -> Result<Equilibrium, SolveFailure> {
    let mut kin = eq.kin.clone();
    kin.n_e = n_e;
    for s in 0..c.n_species() {
        if c.is_ion(s) {
            kin.n[s] = eq.kin.n[s] * n_e;
        }
    }
    match equilibrium_state(c, &eq.regime, kin, eq.bisection_iterations)? {
        Some(e) => Ok(e),
        None => fail("RESCALE_LEFT_REGIME", "rescaled state left its regime (phi_p must be n_e-independent)"),
    }
}

/// Outcome of the CM-ABS solve.
#[derive(Debug, Clone, PartialEq)]
pub enum SolveOutcome {
    /// P_abs = 0, or no positive-density state anywhere in the scanned domain.
    NotSustained,
    Equilibria(Vec<Equilibrium>),
}

/// Solve with P_abs given (CM-ABS, or CM-CAL after EQ-12).
pub fn solve(c: &PreparedCase, num: &NumericalSettings) -> Result<SolveOutcome, SolveFailure> {
    if c.p_abs_w == 0.0 {
        return Ok(SolveOutcome::NotSustained);
    }
    if c.is_linear() {
        let unit = inner_equilibria(c, 1.0, num)?;
        if unit.is_empty() {
            return Ok(SolveOutcome::NotSustained);
        }
        let mut out = Vec::new();
        for e in &unit {
            if !(e.p_loss_w.is_finite() && e.p_loss_w > 0.0) {
                return fail("NV-05_NON_FINITE_POWER", "loss power per unit n_e is not finite and positive");
            }
            out.push(rescaled(c, e, c.p_abs_w / e.p_loss_w)?);
        }
        return Ok(SolveOutcome::Equilibria(out));
    }
    // n_e does not cancel: scan the energy residual over n_e; each grid point solves the inner problem, whose roots
    // (ordered by T_e) define branches. A branch is followed between consecutive points with the same root count.
    let decades = (num.n_e_scan_max_m3 / num.n_e_scan_min_m3).log10();
    let npts = (decades * num.n_e_points_per_decade as f64).round() as usize + 1;
    let grid = log_grid(num.n_e_scan_min_m3, num.n_e_scan_max_m3, npts);
    let inner_sorted = |ne: f64| -> Result<Vec<Equilibrium>, SolveFailure> {
        let mut eqs = inner_equilibria(c, ne, num)?;
        eqs.sort_by(|a, b| a.kin.t_e.total_cmp(&b.kin.t_e));
        Ok(eqs)
    };
    let resid = |e: &Equilibrium| (e.p_loss_w - c.p_abs_w) / c.p_abs_w;
    let mut g: Vec<Vec<f64>> = Vec::with_capacity(npts);
    for &ne in &grid {
        g.push(inner_sorted(ne)?.iter().map(resid).collect());
    }
    if g.iter().all(Vec::is_empty) {
        return Ok(SolveOutcome::NotSustained);
    }
    // Where the branch count changes (a fold), a root of the energy residual could hide between the branches; it is
    // refused unless every branch on both sides has the same sign.
    for i in 0..npts - 1 {
        if g[i].len() != g[i + 1].len() {
            let side = g[i].iter().chain(&g[i + 1]).filter(|x| **x != 0.0);
            let (neg, pos) = side.fold((false, false), |(n, p), x| (n || *x < 0.0, p || *x > 0.0));
            if neg && pos {
                return fail(
                    "ROOT_AT_BRANCH_FOLD_UNRESOLVED",
                    format!(
                        "inner root count {} -> {} between n_e = {:e} and {:e} with a sign change",
                        g[i].len(),
                        g[i + 1].len(),
                        grid[i],
                        grid[i + 1]
                    ),
                );
            }
        }
    }
    let branch = |ne: f64, b: usize, m: usize| -> Result<Equilibrium, SolveFailure> {
        let mut eqs = inner_sorted(ne)?;
        if eqs.len() != m {
            return fail(
                "INNER_ROOT_LOST_IN_BRACKET",
                format!("{} inner roots at n_e = {ne:e}, expected {m}", eqs.len()),
            );
        }
        Ok(eqs.swap_remove(b))
    };
    let mut roots: Vec<(f64, usize, usize)> = Vec::new();
    for i in 0..npts {
        let m = g[i].len();
        for b in 0..m {
            if g[i][b] == 0.0 {
                roots.push((grid[i], b, m));
                continue;
            }
            if i + 1 < npts && g[i + 1].len() == m && g[i + 1][b] != 0.0 && (g[i][b] < 0.0) != (g[i + 1][b] < 0.0) {
                let f = |x: f64| branch(x.exp(), b, m).map(|e| resid(&e));
                let (x, _) = bisect(f, grid[i].ln(), grid[i + 1].ln(), g[i][b], num, "energy balance in n_e")?;
                roots.push((x.exp(), b, m));
            }
        }
    }
    if roots.is_empty() {
        return fail(
            "SCAN_RANGE_EXHAUSTED",
            format!(
                "sustained states exist but P_loss - P_abs has no sign change on n_e in [{:e}, {:e}] m^-3",
                num.n_e_scan_min_m3, num.n_e_scan_max_m3
            ),
        );
    }
    let mut out = Vec::new();
    for (ne, b, m) in roots {
        let e = branch(ne, b, m)?;
        let rel = (e.p_loss_w - c.p_abs_w).abs() / c.p_abs_w.max(e.p_loss_w);
        if rel > crate::constants::TOL_SOLVE {
            return fail(
                "ENERGY_BALANCE_NOT_CONVERGED",
                format!("relative energy residual {rel:e} at the refined n_e = {ne:e} (discontinuity in the bracket)"),
            );
        }
        out.push(e);
    }
    Ok(SolveOutcome::Equilibria(out))
}

/// Neutral densities on the trivial branch (n_e = 0) in FLOW_BALANCE: inflow balanced by effusion (LC-09).
pub fn trivial_neutrals(c: &PreparedCase) -> Vec<f64> {
    match &c.neutrals {
        PreparedNeutrals::Fixed(nf) => nf.clone(),
        PreparedNeutrals::Flow { inflow_per_s } => {
            let open_a_tau: f64 =
                c.surfaces.iter().filter(|s| s.kind.is_open()).map(|s| s.area_m2 * s.tau.unwrap_or(f64::NAN)).sum();
            (0..c.n_species())
                .map(|s| {
                    if c.is_ion(s) {
                        0.0
                    } else {
                        inflow_per_s[s]
                            / (0.25 * physics::neutral_mean_speed(c.t_g_k, c.set.species[s].mass_kg) * open_a_tau)
                    }
                })
                .collect()
        }
    }
}
