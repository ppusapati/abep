"""Tests for the RF break-even overlay (docs/architecture_comparison/overlays/rf/, overlay_rf_v1).

The checks on the committed files need nothing but this checkout. The reproduction test rebuilds the overlay from its
sha256-pinned inputs (other lanes' files, found in this checkout or in sibling worktrees) and skips with the reason when
they cannot be found: the tests never require the input lanes to be present.
"""
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIR = os.path.join(ROOT, "docs", "architecture_comparison", "overlays", "rf")
SCRIPT = os.path.join(DIR, "build_overlay_rf.py")
JSON_PATH = os.path.join(DIR, "overlay_rf_v1.json")
MD_PATH = os.path.join(DIR, "RF_BREAKEVEN_OVERLAY.md")
CASES = ["add_only", "cost_offset", "optimistic_bound"]
PLACED = {"CLEARLY_ABOVE_BREAKEVEN", "CLEARLY_BELOW", "STRADDLES"}


def _load_script():
    spec = importlib.util.spec_from_file_location("_overlay_rf_build_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bo():
    return _load_script()


@pytest.fixture(scope="module")
def overlay():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text():
    with open(MD_PATH, encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------------------------------------ committed files
def test_boundary_architecture_and_milestone(overlay):
    assert overlay["boundary_version"] == "bus_power_boundary_v1"
    assert overlay["overlay_version"] == "overlay_rf_v1"
    assert overlay["architecture"] == "rf_hall" and overlay["reference_architecture"] == "hall_only"
    assert "never plasma-absorbed" in overlay["power_basis"] and "source-only" in overlay["power_basis"]
    assert "discharge-only" in overlay["power_basis"]
    ms = overlay["milestone_support"]
    assert ms["supports"] == ["A"] and ms["to_reach_B"] and ms["to_reach_C"]
    assert overlay["milestone_A_statement"]["supports"] == "A"
    assert overlay["milestone_A_statement"]["conditions_for_rf_hall_as_baseline"]
    assert list(overlay["cases"]) == CASES


def test_inputs_are_pinned(overlay):
    for k, v in overlay["inputs"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", v["sha256"]), k
        assert v["path"] and not os.path.isabs(v["path"]), k      # repository-relative, never a worktree path
        assert ".claude" not in v["path"], k


def test_self_checks_all_pass(overlay):
    assert overlay["self_checks"]
    failed = [k for k, v in overlay["self_checks"].items() if not v["pass"]]
    assert not failed, failed


def test_every_placement_has_chain_or_missing_quantity(overlay):
    units = overlay["evidence_placements"]
    assert units
    for u in units:
        assert u["placement"]["status"] in PLACED, u["unit_id"]
        assert u["power_reference"] in ("absorbed", "forward", "bus"), u["unit_id"]
        chain = u["conversion_chain"]
        assert chain, u["unit_id"]
        for st in chain:
            assert st.get("step") and st.get("status"), u["unit_id"]
            if st["status"].startswith("missing"):
                assert st.get("missing_quantity"), (u["unit_id"], st["step"])
        # the last step refers source-exit ions to delivered ions through eta_t (lane 18 range and basis)
        assert "eta_t" in chain[-1]["step"]
        assert u["eta_t"]["range"] == overlay["eta_transport"]["range"] and u["eta_t"]["basis"]
        C = u["C_src_bus_W_per_A"]
        assert C["basis"] and C["lo"] is not None and C["lo"] >= 0.0
        assert "C_del_bus_W_per_delivered_A" in u
        assert set(u["placement"]["per_case_over_declared_box"]) == set(CASES)
        assert u["decisive_measurements"]["single_measurements"]
        for rv in ("value", "units", "evidence_class"):
            assert rv in u["reported"], (u["unit_id"], rv)
    for x in overlay["not_placeable"]:
        assert x["status"] == "NOT_PLACEABLE"
        assert x["reason"] and x["missing_quantity"], x["id"]
        assert x["entry"]["citation"], x["id"]
    counts = overlay["placement_counts"]
    assert counts["NOT_PLACEABLE"] == len(overlay["not_placeable"])
    assert sum(counts[p] for p in PLACED) == len(units)


def test_eta_transport_basis_from_lane_18(overlay):
    et = overlay["eta_transport"]
    assert et["model"] == "interstage_v1"
    assert et["range"][0] > 0.0 and et["range"][1] == 1.0
    assert "PROPOSED" in et["range_class"]
    assert et["air_value"].startswith("TBD")
    assert et["upper_bound_basis"] and et["lower_bound_basis"] and "CURRENT" in et["ion_basis"]


def test_placements_follow_the_stated_rule(bo, overlay):
    """Recompute every status from the committed numbers with the script's rule."""
    lo_t, hi_t = overlay["eta_transport"]["range"]
    box = overlay["tables"]["Y_box"]
    for u in overlay["evidence_placements"]:
        C = u["C_src_bus_W_per_A"]
        per = {c: bo.classify(C["lo"], C["hi"], C["lo_open"], box[c][0], box[c][1], lo_t, hi_t) for c in CASES}
        assert per == u["placement"]["per_case_over_declared_box"], u["unit_id"]
        assert bo.overall(per)[0] == u["placement"]["status"], u["unit_id"]
        if C["hi"] is None:     # an unbounded cost can never be placed CLEARLY_BELOW
            assert u["placement"]["status"] != "CLEARLY_BELOW"


def test_breakeven_statement_names_X_Y_Z(overlay):
    bc = overlay["breakeven_condition"]
    assert "ONLY IF" in bc["statement"]
    for k in ("X", "Y", "Z"):
        assert bc[k], k
    t = overlay["tables"]
    for tab in ("Y_bus_W_per_delivered_A", "X_required_relative_gain", "coupled_X_interval", "Z_min_eta_t"):
        vals = t[tab]["values"]
        for c in CASES:
            assert any(k == c or k.startswith(c + "|") for k in vals), (tab, c)


def test_generated_markdown_block_matches_json(bo, overlay, md_text):
    """The generated block of the page is a pure function of the committed JSON."""
    i, j = md_text.find(bo.MD_BEGIN), md_text.find(bo.MD_END)
    assert 0 <= i < j
    assert md_text[i:j + len(bo.MD_END)] == bo.md_block(overlay)


FORBIDDEN = [
    r"\bis the winner\b", r"\bwinner is\b", r"\bwins\b", r"\boutperform", r"\bsuperior\b", r"\brecommend",
    r"\bbetter than\b", r"\bshould be selected\b", r"\bis selected\b", r"\bis eliminated\b", r"\beliminates\b",
    r"\beliminated\b", r"\brf_hall is preferable\b", r"\bpredicts?\b", r"\bpredicted\b", r"\branked\b",
]


@pytest.mark.parametrize("path", [JSON_PATH, MD_PATH])
def test_no_forbidden_wording(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    low = text.lower()
    for pat in FORBIDDEN:
        assert not re.search(pat, low), (os.path.basename(path), pat)
    # the other pre-ionized arm is not discussed at all
    assert not re.search(r"\becr", low), os.path.basename(path)
    # 'winner' only ever negated
    for m in re.finditer(r"winner", low):
        assert re.search(r"\bno( |\s\w+\s)winner", low[max(0, m.start() - 12):m.end()]), low[m.start() - 40:m.end()]
    # 'preferable' only in the owner's ONLY-IF form of the necessary condition
    for m in re.finditer(r"preferable", low):
        assert "only if" in low[m.end():m.end() + 60], low[m.start() - 40:m.end() + 60]


# ------------------------------------------------------------------------------------------------ pure functions
def test_classify_rule(bo):
    assert bo.classify(300.0, 400.0, False, 100.0, 200.0, 0.1, 1.0) == "ABOVE"
    assert bo.classify(200.0, 400.0, True, 100.0, 200.0, 0.1, 1.0) == "ABOVE"      # open lower end at the edge
    assert bo.classify(200.0, 400.0, False, 100.0, 200.0, 0.1, 1.0) == "STRADDLES"
    assert bo.classify(1.0, 10.0, False, 100.0, 200.0, 0.1, 1.0) == "BELOW"
    assert bo.classify(1.0, None, False, 100.0, 200.0, 0.1, 1.0) == "STRADDLES"
    assert bo.overall({"add_only": "STRADDLES", "cost_offset": "BELOW", "optimistic_bound": "BELOW"}) == \
        ("CLEARLY_BELOW", "cost_offset")
    assert bo.overall({c: "ABOVE" for c in CASES}) == ("CLEARLY_ABOVE_BREAKEVEN", None)


def test_payable_interval_closed_forms(bo):
    # add_only (n = d = 1): c x^2 - (1 - wf - c) x + wf <= 0
    for c, wf in ((0.5, 0.0), (0.3, 0.05), (0.2, 0.1)):
        iv = bo.payable_x_interval(1.0, 1.0, c, wf)
        A = 1.0 - wf - c
        disc = A * A - 4.0 * c * wf
        lo = 0.0 if wf == 0.0 else (A - disc ** 0.5) / (2.0 * c)
        assert iv == pytest.approx([lo, (A + disc ** 0.5) / (2.0 * c)], abs=1e-12)
    # exactly marginal (c = 2n - d) pays only in the limit; above it nothing pays
    assert bo.payable_x_interval(1.0, 1.0, 1.0, 0.0) is None
    assert bo.payable_x_interval(1.0, 0.7, 1.3, 0.0) is None
    assert bo.payable_x_interval(1.0, 0.7, 1.29, 0.0) is not None
    assert bo.payable_x_interval(1.0, 1.0, 0.9, 0.2) is None


def test_missing_or_changed_input_raises(bo, monkeypatch):
    monkeypatch.setitem(bo.INPUTS["rf_evidence_matrix"], "sha256", "0" * 64)
    with pytest.raises(bo.OverlayInputError):
        bo.resolve_inputs([])


# ------------------------------------------------------------------------------------------------ reproduction
def test_json_and_markdown_reproduce_from_pinned_inputs(bo):
    try:
        bo.resolve_inputs([])
    except bo.OverlayInputError as exc:
        pytest.skip(f"pinned overlay inputs not available in this checkout or its worktrees: {exc}")
    o = bo.build([])
    with open(JSON_PATH, encoding="utf-8") as f:
        assert f.read() == bo.render(o), "overlay_rf_v1.json differs from a fresh build (run the script)"
    with open(MD_PATH, encoding="utf-8") as f:
        assert f.read() == bo.merged_md(bo.md_block(o)), "generated block of RF_BREAKEVEN_OVERLAY.md is stale"
