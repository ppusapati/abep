"""Build the W4 actual-hardware capability-demonstration preparation (fo_capability_demo_prep,
trigger T_PIVOT_CAPABILITY_DEMO_PREP, owner addendum A3) and the metrology-lab measurement specification.

Outputs (deterministic; `--check` verifies the committed files byte for byte):
  docs/experiments/capability_demo/capability_demo_prep_v1.json
  docs/experiments/capability_demo/CAPABILITY_DEMO_PREP.md
  docs/experiments/capability_demo/capability_record_item_v1.schema.json
  docs/experiments/capability_demo/s1a_calibration_procedures_candidate_v1.json
  docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json
  docs/experiments/instrumentation/metrology_spec/METROLOGY_MEASUREMENT_SPEC.md

This is PREPARATION: procedures, planning numbers and the pass/fail analysis for measurements that have not been made.
No data is invented and nothing here states that a capability is demonstrated. The S1-C4 artifact
(docs/experiments/instrumentation/capability_demonstration_v1.json) and its raw data are produced later by W4 from actual
calibration measurements; this lane never writes them.

Every number is a quantity {value, unit, evidence_class, source}: copied bit-for-bit from a pinned input, quoted from a
cited standard, or computed here by a named function. Thresholds not in the RFP are PROPOSED. Inputs are sha256-pinned;
a changed or missing input raises.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRIPT_REL = "docs/experiments/capability_demo/build_capability_demo_prep.py"
ANALYSIS_REL = "docs/experiments/capability_demo/capability_analysis.py"
OUT_JSON = HERE / "capability_demo_prep_v1.json"
OUT_MD = HERE / "CAPABILITY_DEMO_PREP.md"
OUT_SCHEMA = HERE / "capability_record_item_v1.schema.json"
OUT_S1A = HERE / "s1a_calibration_procedures_candidate_v1.json"
SPEC_DIR = ROOT / "docs" / "experiments" / "instrumentation" / "metrology_spec"
OUT_SPEC_JSON = SPEC_DIR / "metrology_measurement_spec_v1.json"
OUT_SPEC_MD = SPEC_DIR / "METROLOGY_MEASUREMENT_SPEC.md"

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
ARCHS = ("hall_only", "rf_hall", "ecr_hall")

INS_REL = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
S1_REL = "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json"
L25_REL = "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"
FEED_REL = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
MCQ_REL = "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json"
OD_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"
A1_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A1_controls.json"
A2_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A2_execution_directive.json"
A3_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json"
S1A_REL = "docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json"

#: sha256 pins (inputs read-only; owner decision files are immutable). A different byte = InputChanged.
PINNED = {
    OD_REL: "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac",
    A1_REL: "04c5a6f46ed2cb3e3fb174bcc7305d129e15ef53af2349d2a8abc4f6d8975992",
    A2_REL: "f82fb78cc0f608c03fd37d9ecbede6aab4ec525eecf5f8a47619eca35e1e73b6",
    A3_REL: "10d79026f1a65e0c2a9fa9e1f9a5f9abc9d162692711857bd43575f3095c8d4e",
    INS_REL: "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
    S1_REL: "1d3388693191295f4c54ea9d1d38b36ca977193e0d9066aa40aac61776b27fd1",
    L25_REL: "54b7b00a60134f2d92f2eb5c9fb49f18d23623a566e04a4b7d70325a0e332509",
    FEED_REL: "ff6e15db449151b5cf790088b4641504bd435a48de2d4c6235bf83625d508ef9",
    MCQ_REL: "53e92f4536f7b30054d3521adbd504eca725c4c6d79a6cb3b51c2fc4ce220b32",
    S1A_REL: "011808100ef38799668cb948324efa6492344d3b58ed3c436605ce5caf7025ac",
}


class InputChanged(RuntimeError):
    """A pinned input's bytes differ from its pin."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs() -> dict:
    """Raise FileNotFoundError / InputChanged unless every pinned input exists with its pinned sha256."""
    out = {}
    for rel, sha in PINNED.items():
        p = ROOT / rel
        if not p.exists():
            raise FileNotFoundError(f"pinned input missing: {rel}")
        got = _sha256(p)
        if got != sha:
            raise InputChanged(f"pinned input changed: {rel} sha256 {got} != pin {sha}")
        out[rel] = sha
    return out


def _load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _analysis():
    spec = importlib.util.spec_from_file_location("_capdemo_analysis", HERE / "capability_analysis.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _analysis()


# ----------------------------------------------------------------------------------------------------------------------
# number helpers
# ----------------------------------------------------------------------------------------------------------------------
def _r(x: float, sig: int = 6) -> float:
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.{sig}g}")


def q(value, unit: str, evidence_class: str, source: str, exact: bool = False, **extra) -> dict:
    """A quantity. exact=True keeps a value copied from a pinned input bit-for-bit (no rounding)."""
    if evidence_class not in EVIDENCE_CLASSES:
        raise ValueError(f"unknown evidence class {evidence_class!r}")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"quantity value must be a finite number, got {value!r}")
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


def proposed(value, unit: str, pid: str, rationale: str) -> dict:
    return q(value, unit, "assumed", f"this lane's proposal {pid} (not in the RFP; owner decides at the calibration-plan "
                                     f"freeze S1-C5)", status="PROPOSED", id=pid, rationale=rationale)


def _src(fn: str) -> str:
    return f"{SCRIPT_REL}: {fn}"


# ----------------------------------------------------------------------------------------------------------------------
# PROPOSED planning thresholds of this lane (owner decides; none is an RFP value)
# ----------------------------------------------------------------------------------------------------------------------
P_CONF = 0.95        # one-sided confidence of the sigma upper bound reported with every repeatability verdict
LOW_DOF_TOL = 0.05   # A3: evaluated k replaces k = 2 when t_{P_K2}(nu_eff) > 2 + LOW_DOF_TOL
K_PLANNING = 2.0     # owner addendum A3 (DECIDED, not proposed)
MIN_SETPOINT_FRACTION = 0.2  # PROPOSED lowest MFC setpoint as a fraction of its full scale for registered points


def proposed_thresholds() -> list:
    return [
        proposed(P_CONF, "one-sided confidence", "CD-P-CONF",
                 "every repeatability verdict reports the chi-square upper bound of sigma at this confidence; the "
                 "point estimate decides MEETS_N<n>, the bound says whether that is 'confident' (capability_analysis."
                 "repeatability_verdict); lane 25 readiness_n at LOCK-2 remains the decisive rule"),
        proposed(LOW_DOF_TOL, "absolute difference in k", "CD-P-LOWDOF",
                 "owner addendum A3 says 'with low effective degrees of freedom use the evaluated coverage factor'; this "
                 "operationalises 'low': the Student-t factor at the k = 2 coverage probability exceeds 2 by more than "
                 "this tolerance (capability_analysis.coverage_factor)"),
        proposed(MIN_SETPOINT_FRACTION, "fraction of MFC full scale", "CD-P-MFC-MINFRAC",
                 "keeps every registered flow high in its MFC range (INS-05: 'choose FS so every registered point sits "
                 "high in the range'); at a 1 % FS device this caps the FS-referred term at 5 % of reading "
                 "(instrumentation derived.mfc_relative_u_by_setpoint_fraction.0.2)"),
        proposed(10, "calibration sequences", "CD-P-FORCE-SEQ",
                 "same count as the INS-01 '>= 10 in-situ calibrations before and after' (REF-POLK2017 as cited by W4; "
                 "lane 06 PROPOSED) so the demonstration exercises the campaign procedure itself"),
        proposed(5, "force levels (incl. zero)", "CD-P-FORCE-LEVELS",
                 "a linearity check needs points inside the span, not only its ends; five levels give three interior "
                 "points and nu = 3 for the residual SD of a straight-line fit"),
        proposed(3, "alternation cycles", "CD-P-CONFIG-CYCLES",
                 "HW-0 / HW-X / HW-0 alternation repeated three times per module separates a configuration (mass) "
                 "effect from stand drift"),
        proposed(5, "readings per flow point", "CD-P-MFC-REPEATS",
                 "Type A at each MFC calibration point (nu = 4) in ascending and descending order (hysteresis)"),
        proposed(3, "complete maps per configuration", "CD-P-BZ-MAPS",
                 "probe removed and re-seated between maps; nu = 2 per point is the minimum that yields a repeatability "
                 "estimate; the owner may raise it after the first map shows the scatter"),
        proposed(3, "current cycles", "CD-P-BZ-CYCLES",
                 "coil current cycled zero -> operating value three times with the pre-registered approach protocol to "
                 "expose magnetic-circuit hysteresis at the peak-field location"),
        proposed(100, "injected reference edges", "CD-P-DAQ-EDGES",
                 "enough edges to estimate per-channel offset scatter and its drift over the record"),
        proposed(3, "comparison temperatures per channel", "CD-P-TC-POINTS",
                 "the minimum that detects curvature of a thermocouple's deviation over its range"),
        proposed(10, "readings per power calibration point", "CD-P-PWR-REPEATS",
                 "Type A per calibration point (nu = 9)"),
        proposed(5, "calibration points per power channel", "CD-P-PWR-POINTS",
                 "gain, offset and nonlinearity over the channel range (range TBD from the LOCK-1 allocation)"),
    ]


# ----------------------------------------------------------------------------------------------------------------------
# planning tables (model-derived; pure functions of the pinned inputs and the analysis module)
# ----------------------------------------------------------------------------------------------------------------------
def chi2_factor_table() -> dict:
    out = {}
    for nu in (2, 3, 4, 5, 9, 12, 19, 29):
        out[f"nu={nu}"] = q(A.sigma_upper_bound(1.0, nu, P_CONF), "sigma_upper / s", "model-derived",
                            _src(f"capability_analysis.sigma_upper_bound(s=1, nu={nu}, confidence=CD-P-CONF)"))
    return out


def coverage_table() -> dict:
    out = {}
    for nu in (2, 3, 4, 5, 6, 8, 10, 15, 20, 30, 50, 100):
        cf = A.coverage_factor(nu, K_PLANNING, LOW_DOF_TOL)
        out[f"nu_eff={nu}"] = q(cf["k_evaluated"], "-", "model-derived",
                                _src(f"capability_analysis.coverage_factor(nu={nu}) Student-t at P_K2"),
                                replaces_k2=cf["low_effective_dof"])
    return out


def low_dof_threshold() -> dict:
    nu = 1
    while A.coverage_factor(nu, K_PLANNING, LOW_DOF_TOL)["low_effective_dof"]:
        nu += 1
    return q(nu, "effective degrees of freedom", "model-derived",
             _src("low_dof_threshold(): smallest integer nu_eff at which k = 2 is used (CD-P-LOWDOF)"))


def lane25_targets(ins: dict) -> dict:
    rb = ins["requirement_basis"]["lane25_by_n"]
    src = f"{INS_REL}: requirement_basis.lane25_by_n (copied exact)"
    out = {}
    for key in ("u_T_max", "u_P_max", "u_inst_max"):
        out[key] = {f"n={n}": q(rb[n][key]["value"], rb[n][key]["unit"], rb[n][key]["evidence_class"],
                                f"{src}; original: {rb[n][key]['source']}", exact=True) for n in sorted(rb, key=int)}
    der = ins["derived"]["repeatability_absolute_by_n"]
    out["sigma_T_at_12mN"] = {f"n={n}": q(der[n]["sigma_T_at_12mN"]["value"], der[n]["sigma_T_at_12mN"]["unit"],
                                          "model-derived", f"{INS_REL}: derived.repeatability_absolute_by_n.{n}",
                                          exact=True) for n in sorted(der, key=int)}
    out["sigma_Pbus_at_1500W"] = {f"n={n}": q(der[n]["sigma_Pbus_at_1500W"]["value"],
                                              der[n]["sigma_Pbus_at_1500W"]["unit"], "model-derived",
                                              f"{INS_REL}: derived.repeatability_absolute_by_n.{n}", exact=True)
                                  for n in sorted(der, key=int)}
    out["u_src_max_by_f_src"] = {f"f_src={f}": q(v["value"], v["unit"], v["evidence_class"],
                                                 f"{INS_REL}: requirement_basis.lane25_u_src_max_by_f_src.{f}",
                                                 exact=True)
                                 for f, v in ins["requirement_basis"]["lane25_u_src_max_by_f_src"].items()}
    thr = {t["id"]: t for t in ins["proposed_thresholds"]}
    for tid in ("I-U-ABS-T", "I-U-ABS-P", "I-U-ID-FLOOR"):
        t = thr[tid]
        out[tid] = q(t["value"], t["unit"], t["evidence_class"], f"{INS_REL}: proposed_thresholds {tid}", exact=True,
                     status=t["status"])
    return out


def lane25_s1_counts(l25: dict) -> dict:
    thr = {t["id"]: t for t in l25["thresholds"]}
    out = {}
    for tid in ("T-S1-REMOUNT-CYCLES", "T-S1-READINGS-PER-CYCLE", "T-N-MIN", "T-N-MAX"):
        t = thr[tid]
        out[tid] = q(t["value"], t["unit"], t["evidence_class"], f"{L25_REL}: thresholds {tid} (lane 25)",
                     exact=True, status=t["status"])
    return out


def mfc_range(feed: dict, ins: dict) -> dict:
    m = feed["mfc_range_requirement"]
    s = f"{FEED_REL}: mfc_range_requirement"
    lo, hi = m["mdot_min_kgps"], m["mdot_max_kgps"]
    u_fs = ins["derived"]["mfc_relative_u_by_setpoint_fraction"]["1.0"]["value"]  # 1 % FS at FS (REF-SNYDER2017 via W4)
    zero_fs = ins["derived"]["mfc_orientation_zero_shift_relative"]["1.0"]["value"]  # 0.4 % FS
    ratio = hi / lo
    n_ranges = {}
    for frac in (0.1, MIN_SETPOINT_FRACTION):
        n = math.ceil(math.log(ratio) / math.log(1.0 / frac) - 1e-12)
        n_ranges[f"min_setpoint_fraction={frac}"] = q(n, "MFC ranges per gas path", "model-derived",
                                                      _src(f"mfc_range(): ceil(ln(max/min) / ln(1/{frac}))"))
    return {
        "basis": "W1 feed-state closure MFC range requirement (DRAFT for owner review; A3 DI_1_4: 'the 0.030-3.14 mg/s "
                 "envelope remains a candidate range, not a flight truth'). An instrumentation range input, not a test "
                 "point; registered test points remain TBD from W1/LOCK-1.",
        "mdot_min": q(lo * 1e6, "mg/s", "model-derived", f"{s}.mdot_min_kgps (x 1e6)"),
        "mdot_max": q(hi * 1e6, "mg/s", "model-derived", f"{s}.mdot_max_kgps (x 1e6)"),
        "sccm_N2_min": q(m["sccm_N2_min"], "sccm N2", "model-derived", f"{s}.sccm_N2_min", exact=True),
        "sccm_N2_max": q(m["sccm_N2_max"], "sccm N2", "model-derived", f"{s}.sccm_N2_max", exact=True),
        "sccm_O2_max": q(m["sccm_O2_max"], "sccm O2", "model-derived", f"{s}.sccm_O2_max", exact=True),
        "sccm_basis": "different bases: sccm_N2_min / sccm_N2_max are the N2 mass-equivalent of the TOTAL feed mass "
                      "flow (mdot / M_N2); sccm_O2_max is only the O2 component of the air surrogate (O2_max / M_O2) "
                      "at the envelope union (feed_state_closure build: mfc_range_requirement). They are not "
                      "additive and must not be compared directly. sccm reference conditions: 273.15 K, 101325 Pa, "
                      "ideal gas (feed_state_closure ground.sccm_reference, PROPOSED there), with the molecular mass "
                      "M_N2 = 28.0 u of abep_sim.constants.M_SPECIES; against a standard molar mass of about 28.013 "
                      "g/mol (verify) this shifts the sccm values by about 0.05 % (implied molar volume about 22,424 "
                      "instead of 22,414 cm3/mol). MFC vendors use other reference conditions; every MFC conversion "
                      "uses the MFC's own stated reference (verify per MFC)",
        "turndown_ratio": q(ratio, "max / min", "model-derived", _src("mfc_range(): mdot_max / mdot_min")),
        "single_device_u_at_min": q(u_fs * ratio, "relative (FS-referred term, 1 sigma treated)", "model-derived",
                                    _src("mfc_range(): 1 % FS (instrumentation derived.mfc_relative_u_by_setpoint_"
                                         "fraction.1.0, REF-SNYDER2017 'typically 1% full scale' as cited by W4) x "
                                         "max/min, one device with FS = mdot_max")),
        "single_device_zero_shift_at_min": q(zero_fs * ratio, "relative (bound)", "model-derived",
                                             _src("mfc_range(): 0.4 % FS orientation zero shift (instrumentation "
                                                  "derived.mfc_orientation_zero_shift_relative.1.0, REF-SNYDER2017 as "
                                                  "cited by W4) x max/min")),
        "ranges_needed": n_ranges,
        "reading": "a single device spanning the candidate range cannot resolve its low end: the FS-referred term "
                   "alone exceeds the reading. The demonstration therefore covers a set of overlapping ranges per gas "
                   "path, each calibrated on its own gas; the actual range set follows the registered W1 points.",
        "xe_cathode_flow": tbd("C-1 cathode Xe flow range (C-1 design, W3) and the LOCK-1 cathode operating point",
                               "fo_hardware_definition"),
    }


def phase_error_table() -> dict:
    out = {"note": "hypothetical planning grid (not a claim about H-1): the skew allowance itself is TBD from the S1 "
                   "I_d spectrum (INS-18); REF-CHOUEIRI2001 (abstract only, as cited by W4) reviews Hall oscillations "
                   "over 1 kHz - 60 MHz"}
    for f in (1e3, 1e4, 1e5, 1e6):
        out[f"f={int(f)}Hz"] = q(1.0 / (360.0 * f), "s skew for 1 degree phase error", "model-derived",
                                 _src(f"phase_error_table(): 1 / (360 f), f = {int(f)} Hz (capability_analysis."
                                      "phase_error_deg inverted)"))
    return out


# ----------------------------------------------------------------------------------------------------------------------
# references (accessed by this lane on 2026-09-27 unless stated)
# ----------------------------------------------------------------------------------------------------------------------
REFERENCES = [
    {"id": "REF-POLK2017", "citation": "J. E. Polk et al., 'Recommended Practice for Thrust Measurement in Electric "
     "Propulsion Testing', J. Propulsion and Power 33(3):539-555 (2017)", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7839308/",
     "access": "as accessed and cited by W4 (docs/experiments/instrumentation/instrumentation_definition_v1.json "
               "references); not re-accessed by this lane"},
    {"id": "REF-SNYDER2017", "citation": "J. S. Snyder et al., 'Recommended Practice for Flow Control and Measurement "
     "in Electric Propulsion Testing', J. Propulsion and Power 33(3) (2017)",
     "url": "https://hpepl.ae.gatech.edu/sites/default/files/Journal_Articles/JPP%20V33%20No3%20MayJune2017_MassFlowMeasurement.pdf",
     "access": "as accessed and cited by W4 (1-5 % FS typical, 1 % FS, 0.4 % FS orientation zero shift, own-gas "
               "calibration, GCF at sensor temperature); not re-accessed by this lane"},
    {"id": "REF-CHOUEIRI2001", "citation": "E. Y. Choueiri, 'Plasma oscillations in Hall thrusters', Phys. Plasmas "
     "8(4):1411-1426 (2001)", "url": None, "access": "abstract only, as cited by W4; not re-accessed"},
    {"id": "REF-GUM2008", "citation": "JCGM 100:2008, 'Evaluation of measurement data - Guide to the expression of "
     "uncertainty in measurement'", "url": "https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf",
     "access": "full text read 2026-09-27 (PDF text extraction): 4.2 (Type A), 6.3.1 ('In general, k will be in the "
               "range 2 to 3'), G.4.1 (Welch-Satterthwaite, Eq. G.2b)"},
    {"id": "REF-OIML-R111-1", "citation": "OIML R 111-1:2004 (E), 'Weights of classes E1, E2, F1, F2, M1, M1-2, M2, "
     "M2-3 and M3 - Part 1: Metrological and technical requirements'", "url": "https://www.oiml.org/en/files/pdf_r/r111-1-e04.pdf",
     "access": "full text read 2026-09-27 (PDF text extraction): 5.2 (U for k = 2 of the conventional mass <= 1/3 of "
               "the MPE, Eq. 5.2-1), Table 1 (MPE, +/- delta_m in mg), C.6.5.1 (k = 2 usually; t-distribution at "
               "95.5 % with Welch-Satterthwaite nu_eff when fewer than 10 measurements and the weighing term "
               "dominates). An 'Amendment 2025' to R 111-1:2004 exists (https://www.oiml.org/en/files/pdf_r/"
               "r111-1-e04_amend25.pdf) and was NOT read: verify whether it changes the values quoted here"},
    {"id": "REF-ISO17025", "citation": "ISO/IEC 17025:2017, 'General requirements for the competence of testing and "
     "calibration laboratories'", "url": "https://www.iso.org/standard/66912.html",
     "access": "metadata only (search result 2026-09-27; the iso.org page returned HTTP 403 to the fetch tool and was "
               "not bypassed): title, third edition 2017; content not read (verify)"},
    {"id": "REF-NABL", "citation": "National Accreditation Board for Testing and Calibration Laboratories (NABL), "
     "India", "url": "https://nabl-india.org/",
     "access": "home page read 2026-09-27: accredits testing and calibration laboratories against ISO/IEC 17025; "
               "maintains an accredited-laboratory search with scopes. No laboratory was searched or contacted"},
    {"id": "REF-ISO25178-700", "citation": "ISO 25178-700:2022, 'Geometrical product specifications (GPS) - Surface "
     "texture: Areal - Part 700: Calibration, adjustment and verification of areal topography measuring "
     "instruments'", "url": "https://www.iso.org/standard/78204.html",
     "access": "metadata / scope summary only (search result 2026-09-27): generic procedures for the metrological "
               "characteristics of ISO 25178-600 (noise, flatness deviation, amplification, linearity deviation, x-y "
               "mapping deviations); methods adaptable to profiling instruments; content not read (verify)"},
    {"id": "REF-ASTM-E1508", "citation": "ASTM E1508-12a(2019), 'Standard Guide for Quantitative Analysis by "
     "Energy-Dispersive Spectroscopy'", "url": "https://store.astm.org/e1508-12ar19.html",
     "access": "metadata / scope summary only (search result 2026-09-27): EDS quantification on SEM/EPMA with and "
               "without standards; routine quantification for elements >= Na at >= tenths of a weight percent; not "
               "TEM; content not read (verify). Note: that applicability statement means light elements (N, O, B, C) "
               "are outside its routine range - relevant to BN and oxide layers"},
    {"id": "REF-ISO15472", "citation": "ISO 15472:2010, 'Surface chemical analysis - X-ray photoelectron "
     "spectrometers - Calibration of energy scales'", "url": "https://www.iso.org/standard/55796.html",
     "access": "scope clause read 2026-09-27 from the publisher's preview (https://cdn.standards.iteh.ai/samples/55796/"
               "72dc0295fe1447ec93e6a6c190572c1b/ISO-15472-2010.pdf): Al/Mg (unmonochromated) or monochromated Al "
               "X-rays; instruments with an ion gun for sputter cleaning; Cu 2p3/2 and Au 4f7/2 reference peaks, "
               "linearity at one intermediate energy; expanded uncertainty of the scale calibration at 95 % "
               "confidence; not applicable below +/-0.03 eV tolerance or resolution worse than 1.5 eV"},
    {"id": "REF-ASTM-E220", "citation": "ASTM E220, 'Standard Test Method for Calibration of Thermocouples by "
     "Comparison Techniques' (E220-19; E220-25 listed)", "url": "https://store.astm.org/e0220-19.html",
     "access": "metadata / scope summary only (search result 2026-09-27): comparison with a reference thermometer, "
               "approximately -195 C to 1700 C (-320 F to 3100 F) per the ASTM scope summary (verify against the current edition); applicable to unused thermocouples, not to used ones (inhomogeneity); "
               "content not read (verify the edition)"},
    {"id": "REF-IEEE1588", "citation": "IEEE Std 1588-2019, 'IEEE Standard for a Precision Clock Synchronization "
     "Protocol for Networked Measurement and Control Systems'", "url": "https://standards.ieee.org/standard/1588-2019.html",
     "access": "metadata only (search result 2026-09-27); content not read (verify). Named only as one generic option "
               "for a distributed time base"},
]


# ----------------------------------------------------------------------------------------------------------------------
# demonstrations
# ----------------------------------------------------------------------------------------------------------------------
def _record(category: str, instrument_id: str, demonstrated: str, extra: list | None = None,
            scope: str | None = None) -> dict:
    d = {
        "category": category,
        "instrument_id": instrument_id,
        "evidence_class": "measured",
        "demonstrated_uncertainty": {"value": "<number from the analysis>", "unit": "<unit>",
                                     "source": "<analysis script path + sha256 + raw-data path>",
                                     "evidence_class": "measured", "meaning": demonstrated},
        "extra_fields": ["demonstration_id", "calibration_date", "raw_data {path, sha256}", "analysis_script_sha256",
                         "calibration_plan_sha256", "coverage {k, nu_eff, low_effective_dof}", "type_a", "type_b",
                         "verdict", "traceability (certificate ids)", "environment", "operator (coded id)"]
                        + (extra or []),
    }
    if scope:
        d["scope"] = scope
    return d


def demonstrations(t25: dict, counts: dict, mfc: dict, ins: dict) -> list:
    ptab = {p["id"]: p for p in proposed_thresholds()}
    rep = lambda pid: {k: ptab[pid][k] for k in ("value", "unit", "evidence_class", "source", "status", "id")}
    bus = ins["bus_power_channels"]

    cd01 = {
        "id": "CD-01",
        "title": "thrust-stand force calibration, repeatability and mass-change behaviour between configurations",
        "instruments": ["INS-01", "INS-17", "INS-18"],
        "s1c4_categories": ["thrust_stand"],
        "stage": "pre-S1 on the delivered stand in the S1 vacuum facility (S1a, no plasma); part of the S1-C4 record",
        "purpose": "show from actual calibrations that the delivered stand resolves the lane-25 per-reading target and "
                   "that its response is either independent of the mass change between HW-0 / HW-RF / HW-ECR or is "
                   "re-calibrated per configuration (INS-01 principle)",
        "equipment": [
            "the delivered thrust stand with its in-situ calibration system (known forces applied under vacuum; "
            "REF-POLK2017 as cited by INS-01); force-standard traceability class TBD - requires owner (INS-01 open)",
            "stand thermocouples and inclinometer (inverted pendulum) logged on the common time base (INS-17, INS-18)",
            "the actual RF and ECR modules unpowered on the stand, or mass-and-inertia dummies of them "
            "(dummy masses TBD - requires W3 module masses)",
            "propellant lines, power cables, RF coax / waveguide in their final routing (tares)",
        ],
        "procedure": [
            "pump down; thermal settling with stand cooling on (settling time TBD - requires S1 thermal time constants)",
            "zero with power and flow off; record inclination and stand temperatures",
            "apply the calibration forces at CD-P-FORCE-LEVELS levels spanning zero to the top of the range (range "
            "TBD: from the knee-scan extinction end to >= 25 mN capability, INS-01) in ascending then descending order",
            "repeat the sequence CD-P-FORCE-SEQ times within the same mount; zero before and after each",
            "magnetic tare: Hall coil and ECR coil currents at the operating settings (TBD - W3/LOCK-1) with the "
            "discharge off, forces re-applied; cable / feed-line tare per configuration (INS-01 tares)",
            "mass-change behaviour: install HW-0, HW-RF (modules or dummies), HW-0, HW-ECR, HW-0 and repeat the "
            "alternation CD-P-CONFIG-CYCLES times, a full calibration in every configuration",
            "archive every raw reading (stand output, applied force id, temperatures, inclination, timestamps)",
        ],
        "repeats": {"force_levels": rep("CD-P-FORCE-LEVELS"), "sequences": rep("CD-P-FORCE-SEQ"),
                    "configuration_cycles": rep("CD-P-CONFIG-CYCLES")},
        "analysis": {
            "type_a": "per force level: sample SD of the stand response over the sequences (capability_analysis."
                      "type_a); per sequence: straight-line fit (linear_calibration) -> slope, intercept, residual SD, "
                      "nonlinearity; zero drift across each sequence (drift_rate; if resolution_limited, the Type B "
                      "resolution term below bounds the drift instead of a zero-u Type A value)",
            "type_b": "applied-force standard (certificate), stand temperature coefficient if a correction is applied, "
                      "tare uncertainty, DAQ resolution q as u = q / (2 sqrt 3) per reading (GUM F.2.2.1; always "
                      "included, and mandatory when drift_rate reports resolution_limited)",
            "repeatability_in_force": "s at the 12 mN-equivalent level converted to relative (s / 12 mN) and at 25 mN",
            "mass_change": "configuration_slope_shift(HW-0 slope, HW-X slope) with k per A3 (coverage_factor); "
                           "DETECTED -> per-configuration calibration mandatory and its uncertainty enters every "
                           "reading of that configuration; NOT_DETECTED never waives the INS-01 re-calibration rule",
            "coverage": "planning k = 2; evaluated Student-t k when nu_eff is low (A3; CD-P-LOWDOF), documented",
        },
        "acceptance": {
            "rule": "repeatability_verdict(s_rel, nu, lane-25 u_T_max by n, CD-P-CONF): MEETS_N4/N6/N8 or "
                    "EXCEEDS_ALL_TARGETS. This is the no-plasma component only; the firing-condition u_T is S1b "
                    "(lane 25), so MEETS is necessary, not sufficient",
            "targets": {"u_T_max": t25["u_T_max"], "sigma_T_at_12mN": t25["sigma_T_at_12mN"]},
            "absolute_gate_context": t25["I-U-ABS-T"],
        },
        "record": _record("thrust_stand", "INS-01", "no-plasma per-reading repeatability of the stand in force "
                          "units, relative at 12 mN (1 sigma), and per-configuration slope shift",
                          ["per-configuration slopes and ln shifts", "tares (magnetic, cable, feed line)",
                           "inclination / temperature logs"]),
        "failure_meaning": [
            "EXCEEDS_ALL_TARGETS: D0 is already at risk before any plasma; the owner decides (widen delta, raise n, "
            "improve the stand / mount, OPTION-DIVERTER or another facility; lane 25) before S1b",
            "mass effect DETECTED and per-configuration calibration not repeatable: the paired R_arch reading is not "
            "admissible with this stand; a mass-independent (torsional) stand is the INS-01 alternative",
            "magnetic tare not repeatable: coil-current changes between arms cannot be separated from thrust",
        ],
    }

    cd02 = {
        "id": "CD-02",
        "title": "installation / reinstallation reproducibility (u_inst)",
        "instruments": ["INS-01", "INS-02", "INS-18"],
        "s1c4_categories": ["thrust_stand", "bus_power_metering"],
        "stage": "CD-02a pre-S1, no plasma (S1-C4 record); CD-02b is lane 25's S1b Hall-on re-mount series (after S1 "
                 "starts; its u_inst fixes n at LOCK-2 and is not part of S1-C4)",
        "purpose": "measure how much a configuration change (vent, remove and re-install the HW-0 feed spacer and "
                   "the thruster mount, re-connect power leads, pump down) moves the stand calibration and the power "
                   "channel gains - the no-plasma part of the lane-25 installation term G5",
        "equipment": ["as CD-01", "a stable DC reference source for a gain check of each re-connected power channel "
                      "(class TBD - requires owner, INS-02)"],
        "procedure": [
            "cycle k = 1..K: vent; remove and re-install the HW-0 feed spacer and the thruster mount exactly as a "
            "configuration change does (lane 25 S1b cycle definition); disconnect and re-connect the power leads at "
            "their break points; pump down; settle",
            "per cycle: in-situ force calibration (CD-01 levels) r times; power-channel gain check against the "
            "reference source r times",
            "K and r are lane 25's T-S1-REMOUNT-CYCLES and T-S1-READINGS-PER-CYCLE (PROPOSED there) so that CD-02a "
            "and S1b share one definition",
        ],
        "repeats": {"K": counts["T-S1-REMOUNT-CYCLES"], "r": counts["T-S1-READINGS-PER-CYCLE"]},
        "analysis": {
            "type_a": "ln_reproducibility(cycle-mean stand slopes) -> s_inst,stand with nu = K - 1; the same for each "
                      "measured power channel gain -> s_inst,i; the ln(P_bus) term is "
                      "pbus_installation_term(): s_inst,P = sqrt(sum_i w_i^2 s_inst,i^2) with w_i = P_i / P_bus at "
                      "the operating point (P_bus is a sum of channels; first-order propagation, independent "
                      "re-connection; shares TBD - requires the LOCK-1 power allocation; before that the share-free "
                      "bound max_i s_inst,i is used, valid for any shares); combined no-plasma installation term "
                      "sqrt(s_inst,stand^2 + s_inst,P^2) in ln units (T and P_bus enter ln(T/P_bus) with opposite sign "
                      "and independent re-connection)",
            "within_cycle_term": "the SD of K cycle means also contains the within-cycle repeatability s_r / sqrt(r) "
                                 "(one-way random-effects model), so s_inst from cycle means is CONSERVATIVE (it "
                                 "over-states the installation term). The acceptance uses the conservative value; "
                                 "within_cycle_corrected_reproducibility reports s_inst^2 = s_between^2 - s_r^2 / r "
                                 "alongside it for information (floored at 0, flagged when not resolved)",
            "coverage": "nu = K - 1 is low; A3 evaluated k documented (coverage_factor)",
            "dof_of_combined_term": "the combined term sums two variances that each have K - 1 degrees of freedom; "
                                    "its Welch-Satterthwaite nu_eff (GUM G.4.1) lies between K - 1 and 2 (K - 1). "
                                    "The verdict uses nu = K - 1, the lower end: this is CONSERVATIVE for the "
                                    "chi-square upper confidence bound (a larger nu gives a smaller bound), and the "
                                    "record states nu = K - 1 as a conservative choice, with nu_eff reported "
                                    "alongside for information",
        },
        "acceptance": {
            "rule": "repeatability_verdict(no-plasma installation term, K - 1 (conservative lower end of nu_eff), "
                    "lane-25 u_inst_max by n, CD-P-CONF). "
                    "Necessary, not sufficient: the Hall-on S1b series adds thermal and plasma re-seating effects",
            "targets": {"u_inst_max": t25["u_inst_max"]},
        },
        "record": _record("thrust_stand", "INS-01+INS-02", "no-plasma installation reproducibility of ln(T/P_bus) "
                          "(1 sigma, ln units, nu = K - 1)", ["per-cycle slopes and gains", "cycle log (vent/pump "
                                                              "times, torque values if specified by W3)"]),
        "failure_meaning": [
            "exceeds u_inst_max at n = 8 without plasma: the mount or lead re-connection alone consumes the G5 budget; "
            "fix the mount (fiducials, torque procedure) or re-connection before S1b; otherwise the owner decides (D0)",
            "a single cycle outlier: investigate and record; never dropped silently (it is a raw reading)",
        ],
    }

    channels = []
    for c in bus:
        st = c["lab_status"]
        if st == "MEASURED":
            plan = ("calibrate the load-plane V and I (or net RF / microwave power, INS-03) against the traceable "
                    "standard at CD-P-PWR-POINTS points over the channel range with CD-P-PWR-REPEATS readings each")
        elif st == "MEASURED_OR_LEDGER":
            plan = ("calibrate as MEASURED if a propulsion heater is present in the lab; otherwise no channel and the "
                    "ledger input carries its own evidence class")
        elif st == "LEDGER_INPUT":
            plan = ("lab electronics are metered as evidence where present (same calibration method) but the component "
                    "enters P_bus as a LOCK-1 ledger input; no capability claim is made for it")
        else:
            plan = ("no lab channel exists; the value is RECONSTRUCTED from the upstream ICD or UNAVAILABLE - never "
                    "zero, never a placeholder; nothing to demonstrate")
        channels.append({"component": c["component"], "architectures": c["architectures"], "lab_status": st,
                         "lab_measurement": c["lab_measurement"], "demonstration": plan})

    cd03 = {
        "id": "CD-03",
        "title": "power-channel calibration per bus_power_boundary_v1 component (incl. discharge current)",
        "instruments": ["INS-02", "INS-03", "INS-04", "INS-18"],
        "s1c4_categories": ["bus_power_metering", "discharge_current"],
        "stage": "pre-S1 bench / facility, no plasma (S1a); S1-C4 record",
        "purpose": "demonstrate each lab power channel against a traceable DC standard, and the RF / microwave "
                   "load-plane power, at the repeatability lane 25 needs, with pickup bounded",
        "boundary": "abep_sim/arch_boundary.py BOUNDARY_VERSION 'bus_power_boundary_v1' (component ids as listed "
                    "in the instrumentation definition bus_power_channels; resolved read-only, never imported here)",
        "channels": channels,
        "equipment": [
            "traceable DC voltage / current calibrator or reference meter with reference shunt (class TBD - requires "
            "owner, INS-02 open decision 'traceable calibration class')",
            "the delivered 4-wire sense leads, shunts or zero-flux transducers and the DAQ in their final wiring",
            "matched dummy loads for the RF and microwave generators (DUMMY_LOAD_PICKUP control, lane 06, adopted by "
            "the package reconciliation, as cited by INS-02)",
            "directional couplers and power sensors with certificates (INS-03)",
            "wide-band current probe on the discharge line (INS-04)",
        ],
        "procedure": [
            "per MEASURED channel: apply CD-P-PWR-POINTS reference levels spanning the channel range (range TBD - "
            "requires the LOCK-1 allocation), CD-P-PWR-REPEATS simultaneous V/I readings each, ascending and "
            "descending",
            "repeat at two shunt / transducer temperatures within the S1 thermal range (range TBD - S1) to "
            "characterise the temperature coefficient (INS-02 calibration)",
            "DUMMY_LOAD_PICKUP: RF and microwave generators into matched dummy loads at each planned power level with "
            "the Hall off; record every DC channel (pickup bound)",
            "INS-03: coupler/sensor certificates; load-plane loss characterisation into matched dummy loads at each "
            "P_lo / P_hi and frequency (method TBD - requires the RF / microwave design, W3)",
            "INS-04: probe gain and offset against the calibrated hall_discharge DC current channel at several DC "
            "levels; noise floor with the discharge supply connected and off",
        ],
        "repeats": {"points": rep("CD-P-PWR-POINTS"), "readings": rep("CD-P-PWR-REPEATS")},
        "analysis": {
            "type_a": "per channel and point: relative SD of the power reading (type_a); fit residuals and "
                      "nonlinearity (linear_calibration)",
            "type_b": "calibrator certificate, temperature coefficient over the S1 range, pickup bound (as a "
                      "rectangular bound / sqrt(3) unless the pickup is corrected), RF mismatch uncertainty (INS-03)",
            "sum": "if every channel meets u_P_max the sum does (instrumentation derived.channel_sum_check)",
            "source_scale": "u_src from the INS-03 Type B chain compared with u_src_max(f_src) - f_src needs the LOCK-1 "
                            "source allocation",
            "coverage": "A3 k rule (coverage_factor)",
        },
        "acceptance": {
            "rule": "per MEASURED channel: repeatability_verdict(relative s, nu, lane-25 u_P_max by n, CD-P-CONF); "
                    "I_d floor: offset + noise (1 sigma) <= I-U-ID-FLOOR x I_d,ref (I_d,ref TBD - LOCK-1); source "
                    "chain: u_src <= u_src_max(f_src) at the pre-registered f_src; pickup: reported, and a channel "
                    "whose pickup exceeds its own u_P_max share is not usable source-on until fixed",
            "targets": {"u_P_max": t25["u_P_max"], "sigma_Pbus_at_1500W": t25["sigma_Pbus_at_1500W"],
                        "u_src_max_by_f_src": t25["u_src_max_by_f_src"], "I-U-ID-FLOOR": t25["I-U-ID-FLOOR"],
                        "absolute_gate_context": t25["I-U-ABS-P"]},
        },
        "record": _record("bus_power_metering", "INS-02", "per-channel relative per-reading repeatability and "
                          "calibration uncertainty (1 sigma), per bus_power_boundary_v1 component",
                          ["component id", "lab_status", "pickup bound per channel", "temperature coefficient"]),
        "record_discharge_current": _record("discharge_current", "INS-04", "I_d probe gain uncertainty and offset + "
                                           "noise floor relative to the DC channel"),
        "failure_meaning": [
            "a MEASURED channel EXCEEDS_ALL_TARGETS: P_bus of that consumer cannot support R_arch at any n <= "
            "T-N-MAX; better shunt / transducer or range before S1",
            "RF / microwave pickup on DC channels above budget: source-on readings of the affected channels are "
            "invalid until shielding / filtering is fixed and CD-03 repeated",
            "u_src above u_src_max(f_src): the source-power scale term alone breaks the G3 budget; the owner may "
            "change the allocation or the load-plane method (INS-03 AT_RISK)",
            "compressor / ledger components are never 'failed' here: they are not measured and never zero",
        ],
    }

    cd04 = {
        "id": "CD-04",
        "title": "MFC behaviour across the required low-flow range (gas correction, zero drift)",
        "instruments": ["INS-05", "INS-06", "INS-07", "INS-18"],
        "s1c4_categories": ["flow"],
        "stage": "pre-S1 (S1a) with the MFCs installed in their final configuration and orientation; S1-C4 record",
        "purpose": "show each MFC range meets the flow uncertainty that the knee scan and the I-FLOW-CONSERVATIVE "
                   "absolute-gate rule need, down to the lower end of the candidate range",
        "range": mfc,
        "equipment": [
            "one thermal MFC per pure gas and range (N2, O2 anode; Xe cathode), INS-05; the range set follows "
            "range.ranges_needed and the registered W1 points (TBD)",
            "a primary flow calibrator: constant-volume (rate-of-rise) or constant-pressure (REF-SNYDER2017 as cited "
            "by INS-05), traceable, able to reach the lower end of the smallest range (capability TBD - requires the "
            "calibrator choice)",
            "inlet pressure and temperature sensors at the MFC (expected inlet conditions), INS-06 / INS-07 at the "
            "valve outlet",
        ],
        "procedure": [
            "calibrate every MFC on its own working gas, installed in the final orientation, at the expected inlet "
            "pressure and temperature (REF-SNYDER2017 as cited by INS-05)",
            "points per range: 10, 20, 50 and 100 % of FS (the points of the instrumentation MFC table) plus every "
            "registered W1 flow in that range (TBD - W1/LOCK-1); CD-P-MFC-REPEATS readings each, ascending and "
            "descending",
            "gas correction: no gas correction factor is used where the MFC is calibrated on its own gas; where one "
            "is unavoidable (e.g. a range only available on N2 used for O2) measure the actual ratio against the "
            "primary calibrator on the working gas and adjust it to the sensor operating temperature "
            "(REF-SNYDER2017 as cited by INS-05); record the factor with its uncertainty",
            "zero drift: valve closed, zero flow, MFC at operating temperature; log the output over the planned "
            "dwell (hold time TBD - requires owner, INS-01 note) and repeat after a power cycle",
            "air-surrogate check: set an N2/O2 pair and verify the composition by the two primary-calibrated flows "
            "(instrumentation derived.mixture_mass_fraction_u)",
        ],
        "repeats": {"readings_per_point": rep("CD-P-MFC-REPEATS"),
                    "min_setpoint_fraction": rep("CD-P-MFC-MINFRAC")},
        "analysis": {
            "type_a": "per point: relative_point_errors against the calibrator and their SD (repeatability, used for "
                      "R_arch: same MFC, same setpoint in every arm); hysteresis = ascending - descending mean",
            "type_b": "calibrator certificate (volume, pressure, temperature, time), gas-correction factor if used, "
                      "zero drift over the dwell (drift_rate x dwell), orientation zero shift if the installed "
                      "orientation differs from the calibration orientation",
            "coverage": "A3 k rule",
        },
        "acceptance": {
            "rule": "for R_arch: repeatability at every registered point reported (target TBD - requires the W1 "
                    "tolerance and the knee-scan resolution, INS-05); for the absolute gate: the expanded relative "
                    "uncertainty at each registered point sets the I-FLOW-CONSERVATIVE margin (the delivered flow "
                    "may not exceed the registered flow at one-sided alpha); every registered point must sit at or "
                    "above CD-P-MFC-MINFRAC of its MFC FS; zero drift over the dwell reported against the smallest "
                    "registered flow of that range",
            "targets": {"knee_scan_resolution": tbd("W1 test-point flows and the lane-25 knee levels",
                                                    "fo_feed_state_closure"),
                        "I-FLOW-CONSERVATIVE": {"see": f"{INS_REL}: proposed_thresholds I-FLOW-CONSERVATIVE"}},
        },
        "record": _record("flow", "INS-05", "per MFC range and gas: relative repeatability and expanded "
                          "calibration uncertainty at each calibrated point, zero drift per hour",
                          ["gas", "range FS", "gas-correction factor (if any) with uncertainty", "orientation",
                           "inlet P/T during calibration"]),
        "failure_meaning": [
            "the lower end is not resolved by any available range: registered low-flow points (and the knee scan's "
            "low end) cannot be set with a known flow; a smaller range or an in-line primary calibrator is needed",
            "gas-correction factor uncertainty dominates: buy / calibrate an own-gas range instead",
            "zero drift over the dwell comparable to the smallest registered flow: the dwell or the range must change "
            "(owner, hold time)",
        ],
    }

    cd05 = {
        "id": "CD-05",
        "title": "B(z) measurement repeatability at actual coil currents",
        "instruments": ["INS-09", "INS-02", "INS-24", "INS-18"],
        "s1c4_categories": ["magnetic_field_Bz"],
        "stage": "pre-S1 (S1a, magnetostatic, room temperature; hot-state effects TBD, lane 25 Sec. 12); S1-C4 record",
        "purpose": "show that a B(z) map at the operating coil currents reproduces within a stated uncertainty, so "
                   "it can serve as a condition record (INS-09) and, if W5 pre-registers it, as held-out evidence "
                   "(VO-BZ) - closing the P5 gap of unpublished coil currents / measured B(z)",
        "equipment": [
            "Hall-probe gaussmeter with a calibration certificate; a reference field for in-situ checks (reference "
            "magnet or calibrated coil; class TBD) and a zero-field chamber for the offset",
            "positioning stage with a calibrated position scale; fixture keyed to the H-1 fiducials (W3 B(z) access)",
            "coil supplies metered on INS-02 (hall_magnet, ecr_magnet); coil 4-wire resistance and hot-spot "
            "thermocouples (INS-24); magnet temperatures (MCQ-W4-03)",
        ],
        "procedure": [
            "probe offset in the zero-field chamber and gain in the reference field before and after each session",
            "approach protocol (PROPOSED, to be frozen): bring every coil from zero to the operating current "
            "monotonically after a defined cycling sequence; the same protocol in every configuration",
            "per configuration (HW-0, HW-RF, HW-ECR with the ECR magnet on and off): CD-P-BZ-MAPS complete centreline "
            "(and exit-region radial) maps with the probe removed and re-seated between maps",
            "hysteresis: CD-P-BZ-CYCLES current cycles, B at the peak-field location recorded ascending and "
            "descending",
            "every map carries coil currents, coil average and hot-spot temperatures and magnet temperatures "
            "(MCQ-W4-03), position-scale readings and timestamps",
        ],
        "repeats": {"maps": rep("CD-P-BZ-MAPS"), "current_cycles": rep("CD-P-BZ-CYCLES")},
        "analysis": {
            "type_a": "pointwise SD across maps; repeatability of B_peak and of its axial location z_peak; hysteresis "
                      "offset (ascending - descending) at the peak",
            "type_b": "probe calibration certificate, reference-field uncertainty, position-scale uncertainty "
                      "propagated through dB/dz, probe angular alignment, coil-current meter (INS-02)",
            "coverage": "A3 k rule; nu = maps - 1 is low, so the evaluated k is expected and documented",
        },
        "acceptance": {
            "rule": "reported against the W5 pre-registered B(z) comparison tolerance when it exists (TBD); until "
                    "then no pass/fail is claimed, only the demonstrated repeatability; hysteresis offset larger "
                    "than the map repeatability makes the approach protocol mandatory in every configuration",
            "targets": {"Bz_tolerance": tbd("the W5 pre-registered B(z) comparison tolerance and the H-1 design "
                                            "range (W3)", "fo_hall_validation_prereg_draft")},
        },
        "record": _record("magnetic_field_Bz", "INS-09", "B(z) map repeatability (1 sigma) at the operating coil "
                          "currents, B_peak and z_peak repeatability, hysteresis offset",
                          ["configuration", "coil currents", "coil/magnet temperatures (MCQ-W4-03)",
                           "approach protocol id"]),
        "failure_meaning": [
            "maps not reproducible at fixed current: B(z) cannot be a held-out observable and every configuration "
            "needs its own map on its own day; find the cause (fixture, probe alignment, remanence) first",
            "strong hysteresis: the coil-current history becomes a controlled variable of every run (recorded, "
            "pre-registered approach)",
            "ECR magnet on/off changes the Hall B(z) beyond repeatability: that is a real configuration difference "
            "and is reported as such, not a capability failure",
        ],
    }

    cd06 = {
        "id": "CD-06",
        "title": "DAQ synchronization / common time base",
        "instruments": ["INS-18", "INS-04", "INS-02", "INS-01", "INS-05", "INS-08", "INS-17"],
        "s1c4_categories": ["stability_oscillations"],
        "stage": "pre-S1 (S1a) with the final DAQ, cabling and channel set; S1-C4 record (partial for "
                 "stability_oscillations: the oscillation band itself needs the S1 I_d spectrum)",
        "purpose": "show that every channel shares one time base with a measured skew and drift, so V x I products, "
                   "I_d(t) and the slow channels can be aligned (INS-18)",
        "equipment": [
            "a reference pulse / step generator fanned out to every channel type with cable delays measured",
            "the final DAQ chain(s); where DAQs are distributed, a shared hardware clock/trigger or a network time "
            "protocol (IEEE 1588 named as one generic option, REF-IEEE1588 metadata only)",
            "a swept-sine source for the amplitude/phase response of the fast channels",
        ],
        "procedure": [
            "inject CD-P-DAQ-EDGES common edges over at least the longest planned dwell (TBD - owner hold time); slow "
            "channels (temperature, flow, pressure) receive a step through a test input where the sensor cannot see "
            "the edge",
            "record every channel; subtract the measured cable delays",
            "swept sine through the V, I and I_d(t) chains up to the band edge (TBD - S1 spectrum): gain and phase",
            "verify that V and I of each power channel are sampled simultaneously (same edge within the skew budget)",
        ],
        "repeats": {"edges": rep("CD-P-DAQ-EDGES")},
        "analysis": {
            "type_a": "channel_skew: worst skew, per-channel offset SD and offset drift (clock drift)",
            "type_b": "cable-delay measurement uncertainty, generator edge jitter (certificate)",
            "planning": "phase_error_deg(f, skew) - see planning_tables.phase_error",
        },
        "acceptance": {
            "rule": "worst skew and offset drift reported; pass/fail against the skew allowance derived from the S1 "
                    "oscillation band (INS-18 TBD) - until then no pass/fail is claimed. Hard rule: V and I of one "
                    "power channel must be simultaneous (mean of the product, not product of the means, when I_d "
                    "oscillates)",
            "targets": {"skew_allowance": tbd("skew allowance from the S1 oscillation band (INS-18)", "S1")},
        },
        "record": _record("stability_oscillations", "INS-18", "worst inter-channel skew and clock drift of the "
                          "common time base", ["channel list", "cable delays", "swept-sine response"]),
        "failure_meaning": [
            "skew or drift not bounded: time-resolved quantities (I_d(t), oscillation-power correlations, "
            "extinction timing) cannot be aligned across channels; V x I products are biased when I_d oscillates",
        ],
    }

    cd07 = {
        "id": "CD-07",
        "title": "temperature-channel performance (incl. the A3 cathode-temperature rule)",
        "instruments": ["INS-17", "INS-23", "INS-24", "INS-07", "INS-18"],
        "s1c4_categories": ["temperature"],
        "stage": "pre-S1: sensor calibration on the bench (before installation) and in-situ checks in the facility "
                 "(S1a); S1-C4 record",
        "purpose": "show each temperature channel's calibration, cold-junction performance and immunity to pickup, "
                   "and enforce the owner's cathode-temperature labelling rule (A3)",
        "equipment": [
            "reference thermometer and comparison medium (bath / dry block / furnace per range) for calibration by "
            "comparison (ASTM E220, metadata only - verify; it applies to unused thermocouples)",
            "cold-junction reference (ice point or calibrated reference junction)",
            "the final DAQ inputs and cabling; coil supplies, RF / microwave generators into dummy loads and HV "
            "supplies for the pickup check (DUMMY_LOAD_PICKUP control)",
            "C-1: cathode-tube thermocouple (mandatory, A3); emitter pyrometer only if HW-C1-09 (b) records a "
            "defensible line of sight and an emissivity treatment (A3)",
        ],
        "procedure": [
            "calibrate each thermocouple type/lot by comparison at CD-P-TC-POINTS temperatures spanning its range "
            "(ranges TBD - W3 positions and life-mechanism limits); unused thermocouples only (ASTM E220 scope)",
            "cold-junction check at the reference point for every DAQ input",
            "in-situ isothermal cross-check: after a long soak with every heater and supply off, all channels on the "
            "same body agree within their calibration uncertainty (PROPOSED check)",
            "pickup: energise coils, RF / microwave into dummy loads and HV supplies one at a time; record every "
            "temperature channel",
            "C-1 (A3): the cathode-tube thermocouple is logged continuously on INS-18 under the label "
            "'cathode_tube_temperature'; no channel is labelled 'emitter_temperature' unless a pyrometer is "
            "installed; without a pyrometer the emitter temperature is recorded as 'unmeasured' (no value inferred "
            "from the tube)",
            "pyrometer (only if installed): calibrated against a thermocouple on a reference body over the emitter "
            "temperature range; emissivity treatment recorded from the HW-C1-09 (b) design record (INS-23)",
            "coil winding: R0 and T0 of each coil isothermally before S1 (INS-24)",
        ],
        "repeats": {"points": rep("CD-P-TC-POINTS")},
        "analysis": {
            "type_a": "deviation from the reference at each point, repeated readings (type_a); isothermal spread",
            "type_b": "reference thermometer certificate, comparison-medium uniformity, cold-junction uncertainty, "
                      "pickup bound",
            "coverage": "A3 k rule",
            "labelling": "capability_analysis.record_item_errors enforces the A3 rules on every temperature record: "
                         "declared scope, the mandatory cathode-tube thermocouple on C-1 items, no emitter label on a "
                         "non-pyrometer sensor, 'unmeasured' emitter status without a pyrometer",
        },
        "acceptance": {
            "rule": "demonstrated uncertainty per channel reported against the INS-17 / INS-23 / INS-24 requirement "
                    "when it exists (TBD: T-SETTLE, life-mechanism resolution, coil hot-spot margin); A3 labelling "
                    "is a hard pass/fail: a record that labels a thermocouple as emitter temperature, or gives an "
                    "emitter value without a calibrated pyrometer, fails",
            "targets": {"INS-17": tbd("T-SETTLE from S1 thermal time constants (lane 25)"),
                        "INS-23": tbd("oxidation / sputter-yield resolution and LaB6 bands (W3 HW-C1-03)",
                                      "fo_hardware_definition"),
                        "INS-24": tbd("coil hot-spot margin to the magnet-wire insulation class (MCQ-QT-06)",
                                      "fo_magnet_coil_qualification + fo_hardware_definition")},
        },
        "record": _record("temperature", "INS-17+INS-23+INS-24", "per-channel calibration uncertainty (1 sigma) "
                          "and pickup bound", ["channel labels", "sensor_type", "emissivity_treatment (pyrometer)",
                                               "emitter_temperature_status"], scope="cathode_c1 for the C-1 item"),
        "failure_meaning": [
            "pickup under RF / microwave / coil operation: the affected channel is invalid source-on (for example "
            "the stand thermocouples feeding the INS-01 drift model) until fixed",
            "no cathode-tube thermocouple installed: the A3 mandatory C-1 provision is missing; S1a cathode "
            "operation should not proceed (owner / S1a gate)",
            "no defensible pyrometer view: not a failure - the emitter temperature is 'unmeasured' by rule",
        ],
    }
    return [cd01, cd02, cd03, cd04, cd05, cd06, cd07]


def s1_contract(s1: dict, demos: list) -> dict:
    c4 = next(c for c in s1["conditions"] if c["id"] == "S1-C4")
    alt = c4["alternatives"][0]
    req = next(r for r in alt["rules"] if r["type"] == "covers")["required"]
    covered = {}
    for d in demos:
        for c in d["s1c4_categories"]:
            covered.setdefault(c, []).append(d["id"])
    gaps = {
        "pressure": "INS-06 feed pressure and INS-08 background gauges (capacitance manometer zero/span, gauge "
                    "calibration on each gas and mixture) - not in this lane's owner list (A3 "
                    "W4_capability_demonstration_prep); W4 must add it before S1-C4 can be satisfied",
        "species_divergence": "INS-13 ExB probe and INS-15 Faraday probes - not in this lane's owner list; W4 must add "
                              "it or the owner reduces the S1-C4 category set (README open item 3, lane 25 s1_plan "
                              "names M1, M2, M3, M9, M10, M11 only)",
    }
    return {
        "condition": "S1-C4 instrumentation capability demonstrated",
        "gate_file": S1_REL,
        "artifact_path": alt["paths"][0],
        "raw_data_prefix": "docs/experiments/instrumentation/raw/",
        "gate_rules_copied": alt["rules"],
        "required_categories": req,
        "coverage_by_this_preparation": {c: covered.get(c, []) for c in req},
        "uncovered_categories": {c: gaps.get(c, "partial - see the demonstration") for c in req if c not in covered},
        "partial_categories": {"stability_oscillations": "CD-06 demonstrates the time base only; oscillation "
                                                         "detection needs the S1 I_d spectrum"},
        "produced_by": "W4 after the measurements: one item per demonstrated instrument, raw data committed under "
                       "the raw prefix, analysis by capability_analysis.py at a pinned sha256, the calibration plan "
                       "frozen by the owner (S1-C5), accepted by the owner",
        "this_lane_writes": "neither the artifact nor raw data; only the procedures, the analysis and the record "
                            "schema (capability_record_item_v1.schema.json)",
        "calibration_plan_link": "the procedures here are candidate entries for the owner-frozen S1-C5 plan "
                                 "(docs/experiments/instrumentation/calibration_plan_frozen.json: procedures[] with "
                                 "category, procedure, traceability, acceptance_rule); see calibration_plan_candidates",
    }


def calibration_plan_candidates(demos: list) -> list:
    out = []
    for d in demos:
        for cat in d["s1c4_categories"]:
            out.append({"category": cat, "demonstration_id": d["id"], "procedure": "; ".join(d["procedure"]),
                        "traceability": "; ".join(e for e in d["equipment"] if "traceab" in e or "certificate" in e
                                                  or "reference" in e) or "see equipment",
                        "acceptance_rule": d["acceptance"]["rule"], "status": "PROPOSED"})
    return out


# ----------------------------------------------------------------------------------------------------------------------
# S1a calibration-procedure candidates (keyed to the S1a gate S1A-C4 and the S1A-FW data firewall)
# ----------------------------------------------------------------------------------------------------------------------
#: (procedure_id, S1A-C4 category, CD item, s1a_data_class, scope of the data this procedure produces).
#: The data classes are the S1A-FW ids of the pinned S1a conditions file (allowed classes, or a custody-held REG-*
#: registration input); the split follows its firewall_reference_classes (PROPOSED there), so that no S1a procedure
#: mixes an allowed class with a registration input. PROPOSED by this lane; the owner freezes.
S1A_PROCEDURE_MAP = (
    ("S1A-P-TS-01", "thrust_stand", "CD-01", "CALIBRATION",
     "in-situ force calibration constants (slope, offset, magnetic and cable tares with coils energised, discharge off) "
     "and their uncertainty, per configuration"),
    ("S1A-P-TS-02", "thrust_stand", "CD-01", "REPEATABILITY",
     "repeatability of the force calibration within a mount and the configuration (mass-change) shift statistics "
     "between HW-0 / HW-RF / HW-ECR mounts (modules or dummies), no plasma"),
    ("S1A-P-TS-03", "thrust_stand", "CD-02", "REINSTALLATION",
     "CD-02a only: no-plasma installation / re-installation reproducibility of the stand slope (optional in S1a per "
     "the gate's required_categories_status; the Hall-on re-mount series CD-02b is S1b, never S1a)"),
    ("S1A-P-PC-01", "power_channels", "CD-03", "CALIBRATION",
     "gain / offset / temperature coefficient of every MEASURED bus_power_boundary_v1 channel (incl. the I_d / V_d "
     "channels calibrated without plasma), coupler / sensor load-plane characterisation into dummy loads"),
    ("S1A-P-PC-02", "power_channels", "CD-03", "NOISE",
     "channel noise floors and the DUMMY_LOAD_PICKUP bound (RF / microwave generators into matched dummy loads, "
     "Hall off)"),
    ("S1A-P-PC-03", "power_channels", "CD-02", "REINSTALLATION",
     "CD-02a only: power-channel gain after lead disconnection / re-connection, no plasma"),
    ("S1A-P-MFC-01", "mass_flow_controllers", "CD-04", "REG-FEED",
     "MFC calibration on the working gas incl. every registered W1 flow, gas-correction factors and the air-surrogate "
     "composition check: this is the calibrated feed-setpoint record, a custody-held registration input (S1A-FW "
     "CALIBRATION excludes it); released only via the custodian after LOCK-H1"),
    ("S1A-P-MFC-02", "mass_flow_controllers", "CD-04", "DRIFT",
     "MFC zero drift with the valve closed (zero flow) over the dwell and after a power cycle; carries no registered "
     "setpoint value"),
    ("S1A-P-BZ-01", "magnetic_field_Bz", "CD-05", "CALIBRATION",
     "Hall-probe offset (zero-field chamber) and gain (reference field) before and after each session: probe "
     "constants only"),
    ("S1A-P-BZ-02", "magnetic_field_Bz", "CD-05", "REG-BZ",
     "the B(z) maps of the H-1 magnetic circuit at actual coil currents, per configuration, and the hysteresis "
     "readings at the peak-field location: custody-held registration input, released only after LOCK-H1"),
    ("S1A-P-BZ-03", "magnetic_field_Bz", "CD-05", "REPEATABILITY",
     "map-to-map dispersion statistics at fixed coil current (probe re-seated between maps) as relative / "
     "dimensionless spreads; the custodian computes them from the REG-BZ maps and releases no field value"),
    ("S1A-P-DAQ-01", "daq_time_base", "CD-06", "CHANNEL_PERFORMANCE",
     "common-edge skew, offset drift, V/I simultaneity and swept-sine gain / phase of the fast chains with test "
     "signals, no plasma"),
    ("S1A-P-TEMP-01", "temperature_channels", "CD-07", "CALIBRATION",
     "thermocouple calibration by comparison, cold-junction check, pyrometer calibration (only if installed), coil "
     "R0 / T0; in-situ isothermal cross-check"),
    ("S1A-P-TEMP-02", "temperature_channels", "CD-07", "NOISE",
     "temperature-channel pickup with coils, RF / microwave into dummy loads and HV supplies energised one at a time, "
     "no plasma"),
)

CATHODE_TEMPERATURE_LABELLING = (
    "A3 decisions.cathode_temperature: the cathode-tube thermocouple is mandatory and is logged under the label "
    "'cathode_tube_temperature'; it is never labelled emitter temperature. A channel is labelled "
    "'emitter_temperature' only if a calibrated pyrometer with a recorded line of sight and emissivity treatment "
    "(HW-C1-09 (b)) is installed; otherwise the emitter temperature is recorded as 'unmeasured' and no value is "
    "inferred from the tube. Enforced on every temperature record by capability_analysis.record_item_errors")


def _s1a_gate(s1a: dict) -> tuple:
    c4 = next(c for c in s1a["conditions"] if c["id"] == "S1A-C4")
    fw = next(c for c in s1a["conditions"] if c["id"] == "S1A-FW")
    c4alt, fwalt = c4["alternatives"][0], fw["alternatives"][0]

    def covers(rules, field):
        return next(r for r in rules if r["type"] == "covers" and r["field"] == field)["required"]
    classes = {"allowed_classes": covers(fwalt["rules"], "allowed_classes"),
               "registration_inputs": covers(fwalt["rules"], "registration_inputs"),
               "forbidden_or_embargoed": covers(fwalt["rules"], "forbidden_or_embargoed")}
    return c4alt, classes


def _nonempty(v) -> bool:
    return isinstance(v, str) and v.strip() != "" and not v.strip().upper().startswith(("TBD", "TBC", "TBA"))


def s1a_rule_check(procedures: list, c4alt: dict, classes: dict) -> list:
    """Evaluate the S1A-C4 rules on the 'procedures' list only (covers / each_item / any_item). The owner-only fields
    (status, decided_by, decided_utc, data_firewall) are not checked here: they are set when the owner freezes.
    member_of_artifact is checked against the S1A-FW class ids named in the gate's own firewall rules (the firewall
    artifact does not exist yet; the gate re-checks against the frozen artifact). Returns [{rule, result, detail}]."""
    out = []
    for r in c4alt["rules"]:
        if r.get("field") != "procedures":
            continue
        fails = []
        if r["type"] == "covers":
            have = {p.get(r["key"]) for p in procedures}
            fails = [f"missing {x}" for x in r["required"] if x not in have]
        elif r["type"] in ("each_item", "any_item"):
            per = []
            for p in procedures:
                e = []
                for sub in r["rules"]:
                    v = p.get(sub["field"])
                    if sub["type"] == "nonempty_string" and not _nonempty(v):
                        e.append(f"{p.get('procedure_id')}: {sub['field']} empty")
                    elif sub["type"] == "equals" and v != sub["value"]:
                        e.append(f"{p.get('procedure_id')}: {sub['field']} != {sub['value']}")
                    elif sub["type"] == "member_of_artifact":
                        ok = set()
                        for lf in (sub["list_field"] if isinstance(sub["list_field"], list) else [sub["list_field"]]):
                            ok |= set(classes[lf])
                        bad = set()
                        for xf in sub.get("exclude_list_fields", []):
                            bad |= set(classes[xf])
                        if v not in ok or v in bad or (sub.get("exclude_pattern") and
                                                        __import__("re").search(sub["exclude_pattern"], str(v))):
                            e.append(f"{p.get('procedure_id')}: s1a_data_class {v!r} not a firewall-allowed / "
                                     f"registration id")
                    elif sub["type"] not in ("nonempty_string", "equals", "member_of_artifact"):
                        raise ValueError(f"unhandled S1A-C4 sub-rule type {sub['type']!r}")
                per.append(e)
            fails = [x for e in per for x in e] if r["type"] == "each_item" else \
                ([] if any(not e for e in per) else ["no item satisfies the rule"])
        else:
            raise ValueError(f"unhandled S1A-C4 rule type {r['type']!r}")
        out.append({"rule": r["type"] + (f" ({r['what']})" if r.get("what") else ""),
                    "result": "PASS" if not fails else "FAIL", "detail": fails})
    return out


def s1a_procedure_candidates(demos: list, s1a: dict) -> dict:
    c4alt, classes = _s1a_gate(s1a)
    by_id = {d["id"]: d for d in demos}
    procs = []
    for pid, cat, cd, cls, scope in S1A_PROCEDURE_MAP:
        d = by_id[cd]
        tr = "; ".join(e for e in d["equipment"] if any(w in e for w in ("traceab", "certificate", "reference",
                                                                         "calibrat")))
        p = {"procedure_id": pid, "category": cat, "demonstration_id": cd, "s1a_data_class": cls,
             "data_scope": scope,
             "procedure": f"{cd} steps restricted to the data scope above (no plasma, no H-1 anode discharge): "
                          + "; ".join(d["procedure"]),
             "traceability": tr or f"{cd} equipment list (no reference standard named there)",
             "acceptance_rule": d["acceptance"]["rule"],
             "custody": ("custody-held registration input: raw data and results go to the owner-designated data "
                         "custodian only, released after LOCK-H1 (S1A-FW; W5 K1)") if cls.startswith("REG-") else
                        "S1a calibration-class data (S1A-FW allowed class); may go to every track",
             "status": "PROPOSED"}
        if cat == "temperature_channels":
            p["cathode_temperature_labelling"] = CATHODE_TEMPERATURE_LABELLING
        procs.append(p)
    check = s1a_rule_check(procs, c4alt, classes)
    if any(c["result"] != "PASS" for c in check):
        raise ValueError(f"S1a candidate procedures fail the S1A-C4 rules: {check}")
    return {
        "gate_file": S1A_REL,
        "gate_condition": "S1A-C4 frozen calibration procedures (alternative S1A-C4-frozen-procedures)",
        "frozen_artifact_path": c4alt["paths"][0],
        "this_lane_writes": "the candidate only (s1a_calibration_procedures_candidate_v1.json); the owner freezes it "
                            "at the frozen path with status FROZEN, decided_by owner, decided_utc and the sha256 "
                            "reference to the frozen S1A-FW firewall. The gate never accepts the candidate itself",
        "firewall_class_ids_used": classes,
        "firewall_class_ids_basis": "the covers lists of the S1A-FW rules in the pinned gate file (the class lists "
                                    "are PROPOSED there; the frozen firewall artifact does not exist yet). If the "
                                    "owner's frozen firewall changes an id, this map must be re-keyed",
        "category_map": {c: sorted({p["demonstration_id"] for p in procs if p["category"] == c})
                         for c in dict.fromkeys(p["category"] for p in procs)},
        "not_in_s1a": ["CD-02b (Hall-on re-mount series: S1b, N4)", "any H-1 anode discharge reading (S1A-FW "
                       "H1-ANY-HALL-OPERATING-POINT)", "the S1-C4 categories pressure and species_divergence (no CD "
                       "item; see s1_contract.uncovered_categories)"],
        "procedures": procs,
        "rule_check_on_procedures": check,
    }


def s1a_candidate_artifact(cands: dict) -> dict:
    """The candidate in the shape of the gate artifact. Owner fields are deliberately not filled: the gate fails
    until the owner freezes it."""
    return {
        "schema": "abep.s1a_calibration_procedures.v1",
        "id": "s1a_calibration_procedures",
        "status": "CANDIDATE_NOT_FROZEN",
        "decided_by": "not decided - owner freezes",
        "decided_utc": "not decided",
        "data_firewall": {"path": "docs/experiments/custody/s1a_data_firewall_frozen.json",
                          "sha256": "not available - requires the owner-frozen S1A-FW firewall"},
        "generated_by": SCRIPT_REL,
        "gate_file": {"path": S1A_REL, "sha256": PINNED[S1A_REL]},
        "freeze_instructions": "owner: review, set status FROZEN, decided_by owner, decided_utc, data_firewall "
                               "{path, sha256} of the frozen firewall, and write to "
                               + cands["frozen_artifact_path"],
        "procedures": [{k: v for k, v in p.items()} for p in cands["procedures"]],
    }


def record_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "docs/experiments/capability_demo/capability_record_item_v1.schema.json",
        "title": "W4 capability-demonstration record item (one per demonstrated instrument)",
        "description": "Shape of each item of instruments[] in docs/experiments/instrumentation/"
                       "capability_demonstration_v1.json (S1-C4). Superset of the S1-C4 each_item rules; the S1 gate "
                       "additionally recomputes sha256 references against the repository. Generated by "
                       f"{SCRIPT_REL}.",
        "type": "object",
        "required": ["category", "instrument_id", "demonstration_id", "evidence_class", "calibration_date", "raw_data",
                     "demonstrated_uncertainty", "coverage", "analysis_script_sha256", "calibration_plan_sha256",
                     "verdict"],
        "properties": {
            "category": {"enum": list(A.S1C4_CATEGORIES)},
            "instrument_id": {"type": "string", "minLength": 1},
            "demonstration_id": {"type": "string", "pattern": "^CD-0[1-9]"},
            "evidence_class": {"const": "measured"},
            "calibration_date": {"type": "string",
                                 "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z)?$"},
            "raw_data": {"type": "object", "required": ["path", "sha256"],
                         "properties": {"path": {"type": "string",
                                                 "pattern": "^docs/experiments/instrumentation/raw/"},
                                        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}},
            "demonstrated_uncertainty": {"type": "object", "required": ["value", "unit", "source", "evidence_class"],
                                         "properties": {"value": {"type": ["number", "object"]},
                                                        "unit": {"type": "string", "minLength": 1},
                                                        "source": {"type": "string", "minLength": 1},
                                                        "evidence_class": {"const": "measured"}}},
            "coverage": {"type": "object", "required": ["k", "nu_eff", "low_effective_dof"],
                         "properties": {"k": {"type": "number"}, "nu_eff": {"type": ["number", "string"]},
                                        "low_effective_dof": {"type": "boolean"}}},
            "type_a": {"type": "object"},
            "type_b": {"type": "array"},
            "verdict": {"type": "string"},
            "analysis_script_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "calibration_plan_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "scope": {"type": "string"},
            "emitter_temperature_status": {"type": "string"},
            "channels": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"}, "label": {"type": "string"},
                "sensor_type": {"enum": ["thermocouple", "rtd", "pyrometer", "other"]},
                "emissivity_treatment": {"type": "string"}}}},
        },
        "a3_rules": "every temperature item declares a scope; C-1 items (scope 'cathode_c1') must carry the mandatory "
                    "thermocouple channel labelled cathode_tube_temperature; no non-pyrometer sensor carries an "
                    "emitter label; emitter_temperature only from a calibrated pyrometer with a recorded emissivity "
                    "treatment; C-1 items without a pyrometer carry emitter_temperature_status 'unmeasured' "
                    "(capability_analysis.record_item_errors)",
    }


# ----------------------------------------------------------------------------------------------------------------------
# metrology specification (owner addendum A3 metrology_lab)
# ----------------------------------------------------------------------------------------------------------------------
E2_NOMINALS = ("1 mg", "10 mg", "100 mg", "1 g", "10 g", "100 g")
# OIML R 111-1:2004 Table 1, class E2, +/- delta_m in mg (read 2026-09-27; verify against Amendment 2025)
E2_MPE_MG = {"1 mg": 0.006, "10 mg": 0.008, "100 mg": 0.016, "1 g": 0.03, "10 g": 0.06, "100 g": 0.16}


def metrology_spec(ins: dict, a3: dict) -> dict:
    oiml = "OIML R 111-1:2004 Table 1 (class E2, +/- delta_m) - REF-OIML-R111-1; normative requirement quoted, not a " \
           "measurement"
    e2 = {}
    for nom in E2_NOMINALS:
        mpe = E2_MPE_MG[nom]
        e2[nom] = {"mpe": q(mpe, "mg", "assumed", oiml),
                   "U_max_k2": q(mpe / 3.0, "mg (k = 2)", "model-derived",
                                 _src("metrology_spec(): OIML R 111-1 5.2 U <= delta_m / 3 applied to Table 1"))}
    I = {i["id"]: i for i in ins["instruments"]}
    return {
        "schema": "abep_metrology_measurement_spec_v1",
        "id": "metrology_measurement_spec_v1",
        "status": "DRAFT_PENDING_OWNER",
        "follow_on": "fo_capability_demo_prep",
        "trigger": "T_PIVOT_CAPABILITY_DEMO_PREP",
        "authority": {"file": A3_REL, "sha256": PINNED[A3_REL], "decision": "metrology_lab",
                      "owner_text": a3["decisions"]["metrology_lab"]},
        "generated_by": SCRIPT_REL,
        "companion_document": "docs/experiments/instrumentation/metrology_spec/METROLOGY_MEASUREMENT_SPEC.md",
        "not_a_procurement": "No laboratory is named, searched or contacted. This specification is issued first; a lab "
                             "satisfying it is procured afterwards (A3). Nothing here is a measurement.",
        "serves": {"instruments": ["INS-19", "INS-20"], "procedures": ["INS-P-01", "INS-P-02", "INS-P-03",
                                                                      "INS-P-04", "INS-P-05"],
                   "instrumentation_definition": INS_REL},
        "milestones": {
            "supports": ["C"],
            "C": {"delivers": "the measurement requirements that make witness-coupon and part metrology usable as "
                              "exposure / erosion / life evidence (thermal_life measured_hardware records, INS-P-10)",
                  "needs_next": ["owner approval of this specification", "procurement of a lab whose accredited scope "
                                 "covers every measurand here", "the pre-S1 control-coupon repeatability trial "
                                 "(INS-19, AOL-PM-02) that sets the detection limits"]},
            "A": "not required for conditional selection; S1a engineering checkout does not depend on it",
            "B": "not affected (no Hall-transport observable)",
        },
        "general_requirements": [
            {"id": "MS-G-01", "requirement": "ISO/IEC 17025 accreditation with the SPECIFIC measurement (measurand, "
             "method, range and calibration and measurement capability) explicitly inside the accredited scope; in "
             "India normally an appropriate NABL-accredited scope (A3; REF-ISO17025, REF-NABL)",
             "verification": "copy of the current scope document and accreditation certificate; the scope lines "
                             "that cover each MS-M item are cited in the offer"},
            {"id": "MS-G-02", "requirement": "SI traceability of every result through an unbroken calibration chain; "
             "certificates of the reference standards used (masses, surface standards, reference foils, length "
             "standards) supplied with the report",
             "verification": "certificate numbers and validity dates in every report"},
            {"id": "MS-G-03", "requirement": "uncertainty evaluated per the GUM (REF-GUM2008): Type A and Type B "
             "components listed; expanded uncertainty with its coverage factor k and coverage probability; planning "
             "k = 2 (A3); where effective degrees of freedom are low, the evaluated k and nu_eff are stated "
             "(REF-GUM2008 G.4.1; for masses also REF-OIML-R111-1 C.6.5.1)",
             "verification": "uncertainty budget attached to each report"},
            {"id": "MS-G-04", "requirement": "raw data (every individual reading, instrument settings, environment "
             "log) delivered in machine-readable form with the report; Vyovrinda may publish them",
             "verification": "data files and their checksums listed in the report"},
            {"id": "MS-G-05", "requirement": "blind coded sample ids only (INS-P-01); the lab never receives "
             "configuration, arm or exposure information",
             "verification": "custody record"},
            {"id": "MS-G-06", "requirement": "the same instrument, method and (coded) operator for baseline and "
             "post-test measurements of an item (INS-P-02, INS-20)",
             "verification": "instrument serial and operator code in each report"},
            {"id": "MS-G-07", "requirement": "no subcontracting of a measurement outside the lab's own accredited "
             "scope without written agreement; a subcontracted measurement must itself satisfy MS-G-01",
             "verification": "declaration in the offer"},
            {"id": "MS-G-08", "requirement": "proficiency-testing or interlaboratory-comparison evidence for each "
             "measurand where the accreditation body requires it",
             "verification": "latest results for the relevant scope lines (verify the accreditation body's policy)"},
        ],
        "measurands": [
            {"id": "MS-M-01", "measurand": "mass of witness coupons, controls and parts (anode, wall rings, C-1 "
             "keeper) at baseline and after each removal (INS-19)",
             "method": "analytical / micro-balance weighing under the dehydrated protocol INS-P-03 (vacuum "
                       "desiccation for a fixed time, repeated readings averaged, room temperature and humidity "
                       "logged, identical pre and post); lab-stored control coupon weighed every session",
             "reference_standards": "SI-traceable balance calibration with OIML class E2 or better certified "
                                    "reference masses where appropriate, OIML R 111 certificates and traceability "
                                    "(A3; REF-OIML-R111-1)",
             "planning_values": {"e2_table_subset": e2,
                                 "verify": "E2 MPE values from OIML R 111-1:2004 Table 1; Amendment 2025 not read - "
                                           "verify against the current edition before procurement",
                                 "note": "which nominal values apply depends on the coupon and part masses (TBD - "
                                         "W3 coupon and part design); the reference-mass U is a small part of the "
                                         "weighing uncertainty, the detection limit comes from the control-coupon "
                                         "repeatability"},
             "required_uncertainty": tbd("detection limit set from the demonstrated control-coupon repeatability "
                                         "before S1 (INS-19; AOL-PM-02); no admitted source gives the expected N/O "
                                         "mass change of the H-1 grades", "metrology lab + S1"),
             "range": tbd("coupon and part masses (W3)", "fo_hardware_definition"),
             "report": "mean, SD and N of readings per session, desiccation parameters, environment, reference-mass "
                       "certificate ids, buoyancy treatment, U with k"},
            {"id": "MS-M-02", "measurand": "surface profile / areal topography against the W3 fiducials (HW-H1-11); "
             "C-1 keeper-face profile (INS-20)",
             "method": "stylus or optical profilometry, same instrument pre and post",
             "reference_standards": "calibration / verification with traceable surface standards consistent with "
                                    "ISO 25178-700 (A3; REF-ISO25178-700: noise, flatness deviation, amplification, "
                                    "linearity deviation, x-y mapping deviations)",
             "required_uncertainty": tbd("erosion depth to be resolved - no admitted source gives it for the H-1 "
                                         "wall grade in N/O (AO register v2); report as detection limits",
                                         "metrology lab"),
             "range": tbd("feature sizes and profile lengths (W3)", "fo_hardware_definition"),
             "report": "verification results of the metrological characteristics at the time of measurement, "
                       "filter settings, fiducial registration method and its uncertainty"},
            {"id": "MS-M-03", "measurand": "morphology and elemental composition of deposits / surfaces by SEM/EDS "
             "(INS-20, INS-P-04)",
             "method": "quantitative EDS by a documented method consistent with ASTM E1508 (A3; REF-ASTM-E1508), "
                       "standards-based or standardless stated; SEM magnification calibration recorded",
             "limitation": "ASTM E1508's routine applicability (as summarised in the search result, verify) is "
                           "elements >= Na at >= tenths of a weight percent: N, O, B and C quantification (BN, "
                           "oxides, nitrides) needs the lab to state its light-element method and uncertainty, or it "
                           "is reported semi-quantitatively",
             "required_uncertainty": tbd("per element: lab's documented method uncertainty", "metrology lab"),
             "report": "beam energy, detector, standards used, matrix-correction method, per-element result with "
                       "uncertainty or a 'semi-quantitative' label"},
            {"id": "MS-M-04", "measurand": "surface chemical state and depth profile by XPS (INS-20)",
             "method": "XPS with sealed dry transfer (INS-P-04); energy-scale calibration per ISO 15472 or an "
                       "equivalent traceable procedure (A3; REF-ISO15472: Cu 2p3/2 and Au 4f7/2 reference peaks, "
                       "linearity check, expanded uncertainty at 95 %)",
             "limitation": "ISO 15472 is not applicable to instruments without a sputter-cleaning ion gun, with "
                           "resolution worse than 1.5 eV or requiring tolerance limits of +/-0.03 eV or less "
                           "(REF-ISO15472 scope) - the lab states which case applies",
             "required_uncertainty": tbd("binding-energy scale U from the lab's ISO 15472 calibration; "
                                         "quantification method uncertainty", "metrology lab"),
             "report": "date of the last energy-scale calibration and its U, charge-referencing method, sputter "
                       "conditions for depth profiles, custody record"},
            {"id": "MS-M-05", "measurand": "C-1 orifice diameter and pole-face inspection photographs (INS-20, "
             "INS-P-05, AOL-PM-08)",
             "method": "calibrated optical dimensional measurement; photographs under fixed lighting",
             "reference_standards": "traceable length standard (stage micrometer or equivalent) - standard TBD "
                                    "(A3 names none for this measurand; verify with the lab's accredited scope)",
             "required_uncertainty": tbd("orifice-diameter resolution needed by the C-1 life assessment (W3 / "
                                         "lane 15)", "fo_hardware_definition"),
             "report": "method, magnification calibration, U with k"},
        ],
        "sample_handling": [
            "coded ids and register (INS-P-01); baseline before first ignition for every serialized item (INS-P-02)",
            "dehydrated mass protocol parameters (desiccation time, pressure, number of readings): TBD - set with the "
            "lab in a pre-S1 repeatability trial (INS-P-03); no value is assumed here",
            "sealed dry transfer containers and custody record for XPS / SEM samples (INS-P-04); container "
            "specification TBD with the lab",
        ],
        "lab_selection_checklist": [
            "every MS-M measurand covered by the accredited scope (MS-G-01), including the range and CMC once the "
            "TBD ranges are fixed",
            "reference-standard classes as specified (E2 or better masses; ISO 25178-700 surface standards; ISO 15472 "
            "reference foils or equivalent traceable procedure)",
            "uncertainty budgets with k and nu_eff (MS-G-03); raw data release (MS-G-04)",
            "blind handling, same instrument/operator pre and post (MS-G-05, MS-G-06)",
            "light-element EDS method stated (MS-M-03 limitation)",
        ],
        "references": [r for r in REFERENCES if r["id"] in ("REF-ISO17025", "REF-NABL", "REF-OIML-R111-1",
                                                           "REF-ISO25178-700", "REF-ASTM-E1508", "REF-ISO15472",
                                                           "REF-GUM2008")],
        "ins_calibration_text": {k: I[k]["calibration"] for k in ("INS-19", "INS-20")},
        "compliance": [
            "no laboratory named, searched or contacted; no supplier contact",
            "standard values quoted only from documents actually read (OIML R 111-1:2004); others cited by scope / "
            "metadata with access stated and 'verify' where content was not read",
            "no measured value is claimed; every requirement without a source is TBD with what it requires",
        ],
    }


# ----------------------------------------------------------------------------------------------------------------------
# document
# ----------------------------------------------------------------------------------------------------------------------
def build() -> dict:
    pins = verify_inputs()
    ins, s1, l25, feed, a3 = (_load(INS_REL), _load(S1_REL), _load(L25_REL), _load(FEED_REL), _load(A3_REL))
    t25 = lane25_targets(ins)
    counts = lane25_s1_counts(l25)
    mfc = mfc_range(feed, ins)
    demos = demonstrations(t25, counts, mfc, ins)
    s1a_c = s1a_procedure_candidates(demos, _load(S1A_REL))
    doc = {
        "schema": "abep_capability_demo_prep_v1",
        "id": "capability_demo_prep_v1",
        "follow_on": "fo_capability_demo_prep",
        "trigger": "T_PIVOT_CAPABILITY_DEMO_PREP",
        "status": "DRAFT_PENDING_OWNER",
        "what": "preparation of the actual-hardware capability demonstration (owner addendum A3 "
                "W4_capability_demonstration_prep): procedures, planning values, pass/fail analysis and the record "
                "format for the S1-C4 measured-capability artifact and the S1a engineering path",
        "not_a_demonstration": "No calibration has been performed. Nothing here demonstrates a capability or "
                               "satisfies S1-C4; a design analysis is never a demonstration (S1-C4 'why'). Planning "
                               "values are PROPOSED; acceptance targets are copied from the instrumentation "
                               "definition (lane 25 model-derived targets, W4 PROPOSED thresholds).",
        "owner_decisions": [{"file": r, "sha256": PINNED[r]} for r in (OD_REL, A1_REL, A2_REL, A3_REL)],
        "a3_rules_carried": {
            "cathode_temperature": a3["decisions"]["cathode_temperature"],
            "ins_p12_coverage_factor": a3["decisions"]["ins_p12_coverage_factor"],
            "near_cathode_rga": a3["decisions"]["near_cathode_rga"] + " (not one of the seven demonstrations here; "
                                "the uncalibrated RGA is qualitative S1a engineering data only)",
            "instrumentation_version": "the instrumentation definition stays v1-r2; this lane adds files beside it "
                                       "and changes none of its ids, semantics or acceptance rules",
            "metrology_lab": "docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json",
        },
        "generated_by": SCRIPT_REL,
        "analysis_module": ANALYSIS_REL,
        "record_schema": "docs/experiments/capability_demo/capability_record_item_v1.schema.json",
        "companion_document": "docs/experiments/capability_demo/CAPABILITY_DEMO_PREP.md",
        "inputs": [{"path": k, "sha256": v} for k, v in pins.items()],
        "architectures": list(ARCHS),
        "compliance": [
            "no Hall transport closure, screening candidate or withdrawn number is used; nothing here predicts "
            "thruster performance",
            "no architecture is preferred or eliminated; the demonstrations are identical for hall_only, rf_hall and "
            "ecr_hall except the source channels that exist only in rf_hall / ecr_hall",
            "P5 calibration nuisance is never an axis or design variable here",
            "no supplier, laboratory or person contacted; equipment is generic with standards cited",
            "every number carries unit, evidence class and source; non-RFP thresholds are PROPOSED; missing inputs "
            "raise",
            "no file of another lane is modified; the instrumentation definition stays v1-r2",
        ],
        "milestones": {
            "supports": ["A"],
            "A": {"conditional": "this lane alone does NOT satisfy S1-C4: pressure and species_divergence are "
                                 "uncovered and stability_oscillations is covered only for the time base (CD-06). "
                                 "The contribution to A holds only if W4 adds those demonstrations or the owner "
                                 "reduces the S1-C4 category set",
                  "delivers": "the ready-to-run procedures and the frozen-analysis candidate that turn delivered "
                              "instruments into the S1-C4 measured-capability record (and the calibration-plan "
                              "candidates for S1-C5), on the path LOCK-1 -> S1 -> LOCK-2 that conditional selection "
                              "rests on",
                  "needs_next": ["owner decisions on the CD-P-* thresholds and the calibration-plan freeze (S1-C5)",
                                 "delivered instruments, facility (S1-C7) and H-1/C-1 configuration (S1-C2)",
                                 "W1 registered test points and W3 ranges for every TBD",
                                 "execution of CD-01..CD-07 and the owner's acceptance of the record (S1-C4)",
                                 "pressure and species/divergence demonstrations (uncovered categories) or an owner "
                                 "reduction of the S1-C4 category set"]},
            "B": {"delivers": "only instrument capability for held-out observables (B(z), I_d(t) time base)",
                  "needs_next": ["W5 pre-registration of the VO-* tolerances", "an admitted Hall closure (credible "
                                 "set empty; gate 3 FAIL)"]},
            "C": {"delivers": "the metrology measurement specification (A3) that life / erosion evidence needs",
                  "needs_next": ["lab procurement against the specification; flight-representative power chains; "
                                 "integrated mass/thermal/life closure"]},
        },
        "proposed_thresholds": proposed_thresholds(),
        "decided_inputs": {
            "k_planning": q(K_PLANNING, "-", "assumed", f"{A3_REL}: decisions.ins_p12_coverage_factor (owner, "
                            "DECIDED: planning k = 2)"),
            "coverage_probability_of_k2": q(A.P_K2, "-", "model-derived",
                                            f"{ANALYSIS_REL}: P_K2 = 2 Phi(2) - 1 (normal distribution)"),
        },
        "lane25_and_w4_targets": t25,
        "lane25_s1_counts": counts,
        "planning_tables": {
            "sigma_upper_bound_factor": chi2_factor_table(),
            "coverage_factor_by_nu_eff": coverage_table(),
            "low_dof_threshold": low_dof_threshold(),
            "phase_error": phase_error_table(),
        },
        "demonstrations": demos,
        "s1_contract": s1_contract(s1, demos),
        "calibration_plan_candidates": calibration_plan_candidates(demos),
        "s1a_calibration_procedure_candidates": s1a_c,
        "s1a_path": {
            "gate": "fo_s1a_engineering_gate (separate lane; A3 S1a_engineering_gate): 'can we safely and usefully "
                    "begin non-score-bearing engineering qualification?'; condition S1A-C4 (" + S1A_REL + ", pinned)",
            "what_this_gives_it": "candidate S1a calibration procedures keyed to S1A-C4 (categories thrust_stand, "
                                  "power_channels, mass_flow_controllers, magnetic_field_Bz, daq_time_base, "
                                  "temperature_channels), each with procedure_id and an S1A-FW s1a_data_class, the "
                                  "temperature procedures with cathode_temperature_labelling "
                                  "(s1a_calibration_procedure_candidates; the same list in the gate-artifact shape in "
                                  "s1a_calibration_procedures_candidate_v1.json). They are CANDIDATES: the gate is "
                                  "satisfied only by the owner-frozen artifact, which also needs the frozen S1A-FW "
                                  "firewall. The S1-C4 / S1-C5 list (calibration_plan_candidates) is a different "
                                  "category set and is kept separately",
            "leak_rule": "no held-out H-1 physics output may leak into W5 (A3; S1A-FW): no S1a procedure includes an "
                         "H-1 anode discharge; the MFC calibration at registered points (REG-FEED) and the B(z) maps "
                         "(REG-BZ) are custody-held registration inputs released only after LOCK-H1; allowed-class "
                         "records carry calibration, noise, drift, repeatability, reinstallation and channel "
                         "performance data only, never used to tune a Hall closure",
        },
        "references": REFERENCES,
        "tbd_register": [
            {"what": "force-standard, DC-standard and RF/microwave-standard traceability classes",
             "requires": "owner (INS-01 / INS-02 open decision)"},
            {"what": "thrust range, module masses on the stand, coil operating currents", "requires": "W3 / LOCK-1"},
            {"what": "registered flows per MFC range, knee-scan resolution, T_feed / P_feed tolerances",
             "requires": "W1 feed-state closure / LOCK-1"},
            {"what": "dwell (hold time) for sustained >= 12 mN and zero-drift allowance", "requires": "owner"},
            {"what": "B(z) tolerance", "requires": "W5 pre-registration"},
            {"what": "skew allowance and I_d band", "requires": "S1 I_d spectrum"},
            {"what": "temperature requirements (T-SETTLE, life resolution, coil margin)",
             "requires": "S1, W3, magnet/coil lane"},
            {"what": "pressure and species/divergence demonstrations", "requires": "W4 scope extension or owner "
                                                                                  "reduction of S1-C4 categories"},
        ],
        "open_owner_decisions": [
            "approve, change or reject CD-P-* planning thresholds",
            "freeze the calibration plan (S1-C5) from the calibration_plan_candidates",
            "freeze the S1a calibration procedures (S1A-C4) from s1a_calibration_procedures_candidate_v1.json after "
            "the S1A-FW firewall is frozen; confirm the data-class split (REG-FEED / REG-BZ custody-held) and whether "
            "installation reproducibility (S1A-P-TS-03 / S1A-P-PC-03) stays in S1a",
            "S1-C4 category set: add pressure and species/divergence demonstrations, or reduce the set",
            "B(z) approach protocol and the isothermal thermocouple cross-check (both PROPOSED)",
            "approve the metrology specification before procurement",
        ],
    }
    validate(doc)
    return doc


# ----------------------------------------------------------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------------------------------------------------------
_STRUCTURAL_NUM_KEYS = ()


def numeric_leaf_errors(obj, path: str = "$", schema_doc: bool = False) -> list:
    """Every number must be the 'value' of a quantity dict carrying unit, evidence_class and source."""
    errs = []
    if isinstance(obj, dict):
        is_q = "value" in obj and isinstance(obj.get("value"), (int, float)) and not isinstance(obj.get("value"), bool)
        if is_q:
            if not (isinstance(obj.get("unit"), str) and obj["unit"] and isinstance(obj.get("source"), str)
                    and obj["source"] and obj.get("evidence_class") in EVIDENCE_CLASSES):
                errs.append(f"{path}: quantity without unit / source / evidence class")
        for k, v in obj.items():
            if is_q and k == "value":
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                errs.append(f"{path}.{k}: bare number {v!r}")
            else:
                errs += numeric_leaf_errors(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                errs.append(f"{path}[{i}]: bare number {v!r}")
            else:
                errs += numeric_leaf_errors(v, f"{path}[{i}]")
    return errs


def validate(doc: dict) -> None:
    errs = numeric_leaf_errors(doc)
    if errs:
        raise ValueError("number discipline: " + "; ".join(errs[:10]))
    if "DEMONSTRATED" == doc.get("status"):
        raise ValueError("this preparation never claims a demonstration")
    for t in doc["proposed_thresholds"]:
        if t.get("status") != "PROPOSED":
            raise ValueError(f"{t['id']} must be PROPOSED")


# ----------------------------------------------------------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------------------------------------------------------
def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _qs(d) -> str:
    if isinstance(d, dict) and "value" in d:
        v = d["value"]
        if v == "TBD":
            return f"TBD - requires {d.get('tbd_requires', '?')}"
        st = f", {d['status']}" if d.get("status") else ""
        return f"{v} {d.get('unit', '')} ({d.get('evidence_class', '')}{st})"
    return str(d)


def _table_rows(tab: dict) -> list:
    return [f"| {k} | {_qs(v)} |" for k, v in tab.items() if isinstance(v, dict)]


def render_md(doc: dict) -> str:
    L = [f"# Capability demonstration preparation (W4, {doc['follow_on']})", "",
         f"Status: **{doc['status']}**. Generated by `{doc['generated_by']}` from sha256-pinned inputs; "
         f"JSON: `docs/experiments/capability_demo/capability_demo_prep_v1.json`; analysis: `{doc['analysis_module']}`; "
         f"record schema: `{doc['record_schema']}`.", "",
         f"> {doc['not_a_demonstration']}", "",
         "## Milestones", ""]
    ms = doc["milestones"]
    L.append(f"Supports **{', '.join(ms['supports'])}**.")
    for k in ("A", "B", "C"):
        L.append(f"- **{k}**: {ms[k]['delivers']}. Next: " + "; ".join(ms[k]["needs_next"]) + ".")
        if "conditional" in ms[k]:
            L.append(f"  - Conditional: {ms[k]['conditional']}.")
    L += ["", "## Owner addendum A3 rules carried", ""]
    for k, v in doc["a3_rules_carried"].items():
        L.append(f"- **{k}**: {v}")
    L += ["", "## PROPOSED planning thresholds (owner decides)", "", "| id | value | rationale |", "|---|---|---|"]
    for t in doc["proposed_thresholds"]:
        L.append(f"| {t['id']} | {t['value']} {t['unit']} | {t['rationale']} |")
    L += ["", f"Decided: planning k = {doc['decided_inputs']['k_planning']['value']} (A3); coverage probability of "
          f"k = 2 for a normal distribution = {doc['decided_inputs']['coverage_probability_of_k2']['value']}.", "",
          "## Targets used for pass/fail (copied from the instrumentation definition)", ""]
    t = doc["lane25_and_w4_targets"]
    for key in ("u_T_max", "u_P_max", "u_inst_max", "sigma_T_at_12mN", "sigma_Pbus_at_1500W", "u_src_max_by_f_src"):
        L += [f"**{key}**", "", "| key | value |", "|---|---|"] + _table_rows(t[key]) + [""]
    for key in ("I-U-ABS-T", "I-U-ABS-P", "I-U-ID-FLOOR"):
        L.append(f"- {key}: {_qs(t[key])}")
    L += ["", "Lane-25 S1 counts: " + "; ".join(f"{k} = {_qs(v)}" for k, v in doc["lane25_s1_counts"].items()), "",
          "## Planning tables (model-derived)", ""]
    pt = doc["planning_tables"]
    L += ["**One-sided upper bound of sigma / sample SD** (CD-P-CONF)", "", "| nu | factor |", "|---|---|"]
    L += _table_rows(pt["sigma_upper_bound_factor"]) + [""]
    L += ["**Evaluated coverage factor at the k = 2 coverage probability** (A3)", "", "| nu_eff | k |", "|---|---|"]
    L += [f"| {k} | {v['value']} (replaces k = 2: {v['replaces_k2']}) |" for k, v in
          pt["coverage_factor_by_nu_eff"].items()] + [""]
    L += [f"k = 2 is used from nu_eff >= {pt['low_dof_threshold']['value']} (CD-P-LOWDOF).", "",
          "**Skew for 1 degree phase error** (" + pt["phase_error"]["note"] + ")", "", "| f | skew |", "|---|---|"]
    L += _table_rows(pt["phase_error"]) + [""]
    L += ["## Demonstrations", ""]
    for d in doc["demonstrations"]:
        L += [f"### {d['id']} - {d['title']}", "",
              f"Instruments: {', '.join(d['instruments'])}. S1-C4 categories: {', '.join(d['s1c4_categories'])}. "
              f"Stage: {d['stage']}.", "", f"Purpose: {d['purpose']}.", ""]
        if "range" in d:
            r = d["range"]
            L += [f"Range basis: {r['basis']}", ""]
            for k in ("mdot_min", "mdot_max", "sccm_N2_min", "sccm_N2_max", "sccm_O2_max", "turndown_ratio",
                      "single_device_u_at_min", "single_device_zero_shift_at_min"):
                L.append(f"- {k}: {_qs(r[k])}")
            for k, v in r["ranges_needed"].items():
                L.append(f"- ranges needed ({k}): {_qs(v)}")
            L += [f"- sccm basis: {r['sccm_basis']}"]
            L += [f"- Xe cathode flow: {_qs(r['xe_cathode_flow'])}", "", r["reading"], ""]
        if "channels" in d:
            L += [f"Boundary: {d['boundary']}", "", "| component | architectures | lab status | demonstration |",
                  "|---|---|---|---|"]
            for c in d["channels"]:
                L.append(f"| {c['component']} | {', '.join(c['architectures'])} | {c['lab_status']} | "
                         f"{c['demonstration']} |")
            L.append("")
        L += ["Equipment (generic):", ""] + [f"- {e}" for e in d["equipment"]] + ["", "Procedure:", ""]
        L += [f"{i + 1}. {s}" for i, s in enumerate(d["procedure"])] + ["", "Repeats:", ""]
        L += [f"- {k}: {_qs(v)}" for k, v in d["repeats"].items()] + ["", "Analysis:", ""]
        L += [f"- {k}: {v}" for k, v in d["analysis"].items()] + ["", f"Acceptance: {d['acceptance']['rule']}", ""]
        rec = d["record"]
        L += [f"Record item: category `{rec['category']}`, instrument `{rec['instrument_id']}`, evidence_class "
              f"`measured`; demonstrated uncertainty = {rec['demonstrated_uncertainty']['meaning']}. Extra fields: "
              + ", ".join(rec["extra_fields"]) + ".", "", "Failure means:", ""]
        L += [f"- {f}" for f in d["failure_meaning"]] + [""]
    s = doc["s1_contract"]
    L += ["## S1-C4 record contract", "",
          f"Artifact (written later by W4, never by this lane): `{s['artifact_path']}`; raw data under "
          f"`{s['raw_data_prefix']}`. Gate: `{s['gate_file']}`. {s['produced_by']}.", "",
          "| category | covered by |", "|---|---|"]
    L += [f"| {k} | {', '.join(v) if v else '**not covered**'} |" for k, v in s["coverage_by_this_preparation"].items()]
    L += [""] + [f"- **{k}** uncovered: {v}" for k, v in s["uncovered_categories"].items()]
    L += [f"- **{k}** partial: {v}" for k, v in s["partial_categories"].items()]
    L += ["", f"Calibration plan: {s['calibration_plan_link']}.", "", "## S1a path", ""]
    L += [f"- {k}: {v}" for k, v in doc["s1a_path"].items()]
    sc = doc["s1a_calibration_procedure_candidates"]
    L += ["", "### S1a calibration-procedure candidates (S1A-C4; PROPOSED, owner freezes)", "",
          f"Gate: `{sc['gate_file']}` ({sc['gate_condition']}); frozen artifact path `{sc['frozen_artifact_path']}`. "
          f"{sc['this_lane_writes']}.", "",
          "| procedure_id | S1A-C4 category | CD item | s1a_data_class | data scope |", "|---|---|---|---|---|"]
    L += [f"| {x['procedure_id']} | {x['category']} | {x['demonstration_id']} | {x['s1a_data_class']} | "
          f"{x['data_scope']} |" for x in sc["procedures"]]
    L += ["", f"Firewall class ids: {sc['firewall_class_ids_basis']}.", "",
          f"Cathode-temperature labelling (temperature_channels procedures): {CATHODE_TEMPERATURE_LABELLING}.", "",
          "Rule check of the procedures list against the S1A-C4 rules (owner-only fields excluded): "
          + "; ".join(f"{c['rule'].split(' (')[0]} {c['result']}" for c in sc["rule_check_on_procedures"]) + ".", "",
          "Not in S1a: " + "; ".join(sc["not_in_s1a"]) + "."]
    L += ["", "## TBD register", ""] + [f"- {x['what']}: requires {x['requires']}" for x in doc["tbd_register"]]
    L += ["", "## Open owner decisions", ""] + [f"- {x}" for x in doc["open_owner_decisions"]]
    L += ["", "## Compliance", ""] + [f"- {x}" for x in doc["compliance"]]
    L += ["", "## References", ""] + [f"- **{r['id']}**: {r['citation']}" + (f" <{r['url']}>" if r["url"] else "")
                                      + f". Access: {r['access']}." for r in doc["references"]]
    L += ["", "## Inputs (sha256)", ""] + [f"- `{i['path']}` {i['sha256']}" for i in doc["inputs"]]
    return "\n".join(L) + "\n"


def render_spec_md(spec: dict) -> str:
    L = ["# Metrology measurement specification (W4, owner addendum A3)", "",
         f"Status: **{spec['status']}**. Generated by `{spec['generated_by']}`; JSON: "
         "`docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json`.", "",
         f"> {spec['not_a_procurement']}", "", f"Authority: `{spec['authority']['file']}` "
         f"(sha256 {spec['authority']['sha256']}), decision `metrology_lab`:", "",
         f"> {spec['authority']['owner_text']}", "", "## Milestones", ""]
    m = spec["milestones"]
    L += [f"- **C**: {m['C']['delivers']}. Next: " + "; ".join(m["C"]["needs_next"]) + ".",
          f"- **A**: {m['A']}.", f"- **B**: {m['B']}.", "", "## General requirements", ""]
    L += [f"- **{g['id']}**: {g['requirement']}. Verification: {g['verification']}." for g in
          spec["general_requirements"]]
    L += ["", "## Measurands", ""]
    for x in spec["measurands"]:
        L += [f"### {x['id']} - {x['measurand']}", "", f"- Method: {x['method']}"]
        if "reference_standards" in x:
            L.append(f"- Reference standards: {x['reference_standards']}")
        if "limitation" in x:
            L.append(f"- Limitation: {x['limitation']}")
        L.append(f"- Required uncertainty: {_qs(x['required_uncertainty'])}")
        if "range" in x:
            L.append(f"- Range: {_qs(x['range'])}")
        L.append(f"- Report: {x['report']}")
        if "planning_values" in x:
            L += ["", "E2 MPE values quoted from OIML R 111-1:2004 Table 1 (verify: Amendment 2025 not read; confirm "
                  "against the current edition before procurement).", "",
                  "| nominal | E2 MPE (verify) | U max (k = 2) |", "|---|---|---|"]
            for nom, v in x["planning_values"]["e2_table_subset"].items():
                L.append(f"| {nom} | +/- {v['mpe']['value']} mg | {v['U_max_k2']['value']} mg |")
            L += ["", x["planning_values"]["note"] + "."]
        L.append("")
    L += ["## Sample handling", ""] + [f"- {s}" for s in spec["sample_handling"]]
    L += ["", "## Lab selection checklist", ""] + [f"- [ ] {s}" for s in spec["lab_selection_checklist"]]
    L += ["", "## Compliance", ""] + [f"- {s}" for s in spec["compliance"]]
    L += ["", "## References", ""] + [f"- **{r['id']}**: {r['citation']}" + (f" <{r['url']}>" if r["url"] else "")
                                      + f". Access: {r['access']}." for r in spec["references"]]
    return "\n".join(L) + "\n"


def build_all() -> dict:
    doc = build()
    spec = metrology_spec(_load(INS_REL), _load(A3_REL))
    errs = numeric_leaf_errors(spec)
    if errs:
        raise ValueError("number discipline (spec): " + "; ".join(errs[:10]))
    return {OUT_JSON: dumps(doc), OUT_MD: render_md(doc), OUT_SCHEMA: dumps(record_schema()),
            OUT_S1A: dumps(s1a_candidate_artifact(doc["s1a_calibration_procedure_candidates"])),
            OUT_SPEC_JSON: dumps(spec), OUT_SPEC_MD: render_spec_md(spec)}


def main(argv: list[str]) -> int:
    outs = build_all()
    if "--check" in argv:
        bad = [p for p, s in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        print("OK" if not bad else "DRIFT: " + ", ".join(str(p.relative_to(ROOT)) for p in bad))
        return 0 if not bad else 1
    for p, s in outs.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(s, encoding="utf-8")
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
