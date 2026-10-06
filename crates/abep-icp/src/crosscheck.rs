//! NV-06 / UQ-06: per-reaction comparison of the direct Maxwellian rate (EQ-06) with the registered 1 eV `.dat`
//! interpolation. The `.dat` side is a cross-check only and never enters a solve. The direct side needs the admitted
//! abep-chem integrator (IF-CHEM-REG-v1: no rate is computed in abep-icp), so it is NOT_EVALUATED today.

use crate::chemistry::RateSource;
use crate::context::IcpModel;
use crate::status::{IcpStatus, Quantity};
use serde::Serialize;

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Nv06Row {
    pub reaction: String,
    pub file: String,
    pub t_e_ev: f64,
    /// Linear interpolation of the registered table at 3/2 T_e (cross-check only).
    pub dat_rate_m3_s: Quantity,
    pub direct_rate_m3_s: Quantity,
    pub relative_difference: Quantity,
}

pub const ABEP_CHEM_NOT_ADMITTED: &str = "EQ-06_ABEP_CHEM_INTEGRATOR_NOT_ADMITTED";

/// The NV-06 report for the registered N2/N set at the given electron temperatures.
pub fn nv06_report(m: &IcpModel, t_e_ev: &[f64]) -> Vec<Nv06Row> {
    let mut out = Vec::new();
    for rx in &m.n2_set.reactions {
        let RateSource::RegisteredTable { file } = &rx.rate else { continue };
        let table = &m.n2_tables[file];
        for &t in t_e_ev {
            let dat = match table.rate_at_te(t) {
                Some(k) => Quantity::value(k, "m^3/s"),
                None => Quantity::withheld("m^3/s", IcpStatus::OutOfDomain, vec!["OUTSIDE_TABULATED_RANGE".into()]),
            };
            let ne = || Quantity::withheld("m^3/s", IcpStatus::NotEvaluated, vec![ABEP_CHEM_NOT_ADMITTED.into()]);
            out.push(Nv06Row {
                reaction: rx.id.clone(),
                file: file.clone(),
                t_e_ev: t,
                dat_rate_m3_s: dat,
                direct_rate_m3_s: ne(),
                relative_difference: Quantity::withheld(
                    "-",
                    IcpStatus::NotEvaluated,
                    vec![ABEP_CHEM_NOT_ADMITTED.into()],
                ),
            });
        }
    }
    out
}
