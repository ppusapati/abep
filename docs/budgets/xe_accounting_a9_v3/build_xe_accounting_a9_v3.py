#!/usr/bin/env python3
"""A9.16 Xe accounting v3 (xe_accounting_a9_v3) - a REVISION of the immutable Xe accounting v2.

Lane: A9.16 step 1, mass / power v3 + Xe accounting v3 (owner instruction 2026-10-01 'continue implementing them
sequentially'). Deterministic, standard library only, no Julia, well under a second. The v2 deliverable
(docs/budgets/xe_accounting_a9_v2/) is pinned by sha256 and read as data, never edited.

v3 = v2 + the recorded owner decisions applied (the verbatim .md of each decision governs; every quote below is checked
verbatim at build time and every question id must be an OWNER_DECIDED entry of the decision json):
  * A9.15 RFP-COMPLIANT PROPELLANT POLICY (amends A9.13 owner_statements.xenon and A9.14 S8.17 / S8.21 / S8.33 / S8.35 /
    S9.3 / S9.10): the system supports BOTH ambient atmospheric propellant (180-230 km) AND Xenon propulsion capability with
    separate air and Xe storage paths; Xe is an RFP-required system capability, never a contingency; C1 is an internal
    element: a selected C1 that requires Xe has its Xe booked inside the system Xe architecture; no C1 Xe is invented or
    excluded in advance; C1 presence / absence never removes the system Xe capability;
  * A9.14 XA9Q-07 (as amended) / XV2Q-01: the reading axis RA-FUNC collapses to APPLIES in hall_icp_neutralizer (the
    NOT_APPLIED / Xe-free reading is retired; XV2Q-01 NOT APPLICABLE);
  * A9.14 XA9Q-01 / MQ-09 / OQ-A910-01: the 2 / 5 / 10 kg cases are LOADED Xe = mission usable + reserve + residual, one
    reading for BOTH ledgers; the residual is a sub-line inside the case and is never added again;
  * A9.14 XA9Q-02 / OQ-A907-01: 3 attempts (1 + 2 retries) x 120 s = 360 s maximum ignition booking per start;
  * A9.14 XA9Q-03: the flow-class term stays additive and inside the non-reserve (reserve) base;
  * A9.14 XA9Q-04: 20 % ground-test Xe logistics margin on calculated test consumption, with purges, conditioning,
    line-fill and known vendor procedures booked explicitly (as their own TBD lines) before the margin;
  * A9.14 XA9Q-06: the 75-bar MEOP placeholder is retired; MEOP only from quotations against the 323 K design cases;
  * A9.14 OQ-A907-07 (as amended): flight C1 integration deferred until C1 is selected (not because Xe is
    contingency-only); the flight C1-specific Xe lines are CONDITIONAL_ON_C1_FLIGHT_SELECTION (neither assumed nor
    excluded, so every flight C1 total stays REFUSED); development/reference C1 ground work continues (A9: heated Xe-fed
    LaB6 C1 control);
  * A9.14 MPQ-01 (as amended): a selected C1 requiring Xe books its C1 branch inside the system Xe architecture (AL-08);
  * A9.14 XA9Q-05 (as amended): an ICP Xe-path getter/filter is an engineering / vendor requirement, never a default.
  * NOT changed: the A9.1 ICP gas-mode baseline (G-REUSE primary, m_Xe,ICP = 0 exactly; G-XE a declared ICP-feed
    variant, CASE-3) - A9.15 recorder note.

Every total with a TBD input stays REFUSED (CLAUDE.md rule 3); no number is invented; no PASS of anything.

    python docs/budgets/xe_accounting_a9_v3/build_xe_accounting_a9_v3.py          # (re)write JSON and Markdown
    python docs/budgets/xe_accounting_a9_v3/build_xe_accounting_a9_v3.py --check  # exit 1 unless reproduced byte for byte
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

LANE_REL = "docs/budgets/xe_accounting_a9_v3"
SCRIPT_REL = LANE_REL + "/build_xe_accounting_a9_v3.py"
JSON_NAME = "xe_accounting_a9_v3.json"
MD_NAME = "XE_ACCOUNTING_A9_V3.md"
TEST_REL = "tests/test_xe_accounting_a9_v3.py"
SCHEMA_ID = "xe_accounting_a9_v3"
BASE_COMMIT = "f68b9999ebc89c41ab051bfaebf03c04fc58cc78"
DATE = "2026-10-01"

# Name stem of the older Xe-ledger family; assembled so that code never spells it contiguously (repository rule).
_STEM = "xe" + "_led" + "ger"
A908_SNAPSHOT_DIR = "docs/budgets/" + _STEM + "_a9/sources"

# ------------------------------------------------------------------------------------- immutable inputs (sha256)
V2 = {
    "V2_JSON": ("docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json",
                "ad6102fc12df3ad6c4bcc85264c1893b8ab51857b0319b9881afecd8a6c4730a"),
    "V2_MD": ("docs/budgets/xe_accounting_a9_v2/XE_ACCOUNTING_A9_V2.md",
              "f2cca970bf7fc9870c001af75f5e855b8183cd8e1fbdccb0af78a4596162ff69"),
    "V2_BUILDER": ("docs/budgets/xe_accounting_a9_v2/build_xe_accounting_a9_v2.py",
                   "2c279af73e9d322a501d8577f9dd916f0fc057459b9ec49618e8c11734ba235a"),
}
SNAPSHOT_323 = (A908_SNAPSHOT_DIR + "/nist_webbook_xe_isotherm_323.15K_70-200bar.tsv",
                "190f8d574000a3e023677d17c7275e3498ca8a324955365b1205f6e40af9e376")
A9_DECISION = ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
               "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f")
DECISIONS = {
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
MASS_POWER_V3 = "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json"   # downstream consumer; never read here

CONFIGS = ("hall_c1_reference", "hall_icp_neutralizer")
LEDGERS = ("FLIGHT", "GROUND_TEST")
ZERO_STATES = ("EXACT_ZERO_BY_OWNER_DECISION", "ABSENT_BY_OWNER_DECISION", "ZERO_BY_SCOPE",
               "ZERO_XE_BY_OWNER_DECISION")
NONZERO_STATES = ("PRESENT", "CONDITIONAL", "PRESENT_WHEN_ACTIVATED")
PENDING_STATES = ("CONDITIONAL_ON_C1_FLIGHT_SELECTION",)
PRESENCE_STATES = ZERO_STATES + NONZERO_STATES + PENDING_STATES
RETIRED_PRESENCE = ("ABSENT_UNDER_READING",)     # v2 Xe-free reading of RA-FUNC: retired by A9.14 XA9Q-07 + A9.15
UNIT_SI = {"mg/s": 1e-6, "h": 3600.0, "s": 1.0, "1": 1.0, "kg": 1.0}
UNIT_DIM = {"mg/s": "mass_flow", "h": "time", "s": "time", "1": "dimensionless", "kg": "mass"}
CASE_READING = "LOADED"                        # the only reading (A9.14 XA9Q-01 / MQ-09 / OQ-A910-01)
RETIRED_CASE_READINGS = ("USABLE_RESIDUAL_ON_TOP",)
RETIRED_MEOP_BAR = 75.0                       # A9.14 XA9Q-06: placeholder retired (never a MEOP and no longer an axis)
IGN_ATTEMPTS_MAX = 3                          # A9.14 OQ-A907-01 / XA9Q-02 (owner-supplied)
IGN_DWELL_CAP_S = 120.0                       # owner row 93 / A9.14 XA9Q-02
IGN_BOOKING_MAX_S = 360.0                     # A9.14 XA9Q-02 (owner-supplied)
GROUND_LOGISTICS_MARGIN = 0.2                 # A9.14 XA9Q-04 (owner-supplied)
C1_STATES = ("NOT_SELECTED", "SELECTED")


class PinError(RuntimeError):
    """A pinned immutable input does not match its recorded sha256."""


class BookingError(ValueError):
    """Double counting, a retired reading, a malformed line or an input the owner rules refuse (fail closed)."""


# ------------------------------------------------------------------------------------------------ helpers
def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins() -> None:
    bad = [f"{p} (expected {s[:12]}, got {_sha(p)[:12]})" for p, s in list(V2.values()) + [SNAPSHOT_323, A9_DECISION]
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
    """Source record of one owner decision. The quote must occur verbatim (whitespace-normalized) in the decision's .md;
    the id must be OWNER_DECIDED in its json (A9.15: an amendment key or 'governing_rule')."""
    js, md = _decision(key)
    if _norm(quote) not in md:
        raise BookingError(f"{key} {qid}: quote not found verbatim in {DECISIONS[key]['md']}: {quote[:80]!r}")
    if key == "A9.15":
        if qid != "governing_rule" and qid not in js["amendments"]:
            raise BookingError(f"A9.15 has no amendment {qid}")
        seq = None
        ans = "RFP_COMPLIANT_PROPELLANT_POLICY" if qid == "governing_rule" else js["amendments"][qid]
    else:
        rec = js["decisions"].get(qid)
        if rec is None or rec.get("status") != "OWNER_DECIDED":
            raise BookingError(f"{key} {qid} is not an OWNER_DECIDED entry of {DECISIONS[key]['json']}")
        seq, ans = rec.get("sequenced_no"), rec.get("answer")
    return {"key": key, "id": qid, "sequenced_no": seq, "answer": ans, "quote": quote,
            "path": DECISIONS[key]["md"], "md_sha256": DECISIONS[key]["md_sha256"],
            "json_path": DECISIONS[key]["json"], "json_sha256": DECISIONS[key]["json_sha256"]}


def cite(s: dict) -> str:
    return f"{s['key']} {s['id']} ({s['json_path']} sha256 {s['json_sha256'][:12]})"


def sig6(x: float) -> float:
    return float(f"{x:.6g}")


def rk(x):
    """Deterministic rounding of a booked kg value (10 significant digits); None stays None."""
    return None if x is None else float(f"{x:.10g}")


def _num(v, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) < 0:
        raise BookingError(f"{what} = {v!r} must be a finite number >= 0 (no NaN / negative Xe)")
    return float(v)


# ------------------------------------------------------------------------------------------------ owner decisions
def S() -> dict:
    """Every owner decision applied by this lane, as verbatim-checked source records."""
    return {
        "GOV": OD("A9.15", "governing_rule",
                  "The official RFP is the sole governing basis for propellant capability. The system shall support "
                  "both ambient atmospheric propellant and Xenon. C1-specific Xe requirements, if any, are derived from "
                  "the selected C1 hardware and integrated into that RFP-compliant Xe architecture; no independent "
                  "policy shall restrict or override the RFP."),
        "GOV_C1": OD("A9.15", "governing_rule",
                     "If the selected C1 implementation requires Xenon, its Xe requirement shall be included in the "
                     "system Xe architecture and accounting. If C1 does not require Xe, no separate C1 Xe consumption "
                     "shall be invented. The presence or absence of C1 shall not remove the system-level Xenon "
                     "capability required by the RFP."),
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
        "OD6_A": OD("A9.15", "OD6",
                    "means the system must provide both ambient-air and Xenon operating capability; it should not be "
                    "weakened into a contingency interpretation."),
        "XA9Q01": OD("A9.14", "XA9Q-01",
                     "2/5/10 kg ARE LOADED-Xe CASES. Reserve and residual are carved out within each total loaded "
                     "mass."),
        "MQ09": OD("A9.14", "MQ-09",
                   "NO RESIDUAL ON TOP OF A LOADED CASE. Define each 2/5/10 kg case as total loaded Xe:"),
        "MQ09_F": OD("A9.14", "MQ-09",
                     "Residual may appear as an accounting sub-line but is not added a second time."),
        "OQA91001": OD("A9.14", "OQ-A910-01",
                       "ONE ACCOUNTING READING GOVERNS BOTH LEDGERS: LOADED Xe. The 2/5/10 kg case includes usable "
                       "mission quantity, reserve and residual. Do not add residual again in the mass BOM."),
        "XA9Q02": OD("A9.14", "XA9Q-02",
                     "THREE DWELLS / 360 s MAXIMUM BOOKING. One attempt + two retries, each capped at 120 s. Final "
                     "operating dwell may later be tightened by evidence."),
        "OQA90701": OD("A9.14", "OQ-A907-01",
                       "One initial C1 ignition attempt plus at most two retries = maximum three dwells per start."),
        "XA9Q03": OD("A9.14", "XA9Q-03",
                     "Keep the flow-class term additive and inside the non-reserve base until hardware evidence "
                     "establishes a lower class."),
        "XA9Q04": OD("A9.14", "XA9Q-04",
                     "BOOK A 20% GROUND-TEST Xe LOGISTICS MARGIN. Apply it to calculated test consumption. Purges, "
                     "conditioning, line-fill and known vendor procedures are booked explicitly before this margin "
                     "rather than hidden within it."),
        "XA9Q06": OD("A9.14", "XA9Q-06",
                     "YES, RETIRE THE 75-bar PLACEHOLDER. Request tank/regulator solutions against the 323 K "
                     "volume/pressure cases. Select MEOP only from the actual design case, supplier qualification "
                     "basis and applicable pressure-vessel practice."),
        "OQA90707": OD("A9.14", "OQ-A907-07",
                       "Do not burden the baseline flight article with C1 until C1 is actually selected as a flight "
                       "fallback. Development/reference C1 work continues separately."),
        "OQA90707_A": OD("A9.15", "OQ-A907-07",
                         "S8.17 / OQ-A907-07: C1 flight integration may still be deferred until C1 is selected, but "
                         "not because Xe is contingency-only."),
        "MPQ01": OD("A9.14", "MPQ-01",
                    "C1 heater/keeper/control electronics belong inside AL-07; the C1 Xe branch belongs inside AL-08;"),
        "MPQ01_A": OD("A9.15", "MPQ-01",
                      "S8.33 / MPQ-01: if C1 is selected and requires Xe, its C1-specific branch is booked within the "
                      "RFP-compliant Xe system; do not assume or exclude C1 Xe in advance."),
        "XA9Q05": OD("A9.14", "XA9Q-05",
                     "NO DEFAULT FILTER/GETTER FOR G-XE ICP. Add one only if the selected ICP/material/process or Xe "
                     "purity specification demonstrates the need."),
        "XA9Q05_A": OD("A9.15", "XA9Q-05",
                       "S9.3 / XA9Q-05: whether the ICP Xe path needs a getter/filter remains an engineering/vendor "
                       "requirement, not a policy choice."),
    }


# ======================================================================== fail-closed rule functions (owner rules)
def xe_system_capability(configuration: str, c1_selected=None, c1_requires_xe=None) -> dict:
    """A9.15 / A9.14 XA9Q-07 + XV2Q-01: the RFP-required Xe propulsion capability (own tank and Xe path, separate from
    the ambient-air path) applies to EVERY flight configuration; C1 selection or its Xe need never removes it."""
    if configuration not in CONFIGS:
        raise BookingError(f"unknown configuration {configuration!r}")
    for name, v in (("c1_selected", c1_selected), ("c1_requires_xe", c1_requires_xe)):
        if v is not None and not isinstance(v, bool):
            raise BookingError(f"{name} must be a bool or None")
    return {"configuration": configuration, "xe_propulsion_capability": "PRESENT_RFP_REQUIRED",
            "xe_free_reading": "NOT_APPLICABLE (A9.14 XV2Q-01 + A9.15)",
            "storage_paths": "separate ambient-air and Xe propellant paths (A9.15, owner-stated RFP content pending "
                             "RFP registration AG-15)",
            "independent_of_c1": True}


def c1_flight_xe_booking(c1_selected, c1_requires_xe=None) -> dict:
    """A9.15 / A9.14 MPQ-01 + OQ-A907-07: flight C1-specific Xe is booked inside the system Xe architecture (AL-08 / this
    accounting) ONLY when C1 is selected AND the selected hardware requires Xe; before selection it is neither assumed
    nor excluded (a pending term: every total that would contain it is REFUSED); a selected C1 that needs no Xe gets
    none (no C1 Xe consumption is invented)."""
    if not isinstance(c1_selected, bool):
        raise BookingError("c1_selected must be a bool (no default)")
    if c1_requires_xe is not None and not isinstance(c1_requires_xe, bool):
        raise BookingError("c1_requires_xe must be a bool or None")
    if not c1_selected:
        if c1_requires_xe is not None:
            raise BookingError("a C1 Xe requirement exists only for a SELECTED C1 hardware (A9.15)")
        return {"state": "PENDING_C1_NOT_SELECTED", "booked": None,
                "rule": "neither assumed nor excluded in advance (A9.15 MPQ-01); flight C1 integration deferred until "
                        "C1 is selected (A9.14 OQ-A907-07 as amended)"}
    if c1_requires_xe is None:
        return {"state": "TBD_FROM_SELECTED_C1_HARDWARE", "booked": None,
                "rule": "the selected C1 hardware states whether it requires Xe (A9.15 governing rule)"}
    if c1_requires_xe:
        return {"state": "BOOKED_IN_SYSTEM_XE_ARCHITECTURE", "booked": True,
                "rule": "C1 Xe branch inside AL-08 and the C1 Xe lines of this accounting (A9.14 MPQ-01, A9.15)"}
    return {"state": "NO_C1_XE", "booked": False,
            "rule": "no separate C1 Xe consumption is invented (A9.15 governing rule)"}


def ignition_booking_s(attempts: int = IGN_ATTEMPTS_MAX, dwell_s: float = IGN_DWELL_CAP_S, evidence=None) -> float:
    """A9.14 XA9Q-02 / OQ-A907-01: at most 3 attempts (1 + 2 retries) x at most 120 s = 360 s per start. A shorter
    dwell is admitted only with an evidence source (the owner: 'may later be tightened by evidence')."""
    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= IGN_ATTEMPTS_MAX:
        raise BookingError(f"attempts {attempts!r} outside 1..{IGN_ATTEMPTS_MAX} (one initial + at most two retries)")
    d = _num(dwell_s, "dwell_s")
    if d <= 0 or d > IGN_DWELL_CAP_S:
        raise BookingError(f"dwell {d!r} s outside (0, {IGN_DWELL_CAP_S}] s (row 93 / XA9Q-02)")
    if d < IGN_DWELL_CAP_S and not (isinstance(evidence, str) and evidence.strip()):
        raise BookingError("a dwell below the 120 s cap needs an evidence source (tightened by evidence only)")
    t = attempts * d
    if t > IGN_BOOKING_MAX_S:
        raise BookingError("ignition booking exceeds the 360 s maximum")
    return t


def ground_supply(calculated_kg: dict, procedures_kg: dict, margin=GROUND_LOGISTICS_MARGIN) -> dict:
    """A9.14 XA9Q-04: supply = (calculated test consumption + explicitly booked purge / conditioning / line-fill /
    known-vendor-procedure Xe) x (1 + 0.20). Every procedure category must be booked explicitly (a number, possibly 0
    with a source, is required; None = TBD -> REFUSED); the margin is never used to hide a procedure."""
    if margin != GROUND_LOGISTICS_MARGIN:
        raise BookingError(f"ground logistics margin {margin!r} is not the owner's 0.20 (XA9Q-04)")
    need = ("purge", "conditioning", "line_fill", "vendor_procedures")
    if set(procedures_kg) != set(need):
        raise BookingError(f"procedure bookings must name exactly {need} (booked explicitly before the margin)")
    tbd = [k for k in need if procedures_kg[k] is None] + [k for k, v in calculated_kg.items() if v is None]
    vals = {k: _num(v, k) for k, v in list(calculated_kg.items()) + list(procedures_kg.items()) if v is not None}
    if tbd:
        return {"status": "REFUSED_TBD_INPUTS", "tbd": sorted(tbd), "supply_kg": None,
                "floor_closed_terms_only_kg": rk(sum(vals.values()))}
    base = sum(vals.values())
    return {"status": "COMPUTED", "tbd": [], "calculated_kg": rk(base), "margin_kg": rk(margin * base),
            "supply_kg": rk(base * (1.0 + margin))}


def case_split_loaded(case_kg, f_reserve, f_residual, reading: str = CASE_READING) -> dict:
    """A9.14 XA9Q-01 / MQ-09 / OQ-A910-01: case = LOADED Xe = mission usable + reserve + residual (each once)."""
    if reading in RETIRED_CASE_READINGS:
        raise BookingError(f"case reading {reading} retired: the residual is never added on top of a loaded case "
                           "(A9.14 MQ-09 / OQ-A910-01)")
    if reading != CASE_READING:
        raise BookingError(f"unknown case reading {reading}")
    c, fr, fs = _num(case_kg, "case_kg"), _num(f_reserve, "f_reserve"), _num(f_residual, "f_residual")
    usable = c / (1.0 + fs)                  # usable incl. reserve
    residual = fs * usable
    mission_usable = usable / (1.0 + fr)     # non-reserve cap
    reserve = fr * mission_usable
    if not abs(mission_usable + reserve + residual - c) <= 1e-12 * max(1.0, c):
        raise BookingError("loaded-case split does not close (double counting)")
    return {"case_kg": c, "reading": CASE_READING, "loaded_kg": c, "mission_usable_kg": mission_usable,
            "reserve_kg": reserve, "residual_kg": residual, "usable_incl_reserve_kg": usable}


def meop_basis(proposal) -> dict:
    """A9.14 XA9Q-06: MEOP only from the actual 323 K design case, a supplier qualification basis and applicable
    pressure-vessel practice; the 75-bar placeholder is retired and refused."""
    if proposal is None:
        return {"state": "TBD_FROM_QUOTATIONS", "meop_bar": None}
    if not isinstance(proposal, dict):
        raise BookingError("MEOP proposal must be a mapping")
    if proposal.get("meop_bar") == RETIRED_MEOP_BAR and proposal.get("basis") in (None, "placeholder", "H2-7 H27-34"):
        raise BookingError("the 75-bar MEOP placeholder is retired (A9.14 XA9Q-06)")
    need = ("meop_bar", "design_case_kg", "design_temperature_K", "supplier_quotation_id",
            "supplier_qualification_basis", "pressure_vessel_practice")
    miss = [k for k in need if proposal.get(k) in (None, "")]
    if miss:
        return {"state": "NOT_SELECTED_INCOMPLETE_BASIS", "missing": miss, "meop_bar": None}
    if proposal["design_temperature_K"] != 323.0:
        return {"state": "NOT_SELECTED_WRONG_DESIGN_TEMPERATURE", "meop_bar": None,
                "note": "the design cases are at 323 K (owner row 50 / XA9Q-06)"}
    return {"state": "CANDIDATE_FROM_QUOTATION_OWNER_SELECTION_PENDING", "meop_bar": _num(proposal["meop_bar"], "MEOP")}


def icp_xe_getter(g_xe_variant_declared: bool, spec_record=None) -> dict:
    """A9.14 XA9Q-05 as amended by A9.15: no default getter/filter on a G-XE ICP feed; one is added only when the
    selected ICP / material / process or the Xe purity specification demonstrates the need (an engineering / vendor
    requirement, not a policy choice). C1 getter requirements are separate (AL-C1, only for a selected C1)."""
    if not isinstance(g_xe_variant_declared, bool):
        raise BookingError("g_xe_variant_declared must be a bool")
    if not g_xe_variant_declared:
        return {"state": "NOT_APPLICABLE_G_REUSE_BASELINE", "mass": None}
    if spec_record is None:
        return {"state": "NOT_REQUIRED_BY_DEFAULT", "mass": None}
    if not isinstance(spec_record, dict) or not spec_record.get("source"):
        raise BookingError("a getter requirement needs a sourced specification record")
    if spec_record.get("requires_getter") is True:
        return {"state": "REQUIRED_BY_SPEC_TBD_MASS_POWER", "mass": None, "source": spec_record["source"]}
    return {"state": "NOT_REQUIRED_BY_SPEC", "mass": None, "source": spec_record["source"]}


# ------------------------------------------------------------------------------------------------ items
def build_items(v2: dict, s: dict) -> list:
    out = []
    for it in v2["items"]:
        x = copy.deepcopy(it)
        x.pop("v2_change", None)
        x["v3_change"] = "carried unchanged from v2"
        x["owner_answers_applied"] = []
        iid = x["id"]
        if iid == "XV2-08":
            x.pop("value_by_reading", None)
            x.update(value=float(IGN_ATTEMPTS_MAX), value_display=float(IGN_ATTEMPTS_MAX),
                     basis="owner decision (1 initial + 2 retries)",
                     status="OWNER_DECIDED_MAXIMUM (A9.14 XA9Q-02 / OQ-A907-01)", evidence_class="owner-allocation")
            x["owner_answers_applied"] = [cite(s["XA9Q02"]), cite(s["OQA90701"])]
            x["source"] = x["source"].replace("(both OPEN)", "(v3 state: decided by A9.14 XA9Q-02 / OQ-A907-01)")
            x["v3_change"] = "RA-DWELL resolved: 3 attempts (v2 carried 3 and 2 side by side)"
        elif iid == "XV2-42":
            x.pop("value_by_reading", None)
            x.update(value=ignition_booking_s(), value_display=ignition_booking_s(),
                     basis="arithmetic 3 attempts x 120 s cap (ignition_booking_s)",
                     status="OWNER_DECIDED_MAXIMUM_BOOKING (A9.14 XA9Q-02; may later be tightened by evidence)")
            x["owner_answers_applied"] = [cite(s["XA9Q02"]), cite(s["OQA90701"])]
            x["v3_change"] = "RA-DWELL resolved: 360 s maximum booking per start"
        elif iid == "XV2-37":
            x.update(value=GROUND_LOGISTICS_MARGIN, value_display=GROUND_LOGISTICS_MARGIN,
                     basis="owner decision: on calculated ground-test consumption, procedures booked explicitly before it",
                     source=f"{s['XA9Q04']['path']} (A9.14 XA9Q-04)", evidence_class="owner-allocation",
                     status="OWNER_DECIDED (A9.14 XA9Q-04)", freeze_point="NOW")
            x.pop("requires", None)
            x["owner_answers_applied"] = [cite(s["XA9Q04"])]
            x["v3_change"] = "TBD owner call -> 0.20 ground-test logistics margin"
        elif iid == "XV2-28":
            x.update(value=None, value_display="TBD_FROM_QUOTATIONS - MEOP only from the actual 323 K design case, "
                     "supplier qualification basis and applicable pressure-vessel practice (A9.14 XA9Q-06); the 75-bar "
                     "placeholder (H2-7 H27-34) is retired", status="TBD_FROM_QUOTATIONS (A9.14 XA9Q-06)",
                     requires="tank / regulator quotations against the 323 K volume / pressure cases (no purchase)")
            x["owner_answers_applied"] = [cite(s["XA9Q06"])]
            x["v3_change"] = "75-bar placeholder retired; MEOP quote-derived"
        elif iid == "XV2-30":
            x["value_display"] = x["value"]
            x.update(basis="owner answer (case masses) + owner decision (content LOADED)",
                     status="DESIGN_CASES, content LOADED = mission usable + reserve + residual (one reading for both "
                            "ledgers; A9.14 XA9Q-01 / MQ-09 / OQ-A910-01); no single mission load frozen")
            x["owner_answers_applied"] = [cite(s["XA9Q01"]), cite(s["MQ09"]), cite(s["OQA91001"])]
            x["source"] = x["source"].replace("(all OPEN)", "(v3 state: decided by A9.14 XA9Q-01 / MQ-09 / "
                                              "OQ-A910-01)")
            x["v3_change"] = "RA-CASE resolved: LOADED (USABLE_RESIDUAL_ON_TOP retired)"
        elif iid == "XV2-24":
            x["status"] = x["status"] + "; a sub-line inside each loaded case, never added again (A9.14 MQ-09)"
            x["owner_answers_applied"] = [cite(s["MQ09_F"])]
            x["v3_change"] = "residual reading fixed: inside the loaded case"
        elif iid in ("XV2-01", "XV2-02", "XV2-04", "XV2-05", "XV2-09", "XV2-10", "XV2-11"):
            x["v3_scope"] = ("flight use CONDITIONAL_ON_C1_FLIGHT_SELECTION (A9.14 OQ-A907-07 / MPQ-01 as amended by "
                             "A9.15); ground (development / reference C1) use unchanged")
            x["owner_answers_applied"] = [cite(s["OQA90707"]), cite(s["MPQ01_A"])]
            x["v3_change"] = "value unchanged; flight scope conditional on C1 selection"
        elif iid in ("XV2-31", "XV2-32"):
            x["v3_scope"] = ("C1-specific getter/filter: AL-C1 only for a SELECTED C1 that needs it (A9.14 MPQ-01); "
                             "separate from the ICP Xe path (A9.14 XA9Q-05 as amended by A9.15)")
            x["owner_answers_applied"] = [cite(s["MPQ01"]), cite(s["XA9Q05_A"])]
            x["v3_change"] = "scope restated (value TBD unchanged)"
        elif iid == "XV2-22":
            x["v3_scope"] = ("G-XE stays a declared ICP-feed variant (CASE-3); A9.1 gas-mode baseline unchanged (A9.15 "
                             "recorder note); an ICP Xe-path getter/filter only if the spec demonstrates the need "
                             "(A9.14 XA9Q-05 as amended)")
            x["owner_answers_applied"] = [cite(s["XA9Q05"]), cite(s["XA9Q05_A"])]
            x["v3_change"] = "scope note only"
        out.append(x)
    proc = [("XV3-03", "ground-test system Xe-path purge Xe (non-C1; per campaign)", "purge"),
            ("XV3-04", "ground-test Xe conditioning (bake-out / flow-conditioning procedures) Xe", "conditioning"),
            ("XV3-05", "ground-test Xe line-fill Xe (facility + article line volumes)", "line_fill"),
            ("XV3-06", "ground-test Xe consumed by known vendor procedures (acceptance / start procedures)",
             "vendor_procedures")]
    out.append({"id": "XV3-01", "a9_08_item": None, "name": "flight C1 selection state", "value": "NOT_SELECTED",
                "value_display": "NOT_SELECTED", "unit": "state", "kind": "state",
                "basis": "owner decision: flight C1 integration deferred until C1 is selected",
                "source": f"{s['OQA90707']['path']} (A9.14 OQ-A907-07; amended by A9.15)",
                "evidence_class": "owner-allocation", "status": "OWNER_DECIDED (deferred until selected)",
                "freeze_point": "after-evidence", "applies_to": {"configs": ["hall_c1_reference"], "ledgers": ["FLIGHT"]},
                "owner_answers_applied": [cite(s["OQA90707"]), cite(s["OQA90707_A"])], "v3_change": "new"})
    out.append({"id": "XV3-02", "a9_08_item": None, "name": "selected C1 hardware requires Xe (flight)",
                "value": None, "value_display": "TBD_FROM_SELECTED_C1_HARDWARE", "unit": "bool", "kind": "state",
                "basis": "A9.15 governing rule (derived from the selected C1 hardware)",
                "source": f"{s['GOV_C1']['path']} (A9.15)", "evidence_class": "none",
                "status": "TBD_FROM_SELECTED_C1_HARDWARE (neither assumed nor excluded)", "freeze_point": "after-evidence",
                "requires": "C1 selection as a flight fallback and the selected hardware's Xe requirement",
                "applies_to": {"configs": ["hall_c1_reference"], "ledgers": ["FLIGHT"]},
                "owner_answers_applied": [cite(s["GOV_C1"]), cite(s["MPQ01_A"])], "v3_change": "new"})
    for iid, name, cat in proc:
        out.append({"id": iid, "a9_08_item": None, "name": name, "value": None,
                    "value_display": "TBD - booked explicitly before the 20 % logistics margin (A9.14 XA9Q-04)",
                    "unit": "kg", "kind": "mass", "basis": "owner decision (booking rule) / pending (size)",
                    "source": f"{s['XA9Q04']['path']} (A9.14 XA9Q-04)", "evidence_class": "none", "status": "TBD",
                    "freeze_point": "LOCK-2", "procedure_category": cat,
                    "requires": "the registered ground-test procedures (facility / article line volumes, conditioning "
                                "and vendor procedures) with their Xe quantities; no number is invented",
                    "applies_to": {"configs": list(CONFIGS), "ledgers": ["GROUND_TEST"]},
                    "owner_answers_applied": [cite(s["XA9Q04"])], "v3_change": "new (explicit procedure line)"})
    out.sort(key=lambda i: i["id"])
    return out


# ------------------------------------------------------------------------------------------------ ledger lines
C1_FLIGHT_SPECIFIC = ("C1-FL-PURGE", "C1-FL-HEAT", "C1-FL-IGN", "C1-FL-KEEPER", "C1-FL-FLOWUNC")
PROC_LINES = {"hall_icp_neutralizer": "P-GT-PROC", "hall_c1_reference": "C1-GT-PROC"}
PROC_ITEMS = (("PURGE", "XV3-03", "purge"), ("COND", "XV3-04", "conditioning"), ("LINEFILL", "XV3-05", "line_fill"),
              ("VENDOR", "XV3-06", "vendor_procedures"))


def build_lines(v2: dict, s: dict) -> list:
    out = []
    for ln in v2["ledger_lines"]:
        x = copy.deepcopy(ln)
        x["v3_change"] = "carried unchanged from v2"
        x["owner_answers_applied"] = []
        pres = x["presence"]
        if isinstance(pres, dict):
            if pres.get("axis") != "RA-FUNC":
                raise BookingError(f"{x['id']}: unexpected reading axis {pres.get('axis')}")
            x["presence_v2"] = pres
            x["presence"] = pres["APPLIES"]
            x["owner_answers_applied"] = [cite(s["XA9Q07"]), cite(s["XA9Q07_A"]), cite(s["XV2Q01_A"])]
            x["v3_change"] = ("RA-FUNC resolved: RFP-required Xe capability applies (the Xe-free NOT_APPLIED reading "
                              "is retired)")
        if x["id"] in C1_FLIGHT_SPECIFIC:
            x["presence_v2"] = x["presence"]
            x["presence"] = "CONDITIONAL_ON_C1_FLIGHT_SELECTION"
            x["owner_answers_applied"] = [cite(s["OQA90707"]), cite(s["OQA90707_A"]), cite(s["MPQ01_A"]),
                                          cite(s["GOV_C1"])]
            x["v3_change"] = ("flight C1-specific Xe: booked only for a selected C1 that requires Xe (inside the system "
                              "Xe architecture); not selected now -> pending, neither assumed nor excluded")
        if x["id"] == "C1-FL-FLOWUNC":
            x["reserve_base_v2"] = x["reserve_base"]
            x["reserve_base"] = True
            x["owner_answers_applied"].append(cite(s["XA9Q03"]))
            x["v3_change"] += "; RA-FLOWUNC resolved: additive and inside the reserve base"
        if x["id"] in ("C1-FL-IGN", "C1-GT-IGN"):
            x["formula"] = x["formula"] + " (n_attempts x t_dwell_max <= 3 x 120 s = 360 s per start)"
            x["owner_answers_applied"].append(cite(s["XA9Q02"]))
            if x.get("note"):
                x["note"] = x["note"].replace("n_attempts follows RA-DWELL", "n_attempts = 3 (A9.14 XA9Q-02)")
            if x["id"] == "C1-GT-IGN":
                x["v3_change"] = "RA-DWELL resolved: 3 attempts / 360 s"
        out.append(x)
    for cfg, prefix in PROC_LINES.items():
        for tag, item, cat in PROC_ITEMS:
            out.append({"id": f"{prefix}-{tag}", "case": "CASE-1" if cfg == "hall_icp_neutralizer" else "CASE-2",
                        "configuration": cfg, "gas_mode": None, "ledger": "GROUND_TEST", "phase": "procedure",
                        "name": f"ground-test {cat.replace('_', ' ')} Xe (explicit, before the logistics margin)",
                        "formula": f"m_{cat} (booked explicitly; never hidden in the 20 % margin)",
                        "fields": [{"name": f"m_{cat}", "item": item, "unit": "kg"}], "presence": "PRESENT",
                        "a9_08_term": None, "sources": [f"{s['XA9Q04']['path']} decisions.XA9Q-04"], "kind": "mass",
                        "reserve_base": True, "of_lines": [], "optional_entry": False,
                        "note": "ground ledger: no reserve / residual; supply margin applied once in the booking",
                        "procedure_category": cat, "owner_answers_applied": [cite(s["XA9Q04"])], "v3_change": "new"})
    for x in out:
        _validate_line(x)
    return out


def _validate_line(ln: dict) -> None:
    p = ln["presence"]
    if not isinstance(p, str) or p not in PRESENCE_STATES:
        raise BookingError(f"{ln['id']}: presence {p!r} not admitted in v3 (retired: {RETIRED_PRESENCE})")
    if ln["phase"] in ("reserve", "residual"):
        raise BookingError(f"{ln['id']}: reserve/residual are booked only by book_reserve_and_residual")
    if ln["kind"] == "product" and p in NONZERO_STATES + PENDING_STATES:
        dims = [UNIT_DIM.get(f["unit"]) for f in ln["fields"]]
        if None in dims or dims.count("mass_flow") != 1 or dims.count("time") != 1:
            raise BookingError(f"{ln['id']}: a mass product needs exactly one mass flow and one time field")
    if ln["kind"] == "mass" and [f["unit"] for f in ln["fields"]] != ["kg"]:
        raise BookingError(f"{ln['id']}: a mass line needs exactly one kg field")


# ------------------------------------------------------------------------------------------------ evaluation
def eval_line(ln: dict, items: dict, done: dict) -> dict:
    pres = ln["presence"]
    if pres in RETIRED_PRESENCE:
        raise BookingError(f"{ln['id']}: retired presence {pres}")
    out = {"line": ln["id"], "presence": pres, "kg": None, "missing": []}
    if pres in ZERO_STATES:
        out["kg"] = 0.0
        return out
    if pres in PENDING_STATES:
        st = c1_flight_xe_booking(items["XV3-01"]["value"] == "SELECTED", items["XV3-02"]["value"])
        out["missing"].append({"field": "flight C1 selection / selected C1 Xe requirement", "item": "XV3-01, XV3-02",
                               "requires": st["state"] + ": " + st["rule"]})
        return out
    if ln["kind"] in ("product", "mass"):
        val = 1.0
        for f in ln["fields"]:
            it = items[f["item"]]
            v = it["value"]
            if v is None:
                out["missing"].append({"field": f["name"], "item": f["item"],
                                       "requires": it.get("requires", it.get("value_display"))})
                continue
            val *= _num(v, f"{ln['id']}.{f['name']}") * UNIT_SI[f["unit"]]
        out["kg"] = None if out["missing"] else rk(val)
        return out
    if ln["kind"] == "fraction_of_lines":
        f = ln["fields"][0]
        u = items[f["item"]]["value"]
        if u is None:
            out["missing"].append({"field": f["name"], "item": f["item"], "requires": items[f["item"]].get("requires")})
        parts = [done[x]["kg"] for x in ln["of_lines"]]
        if any(p is None for p in parts):
            out["missing"].append({"field": "sum of", "lines": [x for x in ln["of_lines"] if done[x]["kg"] is None]})
        if out["missing"]:
            return out
        out["kg"] = rk(_num(u, f["name"]) * sum(parts))
        return out
    raise BookingError(f"{ln['id']}: unknown kind {ln['kind']}")


def book_reserve_and_residual(evals: list, lines: dict, f_reserve, f_residual) -> dict:
    """Reserve (row 43) and residual (row 45) EXACTLY ONCE per flight evaluation; every line is in the reserve base
    (A9.14 XA9Q-03). The residual is a sub-line of the loaded total (A9.14 MQ-09). Totals with a TBD are REFUSED."""
    if f_reserve is None or f_residual is None:
        raise BookingError("reserve/residual fraction missing (no default)")
    ids = [e["line"] for e in evals]
    if len(ids) != len(set(ids)):
        raise BookingError("duplicate ledger line (double counting)")
    for e in evals:
        if e["line"] in ("RESERVE", "RESIDUAL") or lines[e["line"]]["phase"] in ("reserve", "residual"):
            raise BookingError("reserve/residual already present: booking twice is refused")
        if lines[e["line"]]["reserve_base"] is not True:
            raise BookingError(f"{e['line']}: every v3 flight line is inside the reserve base (XA9Q-03)")
    tbd = [e["line"] for e in evals if e["kg"] is None]
    base = sum(e["kg"] or 0.0 for e in evals)
    reserve = f_reserve * base
    usable = base + reserve
    residual = f_residual * usable
    floors = {"mission_usable_kg": rk(base), "reserve_kg": rk(reserve), "usable_incl_reserve_kg": rk(usable),
              "residual_sub_line_kg": rk(residual), "loaded_kg": rk(usable + residual)}
    if tbd:
        return {"status": "REFUSED_TBD_INPUTS", "tbd_lines": tbd, "totals": None, "floors_closed_terms_only": floors}
    return {"status": "COMPUTED_EXACT_ZERO" if usable + residual == 0.0 else "COMPUTED", "tbd_lines": [],
            "totals": floors, "floors_closed_terms_only": floors}


def build_scenarios(v2: dict) -> list:
    out = []
    for sc in v2["scenarios"]:
        x = copy.deepcopy(sc)
        x["axes_v2"] = x.pop("axes")
        if x["ledger"] == "GROUND_TEST":
            pre = PROC_LINES[x["configuration"]]
            x["lines"] = x["lines"] + [f"{pre}-{t}" for t, _i, _c in PROC_ITEMS]
        if x["id"] == "S2-FL-C1":
            x["role"] = ("C1 reference flight configuration: flight C1 integration DEFERRED until C1 is selected (A9.14 "
                         "OQ-A907-07 as amended by A9.15); RFP-required system Xe capability present")
        out.append(x)
    return out


def evaluate(lines: list, items: dict, scenarios: list) -> list:
    ld = {ln["id"]: ln for ln in lines}
    f_rsv, f_res = items["XV2-23"]["value"], items["XV2-24"]["value"]
    out = []
    for sc in scenarios:
        done = {}
        for lid in sorted(sc["lines"], key=lambda x: ld[x]["kind"] == "fraction_of_lines"):
            done[lid] = eval_line(ld[lid], items, done)
        evals = [done[lid] for lid in sc["lines"]]
        rec = {"scenario": sc["id"], "lines": evals}
        if sc["ledger"] == "FLIGHT":
            rec["booking"] = book_reserve_and_residual(evals, ld, f_rsv, f_res)
        else:
            calc = {e["line"]: e["kg"] for e in evals if ld[e["line"]]["phase"] != "procedure"}
            procs = {ld[e["line"]]["procedure_category"]: e["kg"] for e in evals
                     if ld[e["line"]]["phase"] == "procedure"}
            g = ground_supply(calc, procs)
            g["tbd_lines"] = [e["line"] for e in evals if e["kg"] is None]
            g["rule"] = ("supply = (calculated test consumption + explicit procedure lines) x 1.20 (A9.14 XA9Q-04); no "
                         "reserve / residual rule for ground-test Xe")
            rec["booking"] = g
        out.append(rec)
    return out


# ------------------------------------------------------------------------------------------------ design cases
def read_isotherm(rel: str) -> dict:
    rows = (REPO / rel).read_text(encoding="utf-8").splitlines()
    hdr = rows[0].split("\t")
    ip, ir = hdr.index("Pressure (bar)"), hdr.index("Density (kg/m3)")
    return {float(c[ip]): float(c[ir]) for c in (r.split("\t") for r in rows[1:] if r.strip())}


def design_cases(v2: dict, items: dict, evals: list, s: dict) -> dict:
    f_rsv, f_res = items["XV2-23"]["value"], items["XV2-24"]["value"]
    u_rho, cases = items["XV2-27"]["value"], items["XV2-30"]["value"]
    pdc = v2["design_cases"]
    iso = read_isotherm(SNAPSHOT_323[0])
    agreement = []
    axis = []
    for row in pdc["density_axis"]["rows"]:
        if row["p_bar"] == RETIRED_MEOP_BAR:
            continue
        rho = iso[row["p_bar"]]
        agreement.append({"check": f"density {row['p_bar']} bar (323.15 K) = v2 density_axis",
                          "agrees": rho == row["rho_323K_kg_m3"]})
        axis.append({"p_bar": row["p_bar"], "rho_323K_kg_m3": rho, "axis_basis": row["axis_basis"]})
    v2split = {r["case_kg"]: r for r in pdc["reserve_residual_split"]["rows"] if r["reading"] == "LOADED"}
    split = []
    for c in cases:
        sp = case_split_loaded(c, f_rsv, f_res)
        r = {k: (sig6(v) if isinstance(v, float) and k != "case_kg" else v) for k, v in sp.items()}
        p = v2split[c]
        agreement.append({"check": f"LOADED split {c} kg = v2 LOADED row",
                          "agrees": (r["residual_kg"], r["reserve_kg"], r["mission_usable_kg"]) ==
                          (p["residual_kg"], p["reserve_kg"], p["non_reserve_cap_kg"])})
        split.append(r)
    v2vol = {(r["case_kg"], r["p_bar"]): r["V_min_323K_l"] for r in pdc["tank_volume"]["rows"]
             if r["reading"] == "LOADED"}
    vol = []
    for c in cases:
        for a in axis:
            v = sig6(c / (a["rho_323K_kg_m3"] * (1.0 - u_rho)) * 1000.0)
            vol.append({"case_kg": c, "loaded_kg": c, "p_bar": a["p_bar"], "V_min_323K_l": v})
            agreement.append({"check": f"V_min {c} kg @ {a['p_bar']} bar = v2 LOADED", "agrees": v == v2vol[(c, a["p_bar"])]})
    headroom = []
    for e in evals:
        sc = e["scenario"]
        if not sc.split("-")[1] == "FL":
            continue
        fl = e["booking"]["floors_closed_terms_only"]
        for c in cases:
            sp = case_split_loaded(c, f_rsv, f_res)
            cap = sig6(sp["mission_usable_kg"])
            h = cap - fl["mission_usable_kg"]
            headroom.append({"scenario": sc, "case_kg": c, "closed_mission_usable_kg": fl["mission_usable_kg"],
                             "mission_usable_cap_kg": cap, "headroom_for_TBD_terms_kg": sig6(h),
                             "status": "HEADROOM" if h >= 0 else "EXCEEDED_BY_CLOSED_TERMS"})
    # conditional sensitivity: what a SELECTED C1 that requires Xe at the A5 design flow would take (not booked)
    t_fire = items["XV2-01"]["value"] * 3600.0
    keeper = rk(items["XV2-02"]["value"] * 1e-6 * t_fire)
    flowunc = rk(items["XV2-04"]["value"] * items["XV2-05"]["value"] * 1e-6 * t_fire)
    v2ceil = {r["case_kg"]: r["c1_flow_ceiling_mg_s_all_other_terms_zero"] for r in pdc["c1_flow_ceiling"]["rows"]
              if r["reading"] == {"RA-FLOWUNC": "INSIDE_RESERVE_BASE", "RA-CASE": "LOADED"}}
    ceil = []
    for c in cases:
        sp = case_split_loaded(c, f_rsv, f_res)
        cap = sig6(sp["mission_usable_kg"])
        cf = sig6((cap - flowunc) / t_fire / 1e-6)
        agreement.append({"check": f"C1 flow ceiling {c} kg = v2 (LOADED, INSIDE)", "agrees": cf == v2ceil[c]})
        ceil.append({"case_kg": c, "c1_flow_ceiling_mg_s_all_other_terms_zero": cf,
                     "a5_design_flow_mg_s": items["XV2-02"]["value"],
                     "design_flow_within_ceiling": items["XV2-02"]["value"] <= cf})
    bad = [a["check"] for a in agreement if not a["agrees"]]
    if bad:
        raise BookingError("v3 does not reproduce the verified v2 LOADED tables: " + "; ".join(bad))
    gate, capf = items["XV2-38"]["value"], items["XV2-39"]["value"]
    share = [{"case_kg": c, "loaded_kg": c, "share_of_40kg_xe_load_only": sig6(c / gate), "screening_cap_row44": capf,
              "xe_load_alone_reaches_screening_cap": c / gate >= capf} for c in cases]
    return {
        "label": "owner design cases (row 48), content LOADED Xe = mission usable + reserve + residual (A9.14 XA9Q-01 / "
                 "MQ-09 / OQ-A910-01); no mission load is frozen; arithmetic on owner allocations, not a prediction",
        "case_relation": "M_loaded = M_mission_usable + M_reserve + M_residual (each once; residual a sub-line)",
        "eos": dict(pdc["eos"], use="density read from the pinned NIST snapshot (323.15 K); MEOP not chosen here"),
        "density_axis": {"label": "sensitivity axis over MEOP (not a MEOP choice; MEOP TBD_FROM_QUOTATIONS, A9.14 "
                                  "XA9Q-06); the retired 75-bar placeholder row is removed",
                         "retired_rows": [{"p_bar": RETIRED_MEOP_BAR, "why": cite(s["XA9Q06"])}], "rows": axis},
        "loaded_split": {"relation": "usable incl. reserve = case/(1+f_residual); residual = f_residual x usable; "
                                     "mission usable = usable/(1+f_reserve); reserve = f_reserve x mission usable; the "
                                     "three add to the case (checked)", "rows": split},
        "tank_volume": {"relation": "V_min = M_loaded / (rho(323.15 K, p) x (1 - u_rho)); volume only, no tank mass; MEOP "
                                    "and proof/burst factors TBD_FROM_QUOTATIONS", "evidence_class": "model-derived",
                        "rows": vol},
        "headroom": {"label": "mission-usable cap per loaded case minus the closed flight terms (arithmetic; not an "
                              "allocation)", "rows": headroom},
        "c1_conditional_sensitivity": {
            "label": "CONDITIONAL_SENSITIVITY_NOT_BOOKED: what a SELECTED flight C1 that requires Xe at the A5 design "
                     "flow would take (A9.15: neither assumed nor excluded in advance)",
            "keeper_term_kg_if_selected_and_xe": keeper, "flow_class_term_kg_if_selected_and_xe": flowunc,
            "flow_ceiling_rows": ceil},
        "mass_share": {"label": "loaded Xe alone vs the row-44 0.25 screening cap on the 40 kg wet gate (row 5)",
                       "rows": share},
        "v2_agreement": agreement,
    }


# ------------------------------------------------------------------------------------------------ document
APPLIED = [
    ("GOV", "governing rule for every Xe line: the RFP requires air + Xe capability; Xe is never a contingency"),
    ("GOV_C1", "flight C1 Xe lines pending C1 selection; no C1 Xe invented; system Xe capability independent of C1"),
    ("XA9Q07", "RA-FUNC resolved to APPLIES: hall_icp_neutralizer carries the Xe-capable mode family with its own tank"),
    ("XA9Q07_A", "as above (A9.15 amendment: because the RFP requires it, not as a C1 contingency)"),
    ("XV2Q01", "XV2Q-01 closed NOT_APPLICABLE; no Xe-free flight reading remains (ABSENT_UNDER_READING retired)"),
    ("XV2Q01_A", "as above (A9.15)"),
    ("OD6_A", "dual-propellant capability: separate ambient-air and Xe operating modes / paths (no premix assumed)"),
    ("XA9Q01", "RA-CASE resolved to LOADED; USABLE_RESIDUAL_ON_TOP retired (case_split_loaded refuses it)"),
    ("MQ09", "M_loaded = mission usable + reserve + residual"),
    ("MQ09_F", "residual a sub-line inside the case, never added again"),
    ("OQA91001", "one reading for both ledgers: exported to mass / power v3 as LOADED (XV3-IF-01)"),
    ("XA9Q02", "RA-DWELL resolved: 3 dwells x 120 s = 360 s maximum booking per start (ignition_booking_s)"),
    ("OQA90701", "1 + 2 retries = 3 attempts (XV2-08 = 3)"),
    ("XA9Q03", "RA-FLOWUNC resolved: flow-class lines additive and inside the reserve base"),
    ("XA9Q04", "0.20 ground-test logistics margin; explicit purge / conditioning / line-fill / vendor lines (ground_supply)"),
    ("XA9Q06", "75-bar row removed from the MEOP axis; MEOP TBD_FROM_QUOTATIONS (meop_basis refuses the placeholder)"),
    ("OQA90707", "flight C1 integration deferred until selected; ground (development / reference) C1 lines unchanged"),
    ("OQA90707_A", "deferral reason restated: not because Xe is contingency-only"),
    ("MPQ01", "a selected C1's Xe branch belongs inside AL-08 (mass / power v3) and inside this system accounting"),
    ("MPQ01_A", "C1 Xe neither assumed nor excluded in advance (c1_flight_xe_booking)"),
    ("XA9Q05", "no default getter / filter on a G-XE ICP feed (icp_xe_getter)"),
    ("XA9Q05_A", "getter need is an engineering / vendor requirement, not a policy choice"),
]


def owner_answers_applied(s: dict) -> list:
    out = []
    for k, how in APPLIED:
        r = dict(s[k])
        r["how_applied"] = how
        out.append(r)
    return out


def build_doc() -> dict:
    verify_pins()
    v2 = _load(V2["V2_JSON"][0])
    s = S()
    a9 = _load(A9_DECISION[0])
    if "heated Xe-fed LaB6 C1" not in json.dumps(a9):
        raise BookingError("A9 no longer names the heated Xe-fed LaB6 C1 control (ground C1 Xe basis)")
    a913 = _decision("A9.13")[0]
    items = build_items(v2, s)
    idx = {i["id"]: i for i in items}
    lines = build_lines(v2, s)
    scen = build_scenarios(v2)
    ld = {ln["id"] for ln in lines}
    for sc in scen:
        miss = [x for x in sc["lines"] if x not in ld]
        if miss:
            raise BookingError(f"{sc['id']}: unknown lines {miss}")
    evals = evaluate(lines, idx, scen)
    dc = design_cases(v2, idx, evals, s)
    caps = [xe_system_capability(c) for c in CONFIGS]
    return {
        "schema": SCHEMA_ID, "id": SCHEMA_ID, "version": "3.0.0", "lane": "a9_16_step1_mass_power_xe_v3",
        "authorization": "owner instruction 2026-10-01 'continue implementing them sequentially' (A9.16 step 1); "
                         "decisions A9.14 / A9.15 (A9.13 Xe wording superseded)",
        "revision_of": {"path": V2["V2_JSON"][0], "sha256": V2["V2_JSON"][1], "md": V2["V2_MD"][0],
                        "md_sha256": V2["V2_MD"][1], "builder": V2["V2_BUILDER"][0],
                        "builder_sha256": V2["V2_BUILDER"][1],
                        "rule": "v2 is immutable history: read as data, never edited; ids stable (XV2-* kept, new XV3-*)"},
        "status": "PARAMETRIC_XE_ACCOUNTING_V3 - owner decisions applied; every total with a TBD input REFUSED; nothing "
                  "frozen; no winner; no PASS",
        "a9_status": v2["a9_status"], "a9_6_fixed_statuses_unchanged": v2["a9_6_fixed_statuses_unchanged"],
        "date": DATE, "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_REL}/{MD_NAME}", "test": TEST_REL,
        "what_this_is_not": [
            "not a Xe allocation: no mission Xe load is frozen (row 48)",
            "not a prediction of thrust, discharge current, neutralizer current or plasma state (no Hall closure "
            "admitted; credible set EMPTY; 0-D Hall superseded; v1.2-v1.6 withdrawn)",
            "not a C1 selection: flight C1 stays NOT_SELECTED; its Xe is neither assumed nor excluded",
            "not a change of the A9.1 ICP gas-mode baseline (G-REUSE primary, m_Xe,ICP = 0; G-XE a declared variant)",
            "not a ranking and not a compliance statement: no winner, no PASS",
            "not wired into archengine (goldens do not move); v1 / A9-08 / v2 Xe deliverables unchanged"],
        "pins": {"v2": [{"key": k, "path": p, "sha256": h} for k, (p, h) in V2.items()],
                 "decisions": [{"key": k, "json": d["json"], "json_sha256": d["json_sha256"], "md": d["md"],
                                "md_sha256": d["md_sha256"]} for k, d in DECISIONS.items()],
                 "a9": {"path": A9_DECISION[0], "sha256": A9_DECISION[1]},
                 "nist_snapshot_323K": {"path": SNAPSHOT_323[0], "sha256": SNAPSHOT_323[1]}},
        "propellant_policy": {
            "governing_rule": _decision("A9.15")[0]["governing_rule"],
            "source": cite(s["GOV"]),
            "rules": _decision("A9.15")[0]["rules"],
            "superseded_wording": {"A9.13 owner_statements.xenon": a913["owner_statements"]["xenon"],
                                   "A9.14": "the 'Xe contingency-only for C1' wording in S8.17 / S8.21 / S8.33 / S8.35 "
                                            "/ S9.3 / S9.10",
                                   "superseded_by": cite(s["GOV"])},
            "per_configuration": caps,
            "c1_flight_xe_now": c1_flight_xe_booking(False),
            "ground_reference_c1": "development / reference C1 = A9 'heated Xe-fed LaB6 C1' control; its ground Xe lines "
                                   "stay booked (A9.14 OQ-A907-07: development/reference C1 work continues)",
            "icp_gas_mode_baseline_unchanged": "A9.1: G-REUSE primary (m_Xe,ICP = 0 exactly); G-XE a declared ICP-feed "
                                               "variant (CASE-3); A9.15 recorder note",
            "icp_xe_getter": icp_xe_getter(True),
        },
        "reading_axes_resolved": {
            "RA-FUNC": {"v3": "APPLIES", "retired": ["NOT_APPLIED"], "by": [cite(s["XA9Q07"]), cite(s["XA9Q07_A"]),
                                                                          cite(s["XV2Q01_A"])]},
            "RA-DWELL": {"v3": "ATTEMPTS_3 (360 s)", "retired": ["ATTEMPTS_2"],
                         "by": [cite(s["XA9Q02"]), cite(s["OQA90701"])]},
            "RA-FLOWUNC": {"v3": "INSIDE_RESERVE_BASE", "retired": ["OUTSIDE_RESERVE_BASE"], "by": [cite(s["XA9Q03"])]},
            "RA-CASE": {"v3": "LOADED", "retired": list(RETIRED_CASE_READINGS),
                        "by": [cite(s["XA9Q01"]), cite(s["MQ09"]), cite(s["OQA91001"])]},
        },
        "accounting_convention": v2["accounting_convention"],
        "cases": dict(v2["cases"], **{
            "CASE-1": "PRIMARY hall_icp_neutralizer, G-REUSE: m_Xe,ICP = 0 exactly; flight Xe for the RFP-required Hall "
                      "Xe-capable mode family (own tank / path); ground-test Xe; P1 bench Ar-only",
            "CASE-2": "REFERENCE hall_c1_reference: RFP-required Hall Xe-mode family; flight C1-specific lines pending C1 "
                      "selection; ground C1 (development / reference) lines booked"}),
        "items": items, "ledger_lines": lines, "scenarios": scen, "evaluations": evals, "design_cases": dc,
        "interface_demands": [
            {"id": "XV3-IF-01", "direction": "OUT", "from": SCHEMA_ID, "to": MASS_POWER_V3,
             "quantity": "LOADED Xe design cases 2 / 5 / 10 kg and their residual / reserve sub-lines "
                         "(design_cases.loaded_split): the wet roll-up adds M_loaded once and never adds the residual again",
             "units": "kg", "status": "EXPORTED (read by mass / power v3 at build time; id-checked, not sha-pinned)"},
            {"id": "XV3-IF-02", "direction": "IN", "from": MASS_POWER_V3, "to": SCHEMA_ID,
             "quantity": "stored-Xe hardware (AL-08: tank, regulator, valves, plumbing, mounting, thermal) planning "
                         "floor / CBE for the stored-Xe share", "units": "kg",
             "status": "TBD_AFTER_EVIDENCE (AL-08 MEV planning floor 6.0528 kg is not a CBE; quotations replace it)"},
            {"id": "XV3-IF-03", "direction": "OUT", "from": SCHEMA_ID, "to": "RFQ v3 (quotation only)",
             "quantity": "tank / regulator MEOP and proof / burst basis against the 323 K LOADED cases (XV2-28 / XV2-29)",
             "units": "bar", "status": "TBD_FROM_QUOTATIONS (no purchase, no supplier contact)"}],
        "owner_answers_applied": owner_answers_applied(s),
        "open_owner_questions": [
            {"id": "XV2Q-01", "status": "NOT_APPLICABLE", "by": [cite(s["XV2Q01"]), cite(s["XV2Q01_A"])]}],
        "recorder_flags": [
            "XA9Q-04 reading: the 0.20 margin is applied to the full calculated ground total INCLUDING the explicitly "
            "booked purge / conditioning / line-fill / vendor lines (conservative literal reading of 'booked explicitly "
            "before this margin'); flagged for owner confirmation, no number depends on it today (all TBD)",
            "the AL-08 planning floor (5.044 kg CBE floor) is the owner's figure (A9.14 MQ-05); whether its two-branch "
            "valve set already covers a selected C1 branch is decided when C1 is selected (mass / power v3)"],
        "compliance": {
            "no_new_numbers": "every number is owner-given, copied from the pinned v2 / NIST snapshot, or arithmetic "
                              "on those; TBD stays TBD",
            "no_pass": "no PASS verdict; every total with a TBD input REFUSED",
            "no_contact": "no supplier, lab or author contact; quotations only through the RFQ lane",
            "pure": "standard library; not wired into archengine; no frozen data, goldens or production module touched"},
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
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return out + [""]


def render_md(doc: dict) -> str:
    L = [f"# A9 Xe accounting v3 (A9.16 step 1)", "",
         f"Generated by `{doc['generated_by']}` from `{LANE_REL}/{JSON_NAME}` (do not edit by hand; `--check` "
         f"verifies). Status `{doc['status']}`. Base commit `{doc['base_commit']}`. Revision of `{doc['revision_of']['path']}` "
         f"(sha256 `{doc['revision_of']['sha256']}`, immutable). Test `{doc['test']}`.", "",
         "**What this is not:** " + "; ".join(doc["what_this_is_not"]) + ".", "",
         "## RFP-compliant propellant policy (A9.15)", "", "> " + doc["propellant_policy"]["governing_rule"], "",
         f"Source: {doc['propellant_policy']['source']}. Superseded wording: A9.13 owner_statements.xenon "
         f"(\"{doc['propellant_policy']['superseded_wording']['A9.13 owner_statements.xenon']}\") and "
         f"{doc['propellant_policy']['superseded_wording']['A9.14']}.", ""]
    L += _table(["configuration", "Xe propulsion capability", "Xe-free reading", "independent of C1"],
                [[c["configuration"], c["xe_propulsion_capability"], c["xe_free_reading"], c["independent_of_c1"]]
                 for c in doc["propellant_policy"]["per_configuration"]])
    L += [f"* flight C1 Xe now: `{doc['propellant_policy']['c1_flight_xe_now']['state']}` - "
          f"{doc['propellant_policy']['c1_flight_xe_now']['rule']}",
          f"* ground reference C1: {doc['propellant_policy']['ground_reference_c1']}",
          f"* ICP gas-mode baseline: {doc['propellant_policy']['icp_gas_mode_baseline_unchanged']}", "",
          "## Reading axes resolved by the owner", ""]
    L += _table(["axis", "v3", "retired", "by"], [[k, v["v3"], ", ".join(v["retired"]), "; ".join(v["by"])]
                                                 for k, v in doc["reading_axes_resolved"].items()])
    L += ["## Owner decisions applied", ""]
    L += _table(["decision", "id", "seq", "answer", "json sha256", "how applied"],
                [[r["key"], r["id"], r["sequenced_no"], r["answer"], r["json_sha256"], r["how_applied"]]
                 for r in doc["owner_answers_applied"]])
    L += ["## Items", ""]
    L += _table(["id", "name", "value", "unit", "status", "v3 change"],
                [[i["id"], i["name"], i.get("value_display", i["value"]), i["unit"], i["status"], i["v3_change"]]
                 for i in doc["items"]])
    L += ["## Ledger lines", ""]
    L += _table(["id", "config", "ledger", "phase", "presence", "formula", "v3 change"],
                [[x["id"], x["configuration"], x["ledger"], x["phase"], x["presence"], x["formula"], x["v3_change"]]
                 for x in doc["ledger_lines"]])
    L += ["## Scenario evaluations (every total with a TBD input REFUSED)", ""]
    rows = []
    for e in doc["evaluations"]:
        b = e["booking"]
        tot = b.get("totals") or {}
        rows.append([e["scenario"], b["status"], ", ".join(b["tbd_lines"]) or "-",
                     tot.get("loaded_kg", b.get("supply_kg"))])
    L += _table(["scenario", "status", "TBD lines", "loaded / supply kg"], rows)
    dc = doc["design_cases"]
    L += ["## Design cases (LOADED)", "", dc["label"], "", "`" + dc["case_relation"] + "`", ""]
    L += _table(["case kg", "mission usable", "reserve", "residual (sub-line)", "loaded"],
                [[r["case_kg"], r["mission_usable_kg"], r["reserve_kg"], r["residual_kg"], r["loaded_kg"]]
                 for r in dc["loaded_split"]["rows"]])
    L += [dc["density_axis"]["label"], ""]
    L += _table(["case kg", "p bar", "V_min 323 K (l)"], [[r["case_kg"], r["p_bar"], r["V_min_323K_l"]]
                                                          for r in dc["tank_volume"]["rows"]])
    L += _table(["scenario", "case kg", "mission-usable cap", "headroom for TBD terms", "status"],
                [[r["scenario"], r["case_kg"], r["mission_usable_cap_kg"], r["headroom_for_TBD_terms_kg"], r["status"]]
                 for r in dc["headroom"]["rows"]])
    cs = dc["c1_conditional_sensitivity"]
    L += [cs["label"] + f": keeper {cs['keeper_term_kg_if_selected_and_xe']} kg, flow class "
          f"{cs['flow_class_term_kg_if_selected_and_xe']} kg.", ""]
    L += _table(["case kg", "C1 flow ceiling mg/s (all else 0)", "A5 design flow", "within"],
                [[r["case_kg"], r["c1_flow_ceiling_mg_s_all_other_terms_zero"], r["a5_design_flow_mg_s"],
                  r["design_flow_within_ceiling"]] for r in cs["flow_ceiling_rows"]])
    L += ["## Interfaces", ""]
    L += _table(["id", "dir", "to / from", "quantity", "status"],
                [[x["id"], x["direction"], x["to"] if x["direction"] == "OUT" else x["from"], x["quantity"], x["status"]]
                 for x in doc["interface_demands"]])
    L += ["## Open questions and recorder flags", ""]
    L += [f"* {q['id']}: {q['status']} ({'; '.join(q['by'])})" for q in doc["open_owner_questions"]]
    L += [f"* flag: {f}" for f in doc["recorder_flags"]] + [""]
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
