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
| 3 multi-point Hall validation | **FAIL** — P5-Xe closed: transport not identifiable; credible set ∅, 9 SGB screening candidates await no-retuning N₂ prediction |
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
   tables are kept but unused). **Completeness (project decision 2026-09-26):**
   "every file in n2_n.toml exists" ≠ "chemistry complete". `PINNED.toml` stays INCOMPLETE until an omitted-process audit is done:
   - Tier 1 (before P5-N₂ scoring): 8 N₂ excitation states, N momentum transfer.
   - Tier 2 (assess before calling the set complete): N₂ vibrational excitation, dissociative ionization.
   - Tier 3 (assessed/not included unless a bound says otherwise): rotational excitation, double ionization.
   Every omitted process gets a quantitative bound on its maximum share of electron energy loss P_e and of species
   production/destruction S_s over the intended T_e range. Any exceeding a threshold (e.g. 1–2 %) is promoted into the
   model. That threshold is **pre-registered before any P5-N₂ fit quality is seen**. Sources are open literature, not LXCat.
   Open: N₂ excitation (the recommended Su et al. 2021 per-state set ends at 20 eV, and the source for extending it above that is
   the owner's decision); N elastic (Ragimkhanov 2026 not yet located). See docs/HISTORY.md 2026-09-26 and
   `hallthruster_bridge/propellants/PROVENANCE.md`.
3. P5 on N₂ (`cases/p5_n2.json`, Table 2) and ECHT on N₂ (`cases/echt_n2.json`), run across the **credible Xe-informed
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
