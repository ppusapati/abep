//! The harness v2 record (schema `abep_assess_hall_parametric_closure_v2`) and the M1 readiness listing (addendum A2
//! secs. readiness, execution). Deterministic: ordered maps and the repository's Python-compatible JSON writer.

use super::gather::gather_m1;
use super::*;
use crate::closure::{envelope_summary, hall_value, layer_b_rows, layer_b_status, n2_proxy, row_status};
use crate::error::AssessResult;
use crate::neutralization::{hc05, neutralization_quantities, CapacityBasis, Current, NeutralizationInputs};
use abep_icp::v2::cpl::{cpl_hall_on, CplInputs, HallMemberSource, ParametricHallPoint};
use abep_icp::IcpStatus;
use abep_types::pyjson::Dict;
use std::path::Path;

pub fn d(pairs: Vec<(&str, Value)>) -> Value {
    crate::py::dict(pairs)
}

pub fn strs(xs: &[&str]) -> Value {
    crate::py::strs(xs)
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

// ------------------------------------------------------------------------------------------------ readiness

/// Readiness status of a required path (A2 sec. readiness).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Readiness {
    Consumed,
    AwaitingInput,
    Blocked,
}

impl Readiness {
    pub fn as_str(self) -> &'static str {
        match self {
            Readiness::Consumed => "CONSUMED",
            Readiness::AwaitingInput => "AWAITING_INPUT",
            Readiness::Blocked => "BLOCKED",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct PathReadiness {
    pub id: &'static str,
    pub title: &'static str,
    pub producer: String,
    pub producer_status: String,
    pub status: Readiness,
    pub codes: Vec<String>,
    pub detail: String,
}

/// The required paths of A2 sec. readiness, in the registered order.
pub fn readiness(inp: &M1Inputs) -> Vec<PathReadiness> {
    let ti = &inp.today;
    let n_env = ti.mission.states.iter().filter(|s| s.environment_status == abep_types::EvalStatus::Evaluated).count();
    let icp_codes: BTreeSet<String> = inp
        .icp
        .modes
        .values()
        .filter(|m| m.i_e_cap_fav_a.is_none())
        .flat_map(|m| std::iter::once(ICP_CAPACITY_NOT_EVALUATED.to_string()).chain(m.codes.iter().cloned()))
        .collect();
    let robust_empty = inp.flow.robust_members.is_empty();
    let td_codes: BTreeSet<String> = inp.td.per_state_codes.values().flatten().cloned().collect();
    let mut v = vec![
        PathReadiness {
            id: "P-ENV",
            title: "environment per design state",
            producer: "abep_mission::integration::today::run_admitted (abep_atmos::execution)".into(),
            producer_status: "ADMITTED".into(),
            status: Readiness::Consumed,
            codes: vec![],
            detail: format!("{} states, {} EVALUATED", ti.mission.states.len(), n_env),
        },
        PathReadiness {
            id: "P-FLOW",
            title: "intake / feed delivered flow and composition (F7 / F8 chain, robust set carried)",
            producer: "F7 / F8 admitted captured outputs (intake TPMC -> filter -> compressor -> plenum / feed steady)"
                .into(),
            producer_status: "ADMITTED (PARAMETRIC_SENSITIVITY inputs); plenum / feed group PYTHON_REFERENCE".into(),
            status: Readiness::Consumed,
            codes: if robust_empty { vec![GAS_PATH_ROBUST_SET_EMPTY.into()] } else { vec![] },
            detail: inp.flow.provenance.clone(),
        },
        PathReadiness {
            id: "P-FEED-STABILITY",
            title: "feed-loop stability (contract v8 typed UNSTABLE_EQUILIBRIUM)",
            producer: "abep_gaspath::transient stability class under the R2 cross-check rule".into(),
            producer_status: "PYTHON_REFERENCE authoritative (v8 PARITY_FAIL stands)".into(),
            status: if inp.flow.per_state.is_some() { Readiness::Consumed } else { Readiness::AwaitingInput },
            codes: if inp.flow.per_state.is_some() {
                vec![]
            } else if robust_empty {
                vec![GAS_PATH_ROBUST_SET_EMPTY.into(), FEED_CONTROLLER_NOT_REGISTERED.into()]
            } else {
                vec![GASPATH_PER_STATE_VALUES_NOT_SUPPLIED.into()]
            },
            detail: "consumed per state for robust members when they exist; no admissible hardware today".into(),
        },
        PathReadiness {
            id: "P-ICP",
            title: "NP-ICP v2: I_e,cap, IF-ICP-BUS-v2 loads, IF-ICP-FEED-v1",
            producer: inp.icp.provenance.clone(),
            producer_status: inp.icp.producer_status.clone(),
            status: Readiness::Consumed,
            codes: icp_codes.into_iter().collect(),
            detail: "registered-today v2 case per mode; outputs labelled PARAMETRIC / NOT_VALIDATED".into(),
        },
        PathReadiness {
            id: "P-CPL",
            title: "CPL-HALL-ON-v1 at parametric envelope points; M_n; HC-05",
            producer: "abep_icp::v2::cpl::cpl_hall_on; abep_assess::neutralization".into(),
            producer_status: inp.icp.producer_status.clone(),
            status: Readiness::Consumed,
            codes: if inp.xe.is_none() { vec![v1::HALL_ENVELOPE_NOT_RUN.into()] } else { vec![] },
            detail: "evaluated per mode (governed ensemble source without an envelope point); outputs NOT_EVALUATED \
                     (HI-04..HI-06 no producer, HI-07 / HI-08 not registered, VER-24)"
                .into(),
        },
        PathReadiness {
            id: "P-HALL-XE",
            title: "XE Hall parametric envelope (v1)",
            producer: "abep_hall::envelope::ingest (frozen, sha-pinned raw envelope)".into(),
            producer_status: "PARAMETRIC / NOT_VALIDATED".into(),
            status: if inp.xe.is_some() { Readiness::Consumed } else { Readiness::AwaitingInput },
            codes: if inp.xe.is_some() { vec![] } else { vec![v1::HALL_ENVELOPE_NOT_RUN.into()] },
            detail: "the 2268 XE cases run in this container once the Julia hosts are allowed (A9.33)".into(),
        },
        PathReadiness {
            id: "P-HALL-AIR",
            title: "AIR Hall family (A1)",
            producer: "A1 AIR family; raw ingestion by A1 execution.ingestion".into(),
            producer_status: if inp.a1_on_line { "A1 on this line" } else { "A1 not on this line" }.into(),
            status: match &inp.air {
                AirHall::Ingested(_) => Readiness::Consumed,
                AirHall::NotAvailable(_) => Readiness::AwaitingInput,
            },
            codes: match &inp.air {
                AirHall::Ingested(_) => vec![],
                AirHall::NotAvailable(c) => c.clone(),
            },
            detail: "consumed by the A1 composition rule once AIR points are ingested".into(),
        },
        PathReadiness {
            id: "P-PBUS",
            title: "P_bus on bus_power_boundary_a9_v2 (layer (a) ledger)",
            producer: "abep_subsystems::power::official::ledger_with_loads -> ledger (ADMITTED)".into(),
            producer_status: "ADMITTED ledger function; loads from the evaluated paths".into(),
            status: Readiness::Consumed,
            codes: if ti.ledger.status == "COMPLETE" { vec![] } else { vec![v1::BUS_LEDGER_NOT_COMPLETE.into()] },
            detail: "TBD terms at the favorable lower bound, listed per (state, mode)".into(),
        },
        PathReadiness {
            id: "P-THERMAL",
            title: "thermal 2.0.0 (cathodeless)",
            producer: inp.thermal.provenance.clone(),
            producer_status: inp.thermal.producer_status.clone(),
            status: if inp.thermal.per_state.is_some() { Readiness::Consumed } else { Readiness::AwaitingInput },
            codes: inp.thermal.codes.clone(),
            detail: "governed context read and its gates applied; no flight thermal case is registered".into(),
        },
        PathReadiness {
            id: "P-MASS",
            title: "mass v5 wet-mass objective",
            producer: "abep_subsystems::mass::wet_mass; RFP matrix row".into(),
            producer_status: "ADMITTED".into(),
            status: Readiness::Consumed,
            codes: inp.mass.codes.clone(),
            detail: "no current-best-estimate wet mass exists".into(),
        },
        PathReadiness {
            id: "P-LIFE",
            title: "life (Hall wall flux, P4 material)",
            producer: "abep_subsystems::life".into(),
            producer_status: "ADMITTED kernels".into(),
            status: Readiness::Consumed,
            codes: inp.life.codes.clone(),
            detail: "no evaluated firing life".into(),
        },
        PathReadiness {
            id: "P-TD",
            title: "drag / T - D (HC-08)",
            producer: "mission run hook drag_body_N".into(),
            producer_status: "ADMITTED hook; host-spacecraft drag ICD absent".into(),
            status: Readiness::Consumed,
            codes: td_codes.into_iter().collect(),
            detail:
                "a T - D evaluation needs the host-spacecraft drag ICD and a new addendum; T12 / T25 are evaluable \
                     alone"
                    .into(),
        },
        PathReadiness {
            id: "P-LAYER-B",
            title: "layer (b): admitted components only",
            producer: "HallGate, mission run hook, RFP constraint matrix, official ledger, mass record, HC-05".into(),
            producer_status: "ADMITTED / ACCEPTED".into(),
            status: Readiness::Consumed,
            codes: if ti.credible_set_empty {
                vec![abep_mission::statewise_td::CREDIBLE_HALL_TRANSPORT_SET_EMPTY.into()]
            } else {
                vec![]
            },
            detail: "unchanged from v1".into(),
        },
    ];
    for r in &mut v {
        r.codes.sort();
        r.codes.dedup();
    }
    v
}

pub fn readiness_value(r: &[PathReadiness]) -> Value {
    let blocked: Vec<&str> = r.iter().filter(|x| x.status == Readiness::Blocked).map(|x| x.id).collect();
    let waiting: Vec<&str> = r.iter().filter(|x| x.status == Readiness::AwaitingInput).map(|x| x.id).collect();
    d(vec![
        ("rule", s("A2 readiness: the M1 exit item holds iff no required path is BLOCKED")),
        (
            "paths",
            Value::List(
                r.iter()
                    .map(|x| {
                        d(vec![
                            ("id", s(x.id)),
                            ("title", s(x.title)),
                            ("status", s(x.status.as_str())),
                            ("producer", s(x.producer.clone())),
                            ("producer_status", s(x.producer_status.clone())),
                            ("codes", sl(&x.codes)),
                            ("detail", s(x.detail.clone())),
                        ])
                    })
                    .collect(),
            ),
        ),
        ("blocked", strs(&blocked)),
        ("awaiting_input", strs(&waiting)),
        ("m1_exit_item_harness_consumes_all_paths", Value::Bool(blocked.is_empty())),
    ])
}

// ------------------------------------------------------------------------------------------------ record

const FIELDS: [(&str, &str, &str, &str); 14] = [
    ("mdot_atm_delivered_kg_s", "kg/s", "P-FLOW", "NH-FLOW"),
    ("x_O_delivered", "1", "P-FLOW", "NH-FLOW"),
    ("mdot_xe_feed_kg_s", "kg/s", "P-FLOW", "NH-FLOW"),
    ("I_e_cap_fav_A", "A", "P-ICP", "NH-ICP"),
    ("P_nonHall_LB_W", "W", "P-PBUS", "NH-PBUS; Hall point tests"),
    ("thrust_joint_max_N", "N", "P-HALL", "HALL_*"),
    ("P_bus_fav_at_joint_W", "W", "P-PBUS", "NH-PBUS"),
    ("I_d_at_joint_A", "A", "P-HALL", "NH-ICP"),
    ("M_n_point", "1", "P-CPL", "NH-ICP (information; HC-05 is layer (b))"),
    ("drag_body_N", "N", "P-TD", "NH-TD"),
    ("T_minus_D_N", "N", "P-TD", "NH-TD"),
    ("thermal_margin_K", "K", "P-THERMAL", "NH-THERMAL"),
    ("m_wet_kg", "kg", "P-MASS", "NH-MASS"),
    ("firing_life_h", "h", "P-LIFE", "NH-LIFE"),
];

/// A per-state field: value and status; its codes are those of the constraint it binds (`constraints`).
fn field(v: Option<f64>, status: &str) -> Value {
    d(vec![("value", of(v)), ("status", s(status))])
}

fn codes_of(e: &StateModeEval, id: &str) -> Vec<String> {
    e.eval.constraints.iter().find(|c| c.id == id).map(|c| c.codes.clone()).unwrap_or_default()
}

fn state_fields(inp: &M1Inputs, st: &str, m: Mode, e: &StateModeEval) -> Value {
    let mut out = Dict::new();
    let ne = "NOT_EVALUATED";
    let ev = "EVALUATED";
    let first = e.joint_best.first();
    if m == Mode::AirPrimary {
        match e.delivered {
            Some((md, xo)) => {
                out.insert("mdot_atm_delivered_kg_s", field(Some(md), ev));
                out.insert("x_O_delivered", field(xo, if xo.is_some() { ev } else { ne }));
            }
            None => {
                out.insert("mdot_atm_delivered_kg_s", field(None, ne));
                out.insert("x_O_delivered", field(None, ne));
            }
        }
    } else {
        out.insert("mdot_xe_feed_kg_s", field(None, ne));
    }
    let ie = inp.icp.modes.get(&m).and_then(|x| x.i_e_cap_fav_a);
    out.insert("I_e_cap_fav_A", field(ie, if ie.is_some() { ev } else { ne }));
    out.insert("P_nonHall_LB_W", field(Some(e.bus.lb_w), "LOWER_BOUND"));
    match first {
        Some(b) => {
            out.insert("thrust_joint_max_N", field(Some(b.2), ev));
            out.insert("P_bus_fav_at_joint_W", field(Some(b.3), "LOWER_BOUND"));
            out.insert("I_d_at_joint_A", field(b.4, if b.4.is_some() { ev } else { ne }));
        }
        None => {
            for k in ["thrust_joint_max_N", "P_bus_fav_at_joint_W", "I_d_at_joint_A"] {
                out.insert(k, field(None, ne));
            }
        }
    }
    let mn = match (ie, first.and_then(|b| b.4)) {
        (Some(i), Some(id)) if id > 0.0 => Some(i / id - 1.0),
        _ => None,
    };
    out.insert("M_n_point", field(mn, if mn.is_some() { "MODEL_QUANTITY_NOT_A_GATE" } else { ne }));
    if m == Mode::AirPrimary {
        out.insert("drag_body_N", field(None, ne));
        out.insert("T_minus_D_N", field(None, ne));
    }
    let th = inp.thermal.per_state.as_ref().and_then(|p| p.get(&(st.to_string(), m)));
    out.insert(
        "thermal_margin_K",
        match th {
            Some(t) if t.converged && t.margin_k.is_some() => field(t.margin_k, ev),
            Some(_) => field(None, ne),
            None => field(None, ne),
        },
    );
    out.insert(
        "m_wet_kg",
        match inp.mass.cbe_wet_kg {
            Some(w) => field(Some(w), ev),
            None => field(None, ne),
        },
    );
    out.insert(
        "firing_life_h",
        match inp.life.firing_life_h {
            Some(l) => field(Some(l), ev),
            None => field(None, ne),
        },
    );
    Value::Dict(out)
}

fn bus_value(b: &NonHallBus) -> Value {
    d(vec![
        ("label", s(LAYER_A)),
        ("P_nonHall_LB_W", f(b.lb_w)),
        ("P_nonHall_LB_eligible_W", f(b.lb_eligible_w)),
        ("P_nonHall_known_W", of(b.p_nonhall_w)),
        ("hall_discharge_path_efficiency", of(b.hall_path_eff)),
        (
            "overrides",
            Value::List(
                b.overrides
                    .iter()
                    .map(|(sl_, p, src)| d(vec![("slot", s(sl_.clone())), ("P_W", f(*p)), ("source", s(src.clone()))]))
                    .collect(),
            ),
        ),
        (
            "tbd_terms_at_favorable_lower_bound",
            Value::List(
                b.tbd
                    .iter()
                    .map(|(sl_, w, r)| {
                        d(vec![
                            ("slot", s(sl_.clone())),
                            ("what", s(w.clone())),
                            ("favorable_bound", s(if w == "load" { "0 W" } else { "1" })),
                            ("requires", s(r.clone())),
                        ])
                    })
                    .collect(),
            ),
        ),
    ])
}

fn cpl_value(inp: &M1Inputs, out: &M1Outcome, m: Mode) -> Value {
    let Some(model) = inp.icp.model.as_ref() else {
        return d(vec![("status", s(NOT_EVALUATED)), ("reason", s("NP-ICP v2 model not loaded"))]);
    };
    // The joint point with the smallest I_d over every required state (most favorable for neutralization).
    let mut best: Option<(f64, String)> = None;
    for (stref, ms) in &out.states {
        if !stref.required {
            continue;
        }
        if let Some(e) = ms.get(&m) {
            for b in &e.joint_best {
                if let Some(id) = b.4 {
                    if best.as_ref().is_none_or(|x| id < x.0) {
                        best = Some((id, b.1.clone()));
                    }
                }
            }
        }
    }
    let pt = best.as_ref().and_then(|(_, key)| {
        mode_points(inp, m).into_iter().find(|x| &x.p.case.key == key).map(|x| ParametricHallPoint {
            key: key.clone(),
            i_d_a: x.p.discharge_current_a,
            i_beam_a: x.p.ion_current_a,
            v_d_v: Some(x.p.case.vd_v),
        })
    });
    let source = match &pt {
        Some(p) => HallMemberSource::ParametricEnvelope(p),
        None => HallMemberSource::Ensemble,
    };
    let rec = cpl_hall_on(model, &source, &CplInputs::default());
    let im = inp.icp.modes.get(&m);
    let ie = Current {
        value_a: im.and_then(|x| x.i_e_cap_fav_a),
        u_a: None,
        status: if im.and_then(|x| x.i_e_cap_fav_a).is_some() { IcpStatus::Converged } else { IcpStatus::NotEvaluated },
        reasons: im.map(|x| x.codes.clone()).unwrap_or_default(),
    };
    let layer_a = NeutralizationInputs {
        point_id: pt.as_ref().map(|p| p.key.clone()),
        capacity_basis: CapacityBasis::Model,
        i_e_cap: ie.clone(),
        i_d_max_h1: pt.as_ref().and_then(|p| p.i_d_a).map(|v| Current {
            value_a: Some(v),
            u_a: None,
            status: IcpStatus::Converged,
            reasons: vec!["PARAMETRIC_NOT_VALIDATED".into()],
        }),
        validation_cell: None,
        margin_rule: None,
    };
    let layer_b = NeutralizationInputs { i_d_max_h1: None, point_id: None, ..layer_a.clone() };
    let hc = hc05(&inp.today.thresholds, Some(&layer_b))
        .unwrap_or_else(|e| d(vec![("status", s("MODEL_ERROR")), ("reason", s(e.to_string()))]));
    let mut cpl = Dict::new();
    cpl.insert("contract", s(rec.contract.clone()));
    cpl.insert("configuration", s(rec.configuration.clone()));
    cpl.insert("status", s(rec.status.as_str()));
    cpl.insert("reasons", Value::List(rec.reasons.iter().map(|r| s(r.code.clone())).collect()));
    cpl.insert(
        "inputs",
        Value::Dict(
            rec.inputs
                .iter()
                .map(|(k, q)| (k.clone(), d(vec![("value", of(q.value)), ("status", s(q.status.as_str()))])))
                .collect(),
        ),
    );
    cpl.insert("outputs", Value::Dict(rec.outputs.iter().map(|(k, q)| (k.clone(), s(q.status.as_str()))).collect()));
    d(vec![
        ("labels", strs(&[LAYER_A, "NP_ICP_V2_IMPLEMENTED_UNVERIFIED"])),
        (
            "hall_point",
            pt.as_ref().map_or(s("NONE: no joint Hall closing point (governed ensemble source)"), |p| s(p.key.clone())),
        ),
        ("cpl_hall_on_v1", Value::Dict(cpl)),
        ("neutralization_quantities_layer_a", neutralization_quantities(Some(&layer_a))),
        ("hc05_layer_b", hc),
    ])
}

/// The most frequent code list of each constraint of a mode over the required states (ties: the smallest list).
fn modal_codes(out: &M1Outcome, m: Mode) -> BTreeMap<String, Vec<String>> {
    let mut n: BTreeMap<String, BTreeMap<Vec<String>, usize>> = BTreeMap::new();
    for (st, ms) in &out.states {
        if let (true, Some(e)) = (st.required, ms.get(&m)) {
            for c in &e.eval.constraints {
                *n.entry(c.id.clone()).or_default().entry(c.codes.clone()).or_default() += 1;
            }
        }
    }
    n.into_iter()
        .map(|(id, by)| {
            let best = by.iter().max_by(|a, b| a.1.cmp(b.1).then_with(|| b.0.cmp(a.0))).map(|x| x.0.clone());
            (id, best.unwrap_or_default())
        })
        .collect()
}

/// Tally of one constraint over the required states.
#[derive(Default)]
struct Tally {
    hall_specific: bool,
    counts: BTreeMap<String, usize>,
    codes: BTreeSet<String>,
    closes: usize,
    non_closing_eligible: usize,
}

fn constraint_summary(out: &M1Outcome, m: Mode) -> Value {
    let modal = modal_codes(out, m);
    let mut by: BTreeMap<String, Tally> = BTreeMap::new();
    let mut order: Vec<String> = vec![];
    for (st, ms) in &out.states {
        if !st.required {
            continue;
        }
        let Some(e) = ms.get(&m) else { continue };
        for c in &e.eval.constraints {
            if !by.contains_key(&c.id) {
                order.push(c.id.clone());
            }
            let x = by.entry(c.id.clone()).or_default();
            x.hall_specific = c.hall_specific;
            *x.counts.entry(c.status.to_string()).or_default() += 1;
            x.codes.extend(c.codes.iter().cloned());
            x.closes += c.eligible_close as usize;
            x.non_closing_eligible += c.eligible_non_close as usize;
        }
    }
    Value::List(
        order
            .iter()
            .map(|id| {
                let t = &by[id];
                let cl: Vec<String> = t.codes.iter().cloned().collect();
                d(vec![
                    ("constraint", s(id.clone())),
                    ("hall_specific", Value::Bool(t.hall_specific)),
                    (
                        "status_counts",
                        Value::Dict(t.counts.iter().map(|(k, n)| (k.clone(), Value::int(*n as i64))).collect()),
                    ),
                    ("n_required_closes", Value::int(t.closes as i64)),
                    ("n_required_non_closing_eligible", Value::int(t.non_closing_eligible as i64)),
                    ("codes", sl(&cl)),
                    ("categories", Value::List(cl.iter().map(|c| s(category_a2(c))).collect())),
                    ("modal_codes", sl(modal.get(id).map(Vec::as_slice).unwrap_or(&[]))),
                ])
            })
            .collect(),
    )
}

fn binding_findings(inp: &M1Inputs, out: &M1Outcome) -> Value {
    let n_air = out
        .states
        .iter()
        .filter(|(s, ms)| {
            s.required
                && ms
                    .get(&Mode::AirPrimary)
                    .is_some_and(|e| codes_of(e, "NH-FLOW").contains(&GAS_PATH_ROBUST_SET_EMPTY.to_string()))
        })
        .count();
    let mut v = vec![];
    if inp.flow.robust_members.is_empty() {
        let dec = inp
            .flow
            .report
            .as_dict()
            .and_then(|x| x.get("f8"))
            .and_then(Value::as_dict)
            .and_then(|x| x.get("decomposition"))
            .cloned()
            .unwrap_or(Value::Null);
        v.push(d(vec![
            ("id", s(GAS_PATH_ROBUST_SET_EMPTY)),
            ("category", s(category_a2(GAS_PATH_ROBUST_SET_EMPTY))),
            ("binds", s("NH-FLOW (AIR_PRIMARY), every required state")),
            ("n_required_states_bound", Value::int(n_air as i64)),
            (
                "source",
                s("F8 robust set (PARITY-C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY-V1, ADMITTED), carried unchanged"),
            ),
            ("f8_decomposition", dec),
            (
                "statement",
                s("no upstream hardware of the registered F7 / F8 design space is feasible in every admitted surface \
                   scenario (gas-path reasons: dead-head pressure, Gaede K range); the AIR delivered flow cannot close \
                   at any state in layer (a); not eligible for PHYSICALLY_NON_CLOSING (A2)"),
            ),
        ]));
    }
    if let Some(r) =
        inp.flow.report.as_dict().and_then(|x| x.get("frontier_over_hall_grid_floor")).and_then(|x| x.to_f64().ok())
    {
        let fr = inp.flow.report.as_dict().and_then(|x| x.get("frontier_overall")).cloned().unwrap_or(Value::Null);
        v.push(d(vec![
            ("id", s("F7_DELIVERED_FLOW_FRONTIER_VS_HALL_GRID_FLOOR")),
            ("category", s("INFORMATION (raw ratio, no verdict)")),
            ("binds", s("NH-FLOW (AIR_PRIMARY) once an AIR Hall closing point exists")),
            ("frontier_over_hall_grid_floor", f(r)),
            ("frontier_member", fr),
            (
                "statement",
                s("the best statewise-minimum delivered flow of the F7 Pareto members divided by the lowest Hall \
                   envelope grid flow (v1 MF-LO); below 1 no AIR Hall grid point is reachable at the binding state by \
                   any F7 Pareto member"),
            ),
        ]));
    }
    Value::List(v)
}

fn sec23(inp: &M1Inputs, out: &M1Outcome) -> Value {
    let req: Vec<&(StateRef, BTreeMap<Mode, StateModeEval>)> = out.states.iter().filter(|x| x.0.required).collect();
    let mut per = Dict::new();
    for m in REQUIRED_MODES {
        let feas = req.iter().filter(|(_, ms)| ms[&m].eval.status == PHYSICS_FEASIBLE).count() as i64;
        // Robust: feasible, a non-empty F8 robust set (AIR) and, on a joint hardware, every transport candidate closing
        // every Hall test (A9.31 sec. 23 C; the credible Hall set is EMPTY, so this stays a layer (a) count).
        let robust = req
            .iter()
            .filter(|(_, ms)| {
                let e = &ms[&m];
                e.eval.status == PHYSICS_FEASIBLE
                    && (m != Mode::AirPrimary || !inp.flow.robust_members.is_empty())
                    && e.joint_hardware.iter().any(|hw| {
                        e.hall.iter().all(|h| {
                            h.n_transports > 0 && h.closing.get(hw).is_some_and(|ts| ts.len() == h.n_transports)
                        })
                    })
            })
            .count() as i64;
        let lbs: Vec<f64> = req.iter().map(|(_, ms)| ms[&m].bus.lb_w).collect();
        let pb: Vec<f64> = req.iter().filter_map(|(_, ms)| ms[&m].joint_best.first().map(|b| b.3)).collect();
        let th: Vec<f64> = req.iter().filter_map(|(_, ms)| ms[&m].joint_best.first().map(|b| b.2)).collect();
        let fl: Vec<f64> = req.iter().filter_map(|(_, ms)| ms[&m].delivered.map(|x| x.0)).collect();
        let rng = |v: &[f64]| {
            if v.is_empty() {
                s(NOT_EVALUATED)
            } else {
                d(vec![
                    ("min", f(v.iter().cloned().fold(f64::INFINITY, f64::min))),
                    ("max", f(v.iter().cloned().fold(f64::NEG_INFINITY, f64::max))),
                ])
            }
        };
        per.insert(
            m.as_str(),
            d(vec![
                ("n_required_states", Value::int(req.len() as i64)),
                ("B_n_physics_feasible_a", Value::int(feas)),
                ("C_n_robust_a", Value::int(robust)),
                ("E_thrust_joint_N", rng(&th)),
                ("E_P_nonHall_LB_W", rng(&lbs)),
                ("E_P_bus_fav_joint_W", rng(&pb)),
                ("E_atmospheric_mass_flow_delivered_kg_s", rng(&fl)),
                ("E_icp_electron_current_margin", s("NOT_EVALUATED unless I_e,cap and a joint I_d exist (see states)")),
            ]),
        );
    }
    let mut ordered: Vec<&(String, usize)> = out.outcome.blockers.iter().collect();
    ordered.sort_by(|a, b| {
        (category_rank(category_a2(&a.0)), std::cmp::Reverse(a.1), &a.0).cmp(&(
            category_rank(category_a2(&b.0)),
            std::cmp::Reverse(b.1),
            &b.0,
        ))
    });
    d(vec![
        (
            "A_feasible_region_a",
            s(match out.outcome.classification {
                SELECT_WITH_EVIDENCE_CONDITIONS => "YES (parametric layer)",
                PHYSICALLY_NON_CLOSING => "NO (eligible evaluated non-closure)",
                _ => "NOT_DETERMINABLE",
            }),
        ),
        ("per_mode", Value::Dict(per)),
        (
            "C_robust_note",
            s("robust under registered uncertainty: 0 while the credible Hall set is EMPTY and the F8 robust set is EMPTY"),
        ),
        ("D_worst_case_state", s("NOT_DETERMINABLE: no required state is evaluated on every required constraint")),
        ("E_drag_T_minus_D", s("NOT_EVALUATED: host-spacecraft drag ICD absent (intake-face drag of the F7 frontier member in paths.P-FLOW)")),
        ("E_wet_mass", s("NOT_EVALUATED as physics: no current-best-estimate (planning values in paths.P-MASS)")),
        ("E_flow_frontier_statewise_min", inp.flow.report.as_dict().and_then(|x| x.get("frontier_overall")).cloned().unwrap_or(Value::Null)),
        ("F_constraints_closing_a", s("see constraint_closure_a (n_required_closes)")),
        ("G_evidence_limited", Value::List(out.outcome.blockers.iter().map(|(c, _)| s(c.clone())).collect())),
        (
            "H_dominant_blockers",
            d(vec![
                ("order", s("A9.31 sec. 21 category (FUNDAMENTAL, MODEL_DOMAIN, DESIGN_VARIABLE, MISSING_EVIDENCE), then blocked cells")),
                ("codes", Value::List(ordered.iter().map(|(c, _)| s(c.clone())).collect())),
            ]),
        ),
        ("J_engineering_statement", s("not stated here: the coordinator states the A9.31 sec. 20 / 23 J conclusion")),
    ])
}

/// The harness v2 record of evaluated inputs.
pub fn record_v2(inp: &M1Inputs, out: &M1Outcome, run_label: &str) -> Value {
    let ti = &inp.today;
    let req: Vec<&(StateRef, BTreeMap<Mode, StateModeEval>)> = out.states.iter().filter(|x| x.0.required).collect();
    let count = |m: Mode, stt: &str| req.iter().filter(|(_, ms)| ms[&m].eval.status == stt).count() as i64;
    let mut hall_v = Dict::new();
    let mut nh_v = Dict::new();
    let mut binding = Dict::new();
    let mut counts = Dict::new();
    let mut cpl = Dict::new();
    let mut icp = Dict::new();
    let mut bus_groups = Dict::new();
    for m in REQUIRED_MODES {
        let groups: Vec<Value> = out
            .lb_groups
            .get(&m)
            .map(|g| {
                g.iter()
                    .map(|(bits, tests)| {
                        d(vec![
                            ("P_nonHall_LB_W", f(f64::from_bits(*bits))),
                            ("tests", Value::List(tests.iter().map(hall_value).collect())),
                        ])
                    })
                    .collect()
            })
            .unwrap_or_default();
        hall_v.insert(m.as_str(), Value::List(groups));
        nh_v.insert(m.as_str(), constraint_summary(out, m));
        let mut first_bind: BTreeMap<String, usize> = BTreeMap::new();
        for (_, ms) in &req {
            if let Some(b) = &ms[&m].binding_constraint {
                *first_bind.entry(b.clone()).or_default() += 1;
            }
        }
        binding.insert(
            m.as_str(),
            d(vec![
                (
                    "first_blocking_constraint_counts",
                    Value::Dict(first_bind.iter().map(|(k, n)| (k.clone(), Value::int(*n as i64))).collect()),
                ),
                ("order", s("v1 required_constraints order: Hall tests, then NH-FLOW, NH-ICP, NH-PBUS, NH-TD, NH-MASS, NH-THERMAL, NH-LIFE")),
            ]),
        );
        counts.insert(
            m.as_str(),
            d(vec![
                ("n_required_states", Value::int(req.len() as i64)),
                ("n_physics_feasible_a", Value::int(count(m, PHYSICS_FEASIBLE))),
                ("n_physics_non_closing_a", Value::int(count(m, PHYSICS_NON_CLOSING))),
                ("n_not_determinable_a", Value::int(count(m, NOT_DETERMINABLE))),
            ]),
        );
        cpl.insert(m.as_str(), cpl_value(inp, out, m));
        if let Some(im) = inp.icp.modes.get(&m) {
            icp.insert(
                m.as_str(),
                d(vec![
                    ("case_id", s(im.case_id.clone())),
                    ("status", s(im.status.clone())),
                    ("codes", sl(&im.codes)),
                    ("I_e_cap_fav_A", of(im.i_e_cap_fav_a)),
                    ("member_id", im.member_id.clone().map_or(Value::Null, s)),
                    (
                        "bus_loads",
                        Value::List(
                            im.loads
                                .iter()
                                .map(|(sl_, p, src)| {
                                    d(vec![("slot", s(sl_.name())), ("P_W", f(*p)), ("source", s(src.clone()))])
                                })
                                .collect(),
                        ),
                    ),
                    ("bus_load_codes", sl(&im.load_codes)),
                    ("feed", im.feed.clone()),
                    ("summary", im.summary.clone()),
                ]),
            );
        }
        let mut distinct: BTreeMap<String, (usize, Value)> = BTreeMap::new();
        for (_, ms) in &req {
            let bv = bus_value(&ms[&m].bus);
            let k = crate::closure::to_json(&bv).unwrap_or_default();
            distinct.entry(k).or_insert((0, bv)).0 += 1;
        }
        bus_groups.insert(
            m.as_str(),
            Value::List(
                distinct
                    .into_values()
                    .map(|(n, v)| d(vec![("n_required_states", Value::int(n as i64)), ("ledger", v)]))
                    .collect(),
            ),
        );
    }
    let blockers: Vec<Value> = out
        .outcome
        .blockers
        .iter()
        .map(|(c, n)| {
            d(vec![
                ("code", s(c.clone())),
                ("category", s(category_a2(c))),
                ("n_required_state_modes", Value::int(*n as i64)),
            ])
        })
        .collect();
    let statement = match out.outcome.classification {
        PHYSICALLY_NON_CLOSING => {
            "Hall + RF/ICP is physically non-closing under the preregistered favorable-but-defensible envelope"
        }
        SELECT_WITH_EVIDENCE_CONDITIONS => {
            "physically feasible in the parametric layer but not yet experimentally proven (credible Hall set EMPTY)"
        }
        _ => "the A9.32 classification is not determinable with these inputs; see the blocking list",
    };
    let modal: BTreeMap<Mode, BTreeMap<String, Vec<String>>> =
        REQUIRED_MODES.iter().map(|m| (*m, modal_codes(out, *m))).collect();
    let states: Vec<Value> = out
        .states
        .iter()
        .map(|(st, ms)| {
            let mut md = Dict::new();
            for (m, e) in ms {
                let mut cs = Dict::new();
                for c in &e.eval.constraints {
                    let same = modal.get(m).and_then(|x| x.get(&c.id)) == Some(&c.codes);
                    let mut pairs = vec![("status", s(c.status))];
                    if !same {
                        pairs.push(("codes", sl(&c.codes)));
                    }
                    cs.insert(c.id.as_str(), d(pairs));
                }
                let mut mf = Dict::new();
                for k in ["thrust_N", "I_d_A", "I_ecap_A", "P_bus_W", "drag_body_N", "mdot_atm_delivered_kg_s"] {
                    if let Some(q) = ti.mission.field(&st.state_id, *m, k).and_then(|f| f.quantity()) {
                        mf.insert(k, s(q.status.as_str()));
                    }
                }
                md.insert(
                    m.as_str(),
                    d(vec![
                        (
                            "layer_a",
                            d(vec![
                                ("label", s(LAYER_A)),
                                ("status", s(e.eval.status)),
                                ("blockers", sl(&e.eval.blockers)),
                                ("binding_constraint", e.binding_constraint.clone().map_or(Value::Null, s)),
                                ("constraints", Value::Dict(cs)),
                                ("fields", state_fields(inp, &st.state_id, *m, e)),
                            ]),
                        ),
                        (
                            "layer_b",
                            d(vec![
                                ("status", s(layer_b_status(&ti.matrix, *m, ti.credible_set_empty))),
                                ("mission_fields", Value::Dict(mf)),
                            ]),
                        ),
                    ]),
                );
            }
            let envq = |k: &str| {
                ti.mission
                    .field(&st.state_id, Mode::AirPrimary, k)
                    .and_then(|f| f.quantity())
                    .and_then(|q| q.value)
                    .map_or(Value::Null, Value::Float)
            };
            let env_status =
                ti.mission.state(&st.state_id).map(|r| r.environment_status.as_str()).unwrap_or("MODEL_ERROR");
            d(vec![
                ("state_id", s(st.state_id.clone())),
                ("required", Value::Bool(st.required)),
                ("environment_status", s(env_status)),
                (
                    "free_stream",
                    d(vec![
                        ("rho_kg_m3", envq("rho_kg_m3")),
                        ("fO", envq("fO")),
                        ("fN2", envq("fN2")),
                        ("fO2", envq("fO2")),
                    ]),
                ),
                ("modes", Value::Dict(md)),
            ])
        })
        .collect();
    let catalog: Dict = FIELDS
        .iter()
        .map(|(k, u, p, b)| {
            (
                k.to_string(),
                d(vec![
                    ("units", s(*u)),
                    ("layer", s(format!("a ({LAYER_A})"))),
                    ("producer_path", s(*p)),
                    ("binds", s(*b)),
                ]),
            )
        })
        .collect();
    let mut lb_rows = Dict::new();
    let mut lb_feasible = Dict::new();
    for m in REQUIRED_MODES {
        let mut rows = Dict::new();
        let mut all = true;
        for id in layer_b_rows(m) {
            let stt = row_status(&ti.matrix, id, "rfp_assessment_status").unwrap_or_else(|_| "MODEL_ERROR".into());
            all &= stt == "COMPLIES";
            rows.insert(*id, s(stt));
        }
        lb_rows.insert(m.as_str(), Value::Dict(rows));
        lb_feasible.insert(m.as_str(), Value::int(if all && !ti.credible_set_empty { req.len() as i64 } else { 0 }));
    }
    let ready = readiness(inp);
    d(vec![
        ("schema", s(SCHEMA)),
        ("model_id", s(v1::MODEL_ID)),
        ("run_label", s(run_label)),
        (
            "addendum_a2",
            d(vec![("path", s(A2_REL)), ("sha256", s(A2_SHA256)), ("lock", s(A2_LOCK_REL)), ("lock_sha256", s(A2_LOCK_SHA256))]),
        ),
        (
            "prereg_v1",
            d(vec![
                ("path", s(abep_hall::envelope::PREREG_REL)),
                ("sha256", s(abep_hall::envelope::PREREG_SHA256)),
                ("lock_sha256", s(abep_hall::envelope::LOCK_SHA256)),
            ]),
        ),
        (
            "addendum_a1",
            d(vec![
                ("on_this_line", Value::Bool(inp.a1_on_line)),
                ("path", s(A1_REL)),
                ("sha256", s(A1_SHA256)),
                ("lock_sha256", s(A1_LOCK_SHA256)),
                ("supersedes_a2_named_identity", s(A1_NAMED_IN_A2_SHA256)),
                ("air_chemistry", inp.air_chemistry.clone()),
            ]),
        ),
        ("architecture", s("hall_icp_neutralizer")),
        ("rust_commit", s(ti.mission.provenance.rust_commit.clone())),
        (
            "inputs",
            d(vec![
                ("config_manifest_sha256", s(ti.thresholds.manifest_sha256.clone())),
                (
                    "thresholds",
                    d(vec![
                        ("HC-01_N", f(ti.limits.thrust_min_n)),
                        ("HC-02_N", f(ti.limits.thrust_capability_n)),
                        ("HC-03_W", f(ti.limits.p_bus_max_w)),
                        ("HC-04_kg", of(ti.thresholds.limit("HC-04"))),
                        ("HC-06_K", of(inp.hc06_k)),
                        ("HC-07_h", of(inp.hc07_h)),
                        ("HC-08_N", of(inp.hc08_n)),
                    ]),
                ),
                ("credible_set", s(if ti.credible_set_empty { "EMPTY" } else { "NON_EMPTY" })),
                ("admitted_members", sl(&ti.admitted_members)),
                (
                    "official_bus_ledger",
                    d(vec![
                        ("status", s(ti.ledger.status.clone())),
                        ("n_tbd_terms", Value::int(ti.ledger.n_tbd as i64)),
                        ("P_nonHall_LB_W", f(ti.ledger.p_non_hall_lb_w)),
                    ]),
                ),
                ("mission_prereg_sha256", s(ti.mission.prereg_sha256)),
                (
                    "mission_run_hook_layers",
                    Value::List(
                        ti.mission_layers
                            .iter()
                            .map(|(l, stt, dd)| d(vec![("layer", s(l.clone())), ("status", s(stt.clone())), ("detail", s(dd.clone()))]))
                            .collect(),
                    ),
                ),
                ("n_states", Value::int(out.states.len() as i64)),
                ("n_required_states", Value::int(req.len() as i64)),
            ]),
        ),
        ("readiness", readiness_value(&ready)),
        (
            "classification",
            d(vec![
                ("result", s(out.outcome.classification)),
                ("procedure_step", s(out.outcome.step)),
                ("statement", s(statement)),
                ("blockers", Value::List(blockers)),
                ("evidence_conditions", sl(&out.outcome.evidence_conditions)),
                ("common_hardware", Value::List(out.outcome.common_hardware.iter().map(|(g, b)| s(format!("{g}|{b}"))).collect())),
            ]),
        ),
        ("binding_findings", binding_findings(inp, out)),
        (
            "paths",
            d(vec![
                ("P-FLOW", inp.flow.report.clone()),
                ("P-ICP", d(vec![("producer_status", s(inp.icp.producer_status.clone())), ("provenance", s(inp.icp.provenance.clone())), ("modes", Value::Dict(icp))])),
                ("P-CPL", Value::Dict(cpl)),
                ("P-PBUS", d(vec![("boundary", s("bus_power_boundary_a9_v2")), ("limit", s("HC-03 read by abep-assess only")), ("ledgers_by_mode", Value::Dict(bus_groups))])),
                (
                    "P-THERMAL",
                    d(vec![("producer_status", s(inp.thermal.producer_status.clone())), ("provenance", s(inp.thermal.provenance.clone())), ("codes", sl(&inp.thermal.codes))]),
                ),
                ("P-MASS", d(vec![("codes", sl(&inp.mass.codes)), ("info", inp.mass.info.clone())])),
                ("P-LIFE", d(vec![("codes", sl(&inp.life.codes)), ("info", inp.life.info.clone())])),
                (
                    "P-TD",
                    d(vec![
                        ("rule", s("HC-08 needs the host-spacecraft drag ICD; no T - D evaluation is registered in A2 (R5)")),
                        (
                            "codes",
                            sl(&inp.td.per_state_codes.values().flatten().cloned().collect::<BTreeSet<String>>().into_iter().collect::<Vec<_>>()),
                        ),
                    ]),
                ),
            ]),
        ),
        (
            "rfp_thrust_requirements_evaluable_alone",
            d(vec![
                ("HC-01_T12", s("evaluable by the Hall point test HALL_T12_AT_PBUS (thrust and bus power only, no drag)")),
                ("HC-02_T25", s("evaluable by the Hall point test HALL_T25_CAPABILITY (thrust and bus power only, no drag)")),
                ("HC-08_T_minus_D", s("not evaluable: needs the host-spacecraft drag ICD (open condition NH-TD)")),
                ("status_today", s("AIR Hall NOT_EVALUATED (no admitted AIR family); see hall_specific_closure_a")),
            ]),
        ),
        ("envelope_xe", envelope_summary(inp.xe.as_ref())),
        (
            "envelope_air",
            match &inp.air {
                AirHall::NotAvailable(c) => d(vec![("status", s(NOT_EVALUATED)), ("codes", sl(c))]),
                AirHall::Ingested(a) => d(vec![
                    ("status", s("INGESTED")),
                    ("launch_path", s(if a.bounded { "LP-BOUNDED (information only)" } else { "LP-COMPLETE" })),
                    ("provenance", s(a.provenance.clone())),
                    ("n_points", Value::int(a.points.len() as i64)),
                    ("corners", sl(&a.corners)),
                    ("state_exclusions", Value::Dict(a.state_exclusions.iter().map(|(k, v)| (k.clone(), s(v.clone()))).collect())),
                ]),
            },
        ),
        ("hall_specific_closure_a", Value::Dict(hall_v)),
        ("constraint_closure_a", Value::Dict(nh_v)),
        ("binding_constraint", Value::Dict(binding)),
        ("layer_a_counts", Value::Dict(counts)),
        ("n2_proxy_diagnostic", n2_proxy(inp.xe.as_ref(), &ti.limits)),
        ("a9_31_sec_23", sec23(inp, out)),
        (
            "layer_b",
            d(vec![
                ("label", s("EVIDENCE_QUALIFIED / ADMITTED ONLY")),
                ("credible_set", s(if ti.credible_set_empty { "EMPTY" } else { "NON_EMPTY" })),
                ("hall", s(if ti.credible_set_empty { "NOT_EVALUATED: credible Hall transport set EMPTY" } else { "admitted members present" })),
                ("rfp_matrix_rows", Value::Dict(lb_rows)),
                ("n_states_evidence_qualified_b", Value::Dict(lb_feasible)),
            ]),
        ),
        (
            "field_catalog",
            d(vec![
                (
                    "rule",
                    s("every per-state field inherits units, layer, producer path and binding attribution from this \
                       catalog; a per-state constraint carries its codes only when they differ from the mode's \
                       modal_codes in constraint_closure_a"),
                ),
                ("fields", Value::Dict(catalog)),
            ]),
        ),
        ("states", Value::List(states)),
        (
            "what_this_is_not",
            strs(&[
                "not a validation or admission: the credible Hall transport set stays EMPTY and layer (a) never enters layer (b)",
                "not the A9.31 sec. 20 conclusion by itself (the coordinator states it)",
                "not a relabelling of any raw, admitted or scored status (F8 robust set and plenum / feed v8 carried unchanged)",
            ]),
        ),
    ])
}

/// Harness v2 record of the repository.
pub fn closure_record_v2(
    repo: &Path,
    envelope: Option<Envelope>,
    air: Option<AirHallInput>,
    rust_commit: &str,
    run_label: &str,
) -> AssessResult<Value> {
    let inp = gather_m1(repo, envelope, air, rust_commit)?;
    let out = evaluate(&inp)?;
    Ok(record_v2(&inp, &out, run_label))
}

/// Readiness listing of the repository (A2 sec. readiness).
pub fn readiness_record(repo: &Path, envelope: Option<Envelope>, rust_commit: &str) -> AssessResult<Value> {
    let inp = gather_m1(repo, envelope, None, rust_commit)?;
    Ok(d(vec![
        ("schema", s("abep_assess_closure_readiness_v1")),
        ("addendum_a2_sha256", s(A2_SHA256)),
        ("readiness", readiness_value(&readiness(&inp))),
    ]))
}
