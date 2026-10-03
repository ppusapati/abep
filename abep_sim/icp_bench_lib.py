"""ICP bench (P1) and impedance-map (P2) helpers used by the F6 ICP geometry synthesis (A9.22 layer separation).

Verbatim copies of the subset of the P1 / P2 experiment code that abep_sim/design/icp_geometry_synthesis.py needs:

  * P1 ``ICP45A_STATUSES`` from docs/experiments/hall_icp/p1_icp_bench/p1_reducer.py
    (sha256 140cc9cf68b40b585bd8b096fcd66b6fb9a3344608c88f4e759b0587d5da7a65);
  * P2 ``validate_map`` and its top-level dependencies from docs/experiments/hall_icp/p2_impedance_map/p2_framework.py
    (sha256 bc0f59c97c1e474ceadb9dd9a4c389d1a3e11e16e71f56e6a566bafe829c5305), with the reducer names it reaches
    through ``RED`` (``RATING_STATUS``, ``SYNTHETIC_LABEL``, ``MixedEvidenceError``, ``_scan_forbidden`` and their
    dependencies) from docs/experiments/hall_icp/p2_impedance_map/p2_impedance_reducer.py
    (sha256 f762f9805feffaa6dfd2cfbdabcd89f9a7c26b93d6d373fb56196839bdf3a36c). ``RED`` is this module itself, so the
    copied function bodies are unchanged.

Before A9.22 the design layer imported those files by path; it now imports this library. The docs files are unchanged
(they are sha-pinned by immutable records); tests/test_design_layer_separation.py checks that every copied definition
is source-identical to its docs original.

``experiment_p1_reducer()`` loads the complete P1 reducer (experiment data-reduction code, not a design input) for
callers that need the full reducer, e.g. the F6 builder's state probe (``icp45a_evaluate``); no design computation
uses it.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
P1_REDUCER_REL = "docs/experiments/hall_icp/p1_icp_bench/p1_reducer.py"
P2_FRAMEWORK_REL = "docs/experiments/hall_icp/p2_impedance_map/p2_framework.py"
P2_REDUCER_REL = "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_reducer.py"
SOURCE_SHA256 = {
    P1_REDUCER_REL: "140cc9cf68b40b585bd8b096fcd66b6fb9a3344608c88f4e759b0587d5da7a65",
    P2_FRAMEWORK_REL: "bc0f59c97c1e474ceadb9dd9a4c389d1a3e11e16e71f56e6a566bafe829c5305",
    P2_REDUCER_REL: "f762f9805feffaa6dfd2cfbdabcd89f9a7c26b93d6d373fb56196839bdf3a36c",
}

# ================================================================================================ P1 (p1_reducer.py)
ICP45A_STATUSES = ("NOT_EVALUATED", "NOT_EVALUATED_REGISTRATION", "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE",
                   "EVALUATED_ENGINEERING_ONLY")

# ================================================================================================ P2 reducer subset
RATING_STATUS = "TBD_AFTER_IMPEDANCE_MAP"


SYNTHETIC_LABEL = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"


FORBIDDEN_KEY_PREFIXES = ("P_plasma", "P_absorbed_plasma")


class P2ReducerError(ValueError):
    """Base class of every refusal raised by the reducer."""


class ForwardAsPlasmaError(P2ReducerError):
    pass


class RecordError(P2ReducerError):
    pass


class MixedEvidenceError(RecordError):
    """Synthetic and measured evidence combined in one reduction (record vs calibration set, loss verification or cold
    reference): refused (owner A9.6 sec. 14 'mixed synthetic/measured evidence -> refused')."""


def _is_plasma_power_key(k):
    """A key naming plasma power: the forbidden prefixes, or 'plasma' anywhere in a power-like key
    (starts with 'P_' / 'p_', contains 'power' or 'pwr', or carries a watt unit suffix '_W' / '_kW' / '_mW')."""
    if not isinstance(k, str):
        return False
    if k.startswith(FORBIDDEN_KEY_PREFIXES):
        return True
    kl = k.lower()
    if "plasma" not in kl:
        return False
    return (kl.startswith("p_") or "power" in kl or "pwr" in kl or kl.endswith(("_w", "_kw", "_mw"))
            or any(t in kl for t in ("_w_", "_kw_", "_mw_")))


def _scan_forbidden(obj, path="record"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _is_plasma_power_key(k):
                raise ForwardAsPlasmaError(
                    f"{path}.{k}: plasma power is not an input of the impedance chain; P_forward (or P_net) is never "
                    "P_plasma (A9.2 rf_measurement_reference)")
            _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan_forbidden(v, f"{path}[{i}]")


# the P2 framework reaches the reducer through ``RED``; here the reducer subset lives in this module
RED = sys.modules[__name__]

# ================================================================================================ P2 framework subset
MAP_SCHEMA_ID = "p2_impedance_map_v1"


RATING_STATUS = RED.RATING_STATUS                       # TBD_AFTER_IMPEDANCE_MAP (A9.2 a9_10_statuses)


MAP_POINT_FIELDS = ("record_id", "phase", "data_class", "evidence_tag", "calibration_set_id", "f_Hz", "Z0_ohm",
                    "factors", "match_state", "plasma_state_class", "sweep", "Z_antenna", "Z_antenna_primary_method",
                    "gamma_antenna_vs_Z0", "at_RP_CPL", "P_line_match_loss_W", "P_delivered_W", "loss_status",
                    "uncertainty")


MAP_HEADER_FIELDS = ("schema", "map_id", "data_class", "evidence_status", "evidence_tag", "p1_stable_region_ref",
                     "calibration_set_ids", "rating_status", "framework", "points", "excluded_records",
                     "content_sha256")


class FrameworkError(ValueError):
    """Base class of every framework refusal."""


class MapFormatError(FrameworkError):
    pass


def _canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def validate_map(doc):
    if not isinstance(doc, dict):
        raise MapFormatError("map must be an object")
    miss = [k for k in MAP_HEADER_FIELDS if k not in doc]
    if miss:
        raise MapFormatError(f"map lacks {miss}")
    if doc["schema"] != MAP_SCHEMA_ID:
        raise MapFormatError(f"schema {doc['schema']!r} != {MAP_SCHEMA_ID}")
    if doc["rating_status"] != RATING_STATUS:
        raise MapFormatError("rating_status must stay " + RATING_STATUS)
    body = {k: v for k, v in doc.items() if k != "content_sha256"}
    if hashlib.sha256(_canon(body).encode("ascii")).hexdigest() != doc["content_sha256"]:
        raise MapFormatError("content_sha256 mismatch (map edited after writing)")
    for p in doc["points"]:
        pm = [k for k in MAP_POINT_FIELDS if k not in p]
        if pm:
            raise MapFormatError(f"point {p.get('record_id')!r} lacks {pm}")
        if p["data_class"] != doc["data_class"]:
            raise RED.MixedEvidenceError(f"point {p['record_id']!r} data_class differs from the map")
        for m, z in p["Z_antenna"].items():
            if z.get("plane") != "RP-ANT":
                raise MapFormatError(f"point {p['record_id']!r} Z_antenna[{m}] not at RP-ANT")
        RED._scan_forbidden(p, f"map.points[{p['record_id']}]")
    expect = RED.SYNTHETIC_LABEL if doc["data_class"] == "synthetic_test" else "measured (P2 impedance map)"
    if doc["evidence_status"] != expect:
        raise MapFormatError("evidence_status inconsistent with data_class")
    return True


# ================================================================================================ full P1 reducer
_P1 = {}


def experiment_p1_reducer(repo: Path = REPO):
    """The complete P1 reducer module (experiment code; read-only, loaded once). Not used by design computations."""
    key = str(repo)
    if key not in _P1:
        name = "abep_f6_p1_reducer"
        spec = importlib.util.spec_from_file_location(name, str(Path(repo) / P1_REDUCER_REL))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod          # dataclasses resolve annotations through sys.modules
        spec.loader.exec_module(mod)
        _P1[key] = mod
    return _P1[key]
