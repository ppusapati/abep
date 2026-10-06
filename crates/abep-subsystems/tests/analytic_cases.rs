//! Analytic limiting cases AL-01..AL-04, AL-07..AL-09, AL-11, the independent closed-form benchmark IV-02 and the E-12 /
//! CONS-T3 orbit consistency (prereg `analytic_limiting_cases`, `independent_verification`; CI_PLAN principle 9).

mod support;

use support::verify;

fn check(ch: verify::Check) {
    assert!(ch.met, "{} not met: {:#?}", ch.id, ch);
}

#[test]
fn al_01_single_isothermal_radiator() {
    check(verify::al_01());
}

#[test]
fn al_02_two_node_series_conduction() {
    check(verify::al_02());
}

#[test]
fn al_02b_kirchhoff_linear_conductivity() {
    check(verify::al_02b());
}

#[test]
fn al_03_first_order_transient() {
    check(verify::al_03());
}

#[test]
fn al_04_two_surface_enclosure() {
    check(verify::al_04());
}

#[test]
fn al_07_view_factor_reciprocity_and_summation() {
    check(verify::al_07());
}

#[test]
fn al_08_isothermal_enclosure_and_black_body_limit() {
    check(verify::al_08());
}

#[test]
fn al_09_environment_bookkeeping() {
    check(verify::al_09());
}

#[test]
fn al_11_winding_self_heating_r_of_t() {
    check(verify::al_11());
}

#[test]
fn iv_02_howell_coaxial_disks_closed_form() {
    check(verify::iv_02());
}

#[test]
fn e12_orbit_periodic_and_orbit_average_consistency() {
    check(verify::orbit_consistency());
}
