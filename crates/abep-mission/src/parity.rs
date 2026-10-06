//! Parity tooling of abep-mission (contracts C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY, C-ABEP_SIM_STATEWISE_PY and
//! C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL): the request dispatcher of the `abep-mission-parity` CLI
//! and the registered comparison used by the CI replay of the captured Python reference outputs. Not used by the
//! production entry points.
//!
//! Transport: the strings "NaN", "+inf" and "-inf" denote floats in both directions. A result is
//! `{"id", "outcome": "RETURNED", "value"}` or `{"id", "outcome": "RAISED", "class", "message", "status"}`.

use crate::intake_drag::{load_drag_table, DragTable, EnvelopeAtmospheres};
use crate::objective::{supplied_objective, thrust_minus_drag, HallResponseStatus};
use crate::reference_drag::{build_document, case, density_free_table, reference_drag, DragArgs};
use crate::statewise::{statewise_margin, statewise_quantifier, MarginOutcome};
use crate::statewise_td::{statewise_t_minus_d, DesignPoint};
use abep_types::pyjson::{dumps, DumpOptions, Value};
use abep_types::{AbepError, AbepResult};
use std::path::PathBuf;

/// Decode the transport strings into floats (recursively).
pub fn decode(v: Value) -> Value {
    match v {
        Value::Str(s) if s == "NaN" => Value::Float(f64::NAN),
        Value::Str(s) if s == "+inf" => Value::Float(f64::INFINITY),
        Value::Str(s) if s == "-inf" => Value::Float(f64::NEG_INFINITY),
        Value::List(l) => Value::List(l.into_iter().map(decode).collect()),
        Value::Dict(d) => Value::Dict(d.iter().map(|(k, v)| (k.clone(), decode(v.clone()))).collect()),
        other => other,
    }
}

/// Encode non-finite floats as the transport strings (recursively).
pub fn encode(v: Value) -> Value {
    match v {
        Value::Float(f) if f.is_nan() => Value::str("NaN"),
        Value::Float(f) if f.is_infinite() => Value::str(if f > 0.0 { "+inf" } else { "-inf" }),
        Value::List(l) => Value::List(l.into_iter().map(encode).collect()),
        Value::Dict(d) => Value::Dict(d.iter().map(|(k, v)| (k.clone(), encode(v.clone()))).collect()),
        other => other,
    }
}

/// `r[k]`, Null when absent.
pub fn arg<'a>(r: &'a Value, k: &str) -> &'a Value {
    const NULL: Value = Value::Null;
    r.as_dict().and_then(|d| d.get(k)).unwrap_or(&NULL)
}

fn num(v: &Value) -> AbepResult<f64> {
    match v {
        Value::Float(f) => Ok(*f),
        Value::Int(i) => i.to_f64().map_err(|e| AbepError::Model { message: e.to_string() }),
        _ => Err(AbepError::Model { message: format!("request: number expected, got {v:?}") }),
    }
}

/// Resources loaded once per request batch.
pub struct ParityContext {
    pub repo: PathBuf,
    drag: Option<(DragTable, EnvelopeAtmospheres)>,
    hall_repo: Option<HallResponseStatus>,
}

impl ParityContext {
    pub fn new(repo: PathBuf) -> Self {
        ParityContext { repo, drag: None, hall_repo: None }
    }

    fn drag(&mut self) -> AbepResult<&(DragTable, EnvelopeAtmospheres)> {
        if self.drag.is_none() {
            self.drag = Some(load_drag_table(&self.repo)?);
        }
        Ok(self.drag.as_ref().expect("loaded"))
    }

    fn hall(&mut self, spec: &Value) -> AbepResult<HallResponseStatus> {
        match spec {
            Value::Str(s) if s == "repo" => {
                if self.hall_repo.is_none() {
                    self.hall_repo = Some(HallResponseStatus::load(&self.repo)?);
                }
                Ok(self.hall_repo.clone().expect("loaded"))
            }
            Value::Dict(_) => {
                let val = arg(spec, "validation");
                let val = if matches!(val, Value::Null) { None } else { Some(val) };
                HallResponseStatus::from_records(arg(spec, "ensemble"), val)
            }
            _ => Err(AbepError::Model { message: "request: hall must be 'repo' or {ensemble, validation}".into() }),
        }
    }
}

fn drag_args(r: &Value) -> DragArgs {
    DragArgs {
        rho_kg_m3: arg(r, "rho_kg_m3").clone(),
        v_rel_m_s: arg(r, "v_rel_m_s").clone(),
        intake_projected_area_m2: arg(r, "intake_projected_area_m2").clone(),
        intake_cd: arg(r, "intake_cd").clone(),
        intake_source: arg(r, "intake_source").clone(),
        atmosphere_state: arg(r, "atmosphere_state").clone(),
        intake_accounting: arg(r, "intake_accounting").clone(),
    }
}

fn dispatch(ctx: &mut ParityContext, r: &Value) -> AbepResult<Value> {
    match arg(r, "entry").as_str().unwrap_or_default() {
        "reference_drag" => Ok(reference_drag(arg(r, "case"), &drag_args(r))?.to_value()),
        "statewise_margin" => {
            let drag = match arg(r, "drag") {
                Value::Null => arg(r, "drag_result").clone(),
                d => reference_drag(arg(d, "case"), &drag_args(d))?.to_value(),
            };
            statewise_margin(arg(r, "thrust_available_N"), &drag, arg(r, "thrust_state"), arg(r, "thrust_source"))
        }
        "density_free_table" => Ok(Value::List(density_free_table()?.iter().map(|x| x.to_value()).collect())),
        "build_document" => {
            let opts = DumpOptions { indent: Some(1), ensure_ascii: false, ..Default::default() };
            let text = dumps(&build_document()?, &opts).map_err(|e| AbepError::Model { message: e.to_string() })?;
            Ok(abep_types::pydict! { "text" => text })
        }
        "case" => Ok(match arg(r, "case_id") {
            Value::Str(s) => case(s).map_or(Value::Null, |c| c.to_value()),
            _ => Value::Null,
        }),
        "statewise_quantifier" => {
            let states = arg(r, "states").as_list().unwrap_or_default().to_vec();
            let outcomes: Vec<MarginOutcome> = arg(r, "margins")
                .as_list()
                .unwrap_or_default()
                .iter()
                .map(|m| match arg(m, "raise").as_list() {
                    Some([c, msg]) => Err(format!("{}: {}", c.as_str().unwrap_or(""), msg.as_str().unwrap_or(""))),
                    _ => Ok(m.clone()),
                })
                .collect();
            let mut it = outcomes.into_iter();
            let mut f = |_: &Value| -> MarginOutcome { it.next().unwrap_or_else(|| Err("IndexError: margin".into())) };
            statewise_quantifier(&states, &mut f, arg(r, "requirement_id"))
        }
        "drag_table" => {
            let (t, _) = ctx.drag()?;
            Ok(Value::List(
                t.entries
                    .iter()
                    .map(|e| {
                        abep_types::pydict! {
                            "scenario" => e.scenario.as_str(),
                            "L_over_d" => e.l_over_d,
                            "phi" => e.phi,
                            "state_id" => e.state_id.as_str(),
                            "D_per_area_N_m2" => e.drag_per_area_n_m2,
                            "SE_per_area_N_m2" => e.drag_se_per_area_n_m2,
                        }
                    })
                    .collect(),
            ))
        }
        "hall_response_status" => Ok(ctx.hall(arg(r, "hall"))?.to_value()),
        "supplied_objective" => supplied_objective(
            arg(r, "name").as_str().unwrap_or_default(),
            arg(r, "rec"),
            arg(r, "units").as_str().unwrap_or_default(),
        ),
        "thrust_minus_drag" => {
            let hall = ctx.hall(arg(r, "hall"))?;
            thrust_minus_drag(
                arg(r, "drag_intake_N"),
                arg(r, "drag_intake_se_N"),
                arg(r, "thrust"),
                arg(r, "spacecraft_drag"),
                &hall,
                arg(r, "intake_drag"),
            )
        }
        "statewise_t_minus_d" => {
            let hall = ctx.hall(&Value::str("repo"))?;
            let (table, atm) = ctx.drag()?;
            let mut out = Vec::new();
            for p in arg(r, "points").as_list().unwrap_or_default() {
                let p = p.as_list().unwrap_or_default();
                if p.len() != 4 {
                    return Err(AbepError::Model { message: "request: point = [A, L/d, phi, scenario]".into() });
                }
                let point = DesignPoint {
                    area_m2: num(&p[0])?,
                    l_over_d: num(&p[1])?,
                    phi: num(&p[2])?,
                    scenario: p[3].as_str().unwrap_or_default().to_string(),
                };
                let rec = statewise_t_minus_d(table, &hall, &point, &atm.required_ids)?;
                out.push(abep_types::pydict! {
                    "state_ids" => rec.states.iter().map(|s| Value::str(s.state_id.as_str())).collect::<Vec<_>>(),
                    "objectives" => rec.states.iter().map(|s| s.objective.clone()).collect::<Vec<_>>(),
                });
            }
            Ok(Value::List(out))
        }
        other => Err(AbepError::Model { message: format!("request: unknown entry {other:?}") }),
    }
}

/// Evaluate one decoded request into its result record.
pub fn run_request(ctx: &mut ParityContext, r: &Value) -> Value {
    let id = arg(r, "id").clone();
    match dispatch(ctx, r) {
        Ok(v) => abep_types::pydict! { "id" => id, "outcome" => "RETURNED", "value" => encode(v) },
        Err(e) => {
            let (class, message) = match &e {
                AbepError::OutOfDomain { message } | AbepError::Model { message } => match message.split_once(": ") {
                    Some((c, m)) if !c.contains(' ') => (c.to_string(), m.to_string()),
                    _ => ("AbepError".to_string(), message.clone()),
                },
                other => ("AbepError".to_string(), other.to_string()),
            };
            abep_types::pydict! {
                "id" => id,
                "outcome" => "RAISED",
                "class" => class,
                "message" => message,
                "status" => e.status().as_str(),
            }
        }
    }
}

/// A registered ULP_BOUNDED observable: the path of keys (list indices as "*") and its tolerance.
#[derive(Debug, Clone, Copy)]
pub struct UlpRule {
    pub path: &'static [&'static str],
    pub k_ulp: f64,
    pub r_rel: Option<f64>,
}

/// ulp(x) as Python math.ulp (2^(e-52); the smallest subnormal at 0 / subnormals).
pub fn ulp(x: f64) -> f64 {
    let a = x.abs();
    if a < f64::MIN_POSITIVE {
        return f64::from_bits(1);
    }
    let e = ((a.to_bits() >> 52) & 0x7ff) as i32 - 1023;
    2f64.powi(e - 52)
}

fn float_within(r: f64, p: f64, rule: Option<&UlpRule>) -> bool {
    if r.to_bits() == p.to_bits() || (r == p && r != 0.0) {
        return true;
    }
    match rule {
        None => r == p,
        Some(u) => {
            if !r.is_finite() || !p.is_finite() {
                return false;
            }
            let d = (r - p).abs();
            d <= u.k_ulp * ulp(p) || u.r_rel.is_some_and(|rr| d <= rr * p.abs())
        }
    }
}

/// Compare a Rust value with the Python reference value: key sets and order, list lengths, types and values equal;
/// floats bit-equal (EXACT_VALUE) unless a registered ULP rule covers their path. Returns the differences.
pub fn compare(py: &Value, rs: &Value, rules: &[UlpRule]) -> Vec<String> {
    let mut out = Vec::new();
    let mut path = Vec::new();
    walk(py, rs, rules, &mut path, &mut out);
    out
}

fn walk(py: &Value, rs: &Value, rules: &[UlpRule], path: &mut Vec<String>, out: &mut Vec<String>) {
    if out.len() > 20 {
        return;
    }
    let here = || path.join("/");
    match (py, rs) {
        (Value::Dict(a), Value::Dict(b)) => {
            let ka: Vec<&String> = a.keys().collect();
            let kb: Vec<&String> = b.keys().collect();
            if ka != kb {
                out.push(format!("{}: keys {ka:?} != {kb:?}", here()));
                return;
            }
            for (k, v) in a.iter() {
                path.push(k.clone());
                walk(v, b.get(k).expect("same keys"), rules, path, out);
                path.pop();
            }
        }
        (Value::List(a), Value::List(b)) => {
            if a.len() != b.len() {
                out.push(format!("{}: list length {} != {}", here(), a.len(), b.len()));
                return;
            }
            for (x, y) in a.iter().zip(b) {
                path.push("*".into());
                walk(x, y, rules, path, out);
                path.pop();
            }
        }
        (Value::Float(p), Value::Float(r)) => {
            let rule = rules
                .iter()
                .find(|u| u.path.len() == path.len() && u.path.iter().zip(path.iter()).all(|(a, b)| a == b));
            if !float_within(*r, *p, rule) {
                out.push(format!("{}: rust {r:e} python {p:e}", here()));
            }
        }
        (a, b) => {
            if a != b {
                out.push(format!("{}: rust {b:?} python {a:?}", here()));
            }
        }
    }
}
