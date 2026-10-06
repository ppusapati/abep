//! Harness interface of the parity contracts (`abep-assess-parity eval <calls.json>`): evaluates registered calls and
//! returns Python-shaped results. Transport: non-finite floats as {"float": "NaN" | "+inf" | "-inf"}.

use crate::error::{AssessError, AssessResult};
use crate::py::{as_list, dget, dict, get, s, strs};
use crate::rvm::{self, RvmRecord};
use crate::statewise::{self, H1Map};
use crate::thresholds::Thresholds;
use crate::{gates, icp_gate, neutralization, owner_state::OwnerState, pareto, power_gate, propellant};
use abep_config::architecture::ArchitectureDefinition;
use abep_config::ConfigPaths;
use abep_gaspath::upstream::{H1Tolerance, VALUE_STATUSES, VALUE_TBD};
use abep_types::pyjson::{py_eq, py_repr, py_repr_str, py_repr_tuple, py_strip, Dict, Value};
use std::path::{Path, PathBuf};

/// Decode the transport form (wrapped non-finite floats) into values.
pub fn decode(v: &Value) -> Value {
    match v {
        Value::Dict(d) if d.len() == 1 && d.contains_key("float") => match d.get("float").and_then(Value::as_str) {
            Some("NaN") => Value::Float(f64::NAN),
            Some("+inf") => Value::Float(f64::INFINITY),
            Some("-inf") => Value::Float(f64::NEG_INFINITY),
            _ => v.clone(),
        },
        Value::Dict(d) => Value::Dict(d.iter().map(|(k, x)| (k.clone(), decode(x))).collect()),
        Value::List(l) => Value::List(l.iter().map(decode).collect()),
        other => other.clone(),
    }
}

/// Encode non-finite floats for transport.
pub fn encode(v: &Value) -> Value {
    match v {
        Value::Float(f) if f.is_nan() => dict(vec![("float", s("NaN"))]),
        Value::Float(f) if f.is_infinite() => dict(vec![("float", s(if *f > 0.0 { "+inf" } else { "-inf" }))]),
        Value::Dict(d) => Value::Dict(d.iter().map(|(k, x)| (k.clone(), encode(x))).collect()),
        Value::List(l) => Value::List(l.iter().map(encode).collect()),
        other => other.clone(),
    }
}

/// `H1Tolerance(quantity, value_frac, status, source)` with the reference refusal texts.
fn h1_tolerance(h: &Value) -> AssessResult<H1Tolerance> {
    let q = get(h, "quantity")?;
    let vf = get(h, "value_frac")?;
    let st = get(h, "status")?;
    let src = get(h, "source")?;
    let rule = |m: String| AssessError::new("A913RuleError", m);
    let qs = q.as_str().unwrap_or("");
    if !["pressure", "mass_flow", "composition", "ripple"].contains(&qs) || q.as_str().is_none() {
        return Err(rule(format!("unknown H-1 tolerance quantity {}", py_repr(q))));
    }
    let sts = st.as_str().unwrap_or("");
    if st.as_str().is_none() || !VALUE_STATUSES.contains(&sts) {
        let t = py_repr_tuple(&VALUE_STATUSES.iter().map(|x| s(*x)).collect::<Vec<_>>());
        return Err(rule(format!("status {} not in {t}", py_repr(st))));
    }
    let value = if sts == VALUE_TBD {
        if !matches!(vf, Value::Null) {
            return Err(rule("a TBD tolerance carries no value".into()));
        }
        None
    } else {
        if !(crate::py::finite(vf) && vf.to_f64()? > 0.0) {
            return Err(rule("tolerance must be finite and > 0".into()));
        }
        Some(vf.to_f64()?)
    };
    let srcs = src.as_str().unwrap_or("");
    if py_strip(srcs).is_empty() {
        return Err(rule("tolerance needs a source".into()));
    }
    Ok(H1Tolerance { quantity: qs.into(), value_frac: value, status: sts.into(), source: srcs.into() })
}

/// Last-wins table of [state_id, value] pairs.
fn by_state_id(pairs: &[Value]) -> AssessResult<Vec<(Value, Value)>> {
    let mut out: Vec<(Value, Value)> = Vec::new();
    for p in pairs {
        let l = as_list(p)?;
        let (k, v) = (l[0].clone(), l[1].clone());
        match out.iter_mut().find(|(x, _)| py_eq(x, &k)) {
            Some(slot) => slot.1 = v,
            None => out.push((k, v)),
        }
    }
    Ok(out)
}

pub struct Ctx {
    pub repo: PathBuf,
    pub thresholds: Thresholds,
    pub arch: ArchitectureDefinition,
}

impl Ctx {
    pub fn load(repo: &Path) -> AssessResult<Self> {
        let paths = ConfigPaths::repository(repo);
        Ok(Ctx {
            repo: repo.to_path_buf(),
            thresholds: Thresholds::load(&paths)?,
            arch: ArchitectureDefinition::load(&paths)?,
        })
    }
}

fn arg<'a>(a: &'a Value, k: &str) -> AssessResult<&'a Value> {
    get(a, k)
}

fn list(a: &Value, k: &str) -> AssessResult<Vec<Value>> {
    Ok(as_list(arg(a, k)?)?.to_vec())
}

fn positional(a: &Value, k: &str) -> AssessResult<Vec<Value>> {
    list(a, k)
}

fn io(e: std::io::Error) -> AssessError {
    AssessError::new("MODEL_ERROR", e.to_string())
}

/// A fresh scratch directory for one call (scratch trees of the R7 citation cases).
fn scratch_dir() -> PathBuf {
    use std::sync::atomic::{AtomicUsize, Ordering};
    static N: AtomicUsize = AtomicUsize::new(0);
    let d = std::env::temp_dir().join(format!(
        "abep-assess-rs-{}-{}",
        std::process::id(),
        N.fetch_add(1, Ordering::Relaxed)
    ));
    let _ = std::fs::remove_dir_all(&d);
    d
}

/// Evaluate one registered call.
pub fn call(ctx: &Ctx, f: &str, a: &Value) -> AssessResult<Value> {
    let t = &ctx.thresholds;
    match f {
        "hard_constraints" => {
            let mut gl = Dict::new();
            for (k, v) in &t.limits[4..] {
                gl.insert(k.as_str(), v.map_or(Value::Null, Value::Float));
            }
            Ok(dict(vec![
                ("HARD_CONSTRAINTS", Value::List(gates::hard_constraints(t).iter().map(|c| c.to_value()).collect())),
                ("HARD_CONSTRAINT_LIMITS", t.limits_value()),
                ("GATE_THRESHOLDS_LIMITS", Value::Dict(gl)),
                ("PRE_EVALUATED_OBJECTIVES", strs(&gates::PRE_EVALUATED_OBJECTIVES)),
            ]))
        }
        "evaluate_constraints" => gates::evaluate_constraints(t, arg(a, "values")?),
        "hard_constraint_partition" => gates::hard_constraint_partition(&list(a, "evaluations")?),
        "constraint_met_value_kinds" => Ok(Value::List(
            gates::constraint_met_value_kinds(&list(a, "evaluations")?)?.into_iter().map(Value::Str).collect(),
        )),
        "rfp_power_gate" => power_gate::rfp_power_gate(t, arg(a, "steady")?, arg(a, "startup")?),
        "bus_power_gate_verdict" => power_gate::bus_power_gate_verdict(t, arg(a, "supplied")?),
        "ripple_feed_quality" => {
            let h = match arg(a, "h1")? {
                Value::Null => None,
                h => Some(h1_tolerance(h)?),
            };
            statewise::ripple_feed_quality(arg(a, "ripple_frac")?, arg(a, "ripple_status")?, h.as_ref())
        }
        "statewise_envelope" => {
            let table = by_state_id(&list(a, "margins")?)?;
            let mut m = |st: &Value| -> Result<Value, String> {
                let sid = dget(st, "state_id").map_err(|e| e.to_string())?;
                table
                    .iter()
                    .find(|(k, _)| py_eq(k, &sid))
                    .map(|(_, v)| v.clone())
                    .ok_or_else(|| format!("KeyError: {}", py_repr(&sid)))
            };
            let rid = arg(a, "requirement_id")?.as_str().unwrap_or("").to_string();
            statewise::statewise_envelope(&rid, &list(a, "states")?, &mut m, arg(a, "value_status")?)
        }
        "statewise_drag_compensation" => {
            let tr = positional(a, "thrust")?;
            let dr = positional(a, "drag")?;
            let mut tf = |i: usize, _: &Value| -> AssessResult<Value> { Ok(tr[i].clone()) };
            let mut df = |i: usize, _: &Value| -> AssessResult<Value> { Ok(dr[i].clone()) };
            statewise::statewise_drag_compensation(
                t,
                &list(a, "states")?,
                &mut tf,
                &mut df,
                arg(a, "hall_admitted")?.truthy(),
            )
        }
        "feed_state_sufficiency" => {
            let off = positional(a, "offered")?;
            let mut of = |i: usize, _: &Value| -> AssessResult<Value> { Ok(off[i].clone()) };
            let req = match arg(a, "required")? {
                Value::Null => None,
                v => Some(as_list(v)?.to_vec()),
            };
            let mut rf_store;
            let rf: Option<statewise::StateFn<'_>> = match &req {
                Some(r) => {
                    rf_store = |i: usize, _: &Value| -> AssessResult<Value> { Ok(r[i].clone()) };
                    Some(&mut rf_store)
                }
                None => None,
            };
            let map = arg(a, "h1_map")?.clone();
            let table = match &map {
                Value::Null => vec![],
                m => as_list(get(m, "table")?)?.to_vec(),
            };
            let mut mf = |i: usize, _: &Value, _: f64, _: &Value| -> AssessResult<Value> { Ok(table[i].clone()) };
            let h1 = match &map {
                Value::Null => None,
                m => Some(H1Map { status: get(m, "status")?.clone(), min_feed_state: &mut mf }),
            };
            statewise::feed_state_sufficiency(
                t,
                &list(a, "states")?,
                &mut of,
                rf,
                h1,
                arg(a, "fixed_mass_flow_gate")?.truthy(),
            )
        }
        "pareto_s6_17" => pareto::pareto_s6_17(&list(a, "rows")?, !matches!(arg(a, "weights")?, Value::Null)),
        "propellant_paths_check" => propellant::propellant_paths_check(&ctx.arch, arg(a, "paths")?),
        "rvm_gate_snapshot" => RvmRecord::load(&ctx.repo)?.gate_snapshot(),
        "owner_state" => OwnerState::load(&ctx.repo)?.owner_state(arg(a, "qid")?),
        "status_label" => Ok(s(OwnerState::load(&ctx.repo)?.status_label(arg(a, "qid")?)?)),
        "apply_to_questions" => OwnerState::load(&ctx.repo)?.apply_to_questions(&list(a, "questions")?),
        "icp45a_margin" => {
            let n = |k: &str| -> AssessResult<f64> { Ok(arg(a, k)?.to_f64()?) };
            Ok(neutralization::icp45a_margin_value(n("i")?, n("idm")?, n("k")?, n("ue")?, n("ud")?))
        }
        // ---- contract 2
        "rvm_vocabularies" => Ok(rvm::vocabularies()),
        "validate_artifact" => rvm::validate_artifact(arg(a, "artifact")?),
        "assign_status" => {
            let (st, rule, reason) = rvm::assign_status(&list(a, "artifacts")?, arg(a, "requirement_frozen")?)?;
            Ok(Value::List(vec![s(st), s(rule), s(reason)]))
        }
        "is_not_applicable_cell" => Ok(Value::Bool(rvm::is_not_applicable_cell(&list(a, "artifacts")?)?)),
        "floor_fail_check" => {
            rvm::floor_fail_check(&list(a, "readings")?, arg(a, "limit")?.to_f64()?, arg(a, "strict")?.truthy())
        }
        "assert_status_vocabulary" | "assert_no_pass_without_measurement" => {
            let doc = match arg(a, "doc")? {
                Value::Str(x) if x == "COMMITTED" => RvmRecord::load(&ctx.repo)?.doc,
                d => d.clone(),
            };
            if f == "assert_status_vocabulary" {
                rvm::assert_status_vocabulary(&doc)?;
            } else {
                rvm::assert_no_pass_without_measurement(&doc)?;
            }
            Ok(Value::Null)
        }
        "rvm_replay" => {
            let r = RvmRecord::load(&ctx.repo)?;
            let mut out = Vec::new();
            for c in r.replay_cells()? {
                out.push(Value::List(
                    ["row", "configuration", "status", "rule", "reason"]
                        .iter()
                        .map(|k| get(&c, k).cloned())
                        .collect::<AssessResult<Vec<_>>>()?,
                ));
            }
            Ok(Value::List(out))
        }
        "gng_icp_01_replay" => {
            let r = RvmRecord::load(&ctx.repo)?;
            let g = r.gng_icp_01()?;
            icp_gate::evaluate(get(g, "criteria")?, get(g, "evidence")?, &ctx.repo, &r.proposal_text()?)
        }
        "icp_gate_evaluate" => {
            let r = RvmRecord::load(&ctx.repo)?;
            let proposal = r.proposal_text()?;
            let files = dget(a, "files")?;
            if matches!(files, Value::Null) {
                return icp_gate::evaluate(arg(a, "criteria")?, arg(a, "evidence")?, &ctx.repo, &proposal);
            }
            let tmp = scratch_dir();
            let res = (|| -> AssessResult<Value> {
                for (rel, text) in crate::py::as_dict(&files)?.iter() {
                    let p = tmp.join(rel);
                    std::fs::create_dir_all(p.parent().expect("parent")).map_err(io)?;
                    std::fs::write(&p, crate::py::py_str(text)).map_err(io)?;
                }
                let root_rel = match dget(a, "root_rel")? {
                    Value::Str(x) => x,
                    _ => "base".to_string(),
                };
                let root = tmp.join(root_rel);
                std::fs::create_dir_all(&root).map_err(io)?;
                icp_gate::evaluate(arg(a, "criteria")?, arg(a, "evidence")?, &root, &proposal)
            })();
            let _ = std::fs::remove_dir_all(&tmp);
            res
        }
        "lock1_release_reportable" => Ok(Value::Bool(icp_gate::lock1_release_reportable(arg(a, "gates")?)?)),
        other => Err(AssessError::new("MODEL_ERROR", format!("unknown parity entry {}", py_repr_str(other)))),
    }
}

/// Evaluate a list of calls [{"fn", "args"}] into [{"outcome", "value" | "class", "message"}].
pub fn eval_calls(ctx: &Ctx, calls: &Value) -> AssessResult<Value> {
    let mut out = Vec::new();
    for c in as_list(calls)? {
        let f = get(c, "fn")?.as_str().unwrap_or("").to_string();
        let a = decode(get(c, "args")?);
        out.push(match call(ctx, &f, &a) {
            Ok(v) => dict(vec![("outcome", s("RETURNED")), ("value", encode(&v))]),
            Err(e) => dict(vec![("outcome", s("RAISED")), ("class", s(e.class)), ("message", s(e.message))]),
        });
    }
    Ok(Value::List(out))
}
