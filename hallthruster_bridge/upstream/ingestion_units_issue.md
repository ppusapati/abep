# Draft upstream issue for UM-PEPL/HallThruster.jl (not yet filed)

**Title:** `background_pressure_Torr` is used as Pa for neutral ingestion but as Torr by the pressure-shift anomalous model

**Version:** v0.23.1 (commit `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5`); the same code is on `main` as of 2026-09-25.

**Description.** The field name `Config.background_pressure_Torr` implies Torr, but the value is used in two
inconsistent ways:

1. Neutral ingestion treats it as **pascals**. `background_neutral_density` in `src/utilities/utility_functions.jl`
   computes `m * config.background_pressure_Torr / kB / config.background_temperature_K` with no Torr→Pa conversion.
   The `Config` docstring also says "in Pascals", and the constructor converts unit-carrying input with
   `convert_to_float64(background_pressure_Torr, units(:Pa))`.
2. The pressure-dependent anomalous-transport shift treats it as **Torr**:
   `pressure_shift(model, params.background_pressure_Torr, ...)` in `src/collisions/anomalous.jl`, whose docstrings give
   the pressure scale and midpoint in Torr (default 25e-6 Torr).

A user who passes the facility pressure in Torr, as the name suggests, gets an ingested flow that is 133.3× too small.
A user who passes Pa (or a Unitful Torr quantity, which is converted to Pa) gets a pressure shift evaluated at a pressure
133.3× too high. The two features can't both be right with one value.

**Reproducer:** `ingestion_units_mre.jl` (next to this file). Output on v0.23.1:
```
HallThruster ingestion flow:          3.5728325835114074e-10 kg/s
expected if the value is Torr:        4.763385005012988e-8 kg/s
expected if the value is Pa:          3.572832583511408e-10 kg/s
ratio (Torr interpretation / actual): 133.32236800000004
```

**Suggested fix:** keep the field in Torr (matching its name and the anomalous model) and convert once in
`background_neutral_density` (`P_Pa = background_pressure_Torr * 133.322368`). Convert unit-carrying input with
`units(:Torr)` rather than `units(:Pa)`, and correct the docstring. (Minor: the `background_temperature_K` docstring
says the default is 150 K; the constructor default is 100 K.)

**Context / our workaround:** the ABEP simulator passes the pressure in Torr and sets
`neutral_ingestion_multiplier = 133.322 * A_entrainment / A_channel`. It asserts at run time that the resulting flow
equals Brabston et al. JPP 2025 Eq. (13) (`hallthruster_bridge/run_cases.jl`). Remove the 133.322 factor there when the
pinned version is fixed.
