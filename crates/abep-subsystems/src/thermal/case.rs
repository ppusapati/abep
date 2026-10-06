//! Input schema `abep_np_thermal_case_v1`: one case = case inputs (RI-CASE), registered input records (record_format),
//! the topology (nodes, links, enclosures, boundary fluxes, environment, thermal control) and the two interface records
//! (IF-HALL-THERMAL-v1, IF-ICP-THERMAL-v1). Record and value-record fields are optional in the serde layer only so that
//! every missing field is reported (a missing field is MODEL_ERROR).

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

pub const CASE_SCHEMA: &str = "abep_np_thermal_case_v1";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ThermalCase {
    pub schema: String,
    pub case_id: String,
    pub case_class: String,
    pub topology_scope: String,
    pub configuration: String,
    pub supply_mode: String,
    pub design_state_id: Option<String>,
    pub installed_variants: Vec<String>,
    pub match_colocated: Option<bool>,
    pub magnet_load_mode: Option<String>,
    pub anode_material_candidate_id: Option<String>,
    pub collector_material_candidate_id: Option<String>,
    pub bench_vacuum: Option<BenchVacuum>,
    pub solver: SolverSpec,
    pub records: Vec<InputRecord>,
    pub nodes: Vec<NodeRecord>,
    pub links: Vec<LinkRecord>,
    pub enclosures: Vec<EnclosureRecord>,
    pub boundary_fluxes: Vec<BoundaryFlux>,
    pub environment: Vec<EnvSurface>,
    pub thermal_control: Vec<ThermalControl>,
    /// Coil node id -> resistance-ratio relation record id (E-09, CONSTANT_CURRENT_R_OF_T).
    pub coil_resistance_relations: BTreeMap<String, String>,
    pub interfaces: Interfaces,
    /// Registered partitions (RI-PART): interface key -> partition record id.
    pub partitions: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BenchVacuum {
    pub facility_pressure_record_id: String,
    pub a04_max_pressure_record_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SolverSpec {
    pub mode: String,
    /// Registered initial temperature per solved node (NUM-02).
    #[serde(rename = "T_init_K")]
    pub t_init_k: BTreeMap<String, f64>,
    pub t_start_s: Option<f64>,
    pub t_end_s: Option<f64>,
    /// Registered nominal step (E-11); step doubling may halve it (NUM-04).
    pub dt_s: Option<f64>,
    pub orbit_period_s: Option<f64>,
}

/// prereg `registered_inputs.record_format`.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InputRecord {
    pub id: Option<String>,
    pub quantity: Option<String>,
    pub value: Option<Value>,
    pub units: Option<String>,
    pub source: Option<String>,
    pub evidence_class: Option<String>,
    pub uncertainty: Option<Value>,
    pub applicability_domain: Option<ApplicabilityDomain>,
    pub validation_status: Option<String>,
    pub status: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApplicabilityDomain {
    #[serde(rename = "T_min_K")]
    pub t_min_k: Option<f64>,
    #[serde(rename = "T_max_K")]
    pub t_max_k: Option<f64>,
    /// Optical records only (D-03): false = non-gray inside its band.
    pub gray_in_band: Option<bool>,
    pub text: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NodeRecord {
    pub id: String,
    pub group: String,
    pub represents: String,
    pub presence: String,
    pub role: String,
    pub refines: Option<String>,
    pub thermal_mass: String,
    pub parts: Vec<Part>,
    pub surfaces: Vec<Surface>,
    pub biot_geometry: Option<BiotGeometry>,
    pub receives_interface_keys: Vec<String>,
    pub case_classes_allowed: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Part {
    pub part_id: String,
    /// Specific-heat record (quantity specific_heat).
    pub material_record_id: String,
    pub mass_kg_record_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Surface {
    pub surface_id: String,
    pub area_record_id: String,
    #[serde(rename = "eps_IR_record_id")]
    pub eps_ir_record_id: String,
    pub alpha_solar_record_id: Option<String>,
    pub enclosure_id: String,
    pub external: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BiotGeometry {
    pub volume_record_id: String,
    pub conduction_area_record_id: String,
    pub k_record_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LinkRecord {
    pub id: String,
    #[serde(rename = "type")]
    pub link_type: String,
    pub a: Endpoint,
    pub b: Endpoint,
    pub k_record_id: Option<String>,
    pub shape: Option<ShapeSpec>,
    pub h_c_record_id: Option<String>,
    pub contact_area_record_id: Option<String>,
    #[serde(rename = "G_record_id")]
    pub g_record_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Endpoint {
    pub node: Option<String>,
    pub boundary: Option<String>,
    pub temperature_record_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ShapeSpec {
    pub kind: String,
    pub area_record_id: Option<String>,
    pub length_record_id: Option<String>,
    pub r_outer_record_id: Option<String>,
    pub r_inner_record_id: Option<String>,
    #[serde(rename = "S_record_id")]
    pub s_record_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EnclosureRecord {
    pub id: String,
    pub view_factor_record_id: String,
    pub sinks: Vec<SinkMember>,
    /// SCI-C: host spacecraft surfaces at registered temperature and emittance (boundary B_SC).
    pub host_surfaces: Vec<HostSurface>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SinkMember {
    pub surface_id: String,
    pub kind: String,
    pub temperature_record_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HostSurface {
    pub surface_id: String,
    pub area_record_id: String,
    #[serde(rename = "eps_IR_record_id")]
    pub eps_ir_record_id: String,
    pub temperature_record_id: String,
}

/// SCI-B prescribed flux into an attachment node (positive into the node).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BoundaryFlux {
    pub id: String,
    pub boundary: String,
    pub node: String,
    pub q_record_id: String,
}

/// E-06 inputs of one external surface.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EnvSurface {
    pub surface_id: String,
    pub solar_flux_record_id: String,
    #[serde(rename = "F_sun_record_id")]
    pub f_sun_record_id: String,
    pub illumination_record_id: String,
    pub albedo_record_id: String,
    #[serde(rename = "F_alb_record_id")]
    pub f_alb_record_id: String,
    pub olr_flux_record_id: String,
    #[serde(rename = "F_earth_record_id")]
    pub f_earth_record_id: String,
    pub rho_record_id: String,
    #[serde(rename = "V_rel_record_id")]
    pub v_rel_record_id: String,
    #[serde(rename = "alpha_E_record_id")]
    pub alpha_e_record_id: String,
    #[serde(rename = "A_ram_record_id")]
    pub a_ram_record_id: String,
}

/// HS-TC: registered thermal-control dissipation on a node.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ThermalControl {
    pub node: String,
    pub record_id: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Interfaces {
    #[serde(rename = "IF-HALL-THERMAL-v1")]
    pub hall: Option<InterfaceRecord>,
    #[serde(rename = "IF-ICP-THERMAL-v1")]
    pub icp: Option<InterfaceRecord>,
}

/// prereg `heat_sources.interface_record_format`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InterfaceRecord {
    pub interface_id: String,
    pub interface_version: String,
    pub producer_id: String,
    pub producer_version: String,
    pub producer_prereg_sha256: String,
    pub case_id: String,
    pub case_class: String,
    pub supply_mode: String,
    pub design_state_id: Option<String>,
    pub operating_point_id: String,
    pub time_basis: TimeBasis,
    pub keys: BTreeMap<String, ValueRecord>,
    /// Producer-predicted partitions: key -> {receiver: weight}.
    pub partitions: BTreeMap<String, BTreeMap<String, f64>>,
    /// IFI-5 applies only when the producer declares rf_powered_only = true.
    pub rf_powered_only: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TimeBasis {
    /// STEADY | ZOH_SERIES
    pub kind: String,
    pub breakpoints_s: Option<Vec<f64>>,
}

/// prereg `interface_record_format.value_record`; map-derived Hall values add `hall_map`.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ValueRecord {
    pub value: Option<Value>,
    pub units: Option<String>,
    pub status: Option<String>,
    pub evidence_class: Option<String>,
    pub source: Option<String>,
    pub uncertainty: Option<Value>,
    pub applicability_domain: Option<Value>,
    pub validation_status: Option<String>,
    pub hall_map: Option<HallMapProvenance>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HallMapProvenance {
    pub ensemble_member_id: String,
    pub hallthruster_commit: String,
    pub map_meta_sha256: String,
    pub trustworthy: bool,
    pub wall_life_trustworthy: bool,
}
