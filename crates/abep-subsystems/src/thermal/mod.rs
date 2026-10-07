//! NP-THERMAL-CATHODELESS v1 (model version 1.0.0): the cathodeless Hall + downstream RF/ICP neutralizer lumped thermal
//! network of `docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/prereg_v1.json` (sha256 in
//! [`governance::PREREG_SHA256`]).
//!
//! * Configuration `hall_icp_neutralizer` only. There is no cathode node, no Q_cath and no keeper or emitter term; such
//!   identifiers are refused (EX-01, EX-02, FT-10).
//! * Heat enters only through IF-HALL-THERMAL-v1, IF-ICP-THERMAL-v1, `Q_thermal_control_W`, the environment and the
//!   boundaries (HS-00). Map-derived Hall heat is NOT_EVALUATED while the credible transport set is EMPTY.
//! * Raw physics: temperatures, heat flows, energy balances and diagnostics. No margin, limit, PASS / FAIL or HC status
//!   (EX-03, EX-04); every output carries `validation_status = NOT_VALIDATED`.
//!
//! Entry point: [`run_case`] with a [`GovernedContext`] loaded from the repository and the [`RunContext`] of the build.

pub mod assemble;
pub mod case;
pub mod governance;
pub mod linalg;
pub mod network;
pub mod output;
pub mod props;
pub mod series;
pub mod solver;
pub mod vocab;

use assemble::{assemble, assemble_v2, Compiled, Mode};
pub use case::ThermalCase;
pub use governance::{GovernedContext, GovernedContextV2};
use network::{End, Factors, MemberKind, SourceKind};
use output::*;
use solver::{Fail, SteadyOut, TransientOut};
use std::collections::BTreeMap;

pub const MODEL_ID: &str = "NP-THERMAL-CATHODELESS";
pub const MODEL_VERSION: &str = "1.0.0";
pub const A9_STATUS: &str = "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE";
/// D-02 lumped-capacitance criterion (Incropera & DeWitt; verify V-01).
pub const BIOT_MAX: f64 = 0.1;

/// Build provenance supplied by the caller (for example from `abep_provenance::run_record::RunRecord`).
#[derive(Debug, Clone)]
pub struct RunContext {
    pub rust_commit: String,
    pub rust_tree_dirty: bool,
}

fn provenance(
    case_class: &str,
    supply_mode: &str,
    design_state_id: Option<String>,
    gov: &GovernedContext,
    run: &RunContext,
) -> Provenance {
    let mut binding = BTreeMap::new();
    binding.insert("anode_thermal_closure".to_string(), "UNRESOLVED".to_string());
    binding.insert("coupled_h1_icp_thermal_closure".to_string(), "UNRESOLVED".to_string());
    binding.insert(
        "credible_hall_transport_set".to_string(),
        if gov.admitted_hall_members().is_empty() { "EMPTY".to_string() } else { "NON_EMPTY".to_string() },
    );
    binding.insert("flight_hollow_cathode".to_string(), "NONE".to_string());
    Provenance {
        model_id: MODEL_ID.into(),
        model_version: MODEL_VERSION.into(),
        prereg_sha256: governance::PREREG_SHA256.into(),
        prereg_md_sha256: governance::PREREG_MD_SHA256.into(),
        implementation: "rust".into(),
        rust_commit: run.rust_commit.clone(),
        rust_tree_dirty: run.rust_tree_dirty,
        input_set_sha256: String::new(),
        interface_record_sha256: BTreeMap::new(),
        governed_record_sha256: gov.hashes().clone(),
        hallthruster_commit_pinned: gov.hallthruster_commit().into(),
        case_class: case_class.into(),
        supply_mode: supply_mode.into(),
        design_state_id,
        ensemble_member_ids: Vec::new(),
        a9_status: A9_STATUS.into(),
        binding_statuses: binding,
        validation_status: NOT_VALIDATED.into(),
        scenario_member_id: None,
        producer_lock_sha256: None,
    }
}

/// Parse and run a case document (`abep_np_thermal_case_v1`). An unparsable document is a MODEL_ERROR output.
pub fn run_case_json(bytes: &[u8], gov: &GovernedContext, run: &RunContext) -> ThermalOutput {
    match serde_json::from_slice::<ThermalCase>(bytes) {
        Ok(case) => run_case(&case, gov, run),
        Err(e) => {
            let mut prov = provenance("UNPARSED", "UNPARSED", None, gov, run);
            prov.input_set_sha256 = abep_provenance::sha256_hex(bytes);
            let reasons = vec![Reason {
                status: RunStatus::ModelError,
                code: "CASE_MALFORMED".into(),
                subject: "case".into(),
                detail: e.to_string(),
            }];
            ThermalOutput {
                schema: OUTPUT_SCHEMA.into(),
                model_id: MODEL_ID.into(),
                model_version: MODEL_VERSION.into(),
                case_id: "UNPARSED".into(),
                case_class: "UNPARSED".into(),
                solver_mode: "UNPARSED".into(),
                run_status: RunStatus::ModelError,
                status_reasons: reasons,
                labels: Vec::new(),
                results: None,
                domain_diagnostics: None,
                provenance: prov,
                validation_status: NOT_VALIDATED.into(),
            }
        }
    }
}

fn fail_reason(f: &Fail) -> Reason {
    match f {
        Fail::Domain { subject, record_id, t_k, range, detail } => Reason {
            status: RunStatus::OutOfDomain,
            code: "PROPERTY_RANGE_EXCEEDED".into(),
            subject: subject.clone(),
            detail: format!("{detail}; record {record_id}, T = {t_k} K, range [{}, {}] K", range[0], range[1]),
        },
        Fail::Model { code, subject, detail } => Reason {
            status: RunStatus::ModelError,
            code: code.clone(),
            subject: subject.clone(),
            detail: detail.clone(),
        },
    }
}

/// Run one case. Status precedence: record / topology validation, evidence availability, solve, domain checks.
pub fn run_case(case: &ThermalCase, gov: &GovernedContext, run: &RunContext) -> ThermalOutput {
    let asm = assemble(case, gov);
    let prov = provenance(&case.case_class, &case.supply_mode, case.design_state_id.clone(), gov, run);
    finish(case, asm, prov, run, MODEL_VERSION, OUTPUT_SCHEMA)
}

/// Model 2.0.0 (NP-THERMAL-CATHODELESS prereg v2): run one case that consumes IF-ICP-THERMAL-v2 (one producer
/// scenario member). The v1 entry point `run_case` and its outputs are unchanged.
pub fn run_case_v2(case: &ThermalCase, gov: &GovernedContextV2, run: &RunContext) -> ThermalOutput {
    let asm = assemble_v2(case, gov);
    let mut prov = provenance(&case.case_class, &case.supply_mode, case.design_state_id.clone(), gov.v1(), run);
    prov.model_version = vocab::MODEL_VERSION_V2.into();
    prov.prereg_sha256 = gov.prereg_v2_sha256().into();
    prov.prereg_md_sha256 = gov.prereg_v2_md_sha256().into();
    prov.governed_record_sha256 = gov.hashes();
    prov.producer_lock_sha256 = Some(governance::PRODUCER_LOCK_SHA256.into());
    prov.scenario_member_id = case.interfaces.icp_v2.as_ref().map(|r| r.scenario_member_id.clone());
    finish(case, asm, prov, run, vocab::MODEL_VERSION_V2, OUTPUT_SCHEMA_V2)
}

fn finish(
    case: &ThermalCase,
    asm: assemble::Assembly,
    mut prov: Provenance,
    run: &RunContext,
    model_version: &str,
    schema: &str,
) -> ThermalOutput {
    prov.input_set_sha256 = asm.input_set_sha256.clone();
    prov.interface_record_sha256 = asm.interface_hashes.clone();
    prov.ensemble_member_ids = asm.ensemble_member_ids.iter().cloned().collect();
    let mut reasons = asm.reasons.clone();
    if run.rust_commit.is_empty() {
        reasons.push(Reason {
            status: RunStatus::ModelError,
            code: "RUN_PROVENANCE_MISSING".into(),
            subject: "rust_commit".into(),
            detail: "every output carries the Rust commit (DET-03, O-17)".into(),
        });
    }
    let mut results = None;
    let mut diag = None;
    if let (Some(c), true) = (&asm.compiled, reasons.is_empty()) {
        let (r, d, extra) = solve_and_report(c);
        reasons.extend(extra);
        diag = Some(d);
        if reasons.is_empty() {
            results = r;
        }
    }
    reasons.sort();
    reasons.dedup_by(|a, b| a.status == b.status && a.code == b.code && a.subject == b.subject);
    let status = run_status(&reasons);
    if status != RunStatus::Converged {
        results = None;
        if let Some(d) = diag.as_mut() {
            // On refusal no temperature is emitted (outputs.on_refusal); diagnostics keep the criterion and value.
            if status != RunStatus::OutOfDomain {
                *d = DomainDiagnostics { violations: d.violations.clone(), ..Default::default() };
            } else {
                d.time_constant_s.clear();
                d.internal_gradient_estimate_k.clear();
            }
        }
    }
    ThermalOutput {
        schema: schema.into(),
        model_id: MODEL_ID.into(),
        model_version: model_version.into(),
        case_id: case.case_id.clone(),
        case_class: case.case_class.clone(),
        solver_mode: case.solver.mode.clone(),
        run_status: status,
        status_reasons: reasons,
        labels: asm.labels.iter().cloned().collect(),
        results,
        domain_diagnostics: diag,
        provenance: prov,
        validation_status: NOT_VALIDATED.into(),
    }
}

fn node_map(ids: &[String], v: &[f64]) -> BTreeMap<String, f64> {
    ids.iter().cloned().zip(v.iter().copied()).collect()
}

/// Solve the compiled case and build the raw outputs. Returns (results, diagnostics, reasons found).
fn solve_and_report(c: &Compiled) -> (Option<Results>, DomainDiagnostics, Vec<Reason>) {
    let ids = &c.net.ids;
    let n = ids.len();
    let mut diag = DomainDiagnostics::default();
    let ranges = match c.mode {
        Mode::Steady | Mode::OrbitAverageSteady { .. } => &c.ranges_steady,
        _ => &c.ranges_transient,
    };
    for (i, r) in ranges.iter().enumerate() {
        diag.node_property_range_k.insert(ids[i].clone(), [r.lo, r.hi]);
    }
    let want_biot = c.biot.iter().any(Option::is_some);
    let mut steady_out: Option<SteadyOut> = None;
    let mut trans_out: Option<TransientOut> = None;
    let solved = match c.mode {
        Mode::Steady => solver::steady(c, &Factors::window(&c.net, 0.0)).map(|s| steady_out = Some(s)),
        Mode::OrbitAverageSteady { period } => {
            solver::steady(c, &Factors::orbit_average(&c.net, period)).map(|s| steady_out = Some(s))
        }
        Mode::Transient { t0, t1, dt } => solver::transient(c, t0, t1, dt, want_biot).map(|o| trans_out = Some(o)),
        Mode::OrbitPeriodic { period, dt } => solver::periodic(c, period, dt, want_biot).map(|o| trans_out = Some(o)),
    };
    if let Err(f) = solved {
        let reason = fail_reason(&f);
        if reason.status == RunStatus::OutOfDomain {
            diag.violations.push(reason.clone());
        }
        return (None, diag, vec![reason]);
    }
    let state = match (&steady_out, &trans_out) {
        (Some(s), _) => s.state.clone(),
        (_, Some(t)) => t.final_state.clone(),
        _ => unreachable!("one solver ran"),
    };
    let mut reasons = Vec::new();

    // Domain checks at the solution (D-02 Biot for non-synthetic cases; D-09 time constants).
    let g_lin = match (&trans_out, solver::conductance_sum(c, &state.t)) {
        (Some(t), Ok(_)) => Ok(t.g_lin_max.clone()),
        (None, g) => g,
        (_, Err(e)) => Err(e),
    };
    let g_lin = match g_lin {
        Ok(g) => g,
        Err(f) => return (None, diag, vec![fail_reason(&f)]),
    };
    let throughput = node_throughput(c, &state.ev);
    for i in 0..n {
        if let Some(b) = &c.biot[i] {
            let states: Vec<f64> = match &trans_out {
                Some(t) => t.states_for_biot.iter().map(|s| s[i]).collect(),
                None => vec![state.t[i]],
            };
            let mut kmin = f64::INFINITY;
            for t in &states {
                match b.k.value(*t) {
                    Ok(k) => kmin = kmin.min(k),
                    Err(v) => {
                        let r = Reason {
                            status: RunStatus::OutOfDomain,
                            code: "PROPERTY_RANGE_EXCEEDED".into(),
                            subject: ids[i].clone(),
                            detail: format!("Biot conductivity record {} at {} K (D-01)", v.record_id, v.t_k),
                        };
                        diag.violations.push(r.clone());
                        reasons.push(r);
                    }
                }
            }
            if kmin.is_finite() {
                let bi = g_lin[i] * b.volume / (b.area * b.area * kmin);
                diag.biot_number.insert(ids[i].clone(), bi);
                diag.internal_gradient_estimate_k
                    .insert(ids[i].clone(), throughput[i] * b.volume / (b.area * b.area * kmin));
                if bi > BIOT_MAX {
                    let r = Reason {
                        status: RunStatus::OutOfDomain,
                        code: "BIOT_NUMBER_EXCEEDED".into(),
                        subject: ids[i].clone(),
                        detail: format!("Bi = {bi} > {BIOT_MAX} (D-02); remedy: a registered subdivision"),
                    };
                    diag.violations.push(r.clone());
                    reasons.push(r);
                }
            }
        }
    }
    let mut tau_max: f64 = 0.0;
    for i in 0..n {
        let in_range = c.net.parts[i].iter().all(|(_, cp)| cp.in_domain(state.t[i]));
        if in_range && g_lin[i] > 0.0 {
            if let Ok(cap) = c.net.capacity(i, state.t[i]) {
                let tau = cap / g_lin[i];
                tau_max = tau_max.max(tau);
                diag.time_constant_s.insert(ids[i].clone(), tau);
            }
        }
    }
    if let Mode::OrbitAverageSteady { period } | Mode::OrbitPeriodic { period, .. } = c.mode {
        diag.largest_time_constant_over_period = Some(tau_max / period);
    }

    // Energy balance (O-14) and conservation checks.
    let acc = &state.acc;
    let tol_s = solver::cons_s_tol(acc);
    let mut checks = Vec::new();
    let max_r = state.ev.r.iter().fold(0.0_f64, |m, x| m.max(x.abs()));
    let mut energy = EnergyBalance {
        node_residual_w: node_map(ids, &state.ev.r),
        global_residual_w: acc.net,
        q_scale_w: acc.q_scale,
        cumulative_energy_residual_j: None,
        worst_step_energy_residual_j: None,
        checks: Vec::new(),
    };
    let mut conv = ConvergenceOut::default();
    let mut res = Results::default();
    match (&steady_out, &trans_out) {
        (Some(s), _) => {
            checks.push(CheckOut { id: "CONS-S1".into(), observed: max_r, bound: tol_s, met: max_r <= tol_s });
            checks.push(CheckOut {
                id: "CONS-S2".into(),
                observed: acc.net.abs(),
                bound: tol_s,
                met: acc.net.abs() <= tol_s,
            });
            conv.newton_iterations = s.iterations;
            conv.last_max_dt_k = s.last_dt;
            res.t_node_k = Some(node_map(ids, &state.t));
        }
        (_, Some(t)) => {
            let e = &t.energy;
            checks.push(CheckOut {
                id: "CONS-T1.step".into(),
                observed: e.worst_step.0,
                bound: e.worst_step.1,
                met: e.worst_step.0 <= e.worst_step.1,
            });
            checks.push(CheckOut {
                id: "CONS-T1.cumulative".into(),
                observed: e.worst_cumulative.0,
                bound: e.worst_cumulative.1,
                met: e.worst_cumulative.0 <= e.worst_cumulative.1,
            });
            checks.push(CheckOut {
                id: "CONS-T2".into(),
                observed: t.u_num,
                bound: solver::CONS_T2_K,
                met: t.u_num <= solver::CONS_T2_K,
            });
            energy.cumulative_energy_residual_j = Some(e.final_cumulative.0);
            energy.worst_step_energy_residual_j = Some(e.worst_step.0);
            conv.u_num_t_k = Some(t.u_num);
            conv.accepted_steps = Some(t.steps);
            conv.max_newton_iterations_per_step = Some(t.max_iters);
            conv.max_step_halving_depth = Some(t.max_depth);
            let mut series: BTreeMap<String, Vec<f64>> = BTreeMap::new();
            for (i, id) in ids.iter().enumerate() {
                series.insert(id.clone(), t.temps.iter().map(|s| s[i]).collect());
            }
            res.t_node_k_series = Some(series);
            res.t_s = Some(t.times.clone());
            res.dh_node_j = Some(node_map(ids, &t.dh_node));
            res.heat_flows_at_t_s = Some(t.final_time);
            if let Some((orbits, d, stats)) = &t.orbits {
                checks.push(CheckOut {
                    id: "CONS-T3".into(),
                    observed: *d,
                    bound: solver::CONS_T3_K,
                    met: *d <= solver::CONS_T3_K,
                });
                conv.orbits = Some(*orbits);
                conv.periodic_max_dt_k = Some(*d);
                res.t_node_orbit_stats_k = Some(
                    stats
                        .iter()
                        .enumerate()
                        .map(|(k, s)| OrbitStats {
                            orbit: k + 1,
                            min: node_map(ids, &s.min),
                            max: node_map(ids, &s.max),
                            mean: node_map(ids, &s.mean),
                        })
                        .collect(),
                );
            }
        }
        _ => unreachable!("one solver ran"),
    }
    if let Some(d) = &c.derived {
        checks.push(CheckOut {
            id: "CONS-I2".into(),
            observed: d.cons_i2_residual_w,
            bound: d.cons_i2_bound_w,
            met: d.cons_i2_residual_w <= d.cons_i2_bound_w,
        });
        // Model 2.0.0 only (absent from every v1 run).
        if let Some((r, b)) = d.icp_v2.as_ref().and_then(|v| v.cons_i3_residual_w.zip(v.cons_i3_bound_w)) {
            checks.push(CheckOut { id: "CONS-I3".into(), observed: r, bound: b, met: r <= b });
        }
    }
    for ch in &checks {
        if !ch.met {
            reasons.push(Reason {
                status: RunStatus::ModelError,
                code: "CONSERVATION_CRITERION_NOT_MET".into(),
                subject: ch.id.clone(),
                detail: format!("observed {:e} > bound {:e}", ch.observed, ch.bound),
            });
        }
    }
    energy.checks = checks;
    res.energy_balance = energy;
    res.convergence = conv;
    fill_flows(c, &state, &mut res);
    (Some(res), diag, reasons)
}

/// Half the sum of the magnitudes of every heat term of each node (its throughput at a balanced state).
fn node_throughput(c: &Compiled, ev: &network::Eval) -> Vec<f64> {
    let net = &c.net;
    let d = &ev.detail;
    let mut s = vec![0.0; net.ids.len()];
    for (k, src) in net.sources.iter().enumerate() {
        s[src.node] += d.src[k].abs();
    }
    for (k, coil) in net.coils.iter().enumerate() {
        s[coil.node] += d.coil[k].abs();
    }
    for (k, e) in net.env.iter().enumerate() {
        s[e.node] += d.env[k].iter().map(|x| x.abs()).sum::<f64>();
    }
    for (k, l) in net.links.iter().enumerate() {
        for end in [&l.a, &l.b] {
            if let End::Node(i) = end {
                s[*i] += d.link_flow[k].abs();
            }
        }
    }
    for (ei, e) in net.encl.iter().enumerate() {
        for (m, mem) in e.members.iter().enumerate() {
            if let MemberKind::Node { node, .. } = mem.kind {
                s[node] += d.surf_q[ei][m].abs();
            }
        }
    }
    s.iter().map(|x| 0.5 * x).collect()
}

fn fill_flows(c: &Compiled, state: &solver::State, res: &mut Results) {
    let net = &c.net;
    let ids = &net.ids;
    let d = &state.ev.detail;
    for (k, l) in net.links.iter().enumerate() {
        res.q_link_w.insert(l.id.clone(), d.link_flow[k]);
        let out = match (&l.a, &l.b) {
            (End::Node(_), End::Fixed { .. }) => Some(d.link_flow[k]),
            (End::Fixed { .. }, End::Node(_)) => Some(-d.link_flow[k]),
            _ => None,
        };
        if let (Some(out), Some(b)) = (out, &c.link_boundary[k]) {
            match b.as_str() {
                "B_SC" => res.q_boundary_w.b_sc_links.insert(l.id.clone(), out),
                "B_PPU_RF" => res.q_boundary_w.b_ppu_rf_links.insert(l.id.clone(), out),
                _ => res.q_boundary_w.b_feed_links.insert(l.id.clone(), out),
            };
        }
    }
    let mut per_surface = BTreeMap::new();
    let mut pairwise = Vec::new();
    let mut to_sink: BTreeMap<String, f64> = ids.iter().map(|i| (i.clone(), 0.0)).collect();
    for (ei, e) in net.encl.iter().enumerate() {
        for (m, mem) in e.members.iter().enumerate() {
            match mem.kind {
                MemberKind::Sink { .. } => {}
                MemberKind::Node { node, .. } => {
                    per_surface.insert(mem.surface_id.clone(), -d.surf_q[ei][m]);
                    *to_sink.get_mut(&ids[node]).expect("node") += d.surf_to_sink[ei][m];
                }
                MemberKind::Host { .. } => {
                    per_surface.insert(mem.surface_id.clone(), -d.surf_q[ei][m]);
                    res.q_boundary_w.b_sc_radiation.insert(mem.surface_id.clone(), d.host_in[ei][m]);
                }
            }
        }
        for (k, l, q) in &d.pair[ei] {
            pairwise.push(PairExchange {
                from: e.members[*k].surface_id.clone(),
                to: e.members[*l].surface_id.clone(),
                q_w: *q,
            });
        }
    }
    res.q_rad_net_w = RadiationOut { per_surface, per_node: node_map(ids, &d.node_rad), pairwise };
    res.q_to_sink_w = to_sink;
    for (k, e) in net.env.iter().enumerate() {
        let x = d.env[k];
        res.q_env_abs_w.insert(e.surface_id.clone(), EnvOut { solar: x[0], albedo: x[1], olr: x[2], aero: x[3] });
    }
    for (k, s) in net.sources.iter().enumerate() {
        match s.kind {
            SourceKind::BoundaryFlux => {
                let id = s.label.trim_start_matches("SCI-B:").to_string();
                res.q_boundary_w.b_sc_prescribed_flux.insert(id, d.src[k]);
            }
            _ => {
                *res.q_source_node_w.entry(ids[s.node].clone()).or_default().entry(s.label.clone()).or_insert(0.0) +=
                    d.src[k];
            }
        }
    }
    for (k, coil) in net.coils.iter().enumerate() {
        let key = vocab::COILS.iter().find(|x| x.3 == coil.key).map_or(coil.key.clone(), |x| x.2.to_string());
        *res.q_source_node_w.entry(ids[coil.node].clone()).or_default().entry(key).or_insert(0.0) += d.coil[k];
    }
    res.p_exported_w = c.exported.clone();
    res.q_boundary_w.b_ppu_rf_booked = c.booked.clone();
    res.interface_derived = c.derived.clone();
}

#[cfg(test)]
mod tests;
