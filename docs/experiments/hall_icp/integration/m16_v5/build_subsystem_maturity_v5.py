#!/usr/bin/env python3
"""M16 subsystem maturity / scheduler record v5 (re-derivation of the scheduler blocking items): deterministic builder.

A NEW version. M16 v4 (docs/experiments/hall_icp/integration/m16_v4/: JSON, Markdown, builder and its modules) and M16 v3
stay byte-identical and are pinned by sha256 here; nothing under docs/budgets/subsystem_maturity/ is written.

Why v5: A9.16 S9.4 / M16-V3-Q-01 residual - "re-derivation of M16 scheduler blocking items from the A9.8 .. A9.15
answers (M16 v5 refresh) is not built in A9.16". v4 resolves its owner-question blockers against the immutable state v4
snapshot (every one TBD_OWNER there) and only overlays their state v5 status. v5 re-derives every row from:

  * the owner answers A9.8 .. A9.21, read through owner-question state v5 (the source of truth for answered / amended
    statuses: answer pointer + json / verbatim md sha256, later_owner_decisions) and, for the later items without a state
    row (A9.19 architecture, A9.20 answer, A9.21 HW_PROGRAMME / ICP_GATE / AL08 / EXTERNAL_INPUTS), through the pinned
    decision records (docs/decisions/application/a9_later_lib.py);
  * the A9.21 programme order (docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json: steps, predecessors,
    entry preconditions, entry_status_now);
  * GNG-ICP-01 (mandatory ICP go / no-go before LOCK-1: RVM owner_approved_gates + F9 pre_lock1_gates).

For each row it records: what blocked it in v4 (scheduler item + contributing blockers, copied from the pinned v4 JSON);
which answers removed or changed which blockers (pointer + sha256, effect); what still blocks it, each blocker with a
category (OWNER_ACT / EVIDENCE / HARDWARE_RUN / EXTERNAL_INPUT) and a build-time check that it is still open; the single
scheduler blocking item (owner row 141: one-blocker rule); and the readiness state under the existing M16 vocabulary,
derived with the v4 derive_state() plus the v5 guard R-M16V5-03: a state may only advance when its determining evidence
(a registered measured artifact on project hardware) exists; owner answers that only authorise work never advance it.

Named persons: none in the repository; the 'no person fabricated' rule stands (A9.14 M16-V3-Q-01: names come from the
project staffing ledger before the work package starts) - every scheduled row keeps a NAMED_ENGINEER blocker
(PENDING_EVIDENCE) and READY stays unreachable without one (R-M16V4-05).

Fail closed: a missing pinned input, a changed pin, an unknown answer ref, an answer outside A9.8 .. A9.21, a v4
owner-question blocker without a reviewed answer entry, a blocker that is no longer open, or a scheduler item that is
not among the remaining blockers raises.

Build order: ... RVM -> F9 -> owner-question state v5 -> M16 v5 (--check on each catches a stale downstream output).

stdlib only. Usage:
    python docs/experiments/hall_icp/integration/m16_v5/build_subsystem_maturity_v5.py          # write JSON + MD
    python docs/experiments/hall_icp/integration/m16_v5/build_subsystem_maturity_v5.py --check  # verify outputs
No prediction, no winner, no PASS; A9 stays OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
V4_DIR = HERE.parent / "m16_v4"
_APP = str(ROOT / "docs" / "decisions" / "application")
if _APP not in sys.path:
    sys.path.insert(0, _APP)
import a9_16_lib as L  # noqa: E402  (A9.8 .. A9.15 pins)
import a9_later_lib as X  # noqa: E402  (A9.17 .. A9.21 pins)


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B4 = _module("m16_v4_builder_for_v5", V4_DIR / "build_subsystem_maturity_v4.py")  # v4 resolver + derive_state (reused)
SPEC = _module("m16_v5_rows", HERE / "m16_v5_rows.py")


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


OUT_JSON = HERE / "subsystem_maturity_v5.json"
OUT_MD = HERE / "SUBSYSTEM_MATURITY_v5.md"
TEST_REL = "tests/test_m16_v5.py"
ARTIFACT_REL = "docs/experiments/hall_icp/integration/m16_v5/subsystem_maturity_v5.json"

V4_REL = "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json"
V4_DIR_REL = "docs/experiments/hall_icp/integration/m16_v4"
OQ4_REL = "docs/budgets/owner_decisions/owner_questions_state_v4.json"

# immutable inputs pinned by sha256 (M16 v4 stays byte-identical; state v4 immutable)
PINS = {
    V4_REL: ("fde0ddac723b62ab9bdc9789fa738c74198de23b8d150fd67b1b89d9e9d2d2ae", "M16 v4 (immutable; rows re-derived here)"),
    f"{V4_DIR_REL}/SUBSYSTEM_MATURITY_v4.md":
        ("8cd180af12b06939a546e42217d2781fccc916945ae1953c70e8febd6abd0466", "M16 v4 companion (immutable)"),
    f"{V4_DIR_REL}/build_subsystem_maturity_v4.py":
        ("5b825962ab3ea7e7cd5de1c2ca9634d0da508948b426a326a7967123bb844e91",
         "M16 v4 builder (immutable; resolve_blocker / derive_state reused)"),
    f"{V4_DIR_REL}/m16_v4_rows.py":
        ("76f7a1a84e4e1ae05f08d3a962cc7ae68eeecb1d5c07220c49f553404442dc41", "M16 v4 row specifications (immutable)"),
    f"{V4_DIR_REL}/a9_16_m16.py":
        ("2a5f341b4da968721acb453b6bda80678c83910aa28d64027bdb9998fd1b2834", "M16 v4 A9.16 overlay (immutable)"),
    f"{V4_DIR_REL}/a9_19_m16.py":
        ("b81e71e6c1165c317171ab5772ce29c07d42647563a6749ad432e6b7083970e2", "M16 v4 A9.19 / A9.20 / A9.21 labels (immutable)"),
    OQ4_REL: ("6ba74803f9577cb63f3e719d176702eb47e05a55a3c054eba926649a5c23bf67",
              "owner-question state v4 (immutable; the v4 blockers' snapshot)"),
    "docs/EVIDENCE.md": ("a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61",
                         "evidence rules (quantity types; CLAUDE.md rule 10)"),
}

# mutable deliverables: read at build time, identity and every cited id checked; never sha-pinned (rebuilt by their lanes)
REFERENCED = {
    "OQ5": ("docs/budgets/owner_decisions/owner_questions_state_v5.json", "id", "owner_questions_state_v5",
            "source of truth for answered / amended statuses (A9.8 .. A9.21)"),
    "PROG": ("docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json", "id", "hw_programme_a9_21_v1",
             "A9.21 programme order (steps, predecessors, entry preconditions)"),
    "RVM": ("docs/requirements/rvm_a9/rvm_a9_v1.json", "id", "rvm_a9_v1", "GNG-ICP-01 owner_approved_gates"),
    "F9": ("docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json", "id",
           "ARCHITECTURE_FREEZE_CANDIDATE_v1", "GNG-ICP-01 pre_lock1_gates / lock1_precondition"),
    "XE3": ("docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json", "id", "xe_accounting_a9_v3",
            "flight Xe scenario booking"),
    # A9.24 AFI-01: v4 = v3 + the AL-08 cathode-feed re-base; A9.26: the current flight mass / power package is the v5
    # successor of v4 (10 % system margin for the bid basis, AL-09 1.0 kg); AL-08 is unchanged from v4
    "MP5": ("docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json", "id", "mass_power_a9_v5", "AL-08 A9.21 label"),
    "S1A": ("docs/experiments/s1a_readiness/s1a_readiness_status_current.json", "schema",
            "abep_s1a_readiness_report_v1", "S1a readiness conditions"),
    "P4": ("docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json", "id", "p4_anode_materials_v1",
           "P4 applications"),
    "RFQ3": ("docs/procurement/rfq_a9_v3/rfq_a9_v3.json", "id", "RFQ_A9_V3", "RFQ v3 packages"),
    # A9.22 G8 stage 2: BUS_ITEM_OPEN blockers resolve in the v2 boundary (no longer through the immutable v4 builder's
    # INPUTS, which name v1); the item is cross-checked identical in v1
    "BUS": ("docs/architecture_comparison/power_boundary_a9_v2/bus_power_boundary_a9_v2.json", "id",
            "bus_power_boundary_a9_v2", "A9-02 bus-power boundary v2 (BUS_ITEM_OPEN blockers)"),
}
BUS_V1_REL = "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json"


def _bus_v2_text(text):
    """A v4-carried artifact string naming the v1 boundary document, re-pointed to v2 (citation only)."""
    return text.replace(BUS_V1_REL, REFERENCED["BUS"][0]) if isinstance(text, str) else text
V4_KIND_KEY = {"P1_MEASUREMENT": "P1", "P2_MEASUREMENT": "P2", "P3_INPUT": "P3", "P4_EVIDENCE": "P4",
               "VENDOR_QUOTE": "RFQ", "INTERFACE_TBD": "ICD", "BUS_ITEM_OPEN": "BUS", "H2A9_ITEM_TBD": "H2A9"}

STATES = list(B4.STATES)                                   # the existing M16 vocabulary, unchanged
WAITS_ON = list(B4.WAITS_ON) + list(SPEC.WAITS_ON_V5_ADDITIONS)
CATEGORIES = SPEC.CATEGORIES
# readiness rank for the no-advance guard (higher = further toward VERIFIED)
RANK = {"BLOCKED": 0, "RUNNING": 1, "READY": 2, "VERIFIED": 3}
DECIDED_PREFIXES = ("ANSWERED_BY_A9_", "AMENDED_BY_A9_")
ANSWER_DECISIONS = tuple(k for k in L.ORDER) + tuple(X.ORDER)       # A9.8 .. A9.15, A9.17 .. A9.21
PROGRAMME_NOT_DONE = {"NOT_STARTABLE_PREDECESSOR_INCOMPLETE", "NOT_STARTABLE_PRECONDITION_MISSING",
                      "ENTRY_NOT_MET_FROZEN_AFTER_START", "NO_A9_21_ENTRY_PRECONDITION_LISTED",
                      "ENTRY_GATED_BY_EXISTING_STAGE_RULES", "ENTRY_PRECONDITIONS_REGISTERED"}
GATE_ID = "GNG-ICP-01"
# measured artifacts registered on project hardware (docs/EVIDENCE.md quantity type 'measured'); a row's state may
# advance only on an entry here: {row: [{"path", "quantity_type": "measured", "synthetic": False, "what"}]}. Empty: no
# programme step has run and no measured hardware record exists in the repository.
MEASURED_REGISTRY: dict = {}


class BuildError(RuntimeError):
    pass


def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _clip(s, n=240) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 3] + "..."


# ----------------------------------------------------------------------------------------------------------------------
class Ctx:
    def __init__(self):
        self.pins = []
        for rel, (sha, role) in PINS.items():
            if not (ROOT / rel).is_file():
                raise BuildError(f"pinned input missing: {rel}")
            got = _sha(rel)
            if got != sha:
                raise BuildError(f"pinned input changed: {rel} sha256 {got} != {sha}")
            self.pins.append({"path": rel, "sha256": sha, "role": role})
        for p in L.pins() + X.pins():
            if p["sha256"] and _sha(p["path"]) != p["sha256"]:
                raise BuildError(f"decision record changed: {p['path']}")
            self.pins.append({"path": p["path"], "sha256": p["sha256"] or _sha(p["path"]),
                              "role": f"owner decision record ({p['key']})"})
        self.docs = {}
        for key, (rel, field, want, _) in REFERENCED.items():
            if not (ROOT / rel).is_file():
                raise BuildError(f"referenced input missing: {rel}")
            d = _load(rel)
            if d.get(field) != want:
                raise BuildError(f"{rel}: identity {field}={d.get(field)!r} != {want!r}")
            self.docs[key] = d
        self.v4 = _load(V4_REL)
        self.ctx4 = B4.Ctx()          # v4 pins re-verified; live P1 .. H2A9 deliverables for the v4 resolver
        self.v5 = {}
        for r in self.docs["OQ5"]["rows"]:
            self.v5.setdefault(r["id"], []).append(r)
        self.steps = {s["id"]: s for s in self.docs["PROG"]["steps"]}
        vocab = set(self.docs["PROG"]["entry_status_vocabulary"])
        if vocab != PROGRAMME_NOT_DONE:
            raise BuildError(f"programme entry-status vocabulary changed ({sorted(vocab)}): review the M16 v5 "
                             "programme-step rule (a step may now be reportable as done)")

    def v5row(self, qid: str) -> dict:
        rows = self.v5.get(qid, [])
        if len(rows) != 1:
            raise BuildError(f"state v5: {qid} resolves to {len(rows)} rows (expected exactly one)")
        return rows[0]


# ----------------------------------------------------------------------------------------------------------------------
# owner answers (A9.8 .. A9.21): pointer + json / verbatim md sha256
# ----------------------------------------------------------------------------------------------------------------------
def resolve_answer(ctx: Ctx, ref: str) -> dict:
    if "/" in ref:
        key, item = ref.split("/", 1)
        if key not in X.ORDER:
            raise BuildError(f"answer ref {ref!r}: {key} is not a later decision (A9.17 .. A9.21)")
        d = X.LOADED[key]
        return {"ref": ref, "source": "decision record (a9_later_lib, pinned)", "decision": key, "item": item,
                "decision_code": X.decision_code(key, item), "pointer": X.pointer(key, item),
                "decision_json": d["json"], "decision_json_sha256": d["json_sha256"], "decision_md": d["md"],
                "decision_md_sha256": d["md_sha256"]}
    r = ctx.v5row(ref)
    st = r.get("status", "")
    if not st.startswith(DECIDED_PREFIXES):
        raise BuildError(f"answer ref {ref}: state v5 status {st!r} is not an owner answer (ANSWERED_BY_A9_* / "
                         "AMENDED_BY_A9_*)")
    dec = r.get("answer_decision")
    if dec not in ANSWER_DECISIONS:
        raise BuildError(f"answer ref {ref}: answer decision {dec!r} outside A9.8 .. A9.21")
    lib = L if dec in L.ORDER else X
    d = lib.LOADED[dec]
    if r.get("answer_sha256") != d["json_sha256"] or (r.get("answer_verbatim_sha256") not in (None, d["md_sha256"])):
        raise BuildError(f"answer ref {ref}: state v5 sha256 does not match the pinned {dec} record")
    out = {"ref": ref, "source": f"{REFERENCED['OQ5'][0]} rows[id={ref}]", "state_v5_status": st,
           "decision": dec, "decision_code": r.get("decision_code"), "pointer": r.get("answer_pointer"),
           "decision_json": d["json"], "decision_json_sha256": d["json_sha256"], "decision_md": d["md"],
           "decision_md_sha256": d["md_sha256"]}
    if not out["pointer"]:
        raise BuildError(f"answer ref {ref}: no answer_pointer in state v5")
    if r.get("amended_by"):
        a = r["amended_by"]
        out["amended_by"] = {k: a.get(k) for k in ("decision", "decision_json", "decision_json_sha256", "pointer")}
    if r.get("later_owner_decisions"):
        out["later_owner_decisions"] = [{k: x[k] for k in ("decision", "item", "relation", "pointer",
                                                           "decision_json_sha256")} for x in r["later_owner_decisions"]]
    return out


# ----------------------------------------------------------------------------------------------------------------------
# remaining blockers (each checked still open at build time)
# ----------------------------------------------------------------------------------------------------------------------
def _one(items, key, val, where):
    hits = [x for x in items if isinstance(x, dict) and x.get(key) == val]
    if len(hits) != 1:
        raise BuildError(f"{where}: {key}={val!r} found {len(hits)} times")
    return hits[0]


def resolve_v5(ctx: Ctx, kind: str, ident: str, v4row: dict) -> dict:
    if kind not in SPEC.BLOCKER_KINDS_V5:
        raise BuildError(f"blocker kind {kind!r} not in the v5 vocabulary")
    cat = SPEC.BLOCKER_KINDS_V5[kind][0]
    base = {"id": ident, "kind": kind}
    if kind == "BUS_ITEM_OPEN":
        b = B4.resolve_blocker(ctx.ctx4, kind, V4_KIND_KEY[kind], ident)        # v1 (v4 resolver), cross-check
        it = _one(ctx.docs["BUS"].get("items", []), "id", ident, "bus_power_boundary_a9_v2 items")
        if not str(it.get("status", "")).startswith("OPEN"):
            raise BuildError(f"bus item {ident} is no longer OPEN")
        if (b["artifact"], str(it.get("status")), str(it.get("name", ""))) != (BUS_V1_REL, b["state"], b["detail"]):
            raise BuildError(f"bus item {ident}: v2 differs from the v1 resolution")
        return {**base, "category": cat, "artifact": REFERENCED["BUS"][0], "locator": f"items[id={ident}]",
                "state": str(it.get("status")), "detail": _clip(str(it.get("name", "")))}
    if kind in SPEC.V4_KINDS:
        b = B4.resolve_blocker(ctx.ctx4, kind, V4_KIND_KEY[kind], ident)
        return {**base, "category": cat, "artifact": b["artifact"], "locator": b["locator"], "state": b["state"],
                "detail": _clip(b.get("detail"))}
    if kind == "OWNER_QUESTION_V5":
        r = ctx.v5row(ident)
        if r["status"] != "TBD_OWNER":
            raise BuildError(f"owner question {ident} is {r['status']} in state v5, not an open blocker")
        return {**base, "category": cat, "artifact": REFERENCED["OQ5"][0], "locator": f"rows[id={ident}]",
                "state": "TBD_OWNER", "detail": _clip(r.get("question")), "blocks": r.get("blocks")}
    if kind == "GATE_CRITERIA":
        gid = ident.split("/")[0]
        g = _one(ctx.docs["RVM"].get("owner_approved_gates", []), "id", gid, "RVM owner_approved_gates")
        if g.get("criteria") != "PENDING_OWNER_ACCEPTANCE":
            raise BuildError(f"{gid} criteria {g.get('criteria')!r}: no longer pending - refresh the blocker")
        return {**base, "category": cat, "artifact": REFERENCED["RVM"][0], "locator": f"owner_approved_gates[id={gid}]",
                "state": "criteria PENDING_OWNER_ACCEPTANCE", "detail": _clip(g.get("criteria_note")),
                "placement": g.get("placement")}
    if kind == "GATE_EVALUATION":
        gid = ident.split("/")[0]
        g = _one(ctx.docs["F9"].get("pre_lock1_gates", []), "id", gid, "F9 pre_lock1_gates")
        if g.get("current_status") != "NOT_EVALUATED":
            raise BuildError(f"{gid} is {g.get('current_status')!r} in F9: refresh the blocker")
        if ctx.docs["F9"].get("lock1_precondition", {}).get("lock1_release_reportable") is not False:
            raise BuildError("F9 lock1_precondition.lock1_release_reportable is not False")
        return {**base, "category": cat, "artifact": REFERENCED["F9"][0], "locator": f"pre_lock1_gates[id={gid}]",
                "state": "NOT_EVALUATED (fail closed)", "detail": _clip(g.get("status_reason"))}
    if kind == "PROGRAMME_STEP":
        s = ctx.steps.get(ident)
        if s is None:
            raise BuildError(f"programme step {ident} not in {REFERENCED['PROG'][0]}")
        if s["entry_status_now"] not in PROGRAMME_NOT_DONE:
            raise BuildError(f"programme step {ident}: entry status {s['entry_status_now']!r} outside the known set")
        c = SPEC.PROGRAMME_STEP_CATEGORY.get(s["kind"])
        if c is None:
            raise BuildError(f"programme step {ident}: kind {s['kind']!r} has no category")
        return {**base, "category": c, "artifact": REFERENCED["PROG"][0], "locator": f"steps[id={ident}]",
                "state": s["entry_status_now"], "detail": _clip(s["title"]), "step_kind": s["kind"],
                "predecessors": [p["step"] for p in s.get("predecessors", [])],
                "entry_preconditions": [p["id"] for p in s.get("entry_preconditions", [])]}
    if kind == "ANSWER_REQUIRED_EVIDENCE":
        r = ctx.v5row(ident)
        if not r["status"].startswith(DECIDED_PREFIXES):
            raise BuildError(f"{ident}: not an answered row in state v5")
        return {**base, "category": cat, "artifact": REFERENCED["OQ5"][0], "locator": f"rows[id={ident}]",
                "state": "ANSWER_RECORDED_REQUIRED_EVIDENCE_NOT_REGISTERED",
                "detail": f"{r.get('decision_code')}: " + _clip(r.get("answer_excerpt"), 200)}
    if kind == "EXTERNAL_INPUT_V5":
        r = ctx.v5row(ident)
        if not str(r.get("external_input_status", "")).startswith("TBD_EXTERNAL_INPUT"):
            raise BuildError(f"{ident}: external_input_status no longer TBD_EXTERNAL_INPUT")
        return {**base, "category": cat, "artifact": REFERENCED["OQ5"][0], "locator": f"rows[id={ident}]",
                "state": "TBD_EXTERNAL_INPUT", "detail": _clip(r["external_input_status"])}
    if kind == "XE_LEDGER_REFUSED":
        e = _one(ctx.docs["XE3"]["evaluations"], "scenario", ident, "Xe v3 evaluations")
        st = e.get("booking", {}).get("status")
        if st != "REFUSED_TBD_INPUTS":
            raise BuildError(f"Xe v3 {ident} booking {st!r}: refresh the blocker")
        return {**base, "category": cat, "artifact": REFERENCED["XE3"][0], "locator": f"evaluations[scenario={ident}]",
                "state": st, "detail": "TBD lines: " + ", ".join(e["booking"].get("tbd_lines", []))}
    if kind == "AL08_PROVISIONAL":
        ln = _one(ctx.docs["MP5"]["lines"]["hall_icp_neutralizer"], "line", ident, "mass / power v5 lines")
        st = str(ln.get("a9_21_status", ""))
        if not st.startswith("PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN"):
            raise BuildError(f"{ident}: a9_21_status {st[:60]!r} is no longer the provisional floor")
        return {**base, "category": cat, "artifact": REFERENCED["MP5"][0],
                "locator": f"lines.hall_icp_neutralizer[line={ident}]", "state": "PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN",
                "detail": _clip(st)}
    if kind == "S1A_CONDITION":
        m = _one(ctx.docs["S1A"]["missing"], "condition", ident, "S1a readiness missing")
        if m.get("state") != "MISSING":
            raise BuildError(f"{ident}: state {m.get('state')!r}, no longer MISSING")
        return {**base, "category": cat, "artifact": REFERENCED["S1A"][0], "locator": f"missing[condition={ident}]",
                "state": "MISSING", "detail": _clip(m.get("owner_clause"))}
    if kind == "P4_APPLICATION_OPEN":
        a = ctx.docs["P4"]["applications"].get(ident)
        if not a or not a.get("blockers"):
            raise BuildError(f"P4 application {ident} missing or without blockers")
        return {**base, "category": cat, "artifact": REFERENCED["P4"][0], "locator": f"applications.{ident}.blockers",
                "state": "OPEN", "detail": _clip("; ".join(a["blockers"]))}
    if kind == "RFQ3_PACKAGE":
        _one(ctx.docs["RFQ3"]["packages"], "id", ident, "RFQ v3 packages")
        if not any("QUOTATION / SPECIFICATION ONLY" in b for b in ctx.docs["RFQ3"].get("banner", [])):
            raise BuildError("RFQ v3 banner no longer states quotation / specification only")
        return {**base, "category": cat, "artifact": REFERENCED["RFQ3"][0], "locator": f"packages[id={ident}]",
                "state": "QUOTATION_ONLY (no quotation registered; dispatch by the owner / procurement)",
                "detail": "quotation package"}
    if kind == "NAMED_ENGINEER":
        if v4row["owner"].get("named_engineer") is not None:
            raise BuildError(f"row {v4row['row']}: a named engineer appeared in v4 - review")
        return {**base, "category": cat, "artifact": "project staffing ledger (owner; not in the repository)",
                "locator": None, "state": "PENDING_EVIDENCE",
                "detail": "named responsible engineer for the functional role '" + str(v4row["owner"].get(
                    "functional_role")) + "' (A9.14 M16-V3-Q-01: from the staffing ledger before the work package "
                    "starts; none fabricated)"}
    raise BuildError(f"unhandled blocker kind {kind}")


# ----------------------------------------------------------------------------------------------------------------------
# readiness (existing vocabulary; v4 derive_state + the v5 no-advance guard)
# ----------------------------------------------------------------------------------------------------------------------
def determining_evidence(row: int) -> list:
    out = []
    for a in MEASURED_REGISTRY.get(row, []):
        ok = (a.get("quantity_type") == B4.MEASURED_QUANTITY_TYPE and a.get("synthetic") is False
              and a.get("path") and (ROOT / a["path"]).is_file())
        if not ok:
            raise BuildError(f"row {row}: registered evidence {a} is not a measured, existing, non-synthetic artifact")
        out.append({**a, "path_exists": True, "kind": "HARDWARE_RECORD"})
    return out


def derive_state_v5(state_v4: str, rec: dict) -> tuple:
    """(state, rule). v4 derive_state(); then R-M16V5-03: a state above the v4 state needs determining evidence
    (rec['measured_artifacts']: measured, existing, non-synthetic); authorising answers never count."""
    state, rule = B4.derive_state(rec)
    if state == "SUPERSEDED_FOR_PRIMARY_LINE" or state_v4 == "SUPERSEDED_FOR_PRIMARY_LINE":
        return state, rule
    if RANK[state] > RANK[state_v4]:
        ev = [a for a in rec.get("measured_artifacts", []) if a.get("quantity_type") == B4.MEASURED_QUANTITY_TYPE
              and a.get("synthetic") is False and a.get("path_exists") is True]
        if not ev:
            return state_v4, "R-M16V5-03"
    return state, rule


RULES = [
    {"id": "R-M16V5-01", "rule": "state vocabulary, precedence and R-M16V4-01 .. 08 unchanged (M16 v4 derive_state(), "
                                 "reused from the pinned v4 builder)"},
    {"id": "R-M16V5-02", "rule": "re-derivation: every v4 blocker (scheduler + contributing) is dispositioned; an "
                                 "owner-question blocker is removed only by an owner answer A9.8 .. A9.21 recorded in "
                                 "state v5 (ANSWERED_BY_A9_* / AMENDED_BY_A9_*; pointer + json / md sha256); every "
                                 "other blocker is re-resolved against the live artifact and stays while open"},
    {"id": "R-M16V5-03", "rule": "no readiness advance without determining evidence: a state above the v4 state needs a "
                                 "registered measured artifact on project hardware (docs/EVIDENCE.md 'measured'; "
                                 "MEASURED_REGISTRY); an owner answer that authorises / orders work (AUTHORIZES_WORK) "
                                 "or records a rule never advances readiness"},
    {"id": "R-M16V5-04", "rule": "every remaining blocker carries one category (OWNER_ACT / EVIDENCE / HARDWARE_RUN / "
                                 "EXTERNAL_INPUT) and a build-time check that it is still open (fail closed)"},
    {"id": "R-M16V5-05", "rule": "one scheduler blocking item per row (owner row 141), chosen among the remaining "
                                 "blockers; an answer that changed the v4 item re-points the row to the first missing "
                                 "input of the answer's path (A9.21 programme order where it applies)"},
    {"id": "R-M16V5-06", "rule": "named persons: none in the repository and none fabricated; every scheduled row keeps a "
                                 "NAMED_ENGINEER blocker (PENDING_EVIDENCE: staffing ledger, owner) and READY needs a "
                                 "named engineer (R-M16V4-05)"},
    {"id": "R-M16V5-07", "rule": "GNG-ICP-01 (A9.21 ICP_GATE) is a row-18 blocker twice: its criteria "
                                 "(PENDING_OWNER_ACCEPTANCE, OWNER_ACT) and its evaluation (NOT_EVALUATED, fail closed, "
                                 "EVIDENCE); LOCK-1 is not reportable while it is not GO"},
]


# ----------------------------------------------------------------------------------------------------------------------
def _v4_blockers(r4: dict) -> dict:
    b = r4.get("blocking_item") or {}
    typed = [(x["kind"], x["id"]) for x in b.get("items", []) + b.get("also_open", []) + b.get("still_open_check", [])]
    return {"scheduler": {"text": b.get("text"), "kind": b.get("kind"), "carried_from_v3": b.get("carried_from_v3"),
                          "typed_items": [{"kind": k, "id": i} for k, i in typed]},
            "waits_on": r4.get("waits_on"),
            "contributing": [{"kind": c["kind"], "id": c["id"]} for c in r4["contributing_blockers"]]}


def build_row(ctx: Ctx, r4: dict, idx: int) -> tuple:
    n = r4["row"]
    spec = SPEC.ROWS.get(n, "missing")
    if spec == "missing":
        raise BuildError(f"row {n}: no v5 specification")
    v4ref = f"{V4_REL}#/rows/{idx}"
    base = {"row": n, "key": r4["key"], "name": r4["name"], "group": r4["group"], "v4_ref": v4ref,
            "a9_19_20_labels": (v4ref + "/a9_19_20") if r4.get("a9_19_20") else None,
            "a9_21_programme_items_v4": [x["item"] for x in r4.get("a9_21", [])],
            "v4_blockers": _v4_blockers(r4), "state_v4": r4["execution_state"]}
    if r4["execution_state"] == "SUPERSEDED_FOR_PRIMARY_LINE":
        if spec is not None:
            raise BuildError(f"row {n}: superseded in v4 but has a v5 specification")
        state, rule = derive_state_v5("SUPERSEDED_FOR_PRIMARY_LINE", {"superseded_for_primary_line": True})
        row = {**base, "answers_applied": [], "removed_blockers": [], "remaining_blockers": [],
               "remaining_by_category": {}, "blocking_item": None, "waits_on": None, "owner": r4["owner"],
               "determining_evidence": [], "execution_state": state, "state_rule": rule,
               "readiness_statement": "historical row, not scheduled (carried unchanged)"}
        return row, {"removed": 0, "remaining": 0}
    if spec is None:
        raise BuildError(f"row {n}: scheduled row without a v5 specification")
    # answers
    answers = {}
    for ref, (effect, targets, note) in spec["answers"].items():
        if effect not in SPEC.EFFECTS:
            raise BuildError(f"row {n}: effect {effect!r} for {ref} not in the vocabulary")
        if effect in SPEC.EFFECTS_NEEDING_TARGET and not targets:
            raise BuildError(f"row {n}: {ref} ({effect}) must name the blocker it now waits on")
        answers[ref] = {**resolve_answer(ctx, ref), "effect": effect, "now_waits_on": list(targets), "note": note}
    oq_v4 = [c["id"] for c in r4["contributing_blockers"] if c["kind"] == "OWNER_QUESTION"]
    missing = [q for q in oq_v4 if q not in answers]
    if missing:
        raise BuildError(f"row {n}: v4 owner-question blockers without a reviewed v5 answer entry: {missing}")
    # removed blockers
    removed = []
    for q in oq_v4:
        a = answers[q]
        removed.append({"v4_blocker": {"kind": "OWNER_QUESTION", "id": q}, "removed_by": q, "effect": a["effect"],
                        "decision": a["decision"], "pointer": a["pointer"],
                        "decision_json_sha256": a["decision_json_sha256"], "now_waits_on": a["now_waits_on"]})
    sched4 = r4["blocking_item"]
    sd = spec["sched_v4"]
    remaining = []
    if sd["disposition"] == "CHANGED":
        for ref in sd["by"]:
            if ref not in answers:
                raise BuildError(f"row {n}: v4 scheduler item changed by {ref}, which has no answer entry")
        typed = {(x["kind"], x["id"]) for x in base["v4_blockers"]["scheduler"]["typed_items"]}
        contrib = {(c["kind"], c["id"]) for c in r4["contributing_blockers"]}
        if typed - contrib:
            raise BuildError(f"row {n}: changed v4 scheduler item has typed items not carried as contributing")
        removed.append({"v4_blocker": {"kind": "V4_SCHEDULER", "text": sched4["text"]}, "removed_by": list(sd["by"]),
                        "effect": "CHANGED_BY_ANSWERS", "note": sd["note"],
                        "pointers": [{"ref": r, "pointer": answers[r]["pointer"],
                                      "decision_json_sha256": answers[r]["decision_json_sha256"]} for r in sd["by"]]})
    elif sd["disposition"] == "CARRIED":
        if sd["category"] not in CATEGORIES:
            raise BuildError(f"row {n}: category {sd['category']!r}")
        for ref in sd.get("by", []):
            if ref not in answers:
                raise BuildError(f"row {n}: carried item constrained by {ref}, which has no answer entry")
        checks = []
        for x in base["v4_blockers"]["scheduler"]["typed_items"]:
            checks.append(resolve_v5(ctx, x["kind"], x["id"], r4))
        if "check" in sd:
            checks.append(resolve_v5(ctx, sd["check"][0], sd["check"][1], r4))
        remaining.append({"id": "V4-SCHED", "kind": "V4_SCHEDULER_CARRIED", "category": sd["category"],
                          "artifact": _bus_v2_text(sched4.get("source")), "locator": f"{v4ref}/blocking_item",
                          "state": "OPEN (carried from v4" + ("; re-resolved" if checks else "; no answer removes it")
                                   + ")", "detail": _clip(sched4["text"]), "note": sd["note"],
                          "constrained_by": list(sd.get("by", [])), "still_open_checks": checks})
    else:
        raise BuildError(f"row {n}: unknown v4 scheduler disposition {sd['disposition']!r}")
    for c in r4["contributing_blockers"]:
        if c["kind"] == "OWNER_QUESTION":
            continue
        remaining.append({**resolve_v5(ctx, c["kind"], c["id"], r4), "origin": "v4 contributing (re-resolved)"})
    for kind, ident in spec["added"]:
        remaining.append({**resolve_v5(ctx, kind, ident, r4), "origin": "v5 (answers A9.8 .. A9.21 / programme / gate)"})
    remaining.append({**resolve_v5(ctx, "NAMED_ENGINEER", "STAFFING-LEDGER", r4), "origin": "R-M16V5-06"})
    ids = [b["id"] for b in remaining]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise BuildError(f"row {n}: duplicate remaining blockers {dup}")
    for ref, a in answers.items():
        for t in a["now_waits_on"]:
            if t not in ids:
                raise BuildError(f"row {n}: answer {ref} waits on {t!r}, which is not a remaining blocker")
    for b in remaining:
        if b["category"] not in CATEGORIES:
            raise BuildError(f"row {n}: blocker {b['id']} category {b['category']!r}")
    sid, sreason = spec["scheduler"]
    sb = [b for b in remaining if b["id"] == sid]
    if len(sb) != 1:
        raise BuildError(f"row {n}: scheduler item {sid!r} is not one remaining blocker")
    waits = spec["waits_on"]
    if waits not in WAITS_ON:
        raise BuildError(f"row {n}: waits_on {waits!r} not in the vocabulary")
    evidence = determining_evidence(n)
    rec = {"physical": True, "interface_frozen": False, "readiness_conditions": [], "measured_artifacts": evidence,
           "worked_by": None, "blocking_item": sb[0], "contributing_open": remaining,
           "named_engineer": r4["owner"].get("named_engineer")}
    state, rule = derive_state_v5(r4["execution_state"], rec)
    if state not in STATES:
        raise BuildError(f"row {n}: state {state} outside the vocabulary")
    cats = {}
    for b in remaining:
        cats[b["category"]] = cats.get(b["category"], 0) + 1
    owner = dict(r4["owner"])
    owner["named_engineer_status"] = "PENDING_EVIDENCE (project staffing ledger, owner; none in the repository; none " \
                                     "fabricated)"
    row = {**base,
           "answers_applied": list(answers.values()),
           "removed_blockers": removed,
           "remaining_blockers": remaining,
           "remaining_by_category": dict(sorted(cats.items())),
           "blocking_item": {"id": sid, "kind": sb[0]["kind"], "category": sb[0]["category"], "detail": sb[0]["detail"],
                             "state": sb[0]["state"], "reason": sreason,
                             "changed_from_v4": sd["disposition"] == "CHANGED" or sid != "V4-SCHED"},
           "waits_on": waits,
           "owner": owner,
           "determining_evidence": evidence,
           "execution_state": state, "state_rule": rule,
           "readiness_statement": ("state unchanged: no determining evidence exists (no measured artifact on project "
                                   "hardware; no A9.21 programme step has run); answers that authorise work or record a "
                                   "rule do not advance readiness")
           if state == r4["execution_state"] else "STATE CHANGED on registered determining evidence"}
    return row, {"removed": len(removed), "remaining": len(remaining)}


def build() -> dict:
    ctx = Ctx()
    v4rows = ctx.v4["rows"]
    if sorted(k for k in SPEC.ROWS) != [r["row"] for r in v4rows]:
        raise BuildError("v5 row specifications do not cover exactly the v4 rows")
    rows, diff = [], []
    for i, r4 in enumerate(v4rows):
        row, _ = build_row(ctx, r4, i)
        rows.append(row)
        b = row["blocking_item"]
        diff.append({"row": row["row"], "key": row["key"], "state_v4": row["state_v4"], "state_v5": row["execution_state"],
                     "state_changed": row["execution_state"] != row["state_v4"],
                     "scheduler_v4": row["v4_blockers"]["scheduler"]["text"],
                     "scheduler_v5": None if b is None else f"{b['id']}: {b['detail']}",
                     "scheduler_changed": bool(b and b["changed_from_v4"]),
                     "waits_on_v4": row["v4_blockers"]["waits_on"], "waits_on_v5": row["waits_on"],
                     "blockers_removed": len(row["removed_blockers"]),
                     "blockers_remaining": len(row["remaining_blockers"])})
    # roll-ups
    st4, st5, cats, effects, waits = {}, {}, {}, {}, {}
    for r in rows:
        st4[r["state_v4"]] = st4.get(r["state_v4"], 0) + 1
        st5[r["execution_state"]] = st5.get(r["execution_state"], 0) + 1
        if r["waits_on"]:
            waits[r["waits_on"]] = waits.get(r["waits_on"], 0) + 1
        for b in r["remaining_blockers"]:
            cats[b["category"]] = cats.get(b["category"], 0) + 1
        for x in r["removed_blockers"]:
            effects[x["effect"]] = effects.get(x["effect"], 0) + 1
    sched_cats = {}
    for r in rows:
        if r["blocking_item"]:
            c = r["blocking_item"]["category"]
            sched_cats[c] = sched_cats.get(c, 0) + 1
    if any(r["execution_state"] in ("READY", "VERIFIED", "RUNNING") for r in rows) and not MEASURED_REGISTRY:
        raise BuildError("a row advanced without registered determining evidence")
    used = {}
    for r in rows:
        for a in r["answers_applied"]:
            used.setdefault(a["ref"], {k: a[k] for k in ("ref", "decision", "decision_code", "pointer", "decision_json",
                                                         "decision_json_sha256", "decision_md", "decision_md_sha256")
                                       if k in a})
            used[a["ref"]].setdefault("rows", []).append(r["row"])
    n_removed = sum(len(r["removed_blockers"]) for r in rows)
    n_remaining = sum(len(r["remaining_blockers"]) for r in rows)
    n_sched_changed = sum(d["scheduler_changed"] for d in diff)
    gate = _one(ctx.docs["RVM"]["owner_approved_gates"], "id", GATE_ID, "RVM owner_approved_gates")
    m16q = L.applied_row("M16-V3-Q-01", ARTIFACT_REL,
                         ["rows[*].removed_blockers", "rows[*].remaining_blockers", "rows[*].blocking_item",
                          "rows[*].owner.named_engineer_status", "diff_v4_v5"],
                         "scheduler blocking items re-derived from the owner answers A9.8 .. A9.21 (state v5), the "
                         "A9.21 programme order and GNG-ICP-01 for every v4 row (the v4 residual of S9.4); the "
                         "accepted role map is carried; named persons stay PENDING_EVIDENCE (staffing ledger, owner; "
                         "none fabricated)", [TEST_REL])
    m16q.update({"rederivation": "APPLIED", "rows_covered": len(rows),
                 "named_persons": "PENDING_EVIDENCE (project staffing ledger, owner; none in the repository; none "
                                  "fabricated)"})
    item = lambda i, name, v, basis: {"id": i, "name": name, "value": v, "units": "count", "basis": basis,
                                      "evidence_class": "derived (bookkeeping count; no physical quantity)",
                                      "status": "COMPUTED"}
    items = [
        item("M16V5-IT-01", "rows in M16 v5", len(rows), "one row per v4 row (1-21)"),
        item("M16V5-IT-02", "rows whose readiness state changed v4 -> v5", sum(d["state_changed"] for d in diff),
             "R-M16V5-03 (no determining evidence exists)"),
        item("M16V5-IT-03", "rows whose scheduler blocking item changed v4 -> v5", n_sched_changed, "R-M16V5-05"),
        item("M16V5-IT-04", "v4 blockers removed (owner answers / changed scheduler items)", n_removed, "R-M16V5-02"),
        item("M16V5-IT-05", "remaining blockers (each checked open at build time)", n_remaining, "R-M16V5-04"),
        item("M16V5-IT-06", "distinct owner answers used (A9.8 .. A9.21)", len(used), "answers_used"),
        item("M16V5-IT-07", "registered determining evidence (measured artifacts)",
             sum(len(r["determining_evidence"]) for r in rows), "MEASURED_REGISTRY"),
    ]
    return {
        "schema": "subsystem_maturity_matrix_v5", "id": "subsystem_maturity_v5",
        "lane": "M16 v5 refresh (A9.16 S9.4 / M16-V3-Q-01 residual: scheduler re-derivation)",
        "status": "DRAFT_REDERIVATION_PENDING_CONSOLIDATED_VERIFICATION",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "supersedes_for_use": {"path": V4_REL, "sha256": PINS[V4_REL][0],
                               "note": "v4 (and v1 / v2 / v3) stay byte-identical; v4 is pinned"},
        "generated_by": _rel(Path(__file__).resolve()), "rows_module": _rel(HERE / "m16_v5_rows.py"),
        "companion_document": _rel(OUT_MD), "test": TEST_REL,
        "file_location": "docs/experiments/hall_icp/integration/m16_v5/ (nothing under docs/budgets/subsystem_maturity/)",
        "what_it_is_not": ["not a performance prediction", "not an architecture selection (no winner)",
                           "not a requirement verdict (see the RVM)", "not a change to v1 .. v4",
                           "not an owner decision: blocker dispositions, categories and scheduler picks are recorder "
                           "derivations from the cited answers; owner answers come only from the owner",
                           "an owner answer that authorises work is not evidence; software / framework completeness is "
                           "not physical readiness", "no date, duration, staffing or name is introduced"],
        "state_vocabulary": STATES,
        "waits_on_vocabulary": WAITS_ON,
        "waits_on_v5_additions": list(SPEC.WAITS_ON_V5_ADDITIONS),
        "blocker_categories": CATEGORIES, "answer_effects": SPEC.EFFECTS,
        "blocker_kinds": {k: {"default_category": v[0], "meaning": v[1]} for k, v in SPEC.BLOCKER_KINDS_V5.items()},
        "programme_step_categories": SPEC.PROGRAMME_STEP_CATEGORY,
        "readiness_rules_v4": B4.RULES,
        "readiness_rules": RULES,
        "inputs": {"answers": "owner answers A9.8 .. A9.21 via state v5 (answered / amended statuses) and the pinned "
                              "decision records (A9.17 .. A9.21 items without a state row)",
                   "programme": REFERENCED["PROG"][0], "gate": {"id": GATE_ID, "rvm": REFERENCED["RVM"][0] +
                                                                f" owner_approved_gates[id={GATE_ID}]",
                                                                "f9": REFERENCED["F9"][0] +
                                                                f" pre_lock1_gates[id={GATE_ID}]",
                                                                "placement": gate.get("placement")}},
        "pins": ctx.pins,
        "referenced_not_pinned": {"rule": "mutable deliverables: read at build time, identity and every cited id checked "
                                          "(a missing or no-longer-open id raises); never sha-pinned; the M16 v4 "
                                          "resolver also re-reads its own referenced deliverables",
                                  "artifacts": [{"key": k, "path": v[0], "identity": v[2], "use": v[3]}
                                                for k, v in REFERENCED.items()]},
        "rows": rows,
        "diff_v4_v5": diff,
        "rollup": {"execution_states_v4": dict(sorted(st4.items())), "execution_states_v5": dict(sorted(st5.items())),
                   "waits_on_v5": dict(sorted(waits.items())),
                   "removed_by_effect": dict(sorted(effects.items())),
                   "remaining_by_category": dict(sorted(cats.items())),
                   "scheduler_items_by_category": dict(sorted(sched_cats.items()))},
        "answers_used": sorted(used.values(), key=lambda a: a["ref"]),
        "items": items,
        "owner_answers_applied": [m16q],
        "open_owner_questions": [],
        "open_owner_questions_note": "no new owner question; open owner acts are listed per row (OWNER_QUESTION_V5 "
                                     "rows TBD_OWNER in state v5, GNG-ICP-01 criteria, owner releases, the staffing "
                                     "ledger)",
        "compliance": ["v1 .. v4 unchanged (v4 JSON / MD / builder / modules pinned)",
                       "every v4 row present; every v4 blocker dispositioned (R-M16V5-02)",
                       "no readiness advance without determining evidence (R-M16V5-03)",
                       "no person, date, duration or readiness fabricated", "no PASS; no winner; no prediction",
                       "one flight configuration (hall_icp_neutralizer, A9.19); C1 a ground-only laboratory reference "
                       "(A9.20; v4 labels carried by pointer)"],
    }


# ----------------------------------------------------------------------------------------------------------------------
def _c(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return " ".join(str(v).split()).replace("|", "\\|")


def render_md(d: dict) -> str:
    ro = d["rollup"]
    L_ = ["# M16 subsystem maturity / scheduler record v5 (re-derivation)", "",
          f"<!-- GENERATED by {d['generated_by']} from subsystem_maturity_v5.json; do not edit by hand -->", "",
          f"Status **{d['status']}**; A9 stays **{d['a9_status']}**. Supersedes for use `{d['supersedes_for_use']['path']}` "
          f"(sha256 `{d['supersedes_for_use']['sha256']}`), which stays byte-identical.", "",
          "Scheduler blocking items re-derived from the owner answers A9.8 .. A9.21 (owner-question state v5), the A9.21 "
          "programme order and GNG-ICP-01. A readiness state advances only on determining evidence (a registered measured "
          "artifact); answers that authorise work never advance it. Named persons: none fabricated (staffing ledger, "
          "owner). No PASS, no winner, no prediction.", "",
          f"States v4: {_c(ro['execution_states_v4'])}; v5: {_c(ro['execution_states_v5'])}.", "",
          f"Blockers removed by effect: {_c(ro['removed_by_effect'])}. Remaining by category: "
          f"{_c(ro['remaining_by_category'])}. Scheduler items by category: {_c(ro['scheduler_items_by_category'])}.", "",
          "## Rules", ""]
    L_ += [f"* **{r['id']}** {r['rule']}" for r in d["readiness_rules"]]
    L_ += ["", "## Rows", "",
           "| row | subsystem | v4 | v5 | v4 scheduler item | v5 scheduler item | category | waits on | removed | "
           "remaining (by category) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in d["rows"]:
        b = r["blocking_item"] or {}
        L_.append(f"| {r['row']} | {_c(r['key'])} | {r['state_v4']} | {r['execution_state']} | "
                  f"{_c(r['v4_blockers']['scheduler']['text'])} | {_c(b.get('id'))}: {_c(b.get('detail'))} | "
                  f"{_c(b.get('category'))} | {_c(r['waits_on'])} | {len(r['removed_blockers'])} | "
                  f"{_c(r['remaining_by_category'])} |")
    L_ += ["", "## Per-row detail", ""]
    for r in d["rows"]:
        L_ += [f"### Row {r['row']}: {r['key']} ({r['state_v4']} -> {r['execution_state']})", ""]
        if not r["blocking_item"]:
            L_ += [f"* {r['readiness_statement']}", ""]
            continue
        L_.append(f"* v4 scheduler item: {_c(r['v4_blockers']['scheduler']['text'])} (waits on "
                  f"{_c(r['v4_blockers']['waits_on'])})")
        b = r["blocking_item"]
        L_.append(f"* v5 scheduler item: **{b['id']}** [{b['category']}] {_c(b['detail'])} - {_c(b['reason'])}")
        for x in r["removed_blockers"]:
            what = x["v4_blocker"].get("id") or _c(x["v4_blocker"].get("text"))
            L_.append(f"* removed {x['v4_blocker']['kind']} {what}: {x['effect']} by {_c(x['removed_by'])}"
                      + (f" -> now waits on {', '.join(x['now_waits_on'])}" if x.get("now_waits_on") else ""))
        for a in r["answers_applied"]:
            L_.append(f"* answer {a['ref']} ({a['decision']} {_c(a.get('decision_code'))}; `{a['pointer']}` sha256 "
                      f"`{a['decision_json_sha256']}`): {a['effect']} - {_c(a['note'])}")
        for x in r["remaining_blockers"]:
            L_.append(f"* remaining [{x['category']}] {x['kind']} {x['id']}: {_c(x['state'])} - {_c(x['detail'])}")
        L_.append(f"* readiness: {r['readiness_statement']} ({r['state_rule']})")
        L_.append("")
    L_ += ["## Items", "", "| id | name | value | basis |", "|---|---|---|---|"]
    L_ += [f"| {i['id']} | {_c(i['name'])} | {i['value']} | {_c(i['basis'])} |" for i in d["items"]]
    L_ += ["", "## Owner answers applied", ""]
    L_ += [f"* {x['decision']} {x['question_id']} ({x['decision_code']}; `{x['decision_json']}` sha256 "
           f"`{x['decision_json_sha256']}`): {x['how_applied']}; re-derivation {x['rederivation']}; named persons "
           f"{x['named_persons']}" for x in d["owner_answers_applied"]]
    L_ += ["", "## Pins", ""] + [f"* `{p['path']}` `{p['sha256']}`" for p in d["pins"]]
    return "\n".join(L_) + "\n"


def outputs(doc=None) -> dict:
    doc = doc or build()
    return {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc)}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    outs = outputs()
    if "--check" in argv:
        stale = [p.name for p, s in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        if stale:
            print("M16 v5 outputs stale: " + ", ".join(stale))
            return 1
        print("M16 v5: current")
        return 0
    for p, s in outs.items():
        p.write_text(s, encoding="utf-8")
    d = json.loads(outs[OUT_JSON])
    print(f"wrote {_rel(OUT_JSON)} and {_rel(OUT_MD)}: {d['rollup']['execution_states_v5']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
