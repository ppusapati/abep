//! Case builders for verification. Every number here is SYNTHETIC_TEST_ONLY (FC-15): the outputs are labelled and can
//! never be read as evidence. The real-mode template registers only what the repository registers today (owner
//! decisions and the pinned N2/N set); every other input is left unregistered so the model reports why.

use crate::case::*;
use crate::chemistry::*;
use crate::constants::{AMU, F_RF_REGISTERED_HZ};
use crate::evidence::{EvidenceRecord, QuantityType, Registered, UncertaintyRepr};
use crate::geometry::*;
use std::collections::BTreeMap;
use std::f64::consts::PI;

pub fn syn<T>(v: T, what: &str) -> Registered<T> {
    Registered::synthetic(v, what)
}

/// Synthetic atomic gas mass (40 u: the repository's argon round-off convention, tests/test_interstage.py).
pub const M_X_KG: f64 = 40.0 * AMU;
/// Synthetic ionization threshold [eV].
pub const E_IZ_X_EV: f64 = 15.0;
/// Synthetic tube.
pub const R_M: f64 = 0.02;
pub const L_M: f64 = 0.1;
pub const H_EDGE: f64 = 0.5;

pub fn excluded_all(species: &[&str]) -> BTreeMap<String, BTreeMap<ProcessClass, ClassAddress>> {
    species
        .iter()
        .map(|s| {
            (
                s.to_string(),
                ProcessClass::ALL
                    .iter()
                    .map(|c| (*c, ClassAddress::Excluded { justification: "SYNTHETIC_TEST_ONLY analytic case".into() }))
                    .collect(),
            )
        })
        .collect()
}

pub fn arrhenius(k0: f64, e_act: f64) -> SyntheticRate {
    SyntheticRate { k0_m3_s: k0, t_ref_ev: 1.0, power: 0.0, e_act_ev: e_act, t_cut_ev: None }
}

/// Single atomic gas X, one ion X+ (Z = 1), ionization only (LC-01 / LC-02 set).
pub fn x_set(rate: SyntheticRate) -> ChemistrySet {
    ChemistrySet {
        set_id: "SYNTHETIC_X".into(),
        species: vec![
            SpeciesDef {
                name: "X".into(),
                mass_kg: M_X_KG,
                charge: 0,
                elements: [("X".to_string(), 1)].into(),
                electronegative: false,
                wall_products: vec![],
                recombines_to: None,
            },
            SpeciesDef {
                name: "X+".into(),
                mass_kg: M_X_KG,
                charge: 1,
                elements: [("X".to_string(), 1)].into(),
                electronegative: false,
                wall_products: vec![("X".into(), 1)],
                recombines_to: None,
            },
        ],
        reactions: vec![ReactionDef {
            id: "ION_X".into(),
            kind: ReactionKind::Ionization,
            target: "X".into(),
            products: vec![("X+".into(), 1)],
            threshold_ev: E_IZ_X_EV,
            rate: RateSource::Synthetic { rate },
            validity: Validity::Verified { max_mean_energy_ev: 255.0 },
        }],
        process_classes: excluded_all(&["X", "X+"]),
        t_e_domain_ev: [1.0, 100.0],
        vibrot_t_e_min_ev: 1.0,
    }
}

/// The nominal synthetic ionization rate (root near T_e = 3 eV in the tube cases).
pub fn x_rate() -> SyntheticRate {
    arrhenius(1e-13, E_IZ_X_EV)
}

fn surface(id: &str, kind: SurfaceKind, area: f64, o: Orientation, node: ThermalNode) -> Surface {
    Surface {
        id: id.into(),
        kind,
        area_m2: area,
        orientation: o,
        material: "SYNTHETIC".into(),
        thermal_node: node,
        transmission: None,
    }
}

/// All-floating dielectric tube (LC-01, LC-02, LC-06, LC-07): radial wall + two floating end plates.
pub fn floating_surfaces() -> Vec<Surface> {
    vec![
        surface(
            "wall",
            SurfaceKind::DielectricFloating,
            2.0 * PI * R_M * L_M,
            Orientation::Radial,
            ThermalNode::NVessel,
        ),
        surface("end_up", SurfaceKind::DielectricFloating, PI * R_M * R_M, Orientation::Axial, ThermalNode::NMount),
        surface("end_down", SurfaceKind::ConductorFloating, PI * R_M * R_M, Orientation::Axial, ThermalNode::NHousing),
    ]
}

/// CFG-CAP-OFF electrodes: large ion collector at V_ic, small electron collector at V_ec (A_ic >> A_ec).
pub const A_EC_M2: f64 = 2e-6;
pub fn capoff_surfaces() -> Vec<Surface> {
    vec![
        surface(
            "wall",
            SurfaceKind::DielectricFloating,
            2.0 * PI * R_M * L_M,
            Orientation::Radial,
            ThermalNode::NVessel,
        ),
        surface("ic", SurfaceKind::IonCollectorBiased, PI * R_M * R_M, Orientation::Axial, ThermalNode::NCollector),
        surface("ec", SurfaceKind::ElectronCollector, A_EC_M2, Orientation::Axial, ThermalNode::Export),
        surface("up", SurfaceKind::OpenUpstream, 0.5 * PI * R_M * R_M, Orientation::Axial, ThermalNode::H1Faces),
    ]
}

pub fn explicit_h(surfaces: &[Surface], h: f64) -> HModel {
    HModel::Explicit { h_by_surface: surfaces.iter().map(|s| (s.id.clone(), syn(h, "explicit h"))).collect() }
}

/// A complete synthetic CFG-CAP-OFF / CM-ABS case in REGISTERED_PRESSURE mode.
pub fn synthetic_case(
    id: &str,
    set: ChemistrySet,
    surfaces: Vec<Surface>,
    potentials: &[(&str, f64)],
    p_abs_w: f64,
) -> IcpCase {
    let h = explicit_h(&surfaces, H_EDGE);
    let neutrals: BTreeMap<String, f64> =
        set.species.iter().filter(|s| s.charge == 0).map(|s| (s.name.clone(), 0.0)).collect();
    let mut x = neutrals;
    let first = set.species.iter().find(|s| s.charge == 0).map(|s| s.name.clone()).expect("a neutral");
    x.insert(first, 1.0);
    IcpCase {
        case_id: id.into(),
        supply_mode: syn(SupplyMode::SyntheticTestOnly, "mode"),
        gas_mode: syn(GasMode::GReuse, "gas mode"),
        configuration: Configuration::CapOff,
        coupling_mode: CouplingMode::Absorbed,
        h1_point_id: Some("SYNTHETIC_POINT".into()),
        f_rf_hz: Some(syn(F_RF_REGISTERED_HZ, "f_RF")),
        rf_input: Some(RfInput::AbsorbedPower { p_abs_w: syn(p_abs_w, "P_abs") }),
        coupling_evidence: None,
        geometry: Some(syn(
            Geometry {
                geometry_id: "SYNTHETIC_TUBE".into(),
                radius_m: R_M,
                length_m: L_M,
                volume_mode: VolumeMode::GeometricTube,
                surfaces,
            },
            "geometry",
        )),
        electrodes: Some(syn(
            ElectrodeRegistration {
                reference: "SYNTHETIC_REFERENCE".into(),
                potentials_v: potentials.iter().map(|(k, v)| (k.to_string(), *v)).collect(),
                collector_bias_sweep_v: None,
            },
            "electrodes",
        )),
        neutral_source: Some(NeutralSource::RegisteredPressure {
            p_icp_pa: syn(1.0, "p_ICP"),
            t_g_k: syn(300.0, "T_g"),
            mole_fractions: syn(x, "x_k"),
        }),
        feed: None,
        background: None,
        thermal_boundary: None,
        b_icp_max_t: Some(syn(0.0, "B_ICP,max")),
        chemistry: ChemistryRegistration::Synthetic { set },
        h_model: Some(h),
        wall_recombination: BTreeMap::new(),
        dispositions: BTreeMap::new(),
        dedicated_flow_kg_s: None,
        bus: None,
        hall_demand: None,
    }
}

/// LC-01 / LC-02 case: single gas, all-floating tube.
pub fn floating_case(p_abs_w: f64) -> IcpCase {
    synthetic_case("SYN_FLOATING", x_set(x_rate()), floating_surfaces(), &[], p_abs_w)
}

/// CFG-CAP-OFF case with an ion collector at V_ic and the electron sink at V_ec.
pub fn capoff_case(p_abs_w: f64, v_ic: f64, v_ec: f64) -> IcpCase {
    synthetic_case("SYN_CAPOFF", x_set(x_rate()), capoff_surfaces(), &[("ic", v_ic), ("ec", v_ec)], p_abs_w)
}

/// Adds an electronic excitation channel X -> X* (threshold 11.5 eV) whose disposition is left UNRESOLVED.
pub fn with_excitation(mut set: ChemistrySet) -> ChemistrySet {
    set.reactions.push(ReactionDef {
        id: "EXC_X".into(),
        kind: ReactionKind::ExcitationElectronic,
        target: "X".into(),
        products: vec![("X".into(), 1)],
        threshold_ev: 11.5,
        rate: RateSource::Synthetic { rate: arrhenius(3e-14, 11.5) },
        validity: Validity::Verified { max_mean_energy_ev: 255.0 },
    });
    set
}

/// Adds X+ -> X++ (sequential, Z = 2): n_e no longer cancels (nonlinear REGISTERED_PRESSURE case; VER-08 path).
pub fn with_double_ion(mut set: ChemistrySet) -> ChemistrySet {
    set.species.push(SpeciesDef {
        name: "X++".into(),
        mass_kg: M_X_KG,
        charge: 2,
        elements: [("X".to_string(), 1)].into(),
        electronegative: false,
        wall_products: vec![("X".into(), 1)],
        recombines_to: None,
    });
    set.reactions.push(ReactionDef {
        id: "ION_X+".into(),
        kind: ReactionKind::Ionization,
        target: "X+".into(),
        products: vec![("X++".into(), 1)],
        threshold_ev: 27.6,
        rate: RateSource::Synthetic { rate: arrhenius(5e-14, 27.6) },
        validity: Validity::Verified { max_mean_energy_ev: 255.0 },
    });
    set.process_classes = excluded_all(&["X", "X+", "X++"]);
    set
}

/// Synthetic rate for the FLOW_BALANCE cases: k = k0 sqrt(T_e) exp(-E/T_e), so k / u_B rises monotonically and the
/// quasi-neutrality residual has one root at every n_e (a pure Arrhenius form saturates while u_B grows and adds a
/// spurious high-T_e root, which the solver refuses to choose between).
pub fn x_rate_flow() -> SyntheticRate {
    SyntheticRate { k0_m3_s: 1e-13, t_ref_ev: 1.0, power: 0.5, e_act_ev: E_IZ_X_EV, t_cut_ev: None }
}

/// FLOW_BALANCE case: feed through an open downstream end of transmission tau (EQ-02), no background.
pub fn flow_case(p_abs_w: f64, mdot_kg_s: f64, tau: f64) -> IcpCase {
    let mut s = capoff_surfaces();
    s[3] = Surface {
        transmission: Some(Transmission::Registered { tau }),
        ..surface("down", SurfaceKind::OpenDownstream, 0.5 * PI * R_M * R_M, Orientation::Axial, ThermalNode::Export)
    };
    let mut c = synthetic_case("SYN_FLOW", x_set(x_rate_flow()), s, &[("ic", 0.0), ("ec", 30.0)], p_abs_w);
    c.neutral_source = Some(NeutralSource::FlowBalance {
        f_in: syn(1.0, "f_in"),
        t_g_k: syn(300.0, "T_g"),
        sigma_c_m2: [("X".to_string(), syn(1e-19, "sigma_c"))].into(),
    });
    c.feed = Some(syn(
        FeedState {
            mdot_kg_s: [("X".to_string(), mdot_kg_s)].into(),
            p_feed_pa: 1.0,
            t_feed_k: 300.0,
            x_s: [("X".to_string(), 1.0)].into(),
        },
        "feed",
    ));
    c.background = Some(syn(Background { n_b_m3: BTreeMap::new(), t_b_k: 300.0 }, "background"));
    c
}

/// A synthetic P2 point (CM-CAL verification only).
pub fn synthetic_p2(z_re: f64, r_cold: f64, q_line: f64, q_match: f64) -> CouplingEvidence {
    CouplingEvidence::P2Point {
        point: Box::new(syn(
            P2Point {
                map_id: "SYNTHETIC_MAP".into(),
                content_sha256: "0".repeat(64),
                record_ids: vec!["SYN-1".into()],
                method: "ZM-A".into(),
                map_validated: true,
                uncertainty_status: "EVALUATED".into(),
                plasma_state_class: "H_MODE".into(),
                at_map_point: true,
                z_antenna_hot_re_ohm: z_re,
                z_antenna_hot_im_ohm: 120.0,
                r_ant_cold_ohm: r_cold,
                plane_convention: PlaneConvention::RpAnt,
                q_line_w: Some(q_line),
                q_match_w: Some(q_match),
            },
            "P2 point",
        )),
    }
}

/// A synthetic bus registration at the active boundary.
pub fn synthetic_bus(eta_rf: f64, eta_bias: f64) -> BusRegistration {
    BusRegistration {
        boundary_id: crate::context::ACTIVE_BUS_BOUNDARY.into(),
        eta_rf: syn(eta_rf, "eta_RF"),
        p_match_dc_w: syn(2.0, "P_match,DC"),
        eta_bias: syn(eta_bias, "eta_bias"),
        match_colocated: syn(true, "match_colocated"),
        assist_magnet: VariantSlot::NotInstalled,
        flow_control: VariantSlot::NotInstalled,
        ground_facility_only: false,
    }
}

/// An evidence record for an owner decision (categorical input).
pub fn owner(source: &str) -> EvidenceRecord {
    EvidenceRecord {
        source: Some(source.into()),
        evidence_level: Some("OWNER_DECISION".into()),
        quantity_type: Some(QuantityType::OwnerDecision),
        transformation_chain: Some("owner decision record, as registered".into()),
        uncertainty: Some(UncertaintyRepr::Categorical),
        applicability_domain: Some("hall_icp_neutralizer".into()),
        validation_status: Some("NOT_APPLICABLE_DECISION".into()),
    }
}

/// A real-mode CFG-CAP-OFF / CM-ABS case holding only what the repository registers today: the supply mode, the
/// G-REUSE gas mode, 13.56 MHz and the chemistry registration. Every other input is unregistered (None).
pub fn registered_today_case(mode: SupplyMode, chemistry: ChemistryRegistration) -> IcpCase {
    IcpCase {
        case_id: format!("REGISTERED_TODAY_{}", mode.as_str()),
        supply_mode: Registered::new(
            mode,
            owner("A9.19 / config/architecture/hall_icp_neutralizer_v1.json; A9 evidence modes"),
        ),
        gas_mode: Registered::new(GasMode::GReuse, owner("A9.1 HIQ-06 (icp_feed_gas_baseline G-REUSE)")),
        configuration: Configuration::CapOff,
        coupling_mode: CouplingMode::Absorbed,
        h1_point_id: None,
        f_rf_hz: Some(Registered::new(F_RF_REGISTERED_HZ, owner("VI-RF-01; A9 decision 1 (13.56 MHz)"))),
        rf_input: None,
        coupling_evidence: None,
        geometry: None,
        electrodes: None,
        neutral_source: None,
        feed: None,
        background: None,
        thermal_boundary: None,
        b_icp_max_t: None,
        chemistry,
        h_model: None,
        wall_recombination: BTreeMap::new(),
        dispositions: BTreeMap::new(),
        dedicated_flow_kg_s: None,
        bus: None,
        hall_demand: None,
    }
}

/// A SYNTHETIC_TEST_ONLY set whose reactions are registered channels of the EM-N2 set (rates through the IF-CHEM-REG-v1
/// representation and abep_chem::checked, EQ-06); the species selection and the process-class exclusions are synthetic.
/// It exercises the direct-rate path inside a solve; its outputs carry the SYNTHETIC_TEST_ONLY label like every other
/// testkit case (FC-15), so no number from it is evidence.
pub fn n2_registered_rate_set(m: &crate::IcpModel, channels: &[&str], species: &[&str]) -> ChemistrySet {
    let n2 = &m.n2_set;
    let reactions: Vec<ReactionDef> = channels
        .iter()
        .map(|id| n2.reactions.iter().find(|r| r.id == *id).unwrap_or_else(|| panic!("{id} not in EM-N2")).clone())
        .collect();
    let species: Vec<SpeciesDef> = species
        .iter()
        .map(|s| n2.species.iter().find(|x| x.name == *s).unwrap_or_else(|| panic!("{s} not in EM-N2")).clone())
        .map(|mut s| {
            s.recombines_to = None;
            s
        })
        .collect();
    let names: Vec<&str> = species.iter().map(|s| s.name.as_str()).collect();
    ChemistrySet {
        set_id: "SYNTHETIC_SET_OF_REGISTERED_N2_CHANNELS".into(),
        process_classes: excluded_all(&names),
        species,
        reactions,
        t_e_domain_ev: n2.t_e_domain_ev,
        vibrot_t_e_min_ev: n2.vibrot_t_e_min_ev,
    }
}
