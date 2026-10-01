#!/usr/bin/env python3
"""A9.16 mass + power integration v3 (mass_power_a9_v3) - a REVISION of the immutable mass / power v2.

Lane: A9.16 step 1, mass / power v3 + Xe accounting v3 (owner instruction 2026-10-01 'continue implementing them
sequentially'). Deterministic; standard library plus abep_sim.bus_boundary_a9 (import only, through the new helper
peak_sampled_gate_a9_v3.py); no Julia; well under a second. v2 (docs/budgets/mass_power_a9_v2/) is pinned by sha256 and
read as data, never edited. The Xe accounting v3 JSON is read back (ids / values checked, not sha-pinned: cross-lane).

v3 = v2 + the recorded owner decisions applied (the verbatim .md of each decision governs; every quote is checked
verbatim at build time; every id must be OWNER_DECIDED in the decision json):
  * A9.14 MQ-01  row-54 allocations are MEV-level line budgets: no second row-57 margin on an allocation; a heavier
                 CBE x 1.20 or evidence planning floor overrides the allocation (one governing reading; the v2
                 CBE-level reading and the owner-v0-literal reference are retired);
  * A9.14 MQ-02  the 20 % system margin replaces the fixed 4 kg reserve and is recomputed from the current pre-margin
                 sum (today's row-54 allocation sum 24 kg -> 4.8 kg -> 28.8 kg; the evidence-based sum is recomputed
                 the same way - never a frozen 4.8 kg);
  * A9.14 MQ-03 / MQ-04 / MQ-05  AL-04 >= 1.20 x H-1 CBE (today's incomplete planning floor 4.2048 kg from the 3.504 kg
                 magnetic parts), AL-07 MEV planning floor 6.0 kg (5.0 kg lowest admissible PPU analog; replaced by the
                 flight PPU CBE), AL-08 = complete Xe storage / flow hardware, planning floor 6.0528 kg (5.044 kg CBE
                 floor; quotations / design replace it);
  * A9.14 MQ-06  harness is its own line (row-60 rule); controls / electronics / valve drivers a separate allocation /
                 CBE line (its allocation is not stated by the owner -> TBD_OWNER, MPV3Q-01);
  * A9.14 MQ-07 + MPQ-02  item -> line mappings exactly as the verbatim answers;
  * A9.14 MQ-09 + XA9Q-01 + OQ-A910-01  2 / 5 / 10 kg = LOADED Xe (usable + reserve + residual), one reading for both
                 ledgers; the residual is never added again in the wet roll-up;
  * A9.14 MQ-10  no margin relaxation to pass 40 kg: the evidence-based exceedance and the redesign need are reported;
  * A9.14 MPQ-01 + A9.15  option (c): C1 electronics in AL-07, a C1 Xe branch in AL-08 only if the selected C1 requires
                 Xe, AL-C1 = selected C1 module CBE x 1.20 only when C1 is selected (no kg value now);
  * A9.14 OQ-A907-07 + A9.15  flight C1 integration deferred until C1 is selected (not because Xe is contingency-only);
  * A9.14 XA9Q-07 / XV2Q-01 + A9.15  hall_icp_neutralizer is NOT Xe-free: AL-08 and the Xe load are RFP-required in
                 both configurations; XV2Q-01 NOT APPLICABLE;
  * A9.14 OQ-A910-05  local match booked on AL-06; the matched sham reproduces the local-match parasitics (ground);
  * A9.14 OQ-A910-03  peak_sampled < 1500 W one-sided sufficient PASS only on a conformant record; >= 1500 W is not a
                 failure - the 1 ms maximum decides (NEW helper peak_sampled_gate_a9_v3.py; bus_boundary_a9 unchanged).

Evidence classes stay per line; no CBE is invented; no PASS is produced for thermal, RF ratings, anode or ICP capacity.

    python docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py          # (re)write JSON and Markdown
    python docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py --check  # exit 1 unless reproduced byte for byte
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

LANE_REL = "docs/budgets/mass_power_a9_v3"
SCRIPT_REL = LANE_REL + "/build_mass_power_a9_v3.py"
HELPER_REL = LANE_REL + "/peak_sampled_gate_a9_v3.py"
JSON_NAME = "mass_power_a9_v3.json"
MD_NAME = "MASS_POWER_A9_V3.md"
TEST_REL = "tests/test_mass_power_a9_v3.py"
SCHEMA_ID = "mass_power_a9_v3"
BASE_COMMIT = "f68b9999ebc89c41ab051bfaebf03c04fc58cc78"
DATE = "2026-10-01"
XE_V3 = "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json"   # cross-lane: read, ids checked, not pinned

V2 = {
    "V2_JSON": ("docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json",
                "c1a7875fdd0e27b3425cc02ba915ab61bcf9760ac032d294b69a887a91e78459"),
    "V2_MD": ("docs/budgets/mass_power_a9_v2/MASS_POWER_A9_V2.md",
              "6032ca8c15798460e6a67913c14a0413e12e3f4698730152a33f79d4230bba4e"),
    "V2_BUILDER": ("docs/budgets/mass_power_a9_v2/build_mass_power_a9_v2.py",
                   "88a4f0878ba388f8a792138ee5625f83a087fc069dd67049e883a96e0701481b"),
}
BUS_MODULE = ("abep_sim/bus_boundary_a9.py", "7b23dbd23d39bd576691f877c0b32b64c14e83e796b2da9a662f0639319c878a")
DECISIONS = {
    "A9.12": {"json": "docs/decisions/OD_2026_10_01_A9_12_s5_p3_p4_owner_decisions.json",
              "json_sha256": "1485f00b7abe7e621f8dc2d32d8d97704e10e71d53c97b4f617bc022d1f2359d",
              "md": "docs/decisions/OD_2026_10_01_A9_12_S5_P3_P4_OWNER_DECISIONS.md",
              "md_sha256": "d8baac842cfe574037427aef1ced2476ba96919d80ceacda9b2bf16502e0af62"},
    "A9.13": {"json": "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json",
              "json_sha256": "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23",
              "md": "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md",
              "md_sha256": "adf11923c07f773276ee893d6ad01cd51c4988ba4bfb8865ec1d781a4978c8bf"},
    "A9.14": {"json": "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
              "json_sha256": "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
              "md": "docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md",
              "md_sha256": "2a61c761120863c4b5821043ab78b6f9b28227584f7d83cb48ecd6598ed0af07"},
    "A9.15": {"json": "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "json_sha256": "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              "md": "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "md_sha256": "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903"},
}

CONFIGS = ("hall_icp_neutralizer", "hall_c1_reference")
SYSTEM_MARGIN = 0.2              # A9.14 MQ-02 (owner-supplied; row 52)
EQUIPMENT_MARGIN = 0.2           # row 57 default for new / unselected parts; inside the MEV allocation (MQ-01)
HARNESS_FRACTION = 0.05          # row 60
OWNER_MEV_FLOORS = {"AL-04": 4.2048, "AL-07": 6.0, "AL-08": 6.0528}   # A9.14 MQ-03 / MQ-04 / MQ-05 (owner-stated)
OWNER_MQ02_CHECK = (24.0, 4.8, 28.8)                                  # A9.14 MQ-02 (owner-stated arithmetic)
CLOSURE = ("CLOSES", "DOES_NOT_CLOSE", "NOT_EVALUABLE")
C1_STATES = ("NOT_SELECTED", "SELECTED")


class PinError(RuntimeError):
    """A pinned immutable input does not match its recorded sha256."""


class MassError(ValueError):
    """A refused reading, a double count or an impossible value (fail closed)."""


# ------------------------------------------------------------------------------------------------ helpers
def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins() -> None:
    bad = [f"{p} (expected {s[:12]}, got {_sha(p)[:12]})" for p, s in list(V2.values()) + [BUS_MODULE]
           if _sha(p) != s]
    for k, d in DECISIONS.items():
        for f in ("json", "md"):
            if _sha(d[f]) != d[f + "_sha256"]:
                bad.append(f"{k} {d[f]}")
    if bad:
        raise PinError("pinned immutable inputs changed: " + "; ".join(bad))


def _load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    return " ".join(s.split())


_DEC: dict = {}


def _decision(key: str):
    if key not in _DEC:
        d = DECISIONS[key]
        _DEC[key] = (_load(d["json"]), _norm((REPO / d["md"]).read_text(encoding="utf-8")))
    return _DEC[key]


def OD(key: str, qid: str, quote: str) -> dict:
    """Verbatim-checked source record of one owner decision (quote in the .md; id OWNER_DECIDED in the json)."""
    js, md = _decision(key)
    if _norm(quote) not in md:
        raise MassError(f"{key} {qid}: quote not found verbatim in {DECISIONS[key]['md']}: {quote[:80]!r}")
    if key == "A9.15":
        if qid != "governing_rule" and qid not in js["amendments"]:
            raise MassError(f"A9.15 has no amendment {qid}")
        seq = None
        ans = "RFP_COMPLIANT_PROPELLANT_POLICY" if qid == "governing_rule" else js["amendments"][qid]
    else:
        rec = js["decisions"].get(qid)
        if rec is None or rec.get("status") != "OWNER_DECIDED":
            raise MassError(f"{key} {qid} is not an OWNER_DECIDED entry of {DECISIONS[key]['json']}")
        seq, ans = rec.get("sequenced_no"), rec.get("answer")
    return {"key": key, "id": qid, "sequenced_no": seq, "answer": ans, "quote": quote,
            "path": DECISIONS[key]["md"], "md_sha256": DECISIONS[key]["md_sha256"],
            "json_path": DECISIONS[key]["json"], "json_sha256": DECISIONS[key]["json_sha256"]}


def cite(s: dict) -> str:
    return f"{s['key']} {s['id']} ({s['json_path']} sha256 {s['json_sha256'][:12]})"


def rk(x):
    return None if x is None else float(f"{x:.10g}")


def r6(x):
    return None if x is None else float(f"{x:.6f}".rstrip("0").rstrip(".")) if x != 0 else 0.0


def _kg(v, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) < 0:
        raise MassError(f"{what} = {v!r} must be a finite mass >= 0 kg")
    return float(v)


def _helper():
    spec = importlib.util.spec_from_file_location("peak_sampled_gate_a9_v3", REPO / HELPER_REL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------ owner decisions
def S() -> dict:
    return {
        "MQ01": OD("A9.14", "MQ-01",
                   "ROW-54 ALLOCATIONS ARE MEV-LEVEL BUDGETS. Equipment margin is already inside the line allocation; "
                   "do not add the row-57 margin a second time to an owner MEV allocation. Actual CBE/evidence floors "
                   "still override allocations when heavier."),
        "MQ02": OD("A9.14", "MQ-02",
                   "THE 20% SYSTEM MARGIN REPLACES THE FIXED 4 kg RESERVE. Do not add both. With the present 24 kg "
                   "pre-system-margin owner allocation, the formula gives 4.8 kg, hence 28.8 kg; if line allocations "
                   "change, recalculate 20% rather than freezing 4.8 kg forever."),
        "MQ03": OD("A9.14", "MQ-03",
                   "REBASE AL-04; DO NOT PATCH ONLY THE 0.504 kg GAP. Under the MEV reading, the currently known "
                   "3.504 kg magnetic-parts floor already implies 4.2048 kg MEV, before channel/anode/body/fasteners."),
        "MQ04": OD("A9.14", "MQ-04",
                   "Use the present lowest 5.0 kg admissible analog as a provisional CBE floor, giving a 6.0 kg MEV "
                   "planning floor under the selected margin convention. Replace it with the selected flight PPU CBE "
                   "when available. Do not consume system margin to disguise an under-allocated PPU."),
        "MQ05": OD("A9.14", "MQ-05",
                   "AL-08 INCLUDES THE COMPLETE Xe STORAGE/FLOW HARDWARE. Scope includes Xe tank, regulator, valves, "
                   "plumbing, mounting and thermal hardware. The current 5.044 kg incomplete CBE floor implies "
                   "6.0528 kg MEV planning floor; quotations/design replace this value."),
        "MQ06": OD("A9.14", "MQ-06",
                   "Harness is its own mass line governed by the row-60 percentage rule; electronics/controls/valve "
                   "drivers form a separate allocation/CBE line."),
        "MQ07": OD("A9.14", "MQ-07",
                   "collector/bias electrode → AL-05; collector/bias supply → AL-07; RF feedthrough/coax/local match → "
                   "AL-06; flight sensors/valve drivers → controls portion of AL-09; Xe mounting/thermal/plumbing → "
                   "AL-08."),
        "MQ09": OD("A9.14", "MQ-09",
                   "Residual may appear as an accounting sub-line but is not added a second time."),
        "MQ10": OD("A9.14", "MQ-10",
                   "DO NOT RELAX THE MARGIN READING TO MAKE 40 kg PASS. If evidence-based mass exceeds the RFP limit, "
                   "reduce actual subsystem CBE through redesign, integration or lighter qualified parts. Allocation "
                   "bookkeeping cannot override real evidence."),
        "XA9Q01": OD("A9.14", "XA9Q-01",
                     "2/5/10 kg ARE LOADED-Xe CASES. Reserve and residual are carved out within each total loaded "
                     "mass."),
        "OQA91001": OD("A9.14", "OQ-A910-01",
                       "ONE ACCOUNTING READING GOVERNS BOTH LEDGERS: LOADED Xe. The 2/5/10 kg case includes usable "
                       "mission quantity, reserve and residual. Do not add residual again in the mass BOM."),
        "MPQ01": OD("A9.14", "MPQ-01",
                    "C1 heater/keeper/control electronics belong inside AL-07; the C1 Xe branch belongs inside AL-08; "
                    "create a separate AL-C1 only for the cathode module, shield/mount and any C1-specific "
                    "getter/filter. Do not invent a fixed kg allocation now: set `AL-C1 = selected C1 module CBE × "
                    "1.20` under the chosen MEV convention when C1 is actually selected."),
        "MPQ01_A": OD("A9.15", "MPQ-01",
                      "S8.33 / MPQ-01: if C1 is selected and requires Xe, its C1-specific branch is booked within the "
                      "RFP-compliant Xe system; do not assume or exclude C1 Xe in advance."),
        "MPQ02": OD("A9.14", "MPQ-02",
                    "ICP isolation hardware → AL-05; RF protection/sensing electronics → AL-06; anode heat-removal "
                    "hardware → AL-04; ICP open-frame support/spacer → AL-10."),
        "OQA90707": OD("A9.14", "OQ-A907-07",
                       "Do not burden the baseline flight article with C1 until C1 is actually selected as a flight "
                       "fallback. Development/reference C1 work continues separately."),
        "OQA90707_A": OD("A9.15", "OQ-A907-07",
                         "S8.17 / OQ-A907-07: C1 flight integration may still be deferred until C1 is selected, but "
                         "not because Xe is contingency-only."),
        "XA9Q07": OD("A9.14", "XA9Q-07",
                     "YES, Xe CAPABILITY APPLIES TO `hall_icp_neutralizer`. The RFP requires compatibility with both "
                     "ambient air and Xenon and explicitly mentions separate ambient-air and Xe propellant storage."),
        "XA9Q07_A": OD("A9.15", "XA9Q-07",
                       "S8.21 / XA9Q-07: YES — Xe capability applies to the `hall_icp_neutralizer` flight "
                       "configuration because the RFP requires it."),
        "XV2Q01": OD("A9.14", "XV2Q-01",
                     "NOT APPLICABLE BECAUSE XA9Q-07 = YES. `hall_icp_neutralizer` retains the RFP-required Xe "
                     "propulsion capability. It is not Xe-free."),
        "XV2Q01_A": OD("A9.15", "XV2Q-01",
                       "S8.35 / XV2Q-01: becomes NOT APPLICABLE, because the system is not Xe-free under the RFP."),
        "GOV": OD("A9.15", "governing_rule",
                  "The official RFP is the sole governing basis for propellant capability. The system shall support "
                  "both ambient atmospheric propellant and Xenon. C1-specific Xe requirements, if any, are derived from "
                  "the selected C1 hardware and integrated into that RFP-compliant Xe architecture; no independent "
                  "policy shall restrict or override the RFP."),
        "OQA91005": OD("A9.14", "OQ-A910-05",
                       "YES: MATCHED SHAM MUST REPRODUCE THE LOCAL-MATCH PARASITICS. Provide mass/stiffness/thermal/"
                       "service-line equivalent as necessary for force-system equivalence. Book the local matching "
                       "hardware on AL-06 RF generator/matching, not AL-05."),
        # A9.16 repair F5 / F10
        "OQA91006": OD("A9.12", "OQ-A910-06",
                       "Decision: YES — retain 600 W temporarily, then supersede it with the P2-derived RF thermal "
                       "envelope."),
        "OQA90701": OD("A9.14", "OQ-A907-01",
                       "THREE ATTEMPTS. One initial C1 ignition attempt plus at most two retries = maximum three dwells "
                       "per start."),
        "XA9Q02": OD("A9.14", "XA9Q-02",
                     "THREE DWELLS / 360 s MAXIMUM BOOKING. One attempt + two retries, each capped at 120 s."),
        "OQA91003": OD("A9.14", "OQ-A910-03",
                       "Only when the record satisfies the declared ≥100 kSa/s, ≥20 kHz measurement bandwidth, "
                       "anti-alias filtering, synchronized channels, no saturation and total-bus-power reconstruction "
                       "requirements. Since every conformant sample is below 1500 W, its 1 ms mean cannot exceed 1500 W. "
                       "Conversely, `peak_sampled >=1500 W` does not fail the 1 ms gate; calculate the proper 1 ms "
                       "maximum."),
    }


# ======================================================================== fail-closed rule functions (owner rules)
def line_mev_value(allocation_kg=None, cbe_kg=None, floor_cbe_kg=None, equipment_margin=EQUIPMENT_MARGIN) -> dict:
    """A9.14 MQ-01: an owner allocation is already MEV (no row-57 margin is added to it); a CBE (or, before a CBE, a
    CBE-level evidence floor) is raised by the equipment margin to MEV and overrides the allocation when heavier. A CBE
    replaces the floor (MQ-04 / MQ-05: 'replace'). No input -> TBD (None), never 0."""
    if equipment_margin != EQUIPMENT_MARGIN:
        raise MassError("equipment margin other than the row-57 0.20 default needs a selected-part maturity record")
    cands = []
    if allocation_kg is not None:
        cands.append(("ALLOCATION_MEV", _kg(allocation_kg, "allocation")))
    if cbe_kg is not None:
        cands.append(("MEV_FROM_CBE", rk(_kg(cbe_kg, "CBE") * (1.0 + equipment_margin))))
    elif floor_cbe_kg is not None:
        cands.append(("MEV_PLANNING_FLOOR", rk(_kg(floor_cbe_kg, "evidence floor") * (1.0 + equipment_margin))))
    if not cands:
        return {"value_kg": None, "governs": None}
    g, v = max(cands, key=lambda c: c[1])
    return {"value_kg": v, "governs": g, "candidates": [{"basis": b, "kg": k} for b, k in cands]}


def system_margin(pre_margin_kg, fraction=SYSTEM_MARGIN, reserve_kg=0.0) -> dict:
    """A9.14 MQ-02: margin = 20 % of the CURRENT pre-system-margin sum; it replaces the 4 kg reserve (never both)."""
    if fraction != SYSTEM_MARGIN:
        raise MassError("the system margin is 0.20 (MQ-02); relaxing it to pass 40 kg is refused (MQ-10)")
    if reserve_kg not in (0, 0.0):
        raise MassError("the fixed 4 kg reserve is replaced by the 20 % system margin: adding both is refused (MQ-02)")
    p = _kg(pre_margin_kg, "pre-margin sum")
    return {"pre_margin_kg": rk(p), "system_margin_kg": rk(fraction * p), "total_kg": rk(p * (1.0 + fraction))}


def harness_row60(other_nominal_kg, fraction=HARNESS_FRACTION) -> float:
    """Row 60 / A9.14 MQ-06: harness = 5 % of nominal dry (incl. harness) = f/(1-f) x the other nominal dry lines."""
    if fraction != HARNESS_FRACTION:
        raise MassError("harness fraction is the row-60 0.05 until a routed harness exists")
    return rk(_kg(other_nominal_kg, "other nominal dry") * fraction / (1.0 - fraction))


def al_c1_allocation(c1_selected, c1_module_cbe_kg=None) -> dict:
    """A9.14 MPQ-01 option (c): AL-C1 (cathode module, shield/mount, C1-specific getter/filter) = selected C1 module
    CBE x 1.20 - only once C1 is actually selected; no fixed kg allocation now."""
    if not isinstance(c1_selected, bool):
        raise MassError("c1_selected must be a bool (no default)")
    if not c1_selected:
        if c1_module_cbe_kg is not None:
            raise MassError("no AL-C1 value before C1 is selected (MPQ-01: do not invent a fixed kg allocation)")
        return {"state": "NOT_ALLOCATED_C1_NOT_SELECTED", "kg": None}
    if c1_module_cbe_kg is None:
        return {"state": "TBD_SELECTED_C1_MODULE_CBE_REQUIRED", "kg": None}
    return {"state": "ALLOCATED_FROM_SELECTED_C1_CBE", "kg": rk(_kg(c1_module_cbe_kg, "C1 module CBE") * 1.2)}


def c1_xe_branch_booking(c1_selected, c1_requires_xe=None) -> dict:
    """A9.14 MPQ-01 + A9.15: a C1 Xe branch is booked inside AL-08 only for a selected C1 that requires Xe; before
    selection it is neither assumed nor excluded; a selected C1 that needs no Xe gets no branch."""
    if not isinstance(c1_selected, bool) or (c1_requires_xe is not None and not isinstance(c1_requires_xe, bool)):
        raise MassError("c1_selected must be a bool and c1_requires_xe a bool or None")
    if not c1_selected:
        if c1_requires_xe is not None:
            raise MassError("a C1 Xe requirement exists only for a selected C1 hardware (A9.15)")
        return {"state": "PENDING_C1_NOT_SELECTED", "in_AL08": None}
    if c1_requires_xe is None:
        return {"state": "TBD_FROM_SELECTED_C1_HARDWARE", "in_AL08": None}
    return {"state": "BOOKED_IN_AL08" if c1_requires_xe else "NO_C1_XE_BRANCH", "in_AL08": c1_requires_xe}


def xe_hardware_required(configuration: str, c1_selected=None) -> dict:
    """A9.15 / A9.14 XA9Q-07 + XV2Q-01: AL-08 and the Xe load are RFP-required in every flight configuration,
    independent of C1."""
    if configuration not in CONFIGS:
        raise MassError(f"unknown configuration {configuration!r}")
    if c1_selected is not None and not isinstance(c1_selected, bool):
        raise MassError("c1_selected must be a bool or None")
    return {"configuration": configuration, "AL-08": "REQUIRED_RFP_XE_CAPABILITY", "xe_load": "REQUIRED_RFP_XE_CAPABILITY"}


def assert_no_margin_relaxation(reading: dict) -> None:
    """A9.14 MQ-10 / MQ-01 / MQ-02: the only admitted closure reading is MEV allocations, 20 % system margin, no reserve,
    no second equipment margin, loaded Xe. Anything else (a relaxation or a retired v2 reading) is refused."""
    want = {"allocations": "MEV", "system_margin": SYSTEM_MARGIN, "reserve_kg": 0.0, "xe_case": "LOADED"}
    if reading != want:
        raise MassError(f"closure reading {reading!r} refused: only {want} (A9.14 MQ-01 / MQ-02 / MQ-09 / MQ-10)")


def closure_state(known_kg, reference_kg, strict: bool, all_resolved: bool) -> str:
    k, r = _kg(known_kg, "known mass"), _kg(reference_kg, "reference")
    if (k >= r) if strict else (k > r):
        return "DOES_NOT_CLOSE"
    return "CLOSES" if all_resolved else "NOT_EVALUABLE"


# ------------------------------------------------------------------------------------------------ lines
LINE_NAMES = {"AL-01": "intake/filter/duct", "AL-02": "compressor+drive", "AL-03": "plenum/feed",
              "AL-04": "Hall head+magnet (incl. anode heat-removal hardware, MPQ-02)",
              "AL-05": "ICP neutralizer (incl. collector/bias electrode, ICP isolation hardware)",
              "AL-06": "RF generator/matching (incl. RF feedthrough/coax/local match, RF protection/sensing electronics)",
              "AL-07": "Hall PPU (incl. collector/bias supply; C1 heater/keeper/control electronics if C1 selected)",
              "AL-08": "complete Xe storage/flow hardware: tank, regulator, valves, plumbing, mounting, thermal",
              "AL-09": "controls / electronics / valve drivers / flight sensors (MQ-06 split; harness excluded)",
              "AL-HAR": "harness (row-60 rule until a routed harness exists; MQ-06)",
              "AL-10": "structure/thermal (incl. ICP open-frame support/spacer, MPQ-02)",
              "AL-C1": "C1 module: cathode module, shield/mount, C1-specific getter/filter (MPQ-01 option c)"}
ORDER = ["AL-01", "AL-02", "AL-03", "AL-04", "AL-05", "AL-06", "AL-07", "AL-08", "AL-09", "AL-10", "AL-C1", "AL-HAR"]


def build_lines(v2: dict, s: dict) -> dict:
    out = {}
    for cfg in CONFIGS:
        rows = []
        v2l = {x["line"]: x for x in v2["lines"][cfg]}
        for lid in ORDER:
            if lid not in v2l and lid != "AL-HAR":
                continue
            src = v2l.get(lid, {})
            rec = {"line": lid, "name": LINE_NAMES[lid], "row54_allocation_kg": src.get("allocation_kg"),
                   "allocation_source": src.get("allocation_source", []),
                   "evidence_floor_cbe_kg": src.get("evidence_floor_kg"), "floor_is_partial": src.get("floor_is_partial"),
                   "floor_constituents": src.get("floor_constituents", []), "floor_arithmetic": src.get("floor_arithmetic"),
                   "cbe_kg": None, "cbe_status": "TBD - no Vyovrinda design CBE exists yet",
                   "measured_kg": None, "owner_answers_applied": [cite(s["MQ01"])]}
            alloc, floor = rec["row54_allocation_kg"], rec["evidence_floor_cbe_kg"]
            if lid == "AL-09":
                rec["row54_combined_allocation_kg"] = alloc
                rec["row54_allocation_kg"] = None
                rec["allocation_status"] = ("TBD_OWNER (MPV3Q-01): row 54 gave 1.0 kg to controls+harness combined; "
                                            "MQ-06 splits the line but states no controls allocation; no number invented")
                rec["owner_answers_applied"] += [cite(s["MQ06"]), cite(s["MQ07"])]
                alloc = None
            if lid == "AL-HAR":
                rec.update(row54_allocation_kg=None, allocation_status="RULE: row 60 (5 % of nominal dry)",
                           evidence_floor_cbe_kg=None, floor_is_partial=None)
                rec["owner_answers_applied"] = [cite(s["MQ06"])]
                rec["value"] = {"value_kg": None, "governs": "HARNESS_POLICY_ROW60 (computed in the roll-up)"}
                rows.append(rec)
                continue
            if lid == "AL-C1":
                st = al_c1_allocation(False)
                rec.update(row54_allocation_kg=None, allocation_status=st["state"],
                           allocation_rule="AL-C1 = selected C1 module CBE x 1.20 when C1 is selected (MPQ-01)",
                           flight_integration="DEFERRED_UNTIL_C1_SELECTED (A9.14 OQ-A907-07 as amended by A9.15)",
                           v2_partial_floor_not_used="the v2 C1 analog floor (cathode unit 0.2 kg) is not an AL-C1 value: "
                                                     "no kg allocation before selection (MPQ-01)")
                rec["owner_answers_applied"] = [cite(s["MPQ01"]), cite(s["MPQ01_A"]), cite(s["OQA90707"]),
                                                cite(s["OQA90707_A"])]
                rec["value"] = {"value_kg": None, "governs": None}
                rows.append(rec)
                continue
            if lid in OWNER_MEV_FLOORS:
                key = {"AL-04": "MQ03", "AL-07": "MQ04", "AL-08": "MQ05"}[lid]
                rec["owner_answers_applied"].append(cite(s[key]))
                rec["owner_mev_planning_floor_kg"] = OWNER_MEV_FLOORS[lid]
                rec["rebase_rule"] = {
                    "AL-04": "AL-04 >= 1.20 x actual H-1 CBE once the design exists; 4.2048 kg is today's incomplete "
                             "planning floor (magnetic parts only; channel/anode/body/fasteners TBD)",
                    "AL-07": "6.0 kg MEV planning floor from the 5.0 kg lowest admissible PPU analog; replaced by the "
                             "selected flight PPU CBE x 1.20; never covered by system margin",
                    "AL-08": "complete Xe storage/flow hardware; 6.0528 kg MEV planning floor from the 5.044 kg "
                             "incomplete CBE floor; quotations/design replace it"}[lid]
            if lid == "AL-08":
                rec["owner_answers_applied"] += [cite(s["MQ07"]), cite(s["XA9Q07_A"]), cite(s["GOV"])]
                rec["c1_branch"] = c1_xe_branch_booking(False)
                rec["rfp_required"] = xe_hardware_required(cfg)
            if lid in ("AL-05", "AL-06"):
                rec["owner_answers_applied"] += [cite(s["MQ07"]), cite(s["MPQ02"])]
            if lid == "AL-06":
                rec["owner_answers_applied"].append(cite(s["OQA91005"]))
            if lid == "AL-07":
                rec["owner_answers_applied"] += [cite(s["MQ07"]), cite(s["MPQ01"])]
            if lid in ("AL-04", "AL-10"):
                rec["owner_answers_applied"].append(cite(s["MPQ02"]))
            v = line_mev_value(alloc, None, floor)
            if lid in OWNER_MEV_FLOORS and v["value_kg"] != OWNER_MEV_FLOORS[lid]:
                raise MassError(f"{lid}: MEV planning floor {v['value_kg']} != owner-stated {OWNER_MEV_FLOORS[lid]}")
            rec["value"] = v
            ev = {"ALLOCATION_MEV": "owner-allocation", "MEV_PLANNING_FLOOR": "inferred / model-derived floor x 1.20 "
                  "(analog / preliminary design; not a CBE)", "MEV_FROM_CBE": "CBE x 1.20", None: None}[v["governs"]]
            if v["governs"] == "MEV_PLANNING_FLOOR":
                classes = sorted({c["evidence_class"] for c in rec["floor_constituents"] if c.get("evidence_class")})
                ev = ("owner-stated MEV planning floor = 1.20 x analog / preliminary-design floor (not a CBE); "
                      "constituent classes " + ", ".join(classes))
            rec["evidence_class_of_value"] = ev
            rows.append(rec)
        out[cfg] = rows
    return out


def _unresolved(rec: dict) -> list:
    lid, v = rec["line"], rec["value"]
    if lid == "AL-HAR":
        return [f"{lid}: harness by the row-60 rule until a routed harness exists (not a CBE)"]
    if v["value_kg"] is None:
        why = rec.get("allocation_status", "no value")
        return [f"{lid}: NO VALUE - {why} (excluded from the known part)"]
    out = []
    if v["governs"] == "ALLOCATION_MEV":
        out.append(f"{lid}: owner MEV allocation, not a CBE (row 54; MQ-01)")
    elif v["governs"] == "MEV_PLANNING_FLOOR":
        out.append(f"{lid}: MEV planning floor from an analog / preliminary-design floor, not a CBE")
        if rec.get("floor_is_partial"):
            out.append(f"{lid}: floor INCOMPLETE - " + "; ".join(
                c["what"] for c in rec["floor_constituents"] if c.get("kg") is None))
    return out


def rollup(cfg: str, lines: list, xe_split: dict, refs: list) -> dict:
    assert_no_margin_relaxation({"allocations": "MEV", "system_margin": SYSTEM_MARGIN, "reserve_kg": 0.0,
                                 "xe_case": "LOADED"})
    parts, tbd, missing = [], [], []
    for rec in lines:
        if rec["line"] == "AL-HAR":
            continue
        v = rec["value"]["value_kg"]
        parts.append({"line": rec["line"], "used": rec["value"]["governs"], "kg": v})
        tbd += _unresolved(rec)
        if v is None:
            missing.append(rec["line"])
    nh = rk(sum(p["kg"] for p in parts if p["kg"] is not None))
    har = harness_row60(nh)
    parts.append({"line": "AL-HAR", "used": "HARNESS_POLICY_ROW60", "kg": har,
                  "partial": bool(missing), "note": "computed on the known non-harness part only" if missing else None})
    tbd += _unresolved(next(r for r in lines if r["line"] == "AL-HAR"))
    nominal = rk(nh + har)
    sm = system_margin(nominal)
    dry = sm["total_kg"]
    out = {"configuration": cfg, "reading": "MEV_LEVEL_EVIDENCE_BASED (the single owner reading)",
           "parts": parts, "nonharness_known_kg": nh, "harness_kg": har, "nominal_dry_known_kg": nominal,
           "system_margin_kg": sm["system_margin_kg"], "reserve_kg": 0.0, "dry_known_kg": dry,
           "lines_without_value": missing, "tbd": tbd, "all_terms_resolved": False, "wet": []}
    for case_kg, sp in sorted(xe_split.items()):
        if sp["loaded_kg"] != case_kg:
            raise MassError("Xe v3 case is not LOADED (the residual would be counted twice)")
        wet = rk(dry + sp["loaded_kg"])
        for name, ref, strict in refs:
            st = closure_state(wet, ref, strict, all_resolved=False)
            row = {"xe_case_kg": case_kg, "xe_loaded_kg": sp["loaded_kg"], "residual_inside_case_kg": sp["residual_kg"],
                   "residual_added_on_top_kg": 0.0, "wet_known_kg": wet, "reference": name, "reference_kg": ref,
                   "comparator": "<" if strict else "<=", "state": st}
            if st == "DOES_NOT_CLOSE":
                nh_max = (ref - sp["loaded_kg"]) * (1.0 - HARNESS_FRACTION) / (1.0 + SYSTEM_MARGIN)
                row["exceedance_kg"] = rk(wet - ref)
                row["redesign_need"] = {
                    "nonharness_nominal_reduction_kg_at_least": rk(nh - nh_max),
                    "nonharness_nominal_max_kg": rk(nh_max),
                    "rule": "MQ-10: reduce actual subsystem CBE (redesign, integration, lighter qualified parts); the "
                            "margin reading is not relaxed; the lines without a value add to this need when known"}
            else:
                row["margin_to_reference_kg"] = rk(ref - wet)
            out["wet"].append(row)
    return out


def budget_reference(v2: dict, xe_split: dict, refs: list) -> dict:
    items = {i["id"]: i for i in v2["items"]}
    alloc = [items[f"MA-AL-{n:02d}"]["value"] for n in range(1, 11)]
    total = rk(sum(alloc))
    sm = system_margin(total)
    if (sm["pre_margin_kg"], sm["system_margin_kg"], sm["total_kg"]) != OWNER_MQ02_CHECK:
        raise MassError(f"MQ-02 arithmetic {sm} != owner-stated {OWNER_MQ02_CHECK}")
    wet = [{"xe_case_kg": c, "wet_budget_kg": rk(sm["total_kg"] + sp["loaded_kg"]),
            "vs": {n: rk(r - (sm["total_kg"] + sp["loaded_kg"])) for n, r, _s in refs}} for c, sp in sorted(xe_split.items())]
    return {"label": "OWNER BUDGET REFERENCE (row-54 line allocations, MEV-level, summed as stated by the owner; not "
                     "evidence; not a closure): 20 % system margin replaces the 4 kg reserve (A9.14 MQ-02)",
            "row54_allocation_sum_kg": sm["pre_margin_kg"], "system_margin_kg": sm["system_margin_kg"],
            "dry_budget_kg": sm["total_kg"], "retired": {"MA-RES 4 kg reserve": "replaced (MQ-02)",
                                                       "MA-TGT 28 kg dry target": "recomputed 28.8 kg (MQ-02)"},
            "recalculation_rule": "recompute 20 % of the current pre-margin sum whenever line allocations change "
                                  "(the evidence-based roll-ups below do exactly this)",
            "wet_budget_by_loaded_case": wet}


# ------------------------------------------------------------------------------------------------ BOM
MAPPINGS = {
    # item: (line, decision key, mapping text)
    "A9B-18": ("AL-05", "MQ07", "collector/bias electrode -> AL-05"),
    "A9B-22": ("AL-07", "MQ07", "collector/bias supply -> AL-07"),
    "A9B-21": ("AL-06", "MQ07", "RF feedthrough/coax/local match -> AL-06"),
    "A9B-20": ("AL-06", "OQA91005", "local matching hardware -> AL-06 (not AL-05)"),
    "A9B-26": ("AL-09", "MQ07", "valve drivers -> controls portion of AL-09"),
    "A9B-29": ("AL-09", "MQ07", "flight sensors -> controls portion of AL-09"),
    "A9B-27": ("AL-09", "MQ06", "electronics/controls -> separate controls line AL-09"),
    "A9B-28": ("AL-HAR", "MQ06", "harness -> its own line (row-60 rule)"),
    "A9B-08": ("AL-08", "MQ07", "Xe mounting/thermal -> AL-08"),
    "A9B-12": ("AL-08", "MQ07", "Xe plumbing -> AL-08"),
    "MPV2-N01": ("AL-05", "MPQ02", "ICP isolation hardware -> AL-05"),
    "MPV2-N02": ("AL-06", "MPQ02", "RF protection/sensing electronics -> AL-06"),
    "MPV2-N03": ("AL-04", "MPQ02", "anode heat-removal hardware -> AL-04"),
    "MPV2-N04": ("AL-10", "MPQ02", "ICP open-frame support/spacer -> AL-10"),
    "A9B-C01": ("AL-C1", "MPQ01", "cathode module -> AL-C1 (only when C1 is selected)"),
    "A9B-C02": ("AL-C1", "MPQ01", "shield/mount -> AL-C1 (only when C1 is selected)"),
    "A9B-C05": ("AL-C1", "MPQ01", "C1-specific getter/filter -> AL-C1 (only when C1 is selected)"),
    "A9B-C03": ("AL-07", "MPQ01", "C1 heater/keeper/control electronics -> AL-07"),
    "A9B-C04": ("AL-08", "MPQ01", "C1 Xe branch -> AL-08 (only for a selected C1 that requires Xe; A9.15)"),
}
XE_SCOPE_ITEMS = ("A9B-07", "A9B-09", "A9B-10", "A9B-11")       # MQ-05 complete Xe storage / flow hardware


def build_bom(v2: dict, s: dict) -> list:
    out = []
    for b in v2["bom"]:
        x = copy.deepcopy(b)
        x["v3_change"] = "carried unchanged from v2"
        x["owner_answers_applied"] = []
        iid = x["id"]
        if iid in MAPPINGS:
            line, key, txt = MAPPINGS[iid]
            x["allocation_line_v2"] = x["allocation_line"]
            x["allocation_mapping_v2"] = x["allocation_mapping"]
            x["allocation_line"] = line
            x["allocation_mapping"] = f"OWNER_MAPPING ({s[key]['key']} {s[key]['id']}: {txt})"
            x["owner_answers_applied"].append(cite(s[key]))
            x["v3_change"] = "allocation mapping decided by the owner"
            if key == "MPQ01" and iid == "A9B-C04":
                x["owner_answers_applied"].append(cite(s["MPQ01_A"]))
        if iid == "A9B-C07":
            x["allocation_line_v2"] = x["allocation_line"]
            x["allocation_mapping_v2"] = x["allocation_mapping"]
            x["allocation_line"] = "AL-09"
            x["allocation_mapping"] = ("RECORDER_MAPPING_FLAGGED: C1 telemetry = flight sensors -> controls portion of "
                                       "AL-09 by the A9.14 MQ-07 rule (MPQ-01 option c names no line for it)")
            x["owner_answers_applied"].append(cite(s["MQ07"]))
            x["v3_change"] = "mapped by the MQ-07 sensor rule (flagged)"
        if iid in XE_SCOPE_ITEMS:
            x["allocation_mapping"] = "OWNER_LINE (A9.14 MQ-05: complete Xe storage/flow hardware in AL-08)"
            x["owner_answers_applied"].append(cite(s["MQ05"]))
            x["v3_change"] = "scope confirmed by MQ-05"
        if x["group"] in ("xe", "xe_propellant"):
            x["rfp_required_both_configurations"] = True
            x["owner_answers_applied"] += [cite(s["XA9Q07_A"]), cite(s["XV2Q01_A"])]
            if x["v3_change"] == "carried unchanged from v2":
                x["v3_change"] = "RFP-required Xe capability in both configurations (A9.15)"
        if iid == "A9B-13":
            x["v3_status"] = ("LOADED Xe design cases 2 / 5 / 10 kg = mission usable + reserve + residual, one reading "
                              "for both ledgers (A9.14 XA9Q-01 / OQ-A910-01); v1_status is history")
            x["owner_answers_applied"] += [cite(s["XA9Q01"]), cite(s["OQA91001"])]
            x["v3_change"] = "LOADED reading decided"
        if iid == "A9B-14":
            x["name"] = "Xe residual (unusable) - a sub-line inside the LOADED case, never added again"
            x["owner_answers_applied"] += [cite(s["MQ09"]), cite(s["OQA91001"])]
            x["v3_change"] = "LOADED reading: residual inside the case"
        if x["group"] == "c1":
            x["configurations_v2"] = x["configurations"]
            x["configurations"] = {k: ("DEFERRED_UNTIL_C1_SELECTED (A9.14 OQ-A907-07 as amended by A9.15)"
                                       if v not in ("NOT_INSTALLED",) else v) for k, v in x["configurations"].items()}
            x["owner_answers_applied"] += [cite(s["OQA90707"]), cite(s["OQA90707_A"])]
            if iid == "A9B-C06":
                x["owner_answers_applied"].append(cite(s["MPQ01_A"]))
                x["v3_change"] = "flight C1 Xe term pending C1 selection (neither assumed nor excluded)"
            elif x["v3_change"] == "carried unchanged from v2":
                x["v3_change"] = "flight integration deferred until C1 is selected"
        out.append(x)
    return out


def ground_articles(v2: dict, s: dict) -> list:
    out = copy.deepcopy(v2["ground_article_only"])
    for g in out:
        if g["id"] == "GA-03":
            g["v3_rule"] = ("the matched sham reproduces the local-match parasitics: mass / stiffness / thermal / "
                            "service-line equivalent of the on-module local matching hardware as necessary for "
                            "force-system equivalence; values TBD until the local-match selection (no number invented)")
            g["owner_answers_applied"] = [cite(s["OQA91005"])]
    return out


# ------------------------------------------------------------------------------------------------ document
APPLIED = [
    ("MQ01", "single MEV reading: allocations carry their equipment margin; floors / CBE x 1.20 override when heavier "
             "(line_mev_value); CBE-level and owner-v0-literal readings retired"),
    ("MQ02", "20 % system margin of the current pre-margin sum replaces the 4 kg reserve (system_margin); 24 -> 4.8 -> "
             "28.8 kg checked"),
    ("MQ03", "AL-04 = max(3.0 allocation, 1.20 x 3.504 floor) = 4.2048 kg, incomplete (TBD constituents listed)"),
    ("MQ04", "AL-07 = 6.0 kg MEV planning floor; replaced by the flight PPU CBE x 1.20"),
    ("MQ05", "AL-08 = complete Xe storage/flow hardware, 6.0528 kg MEV planning floor"),
    ("MQ06", "AL-09 controls line (allocation TBD_OWNER, MPV3Q-01) + AL-HAR harness by the row-60 rule"),
    ("MQ07", "BOM mappings A9B-18/22/21/26/29/08/12 decided"),
    ("MQ09", "residual a sub-line inside the loaded case; residual_added_on_top_kg = 0 everywhere"),
    ("MQ10", "no margin relaxation (assert_no_margin_relaxation); exceedance and redesign need reported"),
    ("XA9Q01", "wet roll-ups use LOADED cases only"),
    ("OQA91001", "one reading with the Xe accounting v3 (imported loaded split, checked)"),
    ("MPQ01", "option (c): AL-C1 only for a selected C1 (no kg now); C1 electronics -> AL-07; C1 Xe branch -> AL-08"),
    ("MPQ01_A", "C1 Xe branch neither assumed nor excluded in advance (c1_xe_branch_booking)"),
    ("MPQ02", "BOM mappings MPV2-N01..N04 decided"),
    ("OQA90707", "C1 BOM items DEFERRED_UNTIL_C1_SELECTED in the C1 flight column"),
    ("OQA90707_A", "deferral reason restated (not because Xe is contingency-only)"),
    ("XA9Q07", "AL-08 and the Xe load are booked in hall_icp_neutralizer (no 'NO answer' alternative remains)"),
    ("XA9Q07_A", "as above, because the RFP requires it"),
    ("XV2Q01", "Xe-free reading NOT APPLICABLE"),
    ("XV2Q01_A", "as above (A9.15)"),
    ("GOV", "RFP governs propellant capability; Xe hardware independent of C1 (xe_hardware_required)"),
    ("OQA91005", "local match on AL-06; GA-03 matched sham reproduces the local-match parasitics"),
    ("OQA91003", "power gate peak_sampled rule implemented in the new helper peak_sampled_gate_a9_v3.py"),
    ("OQA91006", "open_register_status OQ-A910-06 OWNER_DECIDED: 600 W RF-path heat allocation kept temporarily (not a "
                 "rating / operating point / ICP-43 bound / delivered power), superseded by the P2-derived RF thermal "
                 "envelope (P2 supplies it, p3_a9_16_rules.rf_thermal_basis consumes it; A9.16 repair F5)"),
    ("OQA90701", "hall_c1_reference start step C-S4 reworded: <= 3 dwells (1 + 2 retries) x 120 s = 360 s maximum "
                 "booking (the retired v2 '120 s x 2 retries' shorthand kept as name_v2; A9.16 repair F10)"),
    ("XA9Q02", "as above: three dwells, each capped at 120 s, 360 s maximum booking (A9.16 repair F10)"),
]


def owner_answers_applied(s: dict) -> list:
    return [dict(s[k], how_applied=how) for k, how in APPLIED]


def import_xe(s: dict) -> dict:
    xe = _load(XE_V3)
    if xe.get("schema") != "xe_accounting_a9_v3":
        raise MassError("Xe accounting v3 missing or wrong schema (build order XE -> MP)")
    if xe["reading_axes_resolved"]["RA-CASE"]["v3"] != "LOADED":
        raise MassError("Xe accounting v3 does not carry the LOADED reading (OQ-A910-01: one reading for both ledgers)")
    split = {r["case_kg"]: r for r in xe["design_cases"]["loaded_split"]["rows"]}
    for c, r in split.items():
        if r["loaded_kg"] != c or r["reading"] != "LOADED":
            raise MassError(f"Xe v3 case {c} is not a LOADED case")
    if not any(i["id"] == "XV3-IF-01" for i in xe["interface_demands"]):
        raise MassError("Xe v3 interface XV3-IF-01 missing")
    return {"source": XE_V3, "interface": "XV3-IF-01", "reading": "LOADED",
            "loaded_split": [split[c] for c in sorted(split)],
            "rule": "M_loaded added once to dry; residual inside it (never added again; A9.14 MQ-09 / OQ-A910-01)",
            "_split": split}


def build_doc() -> dict:
    verify_pins()
    v2 = _load(V2["V2_JSON"][0])
    s = S()
    helper = _helper()
    xe = import_xe(s)
    split = xe.pop("_split")
    items = {i["id"]: i for i in v2["items"]}
    refs = [("HARD_40_WET", items["MP-01"]["value"], True), ("INTERNAL_34", items["MP-02"]["value"][0], False),
            ("INTERNAL_36", items["MP-02"]["value"][1], False)]
    lines = build_lines(v2, s)
    rolls = [rollup(cfg, lines[cfg], split, refs) for cfg in CONFIGS]
    for r in rolls:
        r["note"] = ("PRIMARY investigation configuration" if r["configuration"] == "hall_icp_neutralizer" else
                     "C1 reference / fallback: flight C1 integration DEFERRED_UNTIL_C1_SELECTED; AL-C1 and any C1 Xe "
                     "branch have no value; not comparable with the ICP column; no ranking")
    new_items = [
        {"id": "MPV3-01", "name": "system margin (fraction of the current pre-margin nominal dry)", "value": SYSTEM_MARGIN,
         "units": "1", "evidence_class": "owner-allocation", "source": [cite(s["MQ02"])],
         "status": "OWNER_DECIDED (replaces MA-RES 4 kg reserve)"},
        {"id": "MPV3-02", "name": "AL-04 MEV planning floor (incomplete; magnetic parts only)", "value": 4.2048,
         "units": "kg", "evidence_class": "owner-stated planning floor (1.20 x model-derived 3.504 kg)",
         "source": [cite(s["MQ03"])], "status": "PLANNING_FLOOR_NOT_CBE"},
        {"id": "MPV3-03", "name": "AL-07 MEV planning floor", "value": 6.0, "units": "kg",
         "evidence_class": "owner-stated planning floor (1.20 x inferred 5.0 kg analog)", "source": [cite(s["MQ04"])],
         "status": "PLANNING_FLOOR_NOT_CBE"},
        {"id": "MPV3-04", "name": "AL-08 MEV planning floor (complete Xe storage/flow hardware)", "value": 6.0528,
         "units": "kg", "evidence_class": "owner-stated planning floor (1.20 x inferred 5.044 kg)",
         "source": [cite(s["MQ05"])], "status": "PLANNING_FLOOR_NOT_CBE"},
        {"id": "MPV3-05", "name": "AL-C1 allocation", "value": None, "units": "kg", "evidence_class": None,
         "source": [cite(s["MPQ01"]), cite(s["MPQ01_A"])],
         "status": "NOT_ALLOCATED_C1_NOT_SELECTED (= selected C1 module CBE x 1.20 when selected)"},
        {"id": "MPV3-06", "name": "AL-09 controls / electronics / valve drivers allocation after the MQ-06 split",
         "value": None, "units": "kg", "evidence_class": None, "source": [cite(s["MQ06"])],
         "status": "TBD_OWNER (MPV3Q-01)"},
    ]
    v2_items = []
    for it in v2["items"]:
        x = copy.deepcopy(it)
        if x["id"] == "MA-RES":
            x["v3_status"] = "RETIRED: replaced by the 20 % system margin (A9.14 MQ-02); never added with it"
        elif x["id"] == "MA-TGT":
            x["v3_status"] = "HISTORICAL: owner's recomputed budget reference 28.8 kg (A9.14 MQ-02)"
        elif x["id"] == "MP-08":
            x["v3_status"] = "superseded by the Xe accounting v3 LOADED split (residual inside the case)"
        elif x["id"] == "MPV2-M03":
            x["v3_status"] = "decided: AL-C1 = selected C1 module CBE x 1.20, only when C1 is selected (MPQ-01)"
        v2_items.append(x)
    power = copy.deepcopy(v2["power"])
    # A9.16 repair F10: the C1 keeper-ignition step carried the retired v2 '120 s x 2 retries' reading; the owner set
    # three attempts (1 + 2 retries), each <= 120 s, 360 s maximum booking (A9.14 OQ-A907-01 / XA9Q-02)
    c_s4 = [st for st in power["configurations"]["hall_c1_reference"]["phases"]["startup"]["steps"]
            if st.get("step_id") == "C-S4"]
    if len(c_s4) != 1 or "120 s x 2 retries" not in c_s4[0]["name"]:
        raise MassError("v2 C-S4 keeper-ignition step text changed; review the A9.14 OQ-A907-01 / XA9Q-02 rewording")
    c_s4[0]["name_v2"] = c_s4[0]["name"]
    c_s4[0]["name"] = ("keeper ignition (pulsed 300-600 V class; <= 3 dwells (1 + 2 retries) x 120 s = 360 s maximum "
                       "booking, A9.14 OQ-A907-01 / XA9Q-02; row 93)")
    c_s4[0]["decisions"] = [cite(s["OQA90701"]), cite(s["XA9Q02"])]
    stale = "NOT_EVALUABLE for the gate (OQ-A910-03 OPEN, not implemented)"
    for cfg_p in power["configurations"].values():
        rule = cfg_p["phases"]["peak"]["rule"]
        if stale not in rule:
            raise MassError("v2 peak rule text changed; review the OQ-A910-03 update")
        cfg_p["phases"]["peak"]["rule_v2"] = rule
        cfg_p["phases"]["peak"]["rule"] = rule.replace(stale, "evaluated under A9.14 OQ-A910-03 by "
                                                       "power.peak_sampled_rule_v3 (one-sided sufficient PASS only on a "
                                                       "conformant record; >= 1500 W -> the 1 ms maximum decides)")
    power["peak_sampled_rule_v3"] = {
        "decision": cite(s["OQA91003"]), "quote": s["OQA91003"]["quote"], "helper": HELPER_REL,
        "helper_sha256": _sha(HELPER_REL), "rule": helper.RULE,
        "bus_boundary_module": "unchanged (import only); its PEAK_SAMPLED_RULE stays the A9.1 wording - this artifact "
                               "evaluates peak_sampled records through the helper",
        "conformance_keys": list(helper.RECORD_KEYS),
        "state_today": "NOT_EVALUABLE: no measured total-bus record exists (every load TBD); no PASS produced"}
    return {
        "schema": SCHEMA_ID, "id": SCHEMA_ID, "lane": "a9_16_step1_mass_power_xe_v3",
        "directive": "owner instruction 2026-10-01 'continue implementing them sequentially' (A9.16 step 1)",
        "title": "A9 mass + power integration v3: one MEV reading, 20 % system margin, rebased AL-04 / AL-07 / AL-08, "
                 "controls / harness split, decided mappings, LOADED Xe, evidence-based dry / wet vs 40 kg",
        "status": "DRAFT_DECISIONS_APPLIED_PENDING_INTEGRATION_VERIFICATION", "a9_status": v2["a9_status"],
        "date": DATE, "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_REL}/{MD_NAME}", "test": TEST_REL,
        "revision_of": {"path": V2["V2_JSON"][0], "sha256": V2["V2_JSON"][1], "md": V2["V2_MD"][0],
                        "md_sha256": V2["V2_MD"][1], "builder": V2["V2_BUILDER"][0],
                        "builder_sha256": V2["V2_BUILDER"][1], "rule": "v2 immutable history: read as data, never edited"},
        "configurations": v2["configurations"],
        "value_columns": v2["value_columns"],
        "what_this_is_not": [
            "not a performance prediction (no thrust, discharge current, electron current, efficiency or plasma state)",
            "not an architecture selection: no winner between hall_icp_neutralizer and hall_c1_reference",
            "not a CBE: every value is an owner MEV allocation, an owner-stated MEV planning floor or TBD",
            "not a margin relaxation: the 40 kg exceedance is reported with the redesign need (MQ-10)",
            "not a thermal, RF-rating, anode or ICP-capacity PASS; not a P_bus demonstration (every load TBD)"],
        "statuses": v2["statuses"],
        "pins": {"v2": [{"key": k, "path": p, "sha256": h} for k, (p, h) in V2.items()],
                 "decisions": [{"key": k, "json": d["json"], "json_sha256": d["json_sha256"], "md": d["md"],
                                "md_sha256": d["md_sha256"]} for k, d in DECISIONS.items()],
                 "bus_boundary_module": {"path": BUS_MODULE[0], "sha256": BUS_MODULE[1], "use": "import only"}},
        "cross_lane": {"XE": {"path": XE_V3, "ids_checked": ["design_cases.loaded_split", "XV3-IF-01",
                                                             "reading_axes_resolved.RA-CASE"],
                              "sha_pinned": False, "build_order": "XE -> MP"}},
        "margin_convention": {
            "reading": "MEV_LEVEL (A9.14 MQ-01) - the single governing reading",
            "retired_v2_readings": ["OWNER_V0_LITERAL (4 kg reserve)", "MQ01_CBE_LEVEL (second row-57 margin)",
                                    "USABLE_MQ09 (residual on top)"],
            "line_value": "max(owner MEV allocation, 1.20 x CBE or - before a CBE - 1.20 x evidence floor)",
            "harness": "AL-HAR = 0.05/0.95 x the other nominal dry lines (row 60; MQ-06)",
            "system_margin": "0.20 x the current nominal dry (MQ-02); no reserve",
            "wet": "dry + LOADED Xe case (residual inside; MQ-09 / OQ-A910-01)",
            "closure_rule": "CLOSES only when every term is resolved (CBE / measured) and the reference is met; "
                            "DOES_NOT_CLOSE when the known part already reaches the reference; otherwise NOT_EVALUABLE"},
        "propellant_policy": {"governing_rule": _decision("A9.15")[0]["governing_rule"], "source": cite(s["GOV"]),
                              "per_configuration": [xe_hardware_required(c) for c in CONFIGS],
                              "c1_xe_branch_now": c1_xe_branch_booking(False), "al_c1_now": al_c1_allocation(False)},
        "items_v2": v2_items, "items_v3": new_items,
        "lines": lines,
        "budget_reference": budget_reference(v2, split, refs),
        "rollups": rolls,
        "xe_v3_import": xe,
        "bom": build_bom(v2, s),
        "ground_article_only": ground_articles(v2, s),
        "coil_mass_correction": v2["coil_mass_correction"],
        "power": power,
        "open_register_status": {
            "MQ-01": "OWNER_DECIDED", "MQ-02": "OWNER_DECIDED", "MQ-03": "OWNER_DECIDED", "MQ-04": "OWNER_DECIDED",
            "MQ-05": "OWNER_DECIDED", "MQ-06": "OWNER_DECIDED", "MQ-07": "OWNER_DECIDED",
            "MQ-08": "DERIVED (owner_questions_state_v4; H2-7 5.044 kg arithmetic governs, unchanged)",
            "MQ-09": "OWNER_DECIDED", "MQ-10": "OWNER_DECIDED", "XA9Q-01": "OWNER_DECIDED",
            "XA9Q-07": "OWNER_DECIDED (amended by A9.15)", "XV2Q-01": "NOT_APPLICABLE", "MPQ-01": "OWNER_DECIDED "
            "(amended by A9.15)", "MPQ-02": "OWNER_DECIDED", "OQ-A910-01": "OWNER_DECIDED",
            "OQ-A910-03": "OWNER_DECIDED", "OQ-A910-05": "OWNER_DECIDED",
            "OQ-A910-06": "OWNER_DECIDED (A9.12 S5.8 YES_600W_TEMPORARY: 600 W = 500 W x 1.20 kept temporarily as the "
                          "RF-path heat allocation - not a rating / flight point / ICP-43 bound / delivered power - then "
                          "superseded by the P2-derived RF thermal envelope; p3_a9_16_rules.rf_thermal_basis)",
            "MPV3Q-01": "OPEN"},
        "open_owner_questions": [
            {"id": "MPV3Q-01", "question": "MQ-06 splits row-54 'controls/harness 1.0 kg' into a harness line (row-60 "
                                          "rule) and a controls / electronics / valve-driver allocation / CBE line. Which "
                                          "allocation does the controls line carry until its CBE exists (e.g. keep the "
                                          "1.0 kg row-54 figure for controls alone, or another value)?",
             "proposed": "none - owner call; v3 books no controls value (the line is listed as a missing term in every "
                         "evidence-based roll-up)", "needed_by": "LOCK-1", "status": "OPEN"}],
        "recorder_flags": [
            "A9B-C07 (C1 keeper/heater flight telemetry) mapped to the controls portion of AL-09 by the MQ-07 sensor rule; "
            "MPQ-01 option (c) names no line for it",
            "the AL-08 planning floor is the owner's 5.044 kg H2-7 figure (two-branch valve set); whether it already "
            "covers a selected C1 Xe branch is decided when C1 is selected (not added twice now)",
            "INTERNAL_34 / INTERNAL_36 (row 53) carried as internal references beside the 40 kg hard gate"],
        "owner_answers_applied": owner_answers_applied(s),
        "compliance": {
            "no_new_numbers": "every number is owner-given (row / decision), copied from pinned v2, or deterministic "
                              "arithmetic on those; owner-stated floors are checked against that arithmetic",
            "no_margin_relaxation": "assert_no_margin_relaxation refuses any other closure reading (MQ-10)",
            "residual_once": "LOADED cases: residual inside, residual_added_on_top_kg = 0",
            "no_pass": "no PASS for thermal, RF ratings, anode, ICP capacity; the power gate stays NOT_EVALUABLE",
            "no_contact": "no supplier, lab or author contact",
            "pure": "not wired into archengine; no frozen data, goldens or production module touched"},
    }


# ------------------------------------------------------------------------------------------------ markdown
def _cell(v) -> str:
    if v is None:
        return "TBD"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).replace("|", "\\|").replace("\n", " ")


def _table(headers: list, rows: list) -> list:
    return ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] + \
        ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows] + [""]


def render_md(d: dict) -> str:
    L = ["# A9 mass + power integration v3 (A9.16 step 1)", "",
         f"Generated by `{d['generated_by']}` from `{LANE_REL}/{JSON_NAME}` (do not edit by hand; `--check` verifies). "
         f"Status `{d['status']}`; A9 status `{d['a9_status']}`. Base commit `{d['base_commit']}`. Revision of "
         f"`{d['revision_of']['path']}` (sha256 `{d['revision_of']['sha256']}`, immutable). Test `{d['test']}`.", "",
         "**What this is not:** " + "; ".join(d["what_this_is_not"]) + ".", "",
         "## Margin convention (one reading)", ""]
    L += [f"* **{k}**: {v}" for k, v in d["margin_convention"].items() if not isinstance(v, list)]
    L += [f"* **retired v2 readings**: {', '.join(d['margin_convention']['retired_v2_readings'])}", "",
          "## RFP-compliant propellant policy (A9.15)", "", "> " + d["propellant_policy"]["governing_rule"], "",
          f"AL-08 and the Xe load are `REQUIRED_RFP_XE_CAPABILITY` in both configurations; C1 Xe branch now: "
          f"`{d['propellant_policy']['c1_xe_branch_now']['state']}`; AL-C1 now: `{d['propellant_policy']['al_c1_now']['state']}`.",
          "", "## Owner budget reference (MQ-02)", ""]
    b = d["budget_reference"]
    L += [b["label"] + ".", "",
          f"row-54 sum {b['row54_allocation_sum_kg']:g} kg -> 20 % system margin {b['system_margin_kg']:g} kg -> dry "
          f"budget {b['dry_budget_kg']:g} kg. {b['recalculation_rule']}.", ""]
    L += _table(["loaded Xe kg", "wet budget kg", "reference minus wet budget (negative = over)"],
                [[w["xe_case_kg"], w["wet_budget_kg"], w["vs"]] for w in b["wet_budget_by_loaded_case"]])
    for cfg in CONFIGS:
        L += [f"## Lines - `{cfg}`", ""]
        L += _table(["line", "name", "row-54 alloc", "evidence floor (CBE level)", "value used (MEV)", "governs",
                     "evidence class"],
                    [[r["line"], r["name"], r["row54_allocation_kg"], r["evidence_floor_cbe_kg"], r["value"]["value_kg"],
                      r["value"]["governs"], r.get("evidence_class_of_value")] for r in d["lines"][cfg]])
    L += ["## Evidence-based dry / wet totals vs 40 kg (every TBD listed)", ""]
    for r in d["rollups"]:
        L += [f"### `{r['configuration']}`", "", r["note"] + ".", "",
              f"non-harness known {r['nonharness_known_kg']:g} kg + harness {r['harness_kg']:g} kg = nominal "
              f"{r['nominal_dry_known_kg']:g} kg; + 20 % system margin {r['system_margin_kg']:g} kg = **dry known "
              f"{r['dry_known_kg']:g} kg** (reserve 0). Lines without a value: {', '.join(r['lines_without_value'])}.", ""]
        L += _table(["loaded Xe kg", "residual inside", "wet known kg", "reference", "state", "exceedance kg",
                     "non-harness nominal reduction needed (kg, at least)"],
                    [[w["xe_case_kg"], w["residual_inside_case_kg"], w["wet_known_kg"],
                      f"{w['reference']} ({w['comparator']} {w['reference_kg']:g})", w["state"], w.get("exceedance_kg"),
                      (w.get("redesign_need") or {}).get("nonharness_nominal_reduction_kg_at_least")] for w in r["wet"]])
        L += ["TBD / unresolved terms:", ""] + [f"* {t}" for t in r["tbd"]] + [""]
    L += ["MQ-10: the margin reading is not relaxed; closure requires reducing actual subsystem CBE through redesign, "
          "integration or lighter qualified parts.", "", "## BOM allocation mappings decided in v3", ""]
    L += _table(["item", "name", "v2 line", "v3 line", "mapping"],
                [[x["id"], x["name"], x.get("allocation_line_v2"), x["allocation_line"], x["allocation_mapping"]]
                 for x in d["bom"] if "allocation_line_v2" in x])
    L += ["## Power gate: peak_sampled rule (A9.14 OQ-A910-03)", "", d["power"]["peak_sampled_rule_v3"]["rule"], "",
          f"Helper `{d['power']['peak_sampled_rule_v3']['helper']}`; {d['power']['peak_sampled_rule_v3']['bus_boundary_module']}. "
          f"Today: {d['power']['peak_sampled_rule_v3']['state_today']}.", "",
          "## Owner decisions applied", ""]
    L += _table(["decision", "id", "seq", "answer", "json sha256", "how applied"],
                [[r["key"], r["id"], r["sequenced_no"], r["answer"], r["json_sha256"], r["how_applied"]]
                 for r in d["owner_answers_applied"]])
    L += ["## Open questions and recorder flags", ""]
    L += [f"* {q['id']} ({q['status']}): {q['question']}" for q in d["open_owner_questions"]]
    L += [f"* flag: {f}" for f in d["recorder_flags"]] + [""]
    return "\n".join(L)


def render():
    doc = build_doc()
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n", render_md(doc))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify outputs are up to date; write nothing")
    args = ap.parse_args(argv)
    js, md = render()
    files = {HERE / JSON_NAME: js, HERE / MD_NAME: md}
    if args.check:
        bad = [p.name for p, t in files.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("STALE: " + ", ".join(bad))
            return 1
        print(f"OK: {len(files)} outputs reproduce")
        return 0
    for p, t in files.items():
        p.write_text(t, encoding="utf-8")
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
