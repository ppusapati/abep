# S3 (BLOCKS A LATER P1 STAGE) OWNER DECISIONS (A9.10) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat), answering group S3 (S3.1–S3.10) of
`docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md`. Machine-readable companion:
`OD_2026_10_01_A9_10_s3_p1_later_stage_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

1. S3.1 — P1Q-02 — REGISTER HARDWARE-DERIVED HALL START-ATTEMPT LIMITS BEFORE P1-S6.
The Hall start-attempt limits shall be pre-registered before the first P1-S6 attempt.
Register:
   * maximum applied `V_d`;
   * discharge-supply current limit;
   * maximum duration of one start attempt;
   * maximum number of attempts/retries;
   * mandatory cool-down/reset condition between attempts, where required.
The registered limits shall be derived from the actual H-1 article, discharge-supply capability, electrical-isolation qualification, thermal limits and interlock settings.
The maximum applied voltage shall not exceed the qualified H-1 operating/isolation envelope. The current limit shall not exceed the lesser of:
   * the safe H-1 hardware limit;
   * the laboratory supply capability; and
   * the 8.33 A stand/supply ceiling.
The 8.33 A value is only an infrastructure ceiling and shall never be interpreted as `I_d,max,H1`.
Attempt duration and retry count shall be established before P1-S6 from the registered thermal/transient protection basis. They shall not be increased after observing an unsuccessful ignition merely to obtain a sustained discharge.
Decision: methodology frozen now; numerical limits registered from the actual hardware before P1-S6.
2. S3.2 — P1Q-03 — DEFINE SUSTAINED HALL DISCHARGE BY A PRE-REGISTERED CURRENT-AND-TIME CRITERION.
A Hall discharge is `SUSTAINED` only when:
   * the discharge supply is enabled and connected;
   * measured `I_d` exceeds a pre-registered threshold above the measured RF-on/plasma-off pickup/noise floor from P1-M-22;
   * the current remains above that threshold continuously for a pre-registered minimum duration;
   * the condition is not merely an ignition spike, capacitive transient, RF pickup or switching artifact; and
   * no protection/interlock condition invalidates the observation.
The current threshold shall be derived from the measured noise/pickup level and its uncertainty. The minimum duration shall be registered before P1-S6 from the DAQ bandwidth and observed start-transient timescale.
Do not choose either value after looking at whether a particular run sustained.
Decision: sustained discharge = current demonstrably above the registered pickup/noise threshold for the registered minimum continuous duration.
3. S3.3 — P1Q-05 — MINIMUM THREE INDEPENDENT RE-IGNITION ATTEMPTS PER CANDIDATE SURFACE POINT.
Require at least three independent re-ignition attempts at each candidate operating point used for the P2 stable-region handoff.
Each attempt must:
   * begin from an extinguished plasma/RF-off state;
   * allow the relevant state variables to return to their registered restart condition;
   * use the same registered operating point;
   * be recorded independently.
All attempts count. Failed or abnormal attempts may not be discarded simply because additional successful attempts were subsequently obtained.
The three-attempt minimum establishes repeatability evidence; it does not by itself create a PASS. P2 handoff still depends on the separately pre-registered ignition-success and stability criteria.
Decision: minimum 3 independent re-ignition attempts per candidate point.
4. S3.4 — P1Q-06 — TEST BOTH MAGNET-OFF AND REGISTERED H-1 MAGNET SETTINGS.
During ICP-only P1-S3 through P1-S5, test:
   * F6 = H-1 magnet OFF as the baseline; and
   * F6 = registered H-1 magnet operating setting(s) representative of the corresponding H-1 condition.
Run the magnet-OFF condition first so that the intrinsic ICP response is established before introducing H-1 fringe-field coupling.
Record the actual coil currents/field-setting IDs for every magnet-on record.
Do not assume the H-1 fringe field has negligible influence on ICP ignition, impedance, electron extraction or collector behavior until measured.
Decision: BOTH, treated explicitly as test factor F6.
5. S3.5 — P1Q-07 — REGISTER `I_d,max,H1` FROM A DEDICATED H-1 CHARACTERIZATION WITH THE CONVENTIONAL C1 REFERENCE SOURCE.
Use a dedicated H-1 characterization campaign with the conventional C1 electron source/neutralizer to establish the maximum discharge current of H-1 independently of the experimental ICP neutralizer.
For the P1 Ar engineering programme:
   * operate H-1 with C1 under the registered HI-AR H-1 operating envelope;
   * characterize the admissible H-1 operating surface;
   * register `I_d,max,H1,Ar` as the maximum measured discharge current inside that qualified envelope;
   * include its registered uncertainty;
   * freeze that value before P1-S7.
P1-S7 ICP-45A in Ar shall use this registered value. It shall not use the 8.33 A stand ceiling.
This Ar value is an engineering qualification reference only. It shall not automatically become the final flight-relevant `I_d,max,H1`. When H-1 is later characterized on the relevant N2/O2/O or delivered VLEO-propellant condition, register a separate flight-relevant `I_d,max,H1` with its own provenance.
The later value does not retroactively alter the historical Ar P1 result.
Decision: H-1 + conventional C1 characterization; Ar engineering value registered before P1-S7, later propellant-specific value registered separately.
6. S3.6 — P1Q-08 — YES.
P1-S0 through P1-S5 belong to the HI-ENG / HI-S1A engineering/module-bench envelope because the Hall discharge remains OFF.
HI-HOLDOUT-A is therefore required immediately before the first actual Hall-on reading, which occurs at P1-S6.
No result obtained during P1-S0 through S5 shall consume or contaminate the Hall-on held-out partition.
Decision: YES — HI-HOLDOUT-A begins at P1-S6, not earlier.
7. S3.7 — P1Q-19 — CHOOSE `REQUIRE_REGISTERED_GE_CHANNEL`.
If the pre-registered `u_I_e` is smaller than the uncertainty obtained by propagation from its actual calibrated measurement channels, the registration is inadmissible.
Do not silently replace it during evaluation with the larger value.
Before the first P1-S7 measured point, the uncertainty registration must satisfy:
`u_I_e,registered >= u(I_e,cap)_channels`
under the registered correlation/covariance treatment.
If this condition is not met, the ICP-45 evaluation is `NOT_EVALUATED_REGISTRATION` until a valid uncertainty registration is created.
The registration may be corrected before data acquisition on the basis of calibration evidence. It shall not be retrospectively changed after seeing the ICP-45 result.
Decision: `REQUIRE_REGISTERED_GE_CHANNEL`.
8. S3.8 — P1Q-24 — USE `k = 2` FOR BOTH P1 AND P2 AND CONFIRM THE FAIL-CLOSED RULE.
Register a single coverage/agreement factor:
`k_loss = 2.0`
for the at-power RF loss-model verification used by both P1 and P2.
Acceptance form:
`|eta_meas - eta_pred| / u_c <= 2`
where `u_c` is the registered combined standard uncertainty for the comparison.
This is also consistent with the already frozen P1 coupler-versus-calorimeter cross-check factor `k_x = 2`.
The same `k_loss = 2` shall be used for the applicable CAL-P2-09/CAL-P2-10 verification; it may not be independently relaxed in P1 or P2.
Confirm the fail-closed interpretation:
Until the at-power loss-model verification passes,
   * `P_delivered` is reported only as the applicable upper bound / unverified-loss quantity;
   * `C_e` derived using delivered RF power remains correspondingly an upper-bound/qualified quantity;
   * small-signal S-parameter characterization alone does not upgrade the loss model to verified at operating power.
A failed at-power verification is investigated; the tolerance is not widened to recover agreement.
Decision: `k = 2.0` for P1 and P2; fail-closed upper-bound rule CONFIRMED.
9. S3.9 — OQ-RFQV2-09 — C1 MAY BE ABSENT DURING P1-S6; KEEP C1 HARDWARE LATER.
P1-S6 does not require C1 to be physically installed merely so that it can be demonstrated to be disconnected.
For P1-S6:
   * C1 may be physically absent;
   * its electrical and gas connections shall therefore also be absent/open and documented;
   * the record shall state `C1_NOT_INSTALLED` rather than pretending that a disconnected C1 exists.
This provides a cleaner topology-control experiment because it removes C1 itself, its keeper/heater wiring, gas plumbing, exposed surfaces and possible unintended electron/current paths from the configuration.
Therefore HE-L10, HE-L11 and HE-L12 do not need to be advanced to P1_NEEDED for P1-S6.
However, C1 will be required for the dedicated H-1 reference characterization defined in S3.5 before an Ar `I_d,max,H1` can be registered for P1-S7. Its procurement/readiness shall therefore be scheduled against that characterization gate, not against P1-S6.
Decision: C1 absent is acceptable for P1-S6; retain C1 as LATER/reference-characterization hardware.
10. S3.10 — OQ-RFQV2-10 — CREATE A SEPARATE H-1 FABRICATION PACKAGE; KEEP DESIGN AND FINAL INTEGRATION IN-HOUSE.
Do not place H-1 fabrication inside the ICP mechanical RFQ.
Create a dedicated H-1 fabrication/build-to-print RFQ package covering the H2-1/H2-3 hardware required for the P1 article, including as applicable:
   * Hall channel/body components;
   * anode and anode distributor/plenum;
   * gas-path interfaces;
   * ceramic/insulating components;
   * MC-1 magnetic-circuit mechanical parts;
   * coil formers and winding requirements;
   * thermal/mechanical mounting interfaces;
   * feedthrough/interface provisions;
   * dimensional inspection and material certification.
P9e/Vyovrinda retains:
   * H-1 design authority;
   * magnetic design;
   * channel/anode design;
   * interface definition;
   * configuration control;
   * final assembly/integration;
   * instrumentation;
   * acceptance testing.
Precision machining, ceramic fabrication, winding or other specialist manufacturing may be outsourced through this separate RFQ as build-to-print work.
This avoids mixing the experimental ICP fabrication package with the core Hall-thruster article and preserves independent configuration/provenance for H-1.
As with the existing RFQs, this initially authorizes quotation/specification activity only, not an automatic purchase order.
Decision: separate H-1 fabrication RFQ + in-house design authority and final integration.
