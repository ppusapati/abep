//! A9.7 F2 filter stage between the intake exit (IF-A1) and the compressor inlet (IF-A2)
//! (`abep_sim/design/filter_stage.py`, contract PARITY-C-ABEP_SIM_DESIGN_FILTER_STAGE_PY-V1).
//!
//! Per species and direction a stage carries transmission / capture / conversion records (reflection derived), the
//! free-molecular conductance C_s = alpha_s A cbar_s / 4 (Livesey 1998, Eqs. 2.14-2.15; Kn > 0.5, Table 2.1) and the
//! A9.13 S6.19 element records. Numbers come only from usable evidence records or from an explicit
//! PARAMETRIC_SENSITIVITY case; a TBD makes `apply` refuse (REFUSED_TBD -> INCOMPLETE_EVIDENCE). Nothing here selects,
//! ranks or qualifies a filter concept.

use crate::error::{fse, key_error, PyResult};
use crate::pyops::{self, py_max, py_min, py_repr};
use crate::rec::{fnum, onum, ostr, slist, Obj};
use abep_types::constants::{species_mass, K_B};
use abep_types::EvalStatus;
use serde_json::{Map, Value};
use std::f64::consts::PI;

pub const QUANTITY_TYPES: [&str; 12] = [
    "measured",
    "digitized",
    "inferred",
    "reconstructed",
    "model-derived",
    "assumed",
    "owner-allocation",
    "owner-stated",
    "published analog",
    "qualitative",
    "definition",
    "published convention",
];
pub const EV_STATUSES: [&str; 6] =
    ["EVIDENCED", "MODEL_DERIVED", "OWNER_GIVEN", "DEFINITION", "TBD", "PLACEHOLDER_NOT_A_FLIGHT_DESIGN"];
pub const USABLE_STATUSES: [&str; 4] = ["EVIDENCED", "MODEL_DERIVED", "OWNER_GIVEN", "DEFINITION"];
pub const PLACEHOLDER: &str = "PLACEHOLDER_NOT_A_FLIGHT_DESIGN";
pub const AO_GATE_OUTCOMES: [&str; 4] =
    ["INCOMPLETE_EVIDENCE", "OUT_OF_DOMAIN", "GATE_VIOLATED_BY_EVIDENCE", "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN"];
pub const NO_ATOMIC_O: &str = "NO_ATOMIC_O";
pub const SURROGATE_LABELS: [&str; 3] = [NO_ATOMIC_O, "DEDICATED_AO_SOURCE", "NONE"];
pub const INCIDENCES: [&str; 2] = ["diffuse_thermal", "hyperthermal_directed"];
pub const REGIMES: [&str; 1] = ["free_molecular"];
pub const KN_MOLECULAR_MIN: f64 = 0.5;
pub const KN_SOURCE: &str =
    "R. G. Livesey, 'Flow of gases through tubes and orifices', ch. 2 in J. M. Lafferty (ed.), \
Foundations of Vacuum Science and Technology, Wiley 1998, ISBN 0-471-17593-5, Table 2.1 (molecular Kn > 0.5)";
pub const PROTECTION_TARGETS: [&str; 5] = [
    "particulates_debris",
    "sputter_wear_products",
    "atomic_oxygen_to_downstream_surfaces",
    "ambient_charged_particles",
    "filter_self_contamination",
];
pub const INLET_LABELS: [&str; 3] = ["EVIDENCE", "PARAMETRIC_SENSITIVITY", "NORMALIZED_UNIT_INPUT"];
pub const LABEL_EVIDENCE: &str = "EVIDENCE_BASED";
pub const LABEL_SENSITIVITY: &str = "PARAMETRIC_SENSITIVITY_NOT_EVIDENCE";
pub const LABEL_NORMALIZED: &str = "NORMALIZED_UNIT_INPUT_NOT_A_PHYSICAL_STATE";
pub const RESULT_STATUSES: [&str; 5] =
    ["NUMERIC", "NO_FILTER_IDENTITY", "REFUSED_TBD", "OUT_OF_DOMAIN", "NONPHYSICAL_INPUT"];
/// Fixed stoichiometric product maps: only O -> O2 (mass conserved).
pub const CONVERSION_PRODUCTS: [(&str, &[(&str, f64)]); 1] = [("O", &[("O2", 1.0)])];
pub const CONSERVATION_TOL: f64 = 1e-12;
pub const ROLE_BASELINE: &str = "BASELINE_INERT_LOW_RECOMBINATION";
pub const ROLE_CATALYTIC_RESEARCH: &str = "RESEARCH_VARIANT_CATALYTIC_NOT_BASELINE";
pub const ROLE_REFERENCE_BOUND: &str = "REFERENCE_BOUND_FC00_NOT_ADMISSIBLE_FLIGHT_ARCHITECTURE";
pub const ROLES: [&str; 3] = [ROLE_BASELINE, ROLE_CATALYTIC_RESEARCH, ROLE_REFERENCE_BOUND];
pub const CATALYTIC_VARIANT_EVIDENCE: [&str; 4] = [
    "species-conversion measurement",
    "flow / conductance measurement",
    "thermal / material qualification",
    "H-1 performance map on the converted composition",
];
pub const BASELINE_PROTECTION_TARGETS: [&str; 1] = ["particulates_debris"];
pub const NOT_CREDITED_TARGETS: [(&str, &str); 3] = [
    (
        "atomic_oxygen_to_downstream_surfaces",
        "atomic O is propellant (RFP-P17-05), not a contaminant to be removed in the baseline (A9.13 S6.3)",
    ),
    (
        "sputter_wear_products",
        "compressor wear products are downstream-generated: not credited to the intake filter unless backstream \
transport is demonstrated; a separate downstream guard / trap is defined if needed (A9.13 S6.3)",
    ),
    (
        "ambient_charged_particles",
        "not a baseline filter requirement unless a hazard analysis demonstrates the need (A9.13 S6.3)",
    ),
];
pub const ACCEPTANCE_ITEMS: [&str; 7] = [
    "capture efficiency vs registered contaminant / particle class",
    "species-resolved propellant transmission",
    "pressure-loss / conductance penalty",
    "O recombination / conversion probability",
    "retained contaminant capacity",
    "AO erosion / material durability",
    "effect on AG-12 feed-state closure",
];
pub const COLE_SOURCE: &str = "R. G. Livesey 1998 (Lafferty (ed.), Foundations of Vacuum Science and Technology, \
Wiley), Table 2.5 'Transmission Probabilities for Cylindrical Tubes', column alpha (Cole [11]); transcribed from the \
open PDF accessed 2026-10-01 (see source register LIVESEY1998)";
/// (l/d, alpha) exactly as tabulated (diffuse entry, diffusely reflecting walls, free molecular flow).
pub const COLE_TABLE_2_5: [(f64, f64); 29] = [
    (0.05, 0.952399),
    (0.15, 0.869928),
    (0.25, 0.801271),
    (0.35, 0.743410),
    (0.45, 0.694044),
    (0.5, 0.671984),
    (0.6, 0.632228),
    (0.7, 0.597364),
    (0.8, 0.566507),
    (0.9, 0.538975),
    (1.0, 0.514231),
    (1.5, 0.420055),
    (2.0, 0.356572),
    (2.5, 0.310525),
    (3.0, 0.275438),
    (3.5, 0.247735),
    (4.0, 0.225263),
    (4.5, 0.206641),
    (5.0, 0.190941),
    (10.0, 0.109304),
    (15.0, 0.076912),
    (20.0, 0.059422),
    (25.0, 0.048448),
    (30.0, 0.040913),
    (35.0, 0.035415),
    (40.0, 0.031225),
    (45.0, 0.027925),
    (50.0, 0.025258),
    (500.0, 0.002646),
];
pub const DIRECTIONS: [&str; 2] = ["f", "b"];

/// Products of a conversion channel, if the species has one.
pub fn conversion_products(s: &str) -> Option<&'static [(&'static str, f64)]> {
    CONVERSION_PRODUCTS.iter().find(|(k, _)| *k == s).map(|(_, p)| *p)
}

fn finite(x: Option<f64>) -> bool {
    matches!(x, Some(v) if v.is_finite())
}

fn blank(s: &str) -> bool {
    s.trim().is_empty()
}

/// `INTERFACE_POSITION` (A9.13 S6.6 / S6.19).
pub fn interface_position() -> Value {
    Obj::new()
        .s("upstream_interface", "IF-A1 (intake / channel-array exit, downstream of the primary intake / collimator)")
        .s("downstream_interface", "IF-A2 (compressor inlet)")
        .b("production_path_element", true)
        .b("folded_into_intake_efficiency", false)
        .s("basis", "A9.13 S6.6 / S6.19; RFP-P16-02 (Intake -> Filter -> Compressor)")
        .build()
}

fn not_credited_targets() -> Value {
    let mut m = Map::new();
    for (k, v) in NOT_CREDITED_TARGETS {
        m.insert(k.into(), Value::String(v.into()));
    }
    Value::Object(m)
}

// ------------------------------------------------------------------------------------------------ evidence record
/// VALUE | UNCERTAINTY | EVIDENCE CLASS | SOURCE | STATUS record (docs/EVIDENCE.md).
#[derive(Debug, Clone, PartialEq)]
pub struct Ev {
    pub value: Option<f64>,
    pub units: String,
    pub status: String,
    pub evidence_class: Option<String>,
    pub source: Option<String>,
    pub uncertainty: Option<String>,
    pub basis: String,
    pub evidence_level: Option<i64>,
    pub domain: Option<String>,
    pub requires: Option<String>,
}

/// Raw evidence-level input as the reference accepts it (an int, or anything else, which is refused).
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum LevelInput {
    None,
    Int(i64),
    Invalid,
}

impl Ev {
    /// Validated construction (`EV.__post_init__`). `value_is_number` false models a non-number value (e.g. a bool).
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        value: Option<f64>,
        value_is_number: bool,
        units: &str,
        status: &str,
        evidence_class: Option<&str>,
        source: Option<&str>,
        uncertainty: Option<&str>,
        basis: &str,
        evidence_level: LevelInput,
        domain: Option<&str>,
        requires: Option<&str>,
    ) -> PyResult<Ev> {
        if !EV_STATUSES.contains(&status) {
            return Err(fse(format!("EV.status {status:?} not in EV_STATUSES")));
        }
        if units.is_empty() {
            return Err(fse("EV.units must be a non-empty string ('-' for dimensionless)"));
        }
        let level = match evidence_level {
            LevelInput::None => None,
            LevelInput::Int(i) => Some(i),
            LevelInput::Invalid => Some(i64::MIN),
        };
        let ev = Ev {
            value,
            units: units.into(),
            status: status.into(),
            evidence_class: evidence_class.map(String::from),
            source: source.map(String::from),
            uncertainty: uncertainty.map(String::from),
            basis: basis.into(),
            evidence_level: level,
            domain: domain.map(String::from),
            requires: requires.map(String::from),
        };
        if status == "TBD" {
            if value.is_some() || !value_is_number {
                return Err(fse("a TBD record carries no value"));
            }
            if requires.map(blank).unwrap_or(true) {
                return Err(fse("a TBD record must say what it requires"));
            }
            return Ok(ev);
        }
        if !value_is_number || !finite(value) {
            return Err(fse(format!("EV.value must be finite for status {status}")));
        }
        if !evidence_class.map(|c| QUANTITY_TYPES.contains(&c)).unwrap_or(false) {
            return Err(fse("EV.evidence_class not in QUANTITY_TYPES"));
        }
        if source.map(blank).unwrap_or(true) {
            return Err(fse("a non-TBD record needs a source"));
        }
        if let Some(l) = level {
            if !(1..8).contains(&l) {
                return Err(fse("evidence_level must be 1..7 (docs/EVIDENCE.md) or None"));
            }
        }
        Ok(ev)
    }

    pub fn tbd(requires: &str, units: &str, basis: &str) -> Ev {
        Ev {
            value: None,
            units: units.into(),
            status: "TBD".into(),
            evidence_class: None,
            source: None,
            uncertainty: None,
            basis: basis.into(),
            evidence_level: None,
            domain: None,
            requires: Some(requires.into()),
        }
    }

    pub fn definition(value: f64, units: &str, basis: &str) -> Ev {
        Ev {
            value: Some(value),
            units: units.into(),
            status: "DEFINITION".into(),
            evidence_class: Some("definition".into()),
            source: Some("definition (no physical element)".into()),
            uncertainty: Some("exact by definition".into()),
            basis: basis.into(),
            evidence_level: None,
            domain: None,
            requires: None,
        }
    }

    pub fn usable_as_evidence(&self) -> bool {
        USABLE_STATUSES.contains(&self.status.as_str())
            && finite(self.value)
            && self.evidence_class.as_deref() != Some("assumed")
            && self.source.as_deref().map(|s| !s.is_empty()).unwrap_or(false)
    }

    pub fn to_dict(&self) -> Value {
        let value = if self.status == "TBD" { Value::String("TBD".into()) } else { onum(self.value) };
        Obj::new()
            .set("value", value)
            .s("units", &self.units)
            .s("status", &self.status)
            .set("evidence_class", ostr(self.evidence_class.as_deref()))
            .set("evidence_level", self.evidence_level.map(Value::from).unwrap_or(Value::Null))
            .set("source", ostr(self.source.as_deref()))
            .set("uncertainty", ostr(self.uncertainty.as_deref()))
            .s("basis", &self.basis)
            .set("domain", ostr(self.domain.as_deref()))
            .set("requires", ostr(self.requires.as_deref()))
            .build()
    }
}

// ------------------------------------------------------------------------------------------------ Cole / plate
/// Free-molecular transmission probability of one cylindrical hole for diffuse incidence (Cole, Livesey Table 2.5):
/// tabulated points exactly, log-log interpolation between them, refusal outside 0.05 <= l/d <= 500.
pub fn cole_transmission_probability(l_over_d: f64) -> PyResult<Ev> {
    if !l_over_d.is_finite() {
        return Err(fse("l/d must be finite"));
    }
    let lo = COLE_TABLE_2_5[0].0;
    let hi = COLE_TABLE_2_5[28].0;
    if !(lo <= l_over_d && l_over_d <= hi) {
        return Err(fse(format!(
            "l/d = {} outside the tabulated domain [{}, {}] (no extrapolation)",
            py_repr(l_over_d),
            py_repr(lo),
            py_repr(hi)
        )));
    }
    let mut a = None;
    for w in COLE_TABLE_2_5.windows(2) {
        let ((x0, y0), (x1, y1)) = (w[0], w[1]);
        if l_over_d == x0 {
            a = Some(y0);
            break;
        }
        if l_over_d == x1 {
            a = Some(y1);
            break;
        }
        if x0 < l_over_d && l_over_d < x1 {
            let t = (pyops::log(l_over_d)? - pyops::log(x0)?) / (pyops::log(x1)? - pyops::log(x0)?);
            a = Some(pyops::exp(pyops::log(y0)? + t * (pyops::log(y1)? - pyops::log(y0)?))?);
            break;
        }
    }
    let tabulated = COLE_TABLE_2_5.iter().any(|(x, _)| l_over_d == *x);
    Ok(Ev {
        value: a,
        units: "-".into(),
        status: "MODEL_DERIVED".into(),
        evidence_class: Some("model-derived".into()),
        source: Some(COLE_SOURCE.into()),
        uncertainty: Some(
            if tabulated {
                "tabulated value (Livesey: Berman Eq. (2.24) agrees with Cole within 0.13 %)"
            } else {
                "log-log interpolation between tabulated points; interpolation error not quantified"
            }
            .into(),
        ),
        basis: format!("cylindrical hole l/d = {}", py_repr(l_over_d)),
        evidence_level: Some(4),
        domain: Some(
            "free molecular (Kn > 0.5), diffuse incidence, diffusely reflecting walls, 0.05 <= l/d <= 500".into(),
        ),
        requires: None,
    })
}

/// Face-averaged diffuse-incidence transmission of a plate of identical cylindrical holes: phi * alpha_hole.
pub fn perforated_plate_alpha(l_over_d: f64, open_fraction: f64) -> PyResult<Ev> {
    if !(open_fraction.is_finite() && 0.0 < open_fraction && open_fraction <= 1.0) {
        return Err(fse("open_fraction must be in (0, 1]"));
    }
    let a = cole_transmission_probability(l_over_d)?;
    let av = a.value.expect("model-derived value");
    Ok(Ev {
        value: Some(open_fraction * av),
        units: "-".into(),
        status: "MODEL_DERIVED".into(),
        evidence_class: Some("model-derived".into()),
        source: Some(format!("{}; face average phi * alpha (our construction)", a.source.unwrap_or_default())),
        uncertainty: Some(format!("{}; independent-hole assumption not quantified", a.uncertainty.unwrap_or_default())),
        basis: format!(
            "perforated plate, l/d = {}, open fraction {} (design candidate)",
            py_repr(l_over_d),
            py_repr(open_fraction)
        ),
        evidence_level: Some(4),
        domain: Some(format!("{}; independent holes; land area reflects to the incident side", a.domain.unwrap())),
        requires: None,
    })
}

/// cbar = sqrt(8 k T / (pi m)).
pub fn mean_speed_m_s(species: &str, t_k: f64) -> PyResult<f64> {
    let m = species_mass(species).map_err(|_| key_error(species))?;
    pyops::sqrt(8.0 * K_B * t_k / (PI * m))
}

// ------------------------------------------------------------------------------------------------ protection / AO
#[derive(Debug, Clone, PartialEq)]
pub struct ProtectionFunction {
    pub target: String,
    pub mechanism: String,
    pub capture_efficiency: Ev,
    pub evidence_note: String,
}

impl ProtectionFunction {
    pub fn new(target: &str, mechanism: &str, capture_efficiency: Ev, evidence_note: &str) -> PyResult<Self> {
        if !PROTECTION_TARGETS.contains(&target) {
            return Err(fse(format!("protection target {target:?} not in PROTECTION_TARGETS")));
        }
        if blank(mechanism) {
            return Err(fse("protection mechanism must be stated (qualitative)"));
        }
        Ok(ProtectionFunction {
            target: target.into(),
            mechanism: mechanism.into(),
            capture_efficiency,
            evidence_note: evidence_note.into(),
        })
    }

    pub fn to_dict(&self) -> Value {
        Obj::new()
            .s("target", &self.target)
            .s("mechanism", &self.mechanism)
            .set("capture_efficiency", self.capture_efficiency.to_dict())
            .s("evidence_note", &self.evidence_note)
            .build()
    }
}

/// Atomic-oxygen / material applicability of a filter material (P4 vocabulary; never PASS, never selected).
#[derive(Debug, Clone, PartialEq)]
pub struct MaterialApplicability {
    pub material: String,
    pub ao_compatibility: String,
    pub surrogate_label: String,
    pub o_recombination_probability: Ev,
    pub ao_erosion_yield: Ev,
    pub evidence_refs: Vec<String>,
    pub note: String,
}

impl MaterialApplicability {
    pub fn default_o_recombination() -> Ev {
        Ev::tbd(
            "O heterogeneous recombination probability on this material at the filter temperature and surface state \
(dedicated AO measurement; owner row 102 retains catalytic reference coupons)",
            "-",
            "",
        )
    }

    pub fn default_ao_erosion() -> Ev {
        Ev::tbd("AO erosion yield at the filter's O energy and fluence (dedicated AO source, row 132)", "cm^3/atom", "")
    }

    pub fn new(
        material: &str,
        ao_compatibility: &str,
        surrogate_label: &str,
        o_recombination_probability: Option<Ev>,
        ao_erosion_yield: Option<Ev>,
        evidence_refs: Vec<String>,
        note: &str,
    ) -> PyResult<Self> {
        if !AO_GATE_OUTCOMES.contains(&ao_compatibility) {
            return Err(fse(format!("ao_compatibility {ao_compatibility:?} not in AO_GATE_OUTCOMES")));
        }
        if !SURROGATE_LABELS.contains(&surrogate_label) {
            return Err(fse(format!("surrogate_label {surrogate_label:?} not in SURROGATE_LABELS")));
        }
        if ao_compatibility == "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN" && surrogate_label == NO_ATOMIC_O {
            return Err(fse("N2 + O2 surrogate evidence (NO_ATOMIC_O) is never AO proof (owner row 132)"));
        }
        if ao_compatibility != "INCOMPLETE_EVIDENCE" && evidence_refs.is_empty() {
            return Err(fse("an AO gate outcome other than INCOMPLETE_EVIDENCE needs evidence_refs"));
        }
        Ok(MaterialApplicability {
            material: material.into(),
            ao_compatibility: ao_compatibility.into(),
            surrogate_label: surrogate_label.into(),
            o_recombination_probability: o_recombination_probability.unwrap_or_else(Self::default_o_recombination),
            ao_erosion_yield: ao_erosion_yield.unwrap_or_else(Self::default_ao_erosion),
            evidence_refs,
            note: note.into(),
        })
    }

    pub fn to_dict(&self) -> Value {
        Obj::new()
            .s("material", &self.material)
            .s("application", "APP-FILTER (P4 materials application, A9.13 S6.6)")
            .s("ao_compatibility", &self.ao_compatibility)
            .s("surrogate_label", &self.surrogate_label)
            .set("o_recombination_probability", self.o_recombination_probability.to_dict())
            .set("ao_erosion_yield", self.ao_erosion_yield.to_dict())
            .set("evidence_refs", slist(&self.evidence_refs))
            .s("note", &self.note)
            .s("final_material_status", "OPEN")
            .build()
    }
}

// ------------------------------------------------------------------------------------------------ transport
/// Per-species, per-direction transmission / capture / conversion records; reflection is derived.
#[derive(Debug, Clone, PartialEq)]
pub struct SpeciesTransport {
    pub tau_f: Ev,
    pub capture_f: Ev,
    pub conversion_f: Ev,
    pub tau_b: Ev,
    pub capture_b: Ev,
    pub conversion_b: Ev,
    pub alpha_conductance: Ev,
    pub product_to_outlet_f: Option<Ev>,
    pub product_to_outlet_b: Option<Ev>,
}

impl SpeciesTransport {
    /// `records()` in the reference order.
    pub fn records(&self) -> Vec<(&'static str, &Ev)> {
        let mut out = vec![
            ("tau_f", &self.tau_f),
            ("capture_f", &self.capture_f),
            ("conversion_f", &self.conversion_f),
            ("tau_b", &self.tau_b),
            ("capture_b", &self.capture_b),
            ("conversion_b", &self.conversion_b),
            ("alpha_conductance", &self.alpha_conductance),
        ];
        if let Some(e) = &self.product_to_outlet_f {
            out.push(("product_to_outlet_f", e));
        }
        if let Some(e) = &self.product_to_outlet_b {
            out.push(("product_to_outlet_b", e));
        }
        out
    }

    /// Replace one record by its key (used by callers that build stages from evidence records).
    pub fn set_record(&mut self, key: &str, ev: Ev) -> bool {
        match key {
            "tau_f" => self.tau_f = ev,
            "capture_f" => self.capture_f = ev,
            "conversion_f" => self.conversion_f = ev,
            "tau_b" => self.tau_b = ev,
            "capture_b" => self.capture_b = ev,
            "conversion_b" => self.conversion_b = ev,
            "alpha_conductance" => self.alpha_conductance = ev,
            "product_to_outlet_f" if self.product_to_outlet_f.is_some() => self.product_to_outlet_f = Some(ev),
            "product_to_outlet_b" if self.product_to_outlet_b.is_some() => self.product_to_outlet_b = Some(ev),
            _ => return false,
        }
        true
    }
}

/// All-TBD transport for one species: the honest default for every real filter concept today.
pub fn tbd_species_transport(species: &str) -> SpeciesTransport {
    let w = format!(" for {species}");
    let conv = conversion_products(species).is_some();
    let t = |s: String| Ev::tbd(&s, "-", "");
    SpeciesTransport {
        tau_f: t(format!(
            "forward transmission{w} at the declared forward incidence (measured on the element, or model-derived from \
a defined geometry within its domain)"
        )),
        capture_f: t(format!("forward capture fraction{w} (adsorption / deposition; steady-state evidence)")),
        conversion_f: t(if conv {
            format!("forward conversion fraction{w} (O recombination to O2; dedicated AO evidence)")
        } else {
            format!(
                "forward conversion fraction{w}: no conversion channel is modelled, so only an evidenced 0 is \
admissible (otherwise a channel must be added to CONVERSION_PRODUCTS)"
            )
        }),
        tau_b: t(format!("backflow transmission{w} (diffuse incidence from the plenum side)")),
        capture_b: t(format!("backflow capture fraction{w}")),
        conversion_b: t(if conv {
            format!("backflow conversion fraction{w} (O recombination to O2)")
        } else {
            format!(
                "backflow conversion fraction{w}: no conversion channel modelled; only an evidenced 0 is admissible"
            )
        }),
        alpha_conductance: t(format!("diffuse-incidence transmission probability{w} for the conductance law")),
        product_to_outlet_f: conv.then(|| t(format!("routing of forward conversion products to the outlet face{w}"))),
        product_to_outlet_b: conv.then(|| t(format!("routing of backflow conversion products to the outlet face{w}"))),
    }
}

// ------------------------------------------------------------------------------------------------ inlet / case
/// Ordered (species -> value) map, the reference's dict iteration order.
pub type SpMap = Vec<(String, f64)>;

pub fn sp_get(m: &[(String, f64)], k: &str) -> Option<f64> {
    m.iter().find(|(s, _)| s == k).map(|(_, v)| *v)
}

fn same_keys(a: &[(String, f64)], b: &[(String, f64)]) -> bool {
    let mut x: Vec<&str> = a.iter().map(|(k, _)| k.as_str()).collect();
    let mut y: Vec<&str> = b.iter().map(|(k, _)| k.as_str()).collect();
    x.sort();
    x.dedup();
    y.sort();
    y.dedup();
    x == y
}

/// State presented to the filter stage (F1 at IF-A1 plus the downstream incident flux from F4).
#[derive(Debug, Clone, PartialEq)]
pub struct InletState {
    pub mdot_forward_kgps: SpMap,
    pub mdot_back_incident_kgps: SpMap,
    pub back_incident_basis: String,
    pub t_gas_k: Option<f64>,
    pub incidence: String,
    pub knudsen_number: Option<f64>,
    pub label: String,
    pub provenance: String,
    pub incident_power_w: Option<SpMap>,
    pub incident_power_source: String,
}

impl InletState {
    pub fn validate(&self) -> PyResult<()> {
        if !INLET_LABELS.contains(&self.label.as_str()) {
            return Err(fse(format!("inlet label {:?} not in INLET_LABELS", self.label)));
        }
        if let Some(p) = &self.incident_power_w {
            if !same_keys(p, &self.mdot_forward_kgps) {
                return Err(fse("incident_power_W must name the same species as the flows"));
            }
            if p.iter().any(|(_, v)| !v.is_finite() || *v < 0.0) {
                return Err(fse("incident_power_W values must be finite and >= 0"));
            }
            if blank(&self.incident_power_source) {
                return Err(fse("incident_power_W needs incident_power_source"));
            }
        }
        if !INCIDENCES.contains(&self.incidence.as_str()) {
            return Err(fse(format!("incidence {:?} not in INCIDENCES", self.incidence)));
        }
        if blank(&self.provenance) || blank(&self.back_incident_basis) {
            return Err(fse("inlet provenance and back_incident_basis must be stated"));
        }
        if !same_keys(&self.mdot_forward_kgps, &self.mdot_back_incident_kgps) {
            return Err(fse("forward and back-incident flows must name the same species"));
        }
        for (s, v) in &self.mdot_forward_kgps {
            if species_mass(s).is_err() {
                return Err(fse(format!("species {s:?} has no mass in abep_sim.constants.M_SPECIES")));
            }
            let b = sp_get(&self.mdot_back_incident_kgps, s).unwrap_or(f64::NAN);
            for d in [*v, b] {
                if !d.is_finite() || d < 0.0 {
                    return Err(fse(format!("mass flow of {s} must be finite and >= 0")));
                }
            }
        }
        if let Some(t) = self.t_gas_k {
            if !t.is_finite() || t <= 0.0 {
                return Err(fse("T_gas_K must be > 0 or None"));
            }
        }
        if let Some(k) = self.knudsen_number {
            if !k.is_finite() || k <= 0.0 {
                return Err(fse("knudsen_number must be > 0 or None"));
            }
        }
        Ok(())
    }
}

/// Explicit, labelled parametric sensitivity case (never evidence).
#[derive(Debug, Clone, PartialEq)]
pub struct SensitivityCase {
    pub case_id: String,
    pub label: String,
    pub overrides: SpMap,
    pub rationale: String,
    pub regime_assumption: Option<String>,
    pub temperature_override_k: Option<f64>,
}

impl SensitivityCase {
    pub fn validate(&self) -> PyResult<()> {
        if !self.label.contains("PARAMETRIC_SENSITIVITY") {
            return Err(fse("a sensitivity case label must contain PARAMETRIC_SENSITIVITY"));
        }
        if blank(&self.case_id) || blank(&self.rationale) {
            return Err(fse("sensitivity case needs an id and a rationale"));
        }
        for (k, v) in &self.overrides {
            if !v.is_finite() {
                return Err(fse(format!("override {k} must be finite")));
            }
        }
        if let Some(r) = &self.regime_assumption {
            if !REGIMES.contains(&r.as_str()) {
                return Err(fse("regime_assumption must be one of REGIMES"));
            }
        }
        if let Some(t) = self.temperature_override_k {
            if !t.is_finite() || t <= 0.0 {
                return Err(fse("temperature_override_K must be > 0"));
            }
        }
        Ok(())
    }

    fn get(&self, k: &str) -> Option<f64> {
        sp_get(&self.overrides, k)
    }
}

// ------------------------------------------------------------------------------------------------ result
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FilterStatus {
    Numeric,
    NoFilterIdentity,
    RefusedTbd,
    OutOfDomain,
    NonphysicalInput,
}

impl FilterStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            FilterStatus::Numeric => "NUMERIC",
            FilterStatus::NoFilterIdentity => "NO_FILTER_IDENTITY",
            FilterStatus::RefusedTbd => "REFUSED_TBD",
            FilterStatus::OutOfDomain => "OUT_OF_DOMAIN",
            FilterStatus::NonphysicalInput => "NONPHYSICAL_INPUT",
        }
    }

    /// Registered mapping (INV-F-02): REFUSED_TBD is the SC-WP-02 gate 'filter species transport TBD'.
    pub fn eval_status(self) -> EvalStatus {
        match self {
            FilterStatus::Numeric | FilterStatus::NoFilterIdentity => EvalStatus::Evaluated,
            FilterStatus::RefusedTbd => EvalStatus::IncompleteEvidence,
            FilterStatus::OutOfDomain | FilterStatus::NonphysicalInput => EvalStatus::OutOfDomain,
        }
    }
}

/// Outlet state per species, or a refusal, with the A9.13 S6.19 element records.
#[derive(Debug, Clone, PartialEq)]
pub struct FilterResult {
    pub status: FilterStatus,
    pub label: String,
    pub stage_id: String,
    pub concept_id: String,
    pub missing: Vec<Value>,
    pub overrides_used: Vec<Value>,
    pub assumptions: Vec<Value>,
    /// species -> record (reference keys)
    pub species: Vec<(String, Value)>,
    pub totals: Vec<(String, f64)>,
    pub composition_net_downstream: Option<Value>,
    pub mass_kg: Option<f64>,
    pub regime: Map<String, Value>,
    pub protection: Vec<Value>,
    pub materials: Vec<Value>,
    pub notes: Vec<String>,
    pub role: String,
    pub admissible_as_baseline: bool,
    pub interfaces: Value,
    pub retained_inventory: Map<String, Value>,
    pub thermal_load: Value,
    pub material_state: Value,
    pub validity_flags: Value,
}

fn species_obj(v: &[(String, Value)]) -> Value {
    let mut m = Map::new();
    for (k, x) in v {
        m.insert(k.clone(), x.clone());
    }
    Value::Object(m)
}

impl FilterResult {
    pub fn numeric(&self) -> bool {
        matches!(self.status, FilterStatus::Numeric | FilterStatus::NoFilterIdentity)
    }

    pub fn total(&self, k: &str) -> Option<f64> {
        sp_get(&self.totals, k)
    }

    /// The species record field (as a float leaf).
    pub fn species_f64(&self, s: &str, path: &[&str]) -> Option<f64> {
        let mut v = self.species.iter().find(|(k, _)| k == s).map(|(_, v)| v)?;
        for p in path {
            v = v.get(p)?;
        }
        crate::rec::as_f64(v)
    }

    pub fn to_dict(&self) -> Value {
        let totals: Value = if self.totals.is_empty() {
            Value::Object(Map::new())
        } else {
            crate::rec::fmap(self.totals.iter().map(|(k, v)| (k.as_str(), *v)))
        };
        Obj::new()
            .s("status", self.status.as_str())
            .s("label", &self.label)
            .s("stage_id", &self.stage_id)
            .s("concept_id", &self.concept_id)
            .set("missing", Value::Array(self.missing.clone()))
            .set("overrides_used", Value::Array(self.overrides_used.clone()))
            .set("assumptions", Value::Array(self.assumptions.clone()))
            .set("species", species_obj(&self.species))
            .set("totals", totals)
            .set("composition_net_downstream", self.composition_net_downstream.clone().unwrap_or(Value::Null))
            .of("mass_kg", self.mass_kg)
            .set("regime", Value::Object(self.regime.clone()))
            .set("protection", Value::Array(self.protection.clone()))
            .set("materials", Value::Array(self.materials.clone()))
            .set("notes", slist(&self.notes))
            .s("role", &self.role)
            .b("admissible_as_baseline", self.admissible_as_baseline)
            .set("interfaces", self.interfaces.clone())
            .set("retained_inventory", Value::Object(self.retained_inventory.clone()))
            .set("thermal_load", self.thermal_load.clone())
            .set("material_state", self.material_state.clone())
            .set("validity_flags", self.validity_flags.clone())
            .build()
    }

    fn species_map(&self, f: impl Fn(&Value) -> Value) -> Value {
        let mut m = Map::new();
        for (s, v) in &self.species {
            m.insert(s.clone(), f(v));
        }
        Value::Object(m)
    }

    /// Species-resolved forward / reverse transmission and the conductance / pressure effect (S6.19).
    pub fn species_transmission(&self) -> Value {
        if !self.numeric() {
            return Obj::new()
                .s("status", "NOT_EVALUATED")
                .s("reason", self.status.as_str())
                .set("missing", Value::Array(self.missing.clone()))
                .build();
        }
        Obj::new()
            .s("status", self.status.as_str())
            .s("label", &self.label)
            .set(
                "species",
                self.species_map(|v| {
                    Obj::new()
                        .set("forward_transmission", v["fractions_forward"]["transmitted"].clone())
                        .set("reverse_transmission", v["fractions_backflow"]["transmitted"].clone())
                        .set("forward_conversion", v["fractions_forward"]["converted"].clone())
                        .set("reverse_conversion", v["fractions_backflow"]["converted"].clone())
                        .set("forward_capture", v["fractions_forward"]["captured"].clone())
                        .set("reverse_capture", v["fractions_backflow"]["captured"].clone())
                        .set("conductance_m3_s", v["conductance_m3_s"].clone())
                        .set("delta_p_Pa", v["delta_p_Pa"].clone())
                        .build()
                }),
            )
            .build()
    }

    /// IF-A2 record for the compressor inlet (F3).
    pub fn to_f3_record(&self) -> Value {
        if !self.numeric() {
            return Obj::new()
                .s("interface", "IF-A2 filter -> compressor")
                .s("status", "NOT_EVALUATED")
                .s("reason", self.status.as_str())
                .set("missing", Value::Array(self.missing.clone()))
                .s("label", &self.label)
                .s("filter_role", &self.role)
                .build();
        }
        let comp = self.composition_net_downstream.as_ref();
        Obj::new()
            .s("interface", "IF-A2 filter -> compressor")
            .s("status", self.status.as_str())
            .s("label", &self.label)
            .set("mdot_s_net_downstream_kgps", self.species_map(|v| v["net_downstream_kgps"].clone()))
            .set("mdot_s_gross_downstream_kgps", self.species_map(|v| v["gross_downstream_kgps"].clone()))
            .set("w_s_mass", comp.map(|c| c["mass_fraction"].clone()).unwrap_or(Value::Null))
            .set("x_s_mole", comp.map(|c| c["mole_fraction"].clone()).unwrap_or(Value::Null))
            .set("delta_p_s_Pa", self.species_map(|v| v["delta_p_Pa"].clone()))
            .set("conductance_s_m3_s", self.species_map(|v| v["conductance_m3_s"].clone()))
            .b("filter_flow_effect_applied", self.status == FilterStatus::Numeric)
            .of("filter_retained_mass_rate_kgps", self.total("captured_kgps"))
            .of("mass_kg", self.mass_kg)
            .set("overrides_used", Value::Array(self.overrides_used.clone()))
            .s("filter_role", &self.role)
            .b("admissible_as_baseline", self.admissible_as_baseline)
            .set("validity_flags", self.validity_flags.clone())
            .build()
    }

    /// Upstream return record for the intake (F1).
    pub fn to_f1_record(&self) -> Value {
        if !self.numeric() {
            return Obj::new()
                .s("interface", "IF-A1 intake <- filter (return)")
                .s("status", "NOT_EVALUATED")
                .s("reason", self.status.as_str())
                .set("missing", Value::Array(self.missing.clone()))
                .s("label", &self.label)
                .build();
        }
        Obj::new()
            .s("interface", "IF-A1 intake <- filter (return)")
            .s("status", self.status.as_str())
            .s("label", &self.label)
            .set("mdot_s_gross_upstream_kgps", self.species_map(|v| v["gross_upstream_kgps"].clone()))
            .build()
    }
}

fn miss(parameter: &str, status: &str, requires: &str) -> Value {
    Obj::new().s("parameter", parameter).s("status", status).s("requires", requires).build()
}

// ------------------------------------------------------------------------------------------------ stage
#[derive(Debug, Clone, PartialEq)]
pub struct FilterStage {
    pub stage_id: String,
    pub concept_id: String,
    pub kind: String,
    pub transport: Vec<(String, SpeciesTransport)>,
    pub forward_incidence: String,
    pub regime: String,
    pub face_area_m2: Ev,
    pub areal_mass_kg_m2: Ev,
    pub protection: Vec<ProtectionFunction>,
    pub materials: Vec<MaterialApplicability>,
    pub description: String,
    pub role: String,
    pub element_temperature_k: Ev,
    pub energy_accommodation: Ev,
    pub contaminant_capacity_kg: Ev,
    pub research_variant_evidence: Vec<(String, String)>,
}

pub fn default_face_area() -> Ev {
    Ev::tbd("filter face area (geometry)", "m^2", "")
}
pub fn default_areal_mass() -> Ev {
    Ev::tbd("areal mass of the element incl. frame (design + sourced densities, or weighed)", "kg/m^2", "")
}
pub fn default_element_temperature() -> Ev {
    Ev::tbd("filter element temperature at the operating state (P3 coupled thermal network / measurement)", "K", "")
}
pub fn default_energy_accommodation() -> Ev {
    Ev::tbd(
        "energy accommodation of the incident gas on the element (measured / sourced for the element material)",
        "-",
        "",
    )
}
pub fn default_contaminant_capacity() -> Ev {
    Ev::tbd(
        "retained contaminant capacity (defined contamination environment + measured element retention; \
pre-registered before LOCK-1, A9.13 S6.3)",
        "kg",
        "",
    )
}

type Resolved = (Vec<(String, f64)>, Vec<Value>, Vec<Value>);

impl FilterStage {
    /// `FilterStage.__post_init__`.
    pub fn validate(&self) -> PyResult<()> {
        if self.kind != "none" && self.kind != "element" {
            return Err(fse("kind must be 'none' or 'element'"));
        }
        if !ROLES.contains(&self.role.as_str()) {
            return Err(fse(format!("role {:?} not in ROLES", self.role)));
        }
        if (self.kind == "none") != (self.role == ROLE_REFERENCE_BOUND) {
            return Err(fse(
                "only the no-element FC-00 case carries the reference-bound role, and it always does (A9.13 S6.5)",
            ));
        }
        if !self.research_variant_evidence.is_empty() && self.role != ROLE_CATALYTIC_RESEARCH {
            return Err(fse("research_variant_evidence belongs to the catalytic research variant only"));
        }
        for (item, reference) in &self.research_variant_evidence {
            if !CATALYTIC_VARIANT_EVIDENCE.contains(&item.as_str()) || blank(reference) {
                return Err(fse("research_variant_evidence entries are (item, reference) pairs"));
            }
        }
        if !INCIDENCES.contains(&self.forward_incidence.as_str()) {
            return Err(fse("forward_incidence must be one of INCIDENCES"));
        }
        if !REGIMES.contains(&self.regime.as_str()) {
            return Err(fse("regime must be one of REGIMES"));
        }
        for (s, t) in &self.transport {
            if species_mass(s).is_err() {
                return Err(fse(format!("species {s:?} has no mass in abep_sim.constants.M_SPECIES")));
            }
            if conversion_products(s).is_some() {
                if t.product_to_outlet_f.is_none() || t.product_to_outlet_b.is_none() {
                    return Err(fse(format!("{s} has a conversion channel: product routing records are required")));
                }
            } else {
                for (d, r) in [("conversion_f", &t.conversion_f), ("conversion_b", &t.conversion_b)] {
                    if r.status != "TBD" && r.value != Some(0.0) {
                        return Err(fse(format!(
                            "{s} has no conversion channel in CONVERSION_PRODUCTS; {d} must be 0 or TBD"
                        )));
                    }
                }
            }
        }
        Ok(())
    }

    /// The 'no filter' option for trade studies: the definitional identity (FC-00 reference bound only).
    pub fn none(species: &[&str]) -> FilterStage {
        let one = Ev::definition(1.0, "-", "no element: every molecule passes");
        let zero = Ev::definition(0.0, "-", "no element: nothing captured / converted");
        let transport = species
            .iter()
            .map(|s| {
                let conv = conversion_products(s).is_some();
                (
                    s.to_string(),
                    SpeciesTransport {
                        tau_f: one.clone(),
                        capture_f: zero.clone(),
                        conversion_f: zero.clone(),
                        tau_b: one.clone(),
                        capture_b: zero.clone(),
                        conversion_b: zero.clone(),
                        alpha_conductance: one.clone(),
                        product_to_outlet_f: conv.then(|| zero.clone()),
                        product_to_outlet_b: conv.then(|| zero.clone()),
                    },
                )
            })
            .collect();
        FilterStage {
            stage_id: "F2-NONE".into(),
            concept_id: "FC-00".into(),
            kind: "none".into(),
            transport,
            forward_incidence: "diffuse_thermal".into(),
            regime: "free_molecular".into(),
            face_area_m2: Ev::definition(0.0, "m^2", "no element"),
            areal_mass_kg_m2: Ev::definition(0.0, "kg/m^2", "no element"),
            protection: vec![],
            materials: vec![],
            description: "no filter stage: FC-00 ideal reference bound only (A9.13 S6.5), never an admissible flight \
architecture under the RFP intake -> filter -> compressor chain"
                .into(),
            role: ROLE_REFERENCE_BOUND.into(),
            element_temperature_k: Ev::definition(0.0, "K", "no element (no element temperature)"),
            energy_accommodation: Ev::definition(0.0, "-", "no element: nothing absorbs energy"),
            contaminant_capacity_kg: Ev::definition(0.0, "kg", "no element: nothing is retained"),
            research_variant_evidence: vec![],
        }
    }

    /// A filter concept with every physical parameter TBD (fails closed in evidence mode).
    #[allow(clippy::too_many_arguments)]
    pub fn tbd(
        stage_id: &str,
        concept_id: &str,
        species: &[&str],
        forward_incidence: &str,
        description: &str,
        protection: Vec<ProtectionFunction>,
        materials: Vec<MaterialApplicability>,
        role: &str,
    ) -> PyResult<FilterStage> {
        let st = FilterStage {
            stage_id: stage_id.into(),
            concept_id: concept_id.into(),
            kind: "element".into(),
            transport: species.iter().map(|s| (s.to_string(), tbd_species_transport(s))).collect(),
            forward_incidence: forward_incidence.into(),
            regime: "free_molecular".into(),
            face_area_m2: default_face_area(),
            areal_mass_kg_m2: default_areal_mass(),
            protection,
            materials,
            description: description.into(),
            role: role.into(),
            element_temperature_k: default_element_temperature(),
            energy_accommodation: default_energy_accommodation(),
            contaminant_capacity_kg: default_contaminant_capacity(),
            research_variant_evidence: vec![],
        };
        st.validate()?;
        Ok(st)
    }

    /// A deliberately catalytic O -> O2 element: a separately labelled research / contingency variant only.
    pub fn catalytic_research_variant(
        stage_id: &str,
        concept_id: &str,
        species: &[&str],
        forward_incidence: &str,
        description: &str,
        materials: Vec<MaterialApplicability>,
        research_variant_evidence: Vec<(String, String)>,
    ) -> PyResult<FilterStage> {
        let st = FilterStage {
            stage_id: stage_id.into(),
            concept_id: concept_id.into(),
            kind: "element".into(),
            transport: species.iter().map(|s| (s.to_string(), tbd_species_transport(s))).collect(),
            forward_incidence: forward_incidence.into(),
            regime: "free_molecular".into(),
            face_area_m2: default_face_area(),
            areal_mass_kg_m2: default_areal_mass(),
            protection: vec![],
            materials,
            description: if description.is_empty() {
                "catalytic O -> O2 research variant (not baseline, A9.13 S6.4)".into()
            } else {
                description.into()
            },
            role: ROLE_CATALYTIC_RESEARCH.into(),
            element_temperature_k: default_element_temperature(),
            energy_accommodation: default_energy_accommodation(),
            contaminant_capacity_kg: default_contaminant_capacity(),
            research_variant_evidence,
        };
        st.validate()?;
        Ok(st)
    }

    /// Parameter records in the reference order.
    pub fn parameters(&self) -> Vec<(String, &Ev)> {
        let mut out = vec![
            ("face_area_m2".to_string(), &self.face_area_m2),
            ("areal_mass_kg_m2".to_string(), &self.areal_mass_kg_m2),
        ];
        for (s, t) in &self.transport {
            for (k, ev) in t.records() {
                out.push((format!("{k}.{s}"), ev));
            }
        }
        out
    }

    pub fn parameter_ids(&self) -> Vec<String> {
        self.parameters().into_iter().map(|(k, _)| k).collect()
    }

    fn resolve(&self, case: Option<&SensitivityCase>) -> PyResult<Resolved> {
        let params = self.parameters();
        if let Some(c) = case {
            let mut unknown: Vec<&str> =
                c.overrides.iter().map(|(k, _)| k.as_str()).filter(|k| !params.iter().any(|(p, _)| p == k)).collect();
            unknown.sort();
            unknown.dedup();
            if !unknown.is_empty() {
                return Err(fse(format!("sensitivity overrides name unknown parameters: {unknown:?}")));
            }
        }
        let (mut vals, mut missing, mut used) = (vec![], vec![], vec![]);
        for (pid, ev) in params {
            if let Some(v) = case.and_then(|c| c.get(&pid)) {
                vals.push((pid.clone(), v));
                used.push(
                    Obj::new()
                        .s("parameter", &pid)
                        .f("value", v)
                        .s("replaces_status", &ev.status)
                        .of("replaces_value", ev.value)
                        .build(),
                );
            } else if ev.usable_as_evidence() {
                vals.push((pid.clone(), ev.value.expect("usable")));
            } else {
                let req = if ev.status == "TBD" {
                    ev.requires.clone().unwrap_or_default()
                } else {
                    format!(
                        "{} record is not usable as evidence (class {})",
                        ev.status,
                        ev.evidence_class.as_deref().unwrap_or("None")
                    )
                };
                missing.push(miss(&pid, &ev.status, &req));
            }
        }
        Ok((vals, missing, used))
    }

    /// Outlet state per species, or a refusal, annotated with the A9.13 S6.19 element records.
    pub fn apply(&self, inlet: &InletState, case: Option<&SensitivityCase>) -> PyResult<FilterResult> {
        let mut res = self.apply_core(inlet, case)?;
        self.annotate(&mut res, inlet);
        Ok(res)
    }

    fn annotate(&self, res: &mut FilterResult, inlet: &InletState) {
        res.role = self.role.clone();
        res.admissible_as_baseline = false;
        res.interfaces = interface_position();
        let captured = if res.numeric() { res.total("captured_kgps") } else { None };
        let mut ri = Map::new();
        ri.insert("propellant_capture_rate_kgps".into(), onum(captured));
        ri.insert(
            "propellant_capture_status".into(),
            Value::String(if captured.is_some() { "EVALUATED_FROM_STAGE_RECORDS" } else { "NOT_EVALUATED" }.into()),
        );
        ri.insert(
            "contaminant_capture_rate".into(),
            Value::String("TBD (contamination environment / particle classes not defined; A9.13 S6.3)".into()),
        );
        ri.insert("capacity_kg".into(), self.contaminant_capacity_kg.to_dict());
        ri.insert("inventory_over_time".into(), Value::String("retained_inventory_kg(result, duration_s)".into()));
        ri.insert(
            "note".into(),
            Value::String("compressor wear products are not credited to this filter (A9.13 S6.3)".into()),
        );
        res.retained_inventory = ri;
        res.thermal_load = self.thermal_load(res, inlet);
        let mut aos: Vec<String> = self.materials.iter().map(|m| m.ao_compatibility.clone()).collect();
        aos.sort();
        aos.dedup();
        if aos.is_empty() {
            aos.push("INCOMPLETE_EVIDENCE".into());
        }
        res.material_state = Obj::new()
            .s("application", "APP-FILTER (P4, A9.13 S6.6)")
            .set("materials", slist(self.materials.iter().map(|m| m.material.clone())))
            .set("ao_compatibility", slist(&aos))
            .set("element_temperature_K", self.element_temperature_k.to_dict())
            .s("erosion_state", "NOT_EVALUATED (AO erosion yield / fluence TBD per material)")
            .s("final_material_status", if self.kind == "element" { "OPEN" } else { "NOT_APPLICABLE_NO_ELEMENT" })
            .build();
        let conv_o = if res.numeric() && res.species.iter().any(|(s, _)| s == "O") {
            let o = &res.species.iter().find(|(s, _)| s == "O").expect("O").1;
            Obj::new()
                .set("forward", o["fractions_forward"]["converted"].clone())
                .set("reverse", o["fractions_backflow"]["converted"].clone())
                .build()
        } else {
            Value::Null
        };
        let provided: Vec<&str> = self.research_variant_evidence.iter().map(|(i, _)| i.as_str()).collect();
        let rv_missing: Vec<&str> = if self.role == ROLE_CATALYTIC_RESEARCH {
            CATALYTIC_VARIANT_EVIDENCE.iter().copied().filter(|i| !provided.contains(i)).collect()
        } else {
            vec![]
        };
        res.validity_flags = Obj::new()
            .s("status", res.status.as_str())
            .s("label", &res.label)
            .set("regime", if res.regime.is_empty() { Value::Null } else { Value::Object(res.regime.clone()) })
            .s("incidence_declared", &self.forward_incidence)
            .s("incidence_inlet", &inlet.incidence)
            .b("species_resolved", true)
            .b("folded_into_intake_efficiency", false)
            .b("reference_bound_only", self.role == ROLE_REFERENCE_BOUND)
            .b("research_variant_only", self.role == ROLE_CATALYTIC_RESEARCH)
            .set("research_variant_evidence_missing", slist(rv_missing))
            .set("o_conversion_fraction", conv_o)
            .s("o_recombination_acceptance_limit", "TBD (pre-registered before LOCK-1 from evidence, A9.13 S6.3)")
            .set("acceptance_items_preregistration_pending", slist(ACCEPTANCE_ITEMS))
            .set("baseline_protection_targets", slist(BASELINE_PROTECTION_TARGETS))
            .set("not_credited_targets", not_credited_targets())
            .b("f4_gap_model_supports_lossy_element", false)
            .build();
    }

    /// Absorbed thermal load upper bound (accommodation x incident energy flux); NOT_EVALUATED while unsourced.
    fn thermal_load(&self, res: &FilterResult, inlet: &InletState) -> Value {
        if self.kind == "none" {
            return Obj::new().s("status", "NO_ELEMENT").f("absorbed_upper_bound_W", 0.0).build();
        }
        let mut need: Vec<String> = vec![];
        if inlet.incident_power_w.is_none() {
            need.push("incident energy flux per species at the inlet face (F1 / TPMC)".into());
        }
        let ea = &self.energy_accommodation;
        if !ea.usable_as_evidence() {
            need.push(
                ea.requires
                    .clone()
                    .filter(|r| !r.is_empty())
                    .unwrap_or_else(|| format!("energy accommodation ({} is not usable evidence)", ea.status)),
            );
        }
        if !res.numeric() {
            need.push(format!("stage outcome {}", res.status.as_str()));
        } else if res.total("converted_kgps").unwrap_or(0.0) > 0.0 {
            need.push("O recombination heat release (sourced) for the converted O flow".into());
        }
        if !need.is_empty() {
            return Obj::new().s("status", "NOT_EVALUATED").set("requires", slist(need)).build();
        }
        let inc = pyops::py_sum(inlet.incident_power_w.as_ref().expect("checked").iter().map(|(_, v)| *v));
        let eav = ea.value.expect("usable");
        Obj::new()
            .s("status", "UPPER_BOUND_GAS_TRANSFER")
            .f("absorbed_upper_bound_W", eav * inc)
            .f("incident_W", inc)
            .f("energy_accommodation", eav)
            .f("recombination_heat_W", 0.0)
            .s("source", &inlet.incident_power_source)
            .s("label", &res.label)
            .build()
    }

    fn routing_not_needed(pid: &str, vals: &[(String, f64)]) -> bool {
        let Some(rest) = pid.strip_prefix("product_to_outlet_") else { return false };
        let Some((d, s)) = rest.split_once('.') else { return false };
        sp_get(vals, &format!("conversion_{d}.{s}")) == Some(0.0)
    }

    fn apply_core(&self, inlet: &InletState, case: Option<&SensitivityCase>) -> PyResult<FilterResult> {
        let mut label = LABEL_EVIDENCE;
        if inlet.label == "NORMALIZED_UNIT_INPUT" {
            label = LABEL_NORMALIZED;
        }
        if inlet.label == "PARAMETRIC_SENSITIVITY" || case.is_some() {
            label = LABEL_SENSITIVITY;
        }
        let mut res = FilterResult {
            status: FilterStatus::RefusedTbd,
            label: label.into(),
            stage_id: self.stage_id.clone(),
            concept_id: self.concept_id.clone(),
            missing: vec![],
            overrides_used: vec![],
            assumptions: vec![],
            species: vec![],
            totals: vec![],
            composition_net_downstream: None,
            mass_kg: None,
            regime: Map::new(),
            protection: self.protection.iter().map(|p| p.to_dict()).collect(),
            materials: self.materials.iter().map(|m| m.to_dict()).collect(),
            notes: vec![],
            role: ROLE_BASELINE.into(),
            admissible_as_baseline: false,
            interfaces: Value::Object(Map::new()),
            retained_inventory: Map::new(),
            thermal_load: Value::Object(Map::new()),
            material_state: Value::Object(Map::new()),
            validity_flags: Value::Object(Map::new()),
        };
        if let Some(c) = case {
            res.notes.push(format!("sensitivity case {}: {}", c.case_id, c.rationale));
        }
        let inlet_sp: Vec<(String, f64)> = inlet.mdot_forward_kgps.clone();
        let stage_sp: Vec<(String, f64)> = self.transport.iter().map(|(s, _)| (s.clone(), 0.0)).collect();
        if !same_keys(&inlet_sp, &stage_sp) {
            return Err(fse("inlet species != stage species"));
        }
        let (vals, mut missing, used) = self.resolve(case)?;
        res.overrides_used = used;
        let mut t = inlet.t_gas_k;
        if let Some(to) = case.and_then(|c| c.temperature_override_k) {
            t = Some(to);
            res.assumptions.push(
                Obj::new().s("what", "gas temperature").f("value_K", to).s("basis", "sensitivity override").build(),
            );
        }
        if self.kind == "element" {
            if inlet.incidence != self.forward_incidence {
                res.status = FilterStatus::OutOfDomain;
                res.missing = vec![miss(
                    "forward_incidence",
                    "OUT_OF_DOMAIN",
                    &format!("tau_f records valid for {}; inlet is {}", self.forward_incidence, inlet.incidence),
                )];
                return Ok(res);
            }
            if let Some(kn) = inlet.knudsen_number {
                res.regime.insert("regime".into(), Value::String(self.regime.clone()));
                res.regime.insert("knudsen_number".into(), fnum(kn));
                res.regime.insert("criterion".into(), Value::String(format!("Kn > {}", py_repr(KN_MOLECULAR_MIN))));
                res.regime.insert("source".into(), Value::String(KN_SOURCE.into()));
                if !(kn > KN_MOLECULAR_MIN) {
                    res.status = FilterStatus::OutOfDomain;
                    res.missing = vec![miss(
                        "knudsen_number",
                        "OUT_OF_DOMAIN",
                        &format!(
                            "free-molecular laws need Kn > {} (Livesey Table 2.1); a transitional / continuum law is \
not implemented",
                            py_repr(KN_MOLECULAR_MIN)
                        ),
                    )];
                    return Ok(res);
                }
            } else if case.and_then(|c| c.regime_assumption.as_deref()) == Some("free_molecular") {
                res.regime.insert("regime".into(), Value::String(self.regime.clone()));
                res.regime.insert("knudsen_number".into(), Value::Null);
                res.regime.insert(
                    "criterion".into(),
                    Value::String("ASSUMED free molecular (sensitivity case; Kn not established)".into()),
                );
                res.assumptions.push(
                    Obj::new()
                        .s("what", "flow regime")
                        .s("value", "free_molecular")
                        .s("basis", "sensitivity case regime_assumption")
                        .build(),
                );
            } else {
                missing.push(miss(
                    "knudsen_number",
                    "TBD",
                    "Knudsen number at the filter (mean free path from the IF-A1 state and sourced collision cross \
sections; characteristic dimension of the element)",
                ));
            }
            if t.is_none() {
                missing.push(miss("T_gas_K", "TBD", "gas temperature at the filter (IF-A1)"));
            }
        } else {
            res.regime.insert("regime".into(), Value::String("no element".into()));
            res.regime.insert("knudsen_number".into(), onum(inlet.knudsen_number));
            res.regime.insert("criterion".into(), Value::String("not applicable (identity)".into()));
        }
        missing.retain(|m| !Self::routing_not_needed(m["parameter"].as_str().unwrap_or(""), &vals));
        if !missing.is_empty() {
            res.status = FilterStatus::RefusedTbd;
            res.missing = missing;
            return Ok(res);
        }
        let val = |k: &str| -> PyResult<f64> { sp_get(&vals, k).ok_or_else(|| key_error(k)) };

        // per-species balances
        struct Fr {
            transmitted: f64,
            reflected: f64,
            captured: f64,
            converted: f64,
        }
        let mut fractions: Vec<(String, [Fr; 2])> = vec![];
        for (s, _) in &self.transport {
            let mut frs: Vec<Fr> = vec![];
            for d in DIRECTIONS {
                let tau = val(&format!("tau_{d}.{s}"))?;
                let cap = val(&format!("capture_{d}.{s}"))?;
                let conv = val(&format!("conversion_{d}.{s}"))?;
                for (name, v) in [("tau", tau), ("capture", cap), ("conversion", conv)] {
                    if !(0.0 <= v && v <= 1.0) {
                        res.status = FilterStatus::NonphysicalInput;
                        res.missing =
                            vec![miss(&format!("{name}_{d}.{s}"), "NONPHYSICAL_INPUT", "a fraction in [0, 1]")];
                        return Ok(res);
                    }
                }
                let refl = 1.0 - tau - cap - conv;
                if refl < -CONSERVATION_TOL {
                    res.status = FilterStatus::NonphysicalInput;
                    res.missing = vec![miss(
                        &format!("tau_{d}.{s} + capture_{d}.{s} + conversion_{d}.{s}"),
                        "NONPHYSICAL_INPUT",
                        "sum <= 1 (reflection >= 0)",
                    )];
                    return Ok(res);
                }
                let refl = py_max(refl, 0.0);
                if conv > 0.0 && conversion_products(s).is_none() {
                    return Err(fse(format!("{s}: conversion without a product channel")));
                }
                frs.push(Fr { transmitted: tau, reflected: refl, captured: cap, converted: conv });
            }
            let a = val(&format!("alpha_conductance.{s}"))?;
            if !(0.0 <= a && a <= 1.0) {
                res.status = FilterStatus::NonphysicalInput;
                res.missing =
                    vec![miss(&format!("alpha_conductance.{s}"), "NONPHYSICAL_INPUT", "a probability in [0, 1]")];
                return Ok(res);
            }
            let b = frs.pop().expect("b");
            let f = frs.pop().expect("f");
            let lost_f = f.captured + f.converted;
            let lost_b = b.captured + b.converted;
            if self.kind == "element"
                && self.forward_incidence == "diffuse_thermal"
                && lost_f == 0.0
                && lost_b == 0.0
                && (f.transmitted - b.transmitted).abs() > 1e-9
            {
                res.notes.push(format!(
                    "{s}: tau_f != tau_b for diffuse incidence on a loss-free element; free-molecular reciprocity \
(Livesey 1998 Sec. 2.2: the same transmission probability applies to molecules arriving at either plane of a duct) is \
not satisfied - check the records (unequal face areas or temperatures would have to be documented)"
                ));
            }
            fractions.push((s.clone(), [f, b]));
        }
        let fr_obj = |fr: &Fr| -> Value {
            Obj::new()
                .f("transmitted", fr.transmitted)
                .f("reflected", fr.reflected)
                .f("captured", fr.captured)
                .f("converted", fr.converted)
                .f("lost", fr.captured + fr.converted)
                .f("sum", fr.transmitted + fr.reflected + fr.captured + fr.converted)
                .build()
        };
        let mut produced_down: Vec<(String, f64)> = self.transport.iter().map(|(s, _)| (s.clone(), 0.0)).collect();
        let mut produced_up = produced_down.clone();
        let add = |m: &mut Vec<(String, f64)>, k: &str, x: f64| {
            for (s, v) in m.iter_mut() {
                if s == k {
                    *v += x;
                }
            }
        };
        for (s, [f, b]) in &fractions {
            let mf = sp_get(&inlet.mdot_forward_kgps, s).expect("species");
            let mb = sp_get(&inlet.mdot_back_incident_kgps, s).expect("species");
            let (cmf, cmb) = (mf * f.converted, mb * b.converted);
            if cmf + cmb > 0.0 {
                for (prod, y) in conversion_products(s).ok_or_else(|| key_error(s))? {
                    if !self.transport.iter().any(|(k, _)| k == prod) {
                        res.status = FilterStatus::RefusedTbd;
                        res.missing = vec![miss(
                            &format!("species {prod}"),
                            "TBD",
                            &format!("product {prod} of {s} conversion must be a carried species"),
                        )];
                        return Ok(res);
                    }
                    let pf = val(&format!("product_to_outlet_f.{s}"))?;
                    let pb = val(&format!("product_to_outlet_b.{s}"))?;
                    if !((0.0..=1.0).contains(&pf) && (0.0..=1.0).contains(&pb)) {
                        res.status = FilterStatus::NonphysicalInput;
                        res.missing =
                            vec![miss(&format!("product_to_outlet.{s}"), "NONPHYSICAL_INPUT", "a fraction in [0, 1]")];
                        return Ok(res);
                    }
                    add(&mut produced_down, prod, y * (cmf * pf + cmb * pb));
                    add(&mut produced_up, prod, y * (cmf * (1.0 - pf) + cmb * (1.0 - pb)));
                }
            }
        }
        let mut tot = [0.0f64; 6]; // incident, captured, converted, produced, gross_down, gross_up
        let mut species = vec![];
        for (s, [f, b]) in &fractions {
            let mf = sp_get(&inlet.mdot_forward_kgps, s).expect("species");
            let mb = sp_get(&inlet.mdot_back_incident_kgps, s).expect("species");
            let pd = sp_get(&produced_down, s).expect("species");
            let pu = sp_get(&produced_up, s).expect("species");
            let fwd = [mf * f.transmitted, mf * f.reflected, mf * f.captured, mf * f.converted];
            let bck = [mb * b.transmitted, mb * b.reflected, mb * b.captured, mb * b.converted];
            let gross_down = fwd[0] + bck[1] + pd;
            let gross_up = fwd[1] + bck[0] + pu;
            let net_down = gross_down - mb;
            let ins = mf + mb + pd + pu;
            let outs = gross_down + gross_up + fwd[2] + bck[2] + fwd[3] + bck[3];
            let flows = |x: [f64; 4]| -> Value {
                Obj::new().f("transmitted", x[0]).f("reflected", x[1]).f("captured", x[2]).f("converted", x[3]).build()
            };
            let mut r = Obj::new()
                .f("incident_forward_kgps", mf)
                .f("incident_back_kgps", mb)
                .set("forward", flows(fwd))
                .set("backflow", flows(bck))
                .set("fractions_forward", fr_obj(f))
                .set("fractions_backflow", fr_obj(b))
                .f("produced_to_outlet_kgps", pd)
                .f("produced_to_inlet_kgps", pu)
                .f("gross_downstream_kgps", gross_down)
                .f("gross_upstream_kgps", gross_up)
                .f("net_downstream_kgps", net_down)
                .f("species_balance_residual_kgps", ins - outs);
            if self.kind == "none" {
                r = r
                    .s("conductance_m3_s", "INFINITE_NO_ELEMENT")
                    .f("delta_p_Pa", 0.0)
                    .f("delta_p_per_net_kgps_Pa", 0.0);
            } else {
                let area = val("face_area_m2")?;
                let a = val(&format!("alpha_conductance.{s}"))?;
                let tt = t.expect("checked");
                let c = a * area * mean_speed_m_s(s, tt)? / 4.0;
                r = r.f("conductance_m3_s", c);
                if c > 0.0 {
                    let coef = K_B * tt / (species_mass(s).map_err(|_| key_error(s))? * c);
                    r = r.f("delta_p_per_net_kgps_Pa", coef).f("delta_p_Pa", coef * net_down);
                } else {
                    r = r
                        .s("delta_p_per_net_kgps_Pa", "UNBOUNDED_ZERO_CONDUCTANCE")
                        .s("delta_p_Pa", "UNBOUNDED_ZERO_CONDUCTANCE");
                }
            }
            species.push((s.clone(), r.build(), net_down));
            tot[0] += mf + mb;
            tot[1] += fwd[2] + bck[2];
            tot[2] += fwd[3] + bck[3];
            tot[3] += pd + pu;
            tot[4] += gross_down;
            tot[5] += gross_up;
        }
        let resid = tot[0] - tot[4] - tot[5] - tot[1] - tot[2] + tot[3];
        let cmp = tot[2] - tot[3];
        let scale = py_max(tot[0], 1e-300);
        if resid.abs() > 1e-9 * scale || cmp.abs() > 1e-9 * scale {
            return Err(fse("internal conservation failure"));
        }
        res.totals = vec![
            ("incident_kgps".into(), tot[0]),
            ("captured_kgps".into(), tot[1]),
            ("converted_kgps".into(), tot[2]),
            ("produced_kgps".into(), tot[3]),
            ("gross_downstream_kgps".into(), tot[4]),
            ("gross_upstream_kgps".into(), tot[5]),
            ("mass_balance_residual_kgps".into(), resid),
            ("converted_minus_produced_kgps".into(), cmp),
        ];
        let net: Vec<(String, f64)> = species.iter().map(|(s, _, n)| (s.clone(), *n)).collect();
        res.species = species.into_iter().map(|(s, r, _)| (s, r)).collect();
        if net.iter().all(|(_, v)| *v >= 0.0) && pyops::py_sum(net.iter().map(|(_, v)| *v)) > 0.0 {
            let mt = pyops::py_sum(net.iter().map(|(_, v)| *v));
            let mut nmol = vec![];
            for (s, v) in &net {
                nmol.push((s.clone(), v / species_mass(s).map_err(|_| key_error(s))?));
            }
            let nt = pyops::py_sum(nmol.iter().map(|(_, v)| *v));
            res.composition_net_downstream = Some(
                Obj::new()
                    .set("mass_fraction", crate::rec::fmap(net.iter().map(|(s, v)| (s.as_str(), v / mt))))
                    .set("mole_fraction", crate::rec::fmap(nmol.iter().map(|(s, v)| (s.as_str(), v / nt))))
                    .build(),
            );
        } else {
            res.composition_net_downstream = None;
            res.notes.push(
                "net downstream flow is zero or reversed for at least one species: composition of the net delivered \
flow is not defined (NET_REVERSE_OR_ZERO)"
                    .into(),
            );
        }
        res.mass_kg = Some(val("face_area_m2")? * val("areal_mass_kg_m2")?);
        res.status = if self.kind == "none" { FilterStatus::NoFilterIdentity } else { FilterStatus::Numeric };
        Ok(res)
    }

    /// Linear boundary coefficients for the plenum model (F4): per unit flow arriving at the outlet face.
    pub fn backflow_coupling(&self, t_gas_k: Option<f64>, case: Option<&SensitivityCase>) -> PyResult<Value> {
        let (vals, missing, used) = self.resolve(case)?;
        let mut need: Vec<String> = vec![];
        for (s, _) in &self.transport {
            for k in ["tau_b", "capture_b", "conversion_b", "alpha_conductance"] {
                need.push(format!("{k}.{s}"));
            }
        }
        need.push("face_area_m2".into());
        let mut missv: Vec<Value> =
            missing.into_iter().filter(|m| need.iter().any(|n| Some(n.as_str()) == m["parameter"].as_str())).collect();
        if self.kind == "element" && t_gas_k.is_none() {
            missv.push(miss("T_gas_K", "TBD", "gas temperature at the filter"));
        }
        let label = if case.is_some() { LABEL_SENSITIVITY } else { LABEL_EVIDENCE };
        if !missv.is_empty() {
            return Ok(Obj::new()
                .s("status", "REFUSED_TBD")
                .s("label", label)
                .set("missing", Value::Array(missv))
                .build());
        }
        let val = |k: &str| -> PyResult<f64> { sp_get(&vals, k).ok_or_else(|| key_error(k)) };
        let mut out = Map::new();
        for (s, _) in &self.transport {
            let tau = val(&format!("tau_b.{s}"))?;
            let cap = val(&format!("capture_b.{s}"))?;
            let conv = val(&format!("conversion_b.{s}"))?;
            let refl = 1.0 - tau - cap - conv;
            if py_min(py_min(tau, cap), conv) < 0.0 || refl < -CONSERVATION_TOL {
                return Ok(Obj::new().s("status", "NONPHYSICAL_INPUT").s("label", label).s("species", s).build());
            }
            let c = if self.kind == "none" {
                Value::String("INFINITE_NO_ELEMENT".into())
            } else {
                fnum(
                    val(&format!("alpha_conductance.{s}"))?
                        * val("face_area_m2")?
                        * mean_speed_m_s(s, t_gas_k.expect("checked"))?
                        / 4.0,
                )
            };
            out.insert(
                s.clone(),
                Obj::new()
                    .f("to_upstream", tau)
                    .f("reflected_to_plenum", py_max(refl, 0.0))
                    .f("captured", cap)
                    .f("converted", conv)
                    .set("conductance_m3_s", c)
                    .build(),
            );
        }
        let used_ids: Vec<String> = used.iter().map(|u| u["parameter"].as_str().unwrap_or("").to_string()).collect();
        Ok(Obj::new()
            .s("status", "NUMERIC")
            .s("label", label)
            .set("species", Value::Object(out))
            .set("overrides_used", slist(used_ids))
            .build())
    }

    pub fn to_dict(&self) -> Value {
        let mut params = Map::new();
        for (k, v) in self.parameters() {
            params.insert(k, v.to_dict());
        }
        Obj::new()
            .s("stage_id", &self.stage_id)
            .s("concept_id", &self.concept_id)
            .s("kind", &self.kind)
            .s("role", &self.role)
            .set("interfaces", interface_position())
            .s("forward_incidence", &self.forward_incidence)
            .s("regime", &self.regime)
            .s("description", &self.description)
            .set("parameters", Value::Object(params))
            .set("protection", Value::Array(self.protection.iter().map(|p| p.to_dict()).collect()))
            .set("materials", Value::Array(self.materials.iter().map(|m| m.to_dict()).collect()))
            .build()
    }
}

// ------------------------------------------------------------------------------------------------ placeholders
/// `abep_sim.intake_tpmc.IntakeGeometry` filter defaults: PLACEHOLDER_NOT_A_FLIGHT_DESIGN (recorded, never used
/// silently). (filter, filter_open_frac, filter_transmission, filter_mass_per_m2, area_m2, T_wall_K)
pub const REPOSITORY_PLACEHOLDERS: (bool, f64, f64, f64, f64, f64) = (false, 0.7, 0.6, 0.8, 0.5, 350.0);

pub fn repository_placeholder_values() -> Value {
    let (f, of, tr, mpm, area, tw) = REPOSITORY_PLACEHOLDERS;
    Obj::new()
        .b("filter", f)
        .f("filter_open_frac", of)
        .f("filter_transmission", tr)
        .f("filter_mass_per_m2", mpm)
        .f("area_m2", area)
        .f("T_wall_K", tw)
        .build()
}

/// The repository's present filter law as an explicit, labelled sensitivity case.
pub fn placeholder_sensitivity_case(stage: &FilterStage) -> PyResult<SensitivityCase> {
    let (_, of, tr, mpm, area, tw) = REPOSITORY_PLACEHOLDERS;
    let mut ov: SpMap = vec![("face_area_m2".into(), area), ("areal_mass_kg_m2".into(), mpm)];
    for (s, _) in &stage.transport {
        ov.push((format!("tau_f.{s}"), of * pyops::pow(tr, 0.5)?));
        ov.push((format!("tau_b.{s}"), tr));
        ov.push((format!("alpha_conductance.{s}"), tr));
        for d in DIRECTIONS {
            ov.push((format!("capture_{d}.{s}"), 0.0));
            ov.push((format!("conversion_{d}.{s}"), 0.0));
        }
    }
    let c = SensitivityCase {
        case_id: "SC-PLACEHOLDER-REPO-FILTER".into(),
        label: "PARAMETRIC_SENSITIVITY / PLACEHOLDER_NOT_A_FLIGHT_DESIGN (repository filter defaults)".into(),
        overrides: ov,
        rationale: "reproduces the unsourced repository filter law (abep_sim/intake_tpmc.py IntakeGeometry filter_* \
defaults) so its effect can be bounded; not evidence, not a flight design"
            .into(),
        regime_assumption: Some("free_molecular".into()),
        temperature_override_k: Some(tw),
    };
    c.validate()?;
    Ok(c)
}

/// Propellant mass retained over `duration_s` at the result's capture rate, against the capacity record.
pub fn retained_inventory_kg(result: &FilterResult, duration_s: f64) -> PyResult<Value> {
    if !duration_s.is_finite() || duration_s < 0.0 {
        return Err(fse("duration_s must be finite and >= 0"));
    }
    let rate = result.retained_inventory.get("propellant_capture_rate_kgps").and_then(crate::rec::as_f64);
    let Some(rate) = rate else {
        return Ok(Obj::new().s("status", "NOT_EVALUATED").s("reason", result.status.as_str()).build());
    };
    let cap = result.retained_inventory.get("capacity_kg").cloned().unwrap_or(Value::Object(Map::new()));
    let m = rate * duration_s;
    let capv = cap.get("value").cloned().unwrap_or(Value::Null);
    let margin = match &capv {
        Value::Number(n) => fnum(n.as_f64().unwrap_or(f64::NAN) - m),
        _ => Value::String("NOT_EVALUATED (capacity TBD)".into()),
    };
    Ok(Obj::new()
        .s("status", "EVALUATED_FROM_STAGE_RECORDS")
        .s("label", &result.label)
        .f("retained_kg", m)
        .set("capacity_kg", capv)
        .set("capacity_status", cap.get("status").cloned().unwrap_or(Value::Null))
        .set("capacity_margin_kg", margin)
        .build())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn inlet(species: &[&str], label: &str) -> InletState {
        InletState {
            mdot_forward_kgps: species.iter().map(|s| (s.to_string(), 1e-6)).collect(),
            mdot_back_incident_kgps: species.iter().map(|s| (s.to_string(), 2e-7)).collect(),
            back_incident_basis: "test".into(),
            t_gas_k: Some(350.0),
            incidence: "diffuse_thermal".into(),
            knudsen_number: Some(5.0),
            label: label.into(),
            provenance: "test".into(),
            incident_power_w: None,
            incident_power_source: String::new(),
        }
    }

    #[test]
    fn cole_table_points_are_exact_and_domain_refuses() {
        for (x, y) in COLE_TABLE_2_5 {
            assert_eq!(cole_transmission_probability(x).unwrap().value, Some(y));
        }
        assert!(cole_transmission_probability(0.04).is_err());
        assert!(cole_transmission_probability(f64::NAN).is_err());
        let v = cole_transmission_probability(7.0).unwrap().value.unwrap();
        assert!(v < 0.190941 && v > 0.109304);
    }

    #[test]
    fn all_tbd_stage_refuses_with_incomplete_evidence() {
        let st = FilterStage::tbd("S", "C", &["O", "N2", "O2"], "diffuse_thermal", "", vec![], vec![], ROLE_BASELINE)
            .unwrap();
        let r = st.apply(&inlet(&["O", "N2", "O2"], "EVIDENCE"), None).unwrap();
        assert_eq!(r.status, FilterStatus::RefusedTbd);
        assert_eq!(r.status.eval_status(), EvalStatus::IncompleteEvidence);
        assert!(!r.missing.is_empty());
        assert!(!r.admissible_as_baseline);
        assert_eq!(r.species_transmission()["status"], "NOT_EVALUATED");
    }

    #[test]
    fn none_stage_is_identity_and_conserves_mass() {
        let st = FilterStage::none(&["O", "N2", "O2"]);
        st.validate().unwrap();
        let r = st.apply(&inlet(&["O", "N2", "O2"], "EVIDENCE"), None).unwrap();
        assert_eq!(r.status, FilterStatus::NoFilterIdentity);
        assert_eq!(r.status.eval_status(), EvalStatus::Evaluated);
        let inc = r.total("incident_kgps").unwrap();
        assert!(r.total("mass_balance_residual_kgps").unwrap().abs() <= 1e-12 * inc, "CONS-F-01");
        assert_eq!(r.species_f64("O", &["gross_downstream_kgps"]), Some(1e-6 + 2e-7 * 0.0 + 0.0));
        assert_eq!(r.species_f64("O", &["conductance_m3_s"]), None, "INFINITE_NO_ELEMENT is a string sentinel");
    }

    #[test]
    fn status_mapping_is_registered() {
        assert_eq!(FilterStatus::OutOfDomain.eval_status(), EvalStatus::OutOfDomain);
        assert_eq!(FilterStatus::NonphysicalInput.eval_status(), EvalStatus::OutOfDomain);
        for s in RESULT_STATUSES {
            for w in ["PASS", "SELECTED", "WINNER", "QUALIFIED"] {
                assert!(!s.contains(w));
            }
        }
    }

    #[test]
    fn placeholder_case_is_labelled_and_conserves() {
        let st = FilterStage::tbd("S", "C", &["O", "N2", "O2"], "diffuse_thermal", "", vec![], vec![], ROLE_BASELINE)
            .unwrap();
        let c = placeholder_sensitivity_case(&st).unwrap();
        let r = st.apply(&inlet(&["O", "N2", "O2"], "EVIDENCE"), Some(&c)).unwrap();
        assert_eq!(r.status, FilterStatus::Numeric);
        assert_eq!(r.label, LABEL_SENSITIVITY);
        let inc = r.total("incident_kgps").unwrap();
        assert!(r.total("mass_balance_residual_kgps").unwrap().abs() <= 1e-12 * inc);
        for (s, _) in &r.species {
            assert!(r.species_f64(s, &["species_balance_residual_kgps"]).unwrap().abs() <= 1e-12 * inc);
        }
    }
}
