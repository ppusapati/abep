"""A9 spacecraft-DC propulsion bus-power boundary, version 2  (bus_power_boundary_a9_v2).

Owner decision A9.22 item 8 / G8_BUS_BOUNDARY (docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json):
keep ``abep_sim/bus_boundary_a9.py`` (bus_power_boundary_a9_v1) immutable as history and create v2 for the current
flight architecture, ``hall_icp_neutralizer`` only (A9.19: one Hall + one RF/ICP neutralizer). The C1 reference
(``hall_c1_reference``, Hall + heated Xe-fed LaB6 C1) is GROUND_ONLY_LAB_REFERENCE (A9.20). It is not a v2 flight bus
configuration and appears only in ``GROUND_REFERENCE_TEST_METADATA``.

v2 changes the configuration taxonomy and nothing else. The module gets every number, slot, rule and function from v1:

  * Every v1 constant that is not part of the taxonomy is the same object here (the 1500 W gate, the 1 ms window and
    measurement requirements, allocations, SLOTS, PEAK_EVENTS, DEPENDENT_RISES, ICP_GAS_MODES, the evidence classes,
    ``BoundaryA9Error`` ...).
  * Every v1 function (``ledger``, ``rfp_power_gate``, ``p_bus_1ms_max``, ``icp_power_allocation_check``,
    ``allocation_checks``, ``rf_power_planes``, ``check_startup_sequence``, ``installed_slots`` and their helpers)
    runs v1's own code object. The only differences are that the code is bound to this module's globals, and that
    string constants have ``bus_power_boundary_a9_v1`` replaced by ``bus_power_boundary_a9_v2`` (ledger labels and
    error texts). No bytecode instruction differs.
  * The taxonomy is ``CONFIGURATIONS``, ``BASE_SLOTS``, ``VARIANT_OPTIONS``, ``ENFORCED_ORDER`` and
    ``SEQUENCE_TEMPLATES``, restricted to ``hall_icp_neutralizer``, plus ``GROUND_REFERENCE_TEST_METADATA``.
    ``SLOTS`` stays the full v1 slot table, so the C1 slots exist but are never installed in a v2 configuration. A v2
    ``hall_icp_neutralizer`` ledger therefore lists the same items with the same numbers as a v1 ledger;
    only ``boundary_version`` differs (tests/test_bus_boundary_a9_v2.py).

A v2 ledger, start-up check or allocation check refuses ``hall_c1_reference`` (``BoundaryA9Error``: unknown
configuration). A ground-bench C1 ledger is out of scope for v2. The historical v1 module still defines it unchanged.
Its use for C1 bench evidence is an open stage-2 question for the owner, not a v2 feature.

Pure module: standard library only, no physics, no I/O, not wired into ``archengine``. Like v1 it predicts nothing and
has no default load or efficiency.
"""
from __future__ import annotations

import types

from abep_sim import bus_boundary_a9 as _v1

BOUNDARY_VERSION = "bus_power_boundary_a9_v2"
PREDECESSOR_BOUNDARY_VERSION = _v1.BOUNDARY_VERSION          # "bus_power_boundary_a9_v1" (immutable history)
PREDECESSOR_MODULE = "abep_sim/bus_boundary_a9.py"
DECISION = ("docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json G8_BUS_BOUNDARY "
            "(verbatim: docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md item 8)")

FLIGHT_CONFIGURATION = "hall_icp_neutralizer"
GROUND_REFERENCE_CONFIGURATION = "hall_c1_reference"

# ------------------------------------------------------------------------------------------- configuration taxonomy
# The only names whose values differ from v1 (besides BOUNDARY_VERSION and the new metadata names above/below).
TAXONOMY_NAMES = ("CONFIGURATIONS", "BASE_SLOTS", "VARIANT_OPTIONS", "ENFORCED_ORDER", "SEQUENCE_TEMPLATES")
CONFIGURATIONS = (FLIGHT_CONFIGURATION,)
BASE_SLOTS = {FLIGHT_CONFIGURATION: _v1.BASE_SLOTS[FLIGHT_CONFIGURATION]}
VARIANT_OPTIONS = {FLIGHT_CONFIGURATION: _v1.VARIANT_OPTIONS[FLIGHT_CONFIGURATION]}
ENFORCED_ORDER = {FLIGHT_CONFIGURATION: _v1.ENFORCED_ORDER[FLIGHT_CONFIGURATION]}
SEQUENCE_TEMPLATES = {FLIGHT_CONFIGURATION: _v1.SEQUENCE_TEMPLATES[FLIGHT_CONFIGURATION]}

# C1 only as ground-reference / test metadata (A9.20; A9.22 G8). The values are v1's own objects. They are recorded
# so the bench control stays traceable, and they are never a v2 flight bus configuration.
GROUND_REFERENCE_TEST_METADATA = {
    GROUND_REFERENCE_CONFIGURATION: {
        "role": "GROUND_ONLY_LAB_REFERENCE",
        "flight_bus_configuration": False,
        "decisions": ("docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
                      "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
                      DECISION),
        "use": "bench control in the C1-vs-ICP comparison; registers I_d,max,H1,Ar on H-1 independently of the ICP "
               "(A9.20); never flight hardware, never in the flight mass/power/Xe budgets",
        "v2_ledger": "not evaluable with bus_power_boundary_a9_v2 (installed_slots / ledger / check_startup_sequence "
                     "refuse it); bus_power_boundary_a9_v1 still defines it unchanged",
        "base_slots_as_in_v1": _v1.BASE_SLOTS[GROUND_REFERENCE_CONFIGURATION],
        "variant_options_as_in_v1": _v1.VARIANT_OPTIONS[GROUND_REFERENCE_CONFIGURATION],
        "enforced_order_as_in_v1": _v1.ENFORCED_ORDER[GROUND_REFERENCE_CONFIGURATION],
        "sequence_template_as_in_v1": _v1.SEQUENCE_TEMPLATES[GROUND_REFERENCE_CONFIGURATION],
    },
}

# ------------------------------------------------------------------------------- everything else: v1, unchanged
_OWN = {"BOUNDARY_VERSION"} | set(TAXONOMY_NAMES)


def _is_v1_function(obj) -> bool:
    return isinstance(obj, types.FunctionType) and obj.__module__ == _v1.__name__


def _relabel_code(code: types.CodeType) -> types.CodeType:
    """v1 code object with the boundary label in its string constants (incl. nested code) set to the v2 label."""
    consts = []
    for c in code.co_consts:
        if isinstance(c, str):
            c = c.replace(_v1.BOUNDARY_VERSION, BOUNDARY_VERSION)
        elif isinstance(c, types.CodeType):
            c = _relabel_code(c)
        consts.append(c)
    return code.replace(co_consts=tuple(consts))


def _rebind(f: types.FunctionType) -> types.FunctionType:
    g = types.FunctionType(_relabel_code(f.__code__), globals(), f.__name__, f.__defaults__, f.__closure__)
    g.__kwdefaults__ = f.__kwdefaults__
    g.__qualname__ = f.__qualname__
    g.__annotations__ = dict(f.__annotations__)
    g.__module__ = __name__
    return g


INHERITED_NAMES = tuple(sorted(n for n, v in vars(_v1).items()
                               if not (n.startswith("__") and n.endswith("__")) and n not in _OWN
                               and not _is_v1_function(v)))
REBOUND_FUNCTIONS = tuple(sorted(n for n, v in vars(_v1).items() if _is_v1_function(v)))

for _n in INHERITED_NAMES:
    globals()[_n] = getattr(_v1, _n)
for _n in REBOUND_FUNCTIONS:
    globals()[_n] = _rebind(getattr(_v1, _n))
del _n

# ----------------------------------------------------------------------------------------------- self-consistency
if set(BASE_SLOTS) != set(CONFIGURATIONS) or set(VARIANT_OPTIONS) != set(CONFIGURATIONS) \
        or set(ENFORCED_ORDER) != set(CONFIGURATIONS) or set(SEQUENCE_TEMPLATES) != set(CONFIGURATIONS):
    raise RuntimeError(f"{BOUNDARY_VERSION}: taxonomy tables disagree with CONFIGURATIONS")
if set(CONFIGURATIONS) | set(GROUND_REFERENCE_TEST_METADATA) != set(_v1.CONFIGURATIONS) \
        or set(CONFIGURATIONS) & set(GROUND_REFERENCE_TEST_METADATA):
    raise RuntimeError(f"{BOUNDARY_VERSION}: flight + ground-reference configurations must partition the v1 set")
