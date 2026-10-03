"""Build the result schemas schemas/results/raw_closure_v2.json and closure_assessment_v1.json (A9.23 source-of-truth
index; no numerical change, no physics edit).

Owner directive A9.23 (docs/decisions/OD_2026_10_03_A9_23_*): raw physical results and the assessment / compliance
result are separate artefacts, each with one authoritative schema. Neither schema existed as a file: the versions were
only constants (abep_sim.system.RAW_CLOSURE_SCHEMA_VERSION, abep_sim.assessment.closure_checks.ASSESSMENT_SCHEMA_VERSION).
This builder derives both schemas from the ACTUAL outputs of ``abep_sim.system.physics_closure`` and
``abep_sim.assessment.assess`` on four reference configurations, one per closure path (parametric, gas-path physics,
+ plasma physics, + engineering physics), so the key sets, JSON types and path-conditional groups are observed, never
typed by hand. Only key names / types / presence are recorded (no value).

Usage: python scripts/config/build_result_schemas.py           write schemas/results/
       python scripts/config/build_result_schemas.py --check   regenerate in memory, compare byte for byte (exit 1 if stale)
The first gas-path closure builds the TPMC intake surface cache (about 1-2 min).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "schemas" / "results"
GENERATED_BY = "scripts/config/build_result_schemas.py"
REGENERATE = "python scripts/config/build_result_schemas.py  (check: --check)"
RAW_FILE, ASSESS_FILE = "raw_closure_v2.json", "closure_assessment_v1.json"
JSON_SCHEMA = "https://json-schema.org/draft/2020-12/schema"

# Reference configurations, one per closure path (the same set tests/test_layer_separation_physics.py runs).
PATHS = ("parametric", "gaspath_physics", "plasma_physics", "engineering_physics")


def _configs():
    from abep_sim.intake import IntakeParams, CompressorParams
    from abep_sim.system import Config
    tp = {"accommodation": 0.8, "use_tpmc": True, "L_over_d": 5}
    eng = dict(hall_L_m=0.20, hall_shielding=0.03, hall_wall_mm=6.0, blade_coating_um=50, xe_aug_hours=500)
    return {
        "parametric": Config("hall_1stage", 200, "mean", IntakeParams(area_m2=1.5), CompressorParams(ratio=500),
                             vd_V=250),
        "gaspath_physics": Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, **tp),
                                  CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True),
        "plasma_physics": Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, **tp),
                                 CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True, plasma_physics=True),
        "engineering_physics": Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, **tp),
                                      CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True,
                                      plasma_physics=True, engineering_physics=True, **eng),
    }


def _jtype(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, (list, tuple)):
        return "array"
    if isinstance(v, dict):
        return "object"
    raise TypeError(f"unexpected result value type {type(v).__name__}")


def _schema(records: dict, *, sid: str, title: str, extra: dict, consts: dict) -> dict:
    """records: path -> output dict, in PATHS order (each path adds keys to the previous one)."""
    order = [p for p in PATHS if p in records]
    keysets = [set(records[p]) for p in order]
    for a, b in zip(keysets, keysets[1:]):
        if not a <= b:
            raise RuntimeError(f"{sid}: path key sets are not nested ({sorted(a - b)[:5]} ...)")
    types: dict = {}
    for p in order:
        for k, v in records[p].items():
            types.setdefault(k, set()).add(_jtype(v))
    first = list(records[order[0]])
    keys = list(dict.fromkeys(k for p in order for k in records[p]))      # ordered union
    conditional = {}
    for prev, p in zip(order, order[1:]):
        added = [k for k in records[p] if k not in records[prev]]
        if added:
            conditional[p] = added
    props = {}
    for k in keys:
        t = sorted(types[k])
        props[k] = {"const": consts[k]} if k in consts else {"type": t[0] if len(t) == 1 else t}
    return {
        "$schema": JSON_SCHEMA,
        "$id": sid,
        "title": title,
        "type": "object",
        "required": first,
        "properties": props,
        "additionalProperties": False,
        "x-abep": {**extra, "generated_by": GENERATED_BY, "regenerate": REGENERATE,
                   "derivation": "key names, JSON types and presence observed on the outputs of the reference "
                                 "configurations below (one per closure path); no value is recorded",
                   "reference_paths": order,
                   "path_conditional_keys": conditional},
    }


def build() -> dict[str, bytes]:
    from abep_sim import system
    from abep_sim.assessment import closure_checks as cc
    cfgs = _configs()
    raw = {p: system.physics_closure(c) for p, c in cfgs.items()}
    assessed = {p: cc.assess(raw[p], cc.constraints_from_config(c), cc.priors_from_config(c)) for p, c in cfgs.items()}
    raw_schema = _schema(
        raw, sid=system.RAW_CLOSURE_SCHEMA_VERSION,
        title="Raw physics / design closure (abep_sim.system.physics_closure): physical and design quantities and "
              "model labels only; no requirement check, IC metric, preference flag or compliance class",
        consts={"raw_schema_version": system.RAW_CLOSURE_SCHEMA_VERSION},
        extra={"layer": "RAW_PHYSICS_RESULT", "producer": "abep_sim.system.physics_closure",
               "version_constant": "abep_sim.system.RAW_CLOSURE_SCHEMA_VERSION",
               "forbidden_key_prefixes": list(cc.FORBIDDEN_RAW_PREFIXES),
               "forbidden_keys": list(cc.FORBIDDEN_RAW_KEYS),
               "raw_only_keys": list(cc.RAW_ONLY_KEYS)})
    bad = [k for k in raw_schema["properties"] if k.startswith(cc.FORBIDDEN_RAW_PREFIXES) or k in cc.FORBIDDEN_RAW_KEYS]
    if bad:
        raise RuntimeError(f"raw closure carries assessment keys {bad}")
    as_schema = _schema(
        assessed, sid=cc.ASSESSMENT_SCHEMA_VERSION,
        title="Assessment / compliance result of one raw closure (abep_sim.assessment.assess): checks, IC metrics, "
              "classifications, requirement pointers and the constraint values used",
        consts={"assessment_schema_version": cc.ASSESSMENT_SCHEMA_VERSION,
                "raw_schema_version": system.RAW_CLOSURE_SCHEMA_VERSION},
        extra={"layer": "ASSESSMENT_RESULT", "producer": "abep_sim.assessment.closure_checks.assess",
               "version_constant": "abep_sim.assessment.closure_checks.ASSESSMENT_SCHEMA_VERSION",
               "consumes": [system.RAW_CLOSURE_SCHEMA_VERSION, "config/constraints/engineering_constraints_v1.json"],
               "constraints_fields": list(cc.Constraints.__dataclass_fields__)})
    dump = lambda d: (json.dumps(d, indent=1, ensure_ascii=False) + "\n").encode("utf-8")     # noqa: E731
    return {RAW_FILE: dump(raw_schema), ASSESS_FILE: dump(as_schema)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare the regenerated schemas with schemas/results/")
    a = ap.parse_args(argv)
    files = build()
    if a.check:
        stale = [k for k, v in files.items() if not (OUT / k).is_file() or (OUT / k).read_bytes() != v]
        if stale:
            print(f"STALE: {stale}")
            return 1
        print(f"OK: {len(files)} result schemas current")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for k, v in files.items():
        (OUT / k).write_bytes(v)
    print(f"wrote {len(files)} files under schemas/results/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
