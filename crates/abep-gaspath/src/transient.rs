//! F4 plenum / feed transients (`abep_sim/design/plenum_feed.py` TransientRun and its metrics; contract
//! PARITY-C-ABEP_SIM_DESIGN_PLENUM_FEED_PY-V1, SOLVER_TOLERANCE class).
//!
//! The coupled chain under a normalized PI pressure controller (back-calculation anti-windup, first-order valve lag)
//! through a sequence of events, the integrator restarted at each event. States (scaled): p_s / r0 (O, N2, O2), valve
//! opening u, integral I, and three cumulative mass integrals for the conservation gate. The reference integrates with
//! scipy LSODA (BDF for its convergence reference); this port uses a Radau IIA order-5 method (simplified Newton on
//! the analytic Jacobian, step-doubling error estimate with local extrapolation, steps clamped to the output grid). An
//! integrator failure is R_INTEGRATOR (MODEL_ERROR), never a half-converged trajectory (DIV-P-01).

use crate::error::{value_error, PyResult};
use crate::materials::MaterialsView;
use crate::plenum_feed::{
    self as pf, area_for_pressure, bisection_failed, kt_over_m, solve_pressures, status_from_reasons, Chain,
    CompressorPlant, FilterCase, IntakeState, Plenum, Sp3, ATOL_SCALED, K_TOL, MASS_TOL, P_DOMAIN_PA, REASONS, RTOL,
    R_CHARACTERISTIC, R_CONSERVATION, R_DEADHEAD, R_INTEGRATOR, R_NOT_SETTLED, R_SATURATED, R_STAGE_DOMAIN, R_THERMAL,
    R_TRAJ_DOMAIN, SETTLE_BAND, ST_MODEL_ERROR,
};
use crate::pyops::{self, np_amax, np_amin, np_maximum, np_mean, np_nanmax, np_nanmin, np_sum};
use crate::rec::{flist, fnum, onum, slist, Obj};
use crate::SPECIES;
use abep_types::constants::{species_mass, K_B};
use serde_json::{Map, Value};
use std::f64::consts::PI;

pub const WINDOW_S: f64 = 60.0;
pub const SETPOINT_STEP: f64 = 0.10;
pub const FEED_PATH_STEP: f64 = 0.8;
pub const SUPPLY_STEP: f64 = 0.10;
pub const OBJECTIVES: [&str; 5] = ["V_m3", "valve_travel", "settling_max_s", "peak_deviation_max", "P_compressor_el_W"];
pub const REPORTED_NOT_OPTIMISED: [&str; 1] = ["ripple_transfer_shaft"];
const N: usize = 8;

/// Normalized PI on plenum pressure with back-calculation anti-windup and a first-order valve lag.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Controller {
    pub kp: f64,
    pub ti_s: f64,
    pub f_valve_hz: f64,
    pub authority: f64,
}

impl Controller {
    pub fn id(&self) -> String {
        let g = pyops::py_format_g;
        format!("Kp{}_Ti{}_fv{}_r{}", g(self.kp), g(self.ti_s), g(self.f_valve_hz), g(self.authority))
    }
    pub fn tau_v(&self) -> f64 {
        1.0 / (2.0 * PI * self.f_valve_hz)
    }
}

/// One segment of a test sequence.
#[derive(Debug, Clone, PartialEq)]
pub struct Event {
    pub name: String,
    pub kind: String,
    pub duration_s: f64,
    pub setpoint_pa: f64,
    pub feed_factor: f64,
    pub intake: IntakeState,
    pub orbit_amplitude: f64,
    pub orbit_period_s: f64,
    pub density: f64,
}

impl Event {
    pub fn simple(
        name: &str,
        kind: &str,
        duration_s: f64,
        setpoint_pa: f64,
        feed_factor: f64,
        intake: &IntakeState,
        density: f64,
    ) -> Event {
        Event {
            name: name.into(),
            kind: kind.into(),
            duration_s,
            setpoint_pa,
            feed_factor,
            intake: intake.clone(),
            orbit_amplitude: 0.0,
            orbit_period_s: 0.0,
            density,
        }
    }

    /// Free-stream density factor at time t after the event.
    pub fn density_at(&self, t: f64) -> f64 {
        if self.kind == "orbit" {
            self.density * (1.0 + self.orbit_amplitude * (2.0 * PI * t / self.orbit_period_s).sin())
        } else {
            self.density * 1.0
        }
    }

    pub fn to_dict(&self) -> Value {
        Obj::new()
            .s("name", &self.name)
            .s("kind", &self.kind)
            .f("duration_s", self.duration_s)
            .f("setpoint_Pa", self.setpoint_pa)
            .f("feed_factor", self.feed_factor)
            .s("intake_state", &self.intake.state)
            .f("orbit_amplitude", self.orbit_amplitude)
            .f("orbit_period_s", self.orbit_period_s)
            .f("density", self.density)
            .build()
    }
}

/// The fixed test sequence (definition) at the design state.
pub fn event_sequence(design: &IntakeState, r0: f64, window_s: f64) -> Vec<Event> {
    let w = window_s;
    vec![
        Event::simple("E0_hold", "hold", 10.0, r0, 1.0, design, 1.0),
        Event::simple("E1_setpoint_up", "setpoint", w, r0 * (1.0 + SETPOINT_STEP), 1.0, design, 1.0),
        Event::simple("E2_setpoint_down", "setpoint", w, r0, 1.0, design, 1.0),
        Event::simple("E3_feed_path_step", "feed_path", w, r0, FEED_PATH_STEP, design, 1.0),
        Event::simple("E4_feed_path_restore", "feed_path", w, r0, 1.0, design, 1.0),
        Event::simple("E5_supply_down", "supply", w, r0, 1.0, design, 1.0 - SUPPLY_STEP),
        Event::simple("E6_supply_up", "supply", w, r0, 1.0, design, 1.0 + SUPPLY_STEP),
        Event::simple("E7_supply_restore", "supply", w, r0, 1.0, design, 1.0),
    ]
}

/// One simulated segment: samples at the reference t_eval grid plus the trajectory domain summary.
#[derive(Debug, Clone, PartialEq)]
pub struct Segment {
    pub event: String,
    pub kind: String,
    pub t_start_s: f64,
    pub duration_s: f64,
    pub t: Vec<f64>,
    pub p: Vec<f64>,
    pub mdot: Vec<f64>,
    pub u: Vec<f64>,
    pub x_o: Vec<f64>,
    pub setpoint_pa: f64,
    pub saturated_end: bool,
    pub ucmd_end: f64,
    pub intake_state: String,
    pub k_min: f64,
    pub k_over_k0_max: f64,
    pub p_stage_max_pa: f64,
    pub p_inlet_max_pa: f64,
    pub p_el_max_w: f64,
    pub t_comp_max_k: f64,
    pub t_comp_limit_k: f64,
}

impl Segment {
    pub fn to_value(&self) -> Value {
        Obj::new()
            .s("event", &self.event)
            .s("kind", &self.kind)
            .f("t_start_s", self.t_start_s)
            .f("duration_s", self.duration_s)
            .set("t", flist(&self.t))
            .set("p", flist(&self.p))
            .set("mdot", flist(&self.mdot))
            .set("u", flist(&self.u))
            .set("xO", flist(&self.x_o))
            .f("setpoint_Pa", self.setpoint_pa)
            .b("saturated_end", self.saturated_end)
            .s("intake_state", &self.intake_state)
            .f("K_min", self.k_min)
            .f("K_over_K0_max", self.k_over_k0_max)
            .f("p_stage_max_Pa", self.p_stage_max_pa)
            .f("p_inlet_max_Pa", self.p_inlet_max_pa)
            .f("P_el_max_W", self.p_el_max_w)
            .f("T_comp_max_K", self.t_comp_max_k)
            .f("T_comp_limit_K", self.t_comp_limit_k)
            .build()
    }
}

/// Result of TransientRun.run.
#[derive(Debug, Clone, PartialEq)]
pub struct RunResult {
    pub ok: bool,
    pub message: String,
    pub segments: Vec<Segment>,
    pub mass_residual_rel: f64,
    pub throughput_kg: f64,
    pub nfev: usize,
}

impl RunResult {
    pub fn to_value(&self, with_ucmd: bool) -> Value {
        let segs: Vec<Value> = self
            .segments
            .iter()
            .map(|s| {
                let mut v = s.to_value();
                if with_ucmd {
                    v.as_object_mut().expect("obj").insert("_ucmd_end".into(), fnum(s.ucmd_end));
                }
                v
            })
            .collect();
        if !self.ok {
            return Obj::new()
                .b("ok", false)
                .s("reason", R_INTEGRATOR)
                .s("message", &self.message)
                .set("segments", Value::Array(segs))
                .set("nfev", self.nfev)
                .build();
        }
        Obj::new()
            .b("ok", true)
            .set("segments", Value::Array(segs))
            .f("mass_residual_rel", self.mass_residual_rel)
            .f("throughput_kg", self.throughput_kg)
            .set("nfev", self.nfev)
            .build()
    }
}

/// Coefficients of one event (compressor-net inflow and the bookkeeping terms).
struct EventCoeffs {
    q0: Sp3,
    k: Sp3,
    q0g: Sp3,
    dq: Sp3,
    l0: Sp3,
    dl: Sp3,
}

/// The right-hand side and Jacobian of one event.
struct Rhs {
    v: f64,
    r0: f64,
    c: EventCoeffs,
    g: Sp3,
    cl: Sp3,
    km: Sp3,
    kr: f64,
    mr: f64,
    orbit: bool,
    w: f64,
    amp: f64,
    d0: f64,
    rset: f64,
    kp: f64,
    ti: f64,
    tau: f64,
    uff: f64,
    ms: f64,
}

impl Rhs {
    fn dens(&self, t: f64) -> f64 {
        if self.orbit {
            self.d0 * (1.0 + self.amp * (self.w * t).sin())
        } else {
            self.d0
        }
    }

    fn ctrl(&self, p_tot: f64, i_int: f64) -> (f64, f64, bool, f64) {
        let eps = (p_tot - self.rset) / self.rset;
        let ucmd = self.uff * (1.0 + self.kp * eps + (self.kp / self.ti) * i_int);
        let (hi, lo) = (ucmd > 1.0, ucmd < 0.0);
        let usat = if hi {
            1.0
        } else if lo {
            0.0
        } else {
            ucmd
        };
        (eps, ucmd, hi || lo, usat)
    }

    fn f(&self, t: f64, y: &[f64; N]) -> [f64; N] {
        let d = self.dens(t);
        let p = [y[0] * self.r0, y[1] * self.r0, y[2] * self.r0];
        let (u, i_int) = (y[3], y[4]);
        let (eps, ucmd, _, usat) = self.ctrl(p[0] + p[1] + p[2], i_int);
        let rec = self.kr * p[0];
        let mut out = [0.0; N];
        let (mut ins, mut outs) = (0.0, 0.0);
        for i in 0..3 {
            let mut net = self.c.q0[i] * d - self.c.k[i] * p[i] - self.g[i] * u * p[i] - self.cl[i] * p[i];
            if i == 0 {
                net -= rec;
            } else if i == 2 {
                net += rec * self.mr;
            }
            out[i] = net / self.v / self.r0;
            let qg = self.c.q0g[i] * d + self.c.dq[i] * p[i];
            let lb = self.c.l0[i] * d + self.c.dl[i] * p[i];
            ins += qg * self.km[i];
            outs += (lb + self.g[i] * u * p[i] + self.cl[i] * p[i]) * self.km[i];
        }
        out[3] = (usat - u) / self.tau;
        out[4] = eps + (usat - ucmd) / (self.kp * self.uff);
        out[5] = ins / self.ms;
        out[6] = outs / self.ms;
        out[7] = rec * self.km[0] / self.ms;
        out
    }

    fn jac(&self, y: &[f64; N]) -> [[f64; N]; N] {
        let p = [y[0] * self.r0, y[1] * self.r0, y[2] * self.r0];
        let (u, i_int) = (y[3], y[4]);
        let (_, _, sat, _) = self.ctrl(p[0] + p[1] + p[2], i_int);
        let mut j = [[0.0; N]; N];
        let (v, r0) = (self.v, self.r0);
        for i in 0..3 {
            j[i][i] = -(self.c.k[i] + self.g[i] * u + self.cl[i]) / v;
            j[i][3] = -self.g[i] * p[i] / v / r0;
        }
        j[0][0] -= self.kr / v;
        j[2][0] += self.kr * self.mr / v;
        for i in 0..3 {
            j[3][i] = if sat { 0.0 } else { self.uff * self.kp / self.tau * r0 / self.rset };
            j[4][i] = if sat { 0.0 } else { r0 / self.rset };
        }
        j[3][3] = -1.0 / self.tau;
        j[3][4] = if sat { 0.0 } else { self.uff * self.kp / self.ti / self.tau };
        j[4][4] = if sat { -1.0 / self.ti } else { 0.0 };
        for i in 0..3 {
            j[5][i] = self.c.dq[i] * self.km[i] * r0 / self.ms;
            j[6][i] = (self.c.dl[i] + self.g[i] * u + self.cl[i]) * self.km[i] * r0 / self.ms;
            j[6][3] += self.g[i] * p[i] * self.km[i] / self.ms;
        }
        j[7][0] = self.kr * self.km[0] * r0 / self.ms;
        j
    }
}

// ------------------------------------------------------------------------------------------------ Radau IIA (5)
const NS: usize = 3 * N;

fn radau_coeffs() -> ([f64; 3], [[f64; 3]; 3]) {
    let s6 = 6.0f64.sqrt();
    let c = [(4.0 - s6) / 10.0, (4.0 + s6) / 10.0, 1.0];
    let a = [
        [(88.0 - 7.0 * s6) / 360.0, (296.0 - 169.0 * s6) / 1800.0, (-2.0 + 3.0 * s6) / 225.0],
        [(296.0 + 169.0 * s6) / 1800.0, (88.0 + 7.0 * s6) / 360.0, (-2.0 - 3.0 * s6) / 225.0],
        [(16.0 - s6) / 36.0, (16.0 + s6) / 36.0, 1.0 / 9.0],
    ];
    (c, a)
}

/// Dense LU with partial pivoting (in place); None when singular.
fn lu(m: &mut [[f64; NS]; NS]) -> Option<[usize; NS]> {
    let mut piv = [0usize; NS];
    for (k, pv) in piv.iter_mut().enumerate() {
        let mut best = k;
        for i in k + 1..NS {
            if m[i][k].abs() > m[best][k].abs() {
                best = i;
            }
        }
        if m[best][k] == 0.0 || !m[best][k].is_finite() {
            return None;
        }
        m.swap(k, best);
        *pv = best;
        for i in k + 1..NS {
            let f = m[i][k] / m[k][k];
            m[i][k] = f;
            for jj in k + 1..NS {
                m[i][jj] -= f * m[k][jj];
            }
        }
    }
    Some(piv)
}

fn lu_solve(m: &[[f64; NS]; NS], piv: &[usize; NS], b: &mut [f64; NS]) {
    for k in 0..NS {
        b.swap(k, piv[k]);
    }
    for i in 0..NS {
        for k in 0..i {
            b[i] -= m[i][k] * b[k];
        }
    }
    for i in (0..NS).rev() {
        for k in i + 1..NS {
            b[i] -= m[i][k] * b[k];
        }
        b[i] /= m[i][i];
    }
}

struct Integrator<'a> {
    rhs: &'a Rhs,
    rtol: f64,
    atol: f64,
    nfev: usize,
    c: [f64; 3],
    a: [[f64; 3]; 3],
}

impl Integrator<'_> {
    /// One Radau IIA step of size h from (t, y); None when the simplified Newton iteration fails.
    fn step(&mut self, t: f64, y: &[f64; N], h: f64) -> Option<[f64; N]> {
        let j = self.rhs.jac(y);
        let mut m = [[0.0; NS]; NS];
        for bi in 0..3 {
            for bj in 0..3 {
                for r in 0..N {
                    for cidx in 0..N {
                        let id = if bi == bj && r == cidx { 1.0 } else { 0.0 };
                        m[bi * N + r][bj * N + cidx] = id - h * self.a[bi][bj] * j[r][cidx];
                    }
                }
            }
        }
        let piv = lu(&mut m)?;
        let scale: Vec<f64> = y.iter().map(|v| self.atol + self.rtol * v.abs()).collect();
        let mut z = [0.0; NS];
        for _ in 0..12 {
            let mut fz = [[0.0; N]; 3];
            for (i, fzi) in fz.iter_mut().enumerate() {
                let mut yi = *y;
                for k in 0..N {
                    yi[k] += z[i * N + k];
                }
                *fzi = self.rhs.f(t + self.c[i] * h, &yi);
                self.nfev += 1;
            }
            let mut rhs_v = [0.0; NS];
            for i in 0..3 {
                for k in 0..N {
                    let mut s = 0.0;
                    for jj in 0..3 {
                        s += self.a[i][jj] * fz[jj][k];
                    }
                    rhs_v[i * N + k] = -z[i * N + k] + h * s;
                }
            }
            lu_solve(&m, &piv, &mut rhs_v);
            let mut nrm = 0.0;
            for i in 0..3 {
                for k in 0..N {
                    let d = rhs_v[i * N + k];
                    if !d.is_finite() {
                        return None;
                    }
                    z[i * N + k] += d;
                    nrm += (d / scale[k]).powi(2);
                }
            }
            nrm = (nrm / NS as f64).sqrt();
            if nrm <= 1e-3 {
                let mut out = *y;
                for k in 0..N {
                    out[k] += z[2 * N + k];
                }
                return Some(out);
            }
        }
        None
    }

    /// Integrate from t0 = 0 over the output grid `te` (te[0] = 0, increasing); None when the step size collapses.
    fn integrate(&mut self, y0: [f64; N], te: &[f64]) -> Result<Vec<[f64; N]>, String> {
        let mut out = vec![y0];
        let span = te[te.len() - 1];
        let mut t = 0.0;
        let mut y = y0;
        let mut h = if te.len() > 1 { te[1] } else { span };
        let mut steps = 0usize;
        for &t_out in &te[1..] {
            while t < t_out {
                steps += 1;
                if steps > 2_000_000 {
                    return Err("step limit".into());
                }
                let hh = h.min(t_out - t);
                if hh < 1e-14 * span.max(1e-300) {
                    return Err(format!("step size collapsed at t = {t}"));
                }
                let full = self.step(t, &y, hh);
                let half = self.step(t, &y, hh / 2.0).and_then(|ya| self.step(t + hh / 2.0, &ya, hh / 2.0));
                let (Some(y1), Some(y2)) = (full, half) else {
                    h = hh * 0.25;
                    continue;
                };
                let mut en = 0.0;
                let mut err = [0.0; N];
                for k in 0..N {
                    err[k] = (y2[k] - y1[k]) / 31.0;
                    let sc = self.atol + self.rtol * y[k].abs().max(y2[k].abs());
                    en += (err[k] / sc).powi(2);
                }
                en = (en / N as f64).sqrt();
                if !en.is_finite() {
                    h = hh * 0.25;
                    continue;
                }
                let fac = if en == 0.0 { 4.0 } else { (0.9 * en.powf(-1.0 / 6.0)).clamp(0.2, 4.0) };
                if en <= 1.0 {
                    t = if hh == t_out - t { t_out } else { t + hh };
                    for k in 0..N {
                        y[k] = y2[k] + err[k];
                    }
                    // keep the proposed step when the output point clamped it
                    h = if hh < h { h.max(hh * fac) } else { hh * fac };
                } else {
                    h = hh * fac.min(0.9);
                }
            }
            out.push(y);
        }
        Ok(out)
    }
}

// ------------------------------------------------------------------------------------------------ transient run
pub struct TransientRun<'a> {
    pub filt: FilterCase,
    pub plant: CompressorPlant,
    pub plenum: Plenum,
    pub ctrl: Controller,
    pub mats: &'a MaterialsView,
    pub rtol: f64,
    pub method: String,
    pub t_k: f64,
    pub leak: Sp3,
    pub fc: Sp3,
    pub k_rec: f64,
    pub km: Sp3,
    pub mo_mo2: f64,
    pub r0: f64,
    pub a_ss: f64,
    pub a_max: f64,
    pub u_ff: f64,
    pub p_init: Sp3,
    pub mdot_scale: f64,
    pub design_intake: IntakeState,
}

fn m_of(s: &str) -> f64 {
    species_mass(s).expect("chain species")
}

impl<'a> TransientRun<'a> {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        filt: &FilterCase,
        plant: &CompressorPlant,
        plenum: &Plenum,
        ctrl: Controller,
        mats: &'a MaterialsView,
        design_intake: &IntakeState,
        r0_pa: f64,
        rtol: f64,
        method: Option<&str>,
    ) -> PyResult<TransientRun<'a>> {
        let t_k = plenum.t_k;
        let leak = plenum.leak3()?;
        let fc = plenum.feed3()?;
        let k_rec = plenum.k_rec_m3_s()?;
        let mut km = [0.0; 3];
        for (i, s) in SPECIES.iter().enumerate() {
            km[i] = pyops::div(1.0, kt_over_m(s, t_k)?)?;
        }
        let chain =
            Chain { intake: design_intake.clone(), filt: filt.clone(), plant: plant.clone(), plenum: plenum.clone() };
        let co = chain.node_coefficients(1.0)?;
        let sol = area_for_pressure(&co, r0_pa, k_rec, &leak, &fc, true)?;
        if !sol.ok {
            return Err(value_error("design setpoint at or above dead-head: no steady operating point to start from"));
        }
        if bisection_failed(sol.a_eq, sol.resid) {
            return Err(value_error("design setpoint orifice-area bisection did not converge (R_BISECTION)"));
        }
        let a_ss = sol.a_eq;
        let a_max = ctrl.authority * a_ss;
        let u_ff = 1.0 / ctrl.authority;
        let (p3, _) = solve_pressures(&co, a_ss, k_rec, &leak, &fc, true)?;
        let mut mdot_scale = 0.0;
        for i in 0..3 {
            mdot_scale += fc[i] * a_ss * p3[i] * km[i];
        }
        Ok(TransientRun {
            filt: filt.clone(),
            plant: plant.clone(),
            plenum: plenum.clone(),
            ctrl,
            mats,
            rtol,
            method: method.unwrap_or(pf::INTEGRATOR_METHOD).to_string(),
            t_k,
            leak,
            fc,
            k_rec,
            km,
            mo_mo2: m_of("O") / m_of("O2"),
            r0: r0_pa,
            a_ss,
            a_max,
            u_ff,
            p_init: p3,
            mdot_scale,
            design_intake: design_intake.clone(),
        })
    }

    pub fn u_cmd(&self, eps: f64, i_int: f64) -> f64 {
        self.u_ff * (1.0 + self.ctrl.kp * eps + (self.ctrl.kp / self.ctrl.ti_s) * i_int)
    }

    fn chain(&self, intake: &IntakeState) -> Chain {
        Chain {
            intake: intake.clone(),
            filt: self.filt.clone(),
            plant: self.plant.clone(),
            plenum: self.plenum.clone(),
        }
    }

    fn event_coeffs(&self, ev: &Event) -> PyResult<EventCoeffs> {
        let co = self.chain(&ev.intake).node_coefficients(1.0)?;
        let cl = self.plant.leak_m3_s();
        let mut c = EventCoeffs { q0: [0.0; 3], k: [0.0; 3], q0g: [0.0; 3], dq: [0.0; 3], l0: [0.0; 3], dl: [0.0; 3] };
        for i in 0..3 {
            let n = co[i];
            let den = n.e + n.alpha;
            c.q0[i] = pyops::div(n.alpha * n.f, den)?;
            c.k[i] = pyops::div(n.e * n.beta, den)?;
            c.q0g[i] = pyops::div(pyops::div(n.a_c * n.f, den)?, n.b_c)?;
            c.dq[i] = pyops::div(pyops::div(n.a_c * n.beta, den)? - 1.0, n.b_c)?;
            c.l0[i] = pyops::div(-cl * n.f, den)?;
            c.dl[i] = cl * (1.0 - pyops::div(n.beta, den)?);
        }
        Ok(c)
    }

    fn make(&self, ev: &Event) -> PyResult<Rhs> {
        let orbit = ev.kind == "orbit";
        Ok(Rhs {
            v: self.plenum.volume_m3,
            r0: self.r0,
            c: self.event_coeffs(ev)?,
            g: [
                self.fc[0] * self.a_max * ev.feed_factor,
                self.fc[1] * self.a_max * ev.feed_factor,
                self.fc[2] * self.a_max * ev.feed_factor,
            ],
            cl: self.leak,
            km: self.km,
            kr: self.k_rec,
            mr: self.mo_mo2,
            orbit,
            w: if orbit { 2.0 * PI / ev.orbit_period_s } else { 0.0 },
            amp: ev.orbit_amplitude,
            d0: ev.density,
            rset: ev.setpoint_pa,
            kp: self.ctrl.kp,
            ti: self.ctrl.ti_s,
            tau: self.ctrl.tau_v(),
            uff: self.u_ff,
            ms: self.mdot_scale,
        })
    }

    /// Initial state = the steady state of `intake` held at the setpoint: (y0, u_ss); None at / above dead-head.
    pub fn steady_start(
        &self,
        intake: &IntakeState,
        setpoint_pa: f64,
        density: f64,
    ) -> PyResult<Option<([f64; N], f64)>> {
        let co = self.chain(intake).node_coefficients(density)?;
        let sol = area_for_pressure(&co, setpoint_pa, self.k_rec, &self.leak, &self.fc, true)?;
        if !sol.ok {
            return Ok(None);
        }
        let u_ss = sol.a_eq / self.a_max;
        let (p3, _) = solve_pressures(&co, sol.a_eq, self.k_rec, &self.leak, &self.fc, true)?;
        let i_int = (u_ss / self.u_ff - 1.0) * self.ctrl.ti_s / self.ctrl.kp;
        Ok(Some(([p3[0] / self.r0, p3[1] / self.r0, p3[2] / self.r0, u_ss, i_int, 0.0, 0.0, 0.0], u_ss)))
    }

    fn mass(&self, y: &[f64; N]) -> f64 {
        let mut s = 0.0;
        for i in 0..3 {
            s += pyops::py_max(y[i], 0.0) * self.r0 * self.plenum.volume_m3 * self.km[i];
        }
        s
    }

    /// The reference output grid of one event.
    pub fn t_eval(duration_s: f64, n_eval: usize) -> Vec<f64> {
        let g = pyops::np_geomspace(1e-6 * duration_s.max(1.0), duration_s, n_eval);
        let mut te = vec![0.0];
        te.extend(g);
        te.sort_by(|a, b| a.partial_cmp(b).expect("finite"));
        te.dedup();
        let last = te.len() - 1;
        te[last] = duration_s;
        te
    }

    pub fn run(&self, events: &[Event], n_eval: usize, y_start: Option<[f64; N]>) -> PyResult<RunResult> {
        let (c, a) = radau_coeffs();
        let mut y = y_start.unwrap_or([
            self.p_init[0] / self.r0,
            self.p_init[1] / self.r0,
            self.p_init[2] / self.r0,
            self.u_ff,
            0.0,
            0.0,
            0.0,
            0.0,
        ]);
        let m0 = self.mass(&y);
        let (mut t0, mut nfev, mut cum_in, mut cum_out) = (0.0, 0usize, 0.0, 0.0);
        let mut segs = vec![];
        for ev in events {
            let rhs = self.make(ev)?;
            let te = Self::t_eval(ev.duration_s, n_eval);
            let y0 = [y[0], y[1], y[2], y[3], y[4], 0.0, 0.0, 0.0];
            let mut integ = Integrator { rhs: &rhs, rtol: self.rtol, atol: ATOL_SCALED, nfev: 0, c, a };
            let sol = integ.integrate(y0, &te);
            nfev += integ.nfev;
            let ys = match sol {
                Ok(v) => v,
                Err(msg) => {
                    return Ok(RunResult {
                        ok: false,
                        message: msg,
                        segments: segs,
                        mass_residual_rel: f64::NAN,
                        throughput_kg: f64::NAN,
                        nfev,
                    })
                }
            };
            y = ys[ys.len() - 1];
            cum_in += y[5] * self.mdot_scale;
            cum_out += y[6] * self.mdot_scale;
            segs.push(self.segment_record(ev, t0, &te, &ys)?);
            t0 += ev.duration_s;
        }
        let resid = ((self.mass(&y) - m0) - (cum_in - cum_out)).abs() / pyops::py_max(cum_in, 1e-300);
        Ok(RunResult {
            ok: true,
            message: String::new(),
            segments: segs,
            mass_residual_rel: resid,
            throughput_kg: cum_in,
            nfev,
        })
    }

    fn segment_record(&self, ev: &Event, t0: f64, t: &[f64], ys: &[[f64; N]]) -> PyResult<Segment> {
        let r0 = self.r0;
        let n = t.len();
        let (mut p, mut mdot, mut u, mut xo) = (vec![0.0; n], vec![0.0; n], vec![0.0; n], vec![0.0; n]);
        let mut ps_all = vec![[0.0; 3]; n];
        for (k, y) in ys.iter().enumerate() {
            let ps = [np_maximum(y[0], 0.0) * r0, np_maximum(y[1], 0.0) * r0, np_maximum(y[2], 0.0) * r0];
            ps_all[k] = ps;
            p[k] = ps[0] + ps[1] + ps[2];
            u[k] = y[3];
            let a_eq = y[3] * self.a_max * ev.feed_factor;
            let md = [
                self.fc[0] * a_eq * ps[0] * self.km[0],
                self.fc[1] * a_eq * ps[1] * self.km[1],
                self.fc[2] * a_eq * ps[2] * self.km[2],
            ];
            mdot[k] = md[0] + md[1] + md[2];
            let nmol = [md[0] / m_of("O"), md[1] / m_of("N2"), md[2] / m_of("O2")];
            let nt = nmol[0] + nmol[1] + nmol[2];
            xo[k] = if nt > 0.0 { nmol[0] / nt } else { f64::NAN };
        }
        let last = ys[n - 1];
        let ucmd_end = self.u_cmd((p[n - 1] - ev.setpoint_pa) / ev.setpoint_pa, last[4]);
        let co = self.chain(&ev.intake).node_coefficients(1.0)?;
        let (mut kmin, mut kmax, mut psm, mut pin, mut pel, mut tc) = (
            f64::INFINITY,
            f64::NEG_INFINITY,
            f64::NEG_INFINITY,
            f64::NEG_INFINITY,
            f64::NEG_INFINITY,
            f64::NEG_INFINITY,
        );
        let fold_min = |a: f64, b: f64| if a.is_nan() || b.is_nan() { f64::NAN } else { a.min(b) };
        let fold_max = |a: f64, b: f64| if a.is_nan() || b.is_nan() { f64::NAN } else { a.max(b) };
        for k in 0..n {
            let d = ev.density_at(t[k]);
            let (mut p2, mut q) = ([0.0; 3], [0.0; 3]);
            for i in 0..3 {
                let c = co[i];
                p2[i] = (c.f * d + c.beta * ps_all[k][i]) / (c.e + c.alpha);
                q[i] = (c.a_c * p2[i] - ps_all[k][i]) / c.b_c;
            }
            let cas = self.plant.cascade_impl(self.mats, &p2, &q, true)?;
            kmin = fold_min(kmin, cas.k_min);
            kmax = fold_max(kmax, cas.k_over_k0_max);
            psm = fold_max(psm, cas.p_stage_max);
            pin = fold_max(pin, p2[0] + p2[1] + p2[2]);
            pel = fold_max(pel, cas.p_el_w);
            tc = fold_max(tc, cas.t_comp_k);
        }
        Ok(Segment {
            event: ev.name.clone(),
            kind: ev.kind.clone(),
            t_start_s: t0,
            duration_s: ev.duration_s,
            t: t.to_vec(),
            p,
            mdot,
            u,
            x_o: xo,
            setpoint_pa: ev.setpoint_pa,
            saturated_end: ucmd_end > 1.0 + 1e-9 || ucmd_end < -1e-9,
            ucmd_end,
            intake_state: ev.intake.state.clone(),
            k_min: kmin,
            k_over_k0_max: kmax,
            p_stage_max_pa: psm,
            p_inlet_max_pa: pin,
            p_el_max_w: pel,
            t_comp_max_k: tc,
            t_comp_limit_k: self.mats.get(&self.plant.comp.rotor_material)?.t_max_k,
        })
    }
}

// ------------------------------------------------------------------------------------------------ metrics
/// Time after which |y - final| <= band |final| for the rest of the window; None when the last sample is outside.
pub fn settling_time(t: &[f64], y: &[f64], final_v: f64, band: f64) -> Option<f64> {
    let out: Vec<bool> = y.iter().map(|v| (v - final_v).abs() > band * final_v.abs()).collect();
    if !out.iter().any(|b| *b) {
        return Some(0.0);
    }
    if out[out.len() - 1] {
        return None;
    }
    let last = out.iter().rposition(|b| *b).expect("any");
    Some(t[last + 1])
}

/// Metric definitions of the reference (settling, overshoot, peak deviation, flow recovery, ripple, valve travel).
pub fn segment_metrics(seg: &Segment, p_prev_final: f64) -> Value {
    let (t, p, md, u) = (&seg.t, &seg.p, &seg.mdot, &seg.u);
    let r = seg.setpoint_pa;
    let (pf_, mf) = (p[p.len() - 1], md[md.len() - 1]);
    let diffs: Vec<f64> = u.windows(2).map(|w| (w[1] - w[0]).abs()).collect();
    let mut o = Obj::new()
        .s("event", &seg.event)
        .s("kind", &seg.kind)
        .f("P_final_Pa", pf_)
        .f("mdot_final_kgps", mf)
        .f("P_min_Pa", np_amin(p))
        .f("P_max_Pa", np_amax(p))
        .f("mdot_min_kgps", np_amin(md))
        .f("mdot_max_kgps", np_amax(md))
        .f("xO_min", np_nanmin(&seg.x_o))
        .f("xO_max", np_nanmax(&seg.x_o))
        .f("valve_travel", np_sum(&diffs))
        .f("u_min", np_amin(u))
        .f("u_max", np_amax(u))
        .b("saturated_end", seg.saturated_end)
        .f("final_setpoint_error_frac", (pf_ - r).abs() / r);
    if seg.kind == "orbit" {
        return o
            .f("ripple_pp_frac_P", (np_amax(p) - np_amin(p)) / np_mean(p))
            .f("ripple_pp_frac_mdot", (np_amax(md) - np_amin(md)) / np_mean(md))
            .set("settling_time_s", Value::Null)
            .build();
    }
    o = o
        .set("settling_time_s", onum(settling_time(t, p, r, SETTLE_BAND)))
        .set("flow_recovery_s", onum(settling_time(t, md, mf, SETTLE_BAND)));
    if seg.kind == "setpoint" {
        let d = pf_ - p_prev_final;
        let ov = if d != 0.0 {
            let sg = if d > 0.0 {
                1.0
            } else if d < 0.0 {
                -1.0
            } else {
                0.0
            };
            let mx = np_amax(&p.iter().map(|v| sg * (v - r)).collect::<Vec<f64>>());
            let m = if mx > 0.0 { mx } else { 0.0 };
            m / d.abs()
        } else {
            0.0
        };
        o.f("overshoot_frac", ov).set("peak_deviation_frac", Value::Null).build()
    } else {
        let pk = np_amax(&p.iter().map(|v| (v - r).abs()).collect::<Vec<f64>>()) / r;
        o.set("overshoot_frac", Value::Null).f("peak_deviation_frac", pk).build()
    }
}

fn mf(m: &Value, k: &str) -> Option<f64> {
    crate::rec::as_f64(&m[k])
}

/// Trajectory domain reasons (pressure, Gaede characteristic, stage / inlet domain, thermal) over segments.
pub fn domain_reasons(segs: &[Segment]) -> Vec<&'static str> {
    let mut out = vec![];
    let pmax = pyops::py_max_iter(segs.iter().map(|s| np_amax(&s.p))).unwrap_or(f64::NAN);
    if pmax > P_DOMAIN_PA {
        out.push(R_TRAJ_DOMAIN);
    }
    let kmin = pyops::py_min_iter(segs.iter().map(|s| s.k_min)).unwrap_or(f64::NAN);
    let kmax = pyops::py_max_iter(segs.iter().map(|s| s.k_over_k0_max)).unwrap_or(f64::NAN);
    if kmin < 1.0 - K_TOL || kmax > 1.0 + K_TOL {
        out.push(R_CHARACTERISTIC);
    }
    let psm = pyops::py_max_iter(segs.iter().map(|s| s.p_stage_max_pa)).unwrap_or(f64::NAN);
    let pin = pyops::py_max_iter(segs.iter().map(|s| s.p_inlet_max_pa)).unwrap_or(f64::NAN);
    if psm > P_DOMAIN_PA * (1.0 + 1e-12) || pin > P_DOMAIN_PA {
        out.push(R_STAGE_DOMAIN);
    }
    if segs.iter().any(|s| s.t_comp_max_k > s.t_comp_limit_k) {
        out.push(R_THERMAL);
    }
    out
}

fn sort_reasons(mut r: Vec<String>) -> Vec<String> {
    r.sort_by_key(|x| REASONS.iter().position(|y| y == x).unwrap_or(usize::MAX));
    r.dedup();
    r
}

/// Orbit-scale check at every state: density 1 + amplitude sin(phase) on n_phase phases, plenum held at r0.
#[allow(clippy::too_many_arguments)]
pub fn orbit_quasi_static(
    filt: &FilterCase,
    plant: &CompressorPlant,
    plenum: &Plenum,
    mats: &MaterialsView,
    states: &[IntakeState],
    r0: f64,
    amplitude: f64,
    a_max_m2: f64,
    n_phase: usize,
) -> PyResult<Value> {
    let dens: Vec<f64> =
        (0..n_phase).map(|k| 1.0 + amplitude * ((2.0 * PI) * k as f64 / n_phase as f64).sin()).collect();
    let mut rows = vec![];
    let mut reasons: Vec<String> = vec![];
    for st in states {
        let base = pf::intake_side(std::slice::from_ref(st), filt, 1.0)?;
        let f: Vec<Sp3> = dens.iter().map(|d| [base.0[0][0] * d, base.0[0][1] * d, base.0[0][2] * d]).collect();
        let e: Vec<Sp3> = vec![base.1[0]; n_phase];
        let sw = pf::steady_sweep(&(f, e), plant, plenum, mats, &[r0], None)?;
        let bits = sw.bits.iter().fold(0i64, |a, b| a | b);
        let mut rs: Vec<String> = pf::reasons_from_bits(bits).into_iter().map(String::from).collect();
        let mut row = Obj::new().s("state", &st.state).set("n_phase", n_phase).f("amplitude", amplitude);
        if rs.is_empty() {
            let u: Vec<f64> = sw.a_eq_m2.iter().map(|a| a / a_max_m2).collect();
            let md = &sw.mdot_total_kgps;
            let xo = &sw.x_s_flow_mole[0];
            let umax = np_amax(&u);
            row = row
                .f("u_min", np_amin(&u))
                .f("u_max", umax)
                .f("mdot_min_kgps", np_amin(md))
                .f("mdot_max_kgps", np_amax(md))
                .f("ripple_pp_frac_mdot", (np_amax(md) - np_amin(md)) / np_mean(md))
                .f("xO_flow_min", np_amin(xo))
                .f("xO_flow_max", np_amax(xo));
            if umax > 1.0 {
                rs = vec![R_SATURATED.to_string()];
            }
        }
        row = row.set("reasons", slist(&rs));
        reasons.extend(rs);
        rows.push(row.build());
    }
    Ok(Obj::new()
        .set("rows", Value::Array(rows))
        .set("reasons", slist(sort_reasons(reasons)))
        .f("amplitude", amplitude)
        .build())
}

/// Full transient over one orbital period at `state`, started from its own steady state.
#[allow(clippy::too_many_arguments)]
pub fn orbit_simulated(
    filt: &FilterCase,
    plant: &CompressorPlant,
    plenum: &Plenum,
    ctrl: Controller,
    mats: &MaterialsView,
    design: &IntakeState,
    state: &IntakeState,
    r0: f64,
    amplitude: f64,
) -> PyResult<Value> {
    let tr = TransientRun::new(filt, plant, plenum, ctrl, mats, design, r0, RTOL, None)?;
    let start = tr.steady_start(state, r0, 1.0)?;
    let Some((y0, u_ss)) = start.filter(|(_, u)| !(*u > 1.0)) else {
        return Ok(Obj::new().b("ok", false).s("reason", "NO_STEADY_START").build());
    };
    let _ = u_ss;
    let t_orb = pf::orbital_period_s(state.alt_km)?;
    let ev = Event {
        name: format!("O_{}", state.state),
        kind: "orbit".into(),
        duration_s: t_orb,
        setpoint_pa: r0,
        feed_factor: 1.0,
        intake: state.clone(),
        orbit_amplitude: amplitude,
        orbit_period_s: t_orb,
        density: 1.0,
    };
    let out = tr.run(&[ev], 150, Some(y0))?;
    if !out.ok {
        return Ok(Obj::new().b("ok", false).s("reason", R_INTEGRATOR).build());
    }
    let sg = &out.segments[0];
    let dev = np_amax(&sg.p.iter().map(|p| (p / r0 - 1.0).abs()).collect::<Vec<f64>>());
    Ok(Obj::new()
        .b("ok", true)
        .s("state", &state.state)
        .f("P_dev_max_frac", dev)
        .f("mdot_min_kgps", np_amin(&sg.mdot))
        .f("mdot_max_kgps", np_amax(&sg.mdot))
        .f("mass_residual_rel", out.mass_residual_rel)
        .set("nfev", out.nfev)
        .build())
}

/// Event sequence at the design state plus the orbit check: metrics, reasons (fail closed) and Pareto objectives.
#[allow(clippy::too_many_arguments)]
pub fn transient_case(
    filt: &FilterCase,
    plant: &CompressorPlant,
    plenum: &Plenum,
    ctrl: Controller,
    mats: &MaterialsView,
    design: &IntakeState,
    r0: f64,
    orbit_check_reasons: Option<&[String]>,
    window_s: f64,
    rtol: f64,
    method: Option<&str>,
) -> PyResult<(Value, Option<RunResult>)> {
    let tr = match TransientRun::new(filt, plant, plenum, ctrl, mats, design, r0, rtol, method) {
        Ok(t) => t,
        Err(e) if e.class == crate::PyClass::ValueError => {
            return Ok((
                Obj::new()
                    .s("status", status_from_reasons(&[R_DEADHEAD]))
                    .set("reasons", slist([R_DEADHEAD]))
                    .set("metrics", Value::Array(vec![]))
                    .set("summary", Value::Null)
                    .set("objectives", Value::Null)
                    .build(),
                None,
            ))
        }
        Err(e) => return Err(e),
    };
    let out = tr.run(&event_sequence(design, r0, window_s), 150, None)?;
    if !out.ok {
        return Ok((
            Obj::new()
                .s("status", ST_MODEL_ERROR)
                .set("reasons", slist([R_INTEGRATOR]))
                .set("metrics", Value::Array(vec![]))
                .set("summary", Value::Null)
                .set("objectives", Value::Null)
                .s("message", &out.message)
                .build(),
            Some(out),
        ));
    }
    let mut reasons: Vec<String> = vec![];
    if out.mass_residual_rel > MASS_TOL {
        reasons.push(R_CONSERVATION.into());
    }
    let mut metrics = vec![];
    let mut prev = r0;
    for sg in &out.segments {
        let m = segment_metrics(sg, prev);
        prev = mf(&m, "P_final_Pa").unwrap_or(f64::NAN);
        metrics.push(m);
    }
    for m in &metrics[1..] {
        if m["settling_time_s"].is_null() || m["flow_recovery_s"].is_null() {
            reasons.push(R_NOT_SETTLED.into());
        }
        if m["saturated_end"] == Value::Bool(true) {
            reasons.push(R_SATURATED.into());
        }
    }
    reasons.extend(domain_reasons(&out.segments).into_iter().map(String::from));
    if let Some(oc) = orbit_check_reasons {
        reasons.extend(oc.iter().cloned());
    }
    let reasons = sort_reasons(reasons);
    let chain = Chain { intake: design.clone(), filt: filt.clone(), plant: plant.clone(), plenum: plenum.clone() };
    let rip = pf::ripple_transfer(&chain, tr.a_ss, plant.shaft_hz())?;
    let op = pf::steady_operating_point(&chain, mats, r0, 1.0, 1.0)?;
    let reg = &metrics[1..];
    let mut settle: Vec<Option<f64>> = reg.iter().map(|m| mf(m, "settling_time_s")).collect();
    settle.extend(reg.iter().map(|m| mf(m, "flow_recovery_s")));
    let settle_max = if settle.iter().any(|x| x.is_none()) {
        Value::Null
    } else {
        fnum(pyops::py_max_iter(settle.iter().map(|x| x.expect("some"))).expect("non-empty"))
    };
    let peak = pyops::py_max_iter(reg.iter().filter_map(|m| mf(m, "peak_deviation_frac"))).unwrap_or(f64::NAN);
    let valve = pyops::py_sum(metrics.iter().map(|m| mf(m, "valve_travel").unwrap_or(f64::NAN)));
    let pel = op.get("compressor").and_then(|c| c.get("P_el_W")).cloned().unwrap_or(Value::Null);
    let obj = Obj::new()
        .f("V_m3", plenum.volume_m3)
        .f("valve_travel", valve)
        .set("settling_max_s", settle_max)
        .f("peak_deviation_max", peak)
        .set("ripple_transfer_shaft", rip["transfer_max"].clone())
        .set("P_compressor_el_W", pel)
        .build();
    let col = |k: &str, f: fn(Option<f64>, Option<f64>) -> Option<f64>| -> f64 {
        metrics.iter().map(|m| mf(m, k)).fold(None, f).unwrap_or(f64::NAN)
    };
    let minf = |a: Option<f64>, b: Option<f64>| match (a, b) {
        (None, x) => x,
        (Some(x), Some(y)) => Some(pyops::py_min(x, y)),
        (x, None) => x,
    };
    let maxf = |a: Option<f64>, b: Option<f64>| match (a, b) {
        (None, x) => x,
        (Some(x), Some(y)) => Some(pyops::py_max(x, y)),
        (x, None) => x,
    };
    let overshoot =
        pyops::py_max_iter(reg.iter().map(|m| mf(m, "overshoot_frac").filter(|v| *v != 0.0).unwrap_or(0.0)))
            .unwrap_or(f64::NAN);
    let mut summary = Obj::new()
        .f("P_min_Pa", col("P_min_Pa", minf))
        .f("P_max_Pa", col("P_max_Pa", maxf))
        .f("mdot_min_kgps", col("mdot_min_kgps", minf))
        .f("mdot_max_kgps", col("mdot_max_kgps", maxf))
        .f("xO_flow_min", col("xO_min", minf))
        .f("xO_flow_max", col("xO_max", maxf))
        .f("overshoot_max", overshoot)
        .f("mass_residual_rel", out.mass_residual_rel)
        .set("nfev", out.nfev)
        .f("a_eq_design_m2", tr.a_ss)
        .f("a_eq_max_m2", tr.a_max)
        .set("plenum_tau_s", Value::Array(vec![rip["tau_min_s"].clone(), rip["tau_max_s"].clone()]))
        .f("shaft_hz", plant.shaft_hz());
    let offered = op.get("offered").cloned().unwrap_or(Value::Null);
    if offered.is_object() {
        let mut s = 0.0;
        for sp in SPECIES {
            s += mf(&offered["x_s_plenum_mole"], sp).unwrap_or(f64::NAN) * m_of(sp);
        }
        let inv = r0 * plenum.volume_m3 / (K_B * plenum.t_k) * s;
        summary = summary
            .f("inventory_kg", inv)
            .f("ride_through_s", pyops::div(inv, mf(&offered, "mdot_total_kgps").unwrap_or(f64::NAN))?);
    }
    let rec = Obj::new()
        .s("status", status_from_reasons(&reasons))
        .set("reasons", slist(&reasons))
        .set("metrics", Value::Array(metrics))
        .set("summary", summary.build())
        .set("objectives", obj)
        .build();
    Ok((rec, Some(out)))
}

pub fn transient_framework() -> Value {
    let mut fw = crate::upstream::f4_transient_framework();
    let m: &mut Map<String, Value> = fw.as_object_mut().expect("object");
    m.insert("settling_band_frac".into(), fnum(SETTLE_BAND));
    m.insert("observation_window_s".into(), fnum(60.0));
    fw
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn settling_definition() {
        let t = [0.0, 1.0, 2.0, 3.0];
        assert_eq!(settling_time(&t, &[1.0, 1.0, 1.0, 1.0], 1.0, 0.02), Some(0.0));
        assert_eq!(settling_time(&t, &[2.0, 1.5, 1.01, 1.0], 1.0, 0.02), Some(2.0));
        assert_eq!(settling_time(&t, &[1.0, 1.0, 1.0, 1.5], 1.0, 0.02), None);
    }

    #[test]
    fn radau_integrates_a_stiff_linear_decay() {
        // y' = -1000 (y - 1): exact y = 1 - exp(-1000 t) from y0 = 0
        let (c, a) = radau_coeffs();
        let rhs = Rhs {
            v: 1.0,
            r0: 1.0,
            c: EventCoeffs {
                q0: [1000.0, 0.0, 0.0],
                k: [1000.0, 0.0, 0.0],
                q0g: [0.0; 3],
                dq: [0.0; 3],
                l0: [0.0; 3],
                dl: [0.0; 3],
            },
            g: [0.0; 3],
            cl: [0.0; 3],
            km: [1.0; 3],
            kr: 0.0,
            mr: 1.0,
            orbit: false,
            w: 0.0,
            amp: 0.0,
            d0: 1.0,
            rset: 1e30,
            kp: 1.0,
            ti: 1.0,
            tau: 1.0,
            uff: 1.0,
            ms: 1.0,
        };
        let mut integ = Integrator { rhs: &rhs, rtol: 1e-8, atol: 1e-12, nfev: 0, c, a };
        let te = [0.0, 1e-3, 5e-3, 1.0];
        let ys = integ.integrate([0.0; N], &te).unwrap();
        for (k, t) in te.iter().enumerate() {
            let exact = 1.0 - (-1000.0 * t).exp();
            assert!((ys[k][0] - exact).abs() < 1e-7, "t = {t}: {} vs {exact}", ys[k][0]);
        }
    }
}
