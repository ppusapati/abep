# P4: RF/ICP neutralizer, v2 (submission-safe statement)

Supersedes `P4_rf_icp_neutralizer.md` (v1, kept unchanged) for the A9.39 phase (PHYSICS ARCHITECTURE CLOSED — DETAILED
DESIGN / EM VERIFICATION OPEN).

**Engineering evidence:**
- bench design `docs/closure/icp_bench/icp_bench_design_v1.json` (sha256
  `48f210b68c87070d48b6b3c19ff6ce42f265d0439ca259fb7d36e1bf361090f2`) and page `ICP_BENCH_DESIGN_v1.md`;
- test plan `docs/closure/icp_bench/icp_bench_test_plan_v1.json` (sha256
  `31f8b6ca7bb65691b3bbd8140945f2e36e983fd29658e2016b18227f0accfbf1`, lock `icp_bench_test_plan_lock_v1.json`);
- analysis closure `docs/closure/icp/icp_closure_v1.json` (sha256 `3ddf55039b4f…`) and collector window
  `icp_collector_window_a1_v1.json` (sha256 `c414954b13c7…`), both unchanged.

**Internal closure state: FROZEN FOR EM.** The neutralizer design baseline, its bench configuration, the measurement plan
and the pass / fail logic are frozen on registered evidence. RF coupling efficiency, electron-current capacity, collector
ion energy and the neutralization margin are verification-by-test items on the bench and the engineering model. The
analysis-only capacity prediction stays BLOCKED BY SPECIFIC MISSING EVIDENCE in the v1 record. It is now carried as a
bench-verification item, not as a design blocker. GNG-ICP-01 reads NOT EVALUATED until the owner accepts its criteria.

---

## Proposal text

**Electron source and neutralizer.** The design baseline neutralizes the Hall thruster beam with a cathodeless 13.56 MHz
inductively coupled plasma (RF/ICP) electron source. It is mounted downstream of the Hall thruster exit. The flight
architecture has no conventional hollow cathode. One neutralizer therefore serves both supply modes: ambient atmospheric
propellant (primary) and xenon (required secondary capability for commissioning, restart and contingency operation). The
topology follows a published Hall thruster with a downstream RF/ICP electron source (Takahashi et al., J. Electr.
Propuls. 3:18, 2024). That work is a topology precedent, not a performance basis.

**Design baseline (DBF-1.1):**
- **Topology.** Open-tube coaxial, unmagnetized ICP. The borosilicate-class discharge bore has a 120 mm inner diameter
  and is 150 mm long. It leaves a clear passage for the Hall plume.
- **Antenna and RF chain.** An external helical antenna is driven at 13.56 MHz through an adjustable matching network
  on the neutralizer module. Its thermal design (isolation from the module bracket and a dedicated radiator) is
  verified at engineering-model level. The RF
  chain covers a forward-power envelope up to 500 W at the generator-side reference plane. Component ratings are set
  from the measured antenna impedance map.
- **Collector.** A separately biased, metered C-type ion-collecting electrode, 100 mm long, made of nickel-chromium
  alloy (Inconel 600 primary, Inconel 601 backup), on a floating neutralizer body with a 350 V isolation class.
- **Collector operating principle.** The collector is operated close to its floating potential, so the ion-impact energy
  stays low and sputter erosion over the firing life stays small. The floating-body, separately biased topology lets the
  collector sheath voltage be set independently of the Hall discharge voltage.
- **Gas.** The neutralizer runs on neutral gas leaving the Hall thruster, so it has no dedicated feed. A capped
  dedicated port is retained for the xenon variant.
- **Power.** Neutralizer loads are carried in the propulsion system's 1,350 W internal design allocation, inside the
  < 1,500 W bus limit.

**Functional requirement.** At every operating point of the 12–25 mN thrust range, in both supply modes, the
neutralizer supplies an electron current at least equal to the Hall discharge current, with a verified positive margin.

**Design basis (analysis).**
- A preregistered 0-D global (particle and power balance) model of the ICP is implemented in the project's Rust simulator
  with conservation checks and fail-closed evidence rules. Its registered inputs cover geometry, electrode and bias
  configuration, absorbed-power basis, neutral-pressure range and edge-loss model.
- Energy-conservation bounds show that the RF envelope does not, in principle, limit the required electron current.
- The achievable capacity depends on the RF-to-plasma power-transfer efficiency and on discharge energy losses. Both are
  established by measurement, not assumed. Capacity predictions for air and xenon follow the admission of the
  preregistered plasma-chemistry data sets and are finalized at PDR.

**Bench and engineering-model verification.** The neutralizer bench reproduces the flight module geometry, antenna,
local match, collector and floating-body circuit. It runs on the Hall thruster gas path with the discharge supply
physically disconnected, so the neutralizer alone is measured.
1. **Readiness.** Dielectric-withstand qualification of every isolated path, interlock functional tests, RF cold
   checkout with calorimetric cross-check, and the cold antenna impedance.
2. **Coupling efficiency.** An RF impedance map of the antenna, unlit and lit, at each test gas, power level and
   neutral pressure. It gives the plasma and antenna resistances and the power-transfer efficiency, measured by three
   independent methods.
3. **Electron-current capacity.** The extracted electron current is measured on a dedicated, isolated, instrumented
   electron collector over the bias range. Each point is paired with a matched RF-off record and must close the
   current balance of every return path. Test gases follow a fixed order: argon (engineering only), nitrogen,
   nitrogen–oxygen mixtures (molecular oxygen only), then xenon. Atomic-oxygen effects are covered by a separate
   materials programme.
4. **Collector bias and ion energy.** A retarding-field energy analyser at the collector, together with Langmuir and
   emissive probes, measures the collector ion energy, the electron temperature and the plasma potential. This confirms
   that the near-floating collector operating point keeps the ion energy inside the erosion allowance set by the
   measured sputter yields of the procured alloy. A serialized, replaceable collector tracks recession.
5. **Coupled test.** A coupled Hall thruster + neutralizer test confirms current balance, coupling voltage and stable
   operation at registered Hall operating points.
6. **Neutralization margin.** The margin is formed against the measured maximum Hall discharge current with a
   preregistered one-sided uncertainty rule. A model capacity is used only inside a bench-validated domain cell. The
   ICP go / no-go gate before design lock is fail-closed: it reads NOT EVALUATED until its evidence exists.

Facility requirements follow from the registered neutral-pressure range. They include background-pressure
characterization at base pressure and at two elevated levels, and the source pressure is measured on every record.

**Interfaces.** The RF electronics, matching network and collector-bias supply connect at the spacecraft-side DC boundary
of the propulsion power ledger. The neutralizer thermal loads are carried in the propulsion thermal model. The magnetic
field at the neutralizer, created by the Hall magnetic circuit, is taken from the Hall thruster field analysis and
confirmed by measurement.

---

## Controlled-wording notes (internal; not for the proposal)

- Do not quote an electron-current capacity, an absorbed power, a coupling efficiency, a collector bias or a recession
  value as a design value or acceptance criterion. All of them are bench / EM verification items.
- The internal targets are necessary lower bounds, not predictions: ≥ 0.79 / 1.64 A (air) and ≥ 0.39 / 0.81 A (Xe) at
  12 / 25 mN. The governing target is the measured maximum H-1 discharge current (I_d,max,H1), which is not registered yet.
- The bench planning numbers are not ratings: the antenna-voltage envelope (up to ~14 kV peak at the conservative
  assumed impedance), the pumping-speed table, u(η_p) ≤ 0.02 and the 40 V fine bias range. The P2 map sets the RF
  ratings (owner rule A9.2).
- The match location rests on the DCR-DBF1-003 evaluation (route R-1, co-located and isolated). That evaluation is on
  lane-dcr003-match and was uncommitted when read. Its resolution (WITHDRAWN) is the coordinator's register entry.
- The Xe rate set is not admitted. The remaining steps are listed in `ICP_BENCH_DESIGN_v1.md` sec. 10. HC-05 can be
  evaluated on a measured capacity without it.
- GNG-ICP-01 criteria are an owner item. The test plan only maps the recorder proposal (a)–(c) onto measurable
  criteria C-03 / C-04B / C-08.
