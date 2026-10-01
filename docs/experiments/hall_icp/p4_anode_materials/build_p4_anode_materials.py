#!/usr/bin/env python3
"""P4 ANODE / COLLECTOR MATERIALS framework (follow-on fo_a9_6_p4_anode_materials, trigger T_A9_6_P4_ANODE_MATERIALS;
owner directive A9.6 sec. 10; owner A9.2 sec. 3-4; owner rows 86, 87, 106, 132, 134; A9.1 A9-03-collector).

Deterministic, standard library only, no Julia, no network, well under a second.

What it does
  * verifies the sha256 of every pinned immutable input and refuses to run on any mismatch (no fallback, CLAUDE.md
    rule 3);
  * copies owner-answer texts, A9.2 / A9.6 fixed statuses, R8 evidence rows and source entries, Takahashi analog rows
    (TK-xx), AO-register ids, M16 v3 rows and the H2 A9 anode sensitivity number FROM the pinned inputs (never typed)
    and fails if any cited id is missing;
  * carries the bulk property values this lane extracted from three open manufacturer datasheets (URL, access date,
    PDF sha256, page, table, verbatim row); every value is checked against its verbatim row token before use;
  * runs the pure fail-closed screening (p4_screening.py): hard gates are applied only when BOTH the requirement and
    the property are evidenced, otherwise INCOMPLETE_EVIDENCE; no weighted scalar; no selection; final material OPEN;
  * writes p4_anode_materials_v1.json and P4_ANODE_MATERIALS.md (generated from the JSON).

A9.16 step 1 (2026-10-01) applies the owner decisions A9.12 P4-OQ-01..05 (S5.10..S5.14) and A9.13 F2-OQ-04 (S6.6,
APP-FILTER) as fail-closed rules (p4_a9_16_rules.py, a9_16_application.py); A9.15 reviewed (no Xe contingency text).

What it is not: a material selection, a thermal result, an anode or collector temperature, a life prediction, a PASS
of any kind, or a procurement. Not wired into archengine (goldens do not move).

    python docs/experiments/hall_icp/p4_anode_materials/build_p4_anode_materials.py          # (re)write outputs
    python docs/experiments/hall_icp/p4_anode_materials/build_p4_anode_materials.py --check  # exit 1 unless reproduced
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LANE_REL = "docs/experiments/hall_icp/p4_anode_materials"
SCRIPT_REL = f"{LANE_REL}/build_p4_anode_materials.py"
SCREEN_REL = f"{LANE_REL}/p4_screening.py"
JSON_NAME = "p4_anode_materials_v1.json"
MD_NAME = "P4_ANODE_MATERIALS.md"
TEST_REL = "tests/test_p4_anode_materials.py"
BASE_COMMIT = "c33b22c78b14cd4d6a51ed9bd5de4e046bc98cae"
DATE = "2026-09-30"
LANE = "fo_a9_6_p4_anode_materials"
TRIGGER = "T_A9_6_P4_ANODE_MATERIALS"
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
QUANTITY_TYPES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                  "owner-allocation", "owner-stated", "published analog", "qualitative")
ITEM_STATUSES = ("OWNER_GIVEN", "TBD", "TBD_OWNER", "TBD_AFTER_EVIDENCE", "PENDING", "REJECTED_AS_CURRENT_BASELINE",
                 "OPEN", "UNRESOLVED", "ALLOWED_ENGINEERING_ONLY", "CONTEXT_NOT_ADMISSIBLE")
# merged A9.6 packages (cross-lane integration; ids checked at build time by xlane_check, never sha-pinned)
P3_REF = ("the merged P3 coupled-thermal framework docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json "
          "(supply P3-IF-S07; its inputs are TBD and ANODE_THERMAL_CLOSURE / ICP_COUPLED_THERMAL stay UNRESOLVED)")
P3_TBD = "TBD_AFTER_EVIDENCE - requires the coupled solution of " + P3_REF
MASS_REF = ("the merged mass / power v2 docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json (owner line allocations "
            "AL-04 anode, AL-05 ICP module; interface MPV2-ID-03)")
RFQ_REF = "the merged RFQ v2 docs/procurement/rfq_a9_v2/rfq_a9_v2.json (RFQ2-MECH ME-L03, ME-L04, option ME-O01)"
P1_REF = ("the merged P1 bench docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json (P1-M-10, P1-M-11, "
          "P1-M-27; conditional P1-M-30)")

_spec = importlib.util.spec_from_file_location("p4_screening", str(HERE / "p4_screening.py"))
SCR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SCR)


def _load_local(name, fname):
    sp = importlib.util.spec_from_file_location(name, str(HERE / fname))
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sp.loader.exec_module(m)
    return m


RULES = _load_local("p4_a9_16_rules", "p4_a9_16_rules.py")
APP = _load_local("p4_a9_16_application", "a9_16_application.py")
A916_DATE = "2026-10-01"

# ------------------------------------------------------------------------------------------------ pinned inputs
PINS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "147 owner answers (machine-readable)"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "owner decisions A9.1"),
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03", "owner decisions A9.2"),
    "A92_MD": ("docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md",
               "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9", "owner decisions A9.2 (verbatim)"),
    "A96": ("docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json",
            "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327", "owner directive A9.6"),
    "A96_MD": ("docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md",
               "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634", "owner directive A9.6 (verbatim)"),
    "OQ3": ("docs/budgets/owner_decisions/owner_questions_state_v3.json",
            "1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2", "owner question state v3"),
    "R8": ("docs/procurement/web_track_v1/threads/R8_anode_oxygen.json",
           "31131ed6409a4d0a4c8b5935387d9c399767fb5507d25f21c0afa753f3d9e39c", "web track R8 anode materials in oxygen"),
    "H2A9": ("docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json",
             "b428565299c1c41487d9ffa50c174986d2d52c544539f89ca21b7bdbc2ae44fa", "H2 A9 revisions (A9H-ANODE-01/02)"),
    "ICPEV": ("docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
              "092e4ca8e1827dd2e9558058a204f46510f2633316ce188e7126b697ec6d0b53", "ICP neutralizer analog evidence"),
    "ICD": ("docs/interfaces/icp_neutralizer/ICP_NEUTRALIZER_ICD.md",
            "d346bcc5a5edc4a4dfa289010c8e48371477a0f3548a5e9dcf8886b6f55dbe77", "ICP neutralizer ICD (ICP-21)"),
    "AOL5": ("docs/experiments/lifetime_ao/ao_lifetime_register_v5.json",
             "fea8aa05bd561d5ea559b934803d472f1fb1ed1013bfa925a5afb6c68a33e637", "AO / lifetime register v5"),
    "M16V3": ("docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json",
              "636cbd3318831f6f56e9833813c4d8c259aef7db3de1c6e503cccce14dade7e2", "M16 subsystem maturity v3"),
    "EVID": ("docs/EVIDENCE.md", "a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61",
             "evidence rules (CLAUDE.md rule 10)"),
}
PINS.update(APP.decision_pins())  # A9.16 step 1: A9.12, A9.13, A9.15 (json + verbatim md)
NEVER_PINNED = ("docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                "docs/orchestration/fired_triggers.jsonl", "docs/orchestration/trigger_ledger_v2.jsonl",
                "docs/orchestration/runtime_state.json")
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
XLANE_SELF = 'P4'
XLANE_BUILD_ORDER = ["P4", "XE", "P1", "P2", "P3", "MP", "RFQ"]
XLANE_BUILD_ORDER_RULE = ("values flow only P4 -> MP (candidate densities) and XE -> MP (Xe residual and headroom, "
                          "both readings), and P1 / P2 -> RFQ (ids, item text and statuses of the instrument "
                          "coverage); every other cross-lane reference is an id checked at build time. Rebuild in "
                          "the order P4, XE, P1, P2, P3, MP, RFQ; a second pass of any package is a no-op")
XL_PAIRS = {  # pair: (counterpart package, counterpart id, quantity, units, status) - identical text on both sides
    'XL-23': (
        'P3',
        'P3-IF-N05',
        ('per-candidate thermal conductivity and density with provenance (P4 property_records), validated '
         'continuous-use limits (CR-01) and emittances -> P3-M-04, P3-R-01, P3-R-04'),
        'W/(m*K); kg/m3; K; -',
        ('DEFINED (k and density records); T_validated,continuous and emittance TBD_AFTER_EVIDENCE; '
         'FINAL_ANODE_MATERIAL OPEN'),
    ),
    'XL-24': (
        'P3',
        'P3-IF-S07',
        ('T_operating of anode and collector (worst case, coupled; 20 % heat-load margin, row 86), heat flux, '
         'gradients -> P4 IT-09, IT-11'),
        'K; W/m2; K/m',
        'TBD_AFTER_EVIDENCE (ANODE_THERMAL_CLOSURE and ICP_COUPLED_THERMAL UNRESOLVED; no PASS)',
    ),
    'XL-25': (
        'P1',
        'IF-P1-36',
        ('measured collector bias and current (P1-M-10, P1-M-11, P1-M-27) and the conditional sheath-edge plasma '
         'potential (P1-M-30) for the collector ion energy (P4 IT-19, CR-04)'),
        'V; A',
        'TBD_AFTER_EVIDENCE (owning stages P1-S4..S7; sheath energy additionally TBD_OWNER P3Q-01)',
    ),
    'XL-26': (
        'MP',
        'MPV2-ID-03',
        ('candidate densities PR-001, PR-011, PR-021 (P4 property_records) imported by mass / power; part mass = '
         'density x CAD volume'),
        'kg/m3; kg',
        'IMPORTED (densities); part mass TBD - requires the anode / collector geometry; FINAL_ANODE_MATERIAL OPEN',
    ),
    'XL-27': (
        'RFQ',
        'IFD-17',
        ('collector / electrode candidate material lots with heat / lot certificates, coatings, AO-source access; no '
         'anode RFQ while FINAL_ANODE_MATERIAL is OPEN (NIR-03)'),
        '-',
        ('DEFINED (RFQ2-MECH ME-L03, ME-L04, option ME-O01; coupon shortlist TBD_OWNER P4 IT-17; AO-source hardware '
         'NOT_IN_THIS_REVISION NIR-05)'),
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
    "P1": ["P1-M-10", "P1-M-11", "P1-M-27", "P1-M-30"],
    "P3": ["P3-M-04", "P3-R-01", "P3-R-04", "heat_terms"],
    "MP": ["AL-04", "AL-05"],
    "RFQ": ["ME-L03", "ME-L04", "ME-O01", "NIR-03", "NIR-05"],
}


class BuildError(RuntimeError):
    pass


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_pins():
    data = {}
    for key, (rel, sha, _role) in PINS.items():
        p = REPO / rel
        if not p.exists():
            raise BuildError(f"pinned input missing: {rel}")
        got = sha256_file(p)
        if got != sha:
            raise BuildError(f"pinned input changed: {rel} sha256 {got} != {sha}")
        data[key] = json.loads(p.read_text(encoding="utf-8")) if rel.endswith(".json") else p.read_text(
            encoding="utf-8")
    return data


def find_by_id(obj, ident, key="id"):
    """Depth-first search for the dict whose `key` equals ident (first hit)."""
    if isinstance(obj, dict):
        if obj.get(key) == ident:
            return obj
        for v in obj.values():
            r = find_by_id(v, ident, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_by_id(v, ident, key)
            if r is not None:
                return r
    return None


# ------------------------------------------------------------------------------------------------ new sources (this lane)
ACCESS = "2026-09-30"
NEW_SOURCES = [
    {"id": "CLF_316", "cite": "Cleveland-Cliffs, '316/316L Stainless Steel' product data bulletin "
                              "(file CLF_ProductData_316-316LSS_052021.pdf)",
     "url": "https://d1io3yog0oux5.cloudfront.net/_55df71d7861786b4e18f65d183a5ec8d/clevelandcliffs/db/1190/10513/file/"
            "CLF_ProductData_316-316LSS_052021.pdf",
     "accessed": ACCESS, "access_level": "open manufacturer datasheet (full PDF read)",
     "pdf_sha256": "2234883fc720073bfdd899671b086e87b2b64aea4254287b7d3080f3c6430333",
     "extraction": "pdftotext -layout; whitespace collapsed in the verbatim rows below",
     "evidence_level": "L2 manufacturer datasheet (typical values, test procedure unpublished)",
     "scope_note": "values are stated for Types 316 and 316L together"},
    {"id": "SMC_IN600", "cite": "Special Metals Corporation, 'INCONEL alloy 600', Publication Number SMC-027 (Sept 08)",
     "url": "https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-600.pdf",
     "accessed": ACCESS, "access_level": "open manufacturer technical bulletin (full PDF read)",
     "pdf_sha256": "89a3ba65b26b817dfc8a92875a4848af73ccecc31b98c0ca15140cea7fe8fde8",
     "extraction": "pdftotext -layout; whitespace collapsed in the verbatim rows below",
     "evidence_level": "L2 manufacturer datasheet ('typical but ... not suitable for specification use', p.1)",
     "scope_note": "same bulletin as R8 SMC_IN600 (R8 read it 2026-09-27 for oxidation Fig. 11 only)"},
    {"id": "SMC_IN601", "cite": "Special Metals Corporation, 'INCONEL alloy 601', Publication Number SMC-028 (Feb 05)",
     "url": "https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-601.pdf",
     "accessed": ACCESS, "access_level": "open manufacturer technical bulletin (full PDF read)",
     "pdf_sha256": "261c20c247910b729bb4a0030106ed007f055a5bb42e30c4572c767dbab24152",
     "extraction": "pdftotext -layout; whitespace collapsed in the verbatim rows below",
     "evidence_level": "L2 manufacturer datasheet (annealed material, p.1)",
     "scope_note": "same bulletin as R8 SMC_IN601 (R8 read it 2026-09-27 for oxidation text only); thermal "
                   "conductivity values are 'calculated from measurements of electrical resistivity' (p.1 text; Table 3 "
                   "footnote a)"},
    {"id": "NIFS_DATA_23", "cite": "Yamamura Y., Tawara H., 'Energy Dependence of Ion-Induced Sputtering Yields from "
                                   "Monoatomic Solids at Normal Incidence', NIFS-DATA-23, National Institute for Fusion "
                                   "Science, Nagoya, Mar. 1995",
     "url": "https://www.nifs.ac.jp/report/NIFS-DATA-023.pdf",
     "accessed": ACCESS, "access_level": "open report (scanned PDF, 114 pages, no text layer; title page and "
                                         "abstract page read as images)",
     "pdf_sha256": "bc3c8d1aa2c5a238fa346484ccf93cf0e494a08aa1e956ab141a0ed130979ef7",
     "extraction": "NONE - no value extracted; yields are presented graphically for monoatomic targets only",
     "evidence_level": "compilation of experimental data + ACAT Monte Carlo + empirical fit (per its abstract)",
     "scope_note": "LOCATED ONLY: candidate open source for elemental targets (not alloys, not coatings); a "
                   "digitization lane would be needed before any sputter-yield value enters this framework"},
]

# ------------------------------------------------------------------------------------------------ candidates
# origin: R8 coupon proposal id / R8 candidate-matrix row / GABRIEL1993 naming (via R8). Nothing here is typed from
# memory about properties; property data live in PROPERTY_RECORDS / EVIDENCE_LINKS only.
CANDIDATES = [
    ("CAND-01", "Austenitic stainless 316L", "austenitic stainless", "R8-C01", "Austenitic stainless 316L"),
    ("CAND-02A", "INCONEL alloy 600 (chromia-forming Ni alloy)", "chromia-forming Ni alloy", "R8-C02",
     "Chromia-forming Ni superalloys (Inconel 600/625/X-750, Haynes 230, Hastelloy)"),
    ("CAND-02B", "INCONEL alloy 625 (chromia-forming Ni alloy)", "chromia-forming Ni alloy", "R8-C02",
     "Chromia-forming Ni superalloys (Inconel 600/625/X-750, Haynes 230, Hastelloy)"),
    ("CAND-02C", "Haynes 230 (chromia-forming Ni alloy)", "chromia-forming Ni alloy", "R8-C02",
     "Chromia-forming Ni superalloys (Inconel 600/625/X-750, Haynes 230, Hastelloy)"),
    ("CAND-02D", "INCONEL alloy X-750 (named by GABRIEL1993)", "chromia-forming Ni alloy", None,
     "Chromia-forming Ni superalloys (Inconel 600/625/X-750, Haynes 230, Hastelloy)"),
    ("CAND-02E", "Hastelloy (grade not stated by GABRIEL1993)", "chromia-forming Ni alloy", None,
     "Chromia-forming Ni superalloys (Inconel 600/625/X-750, Haynes 230, Hastelloy)"),
    ("CAND-03A", "INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy)", "alumina-forming alloy", "R8-C03",
     "Alumina-forming alloys (Inconel 601, Haynes 214, FeCrAl)"),
    ("CAND-03B", "FeCrAl (grade TBD)", "alumina-forming alloy", "R8-C03",
     "Alumina-forming alloys (Inconel 601, Haynes 214, FeCrAl)"),
    ("CAND-03C", "Haynes 214", "alumina-forming alloy", None, "Alumina-forming alloys (Inconel 601, Haynes 214, FeCrAl)"),
    ("CAND-04", "Rh electroplate on 316L (thickness TBD)", "noble-metal coating", "R8-C04", "Rhodium (plating)"),
    ("CAND-05", "Pt clad or plate on 316L", "noble-metal coating", "R8-C05", "Platinum (bulk or clad/plated)"),
    ("CAND-06", "Cr electroplate on 316L", "conductive-oxide-forming coating", "R8-C06", "Chromium (plating)"),
    ("CAND-07", "IrO2- or RuO2-based conductive-oxide coating (e.g. MMO on Ti)", "conductive-oxide coating", "R8-C07",
     "Conductive-oxide coatings (IrO2, RuO2; e.g. mixed-metal-oxide on Ti)"),
    ("CAND-08", "Bare tungsten", "refractory metal", "R8-C08", "Tungsten (bare)"),
    ("CAND-09", "Graphite (isotropic grade)", "carbon", "R8-C09", "Graphite (incl. pyrolytic)"),
    ("CAND-10", "Molybdenum / TZM", "refractory metal", None, "Molybdenum / TZM"),
    ("CAND-11", "Copper", "pure metal", None, "Copper"),
    ("CAND-12", "Iridium (bulk)", "platinum-group metal", None, "Iridium"),
    ("CAND-13", "Titanium", "pure metal", None, "Titanium"),
    ("CAND-14", "TiN / ZrN coatings", "nitride coating", None, "TiN / ZrN coatings"),
    ("CAND-15", "ZrB2 / HfB2 UHTC, SiC", "ceramic", None, "ZrB2/HfB2 UHTC, SiC"),
    ("CAND-16", "Hafnium / zirconium", "pure metal", None, "Hafnium / zirconium"),
]

APPLICATIONS = {
    "APP-ANODE": {"name": "H-1 anode / gas distributor (design-representative / flight)",
                  "thermal_status_key": "ANODE_THERMAL_CLOSURE",
                  "blockers": ["A9H-ANODE-01", "A9H-ANODE-02"],
                  "service": "electron-collecting electrode in the Hall discharge; O-bearing feed (N2+O2 up to the "
                             "delivered O2 fraction; atomic O in the separate life programme)"},
    "APP-COLLECTOR": {"name": "ICP electron-extraction collector / bias electrode (ICD ICP-21)",
                      "thermal_status_key": "ICP_COUPLED_THERMAL",
                      "blockers": ["ICP-21 material TBD (A9.1 A9-03-collector)"],
                      "service": "ion-collecting bias electrode inside the downstream ICP source (the analog drives it "
                                 "negative; sputtering / deposition observed, TK-71); Ar engineering, then N2, then "
                                 "O2-bearing"},
    # A9.13 S6.6 F2-OQ-04 (A9.16 step 1): the baseline intake filter is a P4 application; no filter material
    # candidate is defined anywhere (F2 lane F2-IF-08), so its candidate set is TBD and no gate cell is generated
    "APP-FILTER": {"name": "baseline intake filter element (intake / channel array -> filter -> compressor inlet)",
                   "thermal_status_key": "FILTER_THERMAL_STATE",
                   "blockers": ["filter material / geometry not defined (F2 lane F2-IF-08)",
                                "filter acceptance slots not registered before LOCK-1 (A9.13 S6.3)"],
                   "service": "particulate / debris protection of the compressor while preserving the atmospheric "
                              "propellant: N2 and atomic O transmitted (AO is not a contaminant to remove), "
                              "inert / low-recombination baseline (A9.13 S6.3 / S6.4); downstream of the primary "
                              "intake / collimator, upstream of the compressor; axial location, area and thermal state "
                              "are design variables (A9.13 S6.6)",
                   "candidate_scope": "TBD_AFTER_EVIDENCE - no filter material candidate is defined (none invented)"},
}
APP_SUFFIX = {"APP-ANODE": "A", "APP-COLLECTOR": "C", "APP-FILTER": "F"}
ELECTRODE_APPS = ["APP-ANODE", "APP-COLLECTOR"]

# ------------------------------------------------------------------------------------------------ property records
# (id, candidate, property, value_str, unit_reported, si_factor, unit_si, T_C, source_id, locator, verbatim_row,
#  column_index_in_verbatim, quantity_type)
PROPERTY_ROWS = [
    ("PR-001", "CAND-01", "density", "8.03", "g/cm3", 1000.0, "kg/m3", None, "CLF_316",
     "PDF p.4, 'PHYSICAL PROPERTIES' block (value in parentheses = SI-style unit)",
     "Density, lbs/in.3 (g/cm3) 0.29 (8.03)", "(8.03)", "measured"),
    ("PR-002", "CAND-01", "electrical_resistivity", "74", "uOhm*cm", 1e-8, "ohm*m", 20, "CLF_316",
     "PDF p.4, 'PHYSICAL PROPERTIES', Electrical Resistivity row 68 F (20 C)",
     "68 °F (20 °C) 29.4 (74)", "(74)", "measured"),
    ("PR-003", "CAND-01", "thermal_conductivity", "16.2", "W/(m*K)", 1.0, "W/(m*K)", 100, "CLF_316",
     "PDF p.4, 'PHYSICAL PROPERTIES', Thermal Conductivity row 212 F (100 C)",
     "212 °F (100 °C) 9.4 (16.2)", "(16.2)", "measured"),
    ("PR-004", "CAND-01", "thermal_conductivity", "21.4", "W/(m*K)", 1.0, "W/(m*K)", 500, "CLF_316",
     "PDF p.4, 'PHYSICAL PROPERTIES', Thermal Conductivity row 932 F (500 C)",
     "932 °F (500 °C) 12.4 (21.4)", "(21.4)", "measured"),
    ("PR-005", "CAND-01", "melting_range", "1371 –1399", "degC", None, "degC", None, "CLF_316",
     "PDF p.4, 'PHYSICAL PROPERTIES', Melting Range", "Melting Range, °F (°C) 2500 – 2550 (1371 –1399)",
     "(1371 –1399)", "measured"),
    ("PR-011", "CAND-02A", "density", "8.47", "Mg/m3", 1000.0, "kg/m3", None, "SMC_IN600",
     "PDF p.1, Table 2 - Physical Constants", "Mg/m3...................................................................8.47",
     "8.47", "measured"),
    ("PR-012", "CAND-02A", "electrical_resistivity", "1.03", "uOhm*m", 1e-6, "ohm*m", 20, "SMC_IN600",
     "PDF p.2, Table 3 - Thermal Properties, SI rows (columns: degC | um/m.degC | uOhm.m | W/m.degC | J/kg.degC)",
     "20 10.4 1.03 14.9 444", "1.03", "measured"),
    ("PR-013", "CAND-02A", "electrical_resistivity", "1.12", "uOhm*m", 1e-6, "ohm*m", 500, "SMC_IN600",
     "PDF p.2, Table 3 - Thermal Properties, SI rows", "500 14.9 1.12 22.1 536", "1.12", "measured"),
    ("PR-014", "CAND-02A", "electrical_resistivity", "1.13", "uOhm*m", 1e-6, "ohm*m", 800, "SMC_IN600",
     "PDF p.2, Table 3 - Thermal Properties, SI rows", "800 16.1 1.13 27.5 611", "1.13", "measured"),
    ("PR-015", "CAND-02A", "thermal_conductivity", "15.9", "W/(m*K)", 1.0, "W/(m*K)", 100, "SMC_IN600",
     "PDF p.2, Table 3 - Thermal Properties, SI rows", "100 13.3 1.04 15.9 465", "15.9", "measured"),
    ("PR-016", "CAND-02A", "thermal_conductivity", "22.1", "W/(m*K)", 1.0, "W/(m*K)", 500, "SMC_IN600",
     "PDF p.2, Table 3 - Thermal Properties, SI rows", "500 14.9 1.12 22.1 536", "22.1", "measured"),
    ("PR-017", "CAND-02A", "thermal_conductivity", "27.5", "W/(m*K)", 1.0, "W/(m*K)", 800, "SMC_IN600",
     "PDF p.2, Table 3 - Thermal Properties, SI rows", "800 16.1 1.13 27.5 611", "27.5", "measured"),
    ("PR-018", "CAND-02A", "melting_range", "1354-1413", "degC", None, "degC", None, "SMC_IN600",
     "PDF p.1, Table 2 - Physical Constants, Melting Range degC",
     "°C ...................................................1354-1413", "1354-1413", "measured"),
    ("PR-021", "CAND-03A", "density", "8.11", "Mg/m3", 1000.0, "kg/m3", None, "SMC_IN601",
     "PDF p.1, Table 2 - Physical Constants",
     "Mg/m3 .............................................................................8.11", "8.11", "measured"),
    ("PR-022", "CAND-03A", "electrical_resistivity", "1.180", "uOhm*m", 1e-6, "ohm*m", 20, "SMC_IN601",
     "PDF p.2, Table 3 - Thermal Properties of INCONEL alloy 601, SI rows (columns: degC | uOhm-m | W/m-degC | "
     "um/m/degC | J/kg-degC)", "20 1.180 11.2 - 448", "1.180", "measured"),
    ("PR-023", "CAND-03A", "electrical_resistivity", "1.239", "uOhm*m", 1e-6, "ohm*m", 500, "SMC_IN601",
     "PDF p.2, Table 3, SI rows", "500 1.239 19.5 15.19 578", "1.239", "measured"),
    ("PR-024", "CAND-03A", "electrical_resistivity", "1.249", "uOhm*m", 1e-6, "ohm*m", 800, "SMC_IN601",
     "PDF p.2, Table 3, SI rows", "800 1.249 24.4 16.67 657", "1.249", "measured"),
    ("PR-025", "CAND-03A", "thermal_conductivity", "12.7", "W/(m*K)", 1.0, "W/(m*K)", 100, "SMC_IN601",
     "PDF p.2, Table 3, SI rows (footnote a: calculated from electrical resistivity)", "100 1.192 12.7 13.75 469",
     "12.7", "inferred"),
    ("PR-026", "CAND-03A", "thermal_conductivity", "19.5", "W/(m*K)", 1.0, "W/(m*K)", 500, "SMC_IN601",
     "PDF p.2, Table 3, SI rows (footnote a)", "500 1.239 19.5 15.19 578", "19.5", "inferred"),
    ("PR-027", "CAND-03A", "thermal_conductivity", "24.4", "W/(m*K)", 1.0, "W/(m*K)", 800, "SMC_IN601",
     "PDF p.2, Table 3, SI rows (footnote a)", "800 1.249 24.4 16.67 657", "24.4", "inferred"),
    ("PR-028", "CAND-03A", "melting_range", "1360-1411", "degC", None, "degC", None, "SMC_IN601",
     "PDF p.1, Table 2 - Physical Constants, Melting Range degC",
     "°C .............................................................1360-1411", "1360-1411", "measured"),
]
BULK_DOMAIN = ["bulk_property", "annealed_or_as_supplied", "no_plasma", "no_electrical_loading"]

# ------------------------------------------------------------------------------------------------ qualitative links
# (link id, candidate ids, criterion, source file key, locator of the row inside the pinned input)
# R8 evidence rows are addressed by (source_id, material prefix); TK rows by id.
R8_LINKS = [
    ("EL-01", ["CAND-08"], "CR-02", ("TEJEDA2024", "Tungsten anode plate")),
    ("EL-02", ["CAND-01"], "CR-02", ("TEJEDA2024", "Stainless steel anode plate")),
    ("EL-03", ["CAND-01", "CAND-08"], "CR-02", ("TEJEDA2023", "Tungsten vs stainless steel anode")),
    ("EL-04", ["CAND-01"], "CR-02", ("MUNOZTEJEDA2024", "Stainless steel anode plate")),
    ("EL-05", ["CAND-11"], "CR-02", ("SCHWERTHEIM2022", "Copper anode")),
    ("EL-06", ["CAND-01", "CAND-04", "CAND-06"], "CR-02", ("IPPL_WEB", "Stainless steel anode cap")),
    ("EL-07", ["CAND-02D", "CAND-02E", "CAND-07", "CAND-12"], "CR-02", ("GABRIEL1993", "Anode (generic)")),
    ("EL-08", ["CAND-05"], "CR-02", ("GABRIEL1993", "SrO on Pt cathode")),
    ("EL-09", ["CAND-12"], "CR-02", ("GABRIEL1993", "Thoria-coated iridium")),
    ("EL-10", ["CAND-01", "CAND-02A", "CAND-03A"], "CR-02", ("CIFALI2011", "PPS1350-TSD anode (material not stated)")),
    ("EL-11", ["CAND-01", "CAND-02A", "CAND-03A"], "CR-02", ("ANDREUSSI2022", "PPS1350 anode")),
    ("EL-12", ["CAND-09"], "CR-02", ("CIFALI2011", "RIT-10 grids (graphite)")),
    ("EL-13", ["CAND-09"], "CR-03", ("BANKS2004", "Pyrolytic graphite")),
    ("EL-14", ["CAND-09"], "CR-03", ("MCCARTHY2010", "Pyrolytic graphite")),
    ("EL-15", ["CAND-10"], "CR-02", ("SMOLIK2000", "TZM")),
    ("EL-16", ["CAND-04", "CAND-12"], "CR-02", ("ZHAO2019", "Ir, IrRh10")),
    ("EL-17", ["CAND-04", "CAND-05", "CAND-12"], "CR-02", ("PGM1400_SNIPPET", "Rh, Pt, Ir")),
    ("EL-18", ["CAND-03A"], "CR-02", ("SMC_IN601", "INCONEL alloy 601")),
    ("EL-19", ["CAND-02A"], "CR-02", ("SMC_IN600", "INCONEL alloy 600")),
    ("EL-20", ["CAND-01"], "CR-02", ("SS316L_SLM2020", "AISI 316L")),
    ("EL-21", ["CAND-14"], "CR-02", ("TIN_CVD2020", "TiN")),
    ("EL-22", ["CAND-14"], "CR-02", ("ZRN_COAT2021", "ZrN")),
    ("EL-23", ["CAND-09"], "CR-02", ("THEODOSIOU2017", "Nuclear graphite")),
    ("EL-24", ["CAND-16"], "CR-02", ("HF_ARC_SNIPPET", "Hafnium cathode")),
    ("EL-25", ["CAND-13", "CAND-09"], "CR-04", ("ANDREUSSI2022", "Titanium vs graphite")),
]
TK_LINKS = [
    ("EL-26", ["CAND-01"], "CR-04", "TK-71", "APP-COLLECTOR",
     "analog electrode is stainless steel named SUS304 in Fig. 5 caption, not 316L; Ar only; qualitative"),
    ("EL-27", ["CAND-01"], "CR-07", "TK-02", "APP-ANODE",
     "analog HET anode/cavity is stainless steel (grade inferred by the ICP evidence lane - verify); Ar only"),
]

# ------------------------------------------------------------------------------------------------ criteria
CRITERIA = [
    {"id": "CR-01", "name": "continuous-use temperature (validated)", "property": "T_validated_continuous",
     "unit_si": "K", "kind": "min_with_margin",
     "rule": "T_operating <= T_validated,continuous - 50 K (owner row 87; A9.2 anode_approach; row 86 for every ICP "
             "module material incl. the collector, ICD); T_validated,continuous must come from the selected "
             "material's oxidation / electrical / creep data in the service condition; melting range and supplier "
             "air ratings are NOT a validated continuous-use limit; no new arbitrary limit. A9.12 P4-OQ-01 (staged): "
             "stage 1 coupon screening gives a coupon-supported provisional limit (design screening only); only stage "
             "2 integrated replaceable anode / collector confirmation on the H-1 / ICP article gives "
             "T_validated,continuous for P3 / LOCK-1; stage 3 qualification / life evidence before a flight-life "
             "claim; the gate admits only stage 2 or later",
     "domain": ["O_bearing_plasma_service", "electrically_loaded", "at_operating_temperature"]},
    {"id": "CR-02", "name": "oxidation behaviour (retention of electrical conduction)",
     "property": "resistance_rise_fraction_after_exposure", "unit_si": "1", "kind": "max",
     "rule": "4-wire resistance rise after a pre-registered exposure <= a pre-registered threshold; the failure mode "
             "in every O-plasma report is loss of conduction, not mass loss (R8)",
     "domain": ["O_bearing_plasma_service", "electrically_loaded", "at_operating_temperature"]},
    {"id": "CR-03", "name": "atomic-oxygen (AO) compatibility", "property": "ao_degradation_metric_at_fluence",
     "unit_si": "1", "kind": "max",
     "rule": "degradation (resistance and recession) at the derived AO fluence <= pre-registered threshold; only a "
             "dedicated AO source counts; N2+O2 surrogate data are labelled NO_ATOMIC_O and never AO-life proof "
             "(row 132)",
     "domain": ["atomic_O_exposure", "at_operating_temperature"]},
    {"id": "CR-04", "name": "sputtering (yield vs ion species and energy)", "property": "sputter_recession_over_life",
     "unit_si": "m", "kind": "max",
     "rule": "recession over the life basis from species-resolved yields (N+, N2+, O+, O2+, Xe+; Ar+ engineering only) "
             "at the sheath ion energy <= allowable thickness loss; deposition on H-1 front face / ICP dielectric is "
             "recorded, never corrected away (ICD)",
     "domain": ["species_resolved_ions", "sheath_energy_range"]},
    {"id": "CR-05", "name": "electrical conductivity", "property": "electrical_resistivity",
     "unit_si": "ohm*m", "kind": "max",
     "rule": "bulk resistivity at T_operating <= value derived from the allowed electrode-path voltage drop; scale / "
             "contact resistance is CR-02",
     "domain": ["bulk_property", "at_operating_temperature"]},
    {"id": "CR-06", "name": "thermal conductivity", "property": "thermal_conductivity",
     "unit_si": "W/(m*K)", "kind": "min",
     "rule": "k(T_operating) >= value the P3 heat-removal path requires (anode thermal-design-first, A9.2 sec. 4)",
     "domain": ["bulk_property", "at_operating_temperature"]},
    {"id": "CR-07", "name": "fabrication (machining, joining to backplate / feed tube, coating adhesion under "
                            "thermal cycling)", "property": "fabrication_trial_defect_metric", "unit_si": "1",
     "kind": "max", "rule": "fabrication / joining / thermal-cycling trial defect metric <= pre-registered limit",
     "domain": ["fabrication_trial", "thermal_cycling"]},
    {"id": "CR-08", "name": "mass / density", "property": "density", "unit_si": "kg/m3", "kind": "max",
     "rule": "part mass (density x CAD volume) within the anode (AL-04) / ICP module (AL-05) allocation; the density "
             "limit follows from the allocation and the geometry",
     "domain": ["bulk_property"]},
    {"id": "CR-09", "name": "evidence provenance (source, evidence class, applicability domain)",
     "property": None, "unit_si": None, "kind": None,
     "rule": "record rule, not a gate: every value carries source id, URL/access date or pinned repository path, "
             "locator, quantity type, evidence level, applicability domain and admissibility; 'verify' / snippet "
             "values are never admissible for a gate",
     "domain": []},
    # ---- A9.13 S6.6 F2-OQ-04 APP-FILTER criteria (owner list: AO / O exposure, erosion, catalytic / recombination
    # behaviour, particulate retention, thermal cycling, transmission / conductance effects); acceptance values are
    # pre-registered before LOCK-1 from the contamination environment, H-1 feed requirement and measured filter
    # material / geometry (A9.13 S6.3) - none here
    {"id": "CR-10", "name": "AO / O exposure and erosion (filter)", "property": "filter_ao_erosion_recession_at_fluence",
     "unit_si": "m", "kind": "max",
     "rule": "erosion / recession of the filter element at the derived AO / O fluence <= the pre-registered AO "
             "erosion / material-durability limit (A9.13 S6.3 / S6.6); only a dedicated AO source counts, N2+O2 "
             "surrogate data are NO_ATOMIC_O (row 132)",
     "domain": ["atomic_O_exposure", "filter_service_condition"]},
    {"id": "CR-11", "name": "catalytic / recombination behaviour (O recombination / conversion probability, filter)",
     "property": "o_recombination_conversion_probability", "unit_si": "1", "kind": "max",
     "rule": "O recombination / conversion probability <= the pre-registered limit; the baseline is inert / "
             "low-recombination and preserves the representative atmospheric O fraction (A9.13 S6.4); a catalytic "
             "O -> O2 element is a separately labelled research variant only",
     "domain": ["atomic_O_exposure", "filter_service_condition"]},
    {"id": "CR-12", "name": "particulate retention (capture efficiency vs registered contaminant class, filter)",
     "property": "capture_efficiency_vs_contaminant_class", "unit_si": "1", "kind": "min",
     "rule": "capture efficiency per registered contaminant / particle class >= the pre-registered value, with the "
             "retained contaminant capacity recorded (A9.13 S6.3); compressor wear products are not credited",
     "domain": ["registered_contaminant_class", "filter_service_condition"]},
    {"id": "CR-13", "name": "thermal cycling (filter)", "property": "filter_thermal_cycling_degradation_metric",
     "unit_si": "1", "kind": "max",
     "rule": "degradation after the pre-registered thermal cycling over the filter's registered thermal-state range "
             "<= the pre-registered limit (thermal state is a design variable, A9.13 S6.6)",
     "domain": ["thermal_cycling", "filter_service_condition"]},
    {"id": "CR-14", "name": "transmission (species-resolved propellant transmission, filter)",
     "property": "species_resolved_propellant_transmission", "unit_si": "1", "kind": "min",
     "rule": "species-resolved forward transmission (N2, O, ...) >= the pre-registered value (A9.13 S6.3 / S6.19); "
             "the filter owns its transmission, never hidden in the intake efficiency",
     "domain": ["species_resolved_flow", "filter_service_condition"]},
    {"id": "CR-15", "name": "conductance / pressure-loss effects (filter)", "property": "filter_conductance",
     "unit_si": "m3/s", "kind": "min",
     "rule": "conductance >= the value the AG-12 feed-state sufficiency closure requires (pressure-loss / conductance "
             "penalty, A9.13 S6.3 / S6.21)",
     "domain": ["registered_flow_regime", "filter_service_condition"]},
]
_FILTER_CRITERIA = ("CR-10", "CR-11", "CR-12", "CR-13", "CR-14", "CR-15")
for _c in CRITERIA:
    _c["applies_to"] = (["APP-ANODE", "APP-COLLECTOR", "APP-FILTER"] if _c["id"] == "CR-09" else
                        ["APP-FILTER"] if _c["id"] in _FILTER_CRITERIA else list(ELECTRODE_APPS))
GATED = [c for c in CRITERIA if c["kind"] is not None]

REQ_TBD = {
    ("CR-01", "APP-ANODE"): "TBD - margin 50 K is OWNER_GIVEN (row 87); T_operating is not evidenced "
                            "(ANODE_THERMAL_CLOSURE = UNRESOLVED; " + P3_REF + ")",
    ("CR-01", "APP-COLLECTOR"): "TBD - margin 50 K is OWNER_GIVEN (row 86 via ICD); T_operating of the collector is "
                                "not evidenced (ICP_COUPLED_THERMAL = UNRESOLVED; " + P3_REF + ")",
    ("CR-02", "APP-ANODE"): "TBD - resistance-rise threshold and exposure frozen at LOCK-2 after metrology "
                            "commissioning, before any acceptance-bearing exposure (A9.12 P4-OQ-03; "
                            "NOT_EVALUATED_LOCK2_TBD)",
    ("CR-02", "APP-COLLECTOR"): "TBD - as APP-ANODE (LOCK-2, A9.12 P4-OQ-03); collector coupons negative-biased + "
                                "floating control, bias magnitude from P1 evidence (A9.12 P4-OQ-05)",
    ("CR-03", "APP-ANODE"): "TBD - requires the AO fluence at the anode over the life basis (derivation not in the "
                            "repository) and the LOCK-2 acceptance (A9.12 P4-OQ-03)",
    ("CR-03", "APP-COLLECTOR"): "TBD - requires the AO fluence at the collector location and the LOCK-2 acceptance "
                                "(A9.12 P4-OQ-03)",
    ("CR-04", "APP-ANODE"): "TBD - requires the ion flux / energy at the anode and the allowable recession (H-1 anode "
                            "drawing, A9H-ANODE-01/02)",
    ("CR-04", "APP-COLLECTOR"): "TBD - requires the measured collector bias / sheath energy (P1; analog value is "
                                "analog-only) and the allowable recession (ICP-21 drawing)",
    ("CR-05", "APP-ANODE"): "TBD - requires the allowed anode-path voltage drop (V_d defined at the anode potential, "
                            "A9.1 A9-03-Vd) and the anode geometry",
    ("CR-05", "APP-COLLECTOR"): "TBD - requires the collector current path budget (ICP-21 V/I range TBD) and geometry",
    ("CR-06", "APP-ANODE"): P3_TBD + " (anode heat-removal path, A9H-ANODE-02)",
    ("CR-06", "APP-COLLECTOR"): P3_TBD + " (Q_collector)",
    ("CR-07", "APP-ANODE"): "TBD_OWNER - fabrication / joining acceptance pre-registered with the coupon plan",
    ("CR-07", "APP-COLLECTOR"): "TBD_OWNER - as APP-ANODE",
    ("CR-08", "APP-ANODE"): "TBD - requires the anode geometry (part mass inside AL-04 of " + MASS_REF + ")",
    ("CR-08", "APP-COLLECTOR"): "TBD - requires the collector geometry (part mass inside AL-05 of " + MASS_REF + ")",
}
_FILTER_TBD = ("TBD - pre-registered before LOCK-1 from the defined contamination environment, the H-1 feed "
               "requirement and the measured filter material / geometry (A9.13 S6.3; "
               "NOT_EVALUATED_FILTER_ACCEPTANCE_TBD); no number invented")
REQ_TBD.update({
    ("CR-10", "APP-FILTER"): _FILTER_TBD + " - AO erosion / material durability",
    ("CR-11", "APP-FILTER"): _FILTER_TBD + " - O recombination / conversion probability",
    ("CR-12", "APP-FILTER"): _FILTER_TBD + " - capture efficiency vs registered contaminant class",
    ("CR-13", "APP-FILTER"): _FILTER_TBD + " - thermal-cycling range (filter thermal state is a design variable)",
    ("CR-14", "APP-FILTER"): _FILTER_TBD + " - species-resolved propellant transmission",
    ("CR-15", "APP-FILTER"): _FILTER_TBD + " - pressure-loss / conductance penalty (AG-12 feed-state closure)",
})


def build_requirements():
    reqs = []
    for c in GATED:
        for app in c["applies_to"]:
            is_margin = c["id"] == "CR-01"
            reqs.append({
                "id": f"RQ-{c['id'][3:]}-{APP_SUFFIX[app]}",
                "criterion": c["id"], "application": app, "property": c["property"], "kind": c["kind"],
                "value": 50.0 if is_margin else None, "unit": c["unit_si"],
                "status": "OWNER_GIVEN" if is_margin else "TBD",
                "source": ("docs/decisions/OD_2026_09_29_owner_answers_147.json row 87 (anode) / row 86 (ICP module "
                           "materials); A9.2 anode_approach") if is_margin else "",
                "domain": c["domain"], "tbd": REQ_TBD[(c["id"], app)],
            })
    return reqs


# ------------------------------------------------------------------------------------------------ builders
def check_verbatim(value_str, verbatim, token):
    if token not in verbatim:
        raise BuildError(f"token {token!r} not in verbatim row {verbatim!r}")
    if value_str not in token:
        raise BuildError(f"value {value_str!r} not in token {token!r}")


def build_property_records():
    srcs = {s["id"] for s in NEW_SOURCES}
    cands = {c[0] for c in CANDIDATES}
    out = []
    for (pid, cand, prop, vstr, unit_r, fac, unit_si, t_c, sid, loc, verb, tok, qt) in PROPERTY_ROWS:
        if sid not in srcs or cand not in cands or qt not in QUANTITY_TYPES:
            raise BuildError(f"{pid}: unknown source/candidate/quantity type")
        check_verbatim(vstr, verb, tok)
        if prop == "melting_range":
            lo, hi = [float(x) for x in re.findall(r"\d+", vstr)]
            vsi = None
            informational = {"low_C": lo, "high_C": hi}
            adm, why = False, ("melting (solidus-liquidus) range is not a validated continuous-use limit (A9.2: no "
                               "material selected merely for melting point); informational only")
        else:
            vsi = float(f"{float(vstr) * fac:.6g}")
            informational = None
            adm, why = False, ("datasheet bulk property outside the service domain (no plasma, no electrical "
                               "loading, typical values); admissible only as a P3 / mass input, and no gate "
                               "requirement is evidenced")
        out.append({
            "id": pid, "candidate": cand, "property": prop, "value_reported": vstr, "unit_reported": unit_r,
            "value_si": vsi, "unit_si": unit_si, "informational": informational,
            "condition": {"temperature_C": t_c, "atmosphere": "not stated (datasheet)"},
            "domain": BULK_DOMAIN, "source_id": sid, "locator": loc, "verbatim_row": verb,
            "quantity_type": qt, "evidence_level": next(s["evidence_level"] for s in NEW_SOURCES if s["id"] == sid),
            "uncertainty": "not stated by the source (typical values)",
            "admissible_for_gate": adm, "admissibility_reason": why, "synthetic": False,
        })
    return out


def build_evidence_links(pins):
    r8 = pins["R8"]
    ev = r8["evidence"]
    out = []
    for lid, cands, crit, (sid, prefix) in R8_LINKS:
        hits = [e for e in ev if e["source_id"] == sid and e["material"].startswith(prefix)]
        if len(hits) != 1:
            raise BuildError(f"{lid}: R8 evidence row ({sid}, {prefix!r}) found {len(hits)} times")
        e = hits[0]
        verify = "verify" in (e["evidence_class"] or "").lower()
        out.append({
            "id": lid, "candidates": cands, "criterion": crit, "applications": ["APP-ANODE", "APP-COLLECTOR"],
            "source_file": PINS["R8"][0], "source_id": sid, "material_as_reported": e["material"],
            "atmosphere": e["atmosphere"], "temperature": e["temperature"], "result": e["result"],
            "value": e["value"], "unit": e["unit"], "locator": e["locator"], "evidence_class": e["evidence_class"],
            "applicability": e["applicability"], "limitations": e["limitations"],
            "quantity_type": "qualitative" if e["value"] in (None, "") else "published analog",
            "admissible_for_gate": False,
            "admissibility_reason": ("search-snippet / 'verify' level" if verify else
                                     "analog device / qualitative or furnace-only; the gate requirement is not "
                                     "evidenced"),
        })
    icp = pins["ICPEV"]
    for lid, cands, crit, tk, app, note in TK_LINKS:
        r = find_by_id(icp, tk)
        if r is None:
            raise BuildError(f"{lid}: {tk} not found in ICP evidence")
        out.append({
            "id": lid, "candidates": cands, "criterion": crit, "applications": [app],
            "source_file": PINS["ICPEV"][0], "source_id": tk, "material_as_reported": r["quantity"],
            "atmosphere": "Ar (analog)", "temperature": "not stated", "result": r["value"], "value": None,
            "unit": r["unit"], "locator": r["locator"], "evidence_class": r["evidence_class"],
            "applicability": "Takahashi et al. 2024 Hall + downstream RF-ICP analog (topology precedent only, A9)",
            "limitations": note, "quantity_type": "qualitative", "admissible_for_gate": False,
            "admissibility_reason": "qualitative analog observation; requirement not evidenced",
        })
    return out


def build_source_register(pins):
    r8src = {s["id"]: s for s in pins["R8"]["source_register"]}
    used = sorted({l[3][0] for l in R8_LINKS})
    reused = []
    for sid in used:
        if sid not in r8src:
            raise BuildError(f"R8 source {sid} missing")
        s = r8src[sid]
        reused.append({"id": sid, "cite": s["cite"], "url": s["url"], "access": s["access"],
                       "accessed": pins["R8"]["date"], "via": PINS["R8"][0]})
    return {"new_this_lane": NEW_SOURCES, "reused_from_r8": reused,
            "reused_from_icp_evidence": sorted({t[3] for t in TK_LINKS})}


def owner_answer(pins, row):
    for a in pins["ANS"]["answers"]:
        if a["row"] == row:
            return a
    raise BuildError(f"owner answer row {row} missing")


def build_fixed_statuses(pins):
    fs = pins["A96"]["summary"]["fixed_statuses"]
    a92 = pins["A92"]["decisions"]["a9_10_statuses"]
    need = {"316L_FLIGHT_ANODE": "REJECTED_AS_CURRENT_BASELINE", "FINAL_ANODE_MATERIAL": "OPEN",
            "ANODE_THERMAL_CLOSURE": "UNRESOLVED", "ICP_COUPLED_THERMAL": "UNRESOLVED"}
    for k, v in need.items():
        if fs.get(k) != v:
            raise BuildError(f"A9.6 fixed status {k} = {fs.get(k)!r}, expected {v!r}")
    if a92.get("316L flight anode") != "REJECTED_AS_CURRENT_BASELINE" or a92.get("final anode material") != "OPEN" \
            or a92.get("anode thermal closure") != "UNRESOLVED":
        raise BuildError("A9.2 a9_10_statuses drifted")
    col = pins["A91"]["decisions"]["A9-03-collector"]
    if "not frozen" not in col or "316L allowed for Ar engineering" not in col:
        raise BuildError("A9.1 A9-03-collector text drifted")
    return {
        "316L_FLIGHT_ANODE": {"status": fs["316L_FLIGHT_ANODE"],
                              "source": "A9.6 summary.fixed_statuses; A9.2 decisions.anode_316L / a9_10_statuses"},
        "FINAL_ANODE_MATERIAL": {"status": fs["FINAL_ANODE_MATERIAL"],
                                 "source": "A9.6 summary.fixed_statuses; A9.2 a9_10_statuses; owner row 106"},
        "ANODE_THERMAL_CLOSURE": {"status": fs["ANODE_THERMAL_CLOSURE"],
                                  "source": "A9.6 summary.fixed_statuses; A9.2 a9_10_statuses"},
        "ICP_COUPLED_THERMAL": {"status": fs["ICP_COUPLED_THERMAL"],
                                "source": "A9.6 summary.fixed_statuses; A9.2 icp_coupled_thermal"},
        "FINAL_COLLECTOR_MATERIAL": {"status": "OPEN",
                                     "source": "A9.1 decisions.A9-03-collector: " + col},
        "ANODE_BASELINE": {"status": "OPEN", "source": "A9.2 decisions.anode_approach"},
        "FINAL_FILTER_MATERIAL": {"status": "OPEN",
                                  "source": "A9.13 F2-OQ-04 (S6.6): APP-FILTER added to P4; no filter material defined"},
        "FILTER_THERMAL_STATE": {"status": "OPEN",
                                 "source": "A9.13 F2-OQ-04 (S6.6): axial location, area and thermal state remain "
                                           "design variables until geometry is frozen"},
    }


def h2_anode_context(pins):
    s = json.dumps(pins["H2A9"])
    vals = sorted(set(re.findall(r"below (\d+) degC \(lowest, LV-ALL\)", s)))
    if len(vals) != 1:
        raise BuildError(f"H2 A9 anode sensitivity number not unique: {vals}")
    for b in ("A9H-ANODE-01", "A9H-ANODE-02"):
        if b not in s:
            raise BuildError(f"{b} not found in H2 A9 revisions")
    return int(vals[0])


def build_items(pins, h2_val):
    r87, r86, r106 = owner_answer(pins, 87), owner_answer(pins, 86), owner_answer(pins, 106)
    r132, r134 = owner_answer(pins, 132), owner_answer(pins, 134)
    A = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
    it = [
        ("IT-01", "316L_FLIGHT_ANODE", "REJECTED_AS_CURRENT_BASELINE", "-", "owner decision",
         "A9.2 anode_316L; A9.6 fixed_statuses", "owner-stated", "REJECTED_AS_CURRENT_BASELINE", "NOW"),
        ("IT-02", "FINAL_ANODE_MATERIAL", "OPEN", "-", "owner decision; no selection without coupon evidence",
         f"A9.2 a9_10_statuses; A9.6 fixed_statuses; {A} row 106", "owner-stated", "OPEN", "after-evidence"),
        ("IT-03", "ANODE_THERMAL_CLOSURE", "UNRESOLVED", "-", "anode attacked as a thermal-design problem first",
         "A9.2 anode_approach; A9.6 fixed_statuses", "owner-stated", "UNRESOLVED", "after-evidence"),
        ("IT-04", "ICP_COUPLED_THERMAL (collector temperature)", "UNRESOLVED", "-",
         "collector heating is part of Q_collector in the coupled model", "A9.2 icp_coupled_thermal; A9.6",
         "owner-stated", "UNRESOLVED", "after-evidence"),
        ("IT-05", "FINAL_COLLECTOR_MATERIAL (ICP-21)", "OPEN", "-", "flight collector material not frozen",
         "A9.1 A9-03-collector", "owner-stated", "OPEN", "after-evidence"),
        ("IT-06", "316L for anode (engineering / shakedown) and collector (Ar engineering reproduction)",
         "ALLOWED_ENGINEERING_ONLY", "-", "never score-bearing design-representative material",
         f"{A} row 106; A9.2 anode_316L; A9.1 A9-03-collector", "owner-stated", "ALLOWED_ENGINEERING_ONLY", "NOW"),
        ("IT-07", "thermal margin below T_validated,continuous", 50, "K", r87["owner_answer_verbatim"],
         f"{A} row 87 (anode), row 86 (all materials); A9.2 anode_approach", "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-08", "heat-load design margin (input to the P3 T_operating, not applied here)", 20, "%",
         r86["owner_answer_verbatim"], f"{A} row 86", "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-09", "T_operating,anode", P3_TBD, "K",
         "requires the coupled anode thermal model (A9H-ANODE-02)", P3_REF, "model-derived", "TBD_AFTER_EVIDENCE",
         "after-evidence"),
        ("IT-10", "context only: H2 A9 uncoupled sensitivity, anode worst case not brought below (degC)", h2_val,
         "degC", "searched/bounded worst case over the lever sets evaluated (lowest, LV-ALL); UNCOUPLED, "
                 "ICP_COUPLED_THERMAL = UNRESOLVED; never a T_operating for a gate",
         PINS["H2A9"][0] + " key_findings (K6)", "model-derived", "CONTEXT_NOT_ADMISSIBLE", "after-evidence"),
        ("IT-11", "T_operating,collector", P3_TBD, "K", "requires Q_collector in the coupled model",
         P3_REF, "model-derived", "TBD_AFTER_EVIDENCE", "after-evidence"),
        ("IT-12", "T_validated,continuous per candidate", "TBD_AFTER_EVIDENCE", "K",
         "A9.12 P4-OQ-01 staged: only stage 2 (integrated replaceable anode / collector confirmation on the H-1 / ICP "
         "article, Q4) gives T_validated,continuous for P3 / LOCK-1; a stage-1 coupon result (Q0 / Q1, TP-01) is a "
         "coupon-supported provisional limit for design screening only; no datasheet air rating, melting range, "
         "short vendor exposure or brief coupon test counts", "test plan TP-01; " + APP.cite("A9.12", "P4-OQ-01"),
         "measured", "TBD_AFTER_EVIDENCE", "after-evidence"),
        ("IT-13", "resistance-rise threshold, mass-loss / recession limits, sputter / erosion acceptance, exposure "
         "duration / fluence, uncertainty treatment, acceptance / rejection logic",
         "TBD - frozen at LOCK-2 after metrology commissioning (IT-24), before any acceptance-bearing exposure "
         "(NOT_EVALUATED_LOCK2_TBD; candidate coupon performance never sets them)", "1; h",
         "A9.12 P4-OQ-03 (LOCK-2 alternative)", "R8 proposed_coupon_candidates.notes; " +
         APP.cite("A9.12", "P4-OQ-03"), "owner-allocation", "TBD", "LOCK-2"),
        ("IT-14", "coupon bias configuration", "anode coupons: biased AND floating (row 106); collector coupons: "
         "NEGATIVE-biased (ion-collecting service polarity, frozen) AND floating matched control (A9.12 P4-OQ-05)",
         "-", r106["owner_answer_verbatim"] + " | A9.12 S5.14: negative-bias collector set + floating control; "
         "polarity frozen; bias magnitude from P1 evidence", f"{A} row 106; " + APP.cite("A9.12", "P4-OQ-05"),
         "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-15", "atomic-O exposure", "dedicated AO source; N2+O2 surrogate labelled NO_ATOMIC_O", "-",
         r132["owner_answer_verbatim"], f"{A} row 132", "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-16", "witness coupons / holders", "non-functional exchangeable items", "-", r134["owner_answer_verbatim"],
         f"{A} row 134", "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-17", "Q0 coupon screening matrix (R8-C01..C09 with the owner's named variants; reserve list)",
         "Q0 matrix per A9.12 P4-OQ-02 (a9_16_owner_rules.q0_matrix): C01 316L reference control; C02 IN600 / IN625 / "
         "Haynes 230 (+ X-750 if readily available; no generic Hastelloy); C03 IN601 / Haynes 214 / one specified "
         "FeCrAl grade; C04 Rh-coated 316L; C05 Pt-clad / plated 316L; C06 Cr-plated 316L; C07 IrO2 / RuO2 MMO (exact "
         "system + substrate); C08 bare W negative / reference control; C09 specified isotropic graphite control; Ti, "
         "TiN / ZrN, bulk Cu, bulk Ir reserve only", "-",
         "A9.12 S5.11: broad Q0, evidence-based down-selection before Q1", APP.cite("A9.12", "P4-OQ-02"),
         "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-18", "AO fluence at anode / collector over the life basis", "TBD - requires an AO flux derivation at "
         "the electrode locations (not in the repository)", "atoms/m2", "input to CR-03", "-", "model-derived",
         "TBD", "after-evidence"),
        ("IT-19", "ion species / energy at the collector (and the collector-coupon bias magnitude)",
         "TBD - requires the measured P1 collector operating envelope and plasma / sheath evidence (ICD ICP-21; analog "
         "value analog-only; A9.12 P4-OQ-05: the coupon bias magnitude is derived from it, never invented)", "eV",
         "input to CR-04 and the acceptance-bearing negative-bias collector coupons",
         "P1 measured data from " + P1_REF + " (none recorded yet; "
         "the sheath-edge plasma potential is conditional on P3Q-01)", "measured", "TBD_AFTER_EVIDENCE",
         "after-evidence"),
        ("IT-20", "allowable electrode-path resistance", "TBD - requires the V_d / collector V-I budget", "ohm",
         "input to CR-05", "A9.1 A9-03-Vd; ICD ICP-21", "owner-allocation", "TBD", "LOCK-1"),
        ("IT-21", "anode / collector mass allocation", "TBD - the part share inside the owner line allocations AL-04 / "
         "AL-05 of " + MASS_REF + " requires the part geometry (no part allocation exists)", "kg", "input to CR-08",
         MASS_REF, "owner-allocation", "TBD", "LOCK-1"),
        ("IT-22", "sputter-yield data for candidates", "TBD - requires species-resolved yields (open elemental "
         "compilation NIFS_DATA_23 located, not digitized); A9.12 P4-OQ-04 BOTH: lawful acquisition of N+ / N2+ / O+ / "
         "O2+ yields (priors / matrix selection / comparison / model initialisation) AND project ion-beam measurement "
         "of the down-selected candidates (candidate-specific evidence); no silent elemental substitution for alloys / "
         "coatings", "atoms/ion", "input to CR-04", "NIFS_DATA_23 (located only); " + APP.cite("A9.12", "P4-OQ-04"),
         "digitized", "TBD", "after-evidence"),
        # ---- A9.16 step 1 registration slots (owner fixed the form; numbers / declarations deferred)
        ("IT-23", "staged evidence hierarchy for T_validated,continuous", "ST-1 coupon screening -> "
         "COUPON_SUPPORTED_PROVISIONAL_LIMIT (screening only); ST-2 integrated replaceable anode / collector "
         "confirmation on H-1 / ICP -> T_VALIDATED_CONTINUOUS (P3 / LOCK-1); ST-3 qualification / life -> "
         "FLIGHT_LIFE_QUALIFIED_LIMIT", "-", "A9.12 S5.10", APP.cite("A9.12", "P4-OQ-01"), "owner-stated",
         "OWNER_GIVEN", "NOW"),
        ("IT-24", "Q0 / Q1 metrology commissioning (resistance repeatability / resolution, mass-change detection "
         "limit, profilometry / recession resolution, SEM / XPS where applicable, coupon-to-coupon / process "
         "repeatability, AO / ion dosimetry)", "TBD - commissioned on standards / blanks / controls / sacrificial "
         "coupons before LOCK-2 (NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD)", "-", "A9.12 S5.12",
         APP.cite("A9.12", "P4-OQ-03"), "measured", "TBD_AFTER_EVIDENCE", "LOCK-2"),
        ("IT-25", "sputter-data acquisition routes", "library access, inter-library loan, publisher purchase, "
         "institutional subscription, other legitimate licensed route (authorized; not performed by this lane)", "-",
         "A9.12 S5.13", APP.cite("A9.12", "P4-OQ-04"), "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-26", "FeCrAl grade (Q0-C03-FECRAL)", "TBD - one explicitly specified grade declared before admission "
         "(NOT_ADMITTED_GRADE_TBD)", "-", "A9.12 S5.11", APP.cite("A9.12", "P4-OQ-02"), "owner-allocation", "TBD",
         "LOCK-2"),
        ("IT-27", "isotropic graphite grade (Q0-C09 control)", "TBD - specified grade declared before admission "
         "(NOT_ADMITTED_GRADE_TBD)", "-", "A9.12 S5.11", APP.cite("A9.12", "P4-OQ-02"), "owner-allocation", "TBD",
         "LOCK-2"),
        ("IT-28", "IrO2 / RuO2 MMO coating system and substrate (Q0-C07)", "TBD - exact coating system and substrate "
         "declared with the full coating record (NOT_ADMITTED_COATING_SYSTEM_TBD)", "-", "A9.12 S5.11",
         APP.cite("A9.12", "P4-OQ-02"), "owner-allocation", "TBD", "LOCK-2"),
        ("IT-29", "collector-coupon bias polarity", "NEGATIVE (ion-collecting service condition) + FLOATING matched "
         "control; frozen", "-", "A9.12 S5.14", APP.cite("A9.12", "P4-OQ-05"), "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-30", "baseline filter placement and recombination class (APP-FILTER)", RULES.FILTER_PLACEMENT +
         "; inert / low-recombination baseline; catalytic O -> O2 only as a separate research variant", "-",
         "A9.13 S6.6 / S6.4 / S6.3", APP.cite("A9.13", "F2-OQ-04"), "owner-stated", "OWNER_GIVEN", "NOW"),
        ("IT-31", "APP-FILTER acceptance (capture efficiency vs contaminant class, species-resolved transmission, "
         "pressure-loss / conductance penalty, O recombination / conversion probability, retained capacity, AO "
         "erosion / durability, AG-12 effect)", "TBD - pre-registered before LOCK-1 from the contamination "
         "environment, H-1 feed requirement and measured filter material / geometry "
         "(NOT_EVALUATED_FILTER_ACCEPTANCE_TBD)", "-", "A9.13 S6.3", APP.cite("A9.13", "F2-OQ-04"),
         "owner-allocation", "TBD", "LOCK-1"),
    ]
    out = []
    for (iid, name, val, unit, basis, src, qt, st, fp) in it:
        if st not in ITEM_STATUSES or fp not in FREEZE_POINTS or qt not in QUANTITY_TYPES:
            raise BuildError(f"{iid}: bad status/freeze/class")
        out.append({"id": iid, "item": name, "value": val, "units": unit, "basis": basis, "source": src,
                    "evidence_class": qt, "status": st, "freeze_point": fp})
    return out


def run_screening(reqs, props, fixed):
    SCR.check_evidence_mode(props, synthetic_mode=False)
    by = {}
    for p in props:
        by.setdefault((p["candidate"], p["property"]), []).append(p)
    matrix = []
    states = {}
    for app, ad in APPLICATIONS.items():
        tstat = fixed[ad["thermal_status_key"]]["status"]
        if app not in ELECTRODE_APPS:
            continue  # APP-FILTER: candidate set TBD_AFTER_EVIDENCE (no filter material is defined; none invented)
        for cid, *_ in CANDIDATES:
            outs = []
            for r in [r for r in reqs if r["application"] == app]:
                recs = by.get((cid, r["property"]), [])
                # several records for one (candidate, property) at different conditions: no condition-matching rule
                # is registered, so a gate is applied only to a single admissible record; two or more admissible
                # records are ambiguous -> INCOMPLETE_EVIDENCE (never an implicit first-record choice; SW-05)
                adm = [x for x in recs if x["admissible_for_gate"] is True]
                ambiguous = len(adm) > 1
                prop = adm[0] if len(adm) == 1 else (recs[0] if recs else None)
                kw = {}
                if r["kind"] == "min_with_margin":
                    kw = {"thermal_closure_status": tstat, "operating_temperature": None}
                o, why = SCR.evaluate_gate(r, prop, **kw)
                if ambiguous:
                    o, why = "INCOMPLETE_EVIDENCE", (f"{len(adm)} admissible property records at different conditions; "
                                                     "no registered condition-matching rule: ambiguous")
                elif prop is not None and not SCR.requirement_evidenced(r):
                    why = f"requirement {r['id']} not evidenced ({r['tbd']})"
                elif prop is None:
                    why = f"no property record; requirement: {r['tbd']}"
                outs.append(o)
                matrix.append({"application": app, "candidate": cid, "criterion": r["criterion"],
                               "requirement": r["id"], "property_records": [x["id"] for x in recs],
                               "outcome": o, "reason": why})
            states[f"{app}|{cid}"] = SCR.candidate_screening_state(outs)
    return matrix, states


def build_pareto(props):
    def val(c, prop, t):
        for p in props:
            if p["candidate"] == c and p["property"] == prop and p["condition"]["temperature_C"] == t:
                return p["value_si"]
        return None
    cands = [c[0] for c in CANDIDATES]
    views = []
    for vid, spec in (
            ("PV-1", {"density (T not stated)": ("density", None, "min"), "electrical_resistivity@20C":
                      ("electrical_resistivity", 20, "min"), "thermal_conductivity@100C":
                      ("thermal_conductivity", 100, "max")}),
            ("PV-2", {"electrical_resistivity@500C": ("electrical_resistivity", 500, "min"),
                      "thermal_conductivity@500C": ("thermal_conductivity", 500, "max")}),
            ("PV-3", {"electrical_resistivity@800C": ("electrical_resistivity", 800, "min"),
                      "thermal_conductivity@800C": ("thermal_conductivity", 800, "max")})):
        values = {c: {o: val(c, p, t) for o, (p, t, _s) in spec.items()} for c in cands}
        v = SCR.pareto_view(cands, values, {o: s for o, (_p, _t, s) in spec.items()})
        v["id"] = vid
        v["values"] = {c: values[c] for c in v["compared"]}
        v["caveats"] = [
            "bulk datasheet properties (no plasma, no electrical loading, typical values); they do not address the "
            "dominant failure mode (loss of conduction through oxide scale, CR-02) or AO / sputtering",
            "CAND-01 316L is REJECTED_AS_CURRENT_BASELINE for the flight / design-representative anode (A9.2) "
            "whatever this view shows",
            "INFORMATIONAL_NOT_A_SELECTION: non-dominance is not a ranking, a recommendation or a gate result",
        ]
        views.append(v)
    return views


def build_coverage(props, links):
    out = {}
    for cid, *_ in CANDIDATES:
        populated = sorted({p["property"] for p in props if p["candidate"] == cid and
                            (p["value_si"] is not None or p["informational"])})
        admissible = sorted({p["property"] for p in props if p["candidate"] == cid and p["admissible_for_gate"]})
        crit_links = sorted({l["criterion"] for l in links if cid in l["candidates"]})
        out[cid] = {"datasheet_properties_populated": populated, "gate_admissible_properties": admissible,
                    "qualitative_evidence_criteria": crit_links,
                    "gated_criteria_with_admissible_evidence": 0, "gated_criteria_total": len(GATED)}
    return out


TEST_PLAN = [
    {"id": "TP-00", "criterion": "CR-09", "populates": "metrology capability (LOCK-2 input)",
     "measure": "commissioning of the Q0 / Q1 metrology: resistance repeatability / resolution, mass-change detection "
                "limit, profilometry / recession resolution, SEM / XPS capability where applicable, coupon-to-coupon "
                "/ process repeatability, AO / ion exposure dosimetry - on standards, blanks, controls or sacrificial "
                "commissioning coupons only; then LOCK-2 freezes the acceptance before any acceptance-bearing "
                "exposure; an unresolvable criterion -> NOT_EVALUATED_METROLOGY (never widened) (A9.12 P4-OQ-03)",
     "instruments": "4-wire micro-ohmmeter; balance; profilometer; SEM / XPS; AO / ion dosimetry",
     "atmosphere_sequence": "-", "acceptance": "commissioning record complete (p4_a9_16_rules.metrology_commissioning)",
     "register_links": ["AOL-RC-02", "AOL-PM-02"]},
    {"id": "TP-01", "criterion": "CR-01", "populates": "T_validated_continuous",
     "measure": "STAGE 1 (A9.12 P4-OQ-01): long-duration coupon exposure at controlled temperature steps in the "
                "service-representative atmosphere / species with the coupon electrically loaded (electron-collecting "
                "biased + floating for anode coupons, row 106; NEGATIVE-biased + floating control for collector "
                "coupons, A9.12 P4-OQ-05, bias magnitude from the measured P1 collector envelope), pre-registered "
                "exposure duration and thermal cycling where applicable; in-situ 4-wire resistance and adjacent "
                "thermocouple; the highest step at which the pre-registered (LOCK-2) acceptance holds for the "
                "pre-registered exposure is a COUPON-SUPPORTED PROVISIONAL limit (design screening only); "
                "T_validated,continuous needs STAGE 2 (Q4)",
     "instruments": "coupon thermocouples (AOL-CX-07); 4-wire resistance (AOL-RC-02 method); bias supply V/I",
     "atmosphere_sequence": "Ar (engineering only) -> N2 -> N2+O2 up to the delivered O2 fraction (label NO_ATOMIC_O) "
                            "-> dedicated AO source (row 132)",
     "acceptance": "TBD - LOCK-2 registration before any acceptance-bearing exposure (A9.12 P4-OQ-01 / P4-OQ-03; "
                   "NOT_EVALUATED_LOCK2_TBD)",
     "register_links": ["AOL-EX-02", "AOL-CX-07"]},
    {"id": "TP-02", "criterion": "CR-02", "populates": "resistance_rise_fraction_after_exposure",
     "measure": "4-wire sheet / contact resistance before, during and after exposure; oxide thickness and phase "
                "(SEM / XPS); mass by the dehydrated protocol; anode coupons biased AND floating (row 106); "
                "collector coupons NEGATIVE-biased AND floating control (A9.12 P4-OQ-05); Q0 matrix per A9.12 "
                "P4-OQ-02",
     "instruments": "4-wire micro-ohmmeter; SEM / XPS; balance (AOL-PM-02)",
     "atmosphere_sequence": "as TP-01", "acceptance": "TBD - LOCK-2 (A9.12 P4-OQ-03; NOT_EVALUATED_LOCK2_TBD)",
     "register_links": ["AOL-EX-02", "AOL-WC-02", "AOL-RC-01", "AOL-RC-02", "AOL-PM-02"]},
    {"id": "TP-03", "criterion": "CR-03", "populates": "ao_degradation_metric_at_fluence",
     "measure": "exposure in a dedicated atomic-O source with measured fluence (and a fluence witness), at the "
                "operating temperature; resistance and recession / mass change; N2+O2 surrogate results labelled "
                "NO_ATOMIC_O and never AO-life proof",
     "instruments": "AO source with fluence witness; 4-wire resistance; profilometer / balance",
     "atmosphere_sequence": "dedicated AO source only (row 132)", "acceptance": "TBD_OWNER",
     "register_links": ["AOL-EX-02"]},
    {"id": "TP-04", "criterion": "CR-04", "populates": "sputter_recession_over_life",
     "measure": "species-resolved yield vs ion energy (N+, N2+, O+, O2+, Xe+; Ar+ engineering only; Xe+ because Xe "
                "is an RFP-required propellant capability, A9.15) - A9.12 P4-OQ-04 BOTH: lawfully acquired literature "
                "yields for prior bounds / test-matrix selection / comparison / model initialisation, AND project "
                "ion-beam measurement of the down-selected candidates at the relevant species / energy / angle / "
                "material (candidate-specific evidence); no silent elemental substitution for alloys / coatings; "
                "in-thruster / in-ICP witness coupons for recession and deposition on the H-1 front face and ICP "
                "dielectric",
     "instruments": "ion source with energy / species control or published data; profilometer; witness holders "
                    "(exchangeable, row 134)",
     "atmosphere_sequence": "ion-beam bench; then H-1 / ICP witness positions (ICD)",
     "acceptance": "TBD - LOCK-2 sputtering / erosion acceptance (A9.12 P4-OQ-03)",
     "register_links": ["AOL-WC-02"]},
    {"id": "TP-05", "criterion": "CR-05", "populates": "electrical_resistivity",
     "measure": "4-wire bulk resistivity vs temperature up to above T_operating on the procured heat / lot "
                "(datasheet typical values are not lot data)",
     "instruments": "4-wire resistivity rig in vacuum furnace", "atmosphere_sequence": "vacuum / inert",
     "acceptance": "TBD (requirement IT-20)", "register_links": []},
    {"id": "TP-06", "criterion": "CR-06", "populates": "thermal_conductivity",
     "measure": "k(T) (e.g. laser flash + density + specific heat) on the procured lot up to above T_operating; "
                "joint / contact conductance of the anode-to-backplate and feed-tube joints for the P3 heat path",
     "instruments": "thermal diffusivity rig; instrumented joint test", "atmosphere_sequence": "vacuum",
     "acceptance": "TBD (k required by the heat path of " + P3_REF + ")", "register_links": []},
    {"id": "TP-07", "criterion": "CR-07", "populates": "fabrication_trial_defect_metric",
     "measure": "machining to the anode / collector drawing tolerances; joining (braze / weld / mechanical) to "
                "backplate and feed tube; coating adhesion and thickness after thermal cycling to above T_operating",
     "instruments": "CMM; metallography; adhesion test; thermal-cycling rig", "atmosphere_sequence": "vacuum / air",
     "acceptance": "TBD_OWNER", "register_links": ["AOL-RC-01"]},
    {"id": "TP-08", "criterion": "CR-08", "populates": "density",
     "measure": "density of the procured lot; part mass from CAD and weighed part", "instruments": "balance; CAD",
     "atmosphere_sequence": "-", "acceptance": "TBD (part mass within " + MASS_REF + ")", "register_links": []},
    {"id": "TP-09", "criterion": "CR-09", "populates": "provenance fields",
     "measure": "every coupon / lot record carries heat / lot id, supplier certificate, test procedure id, raw data "
                "file sha256, evidence class, applicability domain; excluded records kept with the reason",
     "instruments": "-", "atmosphere_sequence": "-", "acceptance": "record rule (fail closed)", "register_links": []},
]
# ---- A9.13 S6.6 F2-OQ-04: APP-FILTER tests (owner list); acceptance pre-registered before LOCK-1 (S6.3)
_FILTER_ACC = "TBD - pre-registered before LOCK-1 (A9.13 S6.3; NOT_EVALUATED_FILTER_ACCEPTANCE_TBD)"
TEST_PLAN += [
    {"id": "TP-10", "criterion": "CR-10", "populates": "filter_ao_erosion_recession_at_fluence",
     "measure": "AO / O exposure of filter-element coupons in a dedicated AO source with measured fluence at the "
                "registered filter thermal state; erosion / recession and mass change",
     "instruments": "AO source with fluence witness; profilometer / balance", "atmosphere_sequence":
     "dedicated AO source (row 132); N2+O2 surrogate labelled NO_ATOMIC_O", "acceptance": _FILTER_ACC,
     "register_links": ["AOL-EX-02"]},
    {"id": "TP-11", "criterion": "CR-11", "populates": "o_recombination_conversion_probability",
     "measure": "catalytic / recombination behaviour: O recombination / conversion probability of the filter "
                "material / geometry (species-conversion measurement)", "instruments": "AO source; species-resolved "
     "downstream measurement", "atmosphere_sequence": "dedicated AO source", "acceptance": _FILTER_ACC,
     "register_links": []},
    {"id": "TP-12", "criterion": "CR-12", "populates": "capture_efficiency_vs_contaminant_class",
     "measure": "particulate retention: capture efficiency per registered contaminant / particle class and retained "
                "contaminant capacity", "instruments": "particle source / counter (per registered class)",
     "atmosphere_sequence": "-", "acceptance": _FILTER_ACC, "register_links": []},
    {"id": "TP-13", "criterion": "CR-13", "populates": "filter_thermal_cycling_degradation_metric",
     "measure": "thermal cycling over the registered filter thermal-state range; integrity / transmission after "
                "cycling", "instruments": "thermal-cycling rig; metallography", "atmosphere_sequence": "vacuum",
     "acceptance": _FILTER_ACC, "register_links": []},
    {"id": "TP-14", "criterion": "CR-14", "populates": "species_resolved_propellant_transmission",
     "measure": "species-resolved forward (and, where relevant, reverse) transmission of the filter element",
     "instruments": "molecular-flow transmission rig (species-resolved)", "atmosphere_sequence": "N2, O-bearing",
     "acceptance": _FILTER_ACC, "register_links": []},
    {"id": "TP-15", "criterion": "CR-15", "populates": "filter_conductance",
     "measure": "conductance / pressure-loss penalty of the filter element in the registered flow regime",
     "instruments": "conductance rig; calibrated gauges", "atmosphere_sequence": "N2",
     "acceptance": _FILTER_ACC + " (AG-12 feed-state closure)", "register_links": []},
]
QUAL_STAGES = [
    {"id": "Q0", "name": "broad screening coupons (bench) over the owner Q0 matrix (A9.12 P4-OQ-02); validation "
                         "stage ST-1", "tests": ["TP-00", "TP-02", "TP-05", "TP-06", "TP-08"]},
    {"id": "Q1", "name": "electrically loaded plasma coupons for Q0 survivors only (pre-registered screening "
                         "criteria): anode biased + floating (row 106), collector negative-biased + floating "
                         "(A9.12 P4-OQ-05); validation stage ST-1 (coupon-supported provisional limit)",
     "tests": ["TP-01", "TP-02"]},
    {"id": "Q2", "name": "dedicated atomic-O coupons (row 132)", "tests": ["TP-03"]},
    {"id": "Q3", "name": "fabrication / joining / thermal cycling", "tests": ["TP-07"]},
    {"id": "Q4", "name": "in-H-1 / in-ICP witness and replaceable anode / collector confirmation (validation stage "
                         "ST-2: the only source of T_validated,continuous for P3 / LOCK-1)", "tests": ["TP-01", "TP-02",
                                                                                                       "TP-04"]},
    {"id": "Q5", "name": "qualification / life evidence (validation stage ST-3: full-duration or justified "
                         "accelerated life before a flight-life claim)", "tests": ["TP-01", "TP-02", "TP-04"]},
    {"id": "QF", "name": "APP-FILTER material programme (A9.13 F2-OQ-04)", "tests": ["TP-10", "TP-11", "TP-12",
                                                                                      "TP-13", "TP-14", "TP-15"]},
]
VALIDATION_STAGES = [
    {"id": "ST-1", "stage": "STAGE_1_COUPON_SCREENING", "qual_stages": ["Q0", "Q1"],
     "result": "COUPON_SUPPORTED_PROVISIONAL_LIMIT", "usable_for": ["design_screening"]},
    {"id": "ST-2", "stage": "STAGE_2_INTEGRATED_REPLACEABLE_COMPONENT_CONFIRMATION", "qual_stages": ["Q4"],
     "result": "T_VALIDATED_CONTINUOUS", "usable_for": ["design_screening", "p3_lock1_material_temperature_closure"]},
    {"id": "ST-3", "stage": "STAGE_3_QUALIFICATION_LIFE_EVIDENCE", "qual_stages": ["Q5"],
     "result": "FLIGHT_LIFE_QUALIFIED_LIMIT",
     "usable_for": ["design_screening", "p3_lock1_material_temperature_closure", "final_flight_life_claim"]},
]

INTERFACE_DEMANDS = [  # (id, direction, counterpart, content, used_for, status, units, xref pairs)
    ("ID-01", "P4 <- P3", XLANE_PATHS["P3"] + " (P3-IF-S07)", "T_operating of anode and collector (worst case, "
     "coupled), heat flux, gradients, 20 % heat-load margin applied (row 86)", "CR-01 / CR-05 / CR-06 condition",
     XL_PAIRS["XL-24"][4], XL_PAIRS["XL-24"][3], ["XL-24"]),
    ("ID-02", "P4 -> P3", XLANE_PATHS["P3"] + " (P3-IF-N05)", "k(T), density per candidate with provenance (PR-xxx); "
     "emissivity TBD - requires a sourced emissivity per candidate and surface state", "anode / collector "
     "conduction and radiation nodes", XL_PAIRS["XL-23"][4], XL_PAIRS["XL-23"][3], ["XL-23"]),
    ("ID-03", "P4 <- H-1 design", PINS["H2A9"][0], "anode geometry, joints, feed-tube path (A9H-ANODE-01/02)",
     "CR-04 / CR-07 / CR-08", "PENDING", "mm", []),
    ("ID-04", "P4 <- ICD", PINS["ICD"][0], "ICP-21 collector V/I range and geometry; witness positions",
     "CR-04 / CR-05 (collector)", "PENDING", "V; A; mm", []),
    ("ID-05", "P4 -> ICD", PINS["ICD"][0], "collector material remains OPEN; 316L Ar-engineering only; the framework "
     "rows APP-COLLECTOR", "ICP-21 material_a9_1", "DEFINED", "-", []),
    ("ID-06", "P4 <- P1", XLANE_PATHS["P1"] + " (IF-P1-36)", "measured collector bias / current, sheath energy "
     "estimate", "CR-04 collector ion energy", XL_PAIRS["XL-25"][4], XL_PAIRS["XL-25"][3], ["XL-25"]),
    ("ID-07", "P4 -> mass", XLANE_PATHS["MP"] + " (MPV2-ID-03)", "density per candidate (PR-001/011/021)",
     "anode (AL-04) / collector (AL-05) CBE when geometry exists", XL_PAIRS["XL-26"][4], XL_PAIRS["XL-26"][3],
     ["XL-26"]),
    ("ID-08", "P4 <-> AO / lifetime register", PINS["AOL5"][0], "AOL-EX-02 / AOL-WC-02 / AOL-RC-01 / AOL-RC-02 / "
     "AOL-CX-07 / AOL-PM-02 coupon and metrology rules", "test plan TP-01..TP-04", "DEFINED", "-", []),
    ("ID-09", "P4 -> RFQ", XLANE_PATHS["RFQ"] + " (IFD-17)", "coupon material lots (heat / lot certificates), "
     "coatings, AO-source access (RFQ only, no purchase)", "Q0-Q3", XL_PAIRS["XL-27"][4], XL_PAIRS["XL-27"][3],
     ["XL-27"]),
    ("ID-10", "P4 -> RVM", "fo_a9_6_rvm (parallel lane, path not in this base)", "AO / material compatibility row: "
     "INCOMPLETE_EVIDENCE for every candidate and application", "RVM state", "DEFINED", "-", []),
    ("ID-11", "P4 -> M16", PINS["M16V3"][0], "rows 18, 20, 21: framework implemented; readiness unchanged",
     "m16_impact", "DEFINED", "-", []),
    ("ID-12", "P4 <-> F2 filter", APP.F2_REL + " (F2-IF-08)", "APP-FILTER (A9.13 F2-OQ-04): filter material / "
     "geometry, thermal-state range and contamination classes from F2; P4 returns the CR-10..CR-15 evidence (AO / O "
     "erosion, recombination, retention, thermal cycling, transmission, conductance)", "APP-FILTER; test plan "
     "TP-10..TP-15", "TBD_AFTER_EVIDENCE (no filter material defined; acceptance pre-registered before LOCK-1)", "-",
     []),
]
A9_16_IFD_NOTES = {
    "ID-06": "A9.12 P4-OQ-05: the collector-coupon bias magnitude / ion energy is derived from this measured P1 "
             "collector envelope and plasma / sheath evidence before any acceptance-bearing biased exposure",
    "ID-09": "A9.12 P4-OQ-02 fixes the Q0 coupon matrix (a9_16_owner_rules.q0_matrix); the XL-27 pair text "
             "'coupon shortlist TBD_OWNER P4 IT-17' is identical on both sides and is re-stated with RFQ at the "
             "integration re-pin",
}

NEW_OPEN_QUESTIONS = [
    {"id": "P4-OQ-01", "question": "Evidence standard for 'T_validated,continuous' of an anode / collector material: "
     "which exposure (atmosphere, bias, duration relative to the provisional firing basis, acceptance metric) makes "
     "a continuous-use temperature 'validated' for the row-87 / A9.2 rule?",
     "why": "row 87 / A9.2 require a validated limit but define no validation standard; datasheet air ratings and "
            "melting ranges are not admissible here",
     "related_existing_open": "OQ-A907-05 (supplier ratings as provisional limits for BN / wire) - OPEN, not answered "
                              "here", "admissible_alternatives": ["coupon exposure at the service condition for a "
                              "pre-registered fraction of the firing basis", "full-duration life test",
                              "staged: coupon screening + in-H-1 replaceable-anode confirmation"],
     "status": "TBD_OWNER"},
    {"id": "P4-OQ-02", "question": "Coupon shortlist: which variants of R8-C02 (IN600 / IN625 / Haynes 230 / X-750 / "
     "Hastelloy) and R8-C03 (IN601 / FeCrAl / Haynes 214) and which optional R8-matrix rows (Ti, TiN / ZrN, Cu, Ir) "
     "enter Q0-Q1?", "why": "row 106 fixes biased + floating coupons across 'the shortlisted O-resistant candidates' "
     "but names no shortlist", "related_existing_open": None,
     "admissible_alternatives": ["R8-C01..C09 as proposed", "R8-C01..C09 plus named variants", "a reduced set"],
     "status": "TBD_OWNER"},
    {"id": "P4-OQ-03", "question": "Pre-registered coupon acceptance: resistance-rise threshold, AO / sputter "
     "recession limits and exposure durations (before any exposure).", "why": "R8: thresholds must be "
     "pre-registered via LOCK-1 / LOCK-2; none are proposed", "related_existing_open": None,
     "admissible_alternatives": ["frozen at LOCK-1", "frozen at LOCK-2 after Q0 bench metrology capability"],
     "status": "TBD_OWNER"},
    {"id": "P4-OQ-04", "question": "Authorize lawful acquisition (library / ILL / purchase) of species-resolved (N+, "
     "N2+, O+, O2+) sputtering-yield data for alloy and coating candidates not covered by open elemental "
     "compilations?", "why": "row 7 authorizes a listed set that does not include sputtering-yield sources; "
     "NIFS-DATA-23 covers monoatomic targets only", "related_existing_open": None,
     "admissible_alternatives": ["acquire", "measure on the ion-beam bench (TP-04) only", "both"],
     "status": "TBD_OWNER"},
    {"id": "P4-OQ-05", "question": "Collector coupons: bias polarity (ion-collecting negative bias as the collector "
     "runs, in addition to or instead of the row-106 electron-collecting / floating pair)?",
     "why": "A9.1 A9-03-collector sends collector candidates through the O / AO coupon programme; the collector's "
            "service is ion-collecting (analog, TK-71), which row 106 (anode) did not address",
     "related_existing_open": None,
     "admissible_alternatives": ["add a negative-bias set", "reuse the anode biased / floating set",
                                 "defer until P1 measures the collector bias"], "status": "TBD_OWNER"},
]


def decided_questions():
    """The five P4 questions as raised (text unchanged), now OWNER_DECIDED by A9.12 (A9.16 step 1)."""
    out = []
    for q in NEW_OPEN_QUESTIONS:
        dk, seq, code = APP.DECIDED_OWNER_QUESTIONS[q["id"]]
        out.append(dict(q, status="OWNER_DECIDED", status_when_raised="TBD_OWNER", answer=code, sequenced_no=seq,
                        decided_by=APP.cite(dk, q["id"])))
    return out


def check_existing_ids(pins):
    s = json.dumps(pins["AOL5"])
    for i in ("AOL-EX-02", "AOL-WC-02", "AOL-RC-01", "AOL-RC-02", "AOL-CX-07", "AOL-PM-02"):
        if f'"{i}"' not in s:
            raise BuildError(f"{i} missing from AO register v5")
    if "### ICP-21 " not in pins["ICD"]:
        raise BuildError("ICP-21 missing from the ICD")
    oq = {r["id"]: r for r in pins["OQ3"]["rows"]}
    if oq.get("OQ-A907-05", {}).get("status") != "OPEN":
        raise BuildError("OQ-A907-05 not OPEN in state v3")
    for q in NEW_OPEN_QUESTIONS:
        if q["id"] in oq:
            raise BuildError(f"{q['id']} collides with an existing question id")
    rows = {r["row"]: r for r in pins["M16V3"]["rows"]}
    for n, key in ((18, "icp_neutralizer_head"), (20, "h1_anode_material"), (21, "h1_anode_heat_path")):
        if rows.get(n, {}).get("key") != key:
            raise BuildError(f"M16 v3 row {n} is not {key}")
    if "no new arbitrary anode temperature limit" not in pins["A92_MD"].replace("\n", " ") and \
            "No new arbitrary anode temperature limit" not in pins["A92_MD"]:
        raise BuildError("A9.2 verbatim text drifted")
    if "P4 — anode/materials" not in pins["A96_MD"]:
        raise BuildError("A9.6 verbatim sec. 10 P4 heading missing")


def build_owner_answers_applied(pins):
    A = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
    out = []
    for row, how in ((86, "IT-07 / IT-08; CR-01 margin for ICP-module materials incl. the collector"),
                     (87, "IT-07; CR-01 rule; no anode temperature target set"),
                     (106, "IT-06 / IT-14; TP-02 biased + floating; FINAL_ANODE_MATERIAL OPEN"),
                     (132, "IT-15; CR-03 / TP-03 dedicated AO source; NO_ATOMIC_O label"),
                     (134, "IT-16; TP-04 witness holders exchangeable"),
                     (7, "source acquisition limited to lawful routes; P4-OQ-04 asks for items outside the list"),
                     (94, "analog only: graphite not a flight keeper baseline for O/AO exposure; CAND-09 stays a "
                          "reference coupon (R8), no selection")):
        a = owner_answer(pins, row)
        out.append({"decision": f"{A} row {row}", "covers_ids": a["covers_ids"],
                    "owner_answer_verbatim": a["owner_answer_verbatim"], "how_applied": how})
    d92 = pins["A92"]["decisions"]
    for k, how in (("anode_316L", "IT-01 / IT-06; CAND-01 owner status; Pareto caveat"),
                   ("anode_approach", "IT-03; CR-01 rule; ID-01 / ID-02 (thermal-design-first link to P3)"),
                   ("icp_coupled_thermal", "IT-04; collector CR-01 forced INCOMPLETE_EVIDENCE")):
        out.append({"decision": f"{PINS['A92'][0]} decisions.{k}", "covers_ids": [k],
                    "owner_answer_verbatim": d92[k] if isinstance(d92[k], str) else json.dumps(d92[k]),
                    "how_applied": how})
    out.append({"decision": f"{PINS['A91'][0]} decisions.A9-03-collector", "covers_ids": ["A9-03-collector"],
                "owner_answer_verbatim": pins["A91"]["decisions"]["A9-03-collector"],
                "how_applied": "IT-05 / IT-06; APP-COLLECTOR rows; P4-OQ-05"})
    out.append({"decision": f"{PINS['A96'][0]} summary.fixed_statuses + sec. 10 (P4)",
                "covers_ids": ["fo_a9_6_p4_anode_materials"],
                "owner_answer_verbatim": json.dumps(pins["A96"]["summary"]["fixed_statuses"], sort_keys=True),
                "how_applied": "fixed_statuses block; criteria list = sec. 10 list; no final selection"})
    for row in APP.owner_answers_applied_rows():
        row["owner_answer_verbatim"] = verbatim_section(pins, row["kind"], row["sequenced_no"], row["question_id"])
        out.append(row)
    return out


def verbatim_section(pins, kind, seq, qid):
    """The owner's verbatim answer text for one question, cut from the pinned verbatim .md (fails if absent)."""
    md = pins[kind.replace(".", "") + "_MD"]
    if kind == "A9.15":
        i = md.find("RFP-COMPLIANT PROPELLANT POLICY\n")
        if i < 0:
            raise BuildError("A9.15 verbatim policy text missing")
        return md[i:].strip()
    m = re.search(r"^\d+\. " + re.escape(seq) + r" \u2014 " + re.escape(qid) + r" \u2014 .*?^Decision: [^\n]*",
                  md, re.S | re.M)
    if m is None:
        raise BuildError(f"{kind} {seq} {qid}: verbatim section not found")
    return m.group(0).strip()


def build_m16_impact(pins):
    rows = {r["row"]: r for r in pins["M16V3"]["rows"]}
    out = []
    for n, how in ((20, "candidate-material comparison framework, gate matrix and coupon test plan now exist "
                        "(software / documentation only); A9H-ANODE-01 stays a design blocker"),
                   (21, "interface ID-01 / ID-02 to the P3 framework defined; A9H-ANODE-02 stays a design blocker"),
                   (18, "APP-COLLECTOR rows for ICP-21 collector material; material OPEN")):
        out.append({"m16_row": n, "key": rows[n]["key"], "how_touched": how,
                    "readiness_change": "NONE - no row becomes READY / VERIFIED; framework implementation is not "
                                        "material evidence (A9.6 sec. 16)"})
    return out


def q0_disposition(cid):
    """A9.12 P4-OQ-02 disposition of one P4 candidate (owner Q0 matrix / reserve / not listed)."""
    for e in RULES.Q0_MATRIX:
        if e[6] == cid:
            d = {"q0_id": e[0], "role": e[3], "r8_coupon": e[1], "material": e[2]}
            if e[4] == "exact_grade":
                d["admission"] = "NOT_ADMITTED_GRADE_TBD (grade declared before admission)"
            elif e[4] == "availability":
                d["admission"] = "NOT_ADMITTED_AVAILABILITY_TBD (only if readily available)"
            elif e[4] == "coating_system_and_substrate":
                d["admission"] = "NOT_ADMITTED_COATING_SYSTEM_TBD (exact coating system + substrate)"
            elif e[5]:
                d["admission"] = ("NOT_ADMITTED_COATING_RECORD_INCOMPLETE (composition, thickness, deposition "
                                  "process, substrate, surface preparation, lot / process provenance)")
            else:
                d["admission"] = "Q0_LISTED (no declaration outstanding; lot / heat certificate per TP-09)"
            return d
    for e in RULES.GENERIC_GRADE_REFUSED:
        if e[3] == cid:
            return {"q0_id": e[0], "role": "NOT_ADMITTED", "material": e[2],
                    "admission": "NOT_ADMITTED_EXACT_GRADE_REQUIRED (no generic Hastelloy)"}
    for e in RULES.RESERVE:
        if e[2] == cid:
            return {"q0_id": e[0], "role": "RESERVE", "material": e[1],
                    "admission": "RESERVE_ONLY_NOT_IN_BASELINE_CAMPAIGN (specific hypothesis / need before "
                                 "activation)"}
    return {"q0_id": None, "role": "NOT_IN_OWNER_Q0_MATRIX", "material": None,
            "admission": "NOT_IN_OWNER_Q0_MATRIX (no owner disposition; not added)"}


def _refusal(fn):
    """Run one rule on the REGISTERED inputs; the expected outcome today is a fail-closed refusal (recorded)."""
    try:
        out = fn()
    except RULES.RuleRefusal as e:
        return {"status": e.code, "reason": str(e)}
    raise BuildError(f"A9.16 rule evaluated on unregistered inputs: fail-closed rule broken ({out})")


def a9_16_owner_rules():
    """A9.16 step 1 rule record: owner forms, registration slots and the rules evaluated on today's registered
    inputs (every evaluation that needs a deferred / TBD input refuses; the refusal is the deliverable)."""
    q0 = [{"q0_id": e[0], "r8_coupon": e[1], "material": e[2], "role": e[3], "declaration_needed": e[4],
           "coating_record_required": e[5], "candidate": e[6],
           "registered_admission": _refusal(lambda e=e: RULES.q0_admission(e[0], None)) if (e[4] or e[5]) else
           {"status": "Q0_LISTED", "reason": "no declaration outstanding"}} for e in RULES.Q0_MATRIX]
    return {
        "rules_module": APP.RULES_REL, "test": APP.TEST_REL, "applied": A916_DATE,
        "rule": "pure fail-closed functions; owner forms only as given; deferred numbers / declarations are "
                "registration slots (NOT_EVALUATED_* / NOT_ADMITTED_* / INCOMPLETE_EVIDENCE); no selection; never PASS",
        "staged_validation": {"stages": VALIDATION_STAGES, "stage_1_conditions": list(RULES.STAGE_1_CONDITIONS),
                              "stage_1_metrics": list(RULES.STAGE_1_METRICS),
                              "stage_2_environment": list(RULES.STAGE_2_ENVIRONMENT),
                              "never_validation": list(RULES.NON_VALIDATION_BASES),
                              "cr01_gate_stages": list(SCR.T_VALIDATED_GATE_STAGES),
                              "registered_evaluation": _refusal(lambda: RULES.validation_stage_record(
                                  {"basis": RULES.STAGE_1, "material": "any Q0 entry", "source": "none yet",
                                   "preregistered_acceptance": "TBD", "T_limit_K": None})),
                              "decision": APP.cite("A9.12", "P4-OQ-01")},
        "q0_matrix": {"entries": q0,
                      "generic_grade_refused": [{"q0_id": e[0], "material": e[2], "candidate": e[3],
                                                 "registered_admission": _refusal(lambda e=e: RULES.q0_entry(e[0]))}
                                                for e in RULES.GENERIC_GRADE_REFUSED],
                      "reserve": [{"id": e[0], "material": e[1], "candidate": e[2],
                                   "registered_activation": _refusal(lambda e=e: RULES.reserve_activation(e[0]))}
                                  for e in RULES.RESERVE],
                      "not_in_owner_matrix": [c[0] for c in CANDIDATES
                                              if q0_disposition(c[0])["role"] == "NOT_IN_OWNER_Q0_MATRIX"],
                      "coating_record_fields": list(RULES.COATING_RECORD_FIELDS),
                      "q1_rule": "only Q0 survivors meeting the pre-registered (LOCK-2) screening criteria "
                                 "(p4_a9_16_rules.q1_admission)",
                      "decision": APP.cite("A9.12", "P4-OQ-02")},
        "lock2": {"metrology_slots": list(RULES.METROLOGY_SLOTS),
                  "commissioning_articles": list(RULES.COMMISSIONING_ARTICLES),
                  "threshold_slots": list(RULES.LOCK2_THRESHOLD_SLOTS),
                  "threshold_metrology": RULES.THRESHOLD_METROLOGY,
                  "registered_commissioning": _refusal(lambda: RULES.metrology_commissioning(None)),
                  "registered_freeze": _refusal(lambda: RULES.lock2_freeze(None, None)),
                  "inadequate_metrology": "NOT_EVALUATED_METROLOGY (criterion never widened)",
                  "decision": APP.cite("A9.12", "P4-OQ-03")},
        "sputter_data": {"acquisition_species": list(RULES.ACQUISITION_SPECIES),
                         "lawful_routes": list(RULES.LAWFUL_ROUTES),
                         "literature_uses": list(RULES.LITERATURE_USES),
                         "candidate_specific_evidence": "PROJECT_ION_BEAM_MEASUREMENT of the down-selected candidate",
                         "elemental_substitution": "refused for alloys / coatings without a registered NOT_MATERIAL "
                                                   "assessment; then an explicit proxy for literature uses only",
                         "acquired_records": [], "project_measurements": [],
                         "decision": APP.cite("A9.12", "P4-OQ-04")},
        "collector_coupons": {"sets": list(RULES.COLLECTOR_SETS), "polarity": RULES.COLLECTOR_POLARITY,
                              "bias_magnitude": "TBD - from the measured P1 collector envelope + plasma / sheath "
                                                "evidence (ID-06, IT-19)",
                              "registered_evaluation": _refusal(lambda: RULES.collector_coupon_exposure(
                                  {"set": "NEGATIVE_BIAS_ION_COLLECTING", "polarity": "NEGATIVE",
                                   "acceptance_bearing": True, "p1_complete": False})),
                              "pre_p1_biased_exposure": "ENGINEERING_ONLY_FIXTURE_PROCESS_VERIFICATION",
                              "decision": APP.cite("A9.12", "P4-OQ-05")},
        "app_filter": {"placement": RULES.FILTER_PLACEMENT, "baseline": RULES.FILTER_BASELINE,
                       "tests": list(RULES.FILTER_TESTS), "criteria": list(_FILTER_CRITERIA),
                       "catalytic_variant": {"label": RULES.FILTER_CATALYTIC_VARIANT,
                                             "requires_own": list(RULES.CATALYTIC_VARIANT_REQUIREMENTS)},
                       "acceptance_slots": list(RULES.FILTER_ACCEPTANCE_SLOTS),
                       "registered_acceptance": _refusal(lambda: RULES.filter_acceptance(None)),
                       "candidates": "TBD_AFTER_EVIDENCE - no filter material defined (F2-IF-08); none invented",
                       "decision": APP.cite("A9.13", "F2-OQ-04")},
        "a9_15_review": {"result": "no text in P4 restricts Xe to a C1 contingency; Xe+ retained in CR-04 / TP-04 as an "
                                   "RFP-required propellant species; ICP gas-mode baseline unchanged",
                         "decision": APP.cite("A9.15", "RFP-COMPLIANT PROPELLANT POLICY")},
        "out_of_lane": [{"path": p, "rules": r} for p, r in APP.OUT_OF_LANE],
    }


def build_doc(pins):
    check_existing_ids(pins)
    fixed = build_fixed_statuses(pins)
    h2_val = h2_anode_context(pins)
    props = build_property_records()
    links = build_evidence_links(pins)
    reqs = build_requirements()
    matrix, states = run_screening(reqs, props, fixed)
    finals = {app: SCR.final_material_status(states) for app in APPLICATIONS}
    candidates = []
    r8m = {c["material"]: c for c in pins["R8"]["candidate_matrix"]}
    r8c = {c["id"]: c for c in pins["R8"]["proposed_coupon_candidates"]["items"]}
    for cid, name, fam, coupon, mrow in CANDIDATES:
        if mrow not in r8m:
            raise BuildError(f"{cid}: R8 matrix row {mrow!r} missing")
        if coupon is not None and coupon not in r8c:
            raise BuildError(f"{cid}: R8 coupon {coupon} missing")
        owner = {}
        if cid == "CAND-01":
            owner = {"APP-ANODE": "REJECTED_AS_CURRENT_BASELINE for the flight / design-representative anode; "
                                  "ALLOWED_ENGINEERING_ONLY (engineering / shakedown, coupon, low-temperature "
                                  "development) - A9.2 anode_316L, row 106",
                     "APP-COLLECTOR": "ALLOWED_ENGINEERING_ONLY for Ar engineering reproduction; flight collector "
                                      "material not frozen - A9.1 A9-03-collector"}
        populated = any(p["candidate"] == cid for p in props)
        candidates.append({
            "id": cid, "name": name, "family": fam, "r8_coupon_id": coupon,
            "r8_coupon_role": r8c[coupon]["role"] if coupon else None,
            "r8_matrix_row": mrow, "r8_matrix_status_research_only": r8m[mrow]["status"],
            "origin": "repository evidence (web track R8)",
            "row_population": "DATASHEET_BULK_PROPERTIES_ONLY" if populated else "UNPOPULATED",
            "owner_status": owner,
            "note": ("A9.2: not selected merely for melting point" if cid in ("CAND-05", "CAND-08", "CAND-10")
                     else None),
            "q0_disposition": q0_disposition(cid),
        })
    doc = {
        "schema": "p4_anode_materials_v1", "id": "p4_anode_materials_v1",
        "title": "P4 anode / collector materials framework (A9.6 sec. 10; A9.2 sec. 3-4)",
        "lane": LANE, "trigger": TRIGGER, "date": DATE, "base_commit": BASE_COMMIT,
        "generated_by": SCRIPT_REL, "screening_module": SCREEN_REL, "companion_document": f"{LANE_REL}/{MD_NAME}",
        "test": TEST_REL,
        "status": "FRAMEWORK_IMPLEMENTED - NO MATERIAL SELECTED; every gate INCOMPLETE_EVIDENCE; owner decisions "
                  "A9.12 P4-OQ-01..05 and A9.13 F2-OQ-04 APPLIED (A9.16 step 1)",
        "a9_16_step": {"date": A916_DATE, "decisions": [APP.DEC[k][0] for k in APP.ORDER]},
        "what_this_is_not": ["a material selection or ranking", "a weighted score", "a thermal result or an anode / "
                             "collector temperature", "a life prediction", "a PASS of any kind",
                             "a procurement or purchase", "an owner decision (the A9.12 / A9.13 decisions are "
                             "applied as fail-closed rules; every deferred number stays a registration slot)"],
        "fixed_statuses": fixed,
        "a9_status": pins["A92"]["decisions"]["a9_10_statuses"],
        "pins": {k: {"path": v[0], "sha256": v[1], "role": v[2]} for k, v in sorted(PINS.items())},
        "never_pinned": list(NEVER_PINNED), "merged_cross_lane": xlane_report(None),
        "vocabulary": {"gate_outcomes": list(SCR.GATE_OUTCOMES),
                       "candidate_screening_states": list(SCR.CANDIDATE_SCREENING_STATES),
                       "never_emitted_as_status": ", ".join(SCR.FORBIDDEN_WORDS), "quantity_types": list(QUANTITY_TYPES),
                       "item_statuses": list(ITEM_STATUSES), "freeze_points": list(FREEZE_POINTS)},
        "screening_rules": [
            "a hard gate is applied only when both the requirement and the property value are evidenced; otherwise "
            "INCOMPLETE_EVIDENCE",
            "a property whose applicability domain does not cover the requirement domain gives OUT_OF_DOMAIN "
            "(distinct from a violation)",
            "CR-01 is INCOMPLETE_EVIDENCE while the thermal closure of the application is UNRESOLVED",
            "CR-01 admits a T_validated_continuous record only at validation stage 2 or 3 (A9.12 P4-OQ-01)",
            "APP-FILTER (A9.13 F2-OQ-04) has no candidate set yet: requirements listed, no gate cell generated",
            "no weighted scalar; no ranking; a satisfied gate is GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN, never PASS",
            "final material OPEN for every application (final_material_status)",
            "synthetic evidence refused; never mixed with published / measured records",
            "units must match exactly (no silent conversion); missing fields raise",
        ],
        "applications": APPLICATIONS, "criteria": CRITERIA, "candidates": candidates,
        "requirements": reqs,
        "items": build_items(pins, h2_val),
        "property_records": props, "evidence_links": links,
        "source_register": build_source_register(pins),
        "gate_matrix": matrix, "candidate_screening_states": states,
        "final_material_status": finals,
        "evidence_coverage": build_coverage(props, links),
        "pareto_views": build_pareto(props),
        "test_plan": {"tests": TEST_PLAN, "qualification_stages": QUAL_STAGES,
                      "validation_stages": VALIDATION_STAGES},
        "interface_demands": [dict({"id": i, "direction": d, "counterpart": c, "content": t, "used_for": u,
                                    "status": s, "units": un, "xref": [xref(p) for p in xr]},
                                   **({"a9_16_note": A9_16_IFD_NOTES[i]} if i in A9_16_IFD_NOTES else {}))
                              for (i, d, c, t, u, s, un, xr) in INTERFACE_DEMANDS],
        "owner_answers_applied": build_owner_answers_applied(pins),
        "open_owner_questions": decided_questions(),
        "a9_16_owner_rules": a9_16_owner_rules(),
        "historical_reuse": [{"path": v[0], "sha256": v[1], "use": v[2]} for _k, v in sorted(PINS.items())],
        "m16_impact": build_m16_impact(pins),
        "findings": [
            f"no candidate has gate-admissible evidence for any criterion; all {len(matrix)} gate cells are "
            "INCOMPLETE_EVIDENCE (requirements TBD / thermal closures UNRESOLVED)",
            "bulk datasheet properties populated only for 316L, INCONEL 600 and INCONEL 601; every other row is "
            "UNPOPULATED apart from qualitative R8 evidence",
            "Cleveland-Cliffs 316/316L bulletin gives a melting range of 1371-1399 degC (PR-005); the H2 A9 "
            "revisions quote about 1375-1400 degC 'from memory - verify' (not edited here; for the consolidated "
            "verification)",
            f"H2 A9 uncoupled anode sensitivity (not below {h2_val} degC) is context only; it is never used as "
            "T_operating while ANODE_THERMAL_CLOSURE is UNRESOLVED",
            "sputtering: no yield value is carried; NIFS-DATA-23 is located (elemental targets, graphical) but not "
            "digitized",
            "A9.16 step 1: P4-OQ-01..05 decided (A9.12) and applied - staged validation, owner Q0 matrix, LOCK-2 "
            "after metrology, sputter data BOTH, collector negative-bias + floating; APP-FILTER added (A9.13 "
            "F2-OQ-04); every deferred number / grade / coating system / bias magnitude / filter acceptance is a "
            "registration slot that refuses today",
        ],
    }
    SCR.assert_no_forbidden_status(doc)
    return doc


# ------------------------------------------------------------------------------------------------ markdown
def md_table(headers, rows):
    esc = lambda x: ("-" if x is None else str(x)).replace("|", "/").replace("\n", " ")
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def render_md(doc):
    L = [f"# {doc['title']}", "",
         f"Generated by `{doc['generated_by']}` from `{JSON_NAME}` (do not edit by hand). Lane `{doc['lane']}`, trigger "
         f"`{doc['trigger']}`, base `{doc['base_commit'][:7]}`, {doc['date']}.", "",
         f"**Status: {doc['status']}.**", "", "This is not: " + "; ".join(doc["what_this_is_not"]) + ".", "",
         "## Fixed statuses", "", md_table(["item", "status", "source"],
                                           [(k, v["status"], v["source"]) for k, v in doc["fixed_statuses"].items()]),
         "", "## Screening rules", ""] + [f"- {r}" for r in doc["screening_rules"]] + [
        "", "## (a) Items", "",
        md_table(["id", "item", "value", "units", "basis", "source", "evidence class", "status", "freeze"],
                 [(i["id"], i["item"], i["value"], i["units"], i["basis"], i["source"], i["evidence_class"],
                   i["status"], i["freeze_point"]) for i in doc["items"]]),
        "", "## Applications", "",
        md_table(["id", "name", "thermal status", "service"],
                 [(k, v["name"], doc["fixed_statuses"][v["thermal_status_key"]]["status"], v["service"])
                  for k, v in doc["applications"].items()]),
        "", "## Criteria", "",
        md_table(["id", "criterion", "property", "unit", "gate kind", "rule"],
                 [(c["id"], c["name"], c["property"], c["unit_si"], c["kind"], c["rule"]) for c in doc["criteria"]]),
        "", "## Candidates (no selection; order is the R8 order, not a ranking)", "",
        md_table(["id", "material", "family", "R8 coupon", "R8 status (research only)", "rows", "owner status",
                  "Q0 disposition (A9.12 P4-OQ-02)"],
                 [(c["id"], c["name"], c["family"], c["r8_coupon_id"], c["r8_matrix_status_research_only"],
                   c["row_population"], "; ".join(f"{k}: {v}" for k, v in c["owner_status"].items()) or c["note"],
                   f"{c['q0_disposition']['q0_id'] or '-'} {c['q0_disposition']['role']}: "
                   f"{c['q0_disposition']['admission']}")
                  for c in doc["candidates"]]),
        "", "## Requirements (per criterion and application)", "",
        md_table(["id", "criterion", "application", "value", "unit", "status", "TBD"],
                 [(r["id"], r["criterion"], r["application"], r["value"], r["unit"], r["status"], r["tbd"])
                  for r in doc["requirements"]]),
        "", "## Property records (datasheet extraction, this lane)", "",
        md_table(["id", "cand", "property", "reported", "SI", "T (degC)", "source", "locator", "verbatim row",
                  "class", "gate-admissible"],
                 [(p["id"], p["candidate"], p["property"], f"{p['value_reported']} {p['unit_reported']}",
                   f"{p['value_si']} {p['unit_si']}" if p["value_si"] is not None else "-",
                   p["condition"]["temperature_C"], p["source_id"], p["locator"], p["verbatim_row"],
                   p["quantity_type"], f"{p['admissible_for_gate']} ({p['admissibility_reason']})")
                  for p in doc["property_records"]]),
        "", "## Qualitative evidence links (copied from pinned inputs)", "",
        md_table(["id", "candidates", "criterion", "source", "locator", "result", "class", "gate-admissible"],
                 [(e["id"], ", ".join(e["candidates"]), e["criterion"], e["source_id"], e["locator"], e["result"],
                   e["evidence_class"], f"{e['admissible_for_gate']} ({e['admissibility_reason']})")
                  for e in doc["evidence_links"]]),
        "", "## Gate matrix summary", ""]
    for app in doc["applications"]:
        L.append(f"### {app}")
        L.append("")
        crits = [c["id"] for c in doc["criteria"] if c["kind"] is not None and app in c["applies_to"]]
        if not any(m["application"] == app for m in doc["gate_matrix"]):
            L += [f"No gate cell: {doc['applications'][app].get('candidate_scope', 'no candidate')}. Criteria "
                  f"{', '.join(crits)}; requirements all TBD (see the requirements table).", "",
                  f"Final material ({app}): **{doc['final_material_status'][app]}**.", ""]
            continue
        rows = []
        for c in doc["candidates"]:
            cells = {m["criterion"]: m["outcome"] for m in doc["gate_matrix"]
                     if m["application"] == app and m["candidate"] == c["id"]}
            rows.append([c["id"]] + [cells[x] for x in crits] +
                        [doc["candidate_screening_states"][f"{app}|{c['id']}"]])
        L += [md_table(["candidate"] + crits + ["screening state"], rows), "",
              f"Final material ({app}): **{doc['final_material_status'][app]}**.", ""]
    L += ["## Pareto / table views (INFORMATIONAL_NOT_A_SELECTION)", ""]
    for v in doc["pareto_views"]:
        L += [f"### {v['id']}: " + ", ".join(f"{k} ({s})" for k, s in v["objectives"].items()), "",
              md_table(["candidate"] + list(v["objectives"]) + ["non-dominated"],
                       [[c] + [v["values"][c][o] for o in v["objectives"]] + [c in v["non_dominated"]]
                        for c in v["compared"]]), "",
              f"Not comparable (incomplete evidence): {len(v['not_comparable'])} candidates.", ""]
        L += [f"- {x}" for x in v["caveats"]] + [""]
    L += ["## Coupon / qualification test plan", "",
          md_table(["id", "criterion", "populates", "measure", "instruments", "atmosphere", "acceptance", "links"],
                   [(t["id"], t["criterion"], t["populates"], t["measure"], t["instruments"],
                     t["atmosphere_sequence"], t["acceptance"], ", ".join(t["register_links"]))
                    for t in doc["test_plan"]["tests"]]), "",
          md_table(["stage", "name", "tests"], [(q["id"], q["name"], ", ".join(q["tests"]))
                                                for q in doc["test_plan"]["qualification_stages"]]), "",
          "### Validation stages for T_validated,continuous (A9.12 P4-OQ-01)", "",
          md_table(["id", "stage", "qualification stages", "result", "usable for"],
                   [(v["id"], v["stage"], ", ".join(v["qual_stages"]), v["result"], ", ".join(v["usable_for"]))
                    for v in doc["test_plan"]["validation_stages"]]), "",
          "## (b) Interface demands", "",
          md_table(["id", "direction", "counterpart", "content", "used for", "units", "status", "pairs",
                    "A9.16 note"],
                   [(i["id"], i["direction"], i["counterpart"], i["content"], i["used_for"], i["units"], i["status"],
                     ", ".join(x["pair"] + " -> " + x["counterpart"] for x in i["xref"]) or "-",
                     i.get("a9_16_note"))
                    for i in doc["interface_demands"]]), "",
          "### Merged cross-lane references", "", doc["merged_cross_lane"]["rule"], "",
          md_table(["package", "path", "pairs", "ids cited", "check"],
                   [(k, v["path"], ", ".join(v["pairs"]) or "-", ", ".join(v["ids_cited"]) or "-", v["check"])
                    for k, v in doc["merged_cross_lane"]["packages"].items()]), "",
          "## (c) Owner answers applied", "",
          md_table(["decision", "covers", "verbatim", "how applied"],
                   [(o["decision"], ", ".join(o["covers_ids"]), o["owner_answer_verbatim"], o["how_applied"])
                    for o in doc["owner_answers_applied"]]), "",
          "## (d) Owner questions raised by this lane (now decided)", "",
          md_table(["id", "question", "why", "related existing", "admissible alternatives", "status", "answer",
                    "decided by"],
                   [(q["id"], q["question"], q["why"], q["related_existing_open"],
                     "; ".join(q["admissible_alternatives"]), q["status"], q["answer"], q["decided_by"])
                    for q in doc["open_owner_questions"]]), "",
          "## A9.16 step 1 owner rules (fail-closed; registered evaluations refuse today)", "",
          f"Rules module `{doc['a9_16_owner_rules']['rules_module']}`, test `{doc['a9_16_owner_rules']['test']}`. "
          + doc["a9_16_owner_rules"]["rule"] + ".", "",
          "### Q0 matrix (A9.12 P4-OQ-02)", "",
          md_table(["Q0 id", "R8", "material", "role", "declaration needed", "coating record", "candidate",
                    "registered admission"],
                   [(e["q0_id"], e["r8_coupon"], e["material"], e["role"], e["declaration_needed"],
                     e["coating_record_required"], e["candidate"], e["registered_admission"]["status"])
                    for e in doc["a9_16_owner_rules"]["q0_matrix"]["entries"]]), "",
          "Refused: " + "; ".join(f"{e['material']} ({e['registered_admission']['status']})" for e in
                                  doc["a9_16_owner_rules"]["q0_matrix"]["generic_grade_refused"]) + ". Reserve: " +
          "; ".join(f"{e['material']} ({e['registered_activation']['status']})" for e in
                    doc["a9_16_owner_rules"]["q0_matrix"]["reserve"]) + ". Not in the owner matrix: " +
          ", ".join(doc["a9_16_owner_rules"]["q0_matrix"]["not_in_owner_matrix"]) + ".", "",
          "### Registered evaluations", "",
          md_table(["rule", "registered evaluation", "decision"],
                   [("staged validation", doc["a9_16_owner_rules"]["staged_validation"]["registered_evaluation"]
                     ["status"], doc["a9_16_owner_rules"]["staged_validation"]["decision"]),
                    ("metrology commissioning", doc["a9_16_owner_rules"]["lock2"]["registered_commissioning"]
                     ["status"], doc["a9_16_owner_rules"]["lock2"]["decision"]),
                    ("LOCK-2 freeze", doc["a9_16_owner_rules"]["lock2"]["registered_freeze"]["status"],
                     doc["a9_16_owner_rules"]["lock2"]["decision"]),
                    ("collector coupon (acceptance-bearing, biased)",
                     doc["a9_16_owner_rules"]["collector_coupons"]["registered_evaluation"]["status"],
                     doc["a9_16_owner_rules"]["collector_coupons"]["decision"]),
                    ("APP-FILTER acceptance", doc["a9_16_owner_rules"]["app_filter"]["registered_acceptance"]
                     ["status"], doc["a9_16_owner_rules"]["app_filter"]["decision"])]), "",
          "### Out of lane (listed, not edited here)", "",
          md_table(["path", "rules"], [(o["path"], ", ".join(o["rules"]))
                                       for o in doc["a9_16_owner_rules"]["out_of_lane"]]), "",
          "## (e) Historical reuse (pinned, sha256)", "",
          md_table(["path", "sha256", "use"], [(h["path"], h["sha256"], h["use"]) for h in doc["historical_reuse"]]),
          "", "## (f) M16 impact", "",
          md_table(["row", "key", "how touched", "readiness change"],
                   [(m["m16_row"], m["key"], m["how_touched"], m["readiness_change"]) for m in doc["m16_impact"]]),
          "", "## Sources", ""]
    for s in doc["source_register"]["new_this_lane"]:
        L.append(f"- **{s['id']}**: {s['cite']}. {s['url']} (accessed {s['accessed']}; {s['access_level']}; PDF "
                 f"sha256 {s['pdf_sha256']}; {s['scope_note']})")
    for s in doc["source_register"]["reused_from_r8"]:
        L.append(f"- **{s['id']}** (via R8, {s['accessed']}): {s['cite']}. {s['url']} ({s['access']})")
    L += ["", "## Findings", ""] + [f"- {f}" for f in doc["findings"]] + [""]
    return "\n".join(L)


def render():
    pins = load_pins()
    doc = build_doc(pins)
    js = json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    return js, render_md(doc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the outputs are reproduced byte for byte")
    args = ap.parse_args(argv)
    js, md = render()
    outs = ((HERE / JSON_NAME, js), (HERE / MD_NAME, md))
    if args.check:
        bad = [p.name for p, t in outs if not p.exists() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("NOT REPRODUCED:", ", ".join(bad))
            return 1
        probs = xlane_check(json.loads(js))
        if probs:
            print("CROSS-LANE REFERENCES BROKEN:", "; ".join(probs))
            return 1
        print("OK: outputs reproduced")
        return 0
    for p, t in outs:
        p.write_text(t, encoding="utf-8")
    print("wrote", ", ".join(p.name for p, _ in outs))
    probs = xlane_check(json.loads(js))
    if probs:
        print("CROSS-LANE REFERENCES BROKEN (rebuild the counterpart, then this package):", "; ".join(probs))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
