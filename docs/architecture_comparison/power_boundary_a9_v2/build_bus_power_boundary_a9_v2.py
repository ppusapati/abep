#!/usr/bin/env python3
"""A9.22 G8 bus-power boundary v2 (bus_power_boundary_a9_v2), a deterministic builder.

Owner decision A9.22 item 8 / G8_BUS_BOUNDARY: create ``bus_boundary_a9_v2`` for the active flight architecture
(``hall_icp_neutralizer`` only), carry C1 only as ground-reference / test metadata, and keep v1 immutable. This
builder uses the standard library only, reads repository files, runs no simulation and wires nothing into archengine.
It does the following:

  * verifies the sha256 of every pinned input: the five v1 boundary files and the A9.19 / A9.20 / A9.22 decisions.
    A missing or changed input stops the build (no fallback). v1 is never rewritten.
  * derives the v2 document from the v1 document. The configuration taxonomy (configuration list, variant options,
    per-slot configuration matrix, enforced orderings, start-up templates) is exported from the pure module
    ``abep_sim/bus_boundary_a9_v2.py``. The C1 columns move under ``ground_reference_test_metadata``. Every other
    field is carried verbatim.
  * computes the field-by-field diff v1 -> v2 of the document and of the instance schema. It refuses any difference
    outside the declared classes IDENTITY (document identity and provenance), TAXONOMY and PROVENANCE_ADDED.
  * writes ``bus_power_boundary_a9_v2.json``, ``BUS_POWER_BOUNDARY_A9_V2.md`` (generated from the JSON) and the
    instance schema ``schemas/interfaces/bus_power_boundary_a9_v2.json``.

No consumer is re-pointed here. The stage-1 consumer inventory is ``CONSUMER_INVENTORY.json`` / ``.md`` in this
directory; the stage-2 migration record (every LIVE_REPOINT consumer re-pointed, before/after diff classified) is
``STAGE2_MIGRATION.json`` / ``.md`` (``build_stage2_migration.py``).

    python docs/architecture_comparison/power_boundary_a9_v2/build_bus_power_boundary_a9_v2.py            # (re)write
    python docs/architecture_comparison/power_boundary_a9_v2/build_bus_power_boundary_a9_v2.py --check    # exit 1 on drift
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from abep_sim import bus_boundary_a9_v2 as B2  # noqa: E402  (pure module, no I/O)

OUT_JSON = os.path.join(HERE, "bus_power_boundary_a9_v2.json")
OUT_MD = os.path.join(HERE, "BUS_POWER_BOUNDARY_A9_V2.md")
OUT_SCHEMA = os.path.join(ROOT, "schemas", "interfaces", "bus_power_boundary_a9_v2.json")
SCRIPT_REL = "docs/architecture_comparison/power_boundary_a9_v2/build_bus_power_boundary_a9_v2.py"
MODULE_REL = "abep_sim/bus_boundary_a9_v2.py"
SCHEMA_REL = "schemas/interfaces/bus_power_boundary_a9_v2.json"
BASE_COMMIT = "9eb302c06241c8e8a369334a6bdc5bc559227143"
DATE = "2026-10-03"
FLIGHT = B2.FLIGHT_CONFIGURATION
GROUND = B2.GROUND_REFERENCE_CONFIGURATION

INPUTS = {
    "V1JSON": ("docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
               "9f6e074cc2cdd1e2445d00a14eec04b4cc33f239655f8619a789e7ae863c43e6",
               "bus_power_boundary_a9_v1 document (immutable history; the source of every carried field)"),
    "V1MOD": ("abep_sim/bus_boundary_a9.py",
              "7b23dbd23d39bd576691f877c0b32b64c14e83e796b2da9a662f0639319c878a",
              "bus_power_boundary_a9_v1 module (immutable; v2 runs its code objects)"),
    "V1SCHEMA": ("schemas/interfaces/bus_power_boundary_a9_v1.json",
                 "64238d1526d8ce6bf3ca6b45f385f8948e6dcf916e4f2140cbcb6c46d2c7aa09",
                 "bus_power_boundary_a9_v1 instance schema (immutable; base of the v2 schema)"),
    "V1BUILDER": ("docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py",
                  "d5c8130ff0f7bea66d9eb82f552f96ebea0eac7f9514fd097bd120ad7397c482",
                  "bus_power_boundary_a9_v1 builder (immutable; not run here)"),
    "V1MD": ("docs/architecture_comparison/power_boundary_a9/BUS_POWER_BOUNDARY_A9.md",
             "bc2c761720ad39a3e7c21a17937ff44a87059d4b5f3b3aadcee64cb323b0a5d0",
             "bus_power_boundary_a9_v1 rendering (immutable; full rendering of the carried sections)"),
    "A922": ("docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json",
             "245307aca27b8151d0ef31a6e92f932a95920e604847694481cba6731835dc49",
             "owner decision A9.22 (G8_BUS_BOUNDARY: create bus_boundary_a9_v2)"),
    "A922MD": ("docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md",
               "749999db6926a2cdda85c7aab7677410b290df11fe4a7bac903a8a8fd6fcfc77",
               "owner decision A9.22 verbatim (item 8)"),
    "A919": ("docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
             "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
             "owner decision A9.19 (one flight architecture: Hall + RF/ICP neutralizer)"),
    "A920": ("docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
             "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
             "owner decision A9.20 (C1 = ground-only laboratory reference)"),
}

# Declared difference classes (JSON-pointer prefixes; '*' matches one list index). Anything else refuses the build.
DOC_CLASSES = (
    ("IDENTITY", ("/id", "/boundary_version", "/module", "/schema_file", "/generated_by", "/regenerate", "/date",
                  "/base_commit", "/compliance/allowed_paths", "/compliance/a9_v1_boundary_byte_identical")),
    ("TAXONOMY", ("/configurations", "/variant_options/" + GROUND, "/slots/*/configurations/" + GROUND,
                  "/sequencing/enforced_order/" + GROUND, "/sequencing/templates_PROPOSED/" + GROUND,
                  "/ground_reference_test_metadata")),
    ("PROVENANCE_ADDED", ("/derived_from", "/v1_to_v2_diff", "/schema_v1_to_v2_diff")),
)
SCHEMA_CLASSES = (
    ("IDENTITY", ("/$id", "/title", "/description", "/properties/boundary_version/const")),
    ("TAXONOMY", ("/properties/configuration/enum", "/x-bus-power-boundary-a9/installed_slots/" + GROUND,
                  "/x-bus-power-boundary-a9/variant_options/" + GROUND,
                  "/x-bus-power-boundary-a9/ground_reference_test_metadata")),
)


class A922BusInputError(RuntimeError):
    """A pinned input is missing or changed, or a v1 -> v2 difference is outside the declared classes."""


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return _sha_bytes(f.read())


def load_inputs() -> dict:
    out = {}
    for key, (rel, sha, _role) in INPUTS.items():
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            raise A922BusInputError(f"pinned input missing: {rel}")
        got = _sha(p)
        if got != sha:
            raise A922BusInputError(f"pinned input changed: {rel} sha256 {got} != {sha} (v1 is immutable)")
        with open(p, encoding="utf-8") as f:
            out[key] = json.load(f) if rel.endswith(".json") else f.read()
    g8 = out["A922"]["decisions"].get("G8_BUS_BOUNDARY", "")
    if not g8.startswith("CREATE_BUS_BOUNDARY_A9_V2") or "hall_icp_neutralizer only" not in g8:
        raise A922BusInputError("A9.22 G8_BUS_BOUNDARY no longer reads CREATE_BUS_BOUNDARY_A9_V2 (hall_icp_neutralizer only)")
    if "`bus_boundary_a9_v2`" not in out["A922MD"]:
        raise A922BusInputError("A9.22 verbatim item 8 no longer names bus_boundary_a9_v2")
    return out


# ------------------------------------------------------------------------------------------------------ diff
def diff(a, b, path: str = "") -> list:
    """Field-by-field difference a -> b as (pointer, change, a_value, b_value); lists of unequal length are one change."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            p = f"{path}/{k}"
            if k not in b:
                out.append((p, "REMOVED", a[k], None))
            elif k not in a:
                out.append((p, "ADDED", None, b[k]))
            else:
                out += diff(a[k], b[k], p)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}/{i}")
        return out
    if a == b and type(a) is type(b):
        return []
    return [(path, "CHANGED", a, b)]


def _match(pointer: str, prefix: str) -> bool:
    ps, qs = pointer.split("/"), prefix.split("/")
    if len(ps) < len(qs):
        return False
    return all(q == "*" and p.isdigit() or q == p for p, q in zip(ps, qs))


def classify(entries: list, classes: tuple, what: str) -> list:
    out, bad = [], []
    for ptr, change, va, vb in entries:
        cls = next((c for c, prefixes in classes if any(_match(ptr, p) for p in prefixes)), None)
        if cls is None:
            bad.append(ptr)
        out.append({"path": ptr, "change": change, "class": cls, "v1_history_value": va, "v2_value": vb})
    if bad:
        raise A922BusInputError(f"{what}: v1 -> v2 differences outside the declared classes: {bad[:12]}")
    return out


# ------------------------------------------------------------------------------------------------------ build
def _slot_status(slot: str, base: dict, variants: dict, config: str) -> str:
    if slot in base[config]:
        return "INSTALLED"
    if slot in variants[config]:
        return "VARIANT_ONLY"
    return "NOT_INSTALLED"


def ground_reference_metadata(v1: dict) -> dict:
    """C1 as ground-reference / test metadata: v1's C1 columns, cross-checked against the pure module."""
    gm = B2.GROUND_REFERENCE_TEST_METADATA[GROUND]
    slot_installation = {s["slot"]: s["configurations"][GROUND] for s in v1["slots"]}
    expect = {s: _slot_status(s, {GROUND: gm["base_slots_as_in_v1"]}, {GROUND: gm["variant_options_as_in_v1"]}, GROUND)
              for s in B2.ALL_SLOTS}
    if slot_installation != expect:
        raise A922BusInputError("v1 document C1 slot matrix disagrees with the v1 module (via v2 metadata)")
    if v1["variant_options"][GROUND] != list(gm["variant_options_as_in_v1"]):
        raise A922BusInputError("v1 document C1 variant options disagree with the v1 module")
    if v1["sequencing"]["enforced_order"][GROUND] != [list(p) for p in gm["enforced_order_as_in_v1"]]:
        raise A922BusInputError("v1 document C1 enforced order disagrees with the v1 module")
    if v1["sequencing"]["templates_PROPOSED"][GROUND] != [dict(s) for s in gm["sequence_template_as_in_v1"]]:
        raise A922BusInputError("v1 document C1 start-up template disagrees with the v1 module")
    return {GROUND: {
        "role": gm["role"],
        "flight_bus_configuration": gm["flight_bus_configuration"],
        "decisions": list(gm["decisions"]),
        "use": gm["use"],
        "v2_ledger": gm["v2_ledger"],
        "slot_installation_as_in_v1": slot_installation,
        "variant_options_as_in_v1": copy.deepcopy(v1["variant_options"][GROUND]),
        "enforced_order_as_in_v1": copy.deepcopy(v1["sequencing"]["enforced_order"][GROUND]),
        "templates_PROPOSED_as_in_v1": copy.deepcopy(v1["sequencing"]["templates_PROPOSED"][GROUND]),
        "note": "values copied from bus_power_boundary_a9_v1 (C1 columns); recorded for bench traceability only - "
                "not a v2 flight bus configuration, not evaluable by the v2 ledger",
    }}


def build_schema(inp: dict) -> tuple:
    v1s = inp["V1SCHEMA"]
    s = copy.deepcopy(v1s)
    s["$id"] = "urn:abep:schemas:interfaces:bus_power_boundary_a9_v2"
    s["title"] = "ABEP A9 spacecraft-DC propulsion bus-power boundary v2 (ledger input declaration)"
    desc = v1s["description"]
    for old, new in (("abep_sim.bus_boundary_a9.ledger", "abep_sim.bus_boundary_a9_v2.ledger"),
                     (INPUTS["V1BUILDER"][0], SCRIPT_REL)):
        if old not in desc:
            raise A922BusInputError(f"v1 schema description no longer contains {old!r}")
        desc = desc.replace(old, new)
    s["description"] = (desc + " v2 (A9.22 G8): configuration hall_icp_neutralizer only; the C1 reference is "
                        "ground-reference / test metadata, not a ledger configuration.")
    s["properties"]["boundary_version"]["const"] = B2.BOUNDARY_VERSION
    s["properties"]["configuration"]["enum"] = list(B2.CONFIGURATIONS)
    variants = sorted({o for c in B2.CONFIGURATIONS for o in B2.VARIANT_OPTIONS[c]})
    if variants != s["properties"]["variant"]["items"]["enum"]:
        raise A922BusInputError("v2 variant-option union differs from v1's: that would be more than a taxonomy change")
    x = s["x-bus-power-boundary-a9"]
    x["installed_slots"] = {c: list(B2.BASE_SLOTS[c]) for c in B2.CONFIGURATIONS}
    x["variant_options"] = {c: list(B2.VARIANT_OPTIONS[c]) for c in B2.CONFIGURATIONS}
    gm = B2.GROUND_REFERENCE_TEST_METADATA[GROUND]
    x["ground_reference_test_metadata"] = {GROUND: {
        "role": gm["role"], "flight_bus_configuration": False,
        "installed_slots_as_in_v1": list(gm["base_slots_as_in_v1"]),
        "variant_options_as_in_v1": list(gm["variant_options_as_in_v1"]),
        "note": "not accepted as a v2 'configuration' value"}}
    sd = classify(diff(v1s, s), SCHEMA_CLASSES, "schema")
    for e in sd:                                 # added section reported by reference, not duplicated
        if e["change"] == "ADDED":
            e["v2_value"] = f"(see schema field {e['path']})"
    return s, sd


def build(inp: dict, schema_diff: list) -> dict:
    v1 = inp["V1JSON"]
    if v1.get("id") != "bus_power_boundary_a9_v1" or v1.get("boundary_version") != B2.PREDECESSOR_BOUNDARY_VERSION:
        raise A922BusInputError("pinned v1 document is not bus_power_boundary_a9_v1")
    d = copy.deepcopy(v1)
    # ---- identity / provenance of the document (not content)
    d["id"] = "bus_power_boundary_a9_v2"
    d["boundary_version"] = B2.BOUNDARY_VERSION
    d["module"] = MODULE_REL
    d["schema_file"] = SCHEMA_REL
    d["generated_by"] = SCRIPT_REL
    d["regenerate"] = f"python {SCRIPT_REL}  (check: --check)"
    d["date"] = DATE
    d["base_commit"] = BASE_COMMIT
    d["compliance"]["allowed_paths"] = [MODULE_REL, "docs/architecture_comparison/power_boundary_a9_v2/**", SCHEMA_REL,
                                        "tests/test_bus_boundary_a9_v2.py"]
    d["compliance"]["a9_v1_boundary_byte_identical"] = True
    # ---- configuration taxonomy (exported from the pure v2 module, as v1's builder exported v1's)
    d["configurations"] = list(B2.CONFIGURATIONS)
    d["variant_options"] = {c: list(B2.VARIANT_OPTIONS[c]) for c in B2.CONFIGURATIONS}
    if [s["slot"] for s in d["slots"]] != list(B2.ALL_SLOTS):
        raise A922BusInputError("v1 slot table order differs from the module's ALL_SLOTS")
    for s in d["slots"]:
        s["configurations"] = {c: _slot_status(s["slot"], B2.BASE_SLOTS, B2.VARIANT_OPTIONS, c)
                               for c in B2.CONFIGURATIONS}
    d["sequencing"]["enforced_order"] = {c: [list(p) for p in B2.ENFORCED_ORDER[c]] for c in B2.CONFIGURATIONS}
    d["sequencing"]["templates_PROPOSED"] = {c: [dict(s) for s in B2.SEQUENCE_TEMPLATES[c]] for c in B2.CONFIGURATIONS}
    d["ground_reference_test_metadata"] = ground_reference_metadata(v1)
    # ---- provenance
    d["derived_from"] = {
        "decision": B2.DECISION,
        "rule": "only the configuration taxonomy differs from bus_power_boundary_a9_v1; every number, slot, rule, "
                "item, owner answer, interface demand, open question and reconciliation record is carried verbatim "
                "(machine-checked: v1_to_v2_diff, schema_v1_to_v2_diff)",
        "predecessor": {"boundary_version": B2.PREDECESSOR_BOUNDARY_VERSION, "status": "IMMUTABLE_HISTORY",
                        "files": [{"key": k, "path": INPUTS[k][0], "sha256": INPUTS[k][1], "role": INPUTS[k][2]}
                                  for k in ("V1JSON", "V1MOD", "V1SCHEMA", "V1BUILDER", "V1MD")]},
        "decision_pins": [{"key": k, "path": INPUTS[k][0], "sha256": INPUTS[k][1], "role": INPUTS[k][2]}
                          for k in ("A922", "A922MD", "A919", "A920")],
        "module_rule": "abep_sim/bus_boundary_a9_v2.py re-exports every non-taxonomy v1 constant (same objects) and "
                       "runs every v1 function's code object rebound to v2 globals, with the boundary label in string "
                       "constants set to bus_power_boundary_a9_v2; a v2 hall_icp_neutralizer ledger equals the v1 "
                       "ledger except boundary_version (tests/test_bus_boundary_a9_v2.py)",
        "carried_text_note": "text carried verbatim from v1 (items A902-25..29/37/43/44, owner answers, interface "
                             "demands, H2-4 flags, open questions, H3/H4 inputs, a9_10_reconciliation) still mentions "
                             "the C1 reference; in v2 it describes the GROUND_ONLY_LAB_REFERENCE recorded under "
                             "ground_reference_test_metadata, never a v2 flight bus configuration",
        "consumers": "docs/architecture_comparison/power_boundary_a9_v2/CONSUMER_INVENTORY.json (stage 1: every "
                     "consumer listed, scanned at the pre-migration commit); stage 2 (one controlled migration) "
                     "re-pointed every LIVE_REPOINT consumer to v2 and proved no physics value changed: "
                     "docs/architecture_comparison/power_boundary_a9_v2/STAGE2_MIGRATION.json",
    }
    d["schema_v1_to_v2_diff"] = schema_diff
    d["v1_to_v2_diff"] = []                      # placeholder so the diff below sees the key as ADDED
    entries = classify(diff(v1, d), DOC_CLASSES, "document")
    for e in entries:                            # added sections are reported by reference, not duplicated
        if e["change"] == "ADDED" and e["path"] in ("/ground_reference_test_metadata", "/derived_from",
                                                    "/schema_v1_to_v2_diff", "/v1_to_v2_diff"):
            e["v2_value"] = f"(see field {e['path']})"
    d["v1_to_v2_diff"] = entries
    return d


# ------------------------------------------------------------------------------------------------------ markdown
def _c(v, limit: int = 160) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        s = f"{v:g}"
    elif isinstance(v, (list, dict)):
        s = json.dumps(v, ensure_ascii=False)
    else:
        s = str(v)
    s = s.replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= limit else s[:limit - 3] + "..."


def _table(rows, cols) -> list:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_c(r.get(c)) for c in cols) + " |")
    return out


def render_md(d: dict) -> str:
    df = d["derived_from"]
    gm = d["ground_reference_test_metadata"][GROUND]
    counts = {}
    for e in d["v1_to_v2_diff"]:
        counts[e["class"]] = counts.get(e["class"], 0) + 1
    L = [f"# A9.22 G8 bus-power boundary `{d['boundary_version']}`", "",
         f"<!-- GENERATED by {d['generated_by']} from bus_power_boundary_a9_v2.json; do not edit by hand -->", "",
         "| item | value |", "|---|---|",
         f"| decision | {df['decision']} |",
         f"| status | {d['status']} |", f"| base commit | `{d['base_commit']}` |",
         f"| module | `{d['module']}` (pure, not wired into archengine) |",
         f"| schema | `{d['schema_file']}` |", f"| regenerate | `{d['regenerate']}` |",
         f"| flight configurations | {', '.join('`' + c + '`' for c in d['configurations'])} |",
         f"| ground reference / test metadata | `{GROUND}` ({gm['role']}; flight bus configuration: "
         f"{gm['flight_bus_configuration']}) |",
         f"| predecessor (immutable) | `{df['predecessor']['boundary_version']}`: "
         + "; ".join(f"`{p['path']}` `{p['sha256']}`" for p in df["predecessor"]["files"]) + " |", "",
         "**Rule.** " + df["rule"] + ".", "", "**Module.** " + df["module_rule"] + ".", "",
         "**Carried text.** " + df["carried_text_note"] + ".", "",
         "**Consumers.** " + df["consumers"] + ".", "",
         "## v1 -> v2 difference (document, field by field)", "",
         "Classes: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
         + ". Every other field of the v1 document is carried byte-for-byte as JSON value.", ""]
    L += _table(d["v1_to_v2_diff"], ["path", "change", "class", "v1_history_value", "v2_value"])
    L += ["", "## v1 -> v2 difference (instance schema)", ""]
    L += _table(d["schema_v1_to_v2_diff"], ["path", "change", "class", "v1_history_value", "v2_value"])
    L += ["", "## Configuration taxonomy (v2)", ""]
    rows = [{"slot": s["slot"], "group": s["group"], FLIGHT: s["configurations"][FLIGHT],
             GROUND + " (ground metadata)": gm["slot_installation_as_in_v1"][s["slot"]]} for s in d["slots"]]
    L += _table(rows, ["slot", "group", FLIGHT, GROUND + " (ground metadata)"])
    L += ["", f"- variant options `{FLIGHT}`: {_c(d['variant_options'][FLIGHT])}",
          f"- enforced order `{FLIGHT}`: " + "; ".join(f"{a} < {b}" for a, b in d["sequencing"]["enforced_order"][FLIGHT]),
          "", f"### `{FLIGHT}` start-up template (PROPOSED, carried from v1)", ""]
    L += _table(d["sequencing"]["templates_PROPOSED"][FLIGHT], ["step_id", "name", "event", "on", "phase"])
    L += ["", f"## Ground reference / test metadata: `{GROUND}`", "", f"- role: {gm['role']}",
          f"- use: {gm['use']}", f"- v2 ledger: {gm['v2_ledger']}", f"- decisions: {'; '.join(gm['decisions'])}",
          f"- variant options (as in v1): {_c(gm['variant_options_as_in_v1'])}",
          "- enforced order (as in v1): " + "; ".join(f"{a} < {b}" for a, b in gm["enforced_order_as_in_v1"]), ""]
    L += _table(gm["templates_PROPOSED_as_in_v1"], ["step_id", "name", "event", "on", "requires_flags", "phase"])
    L += ["", "## Carried unchanged from v1", "",
          f"Items {len(d['items'])}, slots {len(d['slots'])}, RF power planes {len(d['rf_power_planes'])}, interface "
          f"demands {len(d['interface_demands'])}, H2-4 flags {len(d['h2_4_revision_flags'])}, owner answers "
          f"{len(d['owner_answers_applied'])}, open owner questions {len(d['open_owner_questions'])}, H3/H4 inputs "
          f"{len(d['h3_inputs'])}/{len(d['h4_inputs'])}; bus architecture, gates and allocations, sequencing rules, "
          f"historical reuse, M16 impact and the A9-10 reconciliation record are identical to v1. Full rendering: "
          f"`{df['predecessor']['files'][4]['path']}`.", ""]
    L += _table(d["items"], ["id", "name", "value", "units", "evidence_class", "status", "freeze_point"])
    L += ["", "## Compliance", "", f"`{json.dumps(d['compliance'], sort_keys=True)}`", ""]
    return "\n".join(L)


def dumps(d: dict) -> str:
    return json.dumps(d, indent=1, ensure_ascii=False) + "\n"


def outputs() -> dict:
    inp = load_inputs()
    schema, sd = build_schema(inp)
    d = build(inp, sd)
    return {OUT_JSON: dumps(d), OUT_MD: render_md(d), OUT_SCHEMA: dumps(schema)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify the committed outputs reproduce byte-for-byte")
    a = ap.parse_args(argv)
    outs = outputs()
    if a.check:
        bad = [os.path.relpath(p, ROOT) for p, txt in outs.items()
               if not os.path.isfile(p) or open(p, encoding="utf-8").read() != txt]
        if bad:
            print("DRIFT: " + ", ".join(bad))
            return 1
        print("OK")
        return 0
    for p, txt in outs.items():
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
    print("wrote " + ", ".join(os.path.relpath(p, ROOT) for p in outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
