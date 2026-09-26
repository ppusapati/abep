"""Tests for the ECR break-even overlay (overlay_ecr_v1, follow-on fo_ecr_breakeven_overlay).

The committed JSON is recomputed two ways:
  * independently of the other lanes' files, from the values recorded in the JSON itself, with the pure functions of
    build_overlay_ecr.py (always runs);
  * byte-for-byte by the full build against the pinned inputs (skipped when the pinned inputs cannot be resolved; the
    inputs are other lanes' deliverables and this test must not require them).
Also: every placement carries its conversion chain or its missing-quantity note, the boundary is
bus_power_boundary_v1, and no output uses wording that would state a result the overlay does not produce.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs" / "architecture_comparison" / "overlays" / "ecr"
SCRIPT = HERE / "build_overlay_ecr.py"
JSON_PATH = HERE / "overlay_ecr_v1.json"
MD_PATH = HERE / "ECR_BREAKEVEN_OVERLAY.md"
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")


def _load_script():
    name = "_test_overlay_ecr_build"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


B = _load_script()
D = json.loads(JSON_PATH.read_text(encoding="utf-8"))
MD = MD_PATH.read_text(encoding="utf-8")


def close(a, b, rel=2e-5, abs_=1e-9):
    """Stored values are rounded to 6 significant digits."""
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


# ------------------------------------------------------------------------------------------------ reproducibility
def test_script_imports_no_other_lane_module():
    """Importing the builder loads nothing from abep_sim (the pinned modules are resolved lazily in build())."""
    code = ("import importlib.util, sys; "
            f"s = importlib.util.spec_from_file_location('ov', {str(SCRIPT)!r}); "
            "m = importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "print(sorted(k for k in sys.modules if k == 'abep_sim' or k.startswith('abep_sim.')))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=60)
    assert out.stdout.strip() == "[]", out.stdout


def test_json_records_current_script_hash():
    assert D["provenance"]["script_sha256"] == B._sha(SCRIPT.read_bytes()), \
        "overlay_ecr_v1.json is stale: rerun build_overlay_ecr.py"


def test_full_rebuild_is_byte_identical():
    if not B.inputs_available():
        pytest.skip("pinned input lanes (08, 18, 20, 28) not resolvable in this checkout")
    text, block = B.build()
    assert text == JSON_PATH.read_text(encoding="utf-8")
    assert B._splice_md(MD, block) == MD


def test_missing_or_changed_input_raises(monkeypatch):
    bad = dict(B.INPUTS)
    bad["ecr_evidence_matrix"] = {**bad["ecr_evidence_matrix"], "sha256": "0" * 64}
    monkeypatch.setattr(B, "INPUTS", bad)
    with pytest.raises(B.OverlayInputError):
        B.read_input("ecr_evidence_matrix")


def _fake_input(monkeypatch, tmp_path, checkout_bytes, git_result):
    """One synthetic input pinned to sha256(b'pinned'); the checkout is tmp_path; git is replaced by a fake."""
    rel = "docs/fake/input.json"
    monkeypatch.setattr(B, "REPO", tmp_path)
    monkeypatch.setattr(B, "INPUTS", {"fake": {"path": rel, "lane": "lane_x", "commit": "abc1234",
                                               "sha256": hashlib.sha256(b"pinned").hexdigest(), "role": "test"}})
    if checkout_bytes is not None:
        (tmp_path / rel).parent.mkdir(parents=True)
        (tmp_path / rel).write_bytes(checkout_bytes)
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        rc, out = git_result
        return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr=b"")
    monkeypatch.setattr(B, "subprocess", types.SimpleNamespace(run=run))
    return calls


def test_changed_checkout_input_never_falls_back_to_pinned_commit(monkeypatch, tmp_path):
    """Review blocker: a present file with another sha256 must raise, even when the pinned object is reachable."""
    calls = _fake_input(monkeypatch, tmp_path, b"changed", (0, b"pinned"))
    with pytest.raises(B.OverlayInputChangedError):
        B.read_input("fake")
    assert calls == [], "the pinned git object must not be consulted when the checkout file exists"
    with pytest.raises(B.OverlayInputChangedError):     # the full-rebuild test fails; it does not skip
        B.inputs_available()


def test_absent_input_uses_pinned_object_or_reports_missing(monkeypatch, tmp_path):
    _fake_input(monkeypatch, tmp_path, None, (0, b"pinned"))
    assert B.read_input("fake") == b"pinned" and B.inputs_available() is True
    _fake_input(monkeypatch, tmp_path / "b", None, (128, b""))
    with pytest.raises(B.OverlayInputMissingError):
        B.read_input("fake")
    assert B.inputs_available() is False                 # the only case in which the full rebuild skips
    _fake_input(monkeypatch, tmp_path / "c", None, (0, b"other bytes"))
    with pytest.raises(B.OverlayInputChangedError):
        B.read_input("fake")


def test_check_fails_on_input_error(monkeypatch, capsys):
    def boom():
        raise B.OverlayInputChangedError("changed")
    monkeypatch.setattr(B, "build", boom)
    assert B.main(["--check"]) != 0
    assert "FAILED" in capsys.readouterr().out


def test_generated_tables_are_spliced_between_markers():
    assert MD.count(B.MD_BEGIN) == 1 and MD.count(B.MD_END) == 1
    block = MD.split(B.MD_BEGIN, 1)[1].split(B.MD_END, 1)[0]
    assert B._md_block(D).strip() == block.strip()


# ------------------------------------------------------------------ independent recomputation from recorded values
def test_slices_and_box_extremes_recompute():
    bc = D["breakeven_condition"]
    ar = D["analysis_ranges"]
    for name, sl in bc["hall_reference_slices"].items():
        assert close(B.pi_h(sl["V_d_V"], sl["eta_b"], sl["eta_ppu_d"]), sl["Pi_H_W_per_A"])
        for c in B.CASES:
            assert close(B.slice_Y(sl, c), sl["Y_W_per_A"][c]), (name, c)
    box = [(V, eb, pp, ev) for V in ar["V_d_V"] for eb in ar["eta_b"] for pp in ar["eta_ppu_d"]["values"]
           for ev in ar["eta_v_optimistic"]]
    for c in B.CASES:
        ys = [B.pi_h(V, eb, pp) * (2 * B.case_rp(c, eb, ev)[0] - B.case_rp(c, eb, ev)[1]) for V, eb, pp, ev in box]
        assert close(max(ys), bc["box_extremes_W_per_A"]["Y_max_by_case"][c])
        assert close(min(ys), bc["box_extremes_W_per_A"]["Y_min_by_case"][c])
        assert close(max(ys), bc["hall_reference_slices"]["most_favourable_corner"]["Y_W_per_A"][c])
        assert close(min(ys), bc["hall_reference_slices"]["least_favourable_corner"]["Y_W_per_A"][c])


def _rp_from_key(key):
    parts = key.split("|")
    kv = dict(p.split("=") for p in parts[1:])
    return B.case_rp(parts[0], float(kv.get("eta_b", 0.7)), float(kv.get("eta_v", D["analysis_ranges"]["eta_v_mid"])))


def test_x_y_z_tables_recompute():
    ar = D["analysis_ranges"]
    tb = D["breakeven_condition"]["tables"]
    for key, rows in tb["Y_over_Pi_H_vs_X"]["values"].items():
        r, p = _rp_from_key(key)
        for wf_key, vals in rows.items():
            wf = float(wf_key.split("=")[1])
            for x, v in zip(ar["X_grid"], vals):
                assert close(B.y_payable(x, r, p, wf), v, abs_=1e-6), (key, wf, x)
    for key, vals in tb["X_star_vs_omega"]["values"].items():
        r, p = _rp_from_key(key)
        for w, v in zip(ar["omega_grid"], vals):
            assert close(B.x_star(w, r, p), v)
    for key, rows in tb["payable_X_interval"]["values"].items():
        r, p = _rp_from_key(key)
        for wf_key, ivs in rows.items():
            wf = float(wf_key.split("=")[1])
            for y, iv in zip(ar["Y_over_Pi_H_grid"], ivs):
                mine = B.share_interval(y, wf, r, p)
                assert (mine is None) == (iv is None), (key, wf, y)
                if iv is not None:
                    assert close(mine[0], iv[0], abs_=1e-7) and close(mine[1], iv[1], abs_=1e-7)
    for s, byc in tb["Z_vs_C_src_bus"]["values"].items():
        Ys = D["breakeven_condition"]["hall_reference_slices"][s]["Y_W_per_A"]
        for c, vals in byc.items():
            for C, v in zip(ar["C_src_bus_grid_W_per_A"], vals):
                assert close(B.eta_t_needed(C, Ys[c]), v)


def test_breakeven_v1_hand_points():
    """Hand-calculated points of BREAKEVEN_DERIVATION.md Sec. 12 in this overlay's relative form."""
    assert B.x_star(0.1, 1.0, 1.0) == pytest.approx(0.1 / 0.9)                       # item 1: eta_u0 omega/(1-omega)
    assert 0.5 * B.x_star(0.1, 1.0, 0.7) == pytest.approx(0.0424990, abs=1e-7)          # item 2 (eta_u0 = 0.5)
    assert B.g_payable(0.0, *B.case_rp("optimistic_bound", 0.7, 0.9)) == pytest.approx(603.51 / 428.571, rel=1e-5)
    assert B.g_payable(0.0, *B.case_rp("cost_offset", 0.7, 0.9)) == pytest.approx(1.3)  # item 5
    assert B.g_payable(0.1, 1.0, 1.0) == pytest.approx(389.61 / 428.571, rel=1e-5)     # item 4 (x = 0.05/0.5)
    for wf in (0.01, 0.05, 0.2):                                                        # add_only closed form
        assert B.y_sup(1.0, 1.0, wf, 100.0)[0] == pytest.approx((1 - math.sqrt(wf)) ** 2)


def test_placements_recompute_from_recorded_costs():
    bx = D["breakeven_condition"]["box_extremes_W_per_A"]
    ch = D["bus_chain_evidence"]["reference_chain"]["value"]
    lo = D["interstage_eta_t_basis"]["range"][0]
    for p in D["evidence_placements"]:
        t = p["placement_test_costs_W_per_A"]
        cls = B.classify(t["c_above"], t["c_below"], bx["Y_max_by_case"], bx["Y_min_by_case"], lo, ch)
        assert cls["placement"] == p["placement"] and cls["by_case"] == p["placement_by_case"], p["id"]
        dc = p["declared_basis"]["cost_W_per_A"]
        if p["declared_basis"]["phi_kind"] == "assumed":
            assert t["c_above"] == dc[0]
        else:       # a declared value that is only an upper bound cannot support CLEARLY_ABOVE
            assert t["c_above"] == p["ionization_floor_W_per_A"] <= dc[0]
        assert t["c_below"] == dc[1]
        assert close(p["bus_cost_W_per_A"]["at_reference_chain"][0], dc[0] / ch)
        assert p["bus_cost_W_per_A"]["chain_1_on_declared_basis"] == dc
        assert "lower_bound_chain_1" not in p["bus_cost_W_per_A"]
    counts = {k: sum(1 for q in D["evidence_placements"] + D["not_placeable"] if q["placement"] == k)
              for k in B.PLACEMENTS}
    assert counts == D["placement_counts"]


def test_classification_rule_hand_cases():
    ymax = {"add_only": 1000.0, "cost_offset": 1500.0, "optimistic_bound": 2000.0}
    ymin = {"add_only": 100.0, "cost_offset": 110.0, "optimistic_bound": 110.0}
    assert B.classify(2500.0, 2500.0, ymax, ymin, 0.1, 0.5)["placement"] == "CLEARLY_ABOVE_BREAKEVEN"
    below = B.classify(5.0, 5.0, ymax, ymin, 0.1, 0.5)          # 5 / (0.5 * 0.1) = 100 <= 100
    assert below["placement"] == "CLEARLY_BELOW" and below["below_cases"] == list(B.CASES)
    mixed = B.classify(1200.0, 1200.0, ymax, ymin, 0.1, 0.5)     # above add_only only
    assert mixed["placement"] == "STRADDLES" and mixed["by_case"]["add_only"] == "ABOVE"
    with pytest.raises(ValueError):
        B.case_rp("add_only", 0.0, 0.9)
    with pytest.raises(ValueError):
        B.case_rp("unknown_case", 0.7, 0.9)


def test_region_recomputes():
    bx = D["breakeven_condition"]["box_extremes_W_per_A"]
    reg = D["region"]
    for c in B.CASES:
        for t, v in zip(reg["axes"]["eta_t"], reg["by_case"][c]["could_pay_somewhere_in_box"]["C_src_bus_max_W_per_A"]):
            assert close(t * bx["Y_max_by_case"][c], v)
        for t, v in zip(reg["axes"]["eta_t"], reg["by_case"][c]["pays_everywhere_in_box"]["C_src_bus_max_W_per_A"]):
            assert close(t * bx["Y_min_by_case"][c], v)
    for row in reg["evidence_in_region"]:
        p = next(q for q in D["evidence_placements"] if q["id"] == row["id"])
        c0 = p["declared_basis"]["cost_W_per_A"][0]
        for c in B.CASES:
            assert row["by_case"][c]["pays_everywhere_chain_1_eta_t_1"] == (c0 <= bx["Y_min_by_case"][c])
            w = row["by_case"][c]["eta_t_window_chain_1"]
            assert (w is None) == (c0 > bx["Y_max_by_case"][c]) and (w is None or close(w[0], c0 / bx["Y_max_by_case"][c]))


def test_placement_labels_are_the_shared_contract():
    """Brief and sibling overlays: CLEARLY_ABOVE_BREAKEVEN, CLEARLY_BELOW, STRADDLES, NOT_PLACEABLE."""
    assert B.PLACEMENTS == ("CLEARLY_ABOVE_BREAKEVEN", "CLEARLY_BELOW", "STRADDLES", "NOT_PLACEABLE")
    assert list(D["placement_counts"]) == list(B.PLACEMENTS)
    assert set(D["placement_rules"]) >= set(B.PLACEMENTS)
    text = json.dumps(D) + MD
    assert "CLEARLY_BELOW_BREAKEVEN" not in text


def test_upper_bound_entries_carry_the_tightness_caveat():
    ids_ub = set()
    for p in D["evidence_placements"]:
        ub = p["declared_basis"]["phi_kind"] != "assumed"
        assert p["declared_cost_is_upper_bound"] is ub, p["id"]
        q = p["negative_readings_qualifier"]
        assert "declared basis" in q and "ionization floor" in q, p["id"]
        if ub:
            ids_ub.add(p["id"])
            assert "UPPER bound" in q and "tight" in q, p["id"]
            assert p["bus_cost_W_per_A"]["chain_1_bound_type"].startswith("not a bound"), p["id"]
        else:
            assert p["bus_cost_W_per_A"]["chain_1_bound_type"].startswith("lower bound"), p["id"]
    assert ids_ub == {"ECR-D021", "ECR-D023"}
    for r in D["region"]["evidence_in_region"]:
        p = next(q for q in D["evidence_placements"] if q["id"] == r["id"])
        assert r["declared_cost_is_upper_bound"] == p["declared_cost_is_upper_bound"]
        assert r["negative_readings_qualifier"] == p["negative_readings_qualifier"]
    assert "tight" in D["region"]["answer"]["condition"]
    for i in ids_ub:                                     # G6-G9 mark them
        assert f"| {i} † |" in MD, i
    for g in ("### G7", "### G8"):
        sec = MD.split(g, 1)[1].split("### G", 1)[0]
        assert "†" in sec and "tight" in sec, g


def test_below_side_carries_the_small_share_qualifier():
    assert "small delivered shares" in D["placement_rules"]["CLEARLY_BELOW"]
    assert "supremum over X" in D["placement_rules"]["CLEARLY_ABOVE_BREAKEVEN"]
    for p in D["evidence_placements"]:
        assert "small delivered shares" in p["to_definite_placement"][0]["note_below"]
        assert "small delivered shares" in p["to_definite_placement"][2]["note"]
        assert "small delivered shares" in p["to_definite_placement"][3]["moves_to"]
    assert "small delivered shares" in D["region"]["answer"]["paying_everywhere_qualifier"]
    least = D["breakeven_condition"]["hall_reference_slices"]["least_favourable_corner"]
    for r in D["region"]["evidence_in_region"]:
        p = next(q for q in D["evidence_placements"] if q["id"] == r["id"])
        lo, hi = p["declared_basis"]["cost_W_per_A"]
        for c in B.CASES:
            rp = B.case_rp(c, least["eta_b"], least["eta_v"])
            pih = B.pi_h(least["V_d_V"], least["eta_b"], least["eta_ppu_d"])    # exact inputs (X_hi is edge-sensitive)
            xs = [B.share_interval(v / pih, 0.0, *rp) for v in (lo, hi)]
            got = r["by_case"][c]["X_hi_least_favourable_corner_chain_1_eta_t_1"]
            if xs[0] is None:
                assert got is None
            else:
                assert close(got[1], xs[0][1]) and (got[0] is None if xs[1] is None else close(got[0], xs[1][1]))
    lim = D["region"]["answer"]["paying_everywhere_share_limit"]
    assert set(lim) == set(D["region"]["answer"]["entries_paying_everywhere_chain_1_eta_t_1"])
    ms = " ".join(D["milestone_A_statement"]["can_conclude_now"])
    assert "only for small delivered shares" in ms


def test_clearly_below_rule_is_reported_as_empty_by_construction():
    st = D["region"]["structural"]
    bx = D["breakeven_condition"]["box_extremes_W_per_A"]
    ch = D["bus_chain_evidence"]["reference_chain"]["value"]
    lo = D["interstage_eta_t_basis"]["range"][0]
    floors = [v["value_W_per_A"] for v in D["ionization_floor"]["values"].values()]
    for c in B.CASES:
        assert close(st["clearly_below_max_declared_cost_W_per_A"][c], ch * lo * bx["Y_min_by_case"][c])
    assert st["category_empty_by_rule"] is (max(st["clearly_below_max_declared_cost_W_per_A"].values()) < min(floors))
    assert st["category_empty_by_rule"] is True
    od = {o["id"]: o for o in D["owner_decisions_requested"]}
    d1 = od["D1_clearly_below_rule"]
    assert "empty by construction" in d1["plain_statement"] and "not a bound" in d1["reference_chain_note"]
    for key, rd in d1["alternative_readings"].items():
        want = {}
        for p in D["evidence_placements"]:
            cu = p["declared_basis"]["cost_W_per_A"][1]
            div = {"as_proposed_reference_chain_eta_t_lo": ch * lo, "reference_chain_eta_t_1": ch,
                   "lossless_chain_eta_t_1": 1.0}[key]
            cs = [c for c in B.CASES if cu / div <= bx["Y_min_by_case"][c]]
            if cs:
                want[p["id"]] = cs
        assert rd["outcome"] == want, key
    assert d1["alternative_readings"]["as_proposed_reference_chain_eta_t_lo"]["outcome"] == {}
    assert "empty by construction" in " ".join(D["milestone_A_statement"]["can_conclude_now"])
    assert "empty by construction" in MD.split("## Generated tables", 1)[0]


def test_eta_ppu_d_axis_is_an_owner_decision():
    ar = D["analysis_ranges"]
    od = {o["id"]: o for o in D["owner_decisions_requested"]}["D2_eta_ppu_d_axis"]
    assert od["used_values"] == ar["eta_ppu_d"]["values"]
    ev = ar["eta_ppu_d"]["evidence"]
    assert od["used_values"] == [ev["min"], ev["max"]] and ev["min_point"]["lowest_power_of_curve"] is True
    pp = od["breakeven_v1_value"]
    box = [(V, eb, pp, e) for V in ar["V_d_V"] for eb in ar["eta_b"] for e in ar["eta_v_optimistic"]]
    for c in B.CASES:
        ys = [B.pi_h(V, eb, q) * (2 * B.case_rp(c, eb, e)[0] - B.case_rp(c, eb, e)[1]) for V, eb, q, e in box]
        assert close(max(ys), od["box_extremes_at_breakeven_v1_value_W_per_A"]["Y_max_by_case"][c])
        assert close(min(ys), od["box_extremes_at_breakeven_v1_value_W_per_A"]["Y_min_by_case"][c])
    assert od["box_extremes_used_W_per_A"] == {k: D["breakeven_condition"]["box_extremes_W_per_A"][k]
                                               for k in ("Y_max_by_case", "Y_min_by_case")}
    ch = D["bus_chain_evidence"]["reference_chain"]["value"]
    lo = D["interstage_eta_t_basis"]["range"][0]
    changed = []
    ext = od["box_extremes_at_breakeven_v1_value_W_per_A"]
    for p in D["evidence_placements"]:
        t = p["placement_test_costs_W_per_A"]
        alt = B.classify(t["c_above"], t["c_below"], ext["Y_max_by_case"], ext["Y_min_by_case"], lo, ch)
        if alt["placement"] != p["placement"] or alt["by_case"] != p["placement_by_case"]:
            changed.append(p["id"])
    assert changed == [q["id"] for q in od["placements_that_change_at_breakeven_v1_value"]]
    assert "D2_eta_ppu_d_axis" in ar["eta_ppu_d"]["note"]


def test_n2_entry_status_is_qualified():
    st = {p["id"]: p["evidence_status"] for p in D["evidence_placements"]}
    assert st["ECR-E081"] == "published_value_definition_unresolved"
    assert st["ECR-E083"] == "model_output_not_measurement"
    assert st["ECR-D020"] == "published_value"
    for p in D["evidence_placements"]:
        if p["reported"]["evidence_class"] == "model-derived":
            assert p["evidence_status"] == "model_output_not_measurement", p["id"]
        cc = p["consistency_check"]
        if cc is not None and not cc["consistent"]:
            assert p["evidence_status"] == "published_value_definition_unresolved", p["id"]
    ans = D["region"]["answer"]
    assert ans["N2_published_values_with_resolved_definition"] == ["ECR-D020"]
    assert ans["N2_entry_status"] == {i: st[i] for i in ("ECR-D020", "ECR-E081", "ECR-E083")}
    ms = " ".join(D["milestone_A_statement"]["can_conclude_now"])
    assert "ECR-E081 is definition-unresolved" in ms and "ECR-E083 is the source's own model output" in ms
    e081 = next(p for p in D["evidence_placements"] if p["id"] == "ECR-E081")
    assert close(8.0 / 596.2, e081["consistency_check"]["implied_current_A"])
    assert e081["consistency_check"]["reported_maximum_current_A"] == 0.0125
    assert "not established" in e081["consistency_check"]["possible_reading"]


def test_stage_lower_bound_is_not_listed_as_chain_upper_bound():
    ch = D["bus_chain_evidence"]
    assert "ECR-E042" not in [s["id"] for s in ch["stage_only_upper_bounds"]]
    ctx = {s["id"]: s for s in ch["stage_only_context_not_a_bound"]}
    assert ctx["ECR-E042"]["bound_on_chain"].startswith("none")
    head = MD.split("## Generated tables", 1)[0]
    assert "ECR-E042 (> 0.70 on a 5 W breadboard) is a *lower* bound on one stage" in head


# ------------------------------------------------------------------------------ conversion chains, missing notes
def test_every_placement_has_conversion_chain_or_missing_note():
    steps_needed = ("reported", "power plane", "ion basis", "bus referral", "transport", "result")
    assert D["evidence_placements"], "no placed entries"
    for p in D["evidence_placements"]:
        chain = p["conversion_chain"]
        assert len(chain) == len(steps_needed), p["id"]
        for want, step in zip(steps_needed, chain):
            assert step["step"].startswith(want) or want in step["step"], (p["id"], step["step"])
            assert any(step["evidence_class"].startswith(ec) for ec in EVIDENCE_CLASSES), (p["id"], step)
            assert step.get("source"), (p["id"], step["step"])
        assert p["power_reference"]["class"] and p["power_reference"]["bus_basis"] is False
        assert p["reported"]["citation"] and p["reported"]["doi_or_url"] and p["reported"]["evidence_class"]
        assert p["missing_quantities"], p["id"]
        assert p["eta_t"]["range"] == D["interstage_eta_t_basis"]["range"]
        assert p["to_definite_placement"], p["id"]
        if p["placement"] == "STRADDLES":
            assert p["straddles_on"], p["id"]
    for q in D["not_placeable"] + D["x_side_context"]:
        assert q["placement"] == "NOT_PLACEABLE" and q["missing_quantities"], q["id"]
    for q in D["not_placeable"]:
        assert q["to_definite_placement"], q["id"]


def test_interstage_and_chain_basis_recorded():
    it = D["interstage_eta_t_basis"]
    assert it["range"][1] == 1.0 and 0.0 < it["range"][0] < 1.0 and it["tbd_inputs"] and it["range_basis"]
    ch = D["bus_chain_evidence"]
    assert ch["lower_bound"].startswith("none sourced") and ch["missing"]
    assert all(s["value"] is not None for s in ch["stage_only_upper_bounds"])
    assert D["ionization_floor"]["evidence_class"] == "model-derived"


def test_triage_covers_every_matrix_entry_once():
    tr = D["triage"]
    ids = (tr["placed_or_not_placeable"] + tr["chain_evidence"] + tr["fixed_overhead_evidence"]
           + list(tr["covered_by"]) + tr["electron_current_not_an_ion_cost"] + tr["other"])
    assert len(ids) == len(set(ids)) == tr["n_entries"]


def test_numbers_carry_sources_and_proposed_ranges_are_labelled():
    ar = D["analysis_ranges"]
    assert "PROPOSED" in ar["status"]
    assert ar["eta_ppu_d"]["evidence"]["evidence_class"] == "digitized" and ar["eta_ppu_d"]["evidence"]["source_ids"]
    assert "PROPOSED" in D["placement_rules"]["status"]
    for inp in D["inputs"]:
        assert re.fullmatch(r"[0-9a-f]{64}", inp["sha256"]) and inp["path"] and inp["commit"]


# ------------------------------------------------------------------------------------- boundary, milestones, text
def test_boundary_is_bus_power_boundary_v1():
    assert D["boundary"]["version"] == "bus_power_boundary_v1" == B.BOUNDARY_VERSION
    assert D["boundary"]["ecr_hall_source_components"] == ["ecr_source", "ecr_magnet"]
    assert "never absorbed RF power" in D["boundary"]["P_bus"]
    assert "bus_power_boundary_v1" in MD
    assert D["architecture"] == "ecr_hall" and D["reference_architecture"] == "hall_only"


def test_milestones_and_statement():
    ms = D["milestones"]
    assert ms["supports"] == ["A"] and ms["to_reach_B"] and ms["to_reach_C"]
    st = D["milestone_A_statement"]
    assert st["can_conclude_now"] and st["explicit_conditions"] and "does not name a baseline" in \
        st["condition_set_for_milestone_A"]
    # milestone A is conditional: the Hall reference and response case are stated conditions, not admitted/measured
    cs = st["condition_set_for_milestone_A"]
    assert "milestone A leaves as stated conditions" in cs and "milestone-B step" in cs
    assert "evaluated at the admitted Hall reference" not in cs
    assert "evaluated at the admitted Hall reference" not in MD


def test_prose_claims_match_the_json():
    """The hand-written prose states these results; they must still hold."""
    assert all(p["placement"] == "STRADDLES" for p in D["evidence_placements"])
    assert D["placement_counts"]["CLEARLY_ABOVE_BREAKEVEN"] == 0 == D["placement_counts"]["CLEARLY_BELOW"]
    assert not any(D["region"]["structural"]["clearly_below_reachable_over_full_eta_t_range"].values())
    assert D["region"]["answer"]["entries_paying_everywhere_chain_1_eta_t_1"] == ["ECR-D018", "ECR-D019"]
    assert D["region"]["answer"]["all_N2_entries_in_could_pay_region_chain_1_every_case"] is True
    assert D["region"]["answer"]["any_N2_entry_pays_everywhere_chain_1_eta_t_1"] is False
    assert D["triage"]["n_entries"] == 165
    lim = D["region"]["answer"]["paying_everywhere_share_limit"]     # numbers quoted in the prose of Sec. 4
    assert f"{lim['ECR-D018']['cost_offset'][0]:.2g}" == "0.0017" == f"{lim['ECR-D018']['optimistic_bound'][0]:.2g}"
    assert [f"{v:.2g}" for v in lim["ECR-D019"]["add_only"]] == ["0.023", "0.044"]
    assert [f"{v:.3g}" for v in lim["ECR-D019"]["cost_offset"]] == ["0.115", "0.136"]
    assert lim["ECR-D019"]["optimistic_bound"] == lim["ECR-D019"]["cost_offset"]
    no_ref_add = sorted(r["id"] for r in D["region"]["evidence_in_region"]
                        if r["by_case"]["add_only"]["eta_t_window_reference_chain"] is None)
    assert no_ref_add == ["ECR-D021", "ECR-E081", "ECR-E083"]
    od = {o["id"]: o for o in D["owner_decisions_requested"]}["D2_eta_ppu_d_axis"]
    assert round(od["box_extremes_at_breakeven_v1_value_W_per_A"]["Y_max_by_case"]["add_only"]) == 1000
    assert round(od["box_extremes_used_W_per_A"]["Y_max_by_case"]["add_only"]) == 1168
    assert od["placements_change"] is False
    e081 = next(p for p in D["evidence_placements"] if p["id"] == "ECR-E081")
    assert e081["consistency_check"]["consistent"] is False
    assert any(q["id"] == "GAP-ECR-O-O2-AIR" for q in D["not_placeable"])


def test_no_forbidden_wording():
    assert D["forbidden_patterns"] == list(B.FORBIDDEN_PATTERNS)
    body = dict(D)
    body.pop("forbidden_patterns")
    texts = {"json": json.dumps(body, ensure_ascii=False), "md": MD}
    hits = [(n, pat, m.group(0)) for n, t in texts.items() for pat in B.FORBIDDEN_PATTERNS
            for m in re.finditer(pat, t, flags=re.IGNORECASE)]
    assert not hits, hits
