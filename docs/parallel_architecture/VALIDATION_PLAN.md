# Validation plan (v2)

## What each layer can claim

| Layer | Evidence status | May be score-bearing? |
|---|---|---|
| contracts, router, bus ledger, Xe ledger, BOM | exact bookkeeping identities (catch contract and rounding errors, not physics) | n/a (no physics) |
| reduced RF model | model-derived, UNVALIDATED | **never** |
| admitted RF map | measured or admitted external data | yes, inside its domain only |
| Hall transport closure | credible set = ∅ | no (refused in every use) |
| Hall point evidence | measured Vyovrinda (admitted) / analog | admitted Vyovrinda only |
| golden_parallel_v1 | software regression | not validation |

## High-fidelity external data (§32)

External DSMC (PICLas or equivalent), electromagnetic, PIC-MCC magnetic-nozzle and HallThruster.jl solves follow
one pipeline:
- external solve → immutable export → sha256 → schema validation → registry → response map → admission → system
  simulation.

The interfaces that exist today are `rf_reduced.RFCouplingRecord`, `rf_registry` and `propellant_router.flow_regime`.
No new solver is written.

## First scientific deliverables (§45): prerequisites, not fabricated

The spec's surfaces cannot be produced honestly yet:
- the RF atmospheric envelope;
- the Hall-Xe boost envelope;
- the power-sharing surface at fixed total power;
- the Xe duty-cycle surface;
- the installed-mass comparison;
- mission coverage.

The code computes each of them once its inputs exist:

| Surface | Needs |
|---|---|
| RF envelope | RF chamber geometry, η_bus→feed, η_antenna, γ, R_m, B0, and detachment/divergence evidence. The reduced model can map hypotheses only after these are supplied as evidence or as labelled ASSUMED_SCREENING_VALUE inputs. |
| Hall-Xe boost | Measured H1-Hall points, or labelled analog points (planning only). |
| Power sharing / coverage | Both of the above, plus common-component loads (the compressor is still TBD: C1 lacks primary evidence). |
| Xe duty cycle | Mission mode history (from a supplied policy); start-up Xe per start (TBD until C-1/H-1 measure it). |
| Installed mass | Sourced or labelled screening CBEs for every BOM item. |

Stop rule: where a coefficient has no defensible source, v2 stops and reports. It does not invent one (spec §44).
