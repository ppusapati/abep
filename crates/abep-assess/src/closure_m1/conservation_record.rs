//! Records of addendum A4: the `conservation_bounds_a4` block of the harness v2 record and the standalone record
//! `conservation_bounds_v1.json` (schema `abep_assess_conservation_bounds_v1`; A4 sec. record). Deterministic: ordered
//! maps and the repository's Python-compatible JSON writer.

use super::conservation::*;
use super::record::{d, strs};
use super::*;
use crate::error::{model_error, AssessResult};
use abep_mission::conservation_bounds as cb;
use std::path::Path;

fn s(x: impl Into<String>) -> Value {
    Value::Str(x.into())
}

fn f(x: f64) -> Value {
    Value::Float(x)
}

fn of(x: Option<f64>) -> Value {
    x.map_or(Value::Null, Value::Float)
}

fn fl(xs: &[f64]) -> Value {
    Value::List(xs.iter().map(|x| f(*x)).collect())
}

fn sl(xs: &[String]) -> Value {
    Value::List(xs.iter().map(|x| s(x.clone())).collect())
}

fn air(x: &StateBound) -> &ModeBound {
    &x.modes[&Mode::AirPrimary]
}

fn xe(x: &StateBound) -> &ModeBound {
    &x.modes[&Mode::XeContingency]
}

/// {min, max, min_state, max_state, n_states} of a per-state quantity over the required states where it is evaluated.
fn range(st: &[StateBound], q: impl Fn(&StateBound) -> Option<f64>) -> Value {
    let v: Vec<(&str, f64)> =
        st.iter().filter(|x| x.required).filter_map(|x| q(x).map(|y| (x.state_id.as_str(), y))).collect();
    let lo = v.iter().min_by(|a, b| a.1.total_cmp(&b.1));
    let hi = v.iter().max_by(|a, b| a.1.total_cmp(&b.1));
    match (lo, hi) {
        (Some(lo), Some(hi)) => d(vec![
            ("min", f(lo.1)),
            ("max", f(hi.1)),
            ("min_state", s(lo.0)),
            ("max_state", s(hi.0)),
            ("n_states", Value::int(v.len() as i64)),
        ]),
        _ => s(BOUND_NOT_EVALUATED),
    }
}

fn verdict_value(v: &Verdict, full: bool) -> Value {
    let q = v.quantifier.as_dict();
    let pick = |k: &str| q.and_then(|x| x.get(k)).cloned().unwrap_or(Value::Null);
    let quant = if v.quantifier == Value::Null {
        Value::Null
    } else {
        d(vec![
            ("verdict", pick("verdict")),
            ("n_states", pick("n_states")),
            ("n_fail", pick("n_fail")),
            ("worst_state", pick("worst_state")),
            ("margin", s("A_eff,max - A_req(s) (m^2; >= 0 passes)")),
        ])
    };
    let mut pairs = vec![
        ("id", s(v.id)),
        ("mode", s(v.mode.as_str())),
        ("status", s(v.status)),
        ("eligible_for_physically_non_closing", Value::Bool(v.eligible)),
        ("codes", sl(&v.codes)),
        ("n_failing_states", Value::int(v.failing_states.len() as i64)),
        ("detail", s(v.detail.clone())),
        ("statewise_quantifier", quant),
    ];
    if full {
        pairs.push(("failing_states", sl(&v.failing_states)));
    }
    d(pairs)
}

fn area_value(a: &AreaLimit) -> Value {
    match a {
        AreaLimit::NotRegistered => d(vec![
            ("status", s("NOT_REGISTERED")),
            ("code", s(A4_AREA_LIMIT_NOT_REGISTERED)),
            ("read_from", s(format!("config/constraints/engineering_constraints_v1.json constraints.{AREA_CONSTRAINT}"))),
            (
                "searched",
                strs(&[
                    "config/** (requirements snapshot, engineering constraints, gate thresholds, hardware bounds, architecture, mission): no area limit",
                    "RFP-P18-05 'Air intake Specification: Shall be decided by air density based on solar activity and altitude': the intake is a bidder design variable",
                    "H2-7 HI-05: no launcher or spacecraft envelope is defined in the repository",
                    "F1-P-16 frontal-area grid 0.25-1.5 m^2: assumed DESIGN_GRID, not a limit",
                    "OQ-F78-04 spacecraft frontal geometry: DEMANDED, open",
                    "HC-09 intake-face drag <= 25 mN: bounds a drag, not an area (no registered C_D lower bound)",
                    "mass v5: intake mass TBD (F1-09), no areal mass basis",
                ]),
            ),
        ]),
        AreaLimit::Registered { value_m2, status, provenance } => d(vec![
            ("status", s(status.clone())),
            ("value_m2", f(*value_m2)),
            ("provenance", s(provenance.clone())),
            ("eligible", Value::Bool(status == "FROZEN")),
        ]),
    }
}

/// Summary of the A4 evaluation (the v2 record block and the standalone record's `summary`).
pub fn summary_value(inp: &M1Inputs, o: &A4Outcome) -> Value {
    let st = &o.states;
    let a_req = |k: usize| move |x: &StateBound| air(x).a_req.map(|a| a[k]);
    let a_req0 = |k: usize| move |x: &StateBound| air(x).a_req0.map(|a| a[k]);
    let grid: Vec<(String, Value)> = F1_GRID_AREAS_M2
        .iter()
        .enumerate()
        .map(|(i, a)| (format!("{a}"), range(st, move |x: &StateBound| air(x).t_max_grid.get(i).copied())))
        .collect();
    let p_max = st
        .iter()
        .filter(|x| x.required)
        .filter_map(|x| air(x).p_avail_w)
        .fold(None, |a: Option<f64>, x| Some(a.map_or(x, |a| a.max(x))));
    let fr = inp.flow.report.as_dict().and_then(|x| x.get("frontier_overall")).and_then(Value::as_dict);
    let fnum = |k: &str| fr.and_then(|x| x.get(k)).and_then(|x| x.to_f64().ok());
    let frontier = match (fnum("mdot_delivered_min_kgps"), fnum("mdot_captured_min_kgps"), p_max) {
        (Some(md), Some(mc), Some(p)) => d(vec![
            ("label", s("DESIGN_GRID_INFORMATION_NEVER_ELIGIBLE")),
            ("source", s("harness P-FLOW raw report frontier_overall (F7 Pareto members, statewise minimum)")),
            ("mdot_delivered_min_kg_s", f(md)),
            ("mdot_captured_min_kg_s", f(mc)),
            ("P_W", f(p)),
            ("T_max_delivered_N", of(cb::t_max(md, p).ok())),
            ("T_max_captured_N", of(cb::t_max(mc, p).ok())),
            ("mdot_req_HC01_kg_s", of(cb::mdot_required(inp.today.limits.thrust_min_n, p).ok())),
        ]),
        _ => s(BOUND_NOT_EVALUATED),
    };
    let worst = |k: usize| -> Value {
        let w = st
            .iter()
            .filter(|x| x.required)
            .filter_map(|x| air(x).a_req.map(|a| (x, a[k])))
            .max_by(|a, b| a.1.total_cmp(&b.1));
        match w {
            None => s(BOUND_NOT_EVALUATED),
            Some((x, a)) => d(vec![
                ("state_id", s(x.state_id.clone())),
                ("A_req_m2", f(a)),
                ("Phi_max_kg_m2_s", of(x.flux.as_ref().map(|y| y.phi_max_kg_m2_s))),
                ("U_max_m_s", of(x.speed.map(|y| y.u_max_m_s))),
                ("P_avail_W", of(air(x).p_avail_w)),
            ]),
        }
    };
    let t_area = match inp.a4.as_ref().map(|a| &a.area) {
        Some(AreaLimit::Registered { .. }) => range(st, |x| air(x).t_max_at_area),
        _ => d(vec![("status", s(BOUND_NOT_EVALUATED)), ("code", s(A4_AREA_LIMIT_NOT_REGISTERED))]),
    };
    d(vec![
        ("label", s(cb::LABEL)),
        ("Phi_adm_kg_m2_s", range(st, |x| x.phi_adm)),
        ("Phi_max_kg_m2_s", range(st, |x| x.flux.as_ref().map(|y| y.phi_max_kg_m2_s))),
        ("Phi_max_over_Phi_adm", range(st, |x| x.flux.as_ref().zip(x.phi_adm).map(|(y, p)| y.phi_max_kg_m2_s / p))),
        ("mdot_cap_max_per_unit_area", s("= Phi_max_kg_m2_s (eta_cap = 1)")),
        ("q_max_W_m2", range(st, |x| x.flux.as_ref().map(|y| y.q_max_w_m2))),
        ("U_max_m_s", range(st, |x| x.speed.map(|y| y.u_max_m_s))),
        ("U_min_m_s", range(st, |x| x.speed.map(|y| y.u_min_m_s))),
        ("S_min", range(st, |x| x.flux.as_ref().map(|y| y.s_min))),
        ("P_avail_W_AIR", range(st, |x| air(x).p_avail_w)),
        ("P_avail_W_XE", range(st, |x| xe(x).p_avail_w)),
        ("mdot_req_HC01_kg_s", range(st, |x| air(x).mdot_req.map(|m| m[0]))),
        ("mdot_req_HC02_kg_s", range(st, |x| air(x).mdot_req.map(|m| m[1]))),
        ("A_req_HC01_m2", range(st, a_req(0))),
        ("A_req_HC02_m2", range(st, a_req(1))),
        ("A_req0_HC01_m2", range(st, a_req0(0))),
        ("A_req0_HC02_m2", range(st, a_req0(1))),
        ("worst_state_HC01", worst(0)),
        ("worst_state_HC02", worst(1)),
        ("T_max_at_registered_area_N", t_area),
        (
            "I2_T_max_at_F1_grid_areas_N",
            d(vec![
                ("label", s("INFORMATION_DESIGN_GRID_AREA_NOT_A_LIMIT")),
                ("by_area_m2", Value::Dict(grid.into_iter().collect())),
            ]),
        ),
        ("I3_f7_frontier", frontier),
        (
            "I4_hc09",
            d(vec![
                ("label", s("BULK_MOMENTUM_BOUND_INFORMATION (HC-09 is a design-generation filter); never eligible")),
                ("HC09_N", of(inp.a4.as_ref().and_then(|a| a.hc09_n))),
                ("mdot_cap_max_kg_s", range(st, |x| air(x).mdot_cap_hc09)),
            ]),
        ),
        (
            "I5_b_drag",
            d(vec![
                ("label", s("BULK_MOMENTUM_BOUND_INFORMATION; never eligible")),
                ("mdot_TD_max_kg_s", range(st, |x| air(x).mdot_td_max)),
                ("max_T_minus_Dcap_N", range(st, |x| air(x).max_t_minus_dcap)),
            ]),
        ),
        (
            "I6_xe_mdot_req_kg_s",
            d(vec![
                ("HC01", range(st, |x| xe(x).mdot_req.map(|m| m[0]))),
                ("HC02", range(st, |x| xe(x).mdot_req.map(|m| m[1]))),
            ]),
        ),
    ])
}

fn per_mode(o: &A4Outcome) -> Value {
    let air_v: Vec<&Verdict> =
        o.verdicts.iter().filter(|v| v.mode == Mode::AirPrimary && v.id != "A4-B-DRAG").collect();
    let air_status = if !o.eligible_air_states.is_empty() {
        "ELIGIBLE_NON_CLOSURE: PHYSICALLY_NON_CLOSING via CA4"
    } else if air_v.iter().any(|v| v.status == BOUND_FAILS) {
        "BOUND_FAILS_NOT_ELIGIBLE (area limit not FROZEN): classification unchanged"
    } else if air_v.iter().all(|v| v.status == BOUND_HOLDS) {
        "BOUND_HOLDS_NOTHING_ESTABLISHED: classification unchanged"
    } else {
        "NOT_EVALUATED: no eligible non-closure; classification unchanged"
    };
    d(vec![
        (
            "AIR_PRIMARY",
            d(vec![
                ("outcome", s(air_status)),
                ("n_required_states_eligible_non_closing", Value::int(o.eligible_air_states.len() as i64)),
            ]),
        ),
        (
            "XE_CONTINGENCY",
            d(vec![
                ("outcome", s("NOT_EVALUATED: no registered Xe flow / storage limit; no XE non-closure route")),
                ("n_required_states_eligible_non_closing", Value::int(0)),
            ]),
        ),
    ])
}

/// The `conservation_bounds_a4` block of the v2 record.
pub fn record_block(inp: &M1Inputs, out: &M1Outcome) -> Value {
    match (&inp.a4, &out.a4) {
        (Some(a), Some(o)) => d(vec![
            ("addendum_a4", d(vec![("path", s(A4_REL)), ("sha256", s(A4_SHA256)), ("lock_sha256", s(A4_LOCK_SHA256))])),
            ("area_limit", area_value(&a.area)),
            ("verdicts", Value::List(o.verdicts.iter().map(|v| verdict_value(v, false)).collect())),
            ("per_mode", per_mode(o)),
            ("summary", summary_value(inp, o)),
            ("full_record", s("conservation_bounds_v1.json (abep-assess-closure --harness v2 --conservation-bounds)")),
        ]),
        _ => d(vec![("status", s(BOUND_NOT_EVALUATED)), ("reason", s("A4 inputs not gathered"))]),
    }
}

fn state_row(x: &StateBound) -> Value {
    let modes: Vec<(String, Value)> = x
        .modes
        .iter()
        .map(|(m, mb)| {
            let mut p = vec![
                ("P_avail_W", of(mb.p_avail_w)),
                ("codes", sl(&mb.codes)),
                ("mdot_req_kg_s", mb.mdot_req.map_or(Value::Null, |a| fl(&a))),
            ];
            if *m == Mode::AirPrimary {
                p.extend([
                    ("A_req_m2", mb.a_req.map_or(Value::Null, |a| fl(&a))),
                    ("A_req0_m2", mb.a_req0.map_or(Value::Null, |a| fl(&a))),
                    ("T_max_at_area_N", of(mb.t_max_at_area)),
                    ("T_max_F1_grid_N", fl(&mb.t_max_grid)),
                    ("mdot_TD_max_kg_s", of(mb.mdot_td_max)),
                    ("max_T_minus_Dcap_N", of(mb.max_t_minus_dcap)),
                    ("mdot_cap_HC09_kg_s", of(mb.mdot_cap_hc09)),
                ]);
            }
            (m.as_str().to_string(), d(p))
        })
        .collect();
    let u = x.speed.map_or(Value::Null, |u| {
        d(vec![
            ("r_geocentric_m", f(u.r_geocentric_m)),
            ("V_orb_max", f(u.v_orb_max_m_s)),
            ("V_orb_min", f(u.v_orb_min_m_s)),
            ("V_rot", f(u.v_rot_m_s)),
            ("wind", f(u.wind_m_s)),
            ("U_max", f(u.u_max_m_s)),
            ("U_min", f(u.u_min_m_s)),
        ])
    });
    d(vec![
        ("state_id", s(x.state_id.clone())),
        ("required", Value::Bool(x.required)),
        ("status", s(x.status.as_str())),
        ("codes", sl(&x.codes)),
        ("U_m_s", u),
        ("Phi_adm_kg_m2_s", of(x.phi_adm)),
        ("Phi_max_kg_m2_s", of(x.flux.as_ref().map(|y| y.phi_max_kg_m2_s))),
        ("q_max_W_m2", of(x.flux.as_ref().map(|y| y.q_max_w_m2))),
        ("S_min", of(x.flux.as_ref().map(|y| y.s_min))),
        ("modes", Value::Dict(modes.into_iter().collect())),
    ])
}

fn catalog() -> Value {
    let e = |u: &str, p: String| d(vec![("units", s(u)), ("producer", s(p))]);
    let k = "abep_mission::conservation_bounds (A4 kernels; raw physics, no threshold)";
    let a = "abep_assess::closure_m1::conservation (assessment: HC-01..HC-03, area limit)";
    d(vec![
        (
            "rule",
            s("every per-state field carries the state's status and codes; a field is null when NOT_EVALUATED (its \
               codes say why); pairs [x, y] are [HC-01 (12 mN), HC-02 (25 mN)]; T_max_F1_grid_N follows \
               F1_GRID_AREAS_M2 [0.25, 0.5, 0.75, 1.0, 1.25, 1.5] m^2"),
        ),
        ("U_m_s", e("m/s", format!("{k} K-U (r_geocentric_m in m)"))),
        ("Phi_adm_kg_m2_s", e("kg m-2 s-1", "admitted mission field freestream_mass_flux_kg_m2_s = rho V".into())),
        ("Phi_max_kg_m2_s", e("kg m-2 s-1", format!("{k} K-PHI"))),
        ("q_max_W_m2", e("W m-2", format!("{k} K-Q"))),
        ("S_min", e("1", format!("{k} K-PHI"))),
        ("P_avail_W", e("W", format!("{a}: HC-03 - P_nonHall,LB,eligible(s, m) (A2 ledger)"))),
        ("mdot_req_kg_s", e("kg/s", format!("{k} K-MDOT-REQ at P_avail"))),
        ("A_req_m2", e("m^2", format!("{k} K-AREQ at P_avail (eta_cap = 1, energy inflow included)"))),
        ("A_req0_m2", e("m^2", "mdot_req / Phi_max (electric power only)".into())),
        ("T_max_at_area_N", e("N", format!("{k} K-TMAX at the registered area"))),
        ("T_max_F1_grid_N", e("N", "K-TMAX at the F1 design-grid areas (I-2, information)".into())),
        ("mdot_TD_max_kg_s", e("kg/s", "largest mdot with T_max >= mdot U_min (I-5, information)".into())),
        ("max_T_minus_Dcap_N", e("N", "P / (2 U_min) + P / c (I-5, information)".into())),
        ("mdot_cap_HC09_kg_s", e("kg/s", "HC-09 / U_min (I-4, information)".into())),
    ])
}

/// The standalone record `conservation_bounds_v1.json` (A4 sec. record.standalone).
pub fn bounds_record(inp: &M1Inputs, out: &M1Outcome, run_label: &str) -> AssessResult<Value> {
    let a4 = inp.a4.as_ref().ok_or_else(|| model_error("A4 inputs not gathered"))?;
    let o = out.a4.as_ref().ok_or_else(|| model_error("A4 not evaluated"))?;
    let ti = &inp.today;
    let lb = |m: Mode| {
        let v: Vec<f64> = out.states.iter().filter(|x| x.0.required).map(|x| x.1[&m].bus.lb_eligible_w).collect();
        let lo = v.iter().copied().fold(f64::INFINITY, f64::min);
        let hi = v.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        d(vec![("min", f(lo)), ("max", f(hi))])
    };
    let mut by_status: BTreeMap<String, i64> = BTreeMap::new();
    for x in &o.states {
        *by_status.entry(x.status.as_str().to_string()).or_default() += 1;
    }
    let statement = if o.eligible_air_states.is_empty() {
        "no eligible A4 non-closure: the bounds add no blocker and establish nothing; the harness classification is \
         unchanged"
    } else {
        "eligible A4 non-closure at a required AIR state: PHYSICALLY_NON_CLOSING via CA4"
    };
    Ok(d(vec![
        ("schema", s(RECORD_SCHEMA)),
        ("model_id", s("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("run_label", s(run_label)),
        ("label", s(cb::LABEL)),
        (
            "addendum_a4",
            d(vec![
                ("path", s(A4_REL)),
                ("sha256", s(A4_SHA256)),
                ("md_sha256", s(A4_MD_SHA256)),
                ("lock", s(A4_LOCK_REL)),
                ("lock_sha256", s(A4_LOCK_SHA256)),
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
                ("altitude_band_km", fl(&[a4.alt_band_km.0, a4.alt_band_km.1])),
                ("area_limit", area_value(&a4.area)),
                ("HC09_N", of(a4.hc09_n)),
                ("wind_dataset", s(a4.wind_dataset.clone())),
                (
                    "P_nonHall_LB_eligible_W",
                    d(vec![("AIR_PRIMARY", lb(Mode::AirPrimary)), ("XE_CONTINGENCY", lb(Mode::XeContingency))]),
                ),
                (
                    "provenance",
                    Value::List(
                        a4.provenance.iter().map(|(p, h)| d(vec![("path", s(p.clone())), ("sha256", s(h.clone()))])).collect(),
                    ),
                ),
                ("n_states", Value::int(o.states.len() as i64)),
                ("n_required_states", Value::int(o.states.iter().filter(|x| x.required).count() as i64)),
                ("n_states_by_status", Value::Dict(by_status.into_iter().map(|(k, n)| (k, Value::int(n))).collect())),
            ]),
        ),
        ("summary", summary_value(inp, o)),
        ("verdicts", Value::List(o.verdicts.iter().map(|v| verdict_value(v, true)).collect())),
        ("per_mode", per_mode(o)),
        (
            "classification_effect",
            d(vec![
                ("step_CA4_applied", Value::Bool(out.outcome.step == "CA4")),
                ("harness_classification", s(out.outcome.classification)),
                ("harness_procedure_step", s(out.outcome.step)),
                ("statement", s(statement)),
            ]),
        ),
        (
            "registration_item",
            d(vec![
                ("id", s("A4-REG-01")),
                (
                    "item",
                    s(format!(
                        "register A_eff,max, the effective-collection-area limit (A4 bounds.B-FLOW.area_definition), \
                         as engineering constraint {AREA_CONSTRAINT} (units m^2, status FROZEN, with its requirement \
                         / owner basis, e.g. the spacecraft frontal envelope or the launcher envelope DRDO fixes at \
                         PDR, RFP-P19-04)"
                    )),
                ),
                (
                    "effect",
                    s("A4 then decides AIR non-closure without a code change iff A_eff,max < A_req(s, 12 mN) at some \
                       required state, or A_eff,max < A_req(s, 25 mN) at every required state"),
                ),
            ]),
        ),
        ("field_catalog", catalog()),
        ("states", Value::List(o.states.iter().map(state_row).collect())),
        (
            "what_this_is_not",
            strs(&[
                "not a performance prediction: every quantity is an upper bound over any design and any chemistry under the admitted environment",
                "not a closure: a bound that holds establishes nothing (no SELECT, no evidence condition)",
                "not the architecture classification (the coordinator states it in M2)",
                "not a relabelling of any admitted or scored result (F7, F8 robust set EMPTY, plenum / feed v8, A1 BOUNDED results unchanged)",
            ]),
        ),
    ]))
}

/// Harness v2 inputs, evaluation and the standalone A4 record of the repository.
pub fn conservation_bounds_record(repo: &Path, rust_commit: &str, run_label: &str) -> AssessResult<Value> {
    let inp = super::gather::gather_m1(repo, None, None, rust_commit)?;
    let out = evaluate(&inp)?;
    bounds_record(&inp, &out, run_label)
}
