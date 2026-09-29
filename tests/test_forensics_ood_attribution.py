"""Non-gating forensics: P5-N2 v1 vacuum OUT_OF_DOMAIN attribution (scripts/forensics/p5_n2_v1_ood_attribution.py).

Runs the script into temporary directories and checks that
  * its totals reconcile with the OFFICIAL result (714 OOD runs, 1428 OOD run-readings, per-candidate OOD counts equal to
    the official report and the official scores file),
  * its internal breakdowns add up to those totals,
  * the output is deterministic (two runs give byte-identical JSON and Markdown),
  * the hypothetical ladder is labelled as such and the committed outputs are the script's current output.
"""
import collections, json, os, subprocess, sys

import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "forensics", "p5_n2_v1_ood_attribution.py")
VAL = os.path.join(ROOT, "hallthruster_bridge", "validation")
COMMITTED = os.path.join(ROOT, "docs", "forensics", "p5_n2_v1", "ood_attribution")
OFFICIAL_OOD_RUNS = 714
OFFICIAL_OOD_RUN_READINGS = 1428


def _run(out_dir):
    subprocess.run([sys.executable, SCRIPT, "--out-dir", str(out_dir)], check=True, capture_output=True, timeout=120)
    with open(os.path.join(out_dir, "ood_attribution.json"), "rb") as f:
        j = f.read()
    with open(os.path.join(out_dir, "OOD_ATTRIBUTION.md"), "rb") as f:
        m = f.read()
    return j, m


@pytest.fixture(scope="module")
def outputs(tmp_path_factory):
    a, b = tmp_path_factory.mktemp("ood_a"), tmp_path_factory.mktemp("ood_b")
    ja, ma = _run(a)
    jb, mb = _run(b)
    return {"json_a": ja, "json_b": jb, "md_a": ma, "md_b": mb, "d": json.loads(ja)}


def _official_report_ood_by_candidate():
    """Parse the official report's 'vacuum by candidate' table independently of the script."""
    text = open(os.path.join(VAL, "p5_n2_campaign_v1_vacuum_scores_report.md")).read()
    out, col = {}, None
    for line in text.splitlines():
        if line.startswith("| vacuum by candidate"):
            col = [h.strip() for h in line.strip("|").split("|")].index("OUT_OF_DOMAIN")
            continue
        if col is not None:
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells[0].startswith("sgb-"):
                out[cells[0]] = int(cells[col])
    return out


def _official_scores():
    return json.load(open(os.path.join(VAL, "p5_n2_campaign_v1_vacuum_scores.json")))


def test_deterministic(outputs):
    assert outputs["json_a"] == outputs["json_b"]
    assert outputs["md_a"] == outputs["md_b"]


def test_inputs_are_the_frozen_release(outputs):
    checks = outputs["d"]["input_integrity_checks"]
    assert checks and all(checks.values()), [k for k, v in checks.items() if not v]


def test_totals_reconcile_with_official_counts(outputs):
    rc = outputs["d"]["reconciliation"]
    sc = _official_scores()
    assert sc["status_counts"]["vacuum"]["OUT_OF_DOMAIN"] == OFFICIAL_OOD_RUN_READINGS
    assert rc["n_records"] == 1080 and rc["n_run_readings_in_scores_file"] == 2160
    assert rc["n_OOD_runs"] == OFFICIAL_OOD_RUNS
    assert rc["n_OOD_run_readings"] == OFFICIAL_OOD_RUN_READINGS
    assert rc["official_status_counts_vacuum"] == sc["status_counts"]["vacuum"]
    assert rc["OOD_status_reading_independent"] and rc["n_runs_with_reading_dependent_OOD"] == 0
    assert rc["input_consistency_OOD_predicate_on_raw_fields_agrees_with_official_label"]
    assert rc["input_consistency_n_disagreements"] == 0


def test_per_candidate_ood_equals_official_report(outputs):
    rc = outputs["d"]["reconciliation"]
    report = _official_report_ood_by_candidate()
    by_scores = collections.Counter(r["key"].split("|")[0] for r in _official_scores()["runs"] if r["status"] == "OUT_OF_DOMAIN")
    assert len(report) == 9 and sum(report.values()) == OFFICIAL_OOD_RUN_READINGS
    assert set(rc["per_candidate"]) == set(report)
    for c, n in report.items():
        v = rc["per_candidate"][c]
        assert v["official_OOD_run_readings_from_report"] == n
        assert v["official_OOD_run_readings_from_scores_file"] == n == by_scores[c]
        assert 2 * v["OOD_runs"] == n
        assert outputs["d"]["breakdown"]["candidate"][c]["n_OOD_runs"] == n // 2
    assert rc["per_candidate_matches_report"]


def test_breakdowns_add_up(outputs):
    d = outputs["d"]
    for fac in ("candidate", "point", "chemistry", "registration", "coil_shape"):
        assert sum(v["n_OOD_runs"] for v in d["breakdown"][fac].values()) == OFFICIAL_OOD_RUNS, fac
        assert sum(v["n_runs"] for v in d["breakdown"][fac].values()) == 1080, fac
    assert sum(d["co_occurrence"]["category_counts_OOD_runs"].values()) == OFFICIAL_OOD_RUNS
    assert sum(d["co_occurrence"]["subfamily_pattern_counts"].values()) == OFFICIAL_OOD_RUNS
    assert sum(d["co_occurrence"]["beyond_set_size_histogram"].values()) == OFFICIAL_OOD_RUNS
    for rd in ("A", "B"):
        n = sum(m["n_OOD"] for c in d["breakdown"]["candidate_x_member"].values()
                for k, m in c["members"].items() if k.endswith("|" + rd))
        assert n == OFFICIAL_OOD_RUNS
    for c in d["breakdown"]["candidate_x_member"].values():
        for m in c["members"].values():
            assert m["n_runs"] == 20 and m["n_OOD"] + m["n_FAIL_VALIDATION"] + m["n_PASS"] + m["n_NUMERICAL_FAILURE"] == 20
    member_totals = d["breakdown"]["global_layer1_member"]
    assert sum(v["n_OOD_runs"] for k, v in member_totals.items() if k.endswith("|A")) == OFFICIAL_OOD_RUNS
    rr = d["official_status_crosstab"]["run_readings_by_category"]
    assert sum(n for cat, v in rr.items() if cat != "IN_DOMAIN" for n in v.values()) == OFFICIAL_OOD_RUN_READINGS
    assert all(set(v) == {"OUT_OF_DOMAIN"} for cat, v in rr.items() if cat != "IN_DOMAIN")


def test_attribution_is_consistent(outputs):
    d = outputs["d"]
    co = d["co_occurrence"]
    assert co["n_OOD_runs_beyond_set_within_45eV_family"] == OFFICIAL_OOD_RUNS
    assert co["n_runs_any_file_outside_45eV_family_beyond"] == 0
    assert co["n_runs_any_255eV_file_beyond"] == 0
    assert sum(d["per_file"][f]["n_runs_f_out_gt_tol"] for f in co["limit_families"]["255 eV"]) == 0
    assert d["per_file"]["dissociation_N2.dat"]["n_runs_f_out_gt_tol"] == OFFICIAL_OOD_RUNS
    col = d["official_status_crosstab"]["sustainment_collapse_co_occurrence"]
    assert col["check_pattern_equals_official_SUSTAINMENT_reason_on_in_domain_runs"]


def test_hypothetical_ladder_is_labelled_and_monotone(outputs):
    hy = outputs["d"]["hypothetical_limit_ladder_45eV_family"]
    assert hy["label"].startswith("HYPOTHETICAL COUNTING ONLY - not a scoring, not a verdict, not a proposal to change limits")
    assert "HYPOTHETICAL COUNTING ONLY" in outputs["md_a"].decode()
    ladder = hy["ladder"]
    assert [r["hypothetical_limit_mean_energy_eV"] for r in ladder] == [45.0, 60.0, 75.0, 90.0, 120.0, 150.0, 200.0, 255.0]
    counts = [r["n_runs_all_45eV_files_eps_active_le_L"] for r in ladder]
    assert counts == sorted(counts) and counts[-1] <= 1080
    ec = hy["empirical_concordance_at_the_recorded_45eV_limit"]
    assert ec["proxy_evaluable_subset_of_officially_in_domain"]
    assert ladder[0]["n_officially_OOD_runs_with_all_45eV_files_eps_active_le_L"] == 0


def test_no_forbidden_wording(outputs):
    md = outputs["md_a"].decode().lower()
    for w in ("best candidate", "recommended candidate", "promote", "would pass"):
        assert w not in md, w


def test_committed_outputs_are_current(outputs):
    with open(os.path.join(COMMITTED, "ood_attribution.json"), "rb") as f:
        assert f.read() == outputs["json_a"]
    with open(os.path.join(COMMITTED, "OOD_ATTRIBUTION.md"), "rb") as f:
        assert f.read() == outputs["md_a"]
