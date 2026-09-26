# CLAUDE.md — working context for this repository

## What this is
ABEP-VLEO physics simulator for Vyovrinda Aerospace's DRDO TDF bid (RFP DTDF/06/13516/DSP/ABEP/X/L/M/01; bid close
05 Oct 2026). RFP envelope: 180–230 km, 12–25 mN, < 1.5 kW, < 40 kg, 26,000 h mission, > 15,000 h firing, Hall preferred,
air + Xe. Python owns the whole chain; HallThruster.jl (offline) owns Hall-discharge physics only.

## Rules (do not break these)
1. **Frozen data is the reference behaviour.** `abep_sim/data/atmosphere_msis21_v1.*`, `intake_surface_v1.*`,
   `golden_v1.json`, `rates/` carry hashes/provenance. Never regenerate them casually. Rebuild only on an intentional model
   change, via `python -m abep_sim.atmosphere build`, `python -m abep_sim.intake_tpmc build`, `python -m abep_sim.golden generate`,
   and record why in docs/HISTORY.md.
2. **Golden benchmarks must reproduce** (`python -m abep_sim.golden check` → OK). If a change moves them, it is a model
   change: justify it, regenerate, and log it.
3. **No silent fallbacks.** Atmosphere defaults to the frozen NRLMSIS dataset; live MSIS only when asked. Solvers must report
   non-convergence (`sustained=False`, `status=MODEL_ERROR/INFEASIBLE`), never return half-converged states.
4. **Conservation is a gate.** Source mass/power balances close exactly; architecture energy ledger residual < 2 %.
5. **Caches must be pure functions of their keys** (evaluate at the rounded key values).
6. **Cite data.** Every rate table, geometry and validation point needs a source in its file or PROVENANCE.md. Do not
   invent operating points or geometry. Mark anything from memory as "verify".
7. **HallThruster.jl is pinned** to v0.23.1, commit `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5`
   (`hallthruster_bridge/PINNED.toml`). Every Hall map must carry that commit; `abep_sim/hall_map.py` rejects others.
8. **No new propulsion families** until the physics baseline is frozen. Stabilise, don't expand.
9. Tests: `python -m pytest -q tests`. Expected: all pass, 5 skipped (superseded 0-D Hall calibration — do not "fix" them by
   re-tuning), 1 strict xfail (`test_v16_blind_validation_p5_nitrogen`, gate 3 — must turn green only via the new Hall solver).
10. **Published data are evidence, not immutable truth** (docs/EVIDENCE.md is part of these baseline rules). Preserve reported values and provenance, but
   distinguish measured, digitized, inferred, reconstructed, model-derived and assumed quantities. Each input carries
   source, uncertainty, applicability domain and validation status. Don't tune the simulator merely to force agreement
   with literature. Hardware validation supersedes literature-derived assumptions within the hardware's validated
   operating domain.

## Gate status (freeze criteria for "ABEP Physics Baseline 1.0")
| gate | status |
|---|---|
| 1 clean-install reproducibility | pass (frozen atmosphere; pinned deps; runs with pymsis absent) |
| 2 grid-life consistency | pass (optimiser degeneracy flagged; perveance-window tests) |
| 3 multi-point Hall validation | **FAIL** — P5-Xe closed: transport not identifiable. P5-N₂ v1 (pre-registered, no retuning, 1080 vacuum runs): **all 9 SGB candidates INCONCLUSIVE / NOT ELIGIBLE**, none PROMOTABLE; 66 % of run-readings OUT_OF_DOMAIN (chemistry T_e > 30 eV). Credible set stays ∅ |
| 4 cross-family mission UQ | done but **conditional on gate 3** (all absolute Hall numbers withdrawn) |
| 5 numerical convergence | pass |
| 6 golden benchmarks | pass (near-zero `ledger_resid` compared with an absolute tolerance, 2026-09-25) |

## Superseded / withdrawn (do not quote)
- All absolute Hall results from the 0-D closure (v1.2–v1.6): ABEP thrust, 2.5 kW closure, 110–120 kg, ECR+Hall
  P(success) 0.77 vs 0.63. Cause: N₂ ionisation fit was 2.2–3.2× low vs Itikawa 2006, and the Marchioni calibration used
  an invented geometry (true ECHT: 86 mm long, 10 mm wide, 100 mm OD).
- v1.3 Hall hysteresis / low-mode collapse (numerical artefact of an under-resolved T_e root scan).
- Probably robust (mechanism-level, independent of the Hall closure): grids life-limited by CEX + perveance window;
  magnetic nozzles excluded by energy per particle even at the energy bound; RF/helicon pre-ionisers add nothing.

## Next work (in order)
1. **P5-Xe identification campaign: CLOSED** (project decision 2026-09-25). Reopen only if genuinely new published
   information appears (e.g. the 2025 P5 channel depth, coil currents or measured B(z), per-point divergence or I_d traces).
   Record: `hallthruster_bridge/identification/`, docs/HISTORY.md. TwoZoneBohm rejected (no quiet regime); 3-node
   MultiLogBohm no advantage; ScaledGaussianBohm reproduces the quiet regime and thrust (via beam efficiency) but misses the
   pre-registered blind-I_d test at Xe2 (−15.56 % vs 15 %). **P5 transport is not uniquely identifiable; no closure is frozen.**
   Standing rules that still apply: published sources only, no contact with authors or labs; validation modes are never
   crossed; never move the HallThruster.jl pin automatically (`PINNED.toml` upgrade_policy); the ingestion-units issue is
   drafted in `hallthruster_bridge/upstream/`, and filing it is the owner's call.
   **Next phase: two-layer Hall uncertainty** (`hallthruster_bridge/ensemble/transport_ensemble_v0.json`,
   `abep_sim/hall_ensemble.py`; project decision 2026-09-26):
   - *Layer 1, calibration nuisance:* P5 registration (L38/L32-anode/L32-exit), historical coil shape (1.6/3.0 kW),
     beam-efficiency reading (A/B), facility-ingestion interpretation. This is uncertainty in what the P5 experiment WAS.
     It's marginalized when admitting closures and is **never** a Vyovrinda design variable, map axis or trade dimension.
   - *Layer 2, transferable:* the credible set of transport closures that survives marginalization. It's an
     **unweighted** scenario set (no probabilities) until evidence justifies elimination or weighting.
   - Flow: P5 evidence ensemble → credible closure set → Vyovrinda design-specific Hall maps (own geometry and B(z), one
     map set per member) → whole-system UQ reporting envelopes/robustness across members.
   - **Credible set = ∅** (project decision 2026-09-26). No in-sample I_d tolerance is used for admission: the
     pre-registered 15 % blind criterion was not met, and relaxing it post hoc would turn a failed validation into
     calibration. Super-Bohm (a > 1/16) sets are diagnostic/sensitivity cases only.
   - **Screening candidates ≠ admitted members.** Nine ScaledGaussianBohm sets (`screening_candidates`, ids
     `sgb-screen-01..09`) pass the no-cutoff screen: all runs succeed, a ≤ 1/16, quiet at all three Xe points,
     divergence-corrected thrust within 2σ under ≥ 1 layer-1 combination. The best is sgb-screen-01 (a = 1/16, b = 0.8,
     c = 0.9 L, w = 0.25 L; max |ΔI_d| 15.56 %). Support is L32-anode-dominated. Screening candidates never produce design
     Hall maps and never enter the architecture trade or UQ; `HallMap` loads admitted members only.
   - **Promotion rule:** a screening candidate becomes a member only after it predicts new evidence not used to select
     it, without retuning, within the physical prior (a ≤ 1/16). Before simulating that evidence, audit its measurements
     and uncertainties and pre-register the acceptance criteria. Next discriminator: P5-N₂.
   - **Scope:** this uncertainty belongs only to the ionization/discharge → acceleration/thrust block of the RFP
     architecture (atmospheric path: intake → filter → compressor → atmospheric gas chamber → valve; Xe path: Xe chamber
     → valve; both feed ionization/discharge → acceleration/thrust). It must never leak upstream into the intake,
     compressor, gas chambers or valves, or into Vyovrinda's own thruster geometry.
2. N₂/N reaction set **v0.1: partial**. Add one provenance-backed table per commit. Complete the N₂/N reaction set with `abep_sim/rate_tables.py` from cited cross sections. Done: N ionisation
   (`ionization_N.dat`, Kim & Desclaux 2002 via NIST, `scripts/build_n_ionization_table.py`); N₂ dissociation
   (`dissociation_N2.dat`, Song et al. JPCRD 2023 Table 9 = Cosby 1993, `scripts/build_n2_dissociation_table.py`); N₂
   ionization (`ionization_N2_song2023.dat`, Table 10 partial σ(N₂⁺)) and N₂ elastic momentum transfer
   (`elastic_N2_song2023.dat`, Table 5 MTCS) rebuilt; reaction set **abep-n2n-0.3**, versioned in `PINNED.toml` (the shipped
   tables are kept but unused). **abep-n2n-0.4:** dissociative ionization added (promoted by audit 1). It uses a threshold ramp from
   24.284 eV and a header of 24.284 eV. It has chemistry variants upper (`n2_n.toml`) / lower (`n2_n_di_lower.toml`) for the
   N⁺/N₂²⁺ ambiguity. Smoke-test case copies omit `measured`: no P5-N₂ comparison before pre-registration.
   **abep-n2n-0.5/0.6:** N `max_charge` = 2. N⁺ → N²⁺ comes from Bell et al. JPCRD 1983 Eq. (1); the solver needs this link to
   derive the N²⁺ energy, and it dominates N²⁺ production once n_N⁺/n_N₂ ≳ 0.4–8 %. Direct N₂ → N²⁺ + N comes from Table 10
   σ(N⁺⁺), with a ramp from 53.885 eV. Variant configs are regenerated by `scripts/make_n2_variant_configs.py`. Still to bound:
   N → N²⁺ direct, N²⁺ → N³⁺; molecular N₂²⁺ is unresolved.
   **Audit 2:** vibrational excitation → **PROMOTION ROBUST** (Laporta et al. 2014 Eq. (10) fits; `audit/n2_vibrational_excitation_v1.json`).
   The margin is large at low T_e with the presently completed denominator; reaction-set completeness remains pending.
   It dominates the inelastic loss at T_e ≤ 2 eV even with the electronic channels counted, and is > 1 % up to T_e ≈ 9 eV.
   v_f ≤ 10 carries 99.9 % of it (v_f = 1 only ~22 %). **abep-n2n-0.7:** included as v = 0 → v_f = 1…10, from Laporta's rate fits
   evaluated at T_e = ⅔ ε̄ (omitted v_f > 10 ≤ 0.145 % of vib power). Closure-limited: v = 0 only, no superelastic, resonant only.
   Project applicability is capped at the pre-registered domain, T_e ≤ 30 eV (45 eV mean energy); Laporta state no upper cutoff.
   This is source-model applicability, not experimental validation: 0→1 is cross-checked against JPCRD Table 7 (≤ 6 %), and the
   overtones are model-supported only. `chemistry_trustworthy` means "no numerical extrapolation outside the declared model domain",
   not "experimentally confirmed".
   **abep-n2n-0.8:** atomic-N momentum transfer from Ragimkhanov et al. EPJD 2026 (CC BY), vector-extracted from Fig. 1b (OPM curve;
   `propellants/sources/ragimkhanov2026_fig1b_mtcs.csv`). The Wang et al. 2014 BSR curve re-plotted in the same figure disagrees
   materially: OPM/Wang rate 0.36 at T_e 2 eV, 0.56 at 5, 0.74 at 10, 0.96 at 30. It is carried as variant `n2_n_nel_wang.toml`
   (plus `n2_n_di_lower_nel_wang.toml`), not resolved.
   **abep-n2n-0.9:** eight state-resolved electronic excitations: Su 2021 below 20 eV, Johnson 2005 Table 2 (owner-supplied TSV) from
   20 eV, and a power-law continuation above Johnson's last point (≤ 6.7 % of the rate at T_e = 30 eV). Headers are the experimental
   energies. The overlap disagreement Su/Johnson is 0.6–3.8 (step at 20 eV 0.84–2.13); a Johnson-below-20 alternative gives 0.80–0.94
   of the electronic power, recorded as uncertainty. **`n2_n.toml` is now file-complete** (26 reactions; full-set smoke run is
   chemistry-trustworthy). **Final audit pass** (`audit/n2_completeness_final_v1.json`): DI and vib final on the complete denominator; rotational gross
   1.13 % → **abep-n2n-0.10** adds j 0→2, 0→4 (JPCRD Table 6, NIST B₀ headers; marginal, gross convention, owner may reverse);
   N²⁺ → N³⁺ excluded (reference-state margin ~200); direct N → N²⁺ then unresolved-by-source (closed below).
   **Closure pass (owner decision 2026-09-26):** 0.10 rotational stays on (the pre-registered gross F_P; switching to net after seeing
   1.13 % would be post hoc). The generated `n2_n_rot_off.toml` is a lower-bound sensitivity branch (nominal DI + OPM N elastic × 9,
   expand only on trigger).
   **Tier-3 closure → abep-n2n-0.11, status `COMPLETE_FOR_P5_N2_VALIDATION`** (domain T_e 2–30 eV; vib/rot 0.2–30 eV; not a general
   completeness claim; **no further N₂ chemistry changes** unless P5-N₂ evidence forces one). Blind 5 × 9 × 4 = 180-run state envelope
   (measured targets removed; v4 authoritative, v3 = implementation cross-check, identical; prereg addenda 1 ambiguity rule, 2 cross-check
   rule), `audit/n2_closure_verdicts_v1.json`: direct N → N²⁺ (Hahn–Müller–Savin 2017) **PROMOTED** into nominal (F_S(N²⁺ production)
   63–85 % in every run; sensitivity `n2_n_ndd_hmslow/high.toml` ×0.5/×1.3); N²⁺ → N³⁺ **EXCLUDED** (F_ion ≤ 1.5e-6; its activity sits
   at T_e 19–26 eV, far below the 47.45 eV threshold, while N²⁺/N₂ peaks in cold 2–5 eV cells); N₂ → N₂²⁺ **UNCERTAINTY VARIANT**
   (nominal F_ion ≤ 0.39 % < 1 % < upper 2.6 %) as `n2_n_n2dication.toml` (N2 max_charge 2, both routes, on DI-lower); N₂⁺ → N₂²⁺
   excluded from nominal (F_ion ≤ 0.27 %), carried inside the variant. **Open for the P5-N₂ pre-registration:** in all runs of
   sgb-screen-02/03/04 (and 9 of 05) the 45-eV-capped tables (dissociation, electronic, vibrational, rotational) are used above their
   limit (T_e > 30 eV; ≤ 4.1 % of dissociation activity), so those runs are not `chemistry_trustworthy` and cannot be scored as is.
   **Historical audits read immutable snapshots** (`hallthruster_bridge/audit/configs/`, sha256-pinned with every rate table in
   `MANIFEST.json`; PR #25 review): the tier-2/3 final audit uses the 0.9 pre-rotation config, the closure envelope the four 0.10
   pre-HMS configs. Never evaluate an omitted process against a mutable production TOML that may already contain it.
   **P5-N₂ run statuses** (`prereg/p5_n2_run_status_rule_v1.json`, owner decision): PASS / FAIL_VALIDATION / OUT_OF_DOMAIN /
   NUMERICAL_FAILURE. Chemistry-untrustworthy ⇒ OUT_OF_DOMAIN (not scoreable, **not** FAIL). Admission needs scoreable runs at every
   point under the 4 primary chemistry configs; otherwise the candidate is INCONCLUSIVE / not eligible for promotion in this campaign
   (not rejected). Staged sensitivities (Johnson-low, rot-off, HMS low/high, N₂²⁺) are not mandatory. f_out = 0 is not relaxed.
   **P5-N₂ run design (owner decision):** primary 4 chemistry configs × 9 transports = 36 runs, plus the Johnson-low sensitivity
   branch (`n2_n_exc_johnsonlow.toml`: nominal DI + OPM N elastic) × 9 = +9. Expand Johnson-low to the other three chemistry
   combinations (+27, full 72) only if its escalation trigger fires. The trigger ("changes a pass/fail, the surviving set, or
   materially shifts an observable", with "materially" defined from the audited P5-N₂ uncertainties) is pre-registered
   with the P5-N₂ criteria before any run.
   **Completeness (project decision 2026-09-26):**
   "every file in n2_n.toml exists" ≠ "chemistry complete". `PINNED.toml` stayed INCOMPLETE until the omitted-process audit was done (now closed, 0.11):
   - Tier 1 (before P5-N₂ scoring): 8 N₂ excitation states, N momentum transfer.
   - Tier 2 (assess before calling the set complete): N₂ vibrational excitation, dissociative ionization.
   - Tier 3 (assessed/not included unless a bound says otherwise): rotational excitation, double ionization.
   **Pre-registered** (`hallthruster_bridge/prereg/n2_completeness_audit_v1.json`, frozen 2026-09-26 before any P5-N₂
   scoring). Domain: T_e 2–30 eV (mean energy 3–45 eV). Vibrational and rotational excitation: T_e 0.2–30 eV. Promote an
   omitted process if F_P > 1 % of total electron inelastic power, OR F_ion > 1 % of total positive-ion production, OR
   F_S_s > 5 % of any modeled species' production or destruction, anywhere in its domain. Denominators use the best
   available included set; results before the excitation and vibrational channels exist are **provisional**.
   **Provisional verdicts** (`hallthruster_bridge/audit/`, `scripts/audit_n2_dissociative_ionization.py`):
   - Dissociative ionization → **PROMOTE**, forced by F_ion (lower bound up to 25 %, > 1 % from T_e ≈ 4 eV), which does not
     depend on the incomplete excitation/vibrational power denominator. F_P (lower bound up to 24 %) is provisional and is
     recomputed once the set is complete.
     Also F_S(N₂ destruction) up to 14 %, and it dominates N⁺ production unless n_N/n_N₂ > 5 (at T_e 20 eV).
   - N⁺⁺ production (Table 10 σ(N⁺⁺), tier 3) → **crosses** F_ion 1 % at T_e ≥ 25 eV (≥ 19.5 eV if two ions per event).
   - N₂²⁺ is not tabulated (≈ 1 % of total ionization per JPCRD; no recommended values) → unresolved. Sources are open literature, not LXCat.
   Open: N₂ excitation (the recommended Su et al. 2021 per-state set ends at 20 eV, and the source for extending it above that is
   the owner's decision); N elastic (Ragimkhanov 2026 not yet located). See docs/HISTORY.md 2026-09-26 and
   `hallthruster_bridge/propellants/PROVENANCE.md`.
3. **P5-N₂ v1 vacuum campaign SCORED (2026-09-26)** — `hallthruster_bridge/validation/` (frozen raw dataset sha256 20e926d5…,
   scores, provenance, report, decision, `VALIDATION_RELEASE_v1.json`, all links verified). Result: no candidate PROMOTABLE; all nine
   INCONCLUSIVE / NOT ELIGIBLE; credible set ∅; no admission, no design Hall maps. Next (owner plan): O4 staged-sensitivity first stage
   (5 × 270 vacuum) and the 1080 facility runs as pre-registered; non-gating failure/OOD forensics; no retuning, no criteria change.
   **Critical path after v1 (owner decision 2026-09-26):** identify the OOD reactions → independent published evidence for a wider
   validity domain → pre-register an N₂ validation **v2** only if that evidence justifies it → rerun only what v2 requires → admit
   closure(s). In parallel: prepare the Hall-only vs RF+Hall vs ECR+Hall comparison on one common bus-power boundary. **Never extend a
   rate-table validity limit merely because the solver reached a higher T_e**; an extension needs independent published evidence
   and a new v2 pre-registration. **The v1 outcome stays INCONCLUSIVE permanently and is never rewritten.** The E×B diagnostic
   (V_a(N⁺) far below measured; ordering inverted in 0/648 runs) stays non-gating: it gets a physics-forensics lane (possible missing
   species-dependent acceleration / birth-location physics), never tuning. v1 OOD is driven by the 45 eV-capped family (dissociation,
   8 electronic, 2 rotational, 10 vibrational) firing together; 45 eV is the project's pre-registered completeness domain.
   Admission/Hall maps stay gated until the O4 dispositions are complete even if a later campaign yields PROMOTABLE: enforced by
   `hall_ensemble._check_o4` (admission records need `o4_dispositions_file`, `ensemble/o4_dispositions_schema_v1.json`; triggers are
   read from the scored O4 files). O4 datasets: `scripts/score_p5_n2_staged.py freeze|score` (pinned launch manifest gate, score once
   on mandatory + staged, mandatory scores reproduced exactly). Facility: the standard freeze/score pipeline in mode `facility`.
   **Decision milestones (owner decision 2026-09-26):** A = *conditional selection* ("architecture X is baseline provided conditions
   … are demonstrated"; does not need Physics Baseline 1.0); B = *physics-backed selection* (credible envelopes from validated Hall
   transport, chemistry and common-boundary performance); C = *proposal/PDR freeze* (mass, power, thermal, life, startup, cathode,
   mission closure integrated). Two tracks run in parallel and meet only when an admitted closure is needed for absolute performance:
   physics validation (v1 → OOD attribution → higher-energy evidence → v2 if justified → admission) and architecture comparison (common
   feed envelope → common Hall accelerator → RF/ECR interstage → common bus boundary → mass/thermal/life → same-condition comparison,
   break-even surfaces, hard-gate eliminations). **Fan-out rule:** whenever a lane finishes, immediately ask whether its result lets
   another lane start, removes a dependency, or creates a new parallel branch; never fall back to a sequential queue.
   **O4 first stage:** Johnson-low trigger FIRED (scored 2026-09-26) → its three pre-registered escalations are running.
   **Operating rules (owner decision 2026-09-26, after lanes 16–27 were launched):** no new broad lanes; every lane must answer one of
   (i) can an architecture be conditionally selected now, (ii) what evidence prevents physics-backed selection, (iii) what engineering
   issue could later overturn the choice. Results are reported in **milestone bundles**, not lane by lane (unless a dependency changes).
   Bundle 1 = *Architecture Conditional Selection* (lanes 7 RF, 8 ECR, 9 Hall sustainment, 16 feed envelope, 17 Hall reference,
   18 interstage, break-even, 20 PPU/magnets, + available hard gates 24) → first serious Hall-only vs RF+Hall vs ECR+Hall answer from
   inequalities and source-backed ranges (e.g. "RF+Hall is preferable only if it delivers ≥ X at ≤ Y W/A and ≥ Z interstage
   efficiency"), not absolute Hall predictions. Event triggers: 16+17 → grid; 7+18 → RF break-even overlay; 8+18 → ECR overlay;
   9+16 → direct-Hall sustainment envelope; 7+8+9+break-even → first conditional comparison; 20+cathode → full auxiliary bus-power
   comparison; 21+15 → mass/thermal/life veto layer; 24+26 → dossier; 25 → experimental decision package; N₂ domain audit → owner
   decides whether v2 is justified; all O4 first stages → O4 disposition matrix; Johnson-low escalations → does the excitation
   uncertainty survive across the other chemistry combinations; admitted closure → absolute grid + Hall maps + whole-system UQ.
   **Common comparison boundary (binding):** every architecture is reported with the same fields {ṁ_s, P_feed, T_feed, x_s, V_d, T,
   P_bus, m, Q_reject, life, startup, η_u, stability}, and P_bus is always the DC-bus input = discharge + pre-ionizer + cathode +
   magnets + PPU losses + gas path + controls/thermal (in `bus_power_boundary_v1` terms: Σ P_load/η over hall_discharge,
   rf_source|ecr_source(+ecr_magnet), cathode_keeper+cathode_heater, hall_magnet, flow_control+compressor, thermal_control+
   housekeeping; PPU loss = Σ P_load(1/η − 1)). Never compare absorbed RF power, ECR DC input and Hall discharge-only power.
   **v2 chemistry asks two separate questions:** is a wider energy domain source-supported (fixes OOD), and, within it, which
   electronic-excitation representation is justified (Johnson-low is a *material* model uncertainty: 221 triggers, status and
   verdict changes). Never make Johnson-low nominal merely because it changes results. **Execution provenance:** running score-bearing
   jobs are never altered; future campaigns record JULIA_NUM_THREADS / BLAS / OMP threads, Julia and HallThruster commit per run, so
   resource-induced failures stay distinguishable (observed environment of the follow-on runs:
   `hallthruster_bridge/validation/execution_environment/`).
   **P5-N₂ measurement audit: done** (`identification/p5_n2_measurement_audit_findings_v1.json`; values in
   `brabston_p5_n2_measurement_audit_v1.json` from `scripts/audit_p5_n2_measurements.py`). Targets: I_d and thrust at N1–N5,
   E×B species V_a at N1–N3, sustainment; Φ_m,n/η_SP,n/ξ_N are model-derived, not targets. Pre-registration decisions D1–D6 are
   decided (owner D1–D6, `prereg/p5_n2_validation_criteria_v1.json`, extinction addendum to the run-status rule); operational
   rules O1–O5 frozen; hash lock `prereg/p5_n2_prereg_lock_v1.json`; vacuum runs first. **No score-bearing run before the
   pre-registration PR merges.** `cases/p5_n2.json` regenerated
   (`scripts/make_p5_n2_cases.py`, 30 cases, sha256-pinned in the criteria).
   P5 on N₂ (`cases/p5_n2.json`, Table 2) and ECHT on N₂ (`cases/echt_n2.json`), run across the **credible Xe-informed
   transport screening set** (currently the 9 SGB screening candidates) with no retuning per case. N₂ is a
   discrimination experiment that can eliminate candidates or promote them to members. First audit the available N₂
   measurements and uncertainties, then pre-register the acceptance criteria, then simulate.
   Blocked by the driver until every rate file in `propellants/n2_n.toml` exists. P5 B(z) shape is now available
   (`hallthruster_bridge/bfield/`, Peterson 2001; N₂ setpoints use 130 G). Still missing: ECHT B(z), B_max, per-point data.
4. Only if 1–3 succeed: O₂/O chemistry, then intake-delivered mixtures.
5. Interchange schema `hallthruster_bridge/hall_map_schema_v1.json` is defined and shared (driver emits it, `hall_map.py`
   derives `REQUIRED_FIELDS` from it, a test checks both). All fields now have producers: wall ion flux/energy are
   re-evaluated from the solver's WallSheath Bohm-flux model (`bridge_lib.jl`, checked against the solver's own
   `nu_wall` by `checks/wall_flux_consistency.jl`). With `ion_wall_losses=false` that flux is not removed from the ion
   fluid (`wall_ion_basis` says so). `map_ready` = schema-complete only. Erosion/lifetime use requires
   `wall_life_trustworthy` (converged ∧ sustained ∧ `ion_wall_losses=true` ∧ WallSheath, unshielded), which `HallMap`
   reports separately from performance `trustworthy`; map meta must carry `ion_wall_losses`. Never fill missing fields
   with placeholders. **No silent chemistry extrapolation:** every rate file has an entry in
   `propellants/rate_validity.toml` (missing = driver error): `verified` with a mean-energy limit, or `unresolved`.
   A run is `chemistry_trustworthy` only if no file is unresolved and, for every reaction, the activity
   n_e·n_target·k_r(3/2 T_e) summed over every saved frame and cell has zero share (≤ 1e-12) beyond its limit
   (reaction-weighted, per frame; `checks/chemistry_validity_check.jl`). Limits: dissociation_N2 45 eV,
   ionization_N, ionization_N2_song2023 and elastic_N2_song2023 255 eV. The unused HallThruster-shipped N₂ tables stay
   `unresolved`. `chemistry_trustworthy` certifies the validity of the tables used, not completeness; the driver enforces
   completeness separately (it refuses `n2_n.toml` while a listed file is missing). `HallMap` performance `trustworthy` requires it; N₂ validation
   scoring must too. No reaction-contribution allowance until one is pre-registered.
   Then generate frozen Hall maps (all fields in `hall_map.REQUIRED_FIELDS`), one set per ensemble member, each carrying
   `meta.ensemble_member_id`. Wire the `archengine` Hall branch to `HallMap`, and rerun the architecture trade and gate-4
   UQ across members (envelopes, not one deterministic answer).
6. Replace the remaining unverified Arrhenius rates (O, O₂, N ionisation; dissociation; excitation) in `plasma_chem.py`
   with cross-section tables. The N₂ fit was off by ~3× and the N fit is ~2× below `ionization_N.dat` at T_e = 10 eV.
   The HallThruster.jl tables (`hallthruster_bridge/propellants/`) and the 0-D chemistry are **not unified**; wiring a
   table into `plasma_chem` is a model change (goldens move, log it).

## Key modules
`atmosphere.py` (frozen NRLMSIS), `intake.py`/`intake_tpmc.py` (TPMC ROM, Maxwell + CLL), `compressor.py`, `reservoir.py`,
`plasma_chem.py` (global source model; T_e-parameterised solver), `plasma_devices.py` (0-D Hall — superseded; cathodes),
`archengine.py` (modular architecture engine, nested constrained search, energy ledger, mission envelope),
`mission_env.py`/`mission5.py` (J2 propagator, eclipse, arrays), `uq_modular.py` (paired UQ, Sobol), `golden.py`,
`convergence.py`, `validation.py`, `hall_map.py`, `rate_tables.py`, `hall1d.py` (sanity model only).
