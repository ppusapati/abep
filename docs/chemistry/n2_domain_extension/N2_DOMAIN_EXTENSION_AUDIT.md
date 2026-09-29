# N₂ high-T_e domain-extension evidence audit (lane DOMX)

**Status: DRAFT_PENDING_OWNER.** Non-gating. Date 2026-09-26.

**The P5-N₂ v1 outcome is permanent and is not rewritten here.** In the pre-registered vacuum validation, all nine SGB screening
candidates are INCONCLUSIVE / NOT ELIGIBLE, the credible set is empty, and gate 3 is FAIL. This audit scores nothing, re-scores
nothing and re-labels no run. It changes no rate table, validity limit, criterion or tolerance, and nothing under
`hallthruster_bridge/{prereg,propellants,audit,validation,campaign,cases,ensemble}` is touched. Official run statuses are read
from `hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores.json`.

| file | content |
|---|---|
| `domain_extension_requirements.json` | every computed number (v1 inventory, hypothetical coverage, requirements, independent comparisons, criteria, draft proposals, completeness indicators) |
| `domain_extension_audit.json` | per-table audit and verdicts. Every number there is stored as `{value, from}`, a path into the requirements JSON. |
| `sources/song2023_fig19_vector_extract.csv` | vector paths extracted from Song et al. 2023 Fig. 19 (dissociation), with provenance header |
| `drafts/p5_n2_validation_v2_prereg_OUTLINE_DRAFT.md` | outline of what a v2 would change (DRAFT_PENDING_OWNER, deliberately not under `hallthruster_bridge/prereg/`) |
| `scripts/chemistry/n2_domain_extension_requirements.py` | produces the requirements JSON (`--check` reproduces it; `--extract-fig19 <pdf>` rebuilds the CSV) |
| `tests/test_n2_domain_extension_audit.py` | consistency tests |

## 1. Bottom line

1. **What makes v1 runs OUT_OF_DOMAIN.** Only the 21 tables capped at 45 eV mean energy (T_e = 30 eV) are ever beyond their
   limit. `dissociation_N2.dat` is beyond it in all 714 OUT_OF_DOMAIN runs, and in 36 of them it is the only table beyond. No
   table with a 255 eV limit is exceeded. The time-averaged `Te_max_eV` of every OOD run is at most 25.2 eV, so every
   exceedance happens in instantaneous saved frames. The highest active mean energy in any OOD run is 127.9 eV (T_e 85 eV).
2. **Only one table has an evidence-supported extension: `dissociation_N2.dat` to 60 eV (DRAFT).**
   - The support is a measurement-based set plus two evaluated sets, all read from the vector Fig. 19 of Song et al. 2023. The
     measurement-based set is the Winters 1966 neutral points to 296 eV, reconstructed from measured data.
   - None of the three is independent of Table 9 at the 200 eV join. Cosby's recommended set averages Cosby's and Winters'
     data, and Majeed & Strickland used Cosby. The independent content is the part above 200 eV. For Winters that is two
     points, at about 246 and 296 eV. Whether that suffices is owner decision 12.
   - `excitation_N2_a1Pi_g.dat` is **PARTIAL**. Its evaluated coverage (Majeed & Strickland 1997, to 1 keV) agrees with the
     table, but measured coverage ends at 200 eV.
   - The other seven electronic tables are **UNRESOLVED-BY-SOURCE**. The only accessible independent set disagrees with
     Johnson 2005 at the 100 eV join beyond Johnson's stated uncertainty.
   - Both rotational tables are **UNRESOLVED-BY-SOURCE** (no data above 10 eV).
   - The ten vibrational tables are **PARTIAL**. The resonant content has no tail problem, but a non-resonant 0→1 component
     that the table omits is 2–3× the table's rate at T_e 30–60 eV.
3. **Extending limits alone recovers almost none of the v1 OOD runs.** This is a hypothetical proxy count, not scoring:
   - All 21 tables at L = 60 / 75 / 90 / 120 / 150 eV would newly cover 211 / 423 / 609 / 710 / 714 of the 714 OOD runs.
   - Leaving dissociation at 45 eV covers 0 at every L. Leaving rotational at 45 eV covers at most 37, electronic at most
     40, vibrational at most 171.
   - The evidence-supported draft (dissociation to 60 eV only) covers 6. The evaluated reading (dissociation 75, a¹Π_g 150)
     covers 22.
4. **What would be needed instead.** A v2 would need new evidence (rotational above 10 eV, electronic above 100 eV), owner
   model decisions (non-resonant vibration, rotational envelope), and an extended-domain completeness re-audit. The re-audit
   may itself add processes (N²⁺ → N³⁺, N₂²⁺, higher states). Every one of these is an owner decision (§9). v1 stays
   INCONCLUSIVE whatever is decided.

## 2. Inputs and conventions

- **Frozen data.** `validation/p5_n2_campaign_v1_vacuum_raw.jsonl.gz` (1080 records; sha256 of the gz 5b11705c…, which matches
  the manifest's `sha256_gz`). `…_vacuum_scores.json` (2160 run × reading evaluations: OUT_OF_DOMAIN 1428, FAIL_VALIDATION 700,
  PASS 32). `propellants/rate_validity.toml` (limits and basis strings, read and asserted).
- **Rate convention.**
  - HallThruster.jl v0.23.1 looks each rate up at `3/2 * Tev` (`src/collisions/collision_frequencies.jl`). It interpolates the
    table onto a 0–255 eV mean-energy grid (`reactions.jl`, `load_rate_coeff_file`).
  - The tables are Maxwellian rates `k(T_e) = sqrt(8/(π m_e)) (e T_e)^-3/2 ∫σ E e^(-E/T_e) dE` (`abep_sim/rate_tables.py`).
  - Laporta fits are evaluated at T_e = ⅔ ε̄ (`scripts/build_n2_vibrational_tables.py`).
  - The script rebuilds each capped table's cross-section model from the build scripts and reproduces the committed rate
    tables to ≤ 4×10⁻⁵ relative (`model_rate_over_committed_table_minus_1`).
- **f_out** (bridge_lib.jl `chemistry_activity`) is the share of n_e·n_target·k_r·dz, summed over all saved frames and cells,
  at 3/2 T_e above the limit. A run is OOD if any f_out > 10⁻¹².
- **`max_mean_energy_active_eV`** is the highest mean energy at which a cell-frame carries more than 10⁻¹² of that table's
  peak activity. It is the only per-table energy in the frozen records.
- **The coverage counts in §5 are therefore a proxy.** A run counts as covered at L if every capped table either had
  f_out ≤ 10⁻¹² in v1 or has `max_mean_energy_active_eV` ≤ L. This is neither the scoring predicate nor exact: 175 in-domain
  v1 runs have `max_mean_energy_active_eV` > 45 eV at a share ≤ 10⁻¹². An exact count needs reruns, because the frames are
  not in the frozen record.

## 3. v1 inventory: tables beyond their limit (frozen records)

| table | family | OOD runs beyond 45 eV | eps_active p50 / p90 / max (eV) | max f_out |
|---|---|---|---|---|
| `dissociation_N2.dat` | dissociation | 714 | 71.1 / 94.1 / 127.9 | 0.0462 |
| `excitation_N2_A3Sigma_u.dat` | electronic | 636 | 68.6 / 92.9 / 127.9 | 0.017 |
| `excitation_N2_B3Pi_g.dat` | electronic | 633 | 68.5 / 92.9 / 127.9 | 0.016 |
| `excitation_N2_Bprime3Sigma_u.dat` | electronic | 651 | 69.0 / 92.9 / 127.9 | 0.0192 |
| `excitation_N2_C3Pi_u.dat` | electronic | 642 | 68.6 / 92.9 / 127.9 | 0.0178 |
| `excitation_N2_W3Delta_u.dat` | electronic | 641 | 68.6 / 92.9 / 127.9 | 0.0176 |
| `excitation_N2_a1Pi_g.dat` | electronic | 674 | 70.0 / 93.1 / 127.9 | 0.0273 |
| `excitation_N2_aprime1Sigma_u.dat` | electronic | 655 | 69.0 / 92.9 / 127.9 | 0.0202 |
| `excitation_N2_w1Delta_u.dat` | electronic | 659 | 69.5 / 93.0 / 127.9 | 0.0214 |
| `excitation_N2_rot_j0_to_j2.dat` | rotational | 677 | 70.2 / 93.1 / 127.9 | 0.03 |
| `excitation_N2_rot_j0_to_j4.dat` | rotational | 659 | 69.9 / 93.3 / 127.9 | 0.0252 |
| `excitation_N2_vib_0_to_1.dat` … `_4.dat` | vibrational | 537 each | 65.4 / 91.0 / 127.9 | 0.00474 |
| `excitation_N2_vib_0_to_5.dat`, `_6.dat` | vibrational | 539 each | 65.7 / 91.3 / 127.9 | 0.00481 |
| `excitation_N2_vib_0_to_7.dat` | vibrational | 540 | 65.8 / 91.7 / 127.9 | 0.00489 |
| `excitation_N2_vib_0_to_8.dat`, `_9.dat` | vibrational | 541 each | 66.2 / 91.6 / 127.9 | 0.00498 |
| `excitation_N2_vib_0_to_10.dat` | vibrational | 543 | 66.2 / 92.0 / 127.9 | 0.00507 |

The Johnson-low variant tables (`*_johnsonlow.dat`) are not in the v1 mandatory records. They share the nominal tables'
continuation above Johnson's last point, so the electronic verdicts below apply to them unchanged.

## 4. (a) What each source actually covers, and how the tables go beyond it

| table(s) | current limit and basis (rate_validity.toml) | cited source(s) and actual coverage | construction above the source |
|---|---|---|---|
| dissociation | 45 eV. Held tail < 1 % at 45 eV (0.95 %) | Song et al. JPCRD 2023 Table 9, 12–200 eV. This is the recommended Cosby set, a weighted average with Winters 1966, ±20 % [evaluated, transcribed]. Cosby measured 18.5–148.5 eV and recommends 10–200 eV [abstract]; Fig. 19 draws his error bars only to 150 eV (±17–26 % at 50–150 eV). Winters measured total dissociation 0–300 eV [abstract]. | σ held at 0.95×10⁻¹⁶ cm² above 200 eV; fixed 12.14 eV loss |
| A, B, W, B′, a′, w, C | 45 eV. Declared model, capped at the pre-registered T_e ≤ 30 eV | Su et al. 2021, 0.01–20 eV [model-derived, CC BY data in repo]. Johnson et al. 2005 Table 2, 10–100 eV [measured; abstract confirms the range] | power law from Johnson's last two points to 10 keV (p 2.23–2.87 for the triplets; a′ 1.67, w 0.53), zero beyond |
| a¹Π_g | as above | Su 2021 to 20 eV; Johnson 2005 to **200 eV** (new DCS at 200 eV) | power law p = 1.07 above 200 eV |
| rotational j 0→2, 0→4 | 45 eV. Declared model, capped | Song 2023 Table 6, 0.01–10 eV. This is Song's own R-matrix SEP calculation, and σ(0→2) is still rising at 10 eV [model-derived] | σ held at the 10 eV value |
| vibrational 0→1…10 | 45 eV. Source-model applicability, capped | Laporta et al. 2014 Eq. (10) fits of resonant (²Π_g) rates. Their rate integrals run to 15 eV ("negligible beyond 15 eV", Sec. III), and no temperature range is stated [model-derived; arXiv full text]. Only 0→1 is cross-checked against Song Table 7 (1.00–5.00 eV) | none for the resonant part; non-resonant excitation is absent by declaration |

Share of each table's declared-model rate that rests above its source's last data point:

| table | last source point (eV) | 45 eV | 60 eV | 75 eV | 90 eV | 120 eV | 150 eV |
|---|---|---|---|---|---|---|---|
| `dissociation_N2` | 200 | 0.95 % | 3.75 % | 8.34 % | 14.05 % | 26.36 % | 37.75 % |
| `A3Sigma_u` | 100 | 1.46 % | 3.10 % | 4.91 % | 6.70 % | 10.00 % | 12.85 % |
| `B3Pi_g` | 100 | 0.68 % | 1.46 % | 2.33 % | 3.20 % | 4.80 % | 6.18 % |
| `Bprime3Sigma_u` | 100 | 1.39 % | 2.94 % | 4.66 % | 6.38 % | 9.57 % | 12.34 % |
| `C3Pi_u` | 100 | 1.01 % | 2.16 % | 3.45 % | 4.74 % | 7.15 % | 9.26 % |
| `W3Delta_u` | 100 | 1.17 % | 2.53 % | 4.06 % | 5.61 % | 8.52 % | 11.08 % |
| `a1Pi_g` | 200 | 0.23 % | 1.03 % | 2.54 % | 4.62 % | 9.75 % | 15.27 % |
| `aprime1Sigma_u` | 100 | 2.35 % | 4.98 % | 7.90 % | 10.82 % | 16.23 % | 20.93 % |
| `w1Delta_u` | 100 | 6.71 % | 14.19 % | 22.14 % | 29.68 % | 42.46 % | 52.28 % |
| `rot_j0_to_j2` | 10 | 96.31 % | 97.81 % | 98.55 % | 98.97 % | 99.41 % | 99.61 % |
| `rot_j0_to_j4` | 10 | 91.89 % | 95.16 % | 96.79 % | 97.72 % | 98.69 % | 99.15 % |

These are context, not findings against v1. At 45 eV several electronic tables, and both rotational tables, already rest
more than 1 % on their declared continuation. The v1 basis strings say so (≤ 6.7 %; "declared model"). This audit proposes
no change to any v1 limit.

## 5. (b) Required energy coverage and hypothetical run coverage

`E_req` is the cross-section upper energy a source must reach so that the Maxwellian-rate share from higher energies is below
the threshold at T_e = L/1.5. It is computed with a **hold envelope** above the source's last point. That is conservative
for a falling σ, but not for j 0→2, whose σ still rises at 10 eV (`hold_envelope_is_upper_bound` = false). The flat-σ
reference is (1 + x)e^(−x) = threshold with x = E_req/T_e, giving x = 6.64, 16.69 and 31.10.

| table | L = 60 eV: 1e-2 / 1e-6 / 1e-12 (eV) | L = 90 eV | L = 150 eV |
|---|---|---|---|
| flat-σ reference | 266 / 668 / 1244 | 398 / 1001 / 1866 | 664 / 1669 / 3110 |
| `dissociation_N2` | 262 / 664 / 1241 | 392 / 995 / 1860 | 655 / 1661 / 3102 |
| `A3Sigma_u` | 192 / 601 / 1179 | 315 / 926 / 1793 | 581 / 1593 / 3036 |
| `B3Pi_g` | 162 / 575 / 1154 | 277 / 891 / 1759 | 532 / 1549 / 2993 |
| `Bprime3Sigma_u` | 188 / 598 / 1176 | 311 / 922 / 1789 | 575 / 1588 / 3031 |
| `C3Pi_u` | 176 / 587 / 1166 | 296 / 909 / 1776 | 557 / 1571 / 3015 |
| `W3Delta_u` | 181 / 592 / 1170 | 303 / 915 / 1782 | 566 / 1580 / 3023 |
| `a1Pi_g` | 211 / 618 / 1196 | 332 / 941 / 1808 | 591 / 1602 / 3045 |
| `aprime1Sigma_u` | 207 / 614 / 1192 | 334 / 943 / 1809 | 602 / 1612 / 3055 |
| `w1Delta_u` | 240 / 644 / 1221 | 374 / 979 / 1844 | 644 / 1650 / 3092 |
| `rot_j0_to_j2` / `_j4` | 266 / 668 / 1244 | 398 / 1001 / 1866 | 664 / 1669 / 3110 |

- The requirements JSON also gives L = 75 and 120 eV, and E_req under the electronic tables' declared power law.
- For the vibrational tables E_req is not defined: they are rate fits with no cross section in the repository. The flat
  reference and §6.3 apply to them.
- At the 1e-12 level every table needs cross sections to ≥ 1.15 keV even at L = 60 eV. At 1e-6 it needs ≥ 575 eV.

Hypothetical proxy count: newly covered v1 OOD runs, out of 714. Counting only, not scoring, and not an eligibility statement.

| scenario (limits raised to L) | L = 60 eV | L = 75 eV | L = 90 eV | L = 120 eV | L = 150 eV |
|---|---|---|---|---|---|
| all 21 capped tables | 211 (29.6 %) | 423 (59.2 %) | 609 (85.3 %) | 710 (99.4 %) | 714 (100.0 %) |
| all except dissociation | 0 | 0 | 0 | 0 | 0 |
| all except electronic | 7 (1.0 %) | 25 (3.5 %) | 33 (4.6 %) | 40 (5.6 %) | 40 (5.6 %) |
| all except rotational | 6 (0.8 %) | 22 (3.1 %) | 30 (4.2 %) | 37 (5.2 %) | 37 (5.2 %) |
| all except vibrational | 54 (7.6 %) | 105 (14.7 %) | 149 (20.9 %) | 171 (23.9 %) | 171 (23.9 %) |
| dissociation only | 6 (0.8 %) | 22 (3.1 %) | 29 (4.1 %) | 36 (5.0 %) | 36 (5.0 %) |

- **Share of all 1080 v1 runs covered** (all 21 tables raised): 577 (53.4 %), 789 (73.1 %), 975 (90.3 %), 1076 (99.6 %) and
  1080 (100 %).
- **Evidence-supported draft only** (dissociation → 60 eV): 6 OOD runs (0.8 %).
- **Evaluated reading** (dissociation → 75 eV, a¹Π_g → 150 eV): 22 OOD runs (3.1 %).
- The run × reading counts (2160) are exactly double: the OOD status does not depend on the reading.
- The requirements JSON also breaks the counts down by chemistry, point and registration. By design it has no per-candidate
  breakdown.

## 6. (c) Independent published evidence at higher energies

Access labels:

- **full text** was read.
- **abstract only** means only Crossref or publisher metadata was read.
- **secondary** means the numbers come from a reproduction in another accessible document.

No LXCat data was used. No paywall or bot challenge was bypassed. No author or lab was contacted.

### 6.1 Dissociation (`dissociation_N2.dat`)

Song et al. 2023 Fig. 19 (NSF PAR copy) is vector graphics. Its paths were extracted into
`sources/song2023_fig19_vector_extract.csv` [digitized, vector]. As a calibration check, the 16 Cosby diamonds reproduce Table 9
to ≤ 0.00087×10⁻¹⁶ cm² and ≤ 0.10 % in energy.

The series were identified by the figure legend: Majeed = green dashed, Kawaguchi = magenta solid. The caption states the
reverse. The text supports the legend: Kawaguchi "recommended somewhat lower values", and Majeed & Strickland used Cosby.

| independent set | class, access | range (eV) | ratio to Cosby at 50 / 100 / 150 / 200 eV | σ(E)/σ(200 eV) at 250 / 300 / 500 / 900 eV |
|---|---|---|---|---|
| Winters 1966, neutral points | reconstructed from measured data → digitized; abstract only; ±20 % (Song) | 22.6–296.2 | 1.10 / 1.23 / 1.22 / 1.25 | 0.91 / – / – / – |
| Majeed & Strickland 1997 curve | evaluated → digitized; abstract only; uncertainty TBD | 11.0–974.6 | 1.02 / 0.96 / 0.93 / 0.90 | 0.90 / 0.82 / 0.61 / 0.40 |
| Kawaguchi et al. 2021 curve | evaluated → digitized; abstract only; uncertainty TBD | 14.0–1002.0 | 0.76 / 0.83 / 0.79 / 0.75 | 0.89 / 0.81 / 0.62 / 0.44 |
| Tabata et al. 2006 n2-61 | model fit to the Cosby set; QST open data | 12–200 | not independent | no coverage above 200 eV |
| Zipf & McLaughlin 1978 | inferred; not accessed | – | Song quotes ≤ 0.6×10⁻¹⁶ cm² at 200 eV | not used |

**Rate consequence.** All three independent sets fall above 200 eV, so the held tail is an upper envelope. The next table
shows the effect of normalising each set to Cosby at 200 eV:

| L (eV) | share above 200 eV (held) | held-tail bias vs MS1997 / Kawaguchi / Winters shape | share beyond 296 eV (measured end) | share beyond 975 eV (evaluated end) |
|---|---|---|---|---|
| 45 | 0.95 % | 0.07 % / 0.07 % / 0.05 % | 0.05 % | 2.6e-13 |
| 60 | 3.75 % | 0.34 % / 0.35 % / 0.25 % | 0.47 % | 6.2e-10 |
| 75 | 8.34 % | 0.93 % / 0.96 % / 0.66 % | 1.69 % | 6.4e-08 |
| 90 | 14.05 % | 1.86 % / 1.90 % / 1.25 % | 3.87 % | 1.4e-06 |
| 120 | 26.36 % | 4.59 % / 4.63 % / 2.75 % | 10.64 % | 6.2e-05 |
| 150 | 37.75 % | 8.18 % / 8.15 % / 4.37 % | 19.05 % | 5.8e-04 |

**Independence.**

- **Winters' neutral points are reconstructed.** Winters measured the N atoms deposited from N and N⁺ fragments, over
  0–300 eV. The neutral part is that total minus a separately measured dissociative-ionization cross section. The Fig. 19
  caption says Tian & Vidal (J. Phys. B 31, 5369, 1998) was used; the Sec. 2.7 text names Rapp & Englander-Golden (1965).
- **Table 9 is not independent of Winters.** Cosby "recommended weighted averages in-between his and Winter's data" (Song
  Sec. 2.7).
- **MS1997 is not independent of Cosby.** Majeed & Strickland "used the recommended cross sections by Cosby" (Song Sec. 2.7).
- **So the join test is a consistency check.** The C3 join test at 200 eV is not an independent test for Winters or MS1997.
  Only the part above 200 eV adds independent coverage.

**Agreement.**

- **Shape above 200 eV.** All three sets agree with each other to within a few percent. The table's flat hold does not
  follow their shape, but its rate bias is < 1 % up to 75 eV.
- **Normalisation at 200 eV.** Majeed & Strickland (0.90) is within Cosby's ±20 %. Winters (1.25) is within the combined
  ±28 %. Kawaguchi (0.75) is outside ±20 %. This is a normalisation disagreement that also exists inside the v1 domain
  (0.76 at 50 eV). It is recorded here, not resolved.
- **Energy loss per event.** The fixed 12.14 eV loss rests on Cosby's 48.5 eV translational spectra only. Its 9.75–13.33 eV
  model uncertainty stays carried.

### 6.2 Electronic excitation (8 states)

Two sets were accessible:

- The Majeed & Strickland 1997 recommended values, as tabulated in the QST open-data files of Tabata et al. 2006 [evaluated →
  secondary numeric reproduction; the MS1997 paper is abstract-only].
- The Tabata analytic fits [model-derived; fitted to MS1997, Trajmar 1983, Campbell 2001 and others, so not independent of
  MS1997].

Kawaguchi et al. 2021 gives ICS "up to 10 keV for 17 states" (Song Sec. 2.6), but it is abstract-only and was not taken from
LXCat. Samaddar et al. (arXiv:2209.11185) fit the same Johnson data and are not independent.

| state | Johnson last point (eV), rel. unc. | p | MS1997/table at 100 / 150 / 200 eV | at 500 / 1000 eV | MS shape impact on rate at L = 60 / 90 / 150 eV | MS absolute impact at 60 / 90 / 150 eV |
|---|---|---|---|---|---|---|
| A³Σ_u⁺ | 100, ±18 % | 2.29 | 0.35 / 0.25 / 0.22 | – | −0.50 / −1.29 / −2.94 % | −2.19 / −4.80 / −9.36 % |
| B³Π_g | 100, ±18 % | 2.87 | 0.69 / 0.63 / 0.36 | – | −0.11 / −0.33 / −0.91 % | −0.53 / −1.22 / −2.53 % |
| W³Δ_u | 100, ±19 % | 2.25 | 0.46 / 0.35 / 0.27 | – | −0.34 / −0.94 / −2.31 % | −1.53 / −3.48 / −7.09 % |
| B′³Σ_u⁻ | 100, ±35 % | 2.23 | 1.91 / 1.34 / 0.68 | – | −0.58 / −1.60 / −3.93 % | +1.58 / +2.76 / +3.74 % |
| a¹Π_g | 200, ±26 % | 1.07 | 0.78 / 0.79 / 0.82 | 0.87 / 0.92 | +0.01 / +0.07 / +0.34 % | −0.18 / −0.77 / −2.46 % |
| a′¹Σ_u⁻ | 100, ±32 % | 1.67 | 3.82 / 5.54 / 5.72 | 9.43 / 15.05 | +0.88 / +2.64 / +7.49 % | +17.45 / +40.66 / +87.75 % |
| w¹Δ_u | 100, ±26 % | 0.53 | 0.17 / 0.12 / 0.02 | – | −7.72 / −18.87 / −38.17 % | −13.07 / −27.80 / −49.83 % |
| C³Π_u | 100, ±18 % | 2.47 | 1.27 / 1.56 / 2.04 | – | +0.30 / +0.88 / +2.28 % | +0.97 / +2.42 / +5.43 % |

- **a¹Π_g.** MS1997 agrees with Johnson at 200 eV within ±26 %, and with the ~1/E continuation up to 1 keV.
- **The other seven states.** MS1997 disagrees with Johnson's *measured* 100 eV value beyond Johnson's stated uncertainty, by
  factors 0.17–3.8. The same conflict is present at 50 eV, inside the v1 domain. It is recorded here, not acted on.
- **Asymptotic behaviour (from memory: verify).** Spin-forbidden triplet cross sections tend to about E⁻³, and
  dipole-forbidden singlets to about E⁻¹ in the Born limit. The w¹Δ_u continuation (p = 0.53) is shallower than E⁻¹.

### 6.3 Vibrational excitation

The Tabata n2-5 fit is fitted to the Itikawa et al. 1986 recommended v = 0→1 data over 1.05–48.5 eV [evaluated → secondary].
Itikawa 2006 recommends the 7.5–30 eV part from Tanaka, Yamamoto & Okada 1981, at ±30 % (Song Sec. 2.5).

Maxwellian rates of that fit, relative to the table's Laporta 0→1 rate:

| T_e (eV) | mean energy (eV) | E < 5 eV (resonance region) / table | 5–48.5 eV (non-resonant) / table, zero beyond | E > 5 eV / table, held beyond 48.5 eV |
|---|---|---|---|---|
| 2 | 3 | 0.77 | 0.01 | 0.01 |
| 10 | 15 | 0.83 | 0.58 | 0.59 |
| 20 | 30 | 0.84 | 1.47 | 1.59 |
| 30 | 45 | 0.84 | 2.05 | 2.50 |
| 40 | 60 | 0.85 | 2.44 | 3.42 |
| 60 | 90 | 0.85 | 2.91 | 5.56 |
| 100 | 150 | 0.85 | 3.36 | 11.59 |

- **Resonance region.** The fit agrees with Laporta to 0.73–0.85, within the ±20–30 % uncertainties.
- **Non-resonant excitation.** It is omitted by the declared closure ("resonant only"). It exceeds the table's 0→1 rate from
  T_e ≈ 20 eV. Truhlar 1972 (single author per Crossref) [abstract] independently describes non-resonant vibrational excitation of N₂ at 30–83 eV.
- **Overtones (v_f ≥ 2).** The only accessible data (QST n2-6, n2-8) cover the resonance region only (1.9–3.0 eV).

### 6.4 Rotational excitation

No accessible independent cross section exists above 10 eV:

- The Tabata n2-4 fit covers 0.0296–2.94 eV.
- Itikawa 2006 is abstract-only.
- Kawaguchi 2021 lists 31 rotational excitations, but its range is not accessible.

A Born quadrupole estimate (Gerjuoy & Stein 1955) is from memory and is not used (verify).

### 6.5 Not accessed / not used

- Brunger & Buckman, Phys. Rep. 357, 215 (2002): metadata only.
- Itikawa 2006: abstract only.
- Cosby 1993: abstract only.
- Winters 1966: abstract only.
- Tanaka 1981: metadata only.
- Malone et al. 2009/2012 and Liu et al. 2017 (higher states): not accessed.
- The Tabata 2006 paper and its 2012 erratum: not accessed. Only the QST open data were used, and whether those files
  include the erratum was not checked.

## 7. (e) Verdict rule and per-table verdicts (all DRAFT_PENDING_OWNER)

The rule is stated in the requirements JSON, `verdict_criteria.rule`. The criteria are evaluated per table and candidate
limit.

- **C1, coverage.** At L, less than 1 % of the table's declared-model rate may come from above the last point covered by
  accessible published σ. Covered points are the table's own sources plus the independent sets that pass C3. This is the
  existing `rate_validity.toml` convention.
- **C2, shape.** For every independent set that passes C3, replacing the table's σ above its own last source point by that
  set's shape changes the rate at L by less than 1 %.
- **C3, join.** The independent set agrees with the table at the table's last source point within the stated uncertainty.
  Uncertainties are combined in quadrature where both are published.
- **Readings.** The measured reading lets only measurement-based independent sets count for C1. That means measured sets,
  or sets reconstructed by arithmetic from measured sets, such as Winters' neutral points. The evaluated reading also counts
  evaluated sets that are secondary reproductions of abstract-only papers.
- **Verdicts.** SUPPORTED means the measured reading passes at ≥ 60 eV, and the proposal is the largest candidate that
  passes. PARTIAL means only the evaluated reading passes, or the table's content passes but has a documented omission.
  UNRESOLVED-BY-SOURCE means no accessible independent set passes C3. UNSUPPORTED means an independent set passes C3 but
  fails C2 at 60 eV; no table falls in this class.

| table | verdict | proposed limit (DRAFT) | deciding facts |
|---|---|---|---|
| `dissociation_N2.dat` | **SUPPORTED** | **60 eV** | Winters (measurement-based; not independent at the join; 2 points above 200 eV; owner decision 12) passes C3. At 60 eV: C1 0.47 %, C2 ≤ 0.34 %. At 75 eV, C1 is 1.69 % in the measured reading, so the evaluated reading only reaches 75 eV (C2 0.93 %, not proposed). L* (measured) is 68.0 eV. The table itself is unchanged. |
| `excitation_N2_a1Pi_g.dat` | PARTIAL | – | Measured coverage ends at 200 eV: L* own is 59.5 eV (1.03 % at 60 eV). The evaluated reading passes to 150 eV (MS1997 join 0.82, shape ≤ 0.34 %). |
| `excitation_N2_{A3Sigma_u,B3Pi_g,W3Delta_u,Bprime3Sigma_u,aprime1Sigma_u,w1Delta_u,C3Pi_u}.dat` | UNRESOLVED-BY-SOURCE | – | MS1997 fails C3 at 100 eV (0.17–3.82 against ±18–35 %), and Kawaguchi 2021 is not accessible. B³Π_g's own measured coverage alone keeps the continuation below 1 % up to 51.4 eV; that value is not a candidate limit and is not proposed. |
| `excitation_N2_rot_j0_to_j2.dat`, `_j4.dat` | UNRESOLVED-BY-SOURCE | – | No data above 10 eV. The held part is already 92–96 % of the rate at 45 eV. |
| `excitation_N2_vib_0_to_{1..10}.dat` | PARTIAL | – | The resonant content has no tail extrapolation. The omitted non-resonant 0→1 component is 2.05× (T_e 30 eV) to 2.9× (T_e 60 eV) the table's rate, which makes this a completeness question. There are no non-resonant overtone data. |

The 1e-6 and 1e-12 levels change the picture. No measured set reaches the E_req they imply, so under either level no table
is SUPPORTED.

## 8. (d) Completeness implications on an extended domain

Every omitted-process verdict so far was made on T_e 2–30 eV (vibrational and rotational: 0.2–30 eV), under
`prereg/n2_completeness_audit_v1.json`, addenda 1–2, `audit/n2_completeness_final_v1.json` and `audit/n2_closure_verdicts_v1.json`.
Extending any limit requires a pre-registered re-audit on the extended domain **before** any v2 run. It keeps the same
thresholds (F_P 1 %, F_ion 1 %, F_S 5 %) unless the owner decides otherwise. The rate indicators below come from the
committed tables. They are not verdicts.

| process | v1 verdict (T_e ≤ 30 eV) | why it must be re-audited |
|---|---|---|
| N²⁺ → N³⁺ (threshold 47.45 eV) | EXCLUDED (F_ion ≤ 1.5×10⁻⁶; its activity sits at T_e 19–26 eV) | The threshold lies inside the extended domain. Its rate coefficient is 1.6× (T_e 40 eV) to 3.8× (T_e 100 eV) its value at T_e 30 eV. |
| N₂ → N₂²⁺ direct (42.9 eV) | UNCERTAINTY VARIANT (nominal ≤ 0.39 %, upper 2.6 % F_ion) | The upper envelope over N₂⁺ production rises from 0.064 (T_e 30 eV) to 0.086 (T_e 100 eV); the nominal from 0.0101 to 0.0129. Nominal could cross 1 %. |
| N₂⁺ → N₂²⁺ (Tabata/Bahati) | EXCLUDED from nominal (margin 3.7) | The smallest margin of the closure. The rate rises 1.4–2.7× between T_e 40 and 100 eV. |
| N → N²⁺ direct (HMS 2017) | PROMOTED | Stays promoted. Its ×0.5/×1.3 sensitivity needs re-running. |
| non-resonant vibrational excitation | outside the declared closure | It is 2–3× the resonant 0→1 rate at T_e 30–60 eV (§6.3), so F_P must be bounded. |
| rotational above 10 eV | PROMOTE (marginal gross F_P 1.13 % at T_e 1–2 eV) | No σ above 10 eV exists; a bound is needed. |
| dipole-allowed / higher states (b¹Π_u, c₃¹Π_u, o₃¹Π_u, b′¹Σ_u⁺, c′₄¹Σ_u⁺, E³Σ_g⁺, a″¹Σ_g⁺, G³Π_u, F³Π_u) | not in the pre-registered tier lists | Their predissociating part is inside the channel-summed Cosby σ. The radiating part is an omitted loss that grows with energy (Born ln E/E, from memory: verify). Measured ICS 13/17.5–100 eV exist (Malone 2009/2012; Liu 2017), not accessed. |
| triple / multiple ionization (N₂³⁺, N → N³⁺, extra N⁺ from triple events) | not assessed | Their thresholds lie inside the extended domain. |
| dissociation energy loss (fixed 12.14 eV) | carried as 9.75–13.33 eV | The channel mix above 48.5 eV is not covered by Cosby's analysis. |

## 9. Decisions for the owner

1. Whether to open a v2 at all. Evidence supports only dissociation → 60 eV, which newly covers about 6 of 714 v1 OOD runs
   (proxy); the evaluated reading covers 22.
2. Which reading counts as coverage: measured-only (this audit's default) or evaluated-inclusive.
3. The extension threshold: the existing 1 % convention, or 1e-6 / 1e-12. Nothing is supported at the stricter levels.
4. The C3 tolerance, and how to treat sets whose uncertainty is not accessible (MS1997, Kawaguchi 2021).
5. Whether to seek legitimate full-text access (library or purchase; no paywall bypass; no LXCat) to Kawaguchi 2021, MS1997,
   Itikawa 2006, Cosby 1993 and Winters 1966.
6. Dissociation: keep the held tail with the table unchanged, or rebuild it with an evidence-shaped tail. A rebuild is a model
   change and every run reruns. Also decide whether Kawaguchi's −25 % normalisation warrants a chemistry variant.
7. Vibrational: keep "resonant only" above T_e 30 eV, add non-resonant excitation (a model change), or bound it in the
   re-audit.
8. Rotational: accept a theory-only envelope above 10 eV, or keep 45 eV.
9. Electronic: record the MS1997–Johnson conflict at 50–100 eV only, or carry it as a variant in a future version (never in
   v1).
10. Pre-register the extended-domain completeness re-audit: domain, process list (including the higher states and multiple
    ionization) and denominators.
11. The v2 run scope, and whether the driver should save per-frame T_e and activity so that exact f_out can be re-evaluated
    for a new limit without reruns. That is a `bridge_lib.jl` change and the owner's call.
12. Whether two reconstructed Winters points above 200 eV are enough for the dissociation extension to 60 eV. They are
    digitized from Song 2023 Fig. 19 and are not independent of Table 9 at the 200 eV join (`owner_decisions` D-X12).

## 10. Reproduction

```
python scripts/chemistry/n2_domain_extension_requirements.py --check          # recompute, compare with the committed JSON
python -m pytest -q tests/test_n2_domain_extension_audit.py
python scripts/chemistry/n2_domain_extension_requirements.py --extract-fig19 <NSF PAR PDF, sha256 f35b73d1…>   # rebuild the CSV (needs pymupdf)
```

The Song 2023 PDF, the arXiv PDFs and the QST files are not committed. Their sha256 values are recorded in the script, the CSV
header and `domain_extension_audit.json` → `sources`.
