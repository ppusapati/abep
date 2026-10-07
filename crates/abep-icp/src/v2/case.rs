//! model_version 2 case registration: the inputs of prereg v2 (IN-01..IN-27 as replaced / added). Unchanged v1 input
//! types are reused. An absent `Option` is an unregistered input (never a default). The retired inputs `f_in` and
//! `eta_bias` exist only so that a registration carrying them is refused (MODEL_ERROR, INPUT_RETIRED_V2; FC-19).

use crate::case::{
    Configuration, CouplingEvidence, CouplingMode, Disposition, GasMode, HallDemand, RfInput, SupplyMode,
    ThermalBoundary, VariantSlot,
};
use crate::chemistry::ChemistryRegistration;
use crate::evidence::Registered;
use crate::geometry::{HModel, Surface};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// IN-10 v2 effective-volume mode (OQ-NPICP-12).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum VolumeModeV2 {
    /// V = pi R^2 L of the dielectric bore: a declared unvalidated modelling assumption (flag ASSUMED_GEOMETRIC_TUBE).
    AssumedGeometricTube,
    /// V_eff from registered diagnostics (supersedes the tube for its geometry id; DOM-16).
    RegisteredEffective { volume_m3: f64, record_id: String },
}

/// IN-10 v2 geometry. Surface -> node map: module walls -> N_VESSEL / N_ANTENNA / N_MOUNT / N_COLLECTOR / N_HOUSING;
/// electron collector -> EXPORT; OPEN_UPSTREAM -> RX_H1_FACE; OPEN_DOWNSTREAM -> EXPORT.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GeometryV2 {
    pub geometry_id: String,
    pub radius_m: f64,
    pub length_m: f64,
    pub volume_mode: VolumeModeV2,
    pub surfaces: Vec<Surface>,
}

/// IN-26 electrode supply identity.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SupplyIdentity {
    /// Flight slot icp_collector_bias.
    IcpCollectorBias,
    /// Bench supply: never spacecraft bus power (flag INCLUDES_GROUND_FACILITY_SUPPLY).
    GroundFacilityOnly,
    /// CPL-HALL-ON only.
    HallDischargeLoop,
}

/// IN-11 electrodes with the IN-26 supply of every non-floating surface.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ElectrodesV2 {
    pub reference: String,
    pub potentials_v: BTreeMap<String, f64>,
    pub supplies: BTreeMap<String, SupplyIdentity>,
    pub collector_bias_sweep_v: Option<Vec<f64>>,
}

/// IN-12 v2 inflow Gamma_in (OQ-NPICP-14; f_in retired).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum InflowV2 {
    /// No dedicated inflow (a registered zero, e.g. a background-only bench state).
    NoInflow,
    /// Bench: the measured dedicated flow into the ICP [kg/s] per species.
    MeasuredDedicatedFeed { mdot_kg_s: Registered<BTreeMap<String, f64>> },
    /// Flight: Gamma_in [1/s] per species from an upstream conductance / feed model; admitted models only (DOM-14).
    UpstreamModel { model_id: String, gamma_in_per_s: Registered<BTreeMap<String, f64>> },
}

/// IN-12 v2 pressure / neutral density.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum NeutralSourceV2 {
    /// EQ-01 (validation: measured p_ICP is determining, VC-07).
    RegisteredPressure {
        p_icp_pa: Registered<f64>,
        t_g_k: Registered<f64>,
        mole_fractions: Registered<BTreeMap<String, f64>>,
    },
    /// EQ-02 v2.
    FlowBalance {
        t_g_k: Registered<f64>,
        sigma_c_m2: BTreeMap<String, Registered<f64>>,
        inflow: InflowV2,
        /// Retired (OQ-NPICP-14): present -> MODEL_ERROR (INPUT_RETIRED_V2).
        #[serde(default, skip_serializing_if = "Option::is_none")]
        f_in: Option<Registered<f64>>,
    },
}

/// IN-13 v2 background (PF-02, DOM-17).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum BackgroundV2 {
    /// A registered isotropic Maxwellian background (bench: facility gauge p_b, T_b).
    IsotropicMaxwellian { n_b_m3: BTreeMap<String, f64>, t_b_k: f64 },
    /// A directed flight ambient: needs a registered exposure model (DOM-17).
    FlightAmbient { exposure_model_id: Option<String> },
}

/// IN-18 v2 wall coefficients of one (species, wall material): sourced, or absent -> the vertex set {0, 1}. A value
/// registered with a PHYSICAL_BOUND uncertainty is a bound, not a source: its bounds are the vertices.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WallCoefficients {
    pub species: String,
    pub material: String,
    /// Recombination probability per collision (atoms; PF-01).
    pub gamma: Option<Registered<f64>>,
    /// Fraction of the recombination energy accommodated by the surface (AIR-WALL-04).
    pub beta: Option<Registered<f64>>,
    /// Quench probability of an excited state (AIR-WALL-06; ED-04 WALL_QUENCHED distribution).
    pub quench: Option<Registered<f64>>,
}

/// IN-19 v2 bus registration (eta_bias retired: the bias-supply efficiency is the ledger's record).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BusRegistrationV2 {
    pub boundary_id: String,
    /// eta_RF = (P_fwd - P_refl) / P_RF,DC at the generator DC input (slot icp_rf_source load plane).
    pub eta_rf: Registered<f64>,
    pub p_match_dc_w: Registered<f64>,
    pub match_colocated: Registered<bool>,
    pub assist_magnet: VariantSlot,
    pub flow_control: VariantSlot,
    /// A laboratory RF generator (GROUND_FACILITY_ONLY: never spacecraft bus power, BUS2-04).
    pub ground_facility_rf_generator: bool,
    /// Retired: present -> MODEL_ERROR (INPUT_RETIRED_V2).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub eta_bias: Option<Registered<f64>>,
}

/// One model_version 2 case.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IcpCaseV2 {
    pub case_id: String,
    pub supply_mode: Registered<SupplyMode>,
    pub gas_mode: Registered<GasMode>,
    pub configuration: Configuration,
    pub coupling_mode: CouplingMode,
    pub h1_point_id: Option<String>,
    /// VC-04 domain cell of the point (OUT-12 validation_cell_id); None -> reported as not assigned.
    pub validation_cell_id: Option<String>,
    pub f_rf_hz: Option<Registered<f64>>,
    pub rf_input: Option<RfInput>,
    pub coupling_evidence: Option<CouplingEvidence>,
    pub geometry: Option<Registered<GeometryV2>>,
    pub electrodes: Option<Registered<ElectrodesV2>>,
    pub neutral_source: Option<NeutralSourceV2>,
    pub background: Option<Registered<BackgroundV2>>,
    pub thermal_boundary: Option<Registered<ThermalBoundary>>,
    pub b_icp_max_t: Option<Registered<f64>>,
    pub chemistry: ChemistryRegistration,
    pub h_model: Option<HModel>,
    pub wall_coefficients: Vec<WallCoefficients>,
    pub dispositions: BTreeMap<String, Registered<Disposition>>,
    /// IN-25: D0(X2) [eV] per molecule species.
    pub dissociation_energies_ev: BTreeMap<String, Registered<f64>>,
    pub dedicated_flow_kg_s: Option<Registered<BTreeMap<String, f64>>>,
    pub bus: Option<BusRegistrationV2>,
    /// TK-06 conductor split over {N_ANTENNA, N_COLLECTOR, N_HOUSING, N_MOUNT} (echoed; None -> INCOMPLETE_EVIDENCE).
    pub coil_ohmic_split: Option<Registered<BTreeMap<String, f64>>>,
    pub hall_demand: Option<HallDemand>,
}
