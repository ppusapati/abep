//! `robust_optimizer.UQ_AXES`: every uncertainty axis named by A9.7 F8 with its treatment (scenario set, seeded Monte
//! Carlo, deterministic node, local elasticity or NOT_EVALUATED). Probabilities exist only over the quantified TPMC
//! statistics; no weight is attached to any scenario-set member.

use abep_design::records::{D, DESIGN_STATE_SET_ID, DESIGN_STATE_SET_SHA256, ORBIT_BASIS_LABEL};
use abep_types::pyjson::Value;

const F1_REL: &str = "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json";
const F3_REL: &str = "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json";
const F4_REL: &str = "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json";
const ENS_REL: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";
const MP_REL: &str = "docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json";
const P3_REL: &str = "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json";

fn axis(name: &str, treatment: &str, quantified: bool, basis: &str, source: &str) -> Value {
    D::new()
        .s("axis", name)
        .s("treatment", treatment)
        .v("quantified", Value::Bool(quantified))
        .s("basis", basis)
        .s("source", source)
        .build()
}

/// `_uq_axes()` over the F1 states (design-case reference + every required design state).
pub fn uq_axes(states: &[String]) -> Value {
    let atm = D::new()
        .s("axis", "atmosphere")
        .s("treatment", "SCENARIO_SET")
        .v("quantified", Value::Bool(false))
        .v("members", Value::List(states.iter().map(|s| Value::str(s.clone())).collect()))
        .s("design_state_set", DESIGN_STATE_SET_ID)
        .s("design_state_set_sha256", DESIGN_STATE_SET_SHA256)
        .s("orbit_basis", ORBIT_BASIS_LABEL)
        .s(
            "basis",
            "design-case reference point h200_f150 (orbit-averaged, surface build state) + every required state of the \
frozen design-state set v2 (nominal states and physical extrema of density, composition, temperature, local time and \
solar activity; A9.14 S9.8 OD3; F1 coverage_rule); no probability over the states is sourced; broad envelope, \
inclination / LTAN TBD (A9.21)",
        )
        .s("source", &format!("{F1_REL} coverage_rule"))
        .build();
    Value::List(vec![
        atm,
        axis("intake_surface_state", "SCENARIO_SET", false,
             "alpha in {0, 0.2, 0.5, 0.8, 1} (TBD, F1-P-07); no measured accommodation", F1_REL),
        axis("gas_surface_interaction", "SCENARIO_SET", false,
             "Maxwell / CLL kernels (TBD, F1-P-08); carried jointly with alpha (10 scenarios)", F1_REL),
        axis("tpmc_statistics", "SEEDED_MONTE_CARLO", true,
             "1-sigma binomial SEs of the committed F1 IF-A1 records (mdot_fwd_s, p_passive_s, independent normal draws \
per species and state) and the replicate-calibrated C_D SE (drag); model-form uncertainty is NOT in these SEs (F1 \
conventions.uncertainty)", &format!("{F1_REL} if_a1_interface, species_table")),
        axis("pointing_theta", "DETERMINISTIC_NODE", false,
             "theta = 5 deg frozen-surface node at the design-case reference point only (per-species eta_c and CR ratios \
vs theta 0); the AOCS pointing budget is TBD (F1-P-09); the required design states have no theta node",
             &format!("{F1_REL} species_table (theta_deg 5)")),
        axis("wall_recombination", "SCENARIO_SET", false,
             "WALL-G0 (gamma 0 bound) vs WALL-TI64-DB (uncited DB prior), F4-P-06 TBD", F4_REL),
        axis("compressor_performance", "LOCAL_ELASTICITY", false,
             "every DragCompressor coefficient is an uncited code default with NO sourced range (F3 coefficients, \
compressor_downselect CD-01): d ln(objective) / d ln(coefficient) by central difference; no distribution is invented",
             &format!("{F3_REL} coefficients")),
        axis("feed_state", "NOT_EVALUATED", false,
             "H-1 required inlet state TBD (F4-P-10, F5 IFD-F4-01..05); P_set is a requirement-level context axis; \
feed-path conductance steps are in F4's transient study (E3/E4)", F4_REL),
        axis("hall_response", "NOT_EVALUATED", false,
             "credible Hall set EMPTY; P5-N2 v1 INCONCLUSIVE; no admitted response map", ENS_REL),
        axis("rf_efficiency", "NOT_EVALUATED", false,
             "flight RF source efficiency TBD (MPV2-P08); RF ratings TBD_AFTER_IMPEDANCE_MAP", MP_REL),
        axis("thermal_parameters", "NOT_EVALUATED", false,
             "P3 geometry / emittance / conductance inputs TBD; chain gas temperature assumed 350 K (F4-P-01)", P3_REL),
        axis("orbit_scale_density_modulation", "NOT_EVALUATED", false,
             "F4-P-11 TBD (a revolution through the orbit-resolved states needs the TBD inclination / LTAN, A9.21); F4 \
parametric amplitudes 0.1 / 0.2 are reported there", F4_REL),
    ])
}
