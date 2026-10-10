//! F8 seeded Monte Carlo over the quantified TPMC statistics (`robust_optimizer.tpmc_monte_carlo`, `perturbed`,
//! `record_se_index`, `_state_eval`). The perturbation draws are the design / UQ sampling stream (A9.29 sec. 7,
//! EXACT_STREAM): one numpy `default_rng(stable_seed("tpmc", candidate, scenario))` generator per (candidate,
//! scenario), reproduced bit for bit by abep-rng. No TPMC particle is traced here (the committed F1 records and their
//! binomial / replicate SEs are the input); the TPMC kernel keeps its own STATISTICAL contract.

use crate::robust::Survivor;
use abep_design::err::{model, DResult, DesignError};
use abep_design::inputs::UpstreamInputs;
use abep_design::optimizer::plenum;
use abep_gaspath::plenum_feed::{
    intake_side, reasons_from_bits, steady_sweep, CompressorPlant, FilterCase, IntakeState, Plenum, Sp3,
};
use abep_rng::Generator;
use serde_json::{Map, Value};
use std::collections::{BTreeMap, BTreeSet, HashMap};

pub const N_MC_DEFAULT: usize = 100;
pub const SEED_BASE: i64 = 20261001;
pub const SE_FLOOR: f64 = 1e-30;

/// `robust_optimizer.stable_seed(*parts)` = `intake_synthesis.stable_seed(*parts, base=SEED_BASE)`.
pub fn stable_seed(parts: &[&str]) -> i64 {
    abep_rng::stable_seed(parts, SEED_BASE)
}

/// Key of the SE index: (L/d, phi, scenario, state), floats as bit patterns.
pub type SeKey = (u64, u64, String, String);

/// `record_se_index(f1)`: per species (mdot_fwd_se per m^2, p_passive_se).
pub fn record_se_index(inp: &UpstreamInputs) -> DResult<HashMap<SeKey, [(f64, f64); 3]>> {
    let mut out = HashMap::new();
    for r in &inp.f1.records {
        let rest = r.candidate.replace("unit_area_Ld", "");
        let (ld, phi) = rest
            .split_once("_phi")
            .ok_or_else(|| model(format!("ValueError: unrecognised unit-area candidate {:?}", r.candidate)))?;
        let p = |s: &str| s.parse::<f64>().map_err(|_| model(format!("ValueError: could not convert {s:?}")));
        let (ld, phi) = (p(ld)?, p(phi)?);
        let s = &r.species;
        out.insert(
            (ld.to_bits(), phi.to_bits(), r.scenario.clone(), r.state.clone()),
            [(s[0][1], s[0][3]), (s[1][1], s[1][3]), (s[2][1], s[2][3])],
        );
    }
    Ok(out)
}

fn py_max(a: f64, b: f64) -> f64 {
    // Python max(a, b): b only when b > a
    if b > a {
        b
    } else {
        a
    }
}

/// `perturbed(rec, area, se, z_m, z_p)`: mdot_fwd_s + z SE A and p_passive_s + z SE, clipped at a tiny positive floor.
pub fn perturbed(rec: &IntakeState, area: f64, se: &[(f64, f64); 3], z_m: [f64; 3], z_p: [f64; 3]) -> IntakeState {
    let mut out = rec.clone();
    for i in 0..3 {
        out.mdot_fwd_kgps[i] = py_max(rec.mdot_fwd_kgps[i] + z_m[i] * se[i].0 * area, SE_FLOOR);
        out.p_passive_pa[i] = py_max(rec.p_passive_pa[i] + z_p[i] * se[i].1, SE_FLOOR);
    }
    out.source = format!("{} [TPMC-SE draw]", rec.source);
    out
}

/// The draws of one (candidate, scenario): the perturbed intake states (sample-major, state-minor) and the maximum
/// intake drag over the states per sample.
#[derive(Debug, Clone)]
pub struct Draw {
    pub states: Vec<IntakeState>,
    pub drag_max: Vec<f64>,
    /// the raw standard-normal stream (n x n_states x 3 x 3, C order)
    pub z: Vec<f64>,
}

/// One generator per (candidate, scenario): `default_rng(stable_seed("tpmc", cand, sc)).standard_normal((n, nS, 3, 3))`.
pub fn draw(
    inp: &UpstreamInputs,
    se_idx: &HashMap<SeKey, [(f64, f64); 3]>,
    cand: &str,
    sc: &str,
    n: usize,
) -> DResult<Draw> {
    let (a, ld, phi) = *inp.geometry.get(cand).ok_or_else(|| DesignError::new("KeyError", format!("'{cand}'")))?;
    let seed = stable_seed(&["tpmc", cand, sc]);
    let mut rng = Generator::default_rng(seed as u128);
    let ns = inp.states.len();
    let z = rng.standard_normal_fill(n * ns * 9);
    let mut states = Vec::with_capacity(n * ns);
    let mut drag_max = vec![0.0; n];
    for i in 0..n {
        let mut dm = f64::NAN;
        for (j, st) in inp.states.iter().enumerate() {
            let rec = inp.record(cand, sc, st)?;
            let se = se_idx
                .get(&(ld.to_bits(), phi.to_bits(), sc.to_string(), st.clone()))
                .ok_or_else(|| DesignError::new("KeyError", format!("({ld}, {phi}, {sc:?}, {st:?})")))?;
            let b = (i * ns + j) * 9;
            states.push(perturbed(rec, a, se, [z[b], z[b + 1], z[b + 2]], [z[b + 3], z[b + 4], z[b + 5]]));
            let (d0, dse) = inp.drag_per_area(sc, ld, phi, st)?;
            let d = a * (d0 + z[b + 6] * dse);
            // ndarray.max(axis=1): NaN propagates
            dm = if j == 0 {
                d
            } else if dm.is_nan() || d.is_nan() {
                f64::NAN
            } else if d > dm {
                d
            } else {
                dm
            };
        }
        drag_max[i] = dm;
    }
    Ok(Draw { states, drag_max, z })
}

/// `_state_eval` result: per sample (group of every F1 state).
#[derive(Debug, Clone)]
pub struct StateEval {
    /// [sample][state] reason bits
    pub bits: Vec<Vec<i64>>,
    pub all_ok: Vec<bool>,
    pub mdot_min: Vec<f64>,
    pub p_el_max: Vec<f64>,
    pub m_comp_max: Vec<f64>,
    pub deadhead_margin: Vec<f64>,
}

fn nan_red(v: impl Iterator<Item = f64>, min: bool) -> f64 {
    let mut acc = f64::NAN;
    for x in v {
        if x.is_nan() {
            continue;
        }
        if acc.is_nan() || (min && x < acc) || (!min && x > acc) {
            acc = x;
        }
    }
    acc
}

/// `_state_eval(states, filt, plant, pl, P, side)`: gated steady points of whole groups of the F1 states at one set
/// pressure.
pub fn state_eval(
    inp: &UpstreamInputs,
    states: &[IntakeState],
    plant: &CompressorPlant,
    pl: &Plenum,
    p: f64,
    side: &(Vec<Sp3>, Vec<Sp3>),
) -> DResult<StateEval> {
    let f1ok: Vec<bool> = states.iter().map(|r| r.f1_status == "FEASIBLE_AT_STATE").collect();
    let sw = steady_sweep(side, plant, pl, &inp.materials, &[p], Some(&f1ok))?;
    let nst = inp.states.len();
    if !states.len().is_multiple_of(nst) {
        return Err(DesignError::new(
            "OptimizerError",
            format!("{} intake states are not whole groups of the {nst} F1 states", states.len()),
        ));
    }
    let n = states.len() / nst;
    let mut ev = StateEval {
        bits: vec![],
        all_ok: vec![],
        mdot_min: vec![],
        p_el_max: vec![],
        m_comp_max: vec![],
        deadhead_margin: vec![],
    };
    for i in 0..n {
        let rows = i * nst..(i + 1) * nst;
        let bits: Vec<i64> = rows.clone().map(|r| sw.bits[r]).collect();
        let ok = bits.iter().all(|b| *b == 0);
        let pick = |a: &Vec<f64>, min: bool| if ok { nan_red(rows.clone().map(|r| a[r]), min) } else { f64::NAN };
        ev.mdot_min.push(pick(&sw.mdot_total_kgps, true));
        ev.p_el_max.push(pick(&sw.p_el_w, false));
        ev.m_comp_max.push(pick(&sw.m_compressor_kg, false));
        ev.deadhead_margin.push(if ok {
            nan_red(rows.clone().map(|r| (sw.p_deadhead_pa[r] - p) / p), true)
        } else {
            f64::NAN
        });
        ev.all_ok.push(ok);
        ev.bits.push(bits);
    }
    Ok(ev)
}

/// `numpy.percentile(a, q)` (method 'linear', numpy 2.4.4 `_quantile` / `_lerp`): NaN when any value is NaN.
pub fn np_percentile(a: &[f64], q: f64) -> f64 {
    if a.is_empty() || a.iter().any(|x| x.is_nan()) {
        return f64::NAN;
    }
    let mut v = a.to_vec();
    v.sort_by(|x, y| x.partial_cmp(y).expect("no NaN"));
    let n = v.len();
    let vi = (n as f64 - 1.0) * (q / 100.0);
    if vi >= (n - 1) as f64 {
        return v[n - 1];
    }
    if vi < 0.0 {
        return v[0];
    }
    let prev = vi.floor();
    let i = prev as usize;
    let (lo, hi) = (v[i], v[i + 1]);
    let t = vi - prev;
    let diff = hi - lo;
    if t >= 0.5 {
        hi - diff * (1.0 - t)
    } else {
        lo + diff * t
    }
}

/// MC record of one (candidate, filter, compressor, P_set) in one scenario.
#[derive(Debug, Clone, PartialEq)]
pub struct McRecord {
    pub n: usize,
    pub k_feasible: usize,
    pub p_feasible: f64,
    pub mdot_delivered_min_p05_kgps: Option<f64>,
    pub mdot_delivered_min_p50_kgps: Option<f64>,
    pub p_compressor_el_max_p95_w: Option<f64>,
    pub deadhead_margin_p05: Option<f64>,
    pub drag_intake_max_p95_n: f64,
    pub reasons_in_draws: Vec<String>,
}

impl McRecord {
    pub fn to_value(&self) -> Value {
        let o = |x: Option<f64>| x.map(abep_gaspath::rec::fnum).unwrap_or(Value::Null);
        let mut m = Map::new();
        m.insert("n".into(), Value::from(self.n));
        m.insert("k_feasible".into(), Value::from(self.k_feasible));
        m.insert("P_feasible".into(), abep_gaspath::rec::fnum(self.p_feasible));
        m.insert("mdot_delivered_min_p05_kgps".into(), o(self.mdot_delivered_min_p05_kgps));
        m.insert("mdot_delivered_min_p50_kgps".into(), o(self.mdot_delivered_min_p50_kgps));
        m.insert("P_compressor_el_max_p95_W".into(), o(self.p_compressor_el_max_p95_w));
        m.insert("deadhead_margin_p05".into(), o(self.deadhead_margin_p05));
        m.insert("drag_intake_max_p95_N".into(), abep_gaspath::rec::fnum(self.drag_intake_max_p95_n));
        m.insert(
            "reasons_in_draws".into(),
            Value::Array(self.reasons_in_draws.iter().cloned().map(Value::String).collect()),
        );
        Value::Object(m)
    }
}

/// MC key: (candidate, filter, compressor, P_set bits).
pub type McKey = (String, String, String, u64);

/// `tpmc_monte_carlo(inp, cands, scenarios, n, wall)`. Returns, per (candidate, filter, compressor, P_set), the
/// per-scenario records in scenario order.
pub fn tpmc_monte_carlo(
    inp: &UpstreamInputs,
    cands: &[Survivor],
    scenarios: &[String],
    n: usize,
    wall: &str,
) -> DResult<BTreeMap<McKey, Vec<(String, McRecord)>>> {
    let se_idx = record_se_index(inp)?;
    // groups: (filter, compressor) -> candidate -> set of P (sorted iteration below)
    let mut groups: BTreeMap<(String, String), BTreeMap<String, BTreeSet<u64>>> = BTreeMap::new();
    for c in cands {
        groups
            .entry((c.filter.clone(), c.compressor.clone()))
            .or_default()
            .entry(c.candidate.clone())
            .or_default()
            .insert(c.p_set_pa.to_bits());
    }
    let mut draws: HashMap<(String, String), Draw> = HashMap::new();
    let mut sides: HashMap<(String, String, String), (Vec<Sp3>, Vec<Sp3>)> = HashMap::new();
    let mut res: BTreeMap<McKey, Vec<(String, McRecord)>> = BTreeMap::new();
    for sc in scenarios {
        for ((filt, comp), cdict) in &groups {
            let plant = inp.plant(comp)?;
            let pl = plenum(inp, 1e-2, wall)?;
            let fc: &FilterCase = inp.filter(filt)?;
            for (cand, ps) in cdict {
                let dk = (cand.clone(), sc.clone());
                if !draws.contains_key(&dk) {
                    draws.insert(dk.clone(), draw(inp, &se_idx, cand, sc, n)?);
                }
                let d = &draws[&dk];
                let sk = (cand.clone(), sc.clone(), filt.clone());
                if !sides.contains_key(&sk) {
                    sides.insert(sk.clone(), intake_side(&d.states, fc, 1.0)?);
                }
                let side = &sides[&sk];
                let mut pv: Vec<f64> = ps.iter().map(|b| f64::from_bits(*b)).collect();
                pv.sort_by(|a, b| a.partial_cmp(b).expect("finite P"));
                for p in pv {
                    let ev = state_eval(inp, &d.states, plant, &pl, p, side)?;
                    let k = ev.all_ok.iter().filter(|x| **x).count();
                    let pct = |a: &[f64], q: f64| -> Option<f64> {
                        let s: Vec<f64> = a.iter().zip(&ev.all_ok).filter(|(_, ok)| **ok).map(|(x, _)| *x).collect();
                        if s.is_empty() {
                            None
                        } else {
                            Some(np_percentile(&s, q))
                        }
                    };
                    let mut reasons: BTreeSet<&str> = BTreeSet::new();
                    for row in &ev.bits {
                        for b in row {
                            reasons.extend(reasons_from_bits(*b));
                        }
                    }
                    let rec = McRecord {
                        n,
                        k_feasible: k,
                        p_feasible: k as f64 / n as f64,
                        mdot_delivered_min_p05_kgps: pct(&ev.mdot_min, 5.0),
                        mdot_delivered_min_p50_kgps: pct(&ev.mdot_min, 50.0),
                        p_compressor_el_max_p95_w: pct(&ev.p_el_max, 95.0),
                        deadhead_margin_p05: pct(&ev.deadhead_margin, 5.0),
                        drag_intake_max_p95_n: np_percentile(&d.drag_max, 95.0),
                        reasons_in_draws: reasons.into_iter().map(str::to_string).collect(),
                    };
                    res.entry((cand.clone(), filt.clone(), comp.clone(), p.to_bits()))
                        .or_default()
                        .push((sc.clone(), rec));
                }
            }
        }
    }
    Ok(res)
}

/// Minimum P_feasible over the scenario records of one MC entry (`min(v["P_feasible"] for v in m.values())`).
pub fn p_feasible_min(recs: &[(String, McRecord)]) -> Option<f64> {
    let mut acc: Option<f64> = None;
    for (_, r) in recs {
        acc = Some(match acc {
            None => r.p_feasible,
            Some(a) => {
                if r.p_feasible < a {
                    r.p_feasible
                } else {
                    a
                }
            }
        });
    }
    acc
}
