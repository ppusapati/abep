# NP-ICP-CHEM-AIR preregistration v1

| item | value |
|---|---|
| contract id | `NP-ICP-CHEM-AIR` (chemistry contract of `NP-ICP-NEUTRALIZER`; not a separate plasma model) |
| preregistration / contract version | v1 / `1` |
| status | **`PREREGISTERED_NOT_IMPLEMENTED`** (docs only: no table built, no rate computed, nothing admitted) |
| mandate | A9.30 secs. 3-4 (`OD_2026_10_05_A9_30_*`), verbatim lines traced in §17 |
| parent | NP-ICP-NEUTRALIZER v1 (`prereg_v1.json` `5d496ea6…`, lock `e98747e0…`) |
| target crates | `abep-chem` (registry, validity, integrator, builders); `abep-icp` (consumer) |
| registered | 2026-10-05 on `3e1891b` (local integration head with the A9.30 record), branch `lane-np-icp-chem-air` |
| machine-readable | `prereg_v1.json` (same folder). If the two disagree, the JSON is authoritative. |
| lock | `prereg_lock_v1.json` (sha256 of both files, frozen at commit) |
| drafted by | agent session (lane NP-ICP-CHEM-AIR). Not reviewed by the owner. Nothing here is an owner decision. |

**What this is.** The narrow chemistry contract A9.30 sec. 3 asks for: which species and which processes the active
13.56 MHz RF/ICP neutralizer model may use, where each process comes from, what domain it is valid in, how missing
evidence fails closed, and what must be true before AIR_PRIMARY (and, independently, XE_CONTINGENCY) chemistry is
admitted. A9.30 resolves the parent's OQ-NPICP-06 / CONF-05 through this contract.

**What this is not.**
- Not an implementation and not a rate table. No rate coefficient is computed here.
- Not a Hall chemistry change. `hallthruster_bridge/` is read-only for this contract; abep-n2n-0.11 is untouched.
- Not a port of `plasma_chem.py` or `aochem.py`; nothing is taken from either.
- Not a reopening of the P5 Hall campaign or of the old multi-family plasma models.
- Not a claim that the chemistry is complete. Today neither mode is admitted (§11).

**Change rule.** The lock freezes both files. Later changes are dated addenda in this folder, never edits. A change
to the species rule, a threshold, the domain, a metric, the composition grid, a tier or an admission criterion after
any table is built is a v2. Re-applying the species rule to a newly registered delivered composition (MR-6) is an
input addendum, not a rule change.

**Implementation gate.** No implementation before this preregistration is committed. After the commit the build plan
(§12) may start, one provenance-backed table per commit, and abep-chem / abep-icp may implement the registry loader,
validity semantics, status propagation and fail-closed tests (§13). The RF/ICP model may be developed structurally in
parallel; AIR_PRIMARY predictive admission waits for §11.

**Not blocking.** This gate does not block provenance/config, atmosphere, TPMC, intake, compressor, feed or Rust
infrastructure (A9.30 sec. 4). MR-6 only consumes their future outputs.

**No invented numbers.** Every number is computed here from the frozen design states, read from a sha256-named
repository record, copied from the frozen N2 completeness rule, a declared grid or domain choice marked *drafted*, or
marked *verify*. No cross section, rate coefficient, recombination probability or efficiency is stated.

---

## 1. Governing records (sha256 in the JSON)

- `docs/decisions/OD_2026_10_05_A9_30_PUSH_AUTHORIZATION_O_O2_CHEMISTRY_AND_BUS_BOUNDARY_RULINGS.md` (`17401e98…`): secs. 3-4 (verbatim mandate; traced in scope_traceability)
- `docs/decisions/OD_2026_10_05_A9_30_push_authorization_o_o2_chemistry_and_bus_boundary_rulings.json` (`1f61b11e…`): machine-readable companion; 'resolves' block (OQ-NPICP-06 / CONF-05)
- `docs/decisions/OD_2026_10_05_A9_29_RUST_PLAN_V3_1_RULINGS_AND_START_AUTHORIZATION.md` (`5c223f6d…`): sec. 4 RM-OQ-12 (atmospheric species relevant to the registered environment; Xe contingency; species-resolved ionization / dissociation outputs; no invention; validation basis)
- `docs/decisions/OD_2026_10_05_A9_29_rust_plan_v3_1_rulings_and_start_authorization.json` (`51645f0e…`): A9.29 machine-readable
- `CLAUDE.md` (`38b24419…`): rules 3, 6, 10; next-work item 2 (completeness tiers, F_P / F_ion / F_S rule), item 4 (A9.30 note), item 5 (rate_validity.toml, chemistry_trustworthy, no silent extrapolation)
- `docs/EVIDENCE.md` (`a2950352…`): evidence levels 1-7, quantity types, four attributes of every input
- `docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_v1.json` (`5d496ea6…`): parent model (authoritative JSON)
- `docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/PREREG.md` (`3af97940…`): parent model (readable)
- `docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/prereg_lock_v1.json` (`e98747e0…`): parent lock

Evidence records used: 29 files, each with its sha256 in `evidence_records_used` (design states, dataset manifest,
Hall chemistry pins, frozen N2 completeness rule and addenda, O/O2 source matrix, O/O2 completeness DRAFT, v0 tables
and manifests, GK2008 registration, feed-state closure v2, upstream and ICP ICDs, architecture config, and the legacy
modules read as context only).

## 2. Exclusions

| id | rule |
|---|---|
| EXC-01 | No reopening of the P5 Hall-transport campaign; no Hall chemistry change; hallthruster_bridge/ is read-only for this contract (A9.30 sec. 3). |
| EXC-02 | No port of plasma_chem.py, wholesale or in part: no Arrhenius RATES, EPS_C, E_DISS, Chamber defaults or solve_global; no rate inherited because plasma_chem.py or aochem.py used it (A9.30 sec. 3). |
| EXC-03 | No old multi-family plasma model (rf_hall / ecr_hall interstage, pre-ionizer) chemistry is reopened; their registries are citation sources only (A9.30 sec. 3). |
| EXC-04 | No LXCat-distributed data (repository precedent, PROVENANCE.md); published sources only; no contact with authors or laboratories; no paywall bypass. |
| EXC-05 | No N2-only (or N, O2) surrogate for atomic O, no scaled N2 table for O, no O-target process mapped to non-O data (A9.30 sec. 3). |
| EXC-06 | No fabricated coefficient, no fitted coefficient to close a balance, no requirement threshold in raw chemistry output. |

## 3. Species set

### 3.1 Computation (free-stream, 196 registered design states)

- Input: `abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json` (`60073e21…`, 196 states, via
  `config/environment/design_state_set_ref_v1.json`) and the dataset manifest `atmosphere_msis21_orbit_v1.json`
  (`f06416b1…`) for species the file does not carry.
- Method: x_s = n_s / (n_O + n_N2 + n_O2 + n_N + n_He + n_Ar) per state, from the stored densities; min / median / max
  over all 196 states and over the 47 ECSS_LT_MODERATE (nominal-scenario) states; counts of states above 1 % and
  0.1 %. Checks: the six densities sum to the stored n_total within 2.2e-16 relative; the computed x_s equal the stored
  `x_` fields within 3.3e-16. H, NO and anomalous O are not in the file; their values are the manifest's recorded
  maximum number-density share over the full 116,736-row grid, used as recorded.
- Script: standard-library Python in the agent scratchpad (not committed); its text is embedded in the JSON
  (`species_set.computation.script`, sha256 `600d7515…`); output sha256 `638521f3…`.
- Scenarios: ECSS_LT_HIGH 49, ECSS_LT_LOW 48, ECSS_LT_MODERATE 47, ECSS_ST_HIGH 52. Altitudes: 180, 195, 215, 230 km.
- This is the **free-stream** composition. The ICP sees the delivered feed (§3.5).

| species | min | median | max | states > 1 % | states > 0.1 % | nominal scenario (min / median / max) | max at |
|---|---|---|---|---|---|---|---|
| O | 0.05045 | 0.5144 | 0.8596 | 196 / 196 | 196 / 196 | 0.1713 / 0.5302 / 0.7842 | `ds2:ECSS_LT_LOW:alt230:lat-70.0000:lst0:lon0:doy229` |
| N2 | 0.07989 | 0.4581 | 0.8844 | 196 / 196 | 196 / 196 | 0.1937 / 0.4397 / 0.776 | `ds2:ECSS_ST_HIGH:alt180:lat+71.0000:lst0:lon0:doy184` |
| O2 | 0.003543 | 0.02079 | 0.07832 | 149 / 196 | 196 / 196 | 0.008869 / 0.02724 / 0.06692 | `ds2:ECSS_ST_HIGH:alt180:lat-78.0000:lst3:lon120:doy229` |
| N | 4.514e-05 | 0.005582 | 0.08873 | 40 / 196 | 181 / 196 | 0.0007221 / 0.005263 / 0.01551 | `ds2:ECSS_ST_HIGH:alt230:lat-66.0000:lst12:lon240:doy1` |
| He | 4.96e-05 | 0.0008581 | 0.06801 | 14 / 196 | 88 / 196 | 0.0001228 / 0.001156 / 0.00887 | `ds2:ECSS_LT_LOW:alt230:lat-84.0000:lst0:lon60:doy184` |
| Ar | 1.393e-05 | 0.0005291 | 0.01565 | 6 / 196 | 73 / 196 | 6.509e-05 / 0.000438 / 0.002357 | `ds2:ECSS_ST_HIGH:alt215:lat+37.0000:lst6:lon240:doy184` |

Species not carried by the design-state file (dataset manifest, max share over the grid):

| species | ECSS_LT_LOW | ECSS_LT_MODERATE | ECSS_LT_HIGH | ECSS_ST_HIGH |
|---|---|---|---|---|
| H | 0.001639 | 9.242e-05 | 1.354e-05 | 6.473e-06 |
| NO | 0.0003533 | 0.001843 | 0.001718 | 0.002106 |
| ANOMALOUS_O | 2.019e-13 | 2.563e-13 | 8.758e-13 | 8.59e-13 |

Where the exceedances sit: He > 1 % only in ECSS_LT_LOW (14 states, 195-230 km); Ar > 1 % only in ECSS_ST_HIGH (6 states,
180-230 km); N > 1 % in ECSS_ST_HIGH 19, ECSS_LT_HIGH 15, ECSS_LT_MODERATE 6. 20 states have He or Ar above 1 %.
Free-stream O share of the O nuclei (n_O / (n_O + 2 n_O2)): 0.266-0.99 (median 0.91); N share of the N nuclei: 2.6e-05-0.0633.

### 3.2 Materiality rule (preregistered)

| id | rule |
|---|---|
| MR-0 | Input: X_s = max over the 196 registered design states of the free-stream mole fraction x_s (species carried by the file), or the dataset manifest's recorded max share over the full grid (H, NO, anomalous O; a node-based value used as recorded). Free-stream is used because it is the only registered composition (MR-6). |
| MR-1 | Screen threshold x_screen = 0.01 (1 %). *Basis:* Copied from the frozen F_ion and F_P promotion thresholds (n2_completeness_audit_v1): a feed species with X_s <= 0.01 can supply more than 1 % of ion production or inelastic power only if its per-particle rate exceeds the feed-weighted mean of the retained species by the factor 0.01 / X_s. MR-5 covers the case where such a factor is expected from threshold position alone. *Disclosure:* The fractions were computed in this session before the threshold was written down; the threshold is the frozen rule's value, no other value was tried, and no rate was computed. |
| MR-2 | Core retention (AIR_PRIMARY): a species named in A9.30 sec. 3 (O, O2, N2, N) is retained if X_s > x_screen in at least one design state. |
| MR-3 | Process-required retention: a species produced or consumed by a retained process is retained even where its feed fraction is below the screen (ions of retained ionization channels; O and N as dissociation / DI products). Its delivered feed fraction is passed through, never dropped. |
| MR-4 | Screen-passing non-core species: X_s > x_screen and not named in A9.30 sec. 3 -> MATERIALITY_BOUND_REQUIRED. Not added, not dropped. Resolved by the species bound SB (completeness_audit CA-07). Until resolved, every composition in which x_s > x_screen gives INCOMPLETE_EVIDENCE for AIR_PRIMARY (state-resolved); compositions with x_s <= x_screen are unaffected. |
| MR-5 | Low-threshold exception: a species with X_s <= x_screen whose first ionization energy is below the lowest ionization threshold among retained feed species (12.2 eV, header of the O2 -> O2+ v0 table; verify, VER-CHEM-01) is MATERIALITY_BOUND_REQUIRED for F_ion (its F_P / F_S remain screened). *Basis:* For thresholds well above T_e the Maxwellian rate falls roughly as exp(-E_th / T_e) (Maxwellian-tail property; textbook form verify, VER-CHEM-10), so a lower threshold can raise the per-particle ionization rate by more than 0.01 / X_s at the low-T_e end of the domain. Excitation thresholds of the retained molecules already lie at or below T_e (vibrational, rotational, O2 a1Delta_g 0.98 eV), so no comparable advantage is expected there. |
| MR-6 | Composition basis update: when the upstream chain registers delivered compositions per design state (IF-ICP-FEED-v1 x_s; under G-REUSE the Hall-processed exhaust from an admitted Hall member), MR-0..MR-5 are re-applied to them in a dated addendum, with the same threshold. Species may move in either direction. Upstream composition changes (wall recombination O -> O2 in intake / compressor, heterogeneous NO formation, species-selective collection G-02) are upstream inputs, never modelled here. |
| MR-7 | XE_CONTINGENCY retains Xe (A9.30 sec. 3 'Xe for contingency operation'; A9.19) independently of the atmosphere. No air species in Xe mode in v1; mixed Xe / air compositions are OUT_OF_DOMAIN in v1 (OQ-CHEM-10). |

### 3.3 Application

| species | X_s | decision | evidence |
|---|---|---|---|
| O | 0.8596 | RETAINED (MR-2; MR-3 product of O2 dissociation / DI) | x > 0.01 in 196/196 states; min 0.05045, median 0.5144 |
| N2 | 0.8844 | RETAINED (MR-2) | x > 0.01 in 196/196 states; min 0.07989, median 0.4581 |
| O2 | 0.07832 | RETAINED (MR-2) | x > 0.01 in 149/196 states; min 0.003543, median 0.02079 |
| N | 0.08873 | RETAINED (MR-2; MR-3 product of N2 dissociation / DI) | x > 0.01 in 40/196 states (ECSS_ST_HIGH 19, ECSS_LT_HIGH 15, ECSS_LT_MODERATE 6); min 4.514e-05, median 0.005582 |
| He | 0.06801 | MATERIALITY_BOUND_REQUIRED (MR-4; SB-He) | x > 0.01 in 14/196 states, all ECSS_LT_LOW at 195-230 km; nominal-scenario max 0.00887; median 0.0008581 |
| Ar | 0.01565 | MATERIALITY_BOUND_REQUIRED (MR-4; SB-Ar) | x > 0.01 in 6/196 states, all ECSS_ST_HIGH at 180-230 km; nominal-scenario max 0.002357; median 0.0005291 |
| H | 0.001639 | EXCLUDED_BY_SCREEN (MR-1) | grid max share 0.164 % (ECSS_LT_LOW), <= 0.0092 % in the other scenarios; margin 0.01 / X_s = 6.1; IE(H) 13.598 eV (verify, VER-CHEM-11) is not below 12.2 eV, so MR-5 does not apply |
| NO | 0.002106 | MATERIALITY_BOUND_REQUIRED for F_ion (MR-5; SB-NO) | grid max share 0.211 % (ECSS_ST_HIGH), 0.184 % (ECSS_LT_MODERATE); not resolved per design state (dropped from the dataset), so SB-NO applies to every composition; IE(NO) 9.26 eV (verify, VER-CHEM-11) < 12.2 eV |
| anomalous O | 8.758e-13 | EXCLUDED_BY_SCREEN (MR-1) | grid max share 8.76e-13 |
| Xe | - | RETAINED for XE_CONTINGENCY only (MR-7) | supply mode, not atmosphere |
| free-stream ions | - | NOT REPRESENTED | not in the registered environment (NRLMSIS has no ion output) |

So: **O, O2, N2, N are retained** (AIR_PRIMARY), **Xe** for XE_CONTINGENCY. **H** and **anomalous O** are excluded with
numbers. **He and Ar cannot be excluded by mole fraction**: they exceed 1 % in 14 and 6 registered states. **NO** is
below the screen but has the lowest ionization energy (MR-5). None of the three is added; each needs a preregistered
species bound (SB-He, SB-Ar, SB-NO; §9) or an owner ruling (OQ-CHEM-01, -02). This departs from the species list
A9.30 expected (CONF-CHEM-10).

### 3.4 Retained species, ions and products

- AIR_PRIMARY neutrals: O, O2, N2, N; ions: O+; O2+; N2+; N+; N^2+ (products of the reused nominal N2/N channels AIR-ION-07..09; kept unless an ICP-domain bound excludes them).
- Conditional on the completeness audit: O^2+ (AIR-ION-11..13); N2^2+ (variant AIR-ION-10); NO+ and NO (AIR-IM-01, SB-NO, AIR-WALL-05); O- (NEG-CRIT); He / Ar and their ions (SB-He, SB-Ar).
- Excited states: not tracked as species; energy stored and released per AIR-EXC-12 disposition; metastable densities appear only inside the AIR-ION-15 bound method.
- XE_CONTINGENCY: Xe, Xe+; conditional: Xe^2+ (XE-ION-02); Xe2+ dimer (XE-REC-01).
- Evidence modes: EM-N2 uses the N2/N subset (CG-N2); EM-O2B uses the full AIR set because the ICP itself dissociates O2 into atomic O even with a NO_ATOMIC_O feed (OQ-CHEM-11); EM-AR has no Ar set here (parent CHG-05); EM-XE uses the XE set.

### 3.5 How composition enters

- The ICP sees the delivered feed, not the free stream. Composition enters only through IF-ICP-FEED-v1 x_s (parent IN-04 / IN-05) from the upstream chain (intake -> filter -> compressor -> plenum / feed), and under G-REUSE (ICD ICP-26) through the Hall exhaust / residual propellant reaching the ICP (CFG-FLIGHT-HALL-ON needs an admitted Hall member; CFG-CAP-OFF uses the cold delivered flow through the H-1 gas path).
- Gas-path composition change: NOT REGISTERED. No admitted upstream producer registers O recombination, NO formation or species-selective collection. docs/architecture_comparison/feed_state_closure/feed_state_closure_v2.json carries PROPOSED, model-derived valve-outlet x_O (FC-05: nominal 0.459-0.654, scenario range 0.211-0.659) from the Python reference chain with unsourced wall-collision heuristics (UPSTREAM_ICD G-16) and literature-class gamma priors; it is not consumed (CONF-CHEM-09).
- Flight design-state point results are NOT_EVALUATED (parent IN-05) until a delivered composition is registered. The completeness audit and admission use the bounding composition grid CG-AIR, which spans every O / O2 and N / N2 split of the registered nuclei inventory.

## 4. Domain D-CHEM

| item | value |
|---|---|
| T_e | 2-30 eV (mean energy 3-45 eV) |
| low-threshold window | T_e 0.2-30 eV for: N2 and O2 vibrational, N2 and O2 rotational, O2 a1Delta_g (0.98 eV) and b1Sigma_g+ (1.63 eV), O fine structure, O(1D) (1.967 eV), N(2D) |
| basis | drafted: reuse of the frozen N2 domain (upper limit = tightest verified table limit, 45 eV mean energy; also the v0 O/O2 DRAFT cap; parent DOM-02). The 2 eV lower limit is inherited from the Hall audit, not derived from ICP evidence (OQ-CHEM-03). A converged state outside D-CHEM is OUT_OF_DOMAIN. |
| EEDF | Maxwellian (parent DOM-13; flag MAXWELLIAN_ASSUMED) |
| pressure | p_ICP ≤ 13.3322 Pa: parent DOM-05 (H-LIEB bound p < 100 mTorr = 13.3322 Pa); three-body and other pressure-dependent processes are excluded only by a bound evaluated up to this pressure |
| gas temperature | each heavy-particle, recombination and surface source applies only within its stated temperature range (IX-07) |
| composition | AIR: CG-AIR (completeness_audit.CA-05); XE: pure Xe; EM-N2: CG-N2; mixed Xe / air: OUT_OF_DOMAIN in v1 |
| validity vs domain | Table validity (max_mean_energy_eV, source-supported, capped at 255 eV) and the contract domain (<= 45 eV mean energy) are separate checks; both must pass. chemistry_trustworthy-style validity certifies the tables, not completeness. |

## 5. Common rules

**Interpolation / extrapolation (every table and rate):**

| id | rule |
|---|---|
| IX-01 | The rate is the Maxwellian integral of the registered cross-section representation evaluated directly at T_e (parent EQ-06, abep-chem integrator); the .dat table (mean energy 0-300 eV, 1 eV step, HallThruster format) is a cross-check only (parent UQ-06). For rate-fit sources the representation is the published fit with its parameters. |
| IX-02 | Inside the tabulated range: linear interpolation of sigma(E) unless the builder declares another rule and records its transformation uncertainty (precedent: elastic_N2_song2023 linear vs log-log ~2 %). |
| IX-03 | Below the first tabulated point: sigma = 0 or a declared ramp from the cited threshold; the choice and its rate effect at T_e = 2, 5 and 10 eV are recorded in the table manifest (precedent: v0 DI ramp sensitivity). |
| IX-04 | Above the last tabulated point: a declared hold or zero. The validity limit max_mean_energy_eV is the highest mean energy at which the held tail carries < 1 % of the Maxwellian rate, capped at 255 eV (rate_validity.toml convention). |
| IX-05 | Out-of-table activity: same reaction-weighted semantics as chemistry_trustworthy. In the 0-D model a reaction's activity n_e n_target k_r is wholly inside or beyond its limit; any active reaction with 3/2 T_e above its max_mean_energy_eV (activity share beyond limit > 1e-12) makes the result OUT_OF_DOMAIN, naming the reaction. Never a silent extrapolation, never a hold beyond the validity limit. |
| IX-06 | A registry file without a validity entry is MODEL_ERROR; an 'unresolved' entry makes the result INCOMPLETE_EVIDENCE (parent DOM-03). |
| IX-07 | Rate-coefficient sources (heavy-particle, recombination, surface) are evaluated only inside the source's stated temperature range; outside -> OUT_OF_DOMAIN. No Arrhenius extrapolation; no plasma_chem.py rate. |
| IX-08 | Variant and scenario members (DI upper / lower, N elastic OPM / Wang, Johnson-low, O ionization Thompson / BEB, envelopes) form an unweighted scenario set (parent UQ-02); never averaged, never narrowed (parent UQ-07). |

**Conservation (every process):**

| id | rule |
|---|---|
| CV-01 | Every process has an integer stoichiometry over registered species including e; charge sum_s nu_s Z_s = 0 exactly. |
| CV-02 | Nuclei per element (O, N, Xe) are conserved exactly; the mass balance follows with the electron mass explicit. |
| CV-03 | Energy: the electron loses the registered header energy E_r per event. For ionization / dissociation / DI, E_r >= the formation-energy change of the products (ground-state-neutral reference, parent EQ-18); any excess (fragment kinetic energy) is not added and is recorded as energy-loss uncertainty (N2 DI convention). Excitation stores E_r in the state, released per the disposition pair. Elastic: recoil 3 m_e / M (T_e - T_g) (parent EQ-07, VER-02). Attachment removes the electron and its energy. |
| CV-04 | Surface: atom recombination conserves nuclei; the released dissociation energy is split beta to the wall and 1 - beta to the desorbing molecule (beta envelope). Ion neutralization releases the formation energy at the surface (parent VER-12). |
| CV-05 | A registry entry failing CV-01 / CV-02, or with E_r below the formation-energy change, is a MODEL_ERROR at load time (fail-closed test FC-CHEM-03). |

**Status vocabulary:**

- `IN_REPO_VERIFIED`: Data in the repository, sha256-pinned, provenance read and recorded, validity computed (verified entry or manifest support limit), domain and RF/ICP applicability checked. Registration in the ICP registry (validity entry, PROVENANCE row) still follows the build plan.
- `SOURCE_IDENTIFIED_TO_ACQUIRE`: A published source is identified, but its data are not in the repository in verified form: not transcribed, or transcribed only as an unpromoted DRAFT whose version-of-record check is outstanding, or a 'verify' citation to be confirmed.
- `INCOMPLETE_EVIDENCE`: No usable published source is identified over the domain, or the identified source leaves a known gap that the build cannot close without an owner decision. The model exposes INCOMPLETE_EVIDENCE, or an envelope where UE-02 allows.

Evidence class: MEASURED / RECOMMENDED_COMPILATION / THEORY / RECONSTRUCTED / ASSUMED_BOUND, plus docs/EVIDENCE.md evidence_level (1-7) and quantity_type (measured, digitized, inferred, reconstructed, model-derived, assumed). Thresholds: Header energies come from cited level or thermochemical data (Itikawa & Ichimura 1990 Table 2.1, NIST ASD, the evaluated source); inferred headers (D0 + IE) are labelled 'inferred'; excitation headers are experimental vertical energies (N2 precedent).

## 6. Process registry

Each row in the JSON (`processes[]`) carries: reaction, threshold (value, basis, type), source and provenance (citation,
repository path + sha256 or 'to acquire'), evidence class / level / quantity type, stated uncertainty, domain,
conservation, interpolation / extrapolation rule, tier, materiality gate, status, repository state and, for reused data,
the A9.30 reuse check (provenance valid, domain matches, applicable to RF/ICP). The table below is a summary.

| id | reaction | threshold [eV] | source (short) | tier | status |
|---|---|---|---|---|---|
| AIR-ION-01 | e + O -> O+ + 2e | 13.618 | repo: v0 scenario pair (Thompson 1995 / BEB KD2002 via NIST SRD 107) | 1 | `IN_REPO_VERIFIED` |
| AIR-ION-02 | e + O2 -> O2+ + 2e | 12.2 | repo: `ionization_O2_song2026.dat` | 1 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-ION-03 | e + N2 -> N2+ + 2e | 15.58 | repo: `ionization_N2_song2023.dat` | 1 | `IN_REPO_VERIFIED` |
| AIR-ION-04 | e + N -> N+ + 2e | 14.534 | repo: `ionization_N.dat` | 1 | `IN_REPO_VERIFIED` |
| AIR-ION-05 | e + O2 -> O+ + O + 2e (upper / lower variants) | 18.738 | repo: v0 upper / lower pair (SONG2026 Table VII) | 1 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-ION-06 | e + N2 -> N+ + N + 2e (upper / lower variants) | 24.284 | repo: 2 reused table(s) | 2 | `IN_REPO_VERIFIED` |
| AIR-ION-07 | e + N2 -> N^2+ + N + 3e | 53.885 | repo: 1 reused table(s) | 3 | `IN_REPO_VERIFIED` |
| AIR-ION-08 | e + N -> N^2+ + 3e (nominal; x0.5 / x1.3 sensitivities) | 44.1354 | repo: 3 reused table(s) | 3 | `IN_REPO_VERIFIED` |
| AIR-ION-09 | e + N+ -> N^2+ + 2e (energy link) | 29.6013 | repo: 1 reused table(s) | 3 | `IN_REPO_VERIFIED` |
| AIR-ION-10 | e + N2 -> N2^2+ + 3e; e + N2+ -> N2^2+ + 2e (uncertainty variant only) | 42.9 | repo: 2 reused table(s) | 3 | `IN_REPO_VERIFIED` |
| AIR-ION-11 | e + O2 -> O^2+ + O + 3e | 53.89 | repo: `dissociative_ionization_O2_to_O_Z2plus_song2026.dat` | 3 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-ION-12 | e + O+ -> O^2+ + 2e (energy link) | - | Bell, Gilbody, Hughes, Kingston & Smith, JPCRD 12, 891 (1983), Eq. (1) O II row (open NIST reprint; same file  | 3 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-ION-13 | e + O -> O^2+ + 3e | - | to acquire / verify: Thompson, Shah & Gilbody 1995 double-ionization data (paywalled; not in the fetched NIST c | 3 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-ION-14 | e + O2 -> O2^2+ + 3e; e + O2+ -> O2^2+ + 2e | - | to acquire / verify: SONG2026: 'unable to recommend' (large spread among Maerk 1975, Sigaud 2013, Bull 2015, Ji | 3 | `INCOMPLETE_EVIDENCE` |
| AIR-ION-15 | e + X* -> X+ + 2e for X* in {O(1D), O(1S), O(5S), O2(a1Delta_g), O2(b1Sigma_g+), N2(A3Sigma_u+), N(2D), N(2P)} | - | to acquire / verify: BSR-1116 (Tayal & Zatsarinny, PRA 94, 042707 (2016); supplements paywalled) for O metastab | 2 | `INCOMPLETE_EVIDENCE` |
| AIR-DIS-01 | e + N2 -> N + N + e | 12.14 | repo: `dissociation_N2.dat` | 1 | `IN_REPO_VERIFIED` |
| AIR-DIS-02 | e + O2 -> O + O + e | 5.12 | repo: `dissociation_O2_song2026.dat` | 1 | `INCOMPLETE_EVIDENCE` |
| AIR-DIS-03 | e + O2+ -> O+ + O + e | - | Cherkani-Hassani et al., J. Phys. B 39, 5105 (2006), doi 10.1088/0953-4075/39/24/008 (crossed beam; paywalled; | 2 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-DIS-04 | e + N2+ -> N+ + N + e | - | no source registered in the repository (verify whether Bahati et al. 2001 / Tabata et al. 2006 tabulate this c | 3 | `INCOMPLETE_EVIDENCE` |
| AIR-EXC-01 | e + N2(X) -> e + N2(A, B, W, B', a, a', w, C) (8 states; Johnson-low variants) | 7.75, 8.04, 8.88, 9.67, 9.31, 9.92, 10.27, 11.19 | repo: 8 reused table(s) | 1 | `IN_REPO_VERIFIED` |
| AIR-EXC-02 | e + N2(v=0) -> e + N2(v_f), v_f = 1..10 | 0.288 .. 2.728 (headers eps_vf) | repo: 10 reused table(s) | 1 | `IN_REPO_VERIFIED` |
| AIR-EXC-03 | e + N2(j=0) -> e + N2(j=2), N2(j=4) | 0.0014801, 0.0049335 | repo: 2 reused table(s) | 3 | `IN_REPO_VERIFIED` |
| AIR-EXC-04 | e + O2(X) -> e + O2(a1Delta_g), O2(b1Sigma_g+) | 0.98, 1.63 | to acquire / verify: Huang, Zhang & Cheng, J. Phys. Chem. A 126, 2061 (2022) (recommended R-matrix; paywalled) | 1 | `INCOMPLETE_EVIDENCE` |
| AIR-EXC-05 | e + O2(X) -> e + O2(c1Sigma_u-, A'3Delta_u, A3Sigma_u+) (Herzberg) | 6.12, 6.27, 6.47 | to acquire / verify: Huang 2022 (paywalled) | 1 | `INCOMPLETE_EVIDENCE` |
| AIR-EXC-06 | e + O2(X) -> e + O2(B3Sigma_u-) (Schumann-Runge) and higher states | - | to acquire / verify: Huang 2022 (paywalled) | 2 | `INCOMPLETE_EVIDENCE` |
| AIR-EXC-07 | e + O2(v=0) -> e + O2(v_f) | - | Laporta, Celiberto & Tennyson, PSST 22, 025001 (2013), doi 10.1088/0963-0252/22/2/025001 (recommended; arXiv:1 | 2 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-EXC-08 | e + O2(N) -> e + O2(N') | - | Born / Gerjuoy-Stein form, SONG2026 Eq. (1) with B0, Q0 (model only; 'no experimental or accurate theoretical  | 3 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-EXC-09 | e + O(3P) -> e + O(1D), O(1S), O(3s 5S), O(3s 3S), allowed 3D (3s or 3d; verify), lumped remainder | O(1D) 1.967; others from Itikawa & Ichimura 1990 Table 2.1 a | to acquire / verify: BSR-1116: Tayal & Zatsarinny, PRA 94, 042707 (2016), doi 10.1103/PhysRevA.94.042707 (recom | 1 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-EXC-10 | e + O(3P_2) -> e + O(3P_1, 3P_0) | - | Itikawa & Ichimura, JPCRD 19, 637 (1990) Sec. 5.1 (Berrington R-matrix; open NIST reprint); large low-energy d | 3 | `INCOMPLETE_EVIDENCE` |
| AIR-EXC-11 | e + N(4S) -> e + N(2D), N(2P) and higher | - | to acquire / verify: Wang, Zatsarinny & Bartschat 2014 B-spline R-matrix e-N calculation (its MTCS is used via  | 2 | `INCOMPLETE_EVIDENCE` |
| AIR-EXC-12 | X* -> X + h nu (RADIATED) / X* + wall -> X (WALL_QUENCHED) / X* carried out (CARRIED_OUT) | - | parent IN-23 / CHG-08 / VER-11: sourced lifetimes and quenching per state (verify) | 2 | `INCOMPLETE_EVIDENCE` |
| AIR-SUP-01 | e + N2(v>0) / O2(v>0) / X* -> e (gains energy) + ... | - | no state-resolved relaxation set registered (closure limitation inherited from abep-n2n-0.7) | 3 | `INCOMPLETE_EVIDENCE` |
| AIR-EL-01 | e + N2 -> e + N2 | 0 | repo: `elastic_N2_song2023.dat` | 1 | `IN_REPO_VERIFIED` |
| AIR-EL-02 | e + N -> e + N (nominal OPM; Wang BSR variant) | 0 | repo: 2 reused table(s) | 1 | `IN_REPO_VERIFIED` |
| AIR-EL-03 | e + O2 -> e + O2 | 0 | repo: `elastic_O2_song2026.dat` | 1 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-EL-04 | e + O -> e + O | 0 | to acquire / verify: BSR-1116 MTCS, Tayal & Zatsarinny 2016 (recommended; supplement paywalled) or the SONG2026 | 1 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-NEG-01 | e + O2 -> O- + O | 4.2 | repo: `attachment_O2_song2026.dat` | 2 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-NEG-02 | e + O- -> O + 2e | - | Vejby-Christensen et al., PRA 53, 2371 (1996), doi 10.1103/PhysRevA.53.2371 (paywalled) | 2 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-NEG-03 | O- + O -> O2 + e; O- + N -> NO + e; O- + O2(a) -> products; O- + X+ -> O + X | - | no source surveyed (source matrix OO2-23 gap) | 2 | `INCOMPLETE_EVIDENCE` |
| AIR-NEG-04 | e + O2 + M -> O2- + M | - | no source registered (verify) | 3 | `INCOMPLETE_EVIDENCE` |
| AIR-REC-01 | e + O2+ -> O + O | - | to acquire / verify: Peverall et al. 2001 (paywalled; source matrix OO2-21) | 2 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-REC-02 | e + N2+ -> N + N | - | to acquire / verify: storage-ring measurements, e.g. Peterson et al., J. Chem. Phys. 108, 1978 (1998) (verify,  | 2 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-REC-03 | e + O+ -> O + h nu; e + N+ -> N + h nu; e + e + X+ -> X + e | - | none surveyed (source matrix OO2-24 gap) | 3 | `INCOMPLETE_EVIDENCE` |
| AIR-IM-01 | O+ + N2 -> NO+ + N; O+ + O2 -> O2+ + O; N2+ + O -> NO+ + N; N2+ + O -> O+ + N2; N2+ + O2 -> O2+ + N2; N+ + O2 -> O2+ + N / NO+ + O / O+ + NO; O2+ + N  | - | to acquire / verify: Anicich, JPL Publication 03-19 (2003), index of cation-molecule reaction kinetics (verify, | 2 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| AIR-IM-02 | O+ + O, O2+ + O2, N2+ + N2, N+ + N (fast neutral + slow ion) | - | owned by the parent (IN-17, CHG-06, VER-09: Phelps 1991 for nitrogen ions; verify) | n/a | `INCOMPLETE_EVIDENCE` |
| AIR-HN-01 | N + O2 -> NO + O; O + N2 -> NO + N; O + O + M -> O2 + M; N + N + M -> N2 + M; ... | - | no source registered; candidate (verify, VER-CHEM-08): Baulch et al., J. Phys. Chem. Ref. Data 34, 757 (2005); | 3 | `INCOMPLETE_EVIDENCE` |
| AIR-WALL-01 | X+ + wall -> X (atomic ions); O2+ / N2+ + wall -> O2 / N2 or 2 O / 2 N; N^2+ + wall -> N | - | structural: every ion reaching a surface returns as neutral nuclei (parent EQ-03 / EQ-09 / EQ-18; wall energy  | 1 (structural) | `INCOMPLETE_EVIDENCE` |
| AIR-WALL-02 | O + wall -> 1/2 O2 (probability gamma_O) | 5.12 | vessel / dielectric material OPEN (A9 binding statuses; P4 materials); sourced gamma only after selection (can | 1 (structural) | `INCOMPLETE_EVIDENCE` |
| AIR-WALL-03 | N + wall -> 1/2 N2 (probability gamma_N) | - | as AIR-WALL-02 (material OPEN; candidate verify: Kim & Boudart 1991 for silica) | 1 (structural) | `INCOMPLETE_EVIDENCE` |
| AIR-WALL-04 | fraction beta of the recombination energy deposited in the wall | - | no source (material OPEN) | 2 | `INCOMPLETE_EVIDENCE` |
| AIR-WALL-05 | O + N(ads) -> NO; N + O(ads) -> NO | - | no source registered | 3 | `INCOMPLETE_EVIDENCE` |
| AIR-WALL-06 | X* + wall -> X | - | no source (material OPEN); parent IN-23 | 2 | `INCOMPLETE_EVIDENCE` |
| AIR-NL-01 | X(volume) -> X(out) through the open ends, per species | - | repo: `prereg_v1.json` | 1 (structural) | `IN_REPO_VERIFIED` |
| AIR-NL-02 | delivered feed x_s (IF-ICP-FEED-v1) and background (parent IN-13) | - | upstream chain (abep-gaspath; for G-REUSE the Hall exhaust, ICD ICP-26); not registered today (MR-6) | 1 (input) | `INCOMPLETE_EVIDENCE` |
| XE-ION-01 | e + Xe -> Xe+ + 2e | 12.13 | to acquire / verify: Rejoub, Lindsay & Stebbings, PRA 65, 042713 (2002) (measured partial cross sections; paren | 1 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| XE-ION-02 | e + Xe -> Xe^2+ + 3e; e + Xe+ -> Xe^2+ + 2e | - | to acquire / verify: Rejoub et al. 2002 partials (verify) | 3 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| XE-EXC-01 | e + Xe -> e + Xe* (state-resolved or lumped with a sourced representative energy; includes the 6s metastables) | - | to acquire / verify: Goebel & Katz, Fundamentals of Electric Propulsion: Ion and Hall Thrusters, JPL (2008), re | 1 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| XE-EL-01 | e + Xe -> e + Xe | 0 | to acquire / verify: Goebel & Katz, Fundamentals of Electric Propulsion: Ion and Hall Thrusters, JPL (2008), re | 1 | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| XE-ION-03 | e + Xe* -> Xe+ + 2e | - | no source registered (verify) | 2 | `INCOMPLETE_EVIDENCE` |
| XE-REC-01 | e + Xe+ -> Xe + h nu; Xe+ + 2 Xe -> Xe2+ + Xe; e + Xe2+ -> Xe* + Xe | - | no source registered (verify) | 3 | `INCOMPLETE_EVIDENCE` |
| XE-EXC-02 | Xe* -> Xe + h nu / Xe* + wall -> Xe | - | parent IN-23 / VER-11 | 2 | `INCOMPLETE_EVIDENCE` |
| XE-WALL-01 | Xe+ / Xe^2+ + wall -> Xe | - | structural (parent EQ-03 / EQ-09 / EQ-18); energy terms parent VER-12 (verify) | 1 (structural) | `SOURCE_IDENTIFIED_TO_ACQUIRE` |
| XE-NL-01 | Xe(volume) -> Xe(out) | - | repo: `prereg_v1.json` | 1 (structural) | `IN_REPO_VERIFIED` |
| XE-IM-01 | Xe+ + Xe -> Xe + Xe+ | - | owned by the parent (IN-17, CHG-06; Miller et al., J. Appl. Phys. 91, 984 (2002), VER-09, verify) | n/a | `INCOMPLETE_EVIDENCE` |

**Status counts** (64 processes):

| mode | IN_REPO_VERIFIED | SOURCE_IDENTIFIED_TO_ACQUIRE | INCOMPLETE_EVIDENCE |
|---|---|---|---|
| AIR | 15 | 16 | 23 |
| XE | 1 | 5 | 4 |
| total | 16 | 21 | 27 |

Notes on the registry:
- Every N2/N table is reused **by reference** from abep-n2n-0.11 (43 tables pinned in `reuse_pins`); the Hall verdicts
  do not transfer, so each is re-assessed by the ICP audit (CA-11) and stays included unless a bound excludes it.
- The O/O2 v0 DRAFT tables (`docs/chemistry/o_o2/v0/`) are referenced by sha256. The O ionization pair is open NIST
  data (IN_REPO_VERIFIED). Every SONG2026 transcription waits for a version-of-record check (SOURCE_IDENTIFIED_TO_ACQUIRE).
- **Atomic O tier-1 gaps:** momentum transfer (AIR-EL-04) and electronic excitation (AIR-EXC-09) are not built.
- **O2 tier-1 gaps:** a / b and Herzberg excitation (AIR-EXC-04/05) and dissociation below 13.5 eV (AIR-DIS-02,
  admissible later as an envelope).
- Attachment / negative ions: O⁻ is **not represented** (electropositive treatment) only if NEG-CRIT (§9) passes;
  today it is not evaluable, so O2-bearing compositions are INCOMPLETE_EVIDENCE (parent DOM-12).
- AIR-IM-02 / XE-IM-01 (resonant charge exchange) and AIR-NL-02 (feed composition input) are listed for the
  process-class gate; they are owned by the parent or the upstream chain.

## 7. Reuse rule

- RU-01: Existing repository data are reused only where provenance is valid, the physical domain matches and the process applies to the RF/ICP model (A9.30 sec. 3); each reused process carries reuse_check_a9_30.
- RU-02: Reuse is by reference (path + sha256) to hallthruster_bridge/propellants and docs/chemistry/o_o2/v0; files are never copied, moved or edited. A changed byte breaks the pin and the registry load fails (MODEL_ERROR).
- RU-03: Hall-domain verdicts (abep-n2n-0.11 COMPLETE_FOR_P5_N2_VALIDATION) do not transfer to the ICP domain; every reused process is re-assessed by the ICP CA (CA-11).
- RU-04: No plasma_chem.py / aochem.py value is reused (EXC-02).

## 8. Uncertainty-envelope rule (insufficient evidence)

- UE-01: No fabricated coefficient. A missing required quantity yields INCOMPLETE_EVIDENCE.
- UE-02: An envelope is admissible only when every bound is sourced or a physical bound: [0, 1] probabilities (gamma, beta, quenching), zero-vs-hold tails, published channel-ambiguity columns, Cosby-only vs Cosby + dissociative excitation, radiated vs wall-quenched disposition, molecular-ion wall branching. Results are reported per member and as the envelope with flag CHEMISTRY_ENVELOPE; the validation status is unaffected.
- UE-03: Envelope members are unweighted, never averaged and never narrowed (parent UQ-02, UQ-07).
- UE-04: An envelope never stands in for a tier-1 process with no sourced data at all (e.g. O momentum transfer, O electronic excitation): those stay INCOMPLETE_EVIDENCE.
- UE-05: Atomic O is never replaced by an N2-only surrogate (nor N, O2 or scaled N2 data); a registry whose O-target processes point to non-O data is a MODEL_ERROR (FC-CHEM-05).
- UE-06: Stated source uncertainties enter the parent UQ (UQ-01..UQ-04) with their stated form; 'none stated' is recorded as NOT_STATED.

## 9. Completeness audit CA-ICP-v1 (preregistered)

- **Domain:** D-CHEM (T_e 2-30 eV; low-threshold window 0.2-30 eV; p_ICP <= 13.3322 Pa).
- **Metrics:**
  - `F_P`: k_omit dE_omit n_t,omit / sum_j k_j dE_j n_t,j: share of total electron inelastic power (frozen N2 definition, composition-weighted)
  - `F_P_coll`: share of total electron collisional power including elastic recoil 3 m_e / M_k (T_e - T_g) (added for the ICP because elastic recoil enters parent EQ-07 directly and light screened species exist; threshold copied from F_P)
  - `F_ion`: nu_ions,omit k_omit n_t,omit / sum_j nu_ions,j k_j n_t,j: share of total positive-ion production (frozen N2 definition)
  - `F_S_s`: share of the production or destruction of modeled species s due to the omitted channel (frozen N2 definition; extended to heavy-particle and surface channels)
  - `F_e_loss`: electron loss by the omitted channel (attachment, recombination) / electron production by ionization (added for the ICP; threshold copied from F_ion; generalizes the draft F_att)
  - `alpha_neg`: n_negative / n_positive (electronegativity share of the positive-ion charge; threshold copied from F_ion)
- **Thresholds:** F_P 0.01, F_P_coll 0.01, F_ion 0.01, F_S_s 0.05, F_e_loss 0.01, alpha_neg 0.01. Promote an omitted process if any metric exceeds its threshold anywhere in its domain over the evaluated compositions / states. F_P, F_ion, F_S_s copied from n2_completeness_audit_v1 so both reaction sets are judged by one standard; the three ICP additions copy the 1 % value; no ICP rate or number was consulted (none exists).
- **Ambiguity rule:** adopted verbatim from n2_completeness_audit_v1_addendum1_ambiguity: U < T -> EXCLUDE; L > T -> PROMOTE (nominal); L < T < U -> PROMOTE AS UNCERTAINTY VARIANT; bounds over all evaluated nuisance choices.
- **Cross-check rule:** adopted verbatim from n2_completeness_audit_v1_addendum2_crosscheck: newest full set authoritative, never averaged, discrepancies resolved before verdicts, verdicts applied literally.
- **Denominators:** Best available included set. Any verdict before every tier-1 process exists as a registered table is PROVISIONAL and is repeated once they exist.
- **State basis:**
  - stage_R: Rate-coefficient-only evaluation for F_P, F_P_coll, F_ion and neutral-target F_S on CG-AIR (and CG-N2, CG-XE).
  - CG-AIR: drafted: for each of the 196 design states, the free-stream O and N nuclei inventory (n_O + 2 n_O2; n_N + 2 n_N2) redistributed over f_O = n_O / (n_O + 2 n_O2) and f_N = n_N / (n_N + 2 n_N2), each in {0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1} (81 splits per state), plus the free-stream composition itself; He and Ar at their free-stream densities; NO, for SB-NO only, at its recorded grid-max share in every composition. A bounding grid, not a prediction: the delivered and Hall-processed compositions are unregistered and can lie anywhere on these axes (gas-path recombination towards f_O = 0, Hall / ICP dissociation towards 1).
  - CG-N2: drafted: pure N2 / N with f_N in the same 9-point set (EM-N2).
  - CG-XE: pure Xe.
  - stage_E: Blind state envelope for density-dependent and ion-target processes (DR, ion-molecule, O2+ / N2+ dissociative excitation, N+ -> N^2+-type ion channels, stepwise ionization, superelastic, NEG-CRIT, wall-dependent F_S) using the VERIFIED parent core (CFG-CAP-OFF, CM-ABS) over an input grid frozen in a dated addendum before any run (OQ-CHEM-04). No ICP measurement is used (none exists). Nuisance: chemistry variants, gamma / beta / disposition envelopes.
- **Tiers:**
  - 1 required as registered tables before any final verdict: AIR-ION-01..05; AIR-DIS-01, AIR-DIS-02 (envelope); AIR-EXC-01, -02, -04, -05, -09; AIR-EL-01..04; AIR-WALL-01..03 (structural / envelope); AIR-NL-01; XE: XE-ION-01, XE-EXC-01, XE-EL-01, XE-WALL-01, XE-NL-01
  - 2 assess before complete: AIR-ION-06; AIR-ION-15; AIR-DIS-03; AIR-EXC-06, -07, -11, -12; AIR-NEG-01..03 (NEG-CRIT); AIR-REC-01, -02; AIR-IM-01; AIR-WALL-04, -06; XE-ION-03; XE-EXC-02
  - 3 assessed not included unless bound exceeds: AIR-ION-07..14 (07..10 retained by default as sourced tables); AIR-DIS-04; AIR-EXC-03 (retained by default), -08, -10; AIR-SUP-01; AIR-NEG-04; AIR-REC-03; AIR-HN-01; AIR-WALL-05; XE-ION-02; XE-REC-01
- **Species bounds:**
  - SB-He (He): metrics species-summed F_ion, F_P, F_P_coll, F_S over every composition with x_He > 0.01; data needed: He ionization (candidate: NIST SRD 107, verify), He momentum transfer and excitation (source to be identified; LXCat excluded); until resolved: INCOMPLETE_EVIDENCE for the 14 ECSS_LT_LOW states (and any delivered composition with x_He > 0.01).
  - SB-Ar (Ar): metrics as SB-He over compositions with x_Ar > 0.01; data needed: Ar ionization (candidates parent VER-10: Rapp & Englander-Golden 1965 or Straub et al. 1995; NIST SRD 107, verify), Ar momentum transfer and excitation (to be identified; LXCat excluded); until resolved: INCOMPLETE_EVIDENCE for the 6 ECSS_ST_HIGH states.
  - SB-NO (NO): metrics F_ion upper bound with NO at its recorded grid-max share (plus the AIR-WALL-05 upper-bound NO source) over CG-AIR; data needed: NO ionization (candidates, verify: Itikawa, J. Phys. Chem. Ref. Data 45, 033106 (2016) electron-NO review; NIST SRD 107 NO entry), VER-CHEM-12; until resolved: INCOMPLETE_EVIDENCE for every AIR_PRIMARY composition (NO is not resolved per design state).
  - Rule: Exclude a species if every metric's upper bound <= threshold; add it (v2 of this contract) if a lower bound exceeds; between -> uncertainty-variant species (v2).
- **NEG-CRIT:** The electropositive treatment (no negative ions; parent EQ-03, DOM-12) is admissible for O2-bearing compositions only if the upper bounds of F_e_loss(attachment) and alpha_neg are both <= 0.01 over CG-AIR and the Stage-E envelope. alpha_neg needs a sourced lower bound on O- loss (AIR-NEG-02, -03); without it the criterion is not evaluable. On fail: O- is promoted: a v2 of this contract and of the parent (negative-ion balance, electronegative sheath), never a silent electropositive result. Today: NOT EVALUABLE (AIR-NEG-02 to acquire, AIR-NEG-03 no source) -> O2-bearing compositions INCOMPLETE_EVIDENCE, consistent with parent DOM-12 / CHG-03.
- **Snapshots:** The audit reads sha256-pinned snapshot registries (precedent hallthruster_bridge/audit/configs/MANIFEST.json); an omitted process is never evaluated against a mutable production registry that may already contain it.
- **Recording:** One row per process: criterion, lower / nominal / upper, worst case and where, nuisance sensitivity, verdict; literal application; recorded in an audit file under data/chemistry/icp/audit/ with the snapshot sha256.
- **Independence:** No fit quality, ICP bench result, Hall result or validation outcome is used to decide a verdict.
- **Reused sets:** Reused N2/N processes are retained as included by default (sourced, validity-verified); in the ICP domain they are excluded only by a bound; the Hall verdicts do not transfer.
- **Xe:** XE runs its own CA (same metrics, thresholds and rules) on CG-XE and its own Stage-E envelope; it never waits for AIR items.

## 10. Evidence each process needs before admission

| id | requirement |
|---|---|
| E1 | Source: full citation; document identity (DOI, URL, sha256 of the accessed document or data file); lawful, published access; not LXCat-distributed. |
| E2 | Extraction: method (transcribed / vector-extracted / digitized / analytic fit) and an independent check (second extraction or row-by-row); JPCRD-recommended values re-checked against the version of record. |
| E3 | Representation: source-representation file and .dat cross-check produced by a committed builder; sha256 pinned; .source file; PROVENANCE row; validity entry (IX-04) in the ICP registry. |
| E4 | Threshold / header from cited level or thermochemical data; inferred headers labelled. |
| E5 | Uncertainty as stated by the source, or NOT_STATED (then u_model_form stays NOT_EVALUATED; parent UQ-05); never assumed. |
| E6 | Applicability: Maxwellian EEDF, target state, source energy / temperature range inside or covering D-CHEM, else the limit is recorded. |
| E7 | Conservation stoichiometry and energy bookkeeping (CV-01..CV-04) recorded and load-checked. |
| E8 | Materiality: a CA verdict (included nominal / uncertainty variant / excluded by bound) or tier-1 inclusion. |
| E9 | Status: IN_REPO_VERIFIED for every tier-1 process, or an admissible envelope (UE-02) where the process allows one. |

## 11. Admission criteria

**Meaning.** The registered chemistry set of a mode satisfies its AD items over D-CHEM and its composition grid; outside D-CHEM -> OUT_OF_DOMAIN. Admission is software / evidence admission of the chemistry; it is not validation of the ICP model (parent VC-01..06).

**AIR_PRIMARY predictive admission requires** (A9.30 sec. 4):

| id | requirement |
|---|---|
| AD-AIR-01 | This preregistration and its lock committed (A9.30 sec. 4: 'until NP-ICP-CHEM-AIR is committed'). |
| AD-AIR-02 | Every retained species (O, O2, N2, N and the retained ions) has every process class addressed: modelled with a registered table / rate / structural rule, or excluded by a final CA verdict (parent process-class gate). |
| AD-AIR-03 | Every tier-1 process meets E1-E9: IN_REPO_VERIFIED in the ICP registry, or an admissible envelope (AIR-DIS-02, AIR-EXC-04 above 20 eV, AIR-WALL-01..03). |
| AD-AIR-04 | Final (non-provisional) CA verdicts for every tier-2 and tier-3 process on the complete tier-1 denominator over D-CHEM, CG-AIR and the Stage-E envelope; a tier-3 process with no evaluable bound is listed as an UNBOUNDED_OMISSION and blocks admission unless the owner disposes it explicitly (OQ-CHEM-15). |
| AD-AIR-05 | SB-He, SB-Ar and SB-NO resolved (excluded by bound, or the species added by a v2 of this contract). An unresolved SB-He / SB-Ar may be carried as state-resolved INCOMPLETE_EVIDENCE for its states only if the owner accepts that scope (OQ-CHEM-01); SB-NO blocks every AIR composition until resolved (OQ-CHEM-02). |
| AD-AIR-06 | NEG-CRIT evaluated and passed, or O- promoted through a v2. |
| AD-AIR-07 | Atomic O modelled with its own ionization (AIR-ION-01), momentum transfer (AIR-EL-04) and electronic excitation (AIR-EXC-09) tables; FC-CHEM-05 passes. |
| AD-AIR-08 | Wall and surface quantities either sourced for the registered vessel material or carried as the UE-02 envelopes (point values are then not claimed). |
| AD-AIR-09 | A reaction-set label registered in data/chemistry/icp/ICP_CHEM_PINNED.toml (drafted: abep-icp-air-0.x), separate from abep-n2n-* and the proposed Hall label abep-oo2-0.x; one label never names two chemistry definitions. |
| AD-AIR-10 | abep-icp passes the fail-closed chemistry tests FC-CHEM-01..10 under cargo test --workspace --locked. |
| AD-AIR-NOTE | Not required for chemistry admission: ICP hardware validation (parent sec. 16), the delivered composition (its absence makes flight point results NOT_EVALUATED, not the chemistry inadmissible), and He / Ar / NO data unless the bounds force them. |

**XE_CONTINGENCY requires, independently:**

| id | requirement |
|---|---|
| AD-XE-01 | This preregistration and its lock committed. |
| AD-XE-02 | XE tier-1 processes (XE-ION-01, XE-EXC-01, XE-EL-01, XE-WALL-01, XE-NL-01) meet E1-E9. |
| AD-XE-03 | Final CA-12 verdicts for XE-ION-02, XE-ION-03, XE-REC-01, XE-EXC-02. |
| AD-XE-04 | A separate label (drafted: abep-icp-xe-0.x). |
| AD-XE-05 | Independence: no AIR item (O/O2 data, NEG-CRIT, SB-*) is required; Xe admission proceeds wherever its own evidence is sufficient (A9.30 sec. 4). |
| AD-XE-06 | Mixed Xe / air compositions remain OUT_OF_DOMAIN (OQ-CHEM-10). |

**Today.** AIR_PRIMARY: NOT ADMITTED: tier-1 gaps (AIR-EL-04, AIR-EXC-04/05/09, AIR-DIS-02 envelope inputs, SONG2026 version-of-record checks), SB-NO, SB-He, SB-Ar, NEG-CRIT. XE_CONTINGENCY: NOT ADMITTED: no Xe table registered (XE-ION-01, XE-EXC-01, XE-EL-01 to acquire).

## 12. Build plan (after this preregistration)

**Location: `data/chemistry/icp/` (new; drafted, OQ-CHEM-05).**

- `ICP_CHEM_PINNED.toml`: reaction-set labels (abep-icp-air-0.x, abep-icp-xe-0.x), status, history; never abep-n2n-*
- `registry_air.toml / registry_xe.toml`: species and process registry (IF-CHEM-REG-v1)
- `rate_validity_icp.toml`: one validity entry per file used, including mirrored entries for reused Hall tables (each recording the Hall rate_validity.toml sha256 it mirrors)
- `reuse_pins.json`: path + sha256 of every referenced Hall or v0 file
- `PROVENANCE.md`: one row per table
- `xs/`: source representations (cross-section points or fit parameters) of new tables
- `tables/`: .dat cross-check tables of new tables
- `sources/`: committed source extracts where the licence allows (otherwise sha256 only)
- `audit/`: CA snapshots and verdicts

Why not `hallthruster_bridge/propellants/`: hallthruster_bridge/propellants/rate_validity.toml is pinned by config/model_set/physics_model_set_v1.json and by the parent prereg; the Hall driver refuses any rate file in use that lacks an entry in that pinned file; audit/configs/MANIFEST.json pins its rate files; abep-n2n-0.11 is frozen ('no further N2 chemistry changes'). Adding ICP files there would change pinned bytes and mix the Hall and ICP chemistry definitions.

Why not `docs/chemistry/o_o2/v0/`: v0 is an immutable DRAFT record for owner review; production registry data do not live under docs/.

Hall isolation: No file under hallthruster_bridge/ is created, edited or renamed by any ICP chemistry commit; PINNED.toml, rate_validity.toml, n2_n*.toml, audit/configs/MANIFEST.json and config/model_set/physics_model_set_v1.json keep their bytes. A CI check (FC-CHEM-10) asserts those sha256 and that every reuse pin still matches.

Per table: One table (one file) per commit, following CLAUDE.md item 2: builder (Rust in abep-chem, drafted; or the existing offline builder for a referenced v0 / Hall table), source-representation file, .dat cross-check, .source file, PROVENANCE.md row, rate_validity_icp.toml entry, registry entry, ICP_CHEM_PINNED.toml version bump with a history line, and a test pinning its sha256 and validity. A variant pair is two commits.

| step | content |
|---|---|
| BP-S1 | skeleton: registry schema, ICP_CHEM_PINNED.toml at abep-icp-air-0.0 / abep-icp-xe-0.0, reuse_pins.json and mirrored validity entries for the referenced N2/N tables (no new table) |
| BP-S2 | O ionization scenario pair by reference to v0 (2 commits) |
| BP-S3 | O momentum transfer after lawful acquisition (AIR-EL-04) |
| BP-S4 | after the SONG2026 version-of-record check: O2 ionization, O2 DI upper, O2 DI lower, O2 elastic, O2 attachment (assessment input) (one commit each) |
| BP-S5 | O electronic excitation per state (Laher & Gilmore 1990 open route; BSR-1116 when acquired); state list per OQ-CHEM-07 |
| BP-S6 | O2 a, b, Herzberg, Schumann-Runge after acquisition; then the AIR-DIS-02 envelope pair |
| BP-S7 | NEG-CRIT inputs (AIR-NEG-02, -03), DR (AIR-REC-01, -02), ion-molecule set (AIR-IM-01) |
| BP-S8 | species-bound data (SB-NO, SB-He, SB-Ar) and tier-2 / tier-3 bound tables |
| BP-S9 | CA stage R (snapshot), Stage-E grid addendum, CA stage E, verdicts, label to its first admitted version |
| BP-X1..X4 | Xe track, independent: Xe ionization, Xe excitation, Xe elastic, Xe CA |

v0 immutability: docs/chemistry/o_o2/v0/ is referenced by sha256 and never edited; a v0 table that needs a correction after the version-of-record check is rebuilt as a new ICP table with its own name, and the v0 file stays as history.

## 13. Interface to NP-ICP-NEUTRALIZER: `IF-CHEM-REG-v1`

- Provider `abep-chem (registry loader + validity table + integrator)`; consumer `abep-icp (NP-ICP-NEUTRALIZER)`.
- Modes: AIR_PRIMARY, XE_CONTINGENCY, EM-N2, EM-O2B, EM-XE.
- species: id, mass [amu], charge, role (feed / product / ion), retention rule id.
- processes: id, class, stoichiometry, header E_r [eV], representation file + sha256, validity limit [eV mean energy], status, variant / scenario group, tier, CA verdict id.
- envelopes: member list per envelope (UE-02).
- provenance: contract id, lock sha256, label, registry sha256.
- abep-icp loads the registry for the case mode; a lock or registry sha256 mismatch, a missing validity entry or an unregistered file sha256 -> MODEL_ERROR.
- rates come only from the abep-chem integrator (parent EQ-06); no rate is computed in abep-icp.
- the parent's per-reaction chemistry validity output (OUT-12) carries the registry process ids.

**Status propagation per mode:**

| id | rule |
|---|---|
| SP-01 | A required process INCOMPLETE_EVIDENCE without an admissible envelope -> every chemistry-dependent output of that mode (OUT-01, OUT-03..OUT-06, OUT-08..OUT-10) INCOMPLETE_EVIDENCE, naming the process. |
| SP-02 | Envelope-only processes -> outputs per member and as envelope, flag CHEMISTRY_ENVELOPE; status CONVERGED only if every member converges. |
| SP-03 | Activity beyond a validity limit, or a state outside D-CHEM -> OUT_OF_DOMAIN naming the reaction / check (parent DOM-01, DOM-02). |
| SP-04 | A composition with an unresolved MATERIALITY_BOUND_REQUIRED species above the screen (SB-He, SB-Ar) or any AIR composition while SB-NO is unresolved -> INCOMPLETE_EVIDENCE naming the species. |
| SP-05 | O2-bearing composition while NEG-CRIT is unevaluated or failed -> INCOMPLETE_EVIDENCE (parent DOM-12). |
| SP-06 | Delivered composition not registered -> NOT_EVALUATED for flight design-state points (parent IN-04 / IN-05); the CG-AIR audit results are not flight predictions. |
| SP-07 | Mode isolation: AIR statuses never change XE outputs and XE statuses never change AIR outputs; EM-O2B follows AIR. |
| SP-08 | No chemistry status is ever upgraded by assessment; raw output carries no threshold, PASS / FAIL or RFP label (parent EX-05). |

**Fail-closed tests** (Rust-era rule: asserted, never skipped):

| id | test |
|---|---|
| FC-CHEM-01 | registry with a file lacking a validity entry -> MODEL_ERROR |
| FC-CHEM-02 | reaction active beyond its validity limit -> OUT_OF_DOMAIN naming it (reaction-weighted share > 1e-12) |
| FC-CHEM-03 | stoichiometry violating charge / nuclei conservation or E_r below the formation-energy change -> MODEL_ERROR |
| FC-CHEM-04 | reuse pin mismatch (a changed Hall or v0 byte) -> MODEL_ERROR |
| FC-CHEM-05 | O-target process pointing to N2 / N / O2 data, or AIR_PRIMARY registry without AIR-ION-01, AIR-EL-04 and AIR-EXC-09 -> MODEL_ERROR |
| FC-CHEM-06 | AIR_PRIMARY case today -> INCOMPLETE_EVIDENCE naming the tier-1 gaps (asserted, never skipped) |
| FC-CHEM-07 | composition with x_He > 0.01 while SB-He is unresolved -> INCOMPLETE_EVIDENCE; same for Ar |
| FC-CHEM-08 | O2-bearing composition while NEG-CRIT is unevaluated -> INCOMPLETE_EVIDENCE |
| FC-CHEM-09 | mixed Xe / air composition -> OUT_OF_DOMAIN; XE case unaffected by AIR statuses |
| FC-CHEM-10 | Hall chemistry files (PINNED.toml, rate_validity.toml, n2_n*.toml, audit/configs/MANIFEST.json) and physics_model_set_v1.json unchanged by ICP chemistry commits |

## 14. Verify items

Recalled from memory or not readable from repository files. None enters a registry entry until a verification
addendum records the source read.

| id | item | used by |
|---|---|---|
| VER-CHEM-01 | O2+ (X) threshold 12.2 eV as read from the SONG2026 text layer (v0 header); NIST adiabatic IE of O2 recalled as 12.07 eV (memory) | AIR-ION-02, MR-5 |
| VER-CHEM-02 | O^2+ energy 48.77 eV above O ground (OCR text layer of II1990 Table 2.1) | AIR-ION-11 |
| VER-CHEM-03 | IE(O II) 35.12 eV (text layer of Bell 1983) | AIR-ION-12 |
| VER-CHEM-04 | O(1S) ~4.19 eV, O(3s 5S) ~9.15 eV, O(3s 3S) ~9.52 eV (memory); SONG2026 Fig. 25 caption 3s 3D vs plot label 3d 3D | AIR-EXC-09 |
| VER-CHEM-05 | whether Wang, Zatsarinny & Bartschat 2014 tabulate e-N excitation cross sections; N(2D), N(2P) energies | AIR-EXC-11 |
| VER-CHEM-06 | Peterson et al., J. Chem. Phys. 108, 1978 (1998) as an N2+ DR source; Florescu-Mitchell & Mitchell, Phys. Rep. 430, 277 (2006) | AIR-REC-01, -02 |
| VER-CHEM-07 | Anicich, JPL Publication 03-19 (2003); Kossyi et al., PSST 1, 207 (1992) | AIR-IM-01 |
| VER-CHEM-08 | Baulch et al., JPCRD 34, 757 (2005) scope for N / O neutral reactions | AIR-HN-01 |
| VER-CHEM-09 | Kim & Boudart, Langmuir 7, 2999 (1991) for O / N recombination on silica | AIR-WALL-02, -03 |
| VER-CHEM-10 | Maxwellian-tail form k ~ exp(-E_th / T_e) for E_th >> T_e (textbook, e.g. Lieberman & Lichtenberg 2005; parent VER-01 family) | MR-5 |
| VER-CHEM-11 | IE(H) 13.598 eV and IE(NO) 9.26 eV (memory) | species_set.application (H, NO) |
| VER-CHEM-12 | Itikawa, JPCRD 45, 033106 (2016) electron-NO review; NIST SRD 107 entries for NO, He, Ar, H, Xe | SB-NO, SB-He, SB-Ar, XE-ION-01 |
| VER-CHEM-13 | Rejoub, Lindsay & Stebbings 2002, Hayashi 1983 and GK2008 Appendix D/E content and primary sources (parent VER-10) | XE-ION-01, -02, XE-EXC-01, XE-EL-01 |
| VER-CHEM-14 | Itikawa, JPCRD 38, 1 (2009) O2 review (existence not verified in the repository) | AIR-ION-02 alternative |

## 15. Open items for the owner (not resolved here)

| id | question | blocks |
|---|---|---|
| OQ-CHEM-01 | He (> 1 % in 14 ECSS_LT_LOW states) and Ar (> 1 % in 6 ECSS_ST_HIGH states) pass the 1 % screen in free-stream composition, although A9.30 lists O, O2, N2, N. Accept MATERIALITY_BOUND_REQUIRED with state-resolved INCOMPLETE_EVIDENCE until bounded (drafted), or direct otherwise (e.g. wait for the delivered composition, MR-6)? | AD-AIR-05 for 20 of 196 states |
| OQ-CHEM-02 | NO (grid max 0.211 %) is screened out by mole fraction but has the lowest ionization energy (MR-5). Accept that AIR_PRIMARY admission needs an NO ionization bound (drafted), or rule otherwise? | AD-AIR-05 for every AIR composition |
| OQ-CHEM-03 | Keep the inherited T_e lower limit of 2 eV for the ICP, or extend it (needs low-energy completeness and Maxwellian applicability evidence)? | ICP states with T_e < 2 eV (OUT_OF_DOMAIN today) |
| OQ-CHEM-04 | Stage-E input grid (p_ICP, absorbed power, registered bench / analog geometry) to be frozen before any envelope run. | every density-dependent verdict |
| OQ-CHEM-05 | Location data/chemistry/icp/ and Rust builders in abep-chem (drafted), or another location / offline builders? | BP-S1 |
| OQ-CHEM-06 | Labels abep-icp-air-0.x / abep-icp-xe-0.x (drafted) and their relation to the proposed Hall label abep-oo2-0.x when the same O/O2 tables could later serve both. | AD-AIR-09, AD-XE-04 |
| OQ-CHEM-07 | The O/O2 draft owner decisions now needed for the ICP: OD-3 (O state list), OD-4 (O2 dissociation accounting; the envelope does not need it), OD-6 (O2 excitation above 20 eV), OD-7 (rotational convention); OD-1 / OD-2 / OD-5 / OD-8 are replaced here by D-CHEM, CG-AIR, NEG-CRIT and F_e_loss. Confirm. | AIR-EXC-04, -05, -08, -09 nominal choices |
| OQ-CHEM-08 | Lawful acquisition through fo_closed_access_acquisition: SONG2026 version of record and supplement, TZ2016 (BSR-1116) supplement, Huang 2022, Cosby 1993, Laporta 2013 supplement, Cherkani-Hassani 2006, Vejby-Christensen 1996, Peverall 2001, Rejoub 2002, Hayashi 1983. | tier-1 / tier-2 items marked SOURCE_IDENTIFIED_TO_ACQUIRE |
| OQ-CHEM-09 | Accept the molecular-ion wall-neutralization branching pair and the [0, 1] gamma / beta / quenching envelopes until the vessel material is selected and sourced. | point values of atom fractions and wall heat |
| OQ-CHEM-10 | Mixed Xe / air compositions (feed transitions) are OUT_OF_DOMAIN in v1. Accept, or require a mixed set (cross charge transfer, Penning) in a v2? | transition states |
| OQ-CHEM-11 | EM-O2B (NO_ATOMIC_O feed) still produces atomic O in the plasma; confirm it uses the full AIR set (drafted). | EM-O2B |
| OQ-CHEM-12 | Ion-molecule chemistry (NO+ formation, AIR-IM-01) judged by F_S on the Stage-E envelope; if promoted, NO+ / NO enter by a v2. Confirm. | AD-AIR-04 |
| OQ-CHEM-13 | XE_CONTINGENCY nominal set: GK2008 Appendix D/E (textbook compilation, evidence level 5) or the primary measurements (Rejoub 2002 and others)? | AD-XE-02 |
| OQ-CHEM-14 | Apply the species screen per composition / design state (drafted) or globally? | scope of SB-He / SB-Ar |
| OQ-CHEM-15 | Disposition of tier-3 processes with no evaluable bound (UNBOUNDED_OMISSION: AIR-ION-14, AIR-DIS-04, AIR-REC-03, AIR-HN-01, AIR-SUP-01, XE-REC-01 if no source is found): block admission (drafted) or accept as recorded omissions? | AD-AIR-04, AD-XE-03 |

## 16. Repository items that conflict with or constrain this contract

| id | where | against | handling |
|---|---|---|---|
| CONF-CHEM-01 | parent IN-16 producer 'hallthruster_bridge/propellants' | this contract's separate ICP registry with by-reference reuse | dated parent addendum re-points IN-16 to IF-CHEM-REG-v1 (no modelling change); until then both fail closed |
| CONF-CHEM-02 | parent sec. 8 gaps CHG-01..05, CHG-07..09 and NE-03 / NE-04 | this contract's per-process statuses | for the ICP, this contract's statuses supersede the gap rows through the parent addendum; consistent today (all fail closed) |
| CONF-CHEM-03 | parent DOM-02 states 2-30 eV for N2/N only | D-CHEM applies 2-30 eV to AIR and XE | parent addendum; the stricter text applies meanwhile |
| CONF-CHEM-04 | parent DOM-12 'no electronegative species -> INCOMPLETE_EVIDENCE' | NEG-CRIT can admit the electropositive treatment when its bounds pass | parent addendum to reference NEG-CRIT |
| CONF-CHEM-05 | docs/chemistry/o_o2/o_o2_completeness_prereg_DRAFT.json (DRAFT_PENDING_OWNER, Hall-oriented, 'freeze under hallthruster_bridge/prereg/') | this contract reuses its thresholds and tiers for the ICP | the draft is not frozen or changed; Hall O/O2 stays gated by CLAUDE.md item 4; this contract is the ICP rule |
| CONF-CHEM-06 | v0 README / channel_status_v0 ('unused by any campaign'; 'moving a table into hallthruster_bridge/propellants/ is a later model change'; 'CLAUDE.md item 4 unchanged') | ICP registry references v0 tables | v0 files referenced by sha256, not moved; A9.30 supersedes the item-4 sequencing for the active ICP only |
| CONF-CHEM-07 | hallthruster_bridge/propellants/PROVENANCE.md row excitation_N2_vib_*: 'validity 6.47 eV mean energy (see rate_validity.toml)' | rate_validity.toml: 45.0 eV for every excitation_N2_vib_* file | rate_validity.toml is authoritative; the ICP mirrors 45 eV and records the stale text (Hall file not edited) |
| CONF-CHEM-08 | abep_sim/aochem.py RECOMB_GAMMA, collision counts, 'homogeneous gas-phase chemistry is negligible' | rule 6 / A9.30 (no inherited unsourced values) | never used; AIR-WALL-02/03 envelopes; AIR-HN-01 bound |
| CONF-CHEM-09 | feed_state_closure_v2 valve-outlet x_O 0.211-0.659 (PROPOSED, model-derived) | a registered delivered composition | not consumed; MR-6 waits for an admitted upstream producer |
| CONF-CHEM-10 | A9.30 expected species O, O2, N2, N (+Xe) | computed free-stream He and Ar exceedances; NO low-IE exception | OQ-CHEM-01, OQ-CHEM-02; species not added |
| CONF-CHEM-11 | parent EX-12 (Hall-beam ions crossing the ICP not represented) vs G-REUSE (the ICP inlet is Hall-processed) | composition range at the ICP | CG-AIR spans full dissociation; beam-ion chemistry stays excluded in v1 |
| CONF-CHEM-12 | config/model_set/physics_model_set_v1.json pins hallthruster_bridge/propellants/rate_validity.toml | adding ICP entries to that file | constraint honoured by the separate registry (build_plan.location) |

## 17. Scope traceability (A9.30 secs. 3-4, verbatim lines → fields)

Lines are quoted from the A9.30 record with en dashes rendered as ASCII hyphens; bulleted lists are split into one
row per bullet.

**Sec. 3**

| line | fields |
|---|---|
| The old sequencing restriction that deferred O/O2 chemistry must NOT prevent completion of the selected hall_icp_neutralizer simulator. | id, implementation_gate, CONF-CHEM-05, CONF-CHEM-06 |
| AIR_PRIMARY at 180-230 km requires oxygen-capable RF/ICP physics. | species_set.application[O, O2], AIR-ION-01, -02, -05, AIR-EL-03, -04, AIR-EXC-04, -05, -09, AD-AIR-07 |
| O / O2 chemistry work is AUTHORIZED now for the ACTIVE selected RF/ICP neutralizer model. | id, parent_model.resolves_by_owner_ruling |
| This authorization is architecture-specific. | kind, parent_model, EXC-01, build_plan.location.hall_isolation |
| It does NOT reopen: the old P5 Hall-transport campaign; historical plasma_chem.py as an active module; old multi-family plasma models. | EXC-01, EXC-02, EXC-03 |
| Do NOT port plasma_chem.py wholesale. | EXC-02, RU-04 |
| Create a narrow preregistered chemistry contract for the selected RF/ICP model. Suggested identifier: NP-ICP-CHEM-AIR | id, kind, implementation_gate, change_rule |
| The minimum active species set should be justified from the registered 180-230 km atmosphere/design states and should include, where materially present/applicable: O O2 N2 N Xe for contingency operation | species_set.computation, species_set.materiality_rule, species_set.application, species_set.retained |
| Do not add species merely for completeness. | MR-1, MR-4, MR-5, species_set.application[He, Ar, H, NO], CA-07_species_bounds |
| For each retained process require: source/provenance; applicable electron-energy / Te domain; uncertainty/evidence class; reaction threshold; conservation; interpolation/extrapolation rule. | processes[*].source_provenance, processes[*].domain, processes[*].uncertainty, processes[*].evidence, processes[*].threshold, processes[*].conservation, processes[*].interpolation_extrapolation, common_rules |
| electron-impact ionization; | AIR-ION-01..15 |
| relevant dissociation; | AIR-DIS-01..04, AIR-ION-05, -06 (dissociative ionization) |
| dominant excitation / inelastic energy-loss channels; | AIR-EXC-01..12, AIR-SUP-01, AIR-EL-01..04 (elastic recoil), CA-02 F_P, F_P_coll |
| wall/recombination treatment; | AIR-WALL-01..06, AIR-REC-01..03, XE-WALL-01, XE-REC-01 |
| neutral loss / residence treatment; | AIR-NL-01, AIR-NL-02, XE-NL-01 |
| Xe ionization for contingency mode. | XE-ION-01..03, XE-EXC-01, -02, XE-EL-01, admission_criteria.XE_CONTINGENCY |
| Atomic oxygen is especially important for AIR_PRIMARY and must not be replaced by an N2-only surrogate. | EXC-05, UE-05, AD-AIR-07, FC-CHEM-05 |
| Existing repository rate data may be reused only where: provenance is valid; physical domain matches; the process remains applicable to the new RF/ICP model. | reuse_rule, processes[*].reuse_check_a9_30, reuse_pins |
| Do not inherit a rate merely because plasma_chem.py used it. | EXC-02, RU-04, CONF-CHEM-08 |
| If the available O/O2 evidence is insufficient, the model must expose: INCOMPLETE_EVIDENCE or an uncertainty envelope. | uncertainty_envelope_rule, interface_to_parent.status_propagation, common_rules.status_vocabulary |
| Do NOT fabricate missing coefficients. | UE-01, EXC-06, no_invented_numbers |

**Sec. 4**

| line | fields |
|---|---|
| The predictive RF/ICP model may be developed structurally in parallel | implementation_gate, interface_to_parent |
| AIR_PRIMARY predictive admission must not be claimed until NP-ICP-CHEM-AIR is committed and its required chemistry set is admitted for the model domain. | admission_criteria.AIR_PRIMARY, admission_criteria.meaning_of_admitted_for_the_model_domain, domain, FC-CHEM-06 |
| Xe-contingency portions may proceed independently where their evidence is sufficient. | admission_criteria.XE_CONTINGENCY, AD-XE-05, CA-12_xe, SP-07 |
| This chemistry gate must not block unrelated lanes: provenance/config; atmosphere; TPMC; intake; compressor; feed; Rust infrastructure. | non_blocking, MR-6 |

**A9.29 sec. 4 (related)**

| line | fields |
|---|---|
| atmospheric species relevant to the registered environment; | species_set |
| Xe contingency mode; | MR-7, XE-* |
| species-resolved ionization / dissociation quantities where included; | IF-CHEM-REG-v1.provides.processes |
| Do not invent coupling efficiency, impedance, extraction efficiency or stable operating regions merely to close the model. | EXC-06, UE-01 |

## 18. References

- M.-Y. Song, H. Cho, G. P. Karwasz, V. Kokoouline, J. Tennyson, K. Bartschat, 'Cross Sections for Electron Collisions with Molecular and Atomic Oxygen', J. Phys. Chem. Ref. Data 55, 013102 (2026), doi 10.1063/5.0287254; read from the accepted manuscript (UCL Discovery, sha256 32d163a3af584ce48b672a4dd49d3eafa182ae234161773b1e9fa44376d9f88b); version of record and supplement NOT accessed (verify: values re-checked against the version of record before registration)
- Song et al., J. Phys. Chem. Ref. Data 52, 023104 (2023) (registered, PROVENANCE.md)
- NIST SRD 107 electron-impact ionization cross sections (O, N registered; NO, He, Ar, H, Xe entries verify) (verify: partial)
- Itikawa & Ichimura, JPCRD 19, 637 (1990), doi 10.1063/1.555857 (open NIST reprint; source matrix)
- Laher & Gilmore, JPCRD 19, 277 (1990), doi 10.1063/1.555872 (open NIST reprint; source matrix)
- Bell et al., JPCRD 12, 891 (1983), doi 10.1063/1.555700 (open NIST reprint)
- Tayal & Zatsarinny, PRA 94, 042707 (2016) (BSR-1116; paywalled)
- Laporta, Celiberto & Tennyson, PSST 22, 025001 (2013)
- Huang, Zhang & Cheng, J. Phys. Chem. A 126, 2061 (2022) (paywalled)
- Tashiro, Morokuma & Tennyson, PRA 73, 052707 (2006)
- Rapp & Briglia, J. Chem. Phys. 43, 1480 (1965) (via SONG2026 Table VIII)
- Cherkani-Hassani et al., J. Phys. B 39, 5105 (2006) (paywalled)
- Vejby-Christensen et al., PRA 53, 2371 (1996) (paywalled)
- Goebel & Katz, Fundamentals of Electric Propulsion: Ion and Hall Thrusters, JPL (2008), registered document sha256 a373c8a26137b7c7cd989880c303c4f6c1f84f20a11a02770047f6ba4c249e4e (docs/architecture_comparison/scaling/scaling_similarity.json sources.GK2008; evidence level 5) (verify: Appendix D/E content and primary sources)
- abep-n2n-0.11 table sources (hallthruster_bridge/propellants/PROVENANCE.md)
- Itikawa 2009 (O2); Itikawa 2016 (NO); Rejoub 2002; Hayashi 1983; Peterson 1998; Florescu-Mitchell & Mitchell 2006; Anicich 2003; Kossyi 1992; Baulch 2005; Kim & Boudart 1991; Wang, Zatsarinny & Bartschat 2014 (excitation); Lieberman & Lichtenberg 2005 (verify)
