"""Build the D-X5 evidence dossier JSON (fo_dx5_cross_section_evidence, trigger T_DX5_EVIDENCE).

Deterministic: reads only committed files
  docs/chemistry/n2_domain_extension/dx5/dx5_sources_v1.json    (committed source list; adversarially confirmed sources only)
  docs/chemistry/n2_domain_extension/domain_extension_requirements.json   (lane-01, read-only)
  docs/chemistry/n2_domain_extension/domain_extension_audit.json          (lane-01, read-only)
  docs/v2/question_a/QUESTION_A_DISPOSITION.json                          (owner disposition A-NO, read-only)
  scripts/audit_n2_completeness_final.py                                  (TABLE6 last row, read as text)
and writes docs/chemistry/n2_domain_extension/dx5/dx5_evidence_v1.json and DX5_EVIDENCE.md (rendered from the same data).

  python docs/chemistry/n2_domain_extension/dx5/build_dx5_evidence.py           # write
  python docs/chemistry/n2_domain_extension/dx5/build_dx5_evidence.py --check   # reproduce and compare, exit 1 on mismatch

Evidence only. This changes no chemistry table, validity limit, pre-registration or v1 result, proposes no such change, and
decides nothing. Whether the reopening condition of Question A is met is the OWNER's decision (status DRAFT_PENDING_OWNER).
"""
import hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
REL = {
    "sources": "docs/chemistry/n2_domain_extension/dx5/dx5_sources_v1.json",
    "requirements": "docs/chemistry/n2_domain_extension/domain_extension_requirements.json",
    "audit": "docs/chemistry/n2_domain_extension/domain_extension_audit.json",
    "disposition": "docs/v2/question_a/QUESTION_A_DISPOSITION.json",
    "table6_script": "scripts/audit_n2_completeness_final.py",
}
OUT = os.path.join(HERE, "dx5_evidence_v1.json")
STATUSES = ("GAP_CLOSED", "GAP_MATERIALLY_NARROWED", "GAP_UNCHANGED")
ACCESS = ("open", "abstract_only", "not_accessed")
EVIDENCE_CODES = ("measured", "measured_secondary", "measured_not_accessed", "evaluated", "evaluated_secondary",
                  "evaluated_digitized", "evaluated_not_accessed", "model_derived", "inferred", "review", "bibliographic",
                  "secondary_statement", "not_accessed")
ROT = ["excitation_N2_rot_j0_to_j2.dat", "excitation_N2_rot_j0_to_j4.dat"]
ELEC = ["excitation_N2_A3Sigma_u.dat", "excitation_N2_B3Pi_g.dat", "excitation_N2_W3Delta_u.dat",
        "excitation_N2_Bprime3Sigma_u.dat", "excitation_N2_aprime1Sigma_u.dat", "excitation_N2_a1Pi_g.dat",
        "excitation_N2_w1Delta_u.dat", "excitation_N2_C3Pi_u.dat"]
VIB = "excitation_N2_vib_0_to_1.dat"


def _p(k):
    return os.path.join(ROOT, REL[k])


def _sha(k):
    return hashlib.sha256(open(_p(k), "rb").read()).hexdigest()


def resolve(doc, path):
    x = doc
    for key in path:
        x = x[key]
    return x


class Quoter:
    """Quotes lane-01 / disposition fields verbatim as {name, value, from: [file, *path]}; tests re-resolve every one."""

    def __init__(self, docs):
        self.docs = docs

    def __call__(self, name, doc, *path):
        return {"name": name, "value": resolve(self.docs[doc], list(path)), "from": [REL[doc]] + list(path)}


def table6_last_row():
    txt = open(_p("table6_script")).read()
    m = re.search(r"\(10\.00, ([0-9.]+), ([0-9.]+)\)\]", txt)
    return float(m.group(1)), float(m.group(2))


def lane01_usage(audit):
    used = set()
    for t in audit["tables"].values():
        used.update(t.get("cited_sources", []))
        used.update(e["source"] for e in t.get("independent_evidence", []))
    return used


def shape_source(s, audit, used):
    key = s["lane01_source_key"]
    lane = {"cited_in_lane01": key is not None, "lane01_source_key": key,
            "lane01_access_label": audit["sources"][key]["access"] if key else None,
            "referenced_in_lane01_table_entries": bool(key and key in used)}
    return {"id": s["id"], "work_key": s["work_key"], "citation": s["citation"], "doi_or_url": s["doi_or_url"],
            "access": s["access"], "access_note": s["access_note"], "kind": s["kind"], "process": s["process"],
            "energy_range_eV": s["energy_range_eV"], "stated_uncertainty": s["stated_uncertainty"],
            "evidence_class": s["evidence_class"], "evidence_class_code": s["evidence_class_code"],
            "where_data_sit": s["quote_or_location"], "lane01": lane, "what_it_adds": s["what_it_adds"],
            "check_status": s["check_status"], "from_records": s["from_records"],
            "overrides_from_check": s["overrides_from_check"]}


def lane01_requirements(q):
    P1 = []
    for t in ROT:
        P1 += [q(t + " last source point (eV)", "requirements", "requirements", "per_table", t, "source_last_data_point_eV"),
               q(t + " declared model above", "requirements", "requirements", "per_table", t, "declared_model_above_last_point"),
               q(t + " hold envelope is upper bound", "requirements", "requirements", "per_table", t, "hold_envelope_is_upper_bound"),
               q(t + " share above last point (hold), L=45", "requirements", "requirements", "per_table", t, "by_limit", "45", "share_above_last_point_hold"),
               q(t + " share above last point (hold), L=60", "requirements", "requirements", "per_table", t, "by_limit", "60", "share_above_last_point_hold"),
               q(t + " E_req hold envelope, L=60", "requirements", "requirements", "per_table", t, "by_limit", "60", "hold_envelope_E_req_eV"),
               q(t + " E_req hold envelope, L=45", "requirements", "requirements", "per_table", t, "by_limit", "45", "hold_envelope_E_req_eV"),
               q(t + " coverage end (measured reading)", "requirements", "verdict_criteria", "per_table", t, "coverage_end_measured_reading_eV"),
               q(t + " coverage end (evaluated reading)", "requirements", "verdict_criteria", "per_table", t, "coverage_end_evaluated_reading_eV"),
               q(t + " independent sets passing into C1-C3", "requirements", "verdict_criteria", "per_table", t, "independent_sets"),
               q(t + " lane-01 verdict", "audit", "tables", t, "verdict"),
               q(t + " what would change the verdict", "audit", "tables", t, "what_would_change_the_verdict")]
    P1 += [q("rotational independent comparison note", "requirements", "independent_comparisons", "rotational", "note"),
           q("newly covered OOD runs, all capped tables except rotational raised to L=150", "requirements", "hypothetical_coverage", "limits", "150", "all_capped_except_rotational_at_L", "newly_covered_ood_runs"),
           q("newly covered OOD runs, all capped tables raised to L=60", "requirements", "hypothetical_coverage", "limits", "60", "all_capped_tables_at_L", "newly_covered_ood_runs"),
           q("verdict rule C1 coverage", "requirements", "verdict_criteria", "rule", "C1_coverage"),
           q("verdict rule C2 shape", "requirements", "verdict_criteria", "rule", "C2_shape"),
           q("verdict rule C3 join", "requirements", "verdict_criteria", "rule", "C3_join"),
           q("E_req definition", "requirements", "requirements", "note")]
    P2 = []
    for t in ELEC:
        P2 += [q(t + " last source point (eV)", "requirements", "requirements", "per_table", t, "source_last_data_point_eV"),
               q(t + " declared model above", "requirements", "requirements", "per_table", t, "declared_model_above_last_point"),
               q(t + " E_req hold envelope, L=60", "requirements", "requirements", "per_table", t, "by_limit", "60", "hold_envelope_E_req_eV"),
               q(t + " independent sets (join vs C3)", "requirements", "verdict_criteria", "per_table", t, "independent_sets"),
               q(t + " coverage end (measured reading)", "requirements", "verdict_criteria", "per_table", t, "coverage_end_measured_reading_eV"),
               q(t + " coverage end (evaluated reading)", "requirements", "verdict_criteria", "per_table", t, "coverage_end_evaluated_reading_eV"),
               q(t + " lane-01 verdict", "audit", "tables", t, "verdict")]
        if "MS1997_over_table_E_ge_100" in resolve(q.docs["requirements"], ["independent_comparisons", "electronic_MS1997_and_Tabata2006", t]):
            P2.append(q(t + " MS1997/table for E >= 100 eV", "requirements", "independent_comparisons", "electronic_MS1997_and_Tabata2006", t, "MS1997_over_table_E_ge_100"))
    P2 += [q("newly covered OOD runs, all capped tables except electronic raised to L=150", "requirements", "hypothetical_coverage", "limits", "150", "all_capped_except_electronic_at_L", "newly_covered_ood_runs")]
    P3 = [q(VIB + " last source point (eV)", "requirements", "requirements", "per_table", VIB, "source_last_data_point_eV"),
          q(VIB + " declared model above", "requirements", "requirements", "per_table", VIB, "declared_model_above_last_point"),
          q(VIB + " E_req note (L=60)", "requirements", "requirements", "per_table", VIB, "by_limit", "60", "note"),
          q(VIB + " flat-sigma E_req reference, L=60", "requirements", "requirements", "per_table", VIB, "by_limit", "60", "flat_sigma_E_req_eV"),
          q(VIB + " verdict-criteria applicability", "requirements", "verdict_criteria", "per_table", VIB, "reason"),
          q("non-resonant comparison fit", "requirements", "independent_comparisons", "vibrational_0to1_Tabata2006_n2-5", "fit")]
    for te in ("30", "40", "60"):
        P3 += [q("Tabata non-resonant 5-48.5 eV / Laporta 0->1, T_e=" + te + " eV (zero beyond 48.5 eV)", "requirements", "independent_comparisons", "vibrational_0to1_Tabata2006_n2-5", "rows", te, "Tabata_5_to_48p5eV_over_Laporta"),
               q("Tabata non-resonant >5 eV / Laporta 0->1, T_e=" + te + " eV (held beyond 48.5 eV)", "requirements", "independent_comparisons", "vibrational_0to1_Tabata2006_n2-5", "rows", te, "Tabata_above_5eV_hold_beyond_48p5_over_Laporta")]
    P3 += [q(VIB + " lane-01 verdict", "audit", "tables", VIB, "verdict"),
           q("newly covered OOD runs, all capped tables except vibrational raised to L=150", "requirements", "hypothetical_coverage", "limits", "150", "all_capped_except_vibrational_at_L", "newly_covered_ood_runs")]
    return {"P1": P1, "P2": P2, "P3": P3}


def computed_p1():
    s02, s04 = table6_last_row()
    t51 = {  # Itikawa et al. 1986 Table 5.1 (1e-16 cm2) and Siegel et al. 1978 Table 1 (A^2 = 1e-16 cm2) at 10 eV
        "onda_truhlar": (3.86, 1.35), "rumble_truhlar_morrison": (3.84, 0.99), "siegel_dehmer_dill": (4.54, 1.03),
        "tanaka_prelim_exp": (4.4, 0.8)}
    return {"basis": "10 eV join; independent values from P1:itikawa1986_table5_1 (Onda & Truhlar, Rumble et al., Tanaka et al. preliminary) and P1:siegel_dehmer_dill_1978 Table 1; table value = Song 2023 Table 6 last row (10 eV) as committed in scripts/audit_n2_completeness_final.py TABLE6",
            "song2023_table6_10eV_1e-16cm2": {"j0_to_2": s02, "j0_to_4": s04},
            "independent_over_table_at_10eV": {k: {"j0_to_2": round(v[0] / s02, 3), "j0_to_4": round(v[1] / s04, 3)}
                                               for k, v in t51.items()},
            "note": "No independent set and not Song Table 6 states an uncertainty, so C3 (join within stated uncertainty) cannot be evaluated as lane-01 defines it."}


FINDINGS = {
    "P1": {
        "coverage": [
            "Openly accessible evidence above 10 eV is theory only, to 50 eV: Itikawa et al. 1986 Table 5.1 reproduces Onda & Truhlar (1979/1980) and Rumble, Truhlar & Morrison (1983) for j0->2, 0->4, 0->6 at 10-50 eV [P1:itikawa1986_table5_1]; Siegel, Dehmer & Dill 1978 (ANL-78-65) gives j0->2/4/6 to 30 eV [P1:siegel_dehmer_dill_1978].",
            "The only measured rotational ICS above 10 eV found is the preliminary Tanaka, Boesten & Shimamura 1980 conference/private-communication set (5, 10, 20 eV), reproduced secondarily in Itikawa 1986; the compilers state it must be confirmed [P1:tanaka_boesten_shimamura_1980].",
            "Share of the held j0->2 table rate above 50 eV (recomputed by the check from repo TABLE6 with hold beyond 10 eV): 50.77 % at L = 45 eV and 64.77 % at L = 60 eV; above 200 eV 0.98 % / 4.06 %; above 266 eV 0.14 % / 0.99 % [P1 check correction].",
            "Every source whose stated range reaches the lane-01 E_req is closed / abstract-only: Kutz & Meyer 1995 (theory, 0.01-1000 eV) [P1:kutz_meyer_1995], Bhattacharyya & Goswami 1982 (eikonal theory, ICS 20-200 eV) [P1:bhattacharyya_goswami_1982], Gote & Ehrhardt 1995 (the only measurement: state-to-state DCS 10-200 eV, 10-160 deg) [P1:gote_ehrhardt_1995], Choi et al. 1979 (50-500 eV; rotational tabulation not shown) [P1:choi_poe_sun_shan_1979].",
        ],
        "join_and_shape": [
            "At the 10 eV join every independent j0->2 value lies above Song Table 6 (ratios 1.22-1.44; see computed.P1), with no stated uncertainty anywhere, so C3 cannot be evaluated.",
            "Theory shape 10-50 eV contradicts the flat hold: j0->2 falls to 0.42-0.43 of its 10 eV value by 50 eV; j0->4 dips at 20 eV then rises to 1.0-1.4x; j0->6 (absent from the table set) grows to 0.24-0.34e-16 cm2 at 30-50 eV [P1:itikawa1986_table5_1]. Kutz & Meyer and Gote & Ehrhardt abstracts report rotational rainbows / large angular-momentum transfer at higher energy [P1:kutz_meyer_1995, P1:gote_ehrhardt_1995].",
            "The Born point-quadrupole (Gerjuoy & Stein 1955) estimate is a slow-electron threshold theory (abstract), not a usable envelope above 10 eV [P1:gerjuoy_stein_1955]; Glauber/long-range-only models underestimate at 10-50 eV [P1:gianturco_lamanna_rahman].",
            "Song 2023 Table 4 (measured-based vibrationally elastic ICS to 1000 eV, 10-20 %) bounds the rotational sum only by inference [P1:song2023_jpcrd].",
        ],
        "requirement_met_by_confirmed_sources": False,
        "requirement_met_justification": "No confirmed accessible source provides rotational cross sections above 50 eV; lane-01 E_req at L = 60 eV is 266 / 668 / 1244 eV (1e-2 / 1e-6 / 1e-12, hold envelope), and C3 cannot be evaluated because no set states an uncertainty. The rotational tables stay UNRESOLVED-BY-SOURCE under the lane-01 criteria; the structural blocker (at most 37 of 714 v1 OOD runs recoverable with the rotational cap) is unchanged.",
        "sub_material_changes": [
            "Open theory coverage extends from 10 eV to 50 eV (lane-01 had none above 10 eV).",
            "Evidence (theory only) that the flat hold is not conservative channel by channel and that a two-transition table is incomplete above ~30 eV (j0->6).",
            "Access facts: Itikawa et al. 1986 and Majeed & Strickland 1997 full texts are openly available as NIST SRD JPCRD reprints (lane-01 labelled them not accessed / abstract only).",
        ],
        "legitimate_access_candidates": ["P1:kutz_meyer_1995", "P1:gote_ehrhardt_1995", "P1:bhattacharyya_goswami_1982",
                                         "P1:choi_poe_sun_shan_1979", "P1:itikawa_mason_2005", "P1:itikawa2006"],
    },
    "P2": {
        "coverage": [
            "Seven non-a1Pi_g states (A, B, W, B', a', w, C): no open, measured, state-resolved direct-excitation ICS above 100 eV was found. For A, W, B', a' and w no measurement or calculation above 100 eV was found at all (B3Pi_g emission to 450 eV was REJECTED by the check: the 450 eV range belongs to N2+ bands).",
            "Only two open evaluated sets reach above 100 eV for all eight states: Majeed & Strickland 1997 (full text open; built on Cartwright 1977 ICS measured at 10-50 eV, not renormalized, extrapolated by an undocumented method, no uncertainty) [P2:majeed_strickland1997] and the Kawaguchi 2018 thesis set (swarm-adjusted, anchored on Johnson at 100 eV, extrapolated above; identity with PSST 2021 not verified) [P2:kawaguchi2018_thesis]. Neither is measured above 100 eV, and they disagree (thesis/repo continuation 0.29-1.42 at 400-1000 eV).",
            "a1Pi_g: Ajello et al. 2020 gives an inferred, EEL-independent 200 eV point, 4.2e-18 cm2 = 1.23x Johnson (3.41 +- 0.87e-18), composite ~35 % [P2:ajello2020]. Measurements above 200 eV exist only as abstracts: Oda & Osawa 1981 (EEL-GOS, 500-2000 eV) [P2:oda_osawa1981], Skerbele & Lassettre 1970 (DCS/GOS 300-500 eV, Born holds) [P2:skerbele_lassettre1970], Holland 1969 (apparent LBH emission, 900 eV absolute, shape to 2 keV) [P2:holland1969]; Chung & Lin 1972 (Born-Ochkur to 2 keV for singlets) is theory [P2:chung_lin1972]. Ajello & Shemansky 1985 (open reprint) has measured data only to 200 eV plus an analytic fit [P2:ajello_shemansky1985].",
            "C3Pi_u: Fons et al. 1996 (absolute 2PG apparent excitation to 600 eV, 13-20 %) is abstract-only [P2:fons1996]; Imami & Borst 1974 (to 1 keV) is seen only as a digitized secondary figure without uncertainty [P2:imami_borst1974].",
        ],
        "join_and_shape": [
            "Conflict resolution is documentary and partial: the Johnson/MS1997 factors 0.17-3.8 trace to MS1997's un-renormalized, extrapolated Cartwright 1977 data (Trajmar 1983 renormalization changes those by up to 2x) [P2:majeed_strickland1997, P2:itikawa1986]; Kato et al. 2010 (independent DCS, 20-40 eV) support the data behind Johnson in-domain [P2:kato2010]. Kawaguchi is not an independent third measurement.",
            "a1Pi_g at 100 eV: Ajello 2017 (open) 7.37e-18 cm2 vs Johnson 7.16 +- 1.29e-18 (ratio 1.03) [P2:ajello2017]; Ajello & Shemansky 1985 6.22 +- 1.37e-18 [P2:ajello_shemansky1985].",
            "New inferred conflict (a' + w): the cascade into a1Pi_g measured by Ajello 2017 (>= 3.30e-18 cm2 at 100 eV) is ~3.3x Johnson's a'+w sum (~1.00e-18); Ajello 2020 cascade emission (1.7e-18 at 200 eV) implies ~2.6-3.3x (inferred, CIET- and pressure-dependent) [P2:ajello2017, P2:ajello2020].",
            "New shape indicators: Holland's apparent LBH ratios sigma(900)/sigma(100) = 0.164 and sigma(2000)/sigma(100) = 0.078 vs 0.095 / 0.041 for the table continuation (a tail ~1.7-1.9x shallower; partly cascade) [P2:holland1969]; the Imami & Borst C3Pi_u shape normalized at 100 eV is 1.29 / 1.69 / 2.8 / 5.7x the repo p = 2.47 continuation at 200 / 300 / 500 / 900 eV [P2:imami_borst1974].",
        ],
        "requirement_met_by_confirmed_sources": False,
        "requirement_met_justification": "No confirmed source gives cross sections with stated uncertainty, independent of Johnson and MS1997, that reach E_req (lane-01: >= 575 eV at 1e-6 and >= 1.15 keV at 1e-12 for every electronic table at L = 60 eV) for any of the eight tables; the seven UNRESOLVED-BY-SOURCE tables have no accessible independent set passing C3, and the a1Pi_g PARTIAL verdict rests on the same accessible evidence plus one inferred 200 eV point.",
        "sub_material_changes": [
            "Majeed & Strickland 1997 full text is open (NIST SRD reprint), documenting the origin of the MS1997/Johnson conflict.",
            "Open Kawaguchi 2018 thesis set (evaluated, vector-digitized) gives a second evaluated tail opinion to ~0.5-1 keV (not independent at 100 eV).",
            "An independent inferred a1Pi_g point at 200 eV (Ajello 2020) consistent with Johnson; new inferred a'+w and a1Pi_g / C3Pi_u shape conflicts.",
        ],
        "legitimate_access_candidates": ["P2:oda_osawa1981", "P2:fons1996", "P2:chung_lin1972", "P2:holland1969",
                                         "P2:skerbele_lassettre1970", "P2:kawaguchi2021"],
    },
    "P3": {
        "coverage": [
            "What the table omits above ~5 eV is the 2Sigma_u shape resonance near 20-22 eV [P3:tanaka1981, P3:burke1983, P3:gillan1987, P3:malegat1988] and polarization-dominated non-resonant scattering at >= ~33 eV [P3:truhlar1972_V, P3:truhlar1977]; Laporta 2014 excludes both by construction (Eq. (9) background is vibrationally elastic only) [P3:laporta2014].",
            "The only new, confirmed, openly accessible quantitative evidence is Itikawa et al. 1986 Fig. 6.1: two renormalized Truhlar et al. 1977 measured 0->1 points, ~9e-19 cm2 at ~50 eV and ~6.7e-19 cm2 at ~75 eV, digitized (+/-10-15 %), no stated uncertainty, same Itikawa/JPL lineage as the Tabata fit (not independent) [P3:itikawa1986, P3:truhlar1977].",
            "No measured non-resonant 0->1 value above ~75 eV and no non-resonant overtone measurement exist in the accessible literature (Itikawa 1986 Sec. 6.2); theory to 500 eV (Choi et al. 1979) is abstract-only and model-derived [P3:choi1979]. Song 2023 recommends Laporta only (Table 7 ends at 5 eV) [P3:song2023_jpcrd].",
        ],
        "join_and_shape": [
            "Independent recomputation by the check from the QST n2-5 points plus the ~75 eV point: omitted non-resonant (E > 5 eV) 0->1 rate / table 0->1 rate = 2.22 / 2.72 / 3.36 at T_e 30 / 40 / 60 eV (bridge to 74 eV, zero beyond) and 2.35 / 3.04 / 4.22 (power-law continuation) - narrowing the lane-01 bracket at T_e 30 eV from 2.05-2.50 to ~2.2-2.4; upper values depend on the unmeasured tail beyond 75 eV [P3 check correction].",
            "Theory 0->1 magnitudes (Rumble 1983; Burke 1983; Onda & Truhlar 1979) are 2-5x off the measured values at 30-50 eV (Onda & Truhlar v'=1+2 at 50 eV ~2.3e-18 cm2 vs ~0.9e-18 measured), so theory cannot set magnitudes; calculated 0->2/0->1 ~0.03 at 50 eV [P3:rumble1983, P3:burke1983, P3:onda_truhlar1979].",
            "Illustrative materiality context (not an audit result): with F_P_vib = 3.32e-4 at T_e 30 eV (audit/n2_completeness_final_v1.json) and 0->1 = 21.7 % of the resonant vibrational power, the non-resonant 0->1 F_P would be ~1.6-2e-4, below the pre-registered 1 % threshold; any real bound belongs to an owner-authorized pre-registered re-audit.",
        ],
        "requirement_met_by_confirmed_sources": False,
        "requirement_met_justification": "Lane-01 defines no table-specific E_req for the vibrational rate fits (flat reference 266 / 668 / 1244 eV at L = 60 eV); accessible non-resonant 0->1 data end at ~75 eV (digitized, no stated uncertainty, not independent of the Tabata lineage) and no non-resonant overtone data exist. The PARTIAL verdict (documented omission, completeness question) is unchanged.",
        "sub_material_changes": [
            "Measured-lineage non-resonant 0->1 coverage extends from 48.5 eV (Tabata n2-5 fit) to ~75 eV (Itikawa 1986 Fig. 6.1).",
            "Bracket of the omitted non-resonant 0->1 rate at T_e 30 eV narrows from 2.05-2.50 to ~2.2-2.4 x the table 0->1 rate.",
            "New theory/experiment conflict at 50 eV (~2.5x).",
        ],
        "legitimate_access_candidates": ["P3:middleton1992", "P3:truhlar1977", "P3:choi1979", "P3:kawaguchi2021",
                                         "P3:itikawa2006"],
    },
}

STATUS_RULE = ("GAP_CLOSED if the confirmed accessible sources meet the lane-01 requirement (C1 coverage at the declared "
               "E_req with C3/C2 evaluable) for the priority's tables; otherwise GAP_MATERIALLY_NARROWED if the adversarial "
               "check confirmed a material improvement (material_improvement_confirmed = true); otherwise GAP_UNCHANGED. "
               "Sub-material changes (knowledge, access, conflicts) are listed separately and do not change the status.")


def status_for(pk, pri):
    f = FINDINGS[pk]
    if f["requirement_met_by_confirmed_sources"]:
        return "GAP_CLOSED"
    if pri["check"]["material_improvement_confirmed"]:
        return "GAP_MATERIALLY_NARROWED"
    return "GAP_UNCHANGED"


def build():
    docs = {k: json.load(open(_p(k))) for k in ("sources", "requirements", "audit", "disposition")}
    q = Quoter(docs)
    src, audit = docs["sources"], docs["audit"]
    used = lane01_usage(audit)
    reqs = lane01_requirements(q)
    disp = docs["disposition"]
    out = {
        "id": "dx5_evidence_v1",
        "status": "DRAFT_PENDING_OWNER",
        "follow_on": "fo_dx5_cross_section_evidence",
        "trigger": "T_DX5_EVIDENCE",
        "generated_by": "docs/chemistry/n2_domain_extension/dx5/build_dx5_evidence.py",
        "inputs_sha256": {REL[k]: _sha(k) for k in REL},
        "non_gating": True,
        "scope_statement": ("Evidence dossier only. No chemistry table, validity limit, pre-registration or v1 result is changed "
                            "or proposed as changed. The P5-N2 v1 outcome (all nine candidates INCONCLUSIVE / NOT ELIGIBLE, "
                            "credible set empty) is permanent. The owner disposition A-NO stands; this dossier decides nothing."),
        "search_rules": [q("D-X5 rules", "disposition", "D-X5_rules"),
                         "no LXCat website or data used; no author/lab contact; no email; no paywall or bot-challenge bypass "
                         "(abstract-only access labelled 'abstract_only'); TLS/trust settings unchanged; anything from memory marked 'verify'"],
        "owner_priorities": q("D-X5 bounded priorities", "disposition", "D-X5_bounded_priorities"),
        "vocabulary": {"access": list(ACCESS), "evidence_class_code": list(EVIDENCE_CODES), "status": list(STATUSES)},
        "status_rule": STATUS_RULE,
        "curation": {"curated_by": src["curated_by"], "raw_records_sha256": src["raw_records_sha256"],
                     "raw_records_location": src["raw_records_location"],
                     "rule": "only sources the adversarial checks confirmed are used; rejected and unconfirmed records are listed and never used"},
        "computed": {"P1": computed_p1()},
        "priorities": {},
    }
    for pk in ("P1", "P2", "P3"):
        pri = src["priorities"][pk]
        f = FINDINGS[pk]
        out["priorities"][pk] = {
            "priority_statement": pri["priority_statement"],
            "status": status_for(pk, pri),
            "status_justification": f["requirement_met_justification"] + (
                " The adversarial check confirmed no material improvement (material_improvement_confirmed = false)."
                if not pri["check"]["material_improvement_confirmed"] else ""),
            "requirement_met_by_confirmed_sources": f["requirement_met_by_confirmed_sources"],
            "check_material_improvement_confirmed": pri["check"]["material_improvement_confirmed"],
            "lane01_requirement": reqs[pk],
            "findings_coverage": f["coverage"],
            "findings_join_shape_conflicts": f["join_and_shape"],
            "sub_material_changes": f["sub_material_changes"],
            "legitimate_access_candidates_owner_decision": f["legitimate_access_candidates"],
            "sources": [shape_source(s, audit, used) for s in pri["sources"]],
            "rejected_never_used": pri["rejected"],
            "unconfirmed_never_used": pri["unconfirmed_not_used"],
            "adversarial_check": {k: pri["check"][k] for k in ("record", "record_sha256", "checker", "corrections",
                                                                "material_improvement_confirmed", "assessment")},
            "search_log": pri["search_log"],
        }
    p4 = src["priorities"]["P4"]
    out["priorities"]["P4"] = {"priority_statement": p4["priority_statement"], "status": "DEFERRED per owner ordering",
                               "searched": p4["searched"], "status_justification": p4["reason"], "sources": [],
                               "rejected_never_used": [], "unconfirmed_never_used": [], "search_log": []}
    out["reopening_condition_of_question_a"] = {
        "status": "DRAFT_PENDING_OWNER",
        "decided_here": False,
        "who_decides": "owner",
        "condition": q("reopening condition", "disposition", "reopening_condition"),
        "current_disposition": q("decision", "disposition", "decision"),
        "evidence_facts": [
            "Rotational (P1): newly located open evidence above 10 eV is model-derived theory to 50 eV (two sets reproduced in Itikawa et al. 1986 Table 5.1; Siegel, Dehmer & Dill 1978 to 30 eV) plus one preliminary measurement to 20 eV; lane-01 E_req at L = 60 eV is 266 / 668 / 1244 eV; sources reaching that range (Kutz & Meyer 1995; Gote & Ehrhardt 1995; Bhattacharyya & Goswami 1982; Choi et al. 1979) are abstract-only. Status GAP_UNCHANGED under the stated rule.",
            "Electronic (P2): no open, independent, measured cross sections with stated uncertainty above 100 eV for any of the eight states; a1Pi_g gains one inferred open 200 eV point (Ajello 2020, 1.23x Johnson); the Johnson / MS1997 conflict is explained documentarily (un-renormalized, extrapolated Cartwright 1977 data) but not resolved by new data above 100 eV; new inferred conflicts (a'+w cascade, a1Pi_g and C3Pi_u tail shapes). Status GAP_UNCHANGED under the stated rule.",
            "Vibrational (P3): measured-lineage non-resonant 0->1 data extend from 48.5 eV to ~75 eV (digitized, no stated uncertainty, not independent of the Tabata lineage), narrowing the omitted-rate bracket at T_e 30 eV to ~2.2-2.4x the table; no data above ~75 eV and no non-resonant overtone measurement. Status GAP_UNCHANGED under the stated rule.",
            "All three adversarial checks recorded material_improvement_confirmed = false.",
            "The candidates that could change the picture are closed-access primaries; obtaining them by legitimate library or purchase access is itself an owner decision (lists per priority in legitimate_access_candidates_owner_decision).",
            "P4 (dissociation above ~296-330 eV) was not searched (DEFERRED per owner ordering).",
        ],
        "note": ("These are evidence facts relevant to the owner's reopening condition. The judgement on that condition is left "
                 "entirely to the owner; this dossier proposes no table, limit, pre-registration or v1 change."),
    }
    return out


def dumps(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def _v(x):
    return json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x


def _src_block(s):
    lane = s["lane01"]
    if lane["cited_in_lane01"]:
        l01 = "yes (lane-01 key `%s`; lane-01 access label: %s)" % (lane["lane01_source_key"], lane["lane01_access_label"])
    else:
        l01 = "no (new to the project)"
    acc = s["access"] + (" (" + s["access_note"] + ")" if s["access_note"] else "")
    return "\n".join([
        "- **`%s`** - %s" % (s["id"], s["citation"]),
        "  - DOI / URL: %s" % s["doi_or_url"],
        "  - access: **%s**; kind: %s; evidence class: %s (`%s`)" % (acc, s["kind"], s["evidence_class"], s["evidence_class_code"]),
        "  - process: %s; energy range (eV): %s" % (s["process"], s["energy_range_eV"]),
        "  - stated uncertainty: %s" % s["stated_uncertainty"],
        "  - where the data sit: %s" % s["where_data_sit"],
        "  - already in lane-01: %s" % l01,
        "  - what it adds: %s" % s["what_it_adds"],
    ])


def render_md(d):
    L = []
    a = L.append
    a("# D-X5 evidence dossier: N2 cross sections beyond the 45 eV chemistry domain")
    a("")
    a("Status: **DRAFT_PENDING_OWNER** - non-gating evidence dossier for follow-on `%s` (trigger `%s`)." % (d["follow_on"], d["trigger"]))
    a("Generated with `dx5_evidence_v1.json` by `build_dx5_evidence.py` (`--check` reproduces both files). Do not edit by hand.")
    a("")
    a("> " + d["scope_statement"])
    a("")
    a("## 1. Summary")
    a("")
    a("| priority | status | adversarial check: material improvement | requirement met by confirmed sources | confirmed / rejected / unconfirmed records |")
    a("|---|---|---|---|---|")
    for pk in ("P1", "P2", "P3"):
        p = d["priorities"][pk]
        a("| %s %s | **%s** | %s | %s | %d / %d / %d |" % (pk, SHORT[pk], p["status"], p["check_material_improvement_confirmed"],
                                                       p["requirement_met_by_confirmed_sources"], len(p["sources"]),
                                                       len(p["rejected_never_used"]), len(p["unconfirmed_never_used"])))
    p4 = d["priorities"]["P4"]
    a("| P4 %s | **%s** | not searched | - | - |" % (SHORT["P4"], p4["status"]))
    a("")
    a("Status rule: " + d["status_rule"])
    a("")
    a("## 2. Rules followed")
    a("")
    a("- Owner D-X5 rules (quoted from `%s`): %s" % (d["search_rules"][0]["from"][0], d["search_rules"][0]["value"]))
    a("- " + d["search_rules"][1] + ".")
    a("- Only sources confirmed by the adversarial checks are used. Rejected and unconfirmed records are listed with reasons and never used.")
    a("- Curation provenance: `%s`; raw search/check records (session scratchpad, not committed) are pinned by sha256 in the JSON (`curation.raw_records_sha256`)." % d["curation"]["curated_by"])
    a("")
    n = 3
    for pk in ("P1", "P2", "P3"):
        p = d["priorities"][pk]
        a("## %d. %s" % (n, p["priority_statement"]))
        n += 1
        a("")
        a("### Lane-01 requirement (quoted verbatim; each value resolves to the cited file and path)")
        a("")
        a("| field | value | from |")
        a("|---|---|---|")
        for r in p["lane01_requirement"]:
            a("| %s | %s | `%s` : `%s` |" % (r["name"], _v(r["value"]).replace("|", "/"), r["from"][0], "/".join(r["from"][1:])))
        a("")
        if pk == "P1":
            c = d["computed"]["P1"]
            a("Join at 10 eV (independent / Song 2023 Table 6; %s):" % c["basis"])
            a("")
            a("| set | j0->2 | j0->4 |")
            a("|---|---|---|")
            for k, v in c["independent_over_table_at_10eV"].items():
                a("| %s | %s | %s |" % (k, v["j0_to_2"], v["j0_to_4"]))
            a("")
            a(c["note"])
            a("")
        a("### Findings against the requirement")
        a("")
        a("Coverage:")
        a("")
        for x in p["findings_coverage"]:
            a("- " + x)
        a("")
        a("Join, shape and conflicts:")
        a("")
        for x in p["findings_join_shape_conflicts"]:
            a("- " + x)
        a("")
        a("### Status: **%s**" % p["status"])
        a("")
        a(p["status_justification"])
        a("")
        a("Sub-material changes (recorded, do not change the status):")
        a("")
        for x in p["sub_material_changes"]:
            a("- " + x)
        a("")
        a("Closed-access candidates that could change the picture (legitimate library/purchase access is an owner decision): "
          + ", ".join("`%s`" % x for x in p["legitimate_access_candidates_owner_decision"]) + ".")
        a("")
        a("### Confirmed sources (%d)" % len(p["sources"]))
        a("")
        for s in p["sources"]:
            a(_src_block(s))
        a("")
        a("### Rejected and unconfirmed records (never used)")
        a("")
        for r in p["rejected_never_used"]:
            a("- REJECTED `%s` - %s. Reason: %s" % (r["id"], r["citation"], r["reason"]))
        for r in p["unconfirmed_never_used"]:
            a("- UNCONFIRMED `%s` - %s. Reason: %s" % (r["id"], r["citation"], r["reason"]))
        a("")
        a("### Adversarial check")
        a("")
        a("Record `%s` (sha256 `%s`). Assessment: %s" % (p["adversarial_check"]["record"], p["adversarial_check"]["record_sha256"],
                                                      p["adversarial_check"]["assessment"].replace("\n", " ")))
        a("")
        a("Corrections applied:")
        a("")
        for x in p["adversarial_check"]["corrections"]:
            a("- " + x.replace("\n", " "))
        a("")
    a("## %d. P4 - dissociation above ~296-330 eV" % n)
    n += 1
    a("")
    a("**%s.** %s" % (p4["status"], p4["status_justification"]))
    a("")
    a("## %d. Search log (complete; verbatim from the search records)" % n)
    n += 1
    a("")
    for pk in ("P1", "P2", "P3"):
        for lg in d["priorities"][pk]["search_log"]:
            a("### %s - record `%s` (sha256 `%s`)" % (pk, lg["record"], lg["record_sha256"]))
            a("")
            a("Strategy: " + lg["strategy"].replace("\n", " "))
            a("")
            a("Queries, databases and citation chains:")
            a("")
            for x in lg["searched"]:
                a("- " + x.replace("\n", " "))
            a("")
            a("Dead ends:")
            a("")
            for x in lg["dead_ends"]:
                a("- " + x.replace("\n", " "))
            a("")
    r = d["reopening_condition_of_question_a"]
    a("## %d. Reopening condition of Question A" % n)
    a("")
    a("Status: **%s**. Who decides: **%s**. This section states evidence facts only; it does not decide." % (r["status"], r["who_decides"]))
    a("")
    a("Owner condition (quoted from `%s`): \"%s\"" % (r["condition"]["from"][0], r["condition"]["value"]))
    a("")
    a("Current disposition: %s." % r["current_disposition"]["value"])
    a("")
    a("Evidence facts relevant to the condition:")
    a("")
    for x in r["evidence_facts"]:
        a("- " + x)
    a("")
    a(r["note"])
    a("")
    return "\n".join(L)


MD_OUT = os.path.join(HERE, "DX5_EVIDENCE.md")
SHORT = {"P1": "rotational excitation above 10 eV", "P2": "electronic excitation above 100 eV (a1Pi_g above 200 eV)",
         "P3": "non-resonant vibrational excitation", "P4": "dissociation above ~296-330 eV"}


def main(argv):
    d = build()
    outs = {OUT: dumps(d), MD_OUT: render_md(d)}
    if "--check" in argv:
        bad = [p for p, t in outs.items() if (open(p).read() if os.path.exists(p) else "") != t]
        if bad:
            print("does NOT reproduce: " + ", ".join(os.path.basename(p) for p in bad), file=sys.stderr)
            return 1
        print("dx5_evidence_v1.json and DX5_EVIDENCE.md reproduce")
        return 0
    for p, t in outs.items():
        open(p, "w").write(t)
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
