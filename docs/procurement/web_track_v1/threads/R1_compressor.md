# R1: DI-1.4 compressor primary evidence (Li 2015). Accessed 2026-09-27, repo 782f900

**Access.** The Li et al. 2015 full text (Vacuum 120:89-95, doi:10.1016/j.vacuum.2015.06.011) could not be obtained legitimately:
- ScienceDirect returns HTTP 403. This was not bypassed.
- OpenAlex, Unpaywall and Semantic Scholar list it as closed, and the publisher elides the abstract in Semantic Scholar.
- Crossref has metadata only.

The abstract content below comes only from **search-engine excerpts** of the ScienceDirect abstract page. Several queries gave consistent wording, but the abstract was not read verbatim first-hand, so all of it needs verification.

**What the abstract excerpts say**
- **Device:** 500 mm inlet (0.196 m², inside the repo's 0.098–0.377 m² range). Four elements in series: multi-hole plate, "big turbo", small TMP, miniature scroll pump.
- **Collection efficiency:** comes from DSMC/Monte Carlo of the plate and big turbo, not from measurement. Values at 150–240 km:
  - high rotational speed: 56.47–57.85 %
  - low rotational speed: 41.67–42.60 %
  - The "~60 %" quoted elsewhere is a rounding of the high-speed value.
- **Experiment:** only the storage chain (small TMP + scroll pump) was tested. The collected gas "can be compressed and get an atmospheric pressure". No number is given.
- **The throat-scale rotor (the C1 element) appears to have been simulated only.**
- **CR ≥ 3500 appears in no accessible Li 2015 text.** It exists only in Moon et al. (2025 arXiv, full text; 2024 AST, excerpt; same group).

**Secondary citations**

| citing source | access | what it quotes |
|---|---|---|
| Moon 2025 | full text | η_c ≈ 60 %, CR ≥ 3500 |
| Moon 2024 | excerpt | ~60 %, CR > 3500 with a 500 mm TMP; angular-momentum and vibration concerns |
| Romano 2021 | full text | η_c = 0.42–0.58; no CR |
| Andreussi 2022 | contexts only | qualitative "low power consumption"; no numbers |
| IEEE TAES 2023 | contexts only | 150–240 km; energy consumption needs experiments |

**Related primary sources.** Same-group TMP DSMC papers (Li 2013, Li 2014a, Li 2014b; all Vacuum, closed). An AIP 2016 RGD paper and a US patent (12286943, "Turbomolecular air-scoop...") could not be accessed. **I found no independent primary numbers for any rotor-based ABEP compressor.**

**Rule (A4).** "DI-1.4 is NOT frozen until the Li 2015 compression claim is verified from a first-hand source; a secondary citation is not enough for a system-critical compressor choice." The minimum data to freeze DI-1.4 are tests T-1..T-9.

**Recommendation for the owner. Nothing is frozen.**
- Keep C1 at **LEADING_CANDIDATE_PENDING_PRIMARY_EVIDENCE**. It is not primary-evidence-supported, and the evidence is insufficient.
- Annotate EV-08:
  - the ~60 % value is model-derived (DSMC);
  - CR ≥ 3500 is unverified and may not apply to the throat rotor;
  - the rotor has not been demonstrated experimentally.
- C1's lead rests on the pumping-speed physics bounds, not on Li 2015, so demoting it is not warranted.

**What would close it**
1. A first-hand read of Li 2015 through legitimate access: library, interlibrary loan or purchase. It should extract the CR definition, species, pressures, throughput, which stage the figure refers to, simulation vs experiment, rpm, power and mass.
2. For the freeze itself, the repo's own rule still requires tests T-1..T-5 and T-8 (and T-6, T-7, T-9 for Milestone C) on a throat-scale rotor.
