//! IF-CHEM-REG-v1 provider: the species and process registry of the active RF/ICP neutralizer chemistry
//! (`data/chemistry/icp/`, NP-ICP-CHEM-AIR v1 build plan BP-S1; consumer abep-icp, NP-ICP-NEUTRALIZER addendum 02).
//!
//! [`IcpChemRegistry::load`] reads everything through sha256 pins anchored on the consumer's pin of
//! `ICP_CHEM_PINNED.toml`, and refuses (MODEL_ERROR) what the contract's consumption rules and fail-closed tests refuse:
//!
//! | condition | contract item |
//! |---|---|
//! | lock, registry or data-file sha256 mismatch; a channel table not in the reuse pins | consumption rules, FC-CHEM-04 |
//! | reuse pins or a process (id, class, reaction, tier, status) different from the contract | RU-02, status vocabulary |
//! | a channel table without a `rate_validity_icp.toml` entry, or a mirror that differs from its Hall entry | FC-CHEM-01 |
//! | charge or nuclei not conserved; E_r below the formation-energy change | CV-01..CV-03, FC-CHEM-03 |
//! | an O-target process missing or pointing to non-O data | FC-CHEM-05, UE-05 |
//! | a scenario whose Hall configuration names other tables | NP-ICP-NEUTRALIZER addendum 02 (IDENTICAL) |
//!
//! Rates come only from [`crate::checked`] (EQ-06): [`ModeRegistry::direct_rate`] evaluates a registered cross-section
//! representation; a channel without one is INCOMPLETE_EVIDENCE. Nothing here comes from `abep_sim/plasma_chem.py`.

use crate::checked::{self, CrossSection, RateEvaluation, Validity};
use crate::dat::DatTable;
use crate::reference::Tail;
use crate::validity::RateValidityTable;
use abep_provenance::read_verified;
use abep_types::{AbepError, AbepResult};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use std::sync::Arc;

pub const REGISTRY_DIR: &str = "data/chemistry/icp";
pub const PINNED_FILE: &str = "ICP_CHEM_PINNED.toml";
/// sha256 of `data/chemistry/icp/ICP_CHEM_PINNED.toml` this build is registered against (labels abep-icp-air-0.0 /
/// abep-icp-xe-0.0). Every registry change (one table per commit) updates it.
pub const ICP_CHEM_PINNED_SHA256: &str = "074daff90b00dd1dd6ca776c845c7897bbd84b4217ec014e70fb374a16f16eb2";
pub const CONTRACT_ID: &str = "NP-ICP-CHEM-AIR";
pub const CONTRACT_LOCK: &str = "docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/prereg_lock_v1.json";
pub const CONTRACT_LOCK_SHA256: &str = "f42c22699a31acd4e29854823150d7b7c75b35eb8718fb90ade83bdd3d7e46ef";
const CONTRACT_PREREG: &str = "docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/prereg_v1.json";

/// Required fields per object; equal to the `required` lists of `registry_schema_v1.json` (checked by a test).
pub const REQUIRED_TOP: &[&str] = &[
    "schema",
    "mode",
    "label",
    "contract",
    "contract_lock",
    "contract_lock_sha256",
    "evidence_modes",
    "domain",
    "admission",
    "completeness_audit",
    "species",
    "process",
];
pub const REQUIRED_DOMAIN: &[&str] =
    &["id", "t_e_eV", "mean_energy_eV", "low_threshold_window_t_e_eV", "low_threshold_kinds", "p_icp_max_Pa", "eedf"];
pub const REQUIRED_ADMISSION: &[&str] = &["status", "gate", "reason_code", "today"];
pub const REQUIRED_CA: &[&str] = &["id", "status"];
pub const REQUIRED_NEG_CRIT: &[&str] = &["status", "scope"];
pub const REQUIRED_SPECIES_BOUND: &[&str] = &["id", "species", "status", "x_screen", "scope"];
pub const REQUIRED_SPECIES: &[&str] = &["id", "charge", "elements", "role", "status", "retention", "mass_source"];
pub const REQUIRED_PROCESS: &[&str] = &["id", "class", "reaction", "tier", "status", "ca_verdict"];
pub const REQUIRED_CHANNEL: &[&str] = &[
    "id",
    "process",
    "kind",
    "target",
    "data_target",
    "products",
    "electrons_out",
    "threshold_eV",
    "table",
    "table_sha256",
    "validity_entry",
    "representation_kind",
    "representation_status",
    "variant_role",
];
pub const REQUIRED_VARIANT_GROUP: &[&str] = &["id", "process", "members", "note"];
pub const REQUIRED_SCENARIO: &[&str] = &["id", "evidence_mode", "channels"];
pub const REQUIRED_ENVELOPE: &[&str] = &["id", "process", "members", "bound_basis"];

/// Process status vocabulary of the contract.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ProcessStatus {
    InRepoVerified,
    SourceIdentifiedToAcquire,
    IncompleteEvidence,
}

impl ProcessStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            ProcessStatus::InRepoVerified => "IN_REPO_VERIFIED",
            ProcessStatus::SourceIdentifiedToAcquire => "SOURCE_IDENTIFIED_TO_ACQUIRE",
            ProcessStatus::IncompleteEvidence => "INCOMPLETE_EVIDENCE",
        }
    }

    fn parse(s: &str) -> Option<Self> {
        [ProcessStatus::InRepoVerified, ProcessStatus::SourceIdentifiedToAcquire, ProcessStatus::IncompleteEvidence]
            .into_iter()
            .find(|x| x.as_str() == s)
    }
}

/// Electron-impact channel kinds of the registered representations.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ChannelKind {
    Ionization,
    DissociativeIonization,
    Dissociation,
    ExcitationElectronic,
    ExcitationVibrational,
    ExcitationRotational,
    ElasticMomentumTransfer,
}

impl ChannelKind {
    pub const ALL: [ChannelKind; 7] = [
        ChannelKind::Ionization,
        ChannelKind::DissociativeIonization,
        ChannelKind::Dissociation,
        ChannelKind::ExcitationElectronic,
        ChannelKind::ExcitationVibrational,
        ChannelKind::ExcitationRotational,
        ChannelKind::ElasticMomentumTransfer,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            ChannelKind::Ionization => "IONIZATION",
            ChannelKind::DissociativeIonization => "DISSOCIATIVE_IONIZATION",
            ChannelKind::Dissociation => "DISSOCIATION",
            ChannelKind::ExcitationElectronic => "EXCITATION_ELECTRONIC",
            ChannelKind::ExcitationVibrational => "EXCITATION_VIBRATIONAL",
            ChannelKind::ExcitationRotational => "EXCITATION_ROTATIONAL",
            ChannelKind::ElasticMomentumTransfer => "ELASTIC_MOMENTUM_TRANSFER",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VariantRole {
    Nominal,
    Variant,
    Sensitivity,
    UncertaintyVariant,
}

impl VariantRole {
    pub fn as_str(self) -> &'static str {
        match self {
            VariantRole::Nominal => "NOMINAL",
            VariantRole::Variant => "VARIANT",
            VariantRole::Sensitivity => "SENSITIVITY",
            VariantRole::UncertaintyVariant => "UNCERTAINTY_VARIANT",
        }
    }
}

/// A species of the registry. `mass_amu` is None where no mass is registered (no channel uses the species yet).
#[derive(Debug, Clone, PartialEq)]
pub struct Species {
    pub id: String,
    pub charge: i32,
    pub elements: BTreeMap<String, u32>,
    pub role: String,
    pub status: String,
    pub retention: String,
    pub mass_amu: Option<f64>,
    pub mass_source: String,
}

/// A contract process (status exactly as the contract records it).
#[derive(Debug, Clone, PartialEq)]
pub struct Process {
    pub id: String,
    pub class: String,
    pub reaction: String,
    pub target: Option<String>,
    pub tier: String,
    pub status: ProcessStatus,
    pub ca_verdict: String,
}

impl Process {
    pub fn is_tier1(&self) -> bool {
        self.tier.starts_with('1')
    }
}

/// The direct-rate source representation of a channel (EQ-06, IX-01).
#[derive(Debug, Clone, PartialEq)]
pub enum Representation {
    CrossSection {
        file: String,
        sha256: String,
        xs: Arc<CrossSection>,
    },
    /// No registered representation: no direct rate exists (INCOMPLETE_EVIDENCE).
    NotRegistered {
        kind: String,
        gap: String,
    },
}

/// One registered representation of a process: e + target -> products + electrons_out e.
#[derive(Debug, Clone, PartialEq)]
pub struct Channel {
    pub id: String,
    pub process: String,
    pub kind: ChannelKind,
    pub target: String,
    pub products: BTreeMap<String, u32>,
    pub electrons_out: u32,
    /// E_r [eV], equal to the `.dat` header.
    pub threshold_ev: f64,
    pub table: String,
    pub table_sha256: String,
    /// `rate_validity_icp.toml` key.
    pub validity_entry: String,
    pub validity: Validity,
    pub representation: Representation,
    pub variant_role: VariantRole,
    pub variant_group: Option<String>,
}

impl Channel {
    /// The `.dat` file name (key of the validity table, HallThruster `rate_coeff_file`).
    pub fn table_file(&self) -> &str {
        self.table.rsplit('/').next().unwrap_or(&self.table)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Scenario {
    pub id: String,
    pub evidence_mode: String,
    pub channels: Vec<String>,
    pub hall_config: Option<(String, String)>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct VariantGroup {
    pub id: String,
    pub process: String,
    pub members: Vec<String>,
    pub note: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SpeciesBound {
    pub id: String,
    pub species: String,
    pub status: String,
    pub x_screen: f64,
    pub scope: String,
}

/// D-CHEM (contract domain).
#[derive(Debug, Clone, PartialEq)]
pub struct Domain {
    pub t_e_ev: [f64; 2],
    pub mean_energy_ev: [f64; 2],
    pub low_threshold_window_t_e_ev: [f64; 2],
    pub low_threshold_kinds: Vec<ChannelKind>,
    pub p_icp_max_pa: f64,
}

/// The registry of one mode (AIR or XE).
#[derive(Debug, Clone, PartialEq)]
pub struct ModeRegistry {
    pub mode: String,
    pub label: String,
    pub registry_file: String,
    pub registry_sha256: String,
    pub evidence_modes: Vec<String>,
    pub domain: Domain,
    pub admission_status: String,
    pub admission_reason_code: String,
    pub admission_today: String,
    pub completeness_audit_status: String,
    pub neg_crit_status: Option<String>,
    pub species_bounds: Vec<SpeciesBound>,
    pub species: Vec<Species>,
    pub processes: Vec<Process>,
    pub channels: Vec<Channel>,
    pub variant_groups: Vec<VariantGroup>,
    pub scenarios: Vec<Scenario>,
}

impl ModeRegistry {
    pub fn is_admitted(&self) -> bool {
        self.admission_status == "ADMITTED"
    }

    pub fn species(&self, id: &str) -> Option<&Species> {
        self.species.iter().find(|s| s.id == id)
    }

    pub fn process(&self, id: &str) -> Option<&Process> {
        self.processes.iter().find(|p| p.id == id)
    }

    pub fn channel(&self, id: &str) -> Option<&Channel> {
        self.channels.iter().find(|c| c.id == id)
    }

    /// The channel registered for a `.dat` file name, if any.
    pub fn channel_for_table(&self, file: &str) -> Option<&Channel> {
        self.channels.iter().find(|c| c.table_file() == file)
    }

    pub fn scenario(&self, id: &str) -> Option<&Scenario> {
        self.scenarios.iter().find(|s| s.id == id)
    }

    /// Tier-1 processes that are not IN_REPO_VERIFIED (the admission gaps of AD-AIR-03 / AD-XE-02).
    pub fn tier1_gaps(&self) -> Vec<&Process> {
        self.processes.iter().filter(|p| p.is_tier1() && p.status != ProcessStatus::InRepoVerified).collect()
    }

    /// The Maxwellian rate of a channel at T_e through the admitted integrator (EQ-06): MODEL_ERROR / OUT_OF_DOMAIN /
    /// INCOMPLETE_EVIDENCE exactly as [`checked::maxwellian_rate`]; a channel without a registered representation is
    /// INCOMPLETE_EVIDENCE. The D-CHEM domain is the consumer's check.
    pub fn direct_rate(&self, channel: &Channel, t_e_ev: f64) -> AbepResult<RateEvaluation> {
        match &channel.representation {
            Representation::CrossSection { xs, .. } => checked::maxwellian_rate(xs, t_e_ev, &channel.validity),
            Representation::NotRegistered { gap, .. } => Err(AbepError::IncompleteEvidence {
                message: format!("{}: no registered direct-rate representation: {gap}", channel.id),
            }),
        }
    }

    /// Formation energy of each species relative to the ground-state neutrals (EQ-18): neutrals 0, an ion the least
    /// energy over the registered ionization routes (headers). Species without a route are absent.
    pub fn formation_energies(&self) -> BTreeMap<String, f64> {
        formation_energies(&self.species, &self.channels)
    }
}

/// The whole registry: both modes, the validity table and the reuse pins, with every file read.
#[derive(Debug, Clone, PartialEq)]
pub struct IcpChemRegistry {
    pub pinned_sha256: String,
    pub contract_lock_sha256: String,
    pub air: ModeRegistry,
    pub xe: ModeRegistry,
    pub validity: RateValidityTable,
    /// (path, sha256, pinned by) of every file read.
    pub files_read: Vec<(String, String, String)>,
}

fn model(m: impl Into<String>) -> AbepError {
    AbepError::Model { message: m.into() }
}

fn schema(path: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.to_string(), message: m.into() }
}

fn text(path: &str, bytes: Vec<u8>) -> AbepResult<String> {
    String::from_utf8(bytes).map_err(|e| schema(path, e.to_string()))
}

fn toml_of(path: &str, bytes: Vec<u8>) -> AbepResult<toml::Table> {
    text(path, bytes)?.parse().map_err(|e: toml::de::Error| schema(path, e.to_string()))
}

fn json_of(path: &str, bytes: &[u8]) -> AbepResult<Value> {
    serde_json::from_slice(bytes).map_err(|e| schema(path, e.to_string()))
}

/// Field access on a parsed TOML table, with errors naming the file and object.
struct Obj<'a> {
    t: &'a toml::Table,
    origin: &'a str,
    what: String,
}

impl<'a> Obj<'a> {
    fn new(t: &'a toml::Table, origin: &'a str, what: impl Into<String>, required: &[&str]) -> AbepResult<Self> {
        let o = Obj { t, origin, what: what.into() };
        for k in required {
            if !t.contains_key(*k) {
                return Err(o.err(format!("missing required field {k}")));
            }
        }
        Ok(o)
    }

    fn err(&self, m: String) -> AbepError {
        schema(self.origin, format!("{}: {m}", self.what))
    }

    fn s(&self, k: &str) -> AbepResult<String> {
        self.t.get(k).and_then(|v| v.as_str()).map(String::from).ok_or_else(|| self.err(format!("{k} is not a string")))
    }

    fn opt_s(&self, k: &str) -> AbepResult<Option<String>> {
        self.t.get(k).map(|_| self.s(k)).transpose()
    }

    fn f(&self, k: &str) -> AbepResult<f64> {
        let v = self.t.get(k).ok_or_else(|| self.err(format!("missing {k}")))?;
        let x = v
            .as_float()
            .or_else(|| v.as_integer().map(|i| i as f64))
            .ok_or_else(|| self.err(format!("{k} is not a number")))?;
        if !x.is_finite() {
            return Err(self.err(format!("{k} is not finite")));
        }
        Ok(x)
    }

    fn i(&self, k: &str) -> AbepResult<i64> {
        self.t.get(k).and_then(|v| v.as_integer()).ok_or_else(|| self.err(format!("{k} is not an integer")))
    }

    fn pair(&self, k: &str) -> AbepResult<[f64; 2]> {
        let a = self.t.get(k).and_then(|v| v.as_array()).ok_or_else(|| self.err(format!("{k} is not an array")))?;
        let xs: Vec<f64> = a.iter().filter_map(|v| v.as_float()).collect();
        match xs.as_slice() {
            [lo, hi] if lo.is_finite() && hi.is_finite() && lo < hi => Ok([*lo, *hi]),
            _ => Err(self.err(format!("{k} must be an increasing pair of floats"))),
        }
    }

    fn strings(&self, k: &str) -> AbepResult<Vec<String>> {
        let a = self.t.get(k).and_then(|v| v.as_array()).ok_or_else(|| self.err(format!("{k} is not an array")))?;
        a.iter().map(|v| v.as_str().map(String::from).ok_or_else(|| self.err(format!("{k}: not a string")))).collect()
    }

    fn counts(&self, k: &str) -> AbepResult<BTreeMap<String, u32>> {
        let t = self.t.get(k).and_then(|v| v.as_table()).ok_or_else(|| self.err(format!("{k} is not a table")))?;
        let mut out = BTreeMap::new();
        for (name, v) in t {
            let n = v.as_integer().filter(|n| *n >= 1).ok_or_else(|| self.err(format!("{k}.{name} must be >= 1")))?;
            out.insert(name.clone(), u32::try_from(n).map_err(|_| self.err(format!("{k}.{name}")))?);
        }
        Ok(out)
    }

    fn table(&self, k: &str, required: &[&str]) -> AbepResult<Obj<'a>> {
        let t = self.t.get(k).and_then(|v| v.as_table()).ok_or_else(|| self.err(format!("{k} is not a table")))?;
        Obj::new(t, self.origin, format!("[{k}]"), required)
    }

    fn array_of(&self, k: &str, required: &[&str]) -> AbepResult<Vec<Obj<'a>>> {
        let Some(v) = self.t.get(k) else { return Ok(Vec::new()) };
        let a = v.as_array().ok_or_else(|| self.err(format!("{k} is not an array of tables")))?;
        a.iter()
            .enumerate()
            .map(|(i, x)| {
                let t = x.as_table().ok_or_else(|| self.err(format!("{k}[{i}] is not a table")))?;
                let id = t.get("id").and_then(|v| v.as_str()).unwrap_or("?");
                Obj::new(t, self.origin, format!("{k}[{i}] {id}"), required)
            })
            .collect()
    }
}

fn kind_of(s: &str) -> Option<ChannelKind> {
    ChannelKind::ALL.into_iter().find(|k| k.as_str() == s)
}

fn role_of(s: &str) -> Option<VariantRole> {
    [VariantRole::Nominal, VariantRole::Variant, VariantRole::Sensitivity, VariantRole::UncertaintyVariant]
        .into_iter()
        .find(|r| r.as_str() == s)
}

fn formation_energies(species: &[Species], channels: &[Channel]) -> BTreeMap<String, f64> {
    let mut eps: BTreeMap<String, f64> =
        species.iter().filter(|s| s.charge == 0).map(|s| (s.id.clone(), 0.0)).collect();
    let routes: Vec<&Channel> = channels.iter().filter(|c| c.kind == ChannelKind::Ionization).collect();
    for _ in 0..=routes.len() {
        let mut changed = false;
        for c in &routes {
            let (Some(&e_t), Some((p, _))) = (eps.get(&c.target), c.products.iter().next()) else { continue };
            let cand = e_t + c.threshold_ev;
            if eps.get(p).is_none_or(|&e| cand < e) {
                eps.insert(p.clone(), cand);
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    eps
}

/// CV-01..CV-03 for one channel; the reasons it violates them.
fn conservation_violations(c: &Channel, species: &[Species], eps: &BTreeMap<String, f64>) -> Vec<String> {
    let mut v = Vec::new();
    let get = |id: &str| species.iter().find(|s| s.id == id);
    let Some(t) = get(&c.target) else {
        return vec![format!("unknown target {}", c.target)];
    };
    let mut z_out = 0i64;
    let mut nuclei: BTreeMap<String, u32> = BTreeMap::new();
    let mut n_ions = 0u32;
    for (p, n) in &c.products {
        let Some(s) = get(p) else {
            v.push(format!("unknown product {p}"));
            continue;
        };
        z_out += i64::from(s.charge) * i64::from(*n);
        if s.charge != 0 {
            n_ions += n;
        }
        for (el, k) in &s.elements {
            *nuclei.entry(el.clone()).or_insert(0) += k * n;
        }
    }
    if !v.is_empty() {
        return v;
    }
    // e + target -> products + electrons_out e: Z_t - 1 = sum Z_p - electrons_out (CV-01).
    if i64::from(t.charge) - 1 != z_out - i64::from(c.electrons_out) {
        v.push(format!(
            "charge not conserved (target {}, products {z_out}, electrons out {})",
            t.charge, c.electrons_out
        ));
    }
    if nuclei != t.elements {
        v.push("nuclei not conserved (CV-02)".into());
    }
    let n_products: u32 = c.products.values().sum();
    let shape = match c.kind {
        ChannelKind::Ionization => n_products == 1 && z_out > i64::from(t.charge),
        ChannelKind::DissociativeIonization => n_products >= 2 && n_ions >= 1 && z_out > i64::from(t.charge),
        ChannelKind::Dissociation => n_products >= 2 && z_out == i64::from(t.charge),
        _ => c.products.len() == 1 && c.products.get(&c.target) == Some(&1) && c.electrons_out == 1,
    };
    if !shape {
        v.push(format!("products do not match kind {}", c.kind.as_str()));
    }
    if !(c.threshold_ev.is_finite() && c.threshold_ev >= 0.0) {
        v.push("threshold_eV must be finite and >= 0".into());
    }
    // CV-03: E_r >= formation-energy change of the products (ground-state-neutral reference, EQ-18).
    let form = |id: &str| eps.get(id).copied();
    if let Some(e_t) = form(&c.target) {
        let mut sum = Some(0.0);
        for (p, n) in &c.products {
            sum = sum.zip(form(p)).map(|(a, e)| a + f64::from(*n) * e);
        }
        match sum {
            // Headers are decimal literals: their sums are compared within 1e-12 relative (IEEE rounding only).
            Some(s) if c.threshold_ev < (s - e_t) - 1e-12 * (s - e_t).abs().max(1.0) => {
                v.push(format!("E_r {} eV below the formation-energy change {} eV (CV-03)", c.threshold_ev, s - e_t))
            }
            Some(_) => {}
            None => v.push("a product has no formation energy (no registered ionization route)".into()),
        }
    } else {
        v.push(format!("target {} has no formation energy (no registered ionization route)", c.target));
    }
    v
}

/// Load-time context shared by both modes.
struct Ctx<'a> {
    root: &'a Path,
    files: Vec<(String, String, String)>,
}

impl Ctx<'_> {
    fn read(&mut self, rel: &str, sha: &str, by: &str) -> AbepResult<Vec<u8>> {
        let b = read_verified(&self.root.join(rel), sha)?;
        self.files.push((rel.to_string(), sha.to_string(), by.to_string()));
        Ok(b)
    }
}

impl IcpChemRegistry {
    /// Load and verify the registry under `root`; `pinned_sha256` is the consumer's pin of `ICP_CHEM_PINNED.toml`.
    pub fn load(root: &Path, pinned_sha256: &str) -> AbepResult<Self> {
        let mut cx = Ctx { root, files: Vec::new() };
        let pinned_rel = format!("{REGISTRY_DIR}/{PINNED_FILE}");
        let pinned = toml_of(&pinned_rel, cx.read(&pinned_rel, pinned_sha256, "consumer anchor")?)?;
        let po = Obj::new(&pinned, &pinned_rel, "ICP_CHEM_PINNED", &["contract", "files", "air", "xe"])?;
        let contract = po.table("contract", &["id", "lock", "lock_sha256", "interface"])?;
        if contract.s("id")? != CONTRACT_ID
            || contract.s("lock")? != CONTRACT_LOCK
            || contract.s("lock_sha256")? != CONTRACT_LOCK_SHA256
            || contract.s("interface")? != "IF-CHEM-REG-v1"
        {
            return Err(model(format!("{pinned_rel}: not the NP-ICP-CHEM-AIR v1 lock / IF-CHEM-REG-v1")));
        }
        let lock = json_of(CONTRACT_LOCK, &cx.read(CONTRACT_LOCK, CONTRACT_LOCK_SHA256, &pinned_rel)?)?;
        let prereg_sha = lock.pointer("/files/prereg_v1.json").and_then(Value::as_str).unwrap_or_default().to_string();
        let prereg = json_of(CONTRACT_PREREG, &cx.read(CONTRACT_PREREG, &prereg_sha, CONTRACT_LOCK)?)?;
        let file_pins =
            po.t.get("files").and_then(|v| v.as_table()).ok_or_else(|| po.err("files is not a table".into()))?;
        let pin = |name: &str| -> AbepResult<String> {
            file_pins
                .get(name)
                .and_then(|v| v.as_str())
                .map(String::from)
                .ok_or_else(|| model(format!("{pinned_rel}: {name} is not pinned")))
        };

        // Reuse pins: the contract's, verbatim, every file verified (FC-CHEM-04).
        let rp_rel = format!("{REGISTRY_DIR}/reuse_pins.json");
        let rp = json_of(&rp_rel, &cx.read(&rp_rel, &pin("reuse_pins.json")?, &pinned_rel)?)?;
        let mut table_pins: BTreeMap<String, String> = BTreeMap::new();
        let strip = |v: &Value, keys: &[&str]| -> Vec<Value> {
            v.as_array()
                .into_iter()
                .flatten()
                .map(|e| {
                    Value::Object(keys.iter().filter_map(|k| e.get(*k).map(|x| (k.to_string(), x.clone()))).collect())
                })
                .collect()
        };
        let reg_hall = strip(&rp["hall_propellant_tables"], &["path", "sha256", "source_file_sha256"]);
        let con_hall =
            strip(&prereg["reuse_pins"]["hall_propellant_tables"], &["path", "sha256", "source_file_sha256"]);
        if reg_hall.is_empty()
            || reg_hall != con_hall
            || rp["o_o2_v0_files"] != prereg["reuse_pins"]["o_o2_v0_files"]
            || rp["excluded"] != prereg["reuse_pins"]["excluded"]
        {
            return Err(model(format!("{rp_rel}: reuse pins differ from the contract's (RU-02)")));
        }
        for e in rp["hall_propellant_tables"].as_array().into_iter().flatten() {
            let (Some(p), Some(s), Some(sf), Some(ss)) =
                (e["path"].as_str(), e["sha256"].as_str(), e["source_file"].as_str(), e["source_file_sha256"].as_str())
            else {
                return Err(schema(&rp_rel, "hall_propellant_tables entry without path / sha256 / source_file"));
            };
            if sf != format!("{p}.source") {
                return Err(schema(&rp_rel, format!("{p}: source_file must be the table's .source")));
            }
            cx.read(p, s, &rp_rel)?;
            cx.read(sf, ss, &rp_rel)?;
            table_pins.insert(p.to_string(), s.to_string());
        }
        for e in rp["o_o2_v0_files"].as_array().into_iter().flatten() {
            let (Some(p), Some(s)) = (e["path"].as_str(), e["sha256"].as_str()) else {
                return Err(schema(&rp_rel, "o_o2_v0_files entry without path / sha256"));
            };
            cx.read(p, s, &rp_rel)?;
            table_pins.insert(p.to_string(), s.to_string());
        }

        // Validity table: mirrored entries must equal their Hall source (FC-CHEM-01 semantics on use).
        let rv_rel = format!("{REGISTRY_DIR}/rate_validity_icp.toml");
        let rv_bytes = cx.read(&rv_rel, &pin("rate_validity_icp.toml")?, &pinned_rel)?;
        let rv_text = text(&rv_rel, rv_bytes)?;
        let validity = RateValidityTable::parse(&rv_text, &rv_rel)?;
        let rv_toml: toml::Table = rv_text.parse().map_err(|e: toml::de::Error| schema(&rv_rel, e.to_string()))?;
        let mut mirrors: BTreeMap<(String, String), RateValidityTable> = BTreeMap::new();
        for (file, e) in &rv_toml {
            let o = Obj::new(e.as_table().ok_or_else(|| schema(&rv_rel, file))?, &rv_rel, file.clone(), &[])?;
            let (Some(src), Some(src_sha)) = (o.opt_s("mirrors")?, o.opt_s("mirrors_sha256")?) else { continue };
            let key = (src.clone(), src_sha.clone());
            if !mirrors.contains_key(&key) {
                let b = text(&src, cx.read(&src, &src_sha, &rv_rel)?)?;
                mirrors.insert(key.clone(), RateValidityTable::parse(&b, &src)?);
            }
            if mirrors[&key].validity(file) != validity.validity(file) {
                return Err(model(format!("{rv_rel}: {file} differs from the entry it mirrors in {src}")));
            }
        }

        let mut air = None;
        let mut xe = None;
        for (mode, key) in [("AIR", "air"), ("XE", "xe")] {
            let m = po.table(key, &["label", "registry", "status"])?;
            let reg_name = m.s("registry")?;
            let reg_sha = pin(&reg_name)?;
            let reg = load_mode(&mut cx, &reg_name, &reg_sha, &pinned_rel, &prereg, &table_pins, &validity)?;
            if reg.mode != mode || reg.label != m.s("label")? || reg.admission_status != m.s("status")? {
                return Err(model(format!("{pinned_rel}: [{key}] does not match {reg_name}")));
            }
            if mode == "AIR" {
                air = Some(reg);
            } else {
                xe = Some(reg);
            }
        }
        let (air, xe) = (air.expect("loaded"), xe.expect("loaded"));
        // Every contract process appears in exactly one mode registry.
        let contract_ids: BTreeSet<&str> =
            prereg["processes"].as_array().into_iter().flatten().filter_map(|p| p["id"].as_str()).collect();
        let reg_ids: BTreeSet<&str> = air.processes.iter().chain(&xe.processes).map(|p| p.id.as_str()).collect();
        if contract_ids != reg_ids {
            return Err(model("the registries do not list exactly the contract's processes".to_string()));
        }
        Ok(IcpChemRegistry {
            pinned_sha256: pinned_sha256.to_string(),
            contract_lock_sha256: CONTRACT_LOCK_SHA256.to_string(),
            air,
            xe,
            validity,
            files_read: cx.files,
        })
    }

    pub fn mode(&self, mode: &str) -> Option<&ModeRegistry> {
        match mode {
            "AIR" => Some(&self.air),
            "XE" => Some(&self.xe),
            _ => None,
        }
    }
}

fn load_mode(
    cx: &mut Ctx,
    name: &str,
    sha: &str,
    pinned_rel: &str,
    prereg: &Value,
    table_pins: &BTreeMap<String, String>,
    validity: &RateValidityTable,
) -> AbepResult<ModeRegistry> {
    let rel = format!("{REGISTRY_DIR}/{name}");
    let t = toml_of(&rel, cx.read(&rel, sha, pinned_rel)?)?;
    let o = Obj::new(&t, &rel, "registry", REQUIRED_TOP)?;
    if o.s("schema")? != "IF-CHEM-REG-v1"
        || o.s("contract")? != CONTRACT_ID
        || o.s("contract_lock")? != CONTRACT_LOCK
        || o.s("contract_lock_sha256")? != CONTRACT_LOCK_SHA256
    {
        return Err(model(format!("{rel}: not an IF-CHEM-REG-v1 registry of the NP-ICP-CHEM-AIR v1 lock")));
    }
    let mode = o.s("mode")?;
    let d = o.table("domain", REQUIRED_DOMAIN)?;
    let domain = Domain {
        t_e_ev: d.pair("t_e_eV")?,
        mean_energy_ev: d.pair("mean_energy_eV")?,
        low_threshold_window_t_e_ev: d.pair("low_threshold_window_t_e_eV")?,
        low_threshold_kinds: d
            .strings("low_threshold_kinds")?
            .iter()
            .map(|k| kind_of(k).ok_or_else(|| d.err(format!("unknown kind {k}"))))
            .collect::<AbepResult<_>>()?,
        p_icp_max_pa: d.f("p_icp_max_Pa")?,
    };
    let adm = o.table("admission", REQUIRED_ADMISSION)?;
    let ca = o.table("completeness_audit", REQUIRED_CA)?;
    let neg_crit = match o.t.get("neg_crit") {
        Some(_) => Some(o.table("neg_crit", REQUIRED_NEG_CRIT)?.s("status")?),
        None => None,
    };
    let species_bounds = o
        .array_of("species_bound", REQUIRED_SPECIES_BOUND)?
        .iter()
        .map(|b| {
            Ok(SpeciesBound {
                id: b.s("id")?,
                species: b.s("species")?,
                status: b.s("status")?,
                x_screen: b.f("x_screen")?,
                scope: b.s("scope")?,
            })
        })
        .collect::<AbepResult<Vec<_>>>()?;
    let mut species = Vec::new();
    for s in o.array_of("species", REQUIRED_SPECIES)? {
        let mass_amu = match s.t.get("mass_amu") {
            Some(_) => {
                let m = s.f("mass_amu")?;
                if m <= 0.0 {
                    return Err(s.err("mass_amu must be > 0".into()));
                }
                Some(m)
            }
            None => None,
        };
        species.push(Species {
            id: s.s("id")?,
            charge: i32::try_from(s.i("charge")?).map_err(|_| s.err("charge".into()))?,
            elements: s.counts("elements")?,
            role: s.s("role")?,
            status: s.s("status")?,
            retention: s.s("retention")?,
            mass_amu,
            mass_source: s.s("mass_source")?,
        });
    }
    let mut seen = BTreeSet::new();
    if let Some(dup) = species.iter().find(|s| !seen.insert(s.id.as_str())) {
        return Err(model(format!("{rel}: duplicate species {}", dup.id)));
    }

    // Processes: exactly the contract's processes of this mode, with the contract's text and status.
    let contract: BTreeMap<&str, &Value> = prereg["processes"]
        .as_array()
        .into_iter()
        .flatten()
        .filter(|p| p["mode"].as_str() == Some(mode.as_str()))
        .filter_map(|p| p["id"].as_str().map(|id| (id, p)))
        .collect();
    let mut processes = Vec::new();
    for p in o.array_of("process", REQUIRED_PROCESS)? {
        let id = p.s("id")?;
        let Some(c) = contract.get(id.as_str()) else {
            return Err(model(format!("{rel}: process {id} is not a {mode} process of the contract")));
        };
        let status_s = p.s("status")?;
        let same = |k: &str, ck: &str| c[ck].as_str() == Some(p.s(k).unwrap_or_default().as_str());
        if !(same("class", "process_class") && same("reaction", "reaction") && same("tier", "tier"))
            || c["status"].as_str() != Some(status_s.as_str())
        {
            return Err(model(format!(
                "{rel}: process {id} differs from the contract (class, reaction, tier or status)"
            )));
        }
        let target = p.opt_s("target")?;
        if let Some(tg) = &target {
            if !species.iter().any(|s| &s.id == tg) {
                return Err(model(format!("{rel}: process {id} target {tg} is not a registered species")));
            }
        }
        processes.push(Process {
            id,
            class: p.s("class")?,
            reaction: p.s("reaction")?,
            target,
            tier: p.s("tier")?,
            status: ProcessStatus::parse(&status_s).ok_or_else(|| p.err(format!("status {status_s}")))?,
            ca_verdict: p.s("ca_verdict")?,
        });
    }
    let ids: BTreeSet<&str> = processes.iter().map(|p| p.id.as_str()).collect();
    if ids.len() != processes.len() || ids != contract.keys().copied().collect::<BTreeSet<_>>() {
        return Err(model(format!("{rel}: the {mode} processes are not exactly the contract's, once each")));
    }
    // FC-CHEM-05: AIR keeps atomic O's own ionization, momentum transfer and excitation processes.
    if mode == "AIR" {
        for id in ["AIR-ION-01", "AIR-EL-04", "AIR-EXC-09"] {
            if processes.iter().find(|p| p.id == id).and_then(|p| p.target.as_deref()) != Some("O") {
                return Err(model(format!("{rel}: {id} must be registered with target O (FC-CHEM-05)")));
            }
        }
    }

    let mut channels = Vec::new();
    for c in o.array_of("channel", REQUIRED_CHANNEL)? {
        let id = c.s("id")?;
        let process = c.s("process")?;
        let Some(proc_) = processes.iter().find(|p| p.id == process) else {
            return Err(model(format!("{rel}: channel {id} names unknown process {process}")));
        };
        let target = c.s("target")?;
        let data_target = c.s("data_target")?;
        if data_target != target || proc_.target.as_ref().is_some_and(|t| t != &target) {
            return Err(model(format!(
                "{rel}: channel {id}: data for {data_target} used for target {target} of {process} (FC-CHEM-05, UE-05)"
            )));
        }
        let table = c.s("table")?;
        let table_sha256 = c.s("table_sha256")?;
        if table_pins.get(&table) != Some(&table_sha256) {
            return Err(model(format!("{rel}: channel {id}: {table} is not a registered file at that sha256")));
        }
        let kind_s = c.s("kind")?;
        let kind = kind_of(&kind_s).ok_or_else(|| c.err(format!("kind {kind_s}")))?;
        let threshold_ev = c.f("threshold_eV")?;
        let dat = DatTable::read_verified(&cx.root.join(&table), &table_sha256)?;
        if dat.threshold_ev.to_bits() != threshold_ev.to_bits() {
            return Err(model(format!("{rel}: channel {id}: threshold {threshold_ev} eV is not the table header")));
        }
        let validity_entry = c.s("validity_entry")?;
        if Some(validity_entry.as_str()) != table.rsplit('/').next() {
            return Err(model(format!("{rel}: channel {id}: validity_entry must be the table file name")));
        }
        let v = validity.validity(&validity_entry);
        if v == Validity::MissingEntry {
            return Err(model(format!(
                "{rel}: channel {id}: {validity_entry} has no rate_validity_icp.toml entry (FC-CHEM-01)"
            )));
        }
        let rep_kind = c.s("representation_kind")?;
        let representation = match c.s("representation_status")?.as_str() {
            "REGISTERED" => {
                if rep_kind != "CROSS_SECTION" {
                    return Err(model(format!("{rel}: channel {id}: no admitted evaluator for {rep_kind}")));
                }
                let file = c.s("representation")?;
                let sha = c.s("representation_sha256")?;
                let path = format!("{REGISTRY_DIR}/{file}");
                let xs = load_xs(&path, &cx.read(&path, &sha, &rel)?, &table, &table_sha256, threshold_ev)?;
                Representation::CrossSection { file, sha256: sha, xs: Arc::new(xs) }
            }
            "INCOMPLETE_EVIDENCE" => Representation::NotRegistered { kind: rep_kind, gap: c.s("representation_gap")? },
            other => return Err(c.err(format!("representation_status {other}"))),
        };
        let role_s = c.s("variant_role")?;
        channels.push(Channel {
            id,
            process,
            kind,
            target,
            products: c.counts("products")?,
            electrons_out: u32::try_from(c.i("electrons_out")?).map_err(|_| c.err("electrons_out".into()))?,
            threshold_ev,
            table,
            table_sha256,
            validity_entry,
            validity: v,
            representation,
            variant_role: role_of(&role_s).ok_or_else(|| c.err(format!("variant_role {role_s}")))?,
            variant_group: c.opt_s("variant_group")?,
        });
    }
    let mut seen = BTreeSet::new();
    if let Some(dup) = channels.iter().find(|c| !seen.insert(c.id.as_str())) {
        return Err(model(format!("{rel}: duplicate channel {}", dup.id)));
    }
    // CV-01..CV-03 (FC-CHEM-03).
    let eps = formation_energies(&species, &channels);
    for c in &channels {
        let v = conservation_violations(c, &species, &eps);
        if !v.is_empty() {
            return Err(model(format!("{rel}: channel {}: {}", c.id, v.join("; "))));
        }
    }
    let mut variant_groups = Vec::new();
    for g in o.array_of("variant_group", REQUIRED_VARIANT_GROUP)? {
        let vg = VariantGroup {
            id: g.s("id")?,
            process: g.s("process")?,
            members: g.strings("members")?,
            note: g.s("note")?,
        };
        let expect: Vec<&str> =
            channels.iter().filter(|c| c.variant_group.as_deref() == Some(&vg.id)).map(|c| c.id.as_str()).collect();
        if vg.members.iter().map(String::as_str).collect::<Vec<_>>() != expect
            || channels.iter().any(|c| vg.members.contains(&c.id) && c.process != vg.process)
        {
            return Err(model(format!("{rel}: variant group {} does not match its channels", vg.id)));
        }
        variant_groups.push(vg);
    }
    for c in &channels {
        if let Some(g) = &c.variant_group {
            if !variant_groups.iter().any(|v| &v.id == g) {
                return Err(model(format!("{rel}: channel {} names unknown variant group {g}", c.id)));
            }
        }
    }
    if !o.array_of("envelope", REQUIRED_ENVELOPE)?.is_empty() {
        return Err(model(format!("{rel}: UE-02 envelopes are not registered at BP-S1")));
    }
    let mut scenarios = Vec::new();
    for s in o.array_of("scenario", REQUIRED_SCENARIO)? {
        let sc = Scenario {
            id: s.s("id")?,
            evidence_mode: s.s("evidence_mode")?,
            channels: s.strings("channels")?,
            hall_config: match (s.opt_s("hall_config")?, s.opt_s("hall_config_sha256")?) {
                (Some(p), Some(h)) => Some((p, h)),
                (None, None) => None,
                _ => return Err(s.err("hall_config needs hall_config_sha256".into())),
            },
        };
        let mut tables = BTreeSet::new();
        for id in &sc.channels {
            let ch = channels.iter().find(|c| &c.id == id).ok_or_else(|| s.err(format!("unknown channel {id}")))?;
            if ch.variant_role != VariantRole::Nominal {
                return Err(model(format!("{rel}: scenario {} lists the non-nominal channel {id}", sc.id)));
            }
            tables.insert(ch.table_file().to_string());
        }
        if let Some((p, h)) = &sc.hall_config {
            let cfg = toml_of(p, cx.read(p, h, &rel)?)?;
            let files: BTreeSet<String> = cfg
                .get("reactions")
                .and_then(|r| r.as_array())
                .into_iter()
                .flatten()
                .filter_map(|r| r.get("rate_coeff_file").and_then(|v| v.as_str()).map(String::from))
                .collect();
            if files != tables || sc.channels.len() != tables.len() {
                return Err(model(format!("{rel}: scenario {} does not name exactly the tables of {p}", sc.id)));
            }
        }
        scenarios.push(sc);
    }
    Ok(ModeRegistry {
        mode,
        label: o.s("label")?,
        registry_file: rel.clone(),
        registry_sha256: sha.to_string(),
        evidence_modes: o.strings("evidence_modes")?,
        domain,
        admission_status: adm.s("status")?,
        admission_reason_code: adm.s("reason_code")?,
        admission_today: adm.s("today")?,
        completeness_audit_status: ca.s("status")?,
        neg_crit_status: neg_crit,
        species_bounds,
        species,
        processes,
        channels,
        variant_groups,
        scenarios,
    })
}

/// Parse an `xs/` file (schema `icp_chem_xs_v1`): the header must name the channel's table, sha256 and threshold; the
/// points form a valid [`CrossSection`] with the declared tail.
fn load_xs(path: &str, bytes: &[u8], table: &str, table_sha: &str, threshold: f64) -> AbepResult<CrossSection> {
    let v = json_of(path, bytes)?;
    let s = |k: &str| v[k].as_str().unwrap_or_default();
    if s("schema") != "icp_chem_xs_v1"
        || s("kind") != "CROSS_SECTION"
        || s("table") != table
        || s("table_sha256") != table_sha
    {
        return Err(model(format!("{path}: not the cross-section representation of {table} at {table_sha}")));
    }
    if v["threshold_eV"].as_f64().map(f64::to_bits) != Some(threshold.to_bits()) {
        return Err(model(format!("{path}: threshold differs from the channel's")));
    }
    let tail = match s("tail") {
        "hold" => Tail::Hold,
        "zero" => Tail::Zero,
        other => return Err(model(format!("{path}: tail {other:?}"))),
    };
    let pts = v["points"].as_array().ok_or_else(|| schema(path, "points"))?;
    if v["n_points"].as_u64() != Some(pts.len() as u64) {
        return Err(schema(path, "n_points does not match points"));
    }
    let mut e = Vec::with_capacity(pts.len());
    let mut sg = Vec::with_capacity(pts.len());
    for (i, p) in pts.iter().enumerate() {
        match (p.get(0).and_then(Value::as_f64), p.get(1).and_then(Value::as_f64), p.as_array().map(Vec::len)) {
            (Some(a), Some(b), Some(2)) => {
                e.push(a);
                sg.push(b);
            }
            _ => return Err(schema(path, format!("point {i} is not [E_eV, sigma_m2]"))),
        }
    }
    CrossSection::new(e, sg, tail)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sp(id: &str, z: i32, el: &[(&str, u32)]) -> Species {
        Species {
            id: id.into(),
            charge: z,
            elements: el.iter().map(|(k, n)| (k.to_string(), *n)).collect(),
            role: "feed".into(),
            status: "RETAINED".into(),
            retention: "test".into(),
            mass_amu: None,
            mass_source: "test".into(),
        }
    }

    fn ch(id: &str, kind: ChannelKind, target: &str, products: &[(&str, u32)], e_out: u32, e_r: f64) -> Channel {
        Channel {
            id: id.into(),
            process: "P".into(),
            kind,
            target: target.into(),
            products: products.iter().map(|(k, n)| (k.to_string(), *n)).collect(),
            electrons_out: e_out,
            threshold_ev: e_r,
            table: "t.dat".into(),
            table_sha256: String::new(),
            validity_entry: "t.dat".into(),
            validity: Validity::Verified { max_mean_energy_ev: 45.0 },
            representation: Representation::NotRegistered { kind: "CROSS_SECTION".into(), gap: "test".into() },
            variant_role: VariantRole::Nominal,
            variant_group: None,
        }
    }

    #[test]
    fn conservation_and_formation_energy_rules() {
        let s = vec![sp("N2", 0, &[("N", 2)]), sp("N", 0, &[("N", 1)]), sp("N^+", 1, &[("N", 1)])];
        let ion = ch("ion", ChannelKind::Ionization, "N", &[("N^+", 1)], 2, 14.534);
        let di = ch("di", ChannelKind::DissociativeIonization, "N2", &[("N^+", 1), ("N", 1)], 2, 24.284);
        let eps = formation_energies(&s, &[ion.clone(), di.clone()]);
        assert_eq!(eps["N^+"], 14.534);
        assert!(conservation_violations(&ion, &s, &eps).is_empty());
        assert!(conservation_violations(&di, &s, &eps).is_empty());
        // Charge (electrons_out), nuclei, shape and CV-03 violations.
        assert!(!conservation_violations(&ch("x", ChannelKind::Ionization, "N", &[("N^+", 1)], 1, 15.0), &s, &eps)
            .is_empty());
        assert!(!conservation_violations(&ch("x", ChannelKind::Dissociation, "N2", &[("N", 1)], 1, 12.0), &s, &eps)
            .is_empty());
        let low = ch("x", ChannelKind::DissociativeIonization, "N2", &[("N^+", 1), ("N", 1)], 2, 14.0);
        assert!(conservation_violations(&low, &s, &eps).iter().any(|m| m.contains("CV-03")));
        // The least-energy route defines an ion's formation energy.
        let alt = ch("alt", ChannelKind::Ionization, "N", &[("N^+", 1)], 2, 14.6);
        assert_eq!(formation_energies(&s, &[alt, ion])["N^+"], 14.534);
    }
}
