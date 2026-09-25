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
| 3 multi-point Hall validation | **FAIL** — 0-D Hall model superseded; HallThruster.jl validation ladder not yet run |
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
1. P5 on **xenon** in HallThruster.jl (`cases/p5_xenon.json`, Brabston et al. JPP 2025 Table 4) — tests geometry, field,
   settings with no molecular chemistry. Rerun 2026-09-25 with measured B(z) (Peterson 2001, scaled to Table 4) and
   Eq. (13) facility ingestion: default TwoZoneBohm puts P5-Xe into a deep breathing mode (I_d RMS > 100 %, not a
   validation point). The earlier −13/−20/−4 % agreement came from the placeholder B. Next: decide the anomalous-transport
   treatment (step 8 of the plan); verify the 38 vs 32 mm anode offset in the field map. See docs/HISTORY.md.
2. Complete the N₂/N reaction set with `abep_sim/rate_tables.py` from cited LXCat cross sections: N ionisation, N₂
   dissociation (Cosby 1993 / Itikawa 2006), N₂ excitation, N elastic.
3. P5 on N₂ (`cases/p5_n2.json`, Table 2) and ECHT on N₂ (`cases/echt_n2.json`) with ONE transport parameter set.
   Blocked by the driver until every rate file in `propellants/n2_n.toml` exists. P5 B(z) shape is now available
   (`hallthruster_bridge/bfield/`, Peterson 2001; N₂ setpoints use 130 G). Still missing: ECHT B(z), B_max, per-point data.
4. Only if 1–3 succeed: O₂/O chemistry, then intake-delivered mixtures.
5. First define one versioned interchange schema (`hall_map_schema_v1`) that both `run_cases.jl` and `hall_map.py`
   validate against. Names don't match yet (driver `ion_current` vs `ion_current_A`; the driver lacks wall ion
   flux/energy, atomic-ion fraction, `sustained`). Never fill missing fields with placeholders.
   Then generate frozen Hall maps (all fields in `hall_map.REQUIRED_FIELDS`), wire `archengine` Hall branch to `HallMap`,
   rerun the architecture trade and gate-4 UQ.
6. Replace the remaining unverified Arrhenius rates (O, O₂, N ionisation; dissociation; excitation) in `plasma_chem.py`
   with cross-section tables — the N₂ fit was off by ~3×, expect similar errors elsewhere.

## Key modules
`atmosphere.py` (frozen NRLMSIS), `intake.py`/`intake_tpmc.py` (TPMC ROM, Maxwell + CLL), `compressor.py`, `reservoir.py`,
`plasma_chem.py` (global source model; T_e-parameterised solver), `plasma_devices.py` (0-D Hall — superseded; cathodes),
`archengine.py` (modular architecture engine, nested constrained search, energy ledger, mission envelope),
`mission_env.py`/`mission5.py` (J2 propagator, eclipse, arrays), `uq_modular.py` (paired UQ, Sobol), `golden.py`,
`convergence.py`, `validation.py`, `hall_map.py`, `rate_tables.py`, `hall1d.py` (sanity model only).
