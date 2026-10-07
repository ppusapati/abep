//! The F7 / F8 study over the frozen 196 design states (+ the design-case reference): every (wall, filter, surface
//! scenario) context, its Pareto blocks, and the F8 robust filter on the nominal context (build_f7_f8_optimizer
//! stage_f7 / stage_f8, design layer only). An EMPTY robust set is reported as a result with the statuses that
//! remove every survivor (binding-constraint decomposition, A9.31 sec. 21); nothing is retuned to make a member appear.

use crate::mc::{p_feasible_min, tpmc_monte_carlo, McKey, McRecord};
use crate::robust::{
    carried_robust_set, robust_pareto, scenario_robustness, survivors, RobustBlock, Robustness, Survivor,
    NOMINAL_FILTER, NOMINAL_WALL,
};
use crate::sens::{compressor_elasticities, design_gate_snapshot, pointing_sensitivity, ELASTICITY_STEP};
use abep_design::err::DResult;
use abep_design::inputs::UpstreamInputs;
use abep_design::optimizer::{upstream_context, Context, UPSTREAM_TARGETS_PA, VOLUMES_M3, WALL_CASES};
use abep_design::synthesis::{context_pareto, ParetoBlock};
use serde_json::{Map, Value};
use std::collections::BTreeMap;

/// A study grid: candidate / compressor subsets (None = the full F7 grid), MC size and the registered sensitivity
/// picks: fractions u in [0, 1) mapped to survivor indices floor(u * n_survivors) (sorted, duplicates dropped).
#[derive(Debug, Clone)]
pub struct StudySpec {
    pub candidates: Option<Vec<String>>,
    pub compressors: Option<Vec<String>>,
    pub n_mc: usize,
    pub sensitivity_fractions: Vec<f64>,
}

/// The registered pick rule: floor(u * n) for every fraction, sorted, duplicates dropped.
pub fn pick_indices(fractions: &[f64], n: usize) -> Vec<usize> {
    let mut v: Vec<usize> =
        fractions.iter().filter(|u| (0.0..1.0).contains(*u)).map(|u| (u * n as f64).floor() as usize).collect();
    v.sort_unstable();
    v.dedup();
    v.retain(|i| *i < n);
    v
}

pub struct F7Result {
    /// (scenario, filter, wall) in the reference stage_f7 order, with each context's Pareto blocks
    pub pareto: Vec<((String, String, String), Vec<ParetoBlock>)>,
    /// nominal-filter contexts (both walls)
    pub nominal: BTreeMap<(String, String, String), Context>,
}

/// `stage_f7`: for wall in WALL_CASES, filter in filter_cases(), scenario in the F1 envelope. `sink` receives every
/// context (e.g. to write its arrays) before it is dropped.
pub fn stage_f7(inp: &UpstreamInputs, spec: &StudySpec, sink: &mut dyn FnMut(usize, &Context)) -> DResult<F7Result> {
    let mut pareto = vec![];
    let mut nominal = BTreeMap::new();
    let mut i = 0;
    for wall in WALL_CASES {
        for filt in &inp.filter_ids {
            for sc in &inp.scenarios {
                let ctx = upstream_context(
                    inp,
                    sc,
                    filt,
                    wall,
                    &VOLUMES_M3,
                    &UPSTREAM_TARGETS_PA,
                    spec.candidates.as_deref(),
                    spec.compressors.as_deref(),
                )?;
                sink(i, &ctx);
                i += 1;
                let par = context_pareto(&ctx, &abep_design::optimizer::obj_keys())?;
                pareto.push(((sc.clone(), filt.clone(), wall.to_string()), par));
                if filt == NOMINAL_FILTER {
                    nominal.insert((sc.clone(), filt.clone(), wall.to_string()), ctx);
                }
            }
        }
    }
    Ok(F7Result { pareto, nominal })
}

pub struct F8Result {
    pub gates_before: Value,
    pub gates_after: Value,
    pub survivors: Vec<Survivor>,
    pub scenario: Vec<(String, Robustness)>,
    pub mc: BTreeMap<McKey, Vec<(String, McRecord)>>,
    pub all_scenario_feasible: Vec<String>,
    pub robust: Vec<RobustBlock>,
    pub members: Vec<Survivor>,
    pub wall: Vec<(String, Robustness)>,
    pub pointing: Vec<(String, Vec<(String, Value)>)>,
    pub elasticities: Vec<(String, Vec<(String, Value)>)>,
    pub picks: Vec<Survivor>,
    pub picks_pointing_g0: Vec<(String, Vec<(String, Value)>)>,
    pub picks_pointing_ti64: Vec<(String, Vec<(String, Value)>)>,
    pub picks_elasticities: Vec<(String, Vec<(String, Value)>)>,
}

pub fn mc_key(s: &Survivor) -> McKey {
    (s.candidate.clone(), s.filter.clone(), s.compressor.clone(), s.p_set_pa.to_bits())
}

/// `stage_f8` on the F7 result (plus the registered sensitivity picks).
pub fn stage_f8(repo: &std::path::Path, inp: &UpstreamInputs, f7: &F7Result, spec: &StudySpec) -> DResult<F8Result> {
    let gates_before = design_gate_snapshot(repo)?;
    let surv = survivors(&f7.pareto, NOMINAL_FILTER, NOMINAL_WALL);
    let scen = scenario_robustness(&surv, &f7.nominal, &inp.scenarios, NOMINAL_WALL, None, None)?;
    let mc = tpmc_monte_carlo(inp, &surv, &inp.scenarios, spec.n_mc, NOMINAL_WALL)?;
    let allsc: Vec<Survivor> = surv
        .iter()
        .filter(|s| scen.iter().any(|(d, r)| *d == s.design_id && r.worst_case_all_scenarios.is_some()))
        .cloned()
        .collect();
    let robust = robust_pareto(&allsc, &scen, |c| mc.get(&mc_key(c)).and_then(|m| p_feasible_min(m)))?;
    let ids: Vec<String> = robust.iter().flat_map(|b| b.members.iter().map(|m| m.design_id.clone())).collect();
    let members: Vec<Survivor> = surv.iter().filter(|s| ids.contains(&s.design_id)).cloned().collect();
    let wall = scenario_robustness(&members, &f7.nominal, &inp.scenarios, "WALL-TI64-DB", None, None)?;
    let pointing = pointing_sensitivity(inp, &members, &inp.scenarios, NOMINAL_WALL)?;
    let mut elasticities = vec![];
    for m in &members {
        elasticities.push((
            m.design_id.clone(),
            compressor_elasticities(inp, m, &inp.scenarios, NOMINAL_WALL, ELASTICITY_STEP)?,
        ));
    }
    let picks: Vec<Survivor> =
        pick_indices(&spec.sensitivity_fractions, surv.len()).iter().filter_map(|i| surv.get(*i).cloned()).collect();
    let picks_pointing_g0 = pointing_sensitivity(inp, &picks, &inp.scenarios, NOMINAL_WALL)?;
    let picks_pointing_ti64 = pointing_sensitivity(inp, &picks, &inp.scenarios, "WALL-TI64-DB")?;
    let mut picks_elasticities = vec![];
    for m in &picks {
        picks_elasticities.push((
            m.design_id.clone(),
            compressor_elasticities(inp, m, &inp.scenarios, NOMINAL_WALL, ELASTICITY_STEP)?,
        ));
    }
    let gates_after = design_gate_snapshot(repo)?;
    Ok(F8Result {
        gates_before,
        gates_after,
        all_scenario_feasible: allsc.iter().map(|s| s.design_id.clone()).collect(),
        survivors: surv,
        scenario: scen,
        mc,
        robust,
        members,
        wall,
        pointing,
        elasticities,
        picks,
        picks_pointing_g0,
        picks_pointing_ti64,
        picks_elasticities,
    })
}

fn rob_list(v: &[(String, Robustness)]) -> Value {
    Value::Object(v.iter().map(|(d, r)| (d.clone(), r.to_value())).collect())
}

fn per_list(v: &[(String, Vec<(String, Value)>)]) -> Value {
    Value::Object(
        v.iter()
            .map(|(d, per)| (d.clone(), Value::Object(per.iter().map(|(k, x)| (k.clone(), x.clone())).collect())))
            .collect(),
    )
}

/// JSON view of the F8 result (reference shapes; MC keys rendered "candidate|filter|compressor|P").
pub fn f8_value(r: &F8Result) -> Value {
    let mut mc = Map::new();
    for ((c, f, k, p), recs) in &r.mc {
        let key = format!("{c}|{f}|{k}|{}", abep_types::pyjson::float_repr(f64::from_bits(*p)));
        mc.insert(key, Value::Object(recs.iter().map(|(sc, x)| (sc.clone(), x.to_value())).collect()));
    }
    let robust: Vec<Value> = r
        .robust
        .iter()
        .map(|b| {
            let ro = crate::robust::robust_objectives();
            let mut m = Map::new();
            m.insert("P_set_Pa".into(), Value::from(b.p_set_pa));
            m.insert("n_all_scenario_feasible".into(), Value::from(b.n_all_scenario_feasible));
            m.insert(
                "members".into(),
                Value::Array(
                    b.members
                        .iter()
                        .map(|mm| {
                            let mut o = Map::new();
                            o.insert("design_id".into(), Value::String(mm.design_id.clone()));
                            for ((k, _), v) in ro.iter().zip(&mm.row) {
                                o.insert((*k).into(), abep_gaspath::rec::fnum(*v));
                            }
                            Value::Object(o)
                        })
                        .collect(),
                ),
            );
            Value::Object(m)
        })
        .collect();
    let mut m = Map::new();
    m.insert("gates_before".into(), r.gates_before.clone());
    m.insert("gates_after".into(), r.gates_after.clone());
    m.insert("survivors".into(), Value::Array(r.survivors.iter().map(Survivor::to_value).collect()));
    m.insert("scenario".into(), rob_list(&r.scenario));
    m.insert("mc".into(), Value::Object(mc));
    m.insert(
        "all_scenario_feasible".into(),
        Value::Array(r.all_scenario_feasible.iter().cloned().map(Value::String).collect()),
    );
    m.insert("robust_pareto".into(), Value::Array(robust));
    m.insert("members".into(), Value::Array(r.members.iter().map(Survivor::to_value).collect()));
    m.insert("wall".into(), rob_list(&r.wall));
    m.insert("pointing".into(), per_list(&r.pointing));
    m.insert("elasticities".into(), per_list(&r.elasticities));
    m.insert("picks".into(), Value::Array(r.picks.iter().map(Survivor::to_value).collect()));
    m.insert("picks_pointing_g0".into(), per_list(&r.picks_pointing_g0));
    m.insert("picks_pointing_ti64".into(), per_list(&r.picks_pointing_ti64));
    m.insert("picks_elasticities".into(), per_list(&r.picks_elasticities));
    Value::Object(m)
}

/// The carried robust set record (version / provenance as given) of an F8 result.
pub fn carried_value(r: &F8Result, version: &str, provenance: &str) -> DResult<Value> {
    let s = carried_robust_set(&r.robust, version, provenance, &[])?;
    let mut m = Map::new();
    m.insert("set_id".into(), Value::String(s.set_id.clone()));
    m.insert("version".into(), Value::String(s.version.clone()));
    m.insert("members".into(), Value::Array(s.members.iter().cloned().map(Value::String).collect()));
    m.insert("objectives".into(), Value::Array(s.objectives.iter().cloned().map(Value::String).collect()));
    m.insert("label".into(), Value::String(s.label.clone()));
    m.insert("provenance".into(), Value::String(s.provenance.clone()));
    m.insert(
        "regeneration_triggers".into(),
        Value::Array(s.regeneration_triggers.iter().cloned().map(Value::String).collect()),
    );
    m.insert(
        "representative".into(),
        match s.representative() {
            Ok(v) => v,
            Err(e) => Value::String(format!("REFUSED {}: {}", e.class.name(), e.message)),
        },
    );
    Ok(Value::Object(m))
}

/// Binding-constraint decomposition of the robust filter (A9.31 sec. 21): for every survivor, the scenarios that
/// remove it and the gas-path reasons there; counted over the survivors. Raw statuses only (no PASS / FAIL); the
/// classification of the blocker is an assessment of these counts.
pub fn robust_decomposition(r: &F8Result) -> Value {
    let mut by_reason: BTreeMap<String, usize> = BTreeMap::new();
    let mut by_scenario: BTreeMap<String, usize> = BTreeMap::new();
    let mut tiers: BTreeMap<usize, usize> = BTreeMap::new();
    for (_, rob) in &r.scenario {
        *tiers.entry(rob.n_scenarios_feasible).or_default() += 1;
        for (sc, rec) in &rob.per_scenario {
            if rec.feasible {
                continue;
            }
            *by_scenario.entry(sc.clone()).or_default() += 1;
            for rs in &rec.reasons {
                *by_reason.entry(rs.clone()).or_default() += 1;
            }
        }
    }
    let robust_members: usize = r.robust.iter().map(|b| b.members.len()).sum();
    let mut m = Map::new();
    m.insert("n_survivors".into(), Value::from(r.survivors.len()));
    m.insert("n_all_scenario_feasible".into(), Value::from(r.all_scenario_feasible.len()));
    m.insert("n_robust_members".into(), Value::from(robust_members));
    m.insert("robust_set".into(), Value::String(if robust_members == 0 { "EMPTY" } else { "NON_EMPTY" }.into()));
    m.insert(
        "feasible_scenario_tiers".into(),
        Value::Object(tiers.into_iter().map(|(k, v)| (k.to_string(), Value::from(v))).collect()),
    );
    m.insert(
        "infeasible_scenario_counts".into(),
        Value::Object(by_scenario.into_iter().map(|(k, v)| (k, Value::from(v))).collect()),
    );
    m.insert(
        "infeasibility_reason_counts".into(),
        Value::Object(by_reason.into_iter().map(|(k, v)| (k, Value::from(v))).collect()),
    );
    Value::Object(m)
}
