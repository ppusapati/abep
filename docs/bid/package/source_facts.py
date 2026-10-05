"""Facts read from the bid TECHNICAL SOURCE commit (never from the working tree).

Every value returned here is read with `git show <TECHNICAL_SOURCE_SHA>:<path>`; nothing is hand-typed. The technical source
SHA is the single constant `bid_technical_source.commit` in docs/bid/bid_technical_baseline_v2.json (read by
compliance_data.TECHNICAL_SOURCE_SHA). Readers fail closed (SourceFactError) when a record does not have the structure
they need: switching the technical source never silently drops a fact.

Mass: the mass record is the current mass_power successor present at the source (MASS_RECORD_CANDIDATES in order: v5 when
present, else v4). Its numbers are read from the record's hall_icp_neutralizer roll-up and cross-checked arithmetically.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

REG = "docs/requirements/rfp_official/rfp_registration_v1.json"
RVM = "docs/requirements/rvm_a9/rvm_a9_v1.json"
F9 = "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
F78 = "docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json"
HWP = "docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json"
CONSTRAINTS = "config/constraints/engineering_constraints_v1.json"
SCENARIO = "config/mission/mission_scenario_v2.json"
A924_JSON = "docs/decisions/OD_2026_10_04_A9_24_rust_migration_and_open_items_owner_decisions.json"
A925_JSON = "docs/decisions/OD_2026_10_04_A9_25_pre_bid_owner_decisions.json"
A925_MD = "docs/decisions/OD_2026_10_04_A9_25_PRE_BID_OWNER_DECISIONS.md"
A926_JSON = "docs/decisions/OD_2026_10_05_A9_26_mass_budget_owner_decisions.json"
A926_MD = "docs/decisions/OD_2026_10_05_A9_26_MASS_BUDGET_OWNER_DECISIONS.md"
# current mass_power successor first; the first one present at the technical source is the mass record
MASS_RECORD_CANDIDATES = ["docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json",
                          "docs/budgets/mass_power_a9_v4/mass_power_a9_v4.json"]
CONFIG = "hall_icp_neutralizer"
HARD_REF = "HARD_40_WET"
TOL = 1e-6


class SourceFactError(RuntimeError):
    pass


class Source:
    """Read-only view of one commit."""

    def __init__(self, sha: str):
        self.sha = sha
        self._cache: dict[str, str | None] = {}

    def text(self, path: str) -> str | None:
        if path not in self._cache:
            r = subprocess.run(["git", "show", f"{self.sha}:{path}"], cwd=ROOT, capture_output=True, text=True)
            self._cache[path] = r.stdout if r.returncode == 0 else None
        return self._cache[path]

    def exists(self, path: str) -> bool:
        return self.text(path) is not None

    def json(self, path: str) -> dict:
        t = self.text(path)
        if t is None:
            raise SourceFactError(f"{path} is not present at the technical source {self.sha[:7]}")
        return json.loads(t)

    def commit_exists(self) -> bool:
        return subprocess.run(["git", "cat-file", "-e", self.sha + "^{commit}"], cwd=ROOT,
                              capture_output=True).returncode == 0


def resolve(doc, pointer: str):
    """JSON pointer with `[key=value]` list selection (the convention of the evidence locators)."""
    cur = doc
    for part in [p for p in pointer.split("/") if p]:
        m = re.match(r"^([\w.-]+)\[([\w-]+)=([^\]]+)\]$", part)
        if m:
            cur = cur[m.group(1)]
            hits = [x for x in cur if isinstance(x, dict) and str(x.get(m.group(2))) == m.group(3)]
            if not hits:
                raise KeyError(f"no element {m.group(2)}={m.group(3)}")
            cur = hits[0]
        else:
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def _num(d: dict, *keys):
    for k in keys:
        if isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool):
            return float(d[k]), k
    raise SourceFactError(f"mass roll-up has none of {keys}")


def _re1(rx: str, text: str, what: str) -> str:
    m = re.search(rx, text)
    if not m:
        raise SourceFactError(f"cannot read {what} from: {text[:200]}")
    return m.group(1)


# ------------------------------------------------------------------------------------------------ mass
def mass_record_path(src: Source) -> str:
    for p in MASS_RECORD_CANDIDATES:
        if src.exists(p):
            return p
    raise SourceFactError(f"no mass_power record {MASS_RECORD_CANDIDATES} at {src.sha[:7]}")


def mass_facts(src: Source) -> dict:
    path = mass_record_path(src)
    rec = src.json(path)
    rolls = [r for r in rec.get("rollups", []) if r.get("configuration") == CONFIG]
    active = [r for r in rolls if not re.search(r"HISTORICAL|SENSITIVITY",
                                                 " ".join(str(r.get(k, "")) for k in ("reading", "label", "role", "status")),
                                                 re.IGNORECASE)]
    if len(active) != 1:
        raise SourceFactError(f"{path}: expected exactly one active {CONFIG} roll-up, found {len(active)} "
                              f"(readings {[r.get('reading') for r in rolls]})")
    r = active[0]
    nonharness, _ = _num(r, "nonharness_known_kg", "nonharness_kg")
    harness, _ = _num(r, "harness_kg")
    nominal, _ = _num(r, "nominal_dry_known_kg", "nominal_dry_kg")
    margin, _ = _num(r, "system_margin_kg")
    dry, dry_key = _num(r, "dry_known_kg", "dry_kg", "dry_planning_kg")
    if abs(nonharness + harness - nominal) > TOL or abs(nominal + margin - dry) > TOL:
        raise SourceFactError(f"{path}: roll-up arithmetic does not close ({nonharness}+{harness}={nominal}; "
                              f"{nominal}+{margin}={dry})")
    frac = margin / nominal
    pct = round(frac * 100, 6)
    if abs(pct - round(pct)) > 1e-6:
        raise SourceFactError(f"{path}: system margin {pct} % is not a whole percent")
    wet = []
    for w in r.get("wet", []):
        if w.get("reference") != HARD_REF:
            continue
        xe, _ = _num(w, "xe_case_kg", "xe_loaded_kg")
        wk, _ = _num(w, "wet_known_kg", "wet_kg")
        on_top = float(w.get("residual_added_on_top_kg") or 0.0)
        if abs(dry + xe + on_top - wk) > TOL:
            raise SourceFactError(f"{path}: wet {wk} != dry {dry} + Xe {xe} + {on_top}")
        ref = float(w["reference_kg"])
        wet.append({"xe_case_kg": xe, "wet_kg": wk, "reference": HARD_REF, "reference_kg": ref,
                    "comparator": w.get("comparator"), "state": w["state"],
                    "exceedance_kg": float(w["exceedance_kg"]) if w.get("exceedance_kg") is not None else wk - ref})
    if not wet:
        raise SourceFactError(f"{path}: no {HARD_REF} wet entries in the {CONFIG} roll-up")
    wet.sort(key=lambda x: x["xe_case_kg"])
    lines = rec["lines"][CONFIG]
    line_rows = []
    for ln in lines:
        v = ln.get("value") or {}
        line_rows.append({"line": ln["line"], "name": ln["name"], "value_kg": v.get("value_kg"),
                          "governs": v.get("governs"), "evidence_class": ln.get("evidence_class_of_value"),
                          "cbe_kg": ln.get("cbe_kg"), "measured_kg": ln.get("measured_kg"),
                          "evidence_floor_kg": ln.get("evidence_floor_cbe_kg")})
    parts = {p["line"]: p.get("kg") for p in r.get("parts", [])}
    if "AL-HAR" in parts and parts["AL-HAR"] is not None and abs(parts["AL-HAR"] - harness) > TOL:
        raise SourceFactError(f"{path}: harness part {parts['AL-HAR']} != harness_kg {harness}")
    fr = [x for x in rec.get("flight_rollup_vs_40kg", []) if x.get("configuration") == CONFIG]
    if fr:
        fdry, _ = _num(fr[0], "dry_known_kg", "dry_kg", "dry_planning_kg")
        if abs(fdry - dry) > TOL:
            raise SourceFactError(f"{path}: flight_rollup_vs_40kg dry {fdry} != roll-up dry {dry}")
    return {
        "path": path,
        "id": rec.get("id"),
        "status": rec.get("status"),
        "rollup_locator": f"#/rollups[configuration={CONFIG}]",
        "reading": r.get("reading"),
        "nonharness_kg": nonharness, "harness_kg": harness, "nominal_dry_kg": nominal,
        "system_margin_kg": margin, "system_margin_fraction": round(frac, 6), "system_margin_pct": int(round(pct)),
        "dry_kg": dry, "dry_key": dry_key,
        "wet": wet,
        "lines_without_value": list(r.get("lines_without_value") or []),
        "all_terms_resolved": r.get("all_terms_resolved"),
        "lines": line_rows,
        "n_lines_with_cbe": sum(1 for x in line_rows if x["cbe_kg"] is not None),
        "n_lines_with_measured": sum(1 for x in line_rows if x["measured_kg"] is not None),
        "mass_status": rec.get("mass_status"),
        "margin_convention_system_margin": (rec.get("margin_convention") or {}).get("system_margin"),
    }


# ------------------------------------------------------------------------------------------------ everything else
def facts(sha: str) -> dict:
    src = Source(sha)
    if not src.commit_exists():
        raise SourceFactError(f"technical source commit {sha} is not in this clone")
    F: dict = {"sha": sha, "short": sha[:7]}

    reg = src.json(REG)
    pc = reg["page_coverage"]
    F["pages_not_screened"] = pc.get("pages_not_screened_as_registered", pc.get("pages_not_screened"))
    if not F["pages_not_screened"]:
        raise SourceFactError("registration page_coverage has no not-screened statement")
    opr = pc.get("owner_page_review") or {}
    F["page_review_status"] = opr.get("status")
    F["page_review_statement"] = opr.get("owner_statement_verbatim")
    F["page_review_scope"] = opr.get("scope")

    rvm = src.json(RVM)
    c = rvm["status_counts"][CONFIG]
    F["rvm_counts"] = c
    F["rvm_total"] = sum(c.values())
    clause_rows = [r for r in rvm["rows"] if (r.get("rfp_rebase") or {}).get("origin") == "RFP_CLAUSE"]
    F["rvm_rfp_clause_rows"] = len(clause_rows)
    F["rvm_rfp_clause_rows_frozen"] = sum(1 for r in clause_rows if r.get("requirement_frozen"))
    rows = {r["id"]: r for r in rvm["rows"]}
    F["rvm_status"] = {k: r["configurations"][CONFIG]["status"] for k, r in rows.items()}
    kr = rows["RVM-16"]["a9_24_current_architecture_reading"]["keeper_reading"]
    F["rvm16_reading_status"] = kr["status"]

    f9 = src.json(F9)
    F["architecture_status"] = f9["architecture_status"]
    F["frozen_reference_flight_architecture"] = f9["frozen_reference_flight_architecture"]
    gates = [{"id": g["id"], "gate": g["gate"], "status": g["current_status"],
              "sufficient": g["evidence_sufficient_for_freeze"], "criteria": g.get("criteria"),
              "locator": f"#/{grp}[id={g['id']}]"}
             for grp in ("architecture_gates", "pre_lock1_gates") for g in f9[grp]]
    F["gates"] = gates
    F["gate_status"] = {g["id"]: g["status"] for g in gates}
    F["gates_sufficient"] = [g["id"] for g in gates if g["sufficient"]]
    fa = f9["configuration"]["flight_architecture"]
    F["flight_configuration"] = fa["configuration"]
    F["conventional_hollow_cathode"] = fa["conventional_hollow_cathode"]
    F["supply_modes"] = [m["mode"] for m in fa["supply_modes"]]
    F["separate_tanks"] = fa["separate_tanks"]
    F["icp_feed_primary"] = fa["icp_feed_gas_baseline"]["primary"]
    F["icp_feed_variant"] = fa["icp_feed_gas_baseline"]["declared_variant"]
    rs = f9["upstream_pareto"]["robust_set"]
    F["robust_set_status"] = rs["status"]
    F["robust_set_members"] = rs["n_members"]
    df = resolve(f9, "design_findings_for_owner[id=F9-DF-01]")
    F["f9_df01_status"] = df["status"]
    F["f9_df01_relaxation_proposed"] = df["requirement_relaxation_proposed"]
    F["flow_gap_order"] = [(o["rank"], o["lever"]) for o in df["flow_gap_owner_order"]["order"]]

    f78 = src.json(F78)
    ds = f78["design_state_set"]
    F["design_state_set_id"] = ds["design_state_set_id"]
    F["design_state_set_path"] = ds["path"]
    F["design_state_set_sha256"] = ds["sha256"]
    F["design_state_n"] = ds["n_required_states"]
    F["design_state_orbit_basis"] = ds["orbit_basis_label"]
    if not src.exists(ds["path"]):
        raise SourceFactError(f"design-state set {ds['path']} missing at the source")
    find = {x["id"]: x["finding"] for x in f78["findings"]}
    F["f7_frontier_mgs"] = float(_re1(r"all-state delivered-flow frontier is ([0-9.eE+-]+) mg/s", find["F78-02"],
                                      "F78-02 frontier"))
    F["f7_members_reaching_038"] = int(_re1(r"0\.38 mg/s.*?at every state: (\d+)", find["F78-02"], "F78-02 count"))
    lo, hi = re.search(r"\[([0-9.]+), ([0-9.]+)\] kg", find["F78-07"]).groups()
    F["f78_07_compressor_kg"] = (float(lo), float(hi))

    hwp = src.json(HWP)
    F["hw_steps"] = [{"id": s["id"], "status": s["entry_status_now"],
                      "predecessors": [(p["step"], p["basis"]) for p in s["predecessors"]]} for s in hwp["steps"]]

    con = src.json(CONSTRAINTS)
    F["constraints_set_status"] = con["set_status"]
    F["constraints_frozen"] = con["constraints_frozen"]
    F["mission_life_h"] = con["constraints"]["mission_life_h"]["value"]
    F["firing_life_h"] = con["constraints"]["firing_life_h"]["value"]
    F["wet_mass_max_kg"] = con["constraints"]["wet_mass_max_kg"]["value"]
    sc = src.json(SCENARIO)
    F["scenario_id"], F["scenario_layer"], F["scenario_status"] = sc["id"], sc["layer"], sc["status"]

    a925 = src.json(A925_JSON)["owner_decision_summary"]
    for k in ("network_builder", "bid_mass_basis", "C1", "AFI-01-S1", "AFI-03", "AFI-05-S1", "two_sha_discipline"):
        F["a925_" + k] = a925[k]
    a924 = src.json(A924_JSON)
    if "9_bid_basis" not in a924["items"]:
        raise SourceFactError("A9.24 item 9_bid_basis missing")
    F["a926_at_source"] = src.exists(A926_JSON) and src.exists(A926_MD)

    F["mass"] = mass_facts(src)
    return F
