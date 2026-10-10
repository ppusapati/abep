//! `abep-config build [--check]`: the authoritative input manifests under `config/`, reproduced byte for byte (port
//! of `scripts/config/build_config.py`; contract `C-ABEP_SIM_CONFIGURATION_PY` v1, W13 criterion).
//!
//! Every file is derived from the existing sources of record; no number is invented and no source is edited. The
//! frozen operating scenarios are verified against their pins and listed as they are, never generated (A9.24
//! item 4). JSON is written with the Python-compatible writer `abep_types::pyjson` (indent 1, ensure_ascii False).

use crate::builder_readme::README;
use crate::loaders::{display, is_file, read_bytes};
use crate::py::{self, get, index, is_str, or_empty};
use crate::pysrc::version_labels;
use crate::textmatch::{lit, plus, search, space, star, Node};
use crate::{ConfigError, ConfigResult, ScenarioPin};
use abep_types::pydict;
use abep_types::pyjson::{self, py_eq, py_repr, py_str, read_text_utf8, Dict, DumpOptions, PyInt, Value};
use std::path::{Path, PathBuf};

pub const GENERATED_BY: &str = "scripts/config/build_config.py";
pub const REGENERATE: &str = "python scripts/config/build_config.py  (check: --check)";

pub const RVM_REL: &str = "docs/requirements/rvm_a9/rvm_a9_v1.json";
pub const REG_REL: &str = "docs/requirements/rfp_official/rfp_registration_v1.json";
const A922_MD: &str = "docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md";
const A922_JSON: &str = "docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json";
const A923_MD: &str = "docs/decisions/OD_2026_10_03_A9_23_SIMULATION_ARCHITECTURE_OWNER_DIRECTIVE.md";
const A923_JSON: &str = "docs/decisions/OD_2026_10_03_A9_23_simulation_architecture_owner_directive.json";
const A924_MD: &str = "docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md";
const A924_JSON: &str = "docs/decisions/OD_2026_10_04_A9_24_rust_migration_and_open_items_owner_decisions.json";
pub const A9_REL: &str = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json";

pub const ARCH_FILE: &str = "architecture/hall_icp_neutralizer_v1.json";
pub const REQ_FILE: &str = "requirements/rfp_constraints_v1.json";
pub const CONSTRAINTS_FILE: &str = "constraints/engineering_constraints_v1.json";
pub const MISSION_FILE: &str = "mission/mission_scenario_v2.json";
pub const MISSION_V1_FILE: &str = "mission/mission_scenario_v1.json";
pub const MISSION_V1_SHA256: &str = "a01b56a6ec7a79cb3b37c6356542d093c618632388edefb150881bf03fbe7ba0";
pub const GATES_FILE: &str = "assessment/gate_thresholds_v1.json";
pub const DS_REF_FILE: &str = "environment/design_state_set_ref_v1.json";
pub const HW_FILE: &str = "hardware/hardware_bounds_v1.json";
pub const MODEL_SET_FILE: &str = "model_set/physics_model_set_v1.json";
pub const SOT_FILE: &str = "SOURCES_OF_TRUTH.json";

/// An owner decision record the architecture is generated from (immutable; a changed record is refused).
pub struct Decision {
    pub key: &'static str,
    pub md: &'static str,
    pub md_sha256: &'static str,
    pub json: &'static str,
    pub json_sha256: &'static str,
    pub decision_code: &'static str,
}

pub const DECISIONS: [Decision; 3] = [
    Decision {
        key: "A9.19",
        md: "docs/decisions/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md",
        md_sha256: "d3eae1d65f9b679a8538ce4a7c701a40a3f5d3b07d72baae944b685256931749",
        json: "docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
        json_sha256: "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
        decision_code: "A9_19_SINGLE_HALL_ICP_NEUTRALIZER_NO_HOLLOW_CATHODE_XE_CONTINGENCY",
    },
    Decision {
        key: "A9.20",
        md: "docs/decisions/OD_2026_10_01_A9_20_C1_GROUND_ONLY_OWNER_DECISION.md",
        md_sha256: "2b90a7a7f851ac571791ea6ba2fbafac8cf69a086a4a3724e2f66196b6b4d60c",
        json: "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
        json_sha256: "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
        decision_code: "C1_GROUND_ONLY_LABORATORY_REFERENCE",
    },
    Decision {
        key: "A9.15",
        md: "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
        md_sha256: "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903",
        json: "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
        json_sha256: "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
        decision_code: "A9_15_RFP_COMPLIANT_PROPELLANT_POLICY",
    },
];

pub const VERBATIM_A9_19: [&str; 4] = [
    "One Hall accelerator.",
    "One RF/ICP electron-source/neutralizer.",
    "Two propellant supply modes.",
    "No conventional hollow cathode.",
];

pub const SNAPSHOT_RVM_SHA256: &str = "6d7d02beba5498b839497ee6824b15f850738aef40d3a6190ad09cf115006264";
pub const ACCEPTED_RVM_BASIS_SHA256: &str = "1d4a7f0099e937f0c74a8c1be8fc14408b75f211c7990be4672f4eee5f9b66b5";
const BASIS_ROW_FIELDS: [&str; 9] = [
    "id",
    "title",
    "category",
    "requirement_text",
    "requirement_basis",
    "requirement_origin",
    "rfp_clauses",
    "related_rfp_clauses",
    "limit",
];
const BASIS_REBASE_FIELDS: [&str; 4] = ["registration", "clause_coverage", "not_system_requirements", "discrepancies"];

pub const G1_STATUS: &str = "APPLIED";
pub const HISTORICAL_LABEL: &str = "HISTORICAL_CONSTANT_NOT_CONSUMED";

pub const DS_REL: &str = "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json";
pub const DS_MANIFEST_REL: &str = "abep_sim/data/atmosphere_msis21_orbit_v1.json";

/// (id, kind, path, locator, role) of the hardware-limit sources (index only; no value is copied).
pub const HW_ENTRIES: [(&str, &str, &str, &str, &str); 7] = [
    (
        "h1_freeze_candidate",
        "hardware_freeze_candidate",
        "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
        "parameters[*] / freeze_points / consistency_checks",
        "H-1 Hall accelerator freeze-candidate parameter set",
    ),
    (
        "rotor_strength_registry",
        "rotor_strength_registry",
        "abep_sim/rotor_strength.py",
        "REGISTRY (empty: no registered basis) / REFERENCE_RECORDS",
        "registered rotor-strength bases (A9.9 S2.3)",
    ),
    (
        "materials_db",
        "materials_database",
        "abep_sim/materials.py",
        "DB (Material.yield_MPa, T_max_K, ...; literature-class priors with fidelity tags)",
        "materials database",
    ),
    (
        "thermal_life_limits",
        "thermal_node_limits",
        "schemas/thermal_life/limits_v1.json",
        "records[*] (sourced / TBD limits)",
        "sourced thermal / life limits",
    ),
    (
        "thermal_node_model",
        "thermal_node_limits",
        "abep_sim/thermal.py",
        "Node.T_max_K; ThermalParams.radiator_T_max_K",
        "thermal-node limit fields of the 0-D thermal model",
    ),
    (
        "h2_5_thermal_network",
        "thermal_node_limits",
        "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json",
        "limits[*] / node_list",
        "H2-5 thermal-network node limits",
    ),
    (
        "compressor_legacy_caps",
        "compressor_legacy_caps",
        "abep_sim/compressor.py",
        "DragCompressor.stress_safety; DragCompressor.u_max_legacy_sensitivity(); size_for(rpm_max=...)",
        "LEGACY_CONSERVATIVE_SENSITIVITY tip-speed / rpm caps (not a qualification basis)",
    ),
];

pub const DATA_FILES: [&str; 15] = [
    "abep_sim/data/golden_v2.json",
    "abep_sim/data/golden_v1.json",
    "abep_sim/data/intake_surface_v1.json",
    "abep_sim/data/intake_surface_v1.csv",
    "abep_sim/data/atmosphere_msis21_v1.json",
    "abep_sim/data/atmosphere_msis21_v1.csv",
    "abep_sim/data/atmosphere_msis21_orbit_v1.json",
    "abep_sim/data/atmosphere_msis21_orbit_v1.csv.gz",
    "abep_sim/data/atmosphere_msis21_orbit_v1_design_states.json",
    DS_REL,
    "abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.json",
    "abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.csv.gz",
    "abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.disturbance.csv.gz",
    "hallthruster_bridge/PINNED.toml",
    "hallthruster_bridge/propellants/rate_validity.toml",
];

pub const RESULT_SCHEMA_RAW: &str = "schemas/results/raw_closure_v2.json";
pub const RESULT_SCHEMA_ASSESSMENT: &str = "schemas/results/closure_assessment_v2.json";

fn bad(msg: impl Into<String>) -> ConfigError {
    ConfigError::build(msg)
}

fn s(x: &str) -> Value {
    Value::str(x)
}

fn strs(xs: &[&str]) -> Value {
    Value::List(xs.iter().map(|x| s(x)).collect())
}

fn merge(into: &mut Dict, from: &Value) -> ConfigResult<()> {
    for (k, v) in py::items(from)?.iter() {
        into.insert(k.as_str(), v.clone());
    }
    Ok(())
}

fn dict(v: Value) -> Dict {
    match v {
        Value::Dict(d) => d,
        _ => unreachable!("pydict! builds a dict"),
    }
}

/// `v.get(key, default)`.
fn get_or<'a>(v: &'a Value, key: &str, default: &'a Value) -> ConfigResult<&'a Value> {
    match v {
        Value::Dict(d) => Ok(d.get(key).unwrap_or(default)),
        _ => py::get(v, key),
    }
}

/// `list(v)`.
fn py_list(v: &Value) -> ConfigResult<Value> {
    Ok(Value::List(py::iterate(v)?))
}

/// `_num(v)`.
fn num(v: &Value) -> ConfigResult<Value> {
    if !v.is_number() {
        return Err(bad(format!("expected a number, got {}", py_repr(v))));
    }
    Ok(v.clone())
}

/// `v / 100` (Python true division of an int or float).
fn div100(v: &Value) -> ConfigResult<Value> {
    match v {
        Value::Int(i) => {
            let t = i.to_string();
            let (neg, digits) = match t.strip_prefix('-') {
                Some(d) => ("-", d),
                None => ("", t.as_str()),
            };
            let padded = format!("{digits:0>3}");
            let (ip, fp) = padded.split_at(padded.len() - 2);
            let f: f64 = format!("{neg}{ip}.{fp}").parse().map_err(|_| bad("division"))?;
            if f.is_infinite() {
                return Err(ConfigError::new("OverflowError", "integer division result too large for a float"));
            }
            Ok(Value::Float(f))
        }
        Value::Float(f) => Ok(Value::Float(f / 100.0)),
        Value::Bool(b) => Ok(Value::Float(if *b { 0.01 } else { 0.0 })),
        other => Err(py::type_error(format!("unsupported operand type(s) for /: '{}' and 'int'", other.type_name()))),
    }
}

/// `int(digits)` of a regex capture (ASCII decimal digits; contract DIV-03).
fn int_of(digits: &str) -> ConfigResult<Value> {
    if !digits.chars().all(|c| c.is_ascii_digit()) {
        return Err(ConfigError::new("ValueError", "non-ASCII decimal digit in a clause capture (DIV-03)"));
    }
    Ok(Value::Int(PyInt::parse(digits).expect("ascii digits")))
}

fn is_digit_char(c: char) -> bool {
    c.is_numeric()
}

/// `re.search(prefix + r"<sep>(\d+)\s*" + suffix, text).group(1)`; `sep` = `\s+` or `\s*>`.
fn capture_digits(text: &str, prefix: &str, sep_gt: bool, suffix: &str) -> Option<String> {
    let mut p: Vec<Node> = lit(prefix);
    if sep_gt {
        p.push(star(space()));
        p.push(Node::Char('>'));
    } else {
        p.push(plus(space()));
    }
    p.push(plus(Node::Class(is_digit_char)));
    p.push(star(space()));
    p.extend(lit(suffix));
    let t: Vec<char> = text.chars().collect();
    let (start, end) = search(&p, &t, 0)?;
    let mut i = start + prefix.chars().count();
    while i < end && !is_digit_char(t[i]) {
        i += 1;
    }
    let j = (i..end).find(|&j| !is_digit_char(t[j])).unwrap_or(end);
    Some(t[i..j].iter().collect())
}

/// The config builder over a repository tree (`<root>/config` is the configuration root it checks).
pub struct Builder {
    pub root: PathBuf,
    pub config: PathBuf,
    pub scenario_pin: ScenarioPin,
}

/// Result of `--check`: the exit status and the printed line.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CheckOutcome {
    pub exit: i32,
    pub line: String,
}

impl Builder {
    pub fn new(root: &Path) -> Self {
        Builder {
            root: root.to_path_buf(),
            config: root.join("config"),
            scenario_pin: ScenarioPin::mission_scenario_v2(),
        }
    }

    fn sha256_file(&self, rel: &str) -> ConfigResult<String> {
        let p = self.root.join(rel);
        if !is_file(&p) {
            return Err(bad(format!("source {rel} missing")));
        }
        Ok(abep_provenance::sha256_hex(&read_bytes(&p)?))
    }

    fn read_text(&self, rel: &str) -> ConfigResult<String> {
        Ok(read_text_utf8(&read_bytes(&self.root.join(rel))?)?)
    }

    fn read_json(&self, rel: &str) -> ConfigResult<Value> {
        Ok(pyjson::loads(&self.read_text(rel)?)?)
    }

    fn decision_ref(&self, rel_json: &str, rel_md: &str) -> ConfigResult<Value> {
        let mut r = dict(pydict! { "json" => rel_json, "json_sha256" => self.sha256_file(rel_json)? });
        r.insert("md", s(rel_md));
        r.insert("md_sha256", s(&self.sha256_file(rel_md)?));
        Ok(Value::Dict(r))
    }

    // ====================================================================================================== architecture
    pub fn build_architecture(&self) -> ConfigResult<Value> {
        for d in &DECISIONS {
            if self.sha256_file(d.json)? != d.json_sha256 || self.sha256_file(d.md)? != d.md_sha256 {
                return Err(bad(format!("owner decision record {} changed; refused (records are immutable)", d.key)));
            }
            if !is_str(get(&self.read_json(d.json)?, "decision")?, d.decision_code) {
                return Err(bad(format!(
                    "owner decision record {}: decision code differs from {}",
                    d.key, d.decision_code
                )));
            }
        }
        let md19 = self.read_text(DECISIONS[0].md)?;
        let missing: Vec<Value> = VERBATIM_A9_19.iter().filter(|v| !md19.contains(**v)).map(|v| s(v)).collect();
        if !missing.is_empty() {
            return Err(bad(format!(
                "A9.19 verbatim sentences not found in the record: {}",
                py_repr(&Value::List(missing))
            )));
        }
        let j19doc = self.read_json(DECISIONS[0].json)?;
        let j19 = index(&j19doc, "architecture")?;
        let empty_s = s("");
        let empty_l = Value::List(vec![]);
        let differs = !py_eq(get(j19, "hall_accelerators")?, &Value::int(1))
            || !py_str(get_or(j19, "conventional_hollow_cathode", &empty_s)?).starts_with("NONE")
            || py::len(get_or(j19, "propellant_supply_modes", &empty_l)?)? != 2
            || !py::contains_str(get_or(j19, "electron_source_neutralizer", &empty_s)?, "RF/ICP")?;
        if differs {
            return Err(bad("A9.19 record architecture block differs from the definition carried here"));
        }
        let a9 = self.read_json(A9_REL)?;

        let flight = "hall_icp_neutralizer";
        let (air, xe) = ("AIR_PRIMARY", "XE_CONTINGENCY");
        let c1_role = pydict! {
            "status" => "GROUND_ONLY_LAB_EQUIPMENT",
            "uses" => strs(&["H-1 I_d,max,H1,Ar characterization (A9.10 S3.5, independent of the ICP)",
                             "bench control in the C1-vs-ICP comparison"]),
            "never" => strs(&["flight hardware", "flight mass budget", "flight power budget", "flight Xe budget",
                              "flight fallback / candidate flight configuration"]),
            "authority" => "A9.20 (C1_GROUND_ONLY_LABORATORY_REFERENCE); A9.19 amends 'A9 C1 CONTROL_FALLBACK'",
        };
        let icp_feed = pydict! {
            "primary" => "G-REUSE",
            "declared_variant" => "G-XE",
            "status" => "UNCHANGED (A9.1; A9.19 does not alter the ICP feed-gas baseline)",
        };
        let flight_architecture = pydict! {
            "configuration" => flight,
            "hall_accelerators" => 1i64,
            "electron_source_neutralizer" => pydict! {
                "count" => 1i64,
                "kind" => "RF/ICP (13.56 MHz) electron source / neutralizer, cathodeless / electrodeless",
                "serves_supply_modes" => strs(&[air, xe]),
            },
            "supply_modes" => Value::List(vec![
                pydict! {
                    "mode" => air, "role" => "PRIMARY", "propellant" => "ambient atmospheric propellant (180-230 km)",
                    "path" => strs(&["intake", "filter", "compressor", "atmospheric_gas_chamber", "valve"]),
                },
                pydict! {
                    "mode" => xe, "role" => "CONTINGENCY_EMERGENCY", "propellant" => "xenon",
                    "path" => strs(&["xe_tank", "valve"]),
                    "note" => concat!(
                        "capability required by the RFP (RFP-P17-05 extra input system; RFP-P18-08 separate tank); role ",
                        "contingency / emergency, not a parallel co-equal propellant (A9.19)"
                    ),
                },
            ]),
            "separate_tanks" => true,
            "conventional_hollow_cathode" => "NONE",
            "icp_feed_gas_baseline" => icp_feed.clone(),
            "c1" => c1_role.clone(),
            "verbatim" => strs(&VERBATIM_A9_19),
            "status" => "OWNER_DECIDED_ARCHITECTURE_DEFINITION (A9 investigation; not a flight baseline, not a PASS)",
        };
        let mut decision_records = Dict::new();
        for d in &DECISIONS {
            decision_records.insert(
                d.key,
                pydict! {
                    "md" => d.md, "md_sha256" => d.md_sha256, "json" => d.json, "json_sha256" => d.json_sha256,
                    "decision_code" => d.decision_code,
                },
            );
        }
        let gases = pydict! {
            air => strs(&["N2", "NITROGEN", "O2", "OXYGEN", "O", "AIR", "N2/O2", "N2+O2", "N2_O2", "AMBIENT_AIR",
                          "ATMOSPHERIC"]),
            xe => strs(&["XE", "XENON"]),
        };
        Ok(pydict! {
            "schema" => "abep_config_architecture_v1",
            "id" => "hall_icp_neutralizer_v1",
            "layer" => "FROZEN_ENGINEERING_CONFIGURATION",
            "title" => concat!(
                "A9.19 / A9.20 / A9.15 flight architecture: one Hall accelerator + one RF/ICP electron source / ",
                "neutralizer; ambient air PRIMARY, Xe CONTINGENCY_EMERGENCY; separate tanks / paths; no conventional ",
                "hollow cathode; C1 ground-only laboratory reference"
            ),
            "status" => "INVESTIGATION_HYPOTHESIS",
            "status_rule" => concat!(
                "the architecture is an owner-decided definition of an investigation hypothesis; this file never ",
                "promotes it (not a flight baseline, not PASS / SELECTED / WINNER / QUALIFIED)"
            ),
            "a9_status" => get(&a9, "status")?.clone(),
            "generated_by" => GENERATED_BY,
            "regenerate" => REGENERATE,
            "loader" => "abep_sim/design/a9_19_architecture.py (module constants load from this file; values unchanged)",
            "decision_records" => decision_records,
            "governing_directive_a9_22" => self.decision_ref(A922_JSON, A922_MD)?,
            "a9_record" => pydict! { "path" => A9_REL, "sha256" => self.sha256_file(A9_REL)? },
            "rfp_registration" => REG_REL,
            "rfp_clauses" => pydict! { "xe_extra_input" => "RFP-P17-05", "two_tanks" => "RFP-P18-08" },
            "verbatim_a9_19" => strs(&VERBATIM_A9_19),
            "constants" => pydict! {
                "flight_configuration" => flight,
                "flight_configurations" => strs(&[flight]),
                "ground_reference_configuration" => "hall_c1_reference",
                "ground_reference_label" => "GROUND_REFERENCE",
                "ground_only_lab_equipment" => "GROUND_ONLY_LAB_EQUIPMENT",
                "c1_role" => c1_role,
                "supply_mode_air" => air,
                "supply_mode_xe" => xe,
                "supply_modes" => strs(&[air, xe]),
                "xe_path_role" => "CONTINGENCY_EMERGENCY",
                "air_path_role" => "PRIMARY",
                "supply_mode_gases" => gases,
                "bench_engineering_gas" => strs(&["AR", "ARGON"]),
                "bench_supply_mode" => "BENCH_AR_ENGINEERING_GROUND_ONLY",
                "icp_feed_gas_baseline" => icp_feed,
                "flight_architecture" => flight_architecture,
            },
        })
    }

    // ====================================================================================================== requirements
    /// `rvm_requirements_basis_sha256(rvm)`: the A9.22 G3 requirements-basis hash.
    pub fn rvm_requirements_basis_sha256(rvm: &Value) -> ConfigResult<String> {
        let rows = py::iterate(index(rvm, "rows")?)?;
        let mut clause_rows = Vec::new();
        for r in &rows {
            if is_str(get(r, "requirement_origin")?, "RFP_CLAUSE") {
                let mut e = Dict::new();
                for f in BASIS_ROW_FIELDS {
                    e.insert(f, get(r, f)?.clone());
                }
                clause_rows.push(Value::Dict(e));
            }
        }
        let mut origins = Dict::new();
        for r in &rows {
            let id = index(r, "id")?;
            let Value::Str(id) = id else {
                return Err(py::type_error("row id is not a str (not representable as a sorted JSON key)"));
            };
            origins.insert(id.as_str(), get(r, "requirement_origin")?.clone());
        }
        let mut out = dict(pydict! { "rfp_clause_rows" => Value::List(clause_rows), "row_origins" => origins });
        let rebase = index(rvm, "rfp_rebase")?;
        for k in BASIS_REBASE_FIELDS {
            out.insert(k, get(rebase, k)?.clone());
        }
        let text = pyjson::dumps(&Value::Dict(out), &DumpOptions::canonical_hash())?;
        Ok(abep_provenance::sha256_hex(text.as_bytes()))
    }

    pub fn build_requirements(&self) -> ConfigResult<Value> {
        let rvm = self.read_json(RVM_REL)?;
        let reg = self.read_json(REG_REL)?;
        let row_list = py::iterate(index(&rvm, "rows")?)?;
        let mut rows = Dict::new();
        for r in &row_list {
            let id = index(r, "id")?;
            if let Value::Str(k) = id {
                rows.insert(k.as_str(), r.clone());
            }
        }
        let clauses = index(&reg, "clauses")?;
        let clauses_sha =
            abep_provenance::sha256_hex(pyjson::dumps(clauses, &DumpOptions::canonical_hash())?.as_bytes());
        let basis = Self::rvm_requirements_basis_sha256(&rvm)?;
        let accepted = index(
            index(index(index(&rvm, "rfp_rebase")?, "ag15_closure")?, "accepted_rvm")?,
            "requirements_basis_sha256",
        )?;
        let rvm_pin = if is_str(accepted, &basis) && basis == ACCEPTED_RVM_BASIS_SHA256 {
            SNAPSHOT_RVM_SHA256.to_string()
        } else {
            self.sha256_file(RVM_REL)?
        };
        let rb = index(index(&rvm, "rfp_rebase")?, "registration")?;
        if !is_str(index(rb, "clauses_sha256")?, &clauses_sha) {
            return Err(bad("RVM rfp_rebase clauses_sha256 differs from the registration clauses"));
        }
        let row = |rid: &str, key_prefix: &str| -> ConfigResult<Value> {
            match rows.get(rid) {
                Some(r) if py::startswith(index(r, "key")?, key_prefix)? => Ok(r.clone()),
                _ => Err(bad(format!(
                    "RVM {rid} missing or its key does not start with {}",
                    abep_types::pyjson::py_repr_str(key_prefix)
                ))),
            }
        };
        let ref_ = |r: &Value| -> ConfigResult<Dict> {
            let frozen = get(r, "requirement_frozen")?.truthy();
            Ok(dict(pydict! {
                "rvm_row" => index(r, "id")?.clone(),
                "rvm_key" => index(r, "key")?.clone(),
                "rfp_clauses" => py_list(or_empty_list(get(r, "rfp_clauses")?))?,
                "requirement_origin" => get(r, "requirement_origin")?.clone(),
                "requirement_frozen" => frozen,
                "status" => if frozen { "FROZEN" } else { "PROVISIONAL" },
            }))
        };
        let lim = |r: &Value| -> ConfigResult<Value> {
            let l = get(r, "limit")?;
            if !l.truthy() {
                return Err(bad(format!("RVM {} has no limit", py_str(index(r, "id")?))));
            }
            Ok(pydict! {
                "quantity" => index(l, "quantity")?.clone(),
                "comparator" => index(l, "comparator")?.clone(),
                "value" => index(l, "value")?.clone(),
                "units" => index(l, "units")?.clone(),
            })
        };
        let (alt, tmin, tmax) =
            (row("RVM-01", "ALTITUDE")?, row("RVM-02", "THRUST_12MN")?, row("RVM-03", "THRUST_25MN")?);
        let (pbus, mass) = (row("RVM-04", "PBUS")?, row("RVM-06", "MASS_LT_40KG")?);
        let (hall, firing) = (row("RVM-11", "HALL_PREF")?, row("RVM-12", "FIRING")?);
        let (life, ic) = (row("RVM-13", "MISSION_LIFE")?, row("RVM-18", "INDIGENOUS")?);

        let alt_values = py::iterate(index(&lim(&alt)?, "value")?)?;
        let mut pairv = Vec::new();
        for x in alt_values.iter().take(3) {
            pairv.push(num(x)?);
        }
        if pairv.len() != 2 {
            return Err(ConfigError::new("ValueError", "wrong number of values to unpack (expected 2)"));
        }
        let (lo, hi) = (pairv[0].clone(), pairv[1].clone());

        let clause = |cid: &str| -> ConfigResult<Value> {
            for c in py::iterate(index(&reg, "clauses")?)? {
                if is_str(index(&c, "id")?, cid) {
                    return Ok(c);
                }
            }
            Err(bad(format!("clause {cid} not in the RFP registration")))
        };
        let text_of = |c: &Value| -> ConfigResult<String> {
            match index(c, "text")? {
                Value::Str(t) => Ok(t.clone()),
                _ => Err(py::type_error("expected string or bytes-like object")),
            }
        };
        let c_life = clause("RFP-P19-01")?;
        let life_text = text_of(&c_life)?;
        let m_legacy = capture_digits(&life_text, "Approx", false, "hrs");
        let m_ign = capture_digits(&life_text, "More than", false, "hrs");
        let (Some(m_legacy), Some(m_ign)) = (m_legacy, m_ign) else {
            return Err(bad("RFP-P19-01 text no longer carries the printed mission / ignition hours"));
        };
        let legacy_mission_h = int_of(&m_legacy)?;
        let ign = int_of(&m_ign)?;
        if !py_eq(&ign, &num(index(&lim(&firing)?, "value")?)?) {
            return Err(bad("RVM-12 firing limit differs from RFP-P19-01"));
        }
        let c_ic = clause("RFP-P19-05")?;
        let ic_text = text_of(&c_ic)?;
        let mut ic_sub = Dict::new();
        for (k, prefix) in [
            ("thruster", "Space Qualified Thruster"),
            ("intake", "Intake system"),
            ("compressor", "Compressor and Storage"),
            ("pse", "Power Supply Electronics"),
        ] {
            let Some(m) = capture_digits(&ic_text, prefix, true, "%") else {
                return Err(bad(format!("RFP-P19-05: subsystem minimum {k} not found")));
            };
            ic_sub.insert(k, div100(&int_of(&m)?)?);
        }
        if !is_str(index(&lim(&ic)?, "units")?, "%") {
            return Err(bad("RVM-18 limit is not in %"));
        }
        let c_hall = clause("RFP-P18-07")?;
        if !text_of(&c_hall)?.to_lowercase().contains("preferable") {
            return Err(bad("RFP-P18-07 no longer states a Hall preference"));
        }
        let used = [&alt, &tmin, &tmax, &pbus, &mass, &hall, &firing, &life, &ic];
        let mut n_frozen = 0;
        for r in used {
            if get(r, "requirement_frozen")?.truthy() {
                n_frozen += 1;
            }
        }
        let status = if n_frozen == used.len() { "FROZEN" } else { "PROVISIONAL" };
        let mut rfp_rows = Vec::new();
        for r in &row_list {
            if is_str(get(r, "requirement_origin")?, "RFP_CLAUSE") {
                rfp_rows.push(r.clone());
            }
        }
        let c = |value: Value, r: &Value, note: Option<&str>, kw: Vec<(&str, Value)>| -> ConfigResult<Value> {
            let mut e = Dict::new();
            e.insert("value", value);
            merge(&mut e, &Value::Dict(ref_(r)?))?;
            for (k, v) in kw {
                e.insert(k, v);
            }
            if let Some(n) = note {
                e.insert("note", s(n));
            }
            Ok(Value::Dict(e))
        };
        let lim_value = |r: &Value| -> ConfigResult<Value> { num(index(&lim(r)?, "value")?) };
        let mut compat = Dict::new();
        compat.insert("thrust_min_mN", c(lim_value(&tmin)?, &tmin, None, vec![])?);
        compat.insert(
            "thrust_max_mN",
            c(
                lim_value(&tmax)?,
                &tmax,
                Some(concat!(
                    "upper end of the printed thrust band RFP-P18-06 ",
                    "'12 mN to 25 mN'; RVM-03 carries it as the >= 25 mN capability requirement"
                )),
                vec![],
            )?,
        );
        compat.insert("power_max_W", c(lim_value(&pbus)?, &pbus, None, vec![])?);
        compat.insert("mass_max_kg", c(lim_value(&mass)?, &mass, None, vec![])?);
        compat.insert("alt_min_km", c(lo.clone(), &alt, None, vec![])?);
        compat.insert("alt_max_km", c(hi.clone(), &alt, None, vec![])?);
        compat.insert(
            "ignition_hours",
            c(lim_value(&firing)?, &firing, None, vec![("label", s("SUBSYSTEM_FIRING_LIFE_ASSUMPTION"))])?,
        );
        compat.insert(
            "mission_hours",
            c(
                legacy_mission_h.clone(),
                &life,
                Some(concat!(
                    "HISTORICAL value (RFP-P19-01 prints 'Approx 26000 hrs'), carried ",
                    "only so the abep_sim.constants.RFP compatibility record (immutable, sha-pinned) stays ",
                    "field-for-field identical; no consumer computes with it since the A9.22 G1 governed ",
                    "migration was applied. The mission-duration basis is mission_duration.authoritative_basis_h ",
                    "(26,280 h), consumed through config/mission/mission_scenario_v1.json"
                )),
                vec![
                    ("label", s(HISTORICAL_LABEL)),
                    ("authoritative_basis_h", lim_value(&life)?),
                    ("g1_status", s(G1_STATUS)),
                ],
            )?,
        );
        compat.insert(
            "ic_total_min",
            c(div100(&lim_value(&ic)?)?, &ic, None, vec![("layer_target", s("ASSESSMENT (A9.22 G6)"))])?,
        );
        compat.insert(
            "ic_subsystem_min",
            c(
                Value::Dict(ic_sub),
                &ic,
                Some(concat!(
                    "RFP-P19-05 'Minimum Indigenization Desired' subsystem minima, read from ",
                    "the registered clause text (printed as '>'; carried as the legacy minimum)"
                )),
                vec![("layer_target", s("ASSESSMENT (A9.22 G6)")), ("clause_text_source", s("RFP-P19-05"))],
            )?,
        );
        compat.insert(
            "hall_preferred",
            c(
                Value::Bool(true),
                &hall,
                Some("RFP-P18-07 'Hall effect preferable' (a preference flag, not a numeric limit)"),
                vec![("layer_target", s("ASSESSMENT (A9.22 G6)")), ("clause_text_source", s("RFP-P18-07"))],
            )?,
        );

        let mut rfp_frozen = 0;
        for r in &rfp_rows {
            if get(r, "requirement_frozen")?.truthy() {
                rfp_frozen += 1;
            }
        }
        let mut out = dict(pydict! {
            "schema" => "abep_config_requirements_snapshot_v1",
            "id" => "rfp_constraints_v1",
            "layer" => "REQUIREMENTS",
            "title" => "RFP-derived requirements snapshot generated from the RVM limit fields",
            "snapshot_status" => status,
            "snapshot_status_rule" => concat!(
                "FROZEN only when every RVM row this snapshot draws a value from has requirement_frozen ",
                "= true in the pinned RVM; otherwise PROVISIONAL (derived at build time, never ",
                "hard-coded). FROZEN freezes the requirements basis only; it never means compliance ",
                "(A9.22 G3)."
            ),
            "rows_used_frozen" => format!("{n_frozen}/{}", used.len()),
            "rfp_clause_rows_frozen" => format!("{rfp_frozen}/{}", rfp_rows.len()),
            "generated_by" => GENERATED_BY,
            "regenerate" => REGENERATE,
            "rvm" => pydict! {
                "id" => index(&rvm, "id")?.clone(), "path" => RVM_REL, "sha256" => rvm_pin,
                "status" => get(&rvm, "status")?.clone(),
            },
            "registration" => pydict! {
                "path" => REG_REL,
                "sha256" => self.sha256_file(REG_REL)?,
                "rfp_number" => index(rb, "rfp_number")?.clone(),
                "pdf_sha256" => index(rb, "pdf_sha256")?.clone(),
                "clauses_sha256" => clauses_sha,
                "clauses_hash_rule" => index(rb, "clauses_hash_rule")?.clone(),
                "n_clauses" => py::len(index(&reg, "clauses")?)? as i64,
            },
            "governing_directive_a9_22" => self.decision_ref(A922_JSON, A922_MD)?,
            "physics_rule" => concat!(
                "the physics layer never reads this file's clause ids or the RVM; it consumes values through ",
                "config/mission and the abep_sim.constants compatibility loader only"
            ),
        });
        let mut md = dict(pydict! { "altitude_km" => Value::List(vec![lo, hi]) });
        merge(&mut md, &Value::Dict(ref_(&alt)?))?;
        md.insert("units", s("km"));
        md.insert(
            "provenance",
            s(concat!(
                "A9.22 G5: the 180-230 km check stays as a frozen mission / design-state ",
                "domain constraint, consumed as mission_domain.altitude_km"
            )),
        );
        out.insert("mission_domain", Value::Dict(md));
        let mut dur = dict(pydict! { "authoritative_basis_h" => lim_value(&life)? });
        merge(&mut dur, &Value::Dict(ref_(&life)?))?;
        dur.insert("provenance", s("A9.22 G1: 26,280 h is the authoritative mission-duration basis"));
        dur.insert("rfp_printed_text", index(&c_life, "text")?.clone());
        dur.insert("g1_status", s(G1_STATUS));
        dur.insert(
            "historical_mission_hours",
            pydict! {
                "value_h" => legacy_mission_h, "label" => HISTORICAL_LABEL,
                "note" => concat!(
                    "pre-A9.22 basis; kept in abep_sim.constants.RFP ",
                    "(immutable) and in immutable history only"
                ),
            },
        );
        out.insert("mission_duration", Value::Dict(dur));
        let mut sfl = dict(pydict! {
            "value_h" => lim_value(&firing)?,
            "comparator" => index(&lim(&firing)?, "comparator")?.clone(),
        });
        merge(&mut sfl, &Value::Dict(ref_(&firing)?))?;
        sfl.insert("label", s("SUBSYSTEM_FIRING_LIFE_ASSUMPTION"));
        sfl.insert(
            "provenance",
            s(concat!(
                "A9.22 G1: 15,000 h only as an explicitly labelled subsystem ",
                "firing / life assumption, never the mission duration"
            )),
        );
        out.insert("subsystem_firing_life", Value::Dict(sfl));
        let mut limits = Vec::new();
        for r in &row_list {
            if get(r, "limit")?.truthy() {
                let mut e = ref_(r)?;
                e.insert("title", index(r, "title")?.clone());
                e.insert("limit", lim(r)?);
                limits.push(Value::Dict(e));
            }
        }
        out.insert("rvm_limits", Value::List(limits));
        out.insert("rfp_constraints_compat", Value::Dict(compat));
        Ok(Value::Dict(out))
    }

    // ====================================================================================================== constraints
    pub fn build_constraints(&self, snapshot: &Value, snapshot_bytes: &[u8]) -> ConfigResult<Value> {
        let comp = index(snapshot, "rfp_constraints_compat")?;
        let md = index(snapshot, "mission_domain")?;
        let life = index(snapshot, "mission_duration")?;
        let fire = index(snapshot, "subsystem_firing_life")?;
        let limits = py::iterate(index(snapshot, "rvm_limits")?)?;
        let mut rows = Dict::new();
        for e in &limits {
            rows.insert(py_str(index(e, "rvm_row")?), e.clone());
        }
        let limit_of = |row: &Value| -> ConfigResult<Value> {
            for e in &limits {
                if py_eq(index(e, "rvm_row")?, row) {
                    return Ok(index(e, "limit")?.clone());
                }
            }
            Err(bad(format!("requirements snapshot carries no rvm_limits entry for {}", py_str(row))))
        };
        let prov = |field: &str, e: &Value| -> ConfigResult<Value> {
            Ok(pydict! {
                "snapshot_field" => field,
                "rvm_row" => index(e, "rvm_row")?.clone(),
                "rvm_key" => index(e, "rvm_key")?.clone(),
                "rfp_clauses" => py_list(index(e, "rfp_clauses")?)?,
                "requirement_origin" => get(e, "requirement_origin")?.clone(),
                "requirement_frozen" => index(e, "requirement_frozen")?.truthy(),
            })
        };
        let st = |es: &[&Value]| -> ConfigResult<&'static str> {
            for e in es {
                if !index(e, "requirement_frozen")?.truthy() {
                    return Ok("PROVISIONAL");
                }
            }
            Ok("FROZEN")
        };
        let cv = |k: &str, f: &str| -> ConfigResult<Value> { Ok(index(index(comp, k)?, f)?.clone()) };
        let alt_lim = limit_of(index(md, "rvm_row")?)?;
        let tmin_lim = limit_of(&cv("thrust_min_mN", "rvm_row")?)?;
        let tmax_lim = limit_of(&cv("thrust_max_mN", "rvm_row")?)?;
        let pbus_lim = limit_of(&cv("power_max_W", "rvm_row")?)?;
        let mass_lim = limit_of(&cv("mass_max_kg", "rvm_row")?)?;
        let life_lim = limit_of(index(life, "rvm_row")?)?;
        let fire_lim = limit_of(index(fire, "rvm_row")?)?;
        let ic_lim = limit_of(&cv("ic_total_min", "rvm_row")?)?;
        let (air_row, xe_row) = (rows.get("RVM-08").cloned(), rows.get("RVM-10").cloned());
        let rows_ok = match (&air_row, &xe_row) {
            (Some(a), Some(x)) => {
                py::startswith(index(a, "rvm_key")?, "ATMOSPHERIC_PROPELLANT")?
                    && py::startswith(index(x, "rvm_key")?, "XE_CAPABILITY")?
            }
            _ => false,
        };
        if !rows_ok {
            return Err(bad("requirements snapshot: propellant-capability rows (atmospheric / Xe) not found"));
        }
        let (air_row, xe_row) = (air_row.expect("checked"), xe_row.expect("checked"));
        let lv = |l: &Value| -> ConfigResult<Value> { Ok(index(l, "value")?.clone()) };
        for (got, want) in [
            (cv("thrust_min_mN", "value")?, lv(&tmin_lim)?),
            (cv("power_max_W", "value")?, lv(&pbus_lim)?),
            (cv("mass_max_kg", "value")?, lv(&mass_lim)?),
            (index(md, "altitude_km")?.clone(), lv(&alt_lim)?),
            (index(life, "authoritative_basis_h")?.clone(), lv(&life_lim)?),
            (index(fire, "value_h")?.clone(), lv(&fire_lim)?),
            (cv("ignition_hours", "value")?, index(fire, "value_h")?.clone()),
        ] {
            if !py_eq(&got, &want) {
                return Err(bad(format!(
                    "requirements snapshot is internally inconsistent ({} != {})",
                    py_repr(&got),
                    py_repr(&want)
                )));
            }
        }
        #[allow(clippy::too_many_arguments)]
        fn entry(
            value: Value,
            units: &str,
            comparator: Value,
            kind: &str,
            consumed_by: &[&str],
            prov: Value,
            status: Value,
            kw: Vec<(&str, Value)>,
        ) -> Value {
            let mut e = dict(pydict! {
                "value" => value, "units" => units, "comparator" => comparator, "kind" => kind, "status" => status,
                "consumed_by" => strs(consumed_by),
            });
            for (k, v) in kw {
                e.insert(k, v);
            }
            e.insert("provenance", prov);
            Value::Dict(e)
        }
        let comparator = |l: &Value| -> ConfigResult<Value> { Ok(index(l, "comparator")?.clone()) };
        let tmax = index(comp, "thrust_max_mN")?;
        let mut constraints = Dict::new();
        constraints.insert(
            "altitude_band_km",
            entry(
                py_list(index(md, "altitude_km")?)?,
                "km",
                comparator(&alt_lim)?,
                "DOMAIN",
                &[
                    "abep_sim/design/engineering_constraints.py MISSION_DOMAIN_ALTITUDE_KM (design-state domain check)",
                    concat!(
                        "frozen design-state set v2 domain validation (the states themselves are the physics input; owner ",
                        "ruling 2026-10-04: never an operating-scenario input)"
                    ),
                ],
                prov("mission_domain.altitude_km", md)?,
                s(st(&[md])?),
                vec![("note", s("A9.22 G5: frozen mission / design-state domain constraint (mission_domain.altitude_km)"))],
            ),
        );
        let tmin = index(comp, "thrust_min_mN")?;
        constraints.insert(
            "thrust_sustained_min_mN",
            entry(
                index(tmin, "value")?.clone(),
                "mN",
                comparator(&tmin_lim)?,
                "LIMIT",
                &["abep_sim/design/engineering_constraints.py THRUST_MIN_MN / HC-01"],
                prov("rfp_constraints_compat.thrust_min_mN", tmin)?,
                index(tmin, "status")?.clone(),
                vec![],
            ),
        );
        constraints.insert(
            "thrust_capability_mN",
            entry(
                index(tmax, "value")?.clone(),
                "mN",
                comparator(&tmax_lim)?,
                "LIMIT",
                &[
                    "abep_sim/design/engineering_constraints.py THRUST_MAX_MN / HC-02",
                    "abep_sim/assessment/closure_checks.py Constraints.thrust_max_mN (peak-capability check)",
                ],
                prov("rfp_constraints_compat.thrust_max_mN", tmax)?,
                index(tmax, "status")?.clone(),
                vec![(
                    "note",
                    s("upper end of the printed 12-25 mN thrust envelope; carried as the >= 25 mN capability requirement"),
                )],
            ),
        );
        let pbus = index(comp, "power_max_W")?;
        constraints.insert(
            "p_bus_max_W",
            entry(
                index(pbus, "value")?.clone(),
                "W",
                comparator(&pbus_lim)?,
                "LIMIT",
                &[
                    "abep_sim/design/engineering_constraints.py P_BUS_MAX_W / HC-03",
                    "abep_sim/assessment/closure_checks.py Constraints.power_max_W",
                    "abep_sim/assessment/arch_constraints.py default_limits power_max_W",
                ],
                prov("rfp_constraints_compat.power_max_W", pbus)?,
                index(pbus, "status")?.clone(),
                vec![],
            ),
        );
        let mass = index(comp, "mass_max_kg")?;
        constraints.insert(
            "wet_mass_max_kg",
            entry(
                index(mass, "value")?.clone(),
                "kg",
                comparator(&mass_lim)?,
                "LIMIT",
                &[
                    "abep_sim/design/engineering_constraints.py M_WET_MAX_KG / HC-04",
                    "abep_sim/assessment/arch_constraints.py design_constraints default m_max_kg (archengine search preset)",
                    "abep_sim/assessment/closure_checks.py Constraints.mass_max_kg",
                ],
                prov("rfp_constraints_compat.mass_max_kg", mass)?,
                index(mass, "status")?.clone(),
                vec![],
            ),
        );
        let mh = index(comp, "mission_hours")?;
        constraints.insert(
            "mission_life_h",
            entry(
                index(life, "authoritative_basis_h")?.clone(),
                "h",
                comparator(&life_lim)?,
                "LIMIT",
                &[concat!(
                    "config/mission/mission_scenario_v2.json mission_hours initial_basis (provenance only; the ",
                    "mission-integration horizon is an independently versioned operating choice, A9.24 item 4)"
                )],
                prov("mission_duration.authoritative_basis_h", life)?,
                index(life, "status")?.clone(),
                vec![
                    ("g1_status", index(life, "g1_status")?.clone()),
                    (
                        "historical_value",
                        pydict! {
                            "value_h" => index(mh, "value")?.clone(), "label" => HISTORICAL_LABEL,
                            "note" => concat!(
                                "pre-A9.22 basis (abep_sim.constants.RFP.mission_hours, immutable); no consumer ",
                                "computes with it"
                            ),
                        },
                    ),
                ],
            ),
        );
        constraints.insert(
            "firing_life_h",
            entry(
                index(fire, "value_h")?.clone(),
                "h",
                comparator(&fire_lim)?,
                "LIMIT",
                &[
                    "config/assessment/gate_thresholds_v1.json HC-07 (assessment only, A9.24 item 5)",
                    "abep_sim/assessment/arch_constraints.py design_constraints default life_min_h (via HC-07)",
                    concat!(
                        "config/mission/mission_scenario_v2.json firing_hours initial_basis (provenance only; the physics firing ",
                        "duration is an independent operating choice, owner ruling 2026-10-04)"
                    ),
                ],
                prov("subsystem_firing_life.value_h", fire)?,
                index(fire, "status")?.clone(),
                vec![("label", index(fire, "label")?.clone())],
            ),
        );
        let air_lim = index(&air_row, "limit")?;
        let xe_lim = index(&xe_row, "limit")?;
        constraints.insert(
            "propellant_capability",
            entry(
                pydict! { "ambient_atmosphere" => index(air_lim, "value")?.clone(), "xe" => index(xe_lim, "value")?.clone() },
                "-",
                pydict! {
                    "ambient_atmosphere" => index(air_lim, "comparator")?.clone(),
                    "xe" => index(xe_lim, "comparator")?.clone(),
                },
                "CATEGORICAL",
                &["assessment / compliance mapping only (no physics consumer)"],
                Value::List(vec![prov("rvm_limits[RVM-08]", &air_row)?, prov("rvm_limits[RVM-10]", &xe_row)?]),
                s(st(&[&air_row, &xe_row])?),
                vec![(
                    "note",
                    s(concat!(
                        "ambient atmospheric propellant primary + Xe-capable operating mode (architecture: ",
                        "config/architecture/hall_icp_neutralizer_v1.json supply modes)"
                    )),
                )],
            ),
        );
        constraints.insert(
            "intake_drag_generation_limit_mN",
            entry(
                index(tmax, "value")?.clone(),
                "mN",
                s("<="),
                "GENERATION_FILTER",
                &[
                    concat!(
                        "abep_sim/design/engineering_constraints.py INTAKE_DRAG_GENERATION_LIMIT_N (F1 C-DRAG-RFP generation ",
                        "filter)"
                    ),
                    "config/assessment/gate_thresholds_v1.json HC-09 (also reported in assessment, A9.24 item 5)",
                ],
                prov("rfp_constraints_compat.thrust_max_mN", tmax)?,
                index(tmax, "status")?.clone(),
                vec![
                    ("derived_from", s("thrust_capability_mN")),
                    (
                        "note",
                        s(concat!(
                            "A9.22 G2 Option 1: C-DRAG-RFP stays a generation filter (intake-face drag <= thrust maximum); ",
                            "Option 2 (assessment-only) is a separately approved change"
                        )),
                    ),
                ],
            ),
        );
        let ict = index(comp, "ic_total_min")?;
        constraints.insert(
            "ic_total_min",
            entry(
                index(ict, "value")?.clone(),
                "fraction",
                comparator(&ic_lim)?,
                "PROGRAMME_METRIC_LIMIT",
                &["abep_sim/assessment/closure_checks.py Constraints.ic_total_min"],
                prov("rfp_constraints_compat.ic_total_min", ict)?,
                index(ict, "status")?.clone(),
                vec![("layer", s("ASSESSMENT_ONLY (A9.22 G6)"))],
            ),
        );
        let ics = index(comp, "ic_subsystem_min")?;
        let mut ics_value = Dict::new();
        merge(&mut ics_value, index(ics, "value")?)?;
        constraints.insert(
            "ic_subsystem_min",
            entry(
                Value::Dict(ics_value),
                "fraction",
                comparator(&ic_lim)?,
                "PROGRAMME_METRIC_LIMIT",
                &["abep_sim/assessment/closure_checks.py Constraints.ic_thruster_min (thruster)"],
                prov("rfp_constraints_compat.ic_subsystem_min", ics)?,
                index(ics, "status")?.clone(),
                vec![("layer", s("ASSESSMENT_ONLY (A9.22 G6)"))],
            ),
        );
        let hp = index(comp, "hall_preferred")?;
        constraints.insert(
            "hall_preferred",
            entry(
                index(hp, "value")?.clone(),
                "-",
                s("is"),
                "CATEGORICAL_PREFERENCE",
                &["abep_sim/assessment/closure_checks.py (architecture-preference flag)"],
                prov("rfp_constraints_compat.hall_preferred", hp)?,
                index(hp, "status")?.clone(),
                vec![("layer", s("ASSESSMENT_ONLY (A9.22 G6)"))],
            ),
        );
        let n_frozen =
            constraints.values().filter(|c| matches!(get(c, "status"), Ok(v) if is_str(v, "FROZEN"))).count();
        let n = constraints.len();
        Ok(pydict! {
            "schema" => "abep_config_engineering_constraints_v1",
            "id" => "engineering_constraints_v1",
            "layer" => "FROZEN_ENGINEERING_CONSTRAINTS",
            "title" => concat!(
                "Frozen engineering constraints (values) consumed by the physics / design seams and the assessment ",
                "layer; derived from the requirements snapshot (requirements extraction -> engineering constraints)"
            ),
            "set_status" => if n_frozen == n { "FROZEN" } else { "PROVISIONAL" },
            "set_status_rule" => concat!(
                "FROZEN only when every constraint is FROZEN; each constraint's status is derived from the ",
                "requirement_frozen flags its provenance rows carry in the requirements snapshot (never ",
                "hard-coded). FROZEN freezes the constraint basis only; it never means compliance."
            ),
            "constraints_frozen" => format!("{n_frozen}/{n}"),
            "generated_by" => GENERATED_BY,
            "regenerate" => REGENERATE,
            "governing_directive_a9_23" => self.decision_ref(A923_JSON, A923_MD)?,
            "rule" => concat!(
                "A9.23: physics / design code consumes the values of this file only (abep_sim.configuration.",
                "load_engineering_constraints; abep_sim/operating_inputs.py; abep_sim/design/engineering_constraints.",
                "py); the assessment layer reads its limits here. Requirement / clause ids below are PROVENANCE ONLY: ",
                "no code computes with them. The only derivation path is requirements snapshot -> this file ",
                "(scripts/config/build_config.py)."
            ),
            "provenance" => pydict! {
                "requirements_snapshot" => pydict! {
                    "id" => index(snapshot, "id")?.clone(),
                    "path" => format!("config/{REQ_FILE}"),
                    "sha256" => abep_provenance::sha256_hex(snapshot_bytes),
                    "snapshot_status" => index(snapshot, "snapshot_status")?.clone(),
                },
                "role" => "PROVENANCE_ONLY",
            },
            "constraints" => constraints,
        })
    }

    // ====================================================================================================== frozen scenario
    /// The frozen operating scenarios (A9.24 item 4): verified against their pins, never generated.
    pub fn frozen_scenario_bytes(&self) -> ConfigResult<(Vec<u8>, Vec<u8>)> {
        let pin = &self.scenario_pin;
        let mut out = Vec::new();
        for (rel, want) in [(MISSION_FILE, pin.sha256.as_str()), (MISSION_V1_FILE, MISSION_V1_SHA256)] {
            let p = self.config.join(rel);
            if !is_file(&p) {
                return Err(bad(format!("config/{rel} missing (frozen scenario; never generated)")));
            }
            let b = read_bytes(&p)?;
            let got = abep_provenance::sha256_hex(&b);
            if got != want {
                return Err(bad(format!(
                    "config/{rel} sha256 {got} != pinned {want}: a changed operating scenario needs a new scenario \
                     version (A9.24 item 4)"
                )));
            }
            out.push(b);
        }
        let d = pyjson::loads(&read_text_utf8(&out[0])?)?;
        if !(is_str(get(&d, "id")?, &pin.id) && py_eq(get(&d, "scenario_version")?, &Value::int(pin.scenario_version)))
        {
            return Err(bad(format!(
                "config/{MISSION_FILE}: id / scenario_version differ from the pin {{'id': {}, 'scenario_version': {}, \
                 'sha256': {}}}",
                abep_types::pyjson::py_repr_str(&pin.id),
                pin.scenario_version,
                abep_types::pyjson::py_repr_str(&pin.sha256)
            )));
        }
        let v1 = out.pop().expect("two files");
        let v2 = out.pop().expect("two files");
        Ok((v2, v1))
    }

    // ====================================================================================================== gate thresholds
    pub fn build_gate_thresholds(&self, constraints: &Value) -> ConfigResult<Value> {
        let c = index(constraints, "constraints")?;
        for cid in ["firing_life_h", "intake_drag_generation_limit_mN"] {
            if !py::contains_str(c, cid)? {
                return Err(bad(format!("engineering constraints carry no {cid}")));
            }
        }
        let a924 = format!("A9.24 item 5 ({A924_MD})");
        #[allow(clippy::too_many_arguments)]
        fn thr(
            value: Value,
            units: &str,
            comparator: &str,
            layer: &str,
            criterion: &str,
            provenance: Vec<String>,
            status: &str,
            kw: Vec<(&str, Value)>,
        ) -> Value {
            let mut e = dict(pydict! {
                "kind" => "THRESHOLD", "value" => value, "units" => units, "comparator" => comparator,
                "status" => status, "layer" => layer, "criterion" => criterion,
            });
            for (k, v) in kw {
                e.insert(k, v);
            }
            e.insert("provenance", Value::List(provenance.into_iter().map(Value::Str).collect()));
            Value::Dict(e)
        }
        let reference = |cid: &str,
                         units: &str,
                         scale: f64,
                         comparator: &str,
                         layer: &str,
                         criterion: &str,
                         provenance: Vec<String>|
         -> ConfigResult<Value> {
            let cc = index(c, cid)?;
            Ok(pydict! {
                "kind" => "CONSTRAINT_REFERENCE", "constraint_ref" => cid,
                "constraint_units" => index(cc, "units")?.clone(), "units" => units, "scale_to_gate_units" => scale,
                "comparator" => comparator, "status" => index(cc, "status")?.clone(), "layer" => layer,
                "criterion" => criterion,
                "provenance" => Value::List(provenance.into_iter().map(Value::Str).collect()),
            })
        };
        let p = |xs: &[&str]| -> Vec<String> { xs.iter().map(|x| x.to_string()).collect() };
        let mut gates = Dict::new();
        gates.insert(
            "HC-05",
            thr(
                Value::Float(0.0),
                "-",
                ">",
                "ASSESSMENT_ONLY",
                concat!(
                    "M_n,LB > 0, where M_n = I_e,cap / I_d,max,H1 - 1 and M_n,LB is its lower uncertainty bound; ",
                    "the point difference I_e,cap - I_d,max is never the acceptance criterion; without uncertainty ",
                    "evidence (a lower bound) for the inputs HC-05 is NOT_EVALUATED; physics produces the currents ",
                    "and their uncertainties"
                ),
                p(&[
                    &a924,
                    "owner correction 2026-10-04 (uncertainty-aware ratio form)",
                    "former HC-05 literal I_E_MARGIN_MIN_A = 0.0",
                ]),
                "FROZEN",
                vec![("evaluation_without_lower_bound", s("NOT_EVALUATED"))],
            ),
        );
        gates.insert(
            "HC-06",
            thr(
                Value::Float(50.0),
                "K",
                ">=",
                "ASSESSMENT_PROTECTION_POLICY",
                concat!(
                    "temperature margin >= 50 K below the validated hardware-bound temperature limits ",
                    "(config/hardware/hardware_bounds_v1.json index); applied by assessment / protection logic, ",
                    "never inside thermal equations; physics produces temperatures / heat loads"
                ),
                p(&[&a924, "registered protection / acceptance margin (former HC-06 literal THERMAL_MARGIN_MIN_K)"]),
                "FROZEN",
                vec![],
            ),
        );
        gates.insert(
            "HC-07",
            reference(
                "firing_life_h",
                "h",
                1.0,
                ">",
                "ASSESSMENT_ONLY",
                concat!(
                    "predicted / measured subsystem firing life > the 15,000 h subsystem firing-life basis; the ",
                    "mission duration (26,280 h, operating scenario) is separate"
                ),
                p(&[&a924, "engineering constraint firing_life_h (single source)"]),
            )?,
        );
        gates.insert(
            "HC-08",
            thr(
                Value::Float(0.0),
                "N",
                ">=",
                "ASSESSMENT_ONLY",
                concat!(
                    "T_available(state) - D_spacecraft(state) >= 0 at every required state (statewise); physics ",
                    "computes T and D independently"
                ),
                p(&[&a924, "AG-13, owner decision A9.13 S6.15 (former HC-08 literal STATEWISE_T_MINUS_D_MIN_N)"]),
                "FROZEN",
                vec![],
            ),
        );
        gates.insert(
            "HC-09",
            reference(
                "intake_drag_generation_limit_mN",
                "N",
                1e-3,
                "<=",
                "DESIGN_GENERATION_FILTER_ALSO_REPORTED_IN_ASSESSMENT",
                concat!(
                    "intake-face drag <= 25 mN at every orbit state: F1-F8 design-generation filter (A9.22 G2 ",
                    "Option 1, read from the frozen engineering configuration, not RFP parsing) and reported in ",
                    "assessment; assessment-only (C-DRAG-RFP Option 2) needs a separate owner approval"
                ),
                p(&[&a924, "engineering constraint intake_drag_generation_limit_mN (single source)"]),
            )?,
        );
        gates.insert(
            "HC-10",
            thr(
                Value::Float(1.0),
                "-",
                ">=",
                "ASSESSMENT_ONLY",
                concat!(
                    "ambient atmospheric mode AND Xe contingency capability evaluated as architecture / capability ",
                    "evidence (1 = both demonstrated); no physics equation carries this requirement"
                ),
                p(&[&a924, "A9.15 RFP-compliant propellant policy (former HC-10 literal PROPELLANT_CAPABILITY_MIN)"]),
                "FROZEN",
                vec![],
            ),
        );
        gates.insert(
            "HC-11",
            thr(
                Value::Float(0.0),
                "-",
                ">=",
                "ASSESSMENT_ONLY",
                concat!(
                    "feed_available - feed_required >= 0 (statewise feed-state sufficiency, registered formulation: ",
                    "minimum relative field margin); the requirement comes from the measured / validated H-1 ",
                    "performance basis when available and is never reduced to the presently achievable feed"
                ),
                p(&[&a924, "AG-12, owner decision A9.13 S6.21 (former HC-11 literal FEED_STATE_SUFFICIENCY_MIN)"]),
                "FROZEN",
                vec![],
            ),
        );
        gates.insert(
            "HC-12",
            thr(
                Value::Null,
                "-",
                "<=",
                "ASSESSMENT_ONLY",
                concat!(
                    "compressor / plenum ripple <= measured H-1 ripple tolerance; threshold TBD until measured H-1 ",
                    "evidence establishes the permissible ripple basis; no default is invented"
                ),
                p(&[&a924, "A9.13 S6.17 / S6.12 feed quality"]),
                "TBD_PENDING_MEASURED_H1",
                vec![("evaluation_until_frozen", s("NOT_EVALUATED"))],
            ),
        );
        Ok(pydict! {
            "schema" => "abep_config_gate_thresholds_v1",
            "id" => "gate_thresholds_v1",
            "layer" => "ASSESSMENT_THRESHOLDS",
            "title" => concat!(
                "Hard-gate thresholds HC-05..HC-12 of the assessment layer (A9.24 item 5); physics / design modules ",
                "hold none of these values (HC-09 is also the design-generation filter, read from the engineering ",
                "constraints)"
            ),
            "generated_by" => GENERATED_BY,
            "regenerate" => REGENERATE,
            "governing_decision_a9_24" => self.decision_ref(A924_JSON, A924_MD)?,
            "engineering_constraints" => pydict! {
                "id" => index(constraints, "id")?.clone(),
                "path" => format!("config/{CONSTRAINTS_FILE}"),
                "binding" => "BY_ID (CONSTRAINT_REFERENCE gates)",
            },
            "rule" => concat!(
                "read by abep_sim.configuration.load_gate_thresholds for the assessment layer ",
                "(abep_sim/assessment/design_gates.py HARD_CONSTRAINT_LIMITS); a CONSTRAINT_REFERENCE gate carries no ",
                "value (single source: the engineering constraints, x scale_to_gate_units); a TBD gate has value ",
                "null and evaluates NOT_EVALUATED; changing a threshold changes the assessment only, never raw physics"
            ),
            "gates" => gates,
        })
    }

    // ====================================================================================================== design states
    pub fn build_design_state_ref(&self) -> ConfigResult<Value> {
        let ds = self.read_json(DS_REL)?;
        let man = self.read_json(DS_MANIFEST_REL)?;
        let rec = or_empty(get(&man, "design_states_file_v2")?).clone();
        let sha = self.sha256_file(DS_REL)?;
        let file_name = Path::new(DS_REL).file_name().and_then(|n| n.to_str()).expect("file name");
        if !is_str(get(&rec, "sha256")?, &sha) || !is_str(get(&rec, "file")?, file_name) {
            return Err(bad("dataset manifest design_states_file_v2 does not record the design-state file hash"));
        }
        Ok(pydict! {
            "schema" => "abep_config_design_state_set_ref_v1",
            "id" => index(&ds, "design_state_set_id")?.clone(),
            "layer" => "FROZEN_ENGINEERING_CONFIGURATION",
            "kind" => "REFERENCE (never a copy)",
            "path" => DS_REL,
            "sha256" => sha,
            "n_states" => index(&ds, "n_states")?.clone(),
            "version" => index(&ds, "version")?.clone(),
            "dataset_id" => index(&ds, "dataset_id")?.clone(),
            "dataset_sha256" => index(&ds, "dataset_sha256")?.clone(),
            "manifest" => pydict! {
                "path" => DS_MANIFEST_REL,
                "sha256" => self.sha256_file(DS_MANIFEST_REL)?,
                "design_states_file_v2_sha256" => index(&rec, "sha256")?.clone(),
                "dataset_sha256" => get(&man, "sha256")?.clone(),
            },
            "producer" => index(&ds, "producer")?.clone(),
            "loader" => "abep_sim/design/intake_synthesis.py::load_design_state_set (DESIGN_STATE_SET_SHA256)",
            "altitude_domain_source" => "config/constraints/engineering_constraints_v1.json constraints.altitude_band_km",
            "generated_by" => GENERATED_BY,
        })
    }

    // ====================================================================================================== hardware
    pub fn build_hardware(&self) -> ConfigResult<Value> {
        let mut entries = Vec::new();
        for (i, k, p, loc, role) in HW_ENTRIES {
            entries.push(pydict! {
                "id" => i, "kind" => k, "path" => p, "sha256" => self.sha256_file(p)?, "locator" => loc, "role" => role,
            });
        }
        Ok(pydict! {
            "schema" => "abep_config_hardware_bounds_index_v1",
            "id" => "hardware_bounds_v1",
            "layer" => "FROZEN_ENGINEERING_CONFIGURATION",
            "kind" => "INDEX (path + sha256 + locator; no value is copied)",
            "generated_by" => GENERATED_BY,
            "entries" => Value::List(entries),
        })
    }

    // ====================================================================================================== model set
    fn sorted_dir(&self, rel: &str, keep: impl Fn(&str, &Path) -> bool) -> ConfigResult<Vec<String>> {
        let dir = self.root.join(rel);
        let rd = std::fs::read_dir(&dir)
            .map_err(|e| ConfigError::new("FileNotFoundError", format!("{e}: '{}'", display(&dir))))?;
        let mut names = Vec::new();
        for ent in rd {
            let ent = ent.map_err(|e| ConfigError::new("OSError", e.to_string()))?;
            let name =
                ent.file_name().into_string().map_err(|_| ConfigError::new("UnicodeError", "non-UTF-8 file name"))?;
            if keep(&name, &ent.path()) {
                names.push(name);
            }
        }
        names.sort();
        Ok(names)
    }

    pub fn build_model_set(&self) -> ConfigResult<Value> {
        let mut modules = Vec::new();
        let mut flat = Dict::new();
        for name in self.sorted_dir("abep_sim", |n, _| n.ends_with(".py"))? {
            let rel = format!("abep_sim/{name}");
            let labels = version_labels(&self.read_text(&rel)?)?;
            let stem = &name[..name.len() - 3];
            modules.push(pydict! {
                "path" => rel.as_str(), "sha256" => self.sha256_file(&rel)?, "version_labels" => labels.clone(),
            });
            for (k, v) in labels.iter() {
                flat.insert(format!("{stem}.{k}"), v.clone());
            }
        }
        let rates = self.sorted_dir("abep_sim/data/rates", |_, p| is_file(p))?;
        let mut data = Vec::new();
        for r in
            DATA_FILES.iter().map(|x| x.to_string()).chain(rates.iter().map(|n| format!("abep_sim/data/rates/{n}")))
        {
            data.push(pydict! { "path" => r.as_str(), "sha256" => self.sha256_file(&r)? });
        }
        let pinned = self.read_text("hallthruster_bridge/PINNED.toml")?;
        let table: toml::Table =
            pinned.parse().map_err(|e: toml::de::Error| ConfigError::new("TOMLDecodeError", e.to_string()))?;
        let t = |sec: &str, key: &str| -> ConfigResult<Value> {
            let sv = table.get(sec).ok_or_else(|| py::key_error(sec))?;
            let v = sv.get(key).ok_or_else(|| py::key_error(key))?;
            toml_to_value(v)
        };
        let nm = pydict! {
            "hallthruster.package" => t("hallthruster", "package")?,
            "hallthruster.version" => t("hallthruster", "version")?,
            "hallthruster.commit" => t("hallthruster", "commit")?,
            "reaction_set.version" => t("reaction_set", "version")?,
            "reaction_set.status" => t("reaction_set", "status")?,
        };
        Ok(pydict! {
            "schema" => "abep_config_physics_model_set_v1",
            "id" => "physics_model_set_v1",
            "layer" => "PHYSICS",
            "scope" => "abep_sim/*.py (the physics package; abep_sim/design/ is the design layer and is not listed)",
            "generated_by" => GENERATED_BY,
            "regenerate" => REGENERATE,
            "rule" => concat!(
                "any change of a listed source or data file makes this model set stale (scripts/config/build_config.py ",
                "--check); a physics change is a model change under CLAUDE.md rules 1-2"
            ),
            "modules" => Value::List(modules),
            "data" => Value::List(data),
            "version_labels_flat" => flat,
            "numerical_methods_flat" => nm,
        })
    }

    // ====================================================================================================== sources of truth
    pub fn build_sources_of_truth(&self, files: &[(String, Vec<u8>)]) -> ConfigResult<Value> {
        let file = |rel: &str| -> &[u8] { &files.iter().find(|(k, _)| k == rel).expect("built before").1 };
        let doc = |rel: &str| -> ConfigResult<Value> { Ok(pyjson::loads(&read_text_utf8(file(rel))?)?) };
        let sha = |rel: &str| abep_provenance::sha256_hex(file(rel));
        let cfg_entry =
            |rel: &str, layer: &str, role: &str, loader: &str, kw: Vec<(&str, Value)>| -> ConfigResult<Value> {
                let d = doc(rel)?;
                let mut e = dict(pydict! {
                    "layer" => layer, "artefact" => format!("config/{rel}"), "id" => index(&d, "id")?.clone(),
                    "schema" => index(&d, "schema")?.clone(), "sha256" => sha(rel),
                    "pinned_by" => strs(&["config/MANIFEST.json"]), "role" => role, "loader" => loader,
                });
                for (k, v) in kw {
                    e.insert(k, v);
                }
                Ok(Value::Dict(e))
            };
        let schema_entry = |rel: &str, layer: &str, role: &str, producer: &str| -> ConfigResult<Value> {
            if !is_file(&self.root.join(rel)) {
                return Err(bad(format!("{rel} missing: run python scripts/config/build_result_schemas.py")));
            }
            let d = self.read_json(rel)?;
            Ok(pydict! {
                "layer" => layer, "artefact" => rel, "id" => index(&d, "$id")?.clone(),
                "schema" => index(&d, "$schema")?.clone(), "sha256" => self.sha256_file(rel)?,
                "pinned_by" => strs(&["config/SOURCES_OF_TRUTH.json"]), "role" => role, "producer" => producer,
                "generated_by" => index(index(&d, "x-abep")?, "generated_by")?.clone(),
            })
        };
        let ds_ref = doc(DS_REF_FILE)?;
        let ds_manifest_path = py_str(index(index(&ds_ref, "manifest")?, "path")?);
        let mut sources = Dict::new();
        sources.insert(
            "frozen_architecture",
            cfg_entry(
                ARCH_FILE,
                "FROZEN_ARCHITECTURE",
                "architecture_frozen_v1: the single flight architecture definition",
                "abep_sim.configuration.load_architecture; abep_sim/design/a9_19_architecture.py",
                vec![],
            )?,
        );
        sources.insert(
            "frozen_engineering_constraints",
            cfg_entry(
                CONSTRAINTS_FILE,
                "FROZEN_ENGINEERING_CONSTRAINTS",
                concat!(
                    "engineering_constraints_v1: every frozen numerical / categorical constraint (values; provenance only ",
                    "for requirement ids)"
                ),
                concat!(
                    "abep_sim.configuration.load_engineering_constraints; abep_sim/design/engineering_constraints.py; ",
                    "abep_sim/operating_inputs.py; abep_sim/assessment"
                ),
                vec![],
            )?,
        );
        sources.insert(
            "frozen_design_state_set",
            pydict! {
                "layer" => "FROZEN_DESIGN_STATE_SET", "artefact" => index(&ds_ref, "path")?.clone(),
                "id" => index(&ds_ref, "id")?.clone(), "alias" => "vleo_design_states_v2",
                "n_states" => index(&ds_ref, "n_states")?.clone(), "sha256" => index(&ds_ref, "sha256")?.clone(),
                "reference" => format!("config/{DS_REF_FILE}"), "reference_sha256" => sha(DS_REF_FILE),
                "pinned_by" => Value::List(vec![
                    s(&format!("{ds_manifest_path} (design_states_file_v2.sha256)")),
                    s(&format!("config/{DS_REF_FILE}")),
                ]),
                "role" => "the frozen environmental / orbital design states consumed by the design / physics runs",
                "loader" => format!(
                    "abep_sim.configuration.load_design_state_set_ref; {}",
                    py_str_strict(index(&ds_ref, "loader")?)?
                ),
            },
        );
        sources.insert(
            "physics_model_set",
            cfg_entry(
                MODEL_SET_FILE,
                "PHYSICS_MODELS",
                "physics_model_set_v1: physics module / data hashes and version labels",
                "abep_sim.configuration.load_model_set / model_set_drift",
                vec![],
            )?,
        );
        sources.insert(
            "raw_simulation_result",
            schema_entry(
                RESULT_SCHEMA_RAW,
                "RAW_RESULTS",
                "schema raw_closure_v2 of the raw physical result",
                "abep_sim.system.physics_closure",
            )?,
        );
        sources.insert(
            "assessment_result",
            schema_entry(
                RESULT_SCHEMA_ASSESSMENT,
                "ASSESSMENT",
                concat!(
                    "schema closure_assessment_v2 of the assessment / ",
                    "compliance result (raw result + frozen constraints)"
                ),
                "abep_sim.assessment.assess",
            )?,
        );
        let snap_status = index(&doc(REQ_FILE)?, "snapshot_status")?.clone();
        sources.insert(
            "requirements_provenance",
            cfg_entry(
                REQ_FILE,
                "PROVENANCE",
                concat!(
                    "requirements-extraction snapshot (RVM / RFP clause provenance); the only input ",
                    "of the engineering constraints; never read by physics / design code"
                ),
                "abep_sim.configuration.load_requirements_snapshot (assessment / compliance mapping only)",
                vec![("snapshot_status", snap_status)],
            )?,
        );
        Ok(pydict! {
            "schema" => "abep_sources_of_truth_v1",
            "id" => "sources_of_truth_v1",
            "generated_by" => GENERATED_BY,
            "regenerate" => REGENERATE,
            "governing_directive_a9_23" => self.decision_ref(A923_JSON, A923_MD)?,
            "dependency_rule" => strs(&[
                "requirements/provenance -> frozen engineering constraints (scripts/config/build_config.py only)",
                "architecture + frozen constraints + design states + physics -> raw results",
                "raw results + frozen constraints -> assessment / compliance",
            ]),
            "rule" => concat!(
                "exactly one authoritative artefact per role; no second file may claim a listed role (same schema id ",
                "or artefact id); tests/test_a9_23_dependency_rule.py enforces it"
            ),
            "supporting_inputs" => pydict! {
                "operating_scenario" => pydict! {
                    "artefact" => format!("config/{MISSION_FILE}"), "sha256" => sha(MISSION_FILE),
                    "role" => concat!(
                        "frozen, independently versioned operating-scenario choices (A9.24 item 4; ",
                        "constraint-derived inputs referenced, not restated)"
                    ),
                    "pinned_by" => strs(&["abep_sim/configuration.py OPERATING_SCENARIO_PIN", "config/MANIFEST.json"]),
                    "supersedes" => pydict! {
                        "artefact" => format!("config/{MISSION_V1_FILE}"), "sha256" => sha(MISSION_V1_FILE),
                        "status" => "HISTORICAL_SUPERSEDED_NOT_LOADED",
                    },
                },
                "assessment_gate_thresholds" => pydict! {
                    "artefact" => format!("config/{GATES_FILE}"), "sha256" => sha(GATES_FILE),
                    "role" => "HC-05..HC-12 assessment thresholds (A9.24 item 5)",
                    "loader" => "abep_sim.configuration.load_gate_thresholds",
                },
                "hardware_bounds_index" => pydict! {
                    "artefact" => format!("config/{HW_FILE}"), "sha256" => sha(HW_FILE),
                    "role" => "index of hardware-limit sources (no copied values)",
                },
            },
            "sources" => sources,
        })
    }

    // ====================================================================================================== all
    /// `build_all()`: config-relative path -> bytes, in the Python builder's order (MANIFEST.json last).
    pub fn build_all(&self) -> ConfigResult<Vec<(String, Vec<u8>)>> {
        let dump = |v: &Value| -> ConfigResult<Vec<u8>> { Ok(pyjson::dumps_config_file(v)?) };
        let mut out: Vec<(String, Vec<u8>)> = Vec::new();
        out.push((ARCH_FILE.into(), dump(&self.build_architecture()?)?));
        let snap = self.build_requirements()?;
        let snap_b = dump(&snap)?;
        out.push((REQ_FILE.into(), snap_b.clone()));
        let cons = self.build_constraints(&snap, &snap_b)?;
        out.push((CONSTRAINTS_FILE.into(), dump(&cons)?));
        let (v2, v1) = self.frozen_scenario_bytes()?;
        out.push((MISSION_FILE.into(), v2));
        out.push((MISSION_V1_FILE.into(), v1));
        out.push((GATES_FILE.into(), dump(&self.build_gate_thresholds(&cons)?)?));
        out.push((DS_REF_FILE.into(), dump(&self.build_design_state_ref()?)?));
        out.push((HW_FILE.into(), dump(&self.build_hardware()?)?));
        out.push((MODEL_SET_FILE.into(), dump(&self.build_model_set()?)?));
        let sot = self.build_sources_of_truth(&out)?;
        out.push((SOT_FILE.into(), dump(&sot)?));
        out.push(("README.md".into(), README.as_bytes().to_vec()));
        let mut sorted: Vec<&(String, Vec<u8>)> = out.iter().collect();
        sorted.sort_by(|a, b| a.0.cmp(&b.0));
        let mut files = Dict::new();
        for (k, v) in sorted {
            files.insert(k.as_str(), pydict! { "sha256" => abep_provenance::sha256_hex(v), "bytes" => v.len() as i64 });
        }
        let manifest = pydict! {
            "schema" => "abep_config_manifest_v1", "id" => "config_manifest_v1", "generated_by" => GENERATED_BY,
            "regenerate" => REGENERATE, "files" => files,
        };
        out.push(("MANIFEST.json".into(), dump(&manifest)?));
        Ok(out)
    }

    /// `main(["--check"])`: compare the regenerated files with `config/` byte for byte (no write).
    pub fn check(&self) -> ConfigResult<CheckOutcome> {
        let files = self.build_all()?;
        let mut stale = Vec::new();
        for (k, v) in &files {
            let p = self.config.join(k);
            if !is_file(&p) || read_bytes(&p)? != *v {
                stale.push(Value::str(k.as_str()));
            }
        }
        let mut extra = Vec::new();
        if self.config.is_dir() {
            let mut found = Vec::new();
            walk(&self.config, "", &mut found)?;
            found.sort();
            for rel in found {
                if !files.iter().any(|(k, _)| *k == rel) {
                    extra.push(Value::Str(rel));
                }
            }
        }
        if !stale.is_empty() || !extra.is_empty() {
            return Ok(CheckOutcome {
                exit: 1,
                line: format!(
                    "STALE: {}; unlisted files: {}",
                    py_repr(&Value::List(stale)),
                    py_repr(&Value::List(extra))
                ),
            });
        }
        Ok(CheckOutcome { exit: 0, line: format!("OK: {} config files current", files.len()) })
    }

    /// Write mode (`python scripts/config/build_config.py` without `--check`).
    pub fn write(&self) -> ConfigResult<usize> {
        let files = self.build_all()?;
        for (k, v) in &files {
            let p = self.config.join(k);
            if let Some(parent) = p.parent() {
                std::fs::create_dir_all(parent).map_err(|e| ConfigError::new("OSError", e.to_string()))?;
            }
            std::fs::write(&p, v).map_err(|e| ConfigError::new("OSError", e.to_string()))?;
        }
        Ok(files.len())
    }
}

/// The builder's pins and fixed inputs (contract INV-03 / INV-04 compare them with the Python builder's constants).
pub fn constants_value() -> Value {
    let pin = ScenarioPin::mission_scenario_v2();
    let mut decisions = Dict::new();
    for d in &DECISIONS {
        decisions.insert(
            d.key,
            pydict! {
                "md" => d.md, "md_sha256" => d.md_sha256, "json" => d.json, "json_sha256" => d.json_sha256,
                "decision_code" => d.decision_code,
            },
        );
    }
    let hw = HW_ENTRIES.iter().map(|(i, k, p, l, r)| strs(&[i, k, p, l, r])).collect();
    pydict! {
        "OPERATING_SCENARIO_PIN" => pydict! {
            "id" => pin.id.as_str(), "scenario_version" => pin.scenario_version, "sha256" => pin.sha256.as_str(),
        },
        "DECISIONS" => decisions,
        "VERBATIM_A9_19" => strs(&VERBATIM_A9_19),
        "MISSION_V1_SHA256" => MISSION_V1_SHA256,
        "SNAPSHOT_RVM_SHA256" => SNAPSHOT_RVM_SHA256,
        "ACCEPTED_RVM_BASIS_SHA256" => ACCEPTED_RVM_BASIS_SHA256,
        "HW_ENTRIES" => Value::List(hw),
        "DATA_FILES" => strs(&DATA_FILES),
        "RESULT_SCHEMAS" => pydict! { "raw" => RESULT_SCHEMA_RAW, "assessment" => RESULT_SCHEMA_ASSESSMENT },
        "FILES" => strs(&[ARCH_FILE, REQ_FILE, CONSTRAINTS_FILE, MISSION_FILE, MISSION_V1_FILE, GATES_FILE, DS_REF_FILE,
                          HW_FILE, MODEL_SET_FILE, SOT_FILE]),
        "GENERATED_BY" => GENERATED_BY,
        "REGENERATE" => REGENERATE,
        "README" => README,
    }
}

/// Every regular file under `dir` (following symlinks, as Python 3.11 `Path.rglob`), as posix relative paths.
fn walk(dir: &Path, prefix: &str, out: &mut Vec<String>) -> ConfigResult<()> {
    let rd = std::fs::read_dir(dir).map_err(|e| ConfigError::new("OSError", e.to_string()))?;
    for ent in rd {
        let ent = ent.map_err(|e| ConfigError::new("OSError", e.to_string()))?;
        let name =
            ent.file_name().into_string().map_err(|_| ConfigError::new("UnicodeError", "non-UTF-8 file name"))?;
        let rel = if prefix.is_empty() { name.clone() } else { format!("{prefix}/{name}") };
        let path = ent.path();
        if path.is_dir() {
            walk(&path, &rel, out)?;
        } else if is_file(&path) {
            out.push(rel);
        }
    }
    Ok(())
}

/// `v or []`.
fn or_empty_list(v: &Value) -> &Value {
    static EMPTY: Value = Value::List(Vec::new());
    if v.truthy() {
        v
    } else {
        &EMPTY
    }
}

/// `"..." + v` requires a str.
fn py_str_strict(v: &Value) -> ConfigResult<String> {
    match v {
        Value::Str(x) => Ok(x.clone()),
        other => Err(py::type_error(format!("can only concatenate str (not \"{}\") to str", other.type_name()))),
    }
}

fn toml_to_value(v: &toml::Value) -> ConfigResult<Value> {
    Ok(match v {
        toml::Value::String(x) => Value::str(x.as_str()),
        toml::Value::Integer(i) => Value::int(*i),
        toml::Value::Float(f) => Value::Float(*f),
        toml::Value::Boolean(b) => Value::Bool(*b),
        toml::Value::Array(a) => Value::List(a.iter().map(toml_to_value).collect::<ConfigResult<_>>()?),
        toml::Value::Table(t) => {
            let mut d = Dict::new();
            for (k, x) in t {
                d.insert(k.as_str(), toml_to_value(x)?);
            }
            Value::Dict(d)
        }
        toml::Value::Datetime(_) => {
            return Err(py::type_error("Object of type datetime is not JSON serializable"));
        }
    })
}
