//! Orchestration and assessment of the P7 thermal closure (prereg `cases`, `margin_rule`, `limits`, `design_levers`,
//! `allowables`, `sensitivities`, `boundary_units`, `closure_state_rule`). The thermal crate returns raw temperatures;
//! every comparison with a limit happens here.

use super::build::{build, Beta, Flux, Solver, Spec};
use super::env;
use super::loads::{loads, operating_point, LoadSet, OperatingPoint};
use super::{num, s, ClosureError, Context, MARGIN_K};
use abep_subsystems::thermal::output::{RunStatus, ThermalOutput};
use abep_subsystems::thermal::run_case_v2;
use serde_json::{json, Value};
use std::collections::BTreeMap;

pub const K0: f64 = 273.15;
pub const SIGMA: f64 = 5.670374419e-8;
const STEADY_STARTS: [f64; 4] = [500.0, 350.0, 800.0, 1100.0];

/// Raw result of one case (no verdict).
#[derive(Debug, Clone)]
pub struct CaseRun {
    pub id: String,
    pub status: RunStatus,
    pub reasons: Vec<String>,
    /// Steady: T; periodic: max over the converged orbit [K].
    pub t_max_k: BTreeMap<String, f64>,
    /// Steady: T; periodic: min over the converged orbit [K].
    pub t_min_k: BTreeMap<String, f64>,
    pub q_sc_w: Option<f64>,
    pub biot_max: Option<f64>,
    pub case_sha256: String,
    /// Property-range violations: node -> T [K] at which the range was left.
    pub range_exceeded: BTreeMap<String, f64>,
}

impl CaseRun {
    pub fn converged(&self) -> bool {
        self.status == RunStatus::Converged
    }
}

fn status_str(s: RunStatus) -> String {
    serde_json::to_value(s).ok().and_then(|v| v.as_str().map(String::from)).unwrap_or_default()
}

fn nodes_of(ctx: &Context) -> Vec<String> {
    ctx.prereg.nodes.iter().filter_map(|n| n["id"].as_str().map(String::from)).collect()
}

fn run_once(ctx: &Context, spec: &Spec) -> Result<(ThermalOutput, String), ClosureError> {
    let case = build(&ctx.prereg, spec)?;
    let bytes = serde_json::to_vec(&case).map_err(|e| ClosureError(e.to_string()))?;
    Ok((run_case_v2(&case, &ctx.gov, &ctx.run), abep_provenance::sha256_hex(&bytes)))
}

fn summarize(id: &str, out: &ThermalOutput, sha: String) -> CaseRun {
    let mut r = CaseRun {
        id: id.into(),
        status: out.run_status,
        reasons: out
            .status_reasons
            .iter()
            .map(|x| format!("{}:{}:{}", status_str(x.status), x.code, x.subject))
            .collect(),
        t_max_k: BTreeMap::new(),
        t_min_k: BTreeMap::new(),
        q_sc_w: None,
        biot_max: out.domain_diagnostics.as_ref().and_then(|d| d.biot_number.values().cloned().reduce(f64::max)),
        case_sha256: sha,
        range_exceeded: BTreeMap::new(),
    };
    for x in &out.status_reasons {
        if x.code == "PROPERTY_RANGE_EXCEEDED" {
            let t = x.detail.split("T = ").nth(1).and_then(|t| t.split(' ').next()).and_then(|t| t.parse::<f64>().ok());
            r.range_exceeded.insert(x.subject.clone(), t.unwrap_or(f64::NAN));
        }
    }
    if let Some(res) = &out.results {
        if let Some(t) = &res.t_node_k {
            r.t_max_k = t.clone();
            r.t_min_k = t.clone();
        }
        if let Some(stats) = res.t_node_orbit_stats_k.as_ref().and_then(|v| v.last()) {
            r.t_max_k = stats.max.clone();
            r.t_min_k = stats.min.clone();
        }
        r.q_sc_w = Some(res.q_boundary_w.b_sc_links.values().sum());
    }
    r
}

/// Run one case per the prereg `solver_initial` rule.
pub fn run_case(ctx: &Context, spec: &Spec) -> Result<CaseRun, ClosureError> {
    let nodes = nodes_of(ctx);
    let init = |t: f64| -> BTreeMap<String, f64> { nodes.iter().map(|n| (n.clone(), t)).collect() };
    let steady = |mut sp: Spec| -> Result<(CaseRun, BTreeMap<String, f64>), ClosureError> {
        let mut last = None;
        for t0 in STEADY_STARTS {
            sp.t_init = init(t0);
            let (out, sha) = run_once(ctx, &sp)?;
            let run = summarize(&sp.id, &out, sha);
            let t = out.results.as_ref().and_then(|r| r.t_node_k.clone()).unwrap_or_default();
            let fatal = matches!(run.status, RunStatus::ModelError)
                && !run.reasons.iter().any(|x| x.contains("NOT_CONVERGED") || x.contains("SINGULAR"));
            if run.converged() || fatal || matches!(run.status, RunStatus::NotEvaluated | RunStatus::IncompleteEvidence)
            {
                return Ok((run, t));
            }
            last = Some((run, t));
        }
        Ok(last.expect("at least one start"))
    };
    match spec.solver {
        Solver::Steady => Ok(steady(spec.clone())?.0),
        Solver::OrbitAverage => Ok(steady(spec.clone())?.0),
        Solver::Periodic => {
            let mut pre = spec.clone();
            pre.solver = Solver::OrbitAverage;
            let (r0, t0) = steady(pre)?;
            if !r0.converged() {
                let mut r = r0;
                r.id = spec.id.clone();
                r.reasons.insert(0, "ORBIT_AVERAGE_PRE_SOLVE_NOT_CONVERGED".into());
                return Ok(r);
            }
            let mut sp = spec.clone();
            sp.t_init = t0;
            let (out, sha) = run_once(ctx, &sp)?;
            Ok(summarize(&spec.id, &out, sha))
        }
    }
}

// ------------------------------------------------------------------------------------------------ case specs

/// Design-lever and override context of a family of runs.
#[derive(Debug, Clone, Default)]
pub struct Variant {
    pub a_rh: f64,
    pub g_rh: f64,
    pub link_overrides: BTreeMap<String, BTreeMap<String, Value>>,
    pub input_overrides: BTreeMap<String, f64>,
    pub t_sc_override: Option<f64>,
    pub op_edit: Option<OpEdit>,
    pub heater: Option<(String, f64)>,
}

/// A one-quantity edit of the operating point (allowables).
#[derive(Debug, Clone, Copy)]
pub enum OpEdit {
    PD(f64),
    PFwd(f64),
    Plume(f64),
    Return(f64),
}

pub fn spec_for(ctx: &Context, case: &Value, v: &Variant) -> Result<Spec, ClosureError> {
    let id = s(case, "id")?;
    let alt = num(case, "alt_km")?;
    let beta = if case["beta"].as_str() == Some("B0") { Beta::Zero } else { Beta::Star };
    let solver = match case["solver"].as_str() {
        Some("STEADY") => Solver::Steady,
        Some("ORBIT_TRANSIENT_PERIODIC") => Solver::Periodic,
        _ => return Err(ClosureError(format!("{id}: solver"))),
    };
    let flux = if case["flux"].as_str() == Some("cold") { Flux::Cold } else { Flux::Hot };
    let tsc = &ctx.prereg.raw["boundary_temperatures"]["T_SC_K"];
    let t_sc = v.t_sc_override.unwrap_or(if case["T_SC"].as_str() == Some("cold") {
        num(tsc, "cold")?
    } else {
        num(tsc, "hot")?
    });
    let set = LoadSet::parse(case["load_set"].as_str().unwrap_or(""))
        .ok_or_else(|| ClosureError(format!("{id}: load_set")))?;
    let mut op: OperatingPoint = operating_point(&ctx.inputs, set, &v.input_overrides)?;
    match v.op_edit {
        Some(OpEdit::PD(x)) => op.p_d_w = x,
        Some(OpEdit::PFwd(x)) => op.p_fwd_w = x,
        Some(OpEdit::Plume(x)) => op.plume_w = x,
        Some(OpEdit::Return(x)) => op.return_override_w = Some(x),
        None => {}
    }
    let l = loads(&ctx.inputs, set, op, num(case, "factor")?, ctx.rho(alt)?)?;
    Ok(Spec {
        id,
        alt_km: alt,
        beta,
        solver,
        flux,
        t_sc_k: t_sc,
        supply_mode: s(case, "supply_mode")?,
        a_rh: v.a_rh,
        g_rh: v.g_rh,
        link_overrides: v.link_overrides.clone(),
        loads: l,
        t_init: BTreeMap::new(),
        heater: v.heater.clone(),
    })
}

pub fn case_def(ctx: &Context, id: &str) -> Result<Value, ClosureError> {
    ctx.prereg.raw["cases"]
        .as_array()
        .and_then(|a| a.iter().find(|c| c["id"].as_str() == Some(id)).cloned())
        .ok_or_else(|| ClosureError(format!("case {id} not registered")))
}

pub fn run_named(ctx: &Context, id: &str, v: &Variant) -> Result<CaseRun, ClosureError> {
    let c = case_def(ctx, id)?;
    run_case(ctx, &spec_for(ctx, &c, v)?)
}

// ------------------------------------------------------------------------------------------------ limits and verdicts

#[derive(Debug, Clone)]
pub struct Limit {
    pub node: String,
    pub upper_c: Option<f64>,
    pub class: String,
    pub absolute_c: Option<f64>,
    pub lower_op_c: Option<f64>,
    pub lower_nonop_c: Option<f64>,
    pub basis: String,
}

pub fn limits(ctx: &Context) -> Vec<Limit> {
    ctx.prereg.raw["limits"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .map(|l| Limit {
            node: l["node"].as_str().unwrap_or("").into(),
            upper_c: l["upper_C"].as_f64(),
            class: l["class"].as_str().unwrap_or("").into(),
            absolute_c: l["absolute_ceiling_C"].as_f64(),
            lower_op_c: l["lower_operating_C"].as_f64(),
            lower_nonop_c: l["lower_nonoperating_C"].as_f64(),
            basis: l["basis"].as_str().unwrap_or("").into(),
        })
        .collect()
}

/// H-1 nodes whose limit drives the design-lever selection (non-REQUIREMENT_ONLY in the Hall groups).
pub fn h1_limited(ctx: &Context, lims: &[Limit]) -> Vec<String> {
    let groups: BTreeMap<String, String> = ctx
        .prereg
        .nodes
        .iter()
        .filter_map(|n| Some((n["id"].as_str()?.to_string(), n["group"].as_str()?.to_string())))
        .collect();
    lims.iter()
        .filter(|l| {
            l.upper_c.is_some() && matches!(groups.get(&l.node).map(String::as_str), Some("HALL_BODY" | "HALL_MAGNET"))
        })
        .map(|l| l.node.clone())
        .collect()
}

/// Margin to the rule [K]: (limit - 50 K) - T; positive passes.
pub fn margin(lim: &Limit, t_k: f64) -> Option<f64> {
    lim.upper_c.map(|u| u - MARGIN_K - (t_k - K0))
}

/// Min over `nodes` of the rule margin in one run (None when the run did not converge).
pub fn min_margin(run: &CaseRun, lims: &[Limit], nodes: &[String]) -> Option<f64> {
    if !run.converged() {
        return None;
    }
    let mut m = f64::INFINITY;
    for n in nodes {
        let lim = lims.iter().find(|l| &l.node == n)?;
        m = m.min(margin(lim, *run.t_max_k.get(n)?)?);
    }
    Some(m)
}

// ------------------------------------------------------------------------------------------------ allowables

/// Largest x in [0, hi] for which `ok(x)` holds (monotone), bisection to `tol` or `iters`. None when ok(0) fails.
pub fn bisect(
    mut ok: impl FnMut(f64) -> Result<bool, ClosureError>,
    hi: f64,
    tol: f64,
    iters: usize,
) -> Result<Option<f64>, ClosureError> {
    if !ok(0.0)? {
        return Ok(None);
    }
    if ok(hi)? {
        return Ok(Some(hi));
    }
    let (mut lo, mut up) = (0.0, hi);
    for _ in 0..iters {
        if up - lo <= tol {
            break;
        }
        let mid = 0.5 * (lo + up);
        if ok(mid)? {
            lo = mid;
        } else {
            up = mid;
        }
    }
    Ok(Some(lo))
}

pub fn node_ok(run: &CaseRun, lim: &Limit) -> bool {
    run.converged() && run.t_max_k.get(&lim.node).and_then(|t| margin(lim, *t)).is_some_and(|m| m >= 0.0)
}

// ------------------------------------------------------------------------------------------------ boundary units

pub fn eps_sigma_t4(eps: f64, t_k: f64) -> f64 {
    eps * SIGMA * t_k.powi(4)
}

/// Zenith-panel orbit-average absorbed flux [W/m^2]: hot = max over BSTAR / B0 at 180 km with the hot S; cold = B0 at
/// 230 km with the cold S.
pub fn zenith_q(ctx: &Context, hot: bool, alpha: f64) -> Result<f64, ClosureError> {
    let fl = &ctx.prereg.raw["environment"]["fluxes"][if hot { "hot" } else { "cold" }];
    let s_w = num(fl, "S_W_m2")?;
    Ok(if hot {
        env::zenith_orbit_average(180.0, env::beta_star(180.0), alpha, s_w)
            .max(env::zenith_orbit_average(180.0, 0.0, alpha, s_w))
    } else {
        env::zenith_orbit_average(230.0, 0.0, alpha, s_w)
    })
}

pub fn input(ctx: &Context, path: &str) -> Result<f64, ClosureError> {
    let mut v = &ctx.inputs;
    for k in path.split('.') {
        v = &v[k];
    }
    num(v, "value")
}

/// Boundary-unit rejection requirements (prereg `boundary_units`).
pub fn boundary_units(ctx: &Context) -> Result<Value, ClosureError> {
    let alpha = 0.17;
    let eps = 0.92;
    let q_hot = zenith_q(ctx, true, alpha)?;
    let q_cold = zenith_q(ctx, false, alpha)?;
    let pd_hot = input(ctx, "discharge.P_d_hot_W")?;
    let band_lo = ctx.inputs["discharge"]["P_d_band_W"]["value"][0].as_f64().unwrap_or(f64::NAN);
    let (eta_d, eta_mag, p_hk, eta_hk, p_v, eta_v) = (
        input(ctx, "ppu.eta_d")?,
        input(ctx, "ppu.eta_mag")?,
        input(ctx, "ppu.P_hk_out_W")?,
        input(ctx, "ppu.eta_hk")?,
        input(ctx, "ppu.P_valve_out_W")?,
        input(ctx, "ppu.eta_valve")?,
    );
    let mag_hot = input(ctx, "coils.hot_inner_W")? + input(ctx, "coils.hot_outer_W")?;
    let mag_cold = input(ctx, "coils.cold_inner_W")? + input(ctx, "coils.cold_outer_W")?;
    let ppu = |pd: f64, mag: f64| {
        pd * (1.0 / eta_d - 1.0) + mag * (1.0 / eta_mag - 1.0) + p_hk * (1.0 / eta_hk - 1.0) + p_v * (1.0 / eta_v - 1.0)
    };
    let eta_rf = input(ctx, "icp.eta_RF")?;
    let refl = input(ctx, "icp.P_refl_frac")?;
    let rf = |p: f64| p * (1.0 / eta_rf - 1.0) + refl * p;
    let (p_anchor, p_max) = (input(ctx, "icp.P_fwd_anchor_W")?, input(ctx, "icp.P_fwd_max_W")?);
    let comp = input(ctx, "compressor.P_el_max_W")? / input(ctx, "compressor.eta_drive")?;
    let units = &ctx.prereg.raw["boundary_units"]["units"];
    let t_sc_hot = num(&ctx.prereg.raw["boundary_temperatures"]["T_SC_K"], "hot")?;
    let mut out = serde_json::Map::new();
    for (name, q_hot_unit, q_cold_op) in [
        ("PPU", 1.2 * ppu(pd_hot, mag_hot).max(ppu(band_lo, mag_hot)), ppu(band_lo, mag_cold) / 1.2),
        ("RF_GENERATOR", 1.2 * rf(p_anchor).max(rf(p_max)), rf(p_anchor) / 1.2),
        ("COMPRESSOR_MOTOR", 1.2 * comp, comp / 1.2),
    ] {
        let u = &units[name];
        let up = num(u, "upper_limit_C")?;
        let t_d = up - MARGIN_K + K0;
        let net = eps_sigma_t4(eps, t_d) - q_hot;
        let area = if net > 0.0 { Some(q_hot_unit / net) } else { None };
        let mut o = json!({
            "Q_hot_W": q_hot_unit,
            "Q_cold_operating_W": q_cold_op,
            "upper_limit_C": up,
            "design_temperature_C": up - MARGIN_K,
            "class": u["class"],
            "q_abs_hot_W_m2": q_hot,
            "q_abs_cold_W_m2": q_cold,
            "radiator_area_m2": area,
        });
        if let Some(a) = area {
            for (key, low) in [
                ("lower_operating_C", u["lower_operating_C"].as_f64()),
                ("lower_nonoperating_C", u["lower_nonoperating_C"].as_f64()),
            ] {
                if let Some(low) = low {
                    let q_in = if key == "lower_operating_C" { q_cold_op } else { 0.0 };
                    let heater = (a * (eps_sigma_t4(eps, low + K0) - q_cold) - q_in).max(0.0);
                    o[format!("heater_W_at_{key}")] = json!(heater);
                }
            }
        }
        if name == "COMPRESSOR_MOTOR" {
            o["host_conductance_W_K"] = json!(q_hot_unit / (t_d - t_sc_hot));
            o["flag"] = u["flag"].clone();
        }
        out.insert(name.into(), o);
    }
    Ok(Value::Object(out))
}
