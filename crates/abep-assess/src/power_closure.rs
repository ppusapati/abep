//! A9.38 P6 power-closure record: the design-closure ledgers of `abep_subsystems::power::closure_v1` at the five
//! registered points, with the assessment quantities the power module may not hold (A9.30 sec. 5): the margin to
//! HC-03 (P_bus,max, strict '<'), the discharge ceiling at HC-03 and the thrust-to-discharge-power the Hall
//! envelope must reach for HC-01 / HC-02 to close on this bus. Thresholds come from the configuration only.
//!
//! A design ledger with DESIGN_ALLOCATION_NOT_PREDICTED discharge power: no gate verdict, no performance prediction.

use crate::error::{AssessError, AssessResult};
use crate::py::{dict, s};
use crate::thresholds::Thresholds;
use abep_subsystems::power::allocation::{
    allocation_checks, icp_power_allocation_check, COMMON_ALLOCATION_W, CONTROLS_THERMAL_ALLOWANCE_W,
    DESIGN_ALLOCATION_W,
};
use abep_subsystems::power::closure_v1::{
    evaluate_point, ClosureInputs, Corner, DischargeRule, LoadSpec, PointResult, CLOSURE_RANK, INPUTS_REL,
};
use abep_subsystems::power::official::{official_flight_ledger, official_ledger, MassPowerA9V5};
use abep_subsystems::power::slots::{Group, Slot, FLIGHT_CONFIGURATION};
use abep_subsystems::power::PowerError;
use abep_types::pyjson::{Dict, Value};
use std::collections::BTreeMap;
use std::path::Path;

pub const RECORD_REL: &str = "docs/closure/power/power_ledger_v1.json";
pub const SCHEMA: &str = "abep_power_closure_ledger_v1";
const EVIDENCE_RANK: [&str; 7] =
    ["measured", "digitized", "reconstructed", "inferred", "model-derived", "owner-allocation", "assumed"];

fn pe(e: PowerError) -> AssessError {
    AssessError::from(e.to_abep_error())
}

fn f(x: f64) -> Value {
    Value::Float(x)
}

fn limit(th: &Thresholds, id: &str) -> AssessResult<f64> {
    th.limit(id).ok_or_else(|| AssessError::new("ConfigurationError", format!("{id} is not configured")))
}

fn ceilings(r: &PointResult, hc03: f64) -> Value {
    dict(vec![
        ("design_allocation_1350", f(r.discharge_ceiling(DESIGN_ALLOCATION_W))),
        ("rfp_1500_supremum", f(r.discharge_ceiling(hc03))),
    ])
}

fn group_bus(r: &PointResult, g: Group) -> f64 {
    r.ledger.items.iter().filter(|i| i.installed() && i.slot.group() == g).filter_map(|i| i.p_bus_w).sum()
}

fn slot_terms(inp: &ClosureInputs, point: &str) -> AssessResult<Value> {
    let p = inp.point(point).map_err(pe)?;
    let mut d = Dict::new();
    for (sl, effs) in &inp.slot_efficiencies {
        let load = if *sl == Slot::HallDischarge {
            match &p.discharge {
                DischargeRule::Fixed(e) => ClosureInputs::expr_ids(e).join(" + "),
                DischargeRule::CloseDesignAllocation => "closes 1,350 W".to_string(),
            }
        } else {
            match p.loads.iter().find(|(x, _)| x == sl).map(|(_, l)| l) {
                Some(LoadSpec::Expr(e)) => {
                    let ids = ClosureInputs::expr_ids(e);
                    if ids.is_empty() {
                        "0 W".to_string()
                    } else {
                        ids.join(" / ")
                    }
                }
                Some(LoadSpec::ControlsThermalResidual) => "50 W allowance residual".to_string(),
                None => return Err(AssessError::new("ModelError", format!("{point}: no load for {}", sl.name()))),
            }
        };
        d.insert(sl.name(), s(format!("{load}; eta {}", effs.join(" x "))));
    }
    Ok(Value::Dict(d))
}

/// Closure class and evidence class of each TBD term of the official ledger, as closed by the register at P-NOM.
fn closed_tbd(inp: &ClosureInputs, official: &abep_subsystems::power::ledger::Ledger) -> AssessResult<Value> {
    let p = inp.point("P-NOM").map_err(pe)?;
    let r = evaluate_point(inp, "P-NOM", Corner::Reference, &[]).map_err(pe)?;
    let mut by_closure: BTreeMap<String, i64> = BTreeMap::new();
    let mut by_evidence: BTreeMap<String, i64> = BTreeMap::new();
    let mut rows = Vec::new();
    for t in &official.tbd {
        let it = r.ledger.item(t.slot);
        let (closure, evidence) = match t.what {
            "load" => {
                let cc = if t.slot == Slot::HallDischarge {
                    "DESIGN_ALLOCATION_NOT_PREDICTED".to_string()
                } else {
                    match p.loads.iter().find(|(x, _)| *x == t.slot).map(|(_, l)| l) {
                        Some(LoadSpec::Expr(e)) => {
                            inp.weakest_closure(ClosureInputs::expr_ids(e).into_iter()).map_err(pe)?
                        }
                        Some(LoadSpec::ControlsThermalResidual) => "OWNER_ALLOCATION_RESIDUAL".to_string(),
                        None => return Err(AssessError::new("ModelError", "official TBD slot not in the register")),
                    }
                };
                (cc, it.evidence_class.clone().unwrap_or_default())
            }
            "efficiency" => {
                // governed by the converter term(s); the common harness terms are counted once below
                let ids = &inp.slot_efficiencies.iter().find(|(x, _)| *x == t.slot).expect("installed").1;
                let conv: Vec<&str> = ids.iter().map(String::as_str).filter(|i| !i.starts_with("ETA-H-")).collect();
                let use_ids = if conv.is_empty() { ids.iter().map(String::as_str).collect() } else { conv };
                let ev = {
                    let mut worst = 0usize;
                    for i in &use_ids {
                        let c = &inp.term(i).map_err(pe)?.evidence_class;
                        worst = worst.max(EVIDENCE_RANK.iter().position(|x| x == c).unwrap_or(EVIDENCE_RANK.len() - 1));
                    }
                    EVIDENCE_RANK[worst].to_string()
                };
                (inp.weakest_closure(use_ids.into_iter()).map_err(pe)?, ev)
            }
            _ => {
                let fe = inp.term(&inp.front_end).map_err(pe)?;
                (fe.closure_class.clone(), fe.evidence_class.clone())
            }
        };
        *by_closure.entry(closure.clone()).or_default() += 1;
        *by_evidence.entry(evidence.clone()).or_default() += 1;
        rows.push(dict(vec![
            ("slot", s(t.slot.name())),
            ("what", s(t.what)),
            ("closure_class", s(closure)),
            ("evidence_class", s(evidence)),
        ]));
    }
    // The front end and the two harness terms close every slot; each is one term.
    for id in [inp.front_end.as_str(), "ETA-H-HV", "ETA-H-LV"] {
        let t = inp.term(id).map_err(pe)?;
        *by_closure.entry(t.closure_class.clone()).or_default() += 1;
        *by_evidence.entry(t.evidence_class.clone()).or_default() += 1;
        rows.push(dict(vec![
            ("slot", s("all internal_bus slots")),
            ("what", s(format!("{id} ({})", t.quantity))),
            ("closure_class", s(t.closure_class.clone())),
            ("evidence_class", s(t.evidence_class.clone())),
        ]));
    }
    let ordered = |m: BTreeMap<String, i64>, order: &[&str]| {
        let mut d = Dict::new();
        for k in order {
            if let Some(v) = m.get(*k) {
                d.insert(*k, Value::int(*v));
            }
        }
        for (k, v) in &m {
            if !d.contains_key(k) {
                d.insert(k.as_str(), Value::int(*v));
            }
        }
        Value::Dict(d)
    };
    Ok(dict(vec![
        ("rows", Value::List(rows)),
        ("by_closure_class", ordered(by_closure, &CLOSURE_RANK)),
        ("by_evidence_class", ordered(by_evidence, &EVIDENCE_RANK)),
    ]))
}

/// The P6 closure record.
pub fn power_closure_record(repo: &Path, th: &Thresholds) -> AssessResult<Value> {
    let hc01 = limit(th, "HC-01")?;
    let hc02 = limit(th, "HC-02")?;
    let hc03 = limit(th, "HC-03")?;
    let inp = ClosureInputs::load(repo).map_err(pe)?;
    let mp = MassPowerA9V5::load(repo).map_err(pe)?;
    let official = official_flight_ledger(&mp).map_err(pe)?;
    let cp_nom = inp.term("CP-NOM").map_err(pe)?.value;
    let with_cp = official_ledger(&mp, FLIGHT_CONFIGURATION, Some(cp_nom), "").map_err(pe)?;

    let mut points = Vec::new();
    let mut by_id: BTreeMap<String, PointResult> = BTreeMap::new();
    for p in &inp.points {
        let r = evaluate_point(&inp, &p.id, Corner::Reference, &[]).map_err(pe)?;
        let mut corners = Dict::new();
        for c in [Corner::Conservative, Corner::Favourable] {
            let rc = evaluate_point(&inp, &p.id, c, &[]).map_err(pe)?;
            corners.insert(
                c.name(),
                dict(vec![
                    ("P_bus_non_discharge_W", f(rc.p_bus_non_discharge_w)),
                    ("P_bus_W", f(rc.p_bus_w())),
                    ("P_d_max_W", ceilings(&rc, hc03)),
                    ("flags", Value::List(rc.flags.iter().map(|x| s(x.clone())).collect())),
                ]),
            );
        }
        let basis = match &p.discharge {
            DischargeRule::Fixed(e) => {
                format!("{}: DESIGN_ALLOCATION_NOT_PREDICTED", ClosureInputs::expr_ids(e).join(" + "))
            }
            DischargeRule::CloseDesignAllocation => {
                "closes the 1,350 W design allocation: DESIGN_ALLOCATION_NOT_PREDICTED".to_string()
            }
        };
        let pb = r.p_bus_w();
        points.push(dict(vec![
            ("id", s(p.id.clone())),
            ("name", s(p.name.clone())),
            ("mode", s(p.mode.clone())),
            ("state", s(p.state.clone())),
            ("thrust_label", s(p.thrust_label.clone())),
            ("P_d_W", f(r.p_d_w)),
            ("P_d_basis", s(basis)),
            ("P_bus_non_discharge_W", f(r.p_bus_non_discharge_w)),
            ("P_bus_W", f(pb)),
            ("P_bus_by_group_W", {
                let mut d = Dict::new();
                for g in [Group::Hall, Group::Icp, Group::Common, Group::Reserved] {
                    d.insert(g.name(), f(group_bus(&r, g)));
                }
                Value::Dict(d)
            }),
            ("margin_to_design_allocation_W", f(DESIGN_ALLOCATION_W - pb)),
            ("margin_to_rfp_W", f(hc03 - pb)),
            ("P_bus_below_HC03", Value::Bool(pb < hc03)),
            ("P_d_max_W", ceilings(&r, hc03)),
            ("discharge_chain_eta", f(r.discharge_chain_eta)),
            (
                "losses_W",
                dict(vec![
                    ("conversion", f(r.losses.conversion)),
                    ("harness", f(r.losses.harness)),
                    ("front_end", f(r.losses.front_end)),
                    ("rf_generator", f(r.rf_generator_loss_w)),
                    ("note", s("conversion + harness + front end are inside P_bus - sum(loads); the RF generator loss is inside the icp_rf_source load (generator DC input)")),
                ]),
            ),
            ("thermal_residual_bus_W", f(r.thermal_residual_bus_w)),
            ("corners", Value::Dict(corners)),
            ("allocation_checks", allocation_checks(&r.ledger).map_err(pe)?),
            ("icp_power_allocation_check", icp_power_allocation_check(&r.ledger).map_err(pe)?),
            ("flags", Value::List(r.flags.iter().map(|x| s(x.clone())).collect())),
            ("slot_terms", slot_terms(&inp, &p.id)?),
            ("ledger", r.ledger.to_value()),
        ]));
        by_id.insert(p.id.clone(), r);
    }
    let get = |id: &str| -> AssessResult<&PointResult> {
        by_id.get(id).ok_or_else(|| AssessError::new("ModelError", format!("point {id} missing")))
    };
    // RF trade line at the nominal point's loads.
    let mut trade = Vec::new();
    for pf in &inp.rf_trade_line_w {
        let r = evaluate_point(&inp, "P-12", Corner::Reference, &[("RF-PFWD", *pf)]).map_err(pe)?;
        trade.push(dict(vec![
            ("P_fwd_W", f(*pf)),
            ("P_bus_icp_W", f(group_bus(&r, Group::Icp))),
            ("P_d_max_W", ceilings(&r, hc03)),
        ]));
    }
    // Compressor headroom inside the common allocation at P-NOM.
    let nom = get("P-NOM")?;
    let cp_item = nom.ledger.item(Slot::Compressor);
    let common_other: f64 = nom
        .ledger
        .items
        .iter()
        .filter(|i| i.installed() && i.slot.common_allocation() && i.slot != Slot::Compressor)
        .filter_map(|i| i.p_bus_w)
        .sum();
    let cp_chain = cp_item.p_w.expect("known") / cp_item.p_bus_w.expect("known");
    let headroom = dict(vec![
        ("inside_common_300W_W", f((COMMON_ALLOCATION_W - common_other) * cp_chain)),
        ("compressor_bus_per_W_input", f(1.0 / cp_chain)),
        ("dPd_max_per_W_compressor", f(nom.discharge_chain_eta / cp_chain)),
        ("basis", s("P-NOM: 300 W common allocation minus the other common-group bus draws, at the compressor load plane; every extra watt lowers the discharge ceiling by dPd_max_per_W_compressor")),
    ]);
    // Thrust-to-discharge-power the Hall envelope must reach for the bus to close.
    let mut rows = Vec::new();
    for (pid, t, lim_name, lim) in [
        ("P-12", hc01, "design allocation 1,350 W", DESIGN_ALLOCATION_W),
        ("P-12", hc01, "HC-03 1,500 W", hc03),
        ("P-25", hc02, "design allocation 1,350 W", DESIGN_ALLOCATION_W),
        ("P-25", hc02, "HC-03 1,500 W", hc03),
        ("P-WORST", hc02, "HC-03 1,500 W", hc03),
    ] {
        let r = get(pid)?;
        let rc = evaluate_point(&inp, pid, Corner::Conservative, &[]).map_err(pe)?;
        let (pm, pmc) = (r.discharge_ceiling(lim), rc.discharge_ceiling(lim));
        rows.push(dict(vec![
            ("point", s(pid)),
            ("thrust_mN", f(t * 1e3)),
            ("limit", s(lim_name)),
            ("P_d_max_W", f(pm)),
            ("T_over_P_d_mN_per_kW", f(t * 1e3 / (pm * 1e-3))),
            ("P_d_max_conservative_W", f(pmc)),
            ("T_over_P_d_conservative_mN_per_kW", f(t * 1e3 / (pmc * 1e-3))),
        ]));
    }
    let p12 = get("P-12")?;
    let p25 = get("P-25")?;
    let text = format!(
        "Until the Hall envelope converges (P2), the discharge power is an allocation. With every other bus term \
         closed, the bus closes at the 12 mN point if H-1 delivers 12 mN at P_d <= {:.0} W (1,350 W design \
         allocation; T/P_d >= {:.1} mN/kW) and the 25 mN capability if it delivers 25 mN at P_d < {:.0} W (HC-03; \
         T/P_d >= {:.1} mN/kW). The registered DBF-1 band upper end (1,350 W discharge) does not fit the bus with the \
         ICP, magnet and common loads: it is a sizing band, and the flight operating ceiling is P_d,max. These are \
         requirements on the Hall envelope, not predictions.",
        p12.discharge_ceiling(DESIGN_ALLOCATION_W),
        hc01 * 1e3 / (p12.discharge_ceiling(DESIGN_ALLOCATION_W) * 1e-3),
        p25.discharge_ceiling(hc03),
        hc02 * 1e3 / (p25.discharge_ceiling(hc03) * 1e-3),
    );
    let closed = closed_tbd(&inp, &official)?;
    let mut reg = BTreeMap::<String, i64>::new();
    for t in &inp.terms {
        *reg.entry(t.closure_class.clone()).or_default() += 1;
    }
    let mut regd = Dict::new();
    for k in CLOSURE_RANK {
        if let Some(v) = reg.get(k) {
            regd.insert(k, Value::int(*v));
        }
    }
    let terms: Vec<Value> = inp
        .terms
        .iter()
        .map(|t| {
            dict(vec![
                ("id", s(t.id.clone())),
                ("quantity", s(t.quantity.clone())),
                ("value", f(t.value)),
                ("low", f(t.low)),
                ("high", f(t.high)),
                ("units", s(t.units.clone())),
                ("evidence_class", s(t.evidence_class.clone())),
                ("evidence_level", s(t.evidence_level.clone())),
                ("closure_class", s(t.closure_class.clone())),
                ("flags", Value::List(t.flags.iter().map(|x| s(x.clone())).collect())),
            ])
        })
        .collect();
    let n_closed = official.tbd.len() as i64 + 3;
    Ok(dict(vec![
        ("schema", s(SCHEMA)),
        ("id", s("power_ledger_v1")),
        ("item", s("A9.38 P6 power closure")),
        ("date", s("2026-10-08")),
        ("boundary", s("bus_power_boundary_a9_v2")),
        ("configuration", s(FLIGHT_CONFIGURATION)),
        ("inputs", dict(vec![("path", s(INPUTS_REL)), ("sha256", s(inp.sha256.clone()))])),
        (
            "thresholds",
            dict(vec![
                ("HC-01_N", f(hc01)),
                ("HC-02_N", f(hc02)),
                ("HC-03_W", f(hc03)),
                ("HC-03_comparator", s("<")),
                ("source", s("abep-config (config/constraints/engineering_constraints_v1.json); assessment only")),
                ("config_manifest_sha256", s(th.manifest_sha256.clone())),
            ]),
        ),
        (
            "owner_allocations",
            dict(vec![
                ("design_allocation_W", f(DESIGN_ALLOCATION_W)),
                ("common_allocation_W", f(COMMON_ALLOCATION_W)),
                ("controls_thermal_allowance_W", f(CONTROLS_THERMAL_ALLOWANCE_W)),
            ]),
        ),
        (
            "official_ledger_tbd",
            dict(vec![
                ("official", Value::int(official.tbd.len() as i64)),
                ("with_compressor", Value::int(with_cp.tbd.len() as i64)),
                ("closure", Value::int(0)),
            ]),
        ),
        ("points", Value::List(points)),
        ("rf_trade_line", Value::List(trade)),
        ("compressor_headroom", headroom),
        ("derived_hall_requirement", dict(vec![("text", s(text)), ("rows", Value::List(rows))])),
        ("closed_official_tbd_terms", closed.clone()),
        ("terms", Value::List(terms)),
        (
            "summary",
            dict(vec![
                ("ledger_terms_closed", Value::int(n_closed)),
                ("tbd_remaining", Value::int(0)),
                ("ledger_terms_by_closure_class", crate::py::dget(&closed, "by_closure_class")?),
                ("ledger_terms_by_evidence_class", crate::py::dget(&closed, "by_evidence_class")?),
                ("register_terms_by_closure_class", Value::Dict(regd)),
            ]),
        ),
        (
            "not",
            Value::List(vec![
                s("not a Hall performance prediction: the discharge power is DESIGN_ALLOCATION_NOT_PREDICTED at every point (HALL_NUMERICS_NOT_CONVERGED)"),
                s("not a gate verdict: HC-03 margins are differences on a design ledger, not a P_bus,1ms,max measurement (A9.1 OQ-A902-01)"),
                s("not a change to the official A9-02 ledger, the admitted power functions or DBF-1"),
                s("not measured: every term is a sourced analog, a model output, an allocation or a frozen engineering assumption with bounds"),
            ]),
        ),
        ("generated_by", s("abep-assess-power-closure (abep_assess::power_closure, abep_subsystems::power::closure_v1)")),
    ]))
}
