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

import importlib.util
import json
import math
import re
import subprocess
import sys
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
    counts = {k: sum(1 for q in D["evidence_placements"] + D["not_placeable"] if q["placement"] == k)
              for k in B.PLACEMENTS}
    assert counts == D["placement_counts"]


def test_classification_rule_hand_cases():
    ymax = {"add_only": 1000.0, "cost_offset": 1500.0, "optimistic_bound": 2000.0}
    ymin = {"add_only": 100.0, "cost_offset": 110.0, "optimistic_bound": 110.0}
    assert B.classify(2500.0, 2500.0, ymax, ymin, 0.1, 0.5)["placement"] == "CLEARLY_ABOVE_BREAKEVEN"
    below = B.classify(5.0, 5.0, ymax, ymin, 0.1, 0.5)          # 5 / (0.5 * 0.1) = 100 <= 100
    assert below["placement"] == "CLEARLY_BELOW_BREAKEVEN" and below["below_cases"] == list(B.CASES)
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


def test_prose_claims_match_the_json():
    """The hand-written prose states these results; they must still hold."""
    assert all(p["placement"] == "STRADDLES" for p in D["evidence_placements"])
    assert D["placement_counts"]["CLEARLY_ABOVE_BREAKEVEN"] == 0 == D["placement_counts"]["CLEARLY_BELOW_BREAKEVEN"]
    assert not any(D["region"]["structural"]["clearly_below_reachable_over_full_eta_t_range"].values())
    assert D["region"]["answer"]["entries_paying_everywhere_chain_1_eta_t_1"] == ["ECR-D018", "ECR-D019"]
    assert D["region"]["answer"]["all_N2_entries_in_could_pay_region_chain_1_every_case"] is True
    assert D["region"]["answer"]["any_N2_entry_pays_everywhere_chain_1_eta_t_1"] is False
    assert D["triage"]["n_entries"] == 165
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
