#!/usr/bin/env python3
"""Deterministic builder of the A9 downstream ICP-neutralizer ICD (fo_a9_03_icp_neutralizer_icd, trigger T_A9_03_ICP_ICD).

Writes
  schemas/interfaces/icp_neutralizer_icd_v1.json               (machine-readable ICD)
  docs/interfaces/icp_neutralizer/ICP_NEUTRALIZER_ICD.md       (companion document, rendered from the same data)

Governing owner decision: A9 (docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json) and
the owner's 147 answers (docs/decisions/OD_2026_09_29_owner_answers_147.json); both are pinned by sha256 below and the
build refuses to run if either changed. Owner answers are cited by row number; every cited row is resolved in the answers
file and its verbatim answer is fingerprinted.

Rules implemented here
  * every numeric value is either an owner-given value (cited by row), a value COPIED from a verified repository
    deliverable (path + RFC 6901 JSON pointer + sha256), a published-analog value from the open-access Takahashi et al.
    2024 article with page/figure provenance (annex only, never a Vyovrinda value), a deterministic arithmetic bound on
    owner-given values (ICP-36: RF-only partial allocation term, not a module heat-load bound), or ``null`` with "TBD - requires <what>";
  * values owned by the parallel A9 lanes (A9-01, A9-02, A9-04, A9-05) are written "PENDING <lane path>" and never filled;
  * no Hall transport closure, screening candidate, superseded 0-D Hall model or withdrawn number is read; nothing here
    predicts thrust, efficiency, discharge current, neutralizer electron current or plasma state;
  * missing inputs raise (CLAUDE.md rule 3: no silent fallback).

Usage
  python docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py          # write both files
  python docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py --check  # exit 1 if either file differs

Standard library only. Pure: reads repository files and writes the two outputs; not wired into archengine.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ---- A9-10 reconciliation overlay (fo_a9_10_integration): declared, machine-checked changes applied after the build
import importlib.util as _a910_ilu  # noqa: E402
_A910_SPEC = _a910_ilu.spec_from_file_location(
    "a9_10_overlay", str(ROOT) + "/docs/experiments/hall_icp/integration/a9_10_overlay.py")
A910 = _a910_ilu.module_from_spec(_A910_SPEC)
_A910_SPEC.loader.exec_module(A910)

OUT_JSON = "schemas/interfaces/icp_neutralizer_icd_v1.json"
OUT_MD = "docs/interfaces/icp_neutralizer/ICP_NEUTRALIZER_ICD.md"
THIS_SCRIPT = "docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py"
TEST = "tests/test_icp_neutralizer_icd.py"
BASE_COMMIT = "0a430bb5588a438f7c8485c6d16f40ed0d402c4c"

CONFIGURATIONS = ("hall_c1_reference", "hall_icp_neutralizer")
OUTCOME_VOCABULARY = ("hall_c1_reference", "hall_icp_neutralizer", "NO_VIABLE_CASE")
STATUS_VOCABULARY_NOT_OUTCOME = ("OPEN",)
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
ITEM_STATUSES = ("OWNER_GIVEN", "SOURCED", "PROPOSED", "TBD", "PENDING", "DERIVED_BOUND")
TBD = "TBD - requires"

# ----------------------------------------------------------------------------------------------------------------------
# pinned inputs
# ----------------------------------------------------------------------------------------------------------------------
# Immutable owner decisions: expected sha256 is fixed here; a mismatch aborts the build.
DECISIONS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976"),
    "A4": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json", None),
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json", None),
    "A6": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json", None),
    "A7": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json", None),
}
# Verified deliverables read by this lane (sha256 recorded at build time; the test re-checks them).
# Mutable governance files (lane/trigger registries, trigger ledgers, runtime_state.json) are deliberately NOT pinned.
DELIVERABLES = {
    "H21": "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json",
    "H22": "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json",
    "H23": "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
    "H24": "docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json",
    "H25": "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json",
    "H26": "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json",
    "H27": "docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
    "INS": "docs/experiments/instrumentation/instrumentation_definition_v1.json",
    "HW": "docs/experiments/hardware/hardware_requirements_v1.json",
    "M16": "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
}
# Historical artifacts: read for reusable structure only, never edited (A9 supersession rule).
HISTORICAL = {
    "PIM_MD": "docs/interfaces/preionizer_module/PREIONIZER_MODULE_ICD.md",
    "PIM_PY": "docs/interfaces/preionizer_module/build_preionizer_module_icd.py",
    "PIM_JSON": "schemas/interfaces/preionizer_module_icd_v1.json",
}
# Parallel A9 lanes (NOT in the base commit): referenced as PENDING only; nothing is read from them.
A9_LANES = {
    "A9-01": "docs/experiments/hall_icp/prereg_framework/",
    "A9-02": "docs/architecture_comparison/power_boundary_a9/",
    "A9-04": "docs/experiments/hall_icp/uncertainty_budget/",
    "A9-05": "docs/evidence/icp_neutralizer/",
}
A9_05_VALIDATION_INPUTS = "docs/experiments/hall_icp/validation_inputs/"
A9_02_MODULE = "abep_sim/bus_boundary_a9.py"
H2_LANES = {
    "H2-1": "docs/hardware/h2/h2_1_hall_chamber_magnet/",
    "H2-2": "docs/hardware/h2/h2_2_cathode_integration/",
    "H2-3": "docs/hardware/h2/h2_3_gas_path_plenum/",
    "H2-4": "docs/hardware/h2/h2_4_ppu_bus/",
    "H2-5": "docs/hardware/h2/h2_5_thermal_network/",
    "H2-6": "docs/hardware/h2/h2_6_diagnostics_fixture/",
    "H2-7": "docs/hardware/h2/h2_7_mechanical_bom/",
}

# Published analog: accessed by this lane (open access, CC BY-NC-ND 4.0). The PDF is not committed (licence: no
# adaptations); only short factual values with page provenance are quoted.
TAKAHASHI = {
    "id": "SRC-TAKAHASHI2024",
    "citation": ("K. Takahashi, H. Watanabe, Y. Nakahama, K. Kikuchi, 'Hall thruster ion acceleration neutralized by a "
                 "radiofrequency inductively coupled plasma', Journal of Electric Propulsion 3, 18 (2024)"),
    "doi": "10.1007/s44205-024-00081-2",
    "url_accessed": "https://link.springer.com/content/pdf/10.1007/s44205-024-00081-2.pdf",
    "accessed": "2026-09-29",
    "retrieved_pdf_sha256": "1e4778559d61509d520fac91798f7ed9ebb92d18a31a2e9b9f2598a8894d6e1f",
    "pages": 10,
    "crossref_check": ("api.crossref.org/works/10.1007/s44205-024-00081-2 on 2026-09-29: title, authors Takahashi/Watanabe/"
                       "Nakahama/Kikuchi, Journal of Electric Propulsion vol. 3 art. 18, published 2024-09-27, "
                       "licence CC BY-NC-ND 4.0"),
    "licence": "CC BY-NC-ND 4.0 (quoted factual values with attribution; no figure reproduced, no adaptation)",
    "access": "open access full text (publisher PDF)",
    "evidence_level": "3 (primary experimental literature) for the topology; analog hardware (argon, permanent-magnet HET, "
                      "different geometry), so NOT evidence for Vyovrinda H-1 performance",
    "label": "published analog, reported",
    # A9_INT (fo_a9_int_core_integration): pointer resolved to the merged A9-05 deliverable (cited, not read, not pinned
    # here; post-integration sha256 in docs/experiments/hall_icp/integration/a9_core_integration_v1.json)
    "authority_note": ("A9-05 (docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json) owns the authoritative "
                       "evidence extraction; this "
                       "annex is this lane's own page-cited extraction of geometry/operating ranges for interface "
                       "context and must be reconciled with A9-05 when it merges"),
}


# ----------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------
def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel)


def sha256_of(rel: str) -> str:
    p = _abs(rel)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"required input missing: {rel}")
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


_JSON: dict = {}


def load(rel: str):
    if rel not in _JSON:
        p = _abs(rel)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"required input missing: {rel}")
        with open(p, encoding="utf-8") as f:
            _JSON[rel] = json.load(f)
    return _JSON[rel]


def resolve(doc, pointer: str):
    """RFC 6901 JSON pointer resolution; raises on a dangling pointer."""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON pointer: {pointer!r}")
    cur = doc
    for raw in pointer[1:].split("/"):
        tok = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(tok)]
        elif isinstance(cur, dict):
            if tok not in cur:
                raise KeyError(f"pointer {pointer!r}: key {tok!r} not found")
            cur = cur[tok]
        else:
            raise KeyError(f"pointer {pointer!r}: cannot descend into {type(cur).__name__}")
    return cur


def xe_budget_dir() -> str:
    """Directory of the verified A9 Xe ledger lane under docs/budgets/ (exactly one match or raise).
    A9-10: retargeted from the A6 ledger to the A9 ledger update ('_a9'-suffixed directory, fo_a9_08), which books the
    G-REUSE ICP as 0 Xe and a G-XE contingency explicitly (A9.1 HIQ-06, A9-08 instruction)."""
    hits = sorted(os.path.relpath(p, ROOT).replace(os.sep, "/") + "/"
                  for p in glob.glob(os.path.join(ROOT, "docs", "budgets", "xe_*"))
                  if os.path.isdir(p) and os.path.basename(p).endswith("_a9"))
    if len(hits) != 1:
        raise FileNotFoundError(f"expected exactly one Xe ledger directory under docs/budgets/, found {hits}")
    return hits[0]


def check_decisions() -> list:
    pins = []
    for key, (rel, expected) in DECISIONS.items():
        got = sha256_of(rel)
        if expected is not None and got != expected:
            raise RuntimeError(f"immutable decision {rel} changed: sha256 {got} != pinned {expected}")
        pins.append({"key": key, "path": rel, "sha256": got, "immutable": True})
    return pins


def answers_by_row() -> dict:
    ans = load(DECISIONS["ANS"][0])["answers"]
    out = {int(a["row"]): a for a in ans}
    if sorted(out) != list(range(1, 148)):
        raise RuntimeError("owner answers file does not hold rows 1..147")
    return out


def answer_fingerprint(row: int) -> str:
    a = answers_by_row()[row]
    return hashlib.sha256(a["owner_answer_verbatim"].encode("utf-8")).hexdigest()


def dp_pointer(key: str, list_name: str, item_id: str) -> str:
    items = load(DELIVERABLES[key])[list_name]
    hits = [i for i, x in enumerate(items) if isinstance(x, dict) and x.get("id") == item_id]
    if len(hits) != 1:
        raise KeyError(f"{DELIVERABLES[key]}#{list_name}: id {item_id!r} found {len(hits)} times")
    return f"/{list_name}/{hits[0]}"


def copied(key: str, list_name: str, item_id: str, field: str = "value") -> dict:
    """Copy one field of a sourced record (with units, evidence class and status) from a verified deliverable."""
    rel = DELIVERABLES[key]
    ptr = dp_pointer(key, list_name, item_id)
    rec = resolve(load(rel), ptr)
    if field not in rec:
        raise KeyError(f"{rel}{ptr}: no field {field!r}")
    ec = rec.get("evidence_class")
    if not isinstance(ec, str) or not ec.split()[0].strip("()/") in EVIDENCE_CLASSES:
        raise ValueError(f"{rel}{ptr}: evidence class {ec!r} not recognised")
    return {"value": rec[field], "units": rec.get("units"), "evidence_class": ec, "source_status": rec.get("status"),
            "source": {"path": rel, "pointer": f"{ptr}/{field}", "sha256": sha256_of(rel), "id": item_id,
                       "name": rec.get("name")}}


def row_src(*rows: int) -> list:
    ans = answers_by_row()
    out = []
    for r in rows:
        if r not in ans:
            raise KeyError(f"owner answer row {r} does not exist")
        out.append({"path": DECISIONS["ANS"][0], "row": r, "covers_ids": ans[r]["covers_ids"],
                    "answer_sha256": answer_fingerprint(r)})
    return out


def pending(lane: str, what: str) -> str:
    path = A9_LANES.get(lane) or H2_LANES.get(lane)
    if path is None:
        raise KeyError(lane)
    return f"PENDING {path} ({lane}: {what})"


# ----------------------------------------------------------------------------------------------------------------------
# content
# ----------------------------------------------------------------------------------------------------------------------
def interface_planes() -> list:
    exit_plane = copied("H21", "design_parameters", "H21-11")
    length = copied("H21", "design_parameters", "H21-08")
    return [
        {"id": "IP-EXIT", "definition": "H-1 channel exit plane, z = L measured from the anode/gas-distributor face "
                                        "HALL_INLET_Z0 (z = 0); +z points downstream along the H-1 thrust axis",
         "h2_basis": exit_plane, "channel_length_window": length, "status": "SOURCED (PRELIMINARY in H2-1)"},
        {"id": "IP-NEU", "definition": "upstream mechanical datum face of the downstream electron-source module "
                                       "(hall_icp_neutralizer: ICP module) located on the shared kinematic carrier "
                                       "KC-1 at axial standoff z_NEU = z - L >= 0 downstream of IP-EXIT, coaxial with "
                                       "the thrust axis", "status": "PROPOSED (value of the standoff is ICP-02, TBD)"},
        {"id": "IP-C1", "definition": "mechanical datum of the external C1 reference module on the same carrier KC-1 "
                                      "(row 79: external C1; H-1 neutralizer-agnostic)", "status": "PROPOSED"},
        {"id": "KC-1", "definition": "kinematic carrier seat on the thrust-stand moving platform shared by the C1 "
                                     "reference module, the ICP module and the matched mechanical sham (rows 17, 122); "
                                     "H-1 stays bolted", "status": "PROPOSED"},
        {"id": "IP-DN (historical)", "definition": "H-1 rear inlet flange upstream of HALL_INLET_Z0 (H2-1 interface_planes; "
                                                   "historical pre-ionizer ICD). Unchanged and NOT the downstream "
                                                   "neutralizer plane; see ICPQ-01 for the naming note",
         "status": "HISTORICAL_UNCHANGED"},
    ]


def I(iid, group, title, requirement, *, value=None, units="-", basis, sources, evidence_class=None, status,
      freeze_point, verification, rows=(), applies=CONFIGURATIONS, tbd=None, note=None, copied_from=None):
    if freeze_point not in FREEZE_POINTS:
        raise ValueError(f"{iid}: freeze point {freeze_point!r}")
    if status.split()[0] not in ITEM_STATUSES:
        raise ValueError(f"{iid}: status {status!r}")
    if value is None:
        if not ((tbd and tbd.startswith(TBD)) or status.startswith("PENDING")):
            raise ValueError(f"{iid}: null value needs 'TBD - requires ...' or a PENDING status")
        if evidence_class is not None:
            raise ValueError(f"{iid}: a TBD value carries no evidence class")
    else:
        if evidence_class is None or evidence_class.split()[0] not in EVIDENCE_CLASSES:
            raise ValueError(f"{iid}: value needs an evidence class, got {evidence_class!r}")
        if not sources:
            raise ValueError(f"{iid}: value needs a source")
    for a in applies:
        if a not in CONFIGURATIONS + ("sham_module",):
            raise ValueError(f"{iid}: unknown configuration {a!r}")
    rec = {"id": iid, "group": group, "title": title, "requirement": requirement, "value": value, "units": units,
           "basis": basis, "sources": sources, "evidence_class": evidence_class, "status": status,
           "freeze_point": freeze_point, "verification": verification, "owner_rows": list(rows),
           "applies_to": list(applies)}
    if tbd:
        rec["tbd"] = tbd
    if note:
        rec["note"] = note
    if copied_from:
        rec["copied_from"] = copied_from
    return rec


P_FWD_MAX_W = 500.0  # row 72: laboratory forward power 0-500 W initially
HEAT_LOAD_MARGIN = 1.20  # row 86: 20 % heat-load design margin


def require_text(row: int, text: str) -> None:
    """Abort if an owner-given value cited by this builder is not in the verbatim answer of that row."""
    if text not in answers_by_row()[row]["owner_answer_verbatim"]:
        raise RuntimeError(f"owner row {row} no longer carries {text!r}")


def rf_heat_bound_W() -> tuple:
    """RF-only partial allocation term (not a module heat-load bound): full lab forward power x the owner heat-load margin."""
    ans = answers_by_row()
    if "0\u2013500 W" not in ans[72]["owner_answer_verbatim"] or "20% heat-load" not in ans[86]["owner_answer_verbatim"]:
        raise RuntimeError("owner rows 72/86 no longer carry the values this builder cites")
    return P_FWD_MAX_W, round(P_FWD_MAX_W * HEAT_LOAD_MARGIN, 6)


def items() -> list:
    ch_od = copied("H21", "design_parameters", "H21-05")
    probe = copied("H21", "design_parameters", "H21-29")
    carrier = copied("H26", "design_parameters", "H26-41")
    weight = copied("H26", "design_parameters", "H26-42")
    stand_mass = copied("H26", "design_parameters", "H26-43")
    iso = copied("H26", "design_parameters", "H26-45")
    idband = copied("H26", "design_parameters", "H26-16")
    heat_bound = copied("H26", "design_parameters", "H26-44")
    bz_maps = copied("H26", "design_parameters", "H26-36")
    c1_flow = copied("H22", "design_parameters", "H22-42")
    c1_loc = copied("H22", "design_parameters", "H22-01")
    ext_ptr = dp_pointer("H22", "location_options", "L-EXTERNAL")
    c1_ext_src = {"path": DELIVERABLES["H22"], "pointer": f"{ext_ptr}/description",
                  "sha256": sha256_of(DELIVERABLES["H22"]), "id": "L-EXTERNAL",
                  "role": "definition of the external location adopted here (row 79)"}
    c1_prelim_src = dict(c1_loc["source"], role="H2-2 PRELIMINARY L-CENTRAL choice that row 79 reverses (context, "
                                                "not the basis of this item)")
    p_fwd_max, rf_heat_bound = rf_heat_bound_W()
    for r, t in ((72, "13.56 MHz"), (89, "300\u2013600 V"), (23, "two elevated background-pressure levels"),
                 (86, "\u226550 K margin"), (116, "at least 25 kg")):
        require_text(r, t)
    tak = TAKAHASHI["id"]
    X = []
    # ------------------------------------------------------------------ (1) mechanical
    X.append(I("ICP-01", "mechanical", "Coordinate frame and interface planes",
               "The ICD uses one frame for both configurations: z along the H-1 thrust axis, z = 0 at HALL_INLET_Z0, "
               "IP-EXIT at z = L, downstream electron-source module datum IP-NEU at z >= L on the shared carrier KC-1. "
               "The historical upstream plane IP-DN (H-1 rear inlet flange) keeps its meaning and is not used for the "
               "neutralizer.", value="IP-EXIT / IP-NEU / IP-C1 / KC-1 (definitions)", basis="definition",
               sources=[{"path": DELIVERABLES["H21"], "id": "H21-11"}] + row_src(79, 122),
               evidence_class="assumed (convention)", status="PROPOSED", freeze_point="LOCK-1",
               verification="inspection of the interface control drawing", rows=(79, 122)))
    X.append(I("ICP-02", "mechanical", "Axial standoff of the ICP module datum from IP-EXIT (downstream, coaxial)",
               "The ICP electron source sits downstream of IP-EXIT and coaxial with the thrust axis (A9 governing "
               "decision 1; row 79: 'downstream/coaxial interface for the ICP neutralizer'). The standoff z_NEU is an "
               "interface dimension frozen on the interface control drawing before score-bearing Phase 1 (row 71).",
               units="mm", basis="A9 topology; published analog has the HET terminating the upstream end of the "
                                  "source tube (annex TAK-02)",
               sources=row_src(71, 79) + [{"ref": tak, "page": 2}], status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the ICP module design (source length, antenna position) and the H-1 exit-face geometry "
                   "(PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ revision for the external C1, A9-07)",
               verification="measurement on the stand (CMM or gauge) at every installation", rows=(71, 79)))
    X.append(I("ICP-03", "mechanical", "Coaxiality and angular alignment of the ICP bore to the H-1 thrust axis",
               "Lateral offset and tilt of the ICP module axis relative to the H-1 thrust axis are recorded at every "
               "installation against a tolerance whose rule is fixed at LOCK-1 and whose value is fixed at LOCK-2 from "
               "the measured exchange series (ICP-39) and the A9-04 uncertainty allocation.",
               units="mm, deg", basis="uncertainty allocation (A9-04)", sources=row_src(18, 19, 122),
               status="PENDING " + A9_LANES["A9-04"] + " (alignment share of the C1-vs-ICP uncertainty budget)",
               freeze_point="LOCK-2", verification="alignment reference on the H-1 adapter and carrier fiducials read "
                                                     "before and after every exchange (H2-6 H26-FX-07)",
               rows=(18, 19, 122)))
    X.append(I("ICP-04", "mechanical", "ICP clear aperture for the Hall plume",
               "If the ICP source volume encloses the plume axis (Takahashi-type topology), its clear aperture at every "
               "z must pass the H-1 plume; beam interception on the module is recorded, not assumed zero (ICP-29). The "
               "aperture is set from the frozen H-1 channel OD and the measured plume divergence; the H-1 channel OD "
               "window is copied here as the input range, not as a design value.",
               units="mm", basis="H-1 channel OD window (H2-1) + measured divergence (Faraday, INS-15)",
               sources=[ch_od["source"], {"ref": tak, "page": 2}], status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the frozen H-1 channel OD (H2-1 H21-05 window {ch_od['value']} mm, PRELIMINARY) and the "
                   "ICP module design", copied_from=ch_od,
               verification="inspection + Faraday far-field map with each module installed", rows=()))
    X.append(I("ICP-05", "mechanical", "External C1 reference location on the C1 reference module",
               "C1 is external (row 79), outside the outer pole with its axis parallel to the thrust axis (H2-2 option "
               "L-EXTERNAL), mounted on the C1 reference module seated on KC-1; the H-1 mean diameter is not constrained "
               "around a central C1. The H2-2 PRELIMINARY choice L-CENTRAL (H22-01) is reversed by row 79 and needs the "
               "H2-1/H2-2 revision (A9-07). The C1 orifice position relative to IP-EXIT is recorded per installation.",
               units="mm (orifice position r, z relative to IP-EXIT)", basis="row 79; H2-2 location_options[L-EXTERNAL]",
               sources=row_src(79) + [c1_ext_src, c1_prelim_src], status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the H2-1/H2-2 revision for the external C1 (A9-07) and the C1 reference module design",
               verification="inspection + position record per installation", rows=(79,),
               applies=("hall_c1_reference",)))
    X.append(I("ICP-06", "mechanical", "Kinematic carrier KC-1: shared datum, weight path, H-1 stays bolted",
               "Both downstream modules (C1 reference, ICP) and the mechanical sham seat on the same exactly-constrained "
               "carrier on the stand moving platform with identical seat geometry, preload and torque procedure. Module "
               "weight goes through the carrier; no module load or assembly torque reaches the H-1 mount; H-1 is never "
               "unbolted for a configuration change (rows 17, 122).",
               value=carrier["value"], basis="H2-6 fixture concept adapted to the downstream modules",
               sources=row_src(17, 122) + [carrier["source"], weight["source"]],
               evidence_class=carrier["evidence_class"], status="PROPOSED", freeze_point="LOCK-1",
               verification="exchange series ICP-39 (cold/tare repeatability) and alignment record",
               rows=(17, 122), applies=CONFIGURATIONS + ("sham_module",), copied_from=carrier))
    X.append(I("ICP-07", "mechanical", "Module envelope and keep-out zones",
               "Each downstream module stays inside a declared envelope (length, OD, keep-outs) that preserves the "
               "Hall-probe path from beyond the exit plane to the anode face (H2-1 H21-29), the Faraday/ExB/RPA lines of "
               "sight, the witness holder positions and the service-line bundle. The envelope is sized for the ICP "
               "module and the C1 reference module, not for an upstream pre-ionizer (row 61).",
               units="mm", basis="row 61; H2-1 H21-29 provision", sources=row_src(61) + [probe["source"]],
               status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the ICP and C1 reference module designs and the frozen H-1 exit geometry",
               verification="inspection; B(z) probe traverse with each module installed", rows=(61,)))
    X.append(I("ICP-08", "mechanical", "Mass and centre of gravity on the stand per configuration",
               "Mass and CG of H-1 + MC-1 + the installed downstream module (+ its on-platform services) are measured and "
               "recorded per serial and per configuration; the stand is designed for at least 25 kg moving payload and "
               "is uprated rather than the hardware trimmed if exceeded (row 116). The owner v0 dry allocations "
               "(row 54: ICP neutralizer 2.0 kg, RF generator/matching 1.5 kg) are FLIGHT allocations, not stand masses.",
               units="kg", basis="row 116 (stand payload), row 54 (flight allocations, not CBEs)",
               sources=row_src(54, 116) + [stand_mass["source"]], status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the module designs and PENDING {H2_LANES['H2-7']} (A9 amendment, A9-06)",
               verification="weighing per serial; in-situ calibration per configuration", rows=(54, 116),
               applies=CONFIGURATIONS + ("sham_module",)))
    X.append(I("ICP-09", "mechanical", "Matched mechanical sham (stand parasitics only)",
               "A matched mechanical sham reproduces a module's mass/CG and service-line attachment on KC-1 for "
               "stand-parasitic characterisation only (row 63). It is never a plasma control, never a third reported "
               "configuration and never an upstream 'blank' module. Matched sham service lines are present in every "
               "compared configuration (row 133).",
               value="sham_module (stand-parasitic control only)", basis="rows 63, 133",
               sources=row_src(63, 133), evidence_class="owner-allocation", status="OWNER_GIVEN",
               freeze_point="NOW", verification="tare with sham vs module (ICP-39)", rows=(63, 133),
               applies=("sham_module",)))
    X.append(I("ICP-10", "mechanical", "Downstream module mounted on the moving platform (system-thrust rule)",
               "Both downstream modules ride on the thrust-stand moving platform, so any plume-module force (plume "
               "interception, pressure on module surfaces) lies inside the measured system as it would in flight; a "
               "facility-mounted module would bias the comparison.",
               value="on moving platform", basis="rows 17, 122 (carrier on the stand, H-1 fixed); H2-6 H26-FX-02",
               sources=row_src(17, 122) + [carrier["source"]], evidence_class="assumed", status="PROPOSED",
               freeze_point="LOCK-1", verification="inspection; owner decision ICPQ-03", rows=(17, 122)))
    # ------------------------------------------------------------------ (2) RF
    X.append(I("ICP-11", "rf", "RF frequency", "The ICP is driven at 13.56 MHz (row 72).", value=13.56, units="MHz",
               basis="owner answer", sources=row_src(72), evidence_class="owner-allocation", status="OWNER_GIVEN",
               freeze_point="NOW", verification="generator setting record; spectrum check in the pickup test",
               rows=(72,), applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-12", "rf", "Laboratory forward-power range (initial)",
               "The laboratory RF source and the inline measurement chain cover 0-500 W forward power initially "
               "(row 72). This is a laboratory capability range, not a power allocation: the ICP bus power must fit "
               "inside the internal ~1.35 kW design allocation without consuming the 1.35 -> 1.5 kW margin (row 109), "
               "and the full-system gate is P_bus < 1.5 kW at the spacecraft-DC boundary incl. start-up transients "
               "(row 108).", value=[0.0, p_fwd_max], units="W", basis="owner answer",
               sources=row_src(72, 108, 109), evidence_class="owner-allocation", status="OWNER_GIVEN",
               freeze_point="NOW", verification="generator + directional-coupler calibration (ICP-14)",
               rows=(72, 108, 109), applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-13", "rf", "Matching-network location",
               "The matching network location (on the moving platform next to the antenna, or off the platform with a "
               "flexible coax across the stand) is declared on the interface drawing; the RF load plane (ICP-14) and the "
               "sham routing (ICP-18) follow from it.", units="-", basis="row 117 (flexible coax with matched sham)",
               sources=row_src(72, 117), status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the owner decision ICPQ-05 and the dummy-load cable-loss characterisation (S1a)",
               verification="inspection", rows=(72, 117), applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-14", "rf", "Directional-coupler forward/reflected measurement and RF load plane",
               "A directional coupler measures forward and reflected power at a declared load plane; net delivered "
               "power = P_fwd - P_refl at that plane. Losses between the load plane and the antenna are characterised "
               "on a dummy load and with the module unpowered. Calorimetry is an independent cross-check, not the sole "
               "primary measurement (row 72). Generator-internal meters alone (as in the analog, annex TAK-04) are not "
               "sufficient. Measurement uncertainty is allocated by A9-04.",
               units="W", basis="row 72", sources=row_src(72),
               status="PENDING " + A9_LANES["A9-04"] + " (u(P_fwd), u(P_refl), load-plane loss chain)",
               freeze_point="LOCK-2", verification="coupler calibration against a traceable power standard; "
                                                   "calorimetric cross-check", rows=(72,),
               applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-15", "rf", "Coax, vacuum RF feedthrough and connector ratings",
               "Coax, vacuum feedthrough and connectors are rated for at least the full laboratory forward power "
               "(row 72) at 13.56 MHz under the measured reflected-power condition; impedance, voltage rating and "
               "connector family follow the selected generator and matching network (quotations only, row 8).",
               units="W, V, ohm", basis="row 72 (power floor); row 8 (quotation stage)", sources=row_src(8, 72),
               status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the generator/matching-network selection from quotations (RFQ package A9-09)",
               verification="datasheet review; hipot/RF power test of the installed chain", rows=(8, 72),
               applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-16", "rf", "RF interlock",
               "RF output is inhibited unless all permissives are true: chamber vacuum OK, valid ICP MODULE_ID, "
               "coax/connector interlock loop closed, reflected power below its trip, collector/bias supply in a "
               "defined state, Hall discharge supply in the state required by the sequence. Trip values are set from "
               "measured S1a behaviour, never invented. Every trip is logged with time and cause (row 62).",
               units="-", basis="row 62", sources=row_src(62), status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the generator interlock interface and S1a-measured reflected-power behaviour",
               verification="functional interlock test before first RF-on and at every configuration change",
               rows=(62,), applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-17", "rf", "RF pickup / EMC limits on H-1 and diagnostics",
               "RF pickup on the discharge, magnet, C1/collector and diagnostic channels is measured with the generator "
               "into a dummy load and with the ICP energized, H-1 off, in both configurations (the C1 configuration "
               "with the RF chain present as a sham). Allowed pickup per channel is frozen from measured values before "
               "score-bearing data. The exploratory I_d(t) band (row 129; H2-6 H26-16) contains 13.56 MHz and its "
               "harmonics: the chain declares its RF rejection / anti-alias transfer function.",
               units="V, A (per channel), dB", basis="rows 64, 129; H2-6 H26-16",
               sources=row_src(64, 129) + [idband["source"]], status="TBD", freeze_point="LOCK-2",
               tbd=f"{TBD} S1a dummy-load and energized pickup measurements (values are measured, not set now)",
               verification="pickup test at every pump-down and configuration change (ICP-39)", rows=(64, 129),
               copied_from=idband))
    X.append(I("ICP-18", "rf", "Flexible coax across the stand with matched sham routing",
               "The RF line crosses the moving stage as a flexible coax in a low-stiffness symmetric harp/slack loop; "
               "no uncompensated hard RF line crosses the moving stage. In hall_c1_reference an identical sham coax with "
               "identical routing is present and terminated off-stand; residual parasitic force is characterised "
               "(rows 117, 133).", value="flexible coax + matched sham in every configuration",
               basis="owner answers", sources=row_src(117, 133), evidence_class="owner-allocation",
               status="OWNER_GIVEN", freeze_point="NOW", verification="service-line parasitic test (ICP-39)",
               rows=(117, 133)))
    X.append(I("ICP-19", "rf", "Antenna shielding against parasitic discharge",
               "The antenna and its leads are enclosed (insulator + grounded or declared-potential metallic cover) so "
               "that no parasitic discharge forms outside the source; the absence of parasitic discharge is checked "
               "visually/optically and by pickup at every ignition. Analog practice: antenna covered by insulator and "
               "grounded metallic structures (annex TAK-03).", units="-", basis="published analog practice",
               sources=[{"ref": tak, "page": 2}], status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the ICP module design and the body-potential decision (ICP-20)",
               verification="inspection + camera/OES check at ignition", rows=(),
               applies=("hall_icp_neutralizer",)))
    # ------------------------------------------------------------------ (3) electrical
    X.append(I("ICP-20", "electrical", "ICP dielectric/body potential",
               "The ICP dielectric and module body float unless the validated circuit requires otherwise; the body is "
               "not hard-grounded by default (row 70). Body-to-facility-ground and body-to-anode potentials are measured "
               "at every reading.", value="floating (default)", basis="owner answer", sources=row_src(70),
               evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW",
               verification="potential record per reading; insulation-resistance check per exchange", rows=(70,),
               applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-21", "electrical", "Electron-extraction collector / bias electrode",
               "The electron-extraction collector (the ion-collecting electrode inside the source that closes the "
               "current when electrons are extracted) is controlled and measured separately: its bias V and current I "
               "are recorded per reading, it is never hard-grounded by default (row 70). Its V/I range and material are "
               "design items; the analog reports the collector driven to about -100 V w.r.t. ground at high discharge "
               "voltage with sputtering and metallic deposition (annex TAK-10, TAK-11), so collector bias, ion energy "
               "and erosion are interface-relevant.", units="V, A", basis="row 70; analog TAK-10/11",
               sources=row_src(70) + [{"ref": tak, "page": 6}], status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the ICP module design, the A9-02 collector/bias bus slot and S1a Ar engineering data",
               verification="4-wire V and shunt I per reading", rows=(70,), applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-22", "electrical", "Hall discharge circuit topology and V_d definition per configuration",
               "hall_c1_reference: discharge supply between anode and C1 cathode common (H2-2/H2-4). "
               "hall_icp_neutralizer: discharge supply between anode and the ICP electron-source reference (collector "
               "or declared node). Any series resistor or RF filter in the discharge loop is declared and its dissipation "
               "booked (analog: 50 ohm series resistor and a 13.56 MHz L-C resonance circuit, isolation transformer, "
               "annex TAK-06). 'Same V_d setting' across configurations needs one declared definition (supply terminal "
               "vs anode-to-electron-source potential); anode-to-ground, cathode/collector-to-ground and supply-terminal "
               "voltages are all recorded.", units="V", basis="A9 first decisive comparison ('same V_d/B settings')",
               sources=row_src(81, 91) + [{"ref": tak, "page": 3}],
               status="PENDING " + A9_LANES["A9-01"] + " (definition of the V_d setting used as the controlled variable)",
               freeze_point="LOCK-1", verification="circuit inspection; per-reading voltage record", rows=(81, 91),
               note="see open question ICPQ-04"))
    X.append(I("ICP-23", "electrical", "Isolation from the Hall anode and the cathode-common",
               "DC discharge-circuit isolation: the ICP body and the collector/bias circuit are isolated from the Hall "
               "anode, the C1 cathode-common and facility ground, rated to the relaxed 350 V V_d end plus "
               "transient/qualification margin (row 81, a DC discharge-circuit rating). The margin and test voltage are "
               "owner/LOCK-1 items (H2-6 H26-45 carries 350 V with the margin TBD). The RF antenna circuit is NOT covered "
               "by this DC item: its RF voltage, creepage/clearance and Paschen rating, and the combined DC+RF stress "
               "between antenna and collector/body, are ICP-44. The C1 module's pulsed keeper-ignition circuit (300-600 V "
               "class, row 89) is NOT covered by this DC item or its margin either: it is ICP-46. Any gas line to the "
               "ICP crossing a potential difference uses an isolator qualified per row 105 practice. Governing source: "
               "owner row 81 (350 V); the copied H2-6 H26-45 entry (classed 'assumed' there) is context only.",
               value=iso["value"], units=iso["units"], basis="row 81 (governing); H2-6 H26-45 context only (margin TBD)",
               sources=row_src(81, 105) + [iso["source"]], evidence_class="owner-allocation (margin TBD)",
               status="PROPOSED (margin TBD)", freeze_point="LOCK-1",
               verification="insulation resistance + hipot per exchange (ICP-39)", rows=(81, 105),
               copied_from=iso))
    X.append(I("ICP-24", "electrical", "Bus-power slots for the ICP loads",
               "Every active ICP load has a bus slot: RF source/matching, collector/bias supply if required, and any "
               "active cooling; no assist magnet in v1 (row 69). P_bus is taken at the spacecraft-DC propulsion "
               "boundary incl. start-up transients (row 108) on the new A9 boundary, never on bus_power_boundary_v1; "
               "discharge-only or RF-generator-only power is never sufficient (A9 requirement discipline). The RF "
               "generator's and matching network's own conversion loss (DC in minus RF forward power out) is a separate "
               "bus-power term booked in the RF-source slot, and a separate heat term wherever that hardware sits "
               "(platform, stand or flight unit; see ICP-43). The RF power drawn at the electron current of ICP-45 "
               "must fit inside the ~1.35 kW internal allocation (row 109); this is decided by measurement only.",
               units="W", basis="rows 66, 108, 109, 110", sources=row_src(66, 108, 109, 110),
               status="PENDING " + A9_LANES["A9-02"] + " + " + A9_02_MODULE + " (slot ids and ledger efficiencies)",
               freeze_point="LOCK-1", verification="per-slot DC metering at the bus-boundary-equivalent point",
               rows=(66, 108, 109, 110)))
    X.append(I("ICP-25", "electrical", "C1 reference supplies on the C1 module",
               "hall_c1_reference keeps the heated Xe-fed LaB6 C1 with heater and keeper supplies, current-limited "
               "pulsed keeper ignition in the 300-600 V class with interlocks and recorded pulse energy (row 89), and a "
               "selectable cathode-common/bleeder topology with V/I measurement (row 91, no resistor value frozen). The "
               "keeper-pulse isolation rating of lead, feedthrough and harness is ICP-46.",
               value=[300.0, 600.0], units="V (pulsed keeper ignition class)", basis="owner answers",
               sources=row_src(49, 89, 91), evidence_class="owner-allocation", status="OWNER_GIVEN",
               freeze_point="NOW", verification="supply acceptance test", rows=(49, 89, 91),
               applies=("hall_c1_reference",)))
    # ------------------------------------------------------------------ (4) gas / plume
    X.append(I("ICP-26", "gas_plume", "ICP source gas species and flow (booked item)",
               "The ICP gas feed is an explicit ICD item and must be booked (A9 recorder flag on row 46). Declared "
               "modes: G-REUSE (no dedicated feed; the ICP operates on Hall exhaust/residual gas, as in the analog, "
               "annex TAK-05), G-XE (dedicated Xe feed, booked in the Xe ledger as PHASE_TOTAL_FLOW, row 42), G-ATM "
               "(dedicated feed from the atmospheric gas path, booked against the delivered atmospheric flow). The module "
               "provides a dedicated gas port (capped in G-REUSE). The C1 reference uses its Xe cathode flow "
               "(H2-2 H22-42, copied for context).", units="mg/s (per species)",
               basis="row 46 flag; row 42 Xe booking convention",
               sources=row_src(42, 46) + [c1_flow["source"], {"ref": tak, "page": 3}], status="TBD",
               freeze_point="LOCK-1",
               tbd=f"{TBD} the owner choice of the primary ICP gas mode (ICPQ-02) and the ICP module design",
               verification="dedicated MFC (if any) with own-gas calibration; totalised flow per mode",
               rows=(42, 46), copied_from=c1_flow))
    X.append(I("ICP-27", "gas_plume", "Hall-exhaust-to-ICP pressure / conductance interface",
               "The downstream Hall-exhaust-to-ICP interface is defined and measured (row 63): a pressure port in the "
               "ICP source volume (capacitance manometer) and a matched port at the equivalent position on the C1 "
               "reference module; cold-flow conductance IP-EXIT -> ICP volume -> chamber is measured at the anode flow "
               "grid in S1a for each module; the values are recorded before LOCK-2 and before any score-bearing run "
               "(row 71).", units="Pa; m^3/s (conductance)", basis="row 63",
               sources=row_src(63), status="TBD", freeze_point="after-evidence",
               tbd=f"{TBD} S1a cold-flow measurements with each module installed (values measured, not set)",
               verification="cold-flow pressure map per module and per anode flow", rows=(63,)))
    X.append(I("ICP-28", "gas_plume", "Background-pressure sensitivity",
               "ICP ignition/sustainment and Hall operation with each electron source are characterised at base "
               "background pressure and at two elevated p_b levels (row 23); T-PB-MAX is frozen only after the low-flow "
               "knee and facility capability are known (row 23). This is critical in G-REUSE because the ICP then runs "
               "on residual gas (the analog operated at ~28 mPa chamber pressure, annex TAK-05, facility-specific).",
               value=2, units="elevated p_b levels", basis="owner answer", sources=row_src(23),
               evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW",
               verification="facility-effect series (S5-type) per configuration", rows=(23,)))
    X.append(I("ICP-29", "gas_plume", "Plume interception, sputtering and back-deposition",
               "Beam interception on the ICP module, collector sputtering and deposition onto the H-1 front face and "
               "the source dielectric are recorded (witness coupons on the H-1 front face and inside the module; "
               "pre/post inspection). They are architecture consequences inside the system boundary, reported, never "
               "corrected away. Analog: metallic films on the glass tube and on HET front insulators after operation "
               "(annex TAK-11).", units="-", basis="analog TAK-11; rows 99, 134 (witness practice)",
               sources=row_src(99, 134) + [{"ref": tak, "page": 6}], status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} witness positions on the module interface drawing and the collector material (ICPQ-07)",
               verification="witness mass/profile metrology (INS-19/20) per block", rows=(99, 134)))
    X.append(I("ICP-30", "gas_plume", "Gas evidence order, labels and O2 compatibility",
               "Evidence order: Ar ENGINEERING_ONLY (never counts toward DRDO atmospheric requirements) -> pure N2 -> "
               "O2-bearing mixtures labelled NO_ATOMIC_O -> separate atomic-O materials/life programme (rows 36, 132). "
               "Wetted ICP parts in O2 service are cleaned to ASTM G93 Level C (row 107) and exclude silver (row 103).",
               value="Ar ENGINEERING_ONLY -> N2 -> O2-bearing NO_ATOMIC_O -> separate AO programme",
               basis="owner answers", sources=row_src(36, 103, 107, 132), evidence_class="owner-allocation",
               status="OWNER_GIVEN", freeze_point="NOW", verification="gas log label per reading; cleaning certificate",
               rows=(36, 103, 107, 132)))
    # ------------------------------------------------------------------ (5) magnetic
    X.append(I("ICP-31", "magnetic", "B(z) perturbation / sensitivity scan with the ICP module installed and energized",
               "B(z) is mapped along the H-1 probe path with the C1 reference module, the ICP module installed "
               "unpowered and the ICP energized (where the gaussmeter is shown RF-immune by the pickup test; otherwise "
               "immediately after RF-off), plus the coil-current sensitivity scan. The allowable field-change tolerance "
               "is frozen from the measured H-1 sensitivity before the score-bearing comparison; no tolerance is set now "
               "(row 67). Maps per configuration follow the H2-6 repeatability plan (copied).",
               units="G (field change), - (relative)", basis="row 67; H2-6 H26-36",
               sources=row_src(67) + [bz_maps["source"]], status="TBD", freeze_point="after-evidence",
               tbd=f"{TBD} the measured H-1 B(z) sensitivity (S1a/S1b) - tolerance frozen before score-bearing data",
               verification="gaussmeter maps (INS-09) per configuration and per exchange", rows=(67,),
               copied_from=bz_maps))
    X.append(I("ICP-32", "magnetic", "Unmagnetized ICP (v1) and ferromagnetic content",
               "The v1 ICP has no dedicated magnet (row 69); magnetic assistance is only a new controlled variant with "
               "booked power and mass. ICP and C1 modules carry no ferromagnetic part inside the MC-1 exclusion zone; "
               "any Ni-clad or nickel part is measured for perturbation (row 77 practice). The H-1 stray field in the "
               "ICP source volume is a measured interface quantity, not zero by assumption.",
               value="no dedicated ICP magnet (v1)", basis="owner answer", sources=row_src(69, 77),
               evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW",
               verification="inspection + B(z)/stray-field map", rows=(69, 77),
               applies=("hall_icp_neutralizer",)))
    # ------------------------------------------------------------------ (6) harness / telemetry
    X.append(I("ICP-33", "harness_telemetry", "MODULE_ID and serial identity",
               "Every downstream module (C1 reference, ICP, sham) reports a MODULE_ID encoding type and serial; it is "
               "logged with every reading (row 62) and a repaired/replaced score-bearing module gets a new serial "
               "(ICP-40).", value="MODULE_ID line on every module", basis="owner answer", sources=row_src(62, 83),
               evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW",
               verification="identity check at every installation", rows=(62, 83),
               applies=CONFIGURATIONS + ("sham_module",)))
    X.append(I("ICP-34", "harness_telemetry", "ICP telemetry list",
               "Minimum ICP channels (rows 62, 130): RF forward and reflected power, RF interlock state, collector/bias "
               "V and I, ICP body potential, temperatures (antenna, dielectric, collector, matching network, RF source), "
               "ICP source-volume pressure, dedicated gas flow if any, command/telemetry, neutralizer health/interlock "
               "state. Flight subset: forward/reflected RF power, collector/bias V/I, RF source temperature, neutralizer "
               "health/interlock state (row 130).",
               value=["P_fwd", "P_refl", "rf_interlock_state", "V_coll", "I_coll", "V_body", "T_antenna", "T_dielectric",
                      "T_collector", "T_matching", "T_rf_source", "p_icp", "mdot_icp", "cmd_tlm", "neutralizer_health"],
               basis="owner answers", sources=row_src(62, 130), evidence_class="owner-allocation",
               status="OWNER_GIVEN", freeze_point="NOW", verification="DAQ channel audit before S1a", rows=(62, 130),
               applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-35", "harness_telemetry", "Commands, states and start records",
               "The ICP state set (OFF, ARMED, IGNITE, ON, TRIP) is commanded and reported. Start records: ICP ignition "
               "attempts, Hall ignition with ICP electrons, restart success and cycle count, classified per "
               "pre-registration (row 24). The ICP ignition dwell/retry bound is pre-registered by A9-01; the C1 bound "
               "(120 s per dwell, at most two retries, row 93) applies only to C1.", units="-, s, count",
               basis="rows 24, 93", sources=row_src(24, 93),
               status="PENDING " + A9_LANES["A9-01"] + " (ICP ignition dwell/retry bound and start classification)",
               freeze_point="LOCK-1", verification="sequence log audit", rows=(24, 93)))
    # ------------------------------------------------------------------ (7) thermal
    X.append(I("ICP-36", "thermal", "ICP dissipation path and RF-path heat contribution (RF only, partial term)",
               "All RF power not absorbed by the plasma, and part of the absorbed power, ends as heat in the antenna, "
               "collector, dielectric, matching network and cabling (analog: only ~10 % absorbed by the plasma, visible "
               "collector heating, annex TAK-12/13). The RF-path heat allocation term for the module is the full "
               "laboratory forward power (row 72) x the 20 % heat-load design margin (row 86). This value is a "
               "margin-inflated RF-ONLY PARTIAL ALLOCATION TERM (an allocation, not a physical bound); it is NOT a bound "
               "on the total module heat load. It covers RF power delivered past the directional coupler only; the RF "
               "generator's own conversion loss is a separate term (ICP-24, ICP-43). In hall_icp_neutralizer the Hall "
               "discharge loop closes through the ICP collector (ICP-22), so the collector collects an ion current "
               "matching the extracted electron current and receives particle heating of order I_coll x sheath voltage "
               "(analog ion impact energies, annex TAK-10), plus Hall-plume interception and plasma heat flux on the "
               "module (ICP-29). Those terms scale with the discharge current, not with the RF power, and are carried "
               "in the total module heat-load item ICP-43. Heat into H-1 + mount stays inside the H2-6 stand bound "
               "(copied).",
               value=rf_heat_bound, units="W", basis="RF-only partial allocation term: 500 W (row 72) x 1.20 (row 86)",
               sources=row_src(72, 86) + [heat_bound["source"]], evidence_class="model-derived (bound on owner values)",
               status="DERIVED_BOUND", freeze_point="LOCK-1", verification="thermocouple map + energy balance in S1a",
               rows=(72, 86), applies=("hall_icp_neutralizer",), copied_from=heat_bound))
    X.append(I("ICP-37", "thermal", "Interface temperatures and >= 50 K margin",
               "Every ICP-module material/insulation (dielectric, antenna insulation, collector, feedthrough, matching "
               "components, carrier interface) holds >= 50 K below its validated continuous-use limit plus the 20 % "
               "heat-load margin (row 86). Limits come from sourced material data after selection; the facility "
               "radiative sink is measured per run (row 131). The margin check closes only against the total module heat "
               "load ICP-43 (not against the RF-only term ICP-36).", value=50.0, units="K (minimum margin)",
               basis="owner answer", sources=row_src(86, 131), evidence_class="owner-allocation",
               status="OWNER_GIVEN", freeze_point="NOW",
               verification="thermocouples per node vs sourced limits; per-run sink measurement", rows=(86, 131)))
    X.append(I("ICP-38", "thermal", "Cooling provision",
               "Passive cooling is the proposed baseline; active cooling is allowed only with a booked bus slot (row 66) "
               "and matched sham coolant lines in the other configuration (row 133).", value="passive (proposed)",
               basis="rows 66, 133", sources=row_src(66, 133), evidence_class="assumed", status="PROPOSED",
               freeze_point="LOCK-1", verification="thermal balance test in S1a", rows=(66, 133)))
    # ------------------------------------------------------------------ (8) exchange checks
    X.append(I("ICP-39", "exchange", "C1 <-> ICP module exchange series (RR-07 adapted)",
               "Every exchange (and a dedicated S1a series) runs: (a) cold/tare - stand zero and in-situ calibration "
               "with each module and the sham; (b) service-line parasitic - force from the live and sham lines; (c) B(z) "
               "perturbation (ICP-31); (d) electrical isolation - insulation resistance and hipot (ICP-23); (e) RF pickup "
               "(ICP-17). H-1 stays bolted (rows 33, 64). The number of exchange cycles and acceptance values are fixed "
               "at LOCK-2 from measured uncertainty (complete balanced replicate sets, at least three engineering "
               "replicates, row 19).",
               value=["cold_tare", "service_line_parasitic", "Bz_perturbation", "electrical_isolation", "rf_pickup"],
               basis="owner answers", sources=row_src(19, 33, 64), evidence_class="owner-allocation",
               status="OWNER_GIVEN", freeze_point="LOCK-2", verification="exchange series records per installation",
               rows=(19, 33, 64), applies=CONFIGURATIONS + ("sham_module",),
               note="check list is owner-given now; cycle count and acceptance values are LOCK-2 values"))
    X.append(I("ICP-40", "exchange", "Serialized-unit rule for repaired modules",
               "A repaired or replaced score-bearing H-1, C1 or ICP module becomes a new serialized unit and needs a new "
               "reference/reinstallation sequence before score-bearing use (row 83).",
               value="repair/replacement -> new serial + new reference sequence", basis="owner answer",
               sources=row_src(83), evidence_class="owner-allocation", status="OWNER_GIVEN", freeze_point="NOW",
               verification="serial log audit", rows=(83,)))
    X.append(I("ICP-41", "exchange", "Start-up-state and thermal-state equivalence",
               "No pre-ionizer dwell matching (row 65): any C1-vs-ICP comparison pre-registers equivalent start-up-state "
               "and thermal-state handling (C1 heater/keeper conditioning vs ICP ignition; T-SETTLE).", units="-",
               basis="row 65", sources=row_src(65),
               status="PENDING " + A9_LANES["A9-01"] + " (pre-registered start-up/thermal-state rule)",
               freeze_point="LOCK-1", verification="sequence log audit", rows=(65,)))
    X.append(I("ICP-42", "exchange", "Order-balanced installation schedule and reference condition",
               "The ICD supplies the exchange procedure; the order-balanced schedule (row 29), REF-COND as its own "
               "installation per block (row 40) and NOT_TESTED slots after a stop (row 39) belong to the A9-01 "
               "framework.", units="-", basis="rows 29, 39, 40", sources=row_src(29, 39, 40),
               status="PENDING " + A9_LANES["A9-01"] + " (stage map and schedule)", freeze_point="LOCK-1",
               verification="schedule audit", rows=(29, 39, 40)))
    X.append(I("ICP-43", "thermal", "Total ICP module heat load (RF + discharge-path + plume terms)",
               "The module thermal path (antenna, collector, dielectric, matching network, carrier interface) is sized "
               "to the TOTAL module heat load Q_mod = Q_RF + Q_coll + Q_plume, where Q_RF is bounded by ICP-36, Q_coll is "
               "the collector particle heating from the Hall discharge current closing through the collector (ICP-22; of "
               "order I_d x the collector sheath/impact voltage, analog TAK-10) and Q_plume is Hall-plume interception "
               "and plasma heat flux on the module (ICP-29). Q_coll and Q_plume scale with the discharge current, not the "
               "RF power. PROPOSED bounding rule (frozen at LOCK-1): Q_mod,bound = 1.20 (row 86) x (P_fwd,max (row 72) + "
               "P_d,max), where P_d,max = I_d,max x V_d,max is the maximum discharge-supply power permitted at the stand "
               "(A9-02 discharge slot / H2-4 supply limit); the true split is measured in S1a by thermocouple map and "
               "energy balance. No value is set until P_d,max exists (see ICPQ-10 for an alternative envelope). The RF "
               "generator and matching-network conversion loss Q_gen is a further, separate heat term (and bus-power "
               "term, ICP-24) wherever that hardware is mounted: it enters Q_mod if the generator/matching network sits "
               "on the moving platform or in the module, and the platform/flight thermal budget otherwise; it is never "
               "dropped (value TBD - requires the selected generator's published efficiency or a measured DC-in/RF-out "
               "balance).",
               units="W", basis="rows 72, 86, 108; ICP-22 topology (discharge closes on the collector)",
               sources=row_src(72, 86, 108) + [heat_bound["source"], {"ref": tak, "page": 6}],
               status="PENDING " + A9_LANES["A9-02"] + " (maximum discharge-supply power P_d,max at the stand)",
               freeze_point="LOCK-1", verification="thermocouple map + energy balance with RF on/off and discharge "
                                                    "current steps in S1a; hot-spot check against ICP-37",
               rows=(72, 86, 108), applies=("hall_icp_neutralizer",),
               note="ICP-37 (>= 50 K margin) cannot be closed until this item has a value"))
    X.append(I("ICP-44", "rf", "Antenna-circuit RF voltage, creepage/clearance and Paschen rating",
               "The antenna circuit (antenna, matching-network output, RF feedthrough and in-vacuum leads) is rated "
               "separately from the 350 V DC discharge-circuit item (ICP-23). At the full laboratory forward power "
               "(row 72) a 13.56 MHz ICP antenna can run at an RF voltage far above the DC discharge rating. The rating "
               "is k_RF x V_ant,peak, where V_ant,peak is computed at P_fwd,max = 500 W from the selected antenna/"
               "matching design and the MEASURED total circuit resistance R_total (antenna + plasma load; the analog "
               "infers its power-transfer efficiency from such measured resistances, annex TAK-12); the factor k_RF (> 1) is an owner/LOCK-1 "
               "value. Clearance/creepage and in-vacuum Paschen margins are set for the combined stress between antenna "
               "and collector/body: the collector/body DC potential relative to the antenna circuit reference (up to the "
               "ICP-23 DC rating) plus V_ant,peak.", units="V (peak RF), mm (clearance/creepage)",
               basis="row 72 (power); row 81 limited to the DC discharge circuit; analog R_total method (TAK-12)",
               sources=row_src(72, 81) + [{"ref": tak, "page": 8}], status="TBD", freeze_point="LOCK-1",
               tbd=f"{TBD} the antenna/matching-network selection (ICP-13, ICP-15), the measured R_total and the owner "
                   "factor k_RF",
               verification="RF hipot at full forward power (500 W) on a dummy load and with plasma; RF probe of "
                            "V_ant,peak; inspection of clearance/creepage", rows=(72, 81),
               applies=("hall_icp_neutralizer",)))
    X.append(I("ICP-45", "electrical", "Electron-extraction (collector) current capability",
               "In hall_icp_neutralizer the whole Hall discharge current closes through the ICP (ICP-22): the "
               "extracted electron current equals the collector ion current equals I_d. The ICP module, its collector/"
               "bias circuit and its RF drive shall sustain a steady extracted electron current >= I_d,max, the maximum "
               "discharge current of the stand discharge slot (A9-02), with the RF forward power and collector bias at "
               "that current recorded. Electron-current capacity is the first quantity the A9 decision names before C1 "
               "stops being the control/fallback (A9 decision, field 'control_fallback'). No capacity is predicted "
               "here; the published analog is context only (annex TAK-04, TAK-13: reported ~1 A at 200 W forward "
               "power, limit attributed by its authors to the RF power; not scaled to H-1).",
               units="A (extracted electron current), W (RF forward power at that current)",
               basis="A9 decision control_fallback; ICP-22 topology; rows 72, 109",
               sources=row_src(72, 109) + [{"path": DECISIONS["A9"][0], "pointer": "/control_fallback",
                                            "sha256": DECISIONS["A9"][1]}, {"ref": tak, "page": 3}, {"ref": tak, "page": 8}],
               status="PENDING " + A9_LANES["A9-02"] + " (I_d,max of the stand discharge slot)",
               freeze_point="LOCK-1",
               verification="collector-current step/ramp to I_d,max on Ar (ENGINEERING_ONLY) in S1a, with a "
                            "resistive/load stand-in or with H-1, recording P_fwd, P_refl, collector V/I and module "
                            "temperatures at each step; repeated on N2 before score-bearing use",
               rows=(72, 109), applies=("hall_icp_neutralizer",),
               note="value = I_d,max from A9-02; capacity/power tension vs row 109 is listed in the hard-incompatibility "
                    "check as not assessable"))
    X.append(I("ICP-46", "electrical", "C1 keeper-ignition pulse isolation rating (keeper lead, feedthrough, harness)",
               "On the C1 reference module the keeper lead, its vacuum feedthrough, connectors and harness, and their "
               "isolation to the C1 cathode-common, module body and facility ground, are rated for the upper end of the "
               "pulsed keeper-ignition class (row 89) plus a transient margin; this is separate from the 350 V DC "
               "discharge-circuit item ICP-23, whose margin does not cover it. The margin and pulse hipot level are "
               "owner/LOCK-1 items.",
               value=600.0, units="V (pulse class upper end; margin TBD)",
               basis="row 89 (300-600 V class); margin owner/LOCK-1", sources=row_src(89),
               evidence_class="owner-allocation (margin TBD)", status="PROPOSED (margin TBD)", freeze_point="LOCK-1",
               verification="pulse hipot of keeper lead/feedthrough/harness per exchange (ICP-39 d); inspection",
               rows=(89,), applies=("hall_c1_reference",)))
    return X


def analog_annex() -> list:
    t = TAKAHASHI["id"]

    def A(aid, quantity, value, units, page, locator, evidence_class, note):
        if evidence_class.split()[0] not in EVIDENCE_CLASSES:
            raise ValueError(aid)
        return {"id": aid, "quantity": quantity, "value": value, "units": units, "source": t, "page": page,
                "locator": locator, "evidence_class": evidence_class, "label": TAKAHASHI["label"],
                "use": "interface context only; never a Vyovrinda performance or design value", "note": note}

    return [
        A("TAK-01", "vacuum chamber size / base pressure", {"diameter_m": 1.0, "length_m": 2.0, "base_Pa": 1e-4},
          "m, Pa", 2, "p. 2, Experimental setup; Fig. 1a", "measured (reported facility description)",
          "three turbomolecular pumping systems"),
        A("TAK-02", "ICP source tube inner diameter; HET terminates the upstream end of the source tube", 65.0, "mm",
          2, "p. 2, Experimental setup; Fig. 1b ('6.5-cm-inner-diameter pyrex source tube')",
          "measured (reported hardware dimension)", "double-turn loop antenna; tube immersed in the chamber"),
        A("TAK-03", "antenna shielding practice", "antenna covered by insulator and grounded metallic structures", "-",
          2, "p. 2, Experimental setup", "measured (reported hardware description)",
          "to minimize parasitic discharge outside the source"),
        A("TAK-04", "RF drive and match", {"frequency_MHz": 13.56, "generator_W": 200.0, "P_rf_W": 200.0,
                                           "reflected": "none detected"}, "MHz, W", 3,
          "p. 3; two variable capacitors; forward/reflected monitored by the generator power meters",
          "measured (reported operating setting)", "input power to the load equal to the forward power of 200 W"),
        A("TAK-05", "gas: argon fed through the HET anode, exhaust reused by the ICP (no dedicated ICP feed)",
          {"flow_sccm": 70.0, "flow_mg_s": 2.1, "chamber_pressure_mPa": 28.0}, "sccm, mg/s, mPa", 3,
          "p. 3 ('70 sccm (m = 2.1 mg/s), providing the chamber pressure of about 28 mPa'); p. 2 (gas reuse)",
          "measured (reported operating setting)", "facility-specific; residual-gas operation"),
        A("TAK-06", "discharge circuit", "V_D between HET anode and a cathode electrode inside the RF source; isolation "
                                         "transformer; 50 ohm series resistor; 13.56 MHz L-C resonance circuit in "
                                         "series", "-", 3, "p. 3; Fig. 1a", "measured (reported circuit description)",
          "zero net current to the grounded chamber ensured by the isolation transformer"),
        A("TAK-07", "collector ('cathode electrode')", {"type": "C-type stainless steel with axial slit",
                                                         "axial_length_mm": 100.0}, "mm", 3, "p. 3; Fig. 1b",
          "measured (reported hardware dimension)", "installed on the inner wall of the source tube"),
        A("TAK-08", "annular discharge onset", {"V_D_gt_V": 140.0, "no_rf": "no annular discharge for any V_D"}, "V",
          3, "p. 3 (visual observation); p. 6 text; Fig. 4a on p. 7", "measured (reported observation)",
          "analog only; not a Vyovrinda threshold"),
        A("TAK-09", "HET magnetic field (calculated)", {"B_r_peak_T": [0.1, 0.15], "z_mm": -10.0}, "T, mm", 4,
          "p. 4; Fig. 2 (SmCo permanent magnets)", "model-derived (authors' calculation)",
          "permanent-magnet HET; z = 0 at the HET exit"),
        A("TAK-10", "collector potential and ion impact energy", {"V_K_V": -100.0, "E_ion_ICP_eV": 140.0,
                                                                   "E_ion_HET_eV": 220.0}, "V, eV", 6,
          "p. 6 text; Fig. 4a on p. 7", "measured (V_K) / inferred (ion energies)", "V_K decreases to -100 V with increasing V_D"),
        A("TAK-11", "sputtering and deposition", "sputtered stainless steel deposited on the glass wall and on insulators "
                                                 "at the front of the HET", "-", 6, "p. 6 text; Fig. 5 (illustration) on p. 8",
          "measured (reported post-test observation)", "authors: negative collector potential to be minimized"),
        A("TAK-12", "RF power transfer efficiency", {"R_ant_ohm": 0.36, "R_total_ohm": 0.4, "eta_p": 0.1,
                                                     "P_absorbed_W": 20.0}, "ohm, -, W", 8, "p. 8, Eq. (1)",
          "inferred (from measured resistances)", "eddy-current heating of the collector electrode"),
        A("TAK-13", "discharge current and its limit", {"I_D_A_about": 1.0}, "A", 8,
          "p. 8 text; p. 7 Fig. 4b", "measured (reported)",
          "authors: the discharge-current limit 'seems to be decided by the rf power' (p. 7)"),
        A("TAK-14", "plume diagnostic position", {"RFEA_z_cm": 25.0}, "cm", 3, "p. 3; z = 0 at the HET exit",
          "measured (reported setting)", "RFEA 10 mm entrance orifice"),
    ]


def interface_demands() -> list:
    D = []

    def d(did, frm, to, quantity, value, units, status):
        D.append({"id": did, "from": frm, "to": to, "quantity": quantity, "value": value, "units": units,
                  "status": status})

    me = "A9-03"
    # A9-01 prereg framework
    d("ID-01", me, "A9-01", "configuration ids and per-configuration hardware identity (which ICD items may differ "
      "between hall_c1_reference and hall_icp_neutralizer)", "ICP-01..ICP-46 applies_to", "-", "PROPOSED")
    d("ID-02", "A9-01", me, "definition of the V_d setting held equal across configurations", None, "V",
      pending("A9-01", "V_d definition"))
    d("ID-03", "A9-01", me, "ICP ignition dwell/retry bound; start/restart classification; start-up/thermal-state rule",
      None, "s, count", pending("A9-01", "start rules"))
    d("ID-04", "A9-01", me, "stage map (Ar ENGINEERING_ONLY -> N2 -> O2 NO_ATOMIC_O) and exchange schedule", None, "-",
      pending("A9-01", "stage map"))
    # A9-02 bus boundary
    d("ID-05", me, "A9-02", "ICP active loads needing bus slots: RF source/matching, collector/bias, active cooling "
      "(if any); no assist magnet in v1", ["rf_source_matching", "collector_bias", "active_cooling_if_used"], "W",
      "PROPOSED")
    d("ID-06", me, "A9-02", "laboratory RF forward-power range (capability, not allocation)",
      [0.0, rf_heat_bound_W()[0]], "W",
      "OWNER_GIVEN (row 72)")
    d("ID-07", "A9-02", me, "bus slot ids, ledger efficiencies, start-up transient accounting", None, "W",
      pending("A9-02", "slots") + " + " + A9_02_MODULE)
    # A9-04 uncertainty budget
    d("ID-08", me, "A9-04", "measurement chains owned by the ICD: P_fwd/P_refl coupler, collector V/I, body potential, "
      "B(z) maps, exchange series", ["ICP-14", "ICP-21", "ICP-20", "ICP-31", "ICP-39"], "-", "PROPOSED")
    d("ID-09", "A9-04", me, "uncertainty allocations: RF power chain, alignment/installation share, stop rules", None,
      "W, mm, deg, ln-ratio", pending("A9-04", "allocations"))
    # A9-05 evidence
    d("ID-10", me, "A9-05", "this lane's page-cited Takahashi 2024 extraction (annex) for reconciliation",
      "TAK-01..TAK-14", "-", "PROPOSED")
    d("ID-11", "A9-05", me, "authoritative analog evidence and validation-input list (RF coupling, electron extraction "
      "current, collector potential, neutralization margin, ICP pressure/flow, start-up, erosion, life; row 145)", None,
      "-", pending("A9-05", "evidence matrix") + " and PENDING " + A9_05_VALIDATION_INPUTS)
    # H2-1
    d("ID-12", me, "H2-1", "downstream/coaxial neutralizer interface on the H-1 exit face; H-1 neutralizer-agnostic; "
      "external C1 (row 79) -> channel sizing no longer constrained by a central bore", "required", "-",
      "PROPOSED (H2-1 revision A9-07)")
    d("ID-13", "H2-1", me, "exit-face geometry, channel OD (frozen), MC-1 stray field in the ICP volume and at the C1 "
      "orifice (FEMM)", None, "mm, G", pending("H2-1", "revision for external C1 / FEMM"))
    # H2-2
    d("ID-14", me, "H2-2", "C1 moves to an external reference module on KC-1 (L-EXTERNAL); orifice position per "
      "installation", "required", "-", "PROPOSED (H2-2 revision A9-07)")
    # H2-4
    d("ID-15", me, "H2-4", "ICP PPU channels: 13.56 MHz RF source, collector/bias supply; floating secondaries",
      "required", "-", "PROPOSED")
    # H2-5
    d("ID-16", me, "H2-5", "RF-path heat contribution only (ICP-36 partial term; NOT a bound on the total module heat "
      "load, which adds collector particle heating from the Hall discharge current and plume interception, ICP-43)",
      rf_heat_bound_W()[1], "W",
      "DERIVED_BOUND (ICP-36, RF-only partial term)")
    d("ID-17", "H2-5", me, "sink / interface temperature cases and the >= 50 K margin revision", None, "K",
      pending("H2-5", ">= 50 K revision (row 86)"))
    # H2-6
    d("ID-18", me, "H2-6", "kinematic carrier KC-1 shared by C1 reference module, ICP module and sham; H-1 bolted",
      "required", "-", "PROPOSED")
    d("ID-19", me, "H2-6", "service-line bundle additions: RF coax (live in ICP, sham in C1), ICP collector/bias leads, "
      "ICP thermocouples, ICP pressure line, ICP gas line (if dedicated), MODULE_ID/interlock lines", "required", "-",
      "PROPOSED")
    d("ID-20", me, "H2-6", "diagnostics: directional coupler, RF-immune B(z) mapping check, pickup test channels, "
      "witness positions on H-1 front face and module", "required", "-", "PROPOSED")
    d("ID-21", "H2-6", me, "carrier seat dimensions, stand payload capability (>= 25 kg, row 116), per-configuration "
      "calibration procedure", None, "mm, kg", pending("H2-6", "fixture revision for A9"))
    # H2-7
    d("ID-22", me, "H2-7", "new BOM lines: ICP neutralizer, RF generator/matching/feedthrough, collector/bias hardware "
      "(row 59); C1 kept as reference/fallback", "required", "kg", "PROPOSED")
    d("ID-23", "H2-7", me, "module masses and CG per serial; flight dry allocations vs CBE (row 54 flags)", None, "kg",
      pending("H2-7", "A9 amendment (A9-06)"))
    # Xe ledger
    d("ID-24", me, "Xe ledger", "ICP gas feed booking if mode G-XE (PHASE_TOTAL_FLOW, row 42); ICP lifetime/cycle "
      "requirement replaces the continuous C1 cathode term (row 46)", None, "kg",
      "TBD - requires the owner choice of the ICP gas mode (ICPQ-02); ledger at " + xe_budget_dir())
    d("ID-25", "A9-02", me, "maximum discharge-supply power at the stand P_d,max = I_d,max x V_d,max (for the total "
      "module heat-load bound ICP-43)", None, "W", pending("A9-02", "discharge slot limit"))
    d("ID-26", me, "H2-5", "total ICP module heat load for the thermal path (ICP-43: RF + discharge-path + plume terms)",
      None, "W", "PENDING " + A9_LANES["A9-02"] + " (P_d,max; ICP-43)")
    d("ID-27", "A9-02", me, "maximum discharge current of the stand discharge slot I_d,max as the SIZING input for the "
      "ICP electron-extraction capability (ICP-45), not only as a heat input", None, "A",
      pending("A9-02", "discharge slot I_d,max"))
    d("ID-28", me, "A9-01", "electron-current capacity demonstration (collector-current step/ramp to I_d,max on Ar "
      "ENGINEERING_ONLY, ICP-45) as a stage entry condition before any score-bearing hall_icp_neutralizer point",
      "required", "-", "PROPOSED")
    d("ID-29", "A9-05", me, "published analog evidence on extracted electron current vs RF power for RF/ICP plasma "
      "cathodes (context for ICP-45; never a Vyovrinda prediction)", None, "A, W",
      pending("A9-05", "electron-current vs RF power evidence"))
    return D


def owner_answers_applied() -> list:
    how = {
        5: "mass items are full wet-system gates; stand mass (ICP-08) kept separate from flight mass",
        8: "RF chain items specified at quotation level only (ICP-15)",
        17: "H-1 fixed; only the downstream electron-source module is swapped (ICP-06, ICP-10)",
        18: "no numeric margin carried; tolerances are LOCK-1 rules / LOCK-2 values (ICP-03)",
        19: "exchange series cycle count fixed at LOCK-2; >= 3 engineering replicates (ICP-39)",
        23: "two elevated p_b levels; T-PB-MAX not frozen here (ICP-28)",
        24: "ICP ignition, Hall ignition with ICP electrons, restart and cycle count recorded (ICP-35)",
        29: "schedule is order-balanced; deferred to A9-01 (ICP-42)",
        33: "RR-07 adapted to C1 <-> ICP exchange (ICP-39)",
        36: "gas order Ar (engineering-only) -> N2 -> O2-bearing (ICP-30)",
        37: "no scalar ranking; ICD supplies measured quantities only",
        38: "OPEN treated as a status, not an outcome (outcome_vocabulary)",
        39: "NOT_TESTED slot rule referenced (ICP-42)",
        40: "REF-COND own installation per block referenced (ICP-42)",
        42: "any dedicated Xe to the ICP booked as PHASE_TOTAL_FLOW (ICP-26)",
        46: "ICP carries its own lifetime/cycle requirement; ICP gas feed made an explicit booked item (ICP-26)",
        49: "heated Xe-fed LaB6 C1 on the reference module (ICP-25)",
        54: "v0 flight allocations cited as allocations, not stand masses or CBEs (ICP-08)",
        59: "BOM demand for ICP/RF/collector lines (ID-22)",
        61: "dedicated downstream ICP envelope, no ECR-sized common envelope (ICP-07)",
        62: "MODULE_ID, RF fwd/refl, interlock, collector V/I, temperatures, cmd/tlm (ICP-16, ICP-33, ICP-34)",
        63: "Hall-exhaust-to-ICP pressure/conductance interface defined and measured; sham for stand parasitics only "
            "(ICP-09, ICP-27)",
        64: "exchange checks cold/tare, parasitic, B(z), isolation, RF pickup (ICP-17, ICP-39)",
        65: "no dwell matching; start-up/thermal-state equivalence deferred to A9-01 (ICP-41)",
        66: "every ICP load gets a bus slot on the new boundary (ICP-24, ICP-38)",
        67: "B(z) perturbation/sensitivity scan; tolerance from measured sensitivity, none invented (ICP-31)",
        69: "unmagnetized v1 ICP; assistance only as a new booked variant (ICP-32)",
        70: "floating body; separately controlled/measured collector bias; never hard-grounded by default "
            "(ICP-20, ICP-21)",
        71: "all ICP interfaces frozen before score-bearing Phase 1 (freeze points LOCK-1/LOCK-2)",
        72: "13.56 MHz; 0-500 W lab forward power; directional coupler; calorimetry as cross-check (ICP-11..ICP-15)",
        77: "Ni-clad/nickel perturbation measured (ICP-32)",
        79: "external C1 reference; downstream/coaxial ICP interface; H-1 neutralizer-agnostic (ICP-02, ICP-05)",
        81: "DC discharge-circuit isolation rated to 350 V + margin (ICP-23); RF antenna circuit rated separately "
            "(ICP-44)",
        83: "repaired/replaced module = new serial + new reference sequence (ICP-40)",
        86: ">= 50 K margin and 20 % heat-load margin (ICP-36 RF-only term, ICP-43 total, ICP-37)",
        89: "pulsed keeper ignition 300-600 V class on the C1 module (ICP-25); keeper-pulse isolation rating (ICP-46)",
        91: "selectable cathode-common bleeder, no value frozen (ICP-22, ICP-25)",
        93: "120 s x 2 applies to C1 only; ICP bound pre-registered by A9-01 (ICP-35)",
        99: "passive/low-perturbation witnesses near the electron sources (ICP-29)",
        103: "silver excluded from O2-wetted ICP parts (ICP-30)",
        105: "gas-line isolator practice applied to any ICP gas line crossing a potential difference (ICP-23)",
        107: "ASTM G93 Level C for O2-service ICP parts (ICP-30)",
        108: "P_bus < 1.5 kW at the spacecraft-DC boundary incl. start-up transients on the A9 boundary (ICP-12, ICP-24)",
        109: "ICP power inside the ~1.35 kW internal allocation (ICP-12, ICP-24, ICP-45)",
        110: "supply partition incl. ICP RF source/matching and collector/bias (ICP-24)",
        116: "stand designed for >= 25 kg moving payload (ICP-08)",
        117: "flexible RF coax with matched sham routing (ICP-18)",
        122: "kinematic carrier exchanges C1 and ICP modules; H-1 bolted (ICP-06)",
        129: "I_d(t) chain declares its RF rejection/transfer function (ICP-17)",
        130: "ICP-specific telemetry and flight subset (ICP-34)",
        131: "facility sink measured per run (ICP-37)",
        132: "NO_ATOMIC_O label; AO life separate (ICP-30)",
        133: "matched sham service lines in every configuration (ICP-09, ICP-18)",
        134: "witness coupons non-functional exchangeable items (ICP-29)",
        145: "validation inputs owned by A9-05 (ID-11)",
        146: "no surfaces or screening values manufactured",
    }
    ans = answers_by_row()
    out = []
    for r in sorted(how):
        out.append({"row": r, "covers_ids": ans[r]["covers_ids"], "answer_sha256": answer_fingerprint(r),
                    "how_applied": how[r]})
    return out


def open_owner_questions() -> list:
    return [
        {"id": "ICPQ-01", "question": "The lane brief calls the downstream position 'IP-DN', but IP-DN already names the "
         "H-1 rear inlet flange (H2-1, historical pre-ionizer ICD). Adopt IP-EXIT (H-1 exit plane) and IP-NEU "
         "(downstream module datum) for A9 and keep IP-DN historical?", "proposed_answer": "YES - avoids a silent "
         "redefinition of an existing plane"},
        {"id": "ICPQ-02", "question": "Primary ICP gas mode: G-REUSE (Hall exhaust, analog practice), G-XE (dedicated "
         "Xe, Xe ledger) or G-ATM (dedicated atmospheric feed)?", "proposed_answer": "owner call; proposal: the module "
         "carries a capped dedicated port so all modes remain testable as declared variants; Ar engineering "
         "reproduction starts in G-REUSE; the mode used for N2/O2 score-bearing data is fixed at LOCK-1 and booked"},
        {"id": "ICPQ-03", "question": "Mount both downstream modules on the moving platform so plume-module forces "
         "are inside the measured system (ICP-10)?", "proposed_answer": "YES"},
        {"id": "ICPQ-04", "question": "Which V_d is held equal across configurations: supply-terminal voltage or "
         "anode-to-electron-source-reference potential (series resistor/filter drops differ)?",
         "proposed_answer": "owner call via A9-01; proposal: hold the supply-terminal setting equal and record "
         "anode-to-ground, reference-to-ground and loop-element drops so either definition can be reported"},
        {"id": "ICPQ-05", "question": "Matching network on the moving platform or off it (long flexible coax across the "
         "stand)?", "proposed_answer": "owner call; proposal: off-platform unless the S1a dummy-load cable-loss/"
         "reflected-power characterisation requires on-platform matching"},
        {"id": "ICPQ-06", "question": "Apply the row-105 gas-isolator qualification practice (~1 kV DC representative "
         "pressure/gas withstand) to any ICP gas line crossing a potential difference, and the same isolation margin as "
         "H-1 to the ICP body/collector?", "proposed_answer": "YES (margin value remains the H-1 owner item)"},
        {"id": "ICPQ-07", "question": "Collector material for N2/O2-bearing operation (the analog's stainless steel "
         "sputtered and deposited)?", "proposed_answer": "owner call; proposal: add collector candidates to the biased/"
         "floating coupon programme of row 106 before freezing"},
        {"id": "ICPQ-08", "question": "B(z) mapping with RF energized may be corrupted by pickup; accept 'energized where "
         "the gaussmeter is shown RF-immune, otherwise immediately after RF-off' as the ICP-31 rule?",
         "proposed_answer": "YES"},
        {"id": "ICPQ-09", "question": "Plume interception by a Takahashi-type enclosing source is a real architecture "
         "consequence; report it inside the system boundary without correction (ICP-29)?", "proposed_answer": "YES"},
        {"id": "ICPQ-10", "question": "Total ICP module heat-load bound (ICP-43): use 1.20 x (P_fwd,max + P_d,max) with "
         "P_d,max from the A9-02 discharge slot, or, if every score-bearing stand point is held inside the P_bus < 1.5 kW "
         "ceiling (row 108), the envelope 1.20 x 1.5 kW used for the stand by H2-6 H26-44?", "proposed_answer": "owner "
         "call; proposal: 1.20 x (P_fwd,max + P_d,max), because laboratory RF forward power (0-500 W) is a capability "
         "that is not itself held inside the P_bus ceiling"},
        {"id": "ICPQ-11", "question": "Factor k_RF between the rated antenna-circuit RF voltage and the computed "
         "V_ant,peak at 500 W (ICP-44)?", "proposed_answer": "owner call (LOCK-1); no value proposed here"},
    ]


def hard_incompatibility_check() -> dict:
    return {
        "verdict": "none identified",
        "veto_claimed": False,
        "checked": [
            {"item": "ICP module aperture vs the H-1 channel OD window (ICP-04)",
             "finding": "not assessable yet: H-1 channel OD is PRELIMINARY (H2-1) and the ICP module is not designed; "
                        "left TBD at LOCK-1, not a veto"},
            {"item": "external C1 (row 79) vs the H2-2 PRELIMINARY L-CENTRAL choice",
             "finding": "a location revision (A9-07), not an architecture incompatibility; H2-2 carries L-EXTERNAL as "
                        "its alternative"},
            {"item": "ICP power vs the ~1.35 kW internal allocation (row 109) and P_bus < 1.5 kW (row 108)",
             "finding": "not assessable: bus slots PENDING A9-02 and no performance is predicted here; decided only by "
                        "measurement against the full-system gate"},
            {"item": "ICP electron-current capacity at I_d,max vs RF power inside the ~1.35 kW internal allocation "
                     "(row 109) (ICP-45)",
             "finding": "not assessable, PENDING " + A9_LANES["A9-02"] + " (I_d,max) and " + A9_LANES["A9-05"]
                        + " (analog electron-current vs RF power evidence). A real tension to watch: the only analog "
                          "in the annex reported ~1 A at 200 W forward power with the limit attributed to the RF power "
                          "(TAK-04, TAK-13); no scaling to H-1 is made and no veto is claimed; decided only by the "
                          "ICP-45 capacity demonstration"},
            {"item": "stand payload (>= 25 kg design, row 116) vs module mass on the carrier",
             "finding": "module masses PENDING H2-7 / module design; no evidence of exceedance"},
            {"item": "antenna-circuit RF voltage vs the 350 V DC isolation item",
             "finding": "resolved by separating the RF rating (ICP-44) from the DC discharge-circuit rating (ICP-23); "
                        "no incompatibility, a design item"},
        ],
    }


def historical_reuse() -> dict:
    return {
        "artifacts": [{"key": k, "path": p, "sha256": sha256_of(p)} for k, p in HISTORICAL.items()],
        "reused": [
            "document structure: common interface items with requirement / value-or-TBD / verification, annex, "
            "owner-question and compliance sections, pinned-input list, --check builder",
            "concept: module exchange as the controlled variable with matched shams (now C1 vs ICP downstream modules)",
            "concept: MODULE_ID in every record; interlock permissives; separated RF return; dummy-load pickup check",
            "concept: kinematic carrier with weight off the H-1 mount (via H2-6 H26-FX-02 / H26-41)",
            "concept: RF load-plane measurement with a directional coupler (PIM-RF annex) - re-based on row 72",
        ],
        "not_reused": [
            "common envelope sized to the ECR occupant (PMI-01; superseded by row 61)",
            "control harness L1-L5 definition (PMI-04; superseded by row 62)",
            "pressure-drop class and PIM-0 blank/flow-equivalent module (PMI-10, PM0-*; superseded by row 63)",
            "time-matched Xe hold (DEV-H0-05 / PMQ-05; superseded by row 65)",
            "installation-reproducibility numbers u_inst_max, K, r (PMI-11; historical A5/A6 numbers not carried, "
            "rows 18/19)",
            "bus_power_boundary_v1 slots (PMI-03; a new A9 boundary is used, row 108)",
            "configuration ids hall_only / rf_hall / ecr_hall and HW-0/HW-RF/HW-ECR (superseded by rows 17, 28)",
            "upstream plane IP-UP..IP-DN module slot (the A9 source is downstream of IP-EXIT)",
        ],
        "never_edited": True,
    }


def m16_impact() -> list:
    m = load(DELIVERABLES["M16"])
    rows = {r["key"]: r for r in m["rows"]}
    spec = [
        ("cathode", "C1 becomes reference/fallback on an external module (row 79); ICP electron source is the primary "
                    "investigation", "BLOCKED", "H2-2 revision for L-EXTERNAL (A9-07)"),
        ("hall_chamber", "H-1 exit face carries the downstream/coaxial interface; neutralizer-agnostic", "BLOCKED",
         "H2-1 revision (external C1, exit-face geometry)"),
        ("magnetic_circuit", "B(z) perturbation/sensitivity scan with the ICP installed/energized; stray field in the "
                             "ICP volume", "BLOCKED", "FEMM of the preliminary circuit (H2-1)"),
        ("ppu", "new ICP RF source/matching and collector/bias channels", "BLOCKED",
         "PENDING A9-02 bus slots"),
        ("thermal_control", f"ICP dissipation path: RF-only partial term {rf_heat_bound_W()[1]:g} W (ICP-36), total module heat load "
                            "TBD (ICP-43, adds discharge-path and plume terms), >= 50 K margin", "BLOCKED",
         "ICP module design + P_d,max (A9-02) for ICP-43 + H2-5 revision for row 86"),
        ("control_fdir", "RF interlock, neutralizer health state, ICP command set", "BLOCKED",
         "generator interlock interface (quotation)"),
        ("sensors_diagnostics", "directional coupler, collector V/I, RF pickup checks, ICP pressure port",
         "BLOCKED", "S1a pickup and coupler calibration"),
        ("mechanical_structural", "kinematic carrier KC-1 shared datum; module envelope", "BLOCKED",
         "H2-6 fixture revision + module drawings"),
        ("preionizer_interface", "row superseded for the primary line; proposed replacement row 'downstream ICP "
                                 "neutralizer interface' governed by this ICD (row change is an A9-10 governance item)",
         "BLOCKED", "A9-10 M16 governance update"),
    ]
    out = []
    for key, how, state, blocker in spec:
        if key not in rows:
            raise KeyError(f"M16 row key {key!r} not found")
        out.append({"m16_row": rows[key]["row"], "key": key, "name": rows[key]["name"], "how_touched": how,
                    "proposed_state": state, "blocking_item": blocker})
    return out


def h3_h4_inputs() -> dict:
    return {
        "h3_procurement_quotation_only": [
            {"item": "13.56 MHz RF generator, 0-500 W forward, interlock input, remote fwd/refl readout",
             "spec_level": "ICP-11, ICP-12, ICP-16", "status": "quotation only (row 8)"},
            {"item": "matching network (auto or manual) rated for full forward power", "spec_level": "ICP-13, ICP-15",
             "status": "quotation only (row 8)"},
            {"item": "calibrated dual directional coupler + power sensors at the load plane", "spec_level": "ICP-14",
             "status": "quotation only (row 8)"},
            {"item": "vacuum RF feedthrough and flexible low-stiffness coax (live + sham)", "spec_level": "ICP-15, ICP-18",
             "status": "quotation only (row 8)"},
            {"item": "ICP chamber components (dielectric tube, antenna, shield, collector)",
             "spec_level": "ICP-02, ICP-04, ICP-07, ICP-19, ICP-21", "status": "quotation only (row 8)"},
            {"item": "floating collector/bias supply with V/I readback", "spec_level": "ICP-21, ICP-24",
             "status": "quotation only (row 8)"},
            {"item": "capacitance manometer for the ICP source volume", "spec_level": "ICP-27",
             "status": "quotation only (row 8)"},
        ],
        "h4_tests": [
            {"stage": "S1a (engineering)", "measure": "dummy-load and energized RF pickup on all channels",
             "closes": "ICP-17"},
            {"stage": "S1a", "measure": "coupler calibration + calorimetric cross-check; load-plane loss chain",
             "closes": "ICP-14"},
            {"stage": "S1a", "measure": "cold-flow pressure/conductance with each module", "closes": "ICP-27"},
            {"stage": "S1a", "measure": "B(z) maps C1 module / ICP unpowered / ICP energized + coil sensitivity",
             "closes": "ICP-31"},
            {"stage": "S1a", "measure": "C1 <-> ICP exchange series (cold/tare, parasitic, B(z), isolation, pickup)",
             "closes": "ICP-39"},
            {"stage": "Ar ENGINEERING_ONLY", "measure": "topology reproduction: ICP ignition, Hall ignition with ICP "
                                                         "electrons, collector V/I, thermal map, deposition witnesses",
             "closes": "ICP-21, ICP-29, ICP-36, ICP-43 (engineering evidence only)"},
            {"stage": "facility-effect series", "measure": "base + two elevated p_b levels per configuration",
             "closes": "ICP-28"},
        ],
    }


def build() -> dict:
    decision_pins = check_decisions()
    deliverable_pins = [{"key": k, "path": p, "sha256": sha256_of(p)} for k, p in DELIVERABLES.items()]
    X = items()
    ids = [x["id"] for x in X]
    if ids != [f"ICP-{i:02d}" for i in range(1, len(X) + 1)]:
        raise RuntimeError(f"item ids not sequential: {ids}")
    a9 = load(DECISIONS["A9"][0])
    doc = {
        "schema": "icp_neutralizer_icd_v1",
        "id": "icp_neutralizer_icd_v1",
        "title": "Downstream 13.56 MHz RF-ICP neutralizer interface control document (A9)",
        "lane": "A9_03",
        "follow_on": "fo_a9_03_icp_neutralizer_icd",
        "trigger": "T_A9_03_ICP_ICD",
        "status": "DRAFT_PENDING_OWNER",
        "a9_status": a9["status"],
        "base_commit": BASE_COMMIT,
        "generated_by": THIS_SCRIPT,
        "companion_document": OUT_MD,
        "test": TEST,
        "governing_decision": {"path": DECISIONS["A9"][0], "sha256": DECISIONS["A9"][1]},
        "owner_answers": {"path": DECISIONS["ANS"][0], "sha256": DECISIONS["ANS"][1],
                          "verbatim_pack": {"path": DECISIONS["PACK"][0], "sha256": DECISIONS["PACK"][1]}},
        "decision_pins": decision_pins,
        "deliverable_pins": deliverable_pins,
        "never_pinned": ["docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                         "docs/orchestration/trigger_ledger_v2.jsonl", "docs/orchestration/runtime_state.json"],
        "standing_facts": {
            "a9": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE; RF is downstream, not an upstream "
                  "pre-ionizer and not a parallel thrust branch",
            "credible_hall_set": "EMPTY (no Hall transport closure admitted)",
            "p5_n2_v1": "INCONCLUSIVE (permanent)",
            "bundle1": "NO_BASELINE_YET",
            "no_prediction": "this ICD predicts no thrust, efficiency, discharge current, neutralizer electron current "
                             "or plasma state",
            "no_winner": "no configuration is ranked, preferred or eliminated here",
            "full_system_gates": "25 mN, P_bus < 1.5 kW (spacecraft-DC boundary incl. start-up transients, row 108), "
                                 "< 40 kg wet (row 5) are full-system gates",
            "scope": "Hall-closure uncertainty never leaks upstream; nothing upstream of HALL_INLET_Z0 changes between "
                     "configurations",
        },
        "configurations": list(CONFIGURATIONS),
        "control_items": ["sham_module"],
        "outcome_vocabulary": list(OUTCOME_VOCABULARY),
        "status_not_outcome": list(STATUS_VOCABULARY_NOT_OUTCOME),
        "evidence_classes": list(EVIDENCE_CLASSES),
        "freeze_points": list(FREEZE_POINTS),
        "freeze_point_definitions": {
            "NOW": "fixed by an owner answer or a verified deliverable at this revision",
            "LOCK-1": "rule/value frozen at LOCK-1 (interfaces frozen before score-bearing Phase 1, row 71)",
            "LOCK-2": "value frozen at LOCK-2 from S1 evidence, before any score-bearing run",
            "after-evidence": "value frozen from S1a engineering measurements (e.g. cold-flow conductance, measured "
                              "B(z) sensitivity) and recorded before LOCK-2; like every interface item it is frozen "
                              "before any score-bearing Phase 1 run (row 71) and never adjusted after score-bearing data",
        },
        "interface_planes": interface_planes(),
        "items": X,
        "interface_demands": interface_demands(),
        "owner_answers_applied": owner_answers_applied(),
        "open_owner_questions": open_owner_questions(),
        "historical_reuse": historical_reuse(),
        "m16_impact": m16_impact(),
        "h3_h4_inputs": h3_h4_inputs(),
        "hard_incompatibility_check": hard_incompatibility_check(),
        "published_analog_annex": {"source": TAKAHASHI, "entries": analog_annex()},
        "pending_lanes": {k: v for k, v in A9_LANES.items()},
        "compliance": {
            "no_hall_performance_source": "no Hall transport closure, screening candidate, abep_sim/plasma_devices.py "
                                          "or withdrawn v1.2-v1.6 number is read",
            "analog_use": "Takahashi 2024 values appear only in the annex, with page provenance and label 'published "
                          "analog, reported'; body items reference annex ids (TAK-xx) for context only and never use "
                          "an analog value as a design value",
            "lane_paths": "A9-01 is referenced at the path where that lane landed (" + A9_LANES["A9-01"] + "); the A9 "
                          "decision text names the same lane as docs/experiments/hall_icp/prereg/ - same lane, "
                          "different name",
            "no_contact": "no supplier, lab or author contact; open-access sources only",
            "pure": "standard-library builder; not wired into archengine; no frozen data, goldens or existing modules "
                    "touched",
            "thresholds": "no numeric threshold beyond the RFP and cited owner rows; tolerances are LOCK-1 rules / "
                          "LOCK-2 values or after-evidence",
        },
    }
    return doc


# ----------------------------------------------------------------------------------------------------------------------
# markdown
# ----------------------------------------------------------------------------------------------------------------------
def _fmt(v) -> str:
    if v is None:
        return "**TBD**"
    if isinstance(v, (dict, list)):
        return "`" + json.dumps(v, ensure_ascii=False) + "`"
    return str(v)


def _srcs(sources) -> str:
    parts = []
    for s in sources:
        if "row" in s:
            parts.append(f"row {s['row']}")
        elif "ref" in s:
            parts.append(f"{s['ref']} p. {s['page']}")
        elif "pointer" in s:
            parts.append(f"`{s['path']}#{s['pointer']}`")
        else:
            parts.append(f"`{s['path']}` {s.get('id', '')}".strip())
    return "; ".join(parts)


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a(f"# Downstream ICP-neutralizer ICD (`{doc['id']}`)")
    a("")
    a("<!-- generated by docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py; do not edit by hand -->")
    a("")
    a("| item | value |")
    a("|---|---|")
    a(f"| follow-on / trigger | `{doc['follow_on']}` / `{doc['trigger']}` (lane {doc['lane']}) |")
    a(f"| status | {doc['status']} (A9: {doc['a9_status']}) |")
    a(f"| machine-readable | `{OUT_JSON}` |")
    a(f"| builder | `{THIS_SCRIPT}` (`--check` verifies both files) |")
    a(f"| test | `{TEST}` |")
    a(f"| base commit | `{doc['base_commit']}` |")
    a(f"| governing decision A9 | `{doc['governing_decision']['path']}` sha256 `{doc['governing_decision']['sha256']}` |")
    a(f"| owner answers (147) | `{doc['owner_answers']['path']}` sha256 `{doc['owner_answers']['sha256']}` |")
    a(f"| verbatim pack | `{doc['owner_answers']['verbatim_pack']['path']}` sha256 "
      f"`{doc['owner_answers']['verbatim_pack']['sha256']}` |")
    a("")
    a("Interface definition for owner review. Nothing here is approved, pre-registered, procured or frozen. Owner answers "
      "are cited by row. Values are owner-given, copied from verified deliverables (path + JSON pointer + sha256), "
      "a labelled arithmetic bound, published analog (annex only), or TBD / PENDING.")
    a("")
    a("## Standing facts")
    a("")
    for k, v in doc["standing_facts"].items():
        a(f"* **{k}**: {v}")
    a("")
    a(f"Configurations: {', '.join('`' + c + '`' for c in doc['configurations'])}; control item: `sham_module` "
      "(stand parasitics only). Outcome vocabulary: " + ", ".join('`' + o + '`' for o in doc['outcome_vocabulary']) +
      "; `OPEN` is a status, not an outcome (row 38).")
    a("")
    a("Freeze points:")
    for k, v in doc["freeze_point_definitions"].items():
        a(f"* **{k}**: {v}")
    a("")
    a("## 1. Interface planes")
    a("")
    for p in doc["interface_planes"]:
        a(f"* **{p['id']}** - {p['definition']} ({p['status']})")
    a("")
    a("## 2. Items (a)")
    a("")
    a("| id | group | title | value | units | evidence class | status | freeze point | rows |")
    a("|---|---|---|---|---|---|---|---|---|")
    for x in doc["items"]:
        st = x["status"] if not x["status"].startswith("PENDING") else "PENDING"
        a(f"| {x['id']} | {x['group']} | {x['title']} | {_fmt(x['value'])} | {x['units']} | "
          f"{x['evidence_class'] or '-'} | {st} | {x['freeze_point']} | "
          f"{', '.join(str(r) for r in x['owner_rows']) or '-'} |")
    a("")
    for x in doc["items"]:
        a(f"### {x['id']} {x['title']}")
        a("")
        a(f"**Requirement.** {x['requirement']}")
        a("")
        a(f"* value: {_fmt(x['value'])} [{x['units']}]")
        if x.get("tbd"):
            a(f"* {x['tbd']}")
        a(f"* basis: {x['basis']}")
        a(f"* sources: {_srcs(x['sources'])}")
        a(f"* evidence class: {x['evidence_class'] or '- (TBD/PENDING)'}; status: {x['status']}; "
          f"freeze point: {x['freeze_point']}")
        a(f"* applies to: {', '.join(x['applies_to'])}")
        a(f"* verification: {x['verification']}")
        if x.get("copied_from"):
            c = x["copied_from"]
            a(f"* copied input: {_fmt(c['value'])} {c['units'] or ''} ({c['evidence_class']}; source status "
              f"{c['source_status']}; `{c['source']['path']}#{c['source']['pointer']}`)")
        if x.get("note"):
            a(f"* note: {x['note']}")
        a("")
    a("## 3. Interface demands (b)")
    a("")
    a("| id | from | to | quantity | value | units | status |")
    a("|---|---|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        a(f"| {d['id']} | {d['from']} | {d['to']} | {d['quantity']} | {_fmt(d['value'])} | {d['units']} | "
          f"{d['status']} |")
    a("")
    a("## 4. Owner answers applied (c)")
    a("")
    a("| row | covers | how applied |")
    a("|---|---|---|")
    for r in doc["owner_answers_applied"]:
        a(f"| {r['row']} | {', '.join(r['covers_ids'])} | {r['how_applied']} |")
    a("")
    a("## 5. Open owner questions (d)")
    a("")
    for q in doc["open_owner_questions"]:
        a(f"* **{q['id']}** {q['question']} Proposed: {q['proposed_answer']}")
    a("")
    a("## 6. Historical reuse (e)")
    a("")
    for h in doc["historical_reuse"]["artifacts"]:
        a(f"* `{h['path']}` sha256 `{h['sha256']}` (read only, never edited)")
    a("")
    a("Reused:")
    a("")
    for s in doc["historical_reuse"]["reused"]:
        a(f"* {s}")
    a("")
    a("Deliberately not reused:")
    a("")
    for s in doc["historical_reuse"]["not_reused"]:
        a(f"* {s}")
    a("")
    a("## 7. M16 impact (f)")
    a("")
    a("| M16 row | key | how touched | proposed state | blocking item |")
    a("|---|---|---|---|---|")
    for m in doc["m16_impact"]:
        a(f"| {m['m16_row']} | {m['key']} | {m['how_touched']} | {m['proposed_state']} | {m['blocking_item']} |")
    a("")
    a("## 8. H3 / H4 inputs (g)")
    a("")
    a("H3 (quotations only, row 8):")
    a("")
    for h in doc["h3_h4_inputs"]["h3_procurement_quotation_only"]:
        a(f"* {h['item']} - spec: {h['spec_level']} ({h['status']})")
    a("")
    a("H4 tests:")
    a("")
    for h in doc["h3_h4_inputs"]["h4_tests"]:
        a(f"* {h['stage']}: {h['measure']} -> closes {h['closes']}")
    a("")
    h = doc["hard_incompatibility_check"]
    a(f"## 9. Hard-incompatibility check: {h['verdict']} (veto claimed: {h['veto_claimed']})")
    a("")
    for c in h["checked"]:
        a(f"* {c['item']}: {c['finding']}")
    a("")
    s = doc["published_analog_annex"]["source"]
    a("## Annex A. Published analog (Takahashi et al. 2024) - interface context only")
    a("")
    a(f"{s['citation']}. DOI `{s['doi']}`; accessed {s['accessed']} at {s['url_accessed']} (retrieved PDF sha256 "
      f"`{s['retrieved_pdf_sha256']}`, {s['pages']} pages; {s['access']}). {s['crossref_check']}. Licence: {s['licence']}. "
      f"Evidence level: {s['evidence_level']}. {s['authority_note']}.")
    a("")
    a("| id | quantity | value | units | page | locator | evidence class |")
    a("|---|---|---|---|---|---|---|")
    for e in doc["published_analog_annex"]["entries"]:
        a(f"| {e['id']} | {e['quantity']} | {_fmt(e['value'])} | {e['units']} | {e['page']} | {e['locator']} | "
          f"{e['evidence_class']} |")
    a("")
    a("Every annex value is labelled 'published analog, reported' and is never a Vyovrinda performance or design value.")
    a("")
    a("## Compliance")
    a("")
    for k, v in doc["compliance"].items():
        a(f"* **{k}**: {v}")
    a("")
    a("## Pinned inputs")
    a("")
    for p in doc["decision_pins"]:
        a(f"* decision `{p['path']}` `{p['sha256']}`")
    for p in doc["deliverable_pins"]:
        a(f"* deliverable `{p['path']}` `{p['sha256']}`")
    a("")
    a("Not pinned (mutable governance): " + ", ".join(f"`{p}`" for p in doc["never_pinned"]))
    a("")
    return "\n".join(L)


def outputs() -> dict:
    doc = build()
    return {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n", OUT_MD: render_md(doc)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if a committed output differs from a fresh build")
    args = ap.parse_args(argv)
    outs = outputs()
    if args.check:
        bad = []
        for rel, txt in outs.items():
            p = _abs(rel)
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != txt:
                bad.append(rel)
        if bad:
            print("OUT OF DATE: " + ", ".join(bad))
            return 1
        print("OK: " + ", ".join(outs))
        return 0
    for rel, txt in outs.items():
        p = _abs(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
        print("wrote " + rel)
    return 0


# ---- A9-10 reconciliation overlay hooks (fo_a9_10_integration) ------------------------------------------------------
_a910_build_core = build


def build(*args, **kwargs):
    """Verified lane build followed by the declared A9-10 changes (docs/experiments/hall_icp/integration/a9_10_overlay.py)."""
    return A910.apply("A9-03", _a910_build_core(*args, **kwargs))


_a910_md_core = render_md


def render_md(doc):
    """Lane Markdown followed by the A9-10 reconciliation section generated from the same JSON."""
    return _a910_md_core(doc).rstrip("\n") + "\n" + "\n".join(A910.md_section(doc)) + "\n"


if __name__ == "__main__":
    sys.exit(main())
