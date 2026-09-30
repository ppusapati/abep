#!/usr/bin/env python3
"""Deterministic builder of the A9 mass + power integration v2 (A9.6 lane fo_a9_6_mass_power_integration, sec. 11).

Writes
  docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json   (machine-readable deliverable)
  docs/budgets/mass_power_a9_v2/MASS_POWER_A9_V2.md     (companion document, rendered from the same data)

What it is
  A REVISION of the immutable A9-06 mass reconciliation (docs/budgets/mass_a9/mass_a9_v1.json, sha256-pinned below and
  never edited) that propagates the current architecture (A9 + A9.1 .. A9.6) into
    1. the mass BOM, per configuration (hall_icp_neutralizer = primary investigation hypothesis; hall_c1_reference =
       control / fallback, separate column), with four strictly distinct value columns per line:
       ALLOCATION (owner row 54, line level only) | EVIDENCE_FLOOR (analog or preliminary-design value, NOT a CBE) |
       CBE (a Vyovrinda current best estimate; none exists yet) | MEASURED (a weighed article; none exists yet).
       An allocation never becomes a CBE because it is in the BOM; an evidence floor never becomes a CBE either.
    2. dry and wet roll-ups for BOTH configurations under every open reading of MQ-01 (row-54 allocations MEV-level or
       CBE-level; the owner-v0 literal reading kept as reference) and of the Xe design-case content question
       (XA9Q-01 LOADED vs MQ-09 USABLE + residual on top; OQ-A910-01). All readings are carried side by side; none is
       chosen (TBD_OWNER).
    3. the power integration on the A9 spacecraft-DC boundary (abep_sim/bus_boundary_a9.py, bus_power_boundary_a9_v1,
       used by import only): per-slot allocation envelope, steady / start-up / peak phases, the 1 ms-window gate
       P_bus,1ms,max < 1500 W and the internal 1350 W design allocation (row 109). Every load is TBD: the module is run
       on explicit TBD records and must report an incomplete boundary and NOT_EVALUABLE gates (fail-closed).

What it is not: no performance prediction (no thrust, discharge current, electron current, efficiency or plasma state);
no Hall closure or superseded 0-D number is read; no winner between the configurations; no owner allocation is changed;
no genuinely open owner question is answered; no PASS is produced for thermal, RF ratings, anode or ICP capacity.

Usage
  python docs/budgets/mass_power_a9_v2/build_mass_power_a9_v2.py           # write both files
  python docs/budgets/mass_power_a9_v2/build_mass_power_a9_v2.py --check   # exit 1 if either differs from a fresh build
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim import bus_boundary_a9 as bb  # noqa: E402  (pure module; used by import only, never modified)

LANE_DIR = "docs/budgets/mass_power_a9_v2/"
OUT_JSON = LANE_DIR + "mass_power_a9_v2.json"
OUT_MD = LANE_DIR + "MASS_POWER_A9_V2.md"
BUILDER = LANE_DIR + "build_mass_power_a9_v2.py"
TEST = "tests/test_mass_power_a9_v2.py"
BASE_COMMIT = "c33b22c78b14cd4d6a51ed9bd5de4e046bc98cae"

CONFIGS = ("hall_icp_neutralizer", "hall_c1_reference")
ROLE = {"hall_icp_neutralizer": "PRIMARY INVESTIGATION HYPOTHESIS (A9; A9.2 status INVESTIGATION_HYPOTHESIS)",
        "hall_c1_reference": "CONTROL / FALLBACK (A9; A9.2 status CONTROL_FALLBACK); separate column, never combined "
                             "with the ICP in one flight installation (A9.1 OQ-A902-04)"}
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
CLOSURE_STATES = ("CLOSES", "DOES_NOT_CLOSE", "NOT_EVALUABLE")
TBD_OWNER = "TBD_OWNER"

# --------------------------------------------------------------------------------------------------- pinned inputs
XE_A9_DIR = "docs/budgets/" + "xe" + "_ledger_a9/"
PINS = {  # key: (path, sha256, kind)
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "owner decision (immutable)"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "owner decision (immutable)"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "owner decision (immutable)"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "owner decision (immutable)"),
    "A91_MD": ("docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md",
               "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e", "owner decision (immutable)"),
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03", "owner decision (immutable)"),
    "A92_MD": ("docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md",
               "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9", "owner decision (immutable)"),
    "A93": ("docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json",
            "81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b", "owner decision (immutable)"),
    "A93_MD": ("docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md",
               "55a1fd84558a9590705bb82aa11db5e2b9136dd1d83a957d26614c435c707411", "owner decision (immutable)"),
    "A94": ("docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json",
            "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d", "owner decision (immutable)"),
    "A94_MD": ("docs/decisions/OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md",
               "53cc026d63f85bd416f8ed8f4e8f9f7e7d7fc4429dccc45b86a51390b5c08b1c", "owner decision (immutable)"),
    "A95": ("docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json",
            "c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3", "owner decision (immutable)"),
    "A95_MD": ("docs/decisions/OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md",
               "9e49e923328441c1fc82afd3eb64c13d85fc818e8fe534576ada61a16fa525f3", "owner decision (immutable)"),
    "A96": ("docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json",
            "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327", "owner decision (immutable)"),
    "A96_MD": ("docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md",
               "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634", "owner decision (immutable)"),
    "M6": ("docs/budgets/mass_a9/mass_a9_v1.json",
           "071b03fb634c6b25ef422e7ec81006d337e6c333b80133240bdea32999a4f7d4",
           "revised deliverable A9-06 (immutable; this file is its revision, never an edit)"),
    "M6_MD": ("docs/budgets/mass_a9/MASS_A9.md",
              "ee748279b52c9233563cc796e5b06613f6aa19d48a5c1513637d33ff4bad8a44", "revised deliverable A9-06 (immutable)"),
    "M6_BUILD": ("docs/budgets/mass_a9/build_mass_a9.py",
                 "9d719214b0e9d93e1a690a24473c5d42f1150b66295e2cdd720e1c60cfec36de",
                 "revised deliverable A9-06 builder (immutable)"),
    "BBMOD": ("abep_sim/bus_boundary_a9.py",
              "7b23dbd23d39bd576691f877c0b32b64c14e83e796b2da9a662f0639319c878a",
              "pure module bus_power_boundary_a9_v1 (imported, never modified)"),
    "BBDOC": ("docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
              "9f6e074cc2cdd1e2445d00a14eec04b4cc33f239655f8619a789e7ae863c43e6", "verified deliverable A9-02"),
    "XEA9": (XE_A9_DIR + "xe" + "_ledger_a9_v1.json",
             "37c32cda9fb04200f6e9041b0e790ca700e270866f29e7c10f8a298034ddacfd", "verified deliverable A9-08"),
    "H2A9": ("docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json",
             "b428565299c1c41487d9ffa50c174986d2d52c544539f89ca21b7bdbc2ae44fa", "verified deliverable A9-07"),
    "OQS3": ("docs/budgets/owner_decisions/owner_questions_state_v3.json",
             "1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2",
             "owner-question state v3 snapshot (read for open/answered status)"),
}
NEVER_PINNED = ["docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                "docs/orchestration/fired_triggers.jsonl", "docs/orchestration/trigger_ledger_v2.jsonl",
                "docs/orchestration/runtime_state.json"]
PENDING_LANES = {  # A9.6 lanes NOT merged in this base (other worktrees): referenced only as 'PENDING ...', never read
    "M16": ("fo_a9_6_m16_refresh", "(M16 refresh after the implementation batch; A9.6 sec. 16)"),
    "RVM": ("fo_a9_6_rvm", "(system requirement-verification matrix; A9.6 sec. 15)"),
}
MERGED_REF = {  # merged A9.6 packages cited here (ids checked at build time by xlane_check; never sha-pinned)
    "P3": "merged P3 docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json",
    "P4": "merged P4 docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
    "XE2": "merged Xe accounting v2 docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json",
    "RFQ2": "merged RFQ v2 docs/procurement/rfq_a9_v2/rfq_a9_v2.json",
}


def pending(key: str) -> str:
    lane, path = PENDING_LANES[key]
    return f"PENDING {path} ({lane})"


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
XLANE_SELF = 'MP'
XLANE_BUILD_ORDER = ["P4", "XE", "P1", "P2", "P3", "MP", "RFQ"]
XLANE_BUILD_ORDER_RULE = ("values flow only P4 -> MP (candidate densities) and XE -> MP (Xe residual and headroom, "
                          "both readings), and P1 / P2 -> RFQ (ids, item text and statuses of the instrument "
                          "coverage); every other cross-lane reference is an id checked at build time. Rebuild in "
                          "the order P4, XE, P1, P2, P3, MP, RFQ; a second pass of any package is a no-op")
XL_PAIRS = {  # pair: (counterpart package, counterpart id, quantity, units, status) - identical text on both sides
    'XL-26': (
        'P4',
        'ID-07',
        ('candidate densities PR-001, PR-011, PR-021 (P4 property_records) imported by mass / power; part mass = '
         'density x CAD volume'),
        'kg/m3; kg',
        'IMPORTED (densities); part mass TBD - requires the anode / collector geometry; FINAL_ANODE_MATERIAL OPEN',
    ),
    'XL-28': (
        'P3',
        'P3-IF-S08',
        ('thermal-hardware mass (radiator / heaters / MLI / heat paths) and any active-cooling variant from the '
         'coupled H-1 / ICP thermal model'),
        'kg',
        'TBD_AFTER_EVIDENCE (ICP_COUPLED_THERMAL UNRESOLVED; no PASS)',
    ),
    'XL-29': (
        'P3',
        'P3-IF-S09',
        'thermal_control slot power (steady / start-up) for the power ledger',
        'W',
        'TBD_AFTER_EVIDENCE (ICP_COUPLED_THERMAL UNRESOLVED; no PASS)',
    ),
    'XL-30': (
        'XE',
        'XV2-IF-01',
        ('Xe residual per design case under both RA-CASE readings (design_cases.reserve_residual_split.residual_kg), '
         'imported once by mass / power: inside the case under LOADED (LOADED_XA9Q01), on top under '
         'USABLE_RESIDUAL_ON_TOP (USABLE_MQ09)'),
        'kg',
        'IMPORTED (read at build time; XA9Q-01 / MQ-09 / OQ-A910-01 TBD_OWNER, both readings carried)',
    ),
    'XL-31': (
        'XE',
        'XV2-IF-02',
        ('loaded Xe and headroom per design case and flight scenario under both RA-CASE readings '
         '(design_cases.headroom), 323 K tank volume table'),
        'kg; l',
        'IMPORTED (headroom statuses read at build time; totals with TBD inputs REFUSED)',
    ),
    'XL-32': (
        'XE',
        'XV2-IF-03',
        ('stored-Xe hardware masses (tank, regulator / PMU, FCUs, isolation valves, C1-branch filter / getter) for '
         'the row-44 subsystem share'),
        'kg',
        'TBD_AFTER_EVIDENCE (no CBE; owner line allocation AL-08 and evidence floors only)',
    ),
    'XL-33': (
        'XE',
        'XV2-IF-13',
        ('booking rules shared by both ledgers: one Xe design-case content (OQ-A910-01, both readings carried), C1 '
         'terms booked only in hall_c1_reference, primary G-REUSE m_Xe,ICP = 0'),
        'kg',
        'DEFINED (rules applied in both packages; the design-case content question stays TBD_OWNER)',
    ),
    'XL-38': (
        'P1',
        'IF-P1-38',
        ('C_e and C_e,DC with the boundary labelled and the I_e surface; P_mains,in recorded as GROUND/FACILITY_ONLY '
         '(never P_bus evidence)'),
        'W/A; A; W',
        'TBD_AFTER_EVIDENCE (owning stages P1-S4..S5; hardware NOT_PROCURED)',
    ),
    'XL-39': (
        'P2',
        'IDP2-21',
        ('measured P_forward envelope at RP-CPL and Z_antenna map (-> RF_COMPONENT_RATINGS -> flight match '
         'implementation mass / actuator power and generator sizing); laboratory quantities, never P_bus evidence'),
        'W; ohm; kg',
        'TBD_AFTER_IMPEDANCE_MAP (owning stage P2 hot map)',
    ),
    'XL-40': (
        'RFQ',
        'IFD-14',
        ('supplier mass fields for flight-representative options (DC-input RF source, local match, ICP module, '
         'isolation hardware); ceilings only from owner line allocations under the open MQ-01 reading; no ceiling on '
         'GROUND/FACILITY_ONLY lines'),
        'kg',
        ('NOT_IN_THIS_REVISION (flight-representative source NIR-01 is a later separate RFQ; RFQ v2 lines are ground '
         '/ P1 articles; ceilings TBD_OWNER MQ-01)'),
    ),
    'XL-41': (
        'RFQ',
        'IFD-14',
        'DC-input power and efficiency of the flight-representative RF source over the delivered-power range',
        'W',
        'NOT_IN_THIS_REVISION (NIR-01; RF_COMPONENT_RATINGS TBD_AFTER_IMPEDANCE_MAP)',
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
    "P1": ["P1-M-05"],
    "P3": ["P3-IF-S08", "P3-IF-S09", "heat_terms"],
    "P4": ["PR-001", "PR-011", "PR-021", "FINAL_ANODE_MATERIAL"],
    "XE": ["reserve_residual_split", "S1-FL-PRIMARY", "S2-FL-C1"],
    "RFQ": ["NIR-01"],
}
# XE v2 case readings <-> the two mass readings (same owner calls, XA9Q-01 vs MQ-09); scenario per configuration
XE2_READING = {"LOADED_XA9Q01": "LOADED", "USABLE_MQ09": "USABLE_RESIDUAL_ON_TOP"}
XE2_SCENARIO = {"hall_icp_neutralizer": "S1-FL-PRIMARY", "hall_c1_reference": "S2-FL-C1"}
P4_DENSITY_IDS = ("PR-001", "PR-011", "PR-021")


def import_xe_v2(m6: dict) -> dict:
    """XL-30 / XL-31: the Xe residual (both readings, imported ONCE, never computed here) and the design-case headroom
    statuses per flight scenario from the merged Xe accounting v2 (read at build time; values flow XE -> MP only). The
    residual must agree with the immutable mass_a9_v1 import (same owner f_residual, XA9-24); a disagreement refuses
    the build (no silent choice between the two)."""
    xe2 = json.loads((REPO / XLANE_PATHS["XE"]).read_text(encoding="utf-8"))
    dc = xe2["design_cases"]
    res = {"LOADED": {}, "USABLE_RESIDUAL_ON_TOP": {}}
    for r in dc["reserve_residual_split"]["rows"]:
        res[r["reading"]][float(r["case_kg"])] = r["residual_kg"]
    v1 = m6["wet_closure"]["residual"]["by_case_kg"]
    agree = []
    for key, rd in (("inside_case_XA9Q-01", "LOADED"), ("residual_on_top_MQ-09", "USABLE_RESIDUAL_ON_TOP")):
        for k, v in v1[key].items():
            ok = res[rd].get(float(k)) == v
            agree.append({"check": f"mass_a9_v1 {key} {k} kg = Xe v2 {rd} residual", "agrees": ok})
            if not ok:
                raise MassPowerV2Error(f"Xe residual disagreement ({key} {k} kg): v1 {v} vs Xe v2 {res[rd].get(float(k))}")
    head = {}
    for h in dc["headroom"]["rows"]:
        if h["scenario"] not in XE2_SCENARIO.values():
            continue
        rd = h["reading"]["RA-CASE"]
        sub = ", ".join(f"{k}={v}" for k, v in sorted(h["reading"].items()) if k != "RA-CASE")
        head.setdefault((h["scenario"], rd, float(h["case_kg"])), {})[sub] = h["status"]
    return {"source": XLANE_PATHS["XE"], "residual_by_reading_kg": res, "headroom": head, "agreement_with_v1": agree}


def import_p4_densities() -> list:
    """XL-26: candidate densities from the merged P4 property records (read at build time; values flow P4 -> MP only).
    Informational for a later CBE (part mass = density x CAD volume); never booked, never a CBE."""
    p4 = json.loads((REPO / XLANE_PATHS["P4"]).read_text(encoding="utf-8"))
    recs = {r["id"]: r for r in p4["property_records"]}
    cands = {c["id"]: c["name"] for c in p4["candidates"]}
    out = []
    for pid in P4_DENSITY_IDS:
        r = recs.get(pid)
        if r is None or r["property"] != "density" or r["unit_si"] != "kg/m3":
            raise MassPowerV2Error(f"P4 density record {pid} missing or not a density in kg/m3")
        out.append({"id": pid, "candidate": r["candidate"], "material": cands.get(r["candidate"]),
                    "density_kg_m3": r["value_si"], "quantity_type": r["quantity_type"], "source_id": r["source_id"],
                    "locator": r["locator"], "condition": r["condition"],
                    "use_here": "informational: part mass = density x CAD volume once the anode (AL-04) / collector "
                                "(AL-05) geometry exists; not booked, not a CBE; FINAL_ANODE_MATERIAL OPEN"})
    return out


class MassPowerV2Error(ValueError):
    """Malformed or refused input (no default, no fallback)."""


def sha256_file(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins() -> None:
    bad = [(k, p) for k, (p, s, _k) in PINS.items() if sha256_file(p) != s]
    if bad:
        raise SystemExit(f"pinned input changed (sha256 mismatch), refusing to build: {bad}")


def load(key: str):
    return json.loads((REPO / PINS[key][0]).read_text(encoding="utf-8"))


def r6(x):
    return None if x is None else round(float(x) + 0.0, 6)


# ------------------------------------------------------------------------------------------------ owner answers
def answers_by_row() -> dict:
    return {r["row"]: r for r in load("ANS")["answers"]}


def answer_fp(row: int) -> str:
    return hashlib.sha256(answers_by_row()[row]["owner_answer_verbatim"].encode("utf-8")).hexdigest()


def row_src(*rows: int) -> list:
    a = answers_by_row()
    return [{"path": PINS["ANS"][0], "row": r, "covers_ids": a[r]["covers_ids"], "answer_sha256": answer_fp(r)}
            for r in rows]


def dec_src(key: str, decision: str) -> dict:
    return {"path": PINS[key][0], "sha256": PINS[key][1], "decision": decision}


# ======================================================================================================== MASS
# Allocation lines. AL-01..AL-10 are the owner row-54 v0 lines (values read from mass_a9_v1, never changed).
# AL-C1 is the C1 electron-source line of hall_c1_reference: row 54 names no allocation for it (new question MPQ-01).
HARNESS_LINE = "AL-09"          # v1 convention: the 1.0 kg 'controls/harness' line leniently taken as all harness
ICP_ONLY_LINES = ("AL-05", "AL-06")
C1_LINE = "AL-C1"
LINES_BY_CONFIG = {
    "hall_icp_neutralizer": ("AL-01", "AL-02", "AL-03", "AL-04", "AL-05", "AL-06", "AL-07", "AL-08", "AL-09",
                             "AL-10"),
    "hall_c1_reference": ("AL-01", "AL-02", "AL-03", "AL-04", "AL-07", "AL-08", "AL-09", "AL-10", C1_LINE),
}


def v1_lines(m6: dict) -> dict:
    out = {}
    for lc in m6["line_checks"]:
        out[lc["line"]] = {"line": lc["line"], "owner_name": lc["owner_name"], "allocation_kg": lc["allocation_kg"],
                           "allocation_source": lc["allocation_source"], "evidence_floor_kg": lc["evidence_floor_kg"],
                           "floor_is_partial": lc["floor_is_partial"], "v1_state": lc["state"],
                           "floor_arithmetic": lc["arithmetic"],
                           "floor_constituents": [{k: c.get(k) for k in ("what", "kg", "evidence_class", "status")}
                                                  for c in lc["evidence"].get("constituents", [])],
                           "floor_status": lc["evidence"].get("status")}
    return out


def c1_line(m6: dict) -> dict:
    """AL-C1: no owner allocation (TBD_OWNER, MPQ-01). Evidence floor = C1 cathode-unit analog low end only.

    The C1 cathode Xe branch (A9B-C04, 0.285 kg) is NOT added here: it is one branch of the H2-7 H27-12 two-branch
    valve set (2 x (latch + PFCV) = 0.57 kg) that is already a constituent of the AL-08 evidence floor 5.044 kg; the C1
    supplies (A9B-C03) sit inside the AL-07 PPU analogs (their scope includes cathode heater/keeper supplies)."""
    c = {e["id"]: e for e in m6["a9_flight_bom"]["c1_dropped_from_flight"]}
    lo = c["A9B-C01"]["value"][0]
    return {"line": C1_LINE, "owner_name": "C1 electron-source line (hall_c1_reference only)", "allocation_kg": None,
            "allocation_status": f"{TBD_OWNER} - row 54 names no allocation for C1 flight hardware (MPQ-01)",
            "allocation_source": [], "evidence_floor_kg": lo, "floor_is_partial": True,
            "v1_state": None, "floor_status": None,
            "floor_arithmetic": (f"floor = C1 cathode unit analog low end {lo} kg (A9B-C01, H2-7 H27-16, inferred); "
                                 "shield/mount (A9B-C02) and filter/getter (A9B-C05) TBD; the C1 cathode Xe branch "
                                 "0.285 kg (A9B-C04) is already inside the AL-08 floor (H2-7 H27-12 two-branch 0.57 kg) "
                                 "and C1 supplies (A9B-C03) inside the AL-07 PPU analogs: not added twice"),
            "floor_constituents": [{"what": "C1 cathode unit analog low end (A9B-C01)", "kg": lo,
                                    "evidence_class": c["A9B-C01"]["evidence_class"], "status": "PRELIMINARY (analog)"},
                                   {"what": "C1 shield / O-isolation / mount (A9B-C02)", "kg": None,
                                    "evidence_class": None, "status": "TBD - requires a flight C1 module design"},
                                   {"what": "Xe cathode-line filter/getter (A9B-C05)", "kg": None,
                                    "evidence_class": None, "status": "TBD - requires vendor/spec verification (row 51)"}]}


def line_state(alloc, floor, partial: bool) -> str:
    if alloc is None:
        return "ALLOCATION_ABSENT_TBD_OWNER"
    if floor is not None and floor > alloc:
        return "ALLOCATION_BELOW_EVIDENCE_FLOOR"
    if floor is None or partial:
        return "ALLOCATION_UNVERIFIABLE_TBD"
    return "CONSISTENT"


# ---------------------------------------------------------------------------------------- dry / wet roll-up (pure)
READINGS = {
    "OWNER_V0_LITERAL": ("reference only (not an MQ-01 reading): row-54 allocations + 4 kg dry development reserve, "
                         "no further margin (the owner's v0 budget read literally; v1 R0)"),
    "MQ01_MEV_LEVEL": ("MQ-01 reading A: each row-54 allocation already contains its row-57 equipment margin; harness = "
                       "max(1.0 kg line, row-60 policy f/(1-f) x other nominal dry); row-52 20 % system margin on "
                       "nominal dry replaces the 4 kg reserve (MQ-02 reading of v1; v1 R1)"),
    "MQ01_CBE_LEVEL": ("MQ-01 reading B: row-57 20 % equipment margin on every non-harness line; harness = max(1.0 kg "
                       "line, row-60 policy), margin 0; row-52 20 % system margin on nominal dry replaces the 4 kg "
                       "reserve (v1 R2)"),
}
BASES = {
    "ALLOCATIONS": "every line at its owner allocation; a line without allocation contributes 0 kg and is unresolved",
    "WITH_EVIDENCE_FLOORS": ("lines with a verified evidence floor carry the floor (CBE-level: x(1 + row-57 margin) in "
                             "both MQ-01 readings, v1 R1E/R2E convention); others stay at their allocation"),
}


def dry_rollup(lines: list, reading: str, basis: str, reserve_kg: float, f_harness: float, mga: float,
               sys_margin: float) -> dict:
    """Dry mass of one configuration under one reading and basis. Pure arithmetic on the caller's line records.

    lines: [{'line', 'allocation_kg' (float|None), 'evidence_floor_kg' (float|None), 'is_harness' (bool)}]. Every
    field is required (no default). A line without allocation and without a usable floor contributes 0 kg and is
    listed in 'unresolved'; the result is then a known part, never a total."""
    if reading not in READINGS or basis not in BASES:
        raise MassPowerV2Error(f"unknown reading/basis {reading!r}/{basis!r}")
    for name, v in (("reserve_kg", reserve_kg), ("f_harness", f_harness), ("mga", mga), ("sys_margin", sys_margin)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise MassPowerV2Error(f"{name} must be a finite number >= 0 (no default), got {v!r}")
    if not 0 <= f_harness < 1:
        raise MassPowerV2Error("f_harness must be in [0, 1)")
    harness = [ln for ln in lines if ln["is_harness"]]
    if len(harness) != 1:
        raise MassPowerV2Error("exactly one harness line is required (row 60 policy line)")
    unresolved, parts, nonharness_nominal = [], [], 0.0
    for ln in lines:
        for k in ("line", "allocation_kg", "evidence_floor_kg", "is_harness"):
            if k not in ln:
                raise MassPowerV2Error(f"line record lacks {k!r} (no default)")
        if ln["is_harness"]:
            continue
        a, f = ln["allocation_kg"], ln["evidence_floor_kg"]
        if basis == "WITH_EVIDENCE_FLOORS" and f is not None:
            cbe_level, used = f, "EVIDENCE_FLOOR"
        elif a is not None:
            cbe_level, used = None, "ALLOCATION"
        else:
            cbe_level, used = None, "UNRESOLVED"
        if used == "UNRESOLVED":
            unresolved.append(f"{ln['line']}: no owner allocation and no evidence floor on this basis ({TBD_OWNER})")
            parts.append({"line": ln["line"], "used": used, "kg": 0.0})
            continue
        if reading == "OWNER_V0_LITERAL":
            v = cbe_level if used == "EVIDENCE_FLOOR" else a
        elif reading == "MQ01_MEV_LEVEL":
            v = cbe_level * (1 + mga) if used == "EVIDENCE_FLOOR" else a
        else:  # MQ01_CBE_LEVEL
            v = (cbe_level if used == "EVIDENCE_FLOOR" else a) * (1 + mga)
        if used == "EVIDENCE_FLOOR":
            unresolved.append(f"{ln['line']}: evidence floor (analog / preliminary design, partial) used, not a CBE")
        else:
            unresolved.append(f"{ln['line']}: owner allocation, not a CBE (row 54)")
        parts.append({"line": ln["line"], "used": used, "kg": r6(v)})
        nonharness_nominal += v
    h = harness[0]
    unresolved.append(f"{h['line']}: harness by the row-60 policy until a routed harness exists (not a CBE)")
    if reading == "OWNER_V0_LITERAL":
        h_kg = h["allocation_kg"]
        dry = nonharness_nominal + h_kg + reserve_kg
        out = {"nonharness_nominal_kg": r6(nonharness_nominal), "harness_kg": r6(h_kg), "nominal_dry_kg": None,
               "system_margin_kg": None, "reserve_kg": reserve_kg, "dry_known_kg": r6(dry)}
    else:
        h_kg = max(h["allocation_kg"], f_harness / (1 - f_harness) * nonharness_nominal)
        nominal = nonharness_nominal + h_kg
        margin = sys_margin * nominal
        out = {"nonharness_nominal_kg": r6(nonharness_nominal), "harness_kg": r6(h_kg), "nominal_dry_kg": r6(nominal),
               "system_margin_kg": r6(margin), "reserve_kg": 0.0, "dry_known_kg": r6(nominal + margin),
               "dry_if_reserve_additive_MQ02_kg": r6(nominal + margin + reserve_kg)}
    parts.append({"line": h["line"], "used": "HARNESS_POLICY_ROW60" if reading != "OWNER_V0_LITERAL" else "ALLOCATION",
                  "kg": r6(h_kg)})
    out.update({"reading": reading, "basis": basis, "parts": parts, "unresolved": unresolved,
                "all_terms_resolved": False,
                "every_line_has_a_value": not any(p["used"] == "UNRESOLVED" for p in parts)})
    return out


XE_CASE_READINGS = {
    "LOADED_XA9Q01": ("case = LOADED Xe incl. reserve and residual (A9-08 XA9Q-01 PROPOSED); residual inside the case, "
                      "not added"),
    "USABLE_MQ09": ("case = usable Xe incl. the row-43 reserve (A9-06 MQ-09 PROPOSED); residual imported on top once "
                    "(row 45)"),
}


def wet_cell(dry: dict, xe_case_kg: float, reading: str, residual_on_top_kg: float, ref_kg: float,
             strict: bool) -> dict:
    """Wet mass known part and state against one reference. Residual booked once (row 45): inside the case under
    LOADED_XA9Q01, added on top under USABLE_MQ09. CLOSES only when every term is resolved (never today)."""
    if reading not in XE_CASE_READINGS:
        raise MassPowerV2Error(f"unknown Xe case reading {reading!r}")
    for n, v in (("xe_case_kg", xe_case_kg), ("residual_on_top_kg", residual_on_top_kg), ("ref_kg", ref_kg)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise MassPowerV2Error(f"{n} must be a finite number >= 0 (no default), got {v!r}")
    add = residual_on_top_kg if reading == "USABLE_MQ09" else 0.0
    wet = dry["dry_known_kg"] + xe_case_kg + add
    exceeded = wet >= ref_kg if strict else wet > ref_kg
    if exceeded:
        state = "DOES_NOT_CLOSE"
    elif dry["all_terms_resolved"]:
        state = "CLOSES"
    else:
        state = "NOT_EVALUABLE"
    return {"xe_case_kg": xe_case_kg, "xe_case_reading": reading, "residual_added_on_top_kg": r6(add),
            "wet_known_kg": r6(wet), "reference_kg": ref_kg, "comparator": ("<" if strict else "<="),
            "margin_to_reference_kg": None if exceeded else r6(ref_kg - wet), "state": state}


# ---------------------------------------------------------------------------------------------------- BOM v2
def _cfg(icp: str, c1: str) -> dict:
    return {"hall_icp_neutralizer": icp, "hall_c1_reference": c1}


XE_WET_TERMS = ("A9B-13", "A9B-14")   # Xe load (design case) and imported residual: wet terms, never dry lines
INSTALL_STATES = ("INSTALLED", "NOT_INSTALLED", "VARIANT_ONLY", "GROUND_ONLY", "REMOVED_PREIONIZER_ONLY",
                  "WET_TERM_XE_ACCOUNTING")
# A9.2 .. A9.6 propagation per v1 line (decision ids + text); applied on top of the v1 entry, v1 text is preserved.
V2_UPDATES = {
    "A9B-15": ("A92:anode_316L; A92:anode_approach; A96:fixed_statuses",
               "316L_FLIGHT_ANODE = REJECTED_AS_CURRENT_BASELINE; FINAL_ANODE_MATERIAL = OPEN; anode mass TBD - requires "
               "the P4 material trade and the anode heat-removal design (" + "{P4}" + "); no material is selected here"),
    "A9B-16": ("A92:coil_mass_correction",
               "MC-1 floor books the complete-coil copper 1.579 kg (H2-1 H21-24; ~1.58 kg per A9.2) + iron 1.925 kg; the "
               "0.136 kg 60 W fixed-NI basis is a sensitivity basis only and is never booked (A9.2 coil_mass_correction)"),
    "A9B-17": ("A93:OQ-VI-03; A92:radiative_view_requirement; A93:OQ-RFQ-10; A94:P1Q-14",
               "open-tube coaxial first build (A9.3 OQ-VI-03); radiative-view-factor objective (open-frame support, "
               "A9.2); capped dedicated gas port retained (A9.3 OQ-RFQ-10); ICP body floating (row 70); mass TBD - "
               "requires a flight ICP module design"),
    "A9B-18": ("A92:anode_approach; A96:fixed_statuses; A95:P1Q-15",
               "collector material not frozen (O/AO coupon programme; " + "{P4}" + "); isolation per A9.4 P1Q-14 booked "
               "separately (MPV2-N01)"),
    "A9B-19": ("A93:OQ-RFQ-06; A92:rf_500W",
               "flight source = FLIGHT_REPRESENTATIVE_DC_RF_SOURCE (A9.3 OQ-RFQ-06), design/supplier TBD; the mains-"
               "powered laboratory generator is GROUND/FACILITY_ONLY (GA-02) and never in the flight BOM or P_bus; "
               "RF_COMPONENT_RATINGS = TBD_AFTER_IMPEDANCE_MAP"),
    "A9B-20": ("A92:OQ-A907-11; A92:icp_matching_strategy",
               "local adjustable match on / immediately adjacent to the ICP module for the development article; the "
               "flight implementation (fixed / switched / electronically tuned / other) only after Z_antenna = R + jX "
               "is mapped (P2); status LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT; allocation mapping AL-05 vs AL-06 stays "
               "open (MQ-07)"),
    "A9B-21": ("A92:OQ-A907-11",
               "chain generator -> directional coupler -> 50-ohm line -> local match -> antenna; no long unmatched coax "
               "(A9.2 supersedes that A9.1 arrangement); line length and feedthrough TBD"),
    "A9B-22": ("A93:OQ-A907-02; A94:i_d_max_h1; A95:P1Q-16",
               "flight rating TBD - requires I_d,max,H1 from registered H-1 operation (NOT_EVALUATED, A9.4); the 8.33 A "
               "bench ceiling is a ground stand/conductor rating only (A9.3 OQ-A907-02), never a flight requirement"),
    "A9B-23": ("A93:OQ-RFQ-10; A93:ICPQ-06",
               "quote-option only (A9.3 OQ-RFQ-10); if G-ATM / G-XE is activated, mdot_ICP,dedicated is booked in the "
               "corresponding ledger and a gas isolator applies where the line bridges isolated potentials (MPV2-N06)"),
    "A9B-29": ("A92:rf_measurement_reference; A92:rf_protection",
               "ICP telemetry per row 62 incl. RF forward/reflected; RF protection electronics booked separately "
               "(MPV2-N02); in hall_c1_reference the C1 keeper/heater telemetry (A9B-C07) applies instead of the ICP "
               "channels"),
    "A9B-30": ("A92:icp_coupled_thermal; A92:13W_pole_allowance; A96:fixed_statuses",
               "ANODE_THERMAL_CLOSURE = UNRESOLVED; ICP_COUPLED_THERMAL = UNRESOLVED; thermal hardware mass TBD - "
               "requires the coupled thermal model with Q_Hall->ICP, Q_collector, Q_RF/match, Q_plume and the ICP view-"
               "factor effect (" + "{P3}" + "); no thermal PASS"),
    "A9B-31": ("A92:radiative_view_requirement",
               "downstream coaxial ICP mount (hall_icp_neutralizer only) designed to the radiative-view objective "
               "(open-frame, Hall-to-ICP axial spacing); mass TBD"),
    "A9B-C03": ("A91:ICP-46; A93:OQ-A907-02",
                "hall_c1_reference flight fallback supplies (heater, keeper 300-600 V pulsed class row 89, common tie); "
                "mass inside the AL-07 PPU analog scope or AL-C1 (MPQ-01)"),
}
NEW_V2_LINES = [
    {"id": "MPV2-N01", "name": "ICP body / collector isolation hardware (isolators, standoffs, isolated feedthroughs): "
                                "350 V operating class, >= 525 V design-withstand basis, initial 1.05 kV DC / 60 s "
                                "passive-insulation DWV where applicable",
     "group": "icp", "configs": _cfg("INSTALLED", "NOT_INSTALLED"), "allocation_line": "AL-05",
     "allocation_mapping": "PROPOSED_MAPPING (MPQ-02)", "power_slots": [], "decisions": ["A94:P1Q-14"],
     "cbe_tbd": "TBD - requires the ICP isolation design (does not close ICP-44 RF insulation)", "m16_row": None},
    {"id": "MPV2-N02", "name": "flight RF protection and sensing electronics: forward/reflected power monitoring on the "
                                "generator / 50-ohm side of the local match, mismatch interlock, arc detection where "
                                "feasible, thermal monitoring, automatic RF reduction/shutdown",
     "group": "icp", "configs": _cfg("INSTALLED", "NOT_INSTALLED"), "allocation_line": "AL-06",
     "allocation_mapping": "PROPOSED_MAPPING (MPQ-02)", "power_slots": ["icp_rf_source"],
     "decisions": ["A92:rf_measurement_reference", "A92:rf_protection"],
     "cbe_tbd": "TBD - requires the flight RF chain design; trip thresholds frozen only after antenna/load "
                "characterization (A9.2)", "m16_row": 12},
    {"id": "MPV2-N03", "name": "H-1 anode heat-removal path hardware (backplate conduction, support/feed-tube "
                                "conduction, spreading, radiative area)",
     "group": "hall", "configs": _cfg("INSTALLED", "INSTALLED"), "allocation_line": "AL-04",
     "allocation_mapping": "PROPOSED_MAPPING (MPQ-02)", "power_slots": [], "decisions": ["A92:anode_approach"],
     "cbe_tbd": "TBD - requires the anode design (" + "{P4}" + ") and the thermal model (" + "{P3}" + "); "
                "ANODE_THERMAL_CLOSURE = UNRESOLVED", "m16_row": 9},
    {"id": "MPV2-N04", "name": "ICP open-frame support / radiative-view hardware and Hall-to-ICP axial spacer",
     "group": "structure", "configs": _cfg("INSTALLED", "NOT_INSTALLED"), "allocation_line": "AL-10",
     "allocation_mapping": "PROPOSED_MAPPING (MPQ-02)", "power_slots": [],
     "decisions": ["A92:radiative_view_requirement", "A92:13W_pole_allowance"],
     "cbe_tbd": "TBD - requires the ICP mechanical design and the coupled view-factor calculation (" + "{P3}" + ")",
     "m16_row": 16},
    {"id": "MPV2-N05", "name": "active cooling hardware (pump / fan / TEC) - only if passive heat removal fails",
     "group": "thermal", "configs": _cfg("VARIANT_ONLY", "VARIANT_ONLY"), "allocation_line": None,
     "allocation_mapping": "VARIANT (booked only when the active_cooling variant is declared)",
     "power_slots": ["active_cooling"], "decisions": ["A92:anode_approach"],
     "cbe_tbd": "TBD - variant not declared", "m16_row": 13},
    {"id": "MPV2-N06", "name": "gas isolator on a dedicated ICP feed line bridging isolated potentials (~1 kV DC "
                                "representative-gas development qualification)",
     "group": "icp", "configs": _cfg("VARIANT_ONLY", "NOT_INSTALLED"), "allocation_line": None,
     "allocation_mapping": "VARIANT (G-ATM / G-XE only; none where both ends float at the same potential)",
     "power_slots": [], "decisions": ["A93:ICPQ-06", "A93:OQ-RFQ-10"],
     "cbe_tbd": "TBD - variant not declared", "m16_row": None},
]
NEW_GROUND = [
    {"id": "GA-05", "item": "photodiode, optical access/window, amplifier and DAQ channel (P1/P2 plasma-state indicator; "
                            "states UNLIT / E_MODE / H_MODE / UNCERTAIN)",
     "rule": "ground instrumentation (A9.4 P2Q-05); no flight mass"},
    {"id": "GA-06", "item": "laboratory collector/bias circuit, conductors, current sensors and feedthroughs sized to the "
                            "8.33 A stand ceiling (1500 W / 180 V)",
     "rule": "ground stand rating only (A9.3 OQ-A907-02); not evidence that H-1 requires 8.33 A; no flight mass"},
    {"id": "GA-07", "item": "power analyzer for P_mains,in of the mains-powered laboratory 13.56 MHz generator",
     "rule": "GROUND/FACILITY_ONLY (A9.3 OQ-RFQ-06): P_mains,in is an engineering quantity, never P_bus evidence"},
    {"id": "GA-08", "item": "H-1 body single-point metered ground return and floating-anode high-impedance V_anode "
                            "channel for ICP-45 discharge-OFF capacity records",
     "rule": "ground test configuration (A9.4 P1Q-13, A9.5 P1Q-15); no flight mass"},
]


def _fill(s: str) -> str:
    return s.replace("{P3}", MERGED_REF["P3"] + " (inputs TBD; ICP_COUPLED_THERMAL / ANODE_THERMAL_CLOSURE "
                     "UNRESOLVED)").replace("{P4}", MERGED_REF["P4"] + " (FINAL_ANODE_MATERIAL OPEN)")


def build_bom(m6: dict) -> list:
    b = m6["a9_flight_bom"]
    icp_items = {"A9B-17", "A9B-18", "A9B-19", "A9B-20", "A9B-21", "A9B-22"}
    out = []

    def col_floor(e):
        if e.get("value") is None or e.get("evidence_class") in (None, "owner-allocation", "assumed"):
            return None
        return {"value": e["value"], "units": e["units"], "evidence_class": e["evidence_class"], "basis": e["basis"],
                "note": "analog / preliminary-design value copied by pointer from mass_a9_v1 (not a CBE)"}

    def add(e, configs, cls, line=None, mapping=None):
        upd = V2_UPDATES.get(e["id"])
        wet = cls == "WET_TERM"
        out.append({
            "id": e["id"], "v1_list": cls, "name": e["name"], "group": e["group"], "configurations": configs,
            "allocation_line": line if line is not None else e.get("allocation_line"),
            "allocation_mapping": mapping or e.get("allocation_mapping"),
            "power_slots_a9": list(e.get("power_slots_a9", [])), "m16_row": e.get("m16_row"),
            "columns": {
                "ALLOCATION": {"value": None, "rule": "line-level only: see lines[] (an item never carries a share of "
                                                      "its line allocation)"},
                "EVIDENCE_FLOOR": None if wet else col_floor(e),
                "CBE": {"value": None, "status": (
                    "not a dry-mass line: Xe accounting term (wet roll-up)" if wet else
                    _fill(e["status"]) if e.get("value") is None else
                    "TBD - no Vyovrinda CBE exists (the v1 value is an analog / preliminary-design floor, never a CBE)")},
                "MEASURED": {"value": None, "status": "TBD - requires a weighed flight-representative article (S1a "
                                                      "weighs ground articles; ICD ICP-08)"},
            },
            "v1_status": e["status"], "freeze_point": e["freeze_point"], "owner_rows": e.get("owner_rows", []),
            "a9_1_decisions": e.get("a9_1_decisions", []),
            "v2_decisions": [] if not upd else [x.strip() for x in upd[0].split(";")],
            "v2_propagation": None if not upd else _fill(upd[1]),
        })

    for e in b["flight"]:
        if e["id"] in XE_WET_TERMS:
            add(e, _cfg("WET_TERM_XE_ACCOUNTING", "WET_TERM_XE_ACCOUNTING"), "WET_TERM", line="-",
                mapping="Xe propellant term (design case / imported residual): wet roll-up only, never dry mass")
            continue
        cfgs = _cfg("INSTALLED", "NOT_INSTALLED" if e["id"] in icp_items else "INSTALLED")
        add(e, cfgs, "flight")
    for e in b["variant_only"]:
        add(e, _cfg("VARIANT_ONLY", "NOT_INSTALLED"), "variant_only")
    for e in b["c1_dropped_from_flight"]:
        if e["id"] == "A9B-C06":
            add(e, _cfg("NOT_INSTALLED", "WET_TERM_XE_ACCOUNTING"), "WET_TERM", line="-",
                mapping="Xe propellant term: inside the Xe design case of scenario FL-C1 (A9 Xe ledger); never dry mass")
        else:
            add(e, _cfg("NOT_INSTALLED", "INSTALLED"), "c1_fallback", line=C1_LINE,
                mapping="PROPOSED_MAPPING (MPQ-01; no owner allocation)")
    for e in b["removed_preionizer_only"]:
        add(e, _cfg("REMOVED_PREIONIZER_ONLY", "REMOVED_PREIONIZER_ONLY"), "removed_preionizer_only")
    for n in NEW_V2_LINES:
        out.append({
            "id": n["id"], "v1_list": "NEW_V2", "name": n["name"], "group": n["group"], "configurations": n["configs"],
            "allocation_line": n["allocation_line"], "allocation_mapping": n["allocation_mapping"],
            "power_slots_a9": n["power_slots"], "m16_row": n["m16_row"],
            "columns": {"ALLOCATION": {"value": None, "rule": "line-level only: see lines[]"},
                        "EVIDENCE_FLOOR": None,
                        "CBE": {"value": None, "status": _fill(n["cbe_tbd"])},
                        "MEASURED": {"value": None, "status": "TBD - requires a weighed article"}},
            "v1_status": None, "freeze_point": "after-evidence", "owner_rows": [], "a9_1_decisions": [],
            "v2_decisions": n["decisions"], "v2_propagation": "new line (A9.2 .. A9.6 propagation)"})
    for x in out:
        for c, s in x["configurations"].items():
            if s not in INSTALL_STATES:
                raise MassPowerV2Error(f"{x['id']} {c}: bad install state {s}")
    return out


def ground_articles(m6: dict) -> list:
    g = [dict(x) for x in m6["a9_flight_bom"]["ground_article_only"]]
    for x in g:
        if x["id"] == "GA-02":
            x["v2_note"] = ("A9.3 OQ-RFQ-06: the mains-powered laboratory 13.56 MHz generator is GROUND/FACILITY_ONLY; "
                            "its P_mains,in is never P_bus evidence; the flight source is a FLIGHT_REPRESENTATIVE_DC_RF_"
                            "SOURCE (A9B-19)")
    return g + [dict(x) for x in NEW_GROUND]


# ======================================================================================================== POWER
# Allocation envelope membership per slot (owner allocations only; no fixed Hall/ICP split, A9.1 OQ-A902-03).
def slot_envelope(slot: str) -> str:
    s = bb.SLOTS[slot]
    if s.get("controls_thermal"):
        return "COMMON_300W / CONTROLS_THERMAL_50W (row 114; A9.1 OQ-A902-02)"
    if s.get("common_allocation"):
        return "COMMON_300W (row 114; A9.1 OQ-A902-02)"
    if s["group"] in ("hall", "icp", "c1"):
        return ("HALL_AND_ELECTRON_SOURCE (inside 1350 W - P_common - P_other,active; no fixed split, A9.1 "
                "OQ-A902-03)")
    return "OTHER_ACTIVE (inside 1350 W as P_other,active; outside the 300 W common allocation unless reallocated)"


SLOT_TBD = {
    "hall_discharge": ("TBD - requires the registered H-1 operating envelope and a measured flight-representative "
                       "discharge supply (row 113); no Hall closure or 0-D number is used"),
    "hall_magnet_inner": ("TBD - requires the frozen H-1 coil (A9-07 IDA7-01); context only: RP-1 as sized 5.164 W at "
                          "20 degC for the coil set (model-derived), H25-08 0-60 W evaluation range (assumed); bases "
                          "not reconciled"),
    "hall_magnet_outer": "TBD - requires the frozen H-1 coil (A9-07 IDA7-01); see hall_magnet_inner context",
    "hall_magnet_trim": "TBD - requires the frozen H-1 coil and trim-coil use (0 W explicitly when unpowered)",
    "c1_heater": ("TBD - requires the C1 procedure heater power (A9.1 SEQ-heater); no conservative booked power exists, "
                  "so the ledger stays incomplete (a TBD heater is never assumed off)"),
    "c1_keeper": "TBD - requires the C1 keeper operating point and the pulsed-ignition (300-600 V class, row 89) record",
    "c1_common_tie": "TBD - requires the cathode-common network design (row 91)",
    "filter_getter": "TBD - requires vendor/spec verification (row 51: <= 17 W class only after verification)",
    "icp_rf_source": ("TBD - requires a FLIGHT_REPRESENTATIVE_DC_RF_SOURCE with measured P_DC,in at the registered "
                      "ICP-45 point (A9.3 OQ-RFQ-06); C_e,DC from P1 is labelled by its boundary; the mains laboratory "
                      "generator (GROUND/FACILITY_ONLY) never enters P_bus"),
    "icp_matching_network": ("TBD - requires the flight match implementation after the P2 impedance map (A9.2 "
                             "icp_matching_strategy); exactly 0 W only for a fixed passive match"),
    "icp_collector_bias": ("TBD - requires V_bias x I_collector at the registered point; I_d,max,H1 NOT_EVALUATED "
                           "(A9.4); the 8.33 A stand ceiling is not a flight requirement (A9.3 OQ-A907-02)"),
    "flow_control_atmospheric": "TBD - requires the atmospheric valve driver design",
    "flow_control_xe": "TBD - requires the Xe valve driver design (incl. the two series isolation valves, row 90)",
    "compressor": "TBD - requires the compressor ICD (row 22)",
    "thermal_control": ("TBD - requires the coupled thermal model (" + "{P3}" + "); ICP_COUPLED_THERMAL and "
                        "ANODE_THERMAL_CLOSURE UNRESOLVED"),
    "housekeeping_controls": ("TBD - requires the controller design incl. the explicitly booked quiescent draw of "
                              "energised-idle supplies and the front end (module limitation)"),
}
EFF_TBD = "TBD - requires the selected supply / converter efficiency at this load (measured or cited)"
FRONT_END_TBD = "TBD - requires the spacecraft bus specification (row 111: configurable front end)"
RESERVED_PORT = {"P_W": 0.0, "evidence_class": "assumed",
                 "source": "row 110 reserved DC port: no load assigned in the A9 configurations (declared unused)"}
OFF_SOURCE = "slot not commanded ON at this step of the PROPOSED start-up template (row 112; bus_boundary_a9)"


def _tbd_load(slot: str) -> dict:
    rec = {"P_W": bb.TBD, "tbd_requires": _fill(SLOT_TBD[slot])}
    if slot == "icp_rf_source":
        rec["plane"] = "generator_dc_input"
    return rec


def _off_load(slot: str) -> dict:
    rec = {"P_W": 0.0, "evidence_class": "assumed", "source": OFF_SOURCE}
    if slot == "icp_rf_source":
        rec["plane"] = "generator_dc_input"
    return rec


def _effs(config: str) -> dict:
    return {s: {"value": bb.TBD, "tbd_requires": EFF_TBD, "path": "internal_bus"}
            for s in bb.installed_slots(config)}


def template_steps(config: str) -> list:
    """Module start-up template with explicit loads: slots ON so far -> TBD; others -> exactly 0 W (declared OFF)."""
    inst = bb.installed_slots(config)
    on, steps = set(), []
    tpl = bb.SEQUENCE_TEMPLATES[config]
    for i, t in enumerate(tpl):
        on |= set(t["on"])
        loads = {}
        for s in inst:
            if s == "reserved_dc_port":
                loads[s] = dict(RESERVED_PORT)
            elif s in on:
                loads[s] = _tbd_load(s)
            else:
                loads[s] = _off_load(s)
        st = {"step_id": t["step_id"], "event": t["event"], "loads": loads, "efficiencies": _effs(config),
              "power_basis": "p_bus_1ms_max"}
        # template 'requires_flags' (keeper/discharge stable) are NOT asserted: no evidence exists for them
        if i == len(tpl) - 1:
            st["phase"] = "steady"
        steps.append(st)
    return steps


def power_section() -> dict:
    fe = {"value": bb.TBD, "tbd_requires": FRONT_END_TBD}
    per_cfg = {}
    for c in CONFIGS:
        inst = bb.installed_slots(c)
        tpl = bb.SEQUENCE_TEMPLATES[c]
        on_at = {}
        for t in tpl:
            for s in t["on"]:
                on_at.setdefault(s, t["step_id"])
        peak = {v: k for k, v in bb.PEAK_EVENTS.items()}
        slots = []
        for s in inst:
            slots.append({
                "slot": s, "group": bb.SLOTS[s]["group"], "rows": bb.SLOTS[s]["rows"],
                "load_plane": bb.SLOTS[s]["load_plane"], "envelope": slot_envelope(s),
                "ALLOCATION_W": None if s != "reserved_dc_port" else 0.0,
                "allocation_rule": ("no per-slot owner allocation exists: the slot sits in the envelope named; "
                                    "A9.1 OQ-A902-03 forbids a fixed Hall/ICP split") if s != "reserved_dc_port"
                else "declared unused (0 W explicit, row 110)",
                "CBE_W": None, "MEASURED_W": None,
                "status": "declared unused" if s == "reserved_dc_port" else _fill(SLOT_TBD[s]),
                "first_on_step": on_at.get(s), "peak_class_event": peak.get(s),
                "efficiency": "TBD (path internal_bus: row 111 / A9.1 OQ-A902-06 default; " + EFF_TBD + ")"})
        steps = template_steps(c)
        seq = bb.check_startup_sequence(c, steps, fe)
        steady = bb.ledger(c, steps[-1]["loads"], steps[-1]["efficiencies"], fe, label="steady (all TBD)",
                           power_basis="p_bus_1ms_max")
        alloc = bb.allocation_checks(steady)
        icp_chk = bb.icp_power_allocation_check(steady) if c == "hall_icp_neutralizer" else None
        per_cfg[c] = {
            "installed_slots": list(inst),
            "variant_options_not_installed": list(bb.VARIANT_OPTIONS[c]),
            "slots": slots,
            "phases": {
                "steady": {"ledger_status": steady["status"], "P_bus_W": steady["P_bus_W"],
                           "P_bus_lower_bound_W": steady["P_bus_lower_bound_W"], "tbd_count": len(steady["tbd"]),
                           "design_allocation_1350W": alloc["design_allocation"]["verdict"],
                           "a5_1300W_context": alloc["a5_lower_allocation"]["verdict"],
                           "common_300W": alloc["common_allocation"]["verdict"],
                           "controls_thermal_50W": alloc["controls_thermal_allowance"]["verdict"],
                           "icp_available_check": None if icp_chk is None else {
                               "relation": icp_chk["relation"], "verdict": icp_chk["verdict"],
                               "P_ICP_available_upper_bound_W": icp_chk["P_ICP_available_upper_bound_W"]}},
                "startup": {"template": "bus_boundary_a9.SEQUENCE_TEMPLATES (PROPOSED, row 112)",
                            "sequence_status": seq["sequence_status"],
                            "violations": seq["violations"], "not_evaluable_rules": len(seq["not_evaluable"]),
                            "dependent_rises": [d["step_id"] for d in seq["dependent_rises"]],
                            "steps": [{"step_id": s["step_id"], "event": t["event"], "name": t["name"],
                                       "on": list(t["on"]), "ledger_status": s["status"],
                                       "P_bus_lower_bound_W": s["P_bus_lower_bound_W"]}
                                      for s, t in zip(seq["steps"], tpl)]},
                "peak": {"events": {k: v for k, v in bb.PEAK_EVENTS.items() if v in inst},
                         "rule": ("start-up peaks enter the gate only as P_bus,1ms,max (A9.1 OQ-A902-01); the "
                                  "unaveraged sampled peak is a protection record, NOT_EVALUABLE for the gate (OQ-A910-03 "
                                  "OPEN, not implemented); at most one peak-class load commanded to rise per step "
                                  "(A9.1 SEQ-peaks)"),
                         "values": "TBD (no measured transient record exists)"},
            },
            "rfp_gate_1ms": {"verdict": seq["transient_gate"]["verdict"],
                             "rows": [{"role": r["role"], "label": r["label"], "verdict": r["verdict"],
                                       "status": r["status"]} for r in seq["transient_gate"]["rows"]]},
        }
    common_up = bb.COMMON_ALLOCATION_W
    return {
        "boundary_version": bb.BOUNDARY_VERSION, "module": PINS["BBMOD"][0], "module_sha256": PINS["BBMOD"][1],
        "use": "import only (never modified; not wired into archengine)",
        "gate": {"quantity": bb.TRANSIENT_WINDOW["quantity"], "limit_W": bb.P_BUS_REQUIREMENT_W, "strict": True,
                 "window_s": bb.GATE_WINDOW_S, "min_bandwidth_Hz": bb.GATE_MIN_BANDWIDTH_HZ,
                 "min_sample_rate_Sa_s": bb.GATE_MIN_SAMPLE_RATE_SA_S, "applies_to": ["steady", "startup"],
                 "decision": "row 108; A9.1 OQ-A902-01 (A9 engineering definition pending authoritative RFP wording)",
                 "pass_requires": "a declared p_bus_1ms_max ledger with a conformant gate_measurement record and every "
                                  "load known; no step average is substituted"},
        "allocations": {
            "design_allocation_W": {"value": bb.DESIGN_ALLOCATION_W, "row": 109, "kind": "OWNER_ALLOCATION (not a gate)",
                                    "rule": "the ICP fits inside it; the 1350 -> 1500 W margin is not consumed "
                                            "nominally (row 109)"},
            "a5_context_W": {"value": bb.A5_ALLOCATION_RANGE_W[0], "kind": "context / sensitivity (A9.1 OQ-A902-07)"},
            "common_allocation_W": {"value": common_up, "row": 114, "kind": "OWNER_ALLOCATION, upper design value",
                                    "composition": "compressor + atm/Xe/ICP flow control + filter/getter if active + "
                                                   "thermal control + housekeeping/controls (A9.1 OQ-A902-02)"},
            "controls_thermal_allowance_W": {"value": bb.CONTROLS_THERMAL_ALLOWANCE_W, "row": 114,
                                             "kind": "inside the 300 W common allocation"},
            "hall_and_electron_source_envelope_at_common_upper_W": {
                "value": r6(bb.DESIGN_ALLOCATION_W - common_up),
                "arithmetic": f"{bb.DESIGN_ALLOCATION_W} - {common_up} - 0 (P_other,active = 0: no variant declared, "
                              f"reserved port unused)",
                "kind": ("deterministic arithmetic on owner allocations, valid only while P_common is at its 300 W "
                         "upper value and no other load is active; NOT a sub-allocation (A9.1 OQ-A902-03: no fixed "
                         "Hall/ICP split); a lower P_common widens it")},
            "icp_relation": "P_ICP,available = 1350 - P_common - P_Hall - P_other,active (A9.1 OQ-A902-03)",
        },
        "internal_bus_V": bb.INTERNAL_BUS_V,
        "icp_rf_chain": {
            "chain": ["FLIGHT_REPRESENTATIVE_DC_RF_SOURCE (DC input = the only bus-crossing plane)",
                      "directional coupler (forward/reflected on the generator / 50-ohm side)", "50-ohm line",
                      "local adjustable matching network on / adjacent to the ICP module", "ICP antenna"],
            "decisions": ["A92:OQ-A907-11", "A92:rf_measurement_reference", "A93:OQ-RFQ-06"],
            "bus_crossing_plane": "generator_dc_input",
            "flight_source_efficiency": "TBD - requires a measured FLIGHT_REPRESENTATIVE_DC_RF_SOURCE (P_DC,in -> P_RF)",
            "C_e": "C_e = P_RF,delivered / I_e (P1 output; RF-plane quantity, not a bus load)",
            "C_e_DC": ("C_e,DC = P_generator,input / I_e (P1 output with its exact boundary labelled; with the mains "
                       "laboratory generator the boundary is P_mains,in and is GROUND/FACILITY_ONLY, never P_bus)"),
            "ground_facility_only": ["mains-powered laboratory 13.56 MHz generator (GA-02)",
                                     "P_mains,in power analyzer (GA-07)"],
            "P_forward_is_not_P_plasma": True,
        },
        "configurations": per_cfg,
    }


def icp_rf_generator_dc_input(c_e_dc: dict, i_d_max_h1: dict, source_class: str) -> dict:
    """P_DC,in of the ICP RF source at the ICP-45 requirement, from a measured C_e,DC and a REGISTERED I_d,max,H1.

    Fail-closed: a GROUND/FACILITY_ONLY source raises (never P_bus evidence, A9.3 OQ-RFQ-06); a C_e,DC not measured at
    the generator DC input of a flight-representative source raises; a missing or TBD input returns NOT_EVALUATED /
    TBD; synthetic evidence raises. The product is arithmetic on measured inputs, not a prediction."""
    if source_class == "GROUND/FACILITY_ONLY":
        raise MassPowerV2Error("a GROUND/FACILITY_ONLY RF source is never P_bus evidence (A9.3 OQ-RFQ-06)")
    if source_class != "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE":
        raise MassPowerV2Error(f"unknown RF source class {source_class!r}")
    for name, rec in (("c_e_dc", c_e_dc), ("i_d_max_h1", i_d_max_h1)):
        if not isinstance(rec, dict) or "value" not in rec:
            raise MassPowerV2Error(f"{name} must be a record with 'value' (no default)")
        if rec.get("synthetic"):
            raise MassPowerV2Error(f"{name}: synthetic evidence refused")
    if i_d_max_h1["value"] in (None, "TBD") or i_d_max_h1.get("status") != "REGISTERED":
        return {"status": "NOT_EVALUATED", "P_DC_in_W": None,
                "why": "I_d,max,H1 not registered from measured H-1 operation (A9.4 i_d_max_h1)"}
    if c_e_dc["value"] in (None, "TBD"):
        return {"status": "TBD", "P_DC_in_W": None, "why": "C_e,DC not yet measured (P1)"}
    if c_e_dc.get("boundary") != "generator_dc_input" or c_e_dc.get("evidence_class") != "measured":
        raise MassPowerV2Error("C_e,DC must be measured at the flight-representative generator DC input")
    ce, i = c_e_dc["value"], i_d_max_h1["value"]
    for n, v in (("C_e,DC", ce), ("I_d,max,H1", i)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise MassPowerV2Error(f"{n} must be a finite number > 0, got {v!r}")
    return {"status": "COMPUTED_FROM_MEASURED_INPUTS", "P_DC_in_W": r6(ce * i),
            "note": "enters the ledger only as the icp_rf_source load at generator_dc_input with its uncertainty"}


# ======================================================================================================== ASSEMBLY
def statuses(a92: dict, a96: dict) -> dict:
    s = dict(a92["decisions"]["a9_10_statuses"])
    if any(v == "PASS" for v in s.values()):
        raise MassPowerV2Error("an A9.2 status reads PASS")
    return {"a9_2_statuses": s, "a9_6_fixed_statuses": dict(a96["summary"]["fixed_statuses"]),
            "rule": "carried verbatim; this lane never produces PASS for thermal, RF ratings, anode or ICP capacity"}


def open_status(oqs: dict, ids) -> dict:
    rows = {r["id"]: r for r in oqs["rows"]}
    return {i: rows[i]["status"] for i in ids}


def build() -> dict:
    verify_pins()
    m6, a92, a96, oqs = load("M6"), load("A92"), load("A96"), load("OQS3")
    xe2 = import_xe_v2(m6)
    v1 = {i["id"]: i for i in m6["items"]}
    ln = v1_lines(m6)
    ln[C1_LINE] = c1_line(m6)
    f_h = v1["MP-05"]["value"]
    mga = v1["MP-04"]["value"]
    sysm = v1["MP-03"]["value"]
    reserve = v1["MA-RES"]["value"]
    cases = v1["MP-06"]["value"]
    refs = [("INTERNAL_34", v1["MP-02"]["value"][0], False), ("INTERNAL_36", v1["MP-02"]["value"][1], False),
            ("HARD_40_WET", v1["MP-01"]["value"], True)]
    res_top = xe2["residual_by_reading_kg"]["USABLE_RESIDUAL_ON_TOP"]    # imported once (XL-30)
    res_in = xe2["residual_by_reading_kg"]["LOADED"]

    lines_out, rollups = {}, []
    for c in CONFIGS:
        recs = []
        lines_out[c] = []
        for lid in LINES_BY_CONFIG[c]:
            L = ln[lid]
            st = line_state(L["allocation_kg"], L["evidence_floor_kg"], L["floor_is_partial"])
            lines_out[c].append({**L, "state": st, "is_harness": lid == HARNESS_LINE})
            recs.append({"line": lid, "allocation_kg": L["allocation_kg"], "evidence_floor_kg": L["evidence_floor_kg"],
                         "is_harness": lid == HARNESS_LINE})
        for reading in READINGS:
            for basis in BASES:
                d = dry_rollup(recs, reading, basis, reserve, f_h, mga, sysm)
                cells = []
                for xr in XE_CASE_READINGS:
                    for case in cases:
                        for ref_id, ref_kg, strict in refs:
                            w = wet_cell(d, case, xr, res_top[float(case)], ref_kg, strict)
                            w["reference"] = ref_id
                            w["residual_inside_case_kg"] = res_in[float(case)] if xr == "LOADED_XA9Q01" else None
                            hs = xe2["headroom"].get((XE2_SCENARIO[c], XE2_READING[xr], float(case)))
                            if not hs:
                                raise MassPowerV2Error(f"Xe v2 headroom missing for {XE2_SCENARIO[c]} "
                                                       f"{XE2_READING[xr]} {case} kg")
                            w["xe_case_headroom_status"] = (
                                "; ".join(f"{k}: {v}" for k, v in sorted(hs.items())) +
                                f" (Xe accounting v2 scenario {XE2_SCENARIO[c]}, RA-CASE {XE2_READING[xr]}; XL-31)")
                            if any(v == "EXCEEDED_BY_CLOSED_TERMS" for v in hs.values()):
                                w["xe_case_flag"] = ("XE_CASE_BELOW_BOOKED_TERMS: under at least one Xe-accounting "
                                                     "sub-reading this design case is smaller than the Xe terms "
                                                     "already booked for this configuration (Xe accounting v2 "
                                                     "headroom); the wet known part understates the need")
                            else:
                                w["xe_case_flag"] = None
                            cells.append(w)
                rollups.append({"configuration": c, **d, "wet": cells})

    doc = {
        "schema": "mass_power_a9_v2", "id": "fo_a9_6_mass_power_integration_v2",
        "lane": "fo_a9_6_mass_power_integration", "directive": "A9.6 sec. 11 (implementation-first)",
        "title": "A9 mass + power integration v2: BOM per configuration (allocation / evidence floor / CBE / measured), "
                 "dry and wet roll-ups under every open reading, A9 bus-boundary power allocation",
        "status": "DRAFT_IMPLEMENTATION_FIRST_PENDING_CONSOLIDATED_VERIFICATION",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "base_commit": BASE_COMMIT, "generated_by": BUILDER, "companion_document": OUT_MD, "test": TEST,
        "revision_of": {"path": PINS["M6"][0], "sha256": PINS["M6"][1], "md_sha256": PINS["M6_MD"][1],
                        "builder_sha256": PINS["M6_BUILD"][1],
                        "rule": "the A9-06 v1 files are immutable and never edited; v2 is a new file set that reads "
                                "them by pointer"},
        "configurations": {c: ROLE[c] for c in CONFIGS},
        "value_columns": {
            "ALLOCATION": "owner row-54 v0 line budget (evidence class owner-allocation); line level only; never a CBE",
            "EVIDENCE_FLOOR": "analog planning value of other hardware or a Vyovrinda preliminary design point, copied "
                              "by pointer from verified deliverables; not a CBE and not a physical lower bound",
            "CBE": "Vyovrinda current best estimate from a design; none exists yet (all TBD)",
            "MEASURED": "mass of a weighed flight-representative article; none exists yet (all TBD)",
            "rule": "the four columns are never merged: an allocation or floor in the BOM never becomes a CBE",
        },
        "closure_states": list(CLOSURE_STATES), "evidence_classes": list(EVIDENCE_CLASSES),
        "freeze_points": list(FREEZE_POINTS),
        "what_this_is_not": [
            "not a performance prediction (no thrust, discharge current, electron current, efficiency or plasma state)",
            "not an architecture selection: no winner between hall_icp_neutralizer and hall_c1_reference",
            "not a CBE: every line is an owner allocation, an evidence floor or TBD",
            "not a change of any owner allocation and not an answer to any open owner question",
            "not a thermal, RF-rating, anode or ICP-capacity PASS",
            "not a P_bus demonstration: every load is TBD; the gate is NOT_EVALUABLE"],
        "statuses": statuses(a92, a96),
        "pins": [{"key": k, "path": p, "sha256": s, "kind": kd} for k, (p, s, kd) in PINS.items()],
        "never_pinned": NEVER_PINNED,
        "pending_parallel_lanes": {k: pending(k) for k in PENDING_LANES},
        "merged_cross_lane": xlane_report(None),
        "xe_v2_import": {"source": xe2["source"], "pairs": ["XL-30", "XL-31"],
                         "residual_by_reading_kg": {rd: {str(k): v for k, v in sorted(m.items())}
                                                    for rd, m in xe2["residual_by_reading_kg"].items()},
                         "agreement_with_mass_a9_v1": xe2["agreement_with_v1"],
                         "rule": "imported once (row 45): inside the case under LOADED_XA9Q01, on top under "
                                 "USABLE_MQ09; never computed or added a second time; headroom statuses per "
                                 "sub-reading copied, totals with TBD inputs stay REFUSED in the Xe accounting"},
        "p4_density_import": {"source": XLANE_PATHS["P4"], "pair": "XL-26", "records": import_p4_densities()},
        "items": items_table(v1, m6),
        "bom": build_bom(m6),
        "ground_article_only": ground_articles(m6),
        "lines": lines_out,
        "rollup_conventions": {
            "readings": READINGS, "bases": BASES, "xe_case_readings": XE_CASE_READINGS,
            "owner_calls_carried_side_by_side": {
                "MQ-01": "MQ01_MEV_LEVEL vs MQ01_CBE_LEVEL (TBD_OWNER)",
                "XA9Q-01 / MQ-09 / OQ-A910-01": "LOADED_XA9Q01 vs USABLE_MQ09 (TBD_OWNER)",
                "MQ-02": "row-52 margin replaces the reserve (both MQ-01 readings, v1 convention); the additive "
                         "alternative is reported as dry_if_reserve_additive_MQ02_kg (TBD_OWNER)",
                "XA9Q-07": ("Xe hardware and Xe load are booked in hall_icp_neutralizer per row 6 (bounded Xe-capable "
                            "mode), as A9-06 v1 did; XA9Q-07 stays OPEN in the v3 register and is not answered here; "
                            "a NO answer would remove AL-08 and the Xe load from that column")},
            "harness": "row 60: harness = max(1.0 kg AL-09 line, f/(1-f) x other nominal dry), f = 0.05 (v1 "
                       "convention; MQ-06 split question OPEN)",
            "residual": "row 45: imported once from the merged Xe accounting v2 (XV2-IF-01, pair XL-30; "
                        "design_cases.reserve_residual_split, both RA-CASE readings), checked equal to the immutable "
                        "mass_a9_v1 wet_closure.residual; inside the case under LOADED_XA9Q01, on top under "
                        "USABLE_MQ09; never computed here",
            "closure_rule": "CLOSES only when every term is resolved (CBE or measured) and the reference is met; "
                            "DOES_NOT_CLOSE when the booked known part already reaches the reference on this reading; "
                            "otherwise NOT_EVALUABLE",
            "c1_comparability": ("hall_c1_reference has no owner allocation for its C1 line (MPQ-01); on the "
                                 "ALLOCATIONS basis its dry known part omits that line, and on WITH_EVIDENCE_FLOORS "
                                 "the line carries only a partial analog floor (cathode unit 0.2 kg) while the ICP "
                                 "lines AL-05/AL-06 carry 3.5 kg of allocation: the two columns are NOT comparable and "
                                 "no difference between them is a ranking"),
        },
        "rollups": rollups,
        "coil_mass_correction": coil_section(m6, load("H2A9")),
        "power": power_section(),
        "open_register_status": open_status(oqs, ["MQ-01", "MQ-02", "MQ-03", "MQ-04", "MQ-05", "MQ-06", "MQ-07",
                                                  "MQ-08", "MQ-09", "MQ-10", "XA9Q-01", "XA9Q-07", "OQ-A910-01",
                                                  "OQ-A910-03", "OQ-A910-06"]),
        "interface_demands": interface_demands(),
        "owner_answers_applied": owner_answers_applied(),
        "decisions_applied": decisions_applied(),
        "open_owner_questions": open_questions(),
        "historical_reuse": historical_reuse(),
        "m16_impact": m16_impact(),
        "compliance": {
            "no_hall_performance_source": "no Hall transport closure, screening candidate, abep_sim/plasma_devices.py "
                                          "or withdrawn v1.2-v1.6 number is read",
            "no_new_numbers": "every number is owner-given (row / decision), copied by pointer from a pinned verified "
                              "deliverable or module constant, or deterministic arithmetic on those",
            "allocations_unchanged": "no owner allocation is modified; conflicts stay MQ-03..MQ-05, MQ-10",
            "residual_once": "the Xe residual is imported, never computed or added twice",
            "pure": "standard library + abep_sim.bus_boundary_a9 by import; not wired into archengine; no frozen data, "
                    "goldens or existing module touched",
            "no_pass": "no PASS verdict produced; gate and allocation checks NOT_EVALUABLE on TBD loads",
            "no_contact": "no supplier, lab or author contact; no web access used by this lane"},
    }
    return doc


def items_table(v1: dict, m6: dict) -> list:
    out = []
    for iid in ("MA-AL-01", "MA-AL-02", "MA-AL-03", "MA-AL-04", "MA-AL-05", "MA-AL-06", "MA-AL-07", "MA-AL-08",
                "MA-AL-09", "MA-AL-10", "MA-SUM", "MA-RES", "MA-TGT", "MP-01", "MP-02", "MP-03", "MP-04", "MP-05",
                "MP-06", "MP-07", "MP-08", "ME-01", "ME-02", "ME-03", "ME-04", "ME-05", "ME-06", "ME-07"):
        i = v1[iid]
        out.append({"id": iid, "name": i["name"], "value": i["value"], "units": i["units"], "basis": i["basis"],
                    "source": i["source"], "evidence_class": i["evidence_class"], "status": i["status"],
                    "freeze_point": i["freeze_point"], "carried_from": PINS["M6"][0] + " items (by pointer)"})
    bm = PINS["BBMOD"][0]

    def mod(sym):
        return [{"path": bm, "symbol": sym, "sha256": PINS["BBMOD"][1]}]
    new = [
        ("MPV2-P01", "RFP bus-power gate P_bus,1ms,max (strict <)", bb.P_BUS_REQUIREMENT_W, "W", "row 108; A9.1 "
         "OQ-A902-01", row_src(108) + mod("P_BUS_REQUIREMENT_W"), None, "OWNER_GIVEN (RFP as recorded; verify against "
         "the official RFP)", "NOW"),
        ("MPV2-P02", "internal design allocation", bb.DESIGN_ALLOCATION_W, "W", "row 109",
         row_src(109) + mod("DESIGN_ALLOCATION_W"), "owner-allocation", "OWNER_ALLOCATION (not a gate)", "NOW"),
        ("MPV2-P03", "common allocation incl. controls/thermal (upper design allocation)", bb.COMMON_ALLOCATION_W, "W",
         "row 114; A9.1 OQ-A902-02", row_src(114) + mod("COMMON_ALLOCATION_W"), "owner-allocation", "OWNER_ALLOCATION",
         "NOW"),
        ("MPV2-P04", "controls/thermal allowance inside the common allocation", bb.CONTROLS_THERMAL_ALLOWANCE_W, "W",
         "row 114", row_src(114) + mod("CONTROLS_THERMAL_ALLOWANCE_W"), "owner-allocation", "OWNER_ALLOCATION", "NOW"),
        ("MPV2-P05", "Hall + electron-source envelope at P_common = 300 W, P_other = 0",
         r6(bb.DESIGN_ALLOCATION_W - bb.COMMON_ALLOCATION_W), "W", "arithmetic MPV2-P02 - MPV2-P03 (A9.1 OQ-A902-03)",
         [dec_src("A91", "OQ-A902-03")], "owner-allocation",
         "DERIVED (arithmetic on owner allocations; not a sub-allocation)", "NOW"),
        ("MPV2-P06", "regulated internal propulsion bus voltage (breadboard / PPU)", bb.INTERNAL_BUS_V, "V", "row 111",
         row_src(111) + mod("INTERNAL_BUS_V"), None, "OWNER_GIVEN (not an RFP spacecraft interface)", "NOW"),
        ("MPV2-P07", "ICP RF frequency", bb.RF_FREQUENCY_HZ, "Hz", "row 72; A9", row_src(72) + mod("RF_FREQUENCY_HZ"),
         None, "OWNER_GIVEN", "NOW"),
        ("MPV2-P08", "flight RF source DC-input efficiency / C_e,DC", "TBD", "- ; W/A", "A9.3 OQ-RFQ-06",
         [dec_src("A93", "OQ-RFQ-06")], None, "TBD - requires a measured FLIGHT_REPRESENTATIVE_DC_RF_SOURCE and P1 "
         "C_e,DC with its boundary labelled", "after-evidence"),
        ("MPV2-P09", "I_d,max,H1 (ICP-45 requirement)", "TBD", "A", "A9.3 OQ-A907-02; A9.4 i_d_max_h1",
         [dec_src("A93", "OQ-A907-02"), dec_src("A94", "execution_decisions.i_d_max_h1")], None,
         "NOT_EVALUATED - requires registered / measured H-1 operation (never the 8.33 A supply rating)",
         "after-evidence"),
        ("MPV2-P10", "laboratory bench discharge-current ceiling (ground stand rating only)", 8.33, "A",
         "A9.3 OQ-A907-02 (1500 W / 180 V)", [dec_src("A93", "OQ-A907-02")], None,
         "OWNER_GIVEN (ground conductor/sensor/feedthrough sizing; not a flight requirement)", "NOW"),
        ("MPV2-M01", "MC-1 complete-coil copper booked inside the MC-1 floor (H2-1 H21-24)", 1.579, "kg",
         "A9.2 coil_mass_correction (~1.58 kg complete-coil copper)", [dec_src("A92", "coil_mass_correction"),
                                                                     {"path": PINS["M6"][0],
                                                                      "pointer": "/line_checks/3/evidence/constituents/1"}],
         "model-derived", "PRELIMINARY (Vyovrinda design point; evidence floor, not a CBE)", "after-evidence"),
        ("MPV2-M02", "60 W fixed-NI copper sensitivity basis (NOT the MC-1 coil mass; never booked)", 0.136, "kg",
         "A9.2 coil_mass_correction; A9-07 IDA7-01", [dec_src("A92", "coil_mass_correction"),
                                                      {"path": PINS["H2A9"][0],
                                                       "pointer": "/recomputations/lv_coil_copper_delta/value"}],
         "model-derived", "SENSITIVITY_BASIS_ONLY", "after-evidence"),
        ("MPV2-M03", "C1 line (AL-C1) owner allocation", TBD_OWNER, "kg", "row 54 names none", row_src(54), None,
         "TBD_OWNER (MPQ-01)", "LOCK-1"),
    ]
    for (iid, name, val, u, basis, src, ec, st, fp) in new:
        out.append({"id": iid, "name": name, "value": val, "units": u, "basis": basis, "source": src,
                    "evidence_class": ec, "status": st, "freeze_point": fp, "carried_from": None})
    return out


def coil_section(m6: dict, h2a9: dict) -> dict:
    al4 = [x for x in m6["line_checks"] if x["line"] == "AL-04"][0]
    cu = [c for c in al4["evidence"]["constituents"] if "copper" in c["what"]][0]["kg"]
    bases = h2a9["recomputations"]["lv_coil_copper_delta"]["value"]
    s60 = bases["P_mag_basis_60W_H25-08_upper"]["LV-COIL_copper_delta_kg"]
    srp = bases["P_mag_basis_RP1_as_sized"]["LV-COIL_copper_delta_kg"]
    if abs(cu - 1.579) > 1e-9 or abs(s60 - 0.136) > 1e-9:
        raise MassPowerV2Error("coil basis inputs changed; re-derive the coil-mass correction")
    return {"decision": dec_src("A92", "coil_mass_correction"),
            "booked_copper_kg": cu, "booked_in": "AL-04 evidence floor 3.504 kg (MC-1 iron 1.925 + copper 1.579)",
            "complete_coil_copper_estimate_kg": srp,
            "sensitivity_basis_60W_kg": s60,
            "rule": "0.136 kg is the 60 W / fixed-ampere-turn copper sensitivity basis, NOT total MC-1 coil mass; "
                    "~1.58 kg is the complete-coil copper estimate from H2-1 sizing; they are different bases, never "
                    "alternative estimates of the same mass; only clearly defined complete hardware mass is booked",
            "lv_coil_sensitivity": "carried unchanged in mass_a9_v1 lv_coil_sensitivity (not booked; lever adoption "
                                   "owner/LOCK-1)"}


def interface_demands() -> list:
    L = LANE_DIR

    def d(i, frm, to, q, v, u, st, pairs=()):
        xs = [xref(p) for p in pairs]
        if xs:
            u, st = xs[0]["units"], xs[0]["status"]
        return {"id": i, "from": frm, "to": to, "quantity": q, "value": v, "units": u, "status": st, "xref": xs}
    P3, P4, XE, RFQ = (XLANE_PATHS[k] for k in ("P3", "P4", "XE", "RFQ"))
    return [
        d("MPV2-ID-01", P3 + " P3-IF-S08", L, "thermal-hardware mass (radiator / heaters / MLI / heat paths) and any "
          "active-cooling variant from the coupled H-1/ICP thermal model (A9.2 icp_coupled_thermal)", "TBD", None,
          None, ["XL-28"]),
        d("MPV2-ID-02", P3 + " P3-IF-S09", L, "thermal_control slot power (steady / start-up) for the power ledger",
          "TBD", None, None, ["XL-29"]),
        d("MPV2-ID-03", P4 + " ID-07", L, "candidate densities (p4_density_import: PR-001, PR-011, PR-021) for the "
          "mass effect of the anode / collector material candidates and of the anode heat-removal path (MPV2-N03); "
          "part mass needs the geometry", {r: "p4_density_import" for r in P4_DENSITY_IDS}, None, None, ["XL-26"]),
        d("MPV2-ID-04", L, XE + " XV2-IF-13", "one Xe design-case content governing both ledgers (OQ-A910-01) and "
          "hall_c1_reference headroom under the MQ-09 reading; C1 terms booked only in hall_c1_reference; primary "
          "G-REUSE m_Xe,ICP = 0", "TBD", None, None, ["XL-33"]),
        d("MPV2-ID-05", XE + " XV2-IF-02", L, "Xe design-case headroom per configuration under both case readings "
          "(rollups[].wet[].xe_case_headroom_status)", "see rollups", None, None, ["XL-31"]),
        d("MPV2-ID-06", L, RFQ + " IFD-14", "RFQ mass fields: request supplier mass for the FLIGHT_REPRESENTATIVE_DC_RF_"
          "SOURCE, local match, ICP module, isolation hardware; ceilings = owner allocations only (MQ-01 reading "
          "open); no ceiling for GROUND/FACILITY_ONLY items; below-floor ceilings flagged (MQ-03..MQ-05)",
          {"AL-05": 2.0, "AL-06": 1.5}, None, None, ["XL-40"]),
        d("MPV2-ID-07", L, RFQ + " IFD-14", "RFQ power field: DC-input power and efficiency of the flight-"
          "representative RF source at the delivered-power range (no rating before the impedance map)", "TBD", None,
          None, ["XL-41"]),
        d("MPV2-ID-08", XLANE_PATHS["P1"] + " IF-P1-38", L, "C_e and C_e,DC with the boundary labelled; I_e surface; "
          "P_mains,in (P1-M-05) recorded as GROUND/FACILITY_ONLY", "TBD", None, None, ["XL-38"]),
        d("MPV2-ID-09", XLANE_PATHS["P2"] + " IDP2-21", L, "measured P_forward envelope and Z_antenna map -> RF "
          "component ratings -> flight match implementation and its mass / actuator power", "TBD", None, None,
          ["XL-39"]),
        d("MPV2-ID-10", L, "A9-07 docs/hardware/h2_a9_revisions/ (H-1 / MC-1)", "frozen H-1 coil (NI, l_mt, window) "
          "-> MC-1 mass and magnet slot power; H-1 channel / anode / body masses", "TBD", "kg; W", "OPEN"),
        d("MPV2-ID-11", L, pending("RVM"), "mass rows: <40 kg wet = NOT_EVALUATED / INCOMPLETE_EVIDENCE (no CBE); power "
          "rows: <1.5 kW and 1.35 kW = NOT_EVALUATED (all loads TBD)", "see rollups / power", "-", "PROPOSED"),
        d("MPV2-ID-12", L, pending("M16"), "M16 allocation columns and new rows (m16_impact); no row READY/VERIFIED "
          "from this lane", "-", "-", "PROPOSED"),
        d("MPV2-ID-13", "A9-02 " + PINS["BBMOD"][0], L, "slot set, envelopes, gate definition, templates (used by "
          "import)", "-", "-", "USED"),
        d("MPV2-ID-14", L, "owner", "C1 line allocation (MPQ-01) and mapping of the new v2 lines (MPQ-02)", TBD_OWNER,
          "kg", "OPEN"),
        d("MPV2-ID-15", XE + " XV2-IF-01", L, "Xe residual per design case under both readings, imported once "
          "(xe_v2_import.residual_by_reading_kg)", "see xe_v2_import", None, None, ["XL-30"]),
        d("MPV2-ID-16", L, XE + " XV2-IF-03", "stored-Xe hardware masses (tank, regulator / PMU, FCUs, isolation "
          "valves, C1-branch filter / getter) inside the AL-08 owner line allocation", "TBD", None, None, ["XL-32"]),
    ]


def owner_answers_applied() -> list:
    how = {
        5: "40 kg is a wet gate incl. Xe + tank: wet roll-ups add the Xe case (and the imported residual) to dry",
        6: "Xe hardware retained in both configurations (bounded Xe-capable mode); XA9Q-07 stays OPEN",
        43: "reserve belongs to the Xe ledger; case content carried under both readings",
        45: "residual imported once (inside the case or on top per reading), never computed here",
        46: "C1 cathode Xe term only in hall_c1_reference (A9B-C06 as a Xe-accounting wet term)",
        47: "ICP / RF electronics as separate BOM lines",
        48: "2 / 5 / 10 kg design cases evaluated; no load frozen",
        52: "20 % system margin in both MQ-01 readings; 40 kg wet kept hard",
        53: "34 kg and 36 kg internal allocations evaluated",
        54: "row-54 lines as ALLOCATION column only (never CBE); no line changed",
        57: "20 % equipment margin on unselected parts (CBE-level reading; floors in both readings)",
        59: "A9 BOM with ICP, RF source / match / feedthrough, collector / bias; C1 retained as reference / fallback",
        60: "harness 5 % of nominal dry until a routed harness exists",
        62: "ICP telemetry incl. RF forward / reflected power and interlock (A9B-29, MPV2-N02)",
        66: "every legitimate load has a slot (bus_boundary_a9 slots used)",
        70: "ICP body floating; collector bias separate (A9B-17 / A9B-22)",
        72: "13.56 MHz; 0-500 W is a laboratory capability only; lab generator ground-only",
        86: ">= 50 K margin + 20 % heat-load margin drive the thermal hardware (UNRESOLVED)",
        89: "C1 keeper 300-600 V pulsed class in hall_c1_reference supplies",
        108: "< 1.5 kW at the spacecraft-DC boundary incl. start-up (1 ms-window gate)",
        109: "1350 W design allocation; ICP inside it; margin to 1500 W not consumed nominally",
        110: "supply partition = bus slots",
        111: "100 V internal bus; front end configurable (efficiency TBD)",
        112: "start-up templates with one commanded peak per step; C1 heater rule",
        114: "300 W common incl. 50 W controls / thermal",
    }
    a = answers_by_row()
    return [{"row": r, "covers_ids": a[r]["covers_ids"], "answer_sha256": answer_fp(r), "how_applied": h}
            for r, h in how.items()]


def decisions_applied() -> list:
    rows = [
        ("A91", "OQ-A902-01", "1 ms-window gate; peak_sampled protection-only"),
        ("A91", "OQ-A902-02", "common-allocation composition"),
        ("A91", "OQ-A902-03", "no fixed Hall/ICP split; P_ICP,available relation"),
        ("A91", "OQ-A902-04", "no combined flight C1 + ICP; separate columns"),
        ("A91", "OQ-A902-05", "ICP feed flow control variant-only"),
        ("A91", "HIQ-06", "G-REUSE primary, mdot_ICP,dedicated = 0; no ICP gas hardware in the primary BOM"),
        ("A91", "SEQ-heater", "TBD heater never assumed off; no booked power exists -> ledger incomplete"),
        ("A92", "OQ-A907-11", "local adjustable match on / adjacent to the ICP; no long unmatched coax"),
        ("A92", "rf_measurement_reference", "forward/reflected on the generator / 50-ohm side; P_fwd != P_plasma"),
        ("A92", "rf_500W", "0-500 W is a laboratory capability, not a rating"),
        ("A92", "rf_protection", "RF protection electronics line MPV2-N02"),
        ("A92", "icp_matching_strategy", "flight match implementation after the impedance map"),
        ("A92", "anode_316L", "316L REJECTED_AS_CURRENT_BASELINE"),
        ("A92", "anode_approach", "ANODE_BASELINE OPEN; heat-removal path line MPV2-N03"),
        ("A92", "icp_coupled_thermal", "UNRESOLVED; thermal hardware TBD"),
        ("A92", "radiative_view_requirement", "open-frame ICP support line MPV2-N04"),
        ("A92", "coil_mass_correction", "0.136 kg sensitivity basis only; 1.579 kg complete-coil copper booked"),
        ("A92", "a9_10_statuses", "ten statuses carried verbatim; none PASS"),
        ("A93", "OQ-VI-03", "open-tube coaxial first build"),
        ("A93", "OQ-A907-02", "8.33 A stand ceiling ground only; I_d,max,H1 governs"),
        ("A93", "ICPQ-06", "gas isolator only where a line bridges isolated potentials (variant)"),
        ("A93", "OQ-RFQ-06", "lab mains generator GROUND/FACILITY_ONLY; flight DC RF source"),
        ("A93", "OQ-RFQ-10", "dedicated feed controller quote-option only; capped port stays"),
        ("A94", "P1Q-13", "floating anode / metered body ground: ground configuration GA-08"),
        ("A94", "P1Q-14", "ICP isolation class line MPV2-N01"),
        ("A94", "P2Q-05", "photodiode chain ground instrumentation GA-05"),
        ("A94", "execution_decisions.i_d_max_h1", "I_d,max,H1 NOT_EVALUATED until registered"),
        ("A95", "P1Q-15", "capacity-record current closure is a P1 rule; no mass/power value taken from it"),
        ("A95", "P1Q-16", "I_e,cap = I_ON - I_OFF signed; not used for any power value here"),
        ("A96", "sec. 11", "this deliverable (allocation vs CBE vs measured kept distinct)"),
        ("A96", "fixed_statuses", "316L / anode / thermal / RF-rating statuses carried"),
    ]
    return [{"decision_file": PINS[k][0], "sha256": PINS[k][1], "decision": d, "how_applied": h} for k, d, h in rows]


def open_questions() -> list:
    return [
        {"id": "MPQ-01", "question": "Row 54 gives no allocation for the C1 electron-source hardware of the "
                                     "hall_c1_reference flight fallback configuration (cathode unit, shield/mount, "
                                     "filter/getter; supplies and cathode Xe branch possibly inside AL-07/AL-08). Which "
                                     "allocation line and value apply?",
         "proposed": "owner call; admissible options carried: (a) reuse the ICP-only lines AL-05 + AL-06 (3.5 kg) for "
                     "the C1 line in hall_c1_reference; (b) a separate C1 allocation; (c) C1 supplies inside AL-07 and "
                     "the C1 branch inside AL-08 with only the cathode module on a new line. Until then the C1 column "
                     "reports a known part only (not comparable)",
         "needed_by": "LOCK-1", "status": "OPEN", "freeze_point": "LOCK-1"},
        {"id": "MPQ-02", "question": "Map the A9.2-A9.6 lines that neither row 54 nor MQ-07 names: ICP isolation "
                                     "hardware (MPV2-N01), RF protection/sensing electronics (MPV2-N02), anode heat-"
                                     "removal hardware (MPV2-N03), ICP open-frame support / spacer (MPV2-N04)?",
         "proposed": "PROPOSED_MAPPING as booked (AL-05, AL-06, AL-04, AL-10); owner call together with MQ-07",
         "needed_by": "LOCK-1", "status": "OPEN", "freeze_point": "LOCK-1"},
    ]


def historical_reuse() -> dict:
    return {"artifacts": [{"key": k, "path": PINS[k][0], "sha256": PINS[k][1]}
                          for k in ("M6", "M6_MD", "M6_BUILD", "XEA9", "BBDOC", "H2A9")],
            "reused": "mass_a9_v1: owner allocation items, evidence floors and their constituents, BOM lines and ids, "
                      "harness convention, reading definitions R0/R1/R2 (+E), imported residual, LV-COIL sensitivity; "
                      "A9 Xe ledger: design-case headroom status (XA9Q-01 reading); bus_power_boundary_a9 module: "
                      "slots, envelopes, gate, templates, ledger/check functions",
            "not_reused": "no mass_a9_v1 closure state is copied as a result (recomputed); R3 partial reading not "
                          "carried; no historical pre-ionizer item returns to the A9 BOM"}


def m16_impact() -> list:
    rows = [
        (6, "xe_tank", "Xe hardware in both configurations (row 6); XA9Q-07 OPEN"),
        (8, "xe_metering", "C1 cathode branch only in hall_c1_reference (inside the AL-08 floor)"),
        (9, "hall_chamber", "anode material OPEN, 316L rejected as baseline; heat-removal line MPV2-N03"),
        (10, "magnetic_circuit", "coil-mass correction applied (1.579 kg booked, 0.136 kg sensitivity only)"),
        (11, "cathode", "C1 line AL-C1 without owner allocation (MPQ-01); hall_c1_reference column only"),
        (12, "ppu", "flight RF source = FLIGHT_REPRESENTATIVE_DC_RF_SOURCE; RF protection line; collector bias rating "
                    "TBD (I_d,max,H1 NOT_EVALUATED)"),
        (13, "thermal_control", "UNRESOLVED (anode, coupled ICP); active cooling variant-only"),
        (15, "sensors_diagnostics", "RF fwd/refl telemetry; photodiode ground-only"),
        (16, "mechanical_structural", "ICP open-frame support / spacer line MPV2-N04"),
    ]
    return [{"m16_row": r, "key": k, "how_touched": h, "state_change": "none (refresh by " + pending("M16") + ")"}
            for r, k, h in rows]


# ======================================================================================================== MARKDOWN
def _v(x):
    if x is None:
        return "TBD"
    if isinstance(x, float):
        return f"{x:g}"
    if isinstance(x, list):
        return "[" + ", ".join(_v(y) for y in x) + "]"
    if isinstance(x, dict):
        return ", ".join(f"{k}: {_v(v)}" for k, v in x.items())
    return str(x)


def render_md(doc: dict) -> str:
    o = []
    a = o.append
    a("# A9 mass + power integration v2 (A9.6 sec. 11)")
    a("")
    a(f"Generated by `{doc['generated_by']}` from `{OUT_JSON}` (do not edit by hand; `--check` verifies). Status "
      f"`{doc['status']}`; A9 status `{doc['a9_status']}`. Base commit `{doc['base_commit']}`. Revision of "
      f"`{doc['revision_of']['path']}` (sha256 `{doc['revision_of']['sha256']}`, immutable, never edited).")
    a("")
    a("**What this is not:** " + "; ".join(doc["what_this_is_not"]) + ".")
    a("")
    a("## Configurations and value columns")
    a("")
    for c, r in doc["configurations"].items():
        a(f"* `{c}`: {r}")
    a("")
    for k, v in doc["value_columns"].items():
        a(f"* **{k}**: {v}")
    a("")
    a("## Binding statuses (never PASS)")
    a("")
    a("| status | value |")
    a("|---|---|")
    for k, v in doc["statuses"]["a9_2_statuses"].items():
        a(f"| {k} | `{v}` |")
    for k, v in doc["statuses"]["a9_6_fixed_statuses"].items():
        a(f"| {k} | `{v}` |")
    a("")
    a("## Pinned inputs")
    a("")
    a("| key | path | sha256 | kind |")
    a("|---|---|---|---|")
    for p in doc["pins"]:
        a(f"| {p['key']} | `{p['path']}` | `{p['sha256']}` | {p['kind']} |")
    a("")
    a("Never pinned (mutable governance): " + ", ".join(f"`{x}`" for x in doc["never_pinned"]) + ".")
    a("")
    a("Lanes not merged in this base: " + "; ".join(doc["pending_parallel_lanes"].values()) + ".")
    a("")
    a("### Merged cross-lane references")
    a("")
    a(doc["merged_cross_lane"]["rule"])
    a("")
    a("| package | path | pairs | ids cited | check |")
    a("|---|---|---|---|---|")
    for k, v in doc["merged_cross_lane"]["packages"].items():
        a(f"| {k} | `{v['path']}` | {', '.join(v['pairs']) or '-'} | {', '.join(v['ids_cited']) or '-'} | {v['check']} |")
    a("")
    xi = doc["xe_v2_import"]
    a(f"Xe v2 import (`{xi['source']}`, {', '.join(xi['pairs'])}): residual by reading (kg) " +
      "; ".join(f"{rd}: " + ", ".join(f"{k} kg -> {v}" for k, v in m.items()) for rd, m in
                xi["residual_by_reading_kg"].items()) + f". {xi['rule']}.")
    a("")
    pi = doc["p4_density_import"]
    a(f"P4 density import (`{pi['source']}`, {pi['pair']}): " + "; ".join(
        f"{r['id']} {r['candidate']} ({r['material']}) {r['density_kg_m3']} kg/m3 [{r['quantity_type']}, "
        f"{r['source_id']}]" for r in pi["records"]) + ". Informational only; never a CBE.")
    a("")
    a("## (a) Items")
    a("")
    a("| id | name | value | units | basis | evidence class | status | freeze |")
    a("|---|---|---|---|---|---|---|---|")
    for i in doc["items"]:
        a(f"| {i['id']} | {i['name']} | {_v(i['value'])} | {i['units']} | {i['basis']} | {i['evidence_class'] or '-'} "
          f"| {i['status']} | {i['freeze_point']} |")
    a("")
    a("## BOM v2 per configuration")
    a("")
    a("ALLOCATION is line-level (see Lines); EVIDENCE_FLOOR is an analog or preliminary-design value (not a CBE); CBE and "
      "MEASURED are TBD everywhere.")
    a("")
    a("| id | item | ICP | C1 | line | mapping | EVIDENCE_FLOOR | CBE | MEASURED | v2 propagation |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for b in doc["bom"]:
        f = b["columns"]["EVIDENCE_FLOOR"]
        fs = "-" if f is None else f"{_v(f['value'])} {f['units']} ({f['evidence_class']})"
        a(f"| {b['id']} | {b['name']} | {b['configurations']['hall_icp_neutralizer']} | "
          f"{b['configurations']['hall_c1_reference']} | {b['allocation_line'] or '-'} | {b['allocation_mapping'] or '-'}"
          f" | {fs} | TBD: {b['columns']['CBE']['status']} | TBD | {b['v2_propagation'] or '-'} |")
    a("")
    a("### Ground-article-only (never flight mass, never P_bus)")
    a("")
    for g in doc["ground_article_only"]:
        a(f"* **{g['id']}** {g['item']}: {g['rule']}" + (f" ({g['v2_note']})" if g.get("v2_note") else ""))
    a("")
    a("## Lines (ALLOCATION vs EVIDENCE_FLOOR)")
    a("")
    for c, ls in doc["lines"].items():
        a(f"### `{c}`")
        a("")
        a("| line | name | ALLOCATION (kg) | EVIDENCE_FLOOR (kg) | partial | state |")
        a("|---|---|---|---|---|---|")
        for L in ls:
            al = _v(L["allocation_kg"]) if L["allocation_kg"] is not None else TBD_OWNER
            a(f"| {L['line']} | {L['owner_name']} | {al} | {_v(L['evidence_floor_kg'])} | {L['floor_is_partial']} | "
              f"**{L['state']}** |")
        a("")
    rc = doc["rollup_conventions"]
    a("## Dry and wet roll-ups (all readings side by side; none chosen)")
    a("")
    for k, v in rc["readings"].items():
        a(f"* **{k}**: {v}")
    for k, v in rc["bases"].items():
        a(f"* basis **{k}**: {v}")
    for k, v in rc["xe_case_readings"].items():
        a(f"* Xe case **{k}**: {v}")
    for k, v in rc["owner_calls_carried_side_by_side"].items():
        a(f"* owner call {k}: {v}")
    a(f"* harness: {rc['harness']}")
    a(f"* residual: {rc['residual']}")
    a(f"* closure: {rc['closure_rule']}")
    a(f"* comparability: {rc['c1_comparability']}")
    a("")
    a("### Dry")
    a("")
    a("| configuration | reading | basis | nonharness nominal | harness | margin | dry known (kg) | + MQ-02 additive | "
      "every line valued? |")
    a("|---|---|---|---|---|---|---|---|---|")
    for r in doc["rollups"]:
        a(f"| {r['configuration']} | {r['reading']} | {r['basis']} | {_v(r['nonharness_nominal_kg'])} | "
          f"{_v(r['harness_kg'])} | {_v(r['system_margin_kg'])} | {_v(r['dry_known_kg'])} | "
          f"{_v(r.get('dry_if_reserve_additive_MQ02_kg'))} | {'yes' if r['every_line_has_a_value'] else 'no (known part only)'} |")
    a("")
    a("### Wet (state vs 34 / 36 kg internal, < 40 kg hard)")
    a("")
    a("| configuration | reading | basis | Xe reading | case (kg) | wet known (kg) | 34 | 36 | 40 | Xe case headroom |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for r in doc["rollups"]:
        by = {}
        for w in r["wet"]:
            by.setdefault((w["xe_case_reading"], w["xe_case_kg"]), {})[w["reference"]] = w
        for (xr, case), ws in by.items():
            w0 = ws["HARD_40_WET"]
            a(f"| {r['configuration']} | {r['reading']} | {r['basis']} | {xr} | {_v(case)} | {_v(w0['wet_known_kg'])} | "
              f"{ws['INTERNAL_34']['state']} | {ws['INTERNAL_36']['state']} | {w0['state']} | "
              f"{w0['xe_case_headroom_status']}" + (" **XE_CASE_BELOW_BOOKED_TERMS**" if w0["xe_case_flag"] else "")
              + " |")
    a("")
    cm = doc["coil_mass_correction"]
    a("## Coil-mass correction (A9.2)")
    a("")
    a(f"Booked copper {cm['booked_copper_kg']} kg in {cm['booked_in']}; complete-coil estimate "
      f"{cm['complete_coil_copper_estimate_kg']} kg; sensitivity basis {cm['sensitivity_basis_60W_kg']} kg. "
      f"{cm['rule']}. {cm['lv_coil_sensitivity']}.")
    a("")
    p = doc["power"]
    a("## Power integration (bus_power_boundary_a9_v1, import only)")
    a("")
    g = p["gate"]
    a(f"Gate: {g['quantity']} < {g['limit_W']:g} W ({g['decision']}); window {g['window_s']:g} s, >= "
      f"{g['min_bandwidth_Hz']:g} Hz, >= {g['min_sample_rate_Sa_s']:g} Sa/s; applies to steady and start-up. "
      f"PASS requires: {g['pass_requires']}.")
    a("")
    a("| allocation | value (W) | kind |")
    a("|---|---|---|")
    for k, v in p["allocations"].items():
        if isinstance(v, dict):
            a(f"| {k} | {_v(v['value'])} | {v['kind']} |")
    a("")
    a(f"ICP relation: {p['allocations']['icp_relation']}. Internal bus {p['internal_bus_V']:g} V.")
    a("")
    ch = p["icp_rf_chain"]
    a("ICP RF chain: " + " -> ".join(ch["chain"]) + f". Bus-crossing plane `{ch['bus_crossing_plane']}`. "
      f"{ch['C_e']}; {ch['C_e_DC']}. Flight source efficiency: {ch['flight_source_efficiency']}. GROUND/FACILITY_ONLY: "
      + "; ".join(ch["ground_facility_only"]) + ".")
    a("")
    for c, pc in p["configurations"].items():
        a(f"### `{c}`")
        a("")
        a("| slot | envelope | ALLOCATION (W) | CBE | MEASURED | first ON | peak event | status |")
        a("|---|---|---|---|---|---|---|---|")
        for s in pc["slots"]:
            a(f"| {s['slot']} | {s['envelope']} | {_v(s['ALLOCATION_W']) if s['ALLOCATION_W'] is not None else 'none'}"
              f" | TBD | TBD | {s['first_on_step'] or '-'} | {s['peak_class_event'] or '-'} | {s['status']} |")
        a("")
        st = pc["phases"]["steady"]
        a(f"* steady: ledger `{st['ledger_status']}`, P_bus {_v(st['P_bus_W'])}, lower bound "
          f"{_v(st['P_bus_lower_bound_W'])} W, {st['tbd_count']} TBD; 1350 W `{st['design_allocation_1350W']}`, "
          f"1300 W context `{st['a5_1300W_context']}`, 300 W `{st['common_300W']}`, 50 W "
          f"`{st['controls_thermal_50W']}`" + (f"; ICP available `{st['icp_available_check']['verdict']}`"
                                              if st["icp_available_check"] else ""))
        su = pc["phases"]["startup"]
        a(f"* start-up ({su['template']}): sequence `{su['sequence_status']}`, violations {len(su['violations'])}, "
          f"not-evaluable rules {su['not_evaluable_rules']}; steps: " +
          "; ".join(f"{s['step_id']} {s['event'] or '-'} `{s['ledger_status']}`" for s in su["steps"]))
        a(f"* peak: {pc['phases']['peak']['rule']}; values {pc['phases']['peak']['values']}")
        a(f"* RFP 1 ms gate verdict: **{pc['rfp_gate_1ms']['verdict']}**")
        a("")
    a("## Open-register status of the carried owner calls (v3 snapshot)")
    a("")
    a(", ".join(f"{k}: {v}" for k, v in doc["open_register_status"].items()))
    a("")
    a("## (b) Interface demands")
    a("")
    a("| id | from | to | quantity | value | units | status | pairs |")
    a("|---|---|---|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        prs = ", ".join(x["pair"] + " -> " + x["counterpart"] for x in d["xref"]) or "-"
        a(f"| {d['id']} | {d['from']} | {d['to']} | {d['quantity']} | {_v(d['value'])} | {d['units']} | {d['status']} "
          f"| {prs} |")
    a("")
    a("## (c) Owner answers and decisions applied")
    a("")
    a("| row | covers | answer sha256 | how applied |")
    a("|---|---|---|---|")
    for x in doc["owner_answers_applied"]:
        a(f"| {x['row']} | {', '.join(x['covers_ids'])} | `{x['answer_sha256'][:16]}` | {x['how_applied']} |")
    a("")
    a("| decision file | decision | how applied |")
    a("|---|---|---|")
    for x in doc["decisions_applied"]:
        a(f"| `{x['decision_file']}` | {x['decision']} | {x['how_applied']} |")
    a("")
    a("## (d) Open owner questions (new)")
    a("")
    for q in doc["open_owner_questions"]:
        a(f"* **{q['id']}** ({q['status']}, needed by {q['needed_by']}) {q['question']} *Proposed:* {q['proposed']}")
    a("")
    a("## (e) Historical reuse")
    a("")
    for x in doc["historical_reuse"]["artifacts"]:
        a(f"* `{x['path']}` sha256 `{x['sha256']}` (read only)")
    a("")
    a(f"Reused: {doc['historical_reuse']['reused']}. Not reused: {doc['historical_reuse']['not_reused']}.")
    a("")
    a("## (f) M16 impact")
    a("")
    a("| M16 row | key | how touched | state change |")
    a("|---|---|---|---|")
    for m in doc["m16_impact"]:
        a(f"| {m['m16_row']} | {m['key']} | {m['how_touched']} | {m['state_change']} |")
    a("")
    a("## Compliance")
    a("")
    for k, v in doc["compliance"].items():
        a(f"* {k}: {v}")
    a("")
    return "\n".join(o)


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed outputs differ from a fresh build")
    args = ap.parse_args(argv)
    doc = build()
    js, md = dumps(doc), render_md(doc)
    pj, pm = REPO / OUT_JSON, REPO / OUT_MD
    if args.check:
        ok = pj.is_file() and pm.is_file() and pj.read_text(encoding="utf-8") == js and \
            pm.read_text(encoding="utf-8") == md
        probs = xlane_check(json.loads(js))
        if probs:
            print("CROSS-LANE REFERENCES BROKEN:", "; ".join(probs))
            return 1
        print("OK" if ok else "DIFFERS: rebuild with build_mass_power_a9_v2.py")
        return 0 if ok else 1
    pj.parent.mkdir(parents=True, exist_ok=True)
    pj.write_text(js, encoding="utf-8")
    pm.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON} and {OUT_MD}")
    probs = xlane_check(json.loads(js))
    if probs:
        print("CROSS-LANE REFERENCES BROKEN (rebuild the counterpart, then this package):", "; ".join(probs))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
