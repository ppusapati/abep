//! Temporary repository trees for the fail-closed tests: a byte copy of `config/` and `abep_sim/data/` symlinked
//! file by file, with one file removed or replaced. The repository itself is never modified.

#![allow(dead_code)]

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

pub fn repo_root() -> PathBuf {
    abep_provenance::workspace_repo_root().expect("repository root")
}

pub struct Tree {
    pub root: PathBuf,
}

impl Drop for Tree {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

fn copy_dir(src: &Path, dst: &Path) {
    fs::create_dir_all(dst).unwrap();
    for e in fs::read_dir(src).unwrap() {
        let e = e.unwrap();
        let p = e.path();
        if p.is_dir() {
            copy_dir(&p, &dst.join(e.file_name()));
        } else {
            fs::copy(&p, dst.join(e.file_name())).unwrap();
        }
    }
}

static N: AtomicUsize = AtomicUsize::new(0);

/// A tree equal to the repository's frozen inputs.
pub fn tree(tag: &str) -> Tree {
    let repo = repo_root();
    let root = std::env::temp_dir().join(format!(
        "abep_es2_{tag}_{}_{}",
        std::process::id(),
        N.fetch_add(1, Ordering::SeqCst)
    ));
    let _ = fs::remove_dir_all(&root);
    copy_dir(&repo.join("config"), &root.join("config"));
    fs::write(root.join("Cargo.toml"), b"").unwrap();
    let data = root.join("abep_sim").join("data");
    fs::create_dir_all(&data).unwrap();
    for e in fs::read_dir(repo.join("abep_sim").join("data")).unwrap() {
        let e = e.unwrap();
        if e.path().is_file() {
            std::os::unix::fs::symlink(e.path(), data.join(e.file_name())).unwrap();
        }
    }
    Tree { root }
}

impl Tree {
    pub fn data(&self, file: &str) -> PathBuf {
        self.root.join("abep_sim").join("data").join(file)
    }

    pub fn remove(&self, file: &str) -> &Self {
        fs::remove_file(self.data(file)).unwrap();
        self
    }

    /// Replace a data file by a copy whose bytes pass through `f`.
    pub fn alter(&self, file: &str, f: impl Fn(&mut Vec<u8>)) -> &Self {
        let p = self.data(file);
        let mut b = fs::read(&p).unwrap();
        fs::remove_file(&p).unwrap();
        f(&mut b);
        fs::write(&p, b).unwrap();
        self
    }
}
