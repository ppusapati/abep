# NP-ICP-NEUTRALIZER preregistration v2

| item | value |
|---|---|
| model id | `NP-ICP-NEUTRALIZER` |
| preregistration / model version | v2 / model_version `2` |
| status | **`PREREGISTERED_NOT_IMPLEMENTED`** |
| method | `NEW_PHYSICS`: preregistered model → Rust → analytic and independent-evidence verification → admission. No synthetic Python reference. |
| target crate | `abep-icp` (model_version 2 is added beside model_version 1; never depends on `abep-assess` or `abep-groundtest`) |
| governing rulings | A9.31 secs. 7, 8, 9, 10, applied word for word (`OD_2026_10_06_A9_31_*`, sha256 in the JSON); A9.30 secs. 3-5 |
| registered | 2026-10-06 on `0d8922c` (origin/integration/simulation-complete) |
| machine-readable | `prereg_v2.json` (same folder). If the two disagree, the JSON is authoritative. |
| lock | `prereg_lock_v2.json` (sha256 of both files, frozen at commit) |
| drafted by | agent session for the RF/ICP v2 preregistration lane. Not reviewed by the owner. Nothing here is a new owner decision. |

**What this is.** The v2 preregistration A9.31 sec. 9 asks for. It resolves the v1 equation and bookkeeping defects PF-01,
PF-02 and GAP-01..05, incorporates the approved INT-16/17/18, applies the sec. 10 rulings on assessment use, and registers
three interfaces:
- `IF-ICP-THERMAL-v2`, matched with NP-THERMAL-CATHODELESS prereg v2 (sec. 7);
- `IF-ICP-BUS-v2`, with an explicit plane for every key (sec. 8);
- `CPL-HALL-ON-v1`, the Hall-ON neutralization coupling contract (OQ-NPICP-11). Its execution is gated.

**What is unchanged.** Every v1 item (by id) that this record does not replace or retire applies verbatim, as re-pointed
by addendum 01 (G-A930-AIR) and addendum 02 (NP-ICP-CHEM-AIR pointers). Examples are the model class, CM-ABS / CM-CAL /
CM-PRED, EQ-01, EQ-03, EQ-04, EQ-06, EQ-07 and EQ-10..EQ-14. The rest are the status vocabulary, LC-01..LC-11, NV-01..06,
FC-01..FC-13, FC-15, the published and hardware evidence lists, and VER-01..VER-18. Nothing inherited is relaxed.

**v1 is immutable history.** `prereg_v1.json`, `PREREG.md`, `prereg_lock_v1.json`, both addenda and both verification
reports are pinned in the JSON (`predecessor`) and are not edited.

**Implementation gate.** No model_version 2 code before this record and its lock are committed. Each verify item and each
fail-closed gate blocks only the outputs listed against it.

---

## 1. How each defect is resolved

Every resolution rests on conservation, dimensional consistency, a registered source or an explicit bounding branch.
None uses an invented point value, a 50/50 split or another convenience split.

| id | v1 defect | v2 resolution | basis | checks |
|---|---|---|---|---|
| PF-01 | EQ-02 removed (γ/2)·¼ n v̄ A, but NP-ICP-CHEM-AIR defines γ per collision. With γ ∈ [0, 1] the physical maximum was unreachable. | Atom sink at wall j: γ_k,m(j) ¼ n_k v̄_k A_j. Molecule source: ½ of that sum. γ per (atomic species, wall material): sourced, or the vertex set {0, 1}. Recombination energy D0: a fraction β goes to the surface, 1 − β to class N. | registered definition (AIR-WALL-02/03); impingement (Chiggiato sec. 2.1); nuclei conservation | LC-13, FC-17 |
| PF-02 | Background inflow had no τ while effusion did. For τ < 1 the no-plasma equilibrium was n_b/τ. | Inflow through each open end: ¼ n_b v̄_b A_j τ_j. Applies only to a registered isotropic Maxwellian background. T_b ≠ T_g → flag `NON_ISOTHERMAL_PASSAGE`, gated by VER-20. A flight hyperthermal ambient needs a registered exposure model (DOM-17). | Chiggiato Eq. 13 / 19-21 (Q = C Δp: the same τ both ways); detailed balance at n = n_b | LC-12, FC-18 |
| GAP-01 | No operational wall/outflow split for elastic, vibrational and rotational energy | Energy class N, destination vertex set {WALL[m] for each wall material} ∪ {OUT}. This is an outer bound that holds every accommodation coefficient in [0, 1]. | conservation; bounding branch (T_g is an input, the neutral energy balance is not solved: MF-01) | LC-15, CC-08 |
| GAP-02 | Atom formation energy had no loss channel (REGISTERED_PRESSURE) or no γ (FLOW_BALANCE) | Class A = ½ D0 per atom created (registered D0, IN-25). FLOW_BALANCE: set by the solved atom balance of each γ member. REGISTERED_PRESSURE: vertex set {WALL[m]} ∪ {OUT}. Fragment excess E_r − ΔE_form → class X. No registered D0 → partition `INCOMPLETE_EVIDENCE` (FC-29). | conservation; registered D0; bounding branch | LC-15, CC-07 v2, FC-29 |
| GAP-03 | CARRIED_OUT had no split between the open ends | Proportional to A_j τ_j (the EQ-02 effusion terms) when every τ_j is registered. Otherwise the vertex pair OUT[UP] / OUT[DOWN]. | registered effusion form; bounding pair | LC-15 |
| GAP-04 | Per-species σ_i gave per-species h, but EQ-08/09 had one h per surface | λ_i,s = 1/Σ_k n_k σ_s,k. Three unweighted members: H-MS (per-species h; electron edge density n_e,j = Σ Z_s h_j,s n_i,s), H-LO (common h at min λ) and H-HI (common h at max λ). All three equal v1 for one ion species. No nominal member. | definition of the collision probability; sheath-edge quasi-neutrality; monotone h(λ) bounding pair | LC-14, FC-28 |
| GAP-05 | CC-03 "relative to max \|I_j\|" degenerates when all surfaces float | I_scale = max_j e A_j max(Σ Z Γ_i, Γ_e): the magnitude of the summed terms, which is the v1 TOL-SOLVE convention. Tolerance value unchanged. INT-16 adopted in IN-24. | numerical / dimensional consistency | LC-16 |

The v1 implementation's withholding reasons for these items are retired. One gate remains: IN-25 (D0 registration).

**Approved interpretations (A9.31 sec. 9).**
- **INT-16.** With registered tables the T_e scan ends at T_e,end = min over the required tables of ⅔ max_mean_energy.
  That end is a scan node and is reported. Nothing is evaluated beyond a table's validity.
- **INT-17.** E_form,ref(ion) is the least-energy registered route. Each event keeps its route id. The route excess
  E_r − ΔE_form ≥ 0 is booked in class X and reported per route (LC-20: the N²⁺ excess is 1.5e-4 eV per direct event).
- **INT-18.** Reused-table representations live under `data/chemistry/icp/xs/`, each with its capture id, builder,
  source and table sha256 and provenance.

## 2. Energy disposition (operational EQ-16)

| id | rule |
|---|---|
| ED-01 | Classes. **ION / ELEC**: per-surface charged-particle energy L_j, and the ion formation energy F_j released where ions neutralize. Both are computed. **X**: electronic excitation, fragment excess, INT-17 route excess. **N**: elastic recoil, vibrational, rotational, and the (1 − β) share of recombination energy. **A**: atom formation energy. |
| ED-02 | Destinations. RAD → `Q_icp_radiation_W` (class X only). WALL[m] → `Q_icp_plasma_wall_W` on the walls of material m. OUT → the outflow keys. The electron-sink surface takes its share inside `Q_icp_extraction_W`. |
| ED-03 | A sourced disposition is used as sourced. An UNRESOLVED channel takes {RAD} ∪ {WALL[m]} ∪ {OUT}. This widens the v1 / AIR-EXC-12 pair by CARRIED_OUT, the quench-probability-0 limit. It is stricter, never weaker. |
| ED-04 | WALL energy is spread ∝ c_j A_j when every class coefficient is sourced. Otherwise it goes by the per-material vertex WALL[m], area-weighted inside m. Inside one material that is exact under the 0-D uniform isotropic neutral distribution (MF-03). |
| ED-05 | OUT split ∝ A_j τ_j, or the OUT[UP] / OUT[DOWN] vertex pair (GAP-03). |
| ED-06 / 07 | Class A: from the solved atom balance (FLOW_BALANCE), or by vertices (REGISTERED_PRESSURE). β is sourced or taken from {0, 1}. |
| ED-08 | Scenario members. Solve members are chemistry variants × γ vertices × H members. Partition members are X × N × A × β × end-split vertices. They are unweighted, never averaged and never narrowed. Each closes exactly (CC-05 v2, CC-08) and carries a `scenario_member_id`. For every key and every IN-10 node the producer flags the members with the extreme load. The keys are linear in the class allocations, so the extremes lie on these vertices. |
| ED-09 | AIR-NL-01 keeps neutrals at T_g in the particle balance. The fragment energy taken from the electrons is still allocated (class X), never dropped. |

Model-form limitations: MF-01 (T_g input), MF-02 (individual Bohm speeds in a multi-ion plasma, VER-21), MF-03
(uniform isotropic neutrals), MF-04 (uniform-density wall flux at large γ, VER-19), MF-05 (Hall-ON current-free plume
and cathode-common topology).

## 3. Replaced, added and retired items

**Equations.** The full v2 text is in the JSON `replaced_items` / `added_items`.
- **EQ-02.** Gains the PF-01 and PF-02 terms. Γ_in comes only from an admitted conductance / feed model, and the inflow
  fraction f_in is retired (OQ-NPICP-14).
- **EQ-05, EQ-08, EQ-09, EQ-22.** GAP-04.
- **EQ-15.** Plane-explicit bus quantities. η_bias is retired: the slot efficiency belongs to the bus ledger.
- **EQ-16.** Five closures: RF-S, RF, PL, B, S. Per surface Q_j^kin = L_j + C_j exactly; total surface heat Q_j = L_j + F_j + W_j + C_j ≥ 0.
- **EQ-18.** GAP-02 and INT-17.
- **EQ-19.** ω_ce/ν_m and r_ce/R, with v̄_⊥ = (π e T_e / 2 m_e)^½ as the definition.
- **EQ-20.** λ_D/min(R, L), λ_D/R and s_j/R. s_j is NOT_EVALUATED until VER-22 clears.

**Sign convention SG-01** (A9.31 sec. 7).
- Definitions: I_j is the net conventional current from the plasma into surface j. V_j and φ_p are measured against the
  registered reference.
- The terms:
  - L_j = e A_j [Γ_e,j (2T_e + max(0, φ_p − V_j)) + Σ Z Γ_i,s,j T_e/2] ≥ 0;
  - C_j = I_j (φ_p − V_j), signed;
  - L_j + C_j = e A_j [Γ_e,j (2T_e + max(0, V_j − φ_p)) + Σ Z Γ_i,s,j (T_e/2 + max(0, φ_p − V_j))] ≥ 0.
- Σ_j C_j = −Σ_j I_j V_j, because Σ_j I_j = 0.
- On floating surfaces and open ends, C_j = 0.
- LC-17 checks this against the independent closed form to 1e-12.

**Inputs.**
- **IN-10 (OQ-NPICP-12).** The volume mode `ASSUMED_GEOMETRIC_TUBE` is a declared unvalidated assumption and is flagged on
  every output. A `REGISTERED_EFFECTIVE` record supersedes it. Requesting the tube where such a record exists is
  MODEL_ERROR (DOM-16). The surface → node map is:
  - module walls → N_VESSEL / N_ANTENNA / N_MOUNT / N_COLLECTOR / N_HOUSING;
  - electron collector → EXPORT;
  - upstream open end → RX-H1-FACE;
  - downstream open end → EXPORT;
  - the v1 wall mapping to H1_FACES is retired.
- **IN-12 (OQ-NPICP-14).** Validation uses measured p_ICP, which is determining. A validation point without it is
  NOT_EVALUATED (VC-07, DOM-15). Flight FLOW_BALANCE is allowed only with an admitted upstream conductance / feed model
  (DOM-14).
- **IN-13.** PF-02.
- **IN-18.** γ, β, quench probability and α_E per (species, material). Each is sourced or taken from the vertex set {0, 1}.
- **IN-19.** η_RF is defined at the generator DC input. η_bias is retired, and a registration carrying it is MODEL_ERROR.
- **IN-23.** ED-03.
- **IN-24.** INT-16, plus the v1 implementation's numerical settings, now registered.
- **Added.** IN-25 (D0), IN-26 (electrode supply identity: ICP_COLLECTOR_BIAS, GROUND_FACILITY_ONLY or
  HALL_DISCHARGE_LOOP) and IN-27 (frozen calibration / validation partition record).

**Domain checks.**
- **DOM-06 (OQ-NPICP-03).**
  - B_ICP,max absent → INCOMPLETE_EVIDENCE.
  - Registered 0 → in domain.
  - B > 0 → both diagnostic ratios are reported, labelled `DIAGNOSTIC_UNMAGNETIZED_SOLVE`. Every plasma, capacity and
    partition output stays INCOMPLETE_EVIDENCE until a sourced criterion is registered.
  - No threshold is set.
- **DOM-07 (OQ-NPICP-09).** The ratios are reported only, with no threshold.
- **Added.** DOM-14..DOM-18.

**Conservation checks.** CC-03 (GAP-05), CC-05, CC-06 and CC-07 are replaced. CC-08 (disposition closure per member) is added.

**Tests.** LC-12..LC-20 and FC-17..FC-30 are added. FC-14 and FC-16 are replaced. The full assertions are in the JSON.

**Retired.**
- `P_icp_bus_W`, which mixed planes, is replaced by `P_icp_slot_load_sum_W`: a closure reference that is never a bus draw.
- `η_bias` and `Q_icp_bias_supply_loss_W`: the bias supply's conversion loss is the bus ledger's P_loss.
- `Q_icp_rf_generator_loss_W` is split into `Q_icp_rf_conversion_loss_W` and `P_icp_rf_reflected_W`. Each is booked once.
- f_in.
- The v1 withholding reasons.

## 4. IF-ICP-THERMAL-v2 (provider side; the consumer is NP-THERMAL-CATHODELESS prereg v2, with an identical table)

**Scope.**
- Applies to CFG-CAP-OFF and to synthetic / parametric cases.
- A CFG-FLIGHT-HALL-ON record is NOT_EVALUATED until CPL-HALL-ON may execute and its coupling keys have a registered
  consumer version.
- It replaces both versions of the label IF-ICP-THERMAL-v1, which stays immutable history.

**Energy-source rule.** Each watt enters through the interface of the supply that powers it, and only once:
- RF chain → TK-01..TK-04 and TK-06..TK-11;
- matching actuator → TK-05;
- electrode-bias supply → TK-12, TK-13;
- Hall discharge → never here;
- PPU supply conversion loss → the bus ledger's P_loss, never here.

| id | key | role | plane | powered by | sign | receiver |
|---|---|---|---|---|---|---|
| TK-R1 | `P_icp_slot_load_sum_W` | REFERENCE | LOAD_PLANE_SUM | - | >= 0 | none (closure reference IFI2-07, CONS-I3) |
| TK-R2 | `P_icp_rf_source_DC_W` | REFERENCE | LOAD (icp_rf_source) | RF_SOURCE | >= 0 | none (closure reference IFI2-03) |
| TK-R3 | `P_icp_rf_forward_W` | REFERENCE | RF_FORWARD | RF_SOURCE | >= 0 | none (closure reference IFI2-03 / IFI2-04) |
| TK-R4 | `P_icp_abs_W` | REFERENCE | PLASMA | RF_SOURCE | >= 0 | none (closure reference IFI2-04 / IFI2-05) |
| TK-R5 | `P_icp_collector_bias_W` | REFERENCE | LOAD (icp_collector_bias) | ICP_BIAS_SUPPLY (+ GROUND_FACILITY_ONLY supplies in a bench case, flagged) | >= 0 (a sinking supply is OUT_OF_DOMAIN, BUS2-08) | none (closure reference IFI2-06) |
| TK-01 | `Q_icp_rf_conversion_loss_W` | BOOKED | inside the RF source (load side of the slot plane) | RF_SOURCE | >= 0 | B_PPU_RF sub-account RF_SOURCE (or a registered electronics node) |
| TK-02 | `P_icp_rf_reflected_W` | BOOKED | RF_REFLECTED | RF_SOURCE | >= 0 | B_PPU_RF sub-account RF_SOURCE (or a registered electronics node) |
| TK-03 | `Q_icp_line_W` | BOOKED_OR_DEPOSITED | RF line | RF_SOURCE | >= 0 | B_PPU_RF sub-account RF_CHAIN, or N_MATCH for a registered co-located segment |
| TK-04 | `Q_icp_match_W` | BOOKED_OR_DEPOSITED | RF match | RF_SOURCE | >= 0 | N_MATCH iff match_colocated (ICD ICP-13), else B_PPU_RF sub-account RF_CHAIN |
| TK-05 | `P_icp_matching_DC_W` | BOOKED_OR_DEPOSITED | LOAD (icp_matching_network) | ICP_MATCH_ACTUATOR | >= 0 | N_MATCH iff match_colocated, else B_PPU_RF sub-account RF_CHAIN |
| TK-06 | `Q_icp_coil_ohmic_W` | DEPOSITED | RP-ANT | RF_SOURCE | >= 0 | registered conductor split over {N_ANTENNA, N_COLLECTOR, N_HOUSING, N_MOUNT}, weights summing to 1 (a registration may state N_ANTENNA 1.0 with its evidence); unregistered -> INCOMPLETE_EVIDENCE on both sides (no default split) |
| TK-07 | `Q_icp_plasma_wall_W` | DEPOSITED | PLASMA -> surfaces | RF_SOURCE | >= 0 | producer per-surface partition over the IN-10 v2 surface -> node map {N_VESSEL, N_ANTENNA (if exposed), N_MOUNT, N_COLLECTOR, N_HOUSING}; always emitted with the key |
| TK-08 | `Q_icp_radiation_W` | DEPOSITED_OR_EXPORTED | PLASMA | RF_SOURCE | >= 0 | consumer-registered partition f_rad over ICP nodes, H-1 pole faces and EXPORT (unchanged from v1 IK-05) |
| TK-09 | `Q_icp_extraction_W` | EXPORTED | PLASMA -> electron sink | RF_SOURCE | >= 0 | EXPORT |
| TK-10 | `Q_icp_outflow_upstream_W` | DEPOSITED_OR_EXPORTED | PLASMA -> OPEN_UPSTREAM | RF_SOURCE | >= 0 | RX-H1-FACE: registered H-1-facing receiver interface (consumer partition f_up) |
| TK-11 | `Q_icp_outflow_downstream_W` | EXPORTED | PLASMA -> OPEN_DOWNSTREAM | RF_SOURCE | >= 0 | EXPORT (never internal heat) |
| TK-12 | `Q_icp_bias_collector_W` | DEPOSITED | bias circuit -> surfaces | ICP_BIAS_SUPPLY | signed (per-surface Q_j check IFI2-08) | N_COLLECTOR (producer per-surface partition; another bias-connected module surface only through its IN-10 v2 node) |
| TK-13 | `Q_icp_bias_export_W` | EXPORTED | bias circuit -> electron sink | ICP_BIAS_SUPPLY | signed | EXPORT |
| TK-14 | `P_icp_flow_control_W` | VARIANT | LOAD (flow_control_icp_feed) | ICP_FEED_VALVE_DRIVER | >= 0 | installed variant -> INCOMPLETE_EVIDENCE until its receiver node is registered |
| TK-15 | `P_icp_assist_magnet_W` | VARIANT | LOAD (icp_assist_magnet) | ICP_ASSIST_MAGNET_SUPPLY | >= 0 | installed variant -> OUT_OF_DOMAIN (thermal D-05; NP-ICP DOM-06) |

**Closures.** The producer meets them to 1e-10 (CC-05 / CC-06 v2). The consumer checks them to ε_if.

| id | identity |
|---|---|
| IFI2-03 RF-S | `P_icp_rf_source_DC_W` = `Q_icp_rf_conversion_loss_W` + `P_icp_rf_forward_W` |
| IFI2-04 RF | `P_icp_rf_forward_W` = `P_icp_rf_reflected_W` + `Q_icp_line_W` + `Q_icp_match_W` + `Q_icp_coil_ohmic_W` + `P_icp_abs_W` |
| IFI2-05 PL | `P_icp_abs_W` = `Q_icp_plasma_wall_W` + `Q_icp_radiation_W` + `Q_icp_extraction_W` + `Q_icp_outflow_upstream_W` + `Q_icp_outflow_downstream_W` |
| IFI2-06 B | `P_icp_collector_bias_W` = `Q_icp_bias_collector_W` + `Q_icp_bias_export_W` |
| IFI2-07 S | `P_icp_slot_load_sum_W` = `P_icp_rf_source_DC_W` + `P_icp_matching_DC_W` + `P_icp_collector_bias_W` (+ installed variants) |
| CONS-I3 | `P_icp_slot_load_sum_W` = sum of TK-01..TK-13. Every watt of the ICP slot loads has exactly one destination class: a node, RX-H1-FACE, EXPORT or B_PPU_RF. None is a remainder. |

**B_PPU_RF booking.**
- B_PPU_RF receives electronics dissipation only, booked per key:
  - sub-account RF_SOURCE = TK-01 + TK-02;
  - sub-account RF_CHAIN = TK-03 (unless co-located) + TK-04 and TK-05 (unless `match_colocated`).
- The true PPU conversion loss of each ICP slot is the bus ledger's `P_loss_W`. CONS-L1 counts it as supply loss outside
  the account.
- The v1 consumer remainder `Q_icp_boundary_W` (IK-07) is retired.

**Per-surface data.** The record carries L_j, F_j, W_j and C_j, the surface → node map, and the partitions of TK-07 and
TK-12 by node. That lets the consumer check that every node's ICP total is ≥ 0, which matters because TK-12 is signed.

**Scenario members.** There is one record per ED-08 member.

**Status today:** NOT_EVALUATED. The key contract is fixed now.

## 5. IF-ICP-BUS-v2 (A9.31 sec. 8; needed to fix the SC-WP-05 plane finding)

**Target boundary.** `bus_power_boundary_a9_v2`. The A5-era v1 boundary is not reopened.

**The mismatch it fixes.**
- The boundary ledger computes P_bus = Σ P_W / (η_slot η_front_end) itself, from slot loads at their load planes.
- The `icp_collector_bias` load plane is the bias-supply **output**.
- v1 `P_icp_bus_W` added P_bias/η_bias, a supply-input value, to the RF and match load-plane values. NP-THERMAL then read
  that sum as the spacecraft-DC demand.
- v2 emits load-plane values only.

| id | key | plane | bus_power_boundary_a9_v2 slot | plane definition | producer form |
|---|---|---|---|---|---|
| BK-01 | `P_icp_rf_source_DC_W` | LOAD | icp_rf_source (INSTALLED) | 13.56 MHz RF generator DC input terminals (bus_power_boundary_a9_v2 rf_power_planes 'generator_dc_input', crosses_bus_boundary true: the ledger load of slot icp_rf_source) | (P_fwd - P_refl) / eta_RF, eta_RF registered at this plane (IN-19 v2) |
| BK-02 | `P_icp_matching_DC_W` | LOAD | icp_matching_network (INSTALLED) | DC input of the matching network's tuning actuators / controller (0 W explicit for a fixed passive match) | registered input echoed (IN-19 v2) |
| BK-03 | `P_icp_collector_bias_W` | LOAD | icp_collector_bias (INSTALLED) | electron-extraction collector / bias supply OUTPUT (V_bias x I_collector), the slot's load plane; the supply's conversion efficiency is the ledger's own efficiency record for this slot | -sum_j I_j V_j over the surfaces of the registered electrode supplies (EQ-15 v2); a bus value only without a GROUND_FACILITY_ONLY supply (BUS2-04); no eta applied by NP-ICP |
| BK-04 | `P_icp_assist_magnet_W` | LOAD | icp_assist_magnet (VARIANT_ONLY (first build unmagnetized: NOT_INSTALLED, exact 0 record)) | ICP assist-magnet coil terminals | registered input echoed only in a declared variant |
| BK-05 | `P_icp_flow_control_W` | LOAD | flow_control_icp_feed (VARIANT_ONLY (G-REUSE: NOT_INSTALLED, exact 0 record)) | dedicated ICP gas-feed valve / flow-controller driver outputs | registered input echoed only in a declared G-ATM / G-XE variant |
| BK-06 | `P_icp_slot_load_sum_W` | LOAD_PLANE_SUM | none (-) | sum of BK-01..BK-05 load-plane values; a reference for the thermal closure, NEVER a bus draw | sum |
| BK-07 | `P_icp_rf_forward_W` | RF_FORWARD | none (-) | rf_power_planes 'forward' (measurement quantity, crosses_bus_boundary false) | CM-CAL / CM-PRED only; NOT_EVALUATED in CM-ABS |
| BK-08 | `P_icp_rf_reflected_W` | RF_REFLECTED | none (-) | rf_power_planes 'reflected' (measurement quantity) | as BK-07 |
| BK-09 | `P_icp_delivered_W` | RF_DELIVERED | none (-) | rf_power_planes 'delivered_to_load' at RP-ANT (measurement quantity, <= forward - reflected) | EQ-12 P_delivered |
| BK-10 | `Q_icp_rf_conversion_loss_W` | INSIDE_LOAD | none (-) | generator DC-to-RF conversion loss, downstream of the icp_rf_source load plane (not a ledger P_loss) | BK-01 - BK-07 |

| id | rule |
|---|---|
| BUS2-01 | Every key has a plane. Only LOAD keys map to slots, one key per slot. |
| BUS2-02 | NP-ICP emits no SUPPLY_INPUT or BUS value: no P_W/η_slot, P_bus_W, P_loss_W, η_front_end or P_bus,1ms,max. Those belong to the admitted bus ledger. |
| BUS2-03 | η_RF sits at the generator DC input, which is internal to the slot load. η_slot is the supply path that feeds that plane. No efficiency is applied twice. |
| BUS2-04 | The flight ledger consumes CFG-FLIGHT-HALL-ON records only. CFG-CAP-OFF records are bench / parametric. A facility supply or laboratory generator is `GROUND_FACILITY_ONLY` and is never spacecraft bus power. |
| BUS2-05 | Flight conventional cathode heater / keeper: **NONE**. There is no key for c1_heater, c1_keeper, c1_common_tie or filter_getter. |
| BUS2-06 | Physical loads only. The RFP 1.5 kW value is never read: it stays in assessment. |
| BUS2-07 | The variant slots are emitted as full NOT_INSTALLED records (exactly 0) unless a declared variant installs them. |
| BUS2-08 | P_icp_collector_bias_W < 0 → OUT_OF_DOMAIN, unless a bidirectional supply is registered. |
| BUS2-09 | Steady state only. P_bus,1ms,max comes from the ledger's own registered evidence. |

**Consumer side.**
- `abep_subsystems::power::icp_bus` is admitted, reads IF-ICP-BUS-v1, and its KEY_MAP is already at these load planes.
  The v1 path stays unchanged.
- The power lane adds a v2 path alongside it. That path:
  - accepts interface id `IF-ICP-BUS-v2` and checks the target boundary;
  - reads the same five slot keys;
  - treats `P_icp_bus_W` as MODEL_ERROR;
  - takes only CFG-FLIGHT-HALL-ON records into the flight ledger;
  - builds the CONS-L1 ICP account at Plane::Load from the IF-ICP-THERMAL-v2 keys (LC-18).

**Status today:** NOT_EVALUATED.

## 6. CPL-HALL-ON-v1 — Hall-ON neutralization coupling (OQ-NPICP-11; preregistered, execution gated)

| id | rule |
|---|---|
| CPL-HON-01 | **Gate.** Execution needs an ADMITTED HallThruster.jl member (never a screening candidate) and a design-specific map point at the pinned commit. Until then CFG-FLIGHT-HALL-ON = NOT_EVALUATED (`CREDIBLE_HALL_TRANSPORT_SET_EMPTY`), asserted by FC-03 and FC-20. |
| CPL-HON-02 | **Inputs, none defaulted.** HI-01 I_d (`discharge_current_A`); HI-02 I_beam (`ion_current_A`); HI-03 V_d and magnets (map axes); HI-04 per-species exit neutral flux and its transfer to the ICP inlet (**no producer**); HI-05 beam / CEX ions at the ICP (**no producer**, needs a registered plume model); HI-06 plume potential at the sink (**no producer**); HI-07 B in the ICP (IN-15, DOM-06); HI-08 the discharge-circuit return topology (registered ICD record). |
| CPL-HON-03 | With the registered cathode-common topology, Kirchhoff on the discharge loop gives I_e,emit = I_d (MF-05). A registered extra return path adds its registered current. |
| CPL-HON-04 | V_coupling is the root of I_e,extracted(V_sink) = I_e,emit. Until the extraction-boundary law (VER-24) clears, the model reports only the saturation upper bound as `I_e_neutralization_available_A`, and V_coupling is NOT_EVALUATED. If the demand exceeds the bound, the raw state is `DEMAND_ABOVE_EXTRACTION_UPPER_BOUND`: a physics fact, never a verdict. |
| CPL-HON-05 | The orchestrator owns the Hall ↔ ICP fixed point: \|ΔV\| ≤ 1e-6 V, current balance ≤ 1e-10, at most 100 iterations, else MODEL_ERROR. Until VER-23 clears (how the pinned HallThruster.jl takes the coupling potential), coupled outputs are INCOMPLETE_EVIDENCE. |
| CPL-HON-06 | G-REUSE in flight: the ICP inflow is the Hall-exhaust neutral flux through an admitted transfer model. No inflow fraction is used. |
| CPL-HON-07 | Hall ions reaching ICP surfaces add to EQ-10. Their arrival energy is Hall-powered (HK-09). Their sheath energy is circuit energy (CPL-HON-08). |
| CPL-HON-08 | **Attribution.** In Hall-ON the electrode circuit is powered jointly by the ICP bias supply and the Hall discharge loop. A per-surface supply split of C_j is not identifiable, because with Σ I_j = 0 any reassignment of φ_p Σ_S I_j between the supplies conserves energy. So no split is made. Reported: the terminal energies `P_icp_collector_bias_W` and `P_cpl_hall_loop_at_icp_W`, and the joint deposition `Q_cpl_hallon_circuit_by_surface_W` / `Q_cpl_hallon_circuit_export_W`, which sum to the two terminal energies. These keys are never inside an IF-ICP-THERMAL-v2 key (FC-16 v2 keeps v1 FC-16). Before execution, a matched consumer version registers them once, defines HK-08 so that nothing is carried twice, and adds a joint CONS-L1 account. |
| CPL-HON-09 / 10 / 11 | Outputs: the pair (I_e, I_d) goes to assessment and no ratio is formed. Hall-ON bench records validate V_coupling and the current balance; they are never I_e,cap points. No beam, plume, transfer or coupling parameter is invented. |

**Status today:** NOT_EVALUATED. The credible set is EMPTY, HI-04..HI-06 have no producer, and VER-23 and VER-24 are open.

## 7. Assessment use, chemistry screen, validation (A9.31 sec. 10)

**Assessment use.**

| id | rule |
|---|---|
| AS-01 | Raw output gives I_e,cap with its envelope, `validation_status` and `validation_cell_id`. It forms no ratio, margin, HC id, threshold or RFP label. |
| AS-02 | OQ-NPICP-02: a model I_e,cap enters HC-05 only inside a VALIDATED_BENCH cell. A VERIFIED value alone never satisfies HC-05; otherwise HC-05 is NOT_EVALUATED (`MODEL_NOT_VALIDATED_IN_DOMAIN`). |
| AS-03 | A measured I_e,cap supersedes the model at the measured point. |
| AS-04 | M_n is formed only in abep-assess. A Hall-ON value is never an I_e,cap point. |
| AS-05 | The 1.5 kW limit is assessment-only. |

**Chemistry screen (CS-01..CS-06, OQ-NPICP-04).**
- CA-ICP-v1 is used only as a screening convention on D-CHEM.
- No Hall verdict transfers.
- Every ICP process class is evaluated per composition / design state.
- An UNBOUNDED_OMISSION blocks chemistry admission for its mode: its outputs are INCOMPLETE_EVIDENCE (FC-25).
- CA-ICP-v1 has not been run (NOT_RUN today).

**Validation.**
- **VC-03.** r_u is reported. There is no informativeness threshold.
- **VC-06 (OQ-NPICP-07 / -13).** A partition record (IN-27) is frozen before any value is examined. It lists:
  - the planned record ids and operating points, each assigned to CAL or VAL;
  - the measurands calibrated and the measurands validated;
  - the frozen custody list.

  Every repeat of a planned operating point stays in one partition. Repeats are never split randomly or after results.
- **VC-07.** Measured p_ICP is determining.
- **VC-08.** No CM-CAL result becomes VALIDATED_BENCH before its held-out set passes.

## 8. Owner items, conflicts, not evaluated today

**Owner items.**
- OQ-NPICP-01..04 and 06..15 are resolved by A9.30 / A9.31. Each is mapped to its fields in `owner_rulings_applied`.
- OQ-NPICP-05 (Xe / Ar sources) stays open.

**Conflicts.**

| id | handling |
|---|---|
| CONF-11 | Resolved by IF-ICP-THERMAL-v2 and NP-THERMAL v2. |
| CONF-12 | The admitted consumers (`power::icp_bus`, `system_ledger::accounts_from_thermal`) still read the v1 interfaces. v2 consumer paths are added additively by the implementing lanes. |
| CONF-13 | The AIR-EXC-12 pair is widened by v2. That is stricter, and the chemistry contract is not edited. |
| CONF-14 | The registry's CV-03 sets neutral formation energy to 0 as a check reference. The partition uses the registered D0. |
| CONF-15 | The coil-loss split must now be registered on both sides. There is no default to N_ANTENNA. |
| CONF-16 | B > 0 keeps every physics output INCOMPLETE_EVIDENCE; only the two diagnostic ratios are added. |

**Not evaluated today.** NE-01..NE-14 are in the JSON. Flight I_e,cap, AIR, Xe, Ar, EM-N2, Hall-ON, bus, thermal values,
magnetized cells, validation, u_model_form and flight FLOW_BALANCE are all NOT_EVALUATED or INCOMPLETE_EVIDENCE, each
with its reason.

**Verify items added.**
- VER-19: wall loss at large γ (from memory; not used).
- VER-20: non-isothermal transmission reciprocity.
- VER-21: multi-ion Bohm speeds.
- VER-22: Child-law sheath width.
- VER-23: the HallThruster.jl coupling potential.
- VER-24: the extraction-boundary law.
- VER-25: ε0.

Acquisition is lawful only (OQ-NPICP-10).

## 9. Admission

**VERIFIED** requires:
- this lock;
- every inherited and added LC / CC / NV / FC item passing under `cargo test --workspace --locked`;
- abep-chem staying admitted;
- verify addenda on the admitted paths;
- the matched consumers: NP-THERMAL v2 with the identical IF-ICP-THERMAL-v2 table, and the power-lane IF-ICP-BUS-v2
  path passing LC-18;
- an admission record.

Every output stays NOT_VALIDATED until a cell reaches VALIDATED_BENCH. Final SIMULATION_COMPLETE also needs CPL-HALL-ON
executed on an admitted member.

## 10. Scope traceability (A9.31 secs. 7-10)

The JSON `scope_traceability` quotes every bullet of A9.31 secs. 7, 8, 9 and 10 (S7-01..S7-10, S8-01..S8-06,
S9-01..S9-10, S10-02a..S10-15) and of A9.30 sec. 5. It maps each one to field ids. Summary:

| A9.31 | fields |
|---|---|
| sec. 7 matched thermal v2, keys, Q_j = L_j + C_j, mapping, no loss / no double count | IF-ICP-THERMAL-v2 (TK-R1..TK-15), SG-01, EQ-16 v2, CONS-I3, b_ppu_rf_booking, CC-05 / CC-06 / CC-08, retired_items, NP-THERMAL v2 |
| sec. 8 bus_power_boundary_a9_v2, matched bus v2, no flight cathode load, physical loads, 1.5 kW assessment-only | IF-ICP-BUS-v2 (BK-01..BK-10, BUS2-01..09), AS-05, FC-30 |
| sec. 9 PF-01, PF-02, GAP-01..05, bases, bounding / INCOMPLETE_EVIDENCE, no convenience split, INT-16/17/18 | resolutions, energy_disposition ED-01..09, EQ-02 / 05 / 08 / 09 / 18 / 22, IN-24 / 25, CC-03 / 07 / 08, LC-12..16 / 20, FC-17 / 18 / 28 / 29, approved_interpretations |
| sec. 10 OQ-NPICP-02, 03, 04, 07, 08, 09, 10, 11, 12, 13, 14, 15 | AS-02 / 03; DOM-06 / EQ-19; CS-01..06; VC-06 / 08, IN-27; IF-ICP-THERMAL-v2; DOM-07 / EQ-20; verify_gate_v2; CPL-HALL-ON-v1; IN-10 / DOM-16; VC-03; IN-12 / VC-07 / DOM-14 / 15 |
