//! Repository context of NP-ICP-NEUTRALIZER v1: the frozen preregistration (lock-verified), its A9.30 addendum, the
//! NP-ICP-CHEM-AIR chemistry contract (lock-verified), its IF-CHEM-REG-v1 registry (`data/chemistry/icp/`, loaded by
//! abep-chem; addendum 02 re-points IN-16 there), the admission record of the abep-chem rate integrator (EQ-06,
//! admission-rule item 3), and every data file the model reads, each sha256-verified against a pin in one of those
//! records. Nothing is read without a pin; a mismatch is MODEL_ERROR.
//!
//! The model never reads `config/assessment/` (FC-12: a gate-threshold change cannot reach a raw output).

use crate::chemistry::{
    ChemistrySet, ClassAddress, DatTable, ProcessClass, RateSource, ReactionDef, ReactionKind, SpeciesDef, Validity,
};
use crate::constants::AMU;
use abep_chem::checked::Validity as ChemValidity;
use abep_chem::registry::{
    Channel, ChannelKind, IcpChemRegistry, ModeRegistry, RegistrySource, ICP_CHEM_PINNED_SHA256,
};
use abep_provenance::{read_bytes, read_verified, sha256_hex, ConfigManifest};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

pub const MODEL_ID: &str = "NP-ICP-NEUTRALIZER";
pub const MODEL_VERSION: &str = "1";
pub const PREREG_DIR: &str = "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER";
/// sha256 of `prereg_lock_v1.json` (the anchor; the lock pins `prereg_v1.json` and `PREREG.md`).
pub const PREREG_LOCK_SHA256: &str = "e98747e04694bf849164350be3ef4c7b458fccc918777c224066eebf55fa82af";
/// sha256 of `addendum_01_a9_30.json` (A9.30: OQ-NPICP-01 / -06 resolved, gate G-A930-AIR added).
pub const ADDENDUM_01_SHA256: &str = "f8e122492bde654d74a155f4544e51ce0b13ed639b2f510aa453384e333569c9";
pub const CHEM_AIR_DIR: &str = "docs/rust_migration/new_physics/NP-ICP-CHEM-AIR";
/// sha256 of the NP-ICP-CHEM-AIR v1 `prereg_lock_v1.json`.
pub const CHEM_AIR_LOCK_SHA256: &str = "f42c22699a31acd4e29854823150d7b7c75b35eb8718fb90ade83bdd3d7e46ef";
pub const CONTRACT_ID: &str = "NP-ICP-NEUTRALIZER/prereg_v1+addendum_01_a9_30";
/// The active bus boundary (A9.22 G8; A9.30 sec. 5).
pub const ACTIVE_BUS_BOUNDARY: &str = "bus_power_boundary_a9_v2";
/// The IF-CHEM-REG-v1 registry directory (NP-ICP-CHEM-AIR build plan BP-S1).
pub const ICP_CHEM_REGISTRY_DIR: &str = "data/chemistry/icp";
/// The consumer's pin of `data/chemistry/icp/ICP_CHEM_PINNED.toml` (labels abep-icp-air-0.0 / abep-icp-xe-0.0): a
/// registry change is a new pin (IF-CHEM-REG-v1 consumption rule: registry sha256 mismatch -> MODEL_ERROR).
pub const ICP_CHEM_PINNED: &str = ICP_CHEM_PINNED_SHA256;
/// The EM-N2 scenario of the registry: the nominal N2/N set (addendum 02, IN-16: the tables of n2_n.toml).
pub const EM_N2_SCENARIO: &str = "EM-N2-NOMINAL";
/// Admission record of the abep-chem rate integrator (contract C-ABEP_SIM_RATE_TABLES_PY v1): admission-rule item 3.
pub const ABEP_CHEM_REPORT: &str = "docs/rust_migration/contracts/C-ABEP_SIM_RATE_TABLES_PY/parity_report_v1.json";
pub const ABEP_CHEM_REPORT_SHA256: &str = "6864dc0a7b1f3c6c553edf49ed84861ad2115fb08ba5d787bd183804c58fb09e";
/// N2/N set registered by the parent prereg (sec. 8; abep-n2n-0.11).
pub const N2_SET_CONFIG: &str = "n2_n.toml";
/// DOM-02 domain of the N2/N set (prereg chemistry.completeness_domain): T_e 2-30 eV, vib / rot from 0.2 eV.
pub const N2_T_E_DOMAIN_EV: [f64; 2] = [2.0, 30.0];
pub const N2_VIBROT_T_E_MIN_EV: f64 = 0.2;

const RATE_VALIDITY: &str = "hallthruster_bridge/propellants/rate_validity.toml";
const N2_N_TOML: &str = "hallthruster_bridge/propellants/n2_n.toml";
const PINNED_TOML: &str = "hallthruster_bridge/PINNED.toml";
const ENSEMBLE: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";

/// One process of the NP-ICP-CHEM-AIR registry (id, mode AIR / XE, tier, status).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ChemAirProcess {
    pub id: String,
    pub mode: String,
    pub tier: String,
    pub status: String,
    pub reaction: String,
}

/// Validity table entry (rate_validity.toml).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ValidityEntry {
    pub status: String,
    pub max_mean_energy_ev: Option<f64>,
}

/// A data file read by the model, with the record that pins it.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct ReadFile {
    pub path: String,
    pub sha256: String,
    pub pinned_by: String,
}

/// Verified repository context. Load once; `evaluate` is then a pure function of the case.
#[derive(Debug, Clone)]
pub struct IcpModel {
    pub repo_root: PathBuf,
    pub prereg_lock_sha256: String,
    pub prereg_sha256: String,
    pub prereg_md_sha256: String,
    pub addendum_sha256: String,
    pub chem_air_lock_sha256: String,
    pub files_read: BTreeSet<ReadFile>,
    pub chem_air_processes: Vec<ChemAirProcess>,
    pub chem_air_today: BTreeMap<String, String>,
    pub ensemble_member_count: usize,
    pub ensemble_screening_ids: Vec<String>,
    pub rate_validity: BTreeMap<String, ValidityEntry>,
    pub reaction_set_version: String,
    pub supply_modes: Vec<String>,
    pub icp_feed_gas_primary: String,
    /// The IF-CHEM-REG-v1 registry (both modes), verified on load.
    pub chem_registry: IcpChemRegistry,
    /// The abep-chem integrator's admission record reads ADMITTED / PARITY_PASS (admission-rule item 3).
    pub abep_chem_admitted: bool,
    pub abep_chem_admission: String,
    /// EM-N2: the registry scenario EM-N2-NOMINAL as a chemistry structure.
    pub n2_set: ChemistrySet,
    /// The `.dat` cross-check table of every AIR registry channel, by file name (NV-06 / UQ-06 only).
    pub n2_tables: BTreeMap<String, DatTable>,
    /// Caller-supplied commit of the Rust source (OUT-14); None is reported as null.
    pub rust_commit: Option<String>,
}

fn schema(path: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.to_string(), message: m.into() }
}

fn json(path: &str, bytes: &[u8]) -> AbepResult<Value> {
    serde_json::from_slice(bytes).map_err(|e| schema(path, e.to_string()))
}

fn str_at<'a>(v: &'a Value, path: &str, ptr: &str) -> AbepResult<&'a str> {
    v.pointer(ptr).and_then(Value::as_str).ok_or_else(|| schema(path, format!("missing string {ptr}")))
}

impl IcpModel {
    /// Load and verify everything from the repository root of this workspace.
    pub fn load_workspace() -> AbepResult<Self> {
        Self::load(&abep_provenance::workspace_repo_root()?)
    }

    pub fn load(root: &Path) -> AbepResult<Self> {
        Self::load_with(root, &RegistrySource::live())
    }

    /// As [`IcpModel::load`] with the chemistry registry read from `registry` (the live registry or a pinned snapshot:
    /// frozen records regenerate from the registry they were run on).
    pub fn load_with(root: &Path, registry: &RegistrySource) -> AbepResult<Self> {
        let mut files = BTreeSet::new();
        let mut rd = |rel: &str, sha: &str, by: &str| -> AbepResult<Vec<u8>> {
            let b = read_verified(&root.join(rel), sha)?;
            files.insert(ReadFile { path: rel.to_string(), sha256: sha.to_string(), pinned_by: by.to_string() });
            Ok(b)
        };

        // Parent preregistration: lock anchor -> prereg_v1.json, PREREG.md.
        let lock_rel = format!("{PREREG_DIR}/prereg_lock_v1.json");
        let lock = json(&lock_rel, &rd(&lock_rel, PREREG_LOCK_SHA256, "abep-icp anchor (prereg lock)")?)?;
        let prereg_sha = str_at(&lock, &lock_rel, "/files/prereg_v1.json")?.to_string();
        let prereg_md_sha = str_at(&lock, &lock_rel, "/files/PREREG.md")?.to_string();
        let prereg_rel = format!("{PREREG_DIR}/prereg_v1.json");
        let prereg = json(&prereg_rel, &rd(&prereg_rel, &prereg_sha, &lock_rel)?)?;
        rd(&format!("{PREREG_DIR}/PREREG.md"), &prereg_md_sha, &lock_rel)?;
        if str_at(&prereg, &prereg_rel, "/id")? != MODEL_ID
            || str_at(&prereg, &prereg_rel, "/target_crate")? != "abep-icp"
        {
            return Err(schema(&prereg_rel, "not the NP-ICP-NEUTRALIZER / abep-icp preregistration"));
        }

        // A9.30 addendum: must apply to this lock and add gate G-A930-AIR.
        let add_rel = format!("{PREREG_DIR}/addendum_01_a9_30.json");
        let add = json(&add_rel, &rd(&add_rel, ADDENDUM_01_SHA256, "abep-icp anchor (addendum 01)")?)?;
        if str_at(&add, &add_rel, "/applies_to/locked_sha256/prereg_v1.json")? != prereg_sha
            || str_at(&add, &add_rel, "/added_gate/id")? != "G-A930-AIR"
        {
            return Err(schema(&add_rel, "addendum does not apply to the locked prereg or lacks G-A930-AIR"));
        }

        // Pins of the evidence records the prereg uses.
        let mut pins: BTreeMap<String, String> = BTreeMap::new();
        for r in prereg.get("evidence_records_used").and_then(Value::as_array).into_iter().flatten() {
            if let (Some(p), Some(s)) = (r.get("path").and_then(Value::as_str), r.get("sha256").and_then(Value::as_str))
            {
                pins.insert(p.to_string(), s.to_string());
            }
        }
        let pin = |rel: &str| pins.get(rel).cloned().ok_or_else(|| schema(rel, "not pinned by the prereg"));

        // NP-ICP-CHEM-AIR (chemistry contract): lock anchor, parent link, process registry, reuse pins.
        let cl_rel = format!("{CHEM_AIR_DIR}/prereg_lock_v1.json");
        let cl = json(&cl_rel, &rd(&cl_rel, CHEM_AIR_LOCK_SHA256, "abep-icp anchor (NP-ICP-CHEM-AIR lock)")?)?;
        let ca_rel = format!("{CHEM_AIR_DIR}/prereg_v1.json");
        let ca = json(&ca_rel, &rd(&ca_rel, str_at(&cl, &cl_rel, "/files/prereg_v1.json")?, &cl_rel)?)?;
        rd(&format!("{CHEM_AIR_DIR}/PREREG.md"), str_at(&cl, &cl_rel, "/files/PREREG.md")?, &cl_rel)?;
        if str_at(&ca, &ca_rel, "/parent_model/lock_sha256")? != PREREG_LOCK_SHA256 {
            return Err(schema(&ca_rel, "NP-ICP-CHEM-AIR does not name this prereg lock as its parent"));
        }
        // IF-CHEM-REG-v1 registry (provider abep-chem): processes with the contract statuses, channels, validity.
        let chem_registry = IcpChemRegistry::load_from(root, registry)?;
        if chem_registry.contract_lock_sha256 != CHEM_AIR_LOCK_SHA256 {
            return Err(schema(ICP_CHEM_REGISTRY_DIR, "registry of another NP-ICP-CHEM-AIR lock"));
        }
        let chem_air_processes: Vec<ChemAirProcess> = [&chem_registry.air, &chem_registry.xe]
            .into_iter()
            .flat_map(|m| {
                m.processes.iter().map(|p| ChemAirProcess {
                    id: p.id.clone(),
                    mode: m.mode.clone(),
                    tier: p.tier.clone(),
                    status: p.status.as_str().to_string(),
                    reaction: p.reaction.clone(),
                })
            })
            .collect();
        let n_contract = ca.get("processes").and_then(Value::as_array).map_or(0, Vec::len);
        if chem_air_processes.is_empty() || chem_air_processes.len() != n_contract {
            return Err(schema(&ca_rel, "process registry missing or incomplete"));
        }
        let mut chem_air_today = BTreeMap::new();
        for (k, m) in [("AIR_PRIMARY", &chem_registry.air), ("XE_CONTINGENCY", &chem_registry.xe)] {
            chem_air_today.insert(k.to_string(), m.admission_today.clone());
        }
        // Admission-rule item 3: the admission record of the abep-chem rate evaluator.
        let rep = json(
            ABEP_CHEM_REPORT,
            &rd(ABEP_CHEM_REPORT, ABEP_CHEM_REPORT_SHA256, "abep-icp anchor (abep-chem admission record)")?,
        )?;
        let verdict = rep.get("verdict").and_then(Value::as_str).unwrap_or("");
        let parity = rep.get("parity_verdict").and_then(Value::as_str).unwrap_or("");
        let abep_chem_admitted = verdict == "ADMITTED" && parity == "PARITY_PASS";
        let abep_chem_admission = format!(
            "C-ABEP_SIM_RATE_TABLES_PY parity_report_v1: verdict {verdict}, parity {parity}, rust commit {}",
            rep.get("rust_commit").and_then(Value::as_str).unwrap_or("?")
        );

        // Hall ensemble (FC-01), validity table, reaction-set label, N2/N config.
        let ens = json(ENSEMBLE, &rd(ENSEMBLE, &pin(ENSEMBLE)?, &prereg_rel)?)?;
        let members = ens.get("members").and_then(Value::as_array).ok_or_else(|| schema(ENSEMBLE, "members"))?;
        let ensemble_screening_ids = ens
            .get("screening_candidates")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(|c| c.get("id").and_then(Value::as_str).map(String::from))
            .collect();
        let rv_text = String::from_utf8(rd(RATE_VALIDITY, &pin(RATE_VALIDITY)?, &prereg_rel)?)
            .map_err(|e| schema(RATE_VALIDITY, e.to_string()))?;
        let rv: toml::Table = rv_text.parse().map_err(|e: toml::de::Error| schema(RATE_VALIDITY, e.to_string()))?;
        let mut rate_validity = BTreeMap::new();
        for (file, entry) in rv {
            let status = entry.get("status").and_then(|v| v.as_str()).ok_or_else(|| schema(RATE_VALIDITY, "status"))?;
            let lim = entry.get("max_mean_energy_eV").and_then(|v| v.as_float());
            if status == "verified" && lim.is_none() {
                return Err(schema(RATE_VALIDITY, format!("{file}: verified without max_mean_energy_eV")));
            }
            rate_validity.insert(file, ValidityEntry { status: status.to_string(), max_mean_energy_ev: lim });
        }
        let pinned_text = String::from_utf8(rd(PINNED_TOML, &pin(PINNED_TOML)?, &prereg_rel)?)
            .map_err(|e| schema(PINNED_TOML, e.to_string()))?;
        let pinned: toml::Table =
            pinned_text.parse().map_err(|e: toml::de::Error| schema(PINNED_TOML, e.to_string()))?;
        let reaction_set_version = pinned
            .get("reaction_set")
            .and_then(|t| t.get("version"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| schema(PINNED_TOML, "reaction_set.version"))?
            .to_string();
        if reaction_set_version != "abep-n2n-0.11" {
            return Err(schema(
                PINNED_TOML,
                format!("reaction set {reaction_set_version}, prereg registers abep-n2n-0.11"),
            ));
        }
        let n2_text = String::from_utf8(rd(N2_N_TOML, &pin(N2_N_TOML)?, &prereg_rel)?)
            .map_err(|e| schema(N2_N_TOML, e.to_string()))?;

        // Architecture constants through the pinned config manifest.
        let manifest = ConfigManifest::load(root)?;
        let arch_rel = "architecture/hall_icp_neutralizer_v1.json";
        let arch_bytes = manifest.read_verified(root, arch_rel)?;
        files.insert(ReadFile {
            path: format!("config/{arch_rel}"),
            sha256: sha256_hex(&arch_bytes),
            pinned_by: "config/MANIFEST.json".into(),
        });
        let arch = json(arch_rel, &arch_bytes)?;
        let supply_modes = arch
            .pointer("/constants/supply_modes")
            .and_then(Value::as_array)
            .ok_or_else(|| schema(arch_rel, "constants.supply_modes"))?
            .iter()
            .filter_map(|v| v.as_str().map(String::from))
            .collect();
        let icp_feed_gas_primary = str_at(&arch, arch_rel, "/constants/icp_feed_gas_baseline/primary")?.to_string();

        let (n2_set, n2_tables) = em_n2_set(root, &chem_registry.air, &n2_text)?;
        // The scenario's Hall configuration is the parent's pinned n2_n.toml (addendum 02: the same tables).
        let sc = chem_registry
            .air
            .scenario(EM_N2_SCENARIO)
            .ok_or_else(|| schema(ICP_CHEM_REGISTRY_DIR, format!("no scenario {EM_N2_SCENARIO}")))?;
        if sc.hall_config != Some((N2_N_TOML.to_string(), pin(N2_N_TOML)?)) {
            return Err(schema(ICP_CHEM_REGISTRY_DIR, "EM-N2-NOMINAL is not the parent's pinned n2_n.toml"));
        }
        let have: BTreeSet<String> = files.iter().map(|f| f.path.clone()).collect();
        for (p, s, by) in &chem_registry.files_read {
            if !have.contains(p) {
                files.insert(ReadFile { path: p.clone(), sha256: s.clone(), pinned_by: by.clone() });
            }
        }

        Ok(IcpModel {
            repo_root: root.to_path_buf(),
            prereg_lock_sha256: PREREG_LOCK_SHA256.into(),
            prereg_sha256: prereg_sha,
            prereg_md_sha256: prereg_md_sha,
            addendum_sha256: ADDENDUM_01_SHA256.into(),
            chem_air_lock_sha256: CHEM_AIR_LOCK_SHA256.into(),
            files_read: files,
            chem_air_processes,
            chem_air_today,
            ensemble_member_count: members.len(),
            ensemble_screening_ids,
            rate_validity,
            reaction_set_version,
            supply_modes,
            icp_feed_gas_primary,
            chem_registry,
            abep_chem_admitted,
            abep_chem_admission,
            n2_set,
            n2_tables,
            rust_commit: None,
        })
    }

    /// The rate_validity.toml semantics for a file (DOM-03): verified -> limit, unresolved, or no entry.
    pub fn validity_of(&self, file: &str) -> Validity {
        match self.rate_validity.get(file) {
            None => Validity::MissingEntry,
            Some(e) if e.status == "verified" => {
                Validity::Verified { max_mean_energy_ev: e.max_mean_energy_ev.expect("checked at load") }
            }
            Some(_) => Validity::Unresolved,
        }
    }

    /// Tier-1 processes of a CHEM-AIR mode ("AIR" / "XE") that are not IN_REPO_VERIFIED.
    pub fn chem_air_tier1_gaps(&self, mode: &str) -> Vec<&ChemAirProcess> {
        self.chem_air_processes
            .iter()
            .filter(|p| p.mode == mode && p.tier.starts_with('1') && p.status != "IN_REPO_VERIFIED")
            .collect()
    }

    /// The registry of a CHEM-AIR mode ("AIR" / "XE").
    pub fn chem_mode(&self, mode: &str) -> Option<&ModeRegistry> {
        self.chem_registry.mode(mode)
    }

    /// The registry channel of a `.dat` file name, in either mode.
    pub fn chem_channel_for_table(&self, file: &str) -> Option<&Channel> {
        self.chem_registry.air.channel_for_table(file).or_else(|| self.chem_registry.xe.channel_for_table(file))
    }

    /// OUT-14 / IF-CHEM-REG-v1 provenance of the chemistry registry.
    pub fn chem_registry_provenance(&self) -> BTreeMap<String, String> {
        let r = &self.chem_registry;
        [
            ("contract_id", abep_chem::registry::CONTRACT_ID.to_string()),
            ("contract_lock_sha256", r.contract_lock_sha256.clone()),
            ("icp_chem_pinned_sha256", r.pinned_sha256.clone()),
            ("air_label", r.air.label.clone()),
            ("air_registry_sha256", r.air.registry_sha256.clone()),
            ("xe_label", r.xe.label.clone()),
            ("xe_registry_sha256", r.xe.registry_sha256.clone()),
        ]
        .into_iter()
        .map(|(k, v)| (k.to_string(), v))
        .collect()
    }
}

fn kind_of(k: ChannelKind) -> ReactionKind {
    match k {
        ChannelKind::Ionization => ReactionKind::Ionization,
        ChannelKind::DissociativeIonization => ReactionKind::DissociativeIonization,
        ChannelKind::Dissociation => ReactionKind::Dissociation,
        ChannelKind::ExcitationElectronic => ReactionKind::ExcitationElectronic,
        ChannelKind::ExcitationVibrational => ReactionKind::ExcitationVibrational,
        ChannelKind::ExcitationRotational => ReactionKind::ExcitationRotational,
        ChannelKind::ElasticMomentumTransfer => ReactionKind::ElasticMomentumTransfer,
    }
}

/// A registry channel's validity entry in this crate's vocabulary.
pub fn validity_of_channel(v: &ChemValidity) -> Validity {
    match v {
        ChemValidity::Verified { max_mean_energy_ev } => Validity::Verified { max_mean_energy_ev: *max_mean_energy_ev },
        ChemValidity::Unresolved => Validity::Unresolved,
        ChemValidity::MissingEntry => Validity::MissingEntry,
    }
}

type N2Load = (ChemistrySet, BTreeMap<String, DatTable>);

/// EM-N2 (CG-N2): the registry scenario EM-N2-NOMINAL as a chemistry structure (addendum 02 re-points IN-16 to
/// IF-CHEM-REG-v1). Species, masses, stoichiometry, header energies and validity come from the registry; rates are
/// RegisteredTable sources, evaluated only through the registry representation and abep_chem::checked (EQ-06). The
/// parent's pinned n2_n.toml must name the same tables. Every AIR channel's `.dat` is kept for NV-06 only.
fn em_n2_set(root: &Path, air: &ModeRegistry, n2_toml: &str) -> AbepResult<N2Load> {
    let rel = ICP_CHEM_REGISTRY_DIR;
    let sc = air.scenario(EM_N2_SCENARIO).ok_or_else(|| schema(rel, format!("no scenario {EM_N2_SCENARIO}")))?;
    let channels: Vec<_> = sc
        .channels
        .iter()
        .map(|id| air.channel(id).ok_or_else(|| schema(rel, format!("unknown channel {id}"))))
        .collect::<AbepResult<_>>()?;
    let cfg: toml::Table = n2_toml.parse().map_err(|e: toml::de::Error| schema(N2_N_TOML, e.to_string()))?;
    let cfg_files: BTreeSet<&str> = cfg
        .get("reactions")
        .and_then(|v| v.as_array())
        .into_iter()
        .flatten()
        .filter_map(|r| r.get("rate_coeff_file").and_then(|v| v.as_str()))
        .collect();
    if cfg_files != channels.iter().map(|c| c.table_file()).collect::<BTreeSet<_>>() {
        return Err(schema(N2_N_TOML, "the registry scenario and n2_n.toml name different tables"));
    }
    let used: BTreeSet<&str> = channels
        .iter()
        .flat_map(|c| std::iter::once(c.target.as_str()).chain(c.products.keys().map(String::as_str)))
        .collect();
    let neutral_of = |el: &BTreeMap<String, u32>| {
        air.species.iter().find(|x| x.charge == 0 && &x.elements == el && used.contains(x.id.as_str()))
    };
    let mut species = Vec::new();
    for s in air.species.iter().filter(|s| used.contains(s.id.as_str())) {
        let mass_amu = s.mass_amu.ok_or_else(|| schema(rel, format!("species {} has no registered mass", s.id)))?;
        let charge =
            u32::try_from(s.charge).map_err(|_| schema(rel, format!("{}: negative ions are not in v1", s.id)))?;
        let wall_products = if charge > 0 {
            let n =
                neutral_of(&s.elements).ok_or_else(|| schema(rel, format!("{}: no neutral of its nuclei", s.id)))?;
            vec![(n.id.clone(), 1)]
        } else {
            vec![]
        };
        let doubled: BTreeMap<String, u32> = s.elements.iter().map(|(k, n)| (k.clone(), 2 * n)).collect();
        let recombines_to = if charge == 0 && s.elements.values().sum::<u32>() == 1 {
            neutral_of(&doubled).map(|x| x.id.clone())
        } else {
            None
        };
        species.push(SpeciesDef {
            name: s.id.clone(),
            mass_kg: mass_amu * AMU,
            charge,
            elements: s.elements.clone(),
            electronegative: false,
            wall_products,
            recombines_to,
        });
    }
    let mut tables = BTreeMap::new();
    for c in &air.channels {
        let bytes = read_verified(&root.join(&c.table), &c.table_sha256)?;
        tables.insert(c.table_file().to_string(), DatTable::parse(&c.table, &bytes)?);
    }
    let reactions: Vec<ReactionDef> = channels
        .iter()
        .map(|c| ReactionDef {
            id: c.id.clone(),
            kind: kind_of(c.kind),
            target: c.target.clone(),
            products: c.products.iter().map(|(k, n)| (k.clone(), *n)).collect(),
            threshold_ev: c.threshold_ev,
            rate: RateSource::RegisteredTable { file: c.table_file().to_string() },
            validity: validity_of_channel(&c.validity),
        })
        .collect();
    // Process classes addressed by the registered reactions; every other (species, class) pair stays unaddressed
    // until CA-ICP-v1 decides it (the Hall completeness verdict does not transfer: RU-03, OQ-NPICP-04).
    let mut process_classes: BTreeMap<String, BTreeMap<ProcessClass, ClassAddress>> = BTreeMap::new();
    for r in &reactions {
        process_classes
            .entry(r.target.clone())
            .or_default()
            .insert(r.kind.process_class(), ClassAddress::Modelled { by: r.id.clone() });
    }
    let d = &air.domain;
    if d.t_e_ev != N2_T_E_DOMAIN_EV || d.low_threshold_window_t_e_ev[0] != N2_VIBROT_T_E_MIN_EV {
        return Err(schema(rel, "D-CHEM differs from the parent DOM-02 bounds"));
    }
    let set = ChemistrySet {
        set_id: format!("{}/{EM_N2_SCENARIO}", air.label),
        species,
        reactions,
        process_classes,
        t_e_domain_ev: d.t_e_ev,
        vibrot_t_e_min_ev: d.low_threshold_window_t_e_ev[0],
    };
    let v = set.contract_violations();
    if !v.is_empty() {
        return Err(schema(rel, v.join("; ")));
    }
    Ok((set, tables))
}

/// sha256 of a file that is not part of the model inputs (used by tests and the verification example).
pub fn sha256_of(path: &Path) -> AbepResult<String> {
    Ok(sha256_hex(&read_bytes(path)?))
}
