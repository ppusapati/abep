"""Immutable, append-only registry of design Hall maps (DRAFT for owner review).

Lane fo_hallmap_schema_v2_registry (trigger T_PIVOT_HALLMAP_SCHEMA_V2_REGISTRY, owner disposition od_hardware_pivot).
Record format: schemas/hallmap/hallmap_registry_v1.json. Design notes: docs/hallmap/schema_v2/HALLMAP_REGISTRY.md.

One REGISTRATION record binds, by sha256, everything a design Hall map depends on: the map file, its raw-record dataset,
the ADMITTED transport-ensemble member (hall_ensemble.require_admitted; screening candidates are refused), the chemistry
config, the HallThruster.jl pin (must equal hallthruster_bridge/PINNED.toml), Vyovrinda geometry and B(z), the frozen
convergence pre-registration, the O4 dispositions file and the admission decision file (both must equal the member's
admission record), and the map schema version. A later WITHDRAWAL record can retire a registration; nothing is ever
edited or deleted. Records form a hash chain (prev_record_sha256) and are written with an exclusive, atomic create
(os.link of a fully written temporary file), so an existing record can never be overwritten.

verify() re-hashes every bound file, re-checks the pin and the member's admission against the CURRENT repository, and
checks the chain. It answers the open question of lane 15 (abep_sim/thermal_life.py, "no map registry"): a map-derived
record can be re-verified from its map_meta_sha256 with lookup_map_meta().

Milestones: not needed for A (no map is needed for conditional selection); a precondition for using any admitted-member
map as Milestone B/C evidence (provenance re-verification); C additionally needs the wall-life chain.

This module is pure: it is NOT wired into archengine, hall_map or thermal_life (wiring is a separate owner-approved change),
and it holds no physical value. hall_ensemble and hall_map are imported lazily (read only). No admitted member exists today
(credible set empty, 2026-09-26), so register() refuses every real member id.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import tempfile

RECORD_SCHEMA = "hallmap_registry_record_v1"
REGISTRY_SCHEMA_FILE = "schemas/hallmap/hallmap_registry_v1.json"
MAP_SCHEMAS = ("hall_map_schema_v1", "hall_map_schema_v2")
KINDS = ("REGISTRATION", "WITHDRAWAL")
RECORDS_SUBDIR = "records"
_RECORD_NAME = re.compile(r"^(\d{6})_([0-9a-f]{16})\.json$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
# Same rule as schemas/hallmap/hallmap_provenance_v1.json geometry.file / magnetic_field.file: P5 / ECHT evidence files are
# never Vyovrinda design geometry or B(z).
_EVIDENCE_FILE = re.compile(r"(^|[^A-Za-z0-9])[Pp]5([^0-9]|$)|[Ee][Cc][Hh][Tt]|[Bb]rabston|[Pp]eterson")

# Required keys per block (the JSON schema file carries the same lists; a test keeps them identical).
REGISTRATION_KEYS = ("schema", "kind", "seq", "prev_record_sha256", "registered_utc", "registered_by", "map",
                     "raw_records", "ensemble_member", "chemistry", "hallthruster", "geometry", "magnetic_field",
                     "convergence_prereg", "o4_dispositions", "admission_decision")
WITHDRAWAL_KEYS = ("schema", "kind", "seq", "prev_record_sha256", "registered_utc", "registered_by",
                   "withdraws_record_sha256", "reason", "decision")
BLOCK_KEYS = {
    "map": ("file", "sha256", "schema_version", "map_meta_sha256"),
    "raw_records": ("file", "sha256", "sha256_canonical_jsonl"),
    "ensemble_member": ("ensemble_member_id", "ensemble_file", "ensemble_sha256_at_registration"),
    "chemistry": ("config_id", "file", "sha256"),
    "hallthruster": ("commit", "pinned_toml_sha256_at_registration"),
    "geometry": ("id", "file", "sha256"),
    "magnetic_field": ("id", "file", "sha256"),
    "convergence_prereg": ("id", "file", "sha256"),
    "o4_dispositions": ("file", "sha256"),
    "admission_decision": ("file", "sha256"),
    "decision": ("file", "sha256"),
}
# Blocks whose file is re-hashed by verify(). ensemble file and PINNED.toml are recorded "at registration" only: they are
# living files (new members, reaction-set bumps); verify() re-checks the admission and the pinned commit instead.
REHASHED_BLOCKS = ("map", "raw_records", "chemistry", "geometry", "magnetic_field", "convergence_prereg",
                   "o4_dispositions", "admission_decision")


class RegistryError(ValueError):
    """Any refusal: invalid input, unadmitted member, hash mismatch, broken chain, attempted overwrite."""


# ------------------------------------------------------------------------------------------------ hashing / paths
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_canonical_jsonl(path: str) -> str:
    """sha256 of the dataset bytes: the file itself, or its decompressed content for a .gz file (the frozen-dataset
    convention of scripts/freeze_p5_n2_dataset.py: sha256 of the canonical JSONL, then gzip)."""
    if path.endswith(".gz"):
        with gzip.open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    return sha256_file(path)


def canonical_json_sha256(obj) -> str:
    """Same canonical form as abep_sim.thermal_life._canonical_sha256 (map_meta_sha256 of admitted_hallmap records)."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _rel(root: str, rel: str, what: str) -> str:
    """Absolute path of a repository-relative POSIX path; refuses absolute paths and escapes from root."""
    if not isinstance(rel, str) or not rel.strip():
        raise RegistryError(f"{what}: a repository-relative file path is required")
    if os.path.isabs(rel) or "\\" in rel:
        raise RegistryError(f"{what}: {rel!r} must be a repository-relative POSIX path")
    norm = os.path.normpath(rel)
    if norm.startswith("..") or norm != rel.rstrip("/"):
        raise RegistryError(f"{what}: {rel!r} is not a normalised path inside the repository")
    p = os.path.join(os.path.abspath(root), norm)
    if not os.path.isfile(p):
        raise RegistryError(f"{what}: file {rel!r} does not exist under {root!r}")
    return p


def _nonempty(v, what: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise RegistryError(f"{what} must be a non-empty string (no default)")
    return v


def _get(d, path: str):
    node = d
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


# ------------------------------------------------------------------------------------------------ lazy dependencies
def _load_ensemble(root: str, ensemble_file: str):
    from abep_sim import hall_ensemble      # read only; never modified
    return hall_ensemble.load_ensemble(_rel(root, ensemble_file, "ensemble_member.ensemble_file"))


def _require_admitted(member_id: str, ensemble: dict) -> dict:
    """hall_ensemble.require_admitted (screening candidates and unknown ids raise), then the member's admission block."""
    from abep_sim import hall_ensemble
    try:
        hall_ensemble.require_admitted(member_id, ensemble)
    except ValueError as exc:
        raise RegistryError(str(exc)) from exc
    for m in ensemble.get("members", []):
        if m.get("ensemble_member_id") == member_id:
            adm = m.get("admission")
            if not isinstance(adm, dict):
                raise RegistryError(f"admitted member {member_id} has no admission record")
            return adm
    raise RegistryError(f"{member_id} not found among admitted members")


def _pinned_commit(root: str) -> str:
    from abep_sim import hall_map           # read only; never modified
    return hall_map.pinned_commit(os.path.join(os.path.abspath(root), "hallthruster_bridge"))


# ------------------------------------------------------------------------------------------------ schema v2 helper
def load_hall_map_schema_v2(root: str, path: str = "schemas/hallmap/hall_map_schema_v2.json") -> dict:
    """Load schemas/hallmap/hall_map_schema_v2.json and check that the v1 schema it inherits is byte-identical to the one
    it was written against (v1 stays unchanged). Returns {'schema', 'meta_required', 'fields', 'map_fields',
    'not_supplied'}: v1 meta/fields plus the v2 additions; 'map_fields' are the scalar per-node fields only."""
    s2 = json.load(open(_rel(root, path, "hall_map_schema_v2")))
    inh = s2["inherits"]
    v1_path = _rel(root, inh["file"], "hall_map_schema_v1")
    if sha256_file(v1_path) != inh["sha256"]:
        raise RegistryError("hall_map_schema_v1.json differs from the version hall_map_schema_v2 inherits")
    v1 = json.load(open(v1_path))
    clash = (set(v1["fields"]) & set(s2["fields_added"])) | (set(v1["meta_required"]) & set(s2["meta_added"]))
    if clash:
        raise RegistryError(f"v2 redefines v1 keys {sorted(clash)}")
    fields = {**v1["fields"], **s2["fields_added"]}
    map_fields = tuple(list(v1["fields"]) + [k for k, v in s2["fields_added"].items()
                                             if v["level"].startswith("map field")])
    return {"schema": s2["schema"], "meta_required": {**v1["meta_required"], **s2["meta_added"]}, "fields": fields,
            "map_fields": map_fields, "not_supplied": s2["not_supplied"]}


# ------------------------------------------------------------------------------------------------ record validation
def validate_record(rec: dict) -> None:
    """Structural check of one record (the rules of schemas/hallmap/hallmap_registry_v1.json)."""
    if not isinstance(rec, dict) or rec.get("schema") != RECORD_SCHEMA:
        raise RegistryError(f"record schema must be {RECORD_SCHEMA!r}")
    kind = rec.get("kind")
    if kind not in KINDS:
        raise RegistryError(f"record kind must be one of {KINDS}")
    keys = REGISTRATION_KEYS if kind == "REGISTRATION" else WITHDRAWAL_KEYS
    if set(rec) != set(keys):
        raise RegistryError(f"{kind} record keys {sorted(rec)} != {sorted(keys)}")
    if not isinstance(rec["seq"], int) or isinstance(rec["seq"], bool) or rec["seq"] < 1:
        raise RegistryError("seq must be an integer >= 1")
    prev = rec["prev_record_sha256"]
    if (rec["seq"] == 1) != (prev is None) or (prev is not None and not _SHA.match(str(prev))):
        raise RegistryError("prev_record_sha256 must be null for seq 1 and a sha256 otherwise")
    if not isinstance(rec["registered_utc"], str) or not _UTC.match(rec["registered_utc"]):
        raise RegistryError("registered_utc must be YYYY-MM-DDTHH:MM:SSZ")
    _nonempty(rec["registered_by"], "registered_by")
    blocks = [b for b in BLOCK_KEYS if b in rec]
    for b in blocks:
        blk = rec[b]
        if not isinstance(blk, dict) or set(blk) != set(BLOCK_KEYS[b]):
            raise RegistryError(f"block {b!r} must have exactly {BLOCK_KEYS[b]}")
        for k, v in blk.items():
            if k.startswith("sha256") or k.endswith("sha256") or "_sha256_" in k:
                if k == "sha256" and b == "chemistry" and v is None and blk["file"] is None:
                    continue
                if not isinstance(v, str) or not _SHA.match(v):
                    raise RegistryError(f"{b}.{k} must be a 64-hex sha256")
            elif k == "file":
                if b == "chemistry" and v is None:
                    continue
                _nonempty(v, f"{b}.file")
            else:
                _nonempty(v, f"{b}.{k}")
    if kind == "REGISTRATION":
        if rec["map"]["schema_version"] not in MAP_SCHEMAS:
            raise RegistryError(f"map.schema_version must be one of {MAP_SCHEMAS}")
        if not _COMMIT.match(rec["hallthruster"]["commit"]):
            raise RegistryError("hallthruster.commit must be a 40-hex git commit")
        chem = rec["chemistry"]
        if chem["file"] is None and not chem["config_id"].startswith("builtin-"):
            raise RegistryError("chemistry.file may be null only for a built-in chemistry (config_id 'builtin-...')")
        if chem["file"] is None and chem["sha256"] is not None:
            raise RegistryError("a built-in chemistry has no file sha256")
    else:
        if not _SHA.match(str(rec["withdraws_record_sha256"])):
            raise RegistryError("withdraws_record_sha256 must be a sha256")
        _nonempty(rec["reason"], "reason")


def _record_bytes(rec: dict) -> bytes:
    return (json.dumps(rec, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode()


# ------------------------------------------------------------------------------------------------ reading
def _records_dir(registry_dir: str) -> str:
    return os.path.join(registry_dir, RECORDS_SUBDIR)


def read_records(registry_dir: str) -> list[tuple[str, str, dict]]:
    """[(file name, sha256 of file bytes, record)] in seq order. Raises on foreign files or unreadable records."""
    d = _records_dir(registry_dir)
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        if not _RECORD_NAME.match(name):
            raise RegistryError(f"foreign file {name!r} in the registry records directory")
        raw = open(os.path.join(d, name), "rb").read()
        try:
            rec = json.loads(raw)
        except ValueError as exc:
            raise RegistryError(f"record {name} is not valid JSON") from exc
        out.append((name, hashlib.sha256(raw).hexdigest(), rec))
    return out


# ------------------------------------------------------------------------------------------------ checks shared by
# register() and verify()
def _check_registration(rec: dict, root: str, ensemble: dict | None) -> tuple[list[str], list[str]]:
    """Re-check one REGISTRATION against the current repository. Returns (integrity problems, currency problems); both
    empty = verified. Integrity: a bound file changed or is missing, the map's meta/provenance disagrees, a forbidden file
    kind is bound. Currency: the pin moved or the member is no longer admitted with the same decision / O4 record (the
    registration stays intact but must not be used; a WITHDRAWAL record retires it)."""
    problems, currency = [], []

    def rehash(block):
        blk = rec[block]
        if blk["file"] is None:
            return
        try:
            p = _rel(root, blk["file"], f"{block}.file")
        except RegistryError as exc:
            problems.append(str(exc))
            return
        if sha256_file(p) != blk["sha256"]:
            problems.append(f"{block}: {blk['file']} no longer matches its registered sha256")
        if block == "raw_records" and sha256_canonical_jsonl(p) != blk["sha256_canonical_jsonl"]:
            problems.append("raw_records: dataset content no longer matches sha256_canonical_jsonl")

    for b in REHASHED_BLOCKS:
        rehash(b)
    for b in ("geometry", "magnetic_field"):
        if _EVIDENCE_FILE.search(rec[b]["file"]):
            problems.append(f"{b}.file {rec[b]['file']!r} looks like P5/ECHT evidence, not a Vyovrinda design file")
    cp = rec["convergence_prereg"]
    if "DRAFT" in cp["file"].upper() or "DRAFT" in cp["id"].upper():
        problems.append("convergence_prereg: a DRAFT pre-registration is never valid (frozen pre-registration required)")
    try:
        pin = _pinned_commit(root)
        if rec["hallthruster"]["commit"] != pin:
            currency.append(f"hallthruster.commit {rec['hallthruster']['commit']} != PINNED.toml commit {pin}")
    except (OSError, ValueError) as exc:
        currency.append(f"PINNED.toml unreadable: {exc}")
    mid = rec["ensemble_member"]["ensemble_member_id"]
    try:
        ens = ensemble if ensemble is not None else _load_ensemble(root, rec["ensemble_member"]["ensemble_file"])
        adm = _require_admitted(mid, ens)
        if adm.get("decision_sha256") != rec["admission_decision"]["sha256"]:
            currency.append(f"admission_decision sha256 differs from member {mid}'s admission decision_sha256")
        if os.path.normpath(os.path.join("hallthruster_bridge", str(adm.get("decision_file")))) != \
                os.path.normpath(rec["admission_decision"]["file"]):
            currency.append(f"admission_decision.file is not member {mid}'s admission decision_file")
        if adm.get("o4_dispositions_sha256") != rec["o4_dispositions"]["sha256"]:
            currency.append(f"o4_dispositions sha256 differs from member {mid}'s admission o4_dispositions_sha256")
        if os.path.normpath(os.path.join("hallthruster_bridge", str(adm.get("o4_dispositions_file")))) != \
                os.path.normpath(rec["o4_dispositions"]["file"]):
            currency.append(f"o4_dispositions.file is not member {mid}'s admission o4_dispositions_file")
    except (RegistryError, ValueError, OSError) as exc:
        currency.append(f"ensemble member {mid}: {exc}")
    try:
        mp = _rel(root, rec["map"]["file"], "map.file")
        problems += _check_map_meta(json.load(open(mp)), rec)
    except (RegistryError, ValueError, OSError) as exc:
        problems.append(f"map: {exc}")
    return problems, currency


# (registry path, meta.provenance path) pairs that must agree (lane 35 spec, schemas/hallmap/hallmap_provenance_v1.json)
PROVENANCE_EQUALITIES = (
    ("map.schema_version", "hall_map_schema.name"),
    ("ensemble_member.ensemble_member_id", "ensemble_member.ensemble_member_id"),
    ("hallthruster.commit", "hallthruster.pinned_commit"),
    ("hallthruster.commit", "hallthruster.installed_commit"),
    ("geometry.sha256", "geometry.sha256"),
    ("magnetic_field.sha256", "magnetic_field.sha256"),
    ("convergence_prereg.sha256", "numerics.convergence.prereg_sha256"),
    ("admission_decision.sha256", "ensemble_member.admission.decision_sha256"),
    ("o4_dispositions.sha256", "ensemble_member.admission.o4_dispositions_sha256"),
    ("raw_records.sha256_canonical_jsonl", "raw_records.sha256_canonical_jsonl"),
)


def _check_map_meta(doc: dict, rec: dict) -> list[str]:
    problems = []
    meta = doc.get("meta") if isinstance(doc, dict) else None
    if not isinstance(meta, dict):
        return ["map file has no meta object"]
    if canonical_json_sha256(meta) != rec["map"]["map_meta_sha256"]:
        problems.append("map meta no longer matches map_meta_sha256")
    if meta.get("schema") != rec["map"]["schema_version"]:
        problems.append(f"meta.schema {meta.get('schema')!r} != map.schema_version {rec['map']['schema_version']!r}")
    if meta.get("ensemble_member_id") != rec["ensemble_member"]["ensemble_member_id"]:
        problems.append("meta.ensemble_member_id differs from the registered member")
    if meta.get("hallthruster_commit") != rec["hallthruster"]["commit"]:
        problems.append("meta.hallthruster_commit differs from the registered pin")
    if meta.get("facility_ingestion") is not False:
        problems.append("meta.facility_ingestion must be false for a design (flight) map")
    prov = meta.get("provenance")
    if not isinstance(prov, dict):
        return problems + ["meta.provenance missing (docs/hallmap/HALLMAP_PRODUCTION_SPEC.md section 10 requires it)"]
    if _get(prov, "map_set.status") != "FROZEN":
        problems.append("meta.provenance.map_set.status must be FROZEN to register a design map")
    if _get(prov, "numerics.convergence.verdict") != "PASS":
        problems.append("meta.provenance.numerics.convergence.verdict must be PASS")
    for rpath, ppath in PROVENANCE_EQUALITIES:
        if _get(rec, rpath) != _get(prov, ppath):
            problems.append(f"registry {rpath} != meta.provenance.{ppath}")
    chem = rec["chemistry"]
    if chem["file"] is not None and _get(prov, "chemistry.config_sha256") != chem["sha256"]:
        problems.append("registry chemistry.sha256 != meta.provenance.chemistry.config_sha256")
    return problems


# ------------------------------------------------------------------------------------------------ verify / lookup
def verify(registry_dir: str, root: str, *, ensemble: dict | None = None) -> dict:
    """Re-verify the whole registry against the current repository. Never modifies anything.

    Returns {'ok': bool, 'n_records': int, 'chain_ok': bool, 'problems': [str], 'records': {record_sha256: {'seq',
    'kind', 'status', 'problems', 'currency'}}}. status: ACTIVE (verified registration), WITHDRAWN (a later WITHDRAWAL
    names it and its bound files are intact), INVALID (an integrity or currency check failed), or WITHDRAWAL for
    withdrawal records. Integrity problems (bound file changed, chain broken) always fail 'ok'; currency problems (pin
    moved, member no longer admitted) fail 'ok' until a WITHDRAWAL retires the registration. `ensemble` overrides
    load_ensemble() (tests only)."""
    problems, out = [], {}
    try:
        recs = read_records(registry_dir)
    except RegistryError as exc:
        return {"ok": False, "n_records": 0, "chain_ok": False, "problems": [str(exc)], "records": {}}
    chain_ok, prev, maps_active = True, None, {}
    for i, (name, sha, rec) in enumerate(recs, start=1):
        rp = []
        m = _RECORD_NAME.match(name)
        if int(m.group(1)) != i or m.group(2) != sha[:16]:
            rp.append(f"file name {name} does not match seq {i} / content sha256")
            chain_ok = False
        try:
            validate_record(rec)
        except RegistryError as exc:
            rp.append(str(exc))
            out[sha] = {"seq": i, "kind": rec.get("kind") if isinstance(rec, dict) else None, "status": "INVALID",
                        "problems": rp}
            chain_ok, prev = False, sha
            continue
        if rec["seq"] != i or rec["prev_record_sha256"] != prev:
            rp.append("hash chain broken (seq or prev_record_sha256)")
            chain_ok = False
        if rec["kind"] == "REGISTRATION":
            integ, cur = _check_registration(rec, root, ensemble)
            rp += integ
            if rec["map"]["sha256"] in maps_active:
                rp.append("map file already registered by an earlier record")
            maps_active.setdefault(rec["map"]["sha256"], sha)
            out[sha] = {"seq": i, "kind": "REGISTRATION", "status": "INVALID" if (rp or cur) else "ACTIVE",
                        "problems": rp, "currency": cur}
        else:
            tgt = out.get(rec["withdraws_record_sha256"])
            if tgt is None or tgt["kind"] != "REGISTRATION":
                rp.append("WITHDRAWAL names no earlier REGISTRATION record")
            elif tgt.get("withdrawn"):
                rp.append("target registration already withdrawn")
            else:
                # the withdrawn registration keeps its integrity problems; its currency problems no longer matter
                tgt["withdrawn"] = True
                tgt["status"] = "INVALID" if tgt["problems"] else "WITHDRAWN"
            try:
                p = _rel(root, rec["decision"]["file"], "decision.file")
                if sha256_file(p) != rec["decision"]["sha256"]:
                    rp.append("withdrawal decision file no longer matches its sha256")
            except RegistryError as exc:
                rp.append(str(exc))
            out[sha] = {"seq": i, "kind": "WITHDRAWAL", "status": "INVALID" if rp else "WITHDRAWAL", "problems": rp}
        prev = sha
    for sha, r in out.items():
        problems += [f"record {r['seq']} ({sha[:16]}): {p}" for p in r["problems"]]
        if not r.get("withdrawn"):
            problems += [f"record {r['seq']} ({sha[:16]}): {p}" for p in r.get("currency", [])]
    return {"ok": not problems and chain_ok, "n_records": len(recs), "chain_ok": chain_ok, "problems": problems,
            "records": out}


def lookup_map_meta(registry_dir: str, root: str, map_meta_sha256: str, *, ensemble: dict | None = None) -> dict:
    """The ACTIVE, fully re-verified registration whose map meta has this canonical sha256 (the map_meta_sha256 that
    abep_sim.thermal_life.hallmap_wall_inputs writes into admitted_hallmap provenance). Raises RegistryError if the
    registry does not verify, if no registration matches, or if the match is withdrawn or invalid."""
    if not isinstance(map_meta_sha256, str) or not _SHA.match(map_meta_sha256):
        raise RegistryError("map_meta_sha256 must be a 64-hex sha256")
    rep = verify(registry_dir, root, ensemble=ensemble)
    if not rep["chain_ok"]:
        raise RegistryError(f"registry chain does not verify: {rep['problems']}")
    hits = [(sha, rec) for _, sha, rec in read_records(registry_dir)
            if rec.get("kind") == "REGISTRATION" and _get(rec, "map.map_meta_sha256") == map_meta_sha256]
    if not hits:
        raise RegistryError("no registered map has this map_meta_sha256")
    for sha, rec in hits:
        st = rep["records"][sha]
        if st["status"] == "ACTIVE":
            return {"record_sha256": sha, "record": rec}
    raise RegistryError(f"registered map is not ACTIVE: {[rep['records'][s]['status'] for s, _ in hits]} "
                        f"{[rep['records'][s]['problems'] + rep['records'][s].get('currency', []) for s, _ in hits]}")


# ------------------------------------------------------------------------------------------------ appending
def _append(registry_dir: str, rec: dict) -> str:
    """Exclusive, atomic create of the next record file. Returns its sha256. Never overwrites."""
    validate_record(rec)
    data = _record_bytes(rec)
    sha = hashlib.sha256(data).hexdigest()
    d = _records_dir(registry_dir)
    os.makedirs(d, exist_ok=True)
    final = os.path.join(d, f"{rec['seq']:06d}_{sha[:16]}.json")
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=registry_dir)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o444)
        existing = [n for n in os.listdir(d) if n.startswith(f"{rec['seq']:06d}_")]
        if existing:
            raise RegistryError(f"seq {rec['seq']} already exists ({existing[0]}): the registry is append-only")
        try:
            os.link(tmp, final)          # atomic; fails if the name exists
        except FileExistsError as exc:
            raise RegistryError(f"{final} exists: records are never overwritten") from exc
    finally:
        os.unlink(tmp)
    return sha


def _next(registry_dir: str, root: str, ensemble) -> tuple[int, str | None]:
    rep = verify(registry_dir, root, ensemble=ensemble)
    if not rep["chain_ok"]:
        raise RegistryError(f"refusing to append to a registry whose chain does not verify: {rep['problems']}")
    recs = read_records(registry_dir)
    return len(recs) + 1, (recs[-1][1] if recs else None)


def build_registration(root: str, *, map_file: str, raw_records_file: str, ensemble_member_id: str, ensemble_file: str,
                       chemistry_config_id: str, chemistry_file: str | None, geometry_id: str, geometry_file: str,
                       bfield_id: str, bfield_file: str, convergence_prereg_id: str, convergence_prereg_file: str,
                       o4_dispositions_file: str, admission_decision_file: str, registered_by: str,
                       registered_utc: str, seq: int = 1, prev_record_sha256: str | None = None) -> dict:
    """Assemble a REGISTRATION record from repository-relative paths, hashing every file. Every argument is explicit
    (no defaults for anything that identifies evidence). Does not check admission; register() does."""
    def fblock(path, what):
        return sha256_file(_rel(root, path, what))

    mp = _rel(root, map_file, "map_file")
    doc = json.load(open(mp))
    meta = doc.get("meta") if isinstance(doc, dict) else None
    if not isinstance(meta, dict):
        raise RegistryError("map_file has no meta object")
    raw_p = _rel(root, raw_records_file, "raw_records_file")
    ens_p = _rel(root, ensemble_file, "ensemble_file")
    pinned_p = os.path.join(os.path.abspath(root), "hallthruster_bridge", "PINNED.toml")
    if not os.path.isfile(pinned_p):
        raise RegistryError("hallthruster_bridge/PINNED.toml not found under root")
    if chemistry_file is None:
        chem = {"config_id": _nonempty(chemistry_config_id, "chemistry_config_id"), "file": None, "sha256": None}
    else:
        chem = {"config_id": _nonempty(chemistry_config_id, "chemistry_config_id"), "file": chemistry_file,
                "sha256": fblock(chemistry_file, "chemistry_file")}
    return {
        "schema": RECORD_SCHEMA, "kind": "REGISTRATION", "seq": seq, "prev_record_sha256": prev_record_sha256,
        "registered_utc": registered_utc, "registered_by": registered_by,
        "map": {"file": map_file, "sha256": sha256_file(mp), "schema_version": meta.get("schema"),
                "map_meta_sha256": canonical_json_sha256(meta)},
        "raw_records": {"file": raw_records_file, "sha256": sha256_file(raw_p),
                        "sha256_canonical_jsonl": sha256_canonical_jsonl(raw_p)},
        "ensemble_member": {"ensemble_member_id": ensemble_member_id, "ensemble_file": ensemble_file,
                            "ensemble_sha256_at_registration": sha256_file(ens_p)},
        "chemistry": chem,
        "hallthruster": {"commit": meta.get("hallthruster_commit"),
                         "pinned_toml_sha256_at_registration": sha256_file(pinned_p)},
        "geometry": {"id": geometry_id, "file": geometry_file, "sha256": fblock(geometry_file, "geometry_file")},
        "magnetic_field": {"id": bfield_id, "file": bfield_file, "sha256": fblock(bfield_file, "bfield_file")},
        "convergence_prereg": {"id": convergence_prereg_id, "file": convergence_prereg_file,
                               "sha256": fblock(convergence_prereg_file, "convergence_prereg_file")},
        "o4_dispositions": {"file": o4_dispositions_file, "sha256": fblock(o4_dispositions_file, "o4_dispositions_file")},
        "admission_decision": {"file": admission_decision_file,
                               "sha256": fblock(admission_decision_file, "admission_decision_file")},
    }


def register(registry_dir: str, root: str, *, ensemble: dict | None = None, **kw) -> str:
    """Append a REGISTRATION after every check passes (see build_registration for the keyword arguments). The member must
    pass hall_ensemble.require_admitted on the ensemble file named (or on `ensemble`, tests only); screening candidates
    and unknown ids are refused. Returns the new record's sha256."""
    for k in ("registered_by", "registered_utc", "ensemble_member_id", "geometry_id", "bfield_id",
              "convergence_prereg_id"):
        _nonempty(kw.get(k), k)
    cp = kw.get("convergence_prereg_file") or ""
    if "DRAFT" in cp.upper():
        raise RegistryError("convergence_prereg_file: a DRAFT pre-registration is never valid")
    seq, prev = _next(registry_dir, root, ensemble)
    rec = build_registration(root, seq=seq, prev_record_sha256=prev, **kw)
    validate_record(rec)
    integ, cur = _check_registration(rec, root, ensemble)
    problems = integ + cur
    for _, _, old in read_records(registry_dir):
        if old.get("kind") == "REGISTRATION" and _get(old, "map.sha256") == rec["map"]["sha256"]:
            problems.append("this map file is already registered")
    if problems:
        raise RegistryError("registration refused: " + "; ".join(problems))
    return _append(registry_dir, rec)


def withdraw(registry_dir: str, root: str, *, record_sha256: str, reason: str, decision_file: str,
             registered_by: str, registered_utc: str, ensemble: dict | None = None) -> str:
    """Append a WITHDRAWAL of an earlier registration (e.g. its member eliminated by new evidence). The owner decision
    file is bound by sha256. The withdrawn record itself is never touched."""
    seq, prev = _next(registry_dir, root, ensemble)
    targets = {sha: rec for _, sha, rec in read_records(registry_dir)}
    if targets.get(record_sha256, {}).get("kind") != "REGISTRATION":
        raise RegistryError("record_sha256 names no REGISTRATION in this registry")
    if any(r.get("kind") == "WITHDRAWAL" and r.get("withdraws_record_sha256") == record_sha256
           for r in targets.values()):
        raise RegistryError("registration already withdrawn")
    rec = {"schema": RECORD_SCHEMA, "kind": "WITHDRAWAL", "seq": seq, "prev_record_sha256": prev,
           "registered_utc": registered_utc, "registered_by": registered_by, "withdraws_record_sha256": record_sha256,
           "reason": reason,
           "decision": {"file": decision_file, "sha256": sha256_file(_rel(root, decision_file, "decision_file"))}}
    return _append(registry_dir, rec)
