//! NV-06 / UQ-06: per-reaction comparison of the direct Maxwellian rate (EQ-06) with the registered 1 eV `.dat`
//! interpolation, over every channel of the IF-CHEM-REG-v1 AIR registry. The direct side comes only from the admitted
//! abep-chem integrator through the channel's registered representation (no rate is computed in abep-icp); the `.dat`
//! side is a cross-check and never enters a solve. A channel without a registered representation keeps its direct side
//! withheld with the registry's reason; no number is substituted.

use crate::context::IcpModel;
use crate::status::{IcpStatus, Quantity};
use abep_chem::registry::Representation;
use serde::Serialize;

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Nv06Row {
    /// Registry channel id (contract process id / table stem).
    pub reaction: String,
    pub file: String,
    pub variant_role: String,
    pub t_e_ev: f64,
    /// Linear interpolation of the registered table at 3/2 T_e (cross-check only).
    pub dat_rate_m3_s: Quantity,
    /// Direct Maxwellian integral of the registered representation (EQ-06, abep_chem::checked).
    pub direct_rate_m3_s: Quantity,
    /// (dat - direct) / direct.
    pub relative_difference: Quantity,
}

pub const ABEP_CHEM_NOT_ADMITTED: &str = "EQ-06_ABEP_CHEM_INTEGRATOR_NOT_ADMITTED";
pub const REPRESENTATION_NOT_REGISTERED: &str = "EQ-06_REPRESENTATION_NOT_REGISTERED";

fn status_of(e: &abep_types::AbepError) -> IcpStatus {
    match e.status() {
        abep_types::EvalStatus::OutOfDomain => IcpStatus::OutOfDomain,
        abep_types::EvalStatus::IncompleteEvidence => IcpStatus::IncompleteEvidence,
        abep_types::EvalStatus::NotEvaluated => IcpStatus::NotEvaluated,
        _ => IcpStatus::ModelError,
    }
}

/// The NV-06 report for every AIR registry channel at the given electron temperatures.
pub fn nv06_report(m: &IcpModel, t_e_ev: &[f64]) -> Vec<Nv06Row> {
    let air = &m.chem_registry.air;
    let mut out = Vec::new();
    for ch in &air.channels {
        let file = ch.table_file().to_string();
        let table = &m.n2_tables[&file];
        for &t in t_e_ev {
            let dat = match table.rate_at_te(t) {
                Some(k) => Quantity::value(k, "m^3/s"),
                None => Quantity::withheld("m^3/s", IcpStatus::OutOfDomain, vec!["OUTSIDE_TABULATED_RANGE".into()]),
            };
            let direct = if !m.abep_chem_admitted {
                Quantity::withheld("m^3/s", IcpStatus::NotEvaluated, vec![ABEP_CHEM_NOT_ADMITTED.into()])
            } else {
                match (&ch.representation, air.direct_rate(ch, t)) {
                    (_, Ok(e)) => Quantity::value(e.k_m3_s, "m^3/s"),
                    (Representation::NotRegistered { .. }, Err(_)) => Quantity::withheld(
                        "m^3/s",
                        IcpStatus::IncompleteEvidence,
                        vec![format!("{REPRESENTATION_NOT_REGISTERED}:{}", ch.id)],
                    ),
                    (_, Err(e)) => Quantity::withheld("m^3/s", status_of(&e), vec![e.to_string()]),
                }
            };
            let rel = match (direct.value, dat.value) {
                (Some(a), Some(b)) if a > 0.0 => Quantity::value((b - a) / a, "-"),
                (Some(a), Some(b)) if a == 0.0 && b == 0.0 => Quantity::value(0.0, "-"),
                (Some(_), Some(_)) => {
                    Quantity::withheld("-", IcpStatus::NotEvaluated, vec!["DIRECT_RATE_ZERO_DAT_NONZERO".into()])
                }
                _ => {
                    let side = if direct.value.is_none() { &direct } else { &dat };
                    Quantity::withheld("-", side.status, side.reasons.clone())
                }
            };
            out.push(Nv06Row {
                reaction: ch.id.clone(),
                file: file.clone(),
                variant_role: ch.variant_role.as_str().to_string(),
                t_e_ev: t,
                dat_rate_m3_s: dat,
                direct_rate_m3_s: direct,
                relative_difference: rel,
            });
        }
    }
    out
}
