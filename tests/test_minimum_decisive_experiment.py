"""Lane 25 (MINEXP): minimum decisive Hall-only / RF+Hall / ECR+Hall experiment draft.

Checks the machine-readable draft (schema-like validation), that every threshold is PROPOSED, that the Hall
accelerator, cathode, feed state and bus boundary are identical across arms, and that the uncertainty propagation and
every derived number reproduce from the committed deterministic script. Pure, fast, no Julia, no other lane required.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import random
from pathlib import Path
from statistics import NormalDist

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "architecture_comparison" / "minimum_decisive_experiment"
JSON_PATH = DIR / "experiment_draft.json"
MD_PATH = DIR / "MINIMUM_DECISIVE_EXPERIMENT_DRAFT.md"
SCRIPT_PATH = DIR / "minexp_numbers.py"

ARCH_IDS = ["hall_only", "rf_hall", "ecr_hall"]
BOUNDARY_VERSION = "bus_power_boundary_v1"
COMMON_COMPONENTS = ["hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control",
                     "compressor", "thermal_control", "housekeeping"]
ARM_COMPONENTS = {"hall_only": [], "rf_hall": ["rf_source"], "ecr_hall": ["ecr_source", "ecr_magnet"]}
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
TBD_PREFIXES = ("TBD - requires", "TBD — requires")
REQUIRED_TOP = ["schema", "id", "status", "lane", "created", "base_commit", "scope", "rules_compliance", "milestones",
                "architectures", "common_elements", "hardware_configurations", "bus_power_boundary",
                "comparison_grid_axes", "operating_points", "knee_scan", "run_matrix", "decisive_quantities",
                "derived_metrics", "break_even", "measurements", "uncertainty", "planning_grids", "thresholds",
                "randomization", "repeatability", "facility_controls", "facility_split", "decision_tree",
                "preregistration", "hardware_minimum", "related_lanes", "open_owner_decisions", "references",
                "derived_numbers"]


@pytest.fixture(scope="module")
def draft() -> dict:
    with open(JSON_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def mx():
    spec = importlib.util.spec_from_file_location("minexp_numbers_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def md() -> str:
    return MD_PATH.read_text(encoding="utf-8")


def _walk(obj, path="$"):
    yield path, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ------------------------------------------------------------------------------------------------ schema-like checks
def test_top_level_structure_and_status(draft, md):
    missing = [k for k in REQUIRED_TOP if k not in draft]
    assert not missing, f"missing top-level keys: {missing}"
    assert draft["schema"] == "abep_minimum_decisive_experiment_draft_v1"
    assert draft["status"] == "DRAFT_PENDING_OWNER"
    assert "DRAFT_PENDING_OWNER" in md and "PROPOSED" in md
    assert draft["derivation_script"].endswith("minexp_numbers.py") and SCRIPT_PATH.is_file()
    assert "not" in draft["not_frozen"].lower() and "pre-regist" in draft["not_frozen"].lower()


def test_architecture_ids_and_bus_boundary_contract(draft):
    assert [a["id"] for a in draft["architectures"]] == ARCH_IDS
    bpb = draft["bus_power_boundary"]
    assert bpb["version"] == BOUNDARY_VERSION
    assert bpb["components_common"] == COMMON_COMPONENTS
    assert bpb["components_arm_specific"] == ARM_COMPONENTS
    assert bpb["api"] == "ledger(arch, loads, efficiencies)"
    names = set(COMMON_COMPONENTS) | {c for v in ARM_COMPONENTS.values() for c in v}
    assert set(bpb["measured_in_experiment"]) == names
    for a in draft["architectures"]:
        assert a["bus_boundary"] == BOUNDARY_VERSION
        assert a["arm_specific_bus_components"] == ARM_COMPONENTS[a["id"]]


def test_identical_accelerator_feed_cathode_across_arms(draft):
    arms = draft["architectures"]
    for key in ("accelerator", "feed_state", "cathode", "bus_boundary"):
        assert len({a[key] for a in arms}) == 1, f"{key} differs between arms"
    assert [a["pre_ionizer"] for a in arms] == ["none", "RF", "ECR"]
    configs = {h["id"]: h for h in draft["hardware_configurations"]}
    for a in arms:
        assert configs[a["hardware_configuration"]]["arm"] == a["id"]
    ce = draft["common_elements"]
    assert ce["accelerator"]["id"] == arms[0]["accelerator"]
    assert ce["cathode"]["id"] == arms[0]["cathode"]
    assert ce["feed_state"]["id"] == arms[0]["feed_state"]
    assert "IF-A5" in ce["feed_state"]["fields"]


def test_operating_points_share_feed_state_across_arms(draft):
    ops = {o["id"]: o for o in draft["operating_points"]}
    rows = draft["run_matrix"]["conditions"]
    assert len({r["id"] for r in rows}) == len(rows)
    arm_of_hw = {a["hardware_configuration"]: a["id"] for a in draft["architectures"]}
    for r in rows:
        assert r["op"] in ops, r
        assert arm_of_hw[r["hw"]] == r["arm"], r
        assert r["source"] in ops[r["op"]]["P_source_levels"], r
        if r["arm"] == "hall_only":
            assert r["source"] == "off"
    # the two source arms visit exactly the same (op, source, role, stage) set: the pre-ionizer is the only change
    sig = {a: sorted((r["op"], r["source"], r["role"], r["stage"], tuple(r["families"]), bool(r.get("confirmation_subset")))
                     for r in rows if r["arm"] == a) for a in ("rf_hall", "ecr_hall")}
    assert sig["rf_hall"] == sig["ecr_hall"]
    # every compared point has a hall_only baseline on HW-0 at the same operating point
    base_ops = {r["op"] for r in rows if r["arm"] == "hall_only" and r["role"] == "baseline"}
    compared = {r["op"] for r in rows if "primary" in r["families"]}
    assert compared <= base_ops
    # iso-power references differ from their partner points only in V_d
    for iso, partner in (("OP2H", "OP2"), ("OP3H", "OP3")):
        assert ops[iso]["mdot"] == ops[partner]["mdot"]
        assert ops[iso]["composition"] == ops[partner]["composition"]
        assert ops[iso]["V_d"] != ops[partner]["V_d"]
        assert ops[iso]["P_source_levels"] == ["off"]
    iso_ops = {r["op"] for r in rows if "iso_power" in r["families"]}
    assert iso_ops == {"OP2", "OP3"}
    # every 'hi' in the confirmation subset has its installed-off partner
    for a in ("rf_hall", "ecr_hall"):
        sub = {(r["op"], r["source"]) for r in rows if r["arm"] == a and r.get("confirmation_subset")}
        for op, src in sub:
            if src == "hi":
                assert (op, "off") in sub


def test_grid_axes_and_nuisance_never_axes(draft):
    axes = draft["comparison_grid_axes"]
    assert {"mdot", "p", "V_d", "composition", "P_source"} <= set(axes)
    ens = json.loads((ROOT / "hallthruster_bridge" / "ensemble" / "transport_ensemble_v0.json").read_text())
    nuisance = set(ens["calibration_nuisance"])
    assert set(axes["never_axes"]) == nuisance
    assert not (set(axes) - {"never_axes"}) & nuisance
    for o in draft["operating_points"]:
        assert not set(o) & nuisance
    for r in draft["run_matrix"]["conditions"]:
        assert not set(r) & nuisance
    # feed-envelope values are TBD, never invented
    assert axes["mdot"]["values"].startswith(TBD_PREFIXES)
    assert axes["V_d"]["values"].startswith(TBD_PREFIXES)
    assert axes["P_source"]["values"].startswith("P_hi: TBD")


# ------------------------------------------------------------------------------------------- thresholds and rules
def test_every_threshold_is_proposed(draft):
    ths = draft["thresholds"]
    assert ths, "no thresholds"
    ids = [t["id"] for t in ths]
    assert len(ids) == len(set(ids))
    for t in ths:
        assert t["status"] == "PROPOSED", t["id"]
        has_value, has_rule = "value" in t, "rule" in t
        assert has_value or has_rule, t["id"]
        if has_value and _is_num(t["value"]):
            assert t["evidence_class"] == "assumed", t["id"]
            assert t["source"], t["id"]
        elif has_value:
            assert t["value"].startswith(TBD_PREFIXES), t["id"]
    # every decision refers to existing threshold ids or carries its own PROPOSED status
    decisions = draft["decision_tree"]["decisions"]
    stage_ids = {s["id"] for s in draft["decision_tree"]["stages"]}
    for d in decisions:
        refs = [tok for tok in d["rule"].replace(",", " ").split() if tok.startswith("T-")]
        assert all(r in ids for r in refs), d
        assert refs or d.get("status") == "PROPOSED", d
        for part in d["after"].split("+"):
            assert part in stage_ids, d


def test_stop_rules_are_measurement_based_and_no_winner(draft):
    th = {t["id"]: t for t in draft["thresholds"]}
    stop = th["T-STOP-RULE"]["rule"]
    assert "SOURCE_WORSE" in stop and "C_del > C_star" in stop and "EQUIVALENT never stops" in stop
    assert "never stops an arm" in th["T-SCREEN-RULE"]["rule"]
    gate = next(d for d in draft["decision_tree"]["decisions"] if d["id"] == "G-SRC")
    assert "measured" in gate["rule"]
    classes = draft["decision_tree"]["classes"]
    for c in classes["per_point"] + classes["per_arm"] + classes["qualifiers"]:
        assert not any(w in c.upper() for w in ("WIN", "BEST", "SELECT", "BASELINE"))
    stages = {s["id"]: s for s in draft["decision_tree"]["stages"]}
    assert stages["S0"]["score_bearing"] is False and stages["S1"]["score_bearing"] is False
    assert all(stages[s]["score_bearing"] for s in ("S2", "S3", "S4", "S5", "S6"))
    d0 = next(d for d in draft["decision_tree"]["decisions"] if d["id"] == "D0")
    assert d0["after"] == "S1" and "OWNER" in d0["outcomes"]["fail"]


def test_milestones_declared(draft):
    ms = draft["milestones"]
    assert ms["supports"] == ["A", "B"]
    assert ms["A"]["delivers"] and ms["A"]["to_reach"]
    assert ms["B"]["delivers"] and ms["B"]["still_needed"]
    assert ms["C"]["still_needed"]


# ------------------------------------------------------------------------------------------- evidence discipline
def test_every_numeric_value_has_source_and_evidence_class(draft):
    for path, node in _walk(draft):
        if not isinstance(node, dict):
            continue
        if "value" in node:
            v = node["value"]
            if _is_num(v):
                assert node.get("evidence_class") in EVIDENCE_CLASSES, path
                assert isinstance(node.get("source"), str) and node["source"], path
            elif isinstance(v, str):
                assert v.startswith(TBD_PREFIXES), path
        if "values" in node and isinstance(node["values"], list) and any(_is_num(x) for x in node["values"]):
            assert node.get("evidence_class") in EVIDENCE_CLASSES, path
            assert node.get("source"), path


def test_references_record_access(draft):
    refs = draft["references"]
    ids = {r["id"] for r in refs}
    for r in refs:
        assert r["citation"] and r["accessed"] and r["access"] and r["used_for"], r["id"]
        assert r.get("doi") or r.get("url") or r["id"] == "REF-REPO", r["id"]
    blob = json.dumps(draft)
    for rid in ids:
        if rid != "REF-REPO":
            assert blob.count(rid) >= 2, f"{rid} listed but never used"
    # sources that were not fully read are labelled as such
    by = {r["id"]: r for r in refs}
    assert "verify" in by["REF-SNYDER2017"]["access"]
    assert "not bypassed" in by["REF-SHABSHELOWITZ2014"]["access"]


def test_other_lanes_referenced_not_required(draft):
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    for mod in ("arch_boundary", "arch_compare", "thermal_life", "archengine", "hall_map", "hall_ensemble"):
        assert f"import {mod}" not in src and f"abep_sim.{mod}" not in src
    assert "not imported" in draft["bus_power_boundary"]["module"]
    # optional cross-check, only when the other lane's module is present in this checkout
    ab = ROOT / "abep_sim" / "arch_boundary.py"
    if ab.is_file():
        text = ab.read_text(encoding="utf-8")
        assert BOUNDARY_VERSION in text
        for comp in COMMON_COMPONENTS + [c for v in ARM_COMPONENTS.values() for c in v]:
            assert comp in text, comp


# --------------------------------------------------------------------------------- derivations and propagation
def test_derived_numbers_reproduce(draft, mx):
    computed = mx.derive(copy.deepcopy(draft))
    errs = mx.compare(mx._strip(computed), mx._strip(draft["derived_numbers"]))
    assert not errs, "\n".join(errs)


def test_uncertainty_propagation_independent_recompute(draft):
    """Recompute the headline numbers without the script, from the PROPOSED thresholds and the run matrix."""
    th = {t["id"]: t.get("value") for t in draft["thresholds"]}
    rows = draft["run_matrix"]["conditions"]
    m = sum("primary" in r["families"] for r in rows)
    m_iso = sum("iso_power" in r["families"] for r in rows)
    assert (m, m_iso) == (14, 8)
    dn = draft["derived_numbers"]
    z = NormalDist().inv_cdf(1 - th["T-ALPHA-FW"] / (2 * m))
    s_max = th["T-DELTA"] / (2 * z)
    share = s_max / math.sqrt(th["T-VAR-GROUPS"])
    assert math.isclose(dn["z_fw_primary"]["value"], z, rel_tol=1e-5)
    assert math.isclose(dn["sigma_lnR_max"]["value"], s_max, rel_tol=1e-5)
    assert math.isclose(dn["sigma_group_max"]["value"], share, rel_tol=1e-5)
    for n_str, node in dn["u_reading_max_by_n"].items():
        assert math.isclose(node["value"], share * math.sqrt(int(n_str) / 2), rel_tol=1e-5)
    for f_str, node in dn["u_source_scale_max_by_f_src"].items():
        assert math.isclose(node["value"], share / float(f_str), rel_tol=1e-5)
    z_iso = NormalDist().inv_cdf(1 - th["T-ALPHA-FW"] / (2 * m_iso))
    assert math.isclose(dn["sigma_lnR_max_iso"]["value"], th["T-DELTA"] / (2 * z_iso), rel_tol=1e-5)
    assert math.isclose(dn["z_screen_one_sided"]["value"], NormalDist().inv_cdf(1 - th["T-ALPHA-SCREEN"]), rel_tol=1e-5)
    # n_required: 4u^2 / (sigma^2 - 3 shares) -> even ceiling, at least T-N-MIN
    for d_str, row in dn["n_required"].items():
        d_alt = float(d_str.split("=")[1])
        smax_alt = d_alt / (2 * z)
        room = smax_alt ** 2 * (1 - 3 / th["T-VAR-GROUPS"])
        for u_str, node in row.items():
            u = float(u_str.split("=")[1])
            raw = 4 * u ** 2 / room
            k = math.ceil(raw - 1e-12)
            assert node["value"] == max(th["T-N-MIN"], k + k % 2)
            assert node["within_T_N_MAX"] == (node["value"] <= th["T-N-MAX"])


def test_budget_closes_at_allocated_maxima(draft, mx):
    """sigma_lnR() with every group exactly at its allocated share returns sigma_max (budget and model agree)."""
    dn = draft["derived_numbers"]
    share = dn["sigma_group_max"]["value"]
    n = 4
    u = dn["u_reading_max_by_n"][str(n)]["value"]
    f_src = 0.2
    sig = mx.sigma_lnR(u_T=u, u_P=u, n=n, f_src=f_src, u_src_scale=share / f_src, w_common=0.5,
                       u_common_scale=share / 0.5, u_remount=share)
    assert math.isclose(sig, dn["sigma_lnR_max"]["value"], rel_tol=1e-4)
    with pytest.raises(ValueError):
        mx.sigma_lnR(u_T=None, u_P=u, n=n, f_src=f_src, u_src_scale=0.0, w_common=0.0, u_common_scale=0.0,
                     u_remount=0.0)


def test_classification_exhaustive_below_half_delta(draft, mx):
    delta = next(t["value"] for t in draft["thresholds"] if t["id"] == "T-DELTA")
    rng = random.Random(20260926)
    for _ in range(20000):
        x = rng.uniform(-4 * delta, 4 * delta)
        h = rng.uniform(0.0, 0.4999 * delta)
        assert mx.classify(x, h, delta) != "UNRESOLVED"
    assert mx.classify(0.0, 0.3 * delta, delta) == "EQUIVALENT"
    assert mx.classify(2 * delta, 0.3 * delta, delta) == "SOURCE_BETTER"
    assert mx.classify(-2 * delta, 0.3 * delta, delta) == "SOURCE_WORSE"
    assert mx.classify(0.5 * delta, 0.6 * delta, delta) == "UNRESOLVED"
    chk = draft["derived_numbers"]["classification_check"]
    assert chk["unresolved_count_h_below_half_delta"]["value"] == 0
    assert chk["unresolved_count_h_above_half_delta"]["value"] > 0


def test_breakeven_identity_synthetic(mx):
    """R_arch > 1 <=> C_del < C_star (algebraic identity; synthetic vectors, not physical values)."""
    rng = random.Random(7)
    for _ in range(5000):
        T0, P0 = rng.uniform(1, 50), rng.uniform(100, 2000)
        I_del, V_d, eta_d = rng.uniform(0.01, 2), rng.uniform(100, 500), rng.uniform(0.5, 1.0)
        dT = rng.uniform(-0.5, 2) * T0
        dI_d = rng.uniform(-1, 3) * I_del
        P_src = rng.uniform(1, 800)
        dP_other = rng.uniform(-20, 50)
        R = mx.ratio_R(T0, P0, dT, V_d * dI_d, eta_d, P_src, dP_other)
        c_star = mx.breakeven_cost(dT / I_del, P0 / T0, dI_d / I_del, V_d, eta_d, dP_other / I_del)
        c_del = P_src / I_del
        P1 = P0 + V_d * dI_d / eta_d + P_src + dP_other
        if P1 <= 0 or T0 + dT <= 0 or abs(c_del - c_star) < 1e-9 * max(1.0, abs(c_star)):
            continue
        assert (R > 1) == (c_del < c_star)
    with pytest.raises(ValueError):
        mx.ratio_R(1, 1, 0, 0, None, 1, 0)
    with pytest.raises(ValueError):
        mx.breakeven_cost(1, 1, 0, 1, 0.0, 0)


def test_physics_helpers_reproduce_stated_values(draft, mx):
    c = mx.load_constants()
    dn = draft["derived_numbers"]
    y_n2 = math.sqrt(2 * c.M_SPECIES["N2"] * 1.0 / c.E_CHARGE) * 1e3
    assert math.isclose(dn["y_max_per_sqrtV"]["N2+"]["value"], y_n2, rel_tol=1e-5)
    S = (1e-6 / c.M_SPECIES["N2"]) * c.K_B * 300.0 / (1e-5 * 101325.0 / 760.0) * 1e3
    assert math.isclose(dn["S_eff_required_per_mgps"]["N2"]["1.0e-05 Torr"]["value"], S, rel_tol=1e-5)
    with pytest.raises(ValueError):
        mx.z_two_sided_bonferroni(0.05, 0)


def test_missing_or_unproposed_inputs_raise(draft, mx):
    d1 = copy.deepcopy(draft)
    d1["thresholds"] = [t for t in d1["thresholds"] if t["id"] != "T-DELTA"]
    with pytest.raises(KeyError):
        mx.derive(d1)
    d2 = copy.deepcopy(draft)
    next(t for t in d2["thresholds"] if t["id"] == "T-DELTA")["status"] = "APPROVED_BY_NOBODY"
    with pytest.raises(ValueError):
        mx.derive(d2)
    d3 = copy.deepcopy(draft)
    d3["planning_grids"]["f_src"]["values"] = []
    with pytest.raises(ValueError):
        mx.derive(d3)


def test_markdown_states_the_same_numbers(draft, md):
    dn = draft["derived_numbers"]
    expected = [
        f'{dn["z_fw_primary"]["value"]:.4f}',
        f'{dn["sigma_lnR_max"]["value"]:.5f}',
        f'{dn["sigma_group_max"]["value"]:.5f}',
        f'{dn["z_fw_iso"]["value"]:.4f}',
        f'{dn["sigma_lnR_max_iso"]["value"]:.5f}',
        f'{dn["z_screen_one_sided"]["value"]:.4f}',
        f'{dn["run_counts"]["hall_on_conditions_total"]["value"]} Hall-on conditions per block',
        f'{dn["run_counts"]["hall_on_readings_full_at_n_min"]["value"]} readings',
        f'{dn["run_counts"]["hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min"]["value"]} readings',
    ]
    expected += [f'{100 * v["value"]:.2f} %' for v in dn["u_reading_max_by_n"].values()]
    expected += [f'{100 * v["value"]:.2f} %' for v in dn["u_source_scale_max_by_f_src"].values()]
    expected += [f'{v["value"]:.3g}' for v in dn["delta_floor_by_s_nonaveraging"].values()]
    expected += [f'{v["value"]:.4f}' for v in dn["y_max_per_sqrtV"].values()]
    expected += [f'{v["value"]:,.0f} L/s' for g in dn["S_eff_required_per_mgps"].values() for v in g.values()]
    missing = [s for s in expected if s not in md]
    assert not missing, f"markdown lacks derived numbers: {missing}"
