//! Raw output record (OUT-01..OUT-14) and the four interface records. Serialization is deterministic (ordered maps,
//! no time stamps), so two runs with the same inputs give byte-identical JSON (NV-01).

use crate::status::{IcpStatus, Quantity, Reason};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

/// A categorical raw output (e.g. `binding_limit`, `plasma_state`).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Label {
    pub value: Option<String>,
    pub status: IcpStatus,
    pub reasons: Vec<String>,
}

impl Label {
    pub fn value(v: &str) -> Self {
        Label { value: Some(v.to_string()), status: IcpStatus::Converged, reasons: vec![] }
    }

    pub fn withheld(status: IcpStatus, reasons: Vec<String>) -> Self {
        Label { value: None, status, reasons }
    }
}

/// One raw output: a scalar, a keyed family (per species / reaction / surface / node), or a label.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(untagged)]
pub enum OutputValue {
    Scalar(Quantity),
    Map(BTreeMap<String, Quantity>),
    Label(Label),
}

impl OutputValue {
    pub fn scalar(&self) -> Option<&Quantity> {
        match self {
            OutputValue::Scalar(q) => Some(q),
            _ => None,
        }
    }

    pub fn map(&self) -> Option<&BTreeMap<String, Quantity>> {
        match self {
            OutputValue::Map(m) => Some(m),
            _ => None,
        }
    }

    pub fn label(&self) -> Option<&Label> {
        match self {
            OutputValue::Label(l) => Some(l),
            _ => None,
        }
    }
}

/// A domain, conservation or convergence check (OUT-12).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CheckRecord {
    pub id: String,
    pub status: IcpStatus,
    pub value: Option<f64>,
    pub tolerance: Option<f64>,
    pub detail: String,
}

/// Per-reaction chemistry validity (OUT-12): limit, 3/2 T_e and the activity share beyond the limit.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ValidityRecord {
    pub reaction: String,
    pub validity: String,
    pub max_mean_energy_ev: Option<f64>,
    pub mean_energy_ev: Option<f64>,
    pub activity_share_beyond_limit: Option<f64>,
    pub status: IcpStatus,
}

/// Per-surface terms of EQ-09 / EQ-16 (OUT-09 detail): fluxes, the attribution pair L_j / C_j and formation release.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct SurfaceTerms {
    pub kind: String,
    pub thermal_node: String,
    pub potential_v: Quantity,
    pub gamma_e_m2_s: Quantity,
    pub gamma_z_m2_s: Quantity,
    pub l_w: Quantity,
    pub c_w: Quantity,
    pub formation_w: Quantity,
}

/// One refined equilibrium (OUT-12 `equilibria`).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct EquilibriumRecord {
    pub regime: String,
    pub t_e_ev: f64,
    pub n_e_m3: f64,
    pub phi_p_v: Option<f64>,
    pub electron_saturated_surfaces: Vec<String>,
    pub domain_status: IcpStatus,
    pub domain_reasons: Vec<String>,
}

/// Solver convergence (OUT-12 `convergence`, NV-03).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Convergence {
    pub status: IcpStatus,
    pub bisection_iterations: Option<usize>,
    pub fixed_point_iterations: Option<usize>,
    pub species_balance_residual: Option<f64>,
    pub quasi_neutrality_residual: Option<f64>,
    pub current_balance_residual: Option<f64>,
    pub energy_balance_residual: Option<f64>,
    pub tol_solve: f64,
    pub numerical_settings: BTreeMap<String, f64>,
}

/// One bounding assignment of IF-ICP-THERMAL-v1.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ThermalAssignment {
    /// AS_REGISTERED, or ALL_RADIATED / ALL_WALL when an inelastic channel is UNRESOLVED.
    pub assignment: String,
    pub keys: BTreeMap<String, Quantity>,
    pub q_icp_plasma_wall_by_surface_w: BTreeMap<String, Quantity>,
    pub q_icp_plasma_wall_by_node_w: BTreeMap<String, Quantity>,
    pub q_icp_bias_by_surface_w: BTreeMap<String, Quantity>,
    pub q_icp_coil_ohmic_split_w: Quantity,
    pub q_icp_match_w_location: Label,
    pub closures: Vec<CheckRecord>,
}

/// IF-ICP-THERMAL-v1 producer record.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ThermalRecord {
    pub interface: String,
    pub consumer: String,
    pub rf_powered_only: bool,
    pub assignments: Vec<ThermalAssignment>,
    pub consumes: BTreeMap<String, OutputValue>,
    pub hall_powered_heat: String,
    pub status: IcpStatus,
}

/// IF-ICP-BUS-v1 producer record.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct BusRecord {
    pub interface: String,
    pub target_boundary: String,
    pub keys: BTreeMap<String, Quantity>,
    pub slots: BTreeMap<String, Quantity>,
    pub checks: Vec<CheckRecord>,
    pub status: IcpStatus,
    pub reasons: Vec<String>,
}

/// IF-ICP-HALL-v1 record: the pair at one registered point, never a ratio, margin or verdict.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct HallRecord {
    pub interface: String,
    pub configuration: String,
    pub h1_point_id: Option<String>,
    pub supply_mode: String,
    pub coupling_mode: String,
    pub i_e_cap_a: Quantity,
    pub i_e_sat_a: Quantity,
    pub binding_limit: Label,
    pub validation_status: String,
    pub uncertainty: BTreeMap<String, Quantity>,
    pub i_d_max_h1_a: Quantity,
    pub i_d_max_h1_basis: Option<String>,
    pub coupled_status: IcpStatus,
    pub coupled_reasons: Vec<String>,
}

/// IF-ICP-FEED-v1 producer record.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct FeedRecord {
    pub interface: String,
    pub gas_mode: String,
    pub supply_mode: String,
    pub consumes: BTreeMap<String, OutputValue>,
    pub mdot_icp_dedicated_kg_s: BTreeMap<String, Quantity>,
    pub booking: String,
    pub dmdot_conversion_kg_s: BTreeMap<String, Quantity>,
}

/// OUT-13 at case level: the sampled envelope needs the admitted Rust RNG policy (UQ-03, abep-rng / SC-WP-10) and
/// u_model_form needs validation residuals (UQ-05); the unweighted scenario sets evaluated here are listed.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct UncertaintyRecord {
    pub sampled_envelope: Label,
    pub u_model_form: Label,
    pub scenario_sets: Vec<String>,
}

/// OUT-14 provenance.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Provenance {
    pub model_id: String,
    pub model_version: String,
    pub contract_id: String,
    pub prereg_lock_sha256: String,
    pub prereg_sha256: String,
    pub addendum_01_sha256: String,
    pub chem_air_lock_sha256: String,
    pub input_sha256: BTreeMap<String, String>,
    pub data_files_sha256: BTreeMap<String, String>,
    pub rust_commit: Option<String>,
}

/// The raw output record of one case.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct IcpResult {
    pub schema: String,
    pub case_id: String,
    pub supply_mode: String,
    pub gas_mode: String,
    pub configuration: String,
    pub coupling_mode: String,
    pub status: IcpStatus,
    pub plasma_state: Label,
    pub reasons: Vec<Reason>,
    pub flags: BTreeSet<String>,
    pub verify_items_on_path: BTreeSet<String>,
    pub verification_status: String,
    pub validation_status: String,
    pub outputs: BTreeMap<String, OutputValue>,
    pub surface_terms: BTreeMap<String, SurfaceTerms>,
    pub if_icp_thermal_v1: ThermalRecord,
    pub if_icp_bus_v1: BusRecord,
    pub if_icp_hall_v1: HallRecord,
    pub if_icp_feed_v1: FeedRecord,
    pub domain_checks: Vec<CheckRecord>,
    pub chemistry_validity: Vec<ValidityRecord>,
    pub conservation: Vec<CheckRecord>,
    pub convergence: Convergence,
    pub equilibria: Vec<EquilibriumRecord>,
    pub uncertainty: UncertaintyRecord,
    pub provenance: Provenance,
}

impl IcpResult {
    /// Deterministic JSON (NV-01).
    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).expect("serializable")
    }

    pub fn scalar(&self, key: &str) -> &Quantity {
        self.outputs.get(key).and_then(OutputValue::scalar).unwrap_or_else(|| panic!("no scalar output {key}"))
    }

    pub fn map(&self, key: &str) -> &BTreeMap<String, Quantity> {
        self.outputs.get(key).and_then(OutputValue::map).unwrap_or_else(|| panic!("no map output {key}"))
    }

    pub fn reason_codes(&self) -> BTreeSet<String> {
        self.reasons.iter().map(|r| r.code.clone()).collect()
    }

    pub fn check(&self, id: &str) -> Option<&CheckRecord> {
        self.conservation.iter().chain(self.domain_checks.iter()).find(|c| c.id == id)
    }
}
