//! The frozen design baseline DBF-1 (owner decision A9.37; `docs/baseline/DBF-1/`).
//!
//! `dbf1_config_v1.json` is the machine-readable subset of the authoritative `dbf1_v1.json` that the closure harness
//! reads. It is pinned here by sha256 together with the DBF-1 lock, the same way the operating scenario is pinned
//! (a code pin), and not through `config/MANIFEST.json`: that manifest's sha256 is inside committed records that tests
//! regenerate byte for byte. Every refusal is fail closed (`ConfigurationError`, MODEL_ERROR); a changed file is a
//! DCR with a new baseline version and new pins, never an edit.
//!
//! DBF-1.1 (`docs/baseline/DBF-1.1/`, approved DCR-DBF1-002) is the first successor: DBF-1 with DBF1-BZ-04 = BZ-H1FE-V1
//! (the FE-derived H-1 B(z) profiles, each sha256-pinned). [`load_dbf1_1`] is additive; [`load_dbf1`] and DBF-1 are
//! unchanged history.
//!
//! DBF-1.2 (`docs/baseline/DBF-1.2/`, proposed by the DCR-DBF1-001 resolution, A9.39 item 3) is DBF-1.1 with the
//! variable-effective-capture intake / compressor / plenum / feed selection, the AIR operating free-stream-flux window and
//! the altitude schedule. [`load_dbf1_2`] is additive; DBF-1 and DBF-1.1 and their loaders are unchanged history.

use crate::{ConfigError, ConfigResult};
use abep_types::pyjson::{self, Value};
use std::path::Path;

pub const DBF1_DIR: &str = "docs/baseline/DBF-1";
pub const DBF1_CONFIG_REL: &str = "docs/baseline/DBF-1/dbf1_config_v1.json";
pub const DBF1_CONFIG_SHA256: &str = "5bd76159fb9761b5c47619fb42217f05c24841d7009067ac71dcedf731759864";
pub const DBF1_LOCK_REL: &str = "docs/baseline/DBF-1/dbf1_lock_v1.json";
pub const DBF1_LOCK_SHA256: &str = "517e0cf693712ec6d355c4b23791b9ae8626577fd338e3030563eb027e86b907";
pub const DBF1_RECORD_REL: &str = "docs/baseline/DBF-1/dbf1_v1.json";
pub const DBF1_RECORD_SHA256: &str = "d20f1e8aa95c2d6ee0b307669500d7aaa5ea6abf4d21ddb944b7999525943e4f";

/// The DBF-1 feed-loop controller (DBF1-IN-07).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Dbf1Controller {
    pub kp: f64,
    pub ti_s: f64,
    pub f_valve_hz: f64,
    pub authority: f64,
}

/// The DBF-1 upstream design (DBF1-IN-01..07).
#[derive(Debug, Clone, PartialEq)]
pub struct Dbf1Upstream {
    pub design_id: String,
    pub candidate: String,
    pub area_m2: f64,
    pub l_over_d: f64,
    pub phi: f64,
    pub filter: String,
    pub compressor: String,
    pub v_m3: f64,
    pub p_set_pa: f64,
    pub wall: String,
    pub scenarios: Vec<String>,
    pub controller: Dbf1Controller,
}

/// The DBF-1 ICP geometry (DBF1-ICP-01..07, DBF1-MAT-03).
#[derive(Debug, Clone, PartialEq)]
pub struct Dbf1Icp {
    pub radius_m: f64,
    pub length_m: f64,
    pub collector_axial_length_m: f64,
    pub vessel_material: String,
    pub collector_material: String,
    pub f_rf_hz: f64,
    pub p_fwd_envelope_w: [f64; 2],
}

/// The DBF-1 reference host drag (DBF1-DRAG-01..03; REFERENCE_PENDING_CUSTOMER_ICD).
#[derive(Debug, Clone, PartialEq)]
pub struct Dbf1Drag {
    pub case_id: String,
    pub a_ref_m2: f64,
    pub cd: f64,
    pub intake_accounting: String,
    pub sensitivity_cases: Vec<String>,
}

/// The DBF-1 power / mass allocations (DBF1-PWR-*, DBF1-MASS-*): design allocations, never RFP gates.
#[derive(Debug, Clone, PartialEq)]
pub struct Dbf1PowerMass {
    pub design_allocation_w: f64,
    pub common_allocation_w: f64,
    pub mass_margin_fraction: f64,
    pub nominal_dry_target_kg: f64,
    pub xe_reference_load_kg: f64,
    pub wet_target_at_reference_kg: f64,
    pub planning_nominal_dry_kg: f64,
    pub planning_dry_kg: f64,
    pub planning_wet_kg_at_reference: f64,
    /// bus_power_boundary_a9_v2 slot names per group (hall, icp, common, reserved).
    pub slots_by_group: Vec<(String, Vec<String>)>,
}

/// The machine-readable DBF-1 subset as read and verified.
#[derive(Debug, Clone, PartialEq)]
pub struct Dbf1Config {
    pub geometry_id: String,
    pub bz_shape_id: String,
    pub b_peak_band_g: [f64; 2],
    pub v_d_band_v: [f64; 2],
    pub upstream: Dbf1Upstream,
    pub icp: Dbf1Icp,
    pub drag: Dbf1Drag,
    pub power_mass: Dbf1PowerMass,
    pub anode_primary: String,
    pub anode_backup: String,
    pub baseline_deficiencies: Vec<String>,
    /// The raw document (for provenance blocks).
    pub raw: Value,
}

fn bad(m: impl Into<String>) -> ConfigError {
    ConfigError::configuration(format!("{DBF1_CONFIG_REL}: {}", m.into()))
}

fn read_pinned(repo: &Path, rel: &str, want: &str) -> ConfigResult<Vec<u8>> {
    let b = std::fs::read(repo.join(rel))
        .map_err(|e| ConfigError::configuration(format!("{rel} missing or unreadable (no fallback): {e}")))?;
    let got = abep_provenance::sha256_hex(&b);
    if got != want {
        return Err(ConfigError::configuration(format!(
            "{rel}: sha256 {got} != pinned {want} (a changed DBF-1 file needs a DCR and a new baseline version)"
        )));
    }
    Ok(b)
}

fn at<'a>(v: &'a Value, path: &[&str]) -> ConfigResult<&'a Value> {
    path.iter()
        .try_fold(v, |x, k| x.as_dict().and_then(|d| d.get(k)))
        .ok_or_else(|| bad(format!("missing {}", path.join("."))))
}

fn num(v: &Value, path: &[&str]) -> ConfigResult<f64> {
    let x = at(v, path)?.to_f64().map_err(|_| bad(format!("{} is not a number", path.join("."))))?;
    if !x.is_finite() {
        return Err(bad(format!("{} is not finite", path.join("."))));
    }
    Ok(x)
}

fn st(v: &Value, path: &[&str]) -> ConfigResult<String> {
    at(v, path)?.as_str().map(str::to_string).ok_or_else(|| bad(format!("{} is not a string", path.join("."))))
}

fn strs(v: &Value, path: &[&str]) -> ConfigResult<Vec<String>> {
    at(v, path)?
        .as_list()
        .ok_or_else(|| bad(format!("{} is not a list", path.join("."))))?
        .iter()
        .map(|x| x.as_str().map(str::to_string).ok_or_else(|| bad(format!("{}: non-string", path.join(".")))))
        .collect()
}

fn pair(v: &Value, path: &[&str]) -> ConfigResult<[f64; 2]> {
    let l = at(v, path)?.as_list().ok_or_else(|| bad(format!("{} is not a list", path.join("."))))?;
    match l {
        [a, b] => {
            let a = a.to_f64().map_err(|_| bad(format!("{}[0]", path.join("."))))?;
            let b = b.to_f64().map_err(|_| bad(format!("{}[1]", path.join("."))))?;
            Ok([a, b])
        }
        _ => Err(bad(format!("{} must have two entries", path.join(".")))),
    }
}

/// Verify the DBF-1 lock (pinned) names the config and the authoritative record with their pinned sha256.
pub fn verify_lock(repo: &Path) -> ConfigResult<()> {
    let lock = pyjson::loads(&pyjson::read_text_utf8(&read_pinned(repo, DBF1_LOCK_REL, DBF1_LOCK_SHA256)?)?)?;
    for (k, want) in [("dbf1_config_v1.json", DBF1_CONFIG_SHA256), ("dbf1_v1.json", DBF1_RECORD_SHA256)] {
        if at(&lock, &["files", k])?.as_str() != Some(want) {
            return Err(ConfigError::configuration(format!("{DBF1_LOCK_REL}: files.{k} != {want}")));
        }
    }
    read_pinned(repo, DBF1_RECORD_REL, DBF1_RECORD_SHA256)?;
    Ok(())
}

/// `load_dbf1(repo)`: the verified DBF-1 configuration (lock, record and config pins; fail closed).
pub fn load_dbf1(repo: &Path) -> ConfigResult<Dbf1Config> {
    verify_lock(repo)?;
    let raw = pyjson::loads(&pyjson::read_text_utf8(&read_pinned(repo, DBF1_CONFIG_REL, DBF1_CONFIG_SHA256)?)?)?;
    parse(raw)
}

/// Parse a DBF-1 config document (no pin check; [`load_dbf1`] is the production entry).
pub fn parse(raw: Value) -> ConfigResult<Dbf1Config> {
    if st(&raw, &["schema"])? != "abep_dbf1_config_v1" || st(&raw, &["baseline"])? != "DBF-1" {
        return Err(bad("schema / baseline id differ"));
    }
    parse_body(raw)
}

fn parse_body(raw: Value) -> ConfigResult<Dbf1Config> {
    let up = at(&raw, &["upstream"])?;
    let c = at(up, &["controller"])?;
    let upstream = Dbf1Upstream {
        design_id: st(up, &["design_id"])?,
        candidate: st(up, &["candidate"])?,
        area_m2: num(up, &["area_m2"])?,
        l_over_d: num(up, &["L_over_d"])?,
        phi: num(up, &["phi"])?,
        filter: st(up, &["filter"])?,
        compressor: st(up, &["compressor"])?,
        v_m3: num(up, &["V_m3"])?,
        p_set_pa: num(up, &["P_set_Pa"])?,
        wall: st(up, &["wall"])?,
        scenarios: strs(up, &["scenarios"])?,
        controller: Dbf1Controller {
            kp: num(c, &["Kp"])?,
            ti_s: num(c, &["Ti_s"])?,
            f_valve_hz: num(c, &["f_valve_hz"])?,
            authority: num(c, &["authority"])?,
        },
    };
    if upstream.scenarios.is_empty() || upstream.area_m2 <= 0.0 {
        return Err(bad("upstream: empty scenario set or non-positive area"));
    }
    let i = at(&raw, &["icp"])?;
    let icp = Dbf1Icp {
        radius_m: num(i, &["radius_m"])?,
        length_m: num(i, &["length_m"])?,
        collector_axial_length_m: num(i, &["collector_axial_length_m"])?,
        vessel_material: st(i, &["vessel_material"])?,
        collector_material: st(i, &["collector_material"])?,
        f_rf_hz: num(&raw, &["rf", "f_rf_hz"])?,
        p_fwd_envelope_w: pair(&raw, &["rf", "p_fwd_envelope_W"])?,
    };
    if !(icp.radius_m > 0.0 && icp.length_m > icp.collector_axial_length_m && icp.collector_axial_length_m > 0.0) {
        return Err(bad("icp: radius / length / collector length inconsistent"));
    }
    let d = at(&raw, &["host_drag"])?;
    let drag = Dbf1Drag {
        case_id: st(d, &["case_id"])?,
        a_ref_m2: num(d, &["a_ref_m2"])?,
        cd: num(d, &["cd"])?,
        intake_accounting: st(d, &["intake_accounting"])?,
        sensitivity_cases: strs(d, &["sensitivity_cases"])?,
    };
    let p = at(&raw, &["power_mass"])?;
    let groups = at(p, &["slots_by_group"])?.as_dict().ok_or_else(|| bad("power_mass.slots_by_group"))?;
    let mut slots_by_group = vec![];
    for (g, l) in groups.iter() {
        let names = l
            .as_list()
            .ok_or_else(|| bad("slots_by_group entry"))?
            .iter()
            .map(|x| x.as_str().map(str::to_string).ok_or_else(|| bad("slot name")))
            .collect::<ConfigResult<Vec<_>>>()?;
        slots_by_group.push((g.clone(), names));
    }
    let power_mass = Dbf1PowerMass {
        design_allocation_w: num(p, &["design_allocation_W"])?,
        common_allocation_w: num(p, &["common_allocation_W"])?,
        mass_margin_fraction: num(p, &["mass_margin_fraction"])?,
        nominal_dry_target_kg: num(p, &["nominal_dry_target_kg"])?,
        xe_reference_load_kg: num(p, &["xe_reference_load_kg"])?,
        wet_target_at_reference_kg: num(p, &["wet_target_at_reference_kg"])?,
        planning_nominal_dry_kg: num(p, &["planning_rollup", "nominal_dry_kg"])?,
        planning_dry_kg: num(p, &["planning_rollup", "dry_kg"])?,
        planning_wet_kg_at_reference: num(p, &["planning_rollup", "wet_kg_at_2kg"])?,
        slots_by_group,
    };
    Ok(Dbf1Config {
        geometry_id: st(&raw, &["h1", "geometry_id"])?,
        bz_shape_id: st(&raw, &["h1", "bz_shape_id"])?,
        b_peak_band_g: pair(&raw, &["h1", "B_peak_band_G"])?,
        v_d_band_v: pair(&raw, &["h1", "V_d_band_V"])?,
        upstream,
        icp,
        drag,
        power_mass,
        anode_primary: st(&raw, &["materials", "anode_primary"])?,
        anode_backup: st(&raw, &["materials", "anode_backup"])?,
        baseline_deficiencies: strs(&raw, &["baseline_deficiencies"])?,
        raw,
    })
}

// ------------------------------------------------------------------------------------------------------------- DBF-1.1

pub const DBF1_1_DIR: &str = "docs/baseline/DBF-1.1";
pub const DBF1_1_CONFIG_REL: &str = "docs/baseline/DBF-1.1/dbf1_1_config_v1.json";
pub const DBF1_1_CONFIG_SHA256: &str = "f16e07ba5b0c80e724dd53bb8d8a9b02298d8fb20ddac85a4f49ee799949d092";
pub const DBF1_1_LOCK_REL: &str = "docs/baseline/DBF-1.1/dbf1_1_lock_v1.json";
pub const DBF1_1_LOCK_SHA256: &str = "257e141ca252c3015b5bbd2fc953a1de688bc1606be36ebdf9fff8889307cfb8";
pub const DBF1_1_RECORD_REL: &str = "docs/baseline/DBF-1.1/dbf1_1_v1.json";
pub const DBF1_1_RECORD_SHA256: &str = "b8daa5bd5bb18b4fc92d6f65b0d93d0e70b33cd80d0f222cb9957ced3075c22b";
/// The approval of the DCR that created DBF-1.1 (lineage pin).
pub const DCR_DBF1_002_APPROVAL_SHA256: &str = "1718ac8061720959ea52e66e18723c23c3ece8d8c44fcfa41249d4f852c9bb55";

/// One DBF-1.1 B(z) profile file (HallThruster.jl centreline B_r(z), FE-derived), verified against its pinned sha256.
#[derive(Debug, Clone, PartialEq)]
pub struct BzProfile {
    /// "nominal" or "envelope".
    pub role: String,
    /// BP-LO / BP-HI (nominal) or CORNER-A / CORNER-B (shape-uncertainty envelope).
    pub id: String,
    pub file: String,
    pub sha256: String,
    pub ni_total_a: f64,
}

/// The machine-readable DBF-1.1 subset: every DBF-1 field (same structure) plus the pinned B(z) profiles.
#[derive(Debug, Clone, PartialEq)]
pub struct Dbf11Config {
    pub base: Dbf1Config,
    pub bz_profiles: Vec<BzProfile>,
    pub closed_deficiencies: Vec<String>,
    pub parent_lock_sha256: String,
    pub dcr_approval_sha256: String,
}

fn bad11(e: ConfigError) -> ConfigError {
    ConfigError::configuration(e.message.replace(DBF1_CONFIG_REL, DBF1_1_CONFIG_REL))
}

/// Verify the DBF-1.1 lock (pinned): config and record sha256, and the lineage to the DBF-1 lock and the DCR approval.
pub fn verify_lock_dbf1_1(repo: &Path) -> ConfigResult<()> {
    let lock = pyjson::loads(&pyjson::read_text_utf8(&read_pinned(repo, DBF1_1_LOCK_REL, DBF1_1_LOCK_SHA256)?)?)?;
    for (path, want) in [
        (&["files", "dbf1_1_config_v1.json"][..], DBF1_1_CONFIG_SHA256),
        (&["files", "dbf1_1_v1.json"][..], DBF1_1_RECORD_SHA256),
        (&["lineage", "parent_lock_sha256"][..], DBF1_LOCK_SHA256),
        (&["lineage", "dcr_approval_sha256"][..], DCR_DBF1_002_APPROVAL_SHA256),
    ] {
        if at(&lock, path).map_err(bad11)?.as_str() != Some(want) {
            return Err(ConfigError::configuration(format!("{DBF1_1_LOCK_REL}: {} != {want}", path.join("."))));
        }
    }
    read_pinned(repo, DBF1_1_RECORD_REL, DBF1_1_RECORD_SHA256)?;
    Ok(())
}

/// `load_dbf1_1(repo)`: the verified DBF-1.1 configuration (lock, record, config and every B(z) profile file pinned;
/// fail closed).
pub fn load_dbf1_1(repo: &Path) -> ConfigResult<Dbf11Config> {
    verify_lock_dbf1_1(repo)?;
    let raw = pyjson::loads(&pyjson::read_text_utf8(&read_pinned(repo, DBF1_1_CONFIG_REL, DBF1_1_CONFIG_SHA256)?)?)?;
    let c = parse_dbf1_1(raw)?;
    for p in &c.bz_profiles {
        read_pinned(repo, &p.file, &p.sha256)?;
    }
    Ok(c)
}

/// Parse a DBF-1.1 config document (no pin check; [`load_dbf1_1`] is the production entry).
pub fn parse_dbf1_1(raw: Value) -> ConfigResult<Dbf11Config> {
    let head = (|| -> ConfigResult<()> {
        if st(&raw, &["schema"])? != "abep_dbf1_config_v1" || st(&raw, &["baseline"])? != "DBF-1.1" {
            return Err(bad("schema / baseline id differ"));
        }
        if st(&raw, &["h1", "bz_shape_id"])? != "BZ-H1FE-V1" {
            return Err(bad("h1.bz_shape_id is not BZ-H1FE-V1"));
        }
        Ok(())
    })();
    head.map_err(bad11)?;
    let mut bz_profiles = vec![];
    let groups =
        at(&raw, &["h1", "bz_profiles"]).map_err(bad11)?.as_dict().ok_or_else(|| bad11(bad("h1.bz_profiles")))?;
    for (role, d) in groups.iter() {
        let d = d.as_dict().ok_or_else(|| bad11(bad("h1.bz_profiles entry")))?;
        for (id, p) in d.iter() {
            bz_profiles.push(BzProfile {
                role: role.clone(),
                id: id.clone(),
                file: st(p, &["file"]).map_err(bad11)?,
                sha256: st(p, &["sha256"]).map_err(bad11)?,
                ni_total_a: num(p, &["NI_total_A"]).map_err(bad11)?,
            });
        }
    }
    let has = |r: &str, i: &str| bz_profiles.iter().any(|p| p.role == r && p.id == i);
    if !(has("nominal", "BP-LO")
        && has("nominal", "BP-HI")
        && has("envelope", "CORNER-A")
        && has("envelope", "CORNER-B"))
    {
        return Err(bad11(bad("h1.bz_profiles must name nominal BP-LO / BP-HI and envelope CORNER-A / CORNER-B")));
    }
    let closed_deficiencies = strs(&raw, &["closed_deficiencies"]).map_err(bad11)?;
    let parent_lock_sha256 = st(&raw, &["lineage", "parent_lock_sha256"]).map_err(bad11)?;
    let dcr_approval_sha256 = st(&raw, &["lineage", "dcr_approval_sha256"]).map_err(bad11)?;
    if parent_lock_sha256 != DBF1_LOCK_SHA256 || dcr_approval_sha256 != DCR_DBF1_002_APPROVAL_SHA256 {
        return Err(bad11(bad("lineage does not name the DBF-1 lock / DCR-DBF1-002 approval")));
    }
    let base = parse_body(raw).map_err(bad11)?;
    Ok(Dbf11Config { base, bz_profiles, closed_deficiencies, parent_lock_sha256, dcr_approval_sha256 })
}

// ------------------------------------------------------------------------------------------------------------- DBF-1.2

pub const DBF1_2_DIR: &str = "docs/baseline/DBF-1.2";
pub const DBF1_2_CONFIG_REL: &str = "docs/baseline/DBF-1.2/dbf1_2_config_v1.json";
pub const DBF1_2_CONFIG_SHA256: &str = "@CONFIG@";
pub const DBF1_2_LOCK_REL: &str = "docs/baseline/DBF-1.2/dbf1_2_lock_v1.json";
pub const DBF1_2_LOCK_SHA256: &str = "@LOCK@";
pub const DBF1_2_RECORD_REL: &str = "docs/baseline/DBF-1.2/dbf1_2_v1.json";
pub const DBF1_2_RECORD_SHA256: &str = "@RECORD@";
/// The DCR-DBF1-001 resolution that proposes DBF-1.2 (lineage pin).
pub const DCR_DBF1_001_RESOLUTION_SHA256: &str = "@RESOLUTION@";

/// The DBF-1.2 variable-effective-capture mechanism (DBF1-IN-09).
#[derive(Debug, Clone, PartialEq)]
pub struct VariableCapture {
    pub mechanism: String,
    pub n_segments: usize,
    pub a_max_m2: f64,
    pub a_eff_used_m2: [f64; 2],
    pub open_fraction_used: [f64; 2],
    /// Closed-segment drag per unit area / q (analysis bound).
    pub c_closed: f64,
}

/// The DBF-1.2 AIR operating free-stream-flux window and altitude schedule (DBF1-OP-01 / 02).
#[derive(Debug, Clone, PartialEq)]
pub struct OperatingWindow {
    pub flux_coordinate: String,
    pub phi_lo_kg_m2_s: f64,
    pub phi_hi_kg_m2_s: f64,
    /// Admissible altitude nodes per registered condition (ECSS scenario), km.
    pub altitude_schedule: Vec<(String, Vec<f64>)>,
    pub uncovered_conditions: Vec<String>,
}

/// The machine-readable DBF-1.2 subset: every DBF-1.1 field (same structure, new upstream) plus the variable-capture
/// mechanism and the operating window.
#[derive(Debug, Clone, PartialEq)]
pub struct Dbf12Config {
    pub base: Dbf1Config,
    pub bz_profiles: Vec<BzProfile>,
    pub variable_capture: VariableCapture,
    pub window: OperatingWindow,
    pub closed_deficiencies: Vec<String>,
    pub transferred_deficiencies: Vec<String>,
    pub parent_lock_sha256: String,
    pub dcr_resolution_sha256: String,
}

fn bad12(e: ConfigError) -> ConfigError {
    ConfigError::configuration(e.message.replace(DBF1_CONFIG_REL, DBF1_2_CONFIG_REL))
}

/// Verify the DBF-1.2 lock (pinned): config and record sha256, and the lineage to the DBF-1.1 lock and the DCR-DBF1-001
/// resolution.
pub fn verify_lock_dbf1_2(repo: &Path) -> ConfigResult<()> {
    let lock = pyjson::loads(&pyjson::read_text_utf8(&read_pinned(repo, DBF1_2_LOCK_REL, DBF1_2_LOCK_SHA256)?)?)?;
    for (path, want) in [
        (&["files", "dbf1_2_config_v1.json"][..], DBF1_2_CONFIG_SHA256),
        (&["files", "dbf1_2_v1.json"][..], DBF1_2_RECORD_SHA256),
        (&["lineage", "parent_lock_sha256"][..], DBF1_1_LOCK_SHA256),
        (&["lineage", "dcr_resolution_sha256"][..], DCR_DBF1_001_RESOLUTION_SHA256),
    ] {
        if at(&lock, path).map_err(bad12)?.as_str() != Some(want) {
            return Err(ConfigError::configuration(format!("{DBF1_2_LOCK_REL}: {} != {want}", path.join("."))));
        }
    }
    read_pinned(repo, DBF1_2_RECORD_REL, DBF1_2_RECORD_SHA256)?;
    Ok(())
}

/// `load_dbf1_2(repo)`: the verified DBF-1.2 configuration (lock, record, config and every B(z) profile file pinned;
/// fail closed).
pub fn load_dbf1_2(repo: &Path) -> ConfigResult<Dbf12Config> {
    verify_lock_dbf1_2(repo)?;
    let raw = pyjson::loads(&pyjson::read_text_utf8(&read_pinned(repo, DBF1_2_CONFIG_REL, DBF1_2_CONFIG_SHA256)?)?)?;
    let c = parse_dbf1_2(raw)?;
    for p in &c.bz_profiles {
        read_pinned(repo, &p.file, &p.sha256)?;
    }
    Ok(c)
}

/// Parse a DBF-1.2 config document (no pin check; [`load_dbf1_2`] is the production entry).
pub fn parse_dbf1_2(raw: Value) -> ConfigResult<Dbf12Config> {
    let head = (|| -> ConfigResult<()> {
        if st(&raw, &["schema"])? != "abep_dbf1_config_v1" || st(&raw, &["baseline"])? != "DBF-1.2" {
            return Err(bad("schema / baseline id differ"));
        }
        if st(&raw, &["h1", "bz_shape_id"])? != "BZ-H1FE-V1" {
            return Err(bad("h1.bz_shape_id is not BZ-H1FE-V1"));
        }
        Ok(())
    })();
    head.map_err(bad12)?;
    let mut bz_profiles = vec![];
    let groups =
        at(&raw, &["h1", "bz_profiles"]).map_err(bad12)?.as_dict().ok_or_else(|| bad12(bad("h1.bz_profiles")))?;
    for (role, d) in groups.iter() {
        let d = d.as_dict().ok_or_else(|| bad12(bad("h1.bz_profiles entry")))?;
        for (id, p) in d.iter() {
            bz_profiles.push(BzProfile {
                role: role.clone(),
                id: id.clone(),
                file: st(p, &["file"]).map_err(bad12)?,
                sha256: st(p, &["sha256"]).map_err(bad12)?,
                ni_total_a: num(p, &["NI_total_A"]).map_err(bad12)?,
            });
        }
    }
    let vc = (|| -> ConfigResult<VariableCapture> {
        let v = at(&raw, &["variable_capture"])?;
        let n = num(v, &["N_segments"])?;
        if !(n >= 1.0 && n.fract() == 0.0) {
            return Err(bad("variable_capture.N_segments must be a positive integer"));
        }
        Ok(VariableCapture {
            mechanism: st(v, &["mechanism"])?,
            n_segments: n as usize,
            a_max_m2: num(v, &["A_max_m2"])?,
            a_eff_used_m2: pair(v, &["A_eff_used_m2"])?,
            open_fraction_used: pair(v, &["open_fraction_used"])?,
            c_closed: num(v, &["C_closed"])?,
        })
    })()
    .map_err(bad12)?;
    let window = (|| -> ConfigResult<OperatingWindow> {
        let w = at(&raw, &["operating_window"])?;
        let sched = at(w, &["altitude_schedule"])?.as_dict().ok_or_else(|| bad("operating_window.altitude_schedule"))?;
        let mut altitude_schedule = vec![];
        for (c, l) in sched.iter() {
            let nodes = l
                .as_list()
                .ok_or_else(|| bad("altitude_schedule entry"))?
                .iter()
                .map(|x| x.to_f64().map_err(|_| bad("altitude node")))
                .collect::<ConfigResult<Vec<f64>>>()?;
            altitude_schedule.push((c.clone(), nodes));
        }
        Ok(OperatingWindow {
            flux_coordinate: st(w, &["flux_coordinate"])?,
            phi_lo_kg_m2_s: num(w, &["Phi_lo_kg_m2_s"])?,
            phi_hi_kg_m2_s: num(w, &["Phi_hi_kg_m2_s"])?,
            altitude_schedule,
            uncovered_conditions: strs(w, &["uncovered_conditions"])?,
        })
    })()
    .map_err(bad12)?;
    let up_area = num(&raw, &["upstream", "area_m2"]).map_err(bad12)?;
    if !(window.phi_lo_kg_m2_s > 0.0 && window.phi_hi_kg_m2_s > window.phi_lo_kg_m2_s)
        || vc.a_max_m2 != up_area
        || !(vc.a_eff_used_m2[0] > 0.0 && vc.a_eff_used_m2[1] <= vc.a_max_m2 * (1.0 + 1e-12))
    {
        return Err(bad12(bad("variable_capture / operating_window inconsistent with the upstream aperture")));
    }
    let closed_deficiencies = strs(&raw, &["closed_deficiencies"]).map_err(bad12)?;
    let transferred_deficiencies = strs(&raw, &["transferred_deficiencies"]).map_err(bad12)?;
    let parent_lock_sha256 = st(&raw, &["lineage", "parent_lock_sha256"]).map_err(bad12)?;
    let dcr_resolution_sha256 = st(&raw, &["lineage", "dcr_resolution_sha256"]).map_err(bad12)?;
    if parent_lock_sha256 != DBF1_1_LOCK_SHA256 || dcr_resolution_sha256 != DCR_DBF1_001_RESOLUTION_SHA256 {
        return Err(bad12(bad("lineage does not name the DBF-1.1 lock / DCR-DBF1-001 resolution")));
    }
    let base = parse_body(raw).map_err(bad12)?;
    Ok(Dbf12Config {
        base,
        bz_profiles,
        variable_capture: vc,
        window,
        closed_deficiencies,
        transferred_deficiencies,
        parent_lock_sha256,
        dcr_resolution_sha256,
    })
}
