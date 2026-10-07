//! NP-THERMAL-CATHODELESS 2.0.0: the inherited verification cases (prereg v2 inheritance rule and admission_rule_v2:
//! AL-01..AL-11, FT-01..FT-18, DET, IV-02 apply to 2.0.0) run through `run_case_v2`. Every case builder is the v1
//! verification's; under `with_model_v2` each case is run as model 2.0.0, and a VS-NET-based case consumes the
//! registered AL-10 v2 record in place of the retired IF-ICP-THERMAL-v1 record (`vs_net_v2::inherited_to_v2`). AL-10
//! and FT-13 are the v2 cases of tests/thermal_v2.rs; FT-19..FT-23 are there too.

mod support;

use support::{verify, vs_net, with_model_v2};

fn check(ch: verify::Check) {
    assert!(ch.met, "{ch:#?}");
}

#[test]
fn the_switch_runs_model_2() {
    let mut c = vs_net::load_registered();
    vs_net::set_sinks(&mut c, 250.0);
    let o = with_model_v2(|| support::run(&c));
    assert_eq!(o.model_version, "2.0.0");
    assert!(support::converged(&o), "{:#?}", o.status_reasons);
    assert!(o.results.unwrap().interface_derived.unwrap().icp_v2.is_some());
}

#[test]
fn inherited_analytic_cases_hold_in_model_2() {
    for f in [
        verify::al_01,
        verify::al_02,
        verify::al_02b,
        verify::al_03,
        verify::al_04,
        verify::al_07,
        verify::al_08,
        verify::al_09,
        verify::al_11,
        verify::iv_02,
        verify::orbit_consistency,
    ] {
        check(with_model_v2(f));
    }
    let (al05, tau_max) = with_model_v2(verify::al_05);
    check(al05);
    check(with_model_v2(|| verify::al_06(tau_max)));
}

#[test]
fn inherited_fail_closed_cases_hold_in_model_2() {
    for f in [
        verify::ft_01,
        verify::ft_02,
        verify::ft_03,
        verify::ft_04,
        verify::ft_05,
        verify::ft_06,
        verify::ft_07,
        verify::ft_08,
        verify::ft_09,
        verify::ft_10,
        verify::ft_11,
        verify::ft_12,
        verify::ft_15,
        verify::ft_16,
        verify::ft_18,
        verify::bench_domain,
    ] {
        check(with_model_v2(f));
    }
    check(with_model_v2(|| verify::ft_14(&verify::al_07())));
    let outs = with_model_v2(|| verify::det_cases().iter().map(support::run).collect::<Vec<_>>());
    assert!(outs.iter().all(|o| o.model_version == "2.0.0"));
    check(verify::ft_17(&outs.iter().collect::<Vec<_>>()));
}

#[test]
fn inherited_determinism_holds_in_model_2() {
    // DET-02 runs cases on spawned threads: the process-wide switch (every test of this binary is model 2.0.0).
    support::MODEL_V2_PROCESS.store(true, std::sync::atomic::Ordering::SeqCst);
    let (d1, d2, _v1_det03) = with_model_v2(|| verify::det(&verify::det_cases()));
    check(d1);
    check(d2);
    // DET-03 with the 2.0.0 provenance (O-17 v2): the v2 prereg sha256, the IF-ICP-THERMAL-v2 record hash, the
    // producer lock and the scenario member (FT-23). The v1 helper's DET-03 checks the v1 prereg sha256 by its text.
    for c in verify::det_cases() {
        let o = with_model_v2(|| support::run(&c));
        let p = &o.provenance;
        assert_eq!(p.implementation, "rust");
        assert_eq!(p.rust_commit.len(), 40);
        assert_eq!(p.prereg_sha256, "6828f3e257e38a588c9513f2531658035fa904b6c51e3b28831681d871adfa78");
        assert_eq!(p.input_set_sha256.len(), 64);
        assert!(p.interface_record_sha256.contains_key("IF-ICP-THERMAL-v2"), "{}", c.case_id);
        assert!(!p.interface_record_sha256.contains_key("IF-ICP-THERMAL-v1"));
        assert!(p.scenario_member_id.is_some() && p.producer_lock_sha256.is_some());
        for k in ["architecture_config_sha256", "design_state_set_sha256", "model_set_sha256"] {
            assert!(p.governed_record_sha256.contains_key(k), "{k}");
        }
        assert_eq!(p.validation_status, "NOT_VALIDATED");
    }
}

/// IV-01 carry-over: the analytic-case results the v1 IV-01 cross-check compared are identical under 2.0.0, so its
/// independent numbers apply unchanged; the VS-NET 2.0.0 steady and transient parts were cross-checked anew (report).
#[test]
fn iv01_analytic_dump_is_identical_in_model_2() {
    let v1 = verify::iv01_dump();
    let v2 = with_model_v2(verify::iv01_dump);
    assert_eq!(v1, v2);
}
