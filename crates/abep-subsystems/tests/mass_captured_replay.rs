//! CI replay of the captured Python reference outputs of the SC-WP-07 mass contracts (K-MASS-RULES,
//! C-DOCS_BUDGETS_MASS_POWER_A9_V5, C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3; v1 reports PARITY_PASS / ADMITTED): every
//! scored call is evaluated again by the Rust entry points and compared with the Python outcome captured at the
//! reference commit (inline, or its sha256 when large) or, for a registered divergence, with the registered Rust
//! outcome. Case trees are rebuilt from the registered edits. Keeps the parity after the Python reference retires.

use abep_provenance::{read_verified, sha256_hex, workspace_repo_root};
use abep_subsystems::mass::eval;
use abep_subsystems::mass::py::{dict, gi, iter};
use abep_types::pyjson::{self, py_str, Dict, DumpOptions, Value};
use std::io::Read;
use std::path::{Path, PathBuf};

const MESSAGE_CLASSES: [&str; 7] = [
    "MassError",
    "MassPolicyError",
    "PinError",
    "RuntimeError",
    "OptimizerError",
    "IntakeMassUseError",
    "BookingError",
];

fn load(contract: &str, sha: &str) -> Value {
    let root = workspace_repo_root().unwrap();
    let p =
        root.join("docs/rust_migration/contracts").join(contract).join("reference_outputs/python_outcomes_v1.json.gz");
    let gz = read_verified(&p, sha).unwrap();
    let mut raw = String::new();
    flate2::read::GzDecoder::new(gz.as_slice()).read_to_string(&mut raw).unwrap();
    pyjson::loads(&raw).unwrap()
}

fn canon(v: &Value) -> String {
    pyjson::dumps(v, &DumpOptions { ensure_ascii: false, ..Default::default() }).unwrap()
}

fn outcome(r: Result<Value, abep_types::pyjson::PyException>) -> Value {
    match r {
        Ok(v) => dict(vec![("outcome", Value::str("RETURNED")), ("value", v)]),
        Err(e) => dict(vec![
            ("outcome", Value::str("RAISED")),
            ("class", Value::str(e.class)),
            ("message", Value::str(e.message)),
        ]),
    }
}

/// The registered comparison: outcome, value (canonical JSON), class, and the message of the component's own classes.
fn agrees(want: &Value, got: &Value) -> bool {
    let o = |v: &Value| py_str(gi(v, "outcome").unwrap());
    if o(want) != o(got) {
        return false;
    }
    if o(want) == "RETURNED" {
        return canon(gi(want, "value").unwrap()) == canon(gi(got, "value").unwrap());
    }
    let class = py_str(gi(want, "class").unwrap());
    if class != py_str(gi(got, "class").unwrap()) {
        return false;
    }
    !MESSAGE_CLASSES.contains(&class.as_str()) || gi(want, "message").unwrap() == gi(got, "message").unwrap()
}

struct Expander {
    base: Value,
    trees: Vec<(String, PathBuf)>,
}

impl Expander {
    fn arg(&self, v: &Value) -> Value {
        match v {
            Value::Str(s) if s.starts_with("@TREE:") => {
                let name = &s["@TREE:".len()..];
                let p = &self.trees.iter().find(|t| t.0 == name).unwrap_or_else(|| panic!("tree {name}")).1;
                Value::str(p.display().to_string())
            }
            Value::Str(s) if s.starts_with("@BASE_") => gi(&self.base, &s[1..]).unwrap().clone(),
            Value::Dict(d) if d.len() == 1 && d.contains_key("@BASE_ITEMS_VALUES") => {
                let mut items = gi(&self.base, "BASE_ITEMS").unwrap().clone();
                if let (Value::Dict(it), Value::Dict(vals)) = (&mut items, d.get("@BASE_ITEMS_VALUES").unwrap()) {
                    for (k, val) in vals.iter() {
                        if let Some(Value::Dict(item)) = it.get_mut(k) {
                            item.insert("value", val.clone());
                        }
                    }
                }
                items
            }
            Value::Dict(d) if d.len() == 1 && d.contains_key("@BASE_LINES_PRESENCE") => {
                let mut lines = iter(gi(&self.base, "BASE_LINES").unwrap()).unwrap();
                let pres = iter(d.get("@BASE_LINES_PRESENCE").unwrap()).unwrap();
                for (ln, p) in lines.iter_mut().zip(pres) {
                    if let Value::Dict(x) = ln {
                        x.insert("presence", p);
                    }
                }
                Value::List(lines)
            }
            other => other.clone(),
        }
    }

    fn args(&self, a: &Value) -> Value {
        let mut out = Dict::new();
        for (k, v) in a.as_dict().unwrap().iter() {
            out.insert(k.clone(), self.arg(v));
        }
        Value::Dict(out)
    }
}

fn replay(contract: &str, sha: &str, expected_entries: usize, trees: Vec<(String, PathBuf)>) {
    let doc = load(contract, sha);
    let ex = Expander { base: gi(&doc, "base").unwrap().clone(), trees };
    let entries = iter(gi(&doc, "entries").unwrap()).unwrap();
    assert_eq!(entries.len(), expected_entries, "{contract}: captured entry count");
    let mut failures = Vec::new();
    for e in &entries {
        let fname = py_str(gi(e, "fn").unwrap());
        let got = outcome(eval::call(&fname, &ex.args(gi(e, "args").unwrap())));
        let ok = match e.as_dict().unwrap().get("expected_rust") {
            Some(Value::Dict(_)) => agrees(gi(e, "expected_rust").unwrap(), &got),
            _ => match e.as_dict().unwrap().get("python") {
                Some(p) => agrees(p, &got),
                None => sha256_hex(canon(&got).as_bytes()) == py_str(gi(e, "python_sha256").unwrap()),
            },
        };
        if !ok {
            failures.push(format!(
                "{} {}: {}",
                fname,
                py_str(gi(e, "tag").unwrap()),
                &canon(&got)[..canon(&got).len().min(300)]
            ));
        }
    }
    assert!(
        failures.is_empty(),
        "{contract}: {} of {} disagree: {:#?}",
        failures.len(),
        entries.len(),
        &failures[..failures.len().min(10)]
    );
}

fn scratch(tag: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("abep-mass-replay-{}-{tag}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn copy(root: &Path, tree: &Path, rel: &str) {
    let dst = tree.join(rel);
    std::fs::create_dir_all(dst.parent().unwrap()).unwrap();
    std::fs::copy(root.join(rel), dst).unwrap();
}

const A926_MD: &str = "docs/decisions/OD_2026_10_05_A9_26_MASS_BUDGET_OWNER_DECISIONS.md";
const A926_JS: &str = "docs/decisions/OD_2026_10_05_A9_26_mass_budget_owner_decisions.json";

/// The registered case trees CT-00..CT-15 (contract inputs.case_trees), rebuilt from the captured tree_specs.
fn case_trees(root: &Path, base: &Path, specs: &Value) -> Vec<(String, PathBuf)> {
    let pins: Vec<&str> = abep_subsystems::mass::v5::PINS.iter().map(|p| p.1).collect();
    let mut out = Vec::new();
    for (name, edits) in specs.as_dict().unwrap().iter() {
        let t = base.join(name);
        for rel in &pins {
            copy(root, &t, rel);
        }
        for e in iter(edits).unwrap() {
            let e = iter(&e).unwrap();
            match py_str(&e[0]).as_str() {
                "APPEND_NL" => {
                    let p = t.join(py_str(&e[1]));
                    let mut b = std::fs::read(&p).unwrap();
                    b.push(b'\n');
                    std::fs::write(&p, b).unwrap();
                }
                "DELETE" => std::fs::remove_file(t.join(py_str(&e[1]))).unwrap(),
                kind @ ("MD_DUP_HEADING" | "MD_SHA_TOKEN" | "MD_TEXT") => {
                    let p = t.join(A926_MD);
                    let mut md = String::from_utf8(std::fs::read(&p).unwrap()).unwrap();
                    let head = md.split('\n').find(|x| x.starts_with("## Message 2 \u{2014} ")).unwrap().to_string();
                    md = match kind {
                        "MD_DUP_HEADING" => format!("{md}\n{head}\n"),
                        "MD_SHA_TOKEN" => md.replace("text sha256 `c240fca3", "text sha256 `c240fca4"),
                        _ => {
                            let i = md.find(&head).unwrap();
                            let pat = "SYSTEM-LEVEL MASS MARGIN = 10%";
                            let j = i + md[i..].find(pat).unwrap();
                            format!("{}SYSTEM-LEVEL MASS MARGIN = 11%{}", &md[..j], &md[j + pat.len()..])
                        }
                    };
                    std::fs::write(&p, md).unwrap();
                }
                kind @ ("JSON_MSG2_SHA" | "JSON_VERBATIM_SHA") => {
                    let p = t.join(A926_JS);
                    let mut js = pyjson::loads(&String::from_utf8(std::fs::read(&p).unwrap()).unwrap()).unwrap();
                    let zeros = Value::str("0".repeat(64));
                    if let Value::Dict(d) = &mut js {
                        if kind == "JSON_MSG2_SHA" {
                            if let Some(Value::List(ms)) = d.get_mut("messages") {
                                for m in ms.iter_mut() {
                                    if let Value::Dict(md) = m {
                                        if md.get("n") == Some(&Value::int(2)) {
                                            md.insert("text_sha256", zeros.clone());
                                        }
                                    }
                                }
                            }
                        } else if let Some(Value::Dict(vb)) = d.get_mut("verbatim") {
                            vb.insert("sha256", zeros.clone());
                        }
                    }
                    std::fs::write(&p, pyjson::dumps(&js, &DumpOptions::config_writer()).unwrap()).unwrap();
                }
                other => panic!("unregistered edit {other}"),
            }
        }
        out.push((name.clone(), t));
    }
    out
}

fn dict_mut<'a>(v: &'a mut Value, key: &str) -> &'a mut Value {
    match v {
        Value::Dict(d) => d.get_mut(key).unwrap(),
        _ => panic!("dict"),
    }
}

fn list_mut(v: &mut Value) -> &mut Vec<Value> {
    match v {
        Value::List(l) => l,
        _ => panic!("list"),
    }
}

fn set_line(rec: &mut Value, lid: &str, key: &str, val: Value) {
    let lines = list_mut(dict_mut(dict_mut(rec, "lines"), "hall_icp_neutralizer"));
    let ln = lines.iter_mut().find(|x| py_str(gi(x, "line").unwrap()) == lid).unwrap();
    if let Value::Dict(d) = ln {
        d.insert(key, val);
    }
}

/// The registered W-trees W0 and RT-01..RT-06 (records written as json.dumps(indent=1, ensure_ascii=False) + "\n").
fn w_trees(root: &Path, base: &Path) -> Vec<(String, PathBuf)> {
    let rel = abep_subsystems::mass::v5::RECORD_REL;
    let committed = pyjson::loads(&String::from_utf8(std::fs::read(root.join(rel)).unwrap()).unwrap()).unwrap();
    let mut out = Vec::new();
    for name in ["W0", "RT-01", "RT-02", "RT-03", "RT-04", "RT-05", "RT-06"] {
        let t = base.join(name);
        std::fs::create_dir_all(t.join(rel).parent().unwrap()).unwrap();
        if name == "W0" {
            std::fs::copy(root.join(rel), t.join(rel)).unwrap();
            out.push((name.to_string(), t));
            continue;
        }
        let mut d = committed.clone();
        match name {
            "RT-01" => set_line(&mut d, "AL-03", "cbe_kg", Value::Float(1.0)),
            "RT-02" => set_line(&mut d, "AL-05", "measured_kg", Value::Float(2.0)),
            "RT-03" => {
                let roll = &mut list_mut(dict_mut(&mut d, "rollups"))[0];
                let wet = list_mut(dict_mut(roll, "wet"));
                wet.retain(|w| py_str(gi(w, "reference").unwrap()) != "HARD_40_WET");
            }
            "RT-04" => {
                let rolls = list_mut(dict_mut(&mut d, "rollups"));
                let first = rolls[0].clone();
                rolls.push(first);
            }
            "RT-05" => {
                if let Value::Dict(l) = dict_mut(&mut d, "lines") {
                    l.remove("hall_icp_neutralizer");
                }
            }
            _ => {
                let roll = &mut list_mut(dict_mut(&mut d, "rollups"))[0];
                for w in list_mut(dict_mut(roll, "wet")).iter_mut() {
                    let hard = py_str(gi(w, "reference").unwrap()) == "HARD_40_WET";
                    if hard && gi(w, "xe_case_kg").unwrap() == &Value::Float(2.0) {
                        if let Value::Dict(x) = w {
                            x.insert("state", Value::str("CLOSES"));
                        }
                        break;
                    }
                }
            }
        }
        std::fs::write(t.join(rel), pyjson::dumps_config_file(&d).unwrap()).unwrap();
        out.push((name.to_string(), t));
    }
    out
}

#[test]
fn k_mass_rules_reproduces_the_captured_reference() {
    replay("K-MASS-RULES", "65a23f2db43dcea9f36893b100b8232716999346e5bd80bd56eda5909456db15", 8749, vec![]);
}

#[test]
fn mass_power_v5_reproduces_the_captured_reference() {
    let root = workspace_repo_root().unwrap();
    let sha = "a2a458502de7b449907af6f7e95db7c6eeb6f769cb4b2ffe7193d90ae2cf6b00";
    let doc = load("C-DOCS_BUDGETS_MASS_POWER_A9_V5", sha);
    let base = scratch("v5");
    let mut trees = case_trees(&root, &base, gi(gi(&doc, "tree_specs").unwrap(), "case_trees").unwrap());
    trees.extend(w_trees(&root, &base));
    replay("C-DOCS_BUDGETS_MASS_POWER_A9_V5", sha, 1729, trees);
    std::fs::remove_dir_all(&base).unwrap();
}

#[test]
fn xe_accounting_v3_kernels_reproduce_the_captured_reference() {
    replay(
        "C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3",
        "7ae4350bf66a28b1d69a111fe4a8d63be1b547adf2140383da60b5bfc2e45700",
        3590,
        vec![],
    );
}
