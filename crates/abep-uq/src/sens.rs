//! F8 deterministic sensitivities (`robust_optimizer.pointing_sensitivity`, `theta_ratio_index`,
//! `compressor_elasticities`, `plant_with_overrides`, `fixed_coefficients`) and the design part of the evidence-gate
//! snapshot (`design_gate_snapshot`, without the RVM part, which the assessment layer supplies).

use crate::mc::state_eval;
use crate::robust::Survivor;
use abep_design::err::{opt_err, DResult, DesignError};
use abep_design::inputs::{read_pinned, UpstreamInputs, F5_REL, MP_REL};
use abep_design::optimizer::plenum;
use abep_gaspath::compressor::DragCompressor;
use abep_gaspath::compressor_synthesis as cs;
use abep_gaspath::plenum_feed::{intake_side, steady_operating_point, Chain, CompressorPlant, Sp3, T_CHAIN_K};
use abep_gaspath::rec::{fnum, onum};
use abep_mission::intake_drag::DESIGN_CASE_STATE_ID;
use serde_json::{Map, Value};
use std::collections::HashMap;
use std::path::Path;

pub const ELASTICITY_STEP: f64 = 1e-3;

/// `theta_ratio_index(f1)`: (scenario, L/d bits, phi bits, species) -> (eta_c(5) / eta_c(0), CR(5) / CR(0)) at the
/// design-case reference state (frozen surface nodes).
pub fn theta_ratio_index(inp: &UpstreamInputs) -> HashMap<(String, u64, u64, String), (f64, f64)> {
    let mut base: HashMap<(String, u64, u64, String), HashMap<u64, (f64, f64)>> = HashMap::new();
    for r in inp.f1.species_rows.iter().filter(|r| r.state_id == DESIGN_CASE_STATE_ID) {
        let k = (
            format!("{}_a{}", r.scattering, abep_gaspath::pyops::py_format_g(r.alpha)),
            r.l_over_d.to_bits(),
            r.phi.to_bits(),
            r.species.clone(),
        );
        base.entry(k).or_default().insert(r.theta_deg.to_bits(), (r.eta_c, r.cr_passive));
    }
    let mut out = HashMap::new();
    for (k, d) in base {
        if let (Some(a), Some(b)) = (d.get(&0.0f64.to_bits()), d.get(&5.0f64.to_bits())) {
            out.insert(k, (b.0 / a.0, b.1 / a.1));
        }
    }
    out
}

/// `pointing_sensitivity(inp, cands, scenarios, wall)`: theta = 5 deg node at the design-case reference point only;
/// status and delivered flow there vs theta 0. The required design states have no theta node (NOT_EVALUATED).
pub fn pointing_sensitivity(
    inp: &UpstreamInputs,
    cands: &[Survivor],
    scenarios: &[String],
    wall: &str,
) -> DResult<Vec<(String, Vec<(String, Value)>)>> {
    let tr = theta_ratio_index(inp);
    let mut out = vec![];
    for c in cands {
        let (_, ld, phi) = *inp
            .geometry
            .get(&c.candidate)
            .ok_or_else(|| DesignError::new("KeyError", format!("'{}'", c.candidate)))?;
        let plant = inp.plant(&c.compressor)?;
        let pl = plenum(inp, c.v_m3, wall)?;
        let fc = inp.filter(&c.filter)?;
        let mut per = vec![];
        for sc in scenarios {
            let rec0 = inp.record(&c.candidate, sc, DESIGN_CASE_STATE_ID)?;
            let mut r = [(0.0, 0.0); 3];
            for (i, s) in ["O", "N2", "O2"].iter().enumerate() {
                r[i] = *tr
                    .get(&(sc.clone(), ld.to_bits(), phi.to_bits(), s.to_string()))
                    .ok_or_else(|| DesignError::new("KeyError", format!("({sc:?}, {ld}, {phi}, '{s}')")))?;
            }
            let mut rec5 = rec0.clone();
            for i in 0..3 {
                rec5.mdot_fwd_kgps[i] = rec0.mdot_fwd_kgps[i] * r[i].0;
                rec5.p_passive_pa[i] = rec0.p_passive_pa[i] * r[i].1;
            }
            let mut vals = vec![];
            for rec in [rec0.clone(), rec5] {
                let chain = Chain { intake: rec, filt: fc.clone(), plant: plant.clone(), plenum: pl.clone() };
                let op = steady_operating_point(&chain, &inp.materials, c.p_set_pa, 1.0, 1.0)?;
                let st = op["status"].as_str().unwrap_or_default().to_string();
                let md = match op.get("offered") {
                    Some(Value::Object(o)) if !o.is_empty() => {
                        o.get("mdot_total_kgps").and_then(abep_gaspath::rec::as_f64)
                    }
                    _ => None,
                };
                vals.push((st, md));
            }
            let rel = match (vals[0].1, vals[1].1) {
                (Some(a), Some(b)) if a != 0.0 && b != 0.0 => Some(b / a - 1.0),
                _ => None,
            };
            let mut m = Map::new();
            m.insert("status_theta0".into(), Value::String(vals[0].0.clone()));
            m.insert("status_theta5".into(), Value::String(vals[1].0.clone()));
            m.insert("mdot_theta0_kgps".into(), onum(vals[0].1));
            m.insert("mdot_theta5_kgps".into(), onum(vals[1].1));
            m.insert("rel_change".into(), onum(rel));
            per.push((sc.clone(), Value::Object(m)));
        }
        out.push((c.design_id.clone(), per));
    }
    Ok(out)
}

/// `fixed_coefficients()`: the FIXED DragCompressor coefficients in FIELD_ROLES order.
pub fn fixed_coefficients() -> Vec<&'static str> {
    cs::FIELD_ROLES.iter().filter(|r| r.1 == cs::FIXED).map(|r| r.0).collect()
}

/// `plant_with_overrides(design, overrides)`: the plant exactly as `CompressorPlant.from_design` builds it, with
/// FIXED coefficients overridden (validated; anything else is refused).
pub fn plant_with_overrides(
    inp: &UpstreamInputs,
    design: &Map<String, Value>,
    overrides: &[(&str, f64)],
) -> DResult<CompressorPlant> {
    cs::validate_design(inp.ctx(), design)?;
    let mut checked = vec![];
    for (f, v) in overrides {
        if cs::FIELD_ROLES.iter().find(|r| r.0 == *f).map(|r| r.1) != Some(cs::FIXED) {
            return Err(opt_err(format!("only FIXED compressor coefficients can be perturbed, not {f}")));
        }
        checked.push((*f, cs::validate_coefficient(f, Some(&Value::from(*v)))?));
    }
    let mut plant = CompressorPlant::from_design(inp.ctx(), design, T_CHAIN_K)?;
    for (f, v) in checked {
        if !plant.comp.set_float(f, v) {
            return Err(opt_err(format!("only FIXED compressor coefficients can be perturbed, not {f}")));
        }
    }
    Ok(plant)
}

fn code_default(coef: &str) -> DResult<f64> {
    DragCompressor::default()
        .field_value(coef)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| DesignError::new("KeyError", format!("'{coef}'")))
}

/// `compressor_elasticities(inp, cand, scenarios, wall, step)`: d ln(obj) / d ln(c) by central difference for every
/// FIXED coefficient, max |elasticity| over the scenarios; a perturbed status that differs from the nominal status is
/// flagged (STATUS_FLIP). No coefficient range is implied.
pub fn compressor_elasticities(
    inp: &UpstreamInputs,
    cand: &Survivor,
    scenarios: &[String],
    wall: &str,
    step: f64,
) -> DResult<Vec<(String, Value)>> {
    let design = inp
        .designs
        .get(&cand.compressor)
        .ok_or_else(|| DesignError::new("KeyError", format!("'{}'", cand.compressor)))?;
    let pl = plenum(inp, cand.v_m3, wall)?;
    let fc = inp.filter(&cand.filter)?;
    let mut nominal_ok: HashMap<String, bool> = HashMap::new();
    let mut sides: HashMap<String, (Vec<Sp3>, Vec<Sp3>)> = HashMap::new();
    let mut states_by_sc = HashMap::new();
    let mut out = vec![];
    let py_max = |a: f64, b: f64| if b > a { b } else { a };
    for coef in fixed_coefficients() {
        let c0 = code_default(coef)?;
        let mut worst = [0.0f64; 3];
        let mut flip = false;
        for sc in scenarios {
            if !states_by_sc.contains_key(sc) {
                let st: Vec<_> =
                    inp.states.iter().map(|s| inp.record(&cand.candidate, sc, s).cloned()).collect::<DResult<_>>()?;
                states_by_sc.insert(sc.clone(), st);
            }
            let states = &states_by_sc[sc];
            if !sides.contains_key(sc) {
                sides.insert(sc.clone(), intake_side(states, fc, 1.0)?);
            }
            let side = &sides[sc];
            if !nominal_ok.contains_key(sc) {
                let p0 = plant_with_overrides(inp, design, &[])?;
                nominal_ok.insert(sc.clone(), state_eval(inp, states, &p0, &pl, cand.p_set_pa, side)?.all_ok[0]);
            }
            let mut evs = vec![];
            for f in [1.0 - step, 1.0 + step] {
                let p = plant_with_overrides(inp, design, &[(coef, c0 * f)])?;
                evs.push(state_eval(inp, states, &p, &pl, cand.p_set_pa, side)?);
            }
            let oks: Vec<bool> = evs.iter().map(|e| e.all_ok[0]).collect();
            flip = flip || oks.iter().any(|o| *o != nominal_ok[sc]);
            if !oks.iter().all(|o| *o) {
                continue;
            }
            let pairs = [
                (evs[0].mdot_min[0], evs[1].mdot_min[0]),
                (evs[0].p_el_max[0], evs[1].p_el_max[0]),
                (evs[0].m_comp_max[0], evs[1].m_comp_max[0]),
            ];
            for (w, (lo, hi)) in worst.iter_mut().zip(pairs) {
                if lo > 0.0 && hi > 0.0 {
                    let e = (hi.ln() - lo.ln()) / ((1.0 + step).ln() - (1.0 - step).ln());
                    *w = py_max(*w, e.abs());
                }
            }
        }
        let mut wm = Map::new();
        wm.insert("mdot_min".into(), fnum(worst[0]));
        wm.insert("P_el_max".into(), fnum(worst[1]));
        wm.insert("m_comp_max".into(), fnum(worst[2]));
        let mut m = Map::new();
        m.insert("code_default".into(), fnum(c0));
        m.insert("max_abs_elasticity".into(), Value::Object(wm));
        m.insert("status_flip_within_step".into(), Value::Bool(flip));
        out.push((coef.to_string(), Value::Object(m)));
    }
    Ok(out)
}

/// `design_gate_snapshot(repo, rvm_snapshot=None)`: the evidence-gate statuses the robust filter must never change,
/// read from their owning design deliverables (the RVM part is supplied by the assessment layer and is not read here).
pub fn design_gate_snapshot(repo: &Path) -> DResult<Value> {
    let mp = read_pinned(repo, MP_REL)?;
    let f5 = read_pinned(repo, F5_REL)?;
    let hall = abep_mission::objective::HallResponseStatus::load(repo)?;
    let members = abep_types::pyjson::dumps(
        &abep_types::pyjson::Value::List(hall.admitted_members.clone()),
        &abep_types::pyjson::DumpOptions::canonical_hash(),
    )
    .map_err(|e| DesignError::new("RuntimeError", e.to_string()))?;
    let members: Value = serde_json::from_str(&members).map_err(|e| DesignError::new("RuntimeError", e.to_string()))?;
    let st = &mp["statuses"];
    let mut m = Map::new();
    m.insert("hall_credible_set".into(), Value::String(hall.credible_set().to_string()));
    m.insert("hall_admitted_members".into(), members);
    m.insert("a9_2_statuses".into(), st["a9_2_statuses"].clone());
    m.insert(
        "a9_19_20_supersessions".into(),
        st.get("a9_19_20_supersessions").cloned().unwrap_or_else(|| Value::Object(Map::new())),
    );
    m.insert(
        "current_statuses".into(),
        st.get("current_statuses").cloned().unwrap_or_else(|| Value::Object(Map::new())),
    );
    m.insert("h1_article_freeze_state".into(), f5["article_freeze_state"].clone());
    Ok(Value::Object(m))
}
