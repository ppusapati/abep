"""Reference spacecraft drag basis for INTERIM PARAMETRIC drag studies (owner decision A9.13 S6.18, OQ-F78-04).

What this is
------------
A register of documented / public / official spacecraft and published ABEP reference-spacecraft geometry together with the
drag-coefficient basis each source states, plus a parametric drag evaluator

    D = 0.5 * rho * v_rel**2 * C_D * A_ref            (Romano et al. 2018, arXiv:2103.02328v2, Eq. 1)

for a DECLARED reference case. Every output carries ``status = REFERENCE_PARAMETRIC_NOT_FLIGHT``.

What this is not
----------------
Not the flight spacecraft, not the host-spacecraft ICD, not an AG-13 closure. Per S6.18 "Until that ICD exists,
`D_spacecraft` and `T-D` remain `NOT_EVALUATED` for freeze purposes": every result therefore also carries
``freeze_status = NOT_EVALUATED``.

Interfaces (no hidden defaults; missing inputs raise)
-----------------------------------------------------
* Atmosphere: ``rho_kg_m3`` and ``v_rel_m_s`` are supplied by the caller from the ORBIT-RESOLVED atmosphere (S6.14). This
  module imports no atmosphere module and never looks density up itself.
* Intake: the intake projected area and the intake drag coefficient are a SEPARATE caller-supplied term (F1 owns intake
  drag). How that term combines with a reference case is an explicit, required ``intake_accounting`` argument, because
  several published reference areas already contain the intake (e.g. Romano 2018 sets A_f = A_in = 1 m^2).
* Thrust band: 12-25 mN is shown for orientation only, as a frozen engineering input taken from the frozen
  requirements snapshot (owner A9.22 G3: AG-15 closed, snapshot FROZEN; docs/requirements/rfp_official/
  rfp_registration_v1.json); it carries ``requirement_status = FROZEN_REQUIREMENTS_SNAPSHOT``. This module never reads
  or interprets requirement clauses; the band values are plain numbers with provenance.

Evidence classes follow docs/EVIDENCE.md: evidence level (1-7, strength/proximity of the source) is orthogonal to
quantity type (measured / digitized / inferred / reconstructed / model-derived / assumed / as-reported (secondary) / TBD).
For a reference spacecraft the applicability is always "reference spacecraft, not the Vyovrinda host".
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

SCHEMA = "abep.spacecraft_reference_drag.v1"
STATUS = "REFERENCE_PARAMETRIC_NOT_FLIGHT"
FREEZE_STATUS = "NOT_EVALUATED"
LABEL = "REFERENCE/PARAMETRIC"
RETRIEVAL_DATE = "2026-10-01"

# --------------------------------------------------------------------------------------------------------------------
# Owner decisions implemented (immutable records; path + companion-json sha256 + question id)
# --------------------------------------------------------------------------------------------------------------------
DECISIONS = (
    {"path": "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md",
     "md_sha256": "adf11923c07f773276ee893d6ad01cd51c4988ba4bfb8865ec1d781a4978c8bf",
     "json_path": "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json",
     "json_sha256": "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23",
     "question_ids": ["S6.18 / OQ-F78-04", "S6.15 / OQ-F78-01", "S6.21 / F9-OQ-02", "S6.22 / F9-OQ-03 (AG-13, AG-15)",
                      "S6.17 / OQ-F78-03 (drag minimized in Pareto comparison)"],
     "used_for": "authorisation of REFERENCE/PARAMETRIC sourcing (S6.18); statewise T - D >= 0 definition (S6.15); "
                 "owner-stated 12-25 mN band and derivation of required thrust from the registered drag basis (S6.21); "
                 "AG-13 / AG-15 gate clarifications (S6.22)"},
    {"path": "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
     "md_sha256": "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903",
     "json_path": "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
     "json_sha256": "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
     "question_ids": ["A9.15 (RFP-compliant propellant policy; amends A9.13 owner statement on Xe)"],
     "used_for": "read for consistency only: it confirms 'RFP(1)' is the owner-held RFP, not yet registered (AG-15); it "
                 "sets no drag value and changes nothing in this lane"},
    {"path": "docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md",
     "md_sha256": "2a61c761120863c4b5821043ab78b6f9b28227584f7d83cb48ecd6598ed0af07",
     "json_path": "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
     "json_sha256": "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
     "question_ids": [],
     "used_for": "checked: contains no spacecraft-drag decision; cited only for the AG-15 'RFP not registered' note"},
)

RFP_THRUST_BAND = {
    "min_mN": 12.0, "max_mN": 25.0,
    "requirement_status": "FROZEN_REQUIREMENTS_SNAPSHOT",
    "source": "A9.13 S6.21 verbatim: 'The official RFP instead defines the functional orbit and thrust requirement: "
              "180-230 km, intake specification dependent on air density/solar activity, and 12-25 mN thrust for "
              "expected drag compensation. RFP(1)'",
    "provenance": "frozen requirements snapshot docs/requirements/rfp_official/rfp_registration_v1.json (sha256 "
                  "be2d26cdc8c8b140f29d26b52140a3bae6d1080ecaa92ea40841889207e49412); snapshot frozen and AG-15 closed by "
                  "owner decision A9.22 G3 (docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json). "
                  "Value unchanged; the earlier label OWNER_STATED_RFP_NOT_REGISTERED is superseded (stale since the "
                  "registration and the A9.22 freeze).",
    "note": "Shown for orientation only; it is "
            "not a drag result and the statewise gate is T_available(state) - D_spacecraft(state) >= 0 (S6.15).",
}

# --------------------------------------------------------------------------------------------------------------------
# Sources actually retrieved and read on RETRIEVAL_DATE (lawful open access only)
# --------------------------------------------------------------------------------------------------------------------
SOURCES = {
    "SRC-JAXA-2019": {
        "citation": "JAXA press release, 'Super Low Altitude Test Satellite (SLATS) “TSUBAME” has set a "
                    "GUINESS WORLD RECORDS(R)', December 24, 2019 (JST)",
        "url": "https://global.jaxa.jp/press/2019/12/20191224a.html",
        "access": "official agency web page, public",
        "retrieved_sha256": "ee70c5330e8efc2d6e147c5fd95481389dd6999485a5c58d29df8ece91b48769",
        "verbatim_check": "text extracted from the retrieved HTML and matched verbatim",
    },
    "SRC-ESA-GOCE": {
        "citation": "ESA Earth Online, 'GOCE Overview' (missions/goce/description), undated web page",
        "url": "https://earth.esa.int/eogateway/missions/goce/description",
        "access": "official agency web page, public (JavaScript-rendered)",
        "retrieved_sha256": None,
        "verbatim_check": "quotes obtained through a rendering fetch tool; a plain HTTP download returns only the page "
                          "shell, so the quotes are NOT independently byte-verified (verify)",
    },
    "SRC-ROMANO-2018": {
        "citation": "Romano F., Massuti-Ballester B., Binder T., Herdrich G., Fasoulas S., Schoenherr T., 'System "
                    "Analysis and Test-bed for an Atmosphere-Breathing Electric Propulsion System using an Inductive "
                    "Plasma Thruster', Acta Astronautica 147 (2018) 114-126, doi:10.1016/j.actaastro.2018.03.031; "
                    "accepted manuscript arXiv:2103.02328v2",
        "url": "https://arxiv.org/pdf/2103.02328",
        "access": "open accepted manuscript (CC-BY-NC-ND 4.0, as stated on each page)",
        "retrieved_sha256": "5e008fb8e025fc37a82e960a7f073c78de73214dfec99763ff936e4b9e056ca2",
        "verbatim_check": "text extracted from the retrieved PDF (pdftotext) and matched",
    },
    "SRC-ANDREUSSI-2022": {
        "citation": "Andreussi T., Ferrato E., Giannetti V., 'A review of air-breathing electric propulsion: from "
                    "mission studies to technology verification', J. Electr. Propuls. 1:31 (2022), "
                    "doi:10.1007/s44205-022-00024-9, Table 1 and Sect. 2",
        "url": "https://link.springer.com/content/pdf/10.1007/s44205-022-00024-9.pdf",
        "access": "open access (CC BY 4.0, as stated in the article)",
        "retrieved_sha256": "490ca6f6b763fe4ee1089d9815d4075a94223ec74d577f61d67986708c3ce3b7",
        "verbatim_check": "text extracted from the retrieved PDF (pdftotext) and matched",
    },
    "SRC-MEHTA-2022": {
        "citation": "Mehta P.M., Paul S.N., Crisp N.H., Sheridan P.L., Siemes C., March G., Bruinsma S., 'Satellite drag "
                    "coefficient modeling for thermosphere science and mission operations', Adv. Space Res. 72(12) "
                    "(2023) 5443-5459, doi:10.1016/j.asr.2022.05.064",
        "url": "https://pure.tudelft.nl/ws/portalfiles/portal/172534820/1_s2.0_S0273117722004458_main.pdf",
        "access": "open access (CC BY, TU Delft repository, final published version)",
        "retrieved_sha256": "684dcb620c9e581229b935722175ea225f781341b18db1ee47fd7e33ba982389",
        "verbatim_check": "text extracted from the retrieved PDF (pdftotext) and matched",
    },
    "SRC-SINPETRU-2022": {
        "citation": "Sinpetru L.A., Crisp N.H., Mostaza-Prieto D., Livadiotti S., Roberts P.C.E., 'ADBSat: Methodology "
                    "of a novel panel method tool for aerodynamic analysis of satellites', Comput. Phys. Commun. (2022); "
                    "preprint arXiv:2104.05543v2",
        "url": "https://arxiv.org/pdf/2104.05543",
        "access": "open preprint (arXiv)",
        "retrieved_sha256": "bd5029dc49cd3c174a90cd83832a8eb3b22773c48dda0701e9016e591754fc20",
        "verbatim_check": "text extracted; equations are typeset and only partly recoverable as text (see C_D model "
                          "basis notes)",
    },
}

# Sources cited BY the sources above but not accessed here (recorded so nothing is attributed to them first-hand).
NOT_ACCESSED = (
    {"ref": "Vaidya S. et al., CEAS Space J. (2022), doi:10.1007/s12567-022-00436-1",
     "why": "publisher page states access 'No' for this session; no open copy located",
     "consequence": "C_D = 3.7 for the GOCE-like case is carried as-reported (secondary) via Andreussi 2022; its "
                    "underlying derivation (measured / model / assumed) is TBD"},
    {"ref": "ESA, GOCE System Critical Design Review (CDR), Alenia Spazio, May 2005 (Romano 2018 ref. [1])",
     "why": "technical report, not publicly available",
     "consequence": "GOCE frontal area 1.1 m^2 carried as-reported (secondary) via Romano 2018"},
    {"ref": "March G. et al. 2019b (GOCE energy accommodation selection), cited by Mehta 2022",
     "why": "not retrieved in this lane",
     "consequence": "alpha = 0.82 carried as stated by Mehta 2022"},
    {"ref": "Di Cara D. et al., IEPC-2007-162; Diamant; Nishiyama 2003; Tisaev 2021; Crandall & Wirz 2022 "
            "(Andreussi 2022 Table 1 refs.)",
     "why": "not retrieved in this lane",
     "consequence": "their Table 1 values are carried as-reported (secondary) via Andreussi 2022"},
)


def _v(value, unit, source, evidence_level, quantity_type, note=""):
    """One sourced value. ``value`` None means TBD (never a placeholder number)."""
    if value is None:
        quantity_type = "TBD"
    return {"value": value, "unit": unit, "source": source, "evidence_level": evidence_level,
            "quantity_type": quantity_type, "note": note}


# --------------------------------------------------------------------------------------------------------------------
# Reference records (REFERENCE/PARAMETRIC; never the flight spacecraft)
# --------------------------------------------------------------------------------------------------------------------
_APPL = "reference spacecraft only; not the Vyovrinda host spacecraft (S6.18)"


def _table1_row(rid, concept, ref_no, orbit, h, m, p, af, cd, extra_note=""):
    src = f"SRC-ANDREUSSI-2022 Table 1, row '{concept} [{ref_no}]'"
    return {
        "id": rid, "label": LABEL, "name": f"{concept} ABEP concept (as tabulated by Andreussi 2022)",
        "kind": "published ABEP concept study (not flown)", "access": "open access review (secondary for this row)",
        "applicability": _APPL,
        "orbit": _v(orbit, "-", src, 5, "as-reported (secondary)") if orbit else _v(None, "-", src, 5, "TBD"),
        "altitude_km": _v(h, "km", src, 5, "as-reported (secondary)"),
        "mass_kg": _v(m, "kg", src, 5, "as-reported (secondary)"),
        "power_kW": _v(p, "kW", src, 5, "as-reported (secondary)"),
        "frontal_area_m2": _v(af, "m^2", src, 5, "as-reported (secondary)"),
        "cd": _v(cd, "-", src, 5, "as-reported (secondary)"),
        "body_array_configuration": _v(None, "-", src, 5, "TBD", "not stated in Table 1"),
        "attitude_assumption": _v(None, "-", src, 5, "TBD", "not stated in Table 1"),
        "cd_model_basis": _v(None, "-", src, 5, "TBD",
                             "Table 1 gives the value only; GSI model / accommodation not stated there"),
        "a_ref_scope": "unstated",
        "note": extra_note,
    }


RECORDS = (
    {
        "id": "REF-GOCE", "label": LABEL, "name": "ESA GOCE (flown; mission ended November 2013 per Romano 2018)",
        "kind": "flown spacecraft, official agency description", "access": "official public web page + open papers",
        "applicability": _APPL,
        "orbit": _v("sun-synchronous", "-", "SRC-ROMANO-2018 Sect. 1.1", 5, "as-reported (secondary)",
                    "'orbited into a 250 (finally 235)-265 km SSO'"),
        "altitude_km": _v([235.0, 265.0], "km", "SRC-ROMANO-2018 Sect. 1.1", 5, "as-reported (secondary)",
                          "Romano: '250 (finally 235)-265 km SSO'. ESA page (verify): 'designed to skim above Earth "
                          "at a height of just 250 km', 'mean altitude approximately 263 km'"),
        "mass_kg": _v(1050.0, "kg", "SRC-ESA-GOCE; SRC-ROMANO-2018 Sect. 1.1", 3, "as-reported (secondary)",
                      "ESA (verify): 'weighed in at about 1050 kg'; Romano: 'The S/C had a mass of 1050 kg'"),
        "length_m": _v([5.0, 5.3], "m", "SRC-ESA-GOCE", 3, "as-reported (secondary)",
                       "same page gives 'slim 5 metre-long satellite' and '5.3 m long' (verify)"),
        "frontal_area_m2": _v([0.8, 1.1], "m^2", "SRC-ESA-GOCE; SRC-ROMANO-2018 Sect. 1.1", 3,
                              "as-reported (secondary)",
                              "SOURCE CONFLICT carried, not resolved: ESA page (verify) 'cross sectional area of about "
                              "1 m2' AND 'octagonal structure with fixed solar wings, 5.3 m long, cross-section of 0.8 "
                              "m2'; Romano 2018: 'The frontal area was of 1.1 m2 [1]' (ref. [1] = GOCE CDR, not "
                              "accessed). Interval [0.8, 1.1] m^2 spans all three statements"),
        "body_array_configuration": _v("octagonal body; fixed (non-deployable) solar wings and winglets for "
                                       "aerodynamic stabilisation; no moving parts", "-", "SRC-ESA-GOCE", 3,
                                       "as-reported (secondary)", "verify (rendered-page quotes)"),
        "attitude_assumption": _v("flies along the velocity vector with the wings in the flow ('a configuration "
                                  "can be found in the GOCE spacecraft': solar arrays parallel to the direction of "
                                  "flight)", "-", "SRC-ROMANO-2018 Sect. 2.4 (Drag)", 5,
                                  "as-reported (secondary)"),
        "cd": _v(None, "-", "SRC-MEHTA-2022 Fig. 5 (plotted only)", 4, "TBD",
                 "no GOCE flight C_D value is stated in text or table by the sources read (Mehta 2022 plots it in "
                 "Fig. 5; not digitized here). The 'GOCE-like' C_D = 3.7 of Vaidya (via Andreussi 2022: 'a reference "
                 "GOCE-like spacecraft having a 1 m2 intake frontal area, a drag coefficient of 3.7') belongs to a "
                 "different ABEP body and is carried only as REF-T1-VAIDYA / RC-VAIDYA-GOCELIKE"),
        "cd_model_basis": _v("GSI used for GOCE density processing: diffuse reflection with incomplete accommodation "
                             "(DRIA), energy accommodation alpha = 0.82 (constant)", "-",
                             "SRC-MEHTA-2022 Sect. 2.2 (citing March et al. 2019b) and Sect. 5.1", 4, "model-derived",
                             "Mehta: 'The GSIs were modeled as DRIA, where a was set to the carefully selected constant "
                             "values of 0.85 and 0.82 for the CHAMP and GOCE satellites, respectively'; 'For GOCE, the "
                             "largest difference in C D of about 10% is between DUT-DRIA-0.85 and RSM-CLL-WLK.' The "
                             "GOCE C_D time series is only plotted (Fig. 5), not tabulated; not digitized here"),
        "a_ref_scope": "body_without_intake (GOCE has no intake); the GOCE-like C_D = 3.7 case is a different body",
        "note": "GOCE thrust capability (ESA page, verify): 'throttled between 1 and 20 millinewtons'; Romano: 'thrust "
                "between T = 1.5 and 20 mN' - recorded for orientation only, not a requirement",
    },
    {
        "id": "REF-SLATS", "label": LABEL, "name": "JAXA SLATS 'TSUBAME' (flown 23 Dec 2017 - 1 Oct 2019 per JAXA)",
        "kind": "flown spacecraft, official agency description", "access": "official public web page",
        "applicability": _APPL,
        "orbit": _v(None, "-", "SRC-JAXA-2019", 3, "TBD", "orbit type not stated on the page read"),
        "altitude_km": _v([167.4, 181.1, 216.8, 230.0, 240.0, 250.0, 271.5], "km", "SRC-JAXA-2019", 3,
                          "as-reported (secondary)",
                          "'271.5 km and 216.8 km each for 38 days 250 km, 240 km, 230 km, 181.1 km, and 167.4 km "
                          "each for 7 days (At 167.4 km altitude, Tsubame used both its ion engine system and RCS "
                          "because of the large atmospheric drag.)'"),
        "mass_kg": _v(383.0, "kg", "SRC-JAXA-2019", 3, "as-reported (secondary)", "'Weight 383 kg'"),
        "envelope_m": _v([2.5, 5.2, 0.9], "m", "SRC-JAXA-2019", 3, "as-reported (secondary)",
                         "'Size 2.5 m (X) x 5.2 m (Y) x 0.9m (Z) (when expanded in orbit)'"),
        "frontal_area_m2": _v(None, "m^2", "SRC-JAXA-2019", 3, "TBD",
                              "not published on the page read; the axis-to-velocity mapping is not stated, so no "
                              "frontal area is derived from the envelope (deriving one would be an invented attitude)"),
        "body_array_configuration": _v(None, "-", "SRC-JAXA-2019", 3, "TBD",
                                       "envelope is 'when expanded in orbit'; array geometry not stated"),
        "attitude_assumption": _v(None, "-", "SRC-JAXA-2019", 3, "TBD"),
        "cd": _v(None, "-", "SRC-JAXA-2019", 3, "TBD", "no C_D on the page read"),
        "cd_model_basis": _v(None, "-", "SRC-JAXA-2019", 3, "TBD"),
        "a_ref_scope": "unstated",
        "note": "Generated power '1,140 W or more'. Kept as a flown VLEO anchor (lowest altitude 167.4 km, inside "
                "and below the RFP band) but NOT usable for a drag case until frontal area and C_D are sourced",
    },
    {
        "id": "REF-ROMANO2018", "label": LABEL, "name": "Romano et al. 2018 IPG6-S ABEP system analysis reference",
        "kind": "published ABEP system study (not flown)", "access": "open accepted manuscript (arXiv)",
        "applicability": _APPL,
        "orbit": _v(None, "-", "SRC-ROMANO-2018", 5, "TBD"),
        "altitude_km": _v([150.0, 250.0], "km", "SRC-ANDREUSSI-2022 Table 1 row 'Romano [48]'", 5,
                          "as-reported (secondary)"),
        "mass_kg": _v("<1050", "kg", "SRC-ANDREUSSI-2022 Table 1 row 'Romano [48]'", 5, "as-reported (secondary)"),
        "frontal_area_m2": _v(1.0, "m^2", "SRC-ROMANO-2018 Sect. 1.1", 5, "assumed",
                              "'using a reference frontal area Af equal to that of the intake area Ain of 1 m2 for the "
                              "estimation of the drag and the collectible mass flow'"),
        "body_array_configuration": _v("solar arrays parallel to the direction of flight, their drag neglected; lateral "
                                       "surfaces not evaluated", "-", "SRC-ROMANO-2018 Sect. 2.4 (Drag)", 7,
                                       "assumed",
                                       "'the contribution of solar arrays is neglected by considering them to be "
                                       "parallel to the direction of flight'; 'Lateral surfaces also have impact on "
                                       "the drag, however, these require DSMC simulation and will be evaluated in "
                                       "further work'"),
        "attitude_assumption": _v("frontal area normal to the flow ('normal facing area')", "-",
                                  "SRC-ROMANO-2018 Sect. 2.4", 7, "assumed"),
        "cd": _v(2.2, "-", "SRC-ROMANO-2018 Sect. 2.4", 6, "assumed",
                 "'A drag coefficient of CD = 2.2 has been exemplary selected, which is a typical average in literature "
                 "for small S/C in LEO, and for normal facing area'"),
        "cd_model_basis": _v("constant literature-typical C_D; full accommodation at front and intake surfaces "
                             "('a worst condition is chosen assuming full accommodation')", "-",
                             "SRC-ROMANO-2018 Sect. 2.4", 6, "assumed"),
        "a_ref_scope": "includes_intake",
        "note": "A_ref = A_in: the intake IS the reference area in this case",
    },
    _table1_row("REF-T1-NISHIYAMA", "Nishiyama", 5, "SSO 6am", [140.0, 160.0], None, [0.5, 3.3], 1.5, 2.0,
                "Romano 2018 Sect. 1.1 describes the same JAXA ABIE concept at 'h = 170 km' with 'inlet area of "
                "0.48 m2' - altitude conflict with Table 1 carried, not resolved"),
    _table1_row("REF-T1-DICARA", "Di Cara", 43, "SSO 10:30", [200.0, 250.0], 1000.0, 2.9, 1.0, 2.0,
                "Andreussi text: '1000 kg spacecraft with a 1 m2 frontal area and equipped with a 0.6 m2 intake'; "
                "Romano 2018: 'Solar array (SA) surface is of 19.74 m2'"),
    _table1_row("REF-T1-HRUBY", "Hruby", 44, None, 150.0, None, [2.0, 3.0], None, 2.2),
    _table1_row("REF-T1-DIAMANT", "Diamant", 45, None, 200.0, 400.0, 1.0, 0.5, 2.2),
    _table1_row("REF-T1-SHABSHELOWITZ", "Shabelowitz", 46, None, [180.0, 200.0], 325.0, 0.3, 0.36, None,
                "Table 1 prints 'Shabelowitz'; Andreussi text 'Shabshelowitz [57]' gives 0.36 m2, Romano 2018 gives "
                "'The frontal area is of 0.39 m2' and 'Af /Ainlet = 0.5' - conflict carried"),
    _table1_row("REF-T1-SCHONHERR", "Schonherr", 47, None, 200.0, None, None, 0.3, 2.2),
    _table1_row("REF-T1-ROMANO", "Romano", 48, None, [150.0, 250.0], "<1050", 3.5, 1.0, 2.2,
                "same study as REF-ROMANO2018 (primary record there)"),
    _table1_row("REF-T1-ANDREUSSI", "Andreussi", 49, "SSO 6am", [190.0, 240.0], [500.0, 750.0], [2.5, 3.0], 0.7,
                None),
    _table1_row("REF-T1-TISAEV", "Tisaev", 50, "SSO 6am", [170.0, 200.0], 200.0, 0.6, 0.1, [3.2, 4.2]),
    _table1_row("REF-T1-OVCHINNIKOV", "Ovchinnikov", 51, "SSO 6am", 175.0, 120.0, [0.2, 0.4], 0.2, None),
    _table1_row("REF-T1-VAIDYA", "Vaidya", 52, None, [160.0, 250.0], 1000.0, 1.6, 1.0, 3.7,
                "Andreussi text: 'a reference GOCE-like spacecraft having a 1 m2 intake frontal area, a drag "
                "coefficient of 3.7, and 1.6 kW of power'"),
    _table1_row("REF-T1-CRANDALL", "Crandall", 53, "0-90 deg inclination", [160.0, 250.0], [7.5, 10.5],
                [0.01, 0.1], 0.01, [3.0, 6.0]),
)

# --------------------------------------------------------------------------------------------------------------------
# Declared reference cases: only (A_ref, C_D) pairs that the SAME source states together. No cross-source pairing.
# --------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceCase:
    case_id: str
    record_id: str
    a_ref_m2: float
    cd: float
    a_ref_scope: str          # "includes_intake" | "body_excluding_intake" | "unstated"
    source: str
    evidence_level: int
    quantity_type: str
    array_treatment: str
    note: str = ""


_SCOPES = ("includes_intake", "body_excluding_intake", "unstated")

CASES = (
    ReferenceCase("RC-ROMANO2018", "REF-ROMANO2018", 1.0, 2.2, "includes_intake", "SRC-ROMANO-2018 Sect. 1.1 and 2.4, Eq. 1",
                  6, "assumed", "arrays parallel to flight, neglected (source assumption)",
                  "worst condition, full accommodation (source wording)"),
    ReferenceCase("RC-VAIDYA-GOCELIKE", "REF-T1-VAIDYA", 1.0, 3.7, "includes_intake",
                  "SRC-ANDREUSSI-2022 Sect. 2 and Table 1 (Vaidya [52], not accessed)", 5, "as-reported (secondary)",
                  "not stated (TBD)", "'1 m2 intake frontal area' -> reference area treated as containing the intake"),
    ReferenceCase("RC-DICARA-ESA", "REF-T1-DICARA", 1.0, 2.0, "unstated", "SRC-ANDREUSSI-2022 Table 1 (Di Cara [43])", 5,
                  "as-reported (secondary)", "not stated (TBD)",
                  "1 m2 frontal with a 0.6 m2 intake: whether A_f contains the intake is not stated"),
    ReferenceCase("RC-DIAMANT", "REF-T1-DIAMANT", 0.5, 2.2, "unstated", "SRC-ANDREUSSI-2022 Table 1 (Diamant [45])", 5,
                  "as-reported (secondary)", "not stated (TBD)"),
    ReferenceCase("RC-SCHONHERR", "REF-T1-SCHONHERR", 0.3, 2.2, "unstated",
                  "SRC-ANDREUSSI-2022 Table 1 (Schonherr [47])", 5, "as-reported (secondary)", "not stated (TBD)"),
    ReferenceCase("RC-NISHIYAMA", "REF-T1-NISHIYAMA", 1.5, 2.0, "unstated", "SRC-ANDREUSSI-2022 Table 1 (Nishiyama [5])",
                  5, "as-reported (secondary)", "not stated (TBD)"),
    ReferenceCase("RC-TISAEV-LOW", "REF-T1-TISAEV", 0.1, 3.2, "unstated", "SRC-ANDREUSSI-2022 Table 1 (Tisaev [50])", 5,
                  "as-reported (secondary)", "not stated (TBD)", "lower end of the tabulated C_D range 3.2-4.2"),
    ReferenceCase("RC-TISAEV-HIGH", "REF-T1-TISAEV", 0.1, 4.2, "unstated", "SRC-ANDREUSSI-2022 Table 1 (Tisaev [50])",
                  5, "as-reported (secondary)", "not stated (TBD)", "upper end of the tabulated C_D range 3.2-4.2"),
)
CASE_BY_ID = {c.case_id: c for c in CASES}

INTAKE_ACCOUNTING = ("separate_term", "contained_in_reference")

# --------------------------------------------------------------------------------------------------------------------
# Evaluator
# --------------------------------------------------------------------------------------------------------------------


def _req_pos(name, x, allow_zero=False):
    if x is None:
        raise ValueError(f"{name} is required (no default)")
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"{name} must be a number")
    xf = float(x)
    if not math.isfinite(xf) or xf < 0.0 or (xf == 0.0 and not allow_zero):
        raise ValueError(f"{name} must be finite and {'>= 0' if allow_zero else '> 0'}; got {x!r}")
    return xf


def reference_drag(case_id: str, *, rho_kg_m3: float, v_rel_m_s: float, intake_projected_area_m2: float,
                   intake_cd: float, intake_source: str, atmosphere_state: dict, intake_accounting: str) -> dict:
    """Parametric drag of a declared reference case at ONE caller-supplied atmospheric/orbit state.

    ``rho_kg_m3`` and ``v_rel_m_s`` come from the orbit-resolved atmosphere (caller); ``atmosphere_state`` must name
    that state (``{"source": ..., "state_id": ...}``) so thrust and drag can be paired at the same state (S6.15).
    The intake term (``intake_projected_area_m2``, ``intake_cd``, ``intake_source``) is supplied by the caller (F1).

    ``intake_accounting``:
      * ``"separate_term"``: D_total = D_reference + D_intake. Refused for a case whose A_ref includes the intake.
      * ``"contained_in_reference"``: D_intake is reported but not added. Refused for a case whose A_ref excludes it.
      For cases with ``a_ref_scope == "unstated"`` either is accepted and the result is flagged
      ``INTAKE_OVERLAP_UNRESOLVED``.
    """
    if case_id not in CASE_BY_ID:
        raise KeyError(f"unknown reference case {case_id!r}; declared: {sorted(CASE_BY_ID)}")
    case = CASE_BY_ID[case_id]
    rho = _req_pos("rho_kg_m3", rho_kg_m3)
    v = _req_pos("v_rel_m_s", v_rel_m_s)
    a_int = _req_pos("intake_projected_area_m2", intake_projected_area_m2, allow_zero=True)
    cd_int = _req_pos("intake_cd", intake_cd, allow_zero=True)
    if not isinstance(intake_source, str) or not intake_source.strip():
        raise ValueError("intake_source is required: cite the F1 record that supplies the intake area and C_D")
    if not isinstance(atmosphere_state, dict) or not atmosphere_state.get("source") or not atmosphere_state.get(
            "state_id"):
        raise ValueError("atmosphere_state must be a dict with non-empty 'source' and 'state_id' (orbit-resolved state)")
    if intake_accounting not in INTAKE_ACCOUNTING:
        raise ValueError(f"intake_accounting must be one of {INTAKE_ACCOUNTING}; got {intake_accounting!r}")
    if intake_accounting == "separate_term" and case.a_ref_scope == "includes_intake":
        raise ValueError(f"{case_id}: A_ref already includes the intake; adding a separate intake term double-counts")
    if intake_accounting == "contained_in_reference" and case.a_ref_scope == "body_excluding_intake":
        raise ValueError(f"{case_id}: A_ref excludes the intake; the intake term must be added separately")

    q = 0.5 * rho * v * v
    d_ref = q * case.cd * case.a_ref_m2
    d_int = q * cd_int * a_int
    added = intake_accounting == "separate_term"
    d_tot = d_ref + (d_int if added else 0.0)
    flags = []
    if case.a_ref_scope == "unstated":
        flags.append("INTAKE_OVERLAP_UNRESOLVED")
    if case.quantity_type in ("as-reported (secondary)", "assumed"):
        flags.append(f"CD_{'SECONDARY' if case.quantity_type.startswith('as-reported') else 'ASSUMED'}")
    return {
        "schema": SCHEMA, "status": STATUS, "freeze_status": FREEZE_STATUS, "label": LABEL,
        "case_id": case.case_id, "record_id": case.record_id,
        "atmosphere_state": dict(atmosphere_state),
        "inputs": {"rho_kg_m3": rho, "v_rel_m_s": v, "intake_projected_area_m2": a_int, "intake_cd": cd_int,
                   "intake_source": intake_source, "intake_accounting": intake_accounting},
        "q_Pa": q,
        "reference_term": {"cd": case.cd, "a_ref_m2": case.a_ref_m2, "a_ref_scope": case.a_ref_scope,
                           "D_N": d_ref, "source": case.source, "evidence_level": case.evidence_level,
                           "quantity_type": case.quantity_type, "array_treatment": case.array_treatment},
        "intake_term": {"D_N": d_int, "added_to_total": added, "owner": "F1 (caller-supplied)"},
        "D_total_N": d_tot, "D_total_mN": d_tot * 1e3,
        "flags": flags,
        "rfp_thrust_band_mN": {"min": RFP_THRUST_BAND["min_mN"], "max": RFP_THRUST_BAND["max_mN"],
                               "requirement_status": RFP_THRUST_BAND["requirement_status"]},
    }


def statewise_margin(thrust_available_N: float, drag_result: dict, *, thrust_state: dict,
                     thrust_source: str) -> dict:
    """S6.15 margin T_available(state) - D(state) for ONE state, against a REFERENCE drag only.

    Refuses to pair thrust and drag from different atmospheric/orbit states. The result is never a gate verdict:
    ``freeze_status`` stays NOT_EVALUATED until the host-spacecraft ICD exists (S6.18).
    """
    t = _req_pos("thrust_available_N", thrust_available_N, allow_zero=True)
    if not isinstance(thrust_source, str) or not thrust_source.strip():
        raise ValueError("thrust_source is required")
    if not isinstance(drag_result, dict) or drag_result.get("status") != STATUS:
        raise ValueError("drag_result must come from reference_drag()")
    if not isinstance(thrust_state, dict) or thrust_state != drag_result["atmosphere_state"]:
        raise ValueError("thrust and drag must be evaluated at the same atmospheric/orbit state (S6.15)")
    m = t - drag_result["D_total_N"]
    return {"schema": SCHEMA, "status": STATUS, "freeze_status": FREEZE_STATUS, "label": LABEL,
            "case_id": drag_result["case_id"], "state": dict(thrust_state), "thrust_source": thrust_source,
            "T_available_N": t, "D_N": drag_result["D_total_N"], "margin_N": m,
            "nonnegative_against_reference": m >= 0.0,
            "note": "reference/parametric indication only; AG-13 closure needs the host-spacecraft ICD (S6.18)"}


def density_free_table() -> list:
    """Atmosphere-free summary per declared case: C_D*A_ref and the dynamic pressure q* at which the reference term
    alone equals the owner-stated 12 and 25 mN band edges (q* = T / (C_D A_ref)). Intake term excluded."""
    rows = []
    for c in CASES:
        cda = c.cd * c.a_ref_m2
        rows.append({"case_id": c.case_id, "record_id": c.record_id, "cd": c.cd, "a_ref_m2": c.a_ref_m2,
                     "cd_a_m2": round(cda, 6), "a_ref_scope": c.a_ref_scope,
                     "q_at_12mN_Pa": round(RFP_THRUST_BAND["min_mN"] * 1e-3 / cda, 9),
                     "q_at_25mN_Pa": round(RFP_THRUST_BAND["max_mN"] * 1e-3 / cda, 9),
                     "evidence_level": c.evidence_level, "quantity_type": c.quantity_type})
    return rows


FINDINGS = (
    {"id": "SRD-01", "finding": "abep_sim/mission_env.py Spacecraft defaults (bus_frontal_m2 = 0.25, bus_cd = 2.2, "
                                "intake_cd_ref = 2.05) and spacecraft_drag() array C_D 2.4 carry no source in that "
                                "module; this lane does not modify or call it. They are not REFERENCE/PARAMETRIC "
                                "records and must not be quoted as a spacecraft drag basis",
     "action": "owner/step-3 decision whether mission_env adopts a registered reference case (not done here)"},
    {"id": "SRD-02", "finding": "GOCE frontal area is reported as about 1 m2 and 0.8 m2 on the same ESA page and as "
                                "1.1 m2 by Romano 2018 (citing the CDR); the conflict is carried as an interval",
     "action": "none; no GOCE drag case is declared because no source pairs a GOCE flight C_D with its area"},
    {"id": "SRD-03", "finding": "C_D spans 2.0-4.2 across the declared reference cases (C_D*A_ref 0.32-3.7 m^2); the "
                                "sources read do not state the GSI/accommodation basis of most values, so the spread "
                                "cannot be attributed to physics or convention and is not measurement scatter",
     "action": "parametric studies evaluate all declared cases (envelope), no single 'representative' case"},
    {"id": "SRD-04", "finding": "Several reference areas already contain the intake (Romano: A_f = A_in); naive "
                                "addition of an F1 intake term double-counts",
     "action": "enforced by the required intake_accounting argument"},
    {"id": "SRD-05", "finding": "A closed-form Sentman flat-plate C_D (Sinpetru 2022 Eq. 6-7) was considered but not "
                                "implemented: the incident-temperature definition is not recoverable from the text "
                                "read, and implementing it from memory would violate rule 6",
     "action": "open item; implement only from a fully read open source"},
)

OPEN_ITEMS = (
    "AG-13 closure requires the host-spacecraft ICD (body frontal geometry, intake projected area, arrays/deployed "
    "surfaces, attitude/pointing states, C_D/model basis, accommodation/surface state) - S6.18",
    "Orbit-resolved atmosphere producer (S6.14) supplies rho and v_rel; no state evaluated here",
    "SLATS frontal area and C_D: not in the open sources read",
    "Vaidya 2022 (GOCE-like C_D 3.7) not accessed; derivation TBD",
    "Sentman / DRIA flat-plate closed form from a fully readable open source (SRD-05)",
)


def build_document() -> dict:
    """Deterministic JSON body (no timestamps beyond the fixed retrieval date)."""
    return {
        "schema": SCHEMA, "status": STATUS, "freeze_status": FREEZE_STATUS, "label": LABEL,
        "lane": "reference spacecraft drag basis (A9.16 parallel lane)",
        "retrieval_date": RETRIEVAL_DATE,
        "decisions": list(DECISIONS),
        "scope": {
            "is": "documented/public/official spacecraft geometry and C_D basis for INTERIM PARAMETRIC drag studies",
            "is_not": "the flight/host spacecraft, an ICD, a drag closure, or an AG-13 verdict",
            "drag_equation": "D = 0.5 rho v_rel^2 C_D A_ref (Romano 2018 Eq. 1) + caller-supplied intake term (F1)",
            "atmosphere_interface": "rho_kg_m3, v_rel_m_s and atmosphere_state supplied by the caller from the "
                                    "orbit-resolved atmosphere; this module imports no atmosphere module",
        },
        "rfp_thrust_band": RFP_THRUST_BAND,
        "sources": SOURCES,
        "not_accessed": list(NOT_ACCESSED),
        "records": list(RECORDS),
        "cases": [c.__dict__ for c in CASES],
        "density_free_table": density_free_table(),
        "findings": list(FINDINGS),
        "open_items": list(OPEN_ITEMS),
    }


def case(case_id: str) -> Optional[ReferenceCase]:
    return CASE_BY_ID.get(case_id)


def _integrity() -> None:
    """Every case maps to a record whose stated (A_ref, C_D) contains the case pair (no cross-source pairing)."""
    recs = {r["id"]: r for r in RECORDS}
    for c in CASES:
        if c.a_ref_scope not in _SCOPES:
            raise ValueError(f"{c.case_id}: bad a_ref_scope")
        r = recs.get(c.record_id)
        if r is None:
            raise ValueError(f"{c.case_id}: unknown record {c.record_id}")
        a, cd = r["frontal_area_m2"]["value"], r["cd"]["value"]
        cds = cd if isinstance(cd, list) else [cd]
        if a != c.a_ref_m2 or c.cd not in cds:
            raise ValueError(f"{c.case_id}: (A_ref, C_D) not stated together by record {c.record_id}")


_integrity()
