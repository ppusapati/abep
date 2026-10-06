//! Frozen orbit-averaged NRLMSIS 2.1 reader (contract PARITY-C-ABEP_SIM_ATMOSPHERE_PY-V1): node reproduction,
//! domain refusals, conservation and the fail-closed loads.

mod common;

use abep_atmos::msis21::{atmosphere, orbital_velocity, Msis21Frozen, Solar};
use abep_types::constants::K_B;
use abep_types::EvalStatus;

#[test]
fn every_frozen_node_is_reproduced() {
    let fz = Msis21Frozen::load(&common::repo_root()).unwrap();
    assert_eq!(fz.data.alt_axis.len(), 76);
    assert_eq!(fz.data.f107_axis, vec![70.0, 100.0, 150.0, 190.0, 230.0]);
    for c in &fz.data.columns {
        for (i, alt) in c.alt_km.iter().enumerate() {
            let a = atmosphere(&fz, *alt, Solar::F107(c.f107)).unwrap();
            assert!((a.rho / c.rho[i] - 1.0).abs() <= 1e-12, "INV-A-02 rho");
            assert_eq!((a.fO, a.fN2, a.fO2, a.T), (c.f_o[i], c.f_n2[i], c.f_o2[i], c.t_k[i]), "INV-A-02");
            assert!((a.n * a.m_mean / a.rho - 1.0).abs() <= 1e-14, "CONS-A-01");
            assert!((a.p_ambient_Pa / (a.n * K_B * a.T) - 1.0).abs() <= 1e-14, "CONS-A-02");
        }
    }
    let m = atmosphere(&fz, 200.0, Solar::Label("mean".into())).unwrap();
    assert_eq!((m.f107, m.f107a, m.ap, m.epoch.as_str()), (150.0, 150.0, 15.0, "2028-03-21T12:00"));
    assert_eq!(m.source, "NRLMSIS 2.1 frozen scenario 5e108c6e5cb7c03e");
}

#[test]
fn out_of_domain_and_unknown_labels_are_refused() {
    let fz = Msis21Frozen::load(&common::repo_root()).unwrap();
    for (alt, solar) in [
        (149.999, Solar::Label("mean".into())),
        (300.001, Solar::Label("mean".into())),
        (200.0, Solar::F107(69.999)),
        (200.0, Solar::F107(230.001)),
        (f64::NAN, Solar::Label("mean".into())),
        (f64::INFINITY, Solar::Label("mean".into())),
        (f64::NEG_INFINITY, Solar::F107(150.0)),
        (200.0, Solar::F107(f64::NAN)),
        (200.0, Solar::Label("medium".into())),
        (200.0, Solar::Label(String::new())),
    ] {
        assert_eq!(atmosphere(&fz, alt, solar).unwrap_err().status(), EvalStatus::OutOfDomain);
    }
    for alt in [-6371.0, -6400.0, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        assert_eq!(orbital_velocity(alt).unwrap_err().status(), EvalStatus::OutOfDomain, "{alt}");
    }
    assert!(orbital_velocity(-6370.999).unwrap() > 0.0);
}

#[test]
fn missing_or_altered_frozen_table_is_model_error() {
    let t = common::tree("msis_csv_missing");
    t.remove("atmosphere_msis21_v1.csv");
    assert_eq!(Msis21Frozen::load(&t.root).unwrap_err().status(), EvalStatus::ModelError);
    let t = common::tree("msis_json_missing");
    t.remove("atmosphere_msis21_v1.json");
    assert_eq!(Msis21Frozen::load(&t.root).unwrap_err().status(), EvalStatus::ModelError);
    let t = common::tree("msis_csv_altered");
    t.alter("atmosphere_msis21_v1.csv", |b| {
        let i = b.windows(42).position(|w| w.starts_with(b"2.00000000e+02,1.50000000e+02,")).unwrap();
        b[i + 39] = if b[i + 39] == b'9' { b'0' } else { b[i + 39] + 1 };
    });
    assert_eq!(Msis21Frozen::load(&t.root).unwrap_err().status(), EvalStatus::ModelError);
}
