"""Build the transitional-regime compressor evidence package (owner A9.13 S6.8 OQ-F3-03, S6.11 OQ-F4-02).

Outputs (deterministic; no timestamps other than the fixed retrieval date of the sources):
  docs/evidence/compressor_transitional/compressor_transitional_evidence_v1.json
  docs/evidence/compressor_transitional/COMPRESSOR_TRANSITIONAL_EVIDENCE.md   (generated from the JSON)

Contents: source register, model-selection memo, gap memo, coefficient register (read from the module and cross-checked
against the committed NIST snapshots), applicability domain, a computed consistency check against the production
free-molecular DragCompressor, and the admission plan.  The model itself is abep_sim/compressor_transitional.py; its
evidence status is CANDIDATE_NOT_ADMITTED and nothing here changes that.

    python docs/evidence/compressor_transitional/build_compressor_transitional_evidence.py          # (re)write
    python docs/evidence/compressor_transitional/build_compressor_transitional_evidence.py --check  # verify current

Missing inputs (decision record, downselect record, NIST snapshots) raise; there are no hidden defaults.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from abep_sim import compressor_transitional as ct  # noqa: E402
from abep_sim.compressor import DragCompressor  # noqa: E402

OUT_JSON = HERE / "compressor_transitional_evidence_v1.json"
OUT_MD = HERE / "COMPRESSOR_TRANSITIONAL_EVIDENCE.md"
SNAPSHOTS = {
    "N2": HERE / "sources" / "nist_webbook_N2_isobar_0.001bar_200-500K.tsv",
    "O2": HERE / "sources" / "nist_webbook_O2_isobar_0.001bar_200-500K.tsv",
}
DECISION_JSON = ROOT / "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json"
DECISION_MD = ROOT / "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md"
DOWNSELECT = ROOT / "docs/architecture_comparison/compressor_downselect/compressor_downselect_v1.json"
RETRIEVED = "2026-10-01"


def _sha(p: Path) -> str:
    if not p.is_file():
        raise FileNotFoundError(f"required input missing: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def parse_nist_snapshot(path: Path) -> list[tuple[float, float]]:
    """(T_K, viscosity_uPa_s) rows of a NIST WebBook fluid TSV response."""
    if not path.is_file():
        raise FileNotFoundError(f"NIST snapshot missing: {path}")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    head = lines[0].split("\t")
    iT, iv = head.index("Temperature (K)"), head.index("Viscosity (uPa*s)")
    return [(float(c[iT]), float(c[iv])) for c in (ln.split("\t") for ln in lines[1:])]


def decisions() -> dict:
    d = json.loads(DECISION_JSON.read_text(encoding="utf-8"))
    qs = {}
    for qid in ("OQ-F3-03", "OQ-F4-02"):
        found = _find_q(d, qid)
        if found is None:
            raise KeyError(f"{qid} not found in {DECISION_JSON}")
        qs[qid] = {k: found[k] for k in ("sequenced_no", "status", "answer", "summary") if k in found}
    md = DECISION_MD.read_text(encoding="utf-8")
    for needle in ("S6.8 — OQ-F3-03", "S6.11 — OQ-F4-02", "NOT_EVALUATED_OUT_OF_DOMAIN"):
        if needle not in md:
            raise ValueError(f"verbatim record does not contain {needle!r}")
    return {"json": _rel(DECISION_JSON), "json_sha256": _sha(DECISION_JSON),
            "verbatim_md": _rel(DECISION_MD), "verbatim_md_sha256": _sha(DECISION_MD),
            "questions": qs,
            "binding_text_S6_8": "until the transitional model has an admitted evidence basis and/or has been validated "
                                 "against the project hardware: production/design evidence above the current 0.1 Pa "
                                 "free-molecular domain remains NOT_EVALUATED_OUT_OF_DOMAIN; no extrapolated >0.1 Pa "
                                 "result may be treated as a valid architecture point."}


def _find_q(obj, qid):
    if isinstance(obj, dict):
        if qid in obj and isinstance(obj[qid], dict):
            return obj[qid]
        for v in obj.values():
            r = _find_q(v, qid)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_q(v, qid)
            if r is not None:
                return r
    return None


def hardware_tests() -> dict:
    d = json.loads(DOWNSELECT.read_text(encoding="utf-8"))
    tests = {t["id"]: t for t in d["minimum_data_to_freeze_DI_1_4"]}
    return {"record": _rel(DOWNSELECT), "sha256": _sha(DOWNSELECT),
            "T-1": tests["T-1"], "T-2": tests["T-2"]}


SOURCE_REGISTER = [
    {"id": "CT-S01", "citation": "P. A. Skovorodko, 'Continuum model for Couette-Poiseuille flow in a drag molecular "
                                 "pump', 23rd Int. Symp. Rarefied Gas Dynamics, Whistler BC, 21-25 July 2002, abstract "
                                 "#151; arXiv:physics/0401020 (submitted 7 Jan 2004), 2 pages",
     "url": "https://arxiv.org/abs/physics/0401020", "access": "OPEN (arXiv; license: arXiv assumed 1991-2003)",
     "retrieved": RETRIEVED, "retrieved_pdf_sha256": "1d46f7245f235113c051beec51c378b7e0c720acb5139c48d6bf7d8298abab42",
     "quantities": "closed-form stage relation L(p1, p2, g) (Eq. 1); continuum limit dp = 6 mu w L/delta^2; free-molecular "
                   "compression exp[sigma w L/((2-sigma) c0 delta)]; maximum throughput at u = w/2; tapered-channel "
                   "effective gap (not implemented)",
     "regime": "continuum to free molecular (author: 'good qualitative representation'; quantitative only with sigma "
               "fitted to the free-molecular compression)",
     "validation_in_source": "Fig. 1: inlet pressure vs flow rate (1e-9 to 1e-5 kg/s) at outlet 0.1/0.5/1 Torr, helium, "
                             "Holweck pump at 400 rps, experimental data of Kanki (RGD-1994, ref. 3) with sigma = 0.6 "
                             "fitted; channel geometry not given in the source",
     "evidence_level": 6, "quantity_type": "model-derived",
     "use": "IMPLEMENTED (abep_sim/compressor_transitional.py)"},
    {"id": "CT-S02", "citation": "F. Sharipov, 'Rarefied gas dynamics and its applications to vacuum technology', CERN "
                                 "Accelerator School lecture notes (CERN CDS record 1046845; series/year: verify)",
     "url": "https://fisica.ufpr.br/sharipov/CERN.pdf",
     "access": "OPEN (author's institutional site; the CDS copy returned a bot-check page from this environment and "
               "was not used)",
     "retrieved": RETRIEVED, "retrieved_pdf_sha256": "0359f860acb46723b018c13ade7890879737dbdcdc4e80b80752008fd7a4d8a4",
     "quantities": "Kn = l/a and l = mu v_m/P, v_m = (2 k_B T/m)^1/2 (Eqs. 1-2); rarefaction delta = 1/Kn (Eq. 3); "
                   "Holweck-pump methodology (Sec. 5: four linearized flows + superposition), no tabulated coefficients",
     "regime": "whole range of rarefaction (methodology)",
     "validation_in_source": "Fig. 3: limit compression K0 vs fore-vacuum rarefaction delta_f, theory vs experiment "
                             "(graph only; details deferred to Sharipov, Fahrenbach & Zipp 2005)",
     "evidence_level": 4, "quantity_type": "model-derived",
     "use": "Kn definition for reporting; methodology reference for a future kinetic model"},
    {"id": "CT-S03", "citation": "F. Sharipov, P. Fahrenbach, A. Zipp, 'Numerical modeling of the Holweck pump', "
                                 "J. Vac. Sci. Technol. A 23(5), 1331-1339 (2005)",
     "url": "https://doi.org/10.1116/1.1991882", "access": "ABSTRACT_ONLY (Crossref metadata); full text not open",
     "retrieved": RETRIEVED, "quantities": "kinetic-equation Holweck model; pumping speed, torque",
     "regime": "arbitrary rarefaction",
     "validation_in_source": "abstract: 'comparison of the numerical results with experimental data confirms that the "
                             "groove curvature is not a predominant factor, while the gas rarefaction significantly "
                             "affects the main characteristics of the pump'",
     "evidence_level": 4, "quantity_type": "model-derived",
     "use": "NOT IMPLEMENTED (full text and groove solutions not accessible); best-supported candidate if lawfully "
            "accessed later"},
    {"id": "CT-S04", "citation": "F. Sharipov, 'Numerical simulation of turbomolecular pump over a wide range of gas "
                                 "rarefaction', J. Vac. Sci. Technol. A 28(6), 1312-1315 (2010)",
     "url": "https://doi.org/10.1116/1.3484139", "access": "ABSTRACT_ONLY (Crossref metadata)",
     "retrieved": RETRIEVED, "quantities": "DSMC turbomolecular pump: maximum pumping speed and compression ratio vs "
                                           "rarefaction and rotor speed",
     "regime": "free molecular, transitional, hydrodynamic",
     "validation_in_source": "abstract only: 'in the range between the free-molecular and transitional regimes, the "
                             "pump characteristics change slightly, but they vary significantly in the hydrodynamic "
                             "regime ... The compression ratio always decreases when approaching the hydrodynamic "
                             "regime'",
     "evidence_level": 4, "quantity_type": "model-derived",
     "use": "GAP MEMO (qualitative only; no coefficients accessible)"},
    {"id": "CT-S05", "citation": "S. Giors (Agilent Technologies), 'Solved and Unsolved Gas Dynamics Problems for "
                                 "Turbo-Molecular-Drag Pumps: an Industrial Overview', 64th IUVSTA Workshop, "
                                 "Leinsweiler, 16-19 May 2011 (slides)",
     "url": "https://www.itep.kit.edu/downloads/6_Giors.pdf",
     "access": "OPEN (publicly hosted workshop slides; footer carries a template 'Confidentiality Label' field)",
     "retrieved": RETRIEVED, "retrieved_pdf_sha256": "6be731e2aadf67d8ad1fe6bc5d2b547fd269efc4956f6e522704213c328d27ee",
     "quantities": "stage regime map (slide 8: inlet TMP stages Kn 1e7..1e-1, intermediate 1e3..1e-1, outlet MDP 1e1..1e-3); "
                   "model survey (Helmer & Levi 1992 Gaede 1-D; Sawada 1999 Holweck 2-D; Giors 2005/2006 slip CFD; "
                   "Sharipov & Zipp 2005); industry wish for +/-15 % predictive simple models (slide 9)",
     "regime": "molecular to viscous", "validation_in_source": "secondary summary of others' validation",
     "evidence_level": 5, "quantity_type": "secondary",
     "use": "CONTEXT (selection memo); the Helmer-Levi equation on slide 14 is garbled in text extraction and its "
            "primary paper was not accessed -> not implemented"},
    {"id": "CT-S06", "citation": "H. Barfuss (Pfeiffer Vacuum), 'Mechanical Vacuum Pumps', CERN Accelerator School "
                                 "'Vacuum for Particle Accelerators', Lund, 8-9 June 2017 (slides)",
     "url": "https://indico.cern.ch/event/565314/contributions/2285745/attachments/1466629/2274675/Barfuss.pdf",
     "access": "OPEN (CERN Indico)", "retrieved": RETRIEVED,
     "retrieved_pdf_sha256": "90ca7c268d0e81fa4922cdd783203ef49c07d8e7b415a6b579f00d5c25baa5c3",
     "quantities": "flow-regime boundaries (slide 23): molecular Kn > 10, Knudsen 0.1-10, viscous Kn < 0.1; commercial "
                   "TMP speed vs inlet pressure curve (HiPace 300, Ar/H2; not digitized)",
     "regime": "all", "validation_in_source": "manufacturer curve, no uncertainty",
     "evidence_level": 5, "quantity_type": "secondary",
     "use": "KN_FREE_MOLECULAR_MIN = 10 for the overlap-regime flag (Kn definition not stated on the slide)"},
    {"id": "CT-S07", "citation": "NIST Chemistry WebBook, NIST Standard Reference Database 69, 'Thermophysical "
                                 "Properties of Fluid Systems' (section authors not read: verify); isobaric "
                                 "data at 0.001 bar, 200-500 K step 50 K, N2 (C7727379) and O2 (C7782447)",
     "url": "https://webbook.nist.gov/chemistry/fluid/", "access": "OPEN (US Government SRD; Standard Reference Data Act)",
     "retrieved": RETRIEVED,
     "quantities": "dynamic viscosity (uPa s), low-density state",
     "regime": "dilute gas", "validation_in_source": "evaluated correlations; the underlying viscosity-correlation "
                                                     "reference and its uncertainty were not read (verify)",
     "evidence_level": 4, "quantity_type": "model-derived (evaluated correlation output), transcribed",
     "use": "VISCOSITY_TABLE_uPa_s (snapshots committed under sources/)"},
    {"id": "CT-S08", "citation": "Heo & Hwang, DSMC calculations of blade rows of a turbomolecular pump in the "
                                 "molecular and transition flow regions, Vacuum 56, 133 (2000) (as listed by ADS "
                                 "2000Vacuu..56..133H and Giors slide 11)",
     "url": "https://ui.adsabs.harvard.edu/abs/2000Vacuu..56..133H/abstract", "access": "NOT_OPEN (paywalled)",
     "retrieved": None, "quantities": "TMP blade-row performance, molecular + transition", "regime": "transition",
     "validation_in_source": "not read", "evidence_level": None, "quantity_type": None, "use": "GAP MEMO only"},
    {"id": "CT-S09", "citation": "T. Kanki, 'Flow of a rarefied gas in a rectangular channel with a moving plate', "
                                 "Rarefied Gas Dynamics 1994 (19th Symp.), Oxford Univ. Press 1995, Vol. 1, 375-381 "
                                 "(as cited by CT-S01)",
     "url": None, "access": "NOT_ACCESSED (proceedings volume; no open copy found)", "retrieved": None,
     "quantities": "Holweck helium measurements used in CT-S01 Fig. 1", "regime": "transition",
     "validation_in_source": "-", "evidence_level": None, "quantity_type": None,
     "use": "already used by CT-S01 to fit sigma -> NOT held-out for this model"},
    {"id": "CT-S10", "citation": "Helmer & Levi, Couette-Poiseuille Gaede pump 1-D model, J. Vac. Sci. Technol. A "
                                 "(1992) (as cited by CT-S05 slide 14; full reference not read)",
     "url": None, "access": "NOT_ACCESSED", "retrieved": None, "quantities": "Gaede stage 1-D model",
     "regime": "molecular to viscous (per CT-S05)", "validation_in_source": "not read",
     "evidence_level": None, "quantity_type": None, "use": "not implemented (primary not read)"},
    {"id": "CT-S11", "citation": "'An experimental study on the pumping performance of molecular drag pumps', "
                                 "Springer, doi:10.1007/BF02915971 (authors/journal not read: access redirected to "
                                 "a login)",
     "url": "https://doi.org/10.1007/BF02915971", "access": "NOT_OPEN", "retrieved": None,
     "quantities": "N2 drag-pump measurements (per search snippet only)", "regime": "molecular-transition",
     "validation_in_source": "not read", "evidence_level": None, "quantity_type": None,
     "use": "candidate held-out dataset only if lawfully accessible later"},
]


MODEL_SELECTION = {
    "question": "Which open-literature transitional-regime model of molecular-drag / turbomolecular compression can be "
                "implemented with every coefficient cited?",
    "criteria": ["full text openly and lawfully accessible", "closed-form or reproducible relation with all coefficients "
                 "stated", "covers free molecular -> transitional (Kn dependence of compression and speed)",
                 "states its own validation", "reduces to the production free-molecular model in the overlap"],
    "candidates": [
        {"source": "CT-S01 Skovorodko Eq. (1)", "verdict": "SELECTED",
         "why": "only accessed model meeting all criteria: closed form, every factor stated, explicit continuum and "
                "free-molecular limits, reduces exactly to DragCompressor's linear Gaede characteristic in the "
                "free-molecular limit (with xi <-> sigma mapping)",
         "limitations": ["author calls it approximate/qualitative", "sigma is a fitting parameter (no a-priori value)",
                         "plane channel: no groove side walls, land leakage, curvature, centrifugal effects",
                         "inertia neglected, isothermal", "single validation dataset (helium) not reconstructible",
                         "single gas; not a mixture model"]},
        {"source": "CT-S02/CT-S03 Sharipov kinetic Holweck model", "verdict": "NOT_IMPLEMENTABLE_NOW",
         "why": "best physics basis (linearized kinetic equation, experimentally compared), but the groove-flow "
                "solutions (Couette/Poiseuille coefficients vs rarefaction and groove shape) are in the non-open paper"},
        {"source": "CT-S05 survey: Helmer-Levi, Sawada, Giors slip CFD", "verdict": "NOT_IMPLEMENTABLE_NOW",
         "why": "primary papers not open; secondary equation incomplete"},
        {"source": "CT-S04/CT-S08 TMP DSMC", "verdict": "GAP", "why": "no open coefficients; see gap memo"},
    ],
    "result": "Skovorodko Eq. (1) implemented as CANDIDATE_NOT_ADMITTED for drag-channel stages only.",
}

GAP_MEMO = [
    {"id": "GAP-01", "gap": "turbomolecular blade rows in the transitional regime",
     "status": "NO_ADEQUATELY_DOCUMENTED_OPEN_MODEL_FOUND",
     "consequence": "abep_sim.compressor_transitional.turbomolecular_row_transitional raises NotEvaluatedError; the "
                    "DragCompressor turbo rows remain free-molecular only (<= 0.1 Pa)",
     "closure": "T-1 (bladed rotor stage CR vs inlet pressure, outlet 0.05-1 Pa) or lawful access to CT-S04/CT-S08"},
    {"id": "GAP-02", "gap": "groove-resolved Holweck/Gaede/Siegbahn transitional coefficients (side walls, land leakage)",
     "status": "OPEN_ONLY_AS_METHODOLOGY (CT-S02)",
     "consequence": "plane-channel approximation only; the candidate cannot represent leakage-limited compression"},
    {"id": "GAP-03", "gap": "atomic oxygen and gas mixtures",
     "status": "NO_VISCOSITY_SOURCE_FOR_O; single-gas model",
     "consequence": "refused (OutOfModelDomainError); T-3 (AO facility) is the closure path"},
    {"id": "GAP-04", "gap": "accommodation/fit parameter sigma for Vyovrinda geometry and surfaces",
     "status": "TBD", "consequence": "no default; caller must supply sigma with an evidence class"},
    {"id": "GAP-05", "gap": "open held-out transitional dataset with reconstructible geometry",
     "status": "NONE FOUND", "consequence": "admission must go through T-1/T-2 hardware data"},
]


def coefficient_register() -> dict:
    out = {k: dict(v) for k, v in ct.COEFFICIENTS.items()}
    snaps = {}
    for gas, path in SNAPSHOTS.items():
        rows = parse_nist_snapshot(path)
        if tuple(rows) != tuple(ct.VISCOSITY_TABLE_uPa_s[gas]):
            raise ValueError(f"module viscosity table for {gas} differs from the committed NIST snapshot")
        snaps[gas] = {"snapshot": _rel(path), "sha256": _sha(path), "rows_T_K_uPa_s": [list(r) for r in rows],
                      "matches_module_table": True}
    out["mu_T"]["snapshots"] = snaps
    return out


def consistency_check() -> dict:
    """Overlap-regime comparison against DragCompressor. CHECK CONFIGURATION, not a design point."""
    base = DragCompressor()
    cfg = dataclasses.replace(base, L_per_stage_m=0.005)
    rows = []
    for gas in ("N2", "O2"):
        for p in (1e-4, 1e-3, 1e-2):
            stage = ct.DragChannelStage(gap_m=cfg.h_mm * 1e-3, length_m=cfg.L_per_stage_m, width_m=cfg.w_mm * 1e-3,
                                        wall_speed_mps=cfg.u, sigma=ct.sigma_from_free_molecular_xi(cfg.xi),
                                        sigma_evidence_class="model-derived", sigma_source="xi mapping")
            cap = ct.max_throughput_kgps(stage, gas, cfg.T_gas_K, p)
            for frac in (1e-9, 0.1, 0.3):
                r = ct.compare_with_free_molecular(cfg, gas, p, cap * frac)
                rows.append({"gas": gas, "p_in_Pa": p, "throughput_fraction_of_plane_capacity": frac,
                             "K_DragCompressor": _r(r["K_DragCompressor"]), "K_candidate": _r(r["K_candidate"]),
                             "lnK_rel_diff": _r(r["lnK_rel_diff_candidate_vs_DragCompressor"]),
                             "kn_in": _r(r["kn_in"]), "comparable": r["comparable"]})
    default = ct.compare_with_free_molecular(base, "N2", 1e-3, 1e-15)
    return {
        "label": "CONSISTENCY_CHECK_CONFIGURATION_NOT_A_DESIGN_POINT",
        "configuration": {"DragCompressor": "defaults except L_per_stage_m = 0.005 (chosen so outlet stays <= 0.1 Pa)",
                          "xi": cfg.xi, "sigma_mapped": _r(ct.sigma_from_free_molecular_xi(cfg.xi)),
                          "T_K": cfg.T_gas_K, "u_mps": _r(cfg.u)},
        "rows": rows,
        "interpretation": [
            "zero-throughput: the two free-molecular compressions coincide by construction (sigma mapped from xi); the "
            "residual lnK difference is the Eq. (1) viscous/slip correction and grows ~linearly with pressure",
            "finite throughput: DragCompressor applies xi to the pumping speed (S0 = xi u h w/2) while the plane-channel "
            "model has S0 = u h w/2, so DragCompressor loses compression 1/xi times faster with throughput; this is a "
            "structural model difference, not a numerical error, and is unresolved without T-2 data",
        ],
        "default_geometry_finding": {
            "lnK0_free_molecular": _r(default["lnK0_free_molecular_DragCompressor"]),
            "K_DragCompressor_one_stage_near_zero_flow": f"{default['K_DragCompressor']:.3e}",
            "K_candidate_one_stage_near_zero_flow": f"{default['K_candidate']:.3e}",
            "note": "with the default 0.35 m drag stage DragCompressor's free-molecular characteristic implies outlet "
                    "pressures far above 0.1 Pa (outside its own domain), where the candidate saturates through the "
                    "viscous term; both are out of the production domain -> NOT_EVALUATED_OUT_OF_DOMAIN",
            "architecture_point_status": default["architecture_point_status"]},
    }


def _r(x: float) -> float:
    return float(f"{x:.6g}")


def admission_plan(hw: dict) -> dict:
    return {
        "current_status": ct.EVIDENCE_STATUS,
        "rule": "Admission is a separate owner-gated step. No code path in abep_sim/compressor_transitional.py returns "
                "an admitted result; admission requires a new module version, a docs/HISTORY.md entry and an owner "
                "decision record.",
        "routes": [
            {"route": "A_HARDWARE", "data": "T-1 (and T-2 for pumping speed) on the project compressor",
             "definition_source": hw["record"], "T-1": hw["T-1"]["what"], "T-2": hw["T-2"]["what"],
             "note": "T-1 covers a bladed rotor stage (and back stage): only drag-channel stages are within this "
                     "model's geometry class; blade rows stay a gap (GAP-01)"},
            {"route": "B_HELD_OUT_PUBLISHED", "data": "a published, lawfully accessible transitional-regime "
                                                       "drag-stage dataset with reconstructible geometry, not used to "
                                                       "fit sigma",
             "status": "NONE FOUND (GAP-05); Kanki 1994 is not held-out (used by the source to fit sigma)"},
        ],
        "pre_registration_before_any_comparison": [
            "freeze the module version and the dataset hash",
            "fit sigma ONLY on free-molecular-regime points (as the source prescribes), with the Kn threshold "
            "pre-registered",
            "predict the transitional-regime points blind (no refit, no geometry retuning)",
            "acceptance tolerance on compression ratio and pumping speed: TBD by the owner at pre-registration "
            "(CT-S05's +/-15 % industry wish is context, not a criterion)",
            "declare the admitted domain (gas, Kn range, geometry class, T) as exactly the validated span",
            "a failed prediction is recorded as such and is never converted into a recalibration",
        ],
        "until_admitted": "any result above 0.1 Pa is NOT_EVALUATED_OUT_OF_DOMAIN and never a valid architecture point "
                          "(A9.13 S6.8); results <= 0.1 Pa are CANDIDATE_RESULT_NOT_DESIGN_EVIDENCE (the production "
                          "free-molecular DragCompressor remains the model of record there)",
    }


def build() -> dict:
    hw = hardware_tests()
    return {
        "schema": "compressor_transitional_evidence_v1",
        "version": ct.VERSION,
        "module": "abep_sim/compressor_transitional.py",
        "model_id": ct.MODEL_ID,
        "evidence_status": ct.EVIDENCE_STATUS,
        "valid_design_evidence": False,
        "owner_decision": decisions(),
        "source_register": SOURCE_REGISTER,
        "model_selection_memo": MODEL_SELECTION,
        "gap_memo": GAP_MEMO,
        "coefficient_register": coefficient_register(),
        "applicability_domain": dict(ct.APPLICABILITY_DOMAIN),
        "consistency_check_vs_DragCompressor": consistency_check(),
        "admission_plan": admission_plan(hw),
        "access_policy": "open/lawful access only; no paywall or bot-check bypass; no contact with authors, labs or "
                         "suppliers; LXCat not used",
    }


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# Transitional-regime compressor model: evidence package (CANDIDATE, NOT ADMITTED)")
    a("")
    a("Generated by `build_compressor_transitional_evidence.py` from `compressor_transitional_evidence_v1.json`. Do not "
      "edit by hand.")
    a("")
    od = doc["owner_decision"]
    a(f"**Owner decision:** `{od['json']}` (sha256 `{od['json_sha256']}`), verbatim `{od['verbatim_md']}`; questions "
      + ", ".join(f"{k} ({v['sequenced_no']}, {v['answer']})" for k, v in od["questions"].items()) + ".")
    a("")
    a(f"> {od['binding_text_S6_8']}")
    a("")
    a(f"**Model:** `{doc['module']}`, id `{doc['model_id']}`. **Evidence status: `{doc['evidence_status']}`**; "
      "`valid_design_evidence = False` on every output, and `as_design_evidence()` always raises.")
    a("")
    a("## Source register")
    a("")
    a("| id | citation | access | quantities | regime | validation in source | level / type | use |")
    a("|---|---|---|---|---|---|---|---|")
    for s in doc["source_register"]:
        url = f" <{s['url']}>" if s.get("url") else ""
        lvl = f"{s['evidence_level']} / {s['quantity_type']}" if s.get("evidence_level") else "-"
        a(f"| {s['id']} | {s['citation']}{url} | {s['access']} | {s['quantities']} | {s['regime']} | "
          f"{s['validation_in_source']} | {lvl} | {s['use']} |")
    a("")
    a("## Model-selection memo")
    a("")
    ms = doc["model_selection_memo"]
    a(f"Question: {ms['question']}")
    a("")
    a("Criteria: " + "; ".join(ms["criteria"]) + ".")
    a("")
    for c in ms["candidates"]:
        a(f"- **{c['source']}**: {c['verdict']}. {c['why']}.")
        for lim in c.get("limitations", []):
            a(f"  - limitation: {lim}")
    a("")
    a(f"Result: {ms['result']}")
    a("")
    a("## Gap memo")
    a("")
    for g in doc["gap_memo"]:
        a(f"- **{g['id']}** {g['gap']}: {g['status']}. {g['consequence']}." +
          (f" Closure: {g['closure']}." if "closure" in g else ""))
    a("")
    a("## Coefficients")
    a("")
    a("| coefficient | value | source | level | class |")
    a("|---|---|---|---|---|")
    for k, v in doc["coefficient_register"].items():
        a(f"| {k} | {v['value']} | {v['source']} | {v['level']} | {v['evidence_class']} |")
    a("")
    a("Viscosity snapshots: " + ", ".join(f"{g}: `{s['snapshot']}` (sha256 `{s['sha256'][:16]}...`)"
                                         for g, s in doc["coefficient_register"]["mu_T"]["snapshots"].items()) + ".")
    a("")
    a("## Applicability domain")
    a("")
    for k, v in doc["applicability_domain"].items():
        a(f"- {k}: {v}")
    a("")
    cc = doc["consistency_check_vs_DragCompressor"]
    a("## Consistency check against the free-molecular DragCompressor")
    a("")
    a(f"Label: `{cc['label']}`. Configuration: {cc['configuration']}.")
    a("")
    a("| gas | p_in (Pa) | Q / plane capacity | K DragCompressor | K candidate | rel. diff ln K | Kn_in | comparable |")
    a("|---|---|---|---|---|---|---|---|")
    for r in cc["rows"]:
        a(f"| {r['gas']} | {r['p_in_Pa']:g} | {r['throughput_fraction_of_plane_capacity']:g} | {r['K_DragCompressor']} | "
          f"{r['K_candidate']} | {r['lnK_rel_diff']} | {r['kn_in']} | {r['comparable']} |")
    a("")
    for i in cc["interpretation"]:
        a(f"- {i}")
    d = cc["default_geometry_finding"]
    a(f"- default geometry: ln K0 = {d['lnK0_free_molecular']}; one stage near zero flow: DragCompressor K = "
      f"{d['K_DragCompressor_one_stage_near_zero_flow']}, candidate K = {d['K_candidate_one_stage_near_zero_flow']}. "
      f"{d['note']} (`{d['architecture_point_status']}`).")
    a("")
    ap = doc["admission_plan"]
    a("## Admission plan")
    a("")
    a(f"Current status: `{ap['current_status']}`. {ap['rule']}")
    a("")
    for r in ap["routes"]:
        a(f"- **{r['route']}**: {r['data']}." + (f" {r['status']}." if "status" in r else "") +
          (f" T-1: {r['T-1']}. T-2: {r['T-2']}. {r['note']}." if "T-1" in r else ""))
    a("")
    a("Pre-registration before any comparison:")
    for s in ap["pre_registration_before_any_comparison"]:
        a(f"1. {s}")
    a("")
    a(f"Until admitted: {ap['until_admitted']}.")
    a("")
    a(f"Access policy: {doc['access_policy']}.")
    a("")
    return "\n".join(L)


def main(argv) -> int:
    doc = build()
    js = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    md = render_md(doc)
    if "--check" in argv:
        ok = OUT_JSON.is_file() and OUT_JSON.read_text(encoding="utf-8") == js \
            and OUT_MD.is_file() and OUT_MD.read_text(encoding="utf-8") == md
        print("OK" if ok else "STALE: rerun the builder")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {_rel(OUT_JSON)} and {_rel(OUT_MD)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
