# O/O₂ electron-impact chemistry: source matrix v1 (audit only, no implementation)

Machine-readable version: `o_o2_source_matrix_v1.json` (same folder). If the two disagree, the JSON is authoritative.
Draft completeness rule: `o_o2_completeness_prereg_DRAFT.json`. Its status is **DRAFT_PENDING_OWNER**. It is not a
pre-registration until the owner freezes it under `hallthruster_bridge/prereg/`.

**What this is.** A literature and source audit for the O/O₂ reaction set that atmospheric (VLEO) Hall operation would
need later. It records which published sources exist, how they can be accessed, what they cover and what each one says
about its own uncertainty.

**What this is not.** It builds no rate table and changes no chemistry, threshold, solver setting or frozen dataset.
It includes, promotes, excludes and validates nothing. CLAUDE.md "Next work" item 4 still gates O/O₂ work: it starts
only if items 1–3 succeed.

**Rules followed:**
- LXCat was **not** used.
- Published sources only. No person or laboratory was contacted.
- Paywalled texts were not accessed. HTTP 403 blocks were not bypassed, and TLS settings were not changed.
- Every number below is quoted from the named source. Values taken from a PDF text layer are marked "verify".
- Sources whose bibliographic detail comes only from a reference list are marked "DOI not verified".

## Headline findings

1. **A new evaluated compilation covers both species.** Song, Cho, Karwasz, Kokoouline, Tennyson & Bartschat,
   *Cross Sections for Electron Collisions with Molecular and Atomic Oxygen*, J. Phys. Chem. Ref. Data **55**, 013102
   (2026), doi:10.1063/5.0287254 (`SONG2026`). The same group wrote the 2023 N₂ review that most of abep-n2n rests on.
   - The accepted manuscript ("Revised 26 November 2025") is open on UCL Discovery and was read in full
     (sha256 `32d163a3…`).
   - The version of record and the supplementary datasets were **not** accessed.
   - Manuscript anomalies are listed in the JSON, for example a Table V row reading "0.008 eV", and the Fig. 25 caption
     disagreeing with its plot label. Every value must be re-checked against the version of record before
     transcription.
2. **The installed solver has uncited negative-ion constants (CC-2).**
   - The locally installed HallThruster.jl source (`~/.julia/packages/HallThruster/zHCae`, version 0.23.1) hard-codes
     `_K_MUTUAL_NEUTRALIZATION = 1.0e-12 m³/s` and `_K_NEUTRAL_DETACHMENT = 1.0e-12 m³/s` in
     `src/simulation/heavy_species_update.jl`.
   - These apply to any fluid with Z < 0 and carry no citation.
   - If O⁻ (from dissociative attachment) were ever modelled, they would enter silently. That would breach CLAUDE.md
     rules 3 (no silent fallbacks) and 6 (cite data).
   - Whether this tree is identical to the pinned commit was not checked (verify). No Julia was run.
3. **O₂ dissociation double-counts dissociative electronic excitation (CC-4).**
   - Cosby's total dissociation into neutrals (SONG2026 Table VI) starts at 13.5 eV. The O₂ dissociation energy is
     5.12 eV.
   - The dissociative Herzberg states (about 5–7 eV) and the Schumann–Runge band (about 7–9.5 eV) lie below 13.5 eV
     (energies per SONG2026).
   - Above 13.5 eV, the excitation data and Cosby's total count the same events.
   - The owner must fix the accounting before any table is built.
4. **Recommended data stop short of the solver's energy grid (CC-5).**
   - Recommended atomic-O data (BSR-1116) end at 200 eV.
   - The high-energy continuation SONG2026 suggests is a private communication (`BG_OP`), which is not usable under the
     project rules.
   - Recommended O₂ electronic-excitation theory is plotted only to 20 eV. This is the same situation as Su 2021 for
     N₂.

## Matrix

Status meanings:
- **source-identified:** a verified published source gives the quantity over its main range.
- **source-open:** sources exist, but an owner decision is needed first.
- **gap:** no usable source was located in this audit.

Access meanings:
- **open:** the needed numbers were readable and were accessed.
- **paywalled:** only metadata or the abstract was seen.
- **mixed:** the recommended source is paywalled or its supplement was not accessed, but an open route exists.
- **none:** no source, so no access route.

"Tier" is the drafter's proposal in the DRAFT pre-registration, not a decision.

| id | target | process | recommended / candidate sources | range (eV), stated uncertainty | status | access | draft tier |
|---|---|---|---|---|---|---|---|
| OO2-01 | O | ionization O → O⁺ | Thompson et al. 1995 (rec. by SONG2026); BEB Kim & Desclaux 2002 via NIST SRD 107 (open, with Thompson/Brook/Zipf points); Laher & Gilmore 1990 | 13.62–2000 measured, to 5000 BEB; SONG2026: O data "accurate to at least 20 %" where they matter | source-identified | open | 1 |
| OO2-02 | O | momentum transfer | BSR-1116 (Tayal & Zatsarinny 2016, rec.); Williams & Allen 1989 (5 energies); Itikawa & Ichimura 1990 | to 200 (BSR grid); none above 200 except a private communication | source-identified | mixed | 1 |
| OO2-03 | O | electronic excitation (state-resolved / lumped) | BSR-1116 (rec.); Laher & Gilmore 1990 (open, > 60 profiles) | threshold–200; experimental bars up to ≈ 30 % | source-identified | mixed | 1 (state list = owner) |
| OO2-04 | O | ground-term fine structure | Itikawa & Ichimura 1990 §5.1 (Berrington R-matrix) | TBD; large disagreement at low energy | source-open | open | 3 |
| OO2-05 | O₂ | ionization O₂ → O₂⁺ | SONG2026 Table VII (Lindsay & Mangan; Straub 1996) | 13.0–998; 5 % | source-identified | mixed | 1 |
| OO2-06 | O₂ | dissociative ionization → O⁺ + O | SONG2026 Table VII column "O⁺ (+O₂²⁺)"; Tian & Vidal 1998 channel split | 23–998; 7 % (column includes O₂²⁺) | source-identified | mixed | 1 |
| OO2-07 | O₂ | → O²⁺ + O and → O⁺ + O⁺ | SONG2026 Table VII (atomic O²⁺); Tian & Vidal 1998 | 73–998; 10 % | source-identified | mixed | 3 |
| OO2-08 | O₂ | dissociation into neutrals | SONG2026 Table VI (Cosby 1993) | 13.5–198.5; about ±35 % | source-open (double counting, sub-13.5 eV) | mixed | 1 |
| OO2-09 | O₂ | momentum transfer | SONG2026 Table V (beam + Jeon 2003 swarm) | 0.001–1000; ≈ 20 % (1–10 eV), 10–15 % (10–1000 eV), none < 1 eV | source-identified | mixed | 1 |
| OO2-10 | O₂ | excitation a¹Δg, b¹Σg⁺ | Huang et al. 2022 (rec., R-matrix); Tashiro et al. 2006 (open); Shyn & Sweeney 1993 | thresholds 0.98 / 1.63; plotted to 20 | source-open (extension > 20 eV) | mixed | 1 |
| OO2-11 | O₂ | excitation Herzberg c, A′, A | Huang 2022 (rec.); Tashiro 2006; Teillet-Billy et al. 1989 (measured sum) | 6.12 / 6.27 / 6.47 (thresholds) to 20 | source-open (overlap with OO2-08) | mixed | 1 |
| OO2-12 | O₂ | B³Σu⁻ (Schumann–Runge) and higher | Huang 2022 (reports B; not in SONG2026 figures); Shyn et al. 1994 | band about 7–9.5 | source-open | paywalled | 2 |
| OO2-13 | O₂ | electronic excitation above 20 eV | Tanaka et al. 2016 scaled Born (candidate route, not evaluated) | TBD | gap | none | 1 (completeness of 10/11) |
| OO2-14 | O₂ | vibrational excitation | Laporta, Celiberto & Tennyson 2013 (rec.; arXiv open); Alt & Houfek 2021 (up to ×4 different) | < 4 eV and ≈ 10 eV resonances; "20 % or less" (SONG2026 estimate) | source-identified | mixed | 2 |
| OO2-15 | O₂ | rotational excitation | Born / Gerjuoy–Stein, SONG2026 Eq. (1) with B₀, Q₀ | model-only; "no experimental or accurate theoretical data" | source-open | open | 3 |
| OO2-16 | O₂ | dissociative attachment → O⁻ + O | SONG2026 Table VIII (Rapp & Briglia 1965); Christophorou 1965; Laporta 2015 | 4.2–9.9; "no more than 20 %" | source-identified | mixed | 2 (conditional on O⁻) |
| OO2-17 | O⁺ | O⁺ → O²⁺ | Bell et al. 1983 O II (open NIST reprint); Aitken & Harrison 1971 | from 35.12 (text layer, verify); ±10 % (67 % conf.) | source-identified | open | 3 (energy link) |
| OO2-18 | O | direct O → O²⁺ | Thompson 1995 (measured); Laher & Gilmore 1990 §3.2; HMS 2017 (overestimates neutral O ≈ ×2) | TBD | source-identified | mixed | 3 |
| OO2-19 | O₂⁺ | O₂⁺ → O₂²⁺; dissociative ionization; dissociative excitation | Cherkani-Hassani et al. 2006 (crossed beam) | threshold–≈ 2500; maxima (2.20 ± 0.09), (5.3 ± 1.0), (22.0 ± 4.6) × 10⁻¹⁷ cm² | source-identified | paywalled | 2 (diss. exc.) / 3 |
| OO2-20 | O₂ | O₂ → O₂²⁺ | Märk 1975; Sigaud 2013; Bull 2015; Jia 2023 | SONG2026: "unable to recommend" (large spread) | source-open | paywalled | 3 |
| OO2-21 | O₂⁺ | dissociative recombination (relevance) | Peverall et al. 2001; Florescu-Mitchell & Mitchell 2006 | TBD | source-identified | paywalled | outside rule |
| OO2-22 | O⁻ | electron-impact detachment (relevance) | Vejby-Christensen et al. 1996 | threshold–≈ 30 | source-identified | paywalled | conditional on O⁻ |
| OO2-23 | O⁻ | associative detachment, mutual neutralization | none surveyed (heavy-particle) | TBD | gap | none | conditional on O⁻ |
| OO2-24 | O⁺ | radiative / three-body recombination (relevance) | none surveyed | TBD | gap | none | outside rule |
| OO2-25 | O, O₂ metastables | collisions from O(¹D), O(¹S), O₂(a), O₂(b) | BSR-1116; Huang 2022; Tashiro 2006 | see JSON | source-identified | mixed | not proposed |

Each row in the JSON also records:
- the solver reaction type it would need;
- per-source quantity type (measured / model-derived / …);
- open issues;
- the unverified 0-D Arrhenius entry in `abep_sim/plasma_chem.py` that the source would replace. That file was not
  modified.

## Sources verified (key ones)

| key | citation | DOI | access (as found) |
|---|---|---|---|
| SONG2026 | Song et al., JPCRD 55, 013102 (2026) | 10.1063/5.0287254 | accepted manuscript open (UCL Discovery); VoR not accessed |
| ITIKAWA2009 | Itikawa, JPCRD 38, 1 (2009) | 10.1063/1.3025886 | not verified (no NIST reprint) |
| II1990 | Itikawa & Ichimura, JPCRD 19, 637 (1990) | 10.1063/1.555857 | open (NIST reprint) |
| LG1990 | Laher & Gilmore, JPCRD 19, 277 (1990) | 10.1063/1.555872 | open (NIST reprint) |
| BELL1983 | Bell et al., JPCRD 12, 891 (1983) | 10.1063/1.555700 | open (NIST reprint; same file as the N II source) |
| NIST107_O | NIST SRD 107, atomic O (BEB + Thompson/Brook/Zipf points) | — | open |
| TZ2016 | Tayal & Zatsarinny, PRA 94, 042707 (2016) | 10.1103/PhysRevA.94.042707 | paywalled; AAM link returned 403 |
| THOMPSON1995 | Thompson, Shah & Gilbody, J. Phys. B 28, 1321 (1995) | 10.1088/0953-4075/28/7/023 | paywalled (points in NIST SRD 107) |
| COSBY1993 | Cosby, J. Chem. Phys. 98, 9560 (1993) | 10.1063/1.464387 | paywalled |
| LAPORTA2013 | Laporta, Celiberto & Tennyson, PSST 22, 025001 (2013) | 10.1088/0963-0252/22/2/025001 | preprint open (arXiv:1604.05871) |
| HUANG2022 | Huang, Zhang & Cheng, J. Phys. Chem. A 126, 2061 (2022) | 10.1021/acs.jpca.1c09153 | paywalled |
| TASHIRO2006 | Tashiro, Morokuma & Tennyson, PRA 73, 052707 (2006) | 10.1103/PhysRevA.73.052707 | preprint open (arXiv:physics/0604098) |
| RB1965 | Rapp & Briglia, J. Chem. Phys. 43, 1480 (1965) | 10.1063/1.1696958 | paywalled |
| CH2006 | Cherkani-Hassani et al., J. Phys. B 39, 5105 (2006) | 10.1088/0953-4075/39/24/008 | paywalled |
| AH1971 | Aitken & Harrison, J. Phys. B 4, 1176 (1971) | 10.1088/0022-3700/4/9/007 | paywalled |
| VK1996 | Vejby-Christensen et al., PRA 53, 2371 (1996) | 10.1103/PhysRevA.53.2371 | paywalled |

The full list is in the JSON, 45 sources in total. For each source it gives how existence was verified (Crossref,
record page, or a downloaded document with its sha256), the evidence level (docs/EVIDENCE.md) and the role.

Excluded by policy:
- The Alves et al. 2016 oxygen set (EPJD 70, 124), because its numbers are distributed through LXCat.
- The Blanco & García optical-potential numbers, because they are cited only as a private communication.

## What the owner needs to decide before any O/O₂ table

These are the OD-1 to OD-8 items in the DRAFT pre-registration:
- **Domain (OD-1).** Keep T_e 2–30 eV as for N₂, or set the domain after the validity audit.
- **Basis for F_S (OD-2).** A composition grid or a blind state envelope.
- **O excitation (OD-3).** The state list and any lumped remainder.
- **O₂ dissociation accounting (OD-4).** How to split dissociation against dissociative excitation.
- **O⁻ (OD-5).** Whether to model O⁻ at all. If yes, an attachment metric and sourced O⁻ sinks are needed first.
- **O₂ excitation above 20 eV (OD-6).** Which extension source to use.
- **Rotational convention (OD-7).** Gross or net.
- **Volume recombination (OD-8).** A relevance criterion.

A separate reaction-set label is also needed, so that `abep-n2n-*` never names a set containing O/O₂.

## Not claimed

- No O/O₂ process is included, promoted or excluded.
- No ABEP performance, architecture or transport-admission statement is made.
- Nothing about the running P5-N₂ campaign was read or is stated.
