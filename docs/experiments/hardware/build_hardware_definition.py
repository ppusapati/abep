#!/usr/bin/env python3
"""W3 common-hardware definition (fo_hardware_definition): deterministic generator of the register's derived numbers.

The requirements register ``hardware_requirements_v1.json`` (same folder) is hand-written. Its only computed block is
``derived_numbers.outputs``. This script recomputes that block from ``derived_numbers.inputs`` (every input is a
quantity with a source and an evidence class), so no derived number is typed by hand.

Usage::

    python docs/experiments/hardware/build_hardware_definition.py --check        # outputs == recomputation (exit 1 if not)
    python docs/experiments/hardware/build_hardware_definition.py --write        # rewrite derived_numbers.outputs
    python docs/experiments/hardware/build_hardware_definition.py --verify-pins  # inputs == their repository sources

Pure standard library. No default physical or efficiency value is hidden here: every number comes from the register's
``inputs`` block; a missing input raises (CLAUDE.md rule 3). ``--verify-pins`` reads the source files of the inputs
(merged lanes and ``abep_sim/constants.py``) lazily and raises a clear error if one is missing.

Nothing here is a Hall performance prediction. The relations used are identities:
  * electron-cyclotron resonance field B_res = 2 pi f m_e / e (as ECR-D001 in docs/evidence/ecr_source/);
  * thrust-per-bus-power floor T/P_bus > T_min / P_max implied by the RFP ceiling (strict inequality in the RFP);
  * discharge-current bound I_d <= P_max / V_d at any bus-compliant point, because the bus_power_boundary_v1 ledger books
    P_bus = sum_c P_load,c / eta_c with eta_c in (0, 1] and P_load,c >= 0, so V_d I_d = P_load,hall_discharge <= P_bus;
  * an equal root-sum-square sub-allocation of the lane-25 installation term u_inst over N contributors (PROPOSED), and
    the thrust-axis alignment angle whose cosine loss equals one contributor share: theta = arccos(exp(-u_c)).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REGISTER = os.path.join(HERE, "hardware_requirements_v1.json")
SCRIPT_REL = "docs/experiments/hardware/build_hardware_definition.py"

REQUIRED_INPUTS = (
    "e_C", "m_e_kg", "f_ecr_candidate_2p45GHz_Hz", "f_ecr_candidate_5p8GHz_Hz", "B_hall_typical_xenon_database_G",
    "B_rf_ignition_assist_T", "thrust_min_mN", "thrust_max_mN", "power_max_W", "V_d_proposed_set_V",
    "V_d_relaxed_upper_V", "u_inst_max_n4", "u_inst_max_n6", "u_inst_max_n8", "n_installation_contributors",
)


def _sig(x: float) -> float:
    """Round to 10 significant digits (stable text representation; recomputation compares exactly)."""
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.10g}")


def _val(inputs: dict, key: str):
    if key not in inputs:
        raise KeyError(f"derived_numbers.inputs is missing {key!r}; no default exists (CLAUDE.md rule 3)")
    q = inputs[key]
    v = q.get("value")
    if v is None:
        raise ValueError(f"input {key!r} has no value (status {q.get('status')!r}); cannot derive")
    return v


def _q(value, unit: str, locator: str, note: str | None = None) -> dict:
    out = {"value": value, "unit": unit, "status": "DERIVED", "evidence_class": "model-derived",
           "source": ["SRC-THIS-SCRIPT"], "locator": f"{SCRIPT_REL}: {locator}"}
    if note:
        out["note"] = note
    return out


def derive(inputs: dict) -> dict:
    """Recompute every derived number from the register inputs. Raises on any missing input."""
    for k in REQUIRED_INPUTS:
        _val(inputs, k)
    e = float(_val(inputs, "e_C"))
    me = float(_val(inputs, "m_e_kg"))
    out: dict = {}

    # 1. ECR resonance field at the candidate frequencies (fundamental harmonic, non-relativistic).
    for key, tag in (("f_ecr_candidate_2p45GHz_Hz", "2p45GHz"), ("f_ecr_candidate_5p8GHz_Hz", "5p8GHz")):
        f = float(_val(inputs, key))
        out[f"B_res_ecr_{tag}_T"] = _q(_sig(2.0 * math.pi * f * me / e), "T", f"derive(): 2*pi*f*m_e/e with f = {key}",
                                       "identity; cross-check ECR-D001 (docs/evidence/ecr_source/ecr_evidence_matrix.json)")
    b_hall_T = float(_val(inputs, "B_hall_typical_xenon_database_G")) * 1e-4
    b_res = 2.0 * math.pi * float(_val(inputs, "f_ecr_candidate_2p45GHz_Hz")) * me / e
    out["ratio_B_res_2p45GHz_to_B_hall_typical"] = _q(
        _sig(b_res / b_hall_T), "-", "derive(): B_res(2.45 GHz) / (B_hall_typical_xenon_database_G * 1e-4 T/G)",
        "context only: the 200 G denominator is a xenon-database typical value (lane 17 EV-B4), not a Vyovrinda value")
    out["ratio_B_rf_assist_to_B_hall_typical"] = _q(
        _sig(float(_val(inputs, "B_rf_ignition_assist_T")) / b_hall_T), "-",
        "derive(): B_rf_ignition_assist_T / (B_hall_typical_xenon_database_G * 1e-4 T/G)",
        "context only: field on the RF-source axis (RF-IAC18-01), not a field inside any Hall channel")

    # 2. Absolute thrust gate: thrust per bus power implied by the RFP ceiling.
    t_min = float(_val(inputs, "thrust_min_mN"))
    t_max = float(_val(inputs, "thrust_max_mN"))
    p_max = float(_val(inputs, "power_max_W"))
    out["T_over_Pbus_floor_at_T_min_mN_per_kW"] = _q(
        _sig(t_min / (p_max / 1000.0)), "mN kW^-1", "derive(): thrust_min_mN / (power_max_W / 1000)",
        "necessary, not sufficient: sustained T >= T_min with P_bus < P_max implies T/P_bus > this value (strict)")
    out["Pbus_over_T_ceiling_at_T_min_W_per_mN"] = _q(
        _sig(p_max / t_min), "W mN^-1", "derive(): power_max_W / thrust_min_mN")
    out["T_over_Pbus_floor_at_T_max_mN_per_kW"] = _q(
        _sig(t_max / (p_max / 1000.0)), "mN kW^-1", "derive(): thrust_max_mN / (power_max_W / 1000)",
        "applies ONLY if the owner reads the registered 25 mN capability as required within P_bus < 1.5 kW (HWQ-10)")
    out["Pbus_over_T_ceiling_at_T_max_W_per_mN"] = _q(
        _sig(p_max / t_max), "W mN^-1", "derive(): power_max_W / thrust_max_mN",
        "applies ONLY under the HWQ-10 reading stated above")

    # 3. Discharge-current bound at bus-compliant points, per proposed V_d node and the relaxed upper end.
    vset = _val(inputs, "V_d_proposed_set_V")
    if not isinstance(vset, list) or not vset:
        raise ValueError("V_d_proposed_set_V must be a non-empty list")
    vds = [float(v) for v in vset] + [float(_val(inputs, "V_d_relaxed_upper_V"))]
    for vd in vds:
        if vd <= 0:
            raise ValueError(f"non-positive V_d {vd}")
        out[f"I_d_bound_at_Vd_{int(round(vd))}V_A"] = _q(
            _sig(p_max / vd), "A", f"derive(): power_max_W / V_d, V_d = {vd:g} V",
            "upper bound on I_d at any P_bus-compliant point (eta <= 1, loads >= 0); not a prediction of I_d")
    out["I_d_bound_envelope_max_A"] = _q(
        _sig(p_max / min(vds)), "A", "derive(): power_max_W / min(V_d set incl. relaxed end)",
        "sizing basis for the discharge supply and C-1 emission (HW-ENV-02, HW-C1-02); transients excluded")

    # 4. Installation (re-mount) budget sub-allocation and the thrust-axis alignment bound.
    n_c = _val(inputs, "n_installation_contributors")
    if not isinstance(n_c, int) or n_c < 1:
        raise ValueError("n_installation_contributors must be a positive integer")
    for n in (4, 6, 8):
        u_inst = float(_val(inputs, f"u_inst_max_n{n}"))
        u_c = u_inst / math.sqrt(n_c)
        out[f"u_contributor_max_n{n}"] = _q(
            _sig(u_c), "ln-ratio (1 sigma, per installation)",
            f"derive(): u_inst_max_n{n} / sqrt(n_installation_contributors)",
            "equal root-sum-square share (PROPOSED allocation, HW-SVC-03)")
        theta = math.acos(math.exp(-u_c))
        out[f"theta_align_max_n{n}_deg"] = _q(
            _sig(math.degrees(theta)), "deg", f"derive(): degrees(arccos(exp(-u_contributor_max_n{n})))",
            "installation-to-installation change of the angle between thrust axis and stand sensitive axis whose "
            "cosine loss alone uses one contributor share; first-order geometry, not a claim that alignment dominates")
    return out


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check(register: dict) -> list[str]:
    """Return a list of mismatches between the register's outputs and a fresh recomputation."""
    dn = register["derived_numbers"]
    fresh = derive(dn["inputs"])
    have = dn.get("outputs", {})
    errs = []
    for k in sorted(set(fresh) | set(have)):
        if k not in have:
            errs.append(f"missing output {k}")
        elif k not in fresh:
            errs.append(f"stale output {k} (not produced by derive())")
        elif have[k] != fresh[k]:
            errs.append(f"output {k}: register {have[k].get('value')!r} != recomputed {fresh[k]['value']!r}")
    return errs


def _need(rel: str) -> str:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        raise FileNotFoundError(f"pinned source {rel} is not in this checkout; --verify-pins needs it "
                                "(the register itself and --check do not)")
    return path


def verify_pins(register: dict) -> list[str]:
    """Compare every pinned input with the repository file it was transcribed from. Raises if a source is missing."""
    inp = register["derived_numbers"]["inputs"]
    errs: list[str] = []

    def cmp(name, got, want):
        if isinstance(want, list):
            ok = isinstance(got, list) and len(got) == len(want) and all(math.isclose(a, b, rel_tol=0, abs_tol=0)
                                                                         for a, b in zip(got, want))
        else:
            ok = got == want
        if not ok:
            errs.append(f"{name}: register {got!r} != source {want!r}")

    # RFP constants (abep_sim/constants.py is a pure constants/dataclass module).
    _need("abep_sim/constants.py")
    sys.path.insert(0, ROOT)
    try:
        from abep_sim.constants import RFPConstraints  # noqa: E402
    finally:
        sys.path.pop(0)
    rfp = RFPConstraints()
    cmp("thrust_min_mN", _val(inp, "thrust_min_mN"), rfp.thrust_min_mN)
    cmp("thrust_max_mN", _val(inp, "thrust_max_mN"), rfp.thrust_max_mN)
    cmp("power_max_W", _val(inp, "power_max_W"), rfp.power_max_W)

    ecr = _load(_need("docs/evidence/ecr_source/ecr_evidence_matrix.json"))
    cmp("e_C", _val(inp, "e_C"), ecr["constants"]["e_C"])
    cmp("m_e_kg", _val(inp, "m_e_kg"), ecr["constants"]["m_e_kg"])
    d001 = [x for x in ecr["entries"] if x.get("id") == "ECR-D001"]
    if not d001 or d001[0]["conditions"]["frequency_Hz"] != _val(inp, "f_ecr_candidate_2p45GHz_Hz"):
        errs.append("f_ecr_candidate_2p45GHz_Hz does not match ECR-D001 conditions.frequency_Hz")

    href = _load(_need("docs/architecture_comparison/hall_reference/hall_reference_v1.json"))
    cmp("V_d_proposed_set_V", _val(inp, "V_d_proposed_set_V"),
        href["discharge_voltage_interface"]["proposed_evaluation_set_V"]["value"])
    ev_b4 = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("id") == "EV-B4":
                ev_b4.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(href)
    if not ev_b4:
        errs.append("EV-B4 not found in hall_reference_v1.json")
    else:
        cmp("B_hall_typical_xenon_database_G", _val(inp, "B_hall_typical_xenon_database_G"),
            ev_b4[0]["stated_values"]["typical_field_xenon_database"]["value"])

    rf = _load(_need("docs/evidence/rf_source/rf_evidence_matrix.json"))
    iac = [x for x in rf["entries"] if x.get("id") == "RF-IAC18-01"]
    if not iac:
        errs.append("RF-IAC18-01 not found in rf_evidence_matrix.json")
    else:
        if iac[0]["units"] != "mT":
            errs.append("RF-IAC18-01 units changed")
        cmp("B_rf_ignition_assist_T", _val(inp, "B_rf_ignition_assist_T"), iac[0]["value"] * 1e-3)

    mde = _load(_need("docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"))
    for n in (4, 6, 8):
        cmp(f"u_inst_max_n{n}", _val(inp, f"u_inst_max_n{n}"),
            mde["derived_numbers"]["plan_by_n"][str(n)]["u_inst_max"]["value"])
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    g.add_argument("--verify-pins", action="store_true")
    a = ap.parse_args(argv)
    reg = _load(REGISTER)
    if a.write:
        reg["derived_numbers"]["outputs"] = derive(reg["derived_numbers"]["inputs"])
        with open(REGISTER, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {len(reg['derived_numbers']['outputs'])} derived outputs")
        return 0
    errs = check(reg) if a.check else verify_pins(reg)
    for e in errs:
        print("MISMATCH:", e)
    print("OK" if not errs else f"{len(errs)} mismatch(es)")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
