# Experiment mapping (RF maps and Hall evidence)

## RF response maps (`rf_map_v1`, `rf_registry`)

Sweep ṁ × P_RF × B × x_s over N₂, O₂, O where experimentally possible, and Xe.

**Minimum measured outputs:**
- thrust;
- full bus power;
- forward and reflected RF power; absorbed-power estimate;
- mass flow; pressure;
- T_e and n_e; species and ion composition;
- plume divergence;
- stability; ignition and restart;
- thermal state.

**Map rules:**
- Grid axes are (mdot_kg_s, P_dc_W, B0_T). The domain also states composition, pressure and temperature ranges.
- A map is identified by the sha256 of its file.
- Path to use: REGISTER → owner ADMIT (a sha-pinned decision file) → use. A WITHDRAW record revokes admission.
- Interpolation happens only inside the domain. Outside any axis, on different hardware, or in a cell with an
  unmeasured, unstable or unignited corner, the result is `OUT_OF_DOMAIN`. Nothing is clipped.
- **No RF map is labelled admitted before this evidence path exists.**

## Hall evidence

- `HallPoint` records cover measured Vyovrinda points or published analog points, each with its own declared
  domain. There is no interpolation or scaling between points.
- Analog points are never score-bearing.
- A Vyovrinda point is score-bearing only under a sha-pinned owner admission.
- Transport closures always go through `hall_ensemble.require_admitted`. Screening candidates are refused in every
  use, and the credible set is empty.

## Hardware campaign split (§30)

- **H1-RF:** standalone RF characterization.
- **H1-Hall:** standalone Hall characterization, especially Xe boost.
- **H1-P:** the parallel test. Do not begin it until the individual branch envelopes are characterized.
- H1-P includes fixed-total-power cases, P_RF + P_Hall = constant, to test whether reallocating power from RF to
  Hall increases total thrust.
