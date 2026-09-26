# Wall erosion and life evidence, v1 (2026-09-26)

Machine-readable database: [`sputter_yield_db_v1.json`](sputter_yield_db_v1.json). Structural checks:
`python -m pytest -q tests/test_wall_life_db.py`.

**Status: evidence only.** Nothing in `abep_sim/` or `hallthruster_bridge/` reads this database. No model, threshold,
chemistry, frozen dataset or campaign was changed. It records what the open literature does and does not establish about
sputter and erosion yields of Hall-channel wall ceramics, so that later N/O Hall-channel life work starts from cited
evidence and not from priors. Evidence levels (1-7) and evidence classes (measured / digitized / inferred / reconstructed /
model-derived / assumed) follow [`docs/EVIDENCE.md`](../../EVIDENCE.md).

## 0. Milestone relevance and operating-model question

This lane is `lane_32_wall_life` (`docs/orchestration/lane_registry_v1.json`: answers **(iii)**, verification protocol
`single-lens-v1`). The JSON carries the same statement under `milestone_relevance`.

- **Question answered: (iii), an engineering issue that could later overturn the choice.** Hall-channel wall erosion by
  N⁺, N₂⁺, O⁺ and O₂⁺ is unquantified for every candidate wall ceramic, through physical sputtering and O/N surface
  chemistry. Until hardware tests H1-H9 close gaps G1-G10, no architecture can show that it meets the > 15,000 h RFP
  firing requirement. At minimum that needs H1, H3, H4, H6 and H7.
- **Architectures.** The issue is common to `hall_only`, `rf_hall` and `ecr_hall`, because the downstream Hall
  accelerator and its wall are common. It doesn't discriminate between them and supports no elimination.
- **Milestone A: non-decisive.** The database gives no selection input. A conditional baseline may cite it only as a
  condition to be demonstrated: the chosen wall grade must reach N/O wall-erosion life ≥ the required firing hours,
  shown by H1, H4 and H6.
- **Milestone B: evidence only.** It can't give a credible wall-life envelope. No measured N/O yield exists on BN, BN-SiO₂
  or SiC, and there is no admitted Hall closure (the credible set is empty) to supply the wall flux. Reaching B needs
  three things: second-lens verification of this lane, N/O coupon yields (H1-H3), and an admitted closure whose wall
  fields are `wall_life_trustworthy` and validated against near-wall data (H7).
- **Milestone C: evidence only; it cannot support a life number.** Reaching C needs thruster wear-test erosion profiles on
  N₂/O₂ with the Vyovrinda channel (H6), plus H1-H5 and H7-H9. These must be integrated through a consumer that meets
  section 6a.
- **Verification.** This lane was single-lens-v1 at merge `6bbfeb2`, and this revision is the second-lens repair on top of
  `e15f66f`. The lane is not decisive for Milestone B or C until that verification is recorded as passed.

## 1. Use restrictions

These statements gate every use of the database. The JSON carries the same wording under `hard_statements`.

1. **The solver's wall ion flux is not a validated erosion prediction.** `wall_ion_flux_m2s` and `wall_ion_energy_eV`
   (schema `hall_map_schema_v1`, evaluated in `bridge_lib.jl` `wall_ion_metrics`) come from HallThruster.jl's WallSheath
   Bohm-flux closure: Γ_i = loss_scale · h · Σ_s n_s √(Z_s e T_e / m_s), with impact energy Z φ_s + T_e/2. That impact
   energy leaves out the axial ion kinetic energy and the incidence angle. The flux has not been compared with any
   measured wall-erosion profile in this project. With `ion_wall_losses=false` it isn't even removed from the ion fluid.
   `wall_life_trustworthy` certifies only that the flux is self-consistent inside the solve, not that it agrees with
   erosion data. The 1-D solver has no radial resolution and no wall ion energy or angle distribution. The transport
   closure that sets the plasma state is not identified (gate 3). Multiplying this flux by any yield below gives a
   sensitivity number, never a life prediction.
2. **Screening transport candidates must not be used for design life.** The nine ScaledGaussianBohm screening
   candidates (`sgb-screen-01..09`) are not admitted ensemble members; the credible set is empty (CLAUDE.md item 1). They
   never produce design Hall maps. Their wall fields must not feed life estimates, erosion budgets or wall-thickness sizing.
3. **No design-life number can be derived from this version.** I found no measured N⁺, N₂⁺, O⁺ or O₂⁺ yield on BN,
   BN-SiO₂ or SiC in open sources. The only measurement I found of these ions on a candidate ceramic is Espy et al.
   1993, on Al₂O₃ thin films. It is closed access, so its values are TBD.
4. **In-repo priors are not endorsed.** The `abep_sim/materials.py` values `sputter_Eth_eV` and `sputter_Y300` are
   tagged "literature-class prior" and have no citation. This database doesn't support them, and neither does any
   erosion path that uses them (section 7).

## 2. Coverage at a glance

| projectile | BN | BN-SiO₂ | SiC | Al₂O₃ | other |
|---|---|---|---|---|---|
| Xe⁺ (reference) | measured, transcribed | measured, values TBD (SiO₂ constituent only transcribed) | none located | measured, transcribed | BN-AlN, MgO, BN-05, Si₃N₄+BN: values TBD |
| N⁺ | none located | none located | none located | measured, values TBD (Espy 1993) | none located |
| N₂⁺ | none located | none located | none located | measured, values TBD (Espy 1993) | none located |
| O⁺ | model proxy only (TRIM.SP on elemental B and on B₂O₃) | none located | none located | measured, values TBD (Espy 1993) | model only: C (graphite), physical sputtering only |
| O₂⁺ | none located | none located | none located | measured, values TBD (Espy 1993) | none located |

"None located" means none located in the searches recorded in the JSON `search_log`, not that no data exist anywhere.
Closed or bot-challenged sources were not bypassed (`access_log`).

## 3. What the evidence says

- **N/O yields on the primary wall materials are missing.** O-projectile evidence is model-derived only (Eckstein,
  IPP 9/132, TRIM.SP) and uses proxy targets. At 150 eV, O on elemental B gives 0.0375 atoms/ion and O on B₂O₃ gives
  0.752 atoms/ion in total. That is a ~20× spread between two stand-ins for the same wall, driven mainly by the assumed
  surface binding energy. IPP 9/132 has N projectiles only on Be, C (15-30 keV only) and W. None of these is a wall
  material or a sensible proxy for one.
- **The reference pair (Xe⁺ on BN) is itself uncertain by up to an order of magnitude between laboratories.** Rubin et
  al. 2009 (HBC, QCM) and Tartz et al. 2009 (calcium-borate-bound BN, weight loss) differ by 11.8× at 100 eV and 4.6×
  at 500 eV at normal incidence. These ratios are my arithmetic on the transcribed values. Grade/binder and
  neutralization state are the leading suspects. Topper 2011 found about 2× from neutralization alone.
- **The threshold is not identified, even for xenon.** Xe on BN gives 18.3 ± 1.1 eV from a molecular-dynamics fit at
  45°, 24 ± 6 eV from a Bohdansky fit (HBC) and 57 eV from a Zhang fit. Borosil erosion models assumed 30-70 eV. An
  Al₂O₃ yield fit returns 5 eV, which the data don't constrain. The ions that matter most for Hall-wall erosion sit in
  this unconstrained low-energy region: Rubin 2009 (Sec. I) says ≤ 100 eV, and Cheng & Martinez-Sanchez 2007 (Sec. IV.A)
  say the measured data don't reach it. Passet et al. 2024 call for new data at 10-250 eV, 0-85°, 30-600 °C.
- **Temperature matters.** The MD model gives ~2× from 423 K to 850 K (Yim 2008). Rubin 2009 measured a rise from
  ~520 °C (preliminary). Passet 2024 attribute a 50-60 % under-prediction of SPT-100 exit erosion to temperature.
- **Coupon results didn't carry over to thruster life in the one comparison found.** In Abashkin 2007, BN-05 had a
  1.5-18× lower plume yield than BGP (BN-SiO₂), yet both gave ~3000 h predicted life after 500 h tests.
- **Reactive chemistry is outside every yield entry.** O oxidizes B (a B₂O₃ surface forms), Si and C, and N is a
  constituent of BN. Physical-sputtering yields cannot bound N/O erosion from either side without tests.

## 4. Xenon reference data (transcribed)

Normal incidence, full-material volumetric yield, mm³/C. A blank cell means not measured. Britton values are at 15°
from normal, not at normal incidence.

| E (eV) | BN HBC (Rubin 2009) | BN HBR (Rubin 2009) | BN HP (Rubin 2009) | BN Ca-borate (Tartz 2009) | Al₂O₃ (Tartz 2009) | quartz (Tartz 2009) | BN, β = 15° (Britton 2002) |
|---|---|---|---|---|---|---|---|
| 60 | 0.0145 | 0.015 | 0.010 | | | | |
| 100 | 0.0312 | 0.036 | 0.034 | 0.00265 | 0.00189 | 0.0132 | |
| 150 | 0.0390 | | | | | | |
| 200 | 0.0614 | 0.058 | 0.080 | | | | |
| 250 | 0.0669 | 0.079 | 0.122 | 0.01 | 0.0076 | 0.0395 | |
| 300 | 0.0842 | | | | | | 0.0350 |
| 350 | 0.0726 | 0.0838 | | 0.0133 | 0.013 | 0.0577 | |
| 500 | 0.0973 | 0.089 | | 0.021 | 0.0213 | 0.076 | |
| 600 | | | | | | | 0.0576 |
| 800 | | | | 0.034 | 0.0326 | 0.118 | |
| 1000 | | | | | | | 0.0879 |

Notes on the table:
- Rubin 2009 values are the source's own conversion of QCM condensable yields to full BN, Y_BN = Y_QCM (M_B + M_N)/M_B.
  Their uncertainty is about 30 %.
- Britton values are converted from Å/(s · mA/cm²) by the exact factor 10⁻² mm³/C, and the angle by β = 90° − θ.
- Angular data (0-45° for Rubin; 15/40/60° for Britton), fits and raw 40-80 eV runs are in the JSON.
- Rubin 2009 prints two values for k in its HBC Bohdansky fit (0.053 mm³/C in the text, 0.037 in Table 4). Both are
  kept.
- Its printed angular exponent (cos β)^f is inconsistent with the source's own peaked fit; the standard Yamamura form is
  (cos β)^−f. Verify before any use.

Model and compilation fits in the JSON:
- Yim 2008 MD: Bohdansky α = 0.062 ± 0.004 mm³/C, E_th = 18.3 ± 1.1 eV (Xe on h-BN, 45°, 423 K).
- Yim 2017 Eckstein fits (Xe on Al₂O₃ and on SiO₂) and Wei angular fits.
- Cheng & Martinez-Sanchez 2007: Xe on BN fits for imposed thresholds of 0-50 eV. These thresholds were tuned to
  thruster erosion data, so they are calibration parameters, not material properties.

Values TBD, because the text was closed or bot-challenged or the data are figure-only: Garnier 1999 (BN, MgO, BN-AlN,
BN-SiO₂), Crofton & Young 2021 (alumina, HP BN; CC BY), Ranjan et al. 2016 (BN, BN-SiO₂), Tondu 2011 (BN, SiO₂, Al₂O₃;
figures), Abashkin 2007 (BGP, BN-05; figures), Kim et al. 2001 (Xe and Kr on BN ceramics), Duan et al. 2014 (textured
h-BN composites).

## 5. Nitrogen and oxygen evidence

| entry | projectile to target | class (level) | energies | status |
|---|---|---|---|---|
| Espy et al. 1993, SPIE 1761, 130-140 | O⁺, O₂⁺, N⁺, N₂⁺ on Al and Al₂O₃ thin films | measured (3) | 50-200 eV | values TBD (closed); the first thing to obtain |
| Eckstein IPP 9/132 p. 40 | O on elemental B (proxy for the B sublattice) | model-derived (4) | 150-6000 eV, normal | 0.0375 / 0.114 / 0.277 / 0.387 / 0.416 atoms/ion at 150 / 300 / 1000 / 3000 / 6000 eV |
| Eckstein IPP 9/132 p. 278 | O on B₂O₃ (proxy for an oxidized BN surface) | model-derived (4) | 150-3000 eV, normal | total 0.752 / 1.07 / 1.53 / 1.55 atoms/ion; average surface binding energy only 1.28 eV |
| Eckstein IPP 9/132 p. 65 | O on C (physical sputtering only) | model-derived (4) | 38-6000 eV, normal | 4.6e-6 at 38 eV to 0.340 at 6000 eV; chemical erosion (CO/CO₂) not included |

The IPP values were checked against the rendered page images of the scanned report. All three tables are "only low
fluence" and assume flat surfaces.

**Molecular ions.** Treating N₂⁺ or O₂⁺ as two atoms at half the energy each is an assumption (level 7, verify). I
recall it as common practice but did not check a source. The Espy 1993 abstract lists O⁺, O₂⁺, N⁺ and N₂⁺ beams at
50-200 eV on Al and Al₂O₃. Whether the paper compares molecular and atomic ions at matched energy per atom is *inferred
from the abstract only* (verify). Hardware test H3 would settle the question for the Vyovrinda wall.

## 6. Extrapolation policy

A yield may be used without a flag only when all of these match the entry: projectile, material class and grade family,
energy range, measured angles and surface temperature. Every other use carries flags, and any flagged result is
**OUT_OF_DOMAIN**. It can appear in sensitivity or bracketing tables only. It is never a design-life, erosion-budget or
wall-thickness number, and never feeds a trade, UQ envelope or life margin as a prediction.

| flag | meaning |
|---|---|
| `E_BELOW_MEASURED` / `E_ABOVE_MEASURED` | outside the entry's energy range. Below it, bracket with several thresholds. Above ~500 eV a yield jump is reported for BN and BN-SiO₂ (Ranjan 2016 abstract) |
| `ANGLE_OUTSIDE_MEASURED` | ceramic angular dependence is controlled by roughness; smooth-surface fits don't transfer to an eroded wall |
| `PROJECTILE_PROXY` | e.g. xenon data applied to N/O. **Forbidden for design life.** Includes the energy-transfer-factor scaling in `archengine.py` |
| `TARGET_PROXY` | elemental B, B₂O₃, C, the SiO₂ constituent, or another BN grade or binder. Grades differ by up to ~1.8× within one lab; grade and laboratory together differ by up to ~12× |
| `TEMPERATURE_OUTSIDE_MEASURED` | yields rise with temperature (~2× at 850 K vs 423 K in MD) |
| `MOLECULAR_ION_ASSUMPTION` | N₂⁺/O₂⁺ treated as two atoms at half energy (assumed) |
| `SURFACE_STATE` | not modelled: fluence, implantation, oxidation, roughening, grain detachment, moisture uptake |
| `NEUTRALIZATION_STATE` | about 2× systematic for insulators |
| `VALUES_TBD` | numbers not accessed; the entry can motivate a test, never a calculation |

**No silent fallback.** A lookup for a pair with no entry must raise. It must not substitute xenon data, a proxy target
or the `materials.py` priors. Today every N/O lookup on BN, BN-SiO₂ or SiC is OUT_OF_DOMAIN.

### 6a. Consumer requirements

These requirements are binding on any code that takes a yield from this database. The JSON has them under
`consumer_requirements`.

- **Consumer today.** `abep_sim/thermal_life.py` was merged after this lane. Its `_check_hall_discharge` has a
  `wall_erosion_life` margin check with life = d_allow / (Γ_i · peak/avg · Y_v), where the caller supplies Y_v as
  `volumetric_sputter_yield_m3_per_ion`. It gates on an admitted ensemble member and on `wall_life_trustworthy`. It does
  not carry this database's entry id, its extrapolation flags or the OUT_OF_DOMAIN rule, so it can return PASS or FAIL.
  That code is outside this lane's allowed paths and is logged as gap G11 for the thermal/life lane.
- **Unit crosswalk.** Y[m³/ion] = Y[mm³/C] · 10⁻⁹ · e, with e = 1.602176634 × 10⁻¹⁹ C (the exact SI value). It holds for
  singly charged incident ions only. Atomic yields (atoms/ion) need a grade density and a sputtered composition, and no
  crosswalk is given for them here.
- **Carry the flags.** A consumer must pass the entry id and its full flag set into its result.
- **Map flagged results to NOT_DEMONSTRATED.** Any flagged yield makes the erosion-life check OUT_OF_DOMAIN, reported as
  **NOT_DEMONSTRATED**, never PASS or FAIL.
- **N/O today.** With this version, N⁺, N₂⁺, O⁺ or O₂⁺ on BN, BN-SiO₂ or SiC must return NOT_DEMONSTRATED.
- **Missing pairs.** A missing pair raises. Nothing may be substituted for it.
- **Wall flux source.** Wall flux comes only from an admitted member with `wall_life_trustworthy = true`, never from a
  screening candidate.

## 7. In-repo audit (read-only)

| where | what | assessment |
|---|---|---|
| `abep_sim/materials.py` | `sputter_Eth_eV` / `sputter_Y300` (atoms/ion at 300 eV, "Xe-referenced"): BN 45 / 0.25, BN_SiO2 45 / 0.20, SiC 50 / 0.30, Al2O3_anodised 60 / 0.35, Quartz 40 / 0.30, Graphite 35 / 0.2, with Y(E) ∝ ((E/E_th − 1)/(300/E_th − 1))^1.5 | level 7 / assumed. No citation. The 45 eV BN threshold matches none of the fitted Xe values (18.3, 24 ± 6, 57 eV). Units differ from the mm³/C sources. No dependence on ion species |
| `abep_sim/plasma_devices.py` HallChannel | Y(5 T_e + 20 V), wall flux 0.2 n_e u_B × shielding | superseded 0-D closure (CLAUDE.md: absolute Hall results withdrawn) |
| `abep_sim/archengine.py` | Hall life = 6 mm / erosion rate; SiC/Mo cathode-antenna yield at 3 T_e + 10; Mo grid yields scaled by the energy-transfer factor vs Xe | inherits the priors; the scaling is a `PROJECTILE_PROXY` assumption |
| `abep_sim/life.py` | `LifeInputs.hall_sputter_um_per_kh` default 300 (line 22); `hall_channel_life` life = t₀ / rate | assumed |
| `abep_sim/mission5.py:83` | `base.get("pl_wall_erosion_um_per_kh", 150.0)` fallback | assumed |
| `abep_sim/system.py:169`, `:292` | line 169 forwards `wall_erosion_um_per_kh` as `pl_wall_erosion_um_per_kh`; line 292 repeats the 150.0 fallback | assumed |
| `abep_sim/thermal_life.py` (merged after this lane; audited at `e15f66f`) | `wall_erosion_life` check takes a caller-supplied `volumetric_sputter_yield_m3_per_ion`; gated on admitted member + `wall_life_trustworthy` | future consumer; must carry the extrapolation flags and return NOT_DEMONSTRATED for N/O (section 6a, gap G11) |

## 8. Gaps and required hardware tests

Literature cannot close the N/O gap. The hardware tests below are the only route to IN_DOMAIN yields and a validated
erosion model. Details are in the JSON (`gaps` G1-G10 (hardware/literature) and G11 (consumer code), `hardware_tests_required` H1-H9).

| id | test | closes |
|---|---|---|
| H1 | Ion-beam coupons of the Vyovrinda wall grade(s): N⁺, N₂⁺, O⁺, O₂⁺ at 20-300 eV, 0-85°; weight loss **and** QCM with species accounting; beam energy distribution, doubly charged and neutral fractions measured | N/O yields, thresholds |
| H2 | Neutralization / surface-potential sweep on the insulating coupons | the ~2× systematic |
| H3 | Molecular vs atomic ions at matched energy per atom | removes `MOLECULAR_ION_ASSUMPTION` |
| H4 | Combined ion + atomic-O + N₂ exposure at 30-600 °C with XPS/SEM (B₂O₃ formation, SiC oxidation, implantation) | chemical erosion |
| H5 | Long-fluence coupons: yield vs fluence, roughness, grain detachment | surface state |
| H6 | Thruster wear segment on N₂, an N₂/O₂ mixture and Xe with the Vyovrinda channel and B(z): erosion profiles, wall temperature map | end-to-end erosion model validation |
| H7 | Near-wall diagnostics in the same thruster: wall ion flux, ion energy and angle distribution (flush probes, RPA), T_e, sheath potential | validates or rejects the WallSheath flux closure |
| H8 | Xe⁺ yields of the same coupons in the same facility | ties the Vyovrinda grade to the literature and measures the lab-to-lab offset |
| H9 | SEE yield of the walls before and after N/O exposure | sheath potential, and hence impact energy |

Literature tasks for the owner (not done here because of access limits):
- Obtain the full text of Espy 1993 (highest priority), Garnier 1999, Crofton & Young 2021 (CC BY), Ranjan 2016,
  the 2022 Borosil elevated-temperature study (S23) and Tejeda & Knoll 2023 (O₂-fuelled HET with different ceramic walls).
- Digitize Tondu 2011 Figs. 4-8 and Abashkin 2007 Figs. 4-5, recording axis residuals.

## 9. Sources

Full citations, access status, retrieval date and the sha256 of every file actually downloaded are in the JSON
(`sources` S01-S23). The downloaded PDFs stay in the session scratchpad and are not committed.

| id | source | access | level |
|---|---|---|---|
| S01 | Rubin, Topper, Yalin, IEPC-2009-042 | open | 3 |
| S02 | Topper, MSc thesis, Colorado State University 2011 | open | 3 |
| S03 | Britton et al., NASA/TM-2002-211837 | open (NTRS) | 3 |
| S04 | Tartz et al., IEPC-2009-240 | open | 3 |
| S05 | Tondu, Chardon, Zurbach, IEPC-2011-106 | open (figures only) | 3 |
| S06 | Abashkin et al., IEPC-2007-133 | open (figures only) | 3 |
| S07 | Garnier et al., J. Vac. Sci. Technol. A 17, 3246 (1999), doi:10.1116/1.582050 | closed, abstract only | 3 |
| S08 | Crofton & Young, AIP Adv. 11, 125126 (2021), doi:10.1063/5.0067346 | CC BY but bot-challenged, abstract only | 3 |
| S09 | Ranjan et al., AIP Adv. 6, 095224 (2016), doi:10.1063/1.4964312 (Crossref-checked) | bot-challenged, search summary only | 3 |
| S10 | Yim, Falk, Boyd, arXiv:0802.1960 (J. Appl. Phys. 104, 123507) | open preprint | 4 |
| S11 | Yim, IEPC-2017-060 (NTRS 20170009068) | open | 5 |
| S12 | Eckstein, IPP-Report 9/132 (2002) | open (MPG PuRe) | 4 |
| S13 | Espy et al., Proc. SPIE 1761, 130 (1993), doi:10.1117/12.138921 | closed, abstract only | 3 |
| S14 | Cheng & Martinez-Sanchez, IEPC-2007-250 | open | 6 |
| S15 | Passet, Panelli, Battista, Particles 7, 121 (2024), doi:10.3390/particles7010007 | abstract only (MDPI HTTP 403) | 5 |
| S16 | Nikiporetz et al., IEPC-2007-7 | open | 3 |
| S17 | Tejeda & Knoll, Acta Astronaut. 203, 268 (2023), doi:10.1016/j.actaastro.2022.11.055 | not accessed | 3 |
| S18-S21 | Kim et al. 2001; Duan et al. 2014; Tondu et al. 2008; Yamamura & Tawara 1996 / Eckstein 2007 | cited by other sources, not accessed | 3-4 |
| S22 | repository files (schema, `bridge_lib.jl`, `hall_map.py`, `materials.py`, ...) | read-only | 7 |
| S23 | Borosil (BN-SiO₂) elevated-temperature sputter study, Nucl. Instrum. Methods B (2022); authors not retrieved | not accessed | 3 |

## 10. Rules for extending the database

- **New entries.** Every new entry needs a source that was actually read, an evidence level, an evidence class, an energy
  range (or a stated TBD reason), an uncertainty, an applicability domain, a validation status and a transformation
  chain. Numbers must be transcribed exactly. Unit conversions, angle conversions and digitization go into
  `transformation_chain`.
- **Unverified information.** Anything taken from a search summary or from memory is marked "verify".
- **N/O measurements.** A measured N/O entry on BN, BN-SiO₂ or SiC may be added only from a source that was actually
  read, or from hardware test data. The guard test `test_no_n_o_projectile_claimed_measured_on_primary_walls` must then
  be updated deliberately, with the reason logged.
- **Wiring into a model.** Connecting any entry to `life.py`, `archengine.py` or a Hall-map post-processor is a model
  change. It needs an owner decision and an entry in `docs/HISTORY.md`, and the result must carry the extrapolation
  flags.
