//! Compiled network and its residual / analytic Jacobian (E-01..E-09, E-14).
//!
//! Sign convention: Q is positive into the receiving node. `r[i]` is the right-hand side of E-01 for node i (W).

use super::linalg::Lu;
use super::props::{DomainViolation, Prop};
use super::series::TimeValue;

/// Stefan-Boltzmann constant, CODATA 2022, exact (registered source nist_codata_sigma).
pub const SIGMA: f64 = 5.670374419e-8;

#[derive(Debug, Clone)]
pub enum End {
    Node(usize),
    Fixed { boundary: String, t: TimeValue, record_id: String },
}

#[derive(Debug, Clone)]
pub enum LinkKind {
    /// E-03: Q_a->b = S (Theta(T_a) - Theta(T_b)).
    Conduction { s: f64, k: Prop },
    /// E-04: Q_a->b = G (T_a - T_b); G = h_c A_c (CONTACT) or G (LUMPED_G), valid on [t_min, t_max].
    Linear { g: f64, record_id: String, t_min: f64, t_max: f64 },
}

#[derive(Debug, Clone)]
pub struct LinkC {
    pub id: String,
    pub a: End,
    pub b: End,
    pub kind: LinkKind,
}

#[derive(Debug, Clone)]
pub enum MemberKind {
    Node {
        node: usize,
        eps: Prop,
    },
    /// SCI-C host spacecraft surface (boundary B_SC) at a registered temperature.
    Host {
        eps: Prop,
        t: TimeValue,
    },
    /// Black sink (SPACE or B_FACILITY), J = sigma T^4.
    Sink {
        t: TimeValue,
        kind: String,
    },
}

#[derive(Debug, Clone)]
pub struct MemberC {
    pub surface_id: String,
    pub area: f64,
    pub kind: MemberKind,
}

#[derive(Debug, Clone)]
pub struct EnclC {
    pub id: String,
    pub members: Vec<MemberC>,
    /// Non-sink members (radiosity unknowns), in member order.
    pub unknown: Vec<usize>,
    /// F[m][l] for every non-sink member m over all members l (sink rows unused).
    pub f: Vec<Vec<f64>>,
}

#[derive(Debug, Clone)]
pub struct EnvC {
    pub surface_id: String,
    pub node: usize,
    pub area: f64,
    pub alpha: Prop,
    pub eps: Prop,
    pub s: TimeValue,
    pub f_sun: TimeValue,
    pub nu: TimeValue,
    pub a: TimeValue,
    pub f_alb: TimeValue,
    pub q_olr: TimeValue,
    pub f_earth: TimeValue,
    pub rho: TimeValue,
    pub v: TimeValue,
    pub alpha_e: TimeValue,
    pub a_ram: f64,
}

/// E-09 CONSTANT_CURRENT_R_OF_T winding: Q = I^2 R_ref r(T) / r(T_ref).
#[derive(Debug, Clone)]
pub struct CoilC {
    pub node: usize,
    pub key: String,
    pub i: TimeValue,
    pub r_ref: TimeValue,
    pub t_ref: TimeValue,
    pub rel: Prop,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SourceKind {
    /// Interface deposition (E-07), incl. FIXED_POWER coil keys.
    Interface,
    /// HS-TC registered thermal-control dissipation.
    ThermalControl,
    /// SCI-B prescribed flux from B_SC.
    BoundaryFlux,
}

#[derive(Debug, Clone)]
pub struct SourceC {
    pub node: usize,
    pub label: String,
    pub weight: f64,
    pub tv: TimeValue,
    pub kind: SourceKind,
}

#[derive(Debug, Clone)]
pub struct Net {
    pub ids: Vec<String>,
    /// Parts (mass kg, specific heat) per node; empty for a massless series node.
    pub parts: Vec<Vec<(f64, Prop)>>,
    pub links: Vec<LinkC>,
    pub encl: Vec<EnclC>,
    pub env: Vec<EnvC>,
    pub coils: Vec<CoilC>,
    pub sources: Vec<SourceC>,
}

/// Time factors of one evaluation interval (window midpoint) or of an orbit average (E-12).
#[derive(Debug, Clone)]
pub struct Factors {
    pub src: Vec<f64>,
    /// Per env surface: [S F_sun nu, a S F_alb, q_OLR F_earth, 0.5 rho V^3 alpha_E].
    pub env: Vec<[f64; 4]>,
    /// Per coil: (I^2, R_ref, T_ref).
    pub coil: Vec<(f64, f64, f64)>,
    pub link_t: Vec<(Option<f64>, Option<f64>)>,
    pub member_t: Vec<Vec<Option<f64>>>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum EvalError {
    Domain { violation: DomainViolation, subject: String },
    Nonphysical(String),
    Singular(String),
}

impl From<(DomainViolation, &str)> for EvalError {
    fn from((violation, subject): (DomainViolation, &str)) -> Self {
        EvalError::Domain { violation, subject: subject.to_string() }
    }
}

#[derive(Debug, Clone, Default)]
pub struct Detail {
    pub link_flow: Vec<f64>,
    /// Per enclosure, per member: net emitted q (W) for non-sink members, 0 for sinks.
    pub surf_q: Vec<Vec<f64>>,
    /// Per enclosure: (k, l, A_k F_kl (J_k - J_l)) for non-sink k, l != k, F_kl > 0.
    pub pair: Vec<Vec<(usize, usize, f64)>>,
    pub node_rad: Vec<f64>,
    /// Per enclosure, per member: radiation from a node surface to the sinks (W).
    pub surf_to_sink: Vec<Vec<f64>>,
    /// Per enclosure, per member: radiation from node surfaces into a host surface (W).
    pub host_in: Vec<Vec<f64>>,
    pub env: Vec<[f64; 4]>,
    pub src: Vec<f64>,
    pub coil: Vec<f64>,
}

#[derive(Debug, Clone)]
pub struct Eval {
    pub r: Vec<f64>,
    /// Row-major dR_i/dT_j (empty unless requested).
    pub jac: Vec<f64>,
    pub detail: Detail,
}

/// External crossing terms of E-14 at one state.
#[derive(Debug, Clone, Default)]
pub struct Accounting {
    pub inflow: f64,
    pub outflow: f64,
    /// inflow - outflow (= sum_i dH_i/dt).
    pub net: f64,
    /// Sum of magnitudes of every crossing term (Q_abs of CONS-T1).
    pub abs: f64,
    /// NUM-08.
    pub q_scale: f64,
}

fn tv_at(tv: &TimeValue, mid: f64) -> f64 {
    tv.at(mid)
}

impl Factors {
    /// Factors held on the interval with midpoint `mid` (s).
    pub fn window(net: &Net, mid: f64) -> Factors {
        let src = net.sources.iter().map(|s| tv_at(&s.tv, mid)).collect();
        let env = net
            .env
            .iter()
            .map(|e| {
                let s = tv_at(&e.s, mid);
                let v = tv_at(&e.v, mid);
                [
                    s * tv_at(&e.f_sun, mid) * tv_at(&e.nu, mid),
                    tv_at(&e.a, mid) * s * tv_at(&e.f_alb, mid),
                    tv_at(&e.q_olr, mid) * tv_at(&e.f_earth, mid),
                    0.5 * tv_at(&e.rho, mid) * v * v * v.abs() * tv_at(&e.alpha_e, mid),
                ]
            })
            .collect();
        let coil = net
            .coils
            .iter()
            .map(|c| {
                let i = tv_at(&c.i, mid);
                (i * i, tv_at(&c.r_ref, mid), tv_at(&c.t_ref, mid))
            })
            .collect();
        let end_t = |e: &End| match e {
            End::Node(_) => None,
            End::Fixed { t, .. } => Some(tv_at(t, mid)),
        };
        let link_t = net.links.iter().map(|l| (end_t(&l.a), end_t(&l.b))).collect();
        let member_t = net
            .encl
            .iter()
            .map(|e| {
                e.members
                    .iter()
                    .map(|m| match &m.kind {
                        MemberKind::Node { .. } => None,
                        MemberKind::Host { t, .. } | MemberKind::Sink { t, .. } => Some(tv_at(t, mid)),
                    })
                    .collect()
            })
            .collect();
        Factors { src, env, coil, link_t, member_t }
    }

    /// Orbit average over [0, period) (E-12): every product of held values integrated over the union of breakpoints.
    /// Fixed temperatures and coil reference values must be constant (checked by the compiler).
    pub fn orbit_average(net: &Net, period: f64) -> Factors {
        let mut grid = vec![0.0, period];
        let mut push = |tv: &TimeValue| {
            for b in tv.breakpoints() {
                if *b > 0.0 && *b < period {
                    grid.push(*b);
                }
            }
        };
        for s in &net.sources {
            push(&s.tv);
        }
        for e in &net.env {
            for tv in [&e.s, &e.f_sun, &e.nu, &e.a, &e.f_alb, &e.q_olr, &e.f_earth, &e.rho, &e.v, &e.alpha_e] {
                push(tv);
            }
        }
        for c in &net.coils {
            push(&c.i);
        }
        grid.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        grid.dedup();
        let mut acc = Factors::window(net, 0.5 * (grid[0] + grid[1]));
        for v in acc.src.iter_mut() {
            *v = 0.0;
        }
        for e in acc.env.iter_mut() {
            *e = [0.0; 4];
        }
        for c in acc.coil.iter_mut() {
            c.0 = 0.0;
        }
        for w in grid.windows(2) {
            let wt = (w[1] - w[0]) / period;
            let f = Factors::window(net, 0.5 * (w[0] + w[1]));
            for (a, b) in acc.src.iter_mut().zip(&f.src) {
                *a += wt * b;
            }
            for (a, b) in acc.env.iter_mut().zip(&f.env) {
                for j in 0..4 {
                    a[j] += wt * b[j];
                }
            }
            for (a, b) in acc.coil.iter_mut().zip(&f.coil) {
                a.0 += wt * b.0;
            }
        }
        acc
    }
}

fn nonphys(record: &str, what: &str, v: f64) -> EvalError {
    EvalError::Nonphysical(format!("record {record}: {what} = {v} is not physical"))
}

fn eps_check(p: &Prop, v: f64) -> Result<f64, EvalError> {
    if v > 0.0 && v <= 1.0 {
        Ok(v)
    } else {
        Err(nonphys(&p.record_id, "emittance", v))
    }
}

/// Evaluate the residual (and optionally the analytic Jacobian) at temperatures `t`.
pub fn evaluate(net: &Net, t: &[f64], fac: &Factors, want_jac: bool) -> Result<Eval, EvalError> {
    let n = net.ids.len();
    let mut r = vec![0.0; n];
    let mut jac = if want_jac { vec![0.0; n * n] } else { Vec::new() };
    let mut d = Detail { node_rad: vec![0.0; n], ..Default::default() };

    for (k, s) in net.sources.iter().enumerate() {
        let q = s.weight * fac.src[k];
        d.src.push(q);
        r[s.node] += q;
    }

    for (k, c) in net.coils.iter().enumerate() {
        let subj = net.ids[c.node].as_str();
        let (i2, rref, tref) = fac.coil[k];
        let r0 = c.rel.value(tref).map_err(|v| EvalError::from((v, subj)))?;
        let rt = c.rel.value(t[c.node]).map_err(|v| EvalError::from((v, subj)))?;
        if r0 <= 0.0 || rt <= 0.0 {
            return Err(nonphys(&c.rel.record_id, "resistance ratio", r0.min(rt)));
        }
        let q = i2 * rref * rt / r0;
        d.coil.push(q);
        r[c.node] += q;
        if want_jac {
            let dr = c.rel.derivative(t[c.node]).map_err(|v| EvalError::from((v, subj)))?;
            jac[c.node * n + c.node] += i2 * rref * dr / r0;
        }
    }

    for (k, e) in net.env.iter().enumerate() {
        let subj = e.surface_id.as_str();
        let ti = t[e.node];
        let alpha = e.alpha.value(ti).map_err(|v| EvalError::from((v, subj)))?;
        if !(0.0..=1.0).contains(&alpha) {
            return Err(nonphys(&e.alpha.record_id, "absorptance", alpha));
        }
        let eps = eps_check(&e.eps, e.eps.value(ti).map_err(|v| EvalError::from((v, subj)))?)?;
        let f = fac.env[k];
        let comp = [alpha * f[0] * e.area, alpha * f[1] * e.area, eps * f[2] * e.area, f[3] * e.a_ram];
        r[e.node] += comp[0] + comp[1] + comp[2] + comp[3];
        if want_jac {
            let da = e.alpha.derivative(ti).map_err(|v| EvalError::from((v, subj)))?;
            let de = e.eps.derivative(ti).map_err(|v| EvalError::from((v, subj)))?;
            jac[e.node * n + e.node] += da * (f[0] + f[1]) * e.area + de * f[2] * e.area;
        }
        d.env.push(comp);
    }

    for (k, l) in net.links.iter().enumerate() {
        let ta = match l.a {
            End::Node(i) => t[i],
            End::Fixed { .. } => fac.link_t[k].0.unwrap_or(f64::NAN),
        };
        let tb = match l.b {
            End::Node(i) => t[i],
            End::Fixed { .. } => fac.link_t[k].1.unwrap_or(f64::NAN),
        };
        let subj = l.id.as_str();
        let (flow, dfa, dfb) = match &l.kind {
            LinkKind::Conduction { s, k } => {
                let ka = k.value(ta).map_err(|v| EvalError::from((v, subj)))?;
                let kb = k.value(tb).map_err(|v| EvalError::from((v, subj)))?;
                if ka <= 0.0 || kb <= 0.0 {
                    return Err(nonphys(&k.record_id, "thermal conductivity", ka.min(kb)));
                }
                let theta = k.integral(tb, ta).map_err(|v| EvalError::from((v, subj)))?;
                (s * theta, s * ka, -s * kb)
            }
            LinkKind::Linear { g, record_id, t_min, t_max } => {
                for tt in [ta, tb] {
                    if !(tt >= *t_min && tt <= *t_max) {
                        return Err(EvalError::Domain {
                            violation: DomainViolation {
                                record_id: record_id.clone(),
                                t_k: tt,
                                t_min_k: *t_min,
                                t_max_k: *t_max,
                            },
                            subject: subj.to_string(),
                        });
                    }
                }
                (g * (ta - tb), *g, -*g)
            }
        };
        d.link_flow.push(flow);
        if let End::Node(a) = l.a {
            r[a] -= flow;
            if want_jac {
                jac[a * n + a] -= dfa;
                if let End::Node(b) = l.b {
                    jac[a * n + b] -= dfb;
                }
            }
        }
        if let End::Node(b) = l.b {
            r[b] += flow;
            if want_jac {
                jac[b * n + b] += dfb;
                if let End::Node(a) = l.a {
                    jac[b * n + a] += dfa;
                }
            }
        }
    }

    for (ei, e) in net.encl.iter().enumerate() {
        radiosity(net, e, ei, t, fac, want_jac, &mut r, &mut jac, &mut d)?;
    }

    Ok(Eval { r, jac, detail: d })
}

#[allow(clippy::too_many_arguments)]
fn radiosity(
    net: &Net,
    e: &EnclC,
    ei: usize,
    t: &[f64],
    fac: &Factors,
    want_jac: bool,
    r: &mut [f64],
    jac: &mut [f64],
    d: &mut Detail,
) -> Result<(), EvalError> {
    let n = net.ids.len();
    let m = e.members.len();
    let nu = e.unknown.len();
    let mut temp = vec![0.0; m];
    let mut eps = vec![1.0; m];
    let mut deps = vec![0.0; m];
    for (k, mem) in e.members.iter().enumerate() {
        match &mem.kind {
            MemberKind::Node { node, eps: p } => {
                temp[k] = t[*node];
                let subj = mem.surface_id.as_str();
                eps[k] = eps_check(p, p.value(temp[k]).map_err(|v| EvalError::from((v, subj)))?)?;
                deps[k] = p.derivative(temp[k]).map_err(|v| EvalError::from((v, subj)))?;
            }
            MemberKind::Host { eps: p, .. } => {
                temp[k] = fac.member_t[ei][k].unwrap_or(f64::NAN);
                let subj = mem.surface_id.as_str();
                eps[k] = eps_check(p, p.value(temp[k]).map_err(|v| EvalError::from((v, subj)))?)?;
            }
            MemberKind::Sink { .. } => {
                temp[k] = fac.member_t[ei][k].unwrap_or(f64::NAN);
            }
        }
    }
    let eb: Vec<f64> = temp.iter().map(|x| SIGMA * x.powi(4)).collect();
    let mut jv = vec![0.0; m];
    for (k, mem) in e.members.iter().enumerate() {
        if let MemberKind::Sink { .. } = mem.kind {
            jv[k] = eb[k];
        }
    }
    let mut mat = vec![0.0; nu * nu];
    let mut rhs = vec![0.0; nu];
    for (a, &ka) in e.unknown.iter().enumerate() {
        let rho = 1.0 - eps[ka];
        for (b, &kb) in e.unknown.iter().enumerate() {
            mat[a * nu + b] = if a == b { 1.0 } else { 0.0 } - rho * e.f[ka][kb];
        }
        let mut sink_g = 0.0;
        for (l, mem) in e.members.iter().enumerate() {
            if let MemberKind::Sink { .. } = mem.kind {
                sink_g += e.f[ka][l] * jv[l];
            }
        }
        rhs[a] = eps[ka] * eb[ka] + rho * sink_g;
    }
    let lu =
        Lu::factor(mat, nu).ok_or_else(|| EvalError::Singular(format!("radiosity system of enclosure {}", e.id)))?;
    let ju = lu.solve(&rhs);
    for (a, &ka) in e.unknown.iter().enumerate() {
        jv[ka] = ju[a];
    }
    let mut g = vec![0.0; m];
    let mut q = vec![0.0; m];
    let mut to_sink = vec![0.0; m];
    let mut host_in = vec![0.0; m];
    let mut pairs = Vec::new();
    for &ka in &e.unknown {
        g[ka] = (0..m).map(|l| e.f[ka][l] * jv[l]).sum();
        q[ka] = e.members[ka].area * eps[ka] * (eb[ka] - g[ka]);
        for l in 0..m {
            if l != ka && e.f[ka][l] > 0.0 {
                let p = e.members[ka].area * e.f[ka][l] * (jv[ka] - jv[l]);
                pairs.push((ka, l, p));
                if let MemberKind::Node { .. } = e.members[ka].kind {
                    match e.members[l].kind {
                        MemberKind::Sink { .. } => to_sink[ka] += p,
                        MemberKind::Host { .. } => host_in[l] += p,
                        MemberKind::Node { .. } => {}
                    }
                }
            }
        }
        if let MemberKind::Node { node, .. } = e.members[ka].kind {
            r[node] -= q[ka];
            d.node_rad[node] -= q[ka];
        }
    }
    if want_jac {
        let mut nodes_here: Vec<usize> = e
            .members
            .iter()
            .filter_map(|mem| match mem.kind {
                MemberKind::Node { node, .. } => Some(node),
                _ => None,
            })
            .collect();
        nodes_here.sort_unstable();
        nodes_here.dedup();
        for &i in &nodes_here {
            let src: Vec<f64> = e
                .unknown
                .iter()
                .map(|&ka| match e.members[ka].kind {
                    MemberKind::Node { node, .. } if node == i => {
                        deps[ka] * (eb[ka] - g[ka]) + eps[ka] * 4.0 * SIGMA * temp[ka].powi(3)
                    }
                    _ => 0.0,
                })
                .collect();
            let dj = lu.solve(&src);
            for (a, &ka) in e.unknown.iter().enumerate() {
                if let MemberKind::Node { node: mnode, .. } = e.members[ka].kind {
                    let dg: f64 = e.unknown.iter().enumerate().map(|(b, &kb)| e.f[ka][kb] * dj[b]).sum();
                    let dq = e.members[ka].area * (src[a] - eps[ka] * dg);
                    jac[mnode * n + i] -= dq;
                }
            }
        }
    }
    d.surf_q.push(q);
    d.pair.push(pairs);
    d.surf_to_sink.push(to_sink);
    d.host_in.push(host_in);
    Ok(())
}

impl Net {
    /// Heat capacity C_i(T) = sum m c_p(T) (J/K).
    pub fn capacity(&self, i: usize, t: f64) -> Result<f64, EvalError> {
        let mut c = 0.0;
        for (m, cp) in &self.parts[i] {
            let v = cp.value(t).map_err(|v| EvalError::from((v, self.ids[i].as_str())))?;
            if v <= 0.0 {
                return Err(nonphys(&cp.record_id, "specific heat", v));
            }
            c += m * v;
        }
        Ok(c)
    }

    /// Stored-energy change H_i(t1) - H_i(t0) (J), exact for the registered c_p forms.
    pub fn enthalpy_change(&self, i: usize, t0: f64, t1: f64) -> Result<f64, EvalError> {
        let mut h = 0.0;
        for (m, cp) in &self.parts[i] {
            h += m * cp.integral(t0, t1).map_err(|v| EvalError::from((v, self.ids[i].as_str())))?;
        }
        Ok(h)
    }

    /// E-14 crossing terms and NUM-08 Q_scale at one evaluated state.
    pub fn account(&self, ev: &Eval) -> Accounting {
        let n = self.ids.len();
        let d = &ev.detail;
        let mut a = Accounting::default();
        let mut node_src = vec![0.0; n];
        let mut node_tc = vec![0.0; n];
        for (k, s) in self.sources.iter().enumerate() {
            let q = d.src[k];
            a.inflow += q;
            a.abs += q.abs();
            match s.kind {
                SourceKind::Interface => node_src[s.node] += q,
                SourceKind::ThermalControl => node_tc[s.node] += q,
                SourceKind::BoundaryFlux => a.q_scale += q.abs(),
            }
        }
        for (k, c) in self.coils.iter().enumerate() {
            a.inflow += d.coil[k];
            a.abs += d.coil[k].abs();
            node_src[c.node] += d.coil[k];
        }
        for comp in &d.env {
            let s: f64 = comp.iter().sum();
            a.inflow += s;
            a.abs += comp.iter().map(|x| x.abs()).sum::<f64>();
            a.q_scale += s.abs();
        }
        a.q_scale += node_src.iter().map(|x| x.abs()).sum::<f64>() + node_tc.iter().map(|x| x.abs()).sum::<f64>();
        for (k, l) in self.links.iter().enumerate() {
            let out = match (&l.a, &l.b) {
                (End::Node(_), End::Fixed { .. }) => d.link_flow[k],
                (End::Fixed { .. }, End::Node(_)) => -d.link_flow[k],
                _ => continue,
            };
            a.outflow += out;
            a.abs += out.abs();
            a.q_scale += out.abs();
        }
        for (ei, _) in self.encl.iter().enumerate() {
            for x in &d.surf_to_sink[ei] {
                a.outflow += x;
                a.abs += x.abs();
                a.q_scale += x.abs();
            }
            for x in &d.host_in[ei] {
                a.outflow += x;
                a.abs += x.abs();
                a.q_scale += x.abs();
            }
        }
        a.net = a.inflow - a.outflow;
        a
    }
}
