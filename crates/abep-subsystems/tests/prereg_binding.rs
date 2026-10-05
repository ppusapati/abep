//! Binding of the implementation to its preregistration (CI_PLAN principle 9): the prereg_v1 lock, the transcribed
//! vocabulary (nodes, interface keys, numerics), the governed state the gates read (credible Hall transport set EMPTY,
//! HallThruster.jl pin, design states), and the principle-6 forbidden-identifier scan of this crate.

use abep_provenance::{sha256_file, workspace_repo_root};
use abep_subsystems::thermal::governance::{self, GovernedContext};
use abep_subsystems::thermal::{assemble, solver, vocab, MODEL_ID, MODEL_VERSION};
use serde_json::Value;
use std::path::{Path, PathBuf};

fn json(rel: &str) -> Value {
    let root = workspace_repo_root().unwrap();
    serde_json::from_slice(&std::fs::read(root.join(rel)).unwrap()).unwrap()
}

#[test]
fn prereg_files_match_the_lock_and_the_compiled_constants() {
    let root = workspace_repo_root().unwrap();
    let lock = json(governance::PREREG_LOCK_PATH);
    assert_eq!(lock["model_id"], MODEL_ID);
    assert_eq!(lock["files"]["prereg_v1.json"], governance::PREREG_SHA256);
    assert_eq!(lock["files"]["PREREG.md"], governance::PREREG_MD_SHA256);
    assert_eq!(sha256_file(&root.join(governance::PREREG_PATH)).unwrap(), governance::PREREG_SHA256);
    assert_eq!(sha256_file(&root.join(governance::PREREG_MD_PATH)).unwrap(), governance::PREREG_MD_SHA256);
    let p = json(governance::PREREG_PATH);
    assert_eq!(p["id"], MODEL_ID);
    assert_eq!(p["model_version"], MODEL_VERSION);
    assert_eq!(p["target_crate"], "abep-subsystems::thermal");
    assert_eq!(p["contract_kind"], "NEW_PHYSICS");
}

#[test]
fn node_registry_is_the_preregistered_node_set() {
    let p = json(governance::PREREG_PATH);
    let solved = p["nodes"]["solved"].as_array().unwrap();
    assert_eq!(solved.len(), vocab::NODES.len());
    for (n, reg) in solved.iter().zip(vocab::NODES.iter()) {
        assert_eq!(n["id"], reg.id);
        assert_eq!(n["group"], reg.group);
        let presence = n["presence"].as_str().unwrap();
        assert_eq!(presence.starts_with("REQUIRED"), reg.required, "{}", reg.id);
        assert!(reg.required || presence.starts_with("CONDITIONAL"));
        for k in reg.receives {
            let declared =
                n["receives_interface_keys"].as_array().unwrap().iter().any(|x| x.as_str().unwrap().contains(k));
            assert!(declared, "{} does not register {k}", reg.id);
        }
    }
    let excluded: Vec<&str> =
        p["nodes"]["excluded"].as_array().unwrap().iter().map(|x| x["id"].as_str().unwrap()).collect();
    for id in ["CB", "CE", "CK", "PIM", "PPU"] {
        assert!(excluded.contains(&id) && vocab::EXCLUDED_NODE_IDS.contains(&id));
    }
}

#[test]
fn interface_keys_are_the_preregistered_keys() {
    let p = json(governance::PREREG_PATH);
    let hall: Vec<String> = p["heat_sources"]["IF-HALL-THERMAL-v1"]["keys"]
        .as_array()
        .unwrap()
        .iter()
        .map(|k| k["key"].as_str().unwrap().to_string())
        .collect();
    for (i, k) in vocab::HALL_DISCHARGE_KEYS.iter().enumerate() {
        assert_eq!(hall[i], k.key, "HK-{:02}", i + 1);
    }
    for (_, _, q, i, r, t) in vocab::COILS {
        assert!(hall[9].contains(q), "HK-10 lists {q}");
        let hk11 = &hall[10];
        let pos = q.trim_start_matches("Q_hall_coil_").trim_end_matches("_W");
        assert!(
            hk11.contains("I_hall_coil_X_A")
                && hk11.contains("R_hall_coil_X_ref_ohm")
                && hk11.contains("T_hall_coil_X_ref_K")
        );
        assert_eq!(i, format!("I_hall_coil_{pos}_A"));
        assert_eq!(r, format!("R_hall_coil_{pos}_ref_ohm"));
        assert_eq!(t, format!("T_hall_coil_{pos}_ref_K"));
    }
    let icp: Vec<&str> = p["heat_sources"]["IF-ICP-THERMAL-v1"]["keys"]
        .as_array()
        .unwrap()
        .iter()
        .map(|k| k["key"].as_str().unwrap())
        .collect();
    let ours: Vec<&str> = vocab::ICP_KEYS.iter().map(|k| k.key).collect();
    assert_eq!(icp, ours);
}

#[test]
fn numerics_and_tolerances_are_the_preregistered_values() {
    let p = json(governance::PREREG_PATH);
    let rule = |section: &str, id: &str| -> String {
        let items = p[section].as_array().unwrap();
        let it = items.iter().find(|x| x["id"] == id).unwrap();
        it.get("rule")
            .or_else(|| it.get("criterion"))
            .or_else(|| it.get("definition"))
            .unwrap()
            .as_str()
            .unwrap()
            .to_string()
    };
    assert!(rule("numerics", "NUM-01").contains("1e-8 K") && rule("numerics", "NUM-01").contains("100 iterations"));
    assert_eq!((solver::NUM01_MAX_DT_K, solver::NUM01_CAP), (1e-8, 100));
    assert!(rule("numerics", "NUM-03").contains("1e-9 K") && rule("numerics", "NUM-03").contains("50 iterations"));
    assert_eq!((solver::NUM03_MAX_DT_K, solver::NUM03_CAP), (1e-9, 50));
    assert!(rule("numerics", "NUM-04").contains("20 successive halvings"));
    assert_eq!(solver::NUM04_HALVING_CAP, 20);
    assert!(rule("numerics", "NUM-05").contains("200 orbits"));
    assert_eq!(solver::NUM05_ORBIT_CAP, 200);
    assert!(rule("numerics", "NUM-09").contains("1e-6 * (reference power of the identity) + 1e-9 W"));
    assert_eq!((assemble::EPS_IF_REL, assemble::EPS_IF_ABS), (1e-6, 1e-9));
    assert!(rule("conservation", "CONS-S1").contains("1e-9 * Q_scale + 1e-9 W"));
    assert_eq!((solver::CONS_S_REL, solver::CONS_S_ABS_W), (1e-9, 1e-9));
    assert!(
        rule("conservation", "CONS-T1").contains("1e-8 * max(") && rule("conservation", "CONS-T1").contains("+ 1e-6 J")
    );
    assert_eq!((solver::CONS_T1_REL, solver::CONS_T1_ABS_J), (1e-8, 1e-6));
    assert!(rule("conservation", "CONS-T2").contains("1e-2 K"));
    assert_eq!(solver::CONS_T2_K, 1e-2);
    assert!(rule("conservation", "CONS-T3").contains("1e-3 K"));
    assert_eq!(solver::CONS_T3_K, 1e-3);
    assert!(rule("conservation", "CONS-I2").contains("1e-12 relative + 1e-12 W"));
    assert_eq!((assemble::CONS_I2_REL, assemble::CONS_I2_ABS), (1e-12, 1e-12));
    let d07 = p["domains"].as_array().unwrap().iter().find(|x| x["id"] == "D-07").unwrap()["rule"]
        .as_str()
        .unwrap()
        .to_string();
    assert!(d07.contains("<= 1e-9 for every k") && d07.contains("<= 1e-9 * max("));
    assert_eq!((assemble::VF_SUM_TOL, assemble::VF_RECIPROCITY_REL_TOL), (1e-9, 1e-9));
    assert!(p["equations"]["notation"].as_str().unwrap().contains("5.670374419e-8"));
    assert_eq!(abep_subsystems::thermal::network::SIGMA, 5.670374419e-8);
}

/// The empty credible Hall transport set is an expected governed state: asserted, never xfailed (A9.29 sec. 9).
#[test]
fn governed_state_read_by_the_gates() {
    let g = GovernedContext::load(&workspace_repo_root().unwrap()).unwrap();
    assert!(g.admitted_hall_members().is_empty(), "credible Hall transport set is EMPTY");
    assert_eq!(g.screening_candidates().len(), 9);
    assert_eq!(g.hallthruster_commit(), "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5");
    assert_eq!(g.design_state_ids().len(), 196);
    assert_eq!(g.flight_configuration(), "hall_icp_neutralizer");
    assert!(g.anode_candidate_ids().contains("CAND-01") && g.anode_candidate_ids().contains("CAND-16"));
    assert!(g.admitted_icp_producers().is_empty(), "NP-ICP-NEUTRALIZER is not admitted");
    assert!(!g.spacecraft_thermal_icd_registered(), "no host-spacecraft thermal ICD exists");
}

fn files(dir: &Path, out: &mut Vec<PathBuf>) {
    for e in std::fs::read_dir(dir).unwrap() {
        let p = e.unwrap().path();
        if p.is_dir() {
            files(&p, out);
        } else {
            out.push(p);
        }
    }
}

/// CI_PLAN principle 6 on this crate: no obsolete-architecture identifier; no load or component named heater; keeper
/// only inside the refusal vocabulary or exclusion statements. This file holds the scan list and is not scanned.
#[test]
fn forbidden_identifier_scan_of_this_crate() {
    let crate_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let mut all = Vec::new();
    files(crate_dir, &mut all);
    let exact = [
        "LaB6Cathode",
        "lab6_xe",
        "cathode_life",
        "XE_CATHODE",
        "hall_1stage",
        "mw_air",
        "rf_cathode",
        "CONTROL_FALLBACK",
    ];
    let me = Path::new(file!()).file_name().unwrap();
    let mut scanned = 0;
    for f in all {
        if f.file_name() == Some(me) || f.extension().is_none_or(|e| e != "rs" && e != "toml") {
            continue;
        }
        scanned += 1;
        let text = std::fs::read_to_string(&f).unwrap();
        for (n, line) in text.lines().enumerate() {
            let low = line.to_ascii_lowercase();
            for x in exact {
                assert!(!line.contains(x), "{}:{}: {x}", f.display(), n + 1);
            }
            assert!(!low.contains("heater"), "{}:{}: heater", f.display(), n + 1);
            if low.contains("keeper") {
                let t = line.trim_start();
                let allowed = t.starts_with("//") || line.contains("REFUSED_SUBSTRINGS");
                assert!(allowed, "{}:{}: keeper outside the refusal vocabulary", f.display(), n + 1);
            }
        }
    }
    assert!(scanned >= 10, "{scanned} files scanned");
}
