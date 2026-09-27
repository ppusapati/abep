#!/usr/bin/env python3
"""S1-readiness gate (fo_s1_readiness_gate; trigger T_PIVOT_S1_READINESS_GATE; owner disposition od_hardware_pivot).

Evaluates the eight owner conditions of docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json
(execution_directive_2026_09_27.S1_readiness_conditions) against machine-checkable evidence artifacts defined in the
spec docs/experiments/s1_readiness/s1_readiness_conditions_v1.json, and returns

    S1_READY      only if the owner disposition is APPROVED and all eight conditions are SATISFIED
    S1_NOT_READY  otherwise, listing every unsatisfied condition, its expected artifact(s), the failed checks and producer.

Rules (CLAUDE.md rule 3, docs/EVIDENCE.md): nothing is inferred or filled by assumption; a DRAFT / PROPOSED / PENDING
artifact never satisfies a condition; references are verified by recomputing sha256 on disk; only files inside the
repository are read. The module is pure and read-only: it writes a file only when ``--out`` is given. It imports nothing
from abep_sim or hallthruster_bridge and carries no physical, efficiency or threshold value.

S1 is qualification, not architecture selection: this gate schedules S1; it ranks, prefers or eliminates nothing.

Usage:
    python scripts/experiments/s1_readiness.py [--repo-root DIR] [--spec FILE] [--out FILE | --check FILE]
Exit status: 0 S1_READY (or --check identical), 1 S1_NOT_READY (or --check differs), 2 spec / usage error.
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

REPORT_SCHEMA = "abep_s1_readiness_report_v1"
SPEC_SCHEMA = "abep_s1_readiness_conditions_v1"
SPEC_RELPATH = "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json"
VERDICT_READY = "S1_READY"
VERDICT_NOT_READY = "S1_NOT_READY"
N_OWNER_CONDITIONS = 8
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
RULE_TYPES = ("equals", "in", "is_true", "iso_date", "nonempty_string", "sha256_ref", "decisions_decided",
              "location_choice", "covers", "each_item", "any_item", "quantity")
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
    if any(p == ".." for p in parts) or not parts:
        return None
    return "/".join(p for p in parts if p != ".")


def _inside(root: Path, rel: str) -> Path | None:
    s = safe_relpath(rel)
    if s is None:
        return None
    p = (root / s)
    try:
        p.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return p


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
        if t in ("each_item", "any_item"):
            _validate_rules(r.get("rules"), f"{where}/{t}:{r.get('field')}", cond_ids)
        if t not in ("location_choice",) and not isinstance(r.get("field"), str):
            raise SpecError(f"{where}: rule {t} needs a field")
        if t == "location_choice" and not all(isinstance(r.get(k), (str, dict)) for k in ("decisions_field", "decision_id", "choice_key", "map")):
            raise SpecError(f"{where}: location_choice needs decisions_field, decision_id, choice_key, map")
        if t == "sha256_ref" and "artifact_of" in r and r["artifact_of"] not in cond_ids:
            raise SpecError(f"{where}: artifact_of {r['artifact_of']!r} is not a condition id")
        if t == "decisions_decided" and not (isinstance(r.get("ids"), list) and r["ids"] and r.get("choice_key")):
            raise SpecError(f"{where}: decisions_decided needs ids and choice_key")
        if t == "decisions_decided" and "choice_pattern" in r:
            cp = r["choice_pattern"]
            if not (isinstance(cp, str) and "{id}" in cp):
                raise SpecError(f"{where}: choice_pattern must be a string containing {{id}}")
            try:
                re.compile(cp.replace("{id}", re.escape("D-01")))
            except re.error as e:
                raise SpecError(f"{where}: choice_pattern is not a valid regex: {e}") from e
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
    if not isinstance(conds, list) or len(conds) != N_OWNER_CONDITIONS:
        raise SpecError(f"spec must define exactly {N_OWNER_CONDITIONS} owner conditions")
    ids = [c.get("id") for c in conds]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) for i in ids):
        raise SpecError("condition ids must be unique strings")
    cond_ids = set(ids)
    sem = spec.get("gate_semantics", {})
    if not sem.get("draft_status_tokens") or not sem.get("draft_status_fields"):
        raise SpecError("gate_semantics must list draft_status_tokens and draft_status_fields")
    auth = spec.get("authority")
    if not isinstance(auth, dict) or safe_relpath(auth.get("path")) is None:
        raise SpecError("authority must name a repository-relative path")
    _validate_rules(auth.get("rules"), "authority", cond_ids)
    for c in conds:
        if not _is_nonempty_str(c.get("owner_condition")):
            raise SpecError(f"{c['id']}: owner_condition missing")
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
    if t == "decisions_decided":
        pat = f" matching {r['choice_pattern']}" if r.get("choice_pattern") else ""
        return (f"{f} records a decided {r['choice_key']}{pat} for {r['ids'][0]}..{r['ids'][-1]} "
                f"({len(r['ids'])} decisions; DRAFT/PROPOSED/PENDING choices rejected)")
    if t == "location_choice":
        return f"file location matches the owner's {r['decision_id']} choice"
    if t == "covers":
        return f"{f}[].{r['key']} covers {', '.join(r['required'])}{what}"
    if t == "each_item":
        return f"every {f}[] item: " + "; ".join(describe_rule(x) for x in r["rules"])
    if t == "any_item":
        return f"at least one {f}[] item: " + "; ".join(describe_rule(x) for x in r["rules"]) + what
    return t


class _Ctx:
    def __init__(self, root: Path, resolved: dict[str, str | None], artifact_path: str | None,
                 draft_tokens=("DRAFT", "PROPOSED", "PENDING")):
        self.root = root
        self.draft_tokens = tuple(draft_tokens)
        self.resolved = resolved            # condition id -> uniquely resolved artifact path (or None)
        self.artifact_path = artifact_path  # the artifact under evaluation (repository-relative)


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


def check_rule(r: dict, obj, ctx: _Ctx) -> list[str]:
    """Return the list of failure messages of rule r on obj (empty = pass)."""
    t = r["type"]
    if t == "location_choice":
        decs = get_field(obj, r["decisions_field"])
        choice = None
        if isinstance(decs, list):
            for d in decs:
                if isinstance(d, dict) and d.get("id") == r["decision_id"]:
                    choice = d.get(r["choice_key"])
        if choice not in r["map"]:
            return [f"{r['decision_id']}.{r['choice_key']} is not one of {sorted(r['map'])}: {_show(choice)}"]
        here = str(PurePosixPath(ctx.artifact_path).parent) if ctx.artifact_path else None
        if here != r["map"][choice]:
            return [f"file is at {here}, but the owner's {r['decision_id']} choice {choice} puts it in {r['map'][choice]}"]
        return []
    f = r["field"]
    v = get_field(obj, f)
    if t == "equals":
        return [] if v is not _MISSING and v == r["value"] and type(v) is type(r["value"]) else \
            [f"{f} must be {json.dumps(r['value'])}, got {_show(v)}"]
    if t == "in":
        return [] if v is not _MISSING and v in r["values"] else [f"{f} must be one of {json.dumps(r['values'])}, got {_show(v)}"]
    if t == "is_true":
        return [] if v is True else [f"{f} must be true, got {_show(v)}"]
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
            errs.append(f"{f}.evidence_class must be one of {list(EVIDENCE_CLASSES)}, got {_show(v.get('evidence_class', _MISSING))}")
        return errs
    if t == "sha256_ref":
        e = _check_sha_ref(r, v, ctx)
        return [e] if e else []
    if t == "decisions_decided":
        if not isinstance(v, list):
            return [f"{f} must be a list of decisions, got {_show(v)}"]
        got = {d.get("id"): d.get(r["choice_key"]) for d in v if isinstance(d, dict)}
        toks = tuple(ctx.draft_tokens)
        errs = []
        for i in r["ids"]:
            c = got.get(i)
            if not _is_nonempty_str(c):
                errs.append(f"{f}: no owner {r['choice_key']} for {i}")
            elif any(tok in c.upper() for tok in toks):
                errs.append(f"{f}: {i}.{r['choice_key']} = {json.dumps(c)} is a DRAFT / PROPOSED / PENDING choice")
            elif r.get("choice_pattern") and not re.fullmatch(r["choice_pattern"].replace("{id}", re.escape(i)), c):
                errs.append(f"{f}: {i}.{r['choice_key']} = {json.dumps(c)} is not an option id of {i} "
                            f"(pattern {r['choice_pattern']})")
        return errs
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
    draft token. A nested DRAFT / PROPOSED / PENDING (e.g. one LOCK-1 decision or one feed point) rejects the artifact."""
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
    found = []
    for rel in paths:
        p = _inside(root, rel)
        if p is not None and p.is_file():
            found.append(safe_relpath(rel))
    return found


def _load_json(root: Path, rel: str):
    try:
        with open(root / rel, encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, f"cannot be read as JSON: {type(e).__name__}"


def _eval_alternative(root: Path, alt: dict, sem: dict, resolved: dict) -> dict:
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
    ctx = _Ctx(root, resolved, rel, sem["draft_status_tokens"])
    drafts = draft_markers(obj, sem)
    fails = []
    for r in alt["rules"]:
        fails.extend(check_rule(r, obj, ctx) if isinstance(obj, dict) else [f"{rel} is not a JSON object"])
    out["failures"] = drafts + fails
    out["state"] = "REJECTED_DRAFT" if drafts else ("INVALID" if fails else "SATISFIED")
    return out


_STATE_ORDER = ("SATISFIED", "REJECTED_DRAFT", "INVALID", "AMBIGUOUS", "MISSING")


def evaluate(repo_root: Path | str | None = None, spec_path: Path | str | None = None) -> dict:
    """Evaluate the S1-readiness gate on a repository. Pure: reads files, writes nothing."""
    root = Path(repo_root) if repo_root is not None else default_repo_root()
    sp = Path(spec_path) if spec_path is not None else root / SPEC_RELPATH
    spec = load_spec(sp)
    sem = spec["gate_semantics"]
    try:
        spec_rel = sp.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        spec_rel = sp.name
    conds = spec["conditions"]

    # pass 1: unique artifact location per condition (for artifact_of cross-references); no content is trusted here
    resolved: dict[str, str | None] = {}
    for c in conds:
        hits = [f for a in c["alternatives"] for f in _locate(root, a["paths"])]
        resolved[c["id"]] = hits[0] if len(hits) == 1 else None

    # authority
    arel = safe_relpath(spec["authority"]["path"])
    auth = {"path": arel, "sha256": None, "ok": False, "failures": []}
    ap = _inside(root, arel)
    if ap is None or not ap.is_file():
        auth["failures"] = [f"owner disposition {arel} not found"]
    else:
        auth["sha256"] = sha256_file(ap)
        aobj, err = _load_json(root, arel)
        if err:
            auth["failures"] = [f"{arel} {err}"]
        else:
            ctx = _Ctx(root, resolved, arel, sem["draft_status_tokens"])
            for r in spec["authority"]["rules"]:
                auth["failures"].extend(check_rule(r, aobj, ctx))
        auth["ok"] = not auth["failures"]

    results, missing = [], []
    for c in conds:
        alts = [_eval_alternative(root, a, sem, resolved) for a in c["alternatives"]]
        sat = [a["id"] for a in alts if a["state"] == "SATISFIED"]
        if sat:
            state = "SATISFIED"
        else:
            present = [a["state"] for a in alts if a["state"] != "MISSING"]
            state = min(present, key=_STATE_ORDER.index) if present else "MISSING"
        pre_found = [p for p in c.get("precursors", []) if _inside(root, p["path"]) is not None and _inside(root, p["path"]).is_file()]
        pre_absent = [p for p in c.get("precursors", []) if p not in pre_found]
        entry = {
            "id": c["id"],
            "owner_condition": c["owner_condition"],
            "state": state,
            "satisfied_by": sat[0] if sat else None,
            "availability": ("SATISFIED" if sat else ("PARTIAL_PRECURSORS_ONLY" if pre_found else "NONE")),
            "alternatives": alts,
            "precursors_found": [{"path": safe_relpath(p["path"]), "what": p["what"],
                                  "sha256": sha256_file(root / safe_relpath(p["path"]))} for p in pre_found],
            "precursors_absent": [{"path": safe_relpath(p["path"]), "what": p["what"]} for p in pre_absent],
        }
        results.append(entry)
        if not sat:
            missing.append({
                "condition": c["id"],
                "owner_condition": c["owner_condition"],
                "state": state,
                "availability": entry["availability"],
                "needed": [{"alternative": a["id"], "artifact": a["artifact"], "expected_paths": a["expected_paths"],
                            "state": a["state"], "failures": a["failures"], "produced_by": a["produced_by"],
                            "required": a["required"]} for a in alts],
                "note": "precursor drafts exist but never satisfy the condition" if pre_found else
                        "no artifact and no precursor draft in the repository",
            })

    ready = auth["ok"] and not missing
    return {
        "schema": REPORT_SCHEMA,
        "gate": "fo_s1_readiness_gate",
        "trigger": spec.get("trigger"),
        "generated_by": "scripts/experiments/s1_readiness.py",
        "spec": {"path": spec_rel, "sha256": sha256_file(sp), "status": spec.get("status")},
        "note": ("Generated from the repository state; deterministic (no clock, no absolute paths). S1 is qualification, "
                 "not architecture selection. A DRAFT / PROPOSED artifact never satisfies a condition; nothing is inferred."),
        "authority": auth,
        "verdict": VERDICT_READY if ready else VERDICT_NOT_READY,
        "n_conditions": len(conds),
        "n_satisfied": sum(1 for r in results if r["state"] == "SATISFIED"),
        "n_missing_items": len(missing),
        "missing": missing,
        "conditions": results,
        "milestones": spec.get("milestones"),
    }


def render(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S1-readiness gate (fo_s1_readiness_gate)")
    ap.add_argument("--repo-root", default=None, help="repository root (default: this script's repository)")
    ap.add_argument("--spec", default=None, help=f"conditions spec (default: <repo>/{SPEC_RELPATH})")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--out", default=None, help="write the report to this file (otherwise print)")
    g.add_argument("--check", default=None, help="compare the report with this file byte for byte")
    a = ap.parse_args(argv)
    try:
        rep = evaluate(a.repo_root, a.spec)
    except SpecError as e:
        print(f"s1_readiness: spec error: {e}", file=sys.stderr)
        return 2
    text = render(rep)
    if a.check:
        try:
            with open(a.check, encoding="utf-8") as f:
                same = f.read() == text
        except OSError as e:
            print(f"s1_readiness: cannot read {a.check}: {e}", file=sys.stderr)
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
          f"{rep['n_missing_items']} missing item(s)", file=sys.stderr)
    return 0 if rep["verdict"] == VERDICT_READY else 1


if __name__ == "__main__":
    sys.exit(main())
