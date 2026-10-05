//! Orbit atmosphere v1 and HWM14 v2 winds: node reproduction, domain refusals, conservation, the frozen-file
//! re-derivation of the design-state set and the fail-closed loads (contract PARITY-C-ABEP_SIM_ATMOSPHERE_ORBIT_PY-V1).

mod common;

use abep_atmos::design_states::{check, load_design_states};
use abep_atmos::orbit::{OrbitAtmosphere, OrbitRequest};
use abep_atmos::wind::WindAtmosphere;
use abep_data::orbit_v1::{ALT_KM, DOY, LAT_DEG, LON_DEG, LST_H, SCENARIOS};
use abep_types::EvalStatus;

fn rel(a: f64, b: f64) -> f64 {
    if a == b {
        0.0
    } else {
        (a - b).abs() / a.abs().max(b.abs())
    }
}

#[test]
fn nodes_are_reproduced_and_states_conserve_species() {
    let o = OrbitAtmosphere::load(&common::repo_root()).unwrap();
    for (k, sc) in SCENARIOS.iter().enumerate() {
        for (i_doy, i_alt, i_lat, i_lon, i_lst) in [(0, 0, 0, 0, 0), (7, 3, 18, 5, 7), (k, k % 4, 9 + k, k, 2 * k)] {
            let n = o.node_state(i_doy, i_alt, i_lat, i_lon, i_lst, sc.id).unwrap();
            let s = o.state(ALT_KM[i_alt], LAT_DEG[i_lat], LST_H[i_lst], LON_DEG[i_lon], DOY[i_doy], sc.id).unwrap();
            for (a, b) in n.thermo().iter().zip(s.thermo()) {
                assert!(rel(*a, b) <= 1e-10, "INV-D-04 {a} {b}");
            }
            assert_eq!(n.evaluation, "grid_node");
            assert_eq!(n.interp_max_rel_err_rho, Some(0.0));
            assert_eq!(s.evaluation, "interpolated");
            for st in [&n, &s] {
                let x = st.x_o + st.x_n2 + st.x_o2 + st.x_n + st.x_he + st.x_ar;
                assert!((x - 1.0).abs() <= 1e-14, "CONS-D-01");
                let t = st.n_n2_m3 + st.n_o2_m3 + st.n_o_m3 + st.n_he_m3 + st.n_ar_m3 + st.n_n_m3;
                assert_eq!(t.to_bits(), st.n_total_m3.to_bits(), "CONS-D-02");
            }
        }
    }
    let s = o.state(200.0, 0.0, 24.0, -180.0, 365.0, "ECSS_LT_MODERATE").unwrap();
    assert_eq!((s.lst_h, s.lon_deg), (0.0, 180.0));
}

#[test]
fn out_of_domain_queries_are_refused() {
    let root = common::repo_root();
    let o = OrbitAtmosphere::load(&root).unwrap();
    let w = WindAtmosphere::load(&root, &o).unwrap();
    let m = "ECSS_LT_MODERATE";
    for (alt, lat, lst, lon, doy, s) in [
        (179.999, 0.0, 0.0, 0.0, 100.0, m),
        (230.001, 0.0, 0.0, 0.0, 100.0, m),
        (200.0, -90.001, 0.0, 0.0, 100.0, m),
        (200.0, 90.001, 0.0, 0.0, 100.0, m),
        (200.0, 0.0, -1e-9, 0.0, 100.0, m),
        (200.0, 0.0, 24.000001, 0.0, 100.0, m),
        (200.0, 0.0, 0.0, -180.001, 100.0, m),
        (200.0, 0.0, 0.0, 360.001, 100.0, m),
        (200.0, 0.0, 0.0, 0.0, 0.999, m),
        (200.0, 0.0, 0.0, 0.0, 365.001, m),
        (f64::NAN, 0.0, 0.0, 0.0, 100.0, m),
        (200.0, f64::INFINITY, 0.0, 0.0, 100.0, m),
        (200.0, 0.0, 0.0, 0.0, 100.0, "ECSS_LT_MEDIUM"),
        (200.0, 0.0, 0.0, 0.0, 100.0, ""),
    ] {
        assert_eq!(o.state(alt, lat, lst, lon, doy, s).unwrap_err().status(), EvalStatus::OutOfDomain);
        assert_eq!(w.wind(alt, lat, lst, lon, doy, s).unwrap_err().status(), EvalStatus::OutOfDomain);
        assert_eq!(w.state(&o, alt, lat, lst, lon, doy, s).unwrap_err().status(), EvalStatus::OutOfDomain);
    }
    assert_eq!(o.node_state(0, 0, 19, 0, 0, "ECSS_LT_LOW").unwrap_err().status(), EvalStatus::OutOfDomain);
    assert_eq!(o.node_state(8, 0, 0, 0, 0, "ECSS_LT_LOW").unwrap_err().status(), EvalStatus::OutOfDomain);
    assert_eq!(o.node_state(0, 0, 0, 0, 0, "X").unwrap_err().status(), EvalStatus::OutOfDomain);
    let v = w.wind(210.0, 12.3, 7.7, 100.0, 200.5, "ECSS_ST_HIGH").unwrap();
    assert_eq!(v.u_zon_m_s.to_bits(), (v.u_zon_quiet_m_s + v.u_zon_dist_m_s).to_bits(), "CONS-D-04");
    assert_eq!(
        w.state(&o, 210.0, 12.3, 7.7, 100.0, 200.5, "ECSS_ST_HIGH").unwrap().dataset_status,
        "DESIGN_ENVELOPE_PARAMETRIC"
    );
}

#[test]
fn orbit_sampler_validates_like_the_reference() {
    let o = OrbitAtmosphere::load(&common::repo_root()).unwrap();
    let base = OrbitRequest {
        alt_km: 200.0,
        inclination_deg: 97.0,
        ltan_h: 10.5,
        scenario: "ECSS_LT_MODERATE",
        doy: 100.0,
        ut_start_h: 0.0,
        n_samples: 8.0,
    };
    let ok = o.orbit_states(&base).unwrap();
    assert_eq!(ok.len(), 8);
    assert_eq!(ok[0].state_id, "orbit:ECSS_LT_MODERATE:alt200:doy100:k0");
    assert!(ok.iter().all(|s| !s.wind_included && s.orbit_inputs_status.starts_with("PARAMETRIC")));
    let late = o.orbit_states(&OrbitRequest { doy: 365.0, ..base }).unwrap();
    assert_eq!(late.len(), 8);
    let next = o.orbit_states(&OrbitRequest { ut_start_h: 30.0, ..base }).unwrap();
    assert_eq!(next[0].state.doy, 101.0);
    for r in [
        OrbitRequest { n_samples: 3.0, ..base },
        OrbitRequest { n_samples: 4.5, ..base },
        OrbitRequest { doy: 10.5, ..base },
        OrbitRequest { doy: 0.0, ..base },
        OrbitRequest { doy: 366.0, ..base },
        OrbitRequest { inclination_deg: -0.1, ..base },
        OrbitRequest { inclination_deg: 180.1, ..base },
        OrbitRequest { alt_km: 250.0, ..base },
        OrbitRequest { doy: 365.0, ut_start_h: 23.5, ..base },
        OrbitRequest { scenario: "ECSS_LT_MEDIUM", ..base },
        OrbitRequest { ut_start_h: f64::NAN, ..base },
        OrbitRequest { ltan_h: f64::NAN, ..base },
        OrbitRequest { inclination_deg: f64::NAN, ..base },
        OrbitRequest { ut_start_h: f64::INFINITY, ..base },
        OrbitRequest { n_samples: f64::NAN, ..base },
        OrbitRequest { n_samples: f64::INFINITY, ..base },
        OrbitRequest { doy: f64::INFINITY, ..base },
    ] {
        assert_eq!(o.orbit_states(&r).unwrap_err().status(), EvalStatus::OutOfDomain, "{r:?}");
    }
}

#[test]
fn check_reproduces_the_frozen_design_state_set() {
    let r = check(&common::repo_root()).unwrap();
    assert!(r.ok, "{:?}", r.problems);
    let c = r.design_v2_comparison.unwrap();
    assert!(c.ok && c.exact_mismatches.is_empty() && c.max_abs_rel_diff <= 1e-12, "INV-D-01 {c:?}");
}

#[test]
fn frozen_file_refusals() {
    let root = common::repo_root();
    let o = OrbitAtmosphere::load(&root).unwrap();
    assert_eq!(load_design_states(&o, &root, "v2").unwrap().sha256, abep_data::design_states::DESIGN_STATE_SET_SHA256);
    assert!(load_design_states(&o, &root, "v1").is_ok());
    for v in ["v3", ""] {
        assert_eq!(load_design_states(&o, &root, v).unwrap_err().status(), EvalStatus::OutOfDomain);
    }

    let t = common::tree("orbit_gz_mtime");
    t.alter("atmosphere_msis21_orbit_v1.csv.gz", |b| b[4] ^= 1);
    assert_eq!(OrbitAtmosphere::load(&t.root).unwrap_err().status(), EvalStatus::ModelError);
    let r = check(&t.root).unwrap();
    assert!(!r.ok && r.design_v2_comparison.is_none());

    let t = common::tree("orbit_json_missing");
    t.remove("atmosphere_msis21_orbit_v1.json");
    assert_eq!(OrbitAtmosphere::load(&t.root).unwrap_err().status(), EvalStatus::ModelError);
    assert_eq!(check(&t.root).unwrap_err().status(), EvalStatus::ModelError);

    let t = common::tree("design_v2_altered");
    t.alter("atmosphere_msis21_orbit_v1_design_states_v2.json", |b| {
        let i = b.windows(10).position(|w| w == b"python -m ").unwrap();
        b[i + 5] = b'N';
    });
    let o2 = OrbitAtmosphere::load(&t.root).unwrap();
    assert_eq!(load_design_states(&o2, &t.root, "v2").unwrap_err().status(), EvalStatus::ModelError);
    assert!(!check(&t.root).unwrap().ok);

    let t = common::tree("model_set_altered");
    let p = t.root.join("config/model_set/physics_model_set_v1.json");
    let b = std::fs::read(&p).unwrap();
    let s = String::from_utf8(b).unwrap().replacen("\"physics_model_set_v1\"", "\"physics_model_set_vX\"", 1);
    std::fs::write(&p, s).unwrap();
    assert_eq!(OrbitAtmosphere::load(&t.root).unwrap_err().status(), EvalStatus::ModelError);
    assert_eq!(check(&t.root).unwrap_err().status(), EvalStatus::ModelError);

    let t = common::tree("wind_json_missing");
    t.remove("atmosphere_msis21_hwm14_orbit_v2.json");
    assert_eq!(WindAtmosphere::load(&t.root, &o).unwrap_err().status(), EvalStatus::ModelError);
}
