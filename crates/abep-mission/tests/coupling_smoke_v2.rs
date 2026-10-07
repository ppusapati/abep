//! The registered SYNTHETIC coupling smoke case of the model-v2 chain (coupling_smoke_v2_registration_v1.json):
//! NP-ICP model_version 2 -> IF-ICP-THERMAL-v2 adapter -> NP-THERMAL 2.0.0 -> IF-ICP-BUS-v2 -> CONS-L1 v2. Every
//! IF-ICP-THERMAL-v2 energy key is booked exactly once end to end (no loss, no double count) to the registered closure
//! tolerances; a duplicated, renamed or dropped key, an unmapped status, a duplicated member and a double-booked share
//! or account are refused.

// The shared NP-THERMAL verification support of abep-subsystems (VS-NET, its 2.0.0 transformation, LS-01) and the
// registered smoke-case builder, compiled here: abep-mission already depends on both abep-icp and abep-subsystems, so
// neither physics crate gains a dependency (abep-subsystems INV-A05).
#[path = "../../abep-subsystems/tests/support/coupling_smoke.rs"]
mod coupling_smoke;
#[path = "../../abep-subsystems/tests/power_sys/mod.rs"]
mod power_sys;
#[path = "../../abep-subsystems/tests/support/mod.rs"]
mod support;

use abep_icp::v2::{IcpCaseV2, IcpModelV2, IcpResultV2};
use abep_provenance::{sha256_hex, workspace_repo_root};
use abep_subsystems::power::demand::Upstream;
use abep_subsystems::power::icp_bus::icp_upstream_loads_v2;
use abep_subsystems::power::ledger::{ledger, Ledger, LedgerArgs};
use abep_subsystems::power::slots::Slot;
use abep_subsystems::power::system_ledger::{accounts_from_thermal_v2, system_energy_ledger, Account};
use abep_subsystems::thermal::case::{InterfaceRecordV2, ThermalCase};
use abep_subsystems::thermal::icp_v2_adapter::{adapt, member_ids, AdapterContext};
use abep_subsystems::thermal::output::{RunStatus, ThermalOutput};
use abep_subsystems::thermal::vocab::{self, DepositionV2};
use abep_types::pyjson::{Dict, Value as PyValue};
use abep_types::EvalStatus;
use coupling_smoke as smoke;
use serde_json::{json, Value};
use std::sync::OnceLock;
use support::vs_net_v2::{gov_v2, run_v2, vs_net_v2};

const PRODUCER_TOL: f64 = 1e-10;

fn eps_if(x: f64) -> f64 {
    1e-6 * x.abs() + 1e-9
}

fn cons_i2_ok(got: f64, want: f64) -> bool {
    (got - want).abs() <= 1e-12 * want.abs() + 1e-12
}

fn case_file() -> &'static Value {
    static C: OnceLock<Value> = OnceLock::new();
    C.get_or_init(smoke::load_registered)
}

fn producer() -> &'static IcpResultV2 {
    static R: OnceLock<IcpResultV2> = OnceLock::new();
    R.get_or_init(|| {
        let m = IcpModelV2::load_workspace().expect("NP-ICP v1 and v2 locks verify");
        let c: IcpCaseV2 = serde_json::from_value(case_file()["icp_case"].clone()).expect("registered ICP case");
        m.evaluate(&c)
    })
}

fn producer_bytes() -> Vec<u8> {
    serde_json::to_vec(&serde_json::to_value(&producer().if_icp_thermal_v2).unwrap()).unwrap()
}

fn ctx() -> AdapterContext {
    let t = &case_file()["thermal"];
    AdapterContext {
        case_id: t["case_id"].as_str().unwrap().into(),
        case_class: "SYNTHETIC_VERIFICATION".into(),
        supply_mode: "AIR_PRIMARY".into(),
        design_state_id: None,
        operating_point_id: t["operating_point_id"].as_str().unwrap().into(),
    }
}

/// VS-NET 2.0.0 (registered transformation) with the case's f_up, its TK-06 split and the adapted record.
fn thermal_case(rec: InterfaceRecordV2) -> ThermalCase {
    let t = &case_file()["thermal"];
    let mut c = vs_net_v2(
        t["case_id"].as_str().unwrap(),
        t["match_colocated"].as_bool().unwrap(),
        t["sinks_K"].as_f64().unwrap(),
    );
    let fup = c.records.iter_mut().find(|r| r.id.as_deref() == Some("PART.f_up")).unwrap();
    fup.value = Some(json!({ "weights": t["f_up"] }));
    let mut split = c.records.iter().find(|r| r.id.as_deref() == Some("PART.f_up")).unwrap().clone();
    split.id = Some("PART.coil_smoke".into());
    split.value = Some(json!({ "weights": t["tk06_split"] }));
    c.records.push(split);
    c.partitions.insert("Q_icp_coil_ohmic_W".into(), "PART.coil_smoke".into());
    c.interfaces.icp_v2 = Some(rec);
    c
}

fn ledger_with(loads: &[(Slot, f64)]) -> Ledger {
    let b = &case_file()["bus_ledger"];
    let mut l = Dict::new();
    let mut e = Dict::new();
    for (s, p, eff) in power_sys::LS_01 {
        let p = match (s, loads.iter().find(|x| x.0 == s)) {
            (_, Some((_, v))) => *v,
            (Slot::ThermalControl, _) => b["thermal_control_W"].as_f64().unwrap(),
            _ => p,
        };
        let eff = b["eta_slot"].get(s.name()).and_then(Value::as_f64).unwrap_or(eff);
        let mut d = Dict::new();
        d.insert("P_W", PyValue::Float(p));
        d.insert("evidence_class", PyValue::str("assumed"));
        d.insert("source", PyValue::str(power_sys::SYN));
        if s == Slot::IcpRfSource {
            d.insert("plane", PyValue::str("generator_dc_input"));
        }
        l.insert(s.name(), PyValue::Dict(d));
        let mut f = Dict::new();
        f.insert("value", PyValue::Float(eff));
        f.insert("evidence_class", PyValue::str("assumed"));
        f.insert("source", PyValue::str(power_sys::SYN));
        f.insert("path", PyValue::str("internal_bus"));
        e.insert(s.name(), PyValue::Dict(f));
    }
    let mut fe = Dict::new();
    fe.insert("value", PyValue::Float(b["eta_front_end"].as_f64().unwrap()));
    fe.insert("evidence_class", PyValue::str("assumed"));
    fe.insert("source", PyValue::str(power_sys::SYN));
    let mut a = LedgerArgs::new(PyValue::Dict(l), PyValue::Dict(e), PyValue::Dict(fe));
    a.label = PyValue::str("COUPLING-SMOKE-v2");
    ledger(&a).expect("valid ledger")
}

/// Every destination of key `k` in a 2.0.0 output: (deposited on nodes, exported, booked).
fn destinations(o: &ThermalOutput, k: &str) -> (f64, f64, f64) {
    let r = o.results.as_ref().unwrap();
    let dep: f64 = r.q_source_node_w.values().filter_map(|m| m.get(k)).sum();
    let exp: f64 =
        [k.to_string(), format!("{k}.EXPORT")].iter().filter_map(|x| r.p_exported_w.get(x)).map(|v| v[0]).sum();
    let bk: f64 =
        r.q_boundary_w.b_ppu_rf_booked.iter().filter(|(x, _)| x.rsplit(':').next() == Some(k)).map(|(_, v)| v[0]).sum();
    (dep, exp, bk)
}

#[test]
fn smoke_case_file_is_the_registered_builder_output() {
    let root = workspace_repo_root().unwrap();
    let bytes = std::fs::read(root.join(smoke::CASE_REL_PATH)).unwrap();
    let reg: Value = serde_json::from_slice(&std::fs::read(root.join(smoke::REGISTRATION_REL_PATH)).unwrap()).unwrap();
    assert_eq!(reg["case_sha256"].as_str().unwrap(), sha256_hex(&bytes));
    assert_eq!(reg["label"], "SYNTHETIC");
    assert_eq!(bytes, smoke::to_bytes(&smoke::build()), "the builder no longer reproduces the registered case");
    let vs = std::fs::read(root.join(support::vs_net::VS_NET_REL_PATH)).unwrap();
    assert_eq!(case_file()["thermal"]["network_sha256"].as_str().unwrap(), sha256_hex(&vs));
}

#[test]
fn every_energy_key_is_booked_exactly_once_end_to_end() {
    let p = producer();
    assert_eq!(p.status, abep_icp::IcpStatus::Converged, "{:?}", p.reasons);
    assert!(p.flags.contains("SYNTHETIC_TEST_ONLY"));
    let bytes = producer_bytes();
    let ids = member_ids(&bytes).unwrap();
    assert_eq!(ids.len(), p.if_icp_thermal_v2.members.len());
    for id in &ids {
        let pm = p.member(id);
        // Producer closures (CC-05 / CC-06 / CONS-I3 v2).
        for ck in &pm.closures {
            assert_eq!(ck.status, abep_icp::IcpStatus::Converged, "{id} {}: {ck:?}", ck.id);
            if let (Some(v), Some(t)) = (ck.value, ck.tolerance) {
                if t == PRODUCER_TOL {
                    assert!(v <= PRODUCER_TOL, "{id} {}", ck.id);
                }
            }
        }
        // Adapter: CONVERGED -> EVALUATED, evidence SYNTHETIC; the producer's TK-06 split equals the consumer's.
        let ad = adapt(&bytes, id, &ctx(), gov_v2()).unwrap();
        assert!(ad.record.keys.values().all(|v| v.status.as_deref() == Some("EVALUATED")));
        assert!(ad.record.keys.values().all(|v| v.evidence_class.as_deref() == Some(support::SYN)));
        let split = ad.producer_coil_split.clone().expect("registered split echoed by the producer");
        for (n, w) in case_file()["thermal"]["tk06_split"].as_object().unwrap() {
            assert!((split[n] - w.as_f64().unwrap()).abs() <= 1e-15, "{n}");
        }
        // Thermal 2.0.0.
        let o = run_v2(&thermal_case(ad.record.clone()));
        assert_eq!(o.run_status, RunStatus::Converged, "{id}: {:#?}", o.status_reasons);
        let r = o.results.as_ref().unwrap();
        assert!(r.energy_balance.checks.iter().filter(|c| c.id.starts_with("CONS-I")).count() == 2);
        assert!(r.energy_balance.checks.iter().all(|c| c.met), "{:?}", r.energy_balance.checks);
        // Exactly once per key, and nowhere else.
        let pv = |k: &str| pm.keys[k].q.value.unwrap();
        let mut total = 0.0;
        for row in vocab::ICP_V2_KEYS
            .iter()
            .filter(|x| !matches!(x.deposition, DepositionV2::Reference | DepositionV2::Variant { .. }))
        {
            let (d, e, b) = destinations(&o, row.key);
            assert!(cons_i2_ok(d + e + b, pv(row.key)), "{id} {}: {d} + {e} + {b} != {}", row.id, pv(row.key));
            total += d + e + b;
        }
        for (node, m) in &r.q_source_node_w {
            for k in m.keys().filter(|k| k.starts_with("Q_icp") || k.starts_with("P_icp")) {
                assert!(vocab::icp_v2_key(k).is_some(), "{node}: unregistered ICP label {k}");
            }
        }
        let slot_sum = pv("P_icp_slot_load_sum_W");
        assert!((total - slot_sum).abs() <= eps_if(slot_sum), "no loss / double count: {total} vs {slot_sum}");
        assert!((total - slot_sum).abs() <= PRODUCER_TOL * slot_sum);
        // IF-ICP-BUS-v2 of the same solve member -> the ledger, exactly at the load planes.
        let bus = p.if_icp_bus_v2.iter().find(|b| b.solve_member_id == pm.solve_member_id).unwrap();
        let loads =
            icp_upstream_loads_v2(&serde_json::to_value(bus).unwrap(), &[], "assumed", smoke::ID, false).unwrap();
        let lv: Vec<(Slot, f64)> = loads
            .iter()
            .map(|(s, u)| match u {
                Upstream::Evaluated { p_w, .. } => (*s, *p_w),
                u => panic!("{u:?}"),
            })
            .collect();
        for (s, k) in [
            (Slot::IcpRfSource, "P_icp_rf_source_DC_W"),
            (Slot::IcpMatchingNetwork, "P_icp_matching_DC_W"),
            (Slot::IcpCollectorBias, "P_icp_collector_bias_W"),
        ] {
            assert_eq!(
                lv.iter().find(|x| x.0 == s).unwrap().1,
                pv(k),
                "{k}: the bus and thermal records carry the same watt"
            );
        }
        let led = ledger_with(&lv);
        let mut accounts = accounts_from_thermal_v2(&o);
        accounts.extend(power_sys::externals());
        let s = system_energy_ledger(&led, &accounts);
        assert_eq!(s.status, EvalStatus::Evaluated, "{:?}", s.reasons);
        let row = s.rows.iter().find(|x| x.account_id == "ICP").unwrap();
        assert!((row.ledger_w - slot_sum).abs() <= PRODUCER_TOL * slot_sum, "ledger load planes {}", row.ledger_w);
        assert!(row.mismatch_w.abs() <= PRODUCER_TOL * slot_sum, "ICP account mismatch {}", row.mismatch_w);
        assert!(s.relative_residual.unwrap() < 0.02);
    }
}

fn first_member() -> String {
    member_ids(&producer_bytes()).unwrap().remove(0)
}

#[test]
fn the_adapter_refuses_a_duplicated_renamed_or_dropped_key_and_an_unmapped_status() {
    let id = first_member();
    let base: Value = serde_json::from_slice(&producer_bytes()).unwrap();
    let text = serde_json::to_string(&base).unwrap();
    let entry = serde_json::to_string(&base["members"][0]["keys"]["Q_icp_line_W"]).unwrap();
    let needle = format!("\"Q_icp_line_W\":{entry}");
    assert!(text.contains(&needle));
    // A duplicated JSON key.
    let dup = text.replacen(&needle, &format!("{needle},{needle}"), 1);
    let e = adapt(dup.as_bytes(), &id, &ctx(), gov_v2()).unwrap_err();
    assert!(e.contains("duplicated key"), "{e}");
    let edit = |f: &dyn Fn(&mut Value)| {
        let mut v = base.clone();
        f(&mut v);
        serde_json::to_vec(&v).unwrap()
    };
    // The same watt under a second name (same id).
    let b = edit(&|v| {
        let x = v["members"][0]["keys"]["Q_icp_line_W"].clone();
        v["members"][0]["keys"]["Q_icp_line_dup_W"] = x;
    });
    assert!(adapt(&b, &id, &ctx(), gov_v2()).unwrap_err().contains("not in the locked key table"));
    // A dropped key.
    let b = edit(&|v| {
        v["members"][0]["keys"].as_object_mut().unwrap().remove("Q_icp_match_W");
    });
    assert!(adapt(&b, &id, &ctx(), gov_v2()).unwrap_err().contains("dropped"));
    // An unmapped status, a CONVERGED key without a value, a withheld key with a value, a row mismatch.
    for (k, f, want) in [
        ("status", json!("VALIDATED_BENCH"), "no registered mapping"),
        ("value", Value::Null, "without a finite value"),
        ("powered_by", json!("HALL_DISCHARGE"), "differ from the locked row"),
    ] {
        let b = edit(&|v| v["members"][0]["keys"]["Q_icp_plasma_wall_W"][k] = f.clone());
        assert!(adapt(&b, &id, &ctx(), gov_v2()).unwrap_err().contains(want), "{k}");
    }
    let b = edit(&|v| {
        v["members"][0]["keys"]["Q_icp_line_W"]["status"] = json!("NOT_EVALUATED");
    });
    assert!(adapt(&b, &id, &ctx(), gov_v2()).unwrap_err().contains("carries a value"));
    // A duplicated scenario member; a v1 interface; another producer lock.
    let b = edit(&|v| {
        let m = v["members"][0].clone();
        v["members"].as_array_mut().unwrap().push(m);
    });
    assert!(member_ids(&b).is_err());
    assert!(adapt(&b, &id, &ctx(), gov_v2()).unwrap_err().contains("appears 2 times"));
    let b = edit(&|v| v["interface"] = json!("IF-ICP-THERMAL-v1"));
    assert!(adapt(&b, &id, &ctx(), gov_v2()).is_err());
    let b = edit(&|v| v["producer_lock_sha256"] = json!("0".repeat(64)));
    assert!(adapt(&b, &id, &ctx(), gov_v2()).is_err());
    // A withheld producer key maps to its own status (no zero-fill) and propagates in the consumer.
    let b = edit(&|v| {
        let k = &mut v["members"][0]["keys"]["Q_icp_radiation_W"];
        k["status"] = json!("INCOMPLETE_EVIDENCE");
        k["value"] = Value::Null;
    });
    let ad = adapt(&b, &id, &ctx(), gov_v2()).unwrap();
    assert_eq!(ad.record.keys["Q_icp_radiation_W"].status.as_deref(), Some("INCOMPLETE_EVIDENCE"));
    let o = run_v2(&thermal_case(ad.record));
    assert_eq!(o.run_status, RunStatus::IncompleteEvidence);
}

#[test]
fn a_double_booked_watt_is_refused_downstream() {
    let id = first_member();
    let ad = adapt(&producer_bytes(), &id, &ctx(), gov_v2()).unwrap();
    // A plasma-wall share booked on a second node too: the shares no longer sum to the key (IFI2-08).
    let mut rec = ad.record.clone();
    let shares = rec.node_shares_w.get_mut("Q_icp_plasma_wall_W").unwrap();
    let v = shares["N_VESSEL"].clone();
    shares.insert("N_HOUSING".into(), v);
    let o = run_v2(&thermal_case(rec));
    assert_eq!(o.run_status, RunStatus::ModelError);
    assert!(o.status_reasons.iter().any(|r| r.code == "IFI2-08_VIOLATED"));
    // A key counted twice inside the identities (its value doubled): IFI2-04 refuses.
    let mut rec = ad.record.clone();
    let k = rec.keys.get_mut("Q_icp_line_W").unwrap();
    let x = k.value.as_ref().unwrap().as_f64().unwrap();
    k.value = Some(json!(2.0 * x));
    let o = run_v2(&thermal_case(rec));
    assert_eq!(o.run_status, RunStatus::ModelError);
    // The ICP slots claimed by two accounts in CONS-L1 (CONS-L1_DOUBLE_COUNT).
    let o = run_v2(&thermal_case(ad.record));
    let mut accounts = accounts_from_thermal_v2(&o);
    accounts.extend(power_sys::externals());
    let icp: Account = accounts.iter().find(|a| a.account_id == "ICP").unwrap().clone();
    accounts.push(Account { account_id: "ICP_AGAIN".into(), ..icp });
    let p = producer();
    let bus = p.if_icp_bus_v2.iter().find(|b| b.solve_member_id == p.member(&id).solve_member_id).unwrap();
    let loads = icp_upstream_loads_v2(&serde_json::to_value(bus).unwrap(), &[], "assumed", smoke::ID, false).unwrap();
    let lv: Vec<(Slot, f64)> = loads
        .iter()
        .filter_map(|(s, u)| if let Upstream::Evaluated { p_w, .. } = u { Some((*s, *p_w)) } else { None })
        .collect();
    let s = system_energy_ledger(&ledger_with(&lv), &accounts);
    assert_eq!(s.status, EvalStatus::ModelError);
    assert!(s.reasons.iter().any(|r| r.starts_with("CONS-L1_DOUBLE_COUNT")));
}
