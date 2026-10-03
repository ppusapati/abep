"""Physical constants and the DRDO RFP constraint set (DTDF/06/13516).

A9.22 layer separation, Phase A: the RFP constraint values are no longer typed here. ``RFPConstraints`` takes them
from the requirements snapshot ``config/requirements/rfp_constraints_v1.json`` (``rfp_constraints_compat``; generated
from the RVM limit fields by scripts/config/build_config.py and sha256-checked against config/MANIFEST.json by
``abep_sim.configuration``; fail closed, no fallback). Values are unchanged, including the legacy 26,000 h
``mission_hours`` (PENDING_GOVERNED_MIGRATION_A9_22_G1; the frozen mission-duration basis 26,280 h is recorded in the
snapshot and in config/mission/mission_scenario_v1.json). The ``RFP`` name is kept for compatibility.
"""
from dataclasses import dataclass, field

try:
    from .configuration import load_rfp_constraints_compat as _load_rfp_constraints_compat
except ImportError:
    # this file is also loaded by path, outside the package (e.g. minexp_numbers.py, scaling_similarity.py): load the
    # sibling configuration module the same way. The values and the fail-closed checks are identical.
    import importlib.util as _ilu
    import os as _os
    import sys as _sys
    _spec = _ilu.spec_from_file_location("_abep_sim_configuration_by_path",
                                         _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "configuration.py"))
    _cfg = _ilu.module_from_spec(_spec)
    _sys.modules.setdefault(_spec.name, _cfg)
    _spec.loader.exec_module(_cfg)
    _load_rfp_constraints_compat = _cfg.load_rfp_constraints_compat

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

_RFP_VALUES = _load_rfp_constraints_compat()


@dataclass(frozen=True)
class RFPConstraints:
    """Hard limits from Part III Para 2 of the RFP (values from config/requirements/rfp_constraints_v1.json)."""
    thrust_min_mN: float = _RFP_VALUES["thrust_min_mN"]
    thrust_max_mN: float = _RFP_VALUES["thrust_max_mN"]
    power_max_W: float = _RFP_VALUES["power_max_W"]
    mass_max_kg: float = _RFP_VALUES["mass_max_kg"]
    alt_min_km: float = _RFP_VALUES["alt_min_km"]
    alt_max_km: float = _RFP_VALUES["alt_max_km"]
    ignition_hours: float = _RFP_VALUES["ignition_hours"]     # ">15,000 h" (SUBSYSTEM_FIRING_LIFE_ASSUMPTION)
    mission_hours: float = _RFP_VALUES["mission_hours"]       # legacy 26,000 h (PENDING_GOVERNED_MIGRATION_A9_22_G1)
    ic_total_min: float = _RFP_VALUES["ic_total_min"]
    ic_subsystem_min: dict = field(default_factory=lambda: dict(_RFP_VALUES["ic_subsystem_min"]))
    hall_preferred: bool = _RFP_VALUES["hall_preferred"]


RFP = RFPConstraints()
