//! Fail-closed tests FT-01..FT-18 (prereg `fail_closed_tests`). Missing evidence is asserted as its status, never
//! skipped (A9.29 sec. 9); the empty credible Hall transport set is asserted explicitly (FT-01).

mod support;

use support::verify;

fn check(ch: verify::Check) {
    assert!(ch.met, "{} not met: {:#?}", ch.id, ch);
}

#[test]
fn ft_01_flight_hall_heat_needs_the_empty_credible_set() {
    check(verify::ft_01());
}

#[test]
fn ft_02_screening_candidate_and_unpinned_commit() {
    check(verify::ft_02());
}

#[test]
fn ft_03_tbd_input_is_incomplete_evidence() {
    check(verify::ft_03());
}

#[test]
fn ft_04_malformed_record() {
    check(verify::ft_04());
}

#[test]
fn ft_05_synthetic_and_evidence_records_never_mix() {
    check(verify::ft_05());
}

#[test]
fn ft_06_property_outside_its_range() {
    check(verify::ft_06());
}

#[test]
fn ft_07_biot_criterion() {
    check(verify::ft_07());
}

#[test]
fn ft_08_caps_are_model_errors() {
    check(verify::ft_08());
}

#[test]
fn ft_09_floating_node() {
    check(verify::ft_09());
}

#[test]
fn ft_10_cathode_vocabulary_is_refused() {
    check(verify::ft_10());
}

#[test]
fn ft_11_other_configuration_is_refused() {
    check(verify::ft_11());
}

#[test]
fn ft_12_variants_outside_v1() {
    check(verify::ft_12());
}

#[test]
fn ft_13_14_interface_identities_and_view_factors() {
    check(verify::ft_13(&verify::al_10()));
    check(verify::ft_14(&verify::al_07()));
}

#[test]
fn ft_15_design_state_outside_the_set() {
    check(verify::ft_15());
}

#[test]
fn ft_16_rejected_anode_candidate() {
    check(verify::ft_16());
}

#[test]
fn ft_17_output_schema_scan() {
    let cases = verify::det_cases();
    let outs: Vec<_> = cases.iter().map(support::run).collect();
    check(verify::ft_17(&outs.iter().collect::<Vec<_>>()));
}

#[test]
fn ft_18_not_evaluated_key_is_never_zero_filled() {
    check(verify::ft_18());
}

#[test]
fn bench_replica_domain_d04_d05() {
    check(verify::bench_domain());
}
