"""S12 machinery (docs/o4/disposition_matrix/build_o4_disposition_matrix.py): the official O4 disposition matrix is refused while
required datasets are unscored, every hash binding is verified, interrupted attempt-1 outputs are never read, the preview totals
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
SCORED_11 = ["staged_n2_n_exc_johnsonlow", "staged_n2_n_rot_off", "staged_n2_n_ndd_hmslow", "staged_n2_n_ndd_hmshigh",
             "staged_n2_n_n2dication", "escalation_n2_n_exc_johnsonlow_di_lower", "escalation_n2_n_exc_johnsonlow_nel_wang",
             "escalation_n2_n_exc_johnsonlow_di_lower_nel_wang", "escalation_n2_n_rot_off_di_lower",
             "escalation_n2_n_rot_off_nel_wang", "escalation_n2_n_rot_off_di_lower_nel_wang"]


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


# ------------------------------------------------------------------------------------------------------------------ refusal
def test_official_refused_while_required_datasets_missing(preview):
    miss = preview["required_datasets"]["missing"] + preview["required_datasets"]["undetermined"]
    if not miss:
        pytest.fail("all required O4 datasets scored: this lane's refusal state no longer holds; update the test with the "
                    "official matrix lane (never by weakening the refusal)")
    with pytest.raises(M.MatrixRefused) as e:
        M.build(M.DEFAULT_ROOT)
    assert sorted(e.value.missing + e.value.undetermined) == sorted(miss)
    for i in miss:
        assert i in str(e.value)


def test_missing_set_is_exactly_the_unscored_registered_datasets(preview):
    rd = preview["required_datasets"]
    assert len(rd["required"]) == 18 and rd["undetermined"] == [] and rd["not_required_trigger_not_fired"] == []
    unscored = sorted(set(rd["required"]) - set(rd["scored"]))
    assert sorted(rd["missing"]) == unscored
    for i in rd["missing"]:
        m = i[len("ds_"):]
        assert not os.path.exists(os.path.join(VAL, f"{CAMPAIGN}_{m}_scores_provenance.json"))
    assert set("ds_" + m for m in SCORED_11) <= set(rd["scored"])


def test_refusal_on_synthetic_root_lists_missing_first_stage_and_undetermined(tmp_path):
    keep = [m for m in SCORED_11 if "rot_off" not in m]
    r = _synthetic_root(tmp_path, keep)
    with pytest.raises(M.MatrixRefused) as e:
        M.build(r)
    assert "ds_staged_n2_n_rot_off" in e.value.missing
    assert sorted(e.value.undetermined) == sorted(["ds_escalation_n2_n_rot_off_di_lower", "ds_escalation_n2_n_rot_off_nel_wang",
                                                   "ds_escalation_n2_n_rot_off_di_lower_nel_wang"])
    p = M.build(r, preview=True)
    assert p["families"]["n2_n_rot_off.toml"]["all_required_scored"] is False
    assert all(x["required"] == "UNDETERMINED" for x in p["rows"] if x["family"] == "n2_n_rot_off.toml" and x["stage"] == "escalation")


def test_cli_refuses_with_exit_2_and_writes_nothing(tmp_path, capsys):
    before = set(os.listdir(HERE))
    assert M.main([]) == 2
    assert "REFUSED" in capsys.readouterr().err
    assert set(os.listdir(HERE)) == before
    assert not os.path.exists(os.path.join(HERE, M.OFFICIAL_NAME))


# --------------------------------------------------------------------------------------------------------------- hashes
def test_all_checks_passed_and_hash_rows_match_files(preview):
    prov = preview["provenance"]
    assert prov["all_checks_passed"] is True and prov["n_checks"] == len(prov["checks"]) > 11 * 20
    rows = {d["dataset"]: d for d in prov["datasets"]}
    for m in SCORED_11:
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
    r = _synthetic_root(tmp_path, SCORED_11)
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
    r = _synthetic_root(tmp_path, SCORED_11)
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
    r = _synthetic_root(tmp_path, SCORED_11)
    v = os.path.join(r, "hallthruster_bridge", "validation")
    os.makedirs(os.path.join(v, "interrupted"))
    bait = os.path.join(v, "interrupted", "bait.json")
    open(bait, "w").write("{}")
    link = os.path.join(v, f"{CAMPAIGN}_escalation_n2_n_n2dication_nel_wang_scores_provenance.json")
    os.symlink(bait, link)
    with pytest.raises(M.ProvenanceError, match="interrupted"):
        M.guard(M.Paths(r), link)


def test_decoy_files_in_interrupted_do_not_count_as_scored(tmp_path):
    r = _synthetic_root(tmp_path, SCORED_11)
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
    for m in SCORED_11:
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
    keep = [m for m in SCORED_11 if "johnsonlow" in m or "rot_off" in m]
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


def test_no_matrix_file_committed():
    assert not os.path.exists(os.path.join(HERE, M.OFFICIAL_NAME))
    assert sorted(os.listdir(HERE)) == sorted(n for n in os.listdir(HERE) if n in (
        "README.md", "build_o4_disposition_matrix.py", "o4_disposition_matrix_schema_v1.json", "__pycache__"))


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


def test_no_forbidden_wording(preview):
    for f in ("README.md", "build_o4_disposition_matrix.py", "o4_disposition_matrix_schema_v1.json"):
        text = open(os.path.join(HERE, f)).read()
        assert not FORBIDDEN.findall(text), f
    assert not FORBIDDEN.findall(open(__file__).read().replace("promote|promoted|promotes|promoting|validated|admitted", ""))
    hits = [s for s in _strings(preview) if FORBIDDEN.search(s)]
    assert not hits, hits[:5]
