//! Output schema `abep_np_thermal_output_v1` (prereg `outputs` O-01..O-17). Raw physics only: no margin, limit,
//! PASS / FAIL, compliance label, requirement threshold or HC status (FT-17). Every map is ordered, so the serialized
//! bytes are a pure function of the inputs (DET-01, DET-02).

use abep_types::EvalStatus;
use serde::Serialize;
use std::collections::BTreeMap;

pub const OUTPUT_SCHEMA: &str = "abep_np_thermal_output_v1";
pub const NOT_VALIDATED: &str = "NOT_VALIDATED";

/// O-01 run status (prereg `status_vocabulary`). `Converged` maps to `EvalStatus::Evaluated`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RunStatus {
    ModelError,
    NotEvaluated,
    IncompleteEvidence,
    OutOfDomain,
    Converged,
}

impl RunStatus {
    pub fn eval_status(self) -> EvalStatus {
        match self {
            RunStatus::ModelError => EvalStatus::ModelError,
            RunStatus::NotEvaluated => EvalStatus::NotEvaluated,
            RunStatus::IncompleteEvidence => EvalStatus::IncompleteEvidence,
            RunStatus::OutOfDomain => EvalStatus::OutOfDomain,
            RunStatus::Converged => EvalStatus::Evaluated,
        }
    }

    pub fn from_eval(s: EvalStatus) -> RunStatus {
        match s {
            EvalStatus::ModelError => RunStatus::ModelError,
            EvalStatus::NotEvaluated => RunStatus::NotEvaluated,
            EvalStatus::IncompleteEvidence => RunStatus::IncompleteEvidence,
            EvalStatus::OutOfDomain => RunStatus::OutOfDomain,
            EvalStatus::Evaluated => RunStatus::Converged,
        }
    }
}

/// O-02: one reason found by a check (status precedence in `status_vocabulary`).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct Reason {
    pub status: RunStatus,
    pub code: String,
    /// Node, key, record, link, surface or case field the reason is about.
    pub subject: String,
    pub detail: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct OrbitStats {
    pub orbit: usize,
    pub min: BTreeMap<String, f64>,
    pub max: BTreeMap<String, f64>,
    /// Time mean, sum of h_n T(t_n+1) / P (the implicit-Euler right-end rule).
    pub mean: BTreeMap<String, f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PairExchange {
    pub from: String,
    pub to: String,
    /// A_k F_kl (J_k - J_l)
    #[serde(rename = "Q_W")]
    pub q_w: f64,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct RadiationOut {
    pub per_surface: BTreeMap<String, f64>,
    pub per_node: BTreeMap<String, f64>,
    pub pairwise: Vec<PairExchange>,
}

#[derive(Debug, Clone, Serialize)]
pub struct EnvOut {
    pub solar: f64,
    pub albedo: f64,
    pub olr: f64,
    pub aero: f64,
}

/// O-11. Link flows and SCI-C radiation are positive out of the network into the boundary; SCI-B fluxes are positive
/// into the attachment node (as registered).
#[derive(Debug, Clone, Default, Serialize)]
pub struct BoundaryOut {
    #[serde(rename = "B_SC_links")]
    pub b_sc_links: BTreeMap<String, f64>,
    #[serde(rename = "B_SC_prescribed_flux_into_node")]
    pub b_sc_prescribed_flux: BTreeMap<String, f64>,
    #[serde(rename = "B_SC_radiation_to_host_surfaces")]
    pub b_sc_radiation: BTreeMap<String, f64>,
    #[serde(rename = "B_PPU_RF_links")]
    pub b_ppu_rf_links: BTreeMap<String, f64>,
    /// Booked, not solved (E-13 Q_icp_boundary_W; Q_icp_match_W when not co-located), per interface time index.
    #[serde(rename = "B_PPU_RF_booked")]
    pub b_ppu_rf_booked: BTreeMap<String, Vec<f64>>,
    #[serde(rename = "B_FEED_links")]
    pub b_feed_links: BTreeMap<String, f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CheckOut {
    pub id: String,
    /// Observed value of the checked quantity (W or J or K).
    pub observed: f64,
    /// Preregistered bound for that quantity.
    pub bound: f64,
    pub met: bool,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct EnergyBalance {
    pub node_residual_w: BTreeMap<String, f64>,
    pub global_residual_w: f64,
    #[serde(rename = "Q_scale_W")]
    pub q_scale_w: f64,
    /// Transient only: |dH_total - sum dt Q_net| at the end and its worst step.
    pub cumulative_energy_residual_j: Option<f64>,
    pub worst_step_energy_residual_j: Option<f64>,
    pub checks: Vec<CheckOut>,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct ConvergenceOut {
    pub newton_iterations: usize,
    #[serde(rename = "last_max_dT_K")]
    pub last_max_dt_k: f64,
    /// CONS-T2 u_num,t (max over nodes and accepted steps of |T_dt - T_dt/2|).
    #[serde(rename = "u_num_t_K")]
    pub u_num_t_k: Option<f64>,
    #[serde(rename = "periodic_max_dT_K")]
    pub periodic_max_dt_k: Option<f64>,
    pub accepted_steps: Option<usize>,
    pub max_newton_iterations_per_step: Option<usize>,
    pub max_step_halving_depth: Option<u32>,
    pub orbits: Option<usize>,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct DomainDiagnostics {
    /// Max over evaluated states; absent for SYNTHETIC_VERIFICATION (label BIOT_NOT_APPLICABLE_SYNTHETIC).
    pub biot_number: BTreeMap<String, f64>,
    #[serde(rename = "internal_gradient_estimate_K")]
    pub internal_gradient_estimate_k: BTreeMap<String, f64>,
    /// Per node: [T_lo, T_hi] admissible (intersection of the property ranges it uses, D-10).
    #[serde(rename = "node_property_range_K")]
    pub node_property_range_k: BTreeMap<String, [f64; 2]>,
    #[serde(rename = "time_constant_s")]
    pub time_constant_s: BTreeMap<String, f64>,
    /// D-09, orbit modes: largest node time constant / orbit period.
    pub largest_time_constant_over_period: Option<f64>,
    /// D-01 / D-02 / D-03 violations: node or record, criterion, value.
    pub violations: Vec<Reason>,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct InterfaceDerived {
    /// E-13, per interface time index.
    #[serde(rename = "Sigma_dep_H_W")]
    pub sigma_dep_h_w: Option<Vec<f64>>,
    #[serde(rename = "P_hall_exported_W")]
    pub p_hall_exported_w: Option<Vec<f64>>,
    #[serde(rename = "P_hall_unattributed_W")]
    pub p_hall_unattributed_w: Option<Vec<f64>>,
    #[serde(rename = "Sigma_I_W")]
    pub sigma_i_w: Option<Vec<f64>>,
    #[serde(rename = "Q_icp_boundary_W")]
    pub q_icp_boundary_w: Option<Vec<f64>>,
    /// Per key: (deposited on nodes, exported, booked at B_PPU_RF), per time index.
    pub deposition: BTreeMap<String, [Vec<f64>; 3]>,
    /// CONS-I2: worst |deposited + exported + booked - input| and its bound (1e-12 relative + 1e-12 W).
    #[serde(rename = "CONS_I2_residual_W")]
    pub cons_i2_residual_w: f64,
    #[serde(rename = "CONS_I2_bound_W")]
    pub cons_i2_bound_w: f64,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct Results {
    #[serde(rename = "T_node_K")]
    pub t_node_k: Option<BTreeMap<String, f64>>,
    #[serde(rename = "T_node_K_series")]
    pub t_node_k_series: Option<BTreeMap<String, Vec<f64>>>,
    pub t_s: Option<Vec<f64>>,
    #[serde(rename = "T_node_orbit_stats_K")]
    pub t_node_orbit_stats_k: Option<Vec<OrbitStats>>,
    #[serde(rename = "dH_node_J")]
    pub dh_node_j: Option<BTreeMap<String, f64>>,
    /// Transient modes: the heat flows below are evaluated at this time (final accepted state).
    pub heat_flows_at_t_s: Option<f64>,
    #[serde(rename = "Q_link_W")]
    pub q_link_w: BTreeMap<String, f64>,
    #[serde(rename = "Q_rad_net_W")]
    pub q_rad_net_w: RadiationOut,
    #[serde(rename = "Q_env_abs_W")]
    pub q_env_abs_w: BTreeMap<String, EnvOut>,
    #[serde(rename = "Q_to_sink_W")]
    pub q_to_sink_w: BTreeMap<String, f64>,
    #[serde(rename = "Q_boundary_W")]
    pub q_boundary_w: BoundaryOut,
    #[serde(rename = "Q_source_node_W")]
    pub q_source_node_w: BTreeMap<String, BTreeMap<String, f64>>,
    #[serde(rename = "P_exported_W")]
    pub p_exported_w: BTreeMap<String, Vec<f64>>,
    pub interface_derived: Option<InterfaceDerived>,
    pub energy_balance: EnergyBalance,
    pub convergence: ConvergenceOut,
}

#[derive(Debug, Clone, Serialize)]
pub struct Provenance {
    pub model_id: String,
    pub model_version: String,
    pub prereg_sha256: String,
    pub prereg_md_sha256: String,
    pub implementation: String,
    pub rust_commit: String,
    pub rust_tree_dirty: bool,
    pub input_set_sha256: String,
    pub interface_record_sha256: BTreeMap<String, String>,
    pub governed_record_sha256: BTreeMap<String, String>,
    pub hallthruster_commit_pinned: String,
    pub case_class: String,
    pub supply_mode: String,
    pub design_state_id: Option<String>,
    pub ensemble_member_ids: Vec<String>,
    pub a9_status: String,
    pub binding_statuses: BTreeMap<String, String>,
    pub validation_status: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ThermalOutput {
    pub schema: String,
    pub model_id: String,
    pub model_version: String,
    pub case_id: String,
    pub case_class: String,
    pub solver_mode: String,
    pub run_status: RunStatus,
    pub status_reasons: Vec<Reason>,
    pub labels: Vec<String>,
    /// Present only for CONVERGED (outputs.on_refusal).
    pub results: Option<Results>,
    pub domain_diagnostics: Option<DomainDiagnostics>,
    pub provenance: Provenance,
    pub validation_status: String,
}

impl ThermalOutput {
    /// Deterministic JSON (two-space indent, trailing newline).
    pub fn to_json(&self) -> String {
        let mut s = serde_json::to_string_pretty(self).expect("finite outputs serialize");
        s.push('\n');
        s
    }
}

/// Status precedence (prereg `status_vocabulary.precedence`): the first status reached in the order MODEL_ERROR,
/// NOT_EVALUATED, INCOMPLETE_EVIDENCE, OUT_OF_DOMAIN; CONVERGED when there is no reason.
pub fn run_status(reasons: &[Reason]) -> RunStatus {
    reasons.iter().map(|r| r.status).min().unwrap_or(RunStatus::Converged)
}
