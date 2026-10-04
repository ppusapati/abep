"""Single flight configuration (owner decisions A9.19 / A9.20, 2026-10-01): the generated deliverables of the remaining
design chain evaluate exactly one flight configuration, ``hall_icp_neutralizer`` (one Hall + one RF/ICP neutralizer for
air and Xe, two supply modes, Xe contingency / emergency, no hollow cathode). ``hall_c1_reference`` may appear only as
labelled retired-flight history, as the ground / laboratory reference (C1 = GROUND_ONLY_LAB_REFERENCE, A9.20), or inside
quoted / explanatory text.

Scanned: mass/power v3, Xe accounting v3, the H-1 freeze candidate, every design_synthesis (F1-F8) and every
architecture_comparison JSON. The scan fails on

  * a configuration list / map (``configurations``, ``configs``, ``ranking``, ``evaluations_by_configuration``, ...) that
    carries ``hall_c1_reference`` as an evaluated member outside a history / ground-reference section;
  * a status count table (``*status_counts*``) with a ``hall_c1_reference`` column outside such a section;
  * an evaluated record (objective table, roll-up, scenario, ledger line) whose ``configuration`` is
    ``hall_c1_reference`` outside such a section, unless it is a GROUND_TEST record labelled as the ground reference.

One A9-02 input predates A9.19 and is sha-pinned by many deliverables outside this chain
(``bus_power_boundary_a9_v1.json``, dated 2026-09-29); it is accepted only while it stays byte-identical to that
pinned pre-A9.19 version (any rebuild must pass the scan).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FLIGHT = "hall_icp_neutralizer"
RETIRED = "hall_c1_reference"

SCAN_ROOTS = ("docs/budgets/mass_power_a9_v3", "docs/budgets/mass_power_a9_v4", "docs/budgets/xe_accounting_a9_v3", "docs/hardware/h1_freeze_candidate",
              "docs/design_synthesis", "docs/architecture_comparison")
REQUIRED = ("docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json",
            "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json",
            "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
            "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json",
            "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json",
            "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json",
            "docs/design_synthesis/f4_plenum/f4_plenum_chains_v1.json",
            "docs/design_synthesis/f4_plenum/f4_plenum_transients_v1.json",
            "docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json",
            "docs/design_synthesis/f7_f8_optimizer/f7_upstream_pareto_v1.json",
            "docs/design_synthesis/f7_f8_optimizer/f8_robust_candidates_v1.json",
            # A9.22 G8: the current A9-02 boundary (flight configuration only; C1 as ground-reference metadata)
            "docs/architecture_comparison/power_boundary_a9_v2/bus_power_boundary_a9_v2.json",
            # A9.24 AFI-01: the current mass / power successor of v3
            "docs/budgets/mass_power_a9_v4/mass_power_a9_v4.json")
# pre-A9.19 A9-02 boundary v1 (2026-09-29), immutable history (A9.22 G8). After the stage-2 migration the live chain
# (P1, P2, mass/power v3, Xe v3, RFQ v3, M16 v5, F7/F8, RVM, F9) cites bus_power_boundary_a9_v2; v1 stays sha-pinned by
# the immutable deliverables (RFQ v1/v2, M16 v3/v4, mass/Xe v1/v2, H2 revisions, A9-10, core integration, owner brief)
# and is cited by the live chain only where v1 is the correct reference: C1 ground-reference cells (RVM, RFQ v3 C1
# rows), the retired C1 power configuration and the carried v2 items (mass/power v3), P1 historical reuse, Xe v3
# source_v2. It is accepted only while byte-identical to this pinned version.
PINNED_PRE_A9_19 = {"docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json":
                    "9f6e074cc2cdd1e2445d00a14eec04b4cc33f239655f8619a789e7ae863c43e6"}

# a key containing one of these marks a labelled history / ground-reference section
CONTEXT = re.compile(r"history|retired|pre_a9_19|as_carried|ground_reference|ground_lab|ground_article|_v2$|^v2_")
CONFIG_KEYS = re.compile(r"(^|_)(configurations?|configs|ranking|rankings|evaluations_by_configuration|objectives?"
                         r"|rollups?|status_counts)($|_)")
LABEL = re.compile(r"^(RETIRED|GROUND_ONLY|GROUND-ONLY|HISTORY)")


def _is_retired(x) -> bool:
    """A value that NAMES the retired configuration (whitespace-insensitive), as opposed to quoted text mentioning it."""
    return isinstance(x, str) and x.strip() == RETIRED


def _scan(doc) -> list[str]:
    bad: list[str] = []

    def walk(o, path: tuple, ctx: bool):
        if isinstance(o, dict):
            ground = o.get("ledger") == "GROUND_TEST" and any(
                "role" in k and isinstance(v, str) and "GROUND_ONLY" in v for k, v in o.items())
            if not ctx and _is_retired(o.get("configuration")) and not ground:
                bad.append("/".join(path) + ": evaluated record with configuration hall_c1_reference")
            for k, v in o.items():
                kctx = ctx or bool(CONTEXT.search(k))
                if RETIRED in k and not kctx:
                    labelled = isinstance(v, str) and bool(LABEL.match(v))
                    if not labelled:
                        bad.append("/".join(path + (k,)) + ": hall_c1_reference evaluated as a map member")
                if CONFIG_KEYS.search(k) and not kctx and isinstance(v, list) and any(_is_retired(x) for x in v):
                    bad.append("/".join(path + (k,)) + ": hall_c1_reference in a configuration list")
                # any other field whose value names the retired configuration (config, winner, selected, ...)
                if k != "configuration" and not kctx and not ground and _is_retired(v):
                    bad.append("/".join(path + (k,)) + ": hall_c1_reference as an evaluated value")
                walk(v, path + (k,), kctx)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + (f"[{i}]",), ctx)
            if not ctx and any(_is_retired(x) for x in o):
                bad.append("/".join(path) + ": hall_c1_reference as a list member")

    walk(doc, (), False)
    return bad


def _targets() -> list[Path]:
    out = []
    for root in SCAN_ROOTS:
        out += sorted((REPO / root).rglob("*.json"))
    return out


def test_scan_covers_the_chain():
    rels = {p.relative_to(REPO).as_posix() for p in _targets()}
    for r in REQUIRED + tuple(PINNED_PRE_A9_19):
        assert r in rels, r


@pytest.mark.parametrize("path", _targets(), ids=lambda p: p.relative_to(REPO).as_posix())
def test_only_hall_icp_neutralizer_is_evaluated(path: Path):
    rel = path.relative_to(REPO).as_posix()
    if rel in PINNED_PRE_A9_19:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha == PINNED_PRE_A9_19[rel]:
            assert json.loads(path.read_text(encoding="utf-8"))["date"] < "2026-10-01"     # predates A9.19
            return
    bad = _scan(json.loads(path.read_text(encoding="utf-8")))
    assert not bad, f"{rel}: " + "; ".join(bad[:10])


def test_flight_configuration_sets_are_single():
    mp = json.loads((REPO / REQUIRED[0]).read_text(encoding="utf-8"))
    assert set(mp["lines"]) == {FLIGHT}
    assert [r["configuration"] for r in mp["rollups"]] == [FLIGHT]
    assert [r["configuration"] for r in mp["flight_rollup_vs_40kg"]] == [FLIGHT]
    assert set(mp["power"]["configurations"]) == {FLIGHT}
    xe = json.loads((REPO / REQUIRED[1]).read_text(encoding="utf-8"))
    assert xe["propellant_policy"]["architecture"]["flight_configuration"].startswith(FLIGHT)
    assert {s["configuration"] for s in xe["scenarios"] if s["id"].split("-")[1] == "FL"} == {FLIGHT}
    f7 = json.loads((REPO / "docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json").read_text("utf-8"))
    assert set(f7["system_evaluation"]["evaluations_by_configuration"]) == {FLIGHT}
    assert set(f7["system_evaluation"]["ranking"]) == {FLIGHT}
    assert f7["system_evaluation_exemplar"]["configuration"] == FLIGHT
    for g in ("gates_before", "gates_after"):
        assert set(f7["robust"][g]["rvm_status_counts"]) == {FLIGHT}


@pytest.mark.parametrize("doc", [
    {"configurations": [RETIRED, FLIGHT]},
    {"configurations": {RETIRED: {"installed_slots": []}, FLIGHT: {}}},
    {"rvm_status_counts": {RETIRED: {"PASS": 0}}},
    {"rollups": [{"configuration": RETIRED, "dry_known_kg": 1.0}]},
    {"ranking": {RETIRED: "REFUSED"}},
    {"items": [{"applies_to": {"configs": [RETIRED], "ledgers": ["FLIGHT"]}}]},
    {"ledger_lines": [{"configuration": RETIRED, "ledger": "FLIGHT", "role": "GROUND_ONLY"}]},
    # review fix: entries the earlier scan missed
    {"winner": RETIRED},
    {"rollups": [{"config": RETIRED, "dry_known_kg": 1.0}]},
    {"configuration_id": RETIRED},
    {"hall_c1_reference_dry_kg": 3.0},
    {"lines": {RETIRED + " ": []}},
    {"configurations": [RETIRED + " "]},
    {"rollups": [{"configuration": " " + RETIRED, "dry_known_kg": 1.0}]},
])
def test_scanner_catches_evaluations(doc):
    assert _scan(doc)


@pytest.mark.parametrize("doc", [
    {"configurations": {FLIGHT: "FLIGHT", RETIRED: "RETIRED as a candidate flight configuration (A9.19)"}},
    {"retired_flight_configuration_history": {"rollups": [{"configuration": RETIRED}]}},
    {"configurations_pre_a9_19": {RETIRED: "CONTROL / FALLBACK"}},
    {"ground_reference_rvm_status_counts": {"counts": {RETIRED: {"PASS": 0}}}},
    {"applies_to": {"configs": [FLIGHT], "ground_reference": {"configs": [RETIRED], "ledgers": ["GROUND_TEST"]}}},
    {"ledger_lines": [{"configuration": RETIRED, "ledger": "GROUND_TEST", "a9_20_role": "GROUND_ONLY_LAB_REFERENCE"}]},
    {"note": "quoted text naming hall_c1_reference is allowed"},
])
def test_scanner_allows_labelled_history_and_ground_reference(doc):
    assert not _scan(doc)
