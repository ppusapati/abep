# DCR-DBF1-001 — compressor / feed pressure-domain closure v4

PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED. Deterministic (`dcr001_pressure_domain_closure_v4.py` → `.json`, < 1 s).
No Hall simulation, DSMC or optimisation. DBF-1.2 is not built. Supersedes the "finishing pump deleted, 7 stages to 5 Pa"
compressor of v3 (7094ad2): that stack ran turbo blade rows above the repository's 0.1 Pa molecular-regime limit (EV-03).

## 1. Feed pressure (series conductances, air ~300 K, anode-region gas 500 K assumed)
Channel exit conductance (RP-1 annulus 70 × 12 mm, slot transmission 0.30): 0.131 m³/s. Distributor rule p_dist ≥ 3 p_anode
(H1 interface requirement; distributor geometry undefined → required C_dist = 0.039 m³/s). Manifold 40 mm × 0.20 m
(molecular C 0.043 m³/s, a lower bound at Kn 0.03–0.09). Metering valve sized for Δp = p_dist at 0.55 mg/s (50 % opening).

| point | ṁ (mg/s) | p_anode | p_distributor | Δp manifold | Δp valve | plenum min |
|---|---|---|---|---|---|---|
| AIR 12 mN reference | 0.45 | 0.59 Pa | 1.78 Pa | 1.09 Pa | 1.78 Pa | 4.6 Pa |
| AIR 12 mN conservative | 0.55 | 0.72 Pa | 2.17 Pa | 1.33 Pa | 2.17 Pa | 5.7 Pa |
| AIR capability | 1.33 | 1.75 Pa | 5.26 Pa | 3.21 Pa | 2.63 Pa (full open) | 11.1 Pa |

**Selected plenum: 12 Pa (control band 11.1–14 Pa); volume ~4.8 L.** The capability point sets it.

## 2. Compressor by pressure domain (inlet 11.25 m³/s, Clausing W 0.0625, 0.70 m² aperture)
| stage | p_in → p_out (Pa) | PR | Kn (out) | domain | evidence |
|---|---|---|---|---|---|
| F1 front axial, contra-rotating | 0.0051 → 0.0142 | 2.8 | 24 | free molecular | turbomolecular stage theory inside the admitted 0.1 Pa limit; coefficients not measured |
| F2 | 0.0142 → 0.0398 | 2.8 | 14 | free molecular | same |
| F3 | 0.0398 → 0.100 | 2.5 | 9.5 | free molecular | same |
| T finishing-unit turbo rows | 0.1 → 1.0 | 10 | 1.7 | transitional | NOT admitted in the repository model; analog: commercial turbo-drag hybrid pumps (verify) |
| H finishing-unit Holweck | 1.0 → 12 | 12 | 1.9 (gap 0.3 mm) | molecular drag | drag-channel form (EV-02); repository bound Kn ≥ 0.5 met; coefficients uncited |

The finishing unit is retained. It needs ~0.57 m³/s at 0.1 Pa, and a Holweck-only finisher would need a 25 m channel width.
Compressor 8.69 kg (estimate) / **10.42 kg MEV**; power 45 W target / 90 W allowance.

## 3. Component BOM (MEV kg)
The figures are: intake 4.629, compressor 10.424, plenum/feed 1.44, Hall 4.205, ICP 1.583, RF 1.5, PPU 6.0, Xe hardware 3.143,
controls 1.0, structure/thermal 2.5. Non-harness 36.42 + harness 1.92 = nominal dry 38.34; +10 % = 42.18; **+2 kg Xe = 44.18 kg wet
(4.18 kg over 40 kg)**. No hardware is deleted to meet the mass.

## 4. Power
AIR 12 mN bus: 1,166 W reference (26.8 km/s, η_T 0.27, compressor 45 W) / 1,224 W conservative (22 km/s, 0.22, 90 W).
Xe 25 mN Hall discharge-power allocation (compressor off; chain 0.90 × 0.95):

| bus ceiling | nominal ICP | ICP RF +100 W |
|---|---|---|
| 1,500 W (RFP, must be < ) | ≤ 929.8 W | ≤ 819.5 W |
| 1,450 W (preferred design) | **≤ 887.0 W** | **≤ 776.8 W** |

The partial RP-1 Xe A7 runs are supporting evidence only (PARAMETRIC / NOT_VALIDATED).

## Classification
DCR-DBF1-001 NOT READY — compressor mass. The pressure domain needs the turbo-drag finishing stage (0.1 → 12 Pa), which makes
the wet mass 44.2 kg (> 40 kg).
