# O/O₂ electron-impact chemistry v0: first DRAFT rate tables

**Status: DRAFT for owner review. Unused by any campaign.** Lane `fo_o_o2_chemistry_v0` (trigger
`T_PIVOT_O_O2_CHEMISTRY_V0`, owner disposition `od_hardware_pivot`, workstream W7 "continue toward the actual atmospheric
composition"). No file here is read by a propellant configuration, the Hall driver, `HallMap`, `archengine` or any
test other than `tests/test_o_o2_chemistry_v0.py`. Moving a table into `hallthruster_bridge/propellants/` is a later
model change that the owner must approve. It needs a `rate_validity.toml` entry and a separate O/O₂ reaction-set label
(PROPOSED name `abep-oo2-0.x`, never `abep-n2n-*`).

**Precedence.** Lane 13's `../o_o2_completeness_prereg_DRAFT.json` asks to be frozen before any O/O₂ table is built.
That file is DRAFT_PENDING_OWNER and binds nothing. The owner's W7 disposition registered this lane. So this lane
**builds tables only**:
- no F_P, F_ion, F_S or F_att value is computed;
- no process is included, promoted or excluded;
- no completeness verdict is pre-empted.

CLAUDE.md "Next work" item 4 is unchanged.

## What was built

The format is HallThruster.jl's, identical to `hallthruster_bridge/propellants/*.dat`: a header `<label> (eV): <E>`,
then mean energy 0–300 eV in 1 eV steps and k in m³/s. The tables are integrated by the unchanged
`abep_sim/rate_tables.py`.

| file | channel | source (accessed) | range (eV) | stated uncertainty | quantity type | DRAFT limit ε̄ (eV) |
|---|---|---|---|---|---|---|
| `ionization_O_beb_kd2002.dat` | O → O⁺ | Kim & Desclaux 2002 BEB via NIST SRD 107 (open) | 13.618–5000 | none in table (SONG2026: ≥ 20 % overall) | model-derived | 45 |
| `ionization_O_thompson1995.dat` | O → O⁺ | Thompson et al. 1995 points via NIST SRD 107 | 13.618 (ramp), 14.1–2000 | not read (paywalled) | measured | 45 |
| `ionization_O2_song2026.dat` | O₂ → O₂⁺ | SONG2026 Table VII, O₂⁺ | 13.0–998 | 5 % | measured (evaluated), transcribed | 45 |
| `dissociative_ionization_O2_upper_song2026.dat` | O₂ → O⁺ + O | Table VII, O⁺ (+O₂²⁺) as published | 18.738 (ramp), 23–998 | 7 % | measured, ramp assumed | 45 |
| `dissociative_ionization_O2_lower_song2026.dat` | same | same ÷ 1.1 (O₂²⁺ ≈ 10 % of O⁺ at 100 eV, SONG2026 text) | same | 7 % + ambiguity | + inferred | 45 |
| `dissociative_ionization_O2_to_O_Z2plus_song2026.dat` | O₂ → O²⁺ + O (tier-3 candidate) | Table VII, O²⁺ | 53.888 (ramp), 73–998 | 10 % | measured, ramp assumed | 45 |
| `dissociation_O2_song2026.dat` | O₂ → O + O | Table VI (Cosby 1993) | 13.5–198.5 | ±35 % | measured (evaluated) | 45 (support 47) |
| `elastic_O2_song2026.dat` | O₂ momentum transfer | Table V | 0.001–1000 | ~20 % (1–10 eV), 10–15 % (10–1000 eV) | measured / inferred (swarm) | 45 |
| `attachment_O2_song2026.dat` | O₂ → O⁻ + O | Table VIII (Rapp & Briglia 1965) | 4.2–9.9, zero tail | ≤ 20 % | measured, zero tail assumed | not a solver input |

Source keys:
- **SONG2026:** Song et al., J. Phys. Chem. Ref. Data 55, 013102 (2026), doi:10.1063/5.0287254. Read from the
  accepted manuscript on UCL Discovery (sha256 `32d163a3…`, the same file lane 13 audited). The version of record
  and the supplement were **not** accessed.
- **NIST SRD 107 O table:** `https://physics.nist.gov/cgi-bin/Ionization/merge.php?file=OI--&mode=ASCII`. The raw
  sha256 is pinned in the builder. The table is not committed, following the repository precedent.

Every table carries a `.source` file and a manifest record (`manifest_song2026_v0.json`, `manifest_nist107_o_v0.json`).
The record gives the source, DOI, URL, document hash, table and column, extraction method, transformation chain,
evidence level (4) and quantity type. It also gives the uncertainty, header basis, choices and the hold-vs-zero tail
share at 3/15/45/100/255 eV.

**The DRAFT validity limit** is min(source-support limit, 45 eV). The source-support limit is the
`rate_validity.toml` rule: held-tail share < 1 %, capped at 255 eV. The 45 eV cap is the project's pre-registered N₂
domain convention. It is PROPOSED for O/O₂ (OD-1) and is not an RFP value.

**Channel split for O₂ ionization.** The three Table VII partials are kept as separate tables: O₂⁺, O⁺ (+O₂²⁺) and O²⁺.
The total column is not used. Double dissociative ionization (O⁺ + O⁺) and O₂²⁺ remain inside the O⁺ column and
are carried as the upper/lower pair.

**Script-computed sensitivities** (in the manifests):
- DI threshold ramp vs sigma = 0 below 23 eV: −44 % of the rate at T_e = 2 eV, −6.7 % at 5 eV, −1.2 % at 10 eV.
- Envelope vs ramp: +83 % at T_e = 2 eV, +8.4 % at 5 eV.
- O ionization, Thompson ÷ BEB over 20–200 eV (19 points): 0.868–1.064.
- The omitted out-of-order Table V row (read as 0.080 eV) changes the O₂ elastic rate by ≤ 1.3e-5 at T_e ≥ 0.2 eV.

**Transcription check.** `--verify-pdf` confirms that Tables V–VIII appear value-exact and in printed order in a
second (PyMuPDF) text extraction. Table VII partials sum to the printed total within 0.49 %.

## Known defects (not hidden)
- **O₂ dissociation is Cosby-only above 13.5 eV.** Dissociation through the Herzberg (~5–7 eV) and Schumann–Runge
  (~7–9.5 eV) states below 13.5 eV is **missing**, so the rate is under-counted at low T_e by an unknown amount. Any
  dissociative-excitation table added above 13.5 eV would double count. Both issues wait on OD-4.
- **Dissociation header.** It is 5.12 eV, the minimum sink. The range 5.12–7.087 eV (O(¹D) + O(³P)) is recorded as
  energy-loss uncertainty.
- **DI and O²⁺ headers.** These are thermochemical minima: D₀ + IE. They are inferred and PROPOSED, mirroring the N₂ DI
  convention the owner decided. 48.77 eV comes from an OCR text layer (verify).
- **Verification.** Every SONG2026 value must be re-checked against the version of record before promotion.

## Unresolved (details and routes: `channel_status_v0.json`)

**Highest priority: O momentum transfer, then O excitation.** Atomic O is 0.48–0.70 of the free-stream mole fraction
at 180–230 km (lane 16 `FEED_ENVELOPE.md`). The delivered-feed split is still TBD (fo_feed_state_closure / ICD G-02).
The recommended BSR-1116 numbers are only in paywalled or not-accessed supplements.

Also unresolved:
- O₂ a/b/Herzberg/B excitation and anything above 20 eV (OD-4, OD-6);
- O₂ vibrational and rotational excitation;
- O fine structure;
- the O⁺ → O²⁺ link (Bell 1983, open, v0.1);
- direct O → O²⁺;
- O₂⁺ and O₂²⁺ channels;
- recombination and O⁻ sinks (OD-5, OD-8).

Paywalled items go to the owner-approved `fo_closed_access_acquisition` channel. No bypass was attempted.

## Proposed completeness audit (PROPOSED, not evaluated)
This reuses the frozen N₂ rule unchanged:
- promote an omitted process if F_P > 1 %, OR F_ion > 1 %, OR F_S_s > 5 %, anywhere in T_e 2–30 eV (0.2–30 eV for the
  low-threshold channels);
- apply the N₂ ambiguity and cross-check addenda;
- add F_att (attachment electron loss vs ionization) only if OD-5 admits O⁻.

The v0 ionizing set already allows F_ion to be evaluated without excitation denominators, as in the N₂ DI audit.
F_P and F_S stay provisional until the tier-1 gaps above close. Nothing may be evaluated before the owner freezes the
rule under `hallthruster_bridge/prereg/`.

## Milestones
- **A (conditional selection):** indirect support only. It shows the atmospheric-feed chemistry path is source-backed
  and names what blocks it. It is not a gate, and it changes no architecture statement.
- **B (physics-backed selection) needs:**
  - a frozen O/O₂ completeness rule with verdicts, after O MTCS and O/O₂ excitation are built;
  - version-of-record verification;
  - owner-approved promotion with validity entries and a reaction-set label;
  - an admitted Hall closure (physics track);
  - the delivered-feed composition.
- **C (PDR freeze) needs:** mixture chemistry over the mission composition envelope, consistent with thermal, life and
  startup.

## Reproduce
```
python docs/chemistry/o_o2/v0/build_tables_song2026.py [--check]
python docs/chemistry/o_o2/v0/build_tables_song2026.py --verify-pdf <song2026 accepted manuscript>
python docs/chemistry/o_o2/v0/build_tables_nist107_o.py [--check] [--from-file <saved NIST ASCII>]
python -m pytest -q tests/test_o_o2_chemistry_v0.py
```
