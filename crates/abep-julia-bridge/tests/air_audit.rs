//! NP-HALL-CHEM-AIR: the CA-HALL-AIR-v1 audit inputs reproduce from Rust, follow the snapshot and inlet rules, and the
//! verdict reader applies the preregistered rules literally. No test spawns Julia. Records built here are
//! SYNTHETIC_TEST_DATA_NOT_EVIDENCE: they exist only in memory and never in a record.

use abep_julia_bridge::air_audit::{ambiguity_verdict, ineligible, metric, verdicts, METRICS, SUM_KEYS};
use abep_julia_bridge::air_cases::{
    check_audit, check_snapshots, composition_points, inlet_velocity, v1_n2_rows, AUDIT_CASES_REL, AUDIT_MANIFEST_REL,
    V1_FIELDS,
};
use abep_provenance::workspace_repo_root;
use abep_types::pyjson::{self, Dict, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

fn repo() -> PathBuf {
    workspace_repo_root().unwrap()
}

fn cases() -> Vec<Value> {
    let doc = pyjson::loads(&std::fs::read_to_string(repo().join(AUDIT_CASES_REL)).unwrap()).unwrap();
    doc.as_dict().unwrap().get("cases").unwrap().as_list().unwrap().to_vec()
}

fn s<'a>(v: &'a Value, k: &str) -> &'a str {
    v.as_dict().unwrap().get(k).unwrap().as_str().unwrap()
}

#[test]
fn audit_case_file_and_manifest_reproduce_byte_for_byte() {
    assert_eq!(check_audit(&repo()).unwrap(), 576);
}

#[test]
fn audit_cases_are_v1_rows_times_corners_times_chemistry() {
    let rows: BTreeMap<String, Value> = v1_n2_rows(&repo())
        .unwrap()
        .into_iter()
        .map(|r| {
            let id = |k: &str| s(&r, k).to_string();
            let k =
                [id("geometry_id"), id("bz_shape_id"), id("B_peak_id"), id("Vd_id"), id("mdot_id"), id("transport_id")]
                    .join("|");
            (k, r)
        })
        .collect();
    let mut keys = BTreeSet::new();
    let mut per_axis: BTreeMap<&str, BTreeSet<String>> = BTreeMap::new();
    for c in cases() {
        assert!(keys.insert(s(&c, "key").to_string()));
        let k =
            ["geometry_id", "bz_shape_id", "B_peak_id", "Vd_id", "mdot_id", "transport_id"].map(|f| s(&c, f)).join("|");
        let row = &rows[&k];
        for f in V1_FIELDS {
            assert_eq!(c.as_dict().unwrap().get(f), row.as_dict().unwrap().get(f), "{k} {f}");
        }
        for ax in [
            "geometry_id",
            "bz_shape_id",
            "B_peak_id",
            "Vd_id",
            "mdot_id",
            "transport_id",
            "composition_id",
            "chemistry_id",
        ] {
            per_axis.entry(ax).or_default().insert(s(&c, ax).to_string());
        }
        assert!(!c.as_dict().unwrap().contains_key("measured"), "no measured target");
        // NI-01: the feed splits the v1 mass flow by the corner's mass fractions.
        let mdot = c.as_dict().unwrap().get("mdot_kgps").unwrap().to_f64().unwrap();
        let feed = c.as_dict().unwrap().get("feed").unwrap().as_list().unwrap();
        let sum: f64 = feed.iter().map(|f| f.as_dict().unwrap().get("flow_rate_kg_s").unwrap().to_f64().unwrap()).sum();
        assert!((sum - mdot).abs() <= 1e-15 * mdot, "{k}: feed {sum} != {mdot}");
        let species: Vec<&str> = feed.iter().map(|f| s(f, "species")).collect();
        assert_eq!(species, ["N2", "N", "O2", "O"]);
    }
    let n = |ax: &str| per_axis[ax].len();
    assert_eq!(
        [n("geometry_id"), n("bz_shape_id"), n("B_peak_id"), n("Vd_id"), n("mdot_id"), n("transport_id")],
        [1, 1, 2, 2, 2, 9]
    );
    assert_eq!((n("composition_id"), n("chemistry_id")), (4, 2));
}

#[test]
fn composition_corners_and_inlet_rule() {
    let pts = composition_points(&repo()).unwrap();
    assert_eq!(pts.len(), 4);
    for p in &pts {
        let total: f64 = p.w.iter().map(|x| x.1).sum();
        assert!((total - 1.0).abs() < 1e-15, "{}: {total}", p.id);
        assert!(p.w.iter().all(|x| x.1 >= 0.0));
    }
    assert!(pts[0].y_o < 0.08 && pts[2].y_o > 0.83, "hull ends");
    assert_eq!(inlet_velocity("N2").unwrap(), 150.0);
    assert_eq!(inlet_velocity("N").unwrap(), 150.0 * 2.0_f64.sqrt());
    assert!((inlet_velocity("O2").unwrap() - 150.0 * (28.014_f64 / 31.998).sqrt()).abs() < 1e-12);
}

#[test]
fn snapshots_are_production_copies_without_assessed_processes() {
    check_snapshots(&repo()).unwrap();
    let man = pyjson::loads(&std::fs::read_to_string(repo().join(AUDIT_MANIFEST_REL)).unwrap()).unwrap();
    let set = abep_chem::hall_air::AirSet::load(&repo()).unwrap();
    for (_, cfg) in man.as_dict().unwrap().get("configs").unwrap().as_dict().unwrap().iter() {
        for (f, h) in cfg.as_dict().unwrap().get("rate_files").unwrap().as_dict().unwrap().iter() {
            assert_eq!(set.tables[f].sha256, h.as_str().unwrap(), "{f}");
        }
    }
}

#[test]
fn ambiguity_rule_is_literal() {
    assert_eq!(ambiguity_verdict(0.0, 0.009, 0.01), "EXCLUDE");
    assert_eq!(ambiguity_verdict(0.011, 0.5, 0.01), "PROMOTE");
    assert_eq!(ambiguity_verdict(0.0, 0.01, 0.01), "UNCERTAINTY VARIANT");
    assert_eq!(ambiguity_verdict(0.005, 0.02, 0.01), "UNCERTAINTY VARIANT");
}

fn sums(scale: f64, wall: f64) -> BTreeMap<String, f64> {
    let mut m: BTreeMap<String, f64> = SUM_KEYS.iter().map(|k| (k.to_string(), 1.0)).collect();
    for k in SUM_KEYS.iter().filter(|k| k.starts_with("R:")) {
        m.insert(k.to_string(), scale);
    }
    m.insert("W:HA-WALL-02".into(), wall);
    m.insert("W:HA-WALL-03".into(), wall);
    m
}

#[test]
fn metric_formulas_follow_addendum_01() {
    let h: BTreeMap<String, f64> =
        [("HA-O2-DI-02", 53.89), ("HA-N2N-R1", 47.4), ("HA-N2N-R2:nominal", 42.9), ("HA-N2N-R2:upper", 42.9)]
            .iter()
            .map(|(k, v)| (k.to_string(), *v))
            .collect();
    let s = sums(0.01, 0.5);
    let f = |p: &str, m: &str, mem: &str| metric(p, m, mem, &s, &h).unwrap();
    assert_eq!(f("HA-O2-DI-02", "F_ion", "nominal"), Some(0.01 / 1.01));
    assert_eq!(f("HA-O2-DI-02", "F_ion", "upper"), Some(1.1 * 0.01 / (1.0 + 1.1 * 0.01)));
    assert_eq!(f("HA-O2-ATT-01", "F_e_loss", "lower"), Some(0.8 * 0.01));
    assert_eq!(f("HA-WALL-02", "F_S(O destruction)", "lower"), Some(0.0));
    assert_eq!(f("HA-WALL-02", "F_S(O destruction)", "nominal"), None);
    assert_eq!(f("HA-WALL-02", "F_S(O destruction)", "upper"), Some(0.5 / 1.5));
    assert_eq!(f("HA-N2N-R3", "F_S(N2+ destruction)", "upper"), Some(1.11 * 0.01));
    assert!(metric("HA-IM-01", "F_S", "upper", &s, &h).is_err(), "no bound for an unbounded process");
}

fn synthetic_records(rate: f64, wall: f64, drop_corner: Option<&str>) -> BTreeMap<String, Value> {
    let mut out = BTreeMap::new();
    for c in cases() {
        let corner = s(&c, "composition_id").to_string();
        if drop_corner == Some(corner.as_str()) {
            continue;
        }
        let mut d = Dict::new();
        d.insert("key", Value::str(s(&c, "key")));
        d.insert("composition_id", Value::str(&corner));
        d.insert("tag", Value::str("SYNTHETIC_TEST_DATA_NOT_EVIDENCE"));
        for k in ["converged", "finite", "sustained"] {
            d.insert(k, Value::Bool(true));
        }
        d.insert("chemistry_unresolved_rate_files", Value::List(vec![]));
        d.insert("chemistry_extrapolated_fraction_max", Value::Float(0.0));
        d.insert("audit_domain_fraction_max", Value::Float(0.0));
        let mut sd = Dict::new();
        for (k, v) in sums(rate, wall) {
            sd.insert(k, Value::Float(v));
        }
        d.insert("sums", Value::Dict(sd));
        let mut hd = Dict::new();
        for k in ["HA-O2-DI-02", "HA-O2-ATT-01", "HA-N2N-R1", "HA-N2N-R2:nominal", "HA-N2N-R2:upper", "HA-N2N-R3"] {
            hd.insert(k, Value::Float(50.0));
        }
        d.insert("headers", Value::Dict(hd));
        let mut fm = Dict::new();
        let (s0, h0) = (sums(rate, wall), BTreeMap::from([("HA-O2-DI-02".to_string(), 50.0)]));
        let mut h1 = h0.clone();
        for k in ["HA-O2-ATT-01", "HA-N2N-R1", "HA-N2N-R2:nominal", "HA-N2N-R2:upper", "HA-N2N-R3"] {
            h1.insert(k.to_string(), 50.0);
        }
        for (p, m, _) in METRICS {
            for mem in ["lower", "nominal", "upper"] {
                if let Some(v) = metric(p, m, mem, &s0, &h1).unwrap() {
                    fm.insert(format!("{p}|{m}|{mem}"), Value::Float(v));
                }
            }
        }
        d.insert("frame_max", Value::Dict(fm));
        out.insert(s(&c, "key").to_string(), Value::Dict(d));
    }
    out
}

#[test]
fn verdicts_apply_the_rules_literally() {
    let r = repo();
    // Small bound-process rates, a large wall upper bound: every table process EXCLUDE, the wall processes UNCERTAINTY
    // VARIANT (gamma lower bound 0) -> not representable in the pinned solver.
    let v = verdicts(&r, &synthetic_records(1e-6, 10.0, None)).unwrap();
    let d = v.as_dict().unwrap();
    let pv = d.get("process_verdicts").unwrap().as_dict().unwrap();
    assert_eq!(pv.get("HA-O2-DI-02").unwrap().as_str(), Some("EXCLUDE"));
    assert_eq!(pv.get("HA-WALL-02").unwrap().as_str(), Some("UNCERTAINTY VARIANT"));
    assert_eq!(pv.get("HA-IM-01").unwrap().as_str(), Some("UNBOUNDED_OMISSION"));
    assert_eq!(d.get("set_outcome").unwrap().as_str(), Some("NOT_REPRESENTABLE_IN_PINNED_SOLVER"));
    assert_eq!(d.get("provisional").unwrap(), &Value::Bool(true), "tier-1 gaps are open");
    // All bounds below threshold: INCOMPLETE_EVIDENCE remains (unbounded omissions, provisional), never COMPLETE.
    let v = verdicts(&r, &synthetic_records(1e-6, 1e-6, None)).unwrap();
    assert_eq!(v.as_dict().unwrap().get("set_outcome").unwrap().as_str(), Some("INCOMPLETE_EVIDENCE"));
    // A corner without an eligible run: NOT_EVALUABLE.
    let v = verdicts(&r, &synthetic_records(1e-6, 1e-6, Some("CP-YHI-DIS"))).unwrap();
    assert_eq!(v.as_dict().unwrap().get("set_outcome").unwrap().as_str(), Some("NOT_EVALUABLE"));
}

#[test]
fn ineligible_runs_are_named() {
    let mut recs = synthetic_records(1e-6, 1e-6, None);
    let first = recs.values_mut().next().unwrap();
    assert!(ineligible(first).is_none());
    if let Value::Dict(d) = first {
        d.insert("audit_domain_fraction_max", Value::Float(1e-9));
    }
    assert!(ineligible(first).unwrap().contains("DOM-AIR-02"));
}
