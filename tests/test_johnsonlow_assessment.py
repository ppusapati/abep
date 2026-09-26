"""fo_johnsonlow_escalation_assessment: the committed assessment is reproducible from the frozen O4 datasets, its totals equal
the scored staged_escalation blocks, every provenance hash holds, and it carries no forbidden wording."""
import hashlib, importlib.util, json, os, re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
HERE = os.path.join(ROOT, "docs", "o4", "johnsonlow_assessment")
VAL = os.path.join(ROOT, "hallthruster_bridge", "validation")
JS = os.path.join(HERE, "johnsonlow_assessment_v1.json")
MD = os.path.join(HERE, "JOHNSONLOW_ASSESSMENT.md")
STEMS = {"n2_n_exc_johnsonlow.toml": ("staged_n2_n_exc_johnsonlow", "n2_n.toml"),
         "n2_n_exc_johnsonlow_di_lower.toml": ("escalation_n2_n_exc_johnsonlow_di_lower", "n2_n_di_lower.toml"),
         "n2_n_exc_johnsonlow_nel_wang.toml": ("escalation_n2_n_exc_johnsonlow_nel_wang", "n2_n_nel_wang.toml"),
         "n2_n_exc_johnsonlow_di_lower_nel_wang.toml": ("escalation_n2_n_exc_johnsonlow_di_lower_nel_wang",
                                                        "n2_n_di_lower_nel_wang.toml")}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _mod():
    spec = importlib.util.spec_from_file_location("jla_build", os.path.join(HERE, "build_johnsonlow_assessment.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def built():
    return _mod().build()


@pytest.fixture(scope="module")
def res():
    return json.load(open(JS))


def test_reproducible(built):
    js, md = built
    assert js == open(JS).read(), "johnsonlow_assessment_v1.json is not reproduced by the build script"
    assert md == open(MD).read(), "JOHNSONLOW_ASSESSMENT.md is not reproduced by the build script"
    assert _mod().main(["--check"]) == 0


def test_provenance_hashes():
    mprov = json.load(open(os.path.join(VAL, "p5_n2_campaign_v1_vacuum_scores_provenance.json")))
    assert sha(os.path.join(VAL, "p5_n2_campaign_v1_vacuum_scores.json")) == mprov["output_sha256"]
    for sens, (stem, base) in STEMS.items():
        prov = json.load(open(os.path.join(VAL, f"p5_n2_campaign_v1_{stem}_scores_provenance.json")))
        assert sha(os.path.join(VAL, f"p5_n2_campaign_v1_{stem}_scores.json")) == prov["output_sha256"]
        assert prov["mandatory_reproduced"] is True
        assert prov["mandatory_scores_sha256"] == mprov["output_sha256"]
        assert prov["input_mandatory_sha256"] == mprov["input_sha256_canonical_jsonl"]
        assert prov["o4"].get("baseline", prov["o4"].get("compare_with")) == base


def test_provenance_recorded(res):
    assert res["provenance"]["all_checks_passed"] is True
    assert all(c["ok"] for c in res["provenance"]["checks"])
    for row in res["provenance"]["datasets"]:
        assert sha(os.path.join(ROOT, row["provenance"])) == row["provenance_sha256"]
        assert sha(os.path.join(ROOT, "hallthruster_bridge", row["scores"])) == row["scores_sha256"]


def test_totals_equal_scored_blocks(res):
    by = {c["sensitivity"]: c for c in res["combinations"]}
    assert set(by) == set(STEMS)
    for sens, (stem, base) in STEMS.items():
        blk = json.load(open(os.path.join(VAL, f"p5_n2_campaign_v1_{stem}_scores.json")))["staged_escalation"][sens]
        c = by[sens]
        assert c["baseline"] == blk["baseline"] == base
        assert c["trigger_fired"] == blk["trigger_fired"]
        t = c["run_level_triggers"]
        assert t["n_entries_total"] == len(blk["run_level_triggers"])
        assert sum(t["by_kind"].values()) == len(blk["run_level_triggers"])
        kinds = {}
        for _, text in blk["run_level_triggers"]:
            kinds[text.split()[0]] = kinds.get(text.split()[0], 0) + 1
        assert t["by_kind"] == kinds
        for grp in ("by_point", "by_candidate", "by_registration", "by_coil_shape"):
            assert sum(sum(v.values()) for v in t[grp].values()) == len(blk["run_level_triggers"]), grp
        vc = c["verdict_changes"]
        assert vc["detail"] == blk["verdict_changes"]
        assert vc["n_member_changes"] == sum(len(x["members"]) for x in blk["verdict_changes"].values())
        assert c["scored_block_reproduced_by_frozen_scorer"] is True
        # status transitions: every pair counted once per reading; changed-status count matches the status entries
        for rd in ("A", "B"):
            assert sum(c["status_transitions"][rd].values()) == c["n_pairs"]
            assert sum(c["status_transitions_changed_only"][rd].values()) == t["by_kind_and_reading"].get(f"status|{rd}", 0)
    assert res["answer"]["material_on_every_primary_combination"] == all(
        c["trigger_fired"] for c in res["combinations"])


def test_rule_precedes_results():
    md = open(MD).read()
    assert md.index("## Rule used") < md.index("## Answer") < md.index("## 1. Per baseline combination")


def test_no_forbidden_wording():
    for p in (JS, MD, os.path.join(HERE, "build_johnsonlow_assessment.py")):
        text = open(p).read().lower()
        for w in ("promote", "validated", "nominal replacement"):
            assert w not in text, f"forbidden wording '{w}' in {os.path.basename(p)}"
        assert not re.search(r"\bwinner\b", text)
