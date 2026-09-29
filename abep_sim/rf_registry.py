"""Append-only registry of RF response maps (parallel RF || Hall investigation, v2).

Same evidence philosophy as the Hall pipeline (hallmap_registry), without copying Hall-specific logic:

    measurement or external high-fidelity solve -> immutable exported map file -> SHA-256 -> schema validation
    -> REGISTER (status REGISTERED_NOT_ADMITTED) -> ADMIT (owner decision file, sha-pinned) -> response map use

* A map is identified by the SHA-256 of its file bytes; any change is a new map.
* Records are append-only JSON files ``NNNN_<record-sha16>.json``; existing records are never rewritten.
* Admission is never self-declared in a map: it exists only as an ADMIT record that pins an owner decision file
  containing ``"decided_by": "owner"`` and ``"admits_rf_map_sha256": <map sha>``. A later WITHDRAW record revokes it.
* ``verify`` re-hashes every referenced file and fails on any mismatch.
"""
from __future__ import annotations

import hashlib
import json
import os

REGISTRY_VERSION = "rf_registry_v1"
ACTIONS = ("REGISTER", "ADMIT", "WITHDRAW")
STATES = ("UNREGISTERED", "REGISTERED_NOT_ADMITTED", "ADMITTED", "WITHDRAWN")


class RFRegistryError(ValueError):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _rel(root: str, path: str) -> str:
    ap = os.path.abspath(os.path.join(root, path))
    rr = os.path.abspath(root)
    if os.path.commonpath([ap, rr]) != rr:
        raise RFRegistryError(f"{path!r} is outside the repository root")
    if not os.path.isfile(ap):
        raise RFRegistryError(f"{path!r} does not exist")
    return os.path.relpath(ap, rr)


def records(registry_dir: str) -> list[dict]:
    """All records, verified as an unbroken hash chain: each record's body hashes to its record_sha256, seq equals
    its position, and prev_record_sha256 equals the previous record's sha (a deleted or reordered record breaks it)."""
    d = os.path.join(registry_dir, "records")
    if not os.path.isdir(d):
        return []
    out, prev = [], None
    for pos, name in enumerate(sorted(n for n in os.listdir(d) if n.endswith(".json"))):
        rec = json.load(open(os.path.join(d, name)))
        body = {k: v for k, v in rec.items() if k != "record_sha256"}
        if hashlib.sha256(_canon(body)).hexdigest() != rec.get("record_sha256"):
            raise RFRegistryError(f"record {name} was modified (record_sha256 mismatch)")
        if rec.get("seq") != pos or rec.get("prev_record_sha256") != prev:
            raise RFRegistryError(f"record chain broken at {name} (a record was deleted, inserted or reordered)")
        prev = rec["record_sha256"]
        out.append(rec)
    return out


def _append(registry_dir: str, body: dict) -> dict:
    d = os.path.join(registry_dir, "records")
    os.makedirs(d, exist_ok=True)
    existing = records(registry_dir)
    seq = len(existing)
    body = dict(body, registry_version=REGISTRY_VERSION, seq=seq,
                prev_record_sha256=existing[-1]["record_sha256"] if existing else None)
    rec = dict(body, record_sha256=hashlib.sha256(_canon(body)).hexdigest())
    path = os.path.join(d, f"{seq:04d}_{rec['record_sha256'][:16]}.json")
    with open(path, "x") as f:                                  # never overwrite
        json.dump(rec, f, indent=1, sort_keys=True)
        f.write("\n")
    return rec


_TRANSITIONS = {("UNREGISTERED", "REGISTER"): "REGISTERED_NOT_ADMITTED",
                ("REGISTERED_NOT_ADMITTED", "ADMIT"): "ADMITTED",
                ("REGISTERED_NOT_ADMITTED", "WITHDRAW"): "WITHDRAWN",
                ("ADMITTED", "WITHDRAW"): "WITHDRAWN"}


def state(registry_dir: str, map_sha256: str) -> str:
    """State from a validated transition sequence; an illegal transition (e.g. ADMIT without REGISTER) raises."""
    st = "UNREGISTERED"
    for rec in records(registry_dir):
        if rec["map_sha256"] != map_sha256:
            continue
        nxt = _TRANSITIONS.get((st, rec["action"]))
        if nxt is None:
            raise RFRegistryError(f"illegal registry transition {st} --{rec['action']}--> for {map_sha256[:12]}")
        st = nxt
    return st


def register(registry_dir: str, root: str, map_file: str) -> dict:
    from .rf_map import load_document                           # validates the map document
    rel = _rel(root, map_file)
    sha = sha256_file(os.path.join(root, rel))
    if state(registry_dir, sha) != "UNREGISTERED":
        raise RFRegistryError(f"map {sha[:12]} is already registered")
    doc = load_document(os.path.join(root, rel))
    return _append(registry_dir, {"action": "REGISTER", "map_file": rel, "map_sha256": sha,
                                  "map_id": doc["meta"]["map_id"], "evidence_class": doc["meta"]["evidence_class"]})


def admit(registry_dir: str, root: str, map_sha256: str, decision_file: str) -> dict:
    if state(registry_dir, map_sha256) != "REGISTERED_NOT_ADMITTED":
        raise RFRegistryError(f"map {map_sha256[:12]} is not in state REGISTERED_NOT_ADMITTED")
    rel = _rel(root, decision_file)
    dec = json.load(open(os.path.join(root, rel)))
    if dec.get("decided_by") != "owner" or dec.get("admits_rf_map_sha256") != map_sha256:
        raise RFRegistryError("admission needs an owner decision file with decided_by = 'owner' and "
                              "admits_rf_map_sha256 equal to the map's sha256")
    return _append(registry_dir, {"action": "ADMIT", "map_sha256": map_sha256, "decision_file": rel,
                                  "decision_sha256": sha256_file(os.path.join(root, rel))})


def withdraw(registry_dir: str, map_sha256: str, reason: str) -> dict:
    if state(registry_dir, map_sha256) not in ("REGISTERED_NOT_ADMITTED", "ADMITTED"):
        raise RFRegistryError(f"map {map_sha256[:12]} cannot be withdrawn from its current state")
    if not isinstance(reason, str) or not reason.strip():
        raise RFRegistryError("a withdrawal needs a reason")
    return _append(registry_dir, {"action": "WITHDRAW", "map_sha256": map_sha256, "reason": reason})


def head(registry_dir: str) -> str | None:
    """sha256 of the newest record (the chain head); pin it (e.g. in a commit message or decision) to detect tail
    truncation, which the chain alone cannot see."""
    recs = records(registry_dir)
    return recs[-1]["record_sha256"] if recs else None


def verify(registry_dir: str, root: str, expected_head_sha256: str | None = None) -> dict:
    """Re-hash every referenced map and decision file and validate every transition. Returns {map_sha: state};
    raises on any mismatch. LIMIT: deleting the newest record(s) leaves a valid shorter chain; that is detected
    only against an externally pinned head (``expected_head_sha256``) or the git history of the registry."""
    if expected_head_sha256 is not None and head(registry_dir) != expected_head_sha256:
        raise RFRegistryError("registry head does not match the pinned head (records truncated or appended)")
    for rec in records(registry_dir):
        if rec["action"] == "REGISTER":
            p = os.path.join(root, rec["map_file"])
            if not os.path.isfile(p) or sha256_file(p) != rec["map_sha256"]:
                raise RFRegistryError(f"map file {rec['map_file']} missing or modified after registration")
        if rec["action"] == "ADMIT":
            p = os.path.join(root, rec["decision_file"])
            if not os.path.isfile(p) or sha256_file(p) != rec["decision_sha256"]:
                raise RFRegistryError(f"decision file {rec['decision_file']} missing or modified")
    shas = {r["map_sha256"] for r in records(registry_dir)}
    for s_ in shas:
        state(registry_dir, s_)                                  # validates the transition sequence
    return {s: state(registry_dir, s) for s in sorted(shas)}
