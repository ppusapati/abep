//! The P7 thermal-closure record (prereg `outputs`): design-lever search, governing cases, verdicts, allowables,
//! sensitivities, boundary units and the closure state, as JSON plus a Markdown rendering. `dry_assemble` checks that
//! every registered case document assembles (no solve, no temperature).

use super::assess::*;
use super::{num, ClosureError, Context, LOCK_PATH, MARGIN_K, PREREG_PATH};
use abep_subsystems::thermal::assemble::assemble_v2;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;

pub const SCHEMA: &str = "abep_closure_thermal_record_v1";
const GOVERNING_HOT: [&str; 4] = ["TC1-HOT-H-BSTAR", "TC2-HOT-H-B0", "TC3-HOT-I-BSTAR", "TC4-HOT-I-B0"];
const COLD_OP: &str = "TC5-COLD-OP-B0";
const COLD_NONOP: &str = "TC6-COLD-NONOP-B0";

fn grid(ctx: &Context, k: &str) -> Vec<f64> {
    ctx.prereg.raw["design_levers"]["grid"][k]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .filter_map(Value::as_f64)
        .collect()
}

fn case_ids(ctx: &Context) -> Vec<String> {
    ctx.prereg.raw["cases"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .filter_map(|c| c["id"].as_str().map(String::from))
        .collect()
}

/// Assemble every registered case at the first grid point (no solve): the list of assembly reasons per case.
pub fn dry_assemble(ctx: &Context) -> Result<BTreeMap<String, Vec<String>>, ClosureError> {
    let v = Variant { a_rh: grid(ctx, "A_RH_m2")[0], g_rh: grid(ctx, "G_RH_W_K")[0], ..Default::default() };
    let mut out = BTreeMap::new();
    for id in case_ids(ctx) {
        let c = case_def(ctx, &id)?;
        let mut sp = spec_for(ctx, &c, &v)?;
        sp.t_init = ctx.prereg.nodes.iter().filter_map(|n| n["id"].as_str().map(|x| (x.to_string(), 400.0))).collect();
        let case = super::build::build(&ctx.prereg, &sp)?;
        let a = assemble_v2(&case, &ctx.gov);
        out.insert(
            id,
            a.reasons.iter().map(|r| format!("{:?}:{}:{}:{}", r.status, r.code, r.subject, r.detail)).collect(),
        );
    }
    Ok(out)
}

fn temps_c(m: &BTreeMap<String, f64>) -> Value {
    Value::Object(m.iter().map(|(k, v)| (k.clone(), json!(v - K0))).collect())
}

fn run_json(r: &CaseRun) -> Value {
    json!({
        "case_id": r.id,
        "run_status": serde_json::to_value(r.status).unwrap_or(Value::Null),
        "status_reasons": r.reasons,
        "T_max_C": temps_c(&r.t_max_k),
        "T_min_C": temps_c(&r.t_min_k),
        "Q_into_spacecraft_W": r.q_sc_w,
        "biot_max": r.biot_max,
        "property_range_exceeded_K": r.range_exceeded,
        "case_document_sha256": r.case_sha256,
    })
}

/// The full closure run.
pub fn closure_record(ctx: &Context) -> Result<Value, ClosureError> {
    let lims = limits(ctx);
    let h1 = h1_limited(ctx, &lims);
    let a_grid = grid(ctx, "A_RH_m2");
    let g_grid = grid(ctx, "G_RH_W_K");

    // 1. Design-lever grid (TC1, TC3 steady).
    let mut grid_rows = Vec::new();
    let mut evaluated: Vec<(f64, f64, bool, Option<f64>)> = Vec::new();
    let limited: Vec<&Limit> = lims.iter().filter(|l| l.upper_c.is_some()).collect();
    let mut fails_everywhere: BTreeMap<String, bool> = limited.iter().map(|l| (l.node.clone(), true)).collect();
    for &a in &a_grid {
        for &g in &g_grid {
            let v = Variant { a_rh: a, g_rh: g, ..Default::default() };
            let c1 = run_named(ctx, "TC1-HOT-H-BSTAR", &v)?;
            let c3 = run_named(ctx, "TC3-HOT-I-BSTAR", &v)?;
            let m1 = min_margin(&c1, &lims, &h1);
            let m3 = min_margin(&c3, &lims, &h1);
            let m = match (m1, m3) {
                (Some(x), Some(y)) => Some(x.min(y)),
                _ => None,
            };
            for lim in &limited {
                if node_ok(&c1, lim) && node_ok(&c3, lim) {
                    fails_everywhere.insert(lim.node.clone(), false);
                }
            }
            let feasible = m.is_some_and(|x| x >= 0.0);
            evaluated.push((a, g, feasible, m));
            grid_rows.push(json!({
                "A_RH_m2": a, "G_RH_W_K": g, "feasible": feasible, "min_H1_margin_K": m,
                "TC1": {"status": serde_json::to_value(c1.status).unwrap_or(Value::Null), "T_max_C": temps_c(&c1.t_max_k), "Q_into_spacecraft_W": c1.q_sc_w},
                "TC3": {"status": serde_json::to_value(c3.status).unwrap_or(Value::Null), "T_max_C": temps_c(&c3.t_max_k), "Q_into_spacecraft_W": c3.q_sc_w},
            }));
        }
    }
    // 2. Selection and confirmation in TC2 / TC4.
    let mut order: Vec<(f64, f64, bool, Option<f64>)> = evaluated.iter().filter(|x| x.2).cloned().collect();
    order.sort_by(|x, y| x.0.partial_cmp(&y.0).unwrap().then(x.1.partial_cmp(&y.1).unwrap()));
    let mut selected = None;
    let mut confirmations = Vec::new();
    for (a, g, _, _) in &order {
        let v = Variant { a_rh: *a, g_rh: *g, ..Default::default() };
        let c2 = run_named(ctx, "TC2-HOT-H-B0", &v)?;
        let c4 = run_named(ctx, "TC4-HOT-I-B0", &v)?;
        let ok = [&c2, &c4].iter().all(|r| min_margin(r, &lims, &h1).is_some_and(|m| m >= 0.0));
        confirmations.push(json!({"A_RH_m2": a, "G_RH_W_K": g, "confirmed": ok}));
        if ok {
            selected = Some((*a, *g, "FEASIBLE_CONFIRMED"));
            break;
        }
    }
    let selected = match selected {
        Some(x) => x,
        None => {
            let mut best: Option<(f64, f64, f64)> = None;
            for (a, g, _, m) in &evaluated {
                let m = m.unwrap_or(f64::NEG_INFINITY);
                if best.is_none_or(|b| m > b.2) {
                    best = Some((*a, *g, m));
                }
            }
            let b = best.ok_or_else(|| ClosureError("empty design grid".into()))?;
            (b.0, b.1, "NO_FEASIBLE_POINT_MAX_MIN_MARGIN")
        }
    };
    let base = Variant { a_rh: selected.0, g_rh: selected.1, ..Default::default() };

    // 3. Every registered case at the selected design.
    let mut runs: BTreeMap<String, CaseRun> = BTreeMap::new();
    for id in case_ids(ctx) {
        runs.insert(id.clone(), run_named(ctx, &id, &base)?);
    }
    // 4. Node verdicts.
    let coated: Vec<String> = ctx.prereg.raw["margin_rule"]["coated_nodes"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .filter_map(|x| x.as_str().map(String::from))
        .collect();
    let mut node_rows = Map::new();
    let mut fail_nodes: Vec<(String, bool)> = Vec::new();
    let mut blocked: Vec<String> = Vec::new();
    for id in GOVERNING_HOT {
        let r = &runs[id];
        if !r.converged() && r.range_exceeded.is_empty() {
            blocked.push(format!("{id}: {:?}", r.reasons));
        }
    }
    for lim in &lims {
        let mut per_case = Map::new();
        let mut t_max: Option<f64> = None;
        let mut range_fail = false;
        for id in GOVERNING_HOT {
            let r = &runs[id];
            let t = r.t_max_k.get(&lim.node).copied();
            if r.range_exceeded.contains_key(&lim.node) {
                range_fail = true;
            }
            if let Some(t) = t.filter(|_| r.converged()) {
                t_max = Some(t_max.map_or(t, |m: f64| m.max(t)));
            }
            per_case.insert(
                id.into(),
                json!({
                    "T_C": t.filter(|_| r.converged()).map(|x| x - K0),
                    "margin_K": t.filter(|_| r.converged()).and_then(|x| margin(lim, x)),
                }),
            );
        }
        let t_max_c = t_max.map(|t| t - K0);
        let (verdict, required) = if range_fail {
            ("FAIL", None)
        } else if t_max_c.is_none() {
            ("NOT_EVALUATED", None)
        } else if let Some(u) = lim.upper_c {
            if t_max_c.unwrap() <= u - MARGIN_K {
                ("PASS", None)
            } else {
                ("FAIL", None)
            }
        } else {
            let req = t_max_c.unwrap() + MARGIN_K;
            if lim.absolute_c.is_some_and(|a| req > a) {
                ("FAIL", Some(req))
            } else {
                ("REQUIREMENT", Some(req))
            }
        };
        if verdict == "FAIL" {
            fail_nodes.push((lim.node.clone(), lim.upper_c.is_some()));
        }
        let cold_op = &runs[COLD_OP];
        let cold_non = &runs[COLD_NONOP];
        let t_min_op = cold_op.t_min_k.get(&lim.node).filter(|_| cold_op.converged()).map(|t| t - K0);
        let t_min_non = cold_non.t_min_k.get(&lim.node).filter(|_| cold_non.converged()).map(|t| t - K0);
        let mut row = json!({
            "limit_class": lim.class,
            "upper_limit_C": lim.upper_c,
            "design_ceiling_C": lim.upper_c.map(|u| u - MARGIN_K),
            "absolute_ceiling_C": lim.absolute_c,
            "limit_basis": lim.basis,
            "governing_hot": per_case,
            "T_max_hot_C": t_max_c,
            "margin_K": t_max_c.and_then(|t| lim.upper_c.map(|u| u - MARGIN_K - t)),
            "verdict": verdict,
            "required_continuous_use_capability_C": required,
            "T_min_cold_operating_C": t_min_op,
            "T_min_cold_nonoperating_C": t_min_non,
            "cold_cycle_range_C": match (t_min_non, t_max_c) { (Some(a), Some(b)) => json!([a, b]), _ => Value::Null },
        });
        if coated.contains(&lim.node) {
            row["required_coating_capability_C"] = json!(t_max_c.map(|t| t + MARGIN_K));
        }
        node_rows.insert(lim.node.clone(), row);
    }
    // 4b. P8 materials screening ceilings, registered DCR triggers and thermal cycling (prereg materials_screening).
    let ms = &ctx.prereg.raw["materials_screening"];
    let hot_c = |n: &str| node_rows.get(n).and_then(|r| r["T_max_hot_C"].as_f64());
    let cold_c = |n: &str| {
        node_rows.get(n).and_then(|r| r["T_min_cold_nonoperating_C"].as_f64().or(r["T_min_cold_operating_C"].as_f64()))
    };
    let mut screening = Map::new();
    if let Some(c) = ms["ceilings_C"].as_object() {
        for (n, rows) in c {
            let t = hot_c(n);
            let per: Map<String, Value> = rows
                .as_object()
                .cloned()
                .unwrap_or_default()
                .into_iter()
                .map(|(grade, ceil)| {
                    let ce = ceil.as_f64().unwrap_or(f64::NAN);
                    (grade, json!({"ceiling_C": ce, "T_max_hot_C": t, "headroom_K": t.map(|x| ce - x), "within": t.map(|x| x <= ce)}))
                })
                .collect();
            screening.insert(n.clone(), Value::Object(per));
        }
    }
    let mut fired: Vec<Value> = Vec::new();
    let mut triggers = Vec::new();
    for tr in ms["dcr_triggers"].as_array().cloned().unwrap_or_default() {
        let n = tr["node"].as_str().unwrap_or("");
        let above = tr["above_C"].as_f64().unwrap_or(f64::INFINITY);
        let t = hot_c(n);
        let fires = t.map(|x| x > above);
        let row = json!({"id": tr["id"], "node": n, "above_C": above, "T_max_hot_C": t, "fires": fires, "action": tr["action"]});
        if fires == Some(true) {
            fired.push(row.clone());
        }
        triggers.push(row);
    }
    let mism = ms["thermal_cycling"]["radial_mismatch_mm_per_100K"].as_array().cloned().unwrap_or_default();
    let mism: Vec<f64> = mism.iter().filter_map(Value::as_f64).collect();
    let d_hot = match (
        hot_c("H1_ANODE"),
        node_rows.get("H1_WALL_OUT").and_then(|r| r["governing_hot"]["TC1-HOT-H-BSTAR"]["T_C"].as_f64()),
        runs["TC1-HOT-H-BSTAR"].t_max_k.get("H1_ANODE"),
    ) {
        (_, Some(w), Some(a)) => Some(a - K0 - w),
        _ => None,
    };
    let swing = |n: &str| match (hot_c(n), cold_c(n)) {
        (Some(h), Some(c)) => Some(h - c),
        _ => None,
    };
    let cycling = json!({
        "N_cycles_bound": ms["thermal_cycling"]["N_cycles_bound"],
        "hot_cold_swing_K": {"H1_ANODE": swing("H1_ANODE"), "N_COLLECTOR": swing("N_COLLECTOR"), "H1_WALL_IN": swing("H1_WALL_IN"), "H1_WALL_OUT": swing("H1_WALL_OUT")},
        "anode_minus_outer_wall_TC1_K": d_hot,
        "anode_radial_differential_growth_TC1_mm": d_hot.map(|d| mism.iter().map(|m| m * d / 100.0).collect::<Vec<_>>()),
        "anode_radial_differential_growth_over_swing_mm": swing("H1_ANODE").map(|s| mism.iter().map(|m| m * s / 100.0).collect::<Vec<_>>()),
    });
    let materials_screening = json!({"source": ms["source"], "ceilings": screening, "dcr_triggers": triggers, "fired": fired, "thermal_cycling": cycling});

    // 5. Cold lower limits (heater sizing on N_MATCH).
    let mut heaters = Map::new();
    for lim in lims.iter().filter(|l| l.lower_op_c.is_some() || l.lower_nonop_c.is_some()) {
        for (case, low) in [(COLD_OP, lim.lower_op_c), (COLD_NONOP, lim.lower_nonop_c)] {
            let Some(low) = low else { continue };
            let r = &runs[case];
            let t = r.t_min_k.get(&lim.node).filter(|_| r.converged()).map(|t| t - K0);
            let heater = match t {
                Some(t) if t >= low => Some(0.0),
                Some(_) => bisect(
                    |q| {
                        let v = Variant { heater: Some((lim.node.clone(), q)), ..base.clone() };
                        let rr = run_named(ctx, case, &v)?;
                        Ok(rr.converged() && rr.t_min_k.get(&lim.node).is_some_and(|t| t - K0 < low))
                    },
                    200.0,
                    0.05,
                    40,
                )?
                .map(|x| x + 0.05),
                None => None,
            };
            heaters.insert(
                format!("{}@{}", lim.node, case),
                json!({"T_min_C": t, "lower_limit_C": low, "heater_W": heater}),
            );
        }
    }
    // 6. Allowables at the selected design (TC1 / TC3 environment, steady).
    let mut allow = Map::new();
    let icp_lim: Vec<&Limit> = lims.iter().filter(|l| l.upper_c.is_some() && (l.node.starts_with("N_"))).collect();
    let h1_lims: Vec<&Limit> = lims.iter().filter(|l| h1.contains(&l.node)).collect();
    for lim in &h1_lims {
        let x = bisect(
            |p| {
                Ok(node_ok(
                    &run_named(ctx, "TC1-HOT-H-BSTAR", &Variant { op_edit: Some(OpEdit::PD(p)), ..base.clone() })?,
                    lim,
                ))
            },
            3000.0,
            0.01,
            60,
        )?;
        allow.insert(
            format!("AL-PD/{}", lim.node),
            json!({"P_d_allowable_W": x, "case": "TC1-HOT-H-BSTAR", "factor": 1.2}),
        );
    }
    for lim in &icp_lim {
        let x = bisect(
            |p| {
                Ok(node_ok(
                    &run_named(ctx, "TC3-HOT-I-BSTAR", &Variant { op_edit: Some(OpEdit::PFwd(p)), ..base.clone() })?,
                    lim,
                ))
            },
            3000.0,
            0.01,
            60,
        )?;
        allow.insert(
            format!("AL-PFWD/{}", lim.node),
            json!({"P_fwd_allowable_W": x, "case": "TC3-HOT-I-BSTAR", "factor": 1.2}),
        );
        let y = bisect(
            |q| {
                Ok(node_ok(
                    &run_named(ctx, "TC1-HOT-H-BSTAR", &Variant { op_edit: Some(OpEdit::Plume(q)), ..base.clone() })?,
                    lim,
                ))
            },
            2000.0,
            0.01,
            60,
        )?;
        allow.insert(
            format!("AL-PLUME/{}", lim.node),
            json!({"Q_plume_to_icp_allowable_W_before_factor": y, "case": "TC1-HOT-H-BSTAR", "factor": 1.2}),
        );
        let z = bisect(
            |q| {
                Ok(node_ok(
                    &run_named(ctx, "TC1-HOT-H-BSTAR", &Variant { op_edit: Some(OpEdit::Return(q)), ..base.clone() })?,
                    lim,
                ))
            },
            2000.0,
            0.01,
            60,
        )?;
        allow.insert(
            format!("AL-RETURN/{}", lim.node),
            json!({"Q_return_allowable_W_before_factor": z, "case": "TC1-HOT-H-BSTAR", "factor": 1.2}),
        );
    }
    // 7. Sensitivities (non-governing).
    let mut sens = Map::new();
    let ovs = ctx.prereg.raw["sensitivities"]["overrides"].as_object().cloned().unwrap_or_default();
    let mut icd_change = false;
    for (name, o) in &ovs {
        let mut v = base.clone();
        if let Some(links) = o["links"].as_object() {
            for (lid, f) in links {
                v.link_overrides.insert(
                    lid.clone(),
                    f.as_object().map(|m| m.iter().map(|(a, b)| (a.clone(), b.clone())).collect()).unwrap_or_default(),
                );
            }
        }
        if let Some(inp) = o["inputs"].as_object() {
            for (k, x) in inp {
                v.input_overrides.insert(k.clone(), x.as_f64().unwrap_or(f64::NAN));
            }
        }
        v.t_sc_override = o["T_SC_K"].as_f64();
        let mut cases = vec!["TC1-HOT-H-BSTAR"];
        if v.t_sc_override.is_some() {
            cases.push("TC3-HOT-I-BSTAR");
        }
        let mut rows = Map::new();
        for c in cases {
            let r = run_named(ctx, c, &v)?;
            if v.t_sc_override.is_some() {
                for lim in lims.iter().filter(|l| l.upper_c.is_some()) {
                    let ref_ok = node_ok(&runs[c], lim);
                    if node_ok(&r, lim) != ref_ok {
                        icd_change = true;
                    }
                }
            }
            rows.insert(c.into(), run_json(&r));
        }
        sens.insert(name.clone(), Value::Object(rows));
    }
    // 8. Boundary units and the spacecraft interface.
    let units = boundary_units(ctx)?;
    let q_sc = GOVERNING_HOT.iter().filter_map(|id| runs[*id].q_sc_w).fold(f64::NEG_INFINITY, f64::max);
    let q_sc = if q_sc.is_finite() { Some(q_sc) } else { None };
    let q_sc_alloc = 50.0;
    // Reporting only (no verdict, no reselection): the smallest grid point whose TC1 and TC3 heat into the spacecraft
    // is within the 50 W governing allocation.
    let q_sc_reading = grid_rows
        .iter()
        .find(|r| {
            [&r["TC1"], &r["TC3"]].iter().all(|c| c["Q_into_spacecraft_W"].as_f64().is_some_and(|q| q <= q_sc_alloc))
        })
        .map(|r| json!({"A_RH_m2": r["A_RH_m2"], "G_RH_W_K": r["G_RH_W_K"], "TC1_Q_W": r["TC1"]["Q_into_spacecraft_W"], "TC3_Q_W": r["TC3"]["Q_into_spacecraft_W"]}));

    // 9. Closure state (prereg closure_state_rule).
    let confirmed = selected.2 == "FEASIBLE_CONFIRMED";
    let dcr_nodes: Vec<String> = fail_nodes
        .iter()
        .filter(|(n, limited)| *limited && (!confirmed || fails_everywhere.get(n).copied().unwrap_or(true)))
        .map(|(n, _)| n.clone())
        .collect();
    let fundamental: Vec<String> = fail_nodes.iter().filter(|(_, limited)| !limited).map(|(n, _)| n.clone()).collect();
    // CLOSED is not reachable here (NOT_VALIDATED model, PARAMETRIC cases): FROZEN FOR EM is the highest state.
    let state = if !dcr_nodes.is_empty() || !fired.is_empty() {
        "DCR REQUIRED"
    } else if !fundamental.is_empty() {
        "FUNDAMENTAL NON-CLOSURE"
    } else if !blocked.is_empty() || !fail_nodes.is_empty() {
        "BLOCKED BY SPECIFIC MISSING EVIDENCE"
    } else if icd_change || q_sc.is_some_and(|q| q > q_sc_alloc) {
        "REFERENCE/ICD DEPENDENT"
    } else {
        "FROZEN FOR EM"
    };

    let runs_json: Map<String, Value> = runs.iter().map(|(k, r)| (k.clone(), run_json(r))).collect();
    Ok(json!({
        "schema": SCHEMA,
        "id": "P7-THERMAL-CLOSURE",
        "item": "P7 thermal closure (A9.38 priority 7)",
        "lane": "L-THERMAL",
        "model": {"id": "NP-THERMAL-CATHODELESS", "version": "2.0.0", "case_class": "PARAMETRIC", "validation_status": "NOT_VALIDATED", "label": "PARAMETRIC_NOT_A_PREDICTION"},
        "preregistration": {"path": PREREG_PATH, "sha256": ctx.prereg.sha256, "lock_path": LOCK_PATH, "lock_sha256": ctx.lock_sha256},
        "load_inputs": {"path": ctx.inputs_path, "sha256": ctx.inputs_sha256, "id": ctx.inputs["id"], "status": ctx.inputs["status"]},
        "run_provenance": {"rust_commit": ctx.run.rust_commit, "rust_tree_dirty": ctx.run.rust_tree_dirty, "governed_thermal_records": ctx.gov.hashes()},
        "environment_factors": env_factors(ctx)?,
        "design_lever_search": {"grid": grid_rows, "confirmations": confirmations, "selected": {"A_RH_m2": selected.0, "G_RH_W_K": selected.1, "basis": selected.2, "R_HALL_mass_kg_at_4_kg_m2": selected.0 * 4.0}},
        "governing_and_registered_runs": runs_json,
        "nodes": node_rows,
        "materials_screening": materials_screening,
        "cold_lower_limits": heaters,
        "allowables": allow,
        "sensitivities": sens,
        "boundary_units": units,
        "spacecraft_interface": {"Q_into_spacecraft_max_hot_W": q_sc, "owner_provisional_allocation_W": {"governing": 50.0, "contingency_ceiling": 100.0, "stretch": 25.0}, "within_governing_allocation": q_sc.map(|q| q <= q_sc_alloc), "smallest_grid_point_within_allocation_TC1_TC3": q_sc_reading, "T_SC_sensitivity_changes_a_verdict": icd_change, "status": "REFERENCE_PENDING_ICD"},
        "closure": {
            "state": state,
            "dcr_nodes": dcr_nodes,
            "fundamental_nodes": fundamental,
            "materials_dcr_triggers_fired": fired,
            "blocked_cases": blocked,
            "requirement_nodes": node_rows.iter().filter(|(_, r)| r["verdict"] == "REQUIREMENT").map(|(n, _)| n.clone()).collect::<Vec<_>>(),
            "rule": ctx.prereg.raw["closure_state_rule"]["precedence"],
        },
    }))
}

fn env_factors(ctx: &Context) -> Result<Value, ClosureError> {
    use super::env::*;
    let mut o = Map::new();
    for alt in [180.0, 230.0] {
        o.insert(format!("{alt}_km"), json!({
            "beta_star_deg": beta_star(alt).to_degrees(),
            "eclipse_fraction_beta0_admitted_kernel": abep_mission::propagation::eclipse_fraction(alt, 0.0).map_err(|e| ClosureError(e.to_string()))?,
            "eclipse_fraction_beta0_local": eclipse_fraction_local(alt, 0.0),
            "period_s": period(alt),
            "F_earth_LATERAL": ctx.prereg.earth_factor(EnvType::Lateral, alt),
            "F_earth_AFT_FACE": ctx.prereg.earth_factor(EnvType::AftFace, alt),
            "F_earth_ZENITH": 0.0,
            "rho_max_kg_m3": ctx.rho(alt)?,
        }));
    }
    let _ = num;
    Ok(Value::Object(o))
}

fn f1(v: &Value) -> String {
    match v.as_f64() {
        Some(x) => format!("{x:.1}"),
        None => "-".into(),
    }
}

/// Markdown rendering of the record (the JSON governs).
pub fn markdown(rec: &Value) -> String {
    let st = |v: &Value| v.as_str().unwrap_or("").to_string();
    let mut m = String::new();
    let ver = rec["load_inputs"]["id"].as_str().and_then(|x| x.rsplit('-').next()).unwrap_or("v1").to_string();
    m.push_str(&format!("# P7 thermal closure {ver} (DBF-1, frozen topology)\n\n"));
    m.push_str(&format!(
        "Companion of `thermal_closure_{ver}.json` (the JSON governs). Model NP-THERMAL-CATHODELESS 2.0.0, case class \
PARAMETRIC (label PARAMETRIC_NOT_A_PREDICTION), validation status NOT_VALIDATED. Preregistration `{}` (sha256 `{}`); \
load inputs `{}` (sha256 `{}`); Rust commit `{}`.\n\n",
        st(&rec["preregistration"]["path"]),
        st(&rec["preregistration"]["sha256"]),
        st(&rec["load_inputs"]["path"]),
        st(&rec["load_inputs"]["sha256"]),
        st(&rec["run_provenance"]["rust_commit"])
    ));
    m.push_str(&format!("**Closure state: {}**\n\n", st(&rec["closure"]["state"])));
    let sel = &rec["design_lever_search"]["selected"];
    m.push_str(&format!(
        "Selected design levers: R_HALL area {} m^2, back-plate doubler {} W/K ({}); R_HALL mass at 4 kg/m^2: {} kg.\n\n",
        sel["A_RH_m2"],
        sel["G_RH_W_K"],
        st(&sel["basis"]),
        f1(&sel["R_HALL_mass_kg_at_4_kg_m2"])
    ));
    m.push_str("## Nodes (governing hot cases TC1-TC4 with 1.2 x heat loads; cold TC5 / TC6)\n\n");
    m.push_str(
        "| node | limit class | limit degC | ceiling (limit - 50 K) | T max hot degC | margin K | verdict | required \
capability degC | coating capability degC | T min cold op / non-op degC |\n|---|---|---|---|---|---|---|---|---|---|\n",
    );
    if let Some(nodes) = rec["nodes"].as_object() {
        for (n, r) in nodes {
            m.push_str(&format!(
                "| {n} | {} | {} | {} | {} | {} | {} | {} | {} | {} / {} |\n",
                st(&r["limit_class"]),
                f1(&r["upper_limit_C"]),
                f1(&r["design_ceiling_C"]),
                f1(&r["T_max_hot_C"]),
                f1(&r["margin_K"]),
                st(&r["verdict"]),
                f1(&r["required_continuous_use_capability_C"]),
                f1(&r["required_coating_capability_C"]),
                f1(&r["T_min_cold_operating_C"]),
                f1(&r["T_min_cold_nonoperating_C"])
            ));
        }
    }
    m.push_str("\n## Per case (T max / T min, degC)\n\n");
    if let Some(runs) = rec["governing_and_registered_runs"].as_object() {
        let ids: Vec<&String> = runs.keys().collect();
        m.push_str("| node |");
        for id in &ids {
            m.push_str(&format!(" {id} |"));
        }
        m.push_str("\n|---|");
        for _ in &ids {
            m.push_str("---|");
        }
        m.push('\n');
        if let Some(first) = runs.values().find_map(|r| r["T_max_C"].as_object().filter(|o| !o.is_empty())) {
            for n in first.keys() {
                m.push_str(&format!("| {n} |"));
                for id in &ids {
                    let r = &runs[id.as_str()];
                    m.push_str(&format!(" {} / {} |", f1(&r["T_max_C"][n]), f1(&r["T_min_C"][n])));
                }
                m.push('\n');
            }
        }
        m.push_str("| run status |");
        for id in &ids {
            m.push_str(&format!(" {} |", st(&runs[id.as_str()]["run_status"])));
        }
        m.push_str("\n| Q into spacecraft W |");
        for id in &ids {
            m.push_str(&format!(" {} |", f1(&runs[id.as_str()]["Q_into_spacecraft_W"])));
        }
        m.push_str("\n\n");
    }
    m.push_str("## Allowables (bisection at the selected design, 1.2 x loads)\n\n| allowable | value |\n|---|---|\n");
    if let Some(a) = rec["allowables"].as_object() {
        for (k, v) in a {
            let val = v
                .as_object()
                .and_then(|o| {
                    o.iter().find(|(kk, _)| kk.contains("allowable")).map(|(kk, vv)| format!("{kk} = {}", f1(vv)))
                })
                .unwrap_or_default();
            m.push_str(&format!("| {k} | {val} |\n"));
        }
    }
    m.push_str(
        "\n## Boundary units (rejection requirement)\n\n| unit | Q hot W | design T degC | radiator m^2 | heater op W | \
heater non-op W |\n|---|---|---|---|---|---|\n",
    );
    if let Some(u) = rec["boundary_units"].as_object() {
        for (k, v) in u {
            let area = match v["radiator_area_m2"].as_f64() {
                Some(x) => format!("{x:.3}"),
                None => "-".into(),
            };
            m.push_str(&format!(
                "| {k} | {} | {} | {area} | {} | {} |\n",
                f1(&v["Q_hot_W"]),
                f1(&v["design_temperature_C"]),
                f1(&v["heater_W_at_lower_operating_C"]),
                f1(&v["heater_W_at_lower_nonoperating_C"])
            ));
        }
    }
    m.push_str("\n## Cold lower limits\n\n");
    if let Some(h) = rec["cold_lower_limits"].as_object() {
        for (k, v) in h {
            m.push_str(&format!(
                "- {k}: T_min {} degC vs {} degC; heater {} W\n",
                f1(&v["T_min_C"]),
                f1(&v["lower_limit_C"]),
                f1(&v["heater_W"])
            ));
        }
    }
    m.push_str("\n## P8 materials screening ceilings and DCR triggers (T max hot, 1.2 x loads)\n\n");
    m.push_str("| node | grade | ceiling degC | T max hot degC | headroom K |\n|---|---|---|---|---|\n");
    if let Some(c) = rec["materials_screening"]["ceilings"].as_object() {
        for (n, rows) in c {
            for (g, r) in rows.as_object().cloned().unwrap_or_default() {
                m.push_str(&format!(
                    "| {n} | {g} | {} | {} | {} |\n",
                    f1(&r["ceiling_C"]),
                    f1(&r["T_max_hot_C"]),
                    f1(&r["headroom_K"])
                ));
            }
        }
    }
    m.push_str("\n| trigger | node | above degC | fires | action |\n|---|---|---|---|---|\n");
    for t in rec["materials_screening"]["dcr_triggers"].as_array().cloned().unwrap_or_default() {
        m.push_str(&format!(
            "| {} | {} | {} | {} | {} |\n",
            st(&t["id"]),
            st(&t["node"]),
            f1(&t["above_C"]),
            t["fires"],
            st(&t["action"])
        ));
    }
    m.push_str(&format!(
        "\nThermal cycling: cycle bound {}; hot / cold swing K {}; anode - outer wall (TC1) {} K, radial differential growth \
(TC1) {} mm, over the swing {} mm.\n",
        rec["materials_screening"]["thermal_cycling"]["N_cycles_bound"],
        rec["materials_screening"]["thermal_cycling"]["hot_cold_swing_K"],
        f1(&rec["materials_screening"]["thermal_cycling"]["anode_minus_outer_wall_TC1_K"]),
        rec["materials_screening"]["thermal_cycling"]["anode_radial_differential_growth_TC1_mm"],
        rec["materials_screening"]["thermal_cycling"]["anode_radial_differential_growth_over_swing_mm"]
    ));
    let sc = &rec["spacecraft_interface"];
    m.push_str(&format!(
        "\n## Spacecraft interface\n\nMax heat into the spacecraft (hot cases): {} W against the owner provisional 50 W \
governing allocation; the T_SC 20 / 40 / 60 degC sensitivity changes a verdict: {}; smallest R_HALL grid point \
keeping TC1 and TC3 within 50 W: {}. Status REFERENCE_PENDING_ICD.\n\n",
        f1(&sc["Q_into_spacecraft_max_hot_W"]),
        sc["T_SC_sensitivity_changes_a_verdict"],
        sc["smallest_grid_point_within_allocation_TC1_TC3"]
    ));
    m.push_str("## Sensitivities (non-governing, TC1)\n\n| sensitivity | node T max degC (TC1) |\n|---|---|\n");
    if let Some(s) = rec["sensitivities"].as_object() {
        for (k, v) in s {
            let r = &v["TC1-HOT-H-BSTAR"];
            let t = r["T_max_C"]
                .as_object()
                .map(|o| o.iter().map(|(n, x)| format!("{n} {}", f1(x))).collect::<Vec<_>>().join(", "))
                .unwrap_or_default();
            m.push_str(&format!("| {k} ({}) | {t} |\n", st(&r["run_status"])));
        }
    }
    m.push_str(&format!(
        "\n## Closure\n\nState **{}**. DCR nodes: {}. Fundamental: {}. Requirement-only nodes: {}.\n",
        st(&rec["closure"]["state"]),
        rec["closure"]["dcr_nodes"],
        rec["closure"]["fundamental_nodes"],
        rec["closure"]["requirement_nodes"]
    ));
    m
}
