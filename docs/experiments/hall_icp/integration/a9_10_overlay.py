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
M16_V3 = "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"
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
          "PENDING docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json (A9-10 refresh); PENDING "
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
    out = {"A9-01": _a901(), "A9-02": _a902(), "A9-03": _a903(), "A9-04": _a904(), "A9-05ev": _a905ev(),
           "A9-05vi": _a905vi(), "A9-06": _a906(), "A9-07": _a907(), "A9-08": _a908(), "A9-09": _a909()}
    for extra in (_repair_code(), _repair(), _repair2(), _repair3(), _repair4()):
        for k, recs in extra.items():
            out[k] = out[k] + [dict(r) for r in recs]
    return out


# ------------------------------------------------------------------------------------------------------ repair
# A9-10 review repair (OQ-INT-03 / interface-demand reconciliation): each PENDING field or demand whose target
# lane (or an A9.1 decision) now supplies the value is filled or classified SATISFIED / PARTIAL with the exact
# locator; the rest carry the precise remaining reason. 'old' pins the pre-repair value (checked on apply).
def _repair() -> dict:
    return {'A9-01': [{'cid': 'A910-R01-01',
                       'driver': 'OQ-INT-03 (A9-04 readiness_n)',
                       'op': 'merge',
                       'ptr': '/items[id=ITM-39]',
                       'old': {'value': 'TBD - requires the A9-04 budget',
                               'source': 'PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04)'},
                       'new': {'value': 'TBD - requires a LOCK-1 choice of K and r (RR-HI-06); the A9-04 budget (readiness_n) '
                                        'consumes the re-mount series as s_d at LOCK-2 but sets no K or r',
                               'source': 'RR-HI-06 (this framework); '
                                         'docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json '
                                         'readiness_n (A9-04, merged: no K or r defined)'},
                       'summary': 'ITM-39 K, r: A9-04 defines no K or r -> LOCK-1 item of this framework'},
                      {'cid': 'A910-R01-02',
                       'driver': 'OQ-INT-03 (A9-02 SLOTS / BASE_SLOTS)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-01]',
                       'old': {'status': 'PENDING'},
                       'new': {'status': 'SATISFIED by A9-02: one slot per active load in abep_sim/bus_boundary_a9.py SLOTS / '
                                         'BASE_SLOTS (A9-02, merged) (hall_discharge, hall_magnet_inner/outer/trim, '
                                         'c1_heater, c1_keeper, c1_common_tie, filter_getter, icp_rf_source, '
                                         'icp_matching_network, icp_collector_bias (variants: icp_assist_magnet, '
                                         'active_cooling, flow_control_icp_feed only for G-ATM / G-XE), '
                                         'flow_control_atmospheric, flow_control_xe, compressor, thermal_control, '
                                         'housekeeping_controls, reserved_dc_port); start-up transient metering = the gate '
                                         'quantity P_bus,1ms,max (A9.1 OQ-A902-01, p_bus_1ms_max()); PARTIAL_BOUNDARY status '
                                         '(row 22); per-slot W values TBD - measurement'},
                       'summary': 'IF-HI-01 satisfied'},
                      {'cid': 'A910-R01-03',
                       'driver': 'OQ-INT-03 (A9-02 SLOTS)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-02]',
                       'old': {'status': 'PENDING'},
                       'new': {'status': 'SATISFIED by A9-02: slot ids of abep_sim/bus_boundary_a9.py SLOTS / BASE_SLOTS '
                                         '(A9-02, merged) (installed per configuration in BASE_SLOTS, variants in '
                                         'VARIANT_OPTIONS)'},
                       'summary': 'IF-HI-02 satisfied'},
                      {'cid': 'A910-R01-04',
                       'driver': 'OQ-INT-03 (A9-03 items)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-03]',
                       'old': {'status': 'PENDING'},
                       'new': {'status': 'SATISFIED by A9-03 (schemas/interfaces/icp_neutralizer_icd_v1.json): carrier datum '
                                         'KC-1 and exchange series ICP-06 / ICP-39, MODULE_ID ICP-33, matched shams ICP-09 / '
                                         'ICP-18, channels ICP-34 (incl. RF forward/reflected, interlock, collector V/I, '
                                         'temperatures), floating body ICP-20 with separately metered collector ICP-21, '
                                         'Hall-exhaust-to-ICP pressure interface ICP-27, gas port ICP-26 (capped in G-REUSE); '
                                         'dimensions and ranges stay LOCK-1 items'},
                       'summary': 'IF-HI-03 satisfied (items defined)'},
                      {'cid': 'A910-R01-05',
                       'driver': 'OQ-INT-03 (A9-03 items; GD-01)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-04]',
                       'old': {'status': 'PENDING'},
                       'new': {'status': 'PARTIAL: A9-03 item ids ICP-01..ICP-46 exist and are citable for RR-HI-02 / '
                                         'SC-HI-SRC-ICP; they are not frozen - the freeze is gate deadline GD-01 (before '
                                         'HI-S1)'},
                       'summary': 'IF-HI-04 partial (ids exist, freeze before HI-S1)'},
                      {'cid': 'A910-R01-06',
                       'driver': 'OQ-INT-03 (A9-04 measurement_chains, stop_rules, readiness_n)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-06]',
                       'old': {'status': 'PENDING'},
                       'new': {'status': 'PARTIAL: A9-04 '
                                         '(docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json) '
                                         'supplies measurement chains per DQ-HI-* (measurement_chains), stop-rule forms '
                                         '(stop_rules SR-C-SIGN / SR-C-MARGIN; A9.1 UBQ-09 selects SR-C-MARGIN) and the n '
                                         'rule (readiness_n); every uncertainty value and margin number is TBD until LOCK-2'},
                       'summary': 'IF-HI-06 partial'},
                      {'cid': 'A910-R01-07',
                       'driver': 'OQ-INT-03 (A9-05 extraction)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-07]',
                       'old': {'status': 'PENDING'},
                       'new': {'status': 'SATISFIED by A9-05: Takahashi 2024 extraction with page / figure locators '
                                         '(docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json extraction '
                                         'TK-01..TK-74, digitized_fig4; published analog, context only) and the '
                                         'validation-input list '
                                         '(docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json, '
                                         'row 145)'},
                       'summary': 'IF-HI-07 satisfied'},
                      {'cid': 'A910-R01-08',
                       'driver': 'OQ-INT-03 (A9-07 REV-29..34)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-09]',
                       'old': {'status': 'OPEN (revision needed)'},
                       'new': {'status': 'SATISFIED at requirement level by A9-07 '
                                         '(docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json REV-29..REV-34: H-1 stays '
                                         'bolted, downstream module on KC-1, 3-point seat, >= 25 kg payload, SVC-A9 matched '
                                         'shams, matching network off the platform); seat geometry / preload stay LOCK-1 '
                                         '(H2-6 v1 unchanged)'},
                       'summary': 'IF-HI-09 satisfied (A9-07 revision)'},
                      {'cid': 'A910-R01-09',
                       'driver': 'OQ-INT-03 (A9-07 REV-01/03/13/66)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-10]',
                       'old': {'status': 'OPEN (revision needed)'},
                       'new': {'status': 'SATISFIED at requirement level by A9-07 '
                                         '(docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json REV-01, REV-03, REV-13, '
                                         'REV-66: external C1 on KC-1, no central cathode, IP-EXIT / IP-NEU datum); FEMM of '
                                         'MC-1 stays open (IDA7-17)'},
                       'summary': 'IF-HI-10 satisfied (A9-07 revision)'},
                      {'cid': 'A910-R01-10',
                       'driver': 'OQ-INT-03 (A9-07 REV-51/62)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-11]',
                       'old': {'status': 'OPEN'},
                       'new': {'status': 'PARTIAL: A9-07 REV-62 / REV-51 revise the requirement (flight-representative '
                                         'breadboard discharge supply fed from the 100 V internal bus, row 111); eta_d and '
                                         'transients TBD - require the breadboard measurement before LOCK-2 (row 113, GD-14)'},
                       'summary': 'IF-HI-11 partial'},
                      {'cid': 'A910-R01-11',
                       'driver': 'OQ-INT-03 (A9-07 REV-40/45)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-12]',
                       'old': {'status': 'OPEN (revision needed)'},
                       'new': {'status': 'SATISFIED at requirement level by A9-07 '
                                         '(docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json REV-40: >= 50 K below '
                                         'validated limits + 20 % heat-load margin; REV-45: BN wall worst corner <= 850 degC '
                                         'with 1.2 x heat loads); the thermal solution itself is open (H2-5 v1 unchanged)'},
                       'summary': 'IF-HI-12 satisfied (A9-07 revision)'},
                      {'cid': 'A910-R01-12',
                       'driver': 'OQ-INT-03 (A9-03 ICP-34; A9-07 A9H-INS-01)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-13]',
                       'old': {'status': 'PARTIAL (existing INS ids verified; ICP channels PENDING)'},
                       'new': {'status': 'PARTIAL: existing INS ids verified; the ICP channel list is defined by A9-03 ICP-34 '
                                         'and the coupler instrument by A9-07 A9H-INS-01; no INS ids are assigned to the new '
                                         'channels yet (instrumentation list revision, LOCK-1)'},
                       'summary': 'IF-HI-13 channels defined; INS numbering open'},
                      {'cid': 'A910-R01-13',
                       'driver': 'OQ-INT-03 (A9-08 XA9-21, XA9-33, XA9-IF-15)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-14]',
                       'old': {'status': 'OPEN'},
                       'new': {'status': 'PARTIAL: A9-08 (docs/budgets/xe' '_ledger_a9/xe' '_ledger_a9_v1.json) books C1 phases '
                                         'under PHASE_TOTAL_FLOW (row 42), the ICP Xe term only in G-XE (G-REUSE XA9-21 = 0 '
                                         'mg/s) and carries XE_REFERENCE (XA9-33) with its size TBD; the 120 s x 2 dwell (row '
                                         '93) enters via the A9-02 start-up template C-S4 (XA9-IF-15)'},
                       'summary': 'IF-HI-14 partial'},
                      {'cid': 'A910-R01-14',
                       'driver': 'OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-16]',
                       'old': {'status': 'PENDING (hardware not built)'},
                       'new': {'status': 'OPEN - hardware not built: H-1 serial identity, anode / wall freeze (GD-02, GD-03, '
                                         'before HI-S1) and B(z) sensitivity (GD-11) need H-1'},
                       'summary': 'IF-HI-16 precise reason'},
                      {'cid': 'A910-R01-15',
                       'driver': 'OQ-INT-03 (A9-06 MA9-ID-19)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-HI-17]',
                       'old': {'status': 'PENDING'},
                       'new': {'status': 'PARTIAL: A9-06 (docs/budgets/mass_a9/mass_a9_v1.json MA9-ID-19) supplies the '
                                         'item-delta set (ICP adds A9B-17..A9B-22; C1 variant adds A9B-C01..A9B-C06); masses '
                                         'TBD (owner allocations and evidence floors only, no CBE)'},
                       'summary': 'IF-HI-17 partial'}],
            'A9-02': [{'cid': 'A910-R02-01',
                       'driver': 'OQ-INT-03 (A9-03 ICP-13)',
                       'op': 'merge',
                       'ptr': '/items[id=A902-22]',
                       'old': {'source': 'PENDING docs/interfaces/icp_neutralizer/ (fixed vs auto-tuned match)'},
                       'new': {'source': 'schemas/interfaces/icp_neutralizer_icd_v1.json ICP-13 (A9-03, merged; A9.1 '
                                         'A9-03-matching fixes the location off the moving platform but not fixed vs '
                                         'auto-tuned; on-module pre-match OQ-A907-11 OPEN): TBD - requires the '
                                         'matching-network selection (RFQ-04)'},
                       'summary': 'A902-22 precise remaining reason'},
                      {'cid': 'A910-R02-02',
                       'driver': 'A9.1 OQ-A902-01 + OQ-INT-03 (A9-01 stage_map)',
                       'op': 'merge',
                       'ptr': '/interface_demands[1]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/prereg_framework/'},
                       'new': {'status': 'SATISFIED: stage map = A9-01 stage_map HI-ENG..HI-AO '
                                         '(docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json; '
                                         'score-bearing stages HI-CMP and HI-ABS evaluate DQ-HI-PBUS, a hard gate); the '
                                         'transient averaging window is frozen by A9.1 OQ-A902-01 (1 ms; no longer a LOCK-1 '
                                         'item)'},
                       'summary': 'A9-01 -> A9-02 demand satisfied'},
                      {'cid': 'A910-R02-03',
                       'driver': 'OQ-INT-03 (A9-03 items)',
                       'op': 'merge',
                       'ptr': '/interface_demands[3]',
                       'old': {'status': 'PENDING docs/interfaces/icp_neutralizer/'},
                       'new': {'status': 'PARTIAL: A9-03 (schemas/interfaces/icp_neutralizer_icd_v1.json) supplies matching '
                                         'location (ICP-13, A9.1 A9-03-matching), floating body and separately metered '
                                         'collector (ICP-20 / ICP-21), no assist magnet in v1 (ICP-32), passive cooling '
                                         'PROPOSED (ICP-38); generator DC input vs forward power, matching type and draw, and '
                                         'the collector V/I range are TBD - require the selected hardware (RFQ-04 / RFQ-05)'},
                       'summary': 'A9-03 -> A9-02 demand partial'},
                      {'cid': 'A910-R02-04',
                       'driver': 'OQ-INT-03 (A9-04 UB-P-*)',
                       'op': 'merge',
                       'ptr': '/interface_demands[5]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/uncertainty_budget/'},
                       'new': {'status': 'PARTIAL: A9-04 '
                                         '(docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json) '
                                         'defines the DQ-HI-PBUS chain terms UB-P-01..UB-P-07 and the stop-rule forms '
                                         '(stop_rules); values TBD - require certificates / S1a, numbers at LOCK-2'},
                       'summary': 'A9-04 -> A9-02 demand partial'},
                      {'cid': 'A910-R02-05',
                       'driver': 'OQ-INT-03 (A9-05 extraction)',
                       'op': 'merge',
                       'ptr': '/interface_demands[7]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/validation_inputs/ (+ '
                                         'docs/evidence/icp_neutralizer/)'},
                       'new': {'status': 'SATISFIED by A9-05: docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json '
                                         'extraction TK-20..TK-23, TK-27, TK-40 (13.56 MHz, 200 W, matching network, ~20 W '
                                         'absorbed, circuit) with page locators (published analog, reported; context only)'},
                       'summary': 'A9-05 -> A9-02 demand satisfied'},
                      {'cid': 'A910-R02-06',
                       'driver': 'OQ-INT-03 (A9-07 REV-51/68/69)',
                       'op': 'merge',
                       'ptr': '/interface_demands[9]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_4_ppu_bus/ (revision under A9-07)'},
                       'new': {'status': 'OPEN - A9-07 (docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json REV-51, REV-68, '
                                         'REV-69) revises H2-4 to the 100 V internal bus but gives no converter efficiency; '
                                         'TBD - requires the breadboard measurement (row 113) / quotations (RFQ-06)'},
                       'summary': 'H2-4 -> A9-02 precise reason'},
                      {'cid': 'A910-R02-07',
                       'driver': 'OQ-INT-03 (A9-06)',
                       'op': 'merge',
                       'ptr': '/interface_demands[12]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_7_mechanical_bom/; PENDING '
                                         'docs/budgets/mass_a9/mass_a9_v1.json (A9-06, merged)'},
                       'new': {'status': 'OPEN - A9-06 (docs/budgets/mass_a9/mass_a9_v1.json, merged) books owner allocations '
                                         'and evidence floors only; electronics CBE masses TBD - require quotations (RFQ-04 / '
                                         'RFQ-06); H2-7 v1 unchanged'},
                       'summary': 'H2-7 -> A9-02 precise reason'},
                      {'cid': 'A910-R02-08',
                       'driver': 'OQ-INT-03 (A9-07 REV-04/58)',
                       'op': 'merge',
                       'ptr': '/interface_demands[13]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (revision under A9-07)'},
                       'new': {'status': 'OPEN - A9-07 (REV-04 ceramic-insulated coil, REV-58 one slot per coil) revises H2-1 '
                                         'but gives no hot coil V / I / P; TBD - requires the coil design and S1a'},
                       'summary': 'H2-1 -> A9-02 precise reason'},
                      {'cid': 'A910-R02-09',
                       'driver': 'OQ-INT-03 (A9-07 REV-19/21/25/28)',
                       'op': 'merge',
                       'ptr': '/interface_demands[14]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_2_cathode_integration/'},
                       'new': {'status': 'OPEN - A9-07 (REV-19, REV-21, REV-25, REV-28) revises the C1 requirements (heater '
                                         'stated per step, pulsed ignition, 120 s x 2 dwell, selectable common tie) but gives '
                                         'no heater V / I / P, preheat duration or pulse energy; TBD - requires the C1 unit '
                                         'selection (RFQ-08)'},
                       'summary': 'H2-2 -> A9-02 precise reason'},
                      {'cid': 'A910-R02-10',
                       'driver': 'OQ-INT-03 (row 22; A9-07)',
                       'op': 'merge',
                       'ptr': '/interface_demands[16]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_3_gas_path_plenum/'},
                       'new': {'status': 'OPEN - the compressor ICD has not supplied the drive power (row 22, '
                                         'PARTIAL_BOUNDARY); A9-07 (REV-64, REV-65) gives no compressor or valve power'},
                       'summary': 'H2-3 -> A9-02 precise reason'},
                      {'cid': 'A910-R02-11',
                       'driver': 'OQ-INT-03 (A9-07 REV-40..50)',
                       'op': 'merge',
                       'ptr': '/interface_demands[18]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_5_thermal_network/'},
                       'new': {'status': 'OPEN - A9-07 (REV-40..REV-50) revises the thermal limits (>= 50 K) but gives no '
                                         'thermal_control load per step or active-cooling decision; TBD - requires the '
                                         'thermal model / S1b'},
                       'summary': 'H2-5 -> A9-02 precise reason'},
                      {'cid': 'A910-R02-12',
                       'driver': 'OQ-INT-03 (A9-08 XA9-IF-15)',
                       'op': 'merge',
                       'ptr': '/interface_demands[20]',
                       'old': {'status': 'PENDING docs/budgets/xe' '_ledger_a9/ (A9-08, merged)'},
                       'new': {'status': 'SATISFIED: consumed by A9-08 (docs/budgets/xe' '_ledger_a9/xe' '_ledger_a9_v1.json '
                                         'XA9-IF-15: start-up templates C-S2, C-S4, I-S3 booked under PHASE_TOTAL_FLOW)'},
                       'summary': 'A9-02 -> Xe ledger satisfied'},
                      {'cid': 'A910-R02-13',
                       'driver': 'OQ-INT-03 (A9-03 ICP-13)',
                       'op': 'merge',
                       'ptr': '/h3_inputs[id=H3-A902-03]',
                       'old': {'basis': 'PENDING docs/interfaces/icp_neutralizer/'},
                       'new': {'basis': 'schemas/interfaces/icp_neutralizer_icd_v1.json ICP-13 (A9.1 A9-03-matching: off the '
                                        'moving platform; fixed vs auto-tuned and the on-module pre-match OQ-A907-11 still '
                                        'open)'},
                       'summary': 'H3-A902-03 basis'}],
            'A9-03': [{'cid': 'A910-R03-01',
                       'driver': 'OQ-INT-03 (A9-04 UB-T-12)',
                       'op': 'merge',
                       'ptr': '/items[id=ICP-03]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/uncertainty_budget/ (alignment share of the '
                                         'C1-vs-ICP uncertainty budget)',
                               'tbd': '__ABSENT__'},
                       'new': {'status': 'TBD (rule LOCK-1, value LOCK-2)',
                               'tbd': 'TBD - requires the measured exchange series (ICP-39) and the carrier datum '
                                      'repeatability (row 122); A9-04 defines the alignment term UB-T-12 (thrust-axis cosine '
                                      'error per carrier exchange), value TBD'},
                       'summary': 'ICP-03 precise reason'},
                      {'cid': 'A910-R03-02',
                       'driver': 'OQ-INT-03 (A9-04 UB-RF-02..09)',
                       'op': 'merge',
                       'ptr': '/items[id=ICP-14]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/uncertainty_budget/ (u(P_fwd), u(P_refl), '
                                         'load-plane loss chain)',
                               'tbd': '__ABSENT__'},
                       'new': {'status': 'TBD (value LOCK-2)',
                               'tbd': 'TBD - requires coupler / sensor certificates and S1a dummy-load characterization; '
                                      'A9-04 allocates the chain terms UB-RF-02..UB-RF-07 (coupling factor, sensor '
                                      'calibration, directivity / mismatch, matching and cable loss, harmonics, '
                                      'repeatability) with the reference plane UB-RF-09, values TBD'},
                       'summary': 'ICP-14 precise reason'},
                      {'cid': 'A910-R03-03',
                       'driver': 'OQ-INT-03 (A9-02 SLOTS)',
                       'op': 'merge',
                       'ptr': '/items[id=ICP-24]',
                       'old': {'status': 'PENDING docs/architecture_comparison/power_boundary_a9/ + '
                                         'abep_sim/bus_boundary_a9.py (slot ids and ledger efficiencies)',
                               'tbd': '__ABSENT__'},
                       'new': {'status': 'PARTIAL (slot ids defined by A9-02; loads and efficiencies TBD)',
                               'tbd': 'TBD - requires the selected RF source, matching network and collector supply (RFQ-04 / '
                                      'RFQ-05) for the per-slot efficiencies and loads; slot ids defined in '
                                      'abep_sim/bus_boundary_a9.py: icp_rf_source, icp_matching_network, icp_collector_bias '
                                      '(variants: icp_assist_magnet, active_cooling, flow_control_icp_feed only for G-ATM / '
                                      'G-XE)'},
                       'summary': 'ICP-24 slot ids from A9-02'},
                      {'cid': 'A910-R03-04',
                       'driver': 'OQ-INT-03 (A9-01 DQ-HI-IGN, DR-07, MD-HI-02)',
                       'op': 'merge',
                       'ptr': '/items[id=ICP-35]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/prereg_framework/ (ICP ignition dwell/retry bound '
                                         'and start classification)',
                               'tbd': '__ABSENT__'},
                       'new': {'status': 'TBD (LOCK-1)',
                               'tbd': 'TBD - requires a LOCK-1 ICP ignition dwell / retry bound: A9-01 supplies the start '
                                      'classification (DQ-HI-IGN, DR-07, MD-HI-02) but no ICP dwell / retry bound'},
                       'summary': 'ICP-35 precise reason'},
                      {'cid': 'A910-R03-05',
                       'driver': 'OQ-INT-03 (A9-01 GD-17)',
                       'op': 'merge',
                       'ptr': '/items[id=ICP-41]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/prereg_framework/ (pre-registered '
                                         'start-up/thermal-state rule)',
                               'tbd': '__ABSENT__'},
                       'new': {'status': 'TBD (LOCK-1)',
                               'tbd': 'TBD - requires the A9-01 start-up / thermal-state rule, listed as gate deadline GD-17 '
                                      '(latest LOCK-1) and not yet written'},
                       'summary': 'ICP-41 precise reason'},
                      {'cid': 'A910-R03-06',
                       'driver': 'OQ-INT-03 (A9-01 stage_map, execution_design)',
                       'op': 'merge',
                       'ptr': '/items[id=ICP-42]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/prereg_framework/ (stage map and schedule)',
                               'tbd': '__ABSENT__'},
                       'new': {'status': 'SUPPLIED_BY_A9_01 (schedule form)',
                               'tbd': 'TBD - requires the LOCK-2 block count n and the seed (A9-01 GD-05, GD-09); the '
                                      'schedule form is supplied by A9-01: stage_map HI-ENG..HI-AO, execution_design '
                                      '(REF-COND installation with hall_c1_reference in every block, A9.1 HIQ-01; SEQ-A / '
                                      'SEQ-B; >= 6 blocks, A9.1 HIQ-02; NOT_TESTED after a stop, row 39)'},
                       'summary': 'ICP-42 schedule form supplied by A9-01'},
                      {'cid': 'A910-R03-07',
                       'driver': 'A9.1 A9-03-Vd + OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-02]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/prereg_framework/ (A9-01: V_d definition)'},
                       'new': {'status': 'SATISFIED by A9.1 A9-03-Vd (V_d = V_anode - V_electron-source-reference, primary '
                                         'controlled quantity; applied in ICP-22)'},
                       'summary': 'ID-02 satisfied by A9.1'},
                      {'cid': 'A910-R03-08',
                       'driver': 'OQ-INT-03 (A9-01)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-03]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/prereg_framework/ (A9-01: start rules)'},
                       'new': {'status': 'PARTIAL: A9-01 supplies the start / restart classification (DQ-HI-IGN, '
                                         'DQ-HI-RESTART, DR-07, MD-HI-02) and lists the start-up / thermal-state rule as '
                                         'GD-17 (LOCK-1); no ICP ignition dwell / retry bound yet (LOCK-1 item)'},
                       'summary': 'ID-03 partial'},
                      {'cid': 'A910-R03-09',
                       'driver': 'OQ-INT-03 (A9-01 stage_map)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-04]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/prereg_framework/ (A9-01: stage map)'},
                       'new': {'status': 'SATISFIED by A9-01: stage_map HI-ENG..HI-AO (Ar ENGINEERING_ONLY -> N2 -> O2 '
                                         'NO_ATOMIC_O -> AO) and execution_design (block template, SEQ-A / SEQ-B)'},
                       'summary': 'ID-04 satisfied'},
                      {'cid': 'A910-R03-10',
                       'driver': 'OQ-INT-03 (A9-02)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-07]',
                       'old': {'status': 'PENDING docs/architecture_comparison/power_boundary_a9/ (A9-02: slots) + '
                                         'abep_sim/bus_boundary_a9.py'},
                       'new': {'status': 'PARTIAL: slot ids and start-up transient accounting (P_bus,1ms,max, A9.1 '
                                         'OQ-A902-01; SEQUENCE_TEMPLATES, PROPOSED) defined in abep_sim/bus_boundary_a9.py; '
                                         'ledger efficiencies are explicit caller inputs, TBD - require the selected '
                                         'supplies'},
                       'summary': 'ID-07 partial'},
                      {'cid': 'A910-R03-11',
                       'driver': 'OQ-INT-03 (A9-04)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-09]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04: allocations)'},
                       'new': {'status': 'PARTIAL: A9-04 defines the RF chain terms UB-RF-02..UB-RF-09, the alignment term '
                                         'UB-T-12 and the stop-rule forms (A9.1 UBQ-09: SR-C-MARGIN); values LOCK-2'},
                       'summary': 'ID-09 partial'},
                      {'cid': 'A910-R03-12',
                       'driver': 'OQ-INT-03 (A9-05)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-11]',
                       'old': {'status': 'PENDING docs/evidence/icp_neutralizer/ (A9-05: evidence matrix) and PENDING '
                                         'docs/experiments/hall_icp/validation_inputs/'},
                       'new': {'status': 'SATISFIED by A9-05: docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json '
                                         '(extraction, survey, lawful_acquisition_list) and '
                                         'docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json '
                                         '(validation inputs, row 145)'},
                       'summary': 'ID-11 satisfied'},
                      {'cid': 'A910-R03-13',
                       'driver': 'OQ-INT-03 (A9-07 REV-03/66, IDA7-17)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-13]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (H2-1: revision for external C1 '
                                         '/ FEMM)'},
                       'new': {'status': 'PARTIAL: A9-07 REV-03 / REV-66 give the exit-face datum IP-EXIT; channel OD, MC-1 '
                                         'stray field in the ICP volume and at the C1 orifice TBD - require FEMM of MC-1 '
                                         '(A9-07 IDA7-17)'},
                       'summary': 'ID-13 partial'},
                      {'cid': 'A910-R03-14',
                       'driver': 'OQ-INT-03 (A9-07 REV-40/48/49)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-17]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_5_thermal_network/ (H2-5: >= 50 K revision (row 86))'},
                       'new': {'status': 'SATISFIED at requirement level by A9-07 (REV-40: >= 50 K + 20 % heat-load margin; '
                                         'REV-48: 20 / 40 / 60 degC mounting-interface and 25 / 50 / 100 W conducted-heat '
                                         'cases); sink measured per run (REV-49)'},
                       'summary': 'ID-17 satisfied (requirement)'},
                      {'cid': 'A910-R03-15',
                       'driver': 'OQ-INT-03 (A9-07 REV-30..32, REV-38)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-21]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ (H2-6: fixture revision for A9)'},
                       'new': {'status': 'PARTIAL: A9-07 REV-30..REV-32 and REV-38 (3-point seat, weight path, >= 25 kg '
                                         'payload, 1 % thrust test with maximum payload); seat dimensions and the '
                                         'per-configuration calibration procedure stay LOCK-1 items'},
                       'summary': 'ID-21 partial'},
                      {'cid': 'A910-R03-16',
                       'driver': 'OQ-INT-03 (A9-06 MA9-ID-20)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-23]',
                       'old': {'status': 'PENDING docs/hardware/h2/h2_7_mechanical_bom/ (H2-7: A9 amendment (A9-06))'},
                       'new': {'status': 'PARTIAL: A9-06 (MA9-ID-20) answers the flight allocations vs evidence floors '
                                         '(line_checks); module masses and CG per serial TBD - require S1a weighing'},
                       'summary': 'ID-23 partial'},
                      {'cid': 'A910-R03-17',
                       'driver': 'OQ-INT-03 (A9-02; OQ-A907-02)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-25]',
                       'old': {'status': 'PENDING docs/architecture_comparison/power_boundary_a9/ (A9-02: discharge slot '
                                         'limit)'},
                       'new': {'status': 'OPEN - A9-02 registers no stand discharge-slot limit: P_d,max needs the owner '
                                         'registration of the H-1 / discharge-supply envelope (OQ-A907-02)'},
                       'summary': 'ID-25 precise reason'},
                      {'cid': 'A910-R03-18',
                       'driver': 'OQ-INT-03 (ICP-43)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-26]',
                       'old': {'status': 'PENDING docs/architecture_comparison/power_boundary_a9/ (P_d,max; ICP-43)'},
                       'new': {'status': 'OPEN - ICP-43 needs P_d,max (ID-25, OQ-A907-02) and the collector / plume terms; '
                                         'not assessable before that registration'},
                       'summary': 'ID-26 precise reason'},
                      {'cid': 'A910-R03-19',
                       'driver': 'OQ-INT-03 (A9.1 ICP-45; OQ-A907-02)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-27]',
                       'old': {'status': 'PENDING docs/architecture_comparison/power_boundary_a9/ (A9-02: discharge slot '
                                         'I_d,max)'},
                       'new': {'status': 'OPEN - A9-02 registers no stand discharge-slot I_d,max: owner registration of the '
                                         'envelope pending (OQ-A907-02; A9.1 ICP-45: I_d,max from the registered H-1 / '
                                         'discharge-supply envelope)'},
                       'summary': 'ID-27 precise reason'},
                      {'cid': 'A910-R03-20',
                       'driver': 'OQ-INT-03 (A9-05 TK-21/27/52)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=ID-29]',
                       'old': {'status': 'PENDING docs/evidence/icp_neutralizer/ (A9-05: electron-current vs RF power '
                                         'evidence)'},
                       'new': {'status': 'PARTIAL: anchor only '
                                         '(docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json TK-52 I_D about 1 A '
                                         'at TK-21 200 W forward, TK-27 ~20 W absorbed; published analog, reported, context '
                                         'only, never scaled, A9.1 ICP-45); further RF / ICP plasma-cathode sources in '
                                         'lawful_acquisition_list LA-01..LA-09 await owner acquisition (A9.1 OQ-EV-02 order)'},
                       'summary': 'ID-29 partial'},
                      {'cid': 'A910-R03-21',
                       'driver': 'OQ-INT-03 (A9-02 SLOTS)',
                       'op': 'merge',
                       'ptr': '/m16_impact[m16_row=12]',
                       'old': {'blocking_item': 'PENDING A9-02 bus slots'},
                       'new': {'blocking_item': 'A9-02 slots defined (icp_rf_source, icp_matching_network, '
                                                'icp_collector_bias); blocking: supply selection and efficiencies TBD (RFQ-04 '
                                                '/ RFQ-06)'},
                       'summary': 'M16 row 12 blocking item re-evaluated'},
                      {'cid': 'A910-R03-22',
                       'driver': 'A9.1 OQ-A902-03 + OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/hard_incompatibility_check/checked[2]',
                       'old': {'finding': 'not assessable: bus slots PENDING A9-02 and no performance is predicted here; '
                                          'decided only by measurement against the full-system gate'},
                       'new': {'finding': 'not assessable: A9-02 defines the ICP bus slots and the residual P_ICP,available = '
                                          '1350 - P_common - P_Hall - P_other,active (A9.1 OQ-A902-03), but every load is TBD '
                                          'and no performance is predicted here; decided only by measurement against the '
                                          'full-system gate'},
                       'summary': 'hard-incompatibility finding re-evaluated'},
                      {'cid': 'A910-R03-23',
                       'driver': 'A9.1 OQ-A902-03',
                       'op': 'replace',
                       'ptr': '/items[id=ICP-24]/requirement',
                       'old': 'must fit inside the ~1.35 kW internal allocation (row 109);',
                       'new': 'must fit inside the ~1.35 kW internal allocation (row 109), i.e. inside P_ICP,available = 1350 '
                              '- P_common - P_Hall - P_other,active at every registered condition (A9.1 OQ-A902-03; A9-02 '
                              'icp_power_allocation_check; no fixed Hall/ICP split);',
                       'summary': 'ICP-24 cross-references the OQ-A902-03 residual form'}],
            'A9-04': [{'cid': 'A910-R04-01',
                       'driver': 'OQ-INT-03 (A9-02 SLOTS)',
                       'op': 'merge',
                       'ptr': '/items[id=UB-P-01]',
                       'old': {'value': 'PENDING abep_sim/bus_boundary_a9.py + '
                                        'docs/architecture_comparison/power_boundary_a9/ (slots incl. RF source/matching, '
                                        'collector/bias, C1 reference supplies)',
                               'evidence_class': None,
                               'status': 'PENDING',
                               'source': 'owner answers rows 66, 110'},
                       'new': {'value': 'S_A9 = the slot list of abep_sim/bus_boundary_a9.py (A9-02): hall_discharge, '
                                        'hall_magnet_inner, hall_magnet_outer, hall_magnet_trim, c1_heater, c1_keeper, '
                                        'c1_common_tie, filter_getter, icp_rf_source, icp_matching_network, '
                                        'icp_collector_bias (variants: icp_assist_magnet, active_cooling, '
                                        'flow_control_icp_feed only for G-ATM / G-XE), flow_control_atmospheric, '
                                        'flow_control_xe, compressor, thermal_control, housekeeping_controls, '
                                        'reserved_dc_port (installed per configuration in BASE_SLOTS)',
                               'evidence_class': 'owner-allocation',
                               'status': 'VERIFIED_INPUT',
                               'source': 'abep_sim/bus_boundary_a9.py SLOTS / BASE_SLOTS (A9-02, merged); owner answers rows '
                                         '66, 110'},
                       'summary': 'UB-P-01 filled from A9-02'},
                      {'cid': 'A910-R04-02',
                       'driver': 'OQ-INT-03 (A9-02 ledger)',
                       'op': 'merge',
                       'ptr': '/items[id=UB-P-06]',
                       'old': {'value': 'PENDING abep_sim/bus_boundary_a9.py + '
                                        'docs/architecture_comparison/power_boundary_a9/ (and docs/hardware/h2/h2_4_ppu_bus/; '
                                        'a LOCK-1 conditioning input, never a variance term; unmeasured loads -> '
                                        'PARTIAL_BOUNDARY (row 22))',
                               'status': 'PENDING'},
                       'new': {'value': 'TBD - requires the lab-source / breadboard efficiencies (RFQ-06; row 113): A9-02 '
                                        'ledger() takes every slot efficiency as an explicit caller input (value or TBD with '
                                        'what it requires, no default; a LOCK-1 conditioning input, never a variance term); a '
                                        'TBD compressor load -> PARTIAL_BOUNDARY (row 22)',
                               'status': 'TBD'},
                       'summary': 'UB-P-06 precise reason'},
                      {'cid': 'A910-R04-03',
                       'driver': 'A9.1 OQ-A902-01 + OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/items[id=UB-P-07]',
                       'old': {'value': 'TBD - requires the start-up sequence (revised SEQ-1, row 112) and PENDING '
                                        'abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/',
                               'units': 's / Hz',
                               'evidence_class': None,
                               'status': 'TBD',
                               'a9_1_decision': '__ABSENT__',
                               'source': 'owner answers rows 108, 112',
                               'freeze_point': 'LOCK-1',
                               'note': ''},
                       'new': {'value': {'window_s': 0.001, 'bandwidth_min_Hz': 20000.0, 'sample_rate_min_Sa_s': 100000.0},
                               'units': 's / Hz / Sa/s',
                               'evidence_class': 'owner-allocation',
                               'status': 'OWNER_GIVEN',
                               'a9_1_decision': 'OQ-A902-01',
                               'source': 'docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json OQ-A902-01 (A9-02 '
                                         'GATE_DEFINITION)',
                               'freeze_point': 'NOW',
                               'note': 'gate quantity P_bus,1ms,max = max 1 ms moving mean < 1500 W, start-up and steady; >= '
                                       '20 kHz effective bandwidth, >= 100 kSa/s, anti-alias documented, synchronized '
                                       'channels; the start-up step list stays the A9-02 SEQUENCE_TEMPLATES (PROPOSED, row '
                                       '112)'},
                       'summary': 'UB-P-07 window / bandwidth from A9.1',
                       'numeric': True},
                      {'cid': 'A910-R04-04',
                       'driver': 'A9.1 A9-03-matching + OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/items[id=UB-RF-09]',
                       'old': {'value': 'PENDING docs/interfaces/icp_neutralizer/ (coupler location relative to the matching '
                                        'network and coil)',
                               'evidence_class': None,
                               'status': 'PENDING',
                               'a9_1_decision': '__ABSENT__',
                               'source': 'owner answers rows 62, 71'},
                       'new': {'value': 'directional-coupler reference plane AFTER the matching network; matching network off '
                                        'the moving platform with matched flexible coax and cable-loss / S-parameter '
                                        'correction (ICD ICP-13)',
                               'evidence_class': 'owner-allocation',
                               'status': 'OWNER_GIVEN',
                               'a9_1_decision': 'A9-03-matching',
                               'source': 'docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json A9-03-matching; '
                                         'schemas/interfaces/icp_neutralizer_icd_v1.json ICP-13'},
                       'summary': 'UB-RF-09 filled'},
                      {'cid': 'A910-R04-05',
                       'driver': 'OQ-INT-03 (A9-03 ICP-20/21)',
                       'op': 'merge',
                       'ptr': '/items[id=UB-N-00]',
                       'old': {'value': 'PENDING docs/interfaces/icp_neutralizer/ (floating body + separately biased '
                                        'collector circuit, row 70)',
                               'evidence_class': None,
                               'status': 'PENDING',
                               'source': 'owner answer row 70'},
                       'new': {'value': 'ICP body floating by default (ICD ICP-20, row 70); electron-extraction collector / '
                                        'bias controlled and metered separately, never hard-grounded by default (ICD ICP-21)',
                               'evidence_class': 'owner-allocation',
                               'status': 'VERIFIED_INPUT',
                               'source': 'schemas/interfaces/icp_neutralizer_icd_v1.json ICP-20 (OWNER_GIVEN, row 70), ICP-21 '
                                         '(A9-03, merged)'},
                       'summary': 'UB-N-00 filled'},
                      {'cid': 'A910-R04-06',
                       'driver': 'OQ-INT-03 (A9-02 SLOTS)',
                       'op': 'merge',
                       'ptr': '/items[id=UB-Z-03]',
                       'old': {'value': 'TBD - requires certificates (magnet slots PENDING abep_sim/bus_boundary_a9.py + '
                                        'docs/architecture_comparison/power_boundary_a9/)'},
                       'new': {'value': 'TBD - requires certificates of the coil-current channels (magnet slots '
                                        'hall_magnet_inner / hall_magnet_outer / hall_magnet_trim defined by A9-02)'},
                       'summary': 'UB-Z-03 slot reference resolved'},
                      {'cid': 'A910-R04-07',
                       'driver': 'OQ-INT-03 (A9-01 decision_quantities)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-01]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/experiments/hall_icp/prereg_framework/'},
                       'new': {'status': 'PARTIAL',
                               'value': 'A9-01 supplies decision-quantity ids and roles (decision_quantities, '
                                        'decision_topology); the contrast list, confirmation subset and family size m are '
                                        'LOCK-1 items'},
                       'summary': 'IF-01 partial'},
                      {'cid': 'A910-R04-08',
                       'driver': 'OQ-INT-03 (A9-01 stage_map)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-02]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/experiments/hall_icp/prereg_framework/'},
                       'new': {'status': 'SATISFIED',
                               'value': 'A9-01 stage_map HI-ENG..HI-AO with score_bearing flags (score-bearing: HI-CMP, '
                                        'HI-ABS)'},
                       'summary': 'IF-02 satisfied'},
                      {'cid': 'A910-R04-09',
                       'driver': 'OQ-INT-03 (A9-02)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-05]',
                       'old': {'status': 'PENDING',
                               'value': 'PENDING abep_sim/bus_boundary_a9.py + '
                                        'docs/architecture_comparison/power_boundary_a9/'},
                       'new': {'status': 'PARTIAL',
                               'value': 'slot list S_A9 = abep_sim/bus_boundary_a9.py SLOTS / BASE_SLOTS; window frozen by '
                                        'A9.1 OQ-A902-01 (UB-P-07); per-slot eta_s are caller inputs, TBD'},
                       'summary': 'IF-05 partial'},
                      {'cid': 'A910-R04-10',
                       'driver': 'OQ-INT-03 (A9-03)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-07]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/interfaces/icp_neutralizer/'},
                       'new': {'status': 'PARTIAL',
                               'value': 'A9-03 ICP-20 (floating body, body potentials measured), ICP-21 (separately metered '
                                        'collector), ICP-34 (V_coll, I_coll, V_body channels); sign convention and bias range '
                                        'TBD (LOCK-1)'},
                       'summary': 'IF-07 partial'},
                      {'cid': 'A910-R04-11',
                       'driver': 'A9.1 A9-03-matching + OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-08]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/interfaces/icp_neutralizer/'},
                       'new': {'status': 'PARTIAL',
                               'value': 'A9.1 A9-03-matching (ICD ICP-13): coupler plane after the matching network, network '
                                        'off the platform; fixed vs auto-tuned topology and the on-module pre-match '
                                        '(OQ-A907-11) open'},
                       'summary': 'IF-08 partial'},
                      {'cid': 'A910-R04-12',
                       'driver': 'A9.1 HIQ-06 + OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-09]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/interfaces/icp_neutralizer/'},
                       'new': {'status': 'PARTIAL',
                               'value': 'A9-03 ICP-26 / A9.1 HIQ-06: G-REUSE primary, dedicated ICP flow 0 mg/s; G-ATM / G-XE '
                                        'contingency flows TBD'},
                       'summary': 'IF-09 partial'},
                      {'cid': 'A910-R04-13',
                       'driver': 'OQ-INT-03 (A9-03 ICP-08)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-10]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/interfaces/icp_neutralizer/'},
                       'new': {'status': 'OPEN',
                               'value': 'OPEN - ICD ICP-08: module masses and CG are measured per serial at S1a (TBD - '
                                        'requires the modules); A9-03 gives only the row-54 flight allocations'},
                       'summary': 'IF-10 precise reason'},
                      {'cid': 'A910-R04-14',
                       'driver': 'OQ-INT-03 (A9-05)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-12]',
                       'old': {'status': 'PENDING',
                               'value': 'PENDING docs/evidence/icp_neutralizer/ + '
                                        'docs/experiments/hall_icp/validation_inputs/'},
                       'new': {'status': 'SATISFIED',
                               'value': 'docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json extraction '
                                        'TK-01..TK-74 (what the analog measured and how, with page / figure locators; context '
                                        'only)'},
                       'summary': 'IF-12 satisfied'},
                      {'cid': 'A910-R04-15',
                       'driver': 'OQ-INT-03 (A9-07 REV-62)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-17]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/hardware/h2/h2_4_ppu_bus/'},
                       'new': {'status': 'PARTIAL',
                               'value': 'A9-07 REV-62 (breadboard discharge supply from the 100 V bus); channel points and '
                                        'eta_d TBD - require the breadboard measurement before LOCK-2'},
                       'summary': 'IF-17 partial'},
                      {'cid': 'A910-R04-16',
                       'driver': 'OQ-INT-03 (A9-07 REV-11, IDA7-17)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-18]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/'},
                       'new': {'status': 'PARTIAL',
                               'value': 'A9-07 REV-11 (hot-state B reference provision); B(z) map extent and B_max TBD - '
                                        'require FEMM of MC-1 (IDA7-17) and S1a maps'},
                       'summary': 'IF-18 partial'},
                      {'cid': 'A910-R04-17',
                       'driver': 'A9.1 HIQ-06 + OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-20]',
                       'old': {'status': 'PENDING', 'value': 'PENDING docs/interfaces/icp_neutralizer/'},
                       'new': {'status': 'PARTIAL',
                               'value': 'ICP gas booking defined: G-REUSE 0 mg/s (ICD ICP-26; A9-08 XA9-21), G-XE only as a '
                                        'contingency term under PHASE_TOTAL_FLOW; the C1 flow uncertainty term (UB-F-05, +-2 '
                                        '% FS class, row 96) is carried by this lane, its booking size TBD'},
                       'summary': 'IF-20 partial'},
                      {'cid': 'A910-R04-18',
                       'driver': 'A9.1 HIQ-06 + OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/owner_answers_applied[row=46]',
                       'old': {'how_applied': 'ICP gas feed unbooked -> UB-F-12 PENDING A9-03; C1 term 15,000 h context only'},
                       'new': {'how_applied': 'ICP gas feed: UB-F-12 = G-REUSE (A9.1 HIQ-06; ICD ICP-26), no dedicated feed '
                                              'booked; C1 term 15,000 h context only'},
                       'summary': 'row 46 application updated'},
                      {'cid': 'A910-R04-19',
                       'driver': 'OQ-INT-03',
                       'op': 'merge',
                       'ptr': '/owner_answers_applied[row=110]',
                       'old': {'how_applied': 'every active load has a bus slot (UB-P-01 PENDING A9-02)'},
                       'new': {'how_applied': 'every active load has a bus slot (UB-P-01 = the A9-02 slot list)'},
                       'summary': 'row 110 application updated'},
                      {'cid': 'A910-R04-20',
                       'driver': 'A9.1 HIQ-05',
                       'op': 'replace',
                       'ptr': '/stop_rules/net_benefit',
                       'old': 'no weighted scalar and no single winner unless preregistered (row 37);',
                       'new': 'no weighted scalar and no single winner unless preregistered (row 37); A9.1 HIQ-05: no '
                              'mandatory Pareto relation - hard gates alone decide feasibility; the Pareto quantities are '
                              'reported for engineering comparison unless a Pareto condition is preregistered at LOCK-1;',
                       'summary': 'NET_BENEFIT amended for HIQ-05'},
                      {'cid': 'A910-R04-21',
                       'driver': 'A9.1 HIQ-05',
                       'op': 'replace',
                       'ptr': '/compliance[4]',
                       'old': 'NET_BENEFIT is hard gates + Pareto (row 37)',
                       'new': 'NET_BENEFIT is hard gates + a Pareto report (row 37; A9.1 HIQ-05: hard gates alone decide '
                              'feasibility)',
                       'summary': 'compliance line amended for HIQ-05'},
                      {'cid': 'A910-R04-22',
                       'driver': 'A9.1 HIQ-05',
                       'op': 'replace',
                       'ptr': '/owner_answers_applied[row=37]/how_applied',
                       'old': 'NET_BENEFIT = hard gates + Pareto;',
                       'new': 'NET_BENEFIT = hard gates + a Pareto report (A9.1 HIQ-05: no mandatory Pareto relation - hard '
                              'gates alone decide feasibility; the Pareto quantities are reported for engineering comparison '
                              'unless a Pareto condition is preregistered at LOCK-1);',
                       'summary': 'row 37 application amended'}],
            'A9-05vi': [{'cid': 'A910-R05vi-01',
                         'driver': 'OQ-INT-03 (A9-03 ICP-20/21)',
                         'op': 'merge',
                         'ptr': '/items[id=VI-EX-03]',
                         'old': {'definition': 'potential of the ICP ion-collecting electrode with respect to the declared '
                                               'reference (cathode-common / facility ground, PENDING '
                                               'docs/interfaces/icp_neutralizer/ (A9-03 ICD))'},
                         'new': {'definition': 'potential of the ICP ion-collecting electrode with respect to the declared '
                                               'reference (cathode-common / facility ground; the A9-03 ICD (ICP-20 / ICP-21) '
                                               'records the collector bias and the body potentials but does not fix the '
                                               'collector reference: LOCK-1 item)'},
                         'summary': 'VI-EX-03 precise reason'},
                        {'cid': 'A910-R05vi-02',
                         'driver': 'OQ-INT-03 (A9-03 ICP-31)',
                         'op': 'merge',
                         'ptr': '/items[id=VI-HD-06]/how_obtained',
                         'old': {'chain': 'INS-09 extended downstream (PENDING docs/interfaces/icp_neutralizer/ (A9-03 ICD))'},
                         'new': {'chain': 'INS-09 extended downstream (ICD ICP-31 B(z) perturbation / sensitivity scan with '
                                          'the ICP installed; map extent TBD)'},
                         'summary': 'VI-HD-06 chain resolved'},
                        {'cid': 'A910-R05vi-03',
                         'driver': 'OQ-INT-03 (A9-01)',
                         'op': 'merge',
                         'ptr': '/interface_demands[id=IF-01]',
                         'old': {'status': 'PENDING docs/experiments/hall_icp/prereg_framework/ (A9-01 stage map)'},
                         'new': {'status': 'PARTIAL: A9-01 supplies stage_map ids, decision_quantities, design rules and the '
                                           'outcome vocabulary (NO_VIABLE_CASE; OPEN as status); the per-input stage '
                                           'assignment stays OPEN (OQ-A910-02, LOCK-1)'},
                         'summary': 'IF-01 partial'},
                        {'cid': 'A910-R05vi-04',
                         'driver': 'OQ-INT-03 (A9-02)',
                         'op': 'merge',
                         'ptr': '/interface_demands[id=IF-03]',
                         'old': {'status': 'PENDING abep_sim/bus_boundary_a9.py + '
                                           'docs/architecture_comparison/power_boundary_a9/ (A9-02)'},
                         'new': {'status': 'SATISFIED by A9-02: abep_sim/bus_boundary_a9.py SLOTS / BASE_SLOTS (A9-02, '
                                           'merged) (icp_rf_source, icp_matching_network, icp_collector_bias (variants: '
                                           'icp_assist_magnet, active_cooling, flow_control_icp_feed only for G-ATM / G-XE); '
                                           'C1 slots c1_heater, c1_keeper, c1_common_tie, filter_getter, flow_control_xe)'},
                         'summary': 'IF-03 satisfied'},
                        {'cid': 'A910-R05vi-05',
                         'driver': 'OQ-INT-03 (A9-03)',
                         'op': 'merge',
                         'ptr': '/interface_demands[id=IF-05]',
                         'old': {'status': 'PENDING docs/interfaces/icp_neutralizer/ (A9-03 ICD)'},
                         'new': {'status': 'PARTIAL: A9-03 defines the RF load plane (ICP-13 / ICP-14), collector / body '
                                           'terminals (ICP-20 / ICP-21), gas port (ICP-26) and channels (ICP-34); the '
                                           'Hall-exhaust-to-ICP pressure tap (ICP-27) and diagnostic access geometry are TBD '
                                           '(LOCK-1)'},
                         'summary': 'IF-05 partial'},
                        {'cid': 'A910-R05vi-06',
                         'driver': 'OQ-INT-03 (A9-04)',
                         'op': 'merge',
                         'ptr': '/interface_demands[id=IF-07]',
                         'old': {'status': 'PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04 measurement chain / '
                                           'decision quantity)'},
                         'new': {'status': 'PARTIAL: A9-04 measurement chains and stop-rule forms exist; decision-quantity '
                                           'ids per input: see the A9-10 chain -> DQ-HI consumer table (OQ-INT-01, PROPOSED) '
                                           'and OQ-A910-02'},
                         'summary': 'IF-07 partial'},
                        {'cid': 'A910-R05vi-07',
                         'driver': 'OQ-INT-03 (A9-07)',
                         'op': 'merge',
                         'ptr': '/interface_demands[id=IF-12]',
                         'old': {'status': 'PENDING A9-07 revision of H2-1'},
                         'new': {'status': 'PARTIAL: A9-07 revises H2-1 (REV-01..REV-12, REV-66: external C1, IP-EXIT / '
                                           'IP-NEU, hot-state B sensor); the field map incl. the downstream fringe region is '
                                           'TBD - requires FEMM of MC-1 and the S1a map (A9-07 IDA7-17)'},
                         'summary': 'IF-12 partial'},
                        {'cid': 'A910-R05vi-08',
                         'driver': 'A9.1 A9-03-planes + OQ-INT-03',
                         'op': 'merge',
                         'ptr': '/interface_demands[id=IF-19]',
                         'old': {'status': 'PENDING A9-03 (downstream plane definition)'},
                         'new': {'status': 'SATISFIED by A9.1 A9-03-planes (IP-EXIT = H-1 exit, z = L; IP-NEU downstream '
                                           'datum; historical IP-DN unchanged), ICD ICP-01 and A9-07 REV-03 / REV-66'},
                         'summary': 'IF-19 satisfied'},
                        {'cid': 'A910-R05vi-09',
                         'driver': 'A9.1 HIQ-05',
                         'op': 'replace',
                         'ptr': '/decision_vocabulary/net_benefit_form',
                         'old': 'no weighted scalar unless preregistered (row 37)',
                         'new': 'no weighted scalar unless preregistered (row 37); A9.1 HIQ-05: no mandatory Pareto relation '
                                '- hard gates alone decide feasibility; the Pareto quantities are reported for engineering '
                                'comparison unless a Pareto condition is preregistered at LOCK-1',
                         'summary': 'net_benefit_form amended'},
                        {'cid': 'A910-R05vi-10',
                         'driver': 'A9.1 HIQ-05',
                         'op': 'replace',
                         'ptr': '/owner_answers_applied[row=37]/how',
                         'old': 'NET_BENEFIT = hard gates + Pareto, no weighted scalar',
                         'new': 'NET_BENEFIT = hard gates + a Pareto report, no weighted scalar (A9.1 HIQ-05: no mandatory '
                                'Pareto relation)',
                         'summary': 'row 37 application amended'},
                        {'cid': 'A910-R05vi-11',
                         'driver': 'A9.1 HIQ-06',
                         'op': 'replace',
                         'ptr': '/items[id=VI-GAS-01]/definition',
                         'old': '; UNBOOKED today (A9 recorder flag row 46)',
                         'new': '; the primary mode is (a) G-REUSE with no dedicated flow (A9.1 HIQ-06, which closes the '
                                'row-46 recorder flag for the primary mode); (b) and (c) are declared contingency variants '
                                'whose flows are TBD',
                         'summary': 'VI-GAS-01 definition consistent with G-REUSE'},
                        {'cid': 'A910-R05vi-12',
                         'driver': 'A9.1 HIQ-06',
                         'op': 'merge',
                         'ptr': '/items[id=VI-GAS-01]/how_obtained',
                         'old': {'chain': 'owner decision (OQ-VI-01) then INS-05 per species'},
                         'new': {'chain': 'owner decision A9.1 HIQ-06 (answers OQ-VI-01): G-REUSE, no dedicated ICP flow; '
                                          'INS-05 per species only for a declared G-ATM / G-XE contingency variant'},
                         'summary': 'VI-GAS-01 chain: OQ-VI-01 answered by HIQ-06'},
                        {'cid': 'A910-R05vi-13',
                         'driver': 'A9.1 HIQ-06',
                         'op': 'merge',
                         'ptr': '/items[id=VI-GAS-01]',
                         'old': {'source': 'docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json '
                                           'recorder_consistency_flags_for_owner (row 46)'},
                         'new': {'source': 'docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json HIQ-06, '
                                           'HIQ-06_accounting (answers the recorder flag on row 46 of '
                                           'docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json '
                                           'for the primary mode)'},
                         'summary': 'VI-GAS-01 source: A9.1 HIQ-06'}],
            'A9-06': [{'cid': 'A910-R06-01',
                       'driver': 'A9-10 self-reference',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=MA9-ID-18]',
                       'old': {'status': 'PENDING'},
                       'new': {'status': 'SATISFIED by A9-10: closure re-run with the A9-08 residual import and the corrected '
                                         'A9-07 LV-COIL basis (builder --check reproduces)'},
                       'summary': 'MA9-ID-18 satisfied'}],
            'A9-07': [{'cid': 'A910-R07-01',
                       'driver': 'OQ-INT-03 (A9-04 UB-RF-*)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IDA7-15]',
                       'old': {'status': 'PENDING docs/experiments/hall_icp/uncertainty_budget/ (LOCK-2 numbers)'},
                       'new': {'status': 'PARTIAL - A9-04 defines u(P_fwd), u(P_refl) and the cable-loss terms '
                                         '(UB-RF-02..UB-RF-07); values TBD - require certificates / S1a (LOCK-2)'},
                       'summary': 'IDA7-15 partial'},
                      {'cid': 'A910-R07-02',
                       'driver': 'OQ-INT-03 (A9-04 UB-RF-02..07)',
                       'op': 'replace',
                       'ptr': '/new_items[id=A9H-INS-01]/note',
                       'old': 'u(P_fwd), u(P_refl) PENDING A9-04 (ICP-14, UB-RF-04)',
                       'new': 'u(P_fwd), u(P_refl): A9-04 (merged) defines the terms UB-RF-02..UB-RF-07 (ICP-14, UB-RF-04), '
                              'values TBD - require certificates / S1a',
                       'summary': 'A9H-INS-01 note re-evaluated'}],
            'A9-09': [{'cid': 'A910-R09-01',
                       'driver': 'row 111 + A9-07 REV-51/62',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-RFQ-04]',
                       'old': {'status': 'FLAG'},
                       'new': {'status': 'RESOLVED for A9 by row 111 (regulated 100 V internal bus; A9-07 REV-51 / REV-62); '
                                         'the H2-4 v1 28 V class stays history'},
                       'summary': '28 V vs 100 V conflict resolved by row 111'},
                      {'cid': 'A910-R09-02',
                       'driver': 'OQ-INT-03 (OQ-A907-02; ICP-21; A902-22)',
                       'op': 'merge',
                       'ptr': '/interface_demands[id=IF-RFQ-07]',
                       'old': {'status': 'OPEN'},
                       'new': {'status': 'OPEN - I_d,max / P_d of the registered envelope pending (OQ-A907-02); collector / '
                                         'bias range TBD (ICP-21); matching-network draw TBD (A902-22)'},
                       'summary': 'IF-RFQ-07 precise reason'},
                      {'cid': 'A910-R09-03',
                       'driver': 'A9-08 design_cases (verified lane value)',
                       'op': 'merge',
                       'ptr': '/packages[6]/requirements[3]',
                       'old': {'basis': 'pending lane',
                               'sources': [{'type': 'owner_row',
                                            'row': 45,
                                            'covers_ids': ['OD-XE-4', 'H27-Q6'],
                                            'quote': 'book the 2% unusable/residual Xe once in the Xe ledger',
                                            'answer_sha256': 'bb83b79a0651b351139537fc709cfd348e03347511cb59330ae3abecd8c913db',
                                            'path': 'docs/decisions/OD_2026_09_29_owner_answers_147.json'},
                                           {'type': 'owner_row',
                                            'row': 43,
                                            'covers_ids': ['OD-XE-2'],
                                            'quote': 'Use a separate reserve term equal to 20% of planned non-reserve mission '
                                                     'Xe',
                                            'answer_sha256': 'f42b3e3852bb0524e398bec2e9991a7b0dbc3af6c3629ea8e2048e4f38b97872',
                                            'path': 'docs/decisions/OD_2026_09_29_owner_answers_147.json'},
                                           {'type': 'owner_row',
                                            'row': 8,
                                            'covers_ids': ['WEB-SUP-1', 'R6-Q5'],
                                            'quote': 'request quotations for Xe tank/PMU/FCU/MFCs/thrust stand',
                                            'answer_sha256': 'e68149db165896264789c70c412f21a33c4b8356d0184f625a674f7f53e8ea36',
                                            'path': 'docs/decisions/OD_2026_09_29_owner_answers_147.json'}]},
                       'new': {'basis': 'copied from the verified lane A9-08 (design_cases at 323.15 K; reserve / residual '
                                        'split)',
                               'sources': [{'type': 'owner_row',
                                            'row': 45,
                                            'covers_ids': ['OD-XE-4', 'H27-Q6'],
                                            'quote': 'book the 2% unusable/residual Xe once in the Xe ledger',
                                            'answer_sha256': 'bb83b79a0651b351139537fc709cfd348e03347511cb59330ae3abecd8c913db',
                                            'path': 'docs/decisions/OD_2026_09_29_owner_answers_147.json'},
                                           {'type': 'owner_row',
                                            'row': 43,
                                            'covers_ids': ['OD-XE-2'],
                                            'quote': 'Use a separate reserve term equal to 20% of planned non-reserve mission '
                                                     'Xe',
                                            'answer_sha256': 'f42b3e3852bb0524e398bec2e9991a7b0dbc3af6c3629ea8e2048e4f38b97872',
                                            'path': 'docs/decisions/OD_2026_09_29_owner_answers_147.json'},
                                           {'type': 'owner_row',
                                            'row': 8,
                                            'covers_ids': ['WEB-SUP-1', 'R6-Q5'],
                                            'quote': 'request quotations for Xe tank/PMU/FCU/MFCs/thrust stand',
                                            'answer_sha256': 'e68149db165896264789c70c412f21a33c4b8356d0184f625a674f7f53e8ea36',
                                            'path': 'docs/decisions/OD_2026_09_29_owner_answers_147.json'},
                                           {'type': 'deliverable',
                                            'key': 'A9-08',
                                            'path': 'docs/budgets/xe' '_ledger_a9/xe' '_ledger_a9_v1.json',
                                            'pointer': '/design_cases/tank_volume'},
                                           {'type': 'deliverable',
                                            'key': 'A9-08',
                                            'path': 'docs/budgets/xe' '_ledger_a9/xe' '_ledger_a9_v1.json',
                                            'pointer': '/design_cases/reserve_residual_split'}]},
                       'summary': 'RFQ-07-R04 basis and sources name the A9-08 ledger'}]}


def _repair2() -> dict:
    return {'A9-04': [{'cid': 'A910-R04-23',
                       'driver': 'OQ-INT-03 (A9-03 ICP-14)',
                       'op': 'replace',
                       'ptr': '/measurement_chains[dq=UB-DQ-RF]/equations[4]',
                       'old': 'method PENDING docs/interfaces/icp_neutralizer/)',
                       'new': 'method TBD - not defined in the merged A9-03 ICD, whose ICP-14 names calorimetry only as the '
                              'independent cross-check; LOCK-1 item)',
                       'summary': 'calorimetry method: precise remaining reason'},
                      {'cid': 'A910-R04-24',
                       'driver': 'OQ-INT-03 (A9-03 ICP-21)',
                       'op': 'replace',
                       'ptr': '/measurement_chains[dq=UB-DQ-NEUT]/equations[2]',
                       'old': 'sign convention PENDING docs/interfaces/icp_neutralizer/)',
                       'new': 'sign convention TBD - not defined in the merged A9-03 ICD, whose ICP-21 defines the separately '
                              'metered collector only; LOCK-1 item)',
                       'summary': 'collector-current sign convention: precise remaining reason'}]}

def _repair3() -> dict:
    return {'A9-03': [{'cid': 'A910-R03-24',
                       'driver': 'OQ-INT-03 (A9-02; A9-05 TK-21/52)',
                       'op': 'replace',
                       'ptr': '/hard_incompatibility_check/checked[3]/finding',
                       'old': 'not assessable, PENDING docs/architecture_comparison/power_boundary_a9/ (I_d,max) and '
                              'docs/evidence/icp_neutralizer/ (analog electron-current vs RF power evidence).',
                       'new': 'not assessable: A9-02 (merged) registers no stand I_d,max (owner registration OQ-A907-02) and '
                              'A9-05 (merged) holds only the anchor analog '
                              '(docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json TK-52 I_D about 1 A at TK-21 '
                              '200 W forward; published analog, context only, never scaled, A9.1 ICP-45).',
                       'summary': 'hard-incompatibility finding re-evaluated against A9-02 / A9-05'}]}

def _repair4() -> dict:
    return {'A9-04': [{'cid': 'A910-R04-25',
                       'driver': 'OQ-INT-03 (A9-01 DQ-HI-ETAU)',
                       'op': 'merge',
                       'ptr': '/items[id=UB-E-00]',
                       'old': {'value': 'PENDING docs/experiments/hall_icp/prereg_framework/ (if used, S1b Faraday/ExB '
                                        'repeatability is mandatory, row 32)',
                               'status': 'PENDING'},
                       'new': {'value': 'TBD - requires the LOCK-1 choice: A9-01 DQ-HI-ETAU is CONDITIONAL (descriptive '
                                        'unless preregistered at LOCK-1; if used, S1b Faraday / ExB repeatability is '
                                        'mandatory, row 32)',
                               'status': 'TBD'},
                       'summary': 'UB-E-00 re-stated from A9-01 DQ-HI-ETAU'},
                      {'cid': 'A910-R04-26',
                       'driver': 'OQ-INT-03 (A9-01 DQ-HI-ETAU)',
                       'op': 'replace',
                       'ptr': '/measurement_chains[dq=DQ-HI-ETAU]/equations[0]',
                       'old': 'mdot_prop basis PENDING docs/experiments/hall_icp/prereg_framework/]',
                       'new': 'mdot_prop basis TBD - A9-01 DQ-HI-ETAU (CONDITIONAL) does not define it; LOCK-1 item if eta_u '
                              'is preregistered]',
                       'summary': 'mdot_prop basis precise reason'},
                      {'cid': 'A910-R04-27',
                       'driver': 'OQ-INT-03 (A9-03 ICP-21)',
                       'op': 'merge',
                       'ptr': '/stop_rules/limit_aborts/limits[id=LA-04]',
                       'old': {'value': 'TBD - requires PENDING docs/interfaces/icp_neutralizer/ and supply rating'},
                       'new': {'value': 'TBD - requires the collector / bias V-I range (ICD ICP-21: a design item, TBD in the '
                                        'merged A9-03 ICD) and the supply rating (RFQ-05)'},
                       'summary': 'LA-04 precise reason'}]}


def _repair_code() -> dict:
    """Source-code changes of the review repair (recorded as 'code' records with a marker and a scope)."""
    return {"A9-02": [
        R("A910-R02-C1", "A9.1 OQ-A902-01 (review repair; OQ-A910-03 not pre-empted)", "code", None,
          summary="rfp_power_gate: PASS only on p_bus_1ms_max WITH a conformant gate_measurement record (>= 100 kSa/s, "
          ">= 20 kHz, anti-alias documented, synchronized); peak_sampled is NOT_EVALUABLE both ways (protection record; "
          "the reading 'a conformant peak below 1500 W bounds the 1 ms maximum' is the OPEN owner question OQ-A910-03); "
          "an unstated basis is NOT_EVALUABLE; step_average / steady_state FAIL only under the stated duration "
          "assumption; c1_keeper load plane no longer cites peak_sampled",
          file="abep_sim/bus_boundary_a9.py", marker="PEAK_SAMPLED_RULE",
          scope=["/items", "/gates_and_allocations", "/sequencing", "/slots", "/bus_architecture", "/h4_inputs"],
          numeric=False),
        R("A910-R02-C2", "OQ-INT-03 (A9-04 DQ-HI-PBUS chain)", "code", None,
          summary="A902-25 note and the row-89 application: the pulse-energy record is not defined by the merged "
          "A9-04 DQ-HI-PBUS chain (LOCK-1 item) instead of 'PENDING A9-04'; schema gains the gate_measurement record",
          file="docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py",
          marker="defines no pulse-energy record yet", scope=["/items", "/owner_answers_applied"], numeric=False),
    ]}


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
