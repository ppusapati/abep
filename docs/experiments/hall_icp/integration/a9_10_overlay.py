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
    for extra in (_repair_code(), _repair(), _repair2(), _repair3(), _repair4(), _repair5(), _a92(), _a92_repair(), _a92_repair2()):
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


# ------------------------------------------------------------------------------------------------------ repair 5
# Second review repair: stale wording left after the A9.1 decisions were applied (UBQ-02 / UBQ-04 / UBQ-06 /
# OQ-A902-01 / ICP-46) and the A9-05 per-input assignment fields re-stated next to the field (OQ-INT-03 /
# OQ-A910-02). Text only; no number changes.
VI_STAGE_OLD = "PENDING docs/experiments/hall_icp/prereg_framework/ (A9-01 stage map)"
VI_STAGE_NEW = ("TBD - ASSIGNMENT_NOT_DEFINED_BY_TARGET: the merged A9-01 prereg framework defines the stages but no "
                "per-input producing-stage assignment; owner call OQ-A910-02 (LOCK-1)")
VI_DQ_OLD = "PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04 measurement chain / decision quantity)"
VI_DQ_NEW = ("TBD - ASSIGNMENT_NOT_DEFINED_BY_TARGET: the merged A9-04 budget defines the measurement chains but no "
             "per-input decision-quantity assignment (chain -> DQ-HI consumers: A9-10 dq_consumer_table); owner call "
             "OQ-A910-02 (LOCK-1)")


def _repair5() -> dict:
    return {
        "A9-04": [
            R("A910-R04-28", "A9.1 UBQ-06 (review repair 2)", "set", "/items[id=UB-K-00]/note",
              "a design margin (plus 20 % heat-load margin), not an abort limit; whether limit aborts fire at the "
              "validated limit or at limit - margin is open question UBQ-06",
              "a design margin (plus 20 % heat-load margin); A9.1 UBQ-06 sets the score-bearing temperature abort at "
              "the validated continuous-use limit minus 50 K (stop_rules LA-05)",
              "UB-K-00 note restated from the applied A9.1 UBQ-06"),
            R("A910-R04-29", "A9.1 UBQ-02 (review repair 2)", "replace",
              "/measurement_chains[dq=UB-DQ-NEUT]/equations[4]", "PROPOSED margin form (UBQ-02):",
              "OWNER_GIVEN margin form (A9.1 UBQ-02):", "M_n form is owner-given (A9.1 UBQ-02)"),
            R("A910-R04-30", "A9.1 UBQ-02 (review repair 2)", "replace",
              "/measurement_chains[dq=UB-DQ-NEUT]/equations[4]",
              "(margin value PENDING docs/experiments/hall_icp/prereg_framework/)",
              "(any extra design margin is frozen at LOCK-2 per the LOCK-1 rule, A9.1 UBQ-02)",
              "M_n extra margin freeze point from A9.1 UBQ-02 (no stale A9-01 pointer)"),
            R("A910-R04-31", "A9.1 UBQ-04 (review repair 2)", "replace",
              "/measurement_chains[dq=UB-DQ-RF]/equations[4]", "PROPOSED rule |z_x| <= k_x (UBQ-04)",
              "rule |z_x| <= k_x with k_x = 2 frozen at LOCK-1 (A9.1 UBQ-04; failure -> RF-dependent quantities "
              "EXCLUDED_INSTRUMENT; UB-RF-08)", "cross-check rule restated from the applied A9.1 UBQ-04"),
            R("A910-R04-32", "A9-07 IDA7-21 (review repair 2)", "set", "/items[id=UB-RF-04]/units", "W",
              "1 (relative error of P_net; the absolute term in W is this value x P_net)",
              "UB-RF-04 units match the imported IDA7-21 relative-error relation"),
            R("A910-R04-33", "A9.1 OQ-A902-01 (review repair 2)", "gsub", "", "for P_bus,peak",
              "for P_bus,1ms,max (A9.1 OQ-A902-01)",
              "gate quantity renamed P_bus,peak -> P_bus,1ms,max (UB-P-07 name, IF demand, row-112 application)"),
        ],
        "A9-03": [
            R("A910-R03-25", "A9.1 ICP-46 (review repair 2)", "replace", "/items[id=ICP-46]/requirement",
              "The margin and pulse hipot level are owner/LOCK-1 items.",
              "Isolation basis per A9.1 ICP-46: design isolation basis 900 V (1.5 x 600 V); development hipot 1.0 kV "
              "DC at representative pressure/gas (no flashover or breakdown, leakage recorded); a separate 600 V "
              "pulse-waveform test; the flight level may only be revised upward without a controlled justification.",
              "ICP-46 requirement text aligned with the applied A9.1 isolation basis"),
            R("A910-R03-26", "A9.1 ICP-46 (review repair 2)", "set", "/items[id=ICP-46]/verification",
              "pulse hipot of keeper lead/feedthrough/harness per exchange (ICP-39 d); inspection",
              "1.0 kV DC hipot at representative pressure/gas with leakage recorded AND a separate 600 V "
              "pulse-waveform test of keeper lead / feedthrough / connectors / harness per exchange (ICP-39 d) "
              "(A9.1 ICP-46); inspection", "ICP-46 verification aligned with A9.1"),
        ],
        "A9-05vi": [
            R("A910-R05-01", "OQ-INT-03 / OQ-A910-02 (review repair 2)", "gsub", "", VI_STAGE_OLD, VI_STAGE_NEW,
              "per-input producing stage: precise remaining reason next to the field"),
            R("A910-R05-02", "OQ-INT-03 / OQ-A910-02 (review repair 2)", "gsub", "", VI_DQ_OLD, VI_DQ_NEW,
              "per-input decision quantity: precise remaining reason next to the field"),
        ],
    }


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
        R("A910-R02-C3", "A9.1 SEQ-peaks (review repair 2; ICD ICP-22 / ICP-45)", "code", None,
          summary="check_startup_sequence counts peak-class loads COMMANDED to rise (A9.1 SEQ-peaks wording): the "
          "icp_collector_bias rise at the hall_discharge_ignition step is a declared dependent rise (the Hall "
          "discharge current closes through the collector), reported in 'dependent_rises', kept in every power "
          "ledger and the 1500 W gate, not counted as a second commanded peak; the same rise at any other step "
          "still violates",
          file="abep_sim/bus_boundary_a9.py", marker="DEPENDENT_RISES",
          scope=["/sequencing", "/items", "/gates_and_allocations"], numeric=False),
        R("A910-R02-C4", "A9.1 OQ-A902-01 (review repair 2)", "code", None,
          summary="FAIL on a p_bus_1ms_max ledger carries P1MS_SUM_RULE: the per-slot sum is a lower bound only for "
          "simultaneous slot values; summed non-simultaneous per-slot 1 ms maxima are an upper bound (PASS-"
          "conservative), so a FAIL on them must be confirmed on the system-level bus-channel 1 ms maximum",
          file="abep_sim/bus_boundary_a9.py", marker="P1MS_SUM_RULE",
          scope=["/gates_and_allocations", "/items"], numeric=False),
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
            "a9_2_decision": a92_pin(),
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
        elif op == "supersede":
            # A9.2 supersession: the current value is kept as <field>_before_a9_2 (history never deleted)
            if not isinstance(cur, dict):
                raise OverlayError(f"{r['cid']}: {path} is not an object")
            for kk, sub in r["old"].items():
                if kk not in cur:
                    raise OverlayError(f"{r['cid']}: {path}/{kk} absent")
                have = cur[kk] if isinstance(cur[kk], str) else json.dumps(cur[kk], ensure_ascii=False)
                if sub not in have:
                    raise OverlayError(f"{r['cid']}: {path}/{kk} does not contain {sub!r:.80}")
                if kk + "_before_a9_2" in cur:
                    raise OverlayError(f"{r['cid']}: {path}/{kk} already superseded")
            for kk, nv in r["new"].items():
                if kk in r["old"]:
                    cur[kk + "_before_a9_2"] = copy.deepcopy(cur[kk])
                elif kk in cur:
                    raise OverlayError(f"{r['cid']}: {path}/{kk} exists but is not declared in old")
                cur[kk] = copy.deepcopy(nv)
        elif op == "a92_thermal_residual":
            k_changed = _a92_thermal_residual(cur)
            if k_changed == 0:
                raise OverlayError(f"{r['cid']}: A9.2 residual thermal relabel matched nothing")
            n += k_changed - 1
        elif op == "a92_sens_vocab":
            k_changed = _a92_sens_vocab(cur)
            if k_changed == 0:
                raise OverlayError(f"{r['cid']}: A9.2 sensitivity vocabulary rename matched nothing")
            n += k_changed - 1
        elif op == "a92_thermal":
            k_changed = _a92_thermal(cur)
            if k_changed == 0:
                raise OverlayError(f"{r['cid']}: A9.2 thermal status change matched nothing")
            n += k_changed - 1
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
         f"`{sec['a9_1_decision']['sha256']}`); A9.2 decision `{sec['a9_2_decision']['path']}` (sha256 "
         f"`{sec['a9_2_decision']['sha256']}`). A9 stays {sec['a9_status']}; no winner; no prediction.", "",
         "| change | driver | op | pointer | count | summary |", "|---|---|---|---|---|---|"]
    for c in sec["changes"]:
        L.append(f"| {c['cid']} | {_c(c['driver'])} | {c['op']} | `{_c(c['ptr'])}` | {c['count']} | "
                 f"{_c(c['summary'])} |")
    return L


# ------------------------------------------------------------------------------------------------------ A9.2
# Owner-directed incorporation of A9.2 (A9-07 follow-up owner decisions, 2026-09-30). The decision files live in
# docs/decisions/ of the execution branch (commit 19c0040); this lane reads a byte-identical pinned copy under
# a9_2_inputs/ (sha256 checked; when the original is present it must carry the same sha256). Every record below cites
# the A9.2 item it applies (driver 'A9.2 <item>'); no number changes except status/label changes A9.2 requires.
A92_REL = "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
A92_SHA = "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03"
A92_MD_REL = "docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md"
A92_MD_SHA = "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9"
A92_COPY_DIR = "docs/experiments/hall_icp/integration/a9_2_inputs/"
A92_COPY = A92_COPY_DIR + "OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
A92_MD_COPY = A92_COPY_DIR + "OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md"
A92_COMMIT = "19c0040"
ANSWERED_A92 = "ANSWERED_BY_A9_2"
UNRES = "UNRESOLVED"
_A92_CACHE: dict = {}


def _sha_rel(rel: str):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return None
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def a92() -> dict:
    """The A9.2 decision JSON (verified pinned copy; the original, when present, must be byte-identical)."""
    if "d" in _A92_CACHE:
        return _A92_CACHE["d"]
    for copy_rel, orig_rel, sha in ((A92_COPY, A92_REL, A92_SHA), (A92_MD_COPY, A92_MD_REL, A92_MD_SHA)):
        got = _sha_rel(copy_rel)
        if got != sha:
            raise OverlayError(f"{copy_rel} sha256 {got} != pinned {sha} (A9.2 immutable owner decision)")
        orig = _sha_rel(orig_rel)
        if orig is not None and orig != sha:
            raise OverlayError(f"{orig_rel} sha256 {orig} != pinned {sha}")
    with open(os.path.join(ROOT, A92_COPY), encoding="utf-8") as f:
        _A92_CACHE["d"] = json.load(f)
    return _A92_CACHE["d"]


def a92_pin() -> dict:
    return {"path": A92_REL, "sha256": A92_SHA, "verbatim": A92_MD_REL, "verbatim_sha256": A92_MD_SHA,
            "pinned_copy": A92_COPY, "verbatim_pinned_copy": A92_MD_COPY, "recorded_at_commit": A92_COMMIT,
            "path_resolution": "the docs/decisions/ paths exist in the execution branch (commit " + A92_COMMIT + ") "
                               "and resolve in this lane branch only after it merges there; until then the byte-identical "
                               "pinned copies under " + A92_COPY_DIR + " (sha256 checked on every build) are the "
                               "readable authority"}


def a92_statuses() -> dict:
    return dict(a92()["decisions"]["a9_10_statuses"])


def a92_text(item: str) -> str:
    v = a92()["decisions"][item]
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def a92_src(item: str) -> str:
    return f"{A92_REL} decisions.{item} (sha256 {A92_SHA}; verbatim {A92_MD_REL})"


PASS_LIKE = re.compile(r"^(CLOSES(_WITH_SINGLE_LEVER|_ONLY_WITH_COMBINED_LEVERS|_WITH_LEVERS)?|CONDITIONALLY_RESOLVED|"
                       r"PASS|RESOLVED|CLOSED)$")
COUPLED_TERMS = ["Q_Hall->ICP", "Q_collector", "Q_RF/match", "Q_plume",
                 "geometric effect of the ICP assembly on H-1 radiation (view obstruction, back-radiation, carrier "
                 "conduction, plume interception)"]
POLE_PTR = "/recomputations/h25_thermal_rerun/icp_heat_into_h1/min_allowance_W/LV-BASE/PO/CO"
LOCAL_CHAIN = ("RF generator -> directional coupler -> 50-ohm transmission line -> LOCAL matching network on / "
               "immediately adjacent to the ICP module -> ICP antenna")
MEAS_REF = ("forward and reflected power measured on the generator / 50-ohm side of the local matching network; retained "
            "quantities P_forward, P_reflected, |Gamma|, VSWR and, where possible, P_delivered = P_forward - P_reflected "
            "- P_line/match,loss; P_forward = P_plasma is never assumed")
RATINGS_TBD = ("TBD - requires the ICP antenna impedance map Z_antenna = R + jX versus mdot, P_RF, p, gas composition and "
               "the Hall operating point (A9.2 post-A9 priority P2): RF component ratings (generator, coupler, coax, "
               "connectors, matching elements incl. their voltage and current, feedthroughs) are TBD_AFTER_IMPEDANCE_MAP; "
               "the 0-500 W row-72 figure is a laboratory delivered/operating investigation capability, not a component "
               "rating (A9.2)")
PROTECTION = ["reflected-power monitoring", "mismatch / interlock threshold", "arc detection where feasible",
              "thermal monitoring", "automatic RF reduction / shutdown"]
TRIP_TBD = ("TBD - requires the ICP antenna / load characterization: exact reflected-power and VSWR trip thresholds are "
            "frozen after it, never invented now (A9.2 rf_protection)")
ANODE_INVESTIGATION = ["stronger anode-to-backplate conduction", "anode support / feed-tube conduction",
                       "geometric heat spreading", "radiative area", "thermal coupling to the spacecraft / stand",
                       "deposited discharge-power fraction", "refractory / oxidation-resistant material candidates",
                       "optional active cooling only if passive closure fails"]
ANODE_TEXT = ("A9.2: 316L REJECTED_AS_CURRENT_BASELINE for the design-representative / flight H-1 anode (allowed only as "
              "an engineering / shakedown material, a coupon candidate or a low-temperature development component); "
              "ANODE_BASELINE = OPEN; final anode material OPEN; anode thermal closure UNRESOLVED; no refractory metal "
              "(W, Mo, Pt, ...) is selected merely for its melting point; objective: reduce the actual anode operating "
              "temperature first, then select a material with T_operating <= T_validated,continuous - 50 K; no new "
              "anode temperature limit is set")
COUPLED_TEXT = ("A9.2 ICP_COUPLED_THERMAL = UNRESOLVED: every hall_icp_neutralizer thermal result of the A9-07 rerun is an "
                "UNCOUPLED sensitivity (0 W ICP heat, v1 exterior views) and is reported as UNRESOLVED until the coupled "
                "model includes Q_Hall->ICP, Q_collector, Q_RF/match, Q_plume and the ICP assembly's geometric effect "
                "on H-1 radiation; a calculation assuming negligible ICP coupling cannot close A9 (prohibited "
                "assumption)")
POLE_TEXT = ("A9.2 13 W pole allowance: the outer coil CO tolerates only about 13 W of ICP heat injected at the outer "
             "front pole PO at LV-BASE (A9-07 icp_heat_into_h1.min_allowance_W) - a design-driving warning, not grounds "
             "to reject A9; a coupled view-factor / conduction calculation is required before thermal closure")
COIL_TEXT = ("A9.2 coil-mass correction: about 0.14 kg (0.136 kg) is the copper of the 60 W / fixed-ampere-turn "
             "sensitivity basis, NOT the MC-1 coil mass; about 1.58 kg is the current estimated copper mass of the "
             "complete coil geometry from the H2-1 sizing (H21-24 1.579 kg, RP-1 f_NI 2); the two are never alternative "
             "estimates of the same physical mass; the A9-06 closure uses only the clearly defined complete hardware "
             "mass (A9B-16 MC-1 3.504 kg = iron 1.925 kg + complete-coil copper 1.579 kg)")
VIEW_OBJECTIVE = ["open-frame ICP support", "minimum necessary downstream obstruction", "annular / open optical path",
                  "thermally isolated mounting", "high-emittance outward-facing surfaces",
                  "suitable Hall-to-ICP axial spacing"]
POST_A9 = [
    {"id": "P1", "name": "ICP electron-source bench", "measure": "I_e(P_RF, Z, p, mdot, gas); prove ICP-45 (ICP-45A Ar, "
     "ICP-45N N2)", "status_it_moves": "ICP electron-current capacity PENDING_ICP45"},
    {"id": "P2", "name": "ICP impedance map", "measure": "Z_antenna = f(P_RF, mdot, p, gas, plasma state) to size the "
     "matching network and RF chain", "status_it_moves": "RF component ratings TBD_AFTER_IMPEDANCE_MAP"},
    {"id": "P3", "name": "coupled thermal redesign", "measure": "recalculate H-1 with the actual downstream ICP geometry / "
     "view factors (Q_Hall->ICP, Q_collector, Q_RF/match, Q_plume)", "status_it_moves":
     "coupled H-1/ICP thermal closure UNRESOLVED"},
    {"id": "P4", "name": "anode design", "measure": "improve the conductive / radiative path and run the candidate-material "
     "trade", "status_it_moves": "final anode material OPEN; anode thermal closure UNRESOLVED"},
]


def _a92_thermal(th: dict) -> int:
    """A9.2 ICP_COUPLED_THERMAL: every pass-like hall_icp_neutralizer thermal status becomes UNRESOLVED; the computed
    value is kept beside it as the uncoupled sensitivity (numbers untouched). Returns the number of changed fields."""
    n = 0

    def fix(d, key, sens_key):
        nonlocal n
        v = d.get(key)
        if isinstance(v, str) and PASS_LIKE.match(v):
            d[sens_key] = v
            d[key] = UNRES
            n += 1
        elif isinstance(v, list) and any(isinstance(x, str) and PASS_LIKE.match(x) for x in v):
            d[sens_key] = list(v)
            d[key] = [UNRES if isinstance(x, str) and PASS_LIKE.match(x) else x for x in v]
            n += 1

    for _lv, cases in th["results"]["hall_icp_neutralizer"].items():
        for _c, rec in cases.items():
            for _node, e in rec["nodes"].items():
                fix(e, "verdict", "uncoupled_sensitivity_verdict")
                fix(e, "necessary_check", "uncoupled_sensitivity_necessary_check")
    for node, s in th["closure_summary_hall_icp_neutralizer"].items():
        for k in ("status", "brief_verdict_at_baseline", "necessary_check"):
            fix(s, k, "uncoupled_sensitivity_" + k)
        if node == "AN":
            s["a9_2_anode"] = {"ANODE_BASELINE": "OPEN", "316L flight anode": a92_statuses()["316L flight anode"],
                               "final anode material": a92_statuses()["final anode material"],
                               "anode thermal closure": a92_statuses()["anode thermal closure"],
                               "statement": ANODE_TEXT, "investigate": ANODE_INVESTIGATION,
                               "design_blockers": ["A9H-ANODE-01", "A9H-ANODE-02"], "source": a92_src("anode_approach")}
            n += 1
    bn = th["bn_wall_11_2K_case"]
    fix(bn, "status", "uncoupled_sensitivity_status")
    fix(bn["outer_wall"], "status", "uncoupled_sensitivity_status")
    for _lv, cases in th["mount_heat_vs_row85"].items():
        for _c, r in cases.items():
            w = r["within_allowable_W"]
            if any(PASS_LIKE.match(v) for v in w.values()):
                r["within_allowable_W_uncoupled_sensitivity"] = dict(w)
                r["within_allowable_W"] = {a: (UNRES if PASS_LIKE.match(v) else v) for a, v in w.items()}
                n += 1
    ov = th["overall"]
    if ov["status"] != "OPEN":
        raise OverlayError(f"A9-07 overall thermal status is {ov['status']!r}, expected 'OPEN'")
    ov["status_before_a9_2"] = ov["status"]
    ov["status"] = UNRES
    n += 1
    pole = th["icp_heat_into_h1"]["min_allowance_W"]["LV-BASE"]["PO"]["CO"]
    th["a9_2_icp_coupled_thermal"] = {
        "ICP_COUPLED_THERMAL": UNRES, "coupled H-1/ICP thermal closure": a92_statuses()["coupled H-1/ICP thermal closure"],
        "statement": COUPLED_TEXT, "required_terms": COUPLED_TERMS,
        "prohibited_assumption": "ICP thermal interaction is small enough to ignore (A9.2 13W_pole_allowance)",
        "icp_effects_to_model": ["obstruct H-1's radiative view", "radiate back toward the Hall head",
                                 "conduct heat through the carrier", "intercept plume energy"],
        "pole_allowance_warning": {"value_W": pole, "node": "CO (outer coil)", "injection": "PO (outer front pole)",
                                   "lever": "LV-BASE", "source": H2A9 + " " + POLE_PTR.replace(
                                       "/recomputations", "recomputations").replace("/", "."),
                                   "evidence_class": "model-derived (uncoupled sensitivity)",
                                   "status": "DESIGN_DRIVING_WARNING (A9.2)", "text": POLE_TEXT},
        "sensitivity_label": "the computed temperatures, margins, allowances and the uncoupled_sensitivity_* verdicts are "
                             "kept unchanged as sensitivity information only; reported statuses are UNRESOLVED",
        "radiative_view_objective": "ICD ICP-47 (A9.2 radiative_view_requirement)",
        "next_lane": "P3 coupled thermal redesign (recommended, not launched)",
        "source": a92_src("icp_coupled_thermal") + "; " + a92_src("13W_pole_allowance")}
    n += 1
    return n


def _a92_answered(qptr: str, item: str, note: str = "") -> dict:
    return {"op": "merge", "ptr": qptr,
            "old": {"status": ABSENT, "a9_2_decision": ABSENT, "decision_source": ABSENT},
            "new": {"status": f"{ANSWERED_A92} ({item})", "a9_2_decision": a92_text(item) + (f" [{note}]" if note else ""),
                    "decision_source": a92_src(item)},
            "driver": "A9.2 " + item, "summary": f"owner question answered by A9.2 {item}"}


def _new_item_a907(iid, name, value, units, basis, note, status="TBD", freeze="after-evidence", items=()):
    return {"id": iid, "name": name, "value": value, "units": units, "basis": basis,
            "source": [{"kind": "A9.2", "id": x, "path": A92_REL, "sha256": A92_SHA} for x in items],
            "evidence_class": None, "status": status, "freeze_point": freeze,
            "applies_to": ["hall_c1_reference", "hall_icp_neutralizer"] if "ANODE" in iid else ["hall_icp_neutralizer"],
            "note": note}


def _a92_a907() -> list:
    kf = "/key_findings[{}]"
    rp = "/recomputations/rf_reference_plane"
    ids = "/interface_demands[id={}]"
    h3 = "/h3_inputs[id={}]"
    m16 = "/m16_impact[m16_row={}]"
    return [
        dict(R("A910-A92-A907-01", "A9.2 icp_coupled_thermal, 13W_pole_allowance, a9_10_statuses", "a92_thermal",
               "/recomputations/h25_thermal_rerun",
               summary="ICP_COUPLED_THERMAL = UNRESOLVED: every pass-like hall_icp_neutralizer thermal status (node "
                       "verdicts, necessary checks, closure summaries, BN-wall 11.2 K case, row-85 mount-heat checks, "
                       "overall) is reported UNRESOLVED; the computed value is kept as uncoupled_sensitivity_*; anode "
                       "block and the 13 W pole warning added (numbers unchanged; 13.0 W copied)"),
             numeric=True, source={"file": H2A9, "ptr": POLE_PTR, "value": 13.0}),
        R("A910-A92-A907-02", "A9.2 icp_coupled_thermal", "replace", kf.format(1), "Brief verdicts at baseline:",
          "Uncoupled sensitivity verdicts at baseline (A9.2 ICP_COUPLED_THERMAL = UNRESOLVED: the reported status of "
          "every hall_icp_neutralizer thermal closure is UNRESOLVED; sensitivity information only):",
          "K2 relabelled as uncoupled sensitivity"),
        R("A910-A92-A907-43", "A9.2 icp_coupled_thermal", "replace", kf.format(1), "overall status OPEN.",
          "overall status UNRESOLVED (A9.2 ICP_COUPLED_THERMAL; before A9.2: OPEN).", "K2 overall status"),
        R("A910-A92-A907-44", "A9.2 a9_10_statuses, post_a9_priorities", "append", "/key_findings", None,
          "K13 A9.2 (owner decisions 2026-09-30): RF matching architecture LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT (" +
          LOCAL_CHAIN + "); RF component ratings TBD_AFTER_IMPEDANCE_MAP; 316L flight anode "
          "REJECTED_AS_CURRENT_BASELINE; final anode material OPEN; anode thermal closure UNRESOLVED; coupled H-1/ICP "
          "thermal closure UNRESOLVED (" + COUPLED_TEXT + "); " + POLE_TEXT + "; " + COIL_TEXT + ". Recommended next "
          "lanes (not launched): P1 ICP electron-source bench (ICP-45), P2 ICP impedance map, P3 coupled thermal "
          "redesign, P4 anode design.", "K13 A9.2 summary"),
        R("A910-A92-A907-03", "A9.2 13W_pole_allowance", "replace", kf.format(1), "Search-sensitive baseline closures: CO.",
          "Search-sensitive baseline closures: CO. " + POLE_TEXT + ".", "K2 13 W pole warning"),
        R("A910-A92-A907-04", "A9.2 icp_coupled_thermal", "replace", kf.format(2), "the v1 11.2 K BN-wall case is "
          "CONDITIONALLY_RESOLVED", "the v1 11.2 K BN-wall case is UNRESOLVED (A9.2 ICP_COUPLED_THERMAL; uncoupled "
          "sensitivity: CONDITIONALLY_RESOLVED)", "K3 relabelled"),
        R("A910-A92-A907-05", "A9.2 anode_316L, anode_approach", "replace", kf.format(5),
          "or a changed heat path is needed.", "or a changed heat path is needed. " + ANODE_TEXT + "; design blockers "
          "A9H-ANODE-01 (material) and A9H-ANODE-02 (heat-removal path).", "K6 anode status"),
        R("A910-A92-A907-06", "A9.2 OQ-A907-11", "replace", kf.format(7),
          "matching network off-platform with the coupler plane after the match",
          "local adjustable matching network on / immediately adjacent to the ICP module with the directional coupler "
          "on the generator / 50-ohm side (A9.2 OQ-A907-11; the A9.1 off-platform arrangement is superseded for the "
          "baseline)", "K8 matching location"),
        R("A910-A92-A907-07", "A9.2 OQ-A907-11, rf_500W, icp_matching_strategy", "replace", kf.format(10),
          "Proposed: a fixed on-module pre-match (OQ-A907-11)",
          "A9.2 (OQ-A907-11 answered): chain " + LOCAL_CHAIN + "; " + MEAS_REF + "; the review sensitivity loads now "
          "describe the short match-to-antenna segment and the matching elements; ratings TBD_AFTER_IMPEDANCE_MAP; "
          "earlier proposal: a fixed on-module pre-match (OQ-A907-11)", "K11 RF chain"),
        R("A910-A92-A907-08", "A9.2 coil_mass_correction", "replace", kf.format(11),
          "delta 0.136 kg at a 60 W basis, 1.58 kg at a 5.164 W basis; fixed-mean-turn estimates, not bounds;",
          "0.136 kg is the copper of the 60 W / fixed-ampere-turn sensitivity basis (NOT the MC-1 coil mass) and 1.58 kg "
          "the current complete-coil copper estimate of the H2-1 RP-1 sizing (5.164 W basis); A9.2 coil-mass "
          "correction: never alternative estimates of the same mass; fixed-mean-turn estimates, not bounds;",
          "K12 coil-mass wording"),
        R("A910-A92-A907-09", "A9.2 coil_mass_correction", "merge", "/recomputations/lv_coil_copper_delta",
          {"a9_2_coil_mass_correction": ABSENT}, {"a9_2_coil_mass_correction": {
              "text": COIL_TEXT, "source": a92_src("coil_mass_correction"),
              "P_mag_basis_60W_H25-08_upper": "copper of the 60 W / fixed-ampere-turn sensitivity basis; NOT the MC-1 "
                                              "coil mass",
              "P_mag_basis_RP1_as_sized": "current estimated copper mass of the complete coil geometry (H2-1 sizing)"}},
          "coil-mass correction recorded"),
        R("A910-A92-A907-10", "A9.2 coil_mass_correction", "replace", "/recomputations/lv_coil_copper_delta/not_reconciled",
          "(about 0.14 kg copper)", "(about 0.14 kg copper: the copper of that 60 W / fixed-ampere-turn sensitivity basis, "
          "NOT the MC-1 coil mass, A9.2)", "not_reconciled wording"),
        R("A910-A92-A907-11", "A9.2 OQ-A907-11, rf_measurement_reference", "supersede", rp,
          {"reference_plane": "A9.1 A9-03-matching", "finding": "the row-72 0-500 W range is the GENERATOR forward power"},
          {"reference_plane": "A9.2 OQ-A907-11 (supersedes the A9.1 off-platform arrangement for the A9 baseline): " +
                              LOCAL_CHAIN + ". The long flexible coax on the thrust stand stays approximately a "
                              "controlled 50-ohm line; the antenna mismatch is confined to the short match-to-antenna "
                              "segment and the matching elements. " + MEAS_REF,
           "finding": "A9.2: 0-500 W is a laboratory delivered/operating investigation capability, not a component "
                      "rating. With the local match, the retained 50-ohm segment (generator -> coupler -> line -> match "
                      "input) sees only the residual mismatch after the match (residual_vswr_sensitivity); the review "
                      "sensitivity loads (e.g. VSWR 5.208 -> P_fwd 925 W for 500 W delivered) now describe the SHORT "
                      "match-to-antenna segment and the voltage / current stress of the matching elements and show why "
                      "rating the chain merely for 500 W is unacceptable. " + RATINGS_TBD},
          "RF reference plane recomputation re-described (A9.2 local match)"),
        R("A910-A92-A907-12", "A9.2 OQ-A907-11", "merge", rp, {"a9_2_segments": ABSENT}, {"a9_2_segments": {
            "retained_50_ohm_segment": {"path": "generator -> directional coupler -> 50-ohm transmission line (incl. the "
                                                "flexible stand crossing) -> local match input",
                                        "mismatch": "residual |Gamma| after the local match",
                                        "sensitivity_table": "residual_vswr_sensitivity (VSWR 1.2 / 1.5 / 2.0; "
                                                             "sensitivity values, not limits)",
                                        "measurement": MEAS_REF},
            "short_match_to_antenna_segment": {"path": "local matching network output -> ICP antenna",
                                               "mismatch": "the antenna's own reflection",
                                               "sensitivity_table": "sensitivity_loads (review cases; not antenna data)",
                                               "ratings": RATINGS_TBD},
            "p_delivered": "P_delivered = P_forward - P_reflected - P_line/match,loss; P_forward = P_plasma never assumed",
            "source": a92_src("OQ-A907-11") + "; " + a92_src("rf_measurement_reference")}},
          "retained 50-ohm segment and short match-to-antenna segment described"),
        R("A910-A92-A907-13", "A9.2 OQ-A907-11, icp_matching_strategy", "supersede", rp + "/options/a_on_module_pre_match",
          {"status": "PROPOSED (owner call, OQ-A907-11)"},
          {"status": "SUPERSEDED_BY_A9_2 (OQ-A907-11: an ADJUSTABLE local matching network on / immediately adjacent "
                     "to the ICP module is selected for the development article; a fixed network is only one possible "
                     "later flight implementation, decided after the impedance map)"}, "option a superseded"),
        R("A910-A92-A907-14", "A9.2 OQ-A907-11", "supersede", rp + "/options/b_rate_the_mismatched_segment",
          {"status": "FALLBACK"}, {"status": "NOT_BASELINE (A9.2 OQ-A907-11: the long coax no longer carries the antenna "
                                             "mismatch)"}, "option b not baseline"),
        R("A910-A92-A907-15", "A9.2 OQ-A907-11", "replace", rp + "/residual_vswr_note",
          "option (a) cases: the flexible segment sees only a residual mismatch after an on-module pre-match",
          "A9.2 retained 50-ohm segment: the coupler and the flexible line see only the residual mismatch after the "
          "local match", "residual VSWR note"),
        R("A910-A92-A907-16", "A9.2 OQ-A907-11, rf_500W", "replace", rp + "/sensitivity_loads_note",
          "No rating below is taken from them", "No rating below is taken from them. A9.2: they now describe the short "
          "match-to-antenna segment and the matching elements (voltage / current stress), not the 50-ohm line; ratings "
          "TBD_AFTER_IMPEDANCE_MAP", "sensitivity loads note"),
        R("A910-A92-A907-17", "A9.2 rf_500W", "merge", rp + "/P_net_max_W", {"a9_2_interpretation": ABSENT},
          {"a9_2_interpretation": "0-500 W is a laboratory delivered/operating investigation capability, not a component "
                                  "rating (" + a92_src("rf_500W") + ")"}, "500 W interpretation"),
        dict(_a92_answered("/open_owner_questions[id=OQ-A907-11]", "OQ-A907-11",
                           "supersedes the A9.1 A9-03-matching off-platform location for the A9 baseline"),
             cid="A910-A92-A907-Q01"),
        R("A910-A92-A907-18", "A9.2 OQ-A907-11", "merge", "/revision_register[id=REV-34]",
          {"superseded_in_part_by_a9_2": ABSENT},
          {"superseded_in_part_by_a9_2": "matching location: the off-platform tunable match with the coupler after the "
                                         "match is no longer the A9 baseline (A9.2 OQ-A907-11): " + LOCAL_CHAIN + "; " +
                                         MEAS_REF + "; history kept (this REV entry is not rewritten)"},
          "REV-34 superseded in part"),
        R("A910-A92-A907-19", "A9.2 anode_316L, anode_approach", "merge", "/revision_register[id=REV-50]",
          {"a9_2_anode": ABSENT}, {"a9_2_anode": {"text": ANODE_TEXT, "design_blockers": ["A9H-ANODE-01",
                                                                                          "A9H-ANODE-02"],
                                                  "source": a92_src("anode_316L") + "; " + a92_src("anode_approach")}},
          "REV-50 anode status"),
        R("A910-A92-A907-20", "A9.2 anode_316L", "gsub", "", "(row 87; 316L engineering baseline only, row 106)",
          "(row 87; 316L engineering baseline only, row 106; A9.2: 316L REJECTED_AS_CURRENT_BASELINE for the "
          "design-representative / flight anode, ANODE_BASELINE = OPEN, no new anode temperature limit)",
          "anode limit texts"),
        R("A910-A92-A907-21", "A9.2 anode_316L", "gsub", "", "the anode material (316L is only the H-1 engineering "
          "baseline, row 106)", "the anode material (316L: H-1 engineering baseline only per row 106 and "
          "REJECTED_AS_CURRENT_BASELINE for the design-representative / flight anode per A9.2; ANODE_BASELINE = OPEN)",
          "anode design-driver texts"),
        R("A910-A92-A907-22", "A9.2 anode_approach", "append", "/new_items", None, _new_item_a907(
            "A9H-ANODE-01", "DESIGN BLOCKER: H-1 anode material (design-representative / flight)",
            "TBD - requires the candidate-material trade (oxygen compatibility, sputtering, electrical behaviour, "
            "fabrication, thermal conductivity) on a reduced operating temperature; ANODE_BASELINE = OPEN",
            "-", "A9.2 anode_316L / anode_approach", ANODE_TEXT, items=("anode_316L", "anode_approach")),
          "anode material design blocker"),
        R("A910-A92-A907-23", "A9.2 anode_approach", "append", "/new_items", None, _new_item_a907(
            "A9H-ANODE-02", "DESIGN BLOCKER: H-1 anode heat-removal path (thermal-design problem first)",
            "TBD - requires the anode thermal redesign: " + "; ".join(ANODE_INVESTIGATION),
            "W; K", "A9.2 anode_approach", "objective: reduce the actual anode operating temperature substantially, then "
            "T_operating <= T_validated,continuous - 50 K; no new arbitrary anode temperature limit (A9.2)",
            items=("anode_approach",)), "anode heat-path design blocker"),
        R("A910-A92-A907-24", "A9.2 OQ-A907-11, icp_matching_strategy", "append", "/new_items", None, _new_item_a907(
            "A9H-RF-LM-01", "adjustable LOCAL matching network on / immediately adjacent to the ICP module "
            "(development article)", RATINGS_TBD, "ohm; V; A; W", "A9.2 OQ-A907-11 / icp_matching_strategy",
            "flight implementation (fixed / switched / electronically tuned / other) only after Z_antenna = R + jX is "
            "measured vs mdot, P_RF, p, gas composition and the Hall operating point; the sham carries a mass / "
            "stiffness equivalent of the on-module match (row 133; PROPOSED)", freeze="after-evidence",
            items=("OQ-A907-11", "icp_matching_strategy")), "local match item"),
        R("A910-A92-A907-25", "A9.2 rf_protection", "append", "/new_items", None, _new_item_a907(
            "A9H-RF-PROT-01", "RF source protection: " + ", ".join(PROTECTION), TRIP_TBD, "W; -",
            "A9.2 rf_protection", "trip thresholds frozen after the antenna / load characterization",
            items=("rf_protection",)), "RF protection item"),
        R("A910-A92-A907-26", "A9.2 icp_coupled_thermal, radiative_view_requirement", "append", "/new_items", None,
          _new_item_a907("A9H-TH-01", "coupled H-1 / ICP thermal model (A9.2 ICP_COUPLED_THERMAL)",
                         "TBD - requires the KC-1 / ICP module geometry and view factors: " + "; ".join(COUPLED_TERMS),
                         "W; K", "A9.2 icp_coupled_thermal", COUPLED_TEXT + "; " + POLE_TEXT,
                         items=("icp_coupled_thermal", "13W_pole_allowance", "radiative_view_requirement")),
          "coupled thermal model item"),
        R("A910-A92-A907-27", "A9.2 OQ-A907-11, icp_matching_strategy", "supersede", "/new_items[id=A9H-INS-14]",
          {"value": "OQ-A907-11", "status": "TBD"},
          {"value": "TBD - requires the ICP impedance map (A9.2 P2); SUPERSEDED_BY_A9_2 as the baseline treatment: the "
                    "adjustable local match (A9H-RF-LM-01) replaces the fixed pre-match / rated-mismatch options",
           "status": "SUPERSEDED_BY_A9_2"}, "A9H-INS-14 superseded"),
        R("A910-A92-A907-28", "A9.2 rf_500W, OQ-A907-11", "supersede", "/new_items[id=A9H-INS-01]",
          {"note": "0-500 W is the generator forward power"},
          {"note": "A9.2: the coupler sits on the generator / 50-ohm side of the local match and sees the residual "
                   "mismatch; 0-500 W is a laboratory delivered/operating investigation capability, not a component "
                   "rating; coupler / sensor ratings TBD_AFTER_IMPEDANCE_MAP. u(P_fwd), u(P_refl): A9-04 UB-RF-02..07"},
          "A9H-INS-01 note"),
        R("A910-A92-A907-29", "A9.2 OQ-A907-11", "set", "/new_items[id=A9H-INS-01]/value/coupler_plane_P_fwd_max_W",
          "TBD - requires Gamma_max at the coupler plane (on-module pre-match, OQ-A907-11) or the antenna impedance "
          "range (A9-03): P_fwd = P_net / (1 - |Gamma|^2) (recomputations.rf_reference_plane)", RATINGS_TBD,
          "coupler-plane rating TBD after impedance map"),
        R("A910-A92-A907-30", "A9.2 OQ-A907-11", "set", ids.format("IDA7-20") + "/status",
          "TBD - requires the A9-03 antenna design + S1a VNA measurement; owner call OQ-A907-11",
          "PARTIAL - the pre-match decision is ANSWERED by A9.2 OQ-A907-11 (adjustable local match for development); "
          "Z_antenna TBD - requires the ICP impedance map (A9.2 P2); ratings TBD_AFTER_IMPEDANCE_MAP", "IDA7-20"),
        R("A910-A92-A907-31", "A9.2 OQ-A907-11", "merge", ids.format("IDA7-22"), {"a9_2": ABSENT},
          {"a9_2": "ratings of coupler / sensors / coax / connectors / matching elements / feedthroughs "
                   "TBD_AFTER_IMPEDANCE_MAP; the optional fixed pre-match line is superseded by the adjustable local "
                   "match; protection items " + ", ".join(PROTECTION) + " (" + a92_src("rf_protection") + ")"},
          "IDA7-22"),
        R("A910-A92-A907-32", "A9.2 icp_coupled_thermal, 13W_pole_allowance", "merge", ids.format("IDA7-07"),
          {"a9_2": ABSENT}, {"a9_2": COUPLED_TEXT + "; " + POLE_TEXT}, "IDA7-07 coupled-thermal status"),
        R("A910-A92-A907-33", "A9.2 OQ-A907-11", "replace", h3.format("H3-A907-02") + "/item",
          "matching network for off-platform mounting (row 72)",
          "adjustable LOCAL matching network for mounting on / immediately adjacent to the ICP module (row 72; A9.2 "
          "OQ-A907-11); component ratings TBD_AFTER_IMPEDANCE_MAP", "H3-A907-02"),
        R("A910-A92-A907-34", "A9.2 OQ-A907-11", "replace", h3.format("H3-A907-15") + "/item",
          "optional on-module fixed pre-match",
          "SUPERSEDED_BY_A9_2 (replaced by the adjustable local match, H3-A907-02): optional on-module fixed pre-match",
          "H3-A907-15 superseded"),
        R("A910-A92-A907-35", "A9.2 icp_coupled_thermal", "replace", m16.format(10) + "/how_touched",
          "coil node closure CLOSES_ONLY_WITH_COMBINED_LEVERS / CLOSES",
          "coil node closure UNRESOLVED (A9.2 ICP_COUPLED_THERMAL; uncoupled sensitivity CLOSES_ONLY_WITH_COMBINED_"
          "LEVERS / CLOSES)", "M16 row 10"),
        R("A910-A92-A907-36", "A9.2 icp_coupled_thermal", "merge", m16.format(13),
          {"how_touched": "thermal rerun with the owner rules; BN wall CLOSES_WITH_SINGLE_LEVER (REV-40..50)",
           "blocking_item": "measured deposition fractions / sourced BN k(T)"},
          {"how_touched": "thermal rerun with the owner rules (REV-40..50); every hall_icp_neutralizer thermal closure "
                          "reported UNRESOLVED (A9.2 ICP_COUPLED_THERMAL; BN wall uncoupled sensitivity "
                          "CLOSES_WITH_SINGLE_LEVER)",
           "blocking_item": "coupled H-1 / ICP thermal model (A9H-TH-01: Q_Hall->ICP, Q_collector, Q_RF/match, Q_plume, "
                            "ICP view factors; A9.2 ICP_COUPLED_THERMAL = UNRESOLVED)"}, "M16 row 13"),
        R("A910-A92-A907-37", "A9.2 OQ-A907-11", "merge", m16.format(15),
          {"blocking_item": "quotations (A9-09) + antenna impedance / pre-match decision (OQ-A907-11)"},
          {"blocking_item": "quotations (A9-09) + ICP antenna impedance map (A9.2 P2; RF component ratings "
                            "TBD_AFTER_IMPEDANCE_MAP)"}, "M16 row 15"),
        R("A910-A92-A907-38", "A9.2 anode_approach", "replace", m16.format(9) + "/how_touched",
          "exit face = IP-EXIT (REV-01..03)", "exit face = IP-EXIT (REV-01..03); A9.2 anode design blockers "
          "A9H-ANODE-01 (material) / A9H-ANODE-02 (heat-removal path), ANODE_BASELINE = OPEN", "M16 row 9"),
        R("A910-A92-A907-39", "A9.2 OQ-A907-11", "replace", "/a9_1_decisions_applied[id=A9-03-matching]/how_applied",
          "S-parameter correction (REV-34, A9H-INS-03)", "S-parameter correction (REV-34, A9H-INS-03); location "
          "SUPERSEDED for the A9 baseline by A9.2 OQ-A907-11 (local match on / adjacent to the ICP module, coupler on "
          "the generator / 50-ohm side)", "A9.1 application superseded in part"),
        R("A910-A92-A907-40", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/how_applied",
          "(rf_reference_plane, OQ-A907-11)", "(rf_reference_plane; OQ-A907-11 answered by A9.2: 0-500 W is a "
          "laboratory delivered/operating capability, not a component rating)", "row 72 application"),
        R("A910-A92-A907-41", "A9.2 anode_316L", "replace", "/owner_answers_applied[row=106]/how_applied",
          "316L engineering-only anode baseline (REV-50)", "316L engineering-only anode baseline (REV-50); A9.2: 316L "
          "REJECTED_AS_CURRENT_BASELINE for the design-representative / flight anode, ANODE_BASELINE = OPEN",
          "row 106 application"),
        R("A910-A92-A907-42", "A9.2 a9_10_statuses", "set", "/a9_2_statuses", ABSENT,
          {"a9_2_statuses": {"statuses": "see " + RECORD_REL + " a9_2.statuses (verbatim A9.2 item 9)",
                             "applied_here": {k: v for k, v in (("RF matching architecture", "LOCAL_MATCH_SELECTED_FOR_"
                                                                 "DEVELOPMENT"), ("RF component ratings",
                                                                                  "TBD_AFTER_IMPEDANCE_MAP"),
                                                                ("316L flight anode", "REJECTED_AS_CURRENT_BASELINE"),
                                                                ("final anode material", "OPEN"),
                                                                ("anode thermal closure", UNRES),
                                                                ("coupled H-1/ICP thermal closure", UNRES))},
                             "source": a92_src("a9_10_statuses")}}["a9_2_statuses"], "A9.2 statuses carried"),
    ]


def _a92_a903() -> list:
    it = "/items[id={}]"
    return [
        R("A910-A92-A903-01", "A9.2 OQ-A907-11, icp_matching_strategy", "supersede", it.format("ICP-13"),
          {"value": "off the moving thrust-stand platform", "status": "OWNER_GIVEN (location, A9.1)",
           "tbd": "TBD - requires the S1a dummy-load"},
          {"value": LOCAL_CHAIN + " (A9.2 OQ-A907-11): the long flexible coax on the thrust stand stays approximately a "
                    "controlled 50-ohm line; the matching network is ADJUSTABLE for the development article; the flight "
                    "implementation (fixed / switched / electronically tuned / other) is deferred until Z_antenna = R + "
                    "jX is measured vs mdot, P_RF, p, gas composition and the Hall operating point; RF reference planes: "
                    "A9-07 recomputations.rf_reference_plane.a9_2_segments",
           "status": "OWNER_GIVEN (A9.2 OQ-A907-11: LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT; supersedes the A9.1 "
                     "A9-03-matching off-platform location for the baseline)",
           "tbd": RATINGS_TBD}, "matching network location: local match (A9.2)"),
        R("A910-A92-A903-02", "A9.2 OQ-A907-11", "merge", it.format("ICP-13"), {"a9_2_decision": ABSENT},
          {"a9_2_decision": a92_text("OQ-A907-11") + " | " + a92_text("icp_matching_strategy") + " (" +
                            a92_src("OQ-A907-11") + ")"}, "A9.2 decision text on ICP-13"),
        R("A910-A92-A903-03", "A9.2 rf_measurement_reference", "replace", it.format("ICP-14") + "/requirement",
          "net delivered power = P_fwd - P_refl at that plane.",
          "net power at that plane = P_fwd - P_refl; the plane is on the generator / 50-ohm side of the local matching "
          "network and the delivered power is P_delivered = P_forward - P_reflected - P_line/match,loss (A9.2); "
          "P_forward = P_plasma is never assumed.", "ICP-14 measurement reference"),
        R("A910-A92-A903-04", "A9.2 rf_measurement_reference", "merge", it.format("ICP-14"),
          {"a9_2_measurement_reference": ABSENT}, {"a9_2_measurement_reference": MEAS_REF + " (" +
                                                    a92_src("rf_measurement_reference") + ")"},
          "ICP-14 retained quantities"),
        R("A910-A92-A903-05", "A9.2 rf_500W", "supersede", it.format("ICP-15"),
          {"requirement": "rated for at least the full laboratory forward power (row 72)", "status": "TBD",
           "tbd": "TBD - requires the generator/matching-network selection"},
          {"requirement": "Coax, vacuum feedthrough, connectors and the local matching elements (incl. their voltage and "
                          "current) are selected only after the expected mismatch envelope is characterized (A9.2): the "
                          "row-72 0-500 W figure is a laboratory delivered/operating investigation capability, not a "
                          "sufficient component rating by itself (A9-07 sensitivity: VSWR about 5.2 -> P_forward about "
                          "925 W for 500 W delivered); impedance, voltage rating and connector family follow the "
                          "impedance map and the selected generator (quotations only, row 8).",
           "status": "TBD (TBD_AFTER_IMPEDANCE_MAP, A9.2)", "tbd": RATINGS_TBD}, "ICP-15 ratings after impedance map"),
        R("A910-A92-A903-06", "A9.2 rf_protection", "merge", it.format("ICP-16"),
          {"a9_2_protection": ABSENT, "a9_2_trip_thresholds": ABSENT},
          {"a9_2_protection": PROTECTION, "a9_2_trip_thresholds": TRIP_TBD}, "ICP-16 RF protection items"),
        R("A910-A92-A903-07", "A9.2 rf_500W", "merge", it.format("ICP-12"), {"a9_2_interpretation": ABSENT},
          {"a9_2_interpretation": "0-500 W is a laboratory delivered/operating investigation capability, not a "
                                  "component rating (" + a92_src("rf_500W") + ")"}, "ICP-12 interpretation"),
        R("A910-A92-A903-08", "A9.2 OQ-A907-11", "merge", it.format("ICP-18"), {"a9_2_note": ABSENT},
          {"a9_2_note": "with the local match (A9.2 OQ-A907-11) the flexible coax across the stand is the retained, "
                        "approximately controlled 50-ohm segment; the on-module match adds mass / stiffness on the "
                        "moving platform, so the sham configuration carries an equivalent (row 133; PROPOSED, value TBD - "
                        "requires the match selection and module drawing)"}, "ICP-18 coax role"),
        R("A910-A92-A903-09", "A9.2 OQ-A907-11, icp_coupled_thermal", "merge", it.format("ICP-36"), {"a9_2_note": ABSENT},
          {"a9_2_note": "the local matching network sits on / adjacent to the module (A9.2), so its loss "
                        "P_line/match,loss is dissipated on the module and is part of Q_RF/match in ICP-43; the 600 W "
                        "RF-only partial allocation term is unchanged and is not a component rating"},
          "ICP-36 local match heat"),
        R("A910-A92-A903-10", "A9.2 icp_coupled_thermal, 13W_pole_allowance", "replace",
          it.format("ICP-43") + "/h1_heat_allowance_a9_07",
          "every hall_icp_neutralizer thermal CLOSES is conditional on the actual ICP-43 heat meeting this allowance",
          "every hall_icp_neutralizer thermal result is an uncoupled sensitivity reported as UNRESOLVED (" + COUPLED_TEXT +
          "); " + POLE_TEXT, "ICP-43 coupled thermal status"),
        R("A910-A92-A903-11", "A9.2 icp_coupled_thermal, OQ-A907-11", "merge", it.format("ICP-43"),
          {"a9_2_coupled_thermal": ABSENT},
          {"a9_2_coupled_thermal": {"ICP_COUPLED_THERMAL": UNRES, "required_terms": COUPLED_TERMS,
                                    "local_match": "the local match sits on / adjacent to the module (A9.2): Q_RF/match "
                                                   "enters Q_mod",
                                    "prohibited_assumption": "negligible ICP thermal coupling",
                                    "source": a92_src("icp_coupled_thermal")}}, "ICP-43 coupled thermal block"),
        R("A910-A92-A903-12", "A9.2 icp_coupled_thermal, radiative_view_requirement", "replace",
          it.format("ICP-05") + "/view_condition_a9_07", "the downstream module's view of the H-1 exit face enters the "
          "ICP-43 heat split", "the downstream module's view of the H-1 exit face enters the ICP-43 heat split; A9.2: the "
          "ICP assembly's geometric effect on H-1 radiation is a required term of the coupled thermal model "
          "(ICP_COUPLED_THERMAL = UNRESOLVED); radiative-view objective ICP-47", "ICP-05 view condition"),
        R("A910-A92-A903-13", "A9.2 radiative_view_requirement, 13W_pole_allowance", "append", "/items", None, {
            "id": "ICP-47", "group": "mechanical",
            "title": "Radiative-view-factor design objective for the downstream ICP assembly",
            "requirement": "The ICP mechanical design carries a radiative-view-factor objective (A9.2): investigate "
                           + "; ".join(VIEW_OBJECTIVE) + ". The geometry is not optimized for compactness alone; the ICP "
                           "must not solve the cathode problem by creating an unacceptable Hall-head thermal problem. The "
                           "downstream ICP can obstruct H-1's radiative view, radiate back toward the Hall head, conduct "
                           "heat through the carrier and intercept plume energy; a coupled view-factor / conduction "
                           "calculation (A9-07 A9H-TH-01) is required before thermal closure, and the negligible-coupling "
                           "assumption is prohibited (" + POLE_TEXT + ").",
            "value": None, "units": "- (view factors); mm (axial spacing)",
            "basis": "A9.2 radiative_view_requirement / icp_coupled_thermal / 13W_pole_allowance; the >= 50 K rule of "
                     "owner row 86 applies to the resulting temperatures (ICP-37)",
            "sources": [{"path": A92_REL, "sha256": A92_SHA, "id": x, "role": "owner decision (A9.2)"}
                        for x in ("radiative_view_requirement", "icp_coupled_thermal", "13W_pole_allowance")],
            "evidence_class": None, "status": "OWNER_GIVEN_OBJECTIVE (A9.2); geometry TBD", "freeze_point": "LOCK-1",
            "verification": "view-factor analysis of the module drawing + coupled H-1 / ICP thermal model; thermocouple "
                            "map with the module installed / removed in S1a",
            "owner_rows": [], "applies_to": ["hall_icp_neutralizer"],
            "tbd": "TBD - requires the KC-1 / ICP module drawing, its view factors to H-1 and the coupled thermal model "
                   "(A9.2 post-A9 priority P3)"}, "ICP-47 radiative-view objective"),
        R("A910-A92-A903-14", "A9.2 OQ-A907-11", "merge", "/open_owner_questions[id=ICPQ-05]",
          {"superseded_in_part_by_a9_2": ABSENT},
          {"superseded_in_part_by_a9_2": "location superseded for the baseline by A9.2 OQ-A907-11 (local adjustable "
                                         "match on / adjacent to the ICP module; coupler on the generator / 50-ohm side); "
                                         "the A9.1 answer is kept as history (" + a92_src("OQ-A907-11") + ")"},
          "ICPQ-05 supersession"),
        R("A910-A92-A903-15", "A9.2 OQ-A907-11", "supersede", "/h3_h4_inputs/h3_procurement_quotation_only[1]",
          {"item": "matching network (auto or manual) rated for full forward power"},
          {"item": "adjustable LOCAL matching network on / immediately adjacent to the ICP module (development article, "
                   "A9.2); component ratings incl. matching-element voltage / current TBD_AFTER_IMPEDANCE_MAP"},
          "h3 matching item"),
        R("A910-A92-A903-16", "A9.2 rf_protection", "append", "/h3_h4_inputs/h3_procurement_quotation_only", None,
          {"item": "RF source protection: " + ", ".join(PROTECTION) + " (trip thresholds TBD after load "
                   "characterization)", "spec_level": "ICP-16", "status": "quotation only (row 8)"},
          "h3 protection item"),
        R("A910-A92-A903-17", "A9.2 post_a9_priorities (P1, P2)", "append", "/h3_h4_inputs/h4_tests", None,
          {"stage": "ICP bench (A9.2 P1 / P2; recommended, not launched)",
           "measure": "I_e(P_RF, Z, p, mdot, gas) (ICP-45) and the impedance map Z_antenna = R + jX vs mdot, P_RF, p, "
                      "gas composition and Hall operating point",
           "closes": "ICP-45 entry evidence; ICP-13 flight implementation; ICP-15 ratings"}, "h4 impedance map"),
    ]


def _a92_a904() -> list:
    it = "/items[id={}]"
    return [
        R("A910-A92-A904-01", "A9.2 OQ-A907-11, rf_measurement_reference", "supersede", it.format("UB-RF-09"),
          {"value": "directional-coupler reference plane AFTER the matching network"},
          {"value": "directional coupler on the generator / 50-ohm side of the LOCAL matching network (on / immediately "
                    "adjacent to the ICP module; A9.2 OQ-A907-11 supersedes the A9.1 off-platform arrangement for the "
                    "baseline); " + MEAS_REF}, "UB-RF-09 reference plane"),
        R("A910-A92-A904-02", "A9.2 OQ-A907-11", "merge", it.format("UB-RF-09"), {"a9_2_decision": ABSENT},
          {"a9_2_decision": a92_src("OQ-A907-11") + "; " + a92_src("rf_measurement_reference")}, "UB-RF-09 source"),
        R("A910-A92-A904-03", "A9.2 rf_measurement_reference", "supersede", it.format("UB-RF-05"),
          {"name": "matching-network and cable loss between the coupler plane and the coil"},
          {"name": "50-ohm line and local matching-network loss P_line/match,loss between the coupler plane "
                   "(generator / 50-ohm side) and the antenna (A9.2)"}, "UB-RF-05 name"),
        R("A910-A92-A904-04", "A9.2 rf_measurement_reference", "replace", it.format("UB-RF-04") + "/value",
          "the operating |Gamma| at the coupler plane", "the operating |Gamma| at the coupler plane (A9.2: generator / "
          "50-ohm side of the local match, i.e. the residual mismatch after the local match)", "UB-RF-04 |Gamma|"),
        R("A910-A92-A904-05", "A9.2 rf_measurement_reference", "append", "/measurement_chains[dq=UB-DQ-RF]/equations",
          None, "P_delivered = P_forward - P_reflected - P_line/match,loss (A9.2; the same quantity as P_coil above, "
                "P_line/match,loss = P_loss,mn + P_loss,cable); P_forward = P_plasma is never assumed",
          "P_delivered equation"),
        R("A910-A92-A904-06", "A9.2 OQ-A907-11, icp_matching_strategy", "supersede", "/interface_demands[id=IF-08]",
          {"value": "A9.1 A9-03-matching (ICD ICP-13)"},
          {"value": "A9.2 OQ-A907-11 (ICD ICP-13): adjustable local match on / adjacent to the ICP module, coupler on the "
                    "generator / 50-ohm side; flight match implementation deferred until the impedance map; ratings "
                    "TBD_AFTER_IMPEDANCE_MAP"}, "IF-08"),
    ]


def _a92_a909() -> list:
    rf = "/packages[id=RFQ-04]/requirements[id={}]"
    def src(item):
        return {"type": "a9_2", "key": "A9.2", "id": item, "path": A92_REL, "pointer": "/decisions/" + item,
                "sha256": A92_SHA}
    a92s = src("OQ-A907-11")
    return [
        R("A910-A92-A909-01", "A9.2 OQ-A907-11", "supersede", "/packages[id=RFQ-01]/requirements[id=RFQ-01-R12]",
          {"title": "matching network off the platform", "requirement": "OFF the moving platform",
           "value": "off-platform"},
          {"title": "local matching network on the ICP module (moving platform)",
           "requirement": "Baseline (A9.2 OQ-A907-11): the adjustable local RF matching network sits on / immediately "
                          "adjacent to the ICP module on the moving platform; an approximately controlled 50-ohm flexible "
                          "coax crosses the stage (see RFQ-04); the stand must accept one live and one sham RF coax and "
                          "the on-module match mass (TBD - requires the match selection).",
           "value": "on-module local match (A9.2)"}, "RFQ-01-R12 local match"),
        R("A910-A92-A909-02", "A9.2 OQ-A907-11", "append", "/packages[id=RFQ-01]/requirements[id=RFQ-01-R12]/sources",
          None, a92s, "RFQ-01-R12 A9.2 source"),
        R("A910-A92-A909-03", "A9.2 OQ-A907-11", "replace", "/packages[id=RFQ-04]/scope",
          "off-platform matching network, calibrated dual directional coupler with forward/reflected sensors at the "
          "reference plane after the matching network",
          "adjustable LOCAL matching network on / immediately adjacent to the ICP module (A9.2 OQ-A907-11), calibrated "
          "dual directional coupler with forward/reflected sensors on the generator / 50-ohm side of the local match "
          "(component ratings TBD_AFTER_IMPEDANCE_MAP)", "RFQ-04 scope"),
        R("A910-A92-A909-04", "A9.2 OQ-A907-11", "supersede", "/packages[id=RFQ-04]/quantities[1]",
          {"item": "matching network (manual or auto)"},
          {"item": "adjustable local matching network for on-module mounting (development article, A9.2)"},
          "RFQ-04 quantity"),
        R("A910-A92-A909-05", "A9.2 OQ-A907-11, icp_matching_strategy", "supersede", rf.format("RFQ-04-R06"),
          {"requirement": "Baseline OFF the moving thrust-stand platform", "value": "off-platform"},
          {"requirement": "Baseline (A9.2 OQ-A907-11): " + LOCAL_CHAIN + "; adjustable for the development article; the "
                          "long flexible coax stays an approximately controlled 50-ohm line; the flight implementation "
                          "is deferred until the impedance map; matched sham routing in the C1 configuration (row 133).",
           "value": "local match on / immediately adjacent to the ICP module"}, "RFQ-04-R06 location"),
        R("A910-A92-A909-06", "A9.2 OQ-A907-11", "append", rf.format("RFQ-04-R06") + "/sources", None, a92s,
          "RFQ-04-R06 A9.2 source"),
        R("A910-A92-A909-07", "A9.2 rf_500W, icp_matching_strategy", "supersede", rf.format("RFQ-04-R07"),
          {"requirement": "Rated for the full laboratory forward power", "value": "TBD - requires A902-22"},
          {"requirement": "Adjustable (manual or auto-tuned) local matching network for the development article; its "
                          "power, voltage and current ratings are selected only after the mismatch envelope is "
                          "characterized (A9.2: 0-500 W is a laboratory delivered/operating capability, not a component "
                          "rating); any DC draw (tuning actuators/controller) metered as its own bus slot.",
           "value": RATINGS_TBD + "; A902-22 DC draw; ICD ICP-15"}, "RFQ-04-R07 ratings TBD"),
        R("A910-A92-A909-08", "A9.2 rf_measurement_reference", "supersede", rf.format("RFQ-04-R08"),
          {"requirement": "at a declared reference plane AFTER the matching network", "value": "after the matching network"},
          {"requirement": "Directional coupler with forward and reflected sensors on the generator / 50-ohm side of the "
                          "local matching network (A9.2 OQ-A907-11); calibrated at 13.56 MHz; coupling factor, "
                          "directivity and sensor linearity certified; " + MEAS_REF + ". Ratings at the residual |Gamma| "
                          "after the local match are TBD_AFTER_IMPEDANCE_MAP (A9-07 IDA7-22, H3-A907-03).",
           "value": "generator / 50-ohm side of the local match"}, "RFQ-04-R08 coupler position"),
        R("A910-A92-A909-09", "A9.2 rf_measurement_reference", "append", rf.format("RFQ-04-R08") + "/sources", None,
          src("rf_measurement_reference"), "RFQ-04-R08 A9.2 source"),
        R("A910-A92-A909-10", "A9.2 OQ-A907-11", "replace", rf.format("RFQ-04-R11") + "/requirement",
          "(A9-07 H3-A907-04, REV-33, A9H-INS-15).", "(A9-07 H3-A907-04, REV-33, A9H-INS-15); A9.2: this coax is the "
          "retained 50-ohm segment on the generator side of the local match; ratings TBD_AFTER_IMPEDANCE_MAP.",
          "RFQ-04-R11"),
        R("A910-A92-A909-11", "A9.2 rf_500W", "supersede", rf.format("RFQ-04-R12"),
          {"requirement": "Rated for the full laboratory forward power", "value": "TBD - requires ICD ICP-15"},
          {"requirement": "RF-voltage, creepage/clearance and Paschen rating and combined RF + DC stress qualification "
                          "(ICP-44; not replaced by the C1 keeper hipot); power / voltage / current ratings selected only "
                          "after the mismatch envelope is characterized (A9.2; 0-500 W is not a component rating).",
           "value": RATINGS_TBD + "; ICD ICP-15 / ICP-44 (LOCK-1)"}, "RFQ-04-R12 ratings TBD"),
        R("A910-A92-A909-12", "A9.2 OQ-A907-11, icp_matching_strategy", "supersede", rf.format("RFQ-04-R15"),
          {"title": "optional on-module fixed pre-match (option line)", "value": "TBD - requires the owner answer"},
          {"title": "optional on-module fixed pre-match (option line) - SUPERSEDED_BY_A9_2",
           "value": "TBD - requires the ICP impedance map (A9.2 P2): the option line is superseded by the adjustable local "
                    "match (RFQ-04-R06 / R17); a fixed network is only one possible later flight implementation"},
          "RFQ-04-R15 superseded"),
        R("A910-A92-A909-13", "A9.2 rf_500W", "merge", rf.format("RFQ-04-R02"), {"a9_2_interpretation": ABSENT},
          {"a9_2_interpretation": "0-500 W is a laboratory delivered/operating investigation capability, not a component "
                                  "rating (A9.2 rf_500W)"}, "RFQ-04-R02 interpretation"),
        R("A910-A92-A909-14", "A9.2 rf_protection", "append", "/packages[id=RFQ-04]/requirements", None, {
            "id": "RFQ-04-R16", "title": "RF source protection functions",
            "requirement": "The RF source provides " + ", ".join(PROTECTION) + " (A9.2). Exact reflected-power and VSWR "
                           "trip thresholds are frozen after the ICP antenna/load characterization and are not stated "
                           "in this RFQ.",
            "value": TRIP_TBD, "units": "W; -", "basis": "A9.2 rf_protection", "sources": [src("rf_protection")],
            "evidence_class": None, "status": "TBD", "freeze_point": "after-evidence",
            "applies_to": ["hall_icp_neutralizer"], "note": "added in A9-10 for A9.2 (quotation only; no purchase order)"},
          "RFQ-04-R16 protection"),
        R("A910-A92-A909-15", "A9.2 OQ-A907-11, icp_matching_strategy, rf_500W", "append",
          "/packages[id=RFQ-04]/requirements", None, {
              "id": "RFQ-04-R17", "title": "local matching network: on-module mass and matching-element voltage / current",
              "requirement": "Supplier states the mass and envelope of the adjustable local matching network for on-module "
                             "mounting and the voltage / current capability of its elements; required values are set "
                             "after the impedance map (A9.2). No rating is stated in this RFQ.",
              "value": RATINGS_TBD, "units": "kg; V; A", "basis": "A9.2 OQ-A907-11 / icp_matching_strategy / rf_500W",
              "sources": [src("OQ-A907-11"), src("icp_matching_strategy"), src("rf_500W")], "evidence_class": None,
              "status": "TBD", "freeze_point": "after-evidence", "applies_to": ["hall_icp_neutralizer"],
              "note": "added in A9-10 for A9.2 (quotation only)"}, "RFQ-04-R17 local match mass / V-I"),
        R("A910-A92-A909-16", "A9.2 OQ-A907-11", "append", "/packages[id=RFQ-05]/requirements", None, {
            "id": "RFQ-05-R13", "title": "on-module mounting provision for the local matching network",
            "requirement": "The ICP source components provide a mounting and thermal interface for the local matching "
                           "network on / immediately adjacent to the module (A9.2); its heat (P_line/match,loss) is part "
                           "of the module heat load (ICD ICP-43) and its mass of the on-module payload (ICD ICP-08).",
            "value": "TBD - requires the ICP module drawing and the local-match selection (A9.2; ratings "
                     "TBD_AFTER_IMPEDANCE_MAP)", "units": "kg; W", "basis": "A9.2 OQ-A907-11",
            "sources": [src("OQ-A907-11"), src("icp_coupled_thermal")], "evidence_class": None, "status": "TBD",
            "freeze_point": "after-evidence", "applies_to": ["hall_icp_neutralizer"],
            "note": "added in A9-10 for A9.2 (quotation only)"}, "RFQ-05-R13 on-module match provision"),
        R("A910-A92-A909-17", "A9.2 anode_316L, anode_approach", "set", "/a9_2_anode_note", ABSENT,
          "No anode RFQ is implied by A9.2: ANODE_BASELINE = OPEN; 316L REJECTED_AS_CURRENT_BASELINE for the "
          "design-representative / flight anode; final anode material OPEN; no refractory metal selected; the anode "
          "material and heat-removal path are design blockers (A9-07 A9H-ANODE-01 / A9H-ANODE-02). RFQ-05-R03 concerns "
          "the ICP collector, not the Hall anode.", "no anode RFQ"),
    ]


def _a92_a906() -> list:
    b = "/a9_flight_bom/flight[id={}]"
    return [
        R("A910-A92-A906-01", "A9.2 OQ-A907-11, icp_matching_strategy", "supersede", b.format("A9B-20"),
          {"name": "flight RF matching network", "status": "TBD - requires a flight matching-network design"},
          {"name": "local RF matching network hardware on / immediately adjacent to the ICP module (A9.2)",
           "status": "TBD - requires the local-match selection after the impedance map (A9.2: adjustable for the "
                     "development article; flight implementation deferred until Z_antenna = R + jX is mapped)"},
          "A9B-20 local match line"),
        R("A910-A92-A906-02", "A9.2 OQ-A907-11", "merge", b.format("A9B-20"), {"allocation_mapping_proposal_a9_2": ABSENT},
          {"allocation_mapping_proposal_a9_2": "PROPOSED only: the local match is on the ICP module; it may be booked "
                                               "within the ICP-head (AL-05) or the RF (AL-06) allocation; kept on AL-06 "
                                               "here (no number changes); owner call with MQ-07"},
          "A9B-20 allocation mapping proposal"),
        R("A910-A92-A906-03", "A9.2 OQ-A907-11", "merge", b.format("A9B-17"), {"a9_2_note": ABSENT},
          {"a9_2_note": "the local matching network hardware is mounted on / adjacent to this module (A9.2); its mass is "
                        "the separate TBD line A9B-20"}, "A9B-17 note"),
        R("A910-A92-A906-04", "A9.2 anode_316L, anode_approach", "merge", b.format("A9B-15"), {"a9_2_anode": ABSENT},
          {"a9_2_anode": ANODE_TEXT + "; anode material and heat-removal path hardware mass TBD - requires the anode "
                                      "design (A9-07 A9H-ANODE-01 / A9H-ANODE-02)"}, "A9B-15 anode note"),
        R("A910-A92-A906-08", "A9.2 OQ-A907-11", "replace", "/a9_flight_bom/ground_article_only[1]/item",
          "matching network off the moving platform (A9.1 A9-03-matching)",
          "adjustable local matching network on / adjacent to the ICP module (A9.2 OQ-A907-11; supersedes the A9.1 "
          "off-platform location)", "ground-article matching location"),
        R("A910-A92-A906-09", "A9.2 OQ-A907-11", "replace", "/a9_1_decisions_applied[4]/how_applied",
          "matching network off the moving platform (ground)", "matching network off the moving platform (ground; "
          "superseded for the baseline by A9.2 OQ-A907-11: local match on / adjacent to the ICP module)",
          "A9.1 application superseded in part"),
        R("A910-A92-A906-05", "A9.2 coil_mass_correction", "supersede", "/lv_coil_sensitivity",
          {"label": "sensitivity only (not booked)"},
          {"label": "sensitivity only (not booked): LV-COIL adoption is an owner/LOCK-1 call; mass to book TBD - requires "
                    "the frozen H-1 coil (A9-07 IDA7-01). A9.2 coil-mass correction: the 60 W-basis copper (0.136 kg) is "
                    "NOT the MC-1 coil mass; the RP-1 basis (1.58 kg) is the complete-coil copper estimate; the two rows "
                    "are different bases, never alternative estimates of the same mass"}, "LV-COIL label"),
        R("A910-A92-A906-06", "A9.2 coil_mass_correction", "merge", "/lv_coil_sensitivity",
          {"a9_2_coil_mass_correction": ABSENT}, {"a9_2_coil_mass_correction": COIL_TEXT}, "coil-mass correction"),
        R("A910-A92-A906-07", "A9.2 coil_mass_correction", "merge", "/wet_closure",
          {"closure_mass_basis_a9_2": ABSENT},
          {"closure_mass_basis_a9_2": "the closure books MC-1 only as A9B-16 (3.504 kg = H2-1 H21-24 iron 1.925 kg + "
                                      "complete-coil copper 1.579 kg); the 0.136 kg 60 W-basis copper and the LV-COIL "
                                      "sensitivity are never booked (A9.2 coil_mass_correction)"}, "closure mass basis"),
    ]


def _a92_a902() -> list:
    sl = "/slots[slot={}]"
    return [
        R("A910-A92-A902-01", "A9.2 OQ-A907-11, rf_measurement_reference", "merge", sl.format("icp_rf_source"),
          {"a9_2_note": ABSENT},
          {"a9_2_note": "A9.2: forward/reflected power is measured on the generator / 50-ohm side of the local match; "
                        "the 50-ohm line and local matching-network loss P_line/match,loss lies inside P_forward and is "
                        "therefore paid through this slot's DC input; P_delivered = P_forward - P_reflected - "
                        "P_line/match,loss is a measurement quantity, never a bus quantity"}, "icp_rf_source match loss"),
        R("A910-A92-A902-02", "A9.2 OQ-A907-11, icp_matching_strategy", "merge", sl.format("icp_matching_network"),
          {"a9_2_note": ABSENT},
          {"a9_2_note": "A9.2: adjustable LOCAL matching network on / adjacent to the ICP module (development article); "
                        "this slot carries only its tuning actuator / controller DC draw; its RF dissipation "
                        "(P_line/match,loss) is counted in icp_rf_source and is a module heat term (ICD ICP-43 "
                        "Q_RF/match)"}, "icp_matching_network slot"),
        R("A910-A92-A902-03", "A9.2 OQ-A907-11", "replace", "/items[id=A902-22]/source",
          "(A9-03, merged; A9.1 A9-03-matching fixes the location off the moving platform but not fixed vs auto-tuned; "
          "on-module pre-match OQ-A907-11 OPEN)",
          "(A9-03, merged; A9.2 OQ-A907-11: adjustable local match on / adjacent to the ICP module for development; "
          "flight implementation after the impedance map)", "A902-22 source"),
        R("A910-A92-A902-04", "A9.2 OQ-A907-11", "replace", "/h3_inputs[2]/basis",
          "(A9.1 A9-03-matching: off the moving platform; fixed vs auto-tuned and the on-module pre-match OQ-A907-11 "
          "still open)", "(A9.2 OQ-A907-11: adjustable local match on / adjacent to the ICP module; ratings "
          "TBD_AFTER_IMPEDANCE_MAP)", "h3 matching basis"),
    ]


def _a92_a901() -> list:
    return [
        R("A910-A92-A901-01", "A9.2 OQ-A907-11", "replace", "/interface_demands[8]/status",
          "matching network off the platform", "matching network off the platform (superseded for the baseline by A9.2 "
          "OQ-A907-11: local adjustable match on / adjacent to the ICP module, coupler on the generator / 50-ohm side)",
          "A9-01 demand text"),
    ]


def _a92() -> dict:
    return {"A9-01": _a92_a901(), "A9-02": _a92_a902(), "A9-03": _a92_a903(), "A9-04": _a92_a904(),
            "A9-06": _a92_a906(), "A9-07": _a92_a907(), "A9-09": _a92_a909()}


# ------------------------------------------------------------------------------------------------------ A9.2 repair
# A9-10 review repair 3 (A9.2 residual wording): the A9.2 overlay above relabelled the status-like fields, but key
# findings, revision-register rows (REV-42 / REV-44 / REV-45 / REV-47), the IDA7-07 demand, the Curie-check clause,
# the per-node nominal_closes flags and several supplier-facing RF texts still read as PASS / CLOSES or rated the RF
# chain at 500 W. Every record below is a wording / label change required by A9.2 (icp_coupled_thermal: no thermal
# PASS from a negligible-coupling calculation; rf_500W: 0-500 W is a delivered/operating capability, never a component
# rating). No number changes; computed values are kept as uncoupled_sensitivity_* (history never deleted).
UNRES_LABEL = "reported UNRESOLVED, A9.2 ICP_COUPLED_THERMAL"
DELIV_500 = ("0-500 W delivered/operating investigation capability (row 72 as interpreted by A9.2 rf_500W; not a "
             "component rating)")
GEN_RATING_TBD = ("generator forward-power rating and the ratings of the inline chain are TBD_AFTER_IMPEDANCE_MAP (A9.2 "
                  "rf_500W: selected only after the expected mismatch envelope is characterized; with the A9-07 review "
                  "sensitivity VSWR about 5.2, about 925 W forward is needed for 500 W delivered, which is why a 500 W "
                  "rating alone is unacceptable)")
A91_HISTORY_ROLE = ("history: A9.1 A9-03-matching quote kept for provenance; the off-platform location is superseded for "
                    "the A9 baseline by A9.2 OQ-A907-11")


def _a92_thermal_residual(th: dict) -> int:
    """A9.2 ICP_COUPLED_THERMAL (residual): the per-node boolean nominal_closes of every hall_icp_neutralizer result
    is an uncoupled-sensitivity flag; it is kept under uncoupled_sensitivity_nominal_closes (value unchanged).
    Returns the number of renamed flags."""
    n = 0
    for _lv, cases in th["results"]["hall_icp_neutralizer"].items():
        for _c, rec in cases.items():
            for _node, e in rec["nodes"].items():
                if "nominal_closes" in e:
                    if "uncoupled_sensitivity_nominal_closes" in e:
                        raise OverlayError("nominal_closes already relabelled")
                    e["uncoupled_sensitivity_nominal_closes"] = e.pop("nominal_closes")
                    n += 1
    return n


def _a92_repair_a907() -> list:
    kf = "/key_findings[{}]"
    th = "/recomputations/h25_thermal_rerun"
    rv = "/revision_register[id={}]"
    lab = {"a9_2_label": "uncoupled sensitivity only (0 W ICP heat, v1 exterior views); the reported status is "
                         "UNRESOLVED (" + a92_src("icp_coupled_thermal") + ")"}
    return [
        R("A910-A92R-A907-01", "A9.2 icp_coupled_thermal", "a92_thermal_residual", th,
          summary="per-node nominal_closes flags of every hall_icp_neutralizer result renamed "
                  "uncoupled_sensitivity_nominal_closes (booleans unchanged)"),
        R("A910-A92R-A907-02", "A9.2 icp_coupled_thermal", "replace", kf.format(5),
          "necessary Curie checks: PI FAIL, PO PASS, BP PASS",
          "necessary Curie checks: PI FAIL, PO UNRESOLVED, BP UNRESOLVED (" + UNRES_LABEL + "; uncoupled sensitivity "
          "only: PO PASS, BP PASS)", "K6 Curie checks reported UNRESOLVED"),
        R("A910-A92R-A907-03", "A9.2 icp_coupled_thermal", "replace", kf.format(1),
          "Every hall_icp_neutralizer CLOSES is CONDITIONAL on",
          "Every hall_icp_neutralizer uncoupled-sensitivity CLOSES above (" + UNRES_LABEL + ") would in addition be "
          "CONDITIONAL on", "K2 conditional clause relabelled"),
        R("A910-A92R-A907-04", "A9.2 rf_500W", "replace", kf.format(1), "(module sized for 0-500 W forward RF, row 72)",
          "(" + DELIV_500 + ")", "K2 500 W wording"),
        R("A910-A92R-A907-05", "A9.2 icp_coupled_thermal", "replace", kf.format(2),
          "Single levers that close it in every case:",
          "Uncoupled sensitivity (" + UNRES_LABEL + "): single levers that close it in every case:", "K3 relabelled"),
        R("A910-A92R-A907-06", "A9.2 icp_coupled_thermal", "replace", kf.format(3),
          "it closes in every case only with LV-ALL", "in the uncoupled sensitivity it closes in every case only with "
          "LV-ALL", "K4 relabelled"),
        R("A910-A92R-A907-07", "A9.2 icp_coupled_thermal", "replace", kf.format(3), "so the coil closure stays OPEN",
          "so the coil closure stays OPEN (" + UNRES_LABEL + ")", "K4 status"),
        R("A910-A92R-A907-08", "A9.2 icp_coupled_thermal", "replace", kf.format(4),
          "minimal such closing sets per node:", "minimal such closing sets per node (uncoupled sensitivity; "
          + UNRES_LABEL + "):", "K5 relabelled"),
        R("A910-A92R-A907-09", "A9.2 icp_coupled_thermal", "merge", rv.format("REV-42") + "/new/value",
          {"closure_CI": "CLOSES_ONLY_WITH_COMBINED_LEVERS", "closure_CO": "CLOSES",
           "uncoupled_sensitivity_closure_CI": ABSENT, "uncoupled_sensitivity_closure_CO": ABSENT, "a9_2_label": ABSENT},
          dict({"closure_CI": UNRES, "closure_CO": UNRES,
                "uncoupled_sensitivity_closure_CI": "CLOSES_ONLY_WITH_COMBINED_LEVERS",
                "uncoupled_sensitivity_closure_CO": "CLOSES"}, **lab), "REV-42 coil closures reported UNRESOLVED"),
        R("A910-A92R-A907-10", "A9.2 icp_coupled_thermal", "merge", rv.format("REV-44") + "/new/value",
          {"PO": ["PASS"], "BP": ["PASS"], "uncoupled_sensitivity_PO": ABSENT, "uncoupled_sensitivity_BP": ABSENT,
           "a9_2_label": ABSENT},
          dict({"PO": [UNRES], "BP": [UNRES], "uncoupled_sensitivity_PO": ["PASS"], "uncoupled_sensitivity_BP": ["PASS"]},
               **lab), "REV-44 Curie checks PO / BP reported UNRESOLVED"),
        R("A910-A92R-A907-11", "A9.2 icp_coupled_thermal", "merge", rv.format("REV-45") + "/new/value",
          {"status": "CONDITIONALLY_RESOLVED", "uncoupled_sensitivity_status": ABSENT, "a9_2_label": ABSENT},
          dict({"status": UNRES, "uncoupled_sensitivity_status": "CONDITIONALLY_RESOLVED"}, **lab),
          "REV-45 BN wall reported UNRESOLVED (matches bn_wall_11_2K_case)"),
        R("A910-A92R-A907-12", "A9.2 icp_coupled_thermal", "replace", rv.format("REV-47") + "/new/requirement",
          "every hall_icp_neutralizer thermal CLOSES is evaluated with 0 W of it and holds only while",
          "every hall_icp_neutralizer thermal result is an uncoupled sensitivity evaluated with 0 W of it and "
          + UNRES_LABEL + " (the coupled terms Q_Hall->ICP, Q_collector, Q_RF/match, Q_plume and the ICP view effect are "
          "required first); an uncoupled-sensitivity closure would hold only while", "REV-47 wording"),
        R("A910-A92R-A907-13", "A9.2 icp_coupled_thermal", "replace", th + "/overall/open_items[0]",
          "a condition on every hall_icp_neutralizer CLOSES",
          "a condition on every hall_icp_neutralizer uncoupled-sensitivity closure (" + UNRES_LABEL + ")",
          "open item 1 relabelled"),
        R("A910-A92R-A907-14", "A9.2 icp_coupled_thermal", "replace", th + "/overall/open_items[1]",
          "every hall_icp_neutralizer CLOSES is evaluated with 0 W of ICP heat and holds only while",
          "every hall_icp_neutralizer thermal result is an uncoupled sensitivity evaluated with 0 W of ICP heat and "
          + UNRES_LABEL + "; an uncoupled-sensitivity closure would hold only while", "open item 2 relabelled"),
        R("A910-A92R-A907-15", "A9.2 icp_coupled_thermal", "replace", th + "/overall/open_items[4]",
          "(every CLOSES is conditional)", "(every uncoupled-sensitivity CLOSES is conditional; hall_icp_neutralizer "
          "results " + UNRES_LABEL + ")", "open item 5 relabelled"),
        R("A910-A92R-A907-16", "A9.2 icp_coupled_thermal", "replace", th + "/bn_wall_11_2K_case/status_meaning",
          "CONDITIONALLY_RESOLVED = the searched", "Uncoupled-sensitivity label (the reported status is UNRESOLVED, "
          "A9.2 ICP_COUPLED_THERMAL): CONDITIONALLY_RESOLVED = the searched", "BN-wall status meaning relabelled"),
        R("A910-A92R-A907-17", "A9.2 icp_coupled_thermal", "replace", th + "/hall_c1_reference_note",
          "zero-coupling case equals the hall_icp_neutralizer ground rows",
          "zero-coupling case equals the hall_icp_neutralizer ground rows, which are uncoupled sensitivities ("
          + UNRES_LABEL + "); a CLOSES entry in this table is a sensitivity outcome only, never a thermal PASS",
          "C1 sensitivity note relabelled"),
        R("A910-A92R-A907-18", "A9.2 icp_coupled_thermal", "replace", th + "/icp_heat_into_h1/note",
          "the thermal verdicts of hall_icp_neutralizer are evaluated with 0 W of it and are conditional on it",
          "the thermal results of hall_icp_neutralizer are uncoupled sensitivities evaluated with 0 W of it ("
          + UNRES_LABEL + ")", "ICP heat note relabelled"),
        R("A910-A92R-A907-19", "A9.2 icp_coupled_thermal", "replace", "/interface_demands[id=IDA7-07]/quantity",
          "Every hall_icp_neutralizer thermal CLOSES is conditional on the actual ICP-43 heat meeting this allowance",
          "Every hall_icp_neutralizer thermal result is an uncoupled sensitivity (" + UNRES_LABEL + "); an "
          "uncoupled-sensitivity closure would in addition be conditional on the actual ICP-43 heat meeting this "
          "allowance", "IDA7-07 wording"),
        R("A910-A92R-A907-20", "A9.2 icp_coupled_thermal", "code", None,
          summary="H2_A9_REVISIONS.md thermal section: closure-summary vocabulary, table headers, overall line, BN-wall "
                  "line and C1-sensitivity header relabelled as uncoupled sensitivity (render wrapper, each substitution "
                  "must match exactly once)",
          file="docs/hardware/h2_a9_revisions/build_h2_a9_revisions.py", marker="A92_MD_RELABEL", scope=[]),
    ]


def _a92_repair_a909() -> list:
    rf = "/packages[id=RFQ-04]/requirements[id={}]"
    def src(item):
        return {"type": "a9_2", "key": "A9.2", "id": item, "path": A92_REL, "pointer": "/decisions/" + item,
                "sha256": A92_SHA}
    out = [
        R("A910-A92R-A909-01", "A9.2 rf_500W", "supersede", rf.format("RFQ-04-R02"),
          {"title": "laboratory forward-power capability", "requirement": "Generator and inline measurement chain sized "
           "for this forward power range initially."},
          {"title": "laboratory delivered/operating RF investigation capability (generator rating "
                    "TBD_AFTER_IMPEDANCE_MAP)",
           "requirement": "The laboratory RF source and inline measurement chain provide a " + DELIV_500 + ". This "
                          "range is NOT a component rating: the " + GEN_RATING_TBD + ". This is a TEST CAPABILITY, "
                          "not a flight allocation: the flight ICP must fit inside P_ICP,available = 1350 W - P_common - "
                          "P_Hall - P_other,active at every registered condition."},
          "RFQ-04-R02: 500 W is the delivered/operating capability, generator rating TBD after the impedance map"),
        R("A910-A92R-A909-02", "A9.2 rf_500W", "merge", rf.format("RFQ-04-R02"),
          {"rating": ABSENT, "rating_freeze_point": ABSENT, "status_detail_a9_2": ABSENT},
          {"rating": RATINGS_TBD, "rating_freeze_point": "after-evidence",
           "status_detail_a9_2": "OWNER_GIVEN applies to the delivered/operating capability only (A9.2 rf_500W); "
                                 "ratings TBD_AFTER_IMPEDANCE_MAP"}, "RFQ-04-R02 rating field"),
        R("A910-A92R-A909-03", "A9.2 rf_500W", "append", rf.format("RFQ-04-R02") + "/sources", None, src("rf_500W"),
          "RFQ-04-R02 A9.2 source"),
        R("A910-A92R-A909-04", "A9.2 rf_500W", "replace", "/packages[id=RFQ-04]/scope",
          "(0-500 W forward test capability)", "(" + DELIV_500 + "; generator forward-power rating "
          "TBD_AFTER_IMPEDANCE_MAP)", "RFQ-04 scope"),
        R("A910-A92R-A909-05", "A9.2 rf_500W", "supersede", "/packages[id=RFQ-04]/quantities[0]",
          {"item": "13.56 MHz generator, 0-500 W forward"},
          {"item": "13.56 MHz generator for the " + DELIV_500 + "; forward-power rating TBD_AFTER_IMPEDANCE_MAP"},
          "RFQ-04 generator quantity line"),
        R("A910-A92R-A909-06", "A9.2 rf_500W", "replace", "/packages[id=RFQ-04]/acceptance[0]",
          "over 0-500 W forward (row 72)", "over the forward-power range of the selected generator rating "
          "(TBD_AFTER_IMPEDANCE_MAP), covering the " + DELIV_500 + " plus the characterized mismatch",
          "RFQ-04 calibration acceptance"),
        R("A910-A92R-A909-07", "A9.2 OQ-A907-11, icp_matching_strategy", "supersede", rf.format("RFQ-04-R15"),
          {"requirement": "quoted only for the case that OQ-A907-11 option a is adopted; the tunable match stays "
                          "off-platform (A9.1 A9-03-matching)",
           "note": "added in A9-10"},
          {"requirement": "SUPERSEDED_BY_A9_2 - not requested as a quotation line. The A9 baseline is the adjustable "
                          "LOCAL matching network on / immediately adjacent to the ICP module with the coupler on the "
                          "generator / 50-ohm side (A9.2 OQ-A907-11; RFQ-04-R06 / R17); a fixed on-module network is "
                          "only one possible later flight implementation, decided after the ICP impedance map (A9.2 "
                          "icp_matching_strategy). The earlier option-line text is kept as requirement_before_a9_2.",
           "note": "added in A9-10; SUPERSEDED_BY_A9_2 (history kept in requirement_before_a9_2; quotation only, no "
                   "purchase order)"}, "RFQ-04-R15 requirement / note superseded"),
        R("A910-A92R-A909-08", "A9.2 OQ-A907-11", "merge", rf.format("RFQ-04-R15") + "/sources[1]",
          {"id": "A9-03-matching", "role": ABSENT}, {"role": A91_HISTORY_ROLE}, "RFQ-04-R15 A9.1 source = history"),
        R("A910-A92R-A909-09", "A9.2 OQ-A907-11", "supersede", rf.format("RFQ-04-R06"),
          {"basis": "A9.1 clarification"},
          {"basis": "A9.2 OQ-A907-11 (supersedes the A9.1 A9-03-matching location for the A9 baseline); the three A9.1 "
                    "quotes are distinct clauses of A9-03-matching kept as history (matched sham routing still "
                    "applies, row 133)"}, "RFQ-04-R06 basis"),
    ]
    for i in range(3):
        out.append(R(f"A910-A92R-A909-1{i}", "A9.2 OQ-A907-11", "merge", rf.format("RFQ-04-R06") + f"/sources[{i}]",
                     {"id": "A9-03-matching", "role": ABSENT}, {"role": A91_HISTORY_ROLE},
                     f"RFQ-04-R06 A9.1 source {i + 1} = history"))
    out.append(R("A910-A92R-A909-13", "A9.2 rf_500W", "replace",
                 "/packages[id=RFQ-01]/requirements[id=RFQ-01-R14]/requirement", "(0-500 W source, RFQ-04)",
                 "(RF source with a " + DELIV_500 + ", RFQ-04)", "RFQ-01-R14 500 W wording"))
    return out


def _a92_repair_a903() -> list:
    it = "/items[id={}]"
    return [
        R("A910-A92R-A903-01", "A9.2 rf_500W", "supersede", it.format("ICP-12"),
          {"title": "Laboratory forward-power range (initial)",
           "requirement": "cover 0-500 W forward power initially (row 72). This is a laboratory capability range"},
          {"title": "Laboratory delivered/operating RF investigation capability (initial; ratings TBD_AFTER_IMPEDANCE_MAP)",
           "requirement": "The laboratory RF source and the inline measurement chain provide a " + DELIV_500 + "; the "
                          + GEN_RATING_TBD + ". This is a laboratory capability range, not a power allocation: the ICP "
                          "bus power must fit inside the internal ~1.35 kW design allocation without consuming the 1.35 "
                          "-> 1.5 kW margin (row 109), and the full-system gate is P_bus < 1.5 kW at the spacecraft-DC "
                          "boundary incl. start-up transients (row 108)."},
          "ICP-12 requirement consistent with its A9.2 interpretation"),
        R("A910-A92R-A903-02", "A9.2 rf_500W", "replace", it.format("ICP-36") + "/requirement",
          "the full laboratory forward power (row 72)", "the full laboratory RF capability of row 72 (500 W, a "
          "delivered/operating investigation capability per A9.2 rf_500W, not a component rating; used here only as a "
          "heat-allocation term)", "ICP-36 wording"),
        R("A910-A92R-A903-03", "A9.2 rf_500W", "replace", it.format("ICP-36") + "/basis", "500 W (row 72)",
          "500 W (row 72; A9.2: delivered/operating capability, not a component rating)", "ICP-36 basis"),
        R("A910-A92R-A903-04", "A9.2 rf_500W, icp_matching_strategy", "supersede", it.format("ICP-44"),
          {"requirement": "computed at P_fwd,max = 500 W", "verification": "RF hipot at full forward power (500 W)",
           "tbd": "TBD - requires the antenna/matching-network selection"},
          {"requirement": "The antenna circuit (antenna, local matching-network output, RF feedthrough and in-vacuum "
                          "leads) is rated separately from the 350 V DC discharge-circuit item (ICP-23). A 13.56 MHz ICP "
                          "antenna can run at an RF voltage far above the DC discharge rating. The rating is k_RF x "
                          "V_ant,peak, where V_ant,peak is computed at the maximum operating point of the characterized "
                          "mismatch envelope (ICP antenna impedance map Z_antenna = R + jX, A9.2 P2; "
                          "TBD_AFTER_IMPEDANCE_MAP) that delivers the " + DELIV_500 + ", from the selected antenna / "
                          "local matching design and the MEASURED total circuit resistance R_total (antenna + plasma "
                          "load; the analog infers its power-transfer efficiency from such measured resistances, annex "
                          "TAK-12); the factor k_RF (> 1) is an owner/LOCK-1 value (ICPQ-11). Clearance/creepage and "
                          "in-vacuum Paschen margins are set for the combined stress between antenna and collector/body: "
                          "the collector/body DC potential relative to the antenna circuit reference (up to the ICP-23 "
                          "DC rating) plus V_ant,peak.",
           "verification": "RF hipot at the rated operating point of the characterized mismatch envelope "
                           "(TBD_AFTER_IMPEDANCE_MAP; covering the " + DELIV_500 + ") on a dummy load and with plasma; RF "
                           "probe of V_ant,peak; inspection of clearance/creepage",
           "tbd": "TBD - requires the ICP antenna impedance map (A9.2 P2), the local-match selection (ICP-13, ICP-15), the "
                  "measured R_total and the owner factor k_RF (" + RATINGS_TBD + ")"},
          "ICP-44 rating basis on the impedance map"),
        R("A910-A92R-A903-05", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/how_applied",
          "0-500 W lab forward power", "0-500 W lab RF capability (A9.2 rf_500W: delivered/operating investigation "
          "capability, not a component rating)", "row 72 application"),
        R("A910-A92R-A903-06", "A9.2 rf_500W, icp_matching_strategy", "replace",
          "/open_owner_questions[id=ICPQ-10]/proposed_answer", "(0-500 W) is a capability",
          "(0-500 W; A9.2: a delivered/operating investigation capability, not a component rating) is a capability",
          "ICPQ-10 proposal wording (proposal itself unchanged)"),
        R("A910-A92R-A903-07", "A9.2 rf_500W, icp_matching_strategy", "merge", "/open_owner_questions[id=ICPQ-10]",
          {"a9_2_affected": ABSENT, "needed_by": ABSENT},
          {"a9_2_affected": "A9.2 rf_500W / icp_matching_strategy: P_fwd,max is no longer 500 W (0-500 W is the "
                            "delivered/operating capability; forward-power ratings TBD_AFTER_IMPEDANCE_MAP) and the local "
                            "match loss P_line/match,loss is dissipated on the module (ICP-36 a9_2_note); the question "
                            "stays OPEN (owner call)",
           "needed_by": "LOCK-1 (PROPOSED; after the ICP antenna impedance map, A9.2 P2, which sets P_fwd,max)"},
          "ICPQ-10 marked A9.2-affected"),
        R("A910-A92R-A903-08", "A9.2 rf_500W, icp_matching_strategy", "supersede", "/open_owner_questions[id=ICPQ-11]",
          {"question": "computed V_ant,peak at 500 W (ICP-44)?"},
          {"question": "Factor k_RF between the rated antenna-circuit RF voltage and the V_ant,peak computed at the "
                       "maximum operating point of the characterized mismatch envelope (ICP antenna impedance map, A9.2 "
                       "P2; not at a 500 W component rating) (ICP-44)?"}, "ICPQ-11 re-framed on the impedance-map basis"),
        R("A910-A92R-A903-09", "A9.2 rf_500W, icp_matching_strategy", "merge", "/open_owner_questions[id=ICPQ-11]",
          {"a9_2_affected": ABSENT, "needed_by": ABSENT},
          {"a9_2_affected": "A9.2 rf_500W / icp_matching_strategy: V_ant,peak is computed on the impedance-map envelope, "
                            "not at 500 W forward; the question stays OPEN (owner call, no value proposed)",
           "needed_by": "LOCK-1 (PROPOSED; after the ICP antenna impedance map, A9.2 P2)"},
          "ICPQ-11 marked A9.2-affected"),
        R("A910-A92R-A903-10", "A9.2 rf_500W", "supersede", "/h3_h4_inputs/h3_procurement_quotation_only[0]",
          {"item": "13.56 MHz RF generator, 0-500 W forward"},
          {"item": "13.56 MHz RF generator for the " + DELIV_500 + " (forward-power rating TBD_AFTER_IMPEDANCE_MAP), "
                   "interlock input, remote fwd/refl readout"}, "h3 generator line"),
    ]


def _a92_repair_a904() -> list:
    it = "/items[id={}]"
    return [
        R("A910-A92R-A904-01", "A9.2 rf_500W", "supersede", it.format("UB-RF-01"),
          {"name": "laboratory forward-power range of the RF source and inline chain"},
          {"name": "laboratory delivered/operating RF investigation capability of the RF source and inline chain "
                   "(row 72 as interpreted by A9.2 rf_500W; not a component rating)"},
          "UB-RF-01 relabelled (value unchanged)"),
        R("A910-A92R-A904-02", "A9.2 rf_500W", "merge", it.format("UB-RF-01"),
          {"a9_2_interpretation": ABSENT, "rating": ABSENT, "status_detail_a9_2": ABSENT},
          {"a9_2_interpretation": "0-500 W is a laboratory delivered/operating investigation capability, not a component "
                                  "rating (" + a92_src("rf_500W") + "); P_forward != P_delivered",
           "rating": RATINGS_TBD,
           "status_detail_a9_2": "OWNER_GIVEN applies to the delivered/operating capability only (A9.2 rf_500W); "
                                 "forward-power ratings TBD_AFTER_IMPEDANCE_MAP"}, "UB-RF-01 A9.2 interpretation"),
        R("A910-A92R-A904-03", "A9.2 rf_500W", "replace", it.format("UB-RF-03") + "/name", "over 0-500 W",
          "over the forward-power range of the selected generator rating (TBD_AFTER_IMPEDANCE_MAP; covering the "
          + DELIV_500 + ")", "UB-RF-03 range wording"),
        R("A910-A92R-A904-04", "A9.2 rf_500W", "replace", "/stop_rules/limit_aborts/limits[id=LA-02]/value",
          "ratings inside the 0-500 W laboratory chain (row 72)", "ratings (TBD_AFTER_IMPEDANCE_MAP, A9.2) of the "
          "laboratory chain with its " + DELIV_500, "LA-02 wording"),
        R("A910-A92R-A904-05", "A9.2 rf_500W", "replace", "/interface_demands[id=IF-14]/quantity",
          "forward/reflected sensors 0-500 W (row 72)", "forward/reflected sensors for the " + DELIV_500 + ", ratings "
          "TBD_AFTER_IMPEDANCE_MAP", "IF-14 wording"),
        R("A910-A92R-A904-06", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/how_applied",
          "0-500 W lab chain", "0-500 W lab chain (A9.2 rf_500W: delivered/operating investigation capability, not a "
          "component rating)", "row 72 application"),
        R("A910-A92R-A904-07", "A9.2 rf_500W", "replace", "/h3_procurement_inputs[1]/spec_form",
          "0-500 W forward (row 72)", "forward-power range of the selected generator rating (TBD_AFTER_IMPEDANCE_MAP) "
          "covering the " + DELIV_500, "h3 coupler spec form"),
    ]


def _a92_repair_a902() -> list:
    return [
        R("A910-A92R-A902-01", "A9.2 rf_measurement_reference", "code", None,
          summary="rf_power_planes() also returns |Gamma| and VSWR (derived from the measured forward / reflected power) "
                  "and labels the coupler plane as the generator / 50-ohm side of the local match; arithmetic and "
                  "ordering checks unchanged",
          file="abep_sim/bus_boundary_a9.py", marker="generator / 50-ohm side of the local matching network (A9.2",
          scope=[]),
    ]


def _a92_repair() -> dict:
    return {"A9-02": _a92_repair_a902(), "A9-03": _a92_repair_a903(), "A9-04": _a92_repair_a904(),
            "A9-07": _a92_repair_a907(), "A9-09": _a92_repair_a909()}


# ------------------------------------------------------------------------------------------------------ A9.2 repair 2
# A9-10 review repair 4 (A9.2 residual wording, all deliverables): repair 3 relabelled the A9-03 / A9-04 / A9-09 RF
# texts, but key finding K11, A9H-INS-01, REV-34 / REV-35 / REV-60 (A9-07), the A9-01 / A9-02 / A9-05 / A9-06 H3
# inputs and owner-row summaries still sized or rated the RF chain at 0-500 W FORWARD, and REV-34 still carried the
# superseded A9.1 off-platform layout as its current requirement. The uncoupled-sensitivity thermal values of
# hall_icp_neutralizer still used the PASS / CLOSES vocabulary. Every record below is a wording / label change required
# by A9.2 (rf_500W, rf_measurement_reference, OQ-A907-11, icp_coupled_thermal). No number changes: the 0-500 W row-72
# figure is kept as the delivered/operating capability; superseded texts are kept as *_before_a9_2 (history).
SENS_VOCAB = {
    "CLOSES": "UNCOUPLED_SENSITIVITY_WITHIN_LIMIT",
    "CLOSES_WITH_SINGLE_LEVER": "UNCOUPLED_SENSITIVITY_WITHIN_LIMIT_WITH_SINGLE_LEVER",
    "CLOSES_ONLY_WITH_COMBINED_LEVERS": "UNCOUPLED_SENSITIVITY_WITHIN_LIMIT_ONLY_WITH_COMBINED_LEVERS",
    "CLOSES_WITH_LEVERS": "UNCOUPLED_SENSITIVITY_WITHIN_LIMIT_WITH_LEVERS",
    "PASS": "UNCOUPLED_SENSITIVITY_BELOW_CEILING",
    "CONDITIONALLY_RESOLVED": "UNCOUPLED_SENSITIVITY_CONDITIONALLY_WITHIN_LIMIT",
}
SENS_VOCAB_RULE = ("A9.2 ICP_COUPLED_THERMAL (A9-10 review repair 4): the lane's rule vocabulary (CLOSES / PASS / "
                   "CONDITIONALLY_RESOLVED, recomputations.h25_thermal_rerun.rule) is recorded for hall_icp_neutralizer "
                   "only as uncoupled-sensitivity outcomes with the names below; they are sensitivity information, never "
                   "a thermal PASS or closure; every reported hall_icp_neutralizer thermal status is UNRESOLVED")
PLANE_A92 = ("on the generator / 50-ohm side of the LOCAL matching network (ICP-14 plane; A9.2 OQ-A907-11 / "
             "rf_measurement_reference)")
FWD_MAX_TBD = ("P_RF,fwd,max (TBD_AFTER_IMPEDANCE_MAP: the forward power on the generator / 50-ohm side at the maximum "
               "operating point of the characterized mismatch envelope; the row-72 0-500 W figure is the delivered/"
               "operating investigation capability, not a forward maximum and not a component rating - A9.2 rf_500W; "
               "A9.2 cites about 925 W forward at VSWR about 5.2 for 500 W delivered)")
LBL_500 = "(A9.2 rf_500W: delivered/operating investigation capability, not a component rating)"


def _sens_map(v):
    if isinstance(v, str):
        if v in SENS_VOCAB:
            return SENS_VOCAB[v], 1
        if PASS_LIKE.match(v):
            raise OverlayError(f"no uncoupled-sensitivity name for {v!r}")
        return v, 0
    if isinstance(v, list):
        out, n = [], 0
        for x in v:
            y, k = _sens_map(x)
            out.append(y)
            n += k
        return out, n
    return v, 0


def _a92_sens_vocab(th: dict) -> int:
    """Rename the pass-like values of every uncoupled_sensitivity_* field (and the uncoupled-sensitivity mount-heat
    table) of the hall_icp_neutralizer thermal records to the SENS_VOCAB names. Returns the number of renamed fields."""
    n = 0

    def walk(o):
        nonlocal n
        if isinstance(o, dict):
            for k in list(o):
                v = o[k]
                if k.startswith("uncoupled_sensitivity_") and not isinstance(v, (dict, bool)):
                    o[k], c = _sens_map(v)
                    n += 1 if c else 0
                elif k == "within_allowable_W_uncoupled_sensitivity":
                    new = {}
                    for a, x in v.items():
                        new[a], c = _sens_map(x)
                        n += c
                    o[k] = new
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    for key in ("results", "closure_summary_hall_icp_neutralizer", "bn_wall_11_2K_case", "mount_heat_vs_row85"):
        node = th[key]["hall_icp_neutralizer"] if key == "results" else th[key]
        walk(node)
    if "a9_2_sensitivity_vocabulary" in th:
        raise OverlayError("sensitivity vocabulary already renamed")
    th["a9_2_sensitivity_vocabulary"] = {"rule": SENS_VOCAB_RULE, "names": dict(SENS_VOCAB),
                                         "source": a92_src("icp_coupled_thermal")}
    return n


def _a92_repair2_a907() -> list:
    kf = "/key_findings[{}]"
    th = "/recomputations/h25_thermal_rerun"
    rv = "/revision_register[id={}]"
    a92drv = lambda i: {"kind": "A9.2", "id": i, "path": A92_REL, "sha256": A92_SHA}  # noqa: E731
    return [
        R("A910-A92S-A907-01", "A9.2 icp_coupled_thermal", "a92_sens_vocab", th,
          summary="uncoupled_sensitivity_* values of every hall_icp_neutralizer thermal record renamed from the "
                  "CLOSES / PASS / CONDITIONALLY_RESOLVED vocabulary to UNCOUPLED_SENSITIVITY_* names (a9_2_sensitivity_"
                  "vocabulary; values' meaning and every number unchanged)"),
        R("A910-A92S-A907-02", "A9.2 icp_coupled_thermal", "merge", rv.format("REV-42") + "/new/value",
          {"uncoupled_sensitivity_closure_CI": "CLOSES_ONLY_WITH_COMBINED_LEVERS",
           "uncoupled_sensitivity_closure_CO": "CLOSES"},
          {"uncoupled_sensitivity_closure_CI": SENS_VOCAB["CLOSES_ONLY_WITH_COMBINED_LEVERS"],
           "uncoupled_sensitivity_closure_CO": SENS_VOCAB["CLOSES"]}, "REV-42 sensitivity names"),
        R("A910-A92S-A907-03", "A9.2 icp_coupled_thermal", "merge", rv.format("REV-44") + "/new/value",
          {"uncoupled_sensitivity_PO": ["PASS"], "uncoupled_sensitivity_BP": ["PASS"]},
          {"uncoupled_sensitivity_PO": [SENS_VOCAB["PASS"]], "uncoupled_sensitivity_BP": [SENS_VOCAB["PASS"]]},
          "REV-44 sensitivity names"),
        R("A910-A92S-A907-04", "A9.2 icp_coupled_thermal", "merge", rv.format("REV-45") + "/new/value",
          {"uncoupled_sensitivity_status": "CONDITIONALLY_RESOLVED"},
          {"uncoupled_sensitivity_status": SENS_VOCAB["CONDITIONALLY_RESOLVED"]}, "REV-45 sensitivity name"),
        R("A910-A92S-A907-05", "A9.2 icp_coupled_thermal", "replace", th + "/bn_wall_11_2K_case/status_meaning",
          "CONDITIONALLY_RESOLVED = the searched", SENS_VOCAB["CONDITIONALLY_RESOLVED"] + " = the searched",
          "BN-wall status meaning uses the sensitivity name"),
        R("A910-A92S-A907-06", "A9.2 icp_coupled_thermal", "replace", kf.format(1),
          "WI DO_NOT_CLOSE, WO CLOSES, CI DO_NOT_CLOSE, CO CLOSES.",
          "WI DO_NOT_CLOSE, WO UNCOUPLED_SENSITIVITY_WITHIN_LIMIT (uncoupled-sensitivity margin positive), CI "
          "DO_NOT_CLOSE, CO UNCOUPLED_SENSITIVITY_WITHIN_LIMIT (uncoupled-sensitivity margin positive).",
          "K2 node verdicts use the sensitivity names"),
        R("A910-A92S-A907-07", "A9.2 icp_coupled_thermal", "replace", kf.format(1),
          "Every hall_icp_neutralizer uncoupled-sensitivity CLOSES above",
          "Every hall_icp_neutralizer uncoupled-sensitivity within-limit result above", "K2 clause"),
        R("A910-A92S-A907-08", "A9.2 icp_coupled_thermal", "replace", kf.format(2),
          "uncoupled sensitivity: CONDITIONALLY_RESOLVED)",
          "uncoupled sensitivity: " + SENS_VOCAB["CONDITIONALLY_RESOLVED"] + ")", "K3 sensitivity name"),
        R("A910-A92S-A907-09", "A9.2 icp_coupled_thermal", "replace", kf.format(5),
          "uncoupled sensitivity only: PO PASS, BP PASS",
          "uncoupled sensitivity only: PO and BP below the necessary Curie ceiling, " + SENS_VOCAB["PASS"],
          "K6 Curie sensitivity wording"),
        R("A910-A92S-A907-10", "A9.2 icp_coupled_thermal", "replace", "/m16_impact[m16_row=10]/how_touched",
          "uncoupled sensitivity CLOSES_ONLY_WITH_COMBINED_LEVERS / CLOSES",
          "uncoupled sensitivity CI " + SENS_VOCAB["CLOSES_ONLY_WITH_COMBINED_LEVERS"] + " / CO " + SENS_VOCAB["CLOSES"],
          "M16 row 10 wording"),
        R("A910-A92S-A907-11", "A9.2 icp_coupled_thermal", "replace", "/m16_impact[m16_row=13]/how_touched",
          "BN wall uncoupled sensitivity CLOSES_WITH_SINGLE_LEVER",
          "BN wall uncoupled sensitivity " + SENS_VOCAB["CLOSES_WITH_SINGLE_LEVER"], "M16 row 13 wording"),
        R("A910-A92S-A907-12", "A9.2 rf_500W, OQ-A907-11", "replace", kf.format(10),
          "the row-72 0-500 W range is the GENERATOR forward power; at the A9.1 coupler plane (after the match) the "
          "forward power is P_net / (1 - |Gamma|^2) and depends on the antenna impedance, which is TBD.",
          "A9.2 (rf_500W, OQ-A907-11 answered): the row-72 0-500 W range is a laboratory delivered/operating "
          "investigation capability, NOT the generator forward power and not a component rating; the directional "
          "coupler sits on the generator / 50-ohm side of the LOCAL matching network and every RF component rating is "
          "TBD_AFTER_IMPEDANCE_MAP. History (A9-07 analysis on the superseded A9.1 plane, coupler after an off-platform "
          "match; kept for provenance): at that plane the forward power was P_net / (1 - |Gamma|^2) and depended on "
          "the antenna impedance, which is TBD.", "K11 opens with the A9.2 interpretation"),
        R("A910-A92S-A907-13", "A9.2 rf_500W, OQ-A907-11", "replace", kf.format(10),
          "Coupler/sensor/coax ratings and the directivity requirement are therefore TBD until either an on-module "
          "pre-match fixes Gamma_max (option a, proposed) or the antenna impedance range is known (option b).",
          "Coupler/sensor/coax ratings and the directivity requirement were therefore TBD until either an on-module "
          "pre-match fixed Gamma_max (option a, then proposed) or the antenna impedance range was known (option b); "
          "both options are superseded by A9.2 (adjustable local match; ratings TBD_AFTER_IMPEDANCE_MAP).",
          "K11 history clause"),
        R("A910-A92S-A907-14", "A9.2 rf_500W", "replace", kf.format(10),
          "At the review's illustrative loads (not antenna data) and 500 W net:",
          "At the review's illustrative loads (not antenna data) and 500 W net (the delivered/operating capability; "
          "sensitivity only, not a rating):", "K11 sensitivity sentence labelled"),
        R("A910-A92S-A907-15", "A9.2 OQ-A907-11, rf_measurement_reference, rf_500W", "supersede", rv.format("REV-34")
          + "/new",
          {"requirement": "matching network OFF the moving platform", "value": "off-platform tunable match"},
          {"requirement": "A9.2 OQ-A907-11 (supersedes the A9.1 A9-03-matching location for the A9 baseline): "
                          + LOCAL_CHAIN + "; the long flexible coax across the stand stays approximately a controlled "
                          "50-ohm line; " + MEAS_REF + "; calibrated line-loss / S-parameter correction from the coupler "
                          "plane to the local-match input; matched sham coax and an equivalent sham network in "
                          "hall_c1_reference (row 133); RF component ratings TBD_AFTER_IMPEDANCE_MAP (A9.2 rf_500W); "
                          "protection per A9.2 rf_protection, trip thresholds frozen after the ICP load "
                          "characterization. The A9.1 text (match off the moving platform, coupler after the match) is "
                          "kept as requirement_before_a9_2 (history, superseded).",
           "value": {"layout": "LOCAL adjustable matching network on / immediately adjacent to the ICP module; "
                               "directional coupler on the generator / 50-ohm side (A9.2 OQ-A907-11)",
                     "flexible_segment_treatment": "controlled 50-ohm line; the antenna mismatch is confined to the "
                                                   "short match-to-antenna segment and the matching elements (A9.2); "
                                                   "ratings TBD_AFTER_IMPEDANCE_MAP"}},
          "REV-34 current requirement = the A9.2 local-match layout; A9.1 layout kept as history"),
        R("A910-A92S-A907-16", "A9.2 OQ-A907-11", "supersede", rv.format("REV-34"),
          {"basis": "A9.1 A9-03 clarification"},
          {"basis": "A9.2 OQ-A907-11 / rf_measurement_reference / rf_500W (supersede the A9.1 A9-03-matching location "
                    "for the A9 baseline; OWNER_GIVEN by A9.2)"}, "REV-34 basis"),
        R("A910-A92S-A907-17", "A9.2 OQ-A907-11", "append", rv.format("REV-34") + "/driver", None,
          a92drv("OQ-A907-11"), "REV-34 A9.2 driver"),
        R("A910-A92S-A907-18", "A9.2 rf_500W", "replace", rv.format("REV-35") + "/new/requirement",
          "P_RF,fwd,max 500 W", FWD_MAX_TBD, "REV-35 forward maximum is TBD_AFTER_IMPEDANCE_MAP, not 500 W"),
        R("A910-A92S-A907-19", "A9.2 rf_500W", "append", rv.format("REV-35") + "/driver", None, a92drv("rf_500W"),
          "REV-35 A9.2 driver"),
        R("A910-A92S-A907-20", "A9.2 rf_500W", "replace", rv.format("REV-60") + "/new/requirement",
          "the 0-500 W lab RF source is a test capability only",
          "the lab RF source (0-500 W delivered/operating investigation capability, A9.2 rf_500W; not a component "
          "rating) is a test capability only", "REV-60 500 W label"),
        R("A910-A92S-A907-21", "A9.2 rf_500W, rf_measurement_reference", "supersede", "/new_items[id=A9H-INS-01]",
          {"name": "reference plane after the matching network (A9.1)", "value": "generator_P_fwd_W",
           "basis": "row 72; A9.1 A9-03-matching"},
          {"name": "13.56 MHz directional coupler + forward/reflected power sensors " + PLANE_A92 + "; laboratory chain "
                   "with the " + DELIV_500,
           "value": {"f_MHz": 13.56, "delivered_operating_capability_W": [0.0, 500.0],
                     "generator_and_coupler_ratings": RATINGS_TBD,
                     "coupler_plane_P_fwd_max_W": RATINGS_TBD,
                     "directivity_min_dB": "TBD - requires the A9-04 u(P_net) allocation at the coupler-plane |Gamma| "
                                           "(UB-RF-04)"},
           "basis": "row 72 as interpreted by A9.2 rf_500W; A9.2 OQ-A907-11 / rf_measurement_reference (the A9.1 "
                    "A9-03-matching plane is history)"},
          "A9H-INS-01 name / value: coupler plane per A9.2; 0-500 W kept as the delivered/operating capability "
          "(number unchanged, owner row 72)", numeric=True),
        R("A910-A92S-A907-22", "A9.2 OQ-A907-11", "replace", "/new_items[id=A9H-INS-14]/note",
          "the tunable match stays off-platform (A9.1);",
          "history (A9.1, superseded for the A9 baseline by A9.2 OQ-A907-11: adjustable local match on / adjacent to "
          "the ICP module): the tunable match stayed off-platform;", "A9H-INS-14 note marked history"),
        R("A910-A92S-A907-23", "A9.2 rf_500W", "replace", "/h3_inputs[id=H3-A907-02]/item",
          "13.56 MHz RF generator 0-500 W +", "13.56 MHz RF generator for the " + DELIV_500 + " +",
          "H3-A907-02 500 W label"),
        R("A910-A92S-A907-24", "A9.2 rf_500W", "supersede", "/recomputations/rf_reference_plane/P_net_max_W",
          {"basis": "row 72 lab forward power 0-500 W"},
          {"basis": "row 72 0-500 W as interpreted by A9.2 rf_500W: the delivered/operating investigation capability; "
                    "P_net = 500 W is the delivered power of the sensitivity cases (A9.2 cites about 925 W forward at "
                    "VSWR about 5.2 for this 500 W delivered case); not a component rating"},
          "P_net_max basis relabelled (value unchanged)"),
        R("A910-A92S-A907-25", "A9.2 rf_500W", "replace",
          "/recomputations/rf_reference_plane/options/b_rate_the_mismatched_segment/note",
          "for 500 W net: a 0-500 W forward-rated sensor would be over-ranged",
          "for 500 W net (the delivered/operating capability): a sensor rated at 500 W would be over-ranged (A9.2 "
          "rf_500W: 500 W is not a component rating; ratings TBD_AFTER_IMPEDANCE_MAP)", "option-b note labelled"),
        R("A910-A92S-A907-27", "A9.2 icp_coupled_thermal", "replace", th + "/overall/open_items[4]",
          "(every uncoupled-sensitivity CLOSES is conditional;", "(every uncoupled-sensitivity within-limit result is "
          "conditional;", "open item 5 wording"),
        R("A910-A92S-A907-28", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/how_applied",
          "13.56 MHz, 0-500 W generator/chain;", "13.56 MHz, 0-500 W generator/chain " + LBL_500 + ";",
          "row 72 application labelled"),
        R("A910-A92S-A907-26", "A9.2 icp_coupled_thermal", "code", None,
          summary="H2_A9_REVISIONS.md closure-summary vocabulary sentence rewritten with the UNCOUPLED_SENSITIVITY_* "
                  "names (render wrapper A92_MD_RELABEL, each substitution matched exactly once); the register "
                  "renderer shows A9.2 drivers",
          file="docs/hardware/h2_a9_revisions/build_h2_a9_revisions.py", marker="A92_SENS_VOCAB_MD", scope=[]),
    ]


def _a92_repair2_a901() -> list:
    return [
        R("A910-A92S-A901-01", "A9.2 rf_500W, rf_measurement_reference", "replace", "/stage_map[id=HI-S1A]/what",
          "RF chain 13.56 MHz, 0-500 W forward, directional-coupler forward/reflected into a dummy load",
          "RF chain 13.56 MHz with the " + DELIV_500 + " (ratings TBD_AFTER_IMPEDANCE_MAP), directional-coupler "
          "forward/reflected " + PLANE_A92 + " into a dummy load", "HI-S1A RF chain wording"),
        R("A910-A92S-A901-02", "A9.2 rf_500W, rf_measurement_reference", "set",
          "/configurations/configurations[1]/configuration_defining_settings[0]",
          "RF forward power (laboratory 0-500 W range, row 72) and matching state",
          "RF forward / reflected / delivered power (P_forward, P_reflected, |Gamma|, VSWR, P_delivered; A9.2 "
          "rf_measurement_reference; the laboratory 0-500 W range is a delivered/operating investigation capability, "
          "row 72 as interpreted by A9.2 rf_500W) and the local matching-network state", "MOD-ICP setting wording"),
        R("A910-A92S-A901-03", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/applied_as",
          "13.56 MHz, 0-500 W,", "13.56 MHz, 0-500 W " + LBL_500 + ",", "row 72 application labelled"),
        R("A910-A92S-A901-04", "A9.2 rf_500W, OQ-A907-11", "set", "/h3_h4_inputs/h3_procurement_inputs_quotations_only[0]",
          "13.56 MHz RF generator sized for 0-500 W forward, matching network, directional coupler, RF feedthroughs, "
          "ICP chamber components (rows 8, 72)",
          "13.56 MHz RF generator for the " + DELIV_500 + " (generator, coupler, coax, connector, matching-element and "
          "feedthrough ratings TBD_AFTER_IMPEDANCE_MAP), adjustable LOCAL matching network on / immediately adjacent to "
          "the ICP module, directional coupler on its generator / 50-ohm side, RF feedthroughs, ICP chamber components "
          "(rows 8, 72; A9.2 rf_500W / OQ-A907-11)", "H3 RF line: no 500 W rating"),
    ]


def _a92_repair2_a902() -> list:
    return [
        R("A910-A92S-A902-01", "A9.2 rf_500W", "supersede", "/h3_inputs[id=H3-A902-01]",
          {"item": "13.56 MHz laboratory RF generator, 0-500 W forward"},
          {"item": "13.56 MHz laboratory RF generator for the " + DELIV_500 + "; forward-power rating "
                   "TBD_AFTER_IMPEDANCE_MAP; DC input metered"}, "H3-A902-01 no 500 W rating"),
        R("A910-A92S-A902-02", "A9.2 rf_500W", "replace", "/h4_inputs[id=H4-A902-01]/measure",
          "into a dummy load over 0-500 W;", "into a dummy load over the " + DELIV_500 + " plus the characterized "
          "mismatch (generator rating TBD_AFTER_IMPEDANCE_MAP);", "H4-A902-01 wording"),
        R("A910-A92S-A902-03", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/how_applied",
          "lab 0-500 W forward;", "lab 0-500 W " + LBL_500 + ";", "row 72 application labelled"),
        R("A910-A92S-A902-04", "A9.2 rf_500W", "replace", "/items[id=A902-20]/note",
          "the laboratory 0-500 W RF source is a test capability",
          "the laboratory RF source (" + DELIV_500 + ") is a test capability", "A902-20 note labelled"),
        R("A910-A92S-A902-05", "A9.2 rf_500W", "code", None,
          summary="BUS_POWER_BOUNDARY_A9.md ICP-available-power line: the 0-500 W laboratory RF range labelled as the "
                  "delivered/operating capability (builder literal)",
          file="docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py",
          marker="A92_W500_LABEL", scope=[]),
    ]


def _a92_repair2_a903() -> list:
    it = "/items[id={}]"
    return [
        R("A910-A92S-A903-01", "A9.2 rf_500W, rf_measurement_reference", "supersede", it.format("ICP-36"),
          {"status": "DERIVED_BOUND", "evidence_class": "bound on owner values"},
          {"status": "DERIVED_ALLOCATION_TERM",
           "evidence_class": "model-derived (allocation term on owner values; not a bound, not a component rating)"},
          "ICP-36 status names an allocation term, not a bound (value 600 W unchanged)"),
        R("A910-A92S-A903-02", "A9.2 rf_measurement_reference, rf_500W", "replace", it.format("ICP-36") + "/requirement",
          "It covers RF power delivered past the directional coupler only;",
          "Reference plane of the 500 W delivered/operating figure: the delivered plane past the local matching network (P_delivered = "
          "P_forward - P_reflected - P_line/match,loss, A9.2 rf_measurement_reference). The heat downstream of the "
          "directional coupler is P_forward - P_reflected = P_delivered + P_line/match,loss, so the local-match / line "
          "loss dissipated on the module (TBD_AFTER_IMPEDANCE_MAP) is ADDITIONAL to the 500 W delivered figure: it consumes part "
          "of the 20 % margin or exceeds it, and it is carried as Q_RF/match in ICP-43;",
          "ICP-36 reference plane stated; match loss additional"),
        R("A910-A92S-A903-03", "A9.2 rf_500W", "replace", it.format("ICP-43") + "/requirement",
          "Q_RF is bounded by ICP-36,", "Q_RF is the ICP-36 RF-only allocation term (not a bound) plus the local-match / "
          "line loss P_line/match,loss dissipated on the module (A9.2 rf_measurement_reference),",
          "ICP-43 Q_RF wording"),
        R("A910-A92S-A903-04", "A9.2 rf_500W", "replace", it.format("ICP-43") + "/requirement",
          "x (P_fwd,max (row 72) + P_d,max)", "x (P_fwd,max + P_d,max) with P_fwd,max = the forward power on the "
          "generator / 50-ohm side at the maximum operating point of the characterized mismatch envelope "
          "(TBD_AFTER_IMPEDANCE_MAP; not the row-72 0-500 W figure, which is a delivered/operating investigation "
          "capability and not a component rating, A9.2 rf_500W)", "ICP-43 rule: P_fwd,max is not 500 W"),
        R("A910-A92S-A903-05", "A9.2 rf_measurement_reference", "supersede",
          "/h3_h4_inputs/h3_procurement_quotation_only[2]", {"item": "at the load plane"},
          {"item": "calibrated dual directional coupler + power sensors " + PLANE_A92 + "; ratings "
                   "TBD_AFTER_IMPEDANCE_MAP"}, "H3 coupler line: A9.2 plane"),
        R("A910-A92S-A903-06", "A9.2 icp_coupled_thermal", "set", "/h3_h4_inputs/h4_tests[5]/closes",
          "ICP-21, ICP-29, ICP-36, ICP-43 (engineering evidence only)",
          "ICP-21, ICP-29 (engineering evidence only); ICP-36 / ICP-43: engineering heat-map input only, NOT a thermal "
          "closure (A9.2 ICP_COUPLED_THERMAL = UNRESOLVED: a coupled closure needs Q_Hall->ICP, Q_collector, "
          "Q_RF/match, Q_plume and the ICP view factors)", "Ar thermal map re-scoped: no ICP-43 closure"),
        R("A910-A92S-A903-07", "A9.2 rf_measurement_reference", "replace", "/h3_h4_inputs/h4_tests[1]/measure",
          "load-plane loss chain", "loss chain from the coupler plane (generator / 50-ohm side) through the line and "
          "the local match to the antenna feed (A9.2)", "S1a loss-chain wording"),
    ]


def _a92_repair2_a905ev() -> list:
    return [
        R("A910-A92S-A905EV-01", "A9.2 rf_500W", "set", "/h3_h4_inputs/h3_procurement_rfq[0]",
          "13.56 MHz generator with forward/reflected metering (anchor: 200 W class; owner row 72: size 0-500 W)",
          "13.56 MHz generator with forward/reflected metering (anchor: 200 W class; owner row 72 as interpreted by "
          "A9.2 rf_500W: " + DELIV_500 + "; generator rating TBD_AFTER_IMPEDANCE_MAP)", "H3 generator line"),
        R("A910-A92S-A905EV-02", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/how",
          "for the 0-500 W lab chain", "for the lab chain with its " + DELIV_500, "row 72 application labelled"),
    ]


def _a92_repair2_a905vi() -> list:
    it = "/items[id={}]"
    h3 = "/h3_h4_inputs/h3_procurement_rfq_inputs[{}]"
    old = ["13.56 MHz RF generator, 0-500 W forward with forward/reflected metering (row 72)",
           "matching network with remote tuning; RF vacuum feedthrough; flexible coax + matched sham (rows 8, 117)",
           "inline directional coupler + power sensors at the load plane; RF current probe for the antenna"]
    new = ["13.56 MHz RF generator for the " + DELIV_500 + " with forward/reflected metering (row 72; generator "
           "forward-power rating TBD_AFTER_IMPEDANCE_MAP)",
           "adjustable LOCAL matching network on / immediately adjacent to the ICP module (A9.2 OQ-A907-11; "
           "matching-element ratings TBD_AFTER_IMPEDANCE_MAP); RF vacuum feedthrough; flexible 50-ohm coax + matched "
           "sham (rows 8, 117, 133)",
           "inline directional coupler + power sensors " + PLANE_A92 + " (P_forward, P_reflected, |Gamma|, VSWR, "
           "P_delivered); RF current probe for the antenna"]
    out = [R("A910-A92S-A905VI-01", "A9.2 rf_500W, OQ-A907-11", "merge", "/h3_h4_inputs",
             {"h3_procurement_rfq_inputs_before_a9_2": ABSENT},
             {"h3_procurement_rfq_inputs_before_a9_2": {str(i): s for i, s in enumerate(old)}},
             "superseded H3 RF lines kept as history")]
    for i in range(3):
        out.append(R(f"A910-A92S-A905VI-0{i + 2}", "A9.2 rf_500W, OQ-A907-11, rf_measurement_reference", "set",
                     h3.format(i), old[i], new[i], f"H3 RF line {i + 1} per A9.2"))
    out += [
        R("A910-A92S-A905VI-05", "A9.2 rf_500W, rf_measurement_reference", "supersede", it.format("VI-RF-02"),
          {"name": "at the load plane", "value": "sized for 0-500 W forward", "source": "range for sizing the chain"},
          {"name": "forward RF power at the ICP-14 coupler plane (generator / 50-ohm side of the local matching "
                   "network, A9.2)",
           "value": "TBD - requires H-1 + ICP module operation; the laboratory chain provides the " + DELIV_500
                    + "; chain ratings TBD_AFTER_IMPEDANCE_MAP",
           "source": "owner answer row 72 as interpreted by A9.2 rf_500W (a delivered/operating capability; not an "
                     "operating value and not a component rating)"}, "VI-RF-02 plane and 500 W wording"),
        R("A910-A92S-A905VI-06", "A9.2 rf_measurement_reference", "supersede", it.format("VI-RF-03"),
          {"name": "at the load plane"},
          {"name": "reflected RF power at the ICP-14 coupler plane (generator / 50-ohm side of the local matching "
                   "network, A9.2)"}, "VI-RF-03 plane"),
        R("A910-A92S-A905VI-07", "A9.2 rf_measurement_reference", "supersede", it.format("VI-RF-04"),
          {"name": "at the load plane", "definition": "at the declared load plane"},
          {"name": "net RF power at the ICP-14 coupler plane (P_fwd - P_refl)",
           "definition": "P_fwd - P_refl at the ICP-14 coupler plane (generator / 50-ohm side of the local matching "
                         "network); includes the line, local-match and antenna ohmic loss downstream of the plane. "
                         "A9.2: P_delivered = P_forward - P_reflected - P_line/match,loss is the power past the local "
                         "match; P_forward = P_plasma is never assumed"}, "VI-RF-04 plane and A9.2 relation"),
        R("A910-A92S-A905VI-08", "A9.2 rf_measurement_reference", "replace", it.format("VI-RF-02") + "/definition",
          "at the declared RF load plane", "at the declared RF measurement plane, which A9.2 places on the generator / "
          "50-ohm side of the local matching network", "VI-RF-02 definition plane"),
        R("A910-A92S-A905VI-09", "A9.2 rf_measurement_reference", "replace", "/interface_demands[id=IF-06]/what",
          "directional coupler at the load plane", "directional coupler " + PLANE_A92, "IF-06 coupler plane"),
        R("A910-A92S-A905VI-10", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/how",
          "0-500 W lab chain", "0-500 W lab chain " + LBL_500, "row 72 application labelled"),
    ]
    return out


def _a92_repair2_a906() -> list:
    lab_gen = "the laboratory RF generator (" + DELIV_500 + "; rating TBD_AFTER_IMPEDANCE_MAP)"
    return [
        R("A910-A92S-A906-01", "A9.2 rf_500W", "replace", "/a9_flight_bom/flight[id=A9B-19]/status",
          "the laboratory 0-500 W generator (row 72)", lab_gen + " (row 72)", "A9B-19 500 W label"),
        R("A910-A92S-A906-02", "A9.2 rf_500W", "replace", "/a9_flight_bom/ground_article_only[id=GA-02]/item",
          "13.56 MHz 0-500 W lab RF generator", "13.56 MHz lab RF generator (" + DELIV_500 + ")", "GA-02 500 W label"),
        R("A910-A92S-A906-03", "A9.2 rf_500W", "replace", "/interface_demands[id=MA9-ID-13]/quantity",
          "the lab 0-500 W RF generator", "the lab RF generator (" + DELIV_500 + ")", "MA9-ID-13 500 W label"),
        R("A910-A92S-A906-04", "A9.2 rf_500W", "replace", "/owner_answers_applied[row=72]/how_applied",
          "lab 0-500 W RF generator", "lab RF generator (" + DELIV_500 + ")", "row 72 application labelled"),
        R("A910-A92S-A906-05", "A9.2 rf_500W", "replace", "/a9_1_decisions_applied[decision=OQ-A902-03]/how_applied",
          "lab 0-500 W RF is", "lab 0-500 W RF " + LBL_500 + " is", "OQ-A902-03 application labelled"),
    ]


def _a92_repair2() -> dict:
    return {"A9-01": _a92_repair2_a901(), "A9-02": _a92_repair2_a902(), "A9-03": _a92_repair2_a903(),
            "A9-05ev": _a92_repair2_a905ev(), "A9-05vi": _a92_repair2_a905vi(), "A9-06": _a92_repair2_a906(),
            "A9-07": _a92_repair2_a907()}
