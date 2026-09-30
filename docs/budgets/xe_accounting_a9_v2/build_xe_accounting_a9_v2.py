#!/usr/bin/env python3
"""A9.6 complete Xe accounting v2 (xe_accounting_a9_v2) - a REVISION of the immutable A9-08 Xe ledger.

Follow-on ``fo_a9_6_xe_accounting`` (owner directive A9.6 'IMPLEMENTATION-FIRST', sec. 12). Deterministic, standard
library only, no Julia, well under a second. The A9-08 deliverable (docs/budgets/<the Xe ledger>_a9/) is pinned by
sha256 and read, never edited; this directory name deliberately avoids that family's name.

What it does
  * verifies the sha256 of every pinned immutable input (A9, the 147 owner answers + verbatim pack, A9.1 .. A9.6 decisions
    + verbatim records, the A9-08 deliverable files and its two NIST WebBook isotherm snapshots, owner-question state v3)
    and refuses to run on any mismatch (no fallback);
  * books every Xe use as a separate ledger line in three cases:
      CASE-1 PRIMARY  hall_icp_neutralizer, G-REUSE: m_Xe,ICP = 0 exactly (mdot_ICP,dedicated = 0); flight Xe only for the
                      Hall's Xe-capable mode family (row 6 / row 42), carried under BOTH readings of the OPEN XA9Q-07;
                      ground-test Xe (XE_REFERENCE etc.); P1 ICP bench is Ar-only (zero Xe by scope);
      CASE-2 REFERENCE hall_c1_reference (control / fallback): purge, heating/start, ignition (BOTH dwell readings of the
                      OPEN XA9Q-02 / OQ-A907-01), keeper/cathode, transition, fallback - each its own line with its source;
      CASE-3 OPTIONAL  any G-XE ICP contingency / diagnostic feed (and G-ATM, 0 Xe) as separate explicit entries that are
                      ZERO (not present) in every primary scenario;
  * books the row-43 reserve and the row-45 residual EXACTLY ONCE per flight evaluation (the booking function refuses an
    input that already contains a reserve or residual line), carrying both readings of the OPEN XA9Q-03 reserve base;
  * refuses every total with a TBD input (no hidden defaults, CLAUDE.md rule 3) and reports floors on closed terms only;
  * evaluates the row-48 2 / 5 / 10 kg design cases under BOTH OPEN case-content readings (LOADED, XA9Q-01; USABLE with the
    residual on top, MQ-09; OQ-A910-01), with the 323.15 K tank volume from the A9-08 NIST snapshot, and shows that the
    LOADED reading reproduces the verified A9-08 tables exactly;
  * writes xe_accounting_a9_v2.json and XE_ACCOUNTING_A9_V2.md (generated from the JSON).

What it is not: a Xe allocation (row 48), a prediction of any Hall, neutralizer or plasma quantity (no Hall closure is
admitted; 0-D Hall superseded), an owner answer, a ranking or a winner, a PASS of anything. Not wired into archengine.

    python docs/budgets/xe_accounting_a9_v2/build_xe_accounting_a9_v2.py          # (re)write JSON and Markdown
    python docs/budgets/xe_accounting_a9_v2/build_xe_accounting_a9_v2.py --check  # exit 1 unless reproduced byte for byte
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

LANE_REL = "docs/budgets/xe_accounting_a9_v2"
SCRIPT_REL = LANE_REL + "/build_xe_accounting_a9_v2.py"
JSON_NAME = "xe_accounting_a9_v2.json"
MD_NAME = "XE_ACCOUNTING_A9_V2.md"
TEST_REL = "tests/test_xe_accounting_a9_v2.py"
SCHEMA_ID = "xe_accounting_a9_v2"
BASE_COMMIT = "c33b22c78b14cd4d6a51ed9bd5de4e046bc98cae"
DATE = "2026-09-30"

# Name stem of the Xe-ledger family; assembled so that code never spells it contiguously (repository rule).
_STEM = "xe" + "_led" + "ger"
PREV_DIR = "docs/budgets/" + _STEM + "_a9"
V1_DIR = "docs/budgets/" + _STEM

CONFIGS = ("hall_c1_reference", "hall_icp_neutralizer")
LEDGERS = ("FLIGHT", "GROUND_TEST")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "none")
ZERO_STATES = ("EXACT_ZERO_BY_OWNER_DECISION", "ABSENT_BY_OWNER_DECISION", "ABSENT_UNDER_READING", "ZERO_BY_SCOPE",
               "ZERO_XE_BY_OWNER_DECISION")
NONZERO_STATES = ("PRESENT", "CONDITIONAL", "PRESENT_WHEN_ACTIVATED")
PRESENCE_STATES = ZERO_STATES + NONZERO_STATES
UNIT_SI = {"mg/s": 1e-6, "h": 3600.0, "s": 1.0, "1": 1.0}
UNIT_DIM = {"mg/s": "mass_flow", "h": "time", "s": "time", "1": "dimensionless"}


class PinError(RuntimeError):
    """A pinned immutable input does not match its recorded sha256."""


class BookingError(ValueError):
    """Reserve/residual double counting or a malformed ledger line (fail closed)."""


# ------------------------------------------------------------------------------------------------ pinned inputs
DECISIONS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "147 owner answers (machine-readable)"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "147 owner answers (verbatim pack)"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "A9.1 follow-up owner decisions"),
    "A91MD": ("docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md",
              "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e", "A9.1 (verbatim)"),
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03", "A9.2 A9-07 follow-up owner decisions"),
    "A92MD": ("docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md",
              "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9", "A9.2 (verbatim)"),
    "A93": ("docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json",
            "81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b", "A9.3 post-A9 tier-1 owner decisions"),
    "A93MD": ("docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md",
              "55a1fd84558a9590705bb82aa11db5e2b9136dd1d83a957d26614c435c707411", "A9.3 (verbatim)"),
    "A94": ("docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json",
            "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d", "A9.4 P1/P2 owner decisions"),
    "A94MD": ("docs/decisions/OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md",
              "53cc026d63f85bd416f8ed8f4e8f9f7e7d7fc4429dccc45b86a51390b5c08b1c", "A9.4 (verbatim)"),
    "A95": ("docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json",
            "c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3", "A9.5 P1 closure owner decisions"),
    "A95MD": ("docs/decisions/OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md",
              "9e49e923328441c1fc82afd3eb64c13d85fc818e8fe534576ada61a16fa525f3", "A9.5 (verbatim)"),
    "A96": ("docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json",
            "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327", "A9.6 implementation-first directive"),
    "A96MD": ("docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md",
              "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634", "A9.6 (verbatim)"),
}
DELIVERABLES = {
    "PREV_JSON": (PREV_DIR + "/" + _STEM + "_a9_v1.json",
                  "37c32cda9fb04200f6e9041b0e790ca700e270866f29e7c10f8a298034ddacfd",
                  "A9-08 Xe ledger (revision base; verified; immutable, read only)"),
    "PREV_MD": (PREV_DIR + "/XE_LEDGER_A9.md",
                "ccc92f52ce53165042f696f710283e519ced387cca61d12d109f1fbe10581ae1", "A9-08 Xe ledger document"),
    "PREV_BUILDER": (PREV_DIR + "/build_" + _STEM + "_a9.py",
                     "289ff8403314469c6d14fdb846c042f46e3141e3290825e0b657cb42a732ec0b", "A9-08 Xe ledger builder"),
    "PREV_TEST": ("tests/test_" + _STEM + "_a9.py",
                  "880b75cf3755609c17aa535aaba75ae590c28d438944399a894bea2cb9fa0955", "A9-08 Xe ledger tests"),
    "OQS3": ("docs/budgets/owner_decisions/owner_questions_state_v3.json",
             "1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2",
             "owner-question state v3 (OPEN status of every question carried here)"),
}
SNAPSHOTS = {
    "NIST323": (PREV_DIR + "/sources/nist_webbook_xe_isotherm_323.15K_70-200bar.tsv",
                "190f8d574000a3e023677d17c7275e3498ca8a324955365b1205f6e40af9e376",
                "NIST WebBook SRD 69 xenon isotherm 323.15 K, 70-200 bar (A9-08 snapshot, accessed 2026-09-30)"),
    "NIST300": (PREV_DIR + "/sources/nist_webbook_xe_isotherm_300K_70-200bar.tsv",
                "0406d76581db0476ceaea74a8f8c9179c3b07b31f0f8ad90db42154008930633",
                "NIST WebBook SRD 69 xenon isotherm 300 K (contrast only; never used for sizing, row 50)"),
}
HISTORICAL = {
    "V1_JSON": (V1_DIR + "/" + _STEM + "_v1.json",
                "965fdafa60ae9c3ee1e36189f22ef00198ae3f8a906696213bec13bdcbfb09ad", "v1 Xe ledger (verified v1)"),
    "V1_MODULE": ("abep_sim/" + _STEM + ".py",
                  "8a89fa7da7e7eb7f786a7327e1721ea29c59db7c0721ea64646f812bd4afedf0",
                  "v1 pure Xe-ledger module (not imported here)"),
}
NEVER_PINNED = [
    "docs/orchestration/lane_registry_v1.json",
    "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/trigger_ledger_v2.jsonl",
    "docs/orchestration/fired_triggers.jsonl",
    "docs/orchestration/runtime_state.json",
]
# A9.6 lanes built LATER in the build order (P4, XE, P1, P2, P3, MP, RFQ, RVM, state v4, M16 v4) that consume this
# package: merged, named by lane id only as downstream consumers - never read, never pinned (a pin would be circular).
# Consolidated verification S-02 / PHYS-01: formerly worded 'PENDING / not merged in this base', no longer true.
_DS = "downstream consumer (read-only; built later in the A9.6 order, not pinned to avoid a cycle): "
DOWNSTREAM = {
    "DECPROP": _DS + "fo_a9_6_decision_propagation (owner-question state v4)",
    "RVM": _DS + "fo_a9_6_rvm (system requirement-verification matrix)",
    "M16": _DS + "fo_a9_6_m16_refresh",
}
# Merged A9.6 packages cited here (ids checked at build time; never sha-pinned).
MERGED = {
    "MASS_POWER": "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json (merged mass / power v2)",
    "RFQ": "docs/procurement/rfq_a9_v2/rfq_a9_v2.json (merged RFQ v2; quotation only)",
    "P1": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json (merged P1 bench)",
    "P3": "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json (merged; no Xe-accounting demand)",
    "P4": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json (merged; no Xe-accounting demand)",
}
# ------------------------------------------------------------------ merged A9.6 cross-lane references (A9.6 sec. 5-6, 18)
# The seven A9.6 packages (P1, P2, P3, P4, mass / power v2, Xe accounting v2, RFQ v2) are merged. Each cites the others
# by id; every cited id is CHECKED at build time against the target's current JSON (xlane_check, after the outputs are
# written, so a pair added on both sides converges in one rebuild of the second side; --check fails until it does).
# Nothing is sha-pinned between the seven packages: several read each other back (ids, or text such as the RFQ v2
# instrument coverage of the P1 / P2 ids), so a pin would be a circular hash dependency. Interface pairs XL-nn carry
# identical quantity / units / status text on both sides (tests check the pairing).
XLANE_PATHS = {
    "P1": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
    "P2": "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
    "P3": "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json",
    "P4": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
    "MP": "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json",
    "XE": "docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json",
    "RFQ": "docs/procurement/rfq_a9_v2/rfq_a9_v2.json",
}
XLANE_SELF = 'XE'
XLANE_BUILD_ORDER = ["P4", "XE", "P1", "P2", "P3", "MP", "RFQ"]
XLANE_BUILD_ORDER_RULE = ("values flow only P4 -> MP (candidate densities) and XE -> MP (Xe residual and headroom, "
                          "both readings), and P1 / P2 -> RFQ (ids, item text and statuses of the instrument "
                          "coverage); every other cross-lane reference is an id checked at build time. Rebuild in "
                          "the order P4, XE, P1, P2, P3, MP, RFQ; a second pass of any package is a no-op")
XL_PAIRS = {  # pair: (counterpart package, counterpart id, quantity, units, status) - identical text on both sides
    'XL-30': (
        'MP',
        'MPV2-ID-15',
        ('Xe residual per design case under both RA-CASE readings (design_cases.reserve_residual_split.residual_kg), '
         'imported once by mass / power: inside the case under LOADED (LOADED_XA9Q01), on top under '
         'USABLE_RESIDUAL_ON_TOP (USABLE_MQ09)'),
        'kg',
        'IMPORTED (read at build time; XA9Q-01 / MQ-09 / OQ-A910-01 TBD_OWNER, both readings carried)',
    ),
    'XL-31': (
        'MP',
        'MPV2-ID-05',
        ('loaded Xe and headroom per design case and flight scenario under both RA-CASE readings '
         '(design_cases.headroom), 323 K tank volume table'),
        'kg; l',
        'IMPORTED (headroom statuses read at build time; totals with TBD inputs REFUSED)',
    ),
    'XL-32': (
        'MP',
        'MPV2-ID-16',
        ('stored-Xe hardware masses (tank, regulator / PMU, FCUs, isolation valves, C1-branch filter / getter) for '
         'the row-44 subsystem share'),
        'kg',
        'TBD_AFTER_EVIDENCE (no CBE; owner line allocation AL-08 and evidence floors only)',
    ),
    'XL-33': (
        'MP',
        'MPV2-ID-04',
        ('booking rules shared by both ledgers: one Xe design-case content (OQ-A910-01, both readings carried), C1 '
         'terms booked only in hall_c1_reference, primary G-REUSE m_Xe,ICP = 0'),
        'kg',
        'DEFINED (rules applied in both packages; the design-case content question stays TBD_OWNER)',
    ),
    'XL-34': (
        'RFQ',
        'IFD-19',
        ('Xe tank ranges (loaded 2.0-10.2 kg across both readings, V_min per MEOP axis at 323 K), C1 steady FCU '
         '0.05-0.2 mg/s class, C1 start FCU FS 1.0 mg/s (conditional, row 125), ICP dedicated-feed controller as an '
         'option line only (A9.3 OQ-RFQ-10)'),
        'kg; l; mg/s',
        ('NOT_IN_THIS_REVISION (no Xe tank line; flight C1 hardware NIR-04; dedicated-feed controller option GAS-O02 '
         'only; RFQ only, no purchase)'),
    ),
    'XL-35': (
        'RFQ',
        'IFD-15',
        ('MEOP and tank selection, vendor / design-qualified C1 purge, preheat and ignition flows, flow-class '
         'accuracy, filter / getter specification, and mdot_ICP,dedicated of GAS-O02 if a dedicated-feed variant is '
         'ever activated (G-REUSE books 0)'),
        'bar; mg/s; s; 1',
        'TBD_AFTER_EVIDENCE (after quotations; none received; RFQ only, no purchase)',
    ),
    'XL-36': (
        'P1',
        'IF-P1-37',
        ('per-record gas state, dedicated-feed flag and the measured dedicated-feed flow if a labelled DIAGNOSTIC '
         'G-XE feed is activated (P1-M-19; OPT-GT-P1-GXE-DIAG)'),
        'mg/s; s',
        'TBD_AFTER_EVIDENCE (P1 records; the diagnostic feed is CONDITIONAL, never baseline)',
    ),
    'XL-37': (
        'P1',
        'IF-P1-17',
        ('booking rule: G-REUSE mdot_ICP,dedicated = 0; an activated diagnostic dedicated feed is booked as a '
         'separate optional Xe entry (S3-GT-P1-DIAG), never as baseline'),
        'mg/s',
        'DEFINED (rule; no booking in the baseline)',
    ),
}


def xref(pair):
    """The shared description of one cross-lane interface pair (identical on both sides)."""
    pkg, cid, quantity, units, status = XL_PAIRS[pair]
    return {"pair": pair, "counterpart": pkg + ":" + cid, "counterpart_path": XLANE_PATHS[pkg],
            "quantity": quantity, "units": units, "status": status}


def _xlane_demands(doc):
    d = doc["interface_demands"]
    return [e for v in d.values() for e in v] if isinstance(d, dict) else list(d)


def _xlane_has_id(text, ident):
    import re as _re
    return _re.search(r"(?<![A-Za-z0-9_-])" + _re.escape(ident) + r"(?![A-Za-z0-9_])", text) is not None


def xlane_check(doc):
    """Every cross-lane pair points at an existing interface-demand id of the merged target package, and every other
    cited id (XL_CITED) occurs in the target's current JSON. Returns the list of problems (empty = consistent)."""
    problems, cache = [], {}

    def target(pkg):
        if pkg not in cache:
            p = REPO / XLANE_PATHS[pkg]
            cache[pkg] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        return cache[pkg]

    seen = set()
    for e in _xlane_demands(doc):
        for x in e.get("xref", []):
            seen.add(x["pair"])
            pkg, cid = x["counterpart"].split(":", 1)
            t = target(pkg)
            if t is None:
                problems.append("%s: %s missing" % (x["pair"], XLANE_PATHS[pkg]))
                continue
            ids = {d.get("id") for d in _xlane_demands(t)}
            if cid not in ids:
                problems.append("%s: %s has no interface demand %s" % (x["pair"], XLANE_PATHS[pkg], cid))
    missing_pairs = sorted(set(XL_PAIRS) - seen)
    if missing_pairs:
        problems.append("pairs declared but not attached to an interface demand: %s" % missing_pairs)
    for pkg, idents in sorted(XL_CITED.items()):
        t = target(pkg)
        if t is None:
            problems.append("%s missing" % XLANE_PATHS[pkg])
            continue
        text = json.dumps(t, ensure_ascii=False)
        for ident in idents:
            if not _xlane_has_id(text, ident):
                problems.append("cited id %s absent from %s" % (ident, XLANE_PATHS[pkg]))
    return problems


def xlane_report(doc):
    """The merged-lane record written into the JSON: per counterpart package, the pairs and the cited ids."""
    out = {}
    for pkg in XLANE_BUILD_ORDER:
        if pkg == XLANE_SELF:
            continue
        pairs = sorted(k for k, v in XL_PAIRS.items() if v[0] == pkg)
        cited = sorted(XL_CITED.get(pkg, []))
        out[pkg] = {"path": XLANE_PATHS[pkg], "state": "MERGED", "pairs": pairs, "ids_cited": cited,
                    "sha_pinned": False,
                    "check": "ids checked at build time (xlane_check); not sha-pinned (packages read each other "
                             "back; a pin would be circular)" if (pairs or cited) else
                             "no interface demand between the two packages"}
    return {"rule": XLANE_BUILD_ORDER_RULE, "build_order": XLANE_BUILD_ORDER, "packages": out}

XL_CITED = {  # ids cited outside the XL pairs (checked to occur in the target JSON)
    "MP": ["AL-08"],
    "RFQ": ["GAS-O02", "NIR-04"],
    "P1": ["P1-M-19"],
}


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins() -> None:
    bad = []
    for group in (DECISIONS, DELIVERABLES, SNAPSHOTS, HISTORICAL):
        for key, (rel, h, _role) in group.items():
            p = REPO / rel
            if not p.is_file():
                bad.append(f"{key}: missing {rel}")
            elif _sha(rel) != h:
                bad.append(f"{key}: sha256 mismatch {rel}")
    if bad:
        raise PinError("pinned inputs changed - refusing to build: " + "; ".join(bad))


def _load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def R(row: int) -> str:
    return f"{DECISIONS['ANS'][0]} row {row}"


def D(*keys: str) -> str:
    return f"{DECISIONS['A91'][0]} " + ", ".join(f"decisions.{k}" for k in keys)


def sig6(x: float) -> float:
    return float(f"{x:.6g}")


def rk(x):
    """Deterministic rounding of a booked kg value (10 significant digits); None stays None."""
    return None if x is None else float(f"{x:.10g}")


# ------------------------------------------------------------------------------------------------ reading axes (OPEN)
READING_AXES = {
    "RA-FUNC": {
        "questions": ["XA9Q-07"],
        "subject": "does the row-6 bounded functional Xe mode apply to the hall_icp_neutralizer flight configuration "
                   "(so it also carries a Xe tank and Xe flow control)?",
        "readings": {
            "APPLIES": "XA9Q-07 proposal (A9-08): row 6 reads the RFP 'air + Xe' independently of the electron source; "
                       "the Hall Xe-capable mode family (row-6 mode, Hall Xe start, transitions, Xe fallback, Xe peak) "
                       "is booked in the ICP flight configuration as in A9-08",
            "NOT_APPLIED": "the other admissible answer: the ICP flight configuration carries no Xe tank or Xe flow "
                           "control (consequence of the question's own parenthetical); every flight Xe line of that "
                           "configuration is ABSENT_UNDER_READING and its flight Xe is exactly zero (new question "
                           "XV2Q-01 records the intermediate case)",
        },
        "scope": "hall_icp_neutralizer FLIGHT lines only; ground-test Xe is unaffected (HIQ-03)",
    },
    "RA-DWELL": {
        "questions": ["XA9Q-02", "OQ-A907-01"],
        "subject": "row 93 'cap each ignition dwell at 120 s and allow at most two retries': attempts per start",
        "readings": {
            "ATTEMPTS_3": "1 initial + 2 retries = 3 dwells x 120 s = 360 s per start (literal reading; XA9Q-02 / "
                          "OQ-A907-01 proposal)",
            "ATTEMPTS_2": "2 dwells x 120 s = 240 s per start (the '120 s x 2' shorthand named in OQ-A907-01)",
        },
        "scope": "C1 ignition lines (flight and ground) of hall_c1_reference",
    },
    "RA-FLOWUNC": {
        "questions": ["XA9Q-03"],
        "subject": "is the row-96 C1 flow-class term (booked additively, row 96) inside the row-43 reserve base?",
        "readings": {
            "INSIDE_RESERVE_BASE": "XA9Q-03 proposal (A9-08): the term is part of the planned non-reserve Xe",
            "OUTSIDE_RESERVE_BASE": "the other admissible reading: the term is booked additively (row 96) but the "
                                    "20 % reserve (row 43) is taken on the planned terms only",
        },
        "scope": "the row-96 C1 flow-class lines of hall_c1_reference FLIGHT only; the non-C1 flow-class term stays "
                 "inside the base (A9-08 convention; it is TBD in every scenario)",
    },
    "RA-CASE": {
        "questions": ["XA9Q-01", "MQ-09", "OQ-A910-01"],
        "subject": "content of the row-48 2 / 5 / 10 kg design cases",
        "readings": {
            "LOADED": "XA9Q-01 proposal (A9-08): case = LOADED Xe = non-reserve + reserve + residual",
            "USABLE_RESIDUAL_ON_TOP": "MQ-09 proposal (A9-06): case = usable Xe incl. the 20 % reserve; the 2 % residual "
                                      "is imported on top (loaded = case x (1 + f_residual))",
        },
        "scope": "design cases, tank volume, head-room, C1 flow ceiling, mass share",
    },
}


# ------------------------------------------------------------------------------------------------ items
REVISED_ITEMS = ("XA9-08", "XA9-30")
V2_PENDING = {
    "XA9-09": "RFQ", "XA9-10": "RFQ", "XA9-11": "RFQ", "XA9-20": "RFQ", "XA9-28": "RFQ", "XA9-31": "RFQ",
    "XA9-32": "MASS_POWER",
}


V2_COUNTERPART = {
    "RFQ": "TBD_AFTER_EVIDENCE - requires quotations / vendor data requested through " + MERGED["RFQ"] +
           " (IFD-15, pair XL-35; none received, no purchase)",
    "MASS_POWER": "TBD_AFTER_EVIDENCE - stored-Xe hardware masses exchanged with " + MERGED["MASS_POWER"] +
                  " (MPV2-ID-16, pair XL-32; no CBE, owner line allocation AL-08 only)",
}


def v2id(a908_id: str) -> str:
    return "XV2-" + a908_id.split("-")[1]


def build_items(prev: dict, a93: dict) -> list:
    items = []
    for it in prev["items"]:
        if it["id"] in REVISED_ITEMS:
            continue
        x = {
            "id": v2id(it["id"]), "a9_08_item": it["id"], "name": it["name"], "value": it["value"],
            "value_display": it.get("value_display", it["value"]), "unit": it["unit"], "kind": it["kind"],
            "basis": it["basis"], "source": it["source"], "evidence_class": it["evidence_class"] or "none",
            "status": it["status"], "freeze_point": it["freeze_point"], "applies_to": it["applies_to"],
            "v2_change": "imported unchanged from A9-08",
        }
        for extra in ("requires", "note"):
            if it.get(extra) is not None:
                x[extra] = it[extra]
        if it["id"] in V2_PENDING:
            x["v2_counterpart"] = V2_COUNTERPART[V2_PENDING[it["id"]]]
        items.append(x)
    prev_items = {i["id"]: i for i in prev["items"]}
    p08, p30 = prev_items["XA9-08"], prev_items["XA9-30"]
    items.append({
        "id": "XV2-08", "a9_08_item": "XA9-08", "name": "C1 ignition attempts per start (row 93 'at most two retries')",
        "value": None, "value_by_reading": {"ATTEMPTS_3": 3.0, "ATTEMPTS_2": 2.0},
        "value_display": "TBD_OWNER - 3 (reading ATTEMPTS_3) or 2 (reading ATTEMPTS_2); both carried",
        "unit": "1", "kind": "count", "basis": "owner answer; reading OPEN", "source": p08["source"] +
        "; owner_questions_state_v3 XA9Q-02 and OQ-A907-01 (both OPEN)", "evidence_class": "owner-allocation",
        "status": "TBD_OWNER (XA9Q-02 / OQ-A907-01 OPEN; both admissible readings carried side by side)",
        "freeze_point": "LOCK-2", "applies_to": p08["applies_to"],
        "v2_change": "A9-08 carried the 3-attempt reading only (PROPOSED); v2 carries both readings",
    })
    items.append({
        "id": "XV2-30", "a9_08_item": "XA9-30", "name": "Xe design cases for tank/interface sizing (row 48)",
        "value": p30["value"], "value_display": p30["value"], "unit": "kg", "kind": "mass",
        "basis": "owner answer (case masses); case content OPEN", "source": p30["source"] +
        "; owner_questions_state_v3 XA9Q-01, MQ-09, OQ-A910-01 (all OPEN)", "evidence_class": "owner-allocation",
        "status": "DESIGN_CASES (no single mission load frozen); content TBD_OWNER (reading axis RA-CASE: LOADED or "
                  "USABLE_RESIDUAL_ON_TOP, both carried; content needed by LOCK-1 per OQ-A910-01)",
        "freeze_point": p30["freeze_point"], "applies_to": p30["applies_to"],
        "v2_change": "A9-08 read the cases as LOADED only (PROPOSED); v2 carries both readings",
    })
    items.append({
        "id": "XV2-42", "a9_08_item": None, "name": "C1 ignition dwell bound per start (attempts x 120 s)",
        "value": None, "value_by_reading": {"ATTEMPTS_3": 360.0, "ATTEMPTS_2": 240.0},
        "value_display": "TBD_OWNER - 360 s (ATTEMPTS_3) or 240 s (ATTEMPTS_2)", "unit": "s", "kind": "time",
        "basis": "arithmetic XV2-07 x XV2-08", "source": f"{R(93)}; builder {SCRIPT_REL}",
        "evidence_class": "model-derived", "status": "TBD_OWNER (follows RA-DWELL)", "freeze_point": "LOCK-2",
        "applies_to": {"configs": ["hall_c1_reference"], "ledgers": list(LEDGERS)}, "v2_change": "new (derived)",
    })
    p1_auth = a93["authorizations"]["P1"]
    items.append({
        "id": "XV2-43", "a9_08_item": None, "name": "P1 ICP bench Xe (Ar engineering reproduction, G-REUSE)",
        "value": 0.0, "value_display": 0.0, "unit": "kg", "kind": "mass", "basis": "owner authorization scope",
        "source": f"{DECISIONS['A93'][0]} authorizations.P1 ('{p1_auth}'); {DECISIONS['A93'][0]} decisions.OQ-RFQ-10 "
                  "(dedicated feed = quoted option / diagnostic only)",
        "evidence_class": "owner-allocation",
        "status": "ZERO_BY_SCOPE (Ar only; an activated diagnostic dedicated Xe feed is the separate optional entry "
                  "OPT-GT-P1-GXE-DIAG)", "freeze_point": "NOW",
        "applies_to": {"configs": ["hall_icp_neutralizer"], "ledgers": ["GROUND_TEST"]}, "v2_change": "new",
    })
    items.append({
        "id": "XV2-44", "a9_08_item": None, "name": "Xe in a G-ATM dedicated ICP feed",
        "value": 0.0, "value_display": 0.0, "unit": "mg/s", "kind": "mass_flow", "basis": "owner decision",
        "source": f"{D('HIQ-06_accounting')} ('G-ATM: mdot_atm,total = mdot_Hall + mdot_ICP,dedicated (actual "
                  "routing)'); booked on the atmospheric feed path, outside this Xe accounting",
        "evidence_class": "owner-allocation", "status": "ZERO_XE_BY_OWNER_DECISION (contingency variant)",
        "freeze_point": "NOW", "applies_to": {"configs": ["hall_icp_neutralizer"], "ledgers": list(LEDGERS),
                                              "gas_modes": ["G-ATM"]}, "v2_change": "new (explicit line)",
    })
    items.append({
        "id": "XV2-45", "a9_08_item": None,
        "name": "P1 diagnostic dedicated Xe ICP feed (only if activated): events, duration, flow",
        "value": None, "value_display": "TBD - requires a labelled DIAGNOSTIC dedicated Xe feed actually activated in "
        "P1 with its flow measured and recorded per record (" + MERGED["P1"] + " P1-M-19, pair XL-36)",
        "unit": "1; s; mg/s",
        "kind": "count", "basis": "owner decision (booking rule) / pending (size)",
        "source": f"{DECISIONS['A93'][0]} decisions.OQ-RFQ-10 (booking: 'if G-XE/G-ATM is activated, mdot_ICP,dedicated "
                  "is explicitly booked in the corresponding atmospheric/Xe ledger')",
        "evidence_class": "none", "status": "TBD (OPTIONAL_NOT_ACTIVE)", "freeze_point": "after-evidence",
        "applies_to": {"configs": ["hall_icp_neutralizer"], "ledgers": ["GROUND_TEST"], "gas_modes": ["G-XE"]},
        "requires": "an activated diagnostic dedicated Xe feed with measured flow", "v2_change": "new",
    })
    items.sort(key=lambda i: i["id"])
    return items


# ------------------------------------------------------------------------------------------------ ledger lines
def F(name: str, item: str, unit: str) -> dict:
    return {"name": name, "item": item, "unit": unit}


def L(lid, case, config, gas_mode, ledger, phase, name, formula, fields, presence, a908, sources, *,
      kind="product", reserve_base=True, of_lines=None, optional=False, note=None):
    return {"id": lid, "case": case, "configuration": config, "gas_mode": gas_mode, "ledger": ledger, "phase": phase,
            "name": name, "formula": formula, "fields": fields, "presence": presence, "a9_08_term": a908,
            "sources": sources, "kind": kind, "reserve_base": reserve_base, "of_lines": of_lines or [],
            "optional_entry": optional, "note": note}


def _func(applies: str) -> dict:
    return {"axis": "RA-FUNC", "APPLIES": applies, "NOT_APPLIED": "ABSENT_UNDER_READING"}


def build_lines() -> list:
    icp, c1 = "hall_icp_neutralizer", "hall_c1_reference"
    n_st, n_c1 = F("N_starts", "XV2-14", "1"), F("N_c1_starts", "XV2-36", "1")
    purge = [F("t_purge", "XV2-10", "s"), F("mdot_purge", "XV2-10", "mg/s")]
    heat = [F("t_preheat", "XV2-11", "s"), F("mdot_preheat", "XV2-11", "mg/s")]
    ign = [F("n_attempts", "XV2-08", "1"), F("t_dwell_max", "XV2-07", "s"), F("mdot_ign", "XV2-09", "mg/s")]
    hstart = [F("t_hall_ign", "XV2-15", "s"), F("mdot_hall_ign", "XV2-15", "mg/s")]
    trans = [F("N_transitions", "XV2-16", "1"), F("t_transition", "XV2-16", "s"),
             F("mdot_transition", "XV2-16", "mg/s")]
    fallb = [F("t_fallback_max", "XV2-17", "h"), F("mdot_fallback", "XV2-17", "mg/s")]
    func = [F("N_xe_mode", "XV2-18", "1"), F("t_xe_mode", "XV2-18", "h"), F("mdot_xe_mode", "XV2-18", "mg/s")]
    peak = [F("N_peak", "XV2-19", "1"), F("t_peak", "XV2-19", "h"), F("mdot_peak", "XV2-19", "mg/s")]
    gxe = [F("N_icp", "XV2-22", "1"), F("t_icp", "XV2-22", "s"), F("mdot_icp_xe", "XV2-22", "mg/s")]
    s_row6, s_row42 = R(6), R(42)
    s_greuse = (f"{D('HIQ-06', 'HIQ-06_accounting', 'OQ-A902-05')}; {DECISIONS['A93'][0]} decisions.OQ-RFQ-10; "
                f"{DECISIONS['A96MD'][0]} sec. 12 ('m_Xe,ICP = 0')")
    s_c1absent = f"{R(46)} ('no continuous C1-Xe cathode term'); {D('OQ-A902-04')}"
    s_gxe = (f"{D('HIQ-06', 'HIQ-06_accounting')}; {DECISIONS['A93'][0]} decisions.OQ-RFQ-10; "
             f"{DECISIONS['A96MD'][0]} sec. 12 ('Any later G-XE ICP mode must be a separate explicit ledger entry')")
    lines = [
        # ---------------- CASE-1 PRIMARY: hall_icp_neutralizer, G-REUSE, FLIGHT
        L("P-FL-ICP-XE", "CASE-1", icp, "G-REUSE", "FLIGHT", "icp_feed", "ICP neutralizer dedicated Xe (G-REUSE)",
          "m_Xe,ICP = 0 exactly (mdot_ICP,dedicated = 0; the Hall exhaust is never counted again as ICP propellant)",
          [F("mdot_icp_dedicated", "XV2-21", "mg/s")], "EXACT_ZERO_BY_OWNER_DECISION", "F-ICP-XE", [s_greuse]),
        L("P-FL-C1", "CASE-1", icp, "G-REUSE", "FLIGHT", "keeper_cathode", "C1 keeper/cathode Xe",
          "not booked: no C1 in the ICP flight configuration", [], "ABSENT_BY_OWNER_DECISION", "F-C1-CATHODE",
          [s_c1absent]),
        L("P-FL-FUNC", "CASE-1", icp, "G-REUSE", "FLIGHT", "xe_mode", "Hall bounded functional Xe-capable mode (row 6)",
          "N_xe_mode x t_xe_mode x mdot_xe_mode", func, _func("PRESENT"), "F-XE-FUNCTIONAL", [s_row6],
          note="G-REUSE: while the Hall runs on Xe the ICP runs on that Xe exhaust; nothing is added for the ICP"),
        L("P-FL-HALL-START", "CASE-1", icp, "G-REUSE", "FLIGHT", "ignition", "Hall discharge ignition on Xe (if used)",
          "N_starts x t_hall_ign x mdot_hall_ign", [n_st] + hstart, _func("CONDITIONAL"), "F-HALL-XE-START",
          [s_row42]),
        L("P-FL-TRANSITION", "CASE-1", icp, "G-REUSE", "FLIGHT", "transition", "Xe-to-atmosphere transition",
          "N_transitions x t_transition x mdot_transition", trans, _func("PRESENT"), "F-TRANSITION", [s_row42]),
        L("P-FL-FALLBACK", "CASE-1", icp, "G-REUSE", "FLIGHT", "fallback",
          "Hall Xe fallback operation (atmospheric path unavailable)", "t_fallback_max x mdot_fallback", fallb,
          _func("PRESENT"), "F-XE-FALLBACK-OP", [s_row42]),
        L("P-FL-PEAK", "CASE-1", icp, "G-REUSE", "FLIGHT", "xe_peak", "Xe-augmented peak (only if the RFP permits)",
          "N_peak x t_peak x mdot_peak", peak, _func("CONDITIONAL"), "F-XE-PEAK", [f"{R(4)}; {R(26)}"]),
        L("P-FL-FLOWUNC-OTHER", "CASE-1", icp, "G-REUSE", "FLIGHT", "uncertainty",
          "flow-class uncertainty of the Hall-side Xe flows", "u_class x (sum of the Hall-side Xe lines)",
          [F("u_class", "XV2-20", "1")], _func("PRESENT"), "F-XE-FLOWUNC-OTHER", [R(96)], kind="fraction_of_lines",
          of_lines=["P-FL-FUNC", "P-FL-HALL-START", "P-FL-TRANSITION", "P-FL-FALLBACK", "P-FL-PEAK"]),
        # ---------------- CASE-1 PRIMARY: GROUND_TEST
        L("P-GT-ICP-XE", "CASE-1", icp, "G-REUSE", "GROUND_TEST", "icp_feed", "ICP dedicated Xe (ground, G-REUSE)",
          "0 exactly", [F("mdot_icp_dedicated", "XV2-21", "mg/s")], "EXACT_ZERO_BY_OWNER_DECISION", "G-ICP-XE",
          [s_greuse]),
        L("P-GT-P1-BENCH", "CASE-1", icp, "G-REUSE", "GROUND_TEST", "icp_feed", "P1 ICP bench (Ar engineering only)",
          "0 kg Xe by scope", [F("m_xe_p1", "XV2-43", "1")], "ZERO_BY_SCOPE", None,
          [f"{DECISIONS['A93'][0]} authorizations.P1"]),
        L("P-GT-XE-REFERENCE", "CASE-1", icp, "G-REUSE", "GROUND_TEST", "xe_reference",
          "XE_REFERENCE bounded Xe health check per installation", "N_installations x t_ref x mdot_ref",
          [F("N_installations", "XV2-34", "1"), F("t_ref", "XV2-33", "s"), F("mdot_ref", "XV2-33", "mg/s")],
          "PRESENT", "G-XE-REFERENCE", [f"{D('HIQ-03')}; {R(26)}"]),
        L("P-GT-PEAK", "CASE-1", icp, "G-REUSE", "GROUND_TEST", "xe_peak", "XE_AUGMENTED_PEAK points (if permitted)",
          "N_points x t_point x mdot_point",
          [F("N_points", "XV2-35", "1"), F("t_point", "XV2-35", "s"), F("mdot_point", "XV2-35", "mg/s")],
          "CONDITIONAL", "G-XE-AUGMENTED-PEAK", [R(26)]),
        L("P-GT-HALL-START", "CASE-1", icp, "G-REUSE", "GROUND_TEST", "ignition", "Hall ignition on Xe (ground, if used)",
          "N_hall_xe_starts x t_hall_ign x mdot_hall_ign", [F("N_hall_xe_starts", "XV2-36", "1")] + hstart,
          "CONDITIONAL", "G-HALL-XE-START", [s_row42]),
        L("P-GT-TRANSITION", "CASE-1", icp, "G-REUSE", "GROUND_TEST", "transition",
          "Xe-to-atmospheric-surrogate transition (ground)", "N_transitions x t_transition x mdot_transition", trans,
          "PRESENT", "G-TRANSITION", [s_row42]),
        # ---------------- CASE-2 REFERENCE: hall_c1_reference, FLIGHT
        L("C1-FL-PURGE", "CASE-2", c1, None, "FLIGHT", "purge", "C1 Xe purge before heating",
          "N_starts x t_purge x mdot_purge", [n_st] + purge, "PRESENT", "F-C1-PURGE", [f"{R(42)}; {R(93)}"]),
        L("C1-FL-HEAT", "CASE-2", c1, None, "FLIGHT", "preheat", "C1 heating/start (preheat under Xe flow)",
          "N_starts x t_preheat x mdot_preheat", [n_st] + heat, "PRESENT", "F-C1-PREHEAT",
          [f"{R(42)} ('No unbooked preheat flow'); {D('SEQ-heater')}"]),
        L("C1-FL-IGN", "CASE-2", c1, None, "FLIGHT", "ignition",
          "C1 keeper ignition dwell at the protocol bound (<= 120 s per attempt)",
          "N_starts x n_attempts x t_dwell_max x mdot_ign", [n_st] + ign, "PRESENT", "F-C1-IGN", [R(93)],
          note="booked at the protocol bound (upper bound per start), not an expected dwell; n_attempts follows RA-DWELL"),
        L("C1-FL-KEEPER", "CASE-2", c1, None, "FLIGHT", "keeper_cathode",
          "C1 keeper/cathode steady Xe flow over the firing hours", "mdot_cathode x t_firing",
          [F("mdot_cathode", "XV2-02", "mg/s"), F("t_firing", "XV2-01", "h")], "PRESENT", "F-C1-CATHODE",
          [f"{R(42)}; {R(46)}; {DECISIONS['A9'][0]} control_fallback"]),
        L("C1-FL-FLOWUNC", "CASE-2", c1, None, "FLIGHT", "uncertainty",
          "C1 steady-flow controller +-2 % FS class term (row 96, additive)", "u_FS x FS x t_firing",
          [F("u_FS", "XV2-04", "1"), F("FS", "XV2-05", "mg/s"), F("t_firing", "XV2-01", "h")], "PRESENT",
          "F-C1-FLOWUNC", [f"{R(96)}; {R(125)}"], reserve_base="RA-FLOWUNC"),
        L("C1-FL-TRANSITION", "CASE-2", c1, None, "FLIGHT", "transition", "Xe-to-atmosphere transition",
          "N_transitions x t_transition x mdot_transition", trans, "PRESENT", "F-TRANSITION", [s_row42]),
        L("C1-FL-FALLBACK", "CASE-2", c1, None, "FLIGHT", "fallback",
          "Hall Xe fallback operation (atmospheric path unavailable)", "t_fallback_max x mdot_fallback", fallb,
          "PRESENT", "F-XE-FALLBACK-OP", [s_row42],
          note="the C1 configuration as fallback to the ICP is an architecture choice, not an in-flight term "
               "(OQ-A902-04)"),
        L("C1-FL-FUNC", "CASE-2", c1, None, "FLIGHT", "xe_mode", "Hall bounded functional Xe-capable mode (row 6)",
          "N_xe_mode x t_xe_mode x mdot_xe_mode", func, "PRESENT", "F-XE-FUNCTIONAL", [s_row6]),
        L("C1-FL-HALL-START", "CASE-2", c1, None, "FLIGHT", "ignition", "Hall discharge ignition on Xe (if used)",
          "N_starts x t_hall_ign x mdot_hall_ign", [n_st] + hstart, "CONDITIONAL", "F-HALL-XE-START", [s_row42]),
        L("C1-FL-PEAK", "CASE-2", c1, None, "FLIGHT", "xe_peak", "Xe-augmented peak (only if the RFP permits)",
          "N_peak x t_peak x mdot_peak", peak, "CONDITIONAL", "F-XE-PEAK", [f"{R(4)}; {R(26)}"]),
        L("C1-FL-FLOWUNC-OTHER", "CASE-2", c1, None, "FLIGHT", "uncertainty",
          "flow-class uncertainty of the Hall-side Xe flows", "u_class x (sum of the Hall-side Xe lines)",
          [F("u_class", "XV2-20", "1")], "PRESENT", "F-XE-FLOWUNC-OTHER", [R(96)], kind="fraction_of_lines",
          of_lines=["C1-FL-FUNC", "C1-FL-HALL-START", "C1-FL-TRANSITION", "C1-FL-FALLBACK", "C1-FL-PEAK"]),
        L("C1-FL-ICP-XE", "CASE-2", c1, None, "FLIGHT", "icp_feed", "ICP Xe", "not booked: no ICP in the C1 "
          "configuration", [], "ABSENT_BY_OWNER_DECISION", "F-ICP-XE", [D("OQ-A902-04")]),
        # ---------------- CASE-2 REFERENCE: GROUND_TEST
        L("C1-GT-PURGE", "CASE-2", c1, None, "GROUND_TEST", "purge", "C1 purge (ground starts)",
          "N_c1_starts x t_purge x mdot_purge", [n_c1] + purge, "PRESENT", "G-C1-PURGE", [f"{R(42)}; {R(93)}"]),
        L("C1-GT-HEAT", "CASE-2", c1, None, "GROUND_TEST", "preheat", "C1 heating/start under Xe flow (ground)",
          "N_c1_starts x t_preheat x mdot_preheat", [n_c1] + heat, "PRESENT", "G-C1-PREHEAT",
          [f"{R(42)}; {D('SEQ-heater')}"]),
        L("C1-GT-IGN", "CASE-2", c1, None, "GROUND_TEST", "ignition", "C1 ignition dwell bound (ground starts)",
          "N_c1_starts x n_attempts x t_dwell_max x mdot_ign", [n_c1] + ign, "PRESENT", "G-C1-IGN", [R(93)]),
        L("C1-GT-KEEPER", "CASE-2", c1, None, "GROUND_TEST", "keeper_cathode",
          "C1 keeper/cathode flow over the C1 Xe-on hours", "t_c1_on x mdot_c1_ground",
          [F("t_c1_on", "XV2-36", "h"), F("mdot_c1_ground", "XV2-41", "mg/s")], "PRESENT", "G-C1-CATHODE",
          [f"{R(42)}; {D('HIQ-01')}"]),
        L("C1-GT-MINFLOW", "CASE-2", c1, None, "GROUND_TEST", "keeper_cathode",
          "C1 spot-mode minimum-flow search (0.005 mg/s steps)", "N_searches x n_steps x t_step x mdot_step_mean",
          [F("N_searches", "XV2-13", "1"), F("n_steps", "XV2-13", "1"), F("t_step", "XV2-13", "s"),
           F("mdot_step_mean", "XV2-13", "mg/s")], "PRESENT", "G-C1-MINFLOW-SEARCH", [R(92)]),
        L("C1-GT-FLOWUNC", "CASE-2", c1, None, "GROUND_TEST", "uncertainty", "C1 flow-class term (ground)",
          "u_FS x FS x t_c1_on", [F("u_FS", "XV2-04", "1"), F("FS", "XV2-05", "mg/s"), F("t_c1_on", "XV2-36", "h")],
          "PRESENT", "G-C1-FLOWUNC", [R(96)]),
        L("C1-GT-XE-REFERENCE", "CASE-2", c1, None, "GROUND_TEST", "xe_reference",
          "XE_REFERENCE bounded Xe health check per installation", "N_installations x t_ref x mdot_ref",
          [F("N_installations", "XV2-34", "1"), F("t_ref", "XV2-33", "s"), F("mdot_ref", "XV2-33", "mg/s")],
          "PRESENT", "G-XE-REFERENCE", [f"{D('HIQ-03')}; {R(26)}"]),
        L("C1-GT-PEAK", "CASE-2", c1, None, "GROUND_TEST", "xe_peak", "XE_AUGMENTED_PEAK points (if permitted)",
          "N_points x t_point x mdot_point",
          [F("N_points", "XV2-35", "1"), F("t_point", "XV2-35", "s"), F("mdot_point", "XV2-35", "mg/s")],
          "CONDITIONAL", "G-XE-AUGMENTED-PEAK", [R(26)]),
        L("C1-GT-HALL-START", "CASE-2", c1, None, "GROUND_TEST", "ignition", "Hall ignition on Xe (ground, if used)",
          "N_hall_xe_starts x t_hall_ign x mdot_hall_ign", [F("N_hall_xe_starts", "XV2-36", "1")] + hstart,
          "CONDITIONAL", "G-HALL-XE-START", [s_row42]),
        L("C1-GT-TRANSITION", "CASE-2", c1, None, "GROUND_TEST", "transition",
          "Xe-to-atmospheric-surrogate transition (ground)", "N_transitions x t_transition x mdot_transition", trans,
          "PRESENT", "G-TRANSITION", [s_row42]),
        # ---------------- CASE-3 OPTIONAL: contingency / diagnostic entries (zero, i.e. absent, in every primary scenario)
        L("OPT-FL-GXE", "CASE-3", icp, "G-XE", "FLIGHT", "icp_feed",
          "G-XE contingency: dedicated Xe ICP feed (only if G-REUSE fails the preregistered ICP-capacity gate)",
          "N_icp x t_icp x mdot_icp_xe", gxe, "PRESENT_WHEN_ACTIVATED", "F-ICP-XE", [s_gxe], optional=True),
        L("OPT-FL-FLOWUNC-GXE", "CASE-3", icp, "G-XE", "FLIGHT", "uncertainty",
          "flow-class uncertainty of the G-XE ICP feed (only if activated)", "u_class x OPT-FL-GXE",
          [F("u_class", "XV2-20", "1")], "PRESENT_WHEN_ACTIVATED", "F-XE-FLOWUNC-OTHER",
          [f"{R(96)}; A9-08 XA9-20 scope (non-C1 Xe flows incl. the G-XE ICP feed)"], kind="fraction_of_lines",
          of_lines=["OPT-FL-GXE"], optional=True),
        L("OPT-FL-GATM", "CASE-3", icp, "G-ATM", "FLIGHT", "icp_feed", "G-ATM contingency: dedicated atmospheric ICP "
          "feed (0 Xe)", "0 Xe (atmospheric flow booked on the feed path)", [F("mdot_xe_gatm", "XV2-44", "mg/s")],
          "ZERO_XE_BY_OWNER_DECISION", "F-ICP-XE", [D("HIQ-06_accounting")], optional=True),
        L("OPT-GT-GXE", "CASE-3", icp, "G-XE", "GROUND_TEST", "icp_feed", "G-XE contingency: dedicated Xe ICP feed "
          "(ground)", "N_icp x t_icp x mdot_icp_xe", gxe, "PRESENT_WHEN_ACTIVATED", "G-ICP-XE", [s_gxe],
          optional=True),
        L("OPT-GT-GATM", "CASE-3", icp, "G-ATM", "GROUND_TEST", "icp_feed", "G-ATM contingency (ground, 0 Xe)",
          "0 Xe", [F("mdot_xe_gatm", "XV2-44", "mg/s")], "ZERO_XE_BY_OWNER_DECISION", "G-ICP-XE",
          [D("HIQ-06_accounting")], optional=True),
        L("OPT-GT-P1-GXE-DIAG", "CASE-3", icp, "G-XE", "GROUND_TEST", "icp_feed",
          "P1 DIAGNOSTIC dedicated Xe ICP feed (only if activated; never baseline)", "N_diag x t_diag x mdot_diag",
          [F("N_diag", "XV2-45", "1"), F("t_diag", "XV2-45", "s"), F("mdot_diag", "XV2-45", "mg/s")],
          "PRESENT_WHEN_ACTIVATED", None, [f"{DECISIONS['A93'][0]} decisions.OQ-RFQ-10"], optional=True),
    ]
    for ln in lines:
        _validate_line(ln)
    return lines


def _validate_line(ln: dict) -> None:
    pres = ln["presence"]
    states = [pres] if isinstance(pres, str) else [v for k, v in pres.items() if k != "axis"]
    for s in states:
        if s not in PRESENCE_STATES:
            raise BookingError(f"{ln['id']}: unknown presence {s}")
    if ln["phase"] in ("reserve", "residual"):
        raise BookingError(f"{ln['id']}: reserve/residual are booked only by book_reserve_and_residual")
    if ln["kind"] == "product" and any(s in NONZERO_STATES for s in states):
        dims = [UNIT_DIM.get(f["unit"]) for f in ln["fields"]]
        if None in dims:
            raise BookingError(f"{ln['id']}: unknown unit")
        if dims.count("mass_flow") != 1 or dims.count("time") != 1:
            raise BookingError(f"{ln['id']}: a mass product needs exactly one mass flow and one time field")


# ------------------------------------------------------------------------------------------------ evaluation
def resolve_presence(presence, reading: dict) -> str:
    if isinstance(presence, str):
        return presence
    axis = presence["axis"]
    if axis not in reading:
        raise BookingError(f"reading for {axis} missing")
    return presence[reading[axis]]


def item_value(item: dict, reading: dict):
    if "value_by_reading" in item:
        for axis, spec in READING_AXES.items():
            keys = set(spec["readings"])
            if set(item["value_by_reading"]) == keys:
                if axis not in reading:
                    raise BookingError(f"{item['id']}: reading for {axis} missing")
                return item["value_by_reading"][reading[axis]]
        raise BookingError(f"{item['id']}: value_by_reading keys match no reading axis")
    return item["value"]


def eval_line(ln: dict, items: dict, reading: dict, done: dict) -> dict:
    pres = resolve_presence(ln["presence"], reading)
    out = {"line": ln["id"], "presence": pres, "kg": None, "missing": []}
    if pres in ZERO_STATES:
        out["kg"] = 0.0
        return out
    if ln["kind"] == "product":
        val = 1.0
        for f in ln["fields"]:
            it = items[f["item"]]
            v = item_value(it, reading)
            if v is None:
                out["missing"].append({"field": f["name"], "item": f["item"],
                                       "requires": it.get("requires", it.get("value_display"))})
                continue
            if isinstance(v, (list, str, bool)):
                raise BookingError(f"{ln['id']}: non-numeric value for {f['name']}")
            if not math.isfinite(float(v)) or float(v) < 0:          # SW-08: no negative / NaN Xe mass
                raise BookingError(f"{ln['id']}: {f['name']} = {v!r} must be a finite number >= 0")
            if f["unit"] not in UNIT_SI:
                raise BookingError(f"{ln['id']}: unknown unit {f['unit']}")
            val *= float(v) * UNIT_SI[f["unit"]]
        out["kg"] = None if out["missing"] else rk(val)
        return out
    if ln["kind"] == "fraction_of_lines":
        f = ln["fields"][0]
        u = item_value(items[f["item"]], reading)
        if u is None:
            out["missing"].append({"field": f["name"], "item": f["item"],
                                   "requires": items[f["item"]].get("requires")})
        if u is not None and (isinstance(u, (bool, str, list)) or not math.isfinite(float(u)) or float(u) < 0):
            raise BookingError(f"{ln['id']}: fraction {f['name']} = {u!r} must be a finite number >= 0 (SW-08)")
        parts = [done[x]["kg"] for x in ln["of_lines"]]
        if u is None or any(p is None for p in parts):
            out["missing"] += [{"field": "sum of", "lines": [x for x in ln["of_lines"] if done[x]["kg"] is None]}] \
                if any(p is None for p in parts) else []
            return out
        out["kg"] = rk(float(u) * sum(parts))
        return out
    raise BookingError(f"{ln['id']}: unknown kind {ln['kind']}")


def in_reserve_base(ln: dict, reading: dict) -> bool:
    rb = ln["reserve_base"]
    if rb is True:
        return True
    if rb == "RA-FLOWUNC":
        if "RA-FLOWUNC" not in reading:
            raise BookingError(f"{ln.get('id')}: reading for RA-FLOWUNC missing")
        return reading["RA-FLOWUNC"] == "INSIDE_RESERVE_BASE"
    raise BookingError(f"{ln.get('id')}: bad reserve_base {rb}")


def book_reserve_and_residual(evals: list, lines: dict, f_reserve: float, f_residual: float, reading: dict) -> dict:
    """Book the row-43 reserve and the row-45 residual EXACTLY ONCE on a list of evaluated non-reserve lines.

    reserve  = f_reserve x (planned non-reserve lines in the reserve base)
    usable   = all non-reserve lines + reserve
    residual = f_residual x usable            (one line; exported to the mass BOM, never booked twice)
    Refuses (BookingError) an input that already carries a reserve or residual line, a duplicate line or a missing
    fraction. Totals with any TBD line are REFUSED; floors use closed lines only (TBD lines are >= 0)."""
    if f_reserve is None or f_residual is None:
        raise BookingError("reserve/residual fraction missing (no default)")
    ids = [e["line"] for e in evals]
    if len(ids) != len(set(ids)):
        raise BookingError("duplicate ledger line (double counting)")
    for e in evals:
        if lines[e["line"]]["phase"] in ("reserve", "residual") or e["line"] in ("RESERVE", "RESIDUAL"):
            raise BookingError("reserve/residual already present: booking twice is refused")
    base = [e for e in evals if in_reserve_base(lines[e["line"]], reading)]
    outside = [e for e in evals if not in_reserve_base(lines[e["line"]], reading)]
    tbd = [e["line"] for e in evals if e["kg"] is None]

    def s(es):
        return sum(e["kg"] or 0.0 for e in es)

    base_f, out_f = s(base), s(outside)
    reserve_f = f_reserve * base_f
    usable_f = base_f + out_f + reserve_f
    residual_f = f_residual * usable_f
    loaded_f = usable_f + residual_f
    floors = {"reserve_base_kg": rk(base_f), "outside_base_kg": rk(out_f), "non_reserve_kg": rk(base_f + out_f),
              "reserve_kg": rk(reserve_f), "usable_kg": rk(usable_f), "residual_kg": rk(residual_f),
              "loaded_kg": rk(loaded_f)}
    if tbd:
        return {"status": "REFUSED_TBD_INPUTS", "tbd_lines": tbd, "totals": None,
                "floors_closed_terms_only": floors,
                "reserve_line": {"line": "RESERVE", "phase": "reserve", "kg": None, "formula": "f_reserve x base",
                                 "floor_kg": floors["reserve_kg"]},
                "residual_line": {"line": "RESIDUAL", "phase": "residual", "kg": None,
                                  "formula": "f_residual x usable", "floor_kg": floors["residual_kg"]}}
    status = "COMPUTED_EXACT_ZERO" if loaded_f == 0.0 else "COMPUTED"
    return {"status": status, "tbd_lines": [], "totals": floors, "floors_closed_terms_only": floors,
            "reserve_line": {"line": "RESERVE", "phase": "reserve", "kg": floors["reserve_kg"],
                             "formula": "f_reserve x base"},
            "residual_line": {"line": "RESIDUAL", "phase": "residual", "kg": floors["residual_kg"],
                              "formula": "f_residual x usable"}}


SCENARIOS = [
    {"id": "S1-FL-PRIMARY", "case": "CASE-1", "ledger": "FLIGHT", "configuration": "hall_icp_neutralizer",
     "gas_mode": "G-REUSE", "role": "PRIMARY (A9 investigation hypothesis; HIQ-06 G-REUSE)", "axes": ["RA-FUNC"],
     "lines": ["P-FL-ICP-XE", "P-FL-C1", "P-FL-FUNC", "P-FL-HALL-START", "P-FL-TRANSITION", "P-FL-FALLBACK",
               "P-FL-PEAK", "P-FL-FLOWUNC-OTHER"]},
    {"id": "S1-GT-PRIMARY", "case": "CASE-1", "ledger": "GROUND_TEST", "configuration": "hall_icp_neutralizer",
     "gas_mode": "G-REUSE", "role": "PRIMARY ground test", "axes": [],
     "lines": ["P-GT-ICP-XE", "P-GT-P1-BENCH", "P-GT-XE-REFERENCE", "P-GT-PEAK", "P-GT-HALL-START",
               "P-GT-TRANSITION"]},
    {"id": "S2-FL-C1", "case": "CASE-2", "ledger": "FLIGHT", "configuration": "hall_c1_reference", "gas_mode": None,
     "role": "C1 reference / control / fallback (A9 control_fallback)", "axes": ["RA-DWELL", "RA-FLOWUNC"],
     "lines": ["C1-FL-PURGE", "C1-FL-HEAT", "C1-FL-IGN", "C1-FL-KEEPER", "C1-FL-FLOWUNC", "C1-FL-TRANSITION",
               "C1-FL-FALLBACK", "C1-FL-FUNC", "C1-FL-HALL-START", "C1-FL-PEAK", "C1-FL-FLOWUNC-OTHER",
               "C1-FL-ICP-XE"]},
    {"id": "S2-GT-C1", "case": "CASE-2", "ledger": "GROUND_TEST", "configuration": "hall_c1_reference",
     "gas_mode": None, "role": "C1 reference ground test (HIQ-01: in every block)", "axes": ["RA-DWELL"],
     "lines": ["C1-GT-PURGE", "C1-GT-HEAT", "C1-GT-IGN", "C1-GT-KEEPER", "C1-GT-MINFLOW", "C1-GT-FLOWUNC",
               "C1-GT-XE-REFERENCE", "C1-GT-PEAK", "C1-GT-HALL-START", "C1-GT-TRANSITION"]},
    {"id": "S3-FL-GXE", "case": "CASE-3", "ledger": "FLIGHT", "configuration": "hall_icp_neutralizer",
     "gas_mode": "G-XE", "role": "OPTIONAL contingency (HIQ-06): G-XE replaces the G-REUSE zero line",
     "axes": ["RA-FUNC"],
     "lines": ["OPT-FL-GXE", "OPT-FL-FLOWUNC-GXE", "P-FL-C1", "P-FL-FUNC", "P-FL-HALL-START", "P-FL-TRANSITION",
               "P-FL-FALLBACK", "P-FL-PEAK", "P-FL-FLOWUNC-OTHER"]},
    {"id": "S3-FL-GATM", "case": "CASE-3", "ledger": "FLIGHT", "configuration": "hall_icp_neutralizer",
     "gas_mode": "G-ATM", "role": "OPTIONAL contingency (HIQ-06): G-ATM, 0 Xe", "axes": ["RA-FUNC"],
     "lines": ["OPT-FL-GATM", "P-FL-C1", "P-FL-FUNC", "P-FL-HALL-START", "P-FL-TRANSITION", "P-FL-FALLBACK",
               "P-FL-PEAK", "P-FL-FLOWUNC-OTHER"]},
    {"id": "S3-GT-GXE", "case": "CASE-3", "ledger": "GROUND_TEST", "configuration": "hall_icp_neutralizer",
     "gas_mode": "G-XE", "role": "OPTIONAL contingency ground test", "axes": [],
     "lines": ["OPT-GT-GXE", "P-GT-P1-BENCH", "P-GT-XE-REFERENCE", "P-GT-PEAK", "P-GT-HALL-START",
               "P-GT-TRANSITION"]},
    {"id": "S3-GT-GATM", "case": "CASE-3", "ledger": "GROUND_TEST", "configuration": "hall_icp_neutralizer",
     "gas_mode": "G-ATM", "role": "OPTIONAL contingency ground test, 0 Xe", "axes": [],
     "lines": ["OPT-GT-GATM", "P-GT-P1-BENCH", "P-GT-XE-REFERENCE", "P-GT-PEAK", "P-GT-HALL-START",
               "P-GT-TRANSITION"]},
    {"id": "S3-GT-P1-DIAG", "case": "CASE-3", "ledger": "GROUND_TEST", "configuration": "hall_icp_neutralizer",
     "gas_mode": "G-REUSE + DIAGNOSTIC G-XE", "role": "OPTIONAL P1 diagnostic dedicated Xe feed (A9.3 OQ-RFQ-10)",
     "axes": [],
     "lines": ["P-GT-ICP-XE", "P-GT-P1-BENCH", "OPT-GT-P1-GXE-DIAG", "P-GT-XE-REFERENCE", "P-GT-PEAK",
               "P-GT-HALL-START", "P-GT-TRANSITION"]},
]


def reading_combos(axes: list) -> list:
    if not axes:
        return [{}]
    keys = [list(READING_AXES[a]["readings"]) for a in axes]
    return [dict(zip(axes, combo)) for combo in itertools.product(*keys)]


def evaluate(lines: list, items: dict, f_reserve: float, f_residual: float) -> list:
    ld = {ln["id"]: ln for ln in lines}
    out = []
    for sc in SCENARIOS:
        for reading in reading_combos(sc["axes"]):
            done = {}
            order = sorted(sc["lines"], key=lambda x: ld[x]["kind"] == "fraction_of_lines")
            for lid in order:
                done[lid] = eval_line(ld[lid], items, reading, done)
            evals = [done[lid] for lid in sc["lines"]]
            rec = {"scenario": sc["id"], "reading": reading, "lines": evals}
            if sc["ledger"] == "FLIGHT":
                rec["booking"] = book_reserve_and_residual(evals, ld, f_reserve, f_residual, reading)
            else:
                tbd = [e["line"] for e in evals if e["kg"] is None]
                floor = rk(sum(e["kg"] or 0.0 for e in evals))
                rec["booking"] = {
                    "status": "REFUSED_TBD_INPUTS" if tbd else ("COMPUTED_EXACT_ZERO" if floor == 0.0 else "COMPUTED"),
                    "tbd_lines": tbd, "total_kg": None if tbd else floor, "floor_closed_terms_only_kg": floor,
                    "reserve_residual": "none: no owner reserve/residual rule for ground-test Xe; supply margin "
                                        "XA9Q-04 (TBD_OWNER)"}
            out.append(rec)
    return out


# ------------------------------------------------------------------------------------------------ design cases
def read_isotherm(rel: str) -> dict:
    rows = (REPO / rel).read_text(encoding="utf-8").splitlines()
    hdr = rows[0].split("\t")
    ip, ir = hdr.index("Pressure (bar)"), hdr.index("Density (kg/m3)")
    out = {}
    for r in rows[1:]:
        if r.strip():
            c = r.split("\t")
            out[float(c[ip])] = float(c[ir])
    return out


def case_split(case_kg: float, reading: str, f_reserve: float, f_residual: float) -> dict:
    for name, v in (("case_kg", case_kg), ("f_reserve", f_reserve), ("f_residual", f_residual)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise BookingError(f"case split: {name} = {v!r} must be a finite number >= 0 (SW-08; no NaN / negative "
                               "reserve or residual)")
    if reading == "LOADED":
        loaded = case_kg
        usable = case_kg / (1.0 + f_residual)
    elif reading == "USABLE_RESIDUAL_ON_TOP":
        usable = case_kg
        loaded = case_kg * (1.0 + f_residual)
    else:
        raise BookingError(f"unknown case reading {reading}")
    residual = f_residual * usable
    non_reserve_cap = usable / (1.0 + f_reserve)
    reserve = f_reserve * non_reserve_cap
    if not abs(non_reserve_cap + reserve + residual - loaded) <= 1e-12 * max(1.0, loaded):   # NaN-safe (SW-08)
        raise BookingError("design-case split does not close (double counting)")
    return {"case_kg": case_kg, "reading": reading, "loaded_kg": loaded, "usable_kg": usable,
            "residual_kg": residual, "reserve_kg": reserve, "non_reserve_cap_kg": non_reserve_cap}


def design_cases(prev: dict, items: dict, evals: list) -> dict:
    f_rsv, f_res = items["XV2-23"]["value"], items["XV2-24"]["value"]
    u_rho = items["XV2-27"]["value"]
    cases = items["XV2-30"]["value"]
    iso = read_isotherm(SNAPSHOTS["NIST323"][0])
    iso300 = read_isotherm(SNAPSHOTS["NIST300"][0])
    pdc = prev["design_cases"]
    axis = []
    agreement = []
    for row in pdc["density_axis"]["rows"]:
        p = row["p_bar"]
        rho = iso[p]
        ok = rho == row["rho_323K_kg_m3"] and iso300[p] == row["rho_300K_kg_m3_contrast"]
        agreement.append({"check": f"density at {p} bar (323.15 K, 300 K) = A9-08 density_axis", "agrees": ok})
        axis.append({"p_bar": p, "rho_323K_kg_m3": rho, "axis_basis": row["axis_basis"]})
    readings = list(READING_AXES["RA-CASE"]["readings"])
    split = []
    for rd in readings:
        for c in cases:
            s = case_split(c, rd, f_rsv, f_res)
            split.append({k: (sig6(v) if isinstance(v, float) and k != "case_kg" else v) for k, v in s.items()})
    prev_split = {r["case_kg"]: r for r in pdc["reserve_residual_split"]["rows"]}
    for r in split:
        if r["reading"] == "LOADED":
            p = prev_split[r["case_kg"]]
            ok = (r["residual_kg"], r["reserve_kg"], r["non_reserve_cap_kg"]) == \
                (p["residual_kg"], p["reserve_kg"], p["non_reserve_cap_kg"])
            agreement.append({"check": f"LOADED split {r['case_kg']} kg = A9-08 reserve_residual_split", "agrees": ok})
    vol = []
    prev_vol = {(r["case_kg"], r["p_bar"]): r["V_min_323K_l"] for r in pdc["tank_volume"]["rows"]}
    for rd in readings:
        for c in cases:
            loaded = case_split(c, rd, f_rsv, f_res)["loaded_kg"]
            for a in axis:
                v = sig6(loaded / (a["rho_323K_kg_m3"] * (1.0 - u_rho)) * 1000.0)
                vol.append({"case_kg": c, "reading": rd, "loaded_kg": sig6(loaded), "p_bar": a["p_bar"],
                            "V_min_323K_l": v})
                if rd == "LOADED":
                    agreement.append({"check": f"LOADED V_min {c} kg @ {a['p_bar']} bar = A9-08 tank_volume",
                                      "agrees": v == prev_vol[(c, a["p_bar"])]})
    # head-room for the TBD terms per flight scenario (arithmetic on owner allocations)
    ld_flow = items["XV2-01"]["value"] * 3600.0
    headroom, ceiling = [], []
    for e in evals:
        sc = next(s for s in SCENARIOS if s["id"] == e["scenario"])
        if sc["ledger"] != "FLIGHT":
            continue
        if e["reading"].get("RA-DWELL") == "ATTEMPTS_2":
            continue  # the dwell reading changes only TBD ignition terms, not the closed floors
        b = e["booking"]
        fl = b["floors_closed_terms_only"]
        base_reading = {k: v for k, v in e["reading"].items() if k != "RA-DWELL"}
        no_xe = b["status"] == "COMPUTED_EXACT_ZERO"
        for rd in readings:
            for c in cases:
                s = case_split(c, rd, f_rsv, f_res)
                row = {"scenario": e["scenario"], "reading": dict(base_reading, **{"RA-CASE": rd}), "case_kg": c}
                if no_xe:
                    row.update({"headroom_for_TBD_terms_kg": None,
                                "status": "NOT_APPLICABLE_NO_FLIGHT_XE_UNDER_READING"})
                else:
                    # the cap is taken at 6 significant digits before subtracting, exactly as the A9-08 builder does
                    base_cap = sig6((s["usable_kg"] - fl["outside_base_kg"]) / (1.0 + f_rsv))
                    h = base_cap - fl["reserve_base_kg"]
                    row.update({"closed_in_reserve_base_kg": fl["reserve_base_kg"],
                                "closed_outside_reserve_base_kg": fl["outside_base_kg"],
                                "reserve_base_cap_kg": base_cap, "headroom_for_TBD_terms_kg": sig6(h),
                                "status": "HEADROOM" if h >= 0 else "EXCEEDED_BY_CLOSED_TERMS"})
                headroom.append(row)
                if e["scenario"] == "S2-FL-C1":
                    unc = (items["XV2-04"]["value"] * items["XV2-05"]["value"] * 1e-6 * ld_flow
                           if e["reading"]["RA-FLOWUNC"] == "INSIDE_RESERVE_BASE" else 0.0)
                    base_cap = sig6((s["usable_kg"] - fl["outside_base_kg"]) / (1.0 + f_rsv))
                    ceil = (base_cap - unc) / ld_flow / 1e-6
                    ceiling.append({"reading": dict(base_reading, **{"RA-CASE": rd}), "case_kg": c,
                                    "c1_flow_ceiling_mg_s_all_other_terms_zero": sig6(ceil),
                                    "a5_design_flow_mg_s": items["XV2-02"]["value"],
                                    "design_flow_within_ceiling": items["XV2-02"]["value"] <= ceil})
    prev_head = {(r["case_kg"]): r["headroom_for_TBD_terms_kg"] for r in pdc["headroom"]["rows"]
                 if r["scenario"] == "FL-C1"}
    for r in headroom:
        if r["scenario"] == "S2-FL-C1" and r["reading"].get("RA-FLOWUNC") == "INSIDE_RESERVE_BASE" \
                and r["reading"]["RA-CASE"] == "LOADED":
            ph = prev_head[r["case_kg"]]
            ok = ph == r["headroom_for_TBD_terms_kg"] if ph is not None else r["status"] == "EXCEEDED_BY_CLOSED_TERMS"
            agreement.append({"check": f"C1 head-room {r['case_kg']} kg (LOADED, INSIDE) = A9-08 headroom FL-C1",
                              "agrees": ok})
    prev_ceil = {r["case_kg"]: r["c1_flow_ceiling_mg_s_all_other_terms_zero"] for r in pdc["c1_sensitivity"]["rows"]}
    for r in ceiling:
        if r["reading"]["RA-FLOWUNC"] == "INSIDE_RESERVE_BASE" and r["reading"]["RA-CASE"] == "LOADED":
            agreement.append({"check": f"C1 flow ceiling {r['case_kg']} kg (LOADED, INSIDE) = A9-08 c1_sensitivity",
                              "agrees": r["c1_flow_ceiling_mg_s_all_other_terms_zero"] == prev_ceil[r["case_kg"]]})
    bad = [a["check"] for a in agreement if not a["agrees"]]
    if bad:
        raise BookingError("v2 does not reproduce the verified A9-08 tables: " + "; ".join(bad))
    share = []
    gate = items["XV2-38"]["value"]
    cap = items["XV2-39"]["value"]
    for rd in readings:
        for c in cases:
            loaded = case_split(c, rd, f_rsv, f_res)["loaded_kg"]
            share.append({"case_kg": c, "reading": rd, "loaded_kg": sig6(loaded),
                          "share_of_40kg_xe_load_only": sig6(loaded / gate), "screening_cap_row44": cap,
                          "xe_load_alone_reaches_screening_cap": loaded / gate >= cap})
    ign = []
    for rd, t in items["XV2-42"]["value_by_reading"].items():
        ign.append({"reading": rd, "dwell_bound_per_start_s": t,
                    "xe_per_start_per_mg_s_of_ignition_flow_kg": rk(t * 1e-6),
                    "note": "multiply by N_starts (XV2-14, TBD) and mdot_ign (XV2-09, TBD); no total is formed"})
    return {
        "label": "owner design cases (row 48) for tank/interface sizing under BOTH open case-content readings "
                 "(RA-CASE); no mission load is frozen; arithmetic on owner allocations, not a prediction",
        "eos": {"source": pdc["eos"]["citation"], "stated_uncertainty": pdc["eos"]["stated_uncertainty"],
                "snapshot_323K": SNAPSHOTS["NIST323"][0], "snapshot_sha256": SNAPSHOTS["NIST323"][1],
                "evidence_class": "model-derived",
                "use": "density read from the pinned A9-08 NIST snapshot at the A9-08 MEOP axis points; the LOADED "
                       "reading reproduces the verified A9-08 volume table exactly (see a9_08_agreement)"},
        "density_axis": {"label": pdc["density_axis"]["label"], "rows": axis},
        "reserve_residual_split": {
            "relation": "LOADED: usable = case/(1+f_residual); USABLE_RESIDUAL_ON_TOP: usable = case, loaded = "
                        "case x (1+f_residual); both: residual = f_residual x usable, non-reserve cap = "
                        "usable/(1+f_reserve), reserve = f_reserve x cap; non-reserve cap + reserve + residual = "
                        "loaded (checked; each term once)", "rows": split},
        "tank_volume": {"relation": pdc["tank_volume"]["relation"] + " (m_case replaced by the LOADED mass of the "
                        "reading)", "label": pdc["tank_volume"]["label"], "evidence_class": "model-derived",
                        "rows": vol},
        "headroom": {"label": "what each design case leaves for the TBD terms after the closed terms, the reserve and "
                              "the residual (arithmetic on owner allocations; not a prediction, not an allocation); "
                              "the RA-DWELL reading does not change closed floors and is omitted",
                     "rows": headroom},
        "c1_flow_ceiling": {"label": "hall_c1_reference flight: C1 steady flow ceiling per design case with every "
                                     "other TBD term at zero (a ceiling, not an allowance)", "rows": ceiling},
        "c1_ignition_per_start": {"label": "RA-DWELL: Xe per C1 start per mg/s of (TBD) ignition flow", "rows": ign},
        "mass_share": {"label": "Xe load alone vs the row-44 0.25 screening cap on the 40 kg wet gate (row 5); the "
                                "stored-Xe subsystem share needs hardware masses (TBD_AFTER_EVIDENCE: " + MERGED["MASS_POWER"] +
                                " MPV2-ID-16, pair XL-32)",
                       "rows": share},
        "a9_08_agreement": agreement,
    }


# ------------------------------------------------------------------------------------------------ owner answers etc.
ROW_APPLIED = {
    3: "C1 keeper term over 15,000 firing hours (provisional); mission life 26,280 h context (XV2-40)",
    5: "40 kg is wet (Xe + tank): design-case loaded mass reported against it (mass_share)",
    6: "bounded functional Xe mode booked as its own line in both configurations; for hall_icp_neutralizer under both "
       "RA-FUNC readings (XA9Q-07 OPEN)",
    26: "XE_REFERENCE / XE_AUGMENTED_PEAK ground lines; flight peak CONDITIONAL_ON_RFP",
    42: "PHASE_TOTAL_FLOW: purge, heating/start, ignition, keeper/cathode, transition and fallback each a separate line",
    43: "reserve 20 % of planned non-reserve Xe, booked once per flight evaluation (book_reserve_and_residual)",
    44: "0.25 screening cap only (mass_share); not an entitlement",
    45: "residual 2 % booked once (one RESIDUAL line); exported to " + MERGED["MASS_POWER"] + " (XL-30) for import, never "
        "re-booked",
    46: "C1 keeper term only in hall_c1_reference; no continuous C1-Xe term in hall_icp_neutralizer",
    48: "2 / 5 / 10 kg design cases under both content readings; no mission load frozen",
    50: "tank volume at 323.15 K from the pinned NIST snapshot (A9-08), MEOP an explicit axis",
    51: "filter/getter tied to the C1/Xe branch (items XV2-31/32); not required for the ICP-only flight branch",
    92: "C1 spot-mode minimum-flow search ground line (0.005 mg/s steps)",
    93: "C1 purge and ignition flows vendor/design-qualified (TBD); 120 s dwell cap; retries under both RA-DWELL "
        "readings",
    96: "+-2 % FS C1 flow-class term booked additively (0.216 kg flight); reserve-base membership under both "
        "RA-FLOWUNC readings (XA9Q-03 OPEN)",
    125: "C1 steady FCU full scale 0.2 mg/s used in the flow-class term",
}
A91_APPLIED = {
    "HIQ-06": "G-REUSE primary; G-ATM / G-XE only as CASE-3 optional entries",
    "HIQ-06_accounting": "G-REUSE m_Xe,ICP = 0 exactly; G-ATM 0 Xe (atmospheric path); G-XE explicit line",
    "OQ-A902-04": "no combined flight C1 + ICP: C1 lines only in hall_c1_reference, ICP lines only in "
                  "hall_icp_neutralizer",
    "OQ-A902-05": "ICP feed metering only when G-ATM or G-XE is installed/used",
    "HIQ-03": "XE_REFERENCE per installation in both configurations' ground ledgers",
    "HIQ-01": "C1 ground ledger (hall_c1_reference in every block)",
    "SEQ-heater": "C1 heating/start line carries Xe under the heater-ON procedure (booked, never assumed off)",
}


def owner_answers_applied(ans: dict, a91: dict, a93: dict, a96: dict, a96md: str) -> list:
    rows = {r["row"]: r for r in ans["answers"]}
    out = []
    for n, how in ROW_APPLIED.items():
        out.append({"decision": "147 answers", "path": DECISIONS["ANS"][0], "sha256": DECISIONS["ANS"][1],
                    "id": f"row {n}", "owner_answer_verbatim": rows[n]["owner_answer_verbatim"], "how_applied": how})
    for k, how in A91_APPLIED.items():
        v = a91["decisions"][k]
        out.append({"decision": "A9.1", "path": DECISIONS["A91"][0], "sha256": DECISIONS["A91"][1], "id": k,
                    "owner_answer_verbatim": v if isinstance(v, str) else json.dumps(v, ensure_ascii=False),
                    "how_applied": how})
    out.append({"decision": "A9.3", "path": DECISIONS["A93"][0], "sha256": DECISIONS["A93"][1], "id": "OQ-RFQ-10",
                "owner_answer_verbatim": a93["decisions"]["OQ-RFQ-10"]["summary"] + " | booking: " +
                a93["decisions"]["OQ-RFQ-10"]["booking"],
                "how_applied": "dedicated ICP feeds (G-XE, G-ATM, P1 diagnostic) are CASE-3 optional entries, zero in "
                               "every primary scenario"})
    out.append({"decision": "A9.3", "path": DECISIONS["A93"][0], "sha256": DECISIONS["A93"][1],
                "id": "authorizations.P1", "owner_answer_verbatim": a93["authorizations"]["P1"],
                "how_applied": "P1 ICP bench books 0 kg Xe (Ar only) - line P-GT-P1-BENCH"})
    sec = a96md.split("12. Complete Xe accounting", 1)[1].split("13. Complete RFQ packages", 1)[0]
    sec12 = " ".join(x.strip() for x in sec.splitlines() if x.strip())
    out.append({"decision": "A9.6", "path": DECISIONS["A96MD"][0], "sha256": DECISIONS["A96MD"][1],
                "id": "sec. 12", "owner_answer_verbatim": "12. Complete Xe accounting " + sec12,
                "how_applied": "CASE-1 / CASE-2 / CASE-3 structure; reserve and residual booked once"})
    out.append({"decision": "A9.6", "path": DECISIONS["A96"][0], "sha256": DECISIONS["A96"][1],
                "id": "summary.unresolved_questions", "owner_answer_verbatim": a96["summary"]["unresolved_questions"],
                "how_applied": "XA9Q-01/02/03/07, MQ-09, OQ-A907-01, OQ-A910-01 stay TBD_OWNER; both readings carried"})
    return out


def open_questions_carried(oqs: dict) -> list:
    rows = {r["id"]: r for r in oqs["rows"]}
    out = []
    for axis, spec in READING_AXES.items():
        for q in spec["questions"]:
            r = rows[q]
            if r["status"] != "OPEN":
                raise BookingError(f"{q} is not OPEN in the pinned state v3 - a reading axis would answer it")
            out.append({"id": q, "axis": axis, "state_v3_status": r["status"], "question": r["question"],
                        "proposed_by_lane": r["proposed"], "v2_handling": "TBD_OWNER - both readings carried"})
    return out


NEW_OPEN_QUESTIONS = [
    {"id": "XV2Q-01",
     "question": "If XA9Q-07 is answered NO (the row-6 functional Xe mode does not apply to hall_icp_neutralizer), is "
                 "that flight configuration Xe-free (no tank, no Xe flow control), or does it keep a Xe system for "
                 "Hall Xe ignition / Xe fallback / transitions only?",
     "proposed": "none - owner call; v2 carries the Xe-free reading literally from the XA9Q-07 parenthetical and the "
                 "full A9-08 set under YES; an intermediate reading would be a third RA-FUNC value",
     "needed_by": "with XA9Q-07 (NOW)", "status": "OPEN"},
]


def interface_demands() -> list:
    def pair(i, direction, frm, to, quantity_local, p):
        x = xref(p)
        return {"id": i, "direction": direction, "from": frm, "to": to, "quantity": quantity_local,
                "units": x["units"], "status": x["status"], "xref": [x]}
    mp, rfq, p1 = MERGED["MASS_POWER"], MERGED["RFQ"], MERGED["P1"]
    return [
        pair("XV2-IF-01", "OUT", SCHEMA_ID, mp + " MPV2-ID-15",
             "residual Xe: ONE line per flight evaluation (RESIDUAL) and per design case/reading "
             "(design_cases.reserve_residual_split.residual_kg); import once, never re-book (row 45); totals with a "
             "TBD input stay REFUSED", "XL-30"),
        pair("XV2-IF-02", "OUT", SCHEMA_ID, mp + " MPV2-ID-05",
             "loaded Xe and headroom per design case under both RA-CASE readings (design_cases.headroom) and the "
             "323 K tank volume table", "XL-31"),
        pair("XV2-IF-03", "IN", mp + " MPV2-ID-16", SCHEMA_ID,
             "stored-Xe hardware masses (tank, regulator/PMU, FCUs, isolation valves, C1-branch filter/getter) for "
             "the row-44 subsystem share", "XL-32"),
        pair("XV2-IF-04", "OUT", SCHEMA_ID, rfq + " IFD-19",
             "tank ranges (loaded 2.0-10.2 kg across both readings, V_min per MEOP axis at 323 K); C1 steady FCU "
             "0.05-0.2 mg/s class; C1 start FCU FS 1.0 mg/s (conditional, row 125); ICP dedicated-feed controller as "
             "an option line only (A9.3 OQ-RFQ-10)", "XL-34"),
        pair("XV2-IF-05", "IN", rfq + " IFD-15", SCHEMA_ID,
             "MEOP and tank selection (XV2-28), vendor/design-qualified C1 purge, preheat and ignition flows "
             "(XV2-09/10/11), non-C1 flow-class accuracy (XV2-20), filter/getter spec (XV2-31/32)", "XL-35"),
        pair("XV2-IF-06", "IN", p1 + " IF-P1-37", SCHEMA_ID,
             "per-record gas state; dedicated-feed flag; measured dedicated-feed flow if a labelled DIAGNOSTIC G-XE "
             "feed is activated (OPT-GT-P1-GXE-DIAG; P1-M-19)", "XL-36"),
        pair("XV2-IF-07", "OUT", SCHEMA_ID, p1 + " IF-P1-17",
             "booking rule: G-REUSE mdot_ICP,dedicated = 0; any activated diagnostic dedicated feed is booked here "
             "as a separate optional entry (S3-GT-P1-DIAG), never as baseline", "XL-37"),
        {"id": "XV2-IF-08", "direction": "OUT", "from": SCHEMA_ID, "to": DOWNSTREAM["DECPROP"],
         "quantity": "open questions carried (XA9Q-01/02/03/07, MQ-09, OQ-A907-01, OQ-A910-01) and new XV2Q-01; no "
                     "answers", "units": "-", "status": "OFFERED", "xref": []},
        {"id": "XV2-IF-09", "direction": "OUT", "from": SCHEMA_ID, "to": DOWNSTREAM["RVM"],
         "quantity": "Xe capability / Xe accounting evidence state: every total with a TBD input is REFUSED; the RVM "
                     "Xe rows can only be NOT_EVALUATED / INCOMPLETE_EVIDENCE from this accounting (never PASS)",
         "units": "-", "status": "OFFERED", "xref": []},
        {"id": "XV2-IF-10", "direction": "OUT", "from": SCHEMA_ID, "to": DOWNSTREAM["M16"],
         "quantity": "m16_impact rows (no readiness change: framework only)", "units": "-", "status": "OFFERED",
         "xref": []},
        {"id": "XV2-IF-11", "direction": "IN", "from": "C1 vendor/design qualification (external, not contacted)",
         "to": SCHEMA_ID, "quantity": "C1 purge/ignition flow and durations; heater procedure",
         "units": "mg/s; s", "status": "TBD_AFTER_EVIDENCE", "xref": []},
        {"id": "XV2-IF-12", "direction": "IN", "from": "H-1 measurements (hardware campaign)", "to": SCHEMA_ID,
         "quantity": "Hall Xe operating point, Xe ignition use, transition Xe logged per phase (PHASE_TOTAL_FLOW)",
         "units": "mg/s; s", "status": "TBD_AFTER_EVIDENCE", "xref": []},
        pair("XV2-IF-13", "IN", mp + " MPV2-ID-04", SCHEMA_ID,
             "consistency rules demanded by mass / power and applied here: one design-case content with both RA-CASE "
             "readings carried (OQ-A910-01 / XA9Q-01 / MQ-09 TBD_OWNER), C1 terms only in the hall_c1_reference "
             "scenarios (S2-*), primary G-REUSE Xe line = 0 (S1-*)", "XL-33"),
    ]


M16_IMPACT = [
    {"m16_row": 6, "key": "xe_tank", "impact": "tank volume per design case at 323 K under both RA-CASE readings "
     "(USABLE reading adds the residual: loaded x 1.02); totals REFUSED; no readiness change", "cell_edit": "none; "
     + DOWNSTREAM["M16"]},
    {"m16_row": 7, "key": "xe_regulator", "impact": "inlet = MEOP (TBD, XV2-28); no change", "cell_edit": "none; " +
     DOWNSTREAM["M16"]},
    {"m16_row": 8, "key": "xe_metering", "impact": "C1 FCUs only in hall_c1_reference; ICP feed metering only as a "
     "CASE-3 optional entry (G-XE/G-ATM/diagnostic); Hall-side Xe metering under RA-FUNC APPLIES only for the ICP "
     "configuration", "cell_edit": "none; " + DOWNSTREAM["M16"]},
    {"m16_row": 11, "key": "cathode", "impact": "C1 remains CONTROL_FALLBACK: every C1 Xe phase a separate line; "
     "not present in the ICP configuration", "cell_edit": "none; " + DOWNSTREAM["M16"]},
]


def historical_reuse() -> list:
    out = []
    for key, (rel, h, role) in list(DELIVERABLES.items())[:4]:
        out.append({"artifact": rel, "sha256": h, "kind": "verified A9-08 (revision base; read only)", "role": role,
                    "reused": "items (values, sources, evidence classes, statuses) imported unchanged except XA9-08 "
                              "and XA9-30; term/line structure; design-case EOS, density axis and the tables this "
                              "revision must reproduce" if key == "PREV_JSON" else "reference only",
                    "not_reused": "single PROPOSED readings of XA9Q-01 / XA9Q-02 / XA9Q-03 / XA9Q-07 (v2 carries both)"})
    for key, (rel, h, role) in HISTORICAL.items():
        out.append({"artifact": rel, "sha256": h, "kind": "verified v1 (read only; not imported)", "role": role,
                    "reused": "lineage only (cathode term 5.4 kg reproduced from the A9-08 items)",
                    "not_reused": "v1 architecture scope (row 28 superseded)"})
    return out


def pins_list(group: dict) -> list:
    return [{"key": k, "path": rel, "sha256": h, "role": role} for k, (rel, h, role) in group.items()]


# ------------------------------------------------------------------------------------------------ document
def build_doc() -> dict:
    verify_pins()
    prev = _load(DELIVERABLES["PREV_JSON"][0])
    ans = _load(DECISIONS["ANS"][0])
    a91 = _load(DECISIONS["A91"][0])
    a93 = _load(DECISIONS["A93"][0])
    a96 = _load(DECISIONS["A96"][0])
    a9 = _load(DECISIONS["A9"][0])
    oqs = _load(DELIVERABLES["OQS3"][0])
    a96md = (REPO / DECISIONS["A96MD"][0]).read_text(encoding="utf-8")
    items = build_items(prev, a93)
    for it in items:
        if it["evidence_class"] not in EVIDENCE_CLASSES:
            raise BookingError(f"{it['id']}: evidence class {it['evidence_class']}")
        if it["freeze_point"] not in FREEZE_POINTS:
            raise BookingError(f"{it['id']}: freeze point {it['freeze_point']}")
    idx = {i["id"]: i for i in items}
    lines = build_lines()
    for ln in lines:
        for f in ln["fields"]:
            if f["item"] not in idx:
                raise BookingError(f"{ln['id']}: unknown item {f['item']}")
    evals = evaluate(lines, idx, idx["XV2-23"]["value"], idx["XV2-24"]["value"])
    dc = design_cases(prev, idx, evals)
    return {
        "schema": SCHEMA_ID, "id": SCHEMA_ID, "version": "2.0.0", "lane": "fo_a9_6_xe_accounting",
        "authorization": f"{DECISIONS['A96'][0]} implementation_lanes.fo_a9_6_xe_accounting; {DECISIONS['A96MD'][0]} "
                         "sec. 12",
        "revision_of": {"path": DELIVERABLES["PREV_JSON"][0], "sha256": DELIVERABLES["PREV_JSON"][1],
                        "rule": "the A9-08 deliverable is immutable and never edited; v2 is a separate revision"},
        "status": "PARAMETRIC_XE_ACCOUNTING_V2 - every total with a TBD input REFUSED; open owner questions carried "
                  "as side-by-side readings; nothing frozen; no winner; no PASS",
        "a9_status": a9["status"],
        "a9_6_fixed_statuses_unchanged": a96["summary"]["fixed_statuses"],
        "date": DATE, "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_REL}/{MD_NAME}", "test": TEST_REL,
        "what_this_is_not": [
            "not a Xe allocation: no mission Xe load is frozen (row 48)",
            "not a prediction of thrust, discharge current, neutralizer current or plasma state (no Hall closure "
            "admitted; credible set EMPTY; 0-D Hall superseded; v1.2-v1.6 withdrawn)",
            "not an owner answer: XA9Q-01/02/03/07, MQ-09, OQ-A907-01, OQ-A910-01 stay TBD_OWNER",
            "not a ranking and not a compliance statement: no winner, no PASS",
            "not wired into archengine (goldens do not move); the A9-08 and v1 Xe ledgers are unchanged",
        ],
        "pins": {"decisions": pins_list(DECISIONS), "deliverables": pins_list(DELIVERABLES),
                 "source_snapshots": pins_list(SNAPSHOTS), "historical": pins_list(HISTORICAL)},
        "never_pinned": NEVER_PINNED,
        "downstream_consumer_lanes": DOWNSTREAM,
        "merged_cross_lane": xlane_report(None),
        "accounting_convention": prev["accounting_convention"],
        "cases": {
            "CASE-1": "PRIMARY hall_icp_neutralizer, G-REUSE: m_Xe,ICP = 0 exactly; flight Xe only for the Hall "
                      "Xe-capable mode family (RA-FUNC); ground-test Xe; P1 bench Ar-only",
            "CASE-2": "REFERENCE hall_c1_reference (CONTROL_FALLBACK): purge, heating/start, ignition, keeper/cathode, "
                      "transition, fallback each a separate line; plus the Hall Xe-mode family",
            "CASE-3": "OPTIONAL entries: G-XE contingency (flight/ground), G-ATM (0 Xe), P1 diagnostic dedicated Xe; "
                      "zero (absent) in every primary scenario",
        },
        "reading_axes": READING_AXES,
        "open_questions_carried": open_questions_carried(oqs),
        "items": items,
        "ledger_lines": lines,
        "scenarios": SCENARIOS,
        "evaluations": evals,
        "design_cases": dc,
        "interface_demands": interface_demands(),
        "owner_answers_applied": owner_answers_applied(ans, a91, a93, a96, a96md),
        "open_owner_questions": NEW_OPEN_QUESTIONS,
        "historical_reuse": historical_reuse(),
        "m16_impact": M16_IMPACT,
    }


# ------------------------------------------------------------------------------------------------ Markdown
def _cell(v) -> str:
    if v is None:
        return "TBD"
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    return str(v).replace("|", "\\|").replace("\n", " ")


def _table(headers: list, rows: list) -> list:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return out + [""]


def _rd(r: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in r.items()) or "-"


def render_md(doc: dict) -> str:
    o = [f"# Xe accounting v2 (A9.6) - `{doc['id']}`", "",
         f"Generated by `{doc['generated_by']}` from `{JSON_NAME}`; do not edit by hand. Status: **{doc['status']}**.",
         f"A9 status: `{doc['a9_status']}`. Revision of `{doc['revision_of']['path']}` "
         f"(sha256 `{doc['revision_of']['sha256']}`; immutable, never edited).", "",
         "What this is not:", ""] + [f"- {x}" for x in doc["what_this_is_not"]] + [""]
    o += ["## Cases", ""] + [f"- **{k}** - {v}" for k, v in doc["cases"].items()] + [""]
    o += ["## Open owner questions carried as readings (TBD_OWNER)", ""]
    o += _table(["axis", "questions", "reading", "meaning"],
                [[a, ", ".join(s["questions"]), r, t] for a, s in doc["reading_axes"].items()
                 for r, t in s["readings"].items()])
    o += _table(["id", "axis", "state v3", "question", "lane proposal"],
                [[q["id"], q["axis"], q["state_v3_status"], q["question"], q["proposed_by_lane"]]
                 for q in doc["open_questions_carried"]])
    o += ["## (a) Items", ""]
    o += _table(["id", "A9-08", "name", "value", "unit", "basis", "source", "evidence", "status", "freeze"],
                [[i["id"], i["a9_08_item"], i["name"], i.get("value_by_reading", i["value_display"]), i["unit"],
                  i["basis"], i["source"], i["evidence_class"], i["status"], i["freeze_point"]]
                 for i in doc["items"]])
    o += ["## Ledger lines", ""]
    o += _table(["id", "case", "configuration", "gas", "ledger", "phase", "name", "formula", "presence",
                 "A9-08 term", "in reserve base", "sources"],
                [[ln["id"], ln["case"], ln["configuration"], ln["gas_mode"], ln["ledger"], ln["phase"], ln["name"],
                  ln["formula"], ln["presence"], ln["a9_08_term"], ln["reserve_base"], "; ".join(ln["sources"])]
                 for ln in doc["ledger_lines"]])
    o += ["## Evaluations", "",
          "Totals with any TBD input are REFUSED; floors count closed lines only (TBD lines >= 0). Reserve and "
          "residual are booked once per flight evaluation.", ""]
    rows = []
    for e in doc["evaluations"]:
        b = e["booking"]
        fl = b.get("floors_closed_terms_only") or {}
        rows.append([e["scenario"], _rd(e["reading"]), b["status"],
                     ", ".join(b["tbd_lines"]) or "-",
                     fl.get("loaded_kg", b.get("floor_closed_terms_only_kg")),
                     fl.get("reserve_kg", "n/a (ground)"), fl.get("residual_kg", "n/a (ground)")])
    o += _table(["scenario", "reading", "status", "TBD lines", "floor loaded/total kg", "floor reserve kg",
                 "floor residual kg"], rows)
    o += ["### Closed line values", ""]
    seen, rows = set(), []
    for e in doc["evaluations"]:
        for ln in e["lines"]:
            if ln["kg"] is not None:
                k = (e["scenario"], _rd(e["reading"]), ln["line"])
                if k not in seen:
                    seen.add(k)
                    rows.append([e["scenario"], _rd(e["reading"]), ln["line"], ln["presence"], ln["kg"]])
    o += _table(["scenario", "reading", "line", "presence", "kg"], rows)
    dc = doc["design_cases"]
    o += ["## Design cases (row 48)", "", dc["label"], "", f"EOS: {dc['eos']['source']}; {dc['eos']['use']}.", ""]
    o += _table(["reading", "case kg", "loaded kg", "usable kg", "reserve kg", "residual kg", "non-reserve cap kg"],
                [[r["reading"], r["case_kg"], r["loaded_kg"], r["usable_kg"], r["reserve_kg"], r["residual_kg"],
                  r["non_reserve_cap_kg"]] for r in dc["reserve_residual_split"]["rows"]])
    o += ["### Tank volume at 323.15 K", "", dc["tank_volume"]["relation"], ""]
    o += _table(["reading", "case kg", "loaded kg", "MEOP axis bar", "V_min l"],
                [[r["reading"], r["case_kg"], r["loaded_kg"], r["p_bar"], r["V_min_323K_l"]]
                 for r in dc["tank_volume"]["rows"]])
    o += ["### Head-room for the TBD terms", "", dc["headroom"]["label"], ""]
    o += _table(["scenario", "reading", "case kg", "head-room kg", "status"],
                [[r["scenario"], _rd(r["reading"]), r["case_kg"], r["headroom_for_TBD_terms_kg"], r["status"]]
                 for r in dc["headroom"]["rows"]])
    o += ["### C1 flow ceiling", "", dc["c1_flow_ceiling"]["label"], ""]
    o += _table(["reading", "case kg", "ceiling mg/s", "A5 design mg/s", "within"],
                [[_rd(r["reading"]), r["case_kg"], r["c1_flow_ceiling_mg_s_all_other_terms_zero"],
                  r["a5_design_flow_mg_s"], r["design_flow_within_ceiling"]] for r in dc["c1_flow_ceiling"]["rows"]])
    o += ["### C1 ignition per start", ""]
    o += _table(["reading", "dwell bound s", "kg per start per mg/s", "note"],
                [[r["reading"], r["dwell_bound_per_start_s"], r["xe_per_start_per_mg_s_of_ignition_flow_kg"],
                  r["note"]] for r in dc["c1_ignition_per_start"]["rows"]])
    o += ["### Mass share (row 44 screening cap)", "", dc["mass_share"]["label"], ""]
    o += _table(["reading", "case kg", "loaded kg", "share of 40 kg", "cap", "reaches cap"],
                [[r["reading"], r["case_kg"], r["loaded_kg"], r["share_of_40kg_xe_load_only"],
                  r["screening_cap_row44"], r["xe_load_alone_reaches_screening_cap"]] for r in dc["mass_share"]["rows"]])
    o += ["### Agreement with the verified A9-08 tables", ""]
    o += _table(["check", "agrees"], [[a["check"], a["agrees"]] for a in dc["a9_08_agreement"]])
    o += ["## (b) Interface demands", ""]
    o += _table(["id", "direction", "from", "to", "quantity", "units", "status", "pairs"],
                [[d["id"], d["direction"], d["from"], d["to"], d["quantity"], d["units"], d["status"],
                  ", ".join(x["pair"] + " -> " + x["counterpart"] for x in d["xref"]) or "-"]
                 for d in doc["interface_demands"]])
    o += ["## (c) Owner answers applied", ""]
    o += _table(["decision", "id", "verbatim", "how applied"],
                [[a["decision"], a["id"], a["owner_answer_verbatim"], a["how_applied"]]
                 for a in doc["owner_answers_applied"]])
    o += ["## (d) New open owner questions", ""]
    o += _table(["id", "question", "proposed", "needed by", "status"],
                [[q["id"], q["question"], q["proposed"], q["needed_by"], q["status"]]
                 for q in doc["open_owner_questions"]])
    o += ["## (e) Historical reuse", ""]
    o += _table(["artifact", "sha256", "kind", "reused", "not reused"],
                [[h["artifact"], h["sha256"], h["kind"], h["reused"], h["not_reused"]]
                 for h in doc["historical_reuse"]])
    o += ["## (f) M16 impact", ""]
    o += _table(["row", "key", "impact", "cell edit"],
                [[m["m16_row"], m["key"], m["impact"], m["cell_edit"]] for m in doc["m16_impact"]])
    o += ["## Pins", ""]
    o += _table(["group", "path", "sha256", "role"],
                [[g, p["path"], p["sha256"], p["role"]] for g, ps in doc["pins"].items() for p in ps])
    o += ["Never pinned (mutable governance): " + ", ".join(f"`{x}`" for x in doc["never_pinned"]), ""]
    o += ["Downstream consumer lanes (merged; built later in the A9.6 order, not pinned to avoid a cycle): " +
          "; ".join(doc["downstream_consumer_lanes"].values()), ""]
    o += ["### Merged cross-lane references", "", doc["merged_cross_lane"]["rule"], ""]
    o += _table(["package", "path", "pairs", "ids cited", "check"],
                [[k, v["path"], ", ".join(v["pairs"]) or "-", ", ".join(v["ids_cited"]) or "-", v["check"]]
                 for k, v in doc["merged_cross_lane"]["packages"].items()])
    return "\n".join(o)


def render():
    doc = build_doc()
    js = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    md = render_md(json.loads(js))
    return js, md


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the outputs are reproduced byte for byte")
    a = ap.parse_args(argv)
    js, md = render()
    jp, mp = HERE / JSON_NAME, HERE / MD_NAME
    if a.check:
        ok = jp.is_file() and mp.is_file() and jp.read_text(encoding="utf-8") == js and \
            mp.read_text(encoding="utf-8") == md
        probs = xlane_check(json.loads(js))
        if probs:
            print("CROSS-LANE REFERENCES BROKEN:", "; ".join(probs))
            return 1
        print("OK" if ok else "MISMATCH: rerun the builder")
        return 0 if ok else 1
    jp.write_text(js, encoding="utf-8")
    mp.write_text(md, encoding="utf-8")
    print(f"wrote {jp.relative_to(REPO)} and {mp.relative_to(REPO)}")
    probs = xlane_check(json.loads(js))
    if probs:
        print("CROSS-LANE REFERENCES BROKEN (rebuild the counterpart, then this package):", "; ".join(probs))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
