"""One-off curation of the D-X5 search records into the committed source list (dx5_sources_v1.json).

Provenance only. The inputs are the D-X5 search and adversarial-check records written by the search agents to the session
scratchpad (NOT committed; their sha256 values are recorded in the output). This script:
  * keeps ONLY sources the adversarial checks (P1_check / P2_check / P3_check) confirmed,
  * merges duplicates found by the two independent search strategies (A: compilations/reviews, B: primary literature),
  * applies the checkers' corrections (access labels, citations, qualifiers) as explicit overrides,
  * lists rejected and unconfirmed records separately (never used),
  * copies the complete search logs (queries, databases, citation chains, dead ends) verbatim.
It writes nothing but dx5_sources_v1.json. It changes no chemistry table, validity limit, pre-registration or v1 result.

Usage: python curate_dx5_sources.py <scratch_dx5_dir> <out_json>
The committed build (../build_dx5_evidence.py) does NOT depend on this script or on the scratchpad.
"""
import hashlib, json, os, sys

RAW_FILES = ["P1_review", "P1_primary", "P1_check", "P2_review", "P2_primary", "P2_check", "P3_review", "P3_primary",
             "P3_check"]
KEEP = ["citation", "doi_or_url", "access", "kind", "process", "energy_range_eV", "evidence_class", "stated_uncertainty",
        "quote_or_location", "what_it_adds"]

# (canonical id, [(record, raw id), ...] primary first, evidence_class_code, lane01_source_key or None, overrides)
P1 = [
    ("itikawa1986_table5_1", [("P1_review", "P1-A01"), ("P1_primary", "itikawa1986_jpcrd_table5_1")], "evaluated_secondary",
     "itikawa1986", {"stated_uncertainty": "none numeric for Table 5.1; calculated rotational cross sections 'scatter by more than a factor of 2' (Sec. 5.1, generic); the Tanaka et al. column is explicitly preliminary ('have to be confirmed', Sec. 10(d)). Transcription of the 30 eV row (Onda 0->2 2.86 vs 2.66; Rumble 0->6 0.309 vs 0.389): verify."}),
    ("siegel_dehmer_dill_1978", [("P1_review", "P1-A02"), ("P1_primary", "siegel_dehmer_dill_1978_anl")], "model_derived", None,
     {"citation": "J. Siegel, J. L. Dehmer, D. Dill, 'Electron scattering from N2 below 30 eV. Rotationally-inelastic and momentum-transfer cross sections', Argonne National Laboratory Report ANL-78-65 (Pt. 1), pp. 98-104 (December 1978)"}),
    ("onda_truhlar_1979", [("P1_review", "P1-A03"), ("P1_primary", "onda_truhlar_1979_jcp71_5107")], "model_derived", None, {}),
    ("onda_truhlar_1980", [("P1_review", "P1-A04"), ("P1_primary", "onda_truhlar_1980_jcp72_5249")], "model_derived", None, {}),
    ("rumble_truhlar_morrison_1983", [("P1_review", "P1-A05"), ("P1_primary", "rumble_truhlar_morrison_1983")], "model_derived", None, {}),
    ("brandt_truhlar_vancatledge_1976", [("P1_review", "P1-A06"), ("P1_primary", "brandt_truhlar_vancatledge_1976_jcp64_4957")], "model_derived", None, {}),
    ("onda_truhlar_1978_1979_dcs", [("P1_review", "P1-A07")], "model_derived", None, {}),
    ("bhattacharyya_goswami_1982", [("P1_review", "P1-A08"), ("P1_primary", "bhattacharyya_goswami_1982_pra26_2592")], "model_derived", None,
     {"access": "abstract_only"}),
    ("kutz_meyer_1995", [("P1_review", "P1-A09"), ("P1_primary", "kutz_meyer_1995_pra51_3819")], "model_derived", None, {}),
    ("gote_ehrhardt_1995", [("P1_review", "P1-A10"), ("P1_primary", "gote_ehrhardt_1995_jpb28_3957")], "measured_not_accessed", None, {}),
    ("tanaka_boesten_shimamura_1980", [("P1_review", "P1-A11"), ("P1_primary", "tanaka_boesten_shimamura_1980")], "measured_secondary", None, {}),
    ("itikawa_nifs_data_63", [("P1_review", "P1-A12"), ("P1_primary", "itikawa2001_nifs_data_63")], "bibliographic", None,
     {"quote_or_location": "Table I entries pp. 5-23; Table II rotational index p. 32 (N2: 80Ond1 [DCS 30 eV only], 80Ond2, 82Bha1, 82Jun1, 85Ond1, 95Got1, 95Kut1, 97Mor1; 97Rob1 is NOT in the N2 rotational index). PDF page = printed page + 1."}),
    ("hayashi_nifs_data_77", [("P1_review", "P1-A13"), ("P1_primary", "hayashi2003_nifs_data_77")], "bibliographic", None,
     {"stated_uncertainty": "n/a; scanned PDF searched by OCR (entries can be missed); the OCR entry list was not re-verified by the check"}),
    ("kawaguchi2021", [("P1_review", "P1-A14"), ("P1_primary", "unavailable_compilations")], "evaluated_not_accessed", "kawaguchi2021", {}),
    ("casey_arxiv_1904_06671", [("P1_review", "P1-A15")], "secondary_statement", None,
     {"energy_range_eV": "construction calculated to 400 eV for transport (not data)"}),
    ("gerjuoy_stein_1955", [("P1_review", "P1-A16"), ("P1_primary", "gerjuoy_stein_1955_pr97_1671")], "model_derived", None, {}),
    ("choi_poe_sun_shan_1979", [("P1_review", "P1-A17")], "model_derived", None,
     {"what_it_adds": "Theory nominally reaching 500 eV (found via Hayashi NIFS-DATA-077, coded E/R/V). The abstract does NOT show that N2 rotational ICS are tabulated; closed."}),
    ("gianturco_lamanna_rahman", [("P1_review", "P1-A18")], "model_derived", None, {}),
    ("ernesti_gote_korsch_1995", [("P1_review", "P1-A19"), ("P1_primary", "ernesti_gote_korsch_1995_and_korsch_ernesti_1992")], "model_derived", None,
     {"citation": "A. Ernesti, M. Gote, H. J. Korsch, 'Rotational excitation in two-center Coulomb-scattering systems: Application to electron-molecule collisions', Phys. Rev. A 52, 1266 (1995) [Korsch & Ernesti, J. Phys. B 25, 3565 (1992) was not checked and is not used]",
      "doi_or_url": "https://doi.org/10.1103/PhysRevA.52.1266", "access": "abstract_only"}),
    ("song2023_jpcrd", [("P1_review", "P1-A20"), ("P1_primary", "song2023_table4_elastic_ics_envelope")], "evaluated", "song2023_jpcrd",
     {"quote_or_location": "Sec. 2.4 p. 023104-8, Fig. 8 and Table 6 p. 023104-9 (rotational, 0.01-10 eV, no uncertainty); Table 4 p. 023104-7 (recommended elastic ICS 0.1-1000 eV, 10-20 %); Sec. 7 ('the main low-energy cross section for which experimental information is largely missing is electron impact rotational excitation')",
      "what_it_adds": "Re-read for the citation chain: Sec. 2.4 cites none of Gote & Ehrhardt, Itikawa 1986 Table 5.1, Siegel et al., Onda & Truhlar, Rumble et al., Bhattacharyya & Goswami or Choi et al.; Fig. 8 ends at 10 eV (Kutz & Meyer drawn only to ~1 eV). Table 4 (measured-based vibrationally elastic ICS to 1000 eV) is an UPPER BOUND on the rotational sum only by INFERENCE (assumes the recommended ICS is vibrationally elastic, per Itikawa 1986 Sec. 4); the statement that the held 0->2 + 0->4 (4.07e-16 cm2) exceeds that bound above ~160 eV is a derived indicator, not a measured fact."}),
    ("ristic2023_jscs", [("P1_review", "P1-A21")], "secondary_statement", None, {}),
    ("majeed_strickland1997", [("P1_review", "P1-A22"), ("P1_primary", "majeed_strickland_1997_cross_lane")], "evaluated", "majeed_strickland1997", {}),
    ("itikawa_mason_2005", [("P1_review", "P1-A23")], "not_accessed", None, {}),
    ("itikawa2006", [("P1_review", "P1-A24")], "evaluated_not_accessed", "itikawa2006", {}),
]
P1_REJECTED = [("P1_primary", "gupta_mathur_1981_pramana17_81"), ("P1_primary", "minor_low_energy_sources")]
P1_UNCONFIRMED = [("korsch_ernesti_1992", "J. Phys. B 25, 3565 (1992) - part of a merged strategy-B record; the check states it was not checked")]

P2 = [
    ("song2023_jpcrd", [("P2_review", "P2A-01")], "evaluated", "song2023_jpcrd", {}),
    ("kawaguchi2018_thesis", [("P2_review", "P2A-02")], "evaluated_digitized", None,
     {"what_it_adds": "First accessible (open, non-LXCat) version of the Kawaguchi N2 set; identity with PSST 30, 035010 (2021) is NOT verified. Anchored on Johnson at 100 eV (ratios 0.92-1.11), so not independent there; above 100 eV an extrapolated / swarm-fitted tail (ratios to the repo continuation 0.29-1.42 at 400-1000 eV). A second evaluated opinion, not closure. ex7 = w1Delta_u and ex8 = C3Pi_u assignment consistent with Table 7.1 thresholds and in-figure labels (check)."}),
    ("kawaguchi2021", [("P2_review", "P2A-03"), ("P2_primary", "kawaguchi2021")], "evaluated_not_accessed", "kawaguchi2021", {}),
    ("majeed_strickland1997", [("P2_review", "P2A-04")], "evaluated", "majeed_strickland1997",
     {"quote_or_location": "Table 1 p. 338; text p. 338 'The source of these cross sections is Cartwright et al.' (ref 32, PRA 16, 1013 (1977); ref 35 = PRA 16, 1041 is the other Cartwright 1977 paper); Tables 5-7 p. 346 (triplets 6.5-200 eV; a1Pi_g 10-1000 eV; w1Delta_u 9-200 eV; a'1Sigma_u- 11-1000 eV)"}),
    ("itikawa1986", [("P2_review", "P2A-05")], "evaluated", "itikawa1986",
     {"what_it_adds": "Documents the up-to-2x Trajmar 1983 renormalization missing from MS1997's Cartwright source. Fig. 7.5 shows the Imami & Borst 2PG (0,0) shape to 1 keV (digitized, spot-checked). Fig. 7.3 shows Aarts & de Heer 1971 and Holland 1969 LBH (2,0) emission ~100-2000 eV (relative, cascade-inclusive, no uncertainty; open secondary view of the a1Pi_g high-energy shape, noted by the check). Fig. 7.4 shows Oda & Osawa Born values only to ~100 eV. Declines Qexc for A and B from emission (cascade)."}),
    ("imami_borst1974", [("P2_review", "P2A-06"), ("P2_primary", "imami_borst1974")], "measured_secondary",
     None, {"what_it_adds": "Independent optical C3Pi_u shape to 1 keV, seen only as a digitized secondary figure (Itikawa 1986 Fig. 7.5) without uncertainty. Normalized at 100 eV it falls much more slowly than the repo continuation (p = 2.47): ratio 1.29 / 1.69 / 2.8 / 5.7 at 200 / 300 / 500 / 900 eV. The authors say their 100 eV value is an order of magnitude smaller than most EXISTING measurements and attribute that to pressure/secondary-electron effects in the other work (they do NOT flag their own scale as low); Itikawa 1986 finds their Qexc close to Cartwright ELS. Emission may include cascade. Widens the C3Pi_u band; not closure."}),
    ("fons1996", [("P2_review", "P2A-07"), ("P2_primary", "fons1996")], "measured_not_accessed", None, {}),
    ("ajello2017", [("P2_review", "P2A-08"), ("P2_primary", "ajello2017")], "inferred", None, {}),
    ("ajello2020", [("P2_review", "P2A-09"), ("P2_primary", "ajello2020")], "inferred", None,
     {"access": "open", "what_it_adds": "a1Pi_g excitation 0.62e-17 cm2 at 100 eV (0.87x Johnson) and 4.2e-18 at 200 eV (1.23x Johnson 3.41 +- 0.87e-18, within errors), inferred from emission via the 2017 method; 200/100 ratio 0.68 vs Johnson 0.48. The cascade value 1.7e-18 at 200 eV is an EMISSION cross section; the implied a'+w excitation 2.6-3.3x Johnson's sum is an inference (CIET- and pressure-dependent). Nothing above 200 eV."}),
    ("oda_osawa1981", [("P2_review", "P2A-10")], "measured_not_accessed", None, {}),
    ("skerbele_lassettre1970", [("P2_review", "P2A-11"), ("P2_primary", "skerbele_lassettre1970")], "measured_not_accessed", None, {}),
    ("chung_lin1972", [("P2_review", "P2A-12"), ("P2_primary", "chung_lin1972")], "model_derived", None, {}),
    ("aarts_deheer1971", [("P2_review", "P2A-13")], "not_accessed", None, {}),
    ("ajello_shemansky1985", [("P2_primary", "ajello_shemansky1985"), ("P2_review", "P2A-14")], "measured", None,
     {"access": "open", "access_note": "third-party-hosted reprint (spacewx.com); content verified by the check"}),
    ("kato2010", [("P2_review", "P2A-15"), ("P2_primary", "kato2010")], "measured_not_accessed", None, {}),
    ("song2023_epjd", [("P2_review", "P2A-16")], "review", None, {}),
    ("young2010", [("P2_review", "P2A-17")], "measured_not_accessed", None,
     {"access_note": "OpenAlex flags bronze OA, but the IOP page returned a turn-away; kept abstract_only"}),
    ("mason_newell1987", [("P2_review", "P2A-18"), ("P2_primary", "mason_newell1987")], "measured_not_accessed", None,
     {"access_note": "OpenAlex flags bronze OA, but the IOP page returned a turn-away; kept abstract_only"}),
    ("johnson2005", [("P2_review", "P2A-19")], "measured", "johnson2005", {}),
    ("liu2019", [("P2_review", "P2A-20")], "measured_not_accessed", None, {}),
    ("lassettre_osti_7335395", [("P2_review", "P2A-21")], "measured", None,
     {"access_note": "OSTI report open; Lassettre, Skerbele & Meyer 1966 metadata only"}),
    ("hayashi_nifs_data_77", [("P2_review", "P2A-22")], "bibliographic", None,
     {"stated_uncertainty": "n/a; scanned PDF, EX entries from OCR not re-verified by the check"}),
    ("arqueros2008_review", [("P2_review", "P2A-24"), ("P2_primary", "arqueros2008_review")], "review", None, {}),
    ("holland1969", [("P2_primary", "holland1969")], "measured_not_accessed", None, {}),
    ("nicolanti2023", [("P2_primary", "nicolanti2023")], "model_derived", None, {}),
    ("jain_bhardwaj2011", [("P2_primary", "jain_bhardwaj2011")], "model_derived", None, {}),
    ("borst1972", [("P2_primary", "borst1972")], "measured_not_accessed", None, {}),
    ("lee_mckoy1983", [("P2_primary", "lee_mckoy1983")], "model_derived", None, {}),
]
P2_REJECTED = [("P2_primary", "stanton_stjohn1969"), ("P2_review", "P2A-23")]
P2_REJECTED_CLAIMS = ["imami_borst1974 (strategy-B characterisation only)"]
P2_UNCONFIRMED = [("P2_review", "P2A-25"), ("P2_review", "P2A-26"), ("P2_review", "P2A-27"), ("P2_primary", "malone2009_jpb"),
                  ("P2_primary", "tashiro2007"), ("P2_primary", "gillan1996")]

P3 = [
    ("itikawa1986", [("P3_review", "itikawa1986"), ("P3_primary", "itikawa1986")], "measured_secondary", "itikawa1986",
     {"stated_uncertainty": "No uncertainty stated for the vibrational data (the 20-25 % on p. 998 is for renormalized electronic ELS data). Digitization of the scanned log-log Fig. 6.1 is good to about +/-10-15 % (the check rejects the +/-5 % claimed by review A)."}),
    ("truhlar1977", [("P3_review", "truhlar1977"), ("P3_primary", "truhlar1977")], "measured_secondary", None,
     {"quote_or_location": "Abstract: DCS ratios at 20-135 deg for 30, 35, 40, 45 and 75 eV and 25-90 deg at 20 eV (ICS therefore involve angular extrapolation); integral values only via Itikawa 1986 Fig. 6.1 (refs 125/126), renormalized per Trajmar 1983."}),
    ("tanaka1981", [("P3_review", "tanaka1981"), ("P3_primary", "tanaka1981")], "measured", "tanaka1981", {}),
    ("truhlar1972_V", [("P3_review", "truhlar1972_V"), ("P3_primary", "truhlar1972")], "model_derived", "truhlar1972", {}),
    ("truhlar1972_IV", [("P3_review", "truhlar1972_IV")], "measured_not_accessed", None, {}),
    ("truhlar1976", [("P3_review", "truhlar1976")], "measured_secondary", None, {}),
    ("rumble1983", [("P3_review", "rumble1983"), ("P3_primary", "rumble1983")], "model_derived", None,
     {"citation": "J. R. Rumble, D. G. Truhlar, M. A. Morrison, J. Chem. Phys. 79, 1846 (1983) [the 0->2 values of Itikawa 1986 Table 6.1 are footnoted to this paper; Rumble et al. 1981 J. Phys. B 14, L301 computes 0->0, 0->1 and 1->2 only]",
      "doi_or_url": "https://doi.org/10.1063/1.445961"}),
    ("burke1983", [("P3_review", "burke1983"), ("P3_primary", "burke1983")], "model_derived", None,
     {"citation": "P. G. Burke, C. J. Noble, S. Salvini, J. Phys. B 16, L113-L120 (1983)", "doi_or_url": "https://doi.org/10.1088/0022-3700/16/4/005", "access": "abstract_only"}),
    ("onda_truhlar1979", [("P3_review", "onda_truhlar1979"), ("P3_primary", "onda_truhlar1979")], "model_derived", None, {}),
    ("onda_truhlar1980", [("P3_review", "onda_truhlar1980")], "model_derived", None, {}),
    ("gillan1987", [("P3_review", "gillan1987")], "model_derived", None, {}),
    ("malegat1988", [("P3_review", "malegat1988")], "model_derived", None, {}),
    ("middleton1992", [("P3_primary", "middleton1992"), ("P3_review", "middleton1992")], "measured_not_accessed", None,
     {"access": "abstract_only", "energy_range_eV": "20, 30, 50 (N2), 10-90 deg", "quote_or_location": "Abstract via OpenAlex: 0->1 DCS at 20-50 eV, 10-90 deg; no ICS. IOP page: subscription / bot challenge (not bypassed)."}),
    ("pavlovic1972", [("P3_review", "pavlovic1972")], "measured_not_accessed", None,
     {"access": "abstract_only", "energy_range_eV": "15-35 (v = 1, 2, 3)", "quote_or_location": "Abstract via OpenAlex (APS page 403)"}),
    ("linert_zubek2009", [("P3_review", "linert_zubek2009")], "not_accessed", None, {}),
    ("zeng2011", [("P3_review", "zeng2011")], "model_derived", None, {}),
    ("itikawa2006", [("P3_review", "itikawa2006")], "evaluated_not_accessed", "itikawa2006", {}),
    ("song2023_jpcrd", [("P3_review", "song2023"), ("P3_primary", "song2023")], "evaluated", "song2023_jpcrd", {}),
    ("laporta2014", [("P3_review", "laporta2014")], "model_derived", "laporta2014", {}),
    ("tabata2006_qst", [("P3_review", "tabata2006_qst")], "model_derived", "tabata2006", {}),
    ("majeed_strickland1997", [("P3_review", "majeed_strickland1997")], "evaluated", "majeed_strickland1997", {}),
    ("dill1979", [("P3_review", "dill1979")], "model_derived", None, {}),
    ("su2022_pra", [("P3_review", "su2022_pra")], "model_derived", None, {}),
    ("kawaguchi2021", [("P3_review", "kawaguchi2021")], "evaluated_not_accessed", "kawaguchi2021", {}),
    ("choi1979", [("P3_primary", "choi1979")], "model_derived", None, {}),
    ("martendal_mazon2022", [("P3_review", "martendal_mazon2022"), ("P3_primary", "martendal2022")], "model_derived", None,
     {"access": "abstract_only", "access_note": "abstract elided; 'below 15 eV' only from a search snippet; Springer login redirect not followed",
      "energy_range_eV": "< 15 (search snippet only)"}),
    ("itikawa_nifs_data_63", [("P3_primary", "itikawa_nifs63")], "bibliographic", None,
     {"doi_or_url": "https://www.nifs.ac.jp/report/NIFS-DATA-063.pdf",
      "quote_or_location": "Table III N2 vibrational index (pp. 37-38) lists 92Mid1(E); the claim that only 92Mid1 measures above 30 eV was not checked entry by entry"}),
    ("phelps_pitchford1985", [("P3_review", "phelps_pitchford1985")], "evaluated_not_accessed", None,
     {"what_it_adds": "Unusable: the paper is abstract-only and its tabulations are distributed only through a database the project rules exclude; those tabulations were not opened."}),
]
P3_REJECTED = [("P3_review", "trajmar1983_physrep"), ("P3_review", "brunger_buckman2002"), ("P3_primary", "lee_freitas1983")]
P3_UNCONFIRMED = [("P3_primary", "hayashi_nifs77")]

PRI = {"P1": (P1, P1_REJECTED, P1_UNCONFIRMED, "P1_review", "P1_primary", "P1_check"),
       "P2": (P2, P2_REJECTED, P2_UNCONFIRMED, "P2_review", "P2_primary", "P2_check"),
       "P3": (P3, P3_REJECTED, P3_UNCONFIRMED, "P3_review", "P3_primary", "P3_check")}


def main(src, out):
    raw, sha = {}, {}
    for f in RAW_FILES:
        b = open(os.path.join(src, f + ".json"), "rb").read()
        raw[f], sha[f + ".json"] = json.loads(b), hashlib.sha256(b).hexdigest()
    idx = {f: {s["id"]: s for s in raw[f].get("sources", [])} for f in RAW_FILES}
    res = {"schema": "dx5_sources_v1", "curated_by": "docs/chemistry/n2_domain_extension/dx5/curation/curate_dx5_sources.py",
           "raw_records_sha256": sha,
           "raw_records_location": "session scratchpad dx5/ (not committed; hashes above)", "priorities": {}}
    for pk, (lst, rej, unc, fa, fb, fc) in PRI.items():
        chk = raw[fc]
        srcs = []
        for cid, recs, ecode, l01, ov in lst:
            prim = idx[recs[0][0]][recs[0][1]]
            e = {"id": pk + ":" + cid, "work_key": cid}
            for k in KEEP:
                e[k] = prim.get(k)
            e.update({k: v for k, v in ov.items()})
            e.setdefault("access_note", None)
            e["evidence_class_code"] = ecode
            e["lane01_source_key"] = l01
            e["check_status"] = "CONFIRMED"
            e["from_records"] = [r + "#" + i for r, i in recs]
            e["overrides_from_check"] = sorted(ov)
            srcs.append(e)
        rejected = []
        for r, i in rej:
            s = idx[r][i]
            reason = next(x["reason"] for x in chk["rejected"] if x["id"].split(" ")[0] == i)
            rejected.append({"id": pk + ":" + i, "citation": s["citation"], "doi_or_url": s.get("doi_or_url"),
                             "from_record": r + "#" + i, "reason": reason, "used": False})
        for claim in (P2_REJECTED_CLAIMS if pk == "P2" else []):
            reason = next(x["reason"] for x in chk["rejected"] if x["id"] == claim)
            rejected.append({"id": pk + ":claim:" + claim.split(" ")[0], "citation": claim, "doi_or_url": None,
                             "from_record": fb + "#" + claim.split(" ")[0], "reason": reason, "used": False,
                             "note": "rejected characterisation only; the source itself is confirmed and kept with the check's reading"})
        unconfirmed = []
        for item in unc:
            if item[0] in idx:
                s = idx[item[0]][item[1]]
                unconfirmed.append({"id": pk + ":" + item[1], "citation": s["citation"], "doi_or_url": s.get("doi_or_url"),
                                    "from_record": item[0] + "#" + item[1],
                                    "reason": "not covered by the adversarial check's confirmed list; not used", "used": False})
            else:
                unconfirmed.append({"id": pk + ":" + item[0], "citation": item[1], "doi_or_url": None,
                                    "from_record": fb, "reason": "not checked by the adversarial check; not used", "used": False})
        log = []
        for f in (fa, fb):
            log.append({"record": f, "record_sha256": sha[f + ".json"], "priority_statement": raw[f]["priority"],
                        "strategy": raw[f]["strategy"], "searched": raw[f]["searched"], "dead_ends": raw[f]["dead_ends"],
                        "finder_material_improvement": raw[f]["material_improvement"],
                        "finder_gap_assessment": raw[f]["gap_assessment"]})
        res["priorities"][pk] = {
            "priority_statement": raw[fa]["priority"], "sources": srcs, "rejected": rejected, "unconfirmed_not_used": unconfirmed,
            "check": {"record": fc, "record_sha256": sha[fc + ".json"], "checker": chk.get("checker"),
                      "confirmed_sources_text": chk["confirmed_sources"], "corrections": chk["corrections"],
                      "material_improvement_confirmed": chk["material_improvement_confirmed"], "assessment": chk["assessment"]},
            "search_log": log}
    res["priorities"]["P4"] = {"priority_statement": "P4 - additional independent N2 dissociation evidence above ~296-330 eV",
                               "searched": False, "sources": [], "rejected": [], "unconfirmed_not_used": [],
                               "reason": "DEFERRED per owner ordering: P4 is to be searched only after P1-P3 improve; the adversarial checks confirmed no material improvement for P1-P3, so P4 was not searched."}
    json.dump(res, open(out, "w"), indent=1, ensure_ascii=False, sort_keys=False)
    open(out, "a").write("\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
