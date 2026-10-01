#!/usr/bin/env python3
"""M16 subsystem maturity matrix v4 (A9.6 sec. 16 refresh, lane A9_6_M16 / fo_a9_6_m16_refresh): deterministic builder.

A NEW version. M16 v3 (docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json, its builder and its
Markdown under docs/budgets/subsystem_maturity/) stays immutable and is pinned by sha256 here; v1 / v2 stay untouched.
No file is written under docs/budgets/subsystem_maturity/ (the immutable H2-7 v1 builder globs that folder).

For every v3 row (1-21) v4 records, after the A9.6 implementation batch:

  * what now exists for the row (framework / software / plan / RFQ / ledger / budget / requirement-matrix entries of the
    merged A9.6 deliverables, path + ids; every id is resolved at build time and a missing id raises);
  * what evidence exists: no measured or validated artifact is new (the batch produced frameworks only);
  * the single scheduler blocking item (owner row 141: one-blocker rule) and every contributing blocker (owner-question
    state v4 ids, P1 / P2 measurements, P3 inputs, P4 coupon tests, vendor quotations, TBD interface items);
  * owner / role and latest decision point (carried from v3, PROPOSED; M16-V3-Q-01 stays TBD_OWNER);
  * the readiness state, derived by derive_state() from the v2 scheduler rule accepted by the owner (row 141) plus the
    A9.6 sec. 16 guard: framework / software completeness never makes a physical row READY or VERIFIED; VERIFIED needs
    a cited measured hardware artifact; READY needs a named responsible engineer (row 140);
  * the ten A9.2 statuses verbatim (read from the pinned A9.2 decision; never promoted, never PASS);
  * a v3 -> v4 diff per row (state unchanged / changed, blocking item unchanged / re-pointed, reason).

Build order (data dependency; consolidated verification S-03): P4, XE, P1, P2, P3, MP, RFQ, RVM, owner-question
state v4, M16 v4. State v4 reads rvm_a9_v1.json (ids of RVM-ID-10 / RVM-ID-11, RVMQ-01, the lane-24 rows), the RVM
reads only the immutable state v3 snapshot, and M16 v4 reads both - so after any RVM change rebuild state v4 and
then M16 v4 (--check on each catches a stale downstream output).

stdlib only. Usage:
    python docs/experiments/hall_icp/integration/m16_v4/build_subsystem_maturity_v4.py          # write JSON + MD
    python docs/experiments/hall_icp/integration/m16_v4/build_subsystem_maturity_v4.py --check  # verify outputs
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


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


_spec = importlib.util.spec_from_file_location("m16_v4_rows", HERE / "m16_v4_rows.py")
SPEC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SPEC)

OUT_JSON = HERE / "subsystem_maturity_v4.json"
OUT_MD = HERE / "SUBSYSTEM_MATURITY_v4.md"
TEST_REL = "tests/test_m16_v4.py"

V3_REL = "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"
A92_REL = "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
ANS_REL = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
A96_REL = "docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json"
A96_MD_REL = "docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md"
A9_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"
V2_REL = "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json"

# immutable inputs pinned by sha256 (never governance files: lane / trigger registries, ledgers, runtime state)
PINS = {
    V3_REL: ("636cbd3318831f6f56e9833813c4d8c259aef7db3de1c6e503cccce14dade7e2", "M16 v3 (immutable; rows refreshed here)"),
    "docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py":
        ("ba163d09afe9596cdaed1e14fb0fea83aa317ee457674e82f00ef88299936327", "M16 v3 builder (immutable)"),
    "docs/budgets/subsystem_maturity/SUBSYSTEM_MATURITY_v3.md":
        ("16cb3b9218cc9428d0c0bf34cb884da18c48469bf48f120f7c1c840bee34427c", "M16 v3 companion (immutable)"),
    V2_REL: ("a82b1acd118b26e89edd4fa467bec778fa410470cca5eb6f684e6553eadaf23c",
             "M16 v2 (scheduler rule accepted by the owner, row 141)"),
    A9_REL: ("74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    ANS_REL: ("50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "147 owner answers (rows 140-144)"),
    "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json":
        ("7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "owner decisions A9.1"),
    A92_REL: ("e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03",
              "owner decisions A9.2 (the ten statuses, a9_10_statuses)"),
    "docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md":
        ("dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9", "owner decisions A9.2 (verbatim)"),
    "docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json":
        ("81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b", "owner decisions A9.3"),
    "docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json":
        ("b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d", "owner decisions A9.4"),
    "docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json":
        ("c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3", "owner decisions A9.5"),
    A96_REL: ("d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327", "owner directive A9.6"),
    A96_MD_REL: ("c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634", "owner directive A9.6 (verbatim; sec. 16)"),
    "docs/EVIDENCE.md": ("a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61",
                         "evidence rules (quantity types; CLAUDE.md rule 10)"),
}

# mutable deliverables: read at build time, identity and ids checked, never pinned (they are rebuilt by their lanes)
ARTIFACTS = {
    "P1": ("docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json", "id", "p1_icp_bench_v1",
           "fo_a9_6_p1_workflow_completion"),
    "P2": ("docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json", "id", "p2_impedance_prep_v1",
           "fo_a9_6_p2_framework_completion"),
    "P3": ("docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json", "id", "p3_coupled_thermal_v1",
           "fo_a9_6_p3_coupled_thermal"),
    "P4": ("docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json", "id", "p4_anode_materials_v1",
           "fo_a9_6_p4_anode_materials"),
    "MP": ("docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json", "id", "fo_a9_6_mass_power_integration_v2",
           "fo_a9_6_mass_power_integration"),
    "XE": ("docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json", "id", "xe_accounting_a9_v2",
           "fo_a9_6_xe_accounting"),
    "RFQ": ("docs/procurement/rfq_a9_v2/rfq_a9_v2.json", "id", "RFQ_A9_V2", "fo_a9_6_rfq_completion"),
    "RVM": ("docs/requirements/rvm_a9/rvm_a9_v1.json", "id", "rvm_a9_v1", "fo_a9_6_rvm"),
    "OQ4": ("docs/budgets/owner_decisions/owner_questions_state_v4.json", "id", "owner_questions_state_v4",
            "fo_a9_6_decision_propagation (+ register completion by fo_a9_6_m16_refresh)"),
    "ICD": ("schemas/interfaces/icp_neutralizer_icd_v1.json", "id", "icp_neutralizer_icd_v1", "A9-03 (verified)"),
    "BUS": ("docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json", "id",
            "bus_power_boundary_a9_v1", "A9-02 (verified)"),
    "H2A9": ("docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json", "id", "h2_a9_revisions_v1", "A9-07 (verified)"),
}
A96_LANES = ["P1", "P2", "P3", "P4", "MP", "XE", "RFQ", "RVM"]  # A9.6 deliverables whose m16_impact entries are consumed

STATES = ["READY", "RUNNING", "BLOCKED", "VERIFIED", "SUPERSEDED_FOR_PRIMARY_LINE"]  # exactly the v3 vocabulary
WAITS_ON = ["owner decision", "H-1 / C-1 measurement (wave H4, PLANNED_NOT_REGISTERED)",
            "procurement (wave H3, PLANNED_NOT_REGISTERED)", "design work outside every registered scope",
            "first-hand source verification"]  # exactly the v3 vocabulary
# A9.6 sec. 16 guard: only a measured hardware artifact can support VERIFIED of a physical row (docs/EVIDENCE.md
# quantity type 'measured'); none of these kinds ever can
NOT_EVIDENCE_KINDS = set(SPEC.IMPLEMENTATION_KINDS)
MEASURED_QUANTITY_TYPE = "measured"
NEVER_RUNNING_BLOCKERS = {"OWNER_QUESTION", "P1_MEASUREMENT", "P2_MEASUREMENT", "P4_EVIDENCE", "VENDOR_QUOTE"}

A92_ROW_KEYS = {11: ["C1 conventional reference"], 13: ["coupled H-1/ICP thermal closure"], 15: ["RF component ratings"],
                18: ["Hall->ICP architecture", "ICP electron-current capacity", "ICP RF power closure"],
                19: ["RF matching architecture", "RF component ratings", "ICP RF power closure"],
                20: ["316L flight anode", "final anode material"], 21: ["anode thermal closure"]}


class BuildError(RuntimeError):
    pass


# ----------------------------------------------------------------------------------------------------------------------
def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def container(doc, locator: str) -> list:
    """Resolve 'a.b' / 'a[].b' to a flat list of objects; raise on any miss."""
    cur = [doc]
    for part in locator.split("."):
        flat = part.endswith("[]")
        key = part[:-2] if flat else part
        nxt = []
        for c in cur:
            if not isinstance(c, dict) or key not in c:
                raise BuildError(f"container {locator!r}: step {key!r} not found")
            v = c[key]
            if flat:
                if not isinstance(v, list):
                    raise BuildError(f"container {locator!r}: {key!r} is not a list")
                nxt.extend(v)
            else:
                nxt.append(v)
        cur = nxt
    out = []
    for c in cur:
        if isinstance(c, dict) and c and all(isinstance(v, dict) for v in c.values()):
            out.extend({**v, "id": k} for k, v in c.items())  # id-keyed mapping (e.g. P4 'applications')
            continue
        if not isinstance(c, list):
            raise BuildError(f"container {locator!r} is not a list")
        out.extend(c)
    return out


def find(doc, locator: str, ident: str) -> dict:
    hits = [x for x in container(doc, locator) if isinstance(x, dict) and x.get("id") == ident]
    if len(hits) != 1:
        raise BuildError(f"id {ident!r} found {len(hits)} times in {locator!r}")
    return hits[0]


class Ctx:
    def __init__(self):
        self.pins = []
        for rel, (sha, role) in PINS.items():
            got = _sha(rel)
            if got != sha:
                raise BuildError(f"pinned input changed: {rel} sha256 {got} != {sha}")
            self.pins.append({"path": rel, "sha256": sha, "role": role})
        self.docs = {}
        for key, (rel, field, want, lane) in ARTIFACTS.items():
            d = _load(rel)
            if d.get(field) != want:
                raise BuildError(f"{rel}: identity {field}={d.get(field)!r} != {want!r}")
            self.docs[key] = d
        self.v3 = _load(V3_REL)
        self.v2 = _load(V2_REL)
        self.a92 = _load(A92_REL)["decisions"]["a9_10_statuses"]
        self.answers = {a["row"]: a for a in _load(ANS_REL)["answers"]}
        self.a96 = _load(A96_REL)
        self.oq4 = {}
        for r in self.docs["OQ4"]["rows"]:
            self.oq4.setdefault(r["id"], []).append(r)

    def path(self, key):
        return ARTIFACTS[key][0]


# ----------------------------------------------------------------------------------------------------------------------
# blocker resolution (fail closed: every id must exist and still be open)
# ----------------------------------------------------------------------------------------------------------------------
_TBD_PREFIXES = ("TBD", "TBD_AFTER_EVIDENCE", "TBD_AFTER_IMPEDANCE_MAP", "TBD_OWNER")


def resolve_blocker(ctx: Ctx, kind: str, key: str, ident: str) -> dict:
    if kind not in SPEC.BLOCKER_KINDS:
        raise BuildError(f"blocker kind {kind!r} not in the vocabulary")
    base = {"kind": kind, "id": ident, "artifact": ctx.path(key)}
    if kind == "OWNER_QUESTION":
        if key != "OQ4":
            raise BuildError(f"owner question {ident} must resolve in state v4")
        rows = ctx.oq4.get(ident, [])
        if len(rows) != 1:
            raise BuildError(f"owner question {ident} resolves to {len(rows)} rows in state v4")
        r = rows[0]
        if r["status"] != "TBD_OWNER":
            raise BuildError(f"owner question {ident} is {r['status']} in state v4, not an open blocker")
        return {**base, "locator": f"rows[id={ident}]", "state": "TBD_OWNER",
                "detail": " ".join(str(r.get("question", "")).split())[:220],
                "blocks": r.get("blocks"), "group": r.get("group")}
    if kind == "P1_MEASUREMENT":
        doc = ctx.docs["P1"]
        loc = "stage_map" if ident.startswith("P1-S") else "measurements"
        it = find(doc, loc, ident)
        return {**base, "locator": f"{loc}[id={ident}]", "state": "NOT_RUN (plan only; nothing measured)",
                "detail": str(it.get("name", ""))}
    if kind == "P2_MEASUREMENT":
        it = find(ctx.docs["P2"], "p2_outputs_later", ident)
        return {**base, "locator": f"p2_outputs_later[id={ident}]", "state": str(it.get("status")),
                "detail": str(it.get("what", ""))}
    if kind == "P3_INPUT":
        it = find(ctx.docs["P3"], "items", ident)
        v = it.get("value")
        if not (isinstance(v, str) and v.startswith(_TBD_PREFIXES)):
            raise BuildError(f"P3 {ident} is no longer TBD ({v!r}); refresh the blocker")
        return {**base, "locator": f"items[id={ident}]", "state": str(it.get("status")), "detail": str(it.get("name", ""))}
    if kind == "P4_EVIDENCE":
        it = find(ctx.docs["P4"], "test_plan.tests", ident)
        return {**base, "locator": f"test_plan.tests[id={ident}]", "state": "NOT_RUN (coupon test plan)",
                "detail": f"{it.get('criterion')}: populates {it.get('populates')}"}
    if kind == "VENDOR_QUOTE":
        doc = ctx.docs["RFQ"]
        for loc in (SPEC.RFQ_LI, SPEC.RFQ_OSI):
            hits = [x for x in container(doc, loc) if x.get("id") == ident]
            if hits:
                if len(hits) != 1:
                    raise BuildError(f"RFQ id {ident} duplicated")
                it = hits[0]
                if loc == SPEC.RFQ_OSI:
                    v = it.get("value")
                    txt = json.dumps(v) if not isinstance(v, str) else v
                    if "TBD" not in txt and "UNRESOLVED" not in txt:
                        raise BuildError(f"RFQ open specification item {ident} no longer TBD")
                    return {**base, "locator": f"{loc}[id={ident}]", "state": "OPEN_SPECIFICATION (supplier / evidence input)",
                            "detail": str(it.get("title", ""))}
                return {**base, "locator": f"{loc}[id={ident}]",
                        "state": f"QUOTATION_ONLY ({it.get('dispatch')}); no purchase order",
                        "detail": str(it.get("item", ""))[:200]}
        raise BuildError(f"RFQ id {ident} not found")
    if kind == "INTERFACE_TBD":
        it = find(ctx.docs["ICD"], "items", ident)
        if it.get("value") is not None:
            raise BuildError(f"ICD {ident} is no longer TBD")
        return {**base, "locator": f"items[id={ident}]", "state": str(it.get("status")), "detail": str(it.get("name", ""))}
    if kind == "BUS_ITEM_OPEN":
        it = find(ctx.docs["BUS"], "items", ident)
        if not str(it.get("status", "")).startswith("OPEN"):
            raise BuildError(f"bus item {ident} is no longer OPEN")
        return {**base, "locator": f"items[id={ident}]", "state": str(it.get("status")), "detail": str(it.get("name", ""))}
    if kind == "H2A9_ITEM_TBD":
        it = find(ctx.docs["H2A9"], "new_items", ident)
        if not str(it.get("value", "")).startswith("TBD"):
            raise BuildError(f"A9-07 {ident} is no longer TBD")
        return {**base, "locator": f"new_items[id={ident}]", "state": str(it.get("status")), "detail": str(it.get("name", ""))}
    raise BuildError(f"unhandled blocker kind {kind}")


# ----------------------------------------------------------------------------------------------------------------------
# readiness state (pure function; tested adversarially)
# ----------------------------------------------------------------------------------------------------------------------
def derive_state(rec: dict) -> tuple:
    """Return (state, rule id). v2 precedence VERIFIED > RUNNING > BLOCKED > READY, plus the A9.6 sec. 16 guard."""
    if rec.get("superseded_for_primary_line"):
        return "SUPERSEDED_FOR_PRIMARY_LINE", "R-M16V4-07"
    measured = [a for a in rec.get("measured_artifacts", [])
                if a.get("quantity_type") == MEASURED_QUANTITY_TYPE and a.get("kind") not in NOT_EVIDENCE_KINDS
                and not a.get("synthetic", True) and a.get("path_exists") is True]
    conds = rec.get("readiness_conditions", [])
    verified = (rec.get("interface_frozen") is True and bool(conds) and all(c.get("state") == "SATISFIED" for c in conds)
                and (not rec.get("physical", True) or bool(measured)))
    if verified:
        return "VERIFIED", "R-M16V4-02"
    blk = rec.get("blocking_item")
    wb = rec.get("worked_by")
    if blk is not None and wb is not None and wb.get("produces_every_missing_input") is True \
            and blk.get("kind") not in NEVER_RUNNING_BLOCKERS:
        return "RUNNING", "R-M16V4-03"
    if blk is not None or rec.get("contributing_open"):
        return "BLOCKED", "R-M16V4-04"
    if not rec.get("named_engineer"):
        return "BLOCKED", "R-M16V4-05"
    return "READY", "R-M16V4-05"


RULES = [
    {"id": "R-M16V4-01", "rule": "precedence VERIFIED > RUNNING > BLOCKED > READY; the first condition that holds sets the "
                                 "state (M16 v2 scheduler rule, accepted by the owner in row 141)"},
    {"id": "R-M16V4-02", "rule": "VERIFIED: every governing interface document of the row owner-frozen AND every referenced "
                                 "readiness condition SATISFIED (v2 rule) AND, for a physical row, at least one cited "
                                 "artifact of quantity type 'measured' on the project hardware (docs/EVIDENCE.md) that "
                                 "exists and is not synthetic (A9.6 sec. 16). Framework / software / plan / RFQ / ledger / "
                                 "budget / requirement-matrix entries never count"},
    {"id": "R-M16V4-03", "rule": "RUNNING: the single blocking item is worked by a registered lane whose scope produces "
                                 "EVERY missing input; never for an owner decision, a measurement, a coupon test or a "
                                 "vendor quotation (v2 owner_decision_items / non_lane_inputs guards)"},
    {"id": "R-M16V4-04", "rule": "BLOCKED: a single named blocking item exists (one-blocker rule, row 141) or contributing "
                                 "blockers remain open, and no registered lane works it"},
    {"id": "R-M16V4-05", "rule": "READY: no open blocking item AND a named responsible engineer (row 140); without a named "
                                 "engineer the row stays BLOCKED on M16-V3-Q-01"},
    {"id": "R-M16V4-06", "rule": "the ten A9.2 statuses are carried verbatim from the pinned A9.2 decision; this matrix never "
                                 "changes, promotes or turns any of them into PASS"},
    {"id": "R-M16V4-07", "rule": "SUPERSEDED_FOR_PRIMARY_LINE (v3 addition): a historical row that is not scheduled"},
    {"id": "R-M16V4-08", "rule": "blocking-item selection (PROPOSED, extends the v3 rule): the v3 item is carried unless an "
                                 "A9.6 deliverable implements the named item itself as a framework, in which case the row "
                                 "is re-pointed to the missing inputs of that framework (ids checked TBD at build time)"},
]


# ----------------------------------------------------------------------------------------------------------------------
def _implemented(ctx: Ctx, n: int, spec: list) -> list:
    out = []
    for key, loc, ids, kind, what in spec:
        if kind not in SPEC.IMPLEMENTATION_KINDS:
            raise BuildError(f"row {n}: implementation kind {kind!r} not in the vocabulary")
        if loc is None:
            for p in ids:
                if not (ROOT / p).is_file():
                    raise BuildError(f"row {n}: code module missing: {p}")
            out.append({"artifact": ctx.path(key), "kind": kind, "paths": list(ids), "what": what,
                        "counts_as_evidence": False})
            continue
        for i in ids:
            find(ctx.docs[key], loc, i)
        out.append({"artifact": ctx.path(key), "container": loc, "ids": list(ids), "kind": kind, "what": what,
                    "counts_as_evidence": False})
    return out


def _lane_impacts(ctx: Ctx) -> dict:
    touch = {}
    for key in A96_LANES:
        for e in ctx.docs[key].get("m16_impact", []):
            n = e.get("m16_row", e.get("row"))
            if not isinstance(n, int) or not 1 <= n <= 21:
                raise BuildError(f"{key} m16_impact entry without a valid row: {e}")
            if "rvm_rows" in e:
                txt = "requirement rows " + ", ".join(e["rvm_rows"]) + " (status per configuration in rvm_requirement_status)"
            else:
                txt = next((str(e[k]) for k in ("how_touched", "how", "impact", "note") if k in e), None)
            if txt is None:
                raise BuildError(f"{key} m16_impact entry for row {n} has no description")
            ch = next((str(e[k]) for k in ("readiness_change", "state_change", "proposed_change", "cell_edit") if k in e), None)
            touch.setdefault(n, []).append({"lane": ARTIFACTS[key][3], "artifact": ctx.path(key), "how": txt,
                                            "stated_readiness_change": ch})
    return touch


def _rvm_status(ctx: Ctx) -> dict:
    rows = {r["id"]: r for r in ctx.docs["RVM"]["rows"]}
    out = {}
    for e in ctx.docs["RVM"].get("m16_impact", []):
        out[e["m16_row"]] = [{"rvm_row": i, "title": rows[i]["title"],
                              "status": {c: v["status"] for c, v in rows[i]["configurations"].items()}}
                             for i in e["rvm_rows"]]
    return out


def rvm_register_reconciliation(ctx: Ctx) -> dict:
    """Post-v4 reconciliation (consolidated verification S-01): the RVM is built before owner-question state v4 and
    cannot pin it (v4 reads the RVM; a pin would be circular), so the RVM carries every open reading with the status the
    owner register gives it and names v4 as its current register. Here, after both exist, every RVM open reading is
    compared with its v4 row; any disagreement (or a reading absent from v4) raises - the RVM must then be rebuilt with
    the current classification, never silently left stale."""
    v4 = {r["id"]: r for r in ctx.docs["OQ4"]["rows"]}
    rows, bad = [], []
    for row in ctx.docs["RVM"]["rows"]:
        for o in row.get("open_readings", []):
            r4 = v4.get(o["id"])
            st4 = r4["status"] if r4 else None
            agree = st4 is not None and st4 == o["status"]
            rows.append({"rvm_row": row["id"], "id": o["id"], "rvm_status": o["status"], "state_v4_status": st4,
                         "agrees": agree})
            if not agree:
                bad.append(f"{row['id']} {o['id']}: RVM {o['status']!r} vs state v4 {st4!r}")
    if bad:
        raise BuildError("RVM open readings disagree with owner-question state v4 (rebuild the RVM): " + "; ".join(bad))
    return {"rule": "every RVM open reading has the same status as its row in owner_questions_state_v4 (S-01); "
                    "checked after both are built (build order ... RVM, state v4, M16 v4)",
            "n_readings": len(rows), "all_agree": True, "rows": rows}


def build() -> dict:
    ctx = Ctx()
    if sorted(SPEC.ROWS) != [r["row"] for r in ctx.v3["rows"]]:
        raise BuildError("row specifications do not cover exactly the v3 rows")
    touch = _lane_impacts(ctx)
    rvm = _rvm_status(ctx)
    icd_status = str(ctx.docs["ICD"].get("status"))
    if "FROZEN" in icd_status.upper():
        raise BuildError("the ICD is now frozen: review R-M16V4-02 inputs before rebuilding")
    a92_all = dict(ctx.a92)
    if len(a92_all) != 10:
        raise BuildError(f"A9.2 a9_10_statuses has {len(a92_all)} entries, expected 10")
    rows, diff = [], []
    for r3 in ctx.v3["rows"]:
        n = r3["row"]
        spec = SPEC.ROWS[n]
        a3 = r3["a9_refresh"]
        state_v3 = a3["execution_state"]
        superseded = state_v3 == "SUPERSEDED_FOR_PRIMARY_LINE"
        # scheduler blocking item
        if superseded:
            blk, blk_changed, reason_blk = None, False, "historical row, not scheduled"
        elif spec["blocker"] is None:
            b3 = a3["blocking_item"]
            blk = {"carried_from_v3": True, "text": b3["text"], "source": b3["source"], "ref": b3.get("ref"),
                   "kind": "V3_CARRIED"}
            if "v3_check" in spec:
                kind, key, ids = spec["v3_check"]
                blk["still_open_check"] = [resolve_blocker(ctx, kind, key, i) for i in ids]
            blk_changed, reason_blk = False, "v3 blocking item carried: no A9.6 deliverable produces the missing input"
        else:
            b = spec["blocker"]
            kind, key, ids = b["ids"]
            blk = {"carried_from_v3": False, "text": b["text"], "source": ctx.path(b["source"]), "kind": kind,
                   "items": [resolve_blocker(ctx, kind, key, i) for i in ids],
                   "v3_item": {"text": a3["blocking_item"]["text"], "source": a3["blocking_item"]["source"]}}
            if "also_open" in b:
                k2, key2, ids2 = b["also_open"]
                blk["also_open"] = [resolve_blocker(ctx, k2, key2, i) for i in ids2]
            blk_changed, reason_blk = True, b["reason"]
        waits = None if superseded else (spec["blocker"] or {}).get("waits_on", a3.get("waits_on"))
        if waits is not None and waits not in WAITS_ON:
            raise BuildError(f"row {n}: waits_on {waits!r} not in the vocabulary")
        contributing = [resolve_blocker(ctx, k, key, i) for k, key, i in spec["contributing"]]
        owner = dict(a3["owner"])
        owner["owner_question"] = "M16-V3-Q-01 (TBD_OWNER in owner_questions_state_v4)"
        rec = {"superseded_for_primary_line": superseded, "physical": True, "interface_frozen": False,
               "readiness_conditions": [], "measured_artifacts": [], "worked_by": None,
               "blocking_item": blk, "contributing_open": contributing, "named_engineer": owner.get("named_engineer")}
        state, rule = derive_state(rec)
        if state not in STATES:
            raise BuildError(f"row {n}: state {state} outside the vocabulary")
        a92 = {k: ctx.a92[k] for k in A92_ROW_KEYS.get(n, [])}
        v3_a92 = (r3.get("a9_2") or {}).get("statuses", {})
        if a92 != v3_a92:
            raise BuildError(f"row {n}: A9.2 statuses differ from v3 ({a92} vs {v3_a92})")
        row = {
            "row": n, "key": r3["key"], "name": r3["name"], "group": r3["group"], "flag": r3["flag"],
            "physical_item": True,
            "v3_ref": f"{V3_REL}#/rows/{n - 1}",
            "a9_6_implemented": _implemented(ctx, n, spec["implemented"]),
            "a9_6_lanes": touch.get(n, []),
            "evidence": {"new_measured_or_validated_artifacts": [],
                         "statement": "none new: the A9.6 implementation batch produced frameworks, software, plans, RFQ "
                                      "packages, ledgers and budgets only; nothing was measured on project hardware",
                         "carried": f"{V3_REL}#/rows/{n - 1} (v3 evidence cells / v2 cells by reference)"},
            "interface": {"frozen": False, "basis": f"no governing interface document is owner-frozen (ICD "
                                                    f"{ARTIFACTS['ICD'][0]} status {icd_status})"},
            "readiness_conditions": {"satisfied": [], "note": "no S1a / S1 readiness condition newly SATISFIED by the "
                                                             "A9.6 batch (no hardware run)"},
            "blocking_item": blk,
            "contributing_blockers": contributing,
            "worked_by": None,
            "not_worked_reason": None if superseded else (
                "every A9.6 implementation lane touching the row is a complete framework deliverable; none produces the "
                "missing input (owner decision, measurement, quotation, design drawing or source verification); "
                "fo_a9_6_consolidated_verification verifies and produces no input"),
            "waits_on": waits,
            "latest_decision_point": a3.get("latest_decision_point"),
            "latest_decision_point_status": "PROPOSED (carried from v3; owner question M16-V3-Q-01 TBD_OWNER)",
            "a7_category": a3.get("a7_category"),
            "owner": owner,
            "a9_2_statuses": a92,
            "rvm_requirement_status": rvm.get(n, []),
            "execution_state": state, "state_rule": rule,
        }
        rows.append(row)
        diff.append({"row": n, "key": r3["key"], "state_v3": state_v3, "state_v4": state,
                     "state_changed": state != state_v3, "blocking_item_changed": blk_changed,
                     "reason": ("state unchanged: " if state == state_v3 else "STATE CHANGED: ") + rule + "; " + reason_blk})
    # roll-ups and consistency
    carried_a92 = {}
    for r in rows:
        carried_a92.update(r["a9_2_statuses"])
    if carried_a92 != a92_all:
        raise BuildError("the ten A9.2 statuses are not all carried by the rows")
    fixed = ctx.a96["summary"]["fixed_statuses"]
    a96_map = {"316L_FLIGHT_ANODE": "316L flight anode", "FINAL_ANODE_MATERIAL": "final anode material",
               "ANODE_THERMAL_CLOSURE": "anode thermal closure", "ICP_COUPLED_THERMAL": "coupled H-1/ICP thermal closure",
               "RF_COMPONENT_RATINGS": "RF component ratings"}
    for k, v in fixed.items():
        if a92_all[a96_map[k]] != v:
            raise BuildError(f"A9.6 fixed status {k}={v} disagrees with A9.2")
    states, waits_c = {}, {}
    for r in rows:
        states[r["execution_state"]] = states.get(r["execution_state"], 0) + 1
        if r["waits_on"]:
            waits_c[r["waits_on"]] = waits_c.get(r["waits_on"], 0) + 1
    oq_ids = sorted({b["id"] for r in rows for b in r["contributing_blockers"] if b["kind"] == "OWNER_QUESTION"})
    m16q = ctx.oq4.get("M16-V3-Q-01", [])
    if len(m16q) != 1 or m16q[0]["status"] != "TBD_OWNER":
        raise BuildError("M16-V3-Q-01 must be exactly one TBD_OWNER row in state v4")
    n_changed = sum(d["state_changed"] for d in diff)
    n_repointed = sum(d["blocking_item_changed"] for d in diff)
    n_blockers = sum(len(r["contributing_blockers"]) + (1 if r["blocking_item"] else 0) for r in rows)
    item = lambda i, name, v, units, basis: {
        "id": i, "name": name, "value": v, "units": units, "basis": basis, "source": f"{_rel(OUT_JSON)} rows",
        "evidence_class": "derived (bookkeeping count; no physical quantity)", "status": "COMPUTED",
        "freeze_point": "rebuilt whenever a pinned input or a referenced deliverable changes"}
    items = [
        item("M16V4-IT-01", "rows in M16 v4", len(rows), "count", "one row per v3 row (1-21)"),
        item("M16V4-IT-02", "rows BLOCKED", states.get("BLOCKED", 0), "count", "derive_state() over every row"),
        item("M16V4-IT-03", "rows READY", states.get("READY", 0), "count", "R-M16V4-05"),
        item("M16V4-IT-04", "rows VERIFIED", states.get("VERIFIED", 0), "count", "R-M16V4-02 (no measured artifact exists)"),
        item("M16V4-IT-05", "rows RUNNING", states.get("RUNNING", 0), "count", "R-M16V4-03"),
        item("M16V4-IT-06", "rows whose state changed v3 -> v4", n_changed, "count", "diff_v3_v4"),
        item("M16V4-IT-07", "rows whose scheduler blocking item was re-pointed", n_repointed, "count", "R-M16V4-08"),
        item("M16V4-IT-08", "blocking entries (scheduler + contributing) resolved at build time", n_blockers, "count",
             "resolve_blocker()"),
        item("M16V4-IT-09", "distinct owner-question v4 ids used as blockers", len(oq_ids), "count",
             "each resolves to one TBD_OWNER row"),
        item("M16V4-IT-10", "A9.2 statuses carried verbatim", len(carried_a92), "count", "R-M16V4-06"),
        item("M16V4-IT-11", "new measured / validated artifacts", 0, "count", "A9.6 batch: frameworks only"),
    ]
    return {
        "schema": "subsystem_maturity_matrix_v4", "id": "subsystem_maturity_v4",
        "lane": "A9_6_M16 (fo_a9_6_m16_refresh)", "directive": f"{A96_MD_REL} sec. 16",
        "status": "DRAFT_IMPLEMENTATION_FIRST_PENDING_CONSOLIDATED_VERIFICATION",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "supersedes_for_use": {"path": V3_REL, "sha256": PINS[V3_REL][0], "note": "v3 (and v1 / v2) stay byte-identical"},
        "generated_by": _rel(Path(__file__).resolve()), "rows_module": _rel(HERE / "m16_v4_rows.py"),
        "companion_document": _rel(OUT_MD), "test": TEST_REL,
        "file_location": "docs/experiments/hall_icp/integration/m16_v4/ (nothing under docs/budgets/subsystem_maturity/: "
                         "the immutable H2-7 v1 builder globs that folder; OQ-A910-04 DERIVED in state v4)",
        "what_it_is_not": ["not a performance prediction", "not an architecture selection (no winner)",
                           "not a requirement verdict (see the RVM)", "not a change to v1 / v2 / v3",
                           "not an owner decision: blocking-item selection, roles and latest decision points are PROPOSED",
                           "software / framework completeness is not physical readiness"],
        "state_vocabulary": STATES, "waits_on_vocabulary": WAITS_ON,
        "implementation_kinds": SPEC.IMPLEMENTATION_KINDS, "blocker_kinds": SPEC.BLOCKER_KINDS,
        "readiness_rules": RULES,
        "scheduler_rule_source": {"path": V2_REL, "sha256": PINS[V2_REL][0], "scheduler_rule": ctx.v2["scheduler_rule"],
                                  "owner_acceptance": {"row": 141, "verbatim": ctx.answers[141]["owner_answer_verbatim"]}},
        "owner_rule": {"row": 140, "verbatim": ctx.answers[140]["owner_answer_verbatim"]},
        "a9_2_statuses": {"source": f"{A92_REL} decisions.a9_10_statuses", "sha256": PINS[A92_REL][0], "statuses": a92_all},
        "pins": ctx.pins,
        "referenced_not_pinned": {"rule": "mutable deliverables: read at build time, identity and every cited id checked (a "
                                          "missing or no-longer-open id raises); never sha-pinned; governance files "
                                          "(lane / trigger registries, ledgers, runtime state) are neither read nor pinned",
                                  "artifacts": [{"key": k, "path": v[0], "identity": v[2], "lane": v[3]}
                                                for k, v in ARTIFACTS.items()]},
        "rows": rows,
        "diff_v3_v4": diff,
        "rollup": {"execution_states": dict(sorted(states.items())), "waits_on": dict(sorted(waits_c.items()))},
        "owner_question_ids_used": oq_ids,
        "rvm_register_reconciliation": rvm_register_reconciliation(ctx),
        "items": items,
        "interface_demands": [
            {"id": "M16V4-ID-01", "direction": "consumes", "counterpart": V3_REL,
             "quantity": "every v3 row (state, blocking item, waits_on, latest decision point, owner, A9.2 statuses)",
             "status": "APPLIED (pinned)"},
            {"id": "M16V4-ID-02", "direction": "consumes", "counterpart": "m16_impact of the A9.6 deliverables P1, P2, P3, "
             "P4, mass/power v2, Xe accounting v2, RFQ v2, RVM", "quantity": "per-row touches; every entry lands in "
             "rows[].a9_6_lanes; none changes a readiness state", "status": "APPLIED"},
            {"id": "M16V4-ID-03", "direction": "consumes", "counterpart": "docs/requirements/rvm_a9/rvm_a9_v1.json "
             "interface_demands[id=RVM-ID-08]", "quantity": "requirement status per M16 row (rows[].rvm_requirement_status)",
             "status": "APPLIED"},
            {"id": "M16V4-ID-04", "direction": "consumes", "counterpart": "docs/experiments/hall_icp/p4_anode_materials/"
             "p4_anode_materials_v1.json interface_demands[id=ID-11]", "quantity": "rows 18, 20, 21: framework implemented; "
             "readiness unchanged", "status": "APPLIED"},
            {"id": "M16V4-ID-05", "direction": "consumes", "counterpart": "docs/budgets/owner_decisions/"
             "owner_questions_state_v4.json (IF-V4-08)", "quantity": "owner-question ids used as blockers; each must be one "
             "TBD_OWNER row", "status": "APPLIED"},
            {"id": "M16V4-ID-06", "direction": "provides", "counterpart": "fo_a9_6_consolidated_verification (A9.6 sec. 18)",
             "quantity": "readiness rules R-M16V4-01..08, derive_state(), per-row blockers and the v3 -> v4 diff",
             "status": "OFFERED"},
            {"id": "M16V4-ID-07", "direction": "provides", "counterpart": "owner (M16-V3-Q-01)",
             "quantity": "PROPOSED blocking items, roles and latest decision points for acceptance; named engineers",
             "status": "AWAITING_OWNER_DECISION"},
        ],
        "owner_answers_applied": [
            {"id": "owner row 140", "how_applied": "R-M16V4-05: READY needs a named responsible engineer; functional roles "
             "carried from v3; accountable owner carried"},
            {"id": "owner row 141", "how_applied": "R-M16V4-01..04: scheduler rule, one-blocker rule, non-lane-input guard"},
            {"id": "owner row 142", "how_applied": "A9.6 lanes added per row (rows[].a9_6_lanes) without rewriting H2 / A9 "
             "provenance (v3 carried by pointer)"},
            {"id": "owner row 144", "how_applied": "every blocker keeps a latest decision point (carried from v3, PROPOSED)"},
            {"id": "A9.2 a9_10_statuses", "how_applied": "R-M16V4-06: ten statuses verbatim; none promoted"},
            {"id": "A9.6 sec. 16", "how_applied": "R-M16V4-02 guard: no physical row READY / VERIFIED from software / "
             "framework completeness; physical ICP, anode, coupled thermal and RF ratings stay at their A9.2 statuses"},
            {"id": "A9.6 sec. 7", "how_applied": "no open owner question answered; blockers cite TBD_OWNER rows"},
        ],
        "open_owner_questions": [],
        "open_owner_questions_note": "no new owner question: M16-V3-Q-01 (TBD_OWNER, state v4) is carried and covers "
                                     "acceptance of the v4 blocking-item selection, roles and latest decision points",
        "historical_reuse": [{"path": p["path"], "sha256": p["sha256"], "use": p["role"]} for p in ctx.pins
                             if p["path"].startswith(("docs/experiments/hall_icp/integration/m16_v3",
                                                      "docs/budgets/subsystem_maturity"))],
        "m16_impact": {"rows_state_changed": n_changed, "rows_blocking_item_repointed": n_repointed,
                       "summary": f"{states.get('BLOCKED', 0)} BLOCKED, {states.get('SUPERSEDED_FOR_PRIMARY_LINE', 0)} "
                                  f"SUPERSEDED_FOR_PRIMARY_LINE, 0 READY, 0 VERIFIED; no state change v3 -> v4"
                                  if n_changed == 0 else "state changes present: see diff_v3_v4"},
        "compliance": ["v1 / v2 / v3 unchanged (v3 pinned)", "every cited id resolved at build time; no-longer-open ids raise",
                       "no PASS; no winner; no prediction", "A9.2 statuses verbatim",
                       "no file under docs/budgets/subsystem_maturity/"],
    }


# ----------------------------------------------------------------------------------------------------------------------
def _c(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return " ".join(str(v).split()).replace("|", "\\|")


def render_md(d: dict) -> str:
    L = ["# M16 subsystem maturity matrix v4 (A9.6 sec. 16 refresh)", "",
         f"<!-- GENERATED by {d['generated_by']} from subsystem_maturity_v4.json; do not edit by hand -->", "",
         f"Status **{d['status']}**; A9 stays **{d['a9_status']}**. Supersedes for use `{d['supersedes_for_use']['path']}` "
         f"(sha256 `{d['supersedes_for_use']['sha256']}`), which stays unchanged.", "",
         "Software / framework completeness is not physical readiness: no physical row becomes READY or VERIFIED without "
         "a cited measured hardware artifact (A9.6 sec. 16). No PASS, no winner, no prediction.", "",
         f"Roll-up: {_c(d['rollup'])}. {d['m16_impact']['summary']}.", "",
         "## Readiness rules", ""]
    L += [f"* **{r['id']}** {r['rule']}" for r in d["readiness_rules"]]
    L += ["", "## Rows", "",
          "| row | subsystem | v4 state | scheduler blocking item | waits on | latest decision point (PROPOSED) | owner (role) |",
          "|---|---|---|---|---|---|---|"]
    for r in d["rows"]:
        b = r["blocking_item"] or {}
        L.append(f"| {r['row']} | {_c(r['key'])} | {r['execution_state']} | {_c(b.get('text'))} | {_c(r['waits_on'])} | "
                 f"{_c(r['latest_decision_point'])} | {_c(r['owner'].get('functional_role'))} |")
    L += ["", "## Diff v3 -> v4", "", "| row | key | v3 | v4 | state changed | blocker changed | reason |",
          "|---|---|---|---|---|---|---|"]
    L += [f"| {x['row']} | {x['key']} | {x['state_v3']} | {x['state_v4']} | {x['state_changed']} | "
          f"{x['blocking_item_changed']} | {_c(x['reason'])} |" for x in d["diff_v3_v4"]]
    L += ["", "## A9.2 statuses (verbatim, never PASS)", ""]
    L += [f"* {k}: **{v}**" for k, v in d["a9_2_statuses"]["statuses"].items()]
    L += ["", "## Per-row detail", ""]
    for r in d["rows"]:
        L += [f"### Row {r['row']}: {r['key']} ({r['execution_state']})", ""]
        for im in r["a9_6_implemented"]:
            where = ", ".join(im.get("ids") or im.get("paths"))
            L.append(f"* now exists [{im['kind']}]: `{im['artifact']}` {where} - {im['what']}")
        L.append(f"* evidence: {r['evidence']['statement']}")
        if r["a9_2_statuses"]:
            L.append("* A9.2 statuses: " + ", ".join(f"{k} = {v}" for k, v in r["a9_2_statuses"].items()))
        if r["blocking_item"] and not r["blocking_item"].get("carried_from_v3"):
            ids = ", ".join(x["id"] for x in r["blocking_item"]["items"])
            L.append(f"* blocking item RE-POINTED ({ids}); v3 item: {_c(r['blocking_item']['v3_item']['text'])}")
        if r["contributing_blockers"]:
            L.append("* contributing blockers: " + "; ".join(f"{b['kind']} {b['id']} ({_c(b['state'])})"
                                                            for b in r["contributing_blockers"]))
        if r["rvm_requirement_status"]:
            L.append("* RVM: " + "; ".join(f"{x['rvm_row']} {_c(x['status'])}" for x in r["rvm_requirement_status"]))
        for t in r["a9_6_lanes"]:
            L.append(f"* lane {t['lane']}: {_c(t['how'])}")
        L.append("")
    L += ["## Items", "", "| id | name | value | units | basis | evidence class | status |", "|---|---|---|---|---|---|---|"]
    L += [f"| {i['id']} | {_c(i['name'])} | {i['value']} | {i['units']} | {_c(i['basis'])} | {_c(i['evidence_class'])} | "
          f"{i['status']} |" for i in d["items"]]
    L += ["", "## Interface demands", "", "| id | direction | counterpart | quantity | status |", "|---|---|---|---|---|"]
    L += [f"| {x['id']} | {x['direction']} | {_c(x['counterpart'])} | {_c(x['quantity'])} | {x['status']} |"
          for x in d["interface_demands"]]
    L += ["", "## Owner answers applied", ""] + [f"* {x['id']}: {x['how_applied']}" for x in d["owner_answers_applied"]]
    L += ["", "## Open owner questions", "", d["open_owner_questions_note"], "",
          "Owner-question v4 ids used as blockers: " + ", ".join(d["owner_question_ids_used"]) + ".", "",
          "## Historical reuse", ""] + [f"* `{x['path']}` sha256 `{x['sha256']}` ({x['use']})" for x in d["historical_reuse"]]
    L += ["", "## Pins", ""] + [f"* `{p['path']}` `{p['sha256']}`" for p in d["pins"]]
    return "\n".join(L) + "\n"


def outputs(doc=None) -> dict:
    doc = doc or build()
    return {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc)}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    outs = outputs()
    if "--check" in argv:
        stale = [p.name for p, s in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        if stale:
            print("M16 v4 outputs stale: " + ", ".join(stale))
            return 1
        print("M16 v4: current")
        return 0
    for p, s in outs.items():
        p.write_text(s, encoding="utf-8")
    d = json.loads(outs[OUT_JSON])
    print(f"wrote {_rel(OUT_JSON)} and {_rel(OUT_MD)}: {d['rollup']['execution_states']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
