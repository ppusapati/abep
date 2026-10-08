//! A9.38 P6 design-closure ledger v1 of `bus_power_boundary_a9_v2` (additive; the admitted ledger, official-ledger
//! and allocation functions are called unchanged).
//!
//! The term register `docs/closure/power/power_closure_inputs_v1.json` (sha256-pinned) gives every installed slot a
//! load and an efficiency with an evidence class and bounds, so the ledger closes with no TBD term. A slot load is
//! `sum(n_i x term_i) / prod(div_j)`; a slot efficiency is the product of its converter and harness terms (LEDGERS
//! A1 / A2: both losses inside the component efficiency); the evidence class of a composite is its weakest component
//! class. Two rules are not term expressions:
//!
//! * `thermal_control` = the row-114 controls / thermal allowance minus the housekeeping bus draw (an owner-allocation
//!   residual until a flight thermal case supplies the thermal-control power), converted to its load plane;
//! * `hall_discharge` = a registered DESIGN_ALLOCATION_NOT_PREDICTED value, or (`close_design_allocation`) the
//!   discharge load that makes the ledger equal the 1,350 W design allocation.
//!
//! Raw bookkeeping only: the discharge ceiling is evaluated for a bus limit the caller passes; no RFP value is held
//! here (A9.30 sec. 5; the assessment layer applies HC-03).

use super::allocation::{icp_power_allocation_check, CONTROLS_THERMAL_ALLOWANCE_W, DESIGN_ALLOCATION_W};
use super::ledger::{ledger, Ledger, LedgerArgs, LedgerStatus};
use super::pyfmt::fsum;
use super::slots::{installed_slots, Slot, EVIDENCE_CLASSES, FLIGHT_CONFIGURATION};
use super::{PowerError, PowerResult};
use abep_provenance::{read_verified, sha256_hex};
use abep_types::pyjson::{loads, read_text_utf8, Dict, Value};
use std::path::Path;

pub const INPUTS_REL: &str = "docs/closure/power/power_closure_inputs_v1.json";
pub const INPUTS_SHA256: &str = "a588c0dbfb2a5560c5aef98e49b679a0fdbf27c1766493374ad52657e942f147";
pub const INPUTS_SCHEMA: &str = "abep_power_closure_inputs_v1";
pub const LABEL_PREFIX: &str = "A9.38_P6_CLOSURE_V1";
/// Weakest-last order of the ledger evidence classes used for composite records.
const CLASS_RANK: [&str; 7] =
    ["measured", "digitized", "reconstructed", "inferred", "model-derived", "owner-allocation", "assumed"];
/// Weakest-last order of the register closure classes.
pub const CLOSURE_RANK: [&str; 5] = [
    "SOURCED_ANALOG",
    "MODEL_DERIVED",
    "FROZEN_ENGINEERING_ASSUMPTION",
    "OWNER_ALLOCATION_RESIDUAL",
    "DESIGN_ALLOCATION_NOT_PREDICTED",
];

fn merr(m: impl Into<String>) -> PowerError {
    PowerError::new("ModelError", m)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TermKind {
    Load,
    Efficiency,
    Operating,
}

/// Which bound of every term an evaluation uses.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Corner {
    Reference,
    /// loads at their high bound, efficiencies at their low bound
    Conservative,
    /// loads at their low bound, efficiencies at their high bound
    Favourable,
}

impl Corner {
    pub fn name(self) -> &'static str {
        match self {
            Corner::Reference => "reference",
            Corner::Conservative => "conservative",
            Corner::Favourable => "favourable",
        }
    }
}

/// One registered closing value.
#[derive(Debug, Clone, PartialEq)]
pub struct Term {
    pub id: String,
    pub quantity: String,
    pub kind: TermKind,
    pub value: f64,
    pub low: f64,
    pub high: f64,
    pub units: String,
    pub evidence_class: String,
    pub evidence_level: String,
    pub closure_class: String,
    pub flags: Vec<String>,
}

impl Term {
    /// The term value at a corner (operating variables never move with the corner).
    pub fn at(&self, c: Corner) -> f64 {
        match (c, self.kind) {
            (Corner::Reference, _) | (_, TermKind::Operating) => self.value,
            (Corner::Conservative, TermKind::Load) | (Corner::Favourable, TermKind::Efficiency) => self.high,
            (Corner::Conservative, TermKind::Efficiency) | (Corner::Favourable, TermKind::Load) => self.low,
        }
    }
}

/// `sum(n_i x term_i) / prod(div_j)`; an empty numerator is exactly 0 W.
#[derive(Debug, Clone, PartialEq)]
pub struct Expr {
    pub num: Vec<(String, f64)>,
    pub div: Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum LoadSpec {
    Expr(Expr),
    ControlsThermalResidual,
}

#[derive(Debug, Clone, PartialEq)]
pub enum DischargeRule {
    Fixed(Expr),
    CloseDesignAllocation,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PointSpec {
    pub id: String,
    pub name: String,
    pub mode: String,
    pub state: String,
    pub thrust_label: String,
    pub discharge: DischargeRule,
    /// every installed slot except hall_discharge, in slot order
    pub loads: Vec<(Slot, LoadSpec)>,
}

/// The hash-verified term register.
#[derive(Debug, Clone)]
pub struct ClosureInputs {
    pub sha256: String,
    pub terms: Vec<Term>,
    /// slot -> efficiency term ids (converter terms first, harness term `ETA-H-*` included)
    pub slot_efficiencies: Vec<(Slot, Vec<String>)>,
    pub front_end: String,
    pub points: Vec<PointSpec>,
    pub rf_trade_line_w: Vec<f64>,
}

fn get<'a>(d: &'a Dict, k: &str, what: &str) -> PowerResult<&'a Value> {
    d.get(k).ok_or_else(|| merr(format!("{INPUTS_REL}: {what}: '{k}' missing")))
}

fn text(d: &Dict, k: &str, what: &str) -> PowerResult<String> {
    get(d, k, what)?.as_str().map(str::to_string).ok_or_else(|| merr(format!("{INPUTS_REL}: {what}.{k} not a text")))
}

fn num(d: &Dict, k: &str, what: &str) -> PowerResult<f64> {
    let v = get(d, k, what)?;
    if !v.is_number() {
        return Err(merr(format!("{INPUTS_REL}: {what}.{k} not a number")));
    }
    let x = v.to_f64()?;
    if !x.is_finite() {
        return Err(merr(format!("{INPUTS_REL}: {what}.{k} not finite")));
    }
    Ok(x)
}

fn dict<'a>(v: &'a Value, what: &str) -> PowerResult<&'a Dict> {
    v.as_dict().ok_or_else(|| merr(format!("{INPUTS_REL}: {what} not a record")))
}

fn list<'a>(v: &'a Value, what: &str) -> PowerResult<&'a [Value]> {
    v.as_list().ok_or_else(|| merr(format!("{INPUTS_REL}: {what} not a list")))
}

fn expr(v: &Value, what: &str) -> PowerResult<Expr> {
    let d = dict(v, what)?;
    let mut n = Vec::new();
    for p in list(get(d, "num", what)?, what)? {
        let p = list(p, what)?;
        match p {
            [Value::Str(id), c] if c.is_number() => n.push((id.clone(), c.to_f64()?)),
            _ => return Err(merr(format!("{INPUTS_REL}: {what}: numerator entries are [term, count]"))),
        }
    }
    let mut dv = Vec::new();
    for x in list(get(d, "div", what)?, what)? {
        dv.push(x.as_str().ok_or_else(|| merr(format!("{INPUTS_REL}: {what}: divisor not a term id")))?.to_string());
    }
    Ok(Expr { num: n, div: dv })
}

impl ClosureInputs {
    pub fn load(repo_root: &Path) -> PowerResult<Self> {
        let bytes = read_verified(&repo_root.join(INPUTS_REL), INPUTS_SHA256).map_err(|e| merr(e.to_string()))?;
        Self::parse(&bytes)
    }

    /// Parse and validate a register (no hash check; [`ClosureInputs::load`] is the pinned entry point).
    pub fn parse(bytes: &[u8]) -> PowerResult<Self> {
        let doc = loads(&read_text_utf8(bytes)?)?;
        let d = dict(&doc, "register")?;
        if text(d, "schema", "register")? != INPUTS_SCHEMA {
            return Err(merr(format!("{INPUTS_REL}: schema is not {INPUTS_SCHEMA}")));
        }
        if text(d, "configuration", "register")? != FLIGHT_CONFIGURATION {
            return Err(merr(format!("{INPUTS_REL}: configuration is not {FLIGHT_CONFIGURATION}")));
        }
        let mut terms: Vec<Term> = Vec::new();
        for t in list(get(d, "terms", "register")?, "terms")? {
            let t = dict(t, "term")?;
            let id = text(t, "id", "term")?;
            let kind = match text(t, "kind", &id)?.as_str() {
                "load" => TermKind::Load,
                "efficiency" => TermKind::Efficiency,
                "operating" => TermKind::Operating,
                k => return Err(merr(format!("{INPUTS_REL}: {id}: unknown kind '{k}'"))),
            };
            let (value, low, high) = (num(t, "value", &id)?, num(t, "low", &id)?, num(t, "high", &id)?);
            if kind != TermKind::Operating && !(low <= value && value <= high) {
                return Err(merr(format!("{INPUTS_REL}: {id}: value outside [low, high]")));
            }
            if kind == TermKind::Efficiency && !(0.0 < low && high <= 1.0) {
                return Err(merr(format!("{INPUTS_REL}: {id}: efficiency bounds outside (0, 1]")));
            }
            if kind != TermKind::Efficiency && low < 0.0 {
                return Err(merr(format!("{INPUTS_REL}: {id}: negative power")));
            }
            let evidence_class = text(t, "evidence_class", &id)?;
            if !EVIDENCE_CLASSES.contains(&evidence_class.as_str()) {
                return Err(merr(format!(
                    "{INPUTS_REL}: {id}: evidence class '{evidence_class}' not in the ledger set"
                )));
            }
            let closure_class = text(t, "closure_class", &id)?;
            if !CLOSURE_RANK.contains(&closure_class.as_str()) {
                return Err(merr(format!("{INPUTS_REL}: {id}: closure class '{closure_class}' unknown")));
            }
            let srcs = list(get(t, "sources", &id)?, &id)?;
            if srcs.is_empty() {
                return Err(merr(format!("{INPUTS_REL}: {id}: no source")));
            }
            if terms.iter().any(|x| x.id == id) {
                return Err(merr(format!("{INPUTS_REL}: duplicate term {id}")));
            }
            let mut flags = Vec::new();
            for f in list(get(t, "flags", &id)?, &id)? {
                flags.push(f.as_str().ok_or_else(|| merr(format!("{INPUTS_REL}: {id}: flag not a text")))?.to_string());
            }
            terms.push(Term {
                id: id.clone(),
                quantity: text(t, "quantity", &id)?,
                kind,
                value,
                low,
                high,
                units: text(t, "units", &id)?,
                evidence_class,
                evidence_level: text(t, "evidence_level", &id)?,
                closure_class,
                flags,
            });
        }
        let installed = installed_slots(&Value::str(FLIGHT_CONFIGURATION), &Value::List(vec![]))?;
        let mut slot_efficiencies = Vec::new();
        let se = dict(get(d, "slot_efficiencies", "register")?, "slot_efficiencies")?;
        for s in &installed {
            let ids = list(get(se, s.name(), "slot_efficiencies")?, s.name())?;
            let ids: Vec<String> = ids.iter().filter_map(|v| v.as_str().map(str::to_string)).collect();
            if ids.is_empty() {
                return Err(merr(format!("{INPUTS_REL}: {}: no efficiency term", s.name())));
            }
            slot_efficiencies.push((*s, ids));
        }
        if se.len() != installed.len() {
            return Err(merr(format!("{INPUTS_REL}: slot_efficiencies names a slot that is not installed")));
        }
        let mut points = Vec::new();
        for p in list(get(d, "points", "register")?, "points")? {
            let p = dict(p, "point")?;
            let id = text(p, "id", "point")?;
            let hd = dict(get(p, "hall_discharge", &id)?, &id)?;
            let discharge = match text(hd, "rule", &id)?.as_str() {
                "fixed" => DischargeRule::Fixed(expr(get(hd, "load", &id)?, &id)?),
                "close_design_allocation" => DischargeRule::CloseDesignAllocation,
                r => return Err(merr(format!("{INPUTS_REL}: {id}: unknown discharge rule '{r}'"))),
            };
            let ld = dict(get(p, "loads", &id)?, &id)?;
            let mut loads_v = Vec::new();
            for s in installed.iter().filter(|s| **s != Slot::HallDischarge) {
                let v = get(ld, s.name(), &id)?;
                let spec = match v.as_dict().and_then(|x| x.get("rule")).and_then(Value::as_str) {
                    Some("controls_thermal_residual") if *s == Slot::ThermalControl => {
                        LoadSpec::ControlsThermalResidual
                    }
                    Some(r) => return Err(merr(format!("{INPUTS_REL}: {id}: {}: unknown rule '{r}'", s.name()))),
                    None => LoadSpec::Expr(expr(v, &id)?),
                };
                loads_v.push((*s, spec));
            }
            if ld.len() != loads_v.len() {
                return Err(merr(format!("{INPUTS_REL}: {id}: a load names an unknown or not-installed slot")));
            }
            points.push(PointSpec {
                id: id.clone(),
                name: text(p, "name", &id)?,
                mode: text(p, "mode", &id)?,
                state: text(p, "state", &id)?,
                thrust_label: text(p, "thrust_label", &id)?,
                discharge,
                loads: loads_v,
            });
        }
        let mut rf = Vec::new();
        for x in list(get(d, "rf_trade_line_P_fwd_W", "register")?, "rf_trade_line")? {
            rf.push(x.to_f64()?);
        }
        let inp = ClosureInputs {
            sha256: sha256_hex(bytes),
            terms,
            slot_efficiencies,
            front_end: "ETA-FE".to_string(),
            points,
            rf_trade_line_w: rf,
        };
        inp.check_references()?;
        Ok(inp)
    }

    pub fn term(&self, id: &str) -> PowerResult<&Term> {
        self.terms.iter().find(|t| t.id == id).ok_or_else(|| merr(format!("{INPUTS_REL}: unknown term {id}")))
    }

    pub fn point(&self, id: &str) -> PowerResult<&PointSpec> {
        self.points.iter().find(|p| p.id == id).ok_or_else(|| merr(format!("{INPUTS_REL}: unknown point {id}")))
    }

    fn check_references(&self) -> PowerResult<()> {
        let want = |id: &str, kinds: &[TermKind]| -> PowerResult<()> {
            let t = self.term(id)?;
            if kinds.contains(&t.kind) {
                Ok(())
            } else {
                Err(merr(format!("{INPUTS_REL}: term {id} used with the wrong kind")))
            }
        };
        want(&self.front_end, &[TermKind::Efficiency])?;
        for (_, ids) in &self.slot_efficiencies {
            for id in ids {
                want(id, &[TermKind::Efficiency])?;
            }
        }
        for p in &self.points {
            let mut exprs: Vec<&Expr> = p
                .loads
                .iter()
                .filter_map(|(_, l)| match l {
                    LoadSpec::Expr(e) => Some(e),
                    LoadSpec::ControlsThermalResidual => None,
                })
                .collect();
            if let DischargeRule::Fixed(e) = &p.discharge {
                exprs.push(e);
            }
            for e in exprs {
                for (id, n) in &e.num {
                    want(id, &[TermKind::Load, TermKind::Operating])?;
                    if !(*n >= 0.0 && n.is_finite()) {
                        return Err(merr(format!("{INPUTS_REL}: {}: negative count", p.id)));
                    }
                }
                for id in &e.div {
                    want(id, &[TermKind::Efficiency])?;
                }
            }
        }
        Ok(())
    }

    fn weakest_class<'a>(&'a self, ids: impl Iterator<Item = &'a str>) -> PowerResult<String> {
        let mut worst = 0usize;
        for id in ids {
            let c = &self.term(id)?.evidence_class;
            let r = CLASS_RANK.iter().position(|x| x == c).ok_or_else(|| merr(format!("class {c}")))?;
            worst = worst.max(r);
        }
        Ok(CLASS_RANK[worst].to_string())
    }

    /// Weakest closure class over term ids.
    pub fn weakest_closure<'a>(&'a self, ids: impl Iterator<Item = &'a str>) -> PowerResult<String> {
        let mut worst = 0usize;
        for id in ids {
            let c = &self.term(id)?.closure_class;
            worst = worst.max(CLOSURE_RANK.iter().position(|x| x == c).unwrap_or(CLOSURE_RANK.len() - 1));
        }
        Ok(CLOSURE_RANK[worst].to_string())
    }

    fn slot_eff_ids(&self, s: Slot) -> PowerResult<&[String]> {
        self.slot_efficiencies
            .iter()
            .find(|(x, _)| *x == s)
            .map(|(_, v)| v.as_slice())
            .ok_or_else(|| merr(format!("no efficiency for {}", s.name())))
    }

    /// (converter efficiency, harness efficiency) of a slot at a corner.
    pub fn slot_eta(&self, s: Slot, c: Corner) -> PowerResult<(f64, f64)> {
        let (mut conv, mut harness) = (1.0, 1.0);
        for id in self.slot_eff_ids(s)? {
            let v = self.term(id)?.at(c);
            if id.starts_with("ETA-H-") {
                harness *= v;
            } else {
                conv *= v;
            }
        }
        Ok((conv, harness))
    }

    fn eval_expr(&self, e: &Expr, c: Corner, ov: &[(&str, f64)]) -> PowerResult<f64> {
        let val = |id: &str| -> PowerResult<f64> {
            match ov.iter().find(|(k, _)| *k == id) {
                Some((_, v)) => Ok(*v),
                None => Ok(self.term(id)?.at(c)),
            }
        };
        let mut terms = Vec::new();
        for (id, n) in &e.num {
            terms.push(n * val(id)?);
        }
        let mut x = fsum(terms)?;
        for id in &e.div {
            x /= val(id)?;
        }
        Ok(x)
    }

    /// Term ids an expression reads.
    pub fn expr_ids(e: &Expr) -> Vec<&str> {
        e.num.iter().map(|(i, _)| i.as_str()).chain(e.div.iter().map(String::as_str)).collect()
    }
}

/// Losses inside P_bus, split by where they arise (W).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Losses {
    pub conversion: f64,
    pub harness: f64,
    pub front_end: f64,
}

/// One evaluated point.
#[derive(Debug, Clone)]
pub struct PointResult {
    pub point_id: String,
    pub corner: Corner,
    pub ledger: Ledger,
    pub p_d_w: f64,
    /// ledger P_bus with the discharge at 0 W (every other slot as evaluated)
    pub p_bus_non_discharge_w: f64,
    /// eta_slot(hall_discharge) x eta_front_end: P_bus(discharge) = P_d / this
    pub discharge_chain_eta: f64,
    pub losses: Losses,
    /// RF generator DC-input minus forward RF power (inside the icp_rf_source load)
    pub rf_generator_loss_w: f64,
    pub thermal_residual_bus_w: f64,
    pub flags: Vec<String>,
}

impl PointResult {
    /// The largest discharge load-plane power for which the ledger stays at `bus_limit_w` (may be negative when the
    /// other loads alone exceed it).
    pub fn discharge_ceiling(&self, bus_limit_w: f64) -> f64 {
        (bus_limit_w - self.p_bus_non_discharge_w) * self.discharge_chain_eta
    }

    pub fn p_bus_w(&self) -> f64 {
        self.ledger.p_bus_w.expect("closure ledgers are COMPLETE")
    }
}

fn record(p: f64, class: String, source: String) -> Value {
    let mut d = Dict::new();
    d.insert("P_W", Value::Float(p));
    d.insert("evidence_class", Value::str(class));
    d.insert("source", Value::str(source));
    Value::Dict(d)
}

fn describe(e: &Expr) -> String {
    let n: Vec<String> = e.num.iter().map(|(i, k)| if *k == 1.0 { i.clone() } else { format!("{k} x {i}") }).collect();
    let mut s = if n.is_empty() { "0 W (off)".to_string() } else { n.join(" + ") };
    for d in &e.div {
        s = format!("({s}) / {d}");
    }
    s
}

/// Evaluate one point of the register at a corner with optional operating-term overrides (term id, value).
pub fn evaluate_point(inp: &ClosureInputs, point_id: &str, c: Corner, ov: &[(&str, f64)]) -> PowerResult<PointResult> {
    let p = inp.point(point_id)?;
    let fe = inp.term(&inp.front_end)?.at(c);
    let src = |what: String| format!("{INPUTS_REL} ({}) {point_id} [{}]: {what}", &inp.sha256[..12], c.name());
    let mut flags = Vec::new();
    // Every slot but the discharge and thermal control.
    let mut loads: Vec<(Slot, f64, String, String)> = Vec::new();
    for (s, spec) in &p.loads {
        if let LoadSpec::Expr(e) = spec {
            let v = inp.eval_expr(e, c, ov)?;
            let ids = ClosureInputs::expr_ids(e);
            let class = if ids.is_empty() { "assumed".to_string() } else { inp.weakest_class(ids.into_iter())? };
            loads.push((*s, v, class, src(describe(e))));
        }
    }
    let hk = loads
        .iter()
        .find(|(s, ..)| *s == Slot::HousekeepingControls)
        .map(|x| x.1)
        .ok_or_else(|| merr(format!("{point_id}: housekeeping load missing")))?;
    let (hk_c, hk_h) = inp.slot_eta(Slot::HousekeepingControls, c)?;
    // Same association as the ledger (P / eta_slot / eta_front_end), so the allowance check sees the same numbers.
    let hk_bus = hk / (hk_c * hk_h) / fe;
    let residual_bus = CONTROLS_THERMAL_ALLOWANCE_W - hk_bus;
    if p.loads.iter().any(|(_, l)| *l == LoadSpec::ControlsThermalResidual) {
        let (tc, th) = inp.slot_eta(Slot::ThermalControl, c)?;
        let tl = if residual_bus > 0.0 {
            // the largest load whose bus draw keeps the pair inside the allowance (rounding: a few ulps down)
            let mut tl = residual_bus * (tc * th) * fe;
            let mut n = 0;
            while hk_bus + tl / (tc * th) / fe > CONTROLS_THERMAL_ALLOWANCE_W {
                tl = tl.next_down();
                n += 1;
                if n > 64 {
                    return Err(merr(format!("{point_id}: thermal residual does not settle")));
                }
            }
            tl
        } else {
            flags.push("CONTROLS_THERMAL_ALLOWANCE_CONSUMED_BY_HOUSEKEEPING".to_string());
            0.0
        };
        loads.push((
            Slot::ThermalControl,
            tl,
            "owner-allocation".into(),
            src(format!(
                "row-114 controls / thermal allowance {CONTROLS_THERMAL_ALLOWANCE_W} W minus the housekeeping bus draw, \
                 at the thermal_control load plane (OWNER_ALLOCATION_RESIDUAL)"
            )),
        ));
    }
    let (hd_c, hd_h) = inp.slot_eta(Slot::HallDischarge, c)?;
    let chain = hd_c * hd_h * fe;
    let build = |p_d: f64, label: &str| -> PowerResult<Ledger> {
        let mut ld = Dict::new();
        let mut ef = Dict::new();
        for s in installed_slots(&Value::str(FLIGHT_CONFIGURATION), &Value::List(vec![]))? {
            let rec = if s == Slot::HallDischarge {
                record(p_d, "owner-allocation".into(), src(format!("hall discharge {label}")))
            } else {
                let (_, v, cl, so) = loads
                    .iter()
                    .find(|x| x.0 == s)
                    .ok_or_else(|| merr(format!("{point_id}: no load for {}", s.name())))?;
                record(*v, cl.clone(), so.clone())
            };
            let rec = if s == Slot::IcpRfSource {
                let mut d = rec.as_dict().cloned().unwrap_or_default();
                d.insert("plane", Value::str("generator_dc_input"));
                Value::Dict(d)
            } else {
                rec
            };
            ld.insert(s.name(), rec);
            let ids = inp.slot_eff_ids(s)?;
            let (cv, hv) = inp.slot_eta(s, c)?;
            let mut e = Dict::new();
            e.insert("value", Value::Float(cv * hv));
            e.insert("evidence_class", Value::str(inp.weakest_class(ids.iter().map(String::as_str))?));
            e.insert("source", Value::str(src(ids.join(" x "))));
            e.insert("path", Value::str("internal_bus"));
            ef.insert(s.name(), Value::Dict(e));
        }
        let fe_t = inp.term(&inp.front_end)?;
        let mut fed = Dict::new();
        fed.insert("value", Value::Float(fe));
        fed.insert("evidence_class", Value::str(fe_t.evidence_class.clone()));
        fed.insert("source", Value::str(src(fe_t.id.clone())));
        let mut a = LedgerArgs::new(Value::Dict(ld), Value::Dict(ef), Value::Dict(fed));
        a.label = Value::str(format!("{LABEL_PREFIX} {point_id} {}", c.name()));
        a.power_basis = Value::str("steady_state");
        let l = ledger(&a)?;
        if l.status != LedgerStatus::Complete || !l.tbd.is_empty() {
            return Err(merr(format!("{point_id}: closure ledger not COMPLETE")));
        }
        Ok(l)
    };
    let zero = build(0.0, "set to 0 W to isolate the other loads")?;
    let non_hd = zero.p_bus_w.expect("complete");
    let (p_d, label) = match &p.discharge {
        DischargeRule::Fixed(e) => {
            (inp.eval_expr(e, c, ov)?, format!("{} (DESIGN_ALLOCATION_NOT_PREDICTED)", describe(e)))
        }
        DischargeRule::CloseDesignAllocation => (
            (DESIGN_ALLOCATION_W - non_hd) * chain,
            format!("closes the {DESIGN_ALLOCATION_W} W design allocation (DESIGN_ALLOCATION_NOT_PREDICTED)"),
        ),
    };
    if p_d < 0.0 {
        return Err(merr(format!("{point_id}: no discharge power fits the design allocation")));
    }
    let mut p_d = p_d;
    let mut led = build(p_d, &label)?;
    if p.discharge == DischargeRule::CloseDesignAllocation {
        // rounding: step down a few ulps until the ledger is at or below the allocation
        let mut n = 0;
        let over = |l: &Ledger| -> PowerResult<bool> {
            let icp = icp_power_allocation_check(l)?;
            let v = icp.as_dict().and_then(|d| d.get("verdict")).and_then(Value::as_str).unwrap_or("");
            Ok(l.p_bus_w.expect("complete") > DESIGN_ALLOCATION_W || v != "WITHIN_AVAILABLE")
        };
        while over(&led)? {
            p_d = p_d.next_down();
            led = build(p_d, &label)?;
            n += 1;
            if n > 64 {
                return Err(merr(format!("{point_id}: design-allocation discharge does not settle")));
            }
        }
    }
    // Loss decomposition (LEDGERS A1 / A2): every watt once.
    let mut conv = Vec::new();
    let mut harn = Vec::new();
    let mut fel = Vec::new();
    for it in led.items.iter().filter(|i| i.installed()) {
        let pw = it.p_w.expect("known");
        if pw == 0.0 {
            continue;
        }
        let (cv, hv) = inp.slot_eta(it.slot, c)?;
        conv.push(pw / cv - pw);
        harn.push(pw / cv / hv - pw / cv);
        fel.push(it.p_bus_w.expect("known") * (1.0 - fe));
    }
    let losses = Losses { conversion: fsum(conv)?, harness: fsum(harn)?, front_end: fsum(fel)? };
    let loads_sum = fsum(led.items.iter().filter_map(|i| i.p_w))?;
    let total = led.p_bus_w.expect("complete");
    let resid = loads_sum + losses.conversion + losses.harness + losses.front_end - total;
    if resid.abs() > 1e-9 * total.max(1.0) {
        return Err(merr(format!("{point_id}: loss decomposition does not close ({resid} W)")));
    }
    let rf_load = led.item(Slot::IcpRfSource).p_w.expect("known");
    let gen = p
        .loads
        .iter()
        .find_map(|(s, l)| match (s, l) {
            (Slot::IcpRfSource, LoadSpec::Expr(e)) => Some(e),
            _ => None,
        })
        .ok_or_else(|| merr(format!("{point_id}: icp_rf_source is not a term expression")))?;
    let fwd = inp.eval_expr(&Expr { num: gen.num.clone(), div: vec![] }, c, ov)?;
    Ok(PointResult {
        point_id: point_id.to_string(),
        corner: c,
        ledger: led,
        p_d_w: p_d,
        p_bus_non_discharge_w: non_hd,
        discharge_chain_eta: chain,
        losses,
        rf_generator_loss_w: rf_load - fwd,
        thermal_residual_bus_w: residual_bus,
        flags,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn repo() -> std::path::PathBuf {
        abep_provenance::workspace_repo_root().unwrap()
    }

    #[test]
    fn every_point_closes_without_tbd() {
        let inp = ClosureInputs::load(&repo()).unwrap();
        for p in &inp.points {
            for c in [Corner::Reference, Corner::Conservative, Corner::Favourable] {
                let r = evaluate_point(&inp, &p.id, c, &[]).unwrap();
                assert_eq!(r.ledger.status, LedgerStatus::Complete);
                assert!(r.ledger.tbd.is_empty());
                // the ceiling at the point's own P_bus is the point's own discharge power
                let back = r.discharge_ceiling(r.p_bus_w());
                assert!((back - r.p_d_w).abs() <= 1e-9 * r.p_d_w.max(1.0), "{} {back} {}", p.id, r.p_d_w);
            }
        }
    }

    #[test]
    fn nominal_point_fills_the_design_allocation() {
        let inp = ClosureInputs::load(&repo()).unwrap();
        let r = evaluate_point(&inp, "P-NOM", Corner::Reference, &[]).unwrap();
        assert!(r.p_bus_w() <= DESIGN_ALLOCATION_W && DESIGN_ALLOCATION_W - r.p_bus_w() < 1e-9);
    }

    #[test]
    fn tampered_register_is_refused() {
        let root = repo();
        let bytes = std::fs::read(root.join(INPUTS_REL)).unwrap();
        let text = String::from_utf8(bytes).unwrap();
        for (from, to, why) in [
            ("\"evidence_class\": \"digitized\"", "\"evidence_class\": \"datasheet\"", "evidence class"),
            ("\"id\": \"ETA-HK\"", "\"id\": \"ETA-HKX\"", "unknown term ETA-HK"),
            ("\"closure_class\": \"MODEL_DERIVED\"", "\"closure_class\": \"TBD\"", "closure class"),
        ] {
            let bad = text.replacen(from, to, 1);
            assert_ne!(bad, text);
            let e = ClosureInputs::parse(bad.as_bytes()).unwrap_err();
            assert!(e.message.contains(why), "{why}: {}", e.message);
        }
    }
}
