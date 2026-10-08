//! A9.38 P6 power-closure record: byte-identical regeneration of the committed record, no TBD term at any point and
//! the arithmetic the record states (margins, discharge ceilings, loss decomposition).

use abep_assess::power_closure::{power_closure_record, RECORD_REL};
use abep_assess::thresholds::Thresholds;
use abep_subsystems::power::allocation::DESIGN_ALLOCATION_W;
use abep_subsystems::power::closure_v1::{evaluate_point, ClosureInputs, Corner};
use abep_subsystems::power::official::{official_flight_ledger, MassPowerA9V5};
use abep_types::pyjson::{dumps_config_file, Value};

fn repo() -> std::path::PathBuf {
    abep_provenance::workspace_repo_root().unwrap()
}

fn num(v: &Value, path: &[&str]) -> f64 {
    let mut x = v;
    for k in path {
        x = x.as_dict().and_then(|d| d.get(k)).unwrap_or_else(|| panic!("{k} missing"));
    }
    x.to_f64().unwrap()
}

#[test]
fn committed_record_regenerates_byte_for_byte() {
    let root = repo();
    let th = Thresholds::workspace().unwrap();
    let rec = power_closure_record(&root, &th).unwrap();
    let bytes = dumps_config_file(&rec).unwrap();
    let committed = std::fs::read(root.join(RECORD_REL)).unwrap();
    assert!(bytes == committed, "{RECORD_REL} is stale: run abep-assess-power-closure");
}

#[test]
fn every_point_is_complete_and_the_margins_are_the_ledger_differences() {
    let root = repo();
    let th = Thresholds::workspace().unwrap();
    let hc03 = th.limit("HC-03").unwrap();
    let rec = power_closure_record(&root, &th).unwrap();
    let pts = rec.as_dict().unwrap().get("points").unwrap().as_list().unwrap();
    assert_eq!(pts.len(), 5);
    for p in pts {
        let led = p.as_dict().unwrap().get("ledger").unwrap();
        assert_eq!(led.as_dict().unwrap().get("status").unwrap().as_str(), Some("COMPLETE"));
        assert!(led.as_dict().unwrap().get("tbd").unwrap().as_list().unwrap().is_empty());
        let pb = num(p, &["P_bus_W"]);
        assert_eq!(num(p, &["margin_to_rfp_W"]), hc03 - pb);
        assert_eq!(num(p, &["margin_to_design_allocation_W"]), DESIGN_ALLOCATION_W - pb);
    }
    // The official A9-02 ledger still has its TBD terms (the closure is additive).
    let mp = MassPowerA9V5::load(&root).unwrap();
    assert!(!official_flight_ledger(&mp).unwrap().tbd.is_empty());
}

#[test]
fn discharge_ceiling_reproduces_the_limit() {
    let root = repo();
    let inp = ClosureInputs::load(&root).unwrap();
    let hc03 = Thresholds::workspace().unwrap().limit("HC-03").unwrap();
    for id in ["P-12", "P-25", "P-WORST", "P-XE"] {
        let r = evaluate_point(&inp, id, Corner::Reference, &[]).unwrap();
        for lim in [DESIGN_ALLOCATION_W, hc03] {
            let pd = r.discharge_ceiling(lim);
            let p_bus = r.p_bus_non_discharge_w + pd / r.discharge_chain_eta;
            assert!((p_bus - lim).abs() < 1e-9, "{id} {lim}: {p_bus}");
        }
        // the conservative corner never allows more discharge power than the reference
        let c = evaluate_point(&inp, id, Corner::Conservative, &[]).unwrap();
        let f = evaluate_point(&inp, id, Corner::Favourable, &[]).unwrap();
        assert!(c.discharge_ceiling(hc03) < r.discharge_ceiling(hc03));
        assert!(f.discharge_ceiling(hc03) > r.discharge_ceiling(hc03));
    }
}

#[test]
fn rf_forward_power_moves_only_the_icp_group() {
    let root = repo();
    let inp = ClosureInputs::load(&root).unwrap();
    let a = evaluate_point(&inp, "P-12", Corner::Reference, &[("RF-PFWD", 100.0)]).unwrap();
    let b = evaluate_point(&inp, "P-12", Corner::Reference, &[("RF-PFWD", 300.0)]).unwrap();
    let eta_gen = inp.term("ETA-RFGEN").unwrap().value;
    let (cv, hv) = inp.slot_eta(abep_subsystems::power::slots::Slot::IcpRfSource, Corner::Reference).unwrap();
    let fe = inp.term("ETA-FE").unwrap().value;
    let expect = 200.0 / eta_gen / (cv * hv) / fe;
    assert!(((b.p_bus_non_discharge_w - a.p_bus_non_discharge_w) - expect).abs() < 1e-9);
}
