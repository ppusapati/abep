#![allow(dead_code)]
//! Test helpers: the repository root and throw-away copies of config/ (never the repository's own files).

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

pub fn repo() -> PathBuf {
    abep_provenance::workspace_repo_root().expect("repository root")
}

static N: AtomicUsize = AtomicUsize::new(0);

/// A fresh empty directory under the target directory.
pub fn scratch(tag: &str) -> PathBuf {
    let base = PathBuf::from(env!("CARGO_TARGET_TMPDIR"));
    let d = base.join(format!("abep-config-{tag}-{}-{}", std::process::id(), N.fetch_add(1, Ordering::SeqCst)));
    if d.exists() {
        std::fs::remove_dir_all(&d).unwrap();
    }
    std::fs::create_dir_all(&d).unwrap();
    d
}

pub fn copy_dir(src: &Path, dst: &Path) {
    std::fs::create_dir_all(dst).unwrap();
    for e in std::fs::read_dir(src).unwrap() {
        let e = e.unwrap();
        let to = dst.join(e.file_name());
        if e.path().is_dir() {
            copy_dir(&e.path(), &to);
        } else {
            std::fs::copy(e.path(), &to).unwrap();
        }
    }
}

/// A copy of the repository's config/ in a scratch directory.
pub fn config_copy(tag: &str) -> PathBuf {
    let d = scratch(tag).join("config");
    copy_dir(&repo().join("config"), &d);
    d
}

/// Rewrite MANIFEST.json entries to the current bytes of every listed file (the tests' _remanifest rule).
pub fn remanifest(config: &Path) {
    use abep_types::pyjson::{dumps, loads, Value};
    let p = config.join("MANIFEST.json");
    let mut m = loads(&std::fs::read_to_string(&p).unwrap()).unwrap();
    if let Value::Dict(d) = &mut m {
        if let Some(Value::Dict(files)) = d.get_mut("files") {
            let keys: Vec<String> = files.keys().cloned().collect();
            for k in keys {
                if let Ok(b) = std::fs::read(config.join(&k)) {
                    files.insert(
                        k,
                        abep_types::pydict! { "sha256" => abep_provenance::sha256_hex(&b), "bytes" => b.len() as i64 },
                    );
                }
            }
        }
    }
    let opts = abep_types::pyjson::DumpOptions { indent: Some(1), ..Default::default() };
    std::fs::write(&p, dumps(&m, &opts).unwrap() + "\n").unwrap();
}
