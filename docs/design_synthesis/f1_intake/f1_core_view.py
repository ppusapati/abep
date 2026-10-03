"""Standard-library-only reader of the F1 compact core view (f1_intake_synthesis_v1_core.json; A9.22 item 9).

For consumers that must not import abep_sim (F9 build_freeze_candidate.py). It mirrors
abep_sim.design.intake_synthesis.expand_core exactly (tests/test_design_f1_intake.py checks both give the same view of
the committed core file); the encoder and the canonical definition live in intake_synthesis.
"""
from __future__ import annotations

CORE_SCHEMA = "f1_intake_synthesis_v1_core"
RECORD_SPECIES_FIELDS = ("mdot_fwd_kgps", "mdot_fwd_se_kgps", "p_passive_Pa", "p_passive_se_Pa", "K_back")


def expand_core(core: dict) -> dict:
    if core.get("schema") != CORE_SCHEMA:
        raise RuntimeError(f"not an F1 core view: schema {core.get('schema')!r}")
    enc = core["encoded"]
    states = enc["states"]
    nf = len(RECORD_SPECIES_FIELDS)
    out = {}
    for k in core["key_order"]:
        if k == "if_a1_interface":
            e = enc[k]
            recs = [{"candidate": e["candidates"][r[0]], "state": states[r[1]], "scenario": e["scenarios"][r[2]],
                     "theta_deg": r[3],
                     "species": {s: dict(zip(RECORD_SPECIES_FIELDS, r[6 + j * nf:6 + (j + 1) * nf]))
                                 for j, s in enumerate(e["species"])},
                     "T_K": r[4], "converged": r[5]} for r in e["rows"]]
            out[k] = {kk: (recs if kk == "records_per_unit_area" else e["verbatim"][kk]) for kk in e["key_order"]}
        elif k == "species_table":
            e = enc[k]
            i = e["columns"].index("source")
            out[k] = {"columns": list(e["columns"]),
                      "rows": [[states[r[0]]] + r[1:i] + [e["sources"][r[i]]] + r[i + 1:] for r in e["rows"]]}
        elif k == "infeasible_reasons":
            e = enc[k]
            env = {}
            for sc, blk in e["envelope"].items():
                lists = [[x if isinstance(x, str) else f"C-DRAG-RFP at {states[x[0]]}: {x[1]} mN" for x in g]
                         for g in blk["reason_lists"]]
                env[sc] = {cid: list(lists[gi]) for cid, gi in blk["candidates"]}
            out[k] = {kk: (env if kk == "envelope" else e["verbatim"][kk]) for kk in e["key_order"]}
        else:
            out[k] = core["verbatim"][k]
    return out
