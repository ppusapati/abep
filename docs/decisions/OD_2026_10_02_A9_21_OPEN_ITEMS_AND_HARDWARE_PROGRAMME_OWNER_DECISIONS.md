# OPEN ITEMS + HARDWARE PROGRAMME OWNER DECISIONS (A9.21) — verbatim record, 2026-10-02

Recorded verbatim from the owner's message of 2026-10-02 (session chat), answering the recorder's to-do list. Machine-readable
companion: `OD_2026_10_02_A9_21_open_items_and_hardware_programme_owner_decisions.json`. Immutable after commit.

---

1. Dedicated baseline: no action now. Send the exact commit SHA when ready. I’ll treat the rerun as a new baseline artifact in a new folder, preserving the previous baseline unchanged.
2. Xe-hardware floor: wait for quotations before formally rebasing AL-08. Keep 6.05 kg only as a provisional planning floor, not a frozen allocation. The reason is important: that analog-derived figure may contain about 0.285 kg of C1 cathode-branch hardware, while the RFP-required Xe propulsion system and any C1-specific Xe hardware must be accounted separately. Quotations should split tank, regulator, valves, plumbing, mounting/thermal, and any C1-specific branch before the final re-base.
Decision: `KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08`.
3. H2-6 frozen builder: approved. Keep the frozen H2-6 builder unchanged. Move the mutable/live-source verification into CI using the existing source-verification mechanism. The builder already distinguishes pinned evidence from mutable sources and supports source verification, so this preserves the frozen artifact while CI catches drift.
Decision: `H2_6_BUILDER_FROZEN_LIVE_SOURCE_CHECK_IN_CI`.
4. ICP go/no-go before LOCK-1: I approve the existence and placement of a mandatory ICP go/no-go gate before LOCK-1. I would not yet approve any numerical criterion that I cannot see in the proposal text. The gate must be fail-closed: if its required evidence is missing, the result is `NOT_EVALUATED`, not GO.
Decision: `ICP_GO_NO_GO_REQUIRED_BEFORE_LOCK1`.
The exact proposed GO/NO-GO criteria should be preserved separately until their text is available for review.
5. Bid close date: current DefProc-derived listings show 05 October 2026 at 17:00 for Tender `2026_DRDO_788433_1`; TDF/DRDO’s published announcement gives the same deadline. [TenderHut](https://tenderhut.in/tender/defproc/2026-drdo-788433-1?utm_source=chatgpt.com) The RFP PDF itself does not need to contain the portal closing date. Treat 05-Oct-2026, 17:00 as the operational submission deadline unless DefProc subsequently posts a corrigendum changing it.

For the hardware programme:

6. H-1 engineering build — approved. S7.1 FEMM analysis points first, then S7.2 engineering channel-point selection using magnetic feasibility, thermal margin, mass, packaging and manufacturability. It remains an engineering freeze candidate, not a thrust-optimized design.
7. C1 ground reference — approved. Run H-1 + C1 reference characterization and register `I_d,max,H1,Ar` before P1-S7. This remains a reference/engineering campaign and does not redefine the RFP propellant requirement.
8. ICP programme — approved with one sequencing qualification: preserve the Ar engineering/commissioning reference where already required, then perform the registered air/N₂ ICP-45 campaign, followed by the Xe operating mode as a separate registered campaign. Each gas/mode gets its own operating domain and provenance. Before it starts, close the stage domains, pressure-match tolerance, DWV leakage criteria and stable-region criteria.
9. P2 impedance map — approved. Run after the in-house V/I magnitude/phase calibration and its uncertainty budget are frozen.
10. Coupled H-1 + ICP → thermal → P4 — approved. P4 acceptance thresholds must be frozen before acceptance-bearing coupon exposure, following the LOCK-2 rule already adopted.
11. Measured H-1 thrust/feed map — approved and mandatory. This is what should drive the performance-derived feed requirement for AG-12, followed by the statewise AG-13 `T-D >= 0` check.

Items 12–14 cannot be supplied legitimately from the current evidence:

* AOCS pointing envelope: needs the actual spacecraft/AOCS requirement.
* Inclination and LTAN: not specified by the RFP; do not use the old code default as mission truth.
* Host-spacecraft drag ICD: needs actual spacecraft geometry/attitude/surface data.

For 15, I cannot dispatch supplier RFQs from this chat environment. The quotation packages can be finalized here, but you/procurement must actually send them.
