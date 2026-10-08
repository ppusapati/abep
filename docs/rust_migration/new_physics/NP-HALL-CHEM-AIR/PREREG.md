# NP-HALL-CHEM-AIR preregistration v1

| item | value |
|---|---|
| contract | `NP-HALL-CHEM-AIR`: the chemistry contract of the Hall AIR_PRIMARY family (a HallThruster.jl reaction set, not a new plasma model) |
| version | v1 |
| status | **`PREREGISTERED_NOT_IMPLEMENTED`**: no O / O2 Hall table built under it, no audit metric computed, no AIR Hall run, nothing admitted |
| mandate | A9.33 Q2 (owner, 2026-10-08): a narrow, preregistered, sourced Hall O / O2 contract for AIR_PRIMARY, analogous to NP-ICP-CHEM-AIR. No fabricated coefficients. AIR Hall stays NOT_EVALUATED until admitted. |
| reaction-set label | `abep-air-0.x` in `hallthruster_bridge/propellants_air/AIR_PINNED.toml` (new). Never `abep-n2n-*`, never `abep-icp-air-*`. |
| registered | 2026-10-08 on `b730764` + `14c16d1` (capability audit), branch `lane-hall-chem-air` |
| authoritative | `prereg_v1.json` |
| lock | `prereg_lock_v1.json`: sha256 of `prereg_v1.json`, this file and `capability_audit_v1.json` |
| drafted by | agent session. Not reviewed by the owner; nothing here is an owner decision. |

**Registered before** any O / O2 table is built into the Hall set, any omitted-process metric is computed and any AIR Hall
run. The free-stream composition numbers below were computed in this session from the frozen design states before the
composition rule was written. No Hall result informed any choice.

**Change rule.** The lock freezes the three files. Later changes are dated addenda or a v2, never edits. After any
table is built, a change to the domain, a threshold, a tier, the composition rule, the status vocabulary or the
admission rule is a v2.

## 1. Hard rules

- **HR-01** No change to these items (a Rust test asserts their sha256):
  - `hallthruster_bridge/propellants/n2_n.toml`, any N2 variant, `rate_validity.toml`, `PROVENANCE.md`;
  - `PINNED.toml`, i.e. abep-n2n-0.11, COMPLETE_FOR_P5_N2_VALIDATION;
  - `audit/configs/**`, the P5-N2 records and `bridge_lib.jl`;
  - HallMap admission, the credible-set rule (EMPTY) and the HallThruster.jl pin (v0.23.1, `bfb3019f`).
- **HR-02** The new label `abep-air-0.x` lives in a new file. One label never names two chemistry definitions.
- **HR-03** Every table has a citable source, recorded in its `.source` file and in `propellants_air/PROVENANCE.md`.
  No fabricated or fitted-to-close coefficient is allowed. Anything recalled from memory is labelled "verify".
- **HR-04** Atomic O is never replaced by N2, N or O2 data. An O-target process that points to a non-O table is a
  load-time MODEL_ERROR.
- **HR-05** Every rate file of an AIR configuration has a `propellants_air/rate_validity.toml` entry: verified with a
  mean-energy limit, or unresolved. A missing entry is an error, never a default.
- **HR-06** Published sources only. No LXCat data, no contact with authors or laboratories, no paywall or network-policy
  bypass. Every needed source that cannot be reached is listed (§9).
- **HR-07** AIR Hall stays NOT_EVALUATED (AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED) until the set is
  COMPLETE_FOR_PARAMETRIC_ENVELOPE. Admission is never a validation claim.
- **HR-08** A validity limit is never extended because a solver state reached a higher T_e.

## 2. Solver capability (capability_audit_v1)

The pinned solver can run N2 + N + O2 + O in one run (**CAPABLE_WITH_LIMITATIONS**). It cannot represent:
- L-01: heavy-particle chemistry, including every N / O cross reaction and NO / NO⁺;
- L-02: neutral-surface recombination in the channel;
- L-03: dissociative ion-wall neutralization;
- L-04: dissociative recombination and attachment, faithfully;
- L-05: negative ions without uncited built-in constants;
- L-06: O²⁺ without a one-to-one link;
- L-07: a multi-species feed through the pinned `run_case`.

How the limitations are handled:
- They become omitted processes, each with a bound or as UNBOUNDED_OMISSION.
- If a process the solver cannot represent is promoted, or kept as an uncertainty variant, the set is
  **NOT_REPRESENTABLE_IN_PINNED_SOLVER**.
- L-07 is solved by an additive driver function in a new file.

## 3. Species

The species rule is the NP-ICP-CHEM-AIR v1 materiality rule MR-0..MR-6, adopted by reference. It uses the same frozen
states and the same 1 % screen, so both air sets are judged by one standard.

| species | decision |
|---|---|
| O, O2, N2, N | retained |
| He | > 1 % in 14 ECSS_LT_LOW states: MATERIALITY_BOUND_REQUIRED (SB-He, state-resolved) |
| Ar | > 1 % in 6 ECSS_ST_HIGH states: MATERIALITY_BOUND_REQUIRED (SB-Ar, state-resolved) |
| NO | grid max 0.21 %, lowest ionization energy: MATERIALITY_BOUND_REQUIRED (SB-NO, blocks every state) |
| H, anomalous O | excluded by the screen |

Configured species and charge states:

| species | max charge | note |
|---|---|---|
| N | 2 | as abep-n2n-0.11 |
| N2 | 1 | |
| O2 | 1 | |
| O | 1 | O²⁺ is not configured (L-06) |

Not configured: N2²⁺ (re-assessed), O⁻ (L-05), NO / NO⁺ (L-01, SB-NO), He and Ar.

## 4. Domain D-HALL-AIR

- **Range.** T_e 2–30 eV (mean energy 3–45 eV). The low-threshold window, T_e 0.2–30 eV, applies to:
  - vibrational and rotational excitation;
  - O2 a¹Δg and b¹Σg⁺;
  - O fine structure and O(¹D).
- **Upper limit.** It is the tightest verified table limit of the set.
  - The N2 dissociation, electronic, vibrational and rotational tables stop at 45 eV. They are configured in every
    composition, because N2 is present in every registered state (y_O ≤ 0.84).
  - O2 dissociation supports 47 eV.
  - The O and O2 ionization, dissociative-ionization and elastic tables support 255 eV.
  - The same 45 eV is the frozen N2 completeness domain and the NP-ICP-CHEM-AIR D-CHEM limit.
- **Lower limit.** 2 eV is inherited from the N2 audit. It is not derived from O / O2 evidence.
- **EEDF.** Maxwellian.
- **DOM-AIR-01** (per table, bridge `chemistry_validity`, unchanged). The activity beyond a table's limit has share
  ≤ 1e-12, and no table is unresolved.
- **DOM-AIR-02** (audited domain). For every reaction, the activity share at 3/2 T_e > 45 eV is ≤ 1e-12. It is computed
  reaction-weighted, per saved frame.
- A run that fails either rule is OUT_OF_DOMAIN: not scoreable, and not a failure.

## 5. Composition (CE-AIR)

**What is registered.** The registered composition is the free stream of the 196 frozen states. The delivered
(valve-outlet) composition is **not registered**. `feed_state_closure_v2` is PROPOSED and is not consumed.

**Per-state quantities:**
- y_O, the O-nuclei share;
- f_O = n_O / (n_O + 2 n_O2);
- f_N = n_N / (n_N + 2 n_N2).

He and Ar are not carried in the Hall feed.

**Delivered-envelope rules:**
- **CE-01** The element ratio is the state's free-stream y_O. Species-selective collection is not modelled; this is
  evidence condition EC-COMP.
- **CE-02** f_O ∈ [0, f_O,fs] and f_N ∈ [0, f_N,fs]. The passive gas path can recombine atoms, but it has nothing to
  dissociate molecules with (verify VER-HA-05; OQ-HA-04).
- **CE-03** The hull over all states.

**Hall composition points** (label `COMPOSITION_HULL_CORNERS_NOT_INTERIOR_BOUNDS`). The Rust generator recomputes them
and must reproduce them exactly. Masses are the solver's own: O 15.999, N 14.007.

| id | y_O | f_O | f_N | w_O | w_O2 | w_N | w_N2 |
|---|---|---|---|---|---|---|---|
| CP-YLO-REC | 0.07943 | 0 | 0 | 0 | 0.08971 | 0 | 0.91029 |
| CP-YLO-DIS | 0.07943 | 0.99049 | 0.06325 | 0.08886 | 0.00085 | 0.05758 | 0.85272 |
| CP-YHI-REC | 0.83992 | 0 | 0 | 0 | 0.85701 | 0 | 0.14299 |
| CP-YHI-DIS | 0.83992 | 0.99049 | 0.06325 | 0.84886 | 0.00815 | 0.00904 | 0.13395 |

Hull extremes (full precision and state ids in the JSON):
- y_O,min = 0.0794 (ECSS_ST_HIGH, 180 km);
- y_O,max = 0.8399 (ECSS_LT_LOW, 230 km);
- f_O,max = 0.9905;
- f_N,max = 0.0633.

**Why corners do not bound.** The Hall response to composition is not shown to be monotonic, so corner results do not
bound interior compositions. A closure claim therefore needs every corner, plus EC-COMP. Non-closure under the corners is
never eligible for PHYSICALLY_NON_CLOSING. The AIR family addendum fixes this rule.

## 6. Processes

Process statuses:
- **IN_REPO_VERIFIED** – the data are in the repository, pinned and with a computed validity.
- **IN_REPO_PENDING_VERSION_OF_RECORD** – transcribed from the SONG2026 accepted manuscript. They can be built now;
  admission needs the version-of-record check or the owner's acceptance (OQ-HA-01).
- **SOURCE_IDENTIFIED_TO_ACQUIRE** – a source is known, but its data are not in the repository.
- **INCOMPLETE_EVIDENCE** – no usable source is in the repository.
- **BOUND_EVALUABLE** – a physical bound gives the audit values.

| id | reaction | solver | source (short) | tier | status |
|---|---|---|---|---|---|
| HA-N2N-01 | the 27 abep-n2n-0.11 nominal reactions | configured, referenced in place | abep-n2n-0.11 | 1 | IN_REPO_VERIFIED |
| HA-N2N-R1 | N²⁺ → N³⁺ (re-assessment) | not configured | Bell 1983 bound table | 3 | IN_REPO_VERIFIED (bound) |
| HA-N2N-R2 | N2 → N2²⁺ direct (re-assessment) | not configured | JPCRD 2023 statement envelope | 3 | IN_REPO_VERIFIED (bound) |
| HA-N2N-R3 | N2⁺ → N2²⁺ (re-assessment) | not configured | Tabata 2006 fit | 3 | IN_REPO_VERIFIED (bound) |
| HA-O-ION-01 | O → O⁺ | configured | BEB (KD2002, nominal) / Thompson 1995, via NIST SRD 107 | 1 | IN_REPO_VERIFIED |
| HA-O-EL-01 | O momentum transfer | configurable | BSR-1116 / II1990, not reachable | 1 | **INCOMPLETE_EVIDENCE** |
| HA-O-EXC-01 | O electronic excitation | configurable | BSR-1116 / Laher & Gilmore 1990, not reachable | 1 | **INCOMPLETE_EVIDENCE** |
| HA-O-EXC-02 | O fine structure | configurable | II1990, not in the repository | 3 | INCOMPLETE_EVIDENCE |
| HA-O-ION-02 | O → O²⁺ | not configured (L-06) | Thompson 1995 double, paywalled | 3 | INCOMPLETE_EVIDENCE |
| HA-O-ION-03 | O⁺ → O²⁺ | not configured (L-06) | Bell 1983 O II, not reachable | 3 | SOURCE_IDENTIFIED_TO_ACQUIRE |
| HA-O2-ION-01 | O2 → O2⁺ | configured | SONG2026 Table VII | 1 | IN_REPO_PENDING_VERSION_OF_RECORD |
| HA-O2-DI-01 | O2 → O⁺ + O (upper / lower) | configured | SONG2026 Table VII | 1 | IN_REPO_PENDING_VERSION_OF_RECORD |
| HA-O2-DI-02 | O2 → O²⁺ + O | not configured (L-06) | SONG2026 Table VII (bound table) | 3 | IN_REPO_PENDING_VERSION_OF_RECORD (bound) |
| HA-O2-ION-02 | O2²⁺ | not configured | SONG2026: no recommendation | 3 | INCOMPLETE_EVIDENCE |
| HA-O2-DIS-01 | O2 → O + O | configured | SONG2026 Table VI (Cosby), ≥ 13.5 eV only | 1 | pending VoR + **INCOMPLETE_EVIDENCE below 13.5 eV** |
| HA-O2-EL-01 | O2 momentum transfer | configured | SONG2026 Table V | 1 | IN_REPO_PENDING_VERSION_OF_RECORD |
| HA-O2-EXC-01 | O2 a¹Δg, b¹Σg⁺ | configurable | Huang 2022 / Tashiro 2006, not reachable | 1 | **INCOMPLETE_EVIDENCE** |
| HA-O2-EXC-02 | O2 Herzberg c, A′, A | configurable | Huang 2022 / Tashiro 2006, not reachable | 1 | **INCOMPLETE_EVIDENCE** |
| HA-O2-EXC-03 | O2 Schumann–Runge and higher | configurable | Huang 2022, paywalled | 2 | INCOMPLETE_EVIDENCE |
| HA-O2-VIB-01 | O2 vibrational | configurable | Laporta 2013, not reachable | 2 | SOURCE_IDENTIFIED_TO_ACQUIRE |
| HA-O2-ROT-01 | O2 rotational | configurable | Born model, parameters not transcribed | 3 | SOURCE_IDENTIFIED_TO_ACQUIRE |
| HA-O2-ATT-01 | O2 → O⁻ + O | not representable (L-04, L-05) | SONG2026 Table VIII (bound table) | 2 | IN_REPO_PENDING_VERSION_OF_RECORD (bound) |
| HA-O2P-DIS-01 | O2⁺ → O⁺ + O | configurable | Cherkani-Hassani 2006, paywalled | 2 | SOURCE_IDENTIFIED_TO_ACQUIRE |
| HA-N2P-DIS-01 | N2⁺ → N⁺ + N | configurable | none registered | 3 | INCOMPLETE_EVIDENCE |
| HA-DR-01 | dissociative recombination O2⁺, N2⁺ | not representable (L-04) | paywalled / verify | 2 | INCOMPLETE_EVIDENCE |
| HA-REC-02 | radiative / three-body recombination | not representable | none | 3 | INCOMPLETE_EVIDENCE |
| HA-IM-01 | ion-molecule set incl. NO⁺ formation, charge transfer | not representable (L-01) | Anicich 2003 (verify) | 2 | INCOMPLETE_EVIDENCE |
| HA-HN-01 | neutral-neutral and three-body | not representable (L-01) | Baulch 2005 (verify) | 3 | INCOMPLETE_EVIDENCE |
| HA-WALL-01 | ion wall / anode neutralization | structural | solver | 1 | IN_REPO_VERIFIED (structural) |
| HA-WALL-02 | O + wall → ½ O2 in the channel | not representable (L-02) | physical γ ∈ [0, 1] | 2 | BOUND_EVALUABLE |
| HA-WALL-03 | N + wall → ½ N2 in the channel | not representable (L-02) | physical γ ∈ [0, 1] | 2 | BOUND_EVALUABLE |
| HA-MS-01 | stepwise ionization from metastables | not configured | not reachable | 2 | INCOMPLETE_EVIDENCE |
| HA-SUP-01 | superelastic | not configured | none | 3 | INCOMPLETE_EVIDENCE |

**Tier 1** must be configured tables before any verdict is final:
- the N2/N set;
- HA-O-ION-01, HA-O-EL-01, HA-O-EXC-01;
- HA-O2-ION-01, HA-O2-DI-01;
- HA-O2-DIS-01, including below 13.5 eV, or an admissible envelope;
- HA-O2-EL-01, HA-O2-EXC-01, HA-O2-EXC-02;
- HA-WALL-01.

**Tier 2** must be assessed before the set is complete. **Tier 3** is included only if a bound exceeds the threshold.

## 7. Common rules

**Interpolation and extrapolation.**
- **IX-01** Tables are Maxwellian integrals on the HallThruster.jl grid. They are written by the admitted Rust integrator
  (`abep_chem::reference`), or are byte-identical to an existing builder's output.
- **IX-02** Linear in σ inside the tabulated range.
- **IX-03** σ = 0 below the first point, or a declared ramp from the cited threshold.
- **IX-04** The tail is a declared hold (zero for a resonance bound table). The validity limit is the highest mean energy
  at which the held tail is < 1 % of the rate, capped at 255 eV.
- **IX-05** DOM-AIR-01 and DOM-AIR-02.
- **IX-06** Variant members form unweighted scenario sets. They are never averaged and never narrowed.

**Conservation.**
- **CV-01** Charge and nuclei balance per equation (Rust load check).
- **CV-02** The header energy is ≥ the formation-energy change. Excess fragment energy is recorded as uncertainty.
- **CV-03** Ion neutralization returns the parent neutral.

**Uncertainty envelopes.**
- **UE-01** No fabricated coefficient.
- **UE-02** Only sourced or physical bounds.
- **UE-03** Members are unweighted.
- **UE-04** An envelope never replaces a tier-1 process that has no data.
- **UE-05** Source uncertainties are recorded, or marked NOT_STATED.

**Reuse.**
- **RU-01** Data are reused only with valid provenance, a matching domain and Hall applicability.
- **RU-02** N2/N tables are referenced in place (`../propellants/<file>`). Their validity entries are mirrored and must
  equal the source entries.
- **RU-03** v0 O/O2 tables stay immutable. The Hall set holds byte-identical rebuilds or copies, with the v0 sha256.
- **RU-04** Nothing from `plasma_chem.py` or `aochem.py` is used.

## 8. Omitted-process audit CA-HALL-AIR-v1

**Metrics and thresholds:**

| metric | threshold | basis |
|---|---|---|
| F_P | 0.01 | frozen `n2_completeness_audit_v1` |
| F_ion | 0.01 | frozen `n2_completeness_audit_v1` |
| F_S_s | 0.05 | frozen `n2_completeness_audit_v1` |
| F_e_loss (electron loss ÷ electron production by ionization) | 0.01 | copied from F_ion, as NP-ICP-CHEM-AIR |

**Rules:**
- **Ambiguity rule** (N2 addendum 1, verbatim):
  - U < T → EXCLUDE;
  - L > T → PROMOTE;
  - L < T < U → UNCERTAINTY VARIANT.
  - Bounds are taken over every nuisance choice.
- **Cross-check rule.** N2 addendum 2, verbatim.
- **Not representable.** If the pinned solver cannot represent a process and its verdict is PROMOTE or UNCERTAINTY
  VARIANT, the set is NOT_REPRESENTABLE_IN_PINNED_SOLVER.
- **Unbounded.** A process with no evaluable bound is UNBOUNDED_OMISSION. It blocks completeness unless the owner disposes
  of it (OQ-HA-06).
- **Denominators.** The best available configured set. Every verdict stays PROVISIONAL until all tier-1 processes exist.
  Today all of them would be.

**State basis.** A blind HallThruster.jl state envelope. No thrust, current, efficiency or closure quantity is used.

| axis | values |
|---|---|
| geometry | G-RP1 |
| B(z) shape | BZ-P5B16 |
| B_peak | BP-LO, BP-HI |
| V_d | VD-180, VD-350 |
| ṁ | MF-LO, MF-HI |
| composition corners | 4 |
| transport | sgb-screen-01..09 |
| chemistry | AIR-NOM, AIR-ALT (Thompson O, O2 DI lower, N2 DI lower, N elastic Wang) |

That is **576 runs**. Numerics follow the v1 envelope rule; the mode is vacuum.
- Eligible runs are converged, finite and in domain.
- Configurations are sha256-pinned snapshots. An assessed process is never in the configuration that generates the state.
- **Today: PREPARED_NOT_RUN** (no Julia in the container).

## 9. Sources that cannot be reached here

All of the following are blocked by the network policy, paywalled, or not in the repository:
- BSR-1116 (Tayal & Zatsarinny 2016) and its supplement;
- the NIST open reprints of Itikawa & Ichimura 1990, Laher & Gilmore 1990 and Bell 1983 (O II);
- the SONG2026 version of record and supplement;
- Huang 2022;
- Tashiro 2006 and Laporta 2013 (arXiv);
- Cherkani-Hassani 2006;
- Peverall 2001 and Peterson 1998;
- Anicich 2003, Kossyi 1992 and Baulch 2005;
- the NIST SRD 107 NO / He / Ar entries and Itikawa 2016 (NO);
- Thompson 1995 (double ionization).

None was worked around.

## 10. Set status and admission

**Set statuses:**
- **INCOMPLETE_EVIDENCE** – a tier-1 process is missing or pending, a species bound is open, an unbounded omission is
  undisposed, or a verdict is provisional.
- **NOT_REPRESENTABLE_IN_PINNED_SOLVER**
- **COMPLETE_FOR_PARAMETRIC_ENVELOPE**

COMPLETE_FOR_PARAMETRIC_ENVELOPE is admission of the reaction set for the NP-HALL-PARAMETRIC-ENVELOPE AIR family only. It
is **not a validation claim**: results stay PARAMETRIC / NOT_VALIDATED, and the credible set and HallMap are unaffected.

**Admission requires:**
- **AD-HA-01** This preregistration and its lock are committed.
- **AD-HA-02** Every tier-1 process is configured with a verified validity entry. The SONG2026 tables are checked against
  the version of record, or the owner accepts the accepted-manuscript values.
- **AD-HA-03** Atomic O has its own ionization, momentum-transfer and excitation tables.
- **AD-HA-04** Every tier-2 and tier-3 process has a final verdict on the complete denominator. There is no undisposed
  unbounded omission and no NOT_REPRESENTABLE outcome.
- **AD-HA-05** SB-NO is resolved. SB-He and SB-Ar are resolved, or carried state-resolved with the owner's acceptance.
- **AD-HA-06** The label carries COMPLETE_FOR_PARAMETRIC_ENVELOPE, with a history line.
- **AD-HA-07** The Rust validators pass.

**Today: NOT ADMITTED, INCOMPLETE_EVIDENCE.**

## 11. Build plan

**`hallthruster_bridge/propellants_air/`** (new) holds:
- `AIR_PINNED.toml`;
- `rate_validity.toml`, with N2/N entries mirrored and keyed `../propellants/<file>`;
- `PROVENANCE.md`;
- `xs/`;
- the tables and their `.source` files;
- `air_nominal.toml` and `air_alt.toml`.

The bridge reads `rate_validity.toml` from each case's `rate_dir`, so the bridge needs no change.

**`hallthruster_bridge/audit_air/`** holds the snapshots + MANIFEST, the bound tables, the Julia state-envelope script and
a local run script.

**Rust (additive):**
- an `abep-hall` module for the AIR set: loader, conservation and O-target guards, Hall-isolation pins;
- an `abep-chem` example that renders the tables from `xs/` with the admitted integrator.

**AIR family.** A new NP-HALL-PARAMETRIC-ENVELOPE addendum, never an edit of v1, adds the AIR family:
- It is committed with its lock before any AIR run.
- Its case set is generated by Rust.
- Its launch manifest is generated only once this set is COMPLETE_FOR_PARAMETRIC_ENVELOPE.

## 12. Verify items and owner questions

**Verify items:**
- **VER-HA-01** 12.2 eV O2⁺ threshold (text layer).
- **VER-HA-02** 48.77 eV O²⁺ (OCR).
- **VER-HA-03** The NIST Thompson column: partial or counting total.
- **VER-HA-04** IE(NO) 9.26 eV (memory).
- **VER-HA-05** The passive gas path does not dissociate.
- **VER-HA-06** The solver's element masses.

**Owner questions:**
- **OQ-HA-01** SONG2026: version-of-record check (drafted) or accept the accepted-manuscript values?
- **OQ-HA-02** O ionization nominal: BEB (drafted) or Thompson?
- **OQ-HA-03** Species bounds: as NP-ICP-CHEM-AIR (drafted)?
- **OQ-HA-04** Accept the composition envelope rule and EC-COMP?
- **OQ-HA-05** Lawful acquisition of the tier-1 sources.
- **OQ-HA-06** Unbounded omissions: block (drafted) or accept them as recorded omissions?
- **OQ-HA-07** The label `abep-air-0.x`.

## 13. Conflicts

- **CONF-HA-01** CLAUDE.md item 4 sequencing and the A9.30 ICP-only note: resolved by A9.33 Q2 (narrow Hall contract).
- **CONF-HA-02** The O/O2 completeness DRAFT stays unchanged. Its thresholds and tiers are reused here.
- **CONF-HA-03** v0 README "moving a table … is a later owner-approved model change": A9.33 Q2. A separate directory and
  label; v0 is immutable.
- **CONF-HA-04** `run_case` feeds N2 only, and `bridge_lib.jl` is pinned: an additive driver.
- **CONF-HA-05** The proposed `abep-oo2-0.x` label: OQ-HA-07.
- **CONF-HA-06** v1 envelope AIR NOT_EVALUATED: a new addendum; v1 is unchanged.
