//! DCR-DBF1-001 amendment v3 harness (docs/baseline/DCR-001/dcr001_eval_prereg_v3.json): preregistration pins, the
//! effective-area grid, the cross-checks against the v1 harness, the operating-point conditions on a real table and
//! the window / coverage rules.

use abep_assess::dcr001::{gather, Inputs, FILTERS, GEOMS, NOMINAL, TARGETS_PA, VOLUMES_M3};
use abep_assess::dcr001_window::*;
use abep_provenance::{read_verified, workspace_repo_root};
use std::sync::OnceLock;

fn inputs() -> &'static Inputs {
    static I: OnceLock<Inputs> = OnceLock::new();
    I.get_or_init(|| gather(&workspace_repo_root().unwrap()).unwrap())
}

fn w() -> &'static WInputs<'static> {
    static W: OnceLock<WInputs<'static>> = OnceLock::new();
    W.get_or_init(|| gather_window(&workspace_repo_root().unwrap(), inputs()).unwrap())
}

#[test]
fn prereg_v3_pins_verify_and_a_wrong_pin_is_refused() {
    let repo = workspace_repo_root().unwrap();
    verify_prereg_v3(&repo).unwrap();
    assert!(read_verified(&repo.join(V3_REL), &"0".repeat(64)).is_err());
}

#[test]
fn effective_area_grid_is_every_open_fraction_of_every_aperture() {
    let g = aeff_grid();
    assert_eq!(g.len(), 27);
    assert!(g.windows(2).all(|p| p[0] < p[1]));
    for a in A_MAX {
        for n in N_SEG {
            for j in 1..=n {
                let x = a * j as f64 / n as f64;
                assert!(g.iter().any(|y| (y - x).abs() < 1e-12));
            }
        }
    }
    assert_eq!((g[0], g[26]), (0.03125, 1.5));
}

#[test]
fn inputs_carry_the_registered_ceilings_host_drag_and_nodes() {
    let w = w();
    assert_eq!(w.cda_host_m2, 0.22106);
    assert!((w.pd1350(w.cp_nom_w) - w.pd1350_ref_w).abs() < 1e-12);
    assert!((w.pd1350(w.cp_nom_w + 10.0) - (w.pd1350_ref_w - 9.0)).abs() < 1e-9);
    assert!(w.headroom_w > 231.0 && w.headroom_w < 232.0);
    assert_eq!(w.conds.len(), 4);
    assert_eq!(w.nodes.len(), 16);
    assert_eq!(w.nodes.iter().map(|n| n.2.len()).sum::<usize>(), 196);
    assert!(w.order.windows(2).all(|p| w.phi[p[0]] <= w.phi[p[1]]));
    assert!(w.c_mass.len() < inputs().compressors.len());
}

#[test]
fn window_harness_reproduces_the_v1_harness_and_the_side_is_linear_in_area() {
    let x = crosscheck_window(w()).unwrap();
    assert_eq!(x["status"], "PASS", "{x}");
}

#[test]
fn closed_shutter_drag_is_the_registered_bound() {
    let w = w();
    let i = w.order[100];
    let (g, si) = (7, 3);
    let open = w.d_tot(g, si, i, 0.5, 0.5, 0.0);
    let half = w.d_tot(g, si, i, 0.5, 0.25, 0.0);
    let q = inputs().q_pa[i];
    assert!((half - (open / 2.0 + C_CLOSED * q * 0.25)).abs() < 1e-15);
    assert!((w.d_tot(g, si, i, 0.5, 0.5, 1.0) - open - q).abs() < 1e-15);
}

#[test]
fn operating_points_meet_every_condition_and_runs_are_served() {
    let w = w();
    let inp = inputs();
    let g = GEOMS.iter().position(|x| *x == (20.0, 0.9)).unwrap();
    let fc = inp.filter(FILTERS[0]).unwrap();
    let plant = inp.plant(&inp.compressors[w.c_mass[0]], &NOMINAL).unwrap();
    let pl = inp.plenum(VOLUMES_M3[0]).unwrap();
    let t = eval_table(w, g, fc, &plant, &pl, w.cda_host_m2).unwrap();
    for n in [1, 4] {
        for j in [2, 3] {
            let e = eval_design(w, &t, g, 1.0, n, j, GOVERNING).unwrap();
            for (i, row) in e.ops.iter().enumerate() {
                assert_eq!(e.served[i], row.iter().all(|o| o.is_ok()));
                for op in row.iter().flatten() {
                    assert!(op.d_tot <= inp.t25_n && op.mdot >= op.req && op.p_el <= w.headroom_w);
                    assert!(op.m <= inp.m_comp_limit_kg && op.j_open >= 1 && op.j_open <= n);
                    assert!((w.aeff[op.a] - op.j_open as f64 / n as f64).abs() < 1e-12);
                }
            }
            if let Some((k0, k1)) = e.run {
                assert!((k0..=k1).all(|q| e.served[w.order[q]]));
                assert_eq!(coverage(w, k0, k1).0, e.o1);
                let ops = window_ops(w, &e);
                assert_eq!(ops.len(), (k1 - k0 + 1) * inp.up.scenarios.len());
            }
            let _ = TARGETS_PA[j];
        }
    }
}

#[test]
fn ranking_puts_coverage_before_complexity_and_complexity_before_width() {
    let inp = inputs();
    let base = WDesign {
        g: 0,
        filter: 0,
        comp: 0,
        a_max: 0.5,
        n: 2,
        target: 0,
        o1: 3,
        o2: 6,
        log_width: 1.0,
        r_sus: 1.2,
        m_max: 3.0,
        d_max: 0.01,
        p_max: 20.0,
    };
    let more_cov = WDesign { o1: 4, n: 8, ..base.clone() };
    let simpler = WDesign { n: 1, log_width: 0.5, ..base.clone() };
    assert!(cmp_keys(&more_cov.keys(inp), &base.keys(inp)).is_lt());
    assert!(cmp_keys(&simpler.keys(inp), &base.keys(inp)).is_lt());
}
