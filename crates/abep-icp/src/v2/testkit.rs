//! model_version 2 case builders for verification. Every number is SYNTHETIC_TEST_ONLY (FC-15): the outputs are
//! labelled and can never be read as evidence. The real-mode template registers only what the repository registers
//! today; every other input is unregistered so the model reports why.

use super::case::*;
use crate::case::*;
use crate::chemistry::*;
use crate::constants::{AMU, F_RF_REGISTERED_HZ};
use crate::evidence::Registered;
use crate::geometry::*;
use crate::testkit::{arrhenius, excluded_all, explicit_h, owner, x_rate_flow, x_set, A_EC_M2, H_EDGE, L_M, R_M};
use std::collections::BTreeMap;
use std::f64::consts::PI;

pub use crate::testkit::syn;

pub fn surface(id: &str, kind: SurfaceKind, area: f64, o: Orientation, node: ThermalNode, material: &str) -> Surface {
    Surface {
        id: id.into(),
        kind,
        area_m2: area,
        orientation: o,
        material: material.into(),
        thermal_node: node,
        transmission: None,
    }
}

/// All-floating dielectric tube (radial wall + two floating end plates), one wall material.
pub fn floating_surfaces_v2() -> Vec<Surface> {
    crate::testkit::floating_surfaces()
}

/// CFG-CAP-OFF electrodes: radial wall, ion collector, electron collector (EXPORT), upstream open end (RX_H1_FACE).
pub fn capoff_surfaces_v2() -> Vec<Surface> {
    vec![
        surface(
            "wall",
            SurfaceKind::DielectricFloating,
            2.0 * PI * R_M * L_M,
            Orientation::Radial,
            ThermalNode::NVessel,
            "SYN_A",
        ),
        surface(
            "ic",
            SurfaceKind::IonCollectorBiased,
            PI * R_M * R_M,
            Orientation::Axial,
            ThermalNode::NCollector,
            "SYN_B",
        ),
        surface("ec", SurfaceKind::ElectronCollector, A_EC_M2, Orientation::Axial, ThermalNode::Export, "SYN_B"),
        surface(
            "up",
            SurfaceKind::OpenUpstream,
            0.5 * PI * R_M * R_M,
            Orientation::Axial,
            ThermalNode::RxH1Face,
            "OPEN",
        ),
    ]
}

/// Two open ends (upstream RX_H1_FACE, downstream EXPORT), two wall materials, no electrode: the disposition case.
pub fn two_end_surfaces(tau: Option<(f64, f64)>) -> Vec<Surface> {
    let mut up = surface(
        "up",
        SurfaceKind::OpenUpstream,
        0.5 * PI * R_M * R_M,
        Orientation::Axial,
        ThermalNode::RxH1Face,
        "OPEN",
    );
    let mut down = surface(
        "down",
        SurfaceKind::OpenDownstream,
        0.3 * PI * R_M * R_M,
        Orientation::Axial,
        ThermalNode::Export,
        "OPEN",
    );
    if let Some((tu, td)) = tau {
        up.transmission = Some(Transmission::Registered { tau: tu });
        down.transmission = Some(Transmission::Registered { tau: td });
    }
    vec![
        surface(
            "wall",
            SurfaceKind::DielectricFloating,
            2.0 * PI * R_M * L_M,
            Orientation::Radial,
            ThermalNode::NVessel,
            "SYN_A",
        ),
        surface(
            "plate",
            SurfaceKind::ConductorFloating,
            0.5 * PI * R_M * R_M,
            Orientation::Axial,
            ThermalNode::NHousing,
            "SYN_B",
        ),
        up,
        down,
    ]
}

fn geometry(surfaces: Vec<Surface>) -> Registered<GeometryV2> {
    syn(
        GeometryV2 {
            geometry_id: "SYNTHETIC_TUBE_V2".into(),
            radius_m: R_M,
            length_m: L_M,
            volume_mode: VolumeModeV2::AssumedGeometricTube,
            surfaces,
        },
        "geometry v2",
    )
}

/// A complete synthetic CFG-CAP-OFF / CM-ABS model_version 2 case in REGISTERED_PRESSURE mode (explicit h = 0.5).
/// Every biased surface gets supply ICP_COLLECTOR_BIAS; no bus registration (IF-ICP-BUS-v2 NOT_EVALUATED, NE-09).
pub fn case_v2(
    id: &str,
    set: ChemistrySet,
    surfaces: Vec<Surface>,
    potentials: &[(&str, f64)],
    p_abs_w: f64,
) -> IcpCaseV2 {
    let h = explicit_h(&surfaces, H_EDGE);
    let mut x: BTreeMap<String, f64> =
        set.species.iter().filter(|s| s.charge == 0).map(|s| (s.name.clone(), 0.0)).collect();
    let first = set.species.iter().find(|s| s.charge == 0).map(|s| s.name.clone()).expect("a neutral");
    x.insert(first, 1.0);
    IcpCaseV2 {
        case_id: id.into(),
        supply_mode: syn(SupplyMode::SyntheticTestOnly, "mode"),
        gas_mode: syn(GasMode::GReuse, "gas mode"),
        configuration: Configuration::CapOff,
        coupling_mode: CouplingMode::Absorbed,
        h1_point_id: Some("SYNTHETIC_POINT".into()),
        validation_cell_id: None,
        f_rf_hz: Some(syn(F_RF_REGISTERED_HZ, "f_RF")),
        rf_input: Some(RfInput::AbsorbedPower { p_abs_w: syn(p_abs_w, "P_abs") }),
        coupling_evidence: None,
        geometry: Some(geometry(surfaces)),
        electrodes: Some(syn(
            ElectrodesV2 {
                reference: "SYNTHETIC_REFERENCE".into(),
                potentials_v: potentials.iter().map(|(k, v)| (k.to_string(), *v)).collect(),
                supplies: potentials.iter().map(|(k, _)| (k.to_string(), SupplyIdentity::IcpCollectorBias)).collect(),
                collector_bias_sweep_v: None,
            },
            "electrodes",
        )),
        neutral_source: Some(NeutralSourceV2::RegisteredPressure {
            p_icp_pa: syn(1.0, "p_ICP"),
            t_g_k: syn(300.0, "T_g"),
            mole_fractions: syn(x, "x_k"),
        }),
        background: None,
        thermal_boundary: None,
        b_icp_max_t: Some(syn(0.0, "B_ICP,max")),
        chemistry: ChemistryRegistration::Synthetic { set },
        h_model: Some(h),
        wall_coefficients: vec![],
        dispositions: BTreeMap::new(),
        dissociation_energies_ev: BTreeMap::new(),
        dedicated_flow_kg_s: None,
        bus: None,
        coil_ohmic_split: None,
        hall_demand: None,
    }
}

pub fn floating_case_v2(p_abs_w: f64) -> IcpCaseV2 {
    case_v2("SYN_FLOATING_V2", x_set(crate::testkit::x_rate()), floating_surfaces_v2(), &[], p_abs_w)
}

pub fn capoff_case_v2(p_abs_w: f64, v_ic: f64, v_ec: f64) -> IcpCaseV2 {
    case_v2(
        "SYN_CAPOFF_V2",
        x_set(crate::testkit::x_rate()),
        capoff_surfaces_v2(),
        &[("ic", v_ic), ("ec", v_ec)],
        p_abs_w,
    )
}

/// A synthetic IF-ICP-BUS-v2 registration at the active boundary (no eta_bias: retired).
pub fn bus_v2(eta_rf: f64) -> BusRegistrationV2 {
    BusRegistrationV2 {
        boundary_id: crate::context::ACTIVE_BUS_BOUNDARY.into(),
        eta_rf: syn(eta_rf, "eta_RF"),
        p_match_dc_w: syn(2.0, "P_match,DC"),
        match_colocated: syn(true, "match_colocated"),
        assist_magnet: VariantSlot::NotInstalled,
        flow_control: VariantSlot::NotInstalled,
        ground_facility_rf_generator: false,
        eta_bias: None,
    }
}

/// A CM-CAL case with a registered RF chain (synthetic P2 point and bus): LC-17.
pub fn cal_case_v2(p_fwd_w: f64, p_refl_w: f64, v_ic: f64, v_ec: f64) -> IcpCaseV2 {
    let mut c = capoff_case_v2(0.0, v_ic, v_ec);
    c.case_id = "SYN_CAL_V2".into();
    c.coupling_mode = CouplingMode::Calibrated;
    c.rf_input = Some(RfInput::Forward { p_fwd_w: syn(p_fwd_w, "P_fwd"), p_refl_w: syn(p_refl_w, "P_refl") });
    c.coupling_evidence = Some(crate::testkit::synthetic_p2(2.0, 0.4, 0.3, 0.2));
    c.bus = Some(bus_v2(0.8));
    c.coil_ohmic_split =
        Some(syn([("N_ANTENNA".to_string(), 0.75), ("N_HOUSING".to_string(), 0.25)].into(), "TK-06 split"));
    c
}

/// FLOW_BALANCE single-gas X case with open ends of registered tau, an isotropic Maxwellian background and the given
/// inflow (LC-12 with `NoInflow`).
pub fn flow_case_v2(p_abs_w: f64, inflow: InflowV2, tau: f64, n_b_m3: f64, t_b_k: f64, t_g_k: f64) -> IcpCaseV2 {
    let mut s = floating_surfaces_v2();
    let mut down = surface(
        "down",
        SurfaceKind::OpenDownstream,
        0.5 * PI * R_M * R_M,
        Orientation::Axial,
        ThermalNode::Export,
        "OPEN",
    );
    down.transmission = Some(Transmission::Registered { tau });
    s[2] = down;
    let mut c = case_v2("SYN_FLOW_V2", x_set(x_rate_flow()), s, &[], p_abs_w);
    c.neutral_source = Some(NeutralSourceV2::FlowBalance {
        t_g_k: syn(t_g_k, "T_g"),
        sigma_c_m2: [("X".to_string(), syn(1e-19, "sigma_c"))].into(),
        inflow,
        f_in: None,
    });
    let n_b: BTreeMap<String, f64> = if n_b_m3 > 0.0 { [("X".to_string(), n_b_m3)].into() } else { BTreeMap::new() };
    c.background = Some(syn(BackgroundV2::IsotropicMaxwellian { n_b_m3: n_b, t_b_k }, "background"));
    c
}

/// Synthetic diatomic gas: X2 (elements {X: 2}), X, X2+ and X+. Channels: X2 ionization (15.6 eV), X2 dissociation
/// (header 9.8 eV vs D0 9.0 eV: fragment excess 0.8 eV), X ionization (13.6 eV), X2 elastic, X2 vibrational, X
/// electronic excitation (10.2 eV). Wall products: X2+ -> X2, X+ -> X.
pub fn x2_set() -> ChemistrySet {
    let m = 14.0 * AMU;
    let sp = |name: &str, mass: f64, charge: u32, nx: u32, wp: Vec<(String, u32)>| SpeciesDef {
        name: name.into(),
        mass_kg: mass,
        charge,
        elements: [("X".to_string(), nx)].into(),
        electronegative: false,
        wall_products: wp,
        recombines_to: None,
    };
    let rx = |id: &str, kind: ReactionKind, target: &str, products: Vec<(&str, u32)>, e: f64, k0: f64| ReactionDef {
        id: id.into(),
        kind,
        target: target.into(),
        products: products.into_iter().map(|(p, n)| (p.to_string(), n)).collect(),
        threshold_ev: e,
        rate: RateSource::Synthetic { rate: crate::chemistry::SyntheticRate { power: 0.5, ..arrhenius(k0, e) } },
        validity: Validity::Verified { max_mean_energy_ev: 255.0 },
    };
    ChemistrySet {
        set_id: "SYNTHETIC_X2".into(),
        species: vec![
            sp("X2", 2.0 * m, 0, 2, vec![]),
            sp("X", m, 0, 1, vec![]),
            sp("X2+", 2.0 * m, 1, 2, vec![("X2".into(), 1)]),
            sp("X+", m, 1, 1, vec![("X".into(), 1)]),
        ],
        reactions: vec![
            rx("ION_X2", ReactionKind::Ionization, "X2", vec![("X2+", 1)], 15.6, 1e-13),
            rx("DIS_X2", ReactionKind::Dissociation, "X2", vec![("X", 2)], 9.8, 5e-14),
            rx("ION_X", ReactionKind::Ionization, "X", vec![("X+", 1)], 13.6, 1e-13),
            rx("EL_X2", ReactionKind::ElasticMomentumTransfer, "X2", vec![("X2", 1)], 0.0, 1e-13),
            rx("VIB_X2", ReactionKind::ExcitationVibrational, "X2", vec![("X2", 1)], 0.3, 2e-14),
            rx("EXC_X", ReactionKind::ExcitationElectronic, "X", vec![("X", 1)], 10.2, 2e-14),
        ],
        process_classes: excluded_all(&["X2", "X", "X2+", "X+"]),
        t_e_domain_ev: [1.0, 100.0],
        vibrot_t_e_min_ev: 1.0,
    }
}

/// Synthetic D0(X2) [eV].
pub const D0_X2_EV: f64 = 9.0;

/// The disposition case (LC-15): X2 in REGISTERED_PRESSURE (x_X2 = 0.9, x_X = 0.1), two wall materials, two open ends.
pub fn disposition_case(tau: Option<(f64, f64)>) -> IcpCaseV2 {
    let mut c = case_v2("SYN_DISPOSITION_V2", x2_set(), two_end_surfaces(tau), &[], 20.0);
    c.neutral_source = Some(NeutralSourceV2::RegisteredPressure {
        p_icp_pa: syn(1.0, "p_ICP"),
        t_g_k: syn(300.0, "T_g"),
        mole_fractions: syn([("X2".to_string(), 0.9), ("X".to_string(), 0.1)].into(), "x_k"),
    });
    c.dissociation_energies_ev = [("X2".to_string(), syn(D0_X2_EV, "D0(X2)"))].into();
    c
}

/// A real-mode case holding only what the repository registers today (supply mode, G-REUSE, 13.56 MHz, chemistry).
pub fn registered_today_case_v2(mode: SupplyMode, chemistry: ChemistryRegistration) -> IcpCaseV2 {
    IcpCaseV2 {
        case_id: format!("REGISTERED_TODAY_V2_{}", mode.as_str()),
        supply_mode: Registered::new(
            mode,
            owner("A9.19 / config/architecture/hall_icp_neutralizer_v1.json; A9 evidence modes"),
        ),
        gas_mode: Registered::new(GasMode::GReuse, owner("A9.1 HIQ-06 (icp_feed_gas_baseline G-REUSE)")),
        configuration: Configuration::CapOff,
        coupling_mode: CouplingMode::Absorbed,
        h1_point_id: None,
        validation_cell_id: None,
        f_rf_hz: Some(Registered::new(F_RF_REGISTERED_HZ, owner("VI-RF-01; A9 decision 1 (13.56 MHz)"))),
        rf_input: None,
        coupling_evidence: None,
        geometry: None,
        electrodes: None,
        neutral_source: None,
        background: None,
        thermal_boundary: None,
        b_icp_max_t: None,
        chemistry,
        h_model: None,
        wall_coefficients: vec![],
        dispositions: BTreeMap::new(),
        dissociation_energies_ev: BTreeMap::new(),
        dedicated_flow_kg_s: None,
        bus: None,
        coil_ohmic_split: None,
        hall_demand: None,
    }
}
