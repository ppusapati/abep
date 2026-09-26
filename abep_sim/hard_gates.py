"""Architecture hard-gate matrix and evaluator (hall_only / rf_hall / ecr_hall).

The matrix (docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json, schema
schemas/architecture_comparison/hard_gates_v1.schema.json, explained in HARD_GATES.md next to the matrix) holds one gate
per RFP requirement as recorded in this repository, plus the owner's PROPOSED gates. This module evaluates ONE
architecture against it:

    evaluate(architecture, evidence, admitted_members=())  ->  per-gate verdict PASS / FAIL / UNDETERMINED

Rules it enforces (see HARD_GATES.md):
- missing or insufficient evidence => UNDETERMINED. Nothing is ever PASS by default; with no evidence every gate is
  UNDETERMINED.
- FAIL needs a failing-side bound (or a boolean outcome) from a basis the matrix lists as sufficient for that criterion,
  of ARCHITECTURE scope (it holds for every design of the architecture), covering the part of the envelope the matrix
  requires. A model result from an unadmitted Hall closure (screening candidates included) is never verdict-bearing, and
  neither are point estimates, assumptions, engineering estimates or literature on similar hardware.
- admitted_members is checked against the transport ensemble (abep_sim.hall_ensemble.require_admitted): a screening
  candidate or an unknown id raises, and so does evidence that labels a screening candidate as admitted.
- a basis that needs a derivation script counts only if that script exists as a file inside the repository.
- open owner readings never decide an elimination: a criterion counts for FAIL (counts_for_fail) only if its FAIL holds
  under every open reading, and its fail_must_cover spans every reading; criteria that bind under one reading only count
  for PASS (conservative) and never FAIL their gate.
- Hall-closure evidence never reaches the closure-independent upstream elements (matrix hall_closure_scope): on a
  per-element criterion it raises.
- an architecture is ELIMINATED only when a binding (RFP or owner-adopted) gate is FAIL. PROPOSED gates are evaluated
  and reported ("would eliminate if adopted") but never eliminate.
- sufficient evidence on both sides of a criterion is a CONFLICT: the verdict stays UNDETERMINED and nothing is
  eliminated until the owner resolves it.
- verdicts are tagged with the earliest decision milestone the evidence used supports (A conditional /
  B physics-backed); C (PDR freeze) additionally needs one integrated design passing every binding gate and no
  undecided owner item. In design maps the key '__architecture__' (ARCH_KEY) stands for architecture-scope evidence.
- the result also lists the conditions under which a conditional (milestone A) selection would hold. No architecture is
  ranked and no winner is declared.

Pure: no simulation, not wired into archengine (goldens do not move). Other lanes' shared contracts (bus-power boundary,
comparison harness, thermal/life, evidence matrices, ...) are referenced by path only and resolved lazily on request.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import os
import re
import sys
from typing import Any, Iterable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARD_GATES_DIR = os.path.join(ROOT, "docs", "architecture_comparison", "hard_gates")
MATRIX_FILE = os.path.join(HARD_GATES_DIR, "hard_gate_matrix_v1.json")
REGISTER_FILE = os.path.join(HARD_GATES_DIR, "evidence_register_v1.json")
STATUS_FILE = os.path.join(HARD_GATES_DIR, "hard_gate_status_v1.json")
DOC_FILE = os.path.join(HARD_GATES_DIR, "HARD_GATES.md")
SCHEMA_FILE = os.path.join(ROOT, "schemas", "architecture_comparison", "hard_gates_v1.schema.json")

MATRIX_SCHEMA = "hard_gate_matrix_v1"
EVIDENCE_SCHEMA = "hard_gate_evidence_v1"
RESULT_SCHEMA = "hard_gate_evaluation_v1"
RESULT_SET_SCHEMA = "hard_gate_evaluation_set_v1"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
VERDICTS = ("PASS", "FAIL", "UNDETERMINED")
MILESTONES = ("A", "B", "C")
ARCH_KEY = "__architecture__"          # passing evidence of architecture scope: holds for every design
BINDING_STATUSES = ("RFP", "OWNER_ADOPTED")
_RANK = {m: i for i, m in enumerate(MILESTONES)}
_OPEN_CRITERION_STATUSES = ("RFP_INTERPRETATION_OPEN", "TBD")
TABLE_BEGIN = "<!-- BEGIN GENERATED: python -m abep_sim.hard_gates render-table -->"
TABLE_END = "<!-- END GENERATED -->"


# ---------------------------------------------------------------------------------------------------------------------
# Minimal JSON Schema (2020-12 subset) validator. jsonschema is not a project dependency; this implements exactly the
# keywords the hard-gate schema uses and refuses any other keyword, so the schema cannot silently outgrow it.
# ---------------------------------------------------------------------------------------------------------------------
_ANNOTATIONS = {"$schema", "$id", "$defs", "$comment", "title", "description", "default", "examples"}
SUPPORTED_KEYWORDS = frozenset({"type", "required", "properties", "additionalProperties", "propertyNames", "const",
                                "enum", "pattern", "items", "minItems", "maxItems", "uniqueItems", "minimum",
                                "maximum", "minLength", "$ref", "oneOf", "anyOf", "allOf", "not", "if", "then"}
                               | _ANNOTATIONS)
_JSON_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


class SchemaKeywordError(ValueError):
    """The schema uses a keyword the built-in validator does not implement."""


def _is_type(v: Any, t: str) -> bool:
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _JSON_TYPES[t])


def check_schema_keywords(schema: Any, path: str = "$") -> None:
    """Walk every subschema and raise SchemaKeywordError on a keyword this validator does not implement."""
    if isinstance(schema, bool):
        return
    if not isinstance(schema, dict):
        raise SchemaKeywordError(f"{path}: a subschema must be an object or a boolean")
    unknown = {k for k in schema if not k.startswith("x-")} - SUPPORTED_KEYWORDS
    if unknown:
        raise SchemaKeywordError(f"schema keyword(s) {sorted(unknown)} at {path} are not implemented")
    for key in ("properties", "$defs"):
        for name, sub in schema.get(key, {}).items():
            check_schema_keywords(sub, f"{path}.{key}.{name}")
    for key in ("items", "not", "if", "then", "propertyNames", "additionalProperties"):
        if key in schema and not (key == "additionalProperties" and isinstance(schema[key], bool)):
            check_schema_keywords(schema[key], f"{path}.{key}")
    for key in ("oneOf", "anyOf", "allOf"):
        for i, sub in enumerate(schema.get(key, [])):
            check_schema_keywords(sub, f"{path}.{key}[{i}]")


def _resolve_ref(root: dict, ref: str) -> Any:
    if not ref.startswith("#/"):
        raise SchemaKeywordError(f"only local $ref is supported: {ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def schema_errors(inst: Any, sch: Any, root: Any = None, path: str = "$") -> list[str]:
    """Validation errors of `inst` against `sch` (JSON Schema 2020-12 subset); [] when valid."""
    root = sch if root is None else root
    if sch is True:
        return []
    if sch is False:
        return [f"{path}: not allowed"]
    unknown = {k for k in sch if not k.startswith("x-")} - SUPPORTED_KEYWORDS
    if unknown:
        raise SchemaKeywordError(f"schema keyword(s) {sorted(unknown)} at {path} are not implemented")
    out: list[str] = []
    if "$ref" in sch:
        out += schema_errors(inst, _resolve_ref(root, sch["$ref"]), root, path)
    if "type" in sch:
        types = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_is_type(inst, t) for t in types):
            return out + [f"{path}: type {type(inst).__name__} not in {types}"]
    if "const" in sch and not (inst == sch["const"] and type(inst) is type(sch["const"])):
        out.append(f"{path}: {inst!r} != const {sch['const']!r}")
    if "enum" in sch and not any(inst == e and type(inst) is type(e) for e in sch["enum"]):
        out.append(f"{path}: {inst!r} not in enum {sch['enum']}")
    if isinstance(inst, str):
        if "minLength" in sch and len(inst) < sch["minLength"]:
            out.append(f"{path}: shorter than {sch['minLength']}")
        if "pattern" in sch and not re.search(sch["pattern"], inst):
            out.append(f"{path}: {inst!r} does not match {sch['pattern']!r}")
    if _is_type(inst, "number"):
        if "minimum" in sch and inst < sch["minimum"]:
            out.append(f"{path}: {inst} < minimum {sch['minimum']}")
        if "maximum" in sch and inst > sch["maximum"]:
            out.append(f"{path}: {inst} > maximum {sch['maximum']}")
    if isinstance(inst, list):
        if "minItems" in sch and len(inst) < sch["minItems"]:
            out.append(f"{path}: fewer than {sch['minItems']} items")
        if "maxItems" in sch and len(inst) > sch["maxItems"]:
            out.append(f"{path}: more than {sch['maxItems']} items")
        if sch.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in inst}) != len(inst):
            out.append(f"{path}: items not unique")
        if "items" in sch:
            for i, x in enumerate(inst):
                out += schema_errors(x, sch["items"], root, f"{path}[{i}]")
    if isinstance(inst, dict):
        for k in sch.get("required", []):
            if k not in inst:
                out.append(f"{path}: missing required {k!r}")
        props = sch.get("properties", {})
        extra = sch.get("additionalProperties", True)
        for k, v in inst.items():
            if "propertyNames" in sch:
                out += schema_errors(k, sch["propertyNames"], root, f"{path}.<key {k!r}>")
            if k in props:
                out += schema_errors(v, props[k], root, f"{path}.{k}")
            elif extra is False:
                out.append(f"{path}: additional property {k!r}")
            elif isinstance(extra, dict):
                out += schema_errors(v, extra, root, f"{path}.{k}")
    if "oneOf" in sch:
        n = sum(not schema_errors(inst, s, root, path) for s in sch["oneOf"])
        if n != 1:
            out.append(f"{path}: matches {n} oneOf branches (need exactly 1)")
    if "anyOf" in sch and not any(not schema_errors(inst, s, root, path) for s in sch["anyOf"]):
        out.append(f"{path}: matches no anyOf branch")
    for s in sch.get("allOf", []):
        out += schema_errors(inst, s, root, path)
    if "not" in sch and not schema_errors(inst, sch["not"], root, path):
        out.append(f"{path}: must not match {sch['not']}")
    if "if" in sch and "then" in sch and not schema_errors(inst, sch["if"], root, path):
        out += schema_errors(inst, sch["then"], root, path)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Matrix loading and semantic checks
# ---------------------------------------------------------------------------------------------------------------------
def _read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_schema(path: str = SCHEMA_FILE) -> dict:
    schema = _read_json(path)
    check_schema_keywords(schema)
    return schema


def issuable_at(criterion: dict, matrix: dict) -> dict:
    """Earliest milestone at which each verdict can be issued for this criterion, from the bases the matrix accepts.
    PASS at C additionally needs integration (one design across every binding gate), which evaluate() checks."""
    bases = matrix["evidence_policy"]["bases"]

    def earliest(names):
        ms = [bases[b]["milestone"] for b in names]
        return min(ms, key=_RANK.__getitem__) if ms else None
    return {"FAIL": earliest(criterion["fail_sufficient_bases"]), "PASS": earliest(criterion["pass_sufficient_bases"])}


def _matrix_semantics(m: dict) -> None:
    """Consistency rules the schema cannot express. Raises ValueError."""
    bases = m["evidence_policy"]["bases"]
    flags = set(m["evidence_policy"]["flags"])
    dims = set(m["coverage_dimensions"])
    refs = [r["id"] for r in m["rfp"]["recorded_in"]]
    if len(set(refs)) != len(refs):
        raise ValueError("duplicate RFP record id")
    ods = {o["id"] for o in m["open_owner_decisions"]}
    if len(ods) != len(m["open_owner_decisions"]):
        raise ValueError("duplicate open owner decision id")
    for r in m["rfp_requirements_recorded_not_gated"]:
        if not set(r["recorded_in"]) <= set(refs):
            raise ValueError(f"unknown RFP record in {r['requirement']!r}")
    gids, cids = set(), set()
    for g in m["gates"]:
        if g["id"] in gids:
            raise ValueError(f"duplicate gate id {g['id']}")
        gids.add(g["id"])
        if "rfp_source" in g and not set(g["rfp_source"]["refs"]) <= set(refs):
            raise ValueError(f"{g['id']}: rfp_source cites an unknown RFP record")
        unknown_contracts = set(g["shared_contracts"]) - set(m["shared_contracts"])
        if unknown_contracts:
            raise ValueError(f"{g['id']}: unknown shared contract {sorted(unknown_contracts)}")
        if (g["status"] in BINDING_STATUSES) != g["binding"]:
            raise ValueError(f"{g['id']}: binding must be true exactly for status {BINDING_STATUSES}")
        if not any(c["counts_toward_gate"] for c in g["criteria"]):
            raise ValueError(f"{g['id']}: no criterion counts toward the gate verdict")
        prefix = g["id"].split("_")[0] + "."
        for c in g["criteria"]:
            cid = c["id"]
            if cid in cids:
                raise ValueError(f"duplicate criterion id {cid}")
            cids.add(cid)
            if not cid.startswith(prefix):
                raise ValueError(f"criterion {cid} must start with {prefix}")
            if c["counts_for_fail"] and not c["counts_toward_gate"]:
                raise ValueError(f"{cid}: counts_for_fail requires counts_toward_gate")
            if c["counts_toward_gate"] and not c["counts_for_fail"] and not re.search(
                    r"\bOD[0-9]+\b", c.get("fail_reading_dependence") or ""):
                raise ValueError(f"{cid}: a criterion that counts for PASS but not for FAIL must name the open owner "
                                 "reading(s) its FAIL depends on (fail_reading_dependence, 'ODn')")
            unknown_od = set(re.findall(r"\bOD[0-9]+\b", c.get("fail_reading_dependence") or "")) - ods
            if unknown_od:
                raise ValueError(f"{cid}: fail_reading_dependence names unknown owner decision(s) {sorted(unknown_od)}")
            for side in ("fail_sufficient_bases", "pass_sufficient_bases"):
                for b in c[side]:
                    if b not in bases:
                        raise ValueError(f"{cid}: unknown basis {b}")
                    if not bases[b]["verdict_bearing"]:
                        raise ValueError(f"{cid}: basis {b} is not verdict-bearing and cannot be listed as sufficient")
                    if g["hall_closure_dependence"] == "independent" and bases[b]["hall_closure"] != "none":
                        raise ValueError(f"{cid}: gate {g['id']} is Hall-closure independent; {b} would leak closure "
                                         "uncertainty into it")
            if c["comparator"] == "is_true":
                if c["threshold"] is not None:
                    raise ValueError(f"{cid}: an is_true criterion has no numeric threshold")
            elif c["threshold"] is None and c["threshold_status"] != "TBD":
                raise ValueError(f"{cid}: a missing threshold must be marked TBD")
            elif c["threshold"] is not None and c["threshold_status"] == "TBD":
                raise ValueError(f"{cid}: threshold marked TBD but a value is present")
            if c["threshold_status"] == "TBD" and c["counts_toward_gate"] and g["status"] == "RFP":
                raise ValueError(f"{cid}: an RFP-gate criterion with a TBD threshold cannot count toward the gate")
            env = c["envelope"]
            if not set(env) <= dims or not set(c["fail_must_cover"]) <= dims:
                raise ValueError(f"{cid}: unknown coverage dimension")
            if ("elements" in env) != (c.get("elements_semantics") is not None):
                raise ValueError(f"{cid}: elements_semantics must be given exactly when the envelope has elements")
            for dim, need in c["fail_must_cover"].items():
                if dim not in env:
                    raise ValueError(f"{cid}: fail_must_cover.{dim} is not an envelope dimension")
                if dim == "altitude_km" and need != env[dim]:
                    raise ValueError(f"{cid}: fail_must_cover altitude must equal the envelope altitude")
            if "altitude_km" in env and not env["altitude_km"][0] < env["altitude_km"][1]:
                raise ValueError(f"{cid}: altitude envelope must be increasing")
            for basis, sides in c.get("required_flags", {}).items():
                if basis not in bases:
                    raise ValueError(f"{cid}: required_flags for unknown basis {basis}")
                for f in sides.get("pass", []) + sides.get("fail", []):
                    if f not in flags:
                        raise ValueError(f"{cid}: unknown flag {f}")
            if c["issuable_at"] != issuable_at(c, m):
                raise ValueError(f"{cid}: issuable_at {c['issuable_at']} disagrees with its bases {issuable_at(c, m)}")


def validate_matrix(matrix: dict, schema: dict | None = None) -> dict:
    schema = load_schema() if schema is None else schema
    errs = schema_errors(matrix, schema)
    if errs:
        raise ValueError("hard-gate matrix does not validate against hard_gates_v1:\n  " + "\n  ".join(errs[:40]))
    _matrix_semantics(matrix)
    return matrix


def load_matrix(path: str = MATRIX_FILE, schema_path: str = SCHEMA_FILE) -> dict:
    return validate_matrix(_read_json(path), load_schema(schema_path))


def validate_result(result: dict, schema: dict | None = None) -> None:
    """Check an evaluate() / evaluate_all() result against the schema's $defs (contract for consumers)."""
    schema = load_schema() if schema is None else schema
    key = "evaluation_set" if result.get("schema") == RESULT_SET_SCHEMA else "evaluation_result"
    errs = schema_errors(result, schema["$defs"][key], schema)
    if errs:
        raise ValueError(f"{key} does not validate:\n  " + "\n  ".join(errs[:40]))


# ---------------------------------------------------------------------------------------------------------------------
# Evidence normalisation (malformed or rule-violating input raises; insufficient input is reported, never used)
# ---------------------------------------------------------------------------------------------------------------------
def _dict_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _dict_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _dict_keys(v)
    return keys


def _numbers_finite(value: dict) -> bool:
    return all(math.isfinite(v) for k, v in value.items() if k in ("value", "lo", "hi") and _is_type(v, "number"))


def _normalize_evidence(evidence: Any, matrix: dict, schema: dict, screening: frozenset) -> list[dict]:
    if evidence is None:
        raise TypeError("evidence is required: pass [] (no evidence) or a hard_gate_evidence_v1 bundle")
    if isinstance(evidence, dict):
        if evidence.get("schema") != EVIDENCE_SCHEMA:
            raise ValueError(f"an evidence bundle must have schema {EVIDENCE_SCHEMA!r}")
        if evidence.get("matrix_version") != matrix["matrix_version"]:
            raise ValueError(f"evidence bundle is for matrix {evidence.get('matrix_version')!r}, "
                             f"matrix is {matrix['matrix_version']!r}")
        items = evidence.get("items")
        if not isinstance(items, list):
            raise ValueError("evidence bundle 'items' must be a list")
        head = {k: v for k, v in evidence.items() if k != "items"}
        errs = schema_errors({**head, "items": []}, schema["$defs"]["evidence_bundle"], schema)
        if errs:
            raise ValueError("evidence bundle does not validate:\n  " + "\n  ".join(errs))
    elif isinstance(evidence, (list, tuple)):
        items = list(evidence)
    else:
        raise TypeError("evidence must be a list of evidence items or a hard_gate_evidence_v1 bundle")
    nuisance = set(matrix["calibration_nuisance_forbidden"]["keys"])
    bases = matrix["evidence_policy"]["bases"]
    gates = {g["id"]: g for g in matrix["gates"]}
    seen: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            raise TypeError("every evidence item must be an object")
        leaked = _dict_keys(it) & nuisance
        if leaked:
            raise ValueError(f"evidence {it.get('id')!r}: P5 calibration nuisance {sorted(leaked)} appears as a "
                             "variable; calibration nuisance is marginalized in admission and is never a design "
                             "variable, map axis or trade dimension")
        errs = schema_errors(it, schema["$defs"]["evidence_item"], schema)
        if errs:
            raise ValueError(f"evidence {it.get('id')!r} does not validate:\n  " + "\n  ".join(errs))
        if it["id"] in seen:
            raise ValueError(f"duplicate evidence id {it['id']!r}")
        seen.add(it["id"])
        g = gates.get(it["gate"])
        if g is None:
            raise ValueError(f"evidence {it['id']!r}: unknown gate {it['gate']!r}")
        crit = next((c for c in g["criteria"] if c["id"] == it["criterion"]), None)
        if crit is None:
            raise ValueError(f"evidence {it['id']!r}: criterion {it['criterion']!r} is not in gate {g['id']}")
        if it["metric"] != crit["metric"] or it["unit"] != crit["unit"]:
            raise ValueError(f"evidence {it['id']!r}: metric/unit {it['metric']}/{it['unit']} != "
                             f"{crit['metric']}/{crit['unit']} of {crit['id']}")
        want = bases[it["basis"]]["hall_closure"]
        if it["hall_closure"]["status"] != want:
            raise ValueError(f"evidence {it['id']!r}: basis {it['basis']} requires hall_closure.status {want!r}, "
                             f"got {it['hall_closure']['status']!r}")
        if g["hall_closure_dependence"] == "independent" and it["hall_closure"]["status"] != "none":
            raise ValueError(f"evidence {it['id']!r}: gate {g['id']} is independent of the Hall transport closure; "
                             "Hall-closure results must not leak into it")
        if it["hall_closure"]["status"] == "admitted" and it["hall_closure"]["member_id"] in screening:
            raise ValueError(f"evidence {it['id']!r}: {it['hall_closure']['member_id']!r} is a SCREENING candidate "
                             "labelled as an admitted closure; screening candidates are never performance sources")
        upstream = set(matrix["hall_closure_scope"]["closure_independent_elements"])
        leaked_el = set(it["conditions"].get("elements", [])) & upstream
        if (it["hall_closure"]["status"] != "none" and crit.get("elements_semantics") == "per_element"
                and leaked_el):
            raise ValueError(f"evidence {it['id']!r}: Hall-closure results must not leak into the closure-independent "
                             f"upstream element(s) {sorted(leaked_el)} (matrix hall_closure_scope)")
        if not _numbers_finite(it["value"]):
            raise ValueError(f"evidence {it['id']!r}: non-finite value")
        if it["value"]["kind"] == "interval" and it["value"]["lo"] > it["value"]["hi"]:
            raise ValueError(f"evidence {it['id']!r}: interval lo > hi")
        alt = it["conditions"].get("altitude_km")
        if alt is not None and alt[0] > alt[1]:
            raise ValueError(f"evidence {it['id']!r}: altitude_km must be [low, high]")
    return items


REPO_ENSEMBLE_SOURCE = ("abep_sim.hall_ensemble.load_ensemble() "
                        "(hallthruster_bridge/ensemble/transport_ensemble_v0.json)")


def _ensemble_context(ensemble: dict | None) -> tuple:
    """(ensemble, screening ids, source). The repository ensemble's screening candidates are ALWAYS refused, also when
    a caller injects its own ensemble (synthetic tests), so no ensemble can turn a screening candidate into a member."""
    from abep_sim import hall_ensemble as he          # in-repository module, not another lane's contract
    repo = he.load_ensemble()
    if ensemble is None:
        return repo, frozenset(he.screening_ids(repo)), REPO_ENSEMBLE_SOURCE
    if not isinstance(ensemble, dict) or not isinstance(ensemble.get("members"), list):
        raise TypeError("ensemble must be a transport-ensemble dict with a 'members' list (as load_ensemble returns)")
    screening = frozenset(he.screening_ids(ensemble)) | frozenset(he.screening_ids(repo))
    overlap = {m["ensemble_member_id"] for m in ensemble["members"]} & screening
    if overlap:
        raise ValueError(f"injected ensemble lists screening candidate(s) {sorted(overlap)} as members")
    return ensemble, screening, "caller-supplied ensemble (checked against the repository screening candidates)"


def _normalize_admitted(admitted_members: Any, ensemble: dict, screening: frozenset) -> frozenset:
    """Admitted ids must be members of the ensemble (abep_sim.hall_ensemble.require_admitted); a screening candidate or
    an unknown id raises. Never a silent drop."""
    if isinstance(admitted_members, (str, bytes)) or admitted_members is None:
        raise TypeError("admitted_members must be an iterable of ensemble_member_id strings (use () for none)")
    out = frozenset(admitted_members)
    if not all(isinstance(m, str) and m for m in out):
        raise TypeError("admitted_members must contain non-empty strings")
    from abep_sim.hall_ensemble import require_admitted
    for mid in sorted(out):
        if mid in screening:
            raise ValueError(f"{mid} is a SCREENING candidate: screening candidates are never admitted members and "
                             "never performance sources")
        require_admitted(mid, ensemble)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Criterion / gate evaluation
# ---------------------------------------------------------------------------------------------------------------------
def _resolve(values: Any, arch: str) -> Any:
    """Architecture-specific envelope lists are {'common': [...], '<arch>': [...]}; everything else is literal."""
    if isinstance(values, dict):
        return list(values.get("common", [])) + list(values.get(arch, []))
    return values


def _side(value: dict, comparator: str, threshold: Any, equality_open: bool = False) -> str | None:
    """'pass' / 'fail' when the bound decides the criterion, else None. equality_open (criterion
    threshold_equality_open): the owner has not decided whether the limit is strict or inclusive, so a bound AT the
    threshold decides neither side (PASS needs the strict form, FAIL the violation of the inclusive form)."""
    kind = value["kind"]
    if comparator == "is_true":
        return ("pass" if value["value"] else "fail") if kind == "boolean" else None
    if threshold is None or kind in ("boolean", "point_estimate"):
        return None
    lo = value["value"] if kind == "lower_bound" else value["lo"] if kind == "interval" else None
    hi = value["value"] if kind == "upper_bound" else value["hi"] if kind == "interval" else None
    t = threshold
    if equality_open:
        comparator = {">=": ">", "<=": "<"}.get(comparator, comparator)     # PASS strict
        if comparator == ">":
            return "pass" if lo is not None and lo > t else "fail" if hi is not None and hi < t else None
        if comparator == "<":
            return "pass" if hi is not None and hi < t else "fail" if lo is not None and lo > t else None
    if comparator == ">=":
        if lo is not None and lo >= t:
            return "pass"
        if hi is not None and hi < t:
            return "fail"
    elif comparator == ">":
        if lo is not None and lo > t:
            return "pass"
        if hi is not None and hi <= t:
            return "fail"
    elif comparator == "<":
        if hi is not None and hi < t:
            return "pass"
        if lo is not None and lo >= t:
            return "fail"
    elif comparator == "<=":
        if hi is not None and hi <= t:
            return "pass"
        if lo is not None and lo > t:
            return "fail"
    return None


def _script_problem(script: str | None, repo_root: str) -> str | None:
    """Why a derivation_script does not qualify (None when it is a file inside the repository)."""
    if not script:
        return "needs derivation_script (a committed deterministic script)"
    if os.path.isabs(script) or ".." in re.split(r"[\\/]", script):
        return f"derivation_script {script!r} must be a repository-relative path"
    if not os.path.isfile(os.path.join(repo_root, script)):
        return f"derivation_script {script!r} does not exist in the repository"
    return None


def _assess(it: dict, crit: dict, env: dict, fneed: dict, admitted: frozenset, matrix: dict,
            repo_root: str) -> tuple:
    """(side, reasons): the item is verdict-bearing for `side` only when reasons is empty."""
    pol = matrix["evidence_policy"]["bases"][it["basis"]]
    reasons: list[str] = []
    side = _side(it["value"], crit["comparator"], crit["threshold"], crit.get("threshold_equality_open", False))
    if not pol["verdict_bearing"]:
        reasons.append(f"basis {it['basis']!r} is never verdict-bearing: {pol['reason']}")
    else:
        if it["quantity_type"] not in pol["quantity_types"]:
            reasons.append(f"quantity_type {it['quantity_type']!r} is inconsistent with basis {it['basis']!r} "
                           f"(allowed: {pol['quantity_types']})")
        if it["evidence_level"] not in pol["evidence_levels"]:
            reasons.append(f"evidence_level {it['evidence_level']} is inconsistent with basis {it['basis']!r} "
                           f"(allowed: {pol['evidence_levels']})")
        if it["value"]["kind"] not in pol["value_kinds"]:
            reasons.append(f"value kind {it['value']['kind']!r} is not accepted for basis {it['basis']!r}")
        if pol.get("requires_derivation_script"):
            problem = _script_problem(it.get("derivation_script"), repo_root)
            if problem:
                reasons.append(f"basis {it['basis']!r}: {problem}")
        if pol.get("requires_validated_for_this_use") and it.get("validated_for_this_use") is not True:
            reasons.append("model not declared validated for this use (validated_for_this_use)")
        if it["basis"] == "model_admitted_closure":
            hc = it["hall_closure"]
            if hc["member_id"] not in admitted:
                reasons.append(f"Hall closure {hc['member_id']!r} is not in the admitted transport-ensemble set "
                               f"supplied ({sorted(admitted) if admitted else 'empty: credible set = ∅'}); "
                               "screening candidates and unadmitted closures are never performance sources")
            if hc.get("hallthruster_commit") != matrix["hall_pin"]["hallthruster_commit"]:
                reasons.append("hallthruster_commit does not match the pinned HallThruster.jl commit")
    if crit["comparator"] != "is_true" and crit["threshold"] is None:
        reasons.append(f"threshold TBD for {crit['id']}: {crit['threshold_source']}")
    elif side is None:
        reasons.append("inconclusive: the stated bound does not decide the criterion (point estimate, wrong-side "
                       "bound, an interval straddling the threshold, or a bound AT a threshold whose strict/inclusive "
                       "form is an open owner decision)")
    else:
        allowed = crit["fail_sufficient_bases"] if side == "fail" else crit["pass_sufficient_bases"]
        if pol["verdict_bearing"] and it["basis"] not in allowed:
            reasons.append(f"basis {it['basis']!r} is not sufficient for {side.upper()} on {crit['id']} "
                           f"(sufficient: {allowed})")
        for f in crit.get("required_flags", {}).get(it["basis"], {}).get(side, []):
            if it.get("flags", {}).get(f) is not True:
                reasons.append(f"flag {f!r} must be true for {it['basis']} {side.upper()} evidence on {crit['id']}")
    cond = it["conditions"]
    if crit.get("requires_power_boundary") and cond.get("power_boundary") != crit["requires_power_boundary"]:
        reasons.append(f"not stated at the common bus-power boundary {crit['requires_power_boundary']!r}")
    if it["basis"].startswith("measurement_") and "altitude_km" in env and not cond.get("feed_equivalence"):
        reasons.append("a ground measurement must state how its feed state maps to the envelope point "
                       "(conditions.feed_equivalence, upstream ICD thruster-inlet interface)")
    for dim, need_env in env.items():
        need = fneed.get(dim, need_env) if side == "fail" else need_env
        have = cond.get(dim)
        if have is None:
            reasons.append(f"conditions.{dim} not stated (envelope: {need})")
        elif dim == "altitude_km":
            if have[1] < need[0] or have[0] > need[1]:
                reasons.append(f"altitude {have} km lies outside the envelope {need} km")
        elif dim == "elements" and crit["elements_semantics"] == "sum":
            if side == "fail" and not set(have) <= set(need):
                reasons.append(f"a failing lower bound on a sum may include only in-scope elements; "
                               f"out of scope: {sorted(set(have) - set(need))}")
            if side == "pass" and not set(need) <= set(have):
                reasons.append(f"a passing bound on a sum must include every required element; "
                               f"missing: {sorted(set(need) - set(have))}")
        elif not set(have) & set(need):
            reasons.append(f"conditions.{dim} {have} do not intersect {need}")
    return side, reasons


def _interval_gaps(intervals: list, need: list) -> list:
    lo, hi = need
    cur, gaps = lo, []
    for a, b in sorted(intervals):
        if b < cur:
            continue
        if a > cur:
            gaps.append([cur, min(a, hi)])
        cur = max(cur, b)
        if cur >= hi:
            break
    if cur < hi:
        gaps.append([cur, hi])
    return gaps


def _covers(items: list, need: dict) -> list[str]:
    """Missing coverage (empty list = covered). Discrete dims are covered value by value; for each combination the
    union of the selected items' altitude ranges must cover the needed altitude interval."""
    if not items:
        return ["no verdict-bearing evidence"]
    discrete = sorted(d for d in need if d != "altitude_km")
    missing = []
    for combo in itertools.product(*(need[d] for d in discrete)):
        sel = [it for it in items if all(v in it["conditions"].get(d, []) for d, v in zip(discrete, combo))]
        label = ", ".join(f"{d}={v}" for d, v in zip(discrete, combo)) or "envelope"
        if "altitude_km" in need:
            gaps = _interval_gaps([it["conditions"]["altitude_km"] for it in sel if "altitude_km" in it["conditions"]],
                                  need["altitude_km"])
            if gaps:
                missing.append(f"{label}: altitude gap(s) {gaps} km")
        elif not sel:
            missing.append(f"{label}: not covered")
    return missing


def _covers_members(items: list, need: dict, admitted: frozenset) -> list[str]:
    """Admitted-closure evidence counts only as an envelope over EVERY admitted member (unweighted scenario set)."""
    if any(it["basis"] == "model_admitted_closure" for it in items):
        missing = []
        for m in sorted(admitted):
            sub = [it for it in items
                   if it["basis"] != "model_admitted_closure" or it["hall_closure"]["member_id"] == m]
            missing += [f"member {m}: {x}" for x in _covers(sub, need)]
        return missing
    return _covers(items, need)


def _establish(items: list, need: dict, admitted: frozenset, matrix: dict) -> tuple:
    """(ok, earliest milestone, evidence ids used, missing): tries evidence admissible at A first, then B."""
    if not items:
        return False, None, [], ["no verdict-bearing evidence"]
    bases = matrix["evidence_policy"]["bases"]
    missing: list[str] = []
    for ms in ("A", "B"):
        sub = [it for it in items if _RANK[bases[it["basis"]]["milestone"]] <= _RANK[ms]]
        if not sub:
            continue
        missing = _covers_members(sub, need, admitted)
        if not missing:
            return True, ms, sorted(it["id"] for it in sub), []
    return False, None, [], missing


def _eval_criterion(crit: dict, arch: str, items: list, admitted: frozenset, matrix: dict, nvb: list,
                    repo_root: str) -> dict:
    env = {d: _resolve(v, arch) for d, v in crit["envelope"].items()}
    fneed = {d: _resolve(v, arch) for d, v in crit["fail_must_cover"].items()}
    pneed = {d: v for d, v in env.items() if not (d == "elements" and crit["elements_semantics"] == "sum")}
    fails, design_fail_items, passes = [], {}, {}
    for it in items:
        side, reasons = _assess(it, crit, env, fneed, admitted, matrix, repo_root)
        if reasons:
            nvb.append({"id": it["id"], "criterion": crit["id"], "side": side, "reasons": reasons})
        elif side == "fail":
            (fails if it["scope"] == "architecture" else design_fail_items.setdefault(it["design_id"], [])).append(it)
        else:
            passes.setdefault(ARCH_KEY if it["scope"] == "architecture" else it["design_id"], []).append(it)
    res: dict[str, Any] = {"counts_toward_gate": crit["counts_toward_gate"], "counts_for_fail": crit["counts_for_fail"],
                           "status": crit["status"],
                           "metric": crit["metric"], "comparator": crit["comparator"], "threshold": crit["threshold"],
                           "unit": crit["unit"], "verdict": "UNDETERMINED", "milestone": None, "evidence_used": [],
                           "pass_designs": {}, "design_failures": {}, "conflict": False, "reasons": [],
                           "missing_for_fail": [], "missing_for_pass": []}
    f_ok, f_ms, f_used, f_missing = _establish(fails, fneed, admitted, matrix)
    for d, its in sorted(design_fail_items.items()):
        ok, ms, used, _ = _establish(its + fails, fneed, admitted, matrix)
        if ok:
            res["design_failures"][d] = {"milestone": ms, "evidence": used}
    arch_pass = passes.get(ARCH_KEY, [])
    pass_missing, established = [], {}
    for key in sorted(passes):
        ok, ms, used, missing = _establish(passes[key] + ([] if key == ARCH_KEY else arch_pass), pneed, admitted,
                                           matrix)
        if ok:
            established[key] = {"milestone": ms, "evidence": used}
        else:
            pass_missing += [f"{key}: {x}" for x in missing]
    res["pass_designs"] = dict(established)
    for d in list(res["pass_designs"]):
        if d in res["design_failures"]:
            res["conflict"] = True
            res["reasons"].append(f"CONFLICT on design {d!r}: sufficient evidence both passes and fails it "
                                  f"({res['pass_designs'][d]['evidence']} vs {res['design_failures'][d]['evidence']})")
            del res["pass_designs"][d]
    if ARCH_KEY in res["pass_designs"] and res["design_failures"]:
        res["conflict"] = True
        res["reasons"].append(f"CONFLICT: architecture-scope PASS evidence {res['pass_designs'][ARCH_KEY]['evidence']} "
                              f"contradicts the failure of design(s) {sorted(res['design_failures'])}")
        del res["pass_designs"][ARCH_KEY]
    arch_fail_conflict = f_ok and bool(established)
    if arch_fail_conflict:
        res["conflict"] = True
        res["reasons"].append(f"CONFLICT: architecture-scope FAIL evidence {f_used} contradicts PASS evidence for "
                              f"{sorted(established)}; owner review required, nothing is eliminated")
    res["missing_for_fail"] = [] if f_ok else f_missing
    res["missing_for_pass"] = [] if res["pass_designs"] else (pass_missing or ["no verdict-bearing PASS evidence"])
    if crit["comparator"] != "is_true" and crit["threshold"] is None:
        res["reasons"].append(f"threshold TBD: {crit['threshold_source']}")
    elif arch_fail_conflict:
        pass
    elif f_ok:
        res.update(verdict="FAIL", milestone=f_ms, evidence_used=f_used)
    elif res["pass_designs"]:
        ms = min((v["milestone"] for v in res["pass_designs"].values()), key=_RANK.__getitem__)
        used = sorted({e for v in res["pass_designs"].values() for e in v["evidence"]})
        res.update(verdict="PASS", milestone=ms, evidence_used=used)
    return res


def _joint(design_maps: list) -> dict:
    """Designs that pass every map (architecture-scope passes hold for every design)."""
    keys = sorted(set().union(*design_maps)) if design_maps else []
    out = {}
    for k in keys:
        entries = []
        for dm in design_maps:
            e = dm.get(k, dm.get(ARCH_KEY))
            if e is None:
                break
            entries.append(e)
        else:
            out[k] = {"milestone": max((e["milestone"] for e in entries), key=_RANK.__getitem__),
                      "evidence": sorted({x for e in entries for x in e["evidence"]})}
    return out


def _eval_gate(gate: dict, arch: str, items: list, admitted: frozenset, matrix: dict, nvb: list,
               repo_root: str) -> dict:
    crits = {c["id"]: _eval_criterion(c, arch, [it for it in items if it["criterion"] == c["id"]], admitted, matrix,
                                      nvb, repo_root) for c in gate["criteria"]}
    counted = [crits[c["id"]] for c in gate["criteria"] if c["counts_toward_gate"]]
    res: dict[str, Any] = {"title": gate["title"], "status": gate["status"], "binding": gate["binding"],
                           "verdict": "UNDETERMINED", "milestone": None, "evidence_used": [], "pass_designs": {},
                           "conflict": any(c["conflict"] for c in counted), "reasons": [], "criteria": crits}
    failing = {cid: c for cid, c in crits.items() if c["counts_for_fail"] and c["verdict"] == "FAIL"}
    reading_fails = sorted(cid for cid, c in crits.items()
                           if c["counts_toward_gate"] and not c["counts_for_fail"] and c["verdict"] == "FAIL")
    if reading_fails:
        res["reasons"].append(f"{reading_fails} FAIL only under an open owner reading (fail_reading_dependence): the "
                              "gate cannot PASS, and this never makes the gate FAIL")
    if failing:
        res.update(verdict="FAIL",
                   milestone=min((c["milestone"] for c in failing.values()), key=_RANK.__getitem__),
                   evidence_used=sorted({e for c in failing.values() for e in c["evidence_used"]}))
        res["reasons"].append(f"FAIL on {sorted(failing)}")
    elif all(c["verdict"] == "PASS" for c in counted):
        joint = _joint([c["pass_designs"] for c in counted])
        if joint:
            res.update(verdict="PASS", pass_designs=joint,
                       milestone=min((v["milestone"] for v in joint.values()), key=_RANK.__getitem__),
                       evidence_used=sorted({e for v in joint.values() for e in v["evidence"]}))
        else:
            res["reasons"].append("every counted criterion passes, but on different point designs; no single design "
                                  "passes the whole gate")
    else:
        und = sorted(cid for cid, c in crits.items() if c["counts_toward_gate"] and c["verdict"] != "PASS")
        res["reasons"].append(f"not established: {und}")
    return res


def _requirement_text(c: dict) -> str:
    if c["comparator"] == "is_true":
        return f"{c['metric']} is true"
    thr = "TBD" if c["threshold"] is None else f"{c['threshold']:g}"
    form = " (strict vs inclusive open: a bound at the threshold decides nothing)" \
        if c.get("threshold_equality_open") else ""
    return f"{c['metric']} {c['comparator']} {thr} {c['unit']}{form}"


def _condition(gate: dict, crit: dict, cres: dict, arch: str, admitted: frozenset, matrix: dict) -> dict:
    bases = matrix["evidence_policy"]["bases"]
    by_ms = {ms: [b for b in crit["pass_sufficient_bases"] if _RANK[bases[b]["milestone"]] <= _RANK[ms]]
             for ms in ("A", "B")}
    blockers = []
    if crit["comparator"] != "is_true" and crit["threshold"] is None:
        blockers.append(f"threshold TBD: {crit['threshold_source']}")
    if "model_admitted_closure" in crit["pass_sufficient_bases"] and not admitted:
        blockers.append("the admitted-closure route is blocked: the credible Hall-transport set is empty (gate 3 "
                        "FAIL); until a closure is admitted only " + ", ".join(by_ms["A"] or ["(none)"])
                        + " can discharge this condition")
    if cres["conflict"]:
        blockers.append("evidence CONFLICT on this criterion must be resolved by the owner")
    if not crit["counts_for_fail"]:
        blockers.append(f"binds only under an open owner reading: {crit['fail_reading_dependence']}")
    return {"gate": gate["id"], "criterion": crit["id"], "requirement": _requirement_text(crit),
            "over": {d: _resolve(v, arch) for d, v in crit["envelope"].items()},
            "current_verdict": cres["verdict"], "can_eliminate": crit["counts_for_fail"], "discharged_by": by_ms,
            "blockers": blockers}


def evaluate(architecture: str, evidence: Any, *, admitted_members: Iterable[str] = (),
             matrix: dict | None = None, ensemble: dict | None = None, repo_root: str = ROOT) -> dict:
    """Evaluate one architecture against the hard-gate matrix.

    architecture     : 'hall_only' | 'rf_hall' | 'ecr_hall'
    evidence         : list of evidence items, or a hard_gate_evidence_v1 bundle (schema $defs.evidence_item); [] is
                       allowed and gives UNDETERMINED everywhere. Malformed or rule-violating items raise ValueError.
    admitted_members : ensemble_member_ids of ADMITTED Hall transport closures (abep_sim.hall_ensemble.member_ids();
                       empty today). Only these make model_admitted_closure evidence verdict-bearing. Each id is
                       checked with abep_sim.hall_ensemble.require_admitted: a screening candidate or an id that is not
                       an admitted member raises ValueError.
    matrix           : a matrix dict (validated here); default the committed hard_gate_matrix_v1.json.
    ensemble         : transport-ensemble dict the admitted ids are checked against; default the repository ensemble
                       (hallthruster_bridge/ensemble/transport_ensemble_v0.json). Synthetic tests inject one; the
                       repository's screening candidates are refused in every case.
    repo_root        : directory derivation_script paths are resolved against (default: this repository).
    """
    if architecture not in ARCHITECTURES:
        raise ValueError(f"architecture must be one of {ARCHITECTURES}, got {architecture!r}")
    schema = load_schema()
    m = load_matrix() if matrix is None else validate_matrix(copy.deepcopy(matrix), schema)
    ens, screening, ens_source = _ensemble_context(ensemble)
    items = copy.deepcopy(_normalize_evidence(evidence, m, schema, screening))
    admitted = _normalize_admitted(admitted_members, ens, screening)
    rel = [it for it in items if architecture in it["architectures"]]
    nvb: list[dict] = []
    gates = {g["id"]: _eval_gate(g, architecture, [it for it in rel if it["gate"] == g["id"]], admitted, m, nvb,
                                 repo_root) for g in m["gates"]}
    binding = [g["id"] for g in m["gates"] if g["binding"]]
    proposed = [g["id"] for g in m["gates"] if g["status"] == "PROPOSED"]

    def failure_record(gid):
        g = gates[gid]
        crits = sorted(c for c, r in g["criteria"].items() if r["counts_for_fail"] and r["verdict"] == "FAIL")
        return {"gate": gid, "criteria": crits, "evidence": g["evidence_used"], "milestone": g["milestone"]}

    elimination = [failure_record(g) for g in binding if gates[g]["verdict"] == "FAIL"]
    proposed_failures = [{**failure_record(g), "note": "would eliminate only if the owner adopts this PROPOSED gate"}
                         for g in proposed if gates[g]["verdict"] == "FAIL"]
    conflicts = [{"gate": gid, "criterion": cid, "detail": r["reasons"]}
                 for gid, g in gates.items() for cid, r in g["criteria"].items() if r["conflict"]]
    eliminated = bool(elimination)
    binding_conflict = any(gates[g]["conflict"] for g in binding)

    # ---- milestone A: conditional selection
    conditions, open_items = [], []
    for g in m["gates"]:
        for c in g["criteria"]:
            cres = gates[g["id"]]["criteria"][c["id"]]
            if g["binding"] and c["counts_toward_gate"] and cres["verdict"] != "PASS":
                conditions.append(_condition(g, c, cres, architecture, admitted, m))
            if g["binding"] and (not c["counts_for_fail"] or c["status"] in _OPEN_CRITERION_STATUSES):
                open_items.append({"gate": g["id"], "criterion": c["id"], "status": c["status"],
                                   "counts_toward_gate": c["counts_toward_gate"],
                                   "counts_for_fail": c["counts_for_fail"],
                                   "requirement": _requirement_text(c), "current_verdict": cres["verdict"],
                                   "interpretation": c["interpretation"],
                                   "fail_reading_dependence": c.get("fail_reading_dependence")})
    available = not eliminated and not binding_conflict
    if eliminated:
        statement = (f"{architecture} is ELIMINATED by binding gate(s) "
                     f"{[e['gate'] for e in elimination]} on sufficient evidence; no conditional selection.")
    elif binding_conflict:
        statement = (f"{architecture}: sufficient evidence conflicts on a binding gate; the owner must resolve the "
                     "conflict before any conditional selection. Nothing is eliminated.")
    elif conditions:
        statement = (f"{architecture} is not eliminated by any binding hard gate on the registered evidence. A "
                     f"conditional (milestone A) selection of {architecture} would hold only provided each of the "
                     f"{len(conditions)} condition(s) listed is demonstrated with the stated evidence. This is not a "
                     f"selection, and no architecture is ranked (matrix status: {m['status']}).")
    else:
        statement = (f"{architecture} passes every binding hard gate on the registered evidence; see B/C for what a "
                     "physics-backed selection or a PDR freeze still needs. This is not a selection.")
    not_pass = [f"{g}: {gates[g]['verdict']}" for g in binding if gates[g]["verdict"] != "PASS"]
    all_pass = not not_pass and not binding_conflict
    conflicted = [g for g in binding if gates[g]["conflict"]]
    b_missing = list(not_pass) + ([f"evidence conflict on binding gate(s) {conflicted}"] if conflicted else [])
    if m["status"] != "OWNER_APPROVED":
        b_missing.append(f"matrix {m['matrix_version']} is {m['status']}: thresholds, interpretations and the "
                         "evidence policy need owner approval")
    integrated = _joint([gates[g]["pass_designs"] for g in binding]) if all_pass else {}
    c_missing = list(b_missing)
    if all_pass and not integrated:
        c_missing.append("no single integrated design passes every binding gate")
    c_missing += [f"owner decision pending on PROPOSED gate {g} (adopt as binding, or waive)" for g in proposed]
    c_missing += [f"open owner item {o['criterion']} ({o['status']})" for o in open_items
                  if o["status"] in _OPEN_CRITERION_STATUSES]
    return {
        "schema": RESULT_SCHEMA,
        "matrix_schema": m["schema"],
        "matrix_version": m["matrix_version"],
        "matrix_status": m["status"],
        "architecture": architecture,
        "admitted_members": sorted(admitted),
        "admitted_members_checked_against": ens_source,
        "gates": gates,
        "binding_gates": binding,
        "proposed_gates": proposed,
        "eliminated": eliminated,
        "elimination_basis": elimination,
        "proposed_gate_failures": proposed_failures,
        "conflicts": conflicts,
        "evidence_considered": sorted(it["id"] for it in rel),
        "evidence_not_verdict_bearing": sorted(nvb, key=lambda x: (x["id"], x["criterion"])),
        "milestones": {
            "A": {"conditional_selection_available": available, "statement": statement, "conditions": conditions,
                  "open_owner_items": open_items, "proposed_gates_pending": proposed},
            "B": {"all_binding_gates_pass": all_pass, "ready": not b_missing, "missing": b_missing},
            "C": {"integrated_designs": sorted(integrated), "ready": not c_missing, "missing": c_missing},
        },
        "note": "Hard gates only: PASS / FAIL / UNDETERMINED per gate. No ranking, no scoring, no winner.",
    }


def evaluate_all(evidence: Any, *, admitted_members: Iterable[str] = (), matrix: dict | None = None,
                 ensemble: dict | None = None, repo_root: str = ROOT) -> dict:
    """evaluate() for every architecture, in fixed id order. Lists which are eliminated; ranks nothing."""
    admitted_members = list(admitted_members) if not isinstance(admitted_members, (str, bytes)) else admitted_members
    res = {a: evaluate(a, evidence, admitted_members=admitted_members, matrix=matrix, ensemble=ensemble,
                       repo_root=repo_root) for a in ARCHITECTURES}
    first = res[ARCHITECTURES[0]]
    return {"schema": RESULT_SET_SCHEMA, "matrix_version": first["matrix_version"],
            "matrix_status": first["matrix_status"], "admitted_members": first["admitted_members"],
            "architectures": res,
            "eliminated": [a for a in ARCHITECTURES if res[a]["eliminated"]],
            "not_eliminated": [a for a in ARCHITECTURES if not res[a]["eliminated"]],
            "note": "Eliminations follow only from binding hard gates on sufficient evidence. Architectures are "
                    "listed in fixed id order; no ranking, no scoring, no winner."}


# ---------------------------------------------------------------------------------------------------------------------
# Lazy resolution of other lanes' shared contracts (never imported at module import time)
# ---------------------------------------------------------------------------------------------------------------------
def resolve_contract(key: str, matrix: dict | None = None, root: str = ROOT) -> str:
    """Absolute path of a shared contract named in the matrix (e.g. 'bus_power_boundary'); raises FileNotFoundError
    with a clear message if the other lane's file is not present in this checkout."""
    m = load_matrix() if matrix is None else matrix
    contracts = m["shared_contracts"]
    if key not in contracts:
        raise KeyError(f"unknown shared contract {key!r}; known: {sorted(contracts)}")
    path = os.path.join(root, contracts[key]["path"])
    if not os.path.exists(path):
        raise FileNotFoundError(f"shared contract {key!r} ({contracts[key]['path']}) is not present in this checkout; "
                                f"it is built by another lane ({contracts[key]['role']}). The hard-gate matrix only "
                                "references it by path.")
    return path


def check_boundary_contract(matrix: dict | None = None) -> Any:
    """Import abep_sim.arch_boundary lazily and check its BOUNDARY_VERSION against the matrix. Raises ImportError with
    a clear message if that lane's module is absent. Returns the module."""
    m = load_matrix() if matrix is None else matrix
    want = m["power_boundary"]["version"]
    try:
        import importlib
        mod = importlib.import_module("abep_sim.arch_boundary")
    except ImportError as e:
        raise ImportError(f"abep_sim/arch_boundary.py ({want}, bus-power boundary lane) is not present in this "
                          "checkout; G2 evidence must still declare conditions.power_boundary = "
                          f"{want!r}") from e
    if getattr(mod, "BOUNDARY_VERSION", None) != want:
        raise ValueError(f"abep_sim.arch_boundary.BOUNDARY_VERSION = {getattr(mod, 'BOUNDARY_VERSION', None)!r}, "
                         f"matrix expects {want!r}")
    return mod


# ---------------------------------------------------------------------------------------------------------------------
# Deterministic renderers (HARD_GATES.md table, status file)
# ---------------------------------------------------------------------------------------------------------------------
def render_table(matrix: dict | None = None) -> str:
    """Markdown gate table generated from the matrix (HARD_GATES.md embeds it between the GENERATED markers)."""
    m = load_matrix() if matrix is None else matrix
    bases = m["evidence_policy"]["bases"]

    def fmt(names):
        by = {}
        for b in names:
            by.setdefault(bases[b]["milestone"], []).append(bases[b]["short"])
        return "; ".join(f"{ms}: {', '.join(v)}" for ms, v in sorted(by.items()))

    def counts(c):
        if not c["counts_toward_gate"]:
            return "no"
        if c["counts_for_fail"]:
            return "PASS and FAIL"
        return "PASS only (" + ", ".join(sorted(set(re.findall(r"\bOD[0-9]+\b", c["fail_reading_dependence"])))) + ")"

    rows = ["| gate | gate status | criterion | counts for | requirement | threshold status | FAIL may rest on | "
            "PASS may rest on | earliest FAIL / PASS |",
            "|---|---|---|---|---|---|---|---|---|"]
    for g in m["gates"]:
        for c in g["criteria"]:
            ia = c["issuable_at"]
            rows.append(f"| {g['id']} | {g['status']}{'' if g['binding'] else ' (non-binding)'} | {c['id']} | "
                        f"{counts(c)} | {_requirement_text(c)} | "
                        f"{c['threshold_status']} | {fmt(c['fail_sufficient_bases'])} | "
                        f"{fmt(c['pass_sufficient_bases'])} | {ia['FAIL']} / {ia['PASS']} (C: + integration) |")
    return "\n".join(rows) + "\n"


def admitted_member_ids() -> list[str]:
    """ADMITTED Hall transport-ensemble members from the repository ensemble (abep_sim.hall_ensemble; empty today)."""
    from abep_sim.hall_ensemble import member_ids
    return sorted(member_ids())


def build_status(register_path: str = REGISTER_FILE, matrix_path: str = MATRIX_FILE,
                 admitted_members: Iterable[str] | None = None) -> dict:
    """Current hard-gate status: the committed evidence register evaluated for all three architectures."""
    admitted = admitted_member_ids() if admitted_members is None else sorted(admitted_members)
    matrix = load_matrix(matrix_path)
    res = evaluate_all(_read_json(register_path), admitted_members=admitted, matrix=matrix)
    rel = lambda p: os.path.relpath(p, ROOT).replace(os.sep, "/")   # noqa: E731
    res["provenance"] = {"matrix_file": rel(matrix_path), "matrix_sha256": _sha256(matrix_path),
                         "register_file": rel(register_path), "register_sha256": _sha256(register_path),
                         "admitted_members_source": "abep_sim.hall_ensemble.member_ids() "
                                                    "(hallthruster_bridge/ensemble/transport_ensemble_v0.json)",
                         "generated_by": "python -m abep_sim.hard_gates status --out "
                                         "docs/architecture_comparison/hard_gates/hard_gate_status_v1.json"}
    return res


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m abep_sim.hard_gates")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("render-table", help="print the HARD_GATES.md gate table generated from the matrix")
    st = sub.add_parser("status", help="evaluate the committed evidence register for all three architectures")
    st.add_argument("--out", help="write the status JSON here instead of stdout")
    a = ap.parse_args(argv)
    if a.cmd == "render-table":
        sys.stdout.write(render_table())
        return 0
    text = _dump(build_status())
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
