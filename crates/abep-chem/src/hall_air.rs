//! NP-HALL-CHEM-AIR (A9.33 Q2): the Hall AIR_PRIMARY reaction set `abep-air-0.x` of the pinned HallThruster.jl
//! (`hallthruster_bridge/propellants_air/`), its loader, its fail-closed guards and the table builder.
//!
//! [`AirSet::load`] reads everything through sha256 pins anchored on [`AIR_PINNED_SHA256`] and refuses (MODEL_ERROR)
//! what the preregistration refuses:
//!
//! | condition | preregistration item |
//! |---|---|
//! | `AIR_PINNED.toml`, a listed file or a reused abep-n2n-0.11 table differs from its pin; an unlisted file | HR-01, RU-02, build plan |
//! | a configured rate file without a `propellants_air/rate_validity.toml` entry, or a mirror that differs from its N2 entry | HR-05, RU-02 |
//! | a reaction whose target gas differs from its table's registered target (atomic O never served by N2 / N / O2 data) | HR-04 |
//! | charge or nuclei not conserved by an equation; an equation naming an unconfigured species | CV-01 |
//! | a status other than the preregistered vocabulary, or COMPLETE with open gaps | set_status_vocabulary, AD-HA-06 |
//!
//! [`AirSet::admission`] is the gate the AIR family reads: Ok only for COMPLETE_FOR_PARAMETRIC_ENVELOPE; otherwise
//! INCOMPLETE_EVIDENCE (or MODEL_ERROR for NOT_REPRESENTABLE_IN_PINNED_SOLVER) naming every open item. Admission is never a
//! validation claim. [`render_xs`] renders a table from its registered cross-section representation with the admitted
//! integrator ([`crate::reference`], contract C-ABEP_SIM_RATE_TABLES_PY). Nothing here runs HallThruster.jl.

use crate::checked::Validity;
use crate::reference::{self, Tail, TailArg};
use crate::validity::RateValidityTable;
use abep_provenance::{read_verified, sha256_hex};
use abep_types::{AbepError, AbepResult};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

pub const BRIDGE_DIR: &str = "hallthruster_bridge";
pub const AIR_DIR: &str = "hallthruster_bridge/propellants_air";
pub const N2_DIR: &str = "hallthruster_bridge/propellants";
pub const PINNED_FILE: &str = "AIR_PINNED.toml";
/// sha256 of `hallthruster_bridge/propellants_air/AIR_PINNED.toml` this build is registered against. Every change of the
/// set (one table per commit) updates it.
pub const AIR_PINNED_SHA256: &str = "e9ca590ae5f6bd396fff2fdf48b880ef8f4b018d2f13d70958da3c66d5152171";
pub const CONTRACT_ID: &str = "NP-HALL-CHEM-AIR";
pub const PREREG_REL: &str = "docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/prereg_v1.json";
pub const PREREG_SHA256: &str = "306712f78bbbf17e8aa50e804559c36a80680dbebc8ecf0f47f2c244443ea70f";
pub const PREREG_LOCK_REL: &str = "docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/prereg_lock_v1.json";
pub const PREREG_LOCK_SHA256: &str = "1884e42ff98ee07a634500ce338eef9dc3749bf4e5c053b058aec9b764674518";
/// Directories holding the cross-section representations [`render_xs`] renders.
pub const XS_DIRS: [&str; 2] =
    ["hallthruster_bridge/propellants_air/xs", "hallthruster_bridge/audit_air/bound_tables/xs"];
/// The writer grid of every table (mean energy 0-300 eV, 1 eV step; HallThruster.jl reads 0-255 eV).
pub const EPS_MAX_EV: f64 = 300.0;
/// Cap of a source-support limit (rate_validity.toml convention).
pub const SUPPORT_CAP_EV: f64 = 255.0;
/// Held-tail share below which a mean energy is source-supported.
pub const TAIL_SHARE_LIMIT: f64 = 0.01;

/// Hall files the contract never changes (HR-01), with their sha256 at the registration base `b730764`.
pub const HALL_ISOLATION: [(&str, &str); 33] = [
    ("hallthruster_bridge/propellants/n2_n.toml", "4f10db747cfb11cfefb8080a9cad52e502c2ab11f0e485ac644a532b929607de"),
    (
        "hallthruster_bridge/propellants/n2_n_di_lower.toml",
        "8b679aca9b223719d521890c391e227727ff2dfacdea6e3ebbbdee93d1b84372",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_di_lower_nel_wang.toml",
        "29325bda79f18006e9f3c62df2a1ccc6aa74b66a44040f08d1bbe4ccd4305749",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_exc_johnsonlow.toml",
        "95c9bec9f69993691e2539fc55ec20713fccca93376f3ff4ded9133d62721f9e",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_exc_johnsonlow_di_lower.toml",
        "10aed98243c7972d5c86a7b460873bfa210ab43492ba6229bdbc44c9640a1405",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_exc_johnsonlow_di_lower_nel_wang.toml",
        "793cc6e73e3cc4017fad8579aba26c0834b68666e9c87cfc882492ef674c7f4c",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_exc_johnsonlow_nel_wang.toml",
        "58c4b5ea1bd3c2d86ec83108486a44e788060a896f117b39aca695547205e6d3",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_n2dication.toml",
        "fb87c2c4328951bf7ead8d92bc2ffe94f17ce912e2977740d495d4d4cae2581f",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_n2dication_nel_wang.toml",
        "cf54add54566f0af51125e70b680b689ec3953521dc0ef460d192e11c9a1b018",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_ndd_hmshigh.toml",
        "333d6071c035d83376f20a70a257579d7b838c591c374e2cdb5052331e0285d3",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_ndd_hmshigh_di_lower.toml",
        "103541265e687fdeed302fb628efa176ca0c051ebca4ea3835df6d6e6ed4de91",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_ndd_hmshigh_di_lower_nel_wang.toml",
        "88b6f77c52df50eb3becddbf649f08b7b8877b9c8a632dae23e0c1da42c2212f",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_ndd_hmshigh_nel_wang.toml",
        "2ce2cda701c8607eedbe42436c2a9630a24b3dea6da550f2046e5d634c237836",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_ndd_hmslow.toml",
        "f9b64716cdd6294a4338c5708a94ba4db888ec671c2c6a26647566db04085b71",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_ndd_hmslow_di_lower.toml",
        "674438532bb897f0b724bf3b53059f0128cbbe27604fcaea05788e2a07fcf227",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_ndd_hmslow_di_lower_nel_wang.toml",
        "2eec1906e39a1dd6e47a299430e94138db2ca9642a8e996e8fcc1e49aa9ea6a1",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_ndd_hmslow_nel_wang.toml",
        "b7182f02dae5b4a49d1f16dab486fe52e2c42b2cae8596e35978017b636c288a",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_nel_wang.toml",
        "398c795be786194d2caf9c8720f28b4c3cfab80033f43431d21c6e8b14ab1318",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_rot_off.toml",
        "5fa1fafaba358ef8fdea716bd28c085bf48a2db2607c8f3808bed6f05412fbd0",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_rot_off_di_lower.toml",
        "0d9150d125528fae84dc64fc451741aa3c56c39860c86c2973d38787fc637392",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_rot_off_di_lower_nel_wang.toml",
        "022caef866c283c6965c5bda6ea1fac7ecc3e2b4e349ce5067af481d6f70adee",
    ),
    (
        "hallthruster_bridge/propellants/n2_n_rot_off_nel_wang.toml",
        "2011dc1084eb3c4e51cac879b16bdd39658e72d204933ee8793065819aadf93c",
    ),
    (
        "hallthruster_bridge/propellants/rate_validity.toml",
        "64b51be96ef30d6024a99ad9bc0b47384ba3c2434a4c096403cc2b1aa0290e3a",
    ),
    (
        "hallthruster_bridge/propellants/PROVENANCE.md",
        "75a9833303c674257db2124c928e7324e6a5b09c1141517a79327b11ed6607e4",
    ),
    ("hallthruster_bridge/PINNED.toml", "26a00c8a156a5a5e9a58f9796f657ea12f59d87ac2da3d6507ac7347b4765280"),
    ("hallthruster_bridge/Manifest.toml", "a98c1a6e9cdf491ef602ef7cd1d08371b2bbe3da4e1df74e45a1c9d84f6c5634"),
    ("hallthruster_bridge/bridge_lib.jl", "cf26aab8607b640ebb78be9715f2c7c5d957f145ac17f52c1b23db2e980e21ab"),
    (
        "hallthruster_bridge/audit/configs/MANIFEST.json",
        "19e833c902aa9f62f9418105b7540318a9c3d88bd7e4dc07c9f377bcc4dcdcf2",
    ),
    (
        "hallthruster_bridge/prereg/n2_completeness_audit_v1.json",
        "f8353f09a51beb251a74623695e66022b4bc2b0258b746be0f6d146b0b6b4a2b",
    ),
    (
        "hallthruster_bridge/prereg/n2_completeness_audit_v1_addendum1_ambiguity.json",
        "cec43b09ffdb5e994c83dff7e97f10abe756e8f339e882e77b7733c262f587a8",
    ),
    (
        "hallthruster_bridge/prereg/n2_completeness_audit_v1_addendum2_crosscheck.json",
        "8b5add9728885900b3422f8d394ba672ba6f6895e1bfe6dae3931d4fd10f23fa",
    ),
    (
        "hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json",
        "71ecd39fa25ea60e2e4aff9474bdd700ec8cd718e819dfdae774594709e805be",
    ),
    (
        "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json",
        "0a57a397883141be20196853b7d722404dc3cb20c72fba666121fd43507dc97c",
    ),
];

fn model(m: impl Into<String>) -> AbepError {
    AbepError::Model { message: m.into() }
}

fn schema(path: &str, m: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.into(), message: m.into() }
}

fn utf8(path: &str, bytes: Vec<u8>) -> AbepResult<String> {
    String::from_utf8(bytes).map_err(|e| schema(path, e.to_string()))
}

fn toml_of(path: &str, text: &str) -> AbepResult<toml::Table> {
    text.parse().map_err(|e: toml::de::Error| schema(path, e.to_string()))
}

fn s<'a>(t: &'a toml::Table, key: &str, path: &str) -> AbepResult<&'a str> {
    t.get(key).and_then(|v| v.as_str()).ok_or_else(|| schema(path, format!("{key} missing or not a string")))
}

fn str_list(t: &toml::Table, key: &str, path: &str) -> AbepResult<Vec<String>> {
    t.get(key)
        .and_then(|v| v.as_array())
        .ok_or_else(|| schema(path, format!("{key} missing or not an array")))?
        .iter()
        .map(|v| v.as_str().map(str::to_string).ok_or_else(|| schema(path, format!("{key}: non-string item"))))
        .collect()
}

/// The preregistered set status vocabulary (`set_status_vocabulary`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SetStatus {
    IncompleteEvidence,
    NotRepresentableInPinnedSolver,
    CompleteForParametricEnvelope,
}

impl SetStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            SetStatus::IncompleteEvidence => "INCOMPLETE_EVIDENCE",
            SetStatus::NotRepresentableInPinnedSolver => "NOT_REPRESENTABLE_IN_PINNED_SOLVER",
            SetStatus::CompleteForParametricEnvelope => "COMPLETE_FOR_PARAMETRIC_ENVELOPE",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        [Self::IncompleteEvidence, Self::NotRepresentableInPinnedSolver, Self::CompleteForParametricEnvelope]
            .into_iter()
            .find(|x| x.as_str() == s)
    }
}

/// How a configured rate file entered the set.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TableKind {
    /// abep-n2n-0.11 table referenced in place (`../propellants/<file>`).
    Reused,
    /// Rendered from a registered cross-section representation (`xs/<name>.json`).
    Xs { xs: String },
    /// Byte-identical copy of a v0 DRAFT table whose raw source is not committed (NIST SRD 107).
    CopyOfV0 { v0: String, v0_sha256: String },
}

/// A rate file the configurations may name.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableEntry {
    /// Path relative to `propellants_air/` (as the configurations name it).
    pub file: String,
    /// Gas of the heavy reactant the table belongs to (`O`, `O2`, `N`, `N2`).
    pub target: String,
    /// Preregistration process id (`HA-...`).
    pub process: String,
    pub role: String,
    pub kind: TableKind,
    pub sha256: String,
}

/// One `[[reactions]]` entry of a configuration.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Reaction {
    pub kind: String,
    pub equation: Option<String>,
    /// Gas of the heavy reactant (or the elastic / excitation target).
    pub target: String,
    pub file: String,
}

/// One propellant configuration (`air_*.toml`).
#[derive(Debug, Clone, PartialEq)]
pub struct AirConfig {
    pub name: String,
    pub sha256: String,
    /// `(symbol, max_charge)`.
    pub species: Vec<(String, i64)>,
    pub reactions: Vec<Reaction>,
}

/// The loaded, verified AIR reaction set.
#[derive(Debug, Clone)]
pub struct AirSet {
    pub label: String,
    pub status: SetStatus,
    pub nominal_config: Option<String>,
    pub tier1_gaps: Vec<String>,
    pub blocking: Vec<String>,
    pub history: Vec<String>,
    pub tables: BTreeMap<String, TableEntry>,
    pub configs: BTreeMap<String, AirConfig>,
    pub validity: RateValidityTable,
    pub files: BTreeMap<String, String>,
}

/// Parsed species term of an equation: gas formula, charge, coefficient.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Term {
    pub gas: String,
    pub charge: i64,
    pub count: i64,
}

/// `"2N"`, `"O2(+)"`, `"N(2+)"`, `"O(-)"`, `"e"`, `"3e"` -> term (the HallThruster.jl equation syntax used by abep-n2n).
pub fn parse_term(raw: &str) -> AbepResult<Term> {
    let t = raw.trim();
    let digits = t.chars().take_while(|c| c.is_ascii_digit()).count();
    let count = if digits == 0 { 1 } else { t[..digits].parse::<i64>().map_err(|_| model(format!("term {t:?}")))? };
    let rest = &t[digits..];
    let (gas, charge) = match rest.find('(') {
        None => (rest, 0),
        Some(i) => {
            let inner = rest[i + 1..].strip_suffix(')').ok_or_else(|| model(format!("term {t:?}: unclosed charge")))?;
            let (mag, sign) = inner.split_at(inner.len().saturating_sub(1));
            let mag = if mag.is_empty() { 1 } else { mag.parse::<i64>().map_err(|_| model(format!("term {t:?}")))? };
            let z = match sign {
                "+" => mag,
                "-" => -mag,
                _ => return Err(model(format!("term {t:?}: charge must end in + or -"))),
            };
            (&rest[..i], z)
        }
    };
    if gas.is_empty() || !gas.chars().all(|c| c.is_ascii_alphanumeric()) {
        return Err(model(format!("term {t:?}: bad species symbol")));
    }
    let charge = if gas == "e" { -1 } else { charge };
    Ok(Term { gas: gas.to_string(), charge, count })
}

/// Element counts of a formula without parentheses (`"O2"` -> {O: 2}, `"N"` -> {N: 1}).
pub fn elements(formula: &str) -> AbepResult<BTreeMap<String, i64>> {
    let mut out = BTreeMap::new();
    let cs: Vec<char> = formula.chars().collect();
    let mut i = 0;
    while i < cs.len() {
        if !cs[i].is_ascii_uppercase() {
            return Err(model(format!("formula {formula:?}: expected an element symbol at {i}")));
        }
        let mut sym = cs[i].to_string();
        i += 1;
        if i < cs.len() && cs[i].is_ascii_lowercase() {
            sym.push(cs[i]);
            i += 1;
        }
        let start = i;
        while i < cs.len() && cs[i].is_ascii_digit() {
            i += 1;
        }
        let n = if start == i { 1 } else { cs[start..i].iter().collect::<String>().parse::<i64>().unwrap_or(0) };
        *out.entry(sym).or_insert(0) += n;
    }
    Ok(out)
}

/// Both sides of an equation (`"N2 + e -> N(+) + N + 2e"`); terms are separated by `" + "`.
pub fn parse_equation(eq: &str) -> AbepResult<(Vec<Term>, Vec<Term>)> {
    let (l, r) = eq.split_once("->").ok_or_else(|| model(format!("equation {eq:?} has no '->'")))?;
    let side = |x: &str| -> AbepResult<Vec<Term>> { x.split(" + ").map(parse_term).collect() };
    Ok((side(l)?, side(r)?))
}

/// CV-01: charge and nuclei per element balance. Returns the heavy reactant (gas, charge).
pub fn check_conservation(eq: &str) -> AbepResult<(String, i64)> {
    let (lhs, rhs) = parse_equation(eq)?;
    let tally = |side: &[Term]| -> AbepResult<(i64, BTreeMap<String, i64>)> {
        let mut q = 0;
        let mut el: BTreeMap<String, i64> = BTreeMap::new();
        for t in side {
            q += t.count * t.charge;
            if t.gas != "e" {
                for (k, n) in elements(&t.gas)? {
                    *el.entry(k).or_insert(0) += n * t.count;
                }
            }
        }
        Ok((q, el))
    };
    let (ql, el) = tally(&lhs)?;
    let (qr, er) = tally(&rhs)?;
    if ql != qr {
        return Err(model(format!("CV-01: charge not conserved in {eq:?} ({ql} -> {qr})")));
    }
    if el != er {
        return Err(model(format!("CV-01: nuclei not conserved in {eq:?} ({el:?} -> {er:?})")));
    }
    let heavy: Vec<&Term> = lhs.iter().filter(|t| t.gas != "e").collect();
    match heavy.as_slice() {
        [t] if t.count == 1 => Ok((t.gas.clone(), t.charge)),
        _ => {
            Err(model(format!("{eq:?}: an electron-impact reaction has exactly one heavy reactant (capability C-02)")))
        }
    }
}

fn parse_config(name: &str, text: &str) -> AbepResult<AirConfig> {
    let t = toml_of(name, text)?;
    let mut species = Vec::new();
    for sp in t.get("species").and_then(|v| v.as_array()).ok_or_else(|| schema(name, "no [[species]]"))? {
        let sp = sp.as_table().ok_or_else(|| schema(name, "species entry is not a table"))?;
        let mc = sp
            .get("max_charge")
            .and_then(|v| v.as_integer())
            .ok_or_else(|| schema(name, "species without max_charge"))?;
        species.push((s(sp, "symbol", name)?.to_string(), mc));
    }
    let mut reactions = Vec::new();
    for r in t.get("reactions").and_then(|v| v.as_array()).ok_or_else(|| schema(name, "no [[reactions]]"))? {
        let r = r.as_table().ok_or_else(|| schema(name, "reaction entry is not a table"))?;
        let kind = s(r, "type", name)?.to_string();
        let file = s(r, "rate_coeff_file", name)?.to_string();
        let (equation, target) = match kind.as_str() {
            "elastic" | "excitation" => (None, s(r, "target_species", name)?.to_string()),
            "electron_impact" => {
                let eq = s(r, "equation", name)?.to_string();
                let (gas, _) = check_conservation(&eq)?;
                (Some(eq), gas)
            }
            other => {
                return Err(schema(
                    name,
                    format!("reaction type {other:?} is not elastic | excitation | electron_impact"),
                ))
            }
        };
        reactions.push(Reaction { kind, equation, target, file });
    }
    Ok(AirConfig { name: name.into(), sha256: sha256_hex(text.as_bytes()), species, reactions })
}

/// Every file under `dir` (recursive), as paths relative to it with `/` separators.
fn list_files(dir: &Path, prefix: &str, out: &mut Vec<String>) -> AbepResult<()> {
    let rd = std::fs::read_dir(dir)
        .map_err(|e| AbepError::Io { path: dir.display().to_string(), message: e.to_string() })?;
    let mut entries: Vec<_> = rd.filter_map(Result::ok).collect();
    entries.sort_by_key(|e| e.file_name());
    for e in entries {
        let name = e.file_name().to_string_lossy().to_string();
        let rel = if prefix.is_empty() { name.clone() } else { format!("{prefix}/{name}") };
        let ft = e.file_type().map_err(|err| AbepError::Io { path: rel.clone(), message: err.to_string() })?;
        if ft.is_dir() {
            list_files(&e.path(), &rel, out)?;
        } else {
            out.push(rel);
        }
    }
    Ok(())
}

impl AirSet {
    /// Load and verify the set at `repo` against [`AIR_PINNED_SHA256`].
    pub fn load(repo: &Path) -> AbepResult<AirSet> {
        Self::load_pinned(repo, AIR_PINNED_SHA256)
    }

    /// Load and verify the set against an explicit pin of `AIR_PINNED.toml` (tests use it on modified copies).
    pub fn load_pinned(repo: &Path, pinned_sha256: &str) -> AbepResult<AirSet> {
        let air = repo.join(AIR_DIR);
        let prel = format!("{AIR_DIR}/{PINNED_FILE}");
        let pinned = toml_of(&prel, &utf8(&prel, read_verified(&air.join(PINNED_FILE), pinned_sha256)?)?)?;
        let tab = |k: &str| -> AbepResult<&toml::Table> {
            pinned.get(k).and_then(|v| v.as_table()).ok_or_else(|| schema(&prel, format!("[{k}] missing")))
        };
        let contract = tab("contract")?;
        if s(contract, "id", &prel)? != CONTRACT_ID || s(contract, "lock_sha256", &prel)? != PREREG_LOCK_SHA256 {
            return Err(model("AIR_PINNED.toml names another contract or preregistration lock"));
        }
        read_verified(&repo.join(PREREG_LOCK_REL), PREREG_LOCK_SHA256)?;
        read_verified(&repo.join(PREREG_REL), PREREG_SHA256)?;

        // Every file of the directory is pinned, and nothing else (the set is a pure function of pinned bytes).
        let mut files = BTreeMap::new();
        for (f, h) in tab("files")? {
            let h = h.as_str().ok_or_else(|| schema(&prel, format!("[files] {f}: not a string")))?;
            read_verified(&air.join(f), h)?;
            files.insert(f.clone(), h.to_string());
        }
        let mut on_disk = Vec::new();
        list_files(&air, "", &mut on_disk)?;
        let unlisted: Vec<&String> = on_disk.iter().filter(|f| *f != PINNED_FILE && !files.contains_key(*f)).collect();
        if !unlisted.is_empty() {
            return Err(model(format!("files in {AIR_DIR} not pinned by AIR_PINNED.toml [files]: {unlisted:?}")));
        }
        for (rel, sha) in HALL_ISOLATION {
            read_verified(&repo.join(rel), sha).map_err(|e| model(format!("HR-01 Hall isolation: {e}")))?;
        }

        let rs = tab("reaction_set")?;
        let label = s(rs, "label", &prel)?.to_string();
        if !label.starts_with("abep-air-0.") {
            return Err(model(format!("label {label:?} is not abep-air-0.x (HR-02)")));
        }
        let status = SetStatus::parse(s(rs, "status", &prel)?)
            .ok_or_else(|| model("[reaction_set] status outside the preregistered vocabulary"))?;
        let tier1_gaps = str_list(rs, "tier1_gaps", &prel)?;
        let blocking = str_list(rs, "blocking", &prel)?;
        let history = str_list(rs, "history", &prel)?;
        if status == SetStatus::CompleteForParametricEnvelope && (!tier1_gaps.is_empty() || !blocking.is_empty()) {
            return Err(model("COMPLETE_FOR_PARAMETRIC_ENVELOPE with open tier-1 gaps or blocking items (AD-HA-06)"));
        }
        if !history.iter().any(|h| h.starts_with(&format!("{label} "))) {
            return Err(model(format!("no history line for the current label {label}")));
        }

        // Rate files: reused abep-n2n-0.11 tables (pinned in place) and the set's own tables.
        let mut tables = BTreeMap::new();
        for (f, e) in tab("reuse")? {
            let e = e.as_table().ok_or_else(|| schema(&prel, format!("[reuse] {f}: not a table")))?;
            let name = f
                .strip_prefix("../propellants/")
                .ok_or_else(|| model(format!("[reuse] {f}: reused tables are referenced as ../propellants/<file>")))?;
            let sha = s(e, "sha256", &prel)?;
            read_verified(&repo.join(N2_DIR).join(name), sha)?;
            tables.insert(
                f.clone(),
                TableEntry {
                    file: f.clone(),
                    target: s(e, "target", &prel)?.into(),
                    process: s(e, "process", &prel)?.into(),
                    role: s(e, "role", &prel)?.into(),
                    kind: TableKind::Reused,
                    sha256: sha.into(),
                },
            );
        }
        for (f, e) in tab("tables")? {
            let e = e.as_table().ok_or_else(|| schema(&prel, format!("[tables] {f}: not a table")))?;
            let sha = files.get(f).ok_or_else(|| model(format!("[tables] {f} is not pinned in [files]")))?.clone();
            let kind = match s(e, "kind", &prel)? {
                "XS" => {
                    let xs = s(e, "xs", &prel)?.to_string();
                    if !files.contains_key(&xs) {
                        return Err(model(format!("[tables] {f}: representation {xs} is not pinned")));
                    }
                    TableKind::Xs { xs }
                }
                "COPY_OF_V0" => {
                    let v0 = s(e, "v0", &prel)?.to_string();
                    let v0_sha = s(e, "v0_sha256", &prel)?.to_string();
                    read_verified(&repo.join(&v0), &v0_sha)?;
                    if v0_sha != sha {
                        return Err(model(format!("[tables] {f}: not byte-identical to {v0} (RU-03)")));
                    }
                    TableKind::CopyOfV0 { v0, v0_sha256: v0_sha }
                }
                other => return Err(schema(&prel, format!("[tables] {f}: kind {other:?}"))),
            };
            tables.insert(
                f.clone(),
                TableEntry {
                    file: f.clone(),
                    target: s(e, "target", &prel)?.into(),
                    process: s(e, "process", &prel)?.into(),
                    role: s(e, "role", &prel)?.into(),
                    kind,
                    sha256: sha,
                },
            );
        }

        // Validity: one entry per table; mirrors equal their abep-n2n-0.11 source entries.
        let vrel = format!("{AIR_DIR}/rate_validity.toml");
        let vsha = files.get("rate_validity.toml").ok_or_else(|| model("rate_validity.toml is not pinned"))?;
        let vtext = utf8(&vrel, read_verified(&air.join("rate_validity.toml"), vsha)?)?;
        let validity = RateValidityTable::parse(&vtext, &vrel)?;
        let vtoml = toml_of(&vrel, &vtext)?;
        let n2rel = format!("{N2_DIR}/rate_validity.toml");
        let n2toml = toml_of(
            &n2rel,
            &utf8(
                &n2rel,
                std::fs::read(repo.join(&n2rel))
                    .map_err(|e| AbepError::Io { path: n2rel.clone(), message: e.to_string() })?,
            )?,
        )?;
        for (f, t) in &tables {
            if validity.validity(f) == Validity::MissingEntry {
                return Err(model(format!("{f}: no propellants_air/rate_validity.toml entry (HR-05)")));
            }
            if t.kind == TableKind::Reused {
                let name = f.trim_start_matches("../propellants/");
                if vtoml.get(f) != n2toml.get(name) {
                    return Err(model(format!(
                        "{f}: mirrored validity entry differs from propellants/rate_validity.toml"
                    )));
                }
            }
        }
        if let Some(extra) = validity.files().find(|f| !tables.contains_key(*f)) {
            return Err(model(format!("rate_validity.toml entry {extra} names no registered table")));
        }

        // Configurations.
        let mut configs = BTreeMap::new();
        for name in str_list(rs, "configs", &prel)? {
            let sha = files.get(&name).ok_or_else(|| model(format!("configuration {name} is not pinned")))?;
            let c = parse_config(&name, &utf8(&name, read_verified(&air.join(&name), sha)?)?)?;
            let gases: BTreeSet<&str> = c.species.iter().map(|x| x.0.as_str()).collect();
            for r in &c.reactions {
                let t = tables
                    .get(&r.file)
                    .ok_or_else(|| model(format!("{name}: {} is not a registered table", r.file)))?;
                if t.target != r.target {
                    return Err(model(format!(
                        "{name}: reaction on {} uses {} registered for {} (HR-04: no surrogate data)",
                        r.target, r.file, t.target
                    )));
                }
                if let Some(eq) = &r.equation {
                    let (lhs, rhs) = parse_equation(eq)?;
                    for term in lhs.iter().chain(&rhs).filter(|x| x.gas != "e") {
                        if !gases.contains(term.gas.as_str()) {
                            return Err(model(format!("{name}: {eq:?} names unconfigured gas {}", term.gas)));
                        }
                    }
                } else if !gases.contains(r.target.as_str()) {
                    return Err(model(format!("{name}: target {} is not a configured species", r.target)));
                }
            }
            configs.insert(name, c);
        }
        let nominal = s(rs, "nominal_config", &prel)?;
        let nominal_config = if nominal.is_empty() {
            None
        } else if configs.contains_key(nominal) {
            Some(nominal.to_string())
        } else {
            return Err(model(format!("nominal_config {nominal} is not a listed configuration")));
        };
        Ok(AirSet { label, status, nominal_config, tier1_gaps, blocking, history, tables, configs, validity, files })
    }

    /// The gate the AIR family reads (HR-07). Ok only for COMPLETE_FOR_PARAMETRIC_ENVELOPE.
    pub fn admission(&self) -> AbepResult<()> {
        let open = || {
            let mut v: Vec<String> = self.tier1_gaps.iter().map(|g| format!("tier-1 gap {g}")).collect();
            v.extend(self.blocking.iter().cloned());
            v.join("; ")
        };
        match self.status {
            SetStatus::CompleteForParametricEnvelope => Ok(()),
            SetStatus::IncompleteEvidence => Err(AbepError::IncompleteEvidence {
                message: format!("AIR Hall chemistry {} not admitted (INCOMPLETE_EVIDENCE): {}", self.label, open()),
            }),
            SetStatus::NotRepresentableInPinnedSolver => Err(model(format!(
                "AIR Hall chemistry {} is NOT_REPRESENTABLE_IN_PINNED_SOLVER: {}",
                self.label,
                open()
            ))),
        }
    }
}

/// A table rendered from its representation, as the writer would put it on disk.
#[derive(Debug, Clone, PartialEq)]
pub struct RenderedTable {
    /// Repository-relative path of the `.dat`.
    pub table: String,
    pub dat: String,
    pub source: String,
    /// sha256 the v0 DRAFT table has (the rendered `.dat` must equal it).
    pub v0_sha256: String,
    pub energies_ev: Vec<f64>,
    pub sigma_m2: Vec<f64>,
    pub tail: Tail,
}

fn num(v: &Value, what: &str) -> AbepResult<f64> {
    v.as_f64().filter(|x| x.is_finite()).ok_or_else(|| model(format!("{what} is not a finite number")))
}

/// Render the table of a `hall_air_xs_v1` representation with the admitted integrator (IX-01).
pub fn render_xs(repo: &Path, xs_rel: &str) -> AbepResult<RenderedTable> {
    let bytes =
        std::fs::read(repo.join(xs_rel)).map_err(|e| AbepError::Io { path: xs_rel.into(), message: e.to_string() })?;
    let v: Value = serde_json::from_slice(&bytes).map_err(|e| schema(xs_rel, e.to_string()))?;
    let get = |k: &str| v.get(k).ok_or_else(|| schema(xs_rel, format!("{k} missing")));
    if get("schema")?.as_str() != Some("hall_air_xs_v1")
        || get("prereg_lock_sha256")?.as_str() != Some(PREREG_LOCK_SHA256)
    {
        return Err(model(format!("{xs_rel}: not a hall_air_xs_v1 representation of this preregistration")));
    }
    let text = |k: &str| -> AbepResult<String> {
        get(k)?.as_str().map(str::to_string).ok_or_else(|| schema(xs_rel, format!("{k} is not a string")))
    };
    let tail = match text("tail")?.as_str() {
        "hold" => Tail::Hold,
        "zero" => Tail::Zero,
        other => return Err(model(format!("{xs_rel}: tail {other:?}"))),
    };
    let pts = get("points")?.as_array().ok_or_else(|| schema(xs_rel, "points is not a list"))?;
    let mut e = Vec::with_capacity(pts.len());
    let mut sg = Vec::with_capacity(pts.len());
    for (i, p) in pts.iter().enumerate() {
        let p = p.as_array().filter(|p| p.len() == 2).ok_or_else(|| schema(xs_rel, format!("point {i}")))?;
        e.push(num(&p[0], "energy")?);
        sg.push(num(&p[1], "cross section")?);
    }
    if get("n_points")?.as_u64() != Some(e.len() as u64) {
        return Err(schema(xs_rel, "n_points differs from the point count"));
    }
    crate::checked::CrossSection::new(e.clone(), sg.clone(), tail)?;
    let eps_max = num(get("eps_max_eV")?, "eps_max_eV")?;
    if eps_max != EPS_MAX_EV {
        return Err(model(format!("{xs_rel}: eps_max_eV {eps_max} is not the registered writer grid")));
    }
    let threshold = num(get("threshold_eV")?, "threshold_eV")?;
    let label = text("header_label")?;
    let source = text("source_text")?;
    let t = reference::hallthruster_table(&e, &sg, threshold, eps_max, &TailArg::from(tail), &label, &source)
        .map_err(AbepError::from)?;
    Ok(RenderedTable {
        table: text("table")?,
        dat: t.text,
        source: t.source_text.unwrap_or_default(),
        v0_sha256: text("v0_table_sha256")?,
        energies_ev: e,
        sigma_m2: sg,
        tail,
    })
}

/// Every representation file under [`XS_DIRS`] (repository-relative, sorted).
pub fn xs_files(repo: &Path) -> AbepResult<Vec<String>> {
    let mut out = Vec::new();
    for d in XS_DIRS {
        let p = repo.join(d);
        if !p.is_dir() {
            continue;
        }
        let mut v = Vec::new();
        list_files(&p, "", &mut v)?;
        out.extend(v.into_iter().filter(|f| f.ends_with(".json")).map(|f| format!("{d}/{f}")));
    }
    out.sort();
    Ok(out)
}

/// The source-support limit of a held-tail representation: the highest integer mean energy (<= 255 eV) up to which the
/// held-tail rate share stays below 1 % at every integer step (rate_validity.toml convention; the v0 builders' rule).
pub fn support_limit(e: &[f64], sigma: &[f64]) -> AbepResult<f64> {
    let mut last_ok = 0.0;
    let mut eps = 1.0;
    while eps <= SUPPORT_CAP_EV {
        let share = reference::tail_sensitivity(e, sigma, &[eps]).map_err(AbepError::from)?[0].1;
        if share >= TAIL_SHARE_LIMIT {
            break;
        }
        last_ok = eps;
        eps += 1.0;
    }
    Ok(last_ok)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn terms_and_conservation() {
        assert_eq!(parse_term("N(2+)").unwrap(), Term { gas: "N".into(), charge: 2, count: 1 });
        assert_eq!(parse_term("2e").unwrap(), Term { gas: "e".into(), charge: -1, count: 2 });
        assert_eq!(parse_term("O(-)").unwrap().charge, -1);
        assert_eq!(check_conservation("O2 + e -> O(+) + O + 2e").unwrap(), ("O2".to_string(), 0));
        assert_eq!(check_conservation("N(+) + e -> N(2+) + 2e").unwrap(), ("N".to_string(), 1));
        assert!(check_conservation("O2 + e -> O(+) + 2e").is_err(), "nuclei");
        assert!(check_conservation("O2 + e -> O(+) + O + e").is_err(), "charge");
        assert!(check_conservation("O(+) + N2 -> NO(+) + N").is_err(), "two heavy reactants (L-01)");
    }

    #[test]
    fn status_vocabulary() {
        for s in ["INCOMPLETE_EVIDENCE", "NOT_REPRESENTABLE_IN_PINNED_SOLVER", "COMPLETE_FOR_PARAMETRIC_ENVELOPE"] {
            assert_eq!(SetStatus::parse(s).unwrap().as_str(), s);
        }
        assert!(SetStatus::parse("VALIDATED").is_none());
    }
}
