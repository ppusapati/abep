# NP-HALL-PARAMETRIC-ENVELOPE — input audit v1 (A9.32)

`input_audit_v1.json` is authoritative; this page restates it. Base `8a53b13` (integration/simulation-complete), 2026-10-07.
Read-only audit of the inputs the A9.32 HallThruster.jl parametric feasibility envelope for H-1 needs, written before the
preregistration. No Hall run exists for any H-1 case; nothing here is a Hall result.

## Findings

| input | registered? | what exists | consequence for the envelope |
|---|---|---|---|
| H-1 geometry | window only | H1F-CH-02..10 windows (OPEN); design point H1F-CH-11 TBD_AFTER_EVIDENCE; 7 owner-authorised FEMM analysis points (A9.14 F5-OQ-01, analysis points, not a selection) | geometry axis = the 7 analysis points, labelled ANALYSIS_POINT_NOT_DESIGN_SELECTION |
| **H-1 B(z)** | **NO** | H1F-BZ-01 TBD_AFTER_EVIDENCE (no FEMM of MC-1, no measured map); H1F-BZ-02 qualitative shape (peak at or just downstream of z = L, low anode field; OPEN, inferred); H1F-BZ-03 peak band 69.93–268.6 G (OPEN, model-derived, owner-accepted FEMM target band, not a transport optimum); H1F-BZ-04 capability 403 G | only sourced numeric shapes: P5 Peterson 2001 1.6 kW / 3.0 kW (REFERENCE_FOR_P5_ONLY). Either STOP or use a labelled SOURCED_SURROGATE family of those two shapes (rigid, peak at the H-1 exit, scaled to the band ends); its classification effect must be preregistered |
| operating domain | bands | V_d 180–350 V (H2-1; 350 V rating H1F-AN-10); delivered flows 0.377 / 1.287 / 3.2 mg/s (H2-1; H1F-CH-12 owner allocation); P_d 650–1350 W is the A5 allocation, not a limit | V_d and flow axes from these values |
| H-1 Xe flow | NO | XV2-17 / XV2-18 TBD | Xe axis can only reuse the H-1 mass-flow values, labelled XE_FLOW_FROM_H1_ATM_RANGE |
| transport | screening only | credible set EMPTY; sgb-screen-01..09 (ScaledGaussianBohm, all a = 1/16, profile in L units; applicability xenon, P5-like channel, 230–274 V, 5 mg/s); P5-N2 v1 all INCONCLUSIVE | all nine, used as recorded; every H-1 case is TRANSPORT_EXTRAPOLATED; no super-Bohm set |
| chemistry | Xe built-in; N2/N only for air | abep-n2n-0.11 (T_e 2–30 eV, f_out = 0 rule); no Hall O / O2; atomic O 5.0–86.0 % of the inflow over the required states | AIR layer (a) cannot be honest: N2 only as a labelled N2_PROXY diagnostic, not a bound in either direction |
| numerics | P5-N2 only | 200 cells / 0.1 m, dt 5 ns, 2 ms, averaging from 1 ms; H-1 settings and grid-adequacy check (RG-04) open | settings must be a registered rule derived from the P5-N2 settings, labelled NUMERICAL_ADEQUACY_NOT_VERIFIED_FOR_H1 |
| pin | yes | HallThruster.jl 0.23.1 `bfb3019f…`, Julia 1.11.7, bridge_lib.jl | unchanged |
| non-Hall inputs | open | host drag: no ICD; P_bus: ledger PARTIAL_BOUNDARY, 24 TBD terms, lower bound 0 W; delivered flow: no frozen design point; ICP: NP-ICP-NEUTRALIZER RUST_IMPL (not admitted); mass: dry known 38.35 kg, wet 40.35 / 43.35 / 48.35 kg at the 2 / 5 / 10 kg Xe planning cases, DOES_NOT_CLOSE on planning values, INCOMPLETE_EVIDENCE; thermal / life NOT_EVALUATED | each needs a preregistered favorable bound or stays an explicit open condition; planning allocations never make a state PHYSICALLY_NON_CLOSING |
| execution | no | julialang-s3 / pkg.julialang.org return 403 in this container | runs go to a separate environment (workflow_dispatch workflow or a local Julia) |

## Missing for a determinable A9.32 classification

H-1 B(z) (H1F-BZ-01); the H-1 design point (H1F-CH-11); Hall O / O2 chemistry; an admitted Hall member (layer (b) only);
an H-1 Xe flow; H-1 numerical settings and a grid-adequacy check; a delivered-flow record at a frozen design point; a
complete bus ledger; the host-spacecraft drag ICD; an admitted I_e,cap; CBE / measured mass and the frozen Xe load;
thermal and life evaluations.
