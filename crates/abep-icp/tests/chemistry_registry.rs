//! EQ-06 through IF-CHEM-REG-v1 (NP-ICP-NEUTRALIZER addendum 02; NP-ICP-CHEM-AIR interface_to_parent): registered
//! tables are evaluated only through their registry representation and abep_chem::checked, inside the solve and in
//! the NV-06 report; registry statuses propagate per SP-01..SP-08 without relaxing any gate. Missing evidence is asserted
//! as its fail-closed status, never skipped.

mod common;

use abep_icp::case::*;
use abep_icp::chemistry::{ChemistryRegistration, RateSource, Validity};
use abep_icp::constants::{E_CHARGE, NUMERICS};
use abep_icp::testkit::*;
use abep_icp::{IcpResult, IcpStatus};
use common::{model, rel};

const ION: &str = "AIR-ION-03/ionization_N2_song2023";
const EL: &str = "AIR-EL-01/elastic_N2_song2023";
const DIS: &str = "AIR-DIS-01/dissociation_N2";

fn has(r: &IcpResult, code: &str) -> bool {
    r.reason_codes().contains(code)
}

/// Floating tube, N2 at 1 Pa (REGISTERED_PRESSURE), registered N2 ionization, elastic and dissociation channels.
fn registered_rate_case(p_abs_w: f64) -> abep_icp::IcpCase {
    let set = n2_registered_rate_set(model(), &[ION, EL, DIS], &["N2", "N", "N2^+"]);
    synthetic_case("SYN_N2_REGISTERED_RATES", set, floating_surfaces(), &[], p_abs_w)
}

#[test]
fn the_solve_uses_the_direct_rates_of_the_registry() {
    let m = model();
    let r = m.evaluate(&registered_rate_case(20.0));
    assert!(r.flags.contains("SYNTHETIC_TEST_ONLY"));
    assert_eq!(r.equilibria.len(), 1, "{:?}", r.reason_codes());
    let t_e = r.equilibria[0].t_e_ev;
    assert!((2.0..=30.0).contains(&t_e), "T_e {t_e} eV in D-CHEM");
    assert!(
        !r.reason_codes().iter().any(|c| c.starts_with("EQ-06") || c.starts_with("IF-CHEM-REG")),
        "{:?}",
        r.reason_codes()
    );
    // Per reaction at the solution: the rate the solve used is the registry's direct rate, bit for bit (EQ-06); the .dat
    // interpolation is reported beside it (UQ-06) and never used.
    let air = &m.chem_registry.air;
    for id in [ION, EL, DIS] {
        let v = r.chemistry_validity.iter().find(|v| v.reaction == id).unwrap();
        let k = air.direct_rate(air.channel(id).unwrap(), t_e).unwrap().k_m3_s;
        assert_eq!(v.direct_rate_m3_s.map(f64::to_bits), Some(k.to_bits()), "{id}");
        let dat = v.dat_rate_m3_s.expect("table defined");
        assert_eq!(v.dat_minus_direct_relative, Some((dat - k) / k), "{id}");
        assert_eq!(v.status, IcpStatus::Converged);
    }
    // The T_e scan ends where the 45 eV tables (dissociation) end: 30 eV, a scan node (IX-05).
    let end = r.domain_checks.iter().find(|c| c.id == "IN-24_T_E_SCAN_END").expect("reported");
    assert_eq!(end.value, Some(30.0));
    // Independent check of the particle balance with the registry rate: n_N2 k_iz V = u_B sum(h A) (LC-01 form).
    let n_g = 1.0 / (abep_icp::constants::K_B * 300.0);
    let k_iz = air.direct_rate(air.channel(ION).unwrap(), t_e).unwrap().k_m3_s;
    let m_n2 = m.n2_set.species[m.n2_set.species_index("N2^+").unwrap()].mass_kg;
    let sum_ha = H_EDGE * (2.0 * std::f64::consts::PI * R_M * L_M + 2.0 * std::f64::consts::PI * R_M * R_M);
    let vol = std::f64::consts::PI * R_M * R_M * L_M;
    let lhs = n_g * k_iz * vol;
    let rhs = (E_CHARGE * t_e / m_n2).sqrt() * sum_ha;
    assert!(rel(lhs, rhs) <= 1e-9, "particle balance {lhs} vs {rhs}");
    // Linear case: T_e independent of the absorbed power.
    let r2 = m.evaluate(&registered_rate_case(200.0));
    assert_eq!(r2.equilibria[0].t_e_ev.to_bits(), t_e.to_bits());
    // NV-01 on the registered-rate path: a second run is byte-identical.
    assert_eq!(m.evaluate(&registered_rate_case(20.0)).to_json(), r.to_json());
}

#[test]
fn a_synthetic_scan_is_not_truncated() {
    let r = model().evaluate(&floating_case(20.0));
    assert!(r.domain_checks.iter().all(|c| c.id != "IN-24_T_E_SCAN_END"));
    let v = &r.chemistry_validity[0];
    assert_eq!((v.direct_rate_m3_s, v.dat_rate_m3_s, v.dat_minus_direct_relative), (None, None, None));
    assert_eq!(NUMERICS.t_e_scan_max_ev, 150.0);
}

#[test]
fn a_table_without_a_registered_representation_is_incomplete_evidence() {
    let m = model();
    let set = n2_registered_rate_set(m, &["AIR-ION-04/ionization_N", EL], &["N2", "N", "N^+"]);
    let r = m.evaluate(&synthetic_case("SYN_N_ION", set, floating_surfaces(), &[], 20.0));
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    assert!(has(&r, "EQ-06_REPRESENTATION_NOT_REGISTERED:AIR-ION-04/ionization_N"));
    assert!(r.equilibria.is_empty() && r.scalar("T_e_eV").value.is_none(), "no solve with a missing rate");
}

#[test]
fn a_reaction_that_differs_from_its_registry_channel_or_an_unregistered_file_is_model_error() {
    let m = model();
    type Edit = dyn Fn(&mut abep_icp::chemistry::ReactionDef);
    let threshold: &Edit = &|rx| rx.threshold_ev = 15.0;
    let validity: &Edit = &|rx| rx.validity = Validity::Verified { max_mean_energy_ev: 255.0 };
    let products: &Edit = &|rx| rx.products = vec![("N2".into(), 1)];
    for (tag, edit) in [("threshold", threshold), ("validity", validity), ("products", products)] {
        let mut c = registered_rate_case(20.0);
        let ChemistryRegistration::Synthetic { set } = &mut c.chemistry else { unreachable!() };
        let rx = set.reactions.iter_mut().find(|x| x.id == if tag == "validity" { DIS } else { ION }).unwrap();
        edit(rx);
        let r = m.evaluate(&c);
        assert_eq!(r.status, IcpStatus::ModelError, "{tag}");
        assert!(
            r.reason_codes()
                .iter()
                .any(|x| x.starts_with("IF-CHEM-REG-v1_REACTION_DIFFERS_FROM_REGISTRY") || x == "CHEMISTRY_CONTRACT"),
            "{tag}: {:?}",
            r.reason_codes()
        );
    }
    // The HallThruster-shipped table (unresolved, excluded from reuse) has no channel: an unregistered file.
    let mut c = registered_rate_case(20.0);
    let ChemistryRegistration::Synthetic { set } = &mut c.chemistry else { unreachable!() };
    set.reactions[1].rate = RateSource::RegisteredTable { file: "elastic_N2.dat".into() };
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::ModelError);
    assert!(has(&r, &format!("IF-CHEM-REG-v1_UNREGISTERED_FILE:{EL}")));
}

#[test]
fn air_statuses_propagate_from_the_registry_and_never_reach_xe() {
    let m = model();
    let mut air =
        registered_today_case(SupplyMode::AirPrimary, ChemistryRegistration::NotRegistered { gas: "AIR".into() });
    let r = m.evaluate(&air);
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    // G-A930-AIR, every tier-1 gap, SB-NO for every AIR composition (SP-04), NEG-CRIT (SP-05).
    for code in [
        "NP_ICP_CHEM_AIR_NOT_ADMITTED",
        "NP-ICP-CHEM-AIR:AIR-EL-04",
        "NP-ICP-CHEM-AIR:AIR-EXC-09",
        "SP-04_SPECIES_BOUND_UNRESOLVED:SB-NO",
        "DOM-12_NO_NEGATIVE_ION_BALANCE",
    ] {
        assert!(has(&r, code), "{code}");
    }
    for p in m.chem_registry.air.tier1_gaps() {
        assert!(has(&r, &format!("NP-ICP-CHEM-AIR:{}", p.id)), "{}", p.id);
    }
    assert!(!has(&r, "SP-04_SPECIES_BOUND_UNRESOLVED:SB-He"), "no composition registered");
    // SB-He / SB-Ar apply only to compositions above the 1 % screen (FC-CHEM-07).
    for (x_he, expect) in [(0.02, true), (0.005, false)] {
        air.neutral_source = Some(NeutralSource::RegisteredPressure {
            p_icp_pa: syn(1.0, "p"),
            t_g_k: syn(300.0, "T_g"),
            mole_fractions: syn([("N2".to_string(), 1.0 - x_he), ("He".to_string(), x_he)].into(), "x"),
        });
        let r = m.evaluate(&air);
        assert_eq!(has(&r, "SP-04_SPECIES_BOUND_UNRESOLVED:SB-He"), expect, "x_He {x_he}");
        assert!(!has(&r, "SP-04_SPECIES_BOUND_UNRESOLVED:SB-Ar"));
    }
    // XE: its own registry, no AIR item (SP-07, AD-XE-05).
    let xe = m.evaluate(&registered_today_case(
        SupplyMode::XeContingency,
        ChemistryRegistration::NotRegistered { gas: "XE".into() },
    ));
    assert_eq!(xe.status, IcpStatus::IncompleteEvidence);
    for code in ["CHG-04_NO_XE_RATE_SET", "NP_ICP_CHEM_AIR_XE_NOT_ADMITTED", "NP-ICP-CHEM-AIR:XE-ION-01"] {
        assert!(has(&xe, code), "{code}");
    }
    assert!(xe
        .reason_codes()
        .iter()
        .all(|c| !c.contains("AIR-") && !c.starts_with("SP-04") && !c.starts_with("DOM-12")));
}

#[test]
fn em_n2_runs_only_where_every_required_input_is_registered() {
    let m = model();
    let r = m.evaluate(&registered_today_case(
        SupplyMode::EmN2,
        ChemistryRegistration::RegisteredSet { config_file: "n2_n.toml".into() },
    ));
    assert_eq!(r.status, IcpStatus::IncompleteEvidence);
    assert!(r.equilibria.is_empty());
    // Exactly the 11 nominal tables without a direct representation are named; the 18 others pass the EQ-06 gate.
    let missing: Vec<String> = r
        .reason_codes()
        .into_iter()
        .filter_map(|c| c.strip_prefix("EQ-06_REPRESENTATION_NOT_REGISTERED:").map(String::from))
        .collect();
    let mut want = vec!["AIR-ION-04/ionization_N".to_string()];
    want.extend((1..=10).map(|v| format!("AIR-EXC-02/excitation_N2_vib_0_to_{v}")));
    want.sort();
    let mut got = missing.clone();
    got.sort();
    assert_eq!(got, want);
    assert_eq!(m.n2_set.reactions.len() - missing.len(), 18);
}
