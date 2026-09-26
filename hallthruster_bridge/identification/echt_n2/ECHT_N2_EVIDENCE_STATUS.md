# ECHT-N2 evidence status (2026-09-26)

**Status: `HISTORICAL_UNSUPPORTED`. Not score-bearing. Not a transport discriminator.**

The machine-readable form is `STATUS.json` in this directory. The basis is the completed evidence audit
`echt_n2_evidence_audit_v1.json`, pinned by sha256 in `STATUS.json`, with its README. This note records a disposition.
Nothing was simulated, scored or retuned to produce it.

## Why
- Only one open source has per-point data: F. Marchioni's MSc thesis (Politecnico di Torino / Stanford, 2020,
  https://webthesis.biblio.polito.it/14618/, CC BY-NC-ND 3.0). The JAP paper (Marchioni & Cappelli, J. Appl. Phys. 130,
  053306, 2021, doi:10.1063/5.0048283) is paywalled. We read only its abstract, via Crossref, and the abstract gives
  ranges only. (Audit finding E1.)
- The thesis has data at 180/200/220 V only: 13 I_d points and 7 thrust runs at 2.06 mg/s N2. Nothing is published
  above 220 V. (E2.)
- The published B(z) is a flat plateau at about 4.7-8.6 cm. The Gaussian peaked at the exit plane in
  `cases/echt_n2.json` contradicts it. B was measured at one coil current only (2 A), and the quoted "130 G" is the FEMM
  value at 3 A. (E3.)
- Scoring would need eleven forced assumptions (A1-A11): channel radii, anode position and B(z) origin, B per run, plume
  B, the argon cathode flow, facility and ingestion, the thrust reduction reading, divergence, anode flow, BN grade, and
  the unstable runs. (E4-E8.)

The problem is observability, not independence. ECHT is independent of the P5-Xe selection. The open record does not
allow the experiment to be reconstructed without these forced assumptions.

## What ECHT-N2 can be used for
- **At most, a supporting check pre-registered before any ECHT simulation.** It would cover sustainment at 180-220 V and
  2.06 mg/s, the I_d magnitude and its decrease with coil current, and a thrust of about 20-23 mN. A1-A11 are carried
  as declared layer-1 nuisance. Such a check never decides a promotion or an elimination on its own.
  **No such check is pre-registered.** Creating one is an owner decision.
- Context: the published operating envelope (180-220 V, 2.06 mg/s N2), quoted with its evidence class.

## What it cannot be used for
- A transport discriminator. It cannot promote, eliminate or rank screening candidates or admitted members.
- Any score-bearing validation result or gate-3 verdict.
- Tuning or retuning of transport, chemistry or boundary conditions.
- Replacement simulation cases. None were created, and none may be created under this status.
- The 225-275 V points or the 250 V anchor as evidence of ECHT behaviour.

## Historical artifacts (kept, not deleted)
| artifact | unsupported content | handling |
|---|---|---|
| `hallthruster_bridge/cases/echt_n2.json` | V_d 225/250/275 V (no source); exit-peaked Gaussian B(z), `B_max_T` null; no coil current per case | top-level `status: HISTORICAL_UNSUPPORTED`, `status_basis`, `score_bearing: false`; content otherwise unchanged. `run_cases.jl` refuses the file unless `ABEP_ALLOW_HISTORICAL=1`. When allowed, every result record, summary row and the meta carry `score_bearing: false` |
| `abep_sim/validation.py` CAL / `calibration_anchor()` (250 V, 2 mg/s) and the "250 V → 24 mN, 690 W, 1230 s" record in `docs/HISTORY.md` | no open source. The JAP abstract gives ranges only (500-800 W anode, 17-22 mN, 1000-1100 s, 14-18 %). The open thesis has no 250 V data | documentation only (module and function docstrings, `CAL_ANCHOR_PROVENANCE`). No value or behaviour changed, so golden benchmarks are unaffected. Verify against the JAP full text only if it becomes legitimately accessible |

## Evidence classes (summary; full list in `STATUS.json` `items`)
| quantity | level | type |
|---|---|---|
| I_d, Table 6.1 (13 points, 2 s.f.) | 3 | measured (tabulated) |
| thrust, Tables 6.2/6.3 (one-side 20.62-23.41 mN; averaged 17.29-21.31 mN) | 3 | measured, reduced by the author; ± from the calibration fit only |
| centreline B(z) at 2 A (plateau 85.3 G) | 3 | digitized (of measured) |
| FEMM B(z) at 1.5-3 A; "130 G" | 3 | model-derived (+ digitized) |
| length 86 mm, channel height 10 mm, "100 mm OD" of the BN chamber | 3 | measured (design dimension) |
| radii 40/50 mm | 3 | inferred (reading A of A1; verify) |
| facility pressure 8.1e-5 to 2.2e-4 Torr | 3 | measured (ion gauge; no published correction) |
| ingestion 2-6 % of anode flow | 6 | inferred (order of magnitude) |
| plume divergence, species, E×B | none | missing: TBD, requires plume data that no open source publishes |
| JAP abstract ranges | 3 | measured (author-reported ranges; abstract only) |
| `cases/echt_n2.json` 225-275 V and Gaussian B | 7 | assumed (no source; B shape contradicted) |
| 250 V → 24 mN, 690 W anchor | 7 | assumed (unverified; no open source) |

## Reopen only if
Genuinely new published information becomes legitimately available. That means the JAP full text through library access
or an openly licensed copy (radii, anode or cathode position, thrust uncertainty, any 250 V data), or a new open ECHT
measurement paper. The standing rules still apply: published sources only, no contact with authors or labs, no paywall
bypass.

## Owner follow-up (outside this change)
- `CLAUDE.md` "Next work" item 3 still lists ECHT on N2 (`cases/echt_n2.json`) as a discrimination run.
- Add a `docs/HISTORY.md` entry for this disposition.
- The COUPLED_* calibration comment in `abep_sim/plasma_devices.py` refers to the same 250 V anchor (left unchanged).
- The `ECHT` dict in `abep_sim/hall1d.py` (r_in 0.040, r_out 0.050) is reading A of A1. It is a sanity model only and
  was left unchanged.
