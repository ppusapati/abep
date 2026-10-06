//! Configuration layer of the ABEP Rust simulator (SC-WP-12, A9.29 lane A / ES-1).
//!
//! * [`loaders`]: the sha256-verified loaders of `config/` (port of `abep_sim/configuration.py`; contract
//!   `C-ABEP_SIM_CONFIGURATION_PY` v1). The physics seam ([`loaders::load_operating_inputs`]) reads the operating
//!   scenario only; requirement thresholds are assessment data ([`assessment`]).
//! * [`builder`]: `abep-config build --check`, the byte-identical reproduction of `config/**` and `MANIFEST.json`
//!   (port of `scripts/config/build_config.py`).
//! * [`architecture`]: the active-architecture invariant (port of `abep_sim/design/a9_19_architecture.py`; contract
//!   `C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY` v1): flight hollow cathode NONE, C1 ground test / reference only.
//!
//! Every refusal is fail closed (`MODEL_ERROR`) and carries the Python exception class it mirrors, so that the
//! parity harness can compare refusals exactly (CLAUDE.md rule 3: no silent fallback).

pub mod architecture;
pub mod assessment;
pub mod builder;
mod builder_readme;
pub mod eval;
pub mod loaders;
mod py;
pub mod pysrc;
pub mod textmatch;

use abep_types::pyjson::PyException;
use abep_types::{AbepError, EvalStatus};
use std::fmt;
use std::path::{Path, PathBuf};

/// `ABEP_CONFIG_ROOT`: overrides the configuration root (`<repository>/config`).
pub const CONFIG_ENV: &str = "ABEP_CONFIG_ROOT";

/// A refusal, labelled with the Python exception class it mirrors (`ConfigurationError`, `BuildError`,
/// `ArchitectureRuleError`, or a built-in class such as `KeyError`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigError {
    pub class: &'static str,
    pub message: String,
}

impl ConfigError {
    pub fn new(class: &'static str, message: impl Into<String>) -> Self {
        ConfigError { class, message: message.into() }
    }

    /// `ConfigurationError` (abep_sim/configuration.py).
    pub fn configuration(message: impl Into<String>) -> Self {
        Self::new("ConfigurationError", message)
    }

    /// `BuildError` (scripts/config/build_config.py).
    pub fn build(message: impl Into<String>) -> Self {
        Self::new("BuildError", message)
    }

    /// `ArchitectureRuleError` (abep_sim/design/a9_19_architecture.py).
    pub fn architecture(message: impl Into<String>) -> Self {
        Self::new("ArchitectureRuleError", message)
    }

    /// Every configuration refusal is a model error (fail closed).
    pub fn status(&self) -> EvalStatus {
        EvalStatus::ModelError
    }
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.class, self.message)
    }
}

impl std::error::Error for ConfigError {}

impl From<PyException> for ConfigError {
    fn from(e: PyException) -> Self {
        ConfigError { class: e.class, message: e.message }
    }
}

impl From<ConfigError> for AbepError {
    fn from(e: ConfigError) -> Self {
        match e.class {
            "FileNotFoundError" | "IsADirectoryError" => AbepError::Io { path: String::new(), message: e.message },
            _ => AbepError::Model { message: e.to_string() },
        }
    }
}

pub type ConfigResult<T> = Result<T, ConfigError>;

/// The operating-scenario pin (`abep_sim/configuration.py` OPERATING_SCENARIO_PIN; A9.24 item 4).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScenarioPin {
    pub id: String,
    pub scenario_version: i64,
    pub sha256: String,
}

impl ScenarioPin {
    /// The pinned frozen operating scenario `mission_scenario_v2` (also guarded by bid_source_guard).
    pub fn mission_scenario_v2() -> Self {
        ScenarioPin {
            id: "mission_scenario_v2".into(),
            scenario_version: 2,
            sha256: "885b1f70a1a44389e088837fd37bb79390b63132e3c81f17923103b2f9b5fc49".into(),
        }
    }
}

/// Where a load reads from: the repository root (referenced sources, frozen data) and the configuration root.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigPaths {
    pub repo_root: PathBuf,
    pub config_root: PathBuf,
    /// The operating-scenario pin the loaders enforce (production: [`ScenarioPin::mission_scenario_v2`]).
    pub scenario_pin: ScenarioPin,
}

impl ConfigPaths {
    /// `<repo_root>/config`.
    pub fn repository(repo_root: &Path) -> Self {
        Self::with_config_root(repo_root, &repo_root.join("config"))
    }

    pub fn with_config_root(repo_root: &Path, config_root: &Path) -> Self {
        ConfigPaths {
            repo_root: repo_root.to_path_buf(),
            config_root: config_root.to_path_buf(),
            scenario_pin: ScenarioPin::mission_scenario_v2(),
        }
    }

    /// `configuration.config_root()`: `ABEP_CONFIG_ROOT` when set and non-empty, else `<repo_root>/config`.
    pub fn from_env_value(repo_root: &Path, env: Option<&str>) -> Self {
        match env {
            Some(v) if !v.is_empty() => Self::with_config_root(repo_root, Path::new(v)),
            _ => Self::repository(repo_root),
        }
    }

    /// [`Self::from_env_value`] with the process environment.
    pub fn from_env(repo_root: &Path) -> Self {
        let v = std::env::var(CONFIG_ENV).ok();
        Self::from_env_value(repo_root, v.as_deref())
    }

    /// The repository this crate is built in (tests and tools inside the workspace).
    pub fn workspace() -> Result<Self, AbepError> {
        Ok(Self::repository(&abep_provenance::workspace_repo_root()?))
    }
}
