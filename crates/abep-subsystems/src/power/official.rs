//! The official A9-02 steady ledger (`official_ledger` of `abep_sim/design/architecture_optimizer.py`): every
//! installed slot load and supply efficiency TBD as the mass/power v5 record states it (value-status preservation,
//! RM-R27), the reserved port at 0 W `assumed`, the front end TBD (row 111). With a compressor draw the compressor slot
//! carries that model-derived value: a labelled PARAMETRIC_SENSITIVITY ledger, never the official one (row 22).

use super::ledger::{ledger, Ledger, LedgerArgs};
use super::slots::{installed_slots, Slot, FLIGHT_CONFIGURATION, TBD};
use super::{PowerError, PowerResult};
use abep_provenance::read_verified;
use abep_types::pyjson::{loads, py_repr_str, read_text_utf8, Dict, Value};
use std::path::Path;

pub const MASS_POWER_REL: &str = "docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json";
/// sha256 of the mass/power v5 record the official ledger is built from (contract DIV-A06: other bytes are refused).
pub const MASS_POWER_SHA256: &str = "3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a";
pub const LABEL_OFFICIAL: &str = "OFFICIAL_A9_02_STATE";
pub const LABEL_PARAMETRIC: &str = "PARAMETRIC_SENSITIVITY";
const DEFAULT_COMPRESSOR_SOURCE: &str = "F3/F4 DragCompressor cascade (code-default coefficients)";
const FRONT_END_TBD: &str = "front-end converter efficiency (row 111): TBD";

/// The hash-verified mass/power v5 record.
#[derive(Debug, Clone)]
pub struct MassPowerA9V5 {
    doc: Value,
}

impl MassPowerA9V5 {
    pub fn load(repo_root: &Path) -> PowerResult<Self> {
        let bytes = read_verified(&repo_root.join(MASS_POWER_REL), MASS_POWER_SHA256)
            .map_err(|e| PowerError::new("ModelError", e.to_string()))?;
        let doc = loads(&read_text_utf8(&bytes)?)?;
        Ok(MassPowerA9V5 { doc })
    }

    /// `{s['slot']: s for s in mp['power']['configurations'][config]['slots']}`; an absent configuration is a
    /// `KeyError` as in the reference.
    fn slot_texts(&self, config: &str) -> PowerResult<Vec<(String, Dict)>> {
        let key_err = |k: &str| PowerError::new("KeyError", py_repr_str(k));
        let configs = self
            .doc
            .as_dict()
            .and_then(|d| d.get("power"))
            .and_then(Value::as_dict)
            .and_then(|d| d.get("configurations"))
            .and_then(Value::as_dict)
            .ok_or_else(|| PowerError::new("ModelError", "mass/power v5: power.configurations missing"))?;
        let cfg = configs.get(config).and_then(Value::as_dict).ok_or_else(|| key_err(config))?;
        let slots = cfg.get("slots").and_then(Value::as_list).ok_or_else(|| key_err("slots"))?;
        let mut out: Vec<(String, Dict)> = Vec::new();
        for s in slots {
            let d = s.as_dict().ok_or_else(|| PowerError::new("ModelError", "mass/power v5: slot row not a record"))?;
            let name = d.get("slot").and_then(Value::as_str).ok_or_else(|| key_err("slot"))?.to_string();
            match out.iter_mut().find(|(n, _)| *n == name) {
                Some(row) => row.1 = d.clone(),
                None => out.push((name, d.clone())),
            }
        }
        Ok(out)
    }
}

fn text(rec: &Dict, key: &str) -> PowerResult<String> {
    match rec.get(key) {
        Some(Value::Str(s)) => Ok(s.clone()),
        Some(_) => Err(PowerError::new("ModelError", format!("mass/power v5: '{key}' is not a text"))),
        None => Err(PowerError::new("KeyError", py_repr_str(key))),
    }
}

/// `_eff_path(text)`: the supply path named in the mass/power efficiency text.
fn eff_path(t: &str) -> PowerResult<&'static str> {
    let mut best: Option<(usize, &'static str)> = None;
    for p in ["internal_bus", "direct"] {
        if let Some(i) = t.find(&format!("path {p}")) {
            if best.is_none_or(|(j, _)| i < j) {
                best = Some((i, p));
            }
        }
    }
    best.map(|(_, p)| p).ok_or_else(|| {
        PowerError::new("RuntimeError", format!("no supply path in mass/power efficiency text: {}", py_repr_str(t)))
    })
}

/// `official_ledger(config, compressor_P_W, compressor_source)`.
pub fn official_ledger(
    mp: &MassPowerA9V5,
    config: &str,
    compressor_p_w: Option<f64>,
    compressor_source: &str,
) -> PowerResult<Ledger> {
    let texts = mp.slot_texts(config)?;
    let cfg = Value::str(config);
    let mut loads_d = Dict::new();
    let mut effs = Dict::new();
    for s in installed_slots(&cfg, &Value::List(vec![]))? {
        let rec = &texts
            .iter()
            .find(|(n, _)| n == s.name())
            .ok_or_else(|| PowerError::new("KeyError", py_repr_str(s.name())))?
            .1;
        let mut load = Dict::new();
        if s == Slot::ReservedDcPort {
            load.insert("P_W", Value::Float(0.0));
            load.insert("evidence_class", Value::str("assumed"));
            load.insert(
                "source",
                Value::str(format!(
                    "{MASS_POWER_REL} power.configurations.{config} reserved_dc_port: '{}'",
                    text(rec, "status")?
                )),
            );
        } else if let (Slot::Compressor, Some(p)) = (s, compressor_p_w) {
            load.insert("P_W", Value::Float(p));
            load.insert("evidence_class", Value::str("model-derived"));
            let src = if compressor_source.is_empty() { DEFAULT_COMPRESSOR_SOURCE } else { compressor_source };
            load.insert("source", Value::str(src));
        } else {
            load.insert("P_W", Value::str(TBD));
            load.insert("tbd_requires", Value::str(text(rec, "status")?));
        }
        if s == Slot::IcpRfSource {
            load.insert("plane", Value::str("generator_dc_input"));
        }
        loads_d.insert(s.name(), Value::Dict(load));
        let eff_text = text(rec, "efficiency")?;
        let mut eff = Dict::new();
        eff.insert("value", Value::str(TBD));
        eff.insert("tbd_requires", Value::str(eff_text.clone()));
        eff.insert("path", Value::str(eff_path(&eff_text)?));
        effs.insert(s.name(), Value::Dict(eff));
    }
    let mut fe = Dict::new();
    fe.insert("value", Value::str(TBD));
    fe.insert("tbd_requires", Value::str(FRONT_END_TBD));
    let mut args = LedgerArgs::new(Value::Dict(loads_d), Value::Dict(effs), Value::Dict(fe));
    args.config = cfg;
    args.label = Value::str(if compressor_p_w.is_none() { LABEL_OFFICIAL } else { LABEL_PARAMETRIC });
    ledger(&args)
}

/// The official ledger of the selected architecture.
pub fn official_flight_ledger(mp: &MassPowerA9V5) -> PowerResult<Ledger> {
    official_ledger(mp, FLIGHT_CONFIGURATION, None, "")
}
