//! F4 plenum / feed transients (`abep_sim/design/plenum_feed.py` TransientRun and its metrics; contract
//! PARITY-C-ABEP_SIM_DESIGN_PLENUM_FEED_PY-V1, SOLVER_TOLERANCE class).
//!
//! The coupled chain under a normalized PI pressure controller (back-calculation anti-windup, first-order valve lag)
//! through a sequence of events, the integrator restarted at each event. States (scaled): p_s / r0 (O, N2, O2), valve
//! opening u, integral I, and three cumulative mass integrals for the conservation gate. The reference integrates with
//! scipy LSODA (BDF for its convergence reference); this port uses a Radau IIA order-5 method (simplified Newton on
//! the analytic Jacobian, step-doubling error estimate with local extrapolation, steps clamped to the output grid). The
//! valve command clip(u_cmd, 0, 1) makes the right-hand side only Lipschitz where u_cmd crosses 0 or 1: a step whose
//! end changes that saturation state is shortened (bisection) to end just past the switch, so no step integrates
//! across it (contract v4 RUST_DEFECT fix: without it the error control did not see the switch and the samples near
//! it kept an rtol-independent error up to ~6e-7). No accepted step damps a growing mode: where the Jacobian of the
//! dynamic block has an eigenvalue with Re lambda > 0, a step whose accepted update has linear amplification
//! |R_acc(h lambda)| < 1 is halved until it does not (contract v6 RUST_DEFECT fix: Radau IIA is damping for large
//! |h lambda| also in the right half-plane, the step-doubling estimate compares two equally damped solutions, and a
//! closed-loop instability started below the tolerance scale was integrated as a held setpoint). An integrator failure,
//! including a non-converged eigenvalue iteration of that guard, is R_INTEGRATOR (MODEL_ERROR), never a half-converged
//! trajectory (DIV-P-01).

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

    /// Branch of the valve-command clip at y: +1 (u_cmd > 1), -1 (u_cmd < 0), 0 (inside); the same tests as `ctrl`.
    fn sat_state(&self, y: &[f64; N]) -> i8 {
        let (_, ucmd, _, _) = self.ctrl(y[0] * self.r0 + y[1] * self.r0 + y[2] * self.r0, y[4]);
        if ucmd > 1.0 {
            1
        } else if ucmd < 0.0 {
            -1
        } else {
            0
        }
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

/// The system the integrator advances: right-hand side, analytic Jacobian and the valve-command saturation branch.
trait OdeSystem {
    fn f(&self, t: f64, y: &[f64; N]) -> [f64; N];
    fn jac(&self, y: &[f64; N]) -> [[f64; N]; N];
    fn sat_state(&self, y: &[f64; N]) -> i8;
}

impl OdeSystem for Rhs {
    fn f(&self, t: f64, y: &[f64; N]) -> [f64; N] {
        Rhs::f(self, t, y)
    }
    fn jac(&self, y: &[f64; N]) -> [[f64; N]; N] {
        Rhs::jac(self, y)
    }
    fn sat_state(&self, y: &[f64; N]) -> i8 {
        Rhs::sat_state(self, y)
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

// ------------------------------------------------------------------- growing-mode guard (contract v6 RUST_DEFECT fix)
/// The dynamic block of the state: scaled pressures (3), valve opening, integral. States 5..7 are cumulative integrals
/// whose Jacobian columns are zero, so the spectrum of the full Jacobian is that of this block plus three zeros.
const NM: usize = 5;

type Cx = (f64, f64);

fn cx_mul(a: Cx, b: Cx) -> Cx {
    (a.0 * b.0 - a.1 * b.1, a.0 * b.1 + a.1 * b.0)
}

fn cx_div(a: Cx, b: Cx) -> Cx {
    // Smith's algorithm (no overflow for |b| near the f64 range)
    if b.0.abs() >= b.1.abs() {
        let r = b.1 / b.0;
        let d = b.0 + b.1 * r;
        ((a.0 + a.1 * r) / d, (a.1 - a.0 * r) / d)
    } else {
        let r = b.0 / b.1;
        let d = b.0 * r + b.1;
        ((a.0 * r + a.1) / d, (a.1 * r - a.0) / d)
    }
}

/// Stability function of the 3-stage Radau IIA method (order 5): R(z) = (1 + 2z/5 + z^2/20) / (1 - 3z/5 + 3z^2/20 -
/// z^3/60) (Hairer & Wanner, Solving ODEs II, sec. IV.5), i.e. 1 + z b^T (I - z A)^-1 1 for the coefficients of
/// `radau_coeffs` (checked by a unit test).
fn radau_r(z: Cx) -> Cx {
    let z2 = cx_mul(z, z);
    let z3 = cx_mul(z2, z);
    let num = (1.0 + 0.4 * z.0 + z2.0 / 20.0, 0.4 * z.1 + z2.1 / 20.0);
    let den = (1.0 - 0.6 * z.0 + 0.15 * z2.0 - z3.0 / 60.0, -0.6 * z.1 + 0.15 * z2.1 - z3.1 / 60.0);
    cx_div(num, den)
}

/// Linear amplification of one accepted step (`Integrator::trial`: two half steps, one full step, local
/// extrapolation (32 y2 - y1) / 31) on the mode y' = lambda y, z = h lambda: (32 R(z/2)^2 - R(z)) / 31.
fn accepted_amplification(z: Cx) -> Cx {
    let rh = radau_r((0.5 * z.0, 0.5 * z.1));
    let rh2 = cx_mul(rh, rh);
    let r = radau_r(z);
    ((32.0 * rh2.0 - r.0) / 31.0, (32.0 * rh2.1 - r.1) / 31.0)
}

/// True when a step of size h damps the growing mode lambda (Re lambda > 0): |R_acc(h lambda)| < 1 while the exact
/// flow grows by |exp(h lambda)| > 1.
fn damps_growing_mode(h: f64, lam: Cx) -> bool {
    let a = accepted_amplification((h * lam.0, h * lam.1));
    a.0.hypot(a.1) < 1.0
}

/// Eigenvalues (re, im) of a real NM x NM matrix: balancing by exact powers of 2, reduction to upper Hessenberg form by
/// stabilised elimination and the Francis double-shift QR iteration (the EISPACK balanc / elmhes / hqr algorithms as
/// given in Numerical Recipes, 2nd ed., sec. 11.5-11.6). None when an entry is not finite or the QR iteration does not
/// converge within 30 iterations for an eigenvalue (fail closed: the caller reports R_INTEGRATOR).
#[allow(unused_assignments)] // the QR sweep carries its scalars between iterations (hqr)
fn eig_real(m: &[[f64; NM]; NM]) -> Option<[Cx; NM]> {
    const RADIX: f64 = 2.0;
    let n = NM;
    // 1-based working copy
    let mut a = [[0.0f64; NM + 1]; NM + 1];
    for i in 0..n {
        for j in 0..n {
            if !m[i][j].is_finite() {
                return None;
            }
            a[i + 1][j + 1] = m[i][j];
        }
    }
    // balanc (similarity by powers of the radix: exact in floating point)
    let sqrdx = RADIX * RADIX;
    let mut last = false;
    let mut passes = 0;
    while !last {
        passes += 1;
        if passes > 1000 {
            return None;
        }
        last = true;
        for i in 1..=n {
            let (mut r, mut c) = (0.0f64, 0.0f64);
            for j in 1..=n {
                if j != i {
                    c += a[j][i].abs();
                    r += a[i][j].abs();
                }
            }
            if c != 0.0 && r != 0.0 {
                let mut g = r / RADIX;
                let mut f = 1.0;
                let s = c + r;
                while c < g {
                    f *= RADIX;
                    c *= sqrdx;
                }
                g = r * RADIX;
                while c > g {
                    f /= RADIX;
                    c /= sqrdx;
                }
                if (c + r) / f < 0.95 * s {
                    last = false;
                    let g = 1.0 / f;
                    for j in 1..=n {
                        a[i][j] *= g;
                    }
                    for j in 1..=n {
                        a[j][i] *= f;
                    }
                }
            }
        }
    }
    // elmhes
    for mm in 2..n {
        let mut x = 0.0f64;
        let mut i = mm;
        for j in mm..=n {
            if a[j][mm - 1].abs() > x.abs() {
                x = a[j][mm - 1];
                i = j;
            }
        }
        if i != mm {
            for j in (mm - 1)..=n {
                let t = a[i][j];
                a[i][j] = a[mm][j];
                a[mm][j] = t;
            }
            for row in a.iter_mut().skip(1) {
                row.swap(i, mm);
            }
        }
        if x != 0.0 {
            for i in (mm + 1)..=n {
                let mut y = a[i][mm - 1];
                if y != 0.0 {
                    y /= x;
                    a[i][mm - 1] = y;
                    for j in mm..=n {
                        a[i][j] -= y * a[mm][j];
                    }
                    for j in 1..=n {
                        a[j][mm] += y * a[j][i];
                    }
                }
            }
        }
    }
    for i in 1..=n {
        for j in 1..=n {
            if i > j + 1 {
                a[i][j] = 0.0;
            }
        }
    }
    // hqr
    let mut wr = [0.0f64; NM + 1];
    let mut wi = [0.0f64; NM + 1];
    let mut anorm = 0.0f64;
    for i in 1..=n {
        for j in i.max(2) - 1..=n {
            anorm += a[i][j].abs();
        }
    }
    let mut nn = n;
    let mut t = 0.0f64;
    let (mut p, mut q, mut r, mut s, mut w, mut x, mut y, mut z) = (0.0f64, 0.0f64, 0.0f64, 0.0f64, 0.0, 0.0, 0.0, 0.0);
    while nn >= 1 {
        let mut its = 0;
        loop {
            let mut l = nn;
            while l >= 2 {
                s = a[l - 1][l - 1].abs() + a[l][l].abs();
                if s == 0.0 {
                    s = anorm;
                }
                if a[l][l - 1].abs() + s == s {
                    a[l][l - 1] = 0.0;
                    break;
                }
                l -= 1;
            }
            x = a[nn][nn];
            if l == nn {
                wr[nn] = x + t;
                wi[nn] = 0.0;
                nn -= 1;
            } else {
                y = a[nn - 1][nn - 1];
                w = a[nn][nn - 1] * a[nn - 1][nn];
                if l == nn - 1 {
                    p = 0.5 * (y - x);
                    q = p * p + w;
                    z = q.abs().sqrt();
                    x += t;
                    if q >= 0.0 {
                        z = p + if p >= 0.0 { z.abs() } else { -z.abs() };
                        wr[nn - 1] = x + z;
                        wr[nn] = x + z;
                        if z != 0.0 {
                            wr[nn] = x - w / z;
                        }
                        wi[nn - 1] = 0.0;
                        wi[nn] = 0.0;
                    } else {
                        wr[nn - 1] = x + p;
                        wr[nn] = x + p;
                        wi[nn - 1] = -z;
                        wi[nn] = z;
                    }
                    nn -= 2;
                } else {
                    if its == 30 {
                        return None;
                    }
                    if its == 10 || its == 20 {
                        t += x;
                        for i in 1..=nn {
                            a[i][i] -= x;
                        }
                        s = a[nn][nn - 1].abs() + a[nn - 1][nn - 2].abs();
                        x = 0.75 * s;
                        y = x;
                        w = -0.4375 * s * s;
                    }
                    its += 1;
                    let mut mm = nn - 2;
                    loop {
                        z = a[mm][mm];
                        r = x - z;
                        s = y - z;
                        p = (r * s - w) / a[mm + 1][mm] + a[mm][mm + 1];
                        q = a[mm + 1][mm + 1] - z - r - s;
                        r = a[mm + 2][mm + 1];
                        s = p.abs() + q.abs() + r.abs();
                        p /= s;
                        q /= s;
                        r /= s;
                        if mm == l {
                            break;
                        }
                        let u = a[mm][mm - 1].abs() * (q.abs() + r.abs());
                        let v = p.abs() * (a[mm - 1][mm - 1].abs() + z.abs() + a[mm + 1][mm + 1].abs());
                        if u + v == v {
                            break;
                        }
                        mm -= 1;
                    }
                    for i in (mm + 2)..=nn {
                        a[i][i - 2] = 0.0;
                        if i != mm + 2 {
                            a[i][i - 3] = 0.0;
                        }
                    }
                    let mut k = mm;
                    while k < nn {
                        if k != mm {
                            p = a[k][k - 1];
                            q = a[k + 1][k - 1];
                            r = 0.0;
                            if k != nn - 1 {
                                r = a[k + 2][k - 1];
                            }
                            x = p.abs() + q.abs() + r.abs();
                            if x != 0.0 {
                                p /= x;
                                q /= x;
                                r /= x;
                            }
                        }
                        let sq = (p * p + q * q + r * r).sqrt();
                        s = if p >= 0.0 { sq } else { -sq };
                        if s != 0.0 {
                            if k == mm {
                                if l != mm {
                                    a[k][k - 1] = -a[k][k - 1];
                                }
                            } else {
                                a[k][k - 1] = -s * x;
                            }
                            p += s;
                            x = p / s;
                            y = q / s;
                            z = r / s;
                            q /= p;
                            r /= p;
                            for j in k..=nn {
                                p = a[k][j] + q * a[k + 1][j];
                                if k != nn - 1 {
                                    p += r * a[k + 2][j];
                                    a[k + 2][j] -= p * z;
                                }
                                a[k + 1][j] -= p * y;
                                a[k][j] -= p * x;
                            }
                            let mmin = if nn < k + 3 { nn } else { k + 3 };
                            for i in l..=mmin {
                                p = x * a[i][k] + y * a[i][k + 1];
                                if k != nn - 1 {
                                    p += z * a[i][k + 2];
                                    a[i][k + 2] -= p * r;
                                }
                                a[i][k + 1] -= p * q;
                                a[i][k] -= p;
                            }
                        }
                        k += 1;
                    }
                }
            }
            if nn < 2 || l + 1 >= nn {
                break;
            }
        }
    }
    let mut out = [(0.0, 0.0); NM];
    for i in 0..n {
        if !(wr[i + 1].is_finite() && wi[i + 1].is_finite()) {
            return None;
        }
        out[i] = (wr[i + 1], wi[i + 1]);
    }
    Some(out)
}

/// The growing modes (Re lambda > 0) of the dynamic block of the Jacobian at y; Err when the eigenvalue iteration fails.
fn growing_modes<S: OdeSystem>(rhs: &S, y: &[f64; N], t: f64) -> Result<Vec<Cx>, String> {
    let j = rhs.jac(y);
    let mut b = [[0.0; NM]; NM];
    for i in 0..NM {
        b[i].copy_from_slice(&j[i][..NM]);
    }
    let ev =
        eig_real(&b).ok_or_else(|| format!("growing-mode guard: eigenvalue iteration did not converge at t = {t}"))?;
    Ok(ev.iter().copied().filter(|l| l.0 > 0.0).collect())
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

struct Integrator<'a, S: OdeSystem> {
    rhs: &'a S,
    rtol: f64,
    atol: f64,
    nfev: usize,
    c: [f64; 3],
    a: [[f64; 3]; 3],
    /// step halvings by the growing-mode guard (diagnostic; not part of any record)
    n_guard: usize,
}

impl<S: OdeSystem> Integrator<'_, S> {
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

    /// One error-controlled trial of size hh from (t, y): the step-doubling solution with local extrapolation and its
    /// scaled RMS error norm; None when a Newton iteration fails.
    fn trial(&mut self, t: f64, y: &[f64; N], hh: f64) -> Option<([f64; N], f64)> {
        let y1 = self.step(t, y, hh)?;
        let ya = self.step(t, y, hh / 2.0)?;
        let y2 = self.step(t + hh / 2.0, &ya, hh / 2.0)?;
        let mut en = 0.0;
        let mut out = y2;
        for k in 0..N {
            let err = (y2[k] - y1[k]) / 31.0;
            let sc = self.atol + self.rtol * y[k].abs().max(y2[k].abs());
            en += (err / sc).powi(2);
            out[k] = y2[k] + err;
        }
        Some((out, (en / N as f64).sqrt()))
    }

    /// Integrate from t0 = 0 over the output grid `te` (te[0] = 0, increasing); Err when the step size collapses.
    /// An accepted step never crosses a switch of the valve-command saturation state: the step is bisected to the
    /// shortest one whose end has left the start state, which then ends within rounding of the switch.
    fn integrate(&mut self, y0: [f64; N], te: &[f64]) -> Result<Vec<[f64; N]>, String> {
        let mut out = vec![y0];
        let span = te[te.len() - 1];
        let h_min = 1e-14 * span.max(1e-300);
        let mut t = 0.0;
        let mut y = y0;
        let mut h = if te.len() > 1 { te[1] } else { span };
        let mut steps = 0usize;
        let mut modes = growing_modes(self.rhs, &y, t)?;
        for &t_out in &te[1..] {
            let mut to_switch = false;
            while t < t_out {
                steps += 1;
                if steps > 2_000_000 {
                    return Err("step limit".into());
                }
                let mut hh = h.min(t_out - t);
                // growing-mode guard: no accepted step damps a mode the linearised flow grows
                while hh >= h_min && modes.iter().any(|&l| damps_growing_mode(hh, l)) {
                    hh *= 0.5;
                    to_switch = false;
                    self.n_guard += 1;
                }
                if hh < h_min {
                    return Err(format!("step size collapsed at t = {t}"));
                }
                let Some((y_new, en)) = self.trial(t, &y, hh) else {
                    h = hh * 0.25;
                    to_switch = false;
                    continue;
                };
                if !en.is_finite() {
                    h = hh * 0.25;
                    to_switch = false;
                    continue;
                }
                let fac = if en == 0.0 { 4.0 } else { (0.9 * en.powf(-1.0 / 6.0)).clamp(0.2, 4.0) };
                if !(en <= 1.0) {
                    h = hh * fac.min(0.9);
                    to_switch = false;
                    continue;
                }
                let s0 = self.rhs.sat_state(&y);
                if !to_switch && self.rhs.sat_state(&y_new) != s0 {
                    let (mut lo, mut hi) = (0.0, hh);
                    loop {
                        let mid = 0.5 * (lo + hi);
                        if !(lo < mid && mid < hi) {
                            break;
                        }
                        match self.trial(t, &y, mid) {
                            Some((ym, _)) if self.rhs.sat_state(&ym) == s0 => lo = mid,
                            _ => hi = mid,
                        }
                    }
                    // a switch within rounding of the step start is already behind it: the step is accepted
                    if hi < hh && hi >= h_min && t + hi > t {
                        h = hi;
                        to_switch = true;
                        continue;
                    }
                }
                to_switch = false;
                t = if hh == t_out - t { t_out } else { t + hh };
                y = y_new;
                modes = growing_modes(self.rhs, &y, t)?;
                // keep the proposed step when the output point clamped it
                h = if hh < h { h.max(hh * fac) } else { hh * fac };
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

    /// Contract v7 stability class, one equilibrium: the equilibrium of event `ev` at free-stream density `density`
    /// (the event's own density for a constant event; one quasi-static phase for an orbit event) and the spectrum of
    /// the dynamic 5 x 5 block of the Jacobian there. Kinds: "CLOSING" (no unsaturated equilibrium: area_for_pressure
    /// is not ok, the setpoint is at or above the dead-head pressure and the valve closes), "SAT_OPEN" (the
    /// equilibrium opening u = A_eq / (A_max feed_factor) exceeds 1), "UNSAT" (u <= 1; the eigenvalues are returned).
    /// Fail closed: a non-converged eigenvalue iteration is an error, never a silent class.
    pub fn event_equilibrium(&self, ev: &Event, density: f64) -> PyResult<(&'static str, Vec<(f64, f64)>)> {
        let co = self.chain(&ev.intake).node_coefficients(density)?;
        let sol = area_for_pressure(&co, ev.setpoint_pa, self.k_rec, &self.leak, &self.fc, true)?;
        if !sol.ok {
            return Ok(("CLOSING", vec![]));
        }
        let u = sol.a_eq / (self.a_max * ev.feed_factor);
        if u > 1.0 {
            return Ok(("SAT_OPEN", vec![]));
        }
        let (p3, _) = solve_pressures(&co, sol.a_eq, self.k_rec, &self.leak, &self.fc, true)?;
        let i_int = (u / self.u_ff - 1.0) * self.ctrl.ti_s / self.ctrl.kp;
        let y = [p3[0] / self.r0, p3[1] / self.r0, p3[2] / self.r0, u, i_int, 0.0, 0.0, 0.0];
        let j = self.make(ev)?.jac(&y);
        let mut b = [[0.0; NM]; NM];
        for (bi, ji) in b.iter_mut().zip(j.iter()) {
            bi.copy_from_slice(&ji[..NM]);
        }
        let lam = eig_real(&b).ok_or_else(|| {
            crate::GasPathError::new(
                crate::PyClass::RuntimeError,
                "stability class: eigenvalue iteration did not converge",
            )
        })?;
        Ok(("UNSAT", lam.to_vec()))
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
            let mut integ = Integrator { rhs: &rhs, rtol: self.rtol, atol: ATOL_SCALED, nfev: 0, c, a, n_guard: 0 };
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

    /// x' = a x - b y, y' = b x + a y in states 0 / 1 (eigenvalues a +/- i b, the closed-form flow a rotation scaled by
    /// exp(a t)); state 2 is held at 1 (an O(1) state like the scaled pressures); the rest stay 0; no command switch.
    struct LinOsc {
        a: f64,
        b: f64,
    }

    impl OdeSystem for LinOsc {
        fn f(&self, _t: f64, y: &[f64; N]) -> [f64; N] {
            let mut d = [0.0; N];
            d[0] = self.a * y[0] - self.b * y[1];
            d[1] = self.b * y[0] + self.a * y[1];
            d
        }
        fn jac(&self, _y: &[f64; N]) -> [[f64; N]; N] {
            let mut j = [[0.0; N]; N];
            j[0][0] = self.a;
            j[0][1] = -self.b;
            j[1][0] = self.b;
            j[1][1] = self.a;
            j
        }
        fn sat_state(&self, _y: &[f64; N]) -> i8 {
            0
        }
    }

    /// The orbit output grid of R45-192 (orbital period 5319 s, 150 geometric samples) and the nominal tolerances.
    fn osc_run(a: f64, x0: f64) -> (Vec<f64>, Vec<[f64; N]>, usize, usize) {
        let (c, aa) = radau_coeffs();
        let sys = LinOsc { a, b: 2.4 };
        let te = TransientRun::t_eval(5319.0, 150);
        let mut integ = Integrator { rhs: &sys, rtol: RTOL, atol: ATOL_SCALED, nfev: 0, c, a: aa, n_guard: 0 };
        let ys = integ.integrate([x0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], &te).expect("integrates");
        (te, ys, integ.nfev, integ.n_guard)
    }

    /// The unstable closed loop of R45-192 in miniature: lambda = 0.05 +/- 2.4i, started below the absolute tolerance
    /// (as a steady start excited only by the slow orbit forcing). Before the guard (commit 3eeb574) every sample after
    /// the first few decays: the amplitude ends at 1.3e-137 (exact 3.2e102) in 1647 evaluations. With the guard no
    /// accepted step damps the mode, so the sampled amplitude never decreases, and once the mode is above the tolerance
    /// scale the error control reproduces its growth rate (measured 2.9e-5 relative). Below the tolerance scale the
    /// amplitude carries no accuracy guarantee (absolute tolerance), so the onset is not compared to the exact flow.
    #[test]
    fn growing_mode_guard_resolves_an_unstable_oscillator() {
        let (te, ys, _nfev, n_guard) = osc_run(0.05, 1e-13);
        let r: Vec<f64> = ys.iter().map(|y| y[0].hypot(y[1])).collect();
        for k in 1..r.len() {
            assert!(
                r[k] >= r[k - 1],
                "growing mode damped between t = {} and {}: {:e} -> {:e}",
                te[k - 1],
                te[k],
                r[k - 1],
                r[k]
            );
        }
        let n = te.len() - 1;
        let k0 = te.iter().position(|&t| t >= 2.0 * te[n] / 3.0).expect("grid");
        let rate = (r[n].ln() - r[k0].ln()) / (te[n] - te[k0]);
        assert!((rate / 0.05 - 1.0).abs() <= 1e-3, "late growth rate {rate:e} vs 0.05");
        assert!(r[n] > 1.0, "the instability must develop over the orbit: final amplitude {:e}", r[n]);
        assert!(n_guard > 0, "the guard must act on a growing mode");
    }

    /// Stable control (lambda = -0.05 +/- 2.4i, same grid and tolerances): the guard never acts and the trajectory is
    /// bit-identical to the integrator before the guard (FNV-1a of every sampled state and nfev recorded at 3eeb574).
    #[test]
    fn growing_mode_guard_leaves_a_stable_oscillator_unchanged() {
        let (_te, ys, nfev, n_guard) = osc_run(-0.05, 1.0);
        assert_eq!(n_guard, 0);
        assert_eq!(nfev, 14433);
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        for y in &ys {
            for v in y {
                for byte in v.to_bits().to_le_bytes() {
                    h ^= byte as u64;
                    h = h.wrapping_mul(0x0000_0100_0000_01b3);
                }
            }
        }
        assert_eq!(ys.len(), 151);
        assert_eq!(format!("{h:016x}"), "64e8b0492b170e0c");
    }

    /// R(z) in closed form equals 1 + z b^T (I - z A)^-1 1 for the coefficients the integrator uses (b = last row of A,
    /// stiffly accurate), on points of both half-planes.
    #[test]
    fn radau_stability_function_matches_the_coefficients() {
        let (_c, a) = radau_coeffs();
        for z in [(0.3, 0.2), (1.0, 2.4), (-3.0, 7.0), (5.0, -1.0), (60.0, 290.0), (-0.01, 0.0)] {
            // (I - z A) x = 1 by complex Gaussian elimination (3 x 3, no pivoting needed for these z)
            let mut m = [[(0.0, 0.0); 4]; 3];
            for i in 0..3 {
                for j in 0..3 {
                    let za = (z.0 * a[i][j], z.1 * a[i][j]);
                    m[i][j] = (if i == j { 1.0 } else { 0.0 } - za.0, -za.1);
                }
                m[i][3] = (1.0, 0.0);
            }
            for k in 0..3 {
                for i in k + 1..3 {
                    let f = cx_div(m[i][k], m[k][k]);
                    for j in k..4 {
                        let fm = cx_mul(f, m[k][j]);
                        m[i][j] = (m[i][j].0 - fm.0, m[i][j].1 - fm.1);
                    }
                }
            }
            let mut x = [(0.0, 0.0); 3];
            for i in (0..3).rev() {
                let mut acc = m[i][3];
                for j in i + 1..3 {
                    let t = cx_mul(m[i][j], x[j]);
                    acc = (acc.0 - t.0, acc.1 - t.1);
                }
                x[i] = cx_div(acc, m[i][i]);
            }
            let mut bx = (0.0, 0.0);
            for j in 0..3 {
                bx = (bx.0 + a[2][j] * x[j].0, bx.1 + a[2][j] * x[j].1);
            }
            let zbx = cx_mul(z, bx);
            let want = (1.0 + zbx.0, zbx.1);
            let got = radau_r(z);
            let err = (got.0 - want.0).hypot(got.1 - want.1);
            assert!(err <= 1e-13 * (1.0 + want.0.hypot(want.1)), "z = {z:?}: {got:?} vs {want:?}");
        }
        // the defect on the R45-192 growing mode: one Radau step damps it for h >= 1.26 s, the accepted step-doubling
        // update (the map the integrator applies) for h >= 2.63 s; the nominal run reached 471 s steps
        let lam = (0.0508, 2.423);
        let r13 = radau_r((1.3 * lam.0, 1.3 * lam.1));
        assert!(r13.0.hypot(r13.1) < 1.0);
        for h in [3.0, 36.0, 471.0] {
            assert!(damps_growing_mode(h, lam), "h = {h}");
        }
        for h in [0.01, 1.3, 2.0] {
            assert!(!damps_growing_mode(h, lam), "h = {h}");
        }
    }

    fn assert_spectrum(m: &[[f64; NM]; NM], want: &[Cx; NM]) {
        let got = eig_real(m).expect("converges");
        let mut used = [false; NM];
        for w in want {
            let (k, d) = got
                .iter()
                .enumerate()
                .filter(|(k, _)| !used[*k])
                .map(|(k, g)| (k, (g.0 - w.0).hypot(g.1 - w.1)))
                .fold((NM, f64::INFINITY), |b, x| if x.1 < b.1 { x } else { b });
            assert!(d <= 1e-9 * (1.0 + w.0.hypot(w.1)), "eigenvalue {w:?} not found in {got:?}");
            used[k] = true;
        }
    }

    #[test]
    fn eig_real_reproduces_known_spectra() {
        // companion matrix of prod (x - lambda_k), lambda = 0.0508 +/- 2.423i, -0.09575, -0.1159, -6.487 (the
        // R45-192 steady-start spectrum of the reference Jacobian, numpy)
        let want = [(0.0508, 2.423), (0.0508, -2.423), (-0.09575, 0.0), (-0.1159, 0.0), (-6.487, 0.0)];
        let mut poly = vec![(1.0, 0.0)];
        for l in want {
            let mut next = vec![(0.0, 0.0); poly.len() + 1];
            for (k, c) in poly.iter().enumerate() {
                next[k] = (next[k].0 + c.0, next[k].1 + c.1);
                let t = cx_mul(*c, l);
                next[k + 1] = (next[k + 1].0 - t.0, next[k + 1].1 - t.1);
            }
            poly = next;
        }
        let mut m = [[0.0; NM]; NM];
        for j in 0..NM {
            m[0][j] = -poly[j + 1].0;
        }
        for i in 1..NM {
            m[i][i - 1] = 1.0;
        }
        assert_spectrum(&m, &want);
        // a badly scaled triangular-plus-rotation block (balancing exercised)
        let mut t = [[0.0; NM]; NM];
        t[0][0] = 0.05;
        t[0][1] = -2.4e4;
        t[1][0] = 2.4e-4;
        t[1][1] = 0.05;
        t[2][2] = -270.3;
        t[3][3] = -1e-3;
        t[4][4] = 7.0;
        t[0][4] = 1e6;
        t[2][3] = -3e-5;
        assert_spectrum(&t, &[(0.05, 2.4), (0.05, -2.4), (-270.3, 0.0), (-1e-3, 0.0), (7.0, 0.0)]);
        // the zero matrix (a fully saturated, frozen block)
        assert_spectrum(&[[0.0; NM]; NM], &[(0.0, 0.0); NM]);
    }

    #[test]
    fn eig_real_fails_closed_on_non_finite_entries() {
        let mut m = [[0.0; NM]; NM];
        m[2][3] = f64::NAN;
        assert!(eig_real(&m).is_none());
        m[2][3] = f64::INFINITY;
        assert!(eig_real(&m).is_none());
    }

    #[test]
    fn settling_definition() {
        let t = [0.0, 1.0, 2.0, 3.0];
        assert_eq!(settling_time(&t, &[1.0, 1.0, 1.0, 1.0], 1.0, 0.02), Some(0.0));
        assert_eq!(settling_time(&t, &[2.0, 1.5, 1.01, 1.0], 1.0, 0.02), Some(2.0));
        assert_eq!(settling_time(&t, &[1.0, 1.0, 1.0, 1.5], 1.0, 0.02), None);
    }

    /// A plenum frozen at eps = 0.1: the unsaturated valve command u_cmd = 0.6 + 0.1 t crosses 1 at t* = 4 s and
    /// stays saturated (u_cmd' = 1.1 - u_cmd > 0 there); u is a first-order lag of clip(u_cmd, 0, 1), so
    /// u(t) = a + b (t - tau) + (u0 - a + b tau) exp(-t / tau) before t* and 1 + (u(t*) - 1) exp(-(t - t*) / tau) after.
    #[test]
    fn radau_resolves_the_valve_command_saturation_switch() {
        let (c, a) = radau_coeffs();
        let rhs = Rhs {
            v: 1.0,
            r0: 1.0,
            c: EventCoeffs { q0: [0.0; 3], k: [0.0; 3], q0g: [0.0; 3], dq: [0.0; 3], l0: [0.0; 3], dl: [0.0; 3] },
            g: [0.0; 3],
            cl: [0.0; 3],
            km: [1.0; 3],
            kr: 0.0,
            mr: 1.0,
            orbit: false,
            w: 0.0,
            amp: 0.0,
            d0: 1.0,
            rset: 1.0,
            kp: 2.0,
            ti: 1.0,
            tau: 0.5,
            uff: 0.5,
            ms: 1.0,
        };
        let (ua, ub, tau, ts, u0) = (0.6, 0.1, 0.5, 4.0, 0.6);
        let u_lin = |t: f64| ua + ub * (t - tau) + (u0 - ua + ub * tau) * (-t / tau).exp();
        let exact = |t: f64| if t <= ts { u_lin(t) } else { 1.0 + (u_lin(ts) - 1.0) * (-(t - ts) / tau).exp() };
        let te = [0.0, 0.7, 1.9, 3.3, 4.6, 6.1, 8.0, 10.0];
        for rtol in [1e-6, 1e-10] {
            let mut integ = Integrator { rhs: &rhs, rtol, atol: 1e-12, nfev: 0, c, a, n_guard: 0 };
            let ys = integ.integrate([1.1, 0.0, 0.0, u0, 0.0, 0.0, 0.0, 0.0], &te).unwrap();
            for (k, t) in te.iter().enumerate() {
                let e = (ys[k][3] - exact(*t)).abs();
                // before the fix: 3.4e-6 (rtol 1e-6) and 6.4e-10 (rtol 1e-10) at t = 4.6 s, after the switch
                assert!(e <= rtol, "rtol {rtol:e}, t = {t}: |u - exact| = {e:e}");
            }
        }
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
        let mut integ = Integrator { rhs: &rhs, rtol: 1e-8, atol: 1e-12, nfev: 0, c, a, n_guard: 0 };
        let te = [0.0, 1e-3, 5e-3, 1.0];
        let ys = integ.integrate([0.0; N], &te).unwrap();
        for (k, t) in te.iter().enumerate() {
            let exact = 1.0 - (-1000.0 * t).exp();
            assert!((ys[k][0] - exact).abs() < 1e-7, "t = {t}: {} vs {exact}", ys[k][0]);
        }
    }
}
