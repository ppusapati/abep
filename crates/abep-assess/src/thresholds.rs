//! Requirement thresholds of the assessment layer, read only from the frozen configuration through abep-config
//! (A9.22 / A9.23 / A9.24 item 5): HC-01..HC-04 from the engineering constraints, HC-05..HC-12 from the gate
//! thresholds. Nothing here parses RFP text and no requirement number is a literal of this crate.

use crate::error::{AssessError, AssessResult};
use crate::py::{dict, s};
use abep_config::loaders::{load_engineering_constraints, load_gate_thresholds, load_manifest};
use abep_config::ConfigPaths;
use abep_provenance::sha256_hex;
use abep_types::pyjson::{Dict, Value};

pub const HC_IDS: [&str; 12] =
    ["HC-01", "HC-02", "HC-03", "HC-04", "HC-05", "HC-06", "HC-07", "HC-08", "HC-09", "HC-10", "HC-11", "HC-12"];

/// The configured limits and the records they come from.
#[derive(Debug, Clone)]
pub struct Thresholds {
    /// `HARD_CONSTRAINT_LIMITS` in the reference order; `None` is a TBD threshold (HC-12).
    pub limits: Vec<(String, Option<f64>)>,
    /// `load_engineering_constraints` (values), for the domain / capability rows of the constraint matrix.
    pub engineering: Value,
    /// `load_gate_thresholds` (limits + gate records).
    pub gates: Value,
    /// sha256 of config/MANIFEST.json as read.
    pub manifest_sha256: String,
}

fn num(v: &Value, what: &str) -> AssessResult<f64> {
    match v {
        Value::Int(_) | Value::Float(_) => Ok(v.to_f64()?),
        _ => Err(AssessError::new("ConfigurationError", format!("{what} is not a number"))),
    }
}

fn field<'a>(v: &'a Value, key: &str) -> AssessResult<&'a Value> {
    v.as_dict()
        .and_then(|d| d.get(key))
        .ok_or_else(|| AssessError::new("ConfigurationError", format!("configuration value {key} missing")))
}

impl Thresholds {
    pub fn load(paths: &ConfigPaths) -> AssessResult<Self> {
        let ec = load_engineering_constraints(paths)?;
        let gt = load_gate_thresholds(paths)?;
        load_manifest(paths)?;
        let manifest = std::fs::read(paths.config_root.join("MANIFEST.json"))
            .map_err(|e| AssessError::new("ConfigurationError", format!("config/MANIFEST.json: {e}")))?;
        // engineering_constraints.REQUIREMENT_LIMITS (HC-01 = thrust_min_mN * 1e-3, HC-02 = thrust_max_mN * 1e-3)
        let mut limits = vec![
            ("HC-01".to_string(), Some(num(field(&ec, "thrust_min_mN")?, "thrust_min_mN")? * 1e-3)),
            ("HC-02".to_string(), Some(num(field(&ec, "thrust_max_mN")?, "thrust_max_mN")? * 1e-3)),
            ("HC-03".to_string(), Some(num(field(&ec, "power_max_W")?, "power_max_W")?)),
            ("HC-04".to_string(), Some(num(field(&ec, "mass_max_kg")?, "mass_max_kg")?)),
        ];
        let gl = field(&gt, "limits")?;
        for id in &HC_IDS[4..] {
            let v = field(gl, id)?;
            limits.push((id.to_string(), if matches!(v, Value::Null) { None } else { Some(num(v, id)?) }));
        }
        Ok(Thresholds { limits, engineering: ec, gates: gt, manifest_sha256: sha256_hex(&manifest) })
    }

    /// The repository configuration (ABEP_CONFIG_ROOT honoured, as abep-config does).
    pub fn workspace() -> AssessResult<Self> {
        let paths = ConfigPaths::workspace().map_err(AssessError::from)?;
        Self::load(&paths)
    }

    pub fn limit(&self, id: &str) -> Option<f64> {
        self.limits.iter().find(|(k, _)| k == id).and_then(|(_, v)| *v)
    }

    /// `HARD_CONSTRAINT_LIMITS` as a dict (TBD -> None).
    pub fn limits_value(&self) -> Value {
        let mut d = Dict::new();
        for (k, v) in &self.limits {
            d.insert(k.as_str(), v.map_or(Value::Null, Value::Float));
        }
        Value::Dict(d)
    }

    /// `(alt_min_km, alt_max_km)` of the engineering constraint altitude_band_km.
    pub fn altitude_band_km(&self) -> AssessResult<(f64, f64)> {
        Ok((
            num(field(&self.engineering, "alt_min_km")?, "alt_min_km")?,
            num(field(&self.engineering, "alt_max_km")?, "alt_max_km")?,
        ))
    }

    /// Provenance of one configured threshold, for assessment records.
    pub fn provenance(&self, id: &str) -> Value {
        let (src, key) = match id {
            "HC-01" => ("config/constraints/engineering_constraints_v1.json", "thrust_sustained_min_mN x 1e-3"),
            "HC-02" => ("config/constraints/engineering_constraints_v1.json", "thrust_capability_mN x 1e-3"),
            "HC-03" => ("config/constraints/engineering_constraints_v1.json", "p_bus_max_W"),
            "HC-04" => ("config/constraints/engineering_constraints_v1.json", "wet_mass_max_kg"),
            _ => ("config/assessment/gate_thresholds_v1.json", "gates"),
        };
        dict(vec![
            ("gate", s(id)),
            ("value", self.limit(id).map_or(Value::Null, Value::Float)),
            ("source", s(src)),
            ("key", s(if key == "gates" { format!("gates.{id}") } else { key.to_string() })),
            ("config_manifest_sha256", s(self.manifest_sha256.clone())),
        ])
    }
}
