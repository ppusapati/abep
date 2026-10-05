# OWNER DECISIONS — MASS BUDGET BEFORE THE BID FREEZE (A9.26) — verbatim record

Recorded verbatim from the owner's session messages of 2026-10-04 / 2026-10-05 (after A9.25). Text extracted programmatically from the session transcript (no retyping); each message carries its UTC timestamp and the sha256 of its exact text. Companion: `OD_2026_10_05_A9_26_mass_budget_owner_decisions.json`. Immutable after commit.

---

## Message 1 — MASS_CLOSURE_CHECK_REQUEST — 2026-10-04T17:22:28.839Z — text sha256 `3fee21eb93db05e67ffe412cd643006c860176a357bc0f2d3fc623cc37c01859`

````text
Yes — **the 40 kg constraint absolutely still applies**, and this changes how we should interpret Claude’s mass numbers.

I rechecked the live repo. The current mass model explicitly uses:

> **`HARD_40_WET (< 40 kg)`**

So under our present conservative interpretation, the **complete flight system including loaded Xe must be <40 kg**.

The important point is that the repo currently contains **two very different mass views**:

| Mass view | What it means | Current result |
|---|---|---:|
| Owner/design allocation budget | Target we are trying to design to | 28.8 kg dry incl. 20% margin; with 10 kg Xe = 38.8 kg |
| Current evidence/planning-floor roll-up | Analog floors + provisional allocations we presently have evidence for | **40.572 kg dry before any Xe** |
| + 2 kg Xe | current planning case | **42.572 kg** |
| + 5 kg Xe | current planning case | **45.572 kg** |
| + 10 kg Xe | current planning case | **50.572 kg** |

Therefore the repository is correctly saying **`DOES_NOT_CLOSE`**.

### There is an additional problem I found

The `40.572 kg` figure is actually **not a complete mass estimate**.

`AL-09 — controls / electronics / valve drivers / flight sensors` is still **NULL / TBD_OWNER** in the current `mass_power_a9_v4`. It is explicitly excluded from that 40.572 kg known-line sum.

So:

> **40.572 kg is already above the 40 kg wet limit, even before Xe, and even before every currently missing mass term has been included.**

That means we definitely should **not** let the bid package present 40.572 / 42.572 kg as though it were our proposed compliant final design.

But it also does **not** mean the project is automatically dead. These figures are not a completed CBE. Several large values are conservative analog/planning floors rather than designed hardware masses. For example:

- AL-07 PPU = 6.0 kg provisional analog floor;
- AL-08 Xe system = 5.9148 kg provisional planning floor;
- some subsystem values are allocations rather than actual designs;
- AL-09 is not yet estimated;
- plumbing/mounting elements remain TBD.

So the correct engineering statement is:

> **The requirement is <40 kg wet. Our current preliminary evidence/planning-floor roll-up does not yet close that requirement. The flight design must be mass-optimized and rebased using actual CBE/quotation/design values before design freeze.**

There is another issue worth auditing before we lock the bid: some subsystem “MEV planning floors” already contain a 20% uplift, and then the roll-up adds another **20% system margin**. We should verify that we are not unintentionally **double-applying margin** to those lines. I would not change anything yet, but Claude should explicitly audit the margin convention before we treat 40.572 kg as the authoritative preliminary mass.

So I would slightly interrupt Claude’s current sequence. **Do not freeze the bid package yet.** Send this:

```text
MASS-CLOSURE CHECK BEFORE BID FREEZE

Before creating bid_technical_baseline_v2 or regenerating the final bid package,
perform one narrow mass-budget audit.

The governing requirement remains:

    complete flight-system wet mass < 40 kg

under our current conservative owner reading.

Do NOT relax this requirement.

The current mass_power_a9_v4 result:

    dry known = 40.5721 kg
    + 2 kg Xe = 42.5721 kg
    + 5 kg Xe = 45.5721 kg
    + 10 kg Xe = 50.5721 kg

therefore DOES NOT CLOSE the 40 kg requirement.

Also note that dry_known = 40.5721 kg is NOT a complete flight CBE:
AL-09 controls / electronics / valve drivers / flight sensors still has no
current value and is excluded from that sum.

Therefore do not present 40.5721 kg or any of the wet sensitivity values as the
proposed compliant final flight mass.

Before freeze, give me a MASS AUDIT containing:

1. TARGET / ALLOCATION BUDGET

Show the owner allocation/design-target mass separately from the current
evidence/planning-floor mass.

The existing owner budget reference should remain clearly labelled as a DESIGN
BUDGET, not evidence of achieved mass compliance.

2. CURRENT PLANNING / EVIDENCE ROLL-UP

For every AL-01...AL-10 and harness line show:

- allocation;
- CBE if one exists;
- evidence/planning floor;
- measured mass if one exists;
- governing value currently used;
- whether that value already contains margin;
- evidence class;
- outstanding TBD.

Do not mix these classes.

3. MARGIN AUDIT

Check specifically for double counting.

For every governing line determine whether its current value already contains
an MGA / 20% uplift.

Examples requiring inspection include AL-04, AL-07 and AL-08.

Then determine whether applying the additional 20% system margin to those
already-margined values is intentional governance or accidental double-margin.

DO NOT change the margin policy yet.

Report both arithmetic interpretations if double-margin is present.

4. AL-09

Do not continue to describe 40.5721 kg as a complete dry mass while AL-09 is
missing.

Report:

    dry_known_partial

or equivalent.

Identify the proper current allocation/status for:

    controls / electronics / valve drivers / flight sensors

without inventing a CBE.

5. 40 KG CLOSURE

For each realistic Xe planning case show the maximum allowable dry mass:

    2 kg Xe  -> dry must be < 38 kg
    5 kg Xe  -> dry must be < 35 kg
    10 kg Xe -> dry must be < 30 kg

Then calculate the mass-reduction requirement from the current properly
constructed planning roll-up.

Do not select the Xe load merely to make mass compliance easier.

6. BID PRESENTATION

The bid shall state:

    design requirement / target: <40 kg wet

It shall NOT state that current determining evidence already demonstrates mass
compliance.

Until the mass CBE closes:

    MASS STATUS = INCOMPLETE_EVIDENCE / NOT YET CLOSED

The proposal may describe the mass budget and planned mass-closure process, but
must not claim a false PASS.

7. DO NOT FREEZE MASS NUMBERS YET

Do not create the final bid mass table until this audit is complete.

No physics changes.
No requirement relaxation.
No arbitrary mass reductions.
No removal of qualified hardware solely to force <40 kg.

Report the audit to me before completing bid_technical_baseline_v2.
```

So the answer is: **yes, 40 kg remains the constraint, and Claude’s current mass roll-up is telling us that we have a genuine mass-closure problem.** The right response is not to change the 40 kg limit; it is to audit the mass accounting and establish a credible path to a **<40 kg wet flight design** before we call the proposal mass-compliant.

And I would do that audit **now**, before freezing the final bid mass table.
````

---

## Message 2 — MASS_BUDGET_DECISIONS_PRE_BID_FREEZE — 2026-10-05T02:42:08.598Z — text sha256 `c240fca3b8109078ac0113cdb3526d729e3f13c41a8e8639b802b463f535633f`

````text
MASS-BUDGET OWNER DECISIONS — PRE-BID FREEZE

Do NOT confirm audit reading A as the active bid basis.

The governing bid/proposal mass policy is:

    COMPLETE FLIGHT WET MASS < 40 kg

and:

    SYSTEM-LEVEL MASS MARGIN = 10%

for the proposal / bid baseline.

The earlier 20% system-margin treatment remains historical / conservative
internal provenance only and must not remain the active bid mass-margin policy.

==================================================
1. MARGIN CONVENTION
==================================================

OWNER DECISION:

Keep the existing 20% LINE-LEVEL planning uplift on floor-derived lines:

    AL-04
    AL-07
    AL-08

for this bid freeze.

These remain conservative MEV/planning-floor treatments, not CBEs.

But change the SYSTEM margin from:

    20%

to:

    10%

for the active proposal/bid basis.

Therefore a floor-derived line currently using:

    1.20 x evidence floor

then receives:

    1.10 system margin

at system roll-up.

Effective combined factor:

    1.20 x 1.10 = 1.32

NOT:

    1.20 x 1.20 = 1.44

Do not alter the line-floor values themselves in this step.

Preserve the former 20%-system-margin result as:

    HISTORICAL / CONSERVATIVE SENSITIVITY

Do not delete it.

Record the new owner decision as superseding the 20% system-margin reading
for the proposal/bid baseline only.

==================================================
2. AL-09
==================================================

OWNER DECISION:

Set:

    AL-09 controls / electronics / valve drivers / flight sensors
    = 1.0 kg

Status:

    PROVISIONAL_OWNER_ALLOCATION
    NOT_CBE
    NOT_MEASURED

Harness remains separate under the existing 5/95 rule.

Close:

    MPV3Q-01

accordingly.

Do not reduce another line to compensate for this allocation.

Replace AL-09 with a design-derived CBE when available.

==================================================
3. RECOMPUTE THE CURRENT PLANNING ROLL-UP
==================================================

Using the current line values, AL-09 = 1.0 kg, harness 5/95, and 10% system
margin, the expected arithmetic is approximately:

    non-harness = 33.1196 kg
    harness = 1.7431 kg
    nominal dry = 34.8627 kg
    system margin 10% = 3.4863 kg
    dry planning mass = 38.3490 kg

Wet planning sensitivities:

    2 kg Xe  -> 40.3490 kg
    5 kg Xe  -> 43.3490 kg
    10 kg Xe -> 48.3490 kg

Recompute these from the builder; do not hard-code these rounded values.

If the governed builder gives materially different results, STOP and report.

==================================================
4. 40 KG CLOSURE
==================================================

The requirement remains:

    wet mass < 40 kg

Do NOT relax it.

The 2 kg Xe planning/reference case therefore remains slightly above the
requirement under the present preliminary roll-up.

Expected shortfall is approximately:

    0.35 kg

before unresolved/incomplete evidence-floor constituents are fully closed.

Therefore:

    MASS STATUS =
    INCOMPLETE_EVIDENCE / NOT_YET_CLOSED

Do not claim PASS.

==================================================
5. PROPOSAL MASS TARGET
==================================================

Retain the proposal-level design target:

    nominal dry <= 34.0 kg

with:

    10% system margin

and the 2 kg Xe planning/reference case giving approximately:

    34.0 x 1.10 + 2.0 = 39.4 kg wet

This is a DESIGN TARGET, not achieved evidence.

The 2 kg Xe case is a planning/reference case only.

Do not call it the final selected Xe load.

Continue carrying 5 kg and 10 kg as sensitivities.

==================================================
6. ROW-54 / HISTORICAL BUDGET
==================================================

Do not continue presenting:

    24 kg + 20% = 28.8 kg

as the active bid mass basis.

Preserve that as historical/internal allocation provenance.

If a current allocation-budget roll-up is shown, regenerate it consistently
with:

    AL-09 = 1.0 kg
    harness separate
    10% system margin

and label it:

    INTERNAL ALLOCATION TARGET
    NOT EVIDENCE OF MASS COMPLIANCE

Do not confuse it with the <=34 kg proposal nominal-dry target.

==================================================
7. BID WORDING — APPROVED WITH THESE CORRECTIONS
==================================================

Use the following hierarchy in the bid:

Requirement:
    complete flight wet mass < 40 kg

Proposal design target:
    nominal dry <= 34 kg
    10% system margin
    2 kg Xe planning reference -> ~39.4 kg wet

Current provisional planning/evidence roll-up:
    approximately 38.35 kg dry after 10% system margin
    approximately 40.35 / 43.35 / 48.35 kg wet
    for 2 / 5 / 10 kg Xe planning cases

Current status:
    MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED

Mass-closure actions:
    - AL-07 current cathodeless PPU CBE/requote;
    - AL-08 quote/design rebase;
    - AL-04 completed Hall-head CBE;
    - AL-09 design-derived CBE;
    - actual routed harness;
    - subsystem integration / structural optimization.

Do not claim current mass compliance.

==================================================
8. TECHNICAL SOURCE SHA
==================================================

Because this decision changes:

    system margin
    AL-09
    mass roll-up
    bid-facing mass results

b0937e8 is NOT the final technical-source SHA.

Create a narrow successor commit implementing only this governed mass-policy
correction.

Preserve all historical mass records.

Regenerate every artifact directly affected by mass:

- mass_power successor;
- F7/F8 if they consume the mass record;
- F9;
- freeze candidate;
- compliance / RTM outputs where applicable;
- bid package builders later.

Then run:

- full pytest;
- exactly 5 skips;
- 1 strict xfail;
- Rule-9;
- golden;
- CI integrity;
- config/hash checks;
- affected builders --check;
- GitHub CI.

Report:

A. exact new SHA;
B. recomputed complete mass table;
C. whether F7/F8/F9 statuses changed;
D. confirmation raw propulsion physics is unchanged;
E. unresolved mass terms.

STOP before creating bid_technical_baseline_v2 if any result differs
unexpectedly.

If all changes are exactly the governed mass-accounting changes above and all
checks are green, that new SHA becomes the candidate technical source.
````

