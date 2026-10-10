//! SC-WP-02 gas-path invariants of abep-gaspath (CLAUDE.md rule 4 and the registered Rust-only invariants):
//!
//! * CONS-P-01: the source mass balance intake -> compressor -> plenum closes exactly (to rounding) at every steady
//!   operating point with a computed record; the intake outputs enter as explicit plain data (no intake crate).
//! * CONS-P-02: node-wise balances below MASS_TOL; CONS-F-01 through the filter case; CONS-C-01/02 on the compressor.
//! * INV-F-02 / INV-C-03 / INV-P-03: every status maps to exactly one abep_types::EvalStatus (fail closed).
//! * INV-P-05: no requirement threshold in the raw plenum / feed physics.
//!
//! The intake states below are TEST DATA (not evidence): the shape of an F1 IF-A1 record (per-species forward mass
//! flow, passive pressure, back-escape ratio at T = 350 K) with values in the range of the committed F1 core view.

use abep_gaspath::compressor::{Ctx, DragCompressor};
use abep_gaspath::compressor_synthesis as cs;
use abep_gaspath::filter::FilterStatus;
use abep_gaspath::materials::MaterialsView;
use abep_gaspath::plenum_feed::{self as pf, Chain, CompressorPlant, FilterCase, IntakeState, Plenum};
use abep_gaspath::rotor_strength::{self as rs, Registry};
use abep_gaspath::{reservoir, upstream as u13, PyClass, SPECIES};
use abep_types::constants::{species_mass, K_B};
use abep_types::EvalStatus;
use serde_json::{json, Map, Value};

fn mats() -> MaterialsView {
    // materials.DB Ti6Al4V values (abep_sim/materials.py at the registered python_commit; DIV-C-02 / DIV-P-03)
    serde_json::from_value(json!({"Ti6Al4V": {"density": 4430.0, "yield_MPa": 880.0, "T_max_K": 700.0,
        "gamma_min": 0.01, "gamma0": 0.1, "gamma_Ea_eV": 0.08}}))
    .expect("materials")
}

fn mass(s: &str) -> f64 {
    species_mass(s).expect("species mass")
}

fn intake(scale: f64, area: f64, state: &str, f1_status: &str) -> IntakeState {
    IntakeState {
        candidate: format!("A{area}_Ld3_phi0.8"),
        area_m2: area,
        state: state.into(),
        scenario: "TEST".into(),
        t_k: 350.0,
        mdot_fwd_kgps: [7.147e-7 * scale * area, 8.081e-7 * scale * area, 5.045e-8 * scale * area],
        p_passive_pa: [2.024e-3 * scale, 1.714e-3 * scale, 1.009e-4 * scale],
        k_back: [0.4719, 0.4762, 0.4724],
        f1_status: f1_status.into(),
        source: "TEST DATA (not evidence)".into(),
        alt_km: 200.0,
    }
}

fn design(id: &str, n_turbo: i64, rpm: f64, n_drag: i64, hub: f64) -> Map<String, Value> {
    let a = 0.1128299365_f64;
    let r = (a / (std::f64::consts::PI * (1.0 - hub * hub))).sqrt();
    let v = json!({"id": id, "N_turbo": n_turbo, "A_turbo_m2": a, "R_turbo_m": r, "rpm": rpm, "N_drag": n_drag,
                   "rotor_material": "Ti6Al4V", "hub_ratio": hub});
    v.as_object().cloned().expect("design")
}

fn chains(m: &MaterialsView, reg: &Registry) -> Vec<Chain> {
    let ctx = Ctx { materials: m, registry: reg };
    let filters: Vec<FilterCase> = vec![
        pf::filter_none().expect("none"),
        pf::filter_parametric(0.7).expect("t0.7"),
        pf::filter_parametric(0.35).expect("t0.35"),
        pf::filter_placeholder().expect("placeholder"),
    ];
    let plants: Vec<CompressorPlant> = [
        design("TEST-T3-D0", 3, 16000.0, 0, 0.5),
        design("TEST-T6-D2", 6, 9000.0, 2, 0.25),
        design("TEST-T2-D1", 2, 12000.0, 1, 0.0),
    ]
    .iter()
    .map(|d| CompressorPlant::from_design(ctx, d, pf::T_CHAIN_K).expect("plant"))
    .collect();
    let plenums = [
        Plenum::new(2e-3, 0.0, "TEST", 5e-8, pf::T_CHAIN_K).expect("plenum"),
        Plenum::new(5e-2, 0.02, "TEST", 1e-7, pf::T_CHAIN_K).expect("plenum"),
        Plenum::new(4e-4, 0.08, "TEST", 0.0, pf::T_CHAIN_K).expect("plenum"),
    ];
    let intakes = [
        intake(1.0, 0.25, "h200_f150", "FEASIBLE_AT_STATE"),
        intake(3.0, 0.5, "TEST-DENSE", "FEASIBLE_AT_STATE"),
        intake(0.3, 1.0, "TEST-THIN", "FEASIBLE_AT_STATE"),
    ];
    let mut out = vec![];
    for it in &intakes {
        for f in &filters {
            for p in &plants {
                for pl in &plenums {
                    out.push(Chain { intake: it.clone(), filt: f.clone(), plant: p.clone(), plenum: pl.clone() });
                }
            }
        }
    }
    out
}

fn f(v: &Value) -> f64 {
    v.as_f64().expect("number")
}

fn sum3(v: &Value) -> f64 {
    SPECIES.iter().map(|s| f(&v[*s])).sum()
}

#[test]
fn intake_compressor_plenum_mass_balance_closes() {
    let m = mats();
    let reg = Registry::default();
    let (mut n_closed, mut worst) = (0usize, 0.0_f64);
    for ch in chains(&m, &reg) {
        // forward source mass flow at the compressor-inlet node: sum_s f_s m_s / (k T)
        let co = ch.node_coefficients(1.0).expect("coefficients");
        let fwd: f64 = (0..3).map(|i| co[i].f * mass(SPECIES[i]) / (K_B * ch.intake.t_k)).sum();
        for target in [2e-3, 5e-3, 1e-2, 3e-2, 8e-2] {
            let rec = pf::steady_operating_point(&ch, &m, target, 1.0, 1.0).expect("steady record");
            let status = rec["status"].as_str().expect("status");
            assert!(pf::REASONS.iter().all(|r| !status.contains(r)));
            if rec.get("mdot_intake_net_kgps").is_none() || rec["offered"].is_null() {
                assert!(rec["offered"].is_null(), "no state offered without a computed in-domain record");
                continue;
            }
            // CONS-P-01: sum_s intake net = sum_s (H-1 feed + plenum leak); O -> O2 recombination conserves mass
            let net = sum3(&rec["mdot_intake_net_kgps"]);
            let out = sum3(&rec["offered"]["mdot_s_kgps"]) + sum3(&rec["mdot_plenum_leak_kgps"]);
            let resid = (net - out).abs();
            assert!(resid <= 1e-12 * fwd, "CONS-P-01: residual {resid:e} kg/s vs forward source {fwd:e} kg/s");
            worst = worst.max(resid / fwd);
            // CONS-P-02: node-wise balances of the record (inlet node, plenum) below MASS_TOL
            let cr = &rec["conservation_residual_rel"];
            assert!(f(&cr["inlet_node"]) <= pf::MASS_TOL && f(&cr["plenum"]) <= pf::MASS_TOL, "CONS-P-02");
            // the compressor gross flow minus its back-leak is what enters the plenum
            let gross = sum3(&rec["mdot_compressor_gross_kgps"]) - sum3(&rec["mdot_compressor_backleak_kgps"]);
            assert!((gross - out).abs() <= 1e-9 * fwd.max(gross.abs()), "plenum node: {gross:e} vs {out:e}");
            n_closed += 1;
        }
    }
    assert!(n_closed > 20, "the test chains must produce computed records ({n_closed})");
    assert!(worst <= 1e-12);
}

#[test]
fn filter_and_compressor_balances_close() {
    let m = mats();
    let reg = Registry::default();
    let ctx = Ctx { materials: &m, registry: &reg };
    // CONS-F-01 through every filter case: D / E fractions of a loss-free element conserve the incident flow
    for tau in [0.9, 0.5, 0.1] {
        let fc = pf::filter_parametric(tau).expect("filter");
        for i in 0..3 {
            let s = (fc.t_f[i] + fc.r_f[i], fc.t_b[i] + fc.r_b[i]);
            assert!((s.0 - 1.0).abs() <= 1e-15 && (s.1 - 1.0).abs() <= 1e-15, "loss-free fractions sum to 1");
        }
    }
    // CONS-C-01 / CONS-C-02 on a converged self-consistent run
    let c = DragCompressor { n_stages: 0, turbo_rows: 2, leak_conductance_m3_s: 1e-5, ..DragCompressor::default() };
    let mdot = vec![("O".to_string(), 1e-7), ("N2".to_string(), 1e-7), ("O2".to_string(), 1e-8)];
    let r = c.run(ctx, 0.02, &mdot, true).expect("run");
    assert_eq!(r["solver_status"], "CONVERGED");
    for (s, v) in &mdot {
        assert_eq!(f(&r["delivered_kgps"][s.as_str()]), *v, "CONS-C-01 delivered = captured (copied)");
    }
    let (p_el, p_gas, p_bear, tq) = (f(&r["P_el_W"]), f(&r["P_gas_W"]), f(&r["P_bear_W"]), f(&r["torque_Nm"]));
    let omega = c.rpm * 2.0 * std::f64::consts::PI / 60.0;
    assert!((p_el - ((p_gas + p_bear) / c.eta_motor + c.p_ctrl_w)).abs() <= 1e-12 * p_el, "CONS-C-02");
    assert!((tq * omega - (p_gas + p_bear)).abs() <= 1e-12 * p_el, "CONS-C-02 torque");
}

#[test]
fn reservoir_balance_closes() {
    let m = mats();
    let r = reservoir::Reservoir::default();
    for scale in [0.1, 1.0, 10.0] {
        let mdot = vec![("O".into(), 4e-7 * scale), ("N2".into(), 3e-7 * scale), ("O2".into(), 2e-8 * scale)];
        let s = r.steady_state(&m, &mdot).expect("steady");
        if s["converged"] == true {
            assert!(f(&s["balance_residual_rel"]) <= 1e-12, "CONS-P-04");
        }
    }
}

#[test]
fn every_status_maps_to_one_eval_status() {
    // INV-F-02
    assert_eq!(FilterStatus::Numeric.eval_status(), EvalStatus::Evaluated);
    assert_eq!(FilterStatus::NoFilterIdentity.eval_status(), EvalStatus::Evaluated);
    assert_eq!(FilterStatus::RefusedTbd.eval_status(), EvalStatus::IncompleteEvidence);
    assert_eq!(FilterStatus::OutOfDomain.eval_status(), EvalStatus::OutOfDomain);
    assert_eq!(FilterStatus::NonphysicalInput.eval_status(), EvalStatus::OutOfDomain);
    // INV-C-03
    let none: Vec<String> = vec![];
    assert_eq!(cs::design_eval_status(cs::ST_NOT_EVALUATED_MATERIAL_BASIS, &none), EvalStatus::NotEvaluated);
    assert_eq!(cs::design_eval_status(cs::ST_NOT_EVALUATED, &none), EvalStatus::NotEvaluated);
    assert_eq!(cs::design_eval_status(cs::ST_NOT_EVALUATED_OOD, &none), EvalStatus::OutOfDomain);
    assert_eq!(cs::design_eval_status(cs::ST_REJECTED, &[cs::R_MODEL.to_string()]), EvalStatus::ModelError);
    assert_eq!(cs::design_eval_status(cs::ST_REJECTED, &[cs::R_NONCONV.to_string()]), EvalStatus::ModelError);
    assert_eq!(cs::design_eval_status(cs::ST_REJECTED, &[cs::R_STRESS.to_string()]), EvalStatus::Evaluated);
    assert_eq!(cs::design_eval_status(cs::ST_FEASIBLE, &none), EvalStatus::Evaluated);
    assert_eq!(abep_gaspath::compressor::solver_eval_status("MODEL_NOT_CONVERGED"), EvalStatus::ModelError);
    assert_eq!(abep_gaspath::compressor::solver_eval_status("CONVERGED"), EvalStatus::Evaluated);
    assert_eq!(
        abep_gaspath::compressor::gaede_eval_status(abep_gaspath::compressor::GAEDE_OUT_OF_DOMAIN),
        EvalStatus::OutOfDomain
    );
    assert_eq!(rs::qualification_eval_status(rs::Q_NOT_EVALUATED_MATERIAL_BASIS), EvalStatus::NotEvaluated);
    assert_eq!(rs::qualification_eval_status(rs::Q_NOT_EVALUATED_OUT_OF_DOMAIN), EvalStatus::OutOfDomain);
    let slot = cs::compressor_ledger_slot(None, "");
    assert_eq!(slot["status"], "NOT_EVALUATED");
    assert_eq!(slot["ledger_label"], "OFFICIAL_A9_02_STATE");
    let slot = cs::compressor_ledger_slot(Some(42.0), "");
    assert_eq!(slot["status"], "NOT_EVALUATED", "a model-derived draw never fills the official slot");
    assert_eq!(slot["ledger_label"], "PARAMETRIC_SENSITIVITY");
    // INV-P-03
    assert_eq!(pf::status_eval(pf::ST_FEASIBLE), EvalStatus::Evaluated);
    assert_eq!(pf::status_eval(pf::ST_INFEASIBLE), EvalStatus::Evaluated);
    assert_eq!(pf::status_eval(pf::ST_OOD), EvalStatus::OutOfDomain);
    assert_eq!(pf::status_eval(pf::ST_MODEL_ERROR), EvalStatus::ModelError);
    assert_eq!(pf::status_eval(pf::ST_NOT_EVALUATED), EvalStatus::NotEvaluated);
    assert_eq!(reservoir::solver_eval_status(false), EvalStatus::ModelError);
    assert_eq!(u13::feed_requirement_eval_status("PENDING_EVIDENCE"), EvalStatus::NotEvaluated);
    assert_eq!(u13::domain_eval_status(u13::NOT_EVALUATED_OOD), EvalStatus::OutOfDomain);
    assert_eq!(PyClass::RepresentativeSelectionRefused.status(), EvalStatus::NotEvaluated);
    assert_eq!(PyClass::A913RuleError.status(), EvalStatus::NotEvaluated);
    assert_eq!(PyClass::ZeroDivisionError.status(), EvalStatus::ModelError);
    assert_eq!(PyClass::FilterStageError.status(), EvalStatus::OutOfDomain);
    // the bisection failure is reported, never half-converged
    assert!(pf::bisection_failed(pf::A_EQ_BRACKET_M2.1, 0.0));
    assert!(pf::bisection_failed(1e-5, f64::NAN));
}

#[test]
fn strict_mode_refuses_and_no_offered_state_above_the_domain() {
    let m = mats();
    let reg = Registry::default();
    for ch in chains(&m, &reg).iter().take(12) {
        let rec = pf::evaluate(ch, &m, 0.01, pf::MODE_STRICT).expect("strict");
        assert_eq!(rec["status"], pf::ST_NOT_EVALUATED);
        assert!(rec["offered"].is_null());
        // INV-P-04: a target above P_DOMAIN_PA is never evaluated
        let rec = pf::steady_operating_point(ch, &m, 0.2, 1.0, 1.0).expect("ood");
        assert_eq!(rec["status"], pf::ST_OOD);
        assert!(rec["offered"].is_null());
    }
}

#[test]
fn no_requirement_threshold_in_raw_gas_path_physics() {
    // INV-P-05: the fixed mass-flow numbers live only in the upstream refusal guard / coverage record
    for (name, src) in [
        ("plenum_feed.rs", include_str!("../src/plenum_feed.rs")),
        ("transient.rs", include_str!("../src/transient.rs")),
        ("reservoir.rs", include_str!("../src/reservoir.rs")),
        ("compressor.rs", include_str!("../src/compressor.rs")),
        ("filter.rs", include_str!("../src/filter.rs")),
    ] {
        // RFP clause ids may appear as citations in copied record texts; requirement VALUES may not
        for forbidden in ["0.38", "3.2e-6", "3.8e-7", "1500.0", "12e-3", "25e-3"] {
            assert!(!src.contains(forbidden), "{name} carries the requirement-like literal {forbidden}");
        }
    }
}

fn basis_with_allowables(points: Vec<(f64, f64, f64)>) -> rs::RotorStrengthBasis {
    use rs::Field::{Num, Text};
    let t = |s: &str| Text(s.into());
    rs::RotorStrengthBasis {
        basis_id: t("TEST-BASIS"),
        materials_db_key: t("Ti6Al4V"),
        material_spec: t("TEST"),
        product_form: t("TEST"),
        condition: t("TEST"),
        section_thickness_range_m: Some((Num(0.01), Num(0.2))),
        design_temperature_k: Num(400.0),
        allowable_basis: t("TEST"),
        allowable_source: t("TEST"),
        allowables: Some(points.into_iter().map(|(a, b, c)| (Num(a), Num(b), Num(c))).collect()),
        density_kg_m3: Num(4430.0),
        density_source: t("TEST"),
        factor_yield: Num(1.5),
        factor_ultimate: Num(1.5),
        factors_source: t("TEST"),
        max_design_speed_rpm: Num(6e4),
        proof_spin_basis: t("TEST"),
        registration: t("TEST"),
        proof_spin_not_applicable_reason: rs::Field::Other,
        notes: String::new(),
    }
}

#[test]
fn non_finite_allowable_temperature_is_reported_not_sorted() {
    // a NaN / infinite table temperature is a basis problem (reference elif chain), never a panic
    for bad in [f64::NAN, f64::INFINITY, -1.0] {
        let b = basis_with_allowables(vec![(bad, 6e8, 7e8), (500.0, 8e8, 9e8)]);
        assert_eq!(rs::basis_problems(&b), vec!["allowables contain non-finite or non-positive values".to_string()]);
    }
    let b = basis_with_allowables(vec![(500.0, 6e8, 7e8), (300.0, 8e8, 9e8)]);
    assert_eq!(rs::basis_problems(&b), vec!["allowables must be strictly increasing in temperature".to_string()]);
    assert!(rs::basis_problems(&basis_with_allowables(vec![(300.0, 6e8, 7e8), (500.0, 8e8, 9e8)])).is_empty());
}
