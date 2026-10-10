//! Records of addendum A5: the `intake_closure_a5` block of the harness v2 record and the standalone record
//! `intake_closure_a5_v1.json` (schema `abep_assess_intake_closure_a5_v1`; A5 sec. record). Deterministic: ordered
//! maps and the repository's Python-compatible JSON writer.

use super::intake::*;
use super::record::{d, strs};
use super::*;
use crate::error::{model_error, AssessResult};
use std::path::Path;

pub const LABEL: &str = "ACTUAL_DESIGN_EVALUATION / PARAMETRIC_SENSITIVITY / NOT_A_PERFORMANCE_PREDICTION";

fn s(x: impl Into<String>) -> Value {
    Value::Str(x.into())
}

/// A finite float, or null (an unbounded multiplier).
fn f(x: f64) -> Value {
    if x.is_finite() {
        Value::Float(x)
    } else {
        Value::Null
    }
}

fn of(x: Option<f64>) -> Value {
    x.map_or(Value::Null, f)
}

fn sl(xs: &[String]) -> Value {
    Value::List(xs.iter().map(|x| s(x.clone())).collect())
}

fn i(n: usize) -> Value {
    Value::int(n as i64)
}

fn key(l: Level, k: usize) -> String {
    format!("{}|{}", l.as_str(), TESTS[k])
}

const CURRENT_DESIGN_RECORDS: [&str; 5] = [
    "architecture_freeze_candidate_v1.json AFC-UP-IN-01: intake frontal area PARETO_SET, robust set EMPTY, nominal Pareto union {0.25} m^2, no member selected, OPEN",
    "f8_study_v1.json carried_robust_set: members [], representative REFUSED (A9.13 S6.20)",
    "A9.13 S6.20 (F9-OQ-01): carry the robust Pareto set; defer representative selection; evaluate all remaining Pareto members",
    "F1_INTAKE_SYNTHESIS.md: INVESTIGATION_HYPOTHESIS, DESIGN_SYNTHESIS_SCREENING_NOT_A_SELECTION",
    "H2_7_MECHANICAL_BOM.md R01 intake: BLOCKED on DI-1.1 / DI-1.2; no intake in config/hardware",
];

/// The worst required A_req(s, 12 mN) of the A4 outcome and its state (the A9.35 carry-forward numbers).
fn carry_forward(a5: &IntakeOutcome) -> Value {
    let w = a5
        .states
        .iter()
        .filter(|x| x.required)
        .filter_map(|x| x.req.map(|r| (x, r)))
        .max_by(|a, b| a.1.a_req[0].total_cmp(&b.1.a_req[0]));
    match w {
        Some((x, r)) => d(vec![
            ("worst_state", s(x.state_id.clone())),
            ("A_req_T12_m2", f(r.a_req[0])),
            ("A_req_T25_m2", f(r.a_req[1])),
            ("mdot_req_T12_kg_s", f(r.mdot_req[0])),
            ("mdot_req_T25_kg_s", f(r.mdot_req[1])),
            ("P_avail_W", f(r.p_avail_w)),
            ("source", s("A4 outcome of the same harness run (conservation_bounds_v1.json kernels)")),
        ]),
        None => s(NOT_EVALUATED),
    }
}

fn ds_value(a5: &IntakeInputs, o: &IntakeOutcome) -> Value {
    let mut adm: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut areas: BTreeSet<String> = BTreeSet::new();
    for (ra, _) in &o.cand_rows {
        if ra.admissible {
            adm.entry(ra.scenario.clone()).or_default().push(ra.id.clone());
            let c = a5.candidates.iter().find(|c| c.id == ra.id).expect("candidate");
            areas.insert(format!("{}", c.area_m2));
        }
    }
    let mut by_role: BTreeMap<String, usize> = BTreeMap::new();
    let mut by_f8: BTreeMap<String, usize> = BTreeMap::new();
    for m in &a5.members {
        *by_role.entry(m.context_role.clone()).or_default() += 1;
        *by_f8.entry(m.f8_status.clone()).or_default() += 1;
    }
    let tally = |m: BTreeMap<String, usize>| Value::Dict(m.into_iter().map(|(k, n)| (k, i(n))).collect());
    let mut grid_areas: Vec<f64> = a5.candidates.iter().map(|c| c.area_m2).collect();
    grid_areas.sort_by(f64::total_cmp);
    grid_areas.dedup();
    d(vec![
        ("current_design", s("NONE_SELECTED")),
        ("current_design_records", strs(&CURRENT_DESIGN_RECORDS)),
        (
            "DS-F1-GRID",
            d(vec![
                ("n_candidates", i(a5.candidates.len())),
                ("areas_m2", Value::List(grid_areas.into_iter().map(f).collect())),
                ("scenarios", sl(&a5.scenarios)),
                ("d_collapsed", s("channel diameter collapsed: every TPMC output is d-invariant at fixed L/d (F1-02)")),
            ]),
        ),
        (
            "DS-F1-ADMISSIBLE",
            d(vec![
                ("rule", s("FEASIBLE_AT_STATE at every required state (F1 C-CONV, C-DRAG-RFP); a FROZEN area limit excludes larger candidates")),
                ("n_per_scenario", Value::Dict(a5.scenarios.iter().map(|sc| (sc.clone(), i(adm.get(sc).map_or(0, Vec::len)))).collect())),
                ("areas_m2", sl(&areas.into_iter().collect::<Vec<_>>())),
                ("candidates_by_scenario", Value::Dict(adm.into_iter().map(|(k, v)| (k, sl(&v))).collect())),
            ]),
        ),
        (
            "DS-F7-PARETO",
            d(vec![
                ("n_members", i(a5.members.len())),
                ("by_context_role", tally(by_role)),
                ("by_f8_status", tally(by_f8)),
                (
                    "cross_check",
                    d(vec![
                        ("rule", s("A5.1: every state of the Rust rerun in domain; statewise minimum within max(4 ulp, 1e-9 relative) of the committed F7 capture")),
                        ("max_ulp", i(a5.members.iter().map(|m| ulp_distance(m.mdot_delivered_min_rerun_kgps, m.mdot_delivered_min_kgps)).max().unwrap_or(0) as usize)),
                        ("n_not_bit_identical", i(a5.members.iter().filter(|m| m.mdot_delivered_min_rerun_kgps.to_bits() != m.mdot_delivered_min_kgps.to_bits()).count())),
                        ("values_used", s("Rust rerun (admitted implementation, A9.24 item 1)")),
                    ]),
                ),
            ]),
        ),
        (
            "DS-F8",
            d(vec![
                ("robust_set", s(if a5.robust_members.is_empty() { "EMPTY" } else { "NON_EMPTY" })),
                ("robust_members", sl(&a5.robust_members)),
                ("n_survivors", i(a5.f8_survivors.len())),
                ("decomposition", a5.f8_decomposition.clone()),
            ]),
        ),
    ])
}

fn level_value(l: Level, k: usize, a5: &IntakeInputs, o: &IntakeOutcome) -> Value {
    let mut counts: BTreeMap<String, usize> = BTreeMap::new();
    for x in o.states.iter().filter(|x| x.required) {
        let v = x.levels.get(&(l, k)).map_or(NOT_EVALUATED, |y| y.verdict);
        *counts.entry(v.to_string()).or_default() += 1;
    }
    let worst = match o.worst.get(&(l, k)).copied().flatten() {
        Some((idx, kf)) => {
            let st = &o.states[idx];
            let ls = &st.levels[&(l, k)];
            let r = st.req.expect("evaluated");
            let mut pairs = vec![
                ("state_id", s(st.state_id.clone())),
                ("k_fav", of(kf)),
                ("k_unfav", of(ls.k_unfav)),
                ("fav_design", ls.fav.as_ref().map_or(Value::Null, |x| s(x.0.clone()))),
                ("fav_scenario", ls.fav.as_ref().map_or(Value::Null, |x| s(x.1.clone()))),
                ("unfav_design", ls.unfav.as_ref().map_or(Value::Null, |x| s(x.0.clone()))),
                ("unfav_scenario", ls.unfav.as_ref().map_or(Value::Null, |x| s(x.1.clone()))),
                ("no_design_scenarios", sl(&ls.no_design_scenarios)),
                ("A_req_m2", f(r.a_req[k])),
                ("mdot_req_A9_35_kg_s", f(r.mdot_req[k])),
            ];
            if let Some((dsg, sc)) = &ls.fav {
                match l {
                    Level::Area | Level::Cap => {
                        let ci = a5.candidates.iter().position(|c| &c.id == dsg).expect("candidate");
                        let c = &a5.candidates[ci];
                        pairs.push(("A_eff_m2", f(c.area_m2)));
                        pairs.push(("mdot_req_in_kg_s", f(r.mdot_req_in(c.area_m2, k, o.t_req_n).unwrap_or(f64::NAN))));
                        if let Some(v) = design_values(a5, o, ci, sc, idx) {
                            pairs.push(("mdot_cap_kg_s", f(v.mdot_cap)));
                            pairs.push(("eta_c", f(v.eta_c)));
                            pairs.push(("eta_tot", f(v.eta_tot)));
                            pairs.push(("eta_vs_bound", f(v.eta_vs_bound)));
                            pairs.push(("A_cap_eq_m2", f(v.a_cap_eq)));
                        }
                    }
                    Level::Del => {
                        if let Some(m) = a5.members.iter().find(|m| &m.design_id == dsg && &m.scenario == sc) {
                            pairs.push(("A_eff_m2", f(m.area_m2)));
                            pairs.push((
                                "mdot_req_in_kg_s",
                                f(r.mdot_req_in(m.area_m2, k, o.t_req_n).unwrap_or(f64::NAN)),
                            ));
                            pairs.push(("mdot_del_kg_s", f(m.mdot_del[idx])));
                            pairs.push(("x_mole_O_N2_O2", Value::List(m.x_mole[idx].iter().map(|x| f(*x)).collect())));
                            pairs.push(("context_id", s(m.context_id.clone())));
                            pairs.push(("context_role", s(m.context_role.clone())));
                            pairs.push(("f8_status", s(m.f8_status.clone())));
                        }
                    }
                }
            }
            d(pairs)
        }
        None => s(NOT_EVALUATED),
    };
    let oh = &o.one_hardware[&(l, k)];
    d(vec![
        ("state_verdict_counts", Value::Dict(counts.into_iter().map(|(k, n)| (k, i(n))).collect())),
        ("worst_state", worst),
        (
            "one_hardware",
            d(vec![
                ("verdict", s(oh.verdict)),
                (
                    "designs_passing_every_state_by_scenario",
                    Value::Dict(oh.per_scenario.iter().map(|(sc, n)| (sc.clone(), i(*n))).collect()),
                ),
            ]),
        ),
    ])
}

/// Per admissible candidate: the worst required state of L-CAP T12 in its best and its worst scenario.
fn admissible_summary(a5: &IntakeInputs, o: &IntakeOutcome) -> Value {
    let mut by: BTreeMap<String, Vec<&DesignRow>> = BTreeMap::new();
    for (_, rc) in o.cand_rows.iter().filter(|(ra, _)| ra.admissible) {
        by.entry(rc.id.clone()).or_default().push(rc);
    }
    let mut rows = vec![];
    for c in a5.candidates.iter().filter(|c| by.contains_key(&c.id)) {
        let rs = &by[&c.id];
        let kk = |r: &&&DesignRow| r.worst[0].and_then(|w| w.1).unwrap_or(f64::INFINITY);
        let best = rs.iter().min_by(|a, b| kk(a).total_cmp(&kk(b))).expect("non-empty");
        let worst = rs.iter().max_by(|a, b| kk(a).total_cmp(&kk(b))).expect("non-empty");
        let ci = a5.candidates.iter().position(|x| x.id == c.id).expect("candidate");
        let at = |r: &DesignRow| -> Value {
            let Some((idx, kf, nf)) = r.worst[0] else { return s(NOT_EVALUATED) };
            let v = design_values(a5, o, ci, &r.scenario, idx);
            d(vec![
                ("scenario", s(r.scenario.clone())),
                ("worst_state", s(o.states[idx].state_id.clone())),
                ("k_cap_T12", of(kf)),
                ("n_failing_required_states_T12", i(nf)),
                ("n_failing_required_states_T25", i(r.worst[1].map_or(0, |w| w.2))),
                ("mdot_cap_kg_s", of(v.as_ref().map(|x| x.mdot_cap))),
                ("eta_c", of(v.as_ref().map(|x| x.eta_c))),
                ("eta_tot", of(v.as_ref().map(|x| x.eta_tot))),
                ("A_cap_eq_m2", of(v.as_ref().map(|x| x.a_cap_eq))),
            ])
        };
        rows.push(d(vec![
            ("candidate", s(c.id.clone())),
            ("A_eff_m2", f(c.area_m2)),
            ("L_over_d", f(c.l_over_d)),
            ("phi", f(c.phi)),
            ("most_favorable_scenario", at(best)),
            ("least_favorable_scenario", at(worst)),
        ]));
    }
    Value::List(rows)
}

/// The `intake_closure_a5` block of the harness v2 record (A5 sec. record.harness).
pub fn record_block(inp: &M1Inputs, out: &M1Outcome) -> Option<Value> {
    let (a5, o) = (inp.a5.as_ref()?, out.a5.as_ref()?);
    let mut levels = Vec::new();
    for k in 0..2 {
        for l in Level::ALL {
            levels.push((key(l, k), level_value(l, k, a5, o)));
        }
    }
    let mut tally: BTreeMap<String, usize> = BTreeMap::new();
    for x in &o.states {
        for c in &x.cell_codes {
            *tally.entry(c.clone()).or_default() += 1;
        }
    }
    let hall_any = o.states.iter().any(|x| x.hall_min_mdot.iter().any(Option::is_some));
    let air_codes = match &inp.air {
        AirHall::NotAvailable(c) => c.clone(),
        AirHall::Ingested(_) => vec![],
    };
    let floor =
        inp.flow.report.as_dict().and_then(|x| x.get("hall_envelope_grid_floor_kg_s")).and_then(|x| x.to_f64().ok());
    Some(d(vec![
        ("addendum_a5", d(vec![("path", s(A5_REL)), ("sha256", s(A5_SHA256)), ("lock_sha256", s(A5_LOCK_SHA256))])),
        (
            "addendum_a5_1",
            d(vec![("path", s(A5_1_REL)), ("sha256", s(A5_1_SHA256)), ("lock_sha256", s(A5_1_LOCK_SHA256))]),
        ),
        ("label", s(LABEL)),
        (
            "a9_35",
            d(vec![
                ("a4_reg_01", s("OPEN: no maximum intake area is invented or frozen")),
                ("carry_forward", carry_forward(o)),
                ("area_limit", s(o.area_limit.clone())),
                ("excluded_by_frozen_area_limit", sl(&o.excluded)),
                ("above_provisional_area_limit", sl(&o.flagged)),
            ]),
        ),
        ("design_identification", ds_value(a5, o)),
        ("levels", Value::Dict(levels.into_iter().collect())),
        ("admissible_designs_worst_state_L_CAP_T12", admissible_summary(a5, o)),
        (
            "L-HALL",
            d(vec![
                ("status", s(if hall_any { "EVALUATED_INFORMATION" } else { NOT_EVALUATED })),
                ("codes", sl(&air_codes)),
                ("hall_envelope_grid_floor_kg_s", of(floor)),
                ("rule", s("information only; the joint flow condition stays A2 NH-FLOW")),
            ]),
        ),
        (
            "classification_effect",
            d(vec![
                ("n_required_air_cells_with_A5_NH_INTAKE", i(o.cells.len())),
                ("cell_code_counts", Value::Dict(tally.into_iter().map(|(k, n)| (k, i(n))).collect())),
                ("category", s("DESIGN_VARIABLE_LIMIT (A9.35, A9.31 sec. 21)")),
                ("eligible", Value::Bool(false)),
                (
                    "statement",
                    s(if o.cells.is_empty() {
                        "no level fails in every scenario at a required AIR state: A5 adds no constraint"
                    } else {
                        "the registered intake / gas-path designs miss the A4 necessary condition in every surface \
                         scenario at the listed cells: DESIGN_VARIABLE_LIMIT, never PHYSICALLY_NON_CLOSING; the only \
                         non-closure route by a registered spacecraft-envelope bound is A4 CA4 on a FROZEN area limit \
                         (A4-REG-01 OPEN)"
                    }),
                ),
                ("xe_contingency", s(A5_NOT_APPLICABLE_STORED_XE)),
            ]),
        ),
        ("full_record", s("intake_closure_a5_v1.json (abep-assess-closure --harness v2 --intake-closure)")),
    ]))
}

fn worst_value(o: &IntakeOutcome, w: Option<(usize, Option<f64>, usize)>) -> Value {
    match w {
        Some((idx, k, n)) => d(vec![("state", s(o.states[idx].state_id.clone())), ("k", of(k)), ("n_failing", i(n))]),
        None => s(NOT_EVALUATED),
    }
}

fn state_row(a5: &IntakeInputs, o: &IntakeOutcome, idx: usize) -> Value {
    let x = &o.states[idx];
    let Some(r) = x.req else {
        return d(vec![
            ("state_id", s(x.state_id.clone())),
            ("required", Value::Bool(x.required)),
            ("status", s(x.status.as_str())),
            ("codes", sl(&x.codes)),
        ]);
    };
    let mut lv = Vec::new();
    for k in 0..2 {
        for l in Level::ALL {
            let ls = &x.levels[&(l, k)];
            lv.push((
                key(l, k),
                d(vec![
                    ("verdict", s(ls.verdict)),
                    ("k_fav", of(ls.k_fav)),
                    ("k_unfav", of(ls.k_unfav)),
                    ("fav", ls.fav.as_ref().map_or(Value::Null, |p| s(format!("{} @ {}", p.0, p.1)))),
                    ("no_design_scenarios", sl(&ls.no_design_scenarios)),
                ]),
            ));
        }
    }
    let cap = match &x.best_cap {
        Some((m, c, sc)) => {
            let ci = a5.candidates.iter().position(|y| &y.id == c).expect("candidate");
            let a = a5.candidates[ci].area_m2;
            let v = design_values(a5, o, ci, sc, idx).expect("evaluated");
            d(vec![
                ("mdot_cap_kg_s", f(*m)),
                ("candidate", s(c.clone())),
                ("scenario", s(sc.clone())),
                ("A_eff_m2", f(a)),
                ("eta_c", f(v.eta_c)),
                ("eta_tot", f(v.eta_tot)),
                ("eta_vs_bound", f(v.eta_vs_bound)),
                ("A_cap_eq_m2", f(v.a_cap_eq)),
                ("mass_fraction_O_N2_O2", Value::List(v.species_mass_fraction.iter().map(|y| f(*y)).collect())),
                ("mdot_req_in_T12_kg_s", f(r.mdot_req_in(a, 0, o.t_req_n).unwrap_or(f64::NAN))),
                ("mdot_req_in_T25_kg_s", f(r.mdot_req_in(a, 1, o.t_req_n).unwrap_or(f64::NAN))),
            ])
        }
        None => s("NO_ADMISSIBLE_DESIGN"),
    };
    let del = match &x.best_del {
        Some((m, id, sc, xo)) => d(vec![
            ("mdot_del_kg_s", f(*m)),
            ("design_id", s(id.clone())),
            ("scenario", s(sc.clone())),
            ("x_O_mole", f(*xo)),
        ]),
        None => s("NO_F7_MEMBER"),
    };
    d(vec![
        ("state_id", s(x.state_id.clone())),
        ("required", Value::Bool(x.required)),
        ("status", s(x.status.as_str())),
        (
            "requirement",
            d(vec![
                ("A_req_T12_m2", f(r.a_req[0])),
                ("A_req_T25_m2", f(r.a_req[1])),
                ("mdot_req_A9_35_T12_kg_s", f(r.mdot_req[0])),
                ("mdot_req_A9_35_T25_kg_s", f(r.mdot_req[1])),
                ("P_avail_W", f(r.p_avail_w)),
                ("Phi_max_kg_m2_s", f(r.phi_max)),
                ("q_max_W_m2", f(r.q_max)),
                ("Phi_adm_kg_m2_s", f(r.phi_adm)),
                ("Phi_O_N2_O2_kg_m2_s", f(r.phi_3)),
            ]),
        ),
        ("best_capture", cap),
        ("best_delivered", del),
        ("levels", Value::Dict(lv.into_iter().collect())),
        ("hall_min_mdot_kg_s", d(vec![("T12", of(x.hall_min_mdot[0])), ("T25", of(x.hall_min_mdot[1]))])),
        ("cell_codes", sl(&x.cell_codes)),
    ])
}

fn catalog() -> Value {
    let e = |u: &str, def: &str| d(vec![("units", s(u)), ("definition", s(def))]);
    d(vec![
        ("A_eff_m2", e("m^2", "aperture area A of the F1 candidate (A4 effective collection area; AREA_EFF_EQUALS_APERTURE_NO_SPACECRAFT_GEOMETRY_REGISTERED)")),
        ("mdot_cap_kg_s", e("kg/s", "F1 IF-A1 forward-transmitted flow (O + N2 + O2; direct TPMC, theta 0) x A, as the admitted F7 chain reads it")),
        ("eta_c", e("1", "mdot_cap / (A sum_{O,N2,O2} rho_i V_adm)")),
        ("eta_tot", e("1", "mdot_cap / (A Phi_adm), Phi_adm = rho V (admitted)")),
        ("eta_vs_bound", e("1", "mdot_cap / (A Phi_max) (A4 K-PHI)")),
        ("A_cap_eq_m2", e("m^2", "mdot_cap / Phi_max: the ideal-collector area capturing the same flow")),
        ("mdot_del_kg_s", e("kg/s", "delivered flow after filter, compressor and plenum (admitted steady chain, one target P_set)")),
        ("x_mole_O_N2_O2", e("1", "mole fractions of the delivered flow")),
        ("A_req_m2", e("m^2", "A4 K-AREQ at P_avail (eta_cap = 1, Phi_max, q_max)")),
        ("mdot_req_A9_35_kg_s", e("kg/s", "A4 K-MDOT-REQ at P_avail (electric power only; the A9.35 carried-forward value)")),
        ("mdot_req_in_kg_s", e("kg/s", "A4 K-MDOT-REQ at P_avail + q_max A(d) (binding flow requirement of L-CAP / L-DEL)")),
        ("k", e("1", "multiplier required / actual (L-AREA A_req/A_eff, L-CAP mdot_req,in/mdot_cap, L-DEL mdot_req,in/mdot_del); <= 1 passes; null = unbounded")),
        ("k_fav / k_unfav", e("1", "best design multiplier in the most / least favorable surface scenario")),
        ("verdict", e("-", "FAILS_IN_EVERY_SCENARIO | PASSES_IN_EVERY_SCENARIO | SCENARIO_DEPENDENT | NOT_ESTABLISHED_ROBUST_SET_EMPTY | NOT_EVALUATED (A5 sec. statewise)")),
        ("labels", e("-", "PARAMETRIC_SENSITIVITY (F1 / F7 / F8 inputs); necessary conditions only; not a performance prediction")),
    ])
}

/// The standalone record `intake_closure_a5_v1.json` (A5 sec. record.standalone).
pub fn intake_record(inp: &M1Inputs, out: &M1Outcome, run_label: &str) -> AssessResult<Value> {
    let a5 = inp.a5.as_ref().ok_or_else(|| model_error("A5 inputs not gathered"))?;
    let o = out.a5.as_ref().ok_or_else(|| model_error("A5 not evaluated"))?;
    let block = record_block(inp, out).ok_or_else(|| model_error("A5 not evaluated"))?;
    let ti = &inp.today;
    let cands: Vec<Value> = o
        .cand_rows
        .iter()
        .map(|(ra, rc)| {
            let c = a5.candidates.iter().find(|c| c.id == ra.id).expect("candidate");
            let ci = a5.candidates.iter().position(|x| x.id == c.id).expect("candidate");
            let at = rc.worst[0].and_then(|w| design_values(a5, o, ci, &rc.scenario, w.0));
            d(vec![
                ("candidate", s(c.id.clone())),
                ("scenario", s(ra.scenario.clone())),
                ("A_eff_m2", f(c.area_m2)),
                ("L_over_d", f(c.l_over_d)),
                ("phi", f(c.phi)),
                ("admissible", Value::Bool(ra.admissible)),
                ("codes", sl(&ra.codes)),
                ("n_f1_infeasible_required_states", i(ra.n_f1_infeasible_states)),
                ("f1_reason_example", ra.f1_reason_example.clone().map_or(Value::Null, s)),
                ("L-AREA|T12", worst_value(o, ra.worst[0])),
                ("L-AREA|T25", worst_value(o, ra.worst[1])),
                ("L-CAP|T12", worst_value(o, rc.worst[0])),
                ("L-CAP|T25", worst_value(o, rc.worst[1])),
                (
                    "at_L_CAP_T12_worst_state",
                    match at {
                        Some(v) => d(vec![
                            ("mdot_cap_kg_s", f(v.mdot_cap)),
                            ("eta_c", f(v.eta_c)),
                            ("eta_tot", f(v.eta_tot)),
                            ("eta_vs_bound", f(v.eta_vs_bound)),
                            ("A_cap_eq_m2", f(v.a_cap_eq)),
                            (
                                "mass_fraction_O_N2_O2",
                                Value::List(v.species_mass_fraction.iter().map(|y| f(*y)).collect()),
                            ),
                        ]),
                        None => s(NOT_EVALUATED),
                    },
                ),
            ])
        })
        .collect();
    let members: Vec<Value> = a5
        .members
        .iter()
        .zip(&o.member_rows)
        .map(|(m, r)| {
            let w = r.worst[0].map(|w| w.0);
            d(vec![
                ("design_id", s(m.design_id.clone())),
                ("context_id", s(m.context_id.clone())),
                ("context_role", s(m.context_role.clone())),
                ("candidate", s(m.candidate.clone())),
                ("A_eff_m2", f(m.area_m2)),
                ("compressor", s(m.compressor.clone())),
                ("V_m3", f(m.v_m3)),
                ("P_set_Pa", f(m.p_set_pa)),
                ("f8_status", s(m.f8_status.clone())),
                ("codes", sl(&r.codes)),
                ("mdot_delivered_min_committed_kg_s", f(m.mdot_delivered_min_kgps)),
                ("mdot_delivered_min_rerun_kg_s", f(m.mdot_delivered_min_rerun_kgps)),
                (
                    "rerun_vs_committed_ulp",
                    i(ulp_distance(m.mdot_delivered_min_rerun_kgps, m.mdot_delivered_min_kgps) as usize),
                ),
                ("mdot_captured_min_committed_kg_s", f(m.mdot_captured_min_kgps)),
                ("L-DEL|T12", worst_value(o, r.worst[0])),
                ("L-DEL|T25", worst_value(o, r.worst[1])),
                ("mdot_del_at_T12_worst_kg_s", w.map_or(Value::Null, |i| f(m.mdot_del[i]))),
                (
                    "x_mole_O_N2_O2_at_T12_worst",
                    w.map_or(Value::Null, |i| Value::List(m.x_mole[i].iter().map(|y| f(*y)).collect())),
                ),
            ])
        })
        .collect();
    Ok(d(vec![
        ("schema", s(RECORD_SCHEMA)),
        ("model_id", s("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("run_label", s(run_label)),
        ("label", s(LABEL)),
        (
            "addendum_a5",
            d(vec![
                ("path", s(A5_REL)),
                ("sha256", s(A5_SHA256)),
                ("md_sha256", s(A5_MD_SHA256)),
                ("lock", s(A5_LOCK_REL)),
                ("lock_sha256", s(A5_LOCK_SHA256)),
            ]),
        ),
        (
            "addendum_a5_1",
            d(vec![
                ("path", s(A5_1_REL)),
                ("sha256", s(A5_1_SHA256)),
                ("md_sha256", s(A5_1_MD_SHA256)),
                ("lock", s(A5_1_LOCK_REL)),
                ("lock_sha256", s(A5_1_LOCK_SHA256)),
            ]),
        ),
        (
            "addendum_a4",
            d(vec![
                ("path", s(conservation::A4_REL)),
                ("sha256", s(conservation::A4_SHA256)),
                ("lock_sha256", s(conservation::A4_LOCK_SHA256)),
            ]),
        ),
        ("addendum_a2", d(vec![("path", s(A2_REL)), ("sha256", s(A2_SHA256)), ("lock_sha256", s(A2_LOCK_SHA256))])),
        ("architecture", s(abep_subsystems::power::slots::FLIGHT_CONFIGURATION)),
        ("rust_commit", s(ti.mission.provenance.rust_commit.clone())),
        (
            "inputs",
            d(vec![
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
                    "provenance",
                    Value::List(
                        a5.provenance.iter().map(|(p, h)| d(vec![("path", s(p.clone())), ("sha256", s(h.clone()))])).collect(),
                    ),
                ),
                ("n_states", i(o.states.len())),
                ("n_required_states", i(o.states.iter().filter(|x| x.required).count())),
            ]),
        ),
        ("summary", block),
        (
            "harness_classification",
            d(vec![
                ("result", s(out.outcome.classification)),
                ("procedure_step", s(out.outcome.step)),
                ("note", s("the harness result after A5; the architecture classification is the coordinator's (M2)")),
            ]),
        ),
        ("field_catalog", catalog()),
        ("states", Value::List((0..o.states.len()).map(|k| state_row(a5, o, k)).collect())),
        ("candidates", Value::List(cands)),
        ("f7_members", Value::List(members)),
        ("f8_survivors_carried_unchanged", Value::Dict(a5.f8_survivors.iter().map(|(k, v)| (k.clone(), v.clone())).collect())),
        (
            "what_this_is_not",
            strs(&[
                "not a performance prediction: every requirement is the A4 conservation necessary condition at its favorable limit",
                "not an area limit: A4-REG-01 stays OPEN; no maximum intake area is invented or frozen",
                "not a selection or a flight mass-flow requirement (A9.13 S6.20, S6.21)",
                "not the architecture classification (the coordinator states it in M2)",
                "not a relabelling of any admitted or scored result (F7, F8 robust set EMPTY, plenum / feed v8 PARITY_FAIL, A4 verdicts unchanged)",
            ]),
        ),
    ]))
}

/// Harness v2 inputs, evaluation and the standalone A5 record of the repository.
pub fn intake_closure_record(repo: &Path, rust_commit: &str, run_label: &str) -> AssessResult<Value> {
    let inp = super::gather::gather_m1(repo, None, None, rust_commit)?;
    let out = evaluate(&inp)?;
    intake_record(&inp, &out, run_label)
}
