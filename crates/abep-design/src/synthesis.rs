//! Design part of the F7 programme runners (`abep_sim/programme/design_synthesis.py`): the upstream Pareto set per set
//! pressure of one evaluated context (`context_pareto` without its assessment column) and the fail-closed refusal
//! stages of the full-system ranking (`rank_full_system` before any hard-constraint assessment).
//!
//! Layer rule (A9.22, cargo_workspace_proposal): design never depends on the assessment crate. The HC-12 ripple
//! feed-quality status of each member (`ripple_feed_quality`), the RFP power-gate verdict, the hard-constraint
//! evaluation / partition and the HC-10 propellant-path check are assessment functions (SC-WP-11); the raw
//! `ripple_transfer_shaft` value they consume is carried on every member.

use crate::err::{DResult, DesignError};
use crate::optimizer::{
    context_id, design_id, obj_sense, pareto_mask, Context, REPORTED_CONSTRAINT_COLUMNS, SYSTEM_NOT_EVALUATED_CODES,
};
use abep_gaspath::plenum_feed::{reasons_from_bits, status_from_reasons};
use abep_gaspath::rec::fnum;
use abep_gaspath::upstream as u13;
use serde_json::{Map, Value};

/// Member columns copied after the objectives (reference order).
pub const MEMBER_EXTRA_COLUMNS: [&str; 9] = [
    "mdot_captured_min_kgps",
    "drag_intake_max_se_N",
    "mdot_delivered_design_kgps",
    "xO_flow_min",
    "xO_flow_max",
    "deadhead_margin_min",
    "kn_upper_min",
    "T_comp_max_K",
    "a_eq_design_m2",
];

/// One context's Pareto block of one set pressure.
#[derive(Debug, Clone)]
pub struct ParetoBlock {
    pub p_set_pa: f64,
    pub context_id: String,
    pub n_evaluated: usize,
    pub n_feasible: usize,
    /// (status, count) in first-seen order
    pub status_counts: Vec<(String, usize)>,
    /// (reason, count) in first-seen order
    pub reason_counts: Vec<(String, usize)>,
    /// member rows (reference keys, ripple_feed_quality omitted), sorted by design_id
    pub members: Vec<Map<String, Value>>,
}

impl ParetoBlock {
    pub fn to_value(&self) -> Value {
        let counts =
            |v: &Vec<(String, usize)>| Value::Object(v.iter().map(|(k, n)| (k.clone(), Value::from(*n))).collect());
        let mut m = Map::new();
        m.insert("context_id".into(), Value::String(self.context_id.clone()));
        m.insert("n_evaluated".into(), Value::from(self.n_evaluated));
        m.insert("n_feasible".into(), Value::from(self.n_feasible));
        m.insert("status_counts".into(), counts(&self.status_counts));
        m.insert("reason_counts".into(), counts(&self.reason_counts));
        m.insert("n_pareto".into(), Value::from(self.members.len()));
        m.insert("members".into(), Value::Array(self.members.iter().cloned().map(Value::Object).collect()));
        Value::Object(m)
    }
}

fn bump(v: &mut Vec<(String, usize)>, k: &str) {
    match v.iter_mut().find(|(x, _)| x == k) {
        Some(e) => e.1 += 1,
        None => v.push((k.to_string(), 1)),
    }
}

/// `context_pareto(ctx, objectives)` (design part): per set pressure, the weak-dominance Pareto set of the feasible
/// vectors, the status / reason counts over every vector, and the member rows carrying the NOT_EVALUATED system
/// objectives.
pub fn context_pareto(ctx: &Context, objectives: &[&str]) -> DResult<Vec<ParetoBlock>> {
    let senses: Vec<&str> = objectives
        .iter()
        .map(|k| obj_sense(k).ok_or_else(|| DesignError::new("KeyError", format!("'{k}'"))))
        .collect::<DResult<_>>()?;
    let [nc, nk, nv, _] = ctx.shape();
    let col = |k: &str| ctx.array(k).ok_or_else(|| DesignError::new("KeyError", format!("'{k}'")));
    let mut out = vec![];
    for (ti, &p) in ctx.targets.iter().enumerate() {
        let mut idx = vec![];
        let mut status_counts = vec![];
        let mut reason_counts = vec![];
        for ci in 0..nc {
            for ki in 0..nk {
                for vi in 0..nv {
                    let g = ctx.index(ci, ki, vi, ti);
                    let rs = reasons_from_bits(ctx.bits[g]);
                    bump(&mut status_counts, status_from_reasons(&rs));
                    for r in rs {
                        bump(&mut reason_counts, r);
                    }
                    if ctx.feasible(g) {
                        idx.push((ci, ki, vi, g));
                    }
                }
            }
        }
        let mut f = Vec::with_capacity(idx.len());
        for &(_, _, _, g) in &idx {
            let mut row = vec![];
            for k in objectives {
                row.push(col(k)?[g]);
            }
            f.push(row);
        }
        let mask = if idx.is_empty() { vec![] } else { pareto_mask(&f, &senses)? };
        let mut members = vec![];
        for (&(ci, ki, vi, g), m) in idx.iter().zip(mask) {
            if !m {
                continue;
            }
            let mut row = Map::new();
            row.insert(
                "design_id".into(),
                Value::String(design_id(&ctx.candidates[ci], &ctx.filter, &ctx.compressors[ki], ctx.volumes[vi], p)),
            );
            row.insert("candidate".into(), Value::String(ctx.candidates[ci].clone()));
            row.insert("compressor".into(), Value::String(ctx.compressors[ki].clone()));
            row.insert("V_m3".into(), fnum(ctx.volumes[vi]));
            row.insert("P_set_Pa".into(), fnum(p));
            for k in objectives {
                row.insert((*k).into(), fnum(col(k)?[g]));
            }
            for k in MEMBER_EXTRA_COLUMNS {
                row.insert(k.into(), fnum(col(k)?[g]));
            }
            for k in REPORTED_CONSTRAINT_COLUMNS {
                row.insert(k.into(), fnum(col(k)?[g]));
            }
            let md = col("mdot_delivered_min_kgps")?[g];
            let cov = u13::characterization_coverage(u13::Num::F(md));
            row.insert("characterization_coverage".into(), cov["position"].clone());
            row.insert("context_role".into(), Value::String(ctx.context_role.to_string()));
            row.insert(
                "system_not_evaluated".into(),
                Value::Array(SYSTEM_NOT_EVALUATED_CODES.iter().map(|s| Value::String(s.to_string())).collect()),
            );
            members.push(row);
        }
        members.sort_by(|a, b| a["design_id"].as_str().cmp(&b["design_id"].as_str()));
        out.push(ParetoBlock {
            p_set_pa: p,
            context_id: context_id(&ctx.scenario, &ctx.filter, &ctx.wall, p),
            n_evaluated: nc * nk * nv,
            n_feasible: idx.len(),
            status_counts,
            reason_counts,
            members,
        });
    }
    Ok(out)
}

// ------------------------------------------------------------------------------------------- full-system ranking
pub const RANK_REFUSED_INCOMPLETE: &str = "REFUSED_INCOMPLETE";
pub const RANK_REFUSED_NO_FEASIBLE: &str = "REFUSED_NO_FEASIBLE_CANDIDATE";
pub const RANK_REFUSED_MIXED: &str = "REFUSED_MIXED_SYNTHETIC_AND_EVIDENCE";
pub const RANK_REFUSED_PARAMETRIC_UPSTREAM: &str = "REFUSED_PARAMETRIC_UPSTREAM_OBJECTIVE";
pub const SYSTEM_OBJECTIVES: [(&str, &str); 5] = [
    ("T_minus_D_spacecraft_N", "max"),
    ("P_bus_W", "min"),
    ("m_wet_kg", "min"),
    ("Q_reject_W", "min"),
    ("I_e_cap_minus_I_d_max_A", "max"),
];
const EVALUATED: &str = "EVALUATED";
const SYNTHETIC_ONLY: &str = "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE";

/// Outcome of the design-layer stages of `rank_full_system`.
#[derive(Debug, Clone, PartialEq)]
pub enum RankPrecheck {
    /// a refusal record (the reference return value)
    Refused(Value),
    /// every system objective and every ranked upstream objective is EVALUATED / synthetic; the hard-constraint
    /// assessment (SC-WP-11) continues with these value kinds
    ProceedToAssessment { kinds: Vec<String> },
}

fn upstream_value(ev: &Value, key: &str) -> (Option<f64>, Option<String>) {
    let v = ev.get("upstream").and_then(|u| u.get(key));
    match v {
        Some(Value::Object(o)) => {
            (o.get("value").and_then(Value::as_f64), o.get("status").and_then(Value::as_str).map(str::to_string))
        }
        Some(x) => {
            (x.as_f64(), ev.get("upstream_status").and_then(|s| s.get(key)).and_then(Value::as_str).map(str::to_string))
        }
        None => (None, ev.get("upstream_status").and_then(|s| s.get(key)).and_then(Value::as_str).map(str::to_string)),
    }
}

/// `rank_full_system` stages before the hard-constraint assessment: REFUSED_NO_FEASIBLE (no candidate),
/// REFUSED_INCOMPLETE (any system objective, including the life / material gate, not EVALUATED / synthetic; no subset
/// ranking) and REFUSED_PARAMETRIC_UPSTREAM (a ranked upstream objective not EVALUATED / synthetic). `unlock` is the
/// UNLOCK map of the reference (carried verbatim into the refusal).
pub fn rank_precheck(evaluations: &[Value], upstream_objectives: &[&str], unlock: &Value) -> RankPrecheck {
    if evaluations.is_empty() {
        let mut m = Map::new();
        m.insert("status".into(), Value::String(RANK_REFUSED_NO_FEASIBLE.into()));
        m.insert("reason".into(), Value::String("no candidate supplied".into()));
        m.insert("layers".into(), Value::Object(Map::new()));
        return RankPrecheck::Refused(Value::Object(m));
    }
    let mut missing: Vec<(String, usize)> = vec![];
    let mut kinds: Vec<String> = vec![];
    let names: Vec<&str> = SYSTEM_OBJECTIVES.iter().map(|o| o.0).chain(["life_material"]).collect();
    for ev in evaluations {
        for name in &names {
            let o = &ev["objectives"][*name];
            let st = o.get("status").and_then(Value::as_str).unwrap_or("");
            let ok_value = *name == "life_material" || !o.get("value").map(Value::is_null).unwrap_or(true);
            if (st != EVALUATED && st != SYNTHETIC_ONLY) || !ok_value {
                bump(&mut missing, name);
            } else if !kinds.iter().any(|k| k == st) {
                kinds.push(st.to_string());
            }
        }
    }
    if !missing.is_empty() {
        let mut m = Map::new();
        m.insert("status".into(), Value::String(RANK_REFUSED_INCOMPLETE.into()));
        m.insert(
            "reason".into(),
            Value::String(
                "system objectives (incl. the life / material indicator gate) not EVALUATED for some or all \
                 candidates (fail closed, no subset ranking)"
                    .into(),
            ),
        );
        m.insert(
            "missing_counts".into(),
            Value::Object(missing.into_iter().map(|(k, n)| (k, Value::from(n))).collect()),
        );
        m.insert("n_candidates".into(), Value::from(evaluations.len()));
        m.insert("unlock".into(), unlock.clone());
        m.insert("layers".into(), Value::Object(Map::new()));
        return RankPrecheck::Refused(Value::Object(m));
    }
    let mut bad: Vec<(String, Vec<String>)> = vec![];
    for ev in evaluations {
        for k in upstream_objectives {
            let (v, st) = upstream_value(ev, k);
            let st_s = st.clone().unwrap_or_else(|| "None".to_string());
            let good = matches!(st.as_deref(), Some(EVALUATED) | Some(SYNTHETIC_ONLY))
                && v.map(f64::is_finite).unwrap_or(false);
            if !good {
                match bad.iter_mut().find(|(x, _)| x == k) {
                    Some(e) => {
                        if !e.1.contains(&st_s) {
                            e.1.push(st_s);
                        }
                    }
                    None => bad.push((k.to_string(), vec![st_s])),
                }
            } else if let Some(s) = st {
                if !kinds.contains(&s) {
                    kinds.push(s);
                }
            }
        }
    }
    if !bad.is_empty() {
        let mut m = Map::new();
        m.insert("status".into(), Value::String(RANK_REFUSED_PARAMETRIC_UPSTREAM.into()));
        m.insert(
            "reason".into(),
            Value::String(
                "a ranked upstream objective is not EVALUATED / synthetic (PARAMETRIC_SENSITIVITY or unlabelled values \
                 never enter an evidence ranking; rank them in the labelled F7 upstream Pareto sets instead)"
                    .into(),
            ),
        );
        let mut us = Map::new();
        for (k, mut v) in bad {
            v.sort();
            us.insert(k, Value::Array(v.into_iter().map(Value::String).collect()));
        }
        m.insert("upstream_statuses".into(), Value::Object(us));
        m.insert("layers".into(), Value::Object(Map::new()));
        return RankPrecheck::Refused(Value::Object(m));
    }
    kinds.sort();
    RankPrecheck::ProceedToAssessment { kinds }
}

/// The REFUSED_MIXED refusal the reference returns when synthetic and evidence kinds meet (applied by the assessment
/// stage after it adds the kinds of the values hard constraints were met on).
pub fn refused_mixed() -> Value {
    let mut m = Map::new();
    m.insert("status".into(), Value::String(RANK_REFUSED_MIXED.into()));
    m.insert(
        "reason".into(),
        Value::String(
            "synthetic test data and evidence never meet in one ranking (objectives, ranked upstream values and the \
             values hard constraints were met on)"
                .into(),
        ),
    );
    m.insert("layers".into(), Value::Object(Map::new()));
    Value::Object(m)
}
