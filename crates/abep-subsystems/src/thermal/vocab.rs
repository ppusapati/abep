//! Registered vocabulary of NP-THERMAL-CATHODELESS v1: node ids and groups (prereg `nodes`), interface keys and their
//! receiving rules (`heat_sources`), case classes, solver modes, supply modes, record quantities with their units,
//! evidence classes and the refusal vocabulary of EX-02 / FT-10. Nothing here is a physical value.

/// Node groups (prereg `nodes.solved[].group`).
pub const GROUPS: [&str; 4] = ["HALL_BODY", "HALL_MAGNET", "ICP_NEUTRALIZER", "RADIATOR"];

/// One registered solved node: id, group, presence and the interface keys it may receive (prereg `nodes.solved`).
pub struct RegisteredNode {
    pub id: &'static str,
    pub group: &'static str,
    pub required: bool,
    pub receives: &'static [&'static str],
}

pub const NODES: [RegisteredNode; 17] = [
    RegisteredNode {
        id: "H1_ANODE",
        group: "HALL_BODY",
        required: true,
        receives: &["Q_hall_anode_W", "Q_hall_plasma_radiation_W"],
    },
    RegisteredNode {
        id: "H1_WALL_IN",
        group: "HALL_BODY",
        required: true,
        receives: &["Q_hall_wall_inner_W", "Q_hall_plasma_radiation_W"],
    },
    RegisteredNode {
        id: "H1_WALL_OUT",
        group: "HALL_BODY",
        required: true,
        receives: &["Q_hall_wall_outer_W", "Q_hall_plasma_radiation_W"],
    },
    RegisteredNode {
        id: "H1_POLE_IN",
        group: "HALL_BODY",
        required: true,
        receives: &["Q_hall_pole_W", "Q_hall_plasma_radiation_W", "Q_icp_radiation_W"],
    },
    RegisteredNode {
        id: "H1_POLE_OUT",
        group: "HALL_BODY",
        required: true,
        receives: &["Q_hall_pole_W", "Q_hall_plasma_radiation_W", "Q_icp_radiation_W"],
    },
    RegisteredNode { id: "H1_BACKPLATE", group: "HALL_BODY", required: true, receives: &[] },
    RegisteredNode { id: "H1_COIL_IN", group: "HALL_MAGNET", required: true, receives: &["Q_hall_coil_inner_W"] },
    RegisteredNode { id: "H1_COIL_OUT", group: "HALL_MAGNET", required: true, receives: &["Q_hall_coil_outer_W"] },
    RegisteredNode { id: "H1_COIL_TRIM", group: "HALL_MAGNET", required: false, receives: &["Q_hall_coil_trim_W"] },
    RegisteredNode {
        id: "N_VESSEL",
        group: "ICP_NEUTRALIZER",
        required: true,
        receives: &["Q_icp_plasma_wall_W", "Q_icp_radiation_W", "Q_hall_plume_to_icp_W", "Q_hall_plasma_radiation_W"],
    },
    RegisteredNode {
        id: "N_ANTENNA",
        group: "ICP_NEUTRALIZER",
        required: true,
        receives: &["Q_icp_coil_ohmic_W", "Q_icp_plasma_wall_W", "Q_icp_radiation_W"],
    },
    RegisteredNode {
        id: "N_COLLECTOR",
        group: "ICP_NEUTRALIZER",
        required: false,
        receives: &[
            "Q_icp_plasma_wall_W",
            "Q_icp_coil_ohmic_W",
            "Q_icp_radiation_W",
            "Q_hall_return_to_icp_W",
            "Q_hall_plume_to_icp_W",
            "Q_hall_plasma_radiation_W",
        ],
    },
    RegisteredNode {
        id: "N_HOUSING",
        group: "ICP_NEUTRALIZER",
        required: false,
        receives: &[
            "Q_icp_coil_ohmic_W",
            "Q_icp_plasma_wall_W",
            "Q_icp_radiation_W",
            "Q_hall_plume_to_icp_W",
            "Q_hall_plasma_radiation_W",
        ],
    },
    RegisteredNode { id: "N_MATCH", group: "ICP_NEUTRALIZER", required: false, receives: &["Q_icp_match_W"] },
    RegisteredNode { id: "N_MOUNT", group: "ICP_NEUTRALIZER", required: true, receives: &["Q_hall_plume_to_icp_W"] },
    RegisteredNode { id: "R_HALL", group: "RADIATOR", required: false, receives: &[] },
    RegisteredNode { id: "R_ICP", group: "RADIATOR", required: false, receives: &[] },
];

pub fn registered_node(id: &str) -> Option<&'static RegisteredNode> {
    NODES.iter().find(|n| n.id == id)
}

/// Excluded node ids (prereg `nodes.excluded`): H2-5 C-1 nodes, pre-ionizer, upstream demand nodes, PPU, and the
/// class-H `abep_sim/thermal.py` default node set. A node with one of these ids is refused (MODEL_ERROR).
pub const EXCLUDED_NODE_IDS: [&str; 13] = [
    "CB",
    "CE",
    "CK",
    "PIM",
    "COMP",
    "GP",
    "PPU",
    "intake",
    "compressor",
    "thruster",
    "magnets",
    "stage1_source",
    "ppu",
];

/// EX-02 / FT-10 refusal vocabulary: an identifier (node, surface, link, record, key, receiver, enclosure, boundary)
/// containing one of these substrings (case-insensitive) is refused with MODEL_ERROR. The model never carries such a
/// node, key or link; the list exists only to recognise and refuse it.
pub const REFUSED_SUBSTRINGS: [&str; 5] = ["cathode", "keeper", "emitter", "q_cath", "lab6"];
/// EX-02 / FT-10: an identifier with a token (split on non-alphanumerics) equal to one of these is refused.
pub const REFUSED_TOKENS: [&str; 1] = ["c1"];

/// The refusal reason for `ident`, or `None` when it is admissible.
pub fn refused_identifier(ident: &str) -> Option<String> {
    let low = ident.to_ascii_lowercase();
    for s in REFUSED_SUBSTRINGS {
        if low.contains(s) {
            return Some(format!("identifier {ident:?} contains refused substring {s:?} (EX-02, FT-10)"));
        }
    }
    for tok in low.split(|c: char| !c.is_ascii_alphanumeric()) {
        if REFUSED_TOKENS.contains(&tok) {
            return Some(format!("identifier {ident:?} contains refused token {tok:?} (EX-02, FT-10)"));
        }
    }
    if EXCLUDED_NODE_IDS.contains(&ident) {
        return Some(format!("identifier {ident:?} is an excluded node id (nodes.excluded)"));
    }
    None
}

pub const CASE_CLASSES: [&str; 4] = ["SYNTHETIC_VERIFICATION", "PARAMETRIC", "BENCH_REPLICA", "FLIGHT_CONDITIONAL"];
pub const SOLVER_MODES: [&str; 4] = ["STEADY", "ORBIT_AVERAGE_STEADY", "TRANSIENT", "ORBIT_TRANSIENT_PERIODIC"];
/// Topology scopes. `NP_THERMAL_NETWORK` enforces the registered node set; `ANALYTIC_REDUCED_NETWORK` runs the reduced
/// analytic setups of `analytic_limiting_cases` (SYNTHETIC_VERIFICATION only).
pub const TOPOLOGY_SCOPES: [&str; 2] = ["NP_THERMAL_NETWORK", "ANALYTIC_REDUCED_NETWORK"];
pub const FLIGHT_SUPPLY_MODES: [&str; 3] = ["AIR_PRIMARY", "XE_CONTINGENCY", "NON_FIRING"];
/// Bench supply modes named by D-05 (BENCH_REPLICA only), plus NON_FIRING. Any other bench gas needs registration.
pub const BENCH_SUPPLY_MODES: [&str; 3] = ["BENCH_AR_ENGINEERING_GROUND_ONLY", "N2", "NON_FIRING"];
/// Bus variants of `schemas/interfaces/bus_power_boundary_a9_v2.json` (GR-17).
pub const BUS_VARIANTS: [&str; 3] = ["active_cooling", "flow_control_icp_feed", "icp_assist_magnet"];
/// Variants outside v1 (A-10, D-05, FT-12): OUT_OF_DOMAIN.
pub const VARIANTS_OUTSIDE_V1: [&str; 2] = ["active_cooling", "icp_assist_magnet"];
pub const MAGNET_LOAD_MODES: [&str; 2] = ["FIXED_POWER", "CONSTANT_CURRENT_R_OF_T"];
/// Anode candidate rejected as current flight baseline (FT-16; P4 fixed status 316L_FLIGHT_ANODE).
pub const REJECTED_FLIGHT_ANODE_CANDIDATE: &str = "CAND-01";

pub const EVIDENCE_CLASSES: [&str; 9] = [
    "measured",
    "digitized",
    "inferred",
    "reconstructed",
    "model-derived",
    "assumed",
    "owner-allocation",
    "published analog",
    "SYNTHETIC_TEST_DATA_NOT_EVIDENCE",
];
pub const SYNTHETIC: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";
pub const RECORD_STATUSES: [&str; 6] = ["REGISTERED", "TBD", "TBD_AFTER_EVIDENCE", "OPEN", "REFUSED", "NOT_EVALUATED"];
pub const VALUE_STATUSES: [&str; 5] =
    ["EVALUATED", "NOT_EVALUATED", "INCOMPLETE_EVIDENCE", "OUT_OF_DOMAIN", "MODEL_ERROR"];

/// How a record value is shaped.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Shape {
    /// A number.
    Scalar,
    /// A number or a ZOH series `{breakpoints_s, values}`.
    TimeValue,
    /// A temperature-dependent property form with a mandatory [T_min, T_max].
    Property,
    /// A number valid over a mandatory [T_min, T_max] (temperature-independent, A-15).
    RangedScalar,
    /// `{view_factors: {row: {col: F}}}`.
    ViewFactors,
    /// `{weights: {receiver: w}}`.
    Weights,
}

/// Registered quantities with their units and value shape (record `quantity`, `units`).
pub const QUANTITIES: [(&str, &str, Shape); 26] = [
    ("mass", "kg", Shape::Scalar),
    ("specific_heat", "J/(kg*K)", Shape::Property),
    ("thermal_conductivity", "W/(m*K)", Shape::Property),
    ("emittance_IR", "1", Shape::Property),
    ("absorptance_solar", "1", Shape::Property),
    ("resistance_ratio_relation", "1", Shape::Property),
    ("contact_conductance_coefficient", "W/(m^2*K)", Shape::RangedScalar),
    ("conductance", "W/K", Shape::RangedScalar),
    ("area", "m^2", Shape::Scalar),
    ("length", "m", Shape::Scalar),
    ("volume", "m^3", Shape::Scalar),
    ("shape_factor", "m", Shape::Scalar),
    ("temperature", "K", Shape::TimeValue),
    ("power", "W", Shape::TimeValue),
    ("view_factor_matrix", "1", Shape::ViewFactors),
    ("partition", "1", Shape::Weights),
    ("solar_flux", "W/m^2", Shape::TimeValue),
    ("olr_flux", "W/m^2", Shape::TimeValue),
    ("albedo", "1", Shape::TimeValue),
    ("view_factor_env", "1", Shape::TimeValue),
    ("illumination", "1", Shape::TimeValue),
    ("density", "kg/m^3", Shape::TimeValue),
    ("velocity", "m/s", Shape::TimeValue),
    ("energy_accommodation", "1", Shape::TimeValue),
    ("pressure", "Pa", Shape::Scalar),
    ("projected_area", "m^2", Shape::Scalar),
];

pub fn quantity(q: &str) -> Option<(&'static str, Shape)> {
    QUANTITIES.iter().find(|(n, _, _)| *n == q).map(|(_, u, s)| (*u, *s))
}

/// Deposition rule of an interface heat key (prereg IF-HALL-THERMAL-v1 / IF-ICP-THERMAL-v1 `receiving`, E-07).
#[derive(Debug, Clone, Copy)]
pub enum Deposition {
    /// Never deposited (reference for the identities).
    Reference,
    /// Weight 1 on one node (or a registered partition over its subdivision sub-nodes).
    Fixed(&'static str),
    /// Weight 1 on `node`; when `node` is absent, a registered partition over ICP_NEUTRALIZER nodes (HK-08).
    FixedOrIcpPartitionWhenAbsent(&'static str),
    /// Registered or producer-predicted partition over the listed base ids; `export` allows an EXPORT share.
    Partition { allowed: &'static [&'static str], export: bool },
    /// Weight 1 on `default` unless a registered partition over `allowed` is declared (IK-02 induced shares).
    DefaultOrPartition { default: &'static str, allowed: &'static [&'static str] },
    /// Deposited on no node (IK-04).
    Export,
    /// N_MATCH iff match_colocated, else booked at B_PPU_RF (IK-03).
    MatchRule,
    /// Coil load: FIXED_POWER key on the named coil node.
    Coil(&'static str),
}

pub struct InterfaceKey {
    pub key: &'static str,
    pub units: &'static str,
    pub deposition: Deposition,
}

pub const HALL_INTERFACE_ID: &str = "IF-HALL-THERMAL-v1";
pub const ICP_INTERFACE_ID: &str = "IF-ICP-THERMAL-v1";
pub const INTERFACE_VERSION: &str = "v1";
pub const ICP_PRODUCER_ID: &str = "NP-ICP-NEUTRALIZER";

/// HK-01..HK-09 (discharge-supply keys).
pub const HALL_DISCHARGE_KEYS: [InterfaceKey; 9] = [
    InterfaceKey { key: "P_hall_discharge_W", units: "W", deposition: Deposition::Reference },
    InterfaceKey { key: "P_hall_jet_W", units: "W", deposition: Deposition::Reference },
    InterfaceKey { key: "Q_hall_anode_W", units: "W", deposition: Deposition::Fixed("H1_ANODE") },
    InterfaceKey { key: "Q_hall_wall_inner_W", units: "W", deposition: Deposition::Fixed("H1_WALL_IN") },
    InterfaceKey { key: "Q_hall_wall_outer_W", units: "W", deposition: Deposition::Fixed("H1_WALL_OUT") },
    InterfaceKey {
        key: "Q_hall_pole_W",
        units: "W",
        deposition: Deposition::Partition { allowed: &["H1_POLE_IN", "H1_POLE_OUT"], export: false },
    },
    InterfaceKey {
        key: "Q_hall_plasma_radiation_W",
        units: "W",
        deposition: Deposition::Partition {
            allowed: &[
                "H1_ANODE",
                "H1_WALL_IN",
                "H1_WALL_OUT",
                "H1_POLE_IN",
                "H1_POLE_OUT",
                "N_VESSEL",
                "N_COLLECTOR",
                "N_HOUSING",
            ],
            export: true,
        },
    },
    InterfaceKey {
        key: "Q_hall_return_to_icp_W",
        units: "W",
        deposition: Deposition::FixedOrIcpPartitionWhenAbsent("N_COLLECTOR"),
    },
    InterfaceKey {
        key: "Q_hall_plume_to_icp_W",
        units: "W",
        deposition: Deposition::Partition {
            allowed: &["N_VESSEL", "N_COLLECTOR", "N_HOUSING", "N_MOUNT"],
            export: false,
        },
    },
];

/// Coils: (position, node id, FIXED_POWER key, current key, reference resistance key, reference temperature key).
pub const COILS: [(&str, &str, &str, &str, &str, &str); 3] = [
    (
        "inner",
        "H1_COIL_IN",
        "Q_hall_coil_inner_W",
        "I_hall_coil_inner_A",
        "R_hall_coil_inner_ref_ohm",
        "T_hall_coil_inner_ref_K",
    ),
    (
        "outer",
        "H1_COIL_OUT",
        "Q_hall_coil_outer_W",
        "I_hall_coil_outer_A",
        "R_hall_coil_outer_ref_ohm",
        "T_hall_coil_outer_ref_K",
    ),
    (
        "trim",
        "H1_COIL_TRIM",
        "Q_hall_coil_trim_W",
        "I_hall_coil_trim_A",
        "R_hall_coil_trim_ref_ohm",
        "T_hall_coil_trim_ref_K",
    ),
];

/// IK-01..IK-07.
pub const ICP_KEYS: [InterfaceKey; 7] = [
    InterfaceKey {
        key: "Q_icp_plasma_wall_W",
        units: "W",
        deposition: Deposition::Partition {
            allowed: &["N_VESSEL", "N_COLLECTOR", "N_ANTENNA", "N_HOUSING"],
            export: false,
        },
    },
    InterfaceKey {
        key: "Q_icp_coil_ohmic_W",
        units: "W",
        deposition: Deposition::DefaultOrPartition {
            default: "N_ANTENNA",
            allowed: &["N_ANTENNA", "N_COLLECTOR", "N_HOUSING"],
        },
    },
    InterfaceKey { key: "Q_icp_match_W", units: "W", deposition: Deposition::MatchRule },
    InterfaceKey { key: "Q_icp_extraction_W", units: "W", deposition: Deposition::Export },
    InterfaceKey {
        key: "Q_icp_radiation_W",
        units: "W",
        deposition: Deposition::Partition {
            allowed: &["N_VESSEL", "N_ANTENNA", "N_COLLECTOR", "N_HOUSING", "H1_POLE_IN", "H1_POLE_OUT"],
            export: true,
        },
    },
    InterfaceKey { key: "P_icp_rf_forward_W", units: "W", deposition: Deposition::Reference },
    InterfaceKey { key: "P_icp_bus_W", units: "W", deposition: Deposition::Reference },
];

/// Units of every registered Hall interface key, including the coil keys.
pub fn hall_key_units(key: &str) -> Option<&'static str> {
    if let Some(k) = HALL_DISCHARGE_KEYS.iter().find(|k| k.key == key) {
        return Some(k.units);
    }
    for (_, _, q, i, r, t) in COILS {
        if key == q {
            return Some("W");
        }
        if key == i {
            return Some("A");
        }
        if key == r {
            return Some("ohm");
        }
        if key == t {
            return Some("K");
        }
    }
    None
}

pub fn icp_key(key: &str) -> Option<&'static InterfaceKey> {
    ICP_KEYS.iter().find(|k| k.key == key)
}

pub fn hall_discharge_key(key: &str) -> Option<&'static InterfaceKey> {
    HALL_DISCHARGE_KEYS.iter().find(|k| k.key == key)
}

/// Special partition receivers (E-07).
pub const EXPORT: &str = "EXPORT";
pub const BOUNDARY: &str = "BOUNDARY";

/// Boundaries a conductive link may end on (E-08; SCI-A, B_PPU_RF, B_FEED).
pub const LINK_BOUNDARIES: [&str; 3] = ["B_SC", "B_PPU_RF", "B_FEED"];
/// Radiative sinks (E-05): black enclosure surfaces.
pub const SINKS: [&str; 2] = ["SPACE", "B_FACILITY"];
pub const LINK_TYPES: [&str; 3] = ["CONDUCTION", "CONTACT", "LUMPED_G"];
pub const SHAPE_KINDS: [&str; 3] = ["SLAB", "CYLINDRICAL_SHELL", "SHAPE_FACTOR"];
pub const NODE_ROLES: [&str; 4] = ["REGISTERED", "SUBDIVISION", "MASSLESS_SERIES_JUNCTION", "ANALYTIC"];
pub const THERMAL_MASS_KINDS: [&str; 2] = ["LUMPED_C_OF_T", "MASSLESS_SERIES"];

// ------------------------------------------------------------------------------------------------ model 2.0.0

/// NP-THERMAL-CATHODELESS prereg v2 (model 2.0.0): the matched IF-ICP-THERMAL-v2 consumer. The rows below repeat the
/// producer's key table; `GovernedContextV2::load` reads the table from both locked preregistrations, checks its
/// canonical sha256 and that every row here names the same id and key (no row is invented here).
pub const ICP_V2_INTERFACE_ID: &str = "IF-ICP-THERMAL-v2";
pub const MODEL_VERSION_V2: &str = "2.0.0";

/// Consumer deposition rule of one IF-ICP-THERMAL-v2 key (matched_interface.consumer_deposition).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DepositionV2 {
    /// TK-R1..TK-R5: closure references, never deposited.
    Reference,
    /// Booked at B_PPU_RF, sub-account RF_SOURCE (TK-01, TK-02).
    BookedRfSource,
    /// B_PPU_RF RF_CHAIN, or N_MATCH for a registered co-located segment (TK-03).
    LineRule,
    /// N_MATCH iff match_colocated, else B_PPU_RF RF_CHAIN (TK-04, TK-05).
    MatchRule,
    /// Registered RI-PART split over the listed receivers, required (TK-06).
    RegisteredSplit(&'static [&'static str]),
    /// Producer per-node partition [W] over the v2 receivers of the key (TK-07; TK-12 signed).
    ProducerShares,
    /// Registered partition over the listed receivers with an EXPORT share (TK-08 f_rad).
    RegisteredWithExport(&'static [&'static str]),
    /// RX-H1-FACE: registered f_up with an EXPORT share; not needed when the key is exactly 0 (TK-10).
    RxH1Face(&'static [&'static str]),
    /// EXPORT, deposited on no node (TK-09, TK-11, TK-13).
    Export,
    /// A variant slot: exactly 0 when NOT_INSTALLED; installed -> INCOMPLETE_EVIDENCE (TK-14) or OUT_OF_DOMAIN (TK-15).
    Variant { out_of_domain: bool },
}

pub struct IcpKeyV2 {
    pub id: &'static str,
    pub key: &'static str,
    /// TK-12 / TK-13 only (IFI2-02).
    pub signed: bool,
    pub deposition: DepositionV2,
}

pub const ICP_V2_COIL_SPLIT: [&str; 4] = ["N_ANTENNA", "N_COLLECTOR", "N_HOUSING", "N_MOUNT"];
pub const ICP_V2_F_RAD: [&str; 6] = ["N_VESSEL", "N_ANTENNA", "N_COLLECTOR", "N_HOUSING", "H1_POLE_IN", "H1_POLE_OUT"];
/// RX-H1-FACE receivers (rx_h1_face.receivers; its EXPORT share is the partition's export weight).
pub const ICP_V2_RX_H1_FACE: [&str; 7] =
    ["H1_POLE_IN", "H1_POLE_OUT", "H1_WALL_IN", "H1_WALL_OUT", "H1_ANODE", "N_MOUNT", "N_HOUSING"];

pub const ICP_V2_KEYS: [IcpKeyV2; 20] = [
    IcpKeyV2 { id: "TK-R1", key: "P_icp_slot_load_sum_W", signed: false, deposition: DepositionV2::Reference },
    IcpKeyV2 { id: "TK-R2", key: "P_icp_rf_source_DC_W", signed: false, deposition: DepositionV2::Reference },
    IcpKeyV2 { id: "TK-R3", key: "P_icp_rf_forward_W", signed: false, deposition: DepositionV2::Reference },
    IcpKeyV2 { id: "TK-R4", key: "P_icp_abs_W", signed: false, deposition: DepositionV2::Reference },
    IcpKeyV2 { id: "TK-R5", key: "P_icp_collector_bias_W", signed: false, deposition: DepositionV2::Reference },
    IcpKeyV2 {
        id: "TK-01",
        key: "Q_icp_rf_conversion_loss_W",
        signed: false,
        deposition: DepositionV2::BookedRfSource,
    },
    IcpKeyV2 { id: "TK-02", key: "P_icp_rf_reflected_W", signed: false, deposition: DepositionV2::BookedRfSource },
    IcpKeyV2 { id: "TK-03", key: "Q_icp_line_W", signed: false, deposition: DepositionV2::LineRule },
    IcpKeyV2 { id: "TK-04", key: "Q_icp_match_W", signed: false, deposition: DepositionV2::MatchRule },
    IcpKeyV2 { id: "TK-05", key: "P_icp_matching_DC_W", signed: false, deposition: DepositionV2::MatchRule },
    IcpKeyV2 {
        id: "TK-06",
        key: "Q_icp_coil_ohmic_W",
        signed: false,
        deposition: DepositionV2::RegisteredSplit(&ICP_V2_COIL_SPLIT),
    },
    IcpKeyV2 { id: "TK-07", key: "Q_icp_plasma_wall_W", signed: false, deposition: DepositionV2::ProducerShares },
    IcpKeyV2 {
        id: "TK-08",
        key: "Q_icp_radiation_W",
        signed: false,
        deposition: DepositionV2::RegisteredWithExport(&ICP_V2_F_RAD),
    },
    IcpKeyV2 { id: "TK-09", key: "Q_icp_extraction_W", signed: false, deposition: DepositionV2::Export },
    IcpKeyV2 {
        id: "TK-10",
        key: "Q_icp_outflow_upstream_W",
        signed: false,
        deposition: DepositionV2::RxH1Face(&ICP_V2_RX_H1_FACE),
    },
    IcpKeyV2 { id: "TK-11", key: "Q_icp_outflow_downstream_W", signed: false, deposition: DepositionV2::Export },
    IcpKeyV2 { id: "TK-12", key: "Q_icp_bias_collector_W", signed: true, deposition: DepositionV2::ProducerShares },
    IcpKeyV2 { id: "TK-13", key: "Q_icp_bias_export_W", signed: true, deposition: DepositionV2::Export },
    IcpKeyV2 {
        id: "TK-14",
        key: "P_icp_flow_control_W",
        signed: false,
        deposition: DepositionV2::Variant { out_of_domain: false },
    },
    IcpKeyV2 {
        id: "TK-15",
        key: "P_icp_assist_magnet_W",
        signed: false,
        deposition: DepositionV2::Variant { out_of_domain: true },
    },
];

pub fn icp_v2_key(key: &str) -> Option<&'static IcpKeyV2> {
    ICP_V2_KEYS.iter().find(|k| k.key == key)
}

/// Retired keys (IFI2-10 RETIRED_KEY).
pub const ICP_V2_RETIRED_KEYS: [&str; 4] =
    ["P_icp_bus_W", "Q_icp_boundary_W", "Q_icp_rf_generator_loss_W", "Q_icp_bias_supply_loss_W"];

/// A Hall-discharge-powered key or a CPL-HALL-ON circuit key, refused inside the ICP record (IFI2-10
/// ENERGY_SOURCE_RULE).
pub fn icp_v2_energy_source_violation(key: &str) -> bool {
    key.starts_with("Q_hall_") || key.starts_with("P_hall_") || key.contains("_cpl_") || key.contains("hallon")
}

/// prereg v2 `replaced_items.nodes_receives_interface_keys`: the IF-ICP-THERMAL-v2 keys each node may receive (Hall
/// keys stay as v1).
pub const ICP_V2_RECEIVES: [(&str, &[&str]); 11] = [
    ("N_VESSEL", &["Q_icp_plasma_wall_W", "Q_icp_radiation_W"]),
    ("N_ANTENNA", &["Q_icp_coil_ohmic_W", "Q_icp_plasma_wall_W", "Q_icp_radiation_W"]),
    ("N_COLLECTOR", &["Q_icp_plasma_wall_W", "Q_icp_bias_collector_W", "Q_icp_coil_ohmic_W", "Q_icp_radiation_W"]),
    ("N_HOUSING", &["Q_icp_coil_ohmic_W", "Q_icp_plasma_wall_W", "Q_icp_radiation_W", "Q_icp_outflow_upstream_W"]),
    ("N_MATCH", &["Q_icp_match_W", "P_icp_matching_DC_W", "Q_icp_line_W"]),
    ("N_MOUNT", &["Q_icp_coil_ohmic_W", "Q_icp_plasma_wall_W", "Q_icp_outflow_upstream_W"]),
    ("H1_POLE_IN", &["Q_icp_radiation_W", "Q_icp_outflow_upstream_W"]),
    ("H1_POLE_OUT", &["Q_icp_radiation_W", "Q_icp_outflow_upstream_W"]),
    ("H1_WALL_IN", &["Q_icp_outflow_upstream_W"]),
    ("H1_WALL_OUT", &["Q_icp_outflow_upstream_W"]),
    ("H1_ANODE", &["Q_icp_outflow_upstream_W"]),
];

/// Whether `node` may receive the IF-ICP-THERMAL-v2 key `key` in model 2.0.0.
pub fn icp_v2_receives(node: &str, key: &str) -> bool {
    ICP_V2_RECEIVES.iter().any(|(n, ks)| *n == node && ks.contains(&key))
}

/// IFI2-11: configurations a 2.0.0 run consumes (CFG-FLIGHT-HALL-ON is NOT_EVALUATED).
pub const ICP_V2_CONFIGURATIONS: [&str; 3] = ["CFG-CAP-OFF", "SYNTHETIC", "PARAMETRIC"];
