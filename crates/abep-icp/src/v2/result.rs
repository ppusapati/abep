//! model_version 2 raw output record (OUT-01..OUT-14 as replaced in prereg v2) and the IF-ICP-THERMAL-v2 /
//! IF-ICP-BUS-v2 / CPL-HALL-ON-v1 records. Deterministic serialization (ordered maps, no time stamps; NV-01).

use crate::result::{CheckRecord, EquilibriumRecord, Label, OutputValue};
use crate::status::{IcpStatus, Quantity, Reason};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

/// One IF-ICP-THERMAL-v2 key: the value with its own status, and its key-table row (FC-16 v2: powered_by).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ThermalKeyV2 {
    pub id: String,
    pub role: String,
    pub plane: String,
    pub powered_by: String,
    #[serde(flatten)]
    pub q: Quantity,
}

/// OUT-09 per surface: L_j, F_j, W_j (by class), C_j, Q_j^kin = L_j + C_j and Q_j = L_j + F_j + W_j + C_j [W].
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct SurfaceRecordV2 {
    pub kind: String,
    pub node: String,
    pub material: String,
    pub l_w: f64,
    pub f_w: f64,
    pub w_w: f64,
    pub w_x_w: f64,
    pub w_n_w: f64,
    pub w_a_w: f64,
    pub c_w: f64,
    pub q_kin_w: f64,
    pub q_total_w: f64,
}

/// One partition member's IF-ICP-THERMAL-v2 record (ED-08: one record per member).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ThermalMemberV2 {
    pub scenario_member_id: String,
    pub solve_member_id: String,
    pub partition_member_id: String,
    pub status: IcpStatus,
    pub reasons: Vec<String>,
    pub keys: BTreeMap<String, ThermalKeyV2>,
    /// Producer per-node partitions of TK-07 (Q_icp_plasma_wall_W) and TK-12 (Q_icp_bias_collector_W, signed) [W].
    pub node_shares_w: BTreeMap<String, BTreeMap<String, Quantity>>,
    pub surfaces: BTreeMap<String, SurfaceRecordV2>,
    /// TK-06 conductor split [W] (registered split, or INCOMPLETE_EVIDENCE).
    pub coil_ohmic_split_w: BTreeMap<String, Quantity>,
    /// Class energy and its allocated total per class X / N / A [W] (CC-08).
    pub class_energy_w: BTreeMap<String, [f64; 2]>,
    pub route_excess_w: BTreeMap<String, f64>,
    pub closures: Vec<CheckRecord>,
}

/// Extreme load of one key or node over the members (ED-08 consumer minimum set).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Extreme {
    pub min_w: f64,
    pub min_members: Vec<String>,
    pub max_w: f64,
    pub max_members: Vec<String>,
}

/// IF-ICP-THERMAL-v2 producer record.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ThermalRecordV2 {
    pub interface: String,
    pub consumer: String,
    pub producer_lock_sha256: String,
    pub key_table_sha256: String,
    /// CFG-CAP-OFF, CFG-FLIGHT-HALL-ON, or SYNTHETIC for a SYNTHETIC_TEST_ONLY case.
    pub configuration: String,
    pub status: IcpStatus,
    pub reasons: Vec<String>,
    pub members: Vec<ThermalMemberV2>,
    pub per_receiver_extremes: BTreeMap<String, Extreme>,
    pub consumes: BTreeMap<String, OutputValue>,
    pub hall_powered_heat: String,
}

/// One IF-ICP-BUS-v2 key with its plane and slot (BUS2-01).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct BusKeyV2 {
    pub id: String,
    pub plane: String,
    pub plane_definition: String,
    pub slot: Option<String>,
    pub slot_state: String,
    #[serde(flatten)]
    pub q: Quantity,
}

/// IF-ICP-BUS-v2 record of one solve member.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct BusRecordV2 {
    pub interface: String,
    pub target_boundary: String,
    pub configuration: String,
    pub solve_member_id: String,
    pub flags: BTreeSet<String>,
    pub keys: BTreeMap<String, BusKeyV2>,
    pub checks: Vec<CheckRecord>,
    pub status: IcpStatus,
    pub reasons: Vec<String>,
}

/// One solve member (ED-08): chemistry variant x gamma vertices x H member.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct SolveMemberV2 {
    pub solve_member_id: String,
    pub h_member: String,
    pub gamma: BTreeMap<String, f64>,
    pub status: IcpStatus,
    pub reasons: Vec<String>,
    pub plasma_state: Label,
    pub outputs: BTreeMap<String, OutputValue>,
    pub equilibria: Vec<EquilibriumRecord>,
    pub domain_checks: Vec<CheckRecord>,
    pub conservation: Vec<CheckRecord>,
    /// EQ-19 / EQ-20 diagnostics (reported only, no threshold).
    pub diagnostics: BTreeMap<String, Quantity>,
}

/// The IF-ICP-HALL-v1 pair at one point (AS-01): I_e,cap per solve member and its envelope; no ratio is formed.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct HallPairV2 {
    pub interface: String,
    pub configuration: String,
    pub h1_point_id: Option<String>,
    pub i_e_cap_by_member_a: BTreeMap<String, Quantity>,
    pub i_e_cap_envelope_a: BTreeMap<String, Quantity>,
    pub i_d_max_h1_a: Quantity,
    pub validation_status: String,
    pub validation_cell_id: Option<String>,
    pub coupled_status: IcpStatus,
    pub coupled_reasons: Vec<String>,
}

/// IF-ICP-FEED-v1 (inherited): the dedicated ICP flow per gas mode.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct FeedRecordV2 {
    pub interface: String,
    pub gas_mode: String,
    pub mdot_icp_dedicated_kg_s: BTreeMap<String, Quantity>,
    pub booking: String,
}

/// CPL-HALL-ON-v1 record (OUT-07): every value with its status; NOT_EVALUATED while no Hall member is admitted.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CplRecord {
    pub contract: String,
    pub configuration: String,
    pub status: IcpStatus,
    pub reasons: Vec<Reason>,
    pub inputs: BTreeMap<String, Quantity>,
    pub outputs: BTreeMap<String, Quantity>,
    pub verify_items: Vec<String>,
}

/// OUT-13 at case level.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct UncertaintyV2 {
    pub sampled_envelope: Label,
    pub u_model_form: Label,
    pub scenario_sets: Vec<String>,
}

/// OUT-14 v2 provenance.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ProvenanceV2 {
    pub model_id: String,
    pub model_version: String,
    pub contract_id: String,
    pub prereg_lock_sha256: String,
    pub prereg_sha256: String,
    pub predecessor_lock_sha256: String,
    pub interface_ids: Vec<String>,
    pub chem_registry: BTreeMap<String, String>,
    pub input_sha256: String,
    pub data_files_sha256: BTreeMap<String, String>,
    pub rust_commit: Option<String>,
}

/// The model_version 2 raw output record of one case.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct IcpResultV2 {
    pub schema: String,
    pub case_id: String,
    pub model_version: String,
    pub supply_mode: String,
    pub gas_mode: String,
    pub configuration: String,
    pub coupling_mode: String,
    pub status: IcpStatus,
    pub reasons: Vec<Reason>,
    pub flags: BTreeSet<String>,
    pub verify_items_on_path: BTreeSet<String>,
    pub verification_status: String,
    pub validation_status: String,
    pub validation_cell_id: Option<String>,
    pub volume_mode: Option<String>,
    pub solve_members: Vec<SolveMemberV2>,
    pub if_icp_thermal_v2: ThermalRecordV2,
    pub if_icp_bus_v2: Vec<BusRecordV2>,
    pub if_icp_hall_v1: HallPairV2,
    pub if_icp_feed_v1: FeedRecordV2,
    pub cpl_hall_on_v1: CplRecord,
    pub uncertainty: UncertaintyV2,
    pub provenance: ProvenanceV2,
}

impl IcpResultV2 {
    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).expect("serializable")
    }

    pub fn reason_codes(&self) -> BTreeSet<String> {
        self.reasons.iter().map(|r| r.code.clone()).collect()
    }

    pub fn member(&self, id: &str) -> &ThermalMemberV2 {
        self.if_icp_thermal_v2.members.iter().find(|m| m.scenario_member_id == id).expect("member")
    }
}
