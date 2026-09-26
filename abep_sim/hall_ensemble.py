"""Two-layer Hall uncertainty structure (hallthruster_bridge/ensemble/transport_ensemble_v0.json).

Layer 1, calibration nuisance: P5 registration, coil shape, beam-efficiency reading, facility-ingestion interpretation.
It describes uncertainty in the P5 *evidence*, is marginalized when admitting closures, and must never appear as a
Vyovrinda design variable or an architecture-trade dimension.
Layer 2, transferable: the credible set of transport closures (unweighted scenarios; EMPTY as of 2026-09-26). Screening
candidates are a separate list of hypotheses for new evidence to test; they never produce design Hall maps. Each Hall map is produced by exactly
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
    nuisance = e["calibration_nuisance"]
    ids = set()
    for m in e["members"] + e.get("screening_candidates", []):
        missing = [f for f in e["member_fields"] if f not in m]
        if missing:
            raise ValueError(f"ensemble member {m.get('ensemble_member_id')} missing fields {missing}")
        if m["ensemble_member_id"] in ids:
            raise ValueError(f"duplicate ensemble_member_id {m['ensemble_member_id']}")
        ids.add(m["ensemble_member_id"])
        leaked = set(nuisance) & set(m["transport_parameters"])
        if leaked:     # calibration nuisance must stay provenance, never a transport/design parameter
            raise ValueError(f"member {m['ensemble_member_id']}: calibration nuisance {sorted(leaked)} used as a parameter")
        for hyp in m["calibration_hypotheses"]:     # each: {nuisance variable: declared value}
            unknown = set(hyp) - set(nuisance)
            if unknown:
                raise ValueError(f"member {m['ensemble_member_id']}: unknown calibration hypotheses {sorted(unknown)}")
            bad = {k: v for k, v in hyp.items() if v not in nuisance[k]["values"]}
            if bad:
                raise ValueError(f"member {m['ensemble_member_id']}: undeclared nuisance values {bad}")
    if e["members"] and e.get("admission_rule") is None:
        raise ValueError("members present but no admission_rule recorded")
    screening = {m["ensemble_member_id"] for m in e.get("screening_candidates", [])}
    for m in e["members"]:
        _check_admission(m, os.path.dirname(os.path.dirname(os.path.abspath(path))))
        if m["ensemble_member_id"] in screening:
            raise ValueError(f"{m['ensemble_member_id']} is listed both as admitted member and as screening candidate")
    return e


ADMISSION_FIELDS = ("promoted_from_screening_id", "campaign_id", "preregistration", "decision_file", "decision_sha256",
                    "scores_provenance_file", "scores_provenance_sha256", "passing_layer1_members", "admitted_utc", "decided_by")


def _check_admission(member: dict, bridge_dir: str) -> None:
    """An admitted member must carry an admission record (ensemble/admission_record_schema_v1.json) that is verifiable offline:
    the decision and scores-provenance files exist and match their sha256, and the decision lists the member as PROMOTABLE with
    the recorded passing layer-1 members."""
    import hashlib
    mid, adm = member["ensemble_member_id"], member.get("admission")
    if not isinstance(adm, dict):
        raise ValueError(f"admitted member {mid} has no admission record (evidence-based promotion only)")
    missing = [f for f in ADMISSION_FIELDS if f not in adm]
    if missing:
        raise ValueError(f"admitted member {mid}: admission record missing {missing}")
    if adm["promoted_from_screening_id"] != mid:
        raise ValueError(f"admitted member {mid}: promoted_from_screening_id {adm['promoted_from_screening_id']!r} differs")
    for f in ("decision", "scores_provenance"):
        p = os.path.join(bridge_dir, adm[f + "_file"])
        if not os.path.isfile(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != adm[f + "_sha256"]:
            raise ValueError(f"admitted member {mid}: {f} file missing or its sha256 does not match")
    dec = json.load(open(os.path.join(bridge_dir, adm["decision_file"])))
    prov = json.load(open(os.path.join(bridge_dir, adm["scores_provenance_file"])))
    if not dec.get("source_scores_sha256") or dec["source_scores_sha256"] != prov.get("output_sha256"):
        raise ValueError(f"admitted member {mid}: decision is not bound to the scores output named by the provenance manifest")
    scores = os.path.join(bridge_dir, prov.get("output") or "")
    if not prov.get("output") or not os.path.isfile(scores) or \
            hashlib.sha256(open(scores, "rb").read()).hexdigest() != prov["output_sha256"]:
        raise ValueError(f"admitted member {mid}: the scores file named by the provenance manifest is missing or modified")
    if dec.get("candidates", {}).get(mid) != "PROMOTABLE":
        raise ValueError(f"admitted member {mid}: the referenced decision does not list it as PROMOTABLE")
    passing = set(dec.get("passing_members", {}).get(mid, []))
    if not adm["passing_layer1_members"] or not set(adm["passing_layer1_members"]) <= passing:
        raise ValueError(f"admitted member {mid}: passing_layer1_members not supported by the decision")


def require_admitted(member_id: str, ensemble: dict | None = None) -> None:
    """Gate for any Hall-map generator: refuse screening candidates and unknown ids."""
    e = ensemble if ensemble is not None else load_ensemble()
    if member_id in screening_ids(e):
        raise ValueError(f"{member_id} is a SCREENING candidate: screening candidates never produce design Hall maps")
    if member_id not in member_ids(e):
        raise ValueError(f"{member_id} is not an admitted transport-ensemble member")


def member_ids(ensemble: dict | None = None) -> set[str]:
    """ADMITTED members only. Screening candidates are deliberately excluded: they may never produce design Hall maps."""
    e = ensemble if ensemble is not None else load_ensemble()
    return {m["ensemble_member_id"] for m in e["members"]}


def screening_ids(ensemble: dict | None = None) -> set[str]:
    e = ensemble if ensemble is not None else load_ensemble()
    return {m["ensemble_member_id"] for m in e.get("screening_candidates", [])}
