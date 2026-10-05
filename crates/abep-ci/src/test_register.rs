//! Rust-era test rule (A9.29 sec. 9, RM-OQ-05; CI_PLAN.md § 7; CLAUDE.md rule 9): no `#[ignore]` (plain or through
//! `cfg_attr`) in workspace crates, except tests of the registered platform / hardware class, marked
//! `#[ignore = "REGISTERED_PLATFORM_TEST:<id>"]` and listed in the register. Every register entry must match a test
//! that still exists, so a registered test never leaves the inventory silently.
//!
//! The scan tokenizes Rust source (comments, string, raw-string and char literals are skipped), so the pattern inside a
//! string or a comment is not an attribute.

use serde_json::Value;
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

pub const REGISTER_PATH: &str = "docs/rust_migration/test_register/platform_tests_v1.json";
pub const REGISTER_SCHEMA: &str = "abep_platform_test_register_v1";
pub const MARKER_PREFIX: &str = "REGISTERED_PLATFORM_TEST:";
pub const ENTRY_FIELDS: [&str; 8] = [
    "id",
    "crate",
    "path",
    "function",
    "reason",
    "owner_or_evidence_basis",
    "execution_environment",
    "required_trigger",
];

#[derive(Debug, Clone, PartialEq, Eq)]
enum Tok {
    Ident(String),
    Punct(char),
    Str(String),
    Other,
}

fn tokenize(src: &str) -> Vec<(Tok, usize)> {
    let c: Vec<char> = src.chars().collect();
    let (mut i, mut line, mut out) = (0usize, 1usize, Vec::new());
    let at = |k: usize| c.get(k).copied().unwrap_or('\0');
    while i < c.len() {
        let ch = c[i];
        if ch == '\n' {
            line += 1;
            i += 1;
        } else if ch.is_whitespace() {
            i += 1;
        } else if ch == '/' && at(i + 1) == '/' {
            while i < c.len() && c[i] != '\n' {
                i += 1;
            }
        } else if ch == '/' && at(i + 1) == '*' {
            let mut depth = 0;
            while i < c.len() {
                if c[i] == '/' && at(i + 1) == '*' {
                    depth += 1;
                    i += 2;
                } else if c[i] == '*' && at(i + 1) == '/' {
                    depth -= 1;
                    i += 2;
                    if depth == 0 {
                        break;
                    }
                } else {
                    line += usize::from(c[i] == '\n');
                    i += 1;
                }
            }
        } else if let Some((hashes, start)) = raw_string_start(&c, i) {
            let (l0, mut j, mut s) = (line, start, String::new());
            loop {
                if j >= c.len() {
                    break;
                }
                if c[j] == '"' && (1..=hashes).all(|h| at(j + h) == '#') {
                    j += 1 + hashes;
                    break;
                }
                line += usize::from(c[j] == '\n');
                s.push(c[j]);
                j += 1;
            }
            out.push((Tok::Str(s), l0));
            i = j;
        } else if ch == '"' || ((ch == 'b' || ch == 'c') && at(i + 1) == '"') {
            let (l0, mut j, mut s) = (line, if ch == '"' { i + 1 } else { i + 2 }, String::new());
            while j < c.len() && c[j] != '"' {
                if c[j] == '\\' {
                    j += 1;
                }
                if j < c.len() {
                    line += usize::from(c[j] == '\n');
                    s.push(c[j]);
                }
                j += 1;
            }
            out.push((Tok::Str(s), l0));
            i = j + 1;
        } else if ch == '\'' || (ch == 'b' && at(i + 1) == '\'') {
            let q = if ch == '\'' { i } else { i + 1 };
            if at(q + 1) == '\\' {
                let mut j = q + 2;
                while j < c.len() && c[j] != '\'' {
                    j += 1;
                }
                i = j + 1;
                out.push((Tok::Other, line));
            } else if at(q + 2) == '\'' {
                i = q + 3;
                out.push((Tok::Other, line));
            } else {
                i = q + 1; // lifetime or label: the identifier follows
            }
        } else if ch.is_alphabetic() || ch == '_' {
            let mut j = i;
            if ch == 'r' && at(i + 1) == '#' {
                j += 2; // raw identifier
            }
            let s0 = j;
            while j < c.len() && (c[j].is_alphanumeric() || c[j] == '_') {
                j += 1;
            }
            out.push((Tok::Ident(c[s0..j].iter().collect()), line));
            i = j;
        } else if ch.is_ascii_digit() {
            while i < c.len() && (c[i].is_alphanumeric() || c[i] == '_') {
                i += 1;
            }
            out.push((Tok::Other, line));
        } else {
            out.push((Tok::Punct(ch), line));
            i += 1;
        }
    }
    out
}

/// `r"`, `r#"`, `br"`, `br##"`, ...: (number of hashes, index after the opening quote).
fn raw_string_start(c: &[char], i: usize) -> Option<(usize, usize)> {
    let mut j = i;
    if c.get(j) == Some(&'b') || c.get(j) == Some(&'c') {
        j += 1;
    }
    if c.get(j) != Some(&'r') {
        return None;
    }
    j += 1;
    let mut hashes = 0;
    while c.get(j) == Some(&'#') {
        hashes += 1;
        j += 1;
    }
    (c.get(j) == Some(&'"')).then_some((hashes, j + 1))
}

/// One ignore attribute found in a source file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IgnoreAttr {
    pub line: usize,
    pub cfg_attr: bool,
    pub reason: Option<String>,
    pub function: Option<String>,
}

/// Every `#[ignore]`, `#[ignore = "..."]` and `#[cfg_attr(..., ignore ...)]` in `src`.
pub fn scan_source(src: &str) -> Vec<IgnoreAttr> {
    let t = tokenize(src);
    let mut out = Vec::new();
    let mut i = 0;
    while i < t.len() {
        if t[i].0 != Tok::Punct('#') {
            i += 1;
            continue;
        }
        let mut j = i + 1;
        if t.get(j).map(|x| &x.0) == Some(&Tok::Punct('!')) {
            j += 1;
        }
        if t.get(j).map(|x| &x.0) != Some(&Tok::Punct('[')) {
            i += 1;
            continue;
        }
        let (start, mut depth, mut k) = (j + 1, 1, j + 1);
        while k < t.len() && depth > 0 {
            match t[k].0 {
                Tok::Punct('[') => depth += 1,
                Tok::Punct(']') => depth -= 1,
                _ => {}
            }
            k += 1;
        }
        let body = &t[start..k.saturating_sub(1).max(start)];
        let first = body.first().map(|x| &x.0);
        let reason_after = |idx: usize| match (body.get(idx + 1).map(|x| &x.0), body.get(idx + 2).map(|x| &x.0)) {
            (Some(Tok::Punct('=')), Some(Tok::Str(s))) => Some(s.clone()),
            _ => None,
        };
        let found = match first {
            Some(Tok::Ident(n)) if n == "ignore" => Some((false, reason_after(0))),
            Some(Tok::Ident(n)) if n == "cfg_attr" => {
                body.iter().position(|x| x.0 == Tok::Ident("ignore".into())).map(|p| (true, reason_after(p)))
            }
            _ => None,
        };
        if let Some((cfg_attr, reason)) = found {
            out.push(IgnoreAttr { line: t[i].1, cfg_attr, reason, function: next_fn(&t[k..]) });
        }
        i = k;
    }
    out
}

fn next_fn(rest: &[(Tok, usize)]) -> Option<String> {
    for (n, (tok, _)) in rest.iter().enumerate() {
        match tok {
            Tok::Punct('{') | Tok::Punct(';') => return None,
            Tok::Ident(f) if f == "fn" => {
                return match rest.get(n + 1) {
                    Some((Tok::Ident(name), _)) => Some(name.clone()),
                    _ => None,
                }
            }
            _ => {}
        }
    }
    None
}

fn rust_files(dir: &Path, out: &mut Vec<std::path::PathBuf>) {
    let Ok(rd) = fs::read_dir(dir) else { return };
    let mut entries: Vec<_> = rd.filter_map(Result::ok).collect();
    entries.sort_by_key(|e| e.file_name());
    for e in entries {
        let p = e.path();
        let name = e.file_name();
        if p.is_dir() && name != "target" && name != ".git" {
            rust_files(&p, out);
        } else if p.extension().is_some_and(|x| x == "rs") {
            out.push(p);
        }
    }
}

/// Outcome of the register check.
#[derive(Debug, Clone)]
pub struct RegisterReport {
    pub files_scanned: usize,
    pub registered: usize,
    pub ignore_attrs: usize,
    pub violations: Vec<String>,
}

/// Validate the register and scan every `.rs` file under `crates/` (the workspace members, `members = ["crates/*"]`).
pub fn check(repo_root: &Path) -> Result<RegisterReport, String> {
    let reg_path = repo_root.join(REGISTER_PATH);
    let reg: Value = serde_json::from_slice(&fs::read(&reg_path).map_err(|e| format!("{REGISTER_PATH}: {e}"))?)
        .map_err(|e| format!("{REGISTER_PATH}: {e}"))?;
    let mut violations = Vec::new();
    if reg.get("schema").and_then(Value::as_str) != Some(REGISTER_SCHEMA) {
        violations.push(format!("{REGISTER_PATH}: schema is not {REGISTER_SCHEMA}"));
    }
    let fields: Vec<&str> = reg
        .get("entry_fields")
        .and_then(Value::as_object)
        .map(|o| o.keys().map(String::as_str).collect())
        .unwrap_or_default();
    let mut want_fields: Vec<&str> = ENTRY_FIELDS.to_vec();
    want_fields.sort_unstable();
    if fields != want_fields {
        violations.push(format!("{REGISTER_PATH}: entry_fields {fields:?} != {want_fields:?}"));
    }
    let entries = reg.get("tests").and_then(Value::as_array).ok_or(format!("{REGISTER_PATH}: tests is not a list"))?;
    let mut by_id: BTreeMap<String, (String, String)> = BTreeMap::new();
    for (n, e) in entries.iter().enumerate() {
        let get = |k: &str| e.get(k).and_then(Value::as_str).filter(|s| !s.trim().is_empty());
        if let Some(missing) = ENTRY_FIELDS.iter().find(|k| get(k).is_none()) {
            violations.push(format!("{REGISTER_PATH}: tests[{n}] has no non-empty {missing}"));
            continue;
        }
        let id = get("id").unwrap_or_default().to_string();
        let key = (get("path").unwrap_or_default().to_string(), get("function").unwrap_or_default().to_string());
        if by_id.insert(id.clone(), key).is_some() {
            violations.push(format!("{REGISTER_PATH}: duplicate id {id}"));
        }
    }
    let mut files = Vec::new();
    rust_files(&repo_root.join("crates"), &mut files);
    let mut matched: BTreeMap<String, usize> = BTreeMap::new();
    let mut n_attrs = 0;
    for f in &files {
        let rel = f.strip_prefix(repo_root).unwrap_or(f).to_string_lossy().replace('\\', "/");
        let src = fs::read_to_string(f).map_err(|e| format!("{rel}: {e}"))?;
        for a in scan_source(&src) {
            n_attrs += 1;
            let at = format!("{rel}:{}", a.line);
            let id = a.reason.as_deref().and_then(|r| r.strip_prefix(MARKER_PREFIX));
            match (a.cfg_attr, id) {
                (true, _) => violations.push(format!("{at}: cfg_attr(..., ignore) is not allowed")),
                (false, None) => violations.push(format!("{at}: #[ignore] without a registered platform-test marker")),
                (false, Some(id)) => match by_id.get(id) {
                    None => violations.push(format!("{at}: {MARKER_PREFIX}{id} is not in the register")),
                    Some((path, func)) if path != &rel || Some(func) != a.function.as_ref() => violations
                        .push(format!("{at}: {id} is registered for {path}::{func}, found on {:?}", a.function)),
                    Some(_) => *matched.entry(id.to_string()).or_default() += 1,
                },
            }
        }
    }
    for id in by_id.keys() {
        match matched.get(id) {
            None => violations.push(format!("registered platform test {id} has no marked test in the workspace")),
            Some(n) if *n > 1 => violations.push(format!("registered platform test {id} is marked {n} times")),
            Some(_) => {}
        }
    }
    Ok(RegisterReport { files_scanned: files.len(), registered: by_id.len(), ignore_attrs: n_attrs, violations })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_every_ignore_form_and_its_function() {
        let src = "#[test]\n#[ignore]\nfn a() {}\n\
                   #[test]\n#[ignore = \"REGISTERED_PLATFORM_TEST:PT-01\"]\npub async fn b() {}\n\
                   #[cfg_attr(not(feature = \"x\"), ignore)]\n#[test]\nfn c() {}\n\
                   #[cfg_attr(miri, ignore = \"slow\")]\nfn d() {}\n\
                   #[\n  ignore\n]\nfn e() {}\n";
        let f = scan_source(src);
        let got: Vec<(bool, Option<&str>, Option<&str>)> =
            f.iter().map(|a| (a.cfg_attr, a.reason.as_deref(), a.function.as_deref())).collect();
        assert_eq!(
            got,
            vec![
                (false, None, Some("a")),
                (false, Some("REGISTERED_PLATFORM_TEST:PT-01"), Some("b")),
                (true, None, Some("c")),
                (true, Some("slow"), Some("d")),
                (false, None, Some("e")),
            ]
        );
        assert_eq!(f[0].line, 2);
    }

    #[test]
    fn strings_comments_and_chars_are_not_attributes() {
        let src = r####"
            // #[ignore]
            /* #[ignore] /* nested #[ignore] */ still comment #[ignore] */
            const A: &str = "#[ignore]";
            const B: &str = r#"#[ignore] "quoted" "#;
            const C: &[u8] = br##"#[ignore]"##;
            const D: char = '#';
            const E: char = '\'';
            fn f<'a>(x: &'a str) -> &'a str { x }
            #[test]
            fn real() {}
        "####;
        assert!(scan_source(src).is_empty());
        assert_eq!(scan_source(&format!("{src}\n#[ignore]\nfn late() {{}}"))[0].function.as_deref(), Some("late"));
    }

    #[test]
    fn non_test_ignore_has_no_function() {
        assert_eq!(scan_source("#[ignore]\nmod m { fn x() {} }")[0].function, None);
        assert!(scan_source("#[derive(Debug)]\nstruct S;").is_empty());
    }
}
