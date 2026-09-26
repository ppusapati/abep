# Pre-ionizer → Hall interstage model (`interstage_v1`)

| item | value |
|---|---|
| module | `abep_sim/interstage.py` (`MODEL_VERSION = "interstage_v1"`) |
| interchange schema | `schemas/architecture_comparison/interstage_v1.schema.json` (`$defs/case`, `$defs/result`) |
| tests | `tests/test_interstage.py` |
| architectures | `rf_hall`, `ecr_hall` (one common model). `hall_only` has no interstage and is refused. |
| status | DRAFT for owner review, 2026-09-26. Not wired into `archengine` (wiring would be a model change and the goldens must not move). |
| milestone support | **A**: supports. **B**, **C**: not yet (see §9). |

This model does **not** compare architectures and makes no Hall-performance claim. It computes, for **stated inputs**, how
much of the ion current leaving an RF or ECR pre-ionizer reaches the Hall channel, and where the rest and its energy go.
With the sourced data available today it cannot run a real air case: the recombination rates it has are not valid at
interstage electron temperatures, so it refuses (§6). That refusal is the intended behaviour.

## 1. Scope and interfaces

```
 RF / ECR source exit ──► interstage duct (length L, cross-section, wall, B) ──► junction ──► Hall channel
   (source lane output)    wall loss, volume/wall recombination,                 │   captured ions + Hall-path neutrals
                           charge-state evolution, neutral transport             └──► plume / leak (uncaptured ions,
                                                                                      leak-path neutrals)
```

* **Input** is the source exit state: ion densities and axial speeds by species and charge state, T_e, neutral densities,
  neutral flows and neutral temperature. It comes from the RF/ECR source lanes. Here it is only an input and is never
  assumed.
* **Geometry**: circular or annular duct (length, radii), wall-material label, axial B. Wall coefficients (recombination
  probabilities, h factors, cross sections) are separate, sourced inputs. The material label carries no data.
* **Junction**: ion capture fraction per species, and the effective areas (area × transmission probability) of the
  Hall path and of all leak paths.
* **Output** (`$defs/result`): η_transport and its decomposition, flows by species, charge-state fractions, neutral
  pressures and pressure drop, reaction event rates, wall heat and ion impact energy, an energy ledger, the conservation
  residuals, numerics, provenance of every input, assumptions, and the milestone statement.
* Hall-closure uncertainty (layer 1/2, CLAUDE.md) never enters this block. The model takes no Hall transport input, and
  its outputs never depend on a Hall closure.

## 2. State and equations (steady, quasi-1-D plug flow)

Coordinate z ∈ [0, L]. A = duct cross-section and P = wetted perimeter (circular: πR², 2πR; annular: π(r_o² − r_i²),
2π(r_o + r_i)). The state holds ion particle flows N_s(z) = n_s v_s A [s⁻¹] for every ion species s (charge Z_s,
constant supplied axial speed v_s), and neutral particle flows G_k(z) [s⁻¹].

**Ion balance**

  dN_s/dz = − h_s n_s u_B,s P + A Σ_r ν_{r,s} R_r

* u_B,s = (Z_s e T_e / M_s)^{1/2}. For Z = 1 this is the Bohm speed of Lieberman slide 41. For Z > 1 it is the
  isothermal, cold-ion generalization (model-derived; the NRL-formulary ion-sound-speed form was not accessed in this
  session, **verify**).
* Γ_wall = h n₀ u_B (Lieberman slides 41 and 44). In Lieberman's formula n₀ is the **centre** density. This model uses
  the plug-flow (cross-section-average) density n_s = N_s/(v_s A) in its place (**assumed**). The h values of every
  closure refer to n₀, so the wall flux is biased by the unmodelled ratio n₀/⟨n⟩ (≥ 1 for a centre-peaked profile, i.e.
  the model under-states the wall loss by that ratio).
* h_s depends on the radial-loss closure, which is chosen explicitly (there is no default):
  * `lieberman_unmagnetized`: h_R = 0.8 / (4 + R/λ_i)^{1/2}, with λ_i = 1/(n_g σ_i) (Lieberman slides 38 and 44).
    Circular duct only, B = 0 only, total neutral pressure < 100 mTorr (13.3 Pa; 1 Torr = 133.32 Pa, Chiggiato Table 1).
    Two extrapolations, both **model-derived applicability, not validated** (EVIDENCE.md level 6), which the case
    provenance must state:
    (i) *gas*: Lieberman states the formula for argon; N₂/O/Xe is an extrapolation;
    (ii) *configuration*: h_R is the edge-to-centre ratio of the density profile of an **ionization-sustained**,
    low-pressure discharge in equilibrium. The interstage plasma is **source-free and decaying** while it drifts
    through a transport duct, so its radial profile need not relax to that shape within the duct length.
  * `strong_axial_B_no_radial_loss`: h = 0. This is the idealized limit of Lieberman slide 53 (Example 2: "assume no
    radial losses" under a strong axial field). It requires B > 0 and is an upper bound on duct transmission, not a
    prediction.
  * `explicit_h`: a sourced h per ion species. This is the only route for a partially magnetized duct or an annulus
    (catalogue entry `magnetized_cross_field_h` = TBD).
* R_r = k_r Π(reactant densities) is the volume event rate of the two-body reaction r [m⁻³ s⁻¹], and ν_{r,s} is its net
  stoichiometric change of s. n_e = Σ Z_s n_s (quasi-neutral).

**Electron energy removed by recombination.** Each electron-consuming recombination reaction declares the energy
removed from the electron fluid per event (no default):

* `recombining_electron_thermal_1.5Te`: (3/2) T_e, the mean energy of a Maxwellian electron. This is **assumed**: it
  ignores the energy dependence of the cross section.
* `recombining_electron_rate_weighted_(1.5+alpha)Te`: (3/2 + α) T_e, where α = d ln k/d ln T_e is the exponent of the
  power-law rate. This is **model-derived** (the derivation below is this lane's own, not taken from a source): for a
  Maxwellian, k(T) = ⟨σv⟩ = ∫σ v f(ε;T) dε with f ∝ T^{−3/2} ε^{1/2} e^{−ε/T}, so dk/dT = ⟨σvε⟩/T² − 3k/(2T) and
  ⟨σvε⟩/⟨σv⟩ = (3/2 + α) T. It is exact only for Maxwellian electrons and a rate that is a power law over the case's T_e.
  It is refused if 3/2 + α < 0.
* or a sourced energy per event.

The (3/2) T_e choice is biased high whenever α < 0: for the Sheehan & St.-Maurice exponents it gives 1.5 T_e where the
rate-weighted value is 1.11 T_e (N₂⁺, α = −0.39) or 0.80 T_e (O₂⁺, α = −0.70). Each result reports the value used and
its basis per reaction (`reactions.<id>.electron_energy_loss_eV`, `..._basis`).

**Neutral balance**

  dG_k/dz = Σ_s h_s n_s u_B,s P w_{s,k} + A Σ_r ν_{r,k} R_r − 2 Γ_rec,k + Γ_rec,k′

* w_{s,k}: the declared neutralization products of ion s at the wall. They must conserve elements and mass. Ion masses are
  neutral mass − Z m_e (`ion_mass_from_neutral`).
* Wall atom recombination 2 X → X₂ at probability γ: Γ_rec = ½ γ (¼ n_X ⟨v⟩) P per unit length (impingement ¼ n⟨v⟩,
  Chiggiato §2.1). γ is a sourced input; N and O on any wall material are TBD.

**Neutral pressure (free-molecular)**

  p_k(L) = Q_k(L)/C_J,k,  p_k(z) = p_k(L) + (1/(C_duct,k L)) ∫_z^L Q_k dz′,  Q_k = G_k k_B T_n

* C_duct = ¼⟨v⟩ A τ (Chiggiato Eqs. 19–20), with ⟨v⟩ = (8 k_B T/(π m))^{1/2} (Eq. 3).
* τ comes from the Santeler equation for circular tubes, τ = 1/(1 + (3L/8R)(1 + 1/(3(1 + L/7R)))), error < 0.7 %
  (Santeler 1986, Chiggiato Eq. 21), or from an explicit sourced τ (annulus), or an explicit sourced conductance
  (other regimes).
* C_J = ¼⟨v⟩(A_hall,eff + A_leak,eff) is the junction aperture (Chiggiato Eq. 13), with zero downstream back-pressure.
  The duct resistance is spread uniformly along L (1-D free-molecular diffusion; assumption).
* Entry boundary: the net flow of each neutral species across the source-exit plane is the supplied `neutral_flow`
  (zero for a species the source does not emit). A species formed in the duct can have a nonzero entry partial
  pressure with zero net entry flow (a reflecting entry: no net back-flow into the source). Inside the duct a species
  may flow upstream locally.
* Numerics: the integral ∫_z^L Q dz′ uses the end-corrected (Euler–Maclaurin) trapezoidal rule on the RK4 grid, and the
  RK4 mid-step pressures use cubic-Hermite interpolation with dp/dz = −Q/(C_duct L). Both keep the scheme fourth order
  in the step (the fixture's step-doubling change drops ≈ 16× per halving).
* Densities n_k = p_k/(k_B T_n) feed back into the ion and reaction equations. The coupled problem is solved as a fixed
  point on G_k(z), using under-relaxed Picard or Anderson acceleration (Walker & Ni 2011; depth and damping are explicit
  inputs). Convergence is always judged by the true pressure residual. A zero-length duct reduces to its entrance
  aperture: p(0) − p(L) = Q/(¼⟨v⟩A), τ(0) = 1.

**Junction**

* Captured ions: N_s^cap = f_cap,s N_s(L). Plume leakage: N_s(L) − N_s^cap (the ions leave with their electrons).
* Neutral split by free-molecular conductance: G^leak = G(L) A_leak/(A_hall + A_leak). This split is species-independent.

**Outputs**

  η_transport = Σ_s Z_s N_s^cap / Σ_s Z_s N_s(0)   (ion *current* delivered / ion current leaving the source)
  η_duct = Σ Z N(L) / Σ Z N(0),  η_junction = Σ Z N^cap / Σ Z N(L),  η_transport = η_duct · η_junction

The module also reports η_transport,particle (ion count basis), η_transport,mass, and the total mass delivery fraction
(ions + neutrals). Charge-state fractions per element are given at the entry, the exit and in the delivered stream, plus
axial profiles.

**Sheath, wall energy, electron energy**

* Floating dielectric wall only. The sheath voltage comes from Σ Z n u_B = ¼ n_e v̄_e exp(−V_s/T_e), with
  v̄_e = (8eT_e/πm)^{1/2}. For one singly charged species this is exactly V_s = (T_e/2) ln(M/2πm) (Lieberman slide 48;
  "V_s ≈ 4.7 T_e for argon" is reproduced in the tests). The several-species form is a generalization (model-derived).
* Each wall-lost ion deposits its axial kinetic energy + Z(T_e/2 + V_s) (presheath + sheath, slide 48) + its
  neutralization energy (the formation-energy difference). Each of its Z electrons deposits 2T_e (slide 50).
* Isothermal electrons (the only implemented closure, `isothermal_source_conduction`): T_e is held at the source-exit
  value. The power needed for this is reported as `electron_heat_from_source_W`. It includes the wall electron/ion
  energy, the inelastic electron losses of reactions, and the axial kinetic energy given to ions born in the duct. It is
  power the **source** must supply, so it belongs to `rf_source` / `ecr_source` in `bus_power_boundary_v1`, not to a new
  consumer. A self-consistent electron energy equation (ambipolar-field work, field-aligned conduction) is TBD, and asking
  for another closure is refused.

## 3. Conservation gates (CLAUDE.md rule 4)

For every solve the module reports and gates, relative to throughput:

| balance | definition |
|---|---|
| elements | atoms of each element in (ions + neutrals at z = 0) = out (captured + plume ions, Hall-path + leak neutrals) |
| charge | Σ Z N(0) = Σ Z (N^cap + N^plume + N^wall) − Σ_r Δq_r × events_r |
| mass | Σ (M_i + Z m_e) N + Σ M_k G, in = out |
| energy | E_in (ion kinetic + formation, electron enthalpy 5/2 T_e per electron, neutral formation) + conducted source heat = E_out (Hall and plume streams, neutral formation) + sinks (wall ion kinetic, presheath + sheath, neutralization, wall electron, wall atom recombination, volume reaction heat/radiation) |

Neutral thermal enthalpy is excluded: isothermal walls at T_n hold it (this is an assumption). A result is `OK` only if
every residual is finite and ≤ `numerics.conservation_rtol` (an explicit input). The fixture reaches < 10⁻¹² because
RK4 preserves the linear invariants to round-off. A failed gate returns `MODEL_ERROR` with every performance field
`null`.

**What the energy gate does and does not test.** The element, charge and mass gates are independent physical checks.
The energy gate is not. Under the only implemented electron closure (`isothermal_source_conduction`),
`electron_heat_from_source_W` is *defined* as the electron-energy residual: it is built from the same terms as the
sinks, so −d(ion + electron + neutral fluxes)/dz + dE_cond/dz = Σ d(sinks)/dz holds term by term. The energy residual
therefore catches coding and bookkeeping errors only (a term added to one side and not the other, a wrong unit). It
cannot detect a physics error in the energy model. A physical energy-conservation test needs a self-consistent
electron energy equation, which is TBD (§2).

Further gates:
* Step doubling: n_steps vs 2 n_steps, with the change ≤ `convergence_rtol`, else `MODEL_ERROR`. Each compared quantity
  is normalised by one scale shared by both runs: ion flows by the ion entry flow, neutral exit flows by the largest of
  the neutral entry flow and the exit flows of either run, entry pressures by the larger entry pressure. A quantity that
  is zero in both runs is skipped. A non-finite change, or a non-finite state anywhere in the integration, is
  `MODEL_ERROR` (never `OK`), and non-finite numbers are reported as `null`. The earlier normalisation by
  max(ΣG₀, 10⁻³⁰⁰) turned a zero neutral entry flow into NaN, and the gate then passed silently. The regression test
  `test_zero_neutral_entry_flow_step_doubling_gate_is_not_bypassed` covers it.
* Neutral boundary consistency: the supplied source-exit neutral densities must match the densities that the supplied
  flows imply through duct + junction (within `boundary_rtol`), else `INFEASIBLE`. The diagnostics give the flow-path
  values. `flow_path_entry_densities()` returns what the source model must match. The source and interstage lanes
  therefore have to agree on one pressure, and neither lane can pick it independently. **Source lanes must take the
  entry densities from `flow_path_entry_densities()`** (same grid, same quadrature), not from an independent
  calculation. The flow-path entry pressure carries a discretisation error, reported as
  `diagnostics.p_entry_step_doubling_rel_change`, so `boundary_rtol` must not be set below it. Otherwise an
  independently exact density can be rejected as `INFEASIBLE`. (With the second-order scheme of the first draft
  (plain trapezoid, linear mid-step pressures), a reviewer's analytic case at 160 steps differed by 1.4 × 10⁻⁶. With the present fourth-order scheme, the
  single-ion analytic test agrees to < 10⁻⁷ at 100 steps.)
* Infeasible flow paths (a closed duct or junction with a positive neutral throughput; a duct that consumes more of a
  species than enters) return `INFEASIBLE`.

## 4. Validity domain (refused outside it; no silent extrapolation)

| quantity / formula | domain enforced | source of the bound |
|---|---|---|
| free-molecular duct conductance (Santeler, explicit τ) | Kn = λ/D_h > 0.5 everywhere in the duct, λ = 1/(√2 n σ_c) | Chiggiato Table 7 (free molecular Kn > 0.5), Eqs. 7, 10 |
| junction split | Kn(λ(L), D_junction) > 0.5 | same |
| transitional / viscous (Kn ≤ 0.5) | only via `explicit_conductance` with a sourced value; the Leybold Knudsen equation (Eq. 1.26; air at 20 °C, l ≥ 10 d) is provided as a helper for that input, and is not applied automatically to other gases | Leybold 2016 §1.5.3 a), p. 16 |
| Lieberman h_R | B = 0, circular, p_total < 100 mTorr | Lieberman slide 44 ("argon") |
| strong-B limit | B > 0; an idealization | Lieberman slide 53 |
| rate coefficients | each within its source-stated range of its variable (T_e in eV or K, or ion axial energy) | per record |

The Knudsen domain is judged on the **converged** neutral profile. The entry-flow estimate (uniform supplied flows) is
used only when no converged state exists: if the solve fails and that estimate is itself outside the free-molecular
domain, the case is refused with `InterstageDomainError`. A case whose converged profile is in-domain (e.g. with the
neutrals depleted by in-duct ionization) is therefore never refused because of a provisional iterate.

D_h = 4A/P for an annulus (an assumed characteristic dimension). The mixture mean free path uses
1/(√2 Σ n_k σ_k), a generalization of Chiggiato Eq. 7.

**Pressure regime implication.** At room temperature and the Table 6 N₂ cross section, Kn > 0.5 in a duct of hydraulic
diameter D requires p_total < k_B T/(√2 σ_c · 0.5 D). The model refuses outside this range. Whether a real RF or ECR
source exit is in that regime depends on the source lane's exit pressure, which is an input here.

Magnetization diagnostics (electron and ion gyroradii vs the radial scale) are reported, but they do **not** select the
closure: no sourced magnetization threshold has been accessed, so the choice stays explicit.

## 5. Process completeness (no listed process class omitted silently)

Every volume reaction declares its `process` class, and the declaration is checked against the reaction's structure
(e.g. `electron_impact_excitation` must be e + S → S + e). The case must either model or explicitly exclude, with a
written justification (a source or a bound), each of these required keys:

| key | for |
|---|---|
| `volume_recombination:<ion>` | every ion |
| `electron_impact_ionization:<species>` | every species |
| `ion_neutral_charge_transfer:<ion>` | every ion (if the case has neutrals) |
| `electron_impact_excitation:<species>` | every species |
| `electron_elastic_energy_loss:<neutral>` | every neutral |
| `electron_impact_dissociation:<species>` | every molecular species (neutral or ion) |
| `wall_atom_recombination:<atom>` | every atomic neutral |

A reaction addresses `<process>:<S>` when it declares that process and S is one of its heavy reactants. An unaddressed
key refuses the solve (`InterstageTBDError`). The same key may not be both modelled and excluded. The electron-energy
loss classes (excitation, elastic, dissociation) are required because `electron_heat_from_source_W` would otherwise be
under-counted silently.

The claim is limited to these classes. The gate checks that each class is modelled or excluded *per species*. It does
not check that a modelled class is complete (e.g. that every excited state is included), which is the job of the
sourced reaction set. Only two-body reactions are implemented. Three-body recombination, ion–ion reactions and negative
ions are TBD and are refused.

Each reaction must conserve elements, charge and mass (to `conservation_rtol`). Its declared electron energy loss must
cover its endothermicity (the formation energies are relative to the case's stated `energy_reference`), else it is
refused.

## 6. Data catalogue (`interstage.CATALOGUE`) and what is TBD

All values were accessed 2026-09-26. Evidence classes follow docs/EVIDENCE.md.

| key | value | source | class | note |
|---|---|---|---|---|
| ionization_energy:N / N⁺ | 14.53413 / 29.60125 eV | NIST ASD (doi:10.18434/T4W30F) | measured / inferred | N II printed in brackets by ASD (not a direct experimental value; verify bracket definition) |
| ionization_energy:O / O⁺ | 13.618055 / 35.12112 eV | NIST ASD | measured | |
| ionization_energy:Xe / Xe⁺ | 12.1298437 / 20.975 eV | NIST ASD | measured / inferred | Xe II bracketed |
| ionization_energy:N2 | 15.581 ± 0.008 eV | NIST WebBook (IE, evaluated) | measured | |
| collision_cross_section:N2 / O2 | 0.43 / 0.40 nm² | Chiggiato Table 6 (elastic, room T) | inferred | lecture gives no primary reference; uncertainty not stated (verify) |
| dissociative_recombination:N2+ | 2.2×10⁻⁷ (T_e/300)^−0.39 cm³ s⁻¹ | Sheehan & St.-Maurice 2004, abstract | inferred | **valid T < 1200 K (0.103 eV) only**, ground state |
| dissociative_recombination:O2+ | 1.95×10⁻⁷ (T_e/300)^−0.70 cm³ s⁻¹ | same | inferred | same |

**TBD** (a solve that needs them refuses until they are supplied with a source):
* N₂⁺ and O₂⁺ dissociative recombination at T_e > 1200 K. The interstage T_e is of order the source T_e (eV), so the
  only sourced rates above are **refused** in any realistic case (a test checks this).
* D₀(N₂), D₀(O₂), the O₂ ionization energy, and the atomic-O gas-kinetic cross section.
* Ion–neutral total cross sections (N₂⁺/N₂, O⁺/O, Xe⁺/Xe) at the interstage ion energy (Lieberman closure only).
* N and O wall-recombination probabilities on the chosen wall material.
* The junction ion-capture fraction (field-topology dependent: measurement or a validated 2-D model).
* The edge-to-centre ratio for a partially magnetized duct.

The recombination rates, cross sections and wall coefficients the model needs overlap the air chemistry that
CLAUDE.md "Next work" item 4 defers (O₂/O only after gates 1–3). This lane must not pull that chemistry forward. It
supplies the slots and refuses until the data exist.

## 7. Sources (all openly accessible)

| id | reference | used for |
|---|---|---|
| Lieberman 2015 | M. A. Lieberman, short course "Principles of plasma discharges and materials processing" (LiebermanShortCourse15), https://people.eecs.berkeley.edu/~lieber/Day1View150315crop.pdf; slide numbers are the numbers printed on the slides | u_B, Γ_wall (41); λ_i (38); h_l (43); h_l, h_R and "< 100 mTorr in argon" (44); V_s, v̄_e (48); 2T_e electron energy (50); worked example λ_i = 0.03 m → h ≈ 0.3, u_B ≈ 2.9 km/s for argon at 3.5 V (52); strong axial B, no radial loss (53) |
| Chiggiato 2014 | P. Chiggiato, "Vacuum Technology for Ion Sources", CAS-CERN Accelerator School, arXiv:1404.0960 | ⟨v⟩ (Eq. 3, Table 4: N₂ 470 m/s at 293 K); λ (Eq. 7); σ_c (Table 6); Kn (Eq. 10), regimes (Table 7); aperture C (Eq. 13), C′ N₂ 117.5 m³ s⁻¹ m⁻² (Table 8); C = C′Aτ (Eqs. 19–20); Santeler τ (Eq. 21), long-tube limit (Eq. 22, < 10 % for L/R ≫ 20); series/parallel (Eqs. 26–28); 1 Torr = 133.32 Pa (Table 1) |
| Santeler 1986 | D. J. Santeler, "New concepts in molecular gas flow", J. Vac. Sci. Technol. A 4(3) (1986) 338–343, doi:10.1116/1.573923 (bibliographic data via Crossref, 2026-09-26; full text not accessed). The formula is used as given by Chiggiato Eq. 21. Chiggiato's ref. [9] prints page 348, which Crossref assigns to a different paper by the same author ("Exit loss in viscous tube flow", JVST A 4, 348–352, doi:10.1116/1.573925); that is a citation error in the secondary source | τ |
| Leybold 2016 | Leybold GmbH, "Fundamentals of Vacuum Technology", Part No. 199 90, Ed. 2016, §1.5.3 a) "Conductance for piping and orifices", Eq. 1.26, p. 16 | Knudsen-equation helper (air, 20 °C, l ≥ 10 d) |
| Sheehan & St.-Maurice 2004 | J. Geophys. Res. Space Phys. 109(A3), doi:10.1029/2003JA010132, **abstract only** (Crossref) | DR rates, T < 1200 K |
| NIST ASD / WebBook | https://doi.org/10.18434/T4W30F; https://webbook.nist.gov/cgi/cbook.cgi?ID=C7727379&Mask=20 | ionization energies |
| Walker & Ni 2011 | SIAM J. Numer. Anal. 49(4) 1715–1735, doi:10.1137/10078356X (bibliographic data via Crossref) | Anderson acceleration (numerics only) |

The NRL Plasma Formulary was not accessible in this session (HTTP 403 / bot challenge; not bypassed). The Z > 1 sound
speed and the gyroradius definition are therefore marked **verify**.

## 8. Why η_transport may be the decisive RF/ECR variable

The break-even lane (`abep_sim/breakeven.py`, `breakeven_v1`; derivation in
`docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md` as referenced by that module; sibling lane in progress, not in this worktree) writes the ions delivered
into the Hall beam as I_S = η_transport · I_src. A source with bus-referred production cost C_src [W per A of source
ions] therefore delivers ions at

  C_delivered = C_src / η_transport.

The arm can break even only if C_delivered is at most the supremum break-even delivered cost of the Hall reference
point. So `place_evidence(...)["eta_transport_min"] = C_src / sup C_breakeven` is the **required η_transport** for that
source and reference point. Four consequences, none of which ranks RF against ECR:

1. η_transport divides the source cost directly. Any shortfall in it multiplies the cost the source must beat, whatever
   the source technology.
2. η_transport is the one quantity where the **common** Hall block and the **arm-specific** source meet. The downstream
   Hall accelerator, feed state, cathode and bus boundary are common, so differences between `rf_hall` and `ecr_hall`
   enter through the source cost, the source exit state and this transfer.
3. The same exit state gives the same η_transport for either arm (tested). An RF/ECR difference in η_transport can only
   come from different exit states (T_e, ion speeds, charge states, neutral pressure) or a different interstage geometry
   or B field. Those inputs belong to the source lanes and to the design, not to this model.
4. The losses are not free even when η_transport is acceptable. The wall heat and the conducted electron power are extra
   power that the source must provide and the thermal design must reject.

Units must match. `eta_transport` (charge-current basis) pairs with costs in W/A. `eta_transport_particle` (ion-count
basis) pairs with costs in eV per ion. `compare_with_required(result, eta_transport_required)` returns
margin = η_transport − η_required for **one** case against a sourced requirement. It is a condition check, not an
architecture comparison, and both sides' uncertainty envelopes must be propagated before any use.

Interface with `breakeven_v1`: that lane spells the dimensionless unit `"1"` and uses an `Evidenced(value, unit,
evidence_class, source)` record without an uncertainty field. This module spells it `"-"`. Every dimensionless input
here accepts either spelling. `compare_with_required` accepts a `Sourced` or any record with those four attributes
(duck-typed, with no import of the sibling module). `eta_transport_evidence(result)` returns the keyword arguments of a
breakeven `Evidenced` (unit `"1"`, evidence class `model-derived`). breakeven_v1 accepts only 0 < η ≤ 1, so an
η_transport > 1 (in-duct ionization) will be refused there. Choosing one spelling project-wide is an open item for the
owner.

## 9. Milestone support

| milestone | status | what is needed to reach it |
|---|---|---|
| **A** conditional selection | **supports.** "`rf_hall`/`ecr_hall` is baseline provided η_transport ≥ η_transport,min (breakeven_v1)" becomes a computable, input-traceable condition, with the list of TBD inputs it depends on (§6). | owner review of this model and schema |
| **B** physics-backed selection | **not yet** | an admitted Hall transport closure (for η_transport,min through the break-even Hall reference); DR and ion–neutral data valid at the interstage T_e; a magnetized wall-flux closure or measurement; junction capture data; a transitional-flow conductance for the actual gas if Kn ≤ 0.5; measured source exit states |
| **C** proposal/PDR freeze | **not yet** | wall heat and ion impact energy coupled to `abep_sim/thermal_life.py`; conducted electron power charged to `rf_source`/`ecr_source` in `bus_power_boundary_v1`; interstage mass and hardware in the mass ledger (the `"interstage"` entry of break-even `HARDWARE_KEYS`); hardware data |

Open question for the owner: `bus_power_boundary_v1` has no interstage component. A **powered** interstage (bias
electrodes, guide coils) would need one. The break-even lane treats `interstage_loss_bus_W ≠ 0` as not
v1-conformant. This model assumes an unpowered, floating interstage.

## 10. Limitations (also in `result["assumptions"]`)

* The model is steady, quasi-1-D plug flow with constant ion speeds: no axial electric field, no ion acceleration or
  deceleration, no radial structure beyond the h factor.
* Ions are cold. Electrons are isothermal. The wall is floating and dielectric. Biased or conducting walls are TBD.
* Neutrals are free-molecular and isothermal at T_n. They flow independently by species, with zero back-pressure
  downstream of the junction.
* The junction is a lumped capture fraction plus a conductance split. There is no ion optics.
* The wall flux uses the cross-section-average density in place of the centre density n₀ (§2), and the Lieberman h_R
  is carried over from an ionization-sustained argon discharge to a source-free, decaying plasma of another gas (§2).
* Recombination electron energy is (3/2) T_e (assumed, biased high for α < 0) or (3/2 + α) T_e (model-derived), as
  declared per reaction (§2).
* The energy gate is a bookkeeping check under the isothermal closure (§3).
* It is not validated against any interstage measurement. Every output is `model-derived`, conditional on its inputs.

## 11. Using it

```python
from abep_sim import interstage as ist
case = ist.case_from_dict(json_case)                  # schema $defs/case; every number sourced or {"tbd": ...}
n = ist.flow_path_entry_densities(case)               # what the source exit neutral densities must be
res = ist.solve_interstage(case)                      # OK / INFEASIBLE / MODEL_ERROR; raises on TBD / out of domain
```

The exceptions are `InterstageInputError` (missing or invalid), `InterstageTBDError` (TBD input or unaddressed process)
and `InterstageDomainError` (outside a stated formula or rate domain).
