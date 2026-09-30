# A9 FOLLOW-UP OWNER DECISIONS (A9.1) — verbatim record, 2026-09-30

Recorded verbatim from the owner's message of 2026-09-30 (session chat; LaTeX kept as written). Machine-readable companion:
`OD_2026_09_30_A9_1_followup_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

Owner preamble:

The A9 core is now mature enough to move forward. I would not merge to main yet, because A9-04 still has provisional decision-quantity IDs and the five lanes have known PENDING <lane> references. First do a short mechanical integration cleanup, then launch A9-06…09 in parallel, finish A9-10, run the full suite again, and only then merge through the checkpoint PR.

One technical point on startup power: ECSS requires power analysis to include average peak and inrush demands, but it does not prescribe the exact averaging window for our propulsion gate. So the 1 ms window below is an A9 project definition, not an ECSS requirement.

A9 FOLLOW-UP OWNER DECISIONS

These decisions govern the Hall → downstream 13.56 MHz RF/ICP neutralizer investigation after verification of A9-01…A9-05.

Existing immutable A4–A9 history and all prior validation records remain unchanged.

1. HIQ decisions

| ID | Owner decision |
|---|---|
| HIQ-01 | Use hall_c1_reference as the REF-COND reference installation in every block. C1 is the control/fallback and therefore remains the drift/reference anchor. Preserve and report the resulting predecessor asymmetry; do not hide or statistically erase it. |
| HIQ-02 | YES. "Three complete engineering replicates" means three complete balanced replicate sets, i.e. both sequences in each replicate set and therefore at least six blocks before any larger n required by LOCK-2 uncertainty. |
| HIQ-03 | Put the bounded Xe reference/health check at the beginning of the installation, before the N₂ slices and therefore before any O₂-bearing exposure. This prevents O₂ exposure from contaminating the health reference. |
| HIQ-04 | YES. Freeze HI-HOLDOUT-A before the first Hall-on reading on actual H-1, including the Ar engineering reproduction. Freeze the actual held-out condition enumeration after LOCK-1 but before HI-S1. |
| HIQ-05 | NO mandatory Pareto relation. Hard gates determine feasibility. Pareto quantities are reported for engineering comparison only unless a particular Pareto condition is explicitly preregistered at LOCK-1. |
| HIQ-06 | Primary ICP gas mode = G-REUSE: the downstream ICP shall first attempt to operate on Hall exhaust/residual propellant, matching the Takahashi topology. The dedicated ICP gas port remains installed and capped so G-ATM and G-XE can be tested as separately declared contingency variants. Score-bearing N₂/N₂+O₂ comparison uses G-REUSE unless it fails the preregistered ICP-capacity gate. No dedicated Xe is introduced merely to make the ICP work. |
| HIQ-07 | Pure-N₂ hall_icp_neutralizer readings are sequestered for a future Hall-transport preregistration, not inserted into the current Hall-transport validation set. The downstream electron source changes the cathode/electron boundary condition and therefore cannot silently validate the existing transport model. |
| HIQ-08 | YES. Run HI-AR before LOCK-1, after HI-HOLDOUT-A. Engineering findings may refine hardware settings and the ICP recipe subsequently frozen at LOCK-1. Ar readings never enter LOCK-2 uncertainty numbers, architecture decision quantities, or DRDO atmospheric compliance claims. |

ICP gas accounting consequence

For G-REUSE:

\dot m_{\rm ICP,dedicated}=0

because the ICP reuses gas already booked through the Hall atmospheric feed.

Do not count the same atmospheric mass twice.

For a later G-ATM variant:

\dot m_{\rm atmosphere,total} = \dot m_{\rm Hall} + \dot m_{\rm ICP,dedicated}

subject to actual routing.

For G-XE:

\dot m_{\rm ICP,Xe}

is booked explicitly in the Xe ledger under PHASE_TOTAL_FLOW.

⸻

2. UBQ decisions

| ID | Owner decision |
|---|---|
| UBQ-01 | The 1% thrust target is standard relative uncertainty, k = 1, for a sustained reading. Absolute PASS/FAIL gates then use the preregistered one-sided confidence treatment; do not reinterpret 1% as already being k=2 expanded uncertainty. |
| UBQ-02 | Accept the neutralization-margin form: M_n=\frac{I_{e,\mathrm{cap}}}{I_{d,\mathrm{dem}}}-1. Gate on the one-sided lower confidence bound > 0. Any additional design margin is computed/frozen at LOCK-2 according to the LOCK-1 uncertainty rule; do not invent a margin now. |
| UBQ-03 | Accept. A manufacturer's stated ±x bound is treated as rectangular: u=a/\sqrt3 unless its calibration certificate explicitly defines another probability distribution or coverage factor. |
| UBQ-04 | Accept the normalized agreement statistic but freeze k_x = 2 at LOCK-1. S1a determines the uncertainties entering the denominator, not the acceptance threshold. If the coupler-vs-calorimetry check fails, RF-dependent quantities are EXCLUDED_INSTRUMENT until resolved; never reweight whichever instrument looks favorable. |
| UBQ-05 | Both. Pre/post calibration shift enters the uncertainty budget and also has a block-exclusion rule. Freeze the rule form at LOCK-1; LOCK-2 inserts the numerical limit from metrology-only calibration evidence. |
| UBQ-06 | For score-bearing operation, temperature aborts occur at validated continuous-use limit minus 50 K. The 50 K margin therefore remains operationally protected, not merely shown on a drawing while hardware is allowed to run to its material limit. |
| UBQ-07 | Set family-wise α = 0.05 for simultaneous architecture contrasts, using a preregistered multiplicity-control procedure such as Holm. Set one-sided α = 0.05 for each absolute hard-requirement gate. Freeze this at LOCK-1. |
| UBQ-08 | YES. Ar-specific gauge/MFC/RGA calibration is required for HI-AR engineering interpretation. Ar remains engineering-only regardless of calibration quality. |
| UBQ-09 | Use SR-C-MARGIN, not sign-only stopping. A configuration is stopped for inferiority only when its confidence bound crosses the preregistered negative decision margin. The margin rule is frozen at LOCK-1 and its uncertainty-derived numerical value at LOCK-2. |

⸻

3. A9-02 bus-power decisions

OQ-A902-01 — startup transient definition

Freeze the A9 power-gate definition as follows.

Primary RFP/system gate quantity:

P_{\rm bus,1ms,max} = \max_t \left[ \frac{1}{1~{\rm ms}} \int_t^{t+1{\rm ms}} P_{\rm bus}(\tau)d\tau \right].

Requirement:

\boxed{P_{\rm bus,1ms,max}<1500~W}

for startup as well as steady state, unless the official RFP later explicitly provides a different transient exception.

Measurement requirements:

* spacecraft-DC propulsion boundary;
* all required channels synchronized;
* effective measurement bandwidth ≥20 kHz;
* sample rate ≥100 kSa/s per relevant channel or an equivalent direct spacecraft-bus power channel;
* anti-alias filtering documented;
* no step-average may be substituted for this gate.

Also record the unaveraged sampled peak separately for hardware/current/voltage protection analysis. The unaveraged switching-ripple peak is not the 1.5 kW system-power gate.

Report 100 ms and 1 s averages as diagnostic/energy metrics, not as substitutes for the 1 ms gate.

This is an A9 engineering definition pending authoritative RFP wording.

OQ-A902-02 — 300 W common allocation

Accept the proposed composition:

* compressor;
* atmospheric/Xe/ICP flow-control loads;
* filter/getter if active;
* thermal control;
* housekeeping/controls.

The 50 W controls/thermal allowance is inside the 300 W common allocation.

Active cooling beyond the frozen thermal-control allocation and reserved future ports are outside unless explicitly reallocated.

OQ-A902-03 — Hall/ICP sub-allocation

Do not freeze an arbitrary fixed Hall-vs-ICP wattage split.

Instead define at every registered operating condition:

P_{\rm ICP,available} = 1350 - P_{\rm common} - P_{\rm Hall} - P_{\rm other\,active}.

The ICP must demonstrate ICP-45 within this residual budget.

The laboratory 0–500 W RF source is a test capability, not permission for the flight architecture to consume 500 W.

This avoids carrying the old parallel-RF ≤700 W number into a completely different architecture.

OQ-A902-04 — combined flight C1 + ICP installation

NO for the primary A9 flight architecture.

C1 is the ground comparison/control/fallback architecture, not an automatically co-installed flight backup.

A flight variant carrying both complete electron sources would be a new architecture variant requiring its own:

* mass;
* power;
* Xe;
* reliability;
* thermal;
* failure-tree

closure.

Do not burden A9 with it now.

OQ-A902-05 — ICP gas

Primary = G-REUSE.

Book flow_control_icp_feed only when G-ATM or G-XE is actually installed/used.

The capped test port remains in the ICD.

OQ-A902-06 — housekeeping and thermal power path

Route them through the internal propulsion bus by default.

If later PPU/electrical architecture supplies a load directly from spacecraft input, explicitly represent that path in the ledger. No power disappears because it bypasses the 100 V internal rail.

OQ-A902-07

YES.

Report the old 1300 W lower-end allocation as context/sensitivity.

The active A9 internal design check remains:

\boxed{1350~W}

and the hard requirement remains:

\boxed{1500~W}.

⸻

4. A9-02 sequencing questions

Heater TBD treatment

The C1 procedure shall explicitly state heater command/power at every startup step.

Until that stepwise procedure and measured power are available:

\boxed{\text{TBD heater = ON at conservative/worst-case booked power}}

for the bus ledger.

Never obtain a PASS by assuming a TBD heater is off.

Simultaneous peak loads

Accept:

\boxed{\text{at most one peak-class load is commanded to rise per startup step}}

as the baseline sequencing rule.

Steady loads may of course remain on.

If physical hardware later requires two peak-class loads to overlap, that is a registered sequence variant requiring measured transient-power evidence before it can replace the baseline sequence.

⸻

5. ICP-45 electron-current capacity

YES — formal entry condition.

No hall_icp_neutralizer score-bearing point may be taken until the capacity requirement is demonstrated.

Use two steps:

ICP-45A — Ar engineering qualification

Demonstrate electron extraction up to:

I_{e,\rm cap}\ge I_{d,\max}

on Ar as engineering-only evidence.

ICP-45N — N₂ qualification

Repeat electron-current capacity demonstration on N₂ before any score-bearing ICP comparison.

At each current record:

* extracted electron current;
* RF forward/reflected power;
* DC input power;
* collector voltage/current;
* pressure;
* gas state;
* thermal state;
* plasma stability.

The published ~1 A / 200 W Takahashi point remains context only.

Do not scale it to H-1.

I_d,max comes from the actual registered H-1/discharge-supply envelope; do not invent it to unblock ICP sizing.

⸻

6. ICP-46 keeper-pulse isolation

For the C1 300–600 V pulsed keeper circuit:

* upper operating pulse: 600 V;
* minimum design isolation basis: 900 V (1.5× upper operating pulse);
* qualification/hipot test: 1.0 kV DC at representative pressure/gas for the initial H-1/C1 development hardware;
* no flashover/breakdown;
* leakage recorded;
* separately perform the actual 600 V pulse-waveform test.

This applies to:

* keeper lead;
* feedthrough;
* connectors;
* harness;
* isolation to cathode common/module body/facility ground.

It does not replace ICP-44 RF insulation/combined RF+DC stress qualification.

Final flight qualification voltage can be revised upward when the applicable spacecraft insulation standard and final hardware class are frozen, but not downward after seeing test results without a controlled justification.

⸻

7. Additional A9-03 clarifications to prevent future ambiguity

Interface-plane names

Adopt:

* IP-EXIT = H-1 exit;
* IP-NEU = downstream neutralizer datum.

Keep historical IP-DN unchanged.

Effective Hall discharge voltage

For same-condition C1-vs-ICP comparison, the primary controlled electrical quantity shall be:

\boxed{ V_d = V_{\rm anode} - V_{\rm electron-source-reference} }

not merely the discharge-supply terminal setting.

Record supply-terminal voltage and all loop drops as secondary quantities.

This is important because the C1 and ICP electron-source reference potentials can differ.

Matching network location

Baseline: off the moving thrust-stand platform.

Use:

* matched flexible RF coax;
* calibrated cable-loss/S-parameter correction;
* directional coupler/reference plane after the matching network;
* matched sham routing in the C1 configuration.

Move matching hardware onto the platform only if S1a proves the off-platform configuration cannot meet RF-power uncertainty requirements.

Collector material

Do not freeze flight collector material yet.

316L may be used for Ar engineering reproduction if necessary.

Before N₂/O₂ life claims, collector candidates must go through the oxygen/AO coupon programme. The Takahashi stainless-steel sputtering result is a warning, not a material qualification.

⸻

8. OQ-EV decisions

OQ-EV-01

NO author/laboratory data request.

Continue the standing published/lawful-source-only policy unless the owner later explicitly changes it.

OQ-EV-02

Accept the proposed acquisition order:

* P1: LA-01, LA-02, LA-03;
* P2: LA-04, LA-06, LA-07, LA-08;
* P3: LA-05, LA-09.

OQ-EV-03

YES.

Numerical values may be cited/extracted from publisher-served full text that was accessed lawfully without bypass.

Record:

* publisher URL;
* DOI;
* page/figure/table locator;
* access date;
* evidence class.

Do not redistribute or commit the copyrighted PDF where the licence does not permit redistribution.

⸻

9. Repository / execution authorization

Do not merge A9 to main yet

Reason:

* A9-04 still uses provisional A9-01 decision IDs;
* several A9-01…05 references are still marked PENDING <lane>;
* A9-06…09 have not reconciled mass, H2 hardware, Xe and procurement consequences.

Step 1 — immediate core integration repair

Run a short integration lane now limited to:

1. mechanically rename A9-04 decision quantities to the final A9-01 IDs;
2. replace resolved PENDING A9-01…05 cross-references with the actual paths/hashes;
3. update no physics values;
4. update no thresholds;
5. rerun all A9 tests + full suite + golden + integrity.

This must be treated as an integration/reconciliation change, not a new scientific result.

Step 2 — launch in parallel

After that integration repair, authorize:

* A9-06: mass reconciliation;
* A9-07: H2 revisions — external C1, downstream ICP fixture, 50 K thermal protection, revised interfaces;
* A9-08: Xe ledger update;
* A9-09: RFQ/quotation packages.

They may run in parallel where independent.

A9-08 specific instruction

Primary G-REUSE ICP operation has:

m_{\rm Xe,ICP}=0

and no extra dedicated atmospheric feed.

Do not double-count Hall exhaust as ICP propellant.

C1 Xe, XE_REFERENCE, XE_AUGMENTED_PEAK and any explicit G-XE contingency remain separate ledger terms.

A9-09 procurement restriction

RFQs/quotations are authorized.

Purchase orders are not authorized merely because an RFQ lane closes.

Interfaces and H3 procurement gate still control purchases.

Step 3 — A9-10

After A9-06…09:

* reconcile all A9 outputs;
* refresh M16;
* resolve remaining cross-references;
* regenerate consolidated owner-question state;
* run full test/golden/integrity suite;
* verify no immutable historical file changed unexpectedly.

⸻

10. Main-branch strategy

Open a draft checkpoint PR from the execution branch to main now so the diff and CI remain visible.

Do not merge it yet.

Merge only after:

\boxed{ \text{core integration repair} \rightarrow A9\text{-06..09} \rightarrow A9\text{-10} \rightarrow \text{full green CI} }

and final PR review.

This avoids both extremes:

* another very long invisible execution branch;
* merging a knowingly unreconciled A9 halfway through its integration.

⸻

11. Architecture status remains unchanged

A9 remains:

OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE

The current primary hypothesis is:

\boxed{ \text{Hall} \rightarrow \text{downstream 13.56 MHz ICP electron source/neutralizer} }

with Hall-exhaust reuse as the primary ICP gas mode.

Conventional Xe-fed LaB₆ C1 remains the control/fallback until ICP demonstrates:

I_{e,\rm cap}\ge I_{d,\max}

on Ar and N₂,

plus:

* stable Hall operation;
* neutralization;
* <1.35 kW internal design closure;
* <1.5 kW hard power closure;
* thermal closure;
* startup/restart;
* erosion/lifetime evidence.

Passing ICP-45 alone does not retire C1.

The single most important decision in this set is HIQ-06 = G-REUSE. It keeps Professor Umesh/Takahashi's architecture scientifically clean: atmospheric gas enters the Hall stage, the downstream ICP uses that exhaust, and the ICP does not get a hidden separate propellant stream simply to make the architecture work. The published Takahashi proof-of-principle likewise used a single Ar feed through the Hall anode and reused the ejected gas in the ICP.

I would therefore tell Claude to record these owner decisions, perform the short A9-01…05 integration repair immediately, then launch A9-06 through A9-09 in parallel. A9-10 closes the integration, after which the branch can go through the checkpoint PR into main.
