//! B2-OF-01 NUMERICAL_INTERPOLATION_SENSITIVITY diagnostic (A9.31 sec. 6; preregistration
//! `docs/rust_migration/contracts/DIAG-B2-OF-01-INTERP-SENSITIVITY/acceptance_prereg_v1.json`).
//!
//! The frozen intake surface v1 interpolant (scipy / Qhull LinearNDInterpolator semantics, replicated by abep-intake)
//! is non-conforming across some interior faces of its degenerate tensor grid (finding B2-OF-01). The authoritative
//! value stays the simplex the replicated walk selects. For a point lying EXACTLY on a known degenerate internal face
//! (IEEE equality with a canonical interior grid value; no epsilon), this module additionally reports the
//! adjacent-simplex ambiguity envelope over every captured simplex that contains the point within the reference's
//! own find-simplex tolerance. The record carries no robustness, feasibility or selection field: a favourable branch
//! never makes a candidate robust, and nothing here feeds back into F7 / F8.

use abep_atmos::msis21::{atmosphere, Msis21Frozen, Solar};
use abep_design::err::{model, DResult};
use abep_gaspath::pyops::py_format_g;
use abep_gaspath::rec::fnum;
use abep_intake::frozen::read_surface_v1;
use abep_intake::surface::{FrozenIntakeSurfaces, IntakeSurface};
use abep_provenance::read_verified;
use serde_json::{Map, Value};
use std::path::Path;

pub const STATUS: &str = "NUMERICAL_INTERPOLATION_SENSITIVITY";
pub const NOT_APPLICABLE: &str = "NOT_APPLICABLE";
pub const OUT_OF_DOMAIN: &str = "OUT_OF_DOMAIN";
pub const AXES: [&str; 4] = ["L_over_d", "phi", "alpha", "theta_deg"];
pub const FIELDS: [&str; 5] = ["eta_c", "C_D", "CR_passive", "K_back", "mass_kg"];
pub const TABLES: [&str; 2] = ["maxwell", "cll"];
/// Rounding threshold of finding B2-OF-01 (the survey's RTOL): a relative spread at or below it is rounding.
pub const ROUNDING_RTOL: f64 = 1e-12;
pub const SURVEY_REL: &str =
    "docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_TPMC_PY/finding_B2-OF-01_face_survey_v1.json";
pub const SURVEY_SHA256: &str = "4b30eaca5bbd2560426917c3c9ed11c447ef0ec4ce963e372dba4af98673e03f";
pub const SURFACE_JSON_REL: &str = "abep_sim/data/intake_surface_v1.json";
pub const SURFACE_JSON_SHA256: &str = "5b26b7fd60272537dd0e719a122cb874233c6dd777202ab164b159cc7215d425";

/// Face geometry of a surface point.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FaceGeometry {
    OutOfDomain,
    NotOnKnownFace,
    GridNode,
    GridEdge,
    FaceInterior,
}

impl FaceGeometry {
    pub fn as_str(self) -> &'static str {
        match self {
            FaceGeometry::OutOfDomain => "OUT_OF_DOMAIN",
            FaceGeometry::NotOnKnownFace => "NOT_ON_KNOWN_FACE",
            FaceGeometry::GridNode => "GRID_NODE",
            FaceGeometry::GridEdge => "GRID_EDGE",
            FaceGeometry::FaceInterior => "FACE_INTERIOR",
        }
    }
}

/// Classification of one point.
#[derive(Debug, Clone, PartialEq)]
pub struct FaceClass {
    pub geometry: FaceGeometry,
    /// known faces hit, as the survey names them ('L_over_d = 5')
    pub faces_hit: Vec<String>,
    pub free_dims: usize,
}

/// The adjacent-simplex envelope at a point: per species and field (min, max, relative spread).
#[derive(Debug, Clone, PartialEq)]
pub struct Envelope {
    pub simplices: Vec<usize>,
    /// [species][field] -> (min, max, spread)
    pub stats: Vec<[(f64, f64, f64); 5]>,
}

impl Envelope {
    pub fn max_spread(&self) -> f64 {
        self.stats.iter().flat_map(|s| s.iter().map(|x| x.2)).fold(0.0, |a: f64, b| if b > a { b } else { a })
    }
    pub fn rounding_level(&self) -> bool {
        self.stats.iter().all(|s| s.iter().all(|x| x.2 <= ROUNDING_RTOL))
    }
}

/// The loaded diagnostic: canonical grids, the known faces and the frozen surfaces.
pub struct Diagnostic {
    /// per table: per axis the canonical grid values
    pub grids: Vec<(String, [Vec<f64>; 4])>,
    /// known degenerate faces (axis index, value, survey name)
    pub faces: Vec<(usize, f64, String)>,
    pub surfaces: FrozenIntakeSurfaces,
}

fn axis_of(r: &abep_intake::frozen::SurfaceRow, a: usize) -> f64 {
    match a {
        0 => r.l_over_d,
        1 => r.phi,
        2 => r.alpha,
        _ => r.theta_deg,
    }
}

impl Diagnostic {
    pub fn load(repo: &Path) -> DResult<Self> {
        let rows = read_surface_v1(repo)?;
        let meta: Value = serde_json::from_slice(&read_verified(&repo.join(SURFACE_JSON_REL), SURFACE_JSON_SHA256)?)
            .map_err(|e| model(format!("RuntimeError: {SURFACE_JSON_REL}: {e}")))?;
        let mut grids = vec![];
        for t in TABLES {
            let mut g: [Vec<f64>; 4] = Default::default();
            for (a, ga) in g.iter_mut().enumerate() {
                let mut v: Vec<f64> = rows.iter().filter(|r| r.scattering == t).map(|r| axis_of(r, a)).collect();
                v.sort_by(|x, y| x.partial_cmp(y).expect("finite grid"));
                v.dedup();
                let json: Vec<f64> = meta["grid"][AXES[a]]
                    .as_array()
                    .ok_or_else(|| model(format!("RuntimeError: {SURFACE_JSON_REL}: grid.{}", AXES[a])))?
                    .iter()
                    .filter_map(Value::as_f64)
                    .collect();
                if v != json {
                    return Err(model(format!(
                        "RuntimeError: canonical grid of {t} axis {} {v:?} differs from {SURFACE_JSON_REL} grid {json:?}",
                        AXES[a]
                    )));
                }
                *ga = v;
            }
            grids.push((t.to_string(), g));
        }
        let survey: Value = serde_json::from_slice(&read_verified(&repo.join(SURVEY_REL), SURVEY_SHA256)?)
            .map_err(|e| model(format!("RuntimeError: {SURVEY_REL}: {e}")))?;
        let names: Vec<String> = survey["affected_faces"]
            .as_array()
            .ok_or_else(|| model(format!("RuntimeError: {SURVEY_REL}: affected_faces")))?
            .iter()
            .filter_map(|v| v.as_str().map(str::to_string))
            .collect();
        let faces = Self::check_faces(&grids, &names)?;
        let build = atmosphere(&Msis21Frozen::load(repo)?, 200.0, Solar::Label("mean".into()))?;
        let surfaces = FrozenIntakeSurfaces::load(repo, build.m_mean)?;
        Ok(Diagnostic { grids, faces, surfaces })
    }

    /// The survey's faces equal the interior grid values of every table (fail closed otherwise).
    pub fn check_faces(grids: &[(String, [Vec<f64>; 4])], names: &[String]) -> DResult<Vec<(usize, f64, String)>> {
        let mut faces = vec![];
        for n in names {
            let (ax, v) = n.split_once(" = ").ok_or_else(|| model(format!("RuntimeError: survey face {n:?}")))?;
            let a =
                AXES.iter().position(|x| *x == ax).ok_or_else(|| model(format!("RuntimeError: survey axis {ax:?}")))?;
            let val: f64 = v.parse().map_err(|_| model(format!("RuntimeError: survey face value {v:?}")))?;
            faces.push((a, val, n.clone()));
        }
        for (t, g) in grids {
            let mut interior: Vec<(usize, f64)> = vec![];
            for (a, ga) in g.iter().enumerate() {
                if ga.len() > 2 {
                    interior.extend(ga[1..ga.len() - 1].iter().map(|v| (a, *v)));
                }
            }
            let mut want: Vec<String> =
                interior.iter().map(|(a, v)| format!("{} = {}", AXES[*a], py_format_g(*v))).collect();
            let mut have: Vec<String> = faces.iter().map(|f| f.2.clone()).collect();
            want.sort();
            have.sort();
            if want != have {
                return Err(model(format!(
                    "RuntimeError: survey faces {have:?} differ from the interior grid values of {t} {want:?}"
                )));
            }
            for (a, v, n) in &faces {
                if !interior.iter().any(|(b, w)| b == a && w == v) {
                    return Err(model(format!("RuntimeError: survey face {n:?} is not an interior grid value of {t}")));
                }
            }
        }
        Ok(faces)
    }

    fn grid(&self, table: &str) -> DResult<&[Vec<f64>; 4]> {
        self.grids
            .iter()
            .find(|(t, _)| t == table)
            .map(|(_, g)| g)
            .ok_or_else(|| model(format!("ValueError: no frozen table for wall-scattering model {table:?}")))
    }

    fn surface(&self, table: &str) -> DResult<&IntakeSurface> {
        Ok(self.surfaces.get(table)?)
    }

    /// The exact-face classification (IEEE equality with the canonical grid values; no tolerance).
    pub fn classify(&self, table: &str, p: [f64; 4]) -> DResult<FaceClass> {
        let g = self.grid(table)?;
        let in_domain = p.iter().zip(g).all(|(x, ga)| x.is_finite() && ga[0] <= *x && *x <= ga[ga.len() - 1]);
        if !in_domain {
            return Ok(FaceClass { geometry: FaceGeometry::OutOfDomain, faces_hit: vec![], free_dims: 0 });
        }
        let on_grid = p.iter().zip(g).filter(|(x, ga)| ga.contains(x)).count();
        let faces_hit: Vec<String> =
            self.faces.iter().filter(|(a, v, _)| p[*a] == *v).map(|(_, _, n)| n.clone()).collect();
        let free_dims = 4 - on_grid;
        let geometry = if faces_hit.is_empty() {
            FaceGeometry::NotOnKnownFace
        } else {
            match free_dims {
                0 => FaceGeometry::GridNode,
                1 => FaceGeometry::GridEdge,
                _ => FaceGeometry::FaceInterior,
            }
        };
        Ok(FaceClass { geometry, faces_hit, free_dims })
    }

    /// The adjacent-simplex envelope (computed for any in-domain point; the diagnostic applies it to exact-face points).
    pub fn envelope(&self, table: &str, p: [f64; 4]) -> DResult<Option<Envelope>> {
        let s = self.surface(table)?;
        let cs = s.containing_simplex_rows(p[0], p[1], p[2], p[3]);
        if cs.is_empty() {
            return Ok(None);
        }
        let nsp = s.species().len();
        let mut stats = vec![[(0.0, 0.0, 0.0); 5]; nsp];
        for (sp, st) in stats.iter_mut().enumerate() {
            for (f, slot) in st.iter_mut().enumerate() {
                let vals: Vec<f64> = cs.iter().map(|(_, rows)| rows[sp][f]).collect();
                let lo = vals.iter().copied().fold(f64::INFINITY, f64::min);
                let hi = vals.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                let mut acc = 0.0;
                for v in &vals {
                    acc += v;
                }
                let mean = acc / vals.len() as f64;
                *slot = (lo, hi, (hi - lo) / mean.abs());
            }
        }
        Ok(Some(Envelope { simplices: cs.iter().map(|c| c.0).collect(), stats }))
    }

    /// The diagnostic record of one surface point.
    pub fn evaluate(&self, table: &str, p: [f64; 4]) -> DResult<Value> {
        let cls = self.classify(table, p)?;
        let s = self.surface(table)?;
        let mut m = Map::new();
        m.insert("scattering".into(), Value::String(table.to_string()));
        m.insert("point".into(), Value::Array(p.iter().map(|x| fnum(*x)).collect()));
        m.insert("face_geometry".into(), Value::String(cls.geometry.as_str().into()));
        m.insert("faces_hit".into(), Value::Array(cls.faces_hit.iter().cloned().map(Value::String).collect()));
        m.insert("free_dims".into(), Value::from(cls.free_dims));
        if cls.geometry == FaceGeometry::OutOfDomain {
            m.insert("status".into(), Value::String(OUT_OF_DOMAIN.into()));
            m.insert("authoritative".into(), Value::Null);
            m.insert("envelope".into(), Value::Null);
            m.insert(
                "envelope_reason".into(),
                Value::String("OUT_OF_DOMAIN: outside the closed range of the frozen grid (no extrapolation)".into()),
            );
            return Ok(Value::Object(m));
        }
        let auth = s.species_rows_at(p[0], p[1], p[2], p[3])?;
        m.insert("authoritative".into(), rows_value(s.species(), &auth));
        if cls.geometry == FaceGeometry::NotOnKnownFace {
            m.insert("status".into(), Value::String(NOT_APPLICABLE.into()));
            m.insert("envelope".into(), Value::Null);
            m.insert(
                "envelope_reason".into(),
                Value::String("not exactly on a known degenerate internal face (exact-face condition false)".into()),
            );
            return Ok(Value::Object(m));
        }
        m.insert("status".into(), Value::String(STATUS.into()));
        match self.envelope(table, p)? {
            None => {
                m.insert("envelope".into(), Value::Null);
                m.insert(
                    "envelope_reason".into(),
                    Value::String("MODEL_ERROR: no captured simplex contains the point".into()),
                );
            }
            Some(env) => {
                let mut e = Map::new();
                e.insert("n_simplices".into(), Value::from(env.simplices.len()));
                e.insert("simplices".into(), Value::Array(env.simplices.iter().map(|x| Value::from(*x)).collect()));
                let mut sp = Map::new();
                for (k, name) in s.species().iter().enumerate() {
                    let mut f = Map::new();
                    for (j, field) in FIELDS.iter().enumerate() {
                        let (lo, hi, spread) = env.stats[k][j];
                        let mut r = Map::new();
                        r.insert("min".into(), fnum(lo));
                        r.insert("max".into(), fnum(hi));
                        r.insert("relative_spread".into(), fnum(spread));
                        r.insert("authoritative".into(), fnum(auth[k][j]));
                        f.insert((*field).into(), Value::Object(r));
                    }
                    sp.insert(name.clone(), Value::Object(f));
                }
                e.insert("species".into(), Value::Object(sp));
                e.insert("max_relative_spread".into(), fnum(env.max_spread()));
                m.insert(
                    "sensitivity_class".into(),
                    Value::String(if env.rounding_level() { "ROUNDING_LEVEL" } else { "NON_CONFORMING" }.into()),
                );
                m.insert("envelope".into(), Value::Object(e));
            }
        }
        m.insert(
            "rule".into(),
            Value::String(
                "the authoritative frozen value governs; the envelope is reported beside it and never selects a \
                 branch, never makes a candidate robust or feasible (A9.31 sec. 6)"
                    .into(),
            ),
        );
        Ok(Value::Object(m))
    }
}

fn rows_value(species: &[String], rows: &[[f64; 5]]) -> Value {
    let mut sp = Map::new();
    for (name, r) in species.iter().zip(rows) {
        let mut f = Map::new();
        for (j, field) in FIELDS.iter().enumerate() {
            f.insert((*field).into(), fnum(r[j]));
        }
        sp.insert(name.clone(), Value::Object(f));
    }
    Value::Object(sp)
}

/// The surface scattering table and alpha of an F1 scenario id `<scattering>_a<alpha:g>`.
pub fn scenario_surface(scenario: &str) -> DResult<(String, f64)> {
    let (t, a) = scenario.split_once("_a").ok_or_else(|| model(format!("ValueError: scenario {scenario:?}")))?;
    let alpha: f64 = a.parse().map_err(|_| model(format!("ValueError: scenario alpha {a:?}")))?;
    Ok((t.to_string(), alpha))
}

/// Application to the F7 / F8 chain (prereg f7_f8_application): every surface point the given candidates would touch
/// (theta 0 in every scenario, theta 5 for the pointing node). `interpolant_used_by_chain` is false: the chain reads
/// the committed F1 records (frozen surface used only at exact grid nodes of its build state, direct TPMC elsewhere).
pub fn chain_application(diag: &Diagnostic, candidates: &[(String, f64, f64)], scenarios: &[String]) -> DResult<Value> {
    let mut points = vec![];
    let mut counts: Vec<(String, usize)> = vec![];
    let mut non_conforming = 0usize;
    for (cand, ld, phi) in candidates {
        for sc in scenarios {
            let (table, alpha) = scenario_surface(sc)?;
            for theta in [0.0, 5.0] {
                let rec = diag.evaluate(&table, [*ld, *phi, alpha, theta])?;
                let g = rec["face_geometry"].as_str().unwrap_or_default().to_string();
                match counts.iter_mut().find(|(k, _)| *k == g) {
                    Some(e) => e.1 += 1,
                    None => counts.push((g.clone(), 1)),
                }
                if rec.get("sensitivity_class").and_then(Value::as_str) == Some("NON_CONFORMING") {
                    non_conforming += 1;
                }
                let mut m = Map::new();
                m.insert("candidate".into(), Value::String(cand.clone()));
                m.insert("scenario".into(), Value::String(sc.clone()));
                m.insert("theta_deg".into(), fnum(theta));
                m.insert("record".into(), rec);
                points.push(Value::Object(m));
            }
        }
    }
    let mut out = Map::new();
    out.insert("diagnostic".into(), Value::String(STATUS.into()));
    out.insert("interpolant_used_by_chain".into(), Value::Bool(false));
    out.insert(
        "interpolant_basis".into(),
        Value::String(
            "the F7 / F8 chain consumes the committed F1 IF-A1 records and species table; intake_synthesis used the \
             frozen surface only at exact grid nodes of its build state and direct TPMC elsewhere; the interpolant is \
             never called by the chain"
                .into(),
        ),
    );
    out.insert(
        "face_geometry_counts".into(),
        Value::Object(counts.into_iter().map(|(k, n)| (k, Value::from(n))).collect()),
    );
    out.insert("n_points".into(), Value::from(points.len()));
    out.insert("n_non_conforming".into(), Value::from(non_conforming));
    out.insert("points".into(), Value::Array(points));
    Ok(Value::Object(out))
}
