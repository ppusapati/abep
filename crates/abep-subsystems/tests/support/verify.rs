//! The preregistered verification items of NP-THERMAL-CATHODELESS v1 (analytic_limiting_cases AL-01..AL-11,
//! conservation CONS-*, fail_closed_tests FT-01..FT-18, determinism DET-01..DET-03, independent_verification IV-02),
//! each returning its observed value and whether its preregistered criterion is met. Every input is
//! SYNTHETIC_TEST_DATA_NOT_EVIDENCE except the fail-closed fixtures, whose values are TBD or parametric code-path
//! inputs that are never emitted as results.

use super::vs_net;
use super::*;
use abep_subsystems::thermal::case::*;
use abep_subsystems::thermal::output::{RunStatus, ThermalOutput};
use serde::Serialize;
use serde_json::json;

#[derive(Debug, Clone, Serialize)]
pub struct Check {
    pub id: String,
    pub criterion: String,
    /// Worst observed value(s) over the sub-cases.
    pub observed: Value,
    pub met: bool,
    pub sub_cases: usize,
    /// Largest observed / bound ratio of each conservation criterion met inside the runs of this item.
    pub conservation_max_ratio: BTreeMap<String, f64>,
    pub notes: Vec<String>,
}

impl Check {
    fn new(id: &str, criterion: &str) -> Check {
        Check {
            id: id.into(),
            criterion: criterion.into(),
            observed: Value::Null,
            met: true,
            sub_cases: 0,
            conservation_max_ratio: BTreeMap::new(),
            notes: vec![],
        }
    }
    fn fail(&mut self, note: String) {
        self.met = false;
        if self.notes.len() < 20 {
            self.notes.push(note);
        }
    }
    fn absorb(&mut self, o: &ThermalOutput) {
        self.sub_cases += 1;
        if let Some(r) = &o.results {
            for ch in &r.energy_balance.checks {
                let ratio = if ch.bound > 0.0 { ch.observed / ch.bound } else { 0.0 };
                let e = self.conservation_max_ratio.entry(ch.id.clone()).or_insert(0.0);
                *e = e.max(ratio);
                if !ch.met {
                    self.met = false;
                }
            }
        }
    }
    fn expect_converged(&mut self, o: &ThermalOutput) -> bool {
        self.absorb(o);
        if o.run_status != RunStatus::Converged {
            self.fail(format!("{}: {:?} {:?}", o.case_id, o.run_status, codes(o)));
            return false;
        }
        true
    }
    fn expect_status(&mut self, o: &ThermalOutput, status: RunStatus, code: Option<&str>) {
        self.absorb(o);
        let mut ok = o.run_status == status && o.results.is_none();
        if let Some(c) = code {
            ok &= has_code(o, c);
        }
        if !ok {
            self.fail(format!("{}: expected {status:?} {code:?}, got {:?} {:?}", o.case_id, o.run_status, codes(o)));
        }
    }
}

fn t_of(o: &ThermalOutput, node: &str) -> f64 {
    o.results.as_ref().and_then(|r| r.t_node_k.as_ref()).map(|m| m[node]).unwrap_or(f64::NAN)
}

// ------------------------------------------------------------------------------------------------ analytic cases

fn radiator(id: &str, q: f64, eps: f64, a: f64, ts: f64, eps_range: (f64, f64), t_init: f64) -> Cb {
    let mut cb = Cb::reduced(id);
    cb.node("N1", "ANALYTIC", "RADIATOR", Some(100.0), t_init);
    let ar = cb.num("S1.area", "area", a);
    let er = cb.konst("S1.eps", "emittance_IR", eps, eps_range);
    cb.node_mut("N1").surfaces.push(Surface {
        surface_id: "S1".into(),
        area_record_id: ar,
        eps_ir_record_id: er,
        alpha_solar_record_id: None,
        enclosure_id: "E1".into(),
        external: true,
    });
    cb.enclosure("E1", vf_rows(&[("S1", &[("S1", 0.0), ("SPACE", 1.0)])]), &[("SPACE", "SPACE", ts)], &[]);
    cb.tc("N1", q);
    cb
}

pub fn al_01() -> Check {
    let mut ch =
        Check::new("AL-01", "single isothermal radiator: |T - (Q/(eps sigma A) + T_s^4)^(1/4)| <= 1e-6 K, all 54");
    let mut worst: f64 = 0.0;
    for q in [1.0, 100.0, 1000.0] {
        for eps in [0.1, 0.5, 1.0] {
            for a in [0.01, 0.1, 1.0] {
                for ts in [0.0, 300.0] {
                    let o =
                        run(&radiator(&format!("AL-01/Q{q}/eps{eps}/A{a}/Ts{ts}"), q, eps, a, ts, SYN_RANGE, 300.0).c);
                    if !ch.expect_converged(&o) {
                        continue;
                    }
                    let exact = (q / (eps * SIGMA * a) + ts.powi(4)).powf(0.25);
                    let d = (t_of(&o, "N1") - exact).abs();
                    worst = worst.max(d);
                    if d > 1e-6 {
                        ch.fail(format!("{}: |dT| = {d:e}", o.case_id));
                    }
                }
            }
        }
    }
    ch.observed = json!({"max_abs_dT_K": worst});
    ch.met &= ch.sub_cases == 54;
    ch
}

pub fn al_02() -> Check {
    let mut ch = Check::new(
        "AL-02",
        "two-node series conduction: |dT| <= 1e-6 K at both nodes; |link flow - Q| <= 1e-9 Q + 1e-9 W",
    );
    let (mut wt, mut wf): (f64, f64) = (0.0, 0.0);
    for q in [1.0, 10.0, 50.0] {
        for g1 in [0.1, 1.0, 10.0] {
            for g2 in [0.1, 1.0, 10.0] {
                for tb in [250.0, 300.0] {
                    let mut cb = Cb::reduced(&format!("AL-02/Q{q}/G1{g1}/G2{g2}/Tb{tb}"));
                    cb.node("N1", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
                    cb.node("N2", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
                    let tbr = cb.temperature("T_b", tb);
                    cb.lumped_g("L1", node_ep("N1"), node_ep("N2"), g1);
                    cb.lumped_g("L2", node_ep("N2"), boundary_ep("B_SC", &tbr), g2);
                    cb.tc("N1", q);
                    let o = run(&cb.c);
                    if !ch.expect_converged(&o) {
                        continue;
                    }
                    let t2 = tb + q / g2;
                    let t1 = t2 + q / g1;
                    let d = (t_of(&o, "N1") - t1).abs().max((t_of(&o, "N2") - t2).abs());
                    let r = o.results.as_ref().unwrap();
                    let f = (r.q_link_w["L1"] - q).abs().max((r.q_link_w["L2"] - q).abs());
                    wt = wt.max(d);
                    wf = wf.max(f / (1e-9 * q + 1e-9));
                    if d > 1e-6 || f > 1e-9 * q + 1e-9 {
                        ch.fail(format!("{}: |dT| {d:e}, |flow - Q| {f:e}", o.case_id));
                    }
                }
            }
        }
    }
    ch.observed = json!({"max_abs_dT_K": wt, "max_flow_error_over_bound": wf});
    ch.met &= ch.sub_cases == 54;
    ch
}

pub fn al_02b() -> Check {
    let mut ch = Check::new("AL-02b", "conduction with k = k0 (1 + beta (T - T0)) (Kirchhoff): |dT| <= 1e-6 K");
    let mut worst: f64 = 0.0;
    for q in [1.0, 10.0] {
        for s in [0.1, 1.0] {
            for k0 in [10.0, 100.0] {
                for beta in [-0.001, 0.0, 0.001] {
                    let t0 = 300.0;
                    let mut cb = Cb::reduced(&format!("AL-02b/Q{q}/S{s}/k0{k0}/beta{beta}"));
                    cb.node("N1", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
                    let tbr = cb.temperature("T0", t0);
                    let kr = cb.record(
                        "k",
                        "thermal_conductivity",
                        json!({"form": "POLYNOMIAL", "T0_K": t0, "coefficients": [k0, k0 * beta]}),
                        Some((250.0, 1000.0)),
                    );
                    let sr = cb.num("S", "shape_factor", s);
                    cb.c.links.push(LinkRecord {
                        id: "L1".into(),
                        link_type: "CONDUCTION".into(),
                        a: node_ep("N1"),
                        b: boundary_ep("B_SC", &tbr),
                        k_record_id: Some(kr),
                        shape: Some(ShapeSpec {
                            kind: "SHAPE_FACTOR".into(),
                            area_record_id: None,
                            length_record_id: None,
                            r_outer_record_id: None,
                            r_inner_record_id: None,
                            s_record_id: Some(sr),
                        }),
                        h_c_record_id: None,
                        contact_area_record_id: None,
                        g_record_id: None,
                    });
                    cb.tc("N1", q);
                    let o = run(&cb.c);
                    if !ch.expect_converged(&o) {
                        continue;
                    }
                    // x = (-1 + sqrt(1 + 2 beta Q/(S k0))) / beta, in its rationalized form (exact for beta = 0 too).
                    let u = q / (s * k0);
                    let x = 2.0 * u / (1.0 + (1.0 + 2.0 * beta * u).sqrt());
                    let d = (t_of(&o, "N1") - (t0 + x)).abs();
                    worst = worst.max(d);
                    if d > 1e-6 {
                        ch.fail(format!("{}: |dT| {d:e}", o.case_id));
                    }
                }
            }
        }
    }
    ch.observed = json!({"max_abs_dT_K": worst});
    ch.met &= ch.sub_cases == 24;
    ch
}

fn first_order(c: f64, g: f64, q: f64, t0: f64, tb: f64, dt_frac: f64) -> (ThermalOutput, f64) {
    let tau = c / g;
    let mut cb = Cb::reduced(&format!("AL-03/C{c}/G{g}/Q{q}/T0{t0}/dt=tau/{}", 1.0 / dt_frac));
    cb.node("N1", "ANALYTIC", "HALL_BODY", Some(c), t0);
    let tbr = cb.temperature("T_b", tb);
    cb.lumped_g("L1", node_ep("N1"), boundary_ep("B_SC", &tbr), g);
    cb.tc("N1", q);
    cb.transient(0.0, 10.0 * tau, tau * dt_frac);
    let o = run(&cb.c);
    let t_inf = tb + q / g;
    let err = match &o.results {
        Some(r) => {
            let ts = r.t_s.as_ref().unwrap();
            let s = &r.t_node_k_series.as_ref().unwrap()["N1"];
            ts.iter().zip(s).map(|(t, x)| (x - (t_inf + (t0 - t_inf) * (-t / tau).exp())).abs()).fold(0.0, f64::max)
        }
        None => f64::NAN,
    };
    (o, err)
}

pub fn al_03() -> Check {
    let mut ch = Check::new(
        "AL-03",
        "first-order transient: (a) dt = tau/1000: max |T - T_exact| <= 1e-3 |T_inf - T0|; (b) dt = tau/100: |log2(e(dt)/e(dt/2)) - 1| <= 0.1; (c) CONS-T1 at every step",
    );
    let (mut wa, mut wp): (f64, f64) = (0.0, 0.0);
    for c in [100.0, 1000.0] {
        for g in [0.5, 5.0] {
            for q in [0.0, 100.0] {
                for t0 in [250.0, 350.0] {
                    let tb = 300.0;
                    let t_inf = tb + q / g;
                    let (o, e) = first_order(c, g, q, t0, tb, 1e-3);
                    if ch.expect_converged(&o) {
                        let ratio = e / (1e-3 * (t_inf - t0).abs());
                        wa = wa.max(ratio);
                        if ratio > 1.0 {
                            ch.fail(format!("{}: (a) error ratio {ratio}", o.case_id));
                        }
                    }
                    let (o1, e1) = first_order(c, g, q, t0, tb, 1e-2);
                    let (o2, e2) = first_order(c, g, q, t0, tb, 5e-3);
                    if ch.expect_converged(&o1) && ch.expect_converged(&o2) {
                        let p = (e1 / e2).log2();
                        wp = wp.max((p - 1.0).abs());
                        if (p - 1.0).abs() > 0.1 {
                            ch.fail(format!("{}: (b) p_obs {p}", o1.case_id));
                        }
                    }
                }
            }
        }
    }
    ch.observed = json!({"max_error_over_bound_a": wa, "max_abs_p_obs_minus_1": wp});
    ch.met &= ch.sub_cases == 48;
    ch
}

fn two_surface_geometries() -> Vec<(String, f64, f64, [[f64; 2]; 2])> {
    let a1 = 0.1;
    let mut g = Vec::new();
    for ratio in [0.1, 0.5, 1.0] {
        let a2 = a1 / ratio;
        g.push((format!("concentric A1/A2={ratio}"), a1, a2, [[0.0, 1.0], [a1 / a2, 1.0 - a1 / a2]]));
    }
    for a2 in [0.1, 0.4] {
        let s = a1 + a2;
        g.push((format!("sphere A2={a2}"), a1, a2, [[a1 / s, a2 / s], [a1 / s, a2 / s]]));
    }
    g
}

fn r_tot(eps1: f64, eps2: f64, a1: f64, a2: f64, f12: f64) -> f64 {
    (1.0 - eps1) / (eps1 * a1) + 1.0 / (a1 * f12) + (1.0 - eps2) / (eps2 * a2)
}

pub fn al_04() -> Check {
    let mut ch = Check::new(
        "AL-04",
        "two-surface gray enclosure: (a) prescribed |Q12 - exact| <= 1e-9 |exact| + 1e-12 W; (b) loaded |T1 - T1_exact| <= 1e-6 K",
    );
    let (mut wa, mut wb): (f64, f64) = (0.0, 0.0);
    for (gname, a1, a2, f) in two_surface_geometries() {
        let vf = vf_rows(&[("H1", &[("H1", f[0][0]), ("H2", f[0][1])]), ("H2", &[("H1", f[1][0]), ("H2", f[1][1])])]);
        let vf_b = vf_rows(&[("S1", &[("S1", f[0][0]), ("H2", f[0][1])]), ("H2", &[("S1", f[1][0]), ("H2", f[1][1])])]);
        for eps1 in [0.05, 0.5, 1.0] {
            for eps2 in [0.05, 0.5, 1.0] {
                let rt = r_tot(eps1, eps2, a1, a2, f[0][1]);
                for (t1, t2) in [(400.0, 300.0), (300.0, 400.0), (1000.0, 3.0)] {
                    let mut cb = Cb::reduced(&format!("AL-04a/{gname}/eps{eps1},{eps2}/T{t1},{t2}"));
                    cb.enclosure("E1", vf.clone(), &[], &[("H1", a1, eps1, t1), ("H2", a2, eps2, t2)]);
                    let o = run(&cb.c);
                    if !ch.expect_converged(&o) {
                        continue;
                    }
                    let q12 = -o.results.as_ref().unwrap().q_rad_net_w.per_surface["H1"];
                    let exact = SIGMA * (t1.powi(4) - t2.powi(4)) / rt;
                    let d = (q12 - exact).abs();
                    wa = wa.max(d / (1e-9 * exact.abs() + 1e-12));
                    if d > 1e-9 * exact.abs() + 1e-12 {
                        ch.fail(format!("{}: |dQ| {d:e}", o.case_id));
                    }
                }
                for q in [10.0, 100.0] {
                    let mut cb = Cb::reduced(&format!("AL-04b/{gname}/eps{eps1},{eps2}/Q{q}"));
                    cb.node("N1", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
                    let ar = cb.num("S1.area", "area", a1);
                    let er = cb.konst("S1.eps", "emittance_IR", eps1, SYN_RANGE);
                    cb.node_mut("N1").surfaces.push(Surface {
                        surface_id: "S1".into(),
                        area_record_id: ar,
                        eps_ir_record_id: er,
                        alpha_solar_record_id: None,
                        enclosure_id: "E1".into(),
                        external: false,
                    });
                    cb.enclosure("E1", vf_b.clone(), &[], &[("H2", a2, eps2, 300.0)]);
                    cb.tc("N1", q);
                    let o = run(&cb.c);
                    if !ch.expect_converged(&o) {
                        continue;
                    }
                    let exact = (q * rt / SIGMA + 300.0_f64.powi(4)).powf(0.25);
                    let d = (t_of(&o, "N1") - exact).abs();
                    wb = wb.max(d);
                    if d > 1e-6 {
                        ch.fail(format!("{}: |dT| {d:e}", o.case_id));
                    }
                }
            }
        }
    }
    ch.observed = json!({"a_max_error_over_bound": wa, "b_max_abs_dT_K": wb});
    ch.met &= ch.sub_cases == 5 * 9 * 5;
    ch
}

/// AL-05 on the registered VS-NET; returns the check and the largest node time constant at T_s = 250 K.
pub fn al_05() -> (Check, f64) {
    let mut ch =
        Check::new("AL-05", "VS-NET zero load: |T_i - T_s| <= 1e-6 K; |link flow| <= 1e-9 W; T_s in {3, 250, 300} K");
    let (mut wt, mut wf): (f64, f64) = (0.0, 0.0);
    let mut tau_max = f64::NAN;
    for ts in [3.0, 250.0, 300.0] {
        let mut c = vs_net::load_registered();
        vs_net::set_case_id(&mut c, &format!("AL-05/Ts{ts}"));
        vs_net::zero_loads(&mut c);
        vs_net::set_sinks(&mut c, ts);
        let o = run(&c);
        if !ch.expect_converged(&o) {
            continue;
        }
        let r = o.results.as_ref().unwrap();
        for t in r.t_node_k.as_ref().unwrap().values() {
            wt = wt.max((t - ts).abs());
        }
        for f in r.q_link_w.values() {
            wf = wf.max(f.abs());
        }
        if ts == 250.0 {
            tau_max = o.domain_diagnostics.as_ref().unwrap().time_constant_s.values().fold(0.0, |m: f64, x| m.max(*x));
        }
    }
    if wt > 1e-6 || wf > 1e-9 {
        ch.fail(format!("max |T - T_s| {wt:e} K, max |flow| {wf:e} W"));
    }
    ch.observed = json!({"max_abs_T_minus_Ts_K": wt, "max_abs_link_flow_W": wf, "tau_max_at_250K_s": tau_max});
    ch.met &= ch.sub_cases == 3;
    (ch, tau_max)
}

pub fn vs_net_loaded_steady(ts: f64, id: &str) -> ThermalOutput {
    let mut c = vs_net::load_registered();
    vs_net::set_case_id(&mut c, id);
    vs_net::set_sinks(&mut c, ts);
    run(&c)
}

pub fn al_06(tau_max: f64) -> Check {
    let mut ch = Check::new(
        "AL-06",
        "VS-NET step load from equilibrium at 250 K to 30 tau_max: CONS-T1 every step and cumulative; |T_i(t_end) - T_i,steady| <= 1e-3 K",
    );
    let steady = vs_net_loaded_steady(250.0, "AL-06/steady");
    if !ch.expect_converged(&steady) {
        return ch;
    }
    let mut c = vs_net::load_registered();
    vs_net::set_case_id(&mut c, "AL-06/transient");
    vs_net::set_sinks(&mut c, 250.0);
    vs_net::set_all_t_init(&mut c, 250.0);
    c.solver.mode = "TRANSIENT".into();
    c.solver.t_start_s = Some(0.0);
    c.solver.t_end_s = Some(30.0 * tau_max);
    c.solver.dt_s = Some(tau_max / 200.0);
    let o = run(&c);
    if !ch.expect_converged(&o) {
        return ch;
    }
    let r = o.results.as_ref().unwrap();
    let series = r.t_node_k_series.as_ref().unwrap();
    let ts = steady.results.as_ref().unwrap().t_node_k.as_ref().unwrap();
    let mut worst: f64 = 0.0;
    for (id, s) in series {
        worst = worst.max((s.last().unwrap() - ts[id]).abs());
    }
    if worst > 1e-3 {
        ch.fail(format!("max |T(t_end) - T_steady| = {worst:e} K"));
    }
    ch.observed = json!({
        "max_abs_T_end_minus_T_steady_K": worst,
        "t_end_s": 30.0 * tau_max,
        "dt_s": tau_max / 200.0,
        "accepted_steps": r.convergence.accepted_steps,
        "u_num_t_K": r.convergence.u_num_t_k,
        "cumulative_energy_residual_J": r.energy_balance.cumulative_energy_residual_j,
    });
    ch
}

fn disks(r1: f64, r2: f64, a: f64) -> (f64, f64, f64, f64) {
    // Howell C-41 (C-40 when r1 = r2), rationalized: F12 = 2c / (X + sqrt(X^2 - 4c)), X = 1 + (1 + R2^2)/R1^2, c = (R2/R1)^2.
    let (big1, big2) = (r1 / a, r2 / a);
    let x = 1.0 + (1.0 + big2 * big2) / (big1 * big1);
    let c = (big2 / big1).powi(2);
    let f12 = 2.0 * c / (x + (x * x - 4.0 * c).sqrt());
    let a1 = std::f64::consts::PI * r1 * r1;
    let a2 = std::f64::consts::PI * r2 * r2;
    (a1, a2, f12, a1 * f12 / a2)
}

fn disks_case(
    id: &str,
    vf: BTreeMap<String, BTreeMap<String, f64>>,
    a1: f64,
    a2: f64,
    loads: (f64, f64),
    eps: (f64, f64),
) -> Cb {
    let mut cb = Cb::reduced(id);
    for (n, s, a, e, q) in [("N1", "S1", a1, eps.0, loads.0), ("N2", "S2", a2, eps.1, loads.1)] {
        cb.node(n, "ANALYTIC", "RADIATOR", Some(100.0), 300.0);
        let ar = cb.num(&format!("{s}.area"), "area", a);
        let er = cb.konst(&format!("{s}.eps"), "emittance_IR", e, SYN_RANGE);
        cb.node_mut(n).surfaces.push(Surface {
            surface_id: s.into(),
            area_record_id: ar,
            eps_ir_record_id: er,
            alpha_solar_record_id: None,
            enclosure_id: "E1".into(),
            external: true,
        });
        cb.tc(n, q);
    }
    cb.enclosure("E1", vf, &[("SPACE", "SPACE", 3.0)], &[]);
    cb
}

pub fn al_07() -> Check {
    let mut ch = Check::new(
        "AL-07",
        "coaxial disks closed by SPACE (Howell C-41): (a) accepted; (b) one F perturbed by 1e-6 relative and (c) one row sum perturbed by 1e-6 refused with MODEL_ERROR (D-07)",
    );
    let (a1, a2, f12, f21) = disks(0.05, 0.08, 0.1);
    let mk = |f12: f64, f1s: f64| {
        vf_rows(&[
            ("S1", &[("S1", 0.0), ("S2", f12), ("SPACE", f1s)]),
            ("S2", &[("S1", f21), ("S2", 0.0), ("SPACE", 1.0 - f21)]),
        ])
    };
    let a = run(&disks_case("AL-07a", mk(f12, 1.0 - f12), a1, a2, (5.0, 3.0), (0.8, 0.6)).c);
    ch.expect_converged(&a);
    let fp = f12 * (1.0 + 1e-6);
    let b = run(&disks_case("AL-07b-reciprocity", mk(fp, 1.0 - fp), a1, a2, (5.0, 3.0), (0.8, 0.6)).c);
    ch.expect_status(&b, RunStatus::ModelError, Some("VIEW_FACTOR_RECIPROCITY"));
    let b2 = run(&disks_case("AL-07b-uncompensated", mk(fp, 1.0 - f12), a1, a2, (5.0, 3.0), (0.8, 0.6)).c);
    ch.expect_status(&b2, RunStatus::ModelError, Some("VIEW_FACTOR_RECIPROCITY"));
    let c = run(&disks_case("AL-07c-summation", mk(f12, 1.0 - f12 + 1e-6), a1, a2, (5.0, 3.0), (0.8, 0.6)).c);
    ch.expect_status(&c, RunStatus::ModelError, Some("VIEW_FACTOR_SUMMATION"));
    if has_code(&c, "VIEW_FACTOR_RECIPROCITY") {
        ch.fail("(c) also flagged reciprocity".into());
    }
    ch.observed = json!({
        "a": format!("{:?}", a.run_status),
        "b": format!("{:?} {:?}", b.run_status, codes(&b)),
        "b_uncompensated": format!("{:?} {:?}", b2.run_status, codes(&b2)),
        "c": format!("{:?} {:?}", c.run_status, codes(&c)),
        "F12_C41": f12,
    });
    ch
}

pub fn al_08() -> Check {
    let mut ch = Check::new(
        "AL-08",
        "sphere in four patches, F_kl = A_l / A: (a) all at 300 K: |q_k| <= 1e-12 sigma A_k T^4; (b) black at 300..600 K: |Q_kl - sigma A_k F_kl (T_k^4 - T_l^4)| <= 1e-9 |exact|",
    );
    let areas = [0.1, 0.2, 0.3, 0.4];
    let names = ["P1", "P2", "P3", "P4"];
    let members: Vec<(&str, f64, bool)> = names.iter().zip(areas).map(|(n, a)| (*n, a, false)).collect();
    let vf = sphere_vf(&members);
    let mut cb = Cb::reduced("AL-08a");
    let eps = [0.05, 0.3, 0.7, 1.0];
    let hosts: Vec<(&str, f64, f64, f64)> = (0..4).map(|k| (names[k], areas[k], eps[k], 300.0)).collect();
    cb.enclosure("E1", vf.clone(), &[], &hosts);
    let o = run(&cb.c);
    let mut wa: f64 = 0.0;
    if ch.expect_converged(&o) {
        for k in 0..4 {
            let q = o.results.as_ref().unwrap().q_rad_net_w.per_surface[names[k]];
            let r = q.abs() / (1e-12 * SIGMA * areas[k] * 300.0_f64.powi(4));
            wa = wa.max(r);
            if r > 1.0 {
                ch.fail(format!("(a) {}: |q| {q:e}", names[k]));
            }
        }
    }
    let temps = [300.0, 400.0, 500.0, 600.0];
    let mut cb = Cb::reduced("AL-08b");
    let hosts: Vec<(&str, f64, f64, f64)> = (0..4).map(|k| (names[k], areas[k], 1.0, temps[k])).collect();
    cb.enclosure("E1", vf, &[], &hosts);
    let o = run(&cb.c);
    let mut wb: f64 = 0.0;
    if ch.expect_converged(&o) {
        let pairs = &o.results.as_ref().unwrap().q_rad_net_w.pairwise;
        if pairs.len() != 12 {
            ch.fail(format!("(b) {} pairs, expected 12", pairs.len()));
        }
        for p in pairs {
            let k = names.iter().position(|n| *n == p.from).unwrap();
            let l = names.iter().position(|n| *n == p.to).unwrap();
            let exact = SIGMA * areas[k] * areas[l] * (temps[k].powi(4) - temps[l].powi(4));
            let r = (p.q_w - exact).abs() / (1e-9 * exact.abs());
            wb = wb.max(r);
            if r > 1.0 {
                ch.fail(format!("(b) {}->{}: {} vs {exact}", p.from, p.to, p.q_w));
            }
        }
    }
    ch.observed = json!({"a_max_q_over_bound": wa, "b_max_error_over_bound": wb});
    ch
}

pub fn al_09() -> Check {
    let mut ch = Check::new(
        "AL-09",
        "environment on a one-sided 1 m^2 plate, sink 0 K: |T - ((alpha S + eps q F_e + alpha_E q_aero)/(eps sigma))^(1/4)| <= 1e-6 K; Q_env_abs_W components exact to 1e-12 relative",
    );
    let (mut wt, mut wc): (f64, f64) = (0.0, 0.0);
    for alpha in [0.2, 0.9] {
        for eps in [0.1, 0.9] {
            for s in [1000.0, 1400.0] {
                for q in [0.0, 200.0] {
                    for fe in [0.0, 0.5] {
                        for qa in [0.0, 25.0] {
                            let mut cb = Cb::reduced(&format!("AL-09/a{alpha}/e{eps}/S{s}/q{q}/Fe{fe}/qa{qa}"));
                            cb.node("N1", "ANALYTIC", "RADIATOR", Some(100.0), 300.0);
                            cb.surface("N1", "S1", 1.0, eps, Some(alpha), "E1", true);
                            cb.enclosure(
                                "E1",
                                vf_rows(&[("S1", &[("S1", 0.0), ("SPACE", 1.0)])]),
                                &[("SPACE", "SPACE", 0.0)],
                                &[],
                            );
                            // q_aero = 0.5 rho V^3 with V = 1000 m/s.
                            let rho = qa / (0.5 * 1.0e9);
                            let env = EnvSurface {
                                surface_id: "S1".into(),
                                solar_flux_record_id: cb.num("S", "solar_flux", s),
                                f_sun_record_id: cb.num("Fsun", "view_factor_env", 1.0),
                                illumination_record_id: cb.num("nu", "illumination", 1.0),
                                albedo_record_id: cb.num("a", "albedo", 0.0),
                                f_alb_record_id: cb.num("Falb", "view_factor_env", 0.0),
                                olr_flux_record_id: cb.num("q", "olr_flux", q),
                                f_earth_record_id: cb.num("Fe", "view_factor_env", fe),
                                rho_record_id: cb.num("rho", "density", rho),
                                v_rel_record_id: cb.num("V", "velocity", 1000.0),
                                alpha_e_record_id: cb.num("alphaE", "energy_accommodation", 1.0),
                                a_ram_record_id: cb.num("Aram", "projected_area", 1.0),
                            };
                            cb.c.environment.push(env);
                            let o = run(&cb.c);
                            if !ch.expect_converged(&o) {
                                continue;
                            }
                            let exact = ((alpha * s + eps * q * fe + qa) / (eps * SIGMA)).powf(0.25);
                            let d = (t_of(&o, "N1") - exact).abs();
                            wt = wt.max(d);
                            let e = &o.results.as_ref().unwrap().q_env_abs_w["S1"];
                            for (got, want) in
                                [(e.solar, alpha * s), (e.albedo, 0.0), (e.olr, eps * q * fe), (e.aero, qa)]
                            {
                                let r = if want == 0.0 { got.abs() } else { (got - want).abs() / want.abs() };
                                wc = wc.max(r);
                                if r > 1e-12 {
                                    ch.fail(format!("{}: component {got} vs {want}", o.case_id));
                                }
                            }
                            if d > 1e-6 {
                                ch.fail(format!("{}: |dT| {d:e}", o.case_id));
                            }
                        }
                    }
                }
            }
        }
    }
    ch.observed = json!({"max_abs_dT_K": wt, "max_component_relative_error": wc});
    ch.met &= ch.sub_cases == 64;
    ch
}

/// Expected node deposition of VS-NET's nominal interface records (E-07 receivers and weights).
pub const VS_NET_DEPOSITION: [(&str, &str, f64); 35] = [
    ("H1_ANODE", "Q_hall_anode_W", 60.0),
    ("H1_WALL_IN", "Q_hall_wall_inner_W", 40.0),
    ("H1_WALL_OUT", "Q_hall_wall_outer_W", 50.0),
    ("H1_POLE_IN", "Q_hall_pole_W", 4.0),
    ("H1_POLE_OUT", "Q_hall_pole_W", 6.0),
    ("H1_ANODE", "Q_hall_plasma_radiation_W", 2.0),
    ("H1_WALL_IN", "Q_hall_plasma_radiation_W", 4.0),
    ("H1_WALL_OUT", "Q_hall_plasma_radiation_W", 4.0),
    ("H1_POLE_IN", "Q_hall_plasma_radiation_W", 1.0),
    ("H1_POLE_OUT", "Q_hall_plasma_radiation_W", 1.0),
    ("N_VESSEL", "Q_hall_plasma_radiation_W", 1.0),
    ("N_COLLECTOR", "Q_hall_plasma_radiation_W", 1.0),
    ("N_HOUSING", "Q_hall_plasma_radiation_W", 1.0),
    ("N_COLLECTOR", "Q_hall_return_to_icp_W", 8.0),
    ("N_VESSEL", "Q_hall_plume_to_icp_W", 1.5),
    ("N_COLLECTOR", "Q_hall_plume_to_icp_W", 1.5),
    ("N_HOUSING", "Q_hall_plume_to_icp_W", 1.0),
    ("N_MOUNT", "Q_hall_plume_to_icp_W", 1.0),
    ("H1_COIL_IN", "Q_hall_coil_inner_W", 6.0),
    ("H1_COIL_OUT", "Q_hall_coil_outer_W", 9.0),
    ("H1_COIL_TRIM", "Q_hall_coil_trim_W", 2.0),
    ("N_VESSEL", "Q_icp_plasma_wall_W", 6.0),
    ("N_COLLECTOR", "Q_icp_plasma_wall_W", 3.6),
    ("N_ANTENNA", "Q_icp_plasma_wall_W", 1.2),
    ("N_HOUSING", "Q_icp_plasma_wall_W", 1.2),
    ("N_ANTENNA", "Q_icp_coil_ohmic_W", 4.9),
    ("N_COLLECTOR", "Q_icp_coil_ohmic_W", 1.4),
    ("N_HOUSING", "Q_icp_coil_ohmic_W", 0.7),
    ("N_MATCH", "Q_icp_match_W", 3.0),
    ("N_VESSEL", "Q_icp_radiation_W", 0.6),
    ("N_ANTENNA", "Q_icp_radiation_W", 0.2),
    ("N_COLLECTOR", "Q_icp_radiation_W", 0.2),
    ("N_HOUSING", "Q_icp_radiation_W", 0.2),
    ("H1_POLE_IN", "Q_icp_radiation_W", 0.2),
    ("H1_POLE_OUT", "Q_icp_radiation_W", 0.2),
];

fn vs_variant(id: &str, f: impl FnOnce(&mut ThermalCase)) -> ThermalOutput {
    let mut c = vs_net::load_registered();
    vs_net::set_case_id(&mut c, id);
    f(&mut c);
    run(&c)
}

fn set_key(c: &mut ThermalCase, hall: bool, key: &str, v: f64) {
    let rec = if hall { c.interfaces.hall.as_mut() } else { c.interfaces.icp.as_mut() }.unwrap();
    rec.keys.get_mut(key).unwrap().value = Some(json!(v));
}

pub fn al_10() -> Check {
    let mut ch = Check::new(
        "AL-10",
        "interface bookkeeping on VS-NET: consistent set lands on registered receivers with registered weights and meets CONS-I2; extraction on no node; match on N_MATCH iff co-located; IFH-2/3/4 and IFI-2/3/4 (and IFI-5) violations and a missing key MODEL_ERROR; a TBD key INCOMPLETE_EVIDENCE; a NOT_EVALUATED key NOT_EVALUATED",
    );
    let o = vs_variant("AL-10/consistent", |_| {});
    let mut worst: f64 = 0.0;
    if ch.expect_converged(&o) {
        let r = o.results.as_ref().unwrap();
        for (node, key, w) in VS_NET_DEPOSITION {
            let got = r.q_source_node_w.get(node).and_then(|m| m.get(key)).copied().unwrap_or(f64::NAN);
            let e = (got - w).abs() / w;
            worst = worst.max(e);
            if e.is_nan() || e > 1e-12 {
                ch.fail(format!("{node} {key}: {got} vs {w}"));
            }
        }
        let n_entries: usize = r
            .q_source_node_w
            .values()
            .map(|m| m.keys().filter(|k| k.starts_with("Q_hall") || k.starts_with("Q_icp")).count())
            .sum();
        if n_entries != VS_NET_DEPOSITION.len() {
            ch.fail(format!("{n_entries} node deposition entries, expected {}", VS_NET_DEPOSITION.len()));
        }
        if r.q_source_node_w.values().any(|m| m.contains_key("Q_icp_extraction_W")) {
            ch.fail("extraction deposited on a node".into());
        }
        if r.p_exported_w.get("Q_icp_extraction_W") != Some(&vec![4.0]) {
            ch.fail(format!("exported extraction {:?}", r.p_exported_w.get("Q_icp_extraction_W")));
        }
        let d = r.interface_derived.as_ref().unwrap();
        if d.cons_i2_residual_w > d.cons_i2_bound_w {
            ch.fail("CONS-I2".into());
        }
    }
    let nm = vs_variant("AL-10/match-not-colocated", |c| {
        c.match_colocated = Some(false);
        c.nodes.retain(|n| n.id != "N_MATCH");
        c.links.retain(|l| l.id != "L_MA_MO");
        c.solver.t_init_k.remove("N_MATCH");
    });
    if ch.expect_converged(&nm) {
        let r = nm.results.as_ref().unwrap();
        if r.q_source_node_w.values().any(|m| m.contains_key("Q_icp_match_W")) {
            ch.fail("match deposited on a node while not co-located".into());
        }
        if r.q_boundary_w.b_ppu_rf_booked.get("Q_icp_match_W") != Some(&vec![3.0]) {
            ch.fail("match not booked at B_PPU_RF".into());
        }
    }
    let cases: Vec<(&str, Box<dyn FnOnce(&mut ThermalCase)>, RunStatus, &str)> = vec![
        ("IFH-2", Box::new(|c| set_key(c, true, "Q_hall_anode_W", -1.0)), RunStatus::ModelError, "IFH-2_VIOLATED"),
        ("IFH-3", Box::new(|c| set_key(c, true, "P_hall_jet_W", 500.0)), RunStatus::ModelError, "IFH-3_VIOLATED"),
        (
            "IFH-4",
            Box::new(|c| {
                set_key(c, true, "P_hall_discharge_W", 190.0);
                set_key(c, true, "P_hall_jet_W", 0.0);
                set_key(c, true, "Q_hall_plume_to_icp_W", 10.0);
            }),
            RunStatus::ModelError,
            "IFH-4_VIOLATED",
        ),
        ("IFI-2", Box::new(|c| set_key(c, false, "Q_icp_match_W", -1.0)), RunStatus::ModelError, "IFI-2_VIOLATED"),
        ("IFI-3", Box::new(|c| set_key(c, false, "P_icp_rf_forward_W", 60.0)), RunStatus::ModelError, "IFI-3_VIOLATED"),
        (
            "IFI-4",
            Box::new(|c| {
                set_key(c, false, "P_icp_rf_forward_W", 20.0);
                set_key(c, false, "P_icp_bus_W", 20.0);
                c.interfaces.icp.as_mut().unwrap().rf_powered_only = None;
            }),
            RunStatus::ModelError,
            "IFI-4_VIOLATED",
        ),
        ("IFI-5", Box::new(|c| set_key(c, false, "P_icp_rf_forward_W", 25.0)), RunStatus::ModelError, "IFI-5_VIOLATED"),
        (
            "missing key",
            Box::new(|c| {
                c.interfaces.hall.as_mut().unwrap().keys.remove("Q_hall_wall_outer_W");
            }),
            RunStatus::ModelError,
            "INTERFACE_KEY_MISSING",
        ),
        (
            "TBD key",
            Box::new(|c| {
                let v = c.interfaces.icp.as_mut().unwrap().keys.get_mut("Q_icp_coil_ohmic_W").unwrap();
                v.status = Some("INCOMPLETE_EVIDENCE".into());
                v.value = None;
            }),
            RunStatus::IncompleteEvidence,
            "INTERFACE_KEY_INCOMPLETE_EVIDENCE",
        ),
        (
            "NOT_EVALUATED key",
            Box::new(|c| {
                let v = c.interfaces.hall.as_mut().unwrap().keys.get_mut("Q_hall_pole_W").unwrap();
                v.status = Some("NOT_EVALUATED".into());
                v.value = None;
            }),
            RunStatus::NotEvaluated,
            "INTERFACE_KEY_NOT_EVALUATED",
        ),
    ];
    let mut seen = BTreeMap::new();
    for (name, f, status, code) in cases {
        let o = vs_variant(&format!("AL-10/{name}"), f);
        ch.expect_status(&o, status, Some(code));
        seen.insert(name.to_string(), format!("{:?} {}", o.run_status, codes(&o).join(",")));
    }
    ch.observed = json!({"consistent_max_relative_deposition_error": worst, "refusals": seen});
    ch
}

fn coil_case(id: &str, a: f64, i: f64, g: f64) -> Cb {
    let mut cb = Cb::reduced(id);
    cb.c.magnet_load_mode = Some("CONSTANT_CURRENT_R_OF_T".into());
    cb.node("H1_COIL_IN", "REGISTERED", "HALL_MAGNET", Some(100.0), 300.0);
    cb.node_mut("H1_COIL_IN").receives_interface_keys = vec!["Q_hall_coil_inner_W".into()];
    let tb = cb.temperature("T_b", 300.0);
    cb.lumped_g("L1", node_ep("H1_COIL_IN"), boundary_ep("B_SC", &tb), g);
    let rel = cb.record(
        "r(T)",
        "resistance_ratio_relation",
        json!({"form": "POLYNOMIAL", "T0_K": 293.15, "coefficients": [1.0, a]}),
        Some((200.0, 1000.0)),
    );
    cb.c.coil_resistance_relations.insert("H1_COIL_IN".into(), rel);
    let v = |x: f64, u: &str| ValueRecord {
        value: Some(json!(x)),
        units: Some(u.into()),
        status: Some("EVALUATED".into()),
        evidence_class: Some(SYN.into()),
        source: Some(SYN_SOURCE.into()),
        uncertainty: Some(json!("none")),
        applicability_domain: Some(json!("synthetic")),
        validation_status: Some("NOT_APPLICABLE_SYNTHETIC".into()),
        hall_map: None,
    };
    let keys: BTreeMap<String, ValueRecord> = [
        ("I_hall_coil_inner_A".to_string(), v(i, "A")),
        ("R_hall_coil_inner_ref_ohm".to_string(), v(1.0, "ohm")),
        ("T_hall_coil_inner_ref_K".to_string(), v(293.15, "K")),
    ]
    .into_iter()
    .collect();
    cb.c.interfaces.hall = Some(InterfaceRecord {
        interface_id: "IF-HALL-THERMAL-v1".into(),
        interface_version: "v1".into(),
        producer_id: "SYNTHETIC_MAGNET_PRODUCER".into(),
        producer_version: "synthetic-1".into(),
        producer_prereg_sha256: "e3e6859cf61703c27254e9c231ff4637f7d20ea743c8d881b9e55c8ba9d27c5c".into(),
        case_id: id.into(),
        case_class: "SYNTHETIC_VERIFICATION".into(),
        supply_mode: "NON_FIRING".into(),
        design_state_id: None,
        operating_point_id: "AL-11".into(),
        time_basis: TimeBasis { kind: "STEADY".into(), breakpoints_s: None },
        keys,
        partitions: BTreeMap::new(),
        rf_powered_only: None,
    });
    cb
}

pub fn al_11() -> Check {
    let mut ch = Check::new(
        "AL-11",
        "winding R(T) = R_ref (1 + a (T - T_ref)) on [200, 1000] K: |dT| <= 1e-6 K for the 8 regular cases; runaway (I 10 A, G 0.1 W/K, a 0.004) OUT_OF_DOMAIN with no temperature",
    );
    let mut worst: f64 = 0.0;
    for a in [0.0, 0.004] {
        for i in [1.0, 3.0] {
            for g in [0.1, 1.0] {
                let o = run(&coil_case(&format!("AL-11/a{a}/I{i}/G{g}"), a, i, g).c);
                if !ch.expect_converged(&o) {
                    continue;
                }
                let exact = (g * 300.0 + i * i * (1.0 - a * 293.15)) / (g - i * i * a);
                let d = (t_of(&o, "H1_COIL_IN") - exact).abs();
                worst = worst.max(d);
                if d > 1e-6 {
                    ch.fail(format!("{}: |dT| {d:e}", o.case_id));
                }
            }
        }
    }
    let o = run(&coil_case("AL-11/runaway", 0.004, 10.0, 0.1).c);
    ch.expect_status(&o, RunStatus::OutOfDomain, Some("PROPERTY_RANGE_EXCEEDED"));
    ch.observed = json!({"max_abs_dT_K": worst, "runaway": format!("{:?} {:?}", o.run_status, codes(&o))});
    ch.met &= ch.sub_cases == 9;
    ch
}

// ------------------------------------------------------------------------------------------------ IV-02

/// Hand closed form of the three-surface system (disk 1, disk 2, black SPACE): net emitted q1, q2 (W).
fn three_surface(a1: f64, a2: f64, f12: f64, f21: f64, e1: f64, e2: f64, t1: f64, t2: f64, ts: f64) -> (f64, f64) {
    let (f1s, f2s) = (1.0 - f12, 1.0 - f21);
    let (r1, r2) = (1.0 - e1, 1.0 - e2);
    let (b1, b2, bs) = (SIGMA * t1.powi(4), SIGMA * t2.powi(4), SIGMA * ts.powi(4));
    let (c1, c2) = (e1 * b1 + r1 * f1s * bs, e2 * b2 + r2 * f2s * bs);
    let d = 1.0 - r1 * r2 * f12 * f21;
    let j1 = (c1 + r1 * f12 * c2) / d;
    let j2 = (c2 + r2 * f21 * c1) / d;
    let g1 = f12 * j2 + f1s * bs;
    let g2 = f21 * j1 + f2s * bs;
    (a1 * e1 * (b1 - g1), a2 * e2 * (b2 - g2))
}

pub fn iv_02() -> Check {
    let mut ch = Check::new(
        "IV-02",
        "Howell C-40 / C-41 coaxial gray disks closed by SPACE, three-surface radiosity solved by hand: net exchange within 1e-9 relative",
    );
    let mut worst: f64 = 0.0;
    for (geom, r1, r2) in [("C-40", 0.05, 0.05), ("C-41", 0.05, 0.08)] {
        let (a1, a2, f12, f21) = disks(r1, r2, 0.1);
        for (e1, e2) in [(0.8, 0.6), (0.3, 1.0), (1.0, 1.0), (0.05, 0.05)] {
            for (t1, t2, ts) in [(400.0, 300.0, 3.0), (300.0, 500.0, 0.0), (1000.0, 250.0, 250.0)] {
                let mut cb = Cb::reduced(&format!("IV-02/{geom}/e{e1},{e2}/T{t1},{t2},{ts}"));
                let vf = vf_rows(&[
                    ("H1", &[("H1", 0.0), ("H2", f12), ("SPACE", 1.0 - f12)]),
                    ("H2", &[("H1", f21), ("H2", 0.0), ("SPACE", 1.0 - f21)]),
                ]);
                cb.enclosure("E1", vf, &[("SPACE", "SPACE", ts)], &[("H1", a1, e1, t1), ("H2", a2, e2, t2)]);
                let o = run(&cb.c);
                if !ch.expect_converged(&o) {
                    continue;
                }
                let ps = &o.results.as_ref().unwrap().q_rad_net_w.per_surface;
                let (q1, q2) = three_surface(a1, a2, f12, f21, e1, e2, t1, t2, ts);
                for (got, want) in [(-ps["H1"], q1), (-ps["H2"], q2)] {
                    let r = (got - want).abs() / want.abs();
                    worst = worst.max(r);
                    if r > 1e-9 {
                        ch.fail(format!("{}: {got} vs {want}", o.case_id));
                    }
                }
            }
            for (qa, qb) in [(5.0, 3.0), (50.0, 1.0)] {
                let vf = vf_rows(&[
                    ("S1", &[("S1", 0.0), ("S2", f12), ("SPACE", 1.0 - f12)]),
                    ("S2", &[("S1", f21), ("S2", 0.0), ("SPACE", 1.0 - f21)]),
                ]);
                let o = run(&disks_case(
                    &format!("IV-02/{geom}/e{e1},{e2}/loaded{qa},{qb}"),
                    vf,
                    a1,
                    a2,
                    (qa, qb),
                    (e1, e2),
                )
                .c);
                if !ch.expect_converged(&o) {
                    continue;
                }
                let (q1, q2) = three_surface(a1, a2, f12, f21, e1, e2, t_of(&o, "N1"), t_of(&o, "N2"), 3.0);
                for (got, want) in [(q1, qa), (q2, qb)] {
                    let r = (got - want).abs() / want;
                    worst = worst.max(r);
                    if r > 1e-9 {
                        ch.fail(format!("{}: hand q {got} vs load {want}", o.case_id));
                    }
                }
            }
        }
    }
    ch.observed = json!({"max_relative_error": worst});
    ch
}

// ------------------------------------------------------------------------------------------------ E-12 / CONS-T3

pub fn orbit_consistency() -> Check {
    let mut ch = Check::new(
        "E-12/CONS-T3",
        "ORBIT_TRANSIENT_PERIODIC of a linear node with a ZOH load meets CONS-T3; its orbit mean equals the ORBIT_AVERAGE_STEADY temperature within 1e-3 K (identity of the implicit-Euler right-end mean for a linear network)",
    );
    let build = |mode: &str| {
        let mut cb = Cb::reduced(&format!("E-12/{mode}"));
        cb.node("N1", "ANALYTIC", "HALL_BODY", Some(2000.0), 300.0);
        let tb = cb.temperature("T_b", 300.0);
        cb.lumped_g("L1", node_ep("N1"), boundary_ep("B_SC", &tb), 1.0);
        let q = cb.series("N1.Qtc", "power", &[0.0, 3600.0], &[50.0, 0.0]);
        cb.c.thermal_control.push(ThermalControl { node: "N1".into(), record_id: q });
        cb.c.solver.mode = mode.into();
        cb.c.solver.orbit_period_s = Some(5400.0);
        if mode == "ORBIT_TRANSIENT_PERIODIC" {
            cb.c.solver.dt_s = Some(30.0);
        }
        cb
    };
    let p = run(&build("ORBIT_TRANSIENT_PERIODIC").c);
    let s = run(&build("ORBIT_AVERAGE_STEADY").c);
    if ch.expect_converged(&p) && ch.expect_converged(&s) {
        let r = p.results.as_ref().unwrap();
        let stats = r.t_node_orbit_stats_k.as_ref().unwrap();
        let mean = stats.last().unwrap().mean["N1"];
        let ts = t_of(&s, "N1");
        let d = (mean - ts).abs();
        if d > 1e-3 || (ts - (300.0 + 50.0 * 3600.0 / 5400.0)).abs() > 1e-6 {
            ch.fail(format!("orbit mean {mean} vs orbit-average steady {ts}"));
        }
        ch.observed = json!({
            "orbits": r.convergence.orbits,
            "periodic_max_dT_K": r.convergence.periodic_max_dt_k,
            "orbit_mean_K": mean,
            "orbit_average_steady_K": ts,
            "min_K": stats.last().unwrap().min["N1"],
            "max_K": stats.last().unwrap().max["N1"],
            "labels_steady": s.labels,
        });
    }
    ch
}

// ------------------------------------------------------------------------------------------------ fail-closed

fn flight_vs_net(id: &str) -> ThermalCase {
    let mut c = vs_net::load_registered();
    vs_net::set_case_id(&mut c, id);
    vs_net::set_class(&mut c, "FLIGHT_CONDITIONAL");
    let ds = gov().design_state_ids().iter().next().unwrap().clone();
    c.design_state_id = Some(ds.clone());
    c.anode_material_candidate_id = Some("CAND-02A".into());
    c.collector_material_candidate_id = Some("CAND-02B".into());
    for r in c.records.iter_mut() {
        r.evidence_class = Some("assumed".into());
        r.status = Some("TBD".into());
        r.value = None;
        r.source = Some("test fixture: flight inputs are TBD (NE-03..NE-10)".into());
    }
    for e in c.enclosures.iter_mut() {
        for s in e.sinks.iter_mut() {
            s.kind = "SPACE".into();
        }
    }
    for (rec, producer) in
        [(&mut c.interfaces.hall, "HallThruster.jl bridge"), (&mut c.interfaces.icp, "NP-ICP-NEUTRALIZER")]
    {
        let r = rec.as_mut().unwrap();
        r.design_state_id = Some(ds.clone());
        r.producer_id = producer.into();
        for v in r.keys.values_mut() {
            v.status = Some("NOT_EVALUATED".into());
            v.value = None;
            v.evidence_class = Some("model-derived".into());
        }
    }
    c
}

pub fn ft_01() -> Check {
    let mut ch = Check::new(
        "FT-01",
        "FLIGHT_CONDITIONAL case whose Hall keys must come from the credible transport set (EMPTY): NOT_EVALUATED, reason CREDIBLE_HALL_TRANSPORT_SET_EMPTY, asserted explicitly",
    );
    if !gov().admitted_hall_members().is_empty() {
        ch.fail("governed credible set is not empty".into());
    }
    let o = run(&flight_vs_net("FT-01"));
    ch.expect_status(&o, RunStatus::NotEvaluated, Some("CREDIBLE_HALL_TRANSPORT_SET_EMPTY"));
    for c in ["SPACECRAFT_THERMAL_ICD_ABSENT", "INTERFACE_KEY_NOT_EVALUATED"] {
        if !has_code(&o, c) {
            ch.fail(format!("missing reason {c}"));
        }
    }
    if o.status_reasons.iter().any(|r| r.status == RunStatus::ModelError) {
        ch.fail(format!("unexpected MODEL_ERROR reasons {:?}", codes(&o)));
    }
    if o.provenance.binding_statuses.get("credible_hall_transport_set").map(String::as_str) != Some("EMPTY") {
        ch.fail("binding status credible_hall_transport_set != EMPTY".into());
    }
    ch.observed = json!({"run_status": format!("{:?}", o.run_status), "reasons": codes(&o).into_iter().collect::<std::collections::BTreeSet<_>>()});
    ch
}

fn with_hall_map(member: &str, commit: &str) -> ThermalOutput {
    vs_variant(&format!("FT-02/{member}/{}", &commit[..7]), |c| {
        let v = c.interfaces.hall.as_mut().unwrap().keys.get_mut("Q_hall_anode_W").unwrap();
        v.hall_map = Some(HallMapProvenance {
            ensemble_member_id: member.into(),
            hallthruster_commit: commit.into(),
            map_meta_sha256: "0".repeat(64),
            trustworthy: true,
            wall_life_trustworthy: true,
        });
    })
}

pub fn ft_02() -> Check {
    let mut ch = Check::new(
        "FT-02",
        "Hall value from a screening candidate: NOT_EVALUATED; from a non-pinned HallThruster.jl commit: MODEL_ERROR",
    );
    let pinned = gov().hallthruster_commit().to_string();
    let a = with_hall_map("sgb-screen-01", &pinned);
    ch.expect_status(&a, RunStatus::NotEvaluated, Some("SCREENING_CANDIDATE_NOT_ADMITTED"));
    let b = with_hall_map("sgb-screen-01", &"1".repeat(40));
    ch.expect_status(&b, RunStatus::ModelError, Some("HALLTHRUSTER_COMMIT_NOT_PINNED"));
    ch.observed = json!({"screening": format!("{:?} {:?}", a.run_status, codes(&a)), "non_pinned": format!("{:?} {:?}", b.run_status, codes(&b))});
    ch
}

pub fn ft_03() -> Check {
    let mut ch = Check::new(
        "FT-03",
        "a needed input with status TBD, TBD_AFTER_EVIDENCE or OPEN: INCOMPLETE_EVIDENCE listing the input ids",
    );
    let mut obs = BTreeMap::new();
    for st in ["TBD", "TBD_AFTER_EVIDENCE", "OPEN"] {
        let o = vs_variant(&format!("FT-03/{st}"), |c| {
            let r = c.records.iter_mut().find(|r| r.id.as_deref() == Some("S_RH.eps")).unwrap();
            r.status = Some(st.into());
            r.value = None;
        });
        ch.expect_status(&o, RunStatus::IncompleteEvidence, Some("INPUT_NOT_REGISTERED"));
        if !o.status_reasons.iter().any(|r| r.subject == "S_RH.eps") {
            ch.fail(format!("{st}: input id not listed"));
        }
        obs.insert(st, format!("{:?}", o.run_status));
    }
    ch.observed = json!(obs);
    ch
}

pub fn ft_04() -> Check {
    let mut ch = Check::new("FT-04", "record missing evidence_class, uncertainty, applicability_domain or validation_status, or with wrong units: MODEL_ERROR");
    let mut obs = BTreeMap::new();
    let variants: Vec<(&str, Box<dyn Fn(&mut InputRecord)>)> = vec![
        ("evidence_class", Box::new(|r| r.evidence_class = None)),
        ("uncertainty", Box::new(|r| r.uncertainty = None)),
        ("applicability_domain", Box::new(|r| r.applicability_domain = None)),
        ("validation_status", Box::new(|r| r.validation_status = None)),
        ("units", Box::new(|r| r.units = Some("W/m^2".into()))),
    ];
    for (name, f) in variants {
        let mut cb = radiator(&format!("FT-04/{name}"), 10.0, 0.5, 0.1, 3.0, SYN_RANGE, 300.0);
        f(cb.find_record("S1.area"));
        let o = run(&cb.c);
        let code = if name == "units" { "RECORD_UNITS_MISMATCH" } else { "RECORD_FIELD_MISSING" };
        ch.expect_status(&o, RunStatus::ModelError, Some(code));
        obs.insert(name, format!("{:?} {:?}", o.run_status, codes(&o)));
    }
    ch.observed = json!(obs);
    ch
}

fn parametric_vs_net(id: &str, k_biot: Option<f64>) -> ThermalCase {
    let mut c = vs_net::load_registered();
    vs_net::set_case_id(&mut c, id);
    vs_net::set_class(&mut c, "PARAMETRIC");
    c.anode_material_candidate_id = Some("CAND-01".into());
    c.collector_material_candidate_id = Some("CAND-02B".into());
    for r in c.records.iter_mut() {
        r.evidence_class = Some("assumed".into());
        r.source = Some("test fixture: parametric code-path input; not evidence; outputs never quoted".into());
        if let (Some(k), true) = (k_biot, r.id.as_deref().is_some_and(|i| i.ends_with(".kbiot"))) {
            r.value = Some(json!({"form": "CONSTANT", "value": k}));
        }
    }
    for e in c.enclosures.iter_mut() {
        for s in e.sinks.iter_mut() {
            s.kind = "SPACE".into();
        }
    }
    for rec in [&mut c.interfaces.hall, &mut c.interfaces.icp].into_iter().flatten() {
        for v in rec.keys.values_mut() {
            v.evidence_class = Some("assumed".into());
        }
    }
    c
}

pub fn ft_05() -> Check {
    let mut ch = Check::new("FT-05", "SYNTHETIC_TEST_DATA_NOT_EVIDENCE record in a non-synthetic case: MODEL_ERROR");
    let mut c = parametric_vs_net("FT-05", None);
    c.records.iter_mut().find(|r| r.id.as_deref() == Some("S_RH.area")).unwrap().evidence_class = Some(SYN.into());
    let o = run(&c);
    ch.expect_status(&o, RunStatus::ModelError, Some("SYNTHETIC_RECORD_IN_NON_SYNTHETIC_CASE"));
    let mut cb = radiator("FT-05/mixed-synthetic", 10.0, 0.5, 0.1, 3.0, SYN_RANGE, 300.0);
    cb.find_record("S1.area").evidence_class = Some("measured".into());
    let o2 = run(&cb.c);
    ch.expect_status(&o2, RunStatus::ModelError, Some("EVIDENCE_RECORD_IN_SYNTHETIC_CASE"));
    ch.observed = json!({"synthetic_in_parametric": format!("{:?}", o.run_status), "evidence_in_synthetic": format!("{:?}", o2.run_status)});
    ch
}

pub fn ft_06() -> Check {
    let mut ch =
        Check::new("FT-06", "property evaluation outside its validity range: OUT_OF_DOMAIN, no temperature emitted");
    // Solution 349 K > the emittance range end 340 K.
    let o = run(&radiator("FT-06/solution-outside", 100.0, 0.5, 0.1, 300.0, (0.0, 340.0), 300.0).c);
    ch.expect_status(&o, RunStatus::OutOfDomain, Some("PROPERTY_RANGE_EXCEEDED"));
    let o2 = run(&radiator("FT-06/T_init-outside", 100.0, 0.5, 0.1, 300.0, (0.0, 340.0), 400.0).c);
    ch.expect_status(&o2, RunStatus::OutOfDomain, Some("PROPERTY_RANGE_EXCEEDED"));
    for x in [&o, &o2] {
        let d = x.domain_diagnostics.as_ref();
        if !d.is_some_and(|d| d.violations.iter().any(|v| v.subject == "N1")) {
            ch.fail(format!("{}: diagnostics do not name the node", x.case_id));
        }
    }
    ch.observed = json!({"solution_outside": codes(&o), "t_init_outside": codes(&o2)});
    ch
}

pub fn ft_07() -> Check {
    let mut ch = Check::new("FT-07", "Bi > 0.1 at a node of a non-synthetic case: OUT_OF_DOMAIN naming the node");
    let o = run(&parametric_vs_net("FT-07/Bi-high", None));
    ch.expect_status(&o, RunStatus::OutOfDomain, Some("BIOT_NUMBER_EXCEEDED"));
    let named: Vec<String> =
        o.status_reasons.iter().filter(|r| r.code == "BIOT_NUMBER_EXCEEDED").map(|r| r.subject.clone()).collect();
    if named.is_empty() {
        ch.fail("no node named".into());
    }
    let ok = run(&parametric_vs_net("FT-07/Bi-low", Some(1.0e5)));
    ch.expect_converged(&ok);
    if !ok.labels.contains(&"PARAMETRIC_NOT_A_PREDICTION".to_string()) {
        ch.fail("PARAMETRIC label missing".into());
    }
    let bi_max =
        ok.domain_diagnostics.as_ref().map_or(f64::NAN, |d| d.biot_number.values().fold(0.0, |m: f64, x| m.max(*x)));
    ch.observed = json!({"high_k_case_nodes_named": named, "low_case_status": format!("{:?}", ok.run_status), "low_case_max_Bi": bi_max});
    ch
}

pub fn ft_08() -> Check {
    let mut ch = Check::new("FT-08", "Newton, step-refinement or periodic cap reached: MODEL_ERROR");
    let o1 = run(&radiator("FT-08/steady-cap", 1.0, 1.0, 1.0, 0.0, (0.0, 1.0e17), 1.0e16).c);
    ch.expect_status(&o1, RunStatus::ModelError, Some("NEWTON_CAP_REACHED"));
    let mut cb = Cb::reduced("FT-08/step-halving-cap");
    cb.node("N1", "ANALYTIC", "RADIATOR", None, 1.0e16);
    let ar = cb.num("S1.area", "area", 1.0);
    let er = cb.konst("S1.eps", "emittance_IR", 1.0, (0.0, 1.0e17));
    cb.node_mut("N1").surfaces.push(Surface {
        surface_id: "S1".into(),
        area_record_id: ar,
        eps_ir_record_id: er,
        alpha_solar_record_id: None,
        enclosure_id: "E1".into(),
        external: true,
    });
    cb.enclosure("E1", vf_rows(&[("S1", &[("S1", 0.0), ("SPACE", 1.0)])]), &[("SPACE", "SPACE", 0.0)], &[]);
    cb.tc("N1", 1.0);
    cb.transient(0.0, 10.0, 10.0);
    let o2 = run(&cb.c);
    ch.expect_status(&o2, RunStatus::ModelError, Some("STEP_HALVING_CAP_REACHED"));
    let mut cb = Cb::reduced("FT-08/periodic-cap");
    cb.node("N1", "ANALYTIC", "HALL_BODY", Some(1000.0), 300.0);
    let tb = cb.temperature("T_b", 300.0);
    cb.lumped_g("L1", node_ep("N1"), boundary_ep("B_SC", &tb), 1e-4);
    cb.tc("N1", 10.0);
    cb.c.solver.mode = "ORBIT_TRANSIENT_PERIODIC".into();
    cb.c.solver.orbit_period_s = Some(1000.0);
    cb.c.solver.dt_s = Some(500.0);
    let o3 = run(&cb.c);
    ch.expect_status(&o3, RunStatus::ModelError, Some("PERIODIC_CAP_REACHED"));
    ch.observed = json!({"steady": codes(&o1), "step": codes(&o2), "periodic": codes(&o3)});
    ch
}

pub fn ft_09() -> Check {
    let mut ch = Check::new("FT-09", "floating node: MODEL_ERROR");
    let mut cb = Cb::reduced("FT-09");
    cb.node("N1", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
    cb.node("N2", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
    let tb = cb.temperature("T_b", 300.0);
    cb.lumped_g("L1", node_ep("N1"), boundary_ep("B_SC", &tb), 1.0);
    cb.tc("N2", 1.0);
    let o = run(&cb.c);
    ch.expect_status(&o, RunStatus::ModelError, Some("FLOATING_NODE"));
    if !o.status_reasons.iter().any(|r| r.code == "FLOATING_NODE" && r.subject == "N2") {
        ch.fail("floating node not named".into());
    }
    let o2 = vs_variant("FT-09/vs-net", |c| {
        c.links.retain(|l| l.id != "L_MA_MO");
    });
    ch.expect_status(&o2, RunStatus::ModelError, Some("FLOATING_NODE"));
    ch.observed = json!({"reduced": codes(&o), "vs_net_without_L_MA_MO": codes(&o2)});
    ch
}

pub fn ft_10() -> Check {
    let mut ch = Check::new("FT-10", "topology, interface record or case carrying the EX-02 refused vocabulary (vocab::REFUSED_SUBSTRINGS / REFUSED_TOKENS) or an excluded node id: MODEL_ERROR (refusal)");
    let mut tokens: Vec<String> =
        abep_subsystems::thermal::vocab::REFUSED_SUBSTRINGS.iter().map(|s| s.to_uppercase()).collect();
    tokens.extend(abep_subsystems::thermal::vocab::REFUSED_TOKENS.iter().map(|s| s.to_uppercase()));
    let mut obs = BTreeMap::new();
    for tok in &tokens {
        // A node, a link and an interface key carrying the refused vocabulary.
        let node = format!("N_{tok}");
        let mut cb = Cb::reduced(&format!("FT-10/node/{tok}"));
        cb.node(&node, "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
        let tb = cb.temperature("T_b", 300.0);
        cb.lumped_g("L1", node_ep(&node), boundary_ep("B_SC", &tb), 1.0);
        let o = run(&cb.c);
        ch.expect_status(&o, RunStatus::ModelError, Some("FORBIDDEN_IDENTIFIER"));
        let o2 = vs_variant(&format!("FT-10/link/{tok}"), |c| c.links[0].id = format!("L_{tok}_1"));
        ch.expect_status(&o2, RunStatus::ModelError, Some("FORBIDDEN_IDENTIFIER"));
        let o3 = vs_variant(&format!("FT-10/key/{tok}"), |c| {
            let v = c.interfaces.hall.as_ref().unwrap().keys["Q_hall_anode_W"].clone();
            c.interfaces.hall.as_mut().unwrap().keys.insert(format!("Q_{tok}_W"), v);
        });
        ch.expect_status(&o3, RunStatus::ModelError, Some("FORBIDDEN_IDENTIFIER"));
        obs.insert(tok.clone(), format!("{:?}/{:?}/{:?}", o.run_status, o2.run_status, o3.run_status));
    }
    for excluded in ["CB", "CE", "CK"] {
        let mut cb = Cb::reduced(&format!("FT-10/excluded/{excluded}"));
        cb.node(excluded, "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
        let tb = cb.temperature("T_b", 300.0);
        cb.lumped_g("L1", node_ep(excluded), boundary_ep("B_SC", &tb), 1.0);
        let o = run(&cb.c);
        ch.expect_status(&o, RunStatus::ModelError, Some("FORBIDDEN_IDENTIFIER"));
        obs.insert(excluded.to_string(), format!("{:?}", o.run_status));
    }
    ch.observed = json!(obs);
    ch
}

pub fn ft_11() -> Check {
    let mut ch = Check::new(
        "FT-11",
        "configuration other than hall_icp_neutralizer (e.g. hall_c1_reference): MODEL_ERROR (refusal)",
    );
    let o = vs_variant("FT-11", |c| c.configuration = "hall_c1_reference".into());
    ch.expect_status(&o, RunStatus::ModelError, Some("CONFIGURATION_REFUSED"));
    ch.observed = json!(codes(&o));
    ch
}

pub fn ft_12() -> Check {
    let mut ch = Check::new("FT-12", "bus variant active_cooling or icp_assist_magnet installed: OUT_OF_DOMAIN");
    let mut obs = BTreeMap::new();
    for v in ["active_cooling", "icp_assist_magnet"] {
        let o = vs_variant(&format!("FT-12/{v}"), |c| c.installed_variants = vec![v.into()]);
        ch.expect_status(&o, RunStatus::OutOfDomain, Some("VARIANT_OUTSIDE_V1"));
        obs.insert(v, format!("{:?}", o.run_status));
    }
    let ok = vs_variant("FT-12/flow_control_icp_feed", |c| c.installed_variants = vec!["flow_control_icp_feed".into()]);
    ch.expect_converged(&ok);
    ch.observed = json!(obs);
    ch
}

pub fn ft_13(al10: &Check) -> Check {
    let mut ch =
        Check::new("FT-13", "IFH-3, IFH-4, IFI-3, IFI-4 or IFI-5 violated: MODEL_ERROR (asserted inside AL-10)");
    ch.met = al10.met;
    ch.observed = al10.observed.get("refusals").cloned().unwrap_or(Value::Null);
    ch.sub_cases = 5;
    ch
}

pub fn ft_14(al07: &Check) -> Check {
    let mut ch = Check::new("FT-14", "view-factor set violating D-07: MODEL_ERROR (asserted inside AL-07 (b), (c))");
    ch.met = al07.met;
    ch.observed = al07.observed.clone();
    ch.sub_cases = 3;
    ch
}

pub fn ft_15() -> Check {
    let mut ch = Check::new("FT-15", "design state outside design_states_v2: OUT_OF_DOMAIN");
    let o = vs_variant("FT-15", |c| {
        c.design_state_id = Some("ds2:NOT_A_REGISTERED_STATE".into());
        for r in [&mut c.interfaces.hall, &mut c.interfaces.icp].into_iter().flatten() {
            r.design_state_id = Some("ds2:NOT_A_REGISTERED_STATE".into());
        }
    });
    ch.expect_status(&o, RunStatus::OutOfDomain, Some("DESIGN_STATE_OUTSIDE_DESIGN_STATES_V2"));
    let ds = gov().design_state_ids().iter().next().unwrap().clone();
    let ok = vs_variant("FT-15/registered-state", |c| {
        c.design_state_id = Some(ds.clone());
        for r in [&mut c.interfaces.hall, &mut c.interfaces.icp].into_iter().flatten() {
            r.design_state_id = Some(ds.clone());
        }
    });
    ch.expect_converged(&ok);
    ch.observed = json!({"outside": codes(&o), "registered": format!("{:?}", ok.run_status), "n_design_states": gov().design_state_ids().len()});
    ch
}

pub fn ft_16() -> Check {
    let mut ch = Check::new("FT-16", "anode candidate CAND-01 (316L) in a FLIGHT_CONDITIONAL case: MODEL_ERROR; allowed and labelled in BENCH_REPLICA / PARAMETRIC");
    let mut c = flight_vs_net("FT-16/flight");
    c.anode_material_candidate_id = Some("CAND-01".into());
    let o = run(&c);
    ch.expect_status(&o, RunStatus::ModelError, Some("ANODE_CANDIDATE_REJECTED_AS_CURRENT_BASELINE"));
    let p = run(&parametric_vs_net("FT-16/parametric", Some(1.0e5)));
    ch.expect_converged(&p);
    if !p.labels.iter().any(|l| l.starts_with("ANODE_CAND-01"))
        || has_code(&p, "ANODE_CANDIDATE_REJECTED_AS_CURRENT_BASELINE")
    {
        ch.fail(format!("parametric labels {:?}", p.labels));
    }
    ch.observed = json!({"flight": format!("{:?}", o.run_status), "parametric": format!("{:?}", p.run_status), "parametric_labels": p.labels});
    ch
}

pub const FORBIDDEN_KEY_TOKENS: [&str; 6] = ["margin", "limit", "pass", "fail", "compliant", "feasible"];
pub const FORBIDDEN_KEY_PREFIXES: [&str; 3] = ["chk_", "rfp_", "ic_"];

pub fn ft_17(outputs: &[&ThermalOutput]) -> Check {
    let mut ch = Check::new(
        "FT-17",
        "static scan of the output schema: no key named margin, limit, pass, fail, compliant or feasible; no key prefixed chk_, rfp_ or ic_; validation_status present and NOT_VALIDATED",
    );
    let mut n_keys = 0;
    for o in outputs {
        let v = serde_json::to_value(o).unwrap();
        let mut keys = Vec::new();
        all_keys(&v, &mut keys);
        n_keys += keys.len();
        for k in keys {
            let low = k.to_ascii_lowercase();
            let bad_tok = low.split(|c: char| !c.is_ascii_alphanumeric()).any(|t| FORBIDDEN_KEY_TOKENS.contains(&t));
            let bad_pre = FORBIDDEN_KEY_PREFIXES.iter().any(|p| low.starts_with(p));
            if bad_tok || bad_pre {
                ch.fail(format!("{}: key {k:?}", o.case_id));
            }
        }
        if v["validation_status"] != "NOT_VALIDATED" || v["provenance"]["validation_status"] != "NOT_VALIDATED" {
            ch.fail(format!("{}: validation_status", o.case_id));
        }
        ch.sub_cases += 1;
    }
    ch.observed = json!({"outputs_scanned": outputs.len(), "keys_scanned": n_keys});
    ch
}

pub fn ft_18() -> Check {
    let mut ch = Check::new(
        "FT-18",
        "interface key with status NOT_EVALUATED: run NOT_EVALUATED; the key is never replaced by zero",
    );
    let o = vs_variant("FT-18", |c| {
        let v = c.interfaces.icp.as_mut().unwrap().keys.get_mut("Q_icp_radiation_W").unwrap();
        v.status = Some("NOT_EVALUATED".into());
        v.value = None;
    });
    ch.expect_status(&o, RunStatus::NotEvaluated, Some("INTERFACE_KEY_NOT_EVALUATED"));
    let zero_filled = vs_variant("FT-18/zero-with-not-evaluated-status", |c| {
        let v = c.interfaces.icp.as_mut().unwrap().keys.get_mut("Q_icp_radiation_W").unwrap();
        v.status = Some("NOT_EVALUATED".into());
        v.value = Some(json!(0.0));
    });
    ch.expect_status(&zero_filled, RunStatus::ModelError, Some("VALUE_RECORD_VALUE_SHAPE"));
    ch.observed = json!({"not_evaluated": codes(&o), "value_with_not_evaluated_status": codes(&zero_filled)});
    ch
}

// ------------------------------------------------------------------------------------------------ determinism

pub fn det(outputs_cases: &[ThermalCase]) -> (Check, Check, Check) {
    let mut d1 = Check::new("DET-01", "byte-identical outputs on two runs of the same inputs");
    let mut d2 = Check::new("DET-02", "byte-identical outputs across thread counts");
    let mut d3 = Check::new(
        "DET-03",
        "every output carries implementation = rust, rust_commit, the prereg sha256 and the input hashes (O-17)",
    );
    for c in outputs_cases {
        let a = run(c).to_json();
        let b = run(c).to_json();
        d1.sub_cases += 1;
        if a != b {
            d1.fail(format!("{}: two runs differ", c.case_id));
        }
        let handles: Vec<_> = (0..4)
            .map(|_| {
                let c = c.clone();
                std::thread::spawn(move || run(&c).to_json())
            })
            .collect();
        for h in handles {
            if h.join().unwrap() != a {
                d2.fail(format!("{}: threaded run differs", c.case_id));
            }
        }
        d2.sub_cases += 1;
        let o = run(c);
        let p = &o.provenance;
        d3.sub_cases += 1;
        let ok = p.implementation == "rust"
            && p.rust_commit.len() == 40
            && p.prereg_sha256 == "e3e6859cf61703c27254e9c231ff4637f7d20ea743c8d881b9e55c8ba9d27c5c"
            && p.input_set_sha256.len() == 64
            && p.interface_record_sha256.len()
                == usize::from(c.interfaces.hall.is_some()) + usize::from(c.interfaces.icp.is_some())
            && p.governed_record_sha256.contains_key("architecture_config_sha256")
            && p.governed_record_sha256.contains_key("design_state_set_sha256")
            && p.governed_record_sha256.contains_key("model_set_sha256")
            && p.validation_status == "NOT_VALIDATED";
        if !ok {
            d3.fail(format!("{}: provenance {:?}", c.case_id, p));
        }
    }
    d1.observed = json!({"cases": d1.sub_cases});
    d2.observed = json!({"cases": d2.sub_cases, "threads": 4});
    d3.observed = json!({"cases": d3.sub_cases});
    (d1, d2, d3)
}

/// Representative cases for determinism and the output scan: steady VS-NET, transient VS-NET (short), periodic.
pub fn det_cases() -> Vec<ThermalCase> {
    let steady = {
        let mut c = vs_net::load_registered();
        vs_net::set_case_id(&mut c, "DET/vs-net-steady");
        c
    };
    let transient = {
        let mut c = vs_net::load_registered();
        vs_net::set_case_id(&mut c, "DET/vs-net-transient");
        vs_net::set_all_t_init(&mut c, 250.0);
        c.solver.mode = "TRANSIENT".into();
        c.solver.t_start_s = Some(0.0);
        c.solver.t_end_s = Some(600.0);
        c.solver.dt_s = Some(30.0);
        c
    };
    let refused = flight_vs_net("DET/flight-refused");
    vec![steady, transient, refused]
}

// ------------------------------------------------------------------------------------------------ bench domain

fn bench_vs_net(id: &str) -> ThermalCase {
    let mut c = flight_vs_net(id);
    vs_net::set_class(&mut c, "BENCH_REPLICA");
    c.design_state_id = None;
    c.supply_mode = "BENCH_AR_ENGINEERING_GROUND_ONLY".into();
    for r in [&mut c.interfaces.hall, &mut c.interfaces.icp].into_iter().flatten() {
        r.design_state_id = None;
        r.supply_mode = "BENCH_AR_ENGINEERING_GROUND_ONLY".into();
    }
    for e in c.enclosures.iter_mut() {
        for s in e.sinks.iter_mut() {
            s.kind = "B_FACILITY".into();
        }
    }
    c.environment.clear();
    c
}

pub fn bench_domain() -> Check {
    let mut ch = Check::new(
        "D-04/D-05/B_FACILITY",
        "BENCH_REPLICA domain: facility vacuum and A-04 criterion registered (D-04, else OUT_OF_DOMAIN); bench supply modes only (D-05); B_FACILITY replaces SPACE and ENV; facility sink measured per run",
    );
    let mut obs = BTreeMap::new();
    let base = run(&bench_vs_net("BENCH/base"));
    for code in ["BENCH_VACUUM_NOT_REGISTERED", "FACILITY_SINK_NOT_MEASURED"] {
        if !has_code(&base, code) {
            ch.fail(format!("base: missing {code}"));
        }
    }
    if base.status_reasons.iter().any(|r| r.status == RunStatus::ModelError) || base.results.is_some() {
        ch.fail(format!("base: {:?} {:?}", base.run_status, codes(&base)));
    }
    obs.insert("base", format!("{:?}", base.run_status));
    let mut c = bench_vs_net("BENCH/space");
    c.enclosures[1].sinks[0].kind = "SPACE".into();
    let o = run(&c);
    ch.expect_status(&o, RunStatus::ModelError, Some("SINK_NOT_ALLOWED"));
    obs.insert("space_sink", format!("{:?}", o.run_status));
    let mut c = bench_vs_net("BENCH/env");
    c.environment = vs_net::load_registered().environment;
    let o = run(&c);
    ch.expect_status(&o, RunStatus::ModelError, Some("ENV_NOT_ALLOWED"));
    obs.insert("environment", format!("{:?}", o.run_status));
    let mut c = bench_vs_net("BENCH/air");
    c.supply_mode = "AIR_PRIMARY".into();
    for r in [&mut c.interfaces.hall, &mut c.interfaces.icp].into_iter().flatten() {
        r.supply_mode = "AIR_PRIMARY".into();
    }
    let o = run(&c);
    if !has_code(&o, "SUPPLY_MODE_OUTSIDE_DOMAIN") || o.results.is_some() {
        ch.fail(format!("air supply: {:?}", codes(&o)));
    }
    obs.insert("flight_supply_mode", format!("{:?}", o.run_status));
    ch.sub_cases += 2;
    ch.observed = json!(obs);
    ch
}

// ------------------------------------------------------------------------------------------------ IV-01 data

/// Per-case Rust results of the analytic cases for the non-authoritative Python cross-check IV-01 (scratch only).
pub fn iv01_dump() -> Value {
    let mut out = BTreeMap::new();
    let mut al01 = Vec::new();
    for q in [1.0, 100.0, 1000.0] {
        for eps in [0.1, 0.5, 1.0] {
            for a in [0.01, 0.1, 1.0] {
                for ts in [0.0, 300.0] {
                    let o = run(&radiator("IV01/AL-01", q, eps, a, ts, SYN_RANGE, 300.0).c);
                    al01.push(json!({"Q": q, "eps": eps, "A": a, "Ts": ts, "T": t_of(&o, "N1")}));
                }
            }
        }
    }
    out.insert("AL-01", json!(al01));
    let mut al02 = Vec::new();
    for q in [1.0, 10.0, 50.0] {
        for g1 in [0.1, 1.0, 10.0] {
            for g2 in [0.1, 1.0, 10.0] {
                for tb in [250.0, 300.0] {
                    let mut cb = Cb::reduced("IV01/AL-02");
                    cb.node("N1", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
                    cb.node("N2", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
                    let tbr = cb.temperature("T_b", tb);
                    cb.lumped_g("L1", node_ep("N1"), node_ep("N2"), g1);
                    cb.lumped_g("L2", node_ep("N2"), boundary_ep("B_SC", &tbr), g2);
                    cb.tc("N1", q);
                    let o = run(&cb.c);
                    al02.push(
                        json!({"Q": q, "G1": g1, "G2": g2, "Tb": tb, "T1": t_of(&o, "N1"), "T2": t_of(&o, "N2")}),
                    );
                }
            }
        }
    }
    out.insert("AL-02", json!(al02));
    let mut al11 = Vec::new();
    for a in [0.0, 0.004] {
        for i in [1.0, 3.0] {
            for g in [0.1, 1.0] {
                let o = run(&coil_case("IV01/AL-11", a, i, g).c);
                al11.push(json!({"a": a, "I": i, "G": g, "T": t_of(&o, "H1_COIL_IN")}));
            }
        }
    }
    out.insert("AL-11", json!(al11));
    let mut al04 = Vec::new();
    for (gname, a1, a2, f) in two_surface_geometries() {
        let vf_b = vf_rows(&[("S1", &[("S1", f[0][0]), ("H2", f[0][1])]), ("H2", &[("S1", f[1][0]), ("H2", f[1][1])])]);
        for eps1 in [0.05, 0.5, 1.0] {
            for eps2 in [0.05, 0.5, 1.0] {
                for q in [10.0, 100.0] {
                    let mut cb = Cb::reduced("IV01/AL-04b");
                    cb.node("N1", "ANALYTIC", "HALL_BODY", Some(100.0), 300.0);
                    let ar = cb.num("S1.area", "area", a1);
                    let er = cb.konst("S1.eps", "emittance_IR", eps1, SYN_RANGE);
                    cb.node_mut("N1").surfaces.push(Surface {
                        surface_id: "S1".into(),
                        area_record_id: ar,
                        eps_ir_record_id: er,
                        alpha_solar_record_id: None,
                        enclosure_id: "E1".into(),
                        external: false,
                    });
                    cb.enclosure("E1", vf_b.clone(), &[], &[("H2", a2, eps2, 300.0)]);
                    cb.tc("N1", q);
                    let o = run(&cb.c);
                    al04.push(json!({"geometry": gname, "A1": a1, "A2": a2, "F12": f[0][1], "eps1": eps1, "eps2": eps2, "Q": q, "T1": t_of(&o, "N1")}));
                }
            }
        }
    }
    out.insert("AL-04b", json!(al04));
    let mut al03 = Vec::new();
    for c in [100.0, 1000.0] {
        for g in [0.5, 5.0] {
            for q in [0.0, 100.0] {
                for t0 in [250.0, 350.0] {
                    let (o, _) = first_order(c, g, q, t0, 300.0, 1e-2);
                    let r = o.results.as_ref().unwrap();
                    al03.push(json!({"C": c, "G": g, "Q": q, "T0": t0, "Tb": 300.0, "t_s": r.t_s, "T": r.t_node_k_series.as_ref().unwrap()["N1"]}));
                }
            }
        }
    }
    out.insert("AL-03", json!(al03));
    let (a1, a2, f12, f21) = disks(0.05, 0.08, 0.1);
    out.insert("C-41", json!({"r1": 0.05, "r2": 0.08, "a": 0.1, "A1": a1, "A2": a2, "F12": f12, "F21": f21}));
    json!(out)
}

/// The VS-NET cases of the IV-01 cross-check: the loaded steady state (sinks 250 K) and a transient from 250 K at a
/// refined step.
pub fn iv01_vs_net(dt: f64, t_end: f64) -> (ThermalOutput, ThermalOutput) {
    let steady = vs_net_loaded_steady(250.0, "IV01/vs-net-steady");
    let mut c = vs_net::load_registered();
    vs_net::set_case_id(&mut c, "IV01/vs-net-transient");
    vs_net::set_sinks(&mut c, 250.0);
    vs_net::set_all_t_init(&mut c, 250.0);
    c.solver.mode = "TRANSIENT".into();
    c.solver.t_start_s = Some(0.0);
    c.solver.t_end_s = Some(t_end);
    c.solver.dt_s = Some(dt);
    (steady, run(&c))
}
