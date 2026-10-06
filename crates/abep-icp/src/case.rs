//! Case registration: the inputs IN-01..IN-24 of one evaluation. An absent `Option` is an unregistered input; the
//! model reports it with the status the prereg assigns (never a default).

use crate::chemistry::ChemistryRegistration;
use crate::evidence::Registered;
use crate::geometry::{ElectrodeRegistration, Geometry, HModel};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// IN-01 supply / evidence mode. `SYNTHETIC_TEST_ONLY` is the analytic-verification mode of the LC cases: it is not a
/// flight or bench evidence mode, never transfers and labels every output (FC-15).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum SupplyMode {
    #[serde(rename = "AIR_PRIMARY")]
    AirPrimary,
    #[serde(rename = "XE_CONTINGENCY")]
    XeContingency,
    #[serde(rename = "EM-AR")]
    EmAr,
    #[serde(rename = "EM-N2")]
    EmN2,
    #[serde(rename = "EM-O2B")]
    EmO2b,
    #[serde(rename = "EM-XE")]
    EmXe,
    #[serde(rename = "SYNTHETIC_TEST_ONLY")]
    SyntheticTestOnly,
}

impl SupplyMode {
    pub fn as_str(self) -> &'static str {
        match self {
            SupplyMode::AirPrimary => "AIR_PRIMARY",
            SupplyMode::XeContingency => "XE_CONTINGENCY",
            SupplyMode::EmAr => "EM-AR",
            SupplyMode::EmN2 => "EM-N2",
            SupplyMode::EmO2b => "EM-O2B",
            SupplyMode::EmXe => "EM-XE",
            SupplyMode::SyntheticTestOnly => "SYNTHETIC_TEST_ONLY",
        }
    }
}

/// IN-02 ICP gas mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum GasMode {
    #[serde(rename = "G-REUSE")]
    GReuse,
    #[serde(rename = "G-ATM")]
    GAtm,
    #[serde(rename = "G-XE")]
    GXe,
}

impl GasMode {
    pub fn as_str(self) -> &'static str {
        match self {
            GasMode::GReuse => "G-REUSE",
            GasMode::GAtm => "G-ATM",
            GasMode::GXe => "G-XE",
        }
    }
}

/// IN-03 configuration.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Configuration {
    #[serde(rename = "CFG-CAP-OFF")]
    CapOff,
    #[serde(rename = "CFG-FLIGHT-HALL-ON")]
    FlightHallOn,
}

impl Configuration {
    pub fn as_str(self) -> &'static str {
        match self {
            Configuration::CapOff => "CFG-CAP-OFF",
            Configuration::FlightHallOn => "CFG-FLIGHT-HALL-ON",
        }
    }
}

/// Coupling mode (prereg sec. 5).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CouplingMode {
    #[serde(rename = "CM-ABS")]
    Absorbed,
    #[serde(rename = "CM-CAL")]
    Calibrated,
    #[serde(rename = "CM-PRED")]
    Predictive,
}

impl CouplingMode {
    pub fn as_str(self) -> &'static str {
        match self {
            CouplingMode::Absorbed => "CM-ABS",
            CouplingMode::Calibrated => "CM-CAL",
            CouplingMode::Predictive => "CM-PRED",
        }
    }
}

/// IN-08 RF electrical input.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RfInput {
    /// CM-ABS: absorbed plasma power [W].
    AbsorbedPower { p_abs_w: Registered<f64> },
    /// CM-CAL / CM-PRED: forward and reflected power at RP-CPL [W].
    Forward { p_fwd_w: Registered<f64>, p_refl_w: Registered<f64> },
}

/// Reference-plane convention of R_ant and the power (EQ-12 notes).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PlaneConvention {
    /// R_ant = P_delivered / I_ant^2 without plasma (required for IF-ICP-THERMAL-v1).
    #[serde(rename = "RP_ANT")]
    RpAnt,
    /// R_ant = P_net / I_ant^2 without plasma (line and match lumped; flag LUMPED_R_VAC).
    #[serde(rename = "R_VAC")]
    RVac,
}

/// One registered P2 impedance-map point (EQ-13; P2 framework ZM-A / ZM-B). v1 evaluates only at a registered map
/// point; between points the P2-registered interpolation rule would apply and is NOT_EVALUATED here.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct P2Point {
    pub map_id: String,
    pub content_sha256: String,
    pub record_ids: Vec<String>,
    /// "ZM-A" or "ZM-B".
    pub method: String,
    /// The map passed the P2 framework validation (`validate_map`).
    pub map_validated: bool,
    /// Must be "EVALUATED".
    pub uncertainty_status: String,
    /// UNLIT | E_MODE | H_MODE | UNCERTAIN; CM-CAL needs H_MODE (DOM-08).
    pub plasma_state_class: String,
    /// The operating point is a registered map point (DOM-09).
    pub at_map_point: bool,
    pub z_antenna_hot_re_ohm: f64,
    pub z_antenna_hot_im_ohm: f64,
    pub r_ant_cold_ohm: f64,
    pub plane_convention: PlaneConvention,
    /// RP-CPL -> RP-MIN line loss and match loss at the logged tuning state [W] (RP_ANT convention).
    pub q_line_w: Option<f64>,
    pub q_match_w: Option<f64>,
}

/// IN-09 coupling evidence.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CouplingEvidence {
    P2Point {
        point: Box<Registered<P2Point>>,
    },
    /// CM-PRED antenna registration (N_ant, r_ant, L_ant, d_ant, R_ant,cold). Gated: never evaluated in v1.
    PredictiveAntenna {
        n_turns: f64,
        r_ant_m: f64,
        l_ant_m: f64,
        d_ant_m: f64,
        r_ant_cold_ohm: f64,
    },
}

/// IN-12 pressure / neutral density.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum NeutralSource {
    /// EQ-01: n_g,k = x_k p_ICP / (k_B T_g).
    RegisteredPressure {
        p_icp_pa: Registered<f64>,
        t_g_k: Registered<f64>,
        mole_fractions: Registered<BTreeMap<String, f64>>,
    },
    /// EQ-02: neutral balance with the delivered feed (IN-04) times f_in, background inflow (IN-13), effusion and wall
    /// recombination. sigma_c per neutral species for the DOM-04 Knudsen check.
    FlowBalance { f_in: Registered<f64>, t_g_k: Registered<f64>, sigma_c_m2: BTreeMap<String, Registered<f64>> },
}

/// IN-04 delivered feed state.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FeedState {
    pub mdot_kg_s: BTreeMap<String, f64>,
    pub p_feed_pa: f64,
    pub t_feed_k: f64,
    pub x_s: BTreeMap<String, f64>,
}

/// IN-13 background neutral source (bench: facility gauge; flight: environment x exposure).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Background {
    pub n_b_m3: BTreeMap<String, f64>,
    pub t_b_k: f64,
}

/// IN-14 thermal boundary inputs other than T_g (which belongs to IN-12). Echoed; v1 uses no wall temperature.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ThermalBoundary {
    pub t_wall_k: BTreeMap<String, f64>,
    pub t_coil_k: Option<f64>,
}

/// IN-23 energy disposition of an inelastic channel.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Disposition {
    RadiatedOpticallyThin,
    WallQuenched,
    CarriedOut,
    Unresolved,
}

/// A bus-plane variant slot (icp_assist_magnet, flow_control_icp_feed).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum VariantSlot {
    NotInstalled,
    Installed { p_w: Registered<f64> },
}

/// IN-19 RF chain and bias-supply registration for IF-ICP-BUS-v1.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BusRegistration {
    /// Target boundary; the active one is `bus_power_boundary_a9_v2` (A9.22 G8; A9.30 sec. 5).
    pub boundary_id: String,
    pub eta_rf: Registered<f64>,
    pub p_match_dc_w: Registered<f64>,
    pub eta_bias: Registered<f64>,
    pub match_colocated: Registered<bool>,
    pub assist_magnet: VariantSlot,
    pub flow_control: VariantSlot,
    /// A laboratory generator efficiency or mains input (never spacecraft bus power).
    pub ground_facility_only: bool,
}

/// Basis of an I_d,max,H1 registration (IN-20).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum HallDemandBasis {
    /// (b) registered measured value (P1-IT-07; H-1 + C1 reference characterization).
    MeasuredRegistration,
    /// (a) an admitted HallThruster.jl member with a design-specific Hall map.
    AdmittedHallMember,
    /// Refused: a screening candidate.
    ScreeningCandidate,
    /// Refused: the stand / supply rating (8.33 A).
    SupplyRating,
}

/// IN-20 Hall discharge-current demand.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HallDemand {
    pub i_d_max_h1_a: Registered<f64>,
    pub basis: HallDemandBasis,
    pub h1_point_id: String,
}

/// IN-18 wall recombination probability for an atom species.
pub type WallRecombination = BTreeMap<String, Registered<f64>>;

/// One evaluation case.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IcpCase {
    pub case_id: String,
    pub supply_mode: Registered<SupplyMode>,
    pub gas_mode: Registered<GasMode>,
    pub configuration: Configuration,
    pub coupling_mode: CouplingMode,
    pub h1_point_id: Option<String>,
    pub f_rf_hz: Option<Registered<f64>>,
    pub rf_input: Option<RfInput>,
    pub coupling_evidence: Option<CouplingEvidence>,
    pub geometry: Option<Registered<Geometry>>,
    pub electrodes: Option<Registered<ElectrodeRegistration>>,
    pub neutral_source: Option<NeutralSource>,
    pub feed: Option<Registered<FeedState>>,
    pub background: Option<Registered<Background>>,
    pub thermal_boundary: Option<Registered<ThermalBoundary>>,
    pub b_icp_max_t: Option<Registered<f64>>,
    pub chemistry: ChemistryRegistration,
    pub h_model: Option<HModel>,
    pub wall_recombination: WallRecombination,
    pub dispositions: BTreeMap<String, Registered<Disposition>>,
    pub dedicated_flow_kg_s: Option<Registered<BTreeMap<String, f64>>>,
    pub bus: Option<BusRegistration>,
    pub hall_demand: Option<HallDemand>,
}
