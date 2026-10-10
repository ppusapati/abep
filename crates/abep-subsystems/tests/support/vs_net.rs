//! VS-NET v1: the synthetic full-topology verification network of NP-THERMAL-CATHODELESS (prereg
//! `analytic_limiting_cases.vs_net`). Every registered node id (11 REQUIRED, 6 CONDITIONAL) plus one massless series
//! junction, every link type and shape, two enclosures, every boundary (B_SC as SCI-A, SCI-B and SCI-C; B_PPU_RF;
//! B_FEED; SPACE; ENV; B_FACILITY) and both interfaces. All values are SYNTHETIC_TEST_DATA_NOT_EVIDENCE: verification
//! inputs, never physical values. The committed file `verification/vs_net_v1.json` is this builder's output and is
//! sha256-registered before the first scored run.

use super::*;
use abep_subsystems::thermal::case::*;
use serde_json::json;

pub const VS_NET_REL_PATH: &str = "docs/rust_migration/new_physics/NP-THERMAL-CATHODELESS/verification/vs_net_v1.json";
pub const CASE_ID: &str = "VS-NET-v1";
const PREREG_SHA: &str = "e3e6859cf61703c27254e9c231ff4637f7d20ea743c8d881b9e55c8ba9d27c5c";

fn vr(value: Value, units: &str) -> ValueRecord {
    ValueRecord {
        value: Some(value),
        units: Some(units.into()),
        status: Some("EVALUATED".into()),
        evidence_class: Some(SYN.into()),
        source: Some(SYN_SOURCE.into()),
        uncertainty: Some(json!("none: synthetic verification input")),
        applicability_domain: Some(json!("synthetic verification domain")),
        validation_status: Some("NOT_APPLICABLE_SYNTHETIC".into()),
        hall_map: None,
    }
}

fn biot(cb: &mut Cb, id: &str, volume: f64, area: f64, k: f64) -> BiotGeometry {
    BiotGeometry {
        volume_record_id: cb.num(&format!("{id}.V"), "volume", volume),
        conduction_area_record_id: cb.num(&format!("{id}.As"), "area", area),
        k_record_id: cb.konst(&format!("{id}.kbiot"), "thermal_conductivity", k, (1.0, 3000.0)),
    }
}

const RANGE: (f64, f64) = (1.0, 3000.0);

/// (id, mass kg, c_p form, receives)
fn hall_and_icp_nodes() -> Vec<(&'static str, f64, Value, &'static [&'static str])> {
    let c = |v: f64| json!({"form": "CONSTANT", "value": v});
    let poly = |t0: f64, a: f64, b: f64| json!({"form": "POLYNOMIAL", "T0_K": t0, "coefficients": [a, b]});
    let table = json!({"form": "PIECEWISE_LINEAR", "T_K": [1.0, 300.0, 1000.0, 3000.0], "values": [300.0, 480.0, 560.0, 600.0]});
    vec![
        ("H1_ANODE", 0.20, table.clone(), &["Q_hall_anode_W", "Q_hall_plasma_radiation_W"]),
        ("H1_WALL_IN", 0.15, poly(300.0, 800.0, 0.2), &["Q_hall_wall_inner_W", "Q_hall_plasma_radiation_W"]),
        ("H1_WALL_OUT", 0.25, poly(300.0, 800.0, 0.2), &["Q_hall_wall_outer_W", "Q_hall_plasma_radiation_W"]),
        ("H1_POLE_IN", 0.40, c(450.0), &["Q_hall_pole_W", "Q_hall_plasma_radiation_W", "Q_icp_radiation_W"]),
        ("H1_POLE_OUT", 0.60, c(450.0), &["Q_hall_pole_W", "Q_hall_plasma_radiation_W", "Q_icp_radiation_W"]),
        ("H1_BACKPLATE", 0.80, c(450.0), &[]),
        ("H1_COIL_IN", 0.10, c(390.0), &["Q_hall_coil_inner_W"]),
        ("H1_COIL_OUT", 0.20, c(390.0), &["Q_hall_coil_outer_W"]),
        ("H1_COIL_TRIM", 0.05, c(390.0), &["Q_hall_coil_trim_W"]),
        (
            "N_VESSEL",
            0.10,
            c(750.0),
            &["Q_icp_plasma_wall_W", "Q_icp_radiation_W", "Q_hall_plume_to_icp_W", "Q_hall_plasma_radiation_W"],
        ),
        ("N_ANTENNA", 0.05, table, &["Q_icp_coil_ohmic_W", "Q_icp_plasma_wall_W", "Q_icp_radiation_W"]),
        (
            "N_COLLECTOR",
            0.08,
            c(500.0),
            &[
                "Q_icp_plasma_wall_W",
                "Q_icp_coil_ohmic_W",
                "Q_icp_radiation_W",
                "Q_hall_return_to_icp_W",
                "Q_hall_plume_to_icp_W",
                "Q_hall_plasma_radiation_W",
            ],
        ),
        (
            "N_HOUSING",
            0.30,
            c(900.0),
            &[
                "Q_icp_coil_ohmic_W",
                "Q_icp_plasma_wall_W",
                "Q_icp_radiation_W",
                "Q_hall_plume_to_icp_W",
                "Q_hall_plasma_radiation_W",
            ],
        ),
        ("N_MATCH", 0.10, c(700.0), &["Q_icp_match_W"]),
        ("N_MOUNT", 0.30, c(900.0), &["Q_hall_plume_to_icp_W"]),
        ("R_HALL", 5.0, c(900.0), &[]),
        ("R_ICP", 0.30, c(900.0), &[]),
    ]
}

/// Surfaces: (node, surface id, area m^2, eps, alpha, enclosure, external).
const SURFACES: [(&str, &str, f64, f64, Option<f64>, &str, bool); 17] = [
    ("H1_ANODE", "S_AN", 0.010, 0.30, None, "E_INT", true),
    ("H1_WALL_IN", "S_WI", 0.012, 0.80, None, "E_INT", true),
    ("H1_WALL_OUT", "S_WO", 0.016, 0.80, None, "E_INT", true),
    ("H1_POLE_IN", "S_PI_F", 0.004, 0.20, None, "E_INT", true),
    ("H1_POLE_OUT", "S_PO_F", 0.008, 0.20, None, "E_INT", true),
    ("N_VESSEL", "S_VE_IN", 0.006, 0.70, None, "E_INT", true),
    ("N_ANTENNA", "S_ANT", 0.003, 0.10, None, "E_INT", true),
    ("N_COLLECTOR", "S_COL", 0.004, 0.40, None, "E_INT", true),
    ("N_HOUSING", "S_HO_IN", 0.010, 0.50, None, "E_INT", true),
    ("H1_POLE_OUT", "S_PO_X", 0.030, 0.30, Some(0.40), "E_EXT", true),
    ("H1_BACKPLATE", "S_BP", 0.020, 0.60, Some(0.50), "E_EXT", true),
    ("N_VESSEL", "S_VE_X", 0.005, 0.70, None, "E_EXT", true),
    ("N_HOUSING", "S_HO_X", 0.020, 0.85, Some(0.30), "E_EXT", true),
    ("N_MOUNT", "S_MO", 0.010, 0.50, None, "E_EXT", true),
    ("R_HALL", "S_RH", 0.150, 0.85, Some(0.20), "E_EXT", true),
    ("R_ICP", "S_RI", 0.080, 0.85, Some(0.20), "E_EXT", true),
    ("H1_COIL_OUT", "S_CO", 0.004, 0.40, None, "E_EXT", true),
];

/// Build VS-NET (steady, AIR_PRIMARY, nominal synthetic loads, every sink and boundary at 250 K, T_init 300 K).
pub fn build() -> ThermalCase {
    let mut cb = Cb::new(CASE_ID, "SYNTHETIC_VERIFICATION", "NP_THERMAL_NETWORK", "AIR_PRIMARY");
    cb.c.match_colocated = Some(true);
    cb.c.magnet_load_mode = Some("FIXED_POWER".into());
    for (id, mass, cp, receives) in hall_and_icp_nodes() {
        let reg = abep_subsystems::thermal::vocab::registered_node(id).expect("registered");
        let m = cb.num(&format!("{id}.mass"), "mass", mass);
        let cpr = cb.record(&format!("{id}.cp"), "specific_heat", cp, Some(RANGE));
        let bg = biot(&mut cb, id, 1e-5, 2e-3, 20.0);
        cb.c.nodes.push(NodeRecord {
            id: id.into(),
            group: reg.group.into(),
            represents: "VS-NET synthetic node".into(),
            presence: if reg.required { "REQUIRED".into() } else { "CONDITIONAL".into() },
            role: "REGISTERED".into(),
            refines: None,
            thermal_mass: "LUMPED_C_OF_T".into(),
            parts: vec![Part { part_id: format!("{id}.part"), material_record_id: cpr, mass_kg_record_id: m }],
            surfaces: vec![],
            biot_geometry: Some(bg),
            receives_interface_keys: receives.iter().map(|s| s.to_string()).collect(),
            case_classes_allowed: vec![
                "SYNTHETIC_VERIFICATION".into(),
                "PARAMETRIC".into(),
                "BENCH_REPLICA".into(),
                "FLIGHT_CONDITIONAL".into(),
            ],
        });
        cb.c.solver.t_init_k.insert(id.into(), 300.0);
    }
    cb.c.nodes.push(NodeRecord {
        id: "J_ISO".into(),
        group: "HALL_BODY".into(),
        represents: "massless series junction of the anode isolator stack (E-04)".into(),
        presence: "CONDITIONAL".into(),
        role: "MASSLESS_SERIES_JUNCTION".into(),
        refines: None,
        thermal_mass: "MASSLESS_SERIES".into(),
        parts: vec![],
        surfaces: vec![],
        biot_geometry: None,
        receives_interface_keys: vec![],
        case_classes_allowed: vec![
            "SYNTHETIC_VERIFICATION".into(),
            "PARAMETRIC".into(),
            "BENCH_REPLICA".into(),
            "FLIGHT_CONDITIONAL".into(),
        ],
    });
    cb.c.solver.t_init_k.insert("J_ISO".into(), 300.0);

    for (node, sid, area, eps, alpha, encl, external) in SURFACES {
        let a = cb.num(&format!("{sid}.area"), "area", area);
        let e = cb.konst(&format!("{sid}.eps"), "emittance_IR", eps, RANGE);
        let al = alpha.map(|x| cb.konst(&format!("{sid}.alpha"), "absorptance_solar", x, RANGE));
        cb.node_mut(node).surfaces.push(Surface {
            surface_id: sid.into(),
            area_record_id: a,
            eps_ir_record_id: e,
            alpha_solar_record_id: al,
            enclosure_id: encl.into(),
            external,
        });
    }
    let members = |encl: &str| -> Vec<(&'static str, f64, bool)> {
        SURFACES.iter().filter(|s| s.5 == encl).map(|s| (s.1, s.2, false)).collect()
    };
    let mut int = members("E_INT");
    int.push(("FACILITY_INT", 0.02, true));
    cb.enclosure("E_INT", sphere_vf(&int), &[("FACILITY_INT", "B_FACILITY", 250.0)], &[]);
    let mut ext = members("E_EXT");
    ext.push(("HOST_PANEL", 0.10, false));
    ext.push(("SPACE_EXT", 1.0, true));
    cb.enclosure("E_EXT", sphere_vf(&ext), &[("SPACE_EXT", "SPACE", 250.0)], &[("HOST_PANEL", 0.10, 0.80, 250.0)]);

    let t_sc = cb.temperature("T_SC", 250.0);
    let t_feed = cb.temperature("T_FEED", 250.0);
    let t_ppu = cb.temperature("T_PPU", 250.0);
    let contact = |cb: &mut Cb, id: &str, a: &str, b: &str, h: f64, ac: f64| {
        let hr = cb.ranged(&format!("{id}.hc"), "contact_conductance_coefficient", h);
        let ar = cb.num(&format!("{id}.Ac"), "area", ac);
        cb.c.links.push(LinkRecord {
            id: id.into(),
            link_type: "CONTACT".into(),
            a: node_ep(a),
            b: node_ep(b),
            k_record_id: None,
            shape: None,
            h_c_record_id: Some(hr),
            contact_area_record_id: Some(ar),
            g_record_id: None,
        });
    };
    let conduction = |cb: &mut Cb, id: &str, a: &str, b: &str, k: Value, shape: ShapeSpec| {
        let kr = cb.record(&format!("{id}.k"), "thermal_conductivity", k, Some(RANGE));
        cb.c.links.push(LinkRecord {
            id: id.into(),
            link_type: "CONDUCTION".into(),
            a: node_ep(a),
            b: node_ep(b),
            k_record_id: Some(kr),
            shape: Some(shape),
            h_c_record_id: None,
            contact_area_record_id: None,
            g_record_id: None,
        });
    };
    contact(&mut cb, "L_AN_ISO", "H1_ANODE", "J_ISO", 2000.0, 5e-4);
    cb.lumped_g("L_ISO_BP", node_ep("J_ISO"), node_ep("H1_BACKPLATE"), 0.8);
    let slab = ShapeSpec {
        kind: "SLAB".into(),
        area_record_id: Some(cb.num("L_WI_PI.A", "area", 2e-4)),
        length_record_id: Some(cb.num("L_WI_PI.L", "length", 0.01)),
        r_outer_record_id: None,
        r_inner_record_id: None,
        s_record_id: None,
    };
    conduction(
        &mut cb,
        "L_WI_PI",
        "H1_WALL_IN",
        "H1_POLE_IN",
        json!({"form": "PIECEWISE_LINEAR", "T_K": [1.0, 400.0, 1200.0, 3000.0], "values": [40.0, 30.0, 20.0, 18.0]}),
        slab,
    );
    let cyl = ShapeSpec {
        kind: "CYLINDRICAL_SHELL".into(),
        area_record_id: None,
        length_record_id: Some(cb.num("L_WO_PO.L", "length", 0.02)),
        r_outer_record_id: Some(cb.num("L_WO_PO.ro", "length", 0.05)),
        r_inner_record_id: Some(cb.num("L_WO_PO.ri", "length", 0.045)),
        s_record_id: None,
    };
    conduction(
        &mut cb,
        "L_WO_PO",
        "H1_WALL_OUT",
        "H1_POLE_OUT",
        json!({"form": "POLYNOMIAL", "T0_K": 300.0, "coefficients": [2.0, 0.0005]}),
        cyl,
    );
    let sf = ShapeSpec {
        kind: "SHAPE_FACTOR".into(),
        area_record_id: None,
        length_record_id: None,
        r_outer_record_id: None,
        r_inner_record_id: None,
        s_record_id: Some(cb.num("L_PI_BP.S", "shape_factor", 0.02)),
    };
    conduction(&mut cb, "L_PI_BP", "H1_POLE_IN", "H1_BACKPLATE", json!({"form": "CONSTANT", "value": 60.0}), sf);
    cb.lumped_g("L_PO_BP", node_ep("H1_POLE_OUT"), node_ep("H1_BACKPLATE"), 1.5);
    contact(&mut cb, "L_CI_PI", "H1_COIL_IN", "H1_POLE_IN", 800.0, 1e-3);
    contact(&mut cb, "L_CO_PO", "H1_COIL_OUT", "H1_POLE_OUT", 800.0, 1.5e-3);
    cb.lumped_g("L_CT_PO", node_ep("H1_COIL_TRIM"), node_ep("H1_POLE_OUT"), 0.4);
    cb.lumped_g("L_BP_RH", node_ep("H1_BACKPLATE"), node_ep("R_HALL"), 0.2);
    cb.lumped_g("L_BP_SC", node_ep("H1_BACKPLATE"), boundary_ep("B_SC", &t_sc), 0.3);
    cb.lumped_g("L_BP_FEED", node_ep("H1_BACKPLATE"), boundary_ep("B_FEED", &t_feed), 0.05);
    contact(&mut cb, "L_VE_HO", "N_VESSEL", "N_HOUSING", 500.0, 1e-3);
    cb.lumped_g("L_ANT_HO", node_ep("N_ANTENNA"), node_ep("N_HOUSING"), 0.3);
    cb.lumped_g("L_ANT_PPU", node_ep("N_ANTENNA"), boundary_ep("B_PPU_RF", &t_ppu), 0.05);
    cb.lumped_g("L_COL_HO", node_ep("N_COLLECTOR"), node_ep("N_HOUSING"), 0.4);
    let slab2 = ShapeSpec {
        kind: "SLAB".into(),
        area_record_id: Some(cb.num("L_HO_MO.A", "area", 1e-4)),
        length_record_id: Some(cb.num("L_HO_MO.L", "length", 0.02)),
        r_outer_record_id: None,
        r_inner_record_id: None,
        s_record_id: None,
    };
    conduction(&mut cb, "L_HO_MO", "N_HOUSING", "N_MOUNT", json!({"form": "CONSTANT", "value": 150.0}), slab2);
    cb.lumped_g("L_MA_MO", node_ep("N_MATCH"), node_ep("N_MOUNT"), 0.5);
    cb.lumped_g("L_MO_BP", node_ep("N_MOUNT"), node_ep("H1_BACKPLATE"), 0.2);
    cb.lumped_g("L_HO_RI", node_ep("N_HOUSING"), node_ep("R_ICP"), 1.0);
    cb.lumped_g("L_VE_FEED", node_ep("N_VESSEL"), boundary_ep("B_FEED", &t_feed), 0.02);
    cb.lumped_g("L_MO_SC", node_ep("N_MOUNT"), boundary_ep("B_SC", &t_sc), 0.1);

    let q = cb.num("F_SC_RI.q", "power", 1.5);
    cb.c.boundary_fluxes.push(BoundaryFlux {
        id: "F_SC_RI".into(),
        boundary: "B_SC".into(),
        node: "R_ICP".into(),
        q_record_id: q,
    });

    let s = cb.num("ENV.S", "solar_flux", 1300.0);
    let one = cb.num("ENV.one", "view_factor_env", 1.0);
    let half = cb.num("ENV.half", "view_factor_env", 0.5);
    let nu = cb.num("ENV.nu", "illumination", 1.0);
    let alb = cb.num("ENV.albedo", "albedo", 0.3);
    let olr = cb.num("ENV.olr", "olr_flux", 230.0);
    let rho = cb.num("ENV.rho", "density", 4e-10);
    let v = cb.num("ENV.V", "velocity", 7800.0);
    let ae = cb.num("ENV.alphaE", "energy_accommodation", 1.0);
    for (sid, aram, fsun) in [
        ("S_RH", 0.0, &one),
        ("S_RI", 0.0, &half),
        ("S_HO_X", 0.002, &half),
        ("S_BP", 0.0, &half),
        ("S_PO_X", 0.004, &one),
    ] {
        let ar = cb.num(&format!("{sid}.Aram"), "projected_area", aram);
        cb.c.environment.push(EnvSurface {
            surface_id: sid.into(),
            solar_flux_record_id: s.clone(),
            f_sun_record_id: fsun.clone(),
            illumination_record_id: nu.clone(),
            albedo_record_id: alb.clone(),
            f_alb_record_id: half.clone(),
            olr_flux_record_id: olr.clone(),
            f_earth_record_id: half.clone(),
            rho_record_id: rho.clone(),
            v_rel_record_id: v.clone(),
            alpha_e_record_id: ae.clone(),
            a_ram_record_id: ar,
        });
    }
    cb.tc("R_ICP", 2.0);
    cb.tc("N_HOUSING", 1.0);

    let pole = cb.record("PART.pole", "partition", json!({"weights": {"H1_POLE_IN": 0.4, "H1_POLE_OUT": 0.6}}), None);
    let plume = cb.record(
        "PART.plume",
        "partition",
        json!({"weights": {"N_VESSEL": 0.3, "N_COLLECTOR": 0.3, "N_HOUSING": 0.2, "N_MOUNT": 0.2}}),
        None,
    );
    let ohmic = cb.record(
        "PART.ohmic",
        "partition",
        json!({"weights": {"N_ANTENNA": 0.7, "N_COLLECTOR": 0.2, "N_HOUSING": 0.1}}),
        None,
    );
    let rad = cb.record(
        "PART.icp_rad",
        "partition",
        json!({"weights": {"N_VESSEL": 0.3, "N_ANTENNA": 0.1, "N_COLLECTOR": 0.1, "N_HOUSING": 0.1, "H1_POLE_IN": 0.1, "H1_POLE_OUT": 0.1, "EXPORT": 0.2}}),
        None,
    );
    cb.c.partitions.insert("Q_hall_pole_W".into(), pole);
    cb.c.partitions.insert("Q_hall_plume_to_icp_W".into(), plume);
    cb.c.partitions.insert("Q_icp_coil_ohmic_W".into(), ohmic);
    cb.c.partitions.insert("Q_icp_radiation_W".into(), rad);

    let hall_keys: [(&str, f64, &str); 12] = [
        ("P_hall_discharge_W", 600.0, "W"),
        ("P_hall_jet_W", 300.0, "W"),
        ("Q_hall_anode_W", 60.0, "W"),
        ("Q_hall_wall_inner_W", 40.0, "W"),
        ("Q_hall_wall_outer_W", 50.0, "W"),
        ("Q_hall_pole_W", 10.0, "W"),
        ("Q_hall_plasma_radiation_W", 20.0, "W"),
        ("Q_hall_return_to_icp_W", 8.0, "W"),
        ("Q_hall_plume_to_icp_W", 5.0, "W"),
        ("Q_hall_coil_inner_W", 6.0, "W"),
        ("Q_hall_coil_outer_W", 9.0, "W"),
        ("Q_hall_coil_trim_W", 2.0, "W"),
    ];
    let icp_keys: [(&str, f64, &str); 7] = [
        ("Q_icp_plasma_wall_W", 12.0, "W"),
        ("Q_icp_coil_ohmic_W", 7.0, "W"),
        ("Q_icp_match_W", 3.0, "W"),
        ("Q_icp_extraction_W", 4.0, "W"),
        ("Q_icp_radiation_W", 2.0, "W"),
        ("P_icp_rf_forward_W", 40.0, "W"),
        ("P_icp_bus_W", 55.0, "W"),
    ];
    let mk = |id: &str,
              producer: &str,
              keys: &[(&str, f64, &str)],
              parts: BTreeMap<String, BTreeMap<String, f64>>,
              rf: Option<bool>| {
        InterfaceRecord {
            interface_id: id.into(),
            interface_version: "v1".into(),
            producer_id: producer.into(),
            producer_version: "synthetic-1".into(),
            producer_prereg_sha256: PREREG_SHA.into(),
            case_id: CASE_ID.into(),
            case_class: "SYNTHETIC_VERIFICATION".into(),
            supply_mode: "AIR_PRIMARY".into(),
            design_state_id: None,
            operating_point_id: "VS-NET-OP-1".into(),
            time_basis: TimeBasis { kind: "STEADY".into(), breakpoints_s: None },
            keys: keys.iter().map(|(k, v, u)| (k.to_string(), vr(json!(v), u))).collect(),
            partitions: parts,
            rf_powered_only: rf,
        }
    };
    let mut hall_parts = BTreeMap::new();
    hall_parts.insert(
        "Q_hall_plasma_radiation_W".to_string(),
        [
            ("H1_ANODE", 0.1),
            ("H1_WALL_IN", 0.2),
            ("H1_WALL_OUT", 0.2),
            ("H1_POLE_IN", 0.05),
            ("H1_POLE_OUT", 0.05),
            ("N_VESSEL", 0.05),
            ("N_COLLECTOR", 0.05),
            ("N_HOUSING", 0.05),
            ("EXPORT", 0.25),
        ]
        .iter()
        .map(|(k, w)| (k.to_string(), *w))
        .collect(),
    );
    let mut icp_parts = BTreeMap::new();
    icp_parts.insert(
        "Q_icp_plasma_wall_W".to_string(),
        [("N_VESSEL", 0.5), ("N_COLLECTOR", 0.3), ("N_ANTENNA", 0.1), ("N_HOUSING", 0.1)]
            .iter()
            .map(|(k, w)| (k.to_string(), *w))
            .collect(),
    );
    cb.c.interfaces.hall = Some(mk("IF-HALL-THERMAL-v1", "SYNTHETIC_HALL_PRODUCER", &hall_keys, hall_parts, None));
    cb.c.interfaces.icp = Some(mk("IF-ICP-THERMAL-v1", "SYNTHETIC_ICP_PRODUCER", &icp_keys, icp_parts, Some(true)));
    cb.c
}

/// The committed VS-NET bytes (pretty JSON + newline).
pub fn to_bytes(c: &ThermalCase) -> Vec<u8> {
    let mut s = serde_json::to_string_pretty(c).expect("serializable");
    s.push('\n');
    s.into_bytes()
}

pub fn load_registered() -> ThermalCase {
    let root = abep_provenance::workspace_repo_root().expect("repo root");
    let bytes = std::fs::read(root.join(VS_NET_REL_PATH)).expect("VS-NET file");
    serde_json::from_slice(&bytes).expect("VS-NET parses")
}

/// Set every interface key and Q_thermal_control_W, SCI-B flux and environment flux to zero (AL-05).
pub fn zero_loads(c: &mut ThermalCase) {
    for rec in [&mut c.interfaces.hall, &mut c.interfaces.icp].into_iter().flatten() {
        for v in rec.keys.values_mut() {
            v.value = Some(json!(0.0));
        }
        rec.supply_mode = "NON_FIRING".into();
    }
    c.supply_mode = "NON_FIRING".into();
    let zero = ["F_SC_RI.q", "R_ICP.Qtc", "N_HOUSING.Qtc", "ENV.S", "ENV.olr", "ENV.rho"];
    for r in c.records.iter_mut() {
        if r.id.as_deref().is_some_and(|id| zero.contains(&id)) {
            r.value = Some(json!(0.0));
        }
    }
}

/// Set every sink, host and boundary temperature to `t` (AL-05, AL-06).
pub fn set_sinks(c: &mut ThermalCase, t: f64) {
    let ids = ["FACILITY_INT.T", "SPACE_EXT.T", "HOST_PANEL.T", "T_SC", "T_FEED", "T_PPU"];
    for r in c.records.iter_mut() {
        if r.id.as_deref().is_some_and(|id| ids.contains(&id)) {
            r.value = Some(json!(t));
        }
    }
}

pub fn set_case_id(c: &mut ThermalCase, id: &str) {
    c.case_id = id.into();
    for rec in [&mut c.interfaces.hall, &mut c.interfaces.icp].into_iter().flatten() {
        rec.case_id = id.into();
    }
}

pub fn set_class(c: &mut ThermalCase, class: &str) {
    c.case_class = class.into();
    for rec in [&mut c.interfaces.hall, &mut c.interfaces.icp].into_iter().flatten() {
        rec.case_class = class.into();
    }
}

pub fn set_all_t_init(c: &mut ThermalCase, t: f64) {
    for v in c.solver.t_init_k.values_mut() {
        *v = t;
    }
}
