//! Reference spacecraft drag basis record builder (owner decision A9.13 S6.18 / OQ-F78-04): REFERENCE/PARAMETRIC,
//! never the flight spacecraft. Port of docs/design_synthesis/spacecraft_reference_drag/build_spacecraft_reference_drag.py
//! (PARITY-C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG-V1): verifies the owner decision records, builds
//! spacecraft_reference_drag_v1.json from abep_mission::reference_drag and renders SPACECRAFT_REFERENCE_DRAG.md from it.
//!
//! ```text
//! abep-reference-drag-record [--repo <root>]           # write outputs
//! abep-reference-drag-record --check [--repo <root>]   # exit 1 unless reproduced
//! ```
//!
//! The v1 record's provenance block names its original builder and module (module_sha256 = the pin the register was
//! captured from): a present module file must match the pin (DIV-C-01); an absent one (Python retired) is not needed
//! (DIV-C-02). A refused build prints `<class>: <message>` on stderr and exits 1 before writing anything.

use abep_atmos::pyfloat::py_format_g;
use abep_mission::reference_drag::{build_document, register, MODULE_REL, MODULE_SHA256};
use abep_provenance::sha256_hex;
use abep_types::pyjson::{dumps, py_str, read_text_utf8, Dict, DumpOptions, Value};
use std::path::{Path, PathBuf};

const OUT_DIR: &str = "docs/design_synthesis/spacecraft_reference_drag";
const JSON_NAME: &str = "spacecraft_reference_drag_v1.json";
const MD_NAME: &str = "SPACECRAFT_REFERENCE_DRAG.md";
const BUILDER_REL: &str = "docs/design_synthesis/spacecraft_reference_drag/build_spacecraft_reference_drag.py";

struct Refusal {
    class: &'static str,
    message: String,
}

fn sha(repo: &Path, rel: &str) -> Result<String, Refusal> {
    let bytes = std::fs::read(repo.join(rel))
        .map_err(|_| Refusal { class: "FileNotFoundError", message: format!("pinned input missing: {rel}") })?;
    Ok(sha256_hex(&bytes))
}

fn verify_decisions(repo: &Path) -> Result<(), Refusal> {
    let reg = register().map_err(|e| Refusal { class: "RuntimeError", message: e.to_string() })?;
    for d in &reg.decisions {
        for (path, expected) in [(&d.path, &d.md_sha256), (&d.json_path, &d.json_sha256)] {
            let got = sha(repo, path)?;
            if &got != expected {
                return Err(Refusal {
                    class: "RuntimeError",
                    message: format!("decision record changed: {path} sha256 {got} != {expected}"),
                });
            }
        }
    }
    Ok(())
}

fn module_pin(repo: &Path) -> Result<(), Refusal> {
    let p = repo.join(MODULE_REL);
    if !p.exists() {
        return Ok(());
    }
    let got = sha(repo, MODULE_REL)?;
    if got != MODULE_SHA256 {
        return Err(Refusal {
            class: "RuntimeError",
            message: format!(
                "reference module changed: {MODULE_REL} sha256 {got} != {MODULE_SHA256} (the Rust register was \
                 captured from the pinned module; contract DIV-C-01)"
            ),
        });
    }
    Ok(())
}

fn build_json(repo: &Path) -> Result<Value, Refusal> {
    verify_decisions(repo)?;
    let doc = build_document().map_err(|e| Refusal { class: "RuntimeError", message: e.to_string() })?;
    module_pin(repo)?;
    let mut d: Dict = doc.as_dict().cloned().unwrap_or_default();
    d.insert(
        "provenance",
        abep_types::pydict! { "builder" => BUILDER_REL, "module" => MODULE_REL, "module_sha256" => MODULE_SHA256 },
    );
    Ok(Value::Dict(d))
}

/// `_fmt(v)` of the reference builder.
fn fmt(v: &Value) -> String {
    match v {
        Value::Null => "TBD".into(),
        Value::List(l) => {
            if l.len() == 2 && l.iter().all(|x| matches!(x, Value::Int(_) | Value::Float(_) | Value::Bool(_))) {
                l.iter().map(fmt).collect::<Vec<_>>().join("\u{2013}")
            } else {
                l.iter().map(fmt).collect::<Vec<_>>().join(", ")
            }
        }
        Value::Float(f) => py_format_g(*f),
        other => py_str(other).replace('|', "/"),
    }
}

fn s<'a>(d: &'a Value, k: &str) -> &'a Value {
    const NULL: Value = Value::Null;
    d.as_dict().and_then(|x| x.get(k)).unwrap_or(&NULL)
}

fn st(d: &Value, k: &str) -> String {
    py_str(s(d, k))
}

fn g(d: &Value, k: &str) -> String {
    match s(d, k) {
        Value::Float(f) => py_format_g(*f),
        Value::Int(i) => py_format_g(i.to_f64().unwrap_or(f64::NAN)),
        other => py_str(other),
    }
}

fn list<'a>(d: &'a Value, k: &str) -> &'a [Value] {
    s(d, k).as_list().unwrap_or_default()
}

fn render_md(doc: &Value) -> String {
    let mut l: Vec<String> = Vec::new();
    let mut a = |x: String| l.push(x);
    a("# Reference spacecraft drag basis (REFERENCE/PARAMETRIC \u{2014} not the flight spacecraft)".into());
    a(String::new());
    a(format!(
        "Generated from `{JSON_NAME}` by `build_spacecraft_reference_drag.py`; do not edit by hand. Status **{}**, freeze \
         status **{}**.",
        st(doc, "status"),
        st(doc, "freeze_status")
    ));
    a(String::new());
    a("## Owner basis".into());
    for d in list(doc, "decisions") {
        let qids = list(d, "question_ids");
        let q = if qids.is_empty() {
            "(no drag question)".to_string()
        } else {
            qids.iter().map(py_str).collect::<Vec<_>>().join("; ")
        };
        a(format!(
            "- `{}` (json `{}` sha256 `{}`): {q}. {}.",
            st(d, "path"),
            st(d, "json_path"),
            st(d, "json_sha256"),
            st(d, "used_for")
        ));
    }
    a(String::new());
    a("S6.18: sourced geometry is for interim parametric studies only and is labelled `REFERENCE/PARAMETRIC`. AG-13 \
       closure needs the host-spacecraft ICD; until then `D_spacecraft` and `T - D` remain `NOT_EVALUATED` for freeze \
       purposes. S6.15: `T_available(state) - D_spacecraft(state) >= 0` statewise, thrust and drag at the same state."
        .into());
    a(String::new());
    a("## Scope".into());
    if let Some(scope) = s(doc, "scope").as_dict() {
        for (k, v) in scope.iter() {
            a(format!("- **{k}**: {}", py_str(v)));
        }
    }
    let b = s(doc, "rfp_thrust_band");
    a(format!(
        "- **thrust band**: {}\u{2013}{} mN, `{}`. {}",
        g(b, "min_mN"),
        g(b, "max_mN"),
        st(b, "requirement_status"),
        st(b, "note")
    ));
    a(String::new());
    a("## Declared reference cases (same-source (A_ref, C_D) pairs only)".into());
    a(String::new());
    a("| case | record | C_D | A_ref (m\u{b2}) | C_D\u{b7}A (m\u{b2}) | A_ref scope | q at 12 mN (Pa) | q at 25 mN (Pa) | level | type |"
        .into());
    a("|---|---|---|---|---|---|---|---|---|---|".into());
    for r in list(doc, "density_free_table") {
        a(format!(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |",
            st(r, "case_id"),
            st(r, "record_id"),
            g(r, "cd"),
            g(r, "a_ref_m2"),
            g(r, "cd_a_m2"),
            st(r, "a_ref_scope"),
            g(r, "q_at_12mN_Pa"),
            g(r, "q_at_25mN_Pa"),
            st(r, "evidence_level"),
            st(r, "quantity_type")
        ));
    }
    a(String::new());
    a("`q = \u{bd}\u{3c1}v\u{b2}` at which the reference term alone equals a band edge (intake term excluded). This is \
       density-free; statewise values need the orbit-resolved atmosphere (caller input)."
        .into());
    a(String::new());
    a("## Reference records".into());
    a(String::new());
    a("| id | name | altitude (km) | mass (kg) | frontal area (m\u{b2}) | C_D | C_D basis | A_ref scope |".into());
    a("|---|---|---|---|---|---|---|---|".into());
    for r in list(doc, "records") {
        let val = |k: &str| fmt(s(s(r, k), "value"));
        a(format!(
            "| {} | {} | {} | {} | {} | {} | {} | {} |",
            st(r, "id"),
            st(r, "name"),
            val("altitude_km"),
            val("mass_kg"),
            val("frontal_area_m2"),
            val("cd"),
            val("cd_model_basis"),
            fmt(s(r, "a_ref_scope"))
        ));
    }
    a(String::new());
    a("Per-value source, evidence level, quantity type and verbatim notes are in the JSON (`records[*].*`).".into());
    a(String::new());
    a("## Sources read".into());
    if let Some(sources) = s(doc, "sources").as_dict() {
        for (k, v) in sources.iter() {
            let sha = match s(v, "retrieved_sha256") {
                x if x.truthy() => py_str(x),
                _ => "n/a".to_string(),
            };
            a(format!(
                "- **{k}** \u{2014} {}. <{}>. Access: {}. Retrieved sha256: `{sha}`. {}.",
                st(v, "citation"),
                st(v, "url"),
                st(v, "access"),
                st(v, "verbatim_check")
            ));
        }
    }
    a(String::new());
    a("## Cited but not accessed".into());
    for n in list(doc, "not_accessed") {
        a(format!("- {} \u{2014} {}; {}.", st(n, "ref"), st(n, "why"), st(n, "consequence")));
    }
    a(String::new());
    a("## Findings".into());
    for f in list(doc, "findings") {
        a(format!("- **{}** {}. Action: {}.", st(f, "id"), st(f, "finding"), st(f, "action")));
    }
    a(String::new());
    a("## Open items".into());
    for o in list(doc, "open_items") {
        a(format!("- {}", py_str(o)));
    }
    a(String::new());
    l.join("\n")
}

fn render_json(doc: &Value) -> Result<String, Refusal> {
    let opts = DumpOptions { indent: Some(1), ensure_ascii: false, ..Default::default() };
    let mut text = dumps(doc, &opts).map_err(|e| Refusal { class: e.class, message: e.message })?;
    text.push('\n');
    Ok(text)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let check = args.iter().any(|a| a == "--check");
    let repo: PathBuf = match args.iter().position(|a| a == "--repo") {
        Some(i) => PathBuf::from(args.get(i + 1).expect("--repo needs a path")),
        None => abep_provenance::find_repo_root(Path::new(".")).expect("repository root"),
    };
    let outs = build_json(&repo).and_then(|doc| {
        Ok(vec![
            (repo.join(OUT_DIR).join(JSON_NAME), JSON_NAME, render_json(&doc)?),
            (repo.join(OUT_DIR).join(MD_NAME), MD_NAME, render_md(&doc)),
        ])
    });
    let outs = match outs {
        Ok(o) => o,
        Err(r) => {
            eprintln!("{}: {}", r.class, r.message);
            std::process::exit(1);
        }
    };
    if check {
        let bad: Vec<&str> = outs
            .iter()
            .filter(|(p, _, txt)| {
                std::fs::read(p).ok().and_then(|b| read_text_utf8(&b).ok()).is_none_or(|have| &have != txt)
            })
            .map(|(_, name, _)| *name)
            .collect();
        if !bad.is_empty() {
            println!("CHECK FAILED (not reproduced): {}", bad.join(", "));
            std::process::exit(1);
        }
        println!("OK: spacecraft reference drag outputs reproduced");
        return;
    }
    std::fs::create_dir_all(repo.join(OUT_DIR)).expect("output directory");
    for (p, name, txt) in &outs {
        std::fs::write(p, txt.as_bytes()).expect("write output");
        println!("wrote {OUT_DIR}/{name}");
    }
}
