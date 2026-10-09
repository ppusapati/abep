# P9 Host-spacecraft drag interface: submission-safe statement

Item: A9.38 Priority 9. Closure state: **REFERENCE/ICD DEPENDENT**. The closure criterion is met: the allowable host
C_D·A envelope is registered as interface requirement IR-HOST-DRAG-01. Final compliance depends on the customer
spacecraft ICD.

Evidence:
- `docs/closure/icd/host_drag_cda_envelope_v1.json` / `.md`, built by `build_host_drag_cda_envelope.py` from the M2
  closure record;
- the closure record `docs/closure/icd/p9_closure_state_v1.json`.

---

## Proposal text

**Drag-compensation interface.** The propulsion system compensates the total aerodynamic drag of the host spacecraft
and of its own atmospheric intake. It does this at every flight state of the 180–230 km mission envelope. Throughout
this section, thrust is net of the intake's own drag.

The thrust range is 12–25 mN:
- 12 mN is the sustained level for continuous drag compensation;
- 25 mN is the capability level.

The drag the propulsion system can absorb is therefore an interface quantity between the propulsion system and the
spacecraft. It is stated as a limit on the host drag area.

**Interface requirement IR-HOST-DRAG-01.** The host spacecraft drag area (C_D·A) shall satisfy

  (C_D·A)_host ≤ (T − D_intake(s)) / q(s)

at every required flight state s. The terms are:
- q(s) is the free-stream dynamic pressure at the state;
- D_intake(s) is the drag of the propulsion intake face;
- T = 25 mN applies as the statewise limit;
- T = 12 mN applies as the design target for continuous drag compensation at the sustained thrust level.

The host drag area covers the body, solar arrays and appendages in flight attitude, excluding the intake face. It is
evaluated on the spacecraft's own surface-accommodation basis.

The allowable host drag force and the allowable C_D·A are tabulated for each flight state, by altitude and by
solar/geomagnetic activity level. The tables are part of the propulsion interface data package.

**Envelope at a glance.** The table gives the allowable host C_D·A at the 25 mN capability. "Worst" is the most
demanding flight state at that altitude. "Typical" is the median state.

| altitude | worst state | typical state |
|---|---|---|
| 180 km | ~0.2 m² | ~0.9 m² |
| 195 km | ~0.6 m² | ~1.7 m² |
| 215 km | ~1.2 m² | ~3.3 m² |
| 230 km | ~1.8 m² | ~5 m² |

The limit is most restrictive at the lowest altitude during short-term high solar activity. A host drag area of about
1 m² is compatible from about 215 km in every activity case, and from 180–195 km at low and moderate long-term
activity. The mission altitude profile and the host drag area are therefore traded together with the spacecraft team.

**Verification.** Compliance is verified by analysis, using:
- the spacecraft prime's drag model under the customer spacecraft ICD;
- the propulsion system's intake drag and thrust envelope.

The intake drag values will be updated with the final intake design at PDR and finalized at CDR.

---

## Recorder notes (not for the proposal)

- RC-DIAMANT (C_D·A 1.1 m²) remains only a reference pending the customer ICD.
  - It gives T_required above 25 mN at 40 of the 196 required states.
  - The propulsion system is not resized for it (A9.38 P9).
- At 12 mN, 13 states (alt 180 km, long-term high and short-term high activity; 11 in every surface scenario) have no
  positive host C_D·A. There the DBF-1 intake face alone exceeds 12 mN. This is an intake-drag property carried to
  DCR-001, and it is not hidden: at those states the propulsion system must operate above the sustained level.
- The tabulated values use the DBF-1 intake (0.25 m², unfavourable admitted surface scenario).
  - DCR-001 changes only D_intake.
  - Rerun M2 on the revised baseline and rebuild with `--record`. The formula is unchanged.
- T_available is not evaluated (HALL_NUMERICS_NOT_CONVERGED). The envelope is a drag-side interface constraint, not a
  T − D closure.
