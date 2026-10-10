# Reference spacecraft drag basis (REFERENCE/PARAMETRIC — not the flight spacecraft)

Generated from `spacecraft_reference_drag_v1.json` by `build_spacecraft_reference_drag.py`; do not edit by hand. Status **REFERENCE_PARAMETRIC_NOT_FLIGHT**, freeze status **NOT_EVALUATED**.

## Owner basis
- `docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md` (json `docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json` sha256 `9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23`): S6.18 / OQ-F78-04; S6.15 / OQ-F78-01; S6.21 / F9-OQ-02; S6.22 / F9-OQ-03 (AG-13, AG-15); S6.17 / OQ-F78-03 (drag minimized in Pareto comparison). authorisation of REFERENCE/PARAMETRIC sourcing (S6.18); statewise T - D >= 0 definition (S6.15); owner-stated 12-25 mN band and derivation of required thrust from the registered drag basis (S6.21); AG-13 / AG-15 gate clarifications (S6.22).
- `docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md` (json `docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json` sha256 `a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309`): A9.15 (RFP-compliant propellant policy; amends A9.13 owner statement on Xe). read for consistency only: it confirms 'RFP(1)' is the owner-held RFP, not yet registered (AG-15); it sets no drag value and changes nothing in this lane.
- `docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md` (json `docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json` sha256 `c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c`): (no drag question). checked: contains no spacecraft-drag decision; cited only for the AG-15 'RFP not registered' note.

S6.18: sourced geometry is for interim parametric studies only and is labelled `REFERENCE/PARAMETRIC`. AG-13 closure needs the host-spacecraft ICD; until then `D_spacecraft` and `T - D` remain `NOT_EVALUATED` for freeze purposes. S6.15: `T_available(state) - D_spacecraft(state) >= 0` statewise, thrust and drag at the same state.

## Scope
- **is**: documented/public/official spacecraft geometry and C_D basis for INTERIM PARAMETRIC drag studies
- **is_not**: the flight/host spacecraft, an ICD, a drag closure, or an AG-13 verdict
- **drag_equation**: D = 0.5 rho v_rel^2 C_D A_ref (Romano 2018 Eq. 1) + caller-supplied intake term (F1)
- **atmosphere_interface**: rho_kg_m3, v_rel_m_s and atmosphere_state supplied by the caller from the orbit-resolved atmosphere; this module imports no atmosphere module
- **thrust band**: 12–25 mN, `FROZEN_REQUIREMENTS_SNAPSHOT`. Shown for orientation only; it is not a drag result and the statewise gate is T_available(state) - D_spacecraft(state) >= 0 (S6.15).

## Declared reference cases (same-source (A_ref, C_D) pairs only)

| case | record | C_D | A_ref (m²) | C_D·A (m²) | A_ref scope | q at 12 mN (Pa) | q at 25 mN (Pa) | level | type |
|---|---|---|---|---|---|---|---|---|---|
| RC-ROMANO2018 | REF-ROMANO2018 | 2.2 | 1 | 2.2 | includes_intake | 0.00545454 | 0.0113636 | 6 | assumed |
| RC-VAIDYA-GOCELIKE | REF-T1-VAIDYA | 3.7 | 1 | 3.7 | includes_intake | 0.00324324 | 0.00675676 | 5 | as-reported (secondary) |
| RC-DICARA-ESA | REF-T1-DICARA | 2 | 1 | 2 | unstated | 0.006 | 0.0125 | 5 | as-reported (secondary) |
| RC-DIAMANT | REF-T1-DIAMANT | 2.2 | 0.5 | 1.1 | unstated | 0.0109091 | 0.0227273 | 5 | as-reported (secondary) |
| RC-SCHONHERR | REF-T1-SCHONHERR | 2.2 | 0.3 | 0.66 | unstated | 0.0181818 | 0.0378788 | 5 | as-reported (secondary) |
| RC-NISHIYAMA | REF-T1-NISHIYAMA | 2 | 1.5 | 3 | unstated | 0.004 | 0.00833333 | 5 | as-reported (secondary) |
| RC-TISAEV-LOW | REF-T1-TISAEV | 3.2 | 0.1 | 0.32 | unstated | 0.0375 | 0.078125 | 5 | as-reported (secondary) |
| RC-TISAEV-HIGH | REF-T1-TISAEV | 4.2 | 0.1 | 0.42 | unstated | 0.0285714 | 0.0595238 | 5 | as-reported (secondary) |

`q = ½ρv²` at which the reference term alone equals a band edge (intake term excluded). This is density-free; statewise values need the orbit-resolved atmosphere (caller input).

## Reference records

| id | name | altitude (km) | mass (kg) | frontal area (m²) | C_D | C_D basis | A_ref scope |
|---|---|---|---|---|---|---|---|
| REF-GOCE | ESA GOCE (flown; mission ended November 2013 per Romano 2018) | 235–265 | 1050 | 0.8–1.1 | TBD | GSI used for GOCE density processing: diffuse reflection with incomplete accommodation (DRIA), energy accommodation alpha = 0.82 (constant) | body_without_intake (GOCE has no intake); the GOCE-like C_D = 3.7 case is a different body |
| REF-SLATS | JAXA SLATS 'TSUBAME' (flown 23 Dec 2017 - 1 Oct 2019 per JAXA) | 167.4, 181.1, 216.8, 230, 240, 250, 271.5 | 383 | TBD | TBD | TBD | unstated |
| REF-ROMANO2018 | Romano et al. 2018 IPG6-S ABEP system analysis reference | 150–250 | <1050 | 1 | 2.2 | constant literature-typical C_D; full accommodation at front and intake surfaces ('a worst condition is chosen assuming full accommodation') | includes_intake |
| REF-T1-NISHIYAMA | Nishiyama ABEP concept (as tabulated by Andreussi 2022) | 140–160 | TBD | 1.5 | 2 | TBD | unstated |
| REF-T1-DICARA | Di Cara ABEP concept (as tabulated by Andreussi 2022) | 200–250 | 1000 | 1 | 2 | TBD | unstated |
| REF-T1-HRUBY | Hruby ABEP concept (as tabulated by Andreussi 2022) | 150 | TBD | TBD | 2.2 | TBD | unstated |
| REF-T1-DIAMANT | Diamant ABEP concept (as tabulated by Andreussi 2022) | 200 | 400 | 0.5 | 2.2 | TBD | unstated |
| REF-T1-SHABSHELOWITZ | Shabelowitz ABEP concept (as tabulated by Andreussi 2022) | 180–200 | 325 | 0.36 | TBD | TBD | unstated |
| REF-T1-SCHONHERR | Schonherr ABEP concept (as tabulated by Andreussi 2022) | 200 | TBD | 0.3 | 2.2 | TBD | unstated |
| REF-T1-ROMANO | Romano ABEP concept (as tabulated by Andreussi 2022) | 150–250 | <1050 | 1 | 2.2 | TBD | unstated |
| REF-T1-ANDREUSSI | Andreussi ABEP concept (as tabulated by Andreussi 2022) | 190–240 | 500–750 | 0.7 | TBD | TBD | unstated |
| REF-T1-TISAEV | Tisaev ABEP concept (as tabulated by Andreussi 2022) | 170–200 | 200 | 0.1 | 3.2–4.2 | TBD | unstated |
| REF-T1-OVCHINNIKOV | Ovchinnikov ABEP concept (as tabulated by Andreussi 2022) | 175 | 120 | 0.2 | TBD | TBD | unstated |
| REF-T1-VAIDYA | Vaidya ABEP concept (as tabulated by Andreussi 2022) | 160–250 | 1000 | 1 | 3.7 | TBD | unstated |
| REF-T1-CRANDALL | Crandall ABEP concept (as tabulated by Andreussi 2022) | 160–250 | 7.5–10.5 | 0.01 | 3–6 | TBD | unstated |

Per-value source, evidence level, quantity type and verbatim notes are in the JSON (`records[*].*`).

## Sources read
- **SRC-JAXA-2019** — JAXA press release, 'Super Low Altitude Test Satellite (SLATS) “TSUBAME” has set a GUINESS WORLD RECORDS(R)', December 24, 2019 (JST). <https://global.jaxa.jp/press/2019/12/20191224a.html>. Access: official agency web page, public. Retrieved sha256: `ee70c5330e8efc2d6e147c5fd95481389dd6999485a5c58d29df8ece91b48769`. text extracted from the retrieved HTML and matched verbatim.
- **SRC-ESA-GOCE** — ESA Earth Online, 'GOCE Overview' (missions/goce/description), undated web page. <https://earth.esa.int/eogateway/missions/goce/description>. Access: official agency web page, public (JavaScript-rendered). Retrieved sha256: `n/a`. quotes obtained through a rendering fetch tool; a plain HTTP download returns only the page shell, so the quotes are NOT independently byte-verified (verify).
- **SRC-ROMANO-2018** — Romano F., Massuti-Ballester B., Binder T., Herdrich G., Fasoulas S., Schoenherr T., 'System Analysis and Test-bed for an Atmosphere-Breathing Electric Propulsion System using an Inductive Plasma Thruster', Acta Astronautica 147 (2018) 114-126, doi:10.1016/j.actaastro.2018.03.031; accepted manuscript arXiv:2103.02328v2. <https://arxiv.org/pdf/2103.02328>. Access: open accepted manuscript (CC-BY-NC-ND 4.0, as stated on each page). Retrieved sha256: `5e008fb8e025fc37a82e960a7f073c78de73214dfec99763ff936e4b9e056ca2`. text extracted from the retrieved PDF (pdftotext) and matched.
- **SRC-ANDREUSSI-2022** — Andreussi T., Ferrato E., Giannetti V., 'A review of air-breathing electric propulsion: from mission studies to technology verification', J. Electr. Propuls. 1:31 (2022), doi:10.1007/s44205-022-00024-9, Table 1 and Sect. 2. <https://link.springer.com/content/pdf/10.1007/s44205-022-00024-9.pdf>. Access: open access (CC BY 4.0, as stated in the article). Retrieved sha256: `490ca6f6b763fe4ee1089d9815d4075a94223ec74d577f61d67986708c3ce3b7`. text extracted from the retrieved PDF (pdftotext) and matched.
- **SRC-MEHTA-2022** — Mehta P.M., Paul S.N., Crisp N.H., Sheridan P.L., Siemes C., March G., Bruinsma S., 'Satellite drag coefficient modeling for thermosphere science and mission operations', Adv. Space Res. 72(12) (2023) 5443-5459, doi:10.1016/j.asr.2022.05.064. <https://pure.tudelft.nl/ws/portalfiles/portal/172534820/1_s2.0_S0273117722004458_main.pdf>. Access: open access (CC BY, TU Delft repository, final published version). Retrieved sha256: `684dcb620c9e581229b935722175ea225f781341b18db1ee47fd7e33ba982389`. text extracted from the retrieved PDF (pdftotext) and matched.
- **SRC-SINPETRU-2022** — Sinpetru L.A., Crisp N.H., Mostaza-Prieto D., Livadiotti S., Roberts P.C.E., 'ADBSat: Methodology of a novel panel method tool for aerodynamic analysis of satellites', Comput. Phys. Commun. (2022); preprint arXiv:2104.05543v2. <https://arxiv.org/pdf/2104.05543>. Access: open preprint (arXiv). Retrieved sha256: `bd5029dc49cd3c174a90cd83832a8eb3b22773c48dda0701e9016e591754fc20`. text extracted; equations are typeset and only partly recoverable as text (see C_D model basis notes).

## Cited but not accessed
- Vaidya S. et al., CEAS Space J. (2022), doi:10.1007/s12567-022-00436-1 — publisher page states access 'No' for this session; no open copy located; C_D = 3.7 for the GOCE-like case is carried as-reported (secondary) via Andreussi 2022; its underlying derivation (measured / model / assumed) is TBD.
- ESA, GOCE System Critical Design Review (CDR), Alenia Spazio, May 2005 (Romano 2018 ref. [1]) — technical report, not publicly available; GOCE frontal area 1.1 m^2 carried as-reported (secondary) via Romano 2018.
- March G. et al. 2019b (GOCE energy accommodation selection), cited by Mehta 2022 — not retrieved in this lane; alpha = 0.82 carried as stated by Mehta 2022.
- Di Cara D. et al., IEPC-2007-162; Diamant; Nishiyama 2003; Tisaev 2021; Crandall & Wirz 2022 (Andreussi 2022 Table 1 refs.) — not retrieved in this lane; their Table 1 values are carried as-reported (secondary) via Andreussi 2022.

## Findings
- **SRD-01** abep_sim/mission_env.py Spacecraft defaults (bus_frontal_m2 = 0.25, bus_cd = 2.2, intake_cd_ref = 2.05) and spacecraft_drag() array C_D 2.4 carry no source in that module; this lane does not modify or call it. They are not REFERENCE/PARAMETRIC records and must not be quoted as a spacecraft drag basis. Action: owner/step-3 decision whether mission_env adopts a registered reference case (not done here).
- **SRD-02** GOCE frontal area is reported as about 1 m2 and 0.8 m2 on the same ESA page and as 1.1 m2 by Romano 2018 (citing the CDR); the conflict is carried as an interval. Action: none; no GOCE drag case is declared because no source pairs a GOCE flight C_D with its area.
- **SRD-03** C_D spans 2.0-4.2 across the declared reference cases (C_D*A_ref 0.32-3.7 m^2); the sources read do not state the GSI/accommodation basis of most values, so the spread cannot be attributed to physics or convention and is not measurement scatter. Action: parametric studies evaluate all declared cases (envelope), no single 'representative' case.
- **SRD-04** Several reference areas already contain the intake (Romano: A_f = A_in); naive addition of an F1 intake term double-counts. Action: enforced by the required intake_accounting argument.
- **SRD-05** A closed-form Sentman flat-plate C_D (Sinpetru 2022 Eq. 6-7) was considered but not implemented: the incident-temperature definition is not recoverable from the text read, and implementing it from memory would violate rule 6. Action: open item; implement only from a fully read open source.

## Open items
- AG-13 closure requires the host-spacecraft ICD (body frontal geometry, intake projected area, arrays/deployed surfaces, attitude/pointing states, C_D/model basis, accommodation/surface state) - S6.18
- Orbit-resolved atmosphere producer (S6.14) supplies rho and v_rel; no state evaluated here
- SLATS frontal area and C_D: not in the open sources read
- Vaidya 2022 (GOCE-like C_D 3.7) not accessed; derivation TBD
- Sentman / DRIA flat-plate closed form from a fully readable open source (SRD-05)
