//! Fail-closed tests FC-01..FC-16 (prereg `fail_closed_tests`), the A9.30 gate G-A930-AIR with the NP-ICP-CHEM-AIR
//! registry, and the paths this implementation withholds because the preregistration does not define them. Missing
//! evidence is asserted as the fail-closed status, never skipped (A9.29 RM-OQ-05).

mod common;

use abep_icp::case::*;
use abep_icp::chemistry::{ChemistryRegistration, RateSource, ReactionDef, ReactionKind, Validity};
use abep_icp::constants::NumericalSettings;
use abep_icp::constants::NUMERICS;
use abep_icp::evidence::Registered;
use abep_icp::geometry::HModel;
use abep_icp::testkit::*;
use abep_icp::{IcpCase, IcpResult, IcpStatus};
use common::{model, val};
use std::collections::BTreeMap;
use std::path::Path;

fn n2_today() -> IcpCase {
    registered_today_case(SupplyMode::EmN2, ChemistryRegistration::RegisteredSet { config_file: "n2_n.toml".into() })
}

fn has(r: &IcpResult, code: &str) -> bool {
    r.reason_codes().contains(code)
}

fn set_of(c: &mut IcpCase) -> &mut abep_icp::chemistry::ChemistrySet {
    match &mut c.chemistry {
        ChemistryRegistration::Synthetic { set } => set,
        _ => panic!("synthetic case expected"),
    }
}

#[test]
fn fc01_fc02_hall_interface_not_evaluated_with_both_reasons() {
    let m = model();
    assert_eq!(m.ensemble_member_count, 0, "credible Hall transport set is EMPTY");
    for c in [capoff_case(50.0, 0.0, 30.0), n2_today()] {
        let h = m.evaluate(&c).if_icp_hall_v1;
        assert_eq!(h.i_d_max_h1_a.status, IcpStatus::NotEvaluated);
        assert!(h.i_d_max_h1_a.reasons.contains(&"CREDIBLE_HALL_TRANSPORT_SET_EMPTY".to_string()));
        assert!(h.i_d_max_h1_a.reasons.contains(&"I_D_MAX_H1_NOT_REGISTERED".to_string()));
        assert_ne!(h.coupled_status, IcpStatus::Converged);
    }
    // An admitted-member registration cannot exist while the set is empty; screening candidates and the stand rating
    // are refused; a measured registration (P1-IT-07) forms the pair, never a ratio.
    let mut c = capoff_case(50.0, 0.0, 30.0);
    for (basis, status, code) in [
        (HallDemandBasis::AdmittedHallMember, IcpStatus::NotEvaluated, "CREDIBLE_HALL_TRANSPORT_SET_EMPTY"),
        (HallDemandBasis::ScreeningCandidate, IcpStatus::ModelError, "IF-ICP-HALL-v1_SCREENING_CANDIDATE_REFUSED"),
        (HallDemandBasis::SupplyRating, IcpStatus::ModelError, "IF-ICP-HALL-v1_SUPPLY_RATING_REFUSED"),
    ] {
        c.hall_demand = Some(HallDemand { i_d_max_h1_a: syn(5.0, "I_d,max"), basis, h1_point_id: "P".into() });
        let h = m.evaluate(&c).if_icp_hall_v1;
        assert_eq!(h.i_d_max_h1_a.status, status, "{basis:?}");
        assert!(h.coupled_reasons.contains(&code.to_string()), "{basis:?}: {:?}", h.coupled_reasons);
    }
    c.hall_demand = Some(HallDemand {
        i_d_max_h1_a: syn(5.0, "I_d,max"),
        basis: HallDemandBasis::MeasuredRegistration,
        h1_point_id: "P".into(),
    });
    let r = m.evaluate(&c);
    let h = &r.if_icp_hall_v1;
    assert_eq!(h.coupled_status, IcpStatus::Converged);
    assert_eq!(h.i_d_max_h1_a.value, Some(5.0));
    assert!(h.i_e_cap_a.value.is_some());
    // The interface carries the pair and its context only: no ratio, margin or verdict field.
    let v = serde_json::to_value(h).unwrap();
    let keys: Vec<&str> = v.as_object().unwrap().keys().map(String::as_str).collect();
    assert_eq!(
        keys,
        vec![
            "binding_limit",
            "configuration",
            "coupled_reasons",
            "coupled_status",
            "coupling_mode",
            "h1_point_id",
            "i_d_max_h1_a",
            "i_d_max_h1_basis",
            "i_e_cap_a",
            "i_e_sat_a",
            "interface",
            "supply_mode",
            "uncertainty",
            "validation_status",
        ]
    );
    assert!(!serde_json::to_string(h).unwrap().contains("M_n"));
}

#[test]
fn fc03_flight_hall_on_is_not_evaluated() {
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.configuration = Configuration::FlightHallOn;
    let r = model().evaluate(&c);
    assert_eq!(r.status, IcpStatus::NotEvaluated);
    assert!(has(&r, "IN-21_HALL_ON_EXHAUST_NOT_EVALUATED") && has(&r, "CREDIBLE_HALL_TRANSPORT_SET_EMPTY"));
    let out07 = r.scalar("I_e_neutralization_available_A");
    assert_eq!(out07.status, IcpStatus::NotEvaluated);
    assert!(out07.value.is_none());
    for k in ["I_e_cap_A", "I_e_sat_A", "T_e_eV", "n_e_m3"] {
        assert_eq!(r.scalar(k).status, IcpStatus::NotEvaluated, "{k}");
    }
    assert!(r.if_icp_hall_v1.coupled_reasons.contains(&"CFG-FLIGHT-HALL-ON_NOT_EVALUATED".to_string()));
    // OUT-07 is NOT_EVALUATED in every v1 case, including a converged CFG-CAP-OFF one.
    let r = model().evaluate(&capoff_case(50.0, 0.0, 30.0));
    assert_eq!(r.scalar("I_e_neutralization_available_A").status, IcpStatus::NotEvaluated);
}

#[test]
fn fc04_calibrated_mode_without_a_validated_p2_map() {
    let mut c = capoff_case(0.0, 0.0, 30.0);
    c.coupling_mode = CouplingMode::Calibrated;
    c.rf_input = Some(RfInput::Forward { p_fwd_w: syn(200.0, "P_fwd"), p_refl_w: syn(10.0, "P_refl") });
    let r = model().evaluate(&c);
    assert!(has(&r, "FC-04_CM_CAL_WITHOUT_VALIDATED_P2_MAP"));
    for k in ["R_p_ohm", "R_ant_ohm", "X_ant_ohm", "eta_p", "I_ant_rms_A", "P_delivered_W"] {
        assert_eq!(r.scalar(k).status, IcpStatus::NotEvaluated, "{k}");
    }
    let keys = &r.if_icp_thermal_v1.assignments[0].keys;
    for k in [
        "P_icp_rf_forward_W",
        "P_icp_rf_reflected_W",
        "Q_icp_coil_ohmic_W",
        "Q_icp_match_W",
        "Q_icp_line_W",
        "P_icp_bus_W",
    ] {
        assert_eq!(keys[k].status, IcpStatus::NotEvaluated, "{k}");
    }
    assert_eq!(r.if_icp_bus_v1.keys["P_icp_bus_W"].status, IcpStatus::NotEvaluated);
    // An unvalidated map, a non-H_MODE point and an interpolated point fail closed too.
    for (mutate, code) in [
        (
            Box::new(|p: &mut P2Point| p.map_validated = false) as Box<dyn Fn(&mut P2Point)>,
            "FC-04_CM_CAL_WITHOUT_VALIDATED_P2_MAP",
        ),
        (Box::new(|p: &mut P2Point| p.plasma_state_class = "E_MODE".into()), "DOM-08"),
        (Box::new(|p: &mut P2Point| p.at_map_point = false), "DOM-09_P2_INTERPOLATION_NOT_EVALUATED"),
    ] {
        let mut c2 = c.clone();
        let mut ev = synthetic_p2(0.5, 0.3, 2.0, 3.0);
        if let CouplingEvidence::P2Point { point } = &mut ev {
            mutate(&mut point.value);
        }
        c2.coupling_evidence = Some(ev);
        let r = model().evaluate(&c2);
        assert!(has(&r, code), "{code}: {:?}", r.reason_codes());
        assert!(r.scalar("R_p_ohm").value.is_none());
    }
}

#[test]
fn fc05_missing_registrations_are_incomplete_evidence_naming_each_item() {
    let m = model();
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.geometry = None;
    c.electrodes = None;
    c.h_model = None;
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    for code in ["IN-10_GEOMETRY_NOT_REGISTERED", "IN-11_ELECTRODES_NOT_REGISTERED", "IN-17_NO_EDGE_FACTOR_SOURCE"] {
        assert!(has(&r, code), "{code}");
    }
    // Evaluation order: a missing registration decides the status before an input-domain verdict; both are named.
    c.f_rf_hz = Some(syn(27.12e6, "f_RF"));
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    assert_eq!(r.scalar("I_e_cap_A").status, IcpStatus::IncompleteEvidence);
    assert!(has(&r, "DOM-11") && has(&r, "IN-10_GEOMETRY_NOT_REGISTERED"));
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.f_rf_hz = Some(syn(27.12e6, "f_RF"));
    assert_eq!(m.evaluate(&c).status, IcpStatus::OutOfDomain, "DOM-11 alone");
    // H-LIEB without sigma_i for the ion.
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.h_model = Some(HModel::Lieberman { sigma_i_m2: BTreeMap::new() });
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    assert!(has(&r, "CHG-06_SIGMA_I_NOT_REGISTERED:X+"));
    // A missing electrode potential and a missing evidence attribute are named.
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.electrodes.as_mut().unwrap().value.potentials_v.remove("ec");
    c.geometry.as_mut().unwrap().evidence.transformation_chain = None;
    let r = m.evaluate(&c);
    assert!(has(&r, "IN-11_POTENTIAL_NOT_REGISTERED:ec"));
    assert!(has(&r, "IN-22:IN-10.geometry.transformation_chain"));
    assert!(r.scalar("I_e_cap_A").value.is_none());
}

#[test]
fn fc06_out_of_domain_names_the_reaction_and_the_n2_domain() {
    let m = model();
    // DOM-01: a converged T_e whose 3/2 T_e exceeds a used table limit.
    let mut c = floating_case(20.0);
    let set = set_of(&mut c);
    set.reactions[0].validity = Validity::Verified { max_mean_energy_ev: 3.0 };
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::OutOfDomain);
    assert!(has(&r, "DOM-01:ION_X"), "{:?}", r.reason_codes());
    let v = r.chemistry_validity.iter().find(|v| v.reaction == "ION_X").unwrap();
    assert_eq!(v.activity_share_beyond_limit, Some(1.0));
    assert!(r.scalar("T_e_eV").value.is_none());
    // DOM-02: the registered N2/N set domain is 2-30 eV; a state below 2 eV is outside it.
    assert_eq!(m.n2_set.t_e_domain_ev, [2.0, 30.0]);
    let mut c = floating_case(20.0);
    set_of(&mut c).t_e_domain_ev = m.n2_set.t_e_domain_ev;
    if let Some(NeutralSource::RegisteredPressure { p_icp_pa, .. }) = &mut c.neutral_source {
        p_icp_pa.value = 1000.0;
    }
    let r = m.evaluate(&c);
    assert_eq!(r.equilibria.len(), 1);
    assert!(r.equilibria[0].t_e_ev < 2.0);
    assert_eq!(r.status, IcpStatus::OutOfDomain);
    assert!(has(&r, "DOM-02"));
}

#[test]
fn fc07_unresolved_and_missing_validity_entries() {
    let m = model();
    let mut c = floating_case(20.0);
    set_of(&mut c).reactions[0].validity = Validity::Unresolved;
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    assert!(has(&r, "DOM-03_UNRESOLVED:ION_X"));
    let mut c = floating_case(20.0);
    set_of(&mut c).reactions[0].validity = Validity::MissingEntry;
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(has(&r, "DOM-03_MISSING_VALIDITY_ENTRY:ION_X"));
    // The real validity table: the HallThruster-shipped N2 tables are unresolved; an unknown file has no entry.
    assert_eq!(m.validity_of("ionization_N2_N2+.dat"), Validity::Unresolved);
    assert_eq!(m.validity_of("elastic_N2.dat"), Validity::Unresolved);
    assert_eq!(m.validity_of("dissociation_N2.dat"), Validity::Verified { max_mean_energy_ev: 45.0 });
    assert_eq!(m.validity_of("no_such_table.dat"), Validity::MissingEntry);
    for rx in &m.n2_set.reactions {
        assert!(matches!(rx.validity, Validity::Verified { .. }), "{}", rx.id);
    }
}

#[test]
fn fc08_g_reuse_books_zero_dedicated_flow_for_every_species() {
    let m = model();
    for c in [capoff_case(50.0, 0.0, 30.0), flow_case(50.0, 1e-6, 0.8), n2_today()] {
        let f = m.evaluate(&c).if_icp_feed_v1;
        assert_eq!(f.gas_mode, "G-REUSE");
        assert!(!f.mdot_icp_dedicated_kg_s.is_empty());
        for (s, q) in &f.mdot_icp_dedicated_kg_s {
            assert_eq!(q.value, Some(0.0), "{s}");
            assert_eq!(q.status, IcpStatus::Converged, "{s}");
        }
    }
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.gas_mode = syn(GasMode::GXe, "gas mode");
    let f = m.evaluate(&c).if_icp_feed_v1;
    assert!(f.mdot_icp_dedicated_kg_s.values().all(|q| q.status == IcpStatus::NotEvaluated));
}

#[test]
fn fc09_non_convergence_is_model_error_with_every_physics_value_null() {
    let num = NumericalSettings { bisection_max_iter: 3, ..NUMERICS };
    let r = model().evaluate_with(&capoff_case(50.0, 0.0, 30.0), &num);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(has(&r, "ITERATION_LIMIT_BISECTION"));
    for (k, v) in &r.outputs {
        match v {
            abep_icp::result::OutputValue::Scalar(q) => assert!(q.value.is_none(), "{k}"),
            abep_icp::result::OutputValue::Map(m) => assert!(m.values().all(|q| q.value.is_none()), "{k}"),
            abep_icp::result::OutputValue::Label(l) => assert!(l.value.is_none(), "{k}"),
        }
    }
    for a in &r.if_icp_thermal_v1.assignments {
        assert!(a.keys.values().all(|q| q.value.is_none()));
    }
    assert!(r.if_icp_hall_v1.i_e_cap_a.value.is_none());
    assert!(r.surface_terms.values().all(|s| s.l_w.value.is_none()));
}

#[test]
fn fc10_no_assessment_or_groundtest_dependency() {
    let root = abep_provenance::workspace_repo_root().unwrap();
    let lock: toml::Table = std::fs::read_to_string(root.join("Cargo.lock")).unwrap().parse().unwrap();
    let pkgs = lock["package"].as_array().unwrap();
    let deps_of = |name: &str| -> Vec<String> {
        pkgs.iter()
            .find(|p| p["name"].as_str() == Some(name))
            .and_then(|p| p.get("dependencies"))
            .and_then(|d| d.as_array())
            .map(|d| d.iter().filter_map(|x| x.as_str()).map(|s| s.split(' ').next().unwrap().to_string()).collect())
            .unwrap_or_default()
    };
    let mut seen = std::collections::BTreeSet::new();
    let mut stack = vec!["abep-icp".to_string()];
    while let Some(n) = stack.pop() {
        if seen.insert(n.clone()) {
            stack.extend(deps_of(&n));
        }
    }
    assert!(seen.contains("abep-provenance"));
    for forbidden in ["abep-assess", "abep-groundtest"] {
        assert!(!seen.contains(forbidden), "{forbidden} in the abep-icp graph");
    }
}

fn forbidden_source_tokens() -> Vec<String> {
    // Assembled at run time so the literals never appear in this crate.
    vec![
        ["La", "B6"].concat(),
        ["hollow", "_cathode"].concat(),
        ["kee", "per"].concat(),
        ["hea", "ter"].concat(),
        ["c1", "_"].concat(),
    ]
}

fn forbidden_output_tokens() -> Vec<String> {
    vec![
        ["HC", "-05"].concat(),
        ["GNG", "-ICP"].concat(),
        ["PA", "SS"].concat(),
        ["FA", "IL"].concat(),
        ["RF", "P"].concat(),
    ]
}

fn scan_dir(dir: &Path, tokens: &[String], hits: &mut Vec<String>) {
    for e in std::fs::read_dir(dir).unwrap() {
        let p = e.unwrap().path();
        if p.is_dir() {
            scan_dir(&p, tokens, hits);
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

#[test]
fn fc11_forbidden_identifiers_and_output_tokens() {
    let crate_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let mut hits = Vec::new();
    scan_dir(crate_dir, &forbidden_source_tokens(), &mut hits);
    assert!(hits.is_empty(), "{hits:?}");
    let m = model();
    let mut cases = vec![
        floating_case(10.0),
        capoff_case(50.0, 0.0, 30.0),
        capoff_case(0.0, -5.0, 10.0),
        flow_case(50.0, 1e-6, 0.8),
        n2_today(),
        registered_today_case(SupplyMode::AirPrimary, ChemistryRegistration::NotRegistered { gas: "AIR".into() }),
        registered_today_case(SupplyMode::XeContingency, ChemistryRegistration::NotRegistered { gas: "XE".into() }),
    ];
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.configuration = Configuration::FlightHallOn;
    cases.push(c);
    for c in cases {
        let json = m.evaluate(&c).to_json();
        for t in forbidden_output_tokens() {
            assert!(!json.contains(t.as_str()), "{}: output contains {t}", c.case_id);
        }
    }
}

/// Copy every file the model reads into a fresh root (plus `config/assessment/`), optionally rewriting one file.
fn copy_root(tag: &str, rewrite: Option<(&str, &dyn Fn(String) -> String)>) -> std::path::PathBuf {
    let src = abep_provenance::workspace_repo_root().unwrap();
    let dst = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!("abep_icp_root_{tag}"));
    let _ = std::fs::remove_dir_all(&dst);
    let mut files: Vec<String> = model().files_read.iter().map(|f| f.path.clone()).collect();
    files.push("config/MANIFEST.json".into());
    files.push("config/assessment/gate_thresholds_v1.json".into());
    for f in files {
        let to = dst.join(&f);
        std::fs::create_dir_all(to.parent().unwrap()).unwrap();
        let mut text = std::fs::read(src.join(&f)).unwrap();
        if let Some((name, fun)) = &rewrite {
            if f == *name {
                text = fun(String::from_utf8(text).unwrap()).into_bytes();
            }
        }
        std::fs::write(&to, text).unwrap();
    }
    dst
}

#[test]
fn fc12_a_gate_threshold_change_moves_no_raw_output_byte() {
    let m = model();
    assert!(m.files_read.iter().all(|f| !f.path.starts_with("config/assessment/")), "the model never reads assessment");
    let mut hits = Vec::new();
    scan_dir(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("src").as_path(),
        &[["gate_", "thresholds"].concat()],
        &mut hits,
    );
    assert!(hits.is_empty(), "{hits:?}");
    let changed =
        copy_root("fc12", Some(("config/assessment/gate_thresholds_v1.json", &|t: String| t.replacen('0', "7", 1))));
    let m2 = abep_icp::IcpModel::load(&changed).expect("context loads from the copied root");
    for c in [capoff_case(50.0, 0.0, 30.0), n2_today()] {
        assert_eq!(m.evaluate(&c).to_json(), m2.evaluate(&c).to_json(), "{}", c.case_id);
    }
}

#[test]
fn fc_chem_04_a_changed_pinned_byte_is_model_error() {
    for (tag, file) in [
        ("tbl", "hallthruster_bridge/propellants/ionization_N2_song2023.dat"),
        ("rv", "hallthruster_bridge/propellants/rate_validity.toml"),
        ("pre", "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_v1.json"),
        ("ens", "hallthruster_bridge/ensemble/transport_ensemble_v0.json"),
    ] {
        let root = copy_root(tag, Some((file, &|t: String| format!("{t} "))));
        let e = abep_icp::IcpModel::load(&root).expect_err(file);
        assert_eq!(e.status(), abep_types::EvalStatus::ModelError, "{file}");
        assert!(matches!(e, abep_types::AbepError::HashMismatch { .. }), "{file}: {e}");
    }
}

#[test]
fn fc13_o2_bearing_xe_and_ar_cases_are_incomplete_evidence() {
    let m = model();
    let r = m.evaluate(&registered_today_case(
        SupplyMode::EmO2b,
        ChemistryRegistration::NotRegistered { gas: "N2+O2".into() },
    ));
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    assert!(has(&r, "DOM-12_NO_NEGATIVE_ION_BALANCE") && has(&r, "NP_ICP_CHEM_AIR_NOT_ADMITTED"));
    for (mode, gas, code) in [
        (SupplyMode::XeContingency, "XE", "CHG-04_NO_XE_RATE_SET"),
        (SupplyMode::EmXe, "XE", "CHG-04_NO_XE_RATE_SET"),
        (SupplyMode::EmAr, "AR", "CHG-05_NO_AR_RATE_SET"),
    ] {
        let r = m.evaluate(&registered_today_case(mode, ChemistryRegistration::NotRegistered { gas: gas.into() }));
        assert_eq!(r.status, IcpStatus::IncompleteEvidence, "{mode:?}");
        assert!(has(&r, code), "{mode:?}");
        assert!(r.scalar("I_e_cap_A").value.is_none());
    }
    // An electronegative species in any set: DOM-12.
    let mut c = floating_case(20.0);
    set_of(&mut c).species[0].electronegative = true;
    assert!(has(&m.evaluate(&c), "DOM-12"));
}

#[test]
fn fc14_registered_magnetic_field_blocks_capacity_outputs() {
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.b_icp_max_t = Some(syn(0.002, "B_ICP,max"));
    let r = model().evaluate(&c);
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    assert!(has(&r, "DOM-06_MAGNETIZATION_CRITERION_OPEN"));
    for k in ["I_e_cap_A", "I_e_thermal_limit_A", "I_ion_collection_limit_A"] {
        assert_eq!(r.scalar(k).status, IcpStatus::IncompleteEvidence, "{k}");
    }
    c.b_icp_max_t = None;
    assert!(has(&model().evaluate(&c), "DOM-06_B_ICP_NOT_REGISTERED"));
}

#[test]
fn fc15_synthetic_label_propagates_and_mixing_is_refused() {
    let m = model();
    let r = m.evaluate(&capoff_case(50.0, 0.0, 30.0));
    assert!(r.flags.contains("SYNTHETIC_TEST_ONLY"));
    assert!(r.reasons.is_empty());
    // A synthetic geometry inside a real evidence mode, and real-mode chemistry in a synthetic case, are refused.
    let mut c = n2_today();
    c.geometry = capoff_case(50.0, 0.0, 30.0).geometry;
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(has(&r, "FC-15_SYNTHETIC_EVIDENCE_MIX_REFUSED"));
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.chemistry = ChemistryRegistration::RegisteredSet { config_file: "n2_n.toml".into() };
    assert!(has(&m.evaluate(&c), "FC-15_SYNTHETIC_EVIDENCE_MIX_REFUSED"));
}

#[test]
fn fc16_thermal_record_contract() {
    let m = model();
    let mut cases = vec![capoff_case(50.0, 0.0, 30.0), capoff_case(0.0, 0.0, 30.0), n2_today()];
    let mut cal = capoff_case(0.0, 0.0, 30.0);
    cal.coupling_mode = CouplingMode::Calibrated;
    cal.rf_input = Some(RfInput::Forward { p_fwd_w: syn(200.0, "P_fwd"), p_refl_w: syn(10.0, "P_refl") });
    cal.coupling_evidence = Some(synthetic_p2(0.5, 0.3, 2.0, 3.0));
    cases.push(cal);
    for c in cases {
        let r = m.evaluate(&c);
        let t = &r.if_icp_thermal_v1;
        assert!(t.rf_powered_only);
        for a in &t.assignments {
            assert!(a.keys.contains_key("P_icp_rf_reflected_W") && a.keys.contains_key("P_icp_collector_bias_W"));
            for k in [
                "Q_icp_plasma_wall_W",
                "Q_icp_coil_ohmic_W",
                "Q_icp_match_W",
                "Q_icp_extraction_W",
                "Q_icp_radiation_W",
            ] {
                if let Some(v) = a.keys[k].value {
                    assert!(v >= 0.0, "{}: {k} = {v}", c.case_id);
                }
            }
            assert!(a.keys.keys().all(|k| !k.starts_with("Q_hall")), "no Hall-powered key");
            assert_eq!(a.keys.len(), 15, "7 prescribed + 8 additional keys");
        }
        assert!(r.if_icp_bus_v1.keys.contains_key("P_icp_rf_reflected_W"));
        assert!(r.if_icp_bus_v1.keys.contains_key("P_icp_collector_bias_W"));
    }
}

#[test]
fn a930_air_primary_gate_and_mode_isolation() {
    let m = model();
    let air = m.evaluate(&registered_today_case(
        SupplyMode::AirPrimary,
        ChemistryRegistration::NotRegistered { gas: "AIR".into() },
    ));
    assert_eq!(air.status, IcpStatus::IncompleteEvidence);
    assert!(has(&air, "NP_ICP_CHEM_AIR_NOT_ADMITTED"));
    // Every tier-1 AIR gap of the NP-ICP-CHEM-AIR registry is named, including atomic O.
    for id in ["AIR-ION-02", "AIR-EL-04", "AIR-EXC-09", "AIR-DIS-02", "AIR-WALL-02"] {
        assert!(has(&air, &format!("NP-ICP-CHEM-AIR:{id}")), "{id}");
    }
    let gaps = m.chem_air_tier1_gaps("AIR");
    assert!(!gaps.is_empty());
    for p in gaps {
        assert!(has(&air, &format!("NP-ICP-CHEM-AIR:{}", p.id)));
    }
    // Atomic O is never replaced by an N2-only surrogate.
    let sur = m.evaluate(&registered_today_case(
        SupplyMode::AirPrimary,
        ChemistryRegistration::RegisteredSet { config_file: "n2_n.toml".into() },
    ));
    assert_eq!(sur.status, IcpStatus::ModelError);
    assert!(has(&sur, "A9.30_N2_ONLY_SURROGATE_REFUSED"));
    // XE_CONTINGENCY fails closed on its own evidence and carries no AIR status (SP-07).
    let xe = m.evaluate(&registered_today_case(
        SupplyMode::XeContingency,
        ChemistryRegistration::NotRegistered { gas: "XE".into() },
    ));
    assert_eq!(xe.status, IcpStatus::IncompleteEvidence);
    assert!(has(&xe, "CHG-04_NO_XE_RATE_SET") && has(&xe, "NP_ICP_CHEM_AIR_XE_NOT_ADMITTED"));
    assert!(has(&xe, "NP-ICP-CHEM-AIR:XE-ION-01"));
    assert!(xe.reason_codes().iter().all(|c| !c.contains("AIR-") && c != "NP_ICP_CHEM_AIR_NOT_ADMITTED"));
    assert!(air.reason_codes().iter().all(|c| !c.contains("XE-") && !c.contains("CHG-04")));
    // Mixed Xe / air composition: OUT_OF_DOMAIN (OQ-CHEM-10).
    let mut c = capoff_case(50.0, 0.0, 30.0);
    if let Some(NeutralSource::RegisteredPressure { mole_fractions, .. }) = &mut c.neutral_source {
        mole_fractions.value = [("X".to_string(), 0.5), ("XE".to_string(), 0.5)].into();
    }
    assert!(has(&m.evaluate(&c), "FC-CHEM-09_MIXED_XE_AIR_COMPOSITION"));
}

#[test]
fn a930_active_bus_boundary() {
    let mut c = capoff_case(0.0, 0.0, 30.0);
    c.coupling_mode = CouplingMode::Calibrated;
    c.rf_input = Some(RfInput::Forward { p_fwd_w: syn(200.0, "P_fwd"), p_refl_w: syn(10.0, "P_refl") });
    c.coupling_evidence = Some(synthetic_p2(0.5, 0.3, 2.0, 3.0));
    let mut bus = synthetic_bus(0.8, 0.9);
    bus.boundary_id = "bus_power_boundary_v1".into();
    c.bus = Some(bus);
    let r = model().evaluate(&c);
    assert_eq!(r.if_icp_bus_v1.target_boundary, "bus_power_boundary_a9_v2");
    assert!(r.if_icp_bus_v1.reasons.contains(&"A9.30_BUS_BOUNDARY".to_string()));
    assert_eq!(r.if_icp_bus_v1.status, IcpStatus::ModelError);
    c.bus.as_mut().unwrap().boundary_id = "bus_power_boundary_a9_v2".into();
    c.bus.as_mut().unwrap().ground_facility_only = true;
    let r = model().evaluate(&c);
    assert!(r.if_icp_bus_v1.reasons.contains(&"GROUND_FACILITY_ONLY".to_string()));
    assert!(r.if_icp_bus_v1.keys["P_icp_bus_W"].value.is_none());
}

#[test]
fn n2_demonstration_case_is_not_evaluated_with_every_missing_input_listed() {
    let r = model().evaluate(&n2_today());
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    for code in [
        "IN-08_RF_INPUT_NOT_REGISTERED",
        "IN-10_GEOMETRY_NOT_REGISTERED",
        "IN-11_ELECTRODES_NOT_REGISTERED",
        "IN-12_NEUTRAL_SOURCE_NOT_REGISTERED",
        "IN-17_NO_EDGE_FACTOR_SOURCE",
        "DOM-06_B_ICP_NOT_REGISTERED",
        "EQ-06_ABEP_CHEM_INTEGRATOR_NOT_ADMITTED",
        "IF-CHEM-REG-v1_ICP_REGISTRY_NOT_BUILT",
        "OQ-NPICP-04_ICP_COMPLETENESS_AUDIT_OPEN",
        "PROCESS_CLASS_GATE_UNADDRESSED",
    ] {
        assert!(has(&r, code), "{code}");
    }
    assert!(r.reasons.iter().all(|x| x.status != IcpStatus::ModelError), "{:#?}", r.reasons);
    assert!(r.scalar("I_e_cap_A").value.is_none());
}

#[test]
fn withheld_paths_where_the_preregistration_is_not_operational() {
    let m = model();
    // EQ-16 neutral-energy split: an elastic channel solves, but the wall / outflow keys are withheld.
    let mut c = capoff_case(50.0, 0.0, 30.0);
    set_of(&mut c).reactions.push(ReactionDef {
        id: "EL_X".into(),
        kind: ReactionKind::ElasticMomentumTransfer,
        target: "X".into(),
        products: vec![("X".into(), 1)],
        threshold_ev: 0.0,
        rate: RateSource::Synthetic { rate: arrhenius(1e-13, 0.0) },
        validity: Validity::Verified { max_mean_energy_ev: 255.0 },
    });
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
    assert!(r.verify_items_on_path.contains("VER-02"));
    let k = &r.if_icp_thermal_v1.assignments[0].keys;
    assert_eq!(k["Q_icp_plasma_wall_W"].status, IcpStatus::IncompleteEvidence);
    assert!(k["Q_icp_plasma_wall_W"].reasons.contains(&"PREREG_GAP_EQ16_NEUTRAL_ENERGY_SPLIT".to_string()));
    assert!(val(r.scalar("I_e_cap_A")) > 0.0);
    // PF-01: EQ-02 atom recombination with gamma > 0 in FLOW_BALANCE.
    let mut c = flow_case(50.0, 1e-6, 0.8);
    let set = set_of(&mut c);
    set.species.push(abep_icp::chemistry::SpeciesDef {
        name: "X2".into(),
        mass_kg: 2.0 * M_X_KG,
        charge: 0,
        elements: [("X".to_string(), 2)].into(),
        electronegative: false,
        wall_products: vec![],
        recombines_to: None,
    });
    set.species[0].recombines_to = Some("X2".into());
    set.process_classes = excluded_all(&["X", "X+", "X2"]);
    if let Some(NeutralSource::FlowBalance { sigma_c_m2, .. }) = &mut c.neutral_source {
        sigma_c_m2.insert("X2".into(), syn(1e-19, "sigma_c"));
    }
    c.wall_recombination.insert("X".into(), Registered::synthetic(1.0, "gamma"));
    assert!(has(&m.evaluate(&c), "PREREG_FINDING_PF-01_EQ02_ATOM_RECOMBINATION_FACTOR"));
    // PF-02: background inflow over A_open without tau while effusion carries tau.
    let mut c = flow_case(50.0, 1e-6, 0.8);
    c.background.as_mut().unwrap().value.n_b_m3.insert("X".into(), 1e17);
    assert!(has(&m.evaluate(&c), "PREREG_FINDING_PF-02_BACKGROUND_INFLOW_WITHOUT_TAU"));
    // Multi-species H-LIEB with distinct sigma_i: one h per surface is not defined.
    let mut c = synthetic_case(
        "SYN_X2",
        with_double_ion(x_set(x_rate())),
        capoff_surfaces(),
        &[("ic", 0.0), ("ec", 30.0)],
        50.0,
    );
    c.h_model = Some(HModel::Lieberman {
        sigma_i_m2: [("X+".to_string(), syn(5e-19, "s")), ("X++".to_string(), syn(3e-19, "s"))].into(),
    });
    assert!(has(&m.evaluate(&c), "PREREG_GAP_MULTISPECIES_H_LIEB"));
}

#[test]
fn h_lieb_single_species_and_its_domain() {
    let m = model();
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.h_model = Some(HModel::Lieberman { sigma_i_m2: [("X+".to_string(), syn(5e-19, "sigma_i"))].into() });
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::Converged, "{:#?}", r.reasons);
    assert!(r.flags.contains("H_LIEB_ARGON_STATEMENT_EXTRAPOLATED"));
    assert!(r.verify_items_on_path.contains("VER-07"), "open end treated as axial h_L");
    if let Some(NeutralSource::RegisteredPressure { p_icp_pa, .. }) = &mut c.neutral_source {
        p_icp_pa.value = 20.0;
    }
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::OutOfDomain);
    assert!(has(&r, "DOM-05"));
}

#[test]
fn i_e_sat_is_the_maximum_over_the_registered_bias_range() {
    let m = model();
    let mut c = capoff_case(50.0, 0.0, 30.0);
    c.electrodes.as_mut().unwrap().value.collector_bias_sweep_v = Some(vec![0.0, 5.0, 10.0, 20.0, 40.0]);
    let r = m.evaluate(&c);
    let sat = val(r.scalar("I_e_sat_A"));
    let mut best = f64::NEG_INFINITY;
    for v in [0.0, 5.0, 10.0, 20.0, 40.0] {
        best = best.max(val(m.evaluate(&capoff_case(50.0, 0.0, v)).scalar("I_e_cap_A")));
    }
    assert_eq!(sat, best);
    c.electrodes.as_mut().unwrap().value.collector_bias_sweep_v = None;
    let r = m.evaluate(&c);
    assert_eq!(r.scalar("I_e_sat_A").status, IcpStatus::NotEvaluated);
    assert!(r.scalar("I_e_sat_A").reasons.contains(&"EQ-11_BIAS_RANGE_NOT_REGISTERED".to_string()));
}
