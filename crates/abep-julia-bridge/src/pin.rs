//! HallThruster.jl pin read in Rust (contract C-JULIA-BRIDGE-LAUNCH, `pin` step): PINNED.toml `[hallthruster]`
//! commit / version and Manifest.toml `julia_version`, read as julia-smoke.yml reads them with tomllib. `verify_pin`
//! additionally requires the admitted `hallthruster_pin` consistency check (abep_provenance::verifier,
//! C-PROVENANCE-VERIFIER) and the hall_physics_boundary pin; any mismatch is MODEL_ERROR. Julia's own `check_pin()`
//! still runs inside every driver.

use abep_hall::py::{self, PyValue};
use abep_hall::{HallError, HallResult};
use abep_provenance::verifier::{run_checks, CheckName};
use abep_types::{AbepError, AbepResult};
use std::path::Path;

/// simulation_completion_programme_v1_1.json hall_physics_boundary.pin.
pub const PIN_COMMIT: &str = "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5";
pub const PIN_VERSION: &str = "0.23.1";
pub const JULIA_VERSION: &str = "1.11.7";
pub const PINNED_REL: &str = "hallthruster_bridge/PINNED.toml";
pub const MANIFEST_REL: &str = "hallthruster_bridge/Manifest.toml";

/// The three pin values as read (Python values: a non-string TOML value is returned as such).
#[derive(Debug, Clone, PartialEq)]
pub struct BridgePin {
    pub commit: PyValue,
    pub version: PyValue,
    pub julia_version: PyValue,
}

impl BridgePin {
    /// (commit, version, julia_version) equal the hall_physics_boundary pin.
    pub fn is_pinned(&self) -> bool {
        self.commit.py_eq(&py::s(PIN_COMMIT))
            && self.version.py_eq(&py::s(PIN_VERSION))
            && self.julia_version.py_eq(&py::s(JULIA_VERSION))
    }
}

/// `tomllib.load(open(path, "rb"))`.
pub fn load_toml(path: &str) -> HallResult<PyValue> {
    let bytes = py::read_file(path)?;
    let text = std::str::from_utf8(&bytes).map_err(|e| HallError::decode(e.to_string()))?;
    let table: toml::Table = toml::from_str(text).map_err(|e| HallError::decode(e.to_string()))?;
    Ok(PyValue::from_toml(&toml::Value::Table(table)))
}

fn key(v: &PyValue, k: &str) -> HallResult<PyValue> {
    py::getitem(v, k).cloned()
}

/// The pin of the bridge under `root` (julia-smoke.yml order: both files loaded, then the three keys).
pub fn read_pin(root: &str) -> HallResult<BridgePin> {
    let pin = load_toml(&py::join(root, PINNED_REL))?;
    let man = load_toml(&py::join(root, MANIFEST_REL))?;
    let ht = key(&pin, "hallthruster")?;
    Ok(BridgePin {
        commit: key(&ht, "commit")?,
        version: key(&ht, "version")?,
        julia_version: key(&man, "julia_version")?,
    })
}

/// The admitted ci_checks `hallthruster_pin` consistency check (PINNED.toml vs Manifest.toml vs Project.toml).
pub fn manifest_consistent(root: &str) -> bool {
    run_checks(Path::new(root), &[CheckName::HallthrusterPin]).iter().all(|r| r.verified())
}

/// Pre-launch pin check: readable, consistent and equal to the hall_physics_boundary pin; otherwise MODEL_ERROR.
pub fn verify_pin(root: &str) -> AbepResult<BridgePin> {
    let pin =
        read_pin(root).map_err(|e| AbepError::Model { message: format!("HallThruster.jl pin unreadable: {e}") })?;
    if !manifest_consistent(root) {
        return Err(AbepError::Model {
            message: "hallthruster_bridge PINNED.toml / Manifest.toml / Project.toml disagree (hallthruster_pin check)"
                .into(),
        });
    }
    if !pin.is_pinned() {
        return Err(AbepError::Model {
            message: format!(
                "HallThruster.jl pin {} / {} / julia {} is not the pinned {PIN_COMMIT} / {PIN_VERSION} / julia \
                 {JULIA_VERSION} (an upgrade is a physics-model change, never automatic)",
                py::py_str(&pin.commit),
                py::py_str(&pin.version),
                py::py_str(&pin.julia_version)
            ),
        });
    }
    Ok(pin)
}

/// The step outcome of the parity case language: {commit, version, julia_version, manifest_consistent,
/// pinned_constants, verify_pin_ok}.
pub fn pin_report(root: &str) -> HallResult<PyValue> {
    let pin = read_pin(root)?;
    let consistent = manifest_consistent(root);
    let pinned = pin.is_pinned();
    let verified = verify_pin(root).is_ok();
    Ok(PyValue::Dict(vec![
        (py::s("commit"), pin.commit),
        (py::s("version"), pin.version),
        (py::s("julia_version"), pin.julia_version),
        (py::s("manifest_consistent"), PyValue::Bool(consistent)),
        (py::s("pinned_constants"), PyValue::Bool(pinned)),
        (py::s("verify_pin_ok"), PyValue::Bool(verified)),
    ]))
}
