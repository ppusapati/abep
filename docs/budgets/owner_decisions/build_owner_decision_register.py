#!/usr/bin/env python3
"""Consolidated owner decision register v1 (fo_a6_integration_refresh, owner addendum A7): deterministic builder.

Collects VERBATIM every open owner decision of the four merged A6 lanes, each by id with its source path, JSON pointer
and the source file's sha256:

  * Xe ledger (fo_xe_system_ledger)               open_owner_decisions OD-XE-1..8
  * Phase-1 pre-registration framework             reconciliation_items R-01..R-14 and open_owner_decisions[0..4]
  * pre-ionizer module ICD (fo_preionizer_module_icd)  owner_questions PMQ-01..07 and the HWQ items PMQ-07 relays
                                                   (verbatim from docs/experiments/hardware/hardware_requirements_v1.json)
  * subsystem maturity matrix v2 (M16)             open_owner_questions M16-Q-01..04

Per item: needed_by (NOW / before H2 freeze / LOCK-1 / LOCK-2 / later, derived by the fixed phrase rule below from the
source's own words, else UNSTATED), whether it can change a budget or an A7 architecture-changing blocker (with the
reason and a verbatim anchor quote from the source), the source's proposal verbatim, and status OPEN.

No owner decision is taken here and no recommendation is added: the only judgement is the marking of budget / A7
relevance, and every such mark carries a verbatim anchor from the source.

Usage::

    python docs/budgets/owner_decisions/build_owner_decision_register.py --write
    python docs/budgets/owner_decisions/build_owner_decision_register.py --check

Pure standard library; deterministic (no clock, no randomness). Mutable governance files are never read or pinned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DEFAULT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REL = "docs/budgets/owner_decisions"
OUT_JSON = "owner_decision_register_v1.json"
OUT_MD = "OWNER_DECISION_REGISTER.md"
SCRIPT_REL = f"{REL}/build_owner_decision_register.py"

A5 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
A7 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json"
XE = "docs/budgets/xe_ledger/xe_ledger_v1.json"
P1F = "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json"
PMI = "schemas/interfaces/preionizer_module_icd_v1.json"
HWDEF = "docs/experiments/hardware/hardware_requirements_v1.json"
M16 = "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json"
PMI_ROOT = "/x-preionizer-module-icd"

# Immutable inputs: refuse to build on a mismatch.
PINS = {
    A5: "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    A6: "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    A7: "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
    XE: "965fdafa60ae9c3ee1e36189f22ef00198ae3f8a906696213bec13bdcbfb09ad",
    P1F: "84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28",
    PMI: "2470718e1decbde874d2362a997d1e2aaae54eb855d1ed179b930c3be6e7130e",
    HWDEF: "0b75be0a0ddc4888eb157c20e2b22dd4fce2a4bb94c4d6402cbe716ec73b0aa0",
}
# The M16 v2 matrix is produced in the same lane; its sha256 is recorded at build time (a rebuilt matrix makes this
# register STALE under --check).
COMPUTED = [M16]

LANE_OF = {XE: "fo_xe_system_ledger", P1F: "fo_phase1_prereg_framework", PMI: "fo_preionizer_module_icd",
           HWDEF: "fo_hardware_definition (relayed by fo_preionizer_module_icd PMQ-07)",
           M16: "fo_subsystem_maturity_matrix / fo_a6_integration_refresh (M16 v2)"}

# ---------------------------------------------------------------------------------------------------------------------
# needed_by: fixed phrase rule over the source's own words
# ---------------------------------------------------------------------------------------------------------------------
NEEDED_BY_ORDER = ["NOW", "before H2 freeze", "LOCK-1", "LOCK-2", "later"]
MASKS = ["LOCK-1 brief", "LOCK-1 drafts", "LOCK1_DRAFT"]   # document names, not timing
PHRASES = [
    (r"\bNOW\b", "NOW", "the source says NOW"),
    (r"before H2 freeze", "before H2 freeze", "the source says before H2 freeze"),
    (r"LOCK-1", "LOCK-1", "the source ties the item to LOCK-1"),
    (r"before (any )?S1\b", "LOCK-1", "'before S1': LOCK-1 is the last listed gate before S1 (A6 sequence S1a -> LOCK-1 -> W5 freeze -> S1/S1b)"),
    (r"LOCK-2", "LOCK-2", "the source ties the item to LOCK-2"),
    (r"before Phase 1", "LOCK-2", "'before Phase 1': LOCK-2 is the last listed gate before Phase 1 (A6 sequence)"),
]
NEEDED_BY_RULE = ("scan the item's verbatim strings (and the linked source strings named per item) after masking document "
                  "names (" + ", ".join(repr(m) for m in MASKS) + "); map each phrase by the table; needed_by = the earliest "
                  "mapped gate in " + " < ".join(NEEDED_BY_ORDER) + "; a relay or aggregate item takes the earliest over "
                  "itself and the items it names; ICD-sourced items also scan the closes_at of ICD quantities whose text names "
                  "the item id; no match = UNSTATED")

# ---------------------------------------------------------------------------------------------------------------------
# Relevance marks (curated; every non-NO mark carries a verbatim anchor quote checked at build time)
#   budget: YES / NO / SEE_LINKED_ITEMS; budgets from {P_bus, system mass, Xe mass allocation}
#   a7:     CAN_CHANGE (the item can change the content or decision rule of the named A7 blocker)
#           MEASUREMENT_CONDITION_ONLY (changes how the blocker's evidence is obtained on H-1, not the rule)
#           NO / SEE_LINKED_ITEMS
#   anchor: {"in": "item" | <JSON pointer in the same source>, "quote": verbatim substring}
# ---------------------------------------------------------------------------------------------------------------------
B3 = "A7 blocker 3: continuous Xe assistance is disallowed and cathode Xe must fit the system mass allocation"
PH1 = "Phase-1 readings on the common H-1 decide A7 blockers 1 and 2 (A5 cases A / B / C / NO_VIABLE_CASE)"


def _m(budget, budgets, breason, banchor, a7, blockers, areason, aanchor):
    return {"budget": {"value": budget, "budgets": budgets, "reason": breason, "anchor": banchor},
            "a7": {"value": a7, "blockers": blockers, "reason": areason, "anchor": aanchor}}


def _xe(quote, why):
    a = {"in": "item", "quote": quote}
    return _m("YES", ["Xe mass allocation", "system mass"], why, a, "CAN_CHANGE", [3], f"{B3}; {why}", a)


def _proc(quote, blockers, why):
    return _m("NO", [], "test design / schedule of the ground experiment; no flight allocation term", None,
              "MEASUREMENT_CONDITION_ONLY", blockers, f"{why} ({PH1})", {"in": "item", "quote": quote})


MARKS = {
    "OD-XE-1": _xe("books the cathode flow twice", "the accounting convention changes the booked Xe mass (double booking of the cathode flow)"),
    "OD-XE-2": _xe("reserve policy (form and value)", "the reserve is its own Xe mass term"),
    "OD-XE-3": _xe("share of the mass reference the stored-Xe subsystem may take", "the admissible share of the mass reference for the stored-Xe subsystem"),
    "OD-XE-4": _xe("it must not be booked twice", "a residual Xe term enters or stays out of the ledger"),
    "OD-XE-5": _xe("would give 6.48 kg", "the firing-hours basis changes the cathode term (5.4 kg vs 6.48 kg)"),
    "OD-XE-6": _xe("it becomes a new explicit ledger term", "Xe-mode operation beyond ignition, cathode and contingency becomes a new term"),
    "OD-XE-7": _xe("MGA and system margin stay in mass_bom", "the hardware boundary between the Xe ledger and mass_bom decides where Xe-path hardware mass and margin are booked"),
    "OD-XE-8": _xe("whether the 40 kg includes the Xe load", "the reading of the 40 kg requirement decides whether Xe load counts against it"),
    "R-01": _proc("confounds configuration with time", [1, 2], "order balancing of the configurations"),
    "R-02": _proc("seed timing", [1, 2], "randomization seed timing"),
    "R-03": _proc("complete position and carryover balance", [1, 2], "admissible block counts for balance"),
    "R-04": _proc("a condition set must not depend on another configuration's data", [1, 2], "grid fixing under counterbalancing"),
    "R-05": _m("NO", [], "measurement-statistics item; no allocation term", None, "CAN_CHANGE", [1],
               "decides how Case A's utilization criterion is judged when eta_u has no statistical boundary (Case A = Hall-only satisfies the Phase-1 criteria)",
               {"in": "item", "quote": "Case A's utilization criterion"}),
    "R-06": _proc("installation/removal reproducibility of the RF and ECR modules", [2], "module-exchange reproducibility of the RF / ECR modules"),
    "R-07": _m("NO", [], "phase-terminology mapping; no allocation term", None, "CAN_CHANGE", [1, 2],
               "fixes which pivot phases (knee, comparison, absolute gates) make up the A5 H-1 branch decision",
               {"in": "item", "quote": "H-1 branch decision"}),
    "R-08": _m("NO", [], "decision-boundary timing; no allocation term", None, "CAN_CHANGE", [2],
               "whether an effect-size level for the paired configuration contrast is a LOCK-1 rule input or a LOCK-2 value",
               {"in": "item", "quote": "effect-size level"}),
    "R-09": _m("NO", [], "W5 validation custody; no allocation term", None, "NO", [],
               "classification of HW0-REF readings for the held-out Hall-transport validation (W5); not a Phase-1 case-logic input", None),
    "R-10": _proc("within-installation ordering", [1, 2], "propellant ordering within an installation"),
    "R-11": _m("NO", [], "form of a decision criterion; no allocation term", None, "CAN_CHANGE", [2],
               "fixes the form of the net system-level benefit when both Hall-only and a pre-ionized configuration sustain (A5 case B wording)",
               {"in": "item", "quote": "net system-level benefit"}),
    "R-12": _m("NO", [], "decision-status rule; no allocation term", None, "CAN_CHANGE", [1, 2],
               "defines that evidence establishing no A5 outcome leaves the decision OPEN (not NO_VIABLE_CASE)",
               {"in": "item", "quote": "evidence that establishes no outcome"}),
    "R-13": _proc("an arm stop breaks the schedule balance", [1, 2], "schedule handling of a stopped arm"),
    "R-14": _m("YES", ["Xe mass allocation"], "Xe consumed in Xe-augmented peak readings is booked to the single Xe allocation",
               {"in": "item", "quote": "Xe consumed is booked to the single Xe allocation"}, "CAN_CHANGE", [1, 3],
               "an Xe-augmented reading must not count as atmospheric sustainment (blocker 1) and continuous Xe assistance is disallowed (blocker 3)",
               {"in": "item", "quote": "must not be read as atmospheric sustainment"}),
    "P1F-OOD-01": _m("NO", [], "decision topology; no allocation term", None, "CAN_CHANGE", [1, 2],
                     "accepting or amending the framework topology fixes the rules by which Phase 1 decides the A5 case",
                     {"in": "item", "quote": "accept this topology"}),
    "P1F-OOD-02": _m("SEE_LINKED_ITEMS", [], "aggregate of R-01..R-14 (see those entries)", None, "SEE_LINKED_ITEMS", [],
                     "aggregate of R-01..R-14 (see those entries)", None),
    "P1F-OOD-03": _m("NO", [], "reference-condition choice of the ground experiment; no allocation term", None, "MEASUREMENT_CONDITION_ONLY", [1, 2],
                     f"HW-0 reference condition and whether it is merged into an adjacent installation ({PH1})",
                     {"in": "/execution_design/hw0_reference_repeats/cost_note", "quote": "ties the reference to that installation's position"}),
    "P1F-OOD-04": _m("NO", [], "missing-data rule; no allocation term", None, "CAN_CHANGE", [1],
                     "a configuration-caused limit abort is treated as not sustained for that reading (MD-04 rule), i.e. it enters the sustainment classification",
                     {"in": "/missing_data/3/rule", "quote": "treated as not sustained within limits for that reading"}),
    "P1F-OOD-05": _m("NO", [], "decision-status rule; no allocation term", None, "CAN_CHANGE", [1, 2],
                     "same content as R-12 (OPEN decision status)", {"in": "item", "quote": "OPEN decision status"}),
    "PMQ-01": _m("NO", [], "ground-test module envelope; the ICD states the flight pre-ionizer ICD is Milestone C work", None,
                 "MEASUREMENT_CONDITION_ONLY", [2], "a common envelope sized to the largest occupant keeps the fixture from structurally disadvantaging a branch in the blocker-2 comparison",
                 {"in": "item", "quote": "largest occupant"}),
    "PMQ-02": _m("NO", [], "ground-test harness; no allocation term", None, "MEASUREMENT_CONDITION_ONLY", [2],
                 "identical control harness on every occupant (module exchange as the controlled variable)", {"in": "item", "quote": "common control harness"}),
    "PMQ-03": _m("NO", [], "ground-test conductance class; no allocation term", None, "MEASUREMENT_CONDITION_ONLY", [1, 2],
                 "the pressure-drop class sets how equal the feed pressure at the distributor is across configurations", {"in": "item", "quote": "pressure-drop class definition"}),
    "PMQ-04": _m("NO", [], "ground-test calibration series; no allocation term", None, "MEASUREMENT_CONDITION_ONLY", [2],
                 "covers the RF / ECR module-exchange reproducibility not measured by S1b", {"in": "item", "quote": "module-exchange series"}),
    "PMQ-05": _m("NO", [], "ground-test start sequence; no flight allocation term", None, "MEASUREMENT_CONDITION_ONLY", [2],
                 "equalizes Xe exposure before the atmosphere transfer between HW-0 and the pre-ionized configurations", {"in": "item", "quote": "time-matched Xe hold"}),
    "PMQ-06": _m("YES", ["P_bus"], "a module load without a bus_power_boundary_v1 slot is either prohibited or needs a new boundary version",
                 {"in": "item", "quote": "new bus-boundary version"}, "CAN_CHANGE", [2],
                 "A7 blocker 2 is judged after full bus-power accounting; slotless module loads decide what that accounting contains",
                 {"in": "item", "quote": "slotless module loads"}),
    "PMQ-07": _m("SEE_LINKED_ITEMS", [], "relay of HWQ-01/04/05/06/07/15 (see those entries)", None, "SEE_LINKED_ITEMS", [],
                 "relay of HWQ-01/04/05/06/07/15 (see those entries)", None),
    "HWQ-01": _m("NO", [], "ground-test procedure; no allocation term", None, "MEASUREMENT_CONDITION_ONLY", [2],
                 "configuration-change procedure of the paired comparison", {"in": "item", "quote": "Configuration-change procedure"}),
    "HWQ-04": _m("NO", [], "ground-test tolerance; no allocation term", None, "MEASUREMENT_CONDITION_ONLY", [2],
                 "tolerance on the module-induced field change that keeps configurations comparable on H-1 (the ICD records the ECR fringe field as a candidate hard incompatibility)",
                 {"in": "item", "quote": "INV-B3 tolerance on the module-induced field change"}),
    "HWQ-05": _m("YES", ["P_bus"], "an electromagnet is booked as ecr_magnet coil power, a permanent magnet as 0 W",
                 {"in": "item", "quote": "booked as coil power"}, "CAN_CHANGE", [2],
                 "the ecr_hall bus-power term under full bus-power accounting", {"in": "item", "quote": "the ledger must carry the flight value"}),
    "HWQ-06": _m("YES", ["P_bus"], "an RF assist magnet has no bus_power_boundary_v1 slot",
                 {"in": "item", "quote": "where an RF assist-magnet's power is booked"}, "CAN_CHANGE", [2],
                 "the rf_hall bus-power term under full bus-power accounting", {"in": "item", "quote": "no slot in bus_power_boundary_v1"}),
    "HWQ-07": _m("NO", [], "ground-test electrical configuration; no allocation term", None, "MEASUREMENT_CONDITION_ONLY", [2],
                 "module and interstage potential identical across occupants (interstage current enters the cathode budget)",
                 {"in": "item", "quote": "Electrical potential of the module body"}),
    "HWQ-15": _m("NO", [], "interface-freeze timing; no allocation term", None, "MEASUREMENT_CONDITION_ONLY", [2],
                 "frozen module interfaces keep the Phase-1 HW-0 installation valid for the later comparison",
                 {"in": "item", "quote": "so that the Phase-1 HW-0 installation is valid for Phase 2"}),
    "M16-Q-01": _m("NO", [], "accountability assignment; no allocation term", None, "NO", [], "owner assignment only", None),
    "M16-Q-02": _m("NO", [], "scheduling bookkeeping; no allocation term", None, "NO", [],
                   "the scheduler flags record the A7 blockers, they do not define them (A7 is the definition)", None),
    "M16-Q-03": _m("NO", [], "lane-to-row mapping; no allocation term", None, "NO", [], "scheduling bookkeeping", None),
    "M16-Q-04": _m("SEE_LINKED_ITEMS", [], "the RC items include P_bus accounting of ecr_magnet (RC-01) and slotless loads (RC-03)", None,
                   "SEE_LINKED_ITEMS", [], "see the reconciliation items RC-01..RC-10 in the M16 v2 matrix", None),
}

# Linked source strings (same source file) used for proposals and for needed_by scanning.
LINKS = {
    "P1F-OOD-03": ["/execution_design/hw0_reference_repeats/reference_condition", "/execution_design/hw0_reference_repeats/cost_note"],
    "P1F-OOD-04": ["/missing_data/3/rule"],
    "P1F-OOD-05": ["/case_logic/decision_status_open"],
}
# Structural needed_by bases: the item is listed in the framework's LOCK-1 fix list (checked verbatim).
STRUCTURAL = {
    "P1F-OOD-03": [("/locks/lock1_fixes/4", "REF-COND")],
    "P1F-OOD-04": [("/locks/lock1_fixes/1", "missing-data and data-quality rule forms")],
    "P1F-OOD-05": [("/locks/lock1_fixes/1", "the case logic and the OPEN status")],
    "R-12": [("/locks/lock1_fixes/1", "the case logic and the OPEN status")],
}
OVERLAPS = {
    "P1F-OOD-02": [f"R-{i:02d}" for i in range(1, 15)],
    "P1F-OOD-05": ["R-12"], "R-12": ["P1F-OOD-05"],
    "PMQ-04": ["R-06"], "R-06": ["PMQ-04"],
    "PMQ-06": ["HWQ-06"], "HWQ-06": ["PMQ-06"],
}
# The framework's open_owner_decisions are unlabelled strings: expected verbatim, so a changed source fails loudly.
P1F_OOD_EXPECTED = [
    "accept this topology at LOCK-1 (or amend it by a dated addendum before any S1 data)",
    "R-01..R-14 (reconciliation with the lane-25 / lane-06 / LOCK-1 drafts and W5)",
    "REF-COND and the REF-MERGED option",
    "MD-04 treatment of configuration-caused limit aborts",
    "OPEN decision status (R-12)",
]


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(root: str, rel: str):
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"required input missing: {rel}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _ptr(doc, pointer: str):
    cur = doc
    for part in pointer.lstrip("/").split("/"):
        if part == "":
            continue
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k in sorted(o):
            yield from _strings(o[k])
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def verify_pins(root: str) -> dict:
    out = {}
    for rel, want in PINS.items():
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"pinned file missing: {rel}")
        got = _sha(p)
        if got != want:
            raise ValueError(f"pinned file {rel} sha256 {got} != pinned {want}; refusing to build")
        out[rel] = want
    for rel in COMPUTED:
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"required input missing: {rel}")
        out[rel] = _sha(p)
    return out


def _needed_by(texts: list, structural: list) -> dict:
    matches = []
    for where, t in texts:
        tm = t
        for m in MASKS:
            tm = tm.replace(m, "#" * len(m))
        for rx, gate, why in PHRASES:
            for mm in re.finditer(rx, tm):
                matches.append({"phrase": t[mm.start():mm.end()], "maps_to": gate, "why": why, "in": where})
    for where, gate, why in structural:
        matches.append({"phrase": None, "maps_to": gate, "why": why, "in": where})
    if not matches:
        return {"value": "UNSTATED", "matches": []}
    val = min((m["maps_to"] for m in matches), key=NEEDED_BY_ORDER.index)
    seen, uniq = set(), []
    for m in matches:
        k = json.dumps(m, sort_keys=True)
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    return {"value": val, "matches": uniq}


def _check_anchor(rid, anchor, verbatim, src_doc, src_rel):
    if anchor is None:
        return None
    if anchor["in"] == "item":
        hay = "\n".join(_strings(verbatim))
        where = "item"
    else:
        hay = "\n".join(_strings(_ptr(src_doc, anchor["in"])))
        where = f"{src_rel}#{anchor['in']}"
    if anchor["quote"] not in hay:
        raise ValueError(f"{rid}: anchor quote not found verbatim in {where}: {anchor['quote']!r}")
    return {"in": where, "quote": anchor["quote"], "source_calls_it": anchor["in"] == "item"}


def build(root: str = ROOT_DEFAULT) -> dict:
    pins = verify_pins(root)
    xe = _load(root, XE)
    p1 = _load(root, P1F)
    pmi_doc = _load(root, PMI)
    pmi = _ptr(pmi_doc, PMI_ROOT)
    hw = _load(root, HWDEF)
    m16 = _load(root, M16)
    docs = {XE: xe, P1F: p1, PMI: pmi_doc, HWDEF: hw, M16: m16}

    # ICD quantities that name an item id (for ICD-sourced timing)
    icd_q = []
    for i, it in enumerate(pmi["common_items"]):
        for j, q in enumerate(it["quantities"]):
            icd_q.append((f"{PMI}#{PMI_ROOT}/common_items/{i}/quantities/{j}", q))
    for an, a in pmi["annexes"].items():
        for i, m in enumerate(a["module_specific_items"]):
            for j, q in enumerate(m.get("quantities", [])):
                icd_q.append((f"{PMI}#{PMI_ROOT}/annexes/{an}/module_specific_items/{i}/quantities/{j}", q))
    deviations = {}
    for an, a in pmi["annexes"].items():
        for i, d in enumerate(a.get("deviations", [])):
            deviations[d["id"]] = (f"{PMI_ROOT}/annexes/{an}/deviations/{i}", d)

    raw = []   # (register_id, source_id, src_rel, pointer, verbatim, section)
    for i, d in enumerate(xe["open_owner_decisions"]):
        raw.append((d["id"], d["id"], XE, f"/open_owner_decisions/{i}", d, "Xe ledger (fo_xe_system_ledger)"))
    for i, r in enumerate(p1["reconciliation_items"]):
        raw.append((r["id"], r["id"], P1F, f"/reconciliation_items/{i}", r, "Phase-1 framework reconciliation items"))
    if p1["open_owner_decisions"] != P1F_OOD_EXPECTED:
        raise ValueError("the framework's open_owner_decisions changed; revise this register")
    for i, s in enumerate(p1["open_owner_decisions"]):
        raw.append((f"P1F-OOD-{i + 1:02d}", f"open_owner_decisions[{i}]", P1F, f"/open_owner_decisions/{i}", s,
                    "Phase-1 framework open owner decisions"))
    relayed = []
    for i, q in enumerate(pmi["owner_questions"]):
        raw.append((q["id"], q["id"], PMI, f"{PMI_ROOT}/owner_questions/{i}", q, "pre-ionizer module ICD owner questions"))
        if q["id"] == "PMQ-07":
            relayed = re.findall(r"HWQ-\d\d", q["question"])
    hwq_idx = {q["id"]: i for i, q in enumerate(hw["owner_questions"])}
    for h in relayed:
        i = hwq_idx[h]
        raw.append((h, h, HWDEF, f"/owner_questions/{i}", hw["owner_questions"][i], "hardware questions relayed by PMQ-07"))
    for i, q in enumerate(m16["open_owner_questions"]):
        raw.append((q["id"], q["id"], M16, f"/open_owner_questions/{i}", q, "subsystem maturity matrix v2 (M16) open questions"))

    ids = [r[0] for r in raw]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate register id")
    if set(MARKS) != set(ids):
        raise ValueError(f"relevance marks and register items differ: {sorted(set(MARKS) ^ set(ids))}")
    for k, v in OVERLAPS.items():
        if k not in ids or any(x not in ids for x in v):
            raise KeyError(f"overlap reference unknown: {k} -> {v}")

    items = []
    base_nb = {}
    for rid, sid, src, pointer, verbatim, section in raw:
        doc = docs[src]
        if _ptr(doc, pointer) != verbatim:
            raise ValueError(f"{rid}: pointer does not resolve to the verbatim item")
        if isinstance(verbatim, dict) and verbatim.get("id") not in (None, sid):
            raise ValueError(f"{rid}: id mismatch at pointer")
        texts = [("item", t) for t in _strings(verbatim)]
        for lp in LINKS.get(rid, []):
            texts += [(f"{src}#{lp}", t) for t in _strings(_ptr(doc, lp))]
        structural = []
        for sp, quote in STRUCTURAL.get(rid, []):
            v = _ptr(doc, sp)
            if quote not in v:
                raise ValueError(f"{rid}: structural basis {sp} does not contain {quote!r}")
            structural.append((f"{src}#{sp}", "LOCK-1", f"listed in the source's LOCK-1 fix list: {quote!r}"))
        if src in (PMI, HWDEF):
            for where, q in icd_q:
                if re.search(rf"\b{re.escape(sid)}\b", json.dumps(q)) and q.get("closes_at"):
                    texts.append((f"{where}/closes_at", q["closes_at"]))
        base_nb[rid] = _needed_by(texts, structural)

        proposals = []
        if src == XE:
            if "proposed" in verbatim:
                proposals.append({"in": f"{src}#{pointer}/proposed", "text": verbatim["proposed"]})
        elif src == P1F and isinstance(verbatim, dict):
            proposals.append({"in": f"{src}#{pointer}/proposal", "text": verbatim["proposal"]})
        for lp in LINKS.get(rid, []):
            t = _ptr(doc, lp)
            if isinstance(t, str) and "PROPOSED" in t:
                proposals.append({"in": f"{src}#{lp}", "text": t})
        if src == PMI:
            for dev in sorted(set(re.findall(r"DEV-[A-Z0-9]+-\d\d", verbatim["question"]))):
                dp, d = deviations[dev]
                proposals.append({"in": f"{PMI}#{dp}/proposed_control", "text": d["proposed_control"]})
        mk = MARKS[rid]
        budget = dict(mk["budget"])
        a7 = dict(mk["a7"])
        budget["anchor"] = _check_anchor(rid, budget["anchor"], verbatim, doc, src)
        a7["anchor"] = _check_anchor(rid, a7["anchor"], verbatim, doc, src)
        if budget["value"] == "YES" and (not budget["anchor"] or not budget["budgets"]):
            raise ValueError(f"{rid}: a YES budget mark needs budgets and an anchor")
        if a7["value"] in ("CAN_CHANGE", "MEASUREMENT_CONDITION_ONLY") and (not a7["anchor"] or not a7["blockers"]):
            raise ValueError(f"{rid}: an A7 mark needs blockers and an anchor")
        if a7["value"] not in ("CAN_CHANGE", "MEASUREMENT_CONDITION_ONLY", "NO", "SEE_LINKED_ITEMS"):
            raise ValueError(f"{rid}: bad A7 value")
        if budget["value"] not in ("YES", "NO", "SEE_LINKED_ITEMS"):
            raise ValueError(f"{rid}: bad budget value")
        items.append({
            "register_id": rid,
            "source_id": sid,
            "section": section,
            "source_lane": LANE_OF[src],
            "source_path": src,
            "json_pointer": pointer,
            "source_sha256": pins[src],
            "verbatim": verbatim,
            "source_proposal_verbatim": proposals or "NONE_IN_SOURCE (no separate proposal field; see verbatim)",
            "needed_by": None,
            "can_change_budget": budget,
            "can_change_a7_blocker": a7,
            "overlaps_with": OVERLAPS.get(rid, []),
            "status": "OPEN",
        })
    # relays / aggregates take the earliest over themselves and the items they name
    agg = {"PMQ-07": relayed, "P1F-OOD-02": OVERLAPS["P1F-OOD-02"]}
    for it in items:
        rid = it["register_id"]
        nb = dict(base_nb[rid])
        if rid in agg:
            vals = [nb["value"]] + [base_nb[x]["value"] for x in agg[rid]]
            known = [v for v in vals if v != "UNSTATED"]
            nb = {"value": min(known, key=NEEDED_BY_ORDER.index) if known else "UNSTATED",
                  "matches": nb["matches"], "via_items": {x: base_nb[x]["value"] for x in agg[rid]}}
        it["needed_by"] = nb

    def count(f):
        out = {}
        for it in items:
            k = f(it)
            out[k] = out.get(k, 0) + 1
        return {k: out[k] for k in sorted(out)}

    summary = {
        "n_items": len(items),
        "by_section": count(lambda it: it["section"]),
        "by_needed_by": count(lambda it: it["needed_by"]["value"]),
        "by_budget_mark": count(lambda it: it["can_change_budget"]["value"]),
        "by_a7_mark": count(lambda it: it["can_change_a7_blocker"]["value"]),
        "can_change_a7_blocker": {str(b): [it["register_id"] for it in items
                                           if it["can_change_a7_blocker"]["value"] == "CAN_CHANGE" and b in it["can_change_a7_blocker"]["blockers"]]
                                  for b in (1, 2, 3)},
        "can_change_budget": [it["register_id"] for it in items if it["can_change_budget"]["value"] == "YES"],
        "all_status_open": all(it["status"] == "OPEN" for it in items),
    }
    return {
        "schema": "owner_decision_register_v1",
        "id": "owner_decision_register_v1",
        "lane": "fo_a6_integration_refresh",
        "trigger": "T_A6_INTEGRATION_REFRESH",
        "authorization": f"{A7}#m16_as_scheduler; {A6}#authorized_now",
        "status": "REGISTER_FOR_OWNER (no decision taken; every item OPEN)",
        "generated_by": SCRIPT_REL,
        "companion_document": f"{REL}/{OUT_MD}",
        "what_it_is": "every open owner decision of the four merged A6 lanes (plus the HWQ items the pre-ionizer ICD relays), verbatim, by id, with path, JSON pointer and source sha256",
        "what_it_is_not": [
            "not an owner decision: every item stays OPEN",
            "not a recommendation: the only added judgement is the budget / A7-blocker relevance mark, each with a verbatim source anchor",
            "not a change of Bundle 1 (NO_BASELINE_YET), of the credible Hall set (EMPTY) or of any A5 allocation",
            "not an architecture ranking: no winner among hall_only, rf_hall, ecr_hall",
        ],
        "pins": {"sha256": {k: pins[k] for k in PINS}, "computed_at_build": {k: pins[k] for k in COMPUTED},
                 "note": "immutable inputs verified at build time; mutable governance files are never read or pinned"},
        "a7_architecture_changing_blockers": _load(root, A7)["architecture_changing_blockers"],
        "needed_by_vocabulary": NEEDED_BY_ORDER + ["UNSTATED"],
        "needed_by_rule": NEEDED_BY_RULE,
        "needed_by_phrase_table": [{"regex": rx, "maps_to": g, "why": w} for rx, g, w in PHRASES],
        "relevance_vocabulary": {
            "budget": {"YES": "resolving it can change a budget term (P_bus, system mass, Xe mass allocation) or its bookkeeping",
                       "NO": "no allocation term is touched", "SEE_LINKED_ITEMS": "aggregate or relay; see the named items"},
            "a7": {"CAN_CHANGE": "resolving it can change the content or the decision rule of the named A7 blocker",
                   "MEASUREMENT_CONDITION_ONLY": "changes how the blocker's evidence is obtained on H-1 (fixture, schedule, procedure), not the rule",
                   "NO": "no A7 blocker is touched", "SEE_LINKED_ITEMS": "aggregate or relay; see the named items"},
            "anchor": "every YES / CAN_CHANGE / MEASUREMENT_CONDITION_ONLY mark carries a verbatim quote from the source (source_calls_it = true when the quote is in the item itself)",
        },
        "items": items,
        "summary": summary,
        "milestone": {
            "supports": ["A"],
            "statement": ("Milestone A (conditional selection): supported as an execution input only - the register lists, in one "
                          "place and verbatim, the owner decisions that stand between the A5 proposal reference and a conditional "
                          "baseline, and which of them the sources tie to LOCK-1 / LOCK-2. No owner decision is taken and no branch "
                          "is selected; Bundle 1 stays NO_BASELINE_YET. Milestone B: not supported (needs H-1 Phase-1 data or an "
                          "admitted Hall closure; credible set EMPTY). Milestone C: input only (the Xe-ledger and bus-boundary items "
                          "must be decided before a mass / power freeze)."),
            "three_questions": {
                "i_conditional_selection_now": "none; every item is OPEN",
                "ii_what_blocks_physics_backed_selection": "the CAN_CHANGE items on A7 blockers 1 and 2 (framework topology, case wording, OPEN status, MD-04) must be decided by LOCK-1 before any Phase-1 reading; blocker 3 items (OD-XE-*) need C-1 / H-1 measured terms",
                "iii_what_could_overturn": "an owner decision that changes a CAN_CHANGE item after data exist would void LOCK-1 (framework locks.rule)",
            },
        },
        "compliance": {
            "verbatim": "every item is the exact JSON value at its pointer, checked at build time against the pinned source",
            "no_decision": "every status is OPEN",
            "no_winner": "no architecture is ranked, preferred or eliminated",
            "no_hall_performance_source": "no Hall transport closure or screening candidate is used",
            "pure": "standard library only; nothing wired into archengine",
        },
    }


def _esc(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _verb(v) -> str:
    if isinstance(v, str):
        return v
    if "question" in v:
        return v["question"]
    parts = []
    for k in ("topic", "with", "issue", "options", "proposed", "proposal", "note"):
        if k in v:
            val = v[k] if not isinstance(v[k], list) else " / ".join(v[k])
            parts.append(f"{k}: {val}")
    return "; ".join(parts)


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# Owner decision register v1 - open owner decisions of the four merged A6 lanes")
    a("")
    a("| | |")
    a("|---|---|")
    a(f"| lane | `{doc['lane']}` (trigger `{doc['trigger']}`) |")
    a(f"| status | **{doc['status']}** |")
    a(f"| generated by | `{doc['generated_by']}` (`--check` reproduces this file and the JSON exactly) |")
    a(f"| machine-readable | `{REL}/{OUT_JSON}` |")
    a(f"| tests | `tests/test_owner_decision_register.py` |")
    a("")
    a("**Pinned sources (sha256, verified at build time):**")
    a("")
    for rel, h in doc["pins"]["sha256"].items():
        a(f"- `{rel}` - `{h}`")
    for rel, h in doc["pins"]["computed_at_build"].items():
        a(f"- `{rel}` - `{h}` (recorded at build; produced by this lane)")
    a("")
    a("## Milestone statement")
    a("")
    a(doc["milestone"]["statement"])
    a("")
    for k, v in doc["milestone"]["three_questions"].items():
        a(f"- **{k}**: {v}")
    a("")
    a("What this is not: " + "; ".join(doc["what_it_is_not"]) + ".")
    a("")
    s = doc["summary"]
    a("## Summary")
    a("")
    a(f"- items: {s['n_items']} (all OPEN: {s['all_status_open']})")
    a(f"- by section: {json.dumps(s['by_section'])}")
    a(f"- needed_by: {json.dumps(s['by_needed_by'])}")
    a(f"- budget mark: {json.dumps(s['by_budget_mark'])}; can change a budget: {', '.join(s['can_change_budget'])}")
    a(f"- A7 mark: {json.dumps(s['by_a7_mark'])}")
    for b, v in s["can_change_a7_blocker"].items():
        a(f"- can change A7 blocker {b}: {', '.join(v) or '-'}")
    a("")
    a("needed_by rule: " + doc["needed_by_rule"] + ".")
    a("")
    a("## Register")
    a("")
    a("| id | source (pointer) | verbatim | needed_by | budget | A7 blocker | status |")
    a("|---|---|---|---|---|---|---|")
    for it in doc["items"]:
        b, x = it["can_change_budget"], it["can_change_a7_blocker"]
        bb = b["value"] + (f" ({', '.join(b['budgets'])})" if b["budgets"] else "")
        xx = x["value"] + (f" ({', '.join(str(k) for k in x['blockers'])})" if x["blockers"] else "")
        a(f"| {it['register_id']} | `{it['source_path']}#{it['json_pointer']}` | {_esc(_verb(it['verbatim']))} | "
          f"{it['needed_by']['value']} | {bb} | {xx} | {it['status']} |")
    a("")
    a("## Item details")
    for it in doc["items"]:
        a("")
        a(f"### {it['register_id']} ({it['section']})")
        a("")
        a(f"- source: `{it['source_path']}` pointer `{it['json_pointer']}` sha256 `{it['source_sha256']}` (lane `{it['source_lane']}`)")
        a(f"- verbatim: `{_esc(json.dumps(it['verbatim'], ensure_ascii=False))}`")
        if isinstance(it["source_proposal_verbatim"], list):
            for p in it["source_proposal_verbatim"]:
                a(f"- source proposal (`{p['in']}`): {_esc(p['text'])}")
        else:
            a(f"- source proposal: {it['source_proposal_verbatim']}")
        nb = it["needed_by"]
        a(f"- needed_by: **{nb['value']}**" + ("" if not nb["matches"] else " - " + "; ".join(
            (f"'{m['phrase']}'" if m["phrase"] else "listed") + f" -> {m['maps_to']} ({m['in']})" for m in nb["matches"]))
          + ("" if "via_items" not in nb else f"; via items {json.dumps(nb['via_items'])}"))
        for key, lab in (("can_change_budget", "budget"), ("can_change_a7_blocker", "A7 blocker")):
            c = it[key]
            anc = c["anchor"]
            a(f"- {lab}: **{c['value']}**" + (f" {c.get('budgets') or c.get('blockers')}" if (c.get("budgets") or c.get("blockers")) else "")
              + f" - {_esc(c['reason'])}" + (f" - anchor ({anc['in']}): \"{_esc(anc['quote'])}\"" if anc else ""))
        if it["overlaps_with"]:
            a(f"- overlaps with: {', '.join(it['overlaps_with'])}")
        a(f"- status: **{it['status']}**")
    a("")
    return "\n".join(L)


def dump_json(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--root", default=ROOT_DEFAULT)
    args = ap.parse_args(argv)
    doc = build(args.root)
    js, md = dump_json(doc), render_md(doc)
    pj, pm = os.path.join(args.root, REL, OUT_JSON), os.path.join(args.root, REL, OUT_MD)
    if args.write:
        with open(pj, "w", encoding="utf-8") as f:
            f.write(js)
        with open(pm, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"wrote {REL}/{OUT_JSON} and {REL}/{OUT_MD} ({doc['summary']['n_items']} items)")
        return 0
    ok = True
    for p, want in ((pj, js), (pm, md)):
        if not os.path.isfile(p) or open(p, encoding="utf-8").read() != want:
            print(f"STALE: {os.path.relpath(p, args.root)}")
            ok = False
    print("OK" if ok else "rebuild with --write")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
