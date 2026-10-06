//! Derived data of the frozen intake surface (the reference triangulation and scipy search structures): the
//! provenance record agrees with the pinned hashes, and any byte change of an artifact or of the frozen surface is
//! refused with MODEL_ERROR before a surface is built (no fallback, no re-triangulation).

use abep_intake::constants::AMU;
use abep_intake::frozen::{
    SEARCH_V1, SEARCH_V1_SHA256, SURFACE_V1_CSV, SURFACE_V1_CSV_SHA256, SURFACE_V1_JSON, SURFACE_V1_JSON_SHA256,
    TRIANGULATION_V1, TRIANGULATION_V1_SHA256,
};
use abep_intake::surface::FrozenIntakeSurfaces;
use abep_provenance::{sha256_file, workspace_repo_root};
use abep_types::{AbepError, EvalStatus};
use std::path::{Path, PathBuf};

const PROVENANCE: &str = "crates/abep-intake/data/PROVENANCE.json";
const FILES: [&str; 4] = [SURFACE_V1_CSV, SURFACE_V1_JSON, TRIANGULATION_V1, SEARCH_V1];

#[test]
fn provenance_record_matches_the_pinned_hashes() {
    let root = workspace_repo_root().unwrap();
    let p: serde_json::Value = serde_json::from_slice(&std::fs::read(root.join(PROVENANCE)).unwrap()).unwrap();
    assert_eq!(p["schema"], "abep_derived_data_provenance_v1");
    let pinned = [(TRIANGULATION_V1, TRIANGULATION_V1_SHA256), (SEARCH_V1, SEARCH_V1_SHA256)];
    let arts = p["artifacts"].as_array().unwrap();
    assert_eq!(arts.len(), pinned.len());
    for (a, (path, sha)) in arts.iter().zip(pinned) {
        assert_eq!(a["path"], path);
        assert_eq!(a["sha256"], sha);
        assert_eq!(sha256_file(&root.join(path)).unwrap(), sha);
    }
    let src = p["derived_from"].as_array().unwrap();
    assert_eq!(src[0]["path"], SURFACE_V1_CSV);
    assert_eq!(src[0]["sha256"], SURFACE_V1_CSV_SHA256);
    assert_eq!(src[1]["path"], SURFACE_V1_JSON);
    assert_eq!(src[1]["sha256"], SURFACE_V1_JSON_SHA256);
    for k in ["scipy", "qhull", "qhull_options"] {
        assert!(p["derivation"]["tools"][k].is_string(), "{k}");
    }
    assert!(p["generator"]["path"].is_string() && p["generator"]["command"].is_string());
}

/// A scratch copy of the four files the loader reads, under a fresh temporary root.
fn scratch_root(tag: &str) -> PathBuf {
    let root = workspace_repo_root().unwrap();
    let dir = std::env::temp_dir().join(format!("abep_intake_{tag}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    for f in FILES {
        let dst = dir.join(f);
        std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
        std::fs::copy(root.join(f), &dst).unwrap();
    }
    dir
}

fn flip_last_byte(path: &Path) {
    let mut b = std::fs::read(path).unwrap();
    let n = b.len();
    b[n - 2] ^= 0x01;
    std::fs::write(path, b).unwrap();
}

#[test]
fn intact_copy_loads_and_any_changed_byte_is_model_error() {
    let mb = 26.0 * AMU;
    let ok = scratch_root("intact");
    assert!(FrozenIntakeSurfaces::load(&ok, mb).is_ok());
    std::fs::remove_dir_all(&ok).unwrap();
    for (i, f) in FILES.iter().enumerate() {
        let dir = scratch_root(&format!("tamper{i}"));
        flip_last_byte(&dir.join(f));
        let e = FrozenIntakeSurfaces::load(&dir, mb).unwrap_err();
        assert_eq!(e.status(), EvalStatus::ModelError, "{f}");
        assert!(matches!(e, AbepError::HashMismatch { .. }), "{f}: {e}");
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
