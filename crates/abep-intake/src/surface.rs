//! Frozen intake response surface v1: the reduced-order model `abep_sim/intake_tpmc.py::IntakeSurface`
//! (PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1, entry point E4).
//!
//! The reference interpolates with scipy `LinearNDInterpolator(rescale=True)`: linear interpolation in the Qhull
//! Delaunay simplex that contains the rescaled query. The v1 grid is a full tensor product, so that triangulation is
//! degenerate (16 cospherical corners per cell) and the interpolant depends on the simplices Qhull returned. This module
//! reads the reference's own triangulation (captured, hash-pinned) instead of re-triangulating, checks it against the
//! frozen grid on every load, and recombines the species rows by the A9.9 S2.1 physical definitions.

use crate::constants::species_mass;
use crate::frozen::{read_surface_v1, read_triangulation_v1, SurfaceRow, Triangulation, TRIANGULATION_V1};
use crate::refuse;
use abep_types::{AbepError, AbepResult, EvalStatus};
use std::collections::BTreeMap;
use std::path::Path;

pub const AXES: [&str; 4] = ["L_over_d", "phi", "alpha", "theta_deg"];
pub const RECOMBINATION: &str = "species_consistent_v2_A9.9_S2.1";
/// scipy `_qhull` eps: a query is inside a simplex when every barycentric coordinate lies in [-eps, 1 + eps].
pub const FIND_SIMPLEX_EPS: f64 = 100.0 * f64::EPSILON;
/// Strings of the reference `IntakeSurface.domain()` (copied verbatim).
pub const DOMAIN_ATMOSPHERE_STATE: &str =
    "single build state (not an axis); off-build use is an approximation, see intake_surface_v2_spec";
pub const DOMAIN_OUTSIDE: &str = "ValueError (fail closed)";

/// Interpolated columns, in the reference order of `IntakeSurface.f[sp]`.
const N_COLS: usize = 5;
const ETA_C: usize = 0;
const C_D: usize = 1;
const CR_PASSIVE: usize = 2;
const K_BACK: usize = 3;
const MASS_KG: usize = 4;

#[derive(Debug, Clone)]
struct Simplex {
    verts: [usize; 5],
    /// inverse of T[i][j] = p[verts[j]][i] - p[verts[4]][i]
    tinv: [[f64; 4]; 4],
    /// rescaled coordinates of verts[4]
    r: [f64; 4],
}

/// Per-species outputs of a surface evaluation (reference `out["species"][s]`).
#[derive(Debug, Clone, PartialEq)]
pub struct SpeciesEval {
    pub eta_c: f64,
    pub c_d_row: f64,
    pub c_d_species: f64,
    pub cr_passive: f64,
    pub k_back: f64,
    pub mass_fraction: f64,
    pub mole_fraction: f64,
    pub collected_mass_fraction: f64,
    pub collected_mole_fraction: f64,
}

/// Mixture outputs of a surface evaluation (reference `IntakeSurface.__call__` on a species-resolved table).
#[derive(Debug, Clone, PartialEq)]
pub struct SurfaceEval {
    pub eta_c: f64,
    pub c_d: f64,
    pub k_back: f64,
    pub mass_kg: f64,
    pub cr_passive: f64,
    /// species with nonzero free-stream mass fraction, in table order
    pub species: Vec<(String, SpeciesEval)>,
    pub recombination: &'static str,
}

/// `IntakeSurface.domain()`.
#[derive(Debug, Clone, PartialEq)]
pub struct Domain {
    pub axes: [(f64, f64); 4],
    pub species: Vec<String>,
    pub atmosphere_state: &'static str,
    pub outside_domain: &'static str,
}

/// The v1 surface of one scattering kernel.
#[derive(Debug, Clone)]
pub struct IntakeSurface {
    scattering: String,
    species: Vec<String>,
    m_s: Vec<f64>,
    /// values[species][column][point]
    values: Vec<[Vec<f64>; N_COLS]>,
    bounds: [(f64, f64); 4],
    max_unresolved: f64,
    m_mean_build_kg: f64,
    offset: [f64; 4],
    scale: [f64; 4],
    simplices: Vec<Simplex>,
}

/// Both scattering tables of the frozen v1 (the reference `intake._tpmc_surface` cache, built explicitly).
#[derive(Debug, Clone)]
pub struct FrozenIntakeSurfaces {
    pub maxwell: IntakeSurface,
    pub cll: IntakeSurface,
}

fn model(msg: String) -> AbepError {
    AbepError::Model { message: format!("{TRIANGULATION_V1}: {msg}") }
}

/// Gauss-Jordan inverse with partial pivoting; None for an exactly singular matrix.
fn invert4(a: [[f64; 4]; 4]) -> Option<[[f64; 4]; 4]> {
    let mut m = a;
    let mut inv = [[0.0; 4]; 4];
    for (i, row) in inv.iter_mut().enumerate() {
        row[i] = 1.0;
    }
    for col in 0..4 {
        let piv = (col..4).max_by(|&i, &j| m[i][col].abs().total_cmp(&m[j][col].abs()))?;
        if m[piv][col] == 0.0 {
            return None;
        }
        m.swap(col, piv);
        inv.swap(col, piv);
        let d = m[col][col];
        for k in 0..4 {
            m[col][k] /= d;
            inv[col][k] /= d;
        }
        for row in 0..4 {
            if row != col {
                let f = m[row][col];
                if f != 0.0 {
                    for k in 0..4 {
                        m[row][k] -= f * m[col][k];
                        inv[row][k] -= f * inv[col][k];
                    }
                }
            }
        }
    }
    Some(inv)
}

fn det4_int(m: [[i64; 4]; 4]) -> i64 {
    fn det3(a: [[i64; 3]; 3]) -> i64 {
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    }
    let mut d = 0;
    for c in 0..4 {
        let mut minor = [[0i64; 3]; 3];
        for (r, row) in m.iter().enumerate().skip(1) {
            let mut cc = 0;
            for (k, &v) in row.iter().enumerate() {
                if k != c {
                    minor[r - 1][cc] = v;
                    cc += 1;
                }
            }
        }
        let s = if c % 2 == 0 { 1 } else { -1 };
        d += s * m[0][c] * det3(minor);
    }
    d
}

/// Structural checks of the captured triangulation against the grid (contract rust_load_checks (c), (d)); returns
/// the non-degenerate simplices with their barycentric transforms.
fn check_triangulation(tri: &Triangulation) -> AbepResult<Vec<Simplex>> {
    let n = tri.points.len() as f64;
    let mut offset = [0.0; 4];
    let mut lo = [f64::INFINITY; 4];
    let mut hi = [f64::NEG_INFINITY; 4];
    for p in &tri.points {
        for j in 0..4 {
            offset[j] += p[j];
            lo[j] = lo[j].min(p[j]);
            hi[j] = hi[j].max(p[j]);
        }
    }
    let scale: [f64; 4] = std::array::from_fn(|j| {
        let s = hi[j] - lo[j];
        if s > 0.0 {
            s
        } else {
            1.0
        }
    });
    for j in 0..4 {
        offset[j] /= n;
        if offset[j].to_bits() != tri.rescale.offset[j].to_bits()
            || scale[j].to_bits() != tri.rescale.scale[j].to_bits()
        {
            return Err(model(format!("axis {}: recomputed rescale differs from the capture", AXES[j])));
        }
    }
    // grid axes and index-space coordinates
    let axes: Vec<Vec<f64>> = (0..4)
        .map(|j| {
            let mut v: Vec<f64> = tri.points.iter().map(|p| p[j]).collect();
            v.sort_by(f64::total_cmp);
            v.dedup();
            v
        })
        .collect();
    let n_grid: usize = axes.iter().map(Vec::len).product();
    if n_grid != tri.points.len() {
        return Err(model("points are not a full tensor grid".into()));
    }
    let idx: Vec<[i64; 4]> = tri
        .points
        .iter()
        .map(|p| std::array::from_fn(|j| axes[j].iter().position(|&v| v == p[j]).expect("axis value") as i64))
        .collect();
    let rescaled: Vec<[f64; 4]> = tri
        .points
        .iter()
        .map(|p| std::array::from_fn(|j| (p[j] - tri.rescale.offset[j]) / tri.rescale.scale[j]))
        .collect();
    let mut cell_volume: BTreeMap<[i64; 4], i64> = BTreeMap::new();
    let mut out = Vec::new();
    for (s, &degenerate) in tri.simplices.iter().zip(&tri.degenerate) {
        let ii: Vec<[i64; 4]> = s.iter().map(|&k| idx[k]).collect();
        let cell: [i64; 4] = std::array::from_fn(|j| ii.iter().map(|v| v[j]).min().unwrap());
        if (0..4).any(|j| ii.iter().map(|v| v[j]).max().unwrap() - cell[j] > 1) {
            return Err(model(format!("simplex {s:?} spans more than one grid cell")));
        }
        let det = det4_int(std::array::from_fn(|k| std::array::from_fn(|j| ii[k][j] - ii[4][j])));
        if degenerate != (det == 0) {
            return Err(model(format!("simplex {s:?}: degenerate flag {degenerate} but index-space det {det}")));
        }
        if degenerate {
            continue;
        }
        *cell_volume.entry(cell).or_default() += det.abs();
        let r = rescaled[s[4]];
        let t: [[f64; 4]; 4] = std::array::from_fn(|i| std::array::from_fn(|j| rescaled[s[j]][i] - r[i]));
        let tinv = invert4(t).ok_or_else(|| model(format!("simplex {s:?} is singular")))?;
        out.push(Simplex { verts: *s, tinv, r });
    }
    let n_cells: usize = axes.iter().map(|a| a.len() - 1).product();
    if cell_volume.len() != n_cells || cell_volume.values().any(|&v| v != 24) {
        return Err(model(
            "non-degenerate simplices do not tile every grid cell exactly (|det| sum 4! per cell)".into(),
        ));
    }
    Ok(out)
}

impl FrozenIntakeSurfaces {
    /// Load both scattering tables of the frozen v1 with the build-state mean molecular mass `m_mean_build_kg`
    /// (reference: `frozen_surface_build_atmosphere()["m_mean"]`, supplied by the atmosphere layer).
    pub fn load(repo_root: &Path, m_mean_build_kg: f64) -> AbepResult<Self> {
        let rows = read_surface_v1(repo_root)?;
        let tri = read_triangulation_v1(repo_root)?;
        let simplices = check_triangulation(&tri)?;
        Ok(FrozenIntakeSurfaces {
            maxwell: IntakeSurface::build(&rows, "maxwell", &tri, &simplices, m_mean_build_kg)?,
            cll: IntakeSurface::build(&rows, "cll", &tri, &simplices, m_mean_build_kg)?,
        })
    }

    /// The table of one scattering kernel; any other name is refused (contract DIV-07).
    pub fn get(&self, scattering: &str) -> AbepResult<&IntakeSurface> {
        match scattering {
            "maxwell" => Ok(&self.maxwell),
            "cll" => Ok(&self.cll),
            other => Err(refuse(
                "UNKNOWN_SCATTERING",
                format!("intake surface: no frozen table for wall-scattering model {other:?} (admitted: maxwell, cll)"),
            )),
        }
    }
}

impl IntakeSurface {
    fn build(
        rows: &[SurfaceRow],
        scattering: &str,
        tri: &Triangulation,
        simplices: &[Simplex],
        m_mean_build_kg: f64,
    ) -> AbepResult<Self> {
        let sub: Vec<&SurfaceRow> = rows.iter().filter(|r| r.scattering == scattering).collect();
        let mut species: Vec<String> = sub.iter().map(|r| r.species.clone()).collect();
        species.sort();
        species.dedup();
        let mut m_s = Vec::new();
        let mut values = Vec::new();
        for sp in &species {
            let m = species_mass(sp).ok_or_else(|| {
                refuse("UNKNOWN_SPECIES", format!("IntakeSurface: species {sp:?} has no molecular mass"))
            })?;
            m_s.push(m);
            let r: Vec<&&SurfaceRow> = sub.iter().filter(|r| &r.species == sp).collect();
            if r.len() != tri.points.len()
                || r.iter().zip(&tri.points).any(|(r, p)| {
                    [r.l_over_d, r.phi, r.alpha, r.theta_deg].iter().zip(p).any(|(a, b)| a.to_bits() != b.to_bits())
                })
            {
                return Err(model(format!("{scattering}/{sp} rows are not the captured points in captured order")));
            }
            values.push([
                r.iter().map(|r| r.eta_c).collect(),
                r.iter().map(|r| r.c_d).collect(),
                r.iter().map(|r| r.cr_passive).collect(),
                r.iter().map(|r| r.k_back).collect(),
                r.iter().map(|r| r.mass_kg).collect(),
            ]);
        }
        if species.is_empty() {
            return Err(model(format!("no rows for scattering {scattering}")));
        }
        if !(m_mean_build_kg.is_finite() && m_mean_build_kg > 0.0) {
            return Err(refuse(
                "M_MEAN_BUILD_REQUIRED",
                "IntakeSurface: a species-resolved table needs m_mean_build_kg (finite, > 0); no default is assumed",
            ));
        }
        let axis = |f: fn(&SurfaceRow) -> f64| -> (f64, f64) {
            sub.iter().map(|r| f(r)).fold((f64::INFINITY, f64::NEG_INFINITY), |(lo, hi), v| (lo.min(v), hi.max(v)))
        };
        let bounds = [axis(|r| r.l_over_d), axis(|r| r.phi), axis(|r| r.alpha), axis(|r| r.theta_deg)];
        let max_unresolved = sub.iter().map(|r| r.unresolved_fraction).fold(f64::NEG_INFINITY, f64::max);
        Ok(IntakeSurface {
            scattering: scattering.to_string(),
            species,
            m_s,
            values,
            bounds,
            max_unresolved,
            m_mean_build_kg,
            offset: tri.rescale.offset,
            scale: tri.rescale.scale,
            simplices: simplices.to_vec(),
        })
    }

    pub fn scattering(&self) -> &str {
        &self.scattering
    }

    /// Species of the table, sorted (reference `IntakeSurface.species`).
    pub fn species(&self) -> &[String] {
        &self.species
    }

    /// Largest unresolved-particle fraction of the table rows (reference `max_unresolved`).
    pub fn max_unresolved(&self) -> f64 {
        self.max_unresolved
    }

    pub fn bounds(&self) -> [(f64, f64); 4] {
        self.bounds
    }

    pub fn domain(&self) -> Domain {
        Domain {
            axes: self.bounds,
            species: self.species.clone(),
            atmosphere_state: DOMAIN_ATMOSPHERE_STATE,
            outside_domain: DOMAIN_OUTSIDE,
        }
    }

    /// Reference `in_bounds`: every axis inside its closed table range (NaN is outside).
    pub fn in_bounds(&self, l_over_d: f64, phi: f64, alpha: f64, theta_deg: f64) -> bool {
        [l_over_d, phi, alpha, theta_deg].iter().zip(&self.bounds).all(|(&v, &(lo, hi))| lo <= v && v <= hi)
    }

    /// Containing non-degenerate simplex (first in captured order) and its barycentric coordinates.
    fn locate(&self, x: [f64; 4]) -> Option<(&Simplex, [f64; 5])> {
        let xr: [f64; 4] = std::array::from_fn(|j| (x[j] - self.offset[j]) / self.scale[j]);
        self.simplices.iter().find_map(|s| {
            let mut c = [0.0; 5];
            c[4] = 1.0;
            // scipy _barycentric_coordinates: c_i = sum_j Tinv[i][j] (x_j - r_j), c_4 = 1 - c_0 - c_1 - c_2 - c_3
            for i in 0..4 {
                let mut ci = 0.0;
                for ((t, x), r) in s.tinv[i].iter().zip(&xr).zip(&s.r) {
                    ci += t * (x - r);
                }
                c[i] = ci;
                c[4] -= ci;
            }
            c.iter().all(|ck| (-FIND_SIMPLEX_EPS..=1.0 + FIND_SIMPLEX_EPS).contains(ck)).then_some((s, c))
        })
    }

    fn rows(&self, x: [f64; 4]) -> AbepResult<Vec<[f64; N_COLS]>> {
        let (s, c) = self.locate(x).ok_or_else(|| {
            refuse(
                "NON_FINITE_ROW",
                format!(
                    "intake ROM: non-finite interpolation at {x:?} (outside the interpolation hull; no extrapolation)"
                ),
            )
        })?;
        Ok((0..self.species.len())
            .map(|sp| {
                std::array::from_fn(|col| {
                    let mut out = 0.0;
                    for (ck, &v) in c.iter().zip(&s.verts) {
                        out += ck * self.values[sp][col][v];
                    }
                    out
                })
            })
            .collect())
    }

    /// Reference `IntakeSurface.__call__` on the species-resolved table with free-stream MASS fractions.
    pub fn eval(
        &self,
        l_over_d: f64,
        phi: f64,
        alpha: f64,
        theta_deg: f64,
        fractions: Option<&BTreeMap<String, f64>>,
    ) -> AbepResult<SurfaceEval> {
        if !self.in_bounds(l_over_d, phi, alpha, theta_deg) {
            return Err(refuse(
                "OUT_OF_BOUNDS",
                format!(
                    "intake ROM extrapolation: L/d={l_over_d}, phi={phi}, alpha={alpha}, theta={theta_deg} outside {:?}",
                    self.bounds
                ),
            ));
        }
        let fr = match fractions {
            Some(f) if !f.is_empty() => f,
            _ => {
                return Err(refuse(
                    "FRACTIONS_REQUIRED",
                    format!(
                        "intake ROM: a species-resolved table needs explicit free-stream mass fractions {:?}",
                        self.species
                    ),
                ))
            }
        };
        let bad: Vec<_> = fr.iter().filter(|(_, v)| !v.is_finite() || **v < 0.0).collect();
        if !bad.is_empty() {
            return Err(refuse(
                "FRACTION_INVALID",
                format!("intake ROM: mass fractions must be finite and >= 0, got {bad:?}"),
            ));
        }
        let foreign: Vec<_> =
            fr.iter().filter(|(s, v)| !self.species.contains(s) && **v > 0.0).map(|(s, _)| s).collect();
        if !foreign.is_empty() {
            return Err(refuse(
                "FOREIGN_SPECIES",
                format!(
                    "intake ROM: species {foreign:?} with non-zero fraction are not in the frozen table {:?}",
                    self.species
                ),
            ));
        }
        let get = |s: &String| fr.get(s).copied().unwrap_or(0.0);
        let mut tot = 0.0;
        for s in &self.species {
            tot += get(s);
        }
        if tot.partial_cmp(&0.0) != Some(std::cmp::Ordering::Greater) {
            return Err(refuse(
                "ALL_ZERO",
                format!("intake ROM: all mass fractions are zero for species {:?}", self.species),
            ));
        }
        let rows = self.rows([l_over_d, phi, alpha, theta_deg])?;
        // species with w_s > 0, in table order
        let used: Vec<usize> = (0..self.species.len()).filter(|&i| get(&self.species[i]) > 0.0).collect();
        let w: Vec<f64> = used.iter().map(|&i| get(&self.species[i]) / tot).collect();
        let row = |k: usize, col: usize| rows[used[k]][col];
        let m = |k: usize| self.m_s[used[k]];
        let sum = |v: &dyn Fn(usize) -> f64| {
            let mut acc = 0.0;
            for k in 0..used.len() {
                acc += v(k);
            }
            acc
        };
        let inv_m: Vec<f64> = (0..used.len()).map(|k| w[k] / m(k)).collect();
        let s_inv = sum(&|k| inv_m[k]);
        let x: Vec<f64> = inv_m.iter().map(|v| v / s_inv).collect();
        let mb = self.m_mean_build_kg;
        let cd_s: Vec<f64> = (0..used.len()).map(|k| row(k, C_D) * mb / m(k)).collect();
        let c_d = sum(&|k| w[k] * cd_s[k]);
        let cr = sum(&|k| x[k] * row(k, CR_PASSIVE));
        let eta_c = sum(&|k| w[k] * row(k, ETA_C));
        let eff: Vec<f64> = (0..used.len()).map(|k| x[k] * row(k, CR_PASSIVE) / m(k).sqrt()).collect();
        let eff_tot = sum(&|k| eff[k]);
        let k_back = if eff_tot > 0.0 { sum(&|k| eff[k] * row(k, K_BACK)) / eff_tot } else { f64::NAN };
        let mass_kg = sum(&|k| w[k] * row(k, MASS_KG));
        let n_col: Vec<f64> = (0..used.len()).map(|k| x[k] * row(k, ETA_C)).collect();
        let n_col_tot = sum(&|k| n_col[k]);
        let species = (0..used.len())
            .map(|k| {
                (
                    self.species[used[k]].clone(),
                    SpeciesEval {
                        eta_c: row(k, ETA_C),
                        c_d_row: row(k, C_D),
                        c_d_species: cd_s[k],
                        cr_passive: row(k, CR_PASSIVE),
                        k_back: row(k, K_BACK),
                        mass_fraction: w[k],
                        mole_fraction: x[k],
                        collected_mass_fraction: if eta_c > 0.0 { w[k] * row(k, ETA_C) / eta_c } else { f64::NAN },
                        collected_mole_fraction: if n_col_tot > 0.0 { n_col[k] / n_col_tot } else { f64::NAN },
                    },
                )
            })
            .collect();
        Ok(SurfaceEval { eta_c, c_d, k_back, mass_kg, cr_passive: cr, species, recombination: RECOMBINATION })
    }
}

/// The SC-WP-02 fail-closed gate "intake surface v2 axes unregistered -> NOT_EVALUATED": the v2 build of
/// `abep_sim/intake_surface_v2_spec.py` refuses (IntakeSurfaceV2Blocked) while the A9.13 S6.2 AOCS relative-wind
/// pointing envelope and the other axes are unregistered. No v2 value exists; v1 stays the frozen reference.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SurfaceV2Gate {
    pub status: EvalStatus,
    pub label: &'static str,
    pub primary_blocker: &'static str,
    pub unregistered: [&'static str; 6],
}

pub fn surface_v2_gate() -> SurfaceV2Gate {
    SurfaceV2Gate {
        status: EvalStatus::NotEvaluated,
        label: "BLOCKED_PENDING_AOCS_POINTING_ENVELOPE",
        primary_blocker: "theta_deg = TBD_AOCS_POINTING_ENVELOPE (A9.13 S6.2)",
        unregistered: [
            "theta_deg",
            "L_over_d",
            "alpha",
            "atmosphere_state",
            "phi",
            "convergence_criterion.n_per_point",
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn invert4_inverts() {
        let a = [[2.0, 1.0, 0.0, 0.0], [0.0, 1.0, 3.0, 0.0], [1.0, 0.0, 0.0, 4.0], [0.0, 0.5, 0.0, 1.0]];
        let inv = invert4(a).unwrap();
        for (i, row) in a.iter().enumerate() {
            for j in 0..4 {
                let v: f64 = row.iter().zip(&inv).map(|(x, inv_k)| x * inv_k[j]).sum();
                assert!((v - if i == j { 1.0 } else { 0.0 }).abs() < 1e-14);
            }
        }
        assert!(
            invert4([[1.0, 2.0, 0.0, 0.0], [2.0, 4.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]).is_none()
        );
    }

    #[test]
    fn integer_determinant() {
        let id = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
        assert_eq!(det4_int(id), 1);
        assert_eq!(det4_int([[1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]), 0);
        assert_eq!(det4_int([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 2]]), -2);
    }

    #[test]
    fn v2_gate_is_not_evaluated() {
        let g = surface_v2_gate();
        assert_eq!(g.status, EvalStatus::NotEvaluated);
        assert!(!g.status.is_evaluated());
        assert_eq!(g.unregistered[0], "theta_deg");
    }
}
