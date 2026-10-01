# RFP-COMPLIANT PROPELLANT POLICY (A9.15) — verbatim record, 2026-10-01

Recorded verbatim from the owner's message of 2026-10-01 (session chat). It amends A9.13 (owner statement on Xe) and A9.14
(S8.17, S8.21, S8.33, S8.35, S9.3, S9.10). "RFP(1)" cites the official RFP held by the owner (not yet registered in the
repository, AG-15). Machine-readable companion: `OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json`. Immutable
after commit; later amendments are new addenda.

---

just a change in xe 

Agreed. We should remove the separate “Xe is contingency-only for C1” policy and make the official RFP the governing requirement.
The RFP says the thruster must be capable of ionizing N₂ and nascent/atomic oxygen and also have capability to use Xe. It further requires the propulsion system to be compatible with both ambient air at 180–230 km and Xenon, with two separate propellant tanks for ambient air and Xenon. RFP(1)
So from now on the governing interpretation should be:
RFP-COMPLIANT PROPELLANT POLICY
The ABEP system shall support both:

* ambient atmospheric propellant in the 180–230 km operating range; and
* Xenon propulsion capability.

Xenon is therefore an RFP-required system capability, not merely a contingency introduced by our internal architecture.
C1 is an internal architecture element, not an RFP requirement. If the selected C1 implementation requires Xenon, its Xe requirement shall be included in the system Xe architecture and accounting. If C1 does not require Xe, no separate C1 Xe consumption shall be invented.
The presence or absence of C1 shall not remove the system-level Xenon capability required by the RFP.
This means I would revise the relevant S8/S9 answers accordingly:

* S8.17 / OQ-A907-07: C1 flight integration may still be deferred until C1 is selected, but not because Xe is contingency-only.
* S8.21 / XA9Q-07: YES — Xe capability applies to the `hall_icp_neutralizer` flight configuration because the RFP requires it.
* S8.33 / MPQ-01: if C1 is selected and requires Xe, its C1-specific branch is booked within the RFP-compliant Xe system; do not assume or exclude C1 Xe in advance.
* S8.35 / XV2Q-01: becomes NOT APPLICABLE, because the system is not Xe-free under the RFP.
* S9.3 / XA9Q-05: whether the ICP Xe path needs a getter/filter remains an engineering/vendor requirement, not a policy choice.
* S9.10 / OD6: “air + Xe” means the system must provide both ambient-air and Xenon operating capability; it should not be weakened into a contingency interpretation.

And the statement I made earlier should be replaced with:
The official RFP is the sole governing basis for propellant capability. The system shall support both ambient atmospheric propellant and Xenon. C1-specific Xe requirements, if any, are derived from the selected C1 hardware and integrated into that RFP-compliant Xe architecture; no independent policy shall restrict or override the RFP.
That is the rule I will use for all further ABEP decisions.
