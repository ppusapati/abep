//! The M2 DBF-1 closure record (schema `abep_assess_m2_dbf1_closure_v1`, addendum A8 sec. record). Deterministic:
//! ordered maps and the repository's Python-compatible JSON writer.

use super::dbf1::*;
use super::*;
use crate::closure::{layer_b_status, NOT_EVALUATED as NE};
use crate::error::AssessResult;
use abep_types::pyjson::Dict;
use std::path::Path;

fn d(pairs: Vec<(&str, Value)>) -> Value {
    crate::py::dict(pairs)
}

fn s(x: impl Into<String>) -> Value {
    Value::Str(x.into())
}

fn sl(xs: &[String]) -> Value {
    Value::List(xs.iter().map(|x| s(x.clone())).collect())
}

fn f(x: f64) -> Value {
    Value::Float(x)
}

fn of(x: Option<f64>) -> Value {
    x.map_or(Value::Null, Value::Float)
}

fn i(n: usize) -> Value {
    Value::int(n as i64)
}

fn mode_key(m: Mode) -> &'static str {
    match m {
        Mode::AirPrimary => "AIR_PRIMARY",
        _ => "XE_CONTINGENCY",
    }
}

fn counts(it: impl Iterator<Item = String>) -> Value {
    let mut c: BTreeMap<String, usize> = BTreeMap::new();
    for k in it {
        *c.entry(k).or_default() += 1;
    }
    Value::Dict(c.into_iter().map(|(k, v)| (k, i(v))).collect())
}

fn constraint_value(c: &Constraint) -> Value {
    d(vec![
        ("id", s(c.id.clone())),
        ("hall_specific", Value::Bool(c.hall_specific)),
        ("status", s(c.status)),
        ("eligible_close", Value::Bool(c.eligible_close)),
        ("eligible_non_close", Value::Bool(c.eligible_non_close)),
        ("codes", sl(&c.codes)),
        ("detail", s(c.detail.clone())),
    ])
}

fn minmax(v: &[f64]) -> (f64, f64) {
    (v.iter().copied().fold(f64::INFINITY, f64::min), v.iter().copied().fold(f64::NEG_INFINITY, f64::max))
}

fn levels_value(sa: &StateA8, scen: &[String]) -> Value {
    let mut o = Dict::new();
    for ((l, t), e) in &sa.levels {
        o.insert(
            format!("{}|{}", l.as_str(), TARGETS[*t]),
            d(vec![
                ("verdict", s(e.verdict)),
                ("k_fav", of(e.k_fav)),
                ("k_unfav", of(e.k_unfav)),
                ("k_by_scenario", Value::Dict(scen.iter().zip(&e.k).map(|(sc, k)| (sc.clone(), of(*k))).collect())),
            ]),
        );
    }
    Value::Dict(o)
}

fn air_state(inp: &Dbf1Inputs, i: usize, sa: &StateA8) -> Value {
    let dr = &inp.drag[i];
    let scen: Vec<String> = inp.scenarios.iter().map(|x| x.scenario.clone()).collect();
    let rows: Vec<Value> = inp
        .scenarios
        .iter()
        .enumerate()
        .map(|(j, sc)| {
            let p = &sc.points[i];
            d(vec![
                ("scenario", s(sc.scenario.clone())),
                ("in_domain", Value::Bool(p.in_domain)),
                ("steady_reasons", sl(&p.reasons)),
                ("feed_stability_class", s(p.class.clone())),
                ("re_lambda_max_per_s", of(p.re_max)),
                ("mdot_cap_kg_s", f(p.mdot_cap)),
                ("mdot_del_kg_s", if p.in_domain { f(p.mdot_del) } else { Value::Null }),
                (
                    "x_mole_O_N2_O2",
                    if p.in_domain { Value::List(p.x_mole.iter().map(|x| f(*x)).collect()) } else { Value::Null },
                ),
                ("P_compressor_el_W", if p.in_domain { f(p.p_el_w) } else { Value::Null }),
                ("D_intake_mN", f(dr.d_intake_n[j] * 1e3)),
                ("D_total_mN", f(dr.d_total_n[j] * 1e3)),
                ("T_required_mN", f(dr.d_total_n[j] * 1e3)),
                ("mdot_req_in_TD_kg_s", of(sa.mdot_req_in_td.get(j).copied().flatten())),
                ("A_req_TD_m2", of(sa.a_req_td.get(j).copied().flatten())),
            ])
        })
        .collect();
    let (tmin, tmax) = minmax(&dr.d_total_n);
    d(vec![
        ("q_Pa", f(dr.q_pa)),
        ("D_body_mN", f(dr.d_body_n * 1e3)),
        ("drag_flags", sl(&dr.flags)),
        ("T_required_mN_min_max", Value::List(vec![f(tmin * 1e3), f(tmax * 1e3)])),
        ("mdot_req_in_T12_T25_kg_s", Value::List(sa.mdot_req_in.iter().map(|x| of(*x)).collect())),
        ("mdot_del_held_min_max_kg_s", sa.mdot_del_range.map_or(Value::Null, |r| Value::List(vec![f(r.0), f(r.1)]))),
        ("out_of_domain_scenarios", sl(&sa.ood_scenarios)),
        ("unstable_scenarios", sl(&sa.unstable_scenarios)),
        ("compressor_min_W", of(sa.compressor_min_w)),
        ("levels", levels_value(sa, &scen)),
        ("scenarios", Value::List(rows)),
        (
            "drag_sensitivity_body_mN",
            Value::Dict(dr.sensitivity.iter().map(|(c, x)| (c.clone(), f(x * 1e3))).collect()),
        ),
    ])
}

fn cell_value(inp: &Dbf1Inputs, m: Mode, c: &CellA8, comp: Option<f64>) -> Value {
    let ti = &inp.base.today;
    let b = &c.eval.bus;
    let pm = &inp.cfg.power_mass;
    let p_common_lb = if m == Mode::AirPrimary { comp.unwrap_or(0.0) } else { 0.0 };
    d(vec![
        ("layer_a_status", s(c.eval.eval.status)),
        ("layer_b_status", s(layer_b_status(&ti.matrix, m, ti.credible_set_empty))),
        ("blockers", sl(&c.eval.eval.blockers)),
        (
            "binding_constraint",
            c.binding.as_ref().map_or(Value::Null, |(id, code, cat)| {
                d(vec![
                    ("constraint", s(id.clone())),
                    ("code", s(code.clone())),
                    ("category", s(cat.clone())),
                    ("blocker_type", s(blocker_type(code))),
                ])
            }),
        ),
        ("hall_closure", s(if c.eval.hall.iter().all(|h| h.constraint.eligible_close) { "CLOSES" } else { NE })),
        (
            "non_hall_closure",
            s(if c.eval.eval.constraints.iter().filter(|x| !x.hall_specific).any(|x| x.eligible_non_close) {
                "PHYSICS_NON_CLOSING"
            } else if c.eval.eval.constraints.iter().filter(|x| !x.hall_specific).any(|x| x.status == NON_CLOSING) {
                "NON_CLOSING_NOT_ELIGIBLE"
            } else if c.eval.eval.constraints.iter().filter(|x| !x.hall_specific).all(|x| x.eligible_close) {
                "CLOSES"
            } else {
                "OPEN"
            }),
        ),
        ("constraints", Value::List(c.eval.eval.constraints.iter().map(constraint_value).collect())),
        (
            "bus_layer_a",
            d(vec![
                ("P_nonHall_LB_W", f(b.lb_w)),
                ("P_nonHall_LB_eligible_W", f(b.lb_eligible_w)),
                ("n_tbd_terms", i(b.tbd.len())),
                ("P_common_LB_W", f(p_common_lb)),
                ("margin_common_allocation_W", f(pm.common_allocation_w - p_common_lb)),
                ("margin_design_allocation_W", f(pm.design_allocation_w - b.lb_w)),
                ("margin_HC03_W", f(ti.limits.p_bus_max_w - b.lb_w)),
                ("role", s("lower bounds (TBD loads 0 W); allocation margins are design information, never RFP gates")),
            ]),
        ),
    ])
}

fn level_summary(inp: &Dbf1Inputs, out: &Dbf1Outcome) -> Value {
    let mut o = Dict::new();
    for (t, target) in TARGETS.iter().enumerate() {
        for l in Lvl::ALL {
            let mut c: BTreeMap<&str, usize> = BTreeMap::new();
            let mut worst: Option<(usize, f64)> = None;
            for (idx, sa) in out.air.iter().enumerate() {
                if let Some(e) = sa.levels.get(&(l, t)) {
                    *c.entry(e.verdict).or_default() += 1;
                    let k = e.k_fav.unwrap_or(f64::INFINITY);
                    if worst.is_none_or(|w| k > w.1) {
                        worst = Some((idx, k));
                    }
                } else {
                    *c.entry(NE).or_default() += 1;
                }
            }
            o.insert(
                format!("{}|{target}", l.as_str()),
                d(vec![
                    ("state_verdict_counts", Value::Dict(c.into_iter().map(|(k, v)| (k.to_string(), i(v))).collect())),
                    (
                        "worst_state",
                        worst.map_or(Value::Null, |(idx, k)| {
                            d(vec![
                                ("state_id", s(inp.base.today.states[idx].state_id.clone())),
                                ("k_fav", if k.is_finite() { f(k) } else { Value::Null }),
                            ])
                        }),
                    ),
                ]),
            );
        }
    }
    Value::Dict(o)
}

fn t_required(inp: &Dbf1Inputs, ti: &crate::closure::TodayInputs) -> Value {
    let (t12, t25) = (ti.limits.thrust_min_n, ti.limits.thrust_capability_n);
    let bucket = |x: f64| {
        if x <= t12 {
            "LE_HC01_12mN"
        } else if x <= t25 {
            "HC01_TO_HC02_12_25mN"
        } else {
            "GT_HC02_25mN"
        }
    };
    let mins: Vec<f64> = inp.drag.iter().map(|x| minmax(&x.d_total_n).0).collect();
    let maxs: Vec<f64> = inp.drag.iter().map(|x| minmax(&x.d_total_n).1).collect();
    let body: Vec<f64> = inp.drag.iter().map(|x| x.d_body_n).collect();
    let intake: Vec<f64> = inp.drag.iter().flat_map(|x| x.d_intake_n.iter().copied()).collect();
    let (wi, _) = maxs.iter().enumerate().fold((0, f64::NEG_INFINITY), |a, (k, v)| if *v > a.1 { (k, *v) } else { a });
    let (bi, _) = mins.iter().enumerate().fold((0, f64::INFINITY), |a, (k, v)| if *v < a.1 { (k, *v) } else { a });
    let mut sens = Dict::new();
    for (k, (c, _)) in inp.drag[0].sensitivity.iter().enumerate() {
        let v: Vec<f64> = inp.drag.iter().map(|x| x.sensitivity[k].1).collect();
        let (a, b) = minmax(&v);
        sens.insert(c.as_str(), Value::List(vec![f(a * 1e3), f(b * 1e3)]));
    }
    let mm = |v: &[f64]| {
        let (a, b) = minmax(v);
        Value::List(vec![f(a * 1e3), f(b * 1e3)])
    };
    d(vec![
        (
            "definition",
            s("T_required(state, scenario) = D(state, scenario) = q (C_D A)_RC-DIAMANT + F1 intake-face drag x 0.25 m^2 \
               (T - D >= 0, A9.13 S6.15); REFERENCE_PENDING_CUSTOMER_ICD"),
        ),
        ("HC01_mN", f(t12 * 1e3)),
        ("HC02_mN", f(t25 * 1e3)),
        ("range_over_states_and_scenarios_mN", mm(&maxs.iter().chain(&mins).copied().collect::<Vec<_>>())),
        ("D_body_range_mN", mm(&body)),
        ("D_intake_range_mN", mm(&intake)),
        ("distribution_unfavourable_scenario (state max)", counts(maxs.iter().map(|x| bucket(*x).to_string()))),
        ("distribution_favourable_scenario (state min)", counts(mins.iter().map(|x| bucket(*x).to_string()))),
        (
            "worst_state",
            d(vec![
                ("state_id", s(inp.base.today.states[wi].state_id.clone())),
                ("T_required_max_mN", f(maxs[wi] * 1e3)),
            ]),
        ),
        (
            "lowest_state",
            d(vec![
                ("state_id", s(inp.base.today.states[bi].state_id.clone())),
                ("T_required_min_mN", f(mins[bi] * 1e3)),
            ]),
        ),
        ("body_sensitivity_range_mN_by_case", Value::Dict(sens)),
    ])
}

fn ranked_bindings(out: &Dbf1Outcome, m: Mode) -> Value {
    let mut c: BTreeMap<(String, String, String), usize> = BTreeMap::new();
    for (st, ms) in &out.states {
        if !st.required {
            continue;
        }
        if let Some((id, code, cat)) = ms.get(&m).and_then(|x| x.binding.clone()) {
            *c.entry((id, code, cat)).or_default() += 1;
        }
    }
    let mut v: Vec<_> = c.into_iter().collect();
    v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    Value::List(
        v.into_iter()
            .map(|((id, code, cat), n)| {
                d(vec![
                    ("constraint", s(id)),
                    ("code", s(code.clone())),
                    ("category", s(cat)),
                    ("blocker_type", s(blocker_type(&code))),
                    ("n_states", i(n)),
                ])
            })
            .collect(),
    )
}

fn constraint_counts(out: &Dbf1Outcome, m: Mode) -> Value {
    let mut c: BTreeMap<String, BTreeMap<String, usize>> = BTreeMap::new();
    for (st, ms) in &out.states {
        if !st.required {
            continue;
        }
        if let Some(e) = ms.get(&m) {
            for x in &e.eval.eval.constraints {
                let key = if x.eligible_non_close { format!("{}_ELIGIBLE", x.status) } else { x.status.to_string() };
                *c.entry(x.id.clone()).or_default().entry(key).or_default() += 1;
            }
        }
    }
    Value::Dict(c.into_iter().map(|(k, v)| (k, Value::Dict(v.into_iter().map(|(a, b)| (a, i(b))).collect()))).collect())
}

/// The A9.31 sec. 20 conclusion-category input (not the M3 decision).
fn conclusion_input(out: &Dbf1Outcome) -> Value {
    let o = &out.outcome;
    let (cat, text) = match o.classification {
        PHYSICALLY_NON_CLOSING => ("C", "ARCHITECTURE DOES NOT CURRENTLY CLOSE (an eligible evaluated non-closure)"),
        SELECT_WITH_EVIDENCE_CONDITIONS => ("B", "ARCHITECTURE APPEARS FEASIBLE BUT IS NOT YET PROVEN"),
        _ => ("D", "MODEL CANNOT YET DETERMINE ARCHITECTURE FEASIBILITY"),
    };
    d(vec![
        ("category_input", s(cat)),
        ("text", s(text)),
        (
            "missing_items_first",
            Value::List(
                o.blockers
                    .iter()
                    .filter(|b| b.0 == HALL_NUMERICS_NOT_CONVERGED)
                    .map(|b| d(vec![("code", s(b.0.clone())), ("cells", i(b.1))]))
                    .collect(),
            ),
        ),
        (
            "rule",
            s("computed from the A9.32 classification of this record: PHYSICALLY_NON_CLOSING -> C, \
               SELECT_WITH_EVIDENCE_CONDITIONS -> B, NOT_DETERMINABLE -> D; an input to the coordinator's M3 decision, \
               not the decision"),
        ),
    ])
}

/// The M2 DBF-1 record.
pub fn record_dbf1(inp: &Dbf1Inputs, out: &Dbf1Outcome, run_label: &str) -> AssessResult<Value> {
    let ti = &inp.base.today;
    let o = &out.outcome;
    let blockers: Vec<Value> = o
        .blockers
        .iter()
        .map(|(c, n)| {
            d(vec![
                ("code", s(c.clone())),
                ("cells", i(*n)),
                ("category", s(category_a8(c))),
                ("blocker_type", s(blocker_type(c))),
            ])
        })
        .collect();
    let mut per_mode = Dict::new();
    for m in REQUIRED_MODES {
        let cells: Vec<&CellA8> = out.states.iter().filter(|x| x.0.required).filter_map(|x| x.1.get(&m)).collect();
        per_mode.insert(
            mode_key(m),
            d(vec![
                ("n_required_states", i(cells.len())),
                ("layer_a_status_counts", counts(cells.iter().map(|c| c.eval.eval.status.to_string()))),
                (
                    "layer_b_status_counts",
                    counts(cells.iter().map(|_| layer_b_status(&ti.matrix, m, ti.credible_set_empty).to_string())),
                ),
                (
                    "hall_closure_counts",
                    counts(cells.iter().map(|c| {
                        if c.eval.hall.iter().all(|h| h.constraint.eligible_close) { "CLOSES" } else { NE }.to_string()
                    })),
                ),
                ("constraint_status_counts", constraint_counts(out, m)),
                ("binding_constraints_ranked", ranked_bindings(out, m)),
            ]),
        );
    }
    let states: Vec<Value> = out
        .states
        .iter()
        .enumerate()
        .map(|(idx, (st, ms))| {
            let sa = &out.air[idx];
            let mut row = vec![("state_id", s(st.state_id.clone())), ("required", Value::Bool(st.required))];
            for m in REQUIRED_MODES {
                if let Some(c) = ms.get(&m) {
                    row.push((mode_key(m), cell_value(inp, m, c, sa.compressor_min_w)));
                }
            }
            row.push(("air_dbf1", air_state(inp, idx, sa)));
            d(row)
        })
        .collect();
    let icp: Dict = inp
        .icp
        .modes
        .iter()
        .map(|(m, x)| {
            (
                mode_key(*m).to_string(),
                d(vec![
                    ("case_id", s(x.case_id.clone())),
                    ("status", s(x.status.clone())),
                    ("I_e_cap_fav_A", of(x.i_e_cap_fav_a)),
                    ("codes", sl(&x.codes)),
                    ("load_codes", sl(&x.load_codes)),
                    ("summary", x.summary.clone()),
                ]),
            )
        })
        .collect();
    let xcheck: Vec<Value> = inp
        .scenarios
        .iter()
        .map(|x| {
            d(vec![
                ("scenario", s(x.scenario.clone())),
                ("f7_member_in_this_scenario", Value::Bool(x.committed_min.is_some())),
                ("committed_min_kg_s", of(x.committed_min)),
                ("rerun_min_kg_s", f(x.rerun_min)),
                ("n_in_domain_states", i(x.points.iter().filter(|p| p.in_domain).count())),
                ("n_held_states", i(x.points.iter().filter(|p| p.held()).count())),
            ])
        })
        .collect();
    let pm = &inp.cfg.power_mass;
    let mass = d(vec![
        ("policy_margin_fraction", f(pm.mass_margin_fraction)),
        ("nominal_dry_target_kg", f(pm.nominal_dry_target_kg)),
        ("xe_reference_load_kg", f(pm.xe_reference_load_kg)),
        ("wet_target_at_reference_kg", f(pm.wet_target_at_reference_kg)),
        ("planning_nominal_dry_kg", f(pm.planning_nominal_dry_kg)),
        ("planning_wet_kg_at_reference", f(pm.planning_wet_kg_at_reference)),
        ("nominal_dry_margin_to_target_kg", f(pm.nominal_dry_target_kg - pm.planning_nominal_dry_kg)),
        ("HC04_limit_kg", of(ti.thresholds.limit("HC-04"))),
        ("status", s("planning values only (no CBE): NH-MASS OPEN, never eligible (HR-07); DBF1-BD-03 / BD-04")),
        ("objective", inp.base.mass.info.clone()),
    ]);
    let prov: Vec<Value> =
        inp.provenance.iter().map(|(p, h)| d(vec![("path", s(p.clone())), ("sha256", s(h.clone()))])).collect();
    Ok(d(vec![
        ("schema", s(RECORD_SCHEMA)),
        ("model_id", s("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("milestone", s("M2_196_STATE_RFP_CLOSURE")),
        ("run_label", s(run_label)),
        ("label", s(LABEL)),
        ("architecture", s("hall_icp_neutralizer")),
        ("rust_commit", s(ti.mission.provenance.rust_commit.clone())),
        (
            "addendum_a8",
            d(vec![("path", s(A8_REL)), ("sha256", s(A8_SHA256)), ("lock_sha256", s(A8_LOCK_SHA256))]),
        ),
        (
            "dbf1",
            d(vec![
                ("lock", s(abep_config::baseline::DBF1_LOCK_SHA256)),
                ("record", s(abep_config::baseline::DBF1_RECORD_SHA256)),
                ("config", s(abep_config::baseline::DBF1_CONFIG_SHA256)),
                ("design_id", s(inp.cfg.upstream.design_id.clone())),
                (
                    "hardware_configuration",
                    Value::List(vec![s(inp.cfg.geometry_id.clone()), s(inp.cfg.bz_shape_id.clone())]),
                ),
                ("reference_host_drag", s(format!("{} (REFERENCE_PENDING_CUSTOMER_ICD)", inp.cfg.drag.case_id))),
                ("baseline_deficiencies", sl(&inp.cfg.baseline_deficiencies)),
            ]),
        ),
        (
            "thresholds",
            d(vec![
                ("HC-01_N", f(ti.limits.thrust_min_n)),
                ("HC-02_N", f(ti.limits.thrust_capability_n)),
                ("HC-03_W", f(ti.limits.p_bus_max_w)),
                ("source", s("abep-config thresholds (assessment only)")),
            ]),
        ),
        (
            "hall",
            d(vec![
                ("rule", s("A9.36: no Hall envelope ingested; every Hall test NOT_EVALUATED (HALL_NUMERICS_NOT_CONVERGED); no Hall thrust / I_d / P_d enters M2")),
                ("category", s(category_a8(HALL_NUMERICS_NOT_CONVERGED))),
                ("blocker_type", s(blocker_type(HALL_NUMERICS_NOT_CONVERGED))),
            ]),
        ),
        (
            "classification",
            d(vec![
                ("result", s(o.classification)),
                ("procedure_step", s(o.step)),
                ("blockers", Value::List(blockers)),
                ("evidence_conditions", sl(&o.evidence_conditions)),
                ("procedure", s("C0, CA4 (A4), C1..C4 verbatim (A9.32); C1 blocker read as HALL_NUMERICS_NOT_CONVERGED (A8)")),
            ]),
        ),
        ("conclusion_category_input_a9_31_sec_20", conclusion_input(out)),
        ("per_mode", Value::Dict(per_mode)),
        ("t_required_vs_rfp", t_required(inp, ti)),
        ("dbf1_necessary_conditions", level_summary(inp, out)),
        (
            "feed_stability",
            d(vec![
                ("authoritative", s("governed Python reference (A9.34)")),
                ("reference", d(vec![("path", s(inp.stability.reference_rel.clone())), ("sha256", s(inp.stability.reference_sha256.clone()))])),
                ("environment", inp.stability.environment.clone()),
                ("rust_cross_check_R2", d(vec![("n_rows", i(inp.stability.n_rows)), ("n_agree", i(inp.stability.n_agree))])),
                (
                    "class_counts",
                    Value::Dict(inp.stability.counts.iter().map(|(k, v)| (k.clone(), i(*v))).collect()),
                ),
            ]),
        ),
        ("upstream_scenarios", Value::List(xcheck)),
        ("icp_dbf1", Value::Dict(icp)),
        ("mass_dbf1", mass),
        ("states", Value::List(states)),
        ("provenance", Value::List(prov)),
        (
            "what_this_is_not",
            crate::py::strs(&[
                "not a performance prediction: every DBF-1 requirement test is an A4 necessary condition at its favourable limit",
                "not the M3 architecture decision",
                "not a change of DBF-1, of any RFP requirement or of any admitted / scored record",
                "no Hall thrust value (A9.36)",
            ]),
        ),
    ]))
}

/// Gather, evaluate and render (the `--m2-dbf1` entry).
pub fn m2_dbf1_record(
    repo: &Path,
    stability_rel: &Path,
    stability_sha256: &str,
    rust_commit: &str,
    run_label: &str,
) -> AssessResult<Value> {
    let inp = gather_dbf1(repo, stability_rel, stability_sha256, rust_commit)?;
    let out = evaluate_dbf1(&inp)?;
    record_dbf1(&inp, &out, run_label)
}
