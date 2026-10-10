//! F8 robust filter (`abep_sim/design/robust_optimizer.py` survivors / scenario_robustness / robust_pareto /
//! carried_robust_set; `upstream_a9_13.require_all_admitted_scenarios` / `robust_over_scenarios`).
//!
//! A candidate is robust-feasible only if it is nominally feasible in EVERY admitted surface scenario (fail closed:
//! one infeasible scenario removes it); the robust Pareto set compares worst-case objectives plus the minimum TPMC
//! P_feasible and is carried as a versioned set, never reduced to a representative. An EMPTY robust set is a valid
//! output; nothing here retunes an input to make a member appear (A9.31 secs. 12, 21).

use abep_design::err::{DResult, DesignError};
use abep_design::optimizer::{obj_keys, obj_sense, pareto_mask, Context, LABEL_PARAMETRIC};
use abep_design::synthesis::ParetoBlock;
use abep_gaspath::plenum_feed::reasons_from_bits;
use abep_gaspath::upstream::RobustParetoSet;
use serde_json::{Map, Value};
use std::collections::{BTreeMap, BTreeSet};

pub const NOMINAL_FILTER: &str = "F4-FIL-NONE";
pub const NOMINAL_FILTER_ROLE: &str = "REFERENCE_BOUND_FC00_NOT_ADMISSIBLE";
pub const NOMINAL_WALL: &str = "WALL-G0";
pub const VALUE_EVIDENCE: &str = "EVIDENCE";
pub const ROBUST_SET_ID: &str = "F8-ROBUST-UPSTREAM";

fn a913(msg: impl Into<String>) -> DesignError {
    DesignError::new("A913RuleError", msg)
}

fn py_list(xs: &[String]) -> String {
    let inner: Vec<String> = xs.iter().map(|s| abep_types::pyjson::py_repr_str(s)).collect();
    format!("[{}]", inner.join(", "))
}

/// `upstream_a9_13.require_all_admitted_scenarios(used, admitted, narrowing_record)` (A9.13 S6.16).
pub fn require_all_admitted_scenarios(
    used: &[String],
    admitted: &[String],
    narrowing_record: Option<&Map<String, Value>>,
) -> DResult<Value> {
    let used_s: BTreeSet<&String> = used.iter().collect();
    let adm: BTreeSet<&String> = admitted.iter().collect();
    if adm.is_empty() {
        return Err(a913("no admitted surface scenarios supplied"));
    }
    let extra: Vec<String> = used_s.difference(&adm).map(|s| s.to_string()).collect();
    if !extra.is_empty() {
        return Err(a913(format!("scenarios {} are not admitted", py_list(&extra))));
    }
    let missing: Vec<String> = adm.difference(&used_s).map(|s| s.to_string()).collect();
    let adm_sorted: Vec<Value> = adm.iter().map(|s| Value::String(s.to_string())).collect();
    if missing.is_empty() {
        let mut m = Map::new();
        m.insert("status".into(), Value::String("ALL_ADMITTED_SCENARIOS_COVERED".into()));
        m.insert("admitted".into(), Value::Array(adm_sorted));
        m.insert("narrowed".into(), Value::Bool(false));
        return Ok(Value::Object(m));
    }
    let Some(nr) = narrowing_record else {
        return Err(a913(format!(
            "robustness set omits admitted scenarios {}; a favourable surface model is never selected (A9.13 S6.16); \
             narrowing needs a pre-registered DI-1.3 record",
            py_list(&missing)
        )));
    };
    for k in ["preregistration_id", "measurement_source", "mapping", "admitted_range"] {
        let s = match nr.get(k) {
            None | Some(Value::Null) => String::new(),
            Some(Value::String(s)) => s.clone(),
            Some(v) => v.to_string(),
        };
        if s.trim().is_empty() {
            return Err(a913(format!("DI-1.3 narrowing record lacks {}", abep_types::pyjson::py_repr_str(k))));
        }
    }
    if nr.get("evidence_status").and_then(Value::as_str) != Some(VALUE_EVIDENCE) {
        return Err(a913("DI-1.3 narrowing needs measured, applicable accommodation evidence"));
    }
    let mut m = Map::new();
    m.insert("status".into(), Value::String("NARROWED_BY_PREREGISTERED_DI_1_3".into()));
    m.insert("admitted".into(), Value::Array(adm_sorted));
    m.insert("narrowed".into(), Value::Bool(true));
    m.insert("used".into(), Value::Array(used_s.iter().map(|s| Value::String(s.to_string())).collect()));
    m.insert("preserved_as_sensitivity".into(), Value::Array(missing.into_iter().map(Value::String).collect()));
    m.insert("narrowing_record".into(), Value::Object(nr.clone()));
    Ok(Value::Object(m))
}

/// `upstream_a9_13.robust_over_scenarios(per_scenario, admitted)`: feasible only in EVERY admitted scenario.
pub fn robust_over_scenarios(per_scenario: &[(String, bool)], admitted: &[String]) -> DResult<Value> {
    let used: Vec<String> = per_scenario.iter().map(|x| x.0.clone()).collect();
    require_all_admitted_scenarios(&used, admitted, None)?;
    let mut bad: Vec<String> = per_scenario.iter().filter(|x| !x.1).map(|x| x.0.clone()).collect();
    bad.sort();
    let mut m = Map::new();
    m.insert("robust_feasible".into(), Value::Bool(bad.is_empty()));
    m.insert("infeasible_in".into(), Value::Array(bad.into_iter().map(Value::String).collect()));
    m.insert("n_scenarios".into(), Value::from(per_scenario.len()));
    Ok(Value::Object(m))
}

/// One F7 survivor (an upstream vector on any Pareto set of the nominal context).
#[derive(Debug, Clone, PartialEq)]
pub struct Survivor {
    pub design_id: String,
    pub candidate: String,
    pub compressor: String,
    pub v_m3: f64,
    pub p_set_pa: f64,
    pub filter: String,
    pub pareto_in: Vec<String>,
    pub filter_context_role: String,
}

impl Survivor {
    pub fn to_value(&self) -> Value {
        let mut m = Map::new();
        m.insert("design_id".into(), Value::String(self.design_id.clone()));
        m.insert("candidate".into(), Value::String(self.candidate.clone()));
        m.insert("compressor".into(), Value::String(self.compressor.clone()));
        m.insert("V_m3".into(), Value::from(self.v_m3));
        m.insert("P_set_Pa".into(), Value::from(self.p_set_pa));
        m.insert("filter".into(), Value::String(self.filter.clone()));
        m.insert("pareto_in".into(), Value::Array(self.pareto_in.iter().cloned().map(Value::String).collect()));
        m.insert("filter_context_role".into(), Value::String(self.filter_context_role.clone()));
        Value::Object(m)
    }
}

/// `survivors(pareto_by_context, filt, wall)`: unique design vectors on any F7 Pareto set of the (filt, wall)
/// context, over every surface scenario and set pressure. `pareto_by_context` is in the reference dict order.
pub fn survivors(
    pareto_by_context: &[((String, String, String), Vec<ParetoBlock>)],
    filt: &str,
    wall: &str,
) -> Vec<Survivor> {
    let mut seen: BTreeMap<String, Survivor> = BTreeMap::new();
    for ((sc, f, w), par) in pareto_by_context {
        if f != filt || w != wall {
            continue;
        }
        for blk in par {
            for m in &blk.members {
                let id = m["design_id"].as_str().unwrap_or_default().to_string();
                let e = seen.entry(id.clone()).or_insert_with(|| Survivor {
                    design_id: id,
                    candidate: m["candidate"].as_str().unwrap_or_default().to_string(),
                    compressor: m["compressor"].as_str().unwrap_or_default().to_string(),
                    v_m3: m["V_m3"].as_f64().unwrap_or(f64::NAN),
                    p_set_pa: blk.p_set_pa,
                    filter: filt.to_string(),
                    pareto_in: vec![],
                    filter_context_role: if filt == NOMINAL_FILTER {
                        NOMINAL_FILTER_ROLE.into()
                    } else {
                        "ARCHITECTURE_CONTEXT".into()
                    },
                });
                e.pareto_in.push(sc.clone());
            }
        }
    }
    let mut out: Vec<Survivor> = seen.into_values().collect();
    for r in &mut out {
        let s: BTreeSet<String> = r.pareto_in.drain(..).collect();
        r.pareto_in = s.into_iter().collect();
    }
    out
}

/// Per-scenario record of one candidate.
#[derive(Debug, Clone, PartialEq)]
pub struct ScenarioRecord {
    pub feasible: bool,
    pub reasons: Vec<String>,
    /// objective values (OBJ_KEYS order) when feasible
    pub objectives: Option<Vec<f64>>,
}

/// `scenario_robustness` result of one candidate.
#[derive(Debug, Clone, PartialEq)]
pub struct Robustness {
    pub n_scenarios_feasible: usize,
    pub n_scenarios: usize,
    pub infeasible_in: Vec<String>,
    /// worst case over every scenario (OBJ_KEYS order), only when feasible in all
    pub worst_case_all_scenarios: Option<Vec<f64>>,
    pub per_scenario: Vec<(String, ScenarioRecord)>,
}

impl Robustness {
    pub fn to_value(&self) -> Value {
        let keys = obj_keys();
        let objmap = |v: &Vec<f64>| -> Map<String, Value> {
            keys.iter().zip(v).map(|(k, x)| (k.to_string(), abep_gaspath::rec::fnum(*x))).collect()
        };
        let mut per = Map::new();
        for (sc, r) in &self.per_scenario {
            let mut m = Map::new();
            m.insert("feasible".into(), Value::Bool(r.feasible));
            m.insert("reasons".into(), Value::Array(r.reasons.iter().cloned().map(Value::String).collect()));
            if let Some(o) = &r.objectives {
                m.extend(objmap(o));
            }
            per.insert(sc.clone(), Value::Object(m));
        }
        let mut m = Map::new();
        m.insert("n_scenarios_feasible".into(), Value::from(self.n_scenarios_feasible));
        m.insert("n_scenarios".into(), Value::from(self.n_scenarios));
        m.insert("infeasible_in".into(), Value::Array(self.infeasible_in.iter().cloned().map(Value::String).collect()));
        m.insert(
            "worst_case_all_scenarios".into(),
            self.worst_case_all_scenarios.as_ref().map(|w| Value::Object(objmap(w))).unwrap_or(Value::Null),
        );
        m.insert("per_scenario".into(), Value::Object(per));
        Value::Object(m)
    }
}

/// `scenario_robustness(cands, contexts, scenarios, wall, admitted, narrowing_record)`. `contexts` maps
/// (scenario, filter, wall) -> evaluated context; `admitted` defaults to every scenario present in `contexts`.
pub fn scenario_robustness(
    cands: &[Survivor],
    contexts: &BTreeMap<(String, String, String), Context>,
    scenarios: &[String],
    wall: &str,
    admitted: Option<&[String]>,
    narrowing_record: Option<&Map<String, Value>>,
) -> DResult<Vec<(String, Robustness)>> {
    let adm: Vec<String> = match admitted {
        Some(a) => a.to_vec(),
        None => contexts.keys().map(|k| k.0.clone()).collect::<BTreeSet<_>>().into_iter().collect(),
    };
    require_all_admitted_scenarios(scenarios, &adm, narrowing_record)?;
    let keys = obj_keys();
    let mut out = vec![];
    for c in cands {
        let mut per = vec![];
        for sc in scenarios {
            let ctx = contexts
                .get(&(sc.clone(), c.filter.clone(), wall.to_string()))
                .ok_or_else(|| DesignError::new("KeyError", format!("({sc:?}, {:?}, {wall:?})", c.filter)))?;
            let pos = |v: &[String], x: &str| {
                v.iter()
                    .position(|y| y == x)
                    .ok_or_else(|| DesignError::new("ValueError", format!("{x:?} is not in tuple")))
            };
            let ci = pos(&ctx.candidates, &c.candidate)?;
            let ki = pos(&ctx.compressors, &c.compressor)?;
            let vi = ctx
                .volumes
                .iter()
                .position(|v| *v == c.v_m3)
                .ok_or_else(|| DesignError::new("ValueError", "tuple.index(x): x not in tuple"))?;
            let ti = ctx
                .targets
                .iter()
                .position(|v| *v == c.p_set_pa)
                .ok_or_else(|| DesignError::new("ValueError", "tuple.index(x): x not in tuple"))?;
            let g = ctx.index(ci, ki, vi, ti);
            let feas = ctx.feasible(g);
            let objectives = if feas {
                let mut v = vec![];
                for k in &keys {
                    v.push(ctx.array(k).expect("objective column")[g]);
                }
                Some(v)
            } else {
                None
            };
            per.push((
                sc.clone(),
                ScenarioRecord {
                    feasible: feas,
                    reasons: reasons_from_bits(ctx.bits[g]).into_iter().map(str::to_string).collect(),
                    objectives,
                },
            ));
        }
        let feas_sc: Vec<&String> = per.iter().filter(|(_, r)| r.feasible).map(|(s, _)| s).collect();
        let worst = if feas_sc.len() == scenarios.len() {
            let mut w = vec![];
            for (j, k) in keys.iter().enumerate() {
                let max_sense = obj_sense(k) == Some("max");
                let mut acc = f64::NAN;
                for (i, (_, r)) in per.iter().enumerate() {
                    let x = r.objectives.as_ref().expect("feasible")[j];
                    // Python min / max over a generator: keep the first unless a later one compares strictly better
                    if i == 0 || (max_sense && x < acc) || (!max_sense && x > acc) {
                        acc = x;
                    }
                }
                w.push(acc);
            }
            Some(w)
        } else {
            None
        };
        let infeasible_in: Vec<String> = scenarios.iter().filter(|s| !feas_sc.contains(s)).cloned().collect();
        out.push((
            c.design_id.clone(),
            Robustness {
                n_scenarios_feasible: feas_sc.len(),
                n_scenarios: scenarios.len(),
                infeasible_in,
                worst_case_all_scenarios: worst,
                per_scenario: per,
            },
        ));
    }
    Ok(out)
}

/// `ROBUST_OBJECTIVES` = OBJ_KEYS + P_feasible_tpmc_min (max).
pub fn robust_objectives() -> Vec<(&'static str, &'static str)> {
    let mut v: Vec<(&str, &str)> = obj_keys().into_iter().map(|k| (k, obj_sense(k).expect("sense"))).collect();
    v.push(("P_feasible_tpmc_min", "max"));
    v
}

/// One robust Pareto member row.
#[derive(Debug, Clone, PartialEq)]
pub struct RobustMember {
    pub design_id: String,
    /// ROBUST_OBJECTIVES order
    pub row: Vec<f64>,
}

/// `robust_pareto` block of one set pressure.
#[derive(Debug, Clone, PartialEq)]
pub struct RobustBlock {
    pub p_set_pa: f64,
    pub n_all_scenario_feasible: usize,
    pub members: Vec<RobustMember>,
}

/// `robust_pareto(cands, scen, mc)`: per set pressure, candidates nominally feasible in EVERY surface scenario,
/// compared on worst-case objectives plus the minimum TPMC P_feasible over the scenarios. `p_feasible_min` returns
/// the minimum P_feasible of a candidate's MC record (None when no MC record exists: the candidate is skipped).
pub fn robust_pareto(
    cands: &[Survivor],
    scen: &[(String, Robustness)],
    p_feasible_min: impl Fn(&Survivor) -> Option<f64>,
) -> DResult<Vec<RobustBlock>> {
    let mut by_p: Vec<(f64, Vec<(String, Vec<f64>)>)> = vec![];
    for c in cands {
        let s = &scen
            .iter()
            .find(|(d, _)| *d == c.design_id)
            .ok_or_else(|| DesignError::new("KeyError", abep_types::pyjson::py_repr_str(&c.design_id)))?
            .1;
        let Some(w) = &s.worst_case_all_scenarios else { continue };
        let Some(pf) = p_feasible_min(c) else { continue };
        let mut row = w.clone();
        row.push(pf);
        match by_p.iter_mut().find(|(p, _)| *p == c.p_set_pa) {
            Some(e) => e.1.push((c.design_id.clone(), row)),
            None => by_p.push((c.p_set_pa, vec![(c.design_id.clone(), row)])),
        }
    }
    by_p.sort_by(|a, b| a.0.partial_cmp(&b.0).expect("finite P"));
    let ro = robust_objectives();
    let senses: Vec<&str> = ro.iter().map(|x| x.1).collect();
    let mut out = vec![];
    for (p, items) in by_p {
        let f: Vec<Vec<f64>> = items.iter().map(|(_, r)| r.clone()).collect();
        let mask = pareto_mask(&f, &senses)?;
        let mut members: Vec<RobustMember> = items
            .iter()
            .zip(mask)
            .filter(|(_, k)| *k)
            .map(|((d, r), _)| RobustMember { design_id: d.clone(), row: r.clone() })
            .collect();
        members.sort_by(|a, b| a.design_id.cmp(&b.design_id));
        out.push(RobustBlock { p_set_pa: p, n_all_scenario_feasible: items.len(), members });
    }
    Ok(out)
}

/// `robust_pareto_set(ids, version, provenance, regenerated_after)` / `carried_robust_set`: the union of the robust
/// members over the set pressures, carried as a versioned set (no representative).
pub fn carried_robust_set(
    robust: &[RobustBlock],
    version: &str,
    provenance: &str,
    regenerated_after: &[String],
) -> DResult<RobustParetoSet> {
    let ids: BTreeSet<String> = robust.iter().flat_map(|b| b.members.iter().map(|m| m.design_id.clone())).collect();
    Ok(RobustParetoSet::new(
        ROBUST_SET_ID,
        version,
        ids.into_iter().collect(),
        obj_keys().into_iter().map(str::to_string).collect(),
        LABEL_PARAMETRIC,
        provenance,
        None,
        regenerated_after.to_vec(),
    )?)
}
