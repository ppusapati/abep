"""Experimental decision package from the minimum decisive experiment (fo_experiment_package). DRAFT_PENDING_OWNER.

Registered follow-on ``fo_experiment_package`` (trigger ``T_EXPERIMENT_PACKAGE``; prerequisite
``lane_25_min_decisive_experiment``). This script turns the lane-25 draft (minimum decisive experiment) into an owner
decision package:

  (1) the decisions the owner must lock before any score-bearing run, each with options and the consequences for
      statistics, cost and readings, computed with the lane-25 tools (``minexp_numbers.py``, loaded by file path);
  (2) a traceability matrix: measurement -> break-even placement (RF / ECR overlays), Bundle-1 (milestone-A) condition,
      hard-gate criterion (lane 24 matrix and evaluator ``abep_sim/hard_gates.py``) and failure-tree node (lane 26);
  (3) a reconciliation of lane 25 with the lane-06 common-condition protocol and a PROPOSED single protocol basis;
  (4) facility and hardware requirements, stated as requirements (TBD where not sourced; no facility is named);
  (5) what the package unlocks for milestone A -> B.

Nothing here is pre-registered, locked, or decided. Every recommendation is PROPOSED. No absolute Hall performance of
any closure is used (credible set empty, gate 3 FAIL); no screening candidate is a performance source. The valve-outlet
feed state (lane 16) and the compressor bus draw (upstream ICD, lane 33) stay TBD. No architecture is named as
preferred and none is set aside: the only elimination path is lane 24's evaluator, which this script runs on SYNTHETIC
outcome templates to show what the minimum experiment can and cannot decide.

Every input file is pinned by sha256 and lane id; a missing or changed input raises (no fallback).

Usage (from the repository root):
    python docs/architecture_comparison/experiment_package/build_experiment_package.py           # write JSON + Markdown
    python docs/architecture_comparison/experiment_package/build_experiment_package.py --check   # byte-for-byte check
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL_HERE = "docs/architecture_comparison/experiment_package"
SCRIPT_REF = f"{REL_HERE}/build_experiment_package.py"
OUT_JSON = HERE / "experiment_package_v1.json"
OUT_MD = HERE / "EXPERIMENT_PACKAGE.md"
SCHEMA_JSON = HERE / "experiment_package_v1.schema.json"
BASE_COMMIT = "d939ef66324b7d1036b2c9bcd5e7674df218342b"
SIG = 8

# ------------------------------------------------------------------------------------------------------------------
# Pinned inputs: key -> (repository-relative path, producing lane id, sha256). A missing or changed file raises.
# ------------------------------------------------------------------------------------------------------------------
INPUTS = {
    "minexp_draft": ("docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json",
                     "lane_25_min_decisive_experiment",
                     "54b7b00a60134f2d92f2eb5c9fb49f18d23623a566e04a4b7d70325a0e332509"),
    "minexp_doc": ("docs/architecture_comparison/minimum_decisive_experiment/MINIMUM_DECISIVE_EXPERIMENT_DRAFT.md",
                   "lane_25_min_decisive_experiment",
                   "eadc0dacdf3bfd9260f8f588267445729237fe85a62b51a8d0b85c0817c40af2"),
    "minexp_tools": ("docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py",
                     "lane_25_min_decisive_experiment",
                     "3ee68a28ddd98d25705a58e293944d89dc102b44caad7ac55b912e55fafd7f4b"),
    "protocol": ("docs/architecture_comparison/experiment_protocol/protocol_draft.json",
                 "lane_06_experiment_protocol",
                 "287dd7ecd57087e46f2f3d786bfb2d64b01ac4fe29a29de21ef98b04c5ac96e3"),
    "protocol_doc": ("docs/architecture_comparison/experiment_protocol/EXPERIMENT_PROTOCOL_DRAFT.md",
                     "lane_06_experiment_protocol",
                     "8ef5329fb26a0c90d15ae6067c1af81b141b30b95152daf0e5fcff1e4951fb66"),
    "failure_tree": ("docs/architecture_comparison/failure_tree/failure_trees_v1.json",
                     "lane_26_failure_tree",
                     "5b81c1e99fd7ed9a4fbb4f3e4ef0abda5a753af668ffb20003a3888cb0365d93"),
    "overlay_rf": ("docs/architecture_comparison/overlays/rf/overlay_rf_v1.json",
                   "fo_rf_breakeven_overlay",
                   "ba739be2fdf431ac33900207cd8365d265456ad7b9d7e6a71e0875524c662359"),
    "overlay_ecr": ("docs/architecture_comparison/overlays/ecr/overlay_ecr_v1.json",
                    "fo_ecr_breakeven_overlay",
                    "3ee12e66f94204955f61cbb78d7c5036044cc59a9bc50f675704592bfbfabfcd"),
    "overlay_hs": ("docs/architecture_comparison/overlays/hall_sustainment/hall_sustainment_envelope_v1.json",
                   "fo_hall_sustainment_envelope",
                   "c7d05fd04aafe249ff0dce575902067dea9bdd048fa857283cb66066e612b19e"),
    "hg_matrix": ("docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json",
                  "lane_24_hard_gates",
                  "7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f"),
    "hg_status": ("docs/architecture_comparison/hard_gates/hard_gate_status_v1.json",
                  "lane_24_hard_gates",
                  "2c82b3277067b22c85eabd25539b18101f429e6d34ee698d2f5d6e183aa44527"),
    "hg_register": ("docs/architecture_comparison/hard_gates/evidence_register_v1.json",
                    "lane_24_hard_gates",
                    "45dfbfb311441aeb7c9c58f5dbb9ffb39c28fa448b85de552c37e8268ff94a3d"),
    "hg_module": ("abep_sim/hard_gates.py", "lane_24_hard_gates",
                  "a36fe3c9065291f0fe5be3f17e179d5b691f00c013f7f8ef299fa89db896dda8"),
    "hg_schema": ("schemas/architecture_comparison/hard_gates_v1.schema.json", "lane_24_hard_gates",
                  "e5c70c588f3e785720c0d9d01013e5725807b9fd288fa8a1bddf6ba6d86f54ba"),
    "arch_boundary": ("abep_sim/arch_boundary.py", "lane_11_bus_boundary",
                      "8dfc309a5d2c717913fd4961bc660f8bab92ed2c59356f5a78bff3ef4392eeae"),
    "feed_envelope": ("docs/architecture_comparison/feed_envelope/feed_envelope_v1.json", "lane_16_feed_envelope",
                      "ada3ee720b1b8d60526d3b092492589f62a4144112845b4d813dbc8dc7d5ca02"),
    "constants": ("abep_sim/constants.py", "repository (RFP record and physical constants; read by minexp_numbers.py)",
                  "dd1c564324c139471bb361d27ef0f75b0f84de1878d100d4313aed12677f33d7"),
    "hall_ensemble": ("abep_sim/hall_ensemble.py",
                      "repository (admission guard; read by the lane-24 evaluator)",
                      "218f890c8444af1f593396da5051e38d2d093bbb3cb0bc976cc44b01b67df704"),
    "transport_ensemble": ("hallthruster_bridge/ensemble/transport_ensemble_v0.json",
                           "physics track (transport ensemble; read-only, admitted set empty)",
                           "2d5069a3382ab667362befeeb5a737261f70a279d19cb89ee79cb61ae35ba08b"),
}

ARCHS = ("hall_only", "rf_hall", "ecr_hall")
STATUS = "DRAFT_PENDING_OWNER"
REC = "PROPOSED"
FORBIDDEN_PATTERNS = (r"\bwinner\s+is\b", r"\bis\s+the\s+winner\b", r"\bbest\s+architecture\b",
                      r"\barchitecture\s+is\s+eliminated\b", r"\bselect(?:ed|s)?\s+(?:hall_only|rf_hall|ecr_hall)\s+as\b",
                      r"\bsgb-screen-\d", r"\bLOCKED\b(?!_)")


class InputChanged(RuntimeError):
    """A pinned input differs from its recorded sha256 (no fallback: the package must be rebuilt deliberately)."""


# ------------------------------------------------------------------------------------------------------------------
# input handling
# ------------------------------------------------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_inputs(root: Path = ROOT, pins: dict = INPUTS) -> dict:
    """Check every pinned input exists and matches its sha256. Raises FileNotFoundError / InputChanged."""
    missing, changed = [], []
    for key, (rel, lane, sha) in pins.items():
        p = root / rel
        if not p.is_file():
            missing.append(f"{key}: {rel} ({lane})")
            continue
        got = sha256_file(p)
        if got != sha:
            changed.append(f"{key}: {rel} ({lane}) sha256 {got} != pinned {sha}")
    if missing:
        raise FileNotFoundError("pinned inputs missing (no fallback):\n  " + "\n  ".join(missing))
    if changed:
        raise InputChanged("pinned inputs changed; review the change and re-pin deliberately:\n  " + "\n  ".join(changed))
    return {k: root / v[0] for k, v in pins.items()}


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_minexp(path: Path):
    """Lane-25 tools, loaded by file path (no package import of the draft folder)."""
    spec = importlib.util.spec_from_file_location("_exppkg_minexp_numbers", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_hard_gates():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import abep_sim.hard_gates as hg          # lane 24 evaluator (pure; not wired into archengine)
    return hg


def load_arch_boundary():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import abep_sim.arch_boundary as ab       # lane 11 contract (pure)
    return ab


# ------------------------------------------------------------------------------------------------------------------
# number objects
# ------------------------------------------------------------------------------------------------------------------
def _r(x):
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, int):
        return x
    if x == 0 or math.isinf(x) or math.isnan(x):
        return x
    return float(f"{x:.{SIG}g}")


def N(value, unit: str, evidence_class: str, source: str, note: str | None = None) -> dict:
    """A number with unit, evidence class and source (input pointer or computation)."""
    if isinstance(value, float) and (math.isnan(value)):
        raise ValueError("NaN is not a number object value")
    if isinstance(value, float) and math.isinf(value):
        value = "unbounded (no admissible value up to the lane-25 search cap)"
    d = {"value": _r(value), "unit": unit, "evidence_class": evidence_class, "source": source}
    if note:
        d["note"] = note
    return d


def share_objs(shares: dict, source: str) -> dict:
    return {g: N(v, "fraction of sigma_max^2", "assumed", source) for g, v in shares.items()}


def TBD(what: str, requires: str, blocked_by: list[str]) -> dict:
    return {"value": "TBD", "what": what, "requires": requires, "blocked_by": list(blocked_by)}


def ptr(key: str, pointer: str) -> str:
    return f"{INPUTS[key][0]}#{pointer}"


def comp(expr: str) -> str:
    return f"computed: {SCRIPT_REF} via {expr}"


def get_ptr(doc, pointer: str):
    cur = doc
    for part in pointer.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def from_input(docs: dict, key: str, pointer: str, unit: str | None = None, evidence_class: str | None = None,
               note: str | None = None) -> dict:
    """Number read from a pinned input by JSON pointer; the input's own unit/evidence class are used if present."""
    obj = get_ptr(docs[key], pointer)
    if isinstance(obj, dict) and "value" in obj:
        v = obj["value"]
        unit = unit or obj.get("unit")
        evidence_class = evidence_class or obj.get("evidence_class")
    else:
        v = obj
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{key}#{pointer} is not numeric: {v!r}")
    if unit is None or evidence_class is None:
        raise ValueError(f"{key}#{pointer}: unit and evidence class must be stated")
    return N(v, unit, evidence_class, ptr(key, pointer), note)


def find_value_ptr(doc, vid: str, path: str = "") -> str | None:
    """JSON pointer of the value object with id == vid (lane-06 value objects carry 'id' and 'value')."""
    if isinstance(doc, dict):
        if doc.get("id") == vid and "value" in doc:
            return path or "/"
        for k, v in doc.items():
            r = find_value_ptr(v, vid, f"{path}/{k}")
            if r:
                return r
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            r = find_value_ptr(v, vid, f"{path}/{i}")
            if r:
                return r
    return None


def l06(docs: dict, vid: str) -> dict:
    """A lane-06 value object by id (raises if absent)."""
    pt = find_value_ptr(docs["protocol"], vid)
    if pt is None:
        raise KeyError(f"lane-06 value {vid} not found in protocol_draft.json")
    return from_input(docs, "protocol", pt)


# ------------------------------------------------------------------------------------------------------------------
# lane-25 computations (consequences of owner decisions)
# ------------------------------------------------------------------------------------------------------------------
class MinexpContext:
    def __init__(self, mx, draft):
        self.mx, self.draft = mx, draft
        self.delta = mx.threshold(draft, "T-DELTA")
        self.alpha = mx.threshold(draft, "T-ALPHA-FW")
        self.n_min = int(mx.threshold(draft, "T-N-MIN"))
        self.n_max = int(mx.threshold(draft, "T-N-MAX"))
        self.K = int(mx.threshold(draft, "T-S1-REMOUNT-CYCLES"))
        self.r = int(mx.threshold(draft, "T-S1-READINGS-PER-CYCLE"))
        self.knee = int(mx.threshold(draft, "T-KNEE-LEVELS"))
        self.shares = mx.budget_shares(draft)
        self.groups = {g["id"]: g["evaluation"] for g in mx.variance_groups(draft)}
        self.ns = mx.even_blocks(self.n_min, self.n_max)
        self.fam = mx.family_sizes(draft)
        stored = draft.get("derived_numbers")
        if stored is None:
            raise ValueError("lane-25 draft has no derived_numbers block")
        errs = mx.compare(mx._strip(mx.derive(draft)), mx._strip(stored))
        if errs:
            raise InputChanged("lane-25 derived_numbers do not reproduce with its own tools:\n  " + "\n  ".join(errs))

    def by_eval(self, shares: dict) -> dict:
        out = {e: 0.0 for e in self.mx.EVALUATIONS}
        for gid, s in shares.items():
            out[self.groups[gid]] += s
        return out

    def plan(self, shares: dict, K: int | None = None, delta: float | None = None) -> dict:
        """Planning targets for an allocation of sigma_max^2 over the variance groups (lane-25 functions)."""
        mx = self.mx
        K = self.K if K is None else K
        delta = self.delta if delta is None else delta
        if sorted(shares) != sorted(g for g in shares if g in self.groups) or not math.isclose(
                sum(shares.values()), 1.0, abs_tol=1e-12):
            raise ValueError(f"invalid share allocation {shares}")
        be = self.by_eval(shares)
        rows = {}
        for n in self.ns:
            nu = mx.plan_nu_eff(n, K, be)
            k = mx.t_two_sided_bonferroni(self.alpha, self.fam["primary"], nu)
            s = mx.sigma_lnR_max(delta, k)
            rows[str(n)] = {"nu_eff": nu, "k_primary": k, "sigma_lnR_max": s,
                            "u_T_max": s * math.sqrt(shares["G1"] * n / 2.0),
                            "u_P_max": s * math.sqrt(shares["G2"] * n / 2.0),
                            "u_inst_max": (s * math.sqrt(shares["G5"] / 2.0)) if "G5" in shares else None,
                            "u_src_max_times_f_src": s * math.sqrt(shares["G3"])}
        nreq = {}
        for u in self.mx.grid(self.draft, "u_reading"):
            nreq[str(u)] = mx.n_required(u, delta, self.alpha, self.fam["primary"], K, be, self.n_min)
        return {"by_n": rows, "n_required_by_u_reading": nreq}

    def counts(self, draft=None, n=None) -> dict:
        d = self.draft if draft is None else draft
        rc = self.mx.run_counts(d, self.n_min if n is None else n, self.knee, self.K, self.r)
        return {k: (v["value"] if isinstance(v, dict) and "value" in v else
                    {kk: vv["value"] for kk, vv in v.items()}) for k, v in rc.items()}

    def stage_readings(self, stage: str) -> int:
        mx = self.mx
        rm = self.draft["run_matrix"]
        rows = [r for r in rm["conditions"] if r["stage"] == stage]
        src_hw = {a["hardware_configuration"] for a in self.draft["architectures"] if a["pre_ionizer"] != "none"}
        return sum(mx.readings_per_visit(lv, hw in src_hw, rm["reading_rule"])
                   for (hw, _s, _o), lv in mx._visits(rows).items())


def plan_objects(ctx: MinexpContext, plan: dict, label: str) -> dict:
    out = {}
    src = f"MinexpContext.plan({label}) -> minexp_numbers.plan_nu_eff / t_two_sided_bonferroni / sigma_lnR_max"
    for n, row in plan["by_n"].items():
        o = {"nu_eff": N(row["nu_eff"], "-", "model-derived", comp(src + f", n = {n}")),
             "k_primary": N(row["k_primary"], "-", "model-derived", comp(src + f", n = {n}")),
             "sigma_lnR_max": N(row["sigma_lnR_max"], "ln-ratio", "model-derived", comp(src + f", n = {n}")),
             "u_T_max": N(row["u_T_max"], "relative (1 sigma, per reading)", "model-derived",
                          comp(src + f", n = {n}: 2 u_T^2/n = share(G1) sigma_max^2")),
             "u_P_max": N(row["u_P_max"], "relative (1 sigma, per reading)", "model-derived",
                          comp(src + f", n = {n}: 2 u_P^2/n = share(G2) sigma_max^2")),
             "u_src_max_times_f_src": N(row["u_src_max_times_f_src"], "relative (1 sigma) x f_src", "model-derived",
                                        comp(src + f", n = {n}: (f_src u_src)^2 = share(G3) sigma_max^2"))}
        if row["u_inst_max"] is None:
            o["u_inst_max"] = {"value": "not applicable", "reason": "G5 removed (no cross-installation comparison)"}
        else:
            o["u_inst_max"] = N(row["u_inst_max"], "ln-ratio (1 sigma, per installation)", "model-derived",
                                comp(src + f", n = {n}: 2 u_inst^2 = share(G5) sigma_max^2"))
        out[n] = o
    out["n_required_by_u_reading"] = {
        u: N(v, "blocks", "model-derived",
             comp(f"minexp_numbers.n_required(u = {u}, T-DELTA, T-ALPHA-FW, m_primary, K, shares {label}, T-N-MIN)"))
        for u, v in plan["n_required_by_u_reading"].items()}
    return out


# ------------------------------------------------------------------------------------------------------------------
# (1) decisions
# ------------------------------------------------------------------------------------------------------------------
def decisions(ctx: MinexpContext, docs: dict) -> list[dict]:
    mx, draft = ctx.mx, ctx.draft
    D = []
    lane25_open = draft["open_owner_decisions"]

    # ---- D-01 T-BUDGET-SHARES ------------------------------------------------------------------------------------
    eq = dict(ctx.shares)
    div = {"G1": 0.25, "G2": 0.25, "G3": 0.25, "G4": 0.25}
    half = {"G1": 0.35, "G2": 0.35, "G3": 0.1, "G4": 0.1, "G5": 0.1}
    p_eq, p_div, p_half = ctx.plan(eq), ctx.plan(div), ctx.plan(half)
    # the equal allocation must reproduce lane 25's own derived numbers
    for n, row in p_eq["by_n"].items():
        stored = draft["derived_numbers"]["plan_by_n"][n]
        for key in ("nu_eff", "k_primary", "sigma_lnR_max", "u_T_max", "u_P_max", "u_inst_max"):
            if not math.isclose(_r(row[key]), stored[key]["value"], rel_tol=1e-7):
                raise InputChanged(f"plan({n}).{key} {row[key]} does not reproduce lane-25 {stored[key]['value']}")
    D.append({
        "id": "D-01", "title": "T-BUDGET-SHARES: allocation of the ln R uncertainty budget over the variance groups G1-G5",
        "source": {"lane_25_open_decision": [1], "lane_25_threshold": "T-BUDGET-SHARES",
                   "input": ptr("minexp_draft", "/thresholds (id T-BUDGET-SHARES)")},
        "status": "OPEN_OWNER_DECISION",
        "structural_finding": ("The shares set only the PLANNING targets (instrument and mount specifications). D0 "
                               "(readiness_n) and scoring use the actual S1 variance components and never the shares "
                               "(minexp_numbers.readiness_n takes no share argument), so the choice cannot move a "
                               "classification; it moves what the instruments must achieve before D0 can pass."),
        "options": [
            {"id": "D-01-A", "label": "equal five-way (lane-25 proposal)", "shares": share_objs(eq, "lane-25 proposal: "
                                                                                              + ptr("minexp_draft", "/thresholds (id T-BUDGET-SHARES)")),
             "evidence_class": "assumed", "consequences": {"statistics_and_targets": plan_objects(ctx, p_eq, "equal")}},
            {"id": "D-01-B", "label": "G5 removed, four equal shares (only with a no-vent arm switch, D-06-B)",
             "shares": share_objs(div, "package option (assumed): lane-25 rationale 'G5 -> 0 with OPTION-DIVERTER', "
                                       "remaining shares equal"), "evidence_class": "assumed",
             "consequences": {"statistics_and_targets": plan_objects(ctx, p_div, "G5 removed"),
                              "condition": "valid only if hall_only and the source arm share one installation "
                                           "(OPTION-DIVERTER); requires one check against a true HW-0 (lane 25 Sec. 2)"}},
            {"id": "D-01-C", "label": "non-averaging groups G3-G5 at half the equal share (0.1 each), G1/G2 0.35",
             "shares": share_objs(half, "package option (assumed, illustrative): G3-G5 at half the equal share"),
             "evidence_class": "assumed",
             "consequences": {"statistics_and_targets": plan_objects(ctx, p_half, "non-averaging halved")}},
        ],
        "recommendation": {"status": REC, "option": "D-01-A",
                           "rationale": "Keep the transparent equal allocation until S1 gives the actual components; "
                                        "re-allocate at LOCK-1 only together with D-06 (a no-vent switch removes G5)."},
        "cost_note": "No change in readings or conditions; changes instrument / mount specifications only.",
    })

    base0 = ctx.counts()
    # ---- D-02 stop rule --------------------------------------------------------------------------------------------
    delta = ctx.delta
    h_plan = delta / 2.0
    grid_x = [round(-0.10 + 0.005 * i, 6) for i in range(25)]      # ln R estimates -0.10 .. +0.02 (illustrative)
    rows = []
    for h in (h_plan, 0.75 * delta):
        cls_counts, sign_n, margin_n, sub_ok = {}, 0, 0, True
        for x in grid_x:
            c = mx.classify(x, h, delta)
            cls_counts[c] = cls_counts.get(c, 0) + 1
            s = mx.stop_supporting(x, h)
            m = (x + h) < -delta
            sign_n += s
            margin_n += m
            sub_ok &= (not m) or s
        rows.append({"h": N(h, "ln-ratio", "model-derived",
                            comp("h = T-DELTA/2 (planned k sigma_max)" if h == h_plan else "h = 0.75 T-DELTA (lane-25 "
                                                                                          "Sec. 6.2 example)")),
                     "grid_points": N(len(grid_x), "estimates", "assumed",
                                      comp("illustrative grid ln R_hat = -0.10 .. +0.02, step 0.005")),
                     "sign_form_stop_supporting": N(sign_n, "grid points", "model-derived",
                                                    comp("minexp_numbers.stop_supporting(x, h)")),
                     "stop_margin_stop_supporting": N(margin_n, "grid points", "model-derived",
                                                      comp("upper bound x + h < -T-DELTA")),
                     "stop_margin_subset_of_sign_form": sub_ok,
                     "size_classes_on_grid": {k: N(v, "grid points", "model-derived",
                                                   comp("minexp_numbers.classify(x, h, T-DELTA)"))
                                              for k, v in sorted(cls_counts.items())}})
    D.append({
        "id": "D-02", "title": "Stop rule D3: sign form (upper bound of ln R_arch < 0) or STOP-MARGIN (upper bound < -delta)",
        "source": {"lane_25_open_decision": [4], "lane_25_threshold": "T-STOP-RULE",
                   "input": ptr("minexp_draft", "/thresholds (id T-STOP-RULE)")},
        "status": "OPEN_OWNER_DECISION",
        "options": [
            {"id": "D-02-A", "label": "sign form (lane-25 proposal)",
             "consequences": {
                 "statistics": [{"what": "smallest true R_arch that can support a stop at the planned precision "
                                         "(estimate below -h)",
                                 "R_threshold": N(math.exp(-h_plan), "ratio", "model-derived",
                                                  comp("exp(-T-DELTA/2)"))}],
                 "meaning": "equals 'C_del > C* with simultaneous confidence' (break-even identity, lane 25 Sec. 3.2); "
                            "matches the overlays' break-even inequality, which has no margin"}},
            {"id": "D-02-B", "label": "STOP-MARGIN",
             "consequences": {
                 "statistics": [{"what": "smallest true R_arch that can support a stop at the planned precision "
                                         "(estimate below -delta - h)",
                                 "R_threshold": N(math.exp(-delta - h_plan), "ratio", "model-derived",
                                                  comp("exp(-T-DELTA - T-DELTA/2)"))}],
                 "meaning": "keeps running an arm whose bus-referred thrust per watt is confidently below hall_only "
                            "but within delta of it"}},
        ],
        "grid_comparison": rows,
        "cost_note": ("Neither form changes the planned readings; a stop only removes the arm's remaining S4/S5 rows "
                      "(readings_if_stopped below). Every STOP-MARGIN stop is also a sign-form stop (checked on the "
                      "grid), so the sign form can only save readings, never add them. A stop is an "
                      "experiment-internal decision, not an architecture elimination (hard-gate outcome templates)."),
        "readings_if_stopped": {
            "hall_on_readings_full_at_n_min": N(base0["hall_on_readings_full_at_n_min"], "readings", "model-derived",
                                                comp("minexp_numbers.run_counts(n = T-N-MIN)")),
            "hall_on_readings_if_both_arms_stop_at_subset_at_n_min": N(
                base0["hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min"], "readings", "model-derived",
                comp("minexp_numbers.run_counts(n = T-N-MIN)"))},
        "recommendation": {"status": REC, "option": "D-02-A",
                           "rationale": "The sign statement is the break-even condition itself; the margin form would "
                                        "require a larger measured deficit than the break-even surfaces and overlays "
                                        "use, and it is monotone in precision too, so it offers no robustness gain."},
    })

    # ---- D-03 Hall-on at P_lo for subset stops ----------------------------------------------------------------------
    base = ctx.counts()
    d_lo = copy.deepcopy(draft)
    lo_ids = []
    for r in d_lo["run_matrix"]["conditions"]:
        if r["stage"] == "S4" and r["source"] == "lo" and r["arm"] != "hall_only":
            r["confirmation_subset"] = True
            lo_ids.append(r["id"])
    lo = ctx.counts(d_lo)
    src_counts = "minexp_numbers.run_counts(run_matrix, reading_rule, n = T-N-MIN)"
    D.append({
        "id": "D-03", "title": "Does a stop from the confirmation subset require Hall-on data at P_lo?",
        "source": {"lane_25_open_decision": [5], "input": ptr("minexp_draft", "/open_owner_decisions/4")},
        "status": "OPEN_OWNER_DECISION",
        "options": [
            {"id": "D-03-A", "label": "no: P_lo conditions of a stopped arm are NOT_TESTED (lane-25 draft)",
             "consequences": {
                 "readings": {
                     "subset_conditions_per_block_per_arm": {
                         a: N(v, "conditions per block", "model-derived", comp(src_counts))
                         for a, v in base["confirmation_subset_conditions_by_arm"].items()},
                     "hall_on_readings_if_both_arms_stop_at_subset": N(
                         base["hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min"], "readings",
                         "model-derived", comp(src_counts))},
                 "evidence": "the break-even surface at P_lo stays unmeasured for a stopped arm (NOT_TESTED: no "
                             "evidence either way)"}},
            {"id": "D-03-B", "label": "yes: add OP1-OP3 x lo to the subset (rows " + ", ".join(lo_ids) + ")",
             "consequences": {
                 "readings": {
                     "subset_conditions_per_block_per_arm": {
                         a: N(v, "conditions per block", "model-derived",
                              comp(src_counts + " with the lo rows flagged confirmation_subset"))
                         for a, v in lo["confirmation_subset_conditions_by_arm"].items()},
                     "hall_on_readings_if_both_arms_stop_at_subset": N(
                         lo["hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min"], "readings",
                         "model-derived", comp(src_counts + " with the lo rows flagged confirmation_subset")),
                     "added_readings_at_n_min": N(
                         lo["hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min"]
                         - base["hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min"], "readings",
                         "model-derived", comp("difference of the two run_counts results")),
                     "full_campaign_readings_at_n_min_for_reference": N(
                         base["hall_on_readings_full_at_n_min"], "readings", "model-derived", comp(src_counts))},
                 "statistics": {"m_primary_unchanged": N(ctx.mx.family_sizes(d_lo)["primary"], "comparisons",
                                                         "model-derived", comp("minexp_numbers.family_sizes with the lo "
                                                                               "rows flagged")),
                                "note": "the lo conditions are already primary-family members, so k and the "
                                        "uncertainty targets do not change"},
                 "evidence": "C_del and C* are then measured at both source powers wherever an arm stops; the "
                             "power dependence of C_del is unknown (lane 25 Sec. 4) and the RF overlay places its "
                             "evidence units per source power level"}},
        ],
        "recommendation": {"status": REC, "option": "D-03-B",
                           "rationale": "A stop then rests on both tested source powers; the added readings are a "
                                        "small fraction of the full campaign (computed above)."},
    })

    # ---- D-04 T-ISO-INTERP ----------------------------------------------------------------------------------------
    d_mid = copy.deepcopy(draft)
    for rid, op in (("R41", "OP2M"), ("R42", "OP3M")):
        d_mid["run_matrix"]["conditions"].append({"id": rid, "stage": "S2", "hw": "HW-0", "arm": "hall_only", "op": op,
                                                  "source": "off", "role": "iso_power_chord_check", "families": []})
    mid = ctx.counts(d_mid)
    D.append({
        "id": "D-04", "title": "T-ISO-INTERP: chord model error u_interp of the iso-power reference",
        "source": {"lane_25_open_decision": [6], "lane_25_threshold": "T-ISO-INTERP",
                   "input": ptr("minexp_draft", "/thresholds (id T-ISO-INTERP)")},
        "status": "OPEN_OWNER_DECISION",
        "options": [
            {"id": "D-04-A", "label": "pre-registered Type B bound (evidence class assumed)",
             "consequences": {
                 "statistics": {"u_interp_budget_at_n": {
                     n: from_input(docs, "minexp_draft", f"/derived_numbers/plan_by_n/{n}/u_interp_max")
                     for n in map(str, ctx.ns)}},
                 "readings": N(0, "added readings", "model-derived", comp("no added condition")),
                 "evidence": "R_iso classes then rest on an assumed chord error"}},
            {"id": "D-04-B", "label": "V_mid reading on HW-0 at OP2 and OP3 (+2 conditions per block)",
             "consequences": {
                 "readings": {
                     "hall_on_readings_per_block": N(mid["hall_on_readings_per_block"], "readings per block",
                                                     "model-derived",
                                                     comp(src_counts + " with two HW-0 S2 V_mid rows added")),
                     "baseline_hall_on_readings_per_block": N(base["hall_on_readings_per_block"],
                                                              "readings per block", "model-derived", comp(src_counts)),
                     "added_readings_at_n_min": N(
                         (mid["hall_on_readings_per_block"] - base["hall_on_readings_per_block"]) * ctx.n_min,
                         "readings", "model-derived", comp("difference x T-N-MIN"))},
                 "statistics": "families unchanged (the V_mid rows are references, not comparisons)",
                 "evidence": "the chord error is bounded by a measured deviation (measured, not assumed)"}},
        ],
        "recommendation": {"status": REC, "option": "D-04-B",
                           "rationale": "Replaces an assumed bound in the iso-power family by a measurement at a "
                                        "small, computed cost."},
    })

    # ---- D-05 lock location --------------------------------------------------------------------------------------
    D.append({
        "id": "D-05", "title": "Location of the LOCK-1 / LOCK-2 pre-registration files",
        "source": {"lane_25_open_decision": [11], "lane_06_item": "preregistration.lock_location",
                   "input": ptr("minexp_draft", "/preregistration/location")},
        "status": "OPEN_OWNER_DECISION",
        "constraint": "never under hallthruster_bridge/prereg/ (physics-track validation locks; lane 25 Sec. 10)",
        "options": [
            {"id": "D-05-A", "label": "docs/architecture_comparison/experiment_protocol/prereg/ (lane-06 PR-3 proposal)",
             "consequences": {"statistics": "none", "readings": "none",
                              "governance": "one lock location for the single protocol basis (reconciliation)"}},
            {"id": "D-05-B", "label": "docs/architecture_comparison/minimum_decisive_experiment/prereg/",
             "consequences": {"statistics": "none", "readings": "none",
                              "governance": "locks sit next to the lane-25 draft; lane 06 needs a pointer"}},
            {"id": "D-05-C", "label": "docs/architecture_comparison/experiment_package/prereg/",
             "consequences": {"statistics": "none", "readings": "none",
                              "governance": "locks sit next to this decision record"}},
        ],
        "recommendation": {"status": REC, "option": "D-05-A",
                           "rationale": "If the owner adopts one protocol basis (D-10), its lock belongs with the "
                                        "protocol; LOCK-1 then records this package's sha256 as the decision source."},
    })

    # ---- D-06 hardware configuration -------------------------------------------------------------------------------
    kk = {}
    for K, row in draft["derived_numbers"]["k_primary_by_remount_cycles"].items():
        kk[K] = {"k_primary": from_input(docs, "minexp_draft", f"/derived_numbers/k_primary_by_remount_cycles/{K}/k_primary"),
                 "S1b_readings": N(int(K.split("=")[1]) * ctx.r, "readings (non-score-bearing)", "model-derived",
                                   comp(f"{K} x T-S1-READINGS-PER-CYCLE"))}
    D.append({
        "id": "D-06", "title": "Hardware configuration: HW-0 spacer + S1b re-mounts, OPTION-DIVERTER, or lane-06 CFG-A/CFG-B",
        "source": {"lane_25_open_decision": [3, 10], "lane_06_item": "hardware_configurations (CFG-A / CFG-B)",
                   "input": ptr("minexp_draft", "/hardware_configurations")},
        "status": "OPEN_OWNER_DECISION",
        "options": [
            {"id": "D-06-A", "label": "HW-0 flow-equivalent spacer; K re-mount cycles in S1b (lane-25 default)",
             "consequences": {"statistics": {"k_primary_by_K_at_n_min": kk},
                              "hardware": "no new hardware; installation reproducibility must reach u_inst_max "
                                          "(D-01) or D0 fails"}},
            {"id": "D-06-B", "label": "OPTION-DIVERTER: in-vacuum feed-path switch, hall_only in the same installation",
             "consequences": {"statistics": "G5 removed: targets of D-01-B",
                              "readings": "one check against a true HW-0 (count TBD - requires the diverter design)",
                              "hardware": "TBD - requires a feasibility review of the diverter (gas path must be "
                                          "flow-equivalent in both positions)"}},
            {"id": "D-06-C", "label": "lane-06 CFG-A: both applicators installed, hall_only = both unenergized",
             "consequences": {"statistics": "no installation term between arms",
                              "bias": "the reference is not bare hall_only: gas passes both source chambers and an "
                                      "ECR permanent magnet perturbs B(z) (lane 25 Sec. 2); needs an HW-0 anchor to "
                                      "separate that installation effect",
                              "hardware": "TBD - requires a feasibility review of two applicators on one article"}},
            {"id": "D-06-D", "label": "lane-06 CFG-B: separate builds, sham controls, replicate builds",
             "consequences": {"statistics": "equivalent to D-06-A with the installed-off state as the sham "
                                            "(R_arch = R_within x R_install); replicate builds play the S1b role",
                              "hardware": "no new hardware"}},
        ],
        "recommendation": {"status": REC, "option": "D-06-A",
                           "rationale": "Needs no unproven hardware and keeps a true hall_only reference; adopt "
                                        "D-06-B later only if its feasibility review passes (then re-allocate G5, "
                                        "D-01-B)."},
    })

    # ---- D-07 delta ---------------------------------------------------------------------------------------------
    nr = draft["derived_numbers"]["n_required"]
    D.append({
        "id": "D-07", "title": "T-DELTA: equivalence / decision margin on ln R",
        "source": {"lane_25_open_decision": [1], "lane_25_threshold": "T-DELTA", "lane_06_item": "delta_m1 (TBD)",
                   "input": ptr("minexp_draft", "/thresholds (id T-DELTA)")},
        "status": "OPEN_OWNER_DECISION",
        "options": [{"id": f"D-07-{i}", "label": f"delta = {dk.split('=')[1]}",
                     "consequences": {"blocks_required_by_u_reading": {
                         uk: from_input(docs, "minexp_draft", f"/derived_numbers/n_required/{dk}/{uk}")
                         for uk in nr[dk]},
                         "within_T_N_MAX": {uk: nr[dk][uk]["within_T_N_MAX"] for uk in nr[dk]}}}
                    for i, dk in zip("AB", nr)],
        "recommendation": {"status": REC, "option": "D-07-A",
                           "rationale": "Keep the lane-25 T-DELTA at LOCK-1; D0 then tells whether the S1 repeatability "
                                        "supports it (widening delta after S1 is allowed only as a LOCK-1 restart)."},
    })

    # ---- D-08 blocks -------------------------------------------------------------------------------------------
    per_n = {}
    for n in ctx.ns:
        c = ctx.counts(n=n)
        per_n[str(n)] = {"hall_on_readings_full": N(c["hall_on_readings_full_at_n_min"], "readings", "model-derived",
                                                    comp(f"minexp_numbers.run_counts(n = {n})")),
                         "bench_readings": N(c["bench_readings_at_n_min"], "readings", "model-derived",
                                             comp(f"minexp_numbers.run_counts(n = {n})"))}
    D.append({
        "id": "D-08", "title": "T-N-MIN / T-N-MAX: admissible block counts (n fixed at LOCK-2 by readiness_n)",
        "source": {"lane_25_open_decision": [1], "lane_06_item": "replicates_min (3)",
                   "input": ptr("minexp_draft", "/thresholds (ids T-N-MIN, T-N-MAX)")},
        "status": "OPEN_OWNER_DECISION",
        "options": [{"id": "D-08-A", "label": "even n in [4, 8] (lane-25 proposal)",
                     "consequences": {"readings_by_n": per_n,
                                      "knee_scan_readings": N(base["knee_scan_readings"], "readings", "model-derived",
                                                              comp(src_counts)),
                                      "s1b_readings": N(base["s1b_remount_series_readings"], "readings",
                                                        "model-derived", comp(src_counts))}},
                    {"id": "D-08-B", "label": "lane-06 replicates_min = 3 (odd; no drift cancellation over pairs)",
                     "consequences": {"statistics": "below T-N-MIN; the lane-25 drift cancellation needs an even n",
                                      "value": l06(docs, "replicates_min")}}],
        "recommendation": {"status": REC, "option": "D-08-A",
                           "rationale": "Even n keeps the alternating source-level order; n itself is not chosen "
                                        "by the owner but computed by readiness_n from S1 values."},
    })

    # ---- D-09 tested Hall unit --------------------------------------------------------------------------------------
    D.append({
        "id": "D-09", "title": "Tested Hall unit H-1: Vyovrinda design or a surrogate",
        "source": {"lane_25_open_decision": [7], "input": ptr("minexp_draft", "/hardware_minimum/0")},
        "status": "OPEN_OWNER_DECISION",
        "options": [{"id": "D-09-A", "label": "Vyovrinda design (evidence level 1)",
                     "consequences": {"hard_gate_basis": "measurement_vyovrinda (verdict-bearing basis in the lane-24 "
                                                         "matrix, still point_design scope: hard-gate outcome "
                                                         "templates)",
                                      "milestone": "results are evidence about the proposed hardware"}},
                    {"id": "D-09-B", "label": "surrogate Hall unit (evidence level 3)",
                     "consequences": {"hard_gate_basis": "measurement_similar_hardware: not verdict-bearing in the "
                                                         "lane-24 matrix (computed: traceability.rows[].hard_gates[]."
                                                         "measurement_similar_hardware_verdict_bearing)",
                                      "milestone": "transfers to the Vyovrinda design only through an admitted "
                                                   "closure (credible set empty)"}}],
        "recommendation": {"status": REC, "option": "D-09-A",
                           "rationale": "Only level-1 data can serve milestone A without an admitted closure."},
    })

    # ---- D-10 boundary basis and classes (single protocol basis) ------------------------------------------------------
    D.append({
        "id": "D-10", "title": "Single protocol basis: adopt the reconciliation (boundary, classes, "
                               "multiplicity, extinction, ordering, controls)",
        "source": {"lane_25_open_decision": [10], "lane_06_item": "open_items_for_owner",
                   "input": ptr("minexp_draft", "/related_lanes/0")},
        "status": "OPEN_OWNER_DECISION",
        "options": [{"id": "D-10-A", "label": "adopt the PROPOSED single basis (reconciliation section)",
                     "consequences": {"see": "reconciliation.proposed_single_basis"}},
                    {"id": "D-10-B", "label": "run lane 25 and lane 06 as separate protocols",
                     "consequences": {"risk": "two classification vocabularies and two P_bus bases for the same "
                                              "readings; the admissibility rule (one boundary) is then met by only one"}}],
        "recommendation": {"status": REC, "option": "D-10-A",
                           "rationale": "One boundary basis and one class vocabulary are needed for an admissible "
                                        "comparison (operating model Sec. 3)."},
    })

    # ---- D-11 common loads / compressor / feed state ----------------------------------------------------------------
    D.append({
        "id": "D-11", "title": "Unmeasured common loads: compressor bus draw and valve-outlet feed state",
        "source": {"lane_25_open_decision": [2], "lane_06_item": "compressor_bus_power (TBD)",
                   "input": ptr("protocol", "/bus_power_boundary/laboratory_subset")},
        "status": "OPEN_OWNER_DECISION",
        "tbd": [TBD("compressor bus draw per operating point", "upstream ICD compressor bus power",
                    ["lane_33_upstream_icd (not verified)"]),
                TBD("valve-outlet feed state (mdot_min, mdot_nom, composition, p_feed, T_feed; IF-A5)",
                    "feed design inputs with provenance (feed envelope status DESIGN_INPUTS_MISSING)",
                    ["lane_16_feed_envelope (design inputs)"])],
        "options": [{"id": "D-11-A", "label": "report PARTIAL_BOUNDARY classes until the ICD compressor draw exists; "
                                               "V1-basis classes only after it",
                     "consequences": {"admissibility": "PARTIAL-basis classes are not bus_power_boundary_v1 results "
                                                       "and are not admissible Bundle-1 comparison fields",
                                      "direction": "a common additive load P_c multiplies R: R_v1 = R_lab x "
                                                   "(1 + P_c/P_0) / (1 + P_c/P_X), a factor > 1 when P_X > P_0, so a "
                                                   "PARTIAL-basis class is biased against the source arm relative to "
                                                   "the V1 basis (lane 25 Sec. 3.7: common loads raise C*)"}},
                    {"id": "D-11-B", "label": "fix a compressor ledger input at LOCK-1 (lane-25 Sec. 6.7 style)",
                     "consequences": {"compliance": "would fill the compressor draw before lane 33 is verified; not "
                                                    "available to this package (task rule)"}}],
        "recommendation": {"status": REC, "option": "D-11-A",
                           "rationale": "Never fills the compressor draw or the feed state; the V1 basis is added when "
                                        "the upstream ICD supplies it, with its own evidence class."},
    })

    # ---- D-12 facility and T-PB-MAX --------------------------------------------------------------------------------
    D.append({
        "id": "D-12", "title": "Facility per stage and T-PB-MAX; number of elevated background-pressure levels",
        "source": {"lane_25_open_decision": [8], "lane_25_threshold": "T-PB-MAX, T-PB-ELEV-FACTOR",
                   "lane_06_item": "pbg_elevated_levels_min",
                   "input": ptr("minexp_draft", "/thresholds (id T-PB-MAX)")},
        "status": "OPEN_OWNER_DECISION",
        "tbd": [TBD("T-PB-MAX", "facility specification and owner decision at LOCK-1", ["owner", "facility data"]),
                TBD("total grid flow (sets S_eff = Q/p_b)", "IF-A5 feed envelope", ["lane_16_feed_envelope"])],
        "options": [{"id": "D-12-A", "label": "one elevated level (2 x base p_b, lane 25)",
                     "consequences": {"S5_readings_per_block": N(ctx.stage_readings("S5"), "readings per block",
                                                                 "model-derived",
                                                                 comp("minexp_numbers.readings_per_visit over the S5 "
                                                                      "rows of the run matrix"))}},
                    {"id": "D-12-B", "label": "two elevated levels (lane 06 pbg_elevated_levels_min = 2)",
                     "consequences": {"S5_readings_per_block": N(2 * ctx.stage_readings("S5"), "readings per block",
                                                                 "model-derived",
                                                                 comp("2 x the S5 readings (second elevated level "
                                                                      "repeats every S5 visit)")),
                                      "statistics": {
                                          "m_facility_one_level": from_input(docs, "minexp_draft",
                                                                             "/derived_numbers/m_family/facility"),
                                          "m_facility_two_levels_classified": N(
                                              2 * ctx.fam["facility"], "comparisons", "model-derived",
                                              comp("2 x minexp_numbers.family_sizes(...)['facility']")),
                                          "note": "unless the second level is reported without classification"},
                                      "value": l06(docs, "pbg_elevated_levels_min")}}],
        "recommendation": {"status": REC, "option": "D-12-A",
                           "rationale": "One classified elevated level (sign and size of the p_b sensitivity); a "
                                        "second level only as an unclassified slope check if the facility allows."},
    })

    # ---- D-13 ignition --------------------------------------------------------------------------------------------
    aid = docs["protocol"]["statistics"]["ignition_decision_aid"]["rows"]
    D.append({
        "id": "D-13", "title": "Ignition / start attempts (not in the lane-25 minimum; lane-06 M5; G6.ignition, HS-A6)",
        "source": {"lane_06_item": "decision_metrics M5, statistics.ignition_decision_aid",
                   "input": ptr("protocol", "/statistics/ignition_decision_aid")},
        "status": "OPEN_OWNER_DECISION",
        "tbd": [TBD("ignition_p_min and ignition_attempts", "owner/system requirement (start-cycle budget)", ["owner"])],
        "options": [{"id": "D-13-A", "label": "exclude (lane-25 minimum): ignition stays unmeasured",
                     "consequences": {"evidence": "HS-A6 and G6.ignition stay UNDETERMINED from this experiment"}},
                    {"id": "D-13-B", "label": "add an ignition-attempt module per arm (xenon-assisted and, if the "
                                              "cathode lane admits it, air-only), non-score-bearing for R",
                     "consequences": {"attempts_for_zero_failure_demonstration": [
                         {"target": from_input(docs, "protocol",
                                               f"/statistics/ignition_decision_aid/rows/{i}/target"),
                          "attempts": from_input(docs, "protocol",
                                                 f"/statistics/ignition_decision_aid/rows/{i}/n_min_zero_failures")}
                         for i in range(len(aid))],
                         "confidence": l06(docs, "aid_confidence"),
                         "note": "illustrative targets from lane 06 (one-sided zero-failure bound); attempts are per "
                                 "arm and propellant"}}],
        "recommendation": {"status": REC, "option": "D-13-B",
                           "rationale": "Start is a binding gate criterion (G6.ignition) and a Bundle-1 condition "
                                        "(HS-A6) that the minimum otherwise leaves open; the owner sets the target."},
    })

    # ---- D-14 physics-track pre-registration ---------------------------------------------------------------------
    D.append({
        "id": "D-14", "title": "Whether the physics track pre-registers any result as Hall-closure evidence",
        "source": {"lane_25_open_decision": [], "input": ptr("minexp_draft", "/preregistration/locks/0/contents/8")},
        "status": "OPEN_OWNER_DECISION",
        "options": [{"id": "D-14-A", "label": "no physics-track use (architecture comparison only)",
                     "consequences": {"milestone_B": "B(z), I_d traces, species and divergence are published but are "
                                                     "not promotion evidence"}},
                    {"id": "D-14-B", "label": "physics track files its own pre-registration before S1",
                     "consequences": {"milestone_B": "the same readings could become genuinely new predictive "
                                                     "evidence (Question A disposition rule 2) only if pre-registered "
                                                     "before measurement"}}],
        "recommendation": {"status": REC, "option": "D-14-B",
                           "rationale": "Costs no readings; the decision belongs to the physics track."},
    })

    # ---- D-15 scope extensions --------------------------------------------------------------------------------
    D.append({
        "id": "D-15", "title": "Scope extensions outside the minimum: Xe anode operation, second V_d on source arms, "
                               "Xe health check",
        "source": {"lane_25_open_decision": [9], "lane_06_item": "controls XE_HEALTH_CHECK, F-PROP Xe reference",
                   "input": ptr("protocol", "/controls/3")},
        "status": "OPEN_OWNER_DECISION",
        "options": [{"id": "D-15-A", "label": "none (minimum)", "consequences": {"evidence": "G7 (air + Xe) and the "
                                                                                              "Xe mode stay unmeasured"}},
                    {"id": "D-15-B", "label": "add the lane-06 XE_HEALTH_CHECK (hall_only on Xe, start and end of "
                                              "each test day)",
                     "consequences": {"readings": "one reading at the start and one at the end of each test day; "
                                                  "test-day count TBD - requires the facility schedule", "hardware": "Xe anode feed line in addition to the "
                                                                          "cathode Xe line"}}],
        "recommendation": {"status": REC, "option": "D-15-B",
                           "rationale": "A drift reference independent of the N2 grid; the Xe mode as a comparison "
                                        "arm stays outside the minimum."},
    })

    # consistency: every lane-25 open owner decision is covered
    covered = sorted({i for d in D for i in d["source"].get("lane_25_open_decision", [])})
    if covered != list(range(1, len(lane25_open) + 1)):
        raise ValueError(f"lane-25 open owner decisions not all covered: {covered}")
    for d in D:      # reference by pointer (strings), so no bare number appears outside a number object
        d["source"]["lane_25_open_decision"] = [ptr("minexp_draft", f"/open_owner_decisions/{i - 1}")
                                                for i in d["source"].get("lane_25_open_decision", [])]
    return D


# ------------------------------------------------------------------------------------------------------------------
# (2) traceability matrix
# ------------------------------------------------------------------------------------------------------------------
def rf_thresholds(docs):
    rf = docs["overlay_rf"]
    common = {"C_del_above_which_CLEARLY_ABOVE": from_input(
        docs, "overlay_rf", "/decisive_measurement_common/C_del_above_which_CLEARLY_ABOVE_W_per_A", "W/A",
        "model-derived"),
        "C_del_at_or_below_which_CLEARLY_BELOW_add_only": from_input(
            docs, "overlay_rf", "/decisive_measurement_common/C_del_at_or_below_which_CLEARLY_BELOW_add_only_W_per_A",
            "W/A", "model-derived", note="small delivered shares only; in between, the Hall reference (milestone B) "
                                         "decides")}
    per_unit = []
    for i, p in enumerate(rf["evidence_placements"]):
        v = p["decisive_measurements"]["eta_t_below_which_CLEARLY_ABOVE"]
        per_unit.append({"unit_id": p["unit_id"], "placement": p["placement"]["status"],
                         "eta_t_below_which_CLEARLY_ABOVE":
                             from_input(docs, "overlay_rf", f"/evidence_placements/{i}/decisive_measurements/"
                                                            "eta_t_below_which_CLEARLY_ABOVE", "-", "model-derived")
                             if v is not None else {"value": "none", "reason": "no eta_t <= 1 moves this unit to "
                                                                              "CLEARLY_ABOVE (overlay)"}})
    return common, per_unit


def ecr_thresholds(docs):
    ecr = docs["overlay_ecr"]
    out = []
    for i, p in enumerate(ecr["evidence_placements"]):
        tdp = p["to_definite_placement"]
        j_eta = next(j for j, t in enumerate(tdp) if t["measurement"].startswith("interstage transport efficiency"))
        j_cdel = next(j for j, t in enumerate(tdp) if t["measurement"].startswith("end-to-end bus cost"))
        base = f"/evidence_placements/{i}/to_definite_placement"
        out.append({"entry": p["id"], "mode": p["mode"], "placement": p["placement"],
                    "eta_t_below_which_CLEARLY_ABOVE": from_input(docs, "overlay_ecr", f"{base}/{j_eta}/if_below", "-",
                                                                  "model-derived"),
                    "C_del_bus_above_which_CLEARLY_ABOVE": from_input(
                        docs, "overlay_ecr", f"{base}/{j_cdel}/thresholds_W_per_A/Y_max_any_case", "W/A",
                        "model-derived"),
                    "C_del_bus_at_or_below_which_CLEARLY_BELOW_add_only": from_input(
                        docs, "overlay_ecr", f"{base}/{j_cdel}/thresholds_W_per_A/Y_min_by_case/add_only", "W/A",
                        "model-derived", note="small delivered shares only")})
    return out


def bundle1_conditions(docs) -> dict:
    rf = docs["overlay_rf"]["milestone_A_statement"]["conditions_for_rf_hall_as_baseline"]
    rf_ids = {}
    for i, s in enumerate(rf):
        m = re.match(r"^(C\d)\b", s)
        if not m:
            raise ValueError(f"RF milestone-A condition {i} has no id: {s[:40]}")
        rf_ids[m.group(1)] = ptr("overlay_rf", f"/milestone_A_statement/conditions_for_rf_hall_as_baseline/{i}")
    ecr_text = docs["overlay_ecr"]["milestone_A_statement"]["condition_set_for_milestone_A"]
    ecr_ids = {}
    for tag in ("A", "B", "C", "D"):
        if f"({tag})" not in ecr_text:
            raise ValueError(f"ECR condition ({tag}) not found")
        ecr_ids[f"ECR-{tag}"] = ptr("overlay_ecr", "/milestone_A_statement/condition_set_for_milestone_A") + f" ({tag})"
    hs = {c["id"]: ptr("overlay_hs", f"/milestone_A_conditions/{i}") + f" [state: {c['state'][:60]}]"
          for i, c in enumerate(docs["overlay_hs"]["milestone_A_conditions"])}
    return {"rf_hall": rf_ids, "ecr_hall": ecr_ids, "hall_sustainment": hs}


EXPERIMENT_PROPELLANTS = ["n2_surrogate"]      # matrix vocabulary; the N2+O2 air surrogate has no matrix label


def hard_gate_assessment(hg, matrix, crit_ids: list[str]) -> list[dict]:
    """For each criterion: can the minimum experiment's output be verdict-bearing? Computed from the matrix."""
    bases = matrix["evidence_policy"]["bases"]
    crits = {c["id"]: (g, c) for g in matrix["gates"] for c in g["criteria"]}
    out = []
    for cid in crit_ids:
        g, c = crits[cid]
        env_props = c["envelope"].get("propellants")
        covers = env_props is None or bool(set(EXPERIMENT_PROPELLANTS) & set(env_props))
        out.append({
            "criterion": cid, "gate": g["id"], "gate_status": g["status"], "binding": g["binding"],
            "counts_for_fail": c["counts_for_fail"],
            "envelope_propellants": env_props,
            "experiment_propellants_cover_envelope": covers,
            "measurement_vyovrinda_pass_basis": "measurement_vyovrinda" in c["pass_sufficient_bases"],
            "measurement_vyovrinda_fail_basis": "measurement_vyovrinda" in c["fail_sufficient_bases"],
            "measurement_similar_hardware_verdict_bearing": bases["measurement_similar_hardware"]["verdict_bearing"],
            "issuable_at": hg.issuable_at(c, matrix),
            "can_pass_from_minimum_experiment": covers and "measurement_vyovrinda" in c["pass_sufficient_bases"],
            "can_eliminate_from_minimum_experiment": False,
            "why_not_eliminating": "one tested unit is point_design scope; only architecture-scope FAIL evidence "
                                   "makes an architecture FAIL (matrix evidence_policy.scopes)"
                                   + ("" if covers else "; the tested feed does not cover the criterion's "
                                                        "envelope propellants"),
        })
    return out


def traceability(docs, hg, matrix) -> dict:
    ft = docs["failure_tree"]
    node_by_id = {n["id"]: n for n in ft["nodes"]}
    action_ids = {a["id"] for a in ft["actions"]}
    b1 = bundle1_conditions(docs)
    rf_common, rf_units = rf_thresholds(docs)
    ecr = ecr_thresholds(docs)
    lane25_meas = {m["id"] for m in docs["minexp_draft"]["measurements"]}
    lane25_q = {q["id"] for q in docs["minexp_draft"]["decisive_quantities"]}

    def ft_links(pairs):
        res = []
        for node, action in pairs:
            n = node_by_id[node]
            if action not in action_ids:
                raise ValueError(f"unknown failure-tree action {action}")
            eff = next((a["effect"] for a in n["actions"] if a["action"] == action), None)
            res.append({"node": node, "title": n["title"], "architectures": n["architectures"], "action": action,
                        "effect_in_tree": eff if eff else "not listed for this node in lane 26 (package assessment: "
                                                          "informs)",
                        "resolve_by_milestone": n["resolve_by_milestone"],
                        "analysis_requires_admitted_hall_closure": n["analysis_requires_admitted_hall_closure"]})
        return res

    def b1c(arch, cid, coverage, note):
        src = b1[arch][cid]
        return {"architecture_or_overlay": arch, "condition": cid, "source": src, "coverage": coverage, "note": note}

    rows = [
        {"id": "TR-01", "measurement": {"lane25": ["M5"], "quantities": ["Q1"], "stages": ["S3"]},
         "what": "delivered ion current I_del across the Hall channel exit plane (Hall discharge off, magnet on)",
         "breakeven_placement": {
             "rf_hall": {"common": rf_common, "role": "denominator of C_del = P_bus[rf_source]/I_del"},
             "ecr_hall": {"per_entry": ecr, "role": "denominator of C_del,bus (subsumes phi, k, eta_chain, eta_t)"}},
         "bundle1_conditions": [b1c("rf_hall", "C1", "direct", "with TR-03: C_del at the tested point"),
                                b1c("ecr_hall", "ECR-A", "partial", "N2 and N2+O2 surrogate only; no atomic O")],
         "hard_gates": [], "failure_tree": ft_links([("N-ISL-RF", "M-PREION"), ("N-ISL-ECR", "M-PREION")]),
         "limits": ["cold transport (Hall off) may differ from Hall-on transport (lane 25 Sec. 3.4)"]},
        {"id": "TR-02", "measurement": {"lane25": ["M5"], "quantities": ["Q3"], "stages": ["S3"]},
         "what": "interstage transport efficiency eta_ts = I_del / I_src",
         "breakeven_placement": {"rf_hall": {"per_unit": rf_units, "role": "eta_t below the unit threshold -> "
                                                                             "CLEARLY_ABOVE_BREAKEVEN with any chain"},
                                 "ecr_hall": {"per_entry": [{k: e[k] for k in ("entry", "mode", "placement",
                                                                               "eta_t_below_which_CLEARLY_ABOVE")}
                                                            for e in ecr],
                                              "role": "eta_t below the entry threshold -> CLEARLY_ABOVE_BREAKEVEN"}},
         "bundle1_conditions": [b1c("rf_hall", "C2", "direct", "same charge-current basis required"),
                                b1c("ecr_hall", "ECR-B", "direct", "same charge-current basis required")],
         "hard_gates": [], "failure_tree": ft_links([("N-ISL-RF", "M-PREION"), ("N-ISL-ECR", "M-PREION")]),
         "limits": ["species/charge basis from M7 (E x B) is explanatory only in the minimum"]},
        {"id": "TR-03", "measurement": {"lane25": ["M3", "M2"], "quantities": ["Q2"], "stages": ["S3", "S4"]},
         "what": "source load-plane power (net RF / microwave at the coupling terminals; ecr_magnet coil power) and "
                 "its bus draw through the pre-registered ledger efficiency",
         "breakeven_placement": {"rf_hall": {"role": "numerator of C_del; also resolves the antenna/matching loss "
                                                     "named in the RF units' single measurements"},
                                 "ecr_hall": {"role": "numerator of C_del,bus; power plane phi (forward/reflected at "
                                                      "the coupling input; ECR overlay G9 item 4)"}},
         "bundle1_conditions": [b1c("rf_hall", "C5", "partial", "complete ledger needs the compressor draw (TBD, "
                                                                "lane 33) and flight chain efficiencies"),
                                b1c("rf_hall", "C1", "direct", "with TR-01")],
         "hard_gates": hard_gate_assessment(hg, matrix, ["G2.bus_power_max"]),
         "failure_tree": ft_links([("N-PWR-02", "M-PREION"), ("N-PWR-03", "M-PREION"), ("N-PWR-04", "M-PREION")]),
         "limits": ["bus draw = load / ledger efficiency: evidence class reconstructed while the flight chain is "
                    "unmeasured"]},
        {"id": "TR-04", "measurement": {"lane25": ["M2", "M3"], "quantities": [], "stages": ["S3"]},
         "what": "lab generator DC input vs load-plane power: eta_lab (efficiency evidence only, never in R_arch)",
         "breakeven_placement": {"ecr_hall": {"role": "eta_chain threshold per entry equals the eta_t threshold "
                                                      "(TR-02); a LAB generator value is not the flight chain"}},
         "bundle1_conditions": [],
         "hard_gates": [],
         "failure_tree": ft_links([("N-ECR-03", "M-MWCHAIN")]),
         "limits": ["flight microwave / RF chain efficiency: TBD - requires M-MWCHAIN on the candidate flight chain"]},
        {"id": "TR-05", "measurement": {"lane25": ["M1", "M2", "M3"], "quantities": ["Q5", "Q6"],
                                        "stages": ["S2", "S4"]},
         "what": "R_arch = (T/P_bus)_X / (T/P_bus)_hall_only at the same point, bus_power_ledger basis",
         "breakeven_placement": {"both": {"role": "R_arch > 1 <=> C_del < C* (identity, lane 25 Sec. 3.2): the "
                                                  "measured form of the overlays' break-even inequality at the "
                                                  "tested Hall point"}},
         "bundle1_conditions": [b1c("rf_hall", "C1", "direct", "at the tested hardware point only"),
                                b1c("ecr_hall", "ECR-A", "partial", "tested hardware point; no atomic O")],
         "hard_gates": hard_gate_assessment(hg, matrix, ["G1.thrust_floor"]),
         "failure_tree": ft_links([("N-UTL-02", "M-PREION"), ("N-UTL-03", "M-PREION"), ("N-UTL-01", "M-PREION"),
                                   ("N-PWR-01", "M-PREION")]),
         "limits": ["PARTIAL_BOUNDARY until the compressor draw exists (D-11)",
                    "thrust at lab feed, not the delivered feed (lane 16 TBD)"]},
        {"id": "TR-06", "measurement": {"lane25": ["M1", "M4", "M5"], "quantities": ["Q4", "Q5"], "stages": ["S4"]},
         "what": "response: y = dT/I_del and kappa = dI_d/I_del (thrust and discharge current bought per delivered "
                 "ampere)",
         "breakeven_placement": {"both": {"role": "collapses the overlays' response case (alpha, chi, eta_v,S) at "
                                                  "the tested point; the overlays list the response case as a "
                                                  "straddle reason"}},
         "bundle1_conditions": [b1c("rf_hall", "C4", "direct", "coupled RF + Hall test"),
                                b1c("rf_hall", "C3", "partial", "utilization gain needs beam current / species "
                                                                "(TR-10)"),
                                b1c("ecr_hall", "ECR-C", "partial", "utilization gain X needs TR-10")],
         "hard_gates": [], "failure_tree": ft_links([("N-SUS-03", "M-PREION")]),
         "limits": ["y may exceed y_max and kappa may be negative (lane 25 Sec. 3.4)"]},
        {"id": "TR-07", "measurement": {"lane25": [], "quantities": [], "stages": ["S4"],
                                        "derived": ["C_star", "eta_src_be"]},
         "what": "measured break-even cost C* and break-even source-chain efficiency eta_src,be at every compared "
                 "condition",
         "breakeven_placement": {"both": {"role": "replaces the PROPOSED Hall box by a measured Y at the tested "
                                                  "hardware point; eta_src,be is the milestone-A condition on the "
                                                  "flight source chain"}},
         "bundle1_conditions": [b1c("rf_hall", "C1", "direct", "Y at the tested point"),
                                b1c("ecr_hall", "ECR-A", "partial", "no atomic O")],
         "hard_gates": [], "failure_tree": ft_links([("N-UTL-02", "M-PREION"), ("N-UTL-03", "M-PREION")]),
         "limits": ["tested hardware only; transfer to other designs needs an admitted closure (milestone B)"]},
        {"id": "TR-08", "measurement": {"lane25": ["M4", "M9", "M10"], "quantities": [], "stages": ["S2", "S4"]},
         "what": "sustainment: S2 knee scan (flow-down and up) and per-condition ENABLES / DISABLES / "
                 "NEITHER_SUSTAINED classes",
         "breakeven_placement": {},
         "bundle1_conditions": [b1c("hall_sustainment", "HS-A2", "partial",
                                    "DM-2 flow-down extinction scan at the tested V_d/B on N2 (and one air-surrogate "
                                    "point); the composition transfer stays stated"),
                                b1c("hall_sustainment", "HS-A5", "partial", "knee scan spans mdot_min..mdot_nom only")],
         "hard_gates": hard_gate_assessment(hg, matrix, ["G6.sustainment"]),
         "failure_tree": ft_links([("N-SUS-01", "M-SUSWIN"), ("N-SUS-02", "M-SUSWIN"),
                                   ("N-IGN-04", "M-PREION")]),
         "limits": ["one V_d and one magnet setting (M-SUSWIN asks for a window map)"]},
        {"id": "TR-09", "measurement": {"lane25": ["M11"], "quantities": [], "stages": ["S1"]},
         "what": "B(z) per configuration with coil currents (source magnet on/off)",
         "breakeven_placement": {},
         "bundle1_conditions": [b1c("hall_sustainment", "HS-A4", "partial", "design B stated and measured; DI-2 "
                                                                            "still needs the design point")],
         "hard_gates": [], "failure_tree": ft_links([("N-RF-03", "M-PREION"), ("N-ECR-02", "M-ECRSRC")]),
         "limits": ["milestone-B Hall-map input (docs/hallmap/) for the tested hardware"]},
        {"id": "TR-10", "measurement": {"lane25": ["M6", "M7", "M8"], "quantities": [], "stages": ["S3", "S4"]},
         "what": "ion energy distribution, species fractions and far-field beam current / divergence",
         "breakeven_placement": {"rf_hall": {"role": "beam species/charge split named in the RF units' single "
                                                     "measurements"},
                                 "ecr_hall": {"role": "ion basis k of the ECR entries (G9 item 5)"}},
         "bundle1_conditions": [b1c("rf_hall", "C3", "partial", "utilization gain x"),
                                b1c("ecr_hall", "ECR-C", "partial", "utilization gain X")],
         "hard_gates": [], "failure_tree": ft_links([("N-UTL-01", "M-PREION")]),
         "limits": ["E x B probe optional in the minimum; low-energy species need an accelerating bias "
                    "(REF-ROVEY2025 via lane 25)"]},
        {"id": "TR-11", "measurement": {"lane25": ["M9"], "quantities": [], "stages": ["S5"]},
         "what": "background pressure and the S5 elevated-p_b facility check",
         "breakeven_placement": {},
         "bundle1_conditions": [],
         "hard_gates": [], "failure_tree": [],
         "limits": ["facility qualifier only; no ingestion correction (P5-N2 lesson)"]},
        {"id": "TR-12", "measurement": {"lane25": ["M14"], "quantities": [], "stages": ["S1", "S4"],
                                        "lane06": ["DUMMY_LOAD_PICKUP"]},
         "what": "electrical environment and generator pickup on common diagnostics",
         "breakeven_placement": {},
         "bundle1_conditions": [],
         "hard_gates": [], "failure_tree": ft_links([("N-RF-04", "M-PREION")]),
         "limits": []},
        {"id": "TR-13", "measurement": {"lane25": ["M12"], "quantities": [], "stages": ["S1", "S4"]},
         "what": "temperatures (thermal settling; source waste heat)",
         "breakeven_placement": {},
         "bundle1_conditions": [],
         "hard_gates": [], "failure_tree": ft_links([("N-THM-02", "M-THERMAL"), ("N-THM-03", "M-THERMAL")]),
         "limits": ["not a thermal-vacuum balance test; milestone-C input only"]},
        {"id": "TR-14", "measurement": {"lane25": ["M3", "M5"], "quantities": [], "stages": ["S3"],
                                        "gates": ["G-SRC"]},
         "what": "source bench: plasma sustained at each grid flow within P_hi (lane-25 G-SRC)",
         "breakeven_placement": {},
         "bundle1_conditions": [],
         "hard_gates": [],
         "failure_tree": ft_links([("N-IGN-02", "M-RFSRC"), ("N-IGN-03", "M-ECRSRC"), ("N-ECR-01", "M-ECRSRC"),
                                   ("N-RF-01", "M-RFSRC")]),
         "limits": ["G-SRC stops an arm inside this experiment; it is NOT a lane-24 elimination (Sec. 2)",
                    "no E-H hysteresis scan in the minimum (N-RF-01 needs M-RFSRC in full)"]},
        {"id": "TR-15", "measurement": {"lane25": ["M10", "M13"], "quantities": [], "stages": ["S4"],
                                        "operating_points": ["OP5"]},
         "what": "air-surrogate point (N2 + O2, no atomic O) at the knee flow",
         "breakeven_placement": {"ecr_hall": {"role": "the overlay's air arm stays NOT_PLACEABLE for its O content "
                                                      "(no atomic O in a bottled surrogate)"}},
         "bundle1_conditions": [b1c("hall_sustainment", "HS-A3", "partial", "O2 fraction tested; atomic O not")],
         "hard_gates": [], "failure_tree": [],
         "limits": ["composition at IF-A5: TBD - requires lane 16 design inputs"]},
    ]
    used_m = {m for r in rows for m in r["measurement"]["lane25"]}
    used_q = {q for r in rows for q in r["measurement"]["quantities"]}
    if used_m != lane25_meas or used_q != lane25_q:
        raise ValueError(f"traceability must cover every lane-25 measurement and quantity: missing "
                         f"{sorted(lane25_meas - used_m)} {sorted(lane25_q - used_q)}")
    # failure-tree nodes that name M-PREION but are not traced
    preion_nodes = sorted(n["id"] for n in ft["nodes"] if any(a["action"] == "M-PREION" for a in n["actions"]))
    traced = sorted({l["node"] for r in rows for l in r["failure_tree"]})
    return {"rows": rows,
            "failure_tree_nodes_naming_M_PREION": preion_nodes,
            "M_PREION_nodes_not_traced": sorted(set(preion_nodes) - set(traced)),
            "experiment_propellants_matrix_vocabulary": EXPERIMENT_PROPELLANTS}


# ------------------------------------------------------------------------------------------------------------------
# hard-gate outcome templates through the lane-24 evaluator
# ------------------------------------------------------------------------------------------------------------------
SYN = "SYNTHETIC outcome template of this package (not evidence; never registered)"


def outcome_templates(hg, matrix) -> dict:
    crit = next(c for g in matrix["gates"] for c in g["criteria"] if c["id"] == "G6.sustainment")
    gid = "G6_ignition_sustainment"

    def item(iid, arch, props):
        return {"id": iid, "architectures": [arch], "gate": gid, "criterion": "G6.sustainment",
                "metric": crit["metric"], "unit": crit["unit"], "value": {"kind": "boolean", "value": False},
                "basis": "measurement_vyovrinda", "quantity_type": "measured", "evidence_level": 1,
                "scope": "point_design", "design_id": "H-1 (tested unit)",
                "conditions": {"propellants": props, "operating_modes": ["steady"], "altitude_km": [180, 230],
                               "atmosphere_states": ["low", "mean", "high"], "feed_equivalence": SYN},
                "hall_closure": {"status": "none"}, "source": SYN, "uncertainty": SYN, "applicability_domain": SYN,
                "validation_status": SYN, "transformation_chain": SYN}

    out = []
    for arch in ARCHS:
        for tag, props, meaning in (
                ("T1", ["n2_surrogate"], "most adverse sustainment outcome on the N2 grid (not sustained at every "
                                         "tested flow), labelled as the lab feed actually is"),
                ("T2", ["atmospheric"], "the same outcome with a hypothetically accepted feed equivalence to the "
                                        "delivered atmospheric feed")):
            items = [item(f"TEMPLATE-EXPPKG-{tag}-{arch}", arch, props)]
            r = hg.evaluate(arch, items)
            g = r["gates"][gid]
            c = g["criteria"]["G6.sustainment"]
            out.append({"template": tag, "architecture": arch, "meaning": meaning,
                        "evaluator_eliminated": r["eliminated"], "gate_verdict": g["verdict"],
                        "criterion_verdict": c["verdict"],
                        "design_failures": sorted(c["design_failures"]),
                        "not_verdict_bearing_reasons": [e["reasons"] for e in r["evidence_not_verdict_bearing"]]})
    if any(t["evaluator_eliminated"] for t in out):
        raise RuntimeError("an outcome template eliminated an architecture: the package logic is wrong")
    return {"evaluator": "abep_sim/hard_gates.py evaluate() (lane 24), matrix " + INPUTS["hg_matrix"][0],
            "templates": out,
            "reading": "Even the most adverse sustainment outcome the minimum experiment can produce eliminates no "
                       "architecture through lane 24: a single tested unit is point_design scope (recorded as a "
                       "design failure at most), and the lab N2 feed does not cover 'atmospheric'. The lane-25 G-SRC "
                       "and D3 stops end an arm's runs inside the experiment only."}


def current_gate_status(docs) -> dict:
    st = docs["hg_status"]
    return {"source": INPUTS["hg_status"][0], "eliminated": st["eliminated"], "not_eliminated": st["not_eliminated"],
            "admitted_members": st["admitted_members"],
            "register_items": N(len(docs["hg_register"]["items"]), "evidence items", "model-derived",
                                ptr("hg_register", "/items") + " (count)")}


# ------------------------------------------------------------------------------------------------------------------
# (3) reconciliation lane 25 vs lane 06
# ------------------------------------------------------------------------------------------------------------------
def reconciliation(docs, ab) -> dict:
    p = docs["protocol"]
    e = docs["minexp_draft"]
    l06 = {c["id"]: c["v1_component_ids"] for c in p["bus_power_boundary"]["components"]}
    l06_cov = sorted(v for vs in l06.values() for v in vs)
    l25_cov = sorted(e["bus_power_boundary"]["components_common"]
                     + [c for a in ARCHS for c in e["bus_power_boundary"]["components_arm_specific"][a]])
    contract = sorted(ab.ALL_COMPONENTS)
    mapping_ok = {"lane06_covers_contract_exactly_once": l06_cov == contract,
                  "lane25_covers_contract_exactly_once": l25_cov == contract,
                  "contract_version": ab.BOUNDARY_VERSION,
                  "lane06_to_contract": l06}
    if not (mapping_ok["lane06_covers_contract_exactly_once"] and mapping_ok["lane25_covers_contract_exactly_once"]):
        raise ValueError("component mapping of lane 06 or lane 25 no longer covers the bus_power_boundary_v1 contract")
    dims = [
        {"dimension": "boundary basis",
         "lane25": "load-plane power per contract component / pre-registered ledger efficiency "
                   "(abep_sim/arch_boundary.py bus_power_ledger); lab DC input only as efficiency evidence",
         "lane06": "DC input of each consumer from a common lab bus; P_out/eta_conv reconstruction where a lab "
                   "supply replaces a bus-fed converter; PARTIAL (no compressor) vs V1 labels",
         "proposed_single_basis": "decisive P_bus on the contract basis (load plane / ledger efficiency, lane 25), "
                                  "with lane-06 DC-input metering kept as measured efficiency evidence and lane-06 "
                                  "PARTIAL_BOUNDARY / V1 labels adopted; V1 only when the ICD compressor draw exists "
                                  "(D-11)",
         "why": "the contract is the shared definition every lane uses; lab converters are not flight hardware; the "
                "labels prevent a partial-boundary ratio from being read as a bus_power_boundary_v1 result"},
        {"dimension": "component ids",
         "lane25": "contract ids directly", "lane06": "own ids mapped name-by-name to the contract",
         "proposed_single_basis": "contract ids in all records; lane-06 ids as instrument-channel labels",
         "why": "both map onto the contract exactly once (checked: mapping_check)"},
        {"dimension": "decisive metric and classes",
         "lane25": "ln R_arch; EQUIVALENT / SOURCE_BETTER / SOURCE_WORSE / UNRESOLVED against delta, plus "
                   "ENABLES / DISABLES / NEITHER_SUSTAINED / SUSTAINMENT_MIXED / INFEASIBLE_AT_POINT / "
                   "NOT_SCOREABLE_FACILITY / NOT_TESTED",
         "lane06": "M1 ratio classes HIGHER / LOWER / NOT_DISTINGUISHED against delta_m1 (TBD); M2-M6 secondary",
         "proposed_single_basis": "lane-25 classes for M1 (thrust per bus power); lane-06 M2-M6 reported as "
                                  "secondary metrics without entering the primary family",
         "why": "lane-25 classes are defined for the break-even identity and have a proven no-gap property at "
                "h < delta/2; lane-06 delta_m1 is TBD"},
        {"dimension": "interval and multiplicity",
         "lane25": "Bonferroni simultaneous Student-t at Welch-Satterthwaite dof (GUM G.4), Type B components "
                   "explicit",
         "lane06": "t-interval on replicate-level paired log-ratios, bootstrap cross-check, Holm step-down",
         "proposed_single_basis": "lane-25 intervals (classification needs simultaneous intervals, which Holm does "
                                  "not give directly); lane-06 bootstrap kept as a cross-check",
         "why": "the installation term and the Type B scale terms do not appear in a paired replicate t-interval"},
        {"dimension": "replication",
         "lane25": "blocks (even n between T-N-MIN and T-N-MAX, fixed by readiness_n at LOCK-2); S1b re-mount "
                   "series",
         "lane06": "replicates_min per (arm, point), each separated by shutdown and restart",
         "proposed_single_basis": "lane-25 blocks, with the lane-06 definition that consecutive visits of a point "
                                  "are separated by a shutdown and restart",
         "why": "keeps drift cancellation over block pairs and makes each block an independent start"},
        {"dimension": "hardware configuration",
         "lane25": "HW-0 / HW-RF / HW-ECR (+ OPTION-DIVERTER)", "lane06": "CFG-A integrated (preferred) / CFG-B "
                                                                        "separate builds with shams",
         "proposed_single_basis": "D-06 (PROPOSED D-06-A); lane-06 sham = lane-25 installed-off state",
         "why": "a CFG-A reference with both applicators installed is not bare hall_only"},
        {"dimension": "extinction / sustainment",
         "lane25": "T-SUSTAIN: no extinction or restart during the dwell (dwell TBD)",
         "lane06": "THR-EXTINCTION: quantitative I_d rule of the same form as P5-N2 rule O1",
         "proposed_single_basis": "lane-06 quantitative extinction rule as the operational definition inside "
                                  "T-SUSTAIN; dwell from S1",
         "why": "one objective definition shared with the simulation rule"},
        {"dimension": "propellant ordering",
         "lane25": "operating-point order a seeded permutation per block (OP5 air surrogate included)",
         "lane06": "fixed order Xe -> N2 -> O2/N2 within a day; oxygen points never interleaved",
         "proposed_single_basis": "N2 points randomised; OP5 (oxygen-bearing) last in every block",
         "why": "oxygen may change cathode and wall surfaces irreversibly (lane 06 Sec. 8); the bracketing off "
                "readings still control drift at OP5"},
        {"dimension": "controls",
         "lane25": "installed-off, S6 re-installation check",
         "lane06": "SHAM_RF / SHAM_ECR, DUMMY_LOAD_PICKUP, XE_HEALTH_CHECK",
         "proposed_single_basis": "add DUMMY_LOAD_PICKUP to S1a (no plasma); XE_HEALTH_CHECK as D-15",
         "why": "pickup on common diagnostics would bias R without being visible in the variance model"},
        {"dimension": "facility-effect controls",
         "lane25": "one elevated level (T-PB-ELEV-FACTOR x base), classified facility family",
         "lane06": "pbg_elevated_levels_min elevated levels, regression, FACILITY_SENSITIVE label",
         "proposed_single_basis": "D-12 (PROPOSED one classified level)", "why": "cost computed in D-12"},
        {"dimension": "ignition", "lane25": "not in the minimum",
         "lane06": "M5 with zero-failure decision aid", "proposed_single_basis": "D-13",
         "why": "binding gate criterion G6.ignition and Bundle-1 condition HS-A6"},
        {"dimension": "pre-registration",
         "lane25": "LOCK-1 before S1, LOCK-2 after D0 (S1 values, n)",
         "lane06": "PR-1..PR-6: owner decisions, disclosed Hall-only pilot, freeze, merge, addenda, frozen raw data",
         "proposed_single_basis": "two locks (lane 25) with the lane-06 PR-5 addendum rule and PR-6 coded labels; "
                                  "location D-05",
         "why": "S1 values fix n without discretion; the addendum rule covers later changes"},
    ]
    return {"differences_listed_by_lane25": ptr("minexp_draft", "/related_lanes/0"),
            "mapping_check": mapping_ok, "dimensions": dims,
            "status": REC}


# ------------------------------------------------------------------------------------------------------------------
# (4) facility / hardware requirements
# ------------------------------------------------------------------------------------------------------------------
def requirements(docs, ctx) -> list[dict]:
    n0 = str(ctx.n_min)
    s_eff = {}
    for gas, rows in docs["minexp_draft"]["derived_numbers"]["S_eff_required_per_mgps"].items():
        s_eff[gas] = {p: from_input(docs, "minexp_draft", f"/derived_numbers/S_eff_required_per_mgps/{gas}/{p}")
                      for p in rows}
    R = [
        {"id": "REQ-FAC-01", "requirement": "The facility shall hold base p_b <= T-PB-MAX at every grid flow during "
                                            "Hall-on stages (S1b, S2, S4, S5); the effective pumping speed shall be "
                                            "at least Q/p_b,max for the total (anode + cathode) flow.",
         "values": {"S_eff_per_mg_per_s_planning_scenarios": s_eff},
         "tbd": [TBD("T-PB-MAX", "facility specification and owner decision at LOCK-1", ["owner", "facility data"]),
                 TBD("total grid flow (sets S_eff = Q/p_b)", "IF-A5 feed envelope", ["lane_16_feed_envelope"])],
         "reference": "REF-DANKANICH2017 via lane 25 (p_b scenarios are SPT-100/xenon planning values only)"},
        {"id": "REQ-FAC-02", "requirement": "The facility shall be able to raise p_b to T-PB-ELEV-FACTOR x base by "
                                            "injecting the working gas downstream, with a pumping surface between "
                                            "injection and gauge.",
         "values": {"T-PB-ELEV-FACTOR": N(2, "x base p_b", "assumed", ptr("minexp_draft", "/thresholds (id "
                                                                                          "T-PB-ELEV-FACTOR)")),
                    "injection_distance_min": l06(docs, "pbg_injection_distance_min")},
         "tbd": [], "reference": "REF-DANKANICH2017 Sec. IV.B via lanes 25 and 06"},
        {"id": "REQ-FAC-03", "requirement": "Background-pressure gauges shall be placed and operated per the "
                                            "recommended practice and calibrated on the working gases.",
         "values": {k: l06(docs, k) for k in ["gauge_offset_chamber_radii_min", "gauge_distance_thruster_min",
                                 "pressure_sampling_min", "pressure_average_window", "pressure_settle_min",
                                 "gauge_calibration_interval", "pressure_asym_max"]},
         "tbd": [TBD("gas correction for O2/N2 mixtures", "gauge calibration on each mixture", ["facility data"])],
         "reference": "REF-DANKANICH2017 Secs. III, IV.A via lane 06 (values in protocol_draft.json)"},
        {"id": "REQ-FAC-04", "requirement": "The facility shall be compatible with O2 flow (pumps, safety case) for "
                                            "the air-surrogate point.",
         "values": {}, "tbd": [TBD("O2 compatibility", "facility data", ["facility data"])],
         "reference": "lane 25 Sec. 8"},
        {"id": "REQ-FAC-05", "requirement": "S1b, S2, S4 and S5 shall use one facility, stand and mount procedure "
                                            "(S1b measures that facility's installation reproducibility).",
         "values": {}, "tbd": [], "reference": "lane 25 Sec. 12"},
        {"id": "REQ-HW-01", "requirement": "The thrust stand shall have end-to-end in-situ calibration under vacuum "
                                           "and a per-reading repeatability no worse than u_T,max at the n fixed at "
                                           "LOCK-2.",
         "values": {"u_T_max_at_n_min": from_input(docs, "minexp_draft", f"/derived_numbers/plan_by_n/{n0}/u_T_max"),
                    "calibrations_before_min": l06(docs, "thrust_cal_before_min"),
                    "calibrations_after_min": l06(docs, "thrust_cal_after_min")},
         "tbd": [TBD("thrust range", "Hall design", ["DI-2 Vyovrinda Hall design point"])],
         "reference": "REF-POLK2017 via lanes 25 and 06 (>= 10 calibrations before and after: lane-06 "
                      "thrust_cal_before_min / thrust_cal_after_min)"},
        {"id": "REQ-HW-02", "requirement": "Load-plane DC power shall be measured simultaneously on every present DC "
                                           "consumer with per-reading repeatability no worse than u_P,max; each "
                                           "DC-fed lab generator's DC input shall also be metered.",
         "values": {"u_P_max_at_n_min": from_input(docs, "minexp_draft", f"/derived_numbers/plan_by_n/{n0}/u_P_max"),
                    "ledger_residual_max": l06(docs, "ledger_residual_max")},
         "tbd": [TBD("traceable calibration class", "owner", ["owner"])], "reference": "lane 25 M2; lane 06 DIAG-BUS"},
        {"id": "REQ-HW-03", "requirement": "Net RF / microwave power shall be measured at the source load plane "
                                           "(forward minus reflected) or reconstructed from an S1a-characterised "
                                           "loss, with a scale uncertainty no worse than u_src,max(f_src).",
         "values": {f"u_src_max_at_f_src_{f}": from_input(docs, "minexp_draft",
                                                          f"/derived_numbers/u_source_scale_max_by_f_src/{f}")
                    for f in docs["minexp_draft"]["derived_numbers"]["u_source_scale_max_by_f_src"]},
         "tbd": [TBD("f_src allocation", "bus_power_boundary_v1 source allocation at LOCK-1", ["owner",
                                                                                               "lane_11_bus_boundary"]),
                 TBD("load-plane characterisation method", "RF / microwave design", ["RF and ECR source designs"])],
         "reference": "lane 25 M3 (f_src values are hypothetical planning values)"},
        {"id": "REQ-HW-04", "requirement": "The installation (re-mount) reproducibility of ln(T/P_bus) shall be no "
                                           "worse than u_inst,max, or a no-vent arm switch shall be used (D-06).",
         "values": {"u_inst_max_at_n_min": from_input(docs, "minexp_draft",
                                                      f"/derived_numbers/plan_by_n/{n0}/u_inst_max")},
         "tbd": [TBD("achievability", "S1b re-mount series", ["S1b measurement"])], "reference": "lane 25 Sec. 6.4"},
        {"id": "REQ-HW-05", "requirement": "Ion current shall be measured at the source exit (guarded Faraday "
                                           "collector/array) and across the Hall channel exit with the Hall discharge "
                                           "off, with the recommended-practice corrections.",
         "values": {}, "tbd": [TBD("CEX attenuation bound on the collector path",
                                   "cited N2+ on N2 charge-exchange cross section", ["literature (cited source)"])],
         "reference": "REF-BROWN2017 via lane 25 M5"},
        {"id": "REQ-HW-06", "requirement": "B(z) shall be mapped with a Hall probe on a positioning stage for every "
                                           "configuration at the operating coil currents, before and after.",
         "values": {}, "tbd": [TBD("range", "Hall design", ["DI-2 Vyovrinda Hall design point"])],
         "reference": "lane 25 M11"},
        {"id": "REQ-HW-07", "requirement": "Mass-flow controllers shall be calibrated on N2, O2 and Xe in the final "
                                           "configuration; identical setpoints across arms.",
         "values": {"mfc_calibration_interval": l06(docs, "mfc_calibration_interval")}, "tbd": [], "reference": "REF-SNYDER2017 via lanes 25 and 06"},
        {"id": "REQ-HW-08", "requirement": "Hardware set: Hall unit H-1 (D-09), cathode C-1, RF source + interstage + "
                                           "DC-fed generator + matching, ECR source + interstage + DC-fed microwave "
                                           "generator + isolator + coupler + ECR magnet, flow-equivalent spacer "
                                           "(HW-0) or diverter (D-06), matched dummy loads.",
         "values": {}, "tbd": [TBD("cathode type", "cathode lanes", ["lane_10_cathode_dossier",
                                                                     "lane_19_cathode_integration"]),
                               TBD("source frequencies and powers P_hi", "RF / ECR designs and bus allocation",
                                   ["owner", "lane_11_bus_boundary"])],
         "reference": "lane 25 Sec. 11"},
    ]
    return R


# ------------------------------------------------------------------------------------------------------------------
# (5) milestones
# ------------------------------------------------------------------------------------------------------------------
def milestones(docs) -> dict:
    return {
        "supports": ["A"],
        "A": {"unlocks": [
            "LOCK-1 can be written once the owner decides D-01..D-15 (this package is the decision record)",
            "S1 (qualification) can start; D0 then decides from measured S1 values whether delta is reachable",
            "the measurements in the traceability matrix can move overlay placements from STRADDLES to "
            "CLEARLY_ABOVE_BREAKEVEN or CLEARLY_BELOW at the tested hardware point (thresholds carried per entry)",
            "Bundle-1 conditions RF C1/C2/C4, ECR (A)/(B) and HS-A2 become checkable on measured data (partial where "
            "the matrix says so)"],
            "does_not": ["name a baseline or set any architecture aside",
                         "eliminate through lane 24 (outcome templates: point_design scope, n2_surrogate feed)"]},
        "to_reach_B": [
            "an admitted Hall transport closure (credible set empty, gate 3 FAIL) to carry the tested-point C*, y and "
            "kappa to the Vyovrinda design envelope",
            "O / O2 chemistry and an atomic-O-bearing feed (the bottled surrogate has none)",
            "the valve-outlet feed state (lane 16 design inputs) and the ICD compressor draw (lane 33) for the V1 "
            "boundary",
            "the physics-track pre-registration (D-14) if the data are to count as closure evidence",
            "second-lens verification of any single-lens-v1 lane used as decisive evidence"],
        "to_reach_C": ["mass, thermal, life, startup, cathode and mission closure on one integrated design; "
                       "flight-representative PPU and source chains (M-MWCHAIN); endurance on an O-bearing feed "
                       "(DM-6)"],
    }


# ------------------------------------------------------------------------------------------------------------------
# assembly, schema, rendering
# ------------------------------------------------------------------------------------------------------------------
def collect_tbd(obj, path="$", out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        if obj.get("value") == "TBD" and "requires" in obj:
            out.append({"path": path, "what": obj["what"], "requires": obj["requires"], "blocked_by": obj["blocked_by"]})
        for k, v in obj.items():
            collect_tbd(v, f"{path}.{k}", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            collect_tbd(v, f"{path}[{i}]", out)
    return out


def build(root: Path = ROOT) -> dict:
    paths = verify_inputs(root)
    docs = {k: load_json(p) for k, p in paths.items() if p.suffix == ".json"}
    mx = load_minexp(paths["minexp_tools"])
    ctx = MinexpContext(mx, mx.load_draft(paths["minexp_draft"]))
    hg = load_hard_gates()
    ab = load_arch_boundary()
    matrix = hg.load_matrix()
    pkg = {
        "schema": "abep_experiment_package_v1",
        "id": "fo_experiment_package_v1",
        "follow_on": "fo_experiment_package",
        "trigger": "T_EXPERIMENT_PACKAGE",
        "prerequisite": "lane_25_min_decisive_experiment",
        "status": STATUS,
        "base_commit": BASE_COMMIT,
        "generated_by": SCRIPT_REF,
        "not_locked": ("Nothing in this package is pre-registered, locked or decided. Every recommendation is "
                       "PROPOSED for the owner; thresholds not in the RFP are PROPOSED. No score-bearing run may take "
                       "place before the owner's LOCK-1 and LOCK-2 (lane 25 Sec. 10)."),
        "compliance": [
            "no absolute Hall performance from any closure (credible set empty; gate 3 FAIL); no screening candidate "
            "as a performance source; no retuning",
            "valve-outlet feed state (lane 16) and compressor bus draw (lane 33) are TBD, never filled",
            "no architecture named as preferred; eliminations only through lane 24's evaluator (none results)",
            "P5 calibration nuisance is never an axis; Hall-closure uncertainty does not reach upstream elements",
            "every number carries a unit, evidence class and source (input pointer or computation), else TBD with "
            "its blocking lane or measurement"],
        "inputs": [{"key": k, "path": v[0], "lane": v[1], "sha256": v[2]} for k, v in INPUTS.items()],
        "milestones": milestones(docs),
        "decisions": decisions(ctx, docs),
        "traceability": traceability(docs, hg, matrix),
        "hard_gate_context": {"current_status": current_gate_status(docs),
                              "outcome_templates": outcome_templates(hg, matrix)},
        "reconciliation": reconciliation(docs, ab),
        "requirements": requirements(docs, ctx),
    }
    pkg["tbd_register"] = collect_tbd(pkg)
    validate(pkg)
    return pkg


def validate(pkg: dict) -> None:
    hg = load_hard_gates()
    schema = load_json(SCHEMA_JSON)
    hg.check_schema_keywords(schema)
    errs = hg.schema_errors(pkg, schema, schema)
    if errs:
        raise ValueError("experiment package does not validate against its schema:\n  " + "\n  ".join(errs[:20]))
    bad = numeric_leaf_errors(pkg)
    if bad:
        raise ValueError("numbers without unit / evidence class / source:\n  " + "\n  ".join(bad[:20]))
    text = json.dumps(pkg, ensure_ascii=False)
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text):
            raise ValueError(f"forbidden pattern {pat!r} in the package")
    for d in pkg["decisions"]:
        if d["status"] != "OPEN_OWNER_DECISION" or d["recommendation"]["status"] != REC:
            raise ValueError(f"{d['id']}: decisions stay open and recommendations PROPOSED")


def numeric_leaf_errors(obj, path="$", parent=None, key=None) -> list[str]:
    """Every int/float (not bool) must be the 'value' of an object carrying unit, evidence_class and source."""
    errs = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            errs += numeric_leaf_errors(v, f"{path}.{k}", obj, k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errs += numeric_leaf_errors(v, f"{path}[{i}]", obj, None)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        ok = (key == "value" and isinstance(parent, dict)
              and all(parent.get(f) for f in ("unit", "evidence_class", "source")))
        if not ok:
            errs.append(path)
    return errs


def dumps(pkg: dict) -> str:
    return json.dumps(pkg, indent=1, ensure_ascii=False) + "\n"


# ---- markdown ----------------------------------------------------------------------------------------------------
def fmt(x) -> str:
    if isinstance(x, dict) and "value" in x:
        v = x["value"]
        if v == "TBD":
            return f"TBD ({x.get('requires', '')})"
        if isinstance(v, float):
            s = f"{v:.6g}"
        else:
            s = str(v)
        u = x.get("unit", "")
        return f"{s} {u}".strip() if u and u not in ("-",) else s
    return str(x)


def md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_md(pkg: dict) -> str:
    L = []
    L += ["# Experimental decision package: minimum decisive experiment (DRAFT for owner review)", "",
          f"**Status: {pkg['status']}.** Follow-on `{pkg['follow_on']}` (trigger `{pkg['trigger']}`, prerequisite "
          f"`{pkg['prerequisite']}`), base commit `{pkg['base_commit'][:10]}`. {pkg['not_locked']}", "",
          f"Generated by `{pkg['generated_by']}` from `experiment_package_v1.json` (schema "
          "`experiment_package_v1.schema.json`); `--check` reproduces both files byte for byte. The JSON is "
          "authoritative. Every number below carries its source and evidence class in the JSON.", "",
          "## 0. What this package is", "",
          "It turns the lane-25 draft (`docs/architecture_comparison/minimum_decisive_experiment/`) into the list of "
          "decisions the owner must lock before any score-bearing run, with the consequences of each option computed "
          "by the lane-25 tools; a traceability matrix from each measurement to the break-even placements, Bundle-1 "
          "(milestone-A) conditions, hard-gate criteria and failure-tree nodes it resolves; a reconciliation with the "
          "lane-06 protocol; facility and hardware requirements; and what it unlocks for milestone A -> B.", ""]
    L += ["Compliance:", ""] + [f"- {c}" for c in pkg["compliance"]] + [""]
    # milestones
    m = pkg["milestones"]
    L += ["## 1. Milestones", "", f"Supports milestone **{', '.join(m['supports'])}** (conditional selection).", "",
          "Unlocks for A:", ""] + [f"- {x}" for x in m["A"]["unlocks"]] + ["", "Does not:", ""] + \
         [f"- {x}" for x in m["A"]["does_not"]] + ["", "To reach B:", ""] + [f"- {x}" for x in m["to_reach_B"]] + \
         ["", "To reach C:", ""] + [f"- {x}" for x in m["to_reach_C"]] + [""]
    # decisions
    L += ["## 2. Decisions to lock before any score-bearing run (all open; recommendations PROPOSED)", "",
          "| id | decision | options | PROPOSED | source |", "|---|---|---|---|---|"]
    for d in pkg["decisions"]:
        opts = "; ".join(f"{o['id']}: {o['label']}" for o in d["options"])
        src = d["source"]
        s = []
        if src.get("lane_25_open_decision"):
            s.append("lane 25 open decision " + ",".join(str(int(x.rsplit("/", 1)[1]) + 1)
                                                          for x in src["lane_25_open_decision"]))
        if src.get("lane_06_item"):
            s.append("lane 06 " + src["lane_06_item"])
        L.append(f"| {d['id']} | {md_cell(d['title'])} | {md_cell(opts)} | {d['recommendation']['option']} | "
                 f"{md_cell('; '.join(s))} |")
    L.append("")
    for d in pkg["decisions"]:
        L += [f"### {d['id']}. {d['title']}", ""]
        if d.get("structural_finding"):
            L += [f"*Finding.* {d['structural_finding']}", ""]
        L += _render_decision_details(d)
        L += [f"*PROPOSED:* {d['recommendation']['option']}. {d['recommendation']['rationale']}", ""]
        if d.get("cost_note"):
            L += [f"*Cost.* {d['cost_note']}", ""]
    # hard gates
    hgc = pkg["hard_gate_context"]
    cs = hgc["current_status"]
    L += ["## 3. Hard gates: what the experiment can and cannot decide", "",
          f"Current lane-24 status (`{cs['source']}`): eliminated {cs['eliminated']}, not eliminated "
          f"{cs['not_eliminated']}, admitted members {cs['admitted_members']}, registered evidence items "
          f"{fmt(cs['register_items'])}.", "",
          f"Outcome templates run through {hgc['outcome_templates']['evaluator']} (SYNTHETIC, never registered):", "",
          "| template | architecture | criterion verdict | gate verdict | eliminated | design failures |",
          "|---|---|---|---|---|---|"]
    for t in hgc["outcome_templates"]["templates"]:
        L.append(f"| {t['template']} | {t['architecture']} | {t['criterion_verdict']} | {t['gate_verdict']} | "
                 f"{t['evaluator_eliminated']} | {md_cell(', '.join(t['design_failures']) or '-')} |")
    L += ["", hgc["outcome_templates"]["reading"], ""]
    # traceability
    tr = pkg["traceability"]
    L += ["## 4. Traceability: measurement -> what it resolves", "",
          "| id | lane-25 measurement | what | Bundle-1 conditions | hard-gate criteria (can pass / can eliminate) "
          "| failure-tree nodes (effect in tree) |", "|---|---|---|---|---|---|"]
    for r in tr["rows"]:
        meas = ", ".join(r["measurement"]["lane25"] + r["measurement"]["quantities"]
                         + r["measurement"].get("derived", []) + r["measurement"].get("gates", []))
        b1 = "; ".join(f"{c['condition']} ({c['coverage']})" for c in r["bundle1_conditions"]) or "-"
        hgs = "; ".join(f"{h['criterion']} ({h['can_pass_from_minimum_experiment']}/"
                        f"{h['can_eliminate_from_minimum_experiment']})" for h in r["hard_gates"]) or "-"
        fts = "; ".join(f"{f['node']} ({f['effect_in_tree']})" for f in r["failure_tree"]) or "-"
        L.append(f"| {r['id']} | {md_cell(meas)} | {md_cell(r['what'])} | {md_cell(b1)} | {md_cell(hgs)} | "
                 f"{md_cell(fts)} |")
    L += ["", f"Failure-tree nodes naming M-PREION: {', '.join(tr['failure_tree_nodes_naming_M_PREION'])}; "
              f"not traced here: {', '.join(tr['M_PREION_nodes_not_traced']) or 'none'}.", ""]
    L += ["### 4.1 Break-even placement thresholds carried by the measurements", "",
          "RF (`overlay_rf_v1`), end-to-end delivered-ion bus cost C_del:", ""]
    rf = tr["rows"][0]["breakeven_placement"]["rf_hall"]["common"]
    L += [f"- above {fmt(rf['C_del_above_which_CLEARLY_ABOVE'])}: CLEARLY_ABOVE_BREAKEVEN",
          f"- at or below {fmt(rf['C_del_at_or_below_which_CLEARLY_BELOW_add_only'])} (add_only, small delivered "
          "shares): CLEARLY_BELOW; in between, milestone B decides", "",
          "| RF unit | placement | eta_t below which CLEARLY_ABOVE |", "|---|---|---|"]
    for u in tr["rows"][1]["breakeven_placement"]["rf_hall"]["per_unit"]:
        L.append(f"| {u['unit_id']} | {u['placement']} | {fmt(u['eta_t_below_which_CLEARLY_ABOVE'])} |")
    L += ["", "| ECR entry | mode | placement | eta_t below which CLEARLY_ABOVE | C_del,bus above -> ABOVE | "
              "C_del,bus at or below -> BELOW (add_only) |", "|---|---|---|---|---|---|"]
    for e in tr["rows"][0]["breakeven_placement"]["ecr_hall"]["per_entry"]:
        L.append(f"| {e['entry']} | {e['mode']} | {e['placement']} | {fmt(e['eta_t_below_which_CLEARLY_ABOVE'])} | "
                 f"{fmt(e['C_del_bus_above_which_CLEARLY_ABOVE'])} | "
                 f"{fmt(e['C_del_bus_at_or_below_which_CLEARLY_BELOW_add_only'])} |")
    L += ["", "Limits per row are in the JSON (`traceability.rows[].limits`).", ""]
    # reconciliation
    rc = pkg["reconciliation"]
    L += ["## 5. Reconciliation of lane 25 with lane 06 and PROPOSED single protocol basis", "",
          f"Both component mappings cover `{rc['mapping_check']['contract_version']}` exactly once: lane 06 "
          f"{rc['mapping_check']['lane06_covers_contract_exactly_once']}, lane 25 "
          f"{rc['mapping_check']['lane25_covers_contract_exactly_once']}.", "",
          "| dimension | lane 25 | lane 06 | PROPOSED single basis | why |", "|---|---|---|---|---|"]
    for dmn in rc["dimensions"]:
        L.append(f"| {md_cell(dmn['dimension'])} | {md_cell(dmn['lane25'])} | {md_cell(dmn['lane06'])} | "
                 f"{md_cell(dmn['proposed_single_basis'])} | {md_cell(dmn['why'])} |")
    L.append("")
    # requirements
    L += ["## 6. Facility and hardware requirements (no facility is named; published descriptions are references "
          "only)", "", "| id | requirement | values | TBD |", "|---|---|---|---|"]
    for q in pkg["requirements"]:
        vals = _flat_values(q["values"])
        tbd = "; ".join(f"{t['what']} ({t['requires']})" for t in q["tbd"]) or "-"
        L.append(f"| {q['id']} | {md_cell(q['requirement'])} | {md_cell(vals or '-')} | {md_cell(tbd)} |")
    L.append("")
    # TBD register
    L += ["## 7. TBD register", "", "| what | requires | blocked by |", "|---|---|---|"]
    seen = set()
    for t in pkg["tbd_register"]:
        key = (t["what"], t["requires"])
        if key in seen:
            continue
        seen.add(key)
        L.append(f"| {md_cell(t['what'])} | {md_cell(t['requires'])} | {md_cell(', '.join(t['blocked_by']))} |")
    L.append("")
    # inputs
    L += ["## 8. Pinned inputs", "", "| path | lane | sha256 |", "|---|---|---|"]
    for i in pkg["inputs"]:
        L.append(f"| `{i['path']}` | {md_cell(i['lane'])} | `{i['sha256'][:16]}` |")
    L.append("")
    return "\n".join(L)


def _flat_values(v, prefix="") -> str:
    parts = []
    if isinstance(v, dict) and "value" in v and "unit" in v:
        return f"{prefix}{fmt(v)}"
    if isinstance(v, dict):
        for k, x in v.items():
            s = _flat_values(x, f"{k}: " if not prefix else f"{prefix}{k}: ")
            if s:
                parts.append(s)
    return "; ".join(parts)


def _render_decision_details(d: dict) -> list[str]:
    L = []
    for t in d.get("tbd", []):
        L.append(f"- TBD: {t['what']} (requires {t['requires']}; blocked by {', '.join(t['blocked_by'])})")
    if d["id"] in ("D-01",):
        L += ["", "| option | n | nu_eff | k | sigma_max(ln R) | u_T max | u_P max | u_inst max |",
              "|---|---|---|---|---|---|---|---|"]
        for o in d["options"]:
            st = o["consequences"]["statistics_and_targets"]
            for n, row in st.items():
                if n == "n_required_by_u_reading":
                    continue
                L.append(f"| {o['id']} | {n} | {fmt(row['nu_eff'])} | {fmt(row['k_primary'])} | "
                         f"{fmt(row['sigma_lnR_max'])} | {fmt(row['u_T_max'])} | {fmt(row['u_P_max'])} | "
                         f"{md_cell(fmt(row['u_inst_max']))} |")
        keys = list(d["options"][0]["consequences"]["statistics_and_targets"]["n_required_by_u_reading"])
        L += ["", f"| option | blocks needed at per-reading u = {' / '.join(keys)} (lane-25 planning grid) |",
              "|---|---|"]
        for o in d["options"]:
            nr = o["consequences"]["statistics_and_targets"]["n_required_by_u_reading"]
            L.append(f"| {o['id']} | {' / '.join(fmt(v) for v in nr.values())} |")
        L.append("")
        return L
    if d["id"] == "D-02":
        for o in d["options"]:
            s = o["consequences"]["statistics"][0]
            L.append(f"- {o['id']} ({o['label']}): {s['what']}: R < {fmt(s['R_threshold'])}; "
                     f"{o['consequences']['meaning']}")
        for g in d["grid_comparison"]:
            L.append(f"- grid at h = {fmt(g['h'])}: sign form supports a stop at {fmt(g['sign_form_stop_supporting'])},"
                     f" STOP-MARGIN at {fmt(g['stop_margin_stop_supporting'])} of {fmt(g['grid_points'])}; "
                     f"STOP-MARGIN subset of sign form: {g['stop_margin_subset_of_sign_form']}")
        L.append("")
        return L
    for o in d["options"]:
        L.append(f"- **{o['id']}** {o['label']}: {md_cell(_flat_consequences(o.get('consequences', {})))}")
    L.append("")
    return L


def _flat_consequences(c) -> str:
    if isinstance(c, dict) and "value" in c and ("unit" in c or c.get("value") == "TBD"):
        return fmt(c)
    if isinstance(c, dict):
        return "; ".join(f"{k}: {_flat_consequences(v)}" for k, v in c.items())
    if isinstance(c, list):
        return "; ".join(_flat_consequences(x) for x in c)
    return str(c)


# ------------------------------------------------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    pkg = build()
    js, md = dumps(pkg), render_md(pkg)
    if "--check" in argv:
        bad = []
        for path, text in ((OUT_JSON, js), (OUT_MD, md)):
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                bad.append(str(path.relative_to(ROOT)))
        if bad:
            print("NOT REPRODUCED: " + ", ".join(bad), file=sys.stderr)
            return 1
        print("OK: experiment package reproduces byte for byte")
        return 0
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
