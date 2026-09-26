# ECHT-N2 evidence audit (v1, 2026-09-26)

This is a measurement and evidence audit only. Nothing was simulated or scored, and no repository file was changed.

## Sources
- **S1** Marchioni & Cappelli, J. Appl. Phys. 130, 053306 (2021), doi:10.1063/5.0048283. **Paywalled.** The publisher
  returns 403. The author-hosted PDF linked from the SPPL page returns 404 and is not archived. I read only the
  abstract (via Crossref): 500–800 W anode, 17–22 mN, 1000–1100 s, 14–18 % total efficiency, 2 mg/s N2.
- **S2** F. Marchioni, MSc thesis, Politecnico di Torino / Stanford, 2020. **Open** (CC BY-NC-ND 3.0), 130 pp., sha256
  `d3b3ea99…9d7652`. S1 cites it. It is the only open primary source with per-point data.
- No follow-up ECHT measurement paper (N2, O2 or air) turned up among the 35 citing works.

## What is available (S2)
- Geometry: 86 mm long, "100 mm outer diameter" of the BN chamber, 10 mm channel height. Pure-iron pole walls, 46 mm.
  Coil design. Wall material BN (grade not given).
- B(z): a measured 14-point centreline profile at 2 A coil current, plus FEMM profiles at 1.5/2/2.5/3 A (digitized). The
  shape is a **flat plateau from about 4.7 to 8.6 cm, not exit-peaked**. The measured plateau is about 85 G, 12 % below
  FEMM. The quoted "130 G" is the FEMM value at 3 A.
- Table 6.1: 13 points of V_d (180/200/220 V), I_d (1.5–3.9 A, 2 s.f.), coil current, argon cathode flow (0.15–0.74 mg/s)
  and chamber pressure (0.8–2.2e-4 Torr). Anode flow is 2.06 mg/s N2.
- Tables 6.2/6.3: 7 thrust runs, 20.6–23.4 mN (one-side reduction). Four of them also have an averaged reduction, which
  is 6–18 % lower. The ± values are fit-only. Runs 1, 3 and 7 are flagged strongly unstable.
- Facility: SPPL LVF, inverted-pendulum stand, cathode IonTech HCN-252 (BaO) on argon.

## What is missing
- Channel radii (100 mm may be the BN piece OD), anode position and the origin of the B(z) axis.
- Measured B at the run currents.
- Cathode position and coupling voltage.
- Total thrust uncertainty and a cold-flow tare for N2.
- Any plume or divergence data, oscillation data, a facility correction, and any data above 220 V.

`cases/echt_n2.json` has two problems. Its 225–275 V points and its exit-peaked Gaussian B are not supported by any open
source.

## Conclusion
ECHT-N2 **cannot serve as an independent, scoreable validation dataset without forced assumptions.** The forced
assumptions are A1–A11 in the JSON: radii, anode position, B scaling per run, plume B, the argon cathode flow, the
facility/ingestion model, the thrust reduction reading, divergence, anode flow of 2.06 vs 2.083 mg/s, BN grade, and the
unstable runs. At most it can serve as a supporting, pre-registered check (sustainment, I_d magnitude and trend with B,
thrust about 20–23 mN), with those assumptions carried as layer-1 nuisance.

## Files
- `echt_n2_evidence_audit_v1.json`: sources, values with source/class/uncertainty, gap register, findings, conclusion.
- `echt_bfield_digitized_v1.json`: digitized Figs. 4.7/4.8 (method and axis calibration inside).
- `echt_table_checks_v1.json`: arithmetic consistency checks of Tables 6.1–6.3.
- `scripts/`: `digitize_echt_bfield.py`, `check_echt_tables.py`, `build_echt_audit.py`.
- `src/`: the downloaded thesis, extracted text and figure rasters. These are CC BY-NC-ND, so do not commit them to the
  repo. Commit only the extracted values.

## URLs used
- https://pubs.aip.org/aip/jap/article/130/5/053306/1079086/Extended-channel-Hall-thruster-for-air-breathing (403)
- https://api.crossref.org/works/10.1063/5.0048283
- https://api.semanticscholar.org/graph/v1/paper/DOI:10.1063/5.0048283
- https://api.openalex.org/works/doi:10.1063/5.0048283
- https://webthesis.biblio.polito.it/14618/
- https://webthesis.biblio.polito.it/14618/1/tesi.pdf
- https://sppl.stanford.edu/publications/
- https://sppl.stanford.edu/wp-content/uploads/2023/05/MarchioniAirBreathing.pdf (404)
- https://archive.org/wayback/available?url=sppl.stanford.edu/wp-content/uploads/2023/05/MarchioniAirBreathing.pdf and
  the web.archive.org CDX index (no archived PDF)
- https://link.springer.com/article/10.1007/s44205-022-00024-9 (cookie redirect, not followed)
- WebSearch result pages (ResearchGate and Semantic Scholar listings: not fetched)
