# NP-MISSION-INTEGRATION v1 — preregistration

Mission integration of the selected architecture `hall_icp_neutralizer` over `mission_scenario_v2` and the frozen
196-state environment, for AIR_PRIMARY and XE_CONTINGENCY. Work package SC-WP-09 (A9.31 sec. 12, priority 1 of sec.
22). Target: `abep-mission::integration` (additive module). Status PREREGISTERED_NOT_IMPLEMENTED; validation_status
NOT_VALIDATED.

`prereg_v1.json` is authoritative. This file restates it for people; where they differ, the JSON governs.

## What it is

A deterministic bookkeeping and integration model. For every state of the frozen design-state set v2 (196 states,
sha256 `60073e21…`) and each mode it assembles the per-state record from the admitted layers, propagates their
fail-closed statuses, and integrates per-state rates over a registered mode / state schedule into mission totals with
exact time and propellant accounting. It adds no device physics: every rate comes from a subsystem layer or is
NOT_EVALUATED.

It is not a requirement assessment (no RFP threshold, margin, PASS / FAIL or HC verdict: SC-WP-11), not a Hall or ICP
model, not an orbit propagation (altitude is a state coordinate; `mission_env.propagate` is not called in v1), not a
mission prediction while no schedule is registered, and not a choice of Xe load. Nothing is taken from the class-H
modules `mission5.py`, `mission_uq.py`, `transient.py`, `radiation.py`.

## Scope

* `hall_icp_neutralizer` only (other configurations MODEL_ERROR). No flight hollow cathode: no cathode field, load,
  line or event; cathode vocabulary in an input is refused.
* Supply modes AIR_PRIMARY and XE_CONTINGENCY, separate and never premixed (A9.14 OD6, A9.31 OQ-CHEM-10). NON_FIRING is
  a third segment mode for propulsion-off time.
* ICP gas routing `icp_gas_mode` ∈ {G-REUSE, G-ATM, G-XE} (A9.1 HIQ-06). G-REUSE, the registered primary, feeds the ICP
  from Hall exhaust / residual gas and adds no reservoir draw. G-ATM draws from the delivered atmospheric gas, G-XE from
  the Xe tank. G-ATM in XE_CONTINGENCY has no registered routing (INCOMPLETE_EVIDENCE).

## Inputs

| id | content | source |
|---|---|---|
| IN-SCN | H_M = mission_hours (MISSION_DURATION_BASIS), H_F = firing_hours (SUBSYSTEM_FIRING_LIFE_ASSUMPTION), independent | `abep_config::OperatingInputs` (mission_scenario_v2, manifest + code pin) |
| IN-ENV | per state: status, rho, fO / fN2 / fO2, n_O, T, V | `abep_atmos::execution::run` |
| IN-STATE | per (state, mode) subsystem quantities SF-05..SF-17 | the owning layers |
| IN-MASS | m_dry, m_xe,0, Xe planning cases (2 / 5 / 10 kg, carried together), reserve, residual | SC-WP-07 records, A9.25 msg 8 sec. 7 |
| IN-ROUTE | icp_gas_mode | A9.1 HIQ-06 (G-REUSE) |
| IN-SCHED | segments and events (optional) | none registered today (OQ-MI-01) |

No file under `config/requirements`, `config/constraints` or `config/assessment` is read.

## Quantity representation

Every field is a Quantity {units, status, value, parametric, evidence_class, uncertainty, source, reasons} or
NOT_APPLICABLE by the registered applicability table.

* Q-1: `value` exists iff status = EVALUATED.
* Q-2: a parametric / bound / planning result lives in `parametric` with its label (PARAMETRIC_SENSITIVITY_ONLY,
  PARAMETRIC_BOUND, PARAMETRIC_PLANNING_CASE, PARAMETRIC) and never enters `value`, an evidence integral, an envelope or
  a status (A9.31 sec. 16).
* Q-3: no non-finite value.
* Q-4: a structural zero (EVALUATED 0, evidence_class `structural`) exists only at a registered routing / applicability
  cell, never for a missing input.

## Per-state record (A9.31 sec. 16)

SF-01 rho, mass fractions, n_O, T; SF-02 V; SF-03 rho V; SF-04 AO flux n_O V; SF-05 intake capture; SF-06 intake-face
drag; SF-07 feed pressure / temperature; SF-08 delivered atmospheric mass flow; SF-09 Hall anode flow; SF-10 ICP
dedicated flow; SF-11 Hall state; SF-12 I_d; SF-13 I_e,cap; SF-14 P_bus (bus_power_boundary_a9_v2); SF-15 thrust; SF-16
host-spacecraft drag; SF-17 thermal (max solved node temperature); SF-18 total drag; SF-19 T − D (raw difference);
SF-20 Xe tank draw (routing R-XE); SF-21 atmospheric consumption (routing R-ATM); SF-22 feed balance = delivered −
consumed (raw; HC-11 is assessment); SF-23 state / domain / evidence status. M_n is not formed here (NP-ICP EX-05): the
assessment forms it from I_d and I_e,cap.

Applicability: in XE_CONTINGENCY the atmospheric delivery and feed balance are NOT_APPLICABLE; in NON_FIRING the Hall,
ICP and feed fields are NOT_APPLICABLE and thrust, Xe draw and atmospheric consumption are structural zeros. Routing
zeros: Xe draw in AIR_PRIMARY under G-REUSE / G-ATM; atmospheric consumption in XE_CONTINGENCY.

Derived sums and differences take the worst operand status, carry a value only if every operand is EVALUATED, and form
a parametric layer only when every operand has a value or a parametric value (DR-01, DR-02). Nothing is compared with
zero or a threshold.

## Schedule semantics

* SCH-01: ordered segments {id, mode, state_id, duration_h > 0}; per-state rates hold over a segment.
* SCH-02: events {id, segment_id, START_ATTEMPT, count, Xe / atmospheric mass per event}; no defaults.
* SCH-03: time accounting is exact: Σ dt = H_M, Σ firing dt = H_F, H_AIR + H_XE = H_F (exact expansion arithmetic).
  A violation means the schedule does not realise mission_scenario_v2: the whole integration is OUT_OF_DOMAIN.
* SCH-04: unknown / mixed mode, non-member state, bad duration → OUT_OF_DOMAIN; duplicate ids, unknown segment →
  MODEL_ERROR.
* SCH-05: no schedule → every schedule total NOT_EVALUATED (MISSION_SCHEDULE_NOT_REGISTERED), no value.
* SCH-06: the schedule is the only source of time weights. The 196 states carry no time weights (A9.14 S9.7); no rate
  is ever multiplied by H_M or H_F except in the parametric bound PB-AO.

## Equations

* EQ-01 c_k = q(s_k, m_k) · (dt_k · 3600); EQ-02 Q = Σ c_k accumulated exactly (Shewchuk expansions), reported
  faithfully rounded.
* EQ-03 time totals H_sched, H_fire, H_AIR, H_XE, H_coast.
* EQ-04 Xe consumption M_xe = ∫ Xe tank draw + Σ events; EQ-05 tank ledger m_xe,end = m_xe,0 − M_xe, usable =
  m_xe,end − reserve − residual (raw, may be negative); EQ-06 the same for every planning case, labelled
  PARAMETRIC_PLANNING_CASE, none selected; EQ-07 wet mass.
* EQ-08 atmospheric throughput (not stored): delivered, consumed, events, balance.
* EQ-09 bus energy; EQ-10 thrust / drag / net impulse; EQ-11 AO fluence.
* EQ-12 statewise envelopes (min / max with state ids only when every state is EVALUATED; parametric envelope separate).
* EQ-13 PB-AO = [min_s, max_s] AO flux × H_M × 3600, PARAMETRIC_BOUND: bounds the fluence of any schedule over the
  frozen states; the evidence status of the fluence stays NOT_EVALUATED without a schedule.

No Xe consumption is ever formed from Xe flow × H_M or × H_F (MS-02).

## Status propagation

Severity MODEL_ERROR > OUT_OF_DOMAIN > NOT_EVALUATED > INCOMPLETE_EVIDENCE > EVALUATED; every reason kept. No
NOT_EVALUATED input becomes a number. Determining-evidence gates: credible Hall set EMPTY → Hall-dependent fields
NOT_EVALUATED; NP-ICP not admitted → I_e,cap and ICP flows NOT_EVALUATED whatever the crate status; Xe load not frozen
→ m_xe,0 NOT_EVALUATED; host drag ICD absent → host drag NOT_EVALUATED; schedule outside mission_scenario_v2 →
OUT_OF_DOMAIN.

## Conservation (exact)

CONS-T1 time accounting; CONS-M1 Xe ledger (exact expansion residual 0, reported values within 1 ulp); CONS-M2 wet mass;
CONS-F1 atmospheric balance; CONS-S1 every state once per mode (196 × 3); CONS-I1 integral linearity.

## Interfaces

* IF-MIS-v1: `abep_mission::integration::integrate(inputs) -> MissionRecord` (raw keys only; no pass / fail / comply /
  margin / limit / threshold / feasible / chk_ / rfp_ / ic_ key).
* SC-WP-10 calls it per design candidate, admitted Hall member and uncertainty sample; envelopes across calls are
  formed there.
* SC-WP-11 reads the record and never modifies it (HC-05 / 07 / 08 / 11, bus and mass limits, thrust requirements).
* Decisive run (A9.31 sec. 16): `abep_mission::integration::today::run_admitted(repo_root, options)` assembles today's
  admitted inputs for all 196 states and both supply modes and calls `integrate`; it fills nothing the layers do not
  supply.

## Verification (run once after implementation; report `verification_report_v1`)

AL-01 constant rate; AL-02 piecewise integral vs exact rational; AL-03 Xe ledger; AL-04 time accounting (accept /
OUT_OF_DOMAIN / MODEL_ERROR); AL-05 status propagation; AL-06 severity table; AL-07 routing table; AL-08 AO fluence and
PB-AO bracketing over 200 random schedules; AL-09 cancellation (exact 3600.0); AL-10 derived quantities; AL-11
planning cases. FT-01..FT-15 fail-closed tests (credible set EMPTY, NP-ICP not admitted, no schedule, Xe load not
frozen, no zero fill, configuration / mode / state refusals, forbidden vocabulary, no RFP file read, no blind Xe ×
duration, parametric separation, time mismatch, malformed Quantity, cathode vocabulary). DET-01 / DET-02. IV-01: an
exact-rational Python scratch cross-check (non-authoritative, never a dependency).

VERIFIED iff all of these meet their criteria. VERIFIED is software verification only.

## Not evaluated today

Hall state, I_d, thrust, Hall flow, Xe-mode consumption (credible set EMPTY); I_e,cap and ICP flow (NP-ICP not
admitted); intake capture, feed state, delivered flow (no frozen design point; surface scenario TBD); host drag, total
drag, T − D; P_bus (official ledger partial boundary; Hall discharge needs a member); thermal; dry / wet mass and Xe
load; every schedule total (no schedule). Evaluable today: the environment fields and their envelopes, PB-AO, the
G-REUSE routing zeros, the planning-case labels, and optionally the F1 intake-face drag at a caller-supplied design
point (PARAMETRIC_SENSITIVITY_ONLY).

## Open owner questions

* OQ-MI-01: which record registers the mission schedule (state occupancy, XE_CONTINGENCY duration, start events)?
* OQ-MI-02: confirm G-REUSE (no dedicated reservoir draw) as the flight ICP gas mode for mission integration.
* OQ-MI-03: accept `pointing_factors` as AUDITED_NOT_PORTED.
* OQ-MI-04: v2 coupling of altitude evolution (`mission_env.propagate`) once thrust and host drag are evaluable?
* OQ-MI-05: which layer registers the NON_FIRING standby bus load and thermal state?

## Change control

Any change after the lock is a new version or a dated addendum; verification criteria are never relaxed after results
are seen; an interface change is IF-MIS-v2.
