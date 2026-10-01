#!/usr/bin/env python3
"""A9.7 F5 - H-1 freeze-candidate engineering-article definition (lane fo_a9_7_f5_h1_freeze_candidate).

Consolidates the verified H2 work (docs/hardware/h2/h2_1..h2_7 v1, docs/hardware/h2_a9_revisions/, the A9-03 ICD
IP-EXIT items, docs/experiments/hardware/, the P3 / P4 frameworks and mass/power v2) into one H-1 parameter table with
VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS per parameter. Every input is read-only and cited by path +
JSON pointer + sha256. Immutable inputs (owner decisions, H2 v1 deliverables, frozen P5 B(z) data) are PINNED: the
builder refuses to run when one of them has changed. Verified-but-revisable deliverables are CONSUMED: their sha256 at
build time is recorded, so `--check` reports drift.

What this is not: no Hall performance number (thrust, discharge current, efficiency, plasma state) is produced or
read - the credible Hall transport set is empty and P5-N2 v1 is INCONCLUSIVE, so no Hall response map has an admitted
domain; the withdrawn 0-D Hall model is not used; P5 geometry / B(z) are references for P5 only, never H-1 design
values; nothing is selected, ranked, declared a winner or a PASS; it is not wired into abep_sim/archengine.py.

Usage:
    python docs/hardware/h1_freeze_candidate/build_h1_freeze_candidate.py          # write JSON + MD
    python docs/hardware/h1_freeze_candidate/build_h1_freeze_candidate.py --check  # verify both files are current
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LANE_DIR = REPO / "docs" / "hardware" / "h1_freeze_candidate"
JSON_PATH = LANE_DIR / "h1_freeze_candidate_v1.json"
MD_PATH = LANE_DIR / "H1_FREEZE_CANDIDATE.md"
REL_SELF = "docs/hardware/h1_freeze_candidate/build_h1_freeze_candidate.py"
sys.path.insert(0, str(LANE_DIR))
import a9_16_h1 as A16  # noqa: E402  (A9.16 step 1 owner-decision application, integration lane)
import a9_19_h1 as A19  # noqa: E402  (A9.19 / A9.20 owner-decision application, design + experiments lane)
BASE_COMMIT = "1c9d7a648cd4ce739e587248693271e5115698e1"
DATE = "2026-10-01"

# --------------------------------------------------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------------------------------------------------
# Immutable inputs: owner decisions (immutable after commit), the verified H2 v1 deliverables (byte-identical by the
# A9-07 rule) and the frozen P5 B(z) digitization. A mismatch stops the build (fail closed).
PINS = {
    "A97_MD": ("docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md",
               "fb51328d6fe07a6eaf257ef9ef9592cb0c0039ae3e8cf04ef0420007c985b129"),
    "A97": ("docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json",
            "3199a670c901967ae4dca930022470b024cac14b263335da0adc3d423c37f372"),
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03"),
    "A92_MD": ("docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md",
               "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4"),
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"),
    "H21": ("docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json",
            "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d"),
    "H23": ("docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
            "f32b05bd03aad2a09a1d9b90ee5f9423e733e6ea4cb94814c92b500590d43a7b"),
    "H25": ("docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json",
            "68c5be61443d0ef1c7308c4aba265426137292dcf9363e57903e0a1f6c8bc083"),
    "H27": ("docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
            "d1813e153af37ebd45cb2ead964ead6c53c756d1a82f93ea89346a83168d0630"),
    # A9.16 step 1: owner decisions applied to this record (immutable decision files; verbatim .md governs)
    "A912": (A16.L.DECISIONS["A9.12"][0], A16.L.DECISIONS["A9.12"][1]),
    "A912_MD": (A16.L.LOADED["A9.12"]["md"], A16.L.LOADED["A9.12"]["md_sha256"]),
    "A914": (A16.L.DECISIONS["A9.14"][0], A16.L.DECISIONS["A9.14"][1]),
    "A914_MD": (A16.L.LOADED["A9.14"]["md"], A16.L.LOADED["A9.14"]["md_sha256"]),
    "A915": (A16.L.DECISIONS["A9.15"][0], A16.L.DECISIONS["A9.15"][1]),
    "A915_MD": (A16.L.LOADED["A9.15"]["md"], A16.L.LOADED["A9.15"]["md_sha256"]),
    # A9.19 / A9.20 (pinned in abep_sim/design/a9_19_architecture.py)
    "A919": (A19.A.DECISIONS["A9.19"]["json"], A19.A.DECISIONS["A9.19"]["json_sha256"]),
    "A919_MD": (A19.A.DECISIONS["A9.19"]["md"], A19.A.DECISIONS["A9.19"]["md_sha256"]),
    "A920": (A19.A.DECISIONS["A9.20"]["json"], A19.A.DECISIONS["A9.20"]["json_sha256"]),
    "A920_MD": (A19.A.DECISIONS["A9.20"]["md"], A19.A.DECISIONS["A9.20"]["md_sha256"]),
    "P5B16": ("hallthruster_bridge/bfield/p5_vacuum_Br_centerline_1p6kW.csv",
              "65216f4d713be929b9c59f101711301d933df7b2ae1ed3478b36aa3772926625"),
    "P5B30": ("hallthruster_bridge/bfield/p5_vacuum_Br_centerline_3p0kW.csv",
              "1f1cb42cdc9a2b40b527e8e0a8daf5d4559c460ba8e4342e4f488e4ce283efe2"),
}
# Verified deliverables that later consolidated verifications may repair: read-only, sha256 recorded at build time.
CONSUMED = {
    "A9REV": "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json",
    "ICD": "schemas/interfaces/icp_neutralizer_icd_v1.json",
    "HWREQ": "docs/experiments/hardware/hardware_requirements_v1.json",
    "P3": "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json",
    "P4": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
    "MP2": "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json",
    "M16": "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json",
    "OQ4": "docs/budgets/owner_decisions/owner_questions_state_v4.json",
    "OQ5": "docs/budgets/owner_decisions/owner_questions_state_v5.json",
    "PREREG": "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
    "ENS": "hallthruster_bridge/ensemble/transport_ensemble_v0.json",
    "VAL": "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json",
}
# Parallel A9.7 lanes: referenced only, never imported or read by this builder. Counterpart paths and record ids were
# resolved by the A9.7 cross-lane integration pass (consolidated verification round 1, STR-01 / INT-02); every lane
# below is merged on the execution branch.
PENDING_LANES = {
    "F0": ("fo_a9_7_f0_profiling", "docs/performance/PERFORMANCE_BASELINE_98fbbb9.json"),
    "F1": ("fo_a9_7_f1_intake_synthesis", "abep_sim/design/intake_synthesis.py (F1-ID-06; coupled through F4-ID-01)"),
    "F2": ("fo_a9_7_f2_filter_stage", "abep_sim/design/filter_stage.py (F2-IF-05; coupled through F4-ID-03/04)"),
    "F3": ("fo_a9_7_f3_compressor_synthesis", "abep_sim/design/compressor_synthesis.py (IFD-F3-06; coupled through "
                                              "F4-ID-05)"),
    "F4": ("fo_a9_7_f4_plenum_feed", "abep_sim/design/plenum_feed.py; docs/design_synthesis/f4_plenum/"
                                     "f4_plenum_feed_v1.json (F4-ID-07..09)"),
    "F6": ("fo_a9_7_f6_icp_geometry", "abep_sim/design/icp_geometry_synthesis.py (F6-IF-N01, N02, S03)"),
    "F7F8": ("fo_a9_7_f7_f8_coupled_optimizer",
             "abep_sim/design/architecture_optimizer.py (F78-ID-08, F78-ID-09)"),
    "F9": ("fo_a9_7_f9_freeze_candidate", "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json "
                                          "(F9-ID-05, F9-ID-11)"),
}

FREEZE_STATUSES = {
    "FREEZE_CANDIDATE": "owner-given decision, convention or rule that can enter the H-1 LOCK-1 design release as stated; "
                        "it is a candidate, not a frozen value (nothing is frozen by this lane)",
    "OPEN": "a value or window exists (derived / analog / sensitivity) but it is not yet a design value; the listed "
            "evidence moves it to FREEZE_CANDIDATE",
    "TBD_AFTER_EVIDENCE": "no admissible value; it needs measurement, FEMM / thermal analysis or sourced material data",
    "TBD_OWNER": "needs an owner decision (existing owner question cited where one exists)",
}
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "before-HI-S1", "after-evidence")
GROUPS = {
    "CH": "channel geometry",
    "AN": "anode geometry, material and heat path",
    "MC": "magnetic circuit geometry",
    "BZ": "B(z) target / profile",
    "CO": "coil operating envelope",
    "MA": "materials under investigation",
    "TH": "thermal rules and closures touching H-1",
    "IN": "inlet / plenum interface (HALL_INLET_Z0)",
    "EX": "exit plane IP-EXIT",
}
# A9.7 F5 'Freeze candidate' bullets (verbatim) -> parameter groups covering them
A97_F5_BULLETS = {
    "channel geometry;": ["CH"],
    "anode geometry;": ["AN"],
    "magnetic circuit geometry;": ["MC"],
    "B(z) target/profile;": ["BZ"],
    "coil operating envelope;": ["CO"],
    "materials under investigation;": ["MA", "AN"],
    "inlet/plenum interface;": ["IN"],
    "exit plane IP-EXIT.": ["EX"],
}
# A9.2 sec. 4 anode investigation list (verbatim bullets; the builder checks each against the pinned verbatim record)
A92_ANODE_INVESTIGATION = [
    ("AI-01", "stronger anode-to-backplate conduction;", "H-1 design (A9H-ANODE-02) + P3 conductance inputs (P3-IF-N07)"),
    ("AI-02", "anode support/feed-tube conduction;", "H-1 design + H2-3 feed-tube path (P4 ID-03)"),
    ("AI-03", "geometric heat spreading;", "H-1 design + P3"),
    ("AI-04", "radiative area;", "H-1 design + P3 radiosity enclosure (radiative_view_parametric_study)"),
    ("AI-05", "thermal coupling to the spacecraft/stand;", "P3 + spacecraft ICD (row 85 cases, not frozen)"),
    ("AI-06", "deposited discharge-power fraction;", "Phase-1 measurement (P3-IF-N01 / P1 temperatures); no Hall "
                                                     "closure may supply it (credible set empty)"),
    ("AI-07", "refractory/oxidation-resistant material candidates;", "P4 coupon programme (APP-ANODE, row 106)"),
    ("AI-08", "optional active cooling only if passive closure fails.", "variant only (mass_power v2 MPV2-N05)"),
]
PERFORMANCE_QUANTITIES = ("thrust T", "T - D_spacecraft", "discharge current I_d", "I_d,max,H1 (registered envelope)",
                          "anode / total efficiency", "specific impulse", "ionization fraction / plasma state",
                          "Hall-discharge power share actually drawn", "deposited anode / wall heat fractions",
                          "wall erosion rate / life")

_cache: dict = {}
_sha: dict = {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_of(key: str) -> str:
    return PINS[key][0] if key in PINS else CONSUMED[key]


def verify_pins() -> dict:
    out = {}
    for key, (rel, want) in PINS.items():
        p = REPO / rel
        if not p.is_file():
            raise SystemExit(f"REFUSED: pinned input missing: {rel}")
        got = _sha256(p)
        if got != want:
            raise SystemExit(f"REFUSED: pinned input changed: {rel} sha256 {got} != pinned {want}")
        out[key] = {"path": rel, "sha256": want}
    return out


def sha_of(key: str) -> str:
    if key not in _sha:
        p = REPO / path_of(key)
        if not p.is_file():
            raise SystemExit(f"REFUSED: input missing: {path_of(key)}")
        _sha[key] = _sha256(p)
    return _sha[key]


def load(key: str):
    if key not in _cache:
        p = REPO / path_of(key)
        _cache[key] = json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else p.read_text(encoding="utf-8")
    return _cache[key]


def resolve(doc, pointer: str):
    cur = doc
    if pointer in ("", "/"):
        return cur
    for tok in pointer.lstrip("/").split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(tok)]
        elif isinstance(cur, dict):
            if tok not in cur:
                raise KeyError(f"pointer {pointer}: missing {tok!r}")
            cur = cur[tok]
        else:
            raise KeyError(f"pointer {pointer}: cannot descend into {type(cur).__name__}")
    return cur


def get(key: str, pointer: str):
    return resolve(load(key), pointer)


def ref(key: str, pointer: str = "", note: str | None = None) -> dict:
    if pointer:
        resolve(load(key), pointer)  # the pointer must resolve (fail closed)
    r = {"path": path_of(key), "pointer": pointer or "/", "sha256": sha_of(key)}
    if note:
        r["note"] = note
    return r


def find(key: str, list_pointer: str, field: str, value) -> str:
    lst = get(key, list_pointer)
    hits = [i for i, x in enumerate(lst) if isinstance(x, dict) and x.get(field) == value]
    if len(hits) != 1:
        raise SystemExit(f"REFUSED: {path_of(key)}{list_pointer}: {field}={value!r} found {len(hits)} times")
    return f"{list_pointer}/{hits[0]}"


def ans(row: int) -> dict:
    return ref("ANS", find("ANS", "/answers", "row", row) + "/owner_answer_verbatim", note=f"owner row {row}")


def h21(pid: str, field: str = "value") -> str:
    return find("H21", "/design_parameters", "id", pid) + f"/{field}"


def rev(rid: str, sub: str = "/new/value") -> str:
    return find("A9REV", "/revision_register", "id", rid) + sub


def icd(iid: str, field: str = "status") -> str:
    return find("ICD", "/items", "id", iid) + f"/{field}"


def hwreq(rid: str, field: str = "status") -> str:
    return find("HWREQ", "/requirements", "id", rid) + f"/{field}"


def sig(x: float, n: int = 6) -> float:
    return float(f"{x:.{n}g}")


# --------------------------------------------------------------------------------------------------------------------
# parameter table
# --------------------------------------------------------------------------------------------------------------------
def is_tbd(v) -> bool:
    return isinstance(v, str) and v.startswith("TBD")


def P(rows: list, pid: str, name: str, value, *, units: str, tolerance, evidence_class, sources: list, basis: str,
      freeze_status: str, freeze_point: str, evidence_to_freeze: list | None = None, evidence_note: str | None = None,
      source_status: str | None = None, note: str | None = None) -> None:
    group = pid.split("-")[1]
    assert group in GROUPS, pid
    assert freeze_status in FREEZE_STATUSES, (pid, freeze_status)
    assert freeze_point in FREEZE_POINTS, (pid, freeze_point)
    assert sources, pid
    if is_tbd(value):
        assert evidence_class is None, f"{pid}: a TBD value carries no evidence class"
        assert freeze_status != "FREEZE_CANDIDATE", pid
    else:
        assert evidence_class in EVIDENCE_CLASSES, (pid, evidence_class)
    if freeze_status != "FREEZE_CANDIDATE":
        assert evidence_to_freeze, f"{pid}: evidence needed to reach FREEZE_CANDIDATE must be listed"
    row = {"id": pid, "group": group, "name": name, "value": value, "units": units, "tolerance": tolerance,
           "evidence_class": evidence_class}
    if evidence_note:
        row["evidence_note"] = evidence_note
    row.update({"source": sources, "basis": basis, "freeze_status": freeze_status, "freeze_point": freeze_point})
    if source_status:
        row["status_in_source"] = source_status
    row["evidence_to_freeze_candidate"] = evidence_to_freeze or []
    if note:
        row["note"] = note
    rows.append(row)


NO_TOL_WINDOW = "n/a (window, not a design point; the point tolerance is set with the design release)"
NO_TOL_RULE = "n/a (decision / rule)"
NO_TOL_ANCHOR = "n/a (value at the RP-1 calculation anchor, not a design point)"
FEMM = "FEMM-class axisymmetric magnetostatics of MC-1 with supplier B-H curves at the selected design point " \
       "(M16 row 10 blocking item)"
POINT = "owner selection of the channel design point (h, d_mean, L) inside the windows (M16 row 9 blocking item)"
COUPLED = "coupled H-1 / ICP thermal closure (A9.2 ICP_COUPLED_THERMAL; P3 framework inputs: ICP geometry, " \
          "view factors, conductances; >= 50 K + 20 % rule, row 86)"
PHASE1 = "Phase-1 H-1 measurement on the built article (N2 first; hardware pivot OD 2026-09-27): the xenon-derived " \
         "sizing rules are hypotheses for air species"


def build_parameters() -> list:
    rows: list = []
    h21_dp = lambda pid, f="value": ref("H21", h21(pid, f))  # noqa: E731
    rp1 = get("H21", "/assumed_inputs/rp1_geometry/value")

    # ---------------- CH channel geometry ----------------
    P(rows, "H1F-CH-01", "coordinate frame and channel datum planes",
      "z along the H-1 thrust axis; z = 0 at HALL_INLET_Z0 (anode / gas-distributor face); IP-EXIT at z = L",
      units="-", tolerance=NO_TOL_RULE, evidence_class="assumed", evidence_note="convention",
      sources=[ref("A91", "/decisions/A9-03-planes"), ref("ICD", icd("ICP-01", "status")), h21_dp("H21-09")],
      basis="A9.1 A9-03-planes; ICD ICP-01; H2-1 H21-09", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW")
    P(rows, "H1F-CH-02", "channel annulus area window A = pi h d_mean", get("H21", h21("H21-01")),
      units="cm^2", tolerance=NO_TOL_WINDOW, evidence_class="model-derived",
      evidence_note="xenon C_P* and j_d rules (DM2008 Eq. 4.6, GK2008 p. 337) bounded by the A5 power allocation; "
                    "transfer to N2/O/O2 is a hypothesis (engineering correlation outside its domain, level 6)",
      sources=[h21_dp("H21-01"), ref("H21", "/channel/area_window_rule"), ref("A9REV", rev("REV-12"))],
      basis="H2-1 H21-01 (intersection of A_CP and A_jd); A9-07 REV-12 nominal flow basis",
      freeze_status="OPEN", freeze_point="LOCK-1", source_status=get("H21", h21("H21-01", "status")),
      evidence_to_freeze=[POINT, FEMM, COUPLED, PHASE1,
                          "hall_discharge power share at the PPU boundary (H2-4 / mass_power v2 power slots)"])
    P(rows, "H1F-CH-03", "mean-diameter / width ratio window d_mean / h", get("H21", h21("H21-02")),
      units="-", tolerance=NO_TOL_WINDOW, evidence_class="measured",
      evidence_note="measured design dimensions of published analogs AN-Z70, AN-MASMI, AN-CAMILA, AN-ECHT; the window "
                    "is an analog envelope, never a Vyovrinda design value",
      sources=[h21_dp("H21-02"), ref("H21", "/channel/d_over_h_sources")],
      basis="H2-1 H21-02", freeze_status="OPEN", freeze_point="LOCK-1",
      source_status=get("H21", h21("H21-02", "status")), evidence_to_freeze=[POINT, FEMM])
    for pid, hid, nm in (("H1F-CH-04", "H21-03", "channel width h window"),
                         ("H1F-CH-05", "H21-04", "channel mean diameter d_mean window"),
                         ("H1F-CH-06", "H21-05", "channel outer diameter (d_mean + h) window"),
                         ("H1F-CH-07", "H21-06", "channel inner diameter (d_mean - h) window")):
        srcs = [h21_dp(hid)]
        note = None
        if hid == "H21-04":
            srcs.append(ref("A9REV", rev("REV-01")))
            note = ("the v1 central-cathode floor is removed (external C1, row 79, REV-01); the remaining floor is the "
                    "solid-core inner-coil build (H1F-MC-04), binding only under worst-case assumptions")
        if hid == "H21-06":
            srcs.append(ref("A9REV", rev("REV-02")))
        P(rows, pid, nm, get("H21", h21(hid)), units="mm", tolerance=NO_TOL_WINDOW, evidence_class="model-derived",
          sources=srcs, basis=f"H2-1 {hid} (corners of H1F-CH-02 x H1F-CH-03)", freeze_status="OPEN",
          freeze_point="LOCK-1", source_status=get("H21", h21(hid, "status")), evidence_to_freeze=[POINT, FEMM],
          note=note)
    P(rows, "H1F-CH-08", "channel length / width upper bound L/h <= 12", get("A9REV", rev("REV-08")),
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(75), ref("A9REV", rev("REV-08"))], basis="owner row 75 (H2-1 Q3)",
      freeze_status="FREEZE_CANDIDATE", freeze_point="NOW")
    P(rows, "H1F-CH-09", "channel length / width lower bound L/h", get("H21", h21("H21-07"))[0],
      units="-", tolerance=NO_TOL_WINDOW, evidence_class="model-derived",
      evidence_note="ECHT analog L/h 8.6 equals the lower end of the equal-n_e ionization-length rule (Z-70 L/h x "
                    "lambda_i(N2)/lambda_i(Xe)); a hypothesis for air species",
      sources=[h21_dp("H21-07"), ref("H21", "/channel/L_over_h_rules")],
      basis="H2-1 H21-07 lower end", freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[PHASE1 + " (pre-S1 adjustable-anode insert data, row 75)", POINT])
    P(rows, "H1F-CH-10", "channel length L window (HALL_INLET_Z0 to IP-EXIT)", get("H21", h21("H21-08")),
      units="mm", tolerance=NO_TOL_WINDOW, evidence_class="model-derived",
      sources=[h21_dp("H21-08")], basis="H2-1 H21-08 = L/h window x h window", freeze_status="OPEN",
      freeze_point="before-HI-S1", source_status=get("H21", h21("H21-08", "status")),
      evidence_to_freeze=[POINT, PHASE1, "final anode position frozen before score-bearing S1 (row 75, GD-02)"])
    P(rows, "H1F-CH-11", "channel design point (h, d_mean, L)",
      "TBD - requires owner selection inside H1F-CH-02..CH-10 after FEMM and the coupled thermal closure",
      units="mm", tolerance="TBD", evidence_class=None,
      sources=[ref("M16", find("M16", "/rows", "row", 9) + "/blocking_item"), h21_dp("H21-01")],
      basis="M16 v4 row 9 blocking item; no Hall performance criterion is available (credible set empty)",
      freeze_status="TBD_OWNER", freeze_point="LOCK-1",
      evidence_to_freeze=[FEMM + " at candidate points (new owner question F5-OQ-01)",
                          COUPLED, "owner selection on non-performance criteria (new owner question F5-OQ-02)"],
      note=f"RP-1 (d_mean {rp1['d_mean_mm']} mm, h {rp1['h_mm']} mm, L/h {rp1['L_over_h']}) is the H2-1 coil-sizing "
           "calculation anchor, explicitly NOT a design selection")
    P(rows, "H1F-CH-12", "channel neutral-density sizing flow and characterization range",
      {"nominal_sizing_flow_mg_s_approx": get("A9REV", rev("REV-12"))["nominal_flow_mg_s_approx"],
       "operability_thermal_characterization_mg_s": [0.38, 3.2]},
      units="mg/s (delivered atmospheric flow)", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(73), ref("A9REV", rev("REV-12"))],
      basis="owner row 73: nominal sizing ~1.3 mg/s; characterization ~0.38-3.2 mg/s; no flight-qualification claim "
            "before measurement", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW",
      note="sizing basis and test range only; the neutral density at this flow (REV-12) uses a xenon-derived rule")
    P(rows, "H1F-CH-13", "one design-representative wall configuration; alternative-grade sector inserts engineering-only",
      "one wall configuration frozen before S1; engineering-only sector studies before the score-bearing freeze",
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(135), ref("PREREG", find("PREREG", "/gate_deadlines", "id", "GD-03"))],
      basis="owner row 135; prereg framework GD-03", freeze_status="FREEZE_CANDIDATE", freeze_point="before-HI-S1")

    # ---------------- AN anode ----------------
    P(rows, "H1F-AN-01", "anode / gas-distributor face position", "z = 0 = HALL_INLET_Z0 (fixed for all score-bearing runs)",
      units="-", tolerance=NO_TOL_RULE, evidence_class="assumed", evidence_note="convention",
      sources=[h21_dp("H21-09"), ref("HWREQ", hwreq("HW-H1-06", "text"))], basis="H2-1 H21-09; HW-H1-06",
      freeze_status="FREEZE_CANDIDATE", freeze_point="NOW")
    P(rows, "H1F-AN-02", "adjustable-anode development insert", get("A9REV", rev("REV-09")),
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(75), ref("A9REV", rev("REV-09"))], basis="owner row 75: allowed only before score-bearing S1",
      freeze_status="FREEZE_CANDIDATE", freeze_point="NOW",
      note="any L change after S1 creates H-1' (HW-H1-02, row 83)")
    P(rows, "H1F-AN-03", "final anode position / geometry (annulus width, mean diameter, distributor depth, joints)",
      "TBD - requires the channel design point and pre-S1 development data; frozen before score-bearing S1",
      units="mm", tolerance="TBD", evidence_class=None,
      sources=[ref("H21", "/interface_demands/15/value"), ref("H21", "/interface_demands/18/value"),
               ref("P4", find("P4", "/interface_demands", "id", "ID-03") + "/status")],
      basis="row 75 / GD-02; H2-1 interface demand to H2-3 (annulus = channel h, d_mean); P4 ID-03 PENDING",
      freeze_status="TBD_AFTER_EVIDENCE", freeze_point="before-HI-S1",
      evidence_to_freeze=[POINT, "anode heat-removal path design (H1F-AN-06)", "distributor depth (H2-3 owner)"])
    P(rows, "H1F-AN-04", "316L disposition for the design-representative / flight anode",
      get("P4", "/fixed_statuses/316L_FLIGHT_ANODE/status"), units="-", tolerance=NO_TOL_RULE,
      evidence_class="owner-allocation",
      sources=[ref("A92", "/decisions/anode_316L"), ref("P4", "/fixed_statuses/316L_FLIGHT_ANODE")],
      basis="A9.2 sec. 3: 316L allowed only as engineering / shakedown material, coupon candidate or low-temperature "
            "development component", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW",
      note="the frozen content is the exclusion, not a material selection")
    P(rows, "H1F-AN-05", "final anode material (design-representative / flight)",
      "TBD - requires the P4 candidate-material trade on a reduced operating temperature (FINAL_ANODE_MATERIAL OPEN)",
      units="-", tolerance="TBD", evidence_class=None,
      sources=[ref("P4", "/fixed_statuses/FINAL_ANODE_MATERIAL"), ref("P4", "/final_material_status"),
               ref("A9REV", find("A9REV", "/new_items", "id", "A9H-ANODE-01") + "/value"), ans(106)],
      basis="A9.2 sec. 3-4 (do not select W, Mo, Pt etc. merely for melting point); P4: every candidate "
            "INCOMPLETE_EVIDENCE", freeze_status="TBD_AFTER_EVIDENCE", freeze_point="after-evidence",
      source_status="OPEN",
      evidence_to_freeze=["P4 biased + floating coupon programme across the shortlisted O-resistant candidates (row 106; "
                          "P4-OQ-02/03 acceptance pre-registered before exposure)",
                          "evidence standard for T_validated,continuous (P4-OQ-01)",
                          "coupled T_operating of the anode (P3-IF-S07; ANODE_THERMAL_CLOSURE UNRESOLVED)",
                          "species-resolved sputtering yields (P4-OQ-04)",
                          "oxygen compatibility, electrical behaviour, fabrication and thermal conductivity per "
                          "candidate (A9.2 sec. 3)"])
    P(rows, "H1F-AN-06", "anode heat-removal path",
      "TBD - requires the anode thermal redesign (A9.2 sec. 4 investigation list, anode_investigation section)",
      units="W; K", tolerance="TBD", evidence_class=None,
      sources=[ref("A92", "/decisions/anode_approach"),
               ref("A9REV", find("A9REV", "/new_items", "id", "A9H-ANODE-02") + "/value"),
               ref("P3", "/closure_statuses/ANODE_THERMAL_CLOSURE"),
               ref("MP2", find("MP2", "/bom", "id", "MPV2-N03") + "/name")],
      basis="A9.2 sec. 4: thermal-design problem first; objective = reduce the actual anode operating temperature, "
            "then select a material with T_operating <= T_validated,continuous - 50 K",
      freeze_status="TBD_AFTER_EVIDENCE", freeze_point="after-evidence", source_status="UNRESOLVED",
      evidence_to_freeze=["each anode_investigation item AI-01..AI-08 evaluated in the coupled model", COUPLED,
                          "measured deposited discharge-power fraction (Phase-1)", "H-1 anode drawing (joints, "
                          "support, feed tube) at the design point"])
    P(rows, "H1F-AN-07", "anode allowable temperature",
      "TBD - requires the selected anode material's oxidation / electrical / creep data (no unsourced target)",
      units="degC", tolerance="TBD", evidence_class=None,
      sources=[ans(87), ref("A9REV", rev("REV-50"))],
      basis="row 87: allowable = validated continuous-use limit - 50 K; no new arbitrary anode limit (A9.2 sec. 4)",
      freeze_status="TBD_AFTER_EVIDENCE", freeze_point="after-evidence",
      evidence_to_freeze=["final anode material (H1F-AN-05) with its validated continuous-use limit"])
    P(rows, "H1F-AN-08", "anode operating temperature",
      "TBD - requires the coupled thermal closure; the A9-07 uncoupled sensitivity (not below 1190 degC) is context "
      "only and never T_operating", units="degC", tolerance="TBD", evidence_class=None,
      sources=[ref("P4", "/findings"), ref("P3", "/closure_statuses")],
      basis="P4 findings; P3 closure statuses UNRESOLVED", freeze_status="TBD_AFTER_EVIDENCE",
      freeze_point="after-evidence", evidence_to_freeze=[COUPLED, "measured anode temperatures (HW-H1-07 / HW-H1-12)"])
    P(rows, "H1F-AN-09", "gas-distributor azimuthal uniformity sizing rule", get("H23", find("H23", "/design_parameters",
                                                                                            "id", "H23-11") + "/value"),
      units="-", tolerance=NO_TOL_RULE, evidence_class="model-derived",
      evidence_note="1-D molecular-diffusion ring model",
      sources=[ref("H23", find("H23", "/design_parameters", "id", "H23-11") + "/value")],
      basis="H2-3 H23-11", freeze_status="OPEN", freeze_point="LOCK-1",
      source_status=get("H23", find("H23", "/design_parameters", "id", "H23-11") + "/status"),
      evidence_to_freeze=["distributor drawing at the design point", "cold-flow azimuthal pressure / flow map on the "
                                                                       "built H-1 (H2-6 taps)"])
    P(rows, "H1F-AN-10", "anode / H-1 electrical rating basis", "rated to the relaxed 350 V V_d end plus transient / "
                                                                "qualification margin (margin TBD)",
      units="V", tolerance="margin TBD", evidence_class="owner-allocation", sources=[ans(81)],
      basis="owner row 81", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW",
      note="the transient / qualification margin itself is still TBD (CIF-G04, OQ-RFQV2-06)")
    P(rows, "H1F-AN-11", "replaceable, serialized anode (and integral distributor)",
      "removable / re-installable with a documented torque and alignment procedure, serialized (HW-H1-10)",
      source_status=get("HWREQ", hwreq("HW-H1-10", "status")), units="-", tolerance=NO_TOL_RULE, evidence_class="assumed",
      evidence_note="requirement PROPOSED in the DRAFT_PENDING_OWNER hardware register",
      sources=[ref("HWREQ", hwreq("HW-H1-10", "text"))], basis="HW-H1-10 (AOL-RC-01)",
      freeze_status="TBD_OWNER", freeze_point="LOCK-1",
      evidence_to_freeze=["owner acceptance of the hardware requirements register (DRAFT_PENDING_OWNER)"])

    # ---------------- MC magnetic circuit ----------------
    P(rows, "H1F-MC-01", "magnetic topology", "T2 magnetically shielded; MC-1 electromagnet only (no permanent-magnet "
                                              "assistance on H-1)",
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(74), ans(78), ref("A9REV", rev("REV-07"))], basis="owner rows 74, 78; A9-07 REV-07",
      freeze_status="FREEZE_CANDIDATE", freeze_point="NOW",
      note="no published extended-channel shielded analog with geometry exists (H2-1 magnetic_topology_options T2 "
           "risks); shielding effectiveness on air species is evidenced only qualitatively")
    P(rows, "H1F-MC-02", "coil arrangement", "single inner coil + single concentric outer coil + trim-coil provision "
                                             "(winding space + reserved supply channel)",
      units="-", tolerance=NO_TOL_RULE, evidence_class="assumed",
      evidence_note="H2-1 preliminary choice from analog practice (SRC-MASMI pp. 8-9)",
      sources=[h21_dp("H21-12"), ref("H21", "/magnetic_topology_options"), ans(74)],
      basis="H2-1 H21-12 (T2 + T3 provision); the H2-1 T2 option that owner row 74 accepted is defined with a single "
            "inner + single outer coil",
      freeze_status="OPEN", freeze_point="LOCK-1", source_status=get("H21", h21("H21-12", "status")),
      evidence_to_freeze=["an owner decision or design evidence for the single-coil-per-pole arrangement and the "
                          "trim-coil provision: owner rows 74 (T2 shielded) and 78 (EM only) do not decide them "
                          "(consolidated verification round 1, PHY-01)", FEMM],
      note="analog-practice choice (assumed); inner / outer arrangement follows the T2 option, but single coils per "
           "pole and the trim-coil provision are not owner-given, so the row is OPEN, not FREEZE_CANDIDATE")
    P(rows, "H1F-MC-03", "unshielded (T1) replaceable pole-piece set",
      "engineering comparison only; never silently the score-bearing article; switching sets creates H-1'",
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(74), h21_dp("H21-13")], basis="owner row 74; H2-1 H21-13", freeze_status="FREEZE_CANDIDATE",
      freeze_point="NOW")
    P(rows, "H1F-MC-04", "inner core: solid (no cathode bore); inner-coil solid-core floor on d_mean",
      get("A9REV", rev("REV-01")), units="mm", tolerance=NO_TOL_WINDOW, evidence_class="model-derived",
      sources=[ans(79), ref("A9REV", rev("REV-01")), ref("A9REV", "/recomputations/h21_central_bore/method")],
      basis="row 79 removes the central bore; A9-07 REV-01 lumped-circuit recomputation (floor by h)",
      freeze_status="OPEN", freeze_point="LOCK-1", evidence_to_freeze=[FEMM],
      note="'no bore' is decided (row 79); the floor values are lumped-circuit estimates that FEMM closes")
    P(rows, "H1F-MC-05", "pole-piece geometry including chamfered downstream wall edges (shielding)",
      "TBD - requires a shielded-topology FEMM design at the design point", units="mm", tolerance="TBD",
      evidence_class=None, sources=[h21_dp("H21-11"), ref("A9REV", rev("REV-03"))],
      basis="H2-1 H21-11 (chamfer is shielded-thruster practice, SRC-MASMI p. 5)",
      freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1", evidence_to_freeze=[POINT, FEMM])
    P(rows, "H1F-MC-06", "MC-1 envelope at the RP-1 anchor (body OD, axial length)",
      {"body_OD_mm": get("H21", "/interface_demands/14/value/body_OD_mm"),
       "length_mm": get("H21", "/interface_demands/14/value/length_mm")},
      units="mm", tolerance=NO_TOL_ANCHOR, evidence_class="model-derived",
      sources=[h21_dp("H21-25"), ref("H21", "/interface_demands/14/value")],
      basis="H2-1 RP-1 f_NI 2 lumped circuit", freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[POINT, FEMM], note="RP-1 is a calculation anchor; corner cases span 117.6-151.8 mm body OD")
    P(rows, "H1F-MC-07", "engineering design factors (B headroom, working flux / B_sat, discharge share)",
      get("A9REV", rev("REV-10")), units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(80), ref("A9REV", rev("REV-10"))],
      basis="owner row 80: engineering factors until verified", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW",
      note="local saturation at pole roots is not captured by the lumped model (H2-1 H21-23); FEMM verifies")
    P(rows, "H1F-MC-08", "MC-1 magnetic-parts mass floor at RP-1 f_NI 2 (iron + copper)",
      {"iron_kg": get("H21", h21("H21-24"))["iron_kg"], "copper_kg": get("H21", h21("H21-24"))["copper_kg"],
       "total_kg": get("MP2", find("MP2", "/bom", "id", "A9B-16") + "/columns/EVIDENCE_FLOOR/value")},
      units="kg", tolerance=NO_TOL_ANCHOR, evidence_class="model-derived",
      sources=[h21_dp("H21-24"), ref("MP2", find("MP2", "/bom", "id", "A9B-16") + "/columns/EVIDENCE_FLOOR"),
               ref("OQ4", find("OQ4", "/rows", "id", "MQ-03") + "/question")],
      basis="H2-1 H21-24; mass_power v2 A9B-16 evidence floor", freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[POINT, FEMM, "owner re-allocation of AL-04 (existing MQ-03: 3.0 kg allocation below the "
                                       "3.504 kg floor)", "weighed MC-1"],
      note="excludes channel ceramics, anode, body and structure (A9B-15 CBE TBD)")
    P(rows, "H1F-MC-09", "hot-state B reference sensor on MC-1", get("A9REV", rev("REV-11")), units="-",
      tolerance=NO_TOL_RULE, evidence_class="owner-allocation", sources=[ans(82), ref("A9REV", rev("REV-11"))],
      basis="owner row 82: traceable to coil current and temperature", freeze_status="FREEZE_CANDIDATE",
      freeze_point="NOW")
    P(rows, "H1F-MC-10", "MC-1 exterior high-emittance temperature-capable coating (requirement)",
      "required; qualified for vacuum / AO / electrical compatibility", units="-", tolerance=NO_TOL_RULE,
      evidence_class="owner-allocation", sources=[ans(84)], basis="owner row 84",
      freeze_status="FREEZE_CANDIDATE", freeze_point="NOW", note="coating identity and limit: H1F-MA-06")

    # ---------------- BZ B(z) target ----------------
    bz = "/bz_target_envelope"
    P(rows, "H1F-BZ-01", "Vyovrinda-specific B(z) evidence for H-1",
      "TBD - none exists: no FEMM of MC-1 and no measured H-1 map; the P5 Peterson 2001 profile is a reference for "
      "P5 only (bz_reference section)", units="G", tolerance="TBD", evidence_class=None,
      sources=[ref("M16", find("M16", "/rows", "row", 10) + "/blocking_item"), ref("P5B16"), ref("P5B30")],
      basis="M16 v4 row 10; hallthruster_bridge/bfield (P5 only)", freeze_status="TBD_AFTER_EVIDENCE",
      freeze_point="LOCK-1", evidence_to_freeze=[FEMM, "room-temperature B(z) map of the built MC-1 at the actual "
                                                       "coil currents (HW-MC-03) and hot-state traceability "
                                                       "(HW-MC-15, row 82)"])
    P(rows, "H1F-BZ-02", "B_r(z) shape target",
      get("H21", h21("H21-16")), units="-", tolerance="TBD - FEMM + owner tolerance", evidence_class="inferred",
      evidence_note="published xenon practice (GK2008 pp. 329, 331, 335; EV-B1/EV-B5); the ECHT plateau (EV-B6) is "
                    "the recorded alternative extended-channel practice",
      sources=[h21_dp("H21-16"), ref("H21", bz + "/gradient"), ref("H21", bz + "/peak_position")],
      basis="H2-1 H21-16", freeze_status="OPEN", freeze_point="LOCK-1",
      source_status=get("H21", h21("H21-16", "status")), evidence_to_freeze=[FEMM, "owner tolerance on the shape "
                                                                                   "(peak position, B_anode/B_peak)"])
    P(rows, "H1F-BZ-03", "peak centreline B_r target envelope (at / near IP-EXIT)", get("H21", h21("H21-14")),
      units="G", tolerance=NO_TOL_WINDOW, evidence_class="model-derived",
      evidence_note="electron-magnetization criterion r_Le <= 0.1 h over the declared T_e bracket 10-30 eV; a design "
                    "target envelope, not a transport optimization and not taken from P5",
      sources=[h21_dp("H21-14"), ref("H21", bz + "/rLe_rule_table_G")], basis="H2-1 H21-14",
      freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[POINT + " (the criterion depends on h)", FEMM, "owner acceptance of the criterion band "
                                                                         "(new owner question F5-OQ-05)"])
    P(rows, "H1F-BZ-04", "MC-1 field capability", get("H21", h21("H21-15")), units="G", tolerance=NO_TOL_WINDOW,
      evidence_class="model-derived", sources=[h21_dp("H21-15"), ref("A9REV", rev("REV-10"))],
      basis="B headroom 1.5 (row 80) x H1F-BZ-03 upper end", freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[POINT, FEMM])
    P(rows, "H1F-BZ-05", "B_anode / B_peak ratio and peak-position tolerance",
      "TBD - requires FEMM of the circuit at the design point and an owner tolerance", units="- ; mm",
      tolerance="TBD", evidence_class=None, sources=[ref("H21", bz + "/anode_region"), ref("H21", bz + "/peak_position")],
      basis="H2-1 bz_target_envelope", freeze_status="TBD_OWNER", freeze_point="LOCK-1",
      evidence_to_freeze=[FEMM, "owner tolerance after FEMM"])
    P(rows, "H1F-BZ-06", "allowable B(z) field-change tolerance epsilon_B with the downstream module installed / "
                         "energized",
      "TBD - requires measured H-1 sensitivity (do not invent a tolerance now)", units="-", tolerance="TBD",
      evidence_class=None,
      sources=[ans(67), ref("PREREG", find("PREREG", "/gate_deadlines", "id", "GD-11")),
               ref("ICD", icd("ICP-31", "status"))],
      basis="owner row 67; GD-11 (before HI-LOCK2); ICD ICP-31", freeze_status="TBD_AFTER_EVIDENCE",
      freeze_point="LOCK-2", evidence_to_freeze=["coil-current sensitivity scan on the built H-1 (HW-MC-05)",
                                                 "B(z) perturbation scan with the ICP module installed / energized "
                                                 "(A9H-INS-11)"])

    # ---------------- CO coil operating envelope ----------------
    cases = get("H21", "/coil_design/cases")
    rp1_idx = [i for i, c in enumerate(cases) if c["name"].startswith("RP-1")]
    cur = {k: sorted(cases[i]["coils"][k]["chosen"]["I_A"] for i in rp1_idx) for k in ("inner", "outer")}
    P(rows, "H1F-CO-01", "coil supply control rule",
      "current-controlled coil supplies; every coil current recorded per reading with per-channel I and V telemetry",
      units="-", tolerance=NO_TOL_RULE,
      evidence_class="owner-allocation",
      evidence_note="row 78 (EM only for traceable B(z)-versus-current control); HW-MC-02 current-control rule",
      sources=[ans(78), ref("HWREQ", hwreq("HW-MC-02", "text"))],
      basis="row 78; HW-MC-02", freeze_status="FREEZE_CANDIDATE", freeze_point="LOCK-1",
      note="consolidated verification round 2 (PHY-03): the supply channel count (per coil, trim reserved), which "
           "follows from the OPEN coil arrangement H1F-MC-02, was split out to H1F-CO-14 (OPEN); this row fixes only "
           "the control and recording rule")
    P(rows, "H1F-CO-02", "total ampere-turns at the RP-1 anchor (f_NI 1 .. 2)", get("H21", h21("H21-17")),
      units="A-turns", tolerance=NO_TOL_ANCHOR, evidence_class="model-derived",
      sources=[h21_dp("H21-17"), ref("H21", "/coil_design/accuracy_limits")],
      basis="H2-1 lumped reluctance + explicit NI margin factor", freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[POINT, FEMM],
      note=f"RP-1 worst-case assumptions: {cases[rp1_idx[-1]]['NI_total_A']} A-turns; the lumped estimate can be off "
           "by a factor of order the NI margin bracket (H2-1 accuracy_limits)")
    P(rows, "H1F-CO-03", "per-coil current over the RP-1 cases (chosen gauges)",
      {"inner_A": [cur["inner"][0], cur["inner"][-1]], "outer_A": [cur["outer"][0], cur["outer"][-1]]},
      units="A", tolerance=NO_TOL_ANCHOR, evidence_class="model-derived",
      sources=[ref("H21", f"/coil_design/cases/{i}/coils") for i in rp1_idx],
      basis="H2-1 coil_design cases RP-1 f_NI=1, f_NI=2, worst-case assumptions", freeze_status="OPEN",
      freeze_point="LOCK-1", evidence_to_freeze=[POINT, FEMM, "conductor choice (H1F-CO-08)",
                                                 "PPU coil-supply rating (H2-4 / PPU owner)"])
    P(rows, "H1F-CO-04", "highest coil terminal voltage over the RP-1 cases (Ni-clad conductor at its 1000 F class)",
      get("H21", "/interface_demands/5/value"), units="V", tolerance=NO_TOL_ANCHOR, evidence_class="model-derived",
      sources=[ref("H21", "/interface_demands/5/value")], basis="H2-1 interface demand to H2-4",
      freeze_status="OPEN", freeze_point="LOCK-1", evidence_to_freeze=[POINT, FEMM, "conductor choice (H1F-CO-08)"])
    P(rows, "H1F-CO-05", "coil power at the terminals, inner + outer (trim excluded)", get("H21", h21("H21-18")),
      units="W", tolerance=NO_TOL_ANCHOR, evidence_class="model-derived",
      sources=[h21_dp("H21-18"), ref("A9REV", rev("REV-43"))],
      basis="H2-1 H21-18 (copper 20 C f_NI 1 .. Ni-clad conductor at its class temperature, worst case)",
      freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[POINT, FEMM, "coil hot-spot temperature from the coupled thermal closure", "conductor choice"],
      note="A9-07 REV-43 thermal-model bound: 60 W (H2-5 v1 assumed) x Ni-clad factor 1.3263 x 1.2 = 95.49 W "
           "(consistency_checks CC-08)")
    P(rows, "H1F-CO-06", "coils outside the analog 1-5 A / 1-12 V supply window",
      get("H21", "/interface_demands/4/value"), units="-", tolerance=NO_TOL_RULE, evidence_class="model-derived",
      sources=[ref("H21", "/interface_demands/4/value"), ref("H21", "/assumed_inputs/coil_supply_window")],
      basis="H2-1 interface demand to H2-4 (the window is a published analog supply rating, not a Vyovrinda supply)",
      freeze_status="OPEN", freeze_point="LOCK-1", source_status=get("H21", "/interface_demands/4/status"),
      evidence_to_freeze=["Vyovrinda coil-supply rating (PPU owner) matched to the FEMM-sized coils"])
    P(rows, "H1F-CO-07", "trim coil ampere-turns and power", "TBD - requires FEMM of the preliminary circuit",
      units="A-turns; W", tolerance="TBD", evidence_class=None, sources=[ref("H21", "/interface_demands/1/status")],
      basis="H2-1 (trim is a provision; its NI is not sized)", freeze_status="TBD_AFTER_EVIDENCE",
      freeze_point="LOCK-1", evidence_to_freeze=[FEMM])
    P(rows, "H1F-CO-08", "coil conductor: plain copper or Ni-clad copper (both ceramic-insulated)",
      "TBD - owner decision (existing OQ-A907-04); a Ni-clad conductor needs a measured magnetic perturbation",
      units="-", tolerance="TBD", evidence_class=None,
      sources=[ref("OQ4", find("OQ4", "/rows", "id", "OQ-A907-04") + "/status"), ans(77)],
      basis="row 77; OQ-A907-04 (TBD_OWNER)", freeze_status="TBD_OWNER", freeze_point="LOCK-1",
      evidence_to_freeze=["owner answer OQ-A907-04", "wire quotation; measured perturbation if Ni-clad (HW-MC-12)"])
    P(rows, "H1F-CO-09", "coil insulation family", "ceramic-insulated copper; no polyimide as the primary hot / "
                                                   "AO-adjacent solution",
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(77), ref("A9REV", find("A9REV", "/revision_register", "id", "REV-04") + "/new/requirement")],
      basis="owner row 77; REV-04", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW")
    P(rows, "H1F-CO-10", "coil turn-insulation screen", "150 V AC turn rating = minimum procurement screen, subject "
                                                        "to representative-gas hipot",
      units="V AC", tolerance=NO_TOL_RULE, evidence_class="owner-allocation", sources=[ans(77)],
      basis="owner row 77", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW")
    P(rows, "H1F-CO-11", "coil design temperature ceiling", get("A9REV", rev("REV-04")),
      units="degC", tolerance=NO_TOL_RULE, evidence_class="assumed",
      evidence_note="supplier continuous rating (MCQ-EM-03) minus the row-86 50 K margin; the supplier rating is not "
                    "validated (OQ-A907-05 provisional)",
      sources=[ref("A9REV", rev("REV-04")), ans(86)], basis="REV-04; row 86", freeze_status="OPEN",
      freeze_point="LOCK-1", evidence_to_freeze=["coil EIS thermal-endurance qualification (HW-MC-07) and the "
                                                 "sacrificial-coil cycle (HW-MC-16)", "hot-spot offset measurement "
                                                                                      "(HW-MC-14)"])
    P(rows, "H1F-CO-12", "coil thermal node closure", "UNRESOLVED", units="-", tolerance=NO_TOL_RULE,
      evidence_class="model-derived",
      evidence_note="A9-07 inner coil CI is the design-driving node; every hall_icp_neutralizer result is an uncoupled "
                    "sensitivity reported UNRESOLVED",
      sources=[ref("A9REV", "/key_findings/3"), ref("P3", "/closure_statuses/ICP_COUPLED_THERMAL")],
      basis="A9-07 K4; A9.2 ICP_COUPLED_THERMAL", freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[COUPLED, "FEMM-sized winding window", "validated coil rating"])
    P(rows, "H1F-CO-13", "coil copper mass basis (A9.2 sec. 8 coil-mass correction)",
      {"complete_coil_copper_estimate_kg_RP1_fNI2": get("MP2", "/coil_mass_correction/booked_copper_kg"),
       "sensitivity_basis_60W_fixed_NI_kg_NOT_coil_mass": get("MP2", "/coil_mass_correction/sensitivity_basis_60W_kg")},
      units="kg", tolerance=NO_TOL_ANCHOR, evidence_class="model-derived",
      sources=[ref("A92", "/decisions/coil_mass_correction"), ref("MP2", "/coil_mass_correction"),
               ref("A9REV", "/key_findings/11")],
      basis="A9.2 sec. 8: the two figures are different bases, never alternative estimates of the same mass; only the "
            "complete coil mass is booked", freeze_status="OPEN", freeze_point="LOCK-1",
      evidence_to_freeze=[POINT, FEMM, "frozen H-1 coil (IDA7-01) and a weighed coil"])
    P(rows, "H1F-CO-14", "coil supply channel count",
      "one supply per coil: inner, outer, trim reserved (3 channels); contingent on the coil arrangement H1F-MC-02",
      units="-", tolerance=NO_TOL_RULE, evidence_class="assumed",
      evidence_note="H2-1 H21-27 (assumed (requirement), PRELIMINARY); owner rows 74 / 78 and HW-MC-02 give no "
                    "channel count and no trim channel",
      sources=[h21_dp("H21-27"), ref("HWREQ", hwreq("HW-MC-02", "text")), ans(78)],
      basis="H2-1 H21-27; follows the H1F-MC-02 arrangement (OPEN)", freeze_status="OPEN", freeze_point="LOCK-1",
      source_status=get("H21", h21("H21-27", "status")),
      evidence_to_freeze=["H1F-MC-02 (coil arrangement) reaching FREEZE_CANDIDATE: an owner decision or design "
                          "evidence for single coils per pole and the trim-coil provision", FEMM],
      note="consolidated verification round 2 (PHY-03): split from H1F-CO-01; a channel count derived from an OPEN "
           "arrangement is never an owner allocation")

    # ---------------- MA materials ----------------
    P(rows, "H1F-MA-01", "inner core / inner pole material family", "FeCo-2V (Hiperco 50 class) engineering baseline",
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(76), ref("A9REV", find("A9REV", "/revision_register", "id", "REV-05") + "/new/requirement")],
      basis="owner row 76", freeze_status="FREEZE_CANDIDATE", freeze_point="LOCK-1",
      note="the specific grade / lot and its B-H data are HW-MC-13 items")
    P(rows, "H1F-MA-02", "outer core / back plate / outer pole material family", "high-purity iron (ARMCO class) "
                                                                                 "engineering baseline",
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(76), ref("A9REV", find("A9REV", "/revision_register", "id", "REV-06") + "/new/requirement")],
      basis="owner row 76", freeze_status="FREEZE_CANDIDATE", freeze_point="LOCK-1")
    P(rows, "H1F-MA-03", "FeCo-2V hot-use limit", get("A9REV", rev("REV-05")), units="degC", tolerance="TBD",
      evidence_class=None, sources=[ref("A9REV", rev("REV-05")), ref("A9REV", rev("REV-44"))],
      basis="row 76 + row 86; uncoupled-sensitivity Curie check PI = FAIL (REV-44, reported UNRESOLVED)",
      freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1",
      evidence_to_freeze=["sourced B_sat(T) / B-H vs temperature of the selected FeCo-2V grade (HW-MC-13)", COUPLED])
    P(rows, "H1F-MA-04", "pure-iron hot-use limit", get("A9REV", rev("REV-06")), units="degC", tolerance="TBD",
      evidence_class=None, sources=[ref("A9REV", rev("REV-06")), ref("H21", "/materials/candidates/ARMCO_pure_iron/curie_C")],
      basis="row 76 + row 86", freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1",
      evidence_to_freeze=["sourced B_sat(T) of the pure-iron grade (HW-MC-13)", "resolution of the iron Curie value "
                                                                               "discrepancy CC-07 (F5-OQ-03)"])
    P(rows, "H1F-MA-05", "channel wall grade", "TBD - owner / design decision (lane 17 Q6, HW-H1-04); flight practice "
                                               "is BN or BN-SiO2; no N+/N2+/O+/O2+ sputter yield on BN, BN-SiO2 or SiC "
                                               "found in open sources",
      units="-", tolerance="TBD", evidence_class=None, sources=[ref("HWREQ", hwreq("HW-H1-04", "values"))],
      basis="HW-H1-04", freeze_status="TBD_OWNER", freeze_point="before-HI-S1",
      evidence_to_freeze=["owner decision lane 17 Q6", "N/O coupon evidence (lane 32 H1-H4)", "wall thermal margin "
                          "under the coupled model (A9-07 K2: BN inner wall UNRESOLVED against the 850 degC design "
                          "ceiling = 900 degC oxidizing guide - 50 K)"])
    P(rows, "H1F-MA-06", "MC-1 exterior coating identity and temperature limit",
      "TBD - requires a coating datasheet / coupon value (existing OQ-A907-08)", units="degC", tolerance="TBD",
      evidence_class=None, sources=[ref("OQ4", find("OQ4", "/rows", "id", "OQ-A907-08") + "/status"), ans(84)],
      basis="row 84; OQ-A907-08", freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1",
      evidence_to_freeze=["coating datasheet or coupon qualification (vacuum / AO / electrical)"])
    P(rows, "H1F-MA-07", "pole-face O / O2 exposure protection and witness pair",
      "TBD - protective coating or ceramic cover; MC-1 witness pair (HW-MC-06, AOL-WC-04)", units="-",
      tolerance="TBD", evidence_class=None,
      sources=[ref("H21", "/materials/O_O2_exposure"), ref("HWREQ", hwreq("HW-MC-06", "text"))],
      basis="H2-1 materials O_O2_exposure", freeze_status="TBD_AFTER_EVIDENCE", freeze_point="after-evidence",
      evidence_to_freeze=["ground AO exposure of pole-material coupons (AOL-EX-02)", "witness-pair results"])
    P(rows, "H1F-MA-08", "anode material candidates under investigation",
      [c["id"] + " " + c["name"] for c in get("P4", "/candidates")], units="-", tolerance=NO_TOL_RULE,
      evidence_class="assumed", evidence_note="candidate list only; every gate cell INCOMPLETE_EVIDENCE; no ranking",
      sources=[ref("P4", "/candidates"), ref("P4", "/candidate_screening_states")],
      basis="P4 framework (APP-ANODE)", freeze_status="OPEN", freeze_point="after-evidence",
      evidence_to_freeze=["as H1F-AN-05"])

    # ---------------- TH thermal rules ----------------
    P(rows, "H1F-TH-01", "thermal design margin rule", get("A9REV", rev("REV-40")), units="K; -",
      tolerance=NO_TOL_RULE, evidence_class="owner-allocation", sources=[ans(86), ref("A9REV", rev("REV-40"))],
      basis="owner row 86: >= 50 K below each validated continuous-use limit + 20 % heat-load margin",
      freeze_status="FREEZE_CANDIDATE", freeze_point="NOW")
    P(rows, "H1F-TH-02", "spacecraft mounting-interface temperature and allowable conducted heat",
      "TBD - carried as cases 20/40/60 degC and 25/50/100 W; frozen at the spacecraft / PDR interface definition",
      units="degC; W", tolerance="TBD", evidence_class=None,
      sources=[ans(85), ref("OQ4", find("OQ4", "/rows", "id", "OQ-A907-06") + "/status")],
      basis="owner row 85; existing OQ-A907-06", freeze_status="TBD_OWNER", freeze_point="after-evidence",
      evidence_to_freeze=["spacecraft / PDR thermal ICD", "owner answer OQ-A907-06"])
    P(rows, "H1F-TH-03", "coupled H-1 / ICP thermal closure", get("P3", "/closure_statuses/ICP_COUPLED_THERMAL"),
      units="-", tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ref("A92", "/decisions/icp_coupled_thermal"), ref("P3", "/closure_statuses")],
      basis="A9.2 sec. 5-7 (no thermal PASS from a negligible-coupling calculation)", freeze_status="OPEN",
      freeze_point="LOCK-1", evidence_to_freeze=[COUPLED, "ICP module drawings (ICP-02/04/07) from F6 / the ICD"])

    # ---------------- IN inlet ----------------
    P(rows, "H1F-IN-01", "H-1 inlet plane", "HALL_INLET_Z0 = anode / gas-distributor face, z = 0; the distributor "
                                            "belongs to H-1 and is identical in every configuration",
      units="-", tolerance=NO_TOL_RULE, evidence_class="assumed", evidence_note="convention",
      sources=[h21_dp("H21-09"), ref("HWREQ", hwreq("HW-H1-06", "text")), ref("ICD", "/standing_facts/scope")],
      basis="H2-1 H21-09; HW-H1-06; ICD standing fact 'nothing upstream of HALL_INLET_Z0 changes between "
            "configurations'", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW")
    P(rows, "H1F-IN-02", "feed topology upstream of H-1 in the A9 primary line",
      get("A9REV", find("A9REV", "/revision_register", "id", "REV-65") + "/new/requirement"), units="-",
      tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ref("A9REV", find("A9REV", "/revision_register", "id", "REV-65") + "/new")],
      basis="A9-07 REV-65 (no upstream pre-ionizer module in A9)", freeze_status="FREEZE_CANDIDATE",
      freeze_point="NOW")
    P(rows, "H1F-IN-03", "inlet annulus (anode / distributor) width and mean diameter",
      get("H21", "/interface_demands/15/value"), units="mm", tolerance=NO_TOL_WINDOW, evidence_class="model-derived",
      sources=[ref("H21", "/interface_demands/15/value")], basis="H2-1 interface demand to H2-3 (= channel windows)",
      freeze_status="OPEN", freeze_point="LOCK-1", evidence_to_freeze=[POINT])
    P(rows, "H1F-IN-04", "inlet conductance / pressure needed at HALL_INLET_Z0 and IF-A5",
      "TBD - requires the frozen channel and distributor; the H2-3 H23-05 / H23-06 values are ECHT-size analog "
      "illustrations and are not carried", units="Pa; m^3/s", tolerance="TBD", evidence_class=None,
      sources=[ref("H23", find("H23", "/design_parameters", "id", "H23-05") + "/note"),
               ref("H23", find("H23", "/design_parameters", "id", "H23-06") + "/status")],
      basis="H2-3 pressure_budget (PENDING H2-1)", freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1",
      evidence_to_freeze=[POINT, "distributor drawing", "cold-flow conductance measured on the built H-1 (S1a)"])
    P(rows, "H1F-IN-05", "inlet-state demand set offered by F4 (mdot_s, P, T, x_s, transient quality)",
      "TBD - see interface_demands IFD-F4-01..07", units="mixed", tolerance="TBD", evidence_class=None,
      sources=[ref("A97_MD", "", note="A9.7 F4: the final output offered to H-1 is mdot_s, P, T, x_s, transient "
                                      "quality, not merely total mass flow")],
      basis="A9.7 F4 / F5", freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1",
      evidence_to_freeze=["F4 plenum / feed offered-state records with evidenced inputs (F4-ID-07; today PARAMETRIC_SENSITIVITY only)", "H-1 inlet-state sensitivity measured in "
                          "Phase 1 (no admitted Hall map can derive tolerances)"])

    # ---------------- EX exit plane ----------------
    P(rows, "H1F-EX-01", "IP-EXIT definition", get("A9REV", rev("REV-03")), units="mm", tolerance=NO_TOL_RULE,
      evidence_class="assumed", evidence_note="convention (A9.1 plane names)",
      sources=[ref("A91", "/decisions/A9-03-planes"), ref("A9REV", rev("REV-03")), ref("A9REV", rev("REV-66"))],
      basis="A9.1 A9-03-planes; REV-03 / REV-66", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW",
      note="the axial coordinate of IP-EXIT equals L (H1F-CH-10, OPEN)")
    P(rows, "H1F-EX-02", "Hall head neutralizer-agnostic (no C1 bore, no C1 mount on H-1)",
      "no electron-source hardware on H-1; downstream / coaxial module datum IP-NEU on KC-1", units="-",
      tolerance=NO_TOL_RULE, evidence_class="owner-allocation",
      sources=[ans(79), ref("A9REV", find("A9REV", "/revision_register", "id", "REV-03") + "/new/requirement")],
      basis="owner row 79", freeze_status="FREEZE_CANDIDATE", freeze_point="NOW")
    P(rows, "H1F-EX-03", "axial standoff IP-EXIT -> IP-NEU (ICP module datum)",
      "TBD - ICD ICP-02 (LOCK-1); geometry search belongs to F6 after P1/P2 evidence", units="mm", tolerance="TBD",
      evidence_class=None, sources=[ref("ICD", icd("ICP-02", "status"))], basis="ICD ICP-02",
      freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1",
      evidence_to_freeze=["F6 ICP geometry synthesis with P1 / P2 evidence", "coupled view-factor calculation "
                                                                           "(A9.2 sec. 6)"])
    P(rows, "H1F-EX-04", "exit-face channel OD (frozen) for the downstream interface",
      "TBD - follows the design point (ICD ID-13)", units="mm", tolerance="TBD", evidence_class=None,
      sources=[ref("ICD", find("ICD", "/interface_demands", "id", "ID-13") + "/status")], basis="ICD ID-13 (PARTIAL)", freeze_status="TBD_AFTER_EVIDENCE",
      freeze_point="LOCK-1", evidence_to_freeze=[POINT])
    P(rows, "H1F-EX-05", "MC-1 stray field in the ICP volume, at IP-NEU and at the C1 orifice (IP-C1)",
      "TBD - requires FEMM of MC-1 and a measured B map (ICD ID-13, IDA7-17, REV-17)", units="G", tolerance="TBD",
      evidence_class=None, sources=[ref("A9REV", rev("REV-17")), ref("ICD", icd("ICP-32", "value")),
                                    ref("ICD", find("ICD", "/interface_demands", "id", "ID-13") + "/status")],
      basis="REV-17; ICD ICP-32 (unmagnetized ICP, no dedicated ICP magnet, v1)", freeze_status="TBD_AFTER_EVIDENCE",
      freeze_point="LOCK-1", evidence_to_freeze=[FEMM, "measured fringe-field map downstream of IP-EXIT"])
    P(rows, "H1F-EX-06", "exit-face keep-out zone for the downstream module", "TBD - ICD ICP-07 (LOCK-1)",
      units="mm", tolerance="TBD", evidence_class=None, sources=[ref("ICD", icd("ICP-07", "status"))],
      basis="ICD ICP-07", freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1",
      evidence_to_freeze=["H-1 drawing at the design point", "F6 module envelope"])
    P(rows, "H1F-EX-07", "H-1 exit-face radiative exchange with the downstream ICP assembly",
      "TBD - requires the ICP geometry and view factors (Q_Hall->ICP, back-radiation, view obstruction)",
      units="W", tolerance="TBD", evidence_class=None,
      sources=[ref("A92", "/decisions/radiative_view_requirement"), ref("ICD", icd("ICP-47", "status"))],
      basis="A9.2 sec. 5-6; ICD ICP-47", freeze_status="TBD_AFTER_EVIDENCE", freeze_point="LOCK-1",
      evidence_to_freeze=[COUPLED])
    P(rows, "H1F-EX-08", "Hall-probe path from beyond IP-EXIT to the anode face with any module installed",
      "B(z) probe path along the channel mean radius from beyond IP-EXIT to z = 0 (HW-H1-08)",
      source_status=get("HWREQ", hwreq("HW-H1-08", "status")), units="-", tolerance=NO_TOL_RULE, evidence_class="assumed",
      evidence_note="requirement PROPOSED in the DRAFT_PENDING_OWNER hardware register",
      sources=[ref("HWREQ", hwreq("HW-H1-08", "text")), h21_dp("H21-29")], basis="HW-H1-08; H2-1 H21-29",
      freeze_status="TBD_OWNER", freeze_point="LOCK-1",
      evidence_to_freeze=["owner acceptance of the hardware requirements register", "KC-1 / module drawings that "
                                                                                   "leave the path open"])
    return rows


# --------------------------------------------------------------------------------------------------------------------
# geometric admissibility (interface to F7: x_Hall bounds; fail closed; never a PASS)
# --------------------------------------------------------------------------------------------------------------------
# The H2-1 windows and corners are published to 4 significant figures; window edges are compared with this relative
# rounding allowance so that the published corners themselves are not rejected by their own rounding. It is a
# publication-rounding treatment, not a physical tolerance.
ROUNDING_REL = 1e-3


def x_hall_definition() -> dict:
    return {
        "variables": {
            "h_mm": get("H21", h21("H21-03")),
            "d_mean_mm": get("H21", h21("H21-04")),
            "L_mm": get("H21", h21("H21-08")),
        },
        "constraints": {
            "area_window_cm2": get("H21", h21("H21-01")),
            "d_over_h_window": get("H21", h21("H21-02")),
            "L_over_h_window": [get("H21", h21("H21-07"))[0], get("A9REV", rev("REV-08"))],
            "inner_coil_solid_core_floor_mm": {k: v for k, v in get("A9REV", rev("REV-01")).items()},
        },
        "window_edge_rounding_rel": ROUNDING_REL,
        "not_evaluated": ["FEMM magnetic feasibility (saturation, leakage, B(z) shape)", "coupled thermal margins",
                          "coil-supply window", "mass against AL-04", "Hall performance (thrust, I_d, efficiency): no "
                                                                      "admitted Hall response map"],
    }


def geometric_admissibility(h_mm: float, d_mean_mm: float, L_mm: float, assumptions: str = "worst_case_assumptions",
                            xdef: dict | None = None) -> dict:
    """Check a candidate (h, d_mean, L) against the declared H-1 geometric windows only.

    Returns WITHIN_DECLARED_GEOMETRIC_WINDOWS or OUTSIDE_DECLARED_GEOMETRIC_WINDOWS (or OUT_OF_DOMAIN for an h outside
    the tabulated inner-coil floor). It is never a PASS: FEMM, thermal, supply, mass and every Hall performance
    quantity stay NOT_EVALUATED. Between tabulated h rows the larger (upper-row) floor is used (conservative)."""
    xdef = xdef or x_hall_definition()
    c = xdef["constraints"]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (h_mm, d_mean_mm, L_mm)):
        return {"status": "OUT_OF_DOMAIN", "violations": ["non-finite or non-positive input"],
                "not_evaluated": xdef["not_evaluated"], "performance": "NOT_EVALUATED"}
    floors = c["inner_coil_solid_core_floor_mm"]
    if assumptions not in next(iter(floors.values())):
        raise ValueError(f"unknown assumption set {assumptions!r}")
    hs = sorted(float(k) for k in floors)
    if h_mm < hs[0] or h_mm > hs[-1]:
        return {"status": "OUT_OF_DOMAIN", "violations": [f"h {h_mm} mm outside the tabulated floor range "
                                                          f"[{hs[0]}, {hs[-1]}] mm"],
                "not_evaluated": xdef["not_evaluated"], "performance": "NOT_EVALUATED"}
    k = bisect.bisect_left(hs, h_mm)
    key = {float(kk): kk for kk in floors}[hs[k]]
    floor = floors[key][assumptions]
    viol = []
    area_cm2 = math.pi * h_mm * d_mean_mm / 100.0
    tol = ROUNDING_REL
    a0, a1 = c["area_window_cm2"]
    if not (a0 * (1 - tol) <= area_cm2 <= a1 * (1 + tol)):
        viol.append(f"area {area_cm2:.4g} cm^2 outside [{a0}, {a1}]")
    r0, r1 = c["d_over_h_window"]
    if not (r0 * (1 - tol) <= d_mean_mm / h_mm <= r1 * (1 + tol)):
        viol.append(f"d_mean/h {d_mean_mm / h_mm:.4g} outside [{r0}, {r1}]")
    l0, l1 = c["L_over_h_window"]
    if not (l0 * (1 - tol) <= L_mm / h_mm <= l1 * (1 + tol)):
        viol.append(f"L/h {L_mm / h_mm:.4g} outside [{l0}, {l1}]")
    if d_mean_mm < floor:
        viol.append(f"d_mean {d_mean_mm} mm below the inner-coil solid-core floor {floor} mm ({assumptions}, h row "
                    f"{key} mm)")
    return {"status": "OUTSIDE_DECLARED_GEOMETRIC_WINDOWS" if viol else "WITHIN_DECLARED_GEOMETRIC_WINDOWS",
            "violations": viol, "floor_row_h_mm": key, "floor_mm": floor, "assumptions": assumptions,
            "not_evaluated": xdef["not_evaluated"], "performance": "NOT_EVALUATED"}


# --------------------------------------------------------------------------------------------------------------------
# consistency checks (arithmetic re-derivations of consumed values; never a PASS)
# --------------------------------------------------------------------------------------------------------------------
def consistency_checks() -> list:
    out = []

    def add(cid, what, computed, reported, rel_tol, src, note=None, recorded_discrepancy=False):
        if isinstance(computed, (int, float)) and isinstance(reported, (int, float)):
            ok = math.isclose(computed, reported, rel_tol=rel_tol, abs_tol=0.0)
        else:
            ok = computed == reported
        res = "CONSISTENT" if ok else ("DISCREPANCY_RECORDED" if recorded_discrepancy else "INCONSISTENT")
        r = {"id": cid, "check": what, "computed": computed, "reported": reported, "rel_tol": rel_tol,
             "result": res, "source": src}
        if note:
            r["note"] = note
        out.append(r)

    corners = get("H21", "/channel/corners")
    for name, cdat in corners.items():
        h = math.sqrt(cdat["A_cm2"] * 100.0 / (math.pi * cdat["d_over_h"]))
        add(f"CC-01-{name}", f"corner {name}: h = sqrt(A / (pi d/h))", sig(h, 4), cdat["h_mm"], 2e-3,
            [ref("H21", f"/channel/corners/{name}")])
        add(f"CC-02-{name}", f"corner {name}: OD - ID = 2 h", sig(cdat["OD_channel_mm"] - cdat["ID_channel_mm"], 4),
            sig(2 * cdat["h_mm"], 4), 2e-3, [ref("H21", f"/channel/corners/{name}")])
    lw = get("H21", h21("H21-08"))
    hw = get("H21", h21("H21-03"))
    lhw = get("H21", h21("H21-07"))
    add("CC-03", "L window = [L/h_min x h_min, L/h_max x h_max]", [sig(lhw[0] * hw[0], 4), sig(lhw[1] * hw[1], 4)],
        lw, 0.0, [h21_ref("H21-03"), h21_ref("H21-07"), h21_ref("H21-08")])
    add("CC-04", "field capability = B headroom x target upper end",
        sig(get("A9REV", rev("REV-10"))["B_headroom"] * get("H21", h21("H21-14"))[1], 4),
        get("H21", h21("H21-15")), 1e-3, [h21_ref("H21-14"), h21_ref("H21-15"), ref("A9REV", rev("REV-10"))])
    m = get("H21", h21("H21-24"))
    add("CC-05", "MC-1 floor mass = iron + copper (H2-1) = mass_power v2 A9B-16 evidence floor",
        sig(m["iron_kg"] + m["copper_kg"], 4),
        get("MP2", find("MP2", "/bom", "id", "A9B-16") + "/columns/EVIDENCE_FLOOR/value"), 1e-9,
        [h21_ref("H21-24"), ref("MP2", find("MP2", "/bom", "id", "A9B-16") + "/columns/EVIDENCE_FLOOR/value")])
    add("CC-06", "booked coil copper (mass_power v2) = H2-1 H21-24 copper (A9.2 sec. 8)",
        get("MP2", "/coil_mass_correction/booked_copper_kg"), m["copper_kg"], 1e-9,
        [ref("MP2", "/coil_mass_correction/booked_copper_kg"), h21_ref("H21-24")])
    c = get("A9REV", rev("REV-04"))
    add("CC-07a", "coil design ceiling = supplier continuous limit - 50 K (row 86)",
        sig(c["continuous_limit_C (supplier, not validated)"] - 50.0, 6), c["design_ceiling_C"], 1e-9,
        [ref("A9REV", rev("REV-04"))])
    fe_h21 = get("H21", "/materials/candidates/ARMCO_pure_iron/curie_C")[0]
    mt = re.search(r"Curie (\d+(?:\.\d+)?) degC", get("A9REV", rev("REV-06")))
    if not mt:
        raise SystemExit("REFUSED: REV-06 no longer states an iron Curie value; revisit CC-07")
    fe_rev = float(mt.group(1))
    add("CC-07", "iron Curie value used for the necessary ceiling: H2-1 (secondary, verify) vs A9-07 REV-06",
        fe_rev, fe_h21, 0.0,
        [ref("H21", "/materials/candidates/ARMCO_pure_iron/curie_C"), ref("A9REV", rev("REV-06"))],
        note="DISCREPANCY RECORDED, not resolved here: H2-1 carries 770 degC from a secondary source marked 'verify'; "
             "A9-07 REV-06 carries 754 degC from EXT-NBS-ARMCO1967 resistivity hysteresis ('presumably' the Curie "
             "transformation, lower end used). Either is a necessary ceiling only, never a use limit (F5-OQ-03)",
        recorded_discrepancy=True)
    r43 = get("A9REV", rev("REV-43"))
    add("CC-08", "A9-07 coil I2R thermal bound = 60 W (H2-5 v1 upper) x Ni-clad factor x 1.2",
        sig(get("H25", find("H25", "/design_parameters", "id", "H25-08") + "/value")[1] * r43["factor"] * 1.2, 4),
        r43["P_mag_20C_upper_W_used"], 1e-3,
        [ref("H25", find("H25", "/design_parameters", "id", "H25-08") + "/value"), ref("A9REV", rev("REV-43"))])
    return out


def h21_ref(pid: str) -> dict:
    return ref("H21", h21(pid))


# --------------------------------------------------------------------------------------------------------------------
# document
# --------------------------------------------------------------------------------------------------------------------
def build_document() -> dict:
    pins = verify_pins()
    a97_md = load("A97_MD")
    # A9.7 F5 bullets must be present verbatim in the pinned directive
    f5_block = a97_md.split("F5 — H-1 design closure", 1)[1].split("⸻", 1)[0]
    for b in A97_F5_BULLETS:
        if f"* {b}" not in f5_block:
            raise SystemExit(f"REFUSED: A9.7 F5 bullet not found verbatim: {b}")
    a92_md = load("A92_MD")
    for _, txt, _ in A92_ANODE_INVESTIGATION:
        if f"* {txt}" not in a92_md:
            raise SystemExit(f"REFUSED: A9.2 anode investigation item not found verbatim: {txt}")

    # evidence state that bounds this lane (fail closed if it changed: F5 would have to be revisited)
    members = get("ENS", "/members")
    promotable = get("VAL", "/decision/promotable")
    if members or promotable:
        raise SystemExit("REFUSED: an admitted Hall transport member / promotable candidate exists; the F5 Hall "
                         "response-domain statement must be revisited before rebuilding")

    params = build_parameters()
    a916_touched = A16.apply_to_parameters(params, FEMM, COUPLED)
    a919_touched = A19.apply_to_parameters(params)
    ids = [p["id"] for p in params]
    assert len(ids) == len(set(ids))

    counts: dict = {s: 0 for s in FREEZE_STATUSES}
    by_group: dict = {g: {s: 0 for s in FREEZE_STATUSES} for g in GROUPS}
    for p in params:
        counts[p["freeze_status"]] += 1
        by_group[p["group"]][p["freeze_status"]] += 1

    xdef = x_hall_definition()
    rp1 = get("H21", "/assumed_inputs/rp1_geometry/value")
    probes = {}
    for name, cdat in get("H21", "/channel/corners").items():
        for lh in (xdef["constraints"]["L_over_h_window"]):
            probes[f"{name} L/h {lh}"] = (cdat["h_mm"], cdat["d_mean_mm"], cdat["h_mm"] * lh)
    probes["RP-1 anchor (not a selection)"] = (rp1["h_mm"], rp1["d_mean_mm"], rp1["h_mm"] * rp1["L_over_h"])
    probe_rows = []
    for name, (h, d, L) in probes.items():
        for a in ("nominal_assumptions", "worst_case_assumptions"):
            r = geometric_admissibility(h, d, L, a, xdef)
            probe_rows.append({"probe": name, "h_mm": sig(h, 4), "d_mean_mm": sig(d, 4), "L_mm": sig(L, 4),
                               "assumptions": a, "status": r["status"], "violations": r["violations"],
                               "performance": r["performance"]})

    p5 = {}
    for key in ("P5B16", "P5B30"):
        lines = load(key).splitlines()
        src = " ".join(x.lstrip("# ").strip() for x in lines[1:3])
        src = src.split(" z from anode face", 1)[0]
        p5[key] = {"path": path_of(key), "sha256": PINS[key][1], "source_line": src,
                   "role": "REFERENCE_FOR_P5_ONLY"}

    m16 = []
    for rown, contrib in ((9, "channel windows (CH-02..CH-10), design point TBD_OWNER (CH-11), x_Hall admissibility "
                              "interface for F7"),
                          (10, "magnetic circuit items MC-01..MC-10, B(z) BZ-01..BZ-06, coil envelope CO-01..CO-14"),
                          (13, "TH-03 / EX-07 carried UNRESOLVED; no thermal verdict"),
                          (20, "AN-04 / AN-05 / MA-08: 316L REJECTED_AS_CURRENT_BASELINE, FINAL_ANODE_MATERIAL OPEN"),
                          (21, "AN-06 + anode_investigation AI-01..AI-08: heat path UNRESOLVED")):
        rp = find("M16", "/rows", "row", rown)
        m16.append({"m16_row": rown, "key": get("M16", rp + "/key"), "name": get("M16", rp + "/name"),
                    "v4_state": get("M16", rp + "/execution_state"), "proposed_state": get("M16", rp + "/execution_state"),
                    "state_change": False, "f5_contribution": contrib, "source": ref("M16", rp)})

    doc = {
        "schema": "h1_freeze_candidate_v1",
        "id": "h1_freeze_candidate_v1",
        "title": "H-1 freeze-candidate engineering-article definition (A9.7 F5 H-1 design closure)",
        "lane": "fo_a9_7_f5_h1_freeze_candidate",
        "directive": "A9.7 F5 (docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md)",
        "date": DATE,
        "base_commit": BASE_COMMIT,
        "generated_by": REL_SELF,
        "companion_document": "docs/hardware/h1_freeze_candidate/H1_FREEZE_CANDIDATE.md",
        "test": "tests/test_h1_freeze_candidate.py",
        "status": "DRAFT_IMPLEMENTATION_FIRST_PENDING_CONSOLIDATED_VERIFICATION",
        "architecture_status": "INVESTIGATION_HYPOTHESIS",
        "article_freeze_state": "NOT_FROZEN (OPEN / TBD items remain; FREEZE_CANDIDATE items are candidates only)",
        "lock1_release": A16.lock1_release_status(params, None),
        "configuration_items": ["H-1", "MC-1"],
        "interface_planes": ["HALL_INLET_Z0", "IP-EXIT", "IP-NEU (datum owned by the ICD / F6)"],
        "standing_facts": {
            "credible_hall_set": "EMPTY (hallthruster_bridge/ensemble/transport_ensemble_v0.json members = [])",
            "p5_n2_v1": "INCONCLUSIVE (VALIDATION_RELEASE_v1 promotable = [])",
            "hall_response_maps": "no admitted domain exists; none is used",
            "icp45": "NOT_EVALUATED (I_d,max,H1 not registered; no P1 data)",
            "p1_p2": "no data",
            "a9": A19.A9_STANDING,
            "a9_2_statuses": get("A92", "/decisions/a9_10_statuses"),
        },
        "what_this_is_not": [
            "not a Hall performance prediction: no thrust, T - D, discharge current, efficiency or plasma state",
            "not based on the withdrawn 0-D Hall model, any screening candidate or any unadmitted closure",
            "not a transfer of P5 geometry or B(z): the Peterson 2001 profile is a reference for P5 only",
            "not a selection, ranking, winner or PASS; nothing is frozen by this lane",
            "not a modification of any H2 v1, A9 or decision file (all read-only)",
            "not wired into abep_sim/archengine.py",
        ],
        "freeze_status_vocabulary": FREEZE_STATUSES,
        "evidence_classes": list(EVIDENCE_CLASSES),
        "evidence_class_rule": "evidence_class is one of evidence_classes for every value; null for a TBD value; "
                               "qualifiers go to evidence_note (docs/EVIDENCE.md: quantity type, not evidence level)",
        "freeze_points": list(FREEZE_POINTS),
        "pins": pins,
        "consumed_deliverables": {k: {"path": v, "sha256": sha_of(k)} for k, v in CONSUMED.items()},
        "pending_parallel_lanes": {k: {"lane": v[0], "reference": v[1]} for k, v in PENDING_LANES.items()},
        "a9_7_f5_coverage": [{"bullet": b, "groups": g,
                              "parameters": [p["id"] for p in params if p["group"] in g]}
                             for b, g in A97_F5_BULLETS.items()],
        "groups": GROUPS,
        "parameters": params,
        "freeze_rollup": {"counts": counts, "by_group": by_group, "total": len(params)},
        "hall_response_domain": {
            "admitted_members": members,
            "p5_n2_v1_promotable": promotable,
            "p5_n2_v1_inconclusive": get("VAL", "/decision/inconclusive"),
            "admitted_domains": [],
            "statement": "the design-synthesis layer may use Hall response maps only inside admitted domains; there "
                         "are none (credible set empty, P5-N2 v1 INCONCLUSIVE). Screening candidates never produce "
                         "design Hall maps. Every Hall performance quantity is NOT_EVALUATED for every H-1 parameter "
                         "set, and the H-1 design point cannot be chosen on Hall performance",
            "performance_outputs": {q: "NOT_EVALUATED" for q in PERFORMANCE_QUANTITIES},
            "sources": [ref("ENS", "/members"), ref("VAL", "/decision")],
        },
        "bz_reference": {
            "vyovrinda_specific_bz_evidence": "NONE (no FEMM of MC-1, no measured H-1 map)",
            "h1_bz_target": "TBD beyond the H2-1 model-derived envelope and inferred shape (H1F-BZ-02 / BZ-03, OPEN)",
            "p5_files": p5,
            "rule": "the P5 Peterson 2001 B_r(z) digitization in hallthruster_bridge/bfield/ is a reference for P5 "
                    "only (P5 validation cases); no P5 magnitude, gradient, peak position or coil setting is "
                    "transferred to H-1 as a design value (HW-H1-03: P5, ECHT and 0-D defaults are forbidden design "
                    "sources)",
        },
        "anode_investigation": [
            {"id": i, "item_verbatim": t, "owner_or_evidence_route": r, "status": "OPEN",
             "source": ref("A92_MD", "", note="A9.2 sec. 4 verbatim list")}
            for i, t, r in A92_ANODE_INVESTIGATION],
        "anode_statuses": {k: get("P4", f"/fixed_statuses/{k}/status")
                           for k in ("316L_FLIGHT_ANODE", "FINAL_ANODE_MATERIAL", "ANODE_THERMAL_CLOSURE",
                                     "ANODE_BASELINE")},
        "x_hall_design_space": {
            "purpose": "interface to F7 / F8 (x_Hall block of the common design vector); bounds only, no objective",
            "definition": xdef,
            "admissibility_function": f"{REL_SELF}:geometric_admissibility (fail closed; statuses "
                                      "WITHIN_DECLARED_GEOMETRIC_WINDOWS / OUTSIDE_DECLARED_GEOMETRIC_WINDOWS / "
                                      "OUT_OF_DOMAIN; performance always NOT_EVALUATED; never PASS)",
            "probe_evaluations": probe_rows,
        },
        "consistency_checks": consistency_checks(),
        "femm_analysis_points": A16.femm_analysis_points(probe_rows),
        "interface_demands": interface_demands(),
        "open_owner_questions": A16.answered_open_questions(open_owner_questions()),
        "a9_16_owner_answers_applied": A16.owner_answers_applied(),
        "a9_16_touched_parameters": a916_touched,
        "flight_architecture": A19.A.FLIGHT_ARCHITECTURE,
        "a9_19_owner_answers_applied": A19.owner_answers_applied(),
        "a9_19_touched_parameters": a919_touched,
        "existing_owner_questions_touched": [
            {"id": q, "status": get("OQ5", find("OQ5", "/rows", "id", q) + "/status"),
             "v4_status": get("OQ4", find("OQ4", "/rows", "id", q) + "/status"),
             "source": ref("OQ5", find("OQ5", "/rows", "id", q))}
            for q in ("MQ-03", "OQ-A907-04", "OQ-A907-05", "OQ-A907-06", "OQ-A907-08", "P1Q-06", "OQ-RFQV2-10",
                      "P4-OQ-01", "P4-OQ-02", "P4-OQ-04")],
        "m16_impact": m16,
        "key_findings": key_findings(params, counts),
        "compliance": {
            "no_hall_performance": True,
            "no_withdrawn_0d_model": True,
            "no_p5_transfer": True,
            "no_winner_no_pass": True,
            "read_only_inputs": True,
            "archengine_untouched": True,
            "lane_paths": ["docs/hardware/h1_freeze_candidate/", "tests/test_h1_freeze_candidate.py"],
            "parallel_lanes_not_imported": True,
            "no_contact": "no persons, labs or suppliers contacted; no new web source cited",
        },
    }
    return doc


def interface_demands() -> list:
    F4 = PENDING_LANES["F4"][1]
    F6 = PENDING_LANES["F6"][1]
    T = "TBD"
    d = [
        # H-1 <- F4 (what H-1 needs at HALL_INLET_Z0)
        ("IFD-F4-01", "H-1 <- F4", F4, "species-resolved mass flow mdot_s (N2, O2, O, Xe) delivered at HALL_INLET_Z0",
         "TBD - F4 output; context only: owner nominal sizing flow ~1.3 mg/s and characterization range ~0.38-3.2 "
         "mg/s total delivered (row 73, H1F-CH-12)", "mg/s per species", T, "LOCK-1"),
        ("IFD-F4-02", "H-1 <- F4", F4, "feed pressure P at IF-A5 / HALL_INLET_Z0",
         "TBD - depends on the H-1 inlet conductance (H1F-IN-04), itself TBD", "Pa", T, "LOCK-1"),
        ("IFD-F4-03", "H-1 <- F4", F4, "feed temperature T at HALL_INLET_Z0", "TBD", "K", T, "LOCK-1"),
        ("IFD-F4-04", "H-1 <- F4", F4, "species mole fractions x_s at HALL_INLET_Z0 (incl. atomic-O fraction after "
                                       "recombination; ground O2-bearing points labelled NO_ATOMIC_O)",
         "TBD", "-", T, "LOCK-1"),
        ("IFD-F4-05", "H-1 <- F4", F4, "transient quality: settling after a flow-setpoint step, pressure ripple, "
                                       "composition drift, start-up / Xe-to-air transition transient",
         "TBD - metric definitions requested from F4; acceptance tolerances cannot be derived by H-1 now (no "
         "admitted Hall response map); they need Phase-1 inlet-state sensitivity data", "s; Pa; -", T, "LOCK-2"),
        ("IFD-F4-06", "H-1 <- F4", F4, "Xe anode-feed flow in the bounded Xe mode (A9B-11 branch)", "TBD",
         "mg/s", T, "LOCK-1"),
        ("IFD-F4-07", "H-1 <- F4", F4, "particulate / contamination limit at the distributor (filter function F2 "
                                       "carried through F4)", "TBD", "-", T, "LOCK-1"),
        # H-1 -> F4
        ("IFS-F4-01", "H-1 -> F4", F4, "inlet annulus geometry (h, d_mean windows at z = 0)",
         get("H21", "/interface_demands/15/value"), "mm", "OPEN (H1F-IN-03)", "LOCK-1"),
        ("IFS-F4-02", "H-1 -> F4", F4, "H-1 inlet conductance / back-pressure law", "TBD - after the design point and "
                                                                                   "distributor are frozen (H1F-IN-04)",
         "m^3/s", T, "LOCK-1"),
        ("IFS-F4-03", "H-1 -> F4", F4, "ground characterization flow range H-1 must be fed over (not a flight "
                                       "qualification)", [0.38, 3.2], "mg/s", "OWNER_GIVEN (row 73)", "NOW"),
        # F1 / F2 / F3: no direct physical interface; via F4
        ("IFD-F1-01", "H-1 <- F1 (via F4)", PENDING_LANES["F1"][1], "captured species flow feeding F3 / F4; no "
                                                                    "direct H-1 interface", "n/a", "-",
         "NO_DIRECT_INTERFACE", "n/a"),
        ("IFD-F2-01", "H-1 <- F2 (via F4)", PENDING_LANES["F2"][1], "contamination / protection function relevant to "
                                                                    "the H-1 distributor and anode (IFD-F4-07)", "TBD",
         "-", T, "LOCK-1"),
        ("IFD-F3-01", "H-1 <- F3 (via F4)", PENDING_LANES["F3"][1], "compressor outlet composition x_s,out and "
                                                                    "temperature that F4 transforms into IFD-F4-03/04",
         "TBD", "-; K", T, "LOCK-1"),
        # H-1 <-> F6
        ("IFS-F6-01", "H-1 -> F6", F6, "IP-EXIT datum (z = L) and neutralizer-agnostic exit face", "H1F-EX-01 / EX-02",
         "-", "FREEZE_CANDIDATE", "NOW"),
        ("IFS-F6-02", "H-1 -> F6", F6, "channel OD window at IP-EXIT (plume source annulus)",
         get("H21", h21("H21-05")), "mm", "OPEN (H1F-CH-06 / EX-04)", "LOCK-1"),
        ("IFS-F6-03", "H-1 -> F6", F6, "MC-1 stray field in the ICP volume (Hall magnetic-field disturbance input)",
         "TBD - FEMM + measured map (H1F-EX-05)", "G", T, "LOCK-1"),
        ("IFS-F6-04", "H-1 -> F6", F6, "allowable B(z) field change epsilon_B caused by the ICP module",
         "TBD - measured H-1 sensitivity (H1F-BZ-06, row 67)", "-", T, "LOCK-2"),
        ("IFS-F6-05", "H-1 -> F6", F6, "H-1 exit-face radiating surfaces and temperatures for the view-factor objective",
         "TBD - coupled model (H1F-EX-07)", "m^2; K", T, "LOCK-1"),
        ("IFD-F6-01", "H-1 <- F6", F6, "axial standoff, aperture, envelope / keep-out of the ICP module (ICP-02/04/07)",
         "TBD", "mm", T, "LOCK-1"),
        ("IFD-F6-02", "H-1 <- F6", F6, "ICP module heat into H-1 (ICP-43) and view obstruction", "TBD", "W; -", T,
         "LOCK-1"),
        ("IFD-F6-03", "H-1 <- F6", F6, "ferromagnetic content of the ICP module near MC-1 (ICP-32: none in v1)",
         get("ICD", icd("ICP-32", "value")), "-", "OWNER_GIVEN (ICD ICP-32)", "NOW"),
        # F0 / F7-F8 / F9
        ("IFS-F0-01", "H-1 -> F0", PENDING_LANES["F0"][1], "F5 computational load", "builder only (JSON reads and "
                                                                                      "arithmetic, well under 10 s "
                                                                                      "CPU); no hotspot to profile",
         "s", "INFORMATIONAL", "n/a"),
        ("IFS-F7-01", "H-1 -> F7/F8", PENDING_LANES["F7F8"][1], "x_Hall bounds, constraints and admissibility "
                                                                "function (x_hall_design_space)",
         "see x_hall_design_space", "mm", "OPEN", "LOCK-1"),
        ("IFS-F7-02", "H-1 -> F7/F8", PENDING_LANES["F7F8"][1], "Hall performance for any x_Hall (T, I_d, efficiency, "
                                                                "Q_reject share)",
         "NOT_EVALUATED - no admitted Hall response map (hall_response_domain)", "mN; A; -; W", "NOT_EVALUATED",
         "after-evidence"),
        ("IFS-F9-01", "H-1 -> F9", PENDING_LANES["F9"][1], "H-1 geometry / magnetic circuit / anode approach rows "
                                                           "(VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | "
                                                           "FREEZE_STATUS)", "parameters", "-", "DEFINED", "NOW"),
        # existing deliverables
        ("IFS-P3-01", "H-1 -> P3", path_of("P3") + " (P3-IF-N07)", "frozen H-1 geometry, surface-node map, "
                                                                    "conductances, emittances",
         "TBD - design point TBD_OWNER (H1F-CH-11)", "m; W/K; -", T, "LOCK-1"),
        ("IFD-P3-01", "H-1 <- P3", path_of("P3") + " (P3-IF-S07 / S04)", "coupled T_operating of anode, coils, poles, "
                                                                          "walls; equivalent ICP heat into PO / BP",
         "TBD_AFTER_EVIDENCE (ICP_COUPLED_THERMAL, ANODE_THERMAL_CLOSURE UNRESOLVED)", "K; W", T, "after-evidence"),
        ("IFS-P4-01", "H-1 -> P4", path_of("P4") + " (ID-03)", "anode geometry, joints, feed-tube path",
         "TBD (H1F-AN-03, AN-06)", "mm", T, "before-HI-S1"),
        ("IFD-P4-01", "H-1 <- P4", path_of("P4") + " (APP-ANODE)", "validated continuous-use limits, k(T), density, "
                                                                    "emittance per anode candidate",
         "TBD (FINAL_ANODE_MATERIAL OPEN)", "K; W/(m K); kg/m^3; -", T, "after-evidence"),
        ("IFS-MP2-01", "H-1 -> mass/power v2", path_of("MP2") + " (A9B-15, A9B-16, MPV2-N03)",
         "Hall head CBE (channel ceramics, anode, body, fasteners) and the anode heat-path hardware mass",
         "TBD - design point TBD_OWNER; MC-1 magnetic-parts floor 3.504 kg unchanged (H1F-MC-08)", "kg", T, "LOCK-1"),
        ("IFS-PPU-01", "H-1 -> PPU (H2-4 / mass_power v2 power slots hall_magnet_*)",
         "docs/hardware/h2/h2_4_ppu_bus/ (verified v1; A9 revisions REV-51..63)",
         "coil-supply rating matched to the FEMM-sized coils (per-coil I, V, P incl. trim)",
         "TBD - RP-1 anchor values in H1F-CO-03..CO-06 are not a rating", "A; V; W", T, "LOCK-1"),
    ]
    out = []
    for i, dirn, cp, q, v, u, st, fp in d:
        out.append({"id": i, "direction": dirn, "counterpart": cp, "quantity": q, "value": v, "units": u,
                    "status": st, "freeze_point": fp})
    return out


def open_owner_questions() -> list:
    return [
        {"id": "F5-OQ-01", "question": "Authorize FEMM-class axisymmetric magnetostatics of MC-1 at analysis points "
                                       "inside the H-1 windows (the RP-1 anchor plus the window corners that the "
                                       "solid-core inner-coil floor admits, x_hall_design_space.probe_evaluations) as "
                                       "ANALYSIS points, explicitly not a design selection?",
         "proposed_answer": "yes; FEMM is the M16 row 9/10 blocking evidence and needs concrete geometry",
         "blocks": ["H1F-CH-11", "H1F-MC-04..06", "H1F-BZ-01..05", "H1F-CO-02..07", "H1F-EX-05"]},
        {"id": "F5-OQ-02", "question": "With no admitted Hall response map, should the H-1 channel design point be "
                                       "selected now on non-performance criteria only (FEMM magnetic feasibility, "
                                       "coupled thermal margins under row 86, mass against AL-04, packaging, "
                                       "manufacturability), leaving thrust capability to the Phase-1 / Phase-3 "
                                       "measurement, or deferred until pre-S1 adjustable-anode development data exist?",
         "proposed_answer": "select on non-performance criteria (thrust is the T_measured gate, not a sizing input, "
                            "as H2-1 channel.thrust_bound already states); the pre-S1 insert (row 75) remains the "
                            "only L adjustment",
         "blocks": ["H1F-CH-11"]},
        {"id": "F5-OQ-03", "question": "Iron Curie value for the necessary pole/core ceiling: H2-1 carries 770 degC "
                                       "(secondary source, 'verify'), A9-07 REV-06 carries 754 degC (EXT-NBS-ARMCO1967 "
                                       "resistivity hysteresis). Use the lower value as the necessary ceiling until "
                                       "a grade-specific sourced value exists?",
         "proposed_answer": "yes (conservative); it stays a necessary ceiling, never the use limit (B_sat(T) governs)",
         "blocks": ["H1F-MA-04"]},
        {"id": "F5-OQ-04", "question": "Accept the FREEZE_CANDIDATE items of this definition as the basis of the "
                                       "H-1 LOCK-1 design release, with every OPEN / TBD item listed as a release "
                                       "blocker (HW-H1-03 drawing id / revision / sha256)?",
         "proposed_answer": "owner call",
         "blocks": ["H-1 design release"]},
        {"id": "F5-OQ-05", "question": "Accept the H2-1 model-derived peak-field target band (r_Le <= 0.1 h over T_e "
                                       "10-30 eV, H1F-BZ-03) as the FEMM design-target band for H-1 (not a transport "
                                       "optimization), or require a narrower band before FEMM?",
         "proposed_answer": "accept as the FEMM target band; narrow only with H-1 measurements",
         "blocks": ["H1F-BZ-03", "H1F-BZ-04"]},
    ]


def key_findings(params: list, counts: dict) -> list:
    return [
        f"F5-K1 H-1 definition: {len(params)} parameters; FREEZE_CANDIDATE {counts['FREEZE_CANDIDATE']}, OPEN "
        f"{counts['OPEN']}, TBD_AFTER_EVIDENCE {counts['TBD_AFTER_EVIDENCE']}, TBD_OWNER {counts['TBD_OWNER']}. "
        "The article is NOT frozen; every FREEZE_CANDIDATE is an owner-given decision, convention or rule.",
        "F5-K2 the channel design point (h, d_mean, L) is not selected: windows exist (xenon-derived rules, hypotheses "
        "for air species), but no Hall performance can discriminate inside them (credible set empty, P5-N2 v1 "
        "INCONCLUSIVE); the owner rule (A9.14 F5-OQ-01 / F5-OQ-02) selects an ENGINEERING_FREEZE_CANDIDATE point on "
        "non-performance criteria after the authorised FEMM analysis points (FEMM_AUTHORISED_NOT_RUN).",
        "F5-K3 magnetic circuit decided at topology level only (T2 shielded, EM-only, FeCo-2V inner / pure-iron outer, "
        "ceramic-insulated copper coils); all dimensions, ampere-turns, coil currents and B(z) are lumped-circuit "
        "values at the RP-1 calculation anchor or TBD pending FEMM.",
        "F5-K4 B(z): no Vyovrinda-specific evidence exists; the H-1 target is the H2-1 model-derived envelope and an "
        "inferred shape (OPEN); the P5 Peterson 2001 profile is a reference for P5 only and no P5 value is used.",
        "F5-K5 anode: 316L REJECTED_AS_CURRENT_BASELINE; FINAL_ANODE_MATERIAL OPEN (22 P4 candidates, all "
        "INCOMPLETE_EVIDENCE); heat-removal path UNRESOLVED with the eight A9.2 sec. 4 investigation items carried; no "
        "anode temperature target is set (row 87).",
        "F5-K6 coil envelope carried with the A9.2 sec. 8 correction: 1.579 kg is the complete-coil copper estimate "
        "at RP-1 f_NI 2 (booked), 0.136 kg is the 60 W fixed-NI sensitivity basis and never the coil mass.",
        "F5-K7 inlet interface: H-1 needs mdot_s, P, T, x_s and transient quality from F4, all TBD; transient "
        "tolerances cannot be derived by H-1 today (no admitted Hall map) and need Phase-1 sensitivity data.",
        "F5-K8 iron Curie discrepancy recorded (770 vs 754 degC between H2-1 and A9-07); the owner uses 754 degC as the "
        "conservative necessary ceiling, never the usable limit (A9.14 F5-OQ-03).",
        "F5-K9 LOCK-1 release (A9.14 F5-OQ-04): RELEASE_BLOCKED - every non-FREEZE_CANDIDATE item is an explicit "
        "blocker and the release needs the drawing id, revision and content hash.",
    ]


# --------------------------------------------------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------------------------------------------------
def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _fmt(v) -> str:
    if isinstance(v, str):
        s = v
    else:
        s = json.dumps(v, ensure_ascii=False)
    s = s.replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= 400 else s[:397] + "..."


def _src(srcs: list) -> str:
    def one(s):
        t = f"`{s['path']}`{'' if s['pointer'] == '/' else ' ' + s['pointer']}"
        if s.get("note", "").startswith("owner row"):
            t += f" ({s['note']})"
        return t
    return "; ".join(one(s) for s in srcs)


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a(f"# {doc['title']}")
    a("")
    a(f"> Generated by `{doc['generated_by']}` from `h1_freeze_candidate_v1.json`. Do not edit by hand (`--check` "
      "verifies both files).")
    a("")
    a("| | |")
    a("|---|---|")
    for k in ("lane", "directive", "status", "architecture_status", "article_freeze_state", "base_commit", "test"):
        a(f"| {k} | {_fmt(doc[k])} |")
    a("")
    a("## Standing facts")
    a("")
    for k, v in doc["standing_facts"].items():
        a(f"* **{k}**: {_fmt(v)}")
    a("")
    a("## What this is not")
    a("")
    for s in doc["what_this_is_not"]:
        a(f"* {s}")
    a("")
    a("## Freeze-status vocabulary")
    a("")
    for k, v in doc["freeze_status_vocabulary"].items():
        a(f"* **{k}**: {v}")
    a("")
    a(f"Evidence classes: {', '.join(doc['evidence_classes'])}. {doc['evidence_class_rule']}.")
    a("")
    a("## Rollup")
    a("")
    a("| group | " + " | ".join(FREEZE_STATUSES) + " |")
    a("|---|" + "---|" * len(FREEZE_STATUSES))
    for g, name in doc["groups"].items():
        a(f"| {g} {name} | " + " | ".join(str(doc["freeze_rollup"]["by_group"][g][s]) for s in FREEZE_STATUSES) + " |")
    a("| **total** | " + " | ".join(str(doc["freeze_rollup"]["counts"][s]) for s in FREEZE_STATUSES) + " |")
    a("")
    a("A9.7 F5 bullet coverage:")
    a("")
    for c in doc["a9_7_f5_coverage"]:
        a(f"* `{c['bullet']}` -> {', '.join(c['parameters'])}")
    a("")
    a("## Parameters (VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS)")
    for g, name in doc["groups"].items():
        a("")
        a(f"### {g} - {name}")
        a("")
        a("| id | parameter | VALUE | units | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS | freeze point |")
        a("|---|---|---|---|---|---|---|---|---|")
        for p in doc["parameters"]:
            if p["group"] != g:
                continue
            ec = p["evidence_class"] or "- (TBD)"
            if p.get("evidence_note"):
                ec += f" ({p['evidence_note']})"
            a(f"| {p['id']} | {_fmt(p['name'])} | {_fmt(p['value'])} | {_fmt(p['units'])} | {_fmt(p['tolerance'])} | "
              f"{_fmt(ec)} | {_fmt(_src(p['source']))} | **{p['freeze_status']}** | {p['freeze_point']} |")
    a("")
    a("## Evidence needed to move each non-candidate item to FREEZE_CANDIDATE")
    a("")
    a("| id | FREEZE_STATUS | evidence needed |")
    a("|---|---|---|")
    for p in doc["parameters"]:
        if p["freeze_status"] != "FREEZE_CANDIDATE":
            a(f"| {p['id']} | {p['freeze_status']} | {_fmt('; '.join(p['evidence_to_freeze_candidate']))} |")
    a("")
    hr = doc["hall_response_domain"]
    a("## Hall response domain")
    a("")
    a(hr["statement"] + ".")
    a("")
    a(f"Admitted members: {hr['admitted_members']}; P5-N2 v1 promotable: {hr['p5_n2_v1_promotable']}; admitted "
      f"domains: {hr['admitted_domains']}.")
    a("")
    a("| quantity | status |")
    a("|---|---|")
    for q, s in hr["performance_outputs"].items():
        a(f"| {q} | {s} |")
    a("")
    bz = doc["bz_reference"]
    a("## B(z): H-1 target vs the P5 reference")
    a("")
    a(f"* Vyovrinda-specific B(z) evidence: **{bz['vyovrinda_specific_bz_evidence']}**")
    a(f"* H-1 target: {bz['h1_bz_target']}")
    a(f"* Rule: {bz['rule']}")
    for v in bz["p5_files"].values():
        a(f"* `{v['path']}` sha256 `{v['sha256']}` - {v['role']} ({v['source_line']})")
    a("")
    a("## Anode: statuses and A9.2 sec. 4 investigation list")
    a("")
    for k, v in doc["anode_statuses"].items():
        a(f"* {k}: **{v}**")
    a("")
    a("| id | item (verbatim A9.2) | route | status |")
    a("|---|---|---|---|")
    for x in doc["anode_investigation"]:
        a(f"| {x['id']} | {x['item_verbatim']} | {x['owner_or_evidence_route']} | {x['status']} |")
    a("")
    xs = doc["x_hall_design_space"]
    a("## x_Hall design space (interface to F7 / F8)")
    a("")
    a(f"{xs['purpose']}. Admissibility: {xs['admissibility_function']}.")
    a("")
    a(f"Constraints: {_fmt({k: v for k, v in xs['definition']['constraints'].items() if k != 'inner_coil_solid_core_floor_mm'})}; "
      "inner-coil solid-core floor by h from A9-07 REV-01. Not evaluated: "
      + "; ".join(xs["definition"]["not_evaluated"]) + ".")
    a("")
    a("| probe | h | d_mean | L | assumptions | status | violations | performance |")
    a("|---|---|---|---|---|---|---|---|")
    for r in xs["probe_evaluations"]:
        a(f"| {r['probe']} | {r['h_mm']} | {r['d_mean_mm']} | {r['L_mm']} | {r['assumptions']} | {r['status']} | "
          f"{_fmt('; '.join(r['violations']) or '-')} | {r['performance']} |")
    a("")
    a("## Consistency checks (arithmetic re-derivations; never a PASS)")
    a("")
    a("| id | check | computed | reported | result | note |")
    a("|---|---|---|---|---|---|")
    for c in doc["consistency_checks"]:
        a(f"| {c['id']} | {_fmt(c['check'])} | {_fmt(c['computed'])} | {_fmt(c['reported'])} | {c['result']} | "
          f"{_fmt(c.get('note', ''))} |")
    a("")
    a("## Interface demands")
    a("")
    a("| id | direction | counterpart | quantity | value | units | status | freeze point |")
    a("|---|---|---|---|---|---|---|---|")
    for x in doc["interface_demands"]:
        a(f"| {x['id']} | {x['direction']} | {_fmt(x['counterpart'])} | {_fmt(x['quantity'])} | {_fmt(x['value'])} | "
          f"{_fmt(x['units'])} | {_fmt(x['status'])} | {x['freeze_point']} |")
    a("")
    a("## Owner questions raised by F5 (answered by A9.14)")
    a("")
    for q in doc["open_owner_questions"]:
        a(f"* **{q['id']}** {q['question']} *Proposed:* {q['proposed_answer']} (blocks: {', '.join(q['blocks'])}) "
          f"**{q['status']}** {q['decision_code']} - {q['decision']}")
    a("")
    a("## A9.16 owner decisions applied")
    a("")
    lr = doc["lock1_release"]
    a(f"LOCK-1 release: **{lr['status']}** ({lr['blocker_count']} blockers; missing drawing fields: "
      f"{', '.join(lr['missing_drawing_fields']) or 'none'}). {lr['rule']}.")
    a("")
    fp = doc["femm_analysis_points"]
    a(f"FEMM analysis points: **{fp['status']}** ({fp['role']}); authorised: "
      + ", ".join(x["probe"] for x in fp["points"] if x["authorised_analysis_point"]) + ".")
    a("")
    a("| decision | question | code | records | how applied |")
    a("|---|---|---|---|---|")
    for r in doc["a9_16_owner_answers_applied"]:
        a(f"| {r['decision']} | {r['question_id']} | {r['decision_code']} | {', '.join(r['record_ids'])} | "
          f"{_fmt(r['how_applied'])} |")
    a("")
    a("A9.19 / A9.20 owner decisions applied (one Hall + one RF/ICP neutralizer, supply modes AIR_PRIMARY / "
      "XE_CONTINGENCY, no conventional hollow cathode; C1 ground-only):")
    a("")
    a("| decision | item | records | how applied |")
    a("|---|---|---|---|")
    for r in doc["a9_19_owner_answers_applied"]:
        a(f"| {r['decision']} | {r['question_id']} | {', '.join(r['record_ids'])} | {_fmt(r['how_applied'])} |")
    a("")
    a("Existing owner questions touched (not restated): " + ", ".join(
        f"{q['id']} ({q['status']})" for q in doc["existing_owner_questions_touched"]) + ".")
    a("")
    a("## M16 impact")
    a("")
    a("| row | key | v4 state | proposed | change | F5 contribution |")
    a("|---|---|---|---|---|---|")
    for m in doc["m16_impact"]:
        a(f"| {m['m16_row']} | {m['key']} | {m['v4_state']} | {m['proposed_state']} | {m['state_change']} | "
          f"{_fmt(m['f5_contribution'])} |")
    a("")
    a("## Key findings")
    a("")
    for k in doc["key_findings"]:
        a(f"* {k}")
    a("")
    a("## Inputs")
    a("")
    a("Pinned (immutable; the builder refuses on mismatch):")
    a("")
    for v in doc["pins"].values():
        a(f"* `{v['path']}` `{v['sha256']}`")
    a("")
    a("Consumed verified deliverables (sha256 at build time; `--check` reports drift):")
    a("")
    for v in doc["consumed_deliverables"].values():
        a(f"* `{v['path']}` `{v['sha256']}`")
    a("")
    a("Parallel A9.7 lanes (referenced only, never imported):")
    a("")
    for k, v in doc["pending_parallel_lanes"].items():
        a(f"* {k} `{v['lane']}`: {v['reference']}")
    a("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify JSON and MD are current; write nothing")
    args = ap.parse_args(argv)
    doc = build_document()
    js, md = dumps(doc), render_md(doc)
    if args.check:
        bad = [p for p, want in ((JSON_PATH, js), (MD_PATH, md))
               if not p.is_file() or p.read_text(encoding="utf-8") != want]
        if bad:
            print("STALE: " + ", ".join(str(p.relative_to(REPO)) for p in bad) + " (re-run the builder)")
            return 1
        print("OK: h1_freeze_candidate_v1.json and H1_FREEZE_CANDIDATE.md are current")
        return 0
    JSON_PATH.write_text(js, encoding="utf-8")
    MD_PATH.write_text(md, encoding="utf-8")
    print(f"wrote {JSON_PATH.relative_to(REPO)} and {MD_PATH.relative_to(REPO)} ({len(doc['parameters'])} parameters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
