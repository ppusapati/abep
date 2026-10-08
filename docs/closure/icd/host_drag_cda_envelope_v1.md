# Host-spacecraft drag-area envelope (IR-HOST-DRAG-01, A9.38 P9)

Record `host_drag_cda_envelope_v1.json` (this page restates it). Status **INTERFACE_CONSTRAINT_REGISTERED_PENDING_CUSTOMER_ICD**. Inputs: M2 closure record `docs/milestones/M2_196_state_rfp_closure/m2_closure_record_v1.json` (sha256 `600cf229ecdb...`), DBF-1 intake. Builder: `build_host_drag_cda_envelope.py`.

## Interface constraint (ICD wording)

IR-HOST-DRAG-01. The host spacecraft drag area (C_D A of the host body, arrays and appendages in the flight attitude, excluding the propulsion intake face, evaluated on the host's own surface-accommodation basis) shall not exceed (C_D A)_host,max(s) = (T - D_intake(s)) / q(s) at every required flight state s of the mission envelope, with T = 25 mN (propulsion capability) as the hard statewise limit and T = 12 mN (sustained thrust level) as the design target for continuous drag compensation. Equivalently the host body drag shall not exceed D_host,max(s) = T - D_intake(s). Values are tabulated per state in host_drag_cda_envelope_v1.json; compliance is verified by the spacecraft prime by analysis against the customer spacecraft ICD.

## Governing formula

```text
D_host,max(s, k; T) = T - D_intake(s, k)
(C_D A)_host,max(s, k; T) = (T - D_intake(s, k)) / q(s)
D_intake(s, k) = d_intake(s, k) x A_intake; d_intake = F1 TPMC intake-face drag per unit frontal area (theta 0) of the DBF-1 intake A0.25_Ld20_phi0.9 in admitted surface scenario k; A_intake = 0.25 m^2 (DBF1-IN-02)
q(s) = 1/2 rho(s) v(s)^2 at the admitted orbit-resolved state (abep_mission::intake_drag::EnvelopeAtmospheres: frozen NRLMSIS 2.1 design-state set v2, the required states)
```

- **governing scenario**: unfavourable k (largest D_intake) per state: feasibility in every admitted surface scenario is required (A9.13 S6.16); the favourable value is reported alongside
- **thrust levels**: T = 12 mN (sustained, RVM-02) and 25 mN (capability, RVM-03); the statewise hard constraint T_available - D_spacecraft >= 0 (A9.13 S6.15, HC-08) needs D_host + D_intake <= T_available <= 25 mN
- **no positive host**: D_intake(s, k) >= T: no positive host C_D A keeps T_required <= T at that state
- **lower bound**: none from drag compensation: T_required < 12 mN leaves a positive T - D (orbit-raise / duty-cycle authority for mission operations); C_D A >= 0 only
- **update rule**: DCR-001 (intake / compressor redesign) changes d_intake and A_intake only: rerun M2 on the revised controlled baseline and rebuild with --record; the formula is unchanged

## Governing values (all 196 required states, unfavourable surface scenario)

| thrust level | max host C_D A over the whole envelope [m^2] | governing state | D_host,max there [mN] | states with no positive host C_D A (unfav / every scenario) |
|---|---|---|---|---|
| 12 mN (RVM-02 THRUST_12MN_SUSTAINED) | none (no positive value at 13 states; 0.00196 over the others) | `ds2:ECSS_ST_HIGH:alt195:lat-73.0000:lst15:lon240:doy1` | 0.0445 | 13 / 11 |
| 25 mN (RVM-03 THRUST_25MN_CAPABILITY) | 0.221 | `ds2:ECSS_ST_HIGH:alt180:lat-73.0000:lst15:lon240:doy1` | 7.41 | 0 / 0 |

## By altitude band (worst state / typical = median state / max; unfavourable scenario)

| band | states | C_D A max @25 mN worst / typical / max [m^2] | C_D A max @12 mN worst / typical / max [m^2] | states with no positive C_D A @12 mN | RC-DIAMANT states > 25 mN |
|---|---|---|---|---|---|
| alt180 | 49 | 0.221 / 0.927 / 3.09 | none / 0.173 / 1.21 | 13 | 29 |
| alt195 | 48 | 0.574 / 1.67 / 6.74 | 0.00196 / 0.528 / 2.96 | 0 | 11 |
| alt215 | 49 | 1.2 / 3.33 / 17.7 | 0.301 / 1.32 / 8.22 | 0 | 0 |
| alt230 | 50 | 1.8 / 5.1 / 34.1 | 0.592 / 2.18 / 16.1 | 0 | 0 |

## By altitude and atmosphere scenario (unfavourable surface scenario)

| altitude [km] | atmosphere | states | C_D A max @25 mN worst / typical [m^2] | C_D A max @12 mN worst / typical [m^2] | no positive C_D A @12 mN | RC-DIAMANT > 25 mN |
|---|---|---|---|---|---|---|
| 180 | ECSS_LT_HIGH | 12 | 0.414 / 0.762 | none / 0.0922 | 4 | 11 |
| 180 | ECSS_LT_LOW | 12 | 1.34 / 2.38 | 0.369 / 0.868 | 0 | 0 |
| 180 | ECSS_LT_MODERATE | 12 | 0.838 / 1.26 | 0.13 / 0.334 | 0 | 5 |
| 180 | ECSS_ST_HIGH | 13 | 0.221 / 0.498 | none / 0 | 9 | 13 |
| 195 | ECSS_LT_HIGH | 12 | 0.885 / 1.43 | 0.15 / 0.414 | 0 | 3 |
| 195 | ECSS_LT_LOW | 11 | 2.8 / 4.79 | 1.07 / 2.03 | 0 | 0 |
| 195 | ECSS_LT_MODERATE | 12 | 1.66 / 2.4 | 0.522 / 0.878 | 0 | 0 |
| 195 | ECSS_ST_HIGH | 13 | 0.574 / 0.995 | 0.00196 / 0.205 | 0 | 8 |
| 215 | ECSS_LT_HIGH | 12 | 1.68 / 2.73 | 0.53 / 1.04 | 0 | 0 |
| 215 | ECSS_LT_LOW | 12 | 6.13 / 10.6 | 2.67 / 4.83 | 0 | 0 |
| 215 | ECSS_LT_MODERATE | 12 | 3.25 / 4.65 | 1.28 / 1.96 | 0 | 0 |
| 215 | ECSS_ST_HIGH | 13 | 1.2 / 1.96 | 0.301 / 0.667 | 0 | 0 |
| 230 | ECSS_LT_HIGH | 13 | 2.44 / 3.89 | 0.898 / 1.59 | 0 | 0 |
| 230 | ECSS_LT_LOW | 13 | 10.2 / 17.7 | 4.64 / 8.23 | 0 | 0 |
| 230 | ECSS_LT_MODERATE | 11 | 4.94 / 7.34 | 2.1 / 3.25 | 0 | 0 |
| 230 | ECSS_ST_HIGH | 13 | 1.8 / 2.96 | 0.592 / 1.15 | 0 | 0 |

## Declared reference bodies against the envelope (context; none is the host)

| case | C_D A [m^2] | states with T_required > 25 mN (unfav) | complies at 25 mN in every state |
|---|---|---|---|
| RC-DIAMANT | 1.1 | 40 | no |
| RC-DICARA-ESA | 2 | 80 | no |
| RC-NISHIYAMA | 3 | 117 | no |
| RC-SCHONHERR | 0.66 | 15 | no |
| RC-TISAEV-HIGH | 0.42 | 6 | no |
| RC-TISAEV-LOW | 0.32 | 4 | no |

## Lowest altitude band from which a given host C_D A complies (every state at and above it)

| host C_D A [m^2] | thrust level | ECSS_LT_HIGH | ECSS_LT_LOW | ECSS_LT_MODERATE | ECSS_ST_HIGH |
|---|---|---|---|---|---|
| 0.25 | 12 mN | >= 215 km | >= 180 km | >= 195 km | >= 215 km |
| 0.25 | 25 mN | >= 180 km | >= 180 km | >= 180 km | >= 195 km |
| 0.5 | 12 mN | >= 215 km | >= 195 km | >= 195 km | >= 230 km |
| 0.5 | 25 mN | >= 195 km | >= 180 km | >= 180 km | >= 195 km |
| 1 | 12 mN | no band | >= 195 km | >= 215 km | no band |
| 1 | 25 mN | >= 215 km | >= 180 km | >= 195 km | >= 215 km |
| 1.1 | 12 mN | no band | >= 215 km | >= 215 km | no band |
| 1.1 | 25 mN | >= 215 km | >= 180 km | >= 195 km | >= 215 km |
| 2 | 12 mN | no band | >= 215 km | >= 230 km | no band |
| 2 | 25 mN | >= 230 km | >= 195 km | >= 215 km | no band |

Worst = the smallest allowable C_D A over the band's states ('none' when at least one state has no positive value); typical = the median state (a state with no positive value counts as 0).

## States infeasible for any positive host C_D A

- At 25 mN: 0 states (the DBF-1 intake-face drag is below 25 mN at every state and scenario).
- At 12 mN: 13 states in the unfavourable scenario (11 in every scenario): there the DBF-1 intake face alone needs more than 12 mN, so continuous compensation at the sustained level is not possible for any host; the propulsion system must operate above 12 mN (up to its 25 mN capability) at those states. This is an intake-drag property of DBF-1, carried to DCR-001.

Per-state values (both scenarios, both thrust levels, D_host,max and C_D A max) are in the JSON `per_state` list.

## Not

- not a propulsion redesign: the propulsion envelope (12-25 mN) and DBF-1 are unchanged (A9.38 P9)
- not a host design: RC-DIAMANT (1.1 m^2) stays a REFERENCE_PENDING_CUSTOMER_ICD case
- not a thrust prediction: T_available is not evaluated (HALL_NUMERICS_NOT_CONVERGED); the envelope is drag-side only
