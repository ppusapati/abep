# Reduced RF model: limitations

`abep_sim/rf_reduced.py` is **model-derived** with status `UNVALIDATED_REDUCED_RF_MODEL`, and
`score_bearing = False` always. Its uses are hypothesis generation, operating-grid design and experiment planning.
It never declares an architecture viable (spec §14). `rf_branch` raises `ScoreBearingError` if asked to be
score-bearing.

## Chain

P_DC → P_net,feed (η_bus→feed) → P_absorbed (η_antenna) → `plasma_chem.solve_global` → polytropic magnetic nozzle → T.

## Explicit inputs; no defaults

Every one of these inputs is a `Quantity` with evidence, or the named unvalidated reference relation from
`archengine.magnetic_nozzle` (`archengine_v1_eta_det`, `archengine_v1_divergence`):
- chamber geometry and gas temperature;
- h_l, the magnetised-wall factor and the Clausing factor;
- η_bus→feed and η_antenna;
- γ, R_m and B0;
- detachment and divergence.

`P_reflected_W` and `P_forward_W` stay **TBD** unless measured evidence is supplied; they are never zero by default.

## Energy bound (enforced)

P_kin = I_exit · E_i ≤ P_abs − P_ionization/excitation − P_dissociation − P_wall, and T ≤ √(2 ṁ_i P_kin,max).

A violation is `MODEL_ERROR` and the thrust is withheld, never clipped. At the global model's own power balance,
P_kin,max equals its exit-electron energy flux (2 T_e per electron). So with γ = 1.2 the polytropic
E_i = T_e[½ + γ/(γ−1)(1 − R_m^(1−γ))] exceeds the available energy beyond R_m ≈ 3–5; on the test fixture the
bound fires between R_m = 3 and 5. This is an inconsistency between the source model and the nozzle relation.
The bound exposes it instead of hiding it.

## Unresolved physics (propagated in every result's `limitations`)

- RF antenna impedance closure; S11 and reflected power.
- High-fidelity wave–plasma coupling.
- Plasma detachment; magnetic-nozzle kinetic effects; non-Maxwellian EEDF.
- Plume interaction.
- Atomic-oxygen material lifetime; long-duration wall and antenna erosion.
- **Chemistry.** `plasma_chem` uses unverified Arrhenius-class rates: the N₂ fit was about 3× off and the N fit
  about 2× low (CLAUDE.md next-work item 6), and the HallThruster.jl tables are not unified with it.
- The exit ion's Bohm energy is not included in the global model's power balance.

## Not used as evidence

The helicon card in `thruster.py` is an exploratory prior and is not used.
