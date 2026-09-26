# Architecture break-even relations (breakeven_v1): derivation

**Question.** Can a pre-ionizer pay for itself? This document asks it for `rf_hall` and `ecr_hall` against `hall_only`
on the common DC bus boundary `bus_power_boundary_v1`, and answers it **without any absolute Hall prediction**.

**Code.** `abep_sim/breakeven.py` holds the pure functions. It has no defaults and raises `BreakevenInputError` on any
missing or invalid input. It is not wired into `archengine`, so the goldens do not move.
`scripts/architecture/build_breakeven_surfaces.py` computes the surfaces over declared analysis ranges and writes
`breakeven_surfaces_v1.json`. How to read them is explained in `BREAKEVEN_SURFACES.md`, and the tests are in
`tests/test_breakeven.py`.

**Status.** These are analysis relations. They are not predictions and they do not rank the architectures. They name
**no winner**. No Hall transport closure is used, and neither is any screening candidate (`sgb-screen-*`) or any
withdrawn 0-D Hall number (CLAUDE.md "Superseded"). The credible closure set is empty (gate 3 FAIL), so every
Hall-only efficiency component below is an **analysis parameter**, not a value.

## 0. Milestone support

| milestone | what this delivers | what is still needed to reach it |
|---|---|---|
| **A: conditional selection (chiefly supported)** | Closed-form conditions a pre-ionized arm must demonstrate: the required utilization gain Δη_u*, the maximum payable ion production cost C_src*(η_t), and the overhead fraction ω at which no gain can pay. It also marks regions eliminated in power under the most favourable corner of the declared model family, stated conditionally (§10). | Published or measured source ion cost and η_transport on N₂/O/O₂ on the same ion basis (evidence lanes `docs/evidence/rf_source/`, `docs/evidence/ecr_source/`), plus the owner's acceptance of the model-family assumptions A1–A8. |
| B: physics-backed selection | Nothing yet. It supplies the interface: the functions take an admitted closure's η_u0, η_b, η_v and γ without change. | Admitted Hall transport closure(s) for the Vyovrinda geometry (credible set ≠ ∅). Those closures must give η_u0, η_b, η_v and γ with their V_d dependence per member, and measured or closure-derived α, χ, η_v,S and delivered-ion mix. |
| C: proposal/PDR freeze | The inequality structure for mass (§7) and life (§8). | Power-system and thrust mass sensitivities, hardware masses, source and Hall life limits with evidence, thermal closure (`abep_sim/thermal_life.py`, another lane), startup, cathode and mission closure. |

## 1. Scope and common boundary

* **Architectures.** `hall_only`, `rf_hall` and `ecr_hall`. The RF and ECR arms change **only** the pre-ionization
  method. The downstream Hall accelerator, the feed state (ṁ and species), the cathode and the bus boundary are
  common.
* **Boundary.** `bus_power_boundary_v1` (`abep_sim/arch_boundary.py`, built by the power-boundary lane). Its common
  components are `hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor,
  thermal_control, housekeeping`. The source components are `rf_source` (rf_hall) and `ecr_source, ecr_magnet`
  (ecr_hall). `breakeven.py` keeps a copy of the names only. `check_boundary_contract()` resolves the real module
  lazily and raises `BreakevenContractError` if it is absent or its version differs. The contract was cross-checked
  read-only against the unmerged boundary lane on 2026-09-26, and the names and version match. Two ledgers in the v1
  output format can be turned into an overhead directly with `overhead_from_boundary_ledgers`.
* **Feed state is an input.** ṁ reaches the Hall through the common feed. On the air path that is intake → filter →
  compressor → gas chamber → valve. For an arm, the flow also passes through the source. ṁ is **never** changed by the
  break-even analysis. Hall-closure uncertainty stays inside the ionization/acceleration block and does not leak
  upstream (CLAUDE.md, "Scope").
* **Hall-closure calibration nuisance** (P5 registration, coil shape, divergence reading, facility interpretation) is
  not an input, an axis or a design variable here.

## 2. Hall efficiency decomposition (sources)

| relation | source (accessed 2026-09-26) | evidence type |
|---|---|---|
| η_b = I_b/I_d = 1/(1 + I_e/I_b) | Hofer & Gallimore, "Efficiency Analysis of a High-Specific Impulse Hall Thruster", AIAA-2004-3602, Eq. (2), Eq. (7); https://pepl.engin.umich.edu/pdf/AIAA-2004-3602.pdf | definition |
| η_a = T²/(2 ṁ_a P_d) = η_q η_v η_b η_m | ibid. Eq. (4); Goebel & Katz, *Fundamentals of Electric Propulsion: Ion and Hall Thrusters*, JPL Space Science and Technology Series, March 2008 (open JPL edition; Wiley doi:10.1002/9780470436448), Eq. (7.3-16) | definition |
| η_q = (Σ Ω_i/√Z_i)² / Σ(Ω_i/Z_i) | Hofer & Gallimore Eq. (5) | definition |
| η_v = V_a/V_d; η_m = ṁ_b/ṁ_a | Hofer & Gallimore Eqs. (6), (8); G&K Eq. (7.3-11) (η_v = V_b/V_d) | definition |
| T = γ ṁ_i v_i = γ √(2M/e) I_b √V_b; γ = α F_t | G&K Eqs. (2.3-15), (2.3-16) | model (monoenergetic, single species) |
| T = 1.65 I_b √V_b mN (singly charged Xe) | G&K Eq. (2.3-9) | model constant (used as a unit test) |
| discharge loss ε_d = P_abs/I_b [eV/ion] in RF / microwave ion sources | G&K Eqs. (4.5-7), (4.6-27), Sec. 4.5 worked example (230 eV/ion absorbed, 90 % rf supply → 511 W for a 2 A beam) | model + worked example (used as a unit test) |
| wall erosion rate ∝ J_i Y(ε_i) | G&K Eq. (7.5-1) | model |

**Definition note.** Hofer's η_v (Eq. 6) is "the conversion of voltage into axially directed ion velocity", so it
absorbs beam divergence. G&K keep divergence in a separate factor, γ. breakeven_v1 follows G&K:
η_a = γ² η_v η_b η_u q, with q the charge factor (equal to Hofer's η_q for one element). Component values quoted in
Hofer's convention, such as the NASA-173Mv2 abstract ranges η_v 0.89–0.97, η_m 0.86–0.90 and η_b 0.77–0.81 (Xe,
300–900 V, 10 mg/s), are therefore **context only**. They are not inputs.

## 3. Two-population model (assumptions A1–A8)

Two ion populations share the Hall beam:

* **H** ions are born in the Hall discharge. Their beam current is I_H and their composition is mix_H.
* **S** ions are produced in the source and accelerated in the Hall. Their current is I_S = η_t I_src and their
  composition is mix_S.

For a mix with current fractions f_j, masses m_j and charges Z_j, the following quantities are defined:

* μ = Σ f_j m_j/(Z_j e) is the mass per coulomb, and ρ = 1/μ.
* κ = Σ f_j √(2 m_j/(Z_j e)) is the thrust coefficient.
* θ = κ ρ.
* q = κ² ρ/2 is the charge factor.

The mass-utilization shares are u = I μ/ṁ (Hofer's η_m for one population).

```
T   = γ √V_d ṁ N,   N = √η_v θ_H u_H + √η_v,S θ_S u_S
P_d = V_d ṁ D,      D = ρ_H u_H/η_b + ρ_S u_S/η_b,S
η_a = T²/(2 ṁ P_d) = γ² N²/(2D)                      (independent of V_d and ṁ)
1/η_b,S = 1 + (1 − χ)(1/η_b − 1)
u_H = η_u0 − (1 − α) δ_s,   u_S = δ_s,   η_u1 = η_u0 + α δ_s
```

For one population and one element this reduces exactly to η_a = γ² q η_v η_b η_u, which is Hofer Eq. (4) with
divergence separated. The test `test_hofer_charge_utilization_reduction` checks this, and
`test_first_principles_two_population_state` checks the two-population state against a per-species recomputation of
T and P_d.

| # | assumption | evidence class | consequence / how it is bounded |
|---|---|---|---|
| A1 | 0-D efficiency decomposition. η_b, η_v and γ of the Hall-born population do not change when S ions are added, except through χ. | assumed | Admitted closures (milestone B) replace this. |
| A2 | η_b, η_v, γ and η_u0 do not depend on V_d over the V_d change needed to hold the comparison (§4). | assumed | The V_d ratio at break-even is reported so its plausibility can be judged. |
| A3 | α ∈ [0, 1] is the additionality of S ions. At α = 1 they add to the Hall-born ions ("only add ions"). At α = 0 each one replaces a Hall-born ion ("reduces the Hall's own ionization"). | assumed parameter | Scanned over [0, 1]. |
| A4 | χ ∈ [0, 1] is the fraction of the Hall's per-ion electron-current overhead V_d(1/η_b − 1) that an S ion avoids. At χ = 0 the S ion costs the full Hall price V_d/η_b. At χ = 1 it costs only its own current, V_d. | assumed parameter | Scanned over [0, 1]. |
| A5 | η_v,S ∈ (0, 1] is the voltage utilization of S ions, which may be born upstream of the acceleration zone. | assumed parameter | Scanned over [η_v, 1]. |
| A6 | η_t links produced to delivered ions. Lost ions return to the flow as neutrals (ṁ is conserved), so they are already accounted for through u_H. | assumed | η_t must be on the same ion basis as the published cost (§6). |
| A7 | The mass flow ṁ is fixed by the common feed state. | definition of the comparison | ṁ is not a free variable. |
| A8 | The analysis surfaces use a single-species, singly charged beam, the same for H and S. | analysis choice | The module supports mixes. A heavier delivered mix raises the payable cost per ampere (§6.4). |

## 4. (1) Power break-even at the bus, and the two conventions

**Overhead.** Let P_d,bus0 = P_d0/η_ppu,d be the Hall-only discharge bus power. The overhead of an arm, in
`bus_power_boundary_v1` terms, is:

```
rf_hall : O = P_bus[rf_source]                       + Σ_common≠discharge (P_bus,arm − P_bus,hall_only) + P_interstage + P_extraPPU
ecr_hall: O = P_bus[ecr_source] + P_bus[ecr_magnet]   + Σ_common≠discharge (P_bus,arm − P_bus,hall_only) + P_interstage + P_extraPPU
ω = O / P_d,bus0
```

v1 has no interstage component and no extra-PPU component. Supply losses sit inside each component's efficiency, and
added PPU control is booked under `housekeeping`. A v1-conformant overhead therefore has P_interstage = P_extraPPU = 0
(`BusOverhead.boundary_v1_conformant`). Non-zero values are sensitivity terms outside v1, as the task statement
requires. A permanent-magnet ECR stage enters with `ecr_magnet` = 0 W, and that zero must be passed explicitly.

**Equal thrust (bus-power saving).** V_d,1 is chosen so that T₁ = T₀. From T² = 2ṁ η_a P_d, the arm's discharge bus
power is P_d,bus0 · η_a0/η_a1. The net saving is ΔP = P_d,bus0 (1 − η_a0/η_a1) − O. It is at least 0 when the
following holds:

```
dP_Hall_saved = P_d,bus0 (1 − 1/R) ≥ O = P_source_bus + P_interstage + P_extraPPU (+ Δcommon),   R = η_a1/η_a0
```

**Equal bus power (thrust gain).** The Hall discharge receives P_d,bus0 − O. Then T₁/T₀ = √(R (1 − ω)), which is at
least 1 when:

```
R (1 − ω) ≥ 1   ⇔   R ≥ 1/(1 − ω)            (master break-even; identical for both conventions)
```

Both conventions give **the same break-even locus**. Away from it they report different quantities: a bus-power saving
in W and a thrust gain as a fraction. `evaluate_arm` evaluates each convention independently. At break-even it closes
two checks to about 1e-13 on every sampled grid point (`self_checks.conventions_coincide_at_breakeven`, 2003 samples):
the ledger residual of Σ components against the Hall-only bus power, and the energy identity T² = 2ṁ η_a P_d.
**Infeasible region:** ω ≥ 1, where the overhead is at least the whole Hall-only discharge bus power.

## 5. (2) Required utilization improvement Δη_u*

Normalize by the Hall-only values:

```
R_T = √(η_v,S/η_v) θ_S/θ_H,   R_P = (ρ_S/ρ_H) η_b /η_b,S,   n₁ = R_T − (1 − α),   d₁ = R_P − (1 − α)
R(δ) = (η_u0 + n₁ δ)² / (η_u0 (η_u0 + d₁ δ))
```

Break-even holds when q(δ) = (1 − ω)(η_u0 + n₁δ)² − η_u0(η_u0 + d₁δ) ≥ 0. For 0 < ω < 1, q is convex with
q(0) = −ω η_u0² < 0, so exactly one positive root exists:

```
a = (1−ω) n₁²,  b = 2(1−ω) η_u0 n₁ − η_u0 d₁,  c = −ω η_u0²
δ_s* = −2c / (b + √(b² − 4ac))        (INFEASIBLE_NO_GAIN if the denominator ≤ 0)
Δη_u* = α δ_s*                        (INFEASIBLE_UTILIZATION_CAP if δ_s* > δ_max = min(η_u0/(1−α), (1−η_u0)/α))
V_d,1/V_d,0 at break-even = (η_u0 √η_v θ_H / N₁)²   (same in both conventions; assumption A2)
```

**Named cases.** These use the same mix and η_v,S = η_v, so R_T = 1. The optimistic bound is the exception.

| case | α, χ, η_v,S | result |
|---|---|---|
| add-only ("only adds ions") | 1, 0, η_v | **Δη_u* = η_u0 ω/(1 − ω)** (closed form). Independent of η_b, η_v, γ and species at fixed ω. |
| cost-offset ("reduces the Hall's ionization cost") | 1, 1, η_v | Root of (1−ω)(η_u0+δ)² = η_u0(η_u0 + η_b δ). Always below add-only. |
| substitution-only | 0, 1, η_v | Δη_u* = 0, but a delivered share δ_s* = ω η_u0/(χ(1−η_b)) is needed. The gain is purely a lower electron-current cost. |
| optimistic bound | 1, 1, 1 | The most favourable corner of the declared box α, χ ∈ [0,1], η_v,S ∈ [η_v, 1] at equal mix (`self_checks.optimistic_corner_dominates_box`, excess 0). |

**Dependence.** Δη_u* = f(ω, η_u0, η_b, η_v,S/η_v, α, χ, mix ratios). The dimensional inputs enter only through
ω = O η_ppu,d η_b/(V_d I_b0) with I_b0 = η_u0 ṁ ρ_H. So higher V_d, higher ṁ or lighter ions (more I_b0 per kg)
lower the requirement for a fixed overhead in W. **Δη_u* does not depend on η_t.** η_t only relates produced ions to
delivered ions. It fixes what a given source power *achieves* (supply side, §6.3), not what is *required*. At equal
mix Δη_u* also does not depend on η_v, γ and species at fixed ω (self-check 3).

## 6. (3) Break-even ion production cost

### 6.1 Delivered-ion cost
Suppose the whole overhead scales with ions, O = C_del I_S with I_S = δ_s ṁ ρ_S, plus a fixed part O_f. The largest
payable bus cost per ampere delivered into the Hall beam is then:

```
C_del*(δ_s) = [P_d,bus0 (1 − 1/R(δ_s)) − O_f] / I_S          [W/A]
lim δ_s→0, O_f = 0:   C_del*,0 = Π_H (ρ_H/ρ_S) (2R_T − R_P − (1 − α)),   Π_H = V_d/(η_b η_ppu,d)
```

At equal mix:

| case | C_del*,0 |
|---|---|
| add-only | Π_H |
| cost-offset | Π_H(2 − η_b) |
| substitution-only | Π_H(1 − η_b) |
| optimistic | Π_H(2/√η_v − η_b) |

In the add-only case C_del*(δ) = Π_H η_u0/(η_u0 + δ). It falls with the delivered share, so the supremum over any
spend is the marginal value. A fixed overhead O_f > 0 (for example an ECR electromagnet, interstage hardware or common
deltas) lowers the supremum and moves it to δ > 0 (`supremum_breakeven_delivered_cost`). **Physical reading:** a
delivered ion is worth at most what the Hall itself pays per beam ampere, Π_H, adjusted for the offsets χ, α and
η_v,S. That price includes acceleration.

### 6.2 Source-side cost including transport
```
C_src* = η_t · C_del*          (bus W per A of ions PRODUCED in the source)
η_t,min = C_src / C_del*,sup   (below it the source cannot pay at that Hall point)
η_t → 0  ⇒  C_src* → 0: infeasible for every finite source cost (test_eta_transport_to_zero_is_infeasible)
```

### 6.3 Supply side
`achievable_delivered_share` gives δ_s = η_t P_gen/(C_src ṁ ρ_S) and Δη_u = α δ_s. The break-even condition is that
the achieved Δη_u is at least the required Δη_u*. It raises an error if the implied share exceeds the Hall's cap.

### 6.4 Placing published evidence
`bus_referred_source_cost` converts a published cost to bus W/A. There are three power references:

* `absorbed`, the power absorbed by the plasma as in G&K Eq. 4.5-7: divide by the coupling and generator efficiencies.
* `forward`: divide by the generator efficiency.
* `bus`: use as is.

Every stage efficiency must be passed explicitly. A cost in eV/ion becomes W/A after division by the mean charge per
ion. The G&K Sec. 4.5 example is reproduced: 230 eV/ion absorbed with a 90 % supply gives 511 W for 2 A.
`place_evidence` needs `Evidenced` values carrying evidence class and source. It returns:

* the status `CANNOT_BREAK_EVEN_IN_MODEL_FAMILY`, `BREAKS_EVEN_ONLY_IN_LIMIT` or `BREAK_EVEN_POSSIBLE`;
* the payable delivered-share interval;
* η_t,min.

**Ion basis.** Published RF/ECR costs are usually per ampere of grid-extracted beam, and they are referred to generator
input or to incident microwave power. Converting them to "ions leaving a gridless pre-ionizer" can lower the cost, for
example by dividing out grid transparency. Referring them to the bus can only raise it. Until both conversions are
sourced, a published value placed as reported is **neither an upper nor a lower bound** (see the overlay rule in
`BREAKEVEN_SURFACES.md`). **Mix effect:** the mix enters through the factor (ρ_H/ρ_S)(2R_T − R_P − (1 − α)). Delivering a
heavier ion into a lighter Hall beam raises the payable cost per ampere. For example, N₂⁺ delivered into an N⁺ beam at
α = χ = 1 and η_v,S = η_v gives Π_H(2√2 − η_b) instead of Π_H(2 − η_b). A lighter delivered ion lowers it. So the
equal-mix optimistic bound is a bound only at equal mix. Evaluate mixed cases with the module.

## 7. (4) Mass break-even

```
equal thrust:     s_P · ΔP_bus,saved − Δm_prop  ≥  m_source_head + m_generator_PPU + m_magnets + m_interstage + m_thermal_added
equal bus power:  s_T · ΔT          − Δm_prop  ≥  (same right-hand side)
```

`mass_breakeven` requires every term as an `Evidenced` value with its unit. The keys are fixed (`HARDWARE_KEYS`), and
an explicit 0 is allowed while omission is not. It returns the net mass benefit and the required benefit
(Δm_hw + Δm_prop)/s.

| input | status |
|---|---|
| s_P [kg/W] (power-system specific mass: arrays, PCDU, thermal, at the mission point) | **TBD**. Needs power-system sizing (milestone C). |
| s_T [kg/N] (system-mass equivalent of thrust, i.e. drag margin, altitude or intake area) | **TBD**. Needs mission and drag closure. |
| hardware masses | **TBD**. Need source, PPU and magnet designs with evidence. |
| Δm_prop | 0 for the air arm by definition (no stored air). **TBD** for the Xe mode. |

No mass surface is produced because no sensitivity is sourced.

## 8. (5) Life break-even

The life comparison treats each arm as a series system, so its life is the minimum over its life-limiting mechanisms.

```
life break-even:    min(arm limits) ≥ min(hall_only limits)
requirement:        min(limits)    ≥ k_q · t_fire,req,     t_fire,req = 15 000 h (RFP "> 15,000 h firing"); k_q PROPOSED/TBD
arm limits  = { common-hardware mechanisms at the arm's operating point } ∪ { new source mechanisms }
Hall erosion ratio at one wall location/material:  L_arm/L_ref = (J_i Y(ε_i))_ref / (J_i Y(ε_i))_arm     (G&K Eq. 7.5-1)
```

**Left side, life gain from lower Hall stress.** This needs the wall ion flux and energy at both operating points,
which must come from `wall_life_trustworthy` Hall maps (hall_map.py; none exist yet). It also needs the sputter yield
of the wall material for the actual ion mix. The arm runs at a different V_d (§5), which changes ε_i.

**Right side, new source-hardware life limits.** For RF these are window or antenna erosion, coating and the
generator. For ECR they are the microwave window, the magnets and the generator. Each needs a life value with
evidence (evidence lanes `docs/evidence/rf_source/`, `docs/evidence/ecr_source/`, `docs/evidence/wall_life/`).
`life_breakeven` classifies the outcome as `ARM_NOT_WORSE`, `ARM_WORSE_SOURCE_LIMITED` or `ARM_WORSE_COMMON_HARDWARE`.
It refuses a source mechanism that duplicates a Hall-only one and a qualification factor below 1. All values are TBD,
so no life surface is produced.

## 9. No-default and refusal behaviour (CLAUDE.md rule 3)

* No public function or dataclass field in `breakeven.py` has a default (`test_no_defaults_anywhere`).
* The following inputs raise an error:
  * None, NaN, ±inf, bools or strings passed as numbers;
  * efficiencies outside (0, 1];
  * a delivered share beyond the cap;
  * an overhead that is not a `BusOverhead`;
  * a ledger with missing or extra components;
  * a published cost without its power reference or chain efficiencies;
  * an evidence value whose class is "TBD" or whose source is empty.
* Infeasibility is reported as a status and never as a clipped number. The statuses are
  `INFEASIBLE_OVERHEAD_GE_DISCHARGE`, `INFEASIBLE_UTILIZATION_CAP`, `INFEASIBLE_NO_GAIN` and
  `CANNOT_BREAK_EVEN_IN_MODEL_FAMILY`.

## 10. Limitations and what an elimination means

* An elimination here means one thing only. At that Hall operating point and that overhead, **no** combination inside
  the declared box (A3–A5, equal mix) pays in bus power. That claim rests on A1, A2 and A6–A8, all of which are
  *assumed*, and on the Hall-only components being analysis values. It is a **milestone-A elimination candidate** and
  must be presented with those conditions. It is never an architecture ranking.
* Not modelled:
  * neutral-density coupling between source and Hall (A1);
  * η_b, η_v and γ depending on V_d (A2) and on the injected ion distribution;
  * source-induced changes of cathode coupling;
  * plume effects;
  * transients and startup;
  * thermal coupling.
* The mixes on the surfaces are single species. Real air-breathing beams contain N₂⁺, N⁺, O⁺, O₂⁺, NO⁺ and multiply
  charged ions, which the module supports but the surfaces do not scan.

## 11. What reaching milestone B changes

The same functions are evaluated per admitted closure member, with η_u0, η_b, η_v and γ at the member's operating
points. The result is an **envelope** across members, not one answer. α, χ and η_v,S become closure outputs or measured
quantities instead of scanned parameters.

## 12. Hand-calculated points (used in `tests/test_breakeven.py`)

**Reference point.** Test values, not evidence: N₂⁺, η_u0 = 0.5, η_b = 0.7, η_v = 0.9, γ = 0.9, V_d = 300 V and
η_ppu,d = 1. ṁ is chosen so that I_b0 = 1 A, which gives ṁρ = 2 A. Then P_d,bus0 = 300/0.7 = 428.571 W and
Π_H = 428.571 W/A.

1. **Add-only, ω = 0.1.** Δη_u* = 0.5·0.1/0.9 = 0.055556, and the V_d ratio is (1 − ω)² = 0.81.
2. **Cost-offset, ω = 0.1.** n₁ = 1 and d₁ = η_b = 0.7. With δ = 0.5x the condition becomes
   0.9x² + 1.1x − 0.1 = 0. That gives x = 0.084998 and **Δη_u* = 0.0424990**.
3. **Substitution-only (α = 0, χ = 1), ω = 0.05.** n₁ = 0 and d₁ = −0.3, so δ_s* = 0.05·0.5/0.3 = 0.083333 and
   Δη_u* = 0.
4. **C_del* for add-only at δ = 0.05.** R = 1.1, so C_del* = 428.571·(0.1/1.1)/0.1 = 389.61 W/A, which equals
   300·0.5/(0.7·0.55).
5. **Marginal C_del*,0.** The values are:
   * add-only: Π_H = 428.571 W/A
   * cost-offset: 1.3 Π_H = 557.14 W/A
   * substitution: 0.3 Π_H
   * (α, χ) = (0, 0): 0
   * optimistic: Π_H(2/√0.9 − 0.7) = 603.51 W/A
6. **Evidence placement.** C_src = 300 W/A with η_t = 0.9 gives C_del = 333.33 W/A. For add-only the payable interval
   is δ_s ∈ [0, 428.571·0.5/333.33 − 0.5] = [0, 0.142857], and η_t,min = 300/428.571 = 0.7.
7. **Supply side.** P_gen = 60 W with C_src = 300 W/A and η_t = 0.5 gives I_src = 0.2 A, I_S = 0.1 A and δ_s = 0.05.
8. **G&K Sec. 4.5.** 230 eV/ion absorbed, divided by 0.9 supply efficiency, is 255.56 W/A. For 2 A that is 511.1 W.
9. **Thrust constant.** Singly charged Xe with γ = η_v = 1 gives T/(I_b√V_b) = 1.65 mN, matching G&K Eq. (2.3-9).
10. **Mass.** For equal thrust, s_P = 0.01 kg/W and ΔP = 100 W give 1.0 kg, which equals the 1.0 kg of hardware, so
    the net benefit is 0. For equal bus power, s_T = 200 kg/N, ΔT = 2 mN and Δm_prop = −0.1 kg give a net benefit of
    0.4 + 0.1 − 1.0 = −0.5 kg.
11. **Life.** The Hall-only limits are 20 000 h (erosion) and 30 000 h (cathode). The arm has 40 000 h erosion,
    30 000 h cathode and 18 000 h RF window. The result is `ARM_WORSE_SOURCE_LIMITED`. With k_q = 1.5 the requirement
    is 22 500 h, which the arm does not meet.
