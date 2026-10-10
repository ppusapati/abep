//! Acceptance cases AT-01 .. AT-10 of ACCEPT-DIAG-B2-OF-01-INTERP-SENSITIVITY-V1
//! (`docs/rust_migration/contracts/DIAG-B2-OF-01-INTERP-SENSITIVITY/acceptance_prereg_v1.json`).

use abep_intake::frozen::read_surface_v1;
use abep_uq::interp_sensitivity::{chain_application, Diagnostic, FaceGeometry, ROUNDING_RTOL};
use serde_json::Value;
use std::path::PathBuf;
use std::sync::OnceLock;

fn repo() -> PathBuf {
    abep_provenance::workspace_repo_root().expect("repository root")
}

fn diag() -> &'static Diagnostic {
    static D: OnceLock<Diagnostic> = OnceLock::new();
    D.get_or_init(|| Diagnostic::load(&repo()).expect("diagnostic loads"))
}

const TABLES: [&str; 2] = ["maxwell", "cll"];
const SPECIES: [&str; 3] = ["N2", "O", "O2"];
const FIELDS: [&str; 5] = ["eta_c", "C_D", "CR_passive", "K_back", "mass_kg"];

fn rel_close(a: f64, b: f64) -> bool {
    (a - b).abs() <= ROUNDING_RTOL * b.abs().max(f64::MIN_POSITIVE)
}

#[test]
fn at01_grid_node_is_single_valued_and_equals_the_node_row() {
    let p = [5.0, 0.8, 0.5, 2.0];
    let rows = read_surface_v1(&repo()).expect("frozen csv");
    for t in TABLES {
        let c = diag().classify(t, p).unwrap();
        assert_eq!(c.geometry, FaceGeometry::GridNode);
        assert_eq!(c.free_dims, 0);
        let mut hit = c.faces_hit.clone();
        hit.sort();
        assert_eq!(hit, vec!["L_over_d = 5", "alpha = 0.5", "theta_deg = 2"]);
        let env = diag().envelope(t, p).unwrap().expect("containing simplices");
        assert!(env.rounding_level(), "{t}: spread {}", env.max_spread());
        let rec = diag().evaluate(t, p).unwrap();
        assert_eq!(rec["status"], "NUMERICAL_INTERPOLATION_SENSITIVITY");
        assert_eq!(rec["sensitivity_class"], "ROUNDING_LEVEL");
        for sp in SPECIES {
            let node = rows
                .iter()
                .find(|r| {
                    r.scattering == t
                        && r.species == sp
                        && r.l_over_d == 5.0
                        && r.phi == 0.8
                        && r.alpha == 0.5
                        && r.theta_deg == 2.0
                })
                .expect("node row");
            let want = [node.eta_c, node.c_d, node.cr_passive, node.k_back, node.mass_kg];
            for (j, f) in FIELDS.iter().enumerate() {
                let e = &rec["envelope"]["species"][sp][f];
                for k in ["min", "max", "authoritative"] {
                    let v = e[k].as_f64().unwrap();
                    assert!(rel_close(v, want[j]), "{t} {sp} {f} {k}: {v} vs node {}", want[j]);
                }
            }
        }
    }
}

#[test]
fn at02_survey_default_points_are_rounding_level() {
    let pts = [
        ([10.0, 0.85, 0.5, 0.0], FaceGeometry::GridEdge),
        ([5.0, 0.85, 0.8, 0.0], FaceGeometry::GridEdge),
        ([10.0, 0.85, 0.95, 0.0], FaceGeometry::FaceInterior),
        ([3.0, 0.85, 0.5, 0.0], FaceGeometry::GridEdge),
        ([5.0, 0.85, 0.8, 2.0], FaceGeometry::GridEdge),
    ];
    for t in TABLES {
        for (p, g) in pts {
            assert_eq!(diag().classify(t, p).unwrap().geometry, g, "{t} {p:?}");
            let env = diag().envelope(t, p).unwrap().expect("containing simplices");
            assert!(env.max_spread() <= ROUNDING_RTOL, "{t} {p:?}: spread {}", env.max_spread());
            assert_eq!(diag().evaluate(t, p).unwrap()["sensitivity_class"], "ROUNDING_LEVEL");
        }
    }
}

#[test]
fn at03_survey_maxima_are_reproduced_and_non_conforming() {
    let cases: [(&str, &str, &str, [f64; 4], f64); 5] = [
        (
            "eta_c",
            "maxwell",
            "N2",
            [8.227784022690075, 0.8374126887937825, 0.6952669150405878, 2.0],
            0.03768632268222069,
        ),
        ("C_D", "cll", "O", [8.227784022690075, 0.8374126887937825, 0.6952669150405878, 2.0], 0.002217463318732964),
        (
            "CR_passive",
            "cll",
            "N2",
            [14.915437578732714, 0.8108001576950183, 0.048672246638759575, 2.0],
            0.1733934754224049,
        ),
        (
            "K_back",
            "cll",
            "O2",
            [13.642166426737925, 0.8551641047390511, 0.38885151921681604, 2.0],
            0.061172634747115436,
        ),
        (
            "mass_kg",
            "maxwell",
            "N2",
            [15.193095968023385, 0.8484514633109874, 0.2, 3.880158262223903],
            0.03729597039010955,
        ),
    ];
    for (field, t, sp, p, survey) in cases {
        assert_eq!(diag().classify(t, p).unwrap().geometry, FaceGeometry::FaceInterior);
        let rec = diag().evaluate(t, p).unwrap();
        assert_eq!(rec["sensitivity_class"], "NON_CONFORMING");
        let e = &rec["envelope"]["species"][sp][field];
        let spread = e["relative_spread"].as_f64().unwrap();
        assert!((spread - survey).abs() <= ROUNDING_RTOL, "{field}: {spread} vs survey {survey}");
        let (lo, hi, auth) =
            (e["min"].as_f64().unwrap(), e["max"].as_f64().unwrap(), e["authoritative"].as_f64().unwrap());
        assert!(lo <= auth && auth <= hi, "{field}: authoritative {auth} outside [{lo}, {hi}]");
        // the authoritative value is the admitted interpolation, unchanged
        let rows = diag().surfaces.get(t).unwrap().species_rows_at(p[0], p[1], p[2], p[3]).unwrap();
        let k = SPECIES.iter().position(|s| *s == sp).unwrap();
        let j = FIELDS.iter().position(|f| *f == field).unwrap();
        assert_eq!(rows[k][j].to_bits(), auth.to_bits());
    }
}

#[test]
fn at04_one_ulp_off_the_face_is_not_on_it() {
    let p = [14.915437578732714, 0.8108001576950183, 0.048672246638759575, f64::from_bits(2.0f64.to_bits() + 1)];
    let c = diag().classify("cll", p).unwrap();
    assert_eq!(c.geometry, FaceGeometry::NotOnKnownFace);
    let rec = diag().evaluate("cll", p).unwrap();
    assert_eq!(rec["status"], "NOT_APPLICABLE");
    assert!(rec["authoritative"].is_object());
    assert!(rec["envelope"].is_null());
}

#[test]
fn at05_cell_interior_and_outer_faces_are_single_valued() {
    for t in TABLES {
        for p in [[4.0, 0.85, 0.35, 1.0], [4.0, 0.8, 0.35, 1.0], [20.0, 0.9, 1.0, 5.0]] {
            assert_eq!(diag().classify(t, p).unwrap().geometry, FaceGeometry::NotOnKnownFace, "{t} {p:?}");
            assert_eq!(diag().evaluate(t, p).unwrap()["status"], "NOT_APPLICABLE");
            let env = diag().envelope(t, p).unwrap().expect("containing simplices");
            assert!(env.max_spread() <= ROUNDING_RTOL, "{t} {p:?}: {}", env.max_spread());
        }
    }
}

#[test]
fn at06_out_of_domain_has_no_value() {
    for p in [[2.0, 0.85, 0.5, 0.0], [20.0000001, 0.85, 0.5, 0.0], [f64::NAN, 0.85, 0.5, 0.0]] {
        let rec = diag().evaluate("maxwell", p).unwrap();
        assert_eq!(rec["face_geometry"], "OUT_OF_DOMAIN");
        assert_eq!(rec["status"], "OUT_OF_DOMAIN");
        assert!(rec["authoritative"].is_null() && rec["envelope"].is_null());
    }
}

#[test]
fn at07_grid_and_face_cross_checks_fail_closed() {
    let names: Vec<String> =
        ["L_over_d = 10", "L_over_d = 5", "alpha = 0.2", "alpha = 0.5", "alpha = 0.8", "theta_deg = 2"]
            .iter()
            .map(|s| s.to_string())
            .collect();
    assert_eq!(Diagnostic::check_faces(&diag().grids, &names).unwrap().len(), 6);
    let mut tampered = names.clone();
    tampered.pop();
    assert!(Diagnostic::check_faces(&diag().grids, &tampered).is_err());
    let mut extra = names.clone();
    extra.push("phi = 0.85".into());
    assert!(Diagnostic::check_faces(&diag().grids, &extra).is_err());
    for (_, g) in &diag().grids {
        assert_eq!(g[0], vec![3.0, 5.0, 10.0, 20.0]);
        assert_eq!(g[1], vec![0.8, 0.9]);
        assert_eq!(g[2], vec![0.0, 0.2, 0.5, 0.8, 1.0]);
        assert_eq!(g[3], vec![0.0, 2.0, 5.0]);
    }
}

#[test]
fn at08_f7_f8_candidate_points_are_grid_nodes_and_unused_by_the_chain() {
    let f1 = abep_design::f1view::F1View::load(&repo()).expect("F1 view");
    let mut cands = vec![];
    for ld in &f1.l_over_d {
        for phi in &f1.phi {
            cands.push((format!("Ld{ld}_phi{phi}"), *ld, *phi));
        }
    }
    let app = chain_application(diag(), &cands, &f1.scenarios).unwrap();
    assert_eq!(app["interpolant_used_by_chain"], Value::Bool(false));
    assert_eq!(app["n_non_conforming"], 0);
    let counts = app["face_geometry_counts"].as_object().unwrap();
    assert!(counts.keys().all(|k| k == "GRID_NODE" || k == "NOT_ON_KNOWN_FACE"), "{counts:?}");
    for p in app["points"].as_array().unwrap() {
        if p["record"]["status"] == "NUMERICAL_INTERPOLATION_SENSITIVITY" {
            assert_eq!(p["record"]["sensitivity_class"], "ROUNDING_LEVEL");
        }
    }
}

#[test]
fn at10_records_are_deterministic() {
    for p in [[14.915437578732714, 0.8108001576950183, 0.048672246638759575, 2.0], [5.0, 0.8, 0.5, 2.0]] {
        assert_eq!(diag().evaluate("cll", p).unwrap(), diag().evaluate("cll", p).unwrap());
    }
}
