//! Repository context of NP-ICP-NEUTRALIZER v1: the frozen preregistration (lock-verified), its A9.30 addendum, the
//! NP-ICP-CHEM-AIR chemistry contract (lock-verified), and every data file the model reads, each sha256-verified against
//! a pin in one of those frozen records. Nothing is read without a pin; a mismatch is MODEL_ERROR.
//!
//! The model never reads `config/assessment/` (FC-12: a gate-threshold change cannot reach a raw output).

use crate::chemistry::{
    ChemistrySet, ClassAddress, DatTable, ProcessClass, RateSource, ReactionDef, ReactionKind, SpeciesDef, Validity,
};
use crate::constants::AMU;
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
/// The IF-CHEM-REG-v1 registry directory drafted by NP-ICP-CHEM-AIR (build plan BP-S1).
pub const ICP_CHEM_REGISTRY_DIR: &str = "data/chemistry/icp";
/// N2/N set registered by the parent prereg (sec. 8; abep-n2n-0.11).
pub const N2_SET_CONFIG: &str = "n2_n.toml";
/// DOM-02 domain of the N2/N set (prereg chemistry.completeness_domain): T_e 2-30 eV, vib / rot from 0.2 eV.
pub const N2_T_E_DOMAIN_EV: [f64; 2] = [2.0, 30.0];
pub const N2_VIBROT_T_E_MIN_EV: f64 = 0.2;

const RATE_VALIDITY: &str = "hallthruster_bridge/propellants/rate_validity.toml";
const N2_N_TOML: &str = "hallthruster_bridge/propellants/n2_n.toml";
const PINNED_TOML: &str = "hallthruster_bridge/PINNED.toml";
const ENSEMBLE: &str = "hallthruster_bridge/ensemble/transport_ensemble_v0.json";
const PROPELLANTS: &str = "hallthruster_bridge/propellants";

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
    pub icp_registry_present: bool,
    pub n2_set: ChemistrySet,
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
        let mut chem_air_processes = Vec::new();
        for p in ca.get("processes").and_then(Value::as_array).into_iter().flatten() {
            let g = |k: &str| p.get(k).and_then(Value::as_str).unwrap_or("").to_string();
            chem_air_processes.push(ChemAirProcess {
                id: g("id"),
                mode: g("mode"),
                tier: g("tier"),
                status: g("status"),
                reaction: g("reaction"),
            });
        }
        if chem_air_processes.is_empty() || chem_air_processes.iter().any(|p| p.id.is_empty() || p.status.is_empty()) {
            return Err(schema(&ca_rel, "process registry missing or incomplete"));
        }
        let mut chem_air_today = BTreeMap::new();
        if let Some(t) = ca.pointer("/admission_criteria/today").and_then(Value::as_object) {
            for (k, v) in t {
                chem_air_today.insert(k.clone(), v.as_str().unwrap_or("").to_string());
            }
        }
        let mut table_pins: BTreeMap<String, String> = BTreeMap::new();
        for e in ca.pointer("/reuse_pins/hall_propellant_tables").and_then(Value::as_array).into_iter().flatten() {
            if let (Some(p), Some(s)) = (e.get("path").and_then(Value::as_str), e.get("sha256").and_then(Value::as_str))
            {
                table_pins.insert(p.to_string(), s.to_string());
            }
        }

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

        let (n2_set, n2_tables, table_files) = load_n2_set(root, &n2_text, &rate_validity, &table_pins)?;
        files.extend(table_files.into_iter().map(|(p, s)| ReadFile {
            path: p,
            sha256: s,
            pinned_by: format!("{ca_rel} reuse_pins.hall_propellant_tables"),
        }));

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
            icp_registry_present: root.join(ICP_CHEM_REGISTRY_DIR).join("registry_air.toml").is_file(),
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
}

fn ion_name(sym: &str, z: u32) -> String {
    if z == 1 {
        format!("{sym}^+")
    } else {
        format!("{sym}^{z}+")
    }
}

/// "N2(+)" -> ("N2", 1); "N(2+)" -> ("N", 2); "N" -> ("N", 0); "2e" / "e" -> None.
fn parse_token(tok: &str) -> Option<(u32, String, u32)> {
    let tok = tok.trim();
    if tok == "e" || (tok.ends_with('e') && tok[..tok.len() - 1].chars().all(|c| c.is_ascii_digit())) {
        return None;
    }
    let (sym, z) = match tok.find('(') {
        Some(i) => {
            let inner = tok[i + 1..].trim_end_matches(')').trim_end_matches('+');
            let z = if inner.is_empty() { 1 } else { inner.parse().ok()? };
            (&tok[..i], z)
        }
        None => (tok, 0),
    };
    Some((1, sym.to_string(), z))
}

type N2Load = (ChemistrySet, BTreeMap<String, DatTable>, Vec<(String, String)>);

/// The registered N2/N set (parent sec. 8, abep-n2n-0.11) as a chemistry structure. Each table is sha256-verified
/// against the NP-ICP-CHEM-AIR reuse pin (an unpinned table is MODEL_ERROR, IF-CHEM-REG-v1); its header gives E_r and
/// its rows serve only the NV-06 cross-check. Rates are RegisteredTable sources: EQ-06 evaluation needs abep-chem.
fn load_n2_set(
    root: &Path,
    text: &str,
    validity: &BTreeMap<String, ValidityEntry>,
    table_pins: &BTreeMap<String, String>,
) -> AbepResult<N2Load> {
    let cfg: toml::Table = text.parse().map_err(|e: toml::de::Error| schema(N2_N_TOML, e.to_string()))?;
    let mut species = Vec::new();
    for s in cfg.get("species").and_then(|v| v.as_array()).ok_or_else(|| schema(N2_N_TOML, "species"))? {
        let sym = s.get("symbol").and_then(|v| v.as_str()).ok_or_else(|| schema(N2_N_TOML, "symbol"))?;
        let mass_u = s.get("mass").and_then(|v| v.as_float()).ok_or_else(|| schema(N2_N_TOML, "mass"))?;
        let zmax = s.get("max_charge").and_then(|v| v.as_integer()).ok_or_else(|| schema(N2_N_TOML, "max_charge"))?;
        let n_atoms: u32 = sym.trim_start_matches('N').parse().unwrap_or(1);
        let elements: BTreeMap<String, u32> = [("N".to_string(), n_atoms)].into();
        species.push(SpeciesDef {
            name: sym.to_string(),
            mass_kg: mass_u * AMU,
            charge: 0,
            elements: elements.clone(),
            electronegative: false,
            wall_products: vec![],
            recombines_to: if n_atoms == 1 { Some("N2".into()) } else { None },
        });
        for z in 1..=u32::try_from(zmax).map_err(|_| schema(N2_N_TOML, "max_charge"))? {
            // Ion mass = neutral mass (HallThruster.jl convention; Z m_e / M <= 8e-5).
            species.push(SpeciesDef {
                name: ion_name(sym, z),
                mass_kg: mass_u * AMU,
                charge: z,
                elements: elements.clone(),
                electronegative: false,
                wall_products: vec![(sym.to_string(), 1)],
                recombines_to: None,
            });
        }
    }
    let mut reactions = Vec::new();
    let mut tables = BTreeMap::new();
    let mut read = Vec::new();
    for (i, r) in cfg
        .get("reactions")
        .and_then(|v| v.as_array())
        .ok_or_else(|| schema(N2_N_TOML, "reactions"))?
        .iter()
        .enumerate()
    {
        let ty = r.get("type").and_then(|v| v.as_str()).ok_or_else(|| schema(N2_N_TOML, "type"))?;
        let file = r.get("rate_coeff_file").and_then(|v| v.as_str()).ok_or_else(|| schema(N2_N_TOML, "file"))?;
        let rel = format!("{PROPELLANTS}/{file}");
        let sha = table_pins.get(&rel).ok_or_else(|| AbepError::Schema {
            path: rel.clone(),
            message: "rate file without a sha256 pin (IF-CHEM-REG-v1: unregistered file -> MODEL_ERROR)".into(),
        })?;
        let bytes = read_verified(&root.join(&rel), sha)?;
        read.push((rel.clone(), sha.clone()));
        let table = DatTable::parse(&rel, &bytes)?;
        let (kind, target, products) = match ty {
            "elastic" | "excitation" => {
                let t = r.get("target_species").and_then(|v| v.as_str()).ok_or_else(|| schema(N2_N_TOML, "target"))?;
                let kind = if ty == "elastic" {
                    ReactionKind::ElasticMomentumTransfer
                } else if file.contains("_vib_") {
                    ReactionKind::ExcitationVibrational
                } else if file.contains("_rot_") {
                    ReactionKind::ExcitationRotational
                } else {
                    ReactionKind::ExcitationElectronic
                };
                (kind, t.to_string(), vec![(t.to_string(), 1)])
            }
            "electron_impact" => {
                let eq = r.get("equation").and_then(|v| v.as_str()).ok_or_else(|| schema(N2_N_TOML, "equation"))?;
                let (lhs, rhs) = eq.split_once("->").ok_or_else(|| schema(N2_N_TOML, format!("equation {eq}")))?;
                let target = lhs
                    .split(" + ")
                    .filter_map(parse_token)
                    .map(|(_, s, z)| if z == 0 { s } else { ion_name(&s, z) })
                    .next()
                    .ok_or_else(|| schema(N2_N_TOML, format!("equation {eq}")))?;
                let mut prods: BTreeMap<String, u32> = BTreeMap::new();
                let mut n_ions = 0;
                for (n, s, z) in rhs.split(" + ").filter_map(parse_token) {
                    let name = if z == 0 { s } else { ion_name(&s, z) };
                    if z > 0 {
                        n_ions += n;
                    }
                    *prods.entry(name).or_insert(0) += n;
                }
                let total: u32 = prods.values().sum();
                let kind = match (n_ions, total) {
                    (0, _) => ReactionKind::Dissociation,
                    (_, 1) => ReactionKind::Ionization,
                    _ => ReactionKind::DissociativeIonization,
                };
                (kind, target, prods.into_iter().collect())
            }
            other => return Err(schema(N2_N_TOML, format!("reaction type {other}"))),
        };
        let v = match validity.get(file) {
            None => Validity::MissingEntry,
            Some(e) if e.status == "verified" => {
                Validity::Verified { max_mean_energy_ev: e.max_mean_energy_ev.unwrap() }
            }
            Some(_) => Validity::Unresolved,
        };
        reactions.push(ReactionDef {
            id: format!("R{:02}:{}", i + 1, file.trim_end_matches(".dat")),
            kind,
            target,
            products,
            threshold_ev: table.threshold_ev,
            rate: RateSource::RegisteredTable { file: file.to_string() },
            validity: v,
        });
        tables.insert(file.to_string(), table);
    }
    // Process classes addressed by the registered reactions; every other (species, class) pair stays unaddressed:
    // the Hall completeness verdict does not transfer to ICP conditions (OQ-NPICP-04).
    let mut process_classes: BTreeMap<String, BTreeMap<ProcessClass, ClassAddress>> = BTreeMap::new();
    for r in &reactions {
        process_classes
            .entry(r.target.clone())
            .or_default()
            .insert(r.kind.process_class(), ClassAddress::Modelled { by: r.id.clone() });
    }
    let set = ChemistrySet {
        set_id: "abep-n2n-0.11/n2_n.toml".into(),
        species,
        reactions,
        process_classes,
        t_e_domain_ev: N2_T_E_DOMAIN_EV,
        vibrot_t_e_min_ev: N2_VIBROT_T_E_MIN_EV,
    };
    let v = set.contract_violations();
    if !v.is_empty() {
        return Err(schema(N2_N_TOML, v.join("; ")));
    }
    Ok((set, tables, read))
}

/// sha256 of a file that is not part of the model inputs (used by tests and the verification example).
pub fn sha256_of(path: &Path) -> AbepResult<String> {
    Ok(sha256_hex(&read_bytes(path)?))
}
