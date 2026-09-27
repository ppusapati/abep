#!/usr/bin/env python3
"""W4 instrumentation definition (fo_instrumentation_definition, trigger T_PIVOT_INSTRUMENTATION_DEFINITION,
owner disposition od_hardware_pivot, docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json).

DRAFT for owner review. Builds instrumentation_definition_v1.json and INSTRUMENTATION_DEFINITION.md in this folder from
pinned, merged inputs (lane 25 minimum decisive experiment, experiment package D-01..D-15, lane 06 protocol draft, the
owner disposition, the RFP record in abep_sim/constants.py). Every computed number comes from a function in this file;
`--check` rebuilds both files in memory and compares them byte for byte with the committed ones.

Nothing here is pre-registered, locked or decided. Thresholds that are not in the RFP are PROPOSED (evidence class
'assumed'). No Hall transport closure, screening candidate or withdrawn 0-D number is used; no instrument accuracy is
claimed for any product. Missing or changed inputs raise (no silent fallbacks).

Usage:
    python docs/experiments/instrumentation/build_instrumentation_definition.py           # write both files
    python docs/experiments/instrumentation/build_instrumentation_definition.py --check   # verify, write nothing
    python docs/experiments/instrumentation/build_instrumentation_definition.py --pin     # first pin only (refuses to
                                                                                          # overwrite pinned_inputs.json)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT_JSON = HERE / "instrumentation_definition_v1.json"
OUT_MD = HERE / "INSTRUMENTATION_DEFINITION.md"
SCRIPT_REL = "docs/experiments/instrumentation/build_instrumentation_definition.py"
BASE_COMMIT = "510e464fb8e128e4cf3325572a4d36ad33a4899d"

ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
BOUNDARY_VERSION = "bus_power_boundary_v1"
# Contract names of bus_power_boundary_v1 (task naming contract; cross-checked against abep_sim/arch_boundary.py by the
# test when that module is present). Never imported here: the ledger itself is another lane's module.
V1_COMMON = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor",
             "thermal_control", "housekeeping")
V1_PREIONIZER = {"hall_only": (), "rf_hall": ("rf_source",), "ecr_hall": ("ecr_source", "ecr_magnet")}

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")

# Pinned inputs (sha256 of the file bytes at the base commit). A change raises InputChanged: re-read, re-derive, re-pin.
PINNED = {   # path -> lane; the sha256 pins live in pinned_inputs.json (written once by `--pin`, then only verified)
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json": "od_hardware_pivot (owner)",
    "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json": "lane_25_min_decisive_experiment",
    "docs/architecture_comparison/minimum_decisive_experiment/MINIMUM_DECISIVE_EXPERIMENT_DRAFT.md":
        "lane_25_min_decisive_experiment",
    "docs/architecture_comparison/experiment_package/experiment_package_v1.json": "fo_experiment_package",
    "docs/architecture_comparison/experiment_protocol/protocol_draft.json": "lane_06_experiment_protocol",
    "abep_sim/constants.py": "repository (RFP record, physical constants)",
    # control C5 repair (v1-r2)
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A2_execution_directive.json": "od_hardware_pivot A2 (owner; C5)",
    "docs/experiments/lifetime_ao/ao_lifetime_register_v2.json": "fo_ao_lifetime_register (v2)",
    "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json": "fo_magnet_coil_qualification",
    # W3 is pinned as an IMMUTABLE SNAPSHOT (bytes of commit 9a33979), never the live W3 file: W3 pins this file, so
    # pinning the live W3 bytes here made a W3 <-> W4 pin cycle that could never settle (A3 repair review).
    "docs/experiments/instrumentation/snapshots/w3_hardware_requirements_v1_at_9a33979.json":
        "fo_hardware_definition (W3), immutable snapshot of commit 9a33979",
    "schemas/thermal_life/inputs_v1.json": "thermal_life input schema (measured_hardware record)",
    # owner addendum A3 (v1-r2, additive): metrology, cathode temperature, quantitative RGA, k = 2
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json": "od_hardware_pivot A3 (owner)",
}


class InputChanged(RuntimeError):
    """A pinned input's bytes differ from its pin."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pins() -> dict:
    pins_file = HERE / "pinned_inputs.json"
    if not pins_file.exists():
        raise FileNotFoundError(f"{pins_file} missing: the pinned-input record is part of this deliverable")
    pins = json.loads(pins_file.read_text(encoding="utf-8"))
    if sorted(pins) != sorted(PINNED):
        raise InputChanged(f"pinned_inputs.json keys {sorted(pins)} != expected {sorted(PINNED)}")
    return pins


def verify_inputs() -> dict:
    """Raise FileNotFoundError / InputChanged unless every pinned input exists with its pinned sha256."""
    pins = _pins()
    for rel, sha in pins.items():
        p = ROOT / rel
        if not p.exists():
            raise FileNotFoundError(f"pinned input missing: {rel}")
        got = _sha256(p)
        if got != sha:
            raise InputChanged(f"pinned input changed: {rel} sha256 {got} != pin {sha}")
    return pins


def _load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _load_rfp():
    p = ROOT / "abep_sim" / "constants.py"
    spec = importlib.util.spec_from_file_location("_instr_constants", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------------------------------------------------------
# number helpers
# ----------------------------------------------------------------------------------------------------------------------
def _r(x: float, sig: int = 6) -> float:
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.{sig}g}")


def q(value, unit: str, evidence_class: str, source: str, exact: bool = False, **extra) -> dict:
    """exact=True stores a value copied from another lane's file bit-for-bit (no rounding)."""
    if evidence_class not in EVIDENCE_CLASSES:
        raise ValueError(f"unknown evidence class {evidence_class!r}")
    if isinstance(value, float) and not exact:
        value = _r(value)
    d = {"value": value, "unit": unit, "evidence_class": evidence_class, "source": source}
    d.update(extra)
    return d


def tbd(requires: str, blocked_by: str | None = None) -> dict:
    d = {"value": "TBD", "tbd_requires": requires}
    if blocked_by:
        d["blocked_by"] = blocked_by
    return d


def _src(fn: str) -> str:
    return f"{SCRIPT_REL}: {fn}"


def _positive(**kw):
    for k, v in kw.items():
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
            raise ValueError(f"{k} must be a finite positive number, got {v!r}")


# ----------------------------------------------------------------------------------------------------------------------
# derivations (pure functions; tested)
# ----------------------------------------------------------------------------------------------------------------------
def k_one_sided(alpha: float) -> float:
    """One-sided normal quantile z_{1-alpha} (Type B dominated absolute budgets treated as known, GUM G.4.3)."""
    if not 0 < alpha < 0.5:
        raise ValueError("alpha must be in (0, 0.5)")
    return NormalDist().inv_cdf(1.0 - alpha)


def abs_sigma(u_rel: float, level: float) -> float:
    """Absolute 1-sigma value of a relative 1-sigma requirement at a reference level."""
    _positive(u_rel=u_rel, level=level)
    return u_rel * level


def lower_gate(limit: float, u_rel: float, k: float) -> dict:
    """Gate 'X >= limit' decided on a one-sided bound: PASS iff X_hat (1 - k u) >= limit, FAIL iff X_hat (1 + k u) < limit.
    Returns the smallest X_hat that passes and the largest that fails (relative u of the reading, 1 sigma)."""
    _positive(limit=limit, u_rel=u_rel, k=k)
    if k * u_rel >= 1:
        raise ValueError("k * u_rel >= 1: no reading can pass")
    return {"pass_min": limit / (1 - k * u_rel), "fail_max": limit / (1 + k * u_rel)}


def upper_gate(limit: float, u_rel: float, k: float) -> dict:
    """Gate 'X < limit': PASS iff X_hat (1 + k u) < limit, FAIL iff X_hat (1 - k u) >= limit."""
    _positive(limit=limit, u_rel=u_rel, k=k)
    if k * u_rel >= 1:
        raise ValueError("k * u_rel >= 1")
    return {"pass_max": limit / (1 + k * u_rel), "fail_min": limit / (1 - k * u_rel)}


def channel_sum_u(powers, u_rels) -> float:
    """Relative 1-sigma random uncertainty of a sum of independently metered channels."""
    if len(powers) != len(u_rels) or not powers:
        raise ValueError("powers and u_rels must be non-empty and of equal length")
    for p, u in zip(powers, u_rels):
        if p < 0 or u < 0:
            raise ValueError("negative power or uncertainty")
    tot = sum(powers)
    if tot <= 0:
        raise ValueError("total power must be positive")
    return math.sqrt(sum((p * u) ** 2 for p, u in zip(powers, u_rels))) / tot


def consumer_scale_max(group_share: float, w_c: float) -> float:
    """Largest common-consumer meter scale u_c such that (w_c u_c) fills the G4 share alone (lane 25 Sec. 6.1)."""
    _positive(group_share=group_share, w_c=w_c)
    return group_share / w_c


def mfc_relative_u(u_full_scale: float, setpoint_fraction: float) -> float:
    """Relative 1-sigma flow uncertainty at a setpoint when the device uncertainty is stated in % of full scale."""
    _positive(u_full_scale=u_full_scale, setpoint_fraction=setpoint_fraction)
    if setpoint_fraction > 1:
        raise ValueError("setpoint fraction above full scale")
    return u_full_scale / setpoint_fraction


def mass_fraction_u(w: float, u1: float, u2: float) -> float:
    """1-sigma absolute uncertainty of w = m1/(m1+m2) from independent relative uncertainties u1 (m1), u2 (m2)."""
    if not 0 < w < 1:
        raise ValueError("w must be in (0, 1)")
    if u1 < 0 or u2 < 0:
        raise ValueError("negative uncertainty")
    return w * (1 - w) * math.sqrt(u1 ** 2 + u2 ** 2)


def one_way_mass_flux(p_Pa: float, m_kg: float, T_K: float, k_B: float) -> float:
    """Free-molecular one-way mass flux of a stationary Maxwellian gas through a plane, p sqrt(m / (2 pi k_B T))."""
    _positive(p_Pa=p_Pa, m_kg=m_kg, T_K=T_K, k_B=k_B)
    return p_Pa * math.sqrt(m_kg / (2 * math.pi * k_B * T_K))


def stop_sensitivity(sigma_max: float, k: float, delta: float, factor: float, share_type_a: float) -> dict:
    """If the Type-A-in-campaign groups (G1+G2, share_type_a of sigma_max^2) are realised at `factor` x plan and the rest at
    plan: sigma, half-width h = k sigma (k held at its planning value), the largest true R that can support a stop when
    the estimate equals ln R (upper bound < 0 needs ln R < -h), whether EQUIVALENT is reachable (h < delta) and whether
    UNRESOLVED is impossible (h < delta / 2)."""
    _positive(sigma_max=sigma_max, k=k, delta=delta, factor=factor)
    if not 0 < share_type_a < 1:
        raise ValueError("share must be in (0, 1)")
    s = sigma_max * math.sqrt(share_type_a * factor ** 2 + (1 - share_type_a))
    h = k * s
    return {"sigma": s, "h": h, "R_stop_below": math.exp(-h), "equivalent_reachable": _cmp(h, delta),
            "unresolved_impossible": _cmp(h, delta / 2)}


def _cmp(h: float, limit: float, rtol: float = 1e-6) -> str:
    """"yes" if h < limit, "boundary" if h equals limit within rtol (the planning point itself; lane-25 inputs are
    stored to about 8 significant digits), else "no"."""
    if abs(h - limit) <= rtol * limit:
        return "boundary"
    return "yes" if h < limit else "no"


# ----------------------------------------------------------------------------------------------------------------------
# references
# ----------------------------------------------------------------------------------------------------------------------
REFERENCES = [
    {"id": "REF-POLK2017", "citation": "J. E. Polk, A. Pancotti, T. Haag, S. King, M. Walker, J. Blakely, J. Ziemer, "
     "'Recommended Practice for Thrust Measurement in Electric Propulsion Testing', J. Propulsion and Power 33(3):539-555 "
     "(2017), doi:10.2514/1.B35564", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7839308/",
     "access": "full text (PMC) read through the fetch tool on 2026-09-27; statements paraphrased from the tool's "
     "extraction (stand types, end-to-end in-situ calibration, >= 10 calibrations, thermal shrouds/active cooling, zero "
     "before and after, active inclination control, line/cable tares, magnetic tare); exact wording: verify"},
    {"id": "REF-SNYDER2017", "citation": "J. S. Snyder, J. Baldwin, J. D. Frieman, M. L. R. Walker, N. S. Hicks, "
     "K. A. Polzin, J. T. Singleton, 'Recommended Practice for Flow Control and Measurement in Electric Propulsion "
     "Testing', J. Propulsion and Power 33(3) (2017), doi:10.2514/1.B35644",
     "url": "https://hpepl.ae.gatech.edu/sites/default/files/Journal_Articles/JPP%20V33%20No3%20MayJune2017_MassFlowMeasurement.pdf",
     "access": "full text (authors' lab PDF) read on 2026-09-27; quoted: 'typical uncertainties associated with mass flow "
     "measurement are 1-5% of full scale (FS) ... comparable in magnitude to the 0.6-2% uncertainties observed for direct "
     "thrust measurement'; manufacturer accuracy 'typically 1% full scale'; orientation 'can alter the zero point ... by up "
     "to 0.4% of full scale'; zero 'approximately 0.12% per degree'; 'Calibration tests should be conducted for each "
     "specific gas ... at the inlet pressure and environmental temperature expected'; 'calibrated across the intended flow "
     "scale range'; 'traceable to NIST and performed at least every 12 months'; installed 'in the final configuration'. "
     "The GCF errors it tabulates (Table 2) are for Ar, He, SF6, C2F6, H2, not for N2/O2"},
    {"id": "REF-BROWN2017", "citation": "D. L. Brown, M. L. R. Walker, J. Szabo, W. Huang, J. E. Foster, 'Recommended "
     "Practice for Use of Faraday Probes in Electric Propulsion Testing', J. Propulsion and Power 33(3):582-613 (2017), "
     "doi:10.2514/1.B35696", "access": "as accessed and cited by lane 25 (Table A1, far field > 4 channel diameters); not "
     "re-accessed by this lane"},
    {"id": "REF-DANKANICH2017", "citation": "J. W. Dankanich, M. Walker, M. W. Swiatek, J. T. Yim, 'Recommended Practice "
     "for Pressure Measurement and Calculation of Effective Pumping Speed in Electric Propulsion Testing', J. Propulsion "
     "and Power 33(3) (2017), doi:10.2514/1.B35478", "access": "as accessed and cited by lane 25 (Secs. II.A.2, IV.A, "
     "IV.B, V); not re-accessed by this lane"},
    {"id": "REF-ROVEY2025", "citation": "J. L. Rovey et al., 'Recommended Practice for Use of ExB Probes in Electric "
     "Propulsion Testing', IEPC-2025-483, 39th IEPC, London, 14-19 Sept 2025",
     "url": "https://januselectricpropulsion.ae.gatech.edu/sites/default/files/2025-10/IEPC-2025-483_Rovey.pdf",
     "access": "as accessed and cited by lane 25 (Sec. V.A air example: m/q 32, 28, 16, 14 not all resolved at low energy "
     "without an accelerating bias; CEX correction dominated by background neutral density from ion gauges); not "
     "re-accessed by this lane"},
    {"id": "REF-LEMMER2025", "citation": "K. M. Lemmer, A. J. Thomas, W. Huang, D. M. Goebel, R. B. Lobbia, 'Recommended "
     "Practices for Design and Use of Retarding Potential Analyzers in Electric Propulsion', IEPC-2025-363, 39th IEPC, "
     "London, 14-19 Sept 2025, NASA NTRS 20250008889", "url": "https://ntrs.nasa.gov/citations/20250008889",
     "access": "NTRS record and abstract only (2026-09-27): design, construction, operation, error analysis and data "
     "interpretation for EP plumes, Hall thrusters emphasised; body not read (verify before use)"},
    {"id": "REF-LOBBIA2017", "citation": "R. B. Lobbia, B. E. Beal, 'Recommended Practice for Use of Langmuir Probes in "
     "Electric Propulsion Testing', J. Propulsion and Power 33(3):566-581 (2017), doi:10.2514/1.B35531",
     "access": "metadata only (search result, 2026-09-27); the DTIC copy returned HTTP 403 and was not bypassed; content "
     "not read (verify)"},
    {"id": "REF-XU2009", "citation": "K. G. Xu, M. L. R. Walker, 'High-power, null-type, inverted pendulum thrust stand', "
     "Rev. Sci. Instrum. 80(5):055103 (2009)", "url": "https://pubs.aip.org/aip/rsi/article-abstract/80/5/055103/282363",
     "access": "abstract only (search result, 2026-09-27): null-type inverted pendulum, thrusters up to 250 kg, 1 mN to "
     "5 N range, electromagnetic damping, closed-loop inclination, active cooling; an example of the principle, not a "
     "specification for H-1 (verify)"},
    {"id": "REF-CHOUEIRI2001", "citation": "E. Y. Choueiri, 'Plasma oscillations in Hall thrusters', Physics of Plasmas "
     "8(4):1411-1426 (2001), doi:10.1063/1.1354644", "access": "abstract only (search result, 2026-09-27): oscillations "
     "in the 1 kHz - 60 MHz range reviewed band by band; the PDF returned HTTP 503; band-by-band values not read (verify)"},
    {"id": "REF-GUM2008", "citation": "JCGM 100:2008, 'Evaluation of measurement data - Guide to the expression of "
     "uncertainty in measurement'", "url": "https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf",
     "access": "as accessed and cited by lane 25 (G.4.1 Welch-Satterthwaite, G.4.3 Type B as known); not re-accessed"},
]


# ----------------------------------------------------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------------------------------------------------
L25 = "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"
PKG = "docs/architecture_comparison/experiment_package/experiment_package_v1.json"
PROT = "docs/architecture_comparison/experiment_protocol/protocol_draft.json"
OD = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"


def _l25_value(draft: dict, *path):
    node = draft["derived_numbers"]
    for p in path:
        if p not in node:
            raise KeyError(f"lane-25 derived_numbers missing {'.'.join(map(str, path))}")
        node = node[p]
    return node["value"]


def _threshold(draft: dict, tid: str):
    for t in draft["thresholds"]:
        if t["id"] == tid:
            return t["value"]
    raise KeyError(f"lane-25 threshold {tid} missing")


def _l25q(draft: dict, *path, unit: str | None = None) -> dict:
    node = draft["derived_numbers"]
    for p in path:
        node = node[p]
    return q(node["value"], unit or node["unit"], "model-derived",
             f"{L25}: derived_numbers.{'.'.join(map(str, path))} (lane 25, minexp_numbers.py)", exact=True)


def requirement_basis(draft: dict, rfp) -> dict:
    ns = [str(n) for n in (4, 6, 8)]
    for n in ns:
        if n not in draft["derived_numbers"]["plan_by_n"]:
            raise KeyError(f"lane-25 plan_by_n lacks n = {n}")
    return {
        "note": "Relative per-reading and per-installation targets are lane 25's (model-derived from its PROPOSED T-DELTA, "
                "T-ALPHA-FW, T-BUDGET-SHARES, T-N-MIN/MAX, K); the n actually used is fixed at LOCK-2 by readiness_n() from "
                "measured S1 values. RFP values are hard limits (abep_sim/constants.py RFP).",
        "rfp": {
            "thrust_min": q(rfp.RFP.thrust_min_mN, "mN", "assumed",
                            "RFP Part III Para 2 via abep_sim/constants.py RFPConstraints.thrust_min_mN (requirement, not a "
                            "measurement)", status="RFP"),
            "thrust_capability": q(rfp.RFP.thrust_max_mN, "mN", "assumed",
                                   "RFP Part III Para 2 via abep_sim/constants.py RFPConstraints.thrust_max_mN; the owner "
                                   "disposition calls it the registered 25 mN capability condition", status="RFP"),
            "power_max": q(rfp.RFP.power_max_W, "W", "assumed",
                           "RFP Part III Para 2 via abep_sim/constants.py RFPConstraints.power_max_W (P_bus < 1.5 kW)",
                           status="RFP"),
        },
        "lane25_by_n": {n: {
            "u_T_max": _l25q(draft, "plan_by_n", n, "u_T_max"),
            "u_P_max": _l25q(draft, "plan_by_n", n, "u_P_max"),
            "u_inst_max": _l25q(draft, "plan_by_n", n, "u_inst_max"),
            "sigma_lnR_max": _l25q(draft, "plan_by_n", n, "sigma_lnR_max"),
            "k_primary": _l25q(draft, "plan_by_n", n, "k_primary"),
            "G4_share": _l25q(draft, "plan_by_n", n, "group_share_max", "G4"),
        } for n in ns},
        "lane25_u_src_max_by_f_src": {f: _l25q(draft, "u_source_scale_max_by_f_src", f)
                                      for f in sorted(draft["derived_numbers"]["u_source_scale_max_by_f_src"])},
        "lane25_delta": q(_threshold(draft, "T-DELTA"), "ln-ratio", "assumed",
                          f"{L25}: thresholds T-DELTA (PROPOSED, lane 25)", status="PROPOSED"),
        "lane25_share_type_A_in_campaign": _l25q(draft, "share_by_evaluation", "type_A_in_campaign"),
    }


PROPOSED_THRESHOLDS = [
    {"id": "I-ALPHA-ABS", "name": "one-sided error rate of the absolute gates (T_measured >= 12 mN, 25 mN capability, "
     "P_bus < 1.5 kW)", "value": 0.05, "unit": "-", "evidence_class": "assumed", "status": "PROPOSED",
     "source": "this lane's proposal (same alpha as lane 25 T-ALPHA-SCREEN); not in the RFP",
     "rationale": "a gate is claimed PASS only when the one-sided bound clears the RFP limit"},
    {"id": "I-U-ABS-T", "name": "absolute (calibration-traceable) relative 1-sigma uncertainty of a sustained thrust "
     "reading used for the absolute gate", "value": 0.01, "unit": "relative (1 sigma)", "evidence_class": "assumed",
     "status": "PROPOSED", "source": "this lane's proposal; placed inside the 0.6-2 % range REF-SNYDER2017 reports for "
     "direct thrust measurement (a literature statement about uncertainty, not a specification of any stand)",
     "rationale": "with I-ALPHA-ABS the 12 mN gate then passes from a measured 12.2 mN (derived.absolute_thrust_gate)"},
    {"id": "I-U-ABS-P", "name": "absolute relative 1-sigma uncertainty of the P_bus sum used for the 1.5 kW gate",
     "value": 0.01, "unit": "relative (1 sigma)", "evidence_class": "assumed", "status": "PROPOSED",
     "source": "this lane's proposal; no reference value used", "rationale": "the gate passes below a measured "
     "1476 W (derived.absolute_power_gate); the ledger efficiencies and the reconstructed compressor draw are outside "
     "this number and are carried as conditioning inputs (lane 25 Sec. 6.7)"},
    {"id": "I-U-ID-FLOOR", "name": "I_d offset plus noise floor (1 sigma, within the extinction window) as a fraction "
     "of I_d,ref", "value": 0.01, "unit": "fraction of I_d,ref", "evidence_class": "assumed", "status": "PROPOSED",
     "source": "this lane's proposal: a factor 5 below the smallest THR-EXTINCTION fraction (ext_mean_frac 0.05, "
     "lane 06, itself PROPOSED from P5-N2 rule O1)", "rationale": "keeps the extinction classification an electrical "
     "decision, not a noise decision"},
    {"id": "I-FLOW-CONSERVATIVE", "name": "absolute-gate feed rule: the delivered anode flow must not exceed the "
     "registered W1 test-point flow with one-sided confidence", "value": 0.05, "unit": "one-sided alpha",
     "evidence_class": "assumed", "status": "PROPOSED", "source": "this lane's proposal; not in the RFP",
     "rationale": "thrust demonstrated on more flow than the registered feed state would overstate capability on the "
     "actual delivered feed; the rule makes flow uncertainty conservative"},
]


def _threshold_value(tid: str) -> float:
    for t in PROPOSED_THRESHOLDS:
        if t["id"] == tid:
            return t["value"]
    raise KeyError(tid)


def derived(draft: dict, rfp) -> dict:
    alpha = _threshold_value("I-ALPHA-ABS")
    k1 = k_one_sided(alpha)
    T_gate = rfp.RFP.thrust_min_mN
    T_cap = rfp.RFP.thrust_max_mN
    P_lim = rfp.RFP.power_max_W
    u_grid = (0.005, 0.01, 0.015, 0.02, 0.03, 0.05)          # planning grid (hypothetical), relative 1 sigma

    out = {"k_one_sided": q(k1, "-", "model-derived", _src(f"k_one_sided(I-ALPHA-ABS = {alpha})"))}

    # (1) per-reading thrust and power repeatability in absolute terms at RFP levels
    rep = {}
    for n in ("4", "6", "8"):
        uT = _l25_value(draft, "plan_by_n", n, "u_T_max")
        uP = _l25_value(draft, "plan_by_n", n, "u_P_max")
        rep[n] = {
            "sigma_T_at_12mN": q(abs_sigma(uT, T_gate) * 1e3, "uN (1 sigma, per reading)", "model-derived",
                                 _src(f"abs_sigma(lane-25 u_T_max[n={n}], RFP thrust_min)")),
            "sigma_T_at_25mN": q(abs_sigma(uT, T_cap) * 1e3, "uN (1 sigma, per reading)", "model-derived",
                                 _src(f"abs_sigma(lane-25 u_T_max[n={n}], RFP thrust_max)")),
            "sigma_Pbus_at_1500W": q(abs_sigma(uP, P_lim), "W (1 sigma, per reading)", "model-derived",
                                     _src(f"abs_sigma(lane-25 u_P_max[n={n}], RFP power_max)")),
        }
    out["repeatability_absolute_by_n"] = rep

    # (2) channel-sum lemma: every channel at u <= u_max implies the sum at <= u_max (checked on fixed examples)
    uP4 = _l25_value(draft, "plan_by_n", "4", "u_P_max")
    examples = {"one_dominant": (1000.0, 20.0, 15.0, 5.0), "balanced": (400.0, 300.0, 200.0, 100.0)}
    out["channel_sum_check"] = {name: q(channel_sum_u(list(p), [uP4] * len(p)), "relative (1 sigma)", "model-derived",
                                        _src(f"channel_sum_u({list(p)} W hypothetical, all channels at lane-25 "
                                             f"u_P_max[n=4])"), bound=_r(uP4))
                                for name, p in examples.items()}

    # (3) common-consumer meter scale (G4) vs weight w_c (planning grid, hypothetical allocations)
    g4 = _l25_value(draft, "plan_by_n", "4", "group_share_max", "G4")
    out["consumer_scale_max_by_w_c"] = {str(w): q(consumer_scale_max(g4, w), "relative (1 sigma)", "model-derived",
                                                  _src(f"consumer_scale_max(lane-25 G4 share[n=4], w_c = {w}) "
                                                       f"(planning grid, one consumer carrying the whole share)"))
                                        for w in (0.01, 0.02, 0.05, 0.1, 0.2)}

    # (4) absolute thrust gate and capability condition
    out["absolute_thrust_gate"] = {}
    for u in u_grid:
        g = lower_gate(T_gate, u, k1)
        c = lower_gate(T_cap, u, k1)
        out["absolute_thrust_gate"][str(u)] = {
            "pass_min_12mN": q(g["pass_min"], "mN", "model-derived",
                               _src(f"lower_gate(RFP thrust_min, u = {u} (planning grid), k_one_sided)")),
            "fail_max_12mN": q(g["fail_max"], "mN", "model-derived",
                               _src(f"lower_gate(RFP thrust_min, u = {u}, k_one_sided)")),
            "pass_min_25mN": q(c["pass_min"], "mN", "model-derived",
                               _src(f"lower_gate(RFP thrust_max, u = {u}, k_one_sided)")),
            "fail_max_25mN": q(c["fail_max"], "mN", "model-derived",
                               _src(f"lower_gate(RFP thrust_max, u = {u}, k_one_sided)")),
        }
    # (5) absolute power gate
    out["absolute_power_gate"] = {}
    for u in u_grid:
        g = upper_gate(P_lim, u, k1)
        out["absolute_power_gate"][str(u)] = {
            "pass_max_W": q(g["pass_max"], "W", "model-derived", _src(f"upper_gate(RFP power_max, u = {u}, k_one_sided)")),
            "fail_min_W": q(g["fail_min"], "W", "model-derived", _src(f"upper_gate(RFP power_max, u = {u}, k_one_sided)")),
        }

    # (6) MFC: relative flow uncertainty at a setpoint for a device stated at 1 % FS (REF-SNYDER2017 typical spec)
    out["mfc_relative_u_by_setpoint_fraction"] = {
        str(f): q(mfc_relative_u(0.01, f), "relative (1 sigma treated)", "model-derived",
                  _src(f"mfc_relative_u(0.01 FS (REF-SNYDER2017 'typically 1% full scale'; treated as 1 sigma - "
                       f"verify the certificate's coverage), setpoint fraction {f})"))
        for f in (0.1, 0.2, 0.5, 1.0)}
    out["mfc_orientation_zero_shift_relative"] = {
        str(f): q(mfc_relative_u(0.004, f), "relative (bound)", "model-derived",
                  _src(f"mfc_relative_u(0.004 FS orientation zero shift, REF-SNYDER2017, setpoint fraction {f})"))
        for f in (0.1, 0.2, 0.5, 1.0)}

    # (7) mixture composition from two pure-gas MFCs (planning grid of O2 mass fraction; W1 supplies the real value)
    out["mixture_mass_fraction_u"] = {
        f"w={w}": {f"u={u}": q(mass_fraction_u(w, u, u), "mass fraction (1 sigma, absolute)", "model-derived",
                               _src(f"mass_fraction_u(w = {w} (planning grid, hypothetical), u_N2 = u_O2 = {u})"))
                   for u in (0.005, 0.01, 0.02)}
        for w in (0.1, 0.2, 0.3)}

    # (8) background-gas one-way mass flux (ingestion scale) at the lane-25 planning pressures
    torr = 101325.0 / 760.0
    out["background_one_way_mass_flux"] = {
        gas: {f"{p:.1e} Torr": q(one_way_mass_flux(p * torr, rfp.M_SPECIES[gas], 300.0, rfp.K_B) * 1e6 * 1e-2,
                                 "mg s^-1 per 100 cm^2 of exit area", "model-derived",
                                 _src(f"one_way_mass_flux(p_b = {p:.1e} Torr (lane-25 planning scenarios from "
                                      f"REF-DANKANICH2017 Sec. V, SPT-100/Xe specific), m_{gas} (abep_sim/constants.py), "
                                      f"T = 300 K (assumed wall-temperature gas), k_B) x 1e6 mg/kg x 1e-2 m^2; "
                                      f"stationary-Maxwellian upper-scale estimate, not an ingestion model"))
              for p in (1.0e-5, 1.3e-5, 5.0e-5)}
        for gas in ("N2", "O2")}

    # (9) stop-rule sensitivity to realised per-reading repeatability (n = 4, k held at planning value)
    sig = _l25_value(draft, "plan_by_n", "4", "sigma_lnR_max")
    kp = _l25_value(draft, "plan_by_n", "4", "k_primary")
    delta = _threshold(draft, "T-DELTA")
    share_a = _l25_value(draft, "share_by_evaluation", "type_A_in_campaign")
    out["stop_rule_sensitivity_n4"] = {}
    for f in (1.0, 1.5, 2.0, 3.0):
        s = stop_sensitivity(sig, kp, delta, f, share_a)
        src = _src(f"stop_sensitivity(lane-25 sigma_lnR_max[n=4], k_primary[n=4], T-DELTA, factor = {f}, "
                   f"type_A_in_campaign share)")
        out["stop_rule_sensitivity_n4"][f"x{f}"] = {
            "sigma_lnR": q(s["sigma"], "ln-ratio", "model-derived", src),
            "h": q(s["h"], "ln-ratio", "model-derived", src),
            "R_stop_below": q(s["R_stop_below"], "ratio", "model-derived", src),
            "equivalent_reachable": s["equivalent_reachable"],
            "unresolved_impossible": s["unresolved_impossible"],
        }
    return out


# ----------------------------------------------------------------------------------------------------------------------
# content: decision quantities, validation observables, instruments
# ----------------------------------------------------------------------------------------------------------------------
DECISION_QUANTITIES = [
    {"id": "DQ-RARCH", "name": "R_arch = (T/P_bus)_{rf_hall|ecr_hall} / (T/P_bus)_{hall_only}, paired, same point",
     "phase": "Phase 2", "stages": ["S1", "S2", "S4", "S5", "S6"], "classes": "lane 25 size classes + sign-form stop",
     "requirement_source": "lane 25 plan_by_n (u_T, u_P, u_inst, u_src, G4)"},
    {"id": "DQ-TABS", "name": "T_measured: sustained thrust >= 12 mN on the actual delivered feed (W1 test points), and "
     "the registered 25 mN capability condition", "phase": "Phase 3", "stages": ["S1a", "Phase 3 runs"],
     "classes": "PASS / FAIL / UNRESOLVED (PROPOSED one-sided rule, I-ALPHA-ABS)",
     "requirement_source": "RFP limits + I-U-ABS-T (PROPOSED)"},
    {"id": "DQ-PBUS", "name": "P_bus < 1.5 kW on bus_power_boundary_v1 at the same reading as DQ-TABS",
     "phase": "Phase 3", "stages": ["S1a", "Phase 3 runs"],
     "classes": "PASS / FAIL / UNRESOLVED; lab subset (PARTIAL_BOUNDARY) vs v1 (compressor reconstructed from the ICD)",
     "requirement_source": "RFP limit + I-U-ABS-P (PROPOSED)"},
    {"id": "DQ-SUST", "name": "sustainment classes per condition (SUSTAINED / NOT_SUSTAINED / SUSTAINMENT_MIXED; "
     "ENABLES / DISABLES / NEITHER_SUSTAINED)", "phase": "Phase 1-2", "stages": ["S2", "S4", "S5"],
     "classes": "lane 25 Sec. 9 table; THR-EXTINCTION (lane 06) as the operational extinction definition",
     "requirement_source": "THR-EXTINCTION fractions + I-U-ID-FLOOR (PROPOSED)"},
    {"id": "DQ-KNEE", "name": "Hall-only sustainment knee on N2 (mdot_knee, flow down and up)", "phase": "Phase 1",
     "stages": ["S2"], "classes": "T-OP2-FALLBACK (lane 25)", "requirement_source": "MFC resolution vs knee-scan step "
     "(TBD - requires the W1 flow levels)"},
]

# held-out Hall-transport validation observables named by the owner disposition (workstream W5); W5 decides which are
# pre-registered and with which acceptance criteria
VALIDATION_OBSERVABLES = [
    ("VO-ID", "discharge current I_d"), ("VO-T", "thrust T"), ("VO-BZ", "B(z) at actual coil currents"),
    ("VO-FEED", "feed state (mdot_s, P_feed, T_feed, x_s)"), ("VO-SPECIES", "species fractions"),
    ("VO-IEDF", "ion energy"), ("VO-DIV", "divergence"), ("VO-TENE", "T_e / n_e (if feasible)"),
    ("VO-OSC", "oscillations"), ("VO-IGNEXT", "ignition / extinction limits"),
]

# roles in the traceability matrix
ROLE = {"D": "DECISIVE (enters the decision quantity directly)", "C": "CONDITION (certifies the common condition / "
        "admissibility of the reading)", "S": "SUPPORTING (explains or corrects; never enters the class)",
        "V": "VALIDATION OBSERVABLE (if W5 pre-registers it)"}


def _inst(id_, name, lane25, quantity, principle, refs, requirement, calibration, serves, validation, feasibility,
          notes=None):
    return {"id": id_, "name": name, "lane25_measurements": lane25, "quantity": quantity, "principle": principle,
            "references": refs, "required_uncertainty": requirement, "calibration": calibration, "serves": serves,
            "validation_observables": validation, "feasibility": feasibility, "notes": notes or []}


def instruments(basis: dict, der: dict) -> list:
    b4 = basis["lane25_by_n"]["4"]
    return [
        _inst("INS-01", "thrust stand (inverted-pendulum or torsional, null-type preferred)", ["M1"], "thrust T",
              "displacement or null-force pendulum with end-to-end in-situ calibration under vacuum (REF-POLK2017); "
              "inverted pendulum: compact and sensitive but inclination- and thermally sensitive, needs active leveling; "
              "torsional: response independent of thruster mass, needs a larger chamber (REF-POLK2017). Because the "
              "HW-RF / HW-ECR modules change the mass on the stand between arms, a mass-independent response (torsional) "
              "or a mandatory in-situ re-calibration after every configuration change is required (this lane's reading "
              "of REF-POLK2017; stand choice is W3/owner). Example of a null-type inverted pendulum: REF-XU2009",
              ["REF-POLK2017", "REF-XU2009", "REF-SNYDER2017"],
              {"per_reading_repeatability": {"n4": b4["u_T_max"], "absolute_at_12mN_n4":
                                             der["repeatability_absolute_by_n"]["4"]["sigma_T_at_12mN"],
                                             "absolute_at_25mN_n4":
                                             der["repeatability_absolute_by_n"]["4"]["sigma_T_at_25mN"]},
               "installation_reproducibility": {"n4": b4["u_inst_max"], "note": "shared with INS-02 through ln(T/P_bus); "
                                                "S1b re-mount series (K = 6) measures it"},
               "absolute_for_gate": q(_threshold_value("I-U-ABS-T"), "relative (1 sigma)", "assumed",
                                       "PROPOSED threshold I-U-ABS-T", status="PROPOSED"),
               "range": tbd("H-1 thrust range and mass on stand incl. the RF/ECR modules (W3 hardware definition, planned "
                            "path TBD by fo_hardware_definition); the calibration span must cover "
                            "the expected thrust range (REF-POLK2017), from the knee-scan extinction end to >= 25 mN",
                            "fo_hardware_definition")},
              ["S1a: >= 10 in-situ calibrations with known forces spanning the expected range before and >= 10 after each "
               "operating sequence (REF-POLK2017; lane 06 thrust_cal_before/after_min, PROPOSED)",
               "zero with thruster power and flow off before and after every point visit (REF-POLK2017; lane 25 Sec. 7)",
               "thermal shrouds / active cooling of critical stand components, low-conductivity thruster mount, "
               "thermocouples on the stand (INS-17) (REF-POLK2017)",
               "active inclination control with an inclinometer for an inverted pendulum (REF-POLK2017)",
               "tares: propellant lines (solid metal tubing), power cables, RF coax / waveguide crossing the stand "
               "characterised per configuration; magnetic tare across the Hall and ECR coil-current settings with the "
               "discharge off (REF-POLK2017; lane 06 applies the principle to pre-ionizer feed lines)",
               "force standard traceability class: TBD - requires owner (package TBD 'traceable calibration class')"],
              {"DQ-RARCH": "D", "DQ-TABS": "D", "DQ-PBUS": "-", "DQ-SUST": "S", "DQ-KNEE": "S"}, ["VO-T"],
              {"status": "AT_RISK", "why": "lane 25 needs 0.50 % per-reading repeatability (n = 4) and 0.25 % "
               "re-mount reproducibility of ln(T/P_bus); REF-SNYDER2017 reports 0.6-2 % uncertainties for direct thrust "
               "measurement (absolute, not repeatability, so not directly comparable). At 12 mN the n = 4 target is "
               "about 60 uN (1 sigma). Achievability TBD - requires S1b; if D0 fails the owner widens delta, raises n, "
               "or adopts OPTION-DIVERTER (removes G5)."},
              ["sustained >= 12 mN (DQ-TABS) needs a long dwell: zero drift over the dwell is bounded only by the pre- "
               "and post-dwell zeros; the dwell length and its drift allowance are TBD - requires owner (hold time) and "
               "S1 thermal time constants"]),
        _inst("INS-02", "bus-power metering: one DC channel per bus_power_boundary_v1 component present in the lab",
              ["M2", "M14"], "load-plane DC power per component (V, I simultaneously sampled) and DC input of every lab "
              "generator / supply", "4-wire voltage sense with calibrated shunt or zero-flux current transducer per "
              "channel, simultaneous sampling, same channels and positions in every arm (lane 25 M2; lane 06 "
              "bus_power_boundary components). Decisive P_bus on the contract basis: load-plane power / pre-registered "
              "ledger efficiency (abep_sim/arch_boundary.py bus_power_ledger); lane-06 DC-input metering kept as "
              "measured efficiency evidence (package reconciliation D-10)", ["REF-GUM2008"],
              {"per_channel_repeatability": {"n4": b4["u_P_max"], "why": "if every channel meets u_P,max the sum does "
                                             "too (derived.channel_sum_check)"},
               "absolute_at_1500W_n4": der["repeatability_absolute_by_n"]["4"]["sigma_Pbus_at_1500W"],
               "common_consumer_scale": {"G4_share_n4": b4["G4_share"], "u_c_max_by_w_c":
                                         "derived.consumer_scale_max_by_w_c (w_c needs the LOCK-1 allocation)"},
               "absolute_for_gate": q(_threshold_value("I-U-ABS-P"), "relative (1 sigma)", "assumed",
                                       "PROPOSED threshold I-U-ABS-P", status="PROPOSED")},
              ["S1a: channel calibration against a traceable DC standard (class TBD - requires owner); shunt / transducer "
               "temperature coefficient characterised over the S1 thermal range",
               "DUMMY_LOAD_PICKUP control (lane 06, adopted by the package reconciliation) in S1a: generators into matched "
               "dummy loads with the Hall off, all channels recorded, to bound RF/microwave pickup on DC channels",
               "cathode-to-ground and anode-to-ground potentials recorded every reading (M14)"],
              {"DQ-RARCH": "D", "DQ-TABS": "C", "DQ-PBUS": "D", "DQ-SUST": "S", "DQ-KNEE": "S"}, ["VO-ID"],
              {"status": "TBD", "why": "achievability of 0.50 % per channel is TBD - requires calibration certificates "
               "and S1 data; the v1 P_bus sum needs the compressor draw reconstructed from the upstream ICD "
               "(ABSENT_IN_LAB; lane 06 laboratory_subset); until it exists the power gate is only a PARTIAL_BOUNDARY "
               "result (necessary, not sufficient)"}),
        _inst("INS-03", "net RF / microwave power at the source load plane", ["M3"],
              "rf_source: net RF power at the coil/antenna feed terminals; ecr_source: net microwave power at the "
              "coupling-structure input", "directional coupler with forward and reflected power sensors at the load "
              "plane, or upstream with the matching-network / isolator / cable loss characterised in S1a (evidence class "
              "'reconstructed'); lab generator DC input metered on INS-02 as efficiency evidence only", [],
              {"source_scale_max": basis["lane25_u_src_max_by_f_src"],
               "note": "u_src <= G3 share / f_src; f_src = P_src,bus / P_bus,X needs the LOCK-1 source allocation"},
              ["S1a: sensor and coupler calibration (certificates); load-plane loss characterisation into matched dummy "
               "loads at each P_lo / P_hi and frequency (method TBD - requires the RF / microwave design, W3)",
               "reflected-power check at every reading; mismatch uncertainty carried as Type B"],
              {"DQ-RARCH": "D", "DQ-TABS": "C", "DQ-PBUS": "D", "DQ-SUST": "-", "DQ-KNEE": "-"}, [],
              {"status": "AT_RISK", "why": "the G3 target falls from 3.5 % to 0.9 % as f_src rises from 0.1 to 0.4 "
               "(lane 25); no open reference located by this lane for load-plane net RF / microwave power at that level; "
               "achievability TBD - requires sensor certificates and the S1a characterisation"}),
        _inst("INS-04", "discharge voltage and current, DC and time-resolved", ["M4"],
              "V_d, I_d (mean), I_d(t) waveform, keeper voltage, coil currents",
              "calibrated DC meters (INS-02 channel) plus a wide-band current probe on the discharge line and a "
              "time-synchronised DAQ with anti-alias filtering; the same rate in all arms (lane 06 DIAG-DISCHARGE)",
              ["REF-CHOUEIRI2001"],
              {"mean_I_d": "as INS-02 hall_discharge channel",
               "noise_floor": q(_threshold_value("I-U-ID-FLOOR"), "fraction of I_d,ref", "assumed",
                                 "PROPOSED threshold I-U-ID-FLOOR", status="PROPOSED"),
               "bandwidth": tbd("S1 I_d spectrum on HW-0 (lane 25 M4, lane 06 discharge_sampling_rate); REF-CHOUEIRI2001 "
                                "reviews Hall oscillations over 1 kHz - 60 MHz, so the band to capture is set from the "
                                "measured spectrum, not assumed")},
              ["S1a: probe gain and offset against the calibrated DC channel; DAQ timing against a common time base",
               "archive every trace (lane 25; package: publish what P5 lacked)"],
              {"DQ-RARCH": "C", "DQ-TABS": "C", "DQ-PBUS": "C", "DQ-SUST": "D", "DQ-KNEE": "D"},
              ["VO-ID", "VO-OSC", "VO-IGNEXT"],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "standard electrical measurement; the band is TBD from S1"}),
        _inst("INS-05", "propellant mass flow (anode N2, O2; cathode Xe)", ["M10"], "mdot per species",
              "thermal MFCs, one per pure gas (N2, O2) so that each is calibrated on its own gas; the air-surrogate "
              "composition follows from the flow ratio (derived.mixture_mass_fraction_u) - avoids a mixture gas "
              "correction factor, which REF-SNYDER2017 tabulates only for other gases",
              ["REF-SNYDER2017"],
              {"for_R_arch": "repeatability only: the same MFC at the same setpoint in all arms, so the scale term is common "
                             "to both sides of the ratio",
               "for_T_measured": {"rule": "I-FLOW-CONSERVATIVE", "relative_u_at_setpoint":
                                  "derived.mfc_relative_u_by_setpoint_fraction (1 % FS device: 10 % at 10 % of FS, 1 % "
                                  "at FS); choose FS so every registered point sits high in the range"},
               "knee_scan_resolution": tbd("W1 test-point flows and the lane-25 knee levels (T-KNEE-LEVELS = 5)",
                                           "fo_feed_state_closure")},
              ["calibrate each MFC on its own working gas, installed in the final configuration and orientation, at the "
               "expected inlet pressure and temperature, across the flow range, traceable, at least every 12 months "
               "(REF-SNYDER2017)", "constant-volume (rate-of-rise) or constant-pressure calibrator (REF-SNYDER2017)",
               "adjust any unavoidable GCF to the sensor operating temperature (REF-SNYDER2017)"],
              {"DQ-RARCH": "C", "DQ-TABS": "C", "DQ-PBUS": "-", "DQ-SUST": "C", "DQ-KNEE": "D"}, ["VO-FEED"],
              {"status": "AT_RISK", "why": "REF-SNYDER2017: typical mass-flow uncertainty 1-5 % FS; a low-FS setpoint "
               "inflates the relative value; the absolute gate then carries a flow margin (I-FLOW-CONSERVATIVE)"}),
        _inst("INS-06", "feed pressure at the valve outlet (IF-A5 P_feed)", ["M9"], "static pressure at the thruster-side "
              "valve outlet / anode-distributor inlet", "capacitance manometer (force-per-area sensing; gas-type "
              "independent in principle - verify on the certificate) at the IF-A5 plane", [],
              {"value": tbd("W1 registered P_feed tolerance per test point (docs/architecture_comparison/"
                            "feed_state_closure/ planned) and the W5 comparison tolerance", "fo_feed_state_closure")},
              ["S1a: zero at base vacuum; span against a traceable standard; temperature of the head recorded"],
              {"DQ-RARCH": "C", "DQ-TABS": "C", "DQ-PBUS": "-", "DQ-SUST": "S", "DQ-KNEE": "S"}, ["VO-FEED"],
              {"status": "TBD", "why": "with fixed hardware P_feed follows mdot and conductance (lane 25 Sec. 4); a "
               "mismatch with the registered W1 P_feed limits applicability rather than invalidating the reading"}),
        _inst("INS-07", "feed temperature at the valve outlet (IF-A5 T_feed)", [], "gas / line temperature at the IF-A5 "
              "plane", "thermocouple or RTD on the line at the valve outlet (surface temperature; gas temperature "
              "inferred)", [],
              {"value": tbd("W1 registered T_feed tolerance per test point", "fo_feed_state_closure")},
              ["S1a: sensor calibration; line heater state recorded (thermal_control channel)"],
              {"DQ-RARCH": "C", "DQ-TABS": "C", "DQ-PBUS": "-", "DQ-SUST": "-", "DQ-KNEE": "-"}, ["VO-FEED"],
              {"status": "TBD", "why": "surface-to-gas relation is inferred; tolerance TBD from W1"}),
        _inst("INS-08", "facility background pressure and ingestion scale", ["M9"], "p_b (and wall temperature)",
              "hot-cathode ion gauge(s) per REF-DANKANICH2017 Sec. IV.A (near the wall at the exit plane, >= 0.6 chamber "
              "radii off axis, >= 1 m from the thruster OD, >= 10 Hz, 3 s averages, no reading within 2 min of a > 10 % "
              "flow change); calibrated on the working gas and on the O2/N2 mixture", ["REF-DANKANICH2017"],
              {"p_b_max": tbd("T-PB-MAX (owner at LOCK-1, facility specification)", "owner"),
               "ingestion_scale": "derived.background_one_way_mass_flux x the H-1 exit area (TBD - requires W3) / anode "
                                  "flow (TBD - requires W1); a scale, not a correction: no ingestion model is applied to "
                                  "rescue a class (lane 25 Sec. 8)"},
              ["gauge calibration on each gas and mixture (package REQ-FAC-03); calibration interval per the package",
               "S5 elevated-p_b check by downstream injection (REF-DANKANICH2017 Sec. IV.B, lane 25)"],
              {"DQ-RARCH": "C", "DQ-TABS": "C", "DQ-PBUS": "-", "DQ-SUST": "C", "DQ-KNEE": "C"}, ["VO-FEED"],
              {"status": "TBD", "why": "gas-specific gauge response for O2/N2 mixtures needs calibration; for the "
               "absolute gate the p_b sensitivity (S5 slope) is reported with T_measured (PROPOSED rule in the MD)"}),
        _inst("INS-09", "B(z) mapping at actual coil currents", ["M11"], "axial (and radial) magnetic field along the "
              "channel centreline and exit region; coil currents", "Hall-probe gaussmeter on a positioning stage, every "
              "configuration (HW-0, HW-RF, HW-ECR; ECR magnet on/off), before and after the campaign, at the operating "
              "coil currents; coil currents metered on INS-02 (hall_magnet, ecr_magnet)", [],
              {"value": tbd("the W5 pre-registered B(z) comparison tolerance (fo_hall_validation_prereg_draft; path TBD "
                            "by that workstream) and the H-1 design range (W3)",
                            "fo_hall_validation_prereg_draft")},
              ["S1a: probe calibration in a reference field; stage position calibration; room-temperature mapping "
               "(hot-state effects TBD, lane 25 Sec. 12)"],
              {"DQ-RARCH": "C", "DQ-TABS": "S", "DQ-PBUS": "-", "DQ-SUST": "S", "DQ-KNEE": "S"}, ["VO-BZ"],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "magnetostatic; the P5 non-identifiability (CLAUDE.md) is the "
               "reason it is mandatory with coil currents"}),
        _inst("INS-10", "stability / extinction / ignition detection", ["M4"], "per-dwell extinction flag, restarts, "
              "ignition success within timeout", "applies THR-EXTINCTION (lane 06, same functional form as P5-N2 rule "
              "O1: mean I_d < 0.05 I_ref AND >= 90 % of samples < 0.1 I_ref over the window) to INS-04 traces; ignition "
              "attempts per the package D-13 module", [],
              {"floor": "I-U-ID-FLOOR (PROPOSED)", "window": tbd("ext_window from the S1 oscillation band (lane 06)")},
              ["validated on S1 traces with commanded shutdowns (known extinctions) before any score-bearing reading"],
              {"DQ-RARCH": "C", "DQ-TABS": "C", "DQ-PBUS": "-", "DQ-SUST": "D", "DQ-KNEE": "D"}, ["VO-IGNEXT", "VO-OSC"],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "a logic on INS-04 data; thresholds PROPOSED"}),
        _inst("INS-11", "residual gas analyser (RGA)", ["M13"], "background and feed composition (O2 fraction, "
              "contaminants)", "quadrupole RGA on the chamber (and, if practical, a differentially pumped sample of the "
              "feed line)", [],
              {"value": tbd("a W5 decision on whether feed composition is a validation observable; RGA is qualitative "
                            "unless calibrated on the mixture")},
              ["calibrate against known N2/O2 mixtures from the INS-05 flows"],
              {"DQ-RARCH": "S", "DQ-TABS": "S", "DQ-PBUS": "-", "DQ-SUST": "-", "DQ-KNEE": "-"}, ["VO-FEED"],
              {"status": "OPTIONAL", "why": "no reference located by this lane; qualitative O2 background check"}),
        _inst("INS-12", "optical emission spectroscopy (OES)", ["M13"], "emitting species in source / interstage / "
              "plume", "spectrometer with fibre view of the source and interstage", [],
              {"value": tbd("a W5 decision; qualitative only unless a collisional-radiative model is admitted")},
              ["wavelength and relative intensity calibration"],
              {"DQ-RARCH": "S", "DQ-TABS": "-", "DQ-PBUS": "-", "DQ-SUST": "S", "DQ-KNEE": "S"}, ["VO-SPECIES"],
              {"status": "OPTIONAL", "why": "qualitative (lane 25 M13); no quantitative species fraction without a "
               "model this project has not admitted"}),
        _inst("INS-13", "ExB probe (ion species / charge-state current fractions)", ["M7"], "N2+, N+, O2+, O+ (and "
              "multiply charged) current fractions", "Wien filter with an accelerating bias for low-energy interstage "
              "ions (REF-ROVEY2025 as cited by lane 25)", ["REF-ROVEY2025"],
              {"value": tbd("W5 pre-registered species-fraction tolerance; the CEX correction is dominated by the background "
                            "neutral density, whose ion-gauge uncertainty is typically 10-20 % (REF-ROVEY2025 via lane "
                            "25); 10-20 % is that density's uncertainty, not the correction's")},
              ["mass-resolution check on known ions; same analysis code for all arms (lane 06 DIAG-EXB)"],
              {"DQ-RARCH": "S", "DQ-TABS": "-", "DQ-PBUS": "-", "DQ-SUST": "-", "DQ-KNEE": "-"}, ["VO-SPECIES"],
              {"status": "AT_RISK", "why": "at low energy the four air ions are not all resolved without an "
               "accelerating bias (REF-ROVEY2025 via lane 25)"}),
        _inst("INS-14", "retarding potential analyzer (RPA)", ["M6"], "ion energy distribution (interstage / channel "
              "exit in S3, far field in S4)", "multi-grid RPA, same analyzer and position for all arms",
              ["REF-LEMMER2025"],
              {"value": tbd("W5 pre-registered ion-energy tolerance; error analysis per REF-LEMMER2025 (abstract only "
                            "read - verify)")},
              ["grid transparency and potential calibration; collector current zero; time-averaged operation"],
              {"DQ-RARCH": "S", "DQ-TABS": "-", "DQ-PBUS": "-", "DQ-SUST": "-", "DQ-KNEE": "-"}, ["VO-IEDF"],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "recommended practice exists (REF-LEMMER2025); tolerance TBD"}),
        _inst("INS-15", "Faraday probes: source-exit collector, cold-transport I_del, far-field array", ["M5", "M8"],
              "I_src, I_del (Hall discharge off), far-field j(theta), beam current, divergence",
              "guarded Faraday probes; far field > 4 channel diameters; ion-saturation bias checked; SEE, gap and "
              "alignment corrections (REF-BROWN2017 Table A1 via lane 25)", ["REF-BROWN2017"],
              {"I_del": "enters the break-even screen (lane 25 S3), not R_arch; u(I_del) never creates a stop candidate",
               "divergence": tbd("W5 pre-registered divergence tolerance; the full practice asks for >= 4 background "
                                 "pressures and 4 distances, the minimum uses fewer and says so (lane 25 M5)")},
              ["probe area measurement; bias sweep; CEX attenuation bound on the collector path (TBD - requires a cited "
               "N2+ on N2 charge-exchange cross section, package REQ-HW-05)"],
              {"DQ-RARCH": "S", "DQ-TABS": "S", "DQ-PBUS": "-", "DQ-SUST": "-", "DQ-KNEE": "-"}, ["VO-DIV"],
              {"status": "AT_RISK", "why": "CEX bound on the collector path needs a cited cross section not yet in the "
               "repository"}),
        _inst("INS-16", "Langmuir probes (T_e, n_e), where feasible", [], "T_e, n_e in the plume / interstage (not "
              "inside the Hall channel)", "single (or double) cylindrical probe; RF compensation in the rf_hall "
              "interstage (from memory - verify against REF-LOBBIA2017)", ["REF-LOBBIA2017"],
              {"value": tbd("a W5 decision on whether T_e/n_e is pre-registered; REF-LOBBIA2017 not read (metadata only)")},
              ["probe area; sweep calibration; RF-compensation check against a dummy-load pickup test"],
              {"DQ-RARCH": "-", "DQ-TABS": "-", "DQ-PBUS": "-", "DQ-SUST": "S", "DQ-KNEE": "S"}, ["VO-TENE"],
              {"status": "AT_RISK", "why": "in-channel probing perturbs the discharge (from memory - verify); RF and "
               "microwave environments complicate interpretation; the owner lists T_e/n_e 'if feasible'"}),
        _inst("INS-17", "temperatures (stand, thruster, magnet circuit, sources, generators, cathode mount)", ["M12"],
              "temperatures and settling", "thermocouples at fixed positions in every arm", ["REF-POLK2017"],
              {"value": tbd("T-SETTLE from S1 thermal time constants (lane 25)")},
              ["thermocouple calibration; stand thermocouples feed the thrust-drift model (REF-POLK2017)"],
              {"DQ-RARCH": "C", "DQ-TABS": "C", "DQ-PBUS": "S", "DQ-SUST": "-", "DQ-KNEE": "-"}, [],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "standard"}),
        _inst("INS-18", "common time base and DAQ", ["M4", "M14"], "time stamps of every channel", "one time base for "
              "power, thrust, I_d(t), pressure and flow channels", [],
              {"value": tbd("skew allowance from the S1 oscillation band")},
              ["timing check with a common trigger in S1a"],
              {"DQ-RARCH": "C", "DQ-TABS": "C", "DQ-PBUS": "C", "DQ-SUST": "C", "DQ-KNEE": "C"}, ["VO-OSC"],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "standard"}),
    ]


def bus_power_channels() -> list:
    """One row per bus_power_boundary_v1 component: how it is obtained in the lab and on v1."""
    rows = {
        "hall_discharge": ("MEASURED", "INS-02 at the anode-cathode terminals (V_d x I_d); lab supply DC input as "
                           "efficiency evidence", "load / ledger efficiency (LOCK-1)"),
        "hall_magnet": ("MEASURED", "INS-02 at the coil terminals; 0 W explicit for a permanent-magnet circuit",
                        "load / ledger efficiency"),
        "cathode_keeper": ("MEASURED", "INS-02 at the keeper terminals", "load / ledger efficiency"),
        "cathode_heater": ("MEASURED", "INS-02 at the heater terminals in the evaluated mode; 0 W explicit when off",
                           "load / ledger efficiency"),
        "flow_control": ("LEDGER_INPUT", "lab MFC electronics are not flight actuators: metered as evidence, booked as a "
                         "LOCK-1 ledger input with evidence class (lane 25 Sec. 5)", "ledger input, same in all arms"),
        "compressor": ("ABSENT_IN_LAB", "no compressor in the lab feed (lane 06 laboratory_subset); never zero, never a "
                       "placeholder", "RECONSTRUCTED from the upstream ICD at each point's flow and composition; "
                       "UNAVAILABLE until supplied (package D-11)"),
        "thermal_control": ("MEASURED_OR_LEDGER", "INS-02 on any propulsion heater present in the lab; otherwise a "
                            "ledger input per arm with evidence class", "load / ledger efficiency"),
        "housekeeping": ("LEDGER_INPUT", "lab controller is not the flight controller", "ledger input, same in all arms"),
        "rf_source": ("MEASURED", "INS-03 net RF power at the load plane; generator DC input on INS-02 as efficiency "
                      "evidence (R_lab only)", "load / ledger efficiency (rf_hall only)"),
        "ecr_source": ("MEASURED", "INS-03 net microwave power at the coupling input; generator DC input on INS-02 as "
                       "efficiency evidence", "load / ledger efficiency (ecr_hall only)"),
        "ecr_magnet": ("MEASURED", "INS-02 at the resonance-coil terminals; 0 W explicit for a permanent magnet",
                       "load / ledger efficiency (ecr_hall only)"),
    }
    out = []
    for comp in V1_COMMON + ("rf_source", "ecr_source", "ecr_magnet"):
        lab, how, v1 = rows[comp]
        archs = [a for a in ARCHITECTURES if comp in V1_COMMON or comp in V1_PREIONIZER[a]]
        out.append({"component": comp, "architectures": archs, "lab_status": lab, "lab_measurement": how,
                    "v1_basis": v1})
    return out


# ----------------------------------------------------------------------------------------------------------------------
# control C5 (A2 addendum): AO/lifetime register v2 W4 provisions and magnet/coil MCQ-W4-* items (revision v1-r2)
# ----------------------------------------------------------------------------------------------------------------------
AOL = "docs/experiments/lifetime_ao/ao_lifetime_register_v2.json"
MCQ = "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json"
HWR_LIVE = "docs/experiments/hardware/hardware_requirements_v1.json"          # W3's live file (never pinned here)
HWR = "docs/experiments/instrumentation/snapshots/w3_hardware_requirements_v1_at_9a33979.json"   # pinned snapshot
HWR_SNAPSHOT = {"snapshot": HWR, "source_path": HWR_LIVE,
                "source_commit": "9a33979c5198a04cbbc8abdd988e9578aa589b1a",
                "reproduce": "git show 9a33979c5198a04cbbc8abdd988e9578aa589b1a:" + HWR_LIVE,
                "why": "W3 pins this file (instrumentation_definition_v1.json); W4 pinning W3's live bytes created a "
                       "pin cycle (each re-pin changes the other's bytes). W4 therefore pins an immutable historical "
                       "snapshot of the W3 register (the W3 integration-review version that adds HW-C1-09), the same "
                       "pattern as the AO register v2 pin. W3 may now re-pin W4 once and the pair settles; a later W3 "
                       "change reaches W4 only through a deliberate new snapshot and a new W4 revision."}
A2 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A2_execution_directive.json"
TL_SCHEMA = "schemas/thermal_life/inputs_v1.json"
REPAIR_BASE_COMMIT = "af6e4948605081f6cab761ce3a74f67658738e44"

# instrument id -> provisions it adopts (AOL-* rows of the register's W4 interface table, MCQ-W4-*); instruments not
# listed trace to none. Adopted ids in the C5 table are DERIVED from this map and from PROCEDURES (never typed twice).
INSTRUMENT_PROVISIONS = {
    "INS-02": ["MCQ-W4-02"],
    "INS-04": ["AOL-CX-01", "MCQ-W4-02"],
    "INS-09": ["AOL-PM-08", "MCQ-W4-03"],
    "INS-10": ["AOL-CX-06"],
    "INS-11": ["AOL-CX-03"],
    "INS-18": ["AOL-CX-01", "AOL-CX-02", "AOL-CX-05", "AOL-CX-06", "AOL-DC-01"],
    "INS-19": ["AOL-WC-01", "AOL-WC-06", "AOL-PM-01", "AOL-PM-02"],
    "INS-20": ["AOL-WC-01", "AOL-WC-06", "AOL-PM-01", "AOL-PM-04", "AOL-PM-05", "AOL-PM-08"],
    "INS-21": ["AOL-RC-02", "AOL-PM-01", "AOL-PM-06"],
    "INS-22": ["AOL-CX-03"],
    "INS-23": ["AOL-CX-04", "AOL-CX-07"],
    "INS-24": ["MCQ-W4-01", "MCQ-W4-02", "MCQ-W4-03"],
}

C5_REFERENCES = [
    {"id": "REF-CIFALI2011", "citation": "G. Cifali, T. Misuri, P. Rossetti, M. Andrenucci, D. Valentian, D. Feili, "
     "B. Lotz, 'Experimental characterization of HET and RIT with atmospheric propellants', IEPC-2011-224 (2011)",
     "url": "https://electricrocket.org/IEPC/IEPC-2011-224.pdf",
     "access": "as accessed and cited by the AO/lifetime register v2 (source CIFALI2011; anode resistance increase from "
     "oxidation named as the main endurance concern, p. 5, per AOL-RC-02); not re-accessed by this lane"},
    {"id": "REF-DEGROH2006", "citation": "K. K. de Groh, B. A. Banks, C. E. McCarthy, R. N. Rucker, L. M. Roberts, "
     "L. A. Berger, 'MISSE PEACE Polymers Atomic Oxygen Erosion Results', NASA/TM-2006-214482 (2006)",
     "url": "https://ntrs.nasa.gov/api/citations/20070002707/downloads/20070002707.pdf",
     "access": "as accessed and cited by the AO/lifetime register v2 (source DEGROH2006; dehydrated-mass rationale, "
     "moisture uptake of Kapton, p. 3, per AOL-PM-02); not re-accessed by this lane"},
    {"id": "REF-JANKOVSKY1999", "citation": "R. S. Jankovsky, 'Preliminary Evaluation of a 10 kW Hall Thruster', "
     "NASA/TM-1999-209075, AIAA-99-0456", "url": "https://ntrs.nasa.gov/api/citations/19990046494/downloads/"
     "19990046494.pdf", "access": "as accessed and cited by the magnet/coil qualification lane (4-wire potential-probe "
     "coil resistance for average winding temperature, p. 4, per MCQ-W4-01); not re-accessed by this lane"},
    {"id": "REF-KAMHAWI2013", "citation": "H. Kamhawi et al., 'Performance and Thermal Characterization of the "
     "NASA-300MS 20 kW Hall Effect Thruster', IEPC-2013-444 (NTRS 20140017775)",
     "url": "https://ntrs.nasa.gov/api/citations/20140017775/downloads/20140017775.pdf",
     "access": "as accessed and cited by the magnet/coil qualification lane (thermocouples at coil positions, pp. 11, "
     "21, per MCQ-W4-01); not re-accessed by this lane"},
]


def c5_instruments(der: dict) -> list:
    """New instruments adopting the W4 parts of the AO/lifetime register v2 and MCQ-W4-* (control C5)."""
    none = {"DQ-RARCH": "-", "DQ-TABS": "-", "DQ-PBUS": "-", "DQ-SUST": "-", "DQ-KNEE": "-"}
    sust = dict(none, **{"DQ-SUST": "S"})
    return [
        _inst("INS-19", "witness-coupon and part mass metrology (dehydrated protocol)", [], "mass of every witness "
              "coupon (plume array, controls, cathode-vicinity, magnetic-circuit, interstage), anode, wall ring and C-1 "
              "keeper, at baseline and after each removal", "analytical balance in the metrology lab under the "
              "dehydrated protocol INS-P-03 (vacuum desiccation for a fixed time, repeated readings averaged, room "
              "temperature and humidity logged, identical pre and post), coded sample ids (INS-P-01)",
              ["REF-DEGROH2006"],
              {"value": tbd("a mass-change detection limit: no admitted source gives an expected N/O-environment mass "
                            "change for the H-1 wall, anode or pole grades (AO register v2: no N/O yield on BN, BN-SiO2 "
                            "or SiC), so the requirement is set from the demonstrated repeatability of a control coupon "
                            "(AOL-PM-02) before S1 and reported as a detection limit, not a target",
                            "metrology lab + S1")},
              ["balance calibration at each session (owner addendum A3): SI-traceable microbalance calibration with "
               "OIML E2 or better certified reference masses where appropriate (OIML R111 certificates and "
               "traceability), performed by an ISO/IEC 17025-accredited laboratory with this measurement inside its "
               "accredited scope; lab not yet named (W4 measurement specification first, then procurement)", "control-coupon repeatability demonstration before S1 (AOL-PM-02 verification)",
               "lab-stored control coupon weighed in every session (AOL-WC-06 control (d))"],
              none, [],
              {"status": "TBD", "why": "achievable resolution relative to the (unknown) plume-induced mass change is "
               "not known; hygroscopic items (polymers, BN) need the dehydrated protocol (AO register v2 AOL-PM-02)"},
              ["adopts the W4 (metrology) part of AOL-WC-01; the holder is W3 HW-SVC-06"]),
        _inst("INS-20", "surface, profile and post-test inspection metrology", [], "surface profile against fiducials, "
              "morphology and deposits (SEM/EDS), oxidation state and depth profile (XPS), photographs; C-1 orifice "
              "diameter and keeper-face profile; pole-face inspection", "external metrology lab: stylus or optical "
              "profilometry against the W3 fiducials (HW-H1-11), SEM/EDS, XPS with sealed dry transfer and custody "
              "record, calibrated optical measurement of the orifice diameter, photographs under fixed lighting; the "
              "same instruments and operators (coded ids) pre and post", [],
              {"value": tbd("per-technique uncertainty from the metrology lab's calibration records; the profile "
                            "resolution needed follows from the erosion depth to be resolved, which no admitted source "
                            "gives for the H-1 wall grade in N/O (AO register v2); report as detection limits",
                            "metrology lab")},
              ["profilometer calibration / verification with traceable surface standards consistent with ISO 25178-700 "
               "(owner addendum A3)",
               "quantitative SEM/EDS by a documented method consistent with ASTM E1508; XPS energy-scale calibration "
               "per ISO 15472 or an equivalent traceable procedure (owner addendum A3); each recorded with the report",
               "performed by an ISO/IEC 17025-accredited laboratory with the measurement inside its accredited scope "
               "(A3); lab not yet named (W4 measurement specification first, then procurement)", "baseline before first ignition for every serialized item (INS-P-02)"],
              none, [],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "standard laboratory techniques; needs a metrology lab "
               "(not chosen) and sealed-transfer custody (INS-P-04)"},
              ["adopts the W4 parts of AOL-WC-01, AOL-PM-01, AOL-PM-04, AOL-PM-05 (with W3 HW-C1-08) and the pole-face "
               "inspection of AOL-PM-08 (with W3 HW-MC-06)"]),
        _inst("INS-21", "anode resistance (4-wire) and insulation resistance", [], "anode-to-terminal resistance via "
              "the W3 sense lead (HW-ELEC-04); insulation resistance of the anode isolator, coils and harness",
              "4-wire (Kelvin) resistance measurement through the HW-ELEC-04 sense lead between blocks, discharge "
              "off; insulation-resistance tester at a test voltage within the HW-ENV-01 rating (voltage TBD - W3)",
              ["REF-CIFALI2011"],
              {"value": tbd("S1 baseline scatter of the anode resistance (sets the AOL-PT-02 trigger, LOCK-2) and the "
                            "W3 isolator / coil insulation specification", "S1 + fo_hardware_definition")},
              ["meter calibration against traceable resistance standards (class TBD - requires owner)",
               "lead-resistance and contact check with the sense lead shorted at the feedthrough at baseline",
               "measured at baseline, every phase boundary and campaign end (INS-P-06)"],
              sust, [],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "standard electrical measurement once HW-ELEC-04 exists; "
               "the trigger threshold is TBD until the S1 scatter exists"},
              ["closes the review finding 'INS-04 has no anode-resistance measurement' without changing INS-04"]),
        _inst("INS-22", "near-cathode gas sampling point to the RGA (extends INS-11)", [], "O2 / H2O / N2 partial "
              "pressures near C-1 during O-bearing operation (a proxy: the emitter-region O partial pressure is not "
              "measurable directly)", "sampling tube with its inlet at a fixed recorded position near C-1 (outside the "
              "cathode plume core, identical in every arm) feeding the INS-11 RGA; switched against the chamber "
              "sample and logged on INS-18", [],
              {"value": tbd("W5 / owner decision on whether the near-cathode proxy is quantitative; calibration of O2 "
                            "and H2O response at the sampling point (AOL-CX-03: 'calibration TBD')")},
              ["calibrate the sampled O2 and N2 response against known mixtures from the INS-05 flows; H2O response "
               "method TBD - requires the RGA and facility choice", "record the sampling-line transit delay against "
               "INS-18 with a flow step",
               "owner addendum A3: quantitative for the AO/lifetime programme (at least O2 / N2 / H2O partial "
               "pressures or a calibrated response); before any score-bearing or life use the relevant species are "
               "calibrated or traceable sensitivity factors are established"],
              sust, ["VO-FEED"],
              {"status": "AT_RISK", "why": "a sampled partial pressure near the cathode is a proxy for the emitter "
               "region (AO register v2 AOL-CX-03 rationale); H2O calibration method not identified by this lane"},
              ["closes the review finding 'INS-11 has no near-C-1 sampling point' without changing INS-11",
               "data-use rule (owner addendum A3): an uncalibrated near-cathode RGA record is QUALITATIVE and usable "
               "only for S1a engineering checkout; it never supports an exposure-dose or lifetime claim; every record "
               "carries its calibration state (calibrated species / sensitivity-factor reference, or 'uncalibrated')"]),
        _inst("INS-23", "life-mechanism and C-1 emitter / cathode-tube temperatures (extends INS-17)", [],
              "temperatures of the anode, each exit-region wall ring, next to each witness coupon (HW-H1-12 positions), "
              "and the C-1 cathode tube (mandatory) and emitter (only where a pyrometer view exists) during firing",
              "thermocouples at the fixed W3 positions (HW-H1-12, identical in every arm); C-1 (owner addendum A3, W3 "
              "HW-C1-09): a cathode-tube thermocouple is MANDATORY and logged continuously on INS-18; an emitter "
              "pyrometer is added only if HW-C1-09 (b) records a defensible line of sight and an emissivity treatment",
              [],
              {"value": tbd("the temperature resolution the oxidation / sputter-yield evidence needs (lane 32, lane 15 "
                            "limits) and the LaB6 temperature bands cited in W3 HW-C1-03; pyrometer emissivity "
                            "uncertainty TBD - requires the emitter material and view", "fo_hardware_definition")},
              ["thermocouple calibration and cold-junction check (as INS-17)", "pyrometer (if used) calibrated "
               "against a thermocouple on a reference body at the emitter temperature range; emissivity treatment "
               "recorded (from the HW-C1-09 (b) C-1 design record)"],
              sust, [],
              {"status": "AT_RISK", "why": "the emitter temperature is measured only if the C-1 design gives a "
               "defensible pyrometer view (HW-C1-09 (b), not yet decided); a cathode-tube thermocouple gives the "
               "tube, not the emitter (owner addendum A3)"},
              ["closes the review finding that no temperature channel is placed near the cathode (INS-17 is unchanged; "
               "the finding named INS-14, which is the RPA)",
               "labelling rule (owner addendum A3, W3 HW-C1-09 (c)): the thermocouple channel is recorded as "
               "'cathode-tube temperature' and never as emitter temperature; without a pyrometer the emitter "
               "temperature is reported as 'unmeasured' (no value inferred from the tube reading)"]),
        _inst("INS-24", "coil winding temperature and coil electrical record", [], "average winding temperature per "
              "coil (4-wire potential-probe resistance), hot-spot temperatures (thermocouples at the predicted hot "
              "spots), coil current and voltage per reading", "4-wire coil resistance from the INS-02 hall_magnet / "
              "ecr_magnet V and I at the coil terminals (potential probes at the winding) converted by the coil's "
              "own R(T) (the magnet/coil lane records the method and the copper alpha source); embedded thermocouples "
              "at the predicted hot spots; the hot-spot minus average offset is measured, not assumed",
              ["REF-JANKOVSKY1999", "REF-KAMHAWI2013"],
              {"value": tbd("coil hot-spot margin to the insulation class of the selected magnet wire (magnet/coil "
                            "qualification MCQ-QT-06) and the H-1 thermal model (lane 15 hall_magnet inputs)",
                            "fo_magnet_coil_qualification + fo_hardware_definition")},
              ["R0 and T0 of each coil measured isothermally before S1 (reference resistance at a recorded temperature)",
               "thermocouples calibrated as INS-17", "coil V/I channels are INS-02 channels (same calibration)"],
              dict(none, **{"DQ-PBUS": "S"}), ["VO-BZ"],
              {"status": "FEASIBLE_IN_PRINCIPLE", "why": "the method was used on NASA Hall thrusters (as cited by the "
               "magnet/coil lane); hot-spot placement needs the W3 coil design"}),
    ]


PROCEDURES = [
    {"id": "INS-P-01", "name": "witness lot, control coupons and coupon/part register",
     "provisions": ["AOL-WC-06", "AOL-DC-01"],
     "statement": "Every witness lot carries four controls: (a) facility-background (chamber wall), (b) beam-dump-facing, "
                  "(c) shadowed (on the W3 HW-SVC-06 holder) and (d) lab-stored. A register records serial, lot "
                  "(HW-H1-14), material, position, install/remove timestamps and cumulative exposure per feed "
                  "composition, arm and block (from INS-18); metrology operators receive coded sample ids (PROPOSED). "
                  "Kept under the W5 data-custody plan.",
     "instruments": ["INS-18", "INS-19", "INS-20"],
     "required_uncertainty": "n/a (register); timestamps on the INS-18 time base",
     "calibration": "register audit before LOCK-2 (AOL-DC-01 verification)",
     "open": "positions of controls (a) and (b) are facility items: TBD - requires the facility choice (S1-readiness "
             "condition 'facility chosen')"},
    {"id": "INS-P-02", "name": "baseline metrology before first ignition", "provisions": ["AOL-PM-01"],
     "statement": "Every witness coupon, replaceable part (anode HW-H1-10, wall rings HW-H1-11), and the C-1 keeper is "
                  "measured before first ignition: mass (INS-19), profile, SEM/EDS, XPS as listed per item and "
                  "photographs (INS-20), anode resistance (INS-21); instrument, uncertainty and operator recorded.",
     "instruments": ["INS-19", "INS-20", "INS-21"],
     "required_uncertainty": "as INS-19 / INS-20 / INS-21 (TBD, detection limits)",
     "calibration": "per instrument", "open": "metrology lab not chosen"},
    {"id": "INS-P-03", "name": "dehydrated mass protocol", "provisions": ["AOL-PM-02"],
     "statement": "Hygroscopic items (polymers, BN) are weighed after vacuum desiccation for a fixed time, repeated "
                  "readings averaged, room temperature and humidity logged, identically pre and post.",
     "instruments": ["INS-19"],
     "required_uncertainty": "TBD - the control-coupon repeatability demonstrated before S1 is the detection limit",
     "calibration": "desiccation time, pressure and number of readings: TBD - requires the metrology lab and a pre-S1 "
                    "repeatability trial (no value is assumed here)",
     "open": "parameters TBD (AOL-PM-02 leaves them to W4 / metrology lab)"},
    {"id": "INS-P-04", "name": "post-test surface analysis and sample custody", "provisions": ["AOL-PM-04"],
     "statement": "After each removal, SEM/EDS and XPS as listed per item; samples transferred in sealed dry containers "
                  "with a custody record; each report references the item's baseline (INS-P-02).",
     "instruments": ["INS-20"], "required_uncertainty": "as INS-20", "calibration": "as INS-20",
     "open": "container specification TBD - requires the metrology lab"},
    {"id": "INS-P-05", "name": "C-1 post-test inspection", "provisions": ["AOL-PM-05"],
     "statement": "At campaign end or C-1 retirement (disassembly retires the unit, W3 HW-C1-08): orifice diameter, "
                  "keeper-face profile, SEM/EDS and XPS of the insert surface.",
     "instruments": ["INS-20"], "required_uncertainty": "as INS-20", "calibration": "as INS-20",
     "open": "none beyond INS-20"},
    {"id": "INS-P-06", "name": "electrical resistance and insulation schedule", "provisions": ["AOL-RC-02", "AOL-PM-06"],
     "statement": "Anode resistance (4-wire via HW-ELEC-04) and insulation resistance of the anode isolator, coils and "
                  "harness at baseline, every phase boundary and campaign end; the anode resistance also between "
                  "blocks without disassembly.",
     "instruments": ["INS-21"], "required_uncertainty": "as INS-21 (TBD from the S1 baseline scatter)",
     "calibration": "as INS-21", "open": "AOL-PT-02 trigger value TBD (LOCK-2)"},
    {"id": "INS-P-07", "name": "B(z) map record and magnetic-circuit inspection", "provisions": ["AOL-PM-08", "MCQ-W4-03"],
     "statement": "INS-09 maps follow W3 HW-MC-03 (actual coil currents, before/after each configuration's block "
                  "series) and HW-MC-04 (reference sensor during firing; cold re-map after soak); every map record "
                  "carries the coil currents, coil average (INS-24) and hot-spot temperatures and the magnet "
                  "temperatures at the time of mapping, probe calibration and sha256. Pole faces: visual / XPS "
                  "inspection at campaign end (INS-20).",
     "instruments": ["INS-09", "INS-20", "INS-24"],
     "required_uncertainty": "as INS-09 (TBD from the W5 B(z) tolerance)", "calibration": "as INS-09",
     "open": "HW-MC-04 reference-sensor feasibility TBD (W3)"},
    {"id": "INS-P-08", "name": "C-1 logs: daily Xe reference, start log, hot-emitter O-exposure log",
     "provisions": ["AOL-CX-01", "AOL-CX-02", "AOL-CX-05"],
     "statement": "(1) daily keeper and coupling voltage at the fixed Xe reference condition (frozen in LOCK-1; aligns "
                  "W3 HW-C1-03); (2) every C-1 start: heater power, heater time to ignition, keeper ignition voltage, "
                  "outcome; (3) every interval with a hot emitter while O2 is in the chamber or feed, with the Xe "
                  "cathode flow state and interlock states (HW-C1-03 rule). All on the INS-18 time base.",
     "instruments": ["INS-04", "INS-18"],
     "required_uncertainty": "keeper / coupling voltage as the INS-02 / INS-04 channels; AOL-PT-03 shift trigger TBD "
                             "from the S1 day-to-day scatter (LOCK-2)",
     "calibration": "as INS-02 / INS-04", "open": "Xe reference condition: LOCK-1"},
    {"id": "INS-P-09", "name": "extinction and anomaly record", "provisions": ["AOL-CX-06"],
     "statement": "Every spontaneous extinction, ignition failure and anomalous-discharge episode detected by INS-10 is "
                  "time-stamped with feed composition (INS-05 flows, INS-11 / INS-22), the I_d trace (INS-04) and the "
                  "cathode state (INS-P-08 fields). AOL-PT-01 (PROPOSED in the register): a flame-out during "
                  "O-bearing operation stops the block at its end and triggers an anode inspection.",
     "instruments": ["INS-10", "INS-04", "INS-18"], "required_uncertainty": "as INS-10",
     "calibration": "as INS-10", "open": "AOL-PT-01 is an owner confirmation in the register"},
    {"id": "INS-P-10", "name": "life evidence record format (thermal_life measured_hardware)", "provisions": ["AOL-DC-02"],
     "statement": "Every life-relevant measurement (INS-19..INS-24, INS-P-02..INS-P-09) is recorded with the "
                  "measured_hardware evidence_record fields of the pinned schema (listed in c5_adoption."
                  "measured_hardware_fields) so it can later enter abep_sim/thermal_life.py without an admitted "
                  "closure; quantity_type 'measured'.",
     "instruments": ["INS-18"], "required_uncertainty": "n/a (format); the 'uncertainty' field is mandatory",
     "calibration": "schema check of records", "open": "none"},
    {"id": "INS-P-11", "name": "no life extrapolation from an unadmitted closure (control C6)", "provisions": ["AOL-LF-01"],
     "statement": "No H-1 life number is computed here or from these records with a Hall map, a transport screening "
                  "candidate or a withdrawn 0-D result; life statements are measured on H-1, literature for another "
                  "device (labelled), or TBD. This document contains no life number (validate() refuses any quantity with unit 'h').",
     "instruments": [], "required_uncertainty": "n/a", "calibration": "n/a", "open": "none"},
    {"id": "INS-P-12", "name": "witness-holder non-interference check", "provisions": ["AOL-WC-01"],
     "statement": "AOL-WC-01 verification asks that a B(z) re-map and a thrust-stand tare with the HW-SVC-06 holder "
                  "installed show no change beyond W4 instrument uncertainty. W4 answer: the detection limits are the "
                  "INS-09 map repeatability and the INS-01 in-situ calibration repeatability, both measured in S1a; "
                  "the planning value for the thrust side is the lane-25 per-reading target (INS-01 "
                  "required_uncertainty, n = 4). A change is 'beyond' when it exceeds the coverage factor times the "
                  "combined standard uncertainty of the two maps / tares. Owner addendum A3: planning coverage factor "
                  "k = 2 (the ~95 % expanded-uncertainty convention, not a substitute for the measured uncertainty "
                  "model); with low effective degrees of freedom the evaluated coverage factor is used and documented "
                  "with its degrees of freedom.",
     "instruments": ["INS-01", "INS-09"],
     "required_uncertainty": "INS-01 and INS-09 values (no new number)", "calibration": "as INS-01 / INS-09",
     "open": "none for the planning coverage factor (A3: k = 2); the evaluated k and effective degrees of freedom are "
             "documented per test"},
]

# hand disposition per provision; adopted ids are derived. status in ADOPTED / ADOPTED_PARTIAL / NOT_ADOPTED
C5_DISPOSITION = {
    "AOL-WC-01": ("ADOPTED", "metrology (mass INS-19, surface/profile INS-20) and the non-interference detection limit "
                  "(INS-P-12); holder is W3 HW-SVC-06", None),
    "AOL-WC-06": ("ADOPTED_PARTIAL", "register and metrology of all four controls adopted (INS-P-01, INS-19, INS-20)",
                  "positions of the facility-background and beam-dump-facing controls need the facility choice"),
    "AOL-RC-02": ("ADOPTED", "new INS-21 through the W3 HW-ELEC-04 sense lead; schedule INS-P-06", None),
    "AOL-CX-01": ("ADOPTED", "INS-04 / INS-18 channels, INS-P-08 (1)", None),
    "AOL-CX-02": ("ADOPTED", "INS-18 start log, INS-P-08 (2)", None),
    "AOL-CX-03": ("ADOPTED_PARTIAL", "sampling point and log adopted (INS-22 into INS-11)",
                  "H2O calibration method at the sampling point not identified; RGA and facility not chosen"),
    "AOL-CX-04": ("ADOPTED", "INS-23 (cathode-tube thermocouple mandatory, emitter pyrometer only where W3 HW-C1-09 "
                  "gives a view; owner addendum A3)", None),
    "AOL-CX-05": ("ADOPTED", "INS-18 interval log with Xe flow and interlock states, INS-P-08 (3)", None),
    "AOL-CX-06": ("ADOPTED", "INS-10 detection + INS-P-09 record fields", None),
    "AOL-CX-07": ("ADOPTED", "INS-23 at the W3 HW-H1-12 positions (INS-17 unchanged)", None),
    "AOL-PM-01": ("ADOPTED", "INS-P-02 with INS-19 / INS-20 / INS-21", None),
    "AOL-PM-02": ("ADOPTED", "INS-P-03 with INS-19; parameters TBD (no value assumed)", None),
    "AOL-PM-04": ("ADOPTED", "INS-P-04 with INS-20", None),
    "AOL-PM-05": ("ADOPTED", "INS-P-05 with INS-20 (W3 HW-C1-08 makes C-1 inspectable)", None),
    "AOL-PM-06": ("ADOPTED", "INS-P-06 with INS-21", None),
    "AOL-PM-08": ("ADOPTED", "INS-09 per HW-MC-03 / HW-MC-04 plus pole-face inspection (INS-20), INS-P-07", None),
    "AOL-DC-01": ("ADOPTED", "INS-P-01 register, exposure accounting from INS-18", None),
    "AOL-DC-02": ("ADOPTED", "INS-P-10 record format from the pinned thermal_life schema", None),
    "AOL-LF-01": ("ADOPTED", "INS-P-11 compliance; validate() refuses screening-candidate ids and any quantity in hours", None),
    "MCQ-W4-01": ("ADOPTED", "INS-24 (4-wire coil resistance + hot-spot thermocouples)", None),
    "MCQ-W4-02": ("ADOPTED", "INS-02 hall_magnet / ecr_magnet channels record coil V and I simultaneously; INS-04 "
                  "records coil currents; INS-24 uses the same record for R(T)", None),
    "MCQ-W4-03": ("ADOPTED", "INS-P-07 map-record fields (coil currents, coil average and hot-spot temperatures, "
                  "magnet temperatures)", None),
}


# ----------------------------------------------------------------------------------------------------------------------
# owner addendum A3 (still revision v1-r2: additive, no id / value / acceptance rule changed; A3 instrumentation_version)
# ----------------------------------------------------------------------------------------------------------------------
A3 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json"
A3_BASE_COMMIT = "7d373374dcd47eb6c2464423eb5f45a1fa14ef78"

# A3 decision key -> (instrument / procedure ids whose semantics carry it, how)
A3_ADOPTION = {
    "metrology_lab": (["INS-19", "INS-20", "INS-P-02", "INS-P-04", "INS-P-05"],
                      "INS-19 / INS-20 calibration items name the A3 metrology specification (ISO/IEC 17025 accredited "
                      "scope, OIML E2 / R111 reference masses, ISO 25178-700, ASTM E1508, ISO 15472); the procedures "
                      "inherit it; no lab is named (specification first, then procurement)"),
    "cathode_temperature": (["INS-23", "INS-18"],
                            "INS-23: cathode-tube thermocouple mandatory (W3 HW-C1-09 (a)), emitter pyrometer only with "
                            "a HW-C1-09 (b) view; labelling rule in the INS-23 notes; INS-18 logs the tube channel "
                            "continuously and never labels it emitter temperature; emitter reported 'unmeasured' "
                            "without a pyrometer"),
    "near_cathode_rga": (["INS-22", "INS-11"],
                         "INS-22 calibration item (quantitative for AO/lifetime use) and data-use note (uncalibrated = "
                         "qualitative S1a engineering only, never exposure-dose / life evidence); INS-11 note"),
    "ins_p12_coverage_factor": (["INS-P-12"],
                                "INS-P-12 statement: planning k = 2; evaluated k with low effective degrees of freedom, "
                                "documented"),
    "instrumentation_version": ([], "stays instrumentation_definition_v1.json revision v1-r2 (change-log entry "
                                    "'A3'); no schema, measurement-semantics-breaking, acceptance-rule or id-meaning "
                                    "change"),
}

# notes appended to instruments built by instruments() (their other fields are unchanged)
A3_NOTES = {
    "INS-11": ["owner addendum A3 (near_cathode_rga): the INS-22 near-cathode sample through this RGA is quantitative "
               "only after species calibration or traceable sensitivity factors; uncalibrated records are qualitative "
               "S1a engineering data and never exposure-dose or lifetime evidence"],
    "INS-18": ["owner addendum A3 (cathode_temperature, W3 HW-C1-09): the INS-23 cathode-tube thermocouple is logged "
               "continuously during firing under a cathode-tube label; no channel is labelled emitter temperature "
               "unless an INS-23 pyrometer is installed, otherwise the emitter-temperature field is recorded as "
               "'unmeasured'"],
}


def a3_adoption(ins: list) -> dict:
    a3 = _load_json(A3)
    if a3.get("amends") != OD or a3.get("decided_by") != "owner":
        raise InputChanged(f"{A3} does not amend {OD} as an owner decision")
    dec = a3["decisions"]
    if set(dec) != set(A3_ADOPTION):
        raise InputChanged(f"A3 decision keys {sorted(dec)} != adopted {sorted(A3_ADOPTION)}")
    known = {i["id"] for i in ins} | {p["id"] for p in PROCEDURES}
    rows = []
    for key in sorted(A3_ADOPTION):
        ids, how = A3_ADOPTION[key]
        if not set(ids) <= known:
            raise ValueError(f"A3 {key}: unknown id {sorted(set(ids) - known)}")
        rows.append({"decision": key, "owner_text": dec[key], "carried_by": ids, "how": how})
    return {"source": A3, "decided_utc": a3["decided_utc"], "rows": rows,
            "w3_provision": "HW-C1-09 (cathode temperature provision) and HW-C1-07 (b) (near-cathode RGA port) in "
                            + HWR_LIVE + " (read from the pinned snapshot " + HWR + ")",
            "milestones": "supports A (S1a engineering checkout can use the qualitative RGA and the tube "
                          "thermocouple under the labelling rule) and prepares C (quantitative RGA and accredited "
                          "metrology are preconditions for exposure-dose / life evidence); B not affected. Next: "
                          "W4 measurement specification issued to procure an accredited lab; RGA species "
                          "calibration or sensitivity factors before score-bearing / life use; HW-C1-09 (b) view "
                          "decision in the C-1 design release."}


def _walk_ids(obj, out: set):
    if isinstance(obj, dict):
        if isinstance(obj.get("id"), str):
            out.add(obj["id"])
        for v in obj.values():
            _walk_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_ids(v, out)
    return out


def c5_required_provisions() -> dict:
    """provision id -> source record, read from the pinned AO register v2 (W4 interface rows) and MCQ (MCQ-W4-*)."""
    aol = _load_json(AOL)
    req = {r["id"]: r for r in aol["requirements"]}
    out = {}
    for row in aol["interface_table"]["rows"]:
        if row["adopter"] == "W4":
            pid = row["requirement"]
            if pid in out:
                raise ValueError(f"duplicate W4 row {pid}")
            out[pid] = {"source_file": AOL, "w4_target": row["target"], "title": req[pid]["title"],
                        "requirement": req[pid]["requirement"], "register_status_before": row["adoption_status"]}
    for r in _load_json(MCQ)["requirements"]:
        if r["id"].startswith("MCQ-W4-"):
            out[r["id"]] = {"source_file": MCQ, "w4_target": r["verification"], "title": r["id"],
                            "requirement": r["statement"], "register_status_before": "not tracked"}
    return out


def c5_adoption(ins: list) -> dict:
    required = c5_required_provisions()
    if set(required) != set(C5_DISPOSITION):
        raise ValueError(f"C5 provisions differ: register/MCQ {sorted(required)} vs disposition {sorted(C5_DISPOSITION)}")
    ins_ids = {i["id"] for i in ins}
    for iid in INSTRUMENT_PROVISIONS:
        if iid not in ins_ids:
            raise ValueError(f"INSTRUMENT_PROVISIONS names unknown instrument {iid}")
    hw_ids = _walk_ids(_load_json(HWR), set())
    cited_hw = sorted({t for p in PROCEDURES for t in _hw_tokens(p["statement"])} |
                      {t for i in ins for t in _hw_tokens(json.dumps(i))})
    missing_hw = [t for t in cited_hw if t not in hw_ids]
    if missing_hw:
        raise ValueError(f"cited W3 ids not in {HWR}: {missing_hw}")
    schema = _load_json(TL_SCHEMA)
    mh = _find_key(schema, "measured_hardware")
    if not mh or "evidence_record_fields" not in mh:
        raise InputChanged(f"{TL_SCHEMA} has no measured_hardware.evidence_record_fields")
    rows = []
    for pid in sorted(required, key=lambda s: (s.startswith("MCQ"), s)):
        status, how, needs = C5_DISPOSITION[pid]
        ids = sorted([i for i, ps in INSTRUMENT_PROVISIONS.items() if pid in ps] +
                     [p["id"] for p in PROCEDURES if pid in p["provisions"]])
        rows.append({"provision": pid, "title": required[pid]["title"], "source_file": required[pid]["source_file"],
                     "w4_target": required[pid]["w4_target"],
                     "register_status_before": required[pid]["register_status_before"],
                     "status": status, "adopted_ids": ids, "how": how, "needs": needs})
    a2 = _load_json(A2)
    return {"control": "C5_AO_early",
            "control_text": a2["execution_directive_2026_09_27"]["controls_added"]["C5_AO_early"],
            "sources": [AOL, MCQ], "w3_ids_cited_verified_in": HWR, "w3_snapshot": HWR_SNAPSHOT, "w3_ids_cited": cited_hw,
            "measured_hardware_fields": mh["evidence_record_fields"],
            "counts": {s: q(sum(r["status"] == s for r in rows), "provisions", "model-derived", _src("c5_adoption"))
                       for s in ("ADOPTED", "ADOPTED_PARTIAL", "NOT_ADOPTED")},
            "rows": rows,
            "milestones": "supports A (S1-readiness condition 'instrumentation capability demonstrated' now covers the "
                          "C5 provisions) and prepares C (measured life evidence records); B not affected. Next: the "
                          "metrology lab, facility and C-1 view choices, and S1 scatter data for the TBD detection "
                          "limits and triggers (AOL-PT-02, AOL-PT-03)."}


def _hw_tokens(text: str) -> list:
    import re
    return re.findall(r"HW-[A-Z0-9]+-\d+", text)


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


CHANGE_LOG = [
    {"entry": "v1-r1", "revision": "v1-r1", "date": "2026-09-27", "base_commit": "510e464fb8e128e4cf3325572a4d36ad33a4899d",
     "change": "initial W4 instrumentation definition (INS-01..INS-18)"},
    {"entry": "v1-r2/C5", "revision": "v1-r2", "date": "2026-09-27", "base_commit": REPAIR_BASE_COMMIT,
     "change": "control C5 (A2 addendum): adopts the 19 W4 provisions of the AO/lifetime register v2 and MCQ-W4-01..03: "
               "new INS-19..INS-24 and procedures INS-P-01..INS-P-12, c5_adoption table, five new pinned inputs, four "
               "references cited via those lanes; existing ids, values, thresholds and decision quantities unchanged "
               "(only a traces_to_provisions key added to every instrument)",
     "material": False,
     "why_v1": "additive: no existing requirement, threshold, derived number or decision-quantity role changed, so the "
               "file stays instrumentation_definition_v1.json (downstream lanes reference this path)"},
    {"entry": "v1-r2/A3", "revision": "v1-r2", "amendment": "A3", "date": "2026-09-27", "base_commit": A3_BASE_COMMIT,
     "change": "owner addendum A3 applied without changing any id or value: metrology specification (INS-19 / INS-20 "
               "calibration), cathode temperature semantics (INS-23 tube thermocouple mandatory, never labelled "
               "emitter temperature, pyrometer optional, emitter 'unmeasured' without one; INS-18 note; W3 HW-C1-09 "
               "traced), near-cathode RGA data-use rule (INS-22 / INS-11), INS-P-12 planning k = 2; a3_adoption "
               "table; A3 pinned and the W3 hardware definition re-pinned (HW-C1-09 added by the W3 integration "
               "review); four C5 open owner decisions marked decided",
     "material": False,
     "why_v1": "owner addendum A3 decisions.instrumentation_version: keep v1-r2 (additive)"},
    {"entry": "v1-r2/A3-repair", "revision": "v1-r2", "amendment": "A3", "date": "2026-09-27",
     "base_commit": A3_BASE_COMMIT,
     "change": "review repair of the A3 entry: the W3 register is pinned as an immutable snapshot "
               "(snapshots/w3_hardware_requirements_v1_at_9a33979.json, sha256 identical to the W3 file at commit "
               "9a33979) instead of W3's live file, which removes the W3 <-> W4 pin cycle; downstream consumers "
               "whose pins of this file are stale are declared (downstream_repin_required); change-log entries get a "
               "unique 'entry' key (the revision label stays v1-r2 per A3); INS-13 wording: 10-20 % is the "
               "ion-gauge uncertainty of the background neutral density that dominates the CEX correction, not the "
               "correction's uncertainty; Markdown header names both the original and the current base commit",
     "material": False,
     "why_v1": "no id, threshold, derived number or decision-quantity role changed"},
    {"entry": "v1-r2/A3-repair-2", "revision": "v1-r2", "amendment": "A3", "date": "2026-09-27",
     "base_commit": A3_BASE_COMMIT,
     "change": "second review repair: the W3 dependency commit 9a33979 is no longer carried in this branch's history "
               "(W4 relies only on its immutable snapshot, which the snapshot-vs-git test checks when the commit is "
               "available and skips otherwise); lane-25 values copied into requirement_basis are stored bit-for-bit "
               "instead of rounded to 6 significant figures (e.g. k_primary[n=4] 3.1726749, previously 3.17267); "
               "merge-order statement updated",
     "material": False,
     "why_v1": "no id, threshold, derived number or decision-quantity role changed (copied values gain digits only)"},
]

# Consumers outside W4's ALLOWED paths that pin the bytes of this file. Every W4 byte change (including the A3 entry
# and this repair) makes their pins stale; W4 cannot edit them. Their owning lanes / the merge controller re-pin them
# to the sha256 of this file at the W4 lane head (a file cannot contain its own hash). After the snapshot change W4 no
# longer pins W3's live bytes, so a W3 re-pin does not change W4 and the pair settles in one step.
DOWNSTREAM_REPIN = [
    {"file": "docs/experiments/lifetime_ao/ao_lifetime_register_v3.json", "owner": "fo_ao_lifetime_register (v3)",
     "pins": "merged_inputs entries for docs/experiments/instrumentation/instrumentation_definition_v1.json and "
             "INSTRUMENTATION_DEFINITION.md",
     "stale_pin": "4542d26037357cc767c9ce2edc1b2802e040e16b7cc9fa16312730e18fdb441f (JSON, pre-A3); "
                  "f35266c778af134117f56108367c5eefee45ddf6d60ef54b192009abc336b4d5 (Markdown, pre-A3)",
     "test_affected": "tests/test_ao_lifetime_register.py::test_merged_inputs_pinned"},
    {"file": "docs/experiments/hardware/hardware_requirements_v1.json", "owner": "fo_hardware_definition (W3)",
     "pins": "references['SRC-INS-V1R2'].sha256 and w3_integration_review.reviewed_against['SRC-INS-V1R2']",
     "stale_pin": "4542d26037357cc767c9ce2edc1b2802e040e16b7cc9fa16312730e18fdb441f (pre-A3)",
     "test_affected": "tests/test_hardware_definition.py::test_a3_review_traces_exist_in_sources"},
    {"file": "docs/experiments/s1_readiness/s1_readiness_status_current.json", "owner": "fo_s1_readiness_gate",
     "pins": "input sha256 entries for docs/experiments/instrumentation/instrumentation_definition_v1.json",
     "stale_pin": "4542d26037357cc767c9ce2edc1b2802e040e16b7cc9fa16312730e18fdb441f (pre-A3)",
     "test_affected": "regenerate with the S1 readiness builder (status report, not a W4 test)"},
]
MERGE_ORDER = ("This branch carries only W4-authored commits on top of base 7d37337 (the W3 integration-review "
               "commit 9a33979 was removed from this branch's history in the A3-repair-2 review repair). W4's pin of "
               "the W3 register is the immutable snapshot of 9a33979, so W4 merges and verifies independently of W3's "
               "live bytes. The W3 branch (worktree-wf_b92499f0-718-3) is merged and verified by its own lane; the "
               "downstream re-pins listed above are sequenced by the merge controller after both merges.")


def build() -> dict:
    pins = verify_inputs()
    draft = _load_json(L25)
    od = _load_json(OD)
    if od.get("id") != "od_hardware_pivot" or od.get("decision") != "APPROVED":
        raise InputChanged("owner disposition od_hardware_pivot is not APPROVED")
    if "W4_instrumentation" not in od.get("workstreams", {}):
        raise InputChanged("owner disposition lacks workstream W4_instrumentation")
    pkg = _load_json(PKG)
    prot = _load_json(PROT)
    rfp = _load_rfp()
    basis = requirement_basis(draft, rfp)
    der = derived(draft, rfp)
    ins = instruments(basis, der) + c5_instruments(der)
    for i in ins:
        i["traces_to_provisions"] = INSTRUMENT_PROVISIONS.get(i["id"], [])
        i["notes"] = i["notes"] + A3_NOTES.get(i["id"], [])
    c5 = c5_adoption(ins)
    a3 = a3_adoption(ins)
    lane25_ids = [m["id"] for m in draft["measurements"]]
    covered = sorted({m for i in ins for m in i["lane25_measurements"]}, key=lambda s: int(s[1:]))
    if covered != sorted(lane25_ids, key=lambda s: int(s[1:])):
        raise ValueError(f"lane-25 measurements not all covered: {covered} vs {lane25_ids}")
    prot_components = [c["id"] for c in prot["bus_power_boundary"]["components"]]

    doc = {
        "schema": "abep_instrumentation_definition_v1",
        "id": "instrumentation_definition_v1",
        "follow_on": "fo_instrumentation_definition",
        "trigger": "T_PIVOT_INSTRUMENTATION_DEFINITION",
        "owner_disposition": {"id": "od_hardware_pivot", "file": OD, "workstream": "W4_instrumentation",
                              "statement": od["workstreams"]["W4_instrumentation"]},
        "status": "DRAFT_PENDING_OWNER",
        "base_commit": BASE_COMMIT,
        "version": "v1",
        "revision": CHANGE_LOG[-1]["revision"],
        "repair_base_commit": REPAIR_BASE_COMMIT,
        "change_log": CHANGE_LOG,
        "downstream_repin_required": {"consumers": DOWNSTREAM_REPIN, "merge_order": MERGE_ORDER,
                                      "w3_snapshot": HWR_SNAPSHOT},
        "generated_by": SCRIPT_REL,
        "companion_document": "docs/experiments/instrumentation/INSTRUMENTATION_DEFINITION.md",
        "not_locked": "Nothing here is pre-registered, locked or decided. Thresholds not in the RFP are PROPOSED. No "
                      "score-bearing reading before LOCK-1 and LOCK-2 (lane 25 Sec. 10). Instrument choices are "
                      "principles, not product selections; no instrument accuracy is claimed.",
        "compliance": [
            "no Hall transport closure, screening candidate or withdrawn 0-D number is used; no retuning",
            "no architecture is named preferred and none is eliminated; this document defines measurements only",
            "P5 calibration nuisance (registration, coil shape, divergence reading, facility interpretation) is never an "
            "axis or a design variable here",
            "the feed state is an IF-A5 input identical across arms; Hall-closure uncertainty does not reach intake, "
            "compressor, gas chambers or valves",
            "every number carries unit, evidence class and source (computed by this script or pinned), else TBD with "
            "what it requires",
            "the compressor bus draw and the W1 feed test points are never filled",
        ],
        "inputs": [{"path": rel, "lane": PINNED[rel], "sha256": pins[rel]} for rel in sorted(PINNED)],
        "cross_references_planned": [
            {"workstream": "W1 feed-state closure", "follow_on": "fo_feed_state_closure",
             "planned_path": "docs/architecture_comparison/feed_state_closure/", "uses": "registered test points "
             "{mdot_s, P_feed, T_feed, x_s} and their tolerances -> INS-05..INS-07 ranges and I-FLOW-CONSERVATIVE"},
            {"workstream": "W2 LOCK-1", "follow_on": "fo_lock1_decision_brief",
             "planned_path": "docs/architecture_comparison/lock1/", "uses": "D-01 shares, D-06 configuration, D-07 delta, "
             "traceable calibration class, the PROPOSED thresholds of this document"},
            {"workstream": "W3 hardware definition", "follow_on": "fo_hardware_definition",
             "planned_path": "TBD by fo_hardware_definition", "uses": "H-1 thrust range, mass on stand per configuration, "
             "exit area, coil currents, source frequencies and powers"},
            {"workstream": "W5 validation pre-registration", "follow_on": "fo_hall_validation_prereg_draft",
             "planned_path": "TBD by fo_hall_validation_prereg_draft", "uses": "which VO-* are held-out evidence and "
             "their acceptance tolerances -> the TBD required uncertainties of INS-09, INS-11..INS-16"},
        ],
        "milestones": {
            "supports": ["A"],
            "A": {"delivers": "the instrument set, required uncertainties and calibration procedures that make the "
                              "lane-25 R_arch classes, the sustainment classes and the absolute T_measured / P_bus gates "
                              "measurable; a traceability matrix from every instrument to what it decides",
                  "needs_next": ["owner decisions on the PROPOSED thresholds (I-*) at LOCK-1 together with D-01..D-15",
                                 "W1 registered test points and W3 hardware ranges to close the TBD ranges",
                                 "S1a calibrations and S1b re-mount series: D0 decides from measured values whether "
                                 "the targets are met (LOCK-2)"]},
            "B": {"delivers": "held-out validation observables (VO-*) are instrumented with the P5 gaps closed (B(z) at "
                              "coil currents, I_d traces, per-point divergence, gauge location and calibration)",
                  "needs_next": ["W5 pre-registration of the VO-* and their tolerances before any data",
                                 "an admitted Hall transport closure (credible set empty; gate 3 FAIL)",
                                 "O/O2 chemistry and an atomic-O-bearing feed (the bottled surrogate has none)"]},
            "C": {"delivers": "measured load-plane power per consumer and temperatures at the tested points",
                  "needs_next": ["flight-representative PPU / generator chains, mass, thermal, life, startup, cathode and "
                                 "mission closure integrated; this document alone does not support C"]},
        },
        "requirement_basis": basis,
        "proposed_thresholds": PROPOSED_THRESHOLDS,
        "derived": der,
        "decision_quantities": DECISION_QUANTITIES,
        "validation_observables": [{"id": i, "name": n, "source": f"{OD}: workstreams.W5_validation_prereg"}
                                   for i, n in VALIDATION_OBSERVABLES],
        "roles": ROLE,
        "instruments": ins,
        "procedures": PROCEDURES,
        "c5_adoption": c5,
        "a3_adoption": a3,
        "bus_power_channels": bus_power_channels(),
        "lane06_component_ids": prot_components,
        "experiment_package_traceability_ids": [r["id"] for r in pkg["traceability"]["rows"]],
        "references": REFERENCES + C5_REFERENCES,
        "open_owner_decisions": [
            "approve, change or reject I-ALPHA-ABS, I-U-ABS-T, I-U-ABS-P, I-U-ID-FLOOR, I-FLOW-CONSERVATIVE",
            "thrust-stand principle (torsional vs inverted pendulum, null vs displacement) given the per-arm mass change",
            "traceable calibration class for force, DC power and RF / microwave power standards",
            "one MFC per pure gas (proposed) or a mixture-calibrated MFC for the air surrogate",
            "dwell (hold time) for 'sustained >= 12 mN' and its zero-drift allowance",
            "whether OES, RGA and Langmuir probes are in the minimum instrument set",
            "absolute-gate facility rule: report T_measured with the S5 p_b slope and the ingestion scale (proposed) "
            "or require a p_b ceiling for Phase 3",
            "C5 (specification DECIDED by owner addendum A3; open: lab procurement): metrology lab for INS-19 / INS-20 "
            "(mass, profile, SEM/EDS, XPS) and its reference-standard classes",
            "C5 (DECIDED by owner addendum A3; open: HW-C1-09 (b) view in the C-1 design): C-1 temperature sensing - "
            "cathode-tube thermocouple mandatory, emitter pyrometer where a view exists",
            "C5 (DECIDED by owner addendum A3: planning k = 2): coverage factor for the witness-holder "
            "non-interference test (INS-P-12)",
            "C5 (DECIDED by owner addendum A3: quantitative for AO/lifetime use; open: H2O calibration method): whether "
            "the near-cathode RGA proxy (INS-22) is quantitative",
        ],
        "tbd_register": [
            {"what": "thrust range and mass on stand per configuration", "requires": "H-1 and module design",
             "blocked_by": "fo_hardware_definition"},
            {"what": "registered feed test points and tolerances", "requires": "W1 closure",
             "blocked_by": "fo_feed_state_closure"},
            {"what": "VO-* tolerances (B(z), species, ion energy, divergence, T_e/n_e)", "requires": "W5 pre-registration",
             "blocked_by": "fo_hall_validation_prereg_draft"},
            {"what": "I_d band / sampling rate, ext_window, T-SETTLE", "requires": "S1 measurements", "blocked_by": "S1"},
            {"what": "T-PB-MAX", "requires": "facility specification and owner decision", "blocked_by": "owner"},
            {"what": "f_src and w_c allocations", "requires": "LOCK-1 bus allocation", "blocked_by": "owner"},
            {"what": "compressor bus draw on v1", "requires": "upstream ICD", "blocked_by": "lane_33_upstream_icd"},
            {"what": "CEX attenuation bound for Faraday collectors", "requires": "cited N2+ on N2 CEX cross section",
             "blocked_by": "literature"},
            {"what": "C5 detection limits (coupon mass, profile, anode resistance) and triggers AOL-PT-02 / AOL-PT-03",
             "requires": "metrology lab records and S1 baseline scatter", "blocked_by": "S1"},
            {"what": "positions of the facility-background and beam-dump-facing control coupons",
             "requires": "facility choice", "blocked_by": "owner"},
            {"what": "coil hot-spot margin and C-1 emitter-temperature resolution",
             "requires": "magnet wire / insulation selection and the W3 C-1 / coil design",
             "blocked_by": "fo_magnet_coil_qualification + fo_hardware_definition"},
        ],
    }
    validate(doc)
    return doc


# ----------------------------------------------------------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------------------------------------------------------
FORBIDDEN = ("sgb-screen", "preferred architecture", "winner", "baseline is", "ELIMINATED")


def numeric_leaf_errors(obj, path="$", parent=None) -> list:
    """Every int/float must be the 'value' of a quantity dict (unit, evidence_class, source), a PROPOSED threshold value,
    or the 'bound' companion of a quantity."""
    errs = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            errs += numeric_leaf_errors(v, f"{path}.{k}", obj)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errs += numeric_leaf_errors(v, f"{path}[{i}]", None)
    elif isinstance(obj, bool) or obj is None or isinstance(obj, str):
        pass
    elif isinstance(obj, (int, float)):
        key = path.rsplit(".", 1)[-1]
        ok = (parent is not None and key in ("value", "bound") and {"unit", "evidence_class", "source"} <= set(parent)
              and parent["evidence_class"] in EVIDENCE_CLASSES)
        if not ok:
            errs.append(path)
    return errs


def _quantities_with_unit(obj, unit, path="$") -> list:
    out = []
    if isinstance(obj, dict):
        if obj.get("unit") == unit and isinstance(obj.get("value"), (int, float)):
            out.append(path)
        for k, v in obj.items():
            out += _quantities_with_unit(v, unit, f"{path}.{k}")
    elif isinstance(obj, list):
        for n, v in enumerate(obj):
            out += _quantities_with_unit(v, unit, f"{path}[{n}]")
    return out


def validate(doc: dict) -> None:
    errs = numeric_leaf_errors(doc)
    if errs:
        raise ValueError(f"numbers without unit/evidence class/source: {errs[:5]}")
    if doc["status"] != "DRAFT_PENDING_OWNER":
        raise ValueError("status must stay DRAFT_PENDING_OWNER")
    for t in doc["proposed_thresholds"]:
        if t["status"] != "PROPOSED" or t["evidence_class"] != "assumed":
            raise ValueError(f"threshold {t['id']} must be PROPOSED / assumed")
    comps = [r["component"] for r in doc["bus_power_channels"]]
    if sorted(comps) != sorted(V1_COMMON + ("rf_source", "ecr_source", "ecr_magnet")) or len(set(comps)) != len(comps):
        raise ValueError("bus_power_channels must cover bus_power_boundary_v1 exactly once")
    comp_row = {r["component"]: r for r in doc["bus_power_channels"]}
    if comp_row["compressor"]["lab_status"] != "ABSENT_IN_LAB":
        raise ValueError("compressor must stay ABSENT_IN_LAB")
    dq = {d["id"] for d in doc["decision_quantities"]}
    vo = {v["id"] for v in doc["validation_observables"]}
    for i in doc["instruments"]:
        if set(i["serves"]) != dq:
            raise ValueError(f"{i['id']} traceability row must name every decision quantity")
        if not set(i["serves"].values()) <= set(ROLE) | {"-"}:
            raise ValueError(f"{i['id']} unknown role")
        if not set(i["validation_observables"]) <= vo:
            raise ValueError(f"{i['id']} unknown validation observable")
        refs = {r["id"] for r in doc["references"]}
        if not set(i["references"]) <= refs:
            raise ValueError(f"{i['id']} unknown reference")
    for d in dq:
        if not any(i["serves"][d] == "D" for i in doc["instruments"]):
            raise ValueError(f"no decisive instrument for {d}")
    for v in vo:
        if not any(v in i["validation_observables"] for i in doc["instruments"]):
            raise ValueError(f"validation observable {v} has no instrument")
    ids = [i["id"] for i in doc["instruments"]] + [p["id"] for p in doc["procedures"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate instrument / procedure id")
    c5 = doc["c5_adoption"]
    for r in c5["rows"]:
        if r["status"] not in ("ADOPTED", "ADOPTED_PARTIAL", "NOT_ADOPTED"):
            raise ValueError(f"C5 {r['provision']}: unknown status")
        if (r["status"] == "NOT_ADOPTED") != (not r["adopted_ids"]):
            raise ValueError(f"C5 {r['provision']}: status / adopted ids inconsistent")
        if r["status"] != "ADOPTED" and not r["needs"]:
            raise ValueError(f"C5 {r['provision']}: a partial or missing adoption must state what is needed")
        if not set(r["adopted_ids"]) <= set(ids):
            raise ValueError(f"C5 {r['provision']}: unknown adopted id")
    for i in doc["instruments"]:
        for pid in i["traces_to_provisions"]:
            if pid not in {r["provision"] for r in c5["rows"]}:
                raise ValueError(f"{i['id']} traces to unknown provision {pid}")
    for p in doc["procedures"]:
        if not set(p["instruments"]) <= {i["id"] for i in doc["instruments"]}:
            raise ValueError(f"{p['id']} names an unknown instrument")
    a3 = doc["a3_adoption"]
    for r in a3["rows"]:
        if not set(r["carried_by"]) <= set(ids):
            raise ValueError(f"A3 {r['decision']}: unknown carrier id")
        if r["decision"] != "instrumentation_version" and not r["carried_by"]:
            raise ValueError(f"A3 {r['decision']}: not carried by any instrument or procedure")
    ins23 = next(i for i in doc["instruments"] if i["id"] == "INS-23")
    if not any("never as emitter temperature" in n and "'unmeasured'" in n for n in ins23["notes"]):
        raise ValueError("INS-23 must carry the A3 labelling rule (tube thermocouple never labelled emitter temperature)")
    ins22 = next(i for i in doc["instruments"] if i["id"] == "INS-22")
    if not any("QUALITATIVE" in n and "never supports an exposure-dose or lifetime claim" in n for n in ins22["notes"]):
        raise ValueError("INS-22 must carry the A3 data-use rule (uncalibrated RGA is qualitative only)")
    p12 = next(p for p in doc["procedures"] if p["id"] == "INS-P-12")
    if "k = 2" not in p12["statement"] or "effective degrees of freedom" not in p12["statement"]:
        raise ValueError("INS-P-12 must carry the A3 planning coverage factor and the low-dof rule")
    if doc["revision"] != "v1-r2":
        raise ValueError("A3: instrumentation stays v1-r2")
    entries = [c.get("entry") for c in doc["change_log"]]
    if None in entries or len(set(entries)) != len(entries):
        raise ValueError(f"change_log entries must carry a unique 'entry' key: {entries}")
    if HWR_LIVE in {p["path"] for p in doc["inputs"]}:
        raise ValueError("W4 must not pin W3's live file (pin cycle); pin the immutable snapshot")
    for path in _quantities_with_unit(doc, "h"):
        raise ValueError(f"life-type quantity in hours at {path} (control C6 / AOL-LF-01)")
    text = json.dumps(doc)
    for f in FORBIDDEN:
        if f in text:
            raise ValueError(f"forbidden phrase {f!r}")


# ----------------------------------------------------------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------------------------------------------------------
def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _v(x) -> str:
    if isinstance(x, dict) and "value" in x:
        if x["value"] == "TBD":
            return f"TBD - requires {x['tbd_requires']}"
        return f"{x['value']:g} {x['unit']}" if isinstance(x["value"], (int, float)) else str(x["value"])
    return str(x)


def _req_inner(v) -> str:
    if isinstance(v, dict) and "value" in v:
        return _v(v)
    if isinstance(v, dict):
        return "; ".join(f"{kk} {_req_inner(vv)}" for kk, vv in v.items())
    return str(v)


def _req_text(req: dict) -> str:
    return "<br>".join(f"{k}: {_req_inner(v)}" for k, v in req.items())


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    rb = doc["requirement_basis"]
    der = doc["derived"]
    a("# W4 instrumentation definition: common-hardware Hall-only / RF+Hall / ECR+Hall experiment")
    a("")
    a(f"**Status: {doc['status']}.** Follow-on `{doc['follow_on']}` (trigger `{doc['trigger']}`, owner disposition "
      f"`od_hardware_pivot`, workstream W4), version {doc['version']} revision {doc['revision']}. Original v1 base "
      f"commit `{doc['base_commit'][:10]}`; C5 repair base `{doc['repair_base_commit'][:10]}`; current content "
      f"(latest change-log entry `{doc['change_log'][-1]['entry']}`) rebuilt on "
      f"`{doc['change_log'][-1]['base_commit'][:10]}` (change log section 14). "
      f"{doc['not_locked']}")
    a("")
    a(f"Generated by `{doc['generated_by']}` from `instrumentation_definition_v1.json` content built in that script; "
      "`--check` reproduces both files byte for byte and `tests/test_instrumentation_definition.py` checks them. The JSON "
      "is authoritative; every number there carries unit, evidence class and source.")
    a("")
    a("## 0. What this is")
    a("")
    a("The owner pivoted the decisive-thrust question to one controlled experiment on one Hall accelerator H-1 and one "
      "cathode C-1 (HW-0 `hall_only`, HW-RF `rf_hall`, HW-ECR `ecr_hall`), with two separate decisions: the architecture "
      "ratio R_arch and an absolute thrust gate T_measured on the actual delivered feed (sustained >= 12 mN, the "
      "registered 25 mN capability, P_bus < 1.5 kW). This document says, for each measured quantity, what instrument "
      "principle, uncertainty and calibration are needed and which decision or validation quantity it serves. It "
      "chooses no product, claims no accuracy, names no preferred architecture and eliminates none.")
    a("")
    a("Compliance:")
    a("")
    for c in doc["compliance"]:
        a(f"- {c}")
    a("")
    a("## 1. Milestones")
    a("")
    ms = doc["milestones"]
    a(f"Supports milestone **{', '.join(ms['supports'])}** (conditional selection).")
    a("")
    a("| milestone | what this delivers | what the next step needs |")
    a("|---|---|---|")
    for m in ("A", "B", "C"):
        a(f"| {m} | {ms[m]['delivers']} | {'; '.join(ms[m]['needs_next'])} |")
    a("")
    a("## 2. Decision quantities and held-out validation observables")
    a("")
    a("| id | quantity | phase | stages | classes | requirement source |")
    a("|---|---|---|---|---|---|")
    for d in doc["decision_quantities"]:
        a(f"| {d['id']} | {d['name']} | {d['phase']} | {', '.join(d['stages'])} | {d['classes']} | "
          f"{d['requirement_source']} |")
    a("")
    a("Held-out Hall-transport validation observables named by the owner (W5 decides, before any data, which are "
      "pre-registered and with which tolerances): " +
      "; ".join(f"{v['id']} {v['name']}" for v in doc["validation_observables"]) + ".")
    a("")
    a("## 3. Where the uncertainty targets come from")
    a("")
    a("### 3.1 R_arch (lane 25, model-derived from its PROPOSED thresholds)")
    a("")
    a("| n (blocks) | u_T max per reading | u_P max per reading | u_inst max per installation | sigma(ln R) max | "
      "k (m = 14) | sigma_T at 12 mN | sigma_T at 25 mN | sigma_P at 1500 W |")
    a("|---|---|---|---|---|---|---|---|---|")
    for n, v in rb["lane25_by_n"].items():
        r = der["repeatability_absolute_by_n"][n]
        a(f"| {n} | {_v(v['u_T_max'])} | {_v(v['u_P_max'])} | {_v(v['u_inst_max'])} | {_v(v['sigma_lnR_max'])} | "
          f"{_v(v['k_primary'])} | {_v(r['sigma_T_at_12mN'])} | {_v(r['sigma_T_at_25mN'])} | "
          f"{_v(r['sigma_Pbus_at_1500W'])} |")
    a("")
    a("The absolute columns multiply lane 25's relative targets by the RFP levels (12 mN, 25 mN, 1500 W); they show the "
      "scale of the demand, not the thrust at any operating point (unknown until measured). At the knee-scan low-flow end "
      "the thrust is lower and the same relative target is a smaller absolute number.")
    a("")
    a("**Channel sum.** P_bus is a sum of independently metered channels. If every channel meets u_P,max, the sum does "
      "too: sqrt(sum (P_c u)^2) / sum P_c <= u. Checked on fixed hypothetical examples: " +
      "; ".join(f"{k}: {_v(v)} (bound {v['bound']:g})" for k, v in der["channel_sum_check"].items()) + ".")
    a("")
    a("**Common-consumer meter scale (G4)** u_c <= G4 share / w_c, with w_c = |P_c,X/P_bus,X - P_c,0/P_bus,0| from the "
      "LOCK-1 allocation (planning grid, one consumer carrying the whole share): " +
      "; ".join(f"w_c = {w}: {_v(v)}" for w, v in der["consumer_scale_max_by_w_c"].items()) + ".")
    a("")
    a("**Source load-plane scale (G3)**, lane 25: " +
      "; ".join(f"f_src = {f}: {_v(v)}" for f, v in rb["lane25_u_src_max_by_f_src"].items()) + ".")
    a("")
    a("### 3.2 Stop-rule sensitivity (n = 4)")
    a("")
    a("If the per-reading groups (G1, G2) come out at a multiple of plan while G3-G5 stay at their shares, and k is held "
      "at its planning value (approximation), the half-width h grows and the smallest deficit that can support a stop "
      "grows with it:")
    a("")
    a("| realised / planned u_T, u_P | sigma(ln R) | h | stop possible only if true R below | EQUIVALENT reachable "
      "(h < delta) | UNRESOLVED impossible (h < delta/2) |")
    a("|---|---|---|---|---|---|")
    for f, v in der["stop_rule_sensitivity_n4"].items():
        a(f"| {f} | {_v(v['sigma_lnR'])} | {_v(v['h'])} | {_v(v['R_stop_below'])} | {v['equivalent_reachable']} | "
          f"{v['unresolved_impossible']} |")
    a("")
    a("### 3.3 Absolute gates (PROPOSED rule)")
    a("")
    a(f"PROPOSED (I-ALPHA-ABS, one-sided alpha 0.05, k = {_v(der['k_one_sided'])}): T_measured passes the 12 mN gate "
      "only if T_hat (1 - k u) >= 12 mN and fails if T_hat (1 + k u) < 12 mN; in between it is UNRESOLVED. Same form for "
      "the 25 mN capability condition and, as an upper limit, for P_bus < 1500 W. u is the absolute (calibration-"
      "traceable) relative 1-sigma uncertainty of the reading; the grid is for planning.")
    a("")
    a("| u (1 sigma) | T_hat to PASS 12 mN | T_hat below which FAIL | T_hat to PASS 25 mN | T_hat below which FAIL | "
      "P_hat to PASS 1500 W | P_hat from which FAIL |")
    a("|---|---|---|---|---|---|---|")
    for u, v in der["absolute_thrust_gate"].items():
        p = der["absolute_power_gate"][u]
        a(f"| {u} | {_v(v['pass_min_12mN'])} | {_v(v['fail_max_12mN'])} | {_v(v['pass_min_25mN'])} | "
          f"{_v(v['fail_max_25mN'])} | {_v(p['pass_max_W'])} | {_v(p['fail_min_W'])} |")
    a("")
    a("PROPOSED targets I-U-ABS-T = 1 % and I-U-ABS-P = 1 % (both assumed, owner decision). REF-SNYDER2017 reports "
      "0.6-2 % uncertainties for direct thrust measurement, so 1 % is inside the reported range but not a claim for any "
      "stand. Conditions on the absolute gates:")
    a("")
    a("- **Boundary.** The power gate on `bus_power_boundary_v1` needs the compressor draw reconstructed from the upstream "
      "ICD (ABSENT_IN_LAB). Until then the lab result is PARTIAL_BOUNDARY: a lab-subset FAIL is informative, a lab-subset "
      "PASS is necessary but not sufficient.")
    a("- **Feed (I-FLOW-CONSERVATIVE, PROPOSED).** The gate counts only if the delivered anode flow is not above the "
      "registered W1 test-point flow with one-sided confidence (mdot_hat (1 + k u_mdot) <= mdot_registered), so flow "
      "uncertainty can only make the demonstration conservative. Flow uncertainty at a setpoint for a 1 % FS device: " +
      "; ".join(f"{f} of FS: {_v(v)}" for f, v in der["mfc_relative_u_by_setpoint_fraction"].items()) +
      ". Orientation zero shift (bound, REF-SNYDER2017 0.4 % FS): " +
      "; ".join(f"{f} of FS: {_v(v)}" for f, v in der["mfc_orientation_zero_shift_relative"].items()) + ".")
    a("- **Facility (PROPOSED reporting rule).** T_measured is reported at the measured p_b together with the S5 p_b "
      "slope and the ingestion scale below; no ingestion model is applied to rescue a gate (P5-N2 lesson, lane 25 "
      "Sec. 8). If the measured p_b slope times the p_b change to zero exceeds the gate margin, the gate is "
      "FACILITY_CONDITIONAL.")
    a("- **Sustained.** 'Sustained' uses THR-EXTINCTION over an owner-set hold time; the stand's zero drift over that "
      "dwell is bounded only by the pre- and post-dwell zeros (REF-POLK2017) and must fit inside I-U-ABS-T.")
    a("")
    a("**Ingestion scale** (free-molecular one-way mass flux of the background gas through the exit plane, stationary "
      "Maxwellian at 300 K, a scale not a model), per 100 cm^2 of exit area:")
    a("")
    a("| gas | " + " | ".join(next(iter(der["background_one_way_mass_flux"].values())).keys()) + " |")
    a("|---|" + "---|" * len(next(iter(der["background_one_way_mass_flux"].values()))))
    for gas, row in der["background_one_way_mass_flux"].items():
        a(f"| {gas} | " + " | ".join(_v(v) for v in row.values()) + " |")
    a("")
    a("Divide by the anode flow of the registered test point (W1) and scale by the H-1 exit area (W3) to get the "
      "ingested fraction. The three pressures are lane 25's SPT-100/xenon-specific planning scenarios.")
    a("")
    a("**Air-surrogate composition from two pure-gas MFCs** (absolute 1-sigma uncertainty of the O2 mass fraction w; "
      "planning grid, W1 supplies w):")
    a("")
    us = list(next(iter(der["mixture_mass_fraction_u"].values())).keys())
    a("| w | " + " | ".join(us) + " |")
    a("|---|" + "---|" * len(us))
    for w, row in der["mixture_mass_fraction_u"].items():
        a(f"| {w} | " + " | ".join(_v(v) for v in row.values()) + " |")
    a("")
    a("## 4. PROPOSED thresholds (not in the RFP)")
    a("")
    a("| id | what | value | source | rationale |")
    a("|---|---|---|---|---|")
    for t in doc["proposed_thresholds"]:
        a(f"| {t['id']} | {t['name']} | {t['value']:g} {t['unit']} | {t['source']} | {t['rationale']} |")
    a("")
    a("## 5. Instruments")
    a("")
    for i in doc["instruments"]:
        a(f"### {i['id']}. {i['name']}")
        a("")
        a(f"- **Lane-25 measurements:** {', '.join(i['lane25_measurements']) or 'new (not in lane 25)'}; "
          f"**quantity:** {i['quantity']}")
        a(f"- **Principle:** {i['principle']}")
        if i["references"]:
            a(f"- **References:** {', '.join(i['references'])}")
        a(f"- **Required uncertainty:** {_req_text(i['required_uncertainty'])}")
        a("- **Calibration:**")
        for c in i["calibration"]:
            a(f"  - {c}")
        a(f"- **Feasibility:** {i['feasibility']['status']}: {i['feasibility']['why']}")
        for n in i["notes"]:
            a(f"- **Note:** {n}")
        a("")
    a("## 5a. Procedures (control C5, revision v1-r2)")
    a("")
    a("| id | procedure | adopts | instruments | statement | required uncertainty | calibration | open |")
    a("|---|---|---|---|---|---|---|---|")
    for p in doc["procedures"]:
        a(f"| {p['id']} | {p['name']} | {', '.join(p['provisions'])} | {', '.join(p['instruments']) or '-'} | "
          f"{p['statement']} | {p['required_uncertainty']} | {p['calibration']} | {p['open']} |")
    a("")
    a("## 6. Bus-power metering per `bus_power_boundary_v1` component (lab subset vs v1)")
    a("")
    a("| component | architectures | lab status | lab measurement | v1 basis |")
    a("|---|---|---|---|---|")
    for r in doc["bus_power_channels"]:
        a(f"| `{r['component']}` | {', '.join(r['architectures'])} | {r['lab_status']} | {r['lab_measurement']} | "
          f"{r['v1_basis']} |")
    a("")
    a("Lane-06 channel labels (instrument labels only; contract ids in all records): " +
      ", ".join(f"`{c}`" for c in doc["lane06_component_ids"]) + ".")
    a("")
    a("## 7. Traceability matrix")
    a("")
    a("Roles: " + "; ".join(f"**{k}** {v}" for k, v in doc["roles"].items()) + "; - not used.")
    a("")
    dqs = [d["id"] for d in doc["decision_quantities"]]
    vos = [v["id"] for v in doc["validation_observables"]]
    a("| instrument | " + " | ".join(dqs) + " | " + " | ".join(vos) + " |")
    a("|---|" + "---|" * (len(dqs) + len(vos)))
    for i in doc["instruments"]:
        a(f"| {i['id']} | " + " | ".join(i["serves"][d] for d in dqs) + " | " +
          " | ".join("V" if v in i["validation_observables"] else "-" for v in vos) + " |")
    a("")
    a("Experiment-package traceability rows this refines (measurement -> Bundle-1 conditions, hard-gate criteria, "
      "failure-tree nodes): " + ", ".join(doc["experiment_package_traceability_ids"]) + " "
      "(docs/architecture_comparison/experiment_package/).")
    a("")
    c5 = doc["c5_adoption"]
    a("## 7a. Control C5: AO/lifetime register v2 and magnet/coil W4 provisions (adopted / not adopted)")
    a("")
    a(f"Control text (A2 addendum): {c5['control_text']}")
    a("")
    a("Provisions are read from the pinned " + " and ".join(f"`{x}`" for x in c5["sources"]) + " (every W4 row of the "
      "register's interface table and every MCQ-W4-* requirement); adopted ids are derived from the instrument and "
      "procedure trace fields. Cited W3 ids verified in `" + c5["w3_ids_cited_verified_in"] + "`: " +
      ", ".join(c5["w3_ids_cited"]) + ".")
    a("")
    a("Counts: " + ", ".join(f"{k} {v['value']}" for k, v in c5["counts"].items()) + ".")
    a("")
    a("| provision | title | register status before | status now | adopted by | how | still needed |")
    a("|---|---|---|---|---|---|---|")
    for r in c5["rows"]:
        a(f"| {r['provision']} | {r['title']} | {r['register_status_before']} | {r['status']} | "
          f"{', '.join(r['adopted_ids'])} | {r['how']} | {r['needs'] or '-'} |")
    a("")
    a("Instrument -> provision trace: " + "; ".join(f"{i['id']}: {', '.join(i['traces_to_provisions'])}"
                                                   for i in doc["instruments"] if i["traces_to_provisions"]) + ".")
    a("")
    a(f"Milestones: {c5['milestones']}")
    a("")
    a3 = doc["a3_adoption"]
    a("## 7b. Owner addendum A3 (instrument semantics; revision stays v1-r2)")
    a("")
    a(f"Source: `{a3['source']}` (decided {a3['decided_utc']}). W3 provisions: {a3['w3_provision']}.")
    a("")
    a("| A3 decision | carried by | how | owner text |")
    a("|---|---|---|---|")
    for r in a3["rows"]:
        a(f"| {r['decision']} | {', '.join(r['carried_by']) or '-'} | {r['how']} | {r['owner_text']} |")
    a("")
    a(f"Milestones: {a3['milestones']}")
    a("")
    a("## 8. Feasibility flags (honest)")
    a("")
    a("| instrument | status | why |")
    a("|---|---|---|")
    for i in doc["instruments"]:
        a(f"| {i['id']} | {i['feasibility']['status']} | {i['feasibility']['why']} |")
    a("")
    a("## 9. Cross-references to parallel pivot workstreams (planned paths; not read as inputs)")
    a("")
    a("| workstream | follow-on | planned path | used for |")
    a("|---|---|---|---|")
    for c in doc["cross_references_planned"]:
        a(f"| {c['workstream']} | `{c['follow_on']}` | {c['planned_path']} | {c['uses']} |")
    a("")
    a("## 10. Open owner decisions")
    a("")
    for k, o in enumerate(doc["open_owner_decisions"], 1):
        a(f"{k}. {o}")
    a("")
    a("## 11. TBD register")
    a("")
    a("| what | requires | blocked by |")
    a("|---|---|---|")
    for t in doc["tbd_register"]:
        a(f"| {t['what']} | {t['requires']} | {t['blocked_by']} |")
    a("")
    a("## 12. References")
    a("")
    for r in doc["references"]:
        url = f" {r['url']}" if "url" in r else ""
        a(f"- **{r['id']}.** {r['citation']}.{url} Access: {r['access']}.")
    a("")
    a("## 13. Pinned inputs")
    a("")
    a("| path | lane | sha256 |")
    a("|---|---|---|")
    for p in doc["inputs"]:
        a(f"| `{p['path']}` | {p['lane']} | `{p['sha256'][:16]}` |")
    a("")
    a("## 14. Change log")
    a("")
    a("| entry | revision | date | base commit | change |")
    a("|---|---|---|---|---|")
    for c in doc["change_log"]:
        extra = f" Why still v1: {c['why_v1']}" if "why_v1" in c else ""
        rev = c["revision"] + (f" ({c['amendment']})" if "amendment" in c else "")
        a(f"| {c['entry']} | {rev} | {c['date']} | `{c['base_commit'][:10]}` | {c['change']}.{extra} |")
    a("")
    dr = doc["downstream_repin_required"]
    a("## 15. Downstream re-pin required (outside W4's paths)")
    a("")
    a("These consumers pin the bytes of `instrumentation_definition_v1.json` (and, for AO v3, this Markdown file). "
      "Their pins are stale after the A3 revision; W4 cannot edit them. Their owners or the merge controller re-pin "
      "them to the sha256 of this file at the W4 lane head.")
    a("")
    a("| file | owner | pins | stale pin | test / action |")
    a("|---|---|---|---|---|")
    for c in dr["consumers"]:
        a(f"| `{c['file']}` | {c['owner']} | {c['pins']} | `{c['stale_pin'][:16]}` | {c['test_affected']} |")
    a("")
    sn = dr["w3_snapshot"]
    a(f"**Pin cycle resolved.** W4 pins the W3 register as the immutable snapshot `{sn['snapshot']}` "
      f"(reproduce: `{sn['reproduce']}`). {sn['why']}")
    a("")
    a(f"**Merge order.** {dr['merge_order']}")
    a("")
    return "\n".join(L)


def main(argv: list[str]) -> int:
    if "--pin" in argv:
        pins_file = HERE / "pinned_inputs.json"
        if pins_file.exists():
            raise RuntimeError("pinned_inputs.json exists; re-pinning is a deliberate edit, not a flag")
        pins_file.write_text(json.dumps({rel: _sha256(ROOT / rel) for rel in sorted(PINNED)}, indent=1) + "\n",
                             encoding="utf-8")
        return 0
    doc = build()
    js, md = dumps(doc), render_md(doc)
    if "--check" in argv:
        ok = (OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.exists()
              and OUT_MD.read_text(encoding="utf-8") == md)
        print("OK" if ok else "DRIFT: committed files differ from the build")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
