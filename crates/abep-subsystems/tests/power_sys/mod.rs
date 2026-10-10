//! CONS-L1 system cases SYS-01..SYS-08 (contract PARITY-C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY-V1, conservation_checks):
//! the registered VS-NET thermal network solved steady (the NP-THERMAL verification's `vs_net_loaded_steady`), paired
//! with the synthetic bus ledger LS-01, reconciled by the system energy ledger. Every input is
//! SYNTHETIC_TEST_DATA_NOT_EVIDENCE. Shared by `tests/power_system_ledger.rs` and `examples/power_cons_l1.rs`.
#![allow(dead_code)]

use crate::support::verify::vs_net_loaded_steady;
use crate::support::{run, vs_net};
use abep_subsystems::power::ledger::{ledger, Ledger, LedgerArgs};
use abep_subsystems::power::official::{official_flight_ledger, MassPowerA9V5};
use abep_subsystems::power::slots::Slot;
use abep_subsystems::power::system_ledger::{
    accounts_from_thermal, system_energy_ledger, Account, Plane, SystemLedger,
};
use abep_subsystems::thermal::output::ThermalOutput;
use abep_types::pyjson::{Dict, Value};
use abep_types::EvalStatus;
use serde_json::json;

pub const SYN: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE: CONS-L1 LS-01";
/// VS-NET sink temperature of the NP-THERMAL verification's loaded steady solve.
pub const VS_NET_SINK_K: f64 = 250.0;

/// LS-01 rows: (slot, P_W, supply efficiency); every slot internal_bus, front end 0.96.
pub const LS_01: [(Slot, f64, f64); 13] = [
    (Slot::HallDischarge, 600.0, 0.95),
    (Slot::HallMagnetInner, 6.0, 0.9),
    (Slot::HallMagnetOuter, 9.0, 0.9),
    (Slot::HallMagnetTrim, 2.0, 0.9),
    (Slot::IcpRfSource, 45.0, 1.0),
    (Slot::IcpMatchingNetwork, 2.0, 1.0),
    (Slot::IcpCollectorBias, 6.4, 0.8),
    (Slot::FlowControlAtmospheric, 3.0, 0.9),
    (Slot::FlowControlXe, 2.0, 0.9),
    (Slot::Compressor, 40.0, 0.92),
    (Slot::ThermalControl, 0.0, 0.9),
    (Slot::HousekeepingControls, 25.0, 0.85),
    (Slot::ReservedDcPort, 0.0, 0.9),
];

pub const ICP_PLANES: [(Slot, Plane); 3] = [
    (Slot::IcpRfSource, Plane::Load),
    (Slot::IcpMatchingNetwork, Plane::Load),
    (Slot::IcpCollectorBias, Plane::SupplyInput),
];

/// LS-01 with the Hall discharge and thermal-control loads given.
pub fn ls_ledger_with(hall_discharge_w: f64, thermal_control_w: f64) -> Ledger {
    let mut loads = Dict::new();
    let mut effs = Dict::new();
    for (s, p, e) in LS_01 {
        let p = match s {
            Slot::HallDischarge => hall_discharge_w,
            Slot::ThermalControl => thermal_control_w,
            _ => p,
        };
        let mut l = Dict::new();
        l.insert("P_W", Value::Float(p));
        l.insert("evidence_class", Value::str("assumed"));
        l.insert("source", Value::str(SYN));
        if s == Slot::IcpRfSource {
            l.insert("plane", Value::str("generator_dc_input"));
        }
        loads.insert(s.name(), Value::Dict(l));
        let mut f = Dict::new();
        f.insert("value", Value::Float(e));
        f.insert("evidence_class", Value::str("assumed"));
        f.insert("source", Value::str(SYN));
        f.insert("path", Value::str("internal_bus"));
        effs.insert(s.name(), Value::Dict(f));
    }
    let mut fe = Dict::new();
    fe.insert("value", Value::Float(0.96));
    fe.insert("evidence_class", Value::str("assumed"));
    fe.insert("source", Value::str(SYN));
    let mut a = LedgerArgs::new(Value::Dict(loads), Value::Dict(effs), Value::Dict(fe));
    a.label = Value::str("LS-01");
    ledger(&a).expect("LS-01 is a valid ledger")
}

/// The registered LS-01 (thermal_control 0.0 W).
pub fn ls_ledger(hall_discharge_w: f64) -> Ledger {
    ls_ledger_with(hall_discharge_w, 0.0)
}

/// VS-NET's registered thermal-control load (Q_thermal_control_W, total over its nodes).
pub const VS_NET_THERMAL_CONTROL_W: f64 = 3.0;

/// SYS-01b, not registered (demonstration added after the registration): LS-01 with the thermal-control slot carrying
/// VS-NET's 3 W, so that every bus slot with a thermal account matches the thermal model's booked flows.
pub fn sys_01b(steady: &ThermalOutput) -> SystemLedger {
    system_energy_ledger(&ls_ledger_with(600.0, VS_NET_THERMAL_CONTROL_W), &accounts(steady))
}

pub fn external(id: &str, slots: &[Slot], deposited: f64) -> Account {
    Account {
        account_id: id.into(),
        slots: slots.iter().map(|s| (*s, Plane::Load)).collect(),
        deposited_w: deposited,
        exported_w: 0.0,
        booked_w: 0.0,
        status: EvalStatus::Evaluated,
        source: format!("{SYN}: {id} external account"),
    }
}

pub fn externals() -> Vec<Account> {
    vec![
        external("GAS_PATH", &[Slot::Compressor], 40.0),
        external("VALVES", &[Slot::FlowControlAtmospheric, Slot::FlowControlXe], 5.0),
        external("PPU_HOUSEKEEPING", &[Slot::HousekeepingControls], 25.0),
    ]
}

pub fn vs_net_steady() -> ThermalOutput {
    vs_net_loaded_steady(VS_NET_SINK_K, "CONS-L1/vs-net-steady")
}

pub fn vs_net_icp_radiation_not_evaluated() -> ThermalOutput {
    let mut c = vs_net::load_registered();
    vs_net::set_case_id(&mut c, "CONS-L1/SYS-07");
    vs_net::set_sinks(&mut c, VS_NET_SINK_K);
    let v = c.interfaces.icp.as_mut().unwrap().keys.get_mut("Q_icp_radiation_W").unwrap();
    v.status = Some("NOT_EVALUATED".into());
    v.value = None;
    run(&c)
}

fn accounts(out: &ThermalOutput) -> Vec<Account> {
    let mut a = accounts_from_thermal(out, &ICP_PLANES);
    a.extend(externals());
    a
}

/// SYS-01..SYS-08 with their registered expected statuses.
pub fn system_cases(mp: &MassPowerA9V5) -> Vec<(&'static str, EvalStatus, SystemLedger)> {
    let steady = vs_net_steady();
    let base = ls_ledger(600.0);
    let mut out = Vec::new();
    out.push(("SYS-01", EvalStatus::Evaluated, system_energy_ledger(&base, &accounts(&steady))));
    out.push(("SYS-02", EvalStatus::ModelError, system_energy_ledger(&ls_ledger(640.0), &accounts(&steady))));
    let mut a3 = accounts(&steady);
    a3.iter_mut().find(|a| a.account_id == "GAS_PATH").unwrap().status = EvalStatus::NotEvaluated;
    out.push(("SYS-03", EvalStatus::NotEvaluated, system_energy_ledger(&base, &a3)));
    let a4: Vec<Account> = accounts(&steady).into_iter().filter(|a| a.account_id != "PPU_HOUSEKEEPING").collect();
    out.push(("SYS-04", EvalStatus::NotEvaluated, system_energy_ledger(&base, &a4)));
    let mut a5 = accounts(&steady);
    a5.iter_mut().find(|a| a.account_id == "VALVES").unwrap().slots.push((Slot::Compressor, Plane::Load));
    out.push(("SYS-05", EvalStatus::ModelError, system_energy_ledger(&base, &a5)));
    let off = official_flight_ledger(mp).expect("official ledger");
    out.push(("SYS-06", EvalStatus::IncompleteEvidence, system_energy_ledger(&off, &accounts(&steady))));
    let ne = vs_net_icp_radiation_not_evaluated();
    out.push(("SYS-07", EvalStatus::NotEvaluated, system_energy_ledger(&base, &accounts(&ne))));
    let mut a8 = accounts(&steady);
    a8.iter_mut().find(|a| a.account_id == "GAS_PATH").unwrap().deposited_w = -1.0;
    out.push(("SYS-08", EvalStatus::ModelError, system_energy_ledger(&base, &a8)));
    out.push(("SYS-01b (not registered)", EvalStatus::Evaluated, sys_01b(&steady)));
    out
}

pub fn to_json(id: &str, expected: EvalStatus, s: &SystemLedger) -> serde_json::Value {
    json!({
        "case": id,
        "expected_status": expected.as_str(),
        "status": s.status.as_str(),
        "met": s.status == expected,
        "reasons": s.reasons,
        "P_bus_W": s.p_bus_w,
        "sinks_W": s.sinks_w,
        "residual_W": s.residual_w,
        "relative_residual": s.relative_residual,
        "accounts": s.rows.iter().map(|r| json!({
            "account_id": r.account_id, "ledger_W": r.ledger_w, "accounted_W": r.accounted_w,
            "supply_loss_outside_W": r.supply_loss_outside_w, "mismatch_W": r.mismatch_w})).collect::<Vec<_>>(),
        "labels": ["SYNTHETIC_TEST_DATA_NOT_EVIDENCE"],
    })
}
