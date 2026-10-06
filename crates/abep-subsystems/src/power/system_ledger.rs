//! CONS-L1, the system energy ledger (CLAUDE.md rule 4; NP-THERMAL-CATHODELESS prereg CONS-L1 / EB-05; contract
//! PARITY-C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY-V1 conservation_checks).
//!
//! Every watt crossing the spacecraft-side DC boundary in one evaluated step must be accounted for exactly once: as
//! supply / front-end conversion loss at the PPU (the ledger's own P_loss terms), or by the downstream model that the
//! slot's supply powers (deposited on nodes, exported, or booked at a boundary). Each downstream account declares the
//! plane at which its slots' power is compared (load plane, supply input, or spacecraft side); nothing is defaulted.
//! The residual must stay below 2 % of P_bus; a larger residual is a MODEL_ERROR (conservation is a gate). An
//! incomplete bus ledger leaves the check INCOMPLETE_EVIDENCE, a non-EVALUATED account propagates its status, and an
//! ON slot with no account is NOT_EVALUATED (never zero-filled).

use super::ledger::{Ledger, LedgerStatus};
use super::pyfmt::fsum;
use super::slots::Slot;
use crate::thermal::output::{RunStatus, ThermalOutput};
use abep_types::EvalStatus;
use std::collections::BTreeMap;

/// Relative residual bound of the architecture energy ledger (CLAUDE.md rule 4: < 2 %).
pub const CONS_L1_REL_TOL: f64 = 0.02;

/// Where an account's slot power is read from the ledger.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Plane {
    /// P_W at the slot's load plane.
    Load,
    /// P_W / eta_slot (the supply's input on the internal bus or the spacecraft input for direct slots).
    SupplyInput,
    /// P_bus_W (spacecraft side, front end included).
    Bus,
}

/// One downstream account: the power a model receives from the supplies of `slots`, split into what it deposits,
/// exports and books at a boundary.
#[derive(Debug, Clone, PartialEq)]
pub struct Account {
    pub account_id: String,
    pub slots: Vec<(Slot, Plane)>,
    pub deposited_w: f64,
    pub exported_w: f64,
    pub booked_w: f64,
    pub status: EvalStatus,
    pub source: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct AccountRow {
    pub account_id: String,
    /// Ledger power of the account's slots at the declared planes.
    pub ledger_w: f64,
    /// deposited + exported + booked.
    pub accounted_w: f64,
    /// Supply / front-end loss of the account's slots booked outside the account (P_bus - plane value).
    pub supply_loss_outside_w: f64,
    pub mismatch_w: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SystemLedger {
    pub status: EvalStatus,
    pub reasons: Vec<String>,
    pub p_bus_w: Option<f64>,
    pub sinks_w: Option<f64>,
    pub residual_w: Option<f64>,
    pub relative_residual: Option<f64>,
    pub rows: Vec<AccountRow>,
}

fn severity(s: EvalStatus) -> u8 {
    match s {
        EvalStatus::Evaluated => 0,
        EvalStatus::IncompleteEvidence => 1,
        EvalStatus::NotEvaluated => 2,
        EvalStatus::OutOfDomain => 3,
        EvalStatus::ModelError => 4,
    }
}

fn worst(a: EvalStatus, b: EvalStatus) -> EvalStatus {
    if severity(b) > severity(a) {
        b
    } else {
        a
    }
}

fn not_evaluated(status: EvalStatus, reasons: Vec<String>) -> SystemLedger {
    SystemLedger {
        status,
        reasons,
        p_bus_w: None,
        sinks_w: None,
        residual_w: None,
        relative_residual: None,
        rows: vec![],
    }
}

/// CONS-L1 on one ledger and its downstream accounts.
pub fn system_energy_ledger(led: &Ledger, accounts: &[Account]) -> SystemLedger {
    if led.status != LedgerStatus::Complete {
        return not_evaluated(
            EvalStatus::IncompleteEvidence,
            vec![format!("CONS-L1_LEDGER_NOT_COMPLETE: bus ledger {} (P_bus unknown)", led.status.as_str())],
        );
    }
    let mut status = EvalStatus::Evaluated;
    let mut reasons = Vec::new();
    let mut owner: BTreeMap<Slot, &str> = BTreeMap::new();
    for a in accounts {
        for (s, _) in &a.slots {
            if !led.item(*s).installed() {
                status = worst(status, EvalStatus::ModelError);
                reasons.push(format!("CONS-L1_SLOT_NOT_INSTALLED: {} in {}", s.name(), a.account_id));
            }
            if let Some(prev) = owner.insert(*s, &a.account_id) {
                status = worst(status, EvalStatus::ModelError);
                reasons.push(format!("CONS-L1_DOUBLE_COUNT: {} in {} and {}", s.name(), prev, a.account_id));
            }
        }
        for (n, x) in [("deposited_W", a.deposited_w), ("exported_W", a.exported_w), ("booked_W", a.booked_w)] {
            if !(x.is_finite() && x >= 0.0) {
                status = worst(status, EvalStatus::ModelError);
                reasons.push(format!("CONS-L1_ACCOUNT_AMOUNT: {} {n} = {x}", a.account_id));
            }
        }
        if a.status != EvalStatus::Evaluated {
            status = worst(status, a.status);
            reasons.push(format!("CONS-L1_ACCOUNT_STATUS: {} is {}", a.account_id, a.status));
        }
    }
    for it in led.items.iter().filter(|it| it.p_w.is_some_and(|p| p > 0.0)) {
        if !owner.contains_key(&it.slot) {
            status = worst(status, EvalStatus::NotEvaluated);
            reasons.push(format!("CONS-L1_UNCOVERED_LOAD: {} has no downstream account", it.slot.name()));
        }
    }
    if status != EvalStatus::Evaluated {
        return not_evaluated(status, reasons);
    }
    let value_at = |s: Slot, p: Plane| -> (f64, f64) {
        let it = led.item(s);
        let pw = it.p_w.unwrap_or(0.0);
        let bus = it.p_bus_w.unwrap_or(0.0);
        let v = match p {
            Plane::Load => pw,
            Plane::SupplyInput => match it.efficiency {
                Some(e) if pw != 0.0 => pw / e,
                _ => pw,
            },
            Plane::Bus => bus,
        };
        (v, bus - v)
    };
    let mut rows = Vec::new();
    let mut sink_terms = Vec::new();
    for a in accounts {
        let vals: Vec<(f64, f64)> = a.slots.iter().map(|(s, p)| value_at(*s, *p)).collect();
        let v = fsum(vals.iter().map(|x| x.0)).unwrap_or(f64::NAN);
        let x = fsum(vals.iter().map(|x| x.1)).unwrap_or(f64::NAN);
        let c = a.deposited_w + a.exported_w + a.booked_w;
        sink_terms.push(c);
        sink_terms.push(x);
        rows.push(AccountRow {
            account_id: a.account_id.clone(),
            ledger_w: v,
            accounted_w: c,
            supply_loss_outside_w: x,
            mismatch_w: v - c,
        });
    }
    // Slots that draw nothing still close: an OFF slot has P_bus = 0.
    let p_bus = led.p_bus_w.unwrap_or(0.0);
    let sinks = fsum(sink_terms).unwrap_or(f64::NAN);
    let r = p_bus - sinks;
    let rel = if p_bus > 0.0 {
        r.abs() / p_bus
    } else if r == 0.0 {
        0.0
    } else {
        f64::INFINITY
    };
    let (status, reasons) = if rel < CONS_L1_REL_TOL {
        (EvalStatus::Evaluated, vec![])
    } else {
        (EvalStatus::ModelError, vec![format!("CONS-L1_RESIDUAL: |R| / P_bus = {rel} >= {CONS_L1_REL_TOL}")])
    };
    SystemLedger {
        status,
        reasons,
        p_bus_w: Some(p_bus),
        sinks_w: Some(sinks),
        residual_w: Some(r),
        relative_residual: Some(rel),
        rows,
    }
}

/// Interface keys of the Hall discharge supply (IF-HALL-THERMAL-v1 HK-03..HK-09) deposited by the thermal model.
pub const HALL_DISCHARGE_KEYS: [&str; 7] = [
    "Q_hall_anode_W",
    "Q_hall_wall_inner_W",
    "Q_hall_wall_outer_W",
    "Q_hall_pole_W",
    "Q_hall_plasma_radiation_W",
    "Q_hall_return_to_icp_W",
    "Q_hall_plume_to_icp_W",
];
/// Interface keys of the RF/ICP chain deposited by the thermal model (IF-ICP-THERMAL-v1).
pub const ICP_DEPOSITED_KEYS: [&str; 4] =
    ["Q_icp_plasma_wall_W", "Q_icp_coil_ohmic_W", "Q_icp_match_W", "Q_icp_radiation_W"];
pub const COIL_KEYS: [(Slot, &str); 3] = [
    (Slot::HallMagnetInner, "Q_hall_coil_inner_W"),
    (Slot::HallMagnetOuter, "Q_hall_coil_outer_W"),
    (Slot::HallMagnetTrim, "Q_hall_coil_trim_W"),
];

/// Downstream accounts of a steady NP-THERMAL output (the booked flows of the thermal model): Hall discharge, the
/// three coils, the ICP chain at the slot planes the case declares (`icp_slot_planes`) and thermal control. Each
/// account carries the thermal run status; a non-CONVERGED run makes every account NOT_EVALUATED (or its status).
pub fn accounts_from_thermal(out: &ThermalOutput, icp_slot_planes: &[(Slot, Plane)]) -> Vec<Account> {
    let status = out.run_status.eval_status();
    let src = |what: &str| format!("NP-THERMAL-CATHODELESS {} case {}: {what}", out.model_version, out.case_id);
    let mut accounts = Vec::new();
    let res = match (&out.results, out.run_status) {
        (Some(r), RunStatus::Converged) if r.t_node_k.is_some() => r,
        _ => {
            let st = if status == EvalStatus::Evaluated { EvalStatus::NotEvaluated } else { status };
            let mk = |id: &str, slots: Vec<(Slot, Plane)>| Account {
                account_id: id.into(),
                slots,
                deposited_w: 0.0,
                exported_w: 0.0,
                booked_w: 0.0,
                status: st,
                source: src("no converged steady thermal result"),
            };
            accounts.push(mk("HALL_DISCHARGE", vec![(Slot::HallDischarge, Plane::Load)]));
            for (s, _) in COIL_KEYS {
                accounts.push(mk(&format!("HALL_MAGNET_{}", s.name()), vec![(s, Plane::Load)]));
            }
            accounts.push(mk("ICP", icp_slot_planes.to_vec()));
            accounts.push(mk("THERMAL_CONTROL", vec![(Slot::ThermalControl, Plane::Load)]));
            return accounts;
        }
    };
    let deposited = |keys: &[&str]| -> f64 {
        fsum(
            res.q_source_node_w
                .values()
                .flat_map(|m| m.iter().filter(|(k, _)| keys.contains(&k.as_str())))
                .map(|(_, v)| *v),
        )
        .unwrap_or(f64::NAN)
    };
    let first = |m: &BTreeMap<String, Vec<f64>>, k: &str| m.get(k).and_then(|v| v.first().copied()).unwrap_or(0.0);
    let hall_present = res.p_exported_w.contains_key("P_hall_exported_W");
    accounts.push(Account {
        account_id: "HALL_DISCHARGE".into(),
        slots: vec![(Slot::HallDischarge, Plane::Load)],
        deposited_w: deposited(&HALL_DISCHARGE_KEYS),
        exported_w: first(&res.p_exported_w, "P_hall_exported_W"),
        booked_w: 0.0,
        status: if hall_present { EvalStatus::Evaluated } else { EvalStatus::NotEvaluated },
        source: src("Q_source_node_W (Hall discharge keys) + P_exported_W.P_hall_exported_W"),
    });
    for (s, k) in COIL_KEYS {
        accounts.push(Account {
            account_id: format!("HALL_MAGNET_{}", s.name()),
            slots: vec![(s, Plane::Load)],
            deposited_w: deposited(&[k]),
            exported_w: 0.0,
            booked_w: 0.0,
            status: EvalStatus::Evaluated,
            source: src(&format!("Q_source_node_W.{k}")),
        });
    }
    let icp_present = res.q_boundary_w.b_ppu_rf_booked.contains_key("Q_icp_boundary_W");
    accounts.push(Account {
        account_id: "ICP".into(),
        slots: icp_slot_planes.to_vec(),
        deposited_w: deposited(&ICP_DEPOSITED_KEYS),
        exported_w: first(&res.p_exported_w, "Q_icp_extraction_W")
            + first(&res.p_exported_w, "Q_icp_radiation_W.EXPORT"),
        booked_w: first(&res.q_boundary_w.b_ppu_rf_booked, "Q_icp_boundary_W")
            + first(&res.q_boundary_w.b_ppu_rf_booked, "Q_icp_match_W"),
        status: if icp_present { EvalStatus::Evaluated } else { EvalStatus::NotEvaluated },
        source: src("Q_source_node_W (ICP keys) + P_exported_W (extraction, radiation EXPORT) + B_PPU_RF_booked"),
    });
    accounts.push(Account {
        account_id: "THERMAL_CONTROL".into(),
        slots: vec![(Slot::ThermalControl, Plane::Load)],
        deposited_w: deposited(&["Q_thermal_control_W"]),
        exported_w: 0.0,
        booked_w: 0.0,
        status: EvalStatus::Evaluated,
        source: src("Q_source_node_W.Q_thermal_control_W"),
    });
    accounts
}
