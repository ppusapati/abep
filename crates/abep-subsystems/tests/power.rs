//! SC-WP-05 power layer on the real tree: today's flight state fails closed, the IF-ICP-BUS-v1 consumer and the
//! impedance-map gate propagate absent evidence, the flight taxonomy equals the pinned boundary record (INV-A04), the
//! RFP gate is not in this crate (INV-A05) and the mass/power record is hash-pinned (DIV-A06).

use abep_provenance::workspace_repo_root;
use abep_subsystems::power::cplx::C;
use abep_subsystems::power::demand::{bus_demand, Efficiency, FlightInputs, SupplyPath, Upstream};
use abep_subsystems::power::icp_bus::icp_upstream_loads;
use abep_subsystems::power::ledger::LedgerStatus;
use abep_subsystems::power::official::{official_flight_ledger, MassPowerA9V5, MASS_POWER_REL};
use abep_subsystems::power::rf_match::{rf_chain_status, ImpedanceMapPoint};
use abep_subsystems::power::slots::{Slot, BASE_SLOTS, DEPENDENT_RISES, ENFORCED_ORDER, PEAK_EVENTS, VARIANT_OPTIONS};
use abep_types::EvalStatus;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

fn mp() -> MassPowerA9V5 {
    MassPowerA9V5::load(&workspace_repo_root().unwrap()).unwrap()
}

fn known(p: f64) -> Upstream {
    Upstream::Evaluated { p_w: p, evidence_class: "assumed".into(), source: "SYNTHETIC_TEST_DATA_NOT_EVIDENCE".into() }
}

fn eff(v: f64) -> (Efficiency, SupplyPath) {
    (
        Efficiency::Known {
            value: v,
            evidence_class: "assumed".into(),
            source: "SYNTHETIC_TEST_DATA_NOT_EVIDENCE".into(),
        },
        SupplyPath::InternalBus,
    )
}

fn flight_inputs(hall: Upstream, compressor: Upstream) -> FlightInputs {
    let mut loads = BTreeMap::new();
    let mut effs = BTreeMap::new();
    for s in BASE_SLOTS {
        let up = match s {
            Slot::HallDischarge => hall.clone(),
            Slot::Compressor => compressor.clone(),
            _ => known(5.0),
        };
        loads.insert(s, up);
        effs.insert(s, eff(0.9));
    }
    FlightInputs {
        variant: vec![],
        loads,
        efficiencies: effs,
        front_end: Efficiency::Known { value: 0.95, evidence_class: "assumed".into(), source: "synthetic".into() },
        label: "test".into(),
        power_basis: None,
    }
}

#[test]
fn official_flight_ledger_is_partial_boundary_with_every_term_tbd() {
    let led = official_flight_ledger(&mp()).unwrap();
    assert_eq!(led.status, LedgerStatus::PartialBoundary);
    assert_eq!(led.status.eval_status(), EvalStatus::IncompleteEvidence);
    assert_eq!(led.p_bus_w, None);
    assert_eq!(led.p_bus_lower_bound_w, 0.0);
    assert_eq!(led.tbd.len(), 24);
    assert!(led.items.iter().all(|it| it.slot.group().name() != "c1"));
    let reserved = led.item(Slot::ReservedDcPort);
    assert_eq!((reserved.p_w, reserved.evidence_class.as_deref()), (Some(0.0), Some("assumed")));
}

#[test]
fn ledger_with_loads_replaces_only_the_named_tbd_loads() {
    use abep_subsystems::power::official::{ledger_with_loads, official_ledger, LoadOverride};
    let m = mp();
    let ov = |slot: Slot, p: f64| LoadOverride {
        slot,
        p_w: p,
        evidence_class: "model-derived".into(),
        source: "SYNTHETIC_TEST_DATA_NOT_EVIDENCE".into(),
    };
    // official_ledger with a compressor draw is ledger_with_loads with that one override.
    let a = official_ledger(&m, "hall_icp_neutralizer", Some(11.0), "src").unwrap();
    let mut o = ov(Slot::Compressor, 11.0);
    o.source = "src".into();
    let b = ledger_with_loads(&m, "hall_icp_neutralizer", &[o], "PARAMETRIC_SENSITIVITY").unwrap();
    assert_eq!(a, b);
    let led = ledger_with_loads(&m, "hall_icp_neutralizer", &[ov(Slot::IcpRfSource, 40.0)], "L").unwrap();
    assert_eq!(led.item(Slot::IcpRfSource).p_w, Some(40.0));
    // TBD efficiency -> lower bound uses 1 (favorable); the load term leaves the TBD list, its efficiency stays.
    assert_eq!(led.item(Slot::IcpRfSource).lower_bound_w, Some(40.0));
    assert!(!led.tbd.iter().any(|t| t.slot == Slot::IcpRfSource && t.what == "load"));
    assert!(led.tbd.iter().any(|t| t.slot == Slot::IcpRfSource && t.what == "efficiency"));
    // Fail closed: the reserved port and a slot that is not installed cannot be overridden.
    assert!(ledger_with_loads(&m, "hall_icp_neutralizer", &[ov(Slot::ReservedDcPort, 1.0)], "L").is_err());
    assert!(ledger_with_loads(&m, "hall_icp_neutralizer", &[ov(Slot::IcpAssistMagnet, 1.0)], "L").is_err());
}

#[test]
fn bus_demand_fails_closed_on_absent_upstream_inputs() {
    let hall = Upstream::Absent {
        status: EvalStatus::NotEvaluated,
        reason: "credible Hall transport set EMPTY: no admitted member, no Hall map".into(),
    };
    let comp = Upstream::Absent { status: EvalStatus::IncompleteEvidence, reason: "compressor ICD row 22".into() };
    let d = bus_demand(&flight_inputs(hall, comp)).unwrap();
    assert_eq!(d.status, EvalStatus::NotEvaluated);
    assert_eq!(d.ledger.status, LedgerStatus::PartialBoundary);
    assert_eq!(d.p_bus_w, None);
    assert!(d.ledger.tbd.iter().any(|t| t.slot == Slot::HallDischarge && t.requires.starts_with("NOT_EVALUATED")));

    let ok = bus_demand(&flight_inputs(known(600.0), known(40.0))).unwrap();
    assert_eq!(ok.status, EvalStatus::Evaluated);
    let p = ok.p_bus_w.unwrap();
    let expect = (600.0 + 40.0 + 11.0 * 5.0) / 0.9 / 0.95;
    assert!((p - expect).abs() < 1e-9 * expect, "{p} vs {expect}");
}

fn icp_record(status: &str) -> Value {
    let q = |v: f64| json!({"value": v, "unit": "W", "status": "CONVERGED", "reasons": []});
    let mut keys = serde_json::Map::new();
    keys.insert("P_icp_rf_source_DC_W".into(), q(45.0));
    keys.insert("P_icp_matching_DC_W".into(), q(2.0));
    keys.insert(
        "P_icp_collector_bias_W".into(),
        if status == "CONVERGED" {
            q(6.4)
        } else {
            json!({"value": null, "unit": "W", "status": status, "reasons": ["NE-09_FLIGHT_ETA_RF_ETA_BIAS_PENDING"]})
        },
    );
    keys.insert("P_icp_assist_magnet_W".into(), q(0.0));
    keys.insert("P_icp_flow_control_W".into(), q(0.0));
    json!({"interface": "IF-ICP-BUS-v1", "target_boundary": "bus_power_boundary_a9_v2", "keys": keys,
           "slots": {}, "checks": [], "status": "CONVERGED", "reasons": []})
}

#[test]
fn icp_bus_interface_maps_converged_keys_and_propagates_absence() {
    let src = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE IF-ICP-BUS-v1 record";
    let loads = icp_upstream_loads(&icp_record("CONVERGED"), &[], "model-derived", src).unwrap();
    let slots: Vec<Slot> = loads.iter().map(|(s, _)| *s).collect();
    assert_eq!(slots, vec![Slot::IcpRfSource, Slot::IcpMatchingNetwork, Slot::IcpCollectorBias]);
    assert!(matches!(loads[2].1, Upstream::Evaluated { p_w, .. } if p_w == 6.4));

    let with_variant =
        icp_upstream_loads(&icp_record("CONVERGED"), &[Slot::IcpAssistMagnet], "model-derived", src).unwrap();
    assert_eq!(with_variant.len(), 4);

    let ne = icp_upstream_loads(&icp_record("NOT_EVALUATED"), &[], "model-derived", src).unwrap();
    match &ne[2].1 {
        Upstream::Absent { status, reason } => {
            assert_eq!(*status, EvalStatus::NotEvaluated);
            assert!(reason.contains("NE-09_FLIGHT_ETA_RF_ETA_BIAS_PENDING"));
        }
        other => panic!("{other:?}"),
    }

    let mut bad = icp_record("CONVERGED");
    bad["interface"] = json!("IF-ICP-THERMAL-v1");
    assert_eq!(icp_upstream_loads(&bad, &[], "model-derived", src).unwrap_err().status, EvalStatus::ModelError);
    let mut v1 = icp_record("CONVERGED");
    v1["target_boundary"] = json!("bus_power_boundary_v1");
    assert!(icp_upstream_loads(&v1, &[], "model-derived", src).is_err());
    let mut missing = icp_record("CONVERGED");
    missing["keys"].as_object_mut().unwrap().remove("P_icp_matching_DC_W");
    assert!(icp_upstream_loads(&missing, &[], "model-derived", src).is_err());
    let mut null = icp_record("CONVERGED");
    null["keys"]["P_icp_rf_source_DC_W"]["value"] = Value::Null;
    assert!(icp_upstream_loads(&null, &[], "model-derived", src).is_err());
    assert!(icp_upstream_loads(&icp_record("CONVERGED"), &[], "cbe", src).is_err());
}

#[test]
fn matched_rf_chain_is_not_evaluated_without_a_measured_impedance_map() {
    let none = rf_chain_status(None);
    assert_eq!(none.status, EvalStatus::NotEvaluated);
    assert!(none.reason.starts_with("TBD_AFTER_IMPEDANCE_MAP"));
    let id = [C::real(1.0), C::new(0.5, 0.0), C::real(0.0), C::real(1.0)];
    let mut p = ImpedanceMapPoint {
        abcd: id,
        z_load_ohm: C::new(50.0, 0.0),
        evidence_class: "measured".into(),
        source: "SYNTHETIC_TEST_DATA_NOT_EVIDENCE".into(),
    };
    let ok = rf_chain_status(Some(&p));
    assert_eq!(ok.status, EvalStatus::Evaluated);
    assert!((ok.transfer_efficiency.unwrap() - 50.0 / 50.5).abs() < 1e-15);
    p.evidence_class = "assumed".into();
    assert_eq!(rf_chain_status(Some(&p)).status, EvalStatus::IncompleteEvidence);
}

fn read_json(rel: &str) -> Value {
    serde_json::from_slice(&std::fs::read(workspace_repo_root().unwrap().join(rel)).unwrap()).unwrap()
}

/// INV-A04: the flight taxonomy equals the pinned boundary record without its ground-reference rows.
#[test]
fn flight_taxonomy_equals_the_boundary_record() {
    let rel = "docs/architecture_comparison/power_boundary_a9_v2/bus_power_boundary_a9_v2.json";
    let root = workspace_repo_root().unwrap();
    assert_eq!(
        abep_provenance::sha256_file(&root.join(rel)).unwrap(),
        "de346f86f77ae08c2e0cc4a5b945c21c9626bc5ad0f32f904acd4a929a08f980"
    );
    let doc = read_json(rel);
    assert_eq!(doc["configurations"], json!(["hall_icp_neutralizer"]));
    let opts: Vec<&str> = VARIANT_OPTIONS.iter().map(|s| s.name()).collect();
    assert_eq!(doc["variant_options"]["hall_icp_neutralizer"], json!(opts));
    let rows: Vec<&Value> = doc["slots"].as_array().unwrap().iter().filter(|r| r["group"] != "c1").collect();
    assert_eq!(rows.len(), Slot::ALL.len());
    for (row, s) in rows.iter().zip(Slot::ALL) {
        assert_eq!(row["slot"], s.name());
        assert_eq!(row["group"], s.group().name());
        assert_eq!(row["rows"], json!(s.rows()));
        assert_eq!(row["common_allocation"], s.common_allocation());
        assert_eq!(row["controls_thermal"], s.controls_thermal());
        let cfg = if BASE_SLOTS.contains(&s) { "INSTALLED" } else { "VARIANT_ONLY" };
        assert_eq!(row["configurations"]["hall_icp_neutralizer"], cfg, "{}", s.name());
    }
    let ground: Vec<String> = doc["slots"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|r| r["group"] == "c1")
        .map(|r| r["slot"].as_str().unwrap().to_string())
        .collect();
    let pe = doc["sequencing"]["peak_events"].as_object().unwrap();
    let flight: Vec<(&String, &Value)> =
        pe.iter().filter(|(_, v)| !ground.iter().any(|g| v.as_str() == Some(g.as_str()))).collect();
    assert_eq!(flight.len(), PEAK_EVENTS.len());
    for (de, ds) in PEAK_EVENTS {
        assert_eq!(pe[de], ds.name(), "{de}");
    }
    let order: Vec<[&str; 2]> = ENFORCED_ORDER.iter().map(|(a, b)| [*a, *b]).collect();
    assert_eq!(doc["sequencing"]["enforced_order"]["hall_icp_neutralizer"], json!(order));
    assert_eq!(DEPENDENT_RISES[0].0, "hall_discharge_ignition");
}

fn rs_files(dir: &Path, out: &mut Vec<PathBuf>) {
    for e in std::fs::read_dir(dir).unwrap() {
        let p = e.unwrap().path();
        if p.is_dir() {
            rs_files(&p, out);
        } else if p.extension().is_some_and(|x| x == "rs") {
            out.push(p);
        }
    }
}

/// INV-A05: no RFP gate in the physics crate, and its resolved dependency graph holds no assessment, evidence or
/// ground-test crate.
#[test]
fn rfp_gate_is_not_in_the_physics_crate() {
    let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
    let mut files = Vec::new();
    rs_files(&src, &mut files);
    for f in &files {
        let text = std::fs::read_to_string(f).unwrap();
        for bad in ["rfp_power_gate", "P_BUS_REQUIREMENT", "1500"] {
            assert!(!text.contains(bad), "{}: {bad}", f.display());
        }
    }
    let root = workspace_repo_root().unwrap();
    let out = std::process::Command::new(env!("CARGO"))
        .args(["metadata", "--format-version", "1", "--locked", "--offline"])
        .current_dir(&root)
        .output()
        .expect("cargo metadata");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    let meta: Value = serde_json::from_slice(&out.stdout).unwrap();
    let pkgs = meta["packages"].as_array().unwrap();
    let name_of = |id: &str| pkgs.iter().find(|p| p["id"] == id).map(|p| p["name"].as_str().unwrap().to_string());
    let nodes = meta["resolve"]["nodes"].as_array().unwrap();
    let start = pkgs.iter().find(|p| p["name"] == "abep-subsystems").unwrap()["id"].as_str().unwrap().to_string();
    let mut stack = vec![start.clone()];
    let mut seen: Vec<String> = Vec::new();
    while let Some(id) = stack.pop() {
        if seen.contains(&id) {
            continue;
        }
        seen.push(id.clone());
        let node = nodes.iter().find(|n| n["id"] == id.as_str()).unwrap();
        for d in node["dependencies"].as_array().unwrap() {
            stack.push(d.as_str().unwrap().to_string());
        }
    }
    let names: Vec<String> = seen.iter().filter_map(|i| name_of(i)).collect();
    for forbidden in ["abep-assess", "abep-evidence", "abep-groundtest"] {
        assert!(!names.iter().any(|n| n == forbidden), "{forbidden} reachable from abep-subsystems");
    }
    let node = nodes.iter().find(|n| n["id"] == start.as_str()).unwrap();
    let mut direct: Vec<String> = node["dependencies"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|d| name_of(d.as_str().unwrap()))
        .filter(|n| n.starts_with("abep"))
        .collect();
    direct.sort();
    // SC-WP-08 (materials / life) added the admitted data / Hall-gate crates; both are physics-layer crates.
    let want = ["abep-data", "abep-hall", "abep-provenance", "abep-types"];
    assert_eq!(direct, want.iter().map(|s| s.to_string()).collect::<Vec<_>>());
}

/// DIV-A06: the mass/power record is read only with its registered sha256.
#[test]
fn mass_power_record_is_hash_pinned() {
    let root = workspace_repo_root().unwrap();
    let tmp = std::env::temp_dir().join(format!("abep_power_pin_{}", std::process::id()));
    let target = tmp.join(MASS_POWER_REL);
    std::fs::create_dir_all(target.parent().unwrap()).unwrap();
    let mut bytes = std::fs::read(root.join(MASS_POWER_REL)).unwrap();
    bytes.push(b'\n');
    std::fs::write(&target, bytes).unwrap();
    let e = MassPowerA9V5::load(&tmp).unwrap_err();
    assert_eq!(e.status, EvalStatus::ModelError);
    assert!(e.message.contains("sha256"), "{}", e.message);
    std::fs::remove_dir_all(&tmp).unwrap();
}
