"""A9-10 reconciliation overlay (fo_a9_10_integration): the declared, machine-checked changes that A9-10 applies to the
A9 deliverables (A9-01..A9-09) after their verified builds.

Every change is a record with a driver (an A9.1 decision id, a verified upstream lane item, an integration open item
OQ-INT-xx or an A9-10 self-reference) and an operation on a pointer of the deliverable's JSON document:

  * ``set``      the leaf/value at ``ptr`` must equal ``old`` (``ABSENT`` = key must not exist) and becomes ``new``;
  * ``replace``  the string at ``ptr`` must contain ``old``; every occurrence is replaced by ``new``;
  * ``append``   ``new`` is appended to the list at ``ptr`` (an element with the same ``id`` must not exist);
  * ``gsub``     every string leaf under ``ptr`` (default: whole document) containing ``old`` gets ``old`` -> ``new``;
                 at least one leaf must change;
  * ``code``     a change made in the builder / module source (not a JSON op); ``scope`` lists the JSON pointer
                 prefixes whose leaves that code change may alter, ``marker`` a string that must appear in ``file``.

Pointers: ``/key``, ``[index]``, ``[field=value]`` (first list element whose ``field`` equals ``value``) and ``[*]``
(every element). A pointer that does not resolve, an ``old`` value that does not match, or an op that changes nothing
raises: the overlay never silently skips (CLAUDE.md rule 3). Each builder calls ``apply(<deliverable>, doc)`` at the
end of its build and ``md_section(doc)`` at the end of its Markdown, so the JSON, the companion document and the
A9-10 reconciliation record (docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json) all derive from the
same records. Pure module: standard library only, reads only the pinned A9.1 decision file; not wired into archengine.
No value here is a prediction; every number is owner-given (A9.1 / row) or copied from a verified lane (checked by the
reconciliation builder against the source JSON).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
OVERLAY_REL = "docs/experiments/hall_icp/integration/a9_10_overlay.py"
RECORD_REL = "docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json"
LANE = "fo_a9_10_integration"
A91_REL = "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json"
A91_SHA = "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4"
A91_MD_REL = "docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md"
A91_MD_SHA = "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e"
ABSENT = "__ABSENT__"
XE_A9_DIR = "docs/budgets/" + "xe" + "_ledger_a9/"
XE_A9_JSON = XE_A9_DIR + "xe" + "_ledger_a9_v1.json"
M16_V3 = "docs/budgets/subsystem_maturity/v3/subsystem_maturity_v3.json"
OQ_V2 = "docs/budgets/owner_decisions/owner_questions_state_v2.json"
MASS_A9 = "docs/budgets/mass_a9/mass_a9_v1.json"
H2A9 = "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json"
RFQ_A9 = "docs/procurement/rfq_a9/rfq_a9_v1.json"
ICD = "schemas/interfaces/icp_neutralizer_icd_v1.json"
UB = "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json"
PRE = "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json"
EV = "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json"
ANSWERED = "ANSWERED_BY_A9_1"

DELIVERABLE_FILES = {
    "A9-01": PRE,
    "A9-02": "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
    "A9-03": ICD,
    "A9-04": UB,
    "A9-05ev": EV,
    "A9-05vi": "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
    "A9-06": MASS_A9,
    "A9-07": H2A9,
    "A9-08": XE_A9_JSON,
    "A9-09": RFQ_A9,
}


class OverlayError(RuntimeError):
    """A declared A9-10 change does not apply exactly (no silent skip)."""


# ------------------------------------------------------------------------------------------------------ A9.1 texts
_A91_CACHE: dict = {}


def _a91() -> dict:
    if "d" in _A91_CACHE:
        return _A91_CACHE["d"]
    p = os.path.join(ROOT, A91_REL)
    with open(p, "rb") as f:
        b = f.read()
    if hashlib.sha256(b).hexdigest() != A91_SHA:
        raise OverlayError(f"{A91_REL} sha256 changed (immutable owner decision)")
    _A91_CACHE["d"] = json.loads(b.decode("utf-8"))["decisions"]
    return _A91_CACHE["d"]


def decision_text(did: str) -> str:
    d = _a91()[did]
    if isinstance(d, dict):
        if did == "OQ-A902-01":
            return f"{d['gate_quantity']}; requirement: {d['requirement']}; status: {d['status']}"
        return "; ".join(f"{k}: {v}" for k, v in d.items())
    return d


def answered(qptr: str, dids, note: str = "", status_old=ABSENT) -> dict:
    """Mark an open owner question answered by one or more A9.1 decisions (never answers anything itself)."""
    dids = [dids] if isinstance(dids, str) else list(dids)
    text = " | ".join(f"{d}: {decision_text(d)}" for d in dids)
    return {"op": "merge", "ptr": qptr,
            "old": {"status": status_old, "a9_1_decision": ABSENT, "decision_source": ABSENT},
            "new": {"status": f"{ANSWERED} ({', '.join(dids)})", "a9_1_decision": text + (f" [{note}]" if note else ""),
                    "decision_source": f"{A91_REL} (sha256 {A91_SHA}); verbatim {A91_MD_REL}"},
            "driver": "A9.1 " + ", ".join(dids), "summary": f"owner question answered by A9.1 {', '.join(dids)}"}


def R(cid, driver, op, ptr, old=None, new=None, summary="", **kw):
    d = {"cid": cid, "driver": driver, "op": op, "ptr": ptr, "old": old, "new": new, "summary": summary}
    d.update(kw)
    return d


# ------------------------------------------------------------------------------------------------------ records
def _a901() -> list:
    q = "/open_owner_questions[id={}]"
    out = []
    for i, (qid, dec) in enumerate([("HIQ-01", "HIQ-01"), ("HIQ-02", "HIQ-02"), ("HIQ-03", "HIQ-03"),
                                    ("HIQ-04", "HIQ-04"), ("HIQ-05", "HIQ-05"), ("HIQ-06", "HIQ-06"),
                                    ("HIQ-07", "HIQ-07"), ("HIQ-08", "HIQ-08")], 1):
        st_old = {"HIQ-01": "OPEN - owner call", "HIQ-03": "OPEN - owner call", "HIQ-06": "OPEN - owner call",
                  "HIQ-07": "OPEN - owner call"}.get(qid, "OPEN")
        r = answered(q.format(qid), dec, status_old=st_old)
        r.update(cid=f"A910-A901-Q{i:02d}")
        out.append(r)
    out += [
        R("A910-A901-01", "A9.1 HIQ-01", "replace", "/execution_design/block_template[0]/configuration",
          "REF-COND reference installation (module: HIQ-01)",
          "REF-COND reference installation (module: hall_c1_reference in every block, A9.1 HIQ-01)",
          "REF-COND module = hall_c1_reference"),
        R("A910-A901-02", "A9.1 HIQ-01", "replace", "/execution_design/reference_asymmetry_note", "; reported, not hidden (HIQ-01)",
          "; A9.1 HIQ-01: hall_c1_reference stays the REF-COND drift/reference anchor in every block and this "
          "predecessor asymmetry is preserved and reported, never hidden or statistically erased",
          "predecessor asymmetry preserved and reported"),
        R("A910-A901-03", "A9.1 HIQ-02", "set", "/execution_design/min_complete_replicate_sets/interpretation",
          "PROPOSED: one 'complete engineering replicate' = one complete balanced replicate set (HIQ-02)",
          "OWNER (A9.1 HIQ-02): three complete balanced replicate sets = both sequences in each replicate set, i.e. "
          "at least six blocks before any larger n required by the LOCK-2 uncertainty",
          ">= 6 blocks (three complete balanced replicate sets)"),
        R("A910-A901-04", "A9.1 HIQ-02", "set", "/execution_design/min_blocks_if_interpretation_accepted/owner_status",
          ABSENT, "interpretation accepted by the owner (A9.1 HIQ-02): at least 6 blocks; final n at LOCK-2",
          "minimum 6 blocks recorded as owner-accepted"),
        R("A910-A901-05", "A9.1 HIQ-03", "replace", "/module_exchange[3]/rule", "(position: HIQ-03)",
          "(position: at the beginning of the installation, before the N2 slices and therefore before any "
          "O2-bearing exposure, A9.1 HIQ-03)", "Xe reference/health check first in each installation"),
        R("A910-A901-06", "A9.1 HIQ-04", "replace", "/stage_map[id=HI-HOLDOUT-A]/what",
          "(any gas), freeze which reading families",
          "(any gas, including the Ar engineering reproduction; A9.1 HIQ-04), freeze which reading families",
          "HI-HOLDOUT-A before the first Hall-on H-1 reading incl. Ar"),
        R("A910-A901-07", "A9.1 HIQ-04", "replace", "/stage_map[id=HI-HOLDOUT-B]/what",
          "before S1 (row 25)", "after LOCK-1 but before HI-S1 (row 25; A9.1 HIQ-04)",
          "held-out enumeration after LOCK-1, before HI-S1"),
        R("A910-A901-08", "A9.1 HIQ-08 + ICP-45", "set", "/stage_map[id=HI-AR]/a9_1", ABSENT,
          "A9.1 HIQ-08: HI-AR runs before LOCK-1 and after HI-HOLDOUT-A; engineering findings may refine hardware "
          "settings and the ICP recipe frozen at LOCK-1; Ar readings never enter LOCK-2 uncertainty numbers, "
          "architecture decision quantities or DRDO atmospheric compliance claims. A9.1 ICP-45: ICP-45A (Ar "
          "engineering qualification, I_e,cap >= I_d,max, engineering-only evidence) is demonstrated here. A9.1 "
          "UBQ-08: Ar-specific gauge/MFC/RGA calibrations are required for HI-AR interpretation",
          "HI-AR before LOCK-1; ICP-45A on Ar; Ar calibrations"),
        R("A910-A901-09", "A9.1 ICP-45", "append", "/stage_map[id=HI-CMP]/entry", None,
          "ICP-45 formal entry condition met (A9.1 ICP-45): ICP-45A (Ar, engineering-only) and ICP-45N (N2) each "
          "demonstrated I_e,cap >= I_d,max, with I_d,max from the registered H-1 / discharge-supply envelope (never "
          "invented), recording at each current the extracted electron current, RF forward/reflected power, DC "
          "input power, collector voltage/current, pressure, gas state, thermal state and plasma stability; no "
          "hall_icp_neutralizer score-bearing point before it; the Takahashi ~1 A / 200 W point is context only",
          "ICP-45A/ICP-45N as formal entry condition of score-bearing ICP points"),
        R("A910-A901-10", "A9.1 ICP-45", "set", "/decision_quantities[id=DQ-HI-ECAP]/entry_condition_a9_1", ABSENT,
          "ICP-45A (Ar, engineering-only) then ICP-45N (N2): I_e,cap >= I_d,max demonstrated before any "
          "hall_icp_neutralizer score-bearing point (A9.1 ICP-45); passing ICP-45 alone does not retire C1",
          "ICP-45 entry condition attached to DQ-HI-ECAP"),
        R("A910-A901-11", "A9.1 UBQ-02", "set", "/decision_quantities[id=DQ-HI-ECAP]/margin_form_a9_1", ABSENT,
          "M_n = I_e,cap / I_d,dem - 1; gate on the one-sided lower confidence bound > 0 (A9.1 UBQ-02); any "
          "additional design margin is computed/frozen at LOCK-2 by the LOCK-1 uncertainty rule, none invented now",
          "neutralization-margin form"),
        R("A910-A901-12", "A9.1 HIQ-05", "replace", "/decision_topology/net_benefit_form",
          "unless preregistered at LOCK-1 (row 37)",
          "unless preregistered at LOCK-1 (row 37); A9.1 HIQ-05: no mandatory Pareto relation - hard gates alone "
          "determine feasibility and Pareto quantities are reported for engineering comparison only unless a "
          "particular Pareto condition is explicitly preregistered at LOCK-1",
          "no mandatory Pareto relation"),
        R("A910-A901-13", "A9.1 HIQ-06", "set",
          "/configurations/configurations[1]/configuration_defining_settings[2]",
          "ICP gas species and flow - owner question HIQ-06 (A9 recorder flag row 46: unbooked)",
          "ICP gas mode G-REUSE (Hall exhaust / residual propellant; mdot_ICP,dedicated = 0; A9.1 HIQ-06); the "
          "dedicated ICP port is installed and capped; G-ATM / G-XE are separately declared contingency variants, "
          "booked when used; score-bearing N2 / N2+O2 comparison uses G-REUSE unless it fails the preregistered "
          "ICP-capacity gate", "ICP gas mode G-REUSE"),
        R("A910-A901-14", "A9.1 HIQ-06", "set", "/items[id=ITM-40]/value",
          "TBD - requires owner decision HIQ-06 and ICP ICD",
          "G-REUSE: 0 mg/s dedicated ICP flow (A9.1 HIQ-06); a G-ATM / G-XE contingency flow is TBD - requires the "
          "declared variant", "ICP gas feed booked as G-REUSE"),
        R("A910-A901-15", "A9.1 HIQ-06", "set", "/items[id=ITM-40]/status", "OPEN (unbooked)",
          "OWNER_GIVEN (A9.1 HIQ-06; contingency variants open)", "ICP gas feed status"),
        R("A910-A901-25", "A9.1 HIQ-06", "set", "/items[id=ITM-40]/evidence_class", "none (TBD)", "owner-allocation",
          "ICP gas feed evidence class"),
        R("A910-A901-26", "A9.1 HIQ-06", "set", "/items[id=ITM-40]/source",
          "schemas/interfaces/icp_neutralizer_icd_v1.json ICP-26 (A9-03)",
          A91_REL + " HIQ-06 (A9 recorder flag row 46 resolved); schemas/interfaces/icp_neutralizer_icd_v1.json "
          "ICP-26 (A9-03)", "ICP gas feed source"),
        R("A910-A901-16", "A9.1 HIQ-06", "replace", "/decision_quantities[id=DQ-HI-DXE]/operational_definition",
          "ICP gas feed booked by species (HIQ-06, A9 recorder flag row 46)",
          "ICP gas: G-REUSE books no dedicated ICP gas (A9.1 HIQ-06, no double counting of the Hall feed); a declared "
          "G-XE variant books mdot_ICP,Xe under PHASE_TOTAL_FLOW; a G-ATM variant adds mdot_ICP,dedicated to the "
          "atmospheric total", "dXe booking under G-REUSE"),
        R("A910-A901-17", "A9.1 HIQ-06", "replace", "/interface_demands[13]/demand", "ICP gas if Xe (HIQ-06)",
          "ICP Xe only for a declared G-XE contingency variant (A9.1 HIQ-06; G-REUSE books 0)",
          "Xe-ledger demand under G-REUSE"),
        R("A910-A901-18", "A9.1 HIQ-07", "set", "/held_out_validation/proposed_families[1]/role",
          "SEQUESTERED_FOR_FUTURE_PREREG (PROPOSED): the downstream ICP electron source changes the cathode boundary "
          "condition of any transport model; owner / W5 call (HIQ-07)",
          "SEQUESTERED_FOR_FUTURE_PREREG (owner, A9.1 HIQ-07): the downstream ICP electron source changes the "
          "cathode/electron boundary condition and cannot silently validate the existing transport model; kept for "
          "a future Hall-transport preregistration, not inserted into the current validation set",
          "pure-N2 ICP readings sequestered"),
        R("A910-A901-19", "A9.1 UBQ-07 + UBQ-09", "set", "/statistics_a9_1", ABSENT,
          {"alpha_family_wise": 0.05, "alpha_family_wise_scope": "simultaneous architecture contrasts, "
           "preregistered multiplicity-control procedure such as Holm", "alpha_one_sided_absolute_gate": 0.05,
           "freeze_point": "LOCK-1", "stop_rule_form": "SR-C-MARGIN (not sign-only): stop for inferiority only when "
           "the confidence bound crosses the preregistered negative decision margin; rule at LOCK-1, "
           "uncertainty-derived value at LOCK-2", "source": A91_REL + " UBQ-07, UBQ-09",
           "evidence_class": "owner-allocation"},
          "alpha values and stop-rule form (owner-given)", numeric=True),
        R("A910-A901-20", "A9-06 merged", "gsub", "",
          "PENDING A9-06 mass BOM A9 amendment (backlog item in the A9 decision; no path yet)",
          MASS_A9 + " (A9-06; allocations and evidence floors, no design CBE; re-evaluated in A9-10)",
          "mass BOM reference resolved to A9-06"),
        R("A910-A901-21", "A9-07 merged", "gsub", "",
          "PENDING A9-07 H2 revisions (backlog item in the A9 decision; no path yet)",
          H2A9 + " (A9-07; revision register REV-*, interface demands IDA7-*)", "H2 revision reference resolved"),
        R("A910-A901-22", "A9-08 merged", "gsub", "",
          "PENDING A9-08 Xe ledger updates (backlog item in the A9 decision; no path yet)",
          XE_A9_JSON + " (A9-08)", "Xe ledger reference resolved to the A9 ledger"),
        R("A910-A901-23", "A9-10 self-reference", "gsub", "/m16_impact",
          "changes route through PENDING A9-10 governance (backlog item in the A9 decision; no path yet)",
          "changes are routed through the A9-10 M16 refresh " + M16_V3, "M16 routing resolved"),
        R("A910-A901-24", "OQ-INT-01 (proposed consumer table)", "gsub", "/decision_quantities",
          "PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04)",
          UB + " measurement_chains feeding this quantity per the A9-10 chain -> DQ-HI consumer table "
          "(" + RECORD_REL + " dq_consumer_table; OQ-INT-01 PROPOSED, owner call)",
          "uncertainty owner of the unmapped DQ-HI quantities points at the consumer table"),
    ]
    return out


def _a902() -> list:
    q = "/open_owner_questions[id={}]"
    out = []
    for i in range(1, 8):
        qid = f"OQ-A902-0{i}"
        r = answered(q.format(qid), qid)
        r.update(cid=f"A910-A902-Q{i:02d}")
        out.append(r)
    out += [
        R("A910-A902-01", "A9.1 OQ-A902-01", "code", None, summary="1 ms gate quantity P_bus,1ms,max < 1500 W for "
          "start-up and steady state; measurement requirements; unaveraged peak and 100 ms / 1 s means diagnostic "
          "only; interim 'PASS only if peak_sampled' rule replaced (p_bus_1ms_max(), rfp_power_gate)",
          file="abep_sim/bus_boundary_a9.py", marker="P_bus,1ms,max = max_t (1/1 ms)",
          scope=["/items", "/gates_and_allocations", "/sequencing", "/bus_architecture", "/h4_inputs",
                 "/owner_answers_applied", "/h2_4_revision_flags", "/decision_pins", "/pinned_inputs",
                 "/interface_demands", "/m16_impact", "/slots"], numeric=True),
        R("A910-A902-02", "A9.1 OQ-A902-02..07, SEQ-heater, SEQ-peaks, HIQ-06", "code", None,
          summary="300 W composition accepted; P_ICP,available relation (icp_power_allocation_check); no combined "
          "flight C1 + ICP; flow_control_icp_feed only in a G-ATM / G-XE variant; internal-bus default path; 1300 W "
          "context; TBD heater ON at booked power (booked_W); at most one peak-class load rising per step "
          "(items A902-39..46)", file="docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py",
          marker="A902-46", scope=["/items", "/slots", "/variant_options", "/sequencing", "/gates_and_allocations"],
          numeric=True),
        R("A910-A902-03", "A9-10 self-reference", "set", "/interface_demands[21]/status",
          "PENDING docs/budgets/subsystem_maturity/v3/subsystem_maturity_v3.json (A9-10 refresh); PENDING "
          "docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json (A9-10)",
          "SUPPLIED to " + M16_V3 + " (A9-10 M16 refresh; rows 3, 5, 8, 11-15, 17 and new rows 18-19)",
          "M16 demand satisfied by the v3 refresh"),
    ]
    return out


def _a903() -> list:
    q = "/open_owner_questions[id={}]"
    out = []
    for i, (qid, dec, note) in enumerate([
            ("ICPQ-01", "A9-03-planes", ""), ("ICPQ-02", "HIQ-06", "primary G-REUSE; capped port for G-ATM / G-XE"),
            ("ICPQ-04", "A9-03-Vd", ""), ("ICPQ-05", "A9-03-matching", ""), ("ICPQ-07", "A9-03-collector", "")], 1):
        r = answered(q.format(qid), dec, note)
        r.update(cid=f"A910-A903-Q{i:02d}")
        out.append(r)
    out += [
        R("A910-A903-01", "A9.1 A9-03-planes", "set", "/items[id=ICP-01]/status", "PROPOSED",
          "OWNER_GIVEN (plane names, A9.1 A9-03-planes; dimensions stay LOCK-1 items)",
          "IP-EXIT / IP-NEU adopted; historical IP-DN unchanged"),
        R("A910-A903-02", "A9.1 A9-03-planes", "set", "/interface_planes[id=IP-NEU]/status",
          "PROPOSED (value of the standoff is ICP-02, TBD)",
          "ADOPTED (name, A9.1 A9-03-planes); value of the standoff is ICP-02, TBD", "IP-NEU adopted"),
        R("A910-A903-03", "A9.1 A9-03-Vd", "set", "/items[id=ICP-22]/value", None,
          "V_d = V_anode - V_electron-source-reference (primary controlled quantity); supply-terminal voltage and "
          "all loop drops recorded as secondary quantities", "V_d definition"),
        R("A910-A903-04", "A9.1 A9-03-Vd", "set", "/items[id=ICP-22]/status",
          "PENDING docs/experiments/hall_icp/prereg_framework/ (definition of the V_d setting used as the controlled "
          "variable)", "OWNER_GIVEN (A9.1 A9-03-Vd)", "V_d status"),
        R("A910-A903-05", "A9.1 A9-03-matching + A9-07 rf_reference_plane", "set", "/items[id=ICP-13]/value", None,
          "off the moving thrust-stand platform: matched flexible RF coax, calibrated cable-loss / S-parameter "
          "correction, directional coupler reference plane AFTER the matching network, matched sham routing in the "
          "C1 configuration; on-platform only if S1a proves the off-platform chain cannot meet the RF-power "
          "uncertainty; at the coupler plane P_fwd = P_net / (1 - |Gamma|^2) with Gamma the antenna-side "
          "reflection (A9-07 recomputations.rf_reference_plane); an on-module fixed pre-match holding |Gamma| <= "
          "Gamma_max is owner question OQ-A907-11 (Gamma_max at LOCK-1)", "matching network off-platform"),
        R("A910-A903-06", "A9.1 A9-03-matching", "set", "/items[id=ICP-13]/status", "TBD",
          "OWNER_GIVEN (location, A9.1); pre-match OPEN (OQ-A907-11)", "ICP-13 status"),
        R("A910-A903-07", "A9.1 A9-03-collector", "set", "/items[id=ICP-21]/material_a9_1", ABSENT,
          "flight collector material NOT frozen (A9.1 A9-03-collector); 316L may be used for the Ar engineering "
          "reproduction only; candidates pass the oxygen/AO coupon programme before any N2/O2 life claim; the "
          "Takahashi stainless-steel sputtering result is a warning, not a material qualification",
          "collector material rule"),
        R("A910-A903-08", "A9.1 HIQ-06 + OQ-A902-05", "set", "/items[id=ICP-26]/value", None,
          "G-REUSE (primary): the ICP operates on Hall exhaust / residual propellant, dedicated ICP flow 0 mg/s "
          "(no double counting of the Hall atmospheric feed); the dedicated port stays installed and capped; G-ATM "
          "and G-XE are separately declared contingency variants (G-ATM: mdot_atm,total = mdot_Hall + "
          "mdot_ICP,dedicated; G-XE: mdot_ICP,Xe booked in " + XE_A9_JSON + " under PHASE_TOTAL_FLOW)",
          "ICP gas G-REUSE"),
        R("A910-A903-09", "A9.1 HIQ-06", "set", "/items[id=ICP-26]/status", "TBD",
          "OWNER_GIVEN (G-REUSE primary, A9.1 HIQ-06); contingency flows TBD", "ICP-26 status"),
        R("A910-A903-10", "A9.1 HIQ-06 (Xe-ledger retarget)", "code", None,
          summary="Xe-ledger reference retargeted from the A6 ledger to the A9 ledger " + XE_A9_DIR +
          " (xe_budget_dir now selects the '_a9' ledger)",
          file="docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py", marker="A9-10: retargeted",
          scope=["/items", "/interface_demands", "/owner_answers_applied", "/deliverable_pins", "/pending_lanes",
                 "/open_owner_questions", "/historical_reuse", "/h3_h4_inputs", "/m16_impact"]),
        R("A910-A903-11", "A9.1 ICP-45", "set", "/items[id=ICP-45]/entry_condition_a9_1", ABSENT,
          "formal entry condition (A9.1 ICP-45): ICP-45A on Ar (engineering-only) and ICP-45N on N2 each demonstrate "
          "I_e,cap >= I_d,max before any hall_icp_neutralizer score-bearing point; record at each current the "
          "extracted electron current, RF forward/reflected power, DC input power, collector V/I, pressure, gas state, "
          "thermal state and plasma stability; I_d,max from the registered H-1 / discharge-supply envelope (owner "
          "registration OQ-A907-02, not invented); the Takahashi ~1 A / 200 W point is context only, not scaled",
          "ICP-45A / ICP-45N"),
        R("A910-A903-12", "A9.1 ICP-45 + A9-07 IDA7-12", "set", "/items[id=ICP-45]/status",
          "PENDING docs/architecture_comparison/power_boundary_a9/ (I_d,max of the stand discharge slot)",
          "TBD (value); form OWNER_GIVEN (A9.1 ICP-45)", "ICP-45 status re-evaluated"),
        R("A910-A903-28", "A9.1 ICP-45 + A9-07 IDA7-12", "set", "/items[id=ICP-45]/tbd", ABSENT,
          "TBD - requires the owner registration of the stand I_d,max (A9-07 OQ-A907-02; A9-02 registers no stand "
          "value); never invented to unblock ICP sizing (A9.1 ICP-45)", "ICP-45 remaining reason"),
        R("A910-A903-13", "A9.1 ICP-46", "set", "/items[id=ICP-46]/a9_1_isolation_basis", ABSENT,
          {"upper_operating_pulse_V": 600.0, "design_isolation_basis_V": 900.0, "development_hipot_V_DC": 1000.0,
           "pulse_waveform_test_V": 600.0, "source": A91_REL + " ICP-46", "evidence_class": "owner-allocation"},
          "ICP-46 isolation basis (900 V / 1.0 kV DC hipot / 600 V pulse test)", numeric=True),
        R("A910-A903-14", "A9.1 ICP-46", "set", "/items[id=ICP-46]/units",
          "V (pulse class upper end; margin TBD)",
          "V (upper operating pulse; the A9.1 isolation basis is in a9_1_isolation_basis)", "ICP-46 units"),
        R("A910-A903-29", "A9.1 A9-03-matching", "set", "/items[id=ICP-13]/evidence_class", None, "owner-allocation",
          "ICP-13 evidence class"),
        R("A910-A903-30", "A9.1 A9-03-Vd", "set", "/items[id=ICP-22]/evidence_class", None, "owner-allocation",
          "ICP-22 evidence class"),
        R("A910-A903-31", "A9.1 HIQ-06", "set", "/items[id=ICP-26]/evidence_class", None, "owner-allocation",
          "ICP-26 evidence class"),
        R("A910-A903-15", "A9.1 ICP-46", "set", "/items[id=ICP-46]/status", "PROPOSED (margin TBD)",
          "OWNER_GIVEN (A9.1 ICP-46)", "ICP-46 status"),
        R("A910-A903-16", "A9.1 ICP-46", "set", "/items[id=ICP-46]/basis",
          "row 89 (300-600 V class); margin owner/LOCK-1",
          "row 89 (300-600 V class); A9.1 ICP-46: design isolation basis 900 V (1.5 x 600 V); qualification/hipot "
          "1.0 kV DC at representative pressure/gas on the initial H-1/C1 development hardware (no flashover or "
          "breakdown, leakage recorded) plus a separate 600 V pulse-waveform test; applies to keeper lead, "
          "feedthrough, connectors, harness and isolation to cathode common / module body / facility ground; does "
          "not replace ICP-44; the flight level may only be revised upward without a controlled justification",
          "ICP-46 basis"),
        R("A910-A903-17", "A9.1 ICP-46", "set", "/items[id=ICP-46]/evidence_class",
          "owner-allocation (margin TBD)", "owner-allocation", "ICP-46 evidence class"),
        R("A910-A903-18", "A9-07 IDA7-07", "set", "/items[id=ICP-43]/h1_heat_allowance_a9_07", ABSENT,
          "A9-07 IDA7-07 (" + H2A9 + " interface_demands IDA7-07): the allowable ICP-module heat entering H-1 "
          "(1.2 x Q <= headroom, injection at PO / BP) is 0 W at LV-BASE (min over nodes, the inner coil CI and wall "
          "WI have no headroom) and stays 0 W min-over-nodes for every single lever; every hall_icp_neutralizer "
          "thermal CLOSES is conditional on the actual ICP-43 heat meeting this allowance",
          "A9-07 heat allowance propagated to ICP-43", source={"file": H2A9, "ptr": "/interface_demands[id=IDA7-07]/value/LV-BASE/PO/min_over_nodes", "value": 0.0}),
        R("A910-A903-19", "A9-07 IDA7-08 re-evaluation", "set", "/items[id=ICP-43]/status",
          "PENDING docs/architecture_comparison/power_boundary_a9/ (maximum discharge-supply power P_d,max at the "
          "stand)", "TBD", "ICP-43 status re-evaluated"),
        R("A910-A903-32", "A9-07 IDA7-08 re-evaluation", "set", "/items[id=ICP-43]/tbd", ABSENT,
          "TBD - requires P_d,max = I_d,max x V_d,max of the registered stand envelope (owner registration "
          "OQ-A907-02; A9-02 registers no stand value) and the ICPQ-10 bounding choice; the H-1 side is limited by the "
          "A9-07 IDA7-07 allowance", "ICP-43 remaining reason"),
        R("A910-A903-20", "A9-07 K9 / IDA7-07", "set", "/items[id=ICP-05]/view_condition_a9_07", ABSENT,
          "A9-07: the external KC-1 C1 module coupling to H-1 is TBD - requires the C1 module drawing and view "
          "factors (ICP-05); the hall_c1_reference thermal case run by A9-07 is a sensitivity only (v1 central path), "
          "no thermal verdict; the downstream module's view of the H-1 exit face enters the ICP-43 heat split",
          "exit-face view condition propagated"),
        R("A910-A903-21", "A9-07 merged", "set", "/items[id=ICP-05]/tbd",
          "TBD - requires the H2-1/H2-2 revision for the external C1 (A9-07) and the C1 reference module design",
          "TBD - requires the C1 reference module design (orifice position, view factors); the H2-1/H2-2 revision "
          "for the external C1 is done in " + H2A9 + " (REV-13..28)", "ICP-05 re-evaluated"),
        R("A910-A903-23", "A9.1 HIQ-06", "set", "/items[id=ICP-26]/tbd",
          "TBD - requires the owner choice of the primary ICP gas mode (ICPQ-02) and the ICP module design",
          "TBD - requires the ICP module design and, only for a declared G-ATM / G-XE contingency variant, its "
          "dedicated flow (primary mode G-REUSE decided, A9.1 HIQ-06)", "ICP-26 tbd re-evaluated"),
        R("A910-A903-24", "A9.1 HIQ-06 (A9-08 XA9-IF-16)", "set", "/interface_demands[23]/status",
          "TBD - requires the owner choice of the ICP gas mode (ICPQ-02); ledger at " + XE_A9_DIR,
          "RESOLVED by A9.1 HIQ-06 (G-REUSE books 0 Xe; a G-XE contingency is booked as F-ICP-XE / G-ICP-XE in "
          + XE_A9_JSON + ", A9-08 XA9-IF-16)", "ICP gas booking demand resolved"),
        R("A910-A903-25", "A9.1 A9-03-matching", "set", "/items[id=ICP-13]/tbd",
          "TBD - requires the owner decision ICPQ-05 and the dummy-load cable-loss characterisation (S1a)",
          "TBD - requires the S1a dummy-load cable-loss / S-parameter characterisation (location decided off-platform, "
          "A9.1) and the pre-match decision OQ-A907-11", "ICP-13 tbd re-evaluated"),
        R("A910-A903-26", "A9.1 A9-03-Vd", "set", "/items[id=ICP-22]/note", "see open question ICPQ-04",
          "ICPQ-04 answered by A9.1 A9-03-Vd (V_d = V_anode - V_electron-source-reference)", "ICP-22 note"),
        R("A910-A903-27", "A9.1 A9-03-collector", "replace", "/items[id=ICP-29]/tbd", "the collector material (ICPQ-07)",
          "the collector material (not frozen; 316L for Ar engineering only; O/AO coupon programme first, A9.1 "
          "A9-03-collector)", "ICP-29 tbd re-evaluated"),
        R("A910-A903-22", "OQ-INT-04", "replace", "/published_analog_annex/source/authority_note",
          "must be reconciled with A9-05 when it merges",
          "was reconciled with A9-05 in A9-10 (OQ-INT-04): A9-05 governs where they differ; differences listed in "
          + RECORD_REL + " annex_reconciliation", "annex reconciled with A9-05"),
    ]
    return out


def _a904() -> list:
    q = "/open_owner_questions[id={}]"
    out = []
    for i in range(1, 10):
        qid = f"UBQ-0{i}"
        r = answered(q.format(qid), qid)
        r.update(cid=f"A910-A904-Q{i:02d}")
        out.append(r)
    out += [
        R("A910-A904-01", "A9.1 UBQ-01", "replace", "/items[id=UB-T-01]/note",
          "Whether 1 % is a standard (k=1) or expanded uncertainty is open question UBQ-01",
          "A9.1 UBQ-01: 1 % is the standard relative uncertainty (k = 1) of a sustained reading; absolute PASS/FAIL "
          "gates use the preregistered one-sided confidence treatment; never reinterpreted as k = 2", "k = 1"),
        R("A910-A904-02", "A9.1 UBQ-02", "set", "/items[id=UB-N-06]/value",
          "PENDING docs/experiments/hall_icp/prereg_framework/ (gate definition; this lane proposes the ratio form "
          "M_n = I_e,cap/I_d,dem - 1, UBQ-02)",
          "M_n = I_e,cap / I_d,dem - 1; gate on the one-sided lower confidence bound > 0 (A9.1 UBQ-02); any "
          "additional design margin computed/frozen at LOCK-2 by the LOCK-1 uncertainty rule", "M_n form"),
        R("A910-A904-03", "A9.1 UBQ-02", "set", "/items[id=UB-N-06]/status", "PENDING", "OWNER_GIVEN",
          "M_n status"),
        R("A910-A904-04", "A9.1 UBQ-02", "set", "/items[id=UB-N-06]/evidence_class", None, "owner-allocation",
          "M_n evidence class"),
        R("A910-A904-05", "A9.1 UBQ-02", "set", "/items[id=UB-N-06]/source", "owner answers rows 37, 145",
          "owner answers rows 37, 145; " + A91_REL + " UBQ-02", "M_n source"),
        R("A910-A904-06", "A9.1 UBQ-03", "gsub", "/measurement_chains",
          "unless the certificate states a multiplier, GUM 4.3.3; UBQ-03]",
          "unless the certificate states a multiplier, GUM 4.3.3; accepted, A9.1 UBQ-03]",
          "rectangular conversion accepted"),
        R("A910-A904-07", "A9.1 UBQ-04", "set", "/items[id=UB-RF-08]/value",
          "TBD - requires owner acceptance of the rule form (UBQ-04) at LOCK-1; k_x value at LOCK-2 from S1a", 2.0,
          "k_x = 2 frozen at LOCK-1", numeric=True),
        R("A910-A904-08", "A9.1 UBQ-04", "set", "/items[id=UB-RF-08]/status", "PROPOSED", "OWNER_GIVEN",
          "k_x status"),
        R("A910-A904-09", "A9.1 UBQ-04", "set", "/items[id=UB-RF-08]/evidence_class", None, "owner-allocation",
          "k_x evidence class"),
        R("A910-A904-10", "A9.1 UBQ-04", "set", "/items[id=UB-RF-08]/note", "",
          "|z_x| <= k_x with k_x = 2 frozen at LOCK-1 (A9.1 UBQ-04); S1a determines the uncertainties in the "
          "denominator, not the threshold; a failed coupler-vs-calorimetry check makes RF-dependent quantities "
          "EXCLUDED_INSTRUMENT until resolved; no instrument is ever re-weighted", "agreement rule"),
        R("A910-A904-11", "A9.1 UBQ-05", "set", "/items[id=UB-T-07]/note", "",
          "A9.1 UBQ-05: both - the pre/post shift enters the budget AND a block-exclusion rule applies; rule form "
          "frozen at LOCK-1, numerical limit inserted at LOCK-2 from metrology-only calibration evidence",
          "calibration-shift rule"),
        R("A910-A904-12", "A9.1 UBQ-06 + A9-07 IDA7-16", "set", "/stop_rules/limit_aborts/limits[id=LA-05]/value",
          "TBD - requires validated continuous-use limits (rows 86, 87); abort at the limit or at limit - margin is "
          "UBQ-06",
          "abort_C = validated continuous-use limit - 50 K for score-bearing operation (A9.1 UBQ-06; row 86); per-node "
          "abort list in " + H2A9 + " IDA7-16 (BN wall and ceramic coil provisional on supplier limits, OQ-A907-05; "
          "other groups TBD - requires a validated limit)", "aborts at limit - 50 K"),
        R("A910-A904-13", "A9.1 UBQ-07", "set", "/items[id=UB-C-02]/value",
          "TBD - requires owner decision at LOCK-1 (UBQ-07)", 0.05, "alpha_FW = 0.05", numeric=True),
        R("A910-A904-14", "A9.1 UBQ-07", "set", "/items[id=UB-C-02]/status", "TBD", "OWNER_GIVEN",
          "alpha_FW status (frozen at LOCK-1)"),
        R("A910-A904-15", "A9.1 UBQ-07", "set", "/items[id=UB-C-02]/evidence_class", None, "owner-allocation",
          "alpha_FW class"),
        R("A910-A904-16", "A9.1 UBQ-07", "set", "/items[id=UB-C-02]/source", "-", A91_REL + " UBQ-07",
          "alpha_FW source"),
        R("A910-A904-17", "A9.1 UBQ-07", "set", "/items[id=UB-C-02]/note", "",
          "simultaneous architecture contrasts with a preregistered multiplicity-control procedure such as Holm "
          "(the Bonferroni quantile in variance_groups is a PROPOSED form, frozen at LOCK-1)", "multiplicity"),
        R("A910-A904-18", "A9.1 UBQ-07", "set", "/items[id=UB-C-03]/value",
          "TBD - requires owner decision at LOCK-1 (UBQ-07)", 0.05, "alpha_abs = 0.05 one-sided", numeric=True),
        R("A910-A904-19", "A9.1 UBQ-07", "set", "/items[id=UB-C-03]/status", "TBD", "OWNER_GIVEN",
          "alpha_abs status (frozen at LOCK-1)"),
        R("A910-A904-20", "A9.1 UBQ-07", "set", "/items[id=UB-C-03]/evidence_class", None, "owner-allocation",
          "alpha_abs class"),
        R("A910-A904-21", "A9.1 UBQ-07", "set", "/items[id=UB-C-03]/source", "-", A91_REL + " UBQ-07",
          "alpha_abs source"),
        R("A910-A904-37", "A9.1 UBQ-04", "set", "/items[id=UB-RF-08]/source", "owner answer row 72",
          "owner answer row 72; " + A91_REL + " UBQ-04", "k_x source"),
        R("A910-A904-32", "A9.1 UBQ-04", "set", "/items[id=UB-RF-08]/a9_1_decision", ABSENT, "UBQ-04",
          "A9.1 decision id attached (owner-given value source)"),
        R("A910-A904-33", "A9.1 UBQ-07", "set", "/items[id=UB-C-02]/a9_1_decision", ABSENT, "UBQ-07",
          "A9.1 decision id attached (owner-given value source)"),
        R("A910-A904-34", "A9.1 UBQ-07", "set", "/items[id=UB-C-03]/a9_1_decision", ABSENT, "UBQ-07",
          "A9.1 decision id attached (owner-given value source)"),
        R("A910-A904-35", "A9.1 UBQ-02", "set", "/items[id=UB-N-06]/a9_1_decision", ABSENT, "UBQ-02",
          "A9.1 decision id attached"),
        R("A910-A904-36", "A9.1 HIQ-06", "set", "/items[id=UB-F-12]/a9_1_decision", ABSENT, "HIQ-06",
          "A9.1 decision id attached"),
        R("A910-A904-22", "A9.1 UBQ-08", "append", "/items", None,
          {"id": "UB-AR-01", "dq": "engineering-only (HI-AR)", "name": "Ar-specific gauge / MFC / RGA calibrations",
           "symbol": "-", "type": "requirement", "value": "required for HI-AR engineering interpretation",
           "units": "-", "basis": "owner decision", "source": A91_REL + " UBQ-08", "evidence_class": "owner-allocation",
           "status": "OWNER_GIVEN", "freeze_point": "NOW", "owner_rows": [36], "owner_text": None,
           "configurations": ["hall_c1_reference", "hall_icp_neutralizer"], "a9_1_decision": "UBQ-08",
           "note": "Ar remains engineering-only regardless of calibration quality; Ar readings never enter LOCK-2 "
                   "numbers, decision quantities or DRDO compliance claims (A9.1 HIQ-08)"},
          "Ar calibrations required (new item; owner row 36 cited)", numeric=True),
        R("A910-A904-23", "A9.1 UBQ-09", "set", "/stop_rules/contrast_stop/owner_choice",
          "OPEN - explicit owner choice between SR-C-SIGN and SR-C-MARGIN (UBQ-09)",
          "SR-C-MARGIN (A9.1 UBQ-09): a configuration is stopped for inferiority only when its confidence bound "
          "crosses the preregistered negative decision margin; margin rule frozen at LOCK-1, uncertainty-derived "
          "value at LOCK-2; SR-C-SIGN is not used", "SR-C-MARGIN"),
        R("A910-A904-24", "A9-07 IDA7-21", "set", "/items[id=UB-RF-04]/value",
          "TBD - requires coupler directivity from its certificate and the measured load reflection; the evaluation "
          "formula is taken from the coupler/sensor documentation (from memory: a directivity-limited reflection "
          "error - verify)",
          "TBD - requires the coupler directivity D from its certificate, the operating |Gamma| at the coupler plane "
          "and D_min frozen at LOCK-2; first-order relation from A9-07 IDA7-21: worst-case relative error of P_net = "
          "max((|G|+d)^2 - |G|^2, |G|^2 - (|G|-d)^2) / (1 - |G|^2), d = 10^(-D/20) (verify against the coupler "
          "documentation); plus the two-port + Gamma_L load-power correction term (A9H-INS-03)",
          "UB-RF-04 directivity/mismatch term from IDA7-21"),
        R("A910-A904-25", "A9-07 IDA7-21", "set", "/items[id=UB-RF-04]/source", "-",
          H2A9 + " interface_demands IDA7-21 and recomputations.rf_reference_plane (sensitivity at residual VSWR "
          "1.2-2.0, D 20/30/40 dB)", "UB-RF-04 source"),
        R("A910-A904-28", "A9.1 HIQ-06 (A9-03 ICP-26)", "set", "/items[id=UB-F-12]/value",
          "PENDING docs/interfaces/icp_neutralizer/ (ICP gas species and flow; A9 recorder flag row 46: not yet booked)",
          "G-REUSE (A9.1 HIQ-06; " + ICD + " ICP-26): no dedicated ICP feed and no ICP MFC in the primary mode; the "
          "Hall-feed chains (INS-05) already carry the gas; a dedicated-flow chain with own-gas calibration exists "
          "only for a declared G-ATM / G-XE contingency variant", "ICP gas chain under G-REUSE"),
        R("A910-A904-29", "A9.1 HIQ-06", "set", "/items[id=UB-F-12]/status", "PENDING", "OWNER_GIVEN",
          "UB-F-12 status"),
        R("A910-A904-30", "A9.1 HIQ-06", "set", "/items[id=UB-F-12]/evidence_class", None, "owner-allocation",
          "UB-F-12 evidence class"),
        R("A910-A904-31", "A9.1 HIQ-06", "replace", "/items[69]/value",
          "the ICP gas flow is PENDING docs/interfaces/icp_neutralizer/",
          "the ICP gas load is the Hall exhaust reused in G-REUSE (no dedicated flow, A9.1 HIQ-06; " + ICD +
          " ICP-26); a declared G-ATM / G-XE variant adds its dedicated flow", "p_b mismatch item re-evaluated"),
        R("A910-A904-26", "A9-10 self-reference", "gsub", "/m16_impact",
          "row owners and states PENDING A9-10 governance",
          "row owners and states set in the A9-10 M16 refresh " + M16_V3, "M16 routing resolved"),
        R("A910-A904-27", "OQ-INT-01 (proposed consumer table)", "gsub", "/dq_id_mapping/rows",
          "UNMAPPED - owner/A9-10",
          "UNMAPPED - kept as a measurement-chain id; chain -> DQ-HI consumer table in " + RECORD_REL +
          " (OQ-INT-01 PROPOSED, owner call)", "unmapped ids kept; consumer table referenced"),
    ]
    return out


def _a905ev() -> list:
    q = "/open_owner_questions[id={}]"
    out = []
    for i, qid in enumerate(["OQ-EV-01", "OQ-EV-02", "OQ-EV-03"], 1):
        r = answered(q.format(qid), qid, status_old="owner call")
        r.update(cid=f"A910-A905EV-Q{i:02d}")
        out.append(r)
    out += [
        R("A910-A905EV-01", "A9.1 OQ-EV-02", "gsub", "/lawful_acquisition_list/items", " (PROPOSED)",
          " (owner-accepted order, A9.1 OQ-EV-02)", "acquisition order accepted"),
        R("A910-A905EV-02", "A9.1 OQ-EV-02", "set", "/lawful_acquisition_list/note",
          "priorities are PROPOSED; acquisition is an owner action outside the repository (A9 "
          "owner_actions_outside_the_repository)",
          "priorities accepted by the owner (A9.1 OQ-EV-02: P1 LA-01..03; P2 LA-04, LA-06..08; P3 LA-05, LA-09); "
          "acquisition is an owner action outside the repository; no author or laboratory data request (A9.1 "
          "OQ-EV-01)", "acquisition note"),
        R("A910-A905EV-03", "A9.1 OQ-EV-01 + OQ-EV-03", "set", "/acquisition_policy_a9_1", ABSENT,
          {"author_or_lab_requests": "NO (A9.1 OQ-EV-01): standing published/lawful-source-only policy",
           "publisher_served_full_text": "YES (A9.1 OQ-EV-03): values may be cited/extracted from publisher-served "
                                         "full text accessed lawfully without bypass",
           "record_for_every_value": ["publisher URL", "DOI", "page/figure/table locator", "access date",
                                      "evidence class"],
           "redistribution": "the copyrighted PDF is not committed or redistributed where the licence does not "
                             "permit it", "source": A91_REL},
          "acquisition policy recorded"),
    ]
    return out


def _a905vi() -> list:
    q = "/open_owner_questions[id={}]"
    out = []
    for i, (qid, dec) in enumerate([("OQ-VI-01", "HIQ-06"), ("OQ-VI-02", "UBQ-02")], 1):
        r = answered(q.format(qid), dec)
        r.update(cid=f"A910-A905VI-Q{i:02d}")
        out.append(r)
    out += [
        R("A910-A905VI-01", "A9.1 HIQ-06", "set", "/items[id=VI-GAS-01]/value",
          "TBD - requires owner decision OQ-VI-01; flagged UNBOOKED (A9 recorder_consistency_flags row 46)",
          "G-REUSE (A9.1 HIQ-06): Hall exhaust / residual propellant, mdot_ICP,dedicated = 0; dedicated port capped; "
          "G-ATM / G-XE only as declared contingency variants (G-XE booked in " + XE_A9_JSON + " under "
          "PHASE_TOTAL_FLOW)", "ICP gas booked G-REUSE"),
        R("A910-A905VI-02", "A9.1 HIQ-06", "set", "/items[id=VI-GAS-01]/status", "OPEN_UNBOOKED_FLAG",
          "OWNER_GIVEN (A9.1 HIQ-06)", "VI-GAS-01 status"),
        R("A910-A905VI-03", "A9.1 HIQ-06", "set", "/items[id=VI-GAS-01]/basis", "owner allocation (pending)",
          "owner decision (A9.1 HIQ-06)", "VI-GAS-01 basis"),
        R("A910-A905VI-04", "A9.1 UBQ-02", "set", "/items[id=VI-EX-07]/definition",
          "PROPOSED form (OQ-VI-02): electron-current capacity of the electron source at the registered coupling-voltage "
          "limit (VI-EX-02) relative to the measured Hall current demand at the same point (VI-HD-01); the numeric "
          "margin is frozen only at LOCK-2 (rows 18, 19)",
          "owner form (A9.1 UBQ-02): M_n = I_e,cap / I_d,dem - 1 with I_e,cap at the registered coupling-voltage limit "
          "(VI-EX-02) and I_d,dem the measured Hall current demand at the same point (VI-HD-01); gate on the one-sided "
          "lower confidence bound > 0; any extra design margin frozen at LOCK-2 by the LOCK-1 rule (rows 18, 19)",
          "M_n form"),
        R("A910-A905VI-05", "A9.1 UBQ-02", "set", "/items[id=VI-EX-07]/value",
          "TBD - requires VI-EX-02 and VI-HD-01; form: owner call (OQ-VI-02)",
          "TBD - requires VI-EX-02 and VI-HD-01 (hardware); form decided (A9.1 UBQ-02)", "VI-EX-07 value text"),
        R("A910-A905VI-06", "A9-08 merged (Xe-ledger retarget)", "replace", "/items[id=VI-GAS-01]/definition",
          "booked in the Xe ledger, docs/budgets/" + "xe" + "_ledger/)",
          "booked in the A9 Xe ledger " + XE_A9_JSON + " as F-ICP-XE / G-ICP-XE)", "Xe-ledger reference retargeted"),
    ]
    return out


def _a906() -> list:
    return [
        R("A910-A906-01", "A9-08 XA9-IF-01 (single booking) + A9-07 IDA7-01 (LV-COIL)", "code", None,
          summary="wet closure re-run with the A9-08 residual imported once (per design case, under both "
                  "case-content readings XA9Q-01 / MQ-09, never added twice) and an LV-COIL copper-mass sensitivity "
                  "from the corrected A9-07 basis (not booked; lever adoption owner/LOCK-1)",
          file="docs/budgets/mass_a9/build_mass_a9.py", marker="def closure_a9_10",
          scope=["/wet_closure", "/lv_coil_sensitivity", "/a9_flight_bom/flight[13]/value", "/items[20]/value"],
          numeric=True),
        R("A910-A906-02", "OQ-INT-03 re-evaluation (A9-06 references to merged lanes)", "code", None,
          summary="references to A9-07 / A9-08 / A9-09 / A9-10 re-evaluated: values they supply are imported "
                  "(residual, design-case volumes, IDA7-09 confirmation), the rest carry the precise remaining reason "
                  "(pending() text); the A9-08 and A9-07 JSON are read for values (read_deliverables)",
          file="docs/budgets/mass_a9/build_mass_a9.py", marker="A9-10 re-evaluation",
          scope=["/items", "/interface_demands", "/owner_answers_applied", "/a9_flight_bom", "/pending_lanes",
                 "/xe_screen_row44", "/required_reduction_of_evidence_free_lines", "/read_deliverables",
                 "/h2_7_demands_reevaluated", "/open_owner_questions", "/m16_impact", "/line_checks",
                 "/reallocation_options", "/a9_1_decisions_applied"]),
    ]


def _a907() -> list:
    ids = "/interface_demands[id={}]/status"
    return [
        R("A910-A907-01", "A9-08 merged", "gsub", "", "PENDING A9-08, IDA7-04",
          "booked by A9-08 in " + XE_A9_JSON + " as C1 start terms F-C1-* / G-C1-* with values TBD, IDA7-04",
          "Xe-ledger reference resolved"),
        R("A910-A907-02", "A9-08 merged", "replace", "/open_owner_questions[id=OQ-A907-01]/values/scope",
          "purge/preheat Xe excluded, PENDING A9-08)",
          "purge/preheat Xe excluded; booked by A9-08 as F-C1-* terms with values TBD)", "scope text re-evaluated"),
        R("A910-A907-03", "A9-08 XA9-IF-06", "set", ids.format("IDA7-04"),
          "PENDING docs/budgets/" + "xe" + "_ledger_a9/ (A9-08: Xe per start terms)",
          "SUPPLIED as booking structure by A9-08 (" + XE_A9_JSON + " F-C1-* / G-C1-* purge, preheat and ignition "
          "terms, G-XE contingency term); values REFUSED while the vendor/design-qualified flows and durations are "
          "TBD (XA9-09..11)", "IDA7-04 re-evaluated"),
        R("A910-A907-04", "A9-08 XA9-IF-06", "set", "/revision_register[24]/new/value/purge_preheat_xe",
          "PENDING docs/budgets/" + "xe" + "_ledger_a9/ (A9-08: purge/preheat Xe per start (IDA7-04))",
          "booked by A9-08 as F-C1-* terms (" + XE_A9_JSON + "); value TBD - requires vendor/design-qualified "
          "purge/preheat flows and durations (XA9-09..11)", "purge/preheat booking re-evaluated"),
        R("A910-A907-05", "A9-06 merged (no ground module masses)", "set", ids.format("IDA7-02"),
          "PENDING docs/budgets/mass_a9/ (A9-06: module masses and CG)",
          "OPEN - A9-06 (" + MASS_A9 + ", merged) books flight-BOM allocations and evidence floors, not ground module "
          "masses/CG; TBD - requires the C1 / ICP / sham module drawings (ICD ICP-08)", "IDA7-02 re-evaluated"),
        R("A910-A907-06", "A9-06 merged (no ground module masses)", "set",
          "/revision_register[31]/new/value/per_configuration_mass_kg",
          "PENDING docs/budgets/mass_a9/ (A9-06: module masses and CG)",
          "TBD - requires the C1 / ICP / sham module drawings (ICD ICP-08); A9-06 (merged) gives no ground module "
          "masses", "per-configuration stand mass re-evaluated"),
        R("A910-A907-07", "A9-09 merged (quotations only)", "set", ids.format("IDA7-06"),
          "PENDING docs/procurement/rfq_a9/ (A9-09: quotations)",
          "OPEN - A9-09 (" + RFQ_A9 + ", merged) issued RFQ specifications only; no quotation received (no supplier "
          "contact by any lane)", "IDA7-06 re-evaluated"),
        R("A910-A907-09", "A9-10 self-reference", "set", "/parallel_lanes_pending/A9-10",
          "fo_a9_10_integration (reconciliation lane; no path yet)", RECORD_REL + " (fo_a9_10_integration)",
          "A9-10 path resolved"),
        R("A910-A907-10", "OQ-INT-03 re-evaluation", "set", "/parallel_lanes_status_a9_10", ABSENT,
          "A9-06, A9-08 and A9-09 are merged and verified; every reference to them in this deliverable was re-evaluated "
          "in A9-10 (" + RECORD_REL + " pending_reevaluation / interface_demand_matrix)", "parallel lanes merged"),
        R("A910-A907-08", "A9-02 merged (no stand registration)", "set", ids.format("IDA7-08"),
          "PENDING docs/architecture_comparison/power_boundary_a9/ (P_d,max; ICP-43)",
          "OPEN - TBD - requires the owner registration of the stand I_d,max / P_d,max (OQ-A907-02); A9-02 registers "
          "no stand value; ICD ICP-43 now carries the A9-07 IDA7-07 H-1 allowance", "IDA7-08 re-evaluated"),
    ]


def _a908() -> list:
    return [
        R("A910-A908-01", "OQ-INT-03 re-evaluation + A9-10 self-reference", "code", None,
          summary="parallel-lane references re-evaluated: A9-06 / A9-07 / A9-09 merged references carry the precise "
                  "remaining reason (they do not supply the value), A9-10 references point at the reconciliation "
                  "record and M16 v3; upstream sha256 pins refreshed after the A9-10 rebuild of A9-01..05",
          file="docs/budgets/" + "xe" + "_ledger_a9/build_" + "xe" + "_ledger_a9.py", marker="A9-10 re-evaluation",
          scope=["/items", "/terms", "/interface_demands", "/parallel_lanes", "/scenarios", "/evaluations",
                 "/design_cases", "/open_owner_questions", "/m16_impact", "/h3_inputs", "/h4_inputs",
                 "/deliverable_pins", "/filter_getter", "/non_xe_obligations", "/a9_1_decisions_applied",
                 "/owner_answers_applied", "/term_presence", "/accounting_convention", "/ledgers",
                 "/not_primary_variants", "/icp_gas_modes", "/historical_reuse"]),
        R("A910-A908-02", "A9-10 residual import", "set", "/interface_demands[id=XA9-IF-01]/status", "OFFERED",
          "CONSUMED by A9-06 in the A9-10 re-run (" + MASS_A9 + " wet_closure.residual; booked once)",
          "residual import consumed"),
    ]


def _a909() -> list:
    rf = "/packages[id=RFQ-04]/requirements[id={}]"
    xe = "/packages[id=RFQ-07]/requirements[id={}]"
    return [
        R("A910-A909-32", "A9.1 OQ-A902-05 via the A9-02 module (G-REUSE)", "code", None,
          summary="derived.p_bus_channel_slots is re-derived from abep_sim/bus_boundary_a9.py: flow_control_icp_feed "
                  "is now a G-ATM / G-XE variant slot of hall_icp_neutralizer (one installed P_bus channel fewer)",
          file="abep_sim/bus_boundary_a9.py", marker='"hall_icp_neutralizer": ("icp_assist_magnet", "active_cooling", '
                                                   '"flow_control_icp_feed")',
          scope=["/derived/p_bus_channel_slots", "/packages[5]/requirements[11]/value"], numeric=True),
        R("A910-A909-00", "A9-10 package changes (derived lists)", "code", None,
          summary="after the package-level A9-10 changes the derived lists (open_specification_items, "
                  "traceability_matrix, h3_h4_inputs) are rebuilt from the changed packages and the lane validation "
                  "is re-run", file="docs/procurement/rfq_a9/build_rfq_a9.py",
          marker='doc["traceability_matrix"] = traceability(doc["packages"])',
          scope=["/packages", "/traceability_matrix", "/h3_h4_inputs"]),
        R("A910-A909-01", "A9-07 IDA7-22, H3-A907-03, OQ-A907-11", "replace", rf.format("RFQ-04-R08") + "/requirement",
          "coupling factor, directivity and sensor linearity certified.",
          "coupling factor, directivity and sensor linearity certified. Rating basis (A9-07 IDA7-22, H3-A907-03): the "
          "coupler and sensors carry the antenna-side reflection, so they are rated for the coupler-plane forward "
          "power P_fwd = P_net / (1 - |Gamma|^2), peak voltage/current and loss at Gamma_max (option a, on-module "
          "fixed pre-match) or at the antenna mismatch (option b), with directivity stated at the operating |Gamma|; "
          "Gamma_max and the option are owner questions (OQ-A907-11, LOCK-1).",
          "coupler rated at the coupler-plane |Gamma|"),
        R("A910-A909-02", "A9-07 IDA7-21", "replace", rf.format("RFQ-04-R09") + "/requirement",
          "with coverage factor.",
          "with coverage factor, and the directivity D at the operating |Gamma|; the P_net directivity/mismatch term "
          "(A9-07 IDA7-21; A9-04 UB-RF-04) needs D >= D_min, D_min frozen at LOCK-2.",
          "directivity term demanded"),
        R("A910-A909-03", "A9-07 H3-A907-04", "replace", rf.format("RFQ-04-R11") + "/requirement",
          "no uncompensated hard line across the moving stage.",
          "no uncompensated hard line across the moving stage; rated for forward power, peak voltage/current and loss "
          "at the coupler-plane |Gamma| (A9-07 H3-A907-04, REV-33, A9H-INS-15).", "coax rated at coupler-plane |Gamma|"),
        R("A910-A909-04", "A9-07 H3-A907-15, OQ-A907-11", "append", "/packages[id=RFQ-04]/requirements", None,
          {"id": "RFQ-04-R15", "title": "optional on-module fixed pre-match (option line)",
           "requirement": "Optional quotation line: a fixed on-module 13.56 MHz pre-match / impedance transformation "
                          "network (plus a sham-equivalent network) holding the coax/coupler segment at |Gamma| <= "
                          "Gamma_max, quoted only for the case that OQ-A907-11 option a is adopted; the tunable match "
                          "stays off-platform (A9.1 A9-03-matching).",
           "value": "TBD - requires the owner answer to OQ-A907-11 (option a/b, Gamma_max at LOCK-1) and the A9-03 "
                    "antenna impedance", "units": "-", "basis": "A9-07 H3-A907-15",
           "sources": [{"type": "deliverable_item", "key": "H2A9", "path": H2A9, "id": "H3-A907-15",
                        "pointer": "/h3_inputs/4"},
                       {"type": "a9_1", "id": "A9-03-matching", "quote": "Baseline: off the moving thrust-stand "
                        "platform.", "path": A91_MD_REL}],
           "evidence_class": None, "status": "TBD", "freeze_point": "LOCK-1", "applies_to": ["hall_icp_neutralizer"],
           "note": "added in A9-10 (quotation only; no purchase order)"},
          "optional pre-match line"),
        R("A910-A909-05", "A9-08 design_cases.tank_volume (323 K)", "set", xe.format("RFQ-07-R04") + "/value",
          "PENDING docs/budgets/" + "xe" + "_ledger_a9/ (A9-08: final tank ranges incl. residual (row 45) and "
          "reserve (row 43))",
          {"V_min_323K_l_by_case_and_MEOP_axis": {
              "2 kg": {"75bar": 3.25675, "100bar": 1.77865, "150bar": 1.1975, "187bar": 1.09371},
              "5 kg": {"75bar": 8.14187, "100bar": 4.44663, "150bar": 2.99374, "187bar": 2.73428},
              "10 kg": {"75bar": 16.2837, "100bar": 8.89326, "150bar": 5.98748, "187bar": 5.46856}},
           "residual_kg_inside_case": {"2 kg": 0.0392157, "5 kg": 0.0980392, "10 kg": 0.196078},
           "reserve_kg_inside_case": {"2 kg": 0.326797, "5 kg": 0.816993, "10 kg": 1.63399},
           "MEOP": "TBD - requires quotations (XA9-28); the pressures are a sensitivity axis, not a MEOP choice",
           "source": XE_A9_JSON + " design_cases.tank_volume / reserve_residual_split (case = LOADED Xe, XA9Q-01 "
                     "PROPOSED reading)"},
          "tank ranges at 323 K from A9-08", numeric=True,
          source={"file": XE_A9_JSON, "ptr": "/design_cases/tank_volume/rows[0]/V_min_323K_l", "value": 3.25675}),
        R("A910-A909-06", "A9-08 design_cases.tank_volume (323 K)", "set", xe.format("RFQ-07-R04") + "/status",
          "PENDING", "COPIED_VERIFIED", "RFQ-07-R04 status"),
        R("A910-A909-07", "A9-08 design_cases.tank_volume (323 K)", "set", xe.format("RFQ-07-R04") + "/evidence_class",
          None, "model-derived", "RFQ-07-R04 evidence class"),
        R("A910-A909-08", "A9-08 design_cases.tank_volume (323 K)", "set", xe.format("RFQ-07-R04") + "/units",
          "L, bar", "L (V_min at 323.15 K incl. EOS density uncertainty), kg", "RFQ-07-R04 units"),
        R("A910-A909-09", "A9-06 line_checks AL-08", "set", xe.format("RFQ-07-R10") + "/value",
          "PENDING docs/budgets/mass_a9/ (A9-06: Xe hardware mass reconciliation)",
          {"AL-08_owner_allocation_kg": 1.5, "AL-08_evidence_floor_kg": 5.044,
           "state": "ALLOCATION_BELOW_EVIDENCE_FLOOR",
           "note": "owner v0 allocation (row 54) below the H2-7 analog floor (CBE); re-allocation is owner question "
                   "MQ-05; supplier states mass per case",
           "source": MASS_A9 + " line_checks[line=AL-08]"},
          "Xe hardware mass context from A9-06", numeric=True,
          source={"file": MASS_A9, "ptr": "/line_checks[line=AL-08]/evidence_floor_kg", "value": 5.044}),
        R("A910-A909-10", "A9-06 line_checks AL-08", "set", xe.format("RFQ-07-R10") + "/status", "PENDING",
          "COPIED_VERIFIED", "RFQ-07-R10 status"),
        R("A910-A909-11", "A9-06 line_checks AL-08", "set", xe.format("RFQ-07-R10") + "/evidence_class", None,
          "owner-allocation", "RFQ-07-R10 evidence class"),
        R("A910-A909-12", "A9-06 line_checks AL-06", "set", rf.format("RFQ-04-R14") + "/value",
          "PENDING docs/budgets/mass_a9/ (A9-06: RF generator/matching mass reconciliation)",
          "TBD - requires supplier mass data; A9-06 records the owner v0 allocation (row 54, 1.5 kg) as "
          "ALLOCATION_UNVERIFIABLE_TBD (no evidence floor): " + MASS_A9 + " line_checks[line=AL-06]",
          "RF generator mass context re-evaluated"),
        R("A910-A909-13", "A9-06 line_checks AL-06", "set", rf.format("RFQ-04-R14") + "/status", "PENDING", "TBD",
          "RFQ-04-R14 status"),
        R("A910-A909-15", "A9-06 merged (no ground module masses)", "set",
          "/packages[id=RFQ-01]/requirements[id=RFQ-01-R04]/value",
          "PENDING docs/budgets/mass_a9/ (A9-06: module masses and CG per configuration)",
          "TBD - requires the C1 / ICP / sham module drawings (ICD ICP-08); A9-06 (" + MASS_A9 + ", merged) books "
          "flight allocations only, no ground module masses/CG", "RFQ-01-R04 re-evaluated"),
        R("A910-A909-16", "A9-06 merged", "set", "/packages[id=RFQ-01]/requirements[id=RFQ-01-R04]/status",
          "PENDING", "TBD", "RFQ-01-R04 status"),
        R("A910-A909-17", "A9-07 merged (requirements, no drawings)", "set",
          "/packages[id=RFQ-01]/requirements[id=RFQ-01-R13]/value",
          "PENDING docs/hardware/h2_a9_revisions/ (A9-07: KC-1 / downstream ICP fixture drawings)",
          "TBD - requires the KC-1 / downstream ICP fixture drawings; A9-07 (" + H2A9 + ", merged) gives the "
          "requirements (REV-29..36: H-1 bolted, KC-1 carries C1 module / ICP module / sham, >= 25 kg stand), not "
          "drawings", "RFQ-01-R13 re-evaluated"),
        R("A910-A909-18", "A9-07 merged", "set", "/packages[id=RFQ-01]/requirements[id=RFQ-01-R13]/status",
          "PENDING", "TBD", "RFQ-01-R13 status"),
        R("A910-A909-19", "A9-08 merged (XE_REFERENCE term)", "replace",
          "/packages[id=RFQ-02]/requirements[id=RFQ-02-R07]/value",
          "PENDING docs/budgets/" + "xe" + "_ledger_a9/ (A9-08: XE_REFERENCE term)",
          "the XE_REFERENCE term booked by A9-08 (" + XE_A9_JSON + "; structure booked, flow TBD)",
          "RFQ-02-R07 re-evaluated"),
        R("A910-A909-20", "A9-06 line_checks AL-05", "set", "/packages[id=RFQ-05]/requirements[id=RFQ-05-R12]/value",
          "PENDING docs/budgets/mass_a9/ (A9-06: ICP neutralizer mass reconciliation)",
          "TBD - requires supplier mass data; A9-06 records the owner v0 ICP-neutralizer allocation (row 54, 2.0 kg) "
          "as ALLOCATION_UNVERIFIABLE_TBD (no evidence floor): " + MASS_A9 + " line_checks[line=AL-05]",
          "RFQ-05-R12 re-evaluated"),
        R("A910-A909-21", "A9-06 line_checks AL-05", "set", "/packages[id=RFQ-05]/requirements[id=RFQ-05-R12]/status",
          "PENDING", "TBD", "RFQ-05-R12 status"),
        R("A910-A909-22", "A9-08 design_cases (case content)", "replace",
          "/packages[id=RFQ-07]/requirements[id=RFQ-07-R03]/note",
          "final tank ranges PENDING docs/budgets/" + "xe" + "_ledger_a9/ (A9-08)",
          "final tank ranges: RFQ-07-R04 (A9-08 design_cases, imported in A9-10; A9-08 reads each case as LOADED Xe "
          "incl. reserve and residual, XA9Q-01 PROPOSED, and adds the EOS density uncertainty, so its V_min governs)",
          "RFQ-07-R03 note re-evaluated"),
        R("A910-A909-23", "A9-08 design_cases (case content)", "replace", "/derived/xe_tank_indicative_volume_L/note",
          "final tank ranges PENDING docs/budgets/" + "xe" + "_ledger_a9/ (A9-08)",
          "final tank ranges: RFQ-07-R04 (A9-08 design_cases, imported in A9-10)", "derived note re-evaluated"),
        R("A910-A909-24", "A9.1 ICP-46 (A9-07 K7)", "replace", "/packages[id=RFQ-08]/requirements[id=RFQ-08-R12]/value",
          "PENDING docs/hardware/h2_a9_revisions/ (A9-07: H2-2/H2-4 revision)",
          "the H2-2 / H2-4 revision in " + H2A9 + " (merged: keeper isolation basis 900 V, 1.0 kV DC development hipot, "
          "separate 600 V pulse test per A9.1 ICP-46; the break voltage itself is not given)",
          "RFQ-08-R12 re-evaluated"),
        R("A910-A909-25", "A9-08 merged", "set", "/m16_impact[0]/blocking_item", "PENDING A9-08 final ranges",
          "MEOP / tank selection from quotations (XA9-28); the A9-08 design-case volumes are in RFQ-07-R04",
          "M16 blocking item re-evaluated"),
        R("A910-A909-26", "A9-07 merged", "set", "/m16_impact[7]/blocking_item", "PENDING A9-07 fixture drawings",
          "KC-1 / module interface drawings (A9-07 REV-29..36 give the requirements, not drawings)",
          "M16 blocking item re-evaluated"),
        R("A910-A909-27", "A9-06 merged (no ground module masses)", "set", "/interface_demands[id=IF-RFQ-01]/status",
          "PENDING", "OPEN - A9-06 (merged) books flight allocations only; ground module masses/CG TBD - requires the "
          "module drawings (ICP-08)", "IF-RFQ-01 re-evaluated"),
        R("A910-A909-28", "A9-07 merged (requirements, no drawings)", "set", "/interface_demands[id=IF-RFQ-03]/status",
          "PENDING", "PARTIAL - A9-07 (merged) supplies the fixture / external-C1 / >= 50 K thermal requirements "
          "(REV-13..50) consumed here; drawings TBD", "IF-RFQ-03 re-evaluated"),
        R("A910-A909-29", "A9-08 design_cases", "set", "/interface_demands[id=IF-RFQ-05]/status", "PENDING",
          "PARTIAL - A9-08 design-case volumes at 323 K and the residual/reserve split imported into RFQ-07-R04 "
          "(A9-10); MEOP and XE_REFERENCE flow TBD (XA9-28; A9-01 reference point)", "IF-RFQ-05 re-evaluated"),
        R("A910-A909-30", "OQ-INT-03 re-evaluation", "set", "/pending_lanes_status_a9_10", ABSENT,
          "A9-06, A9-07 and A9-08 are merged and verified; every reference to them in this deliverable was re-evaluated "
          "in A9-10 (" + RECORD_REL + " pending_reevaluation / interface_demand_matrix)", "parallel lanes merged"),
        R("A910-A909-31", "A9-08 merged", "replace", "/open_owner_questions[id=OQ-RFQ-09]/proposed_answer",
          "final basis PENDING A9-08",
          "final basis after the quotations (A9-08 design-case volumes at 323 K now in RFQ-07-R04; MEOP XA9-28 TBD)",
          "OQ-RFQ-09 proposed answer re-evaluated (question stays OPEN)"),
        R("A910-A909-14", "row 111 (H2-4 28 V vs 100 V)", "merge", "/open_owner_questions[id=OQ-RFQ-05]",
          {"status": ABSENT, "resolved_by": ABSENT},
          {"status": "ANSWERED_BY_OWNER_ROW_111",
           "resolved_by": "docs/decisions/OD_2026_09_29_owner_answers_147.json row 111 (REGULATED 100 V internal "
                          "propulsion bus for the breadboard/PPU architecture): the H2-4 H3-PPU-05 '28 V class' input "
                          "is superseded for A9 (A9-02 h2_4_revision_flags H3-PPU-05 NEEDS_REVISION; A9-07 REV "
                          "entries); recorded as resolved by row 111 in A9-10"},
          "H2-4 28 V vs row-111 100 V conflict recorded as resolved by row 111"),
    ]


def records() -> dict:
    return {"A9-01": _a901(), "A9-02": _a902(), "A9-03": _a903(), "A9-04": _a904(), "A9-05ev": _a905ev(),
            "A9-05vi": _a905vi(), "A9-06": _a906(), "A9-07": _a907(), "A9-08": _a908(), "A9-09": _a909()}


# ------------------------------------------------------------------------------------------------------ pointers
_SEG = re.compile(r"/([^/\[]*)((?:\[[^\]]*\])*)")


def _parse(ptr: str):
    if ptr in ("", "/"):
        return []
    segs = []
    pos = 0
    while pos < len(ptr):
        m = _SEG.match(ptr, pos)
        if not m or m.end() == pos:
            raise OverlayError(f"bad pointer {ptr!r}")
        segs.append(("key", m.group(1)))
        for sel in re.findall(r"\[([^\]]*)\]", m.group(2)):
            segs.append(("sel", sel))
        pos = m.end()
    return segs


def resolve(doc, ptr: str):
    """Return [(concrete_path, parent, key)] for every location matched by ``ptr`` (parent[key] is the target)."""
    segs = _parse(ptr)
    cur = [("", None, None, doc)]
    for kind, v in segs:
        nxt = []
        for path, _p, _k, node in cur:
            if kind == "key":
                if not isinstance(node, dict):
                    raise OverlayError(f"{ptr}: {path} is not an object")
                nxt.append((path + "/" + v, node, v, node.get(v, ABSENT)))
            else:
                if not isinstance(node, list):
                    raise OverlayError(f"{ptr}: {path} is not a list")
                if v == "*":
                    nxt += [(path + f"[{i}]", node, i, x) for i, x in enumerate(node)]
                elif re.fullmatch(r"\d+", v):
                    i = int(v)
                    if i >= len(node):
                        raise OverlayError(f"{ptr}: index {i} out of range")
                    nxt.append((path + f"[{i}]", node, i, node[i]))
                else:
                    f, _, val = v.partition("=")
                    hits = [i for i, x in enumerate(node) if isinstance(x, dict) and str(x.get(f)) == val]
                    if not hits:
                        raise OverlayError(f"{ptr}: no element with {f} == {val!r} under {path}")
                    i = hits[0]
                    nxt.append((path + f"[{i}]", node, i, node[i]))
        cur = nxt
    return [(p, par, k) for p, par, k, _ in cur]


def _strings(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, path + "/" + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings(v, path + f"[{i}]")
    elif isinstance(node, str):
        yield path, node


def _set_at(doc, path):
    """Return (parent, key) for a concrete path produced by _strings/resolve."""
    toks = re.findall(r"/([^/\[]+)|\[(\d+)\]", path)
    cur = doc
    for i, (k, idx) in enumerate(toks):
        last = i == len(toks) - 1
        key = k if k else int(idx)
        if last:
            return cur, key
        cur = cur[key]
    raise OverlayError(f"empty path {path!r}")


# ------------------------------------------------------------------------------------------------------ apply
def apply(key: str, doc: dict, only_prefix: str = None, exclude_prefix: str = None, attach: bool = True,
          copy_doc: bool = True) -> dict:
    """Apply the declared records of deliverable ``key`` and attach the A9-10 section (once); returns the document.

    By default the builder's document is deep-copied first, so module-level constants a builder may share into its
    document are never mutated (the build stays a pure function)."""
    if copy_doc:
        doc = copy.deepcopy(doc)
    recs = records()[key]
    applied = doc.setdefault("__a9_10_applied__", [])
    for r in recs:
        ptr = r["ptr"]
        if r["op"] != "code":
            if only_prefix is not None and not (ptr or "").startswith(only_prefix):
                continue
            if exclude_prefix is not None and (ptr or "").startswith(exclude_prefix):
                continue
        elif only_prefix is not None:
            continue
        n = _apply_one(doc, r)
        applied.append({"cid": r["cid"], "driver": r["driver"], "op": r["op"], "ptr": ptr, "count": n,
                        "summary": r["summary"]})
    if attach:
        done = doc.pop("__a9_10_applied__")
        ids = [a["cid"] for a in done]
        want = [r["cid"] for r in recs]
        if sorted(ids) != sorted(want):
            raise OverlayError(f"{key}: applied {sorted(ids)} != declared {sorted(want)}")
        order = {c: i for i, c in enumerate(want)}
        done.sort(key=lambda a: order[a["cid"]])
        doc["a9_10_reconciliation"] = {
            "lane": LANE, "record": RECORD_REL, "overlay": OVERLAY_REL,
            "a9_1_decision": {"path": A91_REL, "sha256": A91_SHA, "verbatim": A91_MD_REL, "verbatim_sha256": A91_MD_SHA},
            "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
            "rule": "every change below has a driver (A9.1 decision id, verified lane item, integration open item or "
                    "A9-10 self-reference); no number changes without an A9.1 decision or a verified upstream value; "
                    "no winner; no prediction",
            "changes": done}
    return doc


def _apply_one(doc, r) -> int:
    op, ptr = r["op"], r["ptr"]
    if op == "code":
        p = os.path.join(ROOT, r["file"])
        with open(p, encoding="utf-8") as f:
            if r["marker"] not in f.read():
                raise OverlayError(f"{r['cid']}: marker {r['marker']!r} not in {r['file']}")
        return 0
    if op == "gsub":
        base = resolve(doc, ptr) if ptr else [("", None, None)]
        n = 0

        def _walk(node):
            nonlocal n
            items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
            for kk, v in list(items):
                if isinstance(v, str):
                    if r["old"] in v:
                        node[kk] = v.replace(r["old"], r["new"])
                        n += 1
                elif isinstance(v, (dict, list)):
                    _walk(v)
        for _bpath, par, k in base:
            node = doc if par is None else par[k]
            if isinstance(node, str):
                if r["old"] in node:
                    par[k] = node.replace(r["old"], r["new"])
                    n += 1
            else:
                _walk(node)
        if n == 0 and not r.get("optional"):
            raise OverlayError(f"{r['cid']}: gsub matched nothing: {r['old']!r}")
        return n
    locs = resolve(doc, ptr)
    n = 0
    for path, par, k in locs:
        cur = par.get(k, ABSENT) if isinstance(par, dict) else par[k]
        if op == "set":
            if cur != r["old"]:
                raise OverlayError(f"{r['cid']}: {path} is {cur!r:.120}, expected {r['old']!r:.120}")
            par[k] = copy.deepcopy(r["new"])
        elif op == "replace":
            if not isinstance(cur, str) or r["old"] not in cur:
                raise OverlayError(f"{r['cid']}: {path} does not contain {r['old']!r:.100}")
            par[k] = cur.replace(r["old"], r["new"])
        elif op == "append":
            if not isinstance(cur, list):
                raise OverlayError(f"{r['cid']}: {path} is not a list")
            nid = r["new"].get("id") if isinstance(r["new"], dict) else None
            if nid is not None and any(isinstance(x, dict) and x.get("id") == nid for x in cur):
                raise OverlayError(f"{r['cid']}: {path} already has id {nid}")
            if nid is None and r["new"] in cur:
                raise OverlayError(f"{r['cid']}: {path} already contains the element")
            cur.append(copy.deepcopy(r["new"]))
        elif op == "merge":
            if not isinstance(cur, dict):
                raise OverlayError(f"{r['cid']}: {path} is not an object")
            for kk, ov in r["old"].items():
                if cur.get(kk, ABSENT) != ov:
                    raise OverlayError(f"{r['cid']}: {path}/{kk} is {cur.get(kk, ABSENT)!r:.80}, expected {ov!r:.80}")
            for kk, nv in r["new"].items():
                cur[kk] = copy.deepcopy(nv)
        else:
            raise OverlayError(f"{r['cid']}: unknown op {op!r}")
        n += 1
    return n


# ------------------------------------------------------------------------------------------------------ markdown
def _c(v) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def md_section(doc: dict) -> list:
    sec = doc.get("a9_10_reconciliation")
    if not sec:
        raise OverlayError("document carries no a9_10_reconciliation section (apply() not run)")
    L = ["", "## A9-10 reconciliation (fo_a9_10_integration)", "",
         f"Changes applied by A9-10 after this lane's verified build (record `{sec['record']}`, overlay "
         f"`{sec['overlay']}`). A9.1 decision `{sec['a9_1_decision']['path']}` (sha256 "
         f"`{sec['a9_1_decision']['sha256']}`). A9 stays {sec['a9_status']}; no winner; no prediction.", "",
         "| change | driver | op | pointer | count | summary |", "|---|---|---|---|---|---|"]
    for c in sec["changes"]:
        L.append(f"| {c['cid']} | {_c(c['driver'])} | {c['op']} | `{_c(c['ptr'])}` | {c['count']} | "
                 f"{_c(c['summary'])} |")
    return L
