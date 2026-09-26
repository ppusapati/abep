#!/usr/bin/env python3
"""Build the common operating-envelope comparison grid for hall_only / rf_hall / ecr_hall (lane 23, GRID).

One grid, used identically for the three architectures, so a later comparison is automatic and no architecture gets
favourable points. The grid is a list of *base points* (feed mode x feed state x [Xe mixing level] x discharge
voltage). Every architecture is evaluated at every base point; the only architecture-dependent element is the
pre-ionizer source-power level set: hall_only at P_source = 0 only, rf_hall and ecr_hall at the SAME non-zero set.

Inputs (read-only, never imported, resolved lazily with a clear error when missing):

* feed envelope  docs/architecture_comparison/feed_envelope/feed_envelope_v1.json   (FEED lane 16)
* Hall reference docs/architecture_comparison/hall_reference/hall_reference_v1.json (HALLREF lane 17)
* layer-1 calibration-nuisance names: hallthruster_bridge/ensemble/transport_ensemble_v0.json (read only; these names
  are FORBIDDEN as grid axes)

Everything taken from them is copied into the output's ``inputs`` block together with the sha256 of the file it came
from, so ``build_document(inputs)`` is a pure function and the committed grid can be re-derived without the
prerequisite files (``--check-offline``). ``--check`` re-extracts the inputs from the prerequisite files and compares.

No number is invented here: a level whose prerequisite value is TBD is TBD (value null plus 'requires'), a level that is
not in the RFP is PROPOSED, and the script performs no physics computation (it only enumerates and hashes).
Nothing here is wired into archengine; no Hall closure, screening candidate or Hall-map output is read.

Usage:
  python scripts/architecture/build_comparison_grid.py --feed-envelope F --hall-reference H --write
  python scripts/architecture/build_comparison_grid.py --check-offline
  python scripts/architecture/build_comparison_grid.py --feed-envelope F --hall-reference H --check
  python scripts/architecture/build_comparison_grid.py --freeze-status
  python scripts/architecture/build_comparison_grid.py --freeze --owner-decision REF --date YYYY-MM-DD
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GRID_REL = "docs/architecture_comparison/comparison_grid/comparison_grid_v1.json"
LOCK_REL = "docs/architecture_comparison/comparison_grid/comparison_grid_v1.lock.json"
SCHEMA_REL = "schemas/architecture_comparison/comparison_grid_v1.schema.json"
SCRIPT_REL = "scripts/architecture/build_comparison_grid.py"
DOC_REL = "docs/architecture_comparison/comparison_grid/COMPARISON_GRID.md"
FEED_REL = "docs/architecture_comparison/feed_envelope/feed_envelope_v1.json"
HALLREF_REL = "docs/architecture_comparison/hall_reference/hall_reference_v1.json"
ENSEMBLE_REL = "hallthruster_bridge/ensemble/transport_ensemble_v0.json"
ENV_FEED = "ABEP_FEED_ENVELOPE"
ENV_HALLREF = "ABEP_HALL_REFERENCE"

GRID_ID = "comparison_grid_v1"
GRID_VERSION = "1.0.0-draft"
STATUS_DRAFT = "DRAFT_PENDING_OWNER"
STATUS_FROZEN = "FROZEN"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
SOURCE_ARCHITECTURES = ("rf_hall", "ecr_hall")

# Axis names used by this grid. A test asserts that none of them is a layer-1 calibration-nuisance name.
AXIS_NAMES = ("feed_mode", "feed_state", "xe_anode_mass_fraction", "discharge_voltage_V", "p_source_W")

# Names that are never grid axes, in addition to the ensemble's calibration_nuisance keys (read from the ensemble file).
# The Hall transport closure (layer 2) is a scenario set applied to every point by the harness, never an axis.
ALWAYS_FORBIDDEN_AXES = ("ensemble_member_id", "transport_closure", "screening_candidate_id", "anomalous_transport",
                         "p5_registration", "p5_coil_shape", "beam_efficiency_reading",
                         "facility_ingestion_interpretation")

# Commits at which the prerequisite lanes were read at authoring (documentation; drift is caught by the sha256 check).
PREREQ_AT_AUTHORING = {
    "feed_envelope": {"lane": "FEED (lane 16)", "branch": "worktree-wf_3da51c0c-3b4-1",
                      "commit": "ab27dcc449690606defa09af59725c0ad2eeaab4", "lane_verified": True},
    "hall_reference": {"lane": "HALLREF (lane 17)", "branch": "worktree-wf_3da51c0c-3b4-2",
                       "commit": "91ebd8a4017eb8609804846603063a25c41405c1", "lane_verified": False},
}

TBD_PREFIX = "TBD — requires "

# bus_power_boundary_v1 component names (abep_sim/arch_boundary.py, other lane); P_source sums the arm-specific ones.
EXPECTED_ARM_COMPONENTS = {"hall_only": [], "rf_hall": ["rf_source"], "ecr_hall": ["ecr_source", "ecr_magnet"]}


class GridError(Exception):
    """Base error of this builder."""


class PrerequisiteMissing(GridError):
    """A prerequisite deliverable (another lane's file) cannot be found."""


class PrerequisiteInvalid(GridError):
    """A prerequisite deliverable does not have the structure or values this builder needs."""


class FreezeRefused(GridError):
    """The grid cannot be frozen: TBD levels or un-decided PROPOSED items remain."""


# ----------------------------------------------------------------------------------------------------------- helpers
def canonical_sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dumps(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def resolve_prerequisite(explicit: str | None, env_var: str, rel: str, what: str) -> Path:
    """Explicit path > environment variable > repository path. No search, no fallback content."""
    for cand, how in ((explicit, "--option"), (os.environ.get(env_var), f"${env_var}"), (str(REPO / rel), "repo")):
        if cand:
            p = Path(cand)
            if p.is_file():
                return p
            if how != "repo":
                raise PrerequisiteMissing(f"{what}: {how} points to {cand!r}, which is not a file")
    raise PrerequisiteMissing(
        f"{what} not found at {rel} (repository path). It is another lane's deliverable; pass its path with the "
        f"command-line option or ${env_var}. The grid is never built from a guessed or default feed/voltage set.")


def _need(d, key, where):
    if not isinstance(d, dict) or key not in d:
        raise PrerequisiteInvalid(f"{where}: missing key {key!r}")
    return d[key]


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ---------------------------------------------------------------------------------------------- input extraction
FEED_A5_FIELDS = ("mdot_total_kgps", "mdot_s_kgps", "p_feed_Pa", "T_gas_K", "w_s", "x_s")
FEED_X2_FIELDS = ("mdot_xe_anode_kgps", "mdot_xe_cathode_kgps", "p_feed_Pa", "T_gas_K", "w_s", "x_s")
FREE_STREAM_CONTEXT = ("x_s", "p_ambient_Pa", "mass_flux_kgpm2ps")


def _quantity(q: dict, pointer: str) -> dict:
    """Copy one feed-envelope quantity (value or per-species values) with its status; never fill a null."""
    if not isinstance(q, dict) or ("value" not in q and "values" not in q):
        raise PrerequisiteInvalid(f"{pointer}: not a quantity object")
    out = {"unit": _need(q, "unit", pointer), "evidence_class": q.get("evidence_class"), "source_pointer": pointer}
    if "values" in q:
        vals = q["values"]
        if not isinstance(vals, dict):
            raise PrerequisiteInvalid(f"{pointer}: 'values' must be a species map")
        out["values"] = {k: vals[k] for k in sorted(vals)}
        missing = any(v is None for v in vals.values())
        bad = [k for k, v in vals.items() if v is not None and not _is_num(v)]
    else:
        out["value"] = q["value"]
        missing = q["value"] is None
        bad = [] if (q["value"] is None or _is_num(q["value"])) else ["value"]
    if bad:
        raise PrerequisiteInvalid(f"{pointer}: non-numeric entries {bad}")
    if missing:
        req = q.get("requires")
        if not isinstance(req, str) or not req.strip():
            raise PrerequisiteInvalid(f"{pointer}: null value without a 'requires' statement")
        out["status"] = "TBD"
        out["requires"] = req
    else:
        if q.get("evidence_class") in (None, "TBD"):
            raise PrerequisiteInvalid(f"{pointer}: numeric value without an evidence class")
        out["status"] = "SOURCED"
    return out


def extract_feed(doc: dict, sha: str) -> dict:
    where = FEED_REL
    archs = _need(_need(doc, "architectures", where), "ids", where)
    if tuple(archs) != ARCHITECTURES:
        raise PrerequisiteInvalid(f"{where}: architectures.ids {archs} != {list(ARCHITECTURES)}")
    if _need(doc["architectures"], "architecture_dependent_fields", where):
        raise PrerequisiteInvalid(f"{where}: the feed envelope declares architecture-dependent fields; the common grid "
                                  "needs one architecture-independent feed record per case")
    levels_map = _need(_need(doc, "atmosphere_levels", where), "mapping", where)
    cases = []
    for i, c in enumerate(_need(doc, "cases", where)):
        cw = f"{where}#/cases/{i}"
        if c.get("architecture_dependent") is not False:
            raise PrerequisiteInvalid(f"{cw}: architecture_dependent must be false")
        fs = _need(c, "feed_state", cw)
        free = _need(c, "free_stream", cw)
        cases.append({
            "case_id": _need(c, "case_id", cw),
            "alt_km": _need(c, "alt_km", cw),
            "atmosphere_level": _need(c, "atmosphere_level", cw),
            "averaging": _need(c, "averaging", cw),
            "feed_envelope_status": _need(c, "status", cw),
            "if_a5": {k: _quantity(_need(fs, k, cw), f"{where}#/cases/{i}/feed_state/{k}") for k in FEED_A5_FIELDS},
            "free_stream_context": {k: _quantity(_need(free, k, cw), f"{where}#/cases/{i}/free_stream/{k}")
                                    for k in FREE_STREAM_CONTEXT},
        })
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids) or not ids:
        raise PrerequisiteInvalid(f"{where}: case ids must be unique and non-empty")
    xe = _need(doc, "xe_path", where)
    if xe.get("architecture_dependent") is not False or xe.get("altitude_dependent") is not False:
        raise PrerequisiteInvalid(f"{where}#/xe_path: must be architecture- and altitude-independent")
    xfs = _need(xe, "feed_state", f"{where}#/xe_path")
    mixed = _need(xe, "mixed_air_xe_feed", f"{where}#/xe_path")
    return {
        "path": FEED_REL,
        "sha256": sha,
        "schema": doc.get("schema"),
        "envelope_version": doc.get("envelope_version"),
        "status": doc.get("status"),
        "interfaces": {"feed_state": doc.get("interface_alignment", {}).get("feed_state"),
                       "xe_feed_state": doc.get("interface_alignment", {}).get("xe_feed_state"),
                       "icd_schema": doc.get("interface_alignment", {}).get("icd_schema")},
        "common_feed_rule": doc["architectures"].get("common_feed_rule"),
        "atmosphere_levels": {"mapping": levels_map,
                              "source": doc["atmosphere_levels"].get("source"),
                              "evidence_class": doc["atmosphere_levels"].get("evidence_class")},
        "cases": cases,
        "xe_path": {
            "interface": xe.get("interface"),
            "status": xe.get("status"),
            "if_x2": {k: _quantity(_need(xfs, k, f"{where}#/xe_path/feed_state"),
                                   f"{where}#/xe_path/feed_state/{k}") for k in FEED_X2_FIELDS},
        },
        "mixed_air_xe_feed": {"status": mixed.get("status"), "requires": mixed.get("requires"),
                              "source_pointer": f"{where}#/xe_path/mixed_air_xe_feed"},
    }


def extract_hall_reference(doc: dict, sha: str) -> dict:
    where = HALLREF_REL
    if tuple(_need(doc, "architectures", where)) != ARCHITECTURES:
        raise PrerequisiteInvalid(f"{where}: architectures != {list(ARCHITECTURES)}")
    dv = _need(doc, "discharge_voltage_interface", where)
    ev = _need(dv, "proposed_evaluation_set_V", f"{where}#/discharge_voltage_interface")
    rg = _need(dv, "proposed_range_V", f"{where}#/discharge_voltage_interface")
    vals = _need(ev, "value", "proposed_evaluation_set_V")
    if (not isinstance(vals, list) or not vals or not all(_is_num(v) for v in vals)
            or sorted(set(vals)) != list(vals)):
        raise PrerequisiteInvalid(f"{where}: proposed_evaluation_set_V.value must be a strictly increasing number list")
    rv = _need(rg, "value", "proposed_range_V")
    if not (isinstance(rv, list) and len(rv) == 2 and all(_is_num(v) for v in rv)):
        raise PrerequisiteInvalid(f"{where}: proposed_range_V.value must be [lo, hi]")
    if vals[0] < rv[0] or vals[-1] > rv[1]:
        raise PrerequisiteInvalid(f"{where}: evaluation set {vals} outside proposed range {rv}")
    if ev.get("status") not in ("PROPOSED", "OWNER_DECIDED", "SOURCED"):
        raise PrerequisiteInvalid(f"{where}: unexpected status {ev.get('status')!r} of proposed_evaluation_set_V")
    req = _need(dv, "requirements", f"{where}#/discharge_voltage_interface")
    pmax = _need(req, "power_max_W", "requirements")
    alts = dv.get("span_rule", {}).get("alternative_spans_on_record", {})
    bpb = _need(doc, "bus_power_boundary", where)
    if bpb.get("boundary_version") != "bus_power_boundary_v1":
        raise PrerequisiteInvalid(f"{where}: bus_power_boundary.boundary_version != 'bus_power_boundary_v1'")
    if bpb.get("arm_specific_components") != EXPECTED_ARM_COMPONENTS:
        raise PrerequisiteInvalid(f"{where}: arm_specific_components {bpb.get('arm_specific_components')} != "
                                  f"{EXPECTED_ARM_COMPONENTS} (the P_source definition sums exactly these)")
    return {
        "path": HALLREF_REL,
        "sha256": sha,
        "schema": doc.get("schema"),
        "version": doc.get("version"),
        "status": doc.get("status"),
        "discharge_voltage": {
            "evaluation_set_V": {"value": list(vals), "unit": ev.get("unit"), "status": ev.get("status"),
                                 "evidence_class": ev.get("evidence_class"), "source_ids": ev.get("source"),
                                 "locator": ev.get("locator"),
                                 "source_pointer": f"{where}#/discharge_voltage_interface/proposed_evaluation_set_V"},
            "range_V": {"value": list(rv), "unit": rg.get("unit"), "status": rg.get("status"),
                        "evidence_class": rg.get("evidence_class"), "source_ids": rg.get("source"),
                        "source_pointer": f"{where}#/discharge_voltage_interface/proposed_range_V"},
            "span_rule_id": dv.get("span_rule", {}).get("id"),
            "alternative_spans_on_record": {k: {"value": v.get("value"), "status": v.get("status"),
                                                "evidence_class": v.get("evidence_class")}
                                            for k, v in sorted(alts.items())},
            "invariance_rule": "INV-V1",
        },
        "power_max_W": {"value": pmax.get("value"), "unit": pmax.get("unit"), "status": pmax.get("status"),
                        "evidence_class": pmax.get("evidence_class"), "source_ids": pmax.get("source"),
                        "locator": pmax.get("locator"),
                        "source_pointer": f"{where}#/discharge_voltage_interface/requirements/power_max_W"},
        "bus_power_boundary": {k: doc.get("bus_power_boundary", {}).get(k) for k in
                               ("module", "boundary_version", "arm_specific_components")},
    }


def extract_nuisance(doc: dict) -> dict:
    nz = _need(doc, "calibration_nuisance", ENSEMBLE_REL)
    if not isinstance(nz, dict) or not nz:
        raise PrerequisiteInvalid(f"{ENSEMBLE_REL}: calibration_nuisance must be a non-empty mapping")
    return {"path": ENSEMBLE_REL, "names": sorted(nz),
            "values": sorted({str(v) for spec in nz.values() for v in spec.get("values", [])})}


def extract_inputs(feed_path: Path, hall_path: Path, ensemble_path: Path | None = None) -> dict:
    ensemble_path = ensemble_path or (REPO / ENSEMBLE_REL)
    if not Path(ensemble_path).is_file():
        raise PrerequisiteMissing(f"{ENSEMBLE_REL} not found (needed for the forbidden-axis list)")
    feed = extract_feed(json.loads(Path(feed_path).read_text()), file_sha256(feed_path))
    hall = extract_hall_reference(json.loads(Path(hall_path).read_text()), file_sha256(hall_path))
    try:                                           # cross-check the RFP ceiling with the repository constant
        sys.path.insert(0, str(REPO))
        from abep_sim.constants import RFP  # noqa: E402  (pure constants module)
    finally:
        sys.path.pop(0)
    if hall["power_max_W"]["value"] != RFP.power_max_W:
        raise PrerequisiteInvalid(f"power ceiling {hall['power_max_W']['value']} W in {HALLREF_REL} != "
                                  f"abep_sim.constants.RFP.power_max_W {RFP.power_max_W}")
    return {"feed_envelope": feed, "hall_reference": hall,
            "calibration_nuisance": extract_nuisance(json.loads(Path(ensemble_path).read_text()))}


# -------------------------------------------------------------------------------------- static grid definitions
FEED_MODES = [
    {
        "id": "xe_start",
        "definition": "Anode fed by the Xe path only (IF-X2 mdot_xe_anode_kgps); atmospheric valve closed; Xe-fed "
                      "cathode. Xe anode mass fraction = 1 by definition of the mode.",
        "feed_levels": "xe_path",
        "xe_anode_mass_fraction": {"value": 1, "unit": "-", "status": "DEFINITION",
                                   "evidence_class": "assumed",
                                   "source": "definition of the mode (single-species Xe anode feed; feed envelope "
                                             "xe_path w_s = {Xe: 1}, evidence class assumed)"},
        "dual_feed_state_reference": ["XE_DISCHARGE_IGNITION", "WARM_UP", "XE_FALLBACK"],
    },
    {
        "id": "mixed",
        "definition": "Anode fed by both paths: the atmospheric feed state of the case (IF-A5) plus a Xe anode flow "
                      "(IF-X2) at a Xe anode mass fraction strictly between 0 and 1 (levels TBD).",
        "feed_levels": "atmospheric_cases_x_xe_mixing_levels",
        "xe_anode_mass_fraction": {"value": None, "unit": "-", "status": "TBD",
                                   "evidence_class": "TBD",
                                   "requires": TBD_PREFIX + "a Xe flow-setpoint policy for the mixed feed (feed "
                                               "envelope xe_path.mixed_air_xe_feed is TBD; ICD G-12)"},
        "dual_feed_state_reference": ["ATMOSPHERE_ADMISSION", "MIXED_STABILIZATION",
                                      "ATMOSPHERE_DOMINANT (non-zero Xe trim)"],
    },
    {
        "id": "atmosphere_dominant",
        "definition": "Anode fed by the atmospheric path only (IF-A5 feed state of the case); Xe to the cathode only. "
                      "The grid node is the zero-Xe-trim limit; a non-zero Xe anode trim is a 'mixed' level.",
        "feed_levels": "atmospheric_cases",
        "xe_anode_mass_fraction": {"value": 0, "unit": "-", "status": "PROPOSED",
                                   "evidence_class": "assumed",
                                   "source": "this grid (lane 23): the atmosphere-dominant node is placed at zero Xe "
                                             "anode trim so that it is not a function of the TBD trim limit",
                                   "rationale": "RFP air + Xe concept (CLAUDE.md 'What this is'); the long-duration "
                                                "mode is the atmospheric anode feed. Placing the node at zero trim "
                                                "keeps it free of the TBD Xe trim limit; trims are covered by the "
                                                "mixed levels. Owner may move the node (open question GQ-3)."},
        "dual_feed_state_reference": ["AIR_ONLY_ANODE_XE_CATHODE", "ATMOSPHERE_DOMINANT (zero Xe trim)"],
    },
]

FEED_MODE_AXIS = {
    "status": "PROPOSED",
    "evidence_class": "assumed",
    "source": "lane-23 task definition (Xe start, mixed, atmosphere-dominant) for the RFP air + Xe dual feed "
              "(CLAUDE.md 'What this is': air + Xe; RFP architecture: atmospheric path and Xe path both feed the "
              "ionization/discharge block); mode names referenced to the dual-feed control-logic draft "
              "schemas/controls/dual_feed_state_machine_v1.json (other lane; uncommitted at authoring; names only, "
              "no value taken)",
    "rationale": "The dual-feed concept needs the Xe-only start and the transition through mixed feed as well as the "
                 "atmospheric operating mode; a pre-ionizer may matter most at start or transition, so all three "
                 "modes are compared on the same footing.",
}

XE_MIX_LEVELS = [
    {"id": "XMIX_TBD", "value": None, "unit": "-", "status": "TBD", "evidence_class": "TBD",
     "requires": TBD_PREFIX + "the owner's Xe anode mass-fraction level set for the mixed mode, which needs a Xe "
                              "flow-setpoint policy (feed envelope xe_path.mixed_air_xe_feed; ICD G-12). One "
                              "placeholder level; the set replaces it before freeze (regeneration changes point ids "
                              "and the grid hash, which is allowed only before freeze).",
     "applies_to_modes": ["mixed"]},
]

P_SOURCE_DEFINITION = {
    "quantity": "P_source",
    "unit": "W",
    "definition": "Sum of the DC-bus input power of the architecture-specific components of bus_power_boundary_v1 "
                  "(rf_hall: rf_source; ecr_hall: ecr_source + ecr_magnet), i.e. the whole bus cost of the "
                  "pre-ionizer at the same boundary point for both source arms.",
    "status": "PROPOSED",
    "evidence_class": "assumed",
    "source": "this grid (lane 23), using the component names of abep_sim/arch_boundary.py (bus_power_boundary_v1; "
              "other lane, referenced by path only) and the DC-input power levels of the XPROT draft "
              "(docs/architecture_comparison/experiment_protocol/EXPERIMENT_PROTOCOL_DRAFT.md section 2)",
    "rationale": "Equal P_source then means equal bus spending on pre-ionization in rf_hall and ecr_hall, so neither "
                 "source arm is favoured by where its magnet power is booked. Alternative on record: generator "
                 "power only (ecr_magnet booked separately) - owner question GQ-4.",
}

P_SOURCE_LEVELS = [
    {"id": "PS0", "value": 0, "unit": "W", "status": "DEFINITION", "evidence_class": "assumed",
     "source": "definition of hall_only (no pre-ionizer components in bus_power_boundary_v1 for hall_only)",
     "architectures": ["hall_only"]},
    {"id": "PS_LO", "value": None, "unit": "W", "status": "TBD", "evidence_class": "TBD",
     "requires": TBD_PREFIX + "the owner's pre-ionizer bus-power allocation within bus_power_boundary_v1 (the same "
                              "value for rf_hall and ecr_hall); constraint 0 < PS_LO < PS_HI",
     "architectures": ["rf_hall", "ecr_hall"]},
    {"id": "PS_HI", "value": None, "unit": "W", "status": "TBD", "evidence_class": "TBD",
     "requires": TBD_PREFIX + "the owner's pre-ionizer bus-power allocation within bus_power_boundary_v1 (the same "
                              "value for rf_hall and ecr_hall); constraint PS_HI < the bus power ceiling",
     "architectures": ["rf_hall", "ecr_hall"]},
]

P_SOURCE_LEVEL_STRUCTURE = {
    "nonzero_levels": 2,
    "status": "PROPOSED",
    "evidence_class": "assumed",
    "source": "XPROT draft parameter preionizer_nonzero_levels_min = 2 (docs/architecture_comparison/"
              "experiment_protocol/protocol_draft.json, PROPOSED, 'needed to see a dose-response rather than a "
              "single point'); other lane, commit 1428265",
    "not_adopted": "The minimum-decisive-experiment draft sets P_lo = max(lowest stable source power at that flow, "
                   "0.5 P_hi) (T-PLO-FRACTION, docs/architecture_comparison/minimum_decisive_experiment/, commit "
                   "e0f6be3). Not adopted for the grid: 'lowest stable source power' differs between the RF and "
                   "ECR sources and between flows, which would give the two source arms different levels. Grid "
                   "levels are fixed numbers, identical in both source arms and at every base point.",
}

RULES = [
    {"id": "GR-1", "rule": "Every architecture is evaluated at every base point. Applicability of a base point is "
                           "decided by its feed mode, feed level and mixing level only, never by an architecture."},
    {"id": "GR-2", "rule": "No per-architecture cherry-picking: a base point is never removed, added or moved for "
                           "one architecture. A point at which an architecture does not sustain, exceeds the bus "
                           "ceiling or is otherwise infeasible is a recorded result (status from the harness or a "
                           "hard gate), not a grid change. Eliminations happen only through explicit hard-gate logic "
                           "(docs/architecture_comparison/hard_gates/, other lane) with the evidence class that "
                           "supports them."},
    {"id": "GR-3", "rule": "P_source: hall_only is evaluated at PS0 = 0 W only; rf_hall and ecr_hall are evaluated "
                           "at the SAME non-zero level set, at every base point. Paired comparisons use the same "
                           "base point (hall_only vs each source arm at each level; rf_hall vs ecr_hall at equal "
                           "level)."},
    {"id": "GR-4", "rule": "The feed state at a base point is the feed-envelope record of its case (IF-A5 / IF-X2), "
                           "identical for the three architectures (feed envelope common_feed_rule). Nothing "
                           "downstream of the valve (pre-ionizer, Hall closure, Hall-map output) feeds back into a "
                           "feed level: Hall-closure uncertainty never leaks upstream."},
    {"id": "GR-5", "rule": "Layer-1 P5 calibration nuisance (registration, coil shape, beam-efficiency reading, "
                           "facility-ingestion interpretation) is never a grid axis or level. Layer-2 transport "
                           "closures are scenarios applied by the harness to every point (admitted members only; "
                           "the set is empty today); they are never axes, and screening candidates never produce "
                           "grid results."},
    {"id": "GR-6", "rule": "A level whose prerequisite value is TBD is TBD (value null, 'requires' stated); every "
                           "base point and evaluation that uses it lists it in tbd_dependencies. No level is filled "
                           "with a default, a code value or a historical value."},
    {"id": "GR-7", "rule": "The discharge-voltage level set is the Hall reference's evaluation set, identical in all "
                           "architectures and all feed modes (Hall reference INV-V1)."},
    {"id": "GR-8", "rule": "After freeze the grid is immutable: any change produces comparison_grid_v2 (new file, "
                           "new hash); results computed on v1 stay tied to the v1 hash."},
]

FREEZE_PROCEDURE = {
    "current_status": STATUS_DRAFT,
    "steps": [
        "1. DRAFT_PENDING_OWNER (this file): structure, rules and level provenance for owner review.",
        "2. Owner resolves every TBD level (value + source + evidence class) and decides every PROPOSED item "
        "(recorded as OWNER_DECIDED with a decision reference); the prerequisites (feed envelope, Hall reference) "
        "are at an owner-approved revision.",
        "3. Regenerate with --write from the approved prerequisites; --freeze-status must list no blockers.",
        "4. Hash-lock: --freeze --owner-decision REF --date YYYY-MM-DD writes comparison_grid_v1.lock.json "
        "(grid content sha256, file sha256, prerequisite sha256s, decision reference). The lock is committed before "
        "any comparison run.",
        "5. Every comparison run (abep_sim/arch_compare.py or a test campaign under the experiment protocol) records "
        "the locked grid content sha256 and refuses a grid whose hash differs from the lock.",
        "6. Any later change is a new version (comparison_grid_v2) with its own freeze; v1 is never edited in place.",
    ],
    "blocker_kinds": ["TBD level", "PROPOSED item without owner decision", "prerequisite not at an approved revision",
                      "prerequisite lane not verified"],
}

MILESTONES = {
    "supports": ["A"],
    "A": {
        "supported": "YES (structure)",
        "contribution": "Fixes ONE point set, identical for hall_only, rf_hall and ecr_hall, with the fairness rules "
                        "GR-1..GR-8, so a conditional selection ('X is baseline provided A/B/C are demonstrated') can "
                        "name the base points at which each condition must be shown. Needs no Hall number and not "
                        "Physics Baseline 1.0.",
        "to_reach_next": [
            "Owner decisions on the PROPOSED items: feed-mode set and node placement (GQ-1..GQ-3), P_source "
            "definition (GQ-4), level-count structure (GQ-5), discharge-voltage evaluation set (Hall reference Q1).",
            "Numeric feed levels: a documented design baseline so the feed envelope evaluates IF-A5 mdot, p, T, "
            "x_s (feed envelope to_reach_B), and the Xe path IF-X2 (Xe flow-setpoint policy, ICD G-12).",
            "Numeric P_source levels (pre-ionizer bus allocation within bus_power_boundary_v1) and the mixed-mode "
            "Xe mass-fraction levels.",
            "Freeze and hash-lock of this grid (freeze_procedure) before any comparison run.",
        ],
    },
    "B": {
        "supported": "NO (prerequisite only)",
        "needs": [
            "A frozen, hash-locked grid with no TBD level.",
            "At least one ADMITTED Hall transport closure (credible set is empty; gate 3 FAIL) and design Hall maps "
            "per member whose axes cover every base point (V_d nodes, feed flow range) without extrapolation.",
            "Chemistry covering the feed of every mode (O/O2 absent; N2/N set abep-n2n-0.11 is scoped to P5-N2 "
            "validation) and a solver path for pre-ionized inflow (Hall reference Q4).",
            "Common-boundary ledgers per point (bus_power_boundary_v1) with sourced efficiencies.",
        ],
    },
    "C": {
        "supported": "NO",
        "needs": [
            "Mission weighting of base points (time fraction per altitude/solar level and per feed mode over the "
            "26,000 h mission; start count for xe_start) - TBD, requires the mission profile.",
            "Orbit-resolved extremes (feed envelope: frozen orbit-resolved dataset) if the owner adds extreme levels.",
            "Mass, thermal, life, cathode and start-up closures evaluated on the same frozen points.",
        ],
    },
}

OPEN_QUESTIONS = [
    "GQ-1 Feed modes: confirm the three modes (xe_start, mixed, atmosphere_dominant). Is an explicit air-only anode "
    "level distinct from atmosphere_dominant wanted?",
    "GQ-2 xe_start uses the Xe path only, so it has one feed level (IF-X2 is altitude-independent in the feed "
    "envelope). Should start points also be repeated per altitude/solar level (e.g. for background-dependent "
    "effects)? That would apply to all three architectures.",
    "GQ-3 atmosphere_dominant node at zero Xe anode trim (PROPOSED); or at a non-zero trim limit "
    "(mdot_Xe_anode_trim_max, TBD in the dual-feed draft)?",
    "GQ-4 P_source definition: whole arm-specific bus power (PROPOSED: rf_source; ecr_source + ecr_magnet) or "
    "generator power only?",
    "GQ-5 P_source level count: two non-zero levels (XPROT minimum, PROPOSED) or more; and the values (TBD). Should "
    "an 'installed, unpowered' control level for the source arms (XPROT SHAM controls; Hall reference Q2) be a grid "
    "level or stay in the experiment protocol only?",
    "GQ-6 Discharge voltage: the grid inherits the Hall reference evaluation set (180, 200, 250, 300, 305 V; "
    "PROPOSED there, Q1 there); the same set is applied in xe_start. Confirm, or set a separate Xe-start voltage "
    "set that is still common to all three architectures.",
    "GQ-7 Should the RFP 1.5 kW ceiling apply at the bus_power_boundary_v1 boundary (bus boundary lane open "
    "question 1)? The P_source levels are bounded by it only if so.",
]


# -------------------------------------------------------------------------------------------------- the builder
def _feed_levels(inputs: dict) -> list:
    feed = inputs["feed_envelope"]
    levels = []
    for c in feed["cases"]:
        tbd = sorted(k for k, q in c["if_a5"].items() if q["status"] == "TBD")
        levels.append({
            "id": c["case_id"],
            "path": "atmospheric",
            "alt_km": c["alt_km"],
            "atmosphere_level": c["atmosphere_level"],
            "averaging": c["averaging"],
            "interface": feed["interfaces"]["feed_state"],
            "feed_state": c["if_a5"],
            "free_stream_context": {
                "note": "IF-A0 free-stream values of the same case, carried for orientation only; they are NOT the "
                        "feed composition or flow at the valve outlet (intake, reservoir and valve change them).",
                "interface": "IF-A0",
                "quantities": c["free_stream_context"],
            },
            "status": "TBD" if tbd else "SOURCED",
            "tbd_fields": tbd,
            "applies_to_modes": ["mixed", "atmosphere_dominant"],
            "source_pointer": f"{feed['path']}#/cases/case_id={c['case_id']}",
        })
    x2 = feed["xe_path"]["if_x2"]
    tbd = sorted(k for k, q in x2.items() if q["status"] == "TBD")
    levels.append({
        "id": "xe_path",
        "path": "xenon",
        "alt_km": None,
        "atmosphere_level": None,
        "averaging": None,
        "interface": feed["interfaces"]["xe_feed_state"],
        "feed_state": x2,
        "free_stream_context": None,
        "status": "TBD" if tbd else "SOURCED",
        "tbd_fields": tbd,
        "applies_to_modes": ["xe_start"],
        "source_pointer": f"{feed['path']}#/xe_path",
    })
    return levels


def _vd_levels(inputs: dict) -> list:
    ev = inputs["hall_reference"]["discharge_voltage"]["evaluation_set_V"]
    out = []
    for v in ev["value"]:
        out.append({"id": f"V{v:g}".replace(".", "p"), "value": v, "unit": ev["unit"], "status": ev["status"],
                    "evidence_class": ev["evidence_class"], "source_ids": ev["source_ids"],
                    "source_pointer": ev["source_pointer"], "applies_to_modes": [m["id"] for m in FEED_MODES]})
    return out


def _axes(inputs: dict) -> dict:
    hall = inputs["hall_reference"]
    pmax = hall["power_max_W"]
    return {
        "feed_mode": dict(FEED_MODE_AXIS, levels=copy.deepcopy(FEED_MODES)),
        "feed_state": {
            "status": "SOURCED_STRUCTURE_TBD_VALUES",
            "source": f"{inputs['feed_envelope']['path']} (sha256 {inputs['feed_envelope']['sha256']})",
            "definition": "One level per feed-envelope case (altitude x atmosphere level, orbit-averaged) for the "
                          "atmospheric path (IF-A5 at the valve outlet), plus one level for the Xe path (IF-X2). The "
                          "flow, pressure, temperature and composition of each level are the feed envelope's values, "
                          "copied with their status; a TBD there is TBD here.",
            "atmosphere_levels": inputs["feed_envelope"]["atmosphere_levels"],
            "common_feed_rule": inputs["feed_envelope"]["common_feed_rule"],
            "not_an_axis": "Feed pressure is not set independently: it follows the flow and the hardware "
                           "conductance of the case (the feed envelope's single state per case). An independent "
                           "throttle axis is not included; if the owner adds one, it applies to all architectures.",
            "levels": _feed_levels(inputs),
        },
        "xe_anode_mass_fraction": {
            "status": "TBD",
            "definition": "Xe share of the anode mass flow in the mixed mode (applies to mixed only; xe_start = 1 "
                          "and atmosphere_dominant = 0 by the mode definitions).",
            "source": inputs["feed_envelope"]["mixed_air_xe_feed"]["source_pointer"],
            "levels": copy.deepcopy(XE_MIX_LEVELS),
        },
        "discharge_voltage_V": {
            "status": hall["discharge_voltage"]["evaluation_set_V"]["status"],
            "source": f"{hall['path']} (sha256 {hall['sha256']}) proposed_evaluation_set_V; span rule "
                      f"{hall['discharge_voltage']['span_rule_id']}; invariance rule "
                      f"{hall['discharge_voltage']['invariance_rule']}",
            "range_V": hall["discharge_voltage"]["range_V"],
            "alternative_spans_on_record": hall["discharge_voltage"]["alternative_spans_on_record"],
            "note": "PROPOSED by the Hall reference (not in the RFP); the owner decides there (Hall reference Q1). "
                    "The grid only enumerates the set; it does not choose a voltage.",
            "levels": _vd_levels(inputs),
        },
        "p_source_W": {
            "definition": P_SOURCE_DEFINITION,
            "level_structure": P_SOURCE_LEVEL_STRUCTURE,
            "bound": {
                "rule": "0 < PS_LO < PS_HI < P_bus_max. At a given point the admissible headroom is P_bus_max minus "
                        "the common loads of that point (TBD until the ledger and an admitted Hall closure exist); a "
                        "level above the headroom makes that evaluation a recorded INFEASIBLE result through a hard "
                        "gate (GR-2), it never removes the point.",
                "P_bus_max_W": pmax,
                "applies_if": "the RFP ceiling is taken at the bus_power_boundary_v1 boundary (GQ-7)",
            },
            "boundary": hall["bus_power_boundary"],
            "levels": copy.deepcopy(P_SOURCE_LEVELS),
        },
    }


def _p_levels_for(arch: str) -> list:
    return [lv for lv in P_SOURCE_LEVELS if arch in lv["architectures"]]


def _base_points(axes: dict) -> list:
    feed = {lv["id"]: lv for lv in axes["feed_state"]["levels"]}
    vds = axes["discharge_voltage_V"]["levels"]
    mixes = axes["xe_anode_mass_fraction"]["levels"]
    pts = []
    for mode in axes["feed_mode"]["levels"]:
        m = mode["id"]
        combos = []
        for fid, fl in feed.items():
            if m not in fl["applies_to_modes"]:
                continue
            if m == "mixed":
                combos += [(fid, mx["id"]) for mx in mixes if m in mx["applies_to_modes"]]
            else:
                combos.append((fid, None))
        for fid, mid in combos:
            for vd in vds:
                if m not in vd["applies_to_modes"]:
                    continue
                parts = [m, fid] + ([mid] if mid else []) + [vd["id"]]
                deps = []
                if mode["xe_anode_mass_fraction"]["status"] == "TBD" and not mid:
                    deps.append(f"feed_mode:{m}.xe_anode_mass_fraction")
                if feed[fid]["status"] == "TBD":
                    deps += [f"feed_state:{fid}.{k}" for k in feed[fid]["tbd_fields"]]
                if mid:
                    mx = next(x for x in mixes if x["id"] == mid)
                    if mx["status"] == "TBD":
                        deps.append(f"xe_anode_mass_fraction:{mid}")
                if m == "mixed":             # a mixed point uses both paths
                    xe = feed["xe_path"]
                    deps += [f"feed_state:xe_path.{k}" for k in xe["tbd_fields"]]
                if vd["status"] == "TBD":
                    deps.append(f"discharge_voltage_V:{vd['id']}")
                pts.append({
                    "base_point_id": "/".join(parts),
                    "feed_mode": m,
                    "feed_level_id": fid,
                    "xe_mix_level_id": mid,
                    "vd_level_id": vd["id"],
                    "V_d_V": vd["value"],
                    "architectures": list(ARCHITECTURES),
                    "tbd_dependencies": sorted(set(deps)),
                    "status": "PENDING_TBD_LEVELS" if deps else "DEFINED",
                })
    return pts


def _evaluations(base_points: list) -> list:
    out = []
    for bp in base_points:
        for arch in ARCHITECTURES:
            for lv in _p_levels_for(arch):
                extra = [f"p_source_W:{lv['id']}"] if lv["status"] == "TBD" else []
                out.append({
                    "evaluation_id": f"{bp['base_point_id']}/{arch}/{lv['id']}",
                    "base_point_id": bp["base_point_id"],
                    "architecture": arch,
                    "p_source_level_id": lv["id"],
                    "tbd_dependencies_beyond_base_point": extra,
                    "status": "PENDING_TBD_LEVELS" if (extra or bp["tbd_dependencies"]) else "DEFINED",
                })
    return out


def _forbidden_axes(inputs: dict) -> list:
    return sorted(set(ALWAYS_FORBIDDEN_AXES) | set(inputs["calibration_nuisance"]["names"]))


def grid_content(doc: dict) -> dict:
    """The part of the document the grid hash covers."""
    return {"axes": doc["axes"], "base_points": doc["base_points"], "evaluations": doc["evaluations"],
            "rules": doc["rules"]}


def freeze_blockers(doc: dict) -> list:
    """Everything that prevents a freeze. Empty list == ready for the owner's hash-lock."""
    b = []
    ax = doc["axes"]
    for m in ax["feed_mode"]["levels"]:
        if m["xe_anode_mass_fraction"]["status"] in ("TBD", "PROPOSED"):
            b.append(f"feed_mode {m['id']}: xe_anode_mass_fraction is {m['xe_anode_mass_fraction']['status']}")
    if ax["feed_mode"]["status"] == "PROPOSED":
        b.append("feed_mode axis is PROPOSED (owner decision needed)")
    for lv in ax["feed_state"]["levels"]:
        if lv["status"] == "TBD":
            b.append(f"feed_state {lv['id']}: TBD fields {lv['tbd_fields']}")
    for lv in ax["xe_anode_mass_fraction"]["levels"]:
        if lv["status"] in ("TBD", "PROPOSED"):
            b.append(f"xe_anode_mass_fraction {lv['id']}: {lv['status']}")
    for lv in ax["discharge_voltage_V"]["levels"]:
        if lv["status"] in ("TBD", "PROPOSED"):
            b.append(f"discharge_voltage_V {lv['id']}: {lv['status']}")
    for key in ("definition", "level_structure"):
        if ax["p_source_W"][key]["status"] == "PROPOSED":
            b.append(f"p_source_W {key}: PROPOSED")
    for lv in ax["p_source_W"]["levels"]:
        if lv["status"] in ("TBD", "PROPOSED"):
            b.append(f"p_source_W {lv['id']}: {lv['status']}")
    for name in ("feed_envelope", "hall_reference"):
        pre = doc["prerequisites"][name]
        if not pre.get("lane_verified_at_authoring", False):
            b.append(f"prerequisite {name}: lane not verified at authoring (re-verify before freeze)")
        if "DRAFT" in str(pre.get("status", "")).upper():
            b.append(f"prerequisite {name}: status {pre.get('status')!r} (needs an owner-approved revision)")
    return b


def build_document(inputs: dict) -> dict:
    """Pure function of the extracted inputs (no file access, no clock, no randomness)."""
    inputs = copy.deepcopy(inputs)
    axes = _axes(inputs)
    base = _base_points(axes)
    evals = _evaluations(base)
    per_arch = {a: sorted({e["base_point_id"] for e in evals if e["architecture"] == a}) for a in ARCHITECTURES}
    doc = {
        "schema": SCHEMA_REL,
        "grid_id": GRID_ID,
        "version": GRID_VERSION,
        "status": STATUS_DRAFT,
        "what_it_is": "The single operating-envelope point set on which hall_only, rf_hall and ecr_hall are compared: "
                      "base points (feed mode x feed state x [Xe mixing level] x discharge voltage), each evaluated "
                      "for every architecture, with the pre-ionizer power levels identical for rf_hall and ecr_hall "
                      "and 0 W for hall_only.",
        "what_it_is_not": "Not a result, a ranking, a design point or a Hall prediction. No level is chosen by "
                          "performance. Not wired into archengine; no Hall closure, screening candidate or Hall-map "
                          "output is read.",
        "generated_by": {"script": SCRIPT_REL, "deterministic": True,
                         "command": f"python {SCRIPT_REL} --feed-envelope <{FEED_REL}> --hall-reference "
                                    f"<{HALLREF_REL}> --write"},
        "architectures": list(ARCHITECTURES),
        "milestones": copy.deepcopy(MILESTONES),
        "prerequisites": {
            "feed_envelope": {"path": inputs["feed_envelope"]["path"], "sha256": inputs["feed_envelope"]["sha256"],
                              "schema": inputs["feed_envelope"]["schema"],
                              "version": inputs["feed_envelope"]["envelope_version"],
                              "status": inputs["feed_envelope"]["status"],
                              "lane": PREREQ_AT_AUTHORING["feed_envelope"]["lane"],
                              "commit_at_authoring": PREREQ_AT_AUTHORING["feed_envelope"]["commit"],
                              "lane_verified_at_authoring": PREREQ_AT_AUTHORING["feed_envelope"]["lane_verified"]},
            "hall_reference": {"path": inputs["hall_reference"]["path"], "sha256": inputs["hall_reference"]["sha256"],
                               "schema": inputs["hall_reference"]["schema"],
                               "version": inputs["hall_reference"]["version"],
                               "status": inputs["hall_reference"]["status"],
                               "lane": PREREQ_AT_AUTHORING["hall_reference"]["lane"],
                               "commit_at_authoring": PREREQ_AT_AUTHORING["hall_reference"]["commit"],
                               "lane_verified_at_authoring": PREREQ_AT_AUTHORING["hall_reference"]["lane_verified"]},
            "calibration_nuisance": {"path": inputs["calibration_nuisance"]["path"],
                                     "used_for": "forbidden-axis list only"},
            "referenced_not_read": {
                "bus_power_boundary": "abep_sim/arch_boundary.py (bus_power_boundary_v1)",
                "comparison_harness": "abep_sim/arch_compare.py",
                "hard_gates": "docs/architecture_comparison/hard_gates/",
                "experiment_protocol": "docs/architecture_comparison/experiment_protocol/",
                "minimum_decisive_experiment": "docs/architecture_comparison/minimum_decisive_experiment/",
                "dual_feed_state_machine": "schemas/controls/dual_feed_state_machine_v1.json",
                "upstream_icd": "schemas/interfaces/upstream_icd_v1.json",
            },
        },
        "inputs": inputs,
        "axes": axes,
        "forbidden_axes": {
            "names": _forbidden_axes(inputs),
            "calibration_nuisance_values": inputs["calibration_nuisance"]["values"],
            "rule": "GR-5",
        },
        "rules": copy.deepcopy(RULES),
        "base_points": base,
        "evaluations": evals,
        "summary": {
            "n_base_points": len(base),
            "n_base_points_by_mode": {m["id"]: sum(1 for p in base if p["feed_mode"] == m["id"])
                                      for m in FEED_MODES},
            "n_evaluations": len(evals),
            "n_evaluations_by_architecture": {a: sum(1 for e in evals if e["architecture"] == a)
                                              for a in ARCHITECTURES},
            "p_source_levels_by_architecture": {a: [lv["id"] for lv in _p_levels_for(a)] for a in ARCHITECTURES},
            "identical_base_point_sets": len({tuple(v) for v in per_arch.values()}) == 1,
            "n_base_points_pending_tbd": sum(1 for p in base if p["status"] != "DEFINED"),
            "n_evaluations_pending_tbd": sum(1 for e in evals if e["status"] != "DEFINED"),
        },
        "freeze_procedure": copy.deepcopy(FREEZE_PROCEDURE),
        "open_questions_for_owner": list(OPEN_QUESTIONS),
    }
    doc["freeze_procedure"]["blockers"] = freeze_blockers(doc)
    doc["hashes"] = {
        "algorithm": "sha256 over canonical JSON (sort_keys, separators (',', ':'), UTF-8)",
        "grid_content_sha256": canonical_sha256(grid_content(doc)),
        "grid_content_covers": ["axes", "base_points", "evaluations", "rules"],
        "inputs_sha256": canonical_sha256(inputs),
    }
    return doc


# ---------------------------------------------------------------------------------------- mini schema validator
SUPPORTED_SCHEMA_KEYWORDS = {"type", "required", "properties", "additionalProperties", "items", "enum", "const",
                             "minItems", "maxItems", "uniqueItems", "pattern", "minimum", "maximum", "minLength",
                             "$ref", "anyOf"}
ANNOTATION_KEYWORDS = {"$schema", "$id", "title", "description", "$defs", "$comment"}


def schema_keywords(schema) -> set:
    out = set()
    if isinstance(schema, dict):
        for k, v in schema.items():
            out.add(k)
            if k in ("properties", "$defs"):
                for sub in v.values():
                    out |= schema_keywords(sub)
            elif k in ("items", "additionalProperties") and isinstance(v, dict):
                out |= schema_keywords(v)
            elif k == "anyOf":
                for sub in v:
                    out |= schema_keywords(sub)
    return out


_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _type_ok(x, t) -> bool:
    if t == "number":
        return _is_num(x)
    if t == "integer":
        return _is_num(x) and float(x).is_integer()
    return isinstance(x, _TYPES[t])


def validate(doc, schema, root=None, path="$") -> list:
    """Validate ``doc`` against the JSON-Schema subset in SUPPORTED_SCHEMA_KEYWORDS. Returns error strings."""
    root = root if root is not None else schema
    errs = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            return [f"{path}: unsupported $ref {ref}"]
        return validate(doc, root["$defs"][ref[len("#/$defs/"):]], root, path)
    if "anyOf" in schema:
        if not any(not validate(doc, s, root, path) for s in schema["anyOf"]):
            errs.append(f"{path}: matches no anyOf branch")
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(doc, t) for t in ts):
            return errs + [f"{path}: type {type(doc).__name__} not in {ts}"]
    if "const" in schema and doc != schema["const"]:
        errs.append(f"{path}: {doc!r} != const {schema['const']!r}")
    if "enum" in schema and doc not in schema["enum"]:
        errs.append(f"{path}: {doc!r} not in {schema['enum']}")
    if isinstance(doc, str):
        if "pattern" in schema and not re.search(schema["pattern"], doc):
            errs.append(f"{path}: {doc!r} does not match {schema['pattern']}")
        if "minLength" in schema and len(doc) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
    if _is_num(doc):
        if "minimum" in schema and doc < schema["minimum"]:
            errs.append(f"{path}: {doc} < minimum {schema['minimum']}")
        if "maximum" in schema and doc > schema["maximum"]:
            errs.append(f"{path}: {doc} > maximum {schema['maximum']}")
    if isinstance(doc, list):
        if "minItems" in schema and len(doc) < schema["minItems"]:
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(doc) > schema["maxItems"]:
            errs.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(x, sort_keys=True) for x in doc]
            if len(set(seen)) != len(seen):
                errs.append(f"{path}: items not unique")
        if isinstance(schema.get("items"), dict):
            for i, x in enumerate(doc):
                errs += validate(x, schema["items"], root, f"{path}[{i}]")
    if isinstance(doc, dict):
        for k in schema.get("required", []):
            if k not in doc:
                errs.append(f"{path}: missing required {k!r}")
        props = schema.get("properties", {})
        for k, v in doc.items():
            if k in props:
                errs += validate(v, props[k], root, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected property {k!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errs += validate(v, schema["additionalProperties"], root, f"{path}.{k}")
    return errs


# ------------------------------------------------------------------------------------------------------ freeze
def make_lock(doc: dict, grid_file_sha256: str, owner_decision: str, date: str) -> dict:
    blockers = freeze_blockers(doc)
    if blockers:
        raise FreezeRefused("grid cannot be frozen; blockers:\n  - " + "\n  - ".join(blockers))
    if not owner_decision or not owner_decision.strip():
        raise FreezeRefused("an owner decision reference is required to freeze")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
        raise FreezeRefused("date must be YYYY-MM-DD")
    return {"grid_id": doc["grid_id"], "grid_file": GRID_REL, "grid_file_sha256": grid_file_sha256,
            "grid_content_sha256": doc["hashes"]["grid_content_sha256"],
            "inputs_sha256": doc["hashes"]["inputs_sha256"],
            "prerequisites": {k: {"path": v["path"], "sha256": v["sha256"]}
                              for k, v in doc["prerequisites"].items() if "sha256" in v},
            "owner_decision": owner_decision, "date": date, "status": STATUS_FROZEN}


# -------------------------------------------------------------------------------------------------------- CLI
def _load_committed() -> dict:
    p = REPO / GRID_REL
    if not p.is_file():
        raise GridError(f"{GRID_REL} does not exist; build it with --write")
    return json.loads(p.read_text())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed-envelope", help=f"path to {FEED_REL} (else ${ENV_FEED}, else the repository path)")
    ap.add_argument("--hall-reference", help=f"path to {HALLREF_REL} (else ${ENV_HALLREF}, else the repository path)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="extract inputs from the prerequisites and write the grid")
    g.add_argument("--check", action="store_true", help="re-extract inputs and compare with the committed grid")
    g.add_argument("--check-offline", action="store_true",
                   help="rebuild from the committed grid's own inputs block (no prerequisites needed)")
    g.add_argument("--freeze-status", action="store_true", help="list the freeze blockers of the committed grid")
    g.add_argument("--freeze", action="store_true", help="hash-lock the committed grid (refused while blockers exist)")
    ap.add_argument("--owner-decision", help="owner decision reference (with --freeze)")
    ap.add_argument("--date", help="freeze date YYYY-MM-DD (with --freeze)")
    a = ap.parse_args(argv)
    try:
        if a.check_offline:
            committed = _load_committed()
            rebuilt = build_document(committed["inputs"])
            ok = dumps(rebuilt) == (REPO / GRID_REL).read_text()
            print("OK: offline rebuild reproduces the committed grid" if ok else "MISMATCH: offline rebuild differs")
            return 0 if ok else 1
        if a.freeze_status:
            b = freeze_blockers(_load_committed())
            print(f"{len(b)} blocker(s)")
            for x in b:
                print("  -", x)
            return 0
        if a.freeze:
            committed = _load_committed()
            lock = make_lock(committed, file_sha256(REPO / GRID_REL), a.owner_decision, a.date)
            lp = REPO / LOCK_REL
            if lp.exists():
                raise FreezeRefused(f"{LOCK_REL} already exists; a frozen grid is never re-locked (make v2)")
            lp.write_text(dumps(lock))
            print(f"wrote {LOCK_REL}")
            return 0
        feed = resolve_prerequisite(a.feed_envelope, ENV_FEED, FEED_REL, "feed envelope")
        hall = resolve_prerequisite(a.hall_reference, ENV_HALLREF, HALLREF_REL, "Hall accelerator reference")
        doc = build_document(extract_inputs(feed, hall))
        text = dumps(doc)
        if a.write:
            out = REPO / GRID_REL
            if (REPO / LOCK_REL).exists():
                raise FreezeRefused(f"{LOCK_REL} exists: v1 is frozen and never rewritten (make v2)")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text)
            print(f"wrote {GRID_REL}: {doc['summary']['n_base_points']} base points, "
                  f"{doc['summary']['n_evaluations']} evaluations, grid sha256 "
                  f"{doc['hashes']['grid_content_sha256']}")
            return 0
        ok = text == (REPO / GRID_REL).read_text()
        print("OK: prerequisites reproduce the committed grid" if ok else
              "MISMATCH: prerequisites changed or the builder changed; regenerate (before freeze only)")
        return 0 if ok else 1
    except GridError as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
