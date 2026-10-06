//! Case assembly: record and topology validation, evidence availability and the governance gates (status precedence
//! steps 1-2), case-domain checks (D-04, D-05, FT-12, FT-15), interface deposition (E-07, E-13, IFH / IFI, CONS-I1,
//! CONS-I2) and compilation of the network (E-03..E-09). Every reason found is recorded; nothing is defaulted.

use super::case::*;
use super::governance::GovernedContext;
use super::network::*;
use super::output::{InterfaceDerived, Reason, RunStatus};
use super::props::{Prop, PropertyForm};
use super::series::TimeValue;
use super::vocab::{self, Deposition};
use abep_provenance::sha256_hex;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

/// D-07 view-factor tolerances.
pub const VF_SUM_TOL: f64 = 1e-9;
pub const VF_RECIPROCITY_REL_TOL: f64 = 1e-9;
/// E-07 weight-sum tolerance (consistent with CONS-I2: 1e-12 relative).
pub const WEIGHT_SUM_TOL: f64 = 1e-12;
/// CONS-I2.
pub const CONS_I2_REL: f64 = 1e-12;
pub const CONS_I2_ABS: f64 = 1e-12;
/// NUM-09 eps_if = 1e-6 x reference + 1e-9 W.
pub const EPS_IF_REL: f64 = 1e-6;
pub const EPS_IF_ABS: f64 = 1e-9;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Mode {
    Steady,
    OrbitAverageSteady { period: f64 },
    Transient { t0: f64, t1: f64, dt: f64 },
    OrbitPeriodic { period: f64, dt: f64 },
}

/// Admissible temperature range of a node (D-10) and the records that set its ends.
#[derive(Debug, Clone)]
pub struct Range {
    pub lo: f64,
    pub lo_rec: String,
    pub hi: f64,
    pub hi_rec: String,
}

impl Range {
    fn new() -> Self {
        Range { lo: 0.0, lo_rec: "absolute zero".into(), hi: f64::INFINITY, hi_rec: "none".into() }
    }
    fn add(&mut self, p_min: f64, p_max: f64, rec: &str) {
        if p_min > self.lo {
            self.lo = p_min;
            self.lo_rec = rec.to_string();
        }
        if p_max < self.hi {
            self.hi = p_max;
            self.hi_rec = rec.to_string();
        }
    }
}

#[derive(Debug, Clone)]
pub struct BiotC {
    pub volume: f64,
    pub area: f64,
    pub k: Prop,
}

#[derive(Debug, Clone)]
pub struct Compiled {
    pub net: Net,
    pub mode: Mode,
    pub t_init: Vec<f64>,
    pub ranges_steady: Vec<Range>,
    pub ranges_transient: Vec<Range>,
    pub biot: Vec<Option<BiotC>>,
    /// Per node: (surface area, emittance) of its surfaces (D-02 radiative conductance).
    pub node_surfaces: Vec<Vec<(f64, Prop)>>,
    /// Boundary name of a link with a fixed end.
    pub link_boundary: Vec<Option<String>>,
    pub derived: Option<InterfaceDerived>,
    pub exported: BTreeMap<String, Vec<f64>>,
    pub booked: BTreeMap<String, Vec<f64>>,
    pub breakpoints: Vec<f64>,
}

#[derive(Debug, Clone, Default)]
pub struct Assembly {
    pub reasons: Vec<Reason>,
    pub labels: BTreeSet<String>,
    pub ensemble_member_ids: BTreeSet<String>,
    pub interface_hashes: BTreeMap<String, String>,
    pub input_set_sha256: String,
    pub compiled: Option<Compiled>,
}

/// Node receivers of one key: (node, weight), EXPORT weight, BOUNDARY weight (E-07).
type Receivers = (Vec<(usize, f64)>, f64, f64);
/// surface id -> (node, area, emittance, solar absorptance, external).
type SurfaceMap = BTreeMap<String, (usize, f64, Prop, Option<Prop>, bool)>;
/// Per node: (mass or area, property) pairs.
type NodeParts = Vec<Vec<(f64, Prop)>>;
/// E-13 quantities, exported and booked flows (per interface time index), and the interface breakpoints.
type InterfaceOutcome = (Option<InterfaceDerived>, BTreeMap<String, Vec<f64>>, BTreeMap<String, Vec<f64>>, Vec<f64>);

/// Structural surface (independent of whether its records resolve).
struct SurfStruct {
    node: usize,
    external: bool,
    alpha_declared: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum StructKind {
    Node(usize),
    Fixed,
    Sink,
}

/// Enclosure structure for the floating-node check: member kinds and the view factors when they resolve.
struct EnclStruct {
    kinds: Vec<StructKind>,
    f: Option<Vec<Vec<f64>>>,
}

#[derive(Default)]
struct Radiation {
    compiled: Vec<EnclC>,
    node_surfaces: NodeParts,
    resolved: SurfaceMap,
    structure: BTreeMap<String, SurfStruct>,
    enclosures: Vec<EnclStruct>,
}

struct NodeInfo {
    base: Option<&'static vocab::RegisteredNode>,
    role: String,
    receives: BTreeSet<String>,
}

struct KeyVal {
    status: String,
    values: Option<Vec<f64>>,
    evidence: String,
    map_derived: bool,
}

struct Iface {
    keys: BTreeMap<String, KeyVal>,
    breakpoints: Option<Vec<f64>>,
    n: usize,
}

impl Iface {
    fn tv(&self, values: &[f64]) -> TimeValue {
        match &self.breakpoints {
            None => TimeValue::Constant(values[0]),
            Some(t) => TimeValue::Zoh { t: t.clone(), v: values.to_vec() },
        }
    }
    fn evaluated(&self, key: &str) -> Option<&Vec<f64>> {
        self.keys.get(key).filter(|k| k.status == "EVALUATED").and_then(|k| k.values.as_ref())
    }
}

struct Asm<'a> {
    case: &'a ThermalCase,
    gov: &'a GovernedContext,
    synthetic: bool,
    np_scope: bool,
    records: BTreeMap<String, &'a InputRecord>,
    reasons: Vec<Reason>,
    labels: BTreeSet<String>,
    members: BTreeSet<String>,
    node_index: BTreeMap<String, usize>,
    nodes: Vec<NodeInfo>,
    time_values: Vec<(String, TimeValue, bool)>,
}

fn is_hex64(s: &str) -> bool {
    s.len() == 64 && s.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

fn phys_ok(q: &str, v: f64) -> bool {
    if !v.is_finite() {
        return false;
    }
    match q {
        "mass" | "area" | "length" | "volume" | "shape_factor" | "conductance" | "contact_conductance_coefficient" => {
            v > 0.0
        }
        "projected_area" | "temperature" | "solar_flux" | "olr_flux" | "density" | "pressure" | "velocity" => v >= 0.0,
        "albedo" | "view_factor_env" | "illumination" | "energy_accommodation" => (0.0..=1.0).contains(&v),
        _ => true,
    }
}

fn prop_value_ok(q: &str, v: f64) -> bool {
    match q {
        "emittance_IR" => v > 0.0 && v <= 1.0,
        "absorptance_solar" => (0.0..=1.0).contains(&v),
        _ => v > 0.0,
    }
}

impl<'a> Asm<'a> {
    fn push(&mut self, status: RunStatus, code: &str, subject: &str, detail: impl Into<String>) {
        self.reasons.push(Reason { status, code: code.into(), subject: subject.into(), detail: detail.into() });
    }
    fn me(&mut self, code: &str, subject: &str, detail: impl Into<String>) {
        self.push(RunStatus::ModelError, code, subject, detail);
    }
    fn has_blocking(&self) -> bool {
        self.reasons.iter().any(|r| r.status != RunStatus::OutOfDomain)
    }

    // ---------------------------------------------------------------- records (record_format, registered_inputs.rules)

    fn validate_records(&mut self) {
        let case = self.case;
        for (i, r) in case.records.iter().enumerate() {
            let subj = r.id.clone().unwrap_or_else(|| format!("records[{i}]"));
            let Some(id) = &r.id else {
                self.me("RECORD_FIELD_MISSING", &subj, "id");
                continue;
            };
            if self.records.insert(id.clone(), r).is_some() {
                self.me("RECORD_ID_DUPLICATE", id, "record id registered twice");
            }
            let fields: [(&str, bool); 8] = [
                ("quantity", r.quantity.is_some()),
                ("units", r.units.is_some()),
                ("source", r.source.is_some()),
                ("evidence_class", r.evidence_class.is_some()),
                ("uncertainty", r.uncertainty.is_some()),
                ("applicability_domain", r.applicability_domain.is_some()),
                ("validation_status", r.validation_status.is_some()),
                ("status", r.status.is_some()),
            ];
            for (f, present) in fields {
                if !present {
                    self.me("RECORD_FIELD_MISSING", id, f);
                }
            }
            if let Some(s) = &r.status {
                if !vocab::RECORD_STATUSES.contains(&s.as_str()) {
                    self.me("RECORD_STATUS_UNKNOWN", id, s.clone());
                } else if s == "REGISTERED" && r.value.is_none() {
                    self.me("RECORD_FIELD_MISSING", id, "value (status REGISTERED)");
                }
            }
            if let Some(q) = &r.quantity {
                match vocab::quantity(q) {
                    None => self.me("RECORD_QUANTITY_UNKNOWN", id, q.clone()),
                    Some((units, _)) => {
                        if r.units.as_deref().is_some_and(|u| u != units) {
                            self.me(
                                "RECORD_UNITS_MISMATCH",
                                id,
                                format!("units {:?}, quantity {q} is registered in {units:?}", r.units),
                            );
                        }
                    }
                }
            }
            if let Some(ec) = &r.evidence_class {
                self.check_evidence_class(ec, id);
            }
        }
    }

    fn check_evidence_class(&mut self, ec: &str, subject: &str) {
        if !vocab::EVIDENCE_CLASSES.contains(&ec) {
            self.me("EVIDENCE_CLASS_UNKNOWN", subject, ec.to_string());
        } else if ec == "owner-allocation" {
            self.me("OWNER_ALLOCATION_NOT_A_MODEL_INPUT", subject, "no owner allocation is a model input in v1");
        } else if self.synthetic && ec != vocab::SYNTHETIC {
            self.me(
                "EVIDENCE_RECORD_IN_SYNTHETIC_CASE",
                subject,
                format!("evidence class {ec:?} mixed into a SYNTHETIC_VERIFICATION case"),
            );
        } else if !self.synthetic && ec == vocab::SYNTHETIC {
            self.me(
                "SYNTHETIC_RECORD_IN_NON_SYNTHETIC_CASE",
                subject,
                format!("SYNTHETIC_TEST_DATA_NOT_EVIDENCE in a {} case", self.case.case_class),
            );
        }
    }

    /// A record usable as a value: present, of the expected quantity, REGISTERED, not a bounds-only record.
    fn get(&mut self, id: &str, quantity: &str, user: &str) -> Option<&'a Value> {
        let Some(rec) = self.records.get(id).copied() else {
            self.me("RECORD_NOT_FOUND", id, format!("needed by {user}"));
            return None;
        };
        if rec.quantity.as_deref() != Some(quantity) {
            self.me(
                "RECORD_QUANTITY_MISMATCH",
                id,
                format!("{user} needs quantity {quantity}, record has {:?}", rec.quantity),
            );
            return None;
        }
        match rec.status.as_deref() {
            Some("REGISTERED") => {}
            Some("NOT_EVALUATED") => {
                self.push(RunStatus::NotEvaluated, "INPUT_NOT_EVALUATED", id, format!("needed by {user}"));
                return None;
            }
            Some(s @ ("TBD" | "TBD_AFTER_EVIDENCE" | "OPEN" | "REFUSED")) => {
                self.push(
                    RunStatus::IncompleteEvidence,
                    "INPUT_NOT_REGISTERED",
                    id,
                    format!("status {s}; needed by {user}"),
                );
                return None;
            }
            _ => return None,
        }
        let v = rec.value.as_ref()?;
        if v.get("bounds").is_some() {
            self.push(
                RunStatus::IncompleteEvidence,
                "BOUNDS_RECORD_NEEDS_SCENARIO_EXPANSION",
                id,
                format!("{user} needs a value; bounds are expanded by the UQ layer (U-02, U-04)"),
            );
            return None;
        }
        Some(v)
    }

    fn shape_err(&mut self, id: &str, detail: impl Into<String>) {
        self.me("RECORD_VALUE_SHAPE", id, detail);
    }

    fn scalar(&mut self, id: &str, q: &str, user: &str) -> Option<f64> {
        let v = self.get(id, q, user)?;
        let Some(x) = v.as_f64() else {
            self.shape_err(id, format!("quantity {q} needs a number"));
            return None;
        };
        if !phys_ok(q, x) {
            self.me("VALUE_NOT_PHYSICAL", id, format!("{q} = {x}"));
            return None;
        }
        Some(x)
    }

    fn tvalue(&mut self, id: &str, q: &str, user: &str) -> Option<TimeValue> {
        let v = self.get(id, q, user)?;
        let tv = if let Some(x) = v.as_f64() {
            TimeValue::Constant(x)
        } else {
            let t = v.get("breakpoints_s").and_then(Value::as_array);
            let vals = v.get("values").and_then(Value::as_array);
            let (Some(t), Some(vals)) = (t, vals) else {
                self.shape_err(id, "needs a number or {breakpoints_s, values}");
                return None;
            };
            if v.as_object().is_some_and(|o| o.len() != 2) {
                self.shape_err(id, "ZOH series has fields other than breakpoints_s / values");
                return None;
            }
            let t: Vec<f64> = t.iter().map(|x| x.as_f64().unwrap_or(f64::NAN)).collect();
            let vals: Vec<f64> = vals.iter().map(|x| x.as_f64().unwrap_or(f64::NAN)).collect();
            TimeValue::Zoh { t, v: vals }
        };
        if let Err(e) = tv.check() {
            self.shape_err(id, e);
            return None;
        }
        if let Some(x) = tv.values().into_iter().find(|x| !phys_ok(q, *x)) {
            self.me("VALUE_NOT_PHYSICAL", id, format!("{q} = {x}"));
            return None;
        }
        self.time_values.push((id.to_string(), tv.clone(), q == "temperature"));
        Some(tv)
    }

    fn t_range(&mut self, id: &str) -> Option<(f64, f64)> {
        let rec = self.records.get(id).copied()?;
        let d = rec.applicability_domain.as_ref()?;
        match (d.t_min_k, d.t_max_k) {
            (Some(a), Some(b)) if a.is_finite() && b.is_finite() && a < b => Some((a, b)),
            _ => {
                self.me("PROPERTY_RANGE_MISSING", id, "applicability_domain needs finite T_min_K < T_max_K (D-01)");
                None
            }
        }
    }

    fn prop(&mut self, id: &str, q: &str, user: &str) -> Option<Prop> {
        let v = self.get(id, q, user)?;
        let form: PropertyForm = match serde_json::from_value(v.clone()) {
            Ok(f) => f,
            Err(e) => {
                self.shape_err(id, format!("property form: {e}"));
                return None;
            }
        };
        let (t_min, t_max) = self.t_range(id)?;
        if let Err(e) = form.check(t_min, t_max) {
            self.shape_err(id, e);
            return None;
        }
        let pts: Vec<f64> = match &form {
            PropertyForm::Constant { value } => vec![*value],
            PropertyForm::PiecewiseLinear { values, .. } => values.clone(),
            PropertyForm::Polynomial { .. } => vec![form.value(t_min), form.value(t_max)],
        };
        if let Some(x) = pts.into_iter().find(|x| !prop_value_ok(q, *x)) {
            self.me("VALUE_NOT_PHYSICAL", id, format!("{q} = {x} inside its validity range"));
            return None;
        }
        if q == "emittance_IR" || q == "absorptance_solar" {
            let gray = self.records.get(id).and_then(|r| r.applicability_domain.as_ref()).and_then(|d| d.gray_in_band);
            match gray {
                None => {
                    self.me("RECORD_FIELD_MISSING", id, "applicability_domain.gray_in_band (D-03)");
                    return None;
                }
                Some(false) => {
                    self.push(
                        RunStatus::OutOfDomain,
                        "NON_GRAY_IN_BAND",
                        id,
                        "record flagged non-gray inside its band; no two-band split registered (D-03)",
                    );
                    return None;
                }
                Some(true) => {}
            }
        }
        Some(Prop { record_id: id.to_string(), form, t_min, t_max })
    }

    fn ranged(&mut self, id: &str, q: &str, user: &str) -> Option<(f64, f64, f64)> {
        let x = self.scalar(id, q, user)?;
        let (a, b) = self.t_range(id)?;
        Some((x, a, b))
    }

    fn matrix(&mut self, id: &str, user: &str) -> Option<BTreeMap<String, BTreeMap<String, f64>>> {
        let v = self.get(id, "view_factor_matrix", user)?;
        match v.get("view_factors").map(|m| serde_json::from_value(m.clone())) {
            Some(Ok(m)) if v.as_object().is_some_and(|o| o.len() == 1) => Some(m),
            _ => {
                self.shape_err(id, "needs {view_factors: {row: {col: F}}}");
                None
            }
        }
    }

    fn weights(&mut self, id: &str, user: &str) -> Option<BTreeMap<String, f64>> {
        let v = self.get(id, "partition", user)?;
        match v.get("weights").map(|m| serde_json::from_value(m.clone())) {
            Some(Ok(m)) if v.as_object().is_some_and(|o| o.len() == 1) => Some(m),
            _ => {
                self.shape_err(id, "needs {weights: {receiver: w}}");
                None
            }
        }
    }

    // ---------------------------------------------------------------- case level (AS-01, D-04, D-05, FT-11/12/15/16)

    fn case_level(&mut self) {
        let c = self.case;
        let g = self.gov;
        if c.schema != CASE_SCHEMA {
            self.me("CASE_SCHEMA", "schema", format!("{:?}, expected {CASE_SCHEMA:?}", c.schema));
        }
        if !vocab::CASE_CLASSES.contains(&c.case_class.as_str()) {
            self.me("CASE_CLASS_UNKNOWN", "case_class", c.case_class.clone());
        }
        if !vocab::TOPOLOGY_SCOPES.contains(&c.topology_scope.as_str()) {
            self.me("TOPOLOGY_SCOPE_UNKNOWN", "topology_scope", c.topology_scope.clone());
        } else if !self.np_scope && !self.synthetic {
            self.me(
                "TOPOLOGY_SCOPE_REFUSED",
                "topology_scope",
                "ANALYTIC_REDUCED_NETWORK is allowed only in SYNTHETIC_VERIFICATION cases",
            );
        }
        if c.configuration != g.flight_configuration() {
            self.me(
                "CONFIGURATION_REFUSED",
                "configuration",
                format!("{:?}: only {:?} is modelled (AS-01, FT-11)", c.configuration, g.flight_configuration()),
            );
        }
        let flight = c.case_class == "FLIGHT_CONDITIONAL";
        let bench = c.case_class == "BENCH_REPLICA";
        let mode_ok = if bench {
            vocab::BENCH_SUPPLY_MODES.contains(&c.supply_mode.as_str())
        } else {
            vocab::FLIGHT_SUPPLY_MODES.contains(&c.supply_mode.as_str())
        };
        if !mode_ok {
            self.push(
                RunStatus::OutOfDomain,
                "SUPPLY_MODE_OUTSIDE_DOMAIN",
                "supply_mode",
                format!("{:?} is outside the registered modes of a {} case (D-05)", c.supply_mode, c.case_class),
            );
        }
        match &c.design_state_id {
            None if flight => {
                self.me("CASE_FIELD_MISSING", "design_state_id", "FLIGHT_CONDITIONAL needs a design state")
            }
            Some(ds) if !g.design_state_ids().contains(ds) => self.push(
                RunStatus::OutOfDomain,
                "DESIGN_STATE_OUTSIDE_DESIGN_STATES_V2",
                ds,
                "not a state of atmosphere_msis21_orbit_v1_design_states_v2 (D-05, FT-15)",
            ),
            _ => {}
        }
        let mut seen = BTreeSet::new();
        for v in &c.installed_variants {
            if !seen.insert(v.clone()) {
                self.me("VARIANT_DUPLICATE", v, "listed twice");
            }
            if !vocab::BUS_VARIANTS.contains(&v.as_str()) {
                self.me("VARIANT_UNKNOWN", v, "not a bus_power_boundary_a9_v2 variant");
            } else if vocab::VARIANTS_OUTSIDE_V1.contains(&v.as_str()) {
                self.push(RunStatus::OutOfDomain, "VARIANT_OUTSIDE_V1", v, "uninstallable in v1 (A-10, D-05, FT-12)");
            }
        }
        if let Some(m) = &c.magnet_load_mode {
            if !vocab::MAGNET_LOAD_MODES.contains(&m.as_str()) {
                self.me("MAGNET_LOAD_MODE_UNKNOWN", "magnet_load_mode", m.clone());
            }
        }
        // Anode / collector candidates (FT-16, NE-06).
        for (field, cand, needed) in [
            ("anode_material_candidate_id", &c.anode_material_candidate_id, self.np_scope && !self.synthetic),
            (
                "collector_material_candidate_id",
                &c.collector_material_candidate_id,
                !self.synthetic
                    && c.nodes.iter().any(|n| n.id == "N_COLLECTOR" || n.refines.as_deref() == Some("N_COLLECTOR")),
            ),
        ] {
            match cand {
                Some(_) if self.synthetic => self.me(
                    "CANDIDATE_IN_SYNTHETIC_CASE",
                    field,
                    "material candidates are evidence; synthetic cases carry none",
                ),
                Some(id) if !g.anode_candidate_ids().contains(id) => {
                    self.me("CANDIDATE_UNKNOWN", field, format!("{id:?} is not a P4 candidate id"))
                }
                Some(id) if field == "anode_material_candidate_id" && id == vocab::REJECTED_FLIGHT_ANODE_CANDIDATE => {
                    if flight {
                        self.me(
                            "ANODE_CANDIDATE_REJECTED_AS_CURRENT_BASELINE",
                            field,
                            "CAND-01 (316L) is REJECTED_AS_CURRENT_BASELINE for the flight anode (FT-16)",
                        );
                    } else {
                        self.labels
                            .insert("ANODE_CAND-01_316L_REJECTED_AS_CURRENT_BASELINE_ENGINEERING_CASE_ONLY".into());
                    }
                }
                None if needed => self.me("CASE_FIELD_MISSING", field, "one registered P4 candidate per run"),
                _ => {}
            }
        }
        if bench {
            match &c.bench_vacuum {
                None => self.push(
                    RunStatus::OutOfDomain,
                    "BENCH_VACUUM_NOT_REGISTERED",
                    "bench_vacuum",
                    "facility pressure and the A-04 criterion must be registered (D-04)",
                ),
                Some(bv) => {
                    let p = self.scalar(&bv.facility_pressure_record_id, "pressure", "bench_vacuum");
                    let pmax = self.scalar(&bv.a04_max_pressure_record_id, "pressure", "bench_vacuum");
                    if let (Some(p), Some(pmax)) = (p, pmax) {
                        if p > pmax {
                            self.push(
                                RunStatus::OutOfDomain,
                                "BENCH_VACUUM_A04_NOT_MET",
                                &bv.facility_pressure_record_id,
                                format!("facility pressure {p} Pa > registered A-04 criterion {pmax} Pa (D-04)"),
                            );
                        }
                    }
                }
            }
            self.labels.insert("BENCH_REPLICA_CALIBRATION_VALIDATION_USE_ONLY".into());
        } else if c.bench_vacuum.is_some() {
            self.me("CASE_FIELD_NOT_APPLICABLE", "bench_vacuum", "only BENCH_REPLICA cases register a facility vacuum");
        }
        if flight && !g.spacecraft_thermal_icd_registered() {
            self.push(
                RunStatus::NotEvaluated,
                "SPACECRAFT_THERMAL_ICD_ABSENT",
                "B_SC",
                "no host-spacecraft thermal ICD exists: the spacecraft interface of a flight case is NOT_EVALUATED (NE-07)",
            );
        }
        match c.case_class.as_str() {
            "SYNTHETIC_VERIFICATION" => {
                self.labels.insert(vocab::SYNTHETIC.into());
                self.labels.insert("BIOT_NOT_APPLICABLE_SYNTHETIC".into());
                if !self.np_scope {
                    self.labels.insert("ANALYTIC_REDUCED_NETWORK".into());
                }
            }
            "PARAMETRIC" => {
                self.labels.insert("PARAMETRIC_NOT_A_PREDICTION".into());
            }
            _ => {}
        }
    }

    // ---------------------------------------------------------------- identifiers (EX-02, FT-10)

    fn scan_identifiers(&mut self) {
        let c = self.case;
        let mut ids: Vec<(String, &str)> =
            vec![(c.case_id.clone(), "case_id"), (c.configuration.clone(), "configuration")];
        for r in &c.records {
            if let Some(id) = &r.id {
                ids.push((id.clone(), "record"));
            }
        }
        for n in &c.nodes {
            ids.push((n.id.clone(), "node"));
            for p in &n.parts {
                ids.push((p.part_id.clone(), "part"));
            }
            for s in &n.surfaces {
                ids.push((s.surface_id.clone(), "surface"));
                ids.push((s.enclosure_id.clone(), "enclosure"));
            }
            for k in &n.receives_interface_keys {
                ids.push((k.clone(), "interface key"));
            }
        }
        for l in &c.links {
            ids.push((l.id.clone(), "link"));
            for e in [&l.a, &l.b] {
                if let Some(b) = &e.boundary {
                    ids.push((b.clone(), "boundary"));
                }
            }
        }
        for e in &c.enclosures {
            ids.push((e.id.clone(), "enclosure"));
            for s in &e.sinks {
                ids.push((s.surface_id.clone(), "sink surface"));
            }
            for h in &e.host_surfaces {
                ids.push((h.surface_id.clone(), "host surface"));
            }
        }
        for f in &c.boundary_fluxes {
            ids.push((f.id.clone(), "boundary flux"));
            ids.push((f.boundary.clone(), "boundary"));
        }
        for k in c.partitions.keys() {
            ids.push((k.clone(), "partition key"));
        }
        for k in c.coil_resistance_relations.keys() {
            ids.push((k.clone(), "coil node"));
        }
        for rec in [&c.interfaces.hall, &c.interfaces.icp].into_iter().flatten() {
            for k in rec.keys.keys() {
                ids.push((k.clone(), "interface key"));
            }
            for (k, m) in &rec.partitions {
                ids.push((k.clone(), "partition key"));
                for r in m.keys() {
                    ids.push((r.clone(), "partition receiver"));
                }
            }
            ids.push((rec.producer_id.clone(), "producer"));
        }
        for (id, kind) in ids {
            if let Some(why) = vocab::refused_identifier(&id) {
                self.me("FORBIDDEN_IDENTIFIER", &id, format!("{kind}: {why}"));
            }
        }
    }

    // ---------------------------------------------------------------- nodes

    fn nodes(&mut self) -> (NodeParts, Vec<Option<BiotC>>) {
        let c = self.case;
        let mut parts_out = Vec::new();
        let mut biot_out = Vec::new();
        let collector_absent =
            !c.nodes.iter().any(|n| n.id == "N_COLLECTOR" || n.refines.as_deref() == Some("N_COLLECTOR"));
        for n in &c.nodes {
            let idx = self.nodes.len();
            if self.node_index.insert(n.id.clone(), idx).is_some() {
                self.me("NODE_ID_DUPLICATE", &n.id, "node registered twice");
            }
            if !vocab::NODE_ROLES.contains(&n.role.as_str()) {
                self.me("NODE_ROLE_UNKNOWN", &n.id, n.role.clone());
            }
            if !vocab::GROUPS.contains(&n.group.as_str()) {
                self.me("NODE_GROUP_UNKNOWN", &n.id, n.group.clone());
            }
            if n.presence != "REQUIRED" && n.presence != "CONDITIONAL" {
                self.me("NODE_PRESENCE_UNKNOWN", &n.id, n.presence.clone());
            }
            if !n.case_classes_allowed.contains(&c.case_class) {
                self.me(
                    "NODE_CASE_CLASS_NOT_ALLOWED",
                    &n.id,
                    format!("case_classes_allowed {:?}", n.case_classes_allowed),
                );
            }
            let base = match n.role.as_str() {
                "REGISTERED" => {
                    if n.refines.is_some() {
                        self.me("NODE_FIELD_NOT_APPLICABLE", &n.id, "refines is set on a REGISTERED node");
                    }
                    let b = vocab::registered_node(&n.id);
                    if b.is_none() {
                        self.me("NODE_ID_NOT_REGISTERED", &n.id, "not one of the 17 registered node ids");
                    }
                    b
                }
                "SUBDIVISION" => {
                    let b = n.refines.as_deref().and_then(vocab::registered_node);
                    match b {
                        None => self.me("NODE_REFINES_UNKNOWN", &n.id, format!("refines {:?}", n.refines)),
                        Some(b) => {
                            if !n.id.starts_with(&format!("{}__", b.id)) {
                                self.me(
                                    "NODE_SUBDIVISION_ID",
                                    &n.id,
                                    format!("a sub-node id starts with \"{}__\"", b.id),
                                );
                            }
                        }
                    }
                    b
                }
                "MASSLESS_SERIES_JUNCTION" => {
                    if vocab::registered_node(&n.id).is_some() {
                        self.me("NODE_JUNCTION_ID", &n.id, "a junction cannot take a registered node id");
                    }
                    if n.thermal_mass != "MASSLESS_SERIES"
                        || !n.surfaces.is_empty()
                        || !n.receives_interface_keys.is_empty()
                    {
                        self.me(
                            "NODE_JUNCTION_SHAPE",
                            &n.id,
                            "a junction is MASSLESS_SERIES with no surface and no interface key (E-04)",
                        );
                    }
                    None
                }
                "ANALYTIC" => {
                    if self.np_scope {
                        self.me("NODE_ROLE_REFUSED", &n.id, "ANALYTIC nodes exist only in ANALYTIC_REDUCED_NETWORK");
                    }
                    if !n.receives_interface_keys.is_empty() {
                        self.me("NODE_RECEIVES_NOT_REGISTERED", &n.id, "ANALYTIC nodes receive no interface key");
                    }
                    None
                }
                _ => None,
            };
            if let Some(b) = base {
                if n.group != b.group {
                    self.me("NODE_GROUP_MISMATCH", &n.id, format!("group {}, registered {}", n.group, b.group));
                }
                let want = if b.required { "REQUIRED" } else { "CONDITIONAL" };
                if n.presence != want {
                    self.me("NODE_PRESENCE_MISMATCH", &n.id, format!("presence {}, registered {want}", n.presence));
                }
                for k in &n.receives_interface_keys {
                    let hk08 = k == "Q_hall_return_to_icp_W" && b.group == "ICP_NEUTRALIZER" && collector_absent;
                    if !b.receives.contains(&k.as_str()) && !hk08 {
                        self.me("NODE_RECEIVES_NOT_REGISTERED", &n.id, format!("{k} is not registered for {}", b.id));
                    }
                }
            }
            match n.thermal_mass.as_str() {
                "LUMPED_C_OF_T" if n.parts.is_empty() => {
                    self.me("NODE_PARTS_MISSING", &n.id, "LUMPED_C_OF_T needs parts")
                }
                "MASSLESS_SERIES" if !n.parts.is_empty() => {
                    self.me("NODE_PARTS_NOT_APPLICABLE", &n.id, "a massless series node has no part")
                }
                "MASSLESS_SERIES" if n.role == "REGISTERED" || n.role == "SUBDIVISION" => {
                    self.me("NODE_MASSLESS_REFUSED", &n.id, "C = 0 only for a registered massless series node")
                }
                "LUMPED_C_OF_T" | "MASSLESS_SERIES" => {}
                other => self.me("NODE_THERMAL_MASS_UNKNOWN", &n.id, other.to_string()),
            }
            let mut parts = Vec::new();
            for p in &n.parts {
                let user = format!("{}/{}", n.id, p.part_id);
                let cp = self.prop(&p.material_record_id, "specific_heat", &user);
                let m = self.scalar(&p.mass_kg_record_id, "mass", &user);
                if let (Some(cp), Some(m)) = (cp, m) {
                    parts.push((m, cp));
                }
            }
            parts_out.push(parts);
            let biot = match (&n.biot_geometry, self.synthetic, n.role.as_str()) {
                (_, true, _) | (_, _, "MASSLESS_SERIES_JUNCTION") => None,
                (None, false, _) => {
                    self.me("BIOT_GEOMETRY_MISSING", &n.id, "non-synthetic lumped nodes register biot_geometry (D-02)");
                    None
                }
                (Some(bg), false, _) => {
                    let v = self.scalar(&bg.volume_record_id, "volume", &n.id);
                    let a = self.scalar(&bg.conduction_area_record_id, "area", &n.id);
                    let k = self.prop(&bg.k_record_id, "thermal_conductivity", &n.id);
                    match (v, a, k) {
                        (Some(volume), Some(area), Some(k)) => Some(BiotC { volume, area, k }),
                        _ => None,
                    }
                }
            };
            biot_out.push(biot);
            self.nodes.push(NodeInfo {
                base,
                role: n.role.clone(),
                receives: n.receives_interface_keys.iter().cloned().collect(),
            });
        }
        if self.np_scope {
            for b in vocab::NODES.iter() {
                let present = self.nodes.iter().any(|x| x.base.is_some_and(|y| y.id == b.id));
                if b.required && !present {
                    self.me("REQUIRED_NODE_MISSING", b.id, "a REQUIRED node must be present in every case");
                }
            }
            let has_match = self.nodes.iter().any(|x| x.base.is_some_and(|y| y.id == "N_MATCH"));
            match c.match_colocated {
                None => self.me("CASE_FIELD_MISSING", "match_colocated", "registered switch (RI-CASE)"),
                Some(true) if !has_match => {
                    self.me("N_MATCH_PRESENCE", "N_MATCH", "match_colocated = true needs N_MATCH")
                }
                Some(false) if has_match => {
                    self.me("N_MATCH_PRESENCE", "N_MATCH", "N_MATCH is present iff match_colocated = true")
                }
                _ => {}
            }
            for (i, x) in self.nodes.iter().enumerate() {
                if x.role == "REGISTERED" {
                    let id = &c.nodes[i].id;
                    if self.nodes.iter().any(|y| y.role == "SUBDIVISION" && y.base.is_some_and(|b| b.id == id)) {
                        self.reasons.push(Reason {
                            status: RunStatus::ModelError,
                            code: "NODE_SUBDIVISION_CONFLICT".into(),
                            subject: id.clone(),
                            detail: "a subdivided node is not also registered whole".into(),
                        });
                    }
                }
            }
        }
        (parts_out, biot_out)
    }

    fn node(&mut self, id: &str, user: &str) -> Option<usize> {
        let i = self.node_index.get(id).copied();
        if i.is_none() {
            self.me("NODE_NOT_FOUND", id, format!("referenced by {user}"));
        }
        i
    }

    // ---------------------------------------------------------------- links (E-03, E-04, E-08)

    fn endpoint(&mut self, e: &Endpoint, link: &str) -> Option<End> {
        match (&e.node, &e.boundary) {
            (Some(n), None) => {
                if e.temperature_record_id.is_some() {
                    self.me("LINK_ENDPOINT_SHAPE", link, "a node endpoint carries no temperature record");
                }
                self.node(n, link).map(End::Node)
            }
            (None, Some(b)) => {
                if !vocab::LINK_BOUNDARIES.contains(&b.as_str()) {
                    self.me("LINK_BOUNDARY_UNKNOWN", link, format!("{b:?}: links end on B_SC, B_PPU_RF or B_FEED"));
                    return None;
                }
                let Some(tid) = &e.temperature_record_id else {
                    self.me("LINK_ENDPOINT_SHAPE", link, "a boundary endpoint needs temperature_record_id");
                    return None;
                };
                let t = self.tvalue(tid, "temperature", link)?;
                Some(End::Fixed { boundary: b.clone(), t, record_id: tid.clone() })
            }
            _ => {
                self.me("LINK_ENDPOINT_SHAPE", link, "exactly one of node / boundary");
                None
            }
        }
    }

    fn links(&mut self) -> Vec<LinkC> {
        let c = self.case;
        let mut out = Vec::new();
        let mut seen = BTreeSet::new();
        for l in &c.links {
            if !seen.insert(l.id.clone()) {
                self.me("LINK_ID_DUPLICATE", &l.id, "link registered twice");
            }
            let a = self.endpoint(&l.a, &l.id);
            let b = self.endpoint(&l.b, &l.id);
            let fields = [
                ("k_record_id", l.k_record_id.is_some()),
                ("shape", l.shape.is_some()),
                ("h_c_record_id", l.h_c_record_id.is_some()),
                ("contact_area_record_id", l.contact_area_record_id.is_some()),
                ("G_record_id", l.g_record_id.is_some()),
            ];
            let wanted: &[&str] = match l.link_type.as_str() {
                "CONDUCTION" => &["k_record_id", "shape"],
                "CONTACT" => &["h_c_record_id", "contact_area_record_id"],
                "LUMPED_G" => &["G_record_id"],
                other => {
                    self.me("LINK_TYPE_UNKNOWN", &l.id, other.to_string());
                    continue;
                }
            };
            let mut shape_ok = true;
            for (f, present) in fields {
                if wanted.contains(&f) != present {
                    shape_ok = false;
                    self.me(
                        "LINK_FIELDS",
                        &l.id,
                        format!(
                            "{} link: field {f} {}",
                            l.link_type,
                            if present { "not applicable" } else { "missing" }
                        ),
                    );
                }
            }
            if !shape_ok {
                continue;
            }
            let kind = match l.link_type.as_str() {
                "CONDUCTION" => {
                    let k = self.prop(l.k_record_id.as_deref().unwrap_or(""), "thermal_conductivity", &l.id);
                    let s = self.shape_factor(l.shape.as_ref().expect("checked"), &l.id);
                    match (k, s) {
                        (Some(k), Some(s)) => Some(LinkKind::Conduction { s, k }),
                        _ => None,
                    }
                }
                "CONTACT" => {
                    let id = l.h_c_record_id.clone().unwrap_or_default();
                    let h = self.ranged(&id, "contact_conductance_coefficient", &l.id);
                    let ac = self.scalar(l.contact_area_record_id.as_deref().unwrap_or(""), "area", &l.id);
                    match (h, ac) {
                        (Some((h, t_min, t_max)), Some(ac)) => {
                            Some(LinkKind::Linear { g: h * ac, record_id: id, t_min, t_max })
                        }
                        _ => None,
                    }
                }
                _ => {
                    let id = l.g_record_id.clone().unwrap_or_default();
                    self.ranged(&id, "conductance", &l.id).map(|(g, t_min, t_max)| LinkKind::Linear {
                        g,
                        record_id: id,
                        t_min,
                        t_max,
                    })
                }
            };
            let (Some(a), Some(b), Some(kind)) = (a, b, kind) else { continue };
            match (&a, &b) {
                (End::Fixed { .. }, End::Fixed { .. }) => {
                    self.me("LINK_ENDPOINT_SHAPE", &l.id, "a link needs at least one solved node");
                    continue;
                }
                (End::Node(x), End::Node(y)) if x == y => {
                    self.me("LINK_ENDPOINT_SHAPE", &l.id, "a link joins two different nodes");
                    continue;
                }
                _ => {}
            }
            out.push(LinkC { id: l.id.clone(), a, b, kind });
        }
        out
    }

    fn shape_factor(&mut self, s: &ShapeSpec, link: &str) -> Option<f64> {
        let fields = [
            ("area_record_id", s.area_record_id.is_some()),
            ("length_record_id", s.length_record_id.is_some()),
            ("r_outer_record_id", s.r_outer_record_id.is_some()),
            ("r_inner_record_id", s.r_inner_record_id.is_some()),
            ("S_record_id", s.s_record_id.is_some()),
        ];
        let wanted: &[&str] = match s.kind.as_str() {
            "SLAB" => &["area_record_id", "length_record_id"],
            "CYLINDRICAL_SHELL" => &["length_record_id", "r_outer_record_id", "r_inner_record_id"],
            "SHAPE_FACTOR" => &["S_record_id"],
            other => {
                self.me("SHAPE_KIND_UNKNOWN", link, other.to_string());
                return None;
            }
        };
        for (f, present) in fields {
            if wanted.contains(&f) != present {
                self.me("SHAPE_FIELDS", link, format!("{} shape: field {f}", s.kind));
                return None;
            }
        }
        let r = |o: &Option<String>| o.clone().unwrap_or_default();
        match s.kind.as_str() {
            "SLAB" => {
                let a = self.scalar(&r(&s.area_record_id), "area", link);
                let l = self.scalar(&r(&s.length_record_id), "length", link);
                Some(a? / l?)
            }
            "CYLINDRICAL_SHELL" => {
                let l = self.scalar(&r(&s.length_record_id), "length", link);
                let ro = self.scalar(&r(&s.r_outer_record_id), "length", link);
                let ri = self.scalar(&r(&s.r_inner_record_id), "length", link);
                let (l, ro, ri) = (l?, ro?, ri?);
                if ro <= ri {
                    self.me("SHAPE_GEOMETRY", link, "cylindrical shell needs r_outer > r_inner > 0");
                    return None;
                }
                Some(2.0 * std::f64::consts::PI * l / (ro / ri).ln())
            }
            _ => self.scalar(&r(&s.s_record_id), "shape_factor", link),
        }
    }

    // ---------------------------------------------------------------- radiation (E-05, D-07)

    fn enclosures(&mut self) -> Radiation {
        let c = self.case;
        let mut rad = Radiation { node_surfaces: vec![Vec::new(); c.nodes.len()], ..Default::default() };
        let mut by_encl: BTreeMap<String, Vec<String>> = BTreeMap::new();
        let enclosure_ids: BTreeSet<String> = c.enclosures.iter().map(|e| e.id.clone()).collect();
        let mut seen = BTreeSet::new();
        // Structure first: a surface whose records are not usable stays a member of its enclosure (no cascade).
        for (ni, n) in c.nodes.iter().enumerate() {
            for s in &n.surfaces {
                if !seen.insert(s.surface_id.clone()) {
                    self.me("SURFACE_ID_DUPLICATE", &s.surface_id, "surface registered twice");
                    continue;
                }
                if !enclosure_ids.contains(&s.enclosure_id) {
                    self.me("ENCLOSURE_NOT_FOUND", &s.surface_id, format!("enclosure {:?}", s.enclosure_id));
                    continue;
                }
                rad.structure.insert(
                    s.surface_id.clone(),
                    SurfStruct { node: ni, external: s.external, alpha_declared: s.alpha_solar_record_id.is_some() },
                );
                by_encl.entry(s.enclosure_id.clone()).or_default().push(s.surface_id.clone());
                let a = self.scalar(&s.area_record_id, "area", &s.surface_id);
                let e = self.prop(&s.eps_ir_record_id, "emittance_IR", &s.surface_id);
                let al = s.alpha_solar_record_id.as_ref().map(|id| self.prop(id, "absorptance_solar", &s.surface_id));
                match (a, e, al) {
                    (Some(a), Some(e), None) => {
                        rad.node_surfaces[ni].push((a, e.clone()));
                        rad.resolved.insert(s.surface_id.clone(), (ni, a, e, None, s.external));
                    }
                    (Some(a), Some(e), Some(Some(al))) => {
                        rad.node_surfaces[ni].push((a, e.clone()));
                        rad.resolved.insert(s.surface_id.clone(), (ni, a, e, Some(al), s.external));
                    }
                    _ => {}
                }
            }
        }
        let flight = c.case_class == "FLIGHT_CONDITIONAL";
        let bench = c.case_class == "BENCH_REPLICA";
        let mut eseen = BTreeSet::new();
        for e in &c.enclosures {
            if !eseen.insert(e.id.clone()) {
                self.me("ENCLOSURE_ID_DUPLICATE", &e.id, "enclosure registered twice");
                continue;
            }
            let mut names: Vec<String> = Vec::new();
            let mut kinds: Vec<StructKind> = Vec::new();
            let mut members: Vec<Option<MemberC>> = Vec::new();
            for sid in by_encl.get(&e.id).cloned().unwrap_or_default() {
                let node = rad.structure[&sid].node;
                names.push(sid.clone());
                kinds.push(StructKind::Node(node));
                members.push(rad.resolved.get(&sid).map(|(ni, a, p, _, _)| MemberC {
                    surface_id: sid.clone(),
                    area: *a,
                    kind: MemberKind::Node { node: *ni, eps: p.clone() },
                }));
            }
            for h in &e.host_surfaces {
                if !seen.insert(h.surface_id.clone()) {
                    self.me("SURFACE_ID_DUPLICATE", &h.surface_id, "surface registered twice");
                    continue;
                }
                let a = self.scalar(&h.area_record_id, "area", &h.surface_id);
                let p = self.prop(&h.eps_ir_record_id, "emittance_IR", &h.surface_id);
                let t = self.tvalue(&h.temperature_record_id, "temperature", &h.surface_id);
                names.push(h.surface_id.clone());
                kinds.push(StructKind::Fixed);
                members.push(match (a, p, t) {
                    (Some(a), Some(p), Some(t)) => Some(MemberC {
                        surface_id: h.surface_id.clone(),
                        area: a,
                        kind: MemberKind::Host { eps: p, t },
                    }),
                    _ => None,
                });
            }
            let mut has_space = false;
            for s in &e.sinks {
                if !seen.insert(s.surface_id.clone()) {
                    self.me("SURFACE_ID_DUPLICATE", &s.surface_id, "surface registered twice");
                    continue;
                }
                if !vocab::SINKS.contains(&s.kind.as_str()) {
                    self.me("SINK_KIND_UNKNOWN", &s.surface_id, s.kind.clone());
                    continue;
                }
                has_space |= s.kind == "SPACE";
                if bench && s.kind == "SPACE" {
                    self.me("SINK_NOT_ALLOWED", &s.surface_id, "BENCH_REPLICA replaces SPACE by B_FACILITY");
                }
                if s.kind == "B_FACILITY" && !(bench || self.synthetic) {
                    self.me("SINK_NOT_ALLOWED", &s.surface_id, "B_FACILITY exists only in BENCH_REPLICA cases");
                }
                if bench && s.kind == "B_FACILITY" {
                    let ev = self.records.get(&s.temperature_record_id).and_then(|r| r.evidence_class.as_deref());
                    if ev != Some("measured") {
                        self.push(
                            RunStatus::IncompleteEvidence,
                            "FACILITY_SINK_NOT_MEASURED",
                            &s.temperature_record_id,
                            "the facility sink temperature is measured per run (owner row 131)",
                        );
                    }
                }
                names.push(s.surface_id.clone());
                kinds.push(StructKind::Sink);
                members.push(self.tvalue(&s.temperature_record_id, "temperature", &s.surface_id).map(|t| MemberC {
                    surface_id: s.surface_id.clone(),
                    area: f64::NAN,
                    kind: MemberKind::Sink { t, kind: s.kind.clone() },
                }));
            }
            if names.len() < 2 {
                self.me("ENCLOSURE_MEMBERS", &e.id, "an enclosure needs at least two members");
                continue;
            }
            let external_here = names.iter().any(|n| rad.structure.get(n).is_some_and(|x| x.external));
            if flight && external_here && !has_space {
                self.me("FLIGHT_EXTERNAL_ENCLOSURE_WITHOUT_SPACE", &e.id, "every external enclosure closes on SPACE");
            }
            let f = self
                .matrix(&e.view_factor_record_id, &e.id)
                .and_then(|mat| self.view_factors(&e.id, &names, &kinds, &mat));
            if let Some(f) = &f {
                let unknown: Vec<usize> = (0..names.len()).filter(|&k| kinds[k] != StructKind::Sink).collect();
                for &k in &unknown {
                    let sum: f64 = f[k].iter().sum();
                    if (sum - 1.0).abs() > VF_SUM_TOL {
                        self.me(
                            "VIEW_FACTOR_SUMMATION",
                            &e.id,
                            format!("row {:?}: sum F = {sum:.17e}, |sum - 1| > {VF_SUM_TOL:e} (D-07)", names[k]),
                        );
                    }
                    if let StructKind::Node(_) = kinds[k] {
                        let external = rad.structure.get(&names[k]).is_some_and(|x| x.external);
                        let sees_sink = (0..names.len()).any(|l| kinds[l] == StructKind::Sink && f[k][l] > 0.0);
                        if sees_sink && !external {
                            self.me(
                                "SURFACE_SEES_SINK_NOT_EXTERNAL",
                                &names[k],
                                "a surface that views a sink is external",
                            );
                        }
                    }
                }
                // Reciprocity needs the areas of both members.
                for &k in &unknown {
                    for &l in &unknown {
                        if l <= k {
                            continue;
                        }
                        let (Some(mk), Some(ml)) = (&members[k], &members[l]) else { continue };
                        let x = mk.area * f[k][l];
                        let y = ml.area * f[l][k];
                        if (x - y).abs() > VF_RECIPROCITY_REL_TOL * x.max(y) {
                            self.me(
                                "VIEW_FACTOR_RECIPROCITY",
                                &e.id,
                                format!("A F [{}, {}] = {x:.17e} vs {y:.17e} (D-07)", names[k], names[l]),
                            );
                        }
                    }
                }
            }
            if let (Some(f), true) = (&f, members.iter().all(Option::is_some)) {
                let members: Vec<MemberC> = members.into_iter().flatten().collect();
                let unknown: Vec<usize> = (0..members.len()).filter(|&k| kinds[k] != StructKind::Sink).collect();
                rad.compiled.push(EnclC { id: e.id.clone(), members, unknown, f: f.clone() });
            }
            rad.enclosures.push(EnclStruct { kinds, f });
        }
        rad
    }

    /// Rows of every non-sink member over every member (complete, values in [0, 1]); `None` with a reason otherwise.
    fn view_factors(
        &mut self,
        encl: &str,
        names: &[String],
        kinds: &[StructKind],
        mat: &BTreeMap<String, BTreeMap<String, f64>>,
    ) -> Option<Vec<Vec<f64>>> {
        let name_set: BTreeSet<&String> = names.iter().collect();
        let mut f = vec![vec![0.0; names.len()]; names.len()];
        let mut fine = true;
        for row in mat.keys() {
            match names.iter().position(|n| n == row) {
                None => {
                    self.me("VIEW_FACTOR_ROW_UNKNOWN", encl, format!("row {row:?} is not a member"));
                    fine = false;
                }
                Some(k) if kinds[k] == StructKind::Sink => {
                    self.me("VIEW_FACTOR_ROW_UNKNOWN", encl, format!("row {row:?}: sinks carry no row"));
                    fine = false;
                }
                _ => {}
            }
        }
        for (k, name) in names.iter().enumerate() {
            if kinds[k] == StructKind::Sink {
                continue;
            }
            let Some(row) = mat.get(name) else {
                self.me("VIEW_FACTOR_ROW_MISSING", encl, format!("row {name:?}"));
                fine = false;
                continue;
            };
            if row.len() != names.len() || row.keys().any(|c| !name_set.contains(c)) {
                self.me("VIEW_FACTOR_ROW_INCOMPLETE", encl, format!("row {name:?} must list every member"));
                fine = false;
                continue;
            }
            for (l, nm) in names.iter().enumerate() {
                let v = row[nm];
                if !(v.is_finite() && (0.0..=1.0).contains(&v)) {
                    self.me("VIEW_FACTOR_VALUE", encl, format!("F[{name}][{nm}] = {v}"));
                    fine = false;
                }
                f[k][l] = v;
            }
        }
        fine.then_some(f)
    }

    // ---------------------------------------------------------------- environment, thermal control, SCI-B

    fn environment(&mut self, rad: &Radiation) -> Vec<EnvC> {
        let c = self.case;
        let mut out = Vec::new();
        let mut seen = BTreeSet::new();
        if c.case_class == "BENCH_REPLICA" && !c.environment.is_empty() {
            self.me("ENV_NOT_ALLOWED", "environment", "BENCH_REPLICA replaces ENV by B_FACILITY");
        }
        for e in &c.environment {
            let sid = e.surface_id.as_str();
            if !seen.insert(sid.to_string()) {
                self.me("ENV_SURFACE_DUPLICATE", sid, "one environment entry per surface");
                continue;
            }
            let Some(st) = rad.structure.get(sid) else {
                self.me("ENV_SURFACE_NOT_FOUND", sid, "environment loads act on a registered node surface");
                continue;
            };
            if !st.external {
                self.me("ENV_SURFACE_NOT_EXTERNAL", sid, "environment loads act on external surfaces only (E-06)");
                continue;
            }
            if !st.alpha_declared {
                self.me("RECORD_FIELD_MISSING", sid, "alpha_solar_record_id (E-06)");
                continue;
            }
            let resolved = rad.resolved.get(sid).cloned();
            let s = self.tvalue(&e.solar_flux_record_id, "solar_flux", sid);
            let f_sun = self.tvalue(&e.f_sun_record_id, "view_factor_env", sid);
            let nu = self.tvalue(&e.illumination_record_id, "illumination", sid);
            let a = self.tvalue(&e.albedo_record_id, "albedo", sid);
            let f_alb = self.tvalue(&e.f_alb_record_id, "view_factor_env", sid);
            let q_olr = self.tvalue(&e.olr_flux_record_id, "olr_flux", sid);
            let f_earth = self.tvalue(&e.f_earth_record_id, "view_factor_env", sid);
            let rho = self.tvalue(&e.rho_record_id, "density", sid);
            let v = self.tvalue(&e.v_rel_record_id, "velocity", sid);
            let alpha_e = self.tvalue(&e.alpha_e_record_id, "energy_accommodation", sid);
            let a_ram = self.scalar(&e.a_ram_record_id, "projected_area", sid);
            if let (
                Some(s),
                Some(f_sun),
                Some(nu),
                Some(a),
                Some(f_alb),
                Some(q_olr),
                Some(f_earth),
                Some(rho),
                Some(v),
                Some(alpha_e),
                Some(a_ram),
            ) = (s, f_sun, nu, a, f_alb, q_olr, f_earth, rho, v, alpha_e, a_ram)
            {
                let Some((node, area, eps, Some(alpha), _)) = resolved else { continue };
                out.push(EnvC {
                    surface_id: sid.to_string(),
                    node,
                    area,
                    alpha,
                    eps,
                    s,
                    f_sun,
                    nu,
                    a,
                    f_alb,
                    q_olr,
                    f_earth,
                    rho,
                    v,
                    alpha_e,
                    a_ram,
                });
            }
        }
        out
    }

    fn thermal_control_and_fluxes(&mut self, sources: &mut Vec<SourceC>) {
        let c = self.case;
        for tc in &c.thermal_control {
            let user = format!("Q_thermal_control_W@{}", tc.node);
            let node = self.node(&tc.node, &user);
            let tv = self.tvalue(&tc.record_id, "power", &user);
            if let Some(tv) = &tv {
                if tv.values().iter().any(|v| *v < 0.0) {
                    self.me("VALUE_NOT_PHYSICAL", &tc.record_id, "thermal-control dissipation is >= 0");
                    continue;
                }
            }
            if let (Some(node), Some(tv)) = (node, tv) {
                sources.push(SourceC {
                    node,
                    label: "Q_thermal_control_W".into(),
                    weight: 1.0,
                    tv,
                    kind: SourceKind::ThermalControl,
                });
            }
        }
        let mut seen = BTreeSet::new();
        for f in &c.boundary_fluxes {
            if !seen.insert(f.id.clone()) {
                self.me("BOUNDARY_FLUX_ID_DUPLICATE", &f.id, "registered twice");
            }
            if f.boundary != "B_SC" {
                self.me("BOUNDARY_FLUX_BOUNDARY", &f.id, "prescribed flux is the SCI-B form of B_SC");
                continue;
            }
            let node = self.node(&f.node, &f.id);
            let tv = self.tvalue(&f.q_record_id, "power", &f.id);
            if let (Some(node), Some(tv)) = (node, tv) {
                sources.push(SourceC {
                    node,
                    label: format!("SCI-B:{}", f.id),
                    weight: 1.0,
                    tv,
                    kind: SourceKind::BoundaryFlux,
                });
            }
        }
    }

    // ---------------------------------------------------------------- interfaces (IF-HALL-THERMAL-v1, IF-ICP-THERMAL-v1)

    fn interface(&mut self, rec: &'a InterfaceRecord, hall: bool) -> Option<Iface> {
        let c = self.case;
        let id = if hall { vocab::HALL_INTERFACE_ID } else { vocab::ICP_INTERFACE_ID };
        let mut ok = true;
        if rec.interface_id != id || rec.interface_version != vocab::INTERFACE_VERSION {
            self.me(
                "INTERFACE_VERSION",
                id,
                format!("{} {}: a mismatch needs a versioned interface", rec.interface_id, rec.interface_version),
            );
            ok = false;
        }
        for (f, v) in [
            ("producer_id", &rec.producer_id),
            ("producer_version", &rec.producer_version),
            ("operating_point_id", &rec.operating_point_id),
        ] {
            if v.is_empty() {
                self.me("INTERFACE_FIELD_MISSING", id, f);
                ok = false;
            }
        }
        if !is_hex64(&rec.producer_prereg_sha256) {
            self.me("INTERFACE_FIELD_MISSING", id, "producer_prereg_sha256 (64 lower-case hex)");
            ok = false;
        }
        if rec.case_id != c.case_id
            || rec.case_class != c.case_class
            || rec.supply_mode != c.supply_mode
            || rec.design_state_id != c.design_state_id
        {
            self.me(
                "INTERFACE_CASE_MISMATCH",
                id,
                "case_id / case_class / supply_mode / design_state_id differ from the case",
            );
            ok = false;
        }
        if !hall && rec.producer_id != vocab::ICP_PRODUCER_ID && c.case_class == "FLIGHT_CONDITIONAL" {
            self.me(
                "INTERFACE_PRODUCER",
                id,
                format!("producer {:?}; IF-ICP-THERMAL-v1 is produced by NP-ICP-NEUTRALIZER", rec.producer_id),
            );
            ok = false;
        }
        if hall && rec.rf_powered_only.is_some() {
            self.me("INTERFACE_FIELD_NOT_APPLICABLE", id, "rf_powered_only is an IF-ICP-THERMAL-v1 declaration");
            ok = false;
        }
        let breakpoints = match (rec.time_basis.kind.as_str(), &rec.time_basis.breakpoints_s) {
            ("STEADY", None) => None,
            ("ZOH_SERIES", Some(t)) => {
                if (TimeValue::Zoh { t: t.clone(), v: vec![0.0; t.len()] }).check().is_err() {
                    self.me("INTERFACE_TIME_BASIS", id, "breakpoints_s must be finite and strictly increasing");
                    return None;
                }
                Some(t.clone())
            }
            _ => {
                self.me("INTERFACE_TIME_BASIS", id, "STEADY (no breakpoints) or ZOH_SERIES (breakpoints_s)");
                return None;
            }
        };
        let n = breakpoints.as_ref().map_or(1, Vec::len);
        let mut keys = BTreeMap::new();
        for (k, vr) in &rec.keys {
            let units = if hall { vocab::hall_key_units(k) } else { vocab::icp_key(k).map(|x| x.units) };
            let Some(units) = units else {
                self.me(
                    "INTERFACE_KEY_NOT_REGISTERED",
                    k,
                    format!("not a key of {id}; a new key needs a versioned interface (CC-02)"),
                );
                ok = false;
                continue;
            };
            let missing: Vec<&str> = [
                ("units", vr.units.is_some()),
                ("status", vr.status.is_some()),
                ("evidence_class", vr.evidence_class.is_some()),
                ("source", vr.source.is_some()),
                ("uncertainty", vr.uncertainty.is_some()),
                ("applicability_domain", vr.applicability_domain.is_some()),
                ("validation_status", vr.validation_status.is_some()),
            ]
            .into_iter()
            .filter(|(_, p)| !p)
            .map(|(f, _)| f)
            .collect();
            if !missing.is_empty() {
                self.me("VALUE_RECORD_FIELD_MISSING", k, missing.join(", "));
                ok = false;
                continue;
            }
            if vr.units.as_deref() != Some(units) {
                self.me("VALUE_RECORD_UNITS_MISMATCH", k, format!("{:?}, registered {units:?}", vr.units));
                ok = false;
                continue;
            }
            let status = vr.status.clone().unwrap_or_default();
            if !vocab::VALUE_STATUSES.contains(&status.as_str()) {
                self.me("VALUE_RECORD_STATUS_UNKNOWN", k, status);
                ok = false;
                continue;
            }
            let ec = vr.evidence_class.clone().unwrap_or_default();
            self.check_evidence_class(&ec, k);
            if vr.hall_map.is_some() && !hall {
                self.me("VALUE_RECORD_FIELD_NOT_APPLICABLE", k, "hall_map provenance belongs to IF-HALL-THERMAL-v1");
                ok = false;
            }
            let values = if status == "EVALUATED" {
                let parsed: Option<Vec<f64>> = match (&breakpoints, &vr.value) {
                    (None, Some(Value::Number(x))) => x.as_f64().map(|v| vec![v]),
                    (Some(t), Some(Value::Array(a))) if a.len() == t.len() => a.iter().map(Value::as_f64).collect(),
                    _ => None,
                };
                match parsed {
                    Some(v) if v.iter().all(|x| x.is_finite()) => {
                        if v.iter().any(|x| *x < 0.0) {
                            let check = if hall { "IFH-2" } else { "IFI-2" };
                            self.me(&format!("{check}_VIOLATED"), k, "every Q / P / I / R value is >= 0");
                            ok = false;
                        }
                        Some(v)
                    }
                    _ => {
                        self.me(
                            "VALUE_RECORD_VALUE_SHAPE",
                            k,
                            "EVALUATED needs a finite number (STEADY) or one per breakpoint (ZOH_SERIES)",
                        );
                        ok = false;
                        None
                    }
                }
            } else {
                if vr.value.as_ref().is_some_and(|v| !v.is_null()) {
                    self.me(
                        "VALUE_RECORD_VALUE_SHAPE",
                        k,
                        format!("status {status} carries no value (no zero-fill, rule 3)"),
                    );
                    ok = false;
                }
                let (st, code) = match status.as_str() {
                    "NOT_EVALUATED" => (RunStatus::NotEvaluated, "INTERFACE_KEY_NOT_EVALUATED"),
                    "INCOMPLETE_EVIDENCE" => (RunStatus::IncompleteEvidence, "INTERFACE_KEY_INCOMPLETE_EVIDENCE"),
                    "OUT_OF_DOMAIN" => (RunStatus::OutOfDomain, "INTERFACE_KEY_OUT_OF_DOMAIN"),
                    _ => (RunStatus::ModelError, "INTERFACE_KEY_MODEL_ERROR"),
                };
                self.push(st, code, k, format!("{id} key status {status} propagates to the run (D-06, FT-18)"));
                None
            };
            // Admission gate for map-derived Hall values (IF-HALL-THERMAL-v1.admission_gate, FT-01, FT-02).
            let mut map_derived = false;
            if let Some(hm) = &vr.hall_map {
                map_derived = true;
                self.members.insert(hm.ensemble_member_id.clone());
                if hm.hallthruster_commit != self.gov.hallthruster_commit() {
                    self.me(
                        "HALLTHRUSTER_COMMIT_NOT_PINNED",
                        k,
                        format!("{} != pinned {}", hm.hallthruster_commit, self.gov.hallthruster_commit()),
                    );
                    ok = false;
                }
                if !is_hex64(&hm.map_meta_sha256) {
                    self.me("VALUE_RECORD_FIELD_MISSING", k, "hall_map.map_meta_sha256");
                    ok = false;
                }
                let member = hm.ensemble_member_id.clone();
                if self.gov.screening_candidates().contains(&member) {
                    self.push(
                        RunStatus::NotEvaluated,
                        "SCREENING_CANDIDATE_NOT_ADMITTED",
                        k,
                        format!("{member} is a screening candidate, not an admitted member"),
                    );
                }
                if !self.gov.admitted_hall_members().contains(&member) {
                    if self.gov.admitted_hall_members().is_empty() {
                        self.push(
                            RunStatus::NotEvaluated,
                            "CREDIBLE_HALL_TRANSPORT_SET_EMPTY",
                            k,
                            "no admitted transport-ensemble member (GR-19)",
                        );
                    } else {
                        self.push(RunStatus::NotEvaluated, "HALL_MEMBER_NOT_ADMITTED", k, member.clone());
                    }
                } else if !(hm.trustworthy && hm.wall_life_trustworthy) {
                    self.push(
                        RunStatus::NotEvaluated,
                        "HALL_MAP_POINT_NOT_TRUSTWORTHY",
                        k,
                        "trustworthy and wall_life_trustworthy are required",
                    );
                }
            }
            keys.insert(k.clone(), KeyVal { status, values, evidence: ec, map_derived });
        }
        if !ok {
            return None;
        }
        Some(Iface { keys, breakpoints, n })
    }

    #[allow(clippy::needless_range_loop)]
    fn interfaces(&mut self, sources: &mut Vec<SourceC>, coils: &mut Vec<CoilC>) -> InterfaceOutcome {
        let c = self.case;
        let mut exported = BTreeMap::new();
        let mut booked = BTreeMap::new();
        let mut breakpoints = Vec::new();
        for (name, rec) in
            [(vocab::HALL_INTERFACE_ID, &c.interfaces.hall), (vocab::ICP_INTERFACE_ID, &c.interfaces.icp)]
        {
            if rec.is_none() && self.np_scope {
                self.me(
                    "INTERFACE_RECORD_MISSING",
                    name,
                    "both interface records are required (supply modes register zeros, never absence)",
                );
            }
        }
        let hall = c.interfaces.hall.as_ref().and_then(|r| self.interface(r, true));
        let icp = c.interfaces.icp.as_ref().and_then(|r| self.interface(r, false));
        let flight = c.case_class == "FLIGHT_CONDITIONAL";
        let bench = c.case_class == "BENCH_REPLICA";
        let non_firing = c.supply_mode == "NON_FIRING";
        let discharge_keys: Vec<&str> = vocab::HALL_DISCHARGE_KEYS.iter().map(|k| k.key).collect();

        // Required keys (IFH-1, IFI-1) and the coil keys of the declared magnet mode.
        let mode = c.magnet_load_mode.clone();
        if let Some(h) = &hall {
            if self.np_scope {
                for k in &discharge_keys {
                    if !h.keys.contains_key(*k) {
                        self.me("INTERFACE_KEY_MISSING", k, "IFH-1: every required key is present");
                    }
                }
                if mode.is_none() {
                    self.me("CASE_FIELD_MISSING", "magnet_load_mode", "FIXED_POWER | CONSTANT_CURRENT_R_OF_T per case");
                }
            }
            for (_, node, q, i, r, t) in vocab::COILS {
                let present = self.node_index.contains_key(node);
                let fixed = [q];
                let cc = [i, r, t];
                let (want, other): (&[&str], &[&str]) = match mode.as_deref() {
                    Some("FIXED_POWER") => (&fixed, &cc),
                    Some("CONSTANT_CURRENT_R_OF_T") => (&cc, &fixed),
                    _ => (&[], &[]),
                };
                for k in other {
                    if h.keys.contains_key(*k) {
                        self.me(
                            "INTERFACE_KEY_WRONG_MAGNET_MODE",
                            k,
                            format!("not a key of magnet_load_mode {:?}", mode),
                        );
                    }
                }
                for k in want {
                    let has = h.keys.contains_key(*k);
                    if present && !has && self.np_scope {
                        self.me("INTERFACE_KEY_MISSING", k, format!("IFH-1: {node} is present"));
                    }
                    if !present && has {
                        self.push(
                            RunStatus::IncompleteEvidence,
                            "CONDITIONAL_NODE_ABSENT_WITHOUT_REGISTERED_REMAP",
                            k,
                            format!("{node} is absent and v1 registers no re-map of a winding load"),
                        );
                    }
                }
            }
            if flight
                && self.gov.admitted_hall_members().is_empty()
                && discharge_keys.iter().any(|k| h.keys.get(*k).is_some_and(|v| v.evidence != "measured"))
            {
                self.push(RunStatus::NotEvaluated, "CREDIBLE_HALL_TRANSPORT_SET_EMPTY", vocab::HALL_INTERFACE_ID, "flight Hall heat must come from an admitted transport-ensemble member; the credible set is EMPTY (FT-01, NE-01)");
            }
            if flight || bench {
                for k in &discharge_keys {
                    if let Some(v) = h.keys.get(*k) {
                        if v.status == "EVALUATED" && !v.map_derived && v.evidence != "measured" {
                            self.me(
                                "PARAMETRIC_VALUE_NOT_ALLOWED_IN_CASE_CLASS",
                                k,
                                format!(
                                    "{} Hall values are map-derived from an admitted member or measured",
                                    c.case_class
                                ),
                            );
                        }
                    }
                }
            }
        }
        if let Some(i) = &icp {
            if self.np_scope {
                for k in vocab::ICP_KEYS.iter() {
                    if !i.keys.contains_key(k.key) {
                        self.me("INTERFACE_KEY_MISSING", k.key, "IFI-1: all seven keys are present");
                    }
                }
            }
            if flight || bench {
                let any_eval = i.keys.values().any(|v| v.status == "EVALUATED" && v.evidence != "measured");
                let admitted = c
                    .interfaces
                    .icp
                    .as_ref()
                    .is_some_and(|r| self.gov.admitted_icp_producers().contains(&r.producer_id));
                if any_eval && !admitted {
                    self.push(
                        RunStatus::NotEvaluated,
                        "NP_ICP_NEUTRALIZER_NOT_ADMITTED",
                        vocab::ICP_INTERFACE_ID,
                        "RF/ICP heat must come from an admitted NP-ICP-NEUTRALIZER or measured data (NE-02)",
                    );
                }
            }
        }
        if non_firing {
            let rf: Vec<&str> = vocab::ICP_KEYS.iter().map(|k| k.key).collect();
            for (iface, keys) in [(&hall, &discharge_keys), (&icp, &rf)] {
                if let Some(f) = iface {
                    for k in keys.iter() {
                        if f.evaluated(k).is_some_and(|v| v.iter().any(|x| *x != 0.0)) {
                            self.me(
                                "NON_FIRING_LOAD_NOT_ZERO",
                                k,
                                "NON_FIRING registers zero discharge and RF keys (AS-03)",
                            );
                        }
                    }
                }
            }
        }

        // Deposition (E-07).
        let mut dep_report: BTreeMap<String, [Vec<f64>; 3]> = BTreeMap::new();
        let mut i2_resid: f64 = 0.0;
        let mut i2_bound: f64 = CONS_I2_ABS;
        let mut i2_fail = false;
        let mut w_export: BTreeMap<&str, f64> = BTreeMap::new();
        let icp_producer_parts = c.interfaces.icp.as_ref().map(|r| &r.partitions);
        let hall_producer_parts = c.interfaces.hall.as_ref().map(|r| &r.partitions);
        let mut heat: Vec<(&'static str, Deposition, bool)> = Vec::new();
        for k in vocab::HALL_DISCHARGE_KEYS.iter() {
            heat.push((k.key, k.deposition, true));
        }
        if mode.as_deref() == Some("FIXED_POWER") {
            for (_, node, q, ..) in vocab::COILS {
                if self.node_index.contains_key(node) {
                    heat.push((q, Deposition::Coil(node), true));
                }
            }
        }
        for k in vocab::ICP_KEYS.iter() {
            heat.push((k.key, k.deposition, false));
        }
        // Producer partitions only for registered keys.
        for (parts, iface) in
            [(hall_producer_parts, vocab::HALL_INTERFACE_ID), (icp_producer_parts, vocab::ICP_INTERFACE_ID)]
        {
            for k in parts.into_iter().flat_map(|m| m.keys()) {
                if !heat.iter().any(|(h, ..)| h == k) {
                    self.me(
                        "PARTITION_KEY_NOT_REGISTERED",
                        k,
                        format!("{iface} partition for a key that is not deposited"),
                    );
                }
            }
        }
        for k in c.partitions.keys() {
            if !heat.iter().any(|(h, ..)| h == k) {
                self.me("PARTITION_KEY_NOT_REGISTERED", k, "registered partition for a key that is not deposited");
            }
        }
        for (key, rule, is_hall) in heat {
            let iface = if is_hall { &hall } else { &icp };
            let Some(f) = iface else { continue };
            let Some(kv) = f.keys.get(key) else { continue };
            let producer = if is_hall { hall_producer_parts } else { icp_producer_parts }.and_then(|m| m.get(key));
            let Some((nodes_w, wexp, wbnd)) = self.deposition(key, rule, producer) else { continue };
            if matches!(rule, Deposition::Reference) {
                continue;
            }
            let undeclared: Vec<String> = nodes_w
                .iter()
                .filter(|(i, _)| !self.nodes[*i].receives.contains(key))
                .map(|(i, _)| c.nodes[*i].id.clone())
                .collect();
            if !undeclared.is_empty() {
                self.me("NODE_RECEIVES_NOT_DECLARED", key, format!("receivers {undeclared:?} do not list the key"));
                continue;
            }
            w_export.insert(key, wexp);
            let Some(vals) = kv.values.as_ref().filter(|_| kv.status == "EVALUATED") else { continue };
            let tv = f.tv(vals);
            for (node, w) in &nodes_w {
                sources.push(SourceC {
                    node: *node,
                    label: key.to_string(),
                    weight: *w,
                    tv: tv.clone(),
                    kind: SourceKind::Interface,
                });
            }
            let mut rows: [Vec<f64>; 3] = [Vec::new(), Vec::new(), Vec::new()];
            for v in vals {
                let dep: f64 = nodes_w.iter().map(|(_, w)| w * v).sum();
                let (e, b) = (wexp * v, wbnd * v);
                let r = dep + e + b - v;
                let bound = CONS_I2_REL * v.abs() + CONS_I2_ABS;
                if r.abs() / bound > i2_resid / i2_bound {
                    i2_resid = r.abs();
                    i2_bound = bound;
                }
                if r.abs() > bound {
                    i2_fail = true;
                }
                rows[0].push(dep);
                rows[1].push(e);
                rows[2].push(b);
            }
            if wexp > 0.0 {
                exported.insert(format!("{key}.EXPORT"), rows[1].clone());
            }
            if wbnd > 0.0 {
                booked.insert(key.to_string(), rows[2].clone());
            }
            dep_report.insert(key.to_string(), rows);
            breakpoints.extend(tv.breakpoints().iter().copied());
        }
        if i2_fail {
            self.me("CONS_I2_NOT_MET", "interfaces", format!("deposition bookkeeping residual {i2_resid:e} W"));
        }

        // Coils in CONSTANT_CURRENT_R_OF_T (E-09).
        if let (Some(h), Some("CONSTANT_CURRENT_R_OF_T")) = (&hall, mode.as_deref()) {
            for (_, node, _, ik, rk, tk) in vocab::COILS {
                let Some(&ni) = self.node_index.get(node) else { continue };
                if !self.nodes[ni]
                    .receives
                    .iter()
                    .any(|k| vocab::COILS.iter().any(|c| c.2 == k.as_str() && c.1 == node))
                {
                    self.me("NODE_RECEIVES_NOT_DECLARED", node, "the coil node does not declare its winding load");
                    continue;
                }
                let (Some(i), Some(r), Some(t)) = (h.evaluated(ik), h.evaluated(rk), h.evaluated(tk)) else { continue };
                let Some(rel_id) = c.coil_resistance_relations.get(node) else {
                    self.me("CASE_FIELD_MISSING", node, "coil_resistance_relations entry (E-09)");
                    continue;
                };
                let Some(rel) = self.prop(rel_id, "resistance_ratio_relation", node) else { continue };
                if r.iter().any(|x| *x <= 0.0) {
                    self.me("VALUE_NOT_PHYSICAL", rk, "reference resistance > 0");
                    continue;
                }
                let (i, r, t) = (h.tv(i), h.tv(r), h.tv(t));
                breakpoints.extend(i.breakpoints().iter().copied());
                coils.push(CoilC { node: ni, key: ik.to_string(), i, r_ref: r, t_ref: t, rel });
            }
        }
        for node in c.coil_resistance_relations.keys() {
            let is_coil = vocab::COILS.iter().any(|x| x.1 == node);
            if !is_coil || !self.node_index.contains_key(node) || mode.as_deref() != Some("CONSTANT_CURRENT_R_OF_T") {
                self.me(
                    "CASE_FIELD_NOT_APPLICABLE",
                    node,
                    "coil_resistance_relations applies to present coil nodes in CONSTANT_CURRENT_R_OF_T",
                );
            }
        }

        // E-13 and the identities (CONS-I1).
        let mut derived = InterfaceDerived {
            deposition: dep_report,
            cons_i2_residual_w: i2_resid,
            cons_i2_bound_w: i2_bound,
            ..Default::default()
        };
        if let Some(h) = &hall {
            let need = [
                "P_hall_discharge_W",
                "P_hall_jet_W",
                "Q_hall_anode_W",
                "Q_hall_wall_inner_W",
                "Q_hall_wall_outer_W",
                "Q_hall_pole_W",
                "Q_hall_plasma_radiation_W",
                "Q_hall_return_to_icp_W",
                "Q_hall_plume_to_icp_W",
            ];
            let vals: Option<Vec<&Vec<f64>>> = need.iter().map(|k| h.evaluated(k)).collect();
            if let (Some(v), Some(wexp)) = (vals, w_export.get("Q_hall_plasma_radiation_W")) {
                let mut sig = Vec::new();
                let mut exp = Vec::new();
                let mut una = Vec::new();
                for j in 0..h.n {
                    let s = v[2][j] + v[3][j] + v[4][j] + v[5][j] + (1.0 - wexp) * v[6][j] + v[7][j];
                    let pd = v[0][j];
                    let eps_if = EPS_IF_REL * pd + EPS_IF_ABS;
                    if s > pd - v[1][j] + eps_if {
                        self.me(
                            "IFH-3_VIOLATED",
                            vocab::HALL_INTERFACE_ID,
                            format!("Sigma_dep,H {s} > P_d - P_jet + eps_if = {} (index {j})", pd - v[1][j] + eps_if),
                        );
                    }
                    if s + v[8][j] > pd + eps_if {
                        self.me(
                            "IFH-4_VIOLATED",
                            vocab::HALL_INTERFACE_ID,
                            format!(
                                "Sigma_dep,H + Q_plume {} > P_d + eps_if = {} (index {j})",
                                s + v[8][j],
                                pd + eps_if
                            ),
                        );
                    }
                    sig.push(s);
                    exp.push(pd - s - v[8][j]);
                    una.push(pd - v[1][j] - s);
                }
                exported.insert("P_hall_exported_W".into(), exp.clone());
                exported.insert("P_hall_unattributed_W".into(), una.clone());
                derived.sigma_dep_h_w = Some(sig);
                derived.p_hall_exported_w = Some(exp);
                derived.p_hall_unattributed_w = Some(una);
            }
        }
        if let Some(i) = &icp {
            let fwd = i.evaluated("P_icp_rf_forward_W");
            let bus = i.evaluated("P_icp_bus_W");
            if let (Some(fwd), Some(bus)) = (fwd, bus) {
                for j in 0..i.n {
                    if fwd[j] > bus[j] + EPS_IF_REL * bus[j] + EPS_IF_ABS {
                        self.me(
                            "IFI-3_VIOLATED",
                            vocab::ICP_INTERFACE_ID,
                            format!("P_fwd {} > P_bus {} + eps_if (index {j})", fwd[j], bus[j]),
                        );
                    }
                }
            }
            let parts = [
                "Q_icp_plasma_wall_W",
                "Q_icp_coil_ohmic_W",
                "Q_icp_match_W",
                "Q_icp_extraction_W",
                "Q_icp_radiation_W",
            ];
            let vals: Option<Vec<&Vec<f64>>> = parts.iter().map(|k| i.evaluated(k)).collect();
            if let Some(v) = vals {
                let sig: Vec<f64> = (0..i.n).map(|j| v.iter().map(|x| x[j]).sum()).collect();
                if let Some(bus) = bus {
                    let mut bnd = Vec::new();
                    for j in 0..i.n {
                        if sig[j] > bus[j] + EPS_IF_REL * bus[j] + EPS_IF_ABS {
                            self.me(
                                "IFI-4_VIOLATED",
                                vocab::ICP_INTERFACE_ID,
                                format!("Sigma_I {} > P_bus {} + eps_if (index {j})", sig[j], bus[j]),
                            );
                        }
                        bnd.push(bus[j] - sig[j]);
                    }
                    booked.insert("Q_icp_boundary_W".into(), bnd.clone());
                    derived.q_icp_boundary_w = Some(bnd);
                }
                let rf_only = c.interfaces.icp.as_ref().and_then(|r| r.rf_powered_only) == Some(true);
                if let (true, Some(fwd)) = (rf_only, fwd) {
                    for j in 0..i.n {
                        if sig[j] > fwd[j] + EPS_IF_REL * fwd[j] + EPS_IF_ABS {
                            self.me(
                                "IFI-5_VIOLATED",
                                vocab::ICP_INTERFACE_ID,
                                format!("Sigma_I {} > P_fwd {} + eps_if (index {j})", sig[j], fwd[j]),
                            );
                        }
                    }
                }
                exported.insert("Q_icp_extraction_W".into(), v[3].clone());
                derived.sigma_i_w = Some(sig);
            }
        }
        let any = hall.is_some() || icp.is_some();
        (any.then_some(derived), exported, booked, breakpoints)
    }

    /// Resolve one key's receivers: (node weights, EXPORT weight, BOUNDARY weight). `None` with a reason when the
    /// weight set is missing or malformed.
    fn deposition(
        &mut self,
        key: &str,
        rule: Deposition,
        producer: Option<&BTreeMap<String, f64>>,
    ) -> Option<Receivers> {
        let registered = self.case.partitions.get(key).cloned();
        let given: Option<BTreeMap<String, f64>> = match (producer, &registered) {
            (Some(p), _) => Some(p.clone()),
            (None, Some(rid)) => Some(self.weights(rid, key)?),
            (None, None) => None,
        };
        let present = |s: &Self, base: &str| -> (Option<usize>, Vec<usize>) {
            let whole = s.node_index.get(base).copied().filter(|&i| s.nodes[i].role == "REGISTERED");
            let subs: Vec<usize> = (0..s.nodes.len())
                .filter(|&i| s.nodes[i].role == "SUBDIVISION" && s.nodes[i].base.is_some_and(|b| b.id == base))
                .collect();
            (whole, subs)
        };
        let not_registered = |s: &mut Self| {
            s.me(
                "PARTITION_NOT_REGISTERED_FOR_KEY",
                key,
                "this key has a fixed receiver; a partition is registered only for a subdivided receiver",
            );
            None
        };
        match rule {
            Deposition::Reference => {
                if given.is_some() {
                    return not_registered(self);
                }
                Some((Vec::new(), 0.0, 0.0))
            }
            Deposition::Export => {
                if given.is_some() {
                    return not_registered(self);
                }
                Some((Vec::new(), 1.0, 0.0))
            }
            Deposition::Fixed(base) | Deposition::Coil(base) => {
                let (whole, subs) = present(self, base);
                match (whole, subs.is_empty(), given) {
                    (Some(i), true, None) => Some((vec![(i, 1.0)], 0.0, 0.0)),
                    (Some(_), _, Some(_)) => not_registered(self),
                    (None, false, Some(g)) => self.partition(key, &g, &[base], false, false),
                    (None, false, None) => self.missing_partition(key),
                    _ => {
                        self.me("LOAD_RECEIVER_ABSENT", key, format!("{base} is absent"));
                        None
                    }
                }
            }
            Deposition::FixedOrIcpPartitionWhenAbsent(base) => {
                let (whole, subs) = present(self, base);
                match (whole, subs.is_empty(), given) {
                    (Some(i), true, None) => Some((vec![(i, 1.0)], 0.0, 0.0)),
                    (Some(_), _, Some(_)) => not_registered(self),
                    (None, false, Some(g)) => self.partition(key, &g, &[base], false, false),
                    (None, false, None) => self.missing_partition(key),
                    (None, true, Some(g)) => {
                        let icp: Vec<&str> =
                            vocab::NODES.iter().filter(|n| n.group == "ICP_NEUTRALIZER").map(|n| n.id).collect();
                        self.partition(key, &g, &icp, false, false)
                    }
                    (None, true, None) => {
                        self.push(
                            RunStatus::IncompleteEvidence,
                            "CONDITIONAL_NODE_ABSENT_WITHOUT_REGISTERED_REMAP",
                            key,
                            format!("{base} is absent and no partition over ICP nodes is registered (HK-08)"),
                        );
                        None
                    }
                    _ => None,
                }
            }
            Deposition::Partition { allowed, export } => match given {
                Some(g) => self.partition(key, &g, allowed, export, false),
                None => self.missing_partition(key),
            },
            Deposition::DefaultOrPartition { default, allowed } => match given {
                Some(g) => self.partition(key, &g, allowed, false, false),
                None => {
                    let (whole, subs) = present(self, default);
                    match (whole, subs.is_empty()) {
                        (Some(i), true) => Some((vec![(i, 1.0)], 0.0, 0.0)),
                        (None, false) => self.missing_partition(key),
                        _ => {
                            self.me("LOAD_RECEIVER_ABSENT", key, format!("{default} is absent"));
                            None
                        }
                    }
                }
            },
            Deposition::MatchRule => {
                if self.case.match_colocated == Some(true) {
                    let (whole, subs) = present(self, "N_MATCH");
                    match (whole, subs.is_empty(), given) {
                        (Some(i), true, None) => Some((vec![(i, 1.0)], 0.0, 0.0)),
                        (None, false, Some(g)) => self.partition(key, &g, &["N_MATCH"], false, false),
                        (None, false, None) => self.missing_partition(key),
                        (Some(_), _, Some(_)) => not_registered(self),
                        _ => {
                            self.me("LOAD_RECEIVER_ABSENT", key, "match_colocated = true without N_MATCH");
                            None
                        }
                    }
                } else if given.is_some() {
                    not_registered(self)
                } else {
                    Some((Vec::new(), 0.0, 1.0))
                }
            }
        }
    }

    fn missing_partition(&mut self, key: &str) -> Option<Receivers> {
        self.push(
            RunStatus::IncompleteEvidence,
            "PARTITION_MISSING",
            key,
            "the weight set of this key is neither registered nor predicted by the producer (E-07, NE-10)",
        );
        None
    }

    fn partition(
        &mut self,
        key: &str,
        g: &BTreeMap<String, f64>,
        allowed: &[&str],
        export_ok: bool,
        boundary_ok: bool,
    ) -> Option<Receivers> {
        let mut nodes = Vec::new();
        let (mut we, mut wb, mut sum) = (0.0, 0.0, 0.0);
        let mut ok = true;
        for (recv, &w) in g {
            if !(w.is_finite() && w >= 0.0) {
                self.me("PARTITION_WEIGHT_VALUE", key, format!("{recv}: {w}"));
                ok = false;
                continue;
            }
            sum += w;
            if recv == vocab::EXPORT {
                if export_ok {
                    we += w;
                } else {
                    self.me(
                        "PARTITION_RECEIVER_NOT_REGISTERED",
                        key,
                        "EXPORT is not a registered receiver of this key",
                    );
                    ok = false;
                }
                continue;
            }
            if recv == vocab::BOUNDARY {
                if boundary_ok {
                    wb += w;
                } else {
                    self.me(
                        "PARTITION_RECEIVER_NOT_REGISTERED",
                        key,
                        "BOUNDARY is not a registered receiver of this key",
                    );
                    ok = false;
                }
                continue;
            }
            let Some(&i) = self.node_index.get(recv) else {
                self.me("PARTITION_RECEIVER_UNKNOWN", key, format!("{recv:?} is not a node of the case"));
                ok = false;
                continue;
            };
            let base_ok = self.nodes[i].base.is_some_and(|b| allowed.contains(&b.id));
            if !base_ok {
                self.me("PARTITION_RECEIVER_NOT_REGISTERED", key, format!("{recv} is not a registered receiver"));
                ok = false;
                continue;
            }
            if !self.nodes[i].receives.contains(key) {
                self.me(
                    "PARTITION_RECEIVER_NOT_DECLARED",
                    key,
                    format!("{recv} does not list {key} in receives_interface_keys"),
                );
                ok = false;
                continue;
            }
            nodes.push((i, w));
        }
        if ok && (sum - 1.0).abs() > WEIGHT_SUM_TOL {
            self.me("PARTITION_WEIGHTS_SUM", key, format!("sum of weights {sum:.17e} != 1 (E-07)"));
            ok = false;
        }
        ok.then_some((nodes, we, wb))
    }

    // ---------------------------------------------------------------- solver spec and time bases

    fn solver(&mut self) -> Option<(Mode, Vec<f64>)> {
        let s = &self.case.solver;
        let mode = match s.mode.as_str() {
            "STEADY" => {
                if s.t_start_s.is_some() || s.t_end_s.is_some() || s.dt_s.is_some() || s.orbit_period_s.is_some() {
                    self.me("SOLVER_FIELD_NOT_APPLICABLE", "solver", "STEADY carries no time fields");
                    return None;
                }
                Mode::Steady
            }
            "ORBIT_AVERAGE_STEADY" => match (s.orbit_period_s, s.t_start_s, s.t_end_s, s.dt_s) {
                (Some(p), None, None, None) if p > 0.0 && p.is_finite() => Mode::OrbitAverageSteady { period: p },
                _ => {
                    self.me("SOLVER_FIELDS", "solver", "ORBIT_AVERAGE_STEADY needs orbit_period_s > 0 only");
                    return None;
                }
            },
            "TRANSIENT" => match (s.t_start_s, s.t_end_s, s.dt_s, s.orbit_period_s) {
                (Some(t0), Some(t1), Some(dt), None)
                    if t0.is_finite() && t1.is_finite() && t1 > t0 && dt > 0.0 && dt.is_finite() =>
                {
                    Mode::Transient { t0, t1, dt }
                }
                _ => {
                    self.me("SOLVER_FIELDS", "solver", "TRANSIENT needs t_start_s < t_end_s and dt_s > 0");
                    return None;
                }
            },
            "ORBIT_TRANSIENT_PERIODIC" => match (s.orbit_period_s, s.dt_s, s.t_start_s, s.t_end_s) {
                (Some(p), Some(dt), None, None) if p > 0.0 && p.is_finite() && dt > 0.0 && dt <= p => {
                    Mode::OrbitPeriodic { period: p, dt }
                }
                _ => {
                    self.me(
                        "SOLVER_FIELDS",
                        "solver",
                        "ORBIT_TRANSIENT_PERIODIC needs orbit_period_s and 0 < dt_s <= period",
                    );
                    return None;
                }
            },
            other => {
                self.me("SOLVER_MODE_UNKNOWN", "solver.mode", other.to_string());
                return None;
            }
        };
        let mut t_init = Vec::new();
        let mut ok = true;
        for n in &self.case.nodes {
            match s.t_init_k.get(&n.id) {
                Some(t) if t.is_finite() && *t >= 0.0 => t_init.push(*t),
                _ => {
                    self.me("T_INIT_MISSING", &n.id, "registered initial temperature (NUM-02)");
                    ok = false;
                }
            }
        }
        for k in s.t_init_k.keys() {
            if !self.node_index.contains_key(k) {
                self.me("T_INIT_UNKNOWN_NODE", k, "T_init for a node that is not registered");
                ok = false;
            }
        }
        if matches!(mode, Mode::OrbitAverageSteady { .. }) {
            self.labels.insert("ORBIT_MEAN_LOAD_STEADY_STATE_NOT_TIME_MEAN_OR_EXTREMES".into());
        }
        ok.then_some((mode, t_init))
    }

    fn check_time_bases(&mut self, mode: Mode, coils: &[CoilC]) {
        let mut all: Vec<(String, TimeValue, bool)> = std::mem::take(&mut self.time_values);
        for c in coils {
            for (tv, fixed) in [(&c.i, false), (&c.r_ref, true), (&c.t_ref, true)] {
                all.push((c.key.clone(), tv.clone(), fixed));
            }
        }
        for (iface, rec) in [
            (vocab::HALL_INTERFACE_ID, &self.case.interfaces.hall),
            (vocab::ICP_INTERFACE_ID, &self.case.interfaces.icp),
        ] {
            if let Some(r) = rec {
                if let Some(t) = &r.time_basis.breakpoints_s {
                    all.push((iface.to_string(), TimeValue::Zoh { t: t.clone(), v: vec![0.0; t.len()] }, false));
                }
            }
        }
        for (id, tv, fixed) in all {
            let Some(first) = tv.first_breakpoint() else { continue };
            let last = *tv.breakpoints().last().expect("non-empty");
            match mode {
                Mode::Steady => self.me("TIME_SERIES_IN_STEADY_CASE", &id, "STEADY cases use steady values only"),
                Mode::Transient { t0, .. } => {
                    if first > t0 {
                        self.me("TIME_SERIES_START", &id, format!("first breakpoint {first} s after t_start {t0} s"));
                    }
                }
                Mode::OrbitAverageSteady { period } | Mode::OrbitPeriodic { period, .. } => {
                    if first != 0.0 || last >= period {
                        self.me("TIME_SERIES_ORBIT", &id, "orbit series hold breakpoints in [0, period) starting at 0");
                    }
                    if fixed && matches!(mode, Mode::OrbitAverageSteady { .. }) {
                        self.me(
                            "TIME_SERIES_NOT_AVERAGEABLE",
                            &id,
                            "E-12 averages loads; fixed temperatures and coil references are steady",
                        );
                    }
                }
            }
        }
    }

    // ---------------------------------------------------------------- floating nodes (D-07, FT-09)

    /// D-07 / FT-09 on the registered structure: links by their endpoints, enclosures by their view factors (all members
    /// joined when the view factors do not resolve, so an unresolved record never manufactures a floating node).
    fn floating(&mut self, rad: &Radiation) {
        let c = self.case;
        let n = c.nodes.len();
        let anchor = n;
        let mut parent: Vec<usize> = (0..=n).collect();
        fn find(p: &mut [usize], x: usize) -> usize {
            let mut r = x;
            while p[r] != r {
                r = p[r];
            }
            let mut y = x;
            while p[y] != r {
                let nx = p[y];
                p[y] = r;
                y = nx;
            }
            r
        }
        fn union(p: &mut [usize], a: usize, b: usize) {
            let (ra, rb) = (find(p, a), find(p, b));
            if ra != rb {
                p[ra.max(rb)] = ra.min(rb);
            }
        }
        let end = |s: &Self, e: &Endpoint| -> Option<usize> {
            match (&e.node, &e.boundary) {
                (Some(id), None) => s.node_index.get(id).copied(),
                (None, Some(_)) => Some(anchor),
                _ => None,
            }
        };
        for l in &c.links {
            if let (Some(a), Some(b)) = (end(self, &l.a), end(self, &l.b)) {
                union(&mut parent, a, b);
            }
        }
        let point = |k: StructKind| match k {
            StructKind::Node(i) => i,
            _ => anchor,
        };
        for e in &rad.enclosures {
            for (k, kk) in e.kinds.iter().enumerate() {
                if *kk == StructKind::Sink {
                    continue;
                }
                for (l, kl) in e.kinds.iter().enumerate() {
                    let joined = match &e.f {
                        Some(f) => f[k][l] > 0.0,
                        None => true,
                    };
                    if joined && k != l {
                        union(&mut parent, point(*kk), point(*kl));
                    }
                }
            }
        }
        let root = find(&mut parent, anchor);
        for i in 0..n {
            if find(&mut parent, i) != root {
                let id = c.nodes[i].id.clone();
                self.me("FLOATING_NODE", &id, "no conduction or radiation path to a sink or boundary (D-07)");
            }
        }
    }
}

/// Assemble a case: every reason found, and the compiled network when no reason blocks the solve.
pub fn assemble(case: &ThermalCase, gov: &GovernedContext) -> Assembly {
    let synthetic = case.case_class == "SYNTHETIC_VERIFICATION";
    let mut a = Asm {
        case,
        gov,
        synthetic,
        np_scope: case.topology_scope == "NP_THERMAL_NETWORK",
        records: BTreeMap::new(),
        reasons: Vec::new(),
        labels: BTreeSet::new(),
        members: BTreeSet::new(),
        node_index: BTreeMap::new(),
        nodes: Vec::new(),
        time_values: Vec::new(),
    };
    let mut interface_hashes = BTreeMap::new();
    for (name, rec) in
        [(vocab::HALL_INTERFACE_ID, &case.interfaces.hall), (vocab::ICP_INTERFACE_ID, &case.interfaces.icp)]
    {
        if let Some(r) = rec {
            interface_hashes.insert(name.to_string(), sha256_hex(&serde_json::to_vec(r).expect("serializable")));
        }
    }
    let input_set_sha256 = sha256_hex(&serde_json::to_vec(case).expect("serializable"));

    a.validate_records();
    a.case_level();
    a.scan_identifiers();
    let (parts, biot) = a.nodes();
    let rad = a.enclosures();
    let links = a.links();
    let env = a.environment(&rad);
    let mut sources = Vec::new();
    a.thermal_control_and_fluxes(&mut sources);
    let mut coils = Vec::new();
    let (derived, exported, booked, mut breakpoints) = a.interfaces(&mut sources, &mut coils);
    let solver = a.solver();
    if let Some((mode, _)) = &solver {
        a.check_time_bases(*mode, &coils);
    }
    a.floating(&rad);
    let encl = rad.compiled;
    let node_surfaces = rad.node_surfaces;

    for s in &sources {
        breakpoints.extend(s.tv.breakpoints().iter().copied());
    }
    for e in &env {
        for tv in [&e.s, &e.f_sun, &e.nu, &e.a, &e.f_alb, &e.q_olr, &e.f_earth, &e.rho, &e.v, &e.alpha_e] {
            breakpoints.extend(tv.breakpoints().iter().copied());
        }
    }
    for l in &links {
        for end in [&l.a, &l.b] {
            if let End::Fixed { t, .. } = end {
                breakpoints.extend(t.breakpoints().iter().copied());
            }
        }
    }
    for e in &encl {
        for m in &e.members {
            if let MemberKind::Host { t, .. } | MemberKind::Sink { t, .. } = &m.kind {
                breakpoints.extend(t.breakpoints().iter().copied());
            }
        }
    }
    breakpoints.sort_by(|x, y| x.partial_cmp(y).unwrap_or(std::cmp::Ordering::Equal));
    breakpoints.dedup();

    let blocked = a.has_blocking() || a.reasons.iter().any(|r| r.status == RunStatus::OutOfDomain);
    let compiled = match solver {
        Some((mode, t_init)) if !blocked => {
            let ids: Vec<String> = case.nodes.iter().map(|n| n.id.clone()).collect();
            let net = Net { ids, parts, links, encl, env, coils, sources };
            let (ranges_steady, ranges_transient) = ranges(&net, &node_surfaces, &biot);
            let link_boundary = net
                .links
                .iter()
                .map(|l| match (&l.a, &l.b) {
                    (End::Fixed { boundary, .. }, _) | (_, End::Fixed { boundary, .. }) => Some(boundary.clone()),
                    _ => None,
                })
                .collect();
            Some(Compiled {
                net,
                mode,
                t_init,
                ranges_steady,
                ranges_transient,
                biot,
                node_surfaces,
                link_boundary,
                derived,
                exported,
                booked,
                breakpoints,
            })
        }
        _ => None,
    };
    Assembly {
        reasons: a.reasons,
        labels: a.labels,
        ensemble_member_ids: a.members,
        interface_hashes,
        input_set_sha256,
        compiled,
    }
}

/// Node temperature ranges (D-10): intersection of every property range evaluated at the node temperature; the
/// transient range adds the c_p records.
fn ranges(net: &Net, node_surfaces: &[Vec<(f64, Prop)>], biot: &[Option<BiotC>]) -> (Vec<Range>, Vec<Range>) {
    let n = net.ids.len();
    let mut r: Vec<Range> = (0..n).map(|_| Range::new()).collect();
    for (i, surfaces) in node_surfaces.iter().enumerate() {
        for (_, p) in surfaces {
            r[i].add(p.t_min, p.t_max, &p.record_id);
        }
    }
    for e in &net.env {
        r[e.node].add(e.alpha.t_min, e.alpha.t_max, &e.alpha.record_id);
    }
    for l in &net.links {
        for end in [&l.a, &l.b] {
            if let End::Node(i) = end {
                match &l.kind {
                    LinkKind::Conduction { k, .. } => r[*i].add(k.t_min, k.t_max, &k.record_id),
                    LinkKind::Linear { record_id, t_min, t_max, .. } => r[*i].add(*t_min, *t_max, record_id),
                }
            }
        }
    }
    for c in &net.coils {
        r[c.node].add(c.rel.t_min, c.rel.t_max, &c.rel.record_id);
    }
    for (i, b) in biot.iter().enumerate() {
        if let Some(b) = b {
            r[i].add(b.k.t_min, b.k.t_max, &b.k.record_id);
        }
    }
    let mut rt = r.clone();
    for (i, parts) in net.parts.iter().enumerate() {
        for (_, cp) in parts {
            rt[i].add(cp.t_min, cp.t_max, &cp.record_id);
        }
    }
    (r, rt)
}
