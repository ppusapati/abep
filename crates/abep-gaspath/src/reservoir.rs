//! Species-resolved reservoir / feed network with wall chemistry (`abep_sim/reservoir.py`; contract
//! PARITY-C-ABEP_SIM_DESIGN_PLENUM_FEED_PY-V1).
//!
//! dm_s/dt = mdot_in,s - n_s C_s m_s + R_s with molecular-flow conductances C = K A cbar / 4 and the mass-conserving
//! wall recombination R_O = -gamma(T) (n_O cbar_O / 4) A_w m_O, R_O2 = +same. Steady state by damped fixed point (G-04:
//! the iteration cap is MODEL_NOT_CONVERGED), orifice sizing by geometric bisection (G-05: a bracket end is not
//! convergence), start-up transient by explicit integration.

use crate::error::{key_error, PyResult};
use crate::materials::MaterialsView;
use crate::pyops::{self, py_max, py_min};
use crate::rec::{fnum, Obj};
use abep_types::constants::{species_mass, K_B};
use abep_types::EvalStatus;
use serde_json::{Map, Value};
use std::f64::consts::PI;

pub const SS_MAX_ITER: usize = 200;
pub const SS_RTOL: f64 = 1e-6;
pub const ORIFICE_BRACKET_M2: (f64, f64) = (1e-8, 3e-2);
pub const ORIFICE_BISECTION_STEPS: usize = 60;
pub const ORIFICE_P_RTOL: f64 = 1e-6;
/// Reservoir species order of the reference.
pub const RES_SPECIES: [&str; 3] = ["O", "O2", "N2"];

pub fn solver_eval_status(converged: bool) -> EvalStatus {
    if converged {
        EvalStatus::Evaluated
    } else {
        EvalStatus::ModelError
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Reservoir {
    pub volume_m3: f64,
    pub wall_area_m2: f64,
    pub wall_material: String,
    pub t_k: f64,
    pub anode_orifice_area_m2: f64,
    pub anode_orifice_k: f64,
    pub leak_area_m2: f64,
    pub upstream_collisions: f64,
    pub upstream_material: String,
}

impl Default for Reservoir {
    fn default() -> Self {
        Reservoir {
            volume_m3: 2.0e-3,
            wall_area_m2: 0.12,
            wall_material: "Ti6Al4V".into(),
            t_k: 350.0,
            anode_orifice_area_m2: 8.0e-6,
            anode_orifice_k: 0.6,
            leak_area_m2: 5.0e-8,
            upstream_collisions: 60.0,
            upstream_material: "Ti6Al4V".into(),
        }
    }
}

fn mass(s: &str) -> PyResult<f64> {
    species_mass(s).map_err(|_| key_error(s))
}

/// Ordered (species -> value) map.
pub type SpMap = Vec<(String, f64)>;

fn get(m: &SpMap, k: &str) -> Option<f64> {
    m.iter().find(|(s, _)| s == k).map(|(_, v)| *v)
}

impl Reservoir {
    pub fn cbar(&self, s: &str) -> PyResult<f64> {
        pyops::sqrt(pyops::div(8.0 * K_B * self.t_k, PI * mass(s)?)?)
    }

    /// Molecular-flow orifice conductance [m^3/s] = K A cbar / 4.
    pub fn conductance(&self, s: &str, area: f64, k: f64) -> PyResult<f64> {
        Ok(k * area * self.cbar(s)? / 4.0)
    }

    /// Damped fixed-point steady state (G-04 convergence reported explicitly).
    pub fn steady_state(&self, mats: &MaterialsView, mdot_in: &SpMap) -> PyResult<Map<String, Value>> {
        let g_up = mats.get(&self.upstream_material)?.gamma_o(self.t_k)?;
        let surv_up = pyops::pow(1.0 - g_up, self.upstream_collisions)?;
        let mut m_in: SpMap = mdot_in.clone();
        let o_in = get(mdot_in, "O").unwrap_or(0.0);
        let lost = o_in * (1.0 - surv_up);
        set(&mut m_in, "O", o_in * surv_up);
        let o2 = get(mdot_in, "O2").unwrap_or(0.0) + lost;
        set(&mut m_in, "O2", o2);
        let n2_in = get(&m_in, "N2").ok_or_else(|| key_error("N2"))?;
        let gam = mats.get(&self.wall_material)?.gamma_o(self.t_k)?;
        let mut n: SpMap = RES_SPECIES.iter().map(|s| (s.to_string(), 1e14)).collect();
        let mut c: SpMap = vec![];
        for s in RES_SPECIES {
            c.push((
                s.into(),
                self.conductance(s, self.anode_orifice_area_m2, self.anode_orifice_k)?
                    + self.conductance(s, self.leak_area_m2, 1.0)?,
            ));
        }
        let cg = |s: &str| get(&c, s).expect("species");
        let (mut converged, mut it, mut resid) = (false, 0usize, f64::NAN);
        let (m_o, m_o2, m_n2) = (mass("O")?, mass("O2")?, mass("N2")?);
        for _ in 0..SS_MAX_ITER {
            it += 1;
            let k_rec = gam * (self.cbar("O")? / 4.0) * self.wall_area_m2;
            let new_o = if cg("O") + k_rec > 0.0 {
                pyops::div(get(&m_in, "O").expect("O"), m_o * (cg("O") + k_rec))?
            } else {
                0.0
            };
            let rec_mass = k_rec * new_o * m_o;
            let new_o2 = pyops::div(get(&m_in, "O2").expect("O2") + rec_mass, m_o2 * cg("O2"))?;
            let new_n2 = pyops::div(n2_in, m_n2 * cg("N2"))?;
            let new: SpMap = vec![("O".into(), new_o), ("O2".into(), new_o2), ("N2".into(), new_n2)];
            let mut rv = vec![];
            for s in RES_SPECIES {
                let (a, b) = (get(&new, s).expect("s"), get(&n, s).expect("s"));
                rv.push(pyops::div((a - b).abs(), py_max(a, 1e-30))?);
            }
            resid = pyops::py_max_iter(rv).expect("3");
            if RES_SPECIES.iter().all(|s| {
                let (a, b) = (get(&new, s).expect("s"), get(&n, s).expect("s"));
                (a - b).abs() <= SS_RTOL * py_max(a, 1e-30)
            }) {
                n = new;
                converged = true;
                break;
            }
            n = n.iter().map(|(s, v)| (s.clone(), 0.5 * (v + get(&new, s).expect("s")))).collect();
        }
        let ng = |s: &str| get(&n, s).expect("species");
        let p: SpMap = RES_SPECIES.iter().map(|s| (s.to_string(), ng(s) * K_B * self.t_k)).collect();
        let p_tot = pyops::py_sum(p.iter().map(|(_, v)| *v));
        let mut out: SpMap = vec![];
        let mut anode: SpMap = vec![];
        for s in RES_SPECIES {
            out.push((s.into(), ng(s) * cg(s) * mass(s)?));
            anode.push((
                s.into(),
                ng(s) * self.conductance(s, self.anode_orifice_area_m2, self.anode_orifice_k)? * mass(s)?,
            ));
        }
        let mtot_out = pyops::py_sum(anode.iter().map(|(_, v)| *v));
        let tau = pyops::div(
            pyops::py_sum(RES_SPECIES.iter().map(|s| ng(s) * mass(s).expect("m"))) * self.volume_m3,
            py_max(pyops::py_sum(out.iter().map(|(_, v)| *v)), 1e-30),
        )?;
        let coll = pyops::div(tau * (self.cbar("O")? / 4.0) * self.wall_area_m2, self.volume_m3)?;
        let o_in_total = o_in;
        let k_rec_f = gam * (self.cbar("O")? / 4.0) * self.wall_area_m2;
        let rec_f = k_rec_f * ng("O") * m_o;
        let og = |s: &str| get(&out, s).expect("s");
        let bal = [
            get(&m_in, "O").expect("O") - og("O") - rec_f,
            get(&m_in, "O2").expect("O2") + rec_f - og("O2"),
            n2_in - og("N2"),
        ];
        let bal_rel = pyops::div(
            pyops::py_max_iter(bal.iter().map(|v| v.abs())).expect("3"),
            py_max(pyops::py_sum(RES_SPECIES.iter().map(|s| get(&m_in, s).expect("s"))), 1e-30),
        )?;
        let fm = |m: &SpMap| crate::rec::fmap(m.iter().map(|(k, v)| (k.as_str(), *v)));
        let mut comp = Map::new();
        if mtot_out > 0.0 {
            for (s, v) in &anode {
                comp.insert(s.clone(), fnum(pyops::div(*v, mtot_out)?));
            }
        }
        let leak: SpMap = RES_SPECIES.iter().map(|s| (s.to_string(), og(s) - get(&anode, s).expect("s"))).collect();
        let o_surv = if o_in_total > 0.0 { pyops::div(get(&anode, "O").expect("O"), o_in_total)? } else { 0.0 };
        Ok(Obj::new()
            .b("converged", converged)
            .set("iterations", it)
            .f("residual", resid)
            .f("balance_residual_rel", bal_rel)
            .s("solver_status", if converged { "CONVERGED" } else { "MODEL_NOT_CONVERGED" })
            .f("p_total_Pa", p_tot)
            .set("p_species_Pa", fm(&p))
            .set("n_species", fm(&n))
            .f("T_K", self.t_k)
            .set("mdot_anode", fm(&anode))
            .set("mdot_leak", fm(&leak))
            .set("composition_anode_mass", Value::Object(comp))
            .f("O_survival", o_surv)
            .f("residence_time_s", tau)
            .f("wall_collisions_reservoir", coll)
            .f("gamma_wall", gam)
            .f("gamma_upstream", g_up)
            .f("upstream_survival", surv_up)
            .f("volume_m3", self.volume_m3)
            .f("wall_area_m2", self.wall_area_m2)
            .build()
            .as_object()
            .expect("object")
            .clone())
    }
}

fn set(m: &mut SpMap, k: &str, v: f64) {
    match m.iter_mut().find(|(s, _)| s == k) {
        Some((_, x)) => *x = v,
        None => m.push((k.to_string(), v)),
    }
}

/// Anode feed area that puts the reservoir at p_target for the given inflow (report form, G-05). Mutates
/// `anode_orifice_area_m2` as the reference does.
pub fn size_orifice_for_pressure(
    res: &mut Reservoir,
    mats: &MaterialsView,
    mdot_in: &SpMap,
    p_target_pa: f64,
) -> PyResult<Value> {
    let (mut lo, mut hi) = ORIFICE_BRACKET_M2;
    res.anode_orifice_area_m2 = lo;
    let r_lo = res.steady_state(mats, mdot_in)?;
    res.anode_orifice_area_m2 = hi;
    let r_hi = res.steady_state(mats, mdot_in)?;
    let p_lo = crate::rec::as_f64(&r_lo["p_total_Pa"]).unwrap_or(f64::NAN);
    let p_hi = crate::rec::as_f64(&r_hi["p_total_Pa"]).unwrap_or(f64::NAN);
    let bracketed = p_hi <= p_target_pa && p_target_pa <= p_lo;
    let mut inner_ok = r_lo["converged"] == Value::Bool(true) && r_hi["converged"] == Value::Bool(true);
    for _ in 0..ORIFICE_BISECTION_STEPS {
        let mid = (lo * hi).sqrt();
        res.anode_orifice_area_m2 = mid;
        let r = res.steady_state(mats, mdot_in)?;
        inner_ok = inner_ok && r["converged"] == Value::Bool(true);
        let p = crate::rec::as_f64(&r["p_total_Pa"]).unwrap_or(f64::NAN);
        if p > p_target_pa {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    let area = res.anode_orifice_area_m2;
    let r_fin = res.steady_state(mats, mdot_in)?;
    let p_fin = crate::rec::as_f64(&r_fin["p_total_Pa"]).unwrap_or(f64::NAN);
    let resid = if p_target_pa > 0.0 { pyops::div(p_fin - p_target_pa, p_target_pa)? } else { f64::NAN };
    let fin_ok = r_fin["converged"] == Value::Bool(true);
    let converged = bracketed && inner_ok && fin_ok && resid.is_finite() && resid.abs() <= ORIFICE_P_RTOL;
    Ok(Obj::new()
        .f("area_m2", area)
        .f("p_target_Pa", p_target_pa)
        .f("p_final_Pa", p_fin)
        .f("p_residual_rel", resid)
        .set("bracket_m2", Value::Array(vec![fnum(ORIFICE_BRACKET_M2.0), fnum(ORIFICE_BRACKET_M2.1)]))
        .set("p_at_bracket_Pa", Value::Array(vec![fnum(p_lo), fnum(p_hi)]))
        .b("bracketed", bracketed)
        .b("reachable", bracketed)
        .b("inner_steady_states_converged", inner_ok && fin_ok)
        .b("converged", converged)
        .s("solver_status", if converged { "CONVERGED" } else { "MODEL_NOT_CONVERGED" })
        .build())
}

/// Species-resolved reservoir inventory during compressor spin-up (explicit integration).
pub fn startup_transient(
    res: &Reservoir,
    mats: &MaterialsView,
    mdot_captured: &SpMap,
    p_ignite_pa: f64,
    spinup_s: f64,
    t_end_s: f64,
    dt_s: f64,
) -> PyResult<Value> {
    let mut m: SpMap = RES_SPECIES.iter().map(|s| (s.to_string(), 0.0)).collect();
    let mut c: SpMap = vec![];
    for s in RES_SPECIES {
        c.push((
            s.into(),
            res.conductance(s, res.anode_orifice_area_m2, res.anode_orifice_k)?
                + res.conductance(s, res.leak_area_m2, 1.0)?,
        ));
    }
    let gam = mats.get(&res.wall_material)?.gamma_o(res.t_k)?;
    let k_rec = pyops::div(gam * (res.cbar("O")? / 4.0) * res.wall_area_m2, res.volume_m3)?;
    let mut t = 0.0;
    let mut t_ign: Option<f64> = None;
    let mut hist: Vec<(f64, f64)> = vec![];
    let cmin = pyops::py_min_iter(c.iter().map(|(_, v)| *v)).expect("3");
    let tau = pyops::div(res.volume_m3, cmin)?;
    let dt = py_min(dt_s, tau / 20.0);
    let mut p = f64::NAN;
    let masses = [mass("O")?, mass("O2")?, mass("N2")?];
    while t < t_end_s {
        let f = if spinup_s > 0.0 { py_min(pyops::div(t, spinup_s)?, 1.0) } else { 1.0 };
        let rec = k_rec * get(&m, "O").expect("O");
        let mut dm: Vec<f64> = vec![];
        for s in RES_SPECIES {
            let out = pyops::div(get(&c, s).expect("c"), res.volume_m3)? * get(&m, s).expect("m");
            dm.push(f * get(mdot_captured, s).unwrap_or(0.0) - out);
        }
        dm[0] -= rec;
        dm[1] += rec;
        for (i, s) in RES_SPECIES.iter().enumerate() {
            let v = py_max(get(&m, s).expect("m") + dm[i] * dt, 0.0);
            set(&mut m, s, v);
        }
        let mut nsum = 0.0;
        for (i, s) in RES_SPECIES.iter().enumerate() {
            nsum += pyops::div(get(&m, s).expect("m"), masses[i] * res.volume_m3)?;
        }
        p = nsum * K_B * res.t_k;
        if t_ign.is_none() && p >= p_ignite_pa {
            t_ign = Some(t);
        }
        if hist.is_empty() || t - hist[hist.len() - 1].0 >= t_end_s / 200.0 {
            hist.push((t, p));
        }
        t += dt;
    }
    Ok(Obj::new()
        .set("t_ignite_s", crate::rec::onum(t_ign))
        .f("p_final_Pa", p)
        .f("tau_s", tau)
        .set("history", Value::Array(hist.iter().map(|(a, b)| Value::Array(vec![fnum(*a), fnum(*b)])).collect()))
        .build())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::materials::MaterialProps;

    fn mats() -> MaterialsView {
        let mut m = MaterialsView::default();
        m.0.insert(
            "Ti6Al4V".into(),
            MaterialProps {
                density: 4430.0,
                yield_mpa: 880.0,
                t_max_k: 700.0,
                gamma_min: 0.01,
                gamma0: 0.10,
                gamma_ea_ev: 0.08,
            },
        );
        m
    }

    #[test]
    fn steady_state_balances_and_reports_convergence() {
        let r = Reservoir::default();
        let mdot: SpMap = vec![("O".into(), 4e-7), ("N2".into(), 3e-7), ("O2".into(), 2e-8)];
        let s = r.steady_state(&mats(), &mdot).unwrap();
        assert_eq!(s["solver_status"], "CONVERGED");
        assert!(s["balance_residual_rel"].as_f64().unwrap() <= 1e-12, "CONS-P-04");
        assert_eq!(solver_eval_status(false), EvalStatus::ModelError);
    }

    #[test]
    fn missing_n2_is_a_key_error() {
        let r = Reservoir::default();
        let mdot: SpMap = vec![("O".into(), 4e-7)];
        assert_eq!(r.steady_state(&mats(), &mdot).unwrap_err().class, crate::PyClass::KeyError);
    }
}
