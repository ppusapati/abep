#!/usr/bin/env python3
"""A9.16 mass + power integration v3 (mass_power_a9_v3) - a REVISION of the immutable mass / power v2.

Lane: A9.16 step 1, mass / power v3 + Xe accounting v3 (owner instruction 2026-10-01 'continue implementing them
sequentially'). Deterministic; standard library plus abep_sim.bus_boundary_a9_v2 (import only, through the new helper
peak_sampled_gate_a9_v3.py; A9.22 G8 stage 2 re-pointed it from the immutable v1 abep_sim.bus_boundary_a9, whose code
objects v2 runs unchanged); no Julia; well under a second. v2 (docs/budgets/mass_power_a9_v2/) is pinned by sha256 and
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

A9.19 / A9.20 layer (owner decisions 2026-10-01; the verbatim .md governs; A9.19 amends A9.15 on the ROLE of xenon):
  * the flight thruster architecture is ONE Hall accelerator + ONE RF/ICP electron-source / neutralizer (cathodeless /
    electrodeless) serving both atmospheric gases and xenon, TWO propellant supply modes with separate tanks / paths
    (ambient atmospheric primary; xenon CONTINGENCY / EMERGENCY, capability still RFP-required: RFP-P17-05 /
    RFP-P18-08), NO conventional hollow cathode -> the only flight configuration is hall_icp_neutralizer;
  * hall_c1_reference is no longer a candidate flight configuration: its column, AL-C1, the C1 electronics in AL-07 and
    the C1 Xe branch in AL-08 leave every flight roll-up; the pre-A9.19 C1 column is kept only as a labelled history
    record (retired_flight_configuration_history) with its old numbers;
  * C1 (heated Xe-fed LaB6) is a GROUND-ONLY laboratory reference (A9.20): BOM items A9B-C01..C07 become
    GROUND_ONLY_LAB_EQUIPMENT, never flight mass / power / Xe;
  * AL-08 (complete Xe storage / flow hardware) stays REQUIRED_RFP_XE_CAPABILITY with role CONTINGENCY_EMERGENCY;
  * the flight dry / wet roll-ups are numerically unchanged (the ICP column never carried C1 mass; checked against the
    pre-A9.19 committed values); the owner's 'check C1 mass' request is answered in c1_mass_check (no C1 kg was ever
    booked in a flight roll-up).

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
# A9.22 G8 stage 2: the flight bus boundary is bus_power_boundary_a9_v2 (hall_icp_neutralizer only; C1 ground-reference
# metadata). v1 stays pinned as immutable history: the carried v2 items cite its symbols and the retired C1 power
# configuration was evaluated under it.
BUS_MODULE = ("abep_sim/bus_boundary_a9_v2.py", "8964520ffb55d97eeb93c4b8cc45250026e0c6a0b3082ea58fcfd834ba661e26")
BUS_MODULE_V1 = ("abep_sim/bus_boundary_a9.py", "7b23dbd23d39bd576691f877c0b32b64c14e83e796b2da9a662f0639319c878a")
BUS_VERSION, BUS_VERSION_V1 = "bus_power_boundary_a9_v2", "bus_power_boundary_a9_v1"
BUS_STAGE2 = ("A9.22 G8 stage 2 (docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json "
              "G8_BUS_BOUNDARY): configuration taxonomy only, every value identical")
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
    "A9.19": {"json": "docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
              "json_sha256": "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
              "md": "docs/decisions/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md",
              "md_sha256": "d3eae1d65f9b679a8538ce4a7c701a40a3f5d3b07d72baae944b685256931749"},
    "A9.20": {"json": "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
              "json_sha256": "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
              "md": "docs/decisions/OD_2026_10_01_A9_20_C1_GROUND_ONLY_OWNER_DECISION.md",
              "md_sha256": "2b90a7a7f851ac571791ea6ba2fbafac8cf69a086a4a3724e2f66196b6b4d60c"},
    "A9.21": {"json": "docs/decisions/OD_2026_10_02_A9_21_open_items_and_hardware_programme_owner_decisions.json",
              "json_sha256": "78766d3adaaa6d38730ce82607a1cd0a03ae34186c911d4189e2fd9251db6549",
              "md": "docs/decisions/OD_2026_10_02_A9_21_OPEN_ITEMS_AND_HARDWARE_PROGRAMME_OWNER_DECISIONS.md",
              "md_sha256": "01f7796aa2ae03d7bc0319b191f004e0a1ba0214c2c982f34554ca52cf531440"},
}

CONFIGS = ("hall_icp_neutralizer",)                   # A9.19: the single flight configuration
RETIRED_FLIGHT_CONFIGS = ("hall_c1_reference",)       # A9.19: history column only; C1 ground-only (A9.20)
XE_ROLE = "CONTINGENCY_EMERGENCY"                     # A9.19 (capability RFP-required; role contingency / emergency)
# pre-A9.19 committed v3 roll-up values (docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json at f55abf6): the flight
# column must reproduce them exactly (the ICP column never carried C1 mass); the C1 column is reproduced as history
PRE_A919 = {"hall_icp_neutralizer": {"nonharness_known_kg": 32.2576, "dry_known_kg": 40.7464421},
            "hall_c1_reference": {"nonharness_known_kg": 28.7576, "dry_known_kg": 36.32538948}}
PRE_A919_COMMIT = "f55abf6222c12f07c81c09194df9051e3a297d10"
SYSTEM_MARGIN = 0.2              # A9.14 MQ-02 (owner-supplied; row 52)
EQUIPMENT_MARGIN = 0.2           # row 57 default for new / unselected parts; inside the MEV allocation (MQ-01)
HARNESS_FRACTION = 0.05          # row 60
OWNER_MEV_FLOORS = {"AL-04": 4.2048, "AL-07": 6.0, "AL-08": 6.0528}   # A9.14 MQ-03 / MQ-04 / MQ-05 (owner-stated)
OWNER_MQ02_CHECK = (24.0, 4.8, 28.8)                                  # A9.14 MQ-02 (owner-stated arithmetic)
# A9.21 AL08 (owner decision 2026-10-02): label only, no number changes
AL08_A921_STATUS = ("PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN (A9.21 KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08): "
                    "the 6.0528 kg AL-08 MEV planning floor is kept only as a provisional planning floor, not a frozen "
                    "allocation; AL-08 is formally re-based only after quotations split tank, regulator, valves, "
                    "plumbing, mounting/thermal and any C1-specific branch (the analog-derived figure may contain about "
                    "0.285 kg of C1 cathode-branch hardware)")
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
    bad = [f"{p} (expected {s[:12]}, got {_sha(p)[:12]})" for p, s in list(V2.values()) + [BUS_MODULE, BUS_MODULE_V1]
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
    elif key in ("A9.19", "A9.20"):
        # A9.19: a top-level decision field ('architecture', 'xenon_role') or an 'amends' key; A9.20: 'answer'
        if qid in js.get("amends", {}):
            ans = js["amends"][qid]
        elif qid in ("architecture", "xenon_role", "answer", "decision") and qid in js:
            ans = js[qid]
        else:
            raise MassError(f"{key} has no field / amendment {qid}")
        seq = None
    elif key == "A9.21":
        # A9.21: 'decisions' maps an id (e.g. 'AL08') to the owner's decision string
        if qid not in js.get("decisions", {}):
            raise MassError(f"A9.21 has no decision {qid}")
        seq, ans = None, js["decisions"][qid]
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
        # A9.19 / A9.20 (2026-10-01)
        "A919_ARCH": OD("A9.19", "architecture",
                        "One Hall accelerator. One RF/ICP electron-source/neutralizer. Two propellant supply modes. "
                        "No conventional hollow cathode."),
        "A919_XE": OD("A9.19", "xenon_role",
                      "xenon is not a parllel gas its just a contigency and emergency gas. so our thruster architecture "
                      "should be cathode/electrodless for both the atmosphere gases and xenon"),
        "A919_A915": OD("A9.19", "A9.15", "xenon is not a parllel gas its just a contigency and emergency gas."),
        "A919_C1": OD("A9.19", "A9.14 S8.33 MPQ-01 / S8.17 OQ-A907-07", "No conventional hollow cathode."),
        "A919_CF": OD("A9.19", "A9 C1 CONTROL_FALLBACK",
                      "our thruster architecture should be cathode/electrodless for both the atmosphere gases and "
                      "xenon check C1 mass"),
        "A920": OD("A9.20", "answer",
                   "Options offered: \"Ground-only reference (Recommended)\" / \"Remove C1 entirely\"."),
        "A920_V": OD("A9.20", "answer", "will go with your recommended"),
        # A9.21 (2026-10-02): AL-08 stays a provisional planning floor until quotations
        "A921_AL08": OD("A9.21", "AL08",
                        "Xe-hardware floor: wait for quotations before formally rebasing AL-08. Keep 6.05 kg only as a "
                        "provisional planning floor, not a frozen allocation."),
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


def al_c1_allocation(c1_flight=False, c1_module_cbe_kg=None) -> dict:
    """A9.19 / A9.20 (supersede A9.14 MPQ-01 option (c) for flight): the flight architecture has no conventional hollow
    cathode and C1 is a ground-only laboratory reference, never flight hardware: no AL-C1 exists in any flight roll-up.
    A flight C1 request or any C1 kg offered for a flight line is refused (ground C1 mass is measured per serial on the
    ground article GA-01, never flight mass)."""
    if not isinstance(c1_flight, bool):
        raise MassError("c1_flight must be a bool (no default)")
    if c1_flight:
        raise MassError("C1 is never flight hardware (A9.20); no hollow cathode in the flight architecture (A9.19)")
    if c1_module_cbe_kg is not None:
        raise MassError("no AL-C1 flight value: C1 mass is ground-only lab equipment (A9.20), never a flight line")
    return {"state": "NOT_IN_FLIGHT_ARCHITECTURE_A9_19_A9_20", "kg": None}


# registered official RFP clauses that carry the propellant policy (AG-15 registration; A9.16 repair RFP-06): read
# from the registration record, verbatim text copied, value token checked (fail closed)
RFP_REG_REL = "docs/requirements/rfp_official/rfp_registration_v1.json"
RFP_PROPELLANT_CLAUSES = (("RFP-P18-08", "Two separate propellant tanks for ambient air and xenon"),
                          ("RFP-P17-05", "capability to use Xe as propellant"),
                          ("RFP-P16-02", "Xenon Gas -> Valve -> Thruster"))


def rfp_propellant_clauses() -> dict:
    import json as _json
    from pathlib import Path as _Path
    reg = _json.loads((_Path(__file__).resolve().parents[3] / RFP_REG_REL).read_text(encoding="utf-8"))
    by = {c["id"]: c for c in reg["clauses"]}
    out = []
    for cid, tok in RFP_PROPELLANT_CLAUSES:
        c = by.get(cid)
        if c is None or tok not in c["text"]:
            raise RuntimeError(f"registered RFP clause {cid} missing or token {tok!r} absent")
        out.append({"clause_id": cid, "page": c["page"], "section": c["section"], "verbatim": c["text"]})
    return {"registration": RFP_REG_REL, "rfp_number": reg["document"]["rfp_number"],
            "pdf_sha256": reg["document"]["sha256"], "clauses": out,
            "citation_status": "REGISTERED_CLAUSE (AG-15 closure is the owner's; requirement_frozen stays false in "
                               "the RVM, RVM-10)",
            "note": "the A9.15 rules text 'owner-stated RFP content, pending RFP registration' is the owner's wording "
                    "as decided before the registration and is kept verbatim; the propellant content is now cited to "
                    "the registered clauses above"}


def c1_xe_branch_booking(c1_flight=False) -> dict:
    """A9.19 / A9.20 (supersede the A9.14 MPQ-01 + A9.15 pending C1 Xe branch): there is no C1 Xe branch in the flight
    AL-08; a flight C1 Xe branch is refused."""
    if not isinstance(c1_flight, bool):
        raise MassError("c1_flight must be a bool (no default)")
    if c1_flight:
        raise MassError("no flight C1 Xe branch: C1 is ground-only (A9.20), no hollow cathode in flight (A9.19)")
    return {"state": "NO_C1_XE_BRANCH_IN_FLIGHT (A9.19 / A9.20)", "in_AL08": False}


def xe_hardware_required(configuration: str) -> dict:
    """A9.15 / A9.14 XA9Q-07 + XV2Q-01, role amended by A9.19: AL-08 (complete Xe storage / flow hardware) and the Xe
    load are REQUIRED_RFP_XE_CAPABILITY in the single flight configuration, with role CONTINGENCY_EMERGENCY (not a
    parallel co-equal propellant). hall_c1_reference is no longer a flight configuration (A9.19) and is refused."""
    if configuration in RETIRED_FLIGHT_CONFIGS:
        raise MassError(f"{configuration} was retired as a flight configuration by A9.19 (C1 ground-only, A9.20)")
    if configuration not in CONFIGS:
        raise MassError(f"unknown configuration {configuration!r}")
    return {"configuration": configuration, "AL-08": "REQUIRED_RFP_XE_CAPABILITY", "xe_load": "REQUIRED_RFP_XE_CAPABILITY",
            "xe_role": XE_ROLE, "rfp_clauses": ["RFP-P17-05", "RFP-P18-08"],
            "role_note": "Xe = contingency / emergency supply mode with its own tank / path feeding the same Hall "
                         "accelerator and the same RF/ICP neutralizer (A9.19); capability required by the RFP"}


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
              "AL-07": "Hall PPU (incl. collector/bias supply; no C1 electronics - C1 is ground-only, A9.19 / A9.20)",
              "AL-08": "complete Xe storage/flow hardware: tank, regulator, valves, plumbing, mounting, thermal "
                       "(REQUIRED_RFP_XE_CAPABILITY; role CONTINGENCY_EMERGENCY, A9.19)",
              "AL-09": "controls / electronics / valve drivers / flight sensors (MQ-06 split; harness excluded)",
              "AL-HAR": "harness (row-60 rule until a routed harness exists; MQ-06)",
              "AL-10": "structure/thermal (incl. ICP open-frame support/spacer, MPQ-02)",
              "AL-C1": "C1 module: cathode module, shield/mount, C1-specific getter/filter (MPQ-01 option c; HISTORY - "
                       "retired from flight by A9.19 / A9.20)"}
HISTORY_LINE_NAMES = {"AL-07": "Hall PPU (incl. collector/bias supply; C1 heater/keeper/control electronics if C1 "
                               "selected) - pre-A9.19 history",
                      "AL-08": "complete Xe storage/flow hardware: tank, regulator, valves, plumbing, mounting, thermal "
                               "(pre-A9.19: C1 Xe branch inside if a selected C1 required Xe) - history"}
ORDER = ["AL-01", "AL-02", "AL-03", "AL-04", "AL-05", "AL-06", "AL-07", "AL-08", "AL-09", "AL-10", "AL-C1", "AL-HAR"]


def build_lines(v2: dict, s: dict, cfgs=CONFIGS, history: bool = False) -> dict:
    """Flight lines (CONFIGS) or, with history=True, the pre-A9.19 lines of a retired flight configuration (A9.19)."""
    if history and set(cfgs) - set(RETIRED_FLIGHT_CONFIGS):
        raise MassError("history lines only for a retired flight configuration")
    if not history and set(cfgs) - set(CONFIGS):
        raise MassError(f"{cfgs} contains a configuration that is not a flight configuration (A9.19)")
    out = {}
    for cfg in cfgs:
        rows = []
        v2l = {x["line"]: x for x in v2["lines"][cfg]}
        for lid in ORDER:
            if lid not in v2l and lid != "AL-HAR":
                continue
            src = v2l.get(lid, {})
            name = HISTORY_LINE_NAMES.get(lid, LINE_NAMES[lid]) if history else LINE_NAMES[lid]
            rec = {"line": lid, "name": name, "row54_allocation_kg": src.get("allocation_kg"),
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
                if not history:
                    raise MassError("AL-C1 in a flight configuration: C1 is never flight hardware (A9.19 / A9.20)")
                rec.update(row54_allocation_kg=None, allocation_status="NOT_ALLOCATED_C1_NOT_SELECTED (pre-A9.19 state)",
                           a9_19_status="RETIRED_FROM_FLIGHT: no AL-C1 in any flight roll-up (A9.19 no hollow "
                                        "cathode; A9.20 C1 ground-only lab reference)",
                           allocation_rule="AL-C1 = selected C1 module CBE x 1.20 when C1 is selected (MPQ-01)",
                           flight_integration="DEFERRED_UNTIL_C1_SELECTED (A9.14 OQ-A907-07 as amended by A9.15)",
                           v2_partial_floor_not_used="the v2 C1 analog floor (cathode unit 0.2 kg) is not an AL-C1 value: "
                                                     "no kg allocation before selection (MPQ-01)")
                rec["owner_answers_applied"] = [cite(s["MPQ01"]), cite(s["MPQ01_A"]), cite(s["OQA90707"]),
                                                cite(s["OQA90707_A"]), cite(s["A919_C1"]), cite(s["A920"])]
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
                if history:
                    rec["c1_branch"] = {"state": "PENDING_C1_NOT_SELECTED (pre-A9.19 history)", "in_AL08": None}
                    rec["rfp_required"] = {"configuration": cfg, "AL-08": "REQUIRED_RFP_XE_CAPABILITY (pre-A9.19 "
                                                                         "history column)"}
                else:
                    rec["owner_answers_applied"] += [cite(s["A919_XE"]), cite(s["A919_C1"]), cite(s["A920"])]
                    rec["owner_answers_applied"].append(cite(s["A921_AL08"]))
                    rec["a9_21_status"] = AL08_A921_STATUS
                    rec["c1_branch"] = c1_xe_branch_booking()
                    rec["rfp_required"] = xe_hardware_required(cfg)
                    rec["xe_role"] = XE_ROLE
            if lid in ("AL-05", "AL-06"):
                rec["owner_answers_applied"] += [cite(s["MQ07"]), cite(s["MPQ02"])]
            if lid == "AL-06":
                rec["owner_answers_applied"].append(cite(s["OQA91005"]))
            if lid == "AL-07":
                if history:
                    rec["owner_answers_applied"] += [cite(s["MQ07"]), cite(s["MPQ01"])]
                else:
                    rec["owner_answers_applied"] += [cite(s["MQ07"]), cite(s["A919_C1"]), cite(s["A920"])]
                    rec["c1_electronics"] = ("NOT_BOOKED: no C1 heater / keeper / control electronics in the flight "
                                             "AL-07 (A9.19 no hollow cathode; A9.20 C1 ground-only)")
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
}
# the pre-A9.19 flight mappings of the C1 items (A9.14 MPQ-01 option (c) / MQ-07 sensor rule): kept as history only;
# A9.19 / A9.20 make every C1 item GROUND_ONLY_LAB_EQUIPMENT (never flight mass / power / Xe)
PRE_A919_C1_MAPPINGS = {
    "A9B-C01": ("AL-C1", "MPQ01", "cathode module -> AL-C1 (only when C1 is selected)"),
    "A9B-C02": ("AL-C1", "MPQ01", "shield/mount -> AL-C1 (only when C1 is selected)"),
    "A9B-C05": ("AL-C1", "MPQ01", "C1-specific getter/filter -> AL-C1 (only when C1 is selected)"),
    "A9B-C03": ("AL-07", "MPQ01", "C1 heater/keeper/control electronics -> AL-07"),
    "A9B-C04": ("AL-08", "MPQ01", "C1 Xe branch -> AL-08 (only for a selected C1 that requires Xe; A9.15)"),
    "A9B-C06": ("-", "MPQ01", "C1 cathode Xe design term (wet term, pending C1 selection; A9.15)"),
    "A9B-C07": ("AL-09", "MQ07", "C1 telemetry = flight sensors -> controls portion of AL-09 (recorder mapping, "
                                 "flagged)"),
}
GROUND_ONLY = "GROUND_ONLY_LAB_EQUIPMENT"
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
        if iid in PRE_A919_C1_MAPPINGS:
            line, key, txt = PRE_A919_C1_MAPPINGS[iid]
            x["allocation_line_v2"] = x["allocation_line"]
            x["allocation_mapping_v2"] = x["allocation_mapping"]
            x["allocation_line_pre_a9_19"] = line
            x["allocation_mapping_pre_a9_19"] = f"{s[key]['key']} {s[key]['id']}: {txt}"
            x["allocation_line"] = GROUND_ONLY
            x["allocation_mapping"] = ("GROUND_ONLY_LAB_EQUIPMENT (A9.20): C1 is a ground-only laboratory reference "
                                       "(H-1 I_d,max,H1,Ar characterization per A9.10 S3.5; bench control in the "
                                       "C1-vs-ICP comparison); never flight hardware, never in the flight mass / power / "
                                       "Xe budgets; no conventional hollow cathode in the flight architecture (A9.19)")
            x["classification"] = GROUND_ONLY
            x["owner_answers_applied"] += [cite(s[key]), cite(s["A919_C1"]), cite(s["A920"])]
            x["v3_change"] = "A9.19 / A9.20: ground-only lab equipment (pre-A9.19 flight mapping kept as history)"
        if iid in XE_SCOPE_ITEMS:
            x["allocation_mapping"] = "OWNER_LINE (A9.14 MQ-05: complete Xe storage/flow hardware in AL-08)"
            x["owner_answers_applied"].append(cite(s["MQ05"]))
            x["v3_change"] = "scope confirmed by MQ-05"
        if x["group"] in ("xe", "xe_propellant"):
            x["rfp_required_flight_configuration"] = True
            x["xe_role"] = XE_ROLE
            x["owner_answers_applied"] += [cite(s["XA9Q07_A"]), cite(s["XV2Q01_A"]), cite(s["A919_XE"])]
            if x["v3_change"] == "carried unchanged from v2":
                x["v3_change"] = ("RFP-required Xe capability in the flight configuration (A9.15); role "
                                  "contingency / emergency (A9.19)")
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
            x["configurations_pre_a9_19"] = {k: ("DEFERRED_UNTIL_C1_SELECTED (A9.14 OQ-A907-07 as amended by A9.15)"
                                                 if v not in ("NOT_INSTALLED",) else v)
                                             for k, v in x["configurations"].items()}
            x["owner_answers_applied"] += [cite(s["OQA90707"]), cite(s["OQA90707_A"])]
            if iid == "A9B-C06":
                x["owner_answers_applied"].append(cite(s["MPQ01_A"]))
        # A9.19: the only flight configuration is hall_icp_neutralizer; the hall_c1_reference column is history
        x.setdefault("configurations_pre_a9_19", copy.deepcopy(x["configurations"]))
        flight = {"hall_icp_neutralizer": x["configurations"]["hall_icp_neutralizer"]}
        if x["group"] == "c1":
            flight["ground_lab_reference"] = GROUND_ONLY + " (A9.20)"
        x["configurations"] = flight
        out.append(x)
    return out


def ground_articles(v2: dict, s: dict) -> list:
    out = copy.deepcopy(v2["ground_article_only"])
    for g in out:
        if g["id"] == "GA-01":
            g["a9_20_rule"] = ("GROUND_ONLY laboratory reference (A9.20): registers I_d,max,H1,Ar on H-1 independently "
                               "of the ICP (A9.10 S3.5) and is the bench control in the C1-vs-ICP comparison; its "
                               "hardware (BOM A9B-C01..C07) is GROUND_ONLY_LAB_EQUIPMENT, measured per serial on the "
                               "ground article, never flight mass / power / Xe")
            g["owner_answers_applied"] = [cite(s["A920"]), cite(s["A919_C1"])]
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
    ("MPQ01", "pre-A9.19 option (c) (AL-C1 only for a selected C1; C1 electronics -> AL-07; C1 Xe branch -> AL-08) "
              "is SUPERSEDED for flight by A9.19 / A9.20: kept only in the history column and as "
              "allocation_line_pre_a9_19 of the ground-only C1 BOM items"),
    ("MPQ01_A", "pre-A9.19 'C1 Xe neither assumed nor excluded' superseded for flight by A9.19 / A9.20 "
                "(c1_xe_branch_booking now books no flight C1 Xe branch and refuses one)"),
    ("MPQ02", "BOM mappings MPV2-N01..N04 decided"),
    ("OQA90707", "pre-A9.19 'DEFERRED_UNTIL_C1_SELECTED' kept as configurations_pre_a9_19 history; superseded by "
                 "A9.19 / A9.20 (C1 never flight)"),
    ("OQA90707_A", "deferral reason restated pre-A9.19 (history); superseded by A9.19 / A9.20"),
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
    ("A919_ARCH", "single flight configuration hall_icp_neutralizer (one Hall + one RF/ICP neutralizer for both supply "
                  "modes; two supply modes with separate tanks / paths; no conventional hollow cathode): CONFIGS, "
                  "lines, rollups and power carry it only"),
    ("A919_XE", "AL-08 = REQUIRED_RFP_XE_CAPABILITY with role CONTINGENCY_EMERGENCY (xe_hardware_required); Xe BOM "
                "items carry xe_role; loaded cases 2 / 5 / 10 kg unchanged (Xe accounting v3)"),
    ("A919_A915", "A9.15 'Xe not a contingency' superseded on the ROLE of Xe (propellant_policy.xenon_role); the RFP "
                  "capability rule kept"),
    ("A919_C1", "AL-C1, the C1 electronics in AL-07 and the C1 Xe branch in AL-08 removed from every flight roll-up "
                "(al_c1_allocation / c1_xe_branch_booking refuse a flight C1)"),
    ("A919_CF", "hall_c1_reference retired as a flight configuration: its pre-A9.19 column, roll-up and power "
                "configuration kept only as labelled history (retired_flight_configuration_history); c1_mass_check "
                "answers 'check C1 mass'"),
    ("A920", "C1 = GROUND_ONLY laboratory reference: BOM A9B-C01..C07 -> GROUND_ONLY_LAB_EQUIPMENT; GA-01 a9_20_rule"),
    ("A920_V", "owner chose the recommended option (ground-only reference)"),
    ("A921_AL08", "AL-08 labelled a9_21_status PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN (6.0528 kg kept as a provisional "
                  "planning floor, not a frozen allocation; re-based only after quotations); no number changes"),
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
        r["note"] = ("FLIGHT configuration (A9.19: one Hall accelerator + one RF/ICP electron-source / neutralizer for "
                     "both supply modes; no conventional hollow cathode; Xe supply mode = contingency / emergency)")
    hist_lines = build_lines(v2, s, RETIRED_FLIGHT_CONFIGS, history=True)
    hist_rolls = [rollup(cfg, hist_lines[cfg], split, refs) for cfg in RETIRED_FLIGHT_CONFIGS]
    for r in hist_rolls:
        r["note"] = ("HISTORY - retired flight configuration (A9.19); pre-A9.19 note: C1 reference / fallback, flight C1 "
                     "integration DEFERRED_UNTIL_C1_SELECTED, AL-C1 and any C1 Xe branch without value; never a flight "
                     "roll-up now (C1 ground-only, A9.20)")
    for r in rolls + hist_rolls:
        want = PRE_A919[r["configuration"]]
        if (r["nonharness_known_kg"], r["dry_known_kg"]) != (want["nonharness_known_kg"], want["dry_known_kg"]):
            raise MassError(f"{r['configuration']}: roll-up moved vs the pre-A9.19 committed values {want} - A9.19 / "
                            "A9.20 remove C1 bookings only and must not move the flight numbers")
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
         "source": [cite(s["MPQ01"]), cite(s["MPQ01_A"]), cite(s["A919_C1"]), cite(s["A920"])],
         "status": "RETIRED_FROM_FLIGHT (A9.19 / A9.20): no AL-C1 in any flight roll-up; C1 is ground-only lab "
                   "equipment",
         "status_pre_a9_19": "NOT_ALLOCATED_C1_NOT_SELECTED (= selected C1 module CBE x 1.20 when selected)"},
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
            x["v3_status"] = ("RETIRED_FROM_FLIGHT (A9.19 / A9.20): no AL-C1 in the flight architecture; pre-A9.19 "
                              "decision 'AL-C1 = selected C1 module CBE x 1.20, only when C1 is selected (MPQ-01)' is "
                              "history")
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
    # A9.19: hall_c1_reference is no longer a flight configuration -> its power configuration is history only
    power["retired_flight_configuration_history"] = {
        "label": "HISTORY - hall_c1_reference retired as a flight configuration by A9.19 (C1 ground-only, A9.20); its "
                 "C1 slots (heater / keeper / common tie) are never flight P_bus loads",
        "configurations": {c: power["configurations"].pop(c) for c in RETIRED_FLIGHT_CONFIGS}}
    if set(power["configurations"]) != set(CONFIGS):
        raise MassError("power configurations must be the flight configuration only (A9.19)")
    # A9.22 G8 stage 2: the flight power configuration is evaluated under bus_power_boundary_a9_v2 (same numbers);
    # the retired C1 configuration stays on v1 (C1 is not a v2 configuration)
    if (power["boundary_version"], power["module"], power["module_sha256"]) != (BUS_VERSION_V1,) + BUS_MODULE_V1:
        raise MassError("v2 power block no longer names bus_power_boundary_a9_v1; review the A9.22 G8 re-point")
    power["boundary_version"], power["module"], power["module_sha256"] = (BUS_VERSION,) + BUS_MODULE
    power["boundary_repointed"] = {"rule": BUS_STAGE2, "carried_from_v2": {
        "boundary_version": BUS_VERSION_V1, "module": BUS_MODULE_V1[0], "module_sha256": BUS_MODULE_V1[1]}}
    power["retired_flight_configuration_history"]["boundary_version"] = BUS_VERSION_V1
    power["retired_flight_configuration_history"]["module"] = BUS_MODULE_V1[0]
    power["retired_flight_configuration_history"]["module_sha256"] = BUS_MODULE_V1[1]
    for cfg_p in power["configurations"].values():
        st = cfg_p["phases"]["startup"]
        if st["template"] != "bus_boundary_a9.SEQUENCE_TEMPLATES (PROPOSED, row 112)":
            raise MassError("v2 start-up template citation changed; review the A9.22 G8 re-point")
        st["template"] = "bus_boundary_a9_v2.SEQUENCE_TEMPLATES (PROPOSED, row 112)"
    power["peak_sampled_rule_v3"] = {
        "decision": cite(s["OQA91003"]), "quote": s["OQA91003"]["quote"], "helper": HELPER_REL,
        "helper_sha256": _sha(HELPER_REL), "rule": helper.RULE,
        "bus_boundary_module": "abep_sim/bus_boundary_a9_v2.py unchanged (import only; v2 runs the immutable v1 code "
                               "objects); its PEAK_SAMPLED_RULE stays the A9.1 wording - this artifact evaluates "
                               "peak_sampled records through the helper",
        "conformance_keys": list(helper.RECORD_KEYS),
        "state_today": "NOT_EVALUABLE: no measured total-bus record exists (every load TBD); no PASS produced"}
    return {
        "schema": SCHEMA_ID, "id": SCHEMA_ID, "lane": "a9_16_step1_mass_power_xe_v3",
        "directive": "owner instruction 2026-10-01 'continue implementing them sequentially' (A9.16 step 1)",
        "title": "A9 mass + power integration v3: one MEV reading, 20 % system margin, rebased AL-04 / AL-07 / AL-08, "
                 "controls / harness split, decided mappings, LOADED Xe, evidence-based dry / wet vs 40 kg; A9.19 / "
                 "A9.20: single flight configuration hall_icp_neutralizer, Xe contingency / emergency, C1 ground-only",
        "status": "DRAFT_DECISIONS_APPLIED_PENDING_INTEGRATION_VERIFICATION", "a9_status": v2["a9_status"],
        "date": DATE, "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_REL}/{MD_NAME}", "test": TEST_REL,
        "revision_of": {"path": V2["V2_JSON"][0], "sha256": V2["V2_JSON"][1], "md": V2["V2_MD"][0],
                        "md_sha256": V2["V2_MD"][1], "builder": V2["V2_BUILDER"][0],
                        "builder_sha256": V2["V2_BUILDER"][1], "rule": "v2 immutable history: read as data, never edited"},
        "configurations": {
            "hall_icp_neutralizer": "FLIGHT CONFIGURATION (A9.19: one Hall accelerator + one RF/ICP electron-source / "
                                    "neutralizer, cathodeless / electrodeless, for both atmospheric gases and xenon; two "
                                    "supply modes with separate tanks / paths - ambient atmospheric primary, xenon "
                                    "contingency / emergency; no conventional hollow cathode). A9 investigation status "
                                    "unchanged: " + v2["configurations"]["hall_icp_neutralizer"],
            "hall_c1_reference": "RETIRED as a candidate flight configuration by A9.19; C1 is a GROUND-ONLY laboratory "
                                 "reference (A9.20: H-1 I_d,max,H1,Ar characterization per A9.10 S3.5; bench control in "
                                 "the C1-vs-ICP comparison); never flight hardware, never in the flight mass / power / Xe "
                                 "budgets; its pre-A9.19 column is kept only as labelled history "
                                 "(retired_flight_configuration_history)"},
        "configurations_pre_a9_19": v2["configurations"],
        "value_columns": v2["value_columns"],
        "what_this_is_not": [
            "not a performance prediction (no thrust, discharge current, electron current, efficiency or plasma state)",
            "not an architecture ranking: the single flight configuration hall_icp_neutralizer is the owner's A9.19 "
            "decision, not a result of this budget; the retired hall_c1_reference column is history, never compared "
            "as a flight candidate",
            "not a CBE: every value is an owner MEV allocation, an owner-stated MEV planning floor or TBD",
            "not a margin relaxation: the 40 kg exceedance is reported with the redesign need (MQ-10)",
            "not a thermal, RF-rating, anode or ICP-capacity PASS; not a P_bus demonstration (every load TBD)"],
        "statuses": dict(v2["statuses"], a9_19_20_supersessions={
            "C1 conventional reference": "GROUND_ONLY_LAB_EQUIPMENT (A9.20; the carried A9.2 'CONTROL_FALLBACK' is "
                                         "superseded: C1 is never flight hardware and no hall_c1_reference flight "
                                         "configuration exists after A9.19)"}),
        "pins": {"v2": [{"key": k, "path": p, "sha256": h} for k, (p, h) in V2.items()],
                 "decisions": [{"key": k, "json": d["json"], "json_sha256": d["json_sha256"], "md": d["md"],
                                "md_sha256": d["md_sha256"]} for k, d in DECISIONS.items()],
                 "bus_boundary_module": {"path": BUS_MODULE[0], "sha256": BUS_MODULE[1], "use": "import only",
                                         "boundary_version": BUS_VERSION, "repointed": BUS_STAGE2},
                 "bus_boundary_module_v1_history": {
                     "path": BUS_MODULE_V1[0], "sha256": BUS_MODULE_V1[1], "boundary_version": BUS_VERSION_V1,
                     "use": "immutable history: cited by the carried v2 items and by the retired C1 power "
                            "configuration (C1 is not a v2 configuration)"}},
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
                              "rfp_clauses": rfp_propellant_clauses(),
                              "architecture": dict(_decision("A9.19")[0]["architecture"], source=cite(s["A919_ARCH"])),
                              "xenon_role": {"role": XE_ROLE, "decision": _decision("A9.19")[0]["xenon_role"],
                                             "source": cite(s["A919_XE"]),
                                             "amends_a9_15": _decision("A9.19")[0]["amends"]["A9.15"],
                                             "rfp_clauses": ["RFP-P17-05", "RFP-P18-08"],
                                             "al_08": "REQUIRED_RFP_XE_CAPABILITY, role CONTINGENCY_EMERGENCY"},
                              "icp_feed_gas_baseline": "A9.1 unchanged: G-REUSE primary (m_Xe,ICP = 0), G-XE declared "
                                                       "variant",
                              "per_configuration": [xe_hardware_required(c) for c in CONFIGS],
                              "c1_xe_branch_now": c1_xe_branch_booking(), "al_c1_now": al_c1_allocation()},
        "items_v2": v2_items, "items_v3": new_items,
        "lines": lines,
        "budget_reference": budget_reference(v2, split, refs),
        "rollups": rolls,
        "flight_rollup_vs_40kg": [
            {"configuration": r["configuration"], "dry_known_kg": r["dry_known_kg"],
             "wet_known_kg_by_loaded_case": {str(w["xe_case_kg"]): w["wet_known_kg"] for w in r["wet"]
                                             if w["reference"] == "HARD_40_WET"},
             "hard_40_wet_state_by_loaded_case": {str(w["xe_case_kg"]): w["state"] for w in r["wet"]
                                                  if w["reference"] == "HARD_40_WET"},
             "numerically_unchanged_vs_pre_a9_19": True,
             "basis": f"checked against the pre-A9.19 committed v3 values (commit {PRE_A919_COMMIT}): the ICP column "
                      "never carried C1 mass, so removing the C1 bookings moves no flight number"} for r in rolls],
        "retired_flight_configuration_history": {
            "label": "HISTORY - hall_c1_reference was retired as a candidate FLIGHT configuration by A9.19 (no "
                     "conventional hollow cathode in the flight architecture); C1 is a ground-only laboratory reference "
                     "(A9.20). The pre-A9.19 C1 column and its roll-up are kept for traceability only: never a flight "
                     "roll-up, never compared or ranked against the flight configuration",
            "by": [cite(s["A919_C1"]), cite(s["A919_CF"]), cite(s["A920"])],
            "pre_a9_19_commit": PRE_A919_COMMIT,
            "lines": hist_lines, "rollups": hist_rolls},
        "c1_mass_check": {
            "owner_request": _decision("A9.19")[0]["owner_request"],
            "source": cite(s["A919_CF"]),
            "flight": "no C1 kg was ever booked in a flight roll-up: AL-C1 had no value (A9.14 MPQ-01: no kg before "
                      "selection) and the hall_icp_neutralizer column never contained C1 lines; after A9.19 / A9.20 "
                      "there is no C1 line, no C1 electronics in AL-07 and no C1 Xe branch booked as a line in AL-08 "
                      "in the flight architecture; however, the owner's AL-08 planning floor (H2-7, 5.044 kg, MQ-05) "
                      "kept in the flight roll-up may still embed a two-branch valve set (0.57 kg) that v2 describes "
                      "as including the C1 cathode Xe branch (see recorder_flags, owner observation); no number "
                      "changes",
            "v2_c1_evidence_floor_kg": next(x["evidence_floor_kg"] for x in v2["lines"]["hall_c1_reference"]
                                            if x["line"] == "AL-C1"),
            "v2_c1_floor_is_partial": next(x["floor_is_partial"] for x in v2["lines"]["hall_c1_reference"]
                                           if x["line"] == "AL-C1"),
            "v2_c1_floor_arithmetic": next(x["floor_arithmetic"] for x in v2["lines"]["hall_c1_reference"]
                                           if x["line"] == "AL-C1"),
            "v2_c1_floor_constituents": next(x["floor_constituents"] for x in v2["lines"]["hall_c1_reference"]
                                             if x["line"] == "AL-C1"),
            "reading": "the v2 C1 figure is an incomplete analog floor (0.2 kg cathode-unit low end, inferred, "
                       "PRELIMINARY; shield / mount and filter / getter TBD), never a CBE; it is ground lab-equipment "
                       "information only now; the ground C1 module is weighed per serial on GA-01 (row 116)",
            "flight_numbers_effect": "none (flight_rollup_vs_40kg.numerically_unchanged_vs_pre_a9_19)"},
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
            "XA9Q-07": "OWNER_DECIDED (amended by A9.15; Xe role contingency / emergency by A9.19)",
            "XV2Q-01": "NOT_APPLICABLE", "MPQ-01": "OWNER_DECIDED (amended by A9.15; C1 flight parts superseded by "
            "A9.19 / A9.20: no C1 in flight)", "OQ-A907-07": "SUPERSEDED_BY_A9_19_A9_20 (no flight C1; C1 ground-only)",
            "MPQ-02": "OWNER_DECIDED", "OQ-A910-01": "OWNER_DECIDED",
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
            "A9B-C07 (C1 keeper/heater telemetry): its pre-A9.19 recorder mapping to AL-09 (MQ-07 sensor rule) is "
            "history; it is GROUND_ONLY_LAB_EQUIPMENT now (A9.20)",
            "FOR THE OWNER (observation, nothing changed): the AL-08 planning floor is the owner's 5.044 kg H2-7 figure "
            "(MQ-05) and stays as decided; v2 describes its H2-7 two-branch valve set (0.57 kg) as including the C1 "
            "cathode Xe branch (v2 AL-C1 floor arithmetic, c1_mass_check); with no flight C1 after A9.19 / A9.20, "
            "whether AL-08 is re-based to a single-branch set is for the owner / quotations (v2 records the single-branch "
            "reading arithmetic in its AL-08 floor_arithmetic); no number is changed here",
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
          "## RFP-compliant propellant policy (A9.15) and Xe role (A9.19)", "",
          "> " + d["propellant_policy"]["governing_rule"], "",
          f"A9.19: {d['propellant_policy']['architecture']['hall_accelerators']} Hall accelerator; "
          f"{d['propellant_policy']['architecture']['electron_source_neutralizer']}; supply modes: "
          f"{'; '.join(d['propellant_policy']['architecture']['propellant_supply_modes'])}; conventional hollow cathode: "
          f"{d['propellant_policy']['architecture']['conventional_hollow_cathode']}. Xe role "
          f"`{d['propellant_policy']['xenon_role']['role']}` (capability RFP-required, "
          f"{', '.join(d['propellant_policy']['xenon_role']['rfp_clauses'])}). ICP feed: "
          f"{d['propellant_policy']['icp_feed_gas_baseline']}.", "",
          f"AL-08 and the Xe load are `REQUIRED_RFP_XE_CAPABILITY` (role `CONTINGENCY_EMERGENCY`) in the flight "
          f"configuration; C1 Xe branch now: `{d['propellant_policy']['c1_xe_branch_now']['state']}`; AL-C1 now: "
          f"`{d['propellant_policy']['al_c1_now']['state']}`.",
          "", "Registered RFP clauses (" + d["propellant_policy"]["rfp_clauses"]["registration"] + "): "
          + "; ".join(f"{c['clause_id']} (p. {c['page']}): \"{c['verbatim']}\""
                      for c in d["propellant_policy"]["rfp_clauses"]["clauses"]) + ".",
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
        L += [f"* **{r['line']}** (A9.21): {r['a9_21_status']}" for r in d["lines"][cfg] if r.get("a9_21_status")]
        L += [""]
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
          "integration or lighter qualified parts.", ""]
    L += ["## Flight roll-up vs 40 kg (A9.19 / A9.20: numerically unchanged)", ""]
    L += _table(["configuration", "dry known kg", "wet known kg by loaded case", "HARD_40_WET state", "basis"],
                [[f["configuration"], f["dry_known_kg"], f["wet_known_kg_by_loaded_case"],
                  f["hard_40_wet_state_by_loaded_case"], f["basis"]] for f in d["flight_rollup_vs_40kg"]])
    h = d["retired_flight_configuration_history"]
    L += ["## Retired flight configuration - history (A9.19 / A9.20)", "", h["label"] + ".", ""]
    for r in h["rollups"]:
        L += [f"### `{r['configuration']}` (history)", "", r["note"] + ".", "",
              f"pre-A9.19: non-harness known {r['nonharness_known_kg']:g} kg + harness {r['harness_kg']:g} kg = nominal "
              f"{r['nominal_dry_known_kg']:g} kg; + 20 % system margin {r['system_margin_kg']:g} kg = dry known "
              f"{r['dry_known_kg']:g} kg. Lines without a value: {', '.join(r['lines_without_value'])}.", ""]
        L += _table(["loaded Xe kg", "wet known kg", "reference", "state (pre-A9.19)"],
                    [[w["xe_case_kg"], w["wet_known_kg"], f"{w['reference']} ({w['comparator']} {w['reference_kg']:g})",
                      w["state"]] for w in r["wet"]])
    c = d["c1_mass_check"]
    L += ["## C1 mass check (owner request in A9.19)", "", f"Request: \"{c['owner_request']}\" ({c['source']}).", "",
          f"* flight: {c['flight']}",
          f"* v2 C1 evidence floor: {c['v2_c1_evidence_floor_kg']:g} kg (partial: {c['v2_c1_floor_is_partial']}) - "
          f"{c['v2_c1_floor_arithmetic']}",
          f"* reading: {c['reading']}", f"* effect on flight numbers: {c['flight_numbers_effect']}", ""]
    L += ["## C1 BOM items: ground-only lab equipment (A9.20)", ""]
    L += _table(["item", "name", "v3 line", "pre-A9.19 line", "pre-A9.19 mapping"],
                [[x["id"], x["name"], x["allocation_line"], x.get("allocation_line_pre_a9_19"),
                  x.get("allocation_mapping_pre_a9_19")] for x in d["bom"] if x["group"] == "c1"])
    L += ["## BOM allocation mappings decided in v3", ""]
    L += _table(["item", "name", "v2 line", "v3 line", "mapping"],
                [[x["id"], x["name"], x.get("allocation_line_v2"), x["allocation_line"], x["allocation_mapping"]]
                 for x in d["bom"] if "allocation_line_v2" in x and x["group"] != "c1"])
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
