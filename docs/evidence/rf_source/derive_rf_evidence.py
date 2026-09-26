"""Derived numbers for the RF-source evidence matrix (docs/evidence/rf_source/rf_evidence_matrix.json).

Every matrix entry that carries a ``derived`` block is a number we computed from other entries (unit
conversions, ratios, loose bounds). This script is the only producer of those numbers. It is
deterministic (no network, no randomness, no clock) and uses the repository's physical constants
(``abep_sim/constants.py``, loaded by path so the simulator package is not imported).

Usage (from the repository root):
    python docs/evidence/rf_source/derive_rf_evidence.py            # check; exit status 1 on any mismatch
    python docs/evidence/rf_source/derive_rf_evidence.py --write    # recompute and rewrite derived values
    python docs/evidence/rf_source/derive_rf_evidence.py --list     # print every derived value

Rules enforced here (and by tests/test_rf_source_evidence.py):
  * a derived value is the function evaluated at the ``inputs``; when an input is a range {min, max} the
    function is evaluated at every combination of range end points and the result is reported as
    {min, max} (all functions used here are monotonic in each argument, so this is exact);
  * values are rounded to 4 significant figures;
  * every numeric input must be traceable to a number in one of the ``from_ids`` entries (value or
    conditions, allowing a pure power-of-ten unit-prefix conversion such as mT -> T or mA -> A), or be
    declared in ``assumed_inputs`` with a reason. Species masses come from the repository constants.
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
MATRIX = HERE / "rf_evidence_matrix.json"


def _load_constants():
    spec = importlib.util.spec_from_file_location("abep_constants_for_rf_audit", REPO / "abep_sim" / "constants.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = _load_constants()


# ----------------------------------------------------------------------------------------- functions
def number_density(p_Pa: float, T_K: float) -> float:
    """Ideal-gas neutral number density n = p / (k_B T)  [m^-3]."""
    return p_Pa / (C.K_B * T_K)


def ionization_fraction(n_e_m3: float, p_Pa: float, T_K: float) -> float:
    """n_e / n_n with n_n = p / (k_B T) (neutral depletion ignored)  [-]."""
    return n_e_m3 / number_density(p_Pa, T_K)


def s11_reflected_fraction(s11_dB: float) -> float:
    """Reflected power fraction |Gamma|^2 = 10^(S11/10) for S11 in dB  [-]."""
    return 10.0 ** (s11_dB / 10.0)


def power_transfer_efficiency(R_total_ohm: float, R_vac_ohm: float) -> float:
    """Equivalent-circuit power transfer efficiency (R_total - R_vac) / R_total  [-]."""
    return (R_total_ohm - R_vac_ohm) / R_total_ohm


def power_per_current(P_W: float, I_A: float) -> float:
    """Power per ampere of extracted current  [W/A]."""
    return P_W / I_A


def one_minus(x: float) -> float:
    """1 - x  [-]."""
    return 1.0 - x


def energy_per_injected_particle_eV(P_W: float, mdot_mg_s: float, species: str) -> float:
    """Absorbed power divided by the injected particle flux, in eV per injected particle.

    Particle flux = mdot / m_species, with m_species from abep_sim/constants.py (nominal masses).
    """
    m = C.M_SPECIES[species]
    flux = (mdot_mg_s * 1e-6) / m          # particles / s
    return P_W / flux / C.E_CHARGE


FUNCTIONS = {
    "number_density": number_density,
    "ionization_fraction": ionization_fraction,
    "s11_reflected_fraction": s11_reflected_fraction,
    "power_transfer_efficiency": power_transfer_efficiency,
    "power_per_current": power_per_current,
    "one_minus": one_minus,
    "energy_per_injected_particle_eV": energy_per_injected_particle_eV,
}


# ------------------------------------------------------------------------------------------- helpers
def sig(x: float, n: int = 4) -> float:
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.{n - 1}e}")


def _endpoints(v):
    if isinstance(v, dict):
        return [v[k] for k in ("min", "max") if k in v]
    return [v]


def evaluate(derived: dict):
    fn = FUNCTIONS[derived["function"]]
    inputs = derived["inputs"]
    keys = list(inputs)
    is_range = any(isinstance(inputs[k], dict) for k in keys)
    combos = itertools.product(*[_endpoints(inputs[k]) for k in keys])
    results = [fn(**dict(zip(keys, combo))) for combo in combos]
    if is_range:
        return {"min": sig(min(results)), "max": sig(max(results))}
    return sig(results[0])


def _numbers_in(obj):
    """All numbers inside an entry's value and conditions."""
    out = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_numbers_in(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_numbers_in(v))
    return out


def _prefix_equal(a: float, b: float) -> bool:
    """True if a == b up to a pure power-of-ten factor (unit-prefix conversion), within 1e-9 relative."""
    if a == 0 or b == 0:
        return a == b
    if (a > 0) != (b > 0):
        return False
    r = math.log10(abs(a) / abs(b))
    k = round(r)
    return abs(k) <= 9 and abs(r - k) < 1e-9


def traceability_problems(entry: dict, by_id: dict) -> list[str]:
    d = entry["derived"]
    probs = []
    pool = []
    for fid in d["from_ids"]:
        if fid not in by_id:
            probs.append(f"{entry['id']}: from_id {fid} not in matrix")
            continue
        src = by_id[fid]
        pool.extend(_numbers_in(src["value"]))
        pool.extend(_numbers_in(src["conditions"]))
    assumed = d.get("assumed_inputs", {})
    for key, val in d["inputs"].items():
        if key == "species":
            if val not in C.M_SPECIES:
                probs.append(f"{entry['id']}: species {val!r} not in abep_sim/constants.M_SPECIES")
            continue
        if key in assumed:
            continue
        for x in _endpoints(val):
            if not any(_prefix_equal(float(x), p) for p in pool):
                probs.append(f"{entry['id']}: input {key}={x} not traceable to {d['from_ids']} and not declared assumed")
    return probs


def load(path=MATRIX) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def check(matrix: dict) -> list[str]:
    by_id = {e["id"]: e for e in matrix["entries"]}
    problems = []
    for e in matrix["entries"]:
        if "derived" not in e:
            continue
        want = evaluate(e["derived"])
        if e["value"] != want:
            problems.append(f"{e['id']}: value {e['value']!r} != derived {want!r}")
        problems.extend(traceability_problems(e, by_id))
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="recompute derived values and rewrite the matrix")
    ap.add_argument("--list", action="store_true", help="print derived values")
    args = ap.parse_args(argv)
    m = load()
    if args.write:
        for e in m["entries"]:
            if "derived" in e:
                e["value"] = evaluate(e["derived"])
        MATRIX.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.list:
        for e in m["entries"]:
            if "derived" in e:
                print(f"{e['id']:<18} {e['derived']['function']:<32} {json.dumps(e['value'])} {e['units']}")
    problems = check(m)
    for p in problems:
        print("MISMATCH:", p, file=sys.stderr)
    if not problems:
        print(f"OK: {sum('derived' in e for e in m['entries'])} derived values reproduce; "
              f"{len(m['entries'])} entries")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
