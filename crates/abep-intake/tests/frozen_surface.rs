//! Frozen intake surface v1: hash-verified load, captured-triangulation consistency, interpolation at grid nodes,
//! A9.9 S2.1 recombination identities, species bookkeeping (CONS-01) and fail-closed refusals.

use abep_intake::collection::{collection, IntakeParams};
use abep_intake::constants::{species_mass, AMU};
use abep_intake::freestream::FreeStream;
use abep_intake::frozen::{read_surface_v1, read_triangulation_v1};
use abep_intake::message_key;
use abep_intake::surface::{surface_v2_gate, FrozenIntakeSurfaces};
use abep_provenance::workspace_repo_root;
use abep_types::EvalStatus;
use std::collections::BTreeMap;

/// Positive placeholder for the build-state mixture mass: the identities below hold for any value. The production
/// value comes from the frozen atmosphere (frozen_surface_build_atmosphere); it is not asserted here.
const MB: f64 = 26.0 * AMU;

fn surfaces() -> FrozenIntakeSurfaces {
    FrozenIntakeSurfaces::load(&workspace_repo_root().unwrap(), MB).unwrap()
}

fn fr(o: f64, n2: f64, o2: f64) -> BTreeMap<String, f64> {
    [("O".to_string(), o), ("N2".to_string(), n2), ("O2".to_string(), o2)].into_iter().collect()
}

#[test]
fn frozen_files_and_capture_load_and_agree() {
    let root = workspace_repo_root().unwrap();
    let rows = read_surface_v1(&root).unwrap();
    assert_eq!(rows.len(), 720);
    let tri = read_triangulation_v1(&root).unwrap();
    assert_eq!((tri.points.len(), tri.simplices.len(), tri.degenerate.iter().filter(|&&d| d).count()), (120, 830, 259));
    let s = surfaces();
    assert_eq!(s.maxwell.species(), ["N2", "O", "O2"]);
    assert_eq!(s.cll.bounds(), [(3.0, 20.0), (0.8, 0.9), (0.0, 1.0), (0.0, 5.0)]);
    assert!(s.maxwell.max_unresolved() <= 1e-3);
}

#[test]
fn nodes_reproduce_the_table_rows() {
    let root = workspace_repo_root().unwrap();
    let rows = read_surface_v1(&root).unwrap();
    let s = surfaces();
    for r in rows.iter().filter(|r| r.species == "N2") {
        let e = s
            .get(&r.scattering)
            .unwrap()
            .eval(r.l_over_d, r.phi, r.alpha, r.theta_deg, Some(&fr(0.0, 1.0, 0.0)))
            .unwrap();
        let n2 = &e.species[0].1;
        for (got, want) in
            [(n2.eta_c, r.eta_c), (n2.c_d_row, r.c_d), (n2.cr_passive, r.cr_passive), (n2.k_back, r.k_back)]
        {
            assert!((got - want).abs() <= 1e-13 * want.abs().max(1.0), "{got} vs {want}");
        }
    }
}

#[test]
fn pure_species_and_mixture_identities_and_bookkeeping() {
    let s = surfaces();
    let m = &s.maxwell;
    let pure = m.eval(10.0, 0.85, 0.5, 1.0, Some(&fr(0.0, 1.0, 0.0))).unwrap();
    let n2 = &pure.species[0].1;
    assert_eq!((pure.eta_c, pure.cr_passive, pure.k_back), (n2.eta_c, n2.cr_passive, n2.k_back));
    assert_eq!(pure.c_d, n2.c_d_row * MB / species_mass("N2").unwrap());
    let mix = m.eval(12.5, 0.83, 0.37, 3.3, Some(&fr(0.46, 0.51, 0.03))).unwrap();
    let sum =
        |f: &dyn Fn(&abep_intake::surface::SpeciesEval) -> f64| mix.species.iter().map(|(_, v)| f(v)).sum::<f64>();
    for total in [
        sum(&|v| v.mass_fraction),
        sum(&|v| v.mole_fraction),
        sum(&|v| v.collected_mass_fraction),
        sum(&|v| v.collected_mole_fraction),
    ] {
        assert!((total - 1.0).abs() <= 1e-12);
    }
    assert_eq!(mix.species.iter().map(|(k, _)| k.as_str()).collect::<Vec<_>>(), ["N2", "O", "O2"]);
    // a zero fraction drops the species; unnormalised fractions are normalised
    let two = m.eval(12.5, 0.83, 0.37, 3.3, Some(&fr(2.0, 0.0, 2.0))).unwrap();
    assert_eq!(two.species.iter().map(|(k, _)| k.as_str()).collect::<Vec<_>>(), ["O", "O2"]);
    assert_eq!(two.species[0].1.mass_fraction, 0.5);
}

#[test]
fn refusals_are_out_of_domain_with_registered_keys() {
    let s = surfaces();
    let m = &s.maxwell;
    let key = |r: abep_types::AbepResult<abep_intake::surface::SurfaceEval>| {
        let e = r.unwrap_err();
        assert_eq!(e.status(), EvalStatus::OutOfDomain);
        message_key(&e).unwrap().to_string()
    };
    let f = fr(0.46, 0.51, 0.03);
    assert_eq!(key(m.eval(2.999, 0.85, 0.5, 0.0, Some(&f))), "OUT_OF_BOUNDS");
    assert_eq!(key(m.eval(10.0, 0.85, 0.5, 5.5, Some(&f))), "OUT_OF_BOUNDS");
    assert_eq!(key(m.eval(10.0, 0.85, 0.5, f64::NAN, Some(&f))), "OUT_OF_BOUNDS");
    assert_eq!(key(m.eval(10.0, 0.85, 0.5, 0.0, None)), "FRACTIONS_REQUIRED");
    assert_eq!(key(m.eval(10.0, 0.85, 0.5, 0.0, Some(&BTreeMap::new()))), "FRACTIONS_REQUIRED");
    assert_eq!(key(m.eval(10.0, 0.85, 0.5, 0.0, Some(&fr(-0.1, 1.0, 0.0)))), "FRACTION_INVALID");
    assert_eq!(key(m.eval(10.0, 0.85, 0.5, 0.0, Some(&fr(0.0, 0.0, 0.0)))), "ALL_ZERO");
    let mut foreign = fr(0.0, 0.5, 0.0);
    foreign.insert("Ar".into(), 0.5);
    assert_eq!(key(m.eval(10.0, 0.85, 0.5, 0.0, Some(&foreign))), "FOREIGN_SPECIES");
    foreign.insert("Ar".into(), 0.0);
    assert!(m.eval(10.0, 0.85, 0.5, 0.0, Some(&foreign)).is_ok());
    assert_eq!(message_key(&s.get("specular").unwrap_err()), Some("UNKNOWN_SCATTERING"));
    for bad in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let e = FrozenIntakeSurfaces::load(&workspace_repo_root().unwrap(), bad).unwrap_err();
        assert_eq!(message_key(&e), Some("M_MEAN_BUILD_REQUIRED"));
    }
}

#[test]
fn intake_surface_v2_is_not_evaluated() {
    let g = surface_v2_gate();
    assert_eq!(g.status, EvalStatus::NotEvaluated);
    assert_eq!(g.label, "BLOCKED_PENDING_AOCS_POINTING_ENVELOPE");
}

#[test]
fn tpmc_collection_closes_the_mass_balance() {
    let s = surfaces();
    let m = 26.0 * AMU;
    let fs = FreeStream {
        n: 8e15,
        rho: 8e15 * m,
        v: 7790.0,
        v_rel: None,
        t: 950.0,
        m_mean: m,
        f_o: 0.46,
        f_n2: 0.51,
        f_o2: 0.03,
        flux_kg_m2_s: 8e15 * m * 7790.0,
    };
    for scattering in ["maxwell", "cll"] {
        let p = IntakeParams {
            use_tpmc: true,
            area_m2: 0.7,
            accommodation: 0.8,
            l_over_d: 5.0,
            scattering: scattering.into(),
            ..IntakeParams::default()
        };
        let c = collection(&p, &fs, Some(&s)).unwrap();
        assert_eq!(c.mdot_collected, c.eta_c * c.mdot_incident);
        let sp: f64 = c.mdot_collected_species.as_ref().unwrap().iter().map(|(_, x)| x).sum();
        assert!((sp - c.mdot_collected).abs() <= 1e-12 * c.mdot_collected);
        assert!(c.passive_override.unwrap() > 1.0);
    }
    let off = IntakeParams { use_tpmc: true, off_axis_deg: 6.0, ..IntakeParams::default() };
    assert_eq!(message_key(&collection(&off, &fs, Some(&s)).unwrap_err()), Some("OUT_OF_BOUNDS"));
}
