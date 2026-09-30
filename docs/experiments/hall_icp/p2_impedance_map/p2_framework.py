"""P2 ICP impedance-map FRAMEWORK (follow-on fo_a9_6_p2_framework_completion, trigger T_A9_6_P2_FRAMEWORK_COMPLETION;
owner directive A9.6 sec. 9 and 14, docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md).

Everything needed to ingest REAL P2 data later without further software work, on top of the verified record reducer
(p2_impedance_reducer.py, same directory):

  * Touchstone v1 reader / writer (.s1p / .s2p; option line, RI / MA / DB, 2-port order N11 N21 N12 N22) -
    REF-TOUCHSTONE11 pp. 3-6; spec defaults are never applied silently (allow_spec_defaults=True applies AND records);
  * S-parameter storage (p2_sparam_set_v1) and exact-frequency extraction of the calibration two-ports / one-ports
    (no interpolation);
  * one-port SOL (three-term) error terms from >= 3 known standards and their correction - REF-WALKER2023 Eq. (8) and
    the C / V / E matrix solution p. 4 (least squares for > 3 standards); REF-AN1287-3 p. 4;
  * directional coupler: power factors from coupling / cable loss / sensor calibration factor; worst-case reflection
    error and |Gamma| bounds from directivity, source match and tracking - REF-AN1287-3 p. 12 (Fig. 14);
  * V/I probe: complex gain from magnitude / phase calibration, closed-form calibration on a known load;
  * local-match settings: the logged positions of every record must equal the characterized tuning state (enforced
    in the reducer); ladder element voltages / currents for a declared match topology;
  * RF line / match loss: dissipated fraction of a two-port, at-power loss-model verification (normalized statistic
    with an explicitly supplied k; missing uncertainty -> NOT_EVALUATED);
  * plasma-state classification (reducer, A9.4 P2Q-05) and E/H transition detection on up / down sweeps (photodiode
    required; reflected power and antenna current as corroboration; criteria form TBD_OWNER P2Q-09 / P2Q-03, values
    TBD_AFTER_EVIDENCE - supplied by the caller, never defaulted);
  * uncertainty propagation: GUM law of propagation (REF-GUM2008 5.1.2 Eq. (10), 5.2.2 Eq. (13); multivariate
    REF-JCGM102 6.2.1.3 Eq. (3), complex quantities via real and imaginary parts, 6.4) and a seeded, deterministic
    Monte Carlo (REF-JCGM101 6.4.8.4 Cholesky sampling, 7.6 estimate, 7.7.2 coverage interval);
  * impedance-map storage (p2_impedance_map_v1) with a canonical writer / reader and a content sha256;
  * rating-derivation STRUCTURE for the RF components: every output TBD_AFTER_EVIDENCE until a complete MEASURED
    envelope exists and the owner inputs (ICPQ-10 heat-load bound, ICPQ-11 k_RF, P2Q-10 margins) are given;
    RF_COMPONENT_RATINGS stays TBD_AFTER_IMPEDANCE_MAP in every case.

Pure and deterministic, standard library only; no network access, no Julia; not wired into archengine; imports no
abep_sim module. Nothing here predicts an impedance, power, plasma state, thrust or rating.
"""
from __future__ import annotations

import cmath
import hashlib
import importlib.util
import json
import math
import random
from fractions import Fraction
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("p2_impedance_reducer_fw", str(_HERE / "p2_impedance_reducer.py"))
RED = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RED)

FRAMEWORK_ID = "p2_impedance_framework_v1"
SPARAM_SCHEMA_ID = "p2_sparam_set_v1"
MAP_SCHEMA_ID = "p2_impedance_map_v1"
TBD_EVIDENCE = "TBD_AFTER_EVIDENCE"
TBD_OWNER = "TBD_OWNER"
NOT_EVALUATED = "NOT_EVALUATED"
LOSS_INCONSISTENT = "LOSS_MODEL_INCONSISTENT"
RATING_STATUS = RED.RATING_STATUS                       # TBD_AFTER_IMPEDANCE_MAP (A9.2 a9_10_statuses)
PLANE_ORDER = ("RP-GEN", "RP-CPL", "RP-MIN", "RP-ANT")  # generator -> antenna; RP-VI joins RP-ANT by a fixture
FREQ_UNITS = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}
TS_PARAMETERS = ("S", "Y", "Z", "H", "G")
TS_FORMATS = ("RI", "MA", "DB")
TS_SPEC_DEFAULTS = {"unit": "GHZ", "parameter": "S", "format": "MA", "R": 50.0}   # REF-TOUCHSTONE11 pp. 4-5
TS_2PORT_ORDER = ("S11", "S21", "S12", "S22")           # REF-TOUCHSTONE11 p. 6: '21' data precedes '12' data
FREQ_MATCH_RTOL = 1e-12                                 # float-representation tolerance only; never interpolation
AMPLITUDE_CONVENTIONS = ("peak", "rms")
SENSOR_K_CONVENTIONS = ("indicated_over_incident",)
EH_FORMS = ("absolute_step", "k_times_uc")              # admissible criteria forms (P2Q-09 / HM-R06 open)
EH_CHANNELS = ("photodiode_V", "P_reflected_W", "I_ant_rms_A")
STEP_FRACTION_OF_U = 1e-3                               # numerical-derivative step = 1e-3 u(x_i) (not a physical value)
MC_COVERAGE_P_PERCENT = 95
TRANSITION_CLASSES = ("TRANSITION_CANDIDATE_CORROBORATED", "TRANSITION_CANDIDATE_OPTICAL_ONLY",
                      "UNCERTAIN_ELECTRICAL_ONLY", "UNCERTAIN_PHOTODIODE_INVALID")
MAP_POINT_FIELDS = ("record_id", "phase", "data_class", "evidence_tag", "calibration_set_id", "f_Hz", "Z0_ohm",
                    "factors", "match_state", "plasma_state_class", "sweep", "Z_antenna", "Z_antenna_primary_method",
                    "gamma_antenna_vs_Z0", "at_RP_CPL", "P_line_match_loss_W", "P_delivered_W", "loss_status",
                    "uncertainty")
MAP_HEADER_FIELDS = ("schema", "map_id", "data_class", "evidence_status", "evidence_tag", "p1_stable_region_ref",
                     "calibration_set_ids", "rating_status", "framework", "points", "excluded_records",
                     "content_sha256")
UNC_FIELDS = ("u_gamma_mag", "u_VSWR", "u_P_net_W", "u_P_delivered_W", "U_Z_antenna_ohm2", "method", "basis")
RATING_COMPONENTS = (
    ("RC-GEN-PFWD", "generator forward power", "P_forward_W_at_RP_CPL", "W", "P2Q-10"),
    ("RC-CPL-V", "directional coupler / sensors: peak RF voltage", "line_V_peak_max_V", "V", "P2Q-10"),
    ("RC-CPL-I", "directional coupler: peak RF current", "line_I_peak_max_A", "A", "P2Q-10"),
    ("RC-COAX-V", "50-ohm coax and connectors: peak RF voltage (RP-CPL -> RP-MIN)", "line_V_peak_max_V", "V", "P2Q-10"),
    ("RC-COAX-I", "50-ohm coax and connectors: peak RF current", "line_I_peak_max_A", "A", "P2Q-10"),
    ("RC-FT-V", "vacuum RF feedthrough: peak RF voltage (at RP-MIN)", "feedthrough_V_peak_max_V", "V", "P2Q-10"),
    ("RC-FT-I", "vacuum RF feedthrough: peak RF current (at RP-MIN)", "feedthrough_I_peak_max_A", "A", "P2Q-10"),
    ("RC-MATCH-EL", "local-match elements: peak voltage / current per element", "match_element_peaks", "V; A",
     "P2Q-10"),
    ("RC-ANT-V", "antenna circuit: rated RF voltage vs V_ant,peak (ICP-44)", "antenna_V_peak_max_V", "V", "ICPQ-11"),
    ("RC-HEAT", "total ICP module heat-load bound (ICP-43)", "P_forward_W_at_RP_CPL", "W", "ICPQ-10"),
)


class FrameworkError(ValueError):
    """Base class of every framework refusal."""


class TouchstoneError(FrameworkError):
    pass


class SParamError(FrameworkError):
    pass


class CalibrationSolveError(FrameworkError):
    pass


class CriteriaMissingError(FrameworkError):
    """A detection / acceptance criterion is not supplied: its form is an open owner question (TBD_OWNER) and its value
    is TBD_AFTER_EVIDENCE; nothing is defaulted."""


class UncertaintyMissingError(FrameworkError):
    pass


class MapFormatError(FrameworkError):
    pass


class RatingInputError(FrameworkError):
    pass


def _fin(x, what):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise FrameworkError(f"{what}: finite number required, got {x!r}")
    return float(x)


def _cxv(v, what):
    try:
        return RED.cx(v, what)
    except RED.RecordError as e:
        raise FrameworkError(str(e)) from None


def _c(z):
    return [z.real, z.imag]


def _r(x, n=9):
    return RED._r(x, n)


# ================================================================================================ Touchstone v1
def _parse_option(tokens, allow_spec_defaults, line_no):
    got = {}
    i = 0
    while i < len(tokens):
        t = tokens[i].upper()
        if t in FREQ_UNITS:
            key, val = "unit", t
        elif t in TS_PARAMETERS:
            key, val = "parameter", t
        elif t in TS_FORMATS:
            key, val = "format", t
        elif t == "R":
            if i + 1 >= len(tokens):
                raise TouchstoneError(f"line {line_no}: option 'R' without a value")
            try:
                val = float(tokens[i + 1])
            except ValueError:
                raise TouchstoneError(f"line {line_no}: reference resistance {tokens[i + 1]!r} is not a number") \
                    from None
            if not math.isfinite(val) or val <= 0:
                raise TouchstoneError(f"line {line_no}: reference resistance must be a positive number of ohms")
            key = "R"
            i += 1
        else:
            raise TouchstoneError(f"line {line_no}: unknown option-line token {tokens[i]!r}")
        if key in got:
            raise TouchstoneError(f"line {line_no}: option '{key}' given twice")
        got[key] = val
        i += 1
    defaults = []
    for k in ("unit", "parameter", "format", "R"):
        if k not in got:
            if not allow_spec_defaults:
                raise TouchstoneError(f"line {line_no}: option-line field '{k}' not stated; the Touchstone 1.1 default "
                                      f"({TS_SPEC_DEFAULTS[k]!r}) is not applied silently (pass "
                                      "allow_spec_defaults=True to apply and record it)")
            got[k] = TS_SPEC_DEFAULTS[k]
            defaults.append(k)
    return got, defaults


def _pair(a, b, fmt):
    if fmt == "RI":
        return complex(a, b)
    if fmt == "MA":
        if a < 0:
            raise TouchstoneError(f"negative magnitude {a} in MA format")
        return cmath.rect(a, math.radians(b))
    return cmath.rect(10 ** (a / 20.0), math.radians(b))            # DB: dB = 20 log10 |magnitude|


def parse_touchstone(text, n_ports, *, allow_spec_defaults=False, source=None):
    """Parse Touchstone 1.1 text of a 1- or 2-port S-parameter file (REF-TOUCHSTONE11). Returns a dict with the
    explicit option values, the defaults applied (empty unless allowed), Z0 and the points in Hz with complex
    S-parameters. Refuses: non-ASCII content, a missing or malformed option line, non-S parameters, wrong value
    counts, non-increasing frequencies, and any silent default."""
    if n_ports not in (1, 2):
        raise TouchstoneError("only 1-port (.s1p) and 2-port (.s2p) files are supported")
    if not isinstance(text, str):
        raise TouchstoneError("text must be a string")
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        raise TouchstoneError("non-ASCII content (Touchstone 1.1 general rule 2)") from None
    option, defaults, ignored = None, [], 0
    points, noise, last_f = [], [], None
    in_noise = False
    per_line = 3 if n_ports == 1 else 9
    for ln, raw in enumerate(text.splitlines(), 1):
        body = raw.split("!", 1)[0].strip()
        if not body:
            continue
        if body.startswith("#"):
            if option is None:
                option, defaults = _parse_option(body[1:].split(), allow_spec_defaults, ln)
            else:
                ignored += 1                                           # spec p. 4: later option lines are ignored
            continue
        if option is None:
            raise TouchstoneError(f"line {ln}: data before the option line (it must be the first non-comment line)")
        toks = body.split()
        try:
            vals = [float(t) for t in toks]
        except ValueError:
            raise TouchstoneError(f"line {ln}: non-numeric data {body!r}") from None
        if not all(math.isfinite(v) for v in vals):
            raise TouchstoneError(f"line {ln}: non-finite value")
        f_hz = vals[0] * FREQ_UNITS[option["unit"]]
        if n_ports == 2 and len(vals) == 5 and points and (in_noise or f_hz <= last_f):
            in_noise = True                                            # spec pp. 10-11: noise parameter block
            noise.append({"f_Hz": f_hz, "NFmin_dB": vals[1], "gamma_opt_mag": vals[2], "gamma_opt_deg": vals[3],
                          "rn_normalized": vals[4]})
            continue
        if in_noise:
            raise TouchstoneError(f"line {ln}: network data after the noise block")
        if len(vals) != per_line:
            raise TouchstoneError(f"line {ln}: {len(vals)} values, expected {per_line} for a {n_ports}-port data line")
        if last_f is not None and not f_hz > last_f:
            raise TouchstoneError(f"line {ln}: frequencies must increase (spec p. 6 rule 4)")
        last_f = f_hz
        pairs = [_pair(vals[1 + 2 * k], vals[2 + 2 * k], option["format"]) for k in range(n_ports ** 2)]
        pt = {"f_Hz": f_hz}
        for k, name in enumerate(("S11",) if n_ports == 1 else TS_2PORT_ORDER):
            pt[name] = pairs[k]
        points.append(pt)
    if option is None:
        raise TouchstoneError("no option line")
    if option["parameter"] != "S":
        raise TouchstoneError(f"parameter {option['parameter']!r}: this framework ingests S-parameters only")
    if not points:
        raise TouchstoneError("no network data")
    return {"n_ports": n_ports, "option": option, "defaults_applied": defaults, "Z0_ohm": option["R"],
            "points": points, "noise": noise, "ignored_option_lines": ignored, "source": source}


def read_touchstone(path, *, allow_spec_defaults=False):
    """Read an .s1p / .s2p file (port count from the extension, spec p. 3 rule 4) and record its sha256."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in (".s1p", ".s2p"):
        raise TouchstoneError(f"{p.name}: extension must be .s1p or .s2p")
    raw = p.read_bytes()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise TouchstoneError(f"{p.name}: non-ASCII content") from None
    out = parse_touchstone(text, 1 if ext == ".s1p" else 2, allow_spec_defaults=allow_spec_defaults, source=str(p))
    out["source_sha256"] = hashlib.sha256(raw).hexdigest()
    return out


def write_touchstone(n_ports, points, *, unit="HZ", fmt="RI", r_ohm, comment=None):
    """Touchstone 1.1 text (used for SYNTHETIC fixtures and exports). Every option field is written explicitly."""
    if n_ports not in (1, 2) or unit.upper() not in FREQ_UNITS or fmt.upper() not in TS_FORMATS:
        raise TouchstoneError("unsupported writer options")
    r = _fin(r_ohm, "r_ohm")
    lines = [f"! {comment}"] if comment else []
    lines.append(f"# {unit.upper()} S {fmt.upper()} R {r!r}")
    scale = FREQ_UNITS[unit.upper()]
    names = ("S11",) if n_ports == 1 else TS_2PORT_ORDER
    for pt in points:
        vals = [repr(pt["f_Hz"] / scale)]
        for n in names:
            z = complex(pt[n])
            if fmt.upper() == "RI":
                a, b = z.real, z.imag
            elif fmt.upper() == "MA":
                a, b = abs(z), math.degrees(cmath.phase(z))
            else:
                if z == 0:
                    raise TouchstoneError("DB format cannot encode an exact zero")
                a, b = 20 * math.log10(abs(z)), math.degrees(cmath.phase(z))
            vals += [repr(a), repr(b)]
        lines.append(" ".join(vals))
    return "\n".join(lines) + "\n"


# ================================================================================================ S-parameter storage
def sparam_set(parsed, *, set_id, from_plane, to_plane, cal_id, phase_calibrated, data_class, tuning_state_id=None,
               positions=None):
    """p2_sparam_set_v1 record of a parsed Touchstone file (JSON-able, complex as [re, im]). A 2-port set runs
    from_plane -> to_plane in generator -> antenna order; a 1-port set has to_plane None (the measured plane)."""
    if data_class not in RED.DATA_CLASSES:
        raise SParamError(f"data_class {data_class!r} not in {RED.DATA_CLASSES}")
    if not isinstance(phase_calibrated, bool):
        raise SParamError("phase_calibrated must be true or false")
    if from_plane not in PLANE_ORDER:
        raise SParamError(f"from_plane {from_plane!r} not in {PLANE_ORDER}")
    n = parsed["n_ports"]
    if n == 2:
        if to_plane not in PLANE_ORDER or PLANE_ORDER.index(to_plane) <= PLANE_ORDER.index(from_plane):
            raise SParamError(f"two-port planes {from_plane} -> {to_plane} not in generator -> antenna order")
    elif to_plane is not None:
        raise SParamError("a one-port set has to_plane None")
    if tuning_state_id is not None and (not isinstance(positions, dict) or not positions):
        raise SParamError("a tuning-state set must log the element positions it was characterized at")
    names = ("S11",) if n == 1 else TS_2PORT_ORDER
    return {"schema": SPARAM_SCHEMA_ID, "set_id": set_id, "n_ports": n, "Z0_ohm": parsed["Z0_ohm"],
            "from_plane": from_plane, "to_plane": to_plane, "cal_id": cal_id, "phase_calibrated": phase_calibrated,
            "data_class": data_class, "source_file": parsed.get("source"),
            "source_sha256": parsed.get("source_sha256"), "option": dict(parsed["option"]),
            "defaults_applied": list(parsed["defaults_applied"]), "tuning_state_id": tuning_state_id,
            "positions": dict(positions) if positions else None,
            "points": [dict({"f_Hz": p["f_Hz"]}, **{k: _c(complex(p[k])) for k in names}) for p in parsed["points"]]}


def _point_at(sset, f_hz):
    if not isinstance(sset, dict) or sset.get("schema") != SPARAM_SCHEMA_ID:
        raise SParamError("not a p2_sparam_set_v1 record")
    f = _fin(f_hz, "f_Hz")
    hits = [p for p in sset["points"] if abs(p["f_Hz"] - f) <= FREQ_MATCH_RTOL * f]
    if len(hits) != 1:
        raise SParamError(f"set {sset['set_id']!r} has no point at {f} Hz (no interpolation; measure at the drive "
                          "frequency)")
    return hits[0]


def two_port_entry(sset, f_hz, z0):
    """Calibration-set two-port entry (reducer contract) at exactly f_hz; Z0 must equal the file's reference R."""
    if sset.get("n_ports") != 2:
        raise SParamError("two_port_entry needs a 2-port set")
    if _fin(z0, "Z0") != sset["Z0_ohm"]:
        raise SParamError(f"set {sset['set_id']!r} is referenced to {sset['Z0_ohm']} ohm, not {z0} ohm "
                          "(renormalization is a separate declared step)")
    p = _point_at(sset, f_hz)
    e = {"from_plane": sset["from_plane"], "to_plane": sset["to_plane"], "cal_id": sset["cal_id"],
         "phase_calibrated": sset["phase_calibrated"], "sparam_set_id": sset["set_id"],
         "source_sha256": sset["source_sha256"]}
    e.update({k: list(p[k]) for k in ("S11", "S12", "S21", "S22")})
    if sset["tuning_state_id"] is not None:
        e["positions"] = dict(sset["positions"])
        e["tuning_state_id"] = sset["tuning_state_id"]
    return e


def one_port_gamma(sset, f_hz):
    if sset.get("n_ports") != 1:
        raise SParamError("one_port_gamma needs a 1-port set")
    return complex(*_point_at(sset, f_hz)["S11"])


def check_plane_chain(entries, start, end):
    """The two-port entries (in order) must join start -> end without gaps or overlaps (reference-plane audit)."""
    cur = start
    for e in entries:
        if e["from_plane"] != cur:
            raise RED.ReferencePlaneError(f"chain gap: expected a two-port from {cur}, got {e['from_plane']}")
        cur = e["to_plane"]
    if cur != end:
        raise RED.ReferencePlaneError(f"chain ends at {cur}, not {end}")
    return True


# ================================================================================================ one-port SOL
def _solve3(a, b):
    """Gaussian elimination with partial pivoting for a complex 3x3 system; refuses a near-singular matrix."""
    m = [list(a[i]) + [b[i]] for i in range(3)]
    scale = max(abs(x) for row in a for x in row) or 1.0
    for c in range(3):
        piv = max(range(c, 3), key=lambda r: abs(m[r][c]))
        if abs(m[piv][c]) <= 1e-12 * scale:
            raise CalibrationSolveError("calibration standards are not distinct enough (singular normal equations)")
        m[c], m[piv] = m[piv], m[c]
        for r in range(c + 1, 3):
            f = m[r][c] / m[c][c]
            for k in range(c, 4):
                m[r][k] -= f * m[c][k]
    x = [0j, 0j, 0j]
    for c in (2, 1, 0):
        x[c] = (m[c][3] - sum(m[c][k] * x[k] for k in range(c + 1, 3))) / m[c][c]
    return x


def sol_error_terms(standards):
    """Three-term one-port error model Gamma_m = e00 + e10e01 Gamma_a / (1 - e11 Gamma_a) (REF-WALKER2023 Eq. (8)) from
    >= 3 known standards: rows C_i = [Gamma_a,i, 1, Gamma_a,i Gamma_m,i], V_i = Gamma_m,i, E = (C^H C)^-1 C^H V,
    e00 = E2, e11 = E3, e10e01 = E1 + E2 E3 (REF-WALKER2023 p. 4). Each standard carries its actual reflection
    (data-based definition or a declared ideal) with a definition_source; nothing is assumed ideal silently."""
    if not isinstance(standards, list) or len(standards) < 3:
        raise CalibrationSolveError("at least three known standards are required (three complex unknowns)")
    rows, v = [], []
    for s in standards:
        for k in ("id", "gamma_actual", "gamma_measured", "definition_source"):
            if k not in s or s[k] in (None, ""):
                raise CalibrationSolveError(f"standard {s.get('id')!r} lacks {k}")
        ga = _cxv(s["gamma_actual"], f"{s['id']}.gamma_actual")
        gm = _cxv(s["gamma_measured"], f"{s['id']}.gamma_measured")
        rows.append((ga, 1 + 0j, ga * gm))
        v.append(gm)
    a = [[sum(rows[i][r].conjugate() * rows[i][c] for i in range(len(rows))) for c in range(3)] for r in range(3)]
    b = [sum(rows[i][r].conjugate() * v[i] for i in range(len(rows))) for r in range(3)]
    e1, e2, e3 = _solve3(a, b)
    e00, e11, e10e01 = e2, e3, e1 + e2 * e3
    if e10e01 == 0:
        raise CalibrationSolveError("reflection tracking e10e01 = 0")
    resid = {s["id"]: _r(abs(e00 + e10e01 * _cxv(s["gamma_actual"], "ga") / (1 - e11 * _cxv(s["gamma_actual"], "ga"))
                             - _cxv(s["gamma_measured"], "gm"))) for s in standards}
    return {"e00": e00, "e11": e11, "e10e01": e10e01, "residual_abs": resid, "n_standards": len(standards),
            "solution": "least squares (exact for 3 standards)" if len(standards) > 3 else "exact (3 standards)"}


def sol_correct(gamma_measured, terms):
    """Corrected reflection Gamma_a = (Gamma_m - e00) / (e10e01 + e11 (Gamma_m - e00)) (inverse of Eq. (8))."""
    return RED.correct_reflection(complex(gamma_measured), terms["e00"], terms["e11"], terms["e10e01"])


def coupler_error_model(terms, cal_id, plane="RP-CPL"):
    """Calibration-set 'coupler' entry (vector reflectometer at RP-CPL) from SOL error terms."""
    if plane != "RP-CPL":
        raise RED.ReferencePlaneError("the coupler / reflectometer error model is referred to RP-CPL (A9.2)")
    return {"cal_id": cal_id, "plane": plane, "phase_calibrated": True, "e00": _c(terms["e00"]),
            "e11": _c(terms["e11"]), "e10e01": _c(terms["e10e01"])}


# ================================================================================================ directional coupler
def coupler_power_factor(coupling_dB, cable_loss_dB, sensor_K, sensor_K_convention):
    """Multiplier CF with P_line = CF x P_indicated: coupling C (dB, P_main / P_coupled), coupled-arm cable / pad loss
    L (dB) and sensor calibration factor K = P_indicated / P_incident (certificate convention stated explicitly)."""
    if sensor_K_convention not in SENSOR_K_CONVENTIONS:
        raise FrameworkError(f"sensor calibration-factor convention {sensor_K_convention!r} not in "
                             f"{SENSOR_K_CONVENTIONS} (state the certificate convention)")
    c, l_, k = _fin(coupling_dB, "coupling_dB"), _fin(cable_loss_dB, "cable_loss_dB"), _fin(sensor_K, "sensor_K")
    if c <= 0 or l_ < 0 or not 0 < k <= 1.5:
        raise FrameworkError("coupling_dB > 0, cable_loss_dB >= 0 and 0 < sensor_K required")
    return 10 ** ((c + l_) / 10.0) / k


def term_from_dB(dB):
    """Linear error term from a directivity / match specification in dB (e.g. 47 dB -> 0.0045, REF-AN1287-3 p. 12)."""
    return 10 ** (-_fin(dB, "dB") / 20.0)


def tracking_term_from_dB(dB):
    """|1 - E_RT| from a reflection-tracking specification in dB (0.019 dB -> 0.0022, REF-AN1287-3 p. 12)."""
    return 1 - 10 ** (-abs(_fin(dB, "dB")) / 20.0)


def reflection_worst_case_error(gamma_a_mag, E_D, E_S, E_RT, S21S12_mag=0.0, E_L=0.0):
    """Worst-case reflection error E_D + |S11|^2 E_S + |S21 S12| E_L + |S11| |1 - E_RT| (REF-AN1287-3 p. 12, Fig. 14);
    for a one-port load the S21 S12 E_L term is zero."""
    g = _fin(gamma_a_mag, "gamma")
    return (_fin(E_D, "E_D") + g * g * _fin(E_S, "E_S") + _fin(S21S12_mag, "S21S12") * _fin(E_L, "E_L")
            + g * _fin(E_RT, "E_RT"))


def scalar_gamma_bounds(gamma_meas_mag, E_D, E_S, E_RT):
    """Interval of the true |Gamma| consistent with a scalar reading under the one-port worst-case error (bisection,
    60 halvings, deterministic). 'upper_is_passive_limit' flags an interval that reaches |Gamma| = 1."""
    gm = _fin(gamma_meas_mag, "gamma_meas")
    if not 0 <= gm <= 1:
        raise FrameworkError("measured |Gamma| outside [0, 1]")
    if 2 * E_S + E_RT >= 1:
        raise FrameworkError("error terms too large for a monotone bound (2 E_S + E_RT >= 1)")

    def err(g):
        return reflection_worst_case_error(g, E_D, E_S, E_RT)

    if gm - err(0.0) <= 0:
        lo = 0.0
    else:
        a, b = 0.0, gm
        for _ in range(60):
            m = 0.5 * (a + b)
            a, b = (m, b) if gm - m - err(m) > 0 else (a, m)
        lo = b
    if 1.0 - gm - err(1.0) <= 0:
        hi, passive = 1.0, True
    else:
        a, b = gm, 1.0
        for _ in range(60):
            m = 0.5 * (a + b)
            a, b = (m, b) if m - gm - err(m) <= 0 else (a, m)
        hi, passive = a, False
    return {"gamma_min": _r(lo), "gamma_max": _r(hi), "upper_is_passive_limit": passive,
            "basis": "worst-case one-port error model, REF-AN1287-3 p. 12 (Fig. 14)"}


# ================================================================================================ V/I probe
def k_from_mag_phase(mag, phase_deg):
    """Complex probe gain from a magnitude / phase calibration entry, as [re, im]."""
    m = _fin(mag, "mag")
    if m <= 0:
        raise FrameworkError("calibration magnitude must be > 0")
    return _c(cmath.rect(m, math.radians(_fin(phase_deg, "phase_deg"))))


def vi_calibration_from_known_load(V_raw, I_raw, Z_known, P_known_W, amplitude_convention, basis):
    """Closed-form V/I gains from one known load of impedance Z_known (R > 0) carrying a known power P_known
    (e.g. the calorimetric 50-ohm load of CAL-P2-07/09): k_V / k_I = Z_known I_raw / V_raw and
    |k_I|^2 = P_known / (c R_known |I_raw|^2) with c = 1/2 (peak phasors) or 1 (rms). The absolute phase of k_I does
    not affect Z or P and is fixed to 0 (declared)."""
    if amplitude_convention not in AMPLITUDE_CONVENTIONS:
        raise FrameworkError(f"amplitude_convention must be one of {AMPLITUDE_CONVENTIONS}")
    if not isinstance(basis, str) or not basis.strip():
        raise FrameworkError("basis (the known-load / known-power record) required")
    v, i, z = _cxv(V_raw, "V_raw"), _cxv(I_raw, "I_raw"), _cxv(Z_known, "Z_known")
    p = _fin(P_known_W, "P_known_W")
    if v == 0 or i == 0 or z.real <= 0 or p <= 0:
        raise FrameworkError("non-zero readings, Re(Z_known) > 0 and P_known > 0 required")
    ratio = z * i / v
    c = 0.5 if amplitude_convention == "peak" else 1.0
    k_i = math.sqrt(p / (c * z.real * abs(i) ** 2))
    return {"k_V": _c(ratio * k_i), "k_I": [k_i, 0.0], "amplitude_convention": amplitude_convention,
            "phase_reference": "k_I real (absolute phase irrelevant to Z and P)", "basis": basis}


def vi_power_and_impedance(V_raw, I_raw, k_V, k_I, amplitude_convention):
    v = _cxv(k_V, "k_V") * _cxv(V_raw, "V_raw")
    i = _cxv(k_I, "k_I") * _cxv(I_raw, "I_raw")
    if i == 0:
        raise FrameworkError("zero current")
    c = 0.5 if amplitude_convention == "peak" else 1.0
    return {"Z_ohm": _c(v / i), "P_W": c * (v * i.conjugate()).real}


# ================================================================================================ match topology
def ladder_element_stress(elements, V_load, I_load):
    """Phasor voltage across / current through every element of a declared ladder match (generator side first), walked
    back from the load plane (RP-ANT) V_load, I_load. Element: {'id', 'kind': 'series'|'shunt', 'Z_ohm': [re, im]} at
    the drive frequency and logged tuning state. Returns per-element |V|, |I| (same amplitude convention as the
    inputs) and the input-plane (RP-MIN) V, I."""
    if not isinstance(elements, list) or not elements:
        raise FrameworkError("match topology (element list) required - TBD - requires the selected match and its "
                             "element values at each tuning state")
    v, i = _cxv(V_load, "V_load"), _cxv(I_load, "I_load")
    out = []
    for el in reversed(elements):
        for k in ("id", "kind", "Z_ohm"):
            if k not in el:
                raise FrameworkError(f"match element lacks {k}")
        z = _cxv(el["Z_ohm"], el["id"] + ".Z_ohm")
        if el["kind"] == "series":
            ve, ie = z * i, i
            v = v + ve
        elif el["kind"] == "shunt":
            if z == 0:
                raise FrameworkError(f"{el['id']}: zero shunt impedance")
            ve, ie = v, v / z
            i = i + ie
        else:
            raise FrameworkError(f"{el['id']}: kind must be series or shunt")
        out.append({"id": el["id"], "kind": el["kind"], "V_mag": _r(abs(ve)), "I_mag": _r(abs(ie))})
    return {"elements": list(reversed(out)), "V_in": _c(v), "I_in": _c(i)}


def ladder_abcd(elements):
    m = (1 + 0j, 0j, 0j, 1 + 0j)
    for el in elements:
        z = _cxv(el["Z_ohm"], el["id"])
        m = RED.cascade(m, (1 + 0j, z, 0j, 1 + 0j) if el["kind"] == "series" else (1 + 0j, 0j, 1 / z, 1 + 0j))
    return m


# ================================================================================================ line / match loss
def dissipated_fraction_matched(s11, s21):
    """Fraction of the power incident on port 1 dissipated in a two-port terminated in Z0: 1 - |S11|^2 - |S21|^2."""
    f = 1 - abs(complex(s11)) ** 2 - abs(complex(s21)) ** 2
    if f < -1e-12:
        raise FrameworkError("active or inconsistent two-port (1 - |S11|^2 - |S21|^2 < 0)")
    return max(f, 0.0)


def verify_line_match_loss(*, verification_id, method, eta_pred, u_eta_pred, P_net_W, u_P_net_W, P_ref_load_W,
                           u_P_ref_load_W, k, evidence_record_ids, tuning_states, data_class):
    """At-power verification of the line / match loss model: eta_meas = P_ref_load / P_net (the known power absorbed
    in the reference load, e.g. calorimetry, over the net power at RP-CPL) against the two-port prediction eta_pred.
    Normalized statistic |eta_meas - eta_pred| / sqrt(u^2(eta_meas) + u^2(eta_pred)) <= k (k supplied, never
    defaulted). Any missing uncertainty -> NOT_EVALUATED (never verified). Returns the reducer's
    loss_verification record."""
    if method not in RED.LOSS_VERIFICATION_METHODS:
        raise FrameworkError(f"method {method!r} not in {RED.LOSS_VERIFICATION_METHODS}")
    if data_class not in RED.DATA_CLASSES:
        raise FrameworkError("data_class")
    if not isinstance(evidence_record_ids, list) or not evidence_record_ids:
        raise FrameworkError("evidence_record_ids required")
    if not isinstance(tuning_states, list):
        raise FrameworkError("tuning_states must be a list")
    rec = {"verification_id": verification_id, "method": method, "evidence_record_ids": list(evidence_record_ids),
           "tuning_states": list(tuning_states), "data_class": data_class}
    if k is None:
        raise CriteriaMissingError("k (coverage factor of the loss check) not supplied - TBD_OWNER / LOCK-2")
    kk = _fin(k, "k")
    if any(x is None for x in (u_eta_pred, u_P_net_W, u_P_ref_load_W)):
        rec.update({"status": NOT_EVALUATED, "reason": "missing uncertainty"})
        return rec
    pn, pr = _fin(P_net_W, "P_net_W"), _fin(P_ref_load_W, "P_ref_load_W")
    if pn <= 0 or pr < 0:
        raise FrameworkError("P_net > 0 and P_ref_load >= 0 required")
    eta_m = pr / pn
    u_m = eta_m * math.hypot(_fin(u_P_ref_load_W, "u") / pr if pr else 0.0, _fin(u_P_net_W, "u") / pn)
    u_c = math.hypot(u_m, _fin(u_eta_pred, "u_eta_pred"))
    if u_c == 0:
        rec.update({"status": NOT_EVALUATED, "reason": "zero combined uncertainty"})
        return rec
    stat = abs(eta_m - _fin(eta_pred, "eta_pred")) / u_c
    rec.update({"status": RED.LOSS_VERIFIED if stat <= kk else LOSS_INCONSISTENT, "eta_measured": _r(eta_m),
                "u_eta_measured": _r(u_m), "eta_predicted": _r(eta_pred), "normalized_statistic": _r(stat), "k": kk})
    return rec


# ================================================================================================ uncertainty
def _cholesky(u):
    n = len(u)
    lo = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = u[i][j] - sum(lo[i][k] * lo[j][k] for k in range(j))
            if i == j:
                if s < -1e-15 * max(1.0, abs(u[i][i])):
                    raise UncertaintyMissingError("covariance matrix not positive semidefinite")
                lo[i][j] = math.sqrt(max(s, 0.0))
            else:
                lo[i][j] = s / lo[j][j] if lo[j][j] > 0 else 0.0
    return lo


def _check_cov(x, u):
    n = len(x)
    if u is None:
        raise UncertaintyMissingError("covariance of the inputs not supplied -> NOT_EVALUATED")
    if len(u) != n or any(len(r) != n for r in u):
        raise UncertaintyMissingError("covariance matrix shape does not match the inputs")
    for i in range(n):
        for j in range(n):
            if u[i][j] is None or not math.isfinite(u[i][j]):
                raise UncertaintyMissingError(f"covariance element ({i},{j}) missing -> NOT_EVALUATED")
            if abs(u[i][j] - u[j][i]) > 1e-12 * max(1.0, abs(u[i][j])):
                raise UncertaintyMissingError("covariance matrix not symmetric")


def propagate_linear(f, x, u):
    """Law of propagation of uncertainty U_y = C U_x C^T (REF-JCGM102 6.2.1.3 Eq. (3); scalar form REF-GUM2008 5.2.2
    Eq. (13)), C by central differences with step 1e-3 u(x_i) (inputs with u = 0 contribute nothing)."""
    x = [float(v) for v in x]
    _check_cov(x, u)
    y0 = [float(v) for v in f(x)]
    m, n = len(y0), len(x)
    c = [[0.0] * n for _ in range(m)]
    for j in range(n):
        uj = math.sqrt(u[j][j])
        if uj == 0:
            continue
        h = STEP_FRACTION_OF_U * uj
        xp, xm = list(x), list(x)
        xp[j] += h
        xm[j] -= h
        yp, ym = f(xp), f(xm)
        for i in range(m):
            c[i][j] = (yp[i] - ym[i]) / (2 * h)
    uy = [[sum(c[i][a] * u[a][b] * c[k][b] for a in range(n) for b in range(n)) for k in range(m)] for i in range(m)]
    return {"y": y0, "U_y": uy, "u_y": [math.sqrt(max(uy[i][i], 0.0)) for i in range(m)], "sensitivity": c,
            "method": "GUM law of propagation (JCGM 100:2008 5.2.2; JCGM 102:2011 6.2.1.3)"}


def propagate_mc(f, x, u, *, n_trials, seed):
    """Seeded Monte Carlo propagation (REF-JCGM101): multivariate Gaussian draws x + L z with U_x = L L^T (6.4.8.4),
    mean and covariance of the outputs (7.6) and the probabilistically symmetric 95 % coverage interval from the sorted
    outputs (7.7.2, q = integer part of pM + 1/2). Deterministic for a given seed; normal deviates by Box-Muller from
    random.Random(seed).random()."""
    if not isinstance(n_trials, int) or n_trials < 1000:
        raise FrameworkError("n_trials must be an integer >= 1000 (declared by the caller; see JCGM 101 7.2)")
    if not isinstance(seed, int):
        raise FrameworkError("an integer seed is required (deterministic Monte Carlo)")
    x = [float(v) for v in x]
    _check_cov(x, u)
    lo = _cholesky(u)
    rng = random.Random(seed)
    n = len(x)
    ys = []
    spare = None
    for _ in range(n_trials):
        z = []
        while len(z) < n:
            if spare is not None:
                z.append(spare)
                spare = None
                continue
            u1 = 1.0 - rng.random()
            u2 = rng.random()
            rad = math.sqrt(-2.0 * math.log(u1))
            z.append(rad * math.cos(2 * math.pi * u2))
            spare = rad * math.sin(2 * math.pi * u2)
        xs = [x[i] + sum(lo[i][k] * z[k] for k in range(i + 1)) for i in range(n)]
        ys.append([float(v) for v in f(xs)])
    m = len(ys[0])
    mean = [sum(y[i] for y in ys) / n_trials for i in range(m)]
    cov = [[sum((y[i] - mean[i]) * (y[k] - mean[k]) for y in ys) / (n_trials - 1) for k in range(m)]
           for i in range(m)]
    pm = Fraction(MC_COVERAGE_P_PERCENT, 100) * n_trials
    q = int(pm) if pm.denominator == 1 else int(pm + Fraction(1, 2))
    r = (n_trials - q) // 2 if (n_trials - q) % 2 == 0 else (n_trials - q + 1) // 2
    ci = []
    for i in range(m):
        col = sorted(y[i] for y in ys)
        ci.append([col[r - 1], col[r + q - 1]])      # [y_(r), y_(r+q)], 1-based order statistics (7.7.2)
    return {"y_mean": mean, "U_y": cov, "u_y": [math.sqrt(cov[i][i]) for i in range(m)], "coverage_interval_95": ci,
            "n_trials": n_trials, "seed": seed, "method": "Monte Carlo (JCGM 101:2008 6.4.8.4, 7.6, 7.7.2)"}


def gamma_vswr_pnet_uncertainty(P_fwd_W, u_P_fwd_W, P_ref_W, u_P_ref_W, r_fwd_ref):
    """Analytic GUM propagation for |Gamma| = sqrt(P_ref / P_fwd), VSWR = (1 + |Gamma|) / (1 - |Gamma|) and
    P_net = P_fwd - P_ref with correlation coefficient r_fwd_ref between the two readings (e.g. a shared sensor
    calibration; stated explicitly, no default). REF-GUM2008 5.2.2 Eq. (13)/(14)."""
    if any(v is None for v in (u_P_fwd_W, u_P_ref_W, r_fwd_ref)):
        raise UncertaintyMissingError("u(P_fwd), u(P_ref) and their correlation coefficient are all required -> "
                                      "NOT_EVALUATED")
    pf, pr = _fin(P_fwd_W, "P_fwd"), _fin(P_ref_W, "P_ref")
    uf, ur, rr = _fin(u_P_fwd_W, "u_P_fwd"), _fin(u_P_ref_W, "u_P_ref"), _fin(r_fwd_ref, "r")
    if not -1 <= rr <= 1:
        raise UncertaintyMissingError("correlation coefficient outside [-1, 1]")
    if pf <= 0 or pr <= 0 or pr >= pf:
        raise FrameworkError("0 < P_ref < P_fwd required for the analytic |Gamma| derivative")
    g = math.sqrt(pr / pf)
    dg_dpf, dg_dpr = -0.5 * g / pf, 0.5 / math.sqrt(pr * pf)
    u_g = math.sqrt(max((dg_dpf * uf) ** 2 + (dg_dpr * ur) ** 2 + 2 * dg_dpf * dg_dpr * rr * uf * ur, 0.0))
    u_v = 2 / (1 - g) ** 2 * u_g
    u_pn = math.sqrt(max(uf ** 2 + ur ** 2 - 2 * rr * uf * ur, 0.0))
    return {"gamma_mag": g, "u_gamma_mag": u_g, "VSWR": (1 + g) / (1 - g), "u_VSWR": u_v, "P_net_W": pf - pr,
            "u_P_net_W": u_pn, "method": "analytic GUM (JCGM 100:2008 5.2.2)"}


def z_from_gamma_uncertainty(gamma, U_gamma, z0):
    """Z = Z0 (1 + Gamma) / (1 - Gamma) with the 2x2 covariance of (Re Gamma, Im Gamma): Z is holomorphic in Gamma, so
    the real sensitivity matrix is [[Re d, -Im d], [Im d, Re d]] with d = 2 Z0 / (1 - Gamma)^2 (REF-JCGM102 6.4,
    real and imaginary parts)."""
    g = complex(gamma)
    _check_cov([g.real, g.imag], U_gamma)
    if g == 1:
        raise FrameworkError("Gamma = 1")
    d = 2 * z0 / (1 - g) ** 2
    c = [[d.real, -d.imag], [d.imag, d.real]]
    uz = [[sum(c[i][a] * U_gamma[a][b] * c[k][b] for a in range(2) for b in range(2)) for k in range(2)]
          for i in range(2)]
    z = z0 * (1 + g) / (1 - g)
    return {"Z_ohm": [z.real, z.imag], "U_Z_ohm2": uz, "u_R_ohm": math.sqrt(uz[0][0]), "u_X_ohm": math.sqrt(uz[1][1])}


def p_delivered_uncertainty(P_net_W, u_P_net_W, eta, u_eta):
    """P_delivered = eta P_net (uncorrelated inputs; REF-GUM2008 5.1.2 Eq. (10))."""
    if u_P_net_W is None or u_eta is None:
        raise UncertaintyMissingError("u(P_net) and u(eta) required -> NOT_EVALUATED")
    pn, e = _fin(P_net_W, "P_net"), _fin(eta, "eta")
    return {"P_delivered_W": e * pn, "u_P_delivered_W": math.hypot(e * _fin(u_P_net_W, "u"), pn * _fin(u_eta, "u"))}


DEEMBED_INPUTS = ("m_raw", "e00", "e11", "e10e01", "L11", "L12", "L21", "L22", "M11", "M12", "M21", "M22")


def z_deembed_function(z0):
    """f(x) -> [R, X] of Z_antenna from 24 real inputs: Re/Im of the raw reflection, the three error terms, the line
    S-parameters and the match S-parameters (order DEEMBED_INPUTS). For UB-P2-Z-03 via propagate_linear / _mc."""
    def f(x):
        z = [complex(x[2 * k], x[2 * k + 1]) for k in range(12)]
        g_in = RED.correct_reflection(z[0], z[1], z[2], z[3])
        net = RED.cascade(RED.s_to_abcd(z[4], z[5], z[6], z[7], z0), RED.s_to_abcd(z[8], z[9], z[10], z[11], z0))
        zl = RED.deembed_load(net, RED.z_from_gamma(g_in, z0))
        return [zl.real, zl.imag]
    return f


# ================================================================================================ E/H transitions
def _check_criteria(criteria):
    if criteria is None:
        raise CriteriaMissingError("E/H transition criteria not supplied: form TBD_OWNER (P2Q-09, HM-R06), values "
                                   "TBD_AFTER_EVIDENCE (frozen before the P2 map); nothing is defaulted")
    for k in ("form", "basis", "frozen_before_p2_map"):
        if k not in criteria:
            raise CriteriaMissingError(f"criteria lack {k}")
    if criteria["form"] not in EH_FORMS:
        raise CriteriaMissingError(f"criteria form {criteria['form']!r} not in {EH_FORMS}")
    if criteria["frozen_before_p2_map"] is not True or not RED._ref_ok(criteria["basis"]):
        raise CriteriaMissingError("criteria must be frozen before the P2 map with a non-TBD basis")
    if criteria["form"] == "absolute_step":
        for ch in EH_CHANNELS:
            v = criteria.get("step_" + ch)
            if v is None or _fin(v, "step_" + ch) <= 0:
                raise CriteriaMissingError(f"absolute step threshold for {ch} missing (TBD_AFTER_EVIDENCE)")
    else:
        if criteria.get("k") is None or _fin(criteria["k"], "k") <= 0:
            raise CriteriaMissingError("multiple k of the combined step uncertainty missing (TBD_AFTER_EVIDENCE)")


def _step_exceeds(a, b, ch, criteria):
    va, vb = a.get(ch), b.get(ch)
    if va is None or vb is None:
        return None
    d = _fin(vb, ch) - _fin(va, ch)
    if criteria["form"] == "absolute_step":
        thr = criteria["step_" + ch]
    else:
        ua, ub = a.get("u_" + ch), b.get("u_" + ch)
        if ua is None or ub is None:
            return None                                                   # missing uncertainty -> not evaluable
        thr = criteria["k"] * math.hypot(_fin(ua, "u"), _fin(ub, "u"))
        if thr <= 0:
            return None
    return (abs(d) > thr, d)


def detect_eh_transitions(points, criteria):
    """Adjacent-point jump detection along ONE monotonic sweep (points ordered by index, one direction). The
    photodiode (A9.4 P2Q-05) is required; reflected power (only between points at the same tuning state, HM-R06
    'at fixed tuning') and antenna current are corroboration. Classes: TRANSITION_CANDIDATE_CORROBORATED,
    TRANSITION_CANDIDATE_OPTICAL_ONLY, UNCERTAIN_ELECTRICAL_ONLY (never a transition without the photodiode),
    UNCERTAIN_PHOTODIODE_INVALID. No E / H label is inferred here: the sign of the emission step is reported and the
    E/H assignment stays with the HM-R06 indicators and the photodiode classification of each record."""
    _check_criteria(criteria)
    if not isinstance(points, list) or len(points) < 2:
        raise FrameworkError("a sweep needs at least two points")
    dirs = {p.get("direction") for p in points}
    if len(dirs) != 1 or dirs.pop() not in ("up", "down"):
        raise FrameworkError("one sweep = one direction ('up' or 'down'); split up/down sweeps")
    idx = [p.get("index") for p in points]
    if idx != sorted(idx) or len(set(idx)) != len(idx):
        raise FrameworkError("points must be ordered by strictly increasing sweep index")
    events = []
    for a, b in zip(points, points[1:]):
        pd_valid = all(p.get("photodiode_valid") is True for p in (a, b))
        opt = _step_exceeds(a, b, "photodiode_V", criteria) if pd_valid else None
        same_ts = a.get("tuning_state_id") is not None and a.get("tuning_state_id") == b.get("tuning_state_id")
        refl = _step_exceeds(a, b, "P_reflected_W", criteria) if same_ts else None
        iant = _step_exceeds(a, b, "I_ant_rms_A", criteria)
        elec = [n for n, s in (("P_reflected_W", refl), ("I_ant_rms_A", iant)) if s and s[0]]
        if not pd_valid:
            if elec:
                events.append({"between": [a["index"], b["index"]], "class": "UNCERTAIN_PHOTODIODE_INVALID",
                               "electrical_jumps": elec})
            continue
        if opt is None:
            raise UncertaintyMissingError(f"photodiode step between {a['index']} and {b['index']} not evaluable "
                                          "(missing reading or its uncertainty) -> NOT_EVALUATED")
        if opt[0]:
            events.append({"between": [a["index"], b["index"]],
                           "class": "TRANSITION_CANDIDATE_CORROBORATED" if elec else "TRANSITION_CANDIDATE_OPTICAL_ONLY",
                           "emission_step": "UP" if opt[1] > 0 else "DOWN", "electrical_jumps": elec,
                           "reflected_evaluable": refl is not None,
                           "P_forward_W": [a.get("P_forward_W"), b.get("P_forward_W")],
                           "P_delivered_W": [a.get("P_delivered_W"), b.get("P_delivered_W")]})
        elif elec:
            events.append({"between": [a["index"], b["index"]], "class": "UNCERTAIN_ELECTRICAL_ONLY",
                           "electrical_jumps": elec})
    return {"direction": points[0]["direction"], "n_points": len(points), "events": events,
            "criteria_form": criteria["form"], "criteria_basis": criteria["basis"]}


def hysteresis(up_points, down_points, criteria, fixed_factors_up, fixed_factors_down):
    """Up / down sweep pair (HM-R05): first corroborated emission-UP transition on the up sweep and first corroborated
    emission-DOWN transition on the down sweep, located as power intervals in P_forward AND P_delivered (RF-DALT08-01).
    The agreement / hysteresis judgement rule is P2Q-03 (TBD_OWNER): reported, never judged."""
    if fixed_factors_up != fixed_factors_down or not fixed_factors_up:
        raise FrameworkError("up and down sweeps must share the same (non-empty) fixed factors")
    up = detect_eh_transitions(up_points, criteria)
    dn = detect_eh_transitions(down_points, criteria)
    if up["direction"] != "up" or dn["direction"] != "down":
        raise FrameworkError("first argument must be the up sweep, second the down sweep")

    def first(ev, sign):
        for e in ev["events"]:
            if e["class"] == "TRANSITION_CANDIDATE_CORROBORATED" and e["emission_step"] == sign:
                return e
        return None

    eu, ed = first(up, "UP"), first(dn, "DOWN")
    out = {"up": up, "down": dn, "judgement": "REPORTED_NOT_JUDGED (agreement rule P2Q-03 TBD_OWNER)"}
    for basis in ("P_forward_W", "P_delivered_W"):
        if eu is None or ed is None:
            out["width_" + basis] = "NOT_EVALUATED - no corroborated transition pair"
            continue
        vals = eu[basis] + ed[basis]
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in vals):
            out["width_" + basis] = "NOT_EVALUATED - " + basis + " not numeric at the transition points"
            continue
        lo_u, hi_u = sorted(eu[basis])
        lo_d, hi_d = sorted(ed[basis])
        out["width_" + basis] = {"up_interval": [lo_u, hi_u], "down_interval": [lo_d, hi_d],
                                 "width_min": _r(max(lo_u - hi_d, 0.0)), "width_max": _r(hi_u - lo_d)}
    return out


# ================================================================================================ impedance map
def _canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def map_point(reduced, uncertainty):
    """Map point from a reduced record (reducer output); uncertainty None -> NOT_EVALUATED (never a silent zero)."""
    if uncertainty is None:
        unc = {"status": NOT_EVALUATED, "reason": "missing uncertainty"}
    else:
        miss = [k for k in UNC_FIELDS if k not in uncertainty]
        if miss:
            raise UncertaintyMissingError(f"uncertainty object lacks {miss}")
        unc = dict(uncertainty, status="EVALUATED")
    ps = reduced.get("plasma_state_classification") or reduced.get("unlit_verification")
    cls = ps["state_class"] if isinstance(ps, dict) else ("NOT_CLASSIFIED (phase " + reduced["phase"] + ")")
    pt = {"record_id": reduced["record_id"], "phase": reduced["phase"], "data_class": reduced["data_class"],
          "evidence_tag": reduced["evidence_tag"], "calibration_set_id": reduced["calibration_set_id"],
          "f_Hz": reduced["f_Hz"], "Z0_ohm": reduced["Z0_ohm"], "factors": reduced["factors"],
          "match_state": reduced["match_state"], "plasma_state_class": cls, "sweep": reduced["sweep"],
          "Z_antenna": reduced["Z_antenna"], "Z_antenna_primary_method": reduced["Z_antenna_primary_method"],
          "gamma_antenna_vs_Z0": reduced["gamma_antenna_vs_Z0"], "at_RP_CPL": reduced["at_RP_CPL"],
          "P_line_match_loss_W": reduced["P_line_match_loss_W"], "P_delivered_W": reduced["P_delivered_W"],
          "loss_status": reduced["loss_status"], "uncertainty": unc}
    return pt


def ingest_records(records, calibrations):
    """Reduce every record; refusals are PRESERVED as excluded records with their refusal class and reason (never
    dropped). An UNCERTAIN plasma state is excluded as state UNCERTAIN (A9.4 P2Q-05)."""
    reduced, excluded = [], []
    for rec in records:
        rid = rec.get("record_id") if isinstance(rec, dict) else None
        try:
            reduced.append(RED.reduce_record(rec, calibrations))
        except RED.P2ReducerError as e:
            ex = {"record_id": rid, "refusal_class": type(e).__name__, "reason": str(e)}
            if isinstance(e, RED.UncertainPlasmaStateError):
                ex["plasma_state"] = "UNCERTAIN"
            excluded.append(ex)
    return reduced, excluded


def split_by_domain(points, region):
    """Split map points by the P1 stable-region bounds handed over by P1 (IF-P1-01): region = {'region_id': str,
    'factor_ranges': {factor: [lo, hi]}}. Returns (in_domain, out_of_domain, not_evaluated). A point outside a bound is
    OUT_OF_DOMAIN (excluded from the map, never a FAIL); a point whose factor is missing / non-numeric, or a missing
    region, is NOT_EVALUATED."""
    if region is None:
        return [], [], [{"record_id": p["record_id"], "status": NOT_EVALUATED,
                         "reason": "P1 stable-region bounds not supplied (IF-P1-01)"} for p in points]
    if not RED._ref_ok(region.get("region_id")) or not isinstance(region.get("factor_ranges"), dict) \
            or not region["factor_ranges"]:
        raise FrameworkError("region needs a region_id and non-empty factor_ranges")
    ins, outs, nev = [], [], []
    for p in points:
        why_out, why_nev = [], []
        for fac, rng in region["factor_ranges"].items():
            if not (isinstance(rng, list) and len(rng) == 2):
                raise FrameworkError(f"factor range {fac} must be [lo, hi]")
            lo, hi = _fin(rng[0], fac + ".lo"), _fin(rng[1], fac + ".hi")
            v = p["factors"].get(fac)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                why_nev.append(f"{fac} not recorded")
            elif not lo <= v <= hi:
                why_out.append(f"{fac} = {v} outside [{lo}, {hi}]")
        if why_out:
            outs.append({"record_id": p["record_id"], "status": "OUT_OF_DOMAIN", "reason": "; ".join(why_out),
                         "region_id": region["region_id"]})
        elif why_nev:
            nev.append({"record_id": p["record_id"], "status": NOT_EVALUATED, "reason": "; ".join(why_nev)})
        else:
            ins.append(p)
    return ins, outs, nev


def build_map(map_id, points, excluded, p1_stable_region_ref, calibration_set_ids):
    """Assemble a p2_impedance_map_v1 document. Refuses mixed data classes or evidence tags (measured and synthetic,
    or Ar / N2 / O2-bearing, are never one map) and a HOT_MAP point set without a P1 stable-region reference."""
    if not points:
        raise MapFormatError("a map needs at least one point")
    classes = {p["data_class"] for p in points}
    tags = {p["evidence_tag"] for p in points}
    if len(classes) != 1:
        raise RED.MixedEvidenceError(f"map mixes data classes {sorted(classes)}")
    if len(tags) != 1:
        raise MapFormatError(f"map mixes evidence tags {sorted(tags)}")
    if any(p["phase"] == "HOT_MAP" for p in points) and not RED._ref_ok(p1_stable_region_ref):
        raise RED.SequenceError("HOT_MAP points without a P1 stable-region reference")
    dc = classes.pop()
    body = {"schema": MAP_SCHEMA_ID, "map_id": map_id, "data_class": dc,
            "evidence_status": RED.SYNTHETIC_LABEL if dc == "synthetic_test" else "measured (P2 impedance map)",
            "evidence_tag": tags.pop(), "p1_stable_region_ref": p1_stable_region_ref,
            "calibration_set_ids": sorted(calibration_set_ids), "rating_status": RATING_STATUS,
            "framework": FRAMEWORK_ID, "points": points, "excluded_records": list(excluded)}
    body["content_sha256"] = hashlib.sha256(_canon(body).encode("ascii")).hexdigest()
    return body


def write_map(doc, path):
    validate_map(doc)
    Path(path).write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
                          encoding="ascii")
    return doc["content_sha256"]


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


def read_map(path):
    doc = json.loads(Path(path).read_text(encoding="ascii"))
    validate_map(doc)
    return doc


def map_json_schema():
    """JSON Schema (draft 2020-12) of p2_impedance_map_v1 and p2_sparam_set_v1, generated from this module's tuples."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "P2 ICP impedance map (p2_impedance_map_v1) and S-parameter set (p2_sparam_set_v1)",
        "description": "Generated from p2_framework.py (MAP_HEADER_FIELDS, MAP_POINT_FIELDS, UNC_FIELDS). "
                       "content_sha256 = sha256 of the canonical JSON (sorted keys, ASCII, separators ',' ':') of the "
                       "document without content_sha256. rating_status is always " + RATING_STATUS + ".",
        "type": "object", "required": list(MAP_HEADER_FIELDS),
        "properties": {
            "schema": {"const": MAP_SCHEMA_ID}, "map_id": {"type": "string"},
            "data_class": {"enum": list(RED.DATA_CLASSES)}, "evidence_status": {"type": "string"},
            "evidence_tag": {"enum": list(RED.EVIDENCE_TAGS)}, "p1_stable_region_ref": {"type": ["string", "null"]},
            "calibration_set_ids": {"type": "array", "items": {"type": "string"}},
            "rating_status": {"const": RATING_STATUS}, "framework": {"const": FRAMEWORK_ID},
            "points": {"type": "array", "items": {"$ref": "#/$defs/point"}},
            "excluded_records": {"type": "array", "items": {
                "type": "object", "required": ["record_id", "refusal_class", "reason"]}},
            "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
        "$defs": {
            "point": {"type": "object", "required": list(MAP_POINT_FIELDS), "properties": {
                "uncertainty": {"type": "object", "required": ["status"],
                                "description": "status EVALUATED with " + ", ".join(UNC_FIELDS) +
                                               ", or NOT_EVALUATED (missing uncertainty)"},
                "loss_status": {"type": "string"}, "Z_antenna": {"type": "object"}}},
            "sparam_set": {"type": "object", "required": [
                "schema", "set_id", "n_ports", "Z0_ohm", "from_plane", "to_plane", "cal_id", "phase_calibrated",
                "data_class", "source_file", "source_sha256", "option", "defaults_applied", "tuning_state_id",
                "positions", "points"], "properties": {
                "schema": {"const": SPARAM_SCHEMA_ID}, "n_ports": {"enum": [1, 2]},
                "from_plane": {"enum": list(PLANE_ORDER)}, "to_plane": {"enum": list(PLANE_ORDER) + [None]}}}},
    }


# ================================================================================================ rating structure
def rating_structure(envelope, *, k_rf=None, component_margins=None, heat_load_option=None, match_element_peaks=None,
                     feedthrough_peaks=None):
    """Rating-derivation STRUCTURE (A9.2: ratings are selected by the owner after the complete map). For every RF
    component it lists the envelope quantity it is derived from, the owner input it needs and a candidate minimum
    rating = margin x envelope maximum ONLY when (i) the envelope is MEASURED, (ii) its coverage is complete and
    (iii) the owner input exists; otherwise the value is TBD_AFTER_EVIDENCE (and the input TBD_OWNER). The overall
    RF_COMPONENT_RATINGS status stays TBD_AFTER_IMPEDANCE_MAP in every case (a candidate is not a rating)."""
    measured = isinstance(envelope, dict) and envelope.get("data_classes") == ["measured"]
    complete = isinstance(envelope, dict) and envelope.get("coverage", {}).get("complete") is True
    margins = component_margins or {}
    rows = []
    for cid, name, quantity, units, owner_q in RATING_COMPONENTS:
        if quantity == "feedthrough_V_peak_max_V" or quantity == "feedthrough_I_peak_max_A":
            env_v = (feedthrough_peaks or {}).get(quantity)
        elif quantity == "match_element_peaks":
            env_v = match_element_peaks
        elif quantity == "antenna_V_peak_max_V":
            src = (envelope or {}).get("antenna_peaks_vi_measured", {}).get("V_peak_V")
            env_v = src["max"] if isinstance(src, dict) else None
        elif isinstance(envelope, dict):
            src = envelope.get(quantity)
            env_v = src["max"] if isinstance(src, dict) else (src if isinstance(src, (int, float)) else None)
        else:
            env_v = None
        if owner_q == "ICPQ-11":
            margin = k_rf
        elif owner_q == "ICPQ-10":
            margin = heat_load_option
        else:
            margin = margins.get(cid)
        row = {"id": cid, "component": name, "envelope_quantity": quantity, "units": units,
               "envelope_value": env_v if env_v is not None else TBD_EVIDENCE,
               "owner_input": owner_q, "owner_input_value": margin if margin is not None else TBD_OWNER,
               "rating_status": RATING_STATUS}
        if owner_q == "ICPQ-10":
            row["candidate_minimum"] = TBD_OWNER + " (ICPQ-10 open; alternatives carried side by side in the package)"
        elif not (measured and complete):
            row["candidate_minimum"] = TBD_EVIDENCE + (" (synthetic envelope is not evidence)" if envelope and
                                                       not measured else " (requires a complete measured envelope)")
        elif margin is None:
            row["candidate_minimum"] = TBD_OWNER + f" ({owner_q} open)"
        elif isinstance(env_v, (int, float)) and not isinstance(env_v, bool):
            m = _fin(margin, "margin")
            if m < 1:
                raise RatingInputError(f"{cid}: margin {m} < 1 would rate below the measured envelope")
            row["candidate_minimum"] = {"value": _r(m * env_v), "status": "CANDIDATE_FOR_OWNER_SELECTION"}
        else:
            row["candidate_minimum"] = TBD_EVIDENCE + " (envelope quantity not measured)"
        rows.append(row)
    return {"RF_COMPONENT_RATINGS": RATING_STATUS, "rows": rows,
            "note": "structure only; no rating is selected here (A9.2 a9_10_statuses; owner selects after the complete "
                    "map of the P1 stable region)"}


def feedthrough_peaks_from_network(match_abcd, V_ant, I_ant):
    """Phasor V, I at RP-MIN (feedthrough end of the 50-ohm line) from the antenna-plane V, I through the match ABCD."""
    a, b, c, d = match_abcd
    v, i = _cxv(V_ant, "V_ant"), _cxv(I_ant, "I_ant")
    return {"V": a * v + b * i, "I": c * v + d * i}
