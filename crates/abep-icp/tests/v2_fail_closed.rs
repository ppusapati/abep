//! model_version 2 fail-closed tests FC-16 and FC-18..FC-30 (FC-14 / FC-17 / FC-21 / FC-28 sit with their analytic
//! cases in `v2_analytic.rs`), the real-mode cases of today (NE-01..NE-14) and the v2 lock. Missing evidence is
//! asserted as the fail-closed status, never skipped (A9.29 RM-OQ-05).

mod common;

use abep_icp::case::*;
use abep_icp::chemistry::ChemistryRegistration;
use abep_icp::v2::case::*;
use abep_icp::v2::cpl::{
    cpl_hall_on, CplInputs, HallMemberSource, ParametricHallPoint, SyntheticAdmittedHallStub, CPL_OUTPUT_KEYS,
};
use abep_icp::v2::evaluate::THERMAL_KEYS;
use abep_icp::v2::testkit::*;
use abep_icp::v2::validation::*;
use abep_icp::v2::{IcpModelV2, IcpResultV2};
use abep_icp::IcpStatus;
use common::model_v2;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

fn has(r: &IcpResultV2, code: &str) -> bool {
    r.reason_codes().contains(code)
}

fn n2_today() -> IcpCaseV2 {
    registered_today_case_v2(SupplyMode::EmN2, ChemistryRegistration::RegisteredSet { config_file: "n2_n.toml".into() })
}

fn all_cases() -> Vec<IcpCaseV2> {
    let mut v = vec![
        floating_case_v2(10.0),
        capoff_case_v2(30.0, 0.0, 30.0),
        capoff_case_v2(0.0, 0.0, 30.0),
        cal_case_v2(30.0, 3.0, 0.0, 30.0),
        disposition_case(Some((0.5, 0.2))),
        disposition_case(None),
        flow_case_v2(0.0, InflowV2::NoInflow, 0.5, 1e19, 300.0, 300.0),
        n2_today(),
        registered_today_case_v2(SupplyMode::AirPrimary, ChemistryRegistration::NotRegistered { gas: "AIR".into() }),
        registered_today_case_v2(SupplyMode::XeContingency, ChemistryRegistration::NotRegistered { gas: "XE".into() }),
    ];
    let mut h = capoff_case_v2(30.0, 0.0, 30.0);
    h.configuration = Configuration::FlightHallOn;
    v.push(h);
    v
}

// --------------------------------------------------------------------------------------------- lock / today

#[test]
fn the_v2_context_verifies_its_lock_its_predecessor_and_the_matched_key_table() {
    let m = model_v2();
    assert_eq!(m.prereg_lock_v2_sha256, abep_icp::v2::PREREG_LOCK_V2_SHA256);
    assert_eq!(m.key_table_sha256, abep_icp::v2::THERMAL_V2_KEY_TABLE_SHA256);
    assert_eq!(m.key_table.len(), THERMAL_KEYS.len());
    let table: BTreeSet<&str> = m.key_table.iter().map(|k| k.key.as_str()).collect();
    assert_eq!(table, THERMAL_KEYS.iter().copied().collect());
    // The v1 pins still verify inside the v2 context (v1 context unchanged).
    assert_eq!(m.v1.prereg_lock_sha256, abep_icp::IcpModel::load_workspace().unwrap().prereg_lock_sha256);
    // A changed byte of the v2 prereg is refused.
    let src = abep_provenance::workspace_repo_root().unwrap();
    let dst = Path::new(env!("CARGO_TARGET_TMPDIR")).join("abep_icp_v2_tamper");
    let _ = std::fs::remove_dir_all(&dst);
    let mut files: Vec<String> = m.v1.files_read.iter().map(|f| f.path.clone()).collect();
    files.extend(m.v2_files_read.iter().map(|f| f.path.clone()));
    files.push("config/MANIFEST.json".into());
    for f in files {
        let to = dst.join(&f);
        std::fs::create_dir_all(to.parent().unwrap()).unwrap();
        std::fs::copy(src.join(&f), &to).unwrap();
    }
    assert!(IcpModelV2::load(&dst).is_ok(), "the copied root loads");
    let p = dst.join(format!("{}/prereg_v2.json", abep_icp::context::PREREG_DIR));
    let mut b = std::fs::read(&p).unwrap();
    let i = b.iter().position(|c| *c == b'2').unwrap();
    b[i] = b'3';
    std::fs::write(&p, b).unwrap();
    assert!(IcpModelV2::load(&dst).is_err(), "a changed prereg_v2 byte must be refused");
}

#[test]
fn registered_today_every_mode_is_fail_closed_with_named_reasons() {
    let m = model_v2();
    let r = m.evaluate(&n2_today());
    assert_eq!(r.status, IcpStatus::IncompleteEvidence, "{:?}", r.reasons);
    for code in [
        "IN-10_GEOMETRY_NOT_REGISTERED",
        "IN-11_ELECTRODES_NOT_REGISTERED",
        "IN-12_NEUTRAL_SOURCE_NOT_REGISTERED",
        "DOM-06_B_ICP_NOT_REGISTERED",
        "IN-17_NO_EDGE_FACTOR_SOURCE",
    ] {
        assert!(has(&r, code), "{code} missing: {:?}", r.reason_codes());
    }
    assert!(r.solve_members.iter().all(|s| !s.status.is_converged()));
    assert_ne!(r.if_icp_thermal_v2.status, IcpStatus::Converged);
    assert!(r.if_icp_bus_v2.iter().all(|b| b.status == IcpStatus::NotEvaluated || !b.status.is_converged()));
    assert_eq!(r.if_icp_hall_v1.coupled_status, IcpStatus::NotEvaluated);
    for (mode, gas) in [(SupplyMode::AirPrimary, "AIR"), (SupplyMode::XeContingency, "XE")] {
        let r = m.evaluate(&registered_today_case_v2(mode, ChemistryRegistration::NotRegistered { gas: gas.into() }));
        assert!(!r.status.is_converged());
        assert_eq!(r.validation_status, "NOT_VALIDATED");
        assert_eq!(r.verification_status, "IMPLEMENTED_UNVERIFIED");
    }
}

// --------------------------------------------------------------------------------------------- FC-16

#[test]
fn fc16_thermal_v2_keys_are_full_records_with_the_registered_powered_by_and_no_hall_heat() {
    let m = model_v2();
    let row = |id: &str| m.key_table.iter().find(|k| k.id == id).unwrap().powered_by.clone();
    for id in ["TK-01", "TK-02", "TK-03", "TK-04", "TK-06", "TK-07", "TK-08", "TK-09", "TK-10", "TK-11"] {
        assert_eq!(row(id), "RF_SOURCE", "{id}");
    }
    assert_eq!(row("TK-05"), "ICP_MATCH_ACTUATOR");
    assert_eq!(row("TK-12"), "ICP_BIAS_SUPPLY");
    assert_eq!(row("TK-13"), "ICP_BIAS_SUPPLY");
    for c in all_cases() {
        let r = m.evaluate(&c);
        let t = &r.if_icp_thermal_v2;
        assert_eq!(t.interface, "IF-ICP-THERMAL-v2");
        assert_eq!(t.key_table_sha256, abep_icp::v2::THERMAL_V2_KEY_TABLE_SHA256);
        assert!(!t.members.is_empty());
        for mem in &t.members {
            let keys: BTreeSet<&str> = mem.keys.keys().map(String::as_str).collect();
            assert_eq!(keys, THERMAL_KEYS.iter().copied().collect(), "{}", c.case_id);
            for (k, v) in &mem.keys {
                assert_eq!(v.powered_by, m.key_row(k).unwrap().powered_by);
                // A full record: a value with CONVERGED, or no value with an explicit status and reason.
                assert!(
                    v.q.value.is_some() == v.q.status.is_converged()
                        || v.q.reasons.iter().any(|x| x.starts_with("NOT_DEFINED"))
                );
                if v.q.value.is_none() {
                    assert!(!v.q.reasons.is_empty(), "{}: {k} withheld without reason", c.case_id);
                }
            }
        }
        let json = serde_json::to_string(t).unwrap();
        for hall in ["Q_hall_return_to_icp_W\":", "Q_hall_plume_to_icp_W\":"] {
            assert!(!json.contains(hall), "{}: Hall-powered key emitted", c.case_id);
        }
    }
}

// --------------------------------------------------------------------------------------------- FC-18

#[test]
fn fc18_flight_ambient_without_exposure_model_is_incomplete_evidence() {
    let m = model_v2();
    let mut c = flow_case_v2(10.0, InflowV2::NoInflow, 0.5, 1e19, 300.0, 300.0);
    c.background = Some(syn(BackgroundV2::FlightAmbient { exposure_model_id: None }, "flight ambient"));
    let r = m.evaluate(&c);
    assert!(has(&r, "DOM-17_FLIGHT_AMBIENT_WITHOUT_EXPOSURE_MODEL"));
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    assert!(r.solve_members.iter().all(|s| !s.status.is_converged()));
}

// --------------------------------------------------------------------------------------------- FC-19

#[test]
fn fc19_retired_items_are_never_emitted_and_their_registration_is_refused() {
    let m = model_v2();
    for c in all_cases() {
        let json = m.evaluate(&c).to_json();
        for k in ["P_icp_bus_W", "Q_icp_rf_generator_loss_W", "Q_icp_bias_supply_loss_W"] {
            assert!(!json.contains(&format!("\"{k}\"")), "{}: {k} emitted", c.case_id);
        }
    }
    let mut c = cal_case_v2(30.0, 3.0, 0.0, 30.0);
    c.bus.as_mut().unwrap().eta_bias = Some(syn(0.9, "eta_bias"));
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(has(&r, "INPUT_RETIRED_V2:eta_bias"));
    let mut c = flow_case_v2(10.0, InflowV2::NoInflow, 0.5, 1e19, 300.0, 300.0);
    if let Some(NeutralSourceV2::FlowBalance { f_in, .. }) = &mut c.neutral_source {
        *f_in = Some(syn(1.0, "f_in"));
    }
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(has(&r, "INPUT_RETIRED_V2:f_in"));
    // H1_FACES is retired for v2 surfaces (H-1 receives ICP energy only via RX-H1-FACE).
    let mut c = capoff_case_v2(30.0, 0.0, 30.0);
    c.geometry.as_mut().unwrap().value.surfaces[3].thermal_node = abep_icp::geometry::ThermalNode::H1Faces;
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(has(&r, "IN-10_GEOMETRY_CONTRACT"));
}

// --------------------------------------------------------------------------------------------- FC-20

#[test]
fn fc20_cpl_hall_on_is_not_evaluated_and_names_every_missing_input() {
    let m = model_v2();
    assert_eq!(m.v1.ensemble_member_count, 0, "credible Hall transport set is EMPTY");
    let r = cpl_hall_on(m, &HallMemberSource::Ensemble, &CplInputs::default());
    assert_eq!(r.status, IcpStatus::NotEvaluated);
    assert!(r.reasons.iter().any(|x| x.code == "CREDIBLE_HALL_TRANSPORT_SET_EMPTY"));
    assert_eq!(r.configuration, "CFG-FLIGHT-HALL-ON");
    let stub =
        SyntheticAdmittedHallStub { member_id: "SYN".into(), i_d_a: Some(4.0), i_beam_a: None, v_d_v: Some(300.0) };
    let r = cpl_hall_on(m, &HallMemberSource::SyntheticAdmittedStub(&stub), &CplInputs::default());
    assert!(!r.status.is_converged());
    let codes: BTreeSet<&str> = r.reasons.iter().map(|x| x.code.as_str()).collect();
    for c in [
        "SYNTHETIC_TEST_ONLY",
        "HI-04_NO_PRODUCER",
        "HI-05_NO_PRODUCER",
        "HI-06_NO_PRODUCER",
        "HI-07_B_ICP_NOT_REGISTERED",
        "HI-08_CIRCUIT_TOPOLOGY_NOT_REGISTERED",
        "VER-24_EXTRACTION_BOUNDARY_LAW_UNVERIFIED",
    ] {
        assert!(codes.contains(c), "{c} missing");
    }
    assert_eq!(r.inputs["HI-02_I_beam_A"].reasons, ["HI-02_NOT_ON_MAP_POINT"]);
    // VER-23 is cleared by its verification addendum: no HALL_COUPLING_POTENTIAL_INPUT_UNVERIFIED; VER-24 stays open.
    assert!(!codes.iter().any(|c| c.starts_with("VER-23")));
    assert_eq!(r.verify_items, ["VER-24"]);
    // No beam / plume / coupling default exists: every output is withheld, whatever the stub carries.
    assert_eq!(r.outputs.len(), CPL_OUTPUT_KEYS.len());
    assert!(r.outputs.values().all(|q| q.value.is_none() && q.status == IcpStatus::NotEvaluated));
    let r = cpl_hall_on(
        m,
        &HallMemberSource::SyntheticAdmittedStub(&stub),
        &CplInputs { b_icp_t: Some(0.0), circuit_topology_record: Some("SYN-ICD".into()) },
    );
    assert!(r.outputs.values().all(|q| q.value.is_none()));
    // The case-level record in every evaluation is the gated ensemble record.
    for c in all_cases() {
        assert_eq!(m.evaluate(&c).cpl_hall_on_v1.status, IcpStatus::NotEvaluated);
    }
}

#[test]
fn cpl_hall_on_with_a_parametric_envelope_point_echoes_the_point_and_stays_gated() {
    // NP-HALL-PARAMETRIC-ENVELOPE addendum A2 P-CPL (R1): a PARAMETRIC / NOT_VALIDATED grid point is echoed with that
    // label; the gate stays closed and no output is produced (no beam / plume parameter is invented).
    let m = model_v2();
    let p = ParametricHallPoint {
        key: "XE|G|BZ|BP|VD|MF|T".into(),
        i_d_a: Some(3.0),
        i_beam_a: Some(2.4),
        v_d_v: Some(265.0),
    };
    let r = cpl_hall_on(m, &HallMemberSource::ParametricEnvelope(&p), &CplInputs::default());
    // Gated: HI-07 not registered is INCOMPLETE_EVIDENCE (the worst reason), never CONVERGED.
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    let codes: BTreeSet<&str> = r.reasons.iter().map(|x| x.code.as_str()).collect();
    for c in
        ["PARAMETRIC_ENVELOPE_POINT_NOT_VALIDATED", "HI-04_NO_PRODUCER", "VER-24_EXTRACTION_BOUNDARY_LAW_UNVERIFIED"]
    {
        assert!(codes.contains(c), "{c} missing");
    }
    assert!(!codes.contains("SYNTHETIC_TEST_ONLY"));
    for (k, v) in [("HI-01_I_d_A", 3.0), ("HI-02_I_beam_A", 2.4), ("HI-03_V_d_V", 265.0)] {
        assert_eq!(r.inputs[k].value, Some(v));
        assert_eq!(r.inputs[k].status, IcpStatus::NotEvaluated);
        assert_eq!(r.inputs[k].reasons, ["PARAMETRIC_NOT_VALIDATED"]);
    }
    assert!(r.outputs.values().all(|q| q.value.is_none() && q.status == IcpStatus::NotEvaluated));
    let p = ParametricHallPoint { i_beam_a: None, ..p };
    let r = cpl_hall_on(m, &HallMemberSource::ParametricEnvelope(&p), &CplInputs::default());
    assert_eq!(r.inputs["HI-02_I_beam_A"].reasons, ["HI-02_NOT_ON_MAP_POINT"]);
}

// --------------------------------------------------------------------------------------------- FC-22 / FC-27

fn partition() -> PartitionRecord {
    PartitionRecord {
        partition_id: "SYN-P".into(),
        records: [
            ("R1".to_string(), ("OP1".to_string(), Role::Cal)),
            ("R2".to_string(), ("OP2".to_string(), Role::Val)),
            ("R3".to_string(), ("OP3".to_string(), Role::Val)),
        ]
        .into(),
        measurands_calibrated: ["R_p".to_string()].into(),
        measurands_validated: ["I_e_cap".to_string()].into(),
        custody: vec!["SYN custody: raw files held by nobody; no value examined".into()],
        no_value_examined_before_freeze: true,
    }
}

fn point(rec: &str, op: &str, y_meas: f64) -> ComparisonPoint {
    ComparisonPoint {
        record_id: rec.into(),
        operating_point_id: op.into(),
        measurand: "I_e_cap".into(),
        cell_id: "CELL-1".into(),
        p_icp_measured: true,
        y_model: 1.0,
        u_input: 0.05,
        y_meas,
        u_meas: 0.1,
    }
}

#[test]
fn fc22_fc27_validation_needs_a_frozen_partition_and_measured_p_icp() {
    let p = partition();
    let h = p.sha256();
    assert!(p.violations().is_empty());
    let ok = compare(&point("R2", "OP2", 1.1), Some(&p), Some(&h));
    assert_eq!(ok.status, PointStatus::Consistent);
    assert!((ok.r_u.unwrap() - 0.5).abs() < 1e-15, "VC-03: r_u reported");
    // No partition, a changed partition, a record outside it, an operating point off-plan, a CAL record.
    let ne = |o: ComparisonOutcome, code: &str| {
        assert_eq!(o.status, PointStatus::NotEvaluated);
        assert!(o.z.is_none());
        assert!(o.reasons.iter().any(|x| x.starts_with(code)), "{code}: {:?}", o.reasons);
    };
    ne(compare(&point("R2", "OP2", 1.1), None, None), "IN-27_PARTITION_NOT_FROZEN");
    ne(compare(&point("R2", "OP2", 1.1), Some(&p), Some("0")), "IN-27_PARTITION_HASH_MISMATCH");
    ne(compare(&point("R9", "OP2", 1.1), Some(&p), Some(&h)), "FC-22_RECORD_OUTSIDE_PARTITION");
    ne(compare(&point("R2", "OP3", 1.1), Some(&p), Some(&h)), "FC-22_OPERATING_POINT_DIFFERS_FROM_PLAN");
    ne(compare(&point("R1", "OP1", 1.1), Some(&p), Some(&h)), "VC-08_CALIBRATION_RECORD_NOT_A_VALIDATION_POINT");
    let mut cal = point("R2", "OP2", 1.1);
    cal.measurand = "R_p".into();
    ne(compare(&cal, Some(&p), Some(&h)), "VC-08_CALIBRATED_MEASURAND");
    // FC-27 / DOM-15.
    let mut np = point("R2", "OP2", 1.1);
    np.p_icp_measured = false;
    ne(compare(&np, Some(&p), Some(&h)), "DOM-15_P_ICP_NOT_MEASURED");
    // VC-06: an operating point split across CAL and VAL makes the partition invalid.
    let mut split = partition();
    split.records.insert("R4".into(), ("OP2".into(), Role::Cal));
    assert!(!split.violations().is_empty());
    let hs = split.sha256();
    ne(compare(&point("R2", "OP2", 1.1), Some(&split), Some(&hs)), "VC-06_PARTITION_INVALID");
    // Cell status (VC-04 / VC-08): VALIDATED_BENCH only when every VAL record is compared and CONSISTENT.
    let o2 = (point("R2", "OP2", 1.1), compare(&point("R2", "OP2", 1.1), Some(&p), Some(&h)));
    let o3 = (point("R3", "OP3", 1.05), compare(&point("R3", "OP3", 1.05), Some(&p), Some(&h)));
    assert_eq!(
        cell_status("CELL-1", &p, std::slice::from_ref(&o2)),
        CellStatus::NotValidated,
        "a VAL record not compared"
    );
    assert_eq!(cell_status("CELL-1", &p, &[o2.clone(), o3.clone()]), CellStatus::ValidatedBench);
    let bad = (point("R3", "OP3", 2.0), compare(&point("R3", "OP3", 2.0), Some(&p), Some(&h)));
    assert_eq!(bad.1.status, PointStatus::Inconsistent);
    assert_eq!(cell_status("CELL-1", &p, &[o2.clone(), bad]), CellStatus::Inconsistent);
    let cal_only = (point("R1", "OP1", 1.0), compare(&point("R1", "OP1", 1.0), Some(&p), Some(&h)));
    assert_eq!(
        cell_status("CELL-1", &p, &[o2, o3, cal_only]),
        CellStatus::NotValidated,
        "a NOT_EVALUATED point blocks"
    );
    // No raw output ever carries VALIDATED_BENCH.
    let m = model_v2();
    for c in all_cases() {
        let r = m.evaluate(&c);
        assert_eq!(r.validation_status, "NOT_VALIDATED");
        assert!(!r.to_json().contains("VALIDATED_BENCH"));
    }
}

// --------------------------------------------------------------------------------------------- FC-23

#[test]
fn fc23_assumed_geometric_tube_is_flagged_and_refused_where_an_effective_volume_exists() {
    let m = model_v2();
    let r = m.evaluate(&floating_case_v2(10.0));
    assert!(r.flags.contains("ASSUMED_GEOMETRIC_TUBE"));
    assert_eq!(r.volume_mode.as_deref(), Some("ASSUMED_GEOMETRIC_TUBE"));
    let mut m2 = m.clone();
    m2.registered_effective_volumes.insert("SYNTHETIC_TUBE_V2".into());
    let r = m2.evaluate(&floating_case_v2(10.0));
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(has(&r, "DOM-16_REGISTERED_EFFECTIVE_VOLUME_EXISTS"));
    let mut c = floating_case_v2(10.0);
    c.geometry.as_mut().unwrap().value.volume_mode =
        VolumeModeV2::RegisteredEffective { volume_m3: 1e-4, record_id: "SYN-VEFF".into() };
    let r = m2.evaluate(&c);
    assert!(r.status.is_converged(), "{:?}", r.reasons);
    assert!(!r.flags.contains("ASSUMED_GEOMETRIC_TUBE"));
    assert_eq!(r.volume_mode.as_deref(), Some("REGISTERED_EFFECTIVE"));
}

// --------------------------------------------------------------------------------------------- FC-24

#[test]
fn fc24_flight_flow_balance_without_admitted_upstream_model_is_not_evaluated() {
    let m = model_v2();
    for mode in [SupplyMode::AirPrimary, SupplyMode::XeContingency] {
        let mut c = registered_today_case_v2(mode, ChemistryRegistration::NotRegistered { gas: "AIR".into() });
        c.neutral_source = Some(NeutralSourceV2::FlowBalance {
            t_g_k: syn(300.0, "T_g"),
            sigma_c_m2: BTreeMap::new(),
            inflow: InflowV2::UpstreamModel {
                model_id: "UPSTREAM-UNADMITTED".into(),
                gamma_in_per_s: syn(BTreeMap::new(), "Gamma_in"),
            },
            f_in: None,
        });
        let r = m.evaluate(&c);
        assert!(has(&r, "FLOW_BALANCE_UPSTREAM_MODEL_NOT_ADMITTED"), "{:?}", r.reason_codes());
        assert!(!r.status.is_converged());
    }
}

// --------------------------------------------------------------------------------------------- FC-25

#[test]
fn fc25_an_unbounded_omission_blocks_the_chemistry_dependent_outputs_of_its_mode() {
    let m = model_v2();
    let mut m2 = m.clone();
    m2.chemistry_screen.unbounded_omissions.push(("XE".into(), "SYN_PROCESS".into()));
    let xe =
        registered_today_case_v2(SupplyMode::XeContingency, ChemistryRegistration::NotRegistered { gas: "XE".into() });
    let r = m2.evaluate(&xe);
    assert!(has(&r, "CS-05_UNBOUNDED_OMISSION:SYN_PROCESS"));
    assert!(!r.status.is_converged());
    // Another mode is not touched by the XE omission.
    let air =
        registered_today_case_v2(SupplyMode::AirPrimary, ChemistryRegistration::NotRegistered { gas: "AIR".into() });
    assert!(!has(&m2.evaluate(&air), "CS-05_UNBOUNDED_OMISSION:SYN_PROCESS"));
}

// --------------------------------------------------------------------------------------------- FC-26

#[test]
fn fc26_every_output_carries_its_scenario_member_and_no_nominal_is_selected() {
    let m = model_v2();
    for c in all_cases() {
        let r = m.evaluate(&c);
        let solve_ids: BTreeSet<&str> = r.solve_members.iter().map(|s| s.solve_member_id.as_str()).collect();
        for mem in &r.if_icp_thermal_v2.members {
            assert!(solve_ids.contains(mem.solve_member_id.as_str()));
            assert!(mem.scenario_member_id.starts_with(&mem.solve_member_id));
        }
        for b in &r.if_icp_bus_v2 {
            assert!(solve_ids.contains(b.solve_member_id.as_str()));
        }
        let json = r.to_json();
        assert!(json.contains("\"validation_cell_id\""));
        for t in [["nomi", "nal"].concat(), ["HC", "-05"].concat(), ["mar", "gin"].concat(), ["GNG", "-ICP"].concat()] {
            assert!(!json.to_lowercase().contains(&t.to_lowercase()), "{}: output contains {t}", c.case_id);
        }
        for t in [["PA", "SS"].concat(), ["FA", "IL"].concat(), ["RF", "P"].concat()] {
            assert!(!json.contains(t.as_str()), "{}: output contains {t}", c.case_id);
        }
    }
}

// --------------------------------------------------------------------------------------------- FC-29

#[test]
fn fc29_missing_d0_withholds_the_partition_only() {
    let m = model_v2();
    let mut c = disposition_case(Some((0.5, 0.2)));
    c.dissociation_energies_ev.clear();
    let r = m.evaluate(&c);
    // A partition-only gate (as in v1): named on the IF-ICP-THERMAL-v2 record, not on the solve.
    assert!(
        r.if_icp_thermal_v2.reasons.iter().any(|x| x == "IN-25_D0_NOT_REGISTERED:X2"),
        "{:?}",
        r.if_icp_thermal_v2.reasons
    );
    assert_eq!(r.if_icp_thermal_v2.status, IcpStatus::IncompleteEvidence);
    assert_eq!(r.status, IcpStatus::Converged, "{:?}", r.reasons);
    let sm = &r.solve_members[0];
    assert_eq!(sm.status, IcpStatus::Converged, "the solve is unaffected: {:?}", sm.reasons);
    let cap = sm.outputs["I_e_cap_A"].scalar().unwrap();
    assert_eq!(cap.status, IcpStatus::Converged);
    for mem in &r.if_icp_thermal_v2.members {
        assert_eq!(mem.status, IcpStatus::IncompleteEvidence);
        for k in ["Q_icp_plasma_wall_W", "Q_icp_radiation_W", "Q_icp_outflow_upstream_W", "Q_icp_outflow_downstream_W"]
        {
            let q = &mem.keys[k].q;
            assert_eq!(q.status, IcpStatus::IncompleteEvidence, "{k}");
            assert!(q.reasons.iter().any(|x| x == "IN-25_D0_NOT_REGISTERED:X2"));
        }
    }
}

// --------------------------------------------------------------------------------------------- FC-30

#[test]
fn fc30_interface_ids_target_boundary_and_no_v1_or_cathode_or_rfp_constant() {
    let m = model_v2();
    for c in all_cases() {
        let r = m.evaluate(&c);
        assert_eq!(
            r.provenance.interface_ids,
            ["IF-ICP-THERMAL-v2", "IF-ICP-BUS-v2", "IF-ICP-HALL-v1", "IF-ICP-FEED-v1", "CPL-HALL-ON-v1"]
        );
        assert_eq!(r.model_version, "2");
        assert_eq!(r.provenance.prereg_lock_sha256, abep_icp::v2::PREREG_LOCK_V2_SHA256);
        for b in &r.if_icp_bus_v2 {
            assert_eq!(b.interface, "IF-ICP-BUS-v2");
            assert_eq!(b.target_boundary, "bus_power_boundary_a9_v2");
            // BUS2-01: plane on every key; only LOAD keys carry a slot.
            for k in b.keys.values() {
                assert_eq!(k.slot.is_some(), k.plane == "LOAD", "{}", k.id);
            }
            // BUS2-07: variant slots are full records (exact 0 NOT_INSTALLED unless a variant is declared).
            if c.bus.is_none() {
                for k in ["P_icp_assist_magnet_W", "P_icp_flow_control_W"] {
                    assert_eq!(b.keys[k].slot_state, "NOT_INSTALLED");
                    assert_eq!(b.keys[k].q.value, Some(0.0));
                }
            }
        }
        let json = r.to_json();
        for v1 in ["IF-ICP-BUS-v1", "IF-ICP-THERMAL-v1"] {
            assert!(!json.contains(v1), "{}: {v1} emitted by the v2 path", c.case_id);
        }
        assert!(!json.contains(&["c1", "_"].concat()), "{}: a C1 key", c.case_id);
        // BUS2-05: no cathode slot / key (the consumer's registered name NP-THERMAL-CATHODELESS is not a key).
        let mut keys: Vec<String> = r.if_icp_bus_v2.iter().flat_map(|b| b.keys.keys().cloned()).collect();
        keys.extend(r.if_icp_thermal_v2.members.iter().flat_map(|mm| mm.keys.keys().cloned()));
        keys.extend(r.if_icp_bus_v2.iter().flat_map(|b| b.keys.values().filter_map(|k| k.slot.clone())));
        assert!(keys.iter().all(|k| !k.to_lowercase().contains(&["cath", "ode"].concat())), "{}: {keys:?}", c.case_id);
    }
    // No RFP power-limit constant anywhere in abep-icp (assessment only; BUS2-06); tokens assembled at run time.
    let tokens = [["15", "00"].concat(), ["1.5", "e3"].concat(), ["1_", "500"].concat(), ["1.5 ", "kW"].concat()];
    let mut hits = Vec::new();
    fn scan(dir: &Path, tokens: &[String], hits: &mut Vec<String>) {
        for e in std::fs::read_dir(dir).unwrap() {
            let p = e.unwrap().path();
            if p.is_dir() {
                if p.file_name().is_some_and(|n| n != "target") {
                    scan(&p, tokens, hits);
                }
            } else if p.extension().is_some_and(|x| x == "rs" || x == "toml") {
                let text = std::fs::read_to_string(&p).unwrap();
                for t in tokens {
                    if text.contains(t.as_str()) {
                        hits.push(format!("{}: {t}", p.display()));
                    }
                }
            }
        }
    }
    scan(Path::new(env!("CARGO_MANIFEST_DIR")), &tokens, &mut hits);
    assert!(hits.is_empty(), "{hits:?}");
}

// --------------------------------------------------------------------------------------------- determinism

#[test]
fn nv01_v2_results_are_deterministic() {
    let m = model_v2();
    for c in all_cases() {
        assert_eq!(m.evaluate(&c).to_json(), m.evaluate(&c).to_json(), "{}", c.case_id);
    }
}

#[test]
fn verification_addendum_ver23_is_bound_to_the_pin() {
    let root = abep_provenance::workspace_repo_root().unwrap();
    let a: serde_json::Value = serde_json::from_slice(
        &std::fs::read(root.join(format!("{}/verification_addendum_ver23_v1.json", abep_icp::context::PREREG_DIR)))
            .unwrap(),
    )
    .unwrap();
    let pinned: toml::Table =
        std::fs::read_to_string(root.join("hallthruster_bridge/PINNED.toml")).unwrap().parse().unwrap();
    assert_eq!(a["verify_item"], "VER-23");
    assert_eq!(a["source"]["commit"].as_str(), pinned["hallthruster"]["commit"].as_str());
    assert!(a["confirmation"].as_str().unwrap().contains("VER-23 is CLEARED"));
    for f in a["source"]["files_read"].as_array().unwrap() {
        let h = f["sha256"].as_str().unwrap();
        assert!(h.len() == 64 && h.bytes().all(|b| b.is_ascii_hexdigit()), "{f}");
    }
}

#[test]
fn verification_addendum_ver25_is_bound_to_the_constant() {
    let root = abep_provenance::workspace_repo_root().unwrap();
    let a: serde_json::Value = serde_json::from_slice(
        &std::fs::read(root.join(format!("{}/verification_addendum_ver25_v1.json", abep_icp::context::PREREG_DIR)))
            .unwrap(),
    )
    .unwrap();
    assert_eq!(a["verify_item"], "VER-25");
    assert!(a["confirmation"].as_str().unwrap().contains("VER-25 is CLEARED"));
    assert!(a["read"]["source_line"].as_str().unwrap().contains("2022 CODATA"));
    let v = a["value_registered"]["value_F_per_m"].as_f64().unwrap();
    assert_eq!(v.to_bits(), abep_icp::v2::diagnostics::EPS0_CODATA2022.to_bits());
    let h = a["source"]["document_sha256"].as_str().unwrap();
    assert!(h.len() == 64 && h.bytes().all(|b| b.is_ascii_hexdigit()));
    // A sustained v2 solve no longer carries VER-25; the other inherited items stay on the path.
    let r = model_v2().evaluate(&floating_case_v2(10.0));
    assert!(r.status.is_converged(), "{:?}", r.reasons);
    assert!(!r.verify_items_on_path.contains("VER-25"));
    assert!(r.verify_items_on_path.contains("VER-01"));
}
