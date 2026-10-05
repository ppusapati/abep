//! Assessment-layer configuration (A9.22 / A9.23): the requirements snapshot is provenance for compliance mapping
//! and is never read by physics or design seams. Gate thresholds are loaded by
//! [`crate::loaders::load_gate_thresholds`] as values only; nothing here evaluates a requirement.

use crate::loaders::{load_manifest, load_verified, physics_configuration, SimulationConfiguration, REQUIREMENTS_REL};
use crate::py::{get, index, is_str, r};
use crate::{ConfigError, ConfigPaths, ConfigResult};
use abep_types::pyjson::Value;

/// `load_requirements_snapshot(root)`: the RFP-derived requirements snapshot (PROVENANCE layer).
pub fn load_requirements_snapshot(paths: &ConfigPaths) -> ConfigResult<Value> {
    let d = load_verified(REQUIREMENTS_REL, paths)?;
    if !is_str(get(&d, "schema")?, "abep_config_requirements_snapshot_v1") {
        return Err(ConfigError::configuration("requirements snapshot: unexpected schema"));
    }
    let st = get(&d, "snapshot_status")?;
    if !(is_str(st, "FROZEN") || is_str(st, "PROVISIONAL")) {
        return Err(ConfigError::configuration(format!(
            "requirements snapshot: status {} not FROZEN/PROVISIONAL",
            r(st)
        )));
    }
    Ok(d)
}

/// `assessment_configuration(root)`: the physics configuration plus the requirements-snapshot identity.
pub fn assessment_configuration(paths: &ConfigPaths) -> ConfigResult<SimulationConfiguration> {
    let mut c = physics_configuration(paths)?;
    let snap = load_requirements_snapshot(paths)?;
    c.requirements_snapshot_id = index(&snap, "id")?.clone();
    let man = load_manifest(paths)?;
    c.requirements_snapshot_sha256 = index(index(index(&man, "files")?, REQUIREMENTS_REL)?, "sha256")?.clone();
    c.requirements_snapshot_status = index(&snap, "snapshot_status")?.clone();
    Ok(c)
}
