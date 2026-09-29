"""Lane 25 (MINEXP): minimum decisive Hall-only / RF+Hall / ECR+Hall experiment draft.

Checks the machine-readable draft (schema-like validation), that every threshold is PROPOSED, that the Hall
accelerator, cathode, feed state and bus boundary are identical across arms, and that the uncertainty propagation and
every derived number reproduce from the committed deterministic script
(Student-t critical values at Welch-Satterthwaite effective degrees of freedom, JCGM 100:2008 Annex G). Pure, fast, no Julia, no other lane required.
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

from scipy.stats import t as student_t  # noqa: E402  (pinned in requirements-lock.txt; no silent skip)

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
    # the implemented callable of the power-boundary lane, not the brief's shorthand
    assert bpb["api"] == "bus_power_ledger(arch, loads, efficiencies)"
    assert "ledger(arch, loads, efficiencies)" in bpb["api_note"]
    names = set(COMMON_COMPONENTS) | {c for v in ARM_COMPONENTS.values() for c in v}
    mie = bpb["measured_in_experiment"]
    assert set(mie) == names
    # every component on the same basis: load plane + ledger efficiency (no lab converter efficiency in R_arch)
    for comp, node in mie.items():
        assert node["load_plane"] and node["load_source"], comp
        assert node["efficiency_source"].startswith("ledger"), comp
    for comp in ("rf_source", "ecr_source"):
        assert "net" in mie[comp]["load_plane"], comp
        assert "never substituted" in mie["rf_source"]["lab_chain_evidence"]
    assert "No lab converter's own efficiency enters the decisive R_arch" in bpb["basis"]
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
        if not has_value:
            continue
        v = t["value"]
        if _is_num(v) or (isinstance(v, dict) and all(_is_num(x) for x in v.values())):
            assert t["evidence_class"] == "assumed", t["id"]
            assert t["source"], t["id"]
        else:
            assert isinstance(v, str) and v.startswith(TBD_PREFIXES), t["id"]
    # budget shares are keyed exactly by the variance groups and sum to 1 (no hidden group count)
    shares = next(t for t in ths if t["id"] == "T-BUDGET-SHARES")["value"]
    assert sorted(shares) == sorted(g["id"] for g in draft["uncertainty"]["variance_groups"])
    assert math.isclose(sum(shares.values()), 1.0)
    assert "T-VAR-GROUPS" not in ids
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
    # the rule is stated on the sign statement (upper bound < 0 <=> C_del > C_star), not on the size class
    assert "upper bound of ln R_arch < 0" in stop and "C_del > C_star" in stop
    assert "not the size class" in stop and "monotone in precision" in stop
    assert "NOT_TESTED" in stop and "STOP-MARGIN" in stop
    assert "never stops an arm" in th["T-SCREEN-RULE"]["rule"]
    gate = next(d for d in draft["decision_tree"]["decisions"] if d["id"] == "G-SRC")
    assert "measured" in gate["rule"]
    classes = draft["decision_tree"]["classes"]
    for c in classes["per_point"] + classes["per_arm"] + classes["qualifiers"]:
        assert not any(w in c.upper() for w in ("WIN", "BEST", "SELECT", "BASELINE"))
    # class set has no gap: all four sustainment combinations of hall_only x source_on are mapped
    combos = {(r["hall_only"], r["source_on"]) for r in classes["sustainment_matrix"]}
    for h in ("SUSTAINED", "NOT_SUSTAINED"):
        for so in ("SUSTAINED", "NOT_SUSTAINED"):
            assert (h, so) in combos
    for c in ("DISABLES", "NEITHER_SUSTAINED", "SUSTAINMENT_MIXED", "NOT_TESTED", "INFEASIBLE_AT_POINT"):
        assert c in classes["per_point"]
    stages = {s["id"]: s for s in draft["decision_tree"]["stages"]}
    assert stages["S0"]["score_bearing"] is False and stages["S1"]["score_bearing"] is False
    assert all(stages[s]["score_bearing"] for s in ("S2", "S3", "S4", "S5", "S6"))
    d0 = next(d for d in draft["decision_tree"]["decisions"] if d["id"] == "D0")
    assert d0["after"] == "S1" and "OWNER" in d0["outcomes"]["fail"] and "LOCK-2" in d0["outcomes"]["pass"]


def test_readiness_is_evaluable_before_score_bearing_runs(draft):
    """G5 (installation) is measured in the non-score-bearing S1b series, not only at S6; two locks."""
    groups = {g["id"]: g for g in draft["uncertainty"]["variance_groups"]}
    assert groups["G5"]["evaluation"] == "type_A_S1_remount"
    s1b = draft["s1_plan"]["S1b_hall_on"]
    assert s1b["score_bearing"] is False and s1b["configuration"] == "HW-0"
    assert "S2, S4 and S5" in s1b["facility"]
    assert any("u_inst" in o for o in s1b["outputs"])
    rd = next(t for t in draft["thresholds"] if t["id"] == "T-READINESS")["rule"]
    assert "S1 values only" in rd and "readiness_n" in rd and "u_inst" in rd
    remount = next(t for t in draft["thresholds"] if t["id"] == "T-REMOUNT-CHECK")["rule"]
    assert "never used to re-estimate u_inst" in remount
    locks = draft["preregistration"]["locks"]
    assert [lk["id"] for lk in locks] == ["LOCK-1", "LOCK-2"]
    assert locks[0]["stage"] == "S0" and "S1" in locks[1]["stage"]
    assert "without discretion" in locks[1]["rule"]
    assert "facility" in draft["facility_split"]["stages"]["S1b_hall_on"]


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


def _ws(components):
    total = sum(v for v, _ in components)
    denom = sum(v * v / nu for v, nu in components if not math.isinf(nu))
    return math.inf if denom == 0 else total * total / denom


def _k_t(alpha, m, nu):
    p = 1 - alpha / (2 * m)
    return NormalDist().inv_cdf(p) if math.isinf(nu) else float(student_t.ppf(p, nu))


def test_uncertainty_propagation_independent_recompute(draft):
    """Recompute the headline numbers without the script: Student-t at Welch-Satterthwaite nu_eff (GUM Annex G)."""
    th = {t["id"]: t.get("value") for t in draft["thresholds"]}
    rows = draft["run_matrix"]["conditions"]
    m = {f: sum(f in r["families"] for r in rows) for f in ("primary", "iso_power", "facility")}
    assert m == {"primary": 14, "iso_power": 8, "facility": 4}
    dn = draft["derived_numbers"]
    shares = th["T-BUDGET-SHARES"]
    evals = {g["id"]: g["evaluation"] for g in draft["uncertainty"]["variance_groups"]}
    w_a = sum(shares[g] for g, e in evals.items() if e == "type_A_in_campaign")
    w_rm = sum(shares[g] for g, e in evals.items() if e == "type_A_S1_remount")
    w_b = sum(shares[g] for g, e in evals.items() if e == "type_B")
    K = th["T-S1-REMOUNT-CYCLES"]
    delta, alpha = th["T-DELTA"], th["T-ALPHA-FW"]
    # the normal quantile is only the known-variance limit, and every planning k exceeds it
    z = NormalDist().inv_cdf(1 - alpha / (2 * m["primary"]))
    assert math.isclose(dn["k_primary_known_variance_limit"]["value"], z, rel_tol=1e-6)
    for n_str, row in dn["plan_by_n"].items():
        n = int(n_str)
        nu = _ws([(w_a / 2, n - 1), (w_a / 2, n - 1), (w_rm, K - 1), (w_b, math.inf)])
        assert math.isclose(row["nu_eff"]["value"], nu, rel_tol=1e-6)
        k = _k_t(alpha, m["primary"], nu)
        assert k > z
        s_max = delta / (2 * k)
        assert math.isclose(row["k_primary"]["value"], k, rel_tol=1e-6)
        assert math.isclose(row["sigma_lnR_max"]["value"], s_max, rel_tol=1e-6)
        assert math.isclose(row["u_T_max"]["value"], s_max * math.sqrt(shares["G1"] * n / 2), rel_tol=1e-6)
        assert math.isclose(row["u_P_max"]["value"], s_max * math.sqrt(shares["G2"] * n / 2), rel_tol=1e-6)
        assert math.isclose(row["u_inst_max"]["value"], s_max * math.sqrt(shares["G5"] / 2), rel_tol=1e-6)
        s_iso = delta / (2 * _k_t(alpha, m["iso_power"], nu))
        assert math.isclose(row["sigma_lnR_max_iso"]["value"], s_iso, rel_tol=1e-6)
        assert math.isclose(row["u_interp_max"]["value"], math.sqrt(s_iso ** 2 - s_max ** 2), rel_tol=1e-6)
        s_fac = delta / (2 * _k_t(alpha, m["facility"], nu))
        assert math.isclose(row["sigma_lnR_max_facility"]["value"], s_fac, rel_tol=1e-6)
    # the reviewer's quantiles: Bonferroni 0.05/28 two-sided t at 3, 2, 7 dof
    for nu, k in ((3, 8.37), (2, 16.7), (7, 4.30)):
        assert math.isclose(float(student_t.ppf(1 - 0.05 / 28, nu)), k, rel_tol=5e-3)
    n0 = th["T-N-MIN"]
    nu0 = _ws([(w_a / 2, n0 - 1), (w_a / 2, n0 - 1), (w_rm, K - 1), (w_b, math.inf)])
    s0 = delta / (2 * _k_t(alpha, m["primary"], nu0))
    for f_str, node in dn["u_source_scale_max_by_f_src"].items():
        assert math.isclose(node["value"], s0 * math.sqrt(shares["G3"]) / float(f_str), rel_tol=1e-6)
    nu_inf = _ws([(w_rm, K - 1), (w_b, math.inf)])
    k_inf = _k_t(alpha, m["primary"], nu_inf)
    assert math.isclose(dn["n_to_infinity"]["k_primary"]["value"], k_inf, rel_tol=1e-6)
    for s_str, node in dn["delta_floor_by_s_nonaveraging"].items():
        assert math.isclose(node["value"], 2 * k_inf * float(s_str), rel_tol=1e-6)
    # n_required: smallest even n >= T-N-MIN with 4u^2/n <= w_a (delta / (2 k(n)))^2, k re-evaluated at each n
    for d_str, row in dn["n_required"].items():
        d_alt = float(d_str.split("=")[1])
        for u_str, node in row.items():
            u = float(u_str.split("=")[1])
            n = n0
            while True:
                nu = _ws([(w_a / 2, n - 1), (w_a / 2, n - 1), (w_rm, K - 1), (w_b, math.inf)])
                if 4 * u ** 2 / n <= w_a * (d_alt / (2 * _k_t(alpha, m["primary"], nu))) ** 2:
                    break
                n += 2
            assert node["value"] == n, (d_str, u_str)
            assert node["within_T_N_MAX"] == (n <= th["T-N-MAX"])
    scr = dn["screen"]
    assert math.isclose(scr["k_screen_known_variance"]["value"], NormalDist().inv_cdf(1 - th["T-ALPHA-SCREEN"]),
                        rel_tol=1e-6)
    assert math.isclose(scr["k_screen_all_type_A"]["value"],
                        float(student_t.ppf(1 - th["T-ALPHA-SCREEN"], n0 - 1)), rel_tol=1e-6)


def test_budget_closes_at_allocated_maxima(draft, mx):
    """sigma_lnR() with every group exactly at its allocated share returns sigma_max (budget and model agree)."""
    dn = draft["derived_numbers"]
    n = 4
    row = dn["plan_by_n"][str(n)]
    share = row["group_share_max"]["G3"]["value"]
    f_src = 0.2
    sig = mx.sigma_lnR(u_T=row["u_T_max"]["value"], u_P=row["u_P_max"]["value"], n=n, f_src=f_src,
                       u_src_scale=share / f_src, common=[(0.5, share / 0.5)], u_inst=row["u_inst_max"]["value"])
    assert math.isclose(sig, row["sigma_lnR_max"]["value"], rel_tol=1e-6)
    with pytest.raises(ValueError):
        mx.sigma_lnR(u_T=None, u_P=0.01, n=n, f_src=f_src, u_src_scale=0.0, common=[], u_inst=0.0)
    with pytest.raises(ValueError):
        mx.sigma_lnR(u_T=0.01, u_P=0.01, n=n, f_src=f_src, u_src_scale=0.0, common=[(-0.1, 0.01)], u_inst=0.0)


def test_readiness_n_uses_t_at_effective_dof(draft, mx):
    th = {t["id"]: t.get("value") for t in draft["thresholds"]}
    m = draft["derived_numbers"]["m_family"]["primary"]["value"]
    args = dict(f_src=0.2, u_src_scale=0.01, common=[(0.3, 0.003)], delta=th["T-DELTA"], alpha_fw=th["T-ALPHA-FW"],
                m=m, n_min=th["T-N-MIN"], n_max=th["T-N-MAX"])
    good = mx.readiness_n(u_T=0.003, u_P=0.003, u_inst=0.001, nu_rm=5, **args)
    assert good is not None and good % 2 == 0 and th["T-N-MIN"] <= good <= th["T-N-MAX"]
    s = mx.sigma_lnR(0.003, 0.003, good, 0.2, 0.01, [(0.3, 0.003)], 0.001)
    nu = mx.nu_eff_lnR(0.003, 0.003, good, 0.2, 0.01, [(0.3, 0.003)], 0.001, 5)
    assert mx.t_two_sided_bonferroni(th["T-ALPHA-FW"], m, nu) * s < th["T-DELTA"] / 2
    # a poorly reproducible mount fails D0 no matter how many blocks
    assert mx.readiness_n(u_T=0.003, u_P=0.003, u_inst=0.02, nu_rm=5, **args) is None
    # fewer re-mount dof -> larger k (never the normal quantile)
    kw = dict(u_T=0.004, u_P=0.004, n=4, f_src=0.2, u_src_scale=0.01, common=[], u_inst=0.003)
    k2 = mx.t_two_sided_bonferroni(0.05, m, mx.nu_eff_lnR(nu_rm=2, **kw))
    k10 = mx.t_two_sided_bonferroni(0.05, m, mx.nu_eff_lnR(nu_rm=10, **kw))
    assert k2 > k10 > mx.t_two_sided_bonferroni(0.05, m, math.inf)
    with pytest.raises(ValueError):
        mx.welch_satterthwaite([(0.0, 3)])


def test_iso_power_variance_bound(mx):
    """First-order random variance of ln R_iso is bounded by the stated closed form (a^2 + b^2 <= 1)."""
    rng = random.Random(11)
    checked = 0
    for _ in range(3000):
        P_nom = rng.uniform(100, 2000)
        P_hi = P_nom * rng.uniform(1.05, 2.0)
        T_nom = rng.uniform(1, 50)
        T_hi = T_nom * rng.uniform(0.8, 2.0)
        P_X = rng.uniform(P_nom, P_hi)
        T_X = rng.uniform(1, 60)
        u_T, u_P, n = rng.uniform(0, 0.02), rng.uniform(0, 0.02), rng.choice([4, 6, 8])
        it = mx.iso_interpolation(P_X, T_nom, P_nom, T_hi, P_hi)
        var = mx.var_lnR_iso_random(u_T, u_P, n, T_X, P_X, T_nom, P_nom, T_hi, P_hi)
        bound = mx.sigma_lnR_iso_bound(u_T, u_P, n, it["eps"], 0.0, 0.0, [], 0.0, 0.0) ** 2
        assert var <= bound * (1 + 1e-12) + 1e-300
        if abs(it["eps"]) <= 1:
            assert var <= mx.sigma_lnR(u_T, u_P, n, 0.0, 0.0, [], 0.0) ** 2 * (1 + 1e-12) + 1e-300
            checked += 1
    assert checked > 100
    with pytest.raises(ValueError):          # no extrapolation outside the hall_only chord
        mx.iso_interpolation(99.0, 10.0, 100.0, 15.0, 200.0)


def test_stop_support_is_sign_statement_and_monotone(draft, mx):
    """The worked example of section 9, and monotonicity of stop support in precision."""
    delta = next(t["value"] for t in draft["thresholds"] if t["id"] == "T-DELTA")
    k_r1 = 2.9137                              # r1's normal quantile, used only to reproduce the example
    x = -0.03
    h1, h2 = k_r1 * 0.006, k_r1 * 0.0072
    assert mx.classify(x, h1, delta) == "EQUIVALENT"
    assert mx.classify(x, h2, delta) == "SOURCE_WORSE"
    assert mx.stop_supporting(x, h1) and mx.stop_supporting(x, h2)
    assert f"{x - h1:.4f}" == "-0.0475" and f"{x + h1:.4f}" == "-0.0125"
    assert f"{x - h2:.4f}" == "-0.0510" and f"{x + h2:.4f}" == "-0.0090"
    rng = random.Random(3)
    for _ in range(20000):
        x = rng.uniform(-4 * delta, 4 * delta)
        h_big = rng.uniform(0, 2 * delta)
        h_small = rng.uniform(0, h_big)
        if mx.stop_supporting(x, h_big):
            assert mx.stop_supporting(x, h_small)
        # SOURCE_WORSE always implies stop support; the converse does not hold (EQUIVALENT can support a stop)
        if mx.classify(x, h_big, delta) == "SOURCE_WORSE":
            assert mx.stop_supporting(x, h_big)
    with pytest.raises(ValueError):
        mx.stop_supporting(0.0, -1.0)


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
    """R_arch > 1 <=> C_del < C_star, and R_arch < 1 <=> C_del > C_star (identity; synthetic, not physical)."""
    rng = random.Random(7)
    n_ok = 0
    for _ in range(5000):
        T0, P0 = rng.uniform(1, 50), rng.uniform(100, 2000)
        I_del, V_d, eta_d = rng.uniform(0.01, 2), rng.uniform(100, 500), rng.uniform(0.5, 1.0)
        dT = rng.uniform(-0.5, 2) * T0
        dI_d = rng.uniform(-1, 3) * I_del
        P_src = rng.uniform(1, 800)
        dP_other = rng.uniform(-20, 50)
        P1 = P0 + V_d * dI_d / eta_d + P_src + dP_other
        if P1 <= 0:
            with pytest.raises(ValueError):
                mx.ratio_R(T0, P0, dT, V_d * dI_d, eta_d, P_src, dP_other)
            continue
        R = mx.ratio_R(T0, P0, dT, V_d * dI_d, eta_d, P_src, dP_other)
        c_star = mx.breakeven_cost(dT / I_del, P0 / T0, dI_d / I_del, V_d, eta_d, dP_other / I_del)
        c_del = mx.delivered_ion_cost(P_src, I_del)
        if abs(c_del - c_star) < 1e-9 * max(1.0, abs(c_star)):
            continue
        assert (R > 1) == (c_del < c_star)
        assert (R < 1) == (c_del > c_star)
        n_ok += 1
    assert n_ok > 4000
    # break-even source-chain efficiency: at eta_be, R = 1
    for _ in range(200):
        T0, P0 = rng.uniform(1, 50), rng.uniform(100, 2000)
        I_del, V_d, eta_d = rng.uniform(0.1, 2), rng.uniform(100, 500), rng.uniform(0.5, 1.0)
        dT, dI_d, dP_other = rng.uniform(0.1, 2) * T0, rng.uniform(0, 0.5) * I_del, 0.0
        P_load, P_mag = rng.uniform(10, 400), rng.uniform(0, 20)
        c_star = mx.breakeven_cost(dT / I_del, P0 / T0, dI_d / I_del, V_d, eta_d, 0.0)
        eta_be = mx.breakeven_efficiency(P_load, I_del, c_star, P_mag)
        if eta_be is None:
            continue
        R = mx.ratio_R(T0, P0, dT, V_d * dI_d, eta_d, P_load / eta_be + P_mag, dP_other)
        assert math.isclose(R, 1.0, rel_tol=1e-9)
    # invalid inputs are refused cleanly (no ZeroDivisionError, no meaningless R)
    with pytest.raises(ValueError):
        mx.ratio_R(1, 1, 0, 0, None, 1, 0)
    with pytest.raises(ValueError):
        mx.ratio_R(0.0, 1, 0, 0, 0.9, 1, 0)
    with pytest.raises(ValueError):
        mx.ratio_R(1, 1, 0, 0, 0.9, 1, -10)          # P1 <= 0
    with pytest.raises(ValueError):
        mx.ratio_R(1, 1, -2, 0, 0.9, 1, 0)          # T1 < 0
    with pytest.raises(ValueError):
        mx.breakeven_cost(1, 1, 0, 1, 0.0, 0)
    with pytest.raises(ValueError):
        mx.breakeven_cost(1, 0.0, 0, 1, 0.9, 0)
    with pytest.raises(ValueError):
        mx.delivered_ion_cost(10.0, 0.0)


def test_physics_helpers_reproduce_stated_values(draft, mx):
    c = mx.load_constants()
    dn = draft["derived_numbers"]
    y_n2 = math.sqrt(2 * c.M_SPECIES["N2"] * 1.0 / c.E_CHARGE) * 1e3
    assert math.isclose(dn["y_max_per_sqrtV"]["N2+"]["value"], y_n2, rel_tol=1e-6)
    S = (1e-6 / c.M_SPECIES["N2"]) * c.K_B * 300.0 / (1e-5 * 101325.0 / 760.0) * 1e3
    assert math.isclose(dn["S_eff_required_per_mgps"]["N2"]["1.0e-05 Torr"]["value"], S, rel_tol=1e-6)
    with pytest.raises(ValueError):
        mx.t_two_sided_bonferroni(0.05, 0, 5)
    with pytest.raises(ValueError):
        mx.y_max(c.M_SPECIES["N2"], 300.0, 0, c.E_CHARGE)


def test_run_counts_include_bracketing_readings(draft):
    """Independent count: a source visit with on-levels takes len(on) + 2 readings (off ... off)."""
    rows = draft["run_matrix"]["conditions"]
    src_hw = {"HW-RF", "HW-ECR"}
    visits: dict = {}
    for r in rows:
        visits.setdefault((r["hw"], r["stage"], r["op"]), []).append(r["source"])

    def count(sel_visits):
        tot = 0
        for (hw, _, _), lv in sel_visits.items():
            on = [x for x in lv if x != "off"]
            tot += len(on) + 2 if hw in src_hw and on else len(lv)
        return tot

    rc = draft["derived_numbers"]["run_counts"]
    n_min = next(t["value"] for t in draft["thresholds"] if t["id"] == "T-N-MIN")
    assert rc["hall_on_conditions_per_block"]["value"] == len(rows)
    per_block = count(visits)
    assert per_block > len(rows)
    assert rc["hall_on_readings_per_block"]["value"] == per_block
    assert rc["hall_on_readings_full_at_n_min"]["value"] == per_block * n_min
    bench = draft["run_matrix"]["bench_conditions"]["per_arm"]
    bv: dict = {}
    for op, lv in bench:
        bv.setdefault(op, []).append(lv)
    per_arm = sum(len(lv) + 2 for lv in bv.values())
    assert rc["bench_readings_at_n_min"]["value"] == per_arm * 2 * n_min
    # every bench level has a Hall-on counterpart in S4 (no orphan bench condition)
    s4 = {(r["op"], r["source"]) for r in rows if r["arm"] == "rf_hall" and r["stage"] == "S4"}
    assert all((op, lv) in s4 for op, lv in bench)


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
    # budget shares inconsistent with the variance groups are refused (no silent re-normalisation)
    d4 = copy.deepcopy(draft)
    next(t for t in d4["thresholds"] if t["id"] == "T-BUDGET-SHARES")["value"].pop("G5")
    with pytest.raises(ValueError):
        mx.derive(d4)
    d5 = copy.deepcopy(draft)
    next(t for t in d5["thresholds"] if t["id"] == "T-BUDGET-SHARES")["value"]["G1"] = 0.3
    with pytest.raises(ValueError):
        mx.derive(d5)
    d6 = copy.deepcopy(draft)
    d6["uncertainty"]["variance_groups"][0]["evaluation"] = "guessed"
    with pytest.raises(ValueError):
        mx.derive(d6)


def test_markdown_states_the_same_numbers(draft, md):
    dn = draft["derived_numbers"]
    p4 = dn["plan_by_n"]["4"]
    rc = dn["run_counts"]
    expected = [
        f'{dn["k_primary_known_variance_limit"]["value"]:.4f}',
        f'{dn["n_to_infinity"]["nu_eff"]["value"]:.1f}',
        f'{dn["n_to_infinity"]["k_primary"]["value"]:.4f}',
        f'{dn["screen"]["k_screen_known_variance"]["value"]:.4f}',
        f'{dn["screen"]["k_screen_all_type_A"]["value"]:.4f}',
        f'{rc["hall_on_conditions_per_block"]["value"]} Hall-on conditions per block',
        f'{rc["hall_on_readings_per_block"]["value"]} readings per block',
        f'{rc["hall_on_readings_full_at_n_min"]["value"]}',
        f'{rc["hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min"]["value"]} readings',
        f'{rc["bench_readings_at_n_min"]["value"]} bench readings',
        f'{rc["s1b_remount_series_readings"]["value"]}-reading S1b',
        f'{dn["classification_check"]["unresolved_count_h_above_half_delta"]["value"]} at h = 0.75',
        f'ν_eff is {p4["nu_eff"]["value"]:.1f}',
        f'k = {p4["k_primary"]["value"]:.4f}',
    ]
    for n, row in dn["plan_by_n"].items():
        expected += [f'{row["nu_eff"]["value"]:.1f}', f'{row["k_primary"]["value"]:.4f}',
                     f'{row["sigma_lnR_max"]["value"]:.5f}', f'{row["group_share_max"]["G1"]["value"]:.5f}',
                     f'{100 * row["u_T_max"]["value"]:.2f} %', f'{100 * row["u_inst_max"]["value"]:.2f} %',
                     f'{row["k_iso"]["value"]:.4f}, {row["sigma_lnR_max_iso"]["value"]:.5f}',
                     f'{100 * row["u_interp_max"]["value"]:.2f} %',
                     f'{row["k_facility"]["value"]:.4f}, {row["sigma_lnR_max_facility"]["value"]:.5f}']
    for K, row in dn["k_primary_by_remount_cycles"].items():
        expected += [f'{row["nu_eff"]["value"]:.1f}', f'{row["k_primary"]["value"]:.4f}']
    expected += [f'{100 * v["value"]:.2f} %' for v in dn["u_source_scale_max_by_f_src"].values()]
    expected += [f'{v["value"]:.3g}' for v in dn["delta_floor_by_s_nonaveraging"].values()]
    expected += [f'{v["value"]:.4f}' for v in dn["y_max_per_sqrtV"].values()]
    expected += [f'{v["value"]:,.0f} L/s' for g in dn["S_eff_required_per_mgps"].values() for v in g.values()]
    missing = [s for s in expected if s not in md]
    assert not missing, f"markdown lacks derived numbers: {missing}"
    # the n_required table rows in the markdown match the JSON
    n_max = next(t["value"] for t in draft["thresholds"] if t["id"] == "T-N-MAX")
    for d_str, row in dn["n_required"].items():
        d = float(d_str.split("=")[1])
        cells = []
        for node in row.values():
            v = node["value"]
            cells.append(f"{v}" if node["within_T_N_MAX"] else f"{v} (> {n_max})")
        assert f"| {d:.2f} | " + " | ".join(cells) + " |" in md, d_str
    # r1's anti-conservative normal-quantile claims are gone
    assert "0.00858" not in md
    assert "exactly the brief" not in md.lower()
