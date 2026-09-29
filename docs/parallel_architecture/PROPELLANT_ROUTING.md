# Propellant routing

`propellant_router.route` enforces two balances, with no negative terms, no implicit extra propellant and no
post-hoc repair:

- ṁ_atm,in = ṁ_RF,atm + ṁ_Hall,atm + ṁ_atm,unused/loss
- ṁ_Xe,tank = ṁ_RF,Xe + ṁ_Hall,Xe + ṁ_cathode + ṁ_Xe,unused

What each failure produces:
- over-allocation → `INFEASIBLE_FLOW`;
- a stream the mode does not permit → `IllegalModeError`;
- a Hall mode without cathode Xe booked → `IllegalModeError`.

The atmospheric stream is split by mass only. Each branch receives the same composition, pressure and temperature;
there is no implicit species separation. Xe streams are pure Xe, at the supply's pressure and temperature.

**Rarefied-flow regimes (§33).** `flow_regime(Kn)` classifies each region:

| Regime | Kn | Treatment |
|---|---|---|
| FREE_MOLECULAR | ≥ 10 | TPMC applies |
| TRANSITIONAL | 0.01–10 | flagged for DSMC validation |
| CONTINUUM_APPROX | ≤ 0.01 | outside TPMC applicability |

No DSMC correction is applied until sha-pinned external data exist. The thresholds are the conventional boundaries
(Bird 1994); verify.
