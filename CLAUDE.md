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

## Gate status (freeze criteria for "ABEP Physics Baseline 1.0")
| gate | status |
|---|---|
| 1 clean-install reproducibility | pass (frozen atmosphere; pinned deps; runs with pymsis absent) |
| 2 grid-life consistency | pass (optimiser degeneracy flagged; perveance-window tests) |
| 3 multi-point Hall validation | **FAIL** — P5 transport not identifiable from published data (TwoZoneBohm, ScaledGaussianBohm, 3-node MultiLogBohm; stopping rule 2026-09-25) |
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
1. P5 on **xenon** in HallThruster.jl (`cases/p5_xenon.json`, Brabston et al. JPP 2025 Table 4). **Do not tune anomalous
   transport yet** (project decision 2026-09-25); the Gaussian-B agreement is superseded. Order:
   a. Resolve P5 geometry: 32 mm (Brabston 2025) vs 38 mm (Peterson 2001, Hofer 2004) channel, and how the 2001 B(z) is
      registered, **from published sources only: no contact with authors or labs** (project decision 2026-09-25). Carry `L38-hist`, `L32-anode`, `L32-exit` as separate
      cases, rigid shifts only (`scripts/make_p5_xenon_cases.py`). At default transport all breathe and underpredict
      corrected I_d by 25–56 %; registration moves I_d ~30 %.
   Identification 2026-09-25 (`scripts/identify_p5_transport.py`, pre-registered grids, leave-one-out, all runs in
      `hallthruster_bridge/identification/`): TwoZoneBohm (783 runs) rejected; ScaledGaussianBohm (972) and 3-node
      MultiLogBohm (486) over 6 geometry × coil hypotheses also fail. **Stopping rule applied: published P5 information is
      insufficient to identify transport uniquely.** No closure frozen; geometry and coil shape undiscriminated. Every
      quiet solution overpredicts thrust by +2 to +4.5σ (untested candidate: no divergence correction in the 1-D thrust).
      Reopening P5 calibration needs a new pre-registered test of that item.
   b. (Superseded by the stopping rule unless reopened.) Calibrate transport as parameter identification: ONE TwoZoneBohm set (c₁, c₂, transition length) for all Xe
      points, fitted against I_d, thrust, anode and current efficiency and oscillation (RMS, peak-to-peak, frequency;
      the 50 % RMS flag is an internal diagnostic, not a criterion). Keep facility ingestion on. Hold one Xe point out as a
      blind test (more historical P5 Xe points if available).
   c. Freeze the Xe transport closure before N₂; run P5-N₂ with it unchanged first.
   Validation modes are never crossed: facility ingestion ON vs raw P_d/V_d, OFF vs Eq. (14)-corrected I_d. The driver
   runs both per case and prints them side by side.
   HallThruster.jl ingestion-units issue: drafted in `hallthruster_bridge/upstream/`, not filed; filing is the owner's call.
   Never move the HallThruster.jl pin automatically; an upgrade is a model change (`PINNED.toml` upgrade_policy).
2. N₂/N reaction set **v0.1: partial**. Add one provenance-backed table per commit. Complete the N₂/N reaction set with `abep_sim/rate_tables.py` from cited cross sections. Done: N ionisation
   (`ionization_N.dat`, Kim & Desclaux 2002 via NIST, `scripts/build_n_ionization_table.py`). Blocked on source access:
   N₂ dissociation (Cosby 1993 / Itikawa 2006), N₂ excitation, N elastic. LXCat's redistribution policy restricts
   commercial use, so the source choice is the project's decision (`hallthruster_bridge/propellants/PROVENANCE.md`).
3. P5 on N₂ (`cases/p5_n2.json`, Table 2) and ECHT on N₂ (`cases/echt_n2.json`) with ONE transport parameter set.
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
   with placeholders.
   Then generate frozen Hall maps (all fields in `hall_map.REQUIRED_FIELDS`), wire `archengine` Hall branch to `HallMap`,
   rerun the architecture trade and gate-4 UQ.
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
