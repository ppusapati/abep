# P5-N₂ v1: E×B / species-acceleration physics forensics (non-gating)

**Role and limits.** This is a descriptive forensic of the **non-gating** O5 E×B diagnostic. It never eliminates, admits,
re-scores or re-labels anything. Official per-run statuses and the official `exb_diagnostic` block are read from the frozen
`hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores.json`. The v1 outcome is final and unchanged: all nine
ScaledGaussianBohm screening candidates are INCONCLUSIVE / NOT ELIGIBLE, the credible set is ∅, and gate 3 is FAIL. Nothing
here is tuned. No criterion, tolerance or rate-table validity limit is proposed or changed. The mechanisms in §5 are
**hypotheses**, and no parameter change is proposed for any of them.

**Reproducibility.** Every number from repository data comes from `scripts/forensics/p5_n2_v1_exb_physics.py`. It is
deterministic, reads frozen files only, runs no Julia, and takes under 1 s. It writes `exb_physics.json` (input sha256 values,
grouped summaries, and a per-run table for all 648 N1–N3 runs) and `exb_physics_tables.md` (all generated tables).
`--check` verifies that the committed outputs are current. Test: `python -m pytest -q tests/test_forensics_exb_physics.py`.

**Evidence classes used below.** *measured* (published instrument result), *digitized* (read from a published raster
figure), *model-derived* (computed from v1 model records), *inferred* (reasoning from code or algebra, not measured),
*assumed*, and *TBD — requires …*. Literature is also given its evidence level from docs/EVIDENCE.md.

---

## 1. Reproduction of the official O5 numbers

- Recomputed for all **648** N1–N3 runs: V_a,s = m_s u_s² / (2 Z_s e). The inputs are `outlet_ions` in the frozen raw
  records, with the scorer's constants and operation order. Result: max |recomputed − official| = **0 V** for N₂⁺ and N⁺. The
  keys are identical, and there are **0** ordering-flag mismatches.
- The ordering V_a(N⁺) > V_a(N₂⁺) holds in **0 of 648** runs, both recomputed and official. This confirms the figure given
  in the task.
- It holds in 0 of the 167 runs that are officially not OUT_OF_DOMAIN (32 + 55 + 80 at N1/N2/N3) and in 0 of the 481
  OUT_OF_DOMAIN runs. The OOD label does not change the E×B picture.
- The N⁺ residual (model − measured) spans **−172.0 to −84.9 V** (model-derived). The model is below the measurement in
  every run.

## 2. What is compared: observation geometry and reference potential

| item | model (v1 records) | measurement (Brabston et al., JPP 2025) |
|---|---|---|
| location | right domain edge z = 0.1 m from the anode: 68 mm (L32 registrations) or 62 mm (L38-hist) downstream of the exit plane (`cases/p5_n2.json`; value `ion.u[end]`, `campaign/p5_n2_campaign.jl:70-76`) | E×B probe **1 m** downstream of the exit plane, on centreline (paper Sec. III.C) |
| unmodelled path | — | 0.932 m (L32) / 0.938 m (L38) of facility plume at 1.14–1.47×10⁻⁵ Torr (Table 2) |
| quantity | m u²/(2Ze) using the **time-averaged** u (HallThruster.jl `time_average` averages n, nu and u separately, `postprocess.jl:77-79`) | most-probable velocity of a bi-Gaussian fit to a **time-integrated** Wien spectrum, converted with the assumed m/Z (Eq. 11) |
| potential reference | φ = cathode_coupling_voltage = **0 V** at the outlet (default `configuration.jl:213`, not set by `bridge_lib.jl:225-257`); anode side φ = V_d + anode sheath (`electron_update.jl:85-86`) | kinetic energy per charge in the probe minus the local plasma potential V_p at 1 m (Eq. 11). V_p is Langmuir-measured, not published numerically, max uncertainty 0.25 V (Table 5) |
| uncertainty | — | ±11.6 V per species (Table 5). The ±16.4 V on a difference assumes independent errors (**assumed**) |

**Common-mode invariance (inferred, algebraic).** Consider any species-independent potential offset per unit charge: the
cathode-to-ground voltage, the plume potential fall beyond 0.1 m, or the Eq. (11) V_p term. It shifts V_a(N⁺) and
V_a(N₂⁺) by the same amount. So it can move the absolute residuals, but it **cannot** change
D = V_a(N⁺) − V_a(N₂⁺) or the ordering in a collisionless electrostatic picture. The measured D is +44.0 / +55.4 / +65.1 V
(N1/N2/N3). The model D is **−72.3 V median, range −110.2 to −4.4 V** (model-derived). Only a **species-dependent** effect
can bridge that. Its size cannot be computed for the absolute values: it is TBD and requires the published cathode-to-ground
voltage and V_p at 1 m for N1–N3 (not in the paper as numbers). The NTRS draft recommended practice (Rovey et al., p. 23)
states that V_p at the probe is "generally … only a few volts above facility ground (e.g., 3-15 V)" (level 5; draft,
verify against the final version).

## 3. What the recorded v1 fields show (model-derived unless stated)

Full tables are in `exb_physics_tables.md`. Values are median [min, max] over 216 runs per point.

| point | V_a N₂⁺ | V_a N⁺ | N²⁺ energy per charge | D | R = V_a(N⁺)/V_a(N₂⁺) | u(N⁺)/u(N₂⁺) | flux frac N₂⁺ / N⁺ / N²⁺ |
|---|---|---|---|---|---|---|---|
| N1 model | 135.5 [108.8, 161.1] | 85.8 [69.1, 124.8] | 124.9 [97.4, 154.9] | −49.3 [−73.9, −4.4] | 0.62 [0.52, 0.96] | 1.11 [1.02, 1.39] | 0.520 / 0.469 / 0.011 |
| N1 measured (digitized) | 165.7 ± 11.6 | 209.7 ± 11.6 | not reported | +44.0 | 1.27 | 1.59 (if labels hold) | not published |
| N2 model | 157.4 [114.5, 194.0] | 87.4 [73.1, 125.0] | 122.5 [49.2, 152.6] | −72.3 [−92.6, −28.7] | 0.55 [0.47, 0.75] | 1.04 [0.97, 1.22] | 0.468 / 0.517 / 0.016 |
| N2 measured | 172.1 ± 11.6 | 227.6 ± 11.6 | not reported | +55.4 | 1.32 | 1.63 | not published |
| N3 model | 186.6 [144.0, 225.7] | 92.8 [71.7, 148.0] | 127.9 [39.1, 158.4] | −92.1 [−110.2, −61.9] | 0.51 [0.44, 0.66] | 1.01 [0.94, 1.15] | 0.437 / 0.543 / 0.020 |
| N3 measured | 178.6 ± 11.6 | 243.7 ± 11.6 | not reported | +65.1 | 1.36 | 1.65 | not published |

Reference: equal birth potential, collisionless and cold birth gives R = 1 and u(N⁺)/u(N₂⁺) = √2 = 1.414.

1. **The deficit is an N⁺ deficit.** Model V_a(N₂⁺) is near the measurement. Its median residual is −30.2 / −14.7 / +8.0 V
   at N1–N3 (range −57.7 to +47.1 V; `by_point.*.dVa_N2p` in the JSON). The N⁺ median residual is −123.9 / −140.2 /
   −150.9 V. Model V_a(N⁺)/V_d is 0.33–0.37 (medians), against a measured 0.87–0.90.
   Model N⁺ leaves the outlet at nearly the N₂⁺ **velocity** (ratio 1.01–1.11), so its energy per charge is roughly half
   that of N₂⁺.
2. **D < 0 in every run and in every grouping.** This holds for all 9 candidates × 3 points, all 3 registrations, all 4
   mandatory chemistries, both coil shapes, both domain classes and all Te_max bins. The largest model D per point is still
   48.4 / 84.1 / 127.0 V below the measured D. Across the four mandatory chemistry variants (DI upper/lower, OPM/Wang N
   elastic), the per-point medians of D spread by only 1.7 / 2.1 / 1.6 V.
3. **Discharge-voltage scaling is reversed.** Least-squares slopes over N1–N3 within each of the 216 fixed
   candidate/chemistry/registration/coil series:

   | slope | model median [min, max] | measured |
   |---|---|---|
   | dV_a/dV_d, N₂⁺ | 1.08 [0.20, 2.32] | 0.28 |
   | dV_a/dV_d, N⁺ | 0.26 [−0.95, 1.40] | 0.73 |
   | dD/dV_d | −0.88 [−1.52, −0.61] | +0.45 |

   In the model, added discharge voltage goes to N₂⁺. In the measurement it goes to N⁺.
4. **Associations** (Spearman across 648 runs; descriptive only):
   - D vs N²⁺ flux fraction −0.92, D vs N⁺ flux fraction −0.88, D vs Te_max_eV −0.81, D vs I_d RMS/mean −0.74.
   - V_a(N₂⁺) vs N⁺ flux fraction +0.87, but V_a(N⁺) vs N⁺ flux fraction only +0.26.
   - Transport parameters: D vs width_L +0.30. barrier_scale and center_L are near zero (|ρ| ≤ 0.08).
   - Reading: hotter runs make more atomic ions and more energetic N₂⁺, while N⁺ energy stays roughly flat. This is
     consistent, model-internally, with the extra N⁺ being produced at low potential.
   - Te_max_eV is the maximum of the **time-averaged** T_e profile (`bridge_lib.jl:312`; 12.7–25.2 eV in these runs).
     OUT_OF_DOMAIN is triggered by per-frame states above the table limits, so Te_max_eV does not measure the
     out-of-domain excursions.
5. **Time-average definition (sensitivity only; the official value stands).** The model discharges are strongly pulsed:
   I_d RMS/mean is 4.53 [0.13, 7.43].
   - With the density-weighted velocity ⟨nu⟩/⟨n⟩ in place of ⟨u⟩, V_a(N⁺) scales by 1.33 [0.83, 2.07] and V_a(N₂⁺) by
     0.80 [0.64, 1.20]. The ordering then appears in **106/648** runs, 105 of them in the RMS/mean ≥ 3 band and none in the
     7 runs below 1.
   - The N⁺ energy deficit survives either definition: −171.2 to −71.5 V under ⟨nu⟩/⟨n⟩.
   - So the **magnitude** of the N⁺ deficit is robust to the averaging definition, and the **sign of D** in pulsed runs is not.
   - Neither definition is the most-probable velocity of the time-integrated distribution that a Wien filter records. The
     frozen records do not contain per-frame outlet states, so that operator cannot be evaluated from v1.
6. **Multiply charged ions.** N₂²⁺ is absent from all 648 runs: `N2 max_charge = 1` in all four mandatory configs. N₂²⁺
   exists only in the non-mandatory `n2_n_n2dication.toml` variant, which was not run in v1.
   - N²⁺ is present in all runs, with a 0.4–5.1 % outlet flux fraction.
   - Its energy per charge lies between V_a(N⁺) and V_a(N₂⁺) in 522 runs, above both in 101 and below both in 25.
   - Under ⟨nu⟩/⟨n⟩ it lies above V_a(N₂⁺) in 640. Inferences about where the "hot zone" sits relative to the N₂⁺ birth
     region therefore depend on the averaging definition and are not drawn here.
7. **Velocity space under the m/Z = 14 label** (a Wien filter passes one velocity; descriptive only). A model species read
   under the "N⁺" label would be assigned E₁₄ = m_N u²/(2e). Medians at N1/N2/N3:

   | species | E₁₄ at N1 / N2 / N3 [V] |
   |---|---|
   | N₂⁺ | 68 / 79 / 93 |
   | N⁺ | 86 / 87 / 93 |
   | N²⁺ | 250 / 245 / 256 |
   | measured "N⁺" peak V_a | 209.7 / 227.6 / 243.7 |

   So in the model's velocity space, N₂⁺ and N⁺ nearly coincide, and the only model population near the measured "N⁺" peak
   velocity is N²⁺ at a 1–2 % flux fraction. This is reported as a velocity-space fact of the model outlet, not as a
   re-attribution of the published peaks. The published peak heights and species current fractions are not available
   numerically (audit: Ω_i,n not published). The different reference potentials (§2) also apply.

## 4. How ion species are created and accelerated in the pinned solver (code reading)

The source is read-only: HallThruster.jl v0.23.1, commit bfb3019 (Manifest `repo-rev`), at
`~/.julia/packages/HallThruster/zHCae/src/`, plus `hallthruster_bridge/bridge_lib.jl` and
`hallthruster_bridge/campaign/p5_n2_campaign.jl`. All statements are **inferred from code**. No Julia was run.

| question | answer | where |
|---|---|---|
| Where do ionization / DI source terms deposit ions? | In the same cell as the reacting neutral, cells 2..N−1, at rate k(ε)·n_e·ρ_reactant. The product mass source is `mass_ratio × density_loss` for each product. | `simulation/heavy_species_update.jl:645-723` (loop 657-697; products 699-721) |
| Initial ion velocity | Products get momentum `mass_source × reactant.vel_prim`, which is the reactant's local velocity. From a neutral reactant this is the fixed neutral velocity: N₂ 150 m/s (default), N 150·√(M_N₂/M_N) = 212 m/s. N⁺ → N²⁺ inherits the local N⁺ velocity. | `heavy_species_update.jl:669-675, 707-719`; defaults `physics/constants.jl:33-35`, `physics/gas.jl:408-415`; N velocity scaling `simulation/configuration.jl:331-343`; bridge passes `Propellant("N2", flow_rate_kg_s=…)` with no velocity or temperature (`bridge_lib.jl:255`) |
| Neutral dissociation products (N atoms) | N atoms enter the N continuity fluid. Continuity-only fluids integrate density only (their momentum source is discarded), with a **prescribed** velocity profile. N atoms therefore move at a fixed +212 m/s everywhere, with no upstream motion and no thermal or fragment spread. | `heavy_species_update.jl:83-93, 115-123`; `physics/fluid.jl:43-57, 115-123` |
| Fragment kinetic energy / Franck–Condon | **Not represented.** The electron energy loss per event is the rate-file header (threshold/appearance energy only, e.g. 24.284 eV for DI). Products are born with the reactant velocity. | `collisions/reactions.jl:56-65`; `heavy_species_update.jl:685-686` |
| Common potential? | Yes. One φ(z) comes from the electron Ohm's law and is integrated from the anode (V_d + sheath) to the outlet (V_cc = 0). Every ion fluid is accelerated by −(Z e/m)∇φ from the same cache. | `simulation/potential.jl:1-44`; `electron_update.jl:85-99`; `heavy_species_update.jl:850-863` |
| Ion thermal / pressure term | Isothermal Euler per species, p = ρRT_i, T_i = 1000 K default (≈ 0.086 eV). | `physics/fluid.jl:59-65, 125-130`; `heavy_species_fluxes.jl:130-151`; `configuration.jl:247` |
| Ion–neutral collisions (CEX, momentum transfer) for heavy species | **None found.** A grep of `src/` for charge exchange or ion–neutral terms finds none. Heavy-species sources are reactions, mutual neutralization, associative detachment, acceleration and optional wall loss. | `heavy_species_update.jl:143-158` |
| Ion wall losses | Off (`ion_wall_losses = false` default, not set by the bridge). | `configuration.jl:221`; `heavy_species_update.jl:156-158` |
| Plume | `solve_plume = false` (default). The 1-D domain ends at 0.1 m with a Neumann supersonic outflow. | `configuration.jl:225`; `heavy_species_update.jl:431-454` |
| Outlet value recorded | `ion.u[end]`, `ion.nu[end]` and `ion.n[end]` of the time-averaged frame. The `[end]` entry is the mean of the last interior and ghost cells, i.e. the right edge. | `campaign/p5_n2_campaign.jl:70-76`; `simulation/solution.jl:60-66, 116-126` |
| Time average | Arithmetic mean of each saved frame's n, nu and u from `average_start_s` = 1 ms to 2 ms (1000 saved frames over 2 ms by default). | `simulation/postprocess.jl:21-79`; `simulation/types.jl:63` |
| N⁺ channels in the four mandatory configs | N + e → N⁺ (Kim & Desclaux BEB) and N₂ + e → N⁺ + N (DI, upper or lower). There is no N₂⁺ → N⁺ channel. N²⁺ comes from N⁺ + e, N + e (HMS 2017) and N₂ + e → N²⁺ + N. | `propellants/n2_n*.toml` (read only) |

Consequence (inferred): in a steady, collisionless reading, V_a at the outlet equals the potential drop from an ion's
effective birth point to the outlet. On top of that come a negligible initial energy (0.0033 eV for either 150 m/s N₂ or
212 m/s N, computed in the JSON `neutral_birth_kinetic_energy_eV`) and the small T_i term. Momentum-conserving merging of ions born over a range of potentials makes the recorded value a momentum-weighted
average. The model therefore puts N⁺ births (N-atom ionization and DI) at a lower effective potential than N₂⁺ births in
every v1 run. The measurement implies the opposite, if its labels and the 1-m operator are taken at face value.

## 5. Candidate mechanisms for measured V_a(N⁺) > V_a(N₂⁺) and V_a(N⁺) ≫ model

All mechanisms are hypotheses. None is adopted, and none implies a parameter change.

| # | mechanism | open published evidence (class) | model feature it would require | can v1 records discriminate? | measurement that would discriminate |
|---|---|---|---|---|---|
| 1 | **Birth-location / birth-potential difference**: N⁺ born upstream (higher φ) of N₂⁺ | Brabston 2025 Sec. IV.C, p. 11: N⁺ and N₂⁺ "experience distinct ionization and acceleration regions, where the difference could occur either spatially or temporally" (level 3, interpretation). Gurciullo 2019 Sec. 4.2.1: lighter ions "created in a further upstream region" (hypothesis, Xe/N₂ mixture, Z-70) | Already expressible (species-resolved sources, one φ). v1 places N⁺ lower in all 648 runs | **Partly.** D < 0 everywhere, and D falls with N²⁺/N⁺ flux fraction and Te_max. No φ(z) or per-channel S(z) was recorded | Model side: time-resolved φ(z) and per-channel ion source S_s(z), not saved in v1. Experiment: near-field species-resolved LIF or E×B at several axial stations; OES/TALIF of N at the exit (the paper's own recommendation, Sec. V) |
| 2 | **Hot / diffusing N atoms**: dissociation fragments with eV energies, moving isotropically, some upstream into higher potential before ionizing | JPCRD 2023 Sec. 4.1: dissociative-recombination atoms have "few-eV kinetic energies" (level 5; DR of N₂⁺, not e-impact dissociation of N₂). Fragment energies for e + N₂ → 2N: TBD — requires an accessed source | A kinetic or diffusive neutral-N model. The solver's continuity-only N fluid has a fixed +212 m/s velocity (§4) and cannot move N upstream | **No** (neutral profiles not recorded in the campaign records) | TALIF/OES N-atom density profile in the channel (Brabston Sec. V); neutral-N velocity distribution |
| 3 | **Same m/Z of N₂²⁺ and N⁺** (both 14) | JPCRD 2023 Sec. 2.8 / Fig. 23: N⁺ and N₂²⁺ "indistinguishable in mass spectrometers" without ¹⁵N¹⁴N; N₂²⁺ ≈ 1 % of total ionization, metastable, no recommended values (level 4/5). Gurciullo 2019 Sec. 4.2: Wien filter "cannot distinguish" N₂²⁺ from N⁺; σ(N₂²⁺)/σ(N⁺) at 50 eV = 0.006/1.6 (×10⁻²¹ m², Halas & Adamczyk 1972 as quoted) | N₂ max_charge 2 (non-mandatory variant `n2_n_n2dication.toml`) | **No**: N₂²⁺ is absent in all v1 runs | **Inferred:** the V_a value under the N⁺ label equals the N₂²⁺ energy per charge, so misattribution changes the species reading, not the number. N₂²⁺ made from N₂ where N₂⁺ is made carries the same per-charge energy, and stepwise N₂⁺ → N₂²⁺ carries less. Exceeding V_a(N₂⁺) would need N₂²⁺ born at higher potential. Discriminator: isotopically mixed ¹⁴N¹⁵N (JPCRD). A combined ESA–Wien probe cannot separate equal m/Z at equal velocity (inferred) |
| 3b | **N²⁺ (m/Z 7) velocity** falling in the "N⁺" velocity window | none specific | present in v1 | **Descriptive only:** model N²⁺ E₁₄ medians are 245–256 V at 0.4–5.1 % flux, while model N⁺ and N₂⁺ sit at E₁₄ ≈ 68–93 V | Published raw spectra and peak heights (not available numerically). No re-attribution of the published peaks is proposed |
| 4 | **Fragment kinetic energy from dissociative ionization** | JPCRD 2023 Sec. 2.8 (p. 023104-17) summarising Crowe & McConkey 1973: fragment-ion KE peaks ≈ 2, 5 and 8 eV at 70, 90 and 300 eV impact energy (level 5; the ion label is ambiguous in the text extraction, verify) | Energy-dependent product velocity for DI channels (not in the solver, §4) | **No** (DI-born N⁺ is not separated). **Bound (computed):** the whole 8 eV peak equals 0.18 of the smallest measured D (44.0 V) and 0.094 of the smallest model N⁺ deficit (84.9 V). Isotropic emission lowers the axial share further. It **cannot** explain the magnitude alone | Not needed at this magnitude; per-channel N⁺ source + KE in a model would close it |
| 5 | **CEX / momentum exchange** between the 0.1 m outlet and 1 m | Rovey et al. NTRS draft RP: CEX ion population "around tens of eV" (p. 28), species-dependent CEX corrections (pp. 39–40), overlapping IVDFs as a dominant uncertainty (pp. 41–42) (level 5, draft). Gurciullo 2019 Sec. 4.2.2: "more extended low energy tail in the nitrogen peaks", broadening from distributed ionization and scattering. N₂⁺/N₂ and N⁺/N₂ cross sections: Phelps, JPCRD 20, 557 (1991), identified from its listing only (AIP and OSTI refused access): TBD | Plume transport with ion–neutral collisions (none in the solver, §4) | **No** (no plume beyond 0.1 m) | **Inferred:** first-order CEX removes fast ions and adds slow ones. It attenuates peaks but does not move the fast-peak velocity. A low-energy tail absorbed by a two-Gaussian fit could bias the lower (N₂⁺) peak centre down. Size TBD — requires the raw spectra and fit residuals, E×B at several distances or pressures, and accessed N₂ CEX cross sections |
| 6 | **Facility background and plume potential** | Brabston Table 2 pressures; Eq. (11) V_p term; V_p typically 3–15 V above ground (Rovey et al. draft, p. 23) | Facility-coupled far-field potential model | **No** | **Inferred (§2):** species-independent per charge, so D and the ordering are invariant. It affects absolute residuals only (TBD, requires published V_p and cathode-to-ground voltage). Facility-mode runs are part of the running follow-on campaign and were not read here |
| 7 | **Ion–ion two-stream effects** | Sewell, Kumar & Hara (OSTI 2479074, accepted manuscript) citing Hara & Tsikata, PRE 102, 023202 (2020) and Tsikata et al., PoP 21, 072116 (2014): Xe⁺/Xe²⁺ streams excite an axial wave with ion trapping (level 4, Xe only, PIC) | Kinetic ions, 2-D; outside a 1-D multi-fluid model | **No** | **Inferred:** relaxation of a relative drift tends to equalise species velocities, which pushes R toward ≈ 0.5, not toward R > 1. Not a natural source of the measured ordering. Discriminator: species-resolved IVDF widths (LIF) |
| 8 | **Anomalous-transport form** (where the potential falls relative to the ionization zones) | CLAUDE.md gate 3: P5 transport not identifiable; N₂ B(z), coil currents and near-field φ(z) unpublished (audit F6) | Different transport forms (outside the pre-registered screening set; none proposed) | **Within the 9 SGB sets only:** D < 0 in every set. D is nearly insensitive to barrier_scale and center_L and moderately rank-associated with width_L (+0.30) | Measured B(z) and coil currents for N₂; near-field φ(z) (e.g. emissive probe) |
| 9 | **Time dependence (breathing) plus the averaging operator** | Gurciullo 2019 Sec. 4.3.3: time-dependent ionization with a time-varying potential can give different average acceleration voltages per species (hypothesis). Brabston 2025 via audit finding F6: coils tuned at N3 to minimise I_d and its oscillation (amplitude not published) | Per-frame outlet flux and energy distribution folded into a Wien-spectrum operator | **Partly:** under ⟨nu⟩/⟨n⟩ the ordering appears in 106 runs (105 with RMS/mean ≥ 3), and the N⁺ deficit persists (§3.5) | Model: per-frame outlet records (not saved in v1). Experiment: I_d traces at N1–N3 (unpublished); time-resolved E×B or LIF |
| 10 | **Chemistry outside its validity domain** | Official OOD statuses (scores file) | — | **Yes, for this diagnostic:** D < 0 and the ordering count is 0/167 in the in-domain subset, the same picture as in OOD runs | — |

**Literature context (not P5).** Gurciullo 2019 (Z-70, Xe/air, Wien filter at 30 cm, Sec. 4.3.3) reports most-probable
velocities of 32 km/s (N₂⁺) and 47 km/s (N⁺). The velocity ratio is 1.47, and R = 1.08 computed from the rounded
velocities (level 3). That paper reports the molecular ions at acceleration voltages comparable to Xe⁺, and the atomic
ions N⁺ and O⁺ slightly higher (Sec. 4.3.3). Its conclusions (Sec. 5) call the lighter-ion finding "peculiar" and say it
"needs to be further examined". Brabston 2025 (Sec. IV.C) cites it as a smaller N⁺ > N₂⁺ difference. In P5 the
measured R is 1.27–1.36.

## 6. What this does not say

- It is not evidence for or against any screening candidate. The E×B diagnostic is non-gating (O5), and every candidate
  shows the same sign of D.
- It does not claim the measurement is wrong. The 1-m facility operator (CEX, V_p, peak fitting, time integration) is
  unmodelled, so the model–measurement residuals are not a validation measure.
- It proposes no retuning, no criteria or tolerance change, no rate-table limit extension and no chemistry change.

## 7. Sources accessed

| source | access | used for |
|---|---|---|
| Brabston, Marino, Lev & Walker, JPP 2025, doi:10.2514/1.B39623 | local copy, sha256 14db7e8c… (matches the frozen audit); not redistributed | Sec. III.C (E×B at 1 m, Eq. 11), Table 5, Sec. IV.C (p. 11), Sec. V; values via the frozen audit JSON |
| Gurciullo, Lucca Fabris & Cappelli, J. Phys. D 52, 464003 (2019), doi:10.1088/1361-6463/ab36c5 | author-hosted PDF https://sppl.stanford.edu/wp-content/uploads/2020/09/AntonioHallThruster.pdf (sha256 4ea1ff43…) | Secs. 2.4, 4.2, 4.2.1–4.2.2, 4.3.3; m/Z ambiguity; velocities |
| Song, Cho, Karwasz, Kokoouline & Tennyson, JPCRD 52, 023104 (2023), doi:10.1063/5.0150618 | local copy used by earlier repository audits; not redistributed | Sec. 2.8 (N⁺/N₂²⁺, KE peaks), Sec. 4.1 |
| Rovey, Yamauchi, Huang, Thomas, Hurley, Farnell ×3, Brabston & Young, "Recommended Practice for Use of ExB Probes in Electric Propulsion Testing" (internal-review draft) | NTRS https://ntrs.nasa.gov/api/citations/20260002294/downloads/JEP-ExBPracticePaper-InternalReview_Huang.pdf (sha256 854d6262…) | V_p magnitude, CEX populations and corrections, IVDF overlap; draft, verify against the final version |
| Sewell, Kumar & Hara, "Effects of the wavelength of the plasma waves on cross-field electron transport in partially magnetized plasmas" (accepted manuscript) | OSTI https://www.osti.gov/pages/servlets/purl/2479074 (sha256 a82da0e9…) | IITSI context and references (journal venue: verify) |
| Phelps, JPCRD 20, 557 (1991) | **not accessed** (AIP 403, OSTI 503); search listing only | identified as the N₂⁺/N⁺–N₂ cross-section source; values TBD |
| HallThruster.jl v0.23.1 source (MIT) | local package `zHCae` (Manifest rev bfb3019) | §4 |

No author or lab was contacted, LXCat was not used, and no paywall was bypassed. Earlier unreviewed scratch forensic notes
were used only as a cross-check. Every number above was recomputed by the committed script.
