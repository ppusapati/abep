# NP-HALL-PARAMETRIC-ENVELOPE addendum A9-LP: minimal local Hall AIR package (A9.39 item 4)

`prereg_addendum_a9_local_air_rp1_v1.json` is authoritative; this page restates it.

- Status **PREREGISTERED_NOT_RUN**, label **PARAMETRIC / NOT_VALIDATED / INFORMATION_ONLY**.
- Registered 2026-10-09 on `8060e55`, before any Hall run on the FE-derived field (DCR-DBF1-002 approval condition).
- Lock: `prereg_addendum_a9_local_air_rp1_lock_v1.json`.
- v1, A1..A8 and every committed record are unchanged. "A9-LP" is not one of the A9.xx owner decisions.

## What it is

One small package, `tools/local_runs/hall_air_rp1_v1/`, that the owner runs on their own machine with one command. It
writes one result file. It is a preliminary AIR operating map of RP-1 (DBF-1.1, FE-derived H1 B(z)), not a campaign.

## Cases (10 cases, 20 runs)

| id | ṁ [mg/s] | composition | V_d [V] | B | transport |
|---|---|---|---|---|---|
| C01 | 0.2 | CP-YLO-REC | 350 | BP-LO | sgb-screen-01 |
| C02 | 0.2 | CP-YHI-DIS | 265 | BP-LO | sgb-screen-01 |
| C03 | 0.5 | CP-YLO-REC | 265 | BP-HI | sgb-screen-01 |
| C04 | 0.5 | CP-YHI-DIS | 350 | BP-HI | sgb-screen-01 |
| C05 | 1.0 | CP-YLO-REC | 350 | BP-LO | sgb-screen-01 |
| C06 | 1.0 | CP-YHI-DIS | 350 | BP-HI | sgb-screen-01 |
| C07 | 2.0 | CP-YLO-REC | 265 | BP-HI | sgb-screen-01 |
| C08 | 2.0 | CP-YHI-DIS | 265 | BP-LO | sgb-screen-01 |
| C09 | 1.0 | CP-YLO-REC | 350 | BP-LO | sgb-screen-04 |
| C10 | 1.0 | CP-YHI-DIS | 350 | BP-HI | sgb-screen-04 |

Selection rules:
- **SR-1 composition.** The two registered NP-HALL-CHEM-AIR corners that bracket the O-nuclei share of the frozen
  196-state design set: CP-YLO-REC (y_O 0.079, molecular) and CP-YHI-DIS (y_O 0.840, f_O 0.990). Corners are not
  interior bounds.
- **SR-2 V_d.** The two upper registered v1 levels, 265 and 350 V (inside DBF1-H1-05).
- **SR-3 B.** DBF1-BZ-03 levels BP-LO 69.93 G and BP-HI 268.6 G, nominal FE shape BZ-H1FE-V1. The coil operating point
  is the FE solution's NI_total (153.7 / 587.1 A-turns).
- **SR-4 flow.** 0.2, 0.5 and 1.0 mg/s cover the conservation requirement (A4: 0.048 / 0.208 mg/s at 12 / 25 mN for a
  lossless thruster at 1500 W). 2.0 mg/s is the one higher level. Inlet NI-01.
- **SR-5 transport.** sgb-screen-01 and sgb-screen-04, opposite corners of the screening box in barrier, centre and width.
  Neither is admitted (credible set ∅). sgb-screen-01 carries the map; sgb-screen-04 replicates the 1.0 mg/s rows.
- **SR-6 design.** Half fraction of composition × V_d × B (I = comp·V_d·B). Each flow level gets two rows with both
  compositions, and each row appears twice.

No N2_PROXY substitution. AIR chemistry is abep-air-0.7 on the LP-BOUNDED path (BV-AIR-LL-NOM), with the label
BOUNDED_ONE_SIDED_LOWER_ELECTRON_IMPACT_LOSS_NOT_COMPLETE.

## Method

- **Numerics and observables: A7, unchanged.**
  - Production A7-P: 0.25 mm cells. Check A7-C: 0.125 mm.
  - Duration 13.54 ms. The window runs from 3.38 ms, with 4000 frames.
  - Thrust and I_d are true time-means of the per-frame values, with batch-means SE and half-window means.
- **Physics:** the Config of `air_bridge_lib.jl run_case_air`.
- **Status.** NUMERICAL_FAILURE > EXTINCT > OUT_OF_DOMAIN > NOT_SUSTAINED > NON_STATIONARY > STATISTICALLY_UNRESOLVED
  > PASS.
  - EXTINCT uses the AIR feed in place of Xe.
  - OUT_OF_DOMAIN is the A1 rule DOM-AIR-01 / 02.
  - Numbers are reported for every status, labelled.
- **Convergence:** A7 (C-STATUS, C-QUIET, C-T, C-ID).
- **Efficiency.** η_a = T² / (2 ṁ V_d I_d) from the time-means. Total efficiency is NOT_EVALUATED: it needs the
  non-discharge loads of `bus_power_boundary_a9_v2`.

## Execution

The owner runs the package. Before hand-over it is run once in the authoring container on the registered subset C02,
C05, C06 (both levels). That output is committed as a host-labelled reference and is never merged with the owner's
results.

## Not

- Not measured or demonstrated H1 performance; the EM verifies that.
- Not a closure, selection or non-closure.
- Not a validation.
- Never pooled with surrogate-B(z) records.
