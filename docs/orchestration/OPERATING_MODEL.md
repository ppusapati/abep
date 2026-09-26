# ABEP decision-acceleration operating model (binding; owner decisions 2026-09-26)

## 1. Lanes, triggers, terminal states
* Every unit of work is a registered, machine-addressable id (`lane_registry_v1.json`): `lane_NN_<name>` (owner numbering where
  one exists; break-even = `lane_28_break_even`, E×B physics = `lane_29_exb_physics`), campaign datasets `ds_<manifest>`, follow-ons
  `fo_<name>`. No prose dependencies.
* Follow-on work launches **only** from `trigger_registry_v1.json`.
* **Trigger execution is transactional and idempotent** (`scripts/orchestration/trigger_ledger.py`, ledger
  `trigger_ledger_v2.jsonl`, append-only, fsync'd): READY → CLAIMED → LAUNCHED → VERIFIED | FAILED. The execution key is
  sha256(trigger, member, dependency-state hash, config hash); the dependency-state hash covers each prerequisite's terminal state
  and identity (lane build commit, dataset provenance/structural-check sha256), and the config hash covers the pre-registration
  lock and the trigger registry. CLAIMED is persisted **before** launch through an exclusive-create claim file
  (`claims/<key>.<attempt>.claim`), and a trigger with a live claim is never READY again, so a crash after launch cannot relaunch it.
  LAUNCHED needs checkable evidence that the launch happened (workflow journal, runner log start line, or artifact). A claim with no
  LAUNCHED after 15 min raises ALERT STALE_CLAIM, and LAUNCHED without checkable evidence raises ALERT LAUNCH_UNCONFIRMED. Neither is
  ever relaunched automatically: the operator records either LAUNCHED (recovered, with evidence) or FAILED(launch_not_acknowledged)
  and claims attempt n+1. VERIFIED and FAILED are completion events with evidence. The CLI is
  `python scripts/orchestration/trigger_ledger.py claim|launched|verified|failed|show <trigger> [member] --evidence '<json>'`.
* Every ledger event carries `record_origin` (`live` or `retroactive_reconstruction`). Reconstructions carry the reconstruction
  time, the original event time and the evidence used. The two firings before this ledger existed (T_O4_SCORE and T_O4_ESCALATE
  for Johnson-low) are reconstructions. The v1 ledger `fired_triggers.jsonl` is frozen as historical evidence.
* A lane/follow-on satisfies a trigger only in the terminal state **`verified`**: its final verification round passed under its
  protocol (two-lens: evidence AND rules/recompute; lanes built by the first script: one adversarial reviewer, recorded as
  `single-lens-v1`) AND every registered dependency is verified. `verified_provisional`, `done_open_issues` and anything in progress
  never satisfy a trigger; `done_open_issues` needs operator repair and re-verification.
* `single-lens-v1` lanes (the first lanes workflow) are disclosed as such. If one of them becomes **decisive evidence for
  Milestone B or C**, it must first pass the second (two-lens) verification; its weaker review status is never silently promoted.
* Workflow-internal dependencies (`T_GRID`, `T_DOSSIER`) start the dependent lane at its prerequisites' terminal state and pass
  their verification flag; the dependent lane is `verified` only if the prerequisites are.
* No new broad lanes. Every lane answers (i) can an architecture be conditionally selected now, (ii) what evidence prevents
  physics-backed selection, or (iii) what engineering issue could later overturn the choice.
* Results are reported in milestone bundles, not lane by lane, unless a dependency changes.

## 2. Bundle 1 — Architecture Conditional Selection (`T_BUNDLE1`)
Prerequisites, all `verified`: lane_07_rf_evidence, lane_08_ecr_evidence, lane_09_hall_sustainment, lane_16_feed_envelope,
lane_17_hall_reference, lane_18_interstage, lane_20_ppu_magnet, **lane_24_hard_gates (hard prerequisite)**, lane_28_break_even,
fo_rf_breakeven_overlay, fo_ecr_breakeven_overlay, fo_hall_sustainment_envelope. The overlays are triggered by subsets of these,
so they always exist first.
**Outcome vocabulary (strict):**
* `CONDITIONAL_BASELINE(X)` — architecture X satisfies the current evidence and boundary criteria provided the explicitly listed
  conditions hold. At most one; declaring it among several non-eliminated architectures needs an explicit, stated discriminating
  criterion. It is a proposal for the owner's decision.
* `NO_BASELINE_YET` — evidence or normalization is insufficient; the exact blocking fields and lanes are listed.
* Per architecture: `ELIMINATED_WITHIN_TESTED_ENVELOPE` only where a hard physical/engineering gate (lane_24 logic, with the
  evidence class the gate requires) has been demonstrated — never because another architecture currently looks better.

## 3. Common comparison boundary (admissibility rule)
A comparison is **admissible only** when all architectures are normalized to the same spacecraft-side DC boundary
(`bus_power_boundary_v1`) and every mandatory field is populated or explicitly marked unavailable. Missing values may not be
silently omitted, replaced by subsystem values, or inferred from incompatible power definitions.
* Frozen physics field set: {ṁ_s, P_feed, T_feed, x_s, V_d, T, P_bus, m, Q_reject, life, startup, η_u, stability}. Here P_feed
  and T_feed are the **feed-state pressure [Pa] and temperature [K]** (with ṁ_s, x_s: the feed state), not powers.
* Every value carries metadata: units, operating-point definition (grid point id / feed-envelope case), evidence class and
  source, uncertainty or status (`available | unavailable:<reason> | TBD`), and derivation method.
* **P_bus** = all electrical power crossing the agreed spacecraft-side DC boundary for the architecture under comparison:
  discharge + pre-ionizer + cathode + magnets + PPU losses + gas path + controls/thermal = Σ P_load/η over hall_discharge,
  rf_source | ecr_source (+ ecr_magnet), cathode_keeper + cathode_heater, hall_magnet, flow_control + compressor, thermal_control +
  housekeeping. Electrically driven feed-system loads (compressor, flow control) are **included** in P_bus (gas-path term). Not a
  Hall discharge-only number, absorbed RF power, or ECR source power.

## 4. v2 chemistry: two separate questions
* **Question A** (`fo_v2_domain_question_a`): does the source evidence justify expanding the admissible energy domain (fixes OOD)?
* **Question B** (`fo_v2_excitation_question_b`): conditional on that domain, which electronic-excitation representation is
  supportable? Johnson-low stays a sensitivity/alternative until Question B independently supports promoting it; a large
  numerical effect (221 O4 triggers, status and verdict changes) is not validation.
* v1 remains INCONCLUSIVE permanently.

## 5. Execution provenance
Running score-bearing jobs are never altered. Future campaigns record JULIA_NUM_THREADS / BLAS / OMP threads, Julia version and
HallThruster commit per run, so resource-induced failures stay distinguishable from physical or numerical ones. The orchestration
runtime (daemon, monitors, runners) is recorded in `runtime_state.json` with its restart semantics.
