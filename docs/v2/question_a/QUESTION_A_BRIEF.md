# v2 Question A: owner-decision brief (N₂ chemistry energy domain)

**Status: DRAFT_PENDING_OWNER.** Lane `fo_v2_domain_question_a`, trigger `T_V2_QUESTION_A`, date 2026-09-26.
**This brief decides nothing.** It sets out the evidence and the decision options. No option is chosen:
`question_a_brief.json` → `chosen_option` is `null`, and every option has `chosen: false`.

**v1 is permanent.** In the P5-N₂ v1 vacuum validation, all nine SGB screening candidates are INCONCLUSIVE / NOT
ELIGIBLE, the credible set is empty, and gate 3 is FAIL. None of that changes whatever is decided here. No v1 run is
re-scored or re-labelled.

**Scope limits.**
- Question B asks which electronic-excitation representation is supportable. It is separate, it depends on the
  answer to Question A, and this brief does not address it.
- Johnson-low stays a sensitivity.
- A validity limit is never extended because the solver reached a higher T_e.
- Screening candidates are not used as a source of performance numbers here. Candidate ids appear only in counts
  of v1 statuses.

**Milestones.**
- This brief supports **Milestone B**: it records the chemistry-domain part of what blocks physics-backed selection.
- For **Milestone A** it is an input only. A conditional selection does not need Physics Baseline 1.0, and an
  admitted Hall closure remains one of its explicit conditions.
- **To reach the next step**, the owner must answer Question A. After an A-PARTIAL or A-YES answer, the path is:
  the extended-domain completeness re-audit, then a hash-locked v2 pre-registration, then the v2 runs, then the O4
  dispositions, then an admission decision. Only after that can Milestone B use absolute Hall performance.

## Inputs

All inputs are read-only and pinned by sha256 in `build_question_a_brief.py`.

| input (repository path) | lane / commit | how it is used |
|---|---|---|
| `docs/chemistry/n2_domain_extension/domain_extension_audit.json` | lane_01_n2_domain_extension @ `0636634` | per-table verdicts, sources, caveats, owner decisions D-X1…D-X12, completeness items |
| `docs/chemistry/n2_domain_extension/domain_extension_requirements.json` | lane 01 @ `0636634` | v1 inventory, E_req, coverage criteria, hypothetical coverage counts |
| `docs/chemistry/n2_domain_extension/N2_DOMAIN_EXTENSION_AUDIT.md` | lane 01 @ `0636634` | narrative, §6 evidence tables, §9 decisions |
| `docs/chemistry/n2_domain_extension/drafts/p5_n2_validation_v2_prereg_OUTLINE_DRAFT.md` | lane 01 @ `0636634` | v2 outline: §1 changes, §3 run scope, §4 hash-lock steps, §6 decisions 1–14 |
| `docs/forensics/p5_n2_v1/ood_attribution/ood_attribution.json` (+ `OOD_ATTRIBUTION.md`) | lane_02_ood_attribution @ `5e5c8a7` | OOD cause patterns, per-candidate/member OOD counts, hypothetical ladder |
| `hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json` | base | O3 verdict aggregation rule (quoted) |
| `docs/orchestration/OPERATING_MODEL.md` | base | the question as the operating model words it |

When this brief was written, the lane files were read from the lane worktrees
(`.claude/worktrees/wf_17c9b0e6-1cb-2`, `…-1cb-1`). The builder resolves them from this checkout if they are
present, and otherwise from the lane commits.

**How numbers are traced.** Every number below is in `question_a_brief.json` as `{value, file, field}`. Quoted
lane-01 numbers keep lane 01's own `from` path into the requirements JSON. The only numbers this brief derives
itself are the integer counts in `derived_bounds` (see §2b.2). They use a stated rule, and they are recomputed by
`build_question_a_brief.py --check`.

## 1. The question (verbatim)

- Lane task: *"does INDEPENDENT PUBLISHED evidence justify expanding the admissible N2 chemistry energy domain
  beyond the pre-registered 45 eV mean energy (T_e 30 eV)?"*
- `docs/orchestration/OPERATING_MODEL.md` §4: *"**Question A** (`fo_v2_domain_question_a`): does the source evidence
  justify expanding the admissible energy domain (fixes OOD)?"*
- CLAUDE.md, next-work item 3: *"Question A (is a wider domain source-supported?)"*

## 2. Evidence by table family (lane 01, copied)

Only the 21 tables capped at 45 eV are ever beyond their limit in v1. None of the ten tables with a 255 eV limit
is exceeded (lane 01 `v1_inventory.tables_with_255eV_limit_beyond` = [], lane 02 `co_occurrence.n_runs_any_255eV_file_beyond`
= 0).

### 2.0 How lane 01 reached its verdicts

The rule is `domain_extension_requirements.json` → `verdict_criteria.rule`. All verdicts are DRAFT_PENDING_OWNER.
- **C1 (coverage):** less than 1 % of the table's rate at L comes from above the last point covered by accessible
  published σ.
- **C2 (shape):** swapping in any passing independent set's shape above the last source point changes the rate at
  L by less than 1 %.
- **C3 (join):** the independent set agrees with the table at the table's last source point, within the stated
  uncertainty.
- **Readings.** The *measured* reading counts only measured sets, or sets reconstructed from measured ones. The
  *evaluated* reading also counts evaluated sets that are secondary reproductions of abstract-only papers.
- **Verdicts.**
  - SUPPORTED: the measured reading passes at 60 eV or above.
  - PARTIAL: only the evaluated reading passes, or the table passes but has a documented omission.
  - UNRESOLVED-BY-SOURCE: no accessible independent set passes C3.
  - UNSUPPORTED: a set passes C3 but fails C2 at 60 eV. No table falls in this class.

### 2.1 Summary

| family | tables | lane-01 verdicts | DRAFT extended limit | v1 OOD runs with the table beyond (of 714) |
|---|---|---|---|---|
| dissociation | 1 | SUPPORTED | `dissociation_N2.dat` → **60 eV** (measured reading) | 714 |
| electronic | 8 | a¹Π_g PARTIAL; A, B, W, B′, a′, w, C UNRESOLVED-BY-SOURCE | none | 633–674 |
| rotational | 2 | UNRESOLVED-BY-SOURCE (both) | none | 677 (j0→2), 659 (j0→4) |
| vibrational | 10 | PARTIAL (all ten) | none | 537–543 |

Sources for this table:
- Verdicts: `domain_extension_audit.json` → `tables.<table>.verdict` and `.proposed_extended_limit_mean_energy_eV`.
- OOD counts: `domain_extension_requirements.json` → `v1_inventory.tables.<table>.n_ood_runs_beyond_limit`. These
  equal lane 02's `per_file.<table>.n_runs_f_out_gt_tol` for all 21 tables (see `cross_lane_checks`).

### 2.2 Dissociation (`dissociation_N2.dat`): SUPPORTED, DRAFT limit 60 eV

**Where the table comes from.**
- Song et al. 2023 Table 9, 12–200 eV, ±20 %. This is the Cosby recommended set, a weighted average with Winters
  1966 [evaluated measurement, transcribed].
- Above 200 eV the table holds σ at 0.95×10⁻¹⁶ cm², with a fixed 12.14 eV energy loss.

**Independent evidence above 200 eV.** All of it was read from the vector Fig. 19 of Song 2023.

| set | evidence class (lane 01) | coverage | ratio to Cosby at 200 eV | C3 |
|---|---|---|---|---|
| Winters 1966 neutral points | reconstructed from measured data → digitized (vector); abstract only; ±20 % | 22.6–296.2 eV | 1.249 | passes (within ±28 % combined) |
| Majeed & Strickland 1997 | evaluated → digitized; uncertainty TBD (requires full text) | 11.0–974.6 eV | 0.900 | passes |
| Kawaguchi et al. 2021 | evaluated → digitized; uncertainty TBD | 14.0–1002 eV | 0.749 | fails (outside ±20 %) |

Sources: `tables.dissociation_N2.dat.independent_evidence[*].numbers.over_Cosby_at_200eV`. Coverage ranges are the
same entries' `coverage_eV`.

**Criteria numbers** (`tables.dissociation_N2.dat.criteria_numbers`):
- C1 in the measured reading (rate share beyond 296 eV): 0.47 % at 60 eV and 1.69 % at 75 eV.
- C2, largest shape impact: 0.34 % at 60 eV, 0.93 % at 75 eV and 1.86 % at 90 eV.
- L\* (measured coverage) = 67.96 eV.
- Largest candidate limit that passes: 60 eV in the measured reading and 75 eV in the evaluated reading. The 75 eV
  value is not proposed.

**E_req against available data.** E_req is the cross-section upper energy a source must reach so that the rate
share from higher energies stays below the threshold. At L = 60 eV:
- E_req is 262 eV at the 1e-2 level, 664 eV at 1e-6 and 1241 eV at 1e-12
  (`requirements.per_table.dissociation_N2.dat.by_limit.60.hold_envelope_E_req_eV`).
- Measured-reading coverage ends at 296.2 eV (`verdict_criteria.per_table.dissociation_N2.dat.coverage_end_measured_reading_eV`).
- So only the 1 % convention can be met. Neither 1e-6 nor 1e-12 can.

**Caveats** (verbatim, `tables.dissociation_N2.dat.conditions`):
1. The table is unchanged (no rebuild). The proposal concerns the validity limit only.
2. The fixed 12.14 eV energy loss is supported only by Cosby's 48.5 eV translational spectra. Its model
   uncertainty, 9.75–13.33 eV, stays carried.
3. Kawaguchi 2021 is 25 % below Cosby at 200 eV, outside ±20 %. This normalisation disagreement also exists inside
   the v1 domain (0.76 at 50 eV). It is recorded, not resolved.
4. **The SUPPORTED verdict rests on two reconstructed Winters points above 200 eV** (about 246 and 296 eV),
   digitized from a secondary figure. None of the three sets is independent of Table 9 at the 200 eV join: Table 9
   averages Cosby and Winters, and MS1997 used Cosby. Whether that suffices is owner decision **D-X12**.

**What would change the verdict** (lane 01):
- measured data between 296 eV and about 330 eV (E_req(1e-2) at 75 eV is 327 eV);
- the MS1997 / Kawaguchi full texts, showing how their parts above 200 eV were built.

### 2.3 Electronic excitation (8 states): a¹Π_g PARTIAL; seven states UNRESOLVED-BY-SOURCE

**Where the tables come from.**
- Su et al. 2021, R-matrix, below 20 eV [model-derived].
- Johnson et al. 2005 Table 2, measured ICS from 20 eV to 100 eV (a¹Π_g to 200 eV) [measured].
- Above Johnson's last point: a power-law continuation from Johnson's last two points, up to 10 keV [declared
  model].

**Independent evidence.**
- Majeed & Strickland 1997, via the QST open-data files of Tabata 2006 [evaluated → secondary numeric
  reproduction; uncertainty TBD].
- The Tabata analytic fits, which are not independent of MS1997.
- Kawaguchi 2021, which gives ICS up to 10 keV but is abstract-only. It was not taken from LXCat.

| state | verdict | Johnson last point (eV) | MS1997 / table at the join | L\* own sources (eV) | C1 share beyond measured coverage at 60 eV | E_req(1e-2) at 60 eV (eV) |
|---|---|---|---|---|---|---|
| a¹Π_g | PARTIAL | 200 | 0.82 (at 200 eV; within Johnson ±25.5 %) | 59.5 | 1.03 % | 211 |
| A³Σ_u⁺ | UNRESOLVED-BY-SOURCE | 100 | 0.35 (100 eV) | 40.0 | 3.10 % | 192 |
| B³Π_g | UNRESOLVED-BY-SOURCE | 100 | 0.69 | 51.4 | 1.46 % | 162 |
| B′³Σ_u⁻ | UNRESOLVED-BY-SOURCE | 100 | 1.91 | 40.5 | 2.94 % | 188 |
| C³Π_u | UNRESOLVED-BY-SOURCE | 100 | 1.27 | 44.8 | 2.16 % | 176 |
| W³Δ_u | UNRESOLVED-BY-SOURCE | 100 | 0.46 | 42.8 | 2.53 % | 181 |
| a′¹Σ_u⁻ | UNRESOLVED-BY-SOURCE | 100 | 3.82 | 34.9 | 4.98 % | 207 |
| w¹Δ_u | UNRESOLVED-BY-SOURCE | 100 | 0.17 | 27.5 | 14.19 % | 240 |

Sources for each column:
- MS1997 ratios: `tables.<t>.independent_evidence[majeed_strickland1997].numbers.MS1997_over_table_at_{100,200}eV`.
- L\*: `verdict_criteria.per_table.<t>.L_star_own_sources_eV`.
- C1: `…by_limit.60.coverage_share_measured_reading`.
- E_req: `requirements.per_table.<t>.by_limit.60.hold_envelope_E_req_eV["0.01"]`.

**Caveats.**
- **a¹Π_g.** Measured coverage ends at 200 eV. The evaluated reading passes up to 150 eV (shape impact ≤ 0.34 %).
  The measured reading passes no candidate limit. No limit is proposed.
- **The other seven states.** MS1997 disagrees with Johnson's measured value at 100 eV by factors of 0.17–3.8,
  beyond Johnson's stated ±18–35 %. C3 fails, so these sets cannot test the continuation. The same conflict is
  present at 50 eV, inside the v1 domain. It is recorded, not acted on (lane-01 audit §6.2; D-X9).
- **The continuation already exceeds 1 % below 45 eV for several states.** Lane 01 states this as context and
  proposes no change to any v1 limit.
- **B³Π_g, own coverage.** Johnson's own coverage keeps the continuation below 1 % up to 51.4 eV. Lane 01 says
  this "is not a candidate limit, not independent evidence, and not proposed".
- **Johnson-low tables.** They share the nominal continuation, so these verdicts apply to them unchanged. Which
  representation is supportable is Question B, not answered here.
- **What would change the verdicts** (lane 01):
  - numerical Kawaguchi 2021 ICS above 100 eV (full text, not LXCat);
  - measured ICS above 100 eV;
  - the Itikawa 2006 full text.
  - For a¹Π_g, a measured ICS or excitation function above 200 eV (Ajello & Shemansky 1985 is named by lane 01 as
    "not accessed - verify"), or owner acceptance of the evaluated reading.

### 2.4 Rotational excitation (j 0→2, 0→4): UNRESOLVED-BY-SOURCE

**Where the tables come from.** Song 2023 Table 6, 0.01–10 eV. This is an R-matrix SEP calculation
[model-derived, theory]. Above 10 eV σ is held at the 10 eV value [declared model].

**Coverage.**
- No accessible independent cross section exists above 10 eV.
- Tabata n2-4 ends at 2.94 eV. Itikawa 2006 and Kawaguchi 2021 were not accessible.
- The held part carries 96.3 % (j0→2) and 91.9 % (j0→4) of the rate at 45 eV, and 97.8 % and 95.2 % at 60 eV
  (`key_numbers.declared_share_above_last_source_point_at_45eV`; `criteria_numbers.share_beyond_10eV_at_60eV`).
- E_req(1e-2) at 60 eV is 266 eV and 264 eV, against 10 eV of source coverage.

**Caveats.**
- For j0→2, σ is still rising at 10 eV, so E_req from the hold envelope is not conservative
  (`hold_envelope_is_upper_bound` = false).
- A Born quadrupole estimate (Gerjuoy & Stein 1955) is named by lane 01 as "from memory: verify" and is not used.
- **What would change the verdict:** published rotational σ above 10 eV, or an owner decision that a theory-only
  envelope may count as coverage (**D-X8**).

### 2.5 Vibrational excitation (v 0→1 … 0→10): PARTIAL

**Where the tables come from.** Laporta et al. 2014 Eq. (10) fits of resonant rates. The rate integrals were
taken to 15 eV, and no temperature range is stated [model-derived]. The declared closure is "resonant only". E_req
is not defined for these tables (rate fits, no cross section in the repository); the flat-σ reference is 266 eV at
60 eV.

**Independent evidence** (`tables.excitation_N2_vib_0_to_1.dat.independent_evidence`):
- The Tabata n2-5 fit to the Itikawa 1986 v 0→1 data, 1.05–48.5 eV [evaluated → secondary].
  - In the resonance region it agrees with the table: 0.77 of the table's rate at T_e 2 eV.
  - The non-resonant part (5–48.5 eV), which the table omits, is 2.05× the table's 0→1 rate at T_e 30 eV, 2.44× at
    40 eV and 2.91× at 60 eV.
- Tanaka 1981 [measured; metadata only].
- Truhlar 1972 [model-derived vs measured; abstract], which describes non-resonant excitation at 30–83 eV.
- Overtones (v_f ≥ 2): the only accessible data cover 1.9–3.0 eV.

**Caveats.**
- The resonant content has no tail extrapolation.
- The omission is a completeness question (the F_P rule), to be settled in the extended-domain re-audit.
- **What would change the verdict** (lane 01): a pre-registered extended-domain completeness re-audit that bounds
  the omitted non-resonant vibrational power, and an owner decision on whether "resonant only" remains acceptable
  above T_e 30 eV (**D-X7**).

## 2b. What each option would do to the v1 OOD runs: hypothetical counting only, not scoring

These are counts only. They are not a scoring, a status, a verdict or a proposal to change a limit.

**Why the counts are a proxy.**
- The frozen v1 records hold f_out only at 45 eV. They also hold `max_mean_energy_active_eV` (eps_active).
- A run "counts as covered at L" when eps_active ≤ L. Lane 02 shows this is neither sufficient nor necessary for
  f_out(L) ≤ 1e-12. It bounds f_out(L) only to ≤ 1e-7, and that bound rests on a frame × cell count lane 02 marks
  as "inferred … verify".
- Exact counts need reruns.

**v1 baseline** (lane 01 `v1_inventory`, lane 02 `co_occurrence`):
- 1080 records; 714 runs are OUT_OF_DOMAIN.
- Run-readings: 1428 OUT_OF_DOMAIN, 700 FAIL_VALIDATION, 32 PASS.
- OOD cause pattern:
  - 537 runs have the full 45 eV family beyond its limit.
  - 36 are dissociation-only.
  - 135 have no vibrational file beyond.
  - 6 have some but not all vibrational files beyond.
- Only 37 OOD runs have no rotational file beyond: patterns `D1 E0 V0 R0` = 36 and `D1 E1 V0 R0` = 1.

### 2b.1 Per option

| option | v1 OOD runs that could leave OUT_OF_DOMAIN: proxy (of 714) | hard upper bound from the beyond-limit pattern | runs that stay OOD whatever a rerun shows |
|---|---|---|---|
| **A-NO** (all 21 at 45 eV) | 0 | 0 | 714 |
| **A-PARTIAL**, measured reading (dissociation → 60 eV) | **6** (`draft_proposed_limits_mean_energy_eV.hypothetical_coverage_if_applied.newly_covered_ood_runs`) | **36** (`v1_inventory.n_ood_runs_dissociation_only_beyond`; outline §3 calls the split exact under reproducible reruns) | 678 |
| A-PARTIAL, evaluated reading (dissociation 75 eV + a¹Π_g 150 eV; not proposed) | 22 (`…hypothetical_coverage_evaluated_reading.newly_covered_ood_runs`) | ≤ 37 (runs with no rotational file beyond) | ≥ 677 |
| A-YES, hypothetical: all 21 raised to L = 60 / 75 / 90 / 120 / 150 eV (not evidence-supported) | 211 / 423 / 609 / 710 / 714 | – | – |
| A-YES except rotational (rotational kept at 45 eV) | 6 / 22 / 30 / 37 / 37 | 37 | 677 |

Sources for the A-YES rows: `hypothetical_coverage.limits.<L>.all_capped_tables_at_L.newly_covered_ood_runs` and
`all_capped_except_rotational_at_L`. The five lane-01 A-YES counts equal lane 02's
`hypothetical_limit_ladder_45eV_family.ladder[L].n_officially_OOD_runs_with_all_45eV_files_eps_active_le_L`.

**(candidate, global layer-1 member) cells whose 20 runs are all evaluable** (lane 02 ladder,
`n_candidate_member_cells_all_20_runs_eps_active_le_L`):
- In v1, officially: 2 of 108.
- With all 21 tables raised to L = 60 / 75 / 90 / 120 / 150 eV (proxy): 8 / 26 / 44 / 100 / 108.

Neither lane publishes this cell count for dissociation-only extensions. Lane 01 has no per-candidate breakdown by
design.

### 2b.2 Derived bound: what a minimal v2 can and cannot change

This is counting, not a prediction (`derived_bounds`). It is computed by `build_question_a_brief.py` from lane-02
fields and the v1 O3 rule.

**Assumptions.** These define the "minimal v2" of the lane-01 outline:
- tables are byte-identical and only limits rise;
- the HallThruster.jl pin is unchanged, with the same 30 cases and 9 transports and no retuning;
- reruns reproduce the v1 trajectories. The outline says pinned code gives the same trajectories and asks for a
  bit-for-bit sample to verify it;
- D1–D6 and O1–O5 are unchanged;
- both rotational tables stay at 45 eV, which holds for every evidence-supported option.

**Rule.** Under O3 (`p5_n2_validation_criteria_v1.json` → `operational_rules.O3_verdicts`):
- A global member PASSes only if all 20 of its runs PASS. A candidate is PROMOTABLE only if some member PASSes.
- A v1 FAIL member contains a FAIL_VALIDATION run, and under these assumptions that run keeps its status.
- A v1 INCONCLUSIVE member can reach PASS only if every one of its OOD runs leaves OUT_OF_DOMAIN.

**Counts.**
- With rotational at 45 eV, only the 37 runs with no rotational file beyond can leave OOD.
- Per candidate, that is at most max DISSOCIATION_ONLY (8, `breakdown.candidate.*.OOD_categories`) + 1 = **9 runs**.
- Every v1 INCONCLUSIVE member (42 of 108 cells) has **at least 16** OOD runs
  (`breakdown.official_member_verdict_vs_OOD_count.INCONCLUSIVE`). The other 66 cells are FAIL.

**Consequence.** Under these assumptions, **no global member can reach PASS in a minimal v2, so no candidate can
become PROMOTABLE and the credible set stays empty.** This holds for A-NO and for both A-PARTIAL readings.

**Where the bound does not apply:**
- a v2 that changes any table (evidence-shaped tail, non-resonant vibration, a process promoted by the re-audit);
- different cases, candidates or criteria;
- facility mode, which never gates.

The count of 37 equals lane 01's `all_capped_except_rotational_at_L` at 120 and 150 eV.

## 3. Completeness re-audit items an extended domain would require (lane 01, copied)

**Why a re-audit is needed.** Every v1 omitted-process verdict holds only on T_e 2–30 eV (vibrational and
rotational: 0.2–30 eV). The basis is `prereg/n2_completeness_audit_v1.json` with addenda 1–2,
`audit/n2_completeness_final_v1.json` and `audit/n2_closure_verdicts_v1.json`.

**Rule** (`completeness_implications.rule`):
- The extended-domain re-audit must be pre-registered: domain, processes and denominators.
- The thresholds stay F_P 1 %, F_ion 1 % and F_S 5 % unless the owner decides otherwise.
- It must be completed **before any v2 run**.
- For a 60 eV limit the domain is T_e ≤ 40 eV (outline §1).
- Any promotion is a model change and means a full rerun.

| process | v1 verdict (T_e ≤ 30 eV) | why it must be re-audited |
|---|---|---|
| N²⁺ → N³⁺ (threshold 47.45 eV) | EXCLUDED (F_ion ≤ 1.5e-6) | the threshold is inside the extended domain; the rate is 1.60× (T_e 40 eV) to 3.84× (T_e 100 eV) its T_e 30 eV value |
| N₂ → N₂²⁺ direct (42.9 eV) | UNCERTAINTY VARIANT (nominal ≤ 0.39 %, upper 2.6 % F_ion) | upper envelope over N₂⁺ production is 0.064 at T_e 30 eV and 0.086 at T_e 100 eV; the nominal could cross 1 % |
| N₂⁺ → N₂²⁺ sequential | EXCLUDED from nominal (margin 3.7) | smallest margin of the closure; the rate at T_e 100 eV is 2.70× its T_e 30 eV value |
| N → N²⁺ direct (HMS 2017) | PROMOTED | its ×0.5/×1.3 sensitivity must be re-run |
| non-resonant vibrational excitation | outside the declared closure | 2–3× the resonant 0→1 rate at T_e 30–60 eV; F_P must be bounded |
| rotational above 10 eV | PROMOTE (marginal, gross F_P 1.13 %) | no σ above 10 eV exists; a bound is needed |
| dipole-allowed / higher states (b¹Π_u, c₃¹Π_u, o₃¹Π_u, b′¹Σ_u⁺, c′₄¹Σ_u⁺, E³Σ_g⁺, a″¹Σ_g⁺, G³Π_u, F³Π_u) | not in the pre-registered tier lists | the radiating part is an omitted loss that grows with energy (lane 01: "from memory, verify"); measured ICS exist at 13/17.5–100 eV (Malone 2009/2012, Liu 2017), not accessed |
| triple / multiple ionization (N₂³⁺, N → N³⁺, extra N⁺ from triple events) | not assessed | their thresholds lie inside the extended domain |
| dissociation energy loss (fixed 12.14 eV) | 9.75–13.33 eV carried | the channel mix above 48.5 eV is not covered by Cosby's analysis |

Source: `domain_extension_audit.json` → `completeness_implications.items[0..8]`. The numbers come from
`completeness_indicators.by_mean_energy_eV.*`.

## 4. Decision options (none chosen)

### A-NO: no extension is justified

**What it means.**
- All 21 capped tables keep 45 eV.
- The domain-extension path stops. The lane-01 audit is kept as the recorded negative or insufficient evidence.

**Evidence position.** Lane 01's own SUPPORTED verdict for dissociation rests on D-X12. A-NO follows if the owner
does not accept two reconstructed, non-independent Winters points, or adopts a stricter threshold (D-X3). At 1e-6
or 1e-12, no table is SUPPORTED.

**Consequences.**
- No v1 OOD run becomes evaluable (0 of 714). A v2 with the same inputs would reproduce v1.
- On the P5-N₂ route every candidate stays INCONCLUSIVE / NOT ELIGIBLE, and the credible set stays empty.
- **Blocker to record for Hall admission:**
  - The pre-registered chemistry domain (T_e ≤ 30 eV) does not contain the instantaneous states the screening
    transports reach at P5-N₂ conditions (714 of 1080 v1 runs OOD; all exceedances are transient per lane 02 §5).
  - The accessible published evidence does not support a wider domain. The gaps are rotational σ above 10 eV,
    electronic σ above 100 eV (a¹Π_g above 200 eV), and non-resonant vibration.
- Question B's precondition ("conditional on that domain") is not established. Question B itself is not addressed.

**What it requires next.**
- A dated owner decision record.
- A blocker entry on the admission path.
- A reopening condition: genuinely new published evidence, for example through legitimate full-text access
  (D-X5).

### A-PARTIAL: only the evidence-supported extension, `dissociation_N2.dat` → 60 eV

**What it means.**
- The limit moves from 45 eV to 60 eV (measured reading). The table is unchanged.
- The other 20 capped tables stay at 45 eV.
- **Sub-variant, not proposed by lane 01:** the evaluated reading (dissociation 75 eV, a¹Π_g 150 eV). It needs D-X2
  to be decided as evaluated-inclusive.

**What it unblocks.**
- A pre-registrable v2 limited to one validity-limit change.
- Chemistry evaluability for at most 36 v1 OOD runs: 6 by the proxy, 22 in the evaluated sub-variant, with a hard
  bound of 37. Which statuses those runs would get is not predicted.

**What it does not unblock.**
- The 678 OOD runs in which an unchanged table is beyond its unchanged limit.
- Any global member PASS in a minimal v2 (§2b.2). No candidate could become PROMOTABLE this way, and the credible
  set would stay empty.
- The electronic, rotational and vibrational domains.

**What it requires next.**
- Owner decisions:
  - D-X12 (the Winters points);
  - D-X2 (which reading counts);
  - D-X3 (the threshold);
  - D-X4 (the C3 tolerance);
  - D-X6 (keep the held tail unchanged or rebuild it, and whether Kawaguchi's −25 % warrants a variant).
- The pre-registered extended-domain completeness re-audit on T_e ≤ 40 eV, completed before any v2 run.
- A new versioned `rate_validity` entry, written by the owner under `propellants/`, with the v1 file and configs
  snapshotted.
- v2 criteria and run-status copies that differ only in their domain references, a hash lock, and a merged
  pre-registration PR (outline §4 steps 1–6).
- The run scope, D-X11:
  - (A) the 36 runs plus a bit-for-bit reproduction sample under a pre-registered reuse rule; or
  - (B) a clean 1080-run rerun.
  - Either way, the owner also decides how the facility and O4 datasets are treated under v2.
- Reruns are unavoidable, because the frozen records do not hold f_out at 60 eV.

### A-YES-WITH-CONDITIONS: wider extension, only where evidence supports it

**What it means.** Raise limits beyond dissociation. **The accessible evidence does not support this today for 20
of the 21 tables.**

**The evidence each family would need** (lane-01 `what_would_change_the_verdict`, copied per table in the JSON):

| family | what would have to exist or be decided | coverage needed at L = 60 eV (1e-2 level) vs what is available |
|---|---|---|
| rotational | published σ above 10 eV, or owner acceptance of a theory-only envelope (D-X8) | 264–266 eV vs 10 eV |
| electronic (7) | numerical Kawaguchi 2021 ICS or measured ICS above 100 eV via legitimate access (D-X5); a decision on the MS1997–Johnson conflict (D-X9) | 162–240 eV vs 100 eV |
| a¹Π_g | measured σ above 200 eV, or the evaluated reading (D-X2) | 211 eV vs 200 eV measured (1000 eV evaluated) |
| vibrational (10) | bound or add non-resonant excitation (D-X7); adding it is a model change | E_req not defined (rate fits); flat reference 266 eV vs 15 eV |
| dissociation above 60 eV | measured data between 296 eV and about 330 eV | 327 eV at 75 eV vs 296.2 eV |

**Further conditions.**
- The extended-domain completeness re-audit on the wider domain (D-X10). It may add processes: N²⁺ → N³⁺, N₂²⁺,
  higher states, multiple ionization.
- A full v2 pre-registration. Any table change also needs a new reaction-set version and a full rerun.

**Consequence for OOD (proxy).** If every table reached L, the proxy counts are the A-YES row of §2b.1:
211 / 423 / 609 / 710 / 714. Only an option that includes rotational can go beyond 37 runs.

### Owner decisions enumerated by lane 01 (all open, verbatim in `owner_decisions`)

| audit JSON id | outline §6 no. | subject |
|---|---|---|
| D-X1 | 1 | open a v2 at all (dissociation → 60 eV alone covers about 6 of 714 by the proxy; 22 in the evaluated reading) |
| D-X2 | 2 | coverage reading: measured-only (the lane-01 default) or evaluated-inclusive |
| D-X3 | 3 | extension threshold: 1 % convention, or 1e-6 / 1e-12 (nothing supported at the stricter levels) |
| D-X4 | 4 | C3 join tolerance; treatment of sets without accessible uncertainty (MS1997, Kawaguchi 2021) |
| D-X5 | 5 | legitimate full-text access (library or purchase; no paywall bypass; no LXCat) to Kawaguchi 2021, MS1997, Itikawa 2006, Cosby 1993 and Winters 1966 (the outline adds a search for rotational σ above 10 eV) |
| D-X6 | 6 | dissociation: keep the held tail or rebuild it (a model change); Kawaguchi −25 % variant |
| D-X7 | 7 | vibrational: keep "resonant only", add non-resonant (a model change), or bound it in the re-audit |
| D-X8 | 8 | rotational: theory-only envelope above 10 eV, or keep 45 eV |
| D-X9 | 9 | electronic: record the MS1997–Johnson conflict only, or carry it as a future variant (never in v1) |
| D-X10 | 10 | pre-register the extended-domain completeness re-audit (domain, processes, denominators) |
| D-X11 | 11 + 12 | v2 run scope (A minimal / B clean, facility and O4 treatment); per-frame activity histograms in `bridge_lib.jl` |
| – | 13 | whether D1–D6 or O1–O5 change at all (default **no**) |
| D-X12 | 14 | whether two reconstructed Winters points above 200 eV suffice for dissociation → 60 eV |

The mapping between the two numberings is this brief's reading (QA-2). The same number means different things in
the two lane-01 files: "decision 12" is the Winters points in the audit, but the driver histograms in the outline.

## 5. What each option implies for Hall-transport admission and Milestone B

These are consequences, not recommendations.

**Common to all options.**
- Admission stays gated on the O4 dispositions (CLAUDE.md; `hall_ensemble._check_o4`).
- The facility mode never gates (O3).
- Milestone B needs credible envelopes from validated Hall transport. It stays blocked until a closure is admitted.
- Milestone C stays behind B.
- Milestone A does not need Physics Baseline 1.0. It carries "admitted Hall closure" as an explicit condition.

| option | can a scoreable v2 exist? | can a minimal v2 produce a PROMOTABLE candidate? | route to admission after this option |
|---|---|---|---|
| A-NO | no v2 on the chemistry-domain ground | no (a v2 equals v1) | the P5-N₂ route is closed for the current 9 candidates; admission needs other evidence, not identified in the lane files |
| A-PARTIAL (measured or evaluated reading) | yes, re-scoring at most 36 runs (≤ 37 in the evaluated reading) | **no**, under the §2b.2 assumptions | as A-NO for the current candidates, unless the owner also changes a table (a model change, a full rerun, and nothing inferred from v1) |
| A-YES-WITH-CONDITIONS | only after the evidence in §4 exists, plus the re-audit and pre-registration | not bounded by §2b.2 if rotational is extended or any table changes; the proxy then allows up to 8 / 26 / 44 / 100 / 108 of 108 cells with all 20 runs evaluable at L = 60 … 150 eV (necessary, not sufficient) | open in principle; depends on evidence not accessible today |

**Open question for the owner (QA-5).** Under the promotion rule, a screening candidate becomes a member only after
it predicts new evidence not used to select it. Would a v2 scored on the same P5-N₂ measurements, after the v1
scores are known, still count as such a test? The lane-01 outline requires a hash-locked pre-registration before
any v2 run. It does not address this point.

## 6. Status and QA notes

**Status: DRAFT_PENDING_OWNER.** No option is chosen. `owner_decisions.decided` is empty.

**Cross-lane checks** (`cross_lane_checks`, all equal). Lane 01 and lane 02 agree on:
- the OOD total (714) and the dissociation sole-cause count (36);
- the 175 in-domain runs that are not proxy-evaluable at 45 eV;
- the OOD runs newly covered with all 21 tables at each L;
- the per-table OOD counts for all 21 tables.

**QA observations** (`qa_observations`):
- **QA-1.** The total covered-run counts differ by definition: 577 (lane 01) vs 468 (lane 02) at 60 eV. Lane 01
  credits in-domain runs; lane 02 requires eps_active ≤ L for every file. The OOD counts agree.
- **QA-2.** The owner-decision numbering differs between the lane-01 audit (D-X1…12) and the outline (1…14). See the
  mapping in §4.
- **QA-3.** Lane 02 calls any extension "a model change with its own reruns". The lane-01 outline treats a
  limit-only change with byte-identical tables as a minimal v2. Both require reruns. How to log a limit-only change
  (CLAUDE.md rule 2, docs/HISTORY.md) is the owner's call.
- **QA-4.** In the proxy, the evaluated reading (dissociation 75 eV + a¹Π_g 150 eV) covers 22 OOD runs, the same
  as dissociation alone at 75 eV. The a¹Π_g extension therefore adds no proxy-covered run by itself.
- **QA-5.** The promotion-rule question in §5.

**Reproduction.**
```
python docs/v2/question_a/build_question_a_brief.py --check     # rebuild question_a_brief.json from the pinned inputs
python -m pytest -q tests/test_v2_question_a_brief.py
```
