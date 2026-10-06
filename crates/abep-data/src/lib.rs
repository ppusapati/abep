//! Frozen, hash-pinned dataset readers (CLAUDE.md rule 1; A9.29 sec. 6, RM-OQ-02).
//!
//! Every reader verifies the bytes it reads against every pin that exists for the file (`pins`): the configuration
//! manifest chain `config/MANIFEST.json` -> `config/model_set/physics_model_set_v1.json`, the design-state set
//! reference `config/environment/design_state_set_ref_v1.json` and the dataset's own sidecar JSON. A missing file or a
//! mismatch is `MODEL_ERROR`; there is no fallback dataset and no regeneration path.

pub mod design_states;
pub mod gz;
pub mod hwm14_v2;
pub mod json;
pub mod msis21_v1;
pub mod orbit_v1;
pub mod pins;
pub mod table;

use std::path::{Path, PathBuf};

/// Repository-relative directory of the frozen datasets.
pub const DATA_DIR: &str = "abep_sim/data";

/// `<repo_root>/abep_sim/data/<file>`.
pub fn data_path(repo_root: &Path, file: &str) -> PathBuf {
    repo_root.join(DATA_DIR).join(file)
}

/// Repository-relative path of a dataset file (the key used by the model-set pins).
pub fn data_rel(file: &str) -> String {
    format!("{DATA_DIR}/{file}")
}
