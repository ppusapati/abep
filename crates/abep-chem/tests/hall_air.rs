//! NP-HALL-CHEM-AIR: the committed Hall AIR reaction set loads under its pins, its guards refuse what the
//! preregistration refuses, every rebuilt table renders byte for byte from its representation, every validity limit is
//! the support-limit rule, and the set is not admitted today (INCOMPLETE_EVIDENCE, asserted, never skipped).

use abep_chem::checked::Validity;
use abep_chem::hall_air::{
    render_xs, support_limit, xs_files, AirSet, SetStatus, TableKind, AIR_DIR, HALL_ISOLATION, PINNED_FILE,
};
use abep_provenance::{read_verified, sha256_hex, workspace_repo_root};
use abep_types::{AbepError, EvalStatus};
use std::path::{Path, PathBuf};

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

#[test]
fn committed_set_loads_and_is_not_admitted_today() {
    let set = AirSet::load(&repo()).unwrap();
    assert!(set.label.starts_with("abep-air-0."));
    assert_eq!(set.status, SetStatus::IncompleteEvidence);
    let err = set.admission().unwrap_err();
    assert_eq!(err.status(), EvalStatus::IncompleteEvidence);
    let msg = err.to_string();
    for gap in ["HA-O-EL-01", "HA-O-EXC-01", "HA-O2-EXC-01", "HA-O2-EXC-02", "SB-NO", "CA-HALL-AIR-v1"] {
        assert!(msg.contains(gap), "{gap} not named: {msg}");
    }
}

#[test]
fn hall_isolation_files_are_unchanged() {
    for (rel, sha) in HALL_ISOLATION {
        read_verified(&repo().join(rel), sha).unwrap_or_else(|e| panic!("HR-01: {e}"));
    }
}

#[test]
fn every_rebuilt_table_renders_byte_for_byte_and_equals_its_v0_table() {
    let r = repo();
    for xs in xs_files(&r).unwrap() {
        let t = render_xs(&r, &xs).unwrap();
        assert_eq!(sha256_hex(t.dat.as_bytes()), t.v0_sha256, "{xs}: rendering differs from the v0 table");
        let committed = std::fs::read(r.join(&t.table)).unwrap_or_else(|e| panic!("{}: {e}", t.table));
        assert_eq!(committed, t.dat.as_bytes(), "{}", t.table);
        let src = std::fs::read(r.join(format!("{}.source", t.table))).unwrap();
        assert_eq!(src, t.source.as_bytes(), "{}.source", t.table);
    }
}

#[test]
fn every_own_table_has_its_registered_origin_and_validity() {
    let r = repo();
    let set = AirSet::load(&r).unwrap();
    for (f, t) in &set.tables {
        match &t.kind {
            TableKind::Reused => assert!(f.starts_with("../propellants/")),
            TableKind::CopyOfV0 { v0_sha256, .. } => assert_eq!(&t.sha256, v0_sha256, "{f}"),
            TableKind::Xs { xs } => {
                let rendered = render_xs(&r, &format!("{AIR_DIR}/{xs}")).unwrap();
                assert_eq!(rendered.table, format!("{AIR_DIR}/{f}"));
                assert_eq!(sha256_hex(rendered.dat.as_bytes()), t.sha256, "{f}");
                // The verified limit is the support-limit rule on the registered representation (IX-04).
                let limit = support_limit(&rendered.energies_ev, &rendered.sigma_m2).unwrap();
                assert_eq!(set.validity.validity(f), Validity::Verified { max_mean_energy_ev: limit }, "{f}");
            }
        }
        assert_ne!(set.validity.validity(f), Validity::MissingEntry, "{f}");
    }
}

#[test]
fn atomic_o_is_served_only_by_o_tables() {
    let set = AirSet::load(&repo()).unwrap();
    for c in set.configs.values() {
        for r in &c.reactions {
            let t = &set.tables[&r.file];
            assert_eq!(t.target, r.target, "{}: {}", c.name, r.file);
            if r.target == "O" {
                assert!(t.process.starts_with("HA-O-"), "{}: {}", c.name, r.file);
            }
        }
    }
}

/// Copy the set to a scratch repository layout (prereg, lock, Hall-isolation files, N2 tables) for refusal tests.
fn scratch(tag: &str) -> PathBuf {
    let src = repo();
    let dst = std::env::temp_dir().join(format!("abep_hall_air_{tag}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dst);
    let mut rels: Vec<String> = vec![
        abep_chem::hall_air::PREREG_REL.into(),
        abep_chem::hall_air::PREREG_LOCK_REL.into(),
        "hallthruster_bridge/propellants/rate_validity.toml".into(),
    ];
    rels.extend(HALL_ISOLATION.iter().map(|x| x.0.to_string()));
    for e in std::fs::read_dir(src.join("hallthruster_bridge/propellants")).unwrap() {
        let n = e.unwrap().file_name().to_string_lossy().to_string();
        if n.ends_with(".dat") {
            rels.push(format!("hallthruster_bridge/propellants/{n}"));
        }
    }
    copy_tree(&src.join(AIR_DIR), &dst.join(AIR_DIR));
    for rel in rels {
        let to = dst.join(&rel);
        std::fs::create_dir_all(to.parent().unwrap()).unwrap();
        std::fs::copy(src.join(&rel), to).unwrap();
    }
    if src.join("docs/chemistry/o_o2/v0/tables").is_dir() {
        copy_tree(&src.join("docs/chemistry/o_o2/v0/tables"), &dst.join("docs/chemistry/o_o2/v0/tables"));
    }
    dst
}

fn copy_tree(from: &Path, to: &Path) {
    std::fs::create_dir_all(to).unwrap();
    for e in std::fs::read_dir(from).unwrap() {
        let e = e.unwrap();
        if e.file_type().unwrap().is_dir() {
            copy_tree(&e.path(), &to.join(e.file_name()));
        } else {
            std::fs::copy(e.path(), to.join(e.file_name())).unwrap();
        }
    }
}

/// Rewrite AIR_PINNED.toml in a scratch tree after `edit`, re-pinning [files]; returns the new pin.
fn repin(root: &Path, edit: impl Fn(String) -> String) -> String {
    let p = root.join(AIR_DIR).join(PINNED_FILE);
    let mut text = edit(std::fs::read_to_string(&p).unwrap());
    let mut out = String::new();
    let mut in_files = false;
    for line in text.lines() {
        if line.starts_with('[') {
            in_files = line == "[files]";
        }
        if in_files && line.starts_with('"') {
            let (k, _) = line.split_once(" = ").unwrap();
            let name = k.trim_matches('"');
            let sha = sha256_hex(&std::fs::read(root.join(AIR_DIR).join(name)).unwrap());
            out.push_str(&format!("{k} = \"{sha}\"\n"));
        } else {
            out.push_str(line);
            out.push('\n');
        }
    }
    text = out;
    std::fs::write(&p, &text).unwrap();
    sha256_hex(text.as_bytes())
}

#[test]
fn refusals_are_model_errors() {
    let root = scratch("refusals");
    // a changed byte of a pinned file
    let v = root.join(AIR_DIR).join("rate_validity.toml");
    let orig = std::fs::read_to_string(&v).unwrap();
    std::fs::write(&v, format!("{orig}\n")).unwrap();
    let pin = sha256_hex(&std::fs::read(root.join(AIR_DIR).join(PINNED_FILE)).unwrap());
    assert!(matches!(AirSet::load_pinned(&root, &pin), Err(AbepError::HashMismatch { .. })));
    // a mirror that differs from its N2 entry
    std::fs::write(&v, orig.replacen("max_mean_energy_eV = 45.0", "max_mean_energy_eV = 60.0", 1)).unwrap();
    let pin = repin(&root, |t| t);
    let e = AirSet::load_pinned(&root, &pin).unwrap_err();
    assert!(e.to_string().contains("mirrored validity entry differs"), "{e}");
    std::fs::write(&v, &orig).unwrap();
    // an unlisted file in the directory
    std::fs::write(root.join(AIR_DIR).join("stray.dat"), "x").unwrap();
    let pin = repin(&root, |t| t);
    assert!(AirSet::load_pinned(&root, &pin).unwrap_err().to_string().contains("not pinned"));
    std::fs::remove_file(root.join(AIR_DIR).join("stray.dat")).unwrap();
    // COMPLETE with open gaps
    let pin = repin(&root, |t| {
        t.replacen("status = \"INCOMPLETE_EVIDENCE\"", "status = \"COMPLETE_FOR_PARAMETRIC_ENVELOPE\"", 1)
    });
    assert!(AirSet::load_pinned(&root, &pin).unwrap_err().to_string().contains("AD-HA-06"));
    // a status outside the vocabulary
    let pin =
        repin(&root, |t| t.replacen("status = \"COMPLETE_FOR_PARAMETRIC_ENVELOPE\"", "status = \"VALIDATED\"", 1));
    assert!(AirSet::load_pinned(&root, &pin).is_err());
    let _ = std::fs::remove_dir_all(&root);
}

#[test]
fn an_o_target_reaction_on_n2_data_is_refused() {
    let set = AirSet::load(&repo()).unwrap();
    let Some(nominal) = set.nominal_config.clone() else {
        // No configuration yet (abep-air-0.0): the guard is exercised on a synthetic configuration below.
        return synthetic_surrogate_refused();
    };
    let root = scratch("surrogate");
    let p = root.join(AIR_DIR).join(&nominal);
    let text = std::fs::read_to_string(&p).unwrap();
    let bad = format!(
        "{text}\n[[reactions]]\ntype = \"elastic\"\ntarget_species = \"O\"\nrate_coeff_file = \"../propellants/elastic_N2_song2023.dat\"\n"
    );
    std::fs::write(&p, bad).unwrap();
    let pin = repin(&root, |t| t);
    let e = AirSet::load_pinned(&root, &pin).unwrap_err();
    assert!(e.to_string().contains("HR-04"), "{e}");
    let _ = std::fs::remove_dir_all(&root);
}

fn synthetic_surrogate_refused() {
    let root = scratch("surrogate0");
    let cfg = "[[species]]\nsymbol = \"O\"\nmax_charge = 1\n\n[[species]]\nsymbol = \"N2\"\nmax_charge = 1\n\n\
               [[reactions]]\ntype = \"elastic\"\ntarget_species = \"O\"\nrate_coeff_file = \"../propellants/elastic_N2_song2023.dat\"\n";
    std::fs::write(root.join(AIR_DIR).join("air_bad.toml"), cfg).unwrap();
    let pin = repin(&root, |t| {
        t.replacen("configs = []", "configs = [\"air_bad.toml\"]", 1).replacen(
            "[files]\n",
            "[files]\n\"air_bad.toml\" = \"0\"\n",
            1,
        )
    });
    let e = AirSet::load_pinned(&root, &pin).unwrap_err();
    assert!(e.to_string().contains("HR-04"), "{e}");
    let _ = std::fs::remove_dir_all(&root);
}
