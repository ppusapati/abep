"""Two-layer Hall uncertainty structure (hallthruster_bridge/ensemble/transport_ensemble_v0.json).

Layer 1, calibration nuisance: P5 registration, coil shape, beam-efficiency reading, facility-ingestion interpretation.
It describes uncertainty in the P5 *evidence*, is marginalized when admitting closures, and must never appear as a
Vyovrinda design variable or an architecture-trade dimension.
Layer 2, transferable: the credible set of transport closures (unweighted scenarios). Each Hall map is produced by exactly
one member, on Vyovrinda's own geometry and B(z), and names it in meta.ensemble_member_id.
"""
from __future__ import annotations
import json, os

ENSEMBLE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hallthruster_bridge", "ensemble",
                             "transport_ensemble_v0.json")


def load_ensemble(path: str = ENSEMBLE_FILE) -> dict:
    e = json.load(open(path))
    if e.get("schema") != "transport_ensemble_v0":
        raise ValueError(f"{path} is not transport_ensemble_v0")
    if e.get("weighting") != "unweighted":
        raise ValueError("members must stay unweighted until evidence-based weighting is justified and logged")
    nuisance = set(e["calibration_nuisance"])
    ids = set()
    for m in e["members"]:
        missing = [f for f in e["member_fields"] if f not in m]
        if missing:
            raise ValueError(f"ensemble member {m.get('ensemble_member_id')} missing fields {missing}")
        if m["ensemble_member_id"] in ids:
            raise ValueError(f"duplicate ensemble_member_id {m['ensemble_member_id']}")
        ids.add(m["ensemble_member_id"])
        leaked = nuisance & set(m["transport_parameters"])
        if leaked:     # calibration nuisance must stay provenance, never a transport/design parameter
            raise ValueError(f"member {m['ensemble_member_id']}: calibration nuisance {sorted(leaked)} used as a parameter")
        unknown = set(m["calibration_hypotheses"]) - nuisance
        if unknown:
            raise ValueError(f"member {m['ensemble_member_id']}: unknown calibration hypotheses {sorted(unknown)}")
    if e["members"] and e.get("admission_rule") is None:
        raise ValueError("members present but no admission_rule recorded")
    return e


def member_ids(ensemble: dict | None = None) -> set[str]:
    e = ensemble if ensemble is not None else load_ensemble()
    return {m["ensemble_member_id"] for m in e["members"]}
