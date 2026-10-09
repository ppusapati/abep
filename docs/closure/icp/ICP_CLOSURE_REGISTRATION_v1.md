# P4 RF/ICP neutralizer closure: registration v1 (before evaluation)

Human-readable companion of `icp_closure_registration_v1.json`. The JSON governs. Both are frozen by
`icp_closure_registration_lock_v1.json`, which is committed alone before any evaluation.

| item | value |
|---|---|
| item | A9.38 Priority 4: RF/ICP neutralizer closure (closure board P4; DBF1-BD-06) |
| lane | L-ICP-CLOSURE |
| base | `42bb83a` (origin/integration/simulation-complete) |
| model | NP-ICP v2 as implemented (`abep_icp::v2::IcpModelV2::evaluate`, prereg lock `a180ceef…`). No model change. |
| assessment | `abep_assess::closure_icp` (new, additive). Bounds, M_n and the closure state are formed there only (AS-01..AS-05). |

## Inputs registered

| id | NP-ICP input | registration | evidence |
|---|---|---|---|
| RI-01 | IN-08 (CM-ABS) and the coupling basis | P_abs grid 10 / 20 / 50 / 100 / 200 / 500 W. η_p = P_abs / P_net, with P_net = P_fwd − P_refl at RP-CPL. The reference η_p = 0.1 is the Takahashi TK-26 anchor, so the reference P_abs is 0.1 × 500 W = 50 W. η_p = 1 is the physical upper end. | Level 7 assumed (grid). η_p: level 3 inferred (published analog). The P2 impedance map supersedes it. |
| RI-02 | IN-10 | Analysis geometry DBF1-ICP-02-CAPOFF-EC. It uses the A8 DBF-1 surfaces, except that the downstream open end (πR², EXPORT) becomes an ELECTRON_COLLECTOR of the same area. That is the CFG-CAP-OFF capacity sink (P1-IT-36 option A). | Level 7 assumed. No DCR: this is an analysis representation. The flight sink is the Hall plume (CPL-HALL-ON-v1). |
| RI-03 | IN-11 / IN-26 / EQ-11 | The reference is the ion collector (V = 0). V_ec = +V_bias, with the V_bias grid 25 / 50 / 100 / 200 / 350 V. The same grid is the I_e,sat sweep. Both terminals are on ICP_COLLECTOR_BIAS. | DBF1-ICP-04 / -06 (350 V class), P1-IT-17 / -18 / -36. Level 7. |
| RI-04 | IN-15 / DOM-06 | B_ICP,max = 0 T in CFG-CAP-OFF: Hall coils off, no assist magnet. | Level 7 idealization. Geomagnetic and remanent fields are not included. The flight value needs the H-1 far field (P3). |
| RI-05 | IN-17 (H-LIEB) | σ_i(Xe⁺) = 1.0e-18 m² (GK2008 p. 57, "about"). σ_i(N₂⁺) = 9.65e-19 m² and σ_i(N⁺) = 3.55e-19 m² (Phelps 1991 Tables 3 and 1, Q_m at 1 eV). AIR is not registered: O⁺ and O₂⁺ have no read source. | Levels 5 / 4. Form from REF-LIEB15 slides 43–44. |
| RI-06 | IN-12 / IN-05 / T_g | Parametric REGISTERED_PRESSURE with p_ICP grid 0.001 / 0.003 / 0.01 / 0.03 / 0.1 Pa and T_g = 300 K. Compositions: pure Xe; pure N₂ (EM-N2); and the CG-AIR corner vertices (molecular or atomic) at the extreme free-stream O-nuclei fractions χ_O = 0.0794 and 0.8399 of the 196 frozen design states. | Level 7 assumed. Flight FLOW_BALANCE is blocked by DOM-14 / HI-04. |
| RI-07 | IN-16 | The chemistry is read as registered today: AIR and Xe are NOT_REGISTERED (not admitted). EM-N2 uses n2_n.toml (CA-ICP-v1 NOT_RUN). | Registry 074daff9. Not changed. |
| RI-08 | IN-01..03, IN-07 | Modes AIR_PRIMARY, XE_CONTINGENCY, EM-N2 (bench reference only); G-REUSE; CFG-CAP-OFF; CM-ABS; 13.56 MHz. | Owner decisions. |

## Methods

- **M-A.** NP-ICP v2 runs over mode × composition member × P_abs × p_ICP × V_bias. The record keeps the status, the reason
  codes, the flags, the verify items, and I_e,cap per point and as an envelope.
- **M-B.** Necessary-condition bounds, labelled CONSERVATION_BOUND / NOT_A_PERFORMANCE_PREDICTION:
  - B1: I_beam,LB = T (e / 2 m_i,max V_d,max)^½. Here V_d,max = 350 V (DBF1-H1-05), and m_i,max is the heaviest ion: O₂⁺ for AIR, Xe⁺ for Xe.
  - B2: I_e,req,LB = I_beam,LB (CPL-HON-03, and I_d ≥ I_beam).
  - B3: I_e,cap ≤ e P_abs / E_iz,min, from NIST ionization energies (NO 9.2642 eV while SB-NO is open; O₂ 12.0697 eV; Xe 12.1298 eV).
  - B4: the minimum P_abs and η_p.
  - B5: G-REUSE pressure information.
- **M-C.** Published-analog risk indicator, Xe only: P_abs ≈ I_e,req,LB × 230–450 eV per extracted ion (GK2008 sec. 4.5).
  It is never a model result, never a gate, never a DCR trigger.
- **M-D.** HC-05 runs through `abep_assess::neutralization`. The brief's I_e,cap / I_beam is reported only as the necessary
  condition I_e,cap ≥ I_beam,LB. GNG-ICP-01 is echoed: its criteria are pending owner acceptance.

**Closure-state rule** (applied literally, in this order):
1. DCR REQUIRED if conservation fails inside the frozen 500 W envelope.
2. CLOSED if the I_e,cap is validated and HC-05 is MET.
3. FROZEN FOR EM if I_e,cap is converged in both flight modes and meets B2.
4. Otherwise BLOCKED BY SPECIFIC MISSING EVIDENCE, naming the residual codes.

## Source reads and hosts (2026-10-08)

The lawful reads are SR-01..SR-08: CODATA ε₀, ASD, WebBook, atomic weights, GK2008, REF-LIEB15, Phelps 1991 and SRD 107.
Each has a URL, access time and sha256.

The proxy now connects to every probed host. The 03:34 UTC connect_rejected list no longer applies, and NIST, arXiv,
HAL, OSTI, NTRS and doi.org all answer. What remains are publisher refusals or paywalls:
- pubs.aip.org returns 403;
- journals.aps.org returns 403;
- iopscience full texts are paywalled;
- sciencedirect returns 403;
- pubs.acs.org returns 403.

These are licence barriers. They are never bypassed.

## Not changed

- The ICP chemistry registry. A table build alters the codes that the frozen M2 record regenerates byte for byte
  (`m2_dbf1.rs::committed_m2_record_is_the_a8_record_of_today`), so it waits for the coordinator's M2-rerun decision.
- DBF-1, the M2 record, the NP-ICP and NP-ICP-CHEM-AIR preregistrations, and `hallthruster_bridge/`. That includes
  `propellants_air`, which the Hall AIR lane owns.
