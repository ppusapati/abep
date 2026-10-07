//! NP-MISSION-INTEGRATION v1 verification (prereg AL-01..AL-11, CONS, FT-01..FT-15, DET-01..DET-02). Synthetic vectors
//! (SYNTHETIC_TEST_DATA_NOT_EVIDENCE) on the state ids of the frozen set; FT-01..FT-05 / FT-10 assert today's
//! fail-closed run explicitly (A9.29 sec. 9: missing evidence is a status, not a skip).

use abep_mission::integration::model::{integrate, ConservationCheck, IcpGasMode, MissionRecord, Mode};
use abep_mission::integration::quantity::{Field, Label, Quantity, PARAMETRIC_SENSITIVITY_ONLY};
use abep_mission::integration::testkit::{self as tk, seg, syn, syn_absent};
use abep_mission::integration::today::{run_admitted, TodayOptions, TodayRun};
use abep_mission::integration::{
    ADDENDUM_01_REL, ADDENDUM_01_SHA256, PREREG_MD_REL, PREREG_MD_SHA256, PREREG_REL, PREREG_SHA256,
};
use abep_types::EvalStatus;
use std::path::PathBuf;
use std::sync::OnceLock;

fn repo() -> PathBuf {
    abep_provenance::workspace_repo_root().unwrap()
}

fn ids() -> &'static Vec<String> {
    static IDS: OnceLock<Vec<String>> = OnceLock::new();
    IDS.get_or_init(|| {
        let pins = abep_data::pins::FrozenPins::load(&repo()).unwrap();
        let set = abep_data::design_states::DesignStateSet::load(&repo(), &pins).unwrap();
        set.states.iter().filter(|s| s.required).map(|s| s.state_id.clone()).collect()
    })
}

fn today() -> &'static TodayRun {
    static RUN: OnceLock<TodayRun> = OnceLock::new();
    RUN.get_or_init(|| run_admitted(&repo(), &TodayOptions { design_point: None, rust_commit: "test".into() }).unwrap())
}

fn total<'a>(r: &'a MissionRecord, k: &str) -> &'a Quantity {
    &r.schedule.totals[k]
}

fn q<'a>(r: &'a MissionRecord, sid: &str, mode: Mode, key: &str) -> &'a Quantity {
    r.field(sid, mode, key).and_then(Field::quantity).unwrap_or_else(|| panic!("{sid}/{key}"))
}

fn cons<'a>(c: &'a [ConservationCheck], id: &str) -> &'a ConservationCheck {
    c.iter().find(|x| x.id == id).unwrap()
}

#[test]
fn prereg_files_match_the_lock() {
    for (rel, sha) in
        [(PREREG_REL, PREREG_SHA256), (PREREG_MD_REL, PREREG_MD_SHA256), (ADDENDUM_01_REL, ADDENDUM_01_SHA256)]
    {
        abep_provenance::read_verified(&repo().join(rel), sha).unwrap();
    }
    let lock: serde_json::Value = serde_json::from_slice(
        &std::fs::read(repo().join("docs/rust_migration/new_physics/NP-MISSION-INTEGRATION/prereg_lock_v1.json"))
            .unwrap(),
    )
    .unwrap();
    assert_eq!(lock["files"]["prereg_v1.json"], PREREG_SHA256);
    assert_eq!(lock["files"]["PREREG.md"], PREREG_MD_SHA256);
}

#[test]
fn al01_constant_rate_and_time_totals() {
    let r = integrate(&tk::al01(ids())).unwrap();
    assert_eq!(r.schedule.status, EvalStatus::Evaluated);
    assert_eq!(total(&r, "M_atm_delivered_kg").value, Some(1e-6 * (15000.0 * 3600.0)));
    assert_eq!(total(&r, "H_sched_h").value, Some(26280.0));
    assert_eq!(total(&r, "H_fire_h").value, Some(15000.0));
    assert_eq!(total(&r, "H_air_h").value, Some(15000.0));
    assert_eq!(total(&r, "H_xe_h").value, Some(0.0));
    assert_eq!(total(&r, "H_coast_h").value, Some(11280.0));
    assert_eq!(cons(&r.schedule.conservation, "CONS-T1").holds, Some(true));
    assert_eq!(cons(&r.schedule.conservation, "CONS-F1").holds, Some(true));
}

#[test]
fn al02_piecewise_integral_and_ledgers() {
    let inp = tk::al02(ids());
    let r = integrate(&inp).unwrap();
    assert_eq!(r.schedule.status, EvalStatus::Evaluated);
    let sch = inp.schedule.as_ref().unwrap();
    let mut naive = 0.0;
    for s in &sch.segments {
        if s.mode == "AIR_PRIMARY" {
            let i = ids().iter().position(|x| *x == s.state_id).unwrap();
            naive += tk::rate("mdot_atm_delivered_kg_s", i) * (s.duration_h * 3600.0);
        }
    }
    let v = total(&r, "M_atm_delivered_kg").value.unwrap();
    assert!((v - naive).abs() <= 1e-12 * naive.abs(), "{v} vs {naive}");
    for c in ["CONS-T1", "CONS-F1"] {
        assert_eq!(cons(&r.schedule.conservation, c).holds, Some(true), "{c}");
    }
    for c in ["CONS-M1", "CONS-M2"] {
        assert_eq!(cons(&r.mass.conservation, c).holds, Some(true), "{c}");
    }
    // G-XE routing: the Xe tank feeds the ICP in AIR_PRIMARY and Hall + ICP in XE_CONTINGENCY.
    let id = &ids()[0];
    assert_eq!(q(&r, id, Mode::AirPrimary, "mdot_xe_tank_kg_s").value, Some(1e-8));
    assert_eq!(q(&r, id, Mode::XeContingency, "mdot_xe_tank_kg_s").value, Some(1e-6 + 1e-8));
}

#[test]
fn al03_xe_ledger_closes_exactly() {
    let r = integrate(&tk::al03(ids())).unwrap();
    let m = total(&r, "M_xe_total_kg").value.unwrap();
    assert!((m - 0.3603).abs() <= 1e-15, "{m}");
    let end = r.mass.m_xe_end_kg.value.unwrap();
    assert!((end - 4.6397).abs() <= 1e-15, "{end}");
    let usable = r.mass.m_xe_usable_end_kg.value.unwrap();
    assert!((usable - 3.8897).abs() <= 1e-15, "{usable}");
    assert_eq!(cons(&r.mass.conservation, "CONS-M1").holds, Some(true));
    assert_eq!(cons(&r.mass.conservation, "CONS-M2").holds, Some(true));
    assert_eq!(r.mass.m_wet_start_kg.value, Some(35.0));
    assert_eq!(total(&r, "n_start_attempts").value, Some(3.0));
}

#[test]
fn al04_time_accounting_and_schedule_refusals() {
    let base = tk::al01(ids());
    let with = |segs: Vec<abep_mission::integration::model::Segment>| {
        let mut i = base.clone();
        i.schedule = Some(tk::schedule(segs, vec![]));
        integrate(&i).unwrap()
    };
    let (a, b) = (&ids()[0], &ids()[1]);
    // (b) one dyadic sliver too long: OUT_OF_DOMAIN with the exact residual (FT-13).
    let r = with(vec![seg("A", "AIR_PRIMARY", a, 15000.0), seg("C", "NON_FIRING", b, 11280.0 + 2f64.powi(-30))]);
    assert_eq!(r.schedule.status, EvalStatus::OutOfDomain);
    assert_eq!(r.schedule.time_accounting.as_ref().unwrap().residual_vs_mission_hours_h, 2f64.powi(-30));
    assert!(r.schedule.totals.values().all(|x| x.value.is_none() && x.status == EvalStatus::OutOfDomain));
    // (c) firing hours one hour short.
    let r = with(vec![seg("A", "AIR_PRIMARY", a, 14999.0), seg("C", "NON_FIRING", b, 11281.0)]);
    assert_eq!(r.schedule.status, EvalStatus::OutOfDomain);
    assert!(!r.schedule.time_accounting.as_ref().unwrap().closes_firing_hours_exactly);
    // (d) mixed mode (FT-07).
    let r = with(vec![seg("A", "AIR_PRIMARY+XE_CONTINGENCY", a, 15000.0), seg("C", "NON_FIRING", b, 11280.0)]);
    assert_eq!(r.schedule.status, EvalStatus::OutOfDomain);
    // (e) duplicate id: MODEL_ERROR.
    let r = with(vec![seg("A", "AIR_PRIMARY", a, 15000.0), seg("A", "NON_FIRING", b, 11280.0)]);
    assert_eq!(r.schedule.status, EvalStatus::ModelError);
    // (f) non-member state (FT-08).
    let r = with(vec![seg("A", "AIR_PRIMARY", "not-a-state", 15000.0), seg("C", "NON_FIRING", b, 11280.0)]);
    assert_eq!(r.schedule.status, EvalStatus::OutOfDomain);
    // non-positive duration.
    let r = with(vec![
        seg("A", "AIR_PRIMARY", a, 15000.0),
        seg("Z", "NON_FIRING", b, 0.0),
        seg("C", "NON_FIRING", b, 11280.0),
    ]);
    assert_eq!(r.schedule.status, EvalStatus::OutOfDomain);
}

#[test]
fn al05_status_propagation_and_parametric_layer() {
    let mut inp = tk::al01(ids());
    let (a, b) = (ids()[0].clone(), ids()[1].clone());
    inp.schedule = Some(tk::schedule(
        vec![
            seg("A", "AIR_PRIMARY", &a, 7500.0),
            seg("B", "AIR_PRIMARY", &b, 7500.0),
            seg("C", "NON_FIRING", &a, 11280.0),
        ],
        vec![],
    ));
    let cell = inp.states.get_mut(&(b.clone(), Mode::AirPrimary)).unwrap();
    cell.quantities.insert("mdot_atm_delivered_kg_s".into(), syn_absent("kg s-1", EvalStatus::NotEvaluated, "SYN_NE"));
    let r = integrate(&inp).unwrap();
    let t = total(&r, "M_atm_delivered_kg");
    assert_eq!((t.status, t.value, t.parametric.is_none()), (EvalStatus::NotEvaluated, None, true));
    let cell = inp.states.get_mut(&(b, Mode::AirPrimary)).unwrap();
    let par = syn_absent("kg s-1", EvalStatus::IncompleteEvidence, "SYN_IE")
        .with_parametric(3e-6, PARAMETRIC_SENSITIVITY_ONLY, "syn")
        .unwrap();
    cell.quantities.insert("mdot_atm_delivered_kg_s".into(), par);
    let r = integrate(&inp).unwrap();
    let t = total(&r, "M_atm_delivered_kg");
    assert_eq!((t.status, t.value), (EvalStatus::IncompleteEvidence, None));
    let p = t.parametric.as_ref().unwrap();
    assert_eq!(p.value, 1e-6 * (7500.0 * 3600.0) + 3e-6 * (7500.0 * 3600.0));
}

#[test]
fn al07_routing_table() {
    let id = &ids()[0];
    let rec = |gas| integrate(&tk::inputs(&ids()[..3], gas)).unwrap();
    let r = rec(IcpGasMode::GReuse);
    let x = q(&r, id, Mode::AirPrimary, "mdot_xe_tank_kg_s");
    assert_eq!(
        (x.value, x.evidence_class.as_str(), x.source.as_str()),
        (Some(0.0), "structural", "STRUCTURAL_ZERO_BY_ROUTING")
    );
    assert_eq!(q(&r, id, Mode::XeContingency, "mdot_xe_tank_kg_s").value, Some(tk::rate("mdot_hall_anode_kg_s", 0)));
    assert_eq!(q(&r, id, Mode::XeContingency, "mdot_atm_consumed_kg_s").value, Some(0.0));
    assert_eq!(q(&r, id, Mode::AirPrimary, "mdot_atm_consumed_kg_s").value, Some(tk::rate("mdot_hall_anode_kg_s", 0)));
    assert_eq!(q(&r, id, Mode::NonFiring, "mdot_xe_tank_kg_s").source, "STRUCTURAL_ZERO_NON_FIRING");
    assert_eq!(q(&r, id, Mode::NonFiring, "thrust_N").value, Some(0.0));
    let fb = q(&r, id, Mode::AirPrimary, "feed_balance_kg_s").value.unwrap();
    assert_eq!(fb, tk::rate("mdot_atm_delivered_kg_s", 0) - tk::rate("mdot_hall_anode_kg_s", 0));
    assert!(matches!(r.field(id, Mode::XeContingency, "feed_balance_kg_s"), Some(Field::NotApplicable { .. })));
    let r = rec(IcpGasMode::GAtm);
    assert_eq!(q(&r, id, Mode::XeContingency, "mdot_xe_tank_kg_s").status, EvalStatus::IncompleteEvidence);
    assert_eq!(q(&r, id, Mode::XeContingency, "mdot_atm_consumed_kg_s").status, EvalStatus::IncompleteEvidence);
    assert_eq!(
        q(&r, id, Mode::AirPrimary, "mdot_atm_consumed_kg_s").value,
        Some(tk::rate("mdot_hall_anode_kg_s", 0) + 1e-8)
    );
    assert_eq!(q(&r, id, Mode::AirPrimary, "mdot_xe_tank_kg_s").value, Some(0.0));
    let r = rec(IcpGasMode::GXe);
    assert_eq!(q(&r, id, Mode::AirPrimary, "mdot_xe_tank_kg_s").value, Some(1e-8));
    // NOT_EVALUATED operand -> NOT_EVALUATED, never a zero; a parametric operand -> parametric layer only.
    let mut inp = tk::inputs(&ids()[..3], IcpGasMode::GXe);
    tk::set_all(&mut inp, "mdot_icp_dedicated_kg_s", syn_absent("kg s-1", EvalStatus::NotEvaluated, "SYN"));
    let r = integrate(&inp).unwrap();
    let x = q(&r, id, Mode::AirPrimary, "mdot_xe_tank_kg_s");
    assert_eq!((x.status, x.value), (EvalStatus::NotEvaluated, None));
    tk::set_all(
        &mut inp,
        "mdot_icp_dedicated_kg_s",
        syn_absent("kg s-1", EvalStatus::IncompleteEvidence, "SYN")
            .with_parametric(2e-8, PARAMETRIC_SENSITIVITY_ONLY, "s")
            .unwrap(),
    );
    let r = integrate(&inp).unwrap();
    let x = q(&r, id, Mode::XeContingency, "mdot_xe_tank_kg_s");
    assert_eq!((x.value, x.parametric.as_ref().unwrap().value), (None, tk::rate("mdot_hall_anode_kg_s", 0) + 2e-8));
}

#[test]
fn al08_ao_fluence_is_bracketed_by_pb_ao_for_200_schedules() {
    for seed in 0..200u64 {
        let r = integrate(&tk::al08(ids(), seed)).unwrap();
        assert_eq!(r.schedule.status, EvalStatus::Evaluated, "seed {seed}");
        let phi = total(&r, "Phi_AO_m2").value.unwrap();
        let (lo, hi) = (r.ao_fluence_bound.lower_m2.unwrap(), r.ao_fluence_bound.upper_m2.unwrap());
        assert!(lo <= phi && phi <= hi, "seed {seed}: {lo} <= {phi} <= {hi}");
        assert_eq!(r.ao_fluence_bound.label, "PARAMETRIC_BOUND");
    }
}

#[test]
fn al09_cancellation_is_exact() {
    let r = integrate(&tk::al09(ids())).unwrap();
    assert_eq!(total(&r, "M_atm_delivered_kg").value, Some(3600.0));
}

#[test]
fn al10_derived_quantities() {
    let id = &ids()[0];
    let mut inp = tk::inputs(&ids()[..2], IcpGasMode::GReuse);
    let r = integrate(&inp).unwrap();
    assert_eq!(q(&r, id, Mode::AirPrimary, "drag_total_N").value, Some(0.004 + 0.003));
    assert_eq!(q(&r, id, Mode::AirPrimary, "t_minus_d_N").value, Some(0.012 - (0.004 + 0.003)));
    assert_eq!(q(&r, id, Mode::NonFiring, "t_minus_d_N").value, Some(0.0 - (0.004 + 0.003)));
    tk::set_all(&mut inp, "drag_body_N", syn_absent("N", EvalStatus::NotEvaluated, "HOST_SPACECRAFT_DRAG_ICD_ABSENT"));
    let r = integrate(&inp).unwrap();
    let t = q(&r, id, Mode::AirPrimary, "t_minus_d_N");
    assert_eq!((t.status, t.value, t.parametric.is_none()), (EvalStatus::NotEvaluated, None, true));
    let mut inp = tk::inputs(&ids()[..2], IcpGasMode::GReuse);
    tk::set_all(
        &mut inp,
        "drag_intake_N",
        syn_absent("N", EvalStatus::IncompleteEvidence, "SYN")
            .with_parametric(0.005, PARAMETRIC_SENSITIVITY_ONLY, "s")
            .unwrap(),
    );
    let r = integrate(&inp).unwrap();
    let t = q(&r, id, Mode::AirPrimary, "t_minus_d_N");
    assert_eq!((t.value, t.parametric.as_ref().unwrap().value), (None, 0.012 - (0.005 + 0.003)));
    assert_eq!(t.parametric.as_ref().unwrap().label, PARAMETRIC_SENSITIVITY_ONLY);
}

#[test]
fn al11_planning_cases_are_parametric_and_none_is_selected() {
    let r = integrate(&tk::al03(ids())).unwrap();
    let m = total(&r, "M_xe_total_kg").value.unwrap();
    assert_eq!(r.mass.planning_cases.len(), 3);
    for (pc, c) in r.mass.planning_cases.iter().zip([2.0, 5.0, 10.0]) {
        assert_eq!(pc.m_xe_end_kg.status, EvalStatus::NotEvaluated);
        assert_eq!(pc.m_xe_end_kg.value, None);
        let p = pc.m_xe_end_kg.parametric.as_ref().unwrap();
        assert_eq!(p.label, "PARAMETRIC_PLANNING_CASE");
        assert!((p.value - (c - m)).abs() <= 1e-15 * c);
    }
    assert!(!serde_json::to_string(&r.mass).unwrap().contains("selected\""));
    let r = integrate(&tk::inputs(&ids()[..3], IcpGasMode::GReuse)).unwrap();
    assert!(r.mass.planning_cases.iter().all(|p| p.m_xe_end_kg.parametric.is_none()));
}

#[test]
fn ft01_to_ft05_todays_run_fails_closed() {
    let r = &today().record;
    assert_eq!(r.states.len(), 196);
    for s in &r.states {
        for mode in [Mode::AirPrimary, Mode::XeContingency] {
            for k in ["I_d_A", "thrust_N", "mdot_hall_anode_kg_s"] {
                let x = q(r, &s.state_id, mode, k);
                assert_eq!((x.status, x.value), (EvalStatus::NotEvaluated, None));
                assert!(x.reasons.iter().any(|y| y.code == "CREDIBLE_HALL_TRANSPORT_SET_EMPTY"));
            }
            let h = s.modes[mode.as_str()].hall_state.as_ref().unwrap();
            assert_eq!((h.status, h.label.is_none()), (EvalStatus::NotEvaluated, true));
            let e = q(r, &s.state_id, mode, "I_ecap_A");
            assert_eq!((e.status, e.value), (EvalStatus::NotEvaluated, None));
            assert!(e.reasons.iter().any(|y| y.code == "NP_ICP_NOT_ADMITTED"));
            assert_eq!(q(r, &s.state_id, mode, "t_minus_d_N").value, None);
        }
        for k in ["rho_kg_m3", "ao_flux_m2_s", "freestream_mass_flux_kg_m2_s", "v_orbital_m_s"] {
            assert!(q(r, &s.state_id, Mode::AirPrimary, k).value.is_some());
        }
    }
    // FT-03: no schedule.
    assert_eq!(r.schedule.status, EvalStatus::NotEvaluated);
    assert!(r.schedule.totals.values().all(|t| t.value.is_none() && t.parametric.is_none()));
    assert!(r.ao_fluence_bound.lower_m2.is_some());
    assert_eq!(r.ao_fluence_bound.evidence_status_of_fluence, EvalStatus::NotEvaluated);
    // FT-04: Xe load not frozen; planning cases carried together.
    assert_eq!(r.mass.m_xe_loaded_kg.status, EvalStatus::NotEvaluated);
    assert_eq!(r.mass.planning_cases.iter().map(|p| p.m_xe_loaded_kg).collect::<Vec<_>>(), vec![2.0, 5.0, 10.0]);
    // FT-05: Q-1 everywhere; values only on EVALUATED quantities; structural zeros only at the registered cells.
    for s in &r.states {
        for (m, cell) in &s.modes {
            for (k, f) in &cell.fields {
                if let Field::Q(x) = f {
                    x.validate().unwrap();
                    if x.evidence_class == "structural" {
                        let ok = matches!(
                            (m.as_str(), k.as_str()),
                            ("AIR_PRIMARY", "mdot_xe_tank_kg_s")
                                | ("XE_CONTINGENCY", "mdot_atm_consumed_kg_s")
                                | ("NON_FIRING", "mdot_xe_tank_kg_s" | "mdot_atm_consumed_kg_s" | "thrust_N")
                        );
                        assert!(ok, "unregistered structural zero {m}/{k}");
                    } else if x.value.is_some() {
                        assert_eq!(x.evidence_class, "model-derived", "{m}/{k}");
                    }
                }
            }
        }
    }
}

#[test]
fn ft06_other_configuration_is_model_error() {
    let mut inp = tk::inputs(&ids()[..2], IcpGasMode::GReuse);
    inp.configuration = ["hall_c1", "_reference"].concat();
    assert_eq!(integrate(&inp).unwrap_err().status(), EvalStatus::ModelError);
}

#[test]
fn ft09_ft15_vocabulary() {
    let forbidden_src = [
        ["La", "B6"].concat(),
        ["hollow", "_cathode"].concat(),
        ["kee", "per"].concat(),
        ["hea", "ter"].concat(),
        ["c1", "_"].concat(),
    ];
    let dir = repo().join("crates/abep-mission/src");
    let mut files = vec![
        dir.join("propagation.rs"),
        dir.join("bin/abep_mission_env_parity.rs"),
        dir.join("bin/abep_mission_integration.rs"),
    ];
    for e in std::fs::read_dir(dir.join("integration")).unwrap() {
        files.push(e.unwrap().path());
    }
    for f in files {
        let text = std::fs::read_to_string(&f).unwrap();
        for t in &forbidden_src {
            assert!(!text.contains(t.as_str()), "{} contains {t}", f.display());
        }
    }
    let json: serde_json::Value = serde_json::from_str(&today().record.to_json()).unwrap();
    fn keys(v: &serde_json::Value, out: &mut Vec<String>) {
        match v {
            serde_json::Value::Object(m) => {
                for (k, x) in m {
                    out.push(k.to_lowercase());
                    keys(x, out);
                }
            }
            serde_json::Value::Array(a) => a.iter().for_each(|x| keys(x, out)),
            _ => {}
        }
    }
    let mut ks = Vec::new();
    keys(&json, &mut ks);
    for k in ks {
        for bad in ["pass", "fail", "comply", "margin", "limit", "threshold", "feasible", "chk_", "rfp_", "ic_"] {
            assert!(!k.starts_with(bad) && k != bad, "forbidden key {k}");
        }
    }
    // FT-15: cathode vocabulary in an input identifier is refused.
    let mut inp = tk::inputs(&ids()[..2], IcpGasMode::GReuse);
    let cell = inp.states.get_mut(&(ids()[0].clone(), Mode::AirPrimary)).unwrap();
    cell.hall_state = Some(Label {
        status: EvalStatus::Evaluated,
        label: Some(["hollow ", "cathode op"].concat()),
        source: "s".into(),
        reasons: vec![],
    });
    assert_eq!(integrate(&inp).unwrap_err().status(), EvalStatus::ModelError);
}

#[test]
fn ft10_no_requirement_or_assessment_file_is_read() {
    let files = &today().files_read;
    assert!(
        !files.iter().any(|f| f.starts_with("config/requirements") || f.starts_with("config/assessment")),
        "{files:?}"
    );
    let cons: Vec<&String> = files.iter().filter(|f| f.starts_with("config/constraints")).collect();
    assert_eq!(cons.len(), 1);
    assert!(cons[0].starts_with("config/constraints/engineering_constraints_v1.json (environment layer"));
}

#[test]
fn ft11_no_xe_from_duration() {
    // An XE rate exists in every cell, but the schedule holds no XE hours: exact zero, never rate x hours.
    let r = integrate(&tk::al01(ids())).unwrap();
    let x = total(&r, "M_xe_continuous_kg");
    assert_eq!((x.status, x.value), (EvalStatus::Evaluated, Some(0.0)));
    let t = total(&today().record, "M_xe_total_kg");
    assert_eq!((t.status, t.value), (EvalStatus::NotEvaluated, None));
}

#[test]
fn ft12_parametric_values_never_reach_evidence() {
    let r = &today().record;
    for e in &r.envelopes {
        if e.worst_status != EvalStatus::Evaluated {
            assert!(e.min.is_none() && e.max.is_none(), "{}/{}", e.mode, e.field);
        }
    }
    // An F1 design point of the committed table (area synthetic): the intake-face drag is parametric only, and
    // everything downstream of it stays without an evidence value.
    let (t, _) = abep_mission::intake_drag::load_drag_table(&repo()).unwrap();
    let e = &t.entries[0];
    let p = abep_mission::statewise_td::DesignPoint {
        area_m2: 0.05,
        l_over_d: e.l_over_d,
        phi: e.phi,
        scenario: e.scenario.clone(),
    };
    let run =
        run_admitted(&repo(), &TodayOptions { design_point: Some(p.clone()), rust_commit: "test".into() }).unwrap();
    let id = &ids()[0];
    let d = q(&run.record, id, Mode::AirPrimary, "drag_intake_N");
    assert_eq!((d.status, d.value), (EvalStatus::IncompleteEvidence, None));
    let par = d.parametric.as_ref().unwrap();
    assert_eq!(par.label, PARAMETRIC_SENSITIVITY_ONLY);
    assert_eq!(par.value, 0.05 * t.get(&p.scenario, p.l_over_d, p.phi, id).unwrap().drag_per_area_n_m2);
    let total_drag = q(&run.record, id, Mode::AirPrimary, "drag_total_N");
    assert_eq!(
        (total_drag.status, total_drag.value, total_drag.parametric.is_none()),
        (EvalStatus::NotEvaluated, None, true)
    );
    let env = run.record.envelopes.iter().find(|x| x.field == "drag_intake_N" && x.mode == "AIR_PRIMARY").unwrap();
    assert!(env.min.is_none() && env.parametric_min.is_some());
    // A design point outside the committed F1 table is refused, never filled.
    let off = abep_mission::statewise_td::DesignPoint { phi: 0.123456, ..p };
    assert_eq!(
        run_admitted(&repo(), &TodayOptions { design_point: Some(off), rust_commit: "test".into() })
            .unwrap_err()
            .status(),
        EvalStatus::OutOfDomain
    );
}

#[test]
fn ft14_malformed_input_quantity_is_model_error() {
    let mut inp = tk::inputs(&ids()[..2], IcpGasMode::GReuse);
    let cell = inp.states.get_mut(&(ids()[0].clone(), Mode::AirPrimary)).unwrap();
    let mut bad = syn("N", 1.0);
    bad.status = EvalStatus::NotEvaluated;
    cell.quantities.insert("thrust_N".into(), bad);
    assert_eq!(integrate(&inp).unwrap_err().status(), EvalStatus::ModelError);
    let mut inp = tk::inputs(&ids()[..2], IcpGasMode::GReuse);
    inp.states.get_mut(&(ids()[0].clone(), Mode::AirPrimary)).unwrap().quantities.remove("thrust_N");
    assert_eq!(integrate(&inp).unwrap_err().status(), EvalStatus::ModelError);
}

#[test]
fn det01_det02_cons_s1() {
    let a = integrate(&tk::al08(ids(), 7)).unwrap().to_json();
    let b = integrate(&tk::al08(ids(), 7)).unwrap().to_json();
    assert_eq!(a, b);
    let r = &today().record;
    let again = run_admitted(&repo(), &TodayOptions { design_point: None, rust_commit: "test".into() }).unwrap();
    assert_eq!(r.to_json(), again.record.to_json());
    assert_eq!((r.implementation, r.prereg_sha256, r.validation_status), ("rust", PREREG_SHA256, "NOT_VALIDATED"));
    for k in ["design_state_set_sha256", "config_manifest_sha256", "mission_scenario_sha256", "mass_power_a9_v5_sha256"]
    {
        assert!(r.provenance.input_hashes.contains_key(k), "{k}");
    }
    assert_eq!(r.states.iter().map(|s| s.state_id.clone()).collect::<Vec<_>>(), *ids());
    assert!(r.states.iter().all(|s| s.modes.len() == 3));
    assert_eq!(r.status_summary.n_cells, 196 * 3);
}
