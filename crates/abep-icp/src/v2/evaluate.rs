//! model_version 2 evaluation in the registered order: (1) input registration (the v1 shared part, then the v2
//! gates) -> NOT_EVALUATED / INCOMPLETE_EVIDENCE / MODEL_ERROR; (2) input domain -> OUT_OF_DOMAIN; (3) one solve per
//! solve member (ED-08) -> MODEL_ERROR on failure; (4) solution domain; (5) conservation; (6) the energy disposition
//! per partition member and the interface records. Every output carries its own status and scenario member id.

use super::case::*;
use super::cpl::{cpl_hall_on, CplInputs, HallMemberSource};
use super::diagnostics;
use super::formation::{formation_table, parent_molecule, FormationTable};
use super::partition::{self, Coef, PartitionInput, WallCoefs};
use super::result::*;
use super::THERMAL_INTERFACE_V2;
use super::{IcpModelV2, BUS_INTERFACE_V2, CONTRACT_ID_V2, CPL_HALL_ON, MODEL_VERSION_V2, THERMAL_CONSUMER_V2};
use crate::case::{
    Configuration, CouplingEvidence, CouplingMode, Disposition, FeedState, GasMode, HallDemandBasis, IcpCase,
    NeutralSource, PlaneConvention, RfInput, SupplyMode, VariantSlot,
};
use crate::chemistry::{ChemistryRegistration, ChemistrySet, ReactionKind, Validity};
use crate::constants::{NumericalSettings, E_CHARGE, KN_FREE_MOLECULAR_MIN, K_B, NUMERICS, P_100_MTORR_PA};
use crate::constants::{TOL_CONS, TOL_SOLVE};
use crate::context::ACTIVE_BUS_BOUNDARY;
use crate::coupling::{self, Calibrated};
use crate::evaluate::{production_current, r, Evaluator, Gate};
use crate::evidence::{EvidenceRecord, QuantityType, Registered, UncertaintyRepr};
use crate::geometry::{HModel, SurfaceKind, ThermalNode, Transmission};
use crate::physics;
use crate::result::{CheckRecord, EquilibriumRecord, Label, OutputValue};
use crate::solver::{
    self, DirectRate, Equilibrium, PreparedCase, PreparedH, PreparedNeutrals, PreparedSurface, Recombination,
    SolveOutcome,
};
use crate::status::{worst_of, IcpStatus, Quantity, Reason};
use abep_chem::registry::Representation;
use abep_provenance::sha256_hex;
use std::collections::{BTreeMap, BTreeSet};

const S_CONV: IcpStatus = IcpStatus::Converged;
const S_NE: IcpStatus = IcpStatus::NotEvaluated;
const S_IE: IcpStatus = IcpStatus::IncompleteEvidence;
const S_OOD: IcpStatus = IcpStatus::OutOfDomain;
const S_ME: IcpStatus = IcpStatus::ModelError;

/// The IF-ICP-THERMAL-v2 keys in table order (TK-R1..TK-R5, TK-01..TK-15).
pub const THERMAL_KEYS: [&str; 20] = [
    "P_icp_slot_load_sum_W",
    "P_icp_rf_source_DC_W",
    "P_icp_rf_forward_W",
    "P_icp_abs_W",
    "P_icp_collector_bias_W",
    "Q_icp_rf_conversion_loss_W",
    "P_icp_rf_reflected_W",
    "Q_icp_line_W",
    "Q_icp_match_W",
    "P_icp_matching_DC_W",
    "Q_icp_coil_ohmic_W",
    "Q_icp_plasma_wall_W",
    "Q_icp_radiation_W",
    "Q_icp_extraction_W",
    "Q_icp_outflow_upstream_W",
    "Q_icp_outflow_downstream_W",
    "Q_icp_bias_collector_W",
    "Q_icp_bias_export_W",
    "P_icp_flow_control_W",
    "P_icp_assist_magnet_W",
];

/// The destination keys TK-01..TK-13 of CONS-I3.
pub const DESTINATION_KEYS: [&str; 13] = [
    "Q_icp_rf_conversion_loss_W",
    "P_icp_rf_reflected_W",
    "Q_icp_line_W",
    "Q_icp_match_W",
    "P_icp_matching_DC_W",
    "Q_icp_coil_ohmic_W",
    "Q_icp_plasma_wall_W",
    "Q_icp_radiation_W",
    "Q_icp_extraction_W",
    "Q_icp_outflow_upstream_W",
    "Q_icp_outflow_downstream_W",
    "Q_icp_bias_collector_W",
    "Q_icp_bias_export_W",
];

/// Nodes a TK-06 split may name (IF-ICP-THERMAL-v2 TK-06 receiver).
pub const COIL_SPLIT_NODES: [&str; 4] = ["N_ANTENNA", "N_COLLECTOR", "N_HOUSING", "N_MOUNT"];

fn codes(rs: &[Reason]) -> Vec<String> {
    rs.iter().map(|x| x.code.clone()).collect()
}

fn ok_pos(x: f64) -> bool {
    x.is_finite() && x > 0.0
}

fn max_sev(s: IcpStatus) -> IcpStatus {
    if s.is_converged() {
        S_ME
    } else {
        s
    }
}

fn withheld(unit: &str, rs: &[Reason]) -> Quantity {
    Quantity::withheld_by(unit, rs)
}

impl IcpModelV2 {
    pub fn evaluate(&self, case: &IcpCaseV2) -> IcpResultV2 {
        self.evaluate_with(case, &NUMERICS)
    }

    pub fn evaluate_with(&self, case: &IcpCaseV2, num: &NumericalSettings) -> IcpResultV2 {
        EvalV2 { m: self, c: case, num, flags: BTreeSet::new(), verify: BTreeSet::new() }.run()
    }
}

/// One solve member's choices (ED-08).
#[derive(Debug, Clone)]
struct SolveSpec {
    id: String,
    h_label: String,
    h: PreparedH,
    gamma: BTreeMap<(String, String), f64>,
}

struct EvalV2<'a> {
    m: &'a IcpModelV2,
    c: &'a IcpCaseV2,
    num: &'a NumericalSettings,
    flags: BTreeSet<String>,
    verify: BTreeSet<String>,
}

/// Gates that withhold output groups without blocking the solve.
#[derive(Default)]
struct OutGates {
    /// DOM-06 v2: B > 0 -> every plasma, capacity and partition output INCOMPLETE_EVIDENCE (diagnostics reported).
    magnetized: Vec<Reason>,
    /// Partition-only gates (FC-29 IN-25, ...): the solve and I_e,cap are unaffected.
    partition: Vec<Reason>,
    /// IF-ICP-BUS-v2 per key group.
    bus: Vec<Reason>,
    bias_bus: Vec<Reason>,
    coupling: Vec<Reason>,
}

fn evidence_list(c: &IcpCaseV2) -> Vec<(String, &EvidenceRecord)> {
    let mut v: Vec<(String, &EvidenceRecord)> =
        vec![("IN-01.supply_mode".into(), &c.supply_mode.evidence), ("IN-02.gas_mode".into(), &c.gas_mode.evidence)];
    if let Some(f) = &c.f_rf_hz {
        v.push(("IN-07.f_rf_hz".into(), &f.evidence));
    }
    match &c.rf_input {
        Some(RfInput::AbsorbedPower { p_abs_w }) => v.push(("IN-08.p_abs_w".into(), &p_abs_w.evidence)),
        Some(RfInput::Forward { p_fwd_w, p_refl_w }) => {
            v.push(("IN-08.p_fwd_w".into(), &p_fwd_w.evidence));
            v.push(("IN-08.p_refl_w".into(), &p_refl_w.evidence));
        }
        None => {}
    }
    if let Some(CouplingEvidence::P2Point { point }) = &c.coupling_evidence {
        v.push(("IN-09.p2_point".into(), &point.evidence));
    }
    if let Some(g) = &c.geometry {
        v.push(("IN-10.geometry".into(), &g.evidence));
    }
    if let Some(e) = &c.electrodes {
        v.push(("IN-11.electrodes".into(), &e.evidence));
    }
    match &c.neutral_source {
        Some(NeutralSourceV2::RegisteredPressure { p_icp_pa, t_g_k, mole_fractions }) => {
            v.push(("IN-12.p_icp_pa".into(), &p_icp_pa.evidence));
            v.push(("IN-12.t_g_k".into(), &t_g_k.evidence));
            v.push(("IN-05.mole_fractions".into(), &mole_fractions.evidence));
        }
        Some(NeutralSourceV2::FlowBalance { t_g_k, sigma_c_m2, inflow, f_in }) => {
            v.push(("IN-12.t_g_k".into(), &t_g_k.evidence));
            for (k, s) in sigma_c_m2 {
                v.push((format!("DOM-04.sigma_c.{k}"), &s.evidence));
            }
            match inflow {
                InflowV2::NoInflow => {}
                InflowV2::MeasuredDedicatedFeed { mdot_kg_s } => v.push(("IN-12.inflow".into(), &mdot_kg_s.evidence)),
                InflowV2::UpstreamModel { gamma_in_per_s, .. } => {
                    v.push(("IN-12.inflow".into(), &gamma_in_per_s.evidence))
                }
            }
            if let Some(f) = f_in {
                v.push(("IN-12.f_in (retired)".into(), &f.evidence));
            }
        }
        None => {}
    }
    if let Some(b) = &c.background {
        v.push(("IN-13.background".into(), &b.evidence));
    }
    if let Some(t) = &c.thermal_boundary {
        v.push(("IN-14.thermal_boundary".into(), &t.evidence));
    }
    if let Some(b) = &c.b_icp_max_t {
        v.push(("IN-15.b_icp_max_t".into(), &b.evidence));
    }
    match &c.h_model {
        Some(HModel::Explicit { h_by_surface }) => {
            for (k, h) in h_by_surface {
                v.push((format!("IN-17.h.{k}"), &h.evidence));
            }
        }
        Some(HModel::Lieberman { sigma_i_m2 }) => {
            for (k, s) in sigma_i_m2 {
                v.push((format!("IN-17.sigma_i.{k}"), &s.evidence));
            }
        }
        None => {}
    }
    for w in &c.wall_coefficients {
        for (n, x) in [("gamma", &w.gamma), ("beta", &w.beta), ("quench", &w.quench)] {
            if let Some(x) = x {
                v.push((format!("IN-18.{n}.{}@{}", w.species, w.material), &x.evidence));
            }
        }
    }
    for (k, d) in &c.dispositions {
        v.push((format!("IN-23.disposition.{k}"), &d.evidence));
    }
    for (k, d) in &c.dissociation_energies_ev {
        v.push((format!("IN-25.D0.{k}"), &d.evidence));
    }
    if let Some(d) = &c.dedicated_flow_kg_s {
        v.push(("IF-ICP-FEED-v1.dedicated_flow".into(), &d.evidence));
    }
    if let Some(b) = &c.bus {
        v.push(("IN-19.eta_rf".into(), &b.eta_rf.evidence));
        v.push(("IN-19.p_match_dc_w".into(), &b.p_match_dc_w.evidence));
        v.push(("IN-19.match_colocated".into(), &b.match_colocated.evidence));
        for (n, s) in [("assist_magnet", &b.assist_magnet), ("flow_control", &b.flow_control)] {
            if let VariantSlot::Installed { p_w } = s {
                v.push((format!("IN-19.{n}"), &p_w.evidence));
            }
        }
        if let Some(e) = &b.eta_bias {
            v.push(("IN-19.eta_bias (retired)".into(), &e.evidence));
        }
    }
    if let Some(s) = &c.coil_ohmic_split {
        v.push(("TK-06.coil_ohmic_split".into(), &s.evidence));
    }
    if let Some(h) = &c.hall_demand {
        v.push(("IN-20.i_d_max_h1_a".into(), &h.i_d_max_h1_a.evidence));
    }
    v
}

/// A v1-shaped view of the fields the shared registration reads (the rest are left unregistered there and are
/// registered by the v2 gates).
fn view_case(c: &IcpCaseV2) -> IcpCase {
    let presence = |m: &BTreeMap<String, f64>| -> BTreeMap<String, f64> {
        m.iter().filter(|(_, v)| **v > 0.0).map(|(k, _)| (k.clone(), 1.0)).collect()
    };
    let (neutral_source, feed) = match &c.neutral_source {
        Some(NeutralSourceV2::RegisteredPressure { p_icp_pa, t_g_k, mole_fractions }) => (
            Some(NeutralSource::RegisteredPressure {
                p_icp_pa: p_icp_pa.clone(),
                t_g_k: t_g_k.clone(),
                mole_fractions: mole_fractions.clone(),
            }),
            None,
        ),
        Some(NeutralSourceV2::FlowBalance { inflow, .. }) => {
            let m = match inflow {
                InflowV2::NoInflow => BTreeMap::new(),
                InflowV2::MeasuredDedicatedFeed { mdot_kg_s } => presence(&mdot_kg_s.value),
                InflowV2::UpstreamModel { gamma_in_per_s, .. } => presence(&gamma_in_per_s.value),
            };
            let st = FeedState { mdot_kg_s: m, p_feed_pa: f64::NAN, t_feed_k: f64::NAN, x_s: BTreeMap::new() };
            (None, Some(Registered::new(st, EvidenceRecord::default())))
        }
        None => (None, None),
    };
    IcpCase {
        case_id: c.case_id.clone(),
        supply_mode: c.supply_mode.clone(),
        gas_mode: c.gas_mode.clone(),
        configuration: c.configuration,
        coupling_mode: c.coupling_mode,
        h1_point_id: c.h1_point_id.clone(),
        f_rf_hz: c.f_rf_hz.clone(),
        rf_input: c.rf_input.clone(),
        coupling_evidence: c.coupling_evidence.clone(),
        geometry: None,
        electrodes: None,
        neutral_source,
        feed,
        background: None,
        thermal_boundary: None,
        b_icp_max_t: None,
        chemistry: c.chemistry.clone(),
        h_model: None,
        wall_recombination: BTreeMap::new(),
        dispositions: c.dispositions.clone(),
        dedicated_flow_kg_s: None,
        bus: None,
        hall_demand: None,
    }
}

/// IN-10 v2 surface contract (a violation is MODEL_ERROR).
pub fn geometry_v2_violations(g: &GeometryV2) -> Vec<String> {
    let mut v = Vec::new();
    let pos = |x: f64| x.is_finite() && x > 0.0;
    if !pos(g.radius_m) || !pos(g.length_m) {
        v.push("radius_m and length_m must be finite and > 0".into());
    }
    if let VolumeModeV2::RegisteredEffective { volume_m3, .. } = g.volume_mode {
        if !pos(volume_m3) {
            v.push("registered effective volume must be finite and > 0".into());
        }
    }
    if g.surfaces.is_empty() {
        v.push("no bounding surface registered".into());
    }
    let mut ids = BTreeSet::new();
    let mut n_ec = 0;
    for s in &g.surfaces {
        if !ids.insert(s.id.as_str()) {
            v.push(format!("duplicate surface id {}", s.id));
        }
        if !pos(s.area_m2) {
            v.push(format!("surface {}: area must be finite and > 0", s.id));
        }
        if s.thermal_node == ThermalNode::H1Faces {
            v.push(format!(
                "surface {}: H1_FACES is retired in v2 (H-1 receives ICP energy only via RX-H1-FACE)",
                s.id
            ));
        }
        match s.kind {
            SurfaceKind::ElectronCollector => {
                n_ec += 1;
                if s.thermal_node != ThermalNode::Export {
                    v.push(format!("surface {}: the electron collector maps to EXPORT", s.id));
                }
            }
            SurfaceKind::OpenDownstream if s.thermal_node != ThermalNode::Export => {
                v.push(format!("surface {}: the downstream open end maps to EXPORT", s.id));
            }
            SurfaceKind::OpenUpstream if s.thermal_node != ThermalNode::RxH1Face => {
                v.push(format!("surface {}: the upstream open end maps to RX_H1_FACE", s.id));
            }
            k if k.is_neutralizer_wall() && !s.thermal_node.is_neutralizer_node() => {
                v.push(format!("surface {}: a module wall maps to an N_* node", s.id));
            }
            _ => {}
        }
        if s.material.trim().is_empty() && !s.kind.is_open() {
            v.push(format!("surface {}: wall material not registered", s.id));
        }
        match &s.transmission {
            Some(_) if !s.kind.is_open() => v.push(format!("surface {}: transmission only on open ends", s.id)),
            Some(Transmission::Registered { tau }) if !(tau.is_finite() && (0.0..=1.0).contains(tau)) => {
                v.push(format!("surface {}: tau outside [0, 1]", s.id))
            }
            Some(Transmission::SantelerTube { length_m, radius_m })
                if !(length_m.is_finite() && *length_m >= 0.0 && pos(*radius_m)) =>
            {
                v.push(format!("surface {}: Santeler tube needs length >= 0 and radius > 0", s.id))
            }
            _ => {}
        }
    }
    if n_ec > 1 {
        v.push("at most one ELECTRON_COLLECTOR".into());
    }
    v
}

fn coef_of(x: &Registered<f64>) -> Result<Coef, String> {
    if !(x.value.is_finite() && (0.0..=1.0).contains(&x.value)) {
        return Err(format!("{} outside [0, 1]", x.value));
    }
    Ok(match x.evidence.uncertainty {
        Some(UncertaintyRepr::PhysicalBound { lo, hi }) => Coef::Vertices(vec![lo, hi]),
        _ => Coef::Sourced(x.value),
    })
}

/// SG-01 closed form of Q_j^kin = L_j + C_j [W] (LC-17), with drop = phi_p - V_j (the floating drop for zero-current
/// surfaces).
pub fn sg01_closed_form(area: f64, gamma_e: f64, gamma_z: f64, t_e: f64, drop: f64) -> f64 {
    E_CHARGE * area * (gamma_e * (2.0 * t_e + (-drop).max(0.0)) + gamma_z * (0.5 * t_e + drop.max(0.0)))
}

impl EvalV2<'_> {
    #[allow(clippy::too_many_lines)]
    fn run(mut self) -> IcpResultV2 {
        let c = self.c;
        let m = self.m;
        self.flags.insert("MAXWELLIAN_ASSUMED".into());
        self.verify.insert("VER-01".into());
        let mut g = Gate::default();
        let mut og = OutGates::default();

        // (0) retired inputs (FC-19).
        if let Some(NeutralSourceV2::FlowBalance { f_in: Some(_), .. }) = &c.neutral_source {
            g.plasma.push(r("INPUT_RETIRED_V2:f_in", S_ME, "IN-12 v2: f_in is retired (OQ-NPICP-14)"));
        }
        if c.bus.as_ref().is_some_and(|b| b.eta_bias.is_some()) {
            g.plasma.push(r("INPUT_RETIRED_V2:eta_bias", S_ME, "IN-19 v2: eta_bias is retired (BUS2-03)"));
        }
        // (1) shared registration (v1 code, unchanged) on a v1-shaped view.
        let view = view_case(c);
        let recs = evidence_list(c);
        let mut ev = Evaluator {
            m: &m.v1,
            case: &view,
            num: self.num,
            flags: std::mem::take(&mut self.flags),
            verify: std::mem::take(&mut self.verify),
        };
        let set = ev.registration_common(&recs, &mut g);
        self.flags = ev.flags;
        self.verify = ev.verify;
        // (1b) v2 gates.
        self.gate_b(&mut g, &mut og);
        let geo_ok = self.gate_geometry(set.as_ref(), &mut g, &mut og);
        let coefs = self.gate_neutrals_and_walls(set.as_ref(), &mut g);
        let ft = set.as_ref().map(|s| {
            let d0: BTreeMap<String, f64> =
                c.dissociation_energies_ev.iter().map(|(k, v)| (k.clone(), v.value)).collect();
            formation_table(s, &d0)
        });
        if let Some(ft) = &ft {
            for (k, v) in &c.dissociation_energies_ev {
                if !ok_pos(v.value) {
                    g.plasma.push(r(&format!("IN-25_D0_INVALID:{k}"), S_ME, format!("{}", v.value)));
                }
            }
            for mol in &ft.missing_d0 {
                og.partition.push(r(
                    &format!("IN-25_D0_NOT_REGISTERED:{mol}"),
                    S_IE,
                    "FC-29: the partition keys need a registered D0; the solve and I_e,cap are unaffected",
                ));
            }
            if let Some(set) = &set {
                for (i, s) in set.species.iter().enumerate() {
                    if s.charge > 0 && ft.e_form_ev[i].is_none() && ft.missing_d0.is_empty() {
                        og.partition.push(r(
                            &format!("EQ-18_NO_FORMATION_ROUTE:{}", s.name),
                            S_IE,
                            "no registered formation route for this ion",
                        ));
                    }
                }
            }
        }
        self.gate_bus(&mut g, &mut og);
        self.gate_screen(&mut g);
        // Coupling-mode gates of the RF-chain keys (the shared part filled g.coupling for CM-ABS).
        og.coupling = g.coupling.clone();
        if c.coupling_mode == CouplingMode::Calibrated {
            if let Some(CouplingEvidence::P2Point { point }) = &c.coupling_evidence {
                if point.value.plane_convention == PlaneConvention::RVac {
                    og.coupling.push(r("LUMPED_R_VAC", S_NE, "line and match loss lumped into Q_icp_coil_ohmic_W"));
                }
            }
        }

        // (2) prepare and (3) solve members.
        let mut prepared: Option<(PreparedCase, Option<Calibrated>)> = None;
        if g.plasma.is_empty() && geo_ok {
            if let Some(set) = &set {
                match self.prepare(set) {
                    Ok(x) => prepared = Some(x),
                    Err(rs) => g.plasma.extend(rs),
                }
            }
        }
        if prepared.is_none() && g.plasma.is_empty() {
            g.plasma.push(r("INTERNAL_NO_PREPARED_CASE", S_ME, "registration passed without a prepared case"));
        }
        let specs = self.solve_specs(set.as_ref(), prepared.as_ref().map(|x| &x.0), &coefs);
        let mut members = Vec::new();
        let mut thermal_members = Vec::new();
        let mut bus_records = Vec::new();
        let mut all_reasons: Vec<Reason> = g.plasma.clone();
        for spec in &specs {
            let (sm, tms, bus) = self.member(spec, set.as_ref(), prepared.as_ref(), ft.as_ref(), &coefs, &g, &og);
            for x in &sm.reasons {
                if !all_reasons.iter().any(|y| &y.code == x) {
                    let st = if sm.status.is_converged() { S_NE } else { sm.status };
                    all_reasons.push(r(x, st, format!("solve member {}", sm.solve_member_id)));
                }
            }
            members.push(sm);
            thermal_members.extend(tms);
            bus_records.push(bus);
        }
        if specs.is_empty() {
            let (sm, tms, bus) = self.withheld_member("NONE", &g.plasma, &og);
            members.push(sm);
            thermal_members.extend(tms);
            bus_records.push(bus);
        }
        // Conservation breaches anywhere are reasons of the case (step 5).
        for tm in &thermal_members {
            for ck in tm.closures.iter().filter(|k| k.status == S_ME || k.status == S_OOD) {
                all_reasons.push(r(&ck.id, ck.status, format!("{}: {}", tm.scenario_member_id, ck.detail)));
            }
        }
        for b in &bus_records {
            for ck in b.checks.iter().filter(|k| k.status == S_ME || k.status == S_OOD) {
                all_reasons.push(r(&ck.id, ck.status, format!("{}: {}", b.solve_member_id, ck.detail)));
            }
        }
        all_reasons.extend(og.magnetized.iter().cloned());
        all_reasons.sort();
        all_reasons.dedup();
        let status = if all_reasons.is_empty() { S_CONV } else { worst_of(&all_reasons) };
        if self.flags.contains("SYNTHETIC_TEST_ONLY") {
            self.flags.insert("SYNTHETIC_TEST_ONLY".into());
        }
        let thermal = self.thermal_record(thermal_members);
        let hall = self.hall_pair(&members, &g);
        let feed = self.feed_record(set.as_ref(), &g);
        let cpl = cpl_hall_on(
            m,
            &HallMemberSource::Ensemble,
            &CplInputs { b_icp_t: c.b_icp_max_t.as_ref().map(|b| b.value), circuit_topology_record: None },
        );
        let mut scenario_sets =
            vec!["ED-08 solve members (chemistry variant x gamma vertices x H members)".to_string()];
        scenario_sets.push("ED-08 partition members (X x N x A x beta x end-split vertices)".into());
        IcpResultV2 {
            schema: "abep_icp_raw_output_v2".into(),
            case_id: c.case_id.clone(),
            model_version: MODEL_VERSION_V2.into(),
            supply_mode: c.supply_mode.value.as_str().into(),
            gas_mode: c.gas_mode.value.as_str().into(),
            configuration: c.configuration.as_str().into(),
            coupling_mode: c.coupling_mode.as_str().into(),
            status,
            reasons: all_reasons,
            flags: self.flags.clone(),
            verify_items_on_path: self.verify.clone(),
            verification_status: "IMPLEMENTED_UNVERIFIED".into(),
            validation_status: "NOT_VALIDATED".into(),
            validation_cell_id: c.validation_cell_id.clone(),
            volume_mode: c.geometry.as_ref().map(|g| match g.value.volume_mode {
                VolumeModeV2::AssumedGeometricTube => "ASSUMED_GEOMETRIC_TUBE".to_string(),
                VolumeModeV2::RegisteredEffective { .. } => "REGISTERED_EFFECTIVE".to_string(),
            }),
            solve_members: members,
            if_icp_thermal_v2: thermal,
            if_icp_bus_v2: bus_records,
            if_icp_hall_v1: hall,
            if_icp_feed_v1: feed,
            cpl_hall_on_v1: cpl,
            uncertainty: UncertaintyV2 {
                sampled_envelope: Label::withheld(
                    S_NE,
                    vec!["UQ-03_SAMPLING_NEEDS_ADMITTED_ABEP_RNG (SC-WP-10)".into()],
                ),
                u_model_form: Label::withheld(S_NE, vec!["UQ-05_NO_VALIDATION_RESIDUALS".into()]),
                scenario_sets,
            },
            provenance: self.provenance(),
        }
    }

    // ------------------------------------------------------------------------------------------------- v2 gates

    fn gate_b(&mut self, g: &mut Gate, og: &mut OutGates) {
        match &self.c.b_icp_max_t {
            None => g.plasma.push(r("DOM-06_B_ICP_NOT_REGISTERED", S_IE, "B_ICP,max absent (VI-HD-06; NE-11)")),
            Some(b) if !(b.value.is_finite() && b.value >= 0.0) => {
                g.plasma.push(r("DOM-06_B_ICP_INVALID", S_ME, format!("{}", b.value)))
            }
            Some(b) if b.value > 0.0 => {
                og.magnetized.push(r(
                    "DOM-06_NO_SOURCED_MAGNETIZATION_CRITERION",
                    S_IE,
                    format!("B_ICP,max = {} T > 0: diagnostics reported, every plasma / capacity / partition output withheld (FC-14 v2)", b.value),
                ));
                self.flags.insert("DIAGNOSTIC_UNMAGNETIZED_SOLVE".into());
            }
            Some(_) => {}
        }
    }

    /// IN-10 v2, IN-11 / IN-26, IN-17 v2 and the composition domain. Returns false when no geometry is usable.
    fn gate_geometry(&mut self, set: Option<&ChemistrySet>, g: &mut Gate, og: &mut OutGates) -> bool {
        let c = self.c;
        let geo = match &c.geometry {
            None => {
                g.plasma.push(r("IN-10_GEOMETRY_NOT_REGISTERED", S_IE, "ICP geometry F6-X-01..05, 10..17 TBD (NE-01)"));
                None
            }
            Some(gr) => {
                for x in geometry_v2_violations(&gr.value) {
                    g.plasma.push(r("IN-10_GEOMETRY_CONTRACT", S_ME, x));
                }
                if gr.value.volume_mode == VolumeModeV2::AssumedGeometricTube {
                    self.flags.insert("ASSUMED_GEOMETRIC_TUBE".into());
                    if self.m.registered_effective_volumes.contains(&gr.value.geometry_id) {
                        g.plasma.push(r(
                            "DOM-16_REGISTERED_EFFECTIVE_VOLUME_EXISTS",
                            S_ME,
                            format!(
                                "{}: a REGISTERED_EFFECTIVE record supersedes the assumed tube",
                                gr.value.geometry_id
                            ),
                        ));
                    }
                }
                Some(&gr.value)
            }
        };
        match (&c.electrodes, geo) {
            (None, _) => g.plasma.push(r(
                "IN-11_ELECTRODES_NOT_REGISTERED",
                S_IE,
                "P1-IT-36 extraction topology not registered; ICD ICP-21 TBD",
            )),
            (Some(e), Some(geo)) => {
                for s in geo.surfaces.iter().filter(|s| s.kind.is_biased()) {
                    match e.value.potentials_v.get(&s.id) {
                        None => g.plasma.push(r(&format!("IN-11_POTENTIAL_NOT_REGISTERED:{}", s.id), S_IE, "")),
                        Some(v) if !v.is_finite() => g.plasma.push(r("IN-11_POTENTIAL_INVALID", S_ME, s.id.clone())),
                        _ => {}
                    }
                    match e.value.supplies.get(&s.id) {
                        None => og.bias_bus.push(r(
                            &format!("IN-26_SUPPLY_IDENTITY_NOT_REGISTERED:{}", s.id),
                            S_NE,
                            "P1-IT-36, ICD ICP-21",
                        )),
                        Some(SupplyIdentity::GroundFacilityOnly) => {
                            self.flags.insert("INCLUDES_GROUND_FACILITY_SUPPLY".into());
                        }
                        Some(SupplyIdentity::HallDischargeLoop) if c.configuration == Configuration::CapOff => {
                            g.plasma.push(r(
                                "IN-26_HALL_LOOP_IN_CFG_CAP_OFF",
                                S_ME,
                                format!("{}: HALL_DISCHARGE_LOOP exists only in CPL-HALL-ON", s.id),
                            ))
                        }
                        Some(_) => {}
                    }
                }
                for k in e.value.potentials_v.keys().chain(e.value.supplies.keys()) {
                    if !geo.surfaces.iter().any(|s| &s.id == k && s.kind.is_biased()) {
                        g.plasma.push(r("IN-11_POTENTIAL_ON_UNBIASED_SURFACE", S_ME, k.clone()));
                    }
                }
                if e.value.reference.trim().is_empty() {
                    g.plasma.push(r("IN-11_REFERENCE_NOT_REGISTERED", S_IE, ""));
                }
                match &e.value.collector_bias_sweep_v {
                    None => g.sat.push(r("EQ-11_BIAS_RANGE_NOT_REGISTERED", S_NE, "V_bias range up to V_bias,max")),
                    Some(sw) if sw.is_empty() || sw.iter().any(|v| !v.is_finite()) => {
                        g.sat.push(r("EQ-11_BIAS_RANGE_INVALID", S_ME, "empty or non-finite sweep"))
                    }
                    Some(_) if !geo.surfaces.iter().any(|s| s.kind == SurfaceKind::ElectronCollector) => {
                        g.sat.push(r("EQ-11_NO_ELECTRON_COLLECTOR", S_NE, "no electron sink registered"))
                    }
                    Some(_) => {}
                }
            }
            (Some(_), None) => {}
        }
        match (&c.h_model, geo, set) {
            (None, _, _) => g.plasma.push(r(
                "IN-17_NO_EDGE_FACTOR_SOURCE",
                S_IE,
                "no ion-neutral cross section or explicit h registered (CHG-06)",
            )),
            (Some(HModel::Explicit { h_by_surface }), Some(geo), _) => {
                for s in &geo.surfaces {
                    match h_by_surface.get(&s.id) {
                        None => g.plasma.push(r(&format!("IN-17_H_NOT_REGISTERED:{}", s.id), S_IE, "")),
                        Some(h) if !(h.value.is_finite() && h.value > 0.0 && h.value <= 1.0) => {
                            g.plasma.push(r("IN-17_H_INVALID", S_ME, format!("{}: h = {}", s.id, h.value)))
                        }
                        _ => {}
                    }
                }
            }
            (Some(HModel::Lieberman { sigma_i_m2 }), Some(geo), Some(set)) => {
                self.flags.insert("H_LIEB_ARGON_STATEMENT_EXTRAPOLATED".into());
                let mut vals = BTreeSet::new();
                for i in set.species.iter().filter(|s| s.charge > 0) {
                    match sigma_i_m2.get(&i.name) {
                        None => g.plasma.push(r(&format!("CHG-06_SIGMA_I_NOT_REGISTERED:{}", i.name), S_IE, "")),
                        Some(s) if !ok_pos(s.value) => g.plasma.push(r("IN-17_SIGMA_INVALID", S_ME, i.name.clone())),
                        Some(s) => {
                            vals.insert(s.value.to_bits());
                        }
                    }
                }
                if vals.len() > 1 {
                    self.flags.insert("MULTI_ION_H_ENVELOPE".into());
                }
                if geo.surfaces.iter().any(|s| s.kind.is_open()) {
                    self.verify.insert("VER-07".into());
                }
                if c.b_icp_max_t.as_ref().is_some_and(|b| b.value != 0.0) {
                    g.plasma.push(r("DOM-05", S_OOD, "H-LIEB requires B = 0"));
                }
            }
            _ => {}
        }
        let mut comp: Vec<&String> = Vec::new();
        match &c.neutral_source {
            Some(NeutralSourceV2::RegisteredPressure { mole_fractions, .. }) => {
                comp.extend(mole_fractions.value.iter().filter(|(_, x)| **x > 0.0).map(|(k, _)| k));
            }
            Some(NeutralSourceV2::FlowBalance { inflow: InflowV2::MeasuredDedicatedFeed { mdot_kg_s }, .. }) => {
                comp.extend(mdot_kg_s.value.iter().filter(|(_, x)| **x > 0.0).map(|(k, _)| k));
            }
            Some(NeutralSourceV2::FlowBalance { inflow: InflowV2::UpstreamModel { gamma_in_per_s, .. }, .. }) => {
                comp.extend(gamma_in_per_s.value.iter().filter(|(_, x)| **x > 0.0).map(|(k, _)| k));
            }
            _ => {}
        }
        let is_xe = |k: &String| k.to_ascii_uppercase().starts_with("XE");
        if comp.iter().any(|k| is_xe(k)) && comp.iter().any(|k| !is_xe(k)) {
            g.plasma.push(r("FC-CHEM-09_MIXED_XE_AIR_COMPOSITION", S_OOD, "mixed Xe / air composition (OQ-CHEM-10)"));
        }
        geo.is_some()
    }

    /// IN-12 v2, IN-13 v2 (PF-02, DOM-14, DOM-17, DOM-18) and IN-18 v2. Returns the wall coefficients.
    fn gate_neutrals_and_walls(&mut self, set: Option<&ChemistrySet>, g: &mut Gate) -> WallCoefs {
        let c = self.c;
        let geo = c.geometry.as_ref().map(|x| &x.value);
        let flight = matches!(c.supply_mode.value, SupplyMode::AirPrimary | SupplyMode::XeContingency);
        match &c.neutral_source {
            None => g.plasma.push(r("IN-12_NEUTRAL_SOURCE_NOT_REGISTERED", S_IE, "VI-GAS-03 / VI-GAS-04 TBD")),
            Some(NeutralSourceV2::RegisteredPressure { p_icp_pa, t_g_k, mole_fractions }) => {
                if !ok_pos(p_icp_pa.value) || !ok_pos(t_g_k.value) {
                    g.plasma.push(r("IN-12_DOMAIN", S_OOD, "p_ICP and T_g must be > 0"));
                }
                if matches!(c.h_model, Some(HModel::Lieberman { .. })) && p_icp_pa.value >= P_100_MTORR_PA {
                    g.plasma.push(r("DOM-05", S_OOD, format!("p_ICP = {} Pa >= 100 mTorr", p_icp_pa.value)));
                }
                if p_icp_pa.evidence.quantity_type == Some(QuantityType::Measured) {
                    self.flags.insert("P_ICP_MEASURED".into());
                }
                if let Some(set) = set {
                    let mut sum = 0.0;
                    for (k, x) in &mole_fractions.value {
                        match set.species.iter().find(|s| &s.name == k) {
                            Some(s) if s.charge == 0 => {}
                            _ => g.plasma.push(r(
                                &format!("IN-05_SPECIES_WITHOUT_CHEMISTRY:{k}"),
                                S_IE,
                                "delivered species without registered chemistry",
                            )),
                        }
                        if !(x.is_finite() && *x >= 0.0) {
                            g.plasma.push(r("IN-05_MOLE_FRACTION_INVALID", S_ME, k.clone()));
                        }
                        sum += x;
                    }
                    if (sum - 1.0).abs() > 1e-12 {
                        g.plasma.push(r("IN-05_MOLE_FRACTIONS_DO_NOT_SUM_TO_ONE", S_ME, format!("sum = {sum}")));
                    }
                }
            }
            Some(NeutralSourceV2::FlowBalance { t_g_k, sigma_c_m2, inflow, .. }) => {
                if !ok_pos(t_g_k.value) {
                    g.plasma.push(r("IN-12_DOMAIN", S_OOD, "T_g > 0 required"));
                }
                let admitted = match inflow {
                    InflowV2::UpstreamModel { model_id, .. } => self.m.admitted_upstream_models.contains(model_id),
                    _ => false,
                };
                if flight && !admitted {
                    g.plasma.push(r(
                        "FLOW_BALANCE_UPSTREAM_MODEL_NOT_ADMITTED",
                        S_NE,
                        "DOM-14 / FC-24: flight FLOW_BALANCE needs an admitted upstream conductance / feed model",
                    ));
                }
                let synthetic = c.supply_mode.value == SupplyMode::SyntheticTestOnly;
                if let InflowV2::UpstreamModel { model_id, .. } = inflow {
                    if !admitted && !synthetic && !flight {
                        g.plasma.push(r(
                            "FLOW_BALANCE_UPSTREAM_MODEL_NOT_ADMITTED",
                            S_NE,
                            format!("{model_id} is not admitted (DOM-14)"),
                        ));
                    }
                }
                let per_species = match inflow {
                    InflowV2::NoInflow => None,
                    InflowV2::MeasuredDedicatedFeed { mdot_kg_s } => Some(&mdot_kg_s.value),
                    InflowV2::UpstreamModel { gamma_in_per_s, .. } => Some(&gamma_in_per_s.value),
                };
                if let (Some(map), Some(set)) = (per_species, set) {
                    for (k, v) in map {
                        if !set.species.iter().any(|s| &s.name == k && s.charge == 0) {
                            g.plasma.push(r(&format!("IN-05_SPECIES_WITHOUT_CHEMISTRY:{k}"), S_IE, ""));
                        }
                        if !(v.is_finite() && *v >= 0.0) {
                            g.plasma.push(r("IN-12_INFLOW_INVALID", S_ME, k.clone()));
                        }
                    }
                }
                match &c.background {
                    None => g.plasma.push(r("IN-13_BACKGROUND_NOT_REGISTERED", S_IE, "no facility / exposure record")),
                    Some(b) => match &b.value {
                        BackgroundV2::FlightAmbient { exposure_model_id } => {
                            let reg =
                                exposure_model_id.as_ref().is_some_and(|x| self.m.flight_exposure_models.contains(x));
                            if !reg {
                                g.plasma.push(r(
                                    "DOM-17_FLIGHT_AMBIENT_WITHOUT_EXPOSURE_MODEL",
                                    S_IE,
                                    "FC-18: a directed flight ambient needs a registered exposure model",
                                ));
                            } else {
                                g.plasma.push(r(
                                    "DOM-17_EXPOSURE_MODEL_FORM_NOT_IMPLEMENTED",
                                    S_NE,
                                    "no registered exposure-model inflow form exists in prereg v2",
                                ));
                            }
                        }
                        BackgroundV2::IsotropicMaxwellian { n_b_m3, t_b_k } => {
                            if !ok_pos(*t_b_k) || n_b_m3.values().any(|v| !(v.is_finite() && *v >= 0.0)) {
                                g.plasma.push(r("IN-13_DOMAIN", S_OOD, "T_b > 0 and n_b >= 0"));
                            }
                            let u = |e: &EvidenceRecord| {
                                e.uncertainty.as_ref().and_then(UncertaintyRepr::standard_uncertainty)
                            };
                            let any_bg = n_b_m3.values().any(|v| *v > 0.0);
                            let dt = (t_b_k - t_g_k.value).abs();
                            let within = match (u(&b.evidence), u(&t_g_k.evidence)) {
                                (Some(a), Some(bb)) => dt <= (a * a + bb * bb).sqrt(),
                                _ => dt == 0.0,
                            };
                            if any_bg && !within {
                                self.flags.insert("NON_ISOTHERMAL_PASSAGE".into());
                                self.verify.insert("VER-20".into());
                            }
                        }
                    },
                }
                if let Some(set) = set {
                    for s in set.species.iter().filter(|s| s.charge == 0) {
                        if !sigma_c_m2.contains_key(&s.name) {
                            g.plasma.push(r(&format!("DOM-04_SIGMA_C_NOT_REGISTERED:{}", s.name), S_IE, ""));
                        }
                    }
                }
                if let Some(geo) = geo {
                    let open: Vec<_> = geo.surfaces.iter().filter(|s| s.kind.is_open()).collect();
                    if open.is_empty() {
                        g.plasma.push(r("EQ-02_NO_OPEN_END", S_ME, "FLOW_BALANCE needs an outflow boundary"));
                    }
                    for s in open {
                        if s.transmission.is_none() {
                            g.plasma.push(r(&format!("IN-12_TAU_NOT_REGISTERED:{}", s.id), S_IE, ""));
                        }
                    }
                }
            }
        }
        let mut coefs = WallCoefs::default();
        let mats: BTreeSet<&str> = geo
            .map(|g| g.surfaces.iter().filter(|s| !s.kind.is_open()).map(|s| s.material.as_str()).collect())
            .unwrap_or_default();
        for w in &c.wall_coefficients {
            if set.is_some_and(|s| !s.species.iter().any(|x| x.name == w.species)) {
                g.plasma.push(r("IN-18_UNKNOWN_SPECIES", S_ME, w.species.clone()));
            }
            if geo.is_some() && !mats.contains(w.material.as_str()) {
                g.plasma.push(r("IN-18_UNKNOWN_MATERIAL", S_ME, w.material.clone()));
            }
            let key = (w.species.clone(), w.material.clone());
            for (name, x, map) in [
                ("gamma", &w.gamma, &mut coefs.gamma),
                ("beta", &w.beta, &mut coefs.beta),
                ("quench", &w.quench, &mut coefs.quench),
            ] {
                if let Some(x) = x {
                    match coef_of(x) {
                        Ok(cf) => {
                            if matches!(cf, Coef::Vertices(_)) {
                                self.flags.insert("BOUNDED_BY_PHYSICAL_LIMITS".into());
                            }
                            map.insert(key.clone(), cf);
                        }
                        Err(e) => g.plasma.push(r(&format!("IN-18_{name}_INVALID"), S_ME, e)),
                    }
                }
            }
        }
        coefs
    }

    fn gate_bus(&mut self, g: &mut Gate, og: &mut OutGates) {
        let c = self.c;
        match &c.bus {
            None => og.bus.push(r("NE-09_IN-19_NOT_REGISTERED", S_NE, "eta_RF / P_match,DC / variants not registered")),
            Some(b) => {
                if b.boundary_id != ACTIVE_BUS_BOUNDARY {
                    og.bus.push(r(
                        "A9.30_BUS_BOUNDARY",
                        S_ME,
                        format!("{} is not {ACTIVE_BUS_BOUNDARY}", b.boundary_id),
                    ));
                }
                if !(b.eta_rf.value.is_finite() && b.eta_rf.value > 0.0 && b.eta_rf.value <= 1.0) {
                    og.bus.push(r("CC-06_REGISTRATION_REFUSED", S_ME, format!("eta_RF = {}", b.eta_rf.value)));
                }
                if !(b.p_match_dc_w.value.is_finite() && b.p_match_dc_w.value >= 0.0) {
                    og.bus.push(r("CC-06_REGISTRATION_REFUSED", S_ME, "P_match,DC must be finite and >= 0"));
                }
                for (n, s) in [("icp_assist_magnet", &b.assist_magnet), ("flow_control_icp_feed", &b.flow_control)] {
                    if let VariantSlot::Installed { p_w } = s {
                        if !(p_w.value.is_finite() && p_w.value >= 0.0) {
                            og.bus.push(r("CC-06_REGISTRATION_REFUSED", S_ME, format!("{n} must be >= 0")));
                        }
                    }
                }
                if b.ground_facility_rf_generator {
                    self.flags.insert("INCLUDES_GROUND_FACILITY_SUPPLY".into());
                }
            }
        }
        if c.configuration == Configuration::FlightHallOn {
            og.bus.push(r("BUS2-04_CPL_HALL_ON_NOT_EVALUATED", S_NE, "flight bus records need CPL-HALL-ON"));
        }
        // IF-ICP-HALL-v1 demand gates (inherited FC-01 / FC-02).
        match &c.hall_demand {
            None => {
                if self.m.v1.ensemble_member_count == 0 {
                    g.hall.push(r("CREDIBLE_HALL_TRANSPORT_SET_EMPTY", S_NE, "transport_ensemble_v0 members = []"));
                }
                g.hall.push(r("I_D_MAX_H1_NOT_REGISTERED", S_NE, "P1-IT-07 not registered"));
            }
            Some(h) => match h.basis {
                HallDemandBasis::MeasuredRegistration => {}
                HallDemandBasis::AdmittedHallMember if self.m.v1.ensemble_member_count == 0 => {
                    g.hall.push(r("CREDIBLE_HALL_TRANSPORT_SET_EMPTY", S_NE, "no admitted member"))
                }
                HallDemandBasis::AdmittedHallMember => {}
                HallDemandBasis::ScreeningCandidate => {
                    g.hall.push(r("IF-ICP-HALL-v1_SCREENING_CANDIDATE_REFUSED", S_ME, "never a screening candidate"))
                }
                HallDemandBasis::SupplyRating => {
                    g.hall.push(r("IF-ICP-HALL-v1_SUPPLY_RATING_REFUSED", S_ME, "never the 8.33 A stand ceiling"))
                }
            },
        }
        if c.gas_mode.value != GasMode::GReuse && c.dedicated_flow_kg_s.is_none() {
            g.dedicated.push(r("IF-ICP-FEED-v1_DEDICATED_FLOW_NOT_REGISTERED", S_NE, c.gas_mode.value.as_str()));
        }
    }

    /// CS-05 / FC-25: an UNBOUNDED_OMISSION of the CA-ICP-v1 screen blocks the chemistry-dependent outputs of its mode.
    fn gate_screen(&mut self, g: &mut Gate) {
        let mode = match self.c.supply_mode.value {
            SupplyMode::AirPrimary | SupplyMode::EmO2b | SupplyMode::EmN2 => "AIR",
            SupplyMode::XeContingency | SupplyMode::EmXe => "XE",
            _ => return,
        };
        for (md, process) in &self.m.chemistry_screen.unbounded_omissions {
            if md == mode {
                g.plasma.push(r(
                    &format!("CS-05_UNBOUNDED_OMISSION:{process}"),
                    S_IE,
                    "FC-25: an omitted process without a bound blocks chemistry admission for its mode",
                ));
            }
        }
    }

    // ----------------------------------------------------------------------------------------- prepare / members

    fn prepare(&mut self, set: &ChemistrySet) -> Result<(PreparedCase, Option<Calibrated>), Vec<Reason>> {
        let c = self.c;
        let geo = &c.geometry.as_ref().expect("gated").value;
        let el = &c.electrodes.as_ref().expect("gated").value;
        let surfaces: Vec<PreparedSurface> = geo
            .surfaces
            .iter()
            .map(|s| PreparedSurface {
                id: s.id.clone(),
                kind: s.kind,
                area_m2: s.area_m2,
                orientation: s.orientation,
                node: s.thermal_node,
                potential_v: if s.kind.is_biased() { el.potentials_v.get(&s.id).copied() } else { None },
                tau: s.transmission.as_ref().map(|t| match t {
                    Transmission::Registered { tau } => *tau,
                    Transmission::SantelerTube { length_m, radius_m } => {
                        physics::santeler_transmission(*length_m, *radius_m)
                    }
                }),
            })
            .collect();
        let h = match c.h_model.as_ref().expect("gated") {
            HModel::Explicit { h_by_surface } => {
                PreparedH::Explicit(geo.surfaces.iter().map(|s| h_by_surface[&s.id].value).collect())
            }
            // Replaced per solve member (H-LIEB / H-MS / H-LO / H-HI).
            HModel::Lieberman { .. } => PreparedH::Lieberman { sigma_i_m2: f64::NAN },
        };
        let ns = set.species.len();
        let (neutrals, t_g) = match c.neutral_source.as_ref().expect("gated") {
            NeutralSourceV2::RegisteredPressure { p_icp_pa, t_g_k, mole_fractions } => {
                let ntot = p_icp_pa.value / (K_B * t_g_k.value);
                let n = set
                    .species
                    .iter()
                    .map(|s| {
                        if s.charge == 0 {
                            mole_fractions.value.get(&s.name).copied().unwrap_or(0.0) * ntot
                        } else {
                            0.0
                        }
                    })
                    .collect();
                (PreparedNeutrals::Fixed(n), t_g_k.value)
            }
            NeutralSourceV2::FlowBalance { t_g_k, inflow, .. } => {
                let bg = c.background.as_ref().map(|b| &b.value);
                let inflow_v = (0..ns)
                    .map(|i| {
                        let s = &set.species[i];
                        if s.charge > 0 {
                            return 0.0;
                        }
                        let feed_in = match inflow {
                            InflowV2::NoInflow => 0.0,
                            InflowV2::MeasuredDedicatedFeed { mdot_kg_s } => {
                                mdot_kg_s.value.get(&s.name).copied().unwrap_or(0.0) / s.mass_kg
                            }
                            InflowV2::UpstreamModel { gamma_in_per_s, .. } => {
                                gamma_in_per_s.value.get(&s.name).copied().unwrap_or(0.0)
                            }
                        };
                        // EQ-02 v2 (PF-02): background inflow through each open end with its tau.
                        let bg_in = match bg {
                            Some(BackgroundV2::IsotropicMaxwellian { n_b_m3, t_b_k }) => {
                                let nb = n_b_m3.get(&s.name).copied().unwrap_or(0.0);
                                if nb == 0.0 {
                                    0.0
                                } else {
                                    let vb = physics::neutral_mean_speed(*t_b_k, s.mass_kg);
                                    surfaces
                                        .iter()
                                        .filter(|x| x.kind.is_open())
                                        .map(|x| 0.25 * nb * vb * x.area_m2 * x.tau.unwrap_or(f64::NAN))
                                        .sum()
                                }
                            }
                            _ => 0.0,
                        };
                        feed_in + bg_in
                    })
                    .collect();
                (PreparedNeutrals::Flow { inflow_per_s: inflow_v }, t_g_k.value)
            }
        };
        let mut direct = Vec::with_capacity(set.reactions.len());
        for rx in &set.reactions {
            direct.push(match &rx.rate {
                crate::chemistry::RateSource::Synthetic { .. } => None,
                crate::chemistry::RateSource::RegisteredTable { file } => {
                    match self.m.v1.chem_channel_for_table(file).map(|ch| (ch, &ch.representation)) {
                        Some((ch, Representation::CrossSection { xs, .. })) => {
                            Some(DirectRate { channel: ch.id.clone(), xs: xs.clone(), validity: ch.validity.clone() })
                        }
                        _ => {
                            return Err(vec![r("INTERNAL_EQ06_GATE", S_ME, format!("{} passed the EQ-06 gate", rx.id))])
                        }
                    }
                }
            });
        }
        let mut cal = None;
        let p_abs = match (&c.coupling_mode, c.rf_input.as_ref().expect("gated")) {
            (CouplingMode::Absorbed, RfInput::AbsorbedPower { p_abs_w }) => p_abs_w.value,
            (CouplingMode::Calibrated, RfInput::Forward { p_fwd_w, p_refl_w }) => {
                let Some(CouplingEvidence::P2Point { point }) = &c.coupling_evidence else {
                    return Err(vec![r("INTERNAL_CM_CAL", S_ME, "gated")]);
                };
                let p = &point.value;
                let k = coupling::calibrated(
                    p_fwd_w.value,
                    p_refl_w.value,
                    p.z_antenna_hot_re_ohm,
                    p.z_antenna_hot_im_ohm,
                    p.r_ant_cold_ohm,
                    p.plane_convention,
                    p.q_line_w,
                    p.q_match_w,
                )?;
                let pa = k.p_abs_w;
                cal = Some(k);
                pa
            }
            _ => return Err(vec![r("INTERNAL_COUPLING_MODE", S_ME, "gated")]),
        };
        let volume = match &geo.volume_mode {
            VolumeModeV2::AssumedGeometricTube => std::f64::consts::PI * geo.radius_m * geo.radius_m * geo.length_m,
            VolumeModeV2::RegisteredEffective { volume_m3, .. } => *volume_m3,
        };
        Ok((
            PreparedCase {
                set: set.clone(),
                volume_m3: volume,
                radius_m: geo.radius_m,
                length_m: geo.length_m,
                surfaces,
                h,
                neutrals,
                t_g_k: t_g,
                p_abs_w: p_abs,
                direct,
                recombination: Vec::new(),
            },
            cal,
        ))
    }

    fn materials(&self) -> Vec<String> {
        self.c
            .geometry
            .as_ref()
            .map(|g| g.value.surfaces.iter().map(|s| s.material.clone()).collect())
            .unwrap_or_default()
    }

    /// ED-08 solve members: H members x unsourced gamma vertices (FLOW_BALANCE) x the chemistry set.
    fn solve_specs(&self, set: Option<&ChemistrySet>, p: Option<&PreparedCase>, coefs: &WallCoefs) -> Vec<SolveSpec> {
        let (Some(set), Some(p)) = (set, p) else { return vec![] };
        let c = self.c;
        let mut hs: Vec<(String, PreparedH)> = Vec::new();
        match &c.h_model {
            Some(HModel::Lieberman { sigma_i_m2 }) => {
                let ions: Vec<(usize, f64)> = set
                    .species
                    .iter()
                    .enumerate()
                    .filter(|(_, s)| s.charge > 0)
                    .map(|(i, s)| (i, sigma_i_m2[&s.name].value))
                    .collect();
                let distinct: BTreeSet<u64> = ions.iter().map(|x| x.1.to_bits()).collect();
                if distinct.len() <= 1 {
                    hs.push(("H-LIEB".into(), PreparedH::Lieberman { sigma_i_m2: ions[0].1 }));
                } else {
                    let mut per = vec![0.0; set.species.len()];
                    for (i, s) in &ions {
                        per[*i] = *s;
                    }
                    let smax = ions.iter().map(|x| x.1).fold(f64::NEG_INFINITY, f64::max);
                    let smin = ions.iter().map(|x| x.1).fold(f64::INFINITY, f64::min);
                    hs.push(("H-MS".into(), PreparedH::LiebermanPerSpecies { sigma_by_species_m2: per }));
                    hs.push(("H-LO".into(), PreparedH::Lieberman { sigma_i_m2: smax }));
                    hs.push(("H-HI".into(), PreparedH::Lieberman { sigma_i_m2: smin }));
                }
            }
            _ => hs.push(("H-EXPLICIT".into(), p.h.clone())),
        }
        let mats = self.materials();
        let mut gammas: Vec<BTreeMap<(String, String), f64>> = vec![BTreeMap::new()];
        if matches!(p.neutrals, PreparedNeutrals::Flow { .. }) {
            let mut wall_mats: Vec<String> = c
                .geometry
                .as_ref()
                .map(|g| g.value.surfaces.iter().filter(|s| !s.kind.is_open()).map(|s| s.material.clone()).collect())
                .unwrap_or_default();
            wall_mats.sort();
            wall_mats.dedup();
            for (a, sp) in set.species.iter().enumerate() {
                if parent_molecule(set, a).is_none() {
                    continue;
                }
                for mm in &wall_mats {
                    let opts = coefs.gamma(&sp.name, mm).options();
                    gammas = gammas
                        .into_iter()
                        .flat_map(|gm| {
                            opts.iter().map(move |v| {
                                let mut x = gm.clone();
                                x.insert((sp.name.clone(), mm.clone()), *v);
                                x
                            })
                        })
                        .collect();
                }
            }
        }
        let _ = mats;
        let mut out = Vec::new();
        for (hl, h) in &hs {
            for gm in &gammas {
                let gl: Vec<String> = gm.iter().map(|((s, m), v)| format!("{s}@{m}={v}")).collect();
                out.push(SolveSpec {
                    id: format!("CHEM={};H={hl};GAMMA=[{}]", set.set_id, gl.join(",")),
                    h_label: hl.clone(),
                    h: h.clone(),
                    gamma: gm.clone(),
                });
            }
        }
        out
    }

    fn recombination(&self, p: &PreparedCase, gamma: &BTreeMap<(String, String), f64>) -> Vec<Recombination> {
        let mats = self.materials();
        let mut out = Vec::new();
        for (a, sp) in p.set.species.iter().enumerate() {
            let Some(mol) = parent_molecule(&p.set, a) else { continue };
            let ga: f64 = p
                .surfaces
                .iter()
                .zip(&mats)
                .filter(|(s, _)| !s.kind.is_open())
                .map(|(s, mm)| gamma.get(&(sp.name.clone(), mm.clone())).copied().unwrap_or(0.0) * s.area_m2)
                .sum();
            if ga > 0.0 {
                out.push(Recombination { atom: a, molecule: mol, gamma_area_m2: ga });
            }
        }
        out
    }

    /// A member that cannot be solved: every output withheld with the registration reasons.
    fn withheld_member(
        &self,
        id: &str,
        why: &[Reason],
        og: &OutGates,
    ) -> (SolveMemberV2, Vec<ThermalMemberV2>, BusRecordV2) {
        let st = max_sev(worst_of(why));
        let sm = SolveMemberV2 {
            solve_member_id: id.into(),
            h_member: "-".into(),
            gamma: BTreeMap::new(),
            status: st,
            reasons: codes(why),
            plasma_state: Label::withheld(st, codes(why)),
            outputs: BTreeMap::from([("I_e_cap_A".to_string(), OutputValue::Scalar(withheld("A", why)))]),
            equilibria: vec![],
            domain_checks: vec![],
            conservation: vec![],
            diagnostics: BTreeMap::new(),
        };
        let keys = self.keys_withheld(why);
        let tm = ThermalMemberV2 {
            scenario_member_id: format!("{id}/P:WITHHELD"),
            solve_member_id: id.into(),
            partition_member_id: "WITHHELD".into(),
            status: st,
            reasons: codes(why),
            keys,
            node_shares_w: BTreeMap::new(),
            surfaces: BTreeMap::new(),
            coil_ohmic_split_w: BTreeMap::new(),
            class_energy_w: BTreeMap::new(),
            route_excess_w: BTreeMap::new(),
            closures: vec![],
        };
        let mut bus_why = why.to_vec();
        bus_why.extend(og.bus.iter().cloned());
        let bus = self.bus_record(id, None, None, None, &bus_why, og);
        (sm, vec![tm], bus)
    }

    fn keys_withheld(&self, why: &[Reason]) -> BTreeMap<String, ThermalKeyV2> {
        THERMAL_KEYS.iter().map(|k| (k.to_string(), self.key(k, withheld("W", why)))).collect()
    }

    fn key(&self, k: &str, q: Quantity) -> ThermalKeyV2 {
        let row = self.m.key_row(k).expect("registered key");
        ThermalKeyV2 {
            id: row.id.clone(),
            role: row.role.clone(),
            plane: row.plane.clone(),
            powered_by: row.powered_by.clone(),
            q,
        }
    }

    #[allow(clippy::too_many_arguments, clippy::too_many_lines)]
    fn member(
        &mut self,
        spec: &SolveSpec,
        set: Option<&ChemistrySet>,
        prepared: Option<&(PreparedCase, Option<Calibrated>)>,
        ft: Option<&FormationTable>,
        coefs: &WallCoefs,
        g: &Gate,
        og: &OutGates,
    ) -> (SolveMemberV2, Vec<ThermalMemberV2>, BusRecordV2) {
        let (Some(_), Some((base, cal))) = (set, prepared) else {
            return self.withheld_member(&spec.id, &g.plasma, og);
        };
        let mut p = base.clone();
        p.h = spec.h.clone();
        p.recombination = self.recombination(&p, &spec.gamma);
        let mut reasons: Vec<Reason> = Vec::new();
        let outcome = solver::solve(&p, self.num);
        let mut equilibria = Vec::new();
        let mut eq: Option<Equilibrium> = None;
        let mut trivial: Option<Vec<f64>> = None;
        let plasma_state;
        match outcome {
            Err(f) => {
                reasons.push(r(&f.code, S_ME, f.detail.clone()));
                plasma_state = Label::withheld(S_ME, vec![f.code]);
            }
            Ok(SolveOutcome::NotSustained) => {
                if p.p_abs_w > 0.0 {
                    reasons.push(r(
                        "CC-05_ABSORBED_POWER_WITHOUT_SINK",
                        S_ME,
                        format!("P_abs = {} W > 0 but no sustained state exists", p.p_abs_w),
                    ));
                    plasma_state = Label::withheld(S_ME, vec!["CC-05_ABSORBED_POWER_WITHOUT_SINK".into()]);
                } else {
                    plasma_state = Label::value("NOT_SUSTAINED");
                    trivial = Some(solver::trivial_neutrals(&p));
                }
            }
            Ok(SolveOutcome::Equilibria(mut eqs)) => {
                for e in &eqs {
                    equilibria.push(EquilibriumRecord {
                        regime: e.regime.id.clone(),
                        t_e_ev: e.kin.t_e,
                        n_e_m3: e.kin.n_e,
                        phi_p_v: e.phi_p_v,
                        electron_saturated_surfaces: e
                            .surfaces
                            .iter()
                            .zip(&p.surfaces)
                            .filter(|(s, ps)| s.electron_saturated && ps.potential_v.is_some())
                            .map(|(_, ps)| ps.id.clone())
                            .collect(),
                        domain_status: S_CONV,
                        domain_reasons: vec![],
                    });
                }
                if eqs.len() == 1 {
                    let e = eqs.remove(0);
                    let er = (e.p_loss_w - p.p_abs_w).abs() / p.p_abs_w.max(e.p_loss_w);
                    let res = [e.kin.balance_residual, e.quasi_residual.abs(), er];
                    if res.iter().any(|x| !(x.is_finite() && *x <= TOL_SOLVE)) {
                        reasons.push(r("TOL-SOLVE_NOT_MET", S_ME, format!("residuals {res:?}")));
                    }
                    plasma_state = Label::value("SUSTAINED");
                    eq = Some(e);
                } else {
                    reasons.push(r(
                        "EQUILIBRIUM_SELECTION_NOT_REGISTERED",
                        S_NE,
                        format!("{} equilibria found and reported; no root is chosen silently", eqs.len()),
                    ));
                    plasma_state = Label::withheld(S_NE, vec!["EQUILIBRIUM_SELECTION_NOT_REGISTERED".into()]);
                }
            }
        }
        let (domain_checks, mut conservation) = match (&eq, &trivial) {
            (Some(e), _) => (self.domain_checks(&p, Some(e)), self.conservation(&p, Some(e), None)),
            (None, Some(n)) => (self.domain_checks(&p, None), self.conservation(&p, None, Some(n))),
            _ => (vec![], vec![]),
        };
        for x in domain_checks.iter().filter(|x| x.status == S_OOD) {
            reasons.push(r(&x.id, S_OOD, x.detail.clone()));
        }
        for x in conservation.iter().filter(|x| x.status == S_ME) {
            reasons.push(r(&x.id, S_ME, x.detail.clone()));
        }
        if let Some(e) = &eq {
            if e.surfaces.iter().zip(&p.surfaces).any(|(s, ps)| s.electron_saturated && ps.potential_v.is_some()) {
                self.verify.insert("VER-06".into());
            }
            if p.set.species.iter().zip(&e.kin.n).any(|(s, n)| s.charge > 1 && *n > 0.0) {
                self.verify.insert("VER-08".into());
            }
            self.verify.insert("VER-12".into());
            if spec.h_label == "H-MS" {
                self.verify.insert("VER-21".into());
            }
            if p.recombination.iter().any(|x| x.gamma_area_m2 > 0.0) {
                self.flags.insert("UNIFORM_DENSITY_WALL_FLUX_AT_GAMMA".into());
            }
        }
        let usable = reasons.is_empty() && (eq.is_some() || trivial.is_some());
        let mut plasma_why: Vec<Reason> = reasons.clone();
        if usable {
            plasma_why.extend(og.magnetized.iter().cloned());
        }
        let out_ok = usable && og.magnetized.is_empty();
        let st = if plasma_why.is_empty() { S_CONV } else { max_sev(worst_of(&plasma_why)) };
        // Plasma outputs.
        let mut outputs: BTreeMap<String, OutputValue> = BTreeMap::new();
        let sc = |o: &mut BTreeMap<String, OutputValue>, k: &str, q: Quantity| {
            o.insert(k.into(), OutputValue::Scalar(q));
        };
        let wq = |u: &str| withheld(u, &plasma_why);
        let mut i_e_cap = wq("A");
        let mut p_bias: Option<f64> = None;
        if out_ok {
            let undefined = |u: &str| Quantity::undefined(u, "NOT_DEFINED_PLASMA_NOT_SUSTAINED");
            sc(&mut outputs, "P_abs_W", Quantity::value(p.p_abs_w, "W"));
            match &eq {
                Some(e) => {
                    sc(&mut outputs, "T_e_eV", Quantity::value(e.kin.t_e, "eV"));
                    sc(&mut outputs, "n_e_m3", Quantity::value(e.kin.n_e, "m^-3"));
                    sc(
                        &mut outputs,
                        "phi_p_V",
                        e.phi_p_v.map_or_else(
                            || Quantity::withheld("V", S_NE, vec!["NO_REFERENCED_ELECTRODE".into()]),
                            |x| Quantity::value(x, "V"),
                        ),
                    );
                    let mut n_i = BTreeMap::new();
                    let mut n_g = BTreeMap::new();
                    for (i, s) in p.set.species.iter().enumerate() {
                        let q = Quantity::value(e.kin.n[i], "m^-3");
                        if s.charge > 0 {
                            n_i.insert(s.name.clone(), q);
                        } else {
                            n_g.insert(s.name.clone(), q);
                        }
                    }
                    outputs.insert("n_i_m3".into(), OutputValue::Map(n_i));
                    outputs.insert("n_g_m3".into(), OutputValue::Map(n_g));
                    outputs.insert(
                        "V_s_by_surface_V".into(),
                        OutputValue::Map(
                            p.surfaces
                                .iter()
                                .zip(&e.surfaces)
                                .filter(|(ps, _)| ps.potential_v.is_none())
                                .map(|(ps, s)| (ps.id.clone(), Quantity::value(s.barrier_v, "V")))
                                .collect(),
                        ),
                    );
                    outputs.insert(
                        "I_surface_A".into(),
                        OutputValue::Map(
                            p.surfaces
                                .iter()
                                .zip(&e.surfaces)
                                .map(|(ps, s)| (ps.id.clone(), Quantity::value(s.current_a, "A")))
                                .collect(),
                        ),
                    );
                    let i_prod = production_current(&p, e);
                    sc(&mut outputs, "I_production_A", Quantity::value(i_prod, "A"));
                    let ec = p.surfaces.iter().position(|s| s.kind == SurfaceKind::ElectronCollector);
                    let cap = ec.map_or(0.0, |j| -e.surfaces[j].current_a);
                    let vbar = physics::electron_mean_speed(e.kin.t_e);
                    let n_edge = |j: usize| match &e.kin.h_species {
                        Some(hs) => (0..p.set.species.len())
                            .filter(|&s| p.set.species[s].charge > 0)
                            .map(|s| f64::from(p.set.species[s].charge) * hs[j][s] * e.kin.n[s])
                            .sum::<f64>(),
                        None => e.kin.h[j] * e.kin.n_e,
                    };
                    let thermal = ec.map_or(0.0, |j| 0.25 * E_CHARGE * n_edge(j) * vbar * p.surfaces[j].area_m2);
                    let ion_lim: f64 = e
                        .surfaces
                        .iter()
                        .zip(&p.surfaces)
                        .filter(|(_, ps)| ps.kind == SurfaceKind::IonCollectorBiased)
                        .map(|(s, _)| s.current_ion_a)
                        .sum();
                    i_e_cap = Quantity::value(cap, "A");
                    sc(&mut outputs, "I_e_thermal_limit_A", Quantity::value(thermal, "A"));
                    sc(&mut outputs, "I_ion_collection_limit_A", Quantity::value(ion_lim, "A"));
                    let bounds = [("THERMAL_FLUX", thermal), ("ION_COLLECTION", ion_lim), ("PRODUCTION", i_prod)];
                    let bmin =
                        bounds
                            .iter()
                            .copied()
                            .fold(("THERMAL_FLUX", f64::INFINITY), |a, x| if x.1 < a.1 { x } else { a });
                    outputs.insert("binding_limit".into(), OutputValue::Label(Label::value(bmin.0)));
                    p_bias = Some(
                        -p.surfaces
                            .iter()
                            .zip(&e.surfaces)
                            .filter_map(|(s, st)| s.potential_v.map(|v| st.current_a * v))
                            .sum::<f64>(),
                    );
                }
                None => {
                    for (k, u) in [("T_e_eV", "eV"), ("phi_p_V", "V")] {
                        sc(&mut outputs, k, undefined(u));
                    }
                    sc(&mut outputs, "n_e_m3", Quantity::value(0.0, "m^-3"));
                    let n = trivial.as_ref().expect("trivial");
                    outputs.insert(
                        "n_g_m3".into(),
                        OutputValue::Map(
                            p.set
                                .species
                                .iter()
                                .zip(n)
                                .filter(|(s, _)| s.charge == 0)
                                .map(|(s, v)| (s.name.clone(), Quantity::value(*v, "m^-3")))
                                .collect(),
                        ),
                    );
                    sc(&mut outputs, "I_production_A", Quantity::value(0.0, "A"));
                    i_e_cap = Quantity::value(0.0, "A");
                    p_bias = Some(0.0);
                    outputs.insert(
                        "binding_limit".into(),
                        OutputValue::Label(Label {
                            value: None,
                            status: S_CONV,
                            reasons: vec!["NOT_DEFINED_PLASMA_NOT_SUSTAINED".into()],
                        }),
                    );
                }
            }
        }
        sc(&mut outputs, "I_e_cap_A", i_e_cap.clone());
        sc(&mut outputs, "I_e_sat_A", self.i_e_sat(&p, out_ok, &g.sat, &plasma_why, eq.is_none()));
        outputs.insert(
            "plasma_state".into(),
            OutputValue::Label(if og.magnetized.is_empty() || !usable {
                plasma_state.clone()
            } else {
                Label::withheld(S_IE, codes(&og.magnetized))
            }),
        );
        // Diagnostics (reported even when B > 0 withholds the outputs).
        let diagnostics = self.diagnostics(&p, eq.as_ref(), usable);
        // Partition members and the interfaces.
        let (thermal_members, bias_value) =
            self.partition(spec, &p, cal.as_ref(), eq.as_ref(), ft, coefs, out_ok, &plasma_why, og, p_bias);
        for tm in &thermal_members {
            for ck in &tm.closures {
                if ck.id.starts_with("CC-07") && ck.status == S_ME {
                    conservation.push(ck.clone());
                }
            }
        }
        let mut bus_why = plasma_why.clone();
        if !usable {
            bus_why.extend(g.plasma.iter().cloned());
        }
        let bus = self.bus_record(&spec.id, cal.as_ref(), bias_value, Some(&p), &bus_why, og);
        let sm = SolveMemberV2 {
            solve_member_id: spec.id.clone(),
            h_member: spec.h_label.clone(),
            gamma: spec.gamma.iter().map(|((s, m), v)| (format!("{s}@{m}"), *v)).collect(),
            status: st,
            reasons: codes(&plasma_why),
            plasma_state,
            outputs,
            equilibria,
            domain_checks,
            conservation,
            diagnostics,
        };
        (sm, thermal_members, bus)
    }

    fn i_e_sat(&self, p: &PreparedCase, usable: bool, sat: &[Reason], why: &[Reason], trivial: bool) -> Quantity {
        if !usable {
            return withheld("A", why);
        }
        if !sat.is_empty() {
            return withheld("A", sat);
        }
        if trivial {
            return Quantity::value(0.0, "A");
        }
        let ec = p.surfaces.iter().position(|s| s.kind == SurfaceKind::ElectronCollector).expect("gated");
        let sweep = self.c.electrodes.as_ref().and_then(|e| e.value.collector_bias_sweep_v.clone()).unwrap_or_default();
        let mut best = f64::NEG_INFINITY;
        for v in sweep {
            let mut q = p.clone();
            q.surfaces[ec].potential_v = Some(v);
            match solver::solve(&q, self.num) {
                Ok(SolveOutcome::Equilibria(e)) if e.len() == 1 => best = best.max(-e[0].surfaces[ec].current_a),
                Ok(SolveOutcome::Equilibria(e)) => {
                    return Quantity::withheld(
                        "A",
                        S_NE,
                        vec![format!("EQUILIBRIUM_SELECTION_NOT_REGISTERED at V_ec = {v} V ({} roots)", e.len())],
                    )
                }
                Ok(SolveOutcome::NotSustained) => {
                    return Quantity::withheld(
                        "A",
                        S_ME,
                        vec!["CC-05_ABSORBED_POWER_WITHOUT_SINK in the bias sweep".into()],
                    )
                }
                Err(f) => return Quantity::withheld("A", S_ME, vec![f.code]),
            }
        }
        Quantity::value(best, "A")
    }

    fn diagnostics(&mut self, p: &PreparedCase, e: Option<&Equilibrium>, usable: bool) -> BTreeMap<String, Quantity> {
        let mut d = BTreeMap::new();
        let Some(e) = e.filter(|_| usable) else {
            for k in ["omega_ce_over_nu_m", "r_ce_over_R", "lambda_D_over_min_R_L", "lambda_D_over_R"] {
                d.insert(k.to_string(), Quantity::withheld("-", S_NE, vec!["NO_SUSTAINED_SOLVE".into()]));
            }
            return d;
        };
        let lam = diagnostics::debye_length(e.kin.t_e, e.kin.n_e);
        d.insert("lambda_D_over_min_R_L".into(), Quantity::value(lam / p.radius_m.min(p.length_m), "-"));
        d.insert("lambda_D_over_R".into(), Quantity::value(lam / p.radius_m, "-"));
        for s in p.surfaces.iter().filter(|s| !s.kind.is_open()) {
            d.insert(
                format!("s_over_R.{}", s.id),
                Quantity::withheld("-", S_NE, vec!["VER-22_CHILD_LAW_SHEATH_WIDTH".into()]),
            );
        }
        match self.c.b_icp_max_t.as_ref().map(|b| b.value) {
            Some(b) if b > 0.0 => {
                let nu: f64 = p
                    .set
                    .reactions
                    .iter()
                    .enumerate()
                    .filter(|(_, x)| x.kind == ReactionKind::ElasticMomentumTransfer)
                    .map(|(ri, x)| e.kin.n[p.set.species_index(&x.target).expect("checked")] * e.kin.k[ri])
                    .sum();
                let lbl = vec!["DIAGNOSTIC_UNMAGNETIZED_SOLVE".to_string()];
                let omega = if nu > 0.0 {
                    Quantity {
                        value: Some(diagnostics::omega_ce_over_nu_m(b, nu)),
                        unit: "-".into(),
                        status: S_CONV,
                        reasons: lbl.clone(),
                    }
                } else {
                    Quantity::withheld("-", S_NE, vec!["EQ-19_NO_MOMENTUM_TRANSFER_RATE_IN_SET".into()])
                };
                d.insert("omega_ce_over_nu_m".into(), omega);
                d.insert(
                    "r_ce_over_R".into(),
                    Quantity {
                        value: Some(diagnostics::r_ce_over_r(e.kin.t_e, b, p.radius_m)),
                        unit: "-".into(),
                        status: S_CONV,
                        reasons: lbl,
                    },
                );
            }
            _ => {
                for k in ["omega_ce_over_nu_m", "r_ce_over_R"] {
                    d.insert(k.to_string(), Quantity::undefined("-", "NOT_APPLICABLE_B_ZERO"));
                }
            }
        }
        d
    }

    fn domain_checks(&self, p: &PreparedCase, e: Option<&Equilibrium>) -> Vec<CheckRecord> {
        let mut checks = Vec::new();
        let ck = |id: &str, status, value, tol, detail: &str| CheckRecord {
            id: id.into(),
            status,
            value,
            tolerance: tol,
            detail: detail.into(),
        };
        if let Some(e) = e {
            for (ri, rx) in p.set.reactions.iter().enumerate() {
                let t = p.set.species_index(&rx.target).expect("checked");
                if let Validity::Verified { max_mean_energy_ev } = rx.validity {
                    let active = e.kin.k[ri] > 0.0 && e.kin.n[t] > 0.0;
                    if active && 1.5 * e.kin.t_e > max_mean_energy_ev {
                        checks.push(ck(
                            &format!("DOM-01:{}", rx.id),
                            S_OOD,
                            Some(1.5 * e.kin.t_e),
                            Some(max_mean_energy_ev),
                            "3/2 T_e above the table's max_mean_energy_eV with nonzero activity",
                        ));
                    }
                }
            }
            let [lo, hi] = p.set.t_e_domain_ev;
            let inside = (lo..=hi).contains(&e.kin.t_e);
            checks.push(ck(
                "DOM-02",
                if inside { S_CONV } else { S_OOD },
                Some(e.kin.t_e),
                None,
                &format!("T_e must lie in [{lo}, {hi}] eV ({})", p.set.set_id),
            ));
        }
        if p.direct.iter().any(Option::is_some) {
            checks.push(ck(
                "IN-24_T_E_SCAN_END",
                S_CONV,
                Some(p.t_e_scan_max_ev(self.num)),
                None,
                "INT-16 (approved): the T_e scan ends at the highest T_e every registered table admits",
            ));
        }
        let n: Vec<f64> = match e {
            Some(e) => e.kin.n.clone(),
            None => solver::trivial_neutrals(p),
        };
        if let Some(NeutralSourceV2::FlowBalance { sigma_c_m2, .. }) = &self.c.neutral_source {
            let sum_ns: f64 = p
                .set
                .species
                .iter()
                .zip(&n)
                .filter(|(s, _)| s.charge == 0)
                .map(|(s, x)| x * sigma_c_m2.get(&s.name).map_or(f64::NAN, |v| v.value))
                .sum();
            let kn = physics::molecular_mean_free_path(sum_ns) / (2.0 * p.radius_m);
            checks.push(ck(
                "DOM-04",
                if kn > KN_FREE_MOLECULAR_MIN { S_CONV } else { S_OOD },
                Some(kn),
                Some(KN_FREE_MOLECULAR_MIN),
                "Kn = lambda / (2R) on the converged neutral state",
            ));
            if matches!(p.h, PreparedH::Lieberman { .. } | PreparedH::LiebermanPerSpecies { .. }) {
                let n_g: f64 = p.set.species.iter().zip(&n).filter(|(s, _)| s.charge == 0).map(|(_, x)| x).sum();
                let pr = n_g * K_B * p.t_g_k;
                checks.push(ck(
                    "DOM-05",
                    if pr < P_100_MTORR_PA { S_CONV } else { S_OOD },
                    Some(pr),
                    Some(P_100_MTORR_PA),
                    "H-LIEB: total neutral pressure < 100 mTorr on the converged state",
                ));
            }
        }
        checks
    }

    /// CC-01, CC-02 and CC-03 v2 (GAP-05) of one branch.
    fn conservation(&self, p: &PreparedCase, e: Option<&Equilibrium>, trivial: Option<&Vec<f64>>) -> Vec<CheckRecord> {
        let mut out = Vec::new();
        let rel = |res: f64, scale: f64| if scale == 0.0 { res.abs() } else { res.abs() / scale };
        let chk = |id: &str, v: f64, detail: &str| CheckRecord {
            id: id.into(),
            status: if v <= TOL_CONS { S_CONV } else { S_ME },
            value: Some(v),
            tolerance: Some(TOL_CONS),
            detail: detail.into(),
        };
        let ns = p.set.species.len();
        let n: Vec<f64> = match (e, trivial) {
            (Some(e), _) => e.kin.n.clone(),
            (None, Some(n)) => n.clone(),
            _ => return out,
        };
        let n_e = e.map_or(0.0, |e| e.kin.n_e);
        let mut gain = vec![0.0; ns];
        let mut loss = vec![0.0; ns];
        if let Some(e) = e {
            for (ri, rx) in p.set.reactions.iter().enumerate() {
                if !rx.kind.changes_species() {
                    continue;
                }
                let t = p.set.species_index(&rx.target).expect("checked");
                let rate = p.volume_m3 * n_e * n[t] * e.kin.k[ri];
                loss[t] += rate;
                for (pn, cnt) in &rx.products {
                    gain[p.set.species_index(pn).expect("checked")] += f64::from(*cnt) * rate;
                }
            }
            for (j, sf) in e.surfaces.iter().enumerate() {
                let a = p.surfaces[j].area_m2;
                for (s, sp) in p.set.species.iter().enumerate() {
                    if sp.charge > 0 {
                        loss[s] += a * sf.gamma_i[s];
                        if !p.surfaces[j].kind.is_open() && matches!(p.neutrals, PreparedNeutrals::Flow { .. }) {
                            for (wp, cnt) in &sp.wall_products {
                                gain[p.set.species_index(wp).expect("checked")] += f64::from(*cnt) * a * sf.gamma_i[s];
                            }
                        }
                    }
                }
            }
        }
        let flow = matches!(p.neutrals, PreparedNeutrals::Flow { .. });
        let mut effusion = vec![0.0; ns];
        if let PreparedNeutrals::Flow { inflow_per_s } = &p.neutrals {
            let open_tau: f64 =
                p.surfaces.iter().filter(|s| s.kind.is_open()).map(|s| s.area_m2 * s.tau.unwrap_or(f64::NAN)).sum();
            for (s, sp) in p.set.species.iter().enumerate() {
                if sp.charge == 0 {
                    gain[s] += inflow_per_s[s];
                    effusion[s] = 0.25 * physics::neutral_mean_speed(p.t_g_k, sp.mass_kg) * open_tau * n[s];
                    loss[s] += effusion[s];
                }
            }
            for rc in &p.recombination {
                let sink = 0.25
                    * physics::neutral_mean_speed(p.t_g_k, p.set.species[rc.atom].mass_kg)
                    * rc.gamma_area_m2
                    * n[rc.atom];
                loss[rc.atom] += sink;
                gain[rc.molecule] += 0.5 * sink;
            }
        }
        let mut worst: f64 = 0.0;
        for s in 0..ns {
            if p.set.species[s].charge > 0 || flow {
                worst = worst.max(rel(gain[s] - loss[s], gain[s].max(loss[s])));
            }
        }
        out.push(chk(
            "CC-01",
            worst,
            "every balanced species: gross gains = gross losses (EQ-02 v2 incl. PF-01 / PF-02)",
        ));
        if let PreparedNeutrals::Flow { inflow_per_s } = &p.neutrals {
            let mut elems: BTreeSet<&String> = BTreeSet::new();
            for s in &p.set.species {
                elems.extend(s.elements.keys());
            }
            let mut w: f64 = 0.0;
            for el in elems {
                let cnt = |s: usize| f64::from(*p.set.species[s].elements.get(el).unwrap_or(&0));
                let inn: f64 = (0..ns).map(|s| cnt(s) * inflow_per_s[s]).sum();
                let mut outn: f64 = (0..ns).map(|s| cnt(s) * effusion[s]).sum();
                if let Some(e) = e {
                    for (j, sf) in e.surfaces.iter().enumerate() {
                        if p.surfaces[j].kind.is_open() {
                            outn += (0..ns).map(|s| cnt(s) * p.surfaces[j].area_m2 * sf.gamma_i[s]).sum::<f64>();
                        }
                    }
                }
                w = w.max(rel(inn - outn, inn.max(outn)));
            }
            out.push(chk("CC-02", w, "nuclei in (feed + background) = out (effusion + ions through open ends)"));
        }
        // CC-03 v2 (GAP-05).
        match e {
            None => out.push(chk("CC-03", 0.0, "NOT_SUSTAINED: every current is exactly 0")),
            Some(e) => {
                let i_scale = e
                    .surfaces
                    .iter()
                    .map(|s| s.current_ion_a.abs().max(s.current_electron_a.abs()))
                    .fold(0.0, f64::max);
                let sum_i: f64 = e.surfaces.iter().map(|s| s.current_a).sum();
                let mut v = rel(sum_i, i_scale);
                for (j, sf) in e.surfaces.iter().enumerate() {
                    if p.surfaces[j].kind.is_zero_current() {
                        v = v.max(rel(sf.current_a, i_scale));
                    }
                }
                let i_prod = production_current(p, e);
                let i_loss: f64 = e.surfaces.iter().map(|s| s.current_ion_a).sum();
                v = v.max(rel(i_prod - i_loss, i_prod));
                let mut c3 = chk(
                    "CC-03",
                    v,
                    "I_scale = max_j e A_j max(sum Z Gamma_i, Gamma_e); |sum I_j|, floating |I_j| <= 1e-10 I_scale; production = ion loss",
                );
                if i_scale.is_nan() || i_scale <= 0.0 {
                    c3.status = S_ME;
                    c3.detail = format!("I_scale = {i_scale} is not > 0 for a sustained state");
                }
                out.push(c3);
            }
        }
        out
    }

    // ---------------------------------------------------------------------------------------- partition / keys

    #[allow(clippy::too_many_arguments, clippy::too_many_lines)]
    fn partition(
        &mut self,
        spec: &SolveSpec,
        p: &PreparedCase,
        cal: Option<&Calibrated>,
        e: Option<&Equilibrium>,
        ft: Option<&FormationTable>,
        coefs: &WallCoefs,
        usable: bool,
        plasma_why: &[Reason],
        og: &OutGates,
        p_bias: Option<f64>,
    ) -> (Vec<ThermalMemberV2>, Option<f64>) {
        let c = self.c;
        let mats = self.materials();
        // RF chain and bus quantities (independent of the partition member).
        let mut coup_why: Vec<Reason> = og.coupling.clone();
        if cal.is_none() && coup_why.is_empty() {
            coup_why.push(r("CM-ABS_NO_COUPLING_CLAIMED", S_NE, "CM-ABS claims no RF chain"));
        }
        let bus_why: Vec<Reason> = og.bus.clone();
        let rfq = |v: Option<f64>| match (cal, v) {
            (Some(_), Some(x)) => Quantity::value(x, "W"),
            _ => withheld("W", if coup_why.is_empty() { plasma_why } else { &coup_why }),
        };
        let lumped = cal.is_some_and(|k| k.lumped_r_vac);
        let p_fwd = cal.map(|k| k.p_fwd_w);
        let p_refl = cal.map(|k| k.p_refl_w);
        let bus = c.bus.as_ref();
        let p_rf_dc = match (bus, cal) {
            (Some(b), Some(k)) if bus_why.is_empty() => Some((k.p_fwd_w - k.p_refl_w) / b.eta_rf.value),
            _ => None,
        };
        let p_match_dc = bus.filter(|_| bus_why.is_empty()).map(|b| b.p_match_dc_w.value);
        let slot_val = |s: &VariantSlot| match s {
            VariantSlot::NotInstalled => 0.0,
            VariantSlot::Installed { p_w } => p_w.value,
        };
        // BUS2-07: without a declared variant both variant slots are NOT_INSTALLED records at exact 0 (DEFINITION).
        let variants = match bus {
            None => Some((0.0, 0.0)),
            Some(b) if bus_why.is_empty() => Some((slot_val(&b.flow_control), slot_val(&b.assist_magnet))),
            Some(_) => None,
        };
        let bus_q = |v: Option<f64>, extra: &[Reason]| match v {
            Some(x) => Quantity::value(x, "W"),
            None => {
                let mut w: Vec<Reason> = bus_why.clone();
                w.extend(extra.iter().cloned());
                if w.is_empty() {
                    w.extend(coup_why.iter().cloned());
                }
                if w.is_empty() {
                    w.extend(plasma_why.iter().cloned());
                }
                withheld("W", &w)
            }
        };
        let mut members = Vec::new();
        let p_bias_ok = usable.then_some(p_bias).flatten();
        let base_keys = |this: &Self, part_why: &[Reason]| -> BTreeMap<String, ThermalKeyV2> {
            let mut k = BTreeMap::new();
            let rf_dc_q = bus_q(p_rf_dc, &coup_why);
            k.insert("P_icp_rf_source_DC_W".into(), this.key("P_icp_rf_source_DC_W", rf_dc_q.clone()));
            k.insert("P_icp_rf_forward_W".into(), this.key("P_icp_rf_forward_W", rfq(p_fwd)));
            k.insert("P_icp_rf_reflected_W".into(), this.key("P_icp_rf_reflected_W", rfq(p_refl)));
            k.insert(
                "Q_icp_rf_conversion_loss_W".into(),
                this.key("Q_icp_rf_conversion_loss_W", bus_q(p_rf_dc.zip(p_fwd).map(|(a, b)| a - b), &coup_why)),
            );
            let lumped_why = vec![r("LUMPED_R_VAC", S_NE, "line and match loss lumped into Q_icp_coil_ohmic_W")];
            let (ql, qm) = if lumped {
                (withheld("W", &lumped_why), withheld("W", &lumped_why))
            } else {
                (rfq(cal.and_then(|k| k.q_line_w)), rfq(cal.and_then(|k| k.q_match_w)))
            };
            k.insert("Q_icp_line_W".into(), this.key("Q_icp_line_W", ql));
            k.insert("Q_icp_match_W".into(), this.key("Q_icp_match_W", qm));
            k.insert("P_icp_matching_DC_W".into(), this.key("P_icp_matching_DC_W", bus_q(p_match_dc, &[])));
            k.insert("Q_icp_coil_ohmic_W".into(), this.key("Q_icp_coil_ohmic_W", rfq(cal.map(|k| k.q_coil_ohmic_w))));
            k.insert(
                "P_icp_flow_control_W".into(),
                this.key("P_icp_flow_control_W", bus_q(variants.map(|v| v.0), &[])),
            );
            k.insert(
                "P_icp_assist_magnet_W".into(),
                this.key("P_icp_assist_magnet_W", bus_q(variants.map(|v| v.1), &[])),
            );
            let pb = match p_bias_ok {
                Some(x) => Quantity::value(x, "W"),
                None => withheld("W", plasma_why),
            };
            k.insert("P_icp_collector_bias_W".into(), this.key("P_icp_collector_bias_W", pb));
            let slot_sum = match (p_rf_dc, p_match_dc, p_bias_ok, variants) {
                (Some(a), Some(b), Some(x), Some((f, mg))) => Some(a + b + x + f + mg),
                _ => None,
            };
            let ss = match slot_sum {
                Some(x) => Quantity::value(x, "W"),
                None => {
                    let mut w = bus_why.clone();
                    w.extend(coup_why.iter().cloned());
                    w.extend(plasma_why.iter().cloned());
                    withheld("W", &w)
                }
            };
            k.insert("P_icp_slot_load_sum_W".into(), this.key("P_icp_slot_load_sum_W", ss));
            let pa = if usable { Quantity::value(p.p_abs_w, "W") } else { withheld("W", plasma_why) };
            k.insert("P_icp_abs_W".into(), this.key("P_icp_abs_W", pa));
            for key in [
                "Q_icp_plasma_wall_W",
                "Q_icp_radiation_W",
                "Q_icp_extraction_W",
                "Q_icp_outflow_upstream_W",
                "Q_icp_outflow_downstream_W",
            ] {
                k.insert(key.into(), this.key(key, withheld("W", part_why)));
            }
            for key in ["Q_icp_bias_collector_W", "Q_icp_bias_export_W"] {
                k.insert(key.into(), this.key(key, withheld("W", plasma_why)));
            }
            k
        };
        // Partition gates.
        let mut part_why: Vec<Reason> = plasma_why.to_vec();
        part_why.extend(og.partition.iter().cloned());
        if !usable {
            let keys = base_keys(self, &part_why);
            members.push(ThermalMemberV2 {
                scenario_member_id: format!("{}/P:WITHHELD", spec.id),
                solve_member_id: spec.id.clone(),
                partition_member_id: "WITHHELD".into(),
                status: max_sev(worst_of(plasma_why)),
                reasons: codes(plasma_why),
                keys,
                node_shares_w: BTreeMap::new(),
                surfaces: BTreeMap::new(),
                coil_ohmic_split_w: BTreeMap::new(),
                class_energy_w: BTreeMap::new(),
                route_excess_w: BTreeMap::new(),
                closures: vec![],
            });
            return (members, None);
        }
        // Per-surface charged-particle terms (zero on the trivial branch).
        let nsurf = p.surfaces.len();
        let (l_w, c_w): (Vec<f64>, Vec<f64>) = match e {
            Some(e) => (e.surfaces.iter().map(|s| s.l_w).collect(), e.surfaces.iter().map(|s| s.c_w).collect()),
            None => (vec![0.0; nsurf], vec![0.0; nsurf]),
        };
        let dispositions: BTreeMap<String, Disposition> =
            c.dispositions.iter().map(|(k, v)| (k.clone(), v.value)).collect();
        if dispositions.values().any(|d| *d != Disposition::Unresolved) {
            self.verify.insert("VER-11".into());
        }
        let tau_registered = p.surfaces.iter().filter(|s| s.kind.is_open()).all(|s| s.tau.is_some());
        if tau_registered && p.surfaces.iter().any(|s| s.kind.is_open()) {
            self.flags.insert("UNIFORM_ISOTROPIC_NEUTRAL_EXIT".into());
        }
        let flow_gamma: Option<BTreeMap<(String, String), f64>> =
            matches!(p.neutrals, PreparedNeutrals::Flow { .. }).then(|| spec.gamma.clone());
        let gated = !part_why.is_empty();
        let mut allocations: Vec<(partition::Allocation, partition::ClassEnergies)> = Vec::new();
        let mut part_fail: Vec<Reason> = Vec::new();
        if !gated {
            match (e, ft) {
                (Some(e), Some(ft)) => {
                    let inp = PartitionInput {
                        p,
                        e,
                        formation: ft,
                        dispositions: &dispositions,
                        materials: &mats,
                        coefs,
                        flow_gamma: flow_gamma.as_ref(),
                        tau_registered,
                    };
                    match partition::class_energies(&inp) {
                        Err(msg) => part_fail.push(r("CC-07_FORMATION_BOOKKEEPING", S_ME, msg)),
                        Ok(ce) => {
                            if ce.a_by_atom_w.values().any(|v| *v < 0.0) {
                                part_fail.push(r(
                                    "ED_CLASS_A_NET_NEGATIVE",
                                    S_IE,
                                    "net atom consumption: formation energy of registered / inflowing atoms is not RF-powered and cannot be separated",
                                ));
                            } else {
                                for ch in partition::choices(&inp, &ce) {
                                    match partition::allocate(&inp, &ce, &ch) {
                                        Ok(a) => allocations.push((a, ce.clone())),
                                        Err(msg) => part_fail.push(r("ED_ALLOCATION", S_ME, msg)),
                                    }
                                }
                                if ce.a_by_atom_w.values().any(|v| *v > 0.0) {
                                    self.flags.insert("AREA_WEIGHTED_WITHIN_MATERIAL".into());
                                }
                                if ce.x_unresolved_w != 0.0 || ce.n_base_w != 0.0 {
                                    self.flags.insert("AREA_WEIGHTED_WITHIN_MATERIAL".into());
                                }
                            }
                        }
                    }
                }
                (None, _) => {
                    // Trivial branch: every plasma-borne term is exactly zero; one member.
                    let ce = partition::ClassEnergies { f_w: vec![0.0; nsurf], ..Default::default() };
                    allocations.push((
                        partition::Allocation {
                            id: "TRIVIAL_BRANCH".into(),
                            w_x: vec![0.0; nsurf],
                            w_n: vec![0.0; nsurf],
                            w_a: vec![0.0; nsurf],
                            rad_w: 0.0,
                            class_x_w: 0.0,
                            class_n_w: 0.0,
                            class_a_w: 0.0,
                            allocated_x_w: 0.0,
                            allocated_n_w: 0.0,
                            allocated_a_w: 0.0,
                        },
                        ce,
                    ));
                }
                (Some(_), None) => part_fail.push(r("INTERNAL_NO_FORMATION_TABLE", S_ME, "")),
            }
        }
        if gated || !part_fail.is_empty() {
            let mut why = part_why.clone();
            why.extend(part_fail.iter().cloned());
            let keys = base_keys(self, &why);
            members.push(ThermalMemberV2 {
                scenario_member_id: format!("{}/P:WITHHELD", spec.id),
                solve_member_id: spec.id.clone(),
                partition_member_id: "WITHHELD".into(),
                status: max_sev(worst_of(&why)),
                reasons: codes(&why),
                keys,
                node_shares_w: BTreeMap::new(),
                surfaces: BTreeMap::new(),
                coil_ohmic_split_w: BTreeMap::new(),
                class_energy_w: BTreeMap::new(),
                route_excess_w: BTreeMap::new(),
                closures: part_fail
                    .iter()
                    .map(|x| CheckRecord {
                        id: x.code.clone(),
                        status: x.status,
                        value: None,
                        tolerance: None,
                        detail: x.detail.clone(),
                    })
                    .collect(),
            });
            return (members, p_bias_ok);
        }
        // Coil split (TK-06; echoed registration or INCOMPLETE_EVIDENCE).
        let coil_split = |q: f64| -> BTreeMap<String, Quantity> {
            match &c.coil_ohmic_split {
                None => BTreeMap::from([(
                    "ALL".to_string(),
                    Quantity::withheld("W", S_IE, vec!["TK-06_SPLIT_NOT_REGISTERED".into()]),
                )]),
                Some(s) => {
                    let sum: f64 = s.value.values().sum();
                    if (sum - 1.0).abs() > 1e-12
                        || s.value.keys().any(|k| !COIL_SPLIT_NODES.contains(&k.as_str()))
                        || s.value.values().any(|w| !(w.is_finite() && *w >= 0.0))
                    {
                        BTreeMap::from([(
                            "ALL".to_string(),
                            Quantity::withheld("W", S_ME, vec!["TK-06_SPLIT_INVALID".into()]),
                        )])
                    } else {
                        s.value.iter().map(|(k, w)| (k.clone(), Quantity::value(w * q, "W"))).collect()
                    }
                }
            }
        };
        for (a, ce) in &allocations {
            let mut keys = base_keys(self, &[]);
            let d_j: Vec<f64> = (0..nsurf).map(|j| l_w[j] + ce.f_w[j] + a.w_x[j] + a.w_n[j] + a.w_a[j]).collect();
            let sum_kind = |f: &dyn Fn(SurfaceKind) -> bool| -> f64 {
                p.surfaces.iter().zip(&d_j).filter(|(s, _)| f(s.kind)).map(|(_, x)| x).sum()
            };
            let q_pw = sum_kind(&|k| k.is_neutralizer_wall());
            let q_ext = sum_kind(&|k| k == SurfaceKind::ElectronCollector);
            let q_up = sum_kind(&|k| k == SurfaceKind::OpenUpstream);
            let q_down = sum_kind(&|k| k == SurfaceKind::OpenDownstream);
            let q_bc: f64 = p
                .surfaces
                .iter()
                .zip(&c_w)
                .filter(|(s, _)| s.kind.is_biased() && s.kind != SurfaceKind::ElectronCollector)
                .map(|(_, x)| x)
                .sum();
            let q_be: f64 = p
                .surfaces
                .iter()
                .zip(&c_w)
                .filter(|(s, _)| s.kind == SurfaceKind::ElectronCollector)
                .map(|(_, x)| x)
                .sum();
            for (k, v) in [
                ("Q_icp_plasma_wall_W", q_pw),
                ("Q_icp_radiation_W", a.rad_w),
                ("Q_icp_extraction_W", q_ext),
                ("Q_icp_outflow_upstream_W", q_up),
                ("Q_icp_outflow_downstream_W", q_down),
                ("Q_icp_bias_collector_W", q_bc),
                ("Q_icp_bias_export_W", q_be),
            ] {
                keys.insert(k.into(), self.key(k, Quantity::value(v, "W")));
            }
            // Producer per-node partitions of TK-07 and TK-12.
            let mut pw_nodes: BTreeMap<String, f64> = BTreeMap::new();
            let mut bc_nodes: BTreeMap<String, f64> = BTreeMap::new();
            for (j, s) in p.surfaces.iter().enumerate() {
                if s.kind.is_neutralizer_wall() {
                    *pw_nodes.entry(s.node.as_str().into()).or_insert(0.0) += d_j[j];
                }
                if s.kind.is_biased() && s.kind != SurfaceKind::ElectronCollector {
                    *bc_nodes.entry(s.node.as_str().into()).or_insert(0.0) += c_w[j];
                }
            }
            let to_q = |m: BTreeMap<String, f64>| -> BTreeMap<String, Quantity> {
                m.into_iter().map(|(k, v)| (k, Quantity::value(v, "W"))).collect()
            };
            let node_shares = BTreeMap::from([
                ("Q_icp_plasma_wall_W".to_string(), to_q(pw_nodes)),
                ("Q_icp_bias_collector_W".to_string(), to_q(bc_nodes)),
            ]);
            let mut surfaces = BTreeMap::new();
            let ion_any: Vec<f64> = match e {
                Some(e) => e.surfaces.iter().map(|s| s.gamma_z).collect(),
                None => vec![0.0; nsurf],
            };
            let mut sg01: f64 = 0.0;
            let mut q_neg: f64 = 0.0;
            for (j, s) in p.surfaces.iter().enumerate() {
                let w = a.w_x[j] + a.w_n[j] + a.w_a[j];
                let q_kin = l_w[j] + c_w[j];
                let q_tot = l_w[j] + ce.f_w[j] + w + c_w[j];
                if let Some(e) = e {
                    let st = &e.surfaces[j];
                    let drop = match (s.potential_v, e.phi_p_v) {
                        (Some(v), Some(phi)) => phi - v,
                        _ => st.barrier_v,
                    };
                    let cf = sg01_closed_form(s.area_m2, st.gamma_e, ion_any[j], e.kin.t_e, drop);
                    let scale = q_kin.abs().max(cf.abs());
                    if scale > 0.0 {
                        sg01 = sg01.max((q_kin - cf).abs() / scale);
                    }
                }
                q_neg = q_neg.min(q_tot);
                surfaces.insert(
                    s.id.clone(),
                    SurfaceRecordV2 {
                        kind: serde_json::to_value(s.kind)
                            .ok()
                            .and_then(|v| v.as_str().map(String::from))
                            .unwrap_or_default(),
                        node: s.node.as_str().into(),
                        material: mats[j].clone(),
                        l_w: l_w[j],
                        f_w: ce.f_w[j],
                        w_w: w,
                        w_x_w: a.w_x[j],
                        w_n_w: a.w_n[j],
                        w_a_w: a.w_a[j],
                        c_w: c_w[j],
                        q_kin_w: q_kin,
                        q_total_w: q_tot,
                    },
                );
            }
            // Closures (CC-05 v2, CC-06 v2, CONS-I3, CC-07 v2, CC-08, SG-01).
            let val = |k: &str| keys[k].q.value;
            let pb = p_bias_ok.unwrap_or(0.0);
            let scale = match cal {
                Some(k) => k.p_fwd_w.abs() + pb.abs(),
                None => p.p_abs_w.abs() + pb.abs(),
            };
            let rel = |res: f64, sc: f64| if sc == 0.0 { res.abs() } else { res.abs() / sc };
            let mut closures = Vec::new();
            let mut ident = |id: &str, lhs: Option<f64>, rhs: &[Option<f64>], detail: &str, tol: f64| {
                let sum: Option<f64> = rhs.iter().copied().sum();
                closures.push(match (lhs, sum) {
                    (Some(l), Some(s)) => {
                        let v = rel(l - s, scale);
                        CheckRecord {
                            id: id.into(),
                            status: if v <= tol { S_CONV } else { S_ME },
                            value: Some(v),
                            tolerance: Some(tol),
                            detail: detail.into(),
                        }
                    }
                    _ => CheckRecord {
                        id: id.into(),
                        status: S_NE,
                        value: None,
                        tolerance: Some(tol),
                        detail: format!("{detail} (a term is not evaluated)"),
                    },
                });
            };
            ident(
                "CC-05-RF-S",
                val("P_icp_rf_source_DC_W"),
                &[val("Q_icp_rf_conversion_loss_W"), val("P_icp_rf_forward_W")],
                "IFI2-03 RF-S: P_rf_source_DC = Q_conversion_loss + P_fwd",
                TOL_CONS,
            );
            ident(
                "CC-05-RF",
                val("P_icp_rf_forward_W"),
                &[
                    val("P_icp_rf_reflected_W"),
                    val("Q_icp_line_W"),
                    val("Q_icp_match_W"),
                    val("Q_icp_coil_ohmic_W"),
                    val("P_icp_abs_W"),
                ],
                "IFI2-04 RF: P_fwd = P_refl + Q_line + Q_match + Q_coil + P_abs",
                TOL_CONS,
            );
            ident(
                "CC-05-PL",
                val("P_icp_abs_W"),
                &[
                    val("Q_icp_plasma_wall_W"),
                    val("Q_icp_radiation_W"),
                    val("Q_icp_extraction_W"),
                    val("Q_icp_outflow_upstream_W"),
                    val("Q_icp_outflow_downstream_W"),
                ],
                "IFI2-05 PL: P_abs = plasma_wall + radiation + extraction + outflow_up + outflow_down",
                TOL_CONS,
            );
            ident(
                "CC-05-B",
                val("P_icp_collector_bias_W"),
                &[val("Q_icp_bias_collector_W"), val("Q_icp_bias_export_W")],
                "IFI2-06 B: P_collector_bias (= -sum I_j V_j) = Q_bias_collector + Q_bias_export",
                TOL_CONS,
            );
            ident(
                "CC-06-S",
                val("P_icp_slot_load_sum_W"),
                &[
                    val("P_icp_rf_source_DC_W"),
                    val("P_icp_matching_DC_W"),
                    val("P_icp_collector_bias_W"),
                    val("P_icp_flow_control_W"),
                    val("P_icp_assist_magnet_W"),
                ],
                "IFI2-07 S: slot load sum = rf_source_DC + matching_DC + collector_bias (+ variants)",
                TOL_CONS,
            );
            let dest: Vec<Option<f64>> = DESTINATION_KEYS
                .iter()
                .map(|k| val(k))
                .chain([val("P_icp_flow_control_W"), val("P_icp_assist_magnet_W")])
                .collect();
            ident(
                "CONS-I3",
                val("P_icp_slot_load_sum_W"),
                &dest,
                "every ICP slot-load watt has exactly one destination (TK-01..TK-13; variants 0)",
                TOL_CONS,
            );
            let neg: Vec<&str> = THERMAL_KEYS
                .iter()
                .filter(|k| !matches!(**k, "Q_icp_bias_collector_W" | "Q_icp_bias_export_W"))
                .filter(|k| keys[**k].q.value.is_some_and(|v| v < 0.0))
                .copied()
                .collect();
            closures.push(CheckRecord {
                id: "CC-05-NONNEGATIVE".into(),
                status: if neg.is_empty() { S_CONV } else { S_ME },
                value: None,
                tolerance: None,
                detail: format!("every key except TK-12 / TK-13 >= 0; negative: {neg:?}"),
            });
            closures.push(CheckRecord {
                id: "CC-05-SURFACE-Q".into(),
                status: if q_neg >= -1e-12 * scale { S_CONV } else { S_ME },
                value: Some(q_neg),
                tolerance: Some(1e-12 * scale),
                detail: "every surface Q_j = L_j + F_j + W_j + C_j >= 0".into(),
            });
            closures.push(CheckRecord {
                id: "SG-01".into(),
                status: if sg01 <= 1e-12 { S_CONV } else { S_ME },
                value: Some(sg01),
                tolerance: Some(1e-12),
                detail: "Q_j^kin = L_j + C_j equals the SG-01 closed form per surface".into(),
            });
            if let Some(e) = e {
                let sum_c: f64 = c_w.iter().sum();
                let sum_iv: f64 = p
                    .surfaces
                    .iter()
                    .zip(&e.surfaces)
                    .filter_map(|(s, st)| s.potential_v.map(|v| st.current_a * v))
                    .sum();
                let sc2 = sum_c.abs().max(sum_iv.abs()).max(c_w.iter().map(|x| x.abs()).fold(0.0, f64::max));
                let v = if sc2 == 0.0 { (sum_c + sum_iv).abs() } else { (sum_c + sum_iv).abs() / sc2 };
                closures.push(CheckRecord {
                    id: "SG-01-SUM".into(),
                    status: if v <= 1e-12 { S_CONV } else { S_ME },
                    value: Some(v),
                    tolerance: Some(1e-12),
                    detail: "sum_j C_j = -sum_j I_j V_j".into(),
                });
            }
            if let Some(k) = cal {
                let cl = p_rf_dc.map(|d| d - k.p_fwd_w);
                if let Some(cl) = cl {
                    closures.push(CheckRecord {
                        id: "CC-06-CONVERSION-LOSS".into(),
                        status: if cl >= 0.0 { S_CONV } else { S_ME },
                        value: Some(cl),
                        tolerance: None,
                        detail: "Q_icp_rf_conversion_loss_W >= 0 (P_rf_source_DC >= P_fwd; a violating eta_RF is MODEL_ERROR)".into(),
                    });
                }
            }
            if let Some(pb) = p_bias_ok {
                closures.push(CheckRecord {
                    id: "BUS2-08".into(),
                    status: if pb >= 0.0 { S_CONV } else { S_OOD },
                    value: Some(pb),
                    tolerance: None,
                    detail: "P_icp_collector_bias_W >= 0 (a sinking supply is OUT_OF_DOMAIN unless registered bidirectional)".into(),
                });
            }
            let fsum: f64 = ce.f_w.iter().sum();
            let asum: f64 = ce.a_by_atom_w.values().sum();
            let cc7 =
                rel(ce.formation_created_w - (fsum + asum), ce.formation_created_w.abs().max((fsum + asum).abs()));
            closures.push(CheckRecord {
                id: "CC-07".into(),
                status: if cc7 <= TOL_CONS { S_CONV } else { S_ME },
                value: Some(cc7),
                tolerance: Some(TOL_CONS),
                detail: "formation energy created = released at surfaces (F_j) + carried out + class A (atoms)".into(),
            });
            for (cls, en, al) in [
                ("X", a.class_x_w, a.allocated_x_w),
                ("N", a.class_n_w, a.allocated_n_w),
                ("A", a.class_a_w, a.allocated_a_w),
            ] {
                let v = if en == 0.0 { al.abs() } else { (al - en).abs() / en.abs() };
                closures.push(CheckRecord {
                    id: format!("CC-08-{cls}"),
                    status: if (en == 0.0 && al == 0.0) || v <= TOL_CONS { S_CONV } else { S_ME },
                    value: Some(v),
                    tolerance: Some(TOL_CONS),
                    detail: format!("class {cls}: allocated to RAD + WALL + OUT = class energy"),
                });
            }
            let coil = keys["Q_icp_coil_ohmic_W"].q.value.map_or_else(
                || BTreeMap::from([("ALL".to_string(), keys["Q_icp_coil_ohmic_W"].q.clone())]),
                coil_split,
            );
            let mut status = S_CONV;
            let mut reasons = Vec::new();
            for ck in &closures {
                if ck.status == S_ME || ck.status == S_OOD {
                    status = IcpStatus::worst([status, ck.status]);
                    reasons.push(ck.id.clone());
                }
            }
            // A member is CONVERGED only when every key is (NE-10: a key withheld by its own gate makes the member
            // record that status; the key keeps its own status and reasons).
            for k in keys.values() {
                if !k.q.status.is_converged() {
                    status = IcpStatus::worst([status, k.q.status]);
                    reasons.push(format!("{}:{}", k.id, k.q.status));
                }
            }
            let sid = format!("{}/P:{}", spec.id, a.id);
            members.push(ThermalMemberV2 {
                scenario_member_id: sid,
                solve_member_id: spec.id.clone(),
                partition_member_id: a.id.clone(),
                status,
                reasons,
                keys,
                node_shares_w: node_shares,
                surfaces,
                coil_ohmic_split_w: coil,
                class_energy_w: BTreeMap::from([
                    ("X".to_string(), [a.class_x_w, a.allocated_x_w]),
                    ("N".to_string(), [a.class_n_w, a.allocated_n_w]),
                    ("A".to_string(), [a.class_a_w, a.allocated_a_w]),
                ]),
                route_excess_w: ce.route_excess_w.clone(),
                closures,
            });
        }
        (members, p_bias_ok)
    }

    fn bus_record(
        &self,
        solve_id: &str,
        cal: Option<&Calibrated>,
        p_bias: Option<f64>,
        _p: Option<&PreparedCase>,
        why: &[Reason],
        og: &OutGates,
    ) -> BusRecordV2 {
        let c = self.c;
        let rows: [(&str, &str, &str, Option<&str>, &str); 10] = [
            ("BK-01", "P_icp_rf_source_DC_W", "LOAD", Some("icp_rf_source"), "INSTALLED"),
            ("BK-02", "P_icp_matching_DC_W", "LOAD", Some("icp_matching_network"), "INSTALLED"),
            ("BK-03", "P_icp_collector_bias_W", "LOAD", Some("icp_collector_bias"), "INSTALLED"),
            ("BK-04", "P_icp_assist_magnet_W", "LOAD", Some("icp_assist_magnet"), "VARIANT_ONLY"),
            ("BK-05", "P_icp_flow_control_W", "LOAD", Some("flow_control_icp_feed"), "VARIANT_ONLY"),
            ("BK-06", "P_icp_slot_load_sum_W", "LOAD_PLANE_SUM", None, "-"),
            ("BK-07", "P_icp_rf_forward_W", "RF_FORWARD", None, "-"),
            ("BK-08", "P_icp_rf_reflected_W", "RF_REFLECTED", None, "-"),
            ("BK-09", "P_icp_delivered_W", "RF_DELIVERED", None, "-"),
            ("BK-10", "Q_icp_rf_conversion_loss_W", "INSIDE_LOAD", None, "-"),
        ];
        let defs = BTreeMap::from([
            ("BK-01", "13.56 MHz RF generator DC input terminals (rf_power_planes generator_dc_input; slot icp_rf_source load)"),
            ("BK-02", "DC input of the matching-network tuning actuators / controller"),
            ("BK-03", "electron-extraction collector / bias supply OUTPUT (V_bias x I_collector); the slot load plane"),
            ("BK-04", "ICP assist-magnet coil terminals"),
            ("BK-05", "dedicated ICP gas-feed valve / flow-controller driver outputs"),
            ("BK-06", "sum of BK-01..BK-05: a thermal closure reference, NEVER a bus draw"),
            ("BK-07", "rf_power_planes forward (measurement quantity)"),
            ("BK-08", "rf_power_planes reflected (measurement quantity)"),
            ("BK-09", "rf_power_planes delivered_to_load at RP-ANT (<= forward - reflected)"),
            ("BK-10", "generator DC-to-RF conversion loss, inside the icp_rf_source load (not a ledger P_loss)"),
        ]);
        let mut flags = BTreeSet::new();
        if self.flags.contains("INCLUDES_GROUND_FACILITY_SUPPLY") {
            flags.insert("INCLUDES_GROUND_FACILITY_SUPPLY".to_string());
        }
        if self.flags.contains("SYNTHETIC_TEST_ONLY") {
            flags.insert("SYNTHETIC_TEST_ONLY".to_string());
        }
        let mut gate: Vec<Reason> = og.bus.clone();
        gate.extend(why.iter().cloned());
        let mut cm: Vec<Reason> = og.coupling.clone();
        if cal.is_none() && cm.is_empty() {
            cm.push(r("CM-ABS_NO_COUPLING_CLAIMED", S_NE, "BK-07: CM-CAL / CM-PRED only; NOT_EVALUATED in CM-ABS"));
        }
        let b = c.bus.as_ref().filter(|_| og.bus.is_empty());
        let q = |v: Option<f64>, extra: &[Reason]| match v {
            Some(x) => Quantity::value(x, "W"),
            None => {
                let mut w = gate.clone();
                w.extend(extra.iter().cloned());
                withheld("W", &w)
            }
        };
        let slot_val = |s: &VariantSlot| match s {
            VariantSlot::NotInstalled => 0.0,
            VariantSlot::Installed { p_w } => p_w.value,
        };
        let rf_dc = match (b, cal) {
            (Some(b), Some(k)) => Some((k.p_fwd_w - k.p_refl_w) / b.eta_rf.value),
            _ => None,
        };
        let bias_ok = if og.bias_bus.is_empty() { p_bias } else { None };
        let vals: BTreeMap<&str, Quantity> = BTreeMap::from([
            ("BK-01", q(rf_dc, &cm)),
            ("BK-02", q(b.map(|b| b.p_match_dc_w.value), &[])),
            ("BK-03", q(bias_ok, &og.bias_bus)),
            (
                "BK-04",
                if c.bus.is_none() { Quantity::value(0.0, "W") } else { q(b.map(|b| slot_val(&b.assist_magnet)), &[]) },
            ),
            (
                "BK-05",
                if c.bus.is_none() { Quantity::value(0.0, "W") } else { q(b.map(|b| slot_val(&b.flow_control)), &[]) },
            ),
            (
                "BK-06",
                q(
                    match (rf_dc, b, bias_ok) {
                        (Some(a), Some(bb), Some(x)) => Some(
                            a + bb.p_match_dc_w.value + x + slot_val(&bb.assist_magnet) + slot_val(&bb.flow_control),
                        ),
                        _ => None,
                    },
                    &cm,
                ),
            ),
            (
                "BK-07",
                match cal {
                    Some(k) if why.is_empty() => Quantity::value(k.p_fwd_w, "W"),
                    _ => withheld("W", &[why, &cm[..]].concat()),
                },
            ),
            (
                "BK-08",
                match cal {
                    Some(k) if why.is_empty() => Quantity::value(k.p_refl_w, "W"),
                    _ => withheld("W", &[why, &cm[..]].concat()),
                },
            ),
            (
                "BK-09",
                match cal {
                    Some(k) if why.is_empty() => Quantity::value(k.p_delivered_w, "W"),
                    _ => withheld("W", &[why, &cm[..]].concat()),
                },
            ),
            ("BK-10", q(rf_dc.zip(cal).map(|(d, k)| d - k.p_fwd_w), &cm)),
        ]);
        let mut keys = BTreeMap::new();
        for (id, key, plane, slot, state) in rows {
            let state = match (id, b) {
                ("BK-04", Some(bb)) if bb.assist_magnet == VariantSlot::NotInstalled => "NOT_INSTALLED",
                ("BK-05", Some(bb)) if bb.flow_control == VariantSlot::NotInstalled => "NOT_INSTALLED",
                ("BK-04" | "BK-05", Some(_)) => "INSTALLED_VARIANT",
                // BUS2-07: no variant declared (no IN-19 registration) -> NOT_INSTALLED by definition.
                ("BK-04" | "BK-05", None) if c.bus.is_none() => "NOT_INSTALLED",
                _ => state,
            };
            keys.insert(
                key.to_string(),
                BusKeyV2 {
                    id: id.into(),
                    plane: plane.into(),
                    plane_definition: defs[id].into(),
                    slot: slot.map(String::from),
                    slot_state: state.into(),
                    q: vals[id].clone(),
                },
            );
        }
        let mut checks = Vec::new();
        let v = |k: &str| keys.get(k).and_then(|x: &BusKeyV2| x.q.value);
        if let (Some(s), Some(a), Some(bb), Some(x), Some(mg), Some(f)) = (
            v("P_icp_slot_load_sum_W"),
            v("P_icp_rf_source_DC_W"),
            v("P_icp_matching_DC_W"),
            v("P_icp_collector_bias_W"),
            v("P_icp_assist_magnet_W"),
            v("P_icp_flow_control_W"),
        ) {
            let res = (s - (a + bb + x + mg + f)).abs() / s.abs().max(f64::MIN_POSITIVE);
            checks.push(CheckRecord {
                id: "CC-06".into(),
                status: if res <= TOL_CONS { S_CONV } else { S_ME },
                value: Some(res),
                tolerance: Some(TOL_CONS),
                detail: "BK-06 = BK-01 + BK-02 + BK-03 + BK-04 + BK-05 (load-plane values; no efficiency applied)"
                    .into(),
            });
        }
        if let (Some(l), Some(f)) = (v("Q_icp_rf_conversion_loss_W"), v("P_icp_rf_forward_W")) {
            checks.push(CheckRecord {
                id: "CC-06-CONVERSION-LOSS".into(),
                status: if l >= 0.0 { S_CONV } else { S_ME },
                value: Some(l),
                tolerance: None,
                detail: format!("BK-10 = BK-01 - BK-07 >= 0 (P_fwd = {f} W)"),
            });
        }
        if let Some(x) = v("P_icp_collector_bias_W") {
            checks.push(CheckRecord {
                id: "BUS2-08".into(),
                status: if x >= 0.0 { S_CONV } else { S_OOD },
                value: Some(x),
                tolerance: None,
                detail: "a sinking bias supply is OUT_OF_DOMAIN (BIAS_SUPPLY_SINKING_NOT_REGISTERED)".into(),
            });
        }
        let st = IcpStatus::worst(keys.values().map(|k| k.q.status));
        let status = IcpStatus::worst(std::iter::once(st).chain(checks.iter().map(|x| x.status)));
        let configuration = if self.flags.contains("SYNTHETIC_TEST_ONLY") {
            "SYNTHETIC".to_string()
        } else {
            c.configuration.as_str().to_string()
        };
        BusRecordV2 {
            interface: BUS_INTERFACE_V2.into(),
            target_boundary: ACTIVE_BUS_BOUNDARY.into(),
            configuration,
            solve_member_id: solve_id.into(),
            flags,
            keys,
            checks,
            status,
            reasons: codes(&gate),
        }
    }

    fn thermal_record(&self, members: Vec<ThermalMemberV2>) -> ThermalRecordV2 {
        let mut extremes: BTreeMap<String, Extreme> = BTreeMap::new();
        let mut push = |k: String, v: f64, id: &str| {
            let e =
                extremes.entry(k).or_insert(Extreme { min_w: v, min_members: vec![], max_w: v, max_members: vec![] });
            if v < e.min_w {
                e.min_w = v;
                e.min_members.clear();
            }
            if v == e.min_w {
                e.min_members.push(id.to_string());
            }
            if v > e.max_w {
                e.max_w = v;
                e.max_members.clear();
            }
            if v == e.max_w {
                e.max_members.push(id.to_string());
            }
        };
        for m in &members {
            for (k, q) in &m.keys {
                if let Some(v) = q.q.value {
                    push(format!("key:{k}"), v, &m.scenario_member_id);
                }
            }
            let mut nodes: BTreeMap<String, f64> = BTreeMap::new();
            for shares in m.node_shares_w.values() {
                for (n, q) in shares {
                    if let Some(v) = q.value {
                        *nodes.entry(n.clone()).or_insert(0.0) += v;
                    }
                }
            }
            for (n, v) in nodes {
                push(format!("node:{n}"), v, &m.scenario_member_id);
            }
        }
        let status = IcpStatus::worst(members.iter().map(|m| m.status));
        let mut consumes = BTreeMap::new();
        let t_gas = match &self.c.neutral_source {
            Some(NeutralSourceV2::RegisteredPressure { t_g_k, .. })
            | Some(NeutralSourceV2::FlowBalance { t_g_k, .. }) => Quantity::value(t_g_k.value, "K"),
            None => Quantity::withheld("K", S_IE, vec!["IN-12_NEUTRAL_SOURCE_NOT_REGISTERED".into()]),
        };
        consumes.insert("T_gas_K".to_string(), OutputValue::Scalar(t_gas));
        let configuration = if self.flags.contains("SYNTHETIC_TEST_ONLY") {
            "SYNTHETIC".to_string()
        } else {
            self.c.configuration.as_str().to_string()
        };
        let mut reasons: Vec<String> = members.iter().flat_map(|m| m.reasons.iter().cloned()).collect();
        reasons.sort();
        reasons.dedup();
        ThermalRecordV2 {
            interface: THERMAL_INTERFACE_V2.into(),
            consumer: THERMAL_CONSUMER_V2.into(),
            producer_lock_sha256: self.m.prereg_lock_v2_sha256.clone(),
            key_table_sha256: self.m.key_table_sha256.clone(),
            configuration,
            status,
            reasons,
            members,
            per_receiver_extremes: extremes,
            consumes,
            hall_powered_heat:
                "none: Hall-discharge-powered heat (Q_hall_return_to_icp_W, Q_hall_plume_to_icp_W, CPL-HALL-ON circuit shares) is never inside an IF-ICP-THERMAL-v2 key (FC-16 v2)"
                    .into(),
        }
    }

    fn hall_pair(&self, members: &[SolveMemberV2], g: &Gate) -> HallPairV2 {
        let c = self.c;
        let mut by = BTreeMap::new();
        let mut vals = Vec::new();
        let mut all = true;
        for m in members {
            let q = m
                .outputs
                .get("I_e_cap_A")
                .and_then(OutputValue::scalar)
                .cloned()
                .unwrap_or_else(|| Quantity::withheld("A", S_ME, vec!["INTERNAL_NO_I_E_CAP".into()]));
            if let (true, Some(v)) = (q.is_converged_value(), q.value) {
                vals.push(v);
            } else {
                all = false;
            }
            by.insert(m.solve_member_id.clone(), q);
        }
        let mut env = BTreeMap::new();
        if all && !vals.is_empty() {
            env.insert("min".into(), Quantity::value(vals.iter().copied().fold(f64::INFINITY, f64::min), "A"));
            env.insert("max".into(), Quantity::value(vals.iter().copied().fold(f64::NEG_INFINITY, f64::max), "A"));
        } else {
            for k in ["min", "max"] {
                env.insert(k.into(), Quantity::withheld("A", S_NE, vec!["A_SOLVE_MEMBER_IS_NOT_EVALUATED".into()]));
            }
        }
        let i_d = match &c.hall_demand {
            Some(h) if g.hall.is_empty() => Quantity::value(h.i_d_max_h1_a.value, "A"),
            _ => withheld("A", &g.hall),
        };
        let mut why = g.hall.clone();
        if !all {
            why.push(r("I_E_CAP_NOT_CONVERGED", S_NE, "a solve member has no converged I_e,cap"));
        }
        HallPairV2 {
            interface: "IF-ICP-HALL-v1".into(),
            configuration: c.configuration.as_str().into(),
            h1_point_id: c.h1_point_id.clone(),
            i_e_cap_by_member_a: by,
            i_e_cap_envelope_a: env,
            i_d_max_h1_a: i_d,
            validation_status: "NOT_VALIDATED".into(),
            validation_cell_id: c.validation_cell_id.clone(),
            coupled_status: if why.is_empty() { S_CONV } else { max_sev(worst_of(&why)) },
            coupled_reasons: codes(&why),
        }
    }

    fn feed_record(&self, set: Option<&ChemistrySet>, g: &Gate) -> FeedRecordV2 {
        let c = self.c;
        let mut species: Vec<String> = set
            .map(|s| s.species.iter().filter(|x| x.charge == 0).map(|x| x.name.clone()).collect())
            .unwrap_or_default();
        if let ChemistryRegistration::NotRegistered { gas } = &c.chemistry {
            species.push(gas.clone());
        }
        species.sort();
        species.dedup();
        FeedRecordV2 {
            interface: "IF-ICP-FEED-v1".into(),
            gas_mode: c.gas_mode.value.as_str().into(),
            mdot_icp_dedicated_kg_s: species
                .iter()
                .map(|s| {
                    let q = match c.gas_mode.value {
                        GasMode::GReuse => Quantity::value(0.0, "kg/s"),
                        _ if !g.dedicated.is_empty() => withheld("kg/s", &g.dedicated),
                        _ => Quantity::value(
                            c.dedicated_flow_kg_s.as_ref().and_then(|d| d.value.get(s).copied()).unwrap_or(0.0),
                            "kg/s",
                        ),
                    };
                    (s.clone(), q)
                })
                .collect(),
            booking: match c.gas_mode.value {
                GasMode::GReuse => "G-REUSE: no dedicated ICP flow (A9.1 HIQ-06)".into(),
                GasMode::GXe => "G-XE: Xe ledger, PHASE_TOTAL_FLOW".into(),
                GasMode::GAtm => "G-ATM: mdot_atm,total = mdot_Hall + mdot_ICP,dedicated (ICD ICP-26)".into(),
            },
        }
    }

    fn provenance(&self) -> ProvenanceV2 {
        let m = self.m;
        let mut files: BTreeMap<String, String> =
            m.v1.files_read.iter().map(|f| (f.path.clone(), f.sha256.clone())).collect();
        for f in &m.v2_files_read {
            files.insert(f.path.clone(), f.sha256.clone());
        }
        ProvenanceV2 {
            model_id: crate::context::MODEL_ID.into(),
            model_version: MODEL_VERSION_V2.into(),
            contract_id: CONTRACT_ID_V2.into(),
            prereg_lock_sha256: m.prereg_lock_v2_sha256.clone(),
            prereg_sha256: m.prereg_v2_sha256.clone(),
            predecessor_lock_sha256: m.v1.prereg_lock_sha256.clone(),
            interface_ids: vec![
                THERMAL_INTERFACE_V2.into(),
                BUS_INTERFACE_V2.into(),
                "IF-ICP-HALL-v1".into(),
                "IF-ICP-FEED-v1".into(),
                CPL_HALL_ON.into(),
            ],
            chem_registry: m.v1.chem_registry_provenance(),
            input_sha256: sha256_hex(serde_json::to_string(self.c).expect("serializable").as_bytes()),
            data_files_sha256: files,
            rust_commit: m.v1.rust_commit.clone(),
        }
    }
}
