# ABEP-VLEO simulator (Vyovrinda Aerospace)

Physics simulator for Air-Breathing Electric Propulsion in very low Earth orbit (180–230 km), built for the
DRDO TDF ABEP bid (RFP DTDF/06/13516). Python is authoritative for the full chain (atmosphere → intake → compressor →
reservoir → ionisation → accelerator → power/thermal/mass/life → spacecraft drag → 26,000 h mission → UQ/optimisation).
HallThruster.jl (UM PEPL, MIT) is the authoritative Hall-discharge solver, run offline to produce frozen response maps.

**Status: Python Physics Candidate — NOT a frozen baseline.** See `CLAUDE.md` for the gate status, the rules for working
in this repository, and what is superseded. Full change history: `docs/HISTORY.md`.

## Quick start
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-lock.txt && pip install -e .
python -m pytest -q tests          # ~80 s; expect: all pass, 5 skipped (superseded), 1 xfailed (gate 3)
python -m abep_sim.golden check    # golden benchmarks (stage-by-stage) reproduce to 1e-6
```

## Hall solver (optional, needs Julia >= 1.10)
```bash
julia hallthruster_bridge/setup.jl                                   # pins HallThruster.jl v0.23.1 (commit bfb3019)
mkdir -p hallthruster_bridge/out
julia --project=hallthruster_bridge hallthruster_bridge/run_cases.jl \
      hallthruster_bridge/cases/p5_xenon.json hallthruster_bridge/out/p5_xenon.json
```

## Layout
| path | contents |
|---|---|
| `abep_sim/` | the simulator package |
| `abep_sim/data/` | frozen, hashed reference data: NRLMSIS 2.1 atmosphere, TPMC intake surface, golden benchmarks, cited rate tables |
| `tests/` | test suite (includes golden reproduction and recorded validation failure) |
| `hallthruster_bridge/` | pinned HallThruster.jl setup, driver, N₂/N propellant config, validation cases |
| `scripts/` | install-and-test helper |
| `docs/HISTORY.md` | full version history v0.1 → v1.7-candidate, every finding and withdrawal |
