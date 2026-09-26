#!/usr/bin/env python3
"""build_hall_sustainment_envelope.py - published Hall-only sustainment / ignition evidence mapped onto the common feed
envelope for hall_only (hall_sustainment_envelope_v1).

Registered follow-on ``fo_hall_sustainment_envelope`` (trigger T_HALL_SUSTAIN_ENVELOPE; prerequisites
lane_09_hall_sustainment and lane_16_feed_envelope). For every feed-envelope case (altitude x atmosphere level, plus the
listed feed variants) it states, per published evidence item and per axis (flow, flow per channel cross-section,
composition, voltage, B, cathode gas, power), whether the item's demonstrated operating region covers, partially covers
or does not reach the case, or is not comparable (with the missing quantity named), and gives each case a status
SUSTAINMENT_SUPPORTED / SUSTAINMENT_CONTRADICTED / UNDETERMINED (with blockers). Ignition is assessed separately for a
xenon-assisted start and for air-only ignition.

Conditional statements only: no prediction, no ranking, no architecture is chosen or set aside (setting an architecture
aside is done only by the hard gates of lane_24). Simulation results, the P5-N2 v1 campaign included, are not
sustainment evidence and are not used. No Hall transport closure is used. Nothing is wired into archengine; no golden
moves.

Outputs (this directory):
  hall_sustainment_envelope_v1.json   the overlay (authoritative for every number)
  HALL_SUSTAINMENT_ENVELOPE.md        generated from the JSON by this script (do not edit by hand)

Usage:
  python docs/architecture_comparison/overlays/hall_sustainment/build_hall_sustainment_envelope.py
  python docs/architecture_comparison/overlays/hall_sustainment/build_hall_sustainment_envelope.py --check
  ... --input-root DIR [--input-root DIR ...]      extra roots searched for the pinned inputs
  ... --feed-envelope FILE --design-point FILE --out-dir DIR
        evaluate a design-evaluated feed envelope and/or an explicit Vyovrinda design point. Writes only to --out-dir
        (never to the committed files). Every design-point entry needs value + source + evidence_class, or an explicit
        {"status": "TBD", "requires": ...}; a missing entry raises MissingDesignInput (no hidden defaults).

Inputs are read READ-ONLY and are pinned by sha256 (INPUTS below). Each is looked up by its repository-relative path,
first in this checkout, then under every --input-root (and ABEP_OVERLAY_INPUT_ROOTS), then in the sibling git worktrees
of this checkout; only a file whose sha256 matches the pin is accepted, so the result does not depend on where an input
was found. A missing input raises OverlayInputError listing the places searched (no silent fallback, CLAUDE.md rule 3).
Nothing is read at import time. To move to a newer input, change its pin here deliberately and regenerate.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT_JSON_NAME = "hall_sustainment_envelope_v1.json"
OUT_MD_NAME = "HALL_SUSTAINMENT_ENVELOPE.md"
SCRIPT_REL = "docs/architecture_comparison/overlays/hall_sustainment/build_hall_sustainment_envelope.py"
TEST_REL = "tests/test_overlay_hall_sustainment.py"

OVERLAY_ID = "hall_sustainment_envelope_v1"
OVERLAY_VERSION = "1.0.0"
ARCH = "hall_only"
ARCH_IDS = ["hall_only", "rf_hall", "ecr_hall"]
PREPARED = "2026-09-26"

# ---------------------------------------------------------------------------------------------------- pinned inputs
INPUTS = {
    "hall_sustainment_matrix": {
        "path": "docs/evidence/hall_sustainment/hall_sustainment_matrix.json",
        "sha256": "248aef28cfe6ffff90d9ee6d43c388488140547e1ce5659975ce30ca77f415b4",
        "lane": "lane_09_hall_sustainment", "branch": "worktree-wf_2bcadd98-5ff-3", "commit": "ac7970917f",
        "role": "published Hall-only sustainment / ignition evidence (entries E01-E21), read only"},
    "feed_envelope": {
        "path": "docs/architecture_comparison/feed_envelope/feed_envelope_v1.json",
        "sha256": "ada3ee720b1b8d60526d3b092492589f62a4144112845b4d813dbc8dc7d5ca02",
        "lane": "lane_16_feed_envelope", "branch": "worktree-wf_3da51c0c-3b4-1", "commit": "ab27dcc449",
        "role": "common feed envelope: cases, free stream (IF-A0), valve-outlet feed state (IF-A5), Xe path (IF-X2), "
                "mixed air + Xe feed; read only"},
    "p5_case_geometry": {
        "path": "hallthruster_bridge/cases/p5_xenon.json",
        "sha256": "1071684dca85a60cdd097c7efaccdf3f6ac29014b796b1aa4ce54e49b0e89f85",
        "lane": "base checkout (read only)", "branch": "claude/nifty-ramanujan-w68f9z", "commit": "fe1d79390f",
        "role": "P5 channel radii r_in / r_out and the published source cited for them (P5 channel cross-section only)"},
    "constants_module": {
        "path": "abep_sim/constants.py",
        "sha256": "dd1c564324c139471bb361d27ef0f75b0f84de1878d100d4313aed12677f33d7",
        "lane": "base checkout (read only)", "branch": "claude/nifty-ramanujan-w68f9z", "commit": "fe1d79390f",
        "role": "M_SPECIES (mass-fraction arithmetic on the feed envelope's own basis) and RFPConstraints"},
}
CLAUDE_MD_PROPELLANT_TOKEN = "air + Xe"          # RFP propellant set as recorded in CLAUDE.md (checked, not pinned)
P5_GEOMETRY_SOURCE_TOKEN = "Channel radii: OD 173 mm, width 25 mm (Hofer 2004 Sec. 5.3.1"

# ---------------------------------------------------------------------------------------------------- vocabulary
COVERS, PARTIAL, DNR, NC, UND = "COVERS", "PARTIALLY_COVERS", "DOES_NOT_REACH", "NOT_COMPARABLE", "UNDETERMINED"
S_SUP, S_CON, S_UND = "SUSTAINMENT_SUPPORTED", "SUSTAINMENT_CONTRADICTED", "UNDETERMINED"
I_SUP, I_CON = "IGNITION_SUPPORTED", "IGNITION_CONTRADICTED"
CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
REQUIRED_AXES = ("anode_flow_density", "composition", "discharge_voltage", "magnetic_field", "cathode_gas")
INFO_AXES = ("anode_flow", "discharge_power")
EPS = 1e-9          # numerical-noise tolerance only (not a physical comparability tolerance)
B_DEFINITIONS = {
    "Br_exit_centreline": "radial B on the channel centreline at the exit plane (P5: 'peak radial B at channel centre, "
                          "exit plane'; Z-70: 'radial B at channel centreline, exit plane')",
}
CATHODE_GASES = ("Xe", "N2", "air", "Ar")
# Relation of a cathode gas to the RFP propellant set 'air + Xe' (CLAUDE.md). N2 is a constituent of air, not itself a
# listed RFP propellant: a pure-N2 cathode feed is conditional on a separate N2 supply or on separating N2 from the air
# path (neither is assessed here).
RFP_GAS_RELATION = {"Xe": "LISTED", "air": "LISTED", "N2": "AIR_CONSTITUENT_CONDITIONAL", "Ar": "NOT_LISTED"}
RFP_GAS_RELATION_TEXT = {
    "LISTED": "a listed RFP propellant (air + Xe)",
    "AIR_CONSTITUENT_CONDITIONAL": "a constituent of air, not itself a listed RFP propellant (air + Xe): usable only "
                                   "with a separate N2 supply or separation of N2 from the air path (conditional; not "
                                   "assessed here)",
    "NOT_LISTED": "outside the RFP propellant set air + Xe",
}
DESIGN_KEYS = ("channel_area_m2", "discharge_voltage_V", "magnetic_field", "cathode_gas", "discharge_power_W")
DESIGN_TBD = {
    "channel_area_m2": "TBD - requires the Vyovrinda Hall channel geometry (inner/outer channel diameter); the "
                       "repository documents no Vyovrinda thruster design",
    "discharge_voltage_V": "TBD - requires the Vyovrinda Hall operating point (discharge voltage)",
    "magnetic_field": "TBD - requires the Vyovrinda magnetic-circuit design (value and its definition)",
    "cathode_gas": "TBD - requires the cathode design and its gas (docs/evidence/cathode/, other lane)",
    "discharge_power_W": "TBD - requires the discharge-power allocation on bus_power_boundary_v1 "
                         "(abep_sim/arch_boundary.py, other lane)",
}


class OverlayInputError(RuntimeError):
    """A pinned input is missing, differs from its pin, or lacks an expected field (no silent fallback)."""


class InvalidDesignPoint(ValueError):
    """A design-point entry is malformed (no source / evidence class, unknown key, bad value)."""


class MissingDesignInput(ValueError):
    """A design-point key is absent: every key must be given, as a value or as an explicit TBD."""


# ---------------------------------------------------------------------------------------------------- input resolution
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def candidate_roots(extra_roots):
    roots = [ROOT] + [os.path.abspath(r) for r in extra_roots]
    env = os.environ.get("ABEP_OVERLAY_INPUT_ROOTS", "")
    roots += [os.path.abspath(r) for r in env.split(os.pathsep) if r.strip()]
    parent = os.path.dirname(ROOT)
    if os.path.basename(parent) == "worktrees":           # ROOT is a git worktree: search its siblings, then main
        roots += sorted(p for p in glob.glob(os.path.join(parent, "*")) if os.path.isdir(p))
        roots.append(os.path.dirname(os.path.dirname(parent)))
    out, seen = [], set()
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def resolve_inputs(extra_roots=(), skip=()):
    found, report = {}, {}
    roots = candidate_roots(extra_roots)
    for key, pin in INPUTS.items():
        if key in skip:
            continue
        tried = []
        for r in roots:
            p = os.path.join(r, pin["path"])
            if os.path.isfile(p):
                h = sha256_file(p)
                tried.append(f"{p} (sha256 {h[:12]}...)")
                if h == pin["sha256"]:
                    found[key] = p
                    break
        if key not in found:
            report[key] = tried
    if report:
        lines = [f"  {k}: {INPUTS[k]['path']} pinned sha256 {INPUTS[k]['sha256'][:12]}... from {INPUTS[k]['lane']} "
                 f"(commit {INPUTS[k]['commit']}); candidates: {v or 'none found'}" for k, v in report.items()]
        raise OverlayInputError("pinned overlay inputs not found (pass --input-root DIR, set ABEP_OVERLAY_INPUT_ROOTS, "
                                "or merge the input lanes):\n" + "\n".join(lines))
    return found


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_constants(path):
    spec = importlib.util.spec_from_file_location("_abep_overlay_hs_constants", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_claude_md():
    p = os.path.join(ROOT, "CLAUDE.md")
    if not os.path.isfile(p):
        raise OverlayInputError(f"{p} not found (RFP propellant set 'air + Xe' is read from it)")
    with open(p, encoding="utf-8") as f:
        if CLAUDE_MD_PROPELLANT_TOKEN not in f.read():
            raise OverlayInputError(f"CLAUDE.md no longer contains the RFP propellant token {CLAUDE_MD_PROPELLANT_TOKEN!r}")


# ---------------------------------------------------------------------------------------------------- formatting
def g6(x):
    if x is None:
        return None
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return float(f"{float(x):.6g}")


def gv(v):
    if isinstance(v, (list, tuple)):
        return [g6(x) for x in v]
    return g6(v)


def fmt(x, nd=4):
    if x is None:
        return "TBD"
    if isinstance(x, (list, tuple)):
        a, b = x[0], x[-1]
        return fmt(a, nd) if a == b else f"{fmt(a, nd)}-{fmt(b, nd)}"
    if abs(x) >= 1000 and float(x).is_integer():
        return f"{int(x):,}"
    return f"{x:.{nd}g}"


def qrec(value, unit, cls, source, derivation=None, **kw):
    assert cls in CLASSES, cls
    d = {"value": gv(value), "unit": unit, "evidence_class": cls, "source": source}
    if derivation:
        d["derivation"] = derivation
    d.update(kw)
    return d


def as_range(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return [float(v), float(v)]
    if isinstance(v, list) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return [float(min(v)), float(max(v))]
    return None


# ---------------------------------------------------------------------------------------------------- evidence extraction
# Explicit, per-item extraction map. Names are the matrix's quantity names (checked at build time); values are always
# read from the matrix, never typed here. '@flow' / '@voltage' refer to the entry's flow / voltage fields.
# No number is typed in this map: missing-quantity texts quote the matrix's own field values, and mixture ratios are
# parsed from the matrix's anode_gas strings.
PURE_N2 = {"kind": "pure", "species": "N2", "token": "N2 (pure)"}
MISSING_B = {"definition": None, "why": "not_numeric"}
PPS_AREA = {"kind": "missing", "missing": "channel dimensions not given in the accessed text"}
HT5K_AREA = {"kind": "missing", "missing": "channel dimensions not reported in the accessed text"}
XE = {"gas": "Xe", "token": "Xe"}
P5_AREA = {"kind": "p5_case_file"}
ECHT_AREA = {"kind": "annulus_od_height", "od": "stated outer diameter of the BN chamber", "h": "channel height",
             "bound": "upper", "condition": "ECHT-OD-READING"}
CAMILA_AREA = {"kind": "mean_diameter_width", "d": "channel mean diameter", "w": "channel width"}
Z70_AREA = {"kind": "annulus_od_id", "od": "BN channel outer diameter", "id": "BN channel inner diameter"}

EXTRACT = {
    "E01": {"device": "P5", "role": "support_air_only", "flow": ["@flow"], "area": P5_AREA, "comp": PURE_N2,
            "cathode": XE, "b": {"definition": "Br_exit_centreline"}, "power": "range"},
    "E02": {"device": "P5", "role": "extinction", "ext_kind": "voltage_window", "flow": None,
            "area": P5_AREA, "comp": PURE_N2, "cathode": XE, "b": {"definition": "Br_exit_centreline"},
            "power": "range", "v_condition": "E02-WINDOW-EDGE"},
    "E03": {"device": "ECHT", "role": "support_air_only", "flow": ["@flow"], "area": ECHT_AREA, "comp": PURE_N2,
            "cathode": {"gas": "Ar", "token": "Ar"}, "b": {"definition": None, "why": "not_at_operating_points"},
            "power": "range"},
    "E04": {"device": "ECHT", "role": "extinction", "ext_kind": "low_flow", "flow": ["@flow"], "area": ECHT_AREA,
            "comp": PURE_N2, "cathode": {"gas": "Ar", "token": "Ar"}, "v_numeric": False, "b": MISSING_B,
            "power": "range"},
    "E05": {"device": "PPS1350", "role": "support_air_only", "flow": ["@flow", "long firing: anode N2 flow"],
            "area": PPS_AREA, "comp": PURE_N2, "cathode": XE, "b": MISSING_B, "power": "limit",
            "duration": "long firing: duration"},
    "E06": {"device": "PPS1350", "role": "support_air_only", "flow": ["@flow", "long firing: flow"],
            "area": PPS_AREA, "comp": {"kind": "mole_ratio_N2_O2"}, "cathode": XE, "b": MISSING_B, "power": "limit",
            "duration": "long firing: duration"},
    "E07": {"device": "PPS1350", "role": "duration_limit", "duration": "steady duration before first flame-out",
            "reason": "flame-outs attributed to anode oxidation after the steady duration recorded here, with Xe added "
                      "to the anode flow (second-hand); a duration / life limit, not a steady-state flow condition"},
    "E08": {"device": "HT5k-DM1", "role": "support_air_only", "flow": ["@flow"], "area": HT5K_AREA,
            "comp": {"kind": "mole_ratio_N2_O2"}, "cathode": XE, "b": MISSING_B, "power": "range"},
    "E09": {"device": "HT5k-DM2", "role": "support_air_only", "flow": ["@flow"], "area": HT5K_AREA,
            "comp": {"kind": "mole_fractions_N2_O2"},
            "cathode": {"gas": "N2", "token": "N2", "note": "steady-state cathode on N2 after the transition from Xe"},
            "b": MISSING_B, "power": "range", "duration": "cumulative firing on atmospheric propellant"},
    "E10": {"device": "CAMILA", "role": "support_air_only", "flow": ["@flow"], "area": CAMILA_AREA, "comp": PURE_N2,
            "cathode": XE, "b": {"definition": None, "why": "ratio_only"}, "power": "range"},
    "E11": {"device": "CAMILA", "role": "extinction", "ext_kind": "low_flow", "flow": None, "area": CAMILA_AREA,
            "comp": PURE_N2, "cathode": XE, "v_numeric": False, "b": MISSING_B, "power": "range"},
    "E12": {"device": "MaSHEKT-100", "role": "support_air_only", "flow": None,
            "area": {"kind": "missing", "missing": "geometry not accessed"}, "comp": PURE_N2,
            "cathode": {"gas": None}, "v_numeric": False, "b": MISSING_B, "power": "range"},
    # E13: the matrix flow and Xe flow are those of the lowest-Xe points at which the Z-70 SUSTAINED; the flow (and Xe
    # fraction) at which the discharge ceased is not reported. They are kept as a sustained reference point only and are
    # never used as an extinction value on any axis.
    "E13": {"device": "Z-70", "role": "extinction", "ext_kind": "xe_fraction", "flow": None,
            "flow_at_extinction": "not_reported",
            "sustained_reference": {"flow": ["@flow"],
                                    "flow_plus": ["lowest anode Xe flow that sustained (with N2 1.33-1.39 mg/s)"]},
            "area": Z70_AREA,
            "comp": {"kind": "xe_admixture_extinction", "base": ["N2"],
                     "xe_q": "Xe mass fraction of anode flow at the lowest-Xe points"},
            "cathode": XE, "b": {"definition": "Br_exit_centreline"}, "power": "range"},
    "E14": {"device": "Z-70", "role": "support_xe_admixture", "flow": ["total anode flow (Xe + air), runs XeAir-3/4"],
            "area": Z70_AREA,
            "comp": {"kind": "xe_admixture", "base": ["N2", "O2"], "base_note": "air (composition not stated)",
                     "xe_q": "Xe mass fraction of the anode flow, runs XeAir-3/4"},
            "cathode": XE, "b": {"definition": "Br_exit_centreline"}, "power": "range"},
    "E15": {"device": "TsNIIMASH-TAL", "role": "support_xe_admixture", "flow": None,
            "area": {"kind": "missing", "missing": "channel width not reported (anode diameters only)"},
            "comp": {"kind": "not_comparable", "species": ["N2", "O2", "Xe"],
                     "missing": "Xe + air fractions not legible in the accessed scan"},
            "cathode": {"gas": None}, "v_numeric": False, "b": MISSING_B, "power": "range"},
    "E16": {"device": "BHT", "role": "support_air_only", "flow": ["@flow"],
            "area": {"kind": "missing", "missing": "channel dimensions not reported in the review"},
            "comp": {"kind": "not_comparable", "species": ["N2", "O2", "Ar"],
                     "missing": "fraction basis not stated; its Ar share is a surrogate for atomic O (a different "
                                "species)"},
            "cathode": {"gas": None}, "b": MISSING_B, "power": "range"},
    "E17": {"device": "ABHET", "role": "not_informative",
            "reason": "fed by a pre-ionized upstream source; the role of incoming ions cannot be separated (matrix)"},
    "E18": {"device": "RAM-EP", "role": "not_informative",
            "reason": "two-stage device with a dedicated ionization stage (not direct Hall operation)"},
    "E19": {"device": "HHT", "role": "support_air_only", "flow": ["@flow"],
            "mode_note": "single-stage (RF-off) mode of a helicon Hall device, per the second-hand report",
            "area": {"kind": "missing", "missing": "geometry not accessed"}, "comp": PURE_N2,
            "cathode": XE, "b": MISSING_B, "power": "range"},
    "E20": {"device": "MSTU-lab", "role": "support_air_only", "flow": ["@flow"],
            "flow_condition": "E20-FLOW-BASIS",
            "area": {"kind": "missing", "missing": "channel width not reported (average channel diameter only)"},
            "comp": {"kind": "not_comparable", "species": ["N2", "O2"],
                     "missing": "air composition and the basis of the stated N2/O2 ratio not stated"},
            "cathode": XE, "v_numeric": False, "b": MISSING_B, "power": "range"},
    "E21": {"device": "ABCHT", "role": "not_informative",
            "reason": "tested on xenon only; no atmospheric-gas test reported"},
}
ROLES = {
    "support_air_only": "sustained on atmospheric gas without Xe in the anode flow and without an active pre-ionizer "
                        "(may bound sustainment from the supporting side)",
    "support_xe_admixture": "sustained on atmospheric gas with Xe in the anode flow (relevant to the mixed air + Xe "
                            "variant only)",
    "extinction": "extinction / quenching reported at a stated condition (may bound sustainment from the "
                  "contradicting side)",
    "duration_limit": "sustainment limited in duration (flame-outs), not a steady-state flow condition",
    "not_informative": "not informative for direct Hall operation (hall_only)",
}
CONDITIONS = {
    "ECHT-OD-READING": "the ECHT channel area uses reading A of the stated BN-chamber outer diameter (taken as the "
                       "channel outer-wall diameter); under reading B (BN piece OD) the channel is smaller, so the area "
                       "is an upper bound and the flow density a lower bound (REPO_ECHT_AUDIT "
                       "geometry.outer_diameter.ambiguity)",
    "E20-FLOW-BASIS": "the E20 flow is a review-reported 'total mass flow'; whether it includes the Xe cathode flow "
                      "(a separate matrix quantity) is not stated (matrix E20)",
    "E02-WINDOW-EDGE": "the P5 N2 voltage window of E02 is a text statement without boundary data and its edges are "
                       "approximate: the same thruster sustained N2 setpoints beyond the stated upper edge (E01; the "
                       "matrix's own note is quoted in evidence_regions[E02].discharge_voltage.edge_note). A case "
                       "outside or straddling the stated window is therefore not placed against E02's extinction "
                       "statement until the edge is resolved",
}


def _find_q(entry, name):
    if name == "@flow":
        return entry["flow"]
    if name == "@voltage":
        return entry["voltage"]
    hits = [q for q in entry["quantities"] + entry["thruster"]["geometry"] if q["name"] == name]
    if len(hits) != 1:
        raise OverlayInputError(f"{entry['id']}: expected exactly one quantity named {name!r}, found {len(hits)}")
    return hits[0]


def _num_q(entry, name, unit):
    q = _find_q(entry, name)
    if q["unit"] != unit:
        raise OverlayInputError(f"{entry['id']}: quantity {name!r} unit {q['unit']!r}, expected {unit!r}")
    r = as_range(q["value"])
    if r is None:
        raise OverlayInputError(f"{entry['id']}: quantity {name!r} is not numeric ({q['value']!r})")
    return q, r


def _loc(entry, q):
    return f"{q['source']}, {q['locator']} (matrix {entry['id']}: '{q['name']}')"


def area_record(entry, spec, p5):
    kind = spec["kind"]
    if kind == "missing":
        return None, spec["missing"]
    if kind == "p5_case_file":
        radii = sorted({(c["r_in_m"], c["r_out_m"]) for c in p5["cases"]})
        if len(radii) != 1:
            raise OverlayInputError(f"p5_xenon.json: non-uniform channel radii {radii}")
        if P5_GEOMETRY_SOURCE_TOKEN not in p5["source"]:
            raise OverlayInputError("p5_xenon.json 'source' no longer cites the P5 channel radii as expected")
        r_in, r_out = radii[0]
        a = math.pi * (r_out ** 2 - r_in ** 2)
        return qrec(a, "m^2", "inferred",
                    f"hallthruster_bridge/cases/p5_xenon.json r_in_m = {r_in}, r_out_m = {r_out} (its 'source' field: "
                    f"'{P5_GEOMETRY_SOURCE_TOKEN}; J. Electr. Propuls. 2026, doi:10.1007/s44205-026-00179-9)'; "
                    f"published values as cited by the repository case file, not re-verified by this overlay)",
                    "annulus pi (r_out^2 - r_in^2); radii measured (design dimensions, evidence level 3) -> our "
                    "arithmetic", bound=None, conditional_on=[]), None
    if kind == "annulus_od_height":
        qd, d = _num_q(entry, spec["od"], "mm")
        qh, h = _num_q(entry, spec["h"], "mm")
        a = math.pi * (h[0] * 1e-3) * (d[0] * 1e-3 - h[0] * 1e-3)
        return qrec(a, "m^2", "inferred", f"{_loc(entry, qd)}; {_loc(entry, qh)}",
                    "annulus pi h (D_out - h) with D_out = the stated OD (reading A); our arithmetic",
                    bound="upper", conditional_on=[spec["condition"]]), None
    if kind == "mean_diameter_width":
        qd, d = _num_q(entry, spec["d"], "mm")
        qw, w = _num_q(entry, spec["w"], "mm")
        a = math.pi * (d[0] * 1e-3) * (w[0] * 1e-3)
        return qrec(a, "m^2", "inferred", f"{_loc(entry, qd)}; {_loc(entry, qw)}",
                    "annulus pi D_mean w; our arithmetic", bound=None, conditional_on=[]), None
    if kind == "annulus_od_id":
        qo, do = _num_q(entry, spec["od"], "mm")
        qi, di = _num_q(entry, spec["id"], "mm")
        a = math.pi / 4.0 * ((do[0] * 1e-3) ** 2 - (di[0] * 1e-3) ** 2)
        return qrec(a, "m^2", "inferred", f"{_loc(entry, qo)}; {_loc(entry, qi)}",
                    "annulus pi/4 (D_out^2 - D_in^2); our arithmetic", bound=None, conditional_on=[]), None
    raise OverlayInputError(f"unknown area kind {kind}")


def composition_record(entry, spec, M):
    kind = spec["kind"]
    gas = entry["propellant"]["anode_gas"]
    if "token" in spec and spec["token"] not in gas:
        raise OverlayInputError(f"{entry['id']}: anode_gas {gas!r} lacks the expected token {spec['token']!r}")
    mN2, mO2 = M["N2"], M["O2"]
    if kind == "pure":
        return {"comparable": True, "species_present": [spec["species"]], "w": {spec["species"]: 1.0},
                "evidence_class": "measured", "basis": f"tested gas as stated: '{gas}'", "xe_fraction": None}
    if kind == "mole_ratio_N2_O2":                          # e.g. '1.27N2 + O2', parsed from the matrix string
        m = re.search(r"(\d+(?:\.\d+)?)N2 \+ O2", gas)
        if not m:
            raise OverlayInputError(f"{entry['id']}: no 'rN2 + O2' ratio in anode_gas {gas!r}")
        r = float(m.group(1))
        w = r * mN2 / (r * mN2 + mO2)
        return {"comparable": True, "species_present": ["N2", "O2"], "w": {"N2": g6(w), "O2": g6(1.0 - w)},
                "evidence_class": "inferred", "xe_fraction": None,
                "basis": f"'{gas}': N2:O2 = {m.group(1)}:1 read as a mole ratio (matrix derived_checks; verify) -> "
                         f"mass fractions with abep_sim.constants.M_SPECIES (the feed envelope's basis); our "
                         f"arithmetic"}
    if kind == "mole_fractions_N2_O2":                      # e.g. '0.56N2 + 0.44O2', parsed from the matrix string
        m = re.search(r"(\d*\.\d+)N2 \+ (\d*\.\d+)O2", gas)
        if not m:
            raise OverlayInputError(f"{entry['id']}: no 'xN2 + yO2' fractions in anode_gas {gas!r}")
        xn, xo = float(m.group(1)), float(m.group(2))
        w = xn * mN2 / (xn * mN2 + xo * mO2)
        return {"comparable": True, "species_present": ["N2", "O2"], "w": {"N2": g6(w), "O2": g6(1.0 - w)},
                "evidence_class": "inferred", "xe_fraction": None,
                "basis": f"'{gas}' read as mole fractions (matrix derived_checks: basis not stated by the source; "
                         f"verify) -> mass fractions with abep_sim.constants.M_SPECIES; our arithmetic"}
    if kind == "xe_admixture_extinction":                   # extinction below the lowest SUSTAINING Xe fraction (E13)
        q, xr = _num_q(entry, spec["xe_q"], "1")
        return {"comparable": False, "species_present": sorted(set(spec["base"]) | {"Xe"}), "w": None,
                "evidence_class": q["evidence_class"], "xe_fraction": None,
                "xe_fraction_lowest_sustained": qrec(
                    xr, "1", q["evidence_class"], _loc(entry, q),
                    meaning="lowest Xe mass fraction at which the discharge sustained; the fraction at which it "
                            "ceased is not reported; not an extinction value"),
                "missing": f"Xe mass fraction (and anode flow) at extinction not reported: the lowest Xe mass fraction "
                           f"that sustained was {fmt(xr)} (matrix '{q['name']}'); matrix outcome: "
                           f"'{entry['outcome_statement']}' (anode gas '{gas}'); no Xe-fraction direction is used for an "
                           f"extinction item (definitions.directions)",
                "basis": f"'{gas}'"}
    if kind == "xe_admixture":
        q, xr = _num_q(entry, spec["xe_q"], "1")
        return {"comparable": False, "species_present": sorted(set(spec["base"]) | {"Xe"}), "w": None,
                "base_comparable": len(spec["base"]) == 1 and not spec.get("base_note"),
                "evidence_class": q["evidence_class"],
                "xe_fraction": qrec(xr, "1", q["evidence_class"], _loc(entry, q),
                                    meaning=f"Xe mass fraction of sustained runs (matrix '{q['name']}')"),
                "missing": f"Xe-admixture feed ({' + '.join(spec['base'])} + Xe, Xe mass fraction {fmt(xr)}"
                           + (f"; {spec['base_note']}" if spec.get("base_note") else "")
                           + "): comparable only with a feed that contains Xe (mixed air + Xe variant)",
                "basis": f"'{gas}'"}
    if kind == "not_comparable":
        return {"comparable": False, "species_present": spec["species"], "w": None, "evidence_class": None,
                "missing": spec["missing"], "basis": f"'{gas}'", "xe_fraction": None}
    raise OverlayInputError(f"unknown composition kind {kind}")


def evidence_region(entry, spec, p5, M, rfp_power_kW):
    eid = entry["id"]
    role = spec["role"]
    reg = {"id": eid, "title": entry["title"], "device": spec["device"], "role": role,
           "evidence_level": entry["evidence_level"], "outcome": entry["outcome"],
           "status_bearing": bool(entry["evidence_level"] <= 3 and role in ("support_air_only", "extinction",
                                                                              "support_xe_admixture")),
           "sources": entry["sources"], "preionizer_present": entry["preionizer"]["present"],
           "ignition": {k: entry["ignition"][k] for k in ("mode", "basis", "evidence_class")},
           "anode_gas": entry["propellant"]["anode_gas"], "cathode_gas_reported": entry["propellant"]["cathode_gas"],
           "xenon_in_anode_flow": entry["propellant"]["xenon_in_anode_flow"]}
    if spec.get("mode_note"):
        reg["mode_note"] = spec["mode_note"]
    if role in ("not_informative", "duration_limit"):
        reg["reason"] = spec["reason"] if "reason" in spec else None
        if spec.get("duration"):
            q, r = _num_q(entry, spec["duration"], "h")
            reg["duration"] = qrec(r if r[0] != r[1] else r[0], "h", q["evidence_class"], _loc(entry, q))
        return reg
    conds = []

    def flow_sum(fspec):
        lo, hi, classes, locs = math.inf, -math.inf, [], []
        for n in fspec["flow"]:
            q, r = _num_q(entry, n, "mg/s")
            lo, hi = min(lo, r[0]), max(hi, r[1])
            classes.append(q["evidence_class"])
            locs.append(_loc(entry, q))
        deriv = "min / max over the named quantities"
        if fspec.get("flow_plus"):
            for n in fspec["flow_plus"]:
                q, r = _num_q(entry, n, "mg/s")
                lo, hi = lo + r[0], hi + r[1]
                locs.append(_loc(entry, q))
            classes = ["inferred"]
            deriv = "atmospheric-gas anode flow + Xe anode flow (total anode flow); our arithmetic"
        return [lo, hi], (classes[0] if len(set(classes)) == 1 else "inferred"), "; ".join(locs), deriv

    # flow (anode, atmospheric gas plus any Xe in the anode flow) -----------------------------------------------------
    if spec.get("flow_at_extinction") == "not_reported":
        # an extinction item whose matrix flow is a SUSTAINED reference point: the flow at extinction is not reported
        if role != "extinction":
            raise OverlayInputError(f"{eid}: 'flow_at_extinction' applies to extinction items only")
        fq = entry["flow"]
        rng, cls, locs, deriv = flow_sum(spec["sustained_reference"])
        reg["sustained_reference_point"] = qrec(
            rng, "mg/s", cls, locs, deriv,
            meaning="total anode flow of the lowest-Xe points at which the discharge SUSTAINED; not an extinction "
                    "value; not used on any axis or threshold")
        reg["flow"] = {"value": None,
                       "missing": f"anode flow at extinction not reported: the matrix flow ('{fq['name']}') and Xe flow "
                                  f"are those of the lowest-Xe points at which the discharge sustained (total "
                                  f"{fmt(rng)} mg/s, sustained_reference_point); matrix outcome: "
                                  f"'{entry['outcome_statement']}'"}
    elif spec["flow"] is None:
        fq = entry["flow"]
        if as_range(fq["value"]) is not None:
            raise OverlayInputError(f"{eid}: flow is numeric in the matrix but the extraction map expects none")
        reg["flow"] = {"value": None, "missing": f"matrix '{fq['name']}': {fq['value']}"}
    else:
        rng, cls, locs, deriv = flow_sum(spec)
        fc = [spec["flow_condition"]] if spec.get("flow_condition") else []
        conds += fc
        reg["flow"] = qrec(rng, "mg/s", cls, locs, deriv, conditional_on=fc)
    # channel cross-section and flow density (scaling assumption S1) ---------------------------------------------------
    area, area_missing = area_record(entry, spec["area"], p5)
    reg["channel_area"] = area if area else {"value": None, "missing": area_missing}
    if area and reg["flow"]["value"] is not None:
        a = area["value"]
        f = reg["flow"]["value"]
        bound = "lower" if area.get("bound") == "upper" else None
        fd_conds = list(area.get("conditional_on", [])) + list(reg["flow"].get("conditional_on", []))
        reg["flow_density"] = qrec([f[0] * 1e-6 / a, f[1] * 1e-6 / a], "kg m^-2 s^-1", "inferred",
                                   "flow and channel_area above", "Gamma = mdot / A_ch (scaling assumption S1)",
                                   bound=bound, conditional_on=sorted(set(fd_conds)))
        conds += fd_conds
    else:
        miss = []
        if reg["flow"]["value"] is None:
            miss.append(reg["flow"]["missing"])
        if not area:
            miss.append(area_missing)
        reg["flow_density"] = {"value": None, "missing": "; ".join(miss)}
    # composition ------------------------------------------------------------------------------------------------------
    reg["composition"] = composition_record(entry, spec["comp"], M)
    # voltage ----------------------------------------------------------------------------------------------------------
    vq = entry["voltage"]
    vr = as_range(vq["value"])
    if (vr is None) != (spec.get("v_numeric") is False):
        raise OverlayInputError(f"{eid}: matrix voltage numeric={vr is not None} differs from the extraction map")
    if vr is None:
        reg["discharge_voltage"] = {"value": None, "missing": f"matrix '{vq['name']}': {vq['value']}"}
    else:
        vkw = {}
        if spec.get("v_condition"):                         # a stated window whose edge is approximate (E02)
            vkw = {"conditional_on": [spec["v_condition"]], "edge_note": f"matrix: '{vq['uncertainty']}'"}
            conds.append(spec["v_condition"])
        reg["discharge_voltage"] = qrec(vr, "V", vq["evidence_class"], _loc(entry, vq),
                                        kind=("window" if spec.get("ext_kind") == "voltage_window" else "operated"),
                                        **vkw)
    # magnetic field ---------------------------------------------------------------------------------------------------
    bq = entry["magnetic_field"]
    if spec["b"]["definition"] is None:
        why = spec["b"]["why"]
        numeric = as_range(bq["value"]) is not None
        if numeric != (why != "not_numeric"):
            raise OverlayInputError(f"{eid}: matrix B numeric={numeric} differs from the extraction map ({why})")
        miss = {"not_numeric": f"matrix '{bq['name']}': {bq['value']}",
                "not_at_operating_points": f"B not given at the operating points (matrix quantity '{bq['name']}')",
                "ratio_only": f"B given only as a ratio (unit '{bq['unit']}', matrix quantity '{bq['name']}'), not as "
                              f"an absolute value"}[why]
        reg["magnetic_field"] = {"value": None, "missing": miss}
    else:
        br = as_range(bq["value"])
        if br is None or bq["unit"] != "G":
            raise OverlayInputError(f"{eid}: magnetic field not numeric in G")
        reg["magnetic_field"] = qrec(br, "G", bq["evidence_class"], _loc(entry, bq),
                                     definition=spec["b"]["definition"])
    # cathode gas ------------------------------------------------------------------------------------------------------
    c = spec["cathode"]
    if c["gas"] is None:
        reg["cathode_gas"] = {"gas": None, "missing": f"matrix cathode_gas: {entry['propellant']['cathode_gas']}"}
    else:
        if c["token"] not in entry["propellant"]["cathode_gas"]:
            raise OverlayInputError(f"{eid}: cathode_gas lacks token {c['token']!r}")
        rel = RFP_GAS_RELATION[c["gas"]]
        reg["cathode_gas"] = {"gas": c["gas"], "note": c.get("note"), "rfp_propellant_relation": rel,
                              "rfp_propellant_relation_text": RFP_GAS_RELATION_TEXT[rel]}
    # power (informational; RFP total-power ceiling) -------------------------------------------------------------------
    pq = entry["thruster"]["power"]
    pr = as_range(pq["value"])
    if pr is None:
        reg["discharge_power"] = {"value": None, "missing": f"power: {pq['value']}"}
    else:
        scale = {"kW": 1.0, "W": 1e-3}[pq["unit"]]
        pk = [pr[0] * scale, pr[1] * scale]
        if spec["power"] == "limit":
            rel = "WITHIN_RFP_CEILING" if pk[1] <= rfp_power_kW else "STRADDLES_RFP_CEILING"
            kind = "upper limit applied during the tests"
        else:
            rel = ("ABOVE_RFP_CEILING" if pk[0] >= rfp_power_kW else
                   "WITHIN_RFP_CEILING" if pk[1] <= rfp_power_kW else "STRADDLES_RFP_CEILING")
            kind = "operated range"
        reg["discharge_power"] = qrec(pk, "kW", pq["evidence_class"], _loc(entry, pq), kind=kind,
                                      rfp_total_power_relation=rel)
    if spec.get("ext_kind"):
        reg["extinction_kind"] = spec["ext_kind"]
    if spec.get("duration"):
        q, r = _num_q(entry, spec["duration"], "h")
        reg["duration"] = qrec(r if r[0] != r[1] else r[0], "h", q["evidence_class"], _loc(entry, q))
    reg["conditional_on"] = sorted(set(conds))
    return reg


# ---------------------------------------------------------------------------------------------------- axis comparisons
def cover_directional(case_rng, item_val, bound, conds, mode):
    """mode 'support': the item sustained at item_val (lowest demonstrated); lower is harsher. COVERS when the case is
    at or above the item's lowest demonstrated value. mode 'extinction': the item extinguished at item_val; COVERS when
    the case is at or below it. bound 'lower': the true item value is >= item_val."""
    lo, hi = case_rng
    conds = sorted(conds)

    def out(cov, c):
        return {"coverage": cov, "conditional_on": c} if c else {"coverage": cov}

    if mode == "support":
        if hi < item_val:                      # the true value is >= item_val > hi (exact or lower bound)
            return out(DNR, [] if bound == "lower" else conds)
        return out(COVERS if lo >= item_val else PARTIAL, conds)
    if hi <= item_val:                         # the case is at or below the extinction value (true value >= it)
        return out(COVERS, [] if bound == "lower" else conds)
    return out(DNR if lo > item_val else PARTIAL, conds)


def cover_interval(case_rng, item_rng):
    lo, hi = case_rng
    a, b = item_rng
    if a <= lo and hi <= b:
        return COVERS
    if hi < a or lo > b:
        return DNR
    return PARTIAL


def cover_composition(case_w, reg):
    comp = reg["composition"]
    present = sorted(s for s, v in case_w.items() if (v or 0.0) > EPS)
    absent = [s for s in present if s not in comp["species_present"]]
    if absent:
        return {"coverage": DNR, "species_absent_from_evidence": absent}
    if not comp["comparable"]:
        return {"coverage": NC, "missing": comp["missing"]}
    dev = {s: (case_w.get(s) or 0.0) - (comp["w"].get(s) or 0.0) for s in sorted(set(case_w) | set(comp["w"]))}
    if max(abs(v) for v in dev.values()) <= EPS:
        return {"coverage": COVERS}
    out = {"coverage": DNR, "delta_w": {s: g6(v) for s, v in dev.items() if abs(v) > EPS}}
    return out


def axis_flow(case, reg):
    f = reg["flow"]
    if f["value"] is None:
        return {"coverage": NC, "missing": f["missing"]}
    mode = "extinction" if reg["role"] == "extinction" else "support"
    if case["mdot_kgps"] is None:
        d = {"coverage": UND, "blocked_by": ["B-FEED-MDOT"]}
        if case.get("mdot_max_H_RAM_kgps") is not None and mode == "support":
            d["under_H_RAM"] = DNR if f["value"][0] * 1e-6 > case["mdot_max_H_RAM_kgps"] else "NOT_EXCLUDED"
        return d
    return cover_directional(case["mdot_kgps"], f["value"][0] * 1e-6, None, f.get("conditional_on", []), mode)


def flow_density_range(mdot, area):
    """Gamma = mdot / A_ch over the full ranges (no end of either range is dropped): [mdot_lo / A_hi, mdot_hi / A_lo]."""
    return [mdot[0] / area[1], mdot[1] / area[0]]


def axis_flow_density(case, reg):
    fd = reg["flow_density"]
    if fd["value"] is None:
        return {"coverage": NC, "missing": fd["missing"]}
    if reg["role"] == "extinction" and reg.get("extinction_kind") == "voltage_window":
        return {"coverage": NC, "missing": "anode flow at the window boundary not reported"}
    blk = [b for b, v in (("B-FEED-MDOT", case["mdot_kgps"]), ("B-DESIGN-ACH", case["channel_area_m2"]))
           if v is None]
    if blk:
        return {"coverage": UND, "blocked_by": blk}
    g = flow_density_range(case["mdot_kgps"], case["channel_area_m2"])
    mode = "extinction" if reg["role"] == "extinction" else "support"
    d = cover_directional(g, fd["value"][0], fd.get("bound"), fd.get("conditional_on", []), mode)
    d["assumptions"] = ["S1"]
    d["case_value"] = gv(g)
    return d


def axis_composition(case, reg):
    if case["w_valve"] is None:
        return {"coverage": UND, "blocked_by": ["B-FEED-COMP"]}
    comp, w = reg["composition"], case["w_valve"]
    if comp.get("xe_fraction") is not None:               # Xe-admixture evidence: compare on the Xe mass fraction
        present = sorted(s for s, v in w.items() if (v or 0.0) > EPS)
        absent = [s for s in present if s not in comp["species_present"]]
        if absent:
            return {"coverage": DNR, "species_absent_from_evidence": absent}
        if not comp.get("base_comparable"):
            return {"coverage": NC, "missing": comp["missing"]}
        if reg["role"] != "support_xe_admixture":
            # the declared Xe-fraction direction (definitions.directions) places SUPPORTING Xe-admixture items only;
            # an extinction item would need its Xe fraction at extinction (E13 does not report it)
            raise OverlayInputError(f"{reg['id']}: Xe-fraction comparison is defined for support_xe_admixture items only")
        f, lo = (w.get("Xe") or 0.0), comp["xe_fraction"]["value"][0]
        return {"coverage": COVERS if f >= lo else DNR, "case_xe_fraction": g6(f)}
    return cover_composition(w, reg)


def axis_voltage(case, reg):
    v = reg["discharge_voltage"]
    if v["value"] is None:
        return {"coverage": NC, "missing": v["missing"]}
    if case["V_d"] is None:
        return {"coverage": UND, "blocked_by": ["B-DESIGN-VD"]}
    if v.get("kind") == "window":           # extinction outside a stated window
        inside = cover_interval(case["V_d"], v["value"])
        cov = {COVERS: DNR, DNR: COVERS, PARTIAL: PARTIAL}[inside]
        d = {"coverage": cov}
        if cov != DNR and v.get("conditional_on"):      # outside / straddling an approximate window edge
            d["conditional_on"] = sorted(v["conditional_on"])
        return d
    return {"coverage": cover_interval(case["V_d"], v["value"])}


def axis_b(case, reg):
    b = reg["magnetic_field"]
    if b["value"] is None:
        return {"coverage": NC, "missing": b["missing"]}
    if case["B"] is None:
        return {"coverage": UND, "blocked_by": ["B-DESIGN-B"]}
    if case["B"]["definition"] != b["definition"]:
        return {"coverage": NC, "missing": f"B definition differs (design {case['B']['definition']!r}, evidence "
                                           f"{b['definition']!r})"}
    return {"coverage": cover_interval(case["B"]["value"], b["value"]), "assumptions": ["S2"]}


def axis_cathode(case, reg):
    c = reg["cathode_gas"]
    if c["gas"] is None:
        return {"coverage": NC, "missing": c["missing"]}
    if case["cathode_gas"] is None:
        return {"coverage": UND, "blocked_by": ["B-DESIGN-CATHODE"]}
    return {"coverage": COVERS if case["cathode_gas"] == c["gas"] else DNR}


def axis_power(case, reg):
    p = reg["discharge_power"]
    if p["value"] is None:
        return {"coverage": NC, "missing": p["missing"]}
    d = {"rfp_total_power_relation": p["rfp_total_power_relation"]}
    if case["P_d_kW"] is None:
        d.update({"coverage": UND, "blocked_by": ["B-DESIGN-POWER"]})
    elif p.get("kind") == "upper limit applied during the tests":
        d["coverage"] = COVERS if case["P_d_kW"][1] <= p["value"][1] else PARTIAL
    else:
        d["coverage"] = cover_interval(case["P_d_kW"], p["value"])
    return d


def compare(case, reg):
    axes = {
        "anode_flow": axis_flow(case, reg),
        "anode_flow_density": axis_flow_density(case, reg),
        "composition": axis_composition(case, reg),
        "discharge_voltage": axis_voltage(case, reg),
        "magnetic_field": axis_b(case, reg),
        "cathode_gas": axis_cathode(case, reg),
        "discharge_power": axis_power(case, reg),
    }
    labels = {a: axes[a]["coverage"] for a in REQUIRED_AXES}
    conds = sorted({c for a in REQUIRED_AXES for c in axes[a].get("conditional_on", [])})
    reasons = [f"{a}: {labels[a]}" for a in REQUIRED_AXES if labels[a] != COVERS]
    if conds:
        reasons.append("interpretation conditions: " + ", ".join(conds))
    if not reg["status_bearing"]:
        reasons.append(f"evidence level {reg['evidence_level']} (> 3): corroborating only, not status-bearing")
    all_cover = all(labels[a] == COVERS for a in REQUIRED_AXES) and not conds
    if all_cover and reg["status_bearing"]:
        verdict = "contradicts" if reg["role"] == "extinction" else "supports"
    elif any(labels[a] == DNR for a in REQUIRED_AXES):
        verdict = "does_not_reach_case"
    else:
        verdict = "cannot_decide"
    # S3: the item's region is the product of its per-axis ranges (flow density, V_d, B assessed independently); joint
    # operating points are not checked. Every verdict that rests on more than one numeric axis carries it.
    assumptions = sorted({s for a in REQUIRED_AXES for s in axes[a].get("assumptions", [])} | {"S3"})
    return {"item": reg["id"], "role": reg["role"], "status_bearing": reg["status_bearing"], "axes": axes,
            "verdict": verdict, "reasons": reasons, "assumptions": assumptions,
            "joint_operating_point_check": "NOT_CHECKED (S3)"}


# ---------------------------------------------------------------------------------------------------- design point
def default_design_point():
    return {"supplied": False, "label": None,
            "inputs": {k: {"status": "TBD", "requires": DESIGN_TBD[k]} for k in DESIGN_KEYS}}


def validate_design_point(dp):
    if not isinstance(dp, dict) or dp.get("format") != "hall_sustainment_design_point_v1":
        raise InvalidDesignPoint("design point must be {format: 'hall_sustainment_design_point_v1', label, inputs}")
    inputs = dp.get("inputs")
    if not isinstance(inputs, dict):
        raise InvalidDesignPoint("design point 'inputs' must be an object")
    unknown = sorted(set(inputs) - set(DESIGN_KEYS))
    if unknown:
        raise InvalidDesignPoint(f"unknown design-point inputs {unknown}")
    missing = [k for k in DESIGN_KEYS if k not in inputs]
    if missing:
        raise MissingDesignInput(f"design-point inputs missing {missing}: give each a value (with source and "
                                 f"evidence_class) or an explicit {{'status': 'TBD', 'requires': ...}}")
    out = {}
    for k in DESIGN_KEYS:
        e = inputs[k]
        if not isinstance(e, dict):
            raise InvalidDesignPoint(f"{k}: must be an object")
        if e.get("status") == "TBD":
            if not str(e.get("requires", "")).startswith("TBD - requires"):
                raise InvalidDesignPoint(f"{k}: an explicit TBD needs 'requires': 'TBD - requires ...'")
            out[k] = {"status": "TBD", "requires": e["requires"]}
            continue
        if not e.get("source") or e.get("evidence_class") not in CLASSES:
            raise InvalidDesignPoint(f"{k}: needs 'source' and 'evidence_class' in {CLASSES}")
        v = e.get("value")
        if k == "cathode_gas":
            if v not in CATHODE_GASES:
                raise InvalidDesignPoint(f"cathode_gas must be one of {CATHODE_GASES}")
        elif k == "magnetic_field":
            if e.get("definition") not in B_DEFINITIONS or e.get("unit") != "G" or as_range(v) is None:
                raise InvalidDesignPoint(f"magnetic_field needs a numeric value in G and a definition in "
                                         f"{sorted(B_DEFINITIONS)}")
        else:
            r = as_range(v)
            if r is None or r[0] <= 0:
                raise InvalidDesignPoint(f"{k}: value must be a positive number or [lo, hi]")
        out[k] = {kk: e[kk] for kk in ("value", "unit", "definition", "source", "evidence_class") if kk in e}
    return {"supplied": True, "label": dp.get("label"), "inputs": out}


def design_values(dp):
    inp = dp["inputs"]

    def val(k):
        e = inp[k]
        return None if e.get("status") == "TBD" else e

    a = val("channel_area_m2")
    v = val("discharge_voltage_V")
    b = val("magnetic_field")
    c = val("cathode_gas")
    p = val("discharge_power_W")
    return {"channel_area_m2": as_range(a["value"]) if a else None,       # [lo, hi]: the full range is carried
            "V_d": as_range(v["value"]) if v else None,
            "B": {"value": as_range(b["value"]), "definition": b["definition"]} if b else None,
            "cathode_gas": c["value"] if c else None,
            "P_d_kW": [x * 1e-3 for x in as_range(p["value"])] if p else None}


# ---------------------------------------------------------------------------------------------------- feed cases
def composition_scenarios(w_fs, src):
    wO, wN2, wO2 = w_fs["O"], w_fs["N2"], w_fs["O2"]
    return {
        "SC-FS": {"w": {"O": g6(wO), "N2": g6(wN2), "O2": g6(wO2)}, "evidence_class": "model-derived",
                  "source": src,
                  "definition": "no O recombination: valve-outlet mass fractions equal to the free-stream mass "
                                "fractions (the chain's collected-flow split convention, FE-05 primary)"},
        "SC-REC": {"w": {"O": 0.0, "N2": g6(wN2), "O2": g6(wO + wO2)}, "evidence_class": "model-derived",
                   "source": src,
                   "definition": "complete O -> O2 recombination at the same split: w_N2 unchanged, w_O2 = w_O + w_O2 "
                                 "(mass conserved)"},
    }


def air_case_state(fc, design, T_max_N):
    fs, st = fc["free_stream"], fc["feed_state"]
    rhoV = fs["mass_flux_kgpm2ps"]["value"]
    V = fs["V_mps"]["value"]
    mdot = st["mdot_total_kgps"]["value"]
    wv = st["w_s"]["values"]
    w_valve = None if (not wv or any(v is None for v in wv.values())) else dict(wv)
    return {"mdot_kgps": [mdot, mdot] if mdot is not None else None, "w_valve": w_valve,
            "rhoV": rhoV, "V": V, "mdot_max_H_RAM_kgps": T_max_N / V,
            **design}


def feed_quantity_view(q, path):
    d = {"value": q.get("value", q.get("values")), "unit": q["unit"], "evidence_class": q["evidence_class"],
         "source": f"feed_envelope_v1 {path}"}
    if q.get("requires"):
        d["requires"] = q["requires"]
    if q.get("requires_design_inputs"):
        d["requires_design_inputs"] = q["requires_design_inputs"]
    return d


def case_blockers(cs, fc, comps, regs, max_tested_wO2, scen):
    B = []
    st = fc["feed_state"] if fc else None
    if cs.get("mdot_kgps") is None and st is not None:
        B.append({"id": "B-FEED-MDOT", "kind": "feed_tbd",
                  "detail": "delivered anode mass flow at IF-A5 is TBD in the feed envelope (case status "
                            f"{fc['status']})", "requires": st["mdot_total_kgps"]["requires"],
                  "requires_design_inputs": st["mdot_total_kgps"]["requires_design_inputs"], "resolved_by": ["DI-1"]})
    if cs.get("w_valve") is None and st is not None:
        B.append({"id": "B-FEED-COMP", "kind": "feed_tbd",
                  "detail": "valve-outlet composition at IF-A5 is TBD in the feed envelope; bounded here only by "
                            "the scenarios SC-FS / SC-REC under the chain's split convention",
                  "requires": st["w_s"]["requires"], "requires_design_inputs": st["w_s"]["requires_design_inputs"],
                  "resolved_by": ["DI-1", "DM-1"]})
    for key, bid in (("channel_area_m2", "B-DESIGN-ACH"), ("V_d", "B-DESIGN-VD"), ("B", "B-DESIGN-B"),
                     ("cathode_gas", "B-DESIGN-CATHODE"), ("P_d_kW", "B-DESIGN-POWER")):
        if cs.get(key) is None:
            dk = {"channel_area_m2": "channel_area_m2", "V_d": "discharge_voltage_V", "B": "magnetic_field",
                  "cathode_gas": "cathode_gas", "P_d_kW": "discharge_power_W"}[key]
            B.append({"id": bid, "kind": "design_tbd",
                      "detail": f"Vyovrinda design point '{dk}' is TBD" +
                                (" (informational axis; not needed for a status)" if bid == "B-DESIGN-POWER" else ""),
                      "requires": DESIGN_TBD[dk], "resolved_by": ["DI-2"]})
    sup = [c for c in comps if c["role"] == "support_air_only"]
    if cs.get("w_valve") is not None:
        # a delivered valve-outlet composition is supplied: the composition blockers are evaluated on it, not on the
        # free-stream scenarios (which only bound a TBD composition)
        wv = cs["w_valve"]
        if (wv.get("O") or 0.0) > EPS and sup and all(
                c["axes"]["composition"]["coverage"] == DNR
                and "O" in c["axes"]["composition"].get("species_absent_from_evidence", []) for c in sup):
            B.append({"id": "B-EVID-ATOMIC-O", "kind": "evidence_gap",
                      "detail": f"the delivered valve-outlet composition contains atomic O (w_O {fmt(wv['O'])}); no "
                                "evidence item was tested with atomic O in the anode feed, so every item DOES_NOT_REACH "
                                "on composition", "resolved_by": ["DM-1", "DM-2"]})
        wo2 = wv.get("O2") or 0.0
        if max_tested_wO2 is not None and wo2 > max_tested_wO2 + EPS:
            B.append({"id": "B-EVID-O2-FRACTION", "kind": "evidence_gap",
                      "detail": f"the delivered O2 mass fraction {fmt(wo2)} exceeds the largest O2 mass fraction "
                                f"tested in any comparable item ({fmt(max_tested_wO2)})", "resolved_by": ["DM-2"]})
    elif scen:
        if sup and all(scen["SC-FS"]["per_item"][c["item"]]["coverage"] == DNR and
                       "O" in scen["SC-FS"]["per_item"][c["item"]].get("species_absent_from_evidence", [])
                       for c in sup):
            B.append({"id": "B-EVID-ATOMIC-O", "kind": "evidence_gap",
                      "detail": "no evidence item was tested with atomic O in the anode feed; under SC-FS (w_O "
                                f"{fmt(scen['SC-FS']['w']['O'])}) every item DOES_NOT_REACH on composition",
                      "resolved_by": ["DM-1", "DM-2"]})
        wo2 = scen["SC-REC"]["w"]["O2"]
        if max_tested_wO2 is not None and wo2 > max_tested_wO2 + EPS:
            B.append({"id": "B-EVID-O2-FRACTION", "kind": "evidence_gap",
                      "detail": f"even with complete O recombination (SC-REC) the O2 mass fraction {fmt(wo2)} exceeds "
                                f"the largest O2 mass fraction tested in any comparable item ({fmt(max_tested_wO2)})",
                      "resolved_by": ["DM-2"]})
    nc = []
    for c in comps:
        if not c["status_bearing"] or c["role"] not in ("support_air_only", "extinction", "support_xe_admixture"):
            continue
        m = [f"{a} ({c['axes'][a]['missing']})" for a in REQUIRED_AXES if c["axes"][a]["coverage"] == NC]
        if m:
            nc.append(f"{c['item']}: " + "; ".join(m))
    if nc:
        B.append({"id": "B-EVID-NOT-COMPARABLE", "kind": "evidence_not_comparable",
                  "detail": "status-bearing items lacking a quantity needed on a required axis: " + " | ".join(nc),
                  "resolved_by": ["DM-5", "DM-2"]})
    conds = sorted({x for c in comps if c["status_bearing"] for x in regs[c["item"]].get("conditional_on", [])})
    if conds:
        B.append({"id": "B-EVID-INTERPRETATION", "kind": "interpretation",
                  "detail": "; ".join(f"{k}: {CONDITIONS[k]}" for k in conds), "resolved_by": ["DM-5", "DM-2"]})
    lv = sorted(c["item"] for c in comps if not c["status_bearing"] and c["role"] == "support_air_only")
    if lv:
        B.append({"id": "B-EVID-LEVEL", "kind": "evidence_level",
                  "detail": "second-hand / abstract-level items (evidence level 5) are corroborating only: "
                            + ", ".join(lv), "resolved_by": ["DM-5"]})
    return B


def decide(comps):
    sup = sorted(c["item"] for c in comps if c["verdict"] == "supports")
    con = sorted(c["item"] for c in comps if c["verdict"] == "contradicts")
    if sup and not con:
        return S_SUP, sup, con
    if con and not sup:
        return S_CON, sup, con
    return S_UND, sup, con


def ignition_block(comps, regs, sust_status, blockers):
    by = {c["item"]: c for c in comps}
    base_blk = [b["id"] for b in blockers]

    def assess(items, need_primary=True):
        ok = [i for i in items if by.get(i) and by[i]["verdict"] == "supports" and
              (regs[i]["ignition"]["basis"] == "primary" or not need_primary)]
        return ok

    xs_items = sorted(i for i, r in regs.items() if r["role"] == "support_air_only"
                      and r["ignition"]["mode"] == "xenon_start_then_transition")
    xc_items = sorted(i for i, r in regs.items() if r["role"] in ("support_air_only", "extinction")
                      and r["ignition"]["mode"] == "direct_on_atmospheric_gas"
                      and (r.get("cathode_gas") or {}).get("gas") in ("Xe", None))
    ao_items = sorted(i for i, r in regs.items() if r["role"] in ("support_air_only", "extinction")
                      and r["ignition"]["mode"] == "direct_on_atmospheric_gas"
                      and (r.get("cathode_gas") or {}).get("gas") not in ("Xe", None))
    xs_ok = assess(xs_items)
    xc_ok = assess(xc_items)
    xs = {"mode": "xenon on the anode at ignition, then transition to the atmospheric feed",
          "evidence_items": xs_items,
          "status": I_SUP if xs_ok else S_UND, "supporting_items": xs_ok,
          "blockers": [] if xs_ok else base_blk + ["B-IGN-XE-START-COVERAGE"],
          "note": "within the RFP propellant set (air + Xe); the Xe used per start is not reported as a structured "
                  "quantity in the matrix (TBD - requires DM-4)"}
    xc_notes = [f"{i} ignition basis {regs[i]['ignition']['basis']}, cathode "
                f"{regs[i]['cathode_gas']['gas'] or 'not reported / not accessed'}" for i in xc_items]
    xc = {"mode": "atmospheric gas on the anode at ignition with a xenon cathode",
          "evidence_items": xc_items,
          "status": I_SUP if xc_ok else S_UND, "supporting_items": xc_ok,
          "blockers": [] if xc_ok else base_blk + ["B-IGN-XC-BASIS"],
          "note": "; ".join(xc_notes) + ("; none is a primary-basis ignition statement" if not any(
              regs[i]["ignition"]["basis"] == "primary" for i in xc_items) else "")}
    ao_cath = sorted({regs[i]["cathode_gas"]["gas"] for i in ao_items})
    ao = {"mode": "no xenon anywhere at ignition (anode and cathode on non-Xe gas)",
          "evidence_items": ao_items,
          "status": S_UND, "supporting_items": [],
          "blockers": base_blk + ["B-IGN-AIR-NO-EVIDENCE"],
          "note": f"the only xenon-free direct ignitions ({', '.join(ao_items)}) used a pure-N2 anode and a cathode "
                  f"on {'/'.join(ao_cath)}"
                  + ("; Ar is outside the RFP propellant set (air + Xe)" if "Ar" in ao_cath else "")
                  + "; no item ignites with an atmospheric-gas cathode or an O-containing anode feed"}
    return {"xenon_assisted": {"xe_anode_start": xs, "xe_cathode_direct": xc}, "air_only": ao,
            "no_published_ignition_threshold": True,
            "sustainment_status_of_case": sust_status}


# ---------------------------------------------------------------------------------------------------- build
def build(found, design_point=None, feed_override=None, feed_override_meta=None):
    matrix = load_json(found["hall_sustainment_matrix"])
    feed = feed_override if feed_override is not None else load_json(found["feed_envelope"])
    p5 = load_json(found["p5_case_geometry"])
    K = load_constants(found["constants_module"])
    check_claude_md()
    M = K.M_SPECIES
    RFP = K.RFP
    T_max_N = RFP.thrust_max_mN * 1e-3
    P_max_kW = RFP.power_max_W * 1e-3
    dp = design_point if design_point is not None else default_design_point()
    dv = design_values(dp)

    ids = [e["id"] for e in matrix["entries"]]
    if sorted(ids) != sorted(EXTRACT):
        raise OverlayInputError(f"matrix entries {ids} differ from the extraction map {sorted(EXTRACT)}")
    if matrix["id"] != "hall_sustainment_matrix_v1":
        raise OverlayInputError(f"unexpected matrix id {matrix['id']}")
    if feed.get("architectures", {}).get("ids") != ARCH_IDS:
        raise OverlayInputError("feed envelope architecture ids differ from hall_only / rf_hall / ecr_hall")

    entries = {e["id"]: e for e in matrix["entries"]}
    regs = {i: evidence_region(entries[i], EXTRACT[i], p5, M, P_max_kW) for i in sorted(EXTRACT)}
    rfp = {
        "thrust_max": qrec(RFP.thrust_max_mN, "mN", "assumed",
                           "abep_sim/constants.py RFPConstraints.thrust_max_mN ('Hard limits from Part III Para 2 of the "
                           "RFP'); CLAUDE.md RFP envelope", quantity_kind="requirement (RFP), not a physical measurement"),
        "thrust_min": qrec(RFP.thrust_min_mN, "mN", "assumed", "abep_sim/constants.py RFPConstraints.thrust_min_mN",
                           quantity_kind="requirement (RFP), not a physical measurement"),
        "power_max": qrec(P_max_kW, "kW", "assumed", "abep_sim/constants.py RFPConstraints.power_max_W (RFP total-power "
                          "ceiling)", quantity_kind="requirement (RFP), total power; discharge share TBD"),
        "firing_time_min": qrec(RFP.ignition_hours, "h", "assumed", "abep_sim/constants.py "
                                "RFPConstraints.ignition_hours (RFP firing time)", quantity_kind="requirement (RFP)"),
        "propellants": {"value": CLAUDE_MD_PROPELLANT_TOKEN, "source": "CLAUDE.md RFP envelope",
                        "quantity_kind": "requirement (RFP)"},
    }

    # ------------------------------------------------------------------ max O2 fraction tested (comparable support items)
    tested_wO2 = sorted({(regs[i]["composition"]["w"] or {}).get("O2", 0.0) for i in regs
                         if regs[i]["role"] == "support_air_only" and regs[i]["composition"]["comparable"]})
    max_tested_wO2 = max(tested_wO2) if tested_wO2 else None
    brackets = {}
    for i, r in regs.items():
        if r["role"] != "support_air_only" or not r["status_bearing"] or not r["composition"]["comparable"]:
            continue
        w = r["composition"]["w"].get("O2", 0.0)
        lo, hi, items = brackets.get(r["device"], (w, w, []))
        brackets[r["device"]] = (min(lo, w), max(hi, w), sorted(items + [i]))
    brackets = {d: {"w_O2_range": [g6(v[0]), g6(v[1])], "items": v[2]} for d, v in sorted(brackets.items())
                if v[1] > v[0]}

    # ------------------------------------------------------------------ air cases
    cases = []
    for idx, fc in enumerate(feed["cases"]):
        fs = fc["free_stream"]
        cs = air_case_state(fc, dv, T_max_N)
        scen = composition_scenarios(fs["w_s"]["values"],
                                     f"feed_envelope_v1 cases[{idx}].free_stream.w_s ({fs['w_s']['source']}); "
                                     f"scenario arithmetic by this overlay")
        comps = [compare(cs, regs[i]) for i in sorted(regs)
                 if regs[i]["role"] in ("support_air_only", "extinction")]
        for name, sc in scen.items():
            sc["per_item"] = {c["item"]: cover_composition(sc["w"], regs[c["item"]]) for c in comps}
            sc["covered_by"] = sorted(k for k, v in sc["per_item"].items() if v["coverage"] == COVERS)
        wo2_rec = scen["SC-REC"]["w"]["O2"]
        scen["SC-REC"]["within_device_bracket_if_PROPOSED_rule_adopted"] = sorted(
            d for d, b in brackets.items() if b["w_O2_range"][0] - EPS <= wo2_rec <= b["w_O2_range"][1] + EPS)
        rhoV, V = cs["rhoV"], cs["V"]
        src_fs = f"feed_envelope_v1 cases[{idx}].free_stream"
        thresholds = {}
        for c in comps:
            r = regs[c["item"]]
            t = {}
            src_t = f"{src_fs} and evidence_regions[{c['item']}]; definition: threshold_definitions"
            if r["flow"]["value"] is not None and r["role"] == "support_air_only":
                f = r["flow"]["value"]
                t["A_eff_required_m2"] = qrec([f[0] * 1e-6 / rhoV, f[1] * 1e-6 / rhoV], "m^2", "model-derived",
                                              src_t)
                t["same_size_flow_under_H_RAM"] = c["axes"]["anode_flow"].get("under_H_RAM")
            if r["flow_density"]["value"] is not None:
                g = r["flow_density"]["value"]
                fb = r["flow_density"].get("bound") == "lower"
                lab = "area_ratio_at_extinction" if r["role"] == "extinction" else "area_ratio_required"
                t[lab] = qrec(g[0] / rhoV, "1", "model-derived", src_t, bound=("lower" if fb else None),
                              conditional_on=r["flow_density"].get("conditional_on", []))
                if r["role"] == "support_air_only":
                    t["A_ch_max_under_H_RAM_m2"] = qrec(
                        (T_max_N / V) / g[0], "m^2", "model-derived", src_t, bound=("upper" if fb else None),
                        conditional_on=["H_RAM"] + r["flow_density"].get("conditional_on", []))
            if t:
                thresholds[c["item"]] = t
        blockers = case_blockers(cs, fc, comps, regs, max_tested_wO2, scen)
        status, sup, con = decide(comps)
        if status == S_UND and sup and con:
            blockers.append({"id": "B-EVID-CONFLICT", "kind": "evidence_conflict",
                             "detail": f"supporting {sup} and contradicting {con} items at comparable conditions",
                             "resolved_by": ["DM-2"]})
        if status == S_UND and not blockers:
            blockers.append({"id": "B-NO-COVERING-ITEM", "kind": "evidence_gap",
                             "detail": "no status-bearing item covers the case on every required axis",
                             "resolved_by": ["DM-2"]})
        case = {
            "case_id": fc["case_id"], "kind": "air", "alt_km": fc["alt_km"], "atmosphere_level": fc["atmosphere_level"],
            "averaging": fc["averaging"], "feed_envelope_status": fc["status"],
            "feed": {
                "mass_flux_kgpm2ps": feed_quantity_view(fs["mass_flux_kgpm2ps"], f"cases[{idx}].free_stream.mass_flux_kgpm2ps"),
                "V_mps": feed_quantity_view(fs["V_mps"], f"cases[{idx}].free_stream.V_mps"),
                "free_stream_w_s": feed_quantity_view(fs["w_s"], f"cases[{idx}].free_stream.w_s"),
                "mdot_anode_kgps": feed_quantity_view(fc["feed_state"]["mdot_total_kgps"],
                                                      f"cases[{idx}].feed_state.mdot_total_kgps"),
                "valve_outlet_w_s": feed_quantity_view(fc["feed_state"]["w_s"], f"cases[{idx}].feed_state.w_s"),
                "flow_density_kgpm2ps": ({"value": None, "status": "TBD",
                                          "requires": "TBD - requires the delivered anode flow (mdot_anode_kgps) and "
                                                      "the Vyovrinda channel cross-section (design point "
                                                      "channel_area_m2)"}
                                         if cs["mdot_kgps"] is None or cs["channel_area_m2"] is None else
                                         qrec(flow_density_range(cs["mdot_kgps"], cs["channel_area_m2"]),
                                              "kg m^-2 s^-1", "model-derived",
                                              "delivered mdot / design channel_area_m2",
                                              "[mdot_lo / A_hi, mdot_hi / A_lo]")),
                "composition_scenarios": scen,
            },
            "H_RAM_bound": {
                "mdot_air_max_kgps": qrec(T_max_N / V, "kg s^-1", "model-derived",
                                          f"this overlay: RFP thrust_max / {src_fs}.V_mps", "PROPOSED bound H_RAM",
                                          conditional_on=["H_RAM"]),
                "A_eff_max_m2": qrec(T_max_N / (V * rhoV), "m^2", "model-derived",
                                     f"this overlay: RFP thrust_max / ({src_fs}.V_mps x mass_flux_kgpm2ps)",
                                     "PROPOSED bound H_RAM", conditional_on=["H_RAM"]),
            },
            "thresholds": thresholds,
            "comparisons": comps,
            "status": status, "supporting_items": sup, "contradicting_items": con,
            "blockers": blockers,
            "decisive_measurement": {"id": "DM-2", "prerequisites": ["DI-1", "DI-2", "DM-1"],
                                     "at": "this case's delivered flow density and valve-outlet composition, at the "
                                           "design V_d, B and cathode gas",
                                     "not_stand_alone": "DM-2 needs the delivered feed (DI-1) and the design point "
                                                        "(DI-2), and DM-1 to set whether atomic O is part of the test "
                                                        "composition; a second composition point is part of DM-2 to "
                                                        "check the composition dependence"},
        }
        case["ignition"] = ignition_block(comps, regs, status, blockers)
        cases.append(case)

    # ------------------------------------------------------------------ listed feed variants
    xe = feed["xe_path"]
    variants = []
    vx = {"case_id": "variant_xe_path_IF-X2", "kind": "xe_path_variant", "feed_envelope_status": xe["status"],
          "feed": {k: feed_quantity_view(v, f"xe_path.feed_state.{k}") for k, v in xe["feed_state"].items()},
          "comparisons": [], "status": S_UND, "supporting_items": [], "contradicting_items": [],
          "blockers": [
              {"id": "B-XE-FEED", "kind": "feed_tbd", "detail": f"Xe path (IF-X2) status {xe['status']}",
               "requires": xe["feed_state"]["mdot_xe_anode_kgps"]["requires"], "resolved_by": ["DI-1"]},
              {"id": "B-SCOPE-XE", "kind": "out_of_scope",
               "detail": "the Hall sustainment matrix covers atmospheric gas only (E21 is xenon-only and not "
                         "informative); xenon-only Hall operation is not assessed by this overlay",
               "resolved_by": []}]}
    variants.append(vx)
    mx = feed["xe_path"]["mixed_air_xe_feed"]
    mstate = {"mdot_kgps": None, "w_valve": None, "mdot_max_H_RAM_kgps": None, **dv}
    mcomps = [compare(mstate, regs[i]) for i in sorted(regs)
              if regs[i]["role"] == "support_xe_admixture" or regs[i].get("extinction_kind") == "xe_fraction"]
    for c in mcomps:                                   # the mixed feed's TBD is one record in the feed envelope
        for ax in c["axes"].values():
            if "blocked_by" in ax:
                ax["blocked_by"] = sorted({"B-MIXED-FEED" if b in ("B-FEED-MDOT", "B-FEED-COMP") else b
                                           for b in ax["blocked_by"]})
    vm = {"case_id": "variant_mixed_air_xe", "kind": "mixed_air_xe_variant", "feed_envelope_status": mx["status"],
          "feed": {"mixed_air_xe_feed": {"value": None, "status": mx["status"], "requires": mx["requires"],
                                         "source": "feed_envelope_v1 xe_path.mixed_air_xe_feed"}},
          "xe_fraction_evidence": {i: dict((regs[i]["composition"].get("xe_fraction")
                                            or regs[i]["composition"]["xe_fraction_lowest_sustained"]),
                                           item_role=regs[i]["role"])
                                   for i in sorted(regs)
                                   if (regs[i].get("composition") or {}).get("xe_fraction")
                                   or (regs[i].get("composition") or {}).get("xe_fraction_lowest_sustained")},
          "comparisons": mcomps, "status": S_UND, "supporting_items": [], "contradicting_items": [],
          "blockers": [{"id": "B-MIXED-FEED", "kind": "feed_tbd", "detail": "mixed air + Xe feed is TBD in the feed "
                        "envelope", "requires": mx["requires"], "resolved_by": ["DI-1"]}]
          + [b for b in case_blockers(mstate, None, mcomps, regs, None, None) if b["id"] != "B-FEED-MDOT"]}
    variants.append(vm)

    findings = make_findings(cases, regs, rfp, T_max_N, max_tested_wO2, brackets)
    doc = assemble(found, feed, matrix, regs, rfp, cases + variants, findings, dp, max_tested_wO2, brackets)
    if feed_override is not None:                   # a design evaluation: record the feed actually used
        doc["inputs"]["feed_envelope"] = dict(feed_override_meta or {"path": "(in-memory override)", "sha256": None},
                                              lane="design evaluation (unpinned)", branch=None, commit=None,
                                              role="design-evaluated feed envelope supplied with --feed-envelope "
                                                   "(unpinned); not the committed lane-16 envelope")
    return doc


def make_findings(cases, regs, rfp, T_max_N, max_tested_wO2, brackets):
    air = [c for c in cases if c["kind"] == "air"]
    rv = {c["case_id"]: c["feed"]["mass_flux_kgpm2ps"]["value"] for c in air}
    mm = [c["H_RAM_bound"]["mdot_air_max_kgps"]["value"] for c in air]
    above = sorted(i for i, r in regs.items() if r["role"] == "support_air_only" and r["flow"].get("value")
                   and r["flow"]["value"][0] * 1e-6 > max(mm))
    gam = {i: r["flow_density"]["value"] for i, r in regs.items()
           if r["role"] in ("support_air_only", "extinction", "support_xe_admixture")
           and r["flow_density"].get("value")}
    by_alt = {}
    for c in air:
        by_alt.setdefault(c["alt_km"], []).append(rv[c["case_id"]])
    span_alt = {f"{int(a)} km": g6(max(v) / min(v)) for a, v in sorted(by_alt.items())}
    span_all = g6(max(rv.values()) / min(rv.values()))
    dem = {i: g6(r["flow"]["value"][1] / r["flow"]["value"][0]) for i, r in regs.items()
           if r["role"] == "support_air_only" and r["flow"].get("value")}
    wO = {c["case_id"]: c["feed"]["composition_scenarios"]["SC-FS"]["w"]["O"] for c in air}
    wO2r = {c["case_id"]: c["feed"]["composition_scenarios"]["SC-REC"]["w"]["O2"] for c in air}
    over = sorted(k for k, v in wO2r.items() if max_tested_wO2 is not None and v > max_tested_wO2 + EPS)
    power = {}
    for i, r in regs.items():
        if r.get("discharge_power", {}).get("value") and r["role"] in ("support_air_only", "extinction"):
            power.setdefault(r["discharge_power"]["rfp_total_power_relation"], []).append(i)
    xfree = sorted(i for i, r in regs.items() if r["role"] == "support_air_only" and not r["xenon_in_anode_flow"]
                   and (r.get("cathode_gas") or {}).get("gas") not in ("Xe", None))
    xfree_txt = "; ".join(
        f"{i} ({regs[i]['device']}: {regs[i]['cathode_gas']['gas']} cathode, "
        f"{regs[i]['cathode_gas']['rfp_propellant_relation_text']}; ignition {regs[i]['ignition']['mode']})"
        for i in xfree)
    durations = {i: r["duration"]["value"] for i, r in regs.items() if r.get("duration")}
    dur_limit = sorted(i for i, r in regs.items() if r["role"] == "duration_limit" and r.get("duration"))
    sup_g = sorted(i for i in gam if regs[i]["role"] == "support_air_only")
    sup_no_g = sorted(i for i, r in regs.items() if r["role"] == "support_air_only" and i not in gam)
    bracket_cases = {}
    for c in air:
        for d in c["feed"]["composition_scenarios"]["SC-REC"]["within_device_bracket_if_PROPOSED_rule_adopted"]:
            bracket_cases.setdefault(d, []).append(c["case_id"])
    statuses = {}
    for c in cases:
        statuses[c["status"]] = statuses.get(c["status"], 0) + 1
    harsh = min(rv, key=rv.get)
    richO = max(wO, key=wO.get)
    richO2 = max(wO2r, key=wO2r.get)
    with_O = sorted(i for i, r in regs.items() if "O" in ((r.get("composition") or {}).get("species_present") or []))
    all_und = set(statuses) == {S_UND}
    tbd_feed = all(c["feed"]["mdot_anode_kgps"]["value"] is None for c in air)
    return [
        {"id": "F-1", "topic": "status",
         "statement": (f"Every air case is {S_UND} (status counts {statuses})." if all_und else
                       f"Air-case status counts: {statuses}.")
                      + (" The valve-outlet feed (anode flow, composition) is TBD in the feed envelope and the Vyovrinda "
                         "design point (channel cross-section, V_d, B, cathode gas) is TBD, so no evidence item can be "
                         "placed on a case; feed TBDs propagate, none is filled in." if tbd_feed else ""),
         "values": {"status_counts": statuses}, "evidence_class": None,
         "source": "this overlay: counts of cases[*].status (not a physical quantity)"},
        {"id": "F-2", "topic": "same-size flow under the PROPOSED bound H_RAM",
         "statement": f"Under H_RAM the delivered air flow is at most {fmt([min(mm) * 1e6, max(mm) * 1e6])} mg/s "
                      f"(RFP thrust ceiling / orbital speed). The demonstrated flows of {', '.join(above)} lie wholly "
                      f"above it, so those devices' conditions are not reachable at their own size; under S1 a smaller "
                      f"channel can still reach their flow density (thresholds A_ch_max_under_H_RAM_m2 per case).",
         "values": {"mdot_air_max_mg_s": [g6(min(mm) * 1e6), g6(max(mm) * 1e6)], "items_above": above},
         "evidence_class": "model-derived", "conditional_on": ["H_RAM"],
         "source": "this overlay: rfp_context.thrust_max / cases[*].feed.V_mps; evidence_regions[*].flow"},
        {"id": "F-3", "topic": "flow density (S1) comparability",
         "statement": "A flow per channel cross-section can be formed only for "
                      + ", ".join(f"{i} ({regs[i]['device']}, {fmt(gam[i][0])}"
                                  + (f"-{fmt(gam[i][1])}" if gam[i][1] != gam[i][0] else "")
                                  + " kg m^-2 s^-1" + (", lower bound" if regs[i]['flow_density'].get('bound') else "")
                                  + ")" for i in sorted(gam))
                      + ". Among the air-only supporting items only "
                      + ", ".join(f"{i} ({regs[i]['device']}, {', '.join(regs[i]['composition']['species_present'])})"
                                  for i in sup_g)
                      + " qualify; " + ", ".join(f"{i} ({regs[i]['device']})" for i in sup_no_g)
                      + " lack the flow or channel dimensions in the accessed record.",
         "values": {"flow_density_by_item": {i: gam[i] for i in sorted(gam)}, "air_only_support_with_gamma": sup_g,
                    "air_only_support_without_gamma": sup_no_g}, "evidence_class": "inferred",
         "source": "evidence_regions[*].flow_density (matrix flows and channel geometry; P5 radii from the repository "
                   "case file)"},
        {"id": "F-4", "topic": "composition",
         "statement": (f"Items tested with atomic O in the anode feed: {', '.join(with_O) or 'none'}. The free-stream "
                       f"(SC-FS) atomic-O mass fraction is {fmt([min(wO.values()), max(wO.values())])} across the "
                       f"cases (highest at {richO}). ")
                      +
                      f"With complete recombination (SC-REC) the O2 mass fraction is "
                      f"{fmt([min(wO2r.values()), max(wO2r.values())])} (highest at {richO2}); the largest O2 mass "
                      f"fraction tested in a comparable item is {fmt(max_tested_wO2)}, exceeded at "
                      f"{', '.join(over) if over else 'no case'}. Under the PROPOSED bracketing rule (not adopted) "
                      + ("; ".join(f"the {d} pair {', '.join(brackets[d]['items'])} (w_O2 "
                                   f"{fmt(brackets[d]['w_O2_range'])}) would bracket SC-REC at "
                                   f"{', '.join(bracket_cases.get(d, [])) or 'no case'}" for d in sorted(brackets))
                         or "no device brackets any case") + ".",
         "values": {"SC_FS_w_O": [min(wO.values()), max(wO.values())], "SC_REC_w_O2": [min(wO2r.values()),
                                                                                       max(wO2r.values())],
                    "max_tested_w_O2": max_tested_wO2, "cases_above_max_tested_w_O2": over,
                    "device_brackets": brackets, "cases_within_device_bracket": bracket_cases,
                    "most_atomic_O_case_SC_FS": richO, "most_O2_case_SC_REC": richO2},
         "evidence_class": "model-derived",
         "source": "cases[*].feed.composition_scenarios (frozen NRLMSIS 2.1 free stream) and "
                   "evidence_regions[*].composition"},
        {"id": "F-5", "topic": "flow span one fixed design must sustain",
         "statement": f"The free-stream mass flux rho V spans "
                      + ", ".join(f"x{fmt(v, 3)} at {k}" for k, v in span_alt.items())
                      + f" across solar levels and x{fmt(span_all, 3)} over all cases (lowest at {harsh}). For a fixed "
                      f"design these are the delivered-flow ratios only under S4 (A_eff the same at every case; feed "
                      f"envelope relation mdot = A_eff rho V); the feed envelope records (FE-08) that eta_c, one factor "
                      f"of A_eff, depends on the speed ratio, which changes across the cases, so the delivered-flow "
                      f"span can differ from these ratios. The widest flow span demonstrated within one air-only "
                      f"supporting item is x{fmt(max(dem.values()), 3)} ({max(dem, key=dem.get)}); demonstrated spans "
                      f"are what was tested, not device limits.",
         "values": {"required_span_by_altitude": span_alt, "required_span_all_cases": span_all,
                    "demonstrated_span_by_item": dem, "harshest_flow_case": harsh},
         "span_basis": "free-stream mass-flux ratio; equals the delivered-flow ratio only under S4",
         "conditional_on": ["S4"],
         "evidence_class": "model-derived", "demonstrated_span_evidence_class": "inferred",
         "source": "this overlay: ratios of cases[*].feed.mass_flux_kgpm2ps (model-derived) and of evidence_regions"
                   "[*].flow (measured) values"},
        {"id": "F-6", "topic": "power (same-size transfer)",
         "statement": "Relative to the RFP total-power ceiling "
                      f"({fmt(rfp['power_max']['value'])} kW): "
                      + "; ".join(f"{k}: {', '.join(sorted(v))}" for k, v in sorted(power.items()))
                      + ". Discharge power alone above the total ceiling means the item's own operating point cannot "
                        "be reproduced at its size within the RFP; under S1 the channel (and power) can be smaller.",
         "values": {k: sorted(v) for k, v in sorted(power.items())}},
        {"id": "F-7", "topic": "xenon-free operation and cathode gas",
         "statement": f"Air-only supporting items with no Xe on either electrode in steady state: {xfree_txt}. Every "
                      f"other air-only supporting item used a Xe cathode or did not report its cathode gas.",
         "values": {"xenon_free_items": xfree,
                    "cathode_rfp_propellant_relation": {i: regs[i]["cathode_gas"]["rfp_propellant_relation"]
                                                        for i in xfree}}},
        {"id": "F-8", "topic": "duration",
         "statement": "Demonstrated durations on atmospheric feeds: "
                      + ", ".join(f"{i} {fmt(v)} h" for i, v in sorted(durations.items()))
                      + f", against the RFP firing time > {fmt(rfp['firing_time_min']['value'])} h. "
                      + " ".join(f"{i} (level {regs[i]['evidence_level']}): {regs[i]['reason']}." for i in dur_limit),
         "values": durations, "evidence_class": "measured",
         "source": "evidence_regions[*].duration (matrix quantities; E07 second-hand, level 5)"},
        transfer_reach_finding(regs),
    ]


def transfer_reach_finding(regs):
    """F-9: can any O2- or O-containing (air) feed be covered by literature transfer with the current evidence?"""
    sup = {i: r for i, r in regs.items() if r["role"] == "support_air_only" and r["status_bearing"]}
    with_gamma = sorted(i for i, r in sup.items() if r["flow_density"].get("value") is not None)
    tested_o2 = sorted(i for i, r in regs.items() if r["role"] == "support_air_only" and r["composition"]["comparable"]
                       and "O2" in r["composition"]["species_present"])
    tested_o = sorted(i for i, r in regs.items() if "O" in ((r.get("composition") or {}).get("species_present") or []))
    # an item could cover an O2-containing feed on every required axis only if it has all of these
    full = sorted(i for i in tested_o2 if i in sup and regs[i]["flow_density"].get("value") is not None
                  and regs[i]["discharge_voltage"].get("value") is not None
                  and regs[i]["magnetic_field"].get("value") is not None and regs[i]["cathode_gas"].get("gas"))
    gamma_species = {i: regs[i]["composition"]["species_present"] for i in with_gamma}
    o2_missing = {i: [a for a, k in (("flow density", "flow_density"), ("B", "magnetic_field"),
                                     ("V_d", "discharge_voltage")) if regs[i][k].get("value") is None]
                  for i in tested_o2}
    o2_level = {i: ("" if i in sup else f"; evidence level {regs[i]['evidence_level']}, not status-bearing")
                for i in tested_o2}
    reach = bool(full)
    stmt = (f"Under strict composition containment (no tolerance or bracketing rule adopted) a delivered feed that "
            f"contains O2 or O can be covered on composition only by an item tested on O2 / O. The status-bearing "
            f"air-only items with a flow per channel cross-section are "
            + ", ".join(f"{i} ({regs[i]['device']}, {'+'.join(gamma_species[i])})" for i in with_gamma)
            + "; the items tested with O2 are "
            + ", ".join(f"{i} ({regs[i]['device']}: lacks {', '.join(o2_missing[i]) or 'no required quantity'}"
                        f"{o2_level[i]})" for i in tested_o2)
            + f"; items tested with atomic O: {', '.join(tested_o) or 'none'}. ")
    if not reach:
        stmt += ("Hence, with the current evidence, no air case (SC-FS, SC-REC or any O2- or O-containing delivered "
                 "composition) can become SUSTAINMENT_SUPPORTED by literature transfer, even after DI-1 and DI-2 are "
                 "supplied: the section-4 thresholds (area_ratio_required, A_ch_max_under_H_RAM_m2) exist only for "
                 "pure-N2 items. What can change that: DM-2 (hardware on the delivered composition), or an "
                 "owner-adopted composition tolerance or bracketing rule, which reaches an O2-containing feed only "
                 "through a pure-N2 item within the tolerance or through an O2-tested item once DM-5 supplies its "
                 "channel dimensions and B."
                 + (" No tested composition contains atomic O, so a feed that keeps atomic O needs DM-2 unless the "
                    "tolerance admits trace atomic O." if not tested_o else ""))
    else:
        stmt += (f"Items that could cover an O2-containing feed on every required axis: {', '.join(full)}.")
    return {"id": "F-9", "topic": "reach of literature transfer for air feeds",
            "statement": stmt,
            "values": {"air_only_items_with_flow_density": with_gamma, "items_tested_with_O2": tested_o2,
                       "items_tested_with_atomic_O": tested_o, "O2_items_missing": o2_missing,
                       "O2_items_complete_on_required_axes": full,
                       "air_case_supportable_by_literature_transfer": reach},
            "evidence_class": None,
            "source": "this overlay: evidence_regions[*] (flow_density, composition, magnetic_field, discharge_voltage) "
                      "and the strict containment rule (definitions.directions); a logical consequence, not a physical "
                      "quantity"}


def milestone_conditions(findings, regs, cases, rfp):
    f = {x["id"]: x for x in findings}
    xs = sorted(i for i, r in regs.items() if r["role"] == "support_air_only"
                and r["ignition"]["mode"] == "xenon_start_then_transition")
    air = [c for c in cases if c["kind"] == "air"]
    n = len(air)
    tbd = [c for c in air if c["feed"]["mdot_anode_kgps"]["value"] is None
           or c["feed"]["valve_outlet_w_s"]["value"] is None
           or any(v is None for v in (c["feed"]["valve_outlet_w_s"]["value"] or {}).values())]
    st = {}
    for c in air:
        st.setdefault(c["status"], []).append(c["case_id"])
    if set(st) == {S_SUP}:
        sust = "MET BY LITERATURE TRANSFER at every case (S1-S3 stated; DM-2 still needed for milestone B)"
    elif S_CON in st:
        sust = f"CONTRADICTED at {len(st[S_CON])} of {n} cases: {', '.join(st[S_CON])}"
    else:
        sust = f"UNDETERMINED at {len(st.get(S_UND, []))} of {n} cases"
    xs_ok = [c["case_id"] for c in air if c["ignition"]["xenon_assisted"]["xe_anode_start"]["status"] == I_SUP]
    dur = f["F-8"]["values"]
    longest = max(dur.values()) if dur else None
    firing = rfp["firing_time_min"]["value"]
    return [
        {"id": "HS-A1", "condition": "the delivered feed (anode mass flow and valve-outlet composition at IF-A5) is "
                                     "evaluated for every case of the declared mission envelope",
         "state": (f"NOT_MET: TBD at {len(tbd)} of {n} cases (feed envelope case status "
                   f"{', '.join(sorted({c['feed_envelope_status'] for c in tbd}))})" if tbd else
                   "MET for the supplied feed"), "resolved_by": ["DI-1"]},
        {"id": "HS-A2", "condition": "at every declared case the delivered anode flow density is at or above the "
                                     "extinction boundary of the Vyovrinda channel measured at the design point "
                                     "(DM-2) with a margin (PROPOSED, owner: none adopted); pending DM-2, at or above "
                                     "the lowest demonstrated flow density of a status-bearing sustained item that "
                                     "COVERS the case on every required axis (S1-S3 stated)",
         "state": sust, "thresholds": "cases[*].thresholds (area_ratio_required, A_ch_max_under_H_RAM_m2)",
         "note": ("with the current evidence no air case can be covered by literature transfer (F-9): only DM-2, or "
                  "DM-5 with an owner-adopted composition tolerance, can change that"
                  if not f["F-9"]["values"]["air_case_supportable_by_literature_transfer"] else "see F-9"),
         "resolved_by": ["DI-1", "DI-2", "DM-2"]},
        {"id": "HS-A3", "condition": "the delivered composition lies within the composition tested by the evidence "
                                     "used: atomic O shown negligible at the valve outlet (DM-1) or tested (DM-2), and "
                                     "the O2 fraction within the tested range",
         "state": sust, "values": f["F-4"]["values"], "resolved_by": ["DM-1", "DM-2"]},
        {"id": "HS-A4", "condition": "the design V_d, B and cathode gas lie inside the demonstrated window of that "
                                     "evidence (cathode gas within the RFP propellant set air + Xe; a pure-N2 cathode "
                                     "only with a separate N2 supply or N2 separation from the air path)",
         "state": sust, "resolved_by": ["DI-2", "DM-2"]},
        {"id": "HS-A5", "condition": "the design sustains over the delivered flow span of the declared envelope, or the "
                                     "envelope is restricted, or chamber buffering is specified (not in the feed "
                                     "envelope: TBD)",
         "state": "UNDETERMINED (free-stream mass-flux span x" + fmt(f["F-5"]["values"]["required_span_all_cases"], 3)
                  + " over all cases, the delivered-flow span only under S4, vs widest demonstrated x"
                  + fmt(max(f["F-5"]["values"]["demonstrated_span_by_item"].values()), 3) + ")",
         "values": f["F-5"]["values"], "conditional_on": ["S4"], "resolved_by": ["DI-1", "DM-2"]},
        {"id": "HS-A6", "condition": f"a start method: xenon-assisted start (precedent {', '.join(xs)}; within the RFP "
                                     "propellant set) with its Xe per start inside the Xe budget, or an air-only "
                                     "ignition demonstrated on the delivered composition (no precedent)",
         "state": (f"xenon-assisted start covered at {len(xs_ok)} of {n} cases; Xe per start TBD" if xs_ok else
                   f"UNDETERMINED at {n} of {n} cases"), "resolved_by": ["DM-3", "DM-4"]},
        {"id": "HS-A7", "condition": "(milestone C, listed for completeness) sustained operation without flame-out "
                                     "over the firing time on an O-containing feed",
         "state": (f"NOT_DEMONSTRATED (longest recorded duration {fmt(longest)} h < RFP firing time {fmt(firing)} h)"
                   if longest is None or longest < firing else "see F-8"),
         "values": f["F-8"]["values"], "resolved_by": ["DM-6"]},
    ]


DECISIVE = [
    {"id": "DI-1", "type": "design_input", "what": "a documented feed design baseline with provenance (feed envelope "
     "design_input_contract) evaluated with build_feed_envelope.py --design-inputs, giving the delivered anode flow "
     "and valve-outlet composition per case", "resolves": ["B-FEED-MDOT", "B-FEED-COMP", "B-XE-FEED", "B-MIXED-FEED"]},
    {"id": "DI-2", "type": "design_input", "what": "the Vyovrinda Hall design point with provenance: channel "
     "cross-section, discharge voltage, B (value and definition), cathode gas, discharge-power allocation",
     "resolves": ["B-DESIGN-ACH", "B-DESIGN-VD", "B-DESIGN-B", "B-DESIGN-CATHODE", "B-DESIGN-POWER"]},
    {"id": "DM-1", "type": "upstream_component_measurement", "what": "atomic-O fraction and O2/N2 ratio at the "
     "valve outlet of a representative intake / compressor / gas-chamber assembly (or the O wall-recombination "
     "probability of the chamber material at its temperature, for the feed chain). Upstream data; no Hall-closure "
     "quantity enters it", "resolves": ["B-FEED-COMP", "B-EVID-ATOMIC-O"]},
    {"id": "DM-2", "type": "hardware_measurement", "what": "flow-down extinction scan on a Vyovrinda-representative "
     "channel at the design V_d, B and cathode gas, on the delivered composition (the most O-rich declared case; with "
     "atomic O if DM-1 shows it survives): lower the anode flow at fixed V_d and B until extinction; record the "
     "extinction flow density, I_d oscillation, facility background pressure and ingested flow. One scan gives the "
     "boundary for that design; with DI-1 each air case can then be placed against it on the same device, without the "
     "cross-device assumptions S1/S2 (the facility-to-orbit transfer and the composition dependence still have to be "
     "stated). A second composition point (the least O-rich case) checks that the boundary does not move the other "
     "way with composition",
     "prerequisites": ["DI-1", "DI-2", "DM-1"],
     "resolves": ["B-EVID-ATOMIC-O", "B-EVID-O2-FRACTION", "B-EVID-NOT-COMPARABLE", "B-EVID-INTERPRETATION",
                  "B-EVID-CONFLICT", "B-NO-COVERING-ITEM", "B-IGN-XE-START-COVERAGE"]},
    {"id": "DM-3", "type": "hardware_measurement", "what": "air-only ignition attempt: atmospheric-gas anode on the "
     "delivered composition, non-Xe cathode (if the cathode lane admits one), design V_d and B, at the lowest declared "
     "flow density; record success / failure and the start conditions",
     "resolves": ["B-IGN-AIR-NO-EVIDENCE"]},
    {"id": "DM-4", "type": "hardware_measurement", "what": "xenon-assisted start and transition to the delivered "
     "composition at the lowest declared flow density; record the Xe mass used per start (Xe budget)",
     "resolves": ["B-IGN-XE-START-COVERAGE", "B-IGN-XC-BASIS"]},
    {"id": "DM-5", "type": "desk_extraction", "what": "published-source extraction only (no contact): PPS1350 and "
     "HT5k channel dimensions and B from accessible primaries; digitization of MOSKOVITZ2026 Fig. 6 (E11 boundary); "
     "the ECHT OD reading; per-point (flow, V_d, B) data for joint-point checks (S3); the P5 N2 window edge (E02) "
     "where a primary gives more than the text statement; access to the level-5 primaries (verify)",
     "resolves": ["B-EVID-NOT-COMPARABLE", "B-EVID-INTERPRETATION", "B-EVID-LEVEL"]},
    {"id": "DM-6", "type": "hardware_measurement", "what": "(milestone C) endurance on an O-containing feed with "
     "anode-oxidation mitigation (E07 flame-outs); thermal/life lane abep_sim/thermal_life.py and "
     "docs/evidence/wall_life/", "resolves": []},
]

THRESHOLD_DEFINITIONS = {
    "A_eff_required_m2": "item flow / case rho V: the effective capture area A_eff at which the case's delivered anode "
                         "flow equals the item's demonstrated flow range (same-size reading, no scaling)",
    "same_size_flow_under_H_RAM": "DOES_NOT_REACH when the item's lowest demonstrated flow exceeds the H_RAM bound on "
                                  "the delivered air flow (PROPOSED bound); NOT_EXCLUDED otherwise",
    "area_ratio_required": "item lowest flow density / case rho V: the A_eff / A_ch at which the case's delivered flow "
                           "density equals the item's lowest demonstrated flow density (S1); 'lower' bound when the "
                           "item's flow density is a lower bound",
    "area_ratio_at_extinction": "item extinction flow density / case rho V: the case is at or below the item's "
                                "extinction flow density when A_eff / A_ch is at or below this value (S1)",
    "A_ch_max_under_H_RAM_m2": "(RFP thrust_max / V) / item lowest flow density: the largest channel cross-section at "
                               "which the case can reach the item's lowest demonstrated flow density with the air flow "
                               "at the H_RAM bound (PROPOSED); 'upper' bound when the item's flow density is a lower "
                               "bound",
}

BLOCKER_CATALOGUE = {
    "B-FEED-MDOT": "delivered anode mass flow TBD (feed envelope)",
    "B-FEED-COMP": "valve-outlet composition TBD (feed envelope)",
    "B-DESIGN-ACH": "Vyovrinda channel cross-section TBD",
    "B-DESIGN-VD": "Vyovrinda discharge voltage TBD",
    "B-DESIGN-B": "Vyovrinda magnetic field (value, definition) TBD",
    "B-DESIGN-CATHODE": "Vyovrinda cathode gas TBD",
    "B-DESIGN-POWER": "discharge-power allocation TBD (informational axis)",
    "B-EVID-ATOMIC-O": "no evidence item tested with atomic O in the anode feed",
    "B-EVID-O2-FRACTION": "O2 fraction beyond any tested composition even with complete O recombination",
    "B-EVID-NOT-COMPARABLE": "status-bearing items lack a quantity on a required axis",
    "B-EVID-INTERPRETATION": "an evidence value depends on an unresolved reading",
    "B-EVID-LEVEL": "level-5 items are corroborating only",
    "B-EVID-CONFLICT": "supporting and contradicting items at comparable conditions",
    "B-NO-COVERING-ITEM": "no status-bearing item covers the case on every required axis",
    "B-XE-FEED": "Xe path (IF-X2) TBD",
    "B-SCOPE-XE": "xenon-only operation outside the matrix scope",
    "B-MIXED-FEED": "mixed air + Xe feed TBD",
    "B-IGN-XE-START-COVERAGE": "no xenon-start item covers the case after its transition",
    "B-IGN-XC-BASIS": "no primary-basis statement of direct atmospheric ignition with a Xe cathode",
    "B-IGN-AIR-NO-EVIDENCE": "no item ignites with no xenon anywhere on an RFP propellant",
}


def assemble(found, feed, matrix, regs, rfp, cases, findings, dp, max_tested_wO2, brackets):
    inputs = {k: {kk: v[kk] for kk in ("path", "sha256", "lane", "branch", "commit", "role")} for k, v in INPUTS.items()}
    return {
        "id": OVERLAY_ID, "overlay": "hall_sustainment_envelope", "version": OVERLAY_VERSION, "date": PREPARED,
        "status": "DRAFT for owner review",
        "registered_follow_on": {"id": "fo_hall_sustainment_envelope", "trigger": "T_HALL_SUSTAIN_ENVELOPE",
                                 "prerequisites": ["lane_09_hall_sustainment", "lane_16_feed_envelope"]},
        "architecture": ARCH, "architecture_ids": ARCH_IDS,
        "what_it_is": "A mapping of the published Hall-only sustainment / ignition evidence (lane 09 matrix) onto the "
                      "common feed envelope (lane 16): per case and evidence item, whether the item's demonstrated "
                      "operating region covers, partially covers or does not reach the case, and a per-case status "
                      "with blockers. Conditional statements for milestone A.",
        "what_it_is_not": "Not a prediction, not a performance model, not a ranking and not a choice or setting-aside "
                          "of any architecture (only the lane_24 hard gates set an architecture aside). No Hall "
                          "transport closure, ensemble member or simulation result is used. Nothing is wired into "
                          "archengine; no golden moves.",
        "generated_by": {"script": SCRIPT_REL, "command": f"python {SCRIPT_REL}",
                         "check": f"python {SCRIPT_REL} --check", "test": TEST_REL, "deterministic": True,
                         "output_rounding_significant_digits": 6},
        "inputs": inputs,
        "rfp_context": rfp,
        "design_point": dp,
        "definitions": {
            "coverage": {
                COVERS: "the case lies inside the item's demonstrated region on this axis (directional axes: the item "
                        "sustained at conditions as harsh or harsher, or, for an extinction item, extinguished at "
                        "conditions as mild or milder than the case)",
                PARTIAL: "the case range straddles the item's region boundary",
                DNR: "the item's demonstrated region does not reach the case on this axis",
                NC: "the item lacks the quantity needed on this axis (named in 'missing')",
                UND: "the case-side quantity is TBD (named in 'blocked_by'); feed-envelope TBDs propagate here",
            },
            "case_status": {
                S_SUP: "a status-bearing sustained item (evidence level <= 3) covers the case on every required axis, "
                       "with no interpretation condition, and no status-bearing extinction item does (a literature "
                       "transfer under the stated assumptions S1-S3, not a demonstration on the design)",
                S_CON: "a status-bearing extinction item covers the case on every required axis (extinction at "
                       "comparable or milder conditions), and no supporting item does",
                S_UND: "otherwise; blockers name what is missing",
            },
            "ignition_status": {I_SUP: "a primary-basis item of that start mode sustains at conditions covering the "
                                       "case after its start", I_CON: "a primary-basis failed start at comparable "
                                       "conditions (none exists in the matrix)", S_UND: "otherwise, with blockers"},
            "required_axes": list(REQUIRED_AXES), "informational_axes": list(INFO_AXES),
            "directions": [
                {"axis": "anode_flow / anode_flow_density", "direction": "lower is harsher for sustainment",
                 "evidence_class": "inferred", "basis": "E04 (ECHT quenching below a flow boundary, conditional on V "
                 "and B) and E11 (CAMILA voltage-dependent minimum flow); qualitative, level 3"},
                {"axis": "discharge_voltage", "direction": "non-monotone: window containment",
                 "evidence_class": "inferred", "basis": "E02 (P5 stated voltage window, both edges; the edges are "
                 "approximate, condition E02-WINDOW-EDGE) and E04/E11 (low V needs more flow)"},
                {"axis": "magnetic_field", "direction": "non-monotone: range containment, same definition only",
                 "evidence_class": "inferred", "basis": "E04 (quench at increasing magnet current), E10 (a higher "
                 "field than for Xe needed on N2)"},
                {"axis": "composition (atmospheric species N2, O2, O)", "direction": "none established: containment "
                 "only", "evidence_class": "inferred",
                 "basis": "E06 (O2 addition did not degrade sustainment at low flow in the PPS1350)"},
                {"axis": "composition: Xe mass fraction of an N2 + Xe or air + Xe anode feed",
                 "direction": "lower Xe fraction is harsher; used only to place a SUPPORTING Xe-admixture item "
                              "(mixed air + Xe variant). An extinction item would need its Xe fraction at extinction, "
                              "which E13 does not report, so E13 is NOT_COMPARABLE on composition",
                 "evidence_class": "inferred",
                 "basis": "E13 (Z-70: the discharge ceased after the anode Xe flow was reduced below the lowest "
                          "sustaining value; one device, level 3)"},
            ],
            "roles": ROLES,
            "status_bearing_rule": "evidence level <= 3 (docs/EVIDENCE.md: level 5 = second-hand / abstract); level-5 "
                                   "items are reported as corroborating only (PROPOSED rule, owner to confirm)",
            "interpretation_conditions": CONDITIONS,
            "b_definitions": B_DEFINITIONS,
        },
        "assumptions": {
            "S1": {"statement": "sustainment conditions transfer between Hall devices of different size at equal anode "
                                "mass flow per channel cross-section, Gamma = mdot / A_ch (annulus between the channel "
                                "walls)", "evidence_class": "assumed",
                   "limits": "ignores channel length (it differs across the set with no controlled comparison, matrix "
                             "cross-cutting observation 5), neutral temperature and velocity, molecular mass (a "
                             "mass-flux basis, as reported), facility ingestion and the Xe cathode share"},
            "S2": {"statement": "B values with the same definition are comparable across devices",
                   "evidence_class": "assumed",
                   "limits": "the needed B depends on gas, geometry and discharge (E10: a higher field than for Xe on "
                             "N2; P5 ran N2 at a lower peak field than Xe, matrix cross-cutting observation 4)"},
            "S3": {"statement": "an item's demonstrated operating region is taken as the product of its per-axis ranges "
                                "(flow density, V_d and B are assessed independently); joint operating points, e.g. "
                                "whether the lowest flow was run at every voltage, are not checked",
                   "evidence_class": "assumed",
                   "limits": "flow and voltage are coupled for sustainment (E04: quenched unless the potential is "
                             "raised; E11: voltage-dependent minimum flow), so a case at a low-flow / low-voltage "
                             "corner that no single operating point tested can be labelled COVERS on every axis. Every "
                             "comparison carries S3 (comparisons[*].assumptions, joint_operating_point_check "
                             "NOT_CHECKED); a joint-point check needs per-point (flow, V_d, B) data of the item (DM-5). "
                             "PROPOSED (owner): recheck any SUSTAINMENT_SUPPORTED verdict at joint operating points "
                             "before it is used for milestone B"},
            "S4": aeff_assumption(feed),
        },
        "proposed_rules": {
            "H_RAM": {"status": "PROPOSED (owner to confirm)",
                      "statement": "drag compensation within the RFP thrust range bounds the delivered air flow: T >= "
                                   "D >= mdot_captured V, so mdot_anode,air <= mdot_captured <= T_max / V",
                      "assumptions": ["the RFP thrust range (rfp_context.thrust_min .. thrust_max) bounds the "
                                      "thruster's thrust (verify against the RFP text)",
                                      "full drag compensation is required (verify)",
                                      "the air anode flow is part of the captured flow, which is brought to rest "
                                      "relative to the spacecraft before the thruster exhausts it (ram drag "
                                      "mdot_captured V)",
                                      "no other net thrust (vented or leaked gas, surfaces) offsets that ram drag",
                                      "relative speed = circular orbital speed of the feed envelope (co-rotation and "
                                      "winds TBD, ICD G-10)"],
                      "evidence_class": "model-derived"},
            "composition_bracketing": {"status": "PROPOSED (owner decision; not adopted, not used for any status)",
                                       "statement": "if one device sustained, with other conditions unchanged, at two "
                                                    "O2 fractions, intermediate molecular N2/O2 compositions count as "
                                                    "covered for that device",
                                       "evidence_class": "assumed", "device_brackets": brackets},
            "composition_tolerance": {"status": "PROPOSED (owner decision; none adopted)",
                                      "statement": "a physical tolerance for composition comparability (including "
                                                   "trace atomic O); strict containment is used until one is set"},
            "sustainment_margin": {"status": "PROPOSED (owner decision; none adopted)",
                                   "statement": "a margin of delivered flow density above the extinction boundary"},
            "status_bearing_level": {"status": "PROPOSED (owner to confirm)",
                                     "statement": "only evidence level <= 3 items can set a case status"},
        },
        "threshold_definitions": THRESHOLD_DEFINITIONS,
        "max_tested_w_O2": qrec(max_tested_wO2, "1", "inferred",
                                "largest O2 mass fraction over comparable air-only supporting items (evidence_regions)"),
        "evidence_regions": [regs[i] for i in sorted(regs)],
        "excluded_for_hall_only": [{"item": i, "reason": regs[i]["reason"]} for i in sorted(regs)
                                   if regs[i]["role"] == "not_informative"],
        "cases": cases,
        "findings": findings,
        "milestone_A_conditions": milestone_conditions(findings, regs, cases, rfp),
        "decisive_measurements": DECISIVE,
        "blocker_catalogue": BLOCKER_CATALOGUE,
        "v1_simulation_results": {
            "statement": "P5-N2 v1 simulation results are not sustainment evidence and are not used here. They are "
                         "model results; v1 is INCONCLUSIVE, no transport closure is admitted and the credible set is "
                         "empty. A simulated run that reports a sustained discharge is a model state, not a physical "
                         "observation.",
            "context_counts_from_matrix": matrix["context_not_evidence"]["p5_n2_v1_vacuum"]["vacuum_status_counts"],
            "used_for_any_status": False},
        "milestones": {
            "supports": ["A"],
            "statement": "Supports milestone A (conditional selection): it states, per feed-envelope case, which "
                         "conditions hall_only must meet for its sustainment part and which decisive measurement "
                         "(DM-2, with its prerequisites DI-1, DI-2 and DM-1) resolves each UNDETERMINED case. It does "
                         "not need Physics Baseline 1.0 and contains no Hall prediction.",
            "to_reach_B": ["DI-1 and DI-2 supplied (feed evaluated; Vyovrinda design point with provenance)",
                           "DM-1 (valve-outlet atomic O) and DM-2 (extinction boundary on representative hardware at "
                           "the design point) measured; hardware evidence supersedes the literature transfer within "
                           "its domain (docs/EVIDENCE.md). With the current evidence no air case can be supported by "
                           "literature transfer alone (F-9)",
                           "any SUSTAINMENT_SUPPORTED verdict from literature transfer rechecked at joint operating "
                           "points (assumption S3)",
                           "a sustainment margin set by the owner",
                           "(Hall track) an admitted transport closure can add model-derived margins only after it is "
                           "validated against sustainment / extinction data; no v1 run is such data"],
            "to_reach_C": ["DM-6 endurance on an O-containing feed (anode oxidation, E07)",
                           "start sequence and Xe per start (DM-4) inside the Xe budget; cathode life on the chosen "
                           "gas (docs/evidence/cathode/)",
                           "orbit-resolved feed extremes and feed transients (feed envelope: TBD)"],
        },
        "open_questions_for_owner": [
            "Confirm or reject H_RAM (RFP thrust range as the thruster's thrust; full drag compensation).",
            "Adopt or reject the composition bracketing rule and set a composition tolerance (trace atomic O); without "
            "one, no air case can be supported by literature transfer (F-9).",
            "Confirm the constant-A_eff reading of the flow span (S4) or supply the per-case A_eff (feed envelope "
            "FE-08).",
            "Confirm that only evidence level <= 3 items can set a case status.",
            "Set a sustainment margin above the extinction boundary for milestone B.",
            "Declare the mission envelope subset hall_only must sustain (all nine cases, or a restricted set), since "
            "the fixed-design flow span differs by altitude (F-5).",
        ],
        "not_claimed": [
            "no statement that hall_only sustains or fails on the delivered feed",
            "no comparison of hall_only with rf_hall or ecr_hall",
            "no use of screening or unadmitted Hall transport closures, ensemble members or simulation results",
            "no P5 calibration-nuisance variable (registration, coil shape, divergence reading, facility "
            "interpretation) is a design variable or axis here; the P5 channel cross-section is not one of them",
        ],
    }


def aeff_assumption(feed):
    """S4 (constant A_eff across cases for one design), with its limits read from the feed envelope."""
    reqs = sorted({c["feed_scaling"]["A_eff_m2"]["requires"] for c in feed["cases"]}) if all(
        (c.get("feed_scaling") or {}).get("A_eff_m2", {}).get("requires") for c in feed["cases"]) else []
    fe08 = [x for x in feed.get("chain_findings", []) if x.get("id") == "FE-08"]
    sr = [x for x in feed.get("exposed_uncertainty", []) if str(x.get("quantity", "")).startswith("speed-ratio")]
    if len(reqs) != 1 or "effective capture area" not in reqs[0] or len(fe08) != 1 or len(sr) != 1 \
            or not isinstance(sr[0].get("exposed"), dict):
        raise OverlayInputError("feed envelope lacks the A_eff definition (cases[*].feed_scaling.A_eff_m2.requires), "
                                "finding FE-08 or the speed-ratio exposed_uncertainty entry needed for assumption S4")
    aeff_def = reqs[0].split("provenance: ", 1)[-1]
    ex = sr[0]["exposed"]
    lo, hi = ex["computed_min_relative_change"], ex["computed_max_relative_change"]
    return {"statement": "for one fixed design the effective capture area A_eff of the feed-envelope relation mdot = "
                         "A_eff rho V is the same at every case, so the delivered-flow ratio between cases equals the "
                         "free-stream mass-flux (rho V) ratio",
            "evidence_class": "assumed",
            "limits": f"the feed envelope defines A_eff as '{aeff_def}' (cases[*].feed_scaling.A_eff_m2.requires); its "
                      f"finding FE-08 records that eta_c depends on the speed ratio, and its exposed_uncertainty gives "
                      f"a speed-ratio change sqrt(T/m) relative to the TPMC build point of {lo:+.4g} "
                      f"({ex['computed_min_at']}) to {hi:+.4g} ({ex['computed_max_at']}) across the cases "
                      f"({sr[0]['evidence_class']}), against the code comment '{ex['statement_in_code']}'; the effect "
                      f"on eta_c is not quantified there. The flow spans of F-5 are free-stream mass-flux ratios; they "
                      f"equal delivered-flow ratios only under S4",
            "source": "feed_envelope_v1 cases[*].feed_scaling, chain_findings FE-08, exposed_uncertainty (speed ratio)"}


# ---------------------------------------------------------------------------------------------------- markdown
def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in r) + " |")
    return "\n".join(out)


def _val(q, nd=4):
    if not isinstance(q, dict) or q.get("value") is None:
        return "n/c"
    return fmt(q["value"], nd)


def render_md(doc):
    regs = {r["id"]: r for r in doc["evidence_regions"]}
    air = [c for c in doc["cases"] if c["kind"] == "air"]
    var = [c for c in doc["cases"] if c["kind"] != "air"]
    F = {f["id"]: f for f in doc["findings"]}
    L = []
    L.append("# Hall-only sustainment envelope v1: published sustainment evidence on the common feed envelope")
    L.append("")
    L.append("> Generated by `build_hall_sustainment_envelope.py` from `hall_sustainment_envelope_v1.json`. Do not edit "
             "by hand; rerun the script.")
    L.append("")
    L.append(md_table(["", ""], [
        ["machine-readable", "[`hall_sustainment_envelope_v1.json`](hall_sustainment_envelope_v1.json)"],
        ["status", f"**{doc['status']}** (overlay version {doc['version']}, {doc['date']})"],
        ["registered follow-on", f"`{doc['registered_follow_on']['id']}` (trigger "
                                 f"`{doc['registered_follow_on']['trigger']}`)"],
        ["architecture", "`hall_only` (direct Hall operation on atmospheric propellant, no pre-ionizer)"],
        ["milestone", "supports **A** (conditional selection); what B and C need is in section 10"],
        ["inputs", "; ".join(f"`{v['path']}` ({v['lane']}, commit {v['commit'] or 'n/a'}, sha256 "
                             f"{(v['sha256'] or 'n/a')[:12]}...)"
                             for v in doc["inputs"].values())],
        ["test", f"`{TEST_REL}`"],
    ]))
    L.append("")
    L.append(f"**What it is.** {doc['what_it_is']}")
    L.append("")
    L.append(f"**What it is not.** {doc['what_it_is_not']}")
    L.append("")
    L.append(f"**Simulation results are not sustainment evidence.** {doc['v1_simulation_results']['statement']} "
             "(Context only, from the matrix: v1 vacuum status counts "
             f"{doc['v1_simulation_results']['context_counts_from_matrix']}; used for no status.)")
    L.append("")
    L.append("## 1. Result in one paragraph")
    L.append("")
    L.append(F["F-1"]["statement"] + " The overlay therefore records, per case, the conditions under which each "
             "evidence item would cover it (sections 4-6), what the evidence can never cover as reported (sections "
             "5-7), and the decisive measurement, with its prerequisites, that resolves each case (section 9)."
             + (" With the current evidence no air case can become SUSTAINMENT_SUPPORTED by literature transfer, even "
                "once the feed and the design point are supplied (F-9, section 4)."
                if not F["F-9"]["values"]["air_case_supportable_by_literature_transfer"] else ""))
    L.append("")
    L.append("## 2. Method")
    L.append("")
    L.append("Each evidence item is placed on the case along seven axes. Required for a status: "
             + ", ".join(f"`{a}`" for a in doc["definitions"]["required_axes"])
             + ". Informational: " + ", ".join(f"`{a}`" for a in doc["definitions"]["informational_axes"]) + ".")
    L.append("")
    L.append(md_table(["coverage", "meaning"], [[k, v] for k, v in doc["definitions"]["coverage"].items()]))
    L.append("")
    L.append(md_table(["case status", "rule"], [[k, v] for k, v in doc["definitions"]["case_status"].items()]))
    L.append("")
    L.append(md_table(["axis", "harsher direction", "class", "basis"],
                      [[d["axis"], d["direction"], d["evidence_class"], d["basis"]]
                       for d in doc["definitions"]["directions"]]))
    L.append("")
    L.append("**Scaling assumptions (explicit, evidence class `assumed`).**")
    L.append("")
    for k, a in doc["assumptions"].items():
        L.append(f"- **{k}**: {a['statement']}. Limits: {a['limits']}.")
    L.append("")
    L.append("**Composition scenarios** (the valve-outlet composition is TBD; these bound it under the chain's "
             "collected-flow split convention, FE-05 primary; the species-resolved convention is not bounded here):")
    L.append("")
    sc0 = air[0]["feed"]["composition_scenarios"]
    for k in ("SC-FS", "SC-REC"):
        L.append(f"- **{k}**: {sc0[k]['definition']}.")
    L.append("")
    L.append("**PROPOSED rules for the owner** (none is used to set a status except where stated):")
    L.append("")
    for k, r in doc["proposed_rules"].items():
        extra = ""
        if k == "H_RAM":
            extra = " Assumptions: " + "; ".join(r["assumptions"]) + "."
        L.append(f"- **{k}** ({r['status']}): {r['statement']}.{extra}")
    L.append("")
    L.append(f"Status-bearing rule: {doc['definitions']['status_bearing_rule']}.")
    L.append("")
    L.append("## 3. Evidence operating regions (from the lane 09 matrix; values read, never typed)")
    L.append("")
    rows = []
    for i, r in sorted(regs.items()):
        if r["role"] in ("not_informative", "duration_limit"):
            continue
        fd = r["flow_density"]
        fdv = ("n/c: " + fd["missing"]) if fd.get("value") is None else (
            fmt(fd["value"]) + (" (lower bound)" if fd.get("bound") == "lower" else ""))
        comp = r["composition"]
        cstr = (", ".join(f"w_{s} {fmt(v)}" for s, v in comp["w"].items()) if comp.get("w")
                else f"n/c: {comp.get('missing')}")
        b = r["magnetic_field"]
        bstr = (fmt(b["value"]) + " G") if b.get("value") else f"n/c: {b['missing']}"
        v = r["discharge_voltage"]
        vstr = fmt(v["value"]) if v.get("value") else f"n/c: {v['missing']}"
        if v.get("edge_note"):
            vstr += f" (stated window, approximate edges; {v['edge_note']})"
        p = r["discharge_power"]
        pstr = (f"{fmt(p['value'])} kW, {p['rfp_total_power_relation']}") if p.get("value") else "n/c"
        cg = r["cathode_gas"]
        cgs = (cg["gas"] + ("" if cg["rfp_propellant_relation"] == "LISTED" else
                            f" ({cg['rfp_propellant_relation']})")) if cg["gas"] else f"n/c: {cg['missing']}"
        if r.get("sustained_reference_point"):
            fstr = (f"n/c at extinction (not reported); sustained at the lowest-Xe point, "
                    f"{_val(r['sustained_reference_point'])} (N2 + Xe); anode gas '{r['anode_gas']}'")
            fdv = "n/c: anode flow at extinction not reported"
        else:
            fstr = _val(r["flow"]) if r["flow"].get("value") else f"n/c: {r['flow']['missing']}"
        rows.append([i, r["device"], r["role"], r["evidence_level"], r["outcome"], fstr,
                     fdv, cstr, vstr, bstr, cgs, pstr,
                     f"{r['ignition']['mode']} ({r['ignition']['basis']})"])
    L.append(md_table(["id", "device", "role", "level", "outcome", "flow [mg/s]", "flow density [kg m^-2 s^-1] (S1)",
                       "composition (mass)", "V_d [V]", "B", "cathode", "power vs RFP ceiling", "ignition (basis)"],
                      rows))
    L.append("")
    seen_dev, area_txt = set(), []
    for i, r in sorted(regs.items()):
        a = r.get("channel_area") or {}
        if a.get("value") and r["device"] not in seen_dev:
            seen_dev.add(r["device"])
            area_txt.append(f"{r['device']} {fmt(a['value'])} m^2 ({a['derivation']}"
                            + (f"; {a['bound']} bound" if a.get("bound") else "") + ")")
    L.append("n/c = not comparable (the missing quantity is named). Flow densities use the channel cross-section: "
             + "; ".join(area_txt) + ".")
    L.append("")
    for i, r in sorted(regs.items()):
        if r.get("sustained_reference_point"):
            L.append(f"{i} ({r['device']}): {r['flow']['missing']}. The sustained reference point is not an "
                     "extinction value and enters no axis, threshold or status.")
            L.append("")
    L.append("Cathode-gas relation to the RFP propellant set (air + Xe): "
             + "; ".join(f"{k} = {v}" for k, v in RFP_GAS_RELATION_TEXT.items()) + ".")
    L.append("")
    L.append("Not used for hall_only: " + "; ".join(f"{x['item']} ({x['reason']})" for x in
                                                   doc["excluded_for_hall_only"])
             + ". Duration only: " + "; ".join(f"{i} ({r['reason']})" for i, r in sorted(regs.items())
                                             if r["role"] == "duration_limit") + ".")
    L.append("")
    L.append("## 4. Feed cases and design-independent thresholds")
    L.append("")
    L.append("The delivered anode flow is TBD for every case (feed envelope status DESIGN_INPUTS_MISSING), so each "
             "item is placed on a case through thresholds on the design factors: `A_eff` (feed-envelope relation "
             "mdot = A_eff x rho V) and `A_ch` (Vyovrinda channel cross-section). `area_ratio_required` = the A_eff / "
             "A_ch at which the case reaches the item's lowest demonstrated flow density (S1); `A_ch max (H_RAM)` = "
             "the largest channel at which that flow density is reachable with the air flow at the H_RAM bound.")
    L.append("")
    gcols = sorted(i for i, r in regs.items() if r["role"] == "support_air_only" and r["flow_density"].get("value"))

    def tv(t, i, k):
        q = t.get(i, {}).get(k)
        if not q:
            return "n/c"
        return _val(q) + (f" ({q['bound']} bound)" if q.get("bound") else "")

    rows = []
    for c in air:
        t = c["thresholds"]
        rows.append([c["case_id"], fmt(c["feed"]["mass_flux_kgpm2ps"]["value"]), "TBD",
                     fmt(c["H_RAM_bound"]["mdot_air_max_kgps"]["value"] * 1e6),
                     fmt(c["H_RAM_bound"]["A_eff_max_m2"]["value"])]
                    + [tv(t, i, "area_ratio_required") for i in gcols]
                    + [tv(t, i, "A_ch_max_under_H_RAM_m2") for i in gcols])
    L.append(md_table(["case", "rho V [kg m^-2 s^-1]", "mdot delivered", "mdot air max H_RAM [mg/s]",
                       "A_eff max H_RAM [m^2]"] + [f"A_eff/A_ch req. {i}" for i in gcols]
                      + [f"A_ch max {i} [m^2]" for i in gcols], rows))
    L.append("")
    L.append(F["F-2"]["statement"])
    L.append("")
    L.append(F["F-3"]["statement"])
    L.append("")
    L.append(f"**Reach of literature transfer for air feeds (F-9).** {F['F-9']['statement']}")
    L.append("")
    L.append("Same-size flow (`A_eff_required_m2`, no scaling) is listed per case and item in the JSON "
             "(`cases[*].thresholds`).")
    L.append("")
    L.append("## 5. Composition")
    L.append("")
    rows = []
    for c in air:
        s = c["feed"]["composition_scenarios"]
        rows.append([c["case_id"], fmt(s["SC-FS"]["w"]["O"]), fmt(s["SC-FS"]["w"]["N2"]), fmt(s["SC-FS"]["w"]["O2"]),
                     ", ".join(s["SC-FS"]["covered_by"]) or "none",
                     fmt(s["SC-REC"]["w"]["O2"]), ", ".join(s["SC-REC"]["covered_by"]) or "none",
                     ", ".join(s["SC-REC"]["within_device_bracket_if_PROPOSED_rule_adopted"]) or "none"])
    L.append(md_table(["case", "SC-FS w_O", "SC-FS w_N2", "SC-FS w_O2", "items covering SC-FS", "SC-REC w_O2",
                       "items covering SC-REC", "device bracket (PROPOSED rule)"], rows))
    L.append("")
    L.append(F["F-4"]["statement"])
    L.append("")
    L.append("## 6. Flow span, power, cathode gas, duration")
    L.append("")
    for k in ("F-5", "F-6", "F-7", "F-8"):
        L.append(f"- **{F[k]['topic']}.** {F[k]['statement']}")
    L.append("")
    L.append("## 7. Case status (sustainment)")
    L.append("")
    rows = []
    for c in air + var:
        by_v = {}
        for x in c["comparisons"]:
            if x["status_bearing"]:
                by_v.setdefault(x["verdict"], []).append(x["item"])
        vtxt = "; ".join(f"{v}: {', '.join(sorted(i))}" for v, i in sorted(by_v.items())) or "no item compared"
        rows.append([c["case_id"], f"**{c['status']}**", ", ".join(b["id"] for b in c["blockers"]), vtxt])
    L.append(md_table(["case", "status", "blockers", "status-bearing item verdicts"], rows))
    L.append("")
    L.append(md_table(["blocker", "meaning", "resolved by"],
                      [[k, v, ", ".join(sorted({r for c in doc["cases"] for b in c["blockers"] if b["id"] == k
                                               for r in b.get("resolved_by", [])})) or
                        ", ".join(d["id"] for d in doc["decisive_measurements"] if k in d["resolves"]) or
                        "- (outside this overlay's scope)"]
                       for k, v in doc["blocker_catalogue"].items()]))
    L.append("")
    L.append("Per case and item, every axis result (coverage, missing quantity or blocking TBD) is in "
             "`cases[*].comparisons`; the feed-envelope `requires` text of each TBD is copied into the blockers.")
    L.append("")
    L.append("## 8. Ignition, separately: xenon-assisted start vs air-only ignition")
    L.append("")
    modes = (("xenon-assisted: Xe anode start, then transition", ("xenon_assisted", "xe_anode_start")),
             ("xenon-assisted: atmospheric anode, Xe cathode", ("xenon_assisted", "xe_cathode_direct")),
             ("air-only: no xenon anywhere", ("air_only",)))

    def ig_get(c, path):
        x = c["ignition"]
        for k in path:
            x = x[k]
        return x

    rows = []
    for name, path in modes:
        blk = ig_get(air[0], path)
        sts = sorted({ig_get(c, path)["status"] for c in air})
        rows.append([name, ", ".join(blk["evidence_items"]) or "none", " / ".join(sts), blk["note"]])
    L.append(md_table(["start mode", "evidence items", "status (all air cases)", "note"], rows))
    L.append("")
    L.append("No accessed source publishes an ignition threshold (breakdown voltage or pressure) for atmospheric gas "
             "in a Hall channel (matrix cross-cutting observation 3). No item reports a failed start, so no case is "
             "IGNITION_CONTRADICTED; the air-only mode has no precedent on an RFP propellant.")
    L.append("")
    L.append("## 9. Conditions for the sustainment part of a milestone-A conditional baseline, and decisive "
             "measurements")
    L.append("")
    L.append("hall_only would satisfy the sustainment part of a milestone-A conditional statement ('hall_only is "
             "baseline provided ...') if the following conditions hold; each is stated, not asserted:")
    L.append("")
    L.append(md_table(["id", "condition", "current state", "resolved by"],
                      [[m["id"], m["condition"], m["state"], ", ".join(m["resolved_by"])]
                       for m in doc["milestone_A_conditions"]]))
    L.append("")
    L.append(md_table(["id", "type", "what", "prerequisites", "resolves"],
                      [[d["id"], d["type"], d["what"], ", ".join(d.get("prerequisites", [])) or "-",
                        ", ".join(d["resolves"]) or "-"]
                       for d in doc["decisive_measurements"]]))
    L.append("")
    dm = air[0]["decisive_measurement"]
    L.append(f"Per case, the decisive measurement is {dm['id']} at that case's delivered flow density and "
             f"composition. It is not a stand-alone measurement: {dm['not_stand_alone']} (prerequisites "
             f"{', '.join(dm['prerequisites'])}). For one fixed design the lowest free-stream mass flux (the lowest "
             f"delivered flow under S4) is at "
             f"{F['F-5']['values']['harshest_flow_case']}; the highest free-stream atomic-O fraction is at "
             f"{F['F-4']['values']['most_atomic_O_case_SC_FS']} and the highest O2 fraction after complete "
             f"recombination at {F['F-4']['values']['most_O2_case_SC_REC']}. These measurements feed the minimum "
             f"decisive experiment (docs/architecture_comparison/experiment_protocol/, other lane).")
    L.append("")
    L.append("## 10. Milestones")
    L.append("")
    L.append(doc["milestones"]["statement"])
    L.append("")
    L.append("To reach **B**:")
    L.append("")
    for x in doc["milestones"]["to_reach_B"]:
        L.append(f"- {x}")
    L.append("")
    L.append("To reach **C**:")
    L.append("")
    for x in doc["milestones"]["to_reach_C"]:
        L.append(f"- {x}")
    L.append("")
    L.append("## 11. Open questions for the owner")
    L.append("")
    for n, q in enumerate(doc["open_questions_for_owner"], 1):
        L.append(f"{n}. {q}")
    L.append("")
    L.append("## 12. Not claimed")
    L.append("")
    for x in doc["not_claimed"]:
        L.append(f"- {x}")
    L.append("")
    L.append("## 13. Reproduce / verify")
    L.append("")
    L.append("```")
    L.append(f"python {SCRIPT_REL}            # rewrite {OUT_JSON_NAME} and {OUT_MD_NAME}")
    L.append(f"python {SCRIPT_REL} --check    # exit 1 unless the committed files are reproduced")
    L.append(f"python -m pytest -q {TEST_REL}")
    L.append("```")
    L.append("")
    L.append("Inputs are pinned by sha256 (`inputs` in the JSON). A changed input fails the pin and asks for a "
             "deliberate re-pin and regeneration.")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------------------------------- main
def dumps(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def render_all(extra_roots=(), design_point=None, feed_override_path=None):
    skip = ("feed_envelope",) if feed_override_path else ()
    found = resolve_inputs(extra_roots, skip=skip)
    fo = meta = None
    if feed_override_path:
        fo = load_json(feed_override_path)
        meta = {"path": os.path.abspath(feed_override_path), "sha256": sha256_file(feed_override_path)}
    doc = build(found, design_point=design_point, feed_override=fo, feed_override_meta=meta)
    return dumps(doc), render_md(doc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="rebuild in memory; exit 1 unless the committed files match")
    ap.add_argument("--input-root", action="append", default=[], help="extra root searched for pinned inputs")
    ap.add_argument("--feed-envelope", help="design-evaluated feed envelope JSON (unpinned; needs --out-dir)")
    ap.add_argument("--design-point", help="hall_sustainment_design_point_v1 JSON (needs --out-dir)")
    ap.add_argument("--out-dir", help="output directory for a design evaluation (never this directory)")
    a = ap.parse_args(argv)
    if a.feed_envelope or a.design_point:
        if not a.out_dir or os.path.abspath(a.out_dir) == HERE:
            ap.error("--feed-envelope / --design-point need --out-dir other than the committed directory")
        dp = validate_design_point(load_json(a.design_point)) if a.design_point else None
        js, md = render_all(a.input_root, design_point=dp, feed_override_path=a.feed_envelope)
        os.makedirs(a.out_dir, exist_ok=True)
        for name, text in ((OUT_JSON_NAME, js), (OUT_MD_NAME, md)):
            with open(os.path.join(a.out_dir, name), "w", encoding="utf-8") as f:
                f.write(text)
        print(f"wrote {a.out_dir}/{OUT_JSON_NAME} and {OUT_MD_NAME}")
        return 0
    js, md = render_all(a.input_root)
    targets = ((os.path.join(HERE, OUT_JSON_NAME), js), (os.path.join(HERE, OUT_MD_NAME), md))
    if a.check:
        bad = []
        for p, text in targets:
            cur = open(p, encoding="utf-8").read() if os.path.isfile(p) else None
            if cur != text:
                bad.append(os.path.relpath(p, ROOT))
        if bad:
            print("NOT reproduced: " + ", ".join(bad))
            return 1
        print("OK: committed files reproduced")
        return 0
    for p, text in targets:
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    print("wrote " + ", ".join(os.path.relpath(p, ROOT) for p, _ in targets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
