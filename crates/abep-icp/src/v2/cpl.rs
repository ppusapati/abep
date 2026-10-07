//! CPL-HALL-ON-v1, the Hall-ON neutralization coupling contract (A9.31 OQ-NPICP-11). Preregistered; numerical
//! execution is gated (CPL-HON-01). This module is the typed contract: it names every required input (CPL-HON-02),
//! reports which have no producer, and returns NOT_EVALUATED / INCOMPLETE_EVIDENCE for every output. It holds no beam
//! divergence, plume potential, transfer fraction, coupling voltage or CEX parameter and never defaults one
//! (CPL-HON-11): there is no code path that produces a Hall-ON number until an admitted member, the HI-04..HI-06
//! producers and the VER-24 addendum exist. VER-23 is cleared (verification_addendum_ver23_v1.json): the pinned
//! HallThruster.jl takes the coupling potential as its right-boundary input `cathode_coupling_voltage` [V] (CPL-HON-05).

use super::result::CplRecord;
use super::{IcpModelV2, CPL_HALL_ON};
use crate::status::{worst_of, IcpStatus, Quantity, Reason};
use std::collections::BTreeMap;

/// A SYNTHETIC_TEST_ONLY stand-in for an admitted Hall member (FC-20 only). Never evidence; its outputs stay labelled.
#[derive(Debug, Clone, PartialEq)]
pub struct SyntheticAdmittedHallStub {
    pub member_id: String,
    pub i_d_a: Option<f64>,
    pub i_beam_a: Option<f64>,
    pub v_d_v: Option<f64>,
}

/// Where the Hall member comes from.
#[derive(Debug, Clone, PartialEq)]
pub enum HallMemberSource<'a> {
    /// The governed transport ensemble (`hallthruster_bridge/ensemble/transport_ensemble_v0.json`).
    Ensemble,
    SyntheticAdmittedStub(&'a SyntheticAdmittedHallStub),
}

/// Inputs of CPL-HALL-ON-v1 apart from the Hall member.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct CplInputs {
    /// HI-07: B in the ICP volume at the Hall-ON magnet state [T] (IN-15).
    pub b_icp_t: Option<f64>,
    /// HI-08: the registered discharge-circuit topology record (ICD ICP-20 / ICP-21).
    pub circuit_topology_record: Option<String>,
}

const NE: IcpStatus = IcpStatus::NotEvaluated;
const IE: IcpStatus = IcpStatus::IncompleteEvidence;

/// Output keys of CPL-HON-09 (OUT-07 v2 and the CPL-HON-08 energies).
pub const CPL_OUTPUT_KEYS: [(&str, &str); 7] = [
    ("I_e_neutralization_available_A", "A"),
    ("V_coupling_V", "V"),
    ("I_d_A", "A"),
    ("I_beam_A", "A"),
    ("P_icp_collector_bias_W", "W"),
    ("P_cpl_hall_loop_at_icp_W", "W"),
    ("Q_cpl_hallon_circuit_export_W", "W"),
];

pub fn cpl_hall_on(m: &IcpModelV2, source: &HallMemberSource, inp: &CplInputs) -> CplRecord {
    let mut reasons: Vec<Reason> = Vec::new();
    let mut inputs: BTreeMap<String, Quantity> = BTreeMap::new();
    let r = |c: &str, s: IcpStatus, d: &str| Reason::new(c, s, d);
    let stub = match source {
        HallMemberSource::Ensemble => {
            if m.v1.ensemble_member_count == 0 {
                reasons.push(r(
                    "CREDIBLE_HALL_TRANSPORT_SET_EMPTY",
                    NE,
                    "CPL-HON-01: transport_ensemble_v0 members = []; CFG-FLIGHT-HALL-ON = NOT_EVALUATED",
                ));
            } else {
                reasons.push(r(
                    "HALL_MAP_POINT_NOT_REGISTERED",
                    NE,
                    "CPL-HON-01: no design-specific Hall map point at the pinned commit is registered",
                ));
            }
            None
        }
        HallMemberSource::SyntheticAdmittedStub(s) => {
            reasons.push(r("SYNTHETIC_TEST_ONLY", NE, "synthetic admitted-member stub (FC-20): never evidence"));
            Some(*s)
        }
    };
    let echo = |v: Option<f64>, unit: &str, code: &str| match (stub, v) {
        (Some(_), Some(x)) => {
            Quantity { value: Some(x), unit: unit.into(), status: NE, reasons: vec!["SYNTHETIC_TEST_ONLY".into()] }
        }
        (Some(_), None) => Quantity::withheld(unit, NE, vec![format!("{code}_NOT_ON_MAP_POINT")]),
        (None, _) => Quantity::withheld(unit, NE, vec!["CPL-HON-01_GATE".into()]),
    };
    inputs.insert("HI-01_I_d_A".into(), echo(stub.and_then(|s| s.i_d_a), "A", "HI-01"));
    inputs.insert("HI-02_I_beam_A".into(), echo(stub.and_then(|s| s.i_beam_a), "A", "HI-02"));
    inputs.insert("HI-03_V_d_V".into(), echo(stub.and_then(|s| s.v_d_v), "V", "HI-03"));
    for (id, what) in [
        ("HI-04_exit_neutral_flux_transfer", "per-species Hall-exit neutral flux and its transfer to the ICP inlet"),
        ("HI-05_beam_cex_ions_at_icp", "beam / CEX ion flux, energy and charge state at ICP surfaces (plume model)"),
        ("HI-06_plume_potential_at_sink", "plume potential at the extraction boundary"),
    ] {
        let code = format!("{}_NO_PRODUCER", &id[..5]);
        reasons.push(r(&code, NE, what));
        inputs.insert(id.into(), Quantity::withheld("-", NE, vec![code]));
    }
    match inp.b_icp_t {
        None => {
            reasons.push(r("HI-07_B_ICP_NOT_REGISTERED", IE, "IN-15 / VI-HD-06 at the Hall-ON magnet state"));
            inputs
                .insert("HI-07_B_icp_T".into(), Quantity::withheld("T", IE, vec!["HI-07_B_ICP_NOT_REGISTERED".into()]));
        }
        Some(b) if b > 0.0 => {
            reasons.push(r("DOM-06_NO_SOURCED_MAGNETIZATION_CRITERION", IE, "B > 0 in the ICP volume"));
            inputs.insert("HI-07_B_icp_T".into(), Quantity::withheld("T", IE, vec!["DOM-06".into()]));
        }
        Some(b) => {
            inputs.insert("HI-07_B_icp_T".into(), Quantity::value(b, "T"));
        }
    }
    match &inp.circuit_topology_record {
        None => {
            reasons.push(r("HI-08_CIRCUIT_TOPOLOGY_NOT_REGISTERED", NE, "ICD ICP-20 / ICP-21"));
            inputs.insert("HI-08_circuit_topology".into(), Quantity::withheld("-", NE, vec!["HI-08".into()]));
        }
        Some(rec) => {
            inputs.insert(
                "HI-08_circuit_topology".into(),
                Quantity { value: None, unit: "-".into(), status: IcpStatus::Converged, reasons: vec![rec.clone()] },
            );
        }
    }
    reasons.push(r("VER-24_EXTRACTION_BOUNDARY_LAW_UNVERIFIED", NE, "CPL-HON-04: V_coupling NOT_EVALUATED"));
    let codes: Vec<String> = reasons.iter().map(|x| x.code.clone()).collect();
    let outputs =
        CPL_OUTPUT_KEYS.iter().map(|(k, u)| (k.to_string(), Quantity::withheld(u, NE, codes.clone()))).collect();
    let status = match stub {
        None => NE,
        Some(_) => {
            let s = worst_of(&reasons);
            if s.is_converged() {
                NE
            } else {
                s
            }
        }
    };
    CplRecord {
        contract: CPL_HALL_ON.into(),
        configuration: "CFG-FLIGHT-HALL-ON".into(),
        status,
        reasons,
        inputs,
        outputs,
        verify_items: vec!["VER-24".into()],
    }
}
