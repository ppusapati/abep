//! Ground-test isolation (A9.29 sec. 1; programme_v3_1 cargo_workspace_proposal.groundtest_isolation_check; CI_PLAN.md
//! § 8): no workspace crate other than `abep-groundtest` (and an explicit allowlist of non-flight tooling crates, empty
//! today) may depend on `abep-groundtest`, directly or transitively, for any dependency kind. Read from
//! `cargo metadata --format-version 1 --locked --offline`. While `abep-groundtest` does not exist the check is vacuous;
//! it still walks every member's resolved graph and says so.

use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::path::Path;
use std::process::Command;

pub const GROUNDTEST_CRATE: &str = "abep-groundtest";

/// Non-flight tooling crates allowed to depend on `abep-groundtest`, each with its reason. None is needed yet; an entry
/// is a reviewed change and may never name a flight-runtime crate.
pub const ALLOWLIST: &[(&str, &str)] = &[];

/// The flight-runtime crates named by programme_v3_1 `groundtest_isolation_check` (never allowlisted).
pub const FLIGHT_RUNTIME_CRATES: [&str; 12] = [
    "abep-atmos",
    "abep-intake",
    "abep-gaspath",
    "abep-chem",
    "abep-mission",
    "abep-subsystems",
    "abep-hall",
    "abep-julia-bridge",
    "abep-icp",
    "abep-design",
    "abep-uq",
    "abep-assess",
];

#[derive(Debug, Clone)]
pub struct IsolationReport {
    /// `abep-groundtest` is a package of the resolved graph.
    pub groundtest_present: bool,
    /// Workspace members whose resolved graph was walked (sorted names).
    pub members_checked: Vec<String>,
    pub violations: Vec<String>,
}

impl IsolationReport {
    pub fn summary(&self) -> String {
        let scope = if self.groundtest_present {
            "abep-groundtest present".to_string()
        } else {
            format!("VACUOUS: {GROUNDTEST_CRATE} is not in the workspace yet, nothing can depend on it")
        };
        format!(
            "groundtest isolation: {} violation(s); {} member graph(s) walked ({}); {scope}",
            self.violations.len(),
            self.members_checked.len(),
            self.members_checked.join(", ")
        )
    }
}

/// `cargo metadata --format-version 1 --locked --offline` of the workspace at `repo_root`.
pub fn cargo_metadata(cargo: &str, repo_root: &Path) -> Result<Value, String> {
    let o = Command::new(cargo)
        .args(["metadata", "--format-version", "1", "--locked", "--offline", "--manifest-path"])
        .arg(repo_root.join("Cargo.toml"))
        .output()
        .map_err(|e| format!("cannot run {cargo}: {e}"))?;
    if !o.status.success() {
        return Err(format!("cargo metadata failed: {}", String::from_utf8_lossy(&o.stderr).trim()));
    }
    serde_json::from_slice(&o.stdout).map_err(|e| format!("cargo metadata output: {e}"))
}

/// Walk every workspace member's resolved dependency graph (all kinds) and report any path to `abep-groundtest`.
pub fn check_metadata(meta: &Value) -> Result<IsolationReport, String> {
    let packages = meta.get("packages").and_then(Value::as_array).ok_or("metadata has no packages")?;
    let name_of: BTreeMap<&str, &str> =
        packages.iter().filter_map(|p| Some((p.get("id")?.as_str()?, p.get("name")?.as_str()?))).collect();
    let members: Vec<&str> = meta
        .get("workspace_members")
        .and_then(Value::as_array)
        .ok_or("metadata has no workspace_members")?
        .iter()
        .filter_map(Value::as_str)
        .collect();
    let nodes = meta.pointer("/resolve/nodes").and_then(Value::as_array).ok_or("metadata has no resolved graph")?;
    let mut deps: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for n in nodes {
        let id = n.get("id").and_then(Value::as_str).ok_or("resolve node without id")?;
        let d = n.get("deps").and_then(Value::as_array).ok_or("resolve node without deps")?;
        deps.insert(id, d.iter().filter_map(|x| x.get("pkg").and_then(Value::as_str)).collect());
    }
    let groundtest: BTreeSet<&str> =
        name_of.iter().filter(|(_, n)| **n == GROUNDTEST_CRATE).map(|(id, _)| *id).collect();
    let allowed: BTreeSet<&str> = ALLOWLIST.iter().map(|(n, _)| *n).collect();
    let mut violations = Vec::new();
    for (n, _) in ALLOWLIST {
        if FLIGHT_RUNTIME_CRATES.contains(n) {
            violations.push(format!("flight-runtime crate {n} is allowlisted"));
        }
    }
    let mut checked = Vec::new();
    for m in &members {
        let name = name_of.get(m).copied().ok_or_else(|| format!("member {m} is not a package"))?;
        if name == GROUNDTEST_CRATE || allowed.contains(name) {
            continue;
        }
        checked.push(name.to_string());
        let mut prev: BTreeMap<&str, &str> = BTreeMap::new();
        let mut queue = VecDeque::from([*m]);
        let mut seen = BTreeSet::from([*m]);
        while let Some(id) = queue.pop_front() {
            if groundtest.contains(id) {
                let mut path = vec![name_of.get(id).copied().unwrap_or(id)];
                let mut cur = id;
                while let Some(p) = prev.get(cur) {
                    path.push(name_of.get(p).copied().unwrap_or(p));
                    cur = p;
                }
                path.reverse();
                violations.push(format!("{name} depends on {GROUNDTEST_CRATE}: {}", path.join(" -> ")));
                break;
            }
            for d in deps.get(id).map(Vec::as_slice).unwrap_or_default() {
                if seen.insert(d) {
                    prev.insert(d, id);
                    queue.push_back(d);
                }
            }
        }
    }
    checked.sort();
    violations.sort();
    Ok(IsolationReport { groundtest_present: !groundtest.is_empty(), members_checked: checked, violations })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn meta(edges: &[(&str, &str)], members: &[&str]) -> Value {
        let names: BTreeSet<&str> = edges.iter().flat_map(|(a, b)| [*a, *b]).chain(members.iter().copied()).collect();
        json!({
            "packages": names.iter().map(|n| json!({"id": format!("id-{n}"), "name": n})).collect::<Vec<_>>(),
            "workspace_members": members.iter().map(|n| format!("id-{n}")).collect::<Vec<_>>(),
            "resolve": {"nodes": names.iter().map(|n| json!({
                "id": format!("id-{n}"),
                "deps": edges.iter().filter(|(a, _)| a == n)
                    .map(|(_, b)| json!({"pkg": format!("id-{b}"), "dep_kinds": [{"kind": null}]}))
                    .collect::<Vec<_>>()
            })).collect::<Vec<_>>()}
        })
    }

    #[test]
    fn direct_and_transitive_dependencies_on_groundtest_are_violations() {
        let m = meta(
            &[("abep-hall", "abep-types"), ("abep-design", "abep-cli"), ("abep-cli", GROUNDTEST_CRATE)],
            &["abep-hall", "abep-design", "abep-cli", GROUNDTEST_CRATE, "abep-types"],
        );
        let r = check_metadata(&m).unwrap();
        assert!(r.groundtest_present);
        assert_eq!(
            r.violations,
            vec![
                "abep-cli depends on abep-groundtest: abep-cli -> abep-groundtest",
                "abep-design depends on abep-groundtest: abep-design -> abep-cli -> abep-groundtest",
            ]
        );
        assert!(!r.members_checked.contains(&GROUNDTEST_CRATE.to_string()));
    }

    #[test]
    fn clean_graph_passes_and_absence_is_reported_as_vacuous() {
        let r = check_metadata(&meta(&[("abep-hall", "abep-types")], &["abep-hall", "abep-types"])).unwrap();
        assert!(r.violations.is_empty() && !r.groundtest_present);
        assert!(r.summary().contains("VACUOUS"));
        assert!(check_metadata(&json!({"packages": [], "workspace_members": []})).is_err());
    }

    #[test]
    fn allowlist_never_names_a_flight_crate() {
        for (n, reason) in ALLOWLIST {
            assert!(!FLIGHT_RUNTIME_CRATES.contains(n) && !reason.trim().is_empty());
        }
    }
}
