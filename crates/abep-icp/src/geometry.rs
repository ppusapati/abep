//! IN-10 geometry and bounding surfaces, IN-11 electrode registration, IN-17 edge-to-centre factors.

use crate::evidence::Registered;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Surface types of IN-10.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum SurfaceKind {
    #[serde(rename = "DIELECTRIC_FLOATING")]
    DielectricFloating,
    #[serde(rename = "CONDUCTOR_FLOATING")]
    ConductorFloating,
    #[serde(rename = "ION_COLLECTOR_BIASED")]
    IonCollectorBiased,
    #[serde(rename = "ELECTRON_COLLECTOR")]
    ElectronCollector,
    #[serde(rename = "OPEN_UPSTREAM")]
    OpenUpstream,
    #[serde(rename = "OPEN_DOWNSTREAM")]
    OpenDownstream,
}

impl SurfaceKind {
    /// Held at a registered potential (IN-11): the current balance EQ-10 involves only these.
    pub fn is_biased(self) -> bool {
        matches!(self, SurfaceKind::IonCollectorBiased | SurfaceKind::ElectronCollector)
    }

    /// Floating or open: zero net current (EQ-10; open ends by declared assumption).
    pub fn is_zero_current(self) -> bool {
        !self.is_biased()
    }

    pub fn is_open(self) -> bool {
        matches!(self, SurfaceKind::OpenUpstream | SurfaceKind::OpenDownstream)
    }

    /// Neutralizer surfaces in contact with the plasma (Q_icp_plasma_wall_W): not the electron sink, not an open end.
    pub fn is_neutralizer_wall(self) -> bool {
        matches!(
            self,
            SurfaceKind::DielectricFloating | SurfaceKind::ConductorFloating | SurfaceKind::IonCollectorBiased
        )
    }
}

/// Edge-factor role of a surface for H-LIEB (radial h_R or axial h_L; an open end is axial, VER-07).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Orientation {
    Radial,
    Axial,
}

/// Thermal node of IN-10.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub enum ThermalNode {
    #[serde(rename = "N_VESSEL")]
    NVessel,
    #[serde(rename = "N_ANTENNA")]
    NAntenna,
    #[serde(rename = "N_MOUNT")]
    NMount,
    #[serde(rename = "N_COLLECTOR")]
    NCollector,
    #[serde(rename = "N_HOUSING")]
    NHousing,
    #[serde(rename = "EXPORT")]
    Export,
    #[serde(rename = "H1_FACES")]
    H1Faces,
    /// model_version 2 (IN-10 v2): the upstream open end delivers its outflow to RX-H1-FACE, the registered H-1-facing
    /// receiver interface of NP-THERMAL-CATHODELESS v2 (TK-10). Refused by the v1 surface contract.
    #[serde(rename = "RX_H1_FACE")]
    RxH1Face,
}

impl ThermalNode {
    pub fn as_str(self) -> &'static str {
        match self {
            ThermalNode::NVessel => "N_VESSEL",
            ThermalNode::NAntenna => "N_ANTENNA",
            ThermalNode::NMount => "N_MOUNT",
            ThermalNode::NCollector => "N_COLLECTOR",
            ThermalNode::NHousing => "N_HOUSING",
            ThermalNode::Export => "EXPORT",
            ThermalNode::H1Faces => "H1_FACES",
            ThermalNode::RxH1Face => "RX_H1_FACE",
        }
    }

    pub fn is_neutralizer_node(self) -> bool {
        !matches!(self, ThermalNode::Export | ThermalNode::H1Faces | ThermalNode::RxH1Face)
    }
}

/// Free-molecular transmission probability of an open end (EQ-02).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Transmission {
    /// A sourced tau in [0, 1].
    Registered { tau: f64 },
    /// Santeler form for a circular tube of the given length and radius (Chiggiato 2014 Eq. 21).
    SantelerTube { length_m: f64, radius_m: f64 },
}

/// One bounding surface j.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Surface {
    pub id: String,
    pub kind: SurfaceKind,
    pub area_m2: f64,
    pub orientation: Orientation,
    pub material: String,
    pub thermal_node: ThermalNode,
    /// Open ends only; needed by FLOW_BALANCE effusion.
    pub transmission: Option<Transmission>,
}

/// Effective-volume mode (OQ-NPICP-12; no default).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum VolumeMode {
    /// V = pi R^2 L of the dielectric bore (declared assumption, flag GEOMETRIC_TUBE_VOLUME_ASSUMED).
    GeometricTube,
    /// A sourced effective volume.
    RegisteredEffective { volume_m3: f64 },
}

/// IN-10 plasma geometry.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Geometry {
    pub geometry_id: String,
    pub radius_m: f64,
    pub length_m: f64,
    pub volume_mode: VolumeMode,
    pub surfaces: Vec<Surface>,
}

impl Geometry {
    pub fn volume_m3(&self) -> f64 {
        match self.volume_mode {
            VolumeMode::GeometricTube => std::f64::consts::PI * self.radius_m * self.radius_m * self.length_m,
            VolumeMode::RegisteredEffective { volume_m3 } => volume_m3,
        }
    }

    /// Structural contract checks (a violation is MODEL_ERROR: an internal contract breach, not missing evidence).
    pub fn contract_violations(&self) -> Vec<String> {
        let mut v = Vec::new();
        let pos = |x: f64| x.is_finite() && x > 0.0;
        if !pos(self.radius_m) || !pos(self.length_m) {
            v.push("radius_m and length_m must be finite and > 0".into());
        }
        if let VolumeMode::RegisteredEffective { volume_m3 } = self.volume_mode {
            if !pos(volume_m3) {
                v.push("registered effective volume must be finite and > 0".into());
            }
        }
        if self.surfaces.is_empty() {
            v.push("no bounding surface registered".into());
        }
        let mut ids = std::collections::BTreeSet::new();
        let mut n_ec = 0;
        for s in &self.surfaces {
            if !ids.insert(s.id.as_str()) {
                v.push(format!("duplicate surface id {}", s.id));
            }
            if !pos(s.area_m2) {
                v.push(format!("surface {}: area must be finite and > 0", s.id));
            }
            match s.kind {
                SurfaceKind::ElectronCollector => {
                    n_ec += 1;
                    if s.thermal_node != ThermalNode::Export {
                        v.push(format!("surface {}: the electron sink maps to EXPORT (Q_icp_extraction_W)", s.id));
                    }
                }
                SurfaceKind::OpenDownstream if s.thermal_node != ThermalNode::Export => {
                    v.push(format!("surface {}: the downstream open end maps to EXPORT", s.id));
                }
                SurfaceKind::OpenUpstream if s.thermal_node != ThermalNode::H1Faces => {
                    v.push(format!("surface {}: the upstream open end maps to H1_FACES", s.id));
                }
                k if k.is_neutralizer_wall() && !s.thermal_node.is_neutralizer_node() => {
                    v.push(format!("surface {}: a neutralizer wall maps to an N_* node", s.id));
                }
                _ => {}
            }
            match &s.transmission {
                Some(_) if !s.kind.is_open() => v.push(format!("surface {}: transmission only on open ends", s.id)),
                Some(Transmission::Registered { tau }) if !(tau.is_finite() && (0.0..=1.0).contains(tau)) => {
                    v.push(format!("surface {}: tau outside [0, 1]", s.id))
                }
                Some(Transmission::SantelerTube { length_m, radius_m })
                    if !(length_m.is_finite() && *length_m >= 0.0 && pos(*radius_m)) =>
                {
                    v.push(format!("surface {}: Santeler tube needs length >= 0 and radius > 0", s.id))
                }
                _ => {}
            }
        }
        if n_ec > 1 {
            v.push("at most one ELECTRON_COLLECTOR (I_e_cap_A is defined for the registered electron sink)".into());
        }
        v
    }
}

/// IN-11 electrode registration (CFG-CAP-OFF; P1-IT-36 form). Potentials are against `reference`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ElectrodeRegistration {
    pub reference: String,
    /// Potential [V] of every ION_COLLECTOR_BIASED and ELECTRON_COLLECTOR surface, by surface id.
    pub potentials_v: BTreeMap<String, f64>,
    /// Registered electron-collector bias values [V] up to V_bias,max for I_e_sat_A (EQ-11); None -> NOT_EVALUATED.
    pub collector_bias_sweep_v: Option<Vec<f64>>,
}

/// IN-17 edge-to-centre factor model (EQ-05; no default).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum HModel {
    /// H-EXPLICIT: a sourced h_j for every surface, by surface id.
    Explicit { h_by_surface: BTreeMap<String, Registered<f64>> },
    /// H-LIEB: sourced ion-neutral cross section sigma_i,s [m^2] per ion species.
    Lieberman { sigma_i_m2: BTreeMap<String, Registered<f64>> },
}
