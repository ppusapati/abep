//! Frozen intake response surface v1: the reduced-order model `abep_sim/intake_tpmc.py::IntakeSurface`
//! (PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1, entry point E4).
//!
//! The reference interpolates with scipy `LinearNDInterpolator(rescale=True)`: linear interpolation in the Qhull
//! Delaunay simplex that contains the rescaled query. The v1 grid is a full tensor product, so that triangulation is
//! degenerate (16 cospherical corners per cell) and the interpolant depends on the simplices Qhull returned. That
//! triangulation is also non-conforming across some interior grid faces (Qhull 'Qt' triangulates the shared face
//! differently on its two sides), so at such a face the reference value depends on which containing simplex scipy's
//! search reaches. This module therefore reads the reference's own triangulation and search structures (captured,
//! hash-pinned) and replicates scipy's `_find_simplex` walk and barycentric arithmetic, checks the capture against
//! the frozen grid on every load, and recombines the species rows by the A9.9 S2.1 physical definitions.

use crate::constants::species_mass;
use crate::frozen::{
    read_search_v1, read_surface_v1, read_triangulation_v1, SearchStructures, SurfaceRow, Triangulation,
    TRIANGULATION_V1,
};
use crate::refuse;
use abep_types::{AbepError, AbepResult, EvalStatus};
use std::collections::BTreeMap;
use std::path::Path;

pub const AXES: [&str; 4] = ["L_over_d", "phi", "alpha", "theta_deg"];
pub const RECOMBINATION: &str = "species_consistent_v2_A9.9_S2.1";
/// scipy `_qhull` eps: a query is inside a simplex when every barycentric coordinate lies in [-eps, 1 + eps].
pub const FIND_SIMPLEX_EPS: f64 = 100.0 * f64::EPSILON;
/// scipy `_qhull` eps_broad (leeway towards a degenerate neighbour in the brute-force search).
pub const FIND_SIMPLEX_EPS_BROAD: f64 = 1.4901161193847656e-8; // sqrt(DBL_EPSILON), exact
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

/// The reference Delaunay structure (scipy `DelaunayInfo`): simplices, barycentric transforms (None = degenerate),
/// neighbours, lifted facet equations, paraboloid scale / shift and bounds, in rescaled coordinates.
#[derive(Debug, Clone)]
struct Delaunay {
    verts: Vec<[usize; 5]>,
    transform: Vec<Option<[[f64; 4]; 5]>>,
    neighbors: Vec<[i64; 5]>,
    equations: Vec<[f64; 6]>,
    paraboloid_scale: f64,
    paraboloid_shift: f64,
    min_bound: [f64; 4],
    max_bound: [f64; 4],
}

/// scipy `_barycentric_coordinates`.
fn barycentric(t: &[[f64; 4]; 5], x: &[f64; 4]) -> [f64; 5] {
    let mut c = [0.0; 5];
    c[4] = 1.0;
    for i in 0..4 {
        let mut ci = 0.0;
        for ((tij, xj), rj) in t[i].iter().zip(x).zip(&t[4]) {
            ci += tij * (xj - rj);
        }
        c[i] = ci;
        c[4] -= ci;
    }
    c
}

#[inline]
fn within(c: f64, lo: f64, hi: f64) -> bool {
    lo <= c && c <= hi
}

impl Delaunay {
    /// scipy `_is_point_fully_outside`.
    fn fully_outside(&self, x: &[f64; 4], eps: f64) -> bool {
        (0..4).any(|i| x[i] < self.min_bound[i] - eps || x[i] > self.max_bound[i] + eps)
    }

    /// scipy `_find_simplex_bruteforce`.
    fn bruteforce(&self, x: &[f64; 4], c: &mut [f64; 5], eps: f64, eps_broad: f64) -> Option<usize> {
        if self.fully_outside(x, eps) {
            return None;
        }
        for (isimplex, t) in self.transform.iter().enumerate() {
            match t {
                Some(t) => {
                    // _barycentric_inside: stops at the first coordinate outside
                    c[4] = 1.0;
                    let mut inside = true;
                    for i in 0..4 {
                        let mut ci = 0.0;
                        for ((tij, xj), rj) in t[i].iter().zip(x).zip(&t[4]) {
                            ci += tij * (xj - rj);
                        }
                        c[i] = ci;
                        c[4] -= ci;
                        if !within(ci, -eps, 1.0 + eps) {
                            inside = false;
                            break;
                        }
                    }
                    if inside && within(c[4], -eps, 1.0 + eps) {
                        return Some(isimplex);
                    }
                }
                None => {
                    for &nb in &self.neighbors[isimplex] {
                        if nb == -1 {
                            continue;
                        }
                        let nb = nb as usize;
                        let Some(tn) = &self.transform[nb] else { continue };
                        *c = barycentric(tn, x);
                        let inside = (0..5).all(|m| {
                            let lo = if self.neighbors[nb][m] == isimplex as i64 { -eps_broad } else { -eps };
                            within(c[m], lo, 1.0 + eps)
                        });
                        if inside {
                            return Some(nb);
                        }
                    }
                }
            }
        }
        None
    }

    /// scipy `_find_simplex_directed`.
    fn directed(&self, x: &[f64; 4], c: &mut [f64; 5], start: usize, eps: f64, eps_broad: f64) -> Option<usize> {
        let mut isimplex = start as i64;
        for _ in 0..(1 + self.verts.len() / 4) {
            if isimplex == -1 {
                return None;
            }
            let s = isimplex as usize;
            let Some(t) = &self.transform[s] else {
                // NaN transform: every coordinate test fails ("we've failed utterly")
                return self.bruteforce(x, c, eps, eps_broad);
            };
            let mut inside = 1;
            for k in 0..5 {
                if k == 4 {
                    c[4] = 1.0;
                    for j in 0..4 {
                        c[4] -= c[j];
                    }
                } else {
                    let mut ck = 0.0;
                    for ((tkj, xj), rj) in t[k].iter().zip(x).zip(&t[4]) {
                        ck += tkj * (xj - rj);
                    }
                    c[k] = ck;
                }
                if c[k] < -eps {
                    let m = self.neighbors[s][k];
                    if m == -1 {
                        return None;
                    }
                    isimplex = m;
                    inside = -1;
                    break;
                } else if c[k] <= 1.0 + eps {
                    // inside this coordinate
                } else {
                    inside = 0;
                }
            }
            match inside {
                -1 => continue,
                1 => return Some(s),
                _ => return self.bruteforce(x, c, eps, eps_broad),
            }
        }
        self.bruteforce(x, c, eps, eps_broad)
    }

    /// scipy `_find_simplex` with start 0 (LinearNDInterpolator, one query per call): walk on the lifted paraboloid
    /// to a facet with positive plane distance, then the directed search.
    fn find_simplex(&self, x: &[f64; 4], c: &mut [f64; 5]) -> Option<usize> {
        let (eps, eps_broad) = (FIND_SIMPLEX_EPS, FIND_SIMPLEX_EPS_BROAD);
        if self.fully_outside(x, eps) || self.verts.is_empty() {
            return None;
        }
        let mut z = [x[0], x[1], x[2], x[3], 0.0];
        for xi in x {
            z[4] += xi * xi;
        }
        z[4] *= self.paraboloid_scale;
        z[4] += self.paraboloid_shift;
        let dist = |k: usize| {
            let e = &self.equations[k];
            let mut d = e[5];
            for (eq, zq) in e.iter().zip(&z) {
                d += eq * zq;
            }
            d
        };
        let mut isimplex = 0usize;
        let mut best = dist(isimplex);
        let mut changed = true;
        while changed {
            if best > 0.0 {
                break;
            }
            changed = false;
            for k in 0..5 {
                let nb = self.neighbors[isimplex][k];
                if nb == -1 {
                    continue;
                }
                let d = dist(nb as usize);
                if d > best + eps * (1.0 + best.abs()) {
                    // scipy jumps here and continues the same k loop on the new simplex's neighbours
                    isimplex = nb as usize;
                    best = d;
                    changed = true;
                }
            }
        }
        self.directed(x, c, isimplex, eps, eps_broad)
    }
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
    delaunay: Delaunay,
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

/// Structural checks of the captured triangulation and search structures against the grid (contract
/// rust_load_checks (c), (d), plus: transforms equal an independent inverse to 1e-10, their last row is the rescaled
/// vertex bitwise, None exactly for the degenerate simplices, neighbours symmetric, bounds bitwise).
fn check_triangulation(tri: &Triangulation, search: SearchStructures) -> AbepResult<Delaunay> {
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
    for (k, (s, &degenerate)) in tri.simplices.iter().zip(&tri.degenerate).enumerate() {
        let ii: Vec<[i64; 4]> = s.iter().map(|&k| idx[k]).collect();
        let cell: [i64; 4] = std::array::from_fn(|j| ii.iter().map(|v| v[j]).min().unwrap());
        if (0..4).any(|j| ii.iter().map(|v| v[j]).max().unwrap() - cell[j] > 1) {
            return Err(model(format!("simplex {s:?} spans more than one grid cell")));
        }
        let det = det4_int(std::array::from_fn(|k| std::array::from_fn(|j| ii[k][j] - ii[4][j])));
        if degenerate != (det == 0) {
            return Err(model(format!("simplex {s:?}: degenerate flag {degenerate} but index-space det {det}")));
        }
        if degenerate != search.transform[k].is_none() {
            return Err(model(format!("simplex {k}: transform presence disagrees with the degenerate flag")));
        }
        for (m, &nb) in search.neighbors[k].iter().enumerate() {
            if nb >= 0 && !search.neighbors[nb as usize].contains(&(k as i64)) {
                return Err(model(format!("simplex {k}: neighbour {m} ({nb}) does not list it back")));
            }
        }
        let Some(t) = &search.transform[k] else { continue };
        *cell_volume.entry(cell).or_default() += det.abs();
        let r = rescaled[s[4]];
        if (0..4).any(|j| t[4][j].to_bits() != r[j].to_bits()) {
            return Err(model(format!("simplex {k}: transform row 4 is not the rescaled last vertex")));
        }
        let tm: [[f64; 4]; 4] = std::array::from_fn(|i| std::array::from_fn(|j| rescaled[s[j]][i] - r[i]));
        let tinv = invert4(tm).ok_or_else(|| model(format!("simplex {s:?} is singular")))?;
        if (0..4).any(|i| (0..4).any(|j| (t[i][j] - tinv[i][j]).abs() > 1e-10 * tinv[i][j].abs().max(1.0))) {
            return Err(model(format!("simplex {k}: captured transform differs from the inverse of its matrix")));
        }
    }
    let n_cells: usize = axes.iter().map(|a| a.len() - 1).product();
    if cell_volume.len() != n_cells || cell_volume.values().any(|&v| v != 24) {
        return Err(model(
            "non-degenerate simplices do not tile every grid cell exactly (|det| sum 4! per cell)".into(),
        ));
    }
    for j in 0..4 {
        let lo = rescaled.iter().map(|p| p[j]).fold(f64::INFINITY, f64::min);
        let hi = rescaled.iter().map(|p| p[j]).fold(f64::NEG_INFINITY, f64::max);
        if lo.to_bits() != search.min_bound[j].to_bits() || hi.to_bits() != search.max_bound[j].to_bits() {
            return Err(model(format!("axis {}: captured min / max bound differ from the rescaled grid", AXES[j])));
        }
    }
    Ok(Delaunay {
        verts: tri.simplices.clone(),
        transform: search.transform,
        neighbors: search.neighbors,
        equations: search.equations,
        paraboloid_scale: search.paraboloid_scale,
        paraboloid_shift: search.paraboloid_shift,
        min_bound: search.min_bound,
        max_bound: search.max_bound,
    })
}

impl FrozenIntakeSurfaces {
    /// Load both scattering tables of the frozen v1 with the build-state mean molecular mass `m_mean_build_kg`
    /// (reference: `frozen_surface_build_atmosphere()["m_mean"]`, supplied by the atmosphere layer).
    pub fn load(repo_root: &Path, m_mean_build_kg: f64) -> AbepResult<Self> {
        let rows = read_surface_v1(repo_root)?;
        let tri = read_triangulation_v1(repo_root)?;
        let search = read_search_v1(repo_root, tri.simplices.len())?;
        let delaunay = check_triangulation(&tri, search)?;
        Ok(FrozenIntakeSurfaces {
            maxwell: IntakeSurface::build(&rows, "maxwell", &tri, &delaunay, m_mean_build_kg)?,
            cll: IntakeSurface::build(&rows, "cll", &tri, &delaunay, m_mean_build_kg)?,
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
        delaunay: &Delaunay,
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
            delaunay: delaunay.clone(),
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

    /// The simplex scipy selects for a query (index into the captured triangulation) and its barycentric
    /// coordinates; None outside the hull.
    fn locate(&self, x: [f64; 4]) -> Option<(usize, [f64; 5])> {
        let xr: [f64; 4] = std::array::from_fn(|j| (x[j] - self.offset[j]) / self.scale[j]);
        let mut c = [0.0; 5];
        self.delaunay.find_simplex(&xr, &mut c).map(|s| (s, c))
    }

    /// Index of the simplex the reference would interpolate in (diagnostics; None outside the hull).
    pub fn selected_simplex(&self, l_over_d: f64, phi: f64, alpha: f64, theta_deg: f64) -> Option<usize> {
        self.locate([l_over_d, phi, alpha, theta_deg]).map(|(s, _)| s)
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
                    for (ck, &v) in c.iter().zip(&self.delaunay.verts[s]) {
                        out += ck * self.values[sp][col][v];
                    }
                    out
                })
            })
            .collect())
    }

    /// Authoritative species-row values at a point: per species (table order) the interpolated
    /// [eta_c, C_D, CR_passive, K_back, mass_kg] in the simplex the replicated scipy walk selects (the same rows
    /// [`IntakeSurface::eval`] recombines). Additive accessor for the B2-OF-01 diagnostic
    /// (ACCEPT-DIAG-B2-OF-01-INTERP-SENSITIVITY-V1, SC-WP-10); outside the table range it refuses as `eval` does.
    pub fn species_rows_at(&self, l_over_d: f64, phi: f64, alpha: f64, theta_deg: f64) -> AbepResult<Vec<[f64; 5]>> {
        if !self.in_bounds(l_over_d, phi, alpha, theta_deg) {
            return Err(refuse(
                "OUT_OF_BOUNDS",
                format!(
                    "intake ROM extrapolation: L/d={l_over_d}, phi={phi}, alpha={alpha}, theta={theta_deg} outside {:?}",
                    self.bounds
                ),
            ));
        }
        self.rows([l_over_d, phi, alpha, theta_deg])
    }

    /// Every non-degenerate captured simplex whose five barycentric coordinates of the rescaled point lie in
    /// [-eps, 1 + eps] with the reference's own find-simplex tolerance eps = [`FIND_SIMPLEX_EPS`], and the species-row
    /// values interpolated in each (the adjacent-simplex ambiguity envelope of finding B2-OF-01). Read only: the
    /// authoritative value stays [`IntakeSurface::species_rows_at`]. Additive accessor (SC-WP-10 diagnostic).
    pub fn containing_simplex_rows(
        &self,
        l_over_d: f64,
        phi: f64,
        alpha: f64,
        theta_deg: f64,
    ) -> Vec<(usize, Vec<[f64; N_COLS]>)> {
        let x = [l_over_d, phi, alpha, theta_deg];
        let xr: [f64; 4] = std::array::from_fn(|j| (x[j] - self.offset[j]) / self.scale[j]);
        let eps = FIND_SIMPLEX_EPS;
        let mut out = vec![];
        for (s, t) in self.delaunay.transform.iter().enumerate() {
            let Some(t) = t else { continue };
            let c = barycentric(t, &xr);
            if !c.iter().all(|ck| within(*ck, -eps, 1.0 + eps)) {
                continue;
            }
            let rows = (0..self.species.len())
                .map(|sp| {
                    std::array::from_fn(|col| {
                        let mut v = 0.0;
                        for (ck, &k) in c.iter().zip(&self.delaunay.verts[s]) {
                            v += ck * self.values[sp][col][k];
                        }
                        v
                    })
                })
                .collect();
            out.push((s, rows));
        }
        out
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
