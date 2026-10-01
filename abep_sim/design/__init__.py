"""A9.7 design-synthesis layer (owner directive OD_2026_10_01_A9_7). New code only: it calls the existing abep_sim
physics modules (intake, intake_tpmc, compressor, reservoir, ...) without modifying them, so golden benchmarks cannot
move. It is not wired into archengine. Every module fails closed: TBD evidence inputs are never replaced by assumed
values, hard constraints refuse, and searches return Pareto sets rather than single optima."""
