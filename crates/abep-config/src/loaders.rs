//! Authoritative input manifests: sha256-verified loaders of `config/` (port of `abep_sim/configuration.py`).
//!
//! Every loader fails closed: a file missing from `MANIFEST.json`, a file whose sha256 differs from the manifest, or a
//! referenced file whose sha256 differs from its pin is refused with `ConfigurationError` (MODEL_ERROR), never
//! repaired. Values are returned as Python-shaped [`Value`]s (key order, int / float types and statuses exactly as the
//! Python reference returns them). The physics seam [`load_operating_inputs`] reads `MANIFEST.json` and the frozen
//! operating scenario only; [`physics_configuration`] never opens `config/requirements/` (A9.22 / A9.23).

use crate::py::{self, get, index, is_str, num_field, or_empty, r};
use crate::{ConfigError, ConfigPaths, ConfigResult};
use abep_types::pyjson::{py_eq, py_repr_str, py_str, read_text_utf8, Dict, Value};
use std::path::{Component, Path, PathBuf};

pub const MANIFEST_REL: &str = "MANIFEST.json";
pub const ARCHITECTURE_REL: &str = "architecture/hall_icp_neutralizer_v1.json";
pub const REQUIREMENTS_REL: &str = "requirements/rfp_constraints_v1.json";
pub const CONSTRAINTS_REL: &str = "constraints/engineering_constraints_v1.json";
pub const MISSION_REL: &str = "mission/mission_scenario_v2.json";
pub const MISSION_V1_REL: &str = "mission/mission_scenario_v1.json";
pub const GATE_THRESHOLDS_REL: &str = "assessment/gate_thresholds_v1.json";
pub const DESIGN_STATE_REF_REL: &str = "environment/design_state_set_ref_v1.json";
pub const HARDWARE_BOUNDS_REL: &str = "hardware/hardware_bounds_v1.json";
pub const MODEL_SET_REL: &str = "model_set/physics_model_set_v1.json";
pub const SOURCES_OF_TRUTH_REL: &str = "SOURCES_OF_TRUTH.json";

/// Constraint ids of the engineering-constraints file the loaders require.
pub const CONSTRAINT_IDS: [&str; 12] = [
    "altitude_band_km",
    "thrust_sustained_min_mN",
    "thrust_capability_mN",
    "p_bus_max_W",
    "wet_mass_max_kg",
    "mission_life_h",
    "firing_life_h",
    "propellant_capability",
    "intake_drag_generation_limit_mN",
    "ic_total_min",
    "ic_subsystem_min",
    "hall_preferred",
];

/// Assessment-layer hard gates (A9.24 item 5).
pub const GATE_IDS: [&str; 8] = ["HC-05", "HC-06", "HC-07", "HC-08", "HC-09", "HC-10", "HC-11", "HC-12"];

// ------------------------------------------------------------------------------------------------ file primitives

/// `str(Path(...))`: separators collapsed, `.` components dropped.
pub(crate) fn display(p: &Path) -> String {
    let mut out = PathBuf::new();
    for c in p.components() {
        if c != Component::CurDir {
            out.push(c.as_os_str());
        }
    }
    if out.as_os_str().is_empty() {
        out.push(".");
    }
    out.display().to_string()
}

/// `Path.is_file()` (follows symlinks; False on any error).
pub(crate) fn is_file(p: &Path) -> bool {
    std::fs::metadata(p).map(|m| m.is_file()).unwrap_or(false)
}

/// `Path.read_bytes()` with the Python exception classes.
pub(crate) fn read_bytes(p: &Path) -> ConfigResult<Vec<u8>> {
    std::fs::read(p).map_err(|e| {
        let class = match e.kind() {
            std::io::ErrorKind::NotFound => "FileNotFoundError",
            std::io::ErrorKind::IsADirectory => "IsADirectoryError",
            std::io::ErrorKind::PermissionDenied => "PermissionError",
            _ => "OSError",
        };
        ConfigError::new(class, format!("{e}: '{}'", display(p)))
    })
}

pub(crate) fn sha256_file(p: &Path) -> ConfigResult<String> {
    Ok(abep_provenance::sha256_hex(&read_bytes(p)?))
}

/// `json.loads(path.read_text(encoding="utf-8"))`.
pub(crate) fn read_json(p: &Path) -> ConfigResult<Value> {
    let text = read_text_utf8(&read_bytes(p)?)?;
    Ok(abep_types::pyjson::loads(&text)?)
}

fn schema_is(d: &Value, schema: &str) -> ConfigResult<bool> {
    Ok(is_str(get(d, "schema")?, schema))
}

// ------------------------------------------------------------------------------------------------ manifest

/// `load_manifest(root)`: `<config root>/MANIFEST.json`, schema `abep_config_manifest_v1` with a `files` dict.
pub fn load_manifest(paths: &ConfigPaths) -> ConfigResult<Value> {
    let p = paths.config_root.join(MANIFEST_REL);
    if !is_file(&p) {
        return Err(ConfigError::configuration(format!(
            "{} missing: the configuration manifest is required (no fallback); build it with python \
             scripts/config/build_config.py",
            display(&p)
        )));
    }
    let m = read_json(&p)?;
    if !schema_is(&m, "abep_config_manifest_v1")? || !matches!(get(&m, "files")?, Value::Dict(_)) {
        return Err(ConfigError::configuration(format!("{} is not an abep_config_manifest_v1", display(&p))));
    }
    Ok(m)
}

/// `load_verified(rel, root)`: `config/<rel>` after checking it is listed in MANIFEST.json with a matching sha256.
pub fn load_verified(rel: &str, paths: &ConfigPaths) -> ConfigResult<Value> {
    let m = load_manifest(paths)?;
    let files = index(&m, "files")?;
    if !py::contains_str(files, rel)? {
        return Err(ConfigError::configuration(format!("config/{rel} is not listed in config/MANIFEST.json")));
    }
    let p = paths.config_root.join(rel);
    if !is_file(&p) {
        return Err(ConfigError::configuration(format!(
            "config/{rel} missing (listed in config/MANIFEST.json; no fallback)"
        )));
    }
    let got = sha256_file(&p)?;
    let want = index(index(files, rel)?, "sha256")?;
    if !is_str(want, &got) {
        return Err(ConfigError::configuration(format!(
            "config/{rel} sha256 {got} != MANIFEST {} (an edited configuration file is refused; regenerate with \
             scripts/config/build_config.py)",
            py_str(want)
        )));
    }
    read_json(&p)
}

/// `_check_ref(path_rel, want, what)`: a referenced repository file must exist and match its pin.
fn check_ref(paths: &ConfigPaths, path_rel: &Value, want: &Value, what: &str) -> ConfigResult<PathBuf> {
    let rel = py::path_operand(path_rel)?;
    let p = paths.repo_root.join(rel);
    if !is_file(&p) {
        return Err(ConfigError::configuration(format!("{what}: referenced file {rel} missing")));
    }
    let got = sha256_file(&p)?;
    if !is_str(want, &got) {
        return Err(ConfigError::configuration(format!(
            "{what}: referenced file {rel} sha256 {got} != pinned {}",
            py_str(want)
        )));
    }
    Ok(p)
}

// ------------------------------------------------------------------------------------------------ loaders

/// `load_architecture(root)` (manifest-verified; the code-side pin lives in [`crate::architecture`]).
pub fn load_architecture(paths: &ConfigPaths) -> ConfigResult<Value> {
    let d = load_verified(ARCHITECTURE_REL, paths)?;
    if !schema_is(&d, "abep_config_architecture_v1")? {
        return Err(ConfigError::configuration("architecture config: unexpected schema"));
    }
    Ok(d)
}

/// `load_engineering_constraints_file(root)`: the frozen engineering-constraints artefact (A9.23).
pub fn load_engineering_constraints_file(paths: &ConfigPaths) -> ConfigResult<Value> {
    let d = load_verified(CONSTRAINTS_REL, paths)?;
    if !schema_is(&d, "abep_config_engineering_constraints_v1")? {
        return Err(ConfigError::configuration("engineering constraints: unexpected schema"));
    }
    let set_status = get(&d, "set_status")?;
    if !(is_str(set_status, "FROZEN") || is_str(set_status, "PROVISIONAL")) {
        return Err(ConfigError::configuration(format!(
            "engineering constraints: set_status {} not FROZEN/PROVISIONAL",
            r(set_status)
        )));
    }
    for (k, e) in py::items(or_empty(get(&d, "constraints")?))?.iter() {
        let st = get(e, "status")?;
        if !(is_str(st, "FROZEN") || is_str(st, "PROVISIONAL")) {
            return Err(ConfigError::configuration(format!(
                "engineering constraint {k}: status {} not FROZEN/PROVISIONAL",
                r(st)
            )));
        }
    }
    Ok(d)
}

fn pin_repr(pin: &crate::ScenarioPin) -> String {
    format!(
        "{{'id': {}, 'scenario_version': {}, 'sha256': {}}}",
        py_repr_str(&pin.id),
        pin.scenario_version,
        py_repr_str(&pin.sha256)
    )
}

/// `load_mission_scenario(root, verify_constraints)`: the frozen operating scenario (A9.24 item 4), checked against
/// MANIFEST.json and the code-side pin (id, scenario_version, sha256).
pub fn load_mission_scenario(paths: &ConfigPaths, verify_constraints: bool) -> ConfigResult<Value> {
    let d = load_verified(MISSION_REL, paths)?;
    if !schema_is(&d, "abep_config_mission_scenario_v2")? {
        return Err(ConfigError::configuration("mission scenario: unexpected schema"));
    }
    let got = sha256_file(&paths.config_root.join(MISSION_REL))?;
    let pin = &paths.scenario_pin;
    let id = get(&d, "id")?;
    let version = get(&d, "scenario_version")?;
    if !(is_str(id, &pin.id) && py_eq(version, &Value::int(pin.scenario_version)) && got == pin.sha256) {
        return Err(ConfigError::configuration(format!(
            "operating scenario (id {}, scenario_version {}, sha256 {got}) does not match its pin {} (A9.24 item 4: \
             a changed operating scenario needs a new scenario version)",
            r(id),
            r(version),
            pin_repr(pin)
        )));
    }
    let status = get(&d, "status")?;
    if !is_str(status, "FROZEN") {
        return Err(ConfigError::configuration(format!("mission scenario: status {} != FROZEN", r(status))));
    }
    if verify_constraints {
        let ecf = load_engineering_constraints_file(paths)?;
        let cons = or_empty(get(&ecf, "constraints")?);
        let ec_ref = or_empty(get(&d, "engineering_constraints")?);
        let ref_id = get(ec_ref, "id")?;
        if !py_eq(ref_id, get(&ecf, "id")?) {
            return Err(ConfigError::configuration(format!(
                "mission scenario references engineering constraints {}",
                r(ref_id)
            )));
        }
        for (k, e) in py::items(or_empty(get(&d, "inputs")?))?.iter() {
            let cref = get(e, "constraint_ref")?;
            let cid = if cref.truthy() { cref } else { get(or_empty(get(e, "initial_basis")?), "constraint_id")? };
            if !py::contains(cons, cid)? {
                return Err(ConfigError::configuration(format!(
                    "mission scenario input {k}: constraint {} not in the engineering constraints",
                    r(cid)
                )));
            }
        }
    }
    Ok(d)
}

fn pair(v: &Value, what: &str) -> ConfigResult<(f64, f64)> {
    if let Value::List(l) = v {
        if l.len() == 2 && l.iter().all(Value::is_number) {
            return Ok((l[0].to_f64()?, l[1].to_f64()?));
        }
    }
    Err(ConfigError::configuration(format!("{what}: expected [lo, hi]")))
}

fn all_numbers(d: &Value) -> bool {
    match d {
        Value::Dict(dd) => dd.values().all(Value::is_number),
        _ => false,
    }
}

/// `load_engineering_constraints(root)`: frozen engineering-constraint VALUES for the design seam, the operating
/// seam and the assessment layer; never opens `config/requirements/`.
pub fn load_engineering_constraints(paths: &ConfigPaths) -> ConfigResult<Value> {
    let d = load_engineering_constraints_file(paths)?;
    let c = index(&d, "constraints")?;
    let w = "engineering_constraints.constraints";
    let mut missing = Vec::new();
    for k in CONSTRAINT_IDS {
        if !py::contains_str(c, k)? {
            missing.push(Value::str(k));
        }
    }
    if !missing.is_empty() {
        return Err(ConfigError::configuration(format!("{w}: constraints {} missing", r(&Value::List(missing)))));
    }
    let alt = pair(get(index(c, "altitude_band_km")?, "value")?, &format!("{w}.altitude_band_km"))?;
    let fl = index(c, "firing_life_h")?;
    let fl_label = get(fl, "label")?;
    if !is_str(fl_label, "SUBSYSTEM_FIRING_LIFE_ASSUMPTION") {
        return Err(ConfigError::configuration(format!(
            "{w}.firing_life_h: label {} != SUBSYSTEM_FIRING_LIFE_ASSUMPTION",
            r(fl_label)
        )));
    }
    let ml = index(c, "mission_life_h")?;
    if !is_str(get(ml, "g1_status")?, "APPLIED") {
        return Err(ConfigError::configuration(format!("{w}.mission_life_h: A9.22 G1 not recorded as APPLIED")));
    }
    let sub = get(index(c, "ic_subsystem_min")?, "value")?;
    if !all_numbers(sub) {
        return Err(ConfigError::configuration(format!("{w}.ic_subsystem_min must map subsystem -> number")));
    }
    let hp = get(index(c, "hall_preferred")?, "value")?;
    if !matches!(hp, Value::Bool(_)) {
        return Err(ConfigError::configuration(format!("{w}.hall_preferred must be a boolean")));
    }
    let pc = get(index(c, "propellant_capability")?, "value")?;
    let pc_ok = match pc {
        Value::Dict(dd) => dd.len() == 2 && dd.contains_key("ambient_atmosphere") && dd.contains_key("xe"),
        _ => false,
    };
    if !pc_ok {
        return Err(ConfigError::configuration(format!(
            "{w}.propellant_capability must name ambient_atmosphere and xe"
        )));
    }
    let mut out = Dict::new();
    let field = |name: &str| -> ConfigResult<Value> {
        Ok(Value::Float(num_field(index(c, name)?, "value", &format!("{w}.{name}"))?))
    };
    out.insert("thrust_min_mN", field("thrust_sustained_min_mN")?);
    out.insert("thrust_max_mN", field("thrust_capability_mN")?);
    out.insert("power_max_W", field("p_bus_max_W")?);
    out.insert("mass_max_kg", field("wet_mass_max_kg")?);
    out.insert("alt_min_km", Value::Float(alt.0));
    out.insert("alt_max_km", Value::Float(alt.1));
    out.insert("ignition_hours", Value::Float(num_field(fl, "value", &format!("{w}.firing_life_h"))?));
    out.insert("firing_hours_label", index(fl, "label")?.clone());
    out.insert("mission_life_h", Value::Float(num_field(ml, "value", &format!("{w}.mission_life_h"))?));
    out.insert(
        "historical_mission_hours",
        Value::Float(num_field(
            or_empty(get(ml, "historical_value")?),
            "value_h",
            &format!("{w}.mission_life_h.historical_value"),
        )?),
    );
    out.insert("intake_drag_generation_limit_mN", field("intake_drag_generation_limit_mN")?);
    out.insert("ic_total_min", field("ic_total_min")?);
    let mut subf = Dict::new();
    for (k, v) in py::items(sub)?.iter() {
        subf.insert(k.as_str(), Value::Float(v.to_f64()?));
    }
    out.insert("ic_subsystem_min", Value::Dict(subf));
    out.insert("hall_preferred", hp.clone());
    out.insert("propellant_capability", pc.clone());
    let mut status = Dict::new();
    for (k, e) in py::items(c)?.iter() {
        status.insert(k.as_str(), index(e, "status")?.clone());
    }
    out.insert("status", Value::Dict(status));
    out.insert("set_status", index(&d, "set_status")?.clone());
    out.insert("id", index(&d, "id")?.clone());
    out.insert("source", Value::str(format!("config/{CONSTRAINTS_REL}")));
    Ok(Value::Dict(out))
}

/// `load_operating_inputs(root)`: operating inputs of the physics seam, from the frozen operating scenario ONLY
/// (A9.24 item 4; owner ruling 2026-10-04). Neither the engineering constraints nor the requirements snapshot are read.
pub fn load_operating_inputs(paths: &ConfigPaths) -> ConfigResult<Value> {
    let ms = load_mission_scenario(paths, false)?;
    let inp = or_empty(get(&ms, "inputs")?);
    let w = "mission_scenario.inputs";
    let choice = |key: &str, cid: &str| -> ConfigResult<f64> {
        let e = or_empty(get(inp, key)?);
        let ib = or_empty(get(e, "initial_basis")?);
        let bad = !is_str(get(e, "kind")?, "OPERATING_SCENARIO_CHOICE")
            || !is_str(get(ib, "constraint_id")?, cid)
            || !is_str(get(ib, "role")?, "PROVENANCE_ONLY")
            || py::contains_str(e, "set_equal_to_constraint")?;
        if bad {
            return Err(ConfigError::configuration(format!(
                "{w}.{key}: expected an independently versioned OPERATING_SCENARIO_CHOICE with initial_basis {cid} \
                 (provenance only)"
            )));
        }
        num_field(e, "value", &format!("{w}.{key}"))
    };
    let mh = or_empty(get(inp, "mission_hours")?);
    if !is_str(get(mh, "g1_status")?, "APPLIED") || !is_str(get(mh, "label")?, "MISSION_DURATION_BASIS") {
        return Err(ConfigError::configuration(format!(
            "{w}.mission_hours: A9.22 G1 not recorded as APPLIED (label {})",
            r(get(mh, "label")?)
        )));
    }
    let fh = or_empty(get(inp, "firing_hours")?);
    let fh_label = get(fh, "label")?;
    if !is_str(fh_label, "SUBSYSTEM_FIRING_LIFE_ASSUMPTION") {
        return Err(ConfigError::configuration(format!(
            "{w}.firing_hours: label {} != SUBSYSTEM_FIRING_LIFE_ASSUMPTION",
            r(fh_label)
        )));
    }
    for k in ["wet_mass_limit_kg", "altitude_domain_km"] {
        if py::contains_str(inp, k)? {
            return Err(ConfigError::configuration(format!(
                "{w}.{k}: not an operating-scenario input (engineering / assessment constraint)"
            )));
        }
    }
    let mut out = Dict::new();
    out.insert("mission_hours", Value::Float(choice("mission_hours", "mission_life_h")?));
    out.insert(
        "historical_mission_hours",
        Value::Float(num_field(
            or_empty(get(mh, "historical_note")?),
            "value_h",
            &format!("{w}.mission_hours.historical_note"),
        )?),
    );
    out.insert("firing_hours", Value::Float(choice("firing_hours", "firing_life_h")?));
    out.insert("firing_hours_label", index(fh, "label")?.clone());
    out.insert("thrust_min_mN", Value::Float(choice("xe_sizing_thrust_target_mN", "thrust_sustained_min_mN")?));
    out.insert("thrust_max_mN", Value::Float(choice("commanded_thrust_cap_mN", "thrust_capability_mN")?));
    out.insert("P_bus_max_W", Value::Float(choice("p_bus_throttling_cap_W", "p_bus_max_W")?));
    out.insert("source", Value::str(format!("config/{MISSION_REL}")));
    Ok(Value::Dict(out))
}

/// The operating inputs of the physics seam as typed values (from [`load_operating_inputs`]).
#[derive(Debug, Clone, PartialEq)]
pub struct OperatingInputs {
    pub mission_hours: f64,
    pub historical_mission_hours: f64,
    pub firing_hours: f64,
    pub firing_hours_label: String,
    pub thrust_min_mn: f64,
    pub thrust_max_mn: f64,
    pub p_bus_max_w: f64,
    pub source: String,
}

impl OperatingInputs {
    pub fn load(paths: &ConfigPaths) -> ConfigResult<Self> {
        let v = load_operating_inputs(paths)?;
        let f = |k: &str| -> ConfigResult<f64> { index(&v, k)?.to_f64().map_err(ConfigError::from) };
        let s = |k: &str| -> ConfigResult<String> { Ok(py_str(index(&v, k)?)) };
        Ok(OperatingInputs {
            mission_hours: f("mission_hours")?,
            historical_mission_hours: f("historical_mission_hours")?,
            firing_hours: f("firing_hours")?,
            firing_hours_label: s("firing_hours_label")?,
            thrust_min_mn: f("thrust_min_mN")?,
            thrust_max_mn: f("thrust_max_mN")?,
            p_bus_max_w: f("P_bus_max_W")?,
            source: s("source")?,
        })
    }
}

fn gate_tuple_repr(items: &[Value]) -> String {
    abep_types::pyjson::py_repr_tuple(items)
}

/// `load_gate_thresholds(root)`: assessment-layer HC-05..HC-12 thresholds (A9.24 item 5), read by the assessment
/// layer only. A CONSTRAINT_REFERENCE gate is resolved from the engineering constraints; a TBD gate has no value.
pub fn load_gate_thresholds(paths: &ConfigPaths) -> ConfigResult<Value> {
    let d = load_verified(GATE_THRESHOLDS_REL, paths)?;
    if !schema_is(&d, "abep_config_gate_thresholds_v1")? {
        return Err(ConfigError::configuration("gate thresholds: unexpected schema"));
    }
    let gates = or_empty(get(&d, "gates")?);
    let ids = py::iterate(gates)?;
    let want: Vec<Value> = GATE_IDS.iter().map(|g| Value::str(*g)).collect();
    if !(ids.len() == want.len() && ids.iter().zip(&want).all(|(a, b)| py_eq(a, b))) {
        return Err(ConfigError::configuration(format!(
            "gate thresholds: gates {} != {}",
            gate_tuple_repr(&ids),
            gate_tuple_repr(&want)
        )));
    }
    let mut ec: Option<Value> = None;
    let mut limits = Dict::new();
    for (gid, g) in py::items(gates)?.iter() {
        let w = format!("gate_thresholds.gates.{gid}");
        let kind = get(g, "kind")?;
        if is_str(kind, "CONSTRAINT_REFERENCE") {
            if py::contains_str(g, "value")? {
                return Err(ConfigError::configuration(format!("{w}: a CONSTRAINT_REFERENCE carries no value")));
            }
            if ec.is_none() {
                ec = Some(index(&load_engineering_constraints_file(paths)?, "constraints")?.clone());
            }
            let ecv = ec.as_ref().expect("loaded above");
            let cid = get(g, "constraint_ref")?;
            if !py::contains(ecv, cid)? {
                return Err(ConfigError::configuration(format!(
                    "{w}: constraint {} not in the engineering constraints",
                    r(cid)
                )));
            }
            let cid_s = py_str(cid);
            let entry = index(ecv, &cid_s)?;
            let a = num_field(entry, "value", &format!("{w}.{cid_s}"))?;
            let b = num_field(g, "scale_to_gate_units", &w)?;
            limits.insert(gid.as_str(), Value::Float(a * b));
        } else if is_str(get(g, "kind")?, "THRESHOLD") {
            if is_str(get(g, "status")?, "TBD_PENDING_MEASURED_H1") {
                if !matches!(get(g, "value")?, Value::Null) {
                    return Err(ConfigError::configuration(format!(
                        "{w}: a TBD threshold carries no value (no default is invented)"
                    )));
                }
                limits.insert(gid.as_str(), Value::Null);
            } else {
                let st = get(g, "status")?;
                if !is_str(st, "FROZEN") {
                    return Err(ConfigError::configuration(format!(
                        "{w}: status {} not FROZEN / TBD_PENDING_MEASURED_H1",
                        r(st)
                    )));
                }
                limits.insert(gid.as_str(), Value::Float(num_field(g, "value", &w)?));
            }
        } else {
            return Err(ConfigError::configuration(format!(
                "{w}: kind {} not THRESHOLD / CONSTRAINT_REFERENCE",
                r(get(g, "kind")?)
            )));
        }
    }
    let mut out = Dict::new();
    out.insert("limits", Value::Dict(limits));
    out.insert("gates", gates.clone());
    out.insert("id", index(&d, "id")?.clone());
    out.insert("source", Value::str(format!("config/{GATE_THRESHOLDS_REL}")));
    Ok(Value::Dict(out))
}

/// `load_design_state_set_ref(root, verify_target)`: the REFERENCE to the frozen design-state set v2.
pub fn load_design_state_set_ref(paths: &ConfigPaths, verify_target: bool) -> ConfigResult<Value> {
    let d = load_verified(DESIGN_STATE_REF_REL, paths)?;
    if !schema_is(&d, "abep_config_design_state_set_ref_v1")? {
        return Err(ConfigError::configuration("design-state set reference: unexpected schema"));
    }
    if verify_target {
        check_ref(paths, index(&d, "path")?, index(&d, "sha256")?, "design-state set reference")?;
        let man = index(&d, "manifest")?;
        check_ref(paths, index(man, "path")?, index(man, "sha256")?, "design-state set dataset manifest")?;
    }
    Ok(d)
}

/// `load_hardware_bounds(root, verify_targets)`: the INDEX of hardware-limit sources (path + sha256 + locator).
pub fn load_hardware_bounds(paths: &ConfigPaths, verify_targets: bool) -> ConfigResult<Value> {
    let d = load_verified(HARDWARE_BOUNDS_REL, paths)?;
    if !schema_is(&d, "abep_config_hardware_bounds_index_v1")? {
        return Err(ConfigError::configuration("hardware bounds index: unexpected schema"));
    }
    if verify_targets {
        for e in py::iterate(index(&d, "entries")?)? {
            let path = index(&e, "path")?;
            let sha = index(&e, "sha256")?;
            let what = format!("hardware bounds entry {}", py_str(index(&e, "id")?));
            check_ref(paths, path, sha, &what)?;
        }
    }
    Ok(d)
}

/// `load_model_set(root)`: physics module / data hashes and version labels.
pub fn load_model_set(paths: &ConfigPaths) -> ConfigResult<Value> {
    let d = load_verified(MODEL_SET_REL, paths)?;
    if !schema_is(&d, "abep_config_physics_model_set_v1")? {
        return Err(ConfigError::configuration("physics model set: unexpected schema"));
    }
    Ok(d)
}

/// `model_set_drift(root)`: physics modules / data files whose live sha256 differs from the model set.
pub fn model_set_drift(paths: &ConfigPaths) -> ConfigResult<Vec<String>> {
    let d = load_model_set(paths)?;
    let mut entries = py::iterate(index(&d, "modules")?)?;
    entries.extend(py::iterate(index(&d, "data")?)?);
    let mut bad = Vec::new();
    for e in &entries {
        let rel = py::path_operand(index(e, "path")?)?;
        let p = paths.repo_root.join(rel);
        if !is_file(&p) {
            bad.push(format!("{}: missing", py_str(index(e, "path")?)));
        } else {
            let got = sha256_file(&p)?;
            if !is_str(index(e, "sha256")?, &got) {
                bad.push(format!("{}: sha256 differs from the model set", py_str(index(e, "path")?)));
            }
        }
    }
    Ok(bad)
}

// ------------------------------------------------------------------------------------------------ simulation configuration

/// `SimulationConfiguration`: the identity (ids + sha256) of every input a simulation consumes, recorded with each
/// result. The requirements-snapshot fields are `None` for a raw physics run.
#[derive(Debug, Clone, PartialEq)]
pub struct SimulationConfiguration {
    pub architecture_id: Value,
    pub architecture_sha256: Value,
    pub design_state_set_id: Value,
    pub design_state_set_sha256: Value,
    pub materials_id: String,
    pub hardware_bounds_id: Value,
    pub hardware_bounds_sha256: Value,
    pub model_set_id: Value,
    pub model_set_sha256: Value,
    pub model_versions: Vec<(String, Value)>,
    pub numerical_method_versions: Vec<(String, Value)>,
    pub engineering_constraints_id: Value,
    pub engineering_constraints_sha256: Value,
    pub requirements_snapshot_id: Value,
    pub requirements_snapshot_sha256: Value,
    pub requirements_snapshot_status: Value,
    pub config_manifest_sha256: String,
}

impl SimulationConfiguration {
    /// `SimulationConfiguration.as_dict()`.
    pub fn as_value(&self) -> Value {
        let pairs = |v: &[(String, Value)]| Value::Dict(v.iter().cloned().collect());
        let mut d = Dict::new();
        d.insert("architecture_id", self.architecture_id.clone());
        d.insert("architecture_sha256", self.architecture_sha256.clone());
        d.insert("design_state_set_id", self.design_state_set_id.clone());
        d.insert("design_state_set_sha256", self.design_state_set_sha256.clone());
        d.insert("materials_id", Value::str(self.materials_id.as_str()));
        d.insert("hardware_bounds_id", self.hardware_bounds_id.clone());
        d.insert("hardware_bounds_sha256", self.hardware_bounds_sha256.clone());
        d.insert("model_set_id", self.model_set_id.clone());
        d.insert("model_set_sha256", self.model_set_sha256.clone());
        d.insert("model_versions", pairs(&self.model_versions));
        d.insert("numerical_method_versions", pairs(&self.numerical_method_versions));
        d.insert("engineering_constraints_id", self.engineering_constraints_id.clone());
        d.insert("engineering_constraints_sha256", self.engineering_constraints_sha256.clone());
        d.insert("requirements_snapshot_id", self.requirements_snapshot_id.clone());
        d.insert("requirements_snapshot_sha256", self.requirements_snapshot_sha256.clone());
        d.insert("requirements_snapshot_status", self.requirements_snapshot_status.clone());
        d.insert("config_manifest_sha256", Value::str(self.config_manifest_sha256.as_str()));
        Value::Dict(d)
    }
}

fn sorted_items(v: &Value) -> ConfigResult<Vec<(String, Value)>> {
    let mut items: Vec<(String, Value)> = py::items(v)?.iter().map(|(k, v)| (k.clone(), v.clone())).collect();
    items.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(items)
}

/// `f"{mat['id']}@{mat['sha256'][:16]}"`.
fn materials_id(mat: &Value) -> ConfigResult<String> {
    let id = py_str(index(mat, "id")?);
    let sha = index(mat, "sha256")?;
    let head = match sha {
        Value::Str(s) => s.chars().take(16).collect::<String>(),
        Value::List(l) => py_str(&Value::List(l.iter().take(16).cloned().collect())),
        Value::Dict(_) => return Err(py::type_error("unhashable type: 'slice'")),
        other => return Err(py::type_error(format!("'{}' object is not subscriptable", other.type_name()))),
    };
    Ok(format!("{id}@{head}"))
}

/// `physics_configuration(root)`: the raw-physics configuration (architecture, frozen engineering constraints,
/// design-state set, hardware bounds, model set; A9.23). Never opens the requirements snapshot.
pub fn physics_configuration(paths: &ConfigPaths) -> ConfigResult<SimulationConfiguration> {
    let man_doc = load_manifest(paths)?;
    let man = index(&man_doc, "files")?;
    let arch = load_architecture(paths)?;
    let ds = load_design_state_set_ref(paths, true)?;
    let hw = load_hardware_bounds(paths, true)?;
    let ms = load_model_set(paths)?;
    let ec = load_engineering_constraints_file(paths)?;
    let mut mat = None;
    for e in py::iterate(index(&hw, "entries")?)? {
        if is_str(index(&e, "kind")?, "materials_database") {
            mat = Some(e);
            break;
        }
    }
    let mat = mat.ok_or_else(|| ConfigError::new("StopIteration", ""))?;
    let sha_of = |rel: &str| -> ConfigResult<Value> { Ok(index(index(man, rel)?, "sha256")?.clone()) };
    Ok(SimulationConfiguration {
        architecture_id: index(&arch, "id")?.clone(),
        architecture_sha256: sha_of(ARCHITECTURE_REL)?,
        design_state_set_id: index(&ds, "id")?.clone(),
        design_state_set_sha256: index(&ds, "sha256")?.clone(),
        materials_id: materials_id(&mat)?,
        hardware_bounds_id: index(&hw, "id")?.clone(),
        hardware_bounds_sha256: sha_of(HARDWARE_BOUNDS_REL)?,
        model_set_id: index(&ms, "id")?.clone(),
        model_set_sha256: sha_of(MODEL_SET_REL)?,
        engineering_constraints_id: index(&ec, "id")?.clone(),
        engineering_constraints_sha256: sha_of(CONSTRAINTS_REL)?,
        model_versions: sorted_items(index(&ms, "version_labels_flat")?)?,
        numerical_method_versions: sorted_items(index(&ms, "numerical_methods_flat")?)?,
        requirements_snapshot_id: Value::Null,
        requirements_snapshot_sha256: Value::Null,
        requirements_snapshot_status: Value::Null,
        config_manifest_sha256: sha256_file(&paths.config_root.join(MANIFEST_REL))?,
    })
}
