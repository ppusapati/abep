//! model_version 2 analytic limiting cases LC-12..LC-17, LC-19 and LC-20 (prereg v2 `added_items`; LC-18 is the
//! consumer-side test of the power lane in abep-subsystems). Every case is SYNTHETIC_TEST_ONLY.

mod common;

use abep_icp::chemistry::{ChemistrySet, RateSource, ReactionDef, ReactionKind, SpeciesDef};
use abep_icp::chemistry::{SyntheticRate, Validity};
use abep_icp::constants::{EPS0, E_CHARGE, K_B, M_E, NUMERICS};
use abep_icp::geometry::{HModel, Orientation, SurfaceKind, ThermalNode};
use abep_icp::physics;
use abep_icp::result::OutputValue;
use abep_icp::solver::{self, PreparedCase, PreparedH, PreparedNeutrals, PreparedSurface, Recombination, SolveOutcome};
use abep_icp::testkit::{excluded_all, with_double_ion, x_rate, x_set, L_M, R_M};
use abep_icp::v2::case::*;
use abep_icp::v2::evaluate::sg01_closed_form;
use abep_icp::v2::formation::formation_table;
use abep_icp::v2::testkit::*;
use abep_icp::v2::{diagnostics, IcpModelV2, IcpResultV2};
use abep_icp::IcpStatus;
use common::{model_v2, rel};
use std::collections::BTreeMap;
use std::f64::consts::PI;

const C: IcpStatus = IcpStatus::Converged;

fn scalar(r: &IcpResultV2, member: usize, k: &str) -> f64 {
    match &r.solve_members[member].outputs[k] {
        OutputValue::Scalar(q) => {
            assert_eq!(q.status, C, "{k}: {q:?}");
            q.value.unwrap_or_else(|| panic!("{k} null"))
        }
        o => panic!("{k}: not a scalar {o:?}"),
    }
}

fn map(r: &IcpResultV2, member: usize, k: &str) -> BTreeMap<String, f64> {
    match &r.solve_members[member].outputs[k] {
        OutputValue::Map(m) => m.iter().map(|(s, q)| (s.clone(), q.value.expect("value"))).collect(),
        o => panic!("{k}: not a map {o:?}"),
    }
}

fn closure(r: &IcpResultV2, member: usize, id: &str) -> (IcpStatus, Option<f64>) {
    let m = &r.if_icp_thermal_v2.members[member];
    let c =
        m.closures.iter().find(|c| c.id == id).unwrap_or_else(|| panic!("{id} missing in {}", m.scenario_member_id));
    (c.status, c.value)
}

fn conservation(r: &IcpResultV2, member: usize, id: &str) -> (IcpStatus, f64) {
    let c = r.solve_members[member].conservation.iter().find(|c| c.id == id).unwrap_or_else(|| panic!("{id}"));
    (c.status, c.value.expect("value"))
}

fn vbar(t_k: f64, m: f64) -> f64 {
    (8.0 * K_B * t_k / (PI * m)).sqrt()
}

// ------------------------------------------------------------------------------------------------------- LC-12

#[test]
fn lc12_background_equilibrium_carries_tau_and_flags_non_isothermal_passage() {
    let m = model_v2();
    let n_b = 1e19;
    for tau in [1.0, 0.5, 0.1] {
        let r = m.evaluate(&flow_case_v2(0.0, InflowV2::NoInflow, tau, n_b, 300.0, 300.0));
        assert_eq!(r.status, C, "{:?}", r.reasons);
        let n = map(&r, 0, "n_g_m3")["X"];
        assert!(rel(n, n_b) <= 1e-12, "tau {tau}: n {n} vs n_b {n_b}");
        assert!(!r.flags.contains("NON_ISOTHERMAL_PASSAGE"));
        // T_b != T_g: n = n_b vbar_b / vbar (PF-02 detailed balance through the same tau_j).
        let r = m.evaluate(&flow_case_v2(0.0, InflowV2::NoInflow, tau, n_b, 600.0, 300.0));
        assert_eq!(r.status, C, "{:?}", r.reasons);
        let want = n_b * vbar(600.0, abep_icp::testkit::M_X_KG) / vbar(300.0, abep_icp::testkit::M_X_KG);
        let n = map(&r, 0, "n_g_m3")["X"];
        assert!(rel(n, want) <= 1e-12, "tau {tau}: n {n} vs {want}");
        assert!(r.flags.contains("NON_ISOTHERMAL_PASSAGE"));
        assert!(r.verify_items_on_path.contains("VER-20"));
    }
}

// ------------------------------------------------------------------------------------------------------- LC-13

/// A closed vessel (one radial wall, no open end) holding the synthetic X2 / X set in FLOW_BALANCE.
fn closed_vessel(gamma: f64, s_atoms: f64) -> (PreparedCase, f64) {
    let set = x2_set();
    let area = 2.0 * PI * R_M * L_M;
    let ia = set.species_index("X").unwrap();
    let im = set.species_index("X2").unwrap();
    let mut inflow = vec![0.0; set.species.len()];
    inflow[ia] = s_atoms;
    let c = PreparedCase {
        direct: vec![None; set.reactions.len()],
        recombination: vec![Recombination { atom: ia, molecule: im, gamma_area_m2: gamma * area }],
        set,
        volume_m3: PI * R_M * R_M * L_M,
        radius_m: R_M,
        length_m: L_M,
        surfaces: vec![PreparedSurface {
            id: "wall".into(),
            kind: SurfaceKind::DielectricFloating,
            area_m2: area,
            orientation: Orientation::Radial,
            node: ThermalNode::NVessel,
            potential_v: None,
            tau: None,
        }],
        h: PreparedH::Explicit(vec![0.5]),
        neutrals: PreparedNeutrals::Flow { inflow_per_s: inflow },
        t_g_k: 300.0,
        p_abs_w: 0.0,
    };
    (c, area)
}

#[test]
fn lc13_fc17_per_collision_recombination_sink_and_half_molecule_source() {
    let s = 1e17;
    for gamma in [1e-3, 0.1, 1.0] {
        let (c, area) = closed_vessel(gamma, s);
        let k = vec![0.0; c.set.reactions.len()];
        let (a, b, unknown) = solver::balance_rows(&c, 1.0, 0.0, &k, &[0.5], &[true]);
        let ia = c.set.species_index("X").unwrap();
        let im = c.set.species_index("X2").unwrap();
        let ra = unknown.iter().position(|&u| u == ia).unwrap();
        let rm = unknown.iter().position(|&u| u == im).unwrap();
        // At n_e = 0 the ion rows have no source (n_ion = 0); among the neutrals the atom row depends on n_X only
        // (closed vessel), so n_X = b / a. Its ion columns are the wall return X+ -> X, multiplied by n_ion = 0.
        for (row, &u) in unknown.iter().enumerate() {
            if c.set.species[u].charge > 0 {
                assert_eq!(b[row], 0.0, "ion row {u} has a source at n_e = 0");
            }
        }
        for (col, v) in a[ra].iter().enumerate() {
            if col != ra && c.set.species[unknown[col]].charge == 0 {
                assert_eq!(*v, 0.0, "atom row couples to neutral column {col}");
            }
        }
        let n_a = b[ra] / a[ra][ra];
        let vbar_a = vbar(300.0, c.set.species[ia].mass_kg);
        let want = s / (gamma * 0.25 * vbar_a * area);
        assert!(rel(n_a, want) <= 1e-12, "gamma {gamma}: n_a {n_a} vs {want}");
        // Molecule source = S / 2 (half a molecule per atom lost; nuclei-exact).
        let src = a[rm][ra] * n_a;
        assert!(rel(src, 0.5 * s) <= 1e-12, "gamma {gamma}: molecule source {src}");
        // FC-17: at gamma = 1 the atom loss is (1/4) n vbar A, not half of it (no gamma / 2 factor).
        let loss = -a[ra][ra] * n_a;
        if gamma == 1.0 {
            assert!(rel(loss, 0.25 * n_a * vbar_a * area) <= 1e-12);
        }
        assert!(rel(loss, s) <= 1e-12);
    }
}

/// FLOW_BALANCE X2 case through one open end (registered tau), dedicated feed of X2, no background.
fn x2_flow_case(materials: (&str, &str)) -> IcpCaseV2 {
    let mut surfaces = two_end_surfaces(Some((0.0, 0.4)));
    surfaces.remove(2); // drop the upstream open end
    surfaces[0].material = materials.0.into();
    surfaces[1].material = materials.1.into();
    let mut c = case_v2("SYN_X2_FLOW_V2", x2_set(), surfaces, &[], 15.0);
    c.neutral_source = Some(NeutralSourceV2::FlowBalance {
        t_g_k: syn(300.0, "T_g"),
        sigma_c_m2: [("X2".to_string(), syn(4e-19, "sigma_c")), ("X".to_string(), syn(3e-19, "sigma_c"))].into(),
        inflow: InflowV2::MeasuredDedicatedFeed { mdot_kg_s: syn([("X2".to_string(), 2e-8)].into(), "mdot") },
        f_in: None,
    });
    c.background = Some(syn(BackgroundV2::IsotropicMaxwellian { n_b_m3: BTreeMap::new(), t_b_k: 300.0 }, "background"));
    c.dissociation_energies_ev = [("X2".to_string(), syn(D0_X2_EV, "D0(X2)"))].into();
    c
}

#[test]
fn lc13_fc17_flow_balance_evaluates_every_gamma_vertex_member_with_closed_balances() {
    let m = model_v2();
    for (mats, n_members) in [(("SYN_A", "SYN_A"), 2), (("SYN_A", "SYN_B"), 4)] {
        let r = m.evaluate(&x2_flow_case(mats));
        assert_eq!(r.solve_members.len(), n_members, "{:?}", r.reasons);
        let mut gammas = Vec::new();
        for (i, sm) in r.solve_members.iter().enumerate() {
            assert_eq!(sm.status, C, "{}: {:?}", sm.solve_member_id, sm.reasons);
            for id in ["CC-01", "CC-02", "CC-03"] {
                let (st, v) = conservation(&r, i, id);
                assert!(st == C && v <= 1e-10, "{} {id}: {v}", sm.solve_member_id);
            }
            gammas.push(sm.gamma.clone());
        }
        // The unsourced gamma of each (atom, material) takes both vertices {0, 1}; no member is nominal.
        for g in &gammas {
            assert!(g.values().all(|v| *v == 0.0 || *v == 1.0));
        }
        assert!(gammas.iter().any(|g| g.values().all(|v| *v == 0.0)));
        assert!(gammas.iter().any(|g| g.values().all(|v| *v == 1.0)));
        // gamma = 1 lowers the atom density (the sink acts).
        let n_x = |i: usize| map(&r, i, "n_g_m3")["X"];
        let i0 = gammas.iter().position(|g| g.values().all(|v| *v == 0.0)).unwrap();
        let i1 = gammas.iter().position(|g| g.values().all(|v| *v == 1.0)).unwrap();
        assert!(n_x(i1) < n_x(i0));
        assert!(r.flags.contains("UNIFORM_DENSITY_WALL_FLUX_AT_GAMMA"));
    }
}

// ------------------------------------------------------------------------------------------------------- LC-14

fn lieberman_case(set: ChemistrySet, sigma: &[(&str, f64)]) -> IcpCaseV2 {
    let mut c = case_v2("SYN_LIEB_V2", set, floating_surfaces_v2(), &[], 20.0);
    c.h_model = Some(HModel::Lieberman {
        sigma_i_m2: sigma.iter().map(|(k, v)| (k.to_string(), syn(*v, "sigma_i"))).collect(),
    });
    c
}

#[test]
fn lc14_one_ion_species_h_lieb_is_bit_identical_to_v1() {
    let m = model_v2();
    let r2 = m.evaluate(&lieberman_case(x_set(x_rate()), &[("X+", 1e-18)]));
    assert_eq!(r2.status, C, "{:?}", r2.reasons);
    // One ion species: H-MS, H-LO and H-HI coincide with H-LIEB; the evaluator emits that one member.
    assert_eq!(r2.solve_members.len(), 1);
    assert_eq!(r2.solve_members[0].h_member, "H-LIEB");
    let mut c1 = abep_icp::testkit::floating_case(20.0);
    c1.h_model = Some(HModel::Lieberman { sigma_i_m2: [("X+".to_string(), syn(1e-18, "sigma_i"))].into() });
    let r1 = m.v1.evaluate(&c1);
    assert!(r1.status.is_converged(), "{:?}", r1.reasons);
    for k in ["T_e_eV", "n_e_m3", "I_production_A"] {
        let v1 = r1.scalar(k).value.unwrap();
        let v2 = scalar(&r2, 0, k);
        assert_eq!(v1.to_bits(), v2.to_bits(), "{k}: v1 {v1} v2 {v2}");
    }
}

/// The prepared X / X+ / X++ case of the multi-ion members (REGISTERED_PRESSURE, all-floating tube).
fn multi_ion_prepared(h: PreparedH) -> PreparedCase {
    let set = with_double_ion(x_set(x_rate()));
    let n_g = 1.0 / (K_B * 300.0);
    let surfaces = floating_surfaces_v2()
        .iter()
        .map(|s| PreparedSurface {
            id: s.id.clone(),
            kind: s.kind,
            area_m2: s.area_m2,
            orientation: s.orientation,
            node: s.thermal_node,
            potential_v: None,
            tau: None,
        })
        .collect();
    PreparedCase {
        direct: vec![None; set.reactions.len()],
        recombination: vec![],
        neutrals: PreparedNeutrals::Fixed(set.species.iter().map(|s| if s.charge == 0 { n_g } else { 0.0 }).collect()),
        set,
        volume_m3: PI * R_M * R_M * L_M,
        radius_m: R_M,
        length_m: L_M,
        surfaces,
        h,
        t_g_k: 300.0,
        p_abs_w: 20.0,
    }
}

const SIG_1: f64 = 1e-18;
const SIG_2: f64 = 4e-19;

#[test]
fn lc14_two_ion_species_members_bound_and_edge_relation() {
    let p = multi_ion_prepared(PreparedH::LiebermanPerSpecies { sigma_by_species_m2: vec![0.0, SIG_1, SIG_2] });
    let Ok(SolveOutcome::Equilibria(eqs)) = solver::solve(&p, &NUMERICS) else { panic!("H-MS solve") };
    assert_eq!(eqs.len(), 1);
    let e = &eqs[0];
    let hs = e.kin.h_species.as_ref().expect("H-MS edge factors");
    let n_g = 1.0 / (K_B * 300.0);
    let (lmin, lmax) = (1.0 / (n_g * SIG_1), 1.0 / (n_g * SIG_2));
    let t_e = e.kin.t_e;
    let vbar_e = (8.0 * E_CHARGE * t_e / (PI * M_E)).sqrt();
    for (j, s) in p.surfaces.iter().enumerate() {
        let h = |lam: f64| match s.orientation {
            Orientation::Radial => physics::h_radial_lieberman(R_M, lam),
            Orientation::Axial => physics::h_axial_lieberman(L_M, lam),
        };
        for sp in [1, 2] {
            assert!(h(lmin) <= hs[j][sp] && hs[j][sp] <= h(lmax), "surface {} species {sp}", s.id);
        }
        // EQ-22: n_e,j = sum_s Z_s h_j,s n_i,s; EQ-08 v2 floating sheath Gamma_e = (1/4) n_e,j vbar_e exp(-V_s / T_e).
        let n_ej = hs[j][1] * e.kin.n[1] + 2.0 * hs[j][2] * e.kin.n[2];
        let ge = 0.25 * n_ej * vbar_e * (-e.surfaces[j].barrier_v / t_e).exp();
        assert!(rel(e.surfaces[j].gamma_e, ge) <= 1e-12, "{}: {} vs {ge}", s.id, e.surfaces[j].gamma_e);
        let gz = hs[j][1] * e.kin.n[1] * e.kin.u_b[1] + 2.0 * hs[j][2] * e.kin.n[2] * e.kin.u_b[2];
        assert!(rel(e.surfaces[j].gamma_z, gz) <= 1e-12);
        assert!(rel(e.surfaces[j].gamma_z, e.surfaces[j].gamma_e) <= 1e-10, "{}: floating current", s.id);
    }
}

#[test]
fn lc14_fc28_multi_ion_h_lieb_is_the_three_member_set_with_closed_balances() {
    let m = model_v2();
    let r = m.evaluate(&lieberman_case(with_double_ion(x_set(x_rate())), &[("X+", SIG_1), ("X++", SIG_2)]));
    let members: Vec<&str> = r.solve_members.iter().map(|s| s.h_member.as_str()).collect();
    assert_eq!(members, ["H-MS", "H-LO", "H-HI"], "{:?}", r.reasons);
    assert!(r.flags.contains("MULTI_ION_H_ENVELOPE"));
    assert!(r.verify_items_on_path.contains("VER-21"));
    for (i, sm) in r.solve_members.iter().enumerate() {
        assert_eq!(sm.status, C, "{}: {:?}", sm.solve_member_id, sm.reasons);
        for id in ["CC-01", "CC-03"] {
            let (st, v) = conservation(&r, i, id);
            assert!(st == C && v <= 1e-10, "{} {id}: {v}", sm.h_member);
        }
    }
    // The H-LO / H-HI members bracket the H-MS ion loss: no member is chosen as nominal.
    let ip = |i: usize| scalar(&r, i, "I_production_A");
    assert!(ip(1) <= ip(0) * (1.0 + 1e-9) || ip(2) <= ip(0) * (1.0 + 1e-9));
    assert_eq!(r.if_icp_hall_v1.i_e_cap_by_member_a.len(), 3);
}

// ------------------------------------------------------------------------------------------------------- LC-15

fn area_of(c: &IcpCaseV2, id: &str) -> f64 {
    c.geometry.as_ref().unwrap().value.surfaces.iter().find(|s| s.id == id).unwrap().area_m2
}

#[test]
fn lc15_each_disposition_vertex_places_the_full_class_energy_on_its_destination() {
    let m = model_v2();
    for tau in [Some((0.5, 0.2)), None] {
        let c = disposition_case(tau);
        let r = m.evaluate(&c);
        assert_eq!(r.status, C, "{:?}", r.reasons);
        let t = &r.if_icp_thermal_v2;
        let ends: std::collections::BTreeSet<&str> =
            t.members.iter().map(|x| x.partition_member_id.rsplit("END=").next().unwrap()).collect();
        match tau {
            Some(_) => assert_eq!(ends, ["A_TAU"].into()),
            None => assert_eq!(ends, ["OUT[DOWN]", "OUT[UP]"].into()),
        }
        let mats = |id: &str| {
            if id == "wall" {
                "SYN_A"
            } else if id == "plate" {
                "SYN_B"
            } else {
                "OPEN"
            }
        };
        for mem in &t.members {
            for id in [
                "CC-05-PL",
                "CC-05-B",
                "CC-05-SURFACE-Q",
                "CC-05-NONNEGATIVE",
                "CC-07",
                "CC-08-X",
                "CC-08-N",
                "CC-08-A",
            ] {
                let ck = mem.closures.iter().find(|x| x.id == id).unwrap();
                assert_eq!(ck.status, C, "{} {id}: {:?}", mem.scenario_member_id, ck);
            }
            let pid = &mem.partition_member_id;
            let field = |f: &str| pid.split(';').find_map(|x| x.strip_prefix(&format!("{f}="))).unwrap().to_string();
            let end = field("END");
            let [class_x, alloc_x] = mem.class_energy_w["X"];
            assert!(class_x > 0.0 && rel(alloc_x, class_x) <= 1e-12);
            let [class_n, _] = mem.class_energy_w["N"];
            assert!(class_n > 0.0);
            for (cls, total, get) in [
                ("X", class_x, (|s: &abep_icp::v2::result::SurfaceRecordV2| s.w_x_w) as fn(&_) -> f64),
                ("N", class_n, |s: &abep_icp::v2::result::SurfaceRecordV2| s.w_n_w),
            ] {
                let dest = field(cls);
                let on = |pred: &dyn Fn(&str) -> bool| -> f64 {
                    mem.surfaces.iter().filter(|(id, _)| pred(id)).map(|(_, s)| get(s)).sum()
                };
                let all = on(&|_| true);
                match dest.as_str() {
                    "RAD" => {
                        assert_eq!(cls, "X");
                        assert_eq!(all, 0.0);
                        let rad = mem.keys["Q_icp_radiation_W"].q.value.unwrap();
                        assert!(rel(rad, total) <= 1e-12, "{pid}: RAD {rad} vs {total}");
                    }
                    d if d.starts_with("WALL[") => {
                        let mat = &d[5..d.len() - 1];
                        let got = on(&|id| mats(id) == mat);
                        assert!(rel(got, total) <= 1e-12, "{pid} {cls}: {got} vs {total}");
                        assert!(rel(all, total) <= 1e-12);
                    }
                    "OUT" => {
                        let up = on(&|id| id == "up");
                        let down = on(&|id| id == "down");
                        assert!(rel(up + down, total) <= 1e-12 && rel(all, total) <= 1e-12, "{pid} {cls}");
                        match end.as_str() {
                            "A_TAU" => {
                                let (tu, td) = tau.unwrap();
                                let (wu, wd) = (area_of(&c, "up") * tu, area_of(&c, "down") * td);
                                assert!(rel(up, total * wu / (wu + wd)) <= 1e-12, "{pid}: tau split");
                            }
                            "OUT[UP]" => assert_eq!(down, 0.0),
                            "OUT[DOWN]" => assert_eq!(up, 0.0),
                            e => panic!("{e}"),
                        }
                    }
                    d => panic!("{pid}: destination {d}"),
                }
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------------- LC-16

#[test]
fn lc16_current_normalisation_by_the_largest_component() {
    let m = model_v2();
    for c in [floating_case_v2(10.0), capoff_case_v2(30.0, 0.0, 30.0)] {
        let r = m.evaluate(&c);
        let (st, v) = conservation(&r, 0, "CC-03");
        assert!(st == C && v <= 1e-10, "{}: CC-03 {v}", c.case_id);
    }
    let r = m.evaluate(&capoff_case_v2(0.0, 0.0, 30.0));
    let (st, v) = conservation(&r, 0, "CC-03");
    assert_eq!((st, v), (C, 0.0));
    assert_eq!(scalar(&r, 0, "I_e_cap_A"), 0.0);
    assert_eq!(scalar(&r, 0, "I_production_A"), 0.0);
}

// ------------------------------------------------------------------------------------------------------- LC-17

#[test]
fn lc17_sg01_closed_form_both_branches() {
    let (a, ge, gz, te) = (2e-4, 3e20, 1.5e20, 3.0);
    for drop in [12.0, -4.0, 0.0] {
        let want = E_CHARGE * a * (ge * (2.0 * te + f64::max(0.0, -drop)) + gz * (te / 2.0 + f64::max(0.0, drop)));
        assert!(rel(sg01_closed_form(a, ge, gz, te, drop), want) <= 1e-15);
    }
}

#[test]
fn lc17_interface_closures_and_sign_convention_in_cm_cal() {
    let m = model_v2();
    let c = cal_case_v2(30.0, 3.0, 0.0, 30.0);
    let r = m.evaluate(&c);
    assert_eq!(r.status, C, "{:?}", r.reasons);
    let mem = &r.if_icp_thermal_v2.members[0];
    assert_eq!(mem.status, C, "{:?}", mem.reasons);
    for id in ["CC-05-RF-S", "CC-05-RF", "CC-05-PL", "CC-05-B", "CC-06-S", "CONS-I3"] {
        let (st, v) = closure(&r, 0, id);
        assert!(st == C && v.unwrap() <= 1e-10, "{id}: {v:?}");
    }
    for id in ["SG-01", "SG-01-SUM"] {
        let (st, v) = closure(&r, 0, id);
        assert!(st == C && v.unwrap() <= 1e-12, "{id}: {v:?}");
    }
    // Grand sum from the keys (independent of the closure records).
    let k = |x: &str| mem.keys[x].q.value.unwrap();
    let dest: f64 = abep_icp::v2::evaluate::DESTINATION_KEYS.iter().map(|x| k(x)).sum::<f64>()
        + k("P_icp_flow_control_W")
        + k("P_icp_assist_magnet_W");
    assert!(rel(k("P_icp_slot_load_sum_W"), dest) <= 1e-10);
    // SG-01 from the reported currents: C_j = I_j (phi_p - V_j); sum C_j = -sum I_j V_j; floating C_j = 0.
    let phi = scalar(&r, 0, "phi_p_V");
    let i = map(&r, 0, "I_surface_A");
    let pot = &c.electrodes.as_ref().unwrap().value.potentials_v;
    let mut sum_c = 0.0;
    let mut sum_iv = 0.0;
    for (id, s) in &mem.surfaces {
        match pot.get(id) {
            Some(v) => {
                assert!(rel(s.c_w, i[id] * (phi - v)) <= 1e-12, "{id}");
                sum_iv += i[id] * v;
            }
            None => assert_eq!(s.c_w, 0.0, "{id}: zero-current surface"),
        }
        assert!(rel(s.q_kin_w, s.l_w + s.c_w) <= 1e-15);
        sum_c += s.c_w;
    }
    assert!((sum_c + sum_iv).abs() <= 1e-12 * sum_c.abs().max(sum_iv.abs()));
    assert!(rel(k("P_icp_collector_bias_W"), -sum_iv) <= 1e-12);
    // TK-06: the registered split is echoed.
    let split = &mem.coil_ohmic_split_w;
    assert!(rel(split["N_ANTENNA"].value.unwrap(), 0.75 * k("Q_icp_coil_ohmic_W")) <= 1e-15);
    // All-floating: C_j = 0 exactly.
    let rf = m.evaluate(&floating_case_v2(10.0));
    assert!(rf.if_icp_thermal_v2.members[0].surfaces.values().all(|s| s.c_w == 0.0));
}

// ------------------------------------------------------------------------------------------------------- LC-19

#[test]
fn lc19_diagnostic_closed_forms() {
    let (b, nu, te, ne, r) = (0.01, 3.0e7, 4.0, 1e17, 0.02);
    // CODATA 2018 exact / recommended values (e exact; m_e) written out independently of the crate.
    let (e, me) = (1.602_176_634e-19, 9.109_383_713_9e-31);
    assert!(rel(diagnostics::omega_ce_over_nu_m(b, nu), e * b / (me * nu)) <= 1e-12);
    let vperp = (PI * e * te / (2.0 * me)).sqrt();
    assert!(rel(diagnostics::r_ce_over_r(te, b, r), me * vperp / (e * b * r)) <= 1e-12);
    // lambda_D with the CODATA 2022 eps0 (VER-25 cleared, verification_addendum_ver25_v1.json), written out here.
    let eps0_2022 = 8.854_187_818_8e-12;
    assert!(rel(diagnostics::debye_length(te, ne), (eps0_2022 * te / (e * ne)).sqrt()) <= 1e-12);
    // The shared v1 constant keeps its bytes (CODATA 2018); model_version 2 alone carries the 2022 value.
    assert_eq!(EPS0.to_bits(), 8.854_187_812_8e-12_f64.to_bits());
}

#[test]
fn lc19_fc14_fc21_magnetized_cell_reports_diagnostics_and_withholds_every_plasma_output() {
    let m = model_v2();
    let mut c = disposition_case(Some((0.5, 0.2)));
    c.b_icp_max_t = Some(syn(0.01, "B_ICP,max"));
    let r = m.evaluate(&c);
    assert_eq!(r.status, IcpStatus::IncompleteEvidence, "{:?}", r.reasons);
    assert!(r.reason_codes().contains("DOM-06_NO_SOURCED_MAGNETIZATION_CRITERION"));
    assert!(r.flags.contains("DIAGNOSTIC_UNMAGNETIZED_SOLVE"));
    let sm = &r.solve_members[0];
    let d = &sm.diagnostics;
    for k in ["omega_ce_over_nu_m", "r_ce_over_R"] {
        assert!(d[k].value.is_some(), "{k}: {:?}", d[k]);
        assert!(d[k].reasons.iter().any(|x| x == "DIAGNOSTIC_UNMAGNETIZED_SOLVE"));
    }
    assert!(d.iter().filter(|(k, _)| k.starts_with("s_over_R.")).all(|(_, q)| q.status == IcpStatus::NotEvaluated));
    for (k, o) in &sm.outputs {
        let st = match o {
            OutputValue::Scalar(q) => q.status,
            OutputValue::Label(l) => l.status,
            OutputValue::Map(_) => panic!("{k}: a plasma map output is present for B > 0"),
        };
        assert!(!st.is_converged(), "{k} converged for B > 0");
    }
    for mem in &r.if_icp_thermal_v2.members {
        assert_eq!(mem.status, IcpStatus::IncompleteEvidence);
    }
    assert_eq!(r.if_icp_hall_v1.i_e_cap_envelope_a["min"].status, IcpStatus::NotEvaluated);
}

// ------------------------------------------------------------------------------------------------------- LC-20

/// The N / N+ / N^2+ ionization headers of the pinned EM-N2 set (direct N -> N^2+, stepwise N -> N+ -> N^2+).
fn n_headers(m: &IcpModelV2) -> (ReactionDef, ReactionDef, ReactionDef, Vec<SpeciesDef>) {
    let set = &m.v1.n2_set;
    let charge = |name: &str| set.species.iter().find(|s| s.name == name).map(|s| s.charge);
    let is_n =
        |name: &str| set.species.iter().find(|s| s.name == name).is_some_and(|s| s.elements.get("N") == Some(&1));
    let ion = |r: &ReactionDef, zt: u32, zp: u32| {
        r.kind == ReactionKind::Ionization
            && is_n(&r.target)
            && charge(&r.target) == Some(zt)
            && r.products.len() == 1
            && charge(&r.products[0].0) == Some(zp)
            && is_n(&r.products[0].0)
    };
    let find = |zt, zp| set.reactions.iter().find(|r| ion(r, zt, zp)).unwrap_or_else(|| panic!("{zt}->{zp}")).clone();
    let (a, b, d) = (find(0, 1), find(1, 2), find(0, 2));
    let species = [&a.target, &a.products[0].0, &b.products[0].0]
        .iter()
        .map(|n| {
            let mut s = set.species.iter().find(|s| &&s.name == n).unwrap().clone();
            s.recombines_to = None;
            s
        })
        .collect();
    (a, b, d, species)
}

#[test]
fn lc20_least_energy_route_and_route_excess_with_the_registered_n_headers() {
    let m = model_v2();
    let (step1, step2, direct, species) = n_headers(m);
    assert_eq!((step1.threshold_ev, step2.threshold_ev, direct.threshold_ev), (14.534, 29.60125, 44.1354));
    let syn_rate = |k0: f64, e: f64| RateSource::Synthetic {
        rate: SyntheticRate { k0_m3_s: k0, t_ref_ev: 1.0, power: 0.5, e_act_ev: e, t_cut_ev: None },
    };
    let mut reactions = Vec::new();
    for (r, k0) in [(&step1, 1e-13), (&step2, 5e-14), (&direct, 1e-15)] {
        reactions.push(ReactionDef {
            rate: syn_rate(k0, r.threshold_ev),
            validity: Validity::Verified { max_mean_energy_ev: 255.0 },
            ..r.clone()
        });
    }
    let names: Vec<&str> = species.iter().map(|s| s.name.as_str()).collect();
    let set = ChemistrySet {
        set_id: "SYNTHETIC_N_ROUTES".into(),
        process_classes: excluded_all(&names),
        species: species.clone(),
        reactions,
        t_e_domain_ev: [1.0, 100.0],
        vibrot_t_e_min_ev: 1.0,
    };
    let ft = formation_table(&set, &BTreeMap::new());
    let i2 = set.species_index(&step2.products[0].0).unwrap();
    let e2 = ft.e_form_ev[i2].unwrap();
    assert!(rel(e2, 44.13525) <= 1e-15, "E_form,ref(N^2+) = {e2}");
    assert_eq!(ft.least_routes[i2], vec![step2.id.clone()]);
    let ri = set.reactions.iter().position(|r| r.id == direct.id).unwrap();
    let ex = ft.excess(&set, ri).unwrap();
    assert!((ex - 1.5e-4).abs() <= 1e-12, "route excess {ex}");
    // Through a solve: CC-07 v2 exact and the direct route's excess booked in class X.
    let c = case_v2("SYN_N_ROUTES_V2", set, floating_surfaces_v2(), &[], 20.0);
    let r = m.evaluate(&c);
    assert_eq!(r.status, C, "{:?}", r.reasons);
    for mem in &r.if_icp_thermal_v2.members {
        let ck = mem.closures.iter().find(|x| x.id == "CC-07").unwrap();
        assert!(ck.status == C && ck.value.unwrap() <= 1e-10, "{ck:?}");
        assert!(mem.route_excess_w[&direct.id] > 0.0);
        assert_eq!(mem.route_excess_w[&step1.id], 0.0);
        assert_eq!(mem.route_excess_w[&step2.id], 0.0);
    }
}
