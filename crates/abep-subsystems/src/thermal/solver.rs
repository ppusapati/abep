//! Solvers: steady Newton-Raphson (E-10, NUM-01), implicit Euler on the enthalpy form with step doubling (E-11,
//! NUM-03, NUM-04, CONS-T1, CONS-T2), periodic orbits (E-12, NUM-05, CONS-T3) and orbit-average steady states.
//! Iterates stay inside every node's admissible property range (D-01: no extrapolation, no clamping of a property);
//! a Newton direction blocked at a range end is reported as OUT_OF_DOMAIN.

use super::assemble::{Compiled, Range};
use super::linalg::Lu;
use super::network::{evaluate, Accounting, End, Eval, EvalError, Factors, LinkKind, Net, SIGMA};

pub const NUM01_MAX_DT_K: f64 = 1e-8;
pub const NUM01_CAP: usize = 100;
pub const NUM03_MAX_DT_K: f64 = 1e-9;
pub const NUM03_CAP: usize = 50;
pub const NUM04_HALVING_CAP: u32 = 20;
pub const NUM05_ORBIT_CAP: usize = 200;
pub const CONS_S_REL: f64 = 1e-9;
pub const CONS_S_ABS_W: f64 = 1e-9;
pub const CONS_T1_REL: f64 = 1e-8;
pub const CONS_T1_ABS_J: f64 = 1e-6;
pub const CONS_T2_K: f64 = 1e-2;
pub const CONS_T3_K: f64 = 1e-3;

/// A solve that ends without a converged state.
#[derive(Debug, Clone, PartialEq)]
pub enum Fail {
    /// OUT_OF_DOMAIN: a property or relation would be used outside its range (D-01).
    Domain { subject: String, record_id: String, t_k: f64, range: [f64; 2], detail: String },
    /// MODEL_ERROR: cap reached, singular system, non-physical property value, conservation criterion not met.
    Model { code: String, subject: String, detail: String },
}

fn model(code: &str, subject: &str, detail: impl Into<String>) -> Fail {
    Fail::Model { code: code.into(), subject: subject.into(), detail: detail.into() }
}

fn from_eval(e: EvalError) -> Fail {
    match e {
        EvalError::Domain { violation, subject } => Fail::Domain {
            subject,
            record_id: violation.record_id,
            t_k: violation.t_k,
            range: [violation.t_min_k, violation.t_max_k],
            detail: "property evaluated outside its validity range (D-01)".into(),
        },
        EvalError::Nonphysical(d) => model("PROPERTY_VALUE_NOT_PHYSICAL", "property", d),
        EvalError::Singular(d) => model("SINGULAR_SYSTEM", "solver", d),
    }
}

#[derive(Debug, Clone)]
pub struct State {
    pub t: Vec<f64>,
    pub ev: Eval,
    pub acc: Accounting,
}

#[derive(Debug, Clone)]
pub struct SteadyOut {
    pub state: State,
    pub iterations: usize,
    pub last_dt: f64,
    pub cons_tol: f64,
}

#[derive(Debug, Clone, Default)]
pub struct EnergyTrack {
    /// Worst per-step |dH - h Q_net| and its CONS-T1 bound (largest residual / bound ratio).
    pub worst_step: (f64, f64),
    /// Worst cumulative residual and bound over all accepted steps.
    pub worst_cumulative: (f64, f64),
    pub final_cumulative: (f64, f64),
    dh_q_sum: f64,
    abs_sum: f64,
}

#[derive(Debug, Clone)]
pub struct OrbitRaw {
    pub min: Vec<f64>,
    pub max: Vec<f64>,
    pub mean: Vec<f64>,
}

#[derive(Debug, Clone)]
pub struct TransientOut {
    pub times: Vec<f64>,
    pub temps: Vec<Vec<f64>>,
    pub final_state: State,
    pub final_time: f64,
    pub dh_node: Vec<f64>,
    pub u_num: f64,
    pub max_iters: usize,
    pub max_depth: u32,
    pub steps: usize,
    pub energy: EnergyTrack,
    pub orbits: Option<(usize, f64, Vec<OrbitRaw>)>,
    /// Max over accepted states of the linear conductance sum per node (D-02 / D-09).
    pub g_lin_max: Vec<f64>,
    pub states_for_biot: Vec<Vec<f64>>,
}

fn l2(x: &[f64]) -> f64 {
    x.iter().map(|v| v * v).sum::<f64>().sqrt()
}

fn max_abs_diff(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(x, y)| (x - y).abs()).fold(0.0, f64::max)
}

fn blocked(net: &Net, ranges: &[Range], i: usize, hi: bool, t: f64) -> Fail {
    let r = &ranges[i];
    let (rec, bound) = if hi { (&r.hi_rec, r.hi) } else { (&r.lo_rec, r.lo) };
    Fail::Domain {
        subject: net.ids[i].clone(),
        record_id: rec.clone(),
        t_k: t,
        range: [r.lo, r.hi],
        detail: format!(
            "the Newton direction leaves the admissible range at its {} end {bound} K; no state inside the registered \
             property ranges solves the balance from this iterate (relation domain bound reached)",
            if hi { "upper" } else { "lower" }
        ),
    }
}

/// Largest step fraction in (0, 1] that keeps `t + lam d` inside the ranges; `Err((i, hi))` when node i sits on a
/// range end and the direction points outward.
fn fraction_to_boundary(t: &[f64], d: &[f64], ranges: &[Range]) -> Result<f64, (usize, bool)> {
    let mut lam: f64 = 1.0;
    for i in 0..t.len() {
        if d[i] > 0.0 {
            let room = ranges[i].hi - t[i];
            if room <= 0.0 {
                return Err((i, true));
            }
            lam = lam.min(room / d[i]);
        } else if d[i] < 0.0 {
            let room = t[i] - ranges[i].lo;
            if room <= 0.0 {
                return Err((i, false));
            }
            lam = lam.min(room / -d[i]);
        }
    }
    Ok(lam)
}

fn apply(t: &[f64], d: &[f64], lam: f64, ranges: &[Range]) -> Vec<f64> {
    t.iter().zip(d).zip(ranges).map(|((x, dx), r)| (x + lam * dx).clamp(r.lo, r.hi)).collect()
}

fn check_inside(net: &Net, t: &[f64], ranges: &[Range]) -> Result<(), Fail> {
    for (i, r) in ranges.iter().enumerate() {
        if r.lo > r.hi {
            return Err(Fail::Domain {
                subject: net.ids[i].clone(),
                record_id: format!("{} / {}", r.lo_rec, r.hi_rec),
                t_k: t[i],
                range: [r.lo, r.hi],
                detail: "the property ranges used by this node do not intersect (D-10)".into(),
            });
        }
        if t[i] < r.lo || t[i] > r.hi {
            let rec = if t[i] < r.lo { &r.lo_rec } else { &r.hi_rec };
            return Err(Fail::Domain {
                subject: net.ids[i].clone(),
                record_id: rec.clone(),
                t_k: t[i],
                range: [r.lo, r.hi],
                detail: "registered initial temperature outside the node's property ranges (D-01, NUM-02)".into(),
            });
        }
    }
    Ok(())
}

pub fn cons_s_tol(acc: &Accounting) -> f64 {
    CONS_S_REL * acc.q_scale + CONS_S_ABS_W
}

/// Steady state (E-02, E-10, NUM-01) from the registered initial temperatures.
pub fn steady(c: &Compiled, fac: &Factors) -> Result<SteadyOut, Fail> {
    let net = &c.net;
    let ranges = &c.ranges_steady;
    let n = net.ids.len();
    let mut t = c.t_init.clone();
    check_inside(net, &t, ranges)?;
    let mut ev = evaluate(net, &t, fac, true).map_err(from_eval)?;
    let mut acc = net.account(&ev);
    for it in 1..=NUM01_CAP {
        let d = if n == 0 {
            Vec::new()
        } else {
            let lu =
                Lu::factor(ev.jac.clone(), n).ok_or_else(|| model("SINGULAR_SYSTEM", "solver", "steady Jacobian"))?;
            lu.solve(&ev.r.iter().map(|x| -x).collect::<Vec<_>>())
        };
        let lam_dom = fraction_to_boundary(&t, &d, ranges).map_err(|(i, hi)| blocked(net, ranges, i, hi, t[i]))?;
        let norm0 = l2(&ev.r);
        let tol = cons_s_tol(&acc);
        let mut lam = lam_dom;
        let mut chosen = None;
        for _ in 0..40 {
            let trial = apply(&t, &d, lam, ranges);
            let e = evaluate(net, &trial, fac, true).map_err(from_eval)?;
            let nn = l2(&e.r);
            if nn <= (1.0 - 1e-4 * lam) * norm0 || nn <= tol || norm0 <= tol {
                chosen = Some((trial, e));
                break;
            }
            lam *= 0.5;
        }
        let (trial, e) = match chosen {
            Some(x) => x,
            None => {
                let trial = apply(&t, &d, lam_dom, ranges);
                let e = evaluate(net, &trial, fac, true).map_err(from_eval)?;
                (trial, e)
            }
        };
        let last_dt = max_abs_diff(&trial, &t);
        t = trial;
        ev = e;
        acc = net.account(&ev);
        let tol = cons_s_tol(&acc);
        let s1 = ev.r.iter().all(|r| r.abs() <= tol);
        let s2 = acc.net.abs() <= tol;
        if last_dt <= NUM01_MAX_DT_K && s1 && s2 {
            return Ok(SteadyOut { state: State { t, ev, acc }, iterations: it, last_dt, cons_tol: tol });
        }
    }
    Err(model("NEWTON_CAP_REACHED", "solver", format!("steady Newton did not meet NUM-01 in {NUM01_CAP} iterations")))
}

enum StepFail {
    Newton,
    Blocked(Fail),
    Hard(Fail),
}

struct StepOk {
    t: Vec<f64>,
    ev: Eval,
    iters: usize,
}

/// One implicit-Euler step on the enthalpy form (E-11, NUM-03).
fn step(c: &Compiled, t_n: &[f64], h: f64, fac: &Factors) -> Result<StepOk, StepFail> {
    let net = &c.net;
    let ranges = &c.ranges_transient;
    let n = net.ids.len();
    let mut t = t_n.to_vec();
    for it in 1..=NUM03_CAP {
        let ev = evaluate(net, &t, fac, true).map_err(|e| StepFail::Hard(from_eval(e)))?;
        let mut f = vec![0.0; n];
        let mut jac = ev.jac.iter().map(|x| -h * x).collect::<Vec<_>>();
        for i in 0..n {
            let dh = net.enthalpy_change(i, t_n[i], t[i]).map_err(|e| StepFail::Hard(from_eval(e)))?;
            f[i] = dh - h * ev.r[i];
            jac[i * n + i] += net.capacity(i, t[i]).map_err(|e| StepFail::Hard(from_eval(e)))?;
        }
        if n == 0 {
            return Ok(StepOk { t, ev, iters: it });
        }
        let lu =
            Lu::factor(jac, n).ok_or_else(|| StepFail::Hard(model("SINGULAR_SYSTEM", "solver", "step Jacobian")))?;
        let d = lu.solve(&f.iter().map(|x| -x).collect::<Vec<_>>());
        let lam = fraction_to_boundary(&t, &d, ranges)
            .map_err(|(i, hi)| StepFail::Blocked(blocked(net, ranges, i, hi, t[i])))?;
        let next = apply(&t, &d, lam, ranges);
        let last = max_abs_diff(&next, &t);
        t = next;
        if last <= NUM03_MAX_DT_K {
            let ev = evaluate(net, &t, fac, false).map_err(|e| StepFail::Hard(from_eval(e)))?;
            return Ok(StepOk { t, ev, iters: it });
        }
    }
    Err(StepFail::Newton)
}

/// Per node: sum of link conductances at the node + sum over its surfaces of 4 eps sigma T^3 A (D-02, D-09).
pub fn conductance_sum(c: &Compiled, t: &[f64]) -> Result<Vec<f64>, Fail> {
    let net = &c.net;
    let mut g = vec![0.0; net.ids.len()];
    for l in &net.links {
        for end in [&l.a, &l.b] {
            if let End::Node(i) = end {
                g[*i] += match &l.kind {
                    LinkKind::Conduction { s, k } => {
                        s * k
                            .value(t[*i])
                            .map_err(|v| from_eval(EvalError::Domain { violation: v, subject: l.id.clone() }))?
                    }
                    LinkKind::Linear { g, .. } => *g,
                };
            }
        }
    }
    for (i, surfaces) in c.node_surfaces.iter().enumerate() {
        for (a, p) in surfaces {
            let eps = p
                .value(t[i])
                .map_err(|v| from_eval(EvalError::Domain { violation: v, subject: net.ids[i].clone() }))?;
            g[i] += 4.0 * eps * SIGMA * t[i].powi(3) * a;
        }
    }
    Ok(g)
}

impl EnergyTrack {
    fn record(&mut self, dh_step: f64, h: f64, acc: &Accounting, dh_total: f64) -> Result<(), Fail> {
        let r = dh_step - h * acc.net;
        let tol = CONS_T1_REL * (h * acc.abs).max(dh_step.abs()) + CONS_T1_ABS_J;
        if r.abs() / tol > self.worst_step.0 / self.worst_step.1.max(f64::MIN_POSITIVE) || self.worst_step.1 == 0.0 {
            self.worst_step = (r.abs(), tol);
        }
        self.dh_q_sum += h * acc.net;
        self.abs_sum += h * acc.abs;
        let rc = dh_total - self.dh_q_sum;
        let tolc = CONS_T1_REL * self.abs_sum.max(dh_total.abs()) + CONS_T1_ABS_J;
        if rc.abs() / tolc > self.worst_cumulative.0 / self.worst_cumulative.1.max(f64::MIN_POSITIVE)
            || self.worst_cumulative.1 == 0.0
        {
            self.worst_cumulative = (rc.abs(), tolc);
        }
        self.final_cumulative = (rc.abs(), tolc);
        if r.abs() > tol {
            return Err(model(
                "CONSERVATION_CRITERION_NOT_MET",
                "CONS-T1",
                format!("step residual {r:e} J > {tol:e} J"),
            ));
        }
        if rc.abs() > tolc {
            return Err(model(
                "CONSERVATION_CRITERION_NOT_MET",
                "CONS-T1",
                format!("cumulative residual {rc:e} J > {tolc:e} J"),
            ));
        }
        Ok(())
    }
}

struct Integrator<'a> {
    c: &'a Compiled,
    t0_state: Vec<f64>,
    out: TransientOut,
    want_biot: bool,
}

impl<'a> Integrator<'a> {
    /// Advance over one nominal interval [ta, tb] with step doubling (NUM-04, CONS-T2). Returns the end state.
    fn interval(&mut self, t: Vec<f64>, ta: f64, tb: f64, fac: &Factors, time_offset: f64) -> Result<Vec<f64>, Fail> {
        let c = self.c;
        let span = tb - ta;
        let mut depth: u32 = 0;
        let mut j: u64 = 0;
        let mut state = t;
        let mut last_fail: Option<Fail>;
        loop {
            let parts = 1u64 << depth;
            if j == parts {
                return Ok(state);
            }
            let s0 = ta + span * (j as f64) / (parts as f64);
            let s1 = if j + 1 == parts { tb } else { ta + span * ((j + 1) as f64) / (parts as f64) };
            let h = s1 - s0;
            let attempt = (|| -> Result<(StepOk, f64), StepFail> {
                let full = step(c, &state, h, fac)?;
                let half1 = step(c, &state, 0.5 * h, fac)?;
                let half2 = step(c, &half1.t, 0.5 * h, fac)?;
                let diff = max_abs_diff(&full.t, &half2.t);
                Ok((full, diff))
            })();
            match attempt {
                Ok((full, diff)) if diff <= CONS_T2_K => {
                    let dh_step: f64 = (0..state.len())
                        .map(|i| c.net.enthalpy_change(i, state[i], full.t[i]))
                        .collect::<Result<Vec<_>, _>>()
                        .map_err(from_eval)?
                        .iter()
                        .sum();
                    let dh_nodes: Vec<f64> = (0..state.len())
                        .map(|i| c.net.enthalpy_change(i, self.t0_state[i], full.t[i]))
                        .collect::<Result<Vec<_>, _>>()
                        .map_err(from_eval)?;
                    let dh_total: f64 = dh_nodes.iter().sum();
                    let acc = c.net.account(&full.ev);
                    self.out.energy.record(dh_step, h, &acc, dh_total)?;
                    self.out.u_num = self.out.u_num.max(diff);
                    self.out.max_iters = self.out.max_iters.max(full.iters);
                    self.out.max_depth = self.out.max_depth.max(depth);
                    self.out.steps += 1;
                    self.out.times.push(time_offset + s1);
                    self.out.temps.push(full.t.clone());
                    self.out.dh_node = dh_nodes;
                    if self.want_biot {
                        let g = conductance_sum(c, &full.t)?;
                        for (m, x) in self.out.g_lin_max.iter_mut().zip(&g) {
                            *m = m.max(*x);
                        }
                        self.out.states_for_biot.push(full.t.clone());
                    }
                    self.out.final_time = time_offset + s1;
                    self.out.final_state = State { t: full.t.clone(), acc, ev: full.ev };
                    state = full.t;
                    j += 1;
                    continue;
                }
                Ok(_) | Err(StepFail::Newton) => last_fail = None,
                Err(StepFail::Hard(f)) => return Err(f),
                Err(StepFail::Blocked(f)) => last_fail = Some(f),
            }
            depth += 1;
            j *= 2;
            if depth > NUM04_HALVING_CAP {
                return Err(match last_fail {
                    Some(f) => f,
                    None => model(
                        "STEP_HALVING_CAP_REACHED",
                        "solver",
                        format!(
                            "{NUM04_HALVING_CAP} successive halvings without meeting NUM-03 / CONS-T2 at t = {s0} s"
                        ),
                    ),
                });
            }
        }
    }
}

/// Nominal step grid on [a, b]: a, b, every multiple of dt and every breakpoint inside; a breakpoint wins over a
/// multiple of dt closer than 1e-9 dt (breakpoints are exact step boundaries, E-11).
fn grid(a: f64, b: f64, dt: f64, breakpoints: &[f64]) -> Vec<f64> {
    let tol = 1e-9 * dt;
    let bps: Vec<f64> = breakpoints.iter().copied().filter(|&x| x > a + tol && x < b - tol).collect();
    let mut pts: Vec<(f64, bool)> = vec![(a, true), (b, true)];
    pts.extend(bps.iter().map(|&x| (x, true)));
    let mut k: u64 = 1;
    loop {
        let x = a + (k as f64) * dt;
        if x >= b - tol {
            break;
        }
        if !bps.iter().any(|p| (p - x).abs() <= tol) {
            pts.push((x, false));
        }
        k += 1;
    }
    let mut g: Vec<f64> = pts.into_iter().map(|(x, _)| x).collect();
    g.sort_by(|x, y| x.partial_cmp(y).unwrap_or(std::cmp::Ordering::Equal));
    g.dedup();
    g
}

fn new_out(c: &Compiled, t0: &[f64], start: f64) -> TransientOut {
    let n = c.net.ids.len();
    TransientOut {
        times: vec![start],
        temps: vec![t0.to_vec()],
        final_state: State {
            t: t0.to_vec(),
            ev: Eval { r: vec![], jac: vec![], detail: Default::default() },
            acc: Accounting::default(),
        },
        final_time: start,
        dh_node: vec![0.0; n],
        u_num: 0.0,
        max_iters: 0,
        max_depth: 0,
        steps: 0,
        energy: EnergyTrack::default(),
        orbits: None,
        g_lin_max: vec![0.0; n],
        states_for_biot: Vec::new(),
    }
}

/// TRANSIENT (E-11) from the registered initial state.
pub fn transient(c: &Compiled, t0: f64, t1: f64, dt: f64, want_biot: bool) -> Result<TransientOut, Fail> {
    check_inside(&c.net, &c.t_init, &c.ranges_transient)?;
    let g = grid(t0, t1, dt, &c.breakpoints);
    let mut it = Integrator { c, t0_state: c.t_init.clone(), out: new_out(c, &c.t_init, t0), want_biot };
    let mut state = c.t_init.clone();
    for w in g.windows(2) {
        let fac = Factors::window(&c.net, 0.5 * (w[0] + w[1]));
        state = it.interval(state, w[0], w[1], &fac, 0.0)?;
    }
    Ok(it.out)
}

/// ORBIT_TRANSIENT_PERIODIC (E-12, NUM-05, CONS-T3).
pub fn periodic(c: &Compiled, period: f64, dt: f64, want_biot: bool) -> Result<TransientOut, Fail> {
    check_inside(&c.net, &c.t_init, &c.ranges_transient)?;
    let g = grid(0.0, period, dt, &c.breakpoints);
    let facs: Vec<Factors> = g.windows(2).map(|w| Factors::window(&c.net, 0.5 * (w[0] + w[1]))).collect();
    let mut it = Integrator { c, t0_state: c.t_init.clone(), out: new_out(c, &c.t_init, 0.0), want_biot };
    let mut state = c.t_init.clone();
    let mut prev: Option<Vec<Vec<f64>>> = None;
    let mut stats = Vec::new();
    let n = c.net.ids.len();
    for orbit in 1..=NUM05_ORBIT_CAP {
        let offset = (orbit - 1) as f64 * period;
        let first_step = it.out.times.len();
        let mut phase = Vec::new();
        for (w, fac) in g.windows(2).zip(&facs) {
            state = it.interval(state, w[0], w[1], fac, offset)?;
            phase.push(state.clone());
        }
        let mut mn = vec![f64::INFINITY; n];
        let mut mx = vec![f64::NEG_INFINITY; n];
        let mut mean = vec![0.0; n];
        for s in first_step..it.out.times.len() {
            let h = it.out.times[s] - it.out.times[s - 1];
            for i in 0..n {
                let x = it.out.temps[s][i];
                mn[i] = mn[i].min(x);
                mx[i] = mx[i].max(x);
                mean[i] += h * x / period;
            }
        }
        stats.push(OrbitRaw { min: mn, max: mx, mean });
        if let Some(p) = &prev {
            let d = p.iter().zip(&phase).map(|(a, b)| max_abs_diff(a, b)).fold(0.0, f64::max);
            if d <= CONS_T3_K {
                // Keep only the converged orbit's series.
                let keep_from = first_step - 1;
                it.out.times = it.out.times[keep_from..].iter().map(|t| t - offset).collect();
                it.out.temps = it.out.temps[keep_from..].to_vec();
                it.out.orbits = Some((orbit, d, stats));
                return Ok(it.out);
            }
        }
        prev = Some(phase);
    }
    Err(model("PERIODIC_CAP_REACHED", "solver", format!("CONS-T3 not met within {NUM05_ORBIT_CAP} orbits (NUM-05)")))
}
