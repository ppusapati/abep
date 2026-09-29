# bus_power_boundary_v2

P_bus = Σ_i P_load,i / η_i over every installed component. Nothing is defaulted, and `bus_power_boundary_v1` is
unchanged.

| Group | Components |
|---|---|
| common | compressor, atmospheric_flow_control, xe_flow_control, thermal_control, housekeeping |
| rf | rf_source (net RF power at the antenna/coupler feed terminal; generator, matching network, filters and harness are inside η), rf_magnet |
| hall | hall_discharge, hall_magnet, cathode_keeper, cathode_heater (load planes as in v1) |

- `rf_only` = common + rf; `hall_only` = common + hall; `rf_hall_parallel` = the full universe.
- A component of a branch the mode does not enable must be passed as exactly 0 W at η = 1. Any power on it raises:
  there is no hidden consumption.
- A `TBD` load gives status `INCOMPLETE_EVIDENCE`: `P_bus_W` is null and only the known lower bound is reported.
- The conservation residual closes to 1e-12 relative.

**Proposed allocations** (`PROPOSED_ENGINEERING_ALLOCATION`; reported, not gating):

| Group | Allocation |
|---|---|
| total (design) | ≤ 1350 W |
| common_feed | ≤ 300 W |
| rf | ≤ 700 W |
| hall | ≤ 300 W |
| common_controls_thermal | ≈ 50 W |

The hard requirement is the RFP's P_bus < 1500 W, applied strictly. **Owner clarification needed:** whether the
300 W common allocation already includes the 50 W for controls and thermal. v2 books them separately, as the
specification lists them.
