"""S12 machinery: builder for the O4 disposition matrix (follow-on fo_o4_disposition_matrix, trigger T_O4_DISPOSITION_MATRIX).

WHAT THIS IS. An EVIDENCE matrix for the owner. For every pre-registered O4 staged sensitivity family and every baseline it is
compared against (first stage + escalation combinations) it tabulates, from the frozen scored O4 datasets only:
  trigger_fired, run-level trigger counts by kind (status / dI_d / dT) and by point (N1..N5) and reading (A/B),
  the status transitions, the member / candidate verdict changes (O4 last clause), and an EVIDENCE-ONLY column that
  the owner reads when recording a disposition.
It decides NOTHING. Dispositions are owner decisions (hallthruster_bridge/ensemble/o4_dispositions_schema_v1.json, enforced
by abep_sim/hall_ensemble._check_o4). The builder never writes a disposition, never fills `disposition`, `cleared_for_admission`,
`decided_by` or `decided_utc`, and changes no criterion, tolerance, chemistry, transport parameter or campaign record.
It also never pre-fills a decision hash: `mandatory_decision_sha256` (and any other `*decision_sha256`) of the dispositions
feed stays EMPTY (null) until the owner dispositions are actually made (owner decision 2026-09-27, fo_repo_decisions_batch;
enforced by assert_feed_unbound before the feed is returned).
MILESTONE. Supports Milestone B (physics-backed selection): admission of any Hall transport closure, and hence design Hall
maps, is gated on the O4 dispositions (hall_ensemble._check_o4). Not needed for Milestone A (conditional selection).
All required O4 datasets are scored and the official matrix is built; to reach B it still needs the owner's dispositions recorded,
and (separately) a closure that passes new predictive evidence; the credible set is empty today.

REFUSAL. The official matrix (o4_disposition_matrix_v1.json next to this file) is emitted ONLY when every required O4 dataset
is scored: the five first stages, and every escalation combination of each first stage whose scored trigger fired
(trigger registry T_O4_DISPOSITION_MATRIX: prerequisites + "plus"). Otherwise it raises MatrixRefused listing the missing
dataset ids. `--preview --out PATH` writes a clearly marked PREVIEW over whatever is scored (schema
o4_evidence_matrix_preview_v1); a preview is never the matrix, carries no dispositions feed, and may not be written under a
name containing "disposition" or into the official path.

INPUTS (read-only, repository-relative; every file goes through _read(), which refuses hallthruster_bridge/validation/
interrupted/**; no directory is ever listed, every path is constructed from the registry):
  hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json   (O4 rule, staged_sensitivities, mandatory chemistry)
  hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json           (lock hash)
  hallthruster_bridge/ensemble/o4_dispositions_schema_v1.json    (the dispositions record this matrix feeds)
  docs/orchestration/lane_registry_v1.json                        (datasets: 5 O4 first stages + 13 escalations; ENUMERATION
                                                                   ONLY, see IDENTITY BINDING below)
  docs/orchestration/trigger_registry_v1.json                     (T_O4_DISPOSITION_MATRIX prerequisites; enumeration only)
  docs/orchestration/trigger_ledger_v2.jsonl                      (FIRST VERIFIED record of fo_johnsonlow_escalation_assessment;
                                                                   append-only, so the first record is stable)
  docs/o4/johnsonlow_assessment/johnsonlow_assessment_v1.json     (verified Johnson-low assessment; hash-bound to the datasets)
  hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_*       (mandatory v1 chain)
  hallthruster_bridge/validation/p5_n2_campaign_v1_<manifest>_{raw.jsonl.gz,raw_manifest.json,scores.json,
                                                               scores_provenance.json}   (each registered O4 dataset)
  hallthruster_bridge/propellants/<config>.toml                   (sha256 of the chemistry configs, compared only)
  scripts/score_p5_n2_campaign.py (frozen scorer; imported only after its sha256 equals the provenance value, and used to
                                   recompute every scored staged_escalation block; any difference raises)

IDENTITY BINDING (repair 2026-09-27). provenance.inputs_sha256 binds only IMMUTABLE evidence inputs: the prereg criteria and
lock, the dispositions schema, the frozen scorer and the verified Johnson-low assessment (each scored dataset's raw / scores /
provenance hashes are bound per row in provenance.datasets). The lane and trigger registries are MUTABLE governance files (the
orchestrator records repairs, followon_dir, attempt_history there), so they are never hashed whole: they enumerate the dataset
ids only, and their identity is bound as a canonical projection (O4 dataset {id, manifest, role, escalations}; the
T_O4_DISPOSITION_MATRIX {id, prerequisites, plus}). Editing any other registry field leaves the matrix byte-identical.
The builder NEVER reads an owner o4_dispositions record (hallthruster_bridge/ensemble/o4_dispositions*.json other than the
schema); guard() refuses it, and the feed stays an unbound skeleton.

Usage:
  python docs/o4/disposition_matrix/build_o4_disposition_matrix.py              # official matrix, or refusal (exit 2)
  python docs/o4/disposition_matrix/build_o4_disposition_matrix.py --check      # official file reproduces byte for byte
  python docs/o4/disposition_matrix/build_o4_disposition_matrix.py --status     # which required datasets are scored
  python docs/o4/disposition_matrix/build_o4_disposition_matrix.py --preview --out /tmp/x/o4_evidence_preview.json
"""
import collections
import gzip
import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OFFICIAL_NAME = "o4_disposition_matrix_v1.json"
SCHEMA = "o4_disposition_matrix_v1"
PREVIEW_SCHEMA = "o4_evidence_matrix_preview_v1"
CAMPAIGN = "p5_n2_campaign_v1"
TRIGGER = "T_O4_DISPOSITION_MATRIX"
FOLLOW_ON = "fo_o4_disposition_matrix"
JLA_FOLLOW_ON = "fo_johnsonlow_escalation_assessment"
JLA_SENS = "n2_n_exc_johnsonlow.toml"
DISPOSITIONS_SCHEMA_NAME = "o4_dispositions_schema_v1.json"
POINTS = ["N1", "N2", "N3", "N4", "N5"]
READINGS = ("A", "B")
KINDS = ("status", "dI_d", "dT")
STATUS_WORDS = ("PASS", "FAIL_VALIDATION", "OUT_OF_DOMAIN", "NUMERICAL_FAILURE")

ACCESS_LOG = []          # every path the builder read in this process (tests check that interrupted/** never appears)


class MatrixRefused(Exception):
    """The official matrix is refused: a required O4 dataset is not scored (or its requirement cannot yet be determined)."""

    def __init__(self, missing, undetermined):
        self.missing, self.undetermined = list(missing), list(undetermined)
        super().__init__("official O4 disposition matrix REFUSED: required O4 datasets not scored: "
                         + ", ".join(self.missing)
                         + ("" if not self.undetermined else
                            "; requirement undetermined until their first stage is scored: " + ", ".join(self.undetermined)))


class ProvenanceError(Exception):
    """A hash binding, reproduction or registry consistency check failed (no silent fallback)."""


# ------------------------------------------------------------------------------------------------------------------ file access
class Paths:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.br = os.path.join(self.root, "hallthruster_bridge")
        self.val = os.path.join(self.br, "validation")
        self.interrupted = os.path.join(self.val, "interrupted")
        self.orch = os.path.join(self.root, "docs", "orchestration")
        self.ensemble = os.path.join(self.br, "ensemble")
        self.jla = os.path.join(self.root, "docs", "o4", "johnsonlow_assessment", "johnsonlow_assessment_v1.json")
        self.scorer = os.path.join(self.root, "scripts", "score_p5_n2_campaign.py")
        self.official = os.path.join(self.root, "docs", "o4", "disposition_matrix", OFFICIAL_NAME)

    def rel(self, p):
        return os.path.relpath(p, self.root).replace(os.sep, "/")

    def dataset(self, manifest):
        base = os.path.join(self.val, f"{CAMPAIGN}_{manifest}")
        return {"raw": base + "_raw.jsonl.gz", "manifest": base + "_raw_manifest.json",
                "scores": base + "_scores.json", "provenance": base + "_scores_provenance.json"}


def guard(paths, p):
    """Refuse any path inside hallthruster_bridge/validation/interrupted/ (attempt-1 outputs are never evidence)."""
    a = os.path.abspath(p)
    if a == paths.interrupted or a.startswith(paths.interrupted + os.sep) or \
            os.path.realpath(a).startswith(os.path.realpath(paths.interrupted) + os.sep):
        raise ProvenanceError(f"refused to read interrupted output {paths.rel(a)}")
    b = os.path.basename(a)
    if os.path.dirname(os.path.realpath(a)) == os.path.realpath(paths.ensemble) and b.startswith("o4_dispositions") \
            and b != DISPOSITIONS_SCHEMA_NAME:
        raise ProvenanceError(f"refused to read owner dispositions record {paths.rel(a)}; the feed stays unbound")
    return a


def _read(paths, p):
    a = guard(paths, p)
    ACCESS_LOG.append(a)
    with open(a, "rb") as f:
        return f.read()


def _json(paths, p):
    return json.loads(_read(paths, p).decode())


def _sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _sha(paths, p):
    return _sha_bytes(_read(paths, p))


# --------------------------------------------------------------------------------------------------------------------- registry
def _canonical_sha(obj):
    return _sha_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


REGISTRY_PROJECTION_KEYS = ("id", "manifest", "role", "escalations")


def registry_projection(paths):
    """Canonical projection of the lane registry used as its identity: the O4 datasets' {id, manifest, role, escalations}
    only (never followon_dir, attempt_history, repairs or any lane/follow-on field)."""
    reg = _json(paths, os.path.join(paths.orch, "lane_registry_v1.json"))
    ds = [{k: d.get(k) for k in REGISTRY_PROJECTION_KEYS}
          for d in reg["datasets"] if str(d.get("role", "")).startswith("O4 ")]
    return reg, sorted(ds, key=lambda d: d["id"])


def registry(paths, crit):
    """The 18 registered O4 datasets, cross-checked against the pre-registered staged_sensitivities."""
    reg, _ = registry_projection(paths)
    ds = {d["id"]: d for d in reg["datasets"] if str(d.get("role", "")).startswith("O4 ")}
    staged = crit["staged_sensitivities"]
    fams = []
    seen = set()
    for sens, spec in staged.items():
        stem = sens[:-len(".toml")]
        fid = f"ds_staged_{stem}"
        d = ds.get(fid)
        if d is None or d.get("manifest") != f"staged_{stem}" or d.get("role") != "O4 first stage":
            raise ProvenanceError(f"registry has no O4 first stage {fid} for pre-registered {sens}")
        seen.add(fid)
        escs = []
        for prim, esc in spec["escalation"].items():
            eid = f"ds_escalation_{esc[:-len('.toml')]}"
            e = ds.get(eid)
            if e is None or e.get("manifest") != f"escalation_{esc[:-len('.toml')]}" or e.get("role") != f"O4 escalation of {fid}":
                raise ProvenanceError(f"registry has no O4 escalation {eid} of {fid}")
            escs.append({"id": eid, "config": esc, "baseline": prim, "manifest": e["manifest"],
                         "attempt_history": e.get("attempt_history", [])})
            seen.add(eid)
        if sorted(x["id"] for x in escs) != sorted(d.get("escalations", [])):
            raise ProvenanceError(f"registry escalations of {fid} differ from the pre-registration")
        fams.append({"sensitivity": sens, "first_stage": {"id": fid, "config": sens, "baseline": spec["baseline"],
                                                          "manifest": d["manifest"]}, "escalations": escs})
    extra = sorted(set(ds) - seen)
    if extra:
        raise ProvenanceError(f"registry O4 datasets not in the pre-registration: {extra}")
    return fams


def trigger_prerequisites(paths):
    tr = _json(paths, os.path.join(paths.orch, "trigger_registry_v1.json"))
    items = tr["triggers"] if isinstance(tr, dict) and "triggers" in tr else tr
    for t in (items if isinstance(items, list) else items.values()):
        if isinstance(t, dict) and t.get("id") == TRIGGER:
            return t
    raise ProvenanceError(f"{TRIGGER} not found in the trigger registry")


# ------------------------------------------------------------------------------------------------------------ verification
def load_mandatory(paths, checks):
    lock_p = os.path.join(paths.br, "prereg", "p5_n2_prereg_lock_v1.json")
    mman_p = os.path.join(paths.val, f"{CAMPAIGN}_vacuum_raw_manifest.json")
    mprov_p = os.path.join(paths.val, f"{CAMPAIGN}_vacuum_scores_provenance.json")
    dec_p = os.path.join(paths.val, f"{CAMPAIGN}_vacuum_scores_decision.json")
    mman, mprov = _json(paths, mman_p), _json(paths, mprov_p)
    raw = gzip.decompress(_read(paths, os.path.join(paths.br, mman["dataset"])))
    lock_sha = _sha(paths, lock_p)
    dec = _json(paths, dec_p)

    def chk(name, ok):
        checks.append({"check": name, "ok": bool(ok)})
        if not ok:
            raise ProvenanceError("provenance check failed: " + name)

    chk("mandatory raw canonical sha256 == its freeze manifest", _sha_bytes(raw) == mman["sha256_canonical_jsonl"])
    chk("mandatory provenance input == freeze manifest", mprov["input_sha256_canonical_jsonl"] == mman["sha256_canonical_jsonl"])
    chk("mandatory scores sha256 == provenance output_sha256",
        _sha(paths, os.path.join(paths.br, mprov["output"])) == mprov["output_sha256"])
    chk("mandatory prereg lock == current lock", mprov["prereg_lock_sha256"] == lock_sha == mman["prereg_lock_sha256"])
    chk("scorer file sha256 == mandatory provenance scorer_sha256", _sha(paths, paths.scorer) == mprov["scorer_sha256"])
    chk("mandatory decision bound to the mandatory scores", dec.get("source_scores_sha256") == mprov["output_sha256"])
    recs = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    return {"records": recs, "prov": mprov, "prov_path": mprov_p, "lock_sha": lock_sha,
            "decision_path": dec_p, "decision_sha256": _sha(paths, dec_p),
            "row": {"dataset": "mandatory v1 vacuum", "raw_sha256_canonical": mman["sha256_canonical_jsonl"],
                    "scores": mprov["output"], "scores_sha256": mprov["output_sha256"], "provenance": paths.rel(mprov_p),
                    "provenance_sha256": _sha(paths, mprov_p), "n_records": mman["n_records"]}}


def dataset_state(paths, manifest):
    """SCORED iff its scores-provenance manifest is present (lane registry terminal_states.campaign_dataset); a partial file
    set is an error, never 'missing'."""
    fp = paths.dataset(manifest)
    present = {k: os.path.isfile(guard(paths, p)) for k, p in fp.items()}
    if all(present.values()):
        return "SCORED"
    if not any(present[k] for k in ("scores", "provenance")):
        return "MISSING"
    raise ProvenanceError(f"{manifest}: inconsistent frozen file set {present}")


def verify_dataset(paths, entry, sens, mand, scorer, checks):
    """All hash bindings of one scored O4 dataset, then recompute its staged_escalation block with the frozen scorer."""
    fp = paths.dataset(entry["manifest"])
    man, prov = _json(paths, fp["manifest"]), _json(paths, fp["provenance"])
    gz = _read(paths, fp["raw"])
    raw = gzip.decompress(gz)
    scores_bytes = _read(paths, fp["scores"])
    s_ch, b_ch, tag = entry["config"], entry["baseline"], entry["id"]

    def chk(name, ok):
        checks.append({"check": f"{tag}: {name}", "ok": bool(ok)})
        if not ok:
            raise ProvenanceError(f"provenance check failed: {tag}: {name}")

    chk("raw gz sha256 == freeze manifest", _sha_bytes(gz) == man.get("sha256_gz", _sha_bytes(gz)))
    chk("raw canonical sha256 == freeze manifest", _sha_bytes(raw) == man["sha256_canonical_jsonl"])
    chk("freeze manifest names this raw file", os.path.join(paths.br, man["dataset"]) == fp["raw"])
    chk("provenance input == freeze manifest", prov["input_sha256_canonical_jsonl"] == man["sha256_canonical_jsonl"])
    chk("provenance output names this scores file", os.path.join(paths.br, prov["output"]) == fp["scores"])
    chk("scores sha256 == provenance output_sha256", _sha_bytes(scores_bytes) == prov["output_sha256"])
    chk("mode is vacuum", prov.get("mode") == "vacuum" and man.get("mode") == "vacuum")
    chk("mandatory_reproduced is true", prov.get("mandatory_reproduced") is True)
    chk("bound to the mandatory raw dataset", prov["input_mandatory_sha256"] == mand["prov"]["input_sha256_canonical_jsonl"])
    chk("bound to the official mandatory scores", prov["mandatory_scores_sha256"] == mand["prov"]["output_sha256"])
    chk("scorer sha256 == frozen scorer", prov["scorer_sha256"] == mand["prov"]["scorer_sha256"])
    chk("prereg lock == current lock", prov["prereg_lock_sha256"] == mand["lock_sha"] == man["prereg_lock_sha256"])
    chk(f"pre-registered baseline {b_ch}", prov["o4"].get("baseline", prov["o4"].get("compare_with")) == b_ch)
    chk(f"belongs to sensitivity {sens}", s_ch == sens or prov["o4"].get("sensitivity") == sens)
    chk("chemistry config sha256 == pinned propellant file",
        prov["o4"]["chemistry"].get(s_ch) == _sha(paths, os.path.join(paths.br, "propellants", s_ch)))
    scores = json.loads(scores_bytes.decode())
    blk = (scores.get("staged_escalation") or {}).get(s_ch)
    if not isinstance(blk, dict):
        raise ProvenanceError(f"{tag}: no staged_escalation block for {s_ch}")
    chk("block baseline == pre-registered baseline", blk["baseline"] == b_ch)
    chk("provenance o4_trigger_fired == scored block", prov["o4_trigger_fired"].get(s_ch) == blk["trigger_fired"])
    chk("scores mandatory statistics == official mandatory scores (mandatory reproduced)",
        scores.get("candidates") == mand["scores"].get("candidates"))
    recs = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    chk("record count == freeze manifest == block n_runs", len(recs) == man["n_records"] == blk["n_runs"])
    chk("every record carries this chemistry", all(r["chemistry"] == s_ch for r in recs))
    base = [r for r in mand["records"] if r["chemistry"] == b_ch and r["mode"] == "vacuum"]
    rep_fired = json.loads(json.dumps(scorer.escalation(recs, base, s_ch)))
    rep_vc = json.loads(json.dumps(scorer.verdict_change(recs, mand["records"], b_ch)))
    chk("frozen scorer reproduces run_level_triggers", rep_fired == blk["run_level_triggers"])
    chk("frozen scorer reproduces verdict_changes", rep_vc == blk["verdict_changes"])
    chk("trigger_fired == (any run-level trigger or verdict change)", blk["trigger_fired"] == bool(rep_fired or rep_vc))
    return {"block": blk, "records": recs,
            "provenance_ref": {"scores_provenance_file": paths.rel(fp["provenance"])[len("hallthruster_bridge/"):],
                               "scores_provenance_sha256": _sha(paths, fp["provenance"])},
            "row": {"dataset": entry["manifest"], "dataset_id": tag, "config": s_ch, "baseline": b_ch,
                    "raw_sha256_canonical": man["sha256_canonical_jsonl"], "raw_sha256_gz": _sha_bytes(gz),
                    "scores": prov["output"], "scores_sha256": prov["output_sha256"], "provenance": paths.rel(fp["provenance"]),
                    "provenance_sha256": _sha(paths, fp["provenance"]), "n_records": man["n_records"],
                    "mandatory_reproduced": prov["mandatory_reproduced"], "scored_utc": prov.get("scored_utc")}}


def load_scorer(paths, mand):
    if _sha(paths, paths.scorer) != mand["prov"]["scorer_sha256"]:
        raise ProvenanceError("frozen scorer sha256 mismatch; refusing to import it")
    spec = importlib.util.spec_from_file_location("o4m_frozen_scorer", paths.scorer)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_johnsonlow(paths, verified_rows, checks):
    """The verified Johnson-low assessment: ledger VERIFIED event, all its own checks passed, and every dataset it cites has
    exactly the hashes this builder verified."""
    jla = _json(paths, paths.jla)
    ledger = [json.loads(line) for line in _read(paths, os.path.join(paths.orch, "trigger_ledger_v2.jsonl")).decode().splitlines()
              if line.strip()]
    ver = [e for e in ledger if e.get("event") == "VERIFIED" and (e.get("evidence") or {}).get("follow_on") == JLA_FOLLOW_ON]
    # the ledger is append-only: bind the FIRST VERIFIED record so later appends never change the matrix

    def chk(name, ok):
        checks.append({"check": f"johnsonlow assessment: {name}", "ok": bool(ok)})
        if not ok:
            raise ProvenanceError("provenance check failed: johnsonlow assessment: " + name)

    chk("schema johnsonlow_assessment_v1", jla.get("schema") == "johnsonlow_assessment_v1")
    chk("its own provenance checks all passed", jla["provenance"].get("all_checks_passed") is True)
    chk(f"{JLA_FOLLOW_ON} has a VERIFIED ledger event", bool(ver))
    by_ds = {r["dataset"]: r for r in verified_rows}
    cited = [d for d in jla["provenance"]["datasets"] if d["dataset"] != "mandatory v1 vacuum"]
    chk("cites the four Johnson-low datasets", len(cited) == 4)
    for d in cited:
        v = by_ds.get(d["dataset"])
        chk(f"{d['dataset']} is scored and verified here", v is not None)
        chk(f"{d['dataset']} scores/provenance/raw sha256 identical",
            (d["scores_sha256"], d["provenance_sha256"], d["raw_sha256_canonical"]) ==
            (v["scores_sha256"], v["provenance_sha256"], v["raw_sha256_canonical"]))
    return {"file": paths.rel(paths.jla), "sha256": _sha(paths, paths.jla),
            "ledger_verified_commit": (ver[0].get("evidence") or {}).get("commit"), "answer": jla["answer"]}


# ------------------------------------------------------------------------------------------------------------------ tabulation
def parse_trigger(text):
    """('status', 'A', 'OUT_OF_DOMAIN -> FAIL_VALIDATION') | ('dI_d', 'B', None) | ('dT', 'A', None)."""
    if not text.endswith(")") or "(" not in text:
        raise ProvenanceError(f"unparseable run-level trigger {text!r}")
    body, rd = text[:-1].rsplit("(", 1)
    body = body.strip()
    if rd not in READINGS:
        raise ProvenanceError(f"unknown reading in trigger {text!r}")
    if body.startswith("status "):
        tr = body[len("status "):]
        a, _, b = tr.partition(" -> ")
        if a not in STATUS_WORDS or b not in STATUS_WORDS:
            raise ProvenanceError(f"unknown status transition {text!r}")
        return "status", rd, tr
    if body.startswith("dI_d "):
        return "dI_d", rd, None
    if body.startswith("dT "):
        return "dT", rd, None
    raise ProvenanceError(f"unknown trigger kind {text!r}")


def tabulate(v):
    blk, recs = v["block"], v["records"]
    point_of = {r["key"]: r["point"] for r in recs}
    by_kind = {k: 0 for k in KINDS}
    by_kind_reading = {k: {rd: 0 for rd in READINGS} for k in KINDS}
    by_point = {p: {k: 0 for k in KINDS} for p in POINTS}
    transitions = {rd: collections.Counter() for rd in READINGS}
    runs_any, runs_status = set(), set()
    for key, text in blk["run_level_triggers"]:
        if text == "baseline missing":
            raise ProvenanceError(f"{key}: baseline missing in a scored O4 block")
        kind, rd, tr = parse_trigger(text)
        p = point_of.get(key)
        if p not in POINTS:
            raise ProvenanceError(f"{key}: trigger for a run not in the dataset")
        by_kind[kind] += 1
        by_kind_reading[kind][rd] += 1
        by_point[p][kind] += 1
        runs_any.add(key)
        if kind == "status":
            transitions[rd][tr] += 1
            runs_status.add(key)
    vc = blk["verdict_changes"]
    cand = {c: list(x["candidate"]) for c, x in sorted(vc.items()) if x["candidate"][0] != x["candidate"][1]}
    mem = {c: {m: list(t) for m, t in sorted(x["members"].items())} for c, x in sorted(vc.items()) if x["members"]}
    return {"trigger_fired": blk["trigger_fired"], "n_runs": blk["n_runs"],
            "n_run_level_triggers": len(blk["run_level_triggers"]),
            "n_runs_with_any_run_level_trigger": len(runs_any), "n_runs_with_status_change": len(runs_status),
            "trigger_counts": {"by_kind": by_kind, "by_kind_and_reading": by_kind_reading, "by_point": by_point},
            "status_transitions": {rd: dict(sorted(transitions[rd].items())) for rd in READINGS},
            "verdict_changes": {"n_candidates_with_any_change": len(vc), "candidate_verdict_changes": cand,
                                "n_member_verdict_changes": sum(len(x) for x in mem.values()),
                                "member_verdict_changes": mem}}


def evidence_lines(row, t, jla):
    """Facts only, for the owner's EVIDENCE-ONLY column. No recommendation, no disposition."""
    k = t["trigger_counts"]["by_kind"]
    L = [f"O4 trigger_fired = {t['trigger_fired']} against {row['baseline']} (scored block, reproduced by the frozen scorer)",
         f"{t['n_runs_with_any_run_level_trigger']} of {t['n_runs']} runs carry a run-level trigger "
         f"({k['status']} status, {k['dI_d']} dI_d, {k['dT']} dT readings)",
         f"{t['n_runs_with_status_change']} runs change status under at least one reading",
         f"verdict changes: {len(t['verdict_changes']['candidate_verdict_changes'])} candidate-level, "
         f"{t['verdict_changes']['n_member_verdict_changes']} member-level"]
    if jla is not None and row["family"] == JLA_SENS:
        tb = jla["answer"].get("tail_by_baseline", {}).get(row["baseline"])
        L.append(f"Johnson-low assessment ({jla['file']}): mode {jla['answer'].get('mode')}; "
                 f"material_on_every_primary_combination = {jla['answer'].get('material_on_every_primary_combination')}"
                 + ("" if tb is None else f"; this baseline: {tb.get('n_runs_any_trigger')} runs with any trigger, "
                                          f"{tb.get('n_runs_status_changed_across_OOD_boundary')} status changes across the "
                                          f"OUT_OF_DOMAIN boundary"))
    return L


# ----------------------------------------------------------------------------------------------------------------------- build
def requirement(fams, state, fired):
    """Required dataset ids, missing ones, and escalations whose requirement is undetermined (first stage not scored)."""
    required, missing, undetermined, not_required = [], [], [], []
    for f in fams:
        fs = f["first_stage"]["id"]
        required.append(fs)
        if state[fs] != "SCORED":
            missing.append(fs)
            undetermined.extend(e["id"] for e in f["escalations"])
            continue
        for e in f["escalations"]:
            if fired[fs]:
                required.append(e["id"])
                if state[e["id"]] != "SCORED":
                    missing.append(e["id"])
            else:
                not_required.append(e["id"])
    return required, missing, undetermined, not_required


def build(root=DEFAULT_ROOT, preview=False):
    """Return the matrix dict. Raises MatrixRefused (official only) or ProvenanceError."""
    paths = Paths(root)
    checks = []
    crit_p = os.path.join(paths.br, "prereg", "p5_n2_validation_criteria_v1.json")
    schema_p = os.path.join(paths.ensemble, DISPOSITIONS_SCHEMA_NAME)
    lock_p = os.path.join(paths.br, "prereg", "p5_n2_prereg_lock_v1.json")
    crit = _json(paths, crit_p)
    disp_schema = _json(paths, schema_p)
    if disp_schema.get("schema") != "o4_dispositions_v1":
        raise ProvenanceError("dispositions schema is not o4_dispositions_v1")
    fams = registry(paths, crit)
    trig = trigger_prerequisites(paths)
    prereq = sorted(p["id"] for p in trig["prerequisites"])
    if prereq != sorted(f["first_stage"]["id"] for f in fams):
        raise ProvenanceError(f"{TRIGGER} prerequisites differ from the registered first stages")
    for f in fams:
        if not {e["baseline"] for e in f["escalations"]} | {f["first_stage"]["baseline"]} <= set(crit["mandatory_chemistry"]):
            raise ProvenanceError(f"{f['sensitivity']}: a baseline is not a mandatory primary combination")

    entries = [dict(f["first_stage"], family=f["sensitivity"], stage="first_stage") for f in fams] + \
              [dict(e, family=f["sensitivity"], stage="escalation") for f in fams for e in f["escalations"]]
    state = {e["id"]: dataset_state(paths, e["manifest"]) for e in entries}

    mand = load_mandatory(paths, checks)
    mand["scores"] = _json(paths, os.path.join(paths.br, mand["prov"]["output"]))
    scorer = load_scorer(paths, mand)
    verified = {}
    for e in entries:
        if state[e["id"]] == "SCORED":
            verified[e["id"]] = verify_dataset(paths, e, e["family"], mand, scorer, checks)
    fired = {e["id"]: verified[e["id"]]["block"]["trigger_fired"] for e in entries if e["id"] in verified}
    required, missing, undetermined, not_required = requirement(fams, state, fired)
    if not preview and (missing or undetermined):
        raise MatrixRefused(missing, undetermined)

    jla = None
    jla_cited = {"staged_n2_n_exc_johnsonlow"} | {e["manifest"] for f in fams if f["sensitivity"] == JLA_SENS
                                                  for e in f["escalations"]}
    if jla_cited <= {v["row"]["dataset"] for v in verified.values()}:
        jla = verify_johnsonlow(paths, [v["row"] for v in verified.values()], checks)
    elif not preview:
        raise ProvenanceError("Johnson-low assessment datasets not all scored")

    rows = []
    for e in entries:
        row = {"family": e["family"], "stage": e["stage"], "dataset_id": e["id"], "config": e["config"],
               "baseline": e["baseline"], "state": state[e["id"]],
               "required": (True if e["id"] in required else "UNDETERMINED" if e["id"] in undetermined else False)}
        if e.get("attempt_history"):
            row["attempt_history_note"] = "earlier attempts are not evidence; only the scored dataset named here is read"
        if e["id"] in verified:
            t = tabulate(verified[e["id"]])
            row.update(t)
            row["scored_block_reproduced_by_frozen_scorer"] = True
            row["scores_provenance"] = verified[e["id"]]["provenance_ref"]
            row["evidence_only_for_owner"] = evidence_lines(row, t, jla)
        else:
            row["evidence_only_for_owner"] = ["not scored: no evidence available for this combination"]
        row["owner_disposition"] = None
        rows.append(row)

    families = {}
    for f in fams:
        fs = f["first_stage"]["id"]
        fr = [r for r in rows if r["family"] == f["sensitivity"]]
        families[f["sensitivity"]] = {
            "baseline": f["first_stage"]["baseline"],
            "first_stage_dataset": fs,
            "first_stage_trigger_fired": fired.get(fs),
            "escalations_required": [e["id"] for e in f["escalations"] if e["id"] in required],
            "escalations_missing": [e["id"] for e in f["escalations"] if e["id"] in missing or e["id"] in undetermined],
            "combinations_with_trigger_fired": sorted(r["baseline"] for r in fr if r.get("trigger_fired") is True),
            "combinations_scored": sorted(r["baseline"] for r in fr if r["state"] == "SCORED"),
            "all_required_scored": not any(r["dataset_id"] in missing or r["dataset_id"] in undetermined for r in fr),
            "owner_disposition": None}

    rule = crit["operational_rules"]["O4_staged_escalation"]
    out = {
        "schema": PREVIEW_SCHEMA if preview else SCHEMA,
        "campaign_id": CAMPAIGN, "trigger": TRIGGER, "follow_on": FOLLOW_ON,
        "status_of_this_document": (
            "PREVIEW over the currently scored O4 datasets; NOT the O4 matrix and not a disposition record; never committed"
            if preview else
            "evidence matrix for the owner; decides nothing; every owner_disposition is null and is recorded only by the owner "
            "in an o4_dispositions_v1 file; no criterion, tolerance, chemistry or transport change; the v1 result is unchanged"),
        "o4_rule": {"first_run": rule["first_run"], "triggers": rule["escalate_to_other_three_primary_combinations_if_any_vacuum"],
                    "facility": rule["facility"]},
        "required_datasets": {"required": required, "missing": missing, "undetermined": undetermined,
                              "not_required_trigger_not_fired": not_required,
                              "scored": sorted(i for i, s in state.items() if s == "SCORED")},
        "families": families, "rows": rows,
        "johnsonlow_assessment": None if jla is None else {k: jla[k] for k in ("file", "sha256", "ledger_verified_commit")},
        "provenance": {"all_checks_passed": all(c["ok"] for c in checks), "n_checks": len(checks), "checks": checks,
                       "datasets": [mand["row"]] + [verified[e["id"]]["row"] for e in entries if e["id"] in verified],
                       "inputs_sha256": {paths.rel(crit_p): _sha(paths, crit_p), paths.rel(schema_p): _sha(paths, schema_p),
                                         paths.rel(paths.scorer): _sha(paths, paths.scorer),
                                         paths.rel(lock_p): _sha(paths, lock_p),
                                         **({} if jla is None else {jla["file"]: jla["sha256"]})},
                       "registry_identity": {
                           "note": ("mutable governance files are never hashed whole; only these canonical projections "
                                    "(sorted keys, compact JSON) bind their identity"),
                           "lane_registry_o4_datasets_projection_keys": list(REGISTRY_PROJECTION_KEYS),
                           "lane_registry_o4_datasets_projection_sha256": _canonical_sha(registry_projection(paths)[1]),
                           "trigger_projection_keys": ["id", "prerequisites", "plus"],
                           "trigger_projection_sha256": _canonical_sha(
                               {k: trig.get(k) for k in ("id", "prerequisites", "plus")})}},
    }
    if preview:
        out["PREVIEW"] = True
        out["missing_required_datasets"] = missing + undetermined
    else:
        out["o4_dispositions_feed"] = dispositions_feed(fams, verified, required, mand, paths)
    return out


def dispositions_feed(fams, verified, required, mand, paths):
    """Skeleton conforming to o4_dispositions_v1 with every OWNER field left empty (disposition None, cleared_for_admission
    empty, decided_by / decided_utc None). abep_sim.hall_ensemble._check_o4 rejects it until the owner fills them."""
    sens = {}
    for f in fams:
        fs = f["first_stage"]["id"]
        ent = {"baseline": f["first_stage"]["baseline"], "first_stage": verified[fs]["provenance_ref"],
               "trigger_fired": verified[fs]["block"]["trigger_fired"], "disposition": None}
        if ent["trigger_fired"]:
            ent["escalations"] = {e["config"]: verified[e["id"]]["provenance_ref"] for e in f["escalations"]
                                  if e["id"] in required}
        sens[f["sensitivity"]] = ent
    feed = {"schema": "o4_dispositions_v1", "campaign_id": CAMPAIGN,
            "mandatory_decision_sha256": None,
            "mandatory_decision_file": paths.rel(mand["decision_path"]),
            "sensitivities": sens, "cleared_for_admission": [], "decided_by": None, "decided_utc": None,
            "owner_fills": ["sensitivities.*.disposition", "cleared_for_admission", "decided_by", "decided_utc",
                            "mandatory_decision_sha256 (left empty by the builder; the owner binds it when the dispositions "
                            "are actually made, and it must equal the decision_sha256 of the record that cites this file)"]}
    assert_feed_unbound(feed)
    return feed


# Owner decision 2026-09-27 (fo_repo_decisions_batch): every decision-hash field of the feed stays EMPTY until the owner
# dispositions are actually made. The builder never pre-fills one, so an unfilled template can never look bound to a decision.
DECISION_HASH_FIELDS = ("mandatory_decision_sha256",)
OWNER_FIELDS_EMPTY = {"cleared_for_admission": [], "decided_by": None, "decided_utc": None}


def assert_feed_unbound(feed):
    """Raise ProvenanceError if the builder's feed carries any owner-filled value: a decision hash (any key ending in
    'decision_sha256' at any depth, plus DECISION_HASH_FIELDS), a disposition, a clearance, or decided_by / decided_utc."""
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                p = f"{path}.{k}" if path else k
                if (k in DECISION_HASH_FIELDS or k.endswith("decision_sha256")) and v not in (None, ""):
                    raise ProvenanceError(f"dispositions feed pre-fills decision hash {p}; it stays empty until the owner decides")
                walk(v, p)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
    for k in DECISION_HASH_FIELDS:
        if k not in feed:
            raise ProvenanceError(f"dispositions feed lacks the (empty) owner field {k}")
    walk(feed, "")
    for k, empty in OWNER_FIELDS_EMPTY.items():
        if feed.get(k) != empty:
            raise ProvenanceError(f"dispositions feed pre-fills owner field {k}")
    for s, e in (feed.get("sensitivities") or {}).items():
        if e.get("disposition") is not None:
            raise ProvenanceError(f"dispositions feed pre-fills the disposition of {s}")


def dumps(obj):
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def write_preview(obj, out, root=DEFAULT_ROOT):
    paths = Paths(root)
    a = os.path.abspath(out)
    if "disposition" in os.path.basename(a).lower() or a == paths.official:
        raise ValueError("a preview is never named as a disposition or written to the official matrix path")
    if obj.get("schema") != PREVIEW_SCHEMA or obj.get("PREVIEW") is not True:
        raise ValueError("only a PREVIEW object may be written by write_preview")
    os.makedirs(os.path.dirname(a), exist_ok=True)
    with open(a, "w") as f:
        f.write(dumps(obj))
    return a


def main(argv):
    root = DEFAULT_ROOT
    if "--status" in argv:
        m = build(root, preview=True)
        print(dumps(m["required_datasets"]), end="")
        return 0
    if "--preview" in argv:
        if "--out" not in argv:
            print("--preview needs --out PATH (never the official matrix path)", file=sys.stderr)
            return 2
        p = write_preview(build(root, preview=True), argv[argv.index("--out") + 1], root)
        print("wrote PREVIEW", p)
        return 0
    try:
        js = dumps(build(root))
    except MatrixRefused as e:
        print(str(e), file=sys.stderr)
        return 2
    paths = Paths(root)
    if "--check" in argv:
        ok = os.path.isfile(paths.official) and open(paths.official).read() == js
        print("CHECK", "OK" if ok else "MISMATCH")
        return 0 if ok else 1
    with open(paths.official, "w") as f:
        f.write(js)
    print("wrote", paths.rel(paths.official))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
