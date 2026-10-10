//! AC-05 (acceptance ACCEPT-NI-ABEP-ASSESS-RFP-MATRIX-V1; SC-WP-11 admission criterion): on the resolved workspace
//! graph (`cargo metadata --locked --offline`), no crate other than the registered top-of-graph tools depends on
//! abep-assess, directly or transitively, for any dependency kind; abep-assess depends on no abep-groundtest.

use abep_provenance::workspace_repo_root;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::process::Command;

const ASSESS: &str = "abep-assess";
/// Crates the dependency rule places above assessment (evidence <- cli; parity / perf tooling).
const ALLOWED_DEPENDENTS: [&str; 4] = ["abep-evidence", "abep-cli", "abep-parity", "abep-perf"];

fn metadata() -> Value {
    let root = workspace_repo_root().unwrap();
    let o = Command::new(env!("CARGO"))
        .args(["metadata", "--format-version", "1", "--locked", "--offline", "--manifest-path"])
        .arg(root.join("Cargo.toml"))
        .output()
        .expect("cargo metadata runs");
    assert!(o.status.success(), "{}", String::from_utf8_lossy(&o.stderr));
    serde_json::from_slice(&o.stdout).unwrap()
}

/// Ids of every package reachable from `start` (all dependency kinds).
fn closure<'a>(start: &'a str, deps: &BTreeMap<&'a str, Vec<&'a str>>) -> BTreeSet<&'a str> {
    let mut seen = BTreeSet::from([start]);
    let mut q = VecDeque::from([start]);
    while let Some(id) = q.pop_front() {
        for d in deps.get(id).map(Vec::as_slice).unwrap_or_default() {
            if seen.insert(d) {
                q.push_back(d);
            }
        }
    }
    seen
}

#[test]
fn no_physics_crate_depends_on_abep_assess() {
    let meta = metadata();
    let packages = meta["packages"].as_array().unwrap();
    let name: BTreeMap<&str, &str> =
        packages.iter().map(|p| (p["id"].as_str().unwrap(), p["name"].as_str().unwrap())).collect();
    let mut deps: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for n in meta["resolve"]["nodes"].as_array().unwrap() {
        deps.insert(
            n["id"].as_str().unwrap(),
            n["deps"].as_array().unwrap().iter().map(|d| d["pkg"].as_str().unwrap()).collect(),
        );
    }
    let members: Vec<&str> =
        meta["workspace_members"].as_array().unwrap().iter().map(|m| m.as_str().unwrap()).collect();
    assert!(members.iter().any(|m| name[m] == ASSESS), "abep-assess is a workspace member");
    let mut walked = 0;
    for m in &members {
        let n = name[m];
        if n == ASSESS || ALLOWED_DEPENDENTS.contains(&n) {
            continue;
        }
        walked += 1;
        let reach: Vec<&str> = closure(m, &deps).into_iter().map(|id| name[id]).collect();
        assert!(!reach.contains(&ASSESS), "{n} depends on {ASSESS}");
    }
    let allowed = members.iter().filter(|m| ALLOWED_DEPENDENTS.contains(&name[**m])).count();
    assert_eq!(walked, members.len() - 1 - allowed, "every other member walked");
    assert!(walked >= 10);
    let assess = members.iter().find(|m| name[**m] == ASSESS).unwrap();
    let reach: Vec<&str> = closure(assess, &deps).into_iter().map(|id| name[id]).collect();
    assert!(!reach.contains(&"abep-groundtest"));
    for p in ["pyo3", "maturin"] {
        assert!(!reach.contains(&p), "abep-assess reaches {p}");
    }
}
