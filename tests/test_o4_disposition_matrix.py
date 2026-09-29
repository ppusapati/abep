"""S12 (docs/o4/disposition_matrix/build_o4_disposition_matrix.py): the committed official O4 disposition matrix reproduces byte
for byte from the frozen scored datasets (all 5 first stages and 13 escalations), every row binds its scores-provenance sha256,
the dispositions feed stays unbound (every owner field and every *decision_sha256 empty), and the owner review
(O4_DISPOSITION_MATRIX_REVIEW.md) carries exactly the tables regenerated from the matrix by review_tables() below. The builder
still refuses the official matrix on a synthetic root with unscored required datasets, every hash binding is verified, interrupted attempt-1 outputs are never read, the preview totals
reproduce the scored staged_escalation blocks, the dispositions feed conforms to o4_dispositions_v1 (and is rejected by
hall_ensemble._check_o4 until the owner fills it), and nothing carries forbidden wording. The repository is never modified:
synthetic roots in tmp_path are built from symlinks to the frozen files (tampered files are copies)."""
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "docs", "o4", "disposition_matrix")
VAL = os.path.join(ROOT, "hallthruster_bridge", "validation")
CAMPAIGN = "p5_n2_campaign_v1"
SUFFIXES = ("_raw.jsonl.gz", "_raw_manifest.json", "_scores.json", "_scores_provenance.json")
FORBIDDEN = re.compile(r"\b(promote|promoted|promotes|promoting|validated|admitted)\b", re.IGNORECASE)
SCORED_18 = ["staged_n2_n_exc_johnsonlow", "staged_n2_n_rot_off", "staged_n2_n_ndd_hmslow", "staged_n2_n_ndd_hmshigh",
             "staged_n2_n_n2dication", "escalation_n2_n_exc_johnsonlow_di_lower", "escalation_n2_n_exc_johnsonlow_nel_wang",
             "escalation_n2_n_exc_johnsonlow_di_lower_nel_wang", "escalation_n2_n_rot_off_di_lower",
             "escalation_n2_n_rot_off_nel_wang", "escalation_n2_n_rot_off_di_lower_nel_wang",
             "escalation_n2_n_ndd_hmslow_di_lower", "escalation_n2_n_ndd_hmslow_nel_wang",
             "escalation_n2_n_ndd_hmslow_di_lower_nel_wang", "escalation_n2_n_ndd_hmshigh_di_lower",
             "escalation_n2_n_ndd_hmshigh_nel_wang", "escalation_n2_n_ndd_hmshigh_di_lower_nel_wang",
             "escalation_n2_n_n2dication_nel_wang"]
NOT_N2DIC_ESC = [m for m in SCORED_18 if m != "escalation_n2_n_n2dication_nel_wang"]
OFFICIAL = os.path.join(HERE, "o4_disposition_matrix_v1.json")
REVIEW = os.path.join(HERE, "O4_DISPOSITION_MATRIX_REVIEW.md")


def _mod():
    spec = importlib.util.spec_from_file_location("o4m_build", os.path.join(HERE, "build_o4_disposition_matrix.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = _mod()


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _files(manifest):
    return [f"{CAMPAIGN}_{manifest}{s}" for s in SUFFIXES]


def _synthetic_root(tmp, manifests, copy_dirs=()):
    """tmp/<repo layout>: directory symlinks to the frozen inputs, and a validation/ directory holding symlinks to the
    mandatory v1 chain plus only the given O4 datasets. Directories in copy_dirs are copied (so a test may edit them)."""
    r = str(tmp / "root")
    for d in ("hallthruster_bridge/prereg", "hallthruster_bridge/ensemble", "hallthruster_bridge/propellants",
              "hallthruster_bridge/cases", "hallthruster_bridge/identification", "scripts", "docs/orchestration",
              "docs/o4/johnsonlow_assessment"):
        os.makedirs(os.path.dirname(os.path.join(r, d)), exist_ok=True)
        if d in copy_dirs:
            shutil.copytree(os.path.join(ROOT, d), os.path.join(r, d))
        else:
            os.symlink(os.path.join(ROOT, d), os.path.join(r, d))
    os.makedirs(os.path.join(r, "docs", "o4", "disposition_matrix"))
    v = os.path.join(r, "hallthruster_bridge", "validation")
    os.makedirs(v)
    for f in [f"{CAMPAIGN}_vacuum_raw.jsonl.gz", f"{CAMPAIGN}_vacuum_raw_manifest.json", f"{CAMPAIGN}_vacuum_scores.json",
              f"{CAMPAIGN}_vacuum_scores_provenance.json", f"{CAMPAIGN}_vacuum_scores_decision.json"]:
        os.symlink(os.path.join(VAL, f), os.path.join(v, f))
    for m in manifests:
        for f in _files(m):
            os.symlink(os.path.join(VAL, f), os.path.join(v, f))
    return r


@pytest.fixture(scope="module")
def _built():
    M.ACCESS_LOG.clear()
    res = M.build(M.DEFAULT_ROOT, preview=True)
    return res, list(M.ACCESS_LOG)


@pytest.fixture(scope="module")
def preview(_built):
    return _built[0]


@pytest.fixture(scope="module")
def access_log(_built):
    return _built[1]


@pytest.fixture(scope="module")
def _official():
    M.ACCESS_LOG.clear()
    res = M.build(M.DEFAULT_ROOT)
    return res, list(M.ACCESS_LOG)


@pytest.fixture(scope="module")
def official(_official):
    return _official[0]


@pytest.fixture(scope="module")
def committed():
    return json.load(open(OFFICIAL))


# ------------------------------------------------------------------------------------------------ official matrix (S12)
def test_official_matrix_reproduces_byte_for_byte(official):
    assert M.dumps(official) == open(OFFICIAL).read()
    assert official["schema"] == "o4_disposition_matrix_v1" and "PREVIEW" not in official
    rd = official["required_datasets"]
    assert rd["missing"] == [] and rd["undetermined"] == [] and rd["not_required_trigger_not_fired"] == []
    assert sorted(rd["required"]) == sorted(rd["scored"]) == sorted("ds_" + m for m in SCORED_18)
    assert official["provenance"]["all_checks_passed"] is True
    assert all(c["ok"] for c in official["provenance"]["checks"])


def test_official_build_never_reads_interrupted_outputs(_official):
    log = _official[1]
    assert log and not [p for p in log if os.sep + "interrupted" + os.sep in p or p.endswith(os.sep + "interrupted")]


def test_every_official_row_binds_its_scores_provenance_sha256(committed):
    rows = committed["rows"]
    assert len(rows) == 18 and {r["dataset_id"] for r in rows} == {"ds_" + m for m in SCORED_18}
    for r in rows:
        sp = r["scores_provenance"]
        f = os.path.join(ROOT, "hallthruster_bridge", sp["scores_provenance_file"])
        assert not sp["scores_provenance_file"].startswith("validation/interrupted")
        assert _sha(f) == sp["scores_provenance_sha256"]
        assert r["state"] == "SCORED" and r["required"] is True and r["scored_block_reproduced_by_frozen_scorer"] is True
        assert r["owner_disposition"] is None


def test_official_mandatory_scores_reproduced(committed):
    ds = {d["dataset"]: d for d in committed["provenance"]["datasets"]}
    mprov = json.load(open(os.path.join(VAL, f"{CAMPAIGN}_vacuum_scores_provenance.json")))
    assert ds["mandatory v1 vacuum"]["scores_sha256"] == mprov["output_sha256"]
    for m in SCORED_18:
        assert ds[m]["mandatory_reproduced"] is True
    names = [c["check"] for c in committed["provenance"]["checks"]]
    for m in SCORED_18:
        assert sum(1 for n in names if n.startswith("ds_" + m + ": scores mandatory statistics == official mandatory")) == 1


def test_official_feed_is_unbound_and_empty(committed):
    feed = committed["o4_dispositions_feed"]
    M.assert_feed_unbound(feed)
    assert feed["schema"] == "o4_dispositions_v1" and feed["mandatory_decision_sha256"] is None
    assert feed["cleared_for_admission"] == [] and feed["decided_by"] is None and feed["decided_utc"] is None
    assert all(e["disposition"] is None for e in feed["sensitivities"].values())
    assert all(f["owner_disposition"] is None for f in committed["families"].values())

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k, v
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    assert all(v is None for k, v in keys(committed) if k.endswith("decision_sha256"))
    dec = os.path.join(ROOT, feed["mandatory_decision_file"])
    assert _sha(dec) not in open(OFFICIAL).read()
    # every sensitivity fired, so every escalation is bound in the feed, each to the same file/sha as its matrix row
    rows = {(r["family"], r["config"]): r["scores_provenance"] for r in committed["rows"]}
    for sens, e in feed["sensitivities"].items():
        assert e["trigger_fired"] is True and e["first_stage"] == rows[(sens, sens)]
        for cfg, ref in e["escalations"].items():
            assert ref == rows[(sens, cfg)]


def test_no_dispositions_file_is_written_by_this_lane():
    for dp, _, fs in os.walk(os.path.join(ROOT, "docs", "o4")):
        for f in fs:
            assert not f.startswith("o4_dispositions"), os.path.join(dp, f)


def test_missing_set_is_exactly_the_unscored_registered_datasets(preview):
    rd = preview["required_datasets"]
    assert len(rd["required"]) == 18 and rd["undetermined"] == [] and rd["not_required_trigger_not_fired"] == []
    unscored = sorted(set(rd["required"]) - set(rd["scored"]))
    assert sorted(rd["missing"]) == unscored
    for i in rd["missing"]:
        m = i[len("ds_"):]
        assert not os.path.exists(os.path.join(VAL, f"{CAMPAIGN}_{m}_scores_provenance.json"))
    assert set("ds_" + m for m in SCORED_18) <= set(rd["scored"])


def test_refusal_on_synthetic_root_lists_missing_first_stage_and_undetermined(tmp_path):
    keep = [m for m in SCORED_18 if "rot_off" not in m]
    r = _synthetic_root(tmp_path, keep)
    with pytest.raises(M.MatrixRefused) as e:
        M.build(r)
    assert "ds_staged_n2_n_rot_off" in e.value.missing
    assert sorted(e.value.undetermined) == sorted(["ds_escalation_n2_n_rot_off_di_lower", "ds_escalation_n2_n_rot_off_nel_wang",
                                                   "ds_escalation_n2_n_rot_off_di_lower_nel_wang"])
    p = M.build(r, preview=True)
    assert p["families"]["n2_n_rot_off.toml"]["all_required_scored"] is False
    assert all(x["required"] == "UNDETERMINED" for x in p["rows"] if x["family"] == "n2_n_rot_off.toml" and x["stage"] == "escalation")


def test_cli_check_passes_and_writes_nothing(capsys):
    before = {f: _sha(os.path.join(HERE, f)) for f in os.listdir(HERE) if os.path.isfile(os.path.join(HERE, f))}
    assert M.main(["--check"]) == 0
    assert "CHECK OK" in capsys.readouterr().out
    assert {f: _sha(os.path.join(HERE, f)) for f in os.listdir(HERE) if os.path.isfile(os.path.join(HERE, f))} == before


# ------------------------------------------------------------------------------- identity binds immutable inputs only
def test_official_inputs_bind_no_mutable_governance_file(committed):
    ins = committed["provenance"]["inputs_sha256"]
    assert not [k for k in ins if k.startswith("docs/orchestration/")]
    for k, v in ins.items():
        assert _sha(os.path.join(ROOT, k)) == v
    rid = committed["provenance"]["registry_identity"]
    assert rid["lane_registry_o4_datasets_projection_keys"] == ["id", "manifest", "role", "escalations"]
    assert rid["trigger_projection_keys"] == ["id", "prerequisites", "plus"]


def test_matrix_reproduces_after_editing_non_dataset_registry_fields(tmp_path):
    """The orchestrator edits the lane/trigger registries (repairs, followon_dir, lanes, follow-ons) and appends ledger
    records; none of that is evidence, so the official matrix must stay byte-identical."""
    r = _synthetic_root(tmp_path, SCORED_18, copy_dirs=("docs/orchestration",))
    o = os.path.join(r, "docs", "orchestration")
    lp = os.path.join(o, "lane_registry_v1.json")
    reg = json.load(open(lp))
    reg["repairs"] = [{"lane": "fo_o4_disposition_matrix", "note": "synthetic repair record"}]
    reg["decided"] = {"synthetic": "edited"}
    reg["follow_ons"] = {"synthetic_follow_on": {"state": "EDITED"}} if isinstance(reg.get("follow_ons"), dict) \
        else list(reg.get("follow_ons") or []) + [{"id": "synthetic_follow_on"}]
    for d in reg["datasets"]:
        d["followon_dir"] = "/synthetic/elsewhere/" + d["id"]
    reg["lanes"] = reg["lanes"] if not isinstance(reg.get("lanes"), list) else reg["lanes"] + [{"id": "lane_99_synthetic"}]
    json.dump(reg, open(lp, "w"), indent=2)
    tp = os.path.join(o, "trigger_registry_v1.json")
    tr = json.load(open(tp))
    tr["synthetic_note"] = "edited by the orchestrator"
    json.dump(tr, open(tp, "w"), indent=2)
    with open(os.path.join(o, "trigger_ledger_v2.jsonl"), "a") as f:
        f.write(json.dumps({"event": "VERIFIED", "evidence": {"follow_on": M.JLA_FOLLOW_ON, "commit": "0" * 40}}) + "\n")
    assert _sha(lp) != _sha(os.path.join(ROOT, "docs", "orchestration", "lane_registry_v1.json"))
    assert M.dumps(M.build(r)) == open(OFFICIAL).read()


def test_projected_registry_fields_still_bind(tmp_path):
    """The canonical projection is the identity: changing a dataset manifest is refused, and changing the trigger's
    pre-registered 'plus' rule changes the bound projection hash."""
    r = _synthetic_root(tmp_path, SCORED_18, copy_dirs=("docs/orchestration",))
    tp = os.path.join(r, "docs", "orchestration", "trigger_registry_v1.json")
    tr = json.load(open(tp))
    items = tr["triggers"] if isinstance(tr, dict) and "triggers" in tr else tr
    for t in (items if isinstance(items, list) else items.values()):
        if isinstance(t, dict) and t.get("id") == M.TRIGGER:
            t["plus"] = t["plus"] + " (edited)"
    json.dump(tr, open(tp, "w"), indent=2)
    assert M.build(r)["provenance"]["registry_identity"]["trigger_projection_sha256"] != \
        json.load(open(OFFICIAL))["provenance"]["registry_identity"]["trigger_projection_sha256"]
    lp = os.path.join(r, "docs", "orchestration", "lane_registry_v1.json")
    reg = json.load(open(lp))
    next(d for d in reg["datasets"] if d["id"] == "ds_staged_n2_n_rot_off")["manifest"] = "staged_elsewhere"
    json.dump(reg, open(lp, "w"), indent=2)
    with pytest.raises(M.ProvenanceError):
        M.build(r)


def test_owner_dispositions_record_is_never_read(tmp_path):
    """An owner o4_dispositions file under hallthruster_bridge/ensemble/ is neither read nor bound: the matrix and its feed
    are byte-identical with it present, and guard() refuses it."""
    r = _synthetic_root(tmp_path, SCORED_18, copy_dirs=("hallthruster_bridge/ensemble",))
    bait = os.path.join(r, "hallthruster_bridge", "ensemble", "o4_dispositions_v1.json")
    json.dump({"schema": "o4_dispositions_v1", "decided_by": "synthetic owner", "mandatory_decision_sha256": "f" * 64},
              open(bait, "w"))
    M.ACCESS_LOG.clear()
    assert M.dumps(M.build(r)) == open(OFFICIAL).read()
    assert not [x for x in M.ACCESS_LOG if os.path.basename(x).startswith("o4_dispositions")
                and os.path.basename(x) != M.DISPOSITIONS_SCHEMA_NAME]
    with pytest.raises(M.ProvenanceError, match="owner dispositions"):
        M.guard(M.Paths(r), bait)
    M.guard(M.Paths(r), os.path.join(r, "hallthruster_bridge", "ensemble", M.DISPOSITIONS_SCHEMA_NAME))


# --------------------------------------------------------------------------------------------------------------- hashes
def test_all_checks_passed_and_hash_rows_match_files(preview):
    prov = preview["provenance"]
    assert prov["all_checks_passed"] is True and prov["n_checks"] == len(prov["checks"]) > 11 * 20
    rows = {d["dataset"]: d for d in prov["datasets"]}
    for m in SCORED_18:
        d = rows[m]
        assert d["scores_sha256"] == _sha(os.path.join(VAL, f"{CAMPAIGN}_{m}_scores.json"))
        assert d["provenance_sha256"] == _sha(os.path.join(VAL, f"{CAMPAIGN}_{m}_scores_provenance.json"))
        assert d["raw_sha256_gz"] == _sha(os.path.join(VAL, f"{CAMPAIGN}_{m}_raw.jsonl.gz"))
        assert d["mandatory_reproduced"] is True


@pytest.mark.parametrize("target,edit", [
    ("_scores.json", lambda b: b.replace(b'"n_runs": 270', b'"n_runs": 271', 1)),
    ("_scores_provenance.json", lambda b: b.replace(b'"mandatory_reproduced": true', b'"mandatory_reproduced": false', 1)),
    ("_raw_manifest.json", lambda b: re.sub(rb'"sha256_canonical_jsonl": "[0-9a-f]{4}', b'"sha256_canonical_jsonl": "0000', b, 1)),
])
def test_tampered_file_is_rejected(tmp_path, target, edit):
    r = _synthetic_root(tmp_path, SCORED_18)
    f = os.path.join(r, "hallthruster_bridge", "validation", f"{CAMPAIGN}_staged_n2_n_rot_off{target}")
    data = open(os.path.realpath(f), "rb").read()
    new = edit(data)
    assert new != data
    os.remove(f)
    open(f, "wb").write(new)
    with pytest.raises(M.ProvenanceError):
        M.build(r, preview=True)


def test_scored_block_that_the_frozen_scorer_does_not_reproduce_is_rejected(tmp_path):
    """Change a verdict-change entry AND re-bind every hash: only the frozen-scorer recomputation can catch it."""
    r = _synthetic_root(tmp_path, SCORED_18)
    v = os.path.join(r, "hallthruster_bridge", "validation")
    sp, pp = (os.path.join(v, f"{CAMPAIGN}_staged_n2_n_rot_off{s}") for s in ("_scores.json", "_scores_provenance.json"))
    s = json.load(open(sp))
    s["staged_escalation"]["n2_n_rot_off.toml"]["run_level_triggers"].pop()
    os.remove(sp)
    json.dump(s, open(sp, "w"), indent=1)
    p = json.load(open(pp))
    p["output_sha256"] = _sha(sp)
    os.remove(pp)
    json.dump(p, open(pp, "w"), indent=1)
    with pytest.raises(M.ProvenanceError, match="reproduces run_level_triggers"):
        M.build(r, preview=True)


# ---------------------------------------------------------------------------------------------------------- interrupted
def test_interrupted_outputs_are_never_read(access_log):
    interrupted = os.path.join(VAL, "interrupted")
    assert os.path.isdir(interrupted)
    assert access_log and not [p for p in access_log if "interrupted" in p]


def test_guard_refuses_interrupted_paths_and_symlinks(tmp_path):
    paths = M.Paths(M.DEFAULT_ROOT)
    for p in [os.path.join(VAL, "interrupted", "escalation_n2_n_n2dication_nel_wang_attempt1", "STATUS.json"),
              os.path.join(VAL, "interrupted")]:
        with pytest.raises(M.ProvenanceError):
            M.guard(paths, p)
    r = _synthetic_root(tmp_path, NOT_N2DIC_ESC)
    v = os.path.join(r, "hallthruster_bridge", "validation")
    os.makedirs(os.path.join(v, "interrupted"))
    bait = os.path.join(v, "interrupted", "bait.json")
    open(bait, "w").write("{}")
    link = os.path.join(v, f"{CAMPAIGN}_escalation_n2_n_n2dication_nel_wang_scores_provenance.json")
    os.symlink(bait, link)
    with pytest.raises(M.ProvenanceError, match="interrupted"):
        M.guard(M.Paths(r), link)


def test_decoy_files_in_interrupted_do_not_count_as_scored(tmp_path):
    r = _synthetic_root(tmp_path, NOT_N2DIC_ESC)
    d = os.path.join(r, "hallthruster_bridge", "validation", "interrupted")
    os.makedirs(d)
    for f in _files("escalation_n2_n_n2dication_nel_wang"):
        shutil.copy(os.path.join(VAL, f"{CAMPAIGN}_staged_n2_n_n2dication{f.split('n2dication_nel_wang', 1)[1]}"),
                    os.path.join(d, f))
    M.ACCESS_LOG.clear()
    p = M.build(r, preview=True)
    assert "ds_escalation_n2_n_n2dication_nel_wang" in p["required_datasets"]["missing"]
    assert not [x for x in M.ACCESS_LOG if os.sep + "interrupted" + os.sep in x]


# -------------------------------------------------------------------------------------------------------------- totals
def _counts(block):
    kinds, keys, st = {"status": 0, "dI_d": 0, "dT": 0}, set(), set()
    for key, text in block["run_level_triggers"]:
        k = text.split()[0]
        kinds[k] += 1
        keys.add(key)
        if k == "status":
            st.add(key)
    return kinds, keys, st


def test_totals_reproduce_scored_staged_escalation_blocks(preview):
    rows = {r["dataset_id"]: r for r in preview["rows"]}
    for m in SCORED_18:
        cfg = m.split("_", 1)[1] + ".toml"
        blk = json.load(open(os.path.join(VAL, f"{CAMPAIGN}_{m}_scores.json")))["staged_escalation"][cfg]
        row = rows["ds_" + m]
        assert row["state"] == "SCORED" and row["config"] == cfg and row["baseline"] == blk["baseline"]
        assert row["trigger_fired"] == blk["trigger_fired"] and row["n_runs"] == blk["n_runs"] == 270
        kinds, keys, st = _counts(blk)
        tc = row["trigger_counts"]
        assert tc["by_kind"] == kinds
        assert row["n_run_level_triggers"] == len(blk["run_level_triggers"]) == sum(kinds.values())
        assert sum(sum(p.values()) for p in tc["by_point"].values()) == len(blk["run_level_triggers"])
        for k in kinds:
            assert sum(tc["by_kind_and_reading"][k].values()) == kinds[k]
            assert sum(p[k] for p in tc["by_point"].values()) == kinds[k]
        assert tc["by_point"]["N4"]["dT"] == tc["by_point"]["N5"]["dT"] == 0      # thrust triggers exist only at N1-N3
        assert sum(sum(x.values()) for x in row["status_transitions"].values()) == kinds["status"]
        assert row["n_runs_with_any_run_level_trigger"] == len(keys) and row["n_runs_with_status_change"] == len(st)
        vc = row["verdict_changes"]
        assert vc["n_candidates_with_any_change"] == len(blk["verdict_changes"])
        assert vc["n_member_verdict_changes"] == sum(len(x["members"]) for x in blk["verdict_changes"].values())
        for c, x in blk["verdict_changes"].items():
            if x["candidate"][0] != x["candidate"][1]:
                assert vc["candidate_verdict_changes"][c] == x["candidate"]
        assert row["scored_block_reproduced_by_frozen_scorer"] is True
        assert row["owner_disposition"] is None


def test_johnsonlow_rows_agree_with_the_verified_assessment(preview):
    jla = json.load(open(os.path.join(ROOT, "docs", "o4", "johnsonlow_assessment", "johnsonlow_assessment_v1.json")))
    assert preview["johnsonlow_assessment"]["sha256"] == _sha(os.path.join(ROOT, "docs", "o4", "johnsonlow_assessment",
                                                                           "johnsonlow_assessment_v1.json"))
    rows = [r for r in preview["rows"] if r["family"] == "n2_n_exc_johnsonlow.toml"]
    assert len(rows) == 4
    for r in rows:
        tb = jla["answer"]["tail_by_baseline"][r["baseline"]]
        assert r["n_runs_with_any_run_level_trigger"] == tb["n_runs_any_trigger"]
        assert r["n_runs_with_status_change"] == tb["n_runs_status_changed"]


def test_no_disposition_is_decided(preview):
    assert all(r["owner_disposition"] is None for r in preview["rows"])
    assert all(f["owner_disposition"] is None for f in preview["families"].values())
    assert "o4_dispositions_feed" not in preview and preview["PREVIEW"] is True
    assert preview["schema"] == "o4_evidence_matrix_preview_v1"


# ------------------------------------------------------------------------------------------------ feed vs _check_o4
def test_official_feed_conforms_to_dispositions_schema_and_is_checked_by_hall_ensemble(tmp_path):
    """Test-only synthetic root whose (copied) pre-registration, lane and trigger registries are trimmed to the two fully
    scored families, so the official path runs. The emitted feed is rejected by _check_o4 as is; once test values stand in
    for the owner fields it passes the real _check_o4."""
    from abep_sim import hall_ensemble
    keep = [m for m in SCORED_18 if "johnsonlow" in m or "rot_off" in m]
    r = _synthetic_root(tmp_path, keep, copy_dirs=("hallthruster_bridge/prereg", "docs/orchestration"))
    crit_p = os.path.join(r, "hallthruster_bridge", "prereg", "p5_n2_validation_criteria_v1.json")
    crit = json.load(open(crit_p))
    crit["staged_sensitivities"] = {k: v for k, v in crit["staged_sensitivities"].items()
                                    if k in ("n2_n_exc_johnsonlow.toml", "n2_n_rot_off.toml")}
    json.dump(crit, open(crit_p, "w"), indent=1)
    reg_p = os.path.join(r, "docs", "orchestration", "lane_registry_v1.json")
    reg = json.load(open(reg_p))
    reg["datasets"] = [d for d in reg["datasets"] if not str(d.get("role", "")).startswith("O4 ")
                       or "johnsonlow" in d["id"] or "rot_off" in d["id"]]
    json.dump(reg, open(reg_p, "w"), indent=1)
    tr_p = os.path.join(r, "docs", "orchestration", "trigger_registry_v1.json")
    tr = json.load(open(tr_p))
    for t in (tr["triggers"] if isinstance(tr, dict) and "triggers" in tr else tr):
        if isinstance(t, dict) and t.get("id") == "T_O4_DISPOSITION_MATRIX":
            t["prerequisites"] = [p for p in t["prerequisites"] if "johnsonlow" in p["id"] or "rot_off" in p["id"]]
    json.dump(tr, open(tr_p, "w"), indent=1)

    off = M.build(r)
    assert off["schema"] == "o4_disposition_matrix_v1" and off["required_datasets"]["missing"] == []
    feed = off["o4_dispositions_feed"]
    schema = json.load(open(os.path.join(ROOT, "hallthruster_bridge", "ensemble", "o4_dispositions_schema_v1.json")))
    assert set(schema["required_fields"]) <= set(feed)
    assert feed["schema"] == "o4_dispositions_v1"
    assert feed["cleared_for_admission"] == [] and feed["decided_by"] is None and feed["decided_utc"] is None
    assert all(e["disposition"] is None for e in feed["sensitivities"].values())

    assert feed["mandatory_decision_sha256"] is None                             # never pre-filled by the builder

    br = os.path.join(r, "hallthruster_bridge")
    mprov = json.load(open(os.path.join(br, "validation", f"{CAMPAIGN}_vacuum_scores_provenance.json")))
    dec_sha = _sha(os.path.join(r, feed["mandatory_decision_file"]))            # what a citing admission record would carry
    os.makedirs(os.path.join(br, "ensemble_test"))
    fp = os.path.join(br, "ensemble_test", "o4_dispositions_test.json")

    def check(d):
        json.dump(d, open(fp, "w"), indent=1)
        adm = {"o4_dispositions_file": "ensemble_test/o4_dispositions_test.json", "o4_dispositions_sha256": _sha(fp),
               "decision_sha256": dec_sha,
               "preregistration": "prereg/p5_n2_validation_criteria_v1.json"}
        hall_ensemble._check_o4("sgb-screen-01", adm, br, mprov)

    with pytest.raises(ValueError, match="not bound to this admission's decision"):
        check(feed)                                                              # as emitted: unbound
    bound_only = copy.deepcopy(feed)
    bound_only["mandatory_decision_sha256"] = dec_sha                            # TEST stand-in for the owner's binding
    with pytest.raises(ValueError, match="no owner disposition"):
        check(bound_only)
    filled = copy.deepcopy(bound_only)
    for e in filled["sensitivities"].values():
        e["disposition"] = "TEST STAND-IN (not an owner decision)"
    filled.update(cleared_for_admission=["sgb-screen-01"], decided_by="test", decided_utc="2026-09-27T00:00:00Z")
    check(filled)
    # The decision file's hash appears nowhere in the builder output (matrix and feed): no pre-binding anywhere.
    assert dec_sha not in M.dumps(off)
    bad = copy.deepcopy(filled)
    bad["sensitivities"]["n2_n_rot_off.toml"]["trigger_fired"] = False
    with pytest.raises(ValueError, match="differs from the scored evaluation"):
        check(bad)
    assert M.dumps(M.build(r)) == M.dumps(off)                                   # deterministic


# -------------------------------------------------------------- decision hash stays empty (owner decision 2026-09-27)
def _unbound_feed():
    return {"schema": "o4_dispositions_v1", "campaign_id": CAMPAIGN, "mandatory_decision_sha256": None,
            "mandatory_decision_file": "x", "sensitivities": {"a.toml": {"baseline": "n2_n.toml", "disposition": None,
                                                                         "first_stage": {"scores_provenance_sha256": "ab"}}},
            "cleared_for_admission": [], "decided_by": None, "decided_utc": None}


def test_feed_guard_accepts_the_unbound_template():
    M.assert_feed_unbound(_unbound_feed())
    assert "mandatory_decision_sha256" in M.DECISION_HASH_FIELDS


@pytest.mark.parametrize("edit", [
    lambda f: f.update(mandatory_decision_sha256="0" * 64),
    lambda f: f.update(mandatory_decision_sha256="TBD"),
    lambda f: f.pop("mandatory_decision_sha256"),
    lambda f: f["sensitivities"]["a.toml"].update(decision_sha256="0" * 64),
    lambda f: f.update(extra={"source_decision_sha256": "0" * 64}),
    lambda f: f["sensitivities"]["a.toml"].update(disposition="x"),
    lambda f: f.update(cleared_for_admission=["sgb-screen-01"]),
    lambda f: f.update(decided_by="someone"),
    lambda f: f.update(decided_utc="2026-09-27T00:00:00Z"),
], ids=["mandatory_hash", "mandatory_placeholder", "mandatory_missing", "nested_hash", "other_decision_hash",
        "disposition", "cleared", "decided_by", "decided_utc"])
def test_feed_guard_refuses_any_prefilled_owner_field(edit):
    f = _unbound_feed()
    edit(f)
    with pytest.raises(M.ProvenanceError):
        M.assert_feed_unbound(f)


def test_builder_source_never_binds_the_decision_hash():
    """Static check: the only value dispositions_feed assigns to mandatory_decision_sha256 is None."""
    src = open(os.path.join(HERE, "build_o4_disposition_matrix.py")).read()
    body = src[src.index("def dispositions_feed("):src.index("def assert_feed_unbound(")]
    assigned = re.findall(r'"mandatory_decision_sha256":\s*([^,\n]+)', body)
    assert assigned == ["None"], assigned
    assert "assert_feed_unbound(feed)" in body


def test_readme_states_milestone_and_empty_decision_hash():
    text = open(os.path.join(HERE, "README.md")).read()
    assert "Milestone B" in text and "Milestone A" in text
    assert "mandatory_decision_sha256" in text and "EMPTY" in text


# ----------------------------------------------------------------------------------------------------- preview naming
def test_preview_is_never_named_as_disposition_or_official(tmp_path, preview):
    for name in ("o4_disposition_matrix_v1.json", "my_disposition.json", "Dispositions.json"):
        with pytest.raises(ValueError):
            M.write_preview(preview, str(tmp_path / name))
    with pytest.raises(ValueError):
        M.write_preview(preview, os.path.join(HERE, M.OFFICIAL_NAME))
    with pytest.raises(ValueError):
        M.write_preview(dict(preview, schema="o4_disposition_matrix_v1"), str(tmp_path / "o4_evidence_preview.json"))
    p = M.write_preview(preview, str(tmp_path / "o4_evidence_preview.json"))
    assert json.load(open(p))["PREVIEW"] is True


def test_directory_holds_only_the_expected_files():
    assert sorted(n for n in os.listdir(HERE) if n != "__pycache__") == sorted([
        "README.md", "build_o4_disposition_matrix.py", "o4_disposition_matrix_schema_v1.json", M.OFFICIAL_NAME,
        "O4_DISPOSITION_MATRIX_REVIEW.md"])


# ---------------------------------------------------------------------------------------------------------- wording
def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def test_no_forbidden_wording(preview, committed):
    for f in ("README.md", "build_o4_disposition_matrix.py", "o4_disposition_matrix_schema_v1.json",
              "O4_DISPOSITION_MATRIX_REVIEW.md"):
        text = open(os.path.join(HERE, f)).read()
        assert not FORBIDDEN.findall(text), f
    assert not FORBIDDEN.findall(open(__file__).read().replace("promote|promoted|promotes|promoting|validated|admitted", ""))
    hits = [s for s in list(_strings(preview)) + list(_strings(committed)) if FORBIDDEN.search(s)]
    assert not hits, hits[:5]


# ------------------------------------------------------------------------------------------------- owner review tables
BEGIN_MARK = "<!-- BEGIN GENERATED TABLES: python tests/test_o4_disposition_matrix.py --print-review-tables -->"
END_MARK = "<!-- END GENERATED TABLES -->"
OOD = "OUT_OF_DOMAIN"


def _short(cfg):
    return cfg[:-len(".toml")] if cfg.endswith(".toml") else cfg


def _ordered_rows(m):
    """Rows grouped by family in pre-registration order (first-stage order of the matrix), first stage then escalations."""
    fams = [r["family"] for r in m["rows"] if r["stage"] == "first_stage"]
    return [r for f in fams for r in sorted((x for x in m["rows"] if x["family"] == f), key=lambda x: x["stage"] != "first_stage")]


def _transition_split(row):
    """Status-trigger readings split into: crossing the OUT_OF_DOMAIN boundary, FAIL_VALIDATION <-> PASS, other."""
    ood = fp = other = 0
    for rd in ("A", "B"):
        for t, n in row["status_transitions"][rd].items():
            if OOD in t:
                ood += n
            elif set(t.split(" -> ")) == {"FAIL_VALIDATION", "PASS"}:
                fp += n
            else:
                other += n
    return ood, fp, other


def review_tables(m, jla, candidates):
    """Deterministic Markdown tables of the owner review, regenerated from the committed official matrix, the verified
    Johnson-low assessment and the candidate list of the mandatory v1 decision. Facts only; no disposition."""
    rows = _ordered_rows(m)
    L = []
    L.append("#### Table 1 - per family x baseline: trigger, run-level trigger counts, verdict changes")
    L.append("")
    L.append("| # | family | baseline | stage | trigger_fired | runs with >= 1 trigger / runs | trigger readings status / dI_d / dT "
             "| runs with a status change | candidate verdict changes | member verdict changes | scores_provenance sha256 (12) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        k = r["trigger_counts"]["by_kind"]
        cv = r["verdict_changes"]["candidate_verdict_changes"]
        cvt = "; ".join(f"{c}: {a} -> {b}" for c, (a, b) in sorted(cv.items())) or "none"
        L.append(f"| {i} | {_short(r['family'])} | {_short(r['baseline'])} | {r['stage']} | {r['trigger_fired']} | "
                 f"{r['n_runs_with_any_run_level_trigger']} / {r['n_runs']} | {k['status']} / {k['dI_d']} / {k['dT']} | "
                 f"{r['n_runs_with_status_change']} | {cvt} | {r['verdict_changes']['n_member_verdict_changes']} | "
                 f"`{r['scores_provenance']['scores_provenance_sha256'][:12]}` |")
    L.append("")
    L.append("#### Table 2 - run-level trigger readings by point (status / dI_d / dT; readings A and B counted separately)")
    L.append("")
    L.append("| # | family | baseline | N1 | N2 | N3 | N4 | N5 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        bp = r["trigger_counts"]["by_point"]
        cells = " | ".join(f"{bp[p]['status']} / {bp[p]['dI_d']} / {bp[p]['dT']}" for p in ("N1", "N2", "N3", "N4", "N5"))
        L.append(f"| {i} | {_short(r['family'])} | {_short(r['baseline'])} | {cells} |")
    L.append("")
    L.append("#### Table 3 - status transitions (baseline status -> sensitivity status, number of runs, per reading)")
    L.append("")
    L.append("| # | family | baseline | reading A | reading B |")
    L.append("|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        st = r["status_transitions"]
        cell = {rd: "; ".join(f"{t}: {n}" for t, n in st[rd].items()) or "none" for rd in ("A", "B")}
        L.append(f"| {i} | {_short(r['family'])} | {_short(r['baseline'])} | {cell['A']} | {cell['B']} |")
    L.append("")
    L.append("#### Table 4 - candidate-level verdict changes (counterfactual: one mandatory chemistry replaced by the sensitivity)")
    L.append("")
    L.append("| candidate | v1 verdict -> counterfactual verdict | rows | family x baseline |")
    L.append("|---|---|---|---|")
    cand = {}
    for r in rows:
        for c, (a, b) in r["verdict_changes"]["candidate_verdict_changes"].items():
            cand.setdefault((c, a, b), []).append(f"{_short(r['family'])} x {_short(r['baseline'])}")
    for (c, a, b), where in sorted(cand.items()):
        L.append(f"| {c} | {a} -> {b} | {len(where)} | {'; '.join(where)} |")
    unchanged = sorted(set(candidates) - {c for (c, _, _) in cand})
    L.append("")
    L.append(f"Candidates with no candidate-level change in any row: {', '.join(unchanged) or 'none'}.")
    mem = {}
    for r in rows:
        for c, mm in r["verdict_changes"]["member_verdict_changes"].items():
            for key, (a, b) in mm.items():
                base, rd = key.rsplit("|", 1)
                mem.setdefault((c, base, a, b), {}).setdefault(f"{_short(r['family'])} x {_short(r['baseline'])}", set()).add(rd)
    no_member = sorted(set(candidates) - {c for (c, _, _, _) in mem})
    L.append(f"Candidates with no member-level change in any row: {', '.join(no_member) or 'none'}.")
    L.append("")
    L.append("#### Table 5 - member-level verdict changes (member key = P5 registration, historical coil shape, beam-efficiency reading)")
    L.append("")
    L.append("| candidate | member (registration, coil) | verdict change | readings | rows | family x baseline |")
    L.append("|---|---|---|---|---|---|")
    for (c, base, a, b), where in sorted(mem.items()):
        rds = sorted({x for v in where.values() for x in v})
        L.append(f"| {c} | {base.replace('|', ', ')} | {a} -> {b} | {'/'.join(rds)} | {len(where)} | {'; '.join(where)} |")
    targets = sorted({b for (_, _, _, b) in mem} | {b for (_, _, b) in cand})
    L.append("")
    L.append(f"Counterfactual verdicts reached in any row: {', '.join(targets)}.")
    L.append("")
    L.append("#### Table 6 - per family totals over its rows (trigger readings; readings A and B counted separately)")
    L.append("")
    L.append("| family | rows | rows with trigger_fired | status | dI_d | dT | status readings crossing OUT_OF_DOMAIN "
             "| FAIL_VALIDATION <-> PASS | other status readings | candidates with a candidate-level change | "
             "rows with >= 1 member change |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    tot = {"status": 0, "dI_d": 0, "dT": 0, "ood": 0, "fp": 0, "other": 0}
    for f in dict.fromkeys(r["family"] for r in rows):
        fr = [r for r in rows if r["family"] == f]
        k = {x: sum(r["trigger_counts"]["by_kind"][x] for r in fr) for x in ("status", "dI_d", "dT")}
        sp = [sum(_transition_split(r)[j] for r in fr) for j in range(3)]
        cc = sorted({c for r in fr for c in r["verdict_changes"]["candidate_verdict_changes"]})
        nm = sum(1 for r in fr if r["verdict_changes"]["n_member_verdict_changes"])
        for x in k:
            tot[x] += k[x]
        tot["ood"] += sp[0]
        tot["fp"] += sp[1]
        tot["other"] += sp[2]
        L.append(f"| {_short(f)} | {len(fr)} | {sum(1 for r in fr if r['trigger_fired'])} | {k['status']} | {k['dI_d']} | "
                 f"{k['dT']} | {sp[0]} | {sp[1]} | {sp[2]} | {', '.join(cc) or 'none'} | {nm} |")
    L.append(f"| all | {len(rows)} | {sum(1 for r in rows if r['trigger_fired'])} | {tot['status']} | {tot['dI_d']} | "
             f"{tot['dT']} | {tot['ood']} | {tot['fp']} | {tot['other']} | "
             f"{', '.join(sorted({c for r in rows for c in r['verdict_changes']['candidate_verdict_changes']}))} | "
             f"{sum(1 for r in rows if r['verdict_changes']['n_member_verdict_changes'])} |")
    L.append("")
    a = jla["answer"]
    L.append("#### Table 7 - verified Johnson-low assessment (`docs/o4/johnsonlow_assessment/johnsonlow_assessment_v1.json`, "
             f"sha256 `{m['johnsonlow_assessment']['sha256'][:12]}`, ledger VERIFIED at "
             f"`{str(m['johnsonlow_assessment']['ledger_verified_commit'])[:12]}`)")
    L.append("")
    L.append(f"- mode: `{a['mode']}`; material_on_every_primary_combination: `{a['material_on_every_primary_combination']}`")
    L.append(f"- class counts: {', '.join(f'{k} {v}' for k, v in sorted(a['class_counts'].items()))}")
    L.append(f"- observables that persist (|median r| >= 1 on all four): {', '.join(a['observables_that_persist']) or 'none'}")
    L.append(f"- sign consistent below threshold: {', '.join(a['observables_sign_consistent_below_threshold']) or 'none'}")
    L.append(f"- baseline-dependent sign: {', '.join(a['observables_with_baseline_dependent_sign']) or 'none'}")
    L.append(f"- status changes on every combination: A `{a['status_changes_on_every_combination']['A']}`, "
             f"B `{a['status_changes_on_every_combination']['B']}`; verdict changes on every combination: "
             f"`{a['verdict_changes_on_every_combination']}`; common to all four: `{a['verdict_changes_common_to_all_four']}`")
    L.append("")
    L.append("| baseline | runs with any trigger | runs with a status change | of which across OUT_OF_DOMAIN | "
             "pairs dI >= threshold | pairs dT_A >= threshold | pairs dT_B >= threshold | pairs with thrust |")
    L.append("|---|---|---|---|---|---|---|---|")
    for b, t in sorted(a["tail_by_baseline"].items()):
        L.append(f"| {_short(b)} | {t['n_runs_any_trigger']} | {t['n_runs_status_changed']} | "
                 f"{t['n_runs_status_changed_across_OOD_boundary']} | {t['n_pairs_dI_ge_threshold']} | "
                 f"{t['n_pairs_dT_A_ge_threshold']} | {t['n_pairs_dT_B_ge_threshold']} | {t['n_pairs_with_thrust']} |")
    L.append("")
    L.append(f"> Assessment summary (quoted): {a['summary']}")
    L.append(">")
    L.append(f"> What this does not mean (quoted): {a['what_this_does_not_mean']}")
    L.append("")
    L.append("#### Table 8 - owner fields of the dispositions feed (all empty in the matrix; filled only in a separate "
             "o4_dispositions_v1 file)")
    L.append("")
    L.append("| field | covers matrix rows (Table 1 #) | first stage scores_provenance sha256 (12) | escalations bound | value in feed |")
    L.append("|---|---|---|---|---|")
    feed = m["o4_dispositions_feed"]
    idx = {r["dataset_id"]: i for i, r in enumerate(rows, 1)}
    for sens, e in feed["sensitivities"].items():
        cover = [str(idx[r["dataset_id"]]) for r in rows if r["family"] == sens]
        L.append(f"| `sensitivities.{sens}.disposition` | {', '.join(cover)} | "
                 f"`{e['first_stage']['scores_provenance_sha256'][:12]}` | {len(e.get('escalations') or {})} | "
                 f"{json.dumps(e['disposition'])} |")
    for k in ("cleared_for_admission", "decided_by", "decided_utc", "mandatory_decision_sha256"):
        L.append(f"| `{k}` | all | - | - | {json.dumps(feed[k])} |")
    return "\n".join(L) + "\n"


def _review_inputs():
    m = json.load(open(OFFICIAL))
    jla = json.load(open(os.path.join(ROOT, "docs", "o4", "johnsonlow_assessment", "johnsonlow_assessment_v1.json")))
    dec = json.load(open(os.path.join(VAL, f"{CAMPAIGN}_vacuum_scores_decision.json")))
    return m, jla, sorted(dec["candidates"])


def test_review_tables_are_regenerated_from_the_official_matrix():
    text = open(REVIEW).read()
    assert text.count(BEGIN_MARK) == 1 and text.count(END_MARK) == 1
    body = text.split(BEGIN_MARK, 1)[1].split(END_MARK, 1)[0]
    assert body.strip("\n") == review_tables(*_review_inputs()).strip("\n")


def test_review_facts_used_in_the_prose_hold():
    m, jla, cands = _review_inputs()
    rows = m["rows"]
    # every row fired; candidate-level changes go only INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION; members only
    # between INCONCLUSIVE and FAIL, identically under both beam-efficiency readings
    assert all(r["trigger_fired"] is True for r in rows) and len(rows) == 18
    for r in rows:
        for c, (a, b) in r["verdict_changes"]["candidate_verdict_changes"].items():
            assert (a, b) == ("INCONCLUSIVE / NOT ELIGIBLE", "FAIL_VALIDATION")
        for c, mm in r["verdict_changes"]["member_verdict_changes"].items():
            for key, (a, b) in mm.items():
                assert {a, b} == {"INCONCLUSIVE", "FAIL"}
                other = key[:-1] + ("B" if key.endswith("A") else "A")
                assert mm.get(other) == [a, b]
    n2 = {r["baseline"]: r for r in rows if r["family"] == "n2_n_n2dication.toml"}
    assert n2["n2_n_di_lower_nel_wang.toml"]["verdict_changes"]["candidate_verdict_changes"] == {
        "sgb-screen-05": ["INCONCLUSIVE / NOT ELIGIBLE", "FAIL_VALIDATION"]}
    dec = json.load(open(os.path.join(VAL, f"{CAMPAIGN}_vacuum_scores_decision.json")))
    assert dec["promotable"] == [] and set(dec["candidates"].values()) == {"INCONCLUSIVE / NOT ELIGIBLE"}
    for r in rows:                                                    # thrust triggers only where a thrust tolerance exists
        assert r["trigger_counts"]["by_point"]["N4"]["dT"] == r["trigger_counts"]["by_point"]["N5"]["dT"] == 0
    fp = {"FAIL_VALIDATION -> PASS": 0, "PASS -> FAIL_VALIDATION": 0}
    numfail_rows = set()
    for i, r in enumerate(_ordered_rows(m), 1):
        for rd in ("A", "B"):
            for t, n in r["status_transitions"][rd].items():
                if t in fp:
                    fp[t] += n
                if t.endswith("NUMERICAL_FAILURE"):
                    assert t == "OUT_OF_DOMAIN -> NUMERICAL_FAILURE" and n == 1
                    numfail_rows.add(i)
    assert fp == {"FAIL_VALIDATION -> PASS": 67, "PASS -> FAIL_VALIDATION": 17}
    assert numfail_rows == {8, 18}
    text = open(REVIEW).read()
    for phrase in ("67 FAIL_VALIDATION → PASS and 17 PASS → FAIL_VALIDATION", "rows 8 and 18", "1825 `dT`, 1504 `dI_d` and 970",
                   "886 of 970", "84 of 92 status-changed runs"):
        assert phrase in text, phrase


def test_review_states_scope_and_quotes_the_schema_without_prefilling():
    text = open(REVIEW).read()
    schema = json.load(open(os.path.join(ROOT, "hallthruster_bridge", "ensemble", "o4_dispositions_schema_v1.json")))
    rf = schema["required_fields"]
    assert rf["sensitivities"]["<staged sensitivity config, one per prereg staged_sensitivities entry>"]["disposition"] in text
    for k in ("cleared_for_admission", "decided_by", "decided_utc", "mandatory_decision_sha256"):
        assert rf[k] in text
    for phrase in ("O4 is sensitivity evidence", "cannot alter P5-N2 v1", "INCONCLUSIVE permanently",
                   "credible set stays empty", "hall_ensemble._check_o4", "genuinely new predictive evidence",
                   "Milestone A", "Milestone B", "Milestone C", "no disposition is recommended"):
        assert phrase.lower() in text.lower(), phrase
    assert "o4_dispositions_v1" in text
    readme = open(os.path.join(HERE, "README.md")).read()
    assert "official matrix built, dispositions pending owner" in readme


if __name__ == "__main__":
    import sys
    if "--print-review-tables" in sys.argv:
        sys.stdout.write(review_tables(*_review_inputs()))
