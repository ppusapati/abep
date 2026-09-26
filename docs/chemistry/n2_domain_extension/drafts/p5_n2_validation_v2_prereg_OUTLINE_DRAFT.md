# P5-N₂ validation v2: pre-registration OUTLINE (draft)

**Status: DRAFT_PENDING_OWNER.** This is an outline for the owner. It is **not** a pre-registration, and nothing in it is in
force. It is deliberately kept outside `hallthruster_bridge/prereg/`. Nothing may be run, scored or locked on its basis until
the owner has taken the decisions in §6 and a real pre-registration has been written, hash-locked and merged.

**v1 is permanent.** The pre-registered P5-N₂ v1 vacuum validation stays as scored:

- all nine SGB screening candidates are INCONCLUSIVE / NOT ELIGIBLE;
- the credible set is empty, and gate 3 is FAIL;
- the scores are 1428 OUT_OF_DOMAIN, 700 FAIL_VALIDATION and 32 PASS run × reading evaluations.

The v1 files (`validation/p5_n2_campaign_v1_vacuum_*`, `VALIDATION_RELEASE_v1.json`, `prereg/*_v1*`) are never rewritten, and
no v1 run is ever re-labelled. A v2 would be a separate campaign with separate files. Its outcome could never change a v1
status. It would not bypass the admission gate either: admission stays gated on the O4 dispositions, as CLAUDE.md states.

Evidence basis: `docs/chemistry/n2_domain_extension/N2_DOMAIN_EXTENSION_AUDIT.md` and `domain_extension_audit.json`, with
numbers in `domain_extension_requirements.json`.

## 1. What v2 would change (only what the evidence supports)

| item | v1 | v2 (draft) | basis |
|---|---|---|---|
| `dissociation_N2.dat` validity limit | 45 eV mean energy | **60 eV** | audit verdict SUPPORTED, measurement-based reading (DRAFT; rests on two reconstructed Winters points above 200 eV, owner decision 14) |
| 20 other capped tables (8 electronic, 2 rotational, 10 vibrational) | 45 eV | **45 eV (unchanged)** | PARTIAL / UNRESOLVED-BY-SOURCE |
| rate-table contents | abep-n2n-0.11 | **byte-identical** in the minimal v2 | no evidence-supported table change |
| omitted-process audit | T_e 2–30 eV (vib/rot 0.2–30 eV) | re-audit on the **extended domain** (T_e ≤ 40 eV for a 60 eV limit), pre-registered and completed **before** any v2 run | audit §8 |

**When the minimal v2 becomes a model change.** Three kinds of owner choice turn it into a model change: a table rebuild (for
example an evidence-shaped dissociation tail), an addition (for example non-resonant vibrational excitation), or a process
promoted by the extended-domain re-audit. A model change needs a new reaction-set version, new `rate_validity` entries,
snapshot configs under `audit/configs/`, and a **full rerun**. The minimal v2 rows above then no longer apply.

The electronic, rotational and vibrational limits could move only on new evidence or an owner decision on the reading (§6).
The audit's evaluated reading would allow dissociation 75 eV and a¹Π_g 150 eV. It is recorded, not proposed.

## 2. What stays identical (unless the owner decides otherwise)

- **Scoring rules.** Acceptance criteria D1–D6 (`prereg/p5_n2_validation_criteria_v1.json`) and operational rules O1–O5
  (O1 extinction/SUSTAINMENT, O2 status precedence, O3 member/candidate aggregation, O4 staged escalation, O5 E×B diagnostic).
- **Run statuses.** The run-status rule and its extinction addendum: PASS / FAIL_VALIDATION / OUT_OF_DOMAIN /
  NUMERICAL_FAILURE, with OUT_OF_DOMAIN not scoreable and not a failure.
- **Chemistry-trust rule.** f_out ≤ 10⁻¹² for every reaction, taken over every saved frame and cell.
- **Chemistry configs.** The mandatory configs (`n2_n.toml`, `n2_n_di_lower.toml`, `n2_n_nel_wang.toml`,
  `n2_n_di_lower_nel_wang.toml`) and the staged-sensitivity list.
- **Targets.** The measurement audit (`identification/brabston_p5_n2_measurement_audit_v1.json`), and targets that are
  mode-matched as in v1.
- **Physics inputs.** The 30 cases, the nine SGB screening transports with no retuning, layer-1 registrations and coil
  shapes, the HallThruster.jl pin (v0.23.1, commit `bfb3019f…`) and the run length and averaging window.

## 3. Which runs v2 would require

The minimal v2 changes one validity limit and no table.

- **Solver outputs stay the same.** Pinned code gives the same trajectories. v2 should verify this by reproducing a sample of
  v1 records bit for bit.
- **The frozen v1 records cannot be re-scored.** They store per-table f_out only at the v1 limits and no saved frames, so
  f_out at 60 eV needs reruns.
- **Only 36 v1 OOD runs can change status.** Those are the runs in which `dissociation_N2.dat` is the only table beyond its
  limit. In the other **678 of the 714** OOD runs, at least one unchanged table has f_out > 10⁻¹² at an unchanged limit, so
  they stay out of domain. That count is exact under reproducible reruns.
- **Proxy count.** 6 of the 36 have `max_mean_energy_active_eV` ≤ 60 eV.
- **In-domain v1 runs cannot become OOD**, because limits only rise.

Options for the owner:

- **(A) Minimal.** Rerun the 36 candidate runs and a reproducibility sample. Reuse is pre-registered: a v1 record may count
  in v2 only under an explicit reuse rule with hash checks.
- **(B) Clean.** Rerun all 1080 vacuum runs under the v2 lock.
- **Either way, facility and O4.** The facility (1080) and O4 staged datasets are pre-registered under v1 and scored under v1.
  Their v2 treatment is an owner decision.

A model change (§1) always means (B), plus the staged and facility campaigns if they are to be reported under v2.

**Possible prerequisite (owner decision 12; driver change).** Let `bridge_lib.jl` store, per reaction, the activity histogram against
mean energy over all saved frames. Exact f_out could then be re-evaluated for any future limit without rerunning.

## 4. Hash-lock steps (in order; nothing runs before step 7)

1. Record the owner decisions of §6 in a dated decision record.
2. Write the evidence-supported limit change as a new versioned `rate_validity` entry with a basis string that cites the
   audit. The owner makes this change under `propellants/`. Freeze a snapshot of the v1 validity file and configs so that v1
   stays reproducible.
3. Pre-register the extended-domain completeness re-audit: domain, process list and denominators, with thresholds F_P 1 %,
   F_ion 1 % and F_S 5 % unchanged. Run it on a blind state envelope with measured targets removed and record the verdicts.
   Any promotion is a model change; go back to §1.
4. Write `p5_n2_validation_criteria_v2.json` as a copy of D1–D6 and O1–O5 that differs only in the chemistry-domain
   references. Write `p5_n2_run_status_rule_v2.json` as a copy that differs only in the limits it references.
5. Write `p5_n2_prereg_lock_v2.json` with the sha256 of:
   - the v2 criteria, the v2 run-status rule and its addenda;
   - the v2 validity file, every rate table and propellant config;
   - `cases/p5_n2.json`, the measurement audit and the transport ensemble file;
   - the driver/`bridge_lib.jl` commit, the scorer commit and `PINNED.toml`;
   - this audit's JSON files, as the evidence reference.
6. Merge the pre-registration PR. No score-bearing v2 run happens before the merge.
7. Launch from pinned manifests, freeze the raw v2 dataset (integrity gate), score once, and release v2 as separate files
   (`validation/p5_n2_campaign_v2_*`, `VALIDATION_RELEASE_v2.json`). v1 files are untouched.

## 5. Expected information yield (proxy, not a prediction of any score)

Under the minimal v2, at most 36 of the 714 v1 OOD runs can re-enter the chemistry domain. The proxy count is 6, and 22 under
the evaluated reading. This audit does not predict which statuses the re-entering runs would get. The rotational tables
(no data above 10 eV), the vibrational tables (non-resonant omission) and seven electronic tables (source conflict) keep the
large majority of v1 OOD runs out of domain. The owner should weigh whether a minimal v2 is worth its cost against first
obtaining evidence for those tables (§6).

## 6. Decisions the owner must take (all open)

1. Whether to open a v2 at all, given §5.
2. The coverage reading: measured-only (the audit default) or evaluated-inclusive (secondary reproductions of abstract-only
   evaluations: MS1997, Kawaguchi 2021).
3. The extension threshold: the existing 1 % convention, or 1e-6 / 1e-12. At the stricter levels the accessible evidence
   supports no extension.
4. The C3 join tolerance, and how to treat sets whose uncertainty is not accessible.
5. Legitimate full-text access (library or purchase; no paywall bypass; no LXCat) to Kawaguchi 2021, Majeed & Strickland
   1997, Itikawa 2006, Cosby 1993 and Winters 1966, and a search for rotational σ above 10 eV.
6. Dissociation: keep the table unchanged (held tail; bias ≤ 0.34 % at 60 eV) or rebuild the tail (a model change). Whether
   Kawaguchi's −25 % normalisation at 200 eV warrants a chemistry variant.
7. Vibrational: keep "resonant only" above T_e 30 eV, add non-resonant excitation (a model change), or bound it in the
   re-audit.
8. Rotational: accept a theory-only envelope above 10 eV, or keep 45 eV.
9. Electronic: record the MS1997–Johnson conflict at 50–100 eV only, or carry it as a variant in a future version (never
   applied to v1).
10. The scope, domain and process list of the extended-domain completeness re-audit, including the dipole-allowed and higher
    states, multiple ionization, N²⁺ → N³⁺, N₂²⁺ and non-resonant vibration.
11. The v2 run scope: option (A) minimal with a pre-registered reuse rule, or (B) clean rerun. Also the treatment of the
    facility and O4 datasets.
12. Whether to add per-frame activity histograms to the driver (a `bridge_lib.jl` change) before any v2.
13. Whether D1–D6 or O1–O5 change at all. The default is **no**.
14. Whether two reconstructed Winters points above 200 eV (measured N-atom deposition minus measured dissociative ionization,
    digitized from Song et al. 2023 Fig. 19) suffice for the dissociation extension. They are not independent of Table 9 at the
    200 eV join, because the Cosby recommended set averages Cosby's and Winters' data.
