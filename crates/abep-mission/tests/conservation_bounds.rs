//! NP-HALL-PARAMETRIC-ENVELOPE addendum A4 kernels (sec. verification): analytic limiting cases against independent
//! numerical quadrature of the drifting Maxwellian, the jet-thrust bound and its inverses, the speed bound's circular
//! limit, and fail-closed refusals.

use abep_mission::conservation_bounds::*;
use abep_types::constants::{AMU, K_B, MU_EARTH, M_N2, M_O};
use abep_types::EvalStatus;

/// Composite Simpson rule on [a, b] with n (even) panels.
fn simpson(f: impl Fn(f64) -> f64, a: f64, b: f64, n: usize) -> f64 {
    let h = (b - a) / n as f64;
    let mut s = f(a) + f(b);
    for k in 1..n {
        s += f(a + k as f64 * h) * if k % 2 == 1 { 4.0 } else { 2.0 };
    }
    s * h / 3.0
}

/// One-sided particle and translational energy flux of a drifting Maxwellian (n = 1, m = 1) by quadrature over v_x.
fn quadrature(u: f64, c: f64) -> (f64, f64) {
    let s2 = c * c / 2.0;
    let f = |v: f64| (-(v - u).powi(2) / (2.0 * s2)).exp() / (2.0 * std::f64::consts::PI * s2).sqrt();
    let hi = u + 40.0 * c;
    let g = simpson(|v| v * f(v), 0.0, hi, 400_000);
    let e = simpson(|v| 0.5 * v * (v * v + 2.0 * s2) * f(v), 0.0, hi, 400_000);
    (g, e)
}

#[test]
fn flux_bounds_hold_against_quadrature_and_are_tight_at_large_speed_ratio() {
    // m = 1 kg carrier, T chosen so that c = 1 m/s: 2 k T / m = 1.
    let t = 1.0 / (2.0 * K_B);
    for s in [0.5, 1.0, 1.75, 3.0, 7.0] {
        let k = [Carrier { name: "X".into(), rho_kg_m3: 1.0, m_kg: 1.0 }];
        let fb = flux_bound(&k, t, s).unwrap();
        let (g, e) = quadrature(s, 1.0);
        let c = &fb.carriers[0];
        assert!((c.speed_ratio - s).abs() < 1e-12);
        assert!(c.phi_kg_m2_s >= g * (1.0 - 1e-10), "Phi bound at S = {s}");
        assert!(c.q_translational_w_m2 >= e * (1.0 - 1e-10), "q bound at S = {s}");
        if s >= 3.0 {
            assert!((c.phi_kg_m2_s / g - 1.0).abs() < 2e-5, "tight at S = {s}");
            assert!((c.q_translational_w_m2 / e - 1.0).abs() < 2e-5, "tight at S = {s}");
        }
        // internal <= 2 k T / m per unit mass flux; chemical = Phi eps_x,max
        assert!((c.q_internal_w_m2 - c.phi_kg_m2_s * 2.0 * K_B * t).abs() <= 1e-12 * c.q_internal_w_m2);
        assert!((fb.q_chemical_w_m2 - fb.phi_max_kg_m2_s * eps_x_max_j_kg()).abs() <= 1e-12 * fb.q_chemical_w_m2);
    }
}

#[test]
fn hypersonic_flux_is_rho_u_and_lighter_carriers_raise_it() {
    let (t, u) = (1000.0, 7800.0);
    let heavy = flux_bound(&[Carrier { name: "N2".into(), rho_kg_m3: 1e-10, m_kg: M_N2 }], t, u).unwrap();
    assert!((heavy.phi_max_kg_m2_s / (1e-10 * u) - 1.0).abs() < 1e-15);
    let light = flux_bound(&[Carrier { name: "H".into(), rho_kg_m3: 1e-10, m_kg: M_H_MIN }], t, u).unwrap();
    assert!(light.phi_max_kg_m2_s > heavy.phi_max_kg_m2_s);
    assert!(light.s_min < heavy.s_min);
}

#[test]
fn carriers_split_the_stored_density_and_carry_the_remainder_as_hydrogen() {
    let k = carriers(1e-9, 1e15, 1e15, 1e14).unwrap();
    let sum: f64 = k[..3].iter().map(|c| c.rho_kg_m3).sum();
    assert_eq!(k.len(), 4);
    assert_eq!(k[3].name, "REMAINDER_AS_H");
    assert_eq!(k[3].m_kg, M_H_MIN);
    assert!((k[3].rho_kg_m3 - (1e-9 - sum)).abs() < 1e-24);
    assert_eq!(k[0].rho_kg_m3, 1e15 * M_O);
    // species above the stored total: no negative remainder, the total is the species sum
    let k = carriers(1e-12, 1e15, 0.0, 0.0).unwrap();
    assert_eq!(k[3].rho_kg_m3, 0.0);
}

#[test]
fn thrust_bound_is_attained_by_a_monoenergetic_jet_and_exceeds_any_spread_jet() {
    let (m, u) = (1e-7, 20_000.0);
    let p = 0.5 * m * u * u;
    let tm = t_max(m, p).unwrap();
    assert!(((tm - p / C_LIGHT) / (m * u) - 1.0).abs() < 1e-12);
    // two streams with the same total mass flow and kinetic power give less thrust
    let (m1, m2, u1) = (0.4 * m, 0.6 * m, 30_000.0);
    let u2 = ((2.0 * p - m1 * u1 * u1) / m2).sqrt();
    assert!(m1 * u1 + m2 * u2 < tm - p / C_LIGHT);
}

#[test]
fn required_flow_and_area_invert_the_thrust_bound() {
    for (t, p) in [(0.012, 1500.0), (0.025, 1500.0), (0.025, 900.0)] {
        let m = mdot_required(t, p).unwrap();
        assert!((t_max(m, p).unwrap() / t - 1.0).abs() < 1e-12);
        assert!((m / ((t - p / C_LIGHT).powi(2) / (2.0 * p)) - 1.0).abs() < 1e-15);
        for (phi, q) in [(5e-6, 0.0), (5e-6, 1.2), (3e-7, 0.07)] {
            let a = area_required(t, p, phi, q).unwrap();
            assert!((t_max_at_area(a, p, phi, q).unwrap() / t - 1.0).abs() < 1e-10, "{t} {p} {phi} {q}");
            assert!(t_max_at_area(a * 0.999, p, phi, q).unwrap() < t);
            if q == 0.0 {
                assert!((a / (m / phi) - 1.0).abs() < 1e-12, "A_req,0 = mdot_req / Phi at q = 0");
            } else {
                assert!(a <= m / phi, "energy inflow can only lower the required area");
            }
        }
    }
    // a thrust a photon rocket already provides needs no mass flow
    assert_eq!(mdot_required(1e-9, 1500.0).unwrap(), 0.0);
    assert_eq!(area_required(1e-9, 1500.0, 1e-6, 0.0).unwrap(), 0.0);
}

#[test]
fn captured_momentum_drag_and_the_t_minus_d_maximum() {
    let (p, u) = (1500.0, 7700.0);
    assert_eq!(captured_momentum_drag(2e-8, u).unwrap(), 2e-8 * u);
    let m = mdot_td_max(p, u).unwrap();
    assert!((t_max(m, p).unwrap() / (m * u) - 1.0).abs() < 1e-9);
    assert!((m / (2.0 * p / (u * u)) - 1.0).abs() < 1e-4, "~ 2P / U^2 (radiation shifts it by ~ U / c)");
    let best = max_t_minus_dcap(p, u).unwrap();
    let opt = p / (2.0 * u * u);
    for f in [0.5, 0.9, 1.0, 1.1, 2.0] {
        assert!(t_max(opt * f, p).unwrap() - opt * f * u <= best * (1.0 + 1e-12));
    }
    assert!(((t_max(opt, p).unwrap() - opt * u) / best - 1.0).abs() < 1e-12);
}

#[test]
fn speed_bound_reduces_to_the_circular_speed_and_adds_rotation_and_wind() {
    let h = 200e3;
    let r = WGS84_A + h;
    let v_circ = (MU_EARTH / r).sqrt();
    // equator, one-altitude band, no wind: circular orbit at r with the J2 allowance, plus co-rotation at r
    let b = speed_bound(&SpeedInputs {
        lat_deg: 0.0,
        alt_m: h,
        alt_min_m: h,
        alt_max_m: h,
        v_admitted_m_s: 1.0,
        wind_m_s: 0.0,
    })
    .unwrap();
    assert!((b.r_geocentric_m - r).abs() < 1e-6);
    let j2 = 3.0 * abep_atmos::mission_env_kernel::J2 * (WGS84_A / r).powi(2);
    assert!((b.v_orb_max_m_s / (v_circ * (1.0 + j2).sqrt()) - 1.0).abs() < 1e-14);
    assert!((b.v_rot_m_s - abep_atmos::mission_env_kernel::OMEGA_E * r).abs() < 1e-9);
    assert_eq!(b.u_max_m_s, b.v_orb_max_m_s + b.v_rot_m_s);
    // the admitted speed is a floor; an eccentric orbit in the band is faster at its periapsis; wind adds
    let base = SpeedInputs {
        lat_deg: 45.0,
        alt_m: 180e3,
        alt_min_m: 180e3,
        alt_max_m: 230e3,
        v_admitted_m_s: 9000.0,
        wind_m_s: 150.0,
    };
    let b = speed_bound(&base).unwrap();
    assert_eq!(b.v_orb_max_m_s, 9000.0);
    assert_eq!(b.u_max_m_s, 9000.0 + b.v_rot_m_s + 150.0);
    let ecc = speed_bound(&SpeedInputs { v_admitted_m_s: 1.0, ..base }).unwrap();
    let circ = speed_bound(&SpeedInputs { v_admitted_m_s: 1.0, alt_max_m: 180e3, ..base }).unwrap();
    assert!(ecc.v_orb_max_m_s > circ.v_orb_max_m_s);
    assert!(ecc.u_min_m_s < ecc.u_max_m_s);
    // the pole does not co-rotate
    let pole = speed_bound(&SpeedInputs { lat_deg: 90.0, ..base }).unwrap();
    assert!(pole.v_rot_m_s < 1e-9);
    assert!((pole.r_geocentric_m - (wgs84_b() + 180e3)).abs() < 1e-6);
}

#[test]
fn registered_constants() {
    // eps_x,max = D0(H2) / (2 m_H,min) = 2.2217 eV/u
    let ev_per_u = eps_x_max_j_kg() * AMU / abep_types::constants::E_CHARGE;
    assert!((ev_per_u - 4.4781 / (2.0 * 1.00784)).abs() < 1e-12);
    assert!((wgs84_b() - 6_356_752.314_245).abs() < 1e-3);
    assert!((wgs84_e2() - 6.694_379_990_14e-3).abs() < 1e-12);
    assert!(LABEL.contains("NOT_A_PERFORMANCE_PREDICTION"));
}

#[test]
fn non_finite_or_out_of_domain_inputs_are_refused() {
    let ood = |r: abep_types::AbepResult<f64>| assert_eq!(r.unwrap_err().status(), EvalStatus::OutOfDomain);
    ood(t_max(f64::NAN, 1.0));
    ood(t_max(1e-8, -1.0));
    ood(mdot_required(0.012, 0.0));
    ood(area_required(0.012, 1500.0, 0.0, 0.0));
    ood(area_required(0.012, 1500.0, 1e-6, f64::INFINITY));
    // q beyond 2 Phi c^2 is outside the kernel's domain
    ood(area_required(0.012, 1500.0, 1e-12, 1e6));
    ood(captured_momentum_drag(-1.0, 7000.0));
    ood(mdot_td_max(1500.0, 0.0));
    let k = [Carrier { name: "O".into(), rho_kg_m3: 1e-10, m_kg: M_O }];
    assert_eq!(flux_bound(&k, 0.0, 7800.0).unwrap_err().status(), EvalStatus::OutOfDomain);
    assert_eq!(flux_bound(&k, 1000.0, f64::NAN).unwrap_err().status(), EvalStatus::OutOfDomain);
    let empty = [Carrier { name: "O".into(), rho_kg_m3: 0.0, m_kg: M_O }];
    assert_eq!(flux_bound(&empty, 1000.0, 7800.0).unwrap_err().status(), EvalStatus::OutOfDomain);
    assert_eq!(carriers(f64::NAN, 1.0, 1.0, 1.0).unwrap_err().status(), EvalStatus::OutOfDomain);
    let bad = SpeedInputs {
        lat_deg: 10.0,
        alt_m: 250e3,
        alt_min_m: 180e3,
        alt_max_m: 230e3,
        v_admitted_m_s: 7800.0,
        wind_m_s: 0.0,
    };
    assert_eq!(speed_bound(&bad).unwrap_err().status(), EvalStatus::OutOfDomain);
    assert_eq!(
        speed_bound(&SpeedInputs { alt_m: 200e3, lat_deg: 91.0, ..bad }).unwrap_err().status(),
        EvalStatus::OutOfDomain
    );
    assert_eq!(
        speed_bound(&SpeedInputs { alt_m: 200e3, wind_m_s: f64::NAN, ..bad }).unwrap_err().status(),
        EvalStatus::OutOfDomain
    );
}
