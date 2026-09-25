"""Physical constants and the DRDO RFP constraint set (DTDF/06/13516)."""
from dataclasses import dataclass, field

G0 = 9.80665          # m/s^2
E_CHARGE = 1.602176634e-19
AMU = 1.66053906660e-27
K_B = 1.380649e-23
MU_EARTH = 3.986004418e14   # m^3/s^2
R_EARTH = 6371.0e3          # m

# Species masses (kg)
M_SPECIES = {
    "O":  16.0 * AMU,
    "N2": 28.0 * AMU,
    "O2": 32.0 * AMU,
    "Xe": 131.3 * AMU,
}


@dataclass(frozen=True)
class RFPConstraints:
    """Hard limits from Part III Para 2 of the RFP."""
    thrust_min_mN: float = 12.0
    thrust_max_mN: float = 25.0
    power_max_W: float = 1500.0
    mass_max_kg: float = 40.0
    alt_min_km: float = 180.0
    alt_max_km: float = 230.0
    ignition_hours: float = 15000.0       # ">15,000 h"
    mission_hours: float = 26000.0        # 3 years
    ic_total_min: float = 0.75
    ic_subsystem_min: dict = field(default_factory=lambda: {
        "thruster": 0.80, "intake": 0.80, "compressor": 0.60, "pse": 0.70})
    hall_preferred: bool = True


RFP = RFPConstraints()
