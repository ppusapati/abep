//! The reference drag record builder reproduces the committed v1 record (CI_PLAN.md W15: `--check` byte identity), the
//! register data and module pins hold, and the layer separation of the raw modules (contract invariants INV-A-05,
//! INV-D-05; A9.22: no PASS / FAIL, no requirement threshold and no file read in raw physics).

use abep_mission::reference_drag::{MODULE_REL, MODULE_SHA256, REGISTER_REL, REGISTER_SHA256};
use abep_provenance::{sha256_file, workspace_repo_root};
use std::process::Command;

fn src(rel: &str) -> String {
    let root = workspace_repo_root().unwrap();
    std::fs::read_to_string(root.join("crates/abep-mission").join(rel)).unwrap()
}

/// Source without line comments.
fn code(rel: &str) -> String {
    src(rel).lines().map(|l| l.split("//").next().unwrap_or("")).collect::<Vec<_>>().join("\n")
}

#[test]
fn builder_check_reproduces_the_committed_record() {
    let root = workspace_repo_root().unwrap();
    let out = Command::new(env!("CARGO_BIN_EXE_abep-reference-drag-record"))
        .args(["--check", "--repo"])
        .arg(&root)
        .output()
        .unwrap();
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "OK: spacecraft reference drag outputs reproduced");
}

#[test]
fn register_and_module_pins() {
    let root = workspace_repo_root().unwrap();
    assert_eq!(sha256_file(&root.join(REGISTER_REL)).unwrap(), REGISTER_SHA256);
    // while the Python reference module exists it must be the module the register was captured from (DIV-C-01)
    let module = root.join(MODULE_REL);
    if module.exists() {
        assert_eq!(sha256_file(&module).unwrap(), MODULE_SHA256);
    }
}

#[test]
fn raw_drag_module_reads_no_file_and_compares_no_thrust() {
    let c = code("src/reference_drag.rs");
    for t in ["std::fs", "read_verified", "read_bytes", "File::", "nonnegative"] {
        assert!(!c.contains(t), "reference_drag.rs contains {t}");
    }
}

#[test]
fn statewise_record_constructs_no_thrust_and_no_criterion() {
    let c = code("src/statewise_td.rs");
    let flat: String = c.chars().filter(|ch| !ch.is_whitespace()).collect();
    assert_eq!(flat.matches("thrust_minus_drag(").count(), 1);
    assert!(flat.contains("thrust_minus_drag(&Value::Null,&Value::Null,&Value::Null,&Value::Null,hall,&record)"));
    for op in [">=", "<=", "> 0", "< 0"] {
        assert!(!c.contains(op), "statewise_td.rs contains {op}");
    }
}

#[test]
fn pass_fail_vocabulary_only_in_the_quantifier() {
    for rel in ["src/reference_drag.rs", "src/intake_drag.rs", "src/objective.rs", "src/statewise_td.rs"] {
        let c = code(rel);
        assert!(!c.contains("\"PASS\"") && !c.contains("\"FAIL\""), "{rel} carries PASS / FAIL");
    }
    let manifest = src("Cargo.toml");
    assert!(!manifest.contains("abep-assess") && !manifest.contains("abep-groundtest"));
}
