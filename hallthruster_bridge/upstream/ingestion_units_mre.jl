# Minimal reproducer for the HallThruster.jl issue drafted in ingestion_units_issue.md.
# julia --project=hallthruster_bridge hallthruster_bridge/upstream/ingestion_units_mre.jl
using HallThruster: HallThruster as het

geom = het.Geometry1D(channel_length=0.025, inner_radius=0.0345, outer_radius=0.05)
thruster = het.Thruster(name="test", geometry=geom, magnetic_field=het.MagneticField("", [0.0, 0.08], [0.01, 0.01]))
P_Torr, T = 3.0e-5, 300.0
config = het.Config(thruster=thruster, domain=(0.0, 0.08), discharge_voltage=300.0,
                    background_pressure_Torr=P_Torr, background_temperature_K=T,
                    propellants=[het.Propellant("Xe", flow_rate_kg_s=5e-6)])

m = het.Xenon.m
flux(P_Pa) = P_Pa / (het.kB * T) * m * sqrt(het.kB * T / (2π * m)) * geom.channel_area   # one-sided Maxwellian mass flux
got = het.params_from_config(config).ingestion_flow_rates[1]
println("HallThruster ingestion flow:          ", got, " kg/s")
println("expected if the value is Torr:        ", flux(P_Torr * 133.322368), " kg/s")
println("expected if the value is Pa:          ", flux(P_Torr), " kg/s")
println("ratio (Torr interpretation / actual): ", flux(P_Torr * 133.322368) / got)
