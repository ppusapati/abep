# ABEP ARCHITECTURE-FREEZE DESIGN SYNTHESIS (A9.7) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat; LaTeX kept as written, including the formula
lines whose minus signs were lost in transmission, e.g. dm_s/dt = mdot_s,compressor - mdot_s,Hall - mdot_s,losses).
Machine-readable companion: `OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json`. Immutable after commit;
later amendments are new addenda.

---

ABEP ARCHITECTURE-FREEZE DESIGN SYNTHESIS

Current protected baseline:

main = 98fbbb9

The next objective is no longer additional framework construction.

The objective is:

[
\boxed{\text{CONVERGE TO A PHYSICALLY DEFINED ABEP REFERENCE ARCHITECTURE}}
]

Computational-language decision

Do not rewrite the simulator in Rust.

Python remains the authoritative:

* system orchestrator;
* evidence and provenance layer;
* validation implementation;
* architecture-gate implementation;
* schema / builder / decision environment.

HallThruster.jl remains the authoritative Hall-discharge solver.

Create an optional Rust native package only for demonstrated computational hotspots.

Suggested structure:

abep_core/

with PyO3/maturin bindings to Python.

No Rust result becomes authoritative merely because it is faster.

For every migrated numerical kernel require:

[
\text{Python reference}
\leftrightarrow
\text{Rust implementation}
]

comparison across frozen golden vectors, edge cases and randomized domain points.

A Rust kernel is admitted only when discrepancies remain inside a preregistered numerical tolerance.

⸻

F0 — Profile before porting

Instrument wall-clock and CPU time for:

* TPMC particle tracing;
* intake response-surface generation;
* compressor search;
* whole-system evaluation;
* UQ Monte Carlo;
* robust design search;
* mission propagation;
* P3 ray/view-factor calculations.

Produce:

PERFORMANCE_BASELINE_98fbbb9.json

Do not port code merely because it contains Python.

Port only measured bottlenecks.

⸻

F1 — Intake geometry synthesis

Extend the current TPMC intake design space.

Search at least the existing physical variables:

[
A,\ d,\ L/d,\ \phi,\ \alpha,\ \theta
]

plus allowable wall/material states already supported by evidence.

For every candidate compute:

[
\eta_c
]

[
C_D
]

[
K_{\rm back}
]

[
CR_{\rm passive}
]

[
m_{\rm intake}
]

[
\dot m_{s,\rm captured}.
]

Evaluate across registered atmospheric species and orbit states.

Do not optimize collection efficiency alone.

Use whole-system objectives including:

* captured flow;
* intake drag;
* passive compression;
* mass;
* off-axis sensitivity;
* surface-state sensitivity;
* compressor burden.

Output a Pareto set rather than one artificially selected optimum.

⸻

F2 — Filter architecture

Introduce an explicit filter-stage interface between intake and compressor.

At this stage unknown physical parameters remain evidence-labelled.

Require the model to carry:

* forward transmission;
* backflow transmission;
* pressure/conductance effect;
* mass;
* contamination/protection function;
* atomic-oxygen/material applicability.

Do not silently use the current placeholder filter values as a flight design.

⸻

F3 — Compressor geometry synthesis

Upgrade DragCompressor.size_for() from a three-variable sizing search to a bounded physical design search.

Candidate variables include:

[
N_{\rm turbo},
A_{\rm turbo},
R_{\rm turbo},
N_{\rm drag},
R_{\rm rotor},
RPM,
h,
w,
L,
\xi
]

where evidence supports ranges.

Carry species individually:

[
O,\ O_2,\ N_2
]

and report outlet composition.

Each design must return:

[
P_{\rm out},\quad
\dot m_{\rm delivered},\quad
x_{s,\rm out},\quad
P_{\rm compressor},\quad
m_{\rm compressor},\quad
T_{\rm compressor}.
]

Reject designs violating rotor stress, convergence or evidence domain.

The optimizer shall expose tradeoffs rather than invent a single optimum.

⸻

F4 — Plenum/feed synthesis

Couple intake and compressor to a transient plenum model.

Solve:

[
\frac{dm_s}{dt}

\dot m_{s,\rm compressor}

\dot m_{s,\rm Hall}

\dot m_{s,\rm losses}.
]

Search plenum volume and feed-control parameters sufficient to maintain the H-1 inlet state.

The final output offered to H-1 is:

[
\boxed{
\dot m_s,\ P,\ T,\ x_s,\ \text{transient quality}
}
]

not merely total mass flow.

⸻

F5 — H-1 design closure

Drive the Hall-head geometry/magnetic work to a defined engineering article.

Freeze candidate:

* channel geometry;
* anode geometry;
* magnetic circuit geometry;
* B(z) target/profile;
* coil operating envelope;
* materials under investigation;
* inlet/plenum interface;
* exit plane IP-EXIT.

Do not use the withdrawn 0-D Hall model as absolute performance evidence.

Continue HallThruster.jl plus measured evidence under existing repository rules.

The design synthesis layer may use Hall response maps only inside their admitted domains.

⸻

F6 — Downstream ICP geometry synthesis

Once P1/P2 evidence exists, search the downstream ICP physical geometry:

[
L_{\rm standoff},
r_{\rm aperture},
r_{\rm module},
L_{\rm module},
\text{antenna geometry},
\text{collector geometry}.
]

Simultaneously evaluate:

* electron-current capacity;
* plume interception;
* RF impedance/matching;
* RF power;
* Hall magnetic-field disturbance;
* view-factor obstruction;
* collector heating;
* module mass.

Never optimize ICP electron current alone.

⸻

F7 — Full coupled architecture optimizer

Build one common design vector:

[
x=
[
x_{\rm intake},
x_{\rm compressor},
x_{\rm plenum},
x_{\rm Hall},
x_{\rm ICP},
x_{\rm RF},
x_{\rm thermal}
].
]

For every admissible vector evaluate:

[
T-D_{\rm spacecraft}
]

[
P_{\rm bus}
]

[
m_{\rm wet}
]

[
Q_{\rm reject}
]

[
I_{e,\rm cap}-I_{d,\max}
]

and life/material indicators.

Hard constraints remain fail-closed.

The design search shall never convert a TBD evidence input into an assumed numerical value merely to obtain an optimum.

⸻

F8 — Robust optimization

For surviving architectures perform UQ over:

* atmosphere;
* intake surface state;
* pointing;
* gas-surface interaction;
* compressor performance;
* feed state;
* Hall response;
* RF efficiency;
* thermal parameters.

Rank or Pareto-filter engineering design candidates, but do not change evidence-gate status through optimisation.

⸻

F9 — Architecture Freeze Candidate

Produce one candidate definition containing:

Upstream

* intake area and geometry;
* filter;
* compressor topology and dimensions;
* plenum;
* valves/feed.

Propulsion

* H-1 geometry;
* magnetic circuit;
* anode approach;
* downstream ICP geometry;
* RF/match architecture;
* collector.

System

* PPU topology;
* power budget;
* mass budget;
* thermal interfaces;
* control/start sequence;
* Xe functionality.

For every parameter record:

VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS

The architecture may become:

FROZEN_REFERENCE_FLIGHT_ARCHITECTURE

only when the architecture-level gates have sufficient evidence.

Until then retain:

INVESTIGATION_HYPOTHESIS.

⸻

Rust acceleration admission order

Benchmark first.

If profiling supports it, preferentially prototype Rust implementations in this order:

1. TPMC particle-tracing kernel;
2. large intake geometry-grid generation;
3. compressor design-space search;
4. Monte-Carlo/full-chain UQ driver;
5. mission propagation;
6. P3 ray/view-factor sampling.

Keep Python wrappers with identical inputs/outputs so every Rust kernel can be switched off and reproduced using the Python reference implementation.

Do not port governance, evidence, RVM, ledgers, builders or HallThruster.jl.
