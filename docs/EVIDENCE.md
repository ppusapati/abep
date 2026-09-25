# Evidence policy for simulator inputs

Published data are **evidence, not ground truth**. A peer-reviewed paper can report an experiment accurately and still
leave uncertainty in geometry, instrumentation, calibration, facility effects, data reduction or interpretation. A model
that is correct in one regime may not transfer to another thruster, magnetic topology, gas, pressure or power. When the
published record can't fix a quantity, say that **the published information is insufficient to reconstruct the experiment
uniquely**. That's different from saying the paper is wrong.

## Evidence hierarchy (highest confidence first)
1. In-house hardware measurement on the actual design and operating condition.
2. Independent experimental measurement on the same, or very closely matching, hardware.
3. Experimental literature on similar hardware with complete geometry and operating conditions.
4. Peer-reviewed physics or model literature validated against experiments.
5. Digitized published figures and reconstructed quantities: usable, but their uncertainty must be carried.
6. Engineering correlations, and extrapolation outside the measured domain.
7. Assumptions and hypotheses. Never silently promoted to measured data.

## Four attributes of every input
Each simulator input should carry **source + uncertainty + applicability domain + validation status**, together with its
**quantity type**: *measured*, *digitized*, *inferred*, *reconstructed*, *model-derived* or *assumed*.

Example: the P5 beam efficiency isn't "beam_efficiency = 0.61". It's:

| attribute | value |
|---|---|
| source | Brabston et al., JPP 2025, Fig. 9 |
| quantity type | digitized (raster) experimental quantity; level 5 |
| value | Xe1–Xe3: 0.614 / 0.601 / 0.621 |
| uncertainty | ±0.071 / ±0.075 / ±0.073 (published bars) plus digitization (axis residual ≤ 0.0002). **Reading ambiguity:** Fig. 9 is inconsistent with the paper's Fig. 8, so reading A (f ≈ 0.78) and reading B (f ≈ 0.89–0.91) are both carried |
| applicability | P5, xenon, 5 mg/s, 230–274 V, facility pressure 3.3–4.5×10⁻⁵ Torr (includes CEX broadening) |
| validation status | not independently validated; transfer to flight conditions uncertain |

Models are held to the same standard. "ScaledGaussianBohm with a near-exit transport trough is consistent with important
features of the P5 data within the investigated uncertainty space" is a **model hypothesis**. It isn't "the true transport
model".

## Rules
- Preserve reported values and their provenance exactly. Record any transformation (digitizing, inverting a correction,
  unit conversion) and its uncertainty.
- **Don't tune the simulator merely to force agreement with literature.** When a model and a paper disagree, first check
  geometry, facility, boundary conditions, diagnostics, chemistry and operating regime.
- **Hardware validation supersedes literature-derived assumptions within the hardware's validated operating domain.**
  The experiment being reproduced takes precedence over the reputation of the source.
- Closure path for Vyovrinda hardware: literature → simulation → component experiment → thruster experiment → integrated
  ABEP test → repeated validation. Only the later stages establish that *our* system behaves as predicted.

## Register: current key inputs
| input | level | type | notes |
|---|---|---|---|
| P5 Xe setpoints: flows, V_d, P_d, peak B, chamber pressure (Brabston Table 4) | 3 | measured | tabulated; channel depth conflicts across sources (32 vs 38 mm) |
| P5 corrected thrust Xe1/Xe3 (Brabston abstract) | 3 | measured, then corrected by the paper (Eq. 16) | the correction model is the paper's (ζ_en = 0.8, empirical) |
| P5 corrected thrust Xe2 (Brabston Fig. 5) | 5 | digitized | ±4.9 mN measurement; digitization < 0.35 mN |
| P5 vacuum-corrected I_d (Brabston Eq. 14) | 5 | reconstructed | Eq. 13/14 ingestion model, A_en = 488 cm², ζ_A = 1 |
| P5 B(z) shape (Peterson 2001, Figs. 11/12) | 5 | digitized from vector paths (exact) | historical P5 at 1.6/3.0 kW coil settings; registration to the 2025 thruster is a hypothesis |
| P5 channel depth | 3 | measured, conflicting | 38 mm (Peterson 2001, Hofer 2004) vs 32 mm (Brabston 2025); carried as hypotheses |
| Ψ_b, η_E, Φ_P, component η_T (Brabston Figs. 8/9) | 5 | digitized | internally inconsistent; readings A/B |
| N₂ ionization and elastic tables (Itikawa 2006, via HallThruster.jl) | 4 | evaluated cross sections | |
| N ionization table (Kim & Desclaux 2002 BEB via NIST) | 4 | model-derived (theory) | cross-checked against Brook 1978 (metastable-mix beam) |
| Facility ingestion (Brabston Eq. 13) | 6 | engineering correlation | plume-entrainment estimate; enters the 1-D model at the anode |
| Anomalous transport (any Bohm-type profile) | 7 | assumed model form | P5 transport not uniquely identifiable; ScaledGaussianBohm region carried as an uncertainty ensemble |
| HallThruster.jl v0.23.1 physics (pinned) | 4 | model | ingestion Torr/Pa inconsistency worked around (upstream/) |
