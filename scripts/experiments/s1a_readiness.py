#!/usr/bin/env python3
"""S1a engineering-readiness gate (fo_s1a_engineering_gate; trigger T_PIVOT_S1A_ENGINEERING_GATE; owner disposition
od_hardware_pivot, addendum A3 next_execution.S1a_engineering_gate).

Answers: "Can we safely and usefully begin NON-score-bearing engineering qualification (S1a)?" against the spec
docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json and returns

    S1A_READY      only if the authority holds (the four owner decision files present and byte-identical to their pins,
                   each addendum's amends_sha256 = sha256 of the original on disk, the S1a scope read from A3 equal to the
                   spec's owner_text, every condition's owner_clause a verbatim part of it) and every condition, including
                   the mandatory data firewall S1A-FW, is SATISFIED
    S1A_NOT_READY  otherwise, listing every unsatisfied condition with its expected artifact(s), failed checks, producer.

The data firewall fails closed: if S1A-FW is not SATISFIED the verdict is S1A_NOT_READY whatever else holds, and every
rule that checks against the firewall (member_of_artifact) fails as well.

This gate is separate from the N4 S1-readiness gate (scripts/experiments/s1_readiness.py), which it neither imports nor
reads. S1A_READY never schedules S1, never satisfies an N4 condition, never authorises a Hall-on H-1 reading and never
makes S1a data score-bearing.

Rules (CLAUDE.md rule 3, docs/EVIDENCE.md): nothing is inferred or filled by assumption; a DRAFT / PROPOSED / PENDING
artifact never satisfies a condition; references are verified by recomputing sha256 on disk; only files inside the
repository are read. The module is pure and read-only: it writes a file only with ``--out``. It imports nothing from
abep_sim or hallthruster_bridge and carries no physical, efficiency, safety-limit or threshold value.

Usage:
    python scripts/experiments/s1a_readiness.py [--repo-root DIR] [--spec FILE] [--out FILE | --check FILE]
Exit status: 0 S1A_READY (or --check identical), 1 S1A_NOT_READY (or --check differs), 2 spec / usage error.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

REPORT_SCHEMA = "abep_s1a_readiness_report_v1"
SPEC_SCHEMA = "abep_s1a_readiness_conditions_v1"
SPEC_RELPATH = "docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json"
GATE_ID = "fo_s1a_engineering_gate"
VERDICT_READY = "S1A_READY"
VERDICT_NOT_READY = "S1A_NOT_READY"
FIREWALL_ID = "S1A-FW"
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
RULE_TYPES = ("equals", "in", "is_true", "is_bool", "iso_date", "nonempty_string", "sha256_ref", "covers",
              "each_item", "any_item", "quantity", "member_of_artifact")
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:T(\d{2}:\d{2}(?::\d{2})?)Z)?$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_MISSING = object()


class SpecError(ValueError):
    """The conditions spec is malformed (a usage error, never a readiness verdict)."""


# ----------------------------------------------------------------------------------------------------------- helpers
def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_relpath(rel) -> str | None:
    """Normalised repository-relative POSIX path, or None if absolute / escaping / not a string."""
    if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel):
        return None
    parts = PurePosixPath(rel.replace("\\", "/")).parts
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(p for p in parts if p != ".")


def _inside(root: Path, rel: str) -> Path | None:
    s = safe_relpath(rel)
    if s is None:
        return None
    p = root / s
    try:
        p.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return p


def _is_file(root: Path, rel: str) -> bool:
    p = _inside(root, rel)
    return p is not None and p.is_file()


def get_field(obj, dotted: str):
    cur = obj
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return _MISSING
        cur = cur[key]
    return cur


def _is_nonempty_str(v) -> bool:
    return isinstance(v, str) and v.strip() != "" and not v.strip().upper().startswith("TBD")


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float("inf"), float("-inf"))


def _is_iso_date(v) -> bool:
    """ISO 8601 calendar date YYYY-MM-DD, optionally THH:MM[:SS]Z; the date and time must exist (2026-13-45 fails)."""
    if not isinstance(v, str):
        return False
    m = _DATE_RE.match(v)
    if not m:
        return False
    try:
        datetime.date.fromisoformat(m.group(1))
        if m.group(2):
            datetime.time.fromisoformat(m.group(2))
    except ValueError:
        return False
    return True


def _show(v) -> str:
    if v is _MISSING:
        return "absent"
    return json.dumps(v, sort_keys=True)[:120]


def _load_json(root: Path, rel: str):
    try:
        with open(root / rel, encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, f"cannot be read as JSON: {type(e).__name__}"


# --------------------------------------------------------------------------------------------------- spec validation
def load_spec(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
    except FileNotFoundError as e:
        raise SpecError(f"conditions spec not found: {path}") from e
    except json.JSONDecodeError as e:
        raise SpecError(f"conditions spec is not valid JSON: {path}: {e}") from e
    validate_spec(spec)
    return spec


def _validate_rules(rules, where: str, cond_ids: set[str]):
    if not isinstance(rules, list) or not rules:
        raise SpecError(f"{where}: rules must be a non-empty list")
    for r in rules:
        t = r.get("type") if isinstance(r, dict) else None
        if t not in RULE_TYPES:
            raise SpecError(f"{where}: unknown rule type {t!r}")
        if not isinstance(r.get("field"), str) or not r["field"]:
            raise SpecError(f"{where}: rule {t} needs a field")
        if t in ("each_item", "any_item"):
            _validate_rules(r.get("rules"), f"{where}/{t}:{r['field']}", cond_ids)
        if t in ("sha256_ref", "member_of_artifact") and "artifact_of" in r and r["artifact_of"] not in cond_ids:
            raise SpecError(f"{where}: artifact_of {r['artifact_of']!r} is not a condition id")
        if t == "member_of_artifact" and not (r.get("artifact_of") and isinstance(r.get("list_field"), str)
                                              and isinstance(r.get("key"), str)):
            raise SpecError(f"{where}: member_of_artifact needs artifact_of, list_field and key")
        if t == "sha256_ref" and "path_prefix" in r and (safe_relpath(r["path_prefix"]) is None
                                                          or not r["path_prefix"].endswith("/")):
            raise SpecError(f"{where}: path_prefix must be a repository-relative directory ending in '/'")
        if t == "covers" and not (isinstance(r.get("required"), list) and r["required"] and r.get("key")):
            raise SpecError(f"{where}: covers needs key and required")
        if t == "in" and not (isinstance(r.get("values"), list) and r["values"]):
            raise SpecError(f"{where}: in needs values")
        if t == "equals" and "value" not in r:
            raise SpecError(f"{where}: equals needs value")


def validate_spec(spec: dict) -> None:
    if not isinstance(spec, dict) or spec.get("schema") != SPEC_SCHEMA:
        raise SpecError(f"spec schema must be {SPEC_SCHEMA!r}")
    conds = spec.get("conditions")
    if not isinstance(conds, list) or not conds:
        raise SpecError("spec must define conditions")
    ids = [c.get("id") if isinstance(c, dict) else None for c in conds]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and i for i in ids):
        raise SpecError("condition ids must be unique non-empty strings")
    if FIREWALL_ID not in ids:
        raise SpecError(f"the mandatory data-firewall condition {FIREWALL_ID} is missing from the spec")
    fw = conds[ids.index(FIREWALL_ID)]
    if fw.get("mandatory") is not True or fw.get("fail_closed") is not True:
        raise SpecError(f"{FIREWALL_ID} must be declared mandatory and fail_closed")
    cond_ids = set(ids)
    sem = spec.get("gate_semantics", {})
    if not sem.get("draft_status_tokens") or not sem.get("draft_status_fields"):
        raise SpecError("gate_semantics must list draft_status_tokens and draft_status_fields")
    auth = spec.get("authority")
    docs = auth.get("documents") if isinstance(auth, dict) else None
    if not isinstance(docs, list) or not docs:
        raise SpecError("authority.documents must be a non-empty list")
    roles = [d.get("role") if isinstance(d, dict) else None for d in docs]
    if len(set(roles)) != len(roles) or not all(isinstance(r, str) and r for r in roles):
        raise SpecError("authority document roles must be unique non-empty strings")
    for d in docs:
        where = f"authority/{d['role']}"
        if safe_relpath(d.get("path")) is None:
            raise SpecError(f"{where}: path must be repository-relative")
        if not (isinstance(d.get("sha256"), str) and _SHA_RE.match(d["sha256"])):
            raise SpecError(f"{where}: sha256 must pin the document (64 lowercase hex)")
        _validate_rules(d.get("rules"), where, cond_ids)
        if "amends_role" in d and (d["amends_role"] not in roles or d["amends_role"] == d["role"]
                                   or not isinstance(d.get("amends_sha256_field"), str)):
            raise SpecError(f"{where}: amends_role must name another authority document, with amends_sha256_field")
    ot = auth.get("owner_text")
    if not (isinstance(ot, dict) and ot.get("role") in roles and isinstance(ot.get("field"), str)
            and _is_nonempty_str(ot.get("text"))):
        raise SpecError("authority.owner_text needs role (an authority document), field and text")
    for q in auth.get("quotes", []):
        if not (isinstance(q, dict) and q.get("role") in roles and isinstance(q.get("field"), str)
                and _is_nonempty_str(q.get("text"))):
            raise SpecError("authority.quotes entries need role (an authority document), field and text")
    for c in conds:
        if not _is_nonempty_str(c.get("owner_clause")):
            raise SpecError(f"{c['id']}: owner_clause missing")
        alts = c.get("alternatives")
        if not isinstance(alts, list) or not alts:
            raise SpecError(f"{c['id']}: at least one alternative artifact is required")
        for a in alts:
            paths = a.get("paths")
            if not isinstance(paths, list) or not paths or any(safe_relpath(p) is None for p in paths):
                raise SpecError(f"{c['id']}/{a.get('id')}: paths must be repository-relative")
            if not _is_nonempty_str(a.get("produced_by")):
                raise SpecError(f"{c['id']}/{a.get('id')}: produced_by missing")
            _validate_rules(a.get("rules"), f"{c['id']}/{a.get('id')}", cond_ids)
        for p in c.get("precursors", []):
            if safe_relpath(p.get("path")) is None:
                raise SpecError(f"{c['id']}: precursor path must be repository-relative")
    _evaluation_order(conds)  # raises on a member_of_artifact cycle


def _deps(cond: dict) -> set[str]:
    """Condition ids whose SATISFIED state this condition's rules need (member_of_artifact)."""
    out: set[str] = set()

    def walk(rules):
        for r in rules:
            if r["type"] == "member_of_artifact":
                out.add(r["artifact_of"])
            if r["type"] in ("each_item", "any_item"):
                walk(r["rules"])
    for a in cond["alternatives"]:
        walk(a["rules"])
    out.discard(cond["id"])
    return out


def _evaluation_order(conds: list[dict]) -> list[str]:
    ids = [c["id"] for c in conds]
    deps = {c["id"]: _deps(c) for c in conds}
    order: list[str] = []
    while len(order) < len(ids):
        ready = [i for i in ids if i not in order and deps[i] <= set(order)]
        if not ready:
            raise SpecError("member_of_artifact dependencies form a cycle")
        order.extend(ready)
    return order


# ------------------------------------------------------------------------------------------------------ rule engine
def describe_rule(r: dict) -> str:
    t, f = r["type"], r.get("field")
    what = f" ({r['what']})" if r.get("what") else ""
    if t == "equals":
        return f"{f} == {json.dumps(r['value'])}{what}"
    if t == "in":
        return f"{f} in {json.dumps(r['values'])}{what}"
    if t == "is_true":
        return f"{f} is true{what}"
    if t == "is_bool":
        return f"{f} is a boolean{what}"
    if t == "iso_date":
        return f"{f} is an ISO 8601 date{what}"
    if t == "nonempty_string":
        return f"{f} is a non-empty, non-TBD string{what}"
    if t == "quantity":
        return f"{f} = {{value, unit, source, evidence_class}}{what}"
    if t == "sha256_ref":
        pin = []
        if r.get("path_equals"):
            pin.append(f"path {r['path_equals']}")
        if r.get("artifact_of"):
            pin.append(f"the {r['artifact_of']} artifact")
        if r.get("path_prefix"):
            pin.append(f"under {r['path_prefix']}")
        return f"{f} = {{path, sha256}} matching the file on disk" + (f" ({'; '.join(pin)})" if pin else "") + what
    if t == "covers":
        return f"{f}[].{r['key']} covers {', '.join(r['required'])}{what}"
    if t == "member_of_artifact":
        return (f"{f} is one of the {r['list_field']}[].{r['key']} of the SATISFIED {r['artifact_of']} artifact{what}")
    if t == "each_item":
        return f"every {f}[] item: " + "; ".join(describe_rule(x) for x in r["rules"])
    if t == "any_item":
        return f"at least one {f}[] item: " + "; ".join(describe_rule(x) for x in r["rules"]) + what
    return t


class _Ctx:
    def __init__(self, root: Path, resolved: dict, states: dict, draft_tokens=("DRAFT", "PROPOSED", "PENDING")):
        self.root = root
        self.resolved = resolved        # condition id -> uniquely resolved artifact path (or None)
        self.states = states            # condition id -> evaluated state (for member_of_artifact)
        self.draft_tokens = tuple(draft_tokens)


def _check_sha_ref(r: dict, v, ctx: _Ctx) -> str | None:
    f = r["field"]
    if not isinstance(v, dict):
        return f"{f}: expected {{path, sha256}}, got {_show(v)}"
    rel, sha = v.get("path"), v.get("sha256")
    srel = safe_relpath(rel)
    if srel is None:
        return f"{f}.path is not a repository-relative path: {_show(rel)}"
    if not (isinstance(sha, str) and _SHA_RE.match(sha)):
        return f"{f}.sha256 is not 64 lowercase hex: {_show(sha)}"
    if r.get("path_equals") and srel != safe_relpath(r["path_equals"]):
        return f"{f}.path must be {r['path_equals']}, got {srel}"
    if r.get("path_prefix") and not srel.startswith(safe_relpath(r["path_prefix"]) + "/"):
        return f"{f}.path must lie under {r['path_prefix']}, got {srel}"
    if r.get("artifact_of"):
        want = ctx.resolved.get(r["artifact_of"])
        if want is None:
            return f"{f}: cannot verify, no unique {r['artifact_of']} artifact exists"
        if srel != want:
            return f"{f}.path must be the {r['artifact_of']} artifact {want}, got {srel}"
    p = _inside(ctx.root, srel)
    if p is None or not p.is_file():
        return f"{f}.path does not exist in the repository: {srel}"
    actual = sha256_file(p)
    if actual != sha:
        return f"{f}.sha256 mismatch for {srel}: recorded {sha}, on disk {actual}"
    return None


def _check_member(r: dict, v, ctx: _Ctx) -> str | None:
    f, dep = r["field"], r["artifact_of"]
    if ctx.states.get(dep) != "SATISFIED":
        return (f"{f}: cannot be checked, the {dep} artifact is not SATISFIED "
                f"(state {ctx.states.get(dep, 'NOT_EVALUATED')}); fails closed")
    rel = ctx.resolved.get(dep)
    obj, err = _load_json(ctx.root, rel) if rel else (None, "not resolved")
    lst = get_field(obj, r["list_field"]) if isinstance(obj, dict) else _MISSING
    if err or not isinstance(lst, list):
        return f"{f}: cannot read {r['list_field']} of the {dep} artifact; fails closed"
    allowed = sorted({x.get(r["key"]) for x in lst if isinstance(x, dict) and isinstance(x.get(r["key"]), str)})
    if not isinstance(v, str) or v not in allowed:
        return f"{f} = {_show(v)} is not one of the {dep} {r['list_field']} ids {allowed}"
    return None


def check_rule(r: dict, obj, ctx: _Ctx) -> list[str]:
    """Return the list of failure messages of rule r on obj (empty = pass)."""
    t, f = r["type"], r["field"]
    v = get_field(obj, f)
    if t == "equals":
        return [] if v is not _MISSING and v == r["value"] and type(v) is type(r["value"]) else \
            [f"{f} must be {json.dumps(r['value'])}, got {_show(v)}"]
    if t == "in":
        return [] if v is not _MISSING and v in r["values"] else [f"{f} must be one of {json.dumps(r['values'])}, got {_show(v)}"]
    if t == "is_true":
        return [] if v is True else [f"{f} must be true, got {_show(v)}"]
    if t == "is_bool":
        return [] if isinstance(v, bool) else [f"{f} must be a boolean, got {_show(v)}"]
    if t == "iso_date":
        return [] if _is_iso_date(v) else [f"{f} must be a valid ISO 8601 date, got {_show(v)}"]
    if t == "nonempty_string":
        return [] if _is_nonempty_str(v) else [f"{f} must be a non-empty, non-TBD string, got {_show(v)}"]
    if t == "quantity":
        if not isinstance(v, dict):
            return [f"{f} must be {{value, unit, source, evidence_class}}, got {_show(v)}"]
        errs = []
        val = v.get("value")
        if not (_is_number(val) or (isinstance(val, dict) and val and all(_is_number(x) for x in val.values()))):
            errs.append(f"{f}.value must be a number or an object of numbers, got {_show(val)}")
        for k in ("unit", "source"):
            if not _is_nonempty_str(v.get(k)):
                errs.append(f"{f}.{k} must be a non-empty, non-TBD string, got {_show(v.get(k, _MISSING))}")
        if v.get("evidence_class") not in EVIDENCE_CLASSES:
            errs.append(f"{f}.evidence_class must be one of {list(EVIDENCE_CLASSES)}, "
                        f"got {_show(v.get('evidence_class', _MISSING))}")
        return errs
    if t == "sha256_ref":
        e = _check_sha_ref(r, v, ctx)
        return [e] if e else []
    if t == "member_of_artifact":
        e = _check_member(r, v, ctx)
        return [e] if e else []
    if t == "covers":
        if not isinstance(v, list):
            return [f"{f} must be a list, got {_show(v)}"]
        have = {d.get(r["key"]) for d in v if isinstance(d, dict)}
        miss = [x for x in r["required"] if x not in have]
        return [f"{f}: missing {r['key']} {', '.join(miss)}"] if miss else []
    if t in ("each_item", "any_item"):
        if not isinstance(v, list) or not v:
            return [f"{f} must be a non-empty list, got {_show(v)}"]
        per_item = []
        for i, item in enumerate(v):
            errs = []
            for sub in r["rules"]:
                errs.extend(check_rule(sub, item, ctx) if isinstance(item, dict) else [f"item is not an object: {_show(item)}"])
            per_item.append([f"{f}[{i}].{e}" for e in errs])
        if t == "each_item":
            return [e for errs in per_item for e in errs]
        return [] if any(not errs for errs in per_item) else \
            [f"{f}: no item satisfies: " + "; ".join(describe_rule(x) for x in r["rules"]) + (f" ({r['what']})" if r.get("what") else "")]
    raise SpecError(f"unknown rule type {t!r}")


def draft_markers(obj, sem: dict, _prefix: str = "") -> list[str]:
    """Every draft_status_fields key, at ANY nesting depth (objects and list items), whose string value contains a
    draft token. A nested DRAFT / PROPOSED / PENDING rejects the artifact."""
    out = []
    if isinstance(obj, dict):
        for k in sorted(obj):
            v = obj[k]
            where = f"{_prefix}{k}"
            if k in sem["draft_status_fields"] and isinstance(v, str) and \
                    any(tok in v.upper() for tok in sem["draft_status_tokens"]):
                out.append(f"{where} = {json.dumps(v)} marks a DRAFT / PROPOSED / PENDING artifact "
                           "(never satisfies a condition)")
            out.extend(draft_markers(v, sem, where + "."))
    elif isinstance(obj, list):
        base = _prefix[:-1] if _prefix.endswith(".") else _prefix
        for i, item in enumerate(obj):
            out.extend(draft_markers(item, sem, f"{base}[{i}]."))
    return out


# ------------------------------------------------------------------------------------------------------- evaluation
def _locate(root: Path, paths: list[str]) -> list[str]:
    return [safe_relpath(rel) for rel in paths if _is_file(root, rel)]


def _eval_alternative(root: Path, alt: dict, sem: dict, ctx: _Ctx) -> dict:
    found = _locate(root, alt["paths"])
    out = {"id": alt["id"], "artifact": alt.get("artifact"), "expected_paths": [safe_relpath(p) for p in alt["paths"]],
           "found_paths": found, "sha256": None, "state": None, "failures": [],
           "required": [describe_rule(r) for r in alt["rules"]], "produced_by": alt["produced_by"]}
    if not found:
        out["state"] = "MISSING"
        return out
    if len(found) > 1:
        out["state"] = "AMBIGUOUS"
        out["failures"] = [f"artifact present at {len(found)} candidate locations ({', '.join(found)}); the gate never chooses"]
        return out
    rel = found[0]
    out["sha256"] = sha256_file(root / rel)
    obj, err = _load_json(root, rel)
    if err:
        out["state"], out["failures"] = "INVALID", [f"{rel} {err}"]
        return out
    drafts = draft_markers(obj, sem)
    fails = []
    for r in alt["rules"]:
        fails.extend(check_rule(r, obj, ctx) if isinstance(obj, dict) else [f"{rel} is not a JSON object"])
    out["failures"] = drafts + fails
    out["state"] = "REJECTED_DRAFT" if drafts else ("INVALID" if fails else "SATISFIED")
    return out


def evaluate_authority(root: Path, spec: dict) -> dict:
    """Fail-closed check of the owner decision files the gate derives from. Records each file's sha256 on disk."""
    sem = spec["gate_semantics"]
    auth = spec["authority"]
    docs, objs, shas = [], {}, {}
    ctx = _Ctx(root, {}, {}, sem["draft_status_tokens"])
    for d in auth["documents"]:
        rel = safe_relpath(d["path"])
        ent = {"role": d["role"], "path": rel, "expected_sha256": d["sha256"], "sha256": None, "ok": False,
               "failures": []}
        if not _is_file(root, rel):
            ent["failures"].append(f"owner decision file {rel} not found")
        else:
            ent["sha256"] = shas[d["role"]] = sha256_file(root / rel)
            if ent["sha256"] != d["sha256"]:
                ent["failures"].append(f"{rel} altered: sha256 on disk {ent['sha256']}, pinned {d['sha256']}")
            obj, err = _load_json(root, rel)
            if err:
                ent["failures"].append(f"{rel} {err}")
            elif not isinstance(obj, dict):
                ent["failures"].append(f"{rel} is not a JSON object")
            else:
                objs[d["role"]] = obj
                for r in d["rules"]:
                    ent["failures"].extend(f"{rel}: {e}" for e in check_rule(r, obj, ctx))
        docs.append(ent)
    by_role = {e["role"]: e for e in docs}
    for d in auth["documents"]:
        ent, obj = by_role[d["role"]], objs.get(d["role"])
        if obj is None or "amends_role" not in d:
            continue
        target = shas.get(d["amends_role"])
        got = get_field(obj, d["amends_sha256_field"])
        if target is None:
            ent["failures"].append(f"{ent['path']}: amended document ({d['amends_role']}) missing; chain unverifiable")
        elif got != target:
            ent["failures"].append(f"{ent['path']}: {d['amends_sha256_field']} = {_show(got)} does not equal the "
                                   f"sha256 of the {d['amends_role']} file on disk ({target})")
    # the S1a scope, verbatim, and each condition's clause inside it
    ot = auth["owner_text"]
    src = objs.get(ot["role"])
    owner_text_ok = False
    if src is not None:
        ent = by_role[ot["role"]]
        got = get_field(src, ot["field"])
        if got != ot["text"]:
            ent["failures"].append(f"{ent['path']}: {ot['field']} = {_show(got)} does not equal the spec's owner_text "
                                   "verbatim")
        else:
            owner_text_ok = True
            for c in spec["conditions"]:
                if c["owner_clause"] not in got:
                    ent["failures"].append(f"{ent['path']}: {c['id']} owner_clause {json.dumps(c['owner_clause'])} "
                                           f"is not a verbatim part of {ot['field']}")
    for q in auth.get("quotes", []):
        src = objs.get(q["role"])
        if src is None:
            continue
        got = get_field(src, q["field"])
        if not (isinstance(got, str) and q["text"] in got):
            by_role[q["role"]]["failures"].append(f"{by_role[q['role']]['path']}: quote {json.dumps(q['text'][:60])}... "
                                                  f"is not a verbatim part of {q['field']}")
    for ent in docs:
        ent["ok"] = not ent["failures"]
    return {"ok": all(e["ok"] for e in docs),
            "owner_text_source": {"path": safe_relpath(next(d["path"] for d in auth["documents"]
                                                            if d["role"] == ot["role"])),
                                  "field": ot["field"], "verbatim_match": owner_text_ok},
            "documents": docs,
            "failures": [f for e in docs for f in e["failures"]]}


_STATE_ORDER = ("SATISFIED", "REJECTED_DRAFT", "INVALID", "AMBIGUOUS", "MISSING")


def evaluate(repo_root: Path | str | None = None, spec_path: Path | str | None = None) -> dict:
    """Evaluate the S1a engineering-readiness gate on a repository. Pure: reads files, writes nothing."""
    root = Path(repo_root) if repo_root is not None else default_repo_root()
    sp = Path(spec_path) if spec_path is not None else root / SPEC_RELPATH
    spec = load_spec(sp)
    sem = spec["gate_semantics"]
    try:
        spec_rel = sp.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        spec_rel = sp.name
    conds = spec["conditions"]
    by_id = {c["id"]: c for c in conds}

    # pass 1: unique artifact location per condition (for artifact_of references); no content is trusted here
    resolved: dict[str, str | None] = {}
    for c in conds:
        hits = [f for a in c["alternatives"] for f in _locate(root, a["paths"])]
        resolved[c["id"]] = hits[0] if len(hits) == 1 else None

    auth = evaluate_authority(root, spec)

    # pass 2: conditions in dependency order (the firewall before the procedures that must match its classes)
    states: dict[str, str] = {}
    evaluated: dict[str, tuple[str, list[dict]]] = {}
    for cid in _evaluation_order(conds):
        ctx = _Ctx(root, resolved, states, sem["draft_status_tokens"])
        alts = [_eval_alternative(root, a, sem, ctx) for a in by_id[cid]["alternatives"]]
        if any(a["state"] == "SATISFIED" for a in alts):
            state = "SATISFIED"
        else:
            present = [a["state"] for a in alts if a["state"] != "MISSING"]
            state = min(present, key=_STATE_ORDER.index) if present else "MISSING"
        states[cid] = state
        evaluated[cid] = (state, alts)

    results, missing = [], []
    for c in conds:
        state, alts = evaluated[c["id"]]
        sat = [a["id"] for a in alts if a["state"] == "SATISFIED"]
        pre = c.get("precursors", [])
        pre_found = [p for p in pre if _is_file(root, p["path"])]
        entry = {
            "id": c["id"],
            "owner_clause": c["owner_clause"],
            "task_statement": c.get("task_statement"),
            "mandatory_fail_closed": bool(c.get("fail_closed")),
            "state": state,
            "satisfied_by": sat[0] if sat else None,
            "availability": "SATISFIED" if sat else ("PARTIAL_PRECURSORS_ONLY" if pre_found else "NONE"),
            "alternatives": alts,
            "precursors_found": [{"path": safe_relpath(p["path"]), "what": p["what"],
                                  "sha256": sha256_file(root / safe_relpath(p["path"]))} for p in pre_found],
            "precursors_absent": [{"path": safe_relpath(p["path"]), "what": p["what"]}
                                  for p in pre if p not in pre_found],
        }
        results.append(entry)
        if not sat:
            missing.append({
                "condition": c["id"],
                "owner_clause": c["owner_clause"],
                "state": state,
                "availability": entry["availability"],
                "needed": [{"alternative": a["id"], "artifact": a["artifact"], "expected_paths": a["expected_paths"],
                            "state": a["state"], "failures": a["failures"], "produced_by": a["produced_by"],
                            "required": a["required"]} for a in alts],
                "note": "precursor drafts exist but never satisfy the condition" if pre_found else
                        "no artifact and no precursor draft in the repository",
            })

    fw_state = states[FIREWALL_ID]
    firewall = {
        "condition": FIREWALL_ID,
        "state": fw_state,
        "fail_closed": fw_state != "SATISFIED",
        "effect": ("firewall SATISFIED: S1a data are limited to the owner-frozen allowed classes; held-out H-1 outputs "
                   "are forbidden / embargoed with the W5 OUTPUTS_SEEN consequence")
        if fw_state == "SATISFIED" else
        (f"FAIL CLOSED: the data firewall is {fw_state}; the verdict is {VERDICT_NOT_READY} whatever else holds, and "
         "no S1a procedure can be matched to an allowed data class"),
    }
    ready = auth["ok"] and not missing
    return {
        "schema": REPORT_SCHEMA,
        "gate": GATE_ID,
        "trigger": spec.get("trigger"),
        "question": spec.get("question"),
        "generated_by": "scripts/experiments/s1a_readiness.py",
        "spec": {"path": spec_rel, "sha256": sha256_file(sp), "status": spec.get("status")},
        "note": ("Generated from the repository state; deterministic (no clock, no absolute paths). S1a is "
                 "non-score-bearing engineering qualification with no H-1 Hall discharge; S1A_READY never schedules S1 "
                 "(N4, separate gate, not read here) and never satisfies an N4 condition. A DRAFT / PROPOSED artifact "
                 "never satisfies a condition; nothing is inferred."),
        "authority": auth,
        "verdict": VERDICT_READY if ready else VERDICT_NOT_READY,
        "n_conditions": len(conds),
        "n_satisfied": sum(1 for r in results if r["state"] == "SATISFIED"),
        "n_missing_items": len(missing),
        "firewall": firewall,
        "missing": missing,
        "conditions": results,
        "relation": spec.get("relation"),
        "milestones": spec.get("milestones"),
    }


def render(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S1a engineering-readiness gate (fo_s1a_engineering_gate)")
    ap.add_argument("--repo-root", default=None, help="repository root (default: this script's repository)")
    ap.add_argument("--spec", default=None, help=f"conditions spec (default: <repo>/{SPEC_RELPATH})")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--out", default=None, help="write the report to this file (otherwise print)")
    g.add_argument("--check", default=None, help="compare the report with this file byte for byte")
    a = ap.parse_args(argv)
    try:
        rep = evaluate(a.repo_root, a.spec)
    except SpecError as e:
        print(f"s1a_readiness: spec error: {e}", file=sys.stderr)
        return 2
    text = render(rep)
    if a.check:
        try:
            with open(a.check, encoding="utf-8") as f:
                same = f.read() == text
        except OSError as e:
            print(f"s1a_readiness: cannot read {a.check}: {e}", file=sys.stderr)
            return 2
        print("identical" if same else "DIFFERS")
        return 0 if same else 1
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    print(f"{rep['verdict']}: {rep['n_satisfied']}/{rep['n_conditions']} conditions satisfied, "
          f"{rep['n_missing_items']} missing item(s); firewall {rep['firewall']['state']}", file=sys.stderr)
    return 0 if rep["verdict"] == VERDICT_READY else 1


if __name__ == "__main__":
    sys.exit(main())
