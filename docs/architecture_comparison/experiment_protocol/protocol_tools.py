"""Tools for the DRAFT common-condition ionization-architecture comparison protocol.

Deterministic and re-runnable; no network, no Julia, no long computation.

    python docs/architecture_comparison/experiment_protocol/protocol_tools.py --check
        validate protocol_draft.json against protocol.schema.json (keyword subset below), check the
        numeric-value discipline, recompute every derived value, and check that the generated numeric
        register in EXPERIMENT_PROTOCOL_DRAFT.md is up to date.
    python docs/architecture_comparison/experiment_protocol/protocol_tools.py --write-md
        regenerate the numeric register block in EXPERIMENT_PROTOCOL_DRAFT.md from the JSON.
    python docs/architecture_comparison/experiment_protocol/protocol_tools.py --derive
        print the derived values.

Derived values (evidence class 'model-derived'):
  * rfp_thrust_per_power_floor = rfp_thrust_min / rfp_power_max, from abep_sim/constants.py (RFPConstraints),
    cross-checked against the RFP values transcribed in the JSON.
  * n_zero_fail:<target id> = ceil(ln(1 - c) / ln p): the smallest number of consecutive successful
    ignitions whose one-sided Clopper-Pearson lower bound at confidence c reaches p.

The schema validator implements only the JSON-Schema keywords used by protocol.schema.json (type, required,
properties, additionalProperties, enum, const, items, minItems, minLength, pattern, $ref to #/$defs, oneOf,
anyOf) so the check runs without adding a dependency. The bus-power boundary module
abep_sim/arch_boundary.py (bus_power_boundary_v1) is referenced by name only and is never imported here.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PROTOCOL = HERE / "protocol_draft.json"
SCHEMA = HERE / "protocol.schema.json"
MARKDOWN = HERE / "EXPERIMENT_PROTOCOL_DRAFT.md"

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
BOUNDARY_VERSION_REF = "bus_power_boundary_v1"
ARM_IDS = ("HALL_ONLY", "RF_HALL", "ECR_HALL")
# Consumer list given for bus_power_boundary_v1 in the lane definition (Hall PPU input incl. conversion
# efficiency, magnet supplies, RF generator DC input incl. matching network and cable losses, microwave source DC
# input, cathode heater and keeper, valves/flow control, thermal control, housekeeping).
BOUNDARY_COMPONENTS = (
    "hall_ppu_input",
    "magnet_supplies",
    "rf_generator_input",
    "microwave_source_input",
    "cathode_heater",
    "cathode_keeper",
    "valves_flow_control",
    "thermal_control",
    "housekeeping",
)
REGISTER_BEGIN = "<!-- BEGIN GENERATED: numeric_register (protocol_tools.py --write-md) -->"
REGISTER_END = "<!-- END GENERATED: numeric_register -->"
_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def load(path: Path = PROTOCOL) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------------------------------------------
# JSON-Schema keyword subset
# --------------------------------------------------------------------------------------------------------------
_TYPES = {
    "object": lambda x: isinstance(x, dict),
    "array": lambda x: isinstance(x, list),
    "string": lambda x: isinstance(x, str),
    "boolean": lambda x: isinstance(x, bool),
    "null": lambda x: x is None,
    "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
    "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
}
_SUPPORTED = {"$schema", "$id", "title", "description", "type", "required", "properties", "additionalProperties",
              "enum", "const", "items", "minItems", "minLength", "pattern", "$ref", "oneOf", "anyOf", "$defs"}


def _resolve(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"only local refs are supported: {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(instance, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """Return a list of error strings (empty = valid) for the supported keyword subset."""
    root = schema if root is None else root
    unknown = set(schema) - _SUPPORTED
    if unknown:
        return [f"{path}: unsupported schema keyword(s) {sorted(unknown)}"]
    errs: list[str] = []
    if "$ref" in schema:
        errs += validate(instance, _resolve(schema["$ref"], root), root, path)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[t](instance) for t in types):
            return errs + [f"{path}: expected type {types}, got {type(instance).__name__}"]
    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in {schema['enum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: string shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: {instance!r} does not match {schema['pattern']}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, item in enumerate(instance):
                errs += validate(item, schema["items"], root, f"{path}[{i}]")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errs.append(f"{path}: missing required key {key!r}")
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                errs += validate(value, props[key], root, f"{path}.{key}")
            elif "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                if extra is False:
                    errs.append(f"{path}: additional key {key!r} not allowed")
                elif isinstance(extra, dict):
                    errs += validate(value, extra, root, f"{path}.{key}")
    if "oneOf" in schema:
        n_ok = sum(1 for sub in schema["oneOf"] if not validate(instance, sub, root, path))
        if n_ok != 1:
            errs.append(f"{path}: matches {n_ok} of oneOf alternatives (need exactly 1)")
    if "anyOf" in schema:
        if not any(not validate(instance, sub, root, path) for sub in schema["anyOf"]):
            errs.append(f"{path}: matches none of anyOf alternatives")
    return errs


# --------------------------------------------------------------------------------------------------------------
# Numeric-value discipline
# --------------------------------------------------------------------------------------------------------------
def walk(obj, path: str = "$"):
    """Yield (path, parent, key, value) for every leaf and container in the JSON tree."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            yield p, obj, k, v
            yield from walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f"{path}[{i}]"
            yield p, obj, i, v
            yield from walk(v, p)


def is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def value_objects(protocol: dict) -> list[tuple[str, dict]]:
    """All numeric and TBD value objects (dicts with an 'id' and a 'value' key), in document order."""
    out = []
    for path, _parent, _key, v in walk(protocol):
        if isinstance(v, dict) and "value" in v and "id" in v:
            out.append((path, v))
    return out


def numeric_discipline_errors(protocol: dict) -> list[str]:
    """Every number is a sourced value object; every 'TBD' states what it requires; value ids are unique."""
    errs = []
    for path, parent, key, v in walk(protocol):
        if is_number(v):
            if not (isinstance(parent, dict) and key == "value"):
                errs.append(f"{path}: bare number {v!r} outside a value object")
                continue
            if not str(parent.get("source", "")).strip():
                errs.append(f"{path}: number without source")
            if parent.get("evidence_class") not in EVIDENCE_CLASSES:
                errs.append(f"{path}: number without a valid evidence_class")
            if not str(parent.get("unit", "")).strip():
                errs.append(f"{path}: number without unit")
        if v == "TBD":
            if not (isinstance(parent, dict) and key == "value" and str(parent.get("tbd_requires", "")).strip()):
                errs.append(f"{path}: TBD without tbd_requires")
    ids = [obj["id"] for _p, obj in value_objects(protocol)]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errs.append(f"duplicate value ids: {dup}")
    return errs


def thresholds(protocol: dict) -> list[tuple[str, dict]]:
    return [(p, v) for p, _parent, _k, v in walk(protocol) if isinstance(v, dict) and "threshold_id" in v]


def threshold_errors(protocol: dict) -> list[str]:
    """Every threshold is PROPOSED, undecided, and its rule references exactly its own parameters."""
    errs = []
    found = thresholds(protocol)
    if not found:
        errs.append("no thresholds found")
    for path, thr in found:
        if thr.get("status") != "PROPOSED":
            errs.append(f"{path}: threshold {thr.get('threshold_id')} status {thr.get('status')!r} != 'PROPOSED'")
        if thr.get("decided_by") is not None:
            errs.append(f"{path}: threshold {thr.get('threshold_id')} carries decided_by")
        used = set(_PLACEHOLDER.findall(thr.get("rule", "")))
        params = {p.get("id") for p in thr.get("parameters", [])}
        if used != params:
            errs.append(f"{path}: rule placeholders {sorted(used)} != parameter ids {sorted(params)}")
        if re.search(r"\d+\.\d+|\d+\s*%", thr.get("rule", "")):
            errs.append(f"{path}: literal number in rule text (use a parameter)")
    for path, _parent, key, v in walk(protocol):
        if key == "threshold" and not (isinstance(v, dict) and "threshold_id" in v):
            errs.append(f"{path}: 'threshold' is not a threshold object")
    ids = [t.get("threshold_id") for _p, t in found]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errs.append(f"duplicate threshold ids: {dup}")
    return errs


def boundary_errors(protocol: dict) -> list[str]:
    """One bus-boundary component list, identical for every arm, consistent with bus_power_boundary_v1."""
    errs = []
    bpb = protocol["bus_power_boundary"]
    comp_ids = [c["id"] for c in bpb["components"]]
    if bpb.get("boundary_version_ref") != BOUNDARY_VERSION_REF:
        errs.append("protocol boundary_version_ref is not bus_power_boundary_v1")
    if tuple(comp_ids) != BOUNDARY_COMPONENTS:
        errs.append(f"component list {comp_ids} != {list(BOUNDARY_COMPONENTS)}")
    arm_ids = [a["id"] for a in protocol["arms"]]
    if tuple(arm_ids) != ARM_IDS:
        errs.append(f"arms {arm_ids} != {list(ARM_IDS)}")
    for arm in protocol["arms"]:
        bb = arm["bus_boundary"]
        if bb.get("boundary_version_ref") != BOUNDARY_VERSION_REF:
            errs.append(f"{arm['id']}: boundary_version_ref differs")
        if bb.get("component_ids") != comp_ids:
            errs.append(f"{arm['id']}: component_ids differ from bus_power_boundary.components")
        if list(bb.get("expected_presence", {})) != comp_ids:
            errs.append(f"{arm['id']}: expected_presence keys differ from the component list")
    return errs


# --------------------------------------------------------------------------------------------------------------
# Derived values
# --------------------------------------------------------------------------------------------------------------
def n_zero_failures(p_target: float, confidence: float) -> int:
    """Smallest n such that n successes in n attempts give a one-sided lower bound >= p_target."""
    n = math.ceil(math.log(1.0 - confidence) / math.log(p_target))
    # guard against floating-point edge effects at an exact boundary
    while (1.0 - confidence) ** (1.0 / n) < p_target:
        n += 1
    while n > 1 and (1.0 - confidence) ** (1.0 / (n - 1)) >= p_target:
        n -= 1
    return n


def clopper_pearson_lower(k: int, n: int, confidence: float) -> float:
    """One-sided Clopper-Pearson lower confidence bound for k successes in n attempts (analysis plan, M5)."""
    if k == 0:
        return 0.0
    if k == n:
        return (1.0 - confidence) ** (1.0 / n)
    from scipy.stats import beta
    return float(beta.ppf(1.0 - confidence, k, n - k + 1))


def _index(protocol: dict) -> dict:
    return {obj["id"]: obj for _p, obj in value_objects(protocol)}


def derive(protocol: dict) -> dict:
    """Recompute every derived value from repository data and the JSON inputs."""
    sys.path.insert(0, str(REPO))
    from abep_sim.constants import RFP  # repository record of the RFP limits

    idx = _index(protocol)
    out = {"rfp_thrust_per_power_floor": RFP.thrust_min_mN / (RFP.power_max_W / 1000.0)}
    aid = protocol["statistics"]["ignition_decision_aid"]
    c = aid["confidence"]["value"]
    for row in aid["rows"]:
        tid = row["target"]["id"]
        out[f"n_zero_fail:{tid}"] = n_zero_failures(idx[tid]["value"], c)
    return out


def derived_errors(protocol: dict) -> list[str]:
    sys.path.insert(0, str(REPO))
    from abep_sim.constants import RFP

    errs = []
    idx = _index(protocol)
    pairs = [("rfp_thrust_min", RFP.thrust_min_mN), ("rfp_thrust_max", RFP.thrust_max_mN),
             ("rfp_power_max", RFP.power_max_W), ("rfp_thrust_min_ref", RFP.thrust_min_mN),
             ("rfp_thrust_max_ref", RFP.thrust_max_mN)]
    for vid, ref in pairs:
        if not math.isclose(idx[vid]["value"], ref, rel_tol=0, abs_tol=1e-12):
            errs.append(f"{vid} = {idx[vid]['value']} differs from abep_sim/constants.py ({ref})")
    derived = derive(protocol)
    seen = set()
    for _p, obj in value_objects(protocol):
        key = obj.get("derived_key")
        if key is None:
            if obj.get("status") == "DERIVED":
                errs.append(f"{obj['id']}: status DERIVED without derived_key")
            continue
        seen.add(key)
        if key not in derived:
            errs.append(f"{obj['id']}: unknown derived_key {key}")
        elif not math.isclose(obj["value"], derived[key], rel_tol=1e-12, abs_tol=1e-12):
            errs.append(f"{obj['id']}: value {obj['value']} != recomputed {derived[key]}")
        if obj.get("evidence_class") != "model-derived" or obj.get("status") != "DERIVED":
            errs.append(f"{obj['id']}: derived value must be model-derived / DERIVED")
    missing = set(derived) - seen
    if missing:
        errs.append(f"derived values not present in the JSON: {sorted(missing)}")
    return errs


# --------------------------------------------------------------------------------------------------------------
# Numeric register (Markdown)
# --------------------------------------------------------------------------------------------------------------
def _cell(x) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def render_register(protocol: dict) -> str:
    num_rows, tbd_rows = [], []
    for path, obj in value_objects(protocol):
        if obj["value"] == "TBD":
            tbd_rows.append(f"| `{obj['id']}` | {_cell(obj['unit'])} | {_cell(obj['tbd_requires'])} |")
        else:
            num_rows.append(f"| `{obj['id']}` | {_cell(obj['value'])} | {_cell(obj['unit'])} | {_cell(obj['status'])} | "
                            f"{_cell(obj['evidence_class'])} | {_cell(obj['source'])} |")
    lines = [REGISTER_BEGIN, "",
             f"Numeric values ({len(num_rows)}), each with source and evidence class:", "",
             "| id | value | unit | status | evidence class | source |", "|---|---|---|---|---|---|", *num_rows, "",
             f"TBD values ({len(tbd_rows)}), each with what it requires:", "",
             "| id | unit | requires |", "|---|---|---|", *tbd_rows, "", REGISTER_END]
    return "\n".join(lines)


def markdown_register_block(text: str) -> str | None:
    a, b = text.find(REGISTER_BEGIN), text.find(REGISTER_END)
    if a < 0 or b < 0:
        return None
    return text[a:b + len(REGISTER_END)]


def write_markdown(protocol: dict, path: Path = MARKDOWN) -> None:
    text = path.read_text(encoding="utf-8")
    old = markdown_register_block(text)
    if old is None:
        raise SystemExit(f"register markers not found in {path}")
    path.write_text(text.replace(old, render_register(protocol)), encoding="utf-8")


def markdown_errors(protocol: dict, path: Path = MARKDOWN) -> list[str]:
    block = markdown_register_block(path.read_text(encoding="utf-8"))
    if block is None:
        return ["numeric register markers missing from the Markdown"]
    if block != render_register(protocol):
        return ["numeric register in the Markdown is stale (run protocol_tools.py --write-md)"]
    return []


# --------------------------------------------------------------------------------------------------------------
# Schedule generator (algorithm pinned here; the seed is fixed at pre-registration)
# --------------------------------------------------------------------------------------------------------------
def randomized_schedule(blocks: list[tuple[str, list[str]]], arms: list[str], replicates: int, seed: int,
                        health_check: str | None = "XE_HEALTH_CHECK") -> list[dict]:
    """CFG-A schedule: one test day per replicate; propellant blocks in the given (fixed) order; operating points
    shuffled inside each block; arm order shuffled inside each point; optional health check at day start and end.

    blocks: [(propellant_block_id, [point_id, ...]), ...] in the fixed block order.
    Returns a list of {"replicate", "block", "point", "arm", "slot"} entries (health checks have arm=None).
    """
    rng = random.Random(seed)
    out: list[dict] = []
    slot = 0

    def add(rep, block, point, arm):
        nonlocal slot
        out.append({"replicate": rep, "block": block, "point": point, "arm": arm, "slot": slot})
        slot += 1

    for rep in range(replicates):
        if health_check:
            add(rep, "health", health_check, None)
        for block, points in blocks:
            pts = list(points)
            rng.shuffle(pts)
            for pt in pts:
                order = list(arms)
                rng.shuffle(order)
                for arm in order:
                    add(rep, block, pt, arm)
        if health_check:
            add(rep, "health", health_check, None)
    return out


# --------------------------------------------------------------------------------------------------------------
def check_all(protocol: dict | None = None) -> list[str]:
    protocol = load() if protocol is None else protocol
    schema = load(SCHEMA)
    errs = [f"schema: {e}" for e in validate(protocol, schema)]
    errs += numeric_discipline_errors(protocol)
    errs += threshold_errors(protocol)
    errs += boundary_errors(protocol)
    errs += derived_errors(protocol)
    errs += markdown_errors(protocol)
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write-md", action="store_true")
    g.add_argument("--derive", action="store_true")
    args = ap.parse_args(argv)
    protocol = load()
    if args.derive:
        print(json.dumps(derive(protocol), indent=2))
        return 0
    if args.write_md:
        write_markdown(protocol)
        print(f"wrote numeric register to {MARKDOWN}")
        return 0
    errs = check_all(protocol)
    for e in errs:
        print("ERROR:", e)
    print("OK" if not errs else f"{len(errs)} error(s)")
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
