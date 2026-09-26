"""Deterministic generator of cathode_integration_derived_v1.json (CATHINT lane 19).

    python docs/architecture_comparison/cathode_integration/derive_cathode_integration_v1.py          # write
    python docs/architecture_comparison/cathode_integration/derive_cathode_integration_v1.py --check  # verify

Inputs: cathode_integration_data_v1.json (sourced values), the RFP values it records, and the frozen NRLMSIS 2.1
dataset through abep_sim.atmosphere (read only; nothing is regenerated). Output: conditional statements only. Runs in
well under a second; no Julia, no Hall model.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, REPO)

from abep_sim import cathode_integration as ci          # noqa: E402
from abep_sim.atmosphere import atmosphere, orbital_velocity   # noqa: E402

DATA = os.path.join(HERE, "cathode_integration_data_v1.json")
OUT = os.path.join(HERE, "cathode_integration_derived_v1.json")
SOLAR = ("low", "mean", "high")          # the frozen dataset's solar-activity levels


def ambient_rows(d: dict) -> list:
    lo, hi = d["rfp"]["altitude_km"]["value"]
    rows = []
    for alt in (lo, hi):
        for s in SOLAR:
            a = atmosphere(alt, s)
            rows.append({"alt_km": alt, "solar": s, "n_O_m3": a["n_O"], "V_m_s": orbital_velocity(alt),
                         "source": "frozen_atmosphere"})
    return rows


def build() -> dict:
    d = ci.load_data(DATA)
    return ci.derive_conditional_statements(d, ambient_rows(d))


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def main(argv: list) -> int:
    text = dumps(build())
    if "--check" in argv:
        if not os.path.isfile(OUT):
            print(f"missing {OUT}")
            return 1
        with open(OUT) as fh:
            same = fh.read() == text
        print("OK" if same else f"MISMATCH: {OUT} is not reproduced by this script")
        return 0 if same else 1
    with open(OUT, "w") as fh:
        fh.write(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
