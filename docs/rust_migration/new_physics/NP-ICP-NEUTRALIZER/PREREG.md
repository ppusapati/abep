# NP-ICP-NEUTRALIZER preregistration v1

| item | value |
|---|---|
| model id | `NP-ICP-NEUTRALIZER` |
| preregistration / model version | v1 / model_version `1` |
| status | **`PREREGISTERED_NOT_IMPLEMENTED`** |
| method | `NEW_PHYSICS`: preregistered model → Rust → analytic and independent-evidence verification → admission. No synthetic Python reference. |
| target crate | `abep-icp` (migration class `ACTIVE_SELECTED_ARCHITECTURE`; never depends on `abep-groundtest` or `abep-assess`) |
| work package | SC-WP-03 (owner; plan v3.1 element NP-ICP-NEUTRALIZER, `required: true`; step ES-NP-ICP); couples to SC-WP-02, SC-WP-05, SC-WP-06, SC-WP-09, SC-WP-11 |
| lane | A9.29 sec. 13 LANE C |
| registered | 2026-10-05. First drafted on `e5528bd` (first commit `7e1b349`). Aligned to plan v3.1 on the local integration head `35c06e4` (plan merge `a5a59ea`, plan commit `eb78b4a`), before any implementation. |
| machine-readable | `prereg_v1.json` (same folder). If the two disagree, the JSON is authoritative. |
| lock | `prereg_lock_v1.json` (sha256 of both files, frozen at commit) |
| drafted by | agent session for lane C. Not reviewed by the owner. Nothing here is an owner decision. |

**What this is.** The preregistration of a new predictive model of the downstream 13.56 MHz RF/ICP electron source /
neutralizer of `hall_icp_neutralizer`, as required by A9.29 sec. 4 (RM-OQ-12 closed as
`PREDICTIVE_RF_ICP_MODEL_REQUIRED_FOR_SIMULATION_COMPLETE`).

**What this is not.**
- Not an implementation. No code is written before this file is committed (A9.29 sec. 13).
- Not a Hall model. HallThruster.jl stays authoritative for Hall physics.
- Not a plume, ignition, transient, E-mode or spatially resolved model.
- Not a thermal model and not an assessment.
- Not a value. No number here predicts Vyovrinda hardware.

**Change rule.** The lock freezes both files. A later change is a dated addendum in this folder, never an edit. A change
to an equation, input contract, status rule, tolerance or comparison criterion after implementation starts is a v2
preregistration and a new model_version. Clearing a "verify" item is a verification addendum. If the source differs
from the text here, a v2 preregistration comes first.

**Implementation gate.** No implementation before this preregistration is committed (A9.29 sec. 13; plan v3.1
`programme_v3_1.json` new_physics_lifecycle `gate_a9_29`; ES-NP-ICP; minimum_scope `gating`). After this commit, the
verified core may be implemented: `CFG-CAP-OFF`, coupling mode
`CM-ABS`, every status path, the conservation checks and the analytic limiting cases. Each open owner item and each
verify item blocks only the modes or outputs listed against it.

---

## 1. Governing records (sha256 in the JSON)

- A9.29 (`OD_2026_10_05_A9_29_*`): sec. 4 minimum scope (traced in §23), sec. 13 lane C, sec. 14 speed rule, sec. 15
  full selected architecture.
- A9.28 (`OD_2026_10_05_A9_28_*`): NEW_PHYSICS method (msg 1 sec. 5; msg 2 secs. 9, 10). `plasma_chem.py` is
  `HISTORICAL_LEGACY_MODULE` (msg 1 sec. 3). Fail-closed statuses (msg 2 sec. 14).
- A9 (`OD_HARDWARE_PIVOT_2026_09_29_A9_*`): downstream ICP topology; evidence order Ar → N2 → O2-bearing
  (`NO_ATOMIC_O`) → separate atomic-O programme; Takahashi 2024 anchor.
- A9.19 / A9.20: one Hall + one RF/ICP neutralizer for air and Xe; no conventional hollow cathode; C1 ground-only.
- A9.1 HIQ-06 (G-REUSE, dedicated ICP flow 0), UBQ-02/03/04/07; A9.4 P1Q-10 and A9.5 P1Q-16 (I_e,cap measurand);
  A9.14 S7.8 F6-OQ-03; A9.22 G8 (`bus_power_boundary_a9_v2`); A9.24 item 5 (HC-05 assessment-only); A9.25 secs. 10-11.
- CLAUDE.md rules 3, 4, 6, 10 and the A9 section; `docs/EVIDENCE.md`.
- `config/architecture/hall_icp_neutralizer_v1.json`, `config/assessment/gate_thresholds_v1.json`,
  `docs/audits/a9_24_cathode_path_audit_v1.md`.
- Plan v3.1 (`eb78b4a`, merged into integration/simulation-complete at `a5a59ea`; sha256 in the JSON):
  - `simulation_completion_programme_v1_1.json`: SC-WP-03 element NP-ICP-NEUTRALIZER (`NEW_PHYSICS`, `required: true`)
    with its `minimum_scope`; SC-WP-03 fail-closed gates [8..11] and admission criteria [5..7]; ES-NP-ICP (lane C);
    RM-OQ-12 closed as `PREDICTIVE_RF_ICP_MODEL_REQUIRED_FOR_SIMULATION_COMPLETE`.
  - `programme_v3_1.json`: `np_icp_neutralizer` (same minimum scope), rules RM-R34 and RM-R31, new-physics lifecycle.
  - `SIMULATION_COMPLETION_PROGRAMME.md` (v1.1).
  - Plan v3 (`1236f91`) is kept only as superseded evidence (CONF-04).
- Consumer of IF-ICP-THERMAL-v1: NP-THERMAL-CATHODELESS v1 as merged (`lane-np-thermal-prereg` `fa10c76`, merge
  `35c06e4`; lock: `prereg_v1.json` `e3e6859c…`, `PREREG.md` `e3337c8f…`; full hashes in the JSON). Its first lock was
  `c093ff2`; `fa10c76` changed only its gate and plan references, not the IF-ICP-THERMAL-v1 keys. §11 aligns with it.
- CLAUDE.md is re-pinned at this alignment (`30afe1d` changed rules 2 and 9 only).

Evidence records used (sha256 in the JSON): the ICP neutralizer evidence extraction (Takahashi 2024 TK-xx, survey
S-01..S-08, lawful-acquisition list LA-01..LA-09), the cathode evidence dossier (Schwertheim 2025), P1 bench, P2
impedance prep and map schema, P3 coupled thermal v2, validation inputs, uncertainty budget, prereg framework, F6 ICP
geometry, the ICP ICD, the A9.21 hardware programme, both bus boundaries, the propellant tables and `rate_validity.toml`,
the N2 completeness rule, the empty transport ensemble and the O/O2 v0 records.

## 2. Scope and model class

**Question.** Given the delivered feed state, the RF electrical input, the registered ICP geometry and electrodes and
the thermal boundary:
- which steady plasma state does the ICP reach;
- how much electron current can it deliver to a registered electron sink;
- where does its input power go;
- what does it draw from the bus and the feed?

Every quantity carries an explicit status where evidence is missing.

**Model class.** A steady-state, volume-averaged (global, 0-D) inductive discharge model:
- species particle balances;
- one electron energy balance with Maxwellian electrons;
- Bohm-flux surface losses with registered edge-to-centre factors;
- an explicit electrode current balance for electron extraction;
- an RF coupling representation in three declared modes (§5).

## 3. Exclusions

| id | rule |
|---|---|
| EX-01 | No wholesale port of `plasma_chem.py`. Nothing is taken from it: not the Arrhenius `RATES`, not the `EPS_C` fits, not `E_DISS`, not the `Chamber` default h_l = 0.4, not `magnetised_wall_factor`, not `solve_global`. Shared kernels come from the primary sources below. The rate integral comes from the separately admitted abep-chem port of `rate_tables.maxwellian_rate`. |
| EX-02 | No LaB6, hollow-cathode, thermionic-emitter, keeper or emitter-heater element. Forbidden identifiers in abep-icp: `LaB6`, `hollow_cathode`, `keeper`, `heater`, `c1_`. |
| EX-03 | No ECR, no upstream pre-ionizer, no legacy stage-1 topology. The historical interstage lane is used only as a registry of already-cited sources. No code, closure or topology is inherited. |
| EX-04 | No archengine `rf_cathode` / `mw_air` card and no golden_v1/v2 neutralizer value. |
| EX-05 | No threshold, HC-05 PASS/FAIL, GNG-ICP-01 verdict, RVM status or RFP label in raw output. No RFP parsing. No dependency on abep-assess. |
| EX-06 | C1 is not modelled. C1-based evidence enters only as a registered measured I_d,max,H1 on the Hall side of IF-ICP-HALL-v1. |
| EX-07 | No dependency on `GROUND_TEST_PROGRAMME_ONLY` code. Bench records enter as sha256-pinned data files. |
| EX-08 | No invented coupling efficiency, impedance, extraction efficiency, stable region, h factor, wall coefficient, cross section, conductance, efficiency or temperature. |
| EX-09 | No Ar result transferred to N2, air or flight evidence (A9.25 sec. 10). |
| EX-10 | No Hall transport closure; screening candidates never enter. |
| EX-11 | No F6 geometry-search use before validation on built geometries (A9.14 F6-OQ-03). |
| EX-12 | v1 does not represent Hall-beam ions crossing the ICP, their charge exchange or their collection on ICP surfaces. |

## 4. Operating modes and configurations

**Flight modes.**
- `AIR_PRIMARY`: atmospheric species delivered by the upstream chain from the registered environment. Today
  `INCOMPLETE_EVIDENCE` (O/O2 chemistry unpromoted; delivered O/O2 split TBD).
- `XE_CONTINGENCY`: Xe through the Hall path (G-REUSE) or a declared G-XE feed. Today `INCOMPLETE_EVIDENCE` (no Xe
  rate set).

**Ground evidence / validation modes** (never flight evidence by themselves):
- `EM-AR`: `AR_ENGINEERING_ONLY`. Ar domain only. No Ar rate set yet.
- `EM-N2`: pure N2 surrogate (ICP-45N). Chemistry exists within its limits.
- `EM-O2B`: N2 + O2, labelled `NO_ATOMIC_O`. O2 tables unpromoted; negative ions not represented.
- `EM-XE`: ground Xe campaign (ICP-XE-MODE). No Xe rate set yet.

Each mode is a separate domain with its own registered operating domain, gas mode, pressure-match rule, calibration
basis, stable-region criteria and uncertainty (A9.25 sec. 10). Results never transfer between modes.

**Configurations.**
- `CFG-CAP-OFF`: the owner's I_e,cap measurand (A9.4 P1Q-10, A9.5 P1Q-16, P1-IT-38, P1-S7).
  - Hall discharge OFF and disconnected; anode floating.
  - Gas through the H-1 gas path (G-REUSE) or a registered dedicated feed.
  - Magnet state of the registered H-1 point.
  - Electrons extracted to a dedicated, registered electron collector.
  - Ion-collecting electrode at a registered bias against a registered reference.
  - Evaluable without a Hall closure.
- `CFG-FLIGHT-HALL-ON`: flight operation with the Hall discharge on. Its inlet state (neutral flux after Hall
  ionization, beam ions, plume / anode potential as the electron sink) needs an admitted HallThruster.jl member.
  Today `NOT_EVALUATED` (credible set EMPTY). It exists in the contract and is asserted in tests, never skipped.

## 5. Coupling modes

| id | name | definition | use |
|---|---|---|---|
| CM-ABS | ABSORBED_POWER_INPUT | P_abs is the input. No impedance, coupling efficiency, forward power or bus draw is claimed; those outputs are `NOT_EVALUATED`. | analytic verification; validation against bench points with measured P_abs (VI-RF-05); parametric studies labelled `PARAMETRIC_ABSORBED_POWER` |
| CM-CAL | CALIBRATED | R_p and R_ant come from registered P2 impedance evidence at the operating point (EQ-13). Provenance: map id and content_sha256, record ids, method ZM-A / ZM-B, uncertainty status. Domain: inside the map, `H_MODE`. | points inside a measured coupling domain |
| CM-PRED | PREDICTIVE (uncalibrated) | Transformer-type model from registered coil and plasma geometry and the computed plasma conductivity (EQ-14). R_ant from the measured cold value, or as a lower bound only from a conductor-loss model. Outputs labelled `UNCALIBRATED_PREDICTIVE`. | points with no P2 evidence; blocked until VER-03, VER-04, VER-05, VER-13 are cleared |

## 6. Inputs

Every input carries source, evidence level, quantity type, transformation chain, uncertainty, applicability domain and
validation status (`docs/EVIDENCE.md`). A record missing any attribute is refused (IN-22).

| id | input | symbol / unit | producer | status today |
|---|---|---|---|---|
| IN-01 | supply / evidence mode | `AIR_PRIMARY`, `XE_CONTINGENCY`, `EM-*` | architecture config; bench registration | REGISTERED |
| IN-02 | ICP gas mode | G-REUSE (primary, dedicated flow 0), G-ATM / G-XE (variants) | architecture config; ICD ICP-26; A9.1 HIQ-06 | REGISTERED |
| IN-03 | configuration | `CFG-CAP-OFF`, `CFG-FLIGHT-HALL-ON` | case registration | REGISTERED |
| IN-04 | delivered feed state | ṁ_s [kg/s], P_feed [Pa], T_feed [K], x_s [-] | flight: abep-gaspath plenum/feed per design state; bench: MFC / gauges (VI-GAS-07) | flight NOT_EVALUATED (upstream Rust chain not admitted); bench no records |
| IN-05 | atmospheric species and delivered composition | {s}, x_s | registered environment via the upstream chain | INCOMPLETE_EVIDENCE (delivered O/O2 split TBD; O/O2 chemistry unpromoted) |
| IN-06 | Xe contingency feed | ṁ_Xe [kg/s] | Xe path (G-REUSE) or G-XE flow (Xe ledger, PHASE_TOTAL_FLOW) | INCOMPLETE_EVIDENCE (no Xe rate set) |
| IN-07 | RF frequency | f_RF [Hz] | owner (VI-RF-01) | REGISTERED: 13.56 MHz |
| IN-08 | RF electrical input | P_abs (CM-ABS) or P_fwd, P_refl, P_line/match,loss [W] at RP-CPL | setpoint / design variable; P1/P2 records | flight setpoints TBD; ratings TBD_AFTER_IMPEDANCE_MAP |
| IN-09 | coupling evidence | CM-CAL: P2 map points; CM-PRED: N_ant, r_ant, L_ant, d_ant, R_ant,cold [-, m, ohm] | P2 map; F6-X-06..09; CAL-P2-08 | NOT_EVALUATED (no P2 data; antenna TBD) |
| IN-10 | geometry and effective volume | R, L [m], V [m³], surfaces {A_j [m²], type (floating dielectric / floating conductor / biased ion collector / electron collector / open end), material, thermal_node (N_VESSEL, N_ANTENNA, N_MOUNT, N_COLLECTOR, N_HOUSING, EXPORT, H-1 faces)} | F6-X-01..05, 10..17; ICD ICP-07/21/47; or a registered bench / analog geometry | INCOMPLETE_EVIDENCE (all F6 geometry TBD) |
| IN-11 | electrode registration | A_ic, V_ic; A_ec, V_ec; reference [m², V] | P1-IT-36 at P1-G0; ICD ICP-21 | NOT_EVALUATED |
| IN-12 | pressure / neutral density | REGISTERED_PRESSURE: p_ICP [Pa], T_g [K]; FLOW_BALANCE: f_in or C_HE-ICP, τ_open | VI-GAS-03 tap (ICD ICP-27); VI-GAS-04 or a cited free-molecular transmission | INCOMPLETE_EVIDENCE |
| IN-13 | background neutral source | p_b, T_b (bench); n_amb, exposure (flight) | VI-GAS-05; environment state | bench no records; flight exposure TBD |
| IN-14 | thermal boundary inputs | T_wall,j, T_g, T_coil [K] | NP-THERMAL-CATHODELESS (flight); P1-M-21 (bench) | NOT_EVALUATED |
| IN-15 | magnetic field in the ICP volume | B_ICP,max [T] | VI-HD-06; F6-IF-N02 | TBD_AFTER_EVIDENCE |
| IN-16 | chemistry set | reaction list, sources, validity entries | `hallthruster_bridge/propellants` | N2/N REGISTERED; O/O2, Xe, Ar INCOMPLETE_EVIDENCE |
| IN-17 | ion-neutral cross sections or explicit h | σ_i [m²] or h_j [-] | sourced data | INCOMPLETE_EVIDENCE (none registered) |
| IN-18 | wall recombination / quenching | γ [-] | sourced data; unsourced → [0, 1] two-point envelope | TBD (envelope only) |
| IN-19 | RF chain and bias-supply efficiencies, match actuator draw, match location | η_RF = P_net / P_RF,DC, η_bias [-], P_match,DC [W], `match_colocated` (ICD ICP-13) | flight-representative component evidence (VI-RF-08/09) | PENDING |
| IN-20 | Hall discharge-current demand | I_d,max,H1 [A] | admitted HallThruster.jl member, or measured registration P1-IT-07 | NOT_EVALUATED |
| IN-21 | Hall-ON exhaust at the ICP inlet | fluxes, energies, plume potential | admitted HallThruster.jl member | NOT_EVALUATED |
| IN-22 | per-input evidence registration | four attributes + quantity type | every input record | rule |
| IN-23 | energy disposition of inelastic channels | RADIATED / WALL_QUENCHED / CARRIED_OUT / UNRESOLVED | sourced per state (VER-11) | UNRESOLVED (bounding pair) |
| IN-24 | numerical settings | tolerances, iteration limits, root-scan grid | this preregistration | REGISTERED |

Uncertainty representations are listed per input in the JSON. Manufacturer ± bounds are rectangular (A9.1 UBQ-03).

## 7. State and equations

State: T_e [eV] (Maxwellian), bulk n_e [m⁻³] with edge densities h_j n_e, ion densities n_i,s, neutral densities
n_g,k, plasma potential φ_p [V] against the registered reference.

| id | equation | source |
|---|---|---|
| EQ-01 | n_g,k = x_k p_ICP / (k_B T_g) | ideal-gas definition |
| EQ-02 | neutral balance: feed + background inflow + volume production + wall return of ions = effusion ¼ n v̄ A τ through open ends + wall atom recombination; v̄ = (8 k_B T_g / π M)^½ | Chiggiato 2014 Eqs. 3, 13, 19-21, sec. 2.1, Table 7 (registered); Santeler τ via Chiggiato Eq. 21 |
| EQ-03 | ion balance V Σ_r ν_r,s R_r = Σ_j Γ_i,s,j A_j; n_e = Σ Z_s n_i,s (no negative ions) | Lieberman 2015 slides 41, 44 (registered); textbook structure verify (VER-01) |
| EQ-04 | u_B,s = (Z_s e T_e / M_s)^½ | slide 41 for Z = 1 (registered); Z > 1 verify (VER-08) |
| EQ-05 | H-LIEB: h_R = 0.8 (4 + R/λ_i)^-½, h_L = 0.86 (3 + L/(2 λ_i))^-½, λ_i = 1/(n_g σ_i); or H-EXPLICIT sourced h_j; no default | slides 38, 43, 44 (registered in `abep_sim/interstage.py` and `INTERSTAGE_MODEL.md` sec. 7); domain B = 0, p < 100 mTorr (argon statement; other gases evidence level 6) |
| EQ-06 | k_r(T_e) = Maxwellian ⟨σ v⟩ from the registered source representation (same data as the `.dat` table) | `PROVENANCE.md` per table; `rate_tables.maxwellian_rate` via abep-chem |
| EQ-07 | P_abs = V e n_e [Σ_r n_t,r k_r E_r + Σ_k n_k k_m,k (3 m_e/M_k)(T_e − T_g)] + Σ_j e A_j [Γ_e,j (2 T_e + max(0, φ_p − V_j)) + Γ_i,j T_e/2] | 2 T_e: slide 50, Goebel & Katz Eqs. 7.3-47 / 7.3-61; T_e/2: slide 48, Goebel & Katz Eq. 4.2-10 (registered); barrier term model-derived; elastic factor verify (VER-02) |
| EQ-08 | floating sheath: Σ Z_s h n_i,s u_B,s = ¼ h n_e v̄_e exp(−V_s/T_e); single species V_s = (T_e/2) ln(M / 2π m_e) | slide 48 (registered) |
| EQ-09 | electrode fluxes: ions h n u_B to surfaces below φ_p; electrons ¼ h n v̄_e exp(−(φ_p − V_j)/T_e) below φ_p, saturated ¼ h n v̄_e above (ions repelled) | slide 48 (registered); electron-saturation regime verify (VER-06, Baalrud et al. 2007) |
| EQ-10 | Σ_j I_j = 0; every floating surface I_j = 0; open ends zero net current (assumption) | charge conservation; owner sign convention applied in the comparison adapter |
| EQ-11 | I_e_cap_A = e A_ec (Γ_e,ec − Σ Z Γ_i,ec) at the registered bias, signed, never clipped. Bounds: ≤ ¼ e h n_e v̄_e A_ec; ≤ ion-collection limit; ≤ I_production = e V Σ R_iz. I_e_sat_A = maximum over the registered bias range. | owner measurand A9.4 P1Q-10 / A9.5 P1Q-16 / P1-IT-38; bounds model-derived |
| EQ-12 | P_delivered = P_fwd − P_refl − P_line/match,loss; P_delivered = I_ant² (R_ant + R_p); η_p = R_p / (R_p + R_ant); P_abs = η_p P_delivered; Q_coil_ohmic = I_ant² R_ant | A9.2 (P2 record); Takahashi 2024 Eq. (1), TK-24..TK-26 (registered) |
| EQ-13 | CM-CAL: R_p = Re Z_ant,hot − R_ant,cold, X = Im Z_ant,hot from the P2 map; P2 interpolation rule only | P2 framework ZM-A / ZM-B / ZM-C |
| EQ-14 | CM-PRED: plasma as a one-turn transformer secondary; σ_p = e² n_e / (m_e (ν_m + jω)); R_s = ω² L_12² R_2 / (R_2² + ω² L_2²), X_s = ω L_11 − ω³ L_12² L_2 / (R_2² + ω² L_2²); all equilibria of P_abs(n_e) = P_loss(n_e) plus the n_e = 0 branch, slope-classified | Piejak, Godyak & Alexandrovich 1992; Lieberman & Lichtenberg 2005 ch. 12 — all detail **verify** (VER-03..05); not admissible before those are cleared |
| EQ-15 | P_RF,DC = (P_fwd − P_refl)/η_RF; P_bias,DC = V_bias I_bias / η_bias; P_icp_bus_W = sum of installed ICP slots | VI-RF-09 definition; `bus_power_boundary_a9_v2` slots |
| EQ-16 | RF chain: P_fwd = P_refl + Q_line + Q_match + Q_coil_ohmic + P_abs. RF-powered plasma: P_abs = Q_plasma_wall + Q_extraction + Q_radiation + Q_outflow_upstream + Q_outflow_downstream (surface terms L_j). Bias supply: P_collector_bias = −Σ I_j V_j = Σ C_j = Q_bias_collector + Q_bias_export, C_j = I_j (φ_p − V_j). Per surface Q_j = L_j + C_j exactly. No term is a remainder. | energy conservation (rule 4); per-particle energies EQ-07; attribution convention model-derived (§11) |
| EQ-17 | G-REUSE: ṁ_icp_dedicated = 0 exactly (owner rule); G-ATM / G-XE: registered flow echoed; conversion dṁ_s = M_s V Σ ν R | A9.1 HIQ-06; ICD ICP-26 |
| EQ-18 | formation energy referenced to ground-state neutrals; released where species recombine or carried out | registered thresholds; wall neutralization term verify (VER-12) |

Notes:
- Rates are evaluated by the direct Maxwellian integral because the registered `.dat` tables use a 1 eV mean-energy
  grid and threshold rates are steep at ICP-class energies (for example `ionization_N2_song2023.dat` gives
  6.4e-20 m³/s at 2 eV and 4.4e-18 m³/s at 3 eV). The `.dat` interpolation is a reported cross-check (UQ-06).
- R_ant is the whole non-plasma antenna-circuit resistance. It includes induced losses in nearby conductors (Takahashi
  TK-27: most RF power heated the ion-collecting electrode).
- R_ant and the power must refer to the same plane, registered per case and never mixed.
  - RP-ANT convention (required for IF-ICP-THERMAL-v1): R_ant = P_delivered / I_ant² without plasma; P_abs = η_p
    P_delivered.
  - R_vac convention (P2 note RF-TAKA22-03; VI-RF-05/06): R_ant = P_net / I_ant² lumps line and match loss into R_ant;
    P_abs = η_p P_net. Such a case emits `Q_icp_line_W` and `Q_icp_match_W` as `NOT_EVALUATED` (flag `LUMPED_R_VAC`).
- No extraction efficiency appears. Extraction follows from the registered electrode areas, potentials and EQ-10.
- Facility background electron current is not modelled. The model quantity corresponds to the RF-OFF-corrected
  measurand I_e,collector,RFON − I_e,collector,RFOFF.

## 8. Chemistry

**Validity semantics** mirror `chemistry_trustworthy`.
- Every rate file used needs a `rate_validity.toml` entry. A missing entry is `MODEL_ERROR`, never a default.
- In a 0-D model a reaction's activity is wholly inside or wholly beyond its limit. Any active reaction with
  3/2 T_e above its `max_mean_energy_eV` makes the result `OUT_OF_DOMAIN`. Nothing is extrapolated silently.
- An `unresolved` file makes the result `INCOMPLETE_EVIDENCE`.
- Table validity is not completeness.

**Reused tables** (abep-n2n-0.11; limits from `rate_validity.toml`):

| tables | process | limit (mean energy) |
|---|---|---|
| `elastic_N2_song2023` | N2 momentum transfer | 255 eV |
| `ionization_N2_song2023` | N2 → N2⁺ | 255 eV |
| `dissociative_ionization_N2_upper` / `_lower` | N2 → N⁺ + N | 255 eV |
| `dissociative_ionization_N2_to_N_Z2plus` | N2 → N²⁺ + N | 255 eV |
| `dissociation_N2` | N2 → N + N | 45 eV |
| 8 electronic states (+ Johnson-low variants) | N2 excitation | 45 eV |
| `excitation_N2_vib_0_to_1..10` | N2 vibrational | 45 eV |
| `excitation_N2_rot_j0_to_j2` / `_j4` | N2 rotational | 45 eV |
| `ionization_N` | N → N⁺ | 255 eV |
| `ionization_N_Z1plus_to_N_Z2plus` | N⁺ → N²⁺ | 255 eV |
| `ionization_N_to_N_Z2plus_hms2017` (+ ×0.5, ×1.3) | N → N²⁺ | 255 eV |
| `elastic_N_ragimkhanov2026` / `elastic_N_wang2014_bsr` | N momentum transfer | 255 eV |
| N2 dication tables | variant only | 255 eV |

Never used: the HallThruster.jl-shipped `ionization_N2_N2+.dat` and `elastic_N2.dat` (unresolved), and every
`plasma_chem.py` rate or constant.

**Completeness domain.** The N2/N set is `COMPLETE_FOR_P5_N2_VALIDATION` for T_e 2-30 eV (vibrational / rotational
0.2-30 eV) under the frozen rule F_P > 0.01 OR F_ion > 0.01 OR F_S_s > 0.05. That verdict was made for Hall
conditions. It does not transfer to ICP conditions by itself. T_e < 2 eV is `OUT_OF_DOMAIN`. The ICP-domain audit is
OQ-NPICP-04.

**Process-class gate.** For every species, each process class is modelled with a registered source or excluded with a
written justification. An unaddressed class gives `INCOMPLETE_EVIDENCE`. Classes: ionization, excitation (electronic,
vibrational, rotational), dissociation, dissociative ionization, elastic loss, ion-neutral momentum transfer / charge
exchange, wall atom recombination, metastable wall quenching, volume recombination, attachment / negative ions.

**Gaps (`INCOMPLETE_EVIDENCE`) and what would close them.**

| id | gap | closing source | blocks |
|---|---|---|---|
| CHG-01 | atomic O: momentum transfer and excitation not built; ionization only as v0 DRAFT | BSR-1116 (Tayal & Zatsarinny 2016) supplements; Laher & Gilmore 1990; owner promotion as `abep-oo2-0.x` | AIR_PRIMARY, EM-O2B |
| CHG-02 | O2: v0 DRAFT tables unpromoted; dissociation double counting below 13.5 eV; excitation above 20 eV | SONG2026 version of record; owner OD-4, OD-6 | AIR_PRIMARY, EM-O2B |
| CHG-03 | negative ions (O⁻) not represented | sourced attachment / detachment / mutual-neutralization set and a v2 preregistration | any O2-bearing case |
| CHG-04 | Xe: no electron-impact set, no Xe⁺/Xe data | candidates (verify): Rejoub et al. 2002; Hayashi 1983; Miller et al. 2002; LXCat excluded by precedent | XE_CONTINGENCY, EM-XE |
| CHG-05 | Ar: no electron-impact set, no Ar⁺/Ar data | candidates (verify): Rapp & Englander-Golden 1965 or Straub et al. 1995; Phelps 1994 | EM-AR |
| CHG-06 | ion-neutral cross sections for h factors | candidates (verify): Phelps 1991, Phelps 1994, Miller et al. 2002 | H-LIEB for every gas |
| CHG-07 | wall recombination / quenching on the ICP wall materials (dielectric OPEN) | sourced coefficients; until then the [0, 1] envelope | point values of atom fractions and wall heat |
| CHG-08 | radiative vs metastable disposition per state | sourced lifetimes / quenching (VER-11) | point split radiation / wall heat |
| CHG-09 | atomic N electronic excitation not registered | a sourced set or an audit exclusion (OQ-NPICP-04) | CONVERGED N2 cases once N fractions are material |

## 9. Domain checks

| id | check | on failure |
|---|---|---|
| DOM-01 | 3/2 T_e ≤ table limit for every active reaction | OUT_OF_DOMAIN |
| DOM-02 | N2/N: 2 ≤ T_e ≤ 30 eV (vib/rot from 0.2 eV) | OUT_OF_DOMAIN |
| DOM-03 | no unresolved file; no file without an entry | INCOMPLETE_EVIDENCE / MODEL_ERROR |
| DOM-04 | FLOW_BALANCE: Kn > 0.5 on the converged state | OUT_OF_DOMAIN |
| DOM-05 | H-LIEB: B = 0, p < 100 mTorr | OUT_OF_DOMAIN |
| DOM-06 | magnetization: B_ICP,max registered; ω_ce/ν_m and r_ce/R reported | absent → INCOMPLETE_EVIDENCE; registered 0 → in domain; other values → INCOMPLETE_EVIDENCE until OQ-NPICP-03 |
| DOM-07 | Debye length and sheath width vs plasma size reported | criterion OPEN (OQ-NPICP-09) |
| DOM-08 | H-mode coupling (CM-CAL needs `H_MODE`; CM-PRED reports equilibria only) | OUT_OF_DOMAIN |
| DOM-09 | CM-CAL point inside the P2 map domain | OUT_OF_DOMAIN |
| DOM-10 | CM-PRED geometry inside the transformer model's assumptions | OUT_OF_DOMAIN |
| DOM-11 | f_RF = 13.56 MHz | OUT_OF_DOMAIN |
| DOM-12 | no electronegative species | INCOMPLETE_EVIDENCE |
| DOM-13 | Maxwellian EEDF assumed | flag `MAXWELLIAN_ASSUMED` |

## 10. Raw outputs and status

| id | output | keys and units |
|---|---|---|
| OUT-01 | absorbed RF / plasma power | `P_abs_W` [W] |
| OUT-02 | coupling / impedance | `R_p_ohm`, `R_ant_ohm`, `X_ant_ohm` [ohm], `eta_p` [-], `I_ant_rms_A` [A], `P_delivered_W` [W] |
| OUT-03 | plasma state | `T_e_eV` [eV], `n_e_m3`, `n_i_m3`, `n_g_m3` [m⁻³], `phi_p_V`, `V_s_float_V` [V], `plasma_state` |
| OUT-04 | species-resolved ionization / dissociation | `R_r_per_s` [s⁻¹], `I_iz_s_A` [A], `dissociation_fraction`, `ion_fraction` [-] |
| OUT-05 | electron production capacity | `I_production_A` [A] |
| OUT-06 | extraction capacity (CFG-CAP-OFF) | `I_e_cap_A`, `I_e_sat_A`, `I_e_thermal_limit_A`, `I_ion_collection_limit_A`, `I_surface_A` [A], `binding_limit` |
| OUT-07 | electron current available for neutralization (CFG-FLIGHT-HALL-ON) | `I_e_neutralization_available_A` [A]: NOT_EVALUATED in v1 |
| OUT-08 | plasma / RF loss partition | IF-ICP-THERMAL-v1 keys [W] |
| OUT-09 | heat deposition by surface and node | `Q_icp_plasma_wall_by_surface_W`, `Q_icp_plasma_wall_by_node_W` (N_VESSEL, N_ANTENNA, N_MOUNT, N_COLLECTOR, N_HOUSING), `Q_icp_bias_by_surface_W`, `Q_icp_coil_ohmic_split_W` [W] |
| OUT-10 | gas consumption and conversion | IF-ICP-FEED-v1 keys [kg/s] |
| OUT-11 | bus-plane quantities | IF-ICP-BUS-v1 keys [W] |
| OUT-12 | domain / convergence status | status, domain flags, per-reaction chemistry validity, equilibria, residuals, coupling mode, configuration, verification / validation status, flags |
| OUT-13 | uncertainty envelope | nominal, p2.5, p97.5, min, max, u_input, u_model_form, scenario envelope |
| OUT-14 | provenance | model id / version, lock sha256, input sha256, Rust commit, contract id |

**Status vocabulary.** No other state exists in raw output (no PASS, FAIL, OK, PARTIAL or half-converged state).

| status | meaning |
|---|---|
| `CONVERGED` | solved to TOL-SOLVE, conservation within TOL-CONS, every domain check passed, every required input registered. Includes `plasma_state = NOT_SUSTAINED` when no positive-density steady state exists in the domain. |
| `MODEL_ERROR` | non-convergence, non-finite value, conservation breach, missing validity entry or contract breach. All values null. |
| `OUT_OF_DOMAIN` | an input or the converged state is outside a declared domain. Values null; the check is named. |
| `NOT_EVALUATED` | a determining external input or registration is absent (bench evidence, Hall demand, admitted Hall member, owner registration, upstream Rust component). |
| `INCOMPLETE_EVIDENCE` | a required source, table, cross section, geometry, domain criterion or evidence attribute is missing or unresolved. |

Order of evaluation: input registration → input domain → solve → solution domain → conservation → `CONVERGED`.
Every output carries its own status. A non-converged output has value null.

## 11. System coupling interfaces

### IF-ICP-HALL-v1 (electron capability vs Hall demand)

- Provides `I_e_cap_A`, `I_e_sat_A`, `binding_limit` with envelope, status, validation status, configuration
  `CFG-CAP-OFF`, `h1_point_id`, gas, mode and coupling mode.
- Consumes `I_d_max_H1_A` from an admitted HallThruster.jl member with a design-specific Hall map, or a registered
  measured value (P1-IT-07; H-1 + C1 reference characterization, A9.20).
- Hands the pair at the same registered point to assessment. No ratio, margin or verdict is formed here.
- **Today `NOT_EVALUATED`**, reasons `CREDIBLE_HALL_TRANSPORT_SET_EMPTY` (`transport_ensemble_v0.json` members `[]`)
  and `I_D_MAX_H1_NOT_REGISTERED`. Tests assert this state explicitly (FC-01, FC-02). It is never a skip or an xfail.
- Never a screening candidate; never the 8.33 A stand ceiling; never a Hall-ON record as I_e,cap.

### IF-ICP-BUS-v1 (electrical demand into bus power)

- Target boundary: **`bus_power_boundary_a9_v2`** (A9.22 G8, the `hall_icp_neutralizer` boundary). The lane brief
  names `bus_power_boundary_v1`, which has no ICP component and carries cathode components (CONF-01, OQ-NPICP-01).
- Provides, in W: `P_icp_rf_forward_W`, `P_icp_rf_reflected_W`, `P_icp_rf_source_DC_W` → slot `icp_rf_source`,
  `P_icp_matching_DC_W` → `icp_matching_network`, `P_icp_collector_bias_W` → `icp_collector_bias`,
  `P_icp_assist_magnet_W` (variant; first build unmagnetized), `P_icp_flow_control_W` (variant; G-REUSE books 0),
  `P_icp_bus_W`, `Q_icp_rf_generator_loss_W` (= P_RF,DC − (P_fwd − P_refl), at B_PPU_RF, includes the reflected
  power absorbed in the source), `Q_icp_bias_supply_loss_W` (at B_PPU_RF).
- `P_icp_bus_W` = icp_rf_source + icp_matching_network + icp_collector_bias (+ icp_assist_magnet and
  flow_control_icp_feed only when a declared variant installs them).
- **Booking, never silent.** Reflected power is the raw key `P_icp_rf_reflected_W`, booked at the bus / PPU boundary
  inside `Q_icp_rf_generator_loss_W`. The collector-bias supply is the raw key `P_icp_collector_bias_W` (supply output);
  its DC input is on slot icp_collector_bias, its conversion loss at B_PPU_RF, its output deposited per IF-ICP-THERMAL-v1.
- η_RF, η_bias and the match actuator draw are registered inputs with evidence class. They are never invented. A
  laboratory generator efficiency or mains input is labelled `GROUND_FACILITY_ONLY` and is never spacecraft bus power.
- Today `NOT_EVALUATED` (flight efficiencies PENDING; CM-ABS gives no bus quantity).
- Start-up and transient peaks are not represented (steady-state model).

### IF-ICP-THERMAL-v1 (losses into the cathodeless thermal model)

Consumer: NP-THERMAL-CATHODELESS v1 as merged (`fa10c76`, merge `35c06e4`; keys IK-01..IK-07, checks IFI-1..IFI-5,
energy-source rule HS-00, open alignment OQ-NPT-02, gap CF-04). This record aligns with it.

**Energy-source rule.** Each watt enters through the interface of the supply that powers it. No watt enters twice.
- The five deposited prescribed keys (`Q_icp_plasma_wall_W`, `Q_icp_coil_ohmic_W`, `Q_icp_match_W`,
  `Q_icp_extraction_W`, `Q_icp_radiation_W`) are **RF-powered only**. The producer declares `rf_powered_only = true`
  (consumer IFI-5). Each is ≥ 0 (IFI-2).
- **`Q_icp_plasma_wall_W` never contains Hall-powered heat.** Heating driven by the Hall discharge-current return through
  the neutralizer (ICD ICP-43 discharge-path term) is carried on the Hall side as IF-HALL-THERMAL-v1
  `Q_hall_return_to_icp_W`. Plume interception (ICD ICP-29) is carried as `Q_hall_plume_to_icp_W`. In v1 the Hall
  discharge is OFF in CFG-CAP-OFF, so no such term exists. CFG-FLIGHT-HALL-ON is `NOT_EVALUATED`. A v2 Hall-ON sub-model
  keeps this rule (FC-16).
- **Collector-bias supply.** Raw key `P_icp_collector_bias_W` (supply output into the plasma-electrode circuit). Its DC
  input is on bus slot icp_collector_bias and its conversion loss at the bus / PPU boundary. Its deposition is reported
  only by `Q_icp_bias_collector_W` (N_COLLECTOR) and `Q_icp_bias_export_W` (electron sink, export). It is never inside
  an RF-powered key.
- **Reflected RF power.** Raw key `P_icp_rf_reflected_W`, booked at the bus / PPU boundary inside
  `Q_icp_rf_generator_loss_W`. Never on a neutralizer node. Never counted twice.

**Attribution convention** (model-derived, exact). For each surface j, deposited heat Q_j = L_j + C_j:
- L_j = e A_j [Γ_e,j (2T_e + max(0, φ_p − V_j)) + Γ_i,j T_e/2] is the energy the RF-heated electron population loses
  through j (EQ-07). RF-powered keys use L_j.
- C_j = I_j (φ_p − V_j) is the energy exchanged with the external circuit at j (I_j = net positive current from the
  plasma into j). Bias keys use C_j. Σ_j C_j = P_icp_collector_bias_W = −Σ_j I_j V_j.
- Floating surfaces have I_j = 0, so Q_j = L_j.

Prescribed keys (W):

| key | meaning | node mapping |
|---|---|---|
| `Q_icp_plasma_wall_W` | RF-powered plasma heat on neutralizer surfaces touching the plasma: Σ L_j, formation energy released at walls, wall-quenched excitation, neutral energy relaxed at walls | predicted by NP-ICP per surface over the registered surface → node map (N_VESSEL, N_ANTENNA if exposed, N_MOUNT, N_COLLECTOR, N_HOUSING); neutral-relaxation and wall-quenched shares area-weighted (declared assumption, flag `AREA_WEIGHTED_NEUTRAL_TERMS`) |
| `Q_icp_coil_ohmic_W` | I_ant² R_ant: the whole non-plasma antenna-circuit loss (RP-ANT convention) | coil conductor → N_ANTENNA; induced shares to N_COLLECTOR / N_HOUSING / N_MOUNT only as a registered split (not predicted in v1) |
| `Q_icp_match_W` | matching-network loss (P2 two-port); the line loss is not inside it | N_MATCH iff `match_colocated` (ICD ICP-13), else B_PPU_RF |
| `Q_icp_extraction_W` | L_ec: energy carried out of the RF-heated electron population by the extracted electrons | EXPORT (deposited on no neutralizer node) |
| `Q_icp_radiation_W` | optical / UV radiation leaving the plasma volume | total only; f_rad is registered on the consumer side (IK-05), not predicted here |
| `P_icp_rf_forward_W` | forward RF power at RP-CPL | consumer reference only |
| `P_icp_bus_W` | ICP demand at the DC boundary (slots in IF-ICP-BUS-v1) | consumer reference only |

Additional keys (W): `P_icp_rf_reflected_W`; `Q_icp_line_W` (RP-CPL → RP-MIN; B_PPU_RF unless a co-located segment is
registered); `P_icp_abs_W`; `P_icp_collector_bias_W`; `Q_icp_bias_collector_W` (signed, N_COLLECTOR);
`Q_icp_bias_export_W` (signed, export); `Q_icp_outflow_upstream_W` (toward the H-1 exit face); `Q_icp_outflow_downstream_W`
(plume / space, excluding extraction). They are added, not substituted (OQ-NPICP-08).

**Closures** (CC-04, CC-05, relative residual ≤ 1e-10):
- RF: P_icp_rf_forward_W = P_icp_rf_reflected_W + Q_icp_line_W + Q_icp_match_W + Q_icp_coil_ohmic_W + P_icp_abs_W.
- RF-powered plasma: P_icp_abs_W = Q_icp_plasma_wall_W + Q_icp_extraction_W + Q_icp_radiation_W +
  Q_icp_outflow_upstream_W + Q_icp_outflow_downstream_W.
- Bias: P_icp_collector_bias_W = Q_icp_bias_collector_W + Q_icp_bias_export_W.
- Combined: P_icp_rf_forward_W + P_icp_collector_bias_W = sum of all eleven partition keys. With no bias supply this is
  P_icp_rf_forward_W = sum of the partition.

Consumer checks: IFI-2 holds by construction for the five deposited keys. IFI-3, IFI-4 and IFI-5 follow from the
closures when the registered η_RF gives P_icp_rf_source_DC_W ≥ P_icp_rf_forward_W (CC-06).

**Alignment gap (not resolved here).** The consumer books P_icp_bus_W − (five deposited keys) at B_PPU_RF (IK-07). That
remainder also holds `Q_icp_outflow_upstream_W` (H-1 front faces), `Q_icp_outflow_downstream_W` (export) and the
bias-supply deposition (N_COLLECTOR / export), which are not PPU heat. No energy is lost or double-counted either way;
only the node location differs (OQ-NPICP-15, CONF-11).

- Bounding pair: if any inelastic channel is `UNRESOLVED`, the keys come for `ALL_RADIATED` and `ALL_WALL`; if γ is
  unsourced, for γ = 0 and γ = 1. Each closes exactly.
- Consumes T_wall per surface / node, T_gas and T_coil. The ICP model never iterates thermally. The system orchestrator
  owns the fixed point and its convergence status.
- Excluded: Hall-powered heat at the neutralizer and plume interception (Hall side); any C-1 cathode node (none).

### IF-ICP-FEED-v1 (gas consumption into the feed / mission model)

- Consumes ṁ_s, P_feed, T_feed, x_s, gas mode and supply mode.
- Provides `mdot_icp_dedicated_kg_s` per species:
  - G-REUSE: 0 exactly (A9.1 HIQ-06; asserted, not computed);
  - G-ATM / G-XE: the registered flow echoed with provenance.
- Booking: G-XE in the Xe ledger under PHASE_TOTAL_FLOW; G-ATM as ṁ_atm,total = ṁ_Hall + ṁ_ICP,dedicated.
- Provides `dmdot_conversion_kg_s` (composition change of the throughput, never a feed demand).
- Not represented: ignition / purge flows and on-off cycle counts.

## 12. Assessment separation

- Raw physics provides `I_e_cap_A` with its envelope and status. It never contains HC-05 PASS/FAIL, a threshold or an
  RFP label.
- M_n = I_e,cap / I_d,max,H1 − 1 and HC-05 (M_n,LB > 0) are evaluated only in abep-assess, with the registered rule:
  - P1-IT-29 margin rule: one-sided α = 0.05, k_one_sided not below 1.6449;
  - u_r²(M_n + 1) = u_r²(I_e,cap) + u_r²(I_d) (UB-DQ-NEUT form);
  - registered u_I_e_A ≥ the channel-propagated value (A9.10 P1Q-19).
  - Without a lower bound HC-05 is `NOT_EVALUATED`.
- Drafted default, not decided (OQ-NPICP-02): a model-derived I_e,cap enters HC-05 only inside a `VALIDATED_BENCH`
  domain cell that contains the point, with u_model_form from validation residuals. Otherwise HC-05 is
  `NOT_EVALUATED` (`MODEL_NOT_VALIDATED_IN_DOMAIN`). A measured I_e,cap at the point supersedes the model.
- If determining bench evidence is absent, the raw output carries `NOT_EVALUATED` or the envelope with u_model_form
  `NOT_EVALUATED`.
- Enforcement: no abep-assess dependency (FC-10); forbidden-token scan (FC-11); a threshold-only change moves no raw
  byte (FC-12).

## 13. Conservation checks

| id | check | tolerance |
|---|---|---|
| CC-01 | particle balance per ion and neutral species | ≤ 1e-10 relative |
| CC-02 | element conservation (N, O, Xe, Ar) | ≤ 1e-10 of throughput |
| CC-03 | Σ I_j = 0; each floating surface; production current = loss current | ≤ 1e-10 of max |I_j| |
| CC-04 | RF chain closure | ≤ 1e-10 of P_fwd |
| CC-05 | RF-powered plasma, bias and combined closures, every bounding assignment; the five deposited keys ≥ 0 | ≤ 1e-10 of P_fwd + P_collector_bias |
| CC-06 | bus sum; every conversion loss ≥ 0; P_icp_rf_source_DC_W ≥ P_icp_rf_forward_W (declared assumption: the source does not recover reflected power; a violating η_RF registration is refused, `MODEL_ERROR`) | ≤ 1e-10 |
| CC-07 | formation-energy bookkeeping | ≤ 1e-10 |

Basis: CLAUDE.md rule 4 (source balances close exactly). The tolerances are numerical policy for IEEE double after a
solve to 1e-12. They are not physics numbers. No term is a remainder, so the checks test the solve and the
bookkeeping. They cannot detect a physics error in a source term by themselves.

## 14. Analytic limiting cases

| id | case | exact pass criterion | basis |
|---|---|---|---|
| LC-01 | T_e set by particle balance | synthetic single gas, fixed n_g, CM-ABS: T_e equal at P_abs, 10 P_abs, 100 P_abs and equal to an independent bisection root of n_g k_iz V = u_B Σ h A, ≤ 1e-9 | EQ-03 (model-derived); textbook verify |
| LC-02 | n_e linear in P_abs | same setup: n_e / P_abs constant and = 1 / (e u_B Σ h A (E_iz + 2T_e + T_e/2 + V_s)), ≤ 1e-9 | slides 41, 48, 50 |
| LC-03 | zero absorbed power | `CONVERGED`, `NOT_SUSTAINED`, n_e = 0, I_e_cap = 0, I_production = 0, every plasma key 0 exactly; forward power closes into reflection and circuit losses; CM-PRED lists the trivial branch separately | EQ-07, EQ-12, EQ-14 |
| LC-04 | η_p → 1 as R_ant → 0 | η_p = 1/(1 + R_ant/R_p) to 1e-12 for R_ant/R_p ∈ {1, 1e-3, 1e-6}; at 0: η_p = 1, Q_coil_ohmic = 0 exactly | Takahashi Eq. (1) |
| LC-05 | thermal-flux bound | I_e_cap ≤ ¼ e h n_e v̄_e A_ec (1 + 1e-12) always; equality to 1e-9 when A_ic ≫ A_ec and V_ec > φ_p | EQ-09, EQ-11 |
| LC-06 | ion-collection and production bounds | I_e_cap ≤ both limits (1 + 1e-12); all-floating with no electron collector gives I_e_cap = 0 exactly | EQ-03, EQ-10 |
| LC-07 | floating sheath | V_s = (T_e/2) ln(M/2π m_e) to 1e-12; V_s/T_e rounds to 4.7 for argon | slide 48 |
| LC-08 | Lieberman worked example | argon, 3.5 V: u_B rounds to 2.9e3 m/s; R = 0.15 m, L = 0.3 m, λ_i = 0.03 m: h_R = 0.8/3, h_L = 0.86/√8 (1e-12), both round to 0.3; h_R → 0.4 as λ_i → ∞ | slides 44, 52 |
| LC-09 | free-molecular effusion | n = Γ_in / (¼ v̄ A) to 1e-12; v̄(N2, 293 K) within 2e-3 of 470 m/s; C′ within 2e-3 of 117.5 m³ s⁻¹ m⁻² | Chiggiato Eqs. 3, 13, Tables 4, 8 |
| LC-10 | partition closure with a biased electrode | P_abs = Σ RF-powered partition and P_collector_bias = Q_bias_collector + Q_bias_export, each to 1e-10, with P_collector_bias = −Σ I_j V_j computed independently; Q_j = L_j + C_j per surface to 1e-12; all-floating gives C_j = 0 exactly | EQ-07, EQ-10, EQ-16 |
| LC-11 | predictive coupling vanishes without plasma | R_p → 0 monotonically as n_e → 0, R_p = 0 at n_e = 0, X → ω L_11 | EQ-14 (verify; only after VER-03) |

## 15. Numerical verification and fail-closed tests

- TOL-SOLVE: each balance residual ≤ 1e-12 of its largest term. TOL-ANALYTIC: 1e-9 unless a case says otherwise.
- T_e and φ_p are bracketed over the whole declared domain before refinement. Every sign change on the registered
  root-scan grid is refined and reported. No root is chosen silently.
- Iteration limit reached → `MODEL_ERROR`.
- NV-01 double-run byte identity; NV-02 thread-count independence; NV-03 residuals reported; NV-04 a two-root synthetic
  case reports both roots; NV-05 any non-finite value → `MODEL_ERROR` with null values; NV-06 direct-integral vs
  `.dat` difference reported per reaction.

Fail-closed tests (asserted results; nothing skipped; A9.29 RM-OQ-05):

| id | assertion |
|---|---|
| FC-01 | empty credible set → IF-ICP-HALL-v1 `NOT_EVALUATED`, `CREDIBLE_HALL_TRANSPORT_SET_EMPTY` |
| FC-02 | no I_d,max,H1 registration → `NOT_EVALUATED`, `I_D_MAX_H1_NOT_REGISTERED` |
| FC-03 | CFG-FLIGHT-HALL-ON → `NOT_EVALUATED` for OUT-07 and every Hall-dependent output |
| FC-04 | CM-CAL without a validated P2 map → `NOT_EVALUATED` for coupling, RF-plane and bus keys |
| FC-05 | missing geometry, electrode registration, σ_i or evidence attribute → `INCOMPLETE_EVIDENCE` naming each |
| FC-06 | 3/2 T_e above a used table limit → `OUT_OF_DOMAIN` naming the reaction; T_e < 2 eV (N2/N) → `OUT_OF_DOMAIN` |
| FC-07 | unresolved file → `INCOMPLETE_EVIDENCE`; file without an entry → `MODEL_ERROR` |
| FC-08 | G-REUSE → `mdot_icp_dedicated_kg_s` = 0 exactly |
| FC-09 | non-convergence → `MODEL_ERROR`, every physics value null |
| FC-10 | abep-icp depends on neither abep-assess nor abep-groundtest |
| FC-11 | no `LaB6`, `hollow_cathode`, `keeper`, `heater` or `c1_` identifier in abep-icp source; no `HC-05`, `GNG-ICP`, `PASS`, `FAIL` or RFP clause id in any output |
| FC-12 | a gate-threshold change moves no raw ICP output byte |
| FC-13 | O2-bearing case → `INCOMPLETE_EVIDENCE`; Xe or Ar case → `INCOMPLETE_EVIDENCE` until a rate set is registered |
| FC-14 | registered B_ICP,max > 0 → `INCOMPLETE_EVIDENCE` for capacity outputs until OQ-NPICP-03 |
| FC-15 | `SYNTHETIC_TEST_ONLY` propagates to every output; mixing synthetic and evidence inputs is refused |
| FC-16 | thermal record: `rf_powered_only = true`; the five deposited keys ≥ 0; no Hall-powered term (`Q_hall_return_to_icp_W`, `Q_hall_plume_to_icp_W`) computed by or added into any ICP key; `P_icp_rf_reflected_W` and `P_icp_collector_bias_W` always present (value or explicit status) |

## 16. Validation plan

**Principles.**
- No synthetic Python reference is required or created.
- Admission uses conservation, analytic limiting cases, applicable published evidence, P1/P2 evidence when available
  and the criteria below.
- Calibration data never validate the quantity they calibrated. In CM-CAL the P2 impedance is calibration. The
  validated quantity is a different measurand (I_e,cap, T_e, n_e, p_ICP, collector heat) or a P2 point outside the
  calibration partition.
- No retuning after any comparison. A model change is a new model_version and a new preregistration.
- Published data are evidence, not truth.

**Comparison criteria (fixed now).**

| id | criterion |
|---|---|
| VC-01 | z = (y_model − y_meas) / √(u_input² + u_meas²), standard uncertainties. `CONSISTENT` if \|z\| ≤ 2, `INCONSISTENT` if \|z\| > 2. u_model_form is excluded from z to avoid circularity. Precedent: k_x = 2 (A9.1 UBQ-04); k_agreement = 2.0 (A9.14 P2Q-06). |
| VC-02 | where the model gives only an upper bound (e.g. P_abs ≤ P_net with unknown η_p): `FALSIFIED` if y_meas − y_model,UB > 2 u_meas, else `NOT_FALSIFIED` (never "validated"). |
| VC-03 | r_u = u_input / u_meas is reported with every comparison. No threshold is set here (OQ-NPICP-13). |
| VC-04 | per domain cell (mode × configuration × coupling mode × geometry id): `VALIDATED_BENCH` when every point of the frozen set is `CONSISTENT` and none is `NOT_EVALUATED`; one `INCONSISTENT` point makes the cell `INCONSISTENT`. Cells never transfer. |
| VC-05 | I_e_cap_A is mapped to the owner sign convention (P1-IT-42 / P1-IT-48) by a registered adapter. Only `ICP45_CAPACITY` records meeting all four A9.5 P1Q-16 conditions are comparison points. Hall-ON records never are. |
| VC-06 | each validation set (record ids, measurands, partition) is frozen with a sha256 before its data are inspected. |

**Published evidence.**

| id | source | role | status |
|---|---|---|---|
| VAL-PUB-01 | Takahashi et al. 2024 (registered, full text) | topology precedent only. Non-scoring coupling plausibility: R_ant 0.36 ohm (TK-24), R_total ≈ 0.4 ohm (TK-25), η_p ≈ 0.1 (TK-26), ≈ 20 W absorbed of 200 W forward (TK-27, authors' estimate). Not for I_e,cap: Hall-ON, Ar, HET ions on the collector (TK-70), no electron-current balance (TK-56), different circuit (TK-40). | NOT_EVALUATED (antenna geometry schematic only, TK-11; no Ar chemistry) |
| VAL-PUB-02 | Watanabe et al. 2016 TASTJ (S-01, full text) | VC-02 bound test: 3.3 A at 140 W net RF, Xe 0.3 mg/s, anode 58 V; current proportional to RF power. Orifice topology. | NOT_EVALUATED (no Xe chemistry; coil detail VER-16) |
| VAL-PUB-03 | Xu et al. 2022 PST (S-02) | VC-02 bound tests: 1.03 A at 270 W, 0.18 A at 50 W, Xe 2.766 sccm, 50 V bias | NOT_EVALUATED (no Xe chemistry) |
| VAL-PUB-04 | Schwertheim et al. 2025 preprint (cathode dossier) | VC-02 bound test: up to 0.45 A, 90 W RF on 0.8 sccm 50:50 N2/O2 | NOT_EVALUATED (O2 chemistry, negative ions, geometry) |
| VAL-PUB-05 | Scholze, Tartz, Neumann 2008 (S-03, abstract; LA-04) | candidate (verify) | NOT_EVALUATED |
| VAL-PUB-06 | Longmier & Hershkowitz 2008 (S-04, abstract; LA-05) | candidate (verify); possibly magnetized, context only | NOT_EVALUATED |
| VAL-PUB-07 | Dietz et al. 2020 (S-05, abstract; LA-06) | candidate method precedent (verify) | NOT_EVALUATED |
| VAL-PUB-08 | LA-01, LA-02, LA-03, LA-07, LA-08 (metadata only) | candidates (verify); acquisition is an owner action | NOT_EVALUATED |

**Hardware evidence (P1/P2, when available).**

| id | evidence | validates | status |
|---|---|---|---|
| VAL-HW-01 | P2 impedance map, H_MODE points | CM-PRED R_p, X, η_p on points never used for calibration | NOT_EVALUATED |
| VAL-HW-02 | P1 `ICP45_CAPACITY` records, CFG-CAP-OFF (Ar first; then ICP-45N on N2) | I_e_cap_A in CM-ABS (measured P_abs), CM-CAL, CM-PRED | NOT_EVALUATED |
| VAL-HW-03 | P1 Langmuir probe near the collector (P1-M-30, conditional) | T_e, φ_p (supporting, non-gating) | NOT_EVALUATED |
| VAL-HW-04 | P1 calorimetric collector balance (P3-P1-09) | collector surface heat (supporting) | NOT_EVALUATED |
| VAL-HW-05 | p_ICP (VI-GAS-03), conductance (VI-GAS-04) | FLOW_BALANCE neutral density | NOT_EVALUATED |
| VAL-HW-06 | P1-S5 dwells, P2 plasma_state_class | qualitative consistency of CM-PRED equilibria only (non-gating). The model never asserts a stable operating region. | NOT_EVALUATED |
| VAL-HW-07 | ground Xe and O2-bearing campaigns | XE_CONTINGENCY and O2-bearing cells, after their chemistry exists | NOT_EVALUATED |

## 17. Admission rule

- **VERIFIED** (software admission) when, on the integration line:
  1. this preregistration and its lock are committed;
  2. abep-icp passes every LC, CC, NV and FC item under `cargo test --workspace --locked`;
  3. the abep-chem rate evaluator it uses is admitted (SC-WP-03);
  4. every verify item on an admitted code path is cleared by a verification addendum;
  5. an admission record pins the Rust commit, the test log and this lock's sha256.
- Paths are admitted separately. The core (CFG-CAP-OFF, CM-ABS) can be VERIFIED while CM-PRED is not admissible
  (VER-03..05) and CM-CAL has no data.
- Every output carries `validation_status = NOT_VALIDATED` until a domain cell reaches `VALIDATED_BENCH` (VC-04;
  plan v3.1 RM-R31, new-physics lifecycle VERIFIED → ADMITTED).
- With the core VERIFIED and every unavailable quantity failing closed, the model fills the predictive RF/ICP block of
  the A9.29 sec. 15 chain. "Software complete" never turns `NOT_EVALUATED` into PASS.
- An independent cross-check is optional and non-authoritative.

## 18. Uncertainty handling

- UQ-01: every input has a registered representation: interval (manufacturer ± a → u = a/√3, A9.1 UBQ-03), normal
  (u, k), scenario set, or physical bound ([0, 1] for probabilities).
- UQ-02: epistemic choices form an unweighted scenario set (chemistry variants, disposition pair, γ bounds). Outputs
  are reported per scenario and as the envelope.
- UQ-03: parametric inputs are propagated by seeded sampling under the registered Rust RNG policy (abep-rng, SC-WP-10;
  A9.29 RM-OQ-03). Seed and N are recorded. N starts at 1024 and doubles until the 2.5 / 97.5 percentiles of every
  output change by ≤ 1 % relative, up to 65536; otherwise the envelope is `MODEL_ERROR`.
- UQ-04: each output reports nominal, p2.5, p97.5, min, max, u_input, u_model_form. The one-sided lower bound is formed
  in assessment.
- UQ-05: u_model_form is `NOT_EVALUATED` until validation residuals exist. It is never assumed.
- UQ-06: the direct-integral vs `.dat` difference enters the envelope as a scenario pair.
- UQ-07: no uncertainty is narrowed relative to its producer's record.

## 19. NOT_EVALUATED today, and why

| id | what | status | why |
|---|---|---|---|
| NE-01 | flight I_e,cap | INCOMPLETE_EVIDENCE | ICP geometry and electrodes TBD |
| NE-02 | R_p, X, η_p, P_fwd | NOT_EVALUATED | no P2 data; CM-PRED blocked by VER-03..05 and antenna geometry |
| NE-03 | AIR_PRIMARY, EM-O2B | INCOMPLETE_EVIDENCE | O/O2 chemistry, atomic O, negative ions; O/O2 split TBD |
| NE-04 | XE_CONTINGENCY, EM-XE | INCOMPLETE_EVIDENCE | no Xe rate set |
| NE-05 | EM-AR | INCOMPLETE_EVIDENCE | no Ar rate set |
| NE-06 | EM-N2 point results | INCOMPLETE_EVIDENCE | no ion-neutral cross sections; ICP completeness not audited; no geometry |
| NE-07 | IF-ICP-HALL-v1 | NOT_EVALUATED | credible set EMPTY; I_d,max,H1 not registered |
| NE-08 | CFG-FLIGHT-HALL-ON, OUT-07 | NOT_EVALUATED | needs an admitted Hall member |
| NE-09 | P_icp_bus_W | NOT_EVALUATED | flight η_RF / η_bias PENDING |
| NE-10 | IF-ICP-THERMAL-v1 values | NOT_EVALUATED | follows NE-01..06; NP-THERMAL not implemented |
| NE-11 | magnetization domain at H-1 points | INCOMPLETE_EVIDENCE | B_ICP not measured; no criterion |
| NE-12 | any validation status above NOT_VALIDATED | NOT_EVALUATED | no P1/P2 data; analogs blocked |
| NE-13 | u_model_form | NOT_EVALUATED | no validation residuals |

## 20. Verify items

Each item is recalled from memory or not readable from repository files. None enters an admitted code path until a
verification addendum records the source read and confirms the text (verify gate).

| id | item | used by |
|---|---|---|
| VER-01 | Lieberman & Lichtenberg, *Principles of Plasma Discharges and Materials Processing*, 2nd ed., Wiley (2005), ch. 10: global balance form; T_e set by particle balance | EQ-03, LC-01 (cross-reference) |
| VER-02 | elastic loss term n k_m (3 m_e/M)(T_e − T_g) | EQ-07 |
| VER-03 | Piejak, Godyak, Alexandrovich, Plasma Sources Sci. Technol. 1, 179 (1992); Lieberman & Lichtenberg 2005 ch. 12: every transformer-model formula and its geometric assumptions | EQ-14, LC-11, DOM-10, CM-PRED |
| VER-04 | need for and form of stochastic heating in ν_eff | EQ-14 |
| VER-05 | slope stability criterion of an equilibrium | EQ-14, OUT-12 |
| VER-06 | Baalrud, Hershkowitz, Longmier, Phys. Plasmas 14, 042109 (2007): electron-saturation regime and area condition (form not stated here) | EQ-09 |
| VER-07 | open tube end as an axial h_L surface; candidate precedent Chabert et al., Phys. Plasmas 19, 073512 (2012) | EQ-05, outflow keys |
| VER-08 | Bohm speed for Z > 1 | EQ-04 |
| VER-09 | ion-neutral sources: Phelps, JPCRD 20, 557 (1991); Phelps, J. Appl. Phys. 76, 747 (1994); Miller et al., J. Appl. Phys. 91, 984 (2002) | IN-17, CHG-06 |
| VER-10 | Xe / Ar electron-impact sources: Rejoub, Lindsay, Stebbings, Phys. Rev. A 65, 042713 (2002); Hayashi, J. Phys. D 16, 581 (1983); Rapp & Englander-Golden, J. Chem. Phys. 43, 1464 (1965); Straub et al., Phys. Rev. A 52, 1115 (1995) | CHG-04, CHG-05 |
| VER-11 | radiative vs metastable disposition per excited state | IN-23, CHG-08 |
| VER-12 | wall surface energy terms (work function, neutralization) | EQ-18, Q_icp_plasma_wall_W |
| VER-13 | coil conductor AC resistance with skin effect; resistivity source | CM-PRED R_ant lower bound |
| VER-14 | conductor resistivity temperature coefficient | IN-14 |
| VER-15 | lawful-acquisition items LA-01..LA-09 (metadata / abstract only) | VAL-PUB-05..08 |
| VER-16 | Watanabe 2016 coil geometry from the registered full text | VAL-PUB-02 |
| VER-17 | Turner & Lieberman, Plasma Sources Sci. Technol. 8, 313 (1999): cited in the repository failure tree, not read here | EQ-14 |
| VER-18 | Lee & Lieberman, J. Vac. Sci. Technol. A 13, 368 (1995): candidate O2 global-model precedent for v2 | CHG-03 |

## 21. Open items for the owner (not resolved here)

| id | question | blocks |
|---|---|---|
| OQ-NPICP-01 | Bus boundary: `bus_power_boundary_a9_v2` (as drafted, A9.22 G8) or the brief's `bus_power_boundary_v1`? | IF-ICP-BUS-v1 slot mapping |
| OQ-NPICP-02 | May a VERIFIED but not bench-validated model I_e,cap enter HC-05? Drafted default: no. | assessment use of the model |
| OQ-NPICP-03 | Magnetization criterion for the H-1 fringe field in the ICP volume (no sourced threshold registered) | CFG-CAP-OFF at energized magnet states |
| OQ-NPICP-04 | ICP-domain chemistry completeness audit: reuse the frozen N2 rule, with which domain and which omitted processes? | CONVERGED N2 cases |
| OQ-NPICP-05 | Xe and Ar sources to register | XE_CONTINGENCY, EM-XE, EM-AR |
| OQ-NPICP-06 | O/O2 promotion for the ICP and its relation to CLAUDE.md next-work item 4 | AIR_PRIMARY, EM-O2B |
| OQ-NPICP-07 | Calibration / validation partition rule for P1/P2 records | CM-CAL in any validation comparison |
| OQ-NPICP-08 | Accept the additional thermal keys, the supply-attribution convention (Q_j = L_j + C_j) and the bounding-pair convention | thermal consumption |
| OQ-NPICP-09 | Quasi-neutrality / thin-sheath criterion | nothing now (reported only) |
| OQ-NPICP-10 | Lawful acquisition of VER-03..05 and VER-15 sources | CM-PRED admission |
| OQ-NPICP-11 | Is v1 (CFG-CAP-OFF + a NOT_EVALUATED Hall-ON contract) enough for SIMULATION_COMPLETE, or is a Hall-ON neutralization sub-model (v2) required once a Hall member is admitted? | OUT-07 scope |
| OQ-NPICP-12 | Effective plasma volume of the open tube: GEOMETRIC_TUBE or a registered bench value | point values |
| OQ-NPICP-13 | Validation-set membership, minimum coverage, informativeness threshold | VALIDATED_BENCH |
| OQ-NPICP-14 | G-REUSE neutral source for flight: measured p_ICP, cold-flow conductance, or an inflow-fraction bound | flight neutral density |
| OQ-NPICP-15 | NP-THERMAL v1 books P_icp_bus_W − (five deposited keys) at B_PPU_RF, but that remainder holds the upstream / downstream outflow and the bias-supply deposition. Approve a v2 alignment that consumes those keys, or accept the lumping as a labelled approximation? | node location of bias and outflow heat |

## 22. Repository items that conflict with or constrain A9.29 sec. 4

| id | where | against | handling |
|---|---|---|---|
| CONF-01 | brief and CLAUDE.md admissibility name `bus_power_boundary_v1` (A5-era: hall_only / rf_hall / ecr_hall, cathode components, no ICP) | sec. 4 bus coupling; A9.22 G8 | target `bus_power_boundary_a9_v2`; OQ-NPICP-01 |
| CONF-02 | A9-04 uncertainty budget UB-DQ-NEUT: I_e,cap = max over a Hall-ON bias sweep; "no neutralizer electron current is predicted" | A9.4 P1Q-10 / A9.5 P1Q-16 discharge-OFF measurand; sec. 4 predictive requirement | later owner decisions govern; A9-04 stays immutable history |
| CONF-03 | A9.14 F6-OQ-03: geometry-response model only after separate predictive validation | sec. 4 predictive model (constraint on use) | EX-11 |
| CONF-04 | plan v3 (`1236f91`) treated the predictive model as conditional on RM-OQ-12; plan v3.1 was absent at the first drafting base `e5528bd` | sec. 4 closes RM-OQ-12 as required | **resolved by plan v3.1** (`eb78b4a`, merged `a5a59ea`): the model is unconditional (SC-WP-03 element `required: true`, RM-R34, `np_icp_neutralizer`; engineer-weeks now unconditional). References re-pointed and re-pinned; v3 kept as superseded evidence; traced in §23 |
| CONF-05 | CLAUDE.md next-work item 4 gates O2/O chemistry | sec. 15 requires AIR_PRIMARY (O-dominated air) | AIR_PRIMARY fails closed; OQ-NPICP-06 |
| CONF-06 | `plasma_chem.py` defaults h_l = 0.4, `EPS_C` fits, unverified Arrhenius rates | sec. 4 no invented values, no wholesale port | EX-01 |
| CONF-07 | the seven prescribed thermal keys cannot close P_fwd | sec. 4 conservation; rule 4 | additional keys; OQ-NPICP-08 |
| CONF-08 | `Q_icp_coil_ohmic_W` read literally as coil heat | Takahashi TK-27 (electrode eddy heating) | total antenna-circuit loss; conductor split registered or NOT_EVALUATED |
| CONF-09 | "atmospheric species relevant to the registered environment" | delivered O/O2 split TBD | IN-05 INCOMPLETE_EVIDENCE |
| CONF-10 | H2-5 / P3 v2 network carries a C-1 cathode node (AFI-03) | A9.19 / A9.20 | no cathode term in IF-ICP-THERMAL-v1 |
| CONF-11 | NP-THERMAL v1 (`c093ff2`) IK-07 / CF-04 book the collector-bias supply and the bus remainder at B_PPU_RF | physical location: bias output lands on the ion collector and the electron sink; outflow lands on H-1 faces or leaves; only conversion losses are PPU heat | keys provided; OQ-NPICP-15 |

## 23. Scope traceability (A9.29 sec. 4, verbatim bullets → fields)

**INPUTS**

| bullet | fields |
|---|---|
| gas/feed state from the active upstream chain; | IN-04, IN-02, IF-ICP-FEED-v1.consumes, EQ-02 |
| atmospheric species relevant to the registered environment; | IN-05, AIR_PRIMARY, chemistry gaps |
| Xe contingency mode; | IN-06, XE_CONTINGENCY, CHG-04 |
| 13.56 MHz operating frequency; | IN-07, DOM-11, EQ-14 |
| RF electrical input / absorbed-power representation; | IN-08, IN-09, coupling modes, EQ-12, EQ-13, EQ-14 |
| geometry / effective plasma volume; | IN-10, IN-11, OQ-NPICP-12 |
| pressure / neutral density; | IN-12, IN-13, EQ-01, EQ-02, DOM-04 |
| thermal boundary inputs; | IN-14, IF-ICP-THERMAL-v1.consumes |
| registered uncertainty / evidence classes. | IN-22, per-input evidence and uncertainty fields, UQ-01..07 |

**RAW PHYSICS OUTPUTS**

| bullet | fields |
|---|---|
| absorbed RF/plasma power; | OUT-01 |
| electron temperature or equivalent registered plasma state; | OUT-03 |
| electron density; | OUT-03 |
| species-resolved ionization / dissociation quantities where included; | OUT-04 |
| electron production / extraction capacity; | OUT-05, OUT-06, EQ-11 |
| electron current available for neutralization; | OUT-06, OUT-07 |
| plasma / RF loss partition; | OUT-08, EQ-16, IF-ICP-THERMAL-v1 |
| neutralizer heat deposition; | OUT-09, IF-ICP-THERMAL-v1 prescribed and additional keys, attribution convention |
| applicable coupling / impedance quantities; | OUT-02 |
| domain / convergence status. | OUT-12, status vocabulary, DOM-01..13 |

**SYSTEM COUPLING**

| bullet | fields |
|---|---|
| couple RF/ICP electron-current capability to Hall discharge-current demand; | IF-ICP-HALL-v1 |
| couple RF/ICP electrical demand into bus power; | IF-ICP-BUS-v1, EQ-15 |
| couple RF/ICP losses into the cathodeless thermal model; | IF-ICP-THERMAL-v1 |
| couple gas consumption into the feed / mission model. | IF-ICP-FEED-v1, EQ-17 |

**ASSESSMENT SEPARATION**

| bullet | fields |
|---|---|
| Raw RF/ICP physics MUST NOT contain HC-05 PASS/FAIL, requirement thresholds, RFP compliance labels. | EX-05, §12, output rules, FC-10, FC-11, FC-12 |
| Raw output provides quantities such as I_e,cap | OUT-06, IF-ICP-HALL-v1 |
| Assessment separately evaluates M_n = I_e,cap / I_d,max,H1 - 1 with the registered uncertainty rule. | §12, OQ-NPICP-02 |
| If determining bench evidence is absent, output uncertainty / NOT_EVALUATED appropriately. | §12, status vocabulary, §19 |
| Do not invent coupling efficiency, impedance, extraction efficiency or stable operating regions merely to close the model. | EX-08, coupling modes, EQ-11, EQ-13, EQ-14, VAL-HW-06 |
| The model may have calibrated and uncalibrated modes, but provenance and domain must be explicit. | CM-CAL, CM-PRED, DOM-08..10, OUT-12 coupling_mode |

**VALIDATION**

| bullet | fields |
|---|---|
| conservation; | CC-01..07 |
| analytic limiting cases; | LC-01..11 |
| applicable published evidence; | VAL-PUB-01..08 |
| P1/P2 hardware evidence when available; | VAL-HW-01..07 |
| preregistered comparison criteria. | VC-01..06, §17 |
| No synthetic Python reference is required. | method, §16 principles |

**Plan v3.1 SC-WP-03 NP-ICP-NEUTRALIZER** (`simulation_completion_programme_v1_1.json`; `programme_v3_1.json`)

| plan v3.1 item | fields |
|---|---|
| minimum_scope inputs and raw outputs (incl. "electron current available for neutralization (I_e,cap)") | INPUTS and RAW PHYSICS OUTPUTS rows above; OUT-06, OUT-07, EQ-11 |
| coupling I_e,cap → Hall demand; consumer SC-WP-03 neutralization / coupled thrust; margin only in SC-WP-11 | IF-ICP-HALL-v1, §12 |
| coupling demand → bus power; consumer SC-WP-05 bus-power ledger | IF-ICP-BUS-v1, EQ-15, CC-06 |
| coupling losses → cathodeless thermal; consumer SC-WP-06 NP-THERMAL-CATHODELESS | IF-ICP-THERMAL-v1, EQ-16, CC-05 |
| coupling gas consumption → feed / mission; consumers SC-WP-03 coupled thrust / flow and SC-WP-09 mission | IF-ICP-FEED-v1, EQ-17, CC-02 |
| assessment_separation; no_invention; modes | EX-05, EX-08, §12, CM-CAL / CM-PRED, DOM-08..10, FC-10..12 |
| validation_basis_for_admission; no_synthetic_python_reference | CC, LC, VAL-PUB, VAL-HW, VC-01..06, §17, method |
| excluded (plasma_chem wholesale; LaB6, hollow-cathode, ECR, stage-1) | EX-01..04 |
| preregistration path; gating | this folder; implementation gate |
| validation_status_after_admission (RM-R31) | §17 |
| gate [8] calibrated-quantity bench evidence absent → NOT_EVALUATED | FC-04, EX-08, NE-02 |
| gate [9] outside the preregistered domain, per mode → OUT_OF_DOMAIN | DOM-01..13, FC-06 |
| gate [10] non-converged plasma state → MODEL_ERROR | FC-09, NV-05 |
| gate [11] measured validation absent (VERIFIED) → NOT_EVALUATED | §17, NE-12, NE-13 |
| admission [5] own commit before implementation; validation basis; modes with provenance and domain | implementation gate, §16, §17, §5 |
| admission [6] no HC-05 / threshold / RFP label; M_n only in SC-WP-11; abep-icp never depends on abep-assess | EX-05, §12, FC-10, FC-11, FC-12 |
| admission [7] couplings present and conservative | IF-ICP-HALL/BUS/THERMAL/FEED-v1, CC-02, CC-04..06 |
| ES-NP-ICP deliverables | §2, §3, §5, §16, implementation gate |
| RM-R34 | method, §2, §3, §5, §12 |

Every v3.1 item maps to an existing field. No modelling content was added for this alignment.

**Other sec. 4 rules**: "NEW PHYSICS" → method; "Do NOT port plasma_chem.py wholesale" → EX-01, CONF-06; "Do NOT
inherit LaB6, hollow-cathode, ECR or legacy stage-1 topology" → EX-02, EX-03, EX-04; "a new preregistered model
specifically for the selected downstream 13.56 MHz RF/ICP electron-source / neutralizer" → id, §2, §4.
Related: sec. 13 → implementation gate; sec. 14 → §§9-18; sec. 15 → §4, EX-02, EX-06.

## 24. References

Registered in the repository (locators in the JSON):
- Takahashi, Watanabe, Nakahama, Kikuchi, J. Electr. Propuls. 3, 18 (2024), doi 10.1007/s44205-024-00081-2.
- Lieberman, short course "Principles of plasma discharges and materials processing" (2015), slides 38, 41, 43, 44,
  48, 50, 52, 53.
- Chiggiato, "Vacuum Technology for Ion Sources", arXiv:1404.0960 (2014); Santeler, J. Vac. Sci. Technol. A 4, 338
  (1986) via Chiggiato Eq. 21.
- Goebel & Katz, *Fundamentals of Electric Propulsion* (JPL, 2008), Eqs. 4.2-9, 4.2-10, 7.3-47, 7.3-61, App. C.
- Song et al., JPCRD 52, 023104 (2023); Song et al., JPCRD 55, 013102 (2026) (accepted manuscript).
- abep-n2n-0.11 table sources (`hallthruster_bridge/propellants/PROVENANCE.md`).
- JCGM 100:2008.
- Watanabe et al., Trans. JSASS 14 (2016) Pb_77; Xu et al., Plasma Sci. Technol. 24, 015404 (2022); Schwertheim et
  al., IEPC-2025-378 preprint.

Not in the repository (verify): Lieberman & Lichtenberg 2005; Piejak, Godyak & Alexandrovich 1992; Baalrud,
Hershkowitz & Longmier 2007; Chabert et al. 2012; Turner & Lieberman 1999 (cited, not read); Lee & Lieberman 1995;
Phelps 1991; Phelps 1994; Miller et al. 2002; Rejoub, Lindsay & Stebbings 2002; Hayashi 1983; Rapp &
Englander-Golden 1965 (named in a repository builder, its Ar data not read); Straub et al. 1995.
