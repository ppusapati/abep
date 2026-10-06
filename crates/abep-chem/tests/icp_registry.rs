//! The IF-CHEM-REG-v1 registry `data/chemistry/icp/` (NP-ICP-CHEM-AIR v1 build plan BP-S1) on the real files: the
//! contract statuses, the reused tables and their direct-rate representations, the mirrored validity entries, the
//! fail-closed load rules (FC-CHEM-01, -03, -04, -05) and the Hall isolation check (FC-CHEM-10). Missing evidence is
//! asserted as its fail-closed status, never skipped.

use abep_chem::checked::{self, Validity};
use abep_chem::reference::{self, TailArg};
use abep_chem::registry::*;
use abep_chem::validity::RateValidityTable;
use abep_provenance::{read_verified, sha256_hex, workspace_repo_root};
use abep_types::{AbepError, EvalStatus};
use flate2::read::GzDecoder;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

const CHEM_AIR_PREREG: &str = "docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/prereg_v1.json";
const CAPTURE_DIR: &str = "docs/rust_migration/contracts/C-ABEP_SIM_RATE_TABLES_PY/reference_outputs";

fn root() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn registry() -> &'static IcpChemRegistry {
    static R: OnceLock<IcpChemRegistry> = OnceLock::new();
    R.get_or_init(|| IcpChemRegistry::load(&root(), ICP_CHEM_PINNED_SHA256).expect("the BP-S1 registry verifies"))
}

fn json(rel: &str) -> Value {
    serde_json::from_slice(&std::fs::read(root().join(rel)).unwrap()).unwrap()
}

fn contract_processes() -> Vec<Value> {
    json(CHEM_AIR_PREREG)["processes"].as_array().unwrap().clone()
}

#[test]
fn every_contract_process_with_its_recorded_status() {
    let r = registry();
    assert_eq!((r.air.label.as_str(), r.xe.label.as_str()), ("abep-icp-air-0.0", "abep-icp-xe-0.0"));
    assert_eq!((r.air.processes.len(), r.xe.processes.len()), (54, 10));
    for p in contract_processes() {
        let reg = r.mode(p["mode"].as_str().unwrap()).unwrap();
        let q = reg.process(p["id"].as_str().unwrap()).unwrap();
        assert_eq!(q.status.as_str(), p["status"].as_str().unwrap(), "{}", q.id);
        assert_eq!(q.tier, p["tier"].as_str().unwrap());
        assert_eq!(q.ca_verdict, "NOT_EVALUATED", "CA-ICP-v1 has not run");
    }
    let counts = |m: &ModeRegistry| {
        let mut c: BTreeMap<&str, usize> = BTreeMap::new();
        for p in &m.processes {
            *c.entry(p.status.as_str()).or_default() += 1;
        }
        c
    };
    let prereg = json(CHEM_AIR_PREREG);
    for (m, k) in [(&r.air, "AIR"), (&r.xe, "XE")] {
        let want = &prereg["process_status_counts"][k];
        for (s, n) in counts(m) {
            assert_eq!(want[s].as_u64(), Some(n as u64), "{k} {s}");
        }
    }
    // Neither mode is admitted; the tier-1 gaps are the contract's.
    assert_eq!(r.air.admission_status, "NOT_ADMITTED");
    assert_eq!(r.air.admission_reason_code, "NP_ICP_CHEM_AIR_NOT_ADMITTED");
    assert_eq!(r.xe.admission_reason_code, "NP_ICP_CHEM_AIR_XE_NOT_ADMITTED");
    let gaps: Vec<&str> = r.air.tier1_gaps().iter().map(|p| p.id.as_str()).collect();
    for id in
        ["AIR-ION-02", "AIR-ION-05", "AIR-DIS-02", "AIR-EXC-04", "AIR-EXC-05", "AIR-EXC-09", "AIR-EL-03", "AIR-EL-04"]
    {
        assert!(gaps.contains(&id), "{id}");
    }
    assert!(!gaps.contains(&"AIR-ION-01") && !gaps.contains(&"AIR-ION-03"));
    let xe: Vec<&str> = r.xe.tier1_gaps().iter().map(|p| p.id.as_str()).collect();
    assert_eq!(xe, vec!["XE-ION-01", "XE-EXC-01", "XE-EL-01", "XE-WALL-01"]);
    assert!(r.xe.channels.is_empty(), "no Xe data at BP-S1");
    assert_eq!(r.air.completeness_audit_status, "NOT_RUN");
    assert_eq!(r.air.neg_crit_status.as_deref(), Some("NOT_EVALUABLE"));
    let sb: Vec<(&str, &str)> = r.air.species_bounds.iter().map(|b| (b.id.as_str(), b.status.as_str())).collect();
    assert_eq!(sb, vec![("SB-He", "UNRESOLVED"), ("SB-Ar", "UNRESOLVED"), ("SB-NO", "UNRESOLVED")]);
    // D-CHEM.
    assert_eq!(r.air.domain.t_e_ev, [2.0, 30.0]);
    assert_eq!(r.air.domain.mean_energy_ev, [3.0, 45.0]);
    assert_eq!(r.air.domain.low_threshold_window_t_e_ev, [0.2, 30.0]);
}

#[test]
fn schema_required_fields_are_the_loader_lists() {
    let s = json("data/chemistry/icp/registry_schema_v1.json");
    let req = |v: &Value| -> Vec<String> {
        v["required"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_string()).collect()
    };
    let p = &s["properties"];
    for (got, want) in [
        (req(&s), REQUIRED_TOP),
        (req(&p["domain"]), REQUIRED_DOMAIN),
        (req(&p["admission"]), REQUIRED_ADMISSION),
        (req(&p["completeness_audit"]), REQUIRED_CA),
        (req(&p["neg_crit"]), REQUIRED_NEG_CRIT),
        (req(&p["species_bound"]["items"]), REQUIRED_SPECIES_BOUND),
        (req(&p["species"]["items"]), REQUIRED_SPECIES),
        (req(&p["process"]["items"]), REQUIRED_PROCESS),
        (req(&p["channel"]["items"]), REQUIRED_CHANNEL),
        (req(&p["variant_group"]["items"]), REQUIRED_VARIANT_GROUP),
        (req(&p["scenario"]["items"]), REQUIRED_SCENARIO),
        (req(&p["envelope"]["items"]), REQUIRED_ENVELOPE),
    ] {
        assert_eq!(got, want.iter().map(|x| x.to_string()).collect::<Vec<_>>());
    }
}

#[test]
fn the_reused_tables_their_representations_and_the_em_n2_scenario() {
    let r = registry();
    let pins = json(CHEM_AIR_PREREG)["reuse_pins"]["hall_propellant_tables"].as_array().unwrap().clone();
    assert_eq!(r.air.channels.len(), 43);
    let tables: BTreeSet<&str> = r.air.channels.iter().map(|c| c.table.as_str()).collect();
    let pinned: BTreeSet<&str> = pins.iter().map(|p| p["path"].as_str().unwrap()).collect();
    assert_eq!(tables, pinned, "one channel per reused table");
    let missing: Vec<&str> = r
        .air
        .channels
        .iter()
        .filter(|c| matches!(c.representation, Representation::NotRegistered { .. }))
        .map(|c| c.table_file())
        .collect();
    let mut want = vec!["ionization_N.dat".to_string()];
    want.extend((1..=10).map(|v| format!("excitation_N2_vib_0_to_{v}.dat")));
    assert_eq!(missing.iter().map(|s| s.to_string()).collect::<BTreeSet<_>>(), want.into_iter().collect());
    for c in &r.air.channels {
        assert!(matches!(c.validity, Validity::Verified { .. }), "{}", c.id);
        let p = r.air.process(&c.process).unwrap();
        assert_eq!(p.status, ProcessStatus::InRepoVerified, "{}: a reused channel of a verified process", c.id);
    }
    let sc = r.air.scenario("EM-N2-NOMINAL").unwrap();
    assert_eq!(sc.evidence_mode, "EM-N2");
    assert_eq!(sc.channels.len(), 29);
    let (cfg, cfg_sha) = sc.hall_config.as_ref().unwrap();
    assert_eq!(cfg, "hallthruster_bridge/propellants/n2_n.toml");
    let np = json("docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_v1.json");
    let parent_pin =
        np["evidence_records_used"].as_array().unwrap().iter().find(|e| e["path"] == cfg.as_str()).unwrap();
    assert_eq!(parent_pin["sha256"].as_str(), Some(cfg_sha.as_str()), "the parent's pin of the nominal N2/N set");
    // Ion formation energies come from the least-energy registered route (EQ-18; OBS-01 route spread 1.5e-4 eV).
    let eps = r.air.formation_energies();
    assert_eq!(eps["N^+"], 14.534);
    assert_eq!(eps["N2^+"], 15.58);
    assert!((eps["N^2+"] - (14.534 + 29.60125)).abs() < 1e-12);
}

fn capture() -> Value {
    let m: Value = json(&format!("{CAPTURE_DIR}/MANIFEST.json"));
    let gz = read_verified(
        &root().join(CAPTURE_DIR).join("inputs.json.gz"),
        m["files"]["inputs.json.gz"]["sha256"].as_str().unwrap(),
    )
    .unwrap();
    let mut t = String::new();
    GzDecoder::new(gz.as_slice()).read_to_string(&mut t).unwrap();
    serde_json::from_str(&t).unwrap()
}

#[test]
fn xs_representations_are_the_captured_points_and_render_the_frozen_tables() {
    let r = registry();
    let cap = capture();
    let by_file: BTreeMap<&str, &Value> =
        cap["registered_tables"].as_array().unwrap().iter().map(|t| (t["file"].as_str().unwrap(), t)).collect();
    let bits =
        |v: &Value| -> Vec<u64> { v.as_array().unwrap().iter().map(|x| x.as_f64().unwrap().to_bits()).collect() };
    let mut n = 0;
    for c in &r.air.channels {
        let Representation::CrossSection { xs, file, .. } = &c.representation else { continue };
        let t = by_file[c.table.as_str()];
        assert_eq!(xs.energies_ev().iter().map(|x| x.to_bits()).collect::<Vec<_>>(), bits(&t["E_eV"]), "{file}");
        assert_eq!(xs.sigma_m2().iter().map(|x| x.to_bits()).collect::<Vec<_>>(), bits(&t["sigma_m2"]), "{file}");
        assert_eq!(xs.tail().as_str(), t["tail"].as_str().unwrap(), "{file}");
        assert_eq!(c.threshold_ev, t["threshold_eV"].as_f64().unwrap(), "{file}");
        n += 1;
    }
    assert_eq!(n, 32);
    // End to end on three tables: registered points -> admitted integrator -> the frozen .dat, byte for byte.
    for stem in ["dissociation_N2", "ionization_N2_song2023", "excitation_N2_rot_j0_to_j2"] {
        let c = r.air.channels.iter().find(|c| c.table_file() == format!("{stem}.dat")).unwrap();
        let Representation::CrossSection { xs, .. } = &c.representation else { panic!("{stem}") };
        let label = by_file[c.table.as_str()]["header_label"].as_str().unwrap();
        let t = reference::hallthruster_table(
            xs.energies_ev(),
            xs.sigma_m2(),
            c.threshold_ev,
            300.0,
            &TailArg::from(xs.tail()),
            label,
            "",
        )
        .unwrap();
        let frozen = read_verified(&root().join(&c.table), &c.table_sha256).unwrap();
        assert_eq!(t.text.as_bytes(), frozen.as_slice(), "{stem}");
    }
}

#[test]
fn mirrored_validity_entries_equal_the_hall_entries() {
    let r = registry();
    let hall = RateValidityTable::load(
        &root().join("hallthruster_bridge/propellants/rate_validity.toml"),
        "64b51be96ef30d6024a99ad9bc0b47384ba3c2434a4c096403cc2b1aa0290e3a",
    )
    .unwrap();
    assert_eq!(r.validity.len(), 43);
    for f in r.validity.files() {
        assert_eq!(r.validity.validity(f), hall.validity(f), "{f}");
    }
    assert_eq!(r.validity.validity("dissociation_N2.dat"), Validity::Verified { max_mean_energy_ev: 45.0 });
    assert_eq!(
        r.validity.validity("ionization_N2_N2+.dat"),
        Validity::MissingEntry,
        "the unresolved shipped table is not used"
    );
}

#[test]
fn direct_rates_come_only_from_the_checked_integrator() {
    let r = registry();
    let ch = |f: &str| r.air.channel_for_table(f).unwrap();
    let ion = ch("ionization_N2_song2023.dat");
    let Representation::CrossSection { xs, .. } = &ion.representation else { panic!() };
    let k = r.air.direct_rate(ion, 5.0).unwrap();
    assert_eq!(k.k_m3_s.to_bits(), checked::maxwellian_rate(xs, 5.0, &ion.validity).unwrap().k_m3_s.to_bits());
    assert!(k.k_m3_s > 0.0);
    // Beyond the 45 eV mean-energy limit: OUT_OF_DOMAIN, never extrapolated (IX-05).
    let diss = ch("dissociation_N2.dat");
    assert!(r.air.direct_rate(diss, 30.0).is_ok());
    assert_eq!(r.air.direct_rate(diss, 30.0f64.next_up()).unwrap_err().status(), EvalStatus::OutOfDomain);
    // No registered representation: INCOMPLETE_EVIDENCE.
    for f in ["ionization_N.dat", "excitation_N2_vib_0_to_1.dat"] {
        let e = r.air.direct_rate(ch(f), 5.0).unwrap_err();
        assert_eq!(e.status(), EvalStatus::IncompleteEvidence, "{f}");
    }
}

/// FC-CHEM-10: the Hall chemistry files and physics_model_set_v1.json keep their bytes; every reuse pin matches.
#[test]
fn fc_chem_10_hall_chemistry_files_are_unchanged() {
    let rp = json("data/chemistry/icp/reuse_pins.json");
    let prereg = json(CHEM_AIR_PREREG);
    let frozen: BTreeMap<&str, &str> = prereg["evidence_records_used"]
        .as_array()
        .unwrap()
        .iter()
        .map(|e| (e["path"].as_str().unwrap(), e["sha256"].as_str().unwrap()))
        .collect();
    let files = rp["hall_isolation"]["files"].as_array().unwrap();
    let mut paths = BTreeSet::new();
    for f in files {
        let p = f["path"].as_str().unwrap();
        let s = f["sha256"].as_str().unwrap();
        read_verified(&root().join(p), s).unwrap_or_else(|e| panic!("FC-CHEM-10: {e}"));
        if let Some(w) = frozen.get(p) {
            assert_eq!(s, *w, "{p}: the record differs from the contract's frozen pin");
        }
        paths.insert(p.to_string());
    }
    for p in [
        "hallthruster_bridge/PINNED.toml",
        "hallthruster_bridge/propellants/rate_validity.toml",
        "hallthruster_bridge/audit/configs/MANIFEST.json",
        "config/model_set/physics_model_set_v1.json",
    ] {
        assert!(paths.contains(p) && frozen.contains_key(p), "{p}");
    }
    let mut configs: Vec<String> = std::fs::read_dir(root().join("hallthruster_bridge/propellants"))
        .unwrap()
        .map(|e| e.unwrap().file_name().into_string().unwrap())
        .filter(|n| n.starts_with("n2_n") && n.ends_with(".toml"))
        .map(|n| format!("hallthruster_bridge/propellants/{n}"))
        .collect();
    configs.sort();
    assert_eq!(configs.len(), 22);
    for c in &configs {
        assert!(paths.contains(c), "{c}: every n2_n*.toml is pinned");
    }
    for e in rp["hall_propellant_tables"].as_array().unwrap().iter().chain(rp["o_o2_v0_files"].as_array().unwrap()) {
        read_verified(&root().join(e["path"].as_str().unwrap()), e["sha256"].as_str().unwrap()).unwrap();
    }
    // No registry file lives under hallthruster_bridge/ (build plan location).
    for (p, _, _) in &registry().files_read {
        if p.starts_with("hallthruster_bridge/") {
            assert!(paths.contains(p) || p.ends_with(".dat") || p.ends_with(".dat.source"), "{p}");
        }
    }
}

/// A copy of every file the registry reads, under a fresh directory, with `edit` applied to one registry file and
/// ICP_CHEM_PINNED.toml re-pinned to it. Returns (root, pinned sha256).
fn edited_root(tag: &str, rel: &str, edit: &dyn Fn(String) -> String) -> (PathBuf, String) {
    let dst = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join(format!("icp_registry_{tag}"));
    let _ = std::fs::remove_dir_all(&dst);
    let mut files: Vec<String> = registry().files_read.iter().map(|f| f.0.clone()).collect();
    files.push(format!("{REGISTRY_DIR}/{PINNED_FILE}"));
    for f in files {
        let to = dst.join(&f);
        std::fs::create_dir_all(to.parent().unwrap()).unwrap();
        std::fs::copy(root().join(&f), &to).unwrap();
    }
    let path = dst.join(rel);
    let old = std::fs::read(&path).unwrap();
    let new = edit(String::from_utf8(old.clone()).unwrap());
    assert_ne!(new.as_bytes(), old.as_slice(), "{tag}: the edit changes the file");
    std::fs::write(&path, &new).unwrap();
    let pinned = dst.join(REGISTRY_DIR).join(PINNED_FILE);
    let text = std::fs::read_to_string(&pinned).unwrap().replace(&sha256_hex(&old), &sha256_hex(new.as_bytes()));
    std::fs::write(&pinned, &text).unwrap();
    (dst, sha256_hex(text.as_bytes()))
}

fn refused(tag: &str, rel: &str, edit: &dyn Fn(String) -> String, needle: &str) {
    let (dst, sha) = edited_root(tag, rel, edit);
    let e = IcpChemRegistry::load(&dst, &sha).expect_err(tag);
    assert_eq!(e.status(), EvalStatus::ModelError, "{tag}: {e}");
    assert!(e.to_string().contains(needle), "{tag}: {e}");
    let _ = std::fs::remove_dir_all(&dst);
}

#[test]
fn the_unedited_copy_loads() {
    let (dst, sha) = edited_root("identity", "data/chemistry/icp/reuse_pins.json", &|t| format!("{t}\n"));
    let r = IcpChemRegistry::load(&dst, &sha).unwrap();
    assert_eq!(r.air, registry().air);
    let _ = std::fs::remove_dir_all(&dst);
}

#[test]
fn fc_chem_01_a_table_without_a_validity_entry_is_model_error() {
    refused(
        "fc01",
        "data/chemistry/icp/rate_validity_icp.toml",
        &|t| {
            let start = t.find("[\"dissociation_N2.dat\"]").unwrap();
            let end = start + t[start..].find("\n\n").unwrap() + 2;
            format!("{}{}", &t[..start], &t[end..])
        },
        "FC-CHEM-01",
    );
    // A mirrored entry that differs from its Hall source.
    refused(
        "fc01m",
        "data/chemistry/icp/rate_validity_icp.toml",
        &|t| t.replacen("max_mean_energy_eV = 45.0", "max_mean_energy_eV = 60.0", 1),
        "differs from the entry it mirrors",
    );
}

#[test]
fn fc_chem_03_conservation_violations_are_model_errors() {
    let air = "data/chemistry/icp/registry_air.toml";
    let block = |t: &str, id: &str| -> (usize, usize) {
        let s = t.find(&format!("id = \"{id}\"")).unwrap();
        (s, s + t[s..].find("\n\n").unwrap())
    };
    refused(
        "fc03e",
        air,
        &|t| {
            let (s, e) = block(&t, "AIR-ION-03/ionization_N2_song2023");
            format!("{}{}{}", &t[..s], t[s..e].replace("electrons_out = 2", "electrons_out = 1"), &t[e..])
        },
        "charge not conserved",
    );
    refused(
        "fc03n",
        air,
        &|t| {
            let (s, e) = block(&t, "AIR-DIS-01/dissociation_N2");
            format!("{}{}{}", &t[..s], t[s..e].replace("{ \"N\" = 2 }", "{ \"N\" = 1, \"N2\" = 1 }"), &t[e..])
        },
        "nuclei not conserved",
    );
}

#[test]
fn fc_chem_04_changed_pins_are_model_errors() {
    // A changed Hall byte breaks the pin.
    let (dst, sha) = edited_root("fc04", "data/chemistry/icp/reuse_pins.json", &|t| format!("{t}\n"));
    let tbl = dst.join("hallthruster_bridge/propellants/ionization_N2_song2023.dat");
    let mut b = std::fs::read(&tbl).unwrap();
    b.push(b'\n');
    std::fs::write(&tbl, b).unwrap();
    let e = IcpChemRegistry::load(&dst, &sha).unwrap_err();
    assert!(matches!(e, AbepError::HashMismatch { .. }), "{e}");
    let _ = std::fs::remove_dir_all(&dst);
    // Reuse pins that differ from the contract's.
    refused(
        "fc04p",
        "data/chemistry/icp/reuse_pins.json",
        &|t| t.replacen("fb78ba1d30ec0d88a13e992df7749591f65af5770e973e3696a7a932705eb7fc", &"0".repeat(64), 1),
        "RU-02",
    );
    // A registry pinned at the wrong sha256.
    let e = IcpChemRegistry::load(&root(), &"0".repeat(64)).unwrap_err();
    assert!(matches!(e, AbepError::HashMismatch { .. }));
}

#[test]
fn fc_chem_05_atomic_o_is_never_a_surrogate() {
    let air = "data/chemistry/icp/registry_air.toml";
    refused(
        "fc05t",
        air,
        &|t| {
            let s = t.find("id = \"AIR-EL-04\"").unwrap();
            let e = s + t[s..].find("\n\n").unwrap();
            format!("{}{}{}", &t[..s], t[s..e].replace("target = \"O\"", "target = \"N2\""), &t[e..])
        },
        "FC-CHEM-05",
    );
    refused(
        "fc05d",
        air,
        &|t| t.replacen("target = \"N\"\ndata_target = \"N\"", "target = \"N\"\ndata_target = \"N2\"", 1),
        "FC-CHEM-05",
    );
}

#[test]
fn a_status_upgrade_or_a_missing_process_is_model_error() {
    let air = "data/chemistry/icp/registry_air.toml";
    refused(
        "upgrade",
        air,
        &|t| {
            let s = t.find("id = \"AIR-EXC-09\"").unwrap();
            let e = s + t[s..].find("\n\n").unwrap();
            format!("{}{}{}", &t[..s], t[s..e].replace("SOURCE_IDENTIFIED_TO_ACQUIRE", "IN_REPO_VERIFIED"), &t[e..])
        },
        "differs from the contract",
    );
    refused(
        "drop",
        air,
        &|t| {
            let s = t.find("[[process]]\nid = \"AIR-HN-01\"").unwrap();
            let e = s + t[s..].find("\n\n").unwrap() + 2;
            format!("{}{}", &t[..s], &t[e..])
        },
        "exactly the contract's",
    );
}

#[test]
fn files_read_are_pinned() {
    let r = registry();
    for (p, s, by) in &r.files_read {
        read_verified(&root().join(p), s).unwrap();
        assert!(!by.is_empty(), "{p}");
        assert!(!Path::new(p).is_absolute());
    }
    assert_eq!(r.contract_lock_sha256, CONTRACT_LOCK_SHA256);
}
