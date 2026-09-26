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
                    "scores_provenance_file", "scores_provenance_sha256", "passing_layer1_members", "admitted_utc", "decided_by",
                    "o4_dispositions_file", "o4_dispositions_sha256")


def _sha_ok(path: str, sha) -> bool:
    import hashlib
    return bool(sha) and os.path.isfile(path) and hashlib.sha256(open(path, "rb").read()).hexdigest() == sha


def _o4_result(mid: str, ref, chem: str, bridge_dir: str, mandatory_prov: dict) -> bool:
    """A scored O4 dataset (scripts/score_p5_n2_staged.py): provenance and scores files verified, scored against the SAME
    mandatory dataset and scores as the admission; returns the scorer's trigger_fired for `chem`."""
    if not isinstance(ref, dict):
        raise ValueError(f"admitted member {mid}: no scored O4 result recorded for {chem}")
    pp = os.path.join(bridge_dir, ref.get("scores_provenance_file") or "")
    if not _sha_ok(pp, ref.get("scores_provenance_sha256")):
        raise ValueError(f"admitted member {mid}: O4 provenance for {chem} missing or its sha256 does not match")
    prov = json.load(open(pp))
    if prov.get("mode") != "vacuum" or not mandatory_prov.get("input_sha256_canonical_jsonl") \
            or prov.get("input_mandatory_sha256") != mandatory_prov.get("input_sha256_canonical_jsonl") \
            or prov.get("mandatory_scores_sha256") != mandatory_prov.get("output_sha256"):
        raise ValueError(f"admitted member {mid}: O4 result for {chem} is not scored against this admission's mandatory dataset")
    sp = os.path.join(bridge_dir, prov.get("output") or "")
    if not _sha_ok(sp, prov.get("output_sha256")):
        raise ValueError(f"admitted member {mid}: O4 scores file for {chem} missing or modified")
    ev = (json.load(open(sp)).get("staged_escalation") or {}).get(chem)
    if not isinstance(ev, dict) or not isinstance(ev.get("trigger_fired"), bool):
        raise ValueError(f"admitted member {mid}: O4 scores contain no trigger evaluation for {chem}")
    return ev["trigger_fired"]


def _check_o4(mid: str, adm: dict, bridge_dir: str, mandatory_prov: dict) -> None:
    """Owner decision 2026-09-26: a PROMOTABLE mandatory-vacuum result alone never admits a member (nor enables design Hall
    maps). Every pre-registered O4 staged sensitivity must have been run and scored, every escalation its trigger requires must
    have been run and scored, and each must carry a recorded owner disposition (ensemble/o4_dispositions_schema_v1.json).
    The trigger values are read from the scored files, never from the disposition record."""
    p = os.path.join(bridge_dir, adm["o4_dispositions_file"])
    if not _sha_ok(p, adm["o4_dispositions_sha256"]):
        raise ValueError(f"admitted member {mid}: O4 dispositions file missing or its sha256 does not match")
    d = json.load(open(p))
    if d.get("schema") != "o4_dispositions_v1" or d.get("mandatory_decision_sha256") != adm["decision_sha256"]:
        raise ValueError(f"admitted member {mid}: O4 dispositions are not bound to this admission's decision")
    crit_path = os.path.join(bridge_dir, adm["preregistration"])
    staged = json.load(open(crit_path)).get("staged_sensitivities") if os.path.isfile(crit_path) else None
    if not staged:
        raise ValueError(f"admitted member {mid}: pre-registration {adm['preregistration']} declares no staged sensitivities")
    ents = d.get("sensitivities") or {}
    for sens, spec in staged.items():
        e = ents.get(sens)
        if not isinstance(e, dict) or e.get("baseline") != spec["baseline"] or not isinstance(e.get("trigger_fired"), bool):
            raise ValueError(f"admitted member {mid}: O4 disposition for {sens} missing or not against its baseline")
        fired = _o4_result(mid, e.get("first_stage"), sens, bridge_dir, mandatory_prov)
        if fired != e["trigger_fired"]:
            raise ValueError(f"admitted member {mid}: recorded O4 trigger for {sens} differs from the scored evaluation")
        if fired:
            for combo in spec["escalation"].values():
                _o4_result(mid, (e.get("escalations") or {}).get(combo), combo, bridge_dir, mandatory_prov)
        if not str(e.get("disposition") or "").strip():
            raise ValueError(f"admitted member {mid}: no owner disposition recorded for {sens}")
    if mid not in (d.get("cleared_for_admission") or []) or not d.get("decided_by") or not d.get("decided_utc"):
        raise ValueError(f"admitted member {mid}: not cleared for admission by a recorded O4 disposition")


def _check_admission(member: dict, bridge_dir: str) -> None:
    """An admitted member must carry an admission record (ensemble/admission_record_schema_v1.json) that is verifiable offline:
    the decision and scores-provenance files exist and match their sha256, and the decision lists the member as PROMOTABLE with
    the recorded passing layer-1 members; and the O4 staged sensitivities (plus any triggered escalations) are scored and
    dispositioned (_check_o4)."""
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
    _check_o4(mid, adm, bridge_dir, prov)


def require_admitted(member_id: str, ensemble: dict | None = None) -> None:
    """Gate for any Hall-map generator: refuse screening candidates and unknown ids. Admitted members have passed
    _check_admission, including the O4 dispositions: a mandatory-vacuum PROMOTABLE result alone never enables design maps."""
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
