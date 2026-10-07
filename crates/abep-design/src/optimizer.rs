//! F7 upstream sub-problem (`abep_sim/design/architecture_optimizer.py`): every upstream design vector (intake
//! candidate x compressor x plenum volume x set pressure) of one (surface scenario, filter case, wall case) context is
//! evaluated through the admitted gas-path steady sweep (abep-gaspath `steady_sweep`, F4 fail-closed gates at every
//! F1 state), reduced over the states, and compared by weak Pareto dominance. Nothing here is a selection, a winner or
//! a PASS: every number is PARAMETRIC_SENSITIVITY (uncited code-default compressor coefficients, parametric filter /
//! leak / chain temperature), and the system objectives stay NOT_EVALUATED.

use crate::err::{opt_err, DResult, DesignError};
use crate::inputs::UpstreamInputs;
use abep_gaspath::plenum_feed::{
    intake_side, steady_sweep, CompressorPlant, FilterCase, Plenum, RES_DEFAULT_LEAK_AREA_M2, T_CHAIN_K,
};
use abep_gaspath::pyops::py_format_g;
use abep_gaspath::upstream as u13;
use abep_types::pyjson::py_repr_str;
use serde_json::Value;
use std::f64::consts::PI;

pub const SPECIES: [&str; 3] = ["O", "N2", "O2"];
pub const UPSTREAM_TARGETS_PA: [f64; 6] = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1];
pub const VOLUMES_M3: [f64; 3] = [1e-3, 1e-2, 1e-1];
pub const WALL_CASES: [&str; 2] = ["WALL-G0", "WALL-TI64-DB"];
pub const LABEL_PARAMETRIC: &str = "PARAMETRIC_SENSITIVITY";
pub const FC00_ROLE: &str = "REFERENCE_BOUND_FC00_NOT_ADMISSIBLE";
pub const ARCHITECTURE_CONTEXT: &str = "ARCHITECTURE_CONTEXT";

/// `UPSTREAM_OBJECTIVES`: (key, sense).
pub const UPSTREAM_OBJECTIVES: [(&str, &str); 6] = [
    ("mdot_delivered_min_kgps", "max"),
    ("drag_intake_max_N", "min"),
    ("P_compressor_el_max_W", "min"),
    ("m_compressor_max_kg", "min"),
    ("intake_wall_area_m2", "min"),
    ("plenum_V_m3", "min"),
];
pub const REPORTED_CONSTRAINT_COLUMNS: [&str; 1] = ["ripple_transfer_shaft"];
pub const SYSTEM_NOT_EVALUATED_CODES: [&str; 6] =
    ["T_minus_D", "P_bus", "m_wet", "Q_reject", "I_e_margin", "life_material"];

pub fn obj_keys() -> Vec<&'static str> {
    UPSTREAM_OBJECTIVES.iter().map(|o| o.0).collect()
}

pub fn obj_sense(key: &str) -> Option<&'static str> {
    UPSTREAM_OBJECTIVES.iter().find(|o| o.0 == key).map(|o| o.1)
}

/// The column arrays of a context, in the reference key order of `upstream_context`'s `arrays`.
pub const ARRAY_KEYS: [&str; 16] = [
    "mdot_delivered_min_kgps",
    "P_compressor_el_max_W",
    "m_compressor_max_kg",
    "ripple_transfer_shaft",
    "xO_flow_min",
    "xO_flow_max",
    "a_eq_design_m2",
    "deadhead_margin_min",
    "kn_upper_min",
    "T_comp_max_K",
    "mdot_delivered_design_kgps",
    "drag_intake_max_N",
    "drag_intake_max_se_N",
    "mdot_captured_min_kgps",
    "intake_wall_area_m2",
    "plenum_V_m3",
];

/// `wall_gamma(wall)`: 0 for WALL-G0, the Ti-6Al-4V DB prior gamma_O(T_chain) for WALL-TI64-DB.
pub fn wall_gamma(inp: &UpstreamInputs, wall: &str) -> DResult<f64> {
    match wall {
        "WALL-G0" => Ok(0.0),
        "WALL-TI64-DB" => Ok(inp.materials.get("Ti6Al4V")?.gamma_o(T_CHAIN_K)?),
        _ => Err(opt_err(format!("unknown wall case {}", py_repr_str(wall)))),
    }
}

/// `plenum(V, wall)`.
pub fn plenum(inp: &UpstreamInputs, v: f64, wall: &str) -> DResult<Plenum> {
    Ok(Plenum::new(v, wall_gamma(inp, wall)?, wall, RES_DEFAULT_LEAK_AREA_M2, T_CHAIN_K)?)
}

/// `design_id(cand, filt, comp, V, P)`.
pub fn design_id(cand: &str, filt: &str, comp: &str, v: f64, p: f64) -> String {
    format!("{cand}|{filt}|{comp}|V{}|P{}", py_format_g(v), py_format_g(p))
}

/// `context_id(scenario, filt, wall, P)`.
pub fn context_id(scenario: &str, filt: &str, wall: &str, p: f64) -> String {
    format!("{scenario}|{filt}|{wall}|P{}", py_format_g(p))
}

/// `context_role(fc)` (A9.13 S6.5).
pub fn context_role(fc: &FilterCase) -> &'static str {
    if fc.reference_bound_only() {
        FC00_ROLE
    } else {
        ARCHITECTURE_CONTEXT
    }
}

/// `higher_pressure_branch(targets)`: the S6.11 primary direction, NOT_EVALUATED_OUT_OF_DOMAIN until S6.8 closes.
pub fn higher_pressure_branch(targets: &[f64]) -> DResult<Vec<Value>> {
    targets.iter().map(|t| Ok(u13::classify_pressure_target(*t)?)).collect()
}

/// `ripple_transfer_arrays(side_e, plant, pl, a_eq)` elementwise: least attenuated species of
/// 1 / sqrt(1 + (2 pi f tau_s)^2), tau_s = V / (k_s + G_s + leak_s (+ k_rec for O)).
pub fn ripple_transfer(side_e: [f64; 3], plant: &CompressorPlant, pl: &Plenum, a_eq: f64) -> DResult<f64> {
    let ch = plant.characteristic()?;
    let cl = plant.leak_m3_s();
    let mut out = f64::NAN;
    for (i, s) in SPECIES.iter().enumerate() {
        let (a, b) = ch[i];
        let alpha = a / b + cl;
        let beta = 1.0 / b + cl;
        let e = side_e[i];
        let k = e * beta / (e + alpha);
        let g = pl.feed_c(s)? * a_eq + pl.leak_m3_s(s)? + if *s == "O" { pl.k_rec_m3_s()? } else { 0.0 };
        let tau = pl.volume_m3 / (k + g);
        let w = 2.0 * PI * plant.shaft_hz() * tau;
        let tr = 1.0 / (1.0 + w * w).sqrt();
        out = if i == 0 { tr } else { np_maximum(out, tr) };
    }
    Ok(out)
}

/// numpy `maximum` (NaN propagates).
pub fn np_maximum(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if a >= b {
        a
    } else {
        b
    }
}

/// One evaluated (scenario, filter, wall) context (`upstream_context` result). Arrays are flattened row-major over
/// (candidate, compressor, volume, target).
#[derive(Debug, Clone)]
pub struct Context {
    pub scenario: String,
    pub filter: String,
    pub wall: String,
    pub candidates: Vec<String>,
    pub compressors: Vec<String>,
    pub volumes: Vec<f64>,
    pub targets: Vec<f64>,
    pub bits: Vec<i64>,
    /// arrays in [`ARRAY_KEYS`] order
    pub arrays: Vec<Vec<f64>>,
    pub context_role: &'static str,
    pub design_direction: Vec<String>,
}

impl Context {
    pub fn shape(&self) -> [usize; 4] {
        [self.candidates.len(), self.compressors.len(), self.volumes.len(), self.targets.len()]
    }
    pub fn index(&self, ci: usize, ki: usize, vi: usize, ti: usize) -> usize {
        let [_, nk, nv, nt] = self.shape();
        ((ci * nk + ki) * nv + vi) * nt + ti
    }
    pub fn feasible(&self, g: usize) -> bool {
        self.bits[g] == 0
    }
    pub fn array(&self, key: &str) -> Option<&[f64]> {
        ARRAY_KEYS.iter().position(|k| *k == key).map(|i| self.arrays[i].as_slice())
    }
}

fn nan_reduce(vals: impl Iterator<Item = f64>, min: bool) -> f64 {
    // np.nanmin / np.nanmax over a row (all-NaN -> NaN)
    let mut acc = f64::NAN;
    for v in vals {
        if v.is_nan() {
            continue;
        }
        if acc.is_nan() || (min && v < acc) || (!min && v > acc) {
            acc = v;
        }
    }
    acc
}

/// `upstream_context(inp, scenario, filt, wall, volumes, targets, candidates, compressors)`.
pub fn upstream_context(
    inp: &UpstreamInputs,
    scenario: &str,
    filt: &str,
    wall: &str,
    volumes: &[f64],
    targets: &[f64],
    candidates: Option<&[String]>,
    compressors: Option<&[String]>,
) -> DResult<Context> {
    let cands: Vec<String> = match candidates {
        Some(c) if !c.is_empty() => c.to_vec(),
        _ => inp.candidates.clone(),
    };
    let comps: Vec<String> = match compressors {
        Some(c) if !c.is_empty() => c.to_vec(),
        _ => inp.compressor_ids.clone(),
    };
    if !inp.scenarios.iter().any(|s| s == scenario) {
        return Err(opt_err(format!("unknown scenario {}", py_repr_str(scenario))));
    }
    let fc = inp.filters.get(filt).ok_or_else(|| DesignError::new("KeyError", py_repr_str(filt)))?;
    let states = &inp.states;
    let mut recs = Vec::with_capacity(cands.len() * states.len());
    for c in &cands {
        for st in states {
            recs.push(inp.record(c, scenario, st)?.clone());
        }
    }
    let side = intake_side(&recs, fc, 1.0)?;
    let f1ok: Vec<bool> = recs.iter().map(|r| r.f1_status == "FEASIBLE_AT_STATE").collect();
    let (nc, ns, nt, nv, nk) = (cands.len(), states.len(), targets.len(), volumes.len(), comps.len());
    let gam = wall_gamma(inp, wall)?;
    let n = nc * nk * nv * nt;
    let mut arrays: Vec<Vec<f64>> = (0..ARRAY_KEYS.len()).map(|_| vec![f64::NAN; n]).collect();
    let mut bits_all = vec![0i64; n];
    let d_idx = states
        .iter()
        .position(|s| s == abep_mission::intake_drag::DESIGN_CASE_STATE_ID)
        .ok_or_else(|| opt_err("design-case state missing"))?;
    let idx = |ci: usize, ki: usize, vi: usize, ti: usize| ((ci * nk + ki) * nv + vi) * nt + ti;
    for (ki, comp) in comps.iter().enumerate() {
        let plant = inp.plant(comp)?;
        let mut cache = None;
        for (vi, &v) in volumes.iter().enumerate() {
            let pl = plenum(inp, v, wall)?;
            if cache.is_none() || gam > 0.0 {
                cache = Some(steady_sweep(&side, plant, &pl, &inp.materials, targets, Some(&f1ok))?);
            }
            let sw = cache.as_ref().expect("set");
            for ci in 0..nc {
                for (ti, &tg) in targets.iter().enumerate() {
                    let row = |si: usize| (ci * ns + si) * nt + ti;
                    let mut or = 0i64;
                    let mut all_ok = true;
                    for si in 0..ns {
                        let b = sw.bits[row(si)];
                        or |= b;
                        all_ok &= b == 0;
                    }
                    let g = idx(ci, ki, vi, ti);
                    bits_all[g] = or;
                    if !all_ok {
                        continue;
                    }
                    let col = |a: &Vec<f64>, min: bool| nan_reduce((0..ns).map(|si| a[row(si)]), min);
                    arrays[0][g] = col(&sw.mdot_total_kgps, true);
                    arrays[1][g] = col(&sw.p_el_w, false);
                    arrays[2][g] = col(&sw.m_compressor_kg, false);
                    arrays[9][g] = col(&sw.t_comp_k, false);
                    arrays[4][g] = col(&sw.x_s_flow_mole[0], true);
                    arrays[5][g] = col(&sw.x_s_flow_mole[0], false);
                    arrays[7][g] = nan_reduce((0..ns).map(|si| (sw.p_deadhead_pa[row(si)] - tg) / tg), true);
                    arrays[8][g] = col(&sw.kn_upper, true);
                    let a_d = sw.a_eq_m2[row(d_idx)];
                    arrays[6][g] = a_d;
                    arrays[10][g] = sw.mdot_total_kgps[row(d_idx)];
                    let r = ci * ns + d_idx;
                    arrays[3][g] = ripple_transfer(side.1[r], plant, &pl, a_d)?;
                }
            }
        }
    }
    // per-candidate quantities (independent of compressor / plenum)
    for (ci, c) in cands.iter().enumerate() {
        let (a, ld, phi) = *inp.geometry.get(c).ok_or_else(|| DesignError::new("KeyError", py_repr_str(c)))?;
        let mut j = 0usize;
        let mut best = f64::NAN;
        let mut dd = Vec::with_capacity(ns);
        for (si, st) in states.iter().enumerate() {
            let x = inp.drag_per_area(scenario, ld, phi, st)?;
            // np.argmax: first maximum, NaN counts as maximal
            if si == 0 || (!best.is_nan() && (x.0 > best || x.0.is_nan())) {
                best = x.0;
                j = si;
            }
            dd.push(x);
        }
        let (drag, drag_se) = (a * dd[j].0, a * dd[j].1);
        let mut capt = f64::NAN;
        for (si, st) in states.iter().enumerate() {
            let m = inp.record(c, scenario, st)?.mdot_fwd_kgps;
            let s = 0.0 + m[0] + m[1] + m[2];
            if si == 0 || s < capt {
                capt = s;
            }
        }
        let wall_area = 2.0 * phi * a * ld;
        for ki in 0..nk {
            for (vi, &v) in volumes.iter().enumerate() {
                for ti in 0..nt {
                    let g = idx(ci, ki, vi, ti);
                    if bits_all[g] != 0 {
                        continue;
                    }
                    arrays[11][g] = drag;
                    arrays[12][g] = drag_se;
                    arrays[13][g] = capt;
                    arrays[14][g] = wall_area;
                    arrays[15][g] = v;
                }
            }
        }
    }
    let mut dirs = vec![];
    for t in targets {
        let r = u13::classify_pressure_target(*t)?;
        dirs.push(r["design_direction"].as_str().unwrap_or_default().to_string());
    }
    Ok(Context {
        scenario: scenario.to_string(),
        filter: filt.to_string(),
        wall: wall.to_string(),
        candidates: cands,
        compressors: comps,
        volumes: volumes.to_vec(),
        targets: targets.to_vec(),
        bits: bits_all,
        arrays,
        context_role: context_role(fc),
        design_direction: dirs,
    })
}

/// `pareto_mask(F, senses)`: non-dominated rows under weak dominance ('max' objectives negated); identical rows are
/// all kept; a row with any non-finite value is never non-dominated (fail closed). Rows are given row-major.
pub fn pareto_mask(f: &[Vec<f64>], senses: &[&str]) -> DResult<Vec<bool>> {
    let k = senses.len();
    if f.iter().any(|r| r.len() != k) {
        return Err(opt_err("objective matrix shape"));
    }
    let g: Vec<Vec<f64>> =
        f.iter().map(|r| r.iter().zip(senses).map(|(x, s)| if *s == "max" { -*x } else { *x }).collect()).collect();
    let finite: Vec<bool> = g.iter().map(|r| r.iter().all(|x| x.is_finite())).collect();
    let idx_f: Vec<usize> = (0..g.len()).filter(|i| finite[*i]).collect();
    let mut keep = finite.clone();
    for &b in &idx_f {
        let blk = &g[b];
        let dominated = idx_f.iter().any(|&h| {
            let hr = &g[h];
            hr.iter().zip(blk).all(|(x, y)| x <= y) && hr.iter().zip(blk).any(|(x, y)| x < y)
        });
        keep[b] = !dominated;
    }
    Ok(keep)
}

/// `nondominated_layers(F, senses)`: layer 1 = Pareto set, layer 2 = Pareto set of the rest, ...
pub fn nondominated_layers(f: &[Vec<f64>], senses: &[&str]) -> DResult<Vec<usize>> {
    let mut layer = vec![0usize; f.len()];
    let mut rest: Vec<usize> = (0..f.len()).collect();
    let mut k = 0;
    while !rest.is_empty() {
        k += 1;
        let sub: Vec<Vec<f64>> = rest.iter().map(|i| f[*i].clone()).collect();
        let m = pareto_mask(&sub, senses)?;
        if !m.iter().any(|x| *x) {
            return Err(opt_err("non-finite objective in a ranked record"));
        }
        let mut next = vec![];
        for (j, &i) in rest.iter().enumerate() {
            if m[j] {
                layer[i] = k;
            } else {
                next.push(i);
            }
        }
        rest = next;
    }
    Ok(layer)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pareto_mask_weak_dominance_ties_and_non_finite() {
        let f = vec![vec![1.0, 1.0], vec![1.0, 1.0], vec![2.0, 0.5], vec![2.0, 2.0], vec![f64::NAN, 0.0]];
        // first objective maximised, second minimised
        assert_eq!(pareto_mask(&f, &["max", "min"]).unwrap(), vec![false, false, true, false, false]);
        assert_eq!(pareto_mask(&f[..2], &["min", "min"]).unwrap(), vec![true, true]);
        assert!(pareto_mask(&[vec![1.0]], &["min", "min"]).is_err());
    }

    #[test]
    fn layers_and_refusal() {
        let f = vec![vec![1.0], vec![2.0], vec![3.0], vec![1.0]];
        assert_eq!(nondominated_layers(&f, &["min"]).unwrap(), vec![1, 2, 3, 1]);
        assert_eq!(nondominated_layers(&[vec![f64::NAN]], &["min"]).unwrap_err().class, "OptimizerError");
    }

    #[test]
    fn ids_use_python_g_format() {
        assert_eq!(design_id("A1_Ld10_phi0.9", "F", "C", 1e-3, 0.02), "A1_Ld10_phi0.9|F|C|V0.001|P0.02");
        assert_eq!(context_id("cll_a0.2", "F", "WALL-G0", 0.1), "cll_a0.2|F|WALL-G0|P0.1");
    }
}
