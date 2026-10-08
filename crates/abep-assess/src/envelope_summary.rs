//! Compact summary of an ingested NP-HALL-PARAMETRIC-ENVELOPE envelope (layer (a), PARAMETRIC / NOT_VALIDATED): run
//! status counts, PASS ranges of thrust / I_d / P_d, and the number of points passing the preregistered Hall point tests
//! broken down by geometry, B(z) shape, transport candidate and hardware (geometry, shape). Raw quantities with labels;
//! no classification (that is `closure`).

use crate::closure::{point_passes, HallLimits, HallTest};
use abep_hall::envelope::{self as env, Envelope, EnvelopePoint, Family, RunStatus};
use abep_types::pyjson::{Dict, Value};
use std::collections::BTreeMap;

fn s(x: &str) -> Value {
    Value::str(x)
}

fn dict(pairs: Vec<(&str, Value)>) -> Value {
    let mut d = Dict::new();
    for (k, v) in pairs {
        d.insert(k, v);
    }
    Value::Dict(d)
}

fn range(pts: &[&EnvelopePoint], f: fn(&EnvelopePoint) -> Option<f64>) -> Value {
    let v: Vec<f64> = pts.iter().filter_map(|p| f(p)).collect();
    if v.is_empty() {
        return Value::Null;
    }
    let mn = v.iter().cloned().fold(f64::INFINITY, f64::min);
    let mx = v.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    dict(vec![("min", Value::Float(mn)), ("max", Value::Float(mx))])
}

/// The point tests reported for a family: the family's preregistered tests, plus for XE the AIR thrust thresholds as
/// information only (they are not XE tests).
fn tests(f: Family) -> Vec<(HallTest, &'static str)> {
    match f {
        Family::Xe => vec![
            (HallTest::XeFunc, "XE_FUNC"),
            (HallTest::T12, "INFO_T_GE_HC01_AT_PBUS"),
            (HallTest::T25, "INFO_T_GE_HC02_AT_PBUS"),
        ],
        Family::N2Proxy => vec![(HallTest::T12, "N2_PROXY_T12_DIAGNOSTIC"), (HallTest::T25, "N2_PROXY_T25_DIAGNOSTIC")],
    }
}

fn group(pts: &[&EnvelopePoint], f: Family, lim: &HallLimits) -> Value {
    let mut d = Dict::new();
    for (k, n) in RunStatus::ALL.iter().map(|st| (st.as_str(), pts.iter().filter(|p| p.status == *st).count())) {
        d.insert(k, Value::int(n as i64));
    }
    for (t, name) in tests(f) {
        d.insert(name, Value::int(pts.iter().filter(|p| point_passes(t, p, lim)).count() as i64));
    }
    Value::Dict(d)
}

fn breakdown(pts: &[&EnvelopePoint], f: Family, lim: &HallLimits, key: fn(&EnvelopePoint) -> String) -> Value {
    let mut by: BTreeMap<String, Vec<&EnvelopePoint>> = BTreeMap::new();
    for p in pts {
        by.entry(key(p)).or_default().push(p);
    }
    let mut d = Dict::new();
    for (k, v) in by {
        d.insert(k, group(&v, f, lim));
    }
    Value::Dict(d)
}

/// The summary of one family of an ingested envelope.
pub fn family_summary(e: &Envelope, f: Family, lim: &HallLimits) -> Value {
    let pts: Vec<&EnvelopePoint> = e.family_points(f).collect();
    if pts.is_empty() {
        return dict(vec![("status", s("NOT_RUN")), ("n_points", Value::int(0))]);
    }
    let pass: Vec<&EnvelopePoint> = pts.iter().copied().filter(|p| p.status == RunStatus::Pass).collect();
    let best = |t: HallTest| {
        pts.iter()
            .copied()
            .filter(|p| point_passes(t, p, lim))
            .max_by(|a, b| a.thrust_n.partial_cmp(&b.thrust_n).unwrap_or(std::cmp::Ordering::Equal))
            .map_or(Value::Null, |p| {
                dict(vec![
                    ("key", s(&p.case.key)),
                    ("thrust_N", p.thrust_n.map_or(Value::Null, Value::Float)),
                    ("discharge_power_W", p.discharge_power_w.map_or(Value::Null, Value::Float)),
                    ("discharge_current_A", p.discharge_current_a.map_or(Value::Null, Value::Float)),
                ])
            })
    };
    let mut best_d = Dict::new();
    for (t, name) in tests(f) {
        best_d.insert(name, best(t));
    }
    dict(vec![
        ("labels", Value::List(f.labels().iter().map(|l| s(l)).collect())),
        ("n_points", Value::int(pts.len() as i64)),
        ("all", group(&pts, f, lim)),
        ("pass_thrust_N", range(&pass, |p| p.thrust_n)),
        ("pass_discharge_current_A", range(&pass, |p| p.discharge_current_a)),
        ("pass_discharge_power_W", range(&pass, |p| p.discharge_power_w)),
        ("pass_Te_max_eV", range(&pass, |p| p.te_max_ev)),
        ("max_thrust_point_by_test", Value::Dict(best_d)),
        ("by_geometry", breakdown(&pts, f, lim, |p| p.case.geometry_id.clone())),
        ("by_bz_shape", breakdown(&pts, f, lim, |p| p.case.bz_shape_id.clone())),
        ("by_transport", breakdown(&pts, f, lim, |p| p.case.transport_id.clone())),
        ("by_B_peak", breakdown(&pts, f, lim, |p| p.case.b_peak_id.clone())),
        ("by_V_d", breakdown(&pts, f, lim, |p| p.case.vd_id.clone())),
        ("by_mdot", breakdown(&pts, f, lim, |p| p.case.mdot_id.clone())),
        ("by_hardware", breakdown(&pts, f, lim, |p| format!("{}|{}", p.case.geometry_id, p.case.bz_shape_id))),
    ])
}

/// The summary record of an ingested envelope.
pub fn summary(e: &Envelope, lim: &HallLimits) -> Value {
    let mut fams = Dict::new();
    for f in Family::ALL {
        fams.insert(f.as_str(), family_summary(e, f, lim));
    }
    dict(vec![
        ("schema", s("abep_assess_hall_parametric_envelope_summary_v1")),
        ("model_id", s("NP-HALL-PARAMETRIC-ENVELOPE")),
        ("layer", s(env::LAYER_A_LABEL)),
        ("status_label", s("PARAMETRIC / NOT_VALIDATED: raw envelope quantities, not a classification")),
        ("manifest_sha256", s(&e.manifest_sha256)),
        ("raw_sha256", s(&e.raw_sha256)),
        ("cases_sha256", s(&e.cases_sha256)),
        ("bz_family_kind", s(e.bz_family_kind.as_str())),
        (
            "limits",
            dict(vec![
                ("thrust_min_N_HC01", Value::Float(lim.thrust_min_n)),
                ("thrust_capability_N_HC02", Value::Float(lim.thrust_capability_n)),
                ("p_bus_max_W_HC03", Value::Float(lim.p_bus_max_w)),
                ("p_non_hall_lower_bound_W", Value::Float(lim.p_non_hall_lb_w)),
            ]),
        ),
        (
            "tests",
            s("XE_FUNC = PASS, T > 0, P_d + P_nonHall,LB < HC-03 (prereg); INFO_T_GE_HC01 / HC02_AT_PBUS = T >= HC-01 / HC-02 at the same power test, information only for XE (T12 / T25 are AIR tests)"),
        ),
        ("families", Value::Dict(fams)),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;
    use abep_hall::envelope::{BzFamilyKind, CaseInfo};

    fn pt(g: &str, status: RunStatus, t: f64, pd: f64) -> EnvelopePoint {
        let pass = status == RunStatus::Pass;
        EnvelopePoint {
            case: CaseInfo {
                key: format!("XE|{g}|BZ|BP|VD|MF|T"),
                family: Family::Xe,
                geometry_id: g.into(),
                bz_shape_id: "BZ".into(),
                b_peak_id: "BP".into(),
                vd_id: "VD".into(),
                mdot_id: "MF".into(),
                transport_id: "T".into(),
                vd_v: 300.0,
                mdot_kg_s: 1e-6,
                b_peak_t: 0.01,
                case_sha256: "x".into(),
            },
            status,
            thrust_n: pass.then_some(t),
            discharge_power_w: pass.then_some(pd),
            discharge_current_a: pass.then_some(pd / 300.0),
            ion_current_a: None,
            te_max_ev: None,
        }
    }

    fn n(d: &Dict, k: &str) -> i64 {
        match d.get(k) {
            Some(Value::Int(i)) => i.as_i64().unwrap(),
            other => panic!("{k}: {other:?}"),
        }
    }

    #[test]
    fn counts_and_breakdowns() {
        let e = Envelope {
            manifest_rel: "m".into(),
            manifest_sha256: "a".into(),
            raw_sha256: "b".into(),
            cases_sha256: "c".into(),
            bz_family_kind: BzFamilyKind::SourcedSurrogate,
            points: vec![
                pt("G1", RunStatus::Pass, 0.030, 900.0),
                pt("G1", RunStatus::Pass, 0.030, 1600.0),
                pt("G2", RunStatus::Pass, 0.005, 100.0),
                pt("G2", RunStatus::NumericalFailure, 0.0, 0.0),
            ],
        };
        let lim =
            HallLimits { thrust_min_n: 0.012, thrust_capability_n: 0.025, p_bus_max_w: 1500.0, p_non_hall_lb_w: 0.0 };
        let v = summary(&e, &lim);
        let fam = v.as_dict().unwrap().get("families").unwrap().as_dict().unwrap();
        let xe = fam.get("XE").unwrap().as_dict().unwrap();
        let all = xe.get("all").unwrap().as_dict().unwrap();
        assert_eq!(n(all, "PASS"), 3);
        assert_eq!(n(all, "NUMERICAL_FAILURE"), 1);
        assert_eq!(n(all, "XE_FUNC"), 2, "the 1600 W point fails the bus test");
        assert_eq!(n(all, "INFO_T_GE_HC02_AT_PBUS"), 1);
        let g2 = xe.get("by_geometry").unwrap().as_dict().unwrap().get("G2").unwrap().as_dict().unwrap();
        assert_eq!(n(g2, "INFO_T_GE_HC01_AT_PBUS"), 0);
        assert_eq!(fam.get("N2_PROXY").unwrap().as_dict().unwrap().get("status").unwrap().as_str(), Some("NOT_RUN"));
    }
}
