# Evidence policy for simulator inputs

Published data are **evidence, not ground truth**. A peer-reviewed paper can report an experiment accurately and still
leave uncertainty in geometry, instrumentation, calibration, facility effects, data reduction or interpretation. A model
that is correct in one regime may not transfer to another thruster, magnetic topology, gas, pressure or power. When the
published record can't fix a quantity, say that **the published information is insufficient to reconstruct the experiment
uniquely**. That's different from saying the paper is wrong.

## Evidence hierarchy (highest confidence first)
The evidence level describes only the strength and proximity of the **source**, never what was done to a number.
1. In-house measurement on the actual Vyovrinda hardware and operating condition.
2. Independent measurement on the same or essentially identical hardware.
3. Primary experimental literature on the same or closely similar hardware. Missing geometry, diagnostics, facility
   details, etc. are recorded as limitations; they don't automatically change the level.
4. Validated physics or evaluated-data literature: experimentally benchmarked models, evaluated cross sections, validated
   correlations or simulations applicable to the relevant regime.
5. Indirect published evidence: secondary literature, reviews, compilations, inherited datasets, or results whose
   original primary measurement or model can't be completely inspected or reconstructed.
6. Engineering correlation, or extrapolation outside its directly validated domain.
7. Assumption or hypothesis without direct validating evidence for the present application. Never silently promoted to
   measured data.

**Digitization, unit conversion, interpolation, reconstruction or application of a published correction never changes
the evidence level by itself.** These belong to quantity type, transformation chain and uncertainty.

| question | answered by |
|---|---|
| How strong and proximate is the source? | evidence level |
| What is this number? | quantity type |
| What happened to it before it entered the model? | transformation chain |
| How uncertain is the resulting value? | uncertainty |

So two numbers from the same paper can legitimately be "level 3 / digitized + reconstructed / high uncertainty" and
"level 3 / directly measured / low uncertainty".

## Four attributes of every input
Each simulator input should carry **source + uncertainty + applicability domain + validation status**, together with its
**quantity type**: *measured*, *digitized*, *inferred*, *reconstructed*, *model-derived* or *assumed*, and its
**transformation chain**: instrument reading → the source's own corrections → our extraction/digitization → simulator
input.

**Evidence level and quantity type are orthogonal.** The level characterizes the evidence source and its applicability.
The type characterizes what happened to this particular number. One level-3 paper can contain a measured quantity, a
reconstructed one and an inferred one, so "level 3" never means "measured".

Example: the P5 beam efficiency isn't "beam_efficiency = 0.61". It's:

| attribute | value |
|---|---|
| source | Brabston et al., JPP 2025, Fig. 9 |
| evidence level | 3 (primary experimental literature, closely matching hardware) |
| quantity type | paper-reconstructed (from Faraday/probe data) + digitized (raster) |
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

## Register: current key inputs (living register)
| input | level | type | transformation chain / notes |
|---|---|---|---|
| P5 Xe setpoints: flows, V_d, P_d, peak B, chamber pressure (Brabston Table 4) | 3 | measured | tabulated as reported. Limitation carried in the attributes: 2025 channel depth conflicts across sources (32 vs 38 mm) and coil currents are unpublished |
| P5 raw I_d = P_d/V_d | 3 | inferred (from measured P_d and V_d) | instrument reading → Table 4 → our division |
| P5 vacuum-corrected I_d (Brabston Eq. 14) | 3 | reconstructed | measured I_d → our application of the paper's Eq. 13/14 ingestion correction (A_en = 488 cm², ζ_A = 1) → simulator target |
| P5 corrected thrust Xe1/Xe3 (Brabston abstract) | 3 | reconstructed | stand measurement → paper's Eq. 16 facility correction (ζ_en = 0.8, empirical) → value stated in the abstract |
| P5 corrected thrust Xe2 (Brabston Fig. 5) | 3 | digitized + reconstructed | stand measurement → paper's Eq. 16 correction → plotted in raster Fig. 5 → our digitization (< 0.35 mN; axis residuals < 0.25 mN) → simulator target (±4.9 mN measurement) |
| P5 raw thrust targets | 3 | reconstructed | corrected thrust above → our inversion of Eq. 16 with the paper's ζ_en |
| P5 B(z) shape (Peterson 2001, Figs. 11/12) | 3 | measured → graphically published → vector-extracted | Hall-probe measurement → vector graphic → our path extraction. Extraction is effectively lossless relative to the graphic; converting to physical (z, B) still inherits axis calibration (checked: 25.41/37.99 mm reference lines). Registration to the 2025 thruster is a hypothesis (L38-hist / L32-anode / L32-exit). Historical coil settings only (1.6/3.0 kW) |
| P5 channel depth | 3 | measured, conflicting | 38 mm (Peterson 2001, Hofer 2004) vs 32 mm (Brabston 2025); carried as hypotheses |
| Ψ_b, η_E, Φ_P, component η_T (Brabston Figs. 8/9) | 3 | paper-reconstructed + digitized | internally inconsistent (Fig. 9 vs Fig. 8, 27–38 %); readings A/B carried; facility-condition divergence (CEX broadening) |
| N₂ ionization and elastic tables (Itikawa 2006, via HallThruster.jl) | 4 | evaluated cross sections → model-derived rates | evaluated data → Maxwellian integration (HallThruster.jl) |
| N ionization table (Kim & Desclaux 2002 BEB via NIST) | 4 | model-derived (theory), experimental cross-check | BEB cross section → NIST tabulation → our Maxwellian integration; cross-checked against Brook 1978 (metastable-mix beam) |
| Facility ingestion flow (Brabston Eq. 13) | 6 | engineering correlation | plume-entrainment estimate; enters the 1-D model at the anode (our modelling choice) |
| Anomalous transport (any Bohm-type profile) | 7 | assumed model form | P5 transport not uniquely identifiable; ScaledGaussianBohm region carried as an uncertainty ensemble (a model hypothesis) |
| HallThruster.jl v0.23.1 physics (pinned) | 4 | model | ingestion Torr/Pa inconsistency worked around (`hallthruster_bridge/upstream/`) |

**Future (not yet implemented):** frozen datasets and Hall-map provenance objects should carry these fields
programmatically: `evidence_level`, `quantity_type`, `source`, `uncertainty`, `applicability_domain`, `validation_status`,
`transformation_chain`.
