//! Case evaluation in the registered order (prereg status_vocabulary.evaluation_order): (1) input registration ->
//! NOT_EVALUATED / INCOMPLETE_EVIDENCE; (2) input domain -> OUT_OF_DOMAIN; (3) solve -> MODEL_ERROR on failure;
//! (4) solution domain -> OUT_OF_DOMAIN; (5) conservation -> MODEL_ERROR; (6) CONVERGED. Every output carries its own
//! status; a non-CONVERGED output is null.

use crate::case::*;
use crate::chemistry::{ChemistryRegistration, ChemistrySet, ClassAddress, RateSource, ReactionKind, Validity};
use crate::constants::{NumericalSettings, E_CHARGE, F_RF_REGISTERED_HZ, KN_FREE_MOLECULAR_MIN, K_B, NUMERICS};
use crate::constants::{P_100_MTORR_PA, TOL_CONS, TOL_SOLVE};
use crate::context::{
    validity_of_channel, IcpModel, ACTIVE_BUS_BOUNDARY, CONTRACT_ID, MODEL_ID, MODEL_VERSION, N2_SET_CONFIG,
};
use crate::coupling::{self, Calibrated, CM_PRED_BLOCKED_BY};
use crate::evidence::{EvidenceRecord, QuantityType, UncertaintyRepr};
use crate::geometry::{SurfaceKind, ThermalNode, Transmission};
use crate::physics;
use crate::result::*;
use crate::solver::{
    self, DirectRate, Equilibrium, PreparedCase, PreparedH, PreparedNeutrals, PreparedSurface, SolveOutcome,
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

/// Reasons collected per output group. `plasma` blocks the solve.
#[derive(Default)]
pub(crate) struct Gate {
    pub(crate) plasma: Vec<Reason>,
    pub(crate) coupling: Vec<Reason>,
    pub(crate) bus: Vec<Reason>,
    pub(crate) sat: Vec<Reason>,
    pub(crate) hall: Vec<Reason>,
    pub(crate) dedicated: Vec<Reason>,
}

pub(crate) fn r(code: &str, status: IcpStatus, detail: impl Into<String>) -> Reason {
    Reason::new(code, status, detail)
}

fn codes(rs: &[Reason]) -> Vec<String> {
    rs.iter().map(|x| x.code.clone()).collect()
}

fn ok_pos(x: f64) -> bool {
    x.is_finite() && x > 0.0
}

/// The registered state used to build outputs: the trivial branch (n_e = 0) or one equilibrium.
enum Branch<'a> {
    Trivial(Vec<f64>),
    Eq(&'a Equilibrium),
}

/// Point values of a branch (the trivial branch has no T_e, phi_p or sheath).
struct BranchView {
    t_e: Option<f64>,
    n_e: f64,
    n: Vec<f64>,
    phi: Option<f64>,
    vs: Option<f64>,
    surf_currents: Vec<f64>,
    k: Vec<f64>,
}

impl BranchView {
    fn of(p: &PreparedCase, b: &Branch) -> Self {
        match b {
            Branch::Trivial(n) => BranchView {
                t_e: None,
                n_e: 0.0,
                n: n.clone(),
                phi: None,
                vs: None,
                surf_currents: vec![0.0; p.surfaces.len()],
                k: vec![0.0; p.set.reactions.len()],
            },
            Branch::Eq(e) => BranchView {
                t_e: Some(e.kin.t_e),
                n_e: e.kin.n_e,
                n: e.kin.n.clone(),
                phi: e.phi_p_v,
                vs: Some(e.v_s_float_v),
                surf_currents: e.surfaces.iter().map(|s| s.current_a).collect(),
                k: e.kin.k.clone(),
            },
        }
    }
}

impl IcpModel {
    pub fn evaluate(&self, case: &IcpCase) -> IcpResult {
        self.evaluate_with(case, &NUMERICS)
    }

    /// Evaluate with explicit numerical settings (IN-24; tests use a reduced iteration limit for FC-09).
    pub fn evaluate_with(&self, case: &IcpCase, num: &NumericalSettings) -> IcpResult {
        Evaluator { m: self, case, num, flags: BTreeSet::new(), verify: BTreeSet::new() }.run()
    }
}

pub(crate) struct Evaluator<'a> {
    pub(crate) m: &'a IcpModel,
    pub(crate) case: &'a IcpCase,
    pub(crate) num: &'a NumericalSettings,
    pub(crate) flags: BTreeSet<String>,
    pub(crate) verify: BTreeSet<String>,
}

pub(crate) fn evidence_records(c: &IcpCase) -> Vec<(String, &EvidenceRecord)> {
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
        Some(NeutralSource::RegisteredPressure { p_icp_pa, t_g_k, mole_fractions }) => {
            v.push(("IN-12.p_icp_pa".into(), &p_icp_pa.evidence));
            v.push(("IN-12.t_g_k".into(), &t_g_k.evidence));
            v.push(("IN-05.mole_fractions".into(), &mole_fractions.evidence));
        }
        Some(NeutralSource::FlowBalance { f_in, t_g_k, sigma_c_m2 }) => {
            v.push(("IN-12.f_in".into(), &f_in.evidence));
            v.push(("IN-12.t_g_k".into(), &t_g_k.evidence));
            for (k, s) in sigma_c_m2 {
                v.push((format!("DOM-04.sigma_c.{k}"), &s.evidence));
            }
        }
        None => {}
    }
    if let Some(f) = &c.feed {
        v.push(("IN-04.feed".into(), &f.evidence));
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
        Some(crate::geometry::HModel::Explicit { h_by_surface }) => {
            for (k, h) in h_by_surface {
                v.push((format!("IN-17.h.{k}"), &h.evidence));
            }
        }
        Some(crate::geometry::HModel::Lieberman { sigma_i_m2 }) => {
            for (k, s) in sigma_i_m2 {
                v.push((format!("IN-17.sigma_i.{k}"), &s.evidence));
            }
        }
        None => {}
    }
    for (k, g) in &c.wall_recombination {
        v.push((format!("IN-18.gamma.{k}"), &g.evidence));
    }
    for (k, d) in &c.dispositions {
        v.push((format!("IN-23.disposition.{k}"), &d.evidence));
    }
    if let Some(d) = &c.dedicated_flow_kg_s {
        v.push(("IF-ICP-FEED-v1.dedicated_flow".into(), &d.evidence));
    }
    if let Some(b) = &c.bus {
        v.push(("IN-19.eta_rf".into(), &b.eta_rf.evidence));
        v.push(("IN-19.p_match_dc_w".into(), &b.p_match_dc_w.evidence));
        v.push(("IN-19.eta_bias".into(), &b.eta_bias.evidence));
        v.push(("IN-19.match_colocated".into(), &b.match_colocated.evidence));
        for (n, s) in [("assist_magnet", &b.assist_magnet), ("flow_control", &b.flow_control)] {
            if let VariantSlot::Installed { p_w } = s {
                v.push((format!("IN-19.{n}"), &p_w.evidence));
            }
        }
    }
    if let Some(h) = &c.hall_demand {
        v.push(("IN-20.i_d_max_h1_a".into(), &h.i_d_max_h1_a.evidence));
    }
    v
}

impl Evaluator<'_> {
    fn run(mut self) -> IcpResult {
        self.flags.insert("MAXWELLIAN_ASSUMED".into());
        self.verify.insert("VER-01".into());
        let mut g = Gate::default();
        let set = self.registration(&mut g);
        let mut prepared = None;
        let mut cal = None;
        if g.plasma.is_empty() {
            if let Some(set) = &set {
                match self.prepare(set) {
                    Ok((p, cl)) => {
                        prepared = Some(p);
                        cal = cl;
                    }
                    Err(rs) => g.plasma.extend(rs),
                }
            }
        }
        if prepared.is_none() && g.plasma.is_empty() {
            g.plasma.push(r("INTERNAL_NO_PREPARED_CASE", S_ME, "registration passed without a prepared case"));
        }
        let outcome = prepared.as_ref().map(|p| solver::solve(p, self.num));
        self.assemble(set.as_ref(), prepared.as_ref(), cal.as_ref(), outcome, g)
    }

    /// Steps (1) and (2): input registration and input domain. Returns the chemistry set when one is usable.
    fn registration(&mut self, g: &mut Gate) -> Option<ChemistrySet> {
        let recs = evidence_records(self.case);
        let set = self.registration_common(&recs, g);
        // B_ICP (DOM-06, FC-14).
        match &self.case.b_icp_max_t {
            None => g.plasma.push(r("DOM-06_B_ICP_NOT_REGISTERED", S_IE, "B_ICP,max absent (VI-HD-06; NE-11)")),
            Some(b) if !(b.value.is_finite() && b.value >= 0.0) => {
                g.plasma.push(r("DOM-06_B_ICP_INVALID", S_ME, format!("{}", b.value)))
            }
            Some(b) if b.value > 0.0 => g.plasma.push(r(
                "DOM-06_MAGNETIZATION_CRITERION_OPEN",
                S_IE,
                format!("B_ICP,max = {} T > 0: no sourced criterion until OQ-NPICP-03 (FC-14)", b.value),
            )),
            Some(_) => {}
        }
        self.geometry_gate(set.as_ref(), g);
        self.downstream_gates(g);
        set
    }

    /// The part of steps (1) and (2) that model_version 2 shares unchanged: evidence attributes (IN-22) over `recs`,
    /// FC-15, IN-01, the configuration gate (FC-03), the coupling mode, the RF input domain, IN-07 / DOM-11 and the
    /// chemistry by mode with its contract gate. Returns the chemistry set when one is usable.
    pub(crate) fn registration_common(
        &mut self,
        recs: &[(String, &EvidenceRecord)],
        g: &mut Gate,
    ) -> Option<ChemistrySet> {
        let c = self.case;
        let m = self.m;
        // IN-22 evidence attributes and FC-15 synthetic / evidence separation.
        for (name, e) in recs {
            for a in e.missing_attributes() {
                g.plasma.push(r(&format!("IN-22:{name}.{a}"), S_IE, format!("evidence attribute missing: {a}")));
            }
        }
        let mode = c.supply_mode.value;
        let synth_chem = matches!(c.chemistry, ChemistryRegistration::Synthetic { .. });
        let any_synth =
            recs.iter().any(|(_, e)| e.is_synthetic()) || synth_chem || mode == SupplyMode::SyntheticTestOnly;
        let any_evid =
            recs.iter().any(|(_, e)| !e.is_synthetic()) || !synth_chem || mode != SupplyMode::SyntheticTestOnly;
        if any_synth {
            self.flags.insert("SYNTHETIC_TEST_ONLY".into());
        }
        if any_synth && any_evid {
            let mixed: Vec<String> = recs.iter().filter(|(_, e)| !e.is_synthetic()).map(|(n, _)| n.clone()).collect();
            g.plasma.push(r(
                "FC-15_SYNTHETIC_EVIDENCE_MIX_REFUSED",
                S_ME,
                format!("SYNTHETIC_TEST_ONLY inputs mixed with evidence inputs (mode {}, chemistry synthetic {synth_chem}, evidence records {mixed:?})", mode.as_str()),
            ));
        }
        // IN-01 against the architecture configuration.
        if matches!(mode, SupplyMode::AirPrimary | SupplyMode::XeContingency)
            && !m.supply_modes.iter().any(|s| s == mode.as_str())
        {
            g.plasma.push(r("IN-01_SUPPLY_MODE_NOT_IN_ARCHITECTURE", S_ME, mode.as_str()));
        }
        // Configuration (FC-03).
        if c.configuration == Configuration::FlightHallOn {
            g.plasma.push(r(
                "IN-21_HALL_ON_EXHAUST_NOT_EVALUATED",
                S_NE,
                "CFG-FLIGHT-HALL-ON needs an admitted HallThruster.jl member (NE-08)",
            ));
            if m.ensemble_member_count == 0 {
                g.plasma.push(r(
                    "CREDIBLE_HALL_TRANSPORT_SET_EMPTY",
                    S_NE,
                    "hallthruster_bridge/ensemble/transport_ensemble_v0.json members = []",
                ));
            }
        }
        // Coupling mode.
        match c.coupling_mode {
            CouplingMode::Absorbed => {
                if matches!(c.rf_input, Some(RfInput::Forward { .. })) {
                    g.plasma.push(r("IN-08_CM_ABS_NEEDS_ABSORBED_POWER", S_ME, "CM-ABS takes P_abs as the input"));
                }
                g.coupling.push(r(
                    "CM-ABS_NO_COUPLING_CLAIMED",
                    S_NE,
                    "CM-ABS claims no impedance, eta_p or forward power",
                ));
                g.bus.push(r("CM-ABS_GIVES_NO_BUS_QUANTITY", S_NE, "P_fwd needs CM-CAL or CM-PRED (NE-09)"));
            }
            CouplingMode::Calibrated => {
                if matches!(c.rf_input, Some(RfInput::AbsorbedPower { .. })) {
                    g.plasma.push(r("IN-08_CM_CAL_NEEDS_FORWARD_POWER", S_ME, "CM-CAL takes P_fwd, P_refl at RP-CPL"));
                }
                match &c.coupling_evidence {
                    Some(CouplingEvidence::P2Point { point }) => {
                        let p = &point.value;
                        if !p.map_validated || p.uncertainty_status != "EVALUATED" {
                            g.plasma.push(r(
                                "FC-04_CM_CAL_WITHOUT_VALIDATED_P2_MAP",
                                S_NE,
                                format!(
                                    "map {} validated {} uncertainty {}",
                                    p.map_id, p.map_validated, p.uncertainty_status
                                ),
                            ));
                        }
                        if p.plasma_state_class != "H_MODE" {
                            g.plasma.push(r("DOM-08", S_OOD, format!("plasma_state_class {}", p.plasma_state_class)));
                        }
                        if !p.at_map_point {
                            g.plasma.push(r(
                                "DOM-09_P2_INTERPOLATION_NOT_EVALUATED",
                                S_NE,
                                "v1 evaluates CM-CAL only at a registered map point; the P2 interpolation rule is not implemented",
                            ));
                        }
                        if p.plane_convention == PlaneConvention::RVac {
                            self.flags.insert("LUMPED_R_VAC".into());
                        }
                    }
                    _ => g.plasma.push(r(
                        "FC-04_CM_CAL_WITHOUT_VALIDATED_P2_MAP",
                        S_NE,
                        "no registered P2 impedance evidence (TBD_AFTER_IMPEDANCE_MAP; NE-02)",
                    )),
                }
            }
            CouplingMode::Predictive => {
                for v in CM_PRED_BLOCKED_BY {
                    g.plasma.push(r(
                        &format!("CM-PRED_NOT_ADMISSIBLE:{v}"),
                        S_NE,
                        "EQ-14 transformer model not admissible until the verify item is cleared",
                    ));
                }
                if !matches!(c.coupling_evidence, Some(CouplingEvidence::PredictiveAntenna { .. })) {
                    g.plasma.push(r("IN-09_ANTENNA_GEOMETRY_NOT_REGISTERED", S_NE, "F6-X-06..09 TBD; CAL-P2-08"));
                }
                self.flags.insert("UNCALIBRATED_PREDICTIVE".into());
            }
        }
        // RF input domain.
        match &c.rf_input {
            Some(RfInput::AbsorbedPower { p_abs_w }) => {
                if !(p_abs_w.value.is_finite() && p_abs_w.value >= 0.0) {
                    g.plasma.push(r(
                        "IN-08_P_ABS_DOMAIN",
                        S_OOD,
                        format!("P_abs = {} W (domain P >= 0)", p_abs_w.value),
                    ));
                }
                if p_abs_w.evidence.quantity_type != Some(QuantityType::Measured) {
                    self.flags.insert("PARAMETRIC_ABSORBED_POWER".into());
                }
            }
            Some(RfInput::Forward { .. }) => {}
            None => g.plasma.push(r(
                "IN-08_RF_INPUT_NOT_REGISTERED",
                S_NE,
                "flight setpoints TBD; no bench record with measured P_abs (VI-RF-05)",
            )),
        }
        // IN-07 / DOM-11.
        match &c.f_rf_hz {
            None => g.plasma.push(r("IN-07_F_RF_NOT_REGISTERED", S_IE, "13.56 MHz must be registered on the case")),
            Some(f) if (f.value - F_RF_REGISTERED_HZ).abs() > 1e-9 * F_RF_REGISTERED_HZ => {
                g.plasma.push(r("DOM-11", S_OOD, format!("f_RF = {} Hz", f.value)))
            }
            Some(_) => {}
        }
        // Chemistry by mode, from the IF-CHEM-REG-v1 registry (IN-16; G-A930-AIR; CHG-04 / CHG-05; NP-ICP-CHEM-AIR
        // SP-01, SP-04, SP-05, SP-07). No status is upgraded here (SP-08).
        let mut x_comp: BTreeMap<String, Option<f64>> = BTreeMap::new();
        if let Some(NeutralSource::RegisteredPressure { mole_fractions, .. }) = &c.neutral_source {
            for (k, x) in &mole_fractions.value {
                x_comp.insert(k.clone(), Some(*x));
            }
        }
        if let Some(f) = &c.feed {
            // A feed gives mass flows, not mole fractions: a species present cannot be shown to lie below the screen.
            for (k, v) in &f.value.mdot_kg_s {
                if *v > 0.0 {
                    x_comp.entry(k.clone()).or_insert(None);
                }
            }
        }
        let air_gate = |g: &mut Gate| {
            let air = &m.chem_registry.air;
            if !air.is_admitted() {
                g.plasma.push(r(
                    &air.admission_reason_code,
                    S_IE,
                    format!(
                        "G-A930-AIR (A9.30 sec. 4); registry {} {}; {}",
                        air.label, air.admission_status, air.admission_today
                    ),
                ));
            }
            for p in air.tier1_gaps() {
                g.plasma.push(r(
                    &format!("NP-ICP-CHEM-AIR:{}", p.id),
                    S_IE,
                    format!("tier {} {}: {}", p.tier, p.status.as_str(), p.reaction),
                ));
            }
            for b in air.species_bounds.iter().filter(|b| b.status == "UNRESOLVED") {
                let x = x_comp.get(&b.species);
                let applies = match b.scope.as_str() {
                    "EVERY_AIR_COMPOSITION" => true,
                    _ => x.is_some_and(|x| x.is_none_or(|x| x > b.x_screen)),
                };
                if applies {
                    g.plasma.push(r(
                        &format!("SP-04_SPECIES_BOUND_UNRESOLVED:{}", b.id),
                        S_IE,
                        format!("{} {} (x_screen {}): {}", b.species, b.status, b.x_screen, b.scope),
                    ));
                }
            }
            if air.neg_crit_status.as_deref() != Some("PASSED") {
                g.plasma.push(r(
                    "DOM-12_NO_NEGATIVE_ION_BALANCE",
                    S_IE,
                    format!(
                        "O2-bearing composition: v1 has no negative-ion balance (CHG-03; NEG-CRIT {}, SP-05)",
                        air.neg_crit_status.as_deref().unwrap_or("absent")
                    ),
                ));
            }
        };
        let xe_gate = |g: &mut Gate| {
            let xe = &m.chem_registry.xe;
            if xe.channels.is_empty() {
                g.plasma.push(r("CHG-04_NO_XE_RATE_SET", S_IE, "no registered Xe electron-impact or Xe+/Xe set"));
            }
            if !xe.is_admitted() {
                g.plasma.push(r(
                    &xe.admission_reason_code,
                    S_IE,
                    format!("registry {} {}; {}", xe.label, xe.admission_status, xe.admission_today),
                ));
            }
            for p in xe.tier1_gaps() {
                g.plasma.push(r(
                    &format!("NP-ICP-CHEM-AIR:{}", p.id),
                    S_IE,
                    format!("tier {} {}: {}", p.tier, p.status.as_str(), p.reaction),
                ));
            }
        };
        match mode {
            SupplyMode::AirPrimary => {
                air_gate(g);
                g.plasma.push(r("IN-05_DELIVERED_COMPOSITION_TBD", S_IE, "delivered O/O2 split TBD (ICD G-02)"));
            }
            SupplyMode::EmO2b => air_gate(g),
            SupplyMode::XeContingency | SupplyMode::EmXe => xe_gate(g),
            SupplyMode::EmAr => g.plasma.push(r("CHG-05_NO_AR_RATE_SET", S_IE, "no registered Ar set (EM-AR)")),
            SupplyMode::EmN2 | SupplyMode::SyntheticTestOnly => {}
        }
        let set = match (&c.chemistry, mode) {
            (ChemistryRegistration::NotRegistered { gas }, _) => {
                g.plasma.push(r(&format!("IN-16_NO_REGISTERED_RATE_SET:{gas}"), S_IE, "no registered chemistry"));
                None
            }
            (ChemistryRegistration::Synthetic { set }, _) => Some(set.clone()),
            (ChemistryRegistration::RegisteredSet { config_file }, SupplyMode::EmN2) => {
                if config_file != N2_SET_CONFIG {
                    g.plasma.push(r(
                        "IF-CHEM-REG-v1_UNREGISTERED_CONFIG",
                        S_ME,
                        format!("{config_file}: only {N2_SET_CONFIG} is pinned by the prereg"),
                    ));
                    None
                } else {
                    let ca = &m.chem_registry.air.completeness_audit_status;
                    if ca != "FINAL" {
                        g.plasma.push(r(
                            "OQ-NPICP-04_ICP_COMPLETENESS_AUDIT_OPEN",
                            S_IE,
                            format!("CA-ICP-v1 {ca}: COMPLETE_FOR_P5_N2_VALIDATION was decided for Hall conditions and does not transfer (RU-03, NE-06)"),
                        ));
                    }
                    Some(m.n2_set.clone())
                }
            }
            (ChemistryRegistration::RegisteredSet { config_file }, md) => {
                let code = if md == SupplyMode::AirPrimary || md == SupplyMode::EmO2b {
                    "A9.30_N2_ONLY_SURROGATE_REFUSED"
                } else {
                    "IN-16_SET_DOES_NOT_MATCH_MODE"
                };
                g.plasma.push(r(code, S_ME, format!("{config_file} for mode {}", md.as_str())));
                None
            }
        };
        if let Some(set) = &set {
            self.chemistry_gate(set, g);
        }
        set
    }

    fn chemistry_gate(&mut self, set: &ChemistrySet, g: &mut Gate) {
        let v = set.contract_violations();
        for x in v {
            g.plasma.push(r("CHEMISTRY_CONTRACT", S_ME, x));
        }
        let mut registered_table = false;
        for rx in &set.reactions {
            match rx.validity {
                Validity::MissingEntry => g.plasma.push(r(
                    &format!("DOM-03_MISSING_VALIDITY_ENTRY:{}", rx.id),
                    S_ME,
                    "no rate_validity entry",
                )),
                Validity::Unresolved => {
                    g.plasma.push(r(&format!("DOM-03_UNRESOLVED:{}", rx.id), S_IE, "rate_validity status unresolved"))
                }
                Validity::Verified { max_mean_energy_ev } if !ok_pos(max_mean_energy_ev) => {
                    g.plasma.push(r(&format!("DOM-03_INVALID_LIMIT:{}", rx.id), S_ME, "limit must be > 0"))
                }
                Validity::Verified { .. } => {}
            }
            if let RateSource::RegisteredTable { file } = &rx.rate {
                registered_table = true;
                match self.m.chem_channel_for_table(file) {
                    None => g.plasma.push(r(
                        &format!("IF-CHEM-REG-v1_UNREGISTERED_FILE:{}", rx.id),
                        S_ME,
                        format!("{file} has no channel in the ICP registry"),
                    )),
                    Some(ch) => {
                        let products: Vec<(String, u32)> = ch.products.iter().map(|(k, n)| (k.clone(), *n)).collect();
                        if ch.target != rx.target
                            || products != rx.products
                            || ch.threshold_ev.to_bits() != rx.threshold_ev.to_bits()
                            || validity_of_channel(&ch.validity) != rx.validity
                        {
                            g.plasma.push(r(
                                &format!("IF-CHEM-REG-v1_REACTION_DIFFERS_FROM_REGISTRY:{}", rx.id),
                                S_ME,
                                format!("target, products, E_r or validity differ from channel {}", ch.id),
                            ));
                        }
                        if let Representation::NotRegistered { kind, gap } = &ch.representation {
                            g.plasma.push(r(
                                &format!("EQ-06_REPRESENTATION_NOT_REGISTERED:{}", ch.id),
                                S_IE,
                                format!("{kind}: {gap}"),
                            ));
                        }
                    }
                }
            }
            match rx.kind {
                ReactionKind::ElasticMomentumTransfer => {
                    self.verify.insert("VER-02".into());
                }
                ReactionKind::ExcitationElectronic => {
                    if let Some(d) = self.case.dispositions.get(&rx.id) {
                        if d.value != Disposition::Unresolved {
                            self.verify.insert("VER-11".into());
                        }
                    }
                }
                _ => {}
            }
        }
        if registered_table && !self.m.abep_chem_admitted {
            g.plasma.push(r(
                "EQ-06_ABEP_CHEM_INTEGRATOR_NOT_ADMITTED",
                S_NE,
                format!(
                    "rates come only from the admitted abep-chem port of rate_tables.maxwellian_rate (EX-01, EQ-06, IF-CHEM-REG-v1); {}",
                    self.m.abep_chem_admission
                ),
            ));
        }
        for k in self.case.dispositions.keys() {
            if !set.reactions.iter().any(|x| &x.id == k && x.kind == ReactionKind::ExcitationElectronic) {
                g.plasma.push(r("IN-23_UNKNOWN_CHANNEL", S_ME, format!("disposition for {k}")));
            }
        }
        let gaps = set.unaddressed_classes();
        if !gaps.is_empty() {
            let list: Vec<String> = gaps.iter().map(|(s, c)| format!("{s}/{}", c.as_str())).collect();
            g.plasma.push(r(
                "PROCESS_CLASS_GATE_UNADDRESSED",
                S_IE,
                format!("{} (species, class) pairs neither modelled nor excluded: {}", list.len(), list.join(", ")),
            ));
        }
        for (s, cls) in &set.process_classes {
            for (k, a) in cls {
                if let ClassAddress::Excluded { justification } = a {
                    if justification.trim().is_empty() {
                        g.plasma.push(r("PROCESS_CLASS_EXCLUSION_UNJUSTIFIED", S_IE, format!("{s}/{}", k.as_str())));
                    }
                }
            }
        }
        if set.species.iter().any(|s| s.electronegative) {
            g.plasma.push(r("DOM-12", S_IE, "electronegative species: v1 has no negative-ion balance"));
        }
    }

    fn geometry_gate(&mut self, set: Option<&ChemistrySet>, g: &mut Gate) {
        let c = self.case;
        let geo = match &c.geometry {
            None => {
                g.plasma.push(r("IN-10_GEOMETRY_NOT_REGISTERED", S_IE, "ICP geometry F6-X-01..05, 10..17 TBD (NE-01)"));
                None
            }
            Some(gr) => {
                for x in gr.value.contract_violations() {
                    g.plasma.push(r("IN-10_GEOMETRY_CONTRACT", S_ME, x));
                }
                if matches!(gr.value.volume_mode, crate::geometry::VolumeMode::GeometricTube) {
                    self.flags.insert("GEOMETRIC_TUBE_VOLUME_ASSUMED".into());
                }
                Some(&gr.value)
            }
        };
        // IN-11 electrode registration (CFG-CAP-OFF).
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
                }
                for k in e.value.potentials_v.keys() {
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
        // IN-17 edge factors.
        match (&c.h_model, geo, set) {
            (None, _, _) => g.plasma.push(r(
                "IN-17_NO_EDGE_FACTOR_SOURCE",
                S_IE,
                "no ion-neutral cross section or explicit h registered (CHG-06)",
            )),
            (Some(crate::geometry::HModel::Explicit { h_by_surface }), Some(geo), _) => {
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
            (Some(crate::geometry::HModel::Lieberman { sigma_i_m2 }), Some(geo), Some(set)) => {
                self.flags.insert("H_LIEB_ARGON_STATEMENT_EXTRAPOLATED".into());
                let ions: Vec<&str> = set.species.iter().filter(|s| s.charge > 0).map(|s| s.name.as_str()).collect();
                let mut vals = BTreeSet::new();
                for i in &ions {
                    match sigma_i_m2.get(*i) {
                        None => g.plasma.push(r(&format!("CHG-06_SIGMA_I_NOT_REGISTERED:{i}"), S_IE, "")),
                        Some(s) if !ok_pos(s.value) => g.plasma.push(r("IN-17_SIGMA_INVALID", S_ME, i.to_string())),
                        Some(s) => {
                            vals.insert(s.value.to_bits());
                        }
                    }
                }
                if vals.len() > 1 {
                    g.plasma.push(r(
                        "PREREG_GAP_MULTISPECIES_H_LIEB",
                        S_IE,
                        "per-species sigma_i gives per-species h_j; EQ-08 / EQ-09 define one h per surface",
                    ));
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
        // NP-ICP-CHEM-AIR domain: mixed Xe / air compositions are OUT_OF_DOMAIN in v1 (OQ-CHEM-10, FC-CHEM-09).
        let mut comp: Vec<&String> = Vec::new();
        if let Some(NeutralSource::RegisteredPressure { mole_fractions, .. }) = &c.neutral_source {
            comp.extend(mole_fractions.value.iter().filter(|(_, x)| **x > 0.0).map(|(k, _)| k));
        }
        if let Some(f) = &c.feed {
            comp.extend(f.value.mdot_kg_s.iter().filter(|(_, x)| **x > 0.0).map(|(k, _)| k));
        }
        let is_xe = |k: &String| k.to_ascii_uppercase().starts_with("XE");
        if comp.iter().any(|k| is_xe(k)) && comp.iter().any(|k| !is_xe(k)) {
            g.plasma.push(r("FC-CHEM-09_MIXED_XE_AIR_COMPOSITION", S_OOD, "mixed Xe / air composition (OQ-CHEM-10)"));
        }
        // IN-12 neutral source.
        match &c.neutral_source {
            None => g.plasma.push(r("IN-12_NEUTRAL_SOURCE_NOT_REGISTERED", S_IE, "VI-GAS-03 / VI-GAS-04 TBD")),
            Some(NeutralSource::RegisteredPressure { p_icp_pa, t_g_k, mole_fractions }) => {
                if !ok_pos(p_icp_pa.value) || !ok_pos(t_g_k.value) {
                    g.plasma.push(r("IN-12_DOMAIN", S_OOD, "p_ICP and T_g must be > 0"));
                }
                if matches!(c.h_model, Some(crate::geometry::HModel::Lieberman { .. }))
                    && p_icp_pa.value >= P_100_MTORR_PA
                {
                    g.plasma.push(r("DOM-05", S_OOD, format!("p_ICP = {} Pa >= 100 mTorr", p_icp_pa.value)));
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
            Some(NeutralSource::FlowBalance { f_in, t_g_k, sigma_c_m2 }) => {
                if !(f_in.value.is_finite() && (0.0..=1.0).contains(&f_in.value) && ok_pos(t_g_k.value)) {
                    g.plasma.push(r("IN-12_DOMAIN", S_OOD, "f_in in [0, 1] and T_g > 0 required"));
                }
                match &c.feed {
                    None => g.plasma.push(r(
                        "IN-04_FEED_STATE_NOT_EVALUATED",
                        S_NE,
                        "flight: upstream Rust chain not admitted; bench: no MFC records",
                    )),
                    Some(f) => {
                        if let Some(set) = set {
                            for (k, v) in &f.value.mdot_kg_s {
                                if !set.species.iter().any(|s| &s.name == k && s.charge == 0) {
                                    g.plasma.push(r(&format!("IN-05_SPECIES_WITHOUT_CHEMISTRY:{k}"), S_IE, ""));
                                }
                                if !(v.is_finite() && *v >= 0.0) {
                                    g.plasma.push(r("IN-04_MDOT_INVALID", S_ME, k.clone()));
                                }
                            }
                        }
                    }
                }
                match &c.background {
                    None => g.plasma.push(r("IN-13_BACKGROUND_NOT_REGISTERED", S_IE, "no facility / exposure record")),
                    Some(b) => {
                        let any_bg = b.value.n_b_m3.values().any(|v| *v != 0.0);
                        let tau_ne_1 = geo.is_some_and(|geo| {
                            geo.surfaces.iter().filter(|s| s.kind.is_open()).any(|s| match &s.transmission {
                                Some(Transmission::Registered { tau }) => *tau != 1.0,
                                Some(Transmission::SantelerTube { length_m, .. }) => *length_m != 0.0,
                                None => false,
                            })
                        });
                        if any_bg && tau_ne_1 {
                            g.plasma.push(r(
                                "PREREG_FINDING_PF-02_BACKGROUND_INFLOW_WITHOUT_TAU",
                                S_IE,
                                "EQ-02 books background inflow over A_open without tau while effusion carries tau; inconsistent unless tau = 1 (v2 needed)",
                            ));
                        }
                    }
                }
                if let Some(set) = set {
                    for s in set.species.iter().filter(|s| s.charge == 0) {
                        if !sigma_c_m2.contains_key(&s.name) {
                            g.plasma.push(r(&format!("DOM-04_SIGMA_C_NOT_REGISTERED:{}", s.name), S_IE, ""));
                        }
                        if s.recombines_to.is_some() {
                            match c.wall_recombination.get(&s.name) {
                                None => g.plasma.push(r(&format!("IN-18_GAMMA_NOT_REGISTERED:{}", s.name), S_IE, "")),
                                Some(gm) => {
                                    if matches!(gm.evidence.uncertainty, Some(UncertaintyRepr::PhysicalBound { .. })) {
                                        self.flags.insert("BOUNDED_BY_PHYSICAL_LIMITS".into());
                                    }
                                    if gm.value != 0.0 {
                                        g.plasma.push(r(
                                            "PREREG_FINDING_PF-01_EQ02_ATOM_RECOMBINATION_FACTOR",
                                            S_IE,
                                            "EQ-02 removes (gamma/2) of the atom wall flux; with gamma a per-collision probability (NP-ICP-CHEM-AIR AIR-WALL-02/03) the atom loss is gamma; v2 needed",
                                        ));
                                    }
                                }
                            }
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
    }

    fn downstream_gates(&mut self, g: &mut Gate) {
        let c = self.case;
        let m = self.m;
        // IF-ICP-BUS-v1.
        match &c.bus {
            None => g.bus.push(r("NE-09_FLIGHT_ETA_RF_ETA_BIAS_PENDING", S_NE, "IN-19 not registered")),
            Some(b) => {
                if b.boundary_id != ACTIVE_BUS_BOUNDARY {
                    g.bus.push(r(
                        "A9.30_BUS_BOUNDARY",
                        S_ME,
                        format!("{} is not {ACTIVE_BUS_BOUNDARY}", b.boundary_id),
                    ));
                }
                if b.ground_facility_only {
                    g.bus.push(r(
                        "GROUND_FACILITY_ONLY",
                        S_NE,
                        "a laboratory generator or mains input is never bus power",
                    ));
                }
                for v in coupling::bus_registration_violations(b) {
                    g.bus.push(r("CC-06_REGISTRATION_REFUSED", S_ME, v));
                }
            }
        }
        // IF-ICP-HALL-v1 (FC-01, FC-02).
        match &c.hall_demand {
            None => {
                if m.ensemble_member_count == 0 {
                    g.hall.push(r("CREDIBLE_HALL_TRANSPORT_SET_EMPTY", S_NE, "transport_ensemble_v0 members = []"));
                }
                g.hall.push(r("I_D_MAX_H1_NOT_REGISTERED", S_NE, "P1-IT-07 not registered"));
            }
            Some(h) => match h.basis {
                HallDemandBasis::MeasuredRegistration => {}
                HallDemandBasis::AdmittedHallMember if m.ensemble_member_count == 0 => g.hall.push(r(
                    "CREDIBLE_HALL_TRANSPORT_SET_EMPTY",
                    S_NE,
                    "no admitted member to produce I_d,max,H1",
                )),
                HallDemandBasis::AdmittedHallMember => {}
                HallDemandBasis::ScreeningCandidate => {
                    g.hall.push(r("IF-ICP-HALL-v1_SCREENING_CANDIDATE_REFUSED", S_ME, "never a screening candidate"))
                }
                HallDemandBasis::SupplyRating => {
                    g.hall.push(r("IF-ICP-HALL-v1_SUPPLY_RATING_REFUSED", S_ME, "never the 8.33 A stand ceiling"))
                }
            },
        }
        if c.configuration == Configuration::FlightHallOn {
            g.hall.push(r("CFG-FLIGHT-HALL-ON_NOT_EVALUATED", S_NE, "I_e,cap is a CFG-CAP-OFF measurand"));
        }
        // IF-ICP-FEED-v1 dedicated flow.
        if c.gas_mode.value != GasMode::GReuse && c.dedicated_flow_kg_s.is_none() {
            g.dedicated.push(r("IF-ICP-FEED-v1_DEDICATED_FLOW_NOT_REGISTERED", S_NE, c.gas_mode.value.as_str()));
        }
    }

    /// Reduce the registered case to numbers (and run EQ-12 / EQ-13 in CM-CAL).
    fn prepare(&mut self, set: &ChemistrySet) -> Result<(PreparedCase, Option<Calibrated>), Vec<Reason>> {
        let c = self.case;
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
            crate::geometry::HModel::Explicit { h_by_surface } => {
                PreparedH::Explicit(geo.surfaces.iter().map(|s| h_by_surface[&s.id].value).collect())
            }
            crate::geometry::HModel::Lieberman { sigma_i_m2 } => PreparedH::Lieberman {
                sigma_i_m2: set
                    .species
                    .iter()
                    .find(|s| s.charge > 0)
                    .map(|s| sigma_i_m2[&s.name].value)
                    .ok_or_else(|| vec![r("IN-17_NO_ION_SPECIES", S_ME, "H-LIEB needs an ion species")])?,
            },
        };
        let ns = set.species.len();
        let (neutrals, t_g) = match c.neutral_source.as_ref().expect("gated") {
            NeutralSource::RegisteredPressure { p_icp_pa, t_g_k, mole_fractions } => {
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
            NeutralSource::FlowBalance { f_in, t_g_k, .. } => {
                let feed = &c.feed.as_ref().expect("gated").value;
                let bg = &c.background.as_ref().expect("gated").value;
                let a_open: f64 = geo.surfaces.iter().filter(|s| s.kind.is_open()).map(|s| s.area_m2).sum();
                let inflow = (0..ns)
                    .map(|i| {
                        let s = &set.species[i];
                        if s.charge > 0 {
                            return 0.0;
                        }
                        let feed_in = f_in.value * feed.mdot_kg_s.get(&s.name).copied().unwrap_or(0.0) / s.mass_kg;
                        let nb = bg.n_b_m3.get(&s.name).copied().unwrap_or(0.0);
                        let bg_in = if nb == 0.0 {
                            0.0
                        } else {
                            0.25 * nb * physics::neutral_mean_speed(bg.t_b_k, s.mass_kg) * a_open
                        };
                        feed_in + bg_in
                    })
                    .collect();
                (PreparedNeutrals::Flow { inflow_per_s: inflow }, t_g_k.value)
            }
        };
        let mut direct = Vec::with_capacity(set.reactions.len());
        for rx in &set.reactions {
            direct.push(match &rx.rate {
                RateSource::Synthetic { .. } => None,
                RateSource::RegisteredTable { file } => {
                    match self.m.chem_channel_for_table(file).map(|c| (c, &c.representation)) {
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
        Ok((
            PreparedCase {
                set: set.clone(),
                volume_m3: geo.volume_m3(),
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

    /// Steps (4) and (5) for one equilibrium: solution domain and conservation.
    fn domain_checks(&self, p: &PreparedCase, b: &Branch) -> (Vec<CheckRecord>, Vec<ValidityRecord>) {
        let mut checks = Vec::new();
        let mut val = Vec::new();
        let (t_e, n, k): (Option<f64>, Vec<f64>, Option<Vec<f64>>) = match b {
            Branch::Trivial(n) => (None, n.clone(), None),
            Branch::Eq(e) => (Some(e.kin.t_e), e.kin.n.clone(), Some(e.kin.k.clone())),
        };
        for (ri, rx) in p.set.reactions.iter().enumerate() {
            let t = p.set.species_index(&rx.target).expect("checked");
            let lim = match rx.validity {
                Validity::Verified { max_mean_energy_ev } => Some(max_mean_energy_ev),
                _ => None,
            };
            // UQ-06 / NV-06 at the solution: the .dat interpolation against the direct rate (cross-check only).
            let (direct_k, dat_k) = match (t_e, &k, &rx.rate) {
                (Some(te), Some(k), RateSource::RegisteredTable { file }) => {
                    (Some(k[ri]), self.m.n2_tables.get(file).and_then(|d| d.rate_at_te(te)))
                }
                _ => (None, None),
            };
            let dat_rel = match (direct_k, dat_k) {
                (Some(a), Some(b)) if a > 0.0 => Some((b - a) / a),
                (Some(a), Some(b)) if a == 0.0 && b == 0.0 => Some(0.0),
                _ => None,
            };
            let (eps, share, st) = match (t_e, &k) {
                (Some(te), Some(k)) => {
                    let active = k[ri] > 0.0 && n[t] > 0.0;
                    let beyond = active && lim.is_some_and(|l| 1.5 * te > l);
                    let share = if beyond { 1.0 } else { 0.0 };
                    (Some(1.5 * te), Some(share), if beyond { S_OOD } else { S_CONV })
                }
                _ => (None, Some(0.0), S_CONV),
            };
            val.push(ValidityRecord {
                reaction: rx.id.clone(),
                validity: match rx.validity {
                    Validity::Verified { .. } => "verified".into(),
                    Validity::Unresolved => "unresolved".into(),
                    Validity::MissingEntry => "missing".into(),
                },
                max_mean_energy_ev: lim,
                mean_energy_ev: eps,
                activity_share_beyond_limit: share,
                status: st,
                direct_rate_m3_s: direct_k,
                dat_rate_m3_s: dat_k,
                dat_minus_direct_relative: dat_rel,
            });
            if st == S_OOD {
                checks.push(CheckRecord {
                    id: format!("DOM-01:{}", rx.id),
                    status: S_OOD,
                    value: eps,
                    tolerance: lim,
                    detail: "3/2 T_e above the table's max_mean_energy_eV with nonzero activity".into(),
                });
            }
        }
        if p.direct.iter().any(Option::is_some) {
            checks.push(CheckRecord {
                id: "IN-24_T_E_SCAN_END".into(),
                status: S_CONV,
                value: Some(p.t_e_scan_max_ev(self.num)),
                tolerance: None,
                detail: "T_e scan end [eV]: the highest T_e at which every registered table is admissible (EQ-06, IX-05: no rate beyond a verified limit); a root beyond it would be OUT_OF_DOMAIN (DOM-01) and is not searched".into(),
            });
        }
        if let Some(te) = t_e {
            let [lo, hi] = p.set.t_e_domain_ev;
            let inside = (lo..=hi).contains(&te);
            checks.push(CheckRecord {
                id: "DOM-02".into(),
                status: if inside { S_CONV } else { S_OOD },
                value: Some(te),
                tolerance: None,
                detail: format!("T_e must lie in [{lo}, {hi}] eV ({})", p.set.set_id),
            });
        }
        let n_g: f64 = p.set.species.iter().zip(&n).filter(|(s, _)| s.charge == 0).map(|(_, x)| x).sum();
        if let (PreparedNeutrals::Flow { .. }, Some(NeutralSource::FlowBalance { sigma_c_m2, .. })) =
            (&p.neutrals, &self.case.neutral_source)
        {
            let sum_ns: f64 = p
                .set
                .species
                .iter()
                .zip(&n)
                .filter(|(s, _)| s.charge == 0)
                .map(|(s, x)| x * sigma_c_m2.get(&s.name).map_or(f64::NAN, |v| v.value))
                .sum();
            let kn = physics::molecular_mean_free_path(sum_ns) / (2.0 * p.radius_m);
            checks.push(CheckRecord {
                id: "DOM-04".into(),
                status: if kn > KN_FREE_MOLECULAR_MIN { S_CONV } else { S_OOD },
                value: Some(kn),
                tolerance: Some(KN_FREE_MOLECULAR_MIN),
                detail: "Kn = lambda / (2R) on the converged neutral state (Chiggiato Table 7)".into(),
            });
            if matches!(p.h, PreparedH::Lieberman { .. }) {
                let pr = n_g * K_B * p.t_g_k;
                checks.push(CheckRecord {
                    id: "DOM-05".into(),
                    status: if pr < P_100_MTORR_PA { S_CONV } else { S_OOD },
                    value: Some(pr),
                    tolerance: Some(P_100_MTORR_PA),
                    detail: "H-LIEB: total neutral pressure < 100 mTorr on the converged state".into(),
                });
            }
        }
        if let Branch::Eq(e) = b {
            let ld = physics::debye_length(e.kin.t_e, e.kin.n_e);
            checks.push(CheckRecord {
                id: "DOM-07".into(),
                status: S_CONV,
                value: Some(ld / p.radius_m.min(p.length_m)),
                tolerance: None,
                detail: "lambda_D / min(R, L), reported only (criterion OPEN, OQ-NPICP-09; eps0 from memory: verify)"
                    .into(),
            });
        }
        for (id, detail) in [
            ("DOM-03", "every rate file used has a verified rate_validity entry"),
            ("DOM-06", "B_ICP,max registered as 0 (in domain)"),
            ("DOM-11", "f_RF = 13.56 MHz"),
            ("DOM-12", "no electronegative species"),
        ] {
            checks.push(CheckRecord {
                id: id.into(),
                status: S_CONV,
                value: None,
                tolerance: None,
                detail: detail.into(),
            });
        }
        checks.push(CheckRecord {
            id: "DOM-13".into(),
            status: S_CONV,
            value: None,
            tolerance: None,
            detail: "Maxwellian EEDF assumed (flag MAXWELLIAN_ASSUMED)".into(),
        });
        (checks, val)
    }

    fn conservation(&self, p: &PreparedCase, b: &Branch) -> Vec<CheckRecord> {
        let mut out = Vec::new();
        let rel = |res: f64, scale: f64| if scale == 0.0 { res.abs() } else { res.abs() / scale };
        let chk = |id: &str, v: f64, detail: &str| CheckRecord {
            id: id.into(),
            status: if v <= TOL_CONS { S_CONV } else { S_ME },
            value: Some(v),
            tolerance: Some(TOL_CONS),
            detail: detail.into(),
        };
        let ne_check = |id: &str, detail: &str| CheckRecord {
            id: id.into(),
            status: S_NE,
            value: None,
            tolerance: Some(TOL_CONS),
            detail: detail.into(),
        };
        let e = match b {
            Branch::Trivial(n) => {
                // n_e = 0: CC-01/CC-02 reduce to the neutral inflow / effusion balance.
                if let PreparedNeutrals::Flow { inflow_per_s } = &p.neutrals {
                    let mut worst: f64 = 0.0;
                    let mut cc02: f64 = 0.0;
                    let open_tau: f64 = p
                        .surfaces
                        .iter()
                        .filter(|s| s.kind.is_open())
                        .map(|s| s.area_m2 * s.tau.unwrap_or(f64::NAN))
                        .sum();
                    for (i, s) in p.set.species.iter().enumerate() {
                        if s.charge == 0 {
                            let out_ = 0.25 * physics::neutral_mean_speed(p.t_g_k, s.mass_kg) * open_tau * n[i];
                            worst = worst.max(rel(inflow_per_s[i] - out_, inflow_per_s[i].max(out_)));
                            cc02 = cc02.max(rel(inflow_per_s[i] - out_, inflow_per_s[i].max(out_)));
                        }
                    }
                    out.push(chk("CC-01", worst, "neutral inflow = effusion on the n_e = 0 branch"));
                    out.push(chk("CC-02", cc02, "element inflow = outflow on the n_e = 0 branch"));
                } else {
                    out.push(ne_check("CC-01", "no plasma and neutral densities registered (EQ-01)"));
                    out.push(ne_check("CC-02", "REGISTERED_PRESSURE: no neutral balance (EQ-01)"));
                }
                out.push(chk("CC-03", 0.0, "no plasma: every surface current is exactly zero"));
                out.push(chk("CC-07", 0.0, "no plasma: no formation energy"));
                return out;
            }
            Branch::Eq(e) => *e,
        };
        let ns = p.set.species.len();
        let v = p.volume_m3;
        let n_e = e.kin.n_e;
        // CC-01 per species: gross gains vs gross losses.
        let mut gain = vec![0.0; ns];
        let mut loss = vec![0.0; ns];
        for (ri, rx) in p.set.reactions.iter().enumerate() {
            if !rx.kind.changes_species() {
                continue;
            }
            let t = p.set.species_index(&rx.target).expect("checked");
            let rate = v * n_e * e.kin.n[t] * e.kin.k[ri];
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
                    if !p.surfaces[j].kind.is_open() {
                        if let PreparedNeutrals::Flow { .. } = p.neutrals {
                            for (wp, cnt) in &sp.wall_products {
                                gain[p.set.species_index(wp).expect("checked")] += f64::from(*cnt) * a * sf.gamma_i[s];
                            }
                        }
                    }
                }
            }
        }
        let open_tau: f64 =
            p.surfaces.iter().filter(|s| s.kind.is_open()).map(|s| s.area_m2 * s.tau.unwrap_or(f64::NAN)).sum();
        let mut effusion = vec![0.0; ns];
        if let PreparedNeutrals::Flow { inflow_per_s } = &p.neutrals {
            for (s, sp) in p.set.species.iter().enumerate() {
                if sp.charge == 0 {
                    gain[s] += inflow_per_s[s];
                    effusion[s] = 0.25 * physics::neutral_mean_speed(p.t_g_k, sp.mass_kg) * open_tau * e.kin.n[s];
                    loss[s] += effusion[s];
                }
            }
        }
        let flow = matches!(p.neutrals, PreparedNeutrals::Flow { .. });
        let mut worst: f64 = 0.0;
        for s in 0..ns {
            if p.set.species[s].charge > 0 || flow {
                worst = worst.max(rel(gain[s] - loss[s], gain[s].max(loss[s])));
            }
        }
        out.push(chk(
            "CC-01",
            worst,
            if flow { "every ion and neutral species" } else { "every ion species (neutrals registered, EQ-01)" },
        ));
        // CC-02 element conservation (FLOW_BALANCE).
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
                for (j, sf) in e.surfaces.iter().enumerate() {
                    if p.surfaces[j].kind.is_open() {
                        outn += (0..ns).map(|s| cnt(s) * p.surfaces[j].area_m2 * sf.gamma_i[s]).sum::<f64>();
                    }
                }
                w = w.max(rel(inn - outn, inn.max(outn)));
            }
            out.push(chk("CC-02", w, "nuclei in (feed + background) = out (effusion + ions through open ends)"));
        } else {
            out.push(ne_check(
                "CC-02",
                "REGISTERED_PRESSURE: no neutral balance (EQ-01); element throughput undefined",
            ));
        }
        // CC-03 currents.
        let big = e.surfaces.iter().map(|s| s.current_ion_a.abs().max(s.current_electron_a.abs())).fold(0.0, f64::max);
        let sum_i: f64 = e.surfaces.iter().map(|s| s.current_a).sum();
        let mut cc03 = rel(sum_i, big);
        for (j, sf) in e.surfaces.iter().enumerate() {
            if p.surfaces[j].kind.is_zero_current() {
                cc03 = cc03.max(rel(sf.current_a, sf.current_ion_a.abs().max(sf.current_electron_a.abs())));
            }
        }
        let i_prod = production_current(p, e);
        let i_loss: f64 = e.surfaces.iter().map(|s| s.current_ion_a).sum();
        cc03 = cc03.max(rel(i_prod - i_loss, i_prod.max(i_loss)));
        out.push(chk(
            "CC-03",
            cc03,
            "sum I_j = 0 (scale: largest current component), floating I_j = 0, production = ion loss current",
        ));
        // CC-07 formation energy.
        let created: f64 = p
            .set
            .reactions
            .iter()
            .enumerate()
            .filter(|(_, rx)| rx.kind == ReactionKind::Ionization)
            .map(|(ri, _)| e.p_reaction_w[ri])
            .sum();
        let released: f64 = e.surfaces.iter().map(|s| s.formation_w).sum();
        if p.set.ion_formation_energies().is_ok()
            && !p
                .set
                .reactions
                .iter()
                .any(|x| matches!(x.kind, ReactionKind::Dissociation | ReactionKind::DissociativeIonization))
        {
            out.push(chk(
                "CC-07",
                rel(created - released, created.max(released)),
                "formation energy created = released + carried out",
            ));
        } else {
            out.push(ne_check(
                "CC-07",
                "formation bookkeeping not exact for this set (route-dependent or dissociative energies)",
            ));
        }
        out
    }

    #[allow(clippy::too_many_lines)]
    fn assemble(
        mut self,
        set: Option<&ChemistrySet>,
        p: Option<&PreparedCase>,
        cal: Option<&Calibrated>,
        outcome: Option<Result<SolveOutcome, solver::SolveFailure>>,
        g: Gate,
    ) -> IcpResult {
        let c = self.case;
        let mut reasons: Vec<Reason> = g.plasma.clone();
        let mut domain_checks = Vec::new();
        let mut chem_val = Vec::new();
        let mut conservation = Vec::new();
        let mut equilibria = Vec::new();
        let mut convergence = Convergence {
            status: S_NE,
            bisection_iterations: None,
            fixed_point_iterations: None,
            species_balance_residual: None,
            quasi_neutrality_residual: None,
            current_balance_residual: None,
            energy_balance_residual: None,
            tol_solve: TOL_SOLVE,
            numerical_settings: numerics_map(self.num),
        };
        // Decide the branch.
        let mut branch: Option<Branch> = None;
        // Evaluation order (worst_of): registration precedes the input domain; every reason is still listed.
        let mut status = worst_of(&g.plasma);
        let mut plasma_state = Label::withheld(status, codes(&g.plasma));
        if let (Some(p), Some(outcome)) = (p, outcome.as_ref()) {
            match outcome {
                Err(f) => {
                    reasons.push(r(&f.code, S_ME, f.detail.clone()));
                    status = S_ME;
                    convergence.status = S_ME;
                    plasma_state = Label::withheld(S_ME, vec![f.code.clone()]);
                }
                Ok(SolveOutcome::NotSustained) => {
                    let n = solver::trivial_neutrals(p);
                    convergence.status = S_CONV;
                    if p.p_abs_w > 0.0 {
                        reasons.push(r(
                            "CC-05_ABSORBED_POWER_WITHOUT_SINK",
                            S_ME,
                            format!(
                                "P_abs = {} W > 0 but no sustained state exists in the scanned T_e domain",
                                p.p_abs_w
                            ),
                        ));
                        status = S_ME;
                        plasma_state = Label::withheld(S_ME, vec!["CC-05_ABSORBED_POWER_WITHOUT_SINK".into()]);
                    } else {
                        status = S_CONV;
                        plasma_state = Label::value("NOT_SUSTAINED");
                    }
                    branch = Some(Branch::Trivial(n));
                }
                Ok(SolveOutcome::Equilibria(eqs)) => {
                    convergence.status = S_CONV;
                    for e in eqs {
                        let (dc, _) = self.domain_checks(p, &Branch::Eq(e));
                        let bad: Vec<&CheckRecord> = dc.iter().filter(|x| x.status != S_CONV).collect();
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
                            domain_status: IcpStatus::worst(bad.iter().map(|x| x.status)),
                            domain_reasons: bad.iter().map(|x| x.id.clone()).collect(),
                        });
                    }
                    if eqs.len() == 1 {
                        let e = &eqs[0];
                        branch = Some(Branch::Eq(e));
                        status = S_CONV;
                        plasma_state = Label::value("SUSTAINED");
                        convergence.bisection_iterations = Some(e.bisection_iterations);
                        convergence.fixed_point_iterations = Some(e.kin.fixed_point_iterations);
                        convergence.species_balance_residual = Some(e.kin.balance_residual);
                        convergence.quasi_neutrality_residual = Some(e.quasi_residual.abs());
                        convergence.current_balance_residual = Some(e.current_residual);
                        let er = (e.p_loss_w - p.p_abs_w).abs() / p.p_abs_w.max(e.p_loss_w);
                        convergence.energy_balance_residual = Some(er);
                        let solve_res = [e.kin.balance_residual, e.quasi_residual.abs(), er];
                        if solve_res.iter().any(|x| !(x.is_finite() && *x <= TOL_SOLVE)) {
                            reasons.push(r("TOL-SOLVE_NOT_MET", S_ME, format!("residuals {solve_res:?}")));
                            status = S_ME;
                            convergence.status = S_ME;
                        }
                    } else {
                        reasons.push(r(
                            "EQUILIBRIUM_SELECTION_NOT_REGISTERED",
                            S_NE,
                            format!("{} equilibria found and reported; no root is chosen silently", eqs.len()),
                        ));
                        status = S_NE;
                        plasma_state = Label::withheld(S_NE, vec!["EQUILIBRIUM_SELECTION_NOT_REGISTERED".into()]);
                    }
                }
            }
        }
        if let (Some(p), Some(b)) = (p, branch.as_ref()) {
            let (dc, val) = self.domain_checks(p, b);
            for x in dc.iter().filter(|x| x.status == S_OOD) {
                reasons.push(r(&x.id, S_OOD, x.detail.clone()));
            }
            domain_checks = dc;
            chem_val = val;
            conservation = self.conservation(p, b);
            if status == S_CONV && reasons.iter().any(|x| x.status == S_OOD) {
                status = S_OOD;
            }
            if let Branch::Eq(e) = b {
                if e.surfaces.iter().zip(&p.surfaces).any(|(s, ps)| s.electron_saturated && ps.potential_v.is_some()) {
                    self.verify.insert("VER-06".into());
                }
                if p.set.species.iter().zip(&e.kin.n).any(|(s, n)| s.charge > 1 && *n > 0.0) {
                    self.verify.insert("VER-08".into());
                }
                self.verify.insert("VER-12".into());
            }
        }
        // Plasma outputs (OUT-01..OUT-07) for the branch, then the partition and the interfaces.
        let plasma_reasons: Vec<Reason> = if status == S_CONV { vec![] } else { reasons.clone() };
        let wh = |unit: &str| Quantity::withheld_by(unit, &plasma_reasons);
        let mut outputs: BTreeMap<String, OutputValue> = BTreeMap::new();
        let usable = status == S_CONV;
        let ion_names: Vec<String> = set
            .map(|s| s.species.iter().filter(|x| x.charge > 0).map(|x| x.name.clone()).collect())
            .unwrap_or_default();
        let neu_names: Vec<String> = set
            .map(|s| s.species.iter().filter(|x| x.charge == 0).map(|x| x.name.clone()).collect())
            .unwrap_or_default();
        let rx_ids: Vec<String> = set.map(|s| s.reactions.iter().map(|x| x.id.clone()).collect()).unwrap_or_default();
        let surf_ids: Vec<String> =
            c.geometry.as_ref().map(|g| g.value.surfaces.iter().map(|s| s.id.clone()).collect()).unwrap_or_default();
        let sc = |o: &mut BTreeMap<String, OutputValue>, k: &str, q: Quantity| {
            o.insert(k.into(), OutputValue::Scalar(q));
        };
        let mp = |o: &mut BTreeMap<String, OutputValue>, k: &str, m: BTreeMap<String, Quantity>| {
            o.insert(k.into(), OutputValue::Map(m));
        };
        let family = |names: &[String], f: &dyn Fn(usize) -> Quantity| -> BTreeMap<String, Quantity> {
            names.iter().enumerate().map(|(i, n)| (n.clone(), f(i))).collect()
        };
        let mut i_e_cap = wh("A");
        let mut binding = Label::withheld(worst_of(&plasma_reasons).max_sev(), codes(&plasma_reasons));
        let mut p_bias_value: Option<f64> = None;
        match (usable, p, branch.as_ref()) {
            (true, Some(p), Some(b)) => {
                let BranchView { t_e, n_e, n, phi, vs, surf_currents, k } = BranchView::of(p, b);
                let undefined = |u: &str| Quantity::undefined(u, "NOT_DEFINED_PLASMA_NOT_SUSTAINED");
                sc(&mut outputs, "P_abs_W", Quantity::value(p.p_abs_w, "W"));
                sc(&mut outputs, "T_e_eV", t_e.map_or_else(|| undefined("eV"), |x| Quantity::value(x, "eV")));
                sc(&mut outputs, "n_e_m3", Quantity::value(n_e, "m^-3"));
                let idx = |name: &str| p.set.species_index(name).expect("known");
                mp(&mut outputs, "n_i_m3", family(&ion_names, &|i| Quantity::value(n[idx(&ion_names[i])], "m^-3")));
                mp(&mut outputs, "n_g_m3", family(&neu_names, &|i| Quantity::value(n[idx(&neu_names[i])], "m^-3")));
                sc(
                    &mut outputs,
                    "phi_p_V",
                    match (b, phi) {
                        (Branch::Trivial(_), _) => undefined("V"),
                        (_, Some(x)) => Quantity::value(x, "V"),
                        (_, None) => Quantity::withheld("V", S_NE, vec!["NO_REFERENCED_ELECTRODE".into()]),
                    },
                );
                sc(&mut outputs, "V_s_float_V", vs.map_or_else(|| undefined("V"), |x| Quantity::value(x, "V")));
                let v = p.volume_m3;
                mp(
                    &mut outputs,
                    "R_r_per_s",
                    family(&rx_ids, &|ri| {
                        let t = idx(&p.set.reactions[ri].target);
                        Quantity::value(v * n_e * n[t] * k[ri], "s^-1")
                    }),
                );
                let ion_loss = |s: usize| -> f64 {
                    match b {
                        Branch::Trivial(_) => 0.0,
                        Branch::Eq(e) => {
                            e.surfaces.iter().zip(&p.surfaces).map(|(st, ps)| ps.area_m2 * st.gamma_i[s]).sum()
                        }
                    }
                };
                mp(
                    &mut outputs,
                    "I_iz_s_A",
                    family(&ion_names, &|i| {
                        let s = idx(&ion_names[i]);
                        Quantity::value(E_CHARGE * f64::from(p.set.species[s].charge) * ion_loss(s), "A")
                    }),
                );
                let n_heavy: f64 = n.iter().sum();
                mp(
                    &mut outputs,
                    "ion_fraction",
                    family(&ion_names, &|i| {
                        let x = n[idx(&ion_names[i])];
                        Quantity::value(if n_heavy > 0.0 { x / n_heavy } else { 0.0 }, "-")
                    }),
                );
                let molecules: Vec<String> = p
                    .set
                    .species
                    .iter()
                    .filter(|s| {
                        s.charge == 0 && p.set.species.iter().any(|a| a.recombines_to.as_ref() == Some(&s.name))
                    })
                    .map(|s| s.name.clone())
                    .collect();
                mp(
                    &mut outputs,
                    "dissociation_fraction",
                    family(&molecules, &|i| {
                        let mol = &molecules[i];
                        let m_i = idx(mol);
                        let atoms: f64 = p
                            .set
                            .species
                            .iter()
                            .enumerate()
                            .filter(|(_, a)| a.charge == 0 && a.recombines_to.as_ref() == Some(mol))
                            .map(|(ai, _)| n[ai])
                            .sum();
                        let tot = atoms + 2.0 * n[m_i];
                        Quantity::value(if tot > 0.0 { atoms / tot } else { 0.0 }, "-")
                    }),
                );
                let i_prod = match b {
                    Branch::Trivial(_) => 0.0,
                    Branch::Eq(e) => production_current(p, e),
                };
                sc(&mut outputs, "I_production_A", Quantity::value(i_prod, "A"));
                // OUT-06.
                let ec = p.surfaces.iter().position(|s| s.kind == SurfaceKind::ElectronCollector);
                let (cap, thermal, ion_lim) = match b {
                    Branch::Trivial(_) => (0.0, 0.0, 0.0),
                    Branch::Eq(e) => {
                        let vbar = physics::electron_mean_speed(e.kin.t_e);
                        let cap = ec.map_or(0.0, |j| -e.surfaces[j].current_a);
                        let thermal =
                            ec.map_or(0.0, |j| 0.25 * E_CHARGE * e.kin.h[j] * e.kin.n_e * vbar * p.surfaces[j].area_m2);
                        let ion_lim: f64 = e
                            .surfaces
                            .iter()
                            .zip(&p.surfaces)
                            .filter(|(_, ps)| ps.kind == SurfaceKind::IonCollectorBiased)
                            .map(|(s, _)| s.current_ion_a)
                            .sum();
                        (cap, thermal, ion_lim)
                    }
                };
                i_e_cap = Quantity::value(cap, "A");
                sc(&mut outputs, "I_e_thermal_limit_A", Quantity::value(thermal, "A"));
                sc(&mut outputs, "I_ion_collection_limit_A", Quantity::value(ion_lim, "A"));
                let bounds = [("THERMAL_FLUX", thermal), ("ION_COLLECTION", ion_lim), ("PRODUCTION", i_prod)];
                let bmin =
                    bounds.iter().copied().fold(("THERMAL_FLUX", f64::INFINITY), |a, x| if x.1 < a.1 { x } else { a });
                binding = match b {
                    Branch::Trivial(_) => {
                        Label { value: None, status: S_CONV, reasons: vec!["NOT_DEFINED_PLASMA_NOT_SUSTAINED".into()] }
                    }
                    Branch::Eq(_) => Label::value(bmin.0),
                };
                mp(
                    &mut outputs,
                    "I_surface_A",
                    p.surfaces
                        .iter()
                        .zip(&surf_currents)
                        .map(|(s, i)| (s.id.clone(), Quantity::value(*i, "A")))
                        .collect(),
                );
                // Bias supply output (EQ-16): -sum_j I_j V_j over the biased surfaces.
                p_bias_value = Some(
                    -p.surfaces
                        .iter()
                        .zip(&surf_currents)
                        .filter_map(|(s, i)| s.potential_v.map(|v| i * v))
                        .sum::<f64>(),
                );
            }
            _ => {
                for k in ["P_abs_W", "T_e_eV", "n_e_m3", "phi_p_V", "V_s_float_V", "I_production_A"] {
                    sc(&mut outputs, k, wh(unit_of(k)));
                }
                sc(&mut outputs, "I_e_thermal_limit_A", wh("A"));
                sc(&mut outputs, "I_ion_collection_limit_A", wh("A"));
                for (k, names, u) in [
                    ("n_i_m3", &ion_names, "m^-3"),
                    ("n_g_m3", &neu_names, "m^-3"),
                    ("R_r_per_s", &rx_ids, "s^-1"),
                    ("I_iz_s_A", &ion_names, "A"),
                    ("ion_fraction", &ion_names, "-"),
                    ("I_surface_A", &surf_ids, "A"),
                ] {
                    mp(&mut outputs, k, names.iter().map(|n| (n.clone(), wh(u))).collect());
                }
                mp(&mut outputs, "dissociation_fraction", BTreeMap::new());
            }
        }
        sc(&mut outputs, "I_e_cap_A", i_e_cap.clone());
        outputs.insert("binding_limit".into(), OutputValue::Label(binding.clone()));
        outputs.insert("plasma_state".into(), OutputValue::Label(plasma_state.clone()));
        // OUT-07 (FC-03).
        let mut out07 = vec!["OUT-07_NOT_REPRESENTED_IN_V1".to_string()];
        if self.m.ensemble_member_count == 0 {
            out07.push("CREDIBLE_HALL_TRANSPORT_SET_EMPTY".into());
        }
        sc(&mut outputs, "I_e_neutralization_available_A", Quantity::withheld("A", S_NE, out07));
        // I_e_sat (EQ-11).
        let i_e_sat = self.i_e_sat(p, usable, &g, &plasma_reasons, branch.as_ref());
        sc(&mut outputs, "I_e_sat_A", i_e_sat.clone());
        // OUT-02 coupling quantities.
        let coup_reasons: Vec<Reason> =
            if !g.coupling.is_empty() { g.coupling.clone() } else { plasma_reasons.clone() };
        let coup = |v: Option<f64>, u: &str| match (cal, v) {
            (Some(_), Some(x)) if status == S_CONV => Quantity::value(x, u),
            _ => Quantity::withheld_by(u, &coup_reasons),
        };
        sc(&mut outputs, "R_p_ohm", coup(cal.map(|k| k.r_p_ohm), "ohm"));
        sc(&mut outputs, "R_ant_ohm", coup(cal.map(|k| k.r_ant_ohm), "ohm"));
        sc(&mut outputs, "X_ant_ohm", coup(cal.map(|k| k.x_ant_ohm), "ohm"));
        sc(&mut outputs, "eta_p", coup(cal.map(|k| k.eta_p), "-"));
        sc(&mut outputs, "I_ant_rms_A", coup(cal.map(|k| k.i_ant_rms_a), "A"));
        sc(&mut outputs, "P_delivered_W", coup(cal.map(|k| k.p_delivered_w), "W"));

        let mut surface_terms = BTreeMap::new();
        if let Some(geo) = &c.geometry {
            for (j, s) in geo.value.surfaces.iter().enumerate() {
                let kind =
                    serde_json::to_value(s.kind).ok().and_then(|v| v.as_str().map(String::from)).unwrap_or_default();
                let q = |f: &dyn Fn(&solver::SurfaceState) -> f64, u: &str| match (usable, branch.as_ref()) {
                    (true, Some(Branch::Eq(e))) => Quantity::value(f(&e.surfaces[j]), u),
                    (true, Some(Branch::Trivial(_))) => Quantity::value(0.0, u),
                    _ => Quantity::withheld_by(u, &plasma_reasons),
                };
                let pot = match (usable, branch.as_ref()) {
                    (true, Some(Branch::Eq(e))) => e.surfaces[j].potential_v.map_or_else(
                        || Quantity::withheld("V", S_NE, vec!["NO_REFERENCED_ELECTRODE".into()]),
                        |v| Quantity::value(v, "V"),
                    ),
                    (true, Some(Branch::Trivial(_))) => Quantity::undefined("V", "NOT_DEFINED_PLASMA_NOT_SUSTAINED"),
                    _ => Quantity::withheld_by("V", &plasma_reasons),
                };
                surface_terms.insert(
                    s.id.clone(),
                    SurfaceTerms {
                        kind,
                        thermal_node: s.thermal_node.as_str().into(),
                        potential_v: pot,
                        gamma_e_m2_s: q(&|x| x.gamma_e, "m^-2 s^-1"),
                        gamma_z_m2_s: q(&|x| x.gamma_z, "m^-2 s^-1"),
                        l_w: q(&|x| x.l_w, "W"),
                        c_w: q(&|x| x.c_w, "W"),
                        formation_w: q(&|x| x.formation_w, "W"),
                    },
                );
            }
        }
        let thermal = self.thermal(p, cal, branch.as_ref().filter(|_| usable), p_bias_value, &plasma_reasons, &g);
        let mut scenario_sets = Vec::new();
        if thermal.assignments.len() > 1 {
            scenario_sets
                .push("IN-23 disposition bounding pair ALL_RADIATED / ALL_WALL (IF-ICP-THERMAL-v1)".to_string());
        }
        let bus = self.bus(cal, p_bias_value, usable, &g, &plasma_reasons);
        for a in &thermal.assignments {
            for x in &a.closures {
                if x.status == S_ME {
                    reasons.push(r(&x.id, S_ME, x.detail.clone()));
                }
            }
        }
        for x in &bus.checks {
            if x.status == S_ME {
                reasons.push(r(&x.id, S_ME, x.detail.clone()));
            }
        }
        for x in &conservation {
            if x.status == S_ME {
                reasons.push(r(&x.id, S_ME, x.detail.clone()));
            }
        }
        let hall = self.hall(&i_e_cap, &i_e_sat, &binding, &g);
        let feed = self.feed(set, p, branch.as_ref().filter(|_| usable), &g, &plasma_reasons);

        let mut result = IcpResult {
            schema: "abep_icp_raw_output_v1".into(),
            case_id: c.case_id.clone(),
            supply_mode: c.supply_mode.value.as_str().into(),
            gas_mode: c.gas_mode.value.as_str().into(),
            configuration: c.configuration.as_str().into(),
            coupling_mode: c.coupling_mode.as_str().into(),
            status,
            plasma_state,
            reasons: vec![],
            flags: self.flags.clone(),
            verify_items_on_path: self.verify.clone(),
            verification_status: "IMPLEMENTED_UNVERIFIED".into(),
            validation_status: "NOT_VALIDATED".into(),
            outputs,
            surface_terms,
            if_icp_thermal_v1: thermal,
            if_icp_bus_v1: bus,
            if_icp_hall_v1: hall,
            if_icp_feed_v1: feed,
            domain_checks,
            chemistry_validity: chem_val,
            conservation,
            convergence,
            equilibria,
            uncertainty: UncertaintyRecord {
                sampled_envelope: Label::withheld(
                    S_NE,
                    vec!["UQ-03_SAMPLING_NEEDS_ADMITTED_ABEP_RNG (SC-WP-10)".into()],
                ),
                u_model_form: Label::withheld(S_NE, vec!["UQ-05_NO_VALIDATION_RESIDUALS".into()]),
                scenario_sets: scenario_sets.clone(),
            },
            provenance: self.provenance(),
        };
        // Step (5): a conservation breach anywhere makes the whole case MODEL_ERROR with every physics value null.
        if result.status == S_CONV && reasons.iter().any(|x| x.status == S_ME) {
            result.status = S_ME;
            let me: Vec<Reason> = reasons.iter().filter(|x| x.status == S_ME).cloned().collect();
            withhold_physics(&mut result, &me);
        }
        reasons.sort();
        reasons.dedup();
        result.reasons = reasons;
        result
    }

    fn i_e_sat(
        &self,
        p: Option<&PreparedCase>,
        usable: bool,
        g: &Gate,
        plasma_reasons: &[Reason],
        b: Option<&Branch>,
    ) -> Quantity {
        if !usable {
            return Quantity::withheld_by("A", plasma_reasons);
        }
        if !g.sat.is_empty() {
            return Quantity::withheld_by("A", &g.sat);
        }
        let p = p.expect("usable");
        if let Some(Branch::Trivial(_)) = b {
            return Quantity::value(0.0, "A");
        }
        let ec = p.surfaces.iter().position(|s| s.kind == SurfaceKind::ElectronCollector).expect("gated");
        let sweep =
            self.case.electrodes.as_ref().and_then(|e| e.value.collector_bias_sweep_v.clone()).unwrap_or_default();
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

    #[allow(clippy::too_many_lines)]
    fn thermal(
        &mut self,
        p: Option<&PreparedCase>,
        cal: Option<&Calibrated>,
        b: Option<&Branch>,
        p_bias: Option<f64>,
        plasma_reasons: &[Reason],
        g: &Gate,
    ) -> ThermalRecord {
        let c = self.case;
        let match_loc = match &c.bus {
            Some(bus) if bus.match_colocated.value => Label::value("N_MATCH"),
            Some(_) => Label::value("B_PPU_RF"),
            None => Label::withheld(S_NE, vec!["ICD_ICP-13_MATCH_COLOCATED_NOT_REGISTERED".into()]),
        };
        let mut consumes = BTreeMap::new();
        let t_gas = match &c.neutral_source {
            Some(NeutralSource::RegisteredPressure { t_g_k, .. }) | Some(NeutralSource::FlowBalance { t_g_k, .. }) => {
                Quantity::value(t_g_k.value, "K")
            }
            None => Quantity::withheld("K", S_IE, vec!["IN-12_NEUTRAL_SOURCE_NOT_REGISTERED".into()]),
        };
        consumes.insert("T_gas_K".into(), OutputValue::Scalar(t_gas));
        match &c.thermal_boundary {
            Some(tb) => {
                consumes.insert(
                    "T_wall_K".into(),
                    OutputValue::Map(
                        tb.value.t_wall_k.iter().map(|(k, v)| (k.clone(), Quantity::value(*v, "K"))).collect(),
                    ),
                );
                consumes.insert(
                    "T_coil_K".into(),
                    OutputValue::Scalar(tb.value.t_coil_k.map_or_else(
                        || Quantity::withheld("K", S_NE, vec!["IN-14_T_COIL_NOT_REGISTERED".into()]),
                        |t| Quantity::value(t, "K"),
                    )),
                );
            }
            None => {
                let q = Quantity::withheld("K", S_NE, vec!["IN-14_THERMAL_BOUNDARY_NOT_EVALUATED".into()]);
                consumes.insert("T_wall_K".into(), OutputValue::Scalar(q.clone()));
                consumes.insert("T_coil_K".into(), OutputValue::Scalar(q));
            }
        }
        let coup_reasons: Vec<Reason> =
            if !g.coupling.is_empty() { g.coupling.clone() } else { plasma_reasons.to_vec() };
        let bus_reasons: Vec<Reason> = if !g.bus.is_empty() { g.bus.clone() } else { coup_reasons.clone() };
        let rf = |v: Option<f64>, rs: &[Reason]| {
            v.map_or_else(|| Quantity::withheld_by("W", rs), |x| Quantity::value(x, "W"))
        };
        let lumped = vec![Reason::new("LUMPED_R_VAC", S_NE, "line and match loss lumped into Q_icp_coil_ohmic_W")];
        let (q_line, q_match) = match cal {
            Some(k) if k.lumped_r_vac => (Quantity::withheld_by("W", &lumped), Quantity::withheld_by("W", &lumped)),
            Some(k) => (rf(k.q_line_w, &coup_reasons), rf(k.q_match_w, &coup_reasons)),
            None => (Quantity::withheld_by("W", &coup_reasons), Quantity::withheld_by("W", &coup_reasons)),
        };
        let p_bus = match (&c.bus, cal, p_bias) {
            (Some(reg), Some(k), Some(pb)) if g.bus.is_empty() => {
                coupling::bus_plane(reg, k.p_fwd_w, k.p_refl_w, pb).ok().map(|x| x.p_bus_w)
            }
            _ => None,
        };
        let p_bias_q = match p_bias {
            Some(x) => Quantity::value(x, "W"),
            None => Quantity::withheld_by("W", plasma_reasons),
        };
        // Partition gate (EQ-16 / EQ-18 cases the prereg does not define operationally).
        let mut part_gate: Vec<Reason> = Vec::new();
        if let Some(p) = p {
            let has = |k: &[ReactionKind]| p.set.reactions.iter().any(|x| k.contains(&x.kind));
            if has(&[
                ReactionKind::ElasticMomentumTransfer,
                ReactionKind::ExcitationVibrational,
                ReactionKind::ExcitationRotational,
            ]) {
                part_gate.push(r(
                    "PREREG_GAP_EQ16_NEUTRAL_ENERGY_SPLIT",
                    S_IE,
                    "EQ-16 notes: neutral energy goes to walls 'or carried out ... in proportion to their loss channels' without an operational split; the wall / outflow keys are withheld (v2 needed)",
                ));
            }
            if has(&[ReactionKind::Dissociation, ReactionKind::DissociativeIonization]) {
                part_gate.push(r(
                    "PREREG_GAP_EQ18_ATOM_FORMATION_ENERGY_DISPOSAL",
                    S_IE,
                    "atom formation energy and fragment kinetic energy need the atom loss channels (gamma envelope, neutral split)",
                ));
            }
            if p.set.ion_formation_energies().is_err() {
                part_gate.push(r("EQ-18_FORMATION_ROUTE_INCONSISTENT", S_IE, "route-dependent ion formation energy"));
            }
            if c.dispositions.values().any(|d| d.value == Disposition::CarriedOut) {
                part_gate.push(r("PREREG_GAP_EQ16_CARRIED_OUT_SPLIT", S_IE, "no registered split between open ends"));
            }
        }
        let unresolved = p.is_some_and(|p| {
            p.set.reactions.iter().any(|x| {
                x.kind == ReactionKind::ExcitationElectronic
                    && c.dispositions.get(&x.id).is_none_or(|d| d.value == Disposition::Unresolved)
            })
        });
        let assignments: Vec<&str> = if unresolved { vec!["ALL_RADIATED", "ALL_WALL"] } else { vec!["AS_REGISTERED"] };
        let mut out = Vec::new();
        for a in assignments {
            let mut keys: BTreeMap<String, Quantity> = BTreeMap::new();
            let mut by_surface = BTreeMap::new();
            let mut by_node = BTreeMap::new();
            let mut bias_by_surface = BTreeMap::new();
            let mut closures = Vec::new();
            keys.insert("P_icp_rf_forward_W".into(), rf(cal.map(|k| k.p_fwd_w), &coup_reasons));
            keys.insert("P_icp_rf_reflected_W".into(), rf(cal.map(|k| k.p_refl_w), &coup_reasons));
            keys.insert("Q_icp_coil_ohmic_W".into(), rf(cal.map(|k| k.q_coil_ohmic_w), &coup_reasons));
            keys.insert("Q_icp_line_W".into(), q_line.clone());
            keys.insert("Q_icp_match_W".into(), q_match.clone());
            keys.insert("P_icp_bus_W".into(), rf(p_bus, &bus_reasons));
            keys.insert("P_icp_collector_bias_W".into(), p_bias_q.clone());
            match (p, b) {
                (Some(p), Some(b)) => {
                    let surf: Vec<(f64, f64, f64)> = match b {
                        Branch::Trivial(_) => p.surfaces.iter().map(|_| (0.0, 0.0, 0.0)).collect(),
                        Branch::Eq(e) => e.surfaces.iter().map(|s| (s.l_w, s.c_w, s.formation_w)).collect(),
                    };
                    let (mut exc_rad, mut exc_wall) = (0.0, 0.0);
                    if let Branch::Eq(e) = b {
                        for (ri, x) in p.set.reactions.iter().enumerate() {
                            if x.kind != ReactionKind::ExcitationElectronic {
                                continue;
                            }
                            let d = c.dispositions.get(&x.id).map_or(Disposition::Unresolved, |d| d.value);
                            let to_rad = match d {
                                Disposition::RadiatedOpticallyThin => true,
                                Disposition::WallQuenched | Disposition::CarriedOut => false,
                                Disposition::Unresolved => a == "ALL_RADIATED",
                            };
                            if to_rad {
                                exc_rad += e.p_reaction_w[ri];
                            } else {
                                exc_wall += e.p_reaction_w[ri];
                            }
                        }
                    }
                    let sum_kind = |f: &dyn Fn(SurfaceKind) -> bool| -> f64 {
                        p.surfaces.iter().zip(&surf).filter(|(s, _)| f(s.kind)).map(|(_, x)| x.0 + x.2).sum()
                    };
                    let q_pw = sum_kind(&|k| k.is_neutralizer_wall()) + exc_wall;
                    let q_ext = sum_kind(&|k| k == SurfaceKind::ElectronCollector);
                    let q_up = sum_kind(&|k| k == SurfaceKind::OpenUpstream);
                    let q_down = sum_kind(&|k| k == SurfaceKind::OpenDownstream);
                    let q_bc: f64 = p
                        .surfaces
                        .iter()
                        .zip(&surf)
                        .filter(|(s, _)| s.kind == SurfaceKind::IonCollectorBiased)
                        .map(|(_, x)| x.1)
                        .sum();
                    let q_be: f64 = p
                        .surfaces
                        .iter()
                        .zip(&surf)
                        .filter(|(s, _)| s.kind == SurfaceKind::ElectronCollector)
                        .map(|(_, x)| x.1)
                        .sum();
                    if exc_wall > 0.0 {
                        self.flags.insert("AREA_WEIGHTED_NEUTRAL_TERMS".into());
                    }
                    let a_wall: f64 =
                        p.surfaces.iter().filter(|s| s.kind.is_neutralizer_wall()).map(|s| s.area_m2).sum();
                    let mut nodes: BTreeMap<String, f64> = BTreeMap::new();
                    for (s, x) in p.surfaces.iter().zip(&surf) {
                        if s.kind.is_neutralizer_wall() {
                            by_surface.insert(s.id.clone(), Quantity::value(x.0, "W"));
                            let share = if a_wall > 0.0 { exc_wall * s.area_m2 / a_wall } else { 0.0 };
                            *nodes.entry(s.node.as_str().into()).or_insert(0.0) += x.0 + x.2 + share;
                        }
                        if s.kind.is_biased() {
                            bias_by_surface.insert(s.id.clone(), Quantity::value(x.1, "W"));
                        }
                    }
                    let gated = !part_gate.is_empty();
                    let gq =
                        |x: f64| if gated { Quantity::withheld_by("W", &part_gate) } else { Quantity::value(x, "W") };
                    keys.insert("P_icp_abs_W".into(), Quantity::value(p.p_abs_w, "W"));
                    keys.insert("Q_icp_plasma_wall_W".into(), gq(q_pw));
                    keys.insert("Q_icp_outflow_upstream_W".into(), gq(q_up));
                    keys.insert("Q_icp_outflow_downstream_W".into(), gq(q_down));
                    keys.insert("Q_icp_extraction_W".into(), gq(q_ext));
                    keys.insert("Q_icp_radiation_W".into(), gq(exc_rad));
                    keys.insert("Q_icp_bias_collector_W".into(), Quantity::value(q_bc, "W"));
                    keys.insert("Q_icp_bias_export_W".into(), Quantity::value(q_be, "W"));
                    for node in [
                        ThermalNode::NVessel,
                        ThermalNode::NAntenna,
                        ThermalNode::NMount,
                        ThermalNode::NCollector,
                        ThermalNode::NHousing,
                    ] {
                        let v = nodes.get(node.as_str()).copied().unwrap_or(0.0);
                        by_node.insert(node.as_str().to_string(), gq(v));
                    }
                    let pb = p_bias.unwrap_or(0.0);
                    let scale = match cal {
                        Some(k) => k.p_fwd_w.abs() + pb.abs(),
                        None => p.p_abs_w.abs() + pb.abs(),
                    };
                    let rel = |res: f64| if scale == 0.0 { res.abs() } else { res.abs() / scale };
                    let ck = |id: &str, v: f64, d: &str| CheckRecord {
                        id: format!("{id}[{a}]"),
                        status: if v <= TOL_CONS { S_CONV } else { S_ME },
                        value: Some(v),
                        tolerance: Some(TOL_CONS),
                        detail: d.into(),
                    };
                    let ne = |id: &str, d: &str| CheckRecord {
                        id: format!("{id}[{a}]"),
                        status: S_NE,
                        value: None,
                        tolerance: Some(TOL_CONS),
                        detail: d.into(),
                    };
                    if gated {
                        closures.push(ne("CC-05-RF-POWERED", "partition withheld (see PREREG_GAP / EQ-18 reasons)"));
                        closures.push(ne("CC-05-COMBINED", "partition withheld"));
                    } else {
                        closures.push(ck(
                            "CC-05-RF-POWERED",
                            rel(p.p_abs_w - (q_pw + q_ext + exc_rad + q_up + q_down)),
                            "P_abs = Q_plasma_wall + Q_extraction + Q_radiation + Q_outflow_up + Q_outflow_down",
                        ));
                        let lhs = match cal {
                            Some(k) => k.p_fwd_w + pb,
                            None => p.p_abs_w + pb,
                        };
                        let rf_part = cal.map_or(0.0, |k| {
                            k.p_refl_w + k.q_line_w.unwrap_or(0.0) + k.q_match_w.unwrap_or(0.0) + k.q_coil_ohmic_w
                        });
                        closures.push(ck(
                            "CC-05-COMBINED",
                            rel(lhs - (rf_part + q_pw + q_ext + exc_rad + q_up + q_down + q_bc + q_be)),
                            if cal.is_some() {
                                "P_fwd + P_bias = sum of the eleven partition keys"
                            } else {
                                "CM-ABS form: P_abs + P_bias = plasma partition + bias keys"
                            },
                        ));
                        let neg: Vec<&str> = [
                            ("Q_icp_plasma_wall_W", q_pw),
                            ("Q_icp_extraction_W", q_ext),
                            ("Q_icp_radiation_W", exc_rad),
                        ]
                        .iter()
                        .filter(|(_, v)| *v < 0.0)
                        .map(|(k, _)| *k)
                        .collect();
                        closures.push(CheckRecord {
                            id: format!("CC-05-NONNEGATIVE[{a}]"),
                            status: if neg.is_empty() { S_CONV } else { S_ME },
                            value: None,
                            tolerance: None,
                            detail: format!("five deposited keys >= 0 (IFI-2); negative: {neg:?}"),
                        });
                    }
                    closures.push(ck(
                        "CC-05-BIAS",
                        rel(pb - (q_bc + q_be)),
                        "P_collector_bias (= -sum I_j V_j, computed independently) = Q_bias_collector + Q_bias_export",
                    ));
                    if let Some(k) = cal {
                        let rhs = k.p_refl_w
                            + k.q_line_w.unwrap_or(0.0)
                            + k.q_match_w.unwrap_or(0.0)
                            + k.q_coil_ohmic_w
                            + k.p_abs_w;
                        closures.push(CheckRecord {
                            id: format!("CC-04[{a}]"),
                            status: if (k.p_fwd_w - rhs).abs() <= TOL_CONS * k.p_fwd_w.abs() { S_CONV } else { S_ME },
                            value: Some(if k.p_fwd_w == 0.0 {
                                (k.p_fwd_w - rhs).abs()
                            } else {
                                (k.p_fwd_w - rhs).abs() / k.p_fwd_w
                            }),
                            tolerance: Some(TOL_CONS),
                            detail: "P_fwd = P_refl + Q_line + Q_match + Q_coil_ohmic + P_abs".into(),
                        });
                    } else {
                        closures.push(ne("CC-04", "CM-ABS: no RF chain is claimed"));
                    }
                }
                _ => {
                    for k in [
                        "P_icp_abs_W",
                        "Q_icp_plasma_wall_W",
                        "Q_icp_outflow_upstream_W",
                        "Q_icp_outflow_downstream_W",
                        "Q_icp_extraction_W",
                        "Q_icp_radiation_W",
                        "Q_icp_bias_collector_W",
                        "Q_icp_bias_export_W",
                    ] {
                        keys.insert(k.into(), Quantity::withheld_by("W", plasma_reasons));
                    }
                }
            }
            out.push(ThermalAssignment {
                assignment: a.into(),
                keys,
                q_icp_plasma_wall_by_surface_w: by_surface,
                q_icp_plasma_wall_by_node_w: by_node,
                q_icp_bias_by_surface_w: bias_by_surface,
                q_icp_coil_ohmic_split_w: Quantity::withheld(
                    "W",
                    S_NE,
                    vec!["COIL_OHMIC_SPLIT_NOT_REGISTERED (induced shares are not predicted in v1)".into()],
                ),
                q_icp_match_w_location: match_loc.clone(),
                closures,
            });
        }
        let status = IcpStatus::worst(out.iter().flat_map(|a| a.keys.values().map(|q| q.status)));
        ThermalRecord {
            interface: "IF-ICP-THERMAL-v1".into(),
            consumer: "NP-THERMAL-CATHODELESS v1 (IK-01..IK-07, IFI-1..IFI-5)".into(),
            rf_powered_only: true,
            assignments: out,
            consumes,
            hall_powered_heat:
                "none computed or added here (Hall-side keys of IF-HALL-THERMAL-v1; CFG-CAP-OFF has the discharge off)"
                    .into(),
            status,
        }
    }

    fn bus(
        &self,
        cal: Option<&Calibrated>,
        p_bias: Option<f64>,
        usable: bool,
        g: &Gate,
        plasma_reasons: &[Reason],
    ) -> BusRecord {
        let c = self.case;
        let mut why: Vec<Reason> = g.bus.clone();
        if !usable {
            why.extend(plasma_reasons.iter().cloned());
        }
        let mut keys = BTreeMap::new();
        let mut slots = BTreeMap::new();
        let mut checks = Vec::new();
        let p_bias_q = p_bias.map_or_else(|| Quantity::withheld_by("W", plasma_reasons), |x| Quantity::value(x, "W"));
        keys.insert("P_icp_collector_bias_W".to_string(), p_bias_q);
        let plane = match (&c.bus, cal, p_bias) {
            (Some(reg), Some(k), Some(pb)) if why.is_empty() => {
                match coupling::bus_plane(reg, k.p_fwd_w, k.p_refl_w, pb) {
                    Ok(x) => Some(x),
                    Err(e) => {
                        why.push(e);
                        None
                    }
                }
            }
            _ => None,
        };
        let q = |v: Option<f64>| v.map_or_else(|| Quantity::withheld_by("W", &why), |x| Quantity::value(x, "W"));
        keys.insert("P_icp_rf_forward_W".into(), q(plane.as_ref().map(|_| cal.unwrap().p_fwd_w)));
        keys.insert("P_icp_rf_reflected_W".into(), q(plane.as_ref().map(|_| cal.unwrap().p_refl_w)));
        keys.insert("P_icp_rf_source_DC_W".into(), q(plane.as_ref().map(|x| x.p_rf_source_dc_w)));
        keys.insert("P_icp_matching_DC_W".into(), q(plane.as_ref().map(|x| x.p_matching_dc_w)));
        keys.insert("P_icp_assist_magnet_W".into(), q(plane.as_ref().map(|x| x.p_assist_magnet_w)));
        keys.insert("P_icp_flow_control_W".into(), q(plane.as_ref().map(|x| x.p_flow_control_w)));
        keys.insert("P_icp_bus_W".into(), q(plane.as_ref().map(|x| x.p_bus_w)));
        keys.insert("Q_icp_rf_generator_loss_W".into(), q(plane.as_ref().map(|x| x.q_rf_generator_loss_w)));
        keys.insert("Q_icp_bias_supply_loss_W".into(), q(plane.as_ref().map(|x| x.q_bias_supply_loss_w)));
        slots.insert("icp_rf_source".into(), q(plane.as_ref().map(|x| x.p_rf_source_dc_w)));
        slots.insert("icp_matching_network".into(), q(plane.as_ref().map(|x| x.p_matching_dc_w)));
        slots.insert("icp_collector_bias".into(), q(plane.as_ref().map(|x| x.p_bias_dc_w)));
        slots.insert("icp_assist_magnet".into(), q(plane.as_ref().map(|x| x.p_assist_magnet_w)));
        slots.insert("flow_control_icp_feed".into(), q(plane.as_ref().map(|x| x.p_flow_control_w)));
        if let (Some(x), Some(k)) = (&plane, cal) {
            let sum = x.p_rf_source_dc_w + x.p_matching_dc_w + x.p_bias_dc_w + x.p_assist_magnet_w + x.p_flow_control_w;
            let res = (x.p_bus_w - sum).abs() / x.p_bus_w.max(f64::MIN_POSITIVE);
            let losses_ok = x.q_rf_generator_loss_w >= 0.0 && x.q_bias_supply_loss_w >= 0.0;
            let src_ok = x.p_rf_source_dc_w >= k.p_fwd_w;
            checks.push(CheckRecord {
                id: "CC-06".into(),
                status: if res <= TOL_CONS && losses_ok && src_ok { S_CONV } else { S_ME },
                value: Some(res),
                tolerance: Some(TOL_CONS),
                detail: format!("bus = sum of slots; losses >= 0: {losses_ok}; P_RF,DC >= P_fwd: {src_ok}"),
            });
        } else {
            checks.push(CheckRecord {
                id: "CC-06".into(),
                status: S_NE,
                value: None,
                tolerance: Some(TOL_CONS),
                detail: "bus plane not evaluated".into(),
            });
        }
        let status = if plane.is_some() { S_CONV } else { worst_of(&why).max_sev() };
        BusRecord {
            interface: "IF-ICP-BUS-v1".into(),
            target_boundary: ACTIVE_BUS_BOUNDARY.into(),
            keys,
            slots,
            checks,
            status,
            reasons: codes(&why),
        }
    }

    fn hall(&self, i_e_cap: &Quantity, i_e_sat: &Quantity, binding: &Label, g: &Gate) -> HallRecord {
        let c = self.case;
        let i_d = match &c.hall_demand {
            Some(h) if g.hall.is_empty() => Quantity::value(h.i_d_max_h1_a.value, "A"),
            _ => Quantity::withheld_by("A", &g.hall),
        };
        let mut why: Vec<Reason> = g.hall.clone();
        if !i_e_cap.is_converged_value() {
            why.push(r("I_E_CAP_NOT_CONVERGED", i_e_cap.status, i_e_cap.reasons.join(",")));
        }
        let mut unc = BTreeMap::new();
        let unc_why = vec!["UQ-03_SAMPLING_NEEDS_ADMITTED_ABEP_RNG (SC-WP-10)".to_string()];
        unc.insert(
            "nominal".into(),
            if i_e_cap.is_converged_value() {
                i_e_cap.clone()
            } else {
                Quantity::withheld("A", i_e_cap.status, i_e_cap.reasons.clone())
            },
        );
        for k in ["p2_5", "p97_5", "min", "max", "u_input"] {
            unc.insert(k.into(), Quantity::withheld("A", S_NE, unc_why.clone()));
        }
        unc.insert("u_model_form".into(), Quantity::withheld("A", S_NE, vec!["UQ-05_NO_VALIDATION_RESIDUALS".into()]));
        HallRecord {
            interface: "IF-ICP-HALL-v1".into(),
            configuration: c.configuration.as_str().into(),
            h1_point_id: c.h1_point_id.clone(),
            supply_mode: c.supply_mode.value.as_str().into(),
            coupling_mode: c.coupling_mode.as_str().into(),
            i_e_cap_a: i_e_cap.clone(),
            i_e_sat_a: i_e_sat.clone(),
            binding_limit: binding.clone(),
            validation_status: "NOT_VALIDATED".into(),
            uncertainty: unc,
            i_d_max_h1_a: i_d,
            i_d_max_h1_basis: c.hall_demand.as_ref().map(|h| format!("{:?}", h.basis)),
            coupled_status: if why.is_empty() { S_CONV } else { worst_of(&why).max_sev() },
            coupled_reasons: codes(&why),
        }
    }

    fn feed(
        &self,
        set: Option<&ChemistrySet>,
        p: Option<&PreparedCase>,
        b: Option<&Branch>,
        g: &Gate,
        plasma_reasons: &[Reason],
    ) -> FeedRecord {
        let c = self.case;
        let mut species: Vec<String> = set
            .map(|s| s.species.iter().filter(|x| x.charge == 0).map(|x| x.name.clone()).collect())
            .unwrap_or_default();
        if let ChemistryRegistration::NotRegistered { gas } = &c.chemistry {
            species.push(gas.clone());
        }
        if let Some(f) = &c.feed {
            species.extend(f.value.mdot_kg_s.keys().cloned());
        }
        species.sort();
        species.dedup();
        let dedicated: BTreeMap<String, Quantity> = species
            .iter()
            .map(|s| {
                let q = match c.gas_mode.value {
                    GasMode::GReuse => Quantity::value(0.0, "kg/s"),
                    _ if !g.dedicated.is_empty() => Quantity::withheld_by("kg/s", &g.dedicated),
                    _ => Quantity::value(
                        c.dedicated_flow_kg_s.as_ref().and_then(|d| d.value.get(s).copied()).unwrap_or(0.0),
                        "kg/s",
                    ),
                };
                (s.clone(), q)
            })
            .collect();
        let mut conv = BTreeMap::new();
        if let Some(set) = set {
            for (i, s) in set.species.iter().enumerate() {
                let q = match (p, b) {
                    (Some(_), Some(Branch::Trivial(_))) => Quantity::value(0.0, "kg/s"),
                    (Some(p), Some(Branch::Eq(e))) => {
                        let mut net = 0.0;
                        for (ri, rx) in p.set.reactions.iter().enumerate() {
                            if !rx.kind.changes_species() {
                                continue;
                            }
                            let t = p.set.species_index(&rx.target).expect("checked");
                            let rate = p.volume_m3 * e.kin.n_e * e.kin.n[t] * e.kin.k[ri];
                            if t == i {
                                net -= rate;
                            }
                            for (pn, cnt) in &rx.products {
                                if *pn == s.name {
                                    net += f64::from(*cnt) * rate;
                                }
                            }
                        }
                        Quantity::value(s.mass_kg * net, "kg/s")
                    }
                    _ => Quantity::withheld_by("kg/s", plasma_reasons),
                };
                conv.insert(s.name.clone(), q);
            }
        }
        let mut consumes = BTreeMap::new();
        match &c.feed {
            Some(f) => {
                consumes.insert(
                    "mdot_s_kg_s".into(),
                    OutputValue::Map(
                        f.value.mdot_kg_s.iter().map(|(k, v)| (k.clone(), Quantity::value(*v, "kg/s"))).collect(),
                    ),
                );
                consumes.insert("P_feed_Pa".into(), OutputValue::Scalar(Quantity::value(f.value.p_feed_pa, "Pa")));
                consumes.insert("T_feed_K".into(), OutputValue::Scalar(Quantity::value(f.value.t_feed_k, "K")));
                consumes.insert(
                    "x_s".into(),
                    OutputValue::Map(f.value.x_s.iter().map(|(k, v)| (k.clone(), Quantity::value(*v, "-"))).collect()),
                );
            }
            None => {
                let q = Quantity::withheld("-", S_NE, vec!["IN-04_FEED_STATE_NOT_EVALUATED".into()]);
                for k in ["mdot_s_kg_s", "P_feed_Pa", "T_feed_K", "x_s"] {
                    consumes.insert(k.into(), OutputValue::Scalar(q.clone()));
                }
            }
        }
        FeedRecord {
            interface: "IF-ICP-FEED-v1".into(),
            gas_mode: c.gas_mode.value.as_str().into(),
            supply_mode: c.supply_mode.value.as_str().into(),
            consumes,
            mdot_icp_dedicated_kg_s: dedicated,
            booking: match c.gas_mode.value {
                GasMode::GReuse => {
                    "G-REUSE: no dedicated ICP flow (A9.1 HIQ-06); the ICP draws on the Hall throughput".into()
                }
                GasMode::GXe => "G-XE: Xe ledger, PHASE_TOTAL_FLOW".into(),
                GasMode::GAtm => "G-ATM: mdot_atm,total = mdot_Hall + mdot_ICP,dedicated (ICD ICP-26)".into(),
            },
            dmdot_conversion_kg_s: conv,
        }
    }

    fn provenance(&self) -> Provenance {
        let c = self.case;
        let h = |v: &dyn erased::Ser| sha256_hex(v.json().as_bytes());
        let mut input = BTreeMap::new();
        input.insert("case".into(), h(&c));
        input.insert("chemistry".into(), h(&c.chemistry));
        input.insert("geometry".into(), h(&c.geometry));
        input.insert("electrodes".into(), h(&c.electrodes));
        input.insert("neutral_source".into(), h(&c.neutral_source));
        input.insert("rf_input".into(), h(&c.rf_input));
        Provenance {
            model_id: MODEL_ID.into(),
            model_version: MODEL_VERSION.into(),
            contract_id: CONTRACT_ID.into(),
            prereg_lock_sha256: self.m.prereg_lock_sha256.clone(),
            prereg_sha256: self.m.prereg_sha256.clone(),
            addendum_01_sha256: self.m.addendum_sha256.clone(),
            chem_air_lock_sha256: self.m.chem_air_lock_sha256.clone(),
            chem_registry: self.m.chem_registry_provenance(),
            input_sha256: input,
            data_files_sha256: self.m.files_read.iter().map(|f| (f.path.clone(), f.sha256.clone())).collect(),
            rust_commit: self.m.rust_commit.clone(),
        }
    }
}

mod erased {
    pub trait Ser {
        fn json(&self) -> String;
    }
    impl<T: serde::Serialize> Ser for T {
        fn json(&self) -> String {
            serde_json::to_string(self).expect("serializable")
        }
    }
}

/// I_production = e V sum_r dZ_r R_r (charge created per second; dZ = 1 for single ionization).
pub fn production_current(p: &PreparedCase, e: &Equilibrium) -> f64 {
    p.set
        .reactions
        .iter()
        .enumerate()
        .filter(|(_, x)| matches!(x.kind, ReactionKind::Ionization | ReactionKind::DissociativeIonization))
        .map(|(ri, x)| {
            let t = p.set.species_index(&x.target).expect("checked");
            let z_in = p.set.species[t].charge;
            let z_out: u32 = x
                .products
                .iter()
                .map(|(pn, cnt)| p.set.species[p.set.species_index(pn).expect("checked")].charge * cnt)
                .sum();
            E_CHARGE * f64::from(z_out - z_in) * p.volume_m3 * e.kin.n_e * e.kin.n[t] * e.kin.k[ri]
        })
        .sum()
}

fn unit_of(k: &str) -> &'static str {
    match k {
        "P_abs_W" => "W",
        "T_e_eV" => "eV",
        "n_e_m3" => "m^-3",
        "phi_p_V" | "V_s_float_V" => "V",
        _ => "A",
    }
}

fn numerics_map(n: &NumericalSettings) -> BTreeMap<String, f64> {
    [
        ("t_e_scan_min_ev", n.t_e_scan_min_ev),
        ("t_e_scan_max_ev", n.t_e_scan_max_ev),
        ("t_e_scan_points", n.t_e_scan_points as f64),
        ("n_e_scan_min_m3", n.n_e_scan_min_m3),
        ("n_e_scan_max_m3", n.n_e_scan_max_m3),
        ("n_e_points_per_decade", n.n_e_points_per_decade as f64),
        ("bisection_max_iter", n.bisection_max_iter as f64),
        ("fixed_point_max_iter", n.fixed_point_max_iter as f64),
        ("fixed_point_rel_tol", n.fixed_point_rel_tol),
    ]
    .into_iter()
    .map(|(k, v)| (k.to_string(), v))
    .collect()
}

trait MaxSev {
    fn max_sev(self) -> IcpStatus;
}

impl MaxSev for IcpStatus {
    /// A withheld value never carries CONVERGED.
    fn max_sev(self) -> IcpStatus {
        if self.is_converged() {
            S_ME
        } else {
            self
        }
    }
}

/// MODEL_ERROR: every physics value null (status vocabulary). Registered-input echoes (dedicated flow, I_d,max,H1,
/// consumed temperatures) are not physics values and stay.
fn withhold_physics(res: &mut IcpResult, why: &[Reason]) {
    let codes: Vec<String> = why.iter().map(|x| x.code.clone()).collect();
    let null = |q: &mut Quantity| {
        if q.value.is_some() || q.status == S_CONV {
            *q = Quantity::withheld(&q.unit.clone(), S_ME, codes.clone());
        }
    };
    let null_ov = |v: &mut OutputValue| match v {
        OutputValue::Scalar(q) => null(q),
        OutputValue::Map(m) => m.values_mut().for_each(null),
        OutputValue::Label(l) => *l = Label::withheld(S_ME, codes.clone()),
    };
    res.outputs.values_mut().for_each(null_ov);
    for t in res.surface_terms.values_mut() {
        for q in
            [&mut t.potential_v, &mut t.gamma_e_m2_s, &mut t.gamma_z_m2_s, &mut t.l_w, &mut t.c_w, &mut t.formation_w]
        {
            null(q);
        }
    }
    res.plasma_state = Label::withheld(S_ME, codes.clone());
    for a in &mut res.if_icp_thermal_v1.assignments {
        a.keys.values_mut().for_each(null);
        a.q_icp_plasma_wall_by_surface_w.values_mut().for_each(null);
        a.q_icp_plasma_wall_by_node_w.values_mut().for_each(null);
        a.q_icp_bias_by_surface_w.values_mut().for_each(null);
    }
    res.if_icp_thermal_v1.status = S_ME;
    res.if_icp_bus_v1.keys.values_mut().for_each(null);
    res.if_icp_bus_v1.slots.values_mut().for_each(null);
    res.if_icp_bus_v1.status = S_ME;
    null(&mut res.if_icp_hall_v1.i_e_cap_a);
    null(&mut res.if_icp_hall_v1.i_e_sat_a);
    res.if_icp_hall_v1.uncertainty.values_mut().for_each(null);
    res.if_icp_hall_v1.binding_limit = Label::withheld(S_ME, codes.clone());
    res.if_icp_hall_v1.coupled_status = S_ME;
    res.if_icp_feed_v1.dmdot_conversion_kg_s.values_mut().for_each(null);
}
