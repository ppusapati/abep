#!/usr/bin/env python3
"""IV-01 of NP-MISSION-INTEGRATION v1: non-authoritative exact-rational cross-check (prereg independent_verification).

Reads the JSON of `abep-mission-integration al-export` (synthetic AL vectors, SYNTHETIC_TEST_DATA_NOT_EVIDENCE) and
recomputes every schedule total and Xe ledger with fractions.Fraction from the same binary64 inputs: each contribution
is the binary64 product q * (dt * 3600) (EQ-01), summed exactly; the ledger terms are exact. The Rust value must lie
within 1 ulp of the correctly rounded rational value. Never a CI dependency and never a reference (RM-R26).

    abep-mission-integration al-export > al.json
    python3 iv01_exact_rational_check.py al.json
"""
import json
import math
import sys
from fractions import Fraction


def ulp(x: float) -> float:
    return math.ulp(x) if x != 0 else math.ulp(0.0)


def within_1ulp(rust, exact: Fraction) -> bool:
    if rust is None:
        return False
    rounded = float(exact)
    return abs(rust - rounded) <= ulp(rounded)


def main(path: str) -> int:
    d = json.load(open(path))
    checks, fails = 0, []
    for c in d["cases"]:
        name = c["case"]
        sums = {}
        for total, blk in c["contributions"].items():
            rows = blk["rows"]
            if any(v is None for v, _ in rows):
                continue
            exact = sum((Fraction(v * (dt * 3600.0)) for v, dt in rows), Fraction(0))
            sums[total] = exact
            checks += 1
            if not within_1ulp(blk["rust"], exact):
                fails.append(f"{name} {total}: rust {blk['rust']!r} vs {float(exact)!r}")
        ev = sum((Fraction(m * float(n)) for m, n in c["xe_events"]["rows"]), Fraction(0))
        checks += 1
        if not within_1ulp(c["xe_events"]["rust"], ev):
            fails.append(f"{name} xe events")
        m_xe = sums.get("M_xe_continuous_kg", Fraction(0)) + ev
        checks += 1
        if not within_1ulp(c["M_xe_total_rust"], m_xe):
            fails.append(f"{name} M_xe_total: rust {c['M_xe_total_rust']!r} vs {float(m_xe)!r}")
        end = Fraction(c["m_xe_loaded"]) - m_xe
        usable = end - Fraction(c["xe_reserve"]) - Fraction(c["xe_residual"])
        wet = Fraction(c["m_dry"]) + end
        for k, exact in (("m_xe_end_rust", end), ("m_xe_usable_rust", usable), ("m_wet_end_rust", wet)):
            checks += 1
            if not within_1ulp(c[k], exact):
                fails.append(f"{name} {k}: rust {c[k]!r} vs {float(exact)!r}")
        for case_kg, par in c["planning"]:
            checks += 1
            if not within_1ulp(par, Fraction(case_kg) - m_xe):
                fails.append(f"{name} planning {case_kg}: rust {par!r}")
        if name.startswith("AL-08"):
            lo, hi = c["pb_ao"]
            phi = sums["Phi_AO_m2"]
            checks += 1
            if not (Fraction(lo) <= phi <= Fraction(hi)):
                fails.append(f"{name} PB-AO bracket")
        if name == "AL-09":
            checks += 1
            if c["contributions"]["M_atm_delivered_kg"]["rust"] != 3600.0 or sums["M_atm_delivered_kg"] != 3600:
                fails.append("AL-09 cancellation")
    print(json.dumps({"iv": "IV-01", "authoritative": False, "cases": len(d["cases"]), "checks": checks,
                      "failures": fails, "agree": not fails}, indent=1))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
