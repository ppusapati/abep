"""Programme-runner layer (A9.22 layer separation, owner directive 2026-10-03; four layers
REQUIREMENTS -> FROZEN CONFIGURATION -> PHYSICS -> ASSESSMENT).

The modules here are orchestration / compatibility code that COMBINES the physics (abep_sim.*, abep_sim.design.*) with
the assessment layer (abep_sim.assessment.*): the legacy merged closure record, the parametric sweep, the
architecture-closure / UQ / comparison runners that attach evaluation-only flags, and the F7/F8 design-synthesis
runners that apply the design-gate assessment. They may import both layers. Physics and design modules never import
this package, except the compatibility edges listed (with their reason) in tests/test_layer_separation_physics.py
PROGRAMME_IMPORT_ALLOWLIST. Every function here is a relocation of pre-existing code: outputs are identical to the
pre-move records (same keys, order and values).

  closure            evaluate (legacy merged record), close_architecture (+ closure constraint flags)
  sweep              the parametric screening sweep and its CLI (``abep-sim`` entry point)
  uq_modular         evaluate_sample / run_uq of the modular-architecture UQ (+ success flag)
  arch_compare       compare_architectures and the ``run`` CLI (+ band / cap flags, constraint robustness)
  design_synthesis   F7/F8 runners: context_pareto, bus_power, evaluate_constraints, evaluate_system,
                     rank_full_system, statewise_T_minus_D, system_pareto, feed_quality
"""
