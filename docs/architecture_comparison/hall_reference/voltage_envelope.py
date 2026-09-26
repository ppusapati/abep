#!/usr/bin/env python3
"""Ideal-beam reference table for the common Hall accelerator reference (hall_reference_v1).

For every singly charged ion listed in the reference and every discharge voltage V_d of the PROPOSED evaluation set,
this script computes

    v_b      = sqrt(2 e V_d / m_i)     ideal beam velocity: monoenergetic, collimated, accelerated through the full V_d
    T/P_jet  = 2 / v_b                 thrust per unit jet power of that ideal beam (P_jet = T v_b / 2)

These are physics identities under the stated assumptions (evidence class: model-derived). They are NOT Hall-thruster
performance predictions and NOT bounds on the discharge power. A real beam has voltage losses, a velocity spread,
divergence, multiply charged ions and incomplete mass utilization. Those come only from an admitted transport closure or
from hardware, and they are TBD in the reference. The table only shows how the jet-power cost of thrust scales with V_d
and ion mass, which is the envelope argument of the discharge-voltage interface (HALL_ACCELERATOR_REFERENCE.md, section 5).

Constants come from abep_sim/constants.py: E_CHARGE (exact SI value), AMU, and M_SPECIES in the repository's rounded
convention (O 16, N2 28, O2 32, Xe 131.3 u). N+ uses half of the repository N2 mass. The ion mass is set equal to the parent
neutral mass: the electron mass is neglected (relative effect about m_e / 14 u, i.e. below 4e-5 for the lightest ion here).

Inputs are read from the reference JSON: the voltages from the pointer stored in ideal_beam_reference_table.voltages_from
and the ion list from ideal_beam_reference_table.ions. Nothing has a default; a missing or invalid input raises.
Pure and deterministic: the same inputs always give the same rounded numbers.

Usage (from the repository root):
    python docs/architecture_comparison/hall_reference/voltage_envelope.py            # print the table
    python docs/architecture_comparison/hall_reference/voltage_envelope.py --check    # exit 1 if the JSON table differs
    python docs/architecture_comparison/hall_reference/voltage_envelope.py --write    # rewrite the table in the JSON
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REFERENCE_FILE = os.path.join(HERE, "hall_reference_v1.json")
SCRIPT_REL = "docs/architecture_comparison/hall_reference/voltage_envelope.py"

# Ion -> (parent species key in abep_sim.constants.M_SPECIES, mass factor). N+ is half of the repository N2 mass.
ION_MASS_RULE = {
    "N2+": ("N2", 1.0),
    "N+": ("N2", 0.5),
    "O2+": ("O2", 1.0),
    "O+": ("O", 1.0),
    "Xe+": ("Xe", 1.0),
}
V_DECIMALS = 1        # v_b rounded to 0.1 m/s
TP_DECIMALS = 3       # T/P_jet rounded to 0.001 mN/kW


def _constants():
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from abep_sim.constants import AMU, E_CHARGE, M_SPECIES
    return E_CHARGE, AMU, M_SPECIES


def ion_mass_kg(ion: str) -> float:
    if ion not in ION_MASS_RULE:
        raise ValueError(f"ion {ion!r} has no mass rule (known: {sorted(ION_MASS_RULE)})")
    _, _, m_species = _constants()
    parent, factor = ION_MASS_RULE[ion]
    return m_species[parent] * factor


def ion_mass_u(ion: str) -> float:
    _, amu, _ = _constants()
    return round(ion_mass_kg(ion) / amu, 6)


def beam_velocity_m_s(v_d: float, m_kg: float) -> float:
    e, _, _ = _constants()
    if not (isinstance(v_d, (int, float)) and not isinstance(v_d, bool) and v_d > 0):
        raise ValueError(f"discharge voltage must be a positive number, got {v_d!r}")
    if not m_kg > 0:
        raise ValueError(f"ion mass must be positive, got {m_kg!r}")
    return math.sqrt(2.0 * e * float(v_d) / m_kg)


def compute_rows(voltages_V: list, ions: list) -> dict:
    """Pure: {ion: {'ion_mass_u': float, 'v_b_m_s': [..], 'thrust_per_jet_power_mN_per_kW': [..]}} in voltage order."""
    if not voltages_V:
        raise ValueError("no discharge voltages given")
    if not ions:
        raise ValueError("no ions given")
    out = {}
    for ion in ions:
        m = ion_mass_kg(ion)
        vb = [beam_velocity_m_s(v, m) for v in voltages_V]
        out[ion] = {
            "ion_mass_u": ion_mass_u(ion),
            "v_b_m_s": [round(x, V_DECIMALS) for x in vb],
            # 2 / v_b in N/W -> mN/kW is a factor 1e6
            "thrust_per_jet_power_mN_per_kW": [round(2.0 / x * 1.0e6, TP_DECIMALS) for x in vb],
        }
    return out


def resolve_pointer(doc, pointer: str):
    """RFC 6901 JSON pointer (no escapes needed for the keys used here)."""
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON pointer: {pointer!r}")
    node = doc
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def inputs_from_reference(ref: dict) -> tuple[list, list]:
    table = ref["discharge_voltage_interface"]["ideal_beam_reference_table"]
    vset = resolve_pointer(ref, table["voltages_from"])
    voltages = vset["value"]
    if not isinstance(voltages, list) or not voltages:
        raise ValueError(f"{table['voltages_from']} has no voltage list (status {vset.get('status')!r})")
    return voltages, list(table["ions"])


def quantity_rows(rows: dict, voltages_pointer: str) -> dict:
    """Wrap the computed numbers in the reference's quantity objects (status SOURCED, model-derived, this script)."""
    out = {}
    for ion, r in rows.items():
        parent, factor = ION_MASS_RULE[ion]
        out[ion] = {
            "ion_mass_u": {
                "definition": f"ion mass used for {ion} (parent neutral mass; electron mass neglected)",
                "value": r["ion_mass_u"],
                "unit": "u",
                "status": "SOURCED",
                "evidence_class": "assumed",
                "source": ["SRC-CONSTANTS"],
                "locator": (f"abep_sim/constants.py M_SPECIES['{parent}']" + (f" x {factor}" if factor != 1.0 else "")
                            + " / AMU (repository rounded convention)"),
            },
            "v_b_m_s": {
                "definition": (f"ideal beam velocity sqrt(2 e V_d / m) of {ion} at each V_d of {voltages_pointer} "
                               "(same order)"),
                "value": r["v_b_m_s"],
                "unit": "m s^-1",
                "status": "SOURCED",
                "evidence_class": "model-derived",
                "source": ["SRC-VENV-SCRIPT", "SRC-CONSTANTS"],
                "locator": f"{SCRIPT_REL} compute_rows()",
                "uncertainty": "exact under the stated assumptions; rounded to 0.1 m/s; not a thruster exhaust velocity",
            },
            "thrust_per_jet_power_mN_per_kW": {
                "definition": (f"thrust per unit jet power 2 / v_b of an ideal {ion} beam at each V_d of "
                               f"{voltages_pointer} (same order)"),
                "value": r["thrust_per_jet_power_mN_per_kW"],
                "unit": "mN kW^-1",
                "status": "SOURCED",
                "evidence_class": "model-derived",
                "source": ["SRC-VENV-SCRIPT", "SRC-CONSTANTS"],
                "locator": f"{SCRIPT_REL} compute_rows()",
                "uncertainty": ("exact under the stated assumptions; rounded to 0.001 mN/kW; not a thruster "
                                "thrust-to-power ratio (that needs the discharge efficiency, TBD)"),
            },
        }
    return out


def load_reference(path: str = REFERENCE_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def expected_table_rows(ref: dict) -> dict:
    voltages, ions = inputs_from_reference(ref)
    pointer = ref["discharge_voltage_interface"]["ideal_beam_reference_table"]["voltages_from"]
    return quantity_rows(compute_rows(voltages, ions), pointer)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="exit 1 if the table stored in the reference JSON differs")
    g.add_argument("--write", action="store_true", help="rewrite the table in the reference JSON")
    args = ap.parse_args(argv)
    ref = load_reference()
    rows = expected_table_rows(ref)
    table = ref["discharge_voltage_interface"]["ideal_beam_reference_table"]
    if args.check:
        if table["rows"] != rows:
            print("ideal_beam_reference_table.rows differs from voltage_envelope.py output", file=sys.stderr)
            return 1
        print("OK: ideal_beam_reference_table.rows matches voltage_envelope.py")
        return 0
    if args.write:
        table["rows"] = rows
        with open(REFERENCE_FILE, "w", encoding="utf-8") as f:
            json.dump(ref, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {len(rows)} ion rows to {os.path.relpath(REFERENCE_FILE, ROOT)}")
        return 0
    voltages, _ = inputs_from_reference(ref)
    print("V_d [V]: " + ", ".join(str(v) for v in voltages))
    for ion, r in rows.items():
        print(f"{ion:4s} m = {r['ion_mass_u']['value']} u  v_b [m/s] = {r['v_b_m_s']['value']}  "
              f"T/P_jet [mN/kW] = {r['thrust_per_jet_power_mN_per_kW']['value']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
