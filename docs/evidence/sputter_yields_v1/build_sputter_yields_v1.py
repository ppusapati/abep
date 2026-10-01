#!/usr/bin/env python3
"""Species-resolved sputter-yield evidence register v1 (owner A9.12 S5.13 P4-OQ-04; Q0 matrix S5.11 P4-OQ-02).

Reads the hand-transcribed inputs in ``sputter_yield_inputs_v1.json`` (same folder) and writes

* ``sputter_yields_v1.json``  - machine-readable register (sources, records, coverage matrix, acquisition requests,
  measurement-needed list, consistency checks), and
* ``SPUTTER_YIELDS_V1.md``    - the generated companion document.

Evidence only: nothing in abep_sim/ or hallthruster_bridge/ reads it. Every numeric yield in the register is an
ELEMENTAL-target literature or semi-empirical value carried as a prior bound; no alloy or coating value is produced, and
molecular-ion (N2+, O2+) cells carry no number at all.

Usage:  python docs/evidence/sputter_yields_v1/build_sputter_yields_v1.py [--check]

``--check`` rebuilds both outputs in memory and fails (exit 1) unless they match the files on disk byte for byte.
Missing or unknown input fields raise ``ValueError``; a changed sha256 of a cited owner-decision file raises.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = "docs/evidence/sputter_yields_v1"
INPUTS = HERE / "sputter_yield_inputs_v1.json"
OUT_JSON = HERE / "sputter_yields_v1.json"
OUT_MD = HERE / "SPUTTER_YIELDS_V1.md"

ACCESS_TYPES = {"OPEN", "OPEN_NOT_RETRIEVABLE_AUTOMATED", "PAYWALLED_ACQUISITION_NEEDED"}
REQUIRED_SPECIES = ("N+", "N2+", "O+", "O2+")
ATOMIC_SPECIES = {"N+": "N", "O+": "O"}
MOLECULAR_SPECIES = ("N2+", "O2+")
MATERIAL_CLASSES = {"alloy", "coating", "oxide_coating", "element"}
TOP_KEYS = ("id", "date", "base_commit", "screening_guardbands", "decisions", "read_only_references", "species_required",
            "species_context_not_assessed", "reporting_energy_grid_eV", "reporting_energy_grid_note", "sources",
            "atomic_weights", "atomic_numbers", "nifs_table1", "nifs_worked_example", "nifs_formula_reading",
            "nifs_caption_fits", "trim_tables", "apid_fit_params", "q0_matrix", "acquisition_requests", "search_log",
            "access_log")
SOURCE_KEYS = ("id", "citation", "url", "doi", "access", "access_detail", "retrieved", "sha256", "evidence_level",
               "kind")
Q0_KEYS = ("row", "p4_candidate", "label", "material_class", "exact_specification_status", "surface_state_in_service",
           "elements_named_in_registered_label", "label_basis")
CAPTION_KEYS = ("id", "projectile", "target", "figure", "report_page", "pdf_page", "A", "Q", "Us_eV", "s",
                "W_factor_of_Us", "best_fit_Us", "legend", "caption_remark", "data_vs_curve")
APID_KEYS = ("id", "projectile", "target", "pdf_page", "lambda", "q", "mu", "eps_L_per_eV", "Eth_eV", "avg_error_pct",
             "Emax_eV", "comments")
AR_KEYS = ("id", "source", "provides", "lawful_route", "relevant_cells_text", "applies_to")
# optional keys (allowed but not required); every other key is rejected (fail closed)
TOP_OPTIONAL = ("purpose",)
# owner A9.17 screening guardbands (frozen 2026-10-01; values read from the inputs and cross-checked against the decision)
GUARDBAND_KEYS = ("status", "E_screen_factor", "F_worst", "decision", "use_in_this_register", "scope",
                  "provenance_history", "first_build")
GUARDBAND_DECISION_KEYS = ("id", "decision_key", "answer", "json", "json_sha256", "verbatim_md", "verbatim_md_sha256",
                           "verbatim_quote")
GUARDBAND_FIRST_BUILD_KEYS = ("commit", "inputs_sha256", "register_json_sha256", "register_md_sha256",
                              "screening_outcomes")
SOURCE_OPTIONAL = ("abstract_statement", "same_file_as", "scope_note")
AR_OPTIONAL = ("priority_note",)
TRIM_KEYS = ("id", "projectile", "target", "locator", "header", "angles_deg", "rows", "flags")
DECISION_KEYS = ("id", "json", "json_sha256", "verbatim_md", "question_ids", "applied")
READ_ONLY_REF_KEYS = ("path", "sha256_at_base_commit", "ids_used", "note")
BLOCK_KEYS = {"atomic_weights": ("source", "values"),
              "nifs_table1": ("source", "locator", "columns", "rows"),
              "nifs_worked_example": ("source", "locator", "projectile", "target", "energy_eV", "printed_yield",
                                      "printed_Eth_eV", "note"),
              "nifs_formula_reading": ("source", "locator", "alpha_branch_note", "threshold_note"),
              "nifs_caption_fits": ("source", "note", "rows", "w_inconsistency_note"),
              "trim_tables": ("source", "note", "tables"),
              "apid_fit_params": ("source", "formula_locator", "rows")}
# blocks whose numbers are transcribed into or evaluated by this register: their source must be OPEN
NUMERIC_BLOCKS = ("atomic_weights", "nifs_table1", "nifs_worked_example", "nifs_caption_fits", "trim_tables",
                  "apid_fit_params")
# owner A9.12 S5.11 (P4-OQ-02) Q0 matrix candidates, as registered in the read-only P4 register
Q0_CANDIDATES = ("CAND-01", "CAND-02A", "CAND-02B", "CAND-02C", "CAND-02D", "CAND-03A", "CAND-03B", "CAND-03C",
                 "CAND-04", "CAND-05", "CAND-06", "CAND-07", "CAND-08", "CAND-09")
# The APID-reproduction screen factors (E_screen = E_screen_factor x Eth; F_worst) are NOT builder constants: they are the
# owner A9.17 screening guardbands in inputs["screening_guardbands"] (see verify_guardbands).
IDENTITY_W_TOL = 0.005         # captions print W as k * Us; Table 1 prints W to two decimals
TOL_WORKED_EXAMPLE = 0.02      # relative, see nifs_worked_example.note
TOL_MASS_RATIO = 0.006         # captions print A to two decimals

# ------------------------------------------------------------------------------------------------ input handling


def _require(obj: dict, keys, where: str, optional=()) -> None:
    """Fail closed: every required key present, and no key outside required + optional."""
    if not isinstance(obj, dict):
        raise ValueError(f"{where}: expected an object")
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ValueError(f"{where}: missing required field(s) {missing}")
    unknown = sorted(set(obj) - set(keys) - set(optional))
    if unknown:
        raise ValueError(f"{where}: unknown field(s) {unknown}")


def _finite_nonneg(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(path: Path = INPUTS) -> dict:
    if not path.is_file():
        raise ValueError(f"inputs file missing: {path}")
    with path.open(encoding="utf-8") as fh:
        d = json.load(fh)
    validate_inputs(d)
    return d


def validate_inputs(d: dict) -> None:
    _require(d, TOP_KEYS, "inputs", TOP_OPTIONAL)
    for blk, keys in BLOCK_KEYS.items():
        _require(d[blk], keys, blk)
    for dec in d["decisions"]:
        _require(dec, DECISION_KEYS, f"decision {dec.get('id') if isinstance(dec, dict) else dec}")
    for ref in d["read_only_references"]:
        _require(ref, READ_ONLY_REF_KEYS, f"read-only reference {ref.get('path') if isinstance(ref, dict) else ref}")
    for sp in d["species_context_not_assessed"]:
        _require(sp, ("species", "why"), "species_context_not_assessed entry")
    for s in d["search_log"]:
        _require(s, ("query", "result"), "search_log entry")
    for s in d["access_log"]:
        _require(s, ("url", "result"), "access_log entry")
    if tuple(d["species_required"]) != REQUIRED_SPECIES:
        raise ValueError(f"species_required must be exactly {REQUIRED_SPECIES} (owner P4-OQ-04)")
    src_ids = set()
    for s in d["sources"]:
        _require(s, SOURCE_KEYS, f"source {s.get('id')}", SOURCE_OPTIONAL)
        if s["access"] not in ACCESS_TYPES:
            raise ValueError(f"source {s['id']}: access {s['access']!r} not in {sorted(ACCESS_TYPES)}")
        if s["evidence_level"] not in range(1, 8):
            raise ValueError(f"source {s['id']}: evidence_level must be 1..7")
        if s["id"] in src_ids:
            raise ValueError(f"duplicate source id {s['id']}")
        src_ids.add(s["id"])
    for blk in ("atomic_weights", "nifs_table1", "nifs_worked_example", "nifs_caption_fits", "trim_tables",
                "apid_fit_params"):
        sid = d[blk].get("source")
        if sid not in src_ids:
            raise ValueError(f"{blk}: unknown or missing source {sid!r}")
    access = {s["id"]: s["access"] for s in d["sources"]}
    for blk in NUMERIC_BLOCKS:
        if access[d[blk]["source"]] != "OPEN":
            raise ValueError(f"{blk}: numbers transcribed from source {d[blk]['source']} with access "
                             f"{access[d[blk]['source']]!r}; only OPEN sources may carry numbers")
    for row in d["nifs_caption_fits"]["rows"]:
        _require(row, CAPTION_KEYS, f"caption fit {row.get('id')}")
    for row in d["apid_fit_params"]["rows"]:
        _require(row, APID_KEYS, f"APID row {row.get('id')}")
    for t in d["trim_tables"]["tables"]:
        _require(t, TRIM_KEYS, f"TRIM {t.get('id')}")
        for r in t["rows"]:
            if len(r) != 1 + len(t["angles_deg"]):
                raise ValueError(f"TRIM {t['id']}: row {r} does not match angles {t['angles_deg']}")
            if not (_finite_nonneg(r[0]) and r[0] > 0):
                raise ValueError(f"TRIM {t['id']}: energy {r[0]!r} must be a positive finite number")
            for v in r[1:]:
                if v is not None and not _finite_nonneg(v):
                    raise ValueError(f"TRIM {t['id']}: yield {v!r} at {r[0]} eV must be finite and non-negative (or null)")
    for q in d["q0_matrix"]:
        _require(q, Q0_KEYS, f"q0 row {q.get('p4_candidate')}")
        if q["material_class"] not in MATERIAL_CLASSES:
            raise ValueError(f"q0 {q['p4_candidate']}: material_class {q['material_class']!r}")
    cands = [q["p4_candidate"] for q in d["q0_matrix"]]
    if len(cands) != len(set(cands)) or set(cands) != set(Q0_CANDIDATES):
        raise ValueError(f"q0_matrix candidates {sorted(cands)} must be exactly the 14 S5.11 candidates "
                         f"{list(Q0_CANDIDATES)}, each once")
    for a in d["acquisition_requests"]:
        _require(a, AR_KEYS, f"acquisition request {a.get('id')}", AR_OPTIONAL)
        _require(a["applies_to"], ("candidates", "species"), f"acquisition request {a['id']} applies_to")
        if a["source"] is not None and a["source"] not in src_ids:
            raise ValueError(f"{a['id']}: unknown source {a['source']}")
    for el in d["nifs_table1"]["rows"]:
        if el not in d["atomic_weights"]["values"] or el not in d["atomic_numbers"]:
            raise ValueError(f"element {el}: atomic weight / number missing")
    for proj in ("N", "O", "He"):
        if proj not in d["atomic_weights"]["values"] or proj not in d["atomic_numbers"]:
            raise ValueError(f"projectile {proj}: atomic weight / number missing")


def verify_guardbands(d: dict) -> dict:
    """Owner A9.17 (decision key SPUTTER): E_screen = 1.10 x E_threshold, F_worst = 1.25, frozen prospectively as
    screening / down-selection guardbands. The values in the inputs must equal the decision file's owner_supplied_values,
    and the decision json / verbatim md must match their pinned sha256 (decisions are immutable)."""
    g = d["screening_guardbands"]
    _require(g, GUARDBAND_KEYS, "screening_guardbands")
    _require(g["decision"], GUARDBAND_DECISION_KEYS, "screening_guardbands.decision")
    _require(g["first_build"], GUARDBAND_FIRST_BUILD_KEYS, "screening_guardbands.first_build")
    if g["status"] != "OWNER_DEFINED_SCREENING_GUARDBANDS":
        raise ValueError(f"screening_guardbands.status {g['status']!r} != OWNER_DEFINED_SCREENING_GUARDBANDS")
    dec = g["decision"]
    for key, rel in (("json_sha256", dec["json"]), ("verbatim_md_sha256", dec["verbatim_md"])):
        p = ROOT / rel
        if not p.is_file():
            raise ValueError(f"screening_guardbands: decision file missing: {rel}")
        got = _sha256(p)
        if got != dec[key]:
            raise ValueError(f"screening_guardbands: {rel} sha256 {got} != pinned {dec[key]} (decisions are immutable)")
    od = json.loads((ROOT / dec["json"]).read_text(encoding="utf-8"))
    if od["decisions"][dec["decision_key"]]["answer"] != dec["answer"]:
        raise ValueError("screening_guardbands: decision answer does not match the owner decision file")
    osv = od["owner_supplied_values"]
    for k in ("E_screen_factor", "F_worst"):
        v = g[k]
        if not (_finite_nonneg(v) and v > 0) or v != osv[k]:
            raise ValueError(f"screening_guardbands.{k} = {v!r} differs from the owner-supplied value {osv[k]!r} "
                             f"({dec['json']}); the guardbands are owner constants, never lane-chosen")
    def norm(t: str) -> str:   # the verbatim record wraps lines; compare whitespace-normalised
        return " ".join(t.split())
    if norm(dec["verbatim_quote"]) not in norm((ROOT / dec["verbatim_md"]).read_text(encoding="utf-8")):
        raise ValueError("screening_guardbands: verbatim_quote not found in the verbatim decision record")
    return g


def verify_decision_pins(d: dict) -> list:
    out = []
    for dec in d["decisions"]:
        _require(dec, DECISION_KEYS, f"decision {dec.get('id')}")
        p = ROOT / dec["json"]
        if not p.is_file():
            raise ValueError(f"decision file missing: {dec['json']}")
        got = _sha256(p)
        if got != dec["json_sha256"]:
            raise ValueError(f"decision {dec['id']}: sha256 {got} != pinned {dec['json_sha256']} (decisions are immutable)")
        if not (ROOT / dec["verbatim_md"]).is_file():
            raise ValueError(f"decision {dec['id']}: verbatim md missing: {dec['verbatim_md']}")
        out.append({"id": dec["id"], "json": dec["json"], "json_sha256": got, "verbatim_md": dec["verbatim_md"],
                    "question_ids": dec["question_ids"], "applied": dec["applied"]})
    return out

# ------------------------------------------------------------------------------------------------ physics (cited formulas)


def yamamura_tawara(E: float, Z1: int, M1: float, Z2: int, M2: float, Us: float, Q: float, W: float, s: float) -> dict:
    """NIFS-DATA-23 Eqs. (4), (15)-(22) (report pp. 3, 7-8). Returns yield (atoms/ion) and Eth (eV).

    alpha* branch: the 0.249 branch is used for M1 <= M2, as the paper's worked example and Fig. 1 do (the printed Eq. (17)
    labels are inverted relative to that use; see inputs nifs_formula_reading.alpha_branch_note)."""
    for name, v in (("E", E), ("M1", M1), ("M2", M2), ("Us", Us), ("Q", Q), ("W", W), ("s", s)):
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
            raise ValueError(f"yamamura_tawara: {name} must be a positive finite number, got {v!r}")
    zz = (Z1 ** (2.0 / 3.0) + Z2 ** (2.0 / 3.0))
    eps = 0.03255 / (Z1 * Z2 * zz ** 0.5) * M2 / (M1 + M2) * E                                  # Eq. (22)
    se = math.sqrt(eps)
    sn_tf = 3.441 * se * math.log(eps + 2.718) / (1.0 + 6.355 * se + eps * (6.882 * se - 1.708))  # Eq. (4)
    ke = 0.079 * (M1 + M2) ** 1.5 / (M1 ** 1.5 * M2 ** 0.5) * Z1 ** (2.0 / 3.0) * Z2 ** 0.5 / zz ** 0.75  # Eq. (20)
    Sn = 84.78 * Z1 * Z2 / zz ** 0.5 * M1 / (M1 + M2) * sn_tf                                   # Eq. (21)
    r = M2 / M1
    alpha = 0.249 * r ** 0.56 + 0.0035 * r ** 1.5 if M1 <= M2 else 0.088 * r ** -0.15 + 0.165 * r  # Eq. (17)
    gamma = 4.0 * M1 * M2 / (M1 + M2) ** 2                                                     # Eq. (19)
    Eth = (6.7 / gamma if M1 >= M2 else (1.0 + 5.7 * M1 / M2) / gamma) * Us                    # Eq. (18)
    Gamma = W / (1.0 + (M1 / 7.0) ** 3)                                                         # Eq. (16)
    if E <= Eth:
        return {"Y": 0.0, "Eth_eV": Eth, "below_threshold": True}
    Y = 0.042 * Q * alpha / Us * Sn / (1.0 + Gamma * ke * eps ** 0.3) * (1.0 - math.sqrt(Eth / E)) ** s  # Eq. (15)
    return {"Y": Y, "Eth_eV": Eth, "below_threshold": False}


def apid_fit(E: float, lam: float, q: float, mu: float, epsL: float, Eth: float) -> float:
    """IAEA APID 7B report p. 18 (PDF p. 20) fit formula (used only for the reproduction check):

    Y = 0.5 q x ln(1 + 1.2288 eps) / (lambda + x [eps + 0.1728 sqrt(eps) + 0.008 eps^0.1504]),  x = (E/Eth - 1)^mu,
    eps = E eps_L. The bracket multiplies only the threshold term x, not lambda."""
    for name, v in (("E", E), ("lambda", lam), ("q", q), ("mu", mu), ("eps_L", epsL), ("Eth", Eth)):
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
            raise ValueError(f"apid_fit: {name} must be a positive finite number, got {v!r}")
    if E <= Eth:
        return 0.0
    x = (E / Eth - 1.0) ** mu
    e = E * epsL
    w = e + 0.1728 * math.sqrt(e) + 0.008 * e ** 0.1504
    return 0.5 * q * x * math.log(1.0 + 1.2288 * e) / (lam + x * w)


def _worst_factor(pts):
    return max((max(p["ratio"], 1.0 / p["ratio"]) for p in pts if p["ratio"] > 0), default=None)


def _r(x: float, n: int = 4):
    """Round to n significant figures for stable JSON output."""
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.{n}g}")

# ------------------------------------------------------------------------------------------------ build


def build(d: dict) -> dict:
    decisions = verify_decision_pins(d)
    gb = verify_guardbands(d)
    e_screen, f_worst = gb["E_screen_factor"], gb["F_worst"]
    aw = d["atomic_weights"]["values"]
    zn = d["atomic_numbers"]
    t1 = d["nifs_table1"]["rows"]
    grid = d["reporting_energy_grid_eV"]
    if not grid or any((not isinstance(e, (int, float))) or e <= 0 for e in grid):
        raise ValueError("reporting_energy_grid_eV must be a non-empty list of positive energies")

    fitted = [r["Us_eV"] / t1[r["target"]][0] for r in d["nifs_caption_fits"]["rows"] if r["best_fit_Us"]]
    if not fitted:
        raise ValueError("no best-fit-Us caption rows: the reactive-projectile statement cannot be derived")
    us_span = f"{min(fitted):.2f}x to {max(fitted):.2f}x"
    no_data_els = sorted(el for el in t1 if el != "Au" and not any(r["target"] == el for r in d["nifs_caption_fits"]["rows"]))
    fit_els = sorted({r["target"] for r in d["nifs_caption_fits"]["rows"] if r["best_fit_Us"]})

    def is_identity(row):
        us_t, q_t, w_t, s_t = t1[row["target"]]
        return (not row["best_fit_Us"] and row["Us_eV"] == us_t and row["Q"] == q_t and row["s"] == s_t
                and abs(row["W_factor_of_Us"] * row["Us_eV"] - w_t) <= IDENTITY_W_TOL)

    def yt(proj, targ, E, Us, Q, W, s):
        return yamamura_tawara(E, zn[proj], aw[proj], zn[targ], aw[targ], Us, Q, W, s)

    checks = []
    # (1) worked example reproduction
    we = d["nifs_worked_example"]
    us, Q, W, s = t1[we["target"]]
    y = yt(we["projectile"], we["target"], we["energy_eV"], us, Q, W, s)
    rel = y["Y"] / we["printed_yield"] - 1.0
    checks.append({"id": "CHK-YT-WORKED-EXAMPLE", "what": "NIFS-DATA-23 sec. 7: 1 keV He -> Au",
                   "printed_yield": we["printed_yield"], "computed_yield": _r(y["Y"]), "relative_residual": _r(rel, 3),
                   "printed_Eth_eV": we["printed_Eth_eV"], "computed_Eth_eV": _r(y["Eth_eV"]),
                   "tolerance": TOL_WORKED_EXAMPLE, "pass": abs(rel) <= TOL_WORKED_EXAMPLE})
    if abs(rel) > TOL_WORKED_EXAMPLE:
        raise ValueError(f"Yamamura-Tawara implementation does not reproduce the worked example (residual {rel:.3%})")
    # (2) mass ratios vs captions
    worst = 0.0
    for row in d["nifs_caption_fits"]["rows"]:
        a = aw[row["target"]] / aw[row["projectile"]]
        worst = max(worst, abs(a - row["A"]))
        if abs(a - row["A"]) > TOL_MASS_RATIO:
            raise ValueError(f"{row['id']}: M2/M1 {a:.4f} disagrees with caption A {row['A']}")
    n_cap = len(d["nifs_caption_fits"]["rows"])
    checks.append({"id": "CHK-MASS-RATIOS",
                   "what": f"CIAAW atomic weights vs caption A = M2/M1 ({n_cap} caption{'s' if n_cap != 1 else ''})",
                   "max_abs_difference": _r(worst, 3), "tolerance": TOL_MASS_RATIO, "pass": True})

    records = []
    # TRIM.SP tables (transcribed)
    for t in d["trim_tables"]["tables"]:
        vals = []
        for r in t["rows"]:
            for ang, v in zip(t["angles_deg"], r[1:]):
                if v is not None:
                    vals.append({"E_eV": r[0], "angle_deg": ang, "Y_atoms_per_ion": v})
        es = [r[0] for r in t["rows"]]
        records.append({
            "id": t["id"], "kind": "TRIM_SP_TABLE", "source": d["trim_tables"]["source"], "locator": t["locator"],
            "projectile": t["projectile"] + "+", "projectile_note": "TRIM.SP projectile atom; charge state not modelled (neutral and singly charged ions equivalent at these energies in BCA)",
            "target": t["target"] + " (pure element, flat, low fluence)", "target_element": t["target"],
            "energy_range_eV": [min(es), max(es)], "angles_deg": t["angles_deg"], "values": vals,
            "header_as_printed": t["header"], "flags": t["flags"],
            "evidence_level": 4, "evidence_class": "model-derived",
            "measured_or_model": "TRIM.SP binary-collision Monte Carlo (calculated)",
            "uncertainty": "source: statistical error usually < 3 % (1 sigma) for Y > 1e-5, up to 100 % at the lowest values; model-form uncertainty (surface binding energy, compound / nitride / oxide formation at steady-state fluence) not quantified",
            "transformation_chain": "TRIM.SP output -> IPP 9/132 printed table -> read from rendered page image by this lane (no conversion)",
            "use": "ELEMENTAL_PRIOR_BOUND_ONLY"})
    # Yamamura-Tawara with per-combination caption fits
    gen_vs_fit = []
    for row in d["nifs_caption_fits"]["rows"]:
        p_, t_ = row["projectile"], row["target"]
        us_t, Q_t, W_t, s_t = t1[t_]
        readings = {"W_table1": W_t, "k_times_table1_Us": row["W_factor_of_Us"] * us_t,
                    "k_times_caption_Us": row["W_factor_of_Us"] * row["Us_eV"]}
        vals = []
        for E in grid:
            ys = {k: yt(p_, t_, E, row["Us_eV"], row["Q"], w, row["s"]) for k, w in readings.items()}
            yv = [v["Y"] for v in ys.values()]
            g = yt(p_, t_, E, us_t, Q_t, W_t, s_t)
            vals.append({"E_eV": E, "angle_deg": 0, "Y_min": _r(min(yv)), "Y_max": _r(max(yv)),
                         "W_reading_spread_rel": _r((max(yv) - min(yv)) / max(yv), 3) if max(yv) > 0 else 0.0,
                         "below_formula_threshold": all(v["below_threshold"] for v in ys.values()),
                         "Eth_eV": _r(ys["W_table1"]["Eth_eV"])})
            if g["Y"] > 0 and min(yv) > 0:
                gen_vs_fit.append({"combo": f"{p_}+ -> {t_}", "E_eV": E, "generic_over_fit": _r(g["Y"] / max(yv), 3),
                                   "identity_row": is_identity(row)})
        records.append({
            "id": "YT-FIT-" + row["id"], "kind": "YAMAMURA_TAWARA_CAPTION_FIT", "source": d["nifs_caption_fits"]["source"],
            "locator": f"NIFS-DATA-23 {row['figure']} caption, report p. {row['report_page']} (PDF p. {row['pdf_page']})",
            "projectile": p_ + "+", "target": t_ + " (pure element)", "target_element": t_,
            "parameters_as_printed": {"A": row["A"], "Q": row["Q"], "Us_eV": row["Us_eV"], "s": row["s"],
                                      "W": f"{row['W_factor_of_Us']} Us", "best_fit_Us": row["best_fit_Us"]},
            "caption_remark": row["caption_remark"], "measured_data_in_figure": row["legend"],
            "data_vs_curve_as_seen": row["data_vs_curve"],
            "energy_range_eV": [min(grid), max(grid)], "angles_deg": [0], "values": vals,
            "evidence_level": 5, "evidence_class": "model-derived",
            "measured_or_model": "semi-empirical formula with parameters best-fitted to measured elemental data (normal incidence)",
            "uncertainty": "not stated by the source per point; the W(Z2) reading ambiguity is carried as Y_min..Y_max; values below the lowest plotted measured energy are formula extrapolation",
            "transformation_chain": "measured yields (legend refs) -> NIFS-DATA-23 best fit -> caption parameters read from page image -> Eq. (15) evaluated by this builder at the reporting grid",
            "use": "ELEMENTAL_PRIOR_BOUND_ONLY"})
    # Yamamura-Tawara generic Table-1 parameters for every listed element (N and O projectiles)
    fit_combos = {(r["projectile"], r["target"]) for r in d["nifs_caption_fits"]["rows"] if not is_identity(r)}
    ident_set = {(r["projectile"], r["target"]) for r in d["nifs_caption_fits"]["rows"] if is_identity(r)}
    for el in sorted(t1):
        if el == "Au":
            continue  # validation target only
        us_t, Q_t, W_t, s_t = t1[el]
        for p_ in ("N", "O"):
            vals = []
            for E in grid:
                g = yt(p_, el, E, us_t, Q_t, W_t, s_t)
                vals.append({"E_eV": E, "angle_deg": 0, "Y": _r(g["Y"]), "below_formula_threshold": g["below_threshold"],
                             "Eth_eV": _r(g["Eth_eV"])})
            has_fit = (p_, el) in fit_combos
            records.append({
                "id": f"YT-GEN-{p_}-{el}", "kind": "YAMAMURA_TAWARA_GENERIC_TABLE1",
                "source": d["nifs_table1"]["source"], "locator": d["nifs_table1"]["locator"],
                "projectile": p_ + "+", "target": el + " (pure element)", "target_element": el,
                "parameters_as_printed": {"Us_eV": us_t, "Q": Q_t, "W": W_t, "s": s_t},
                "energy_range_eV": [min(grid), max(grid)], "angles_deg": [0], "values": vals,
                "has_combination_specific_fit": has_fit, "caption_uses_table1_parameters": (p_, el) in ident_set,
                "evidence_level": 6, "evidence_class": "model-derived",
                "measured_or_model": "semi-empirical formula with element parameters (Table 1) applied to a reactive projectile; "
                                     + ("a combination-specific best fit exists (see YT-FIT record) and differs" if has_fit
                                        else "the figure caption for this combination prints the Table 1 parameters themselves (identity, not a refit; see YT-FIT record and caption remark)" if (p_, el) in ident_set
                                        else "no N/O measurement on this element in NIFS-DATA-23 Table 3, so the result is unvalidated for this projectile"),
                "uncertainty": f"large and unquantified: where measured N/O data exist the source had to refit Us ({us_span} the Table 1 value), see CHK-GENERIC-VS-FIT",
                "transformation_chain": "Table 1 parameters read from page image -> Eq. (15) evaluated by this builder",
                "use": "ELEMENTAL_PRIOR_BOUND_ONLY"})
    rs = [g["generic_over_fit"] for g in gen_vs_fit if not g["identity_row"]]
    if not rs:
        raise ValueError("CHK-GENERIC-VS-FIT: no refitted caption combination above threshold")
    refit_combos = sorted({f"{r['projectile']}+ -> {r['target']}" for r in d["nifs_caption_fits"]["rows"] if not is_identity(r)})
    ident_combos = sorted({f"{r['projectile']}+ -> {r['target']}" for r in d["nifs_caption_fits"]["rows"] if is_identity(r)})
    checks.append({"id": "CHK-GENERIC-VS-FIT",
                   "what": f"Table-1 generic yield / caption-fit yield (max of W readings) for the {len(refit_combos)} N/O combinations whose caption parameters are refitted, over the reporting grid where both are above threshold",
                   "ratio_min": min(rs), "ratio_max": max(rs), "refitted_combinations": refit_combos,
                   "identity_combinations_excluded": ident_combos,
                   "identity_rule": f"caption row with best_fit_Us false, Us, Q and s equal to Table 1 and |k * Us - W_table1| <= {IDENTITY_W_TOL} eV: the caption curve is the Table-1 evaluation itself, so its points (ratio about 1) carry identity_row = true and are excluded from ratio_min / ratio_max",
                   "points": gen_vs_fit,
                   "reading": "the generic Table-1 evaluation is not a reliable N/O prior: it departs from the data-fitted curve by the ratio range shown, mostly upward (the fits raise Us for N/O)",
                   "pass": None})
    # YT caption fit vs TRIM.SP on common points
    trim_by = {(t["projectile"], t["target"]): t for t in d["trim_tables"]["tables"]}
    cmp_pts = []
    for row in d["nifs_caption_fits"]["rows"]:
        t = trim_by.get((row["projectile"], row["target"]))
        if t is None:
            continue
        for r in t["rows"]:
            E, y0 = r[0], r[1]
            if E in grid and y0:
                us_t, _, W_t, _ = t1[row["target"]]
                ys = [yt(row["projectile"], row["target"], E, row["Us_eV"], row["Q"], w, row["s"])["Y"]
                      for w in (W_t, row["W_factor_of_Us"] * us_t, row["W_factor_of_Us"] * row["Us_eV"])]
                cmp_pts.append({"combo": f"{row['projectile']}+ -> {row['target']}", "E_eV": E, "TRIM_SP": y0,
                                "YT_fit_max": _r(max(ys)),
                                "YT_over_TRIM": _r(max(ys) / y0, 3) if max(ys) > 0 else None,
                                "YT_below_formula_threshold": max(ys) == 0})
    checks.append({"id": "CHK-YT-FIT-VS-TRIM", "what": "caption-fit semi-empirical yield vs TRIM.SP (IPP 9/132) at common energies, normal incidence",
                   "points": cmp_pts,
                   "reading": "model-to-model spread for the same elemental target and projectile; it is a lower limit of the prior-bound width, not an error estimate",
                   "pass": None})
    # APID fits: transcribed, reproduction check against the TRIM points they were fitted to
    apid_rows = []
    for row in d["apid_fit_params"]["rows"]:
        t = trim_by.get((row["projectile"], row["target"]))
        pts = []
        if t is not None:
            for r in t["rows"]:
                if r[1] and row["Eth_eV"] < r[0] <= row["Emax_eV"] and r[0] <= 1000:
                    y = apid_fit(r[0], row["lambda"], row["q"], row["mu"], row["eps_L_per_eV"], row["Eth_eV"])
                    pts.append({"E_eV": r[0], "TRIM_SP": r[1], "fit": _r(y), "ratio": _r(y / r[1], 3),
                                "near_threshold": r[0] < e_screen * row["Eth_eV"]})
        worst_all = _worst_factor(pts)
        worst_away = _worst_factor([p for p in pts if not p["near_threshold"]])
        if worst_away is not None and worst_away > f_worst:
            raise ValueError(f"{row['id']}: printed APID fit does not reproduce TRIM.SP away from threshold "
                             f"(worst factor {worst_away:.3f} > F_worst {f_worst}); transcription or formula error")
        apid_rows.append({"id": row["id"], "projectile": row["projectile"] + "+", "target": row["target"],
                          "parameters_as_printed": {k: row[k] for k in ("lambda", "q", "mu", "eps_L_per_eV", "Eth_eV",
                                                                         "avg_error_pct", "Emax_eV")},
                          "comments_as_printed": row["comments"], "locator": f"IAEA APID 7B PDF p. {row['pdf_page']}",
                          "reproduction_check_vs_TRIM_SP": pts,
                          "worst_factor_all_points": _r(worst_all, 3) if worst_all else None,
                          "worst_factor_E_ge_1p1_Eth": _r(worst_away, 3) if worst_away else None,
                          "reproduction": "NO_TRIM_TABLE_TRANSCRIBED" if not pts else "REPRODUCED_AWAY_FROM_THRESHOLD",
                          "status": "NOT_USED_NUMERICALLY",
                          "status_reason": "the fit is an analytic fit to TRIM.SP calculated points (source comment); it adds no evidence independent of the TRIM.SP calculations, which are carried as records where transcribed"})
    checks.append({"id": "CHK-APID-REPRODUCTION",
                   "what": f"IAEA APID 7B fit formula (report p. 18, PDF p. 20) with the printed parameters vs the TRIM.SP points the fits were made to (<= 1 keV); gate: worst factor <= {f_worst:g} for E >= {e_screen:g} Eth",
                   "guardbands": {"E_screen_factor": e_screen, "F_worst": f_worst,
                                  "status": gb["status"], "decision": f"{gb['decision']['id']} {gb['decision']['decision_key']}"},
                   "rows": [{"id": r["id"], "worst_factor_all_points": r["worst_factor_all_points"],
                             "worst_factor_E_ge_1p1_Eth": r["worst_factor_E_ge_1p1_Eth"],
                             "reproduction": r["reproduction"], "status": r["status"]} for r in apid_rows],
                   "reading": "the printed fits reproduce the TRIM.SP points they were fitted to, consistent with the printed average errors, except within a few eV of the fitted threshold (fitted Eth slightly above the TRIM.SP onset); they are still not evaluated as priors because they carry no information beyond the TRIM.SP calculations",
                   "pass": True})

    # regenerated screening outcomes vs the first (non-pre-registered) build: reported, never acted on
    fb = gb["first_build"]["screening_outcomes"]
    now_rows = [{"id": r["id"], "reproduction": r["reproduction"],
                 "excluded_below_E_screen_eV": [p["E_eV"] for p in r["reproduction_check_vs_TRIM_SP"] if p["near_threshold"]],
                 "worst_factor_E_ge_E_screen": r["worst_factor_E_ge_1p1_Eth"]} for r in apid_rows]
    fb_by = {r["id"]: r for r in fb["rows"]}
    now_by = {r["id"]: r for r in now_rows}
    diffs = []
    for rid in sorted(set(fb_by) | set(now_by)):
        if fb_by.get(rid) != now_by.get(rid):
            diffs.append({"id": rid, "first_build": fb_by.get(rid), "regenerated": now_by.get(rid)})
    if fb["chk_apid_reproduction_pass"] is not True:
        diffs.append({"id": "CHK-APID-REPRODUCTION.pass", "first_build": fb["chk_apid_reproduction_pass"],
                      "regenerated": True})
    screening_comparison = {
        "first_build_commit": gb["first_build"]["commit"],
        "first_build_register_json_sha256": gb["first_build"]["register_json_sha256"],
        "rows_compared": len(now_rows),
        "differences": diffs,
        "result": "IDENTICAL" if not diffs else "DIFFERS",
        "note": "reported only; no factor, transcription or status is adjusted because a row or material passes or fails (A9.17)"}

    # coverage matrix
    rec_by_el = {}
    for r in records:
        rec_by_el.setdefault((r["projectile"], r["target_element"]), []).append(r["id"])
    ars = d["acquisition_requests"]

    def ar_applies(a, cand, mclass, sp):
        c = a["applies_to"]["candidates"]
        ok_c = (c == "ALL") or (c == "ALL_NON_ELEMENTAL" and mclass != "element") or (isinstance(c, list) and cand in c)
        return ok_c and sp in a["applies_to"]["species"]

    coverage = []
    for q in d["q0_matrix"]:
        for sp in REQUIRED_SPECIES:
            els = q["elements_named_in_registered_label"]
            cls = q["material_class"]
            prior, context = [], []
            if sp in ATOMIC_SPECIES:
                for el in els:
                    ids = rec_by_el.get((sp, el), [])
                    (context if cls == "oxide_coating" else prior).extend(ids)
            if sp in MOLECULAR_SPECIES:
                applic = "NO_PRIOR_NUMBER (molecular ion: no open species-resolved data on any Q0 element; the per-atom equal-velocity mapping is not applied - SRC-DOBES-2011 abstract reports up to +25 % per-atom enhancement for N2+ on W below 1 keV)"
            elif cls == "element":
                applic = "MATERIAL_MATCHED_ELEMENT__SURFACE_STATE_NOT_MATCHED (low-fluence pure-element models / fits; in-service oxide or nitride not represented)"
            elif cls == "coating":
                applic = "COATING_ELEMENT_PRIOR_BOUND_ONLY (pure-element values; coating microstructure, impurities and O/N surface chemistry not represented)"
            elif cls == "oxide_coating":
                applic = "NOT_REPRESENTATIVE (metal-element values listed as context only; the surface is a mixed metal oxide)"
            elif els:
                applic = "CONSTITUENT_ELEMENT_PRIOR_BOUND_ONLY (elements named in the registered label; alloy composition, preferential sputtering and oxide / nitride scales not represented)"
            else:
                applic = "NO_CONSTITUENT_REGISTERED (no element named in the registered label; mapping needs the exact-grade / lot composition)"
            direction = None
            if q["p4_candidate"] == "CAND-09" and sp in ("O+", "O2+"):
                direction = "PHYSICAL_SPUTTERING_IS_A_LOWER_BOUND_ONLY: O on carbon is dominated by chemical erosion (NIFS-DATA-23 Fig. 19 caption; IAEA APID 7B 2.1.2.7 comment); measured points lie well above the physical-sputtering curve"
            if q["p4_candidate"] == "CAND-08" and sp in ("O+", "O2+"):
                direction = "IAEA APID 7B 2.1.3.7 comment: low-temperature O -> W data probably reflect a tungsten-oxide surface; the elemental values do not bound an oxidised surface"
            disp = ["MEASUREMENT_NEEDED:TP-04"] + [a["id"] for a in ars if ar_applies(a, q["p4_candidate"], cls, sp)]
            coverage.append({"row": q["row"], "p4_candidate": q["p4_candidate"], "label": q["label"], "species": sp,
                             "candidate_specific_value": None,
                             "status": "NO_CANDIDATE_SPECIFIC_DATA",
                             "elemental_prior_records": sorted(prior), "non_representative_context_records": sorted(context),
                             "prior_applicability": applic, "bound_direction_note": direction,
                             "dispositions": disp})

    measurement_needed = []
    for q in d["q0_matrix"]:
        measurement_needed.append({
            "p4_candidate": q["p4_candidate"], "label": q["label"], "route": "TP-04 (P4 test plan; ion source with energy / species control; profilometer; witness holders)",
            "species": list(REQUIRED_SPECIES),
            "exact_specification_prerequisite": q["exact_specification_status"],
            "variables_to_register_before_measurement": [
                "ion species and charge state (N+, N2+, O+, O2+ separately; mass-selected or with measured beam composition)",
                "ion energy range: TBD from the registered H-1 / ICP electrode sheath-energy envelope (CR-04 domain 'sheath_energy_range'; not registered)",
                "angle of incidence: TBD from the electrode geometry",
                "fluence to steady state (compound / oxide / nitride build-up) and target temperature: TBD",
                "surface composition after exposure (S5.12 metrology list includes SEM / XPS)"],
            "applies_when": "candidate survives Q0 and is down-selected for Q1 (S5.11); S5.13 'project ion-beam / materials test route for the down-selected candidate materials / coatings'",
            "acceptance": "TBD at LOCK-2 after metrology commissioning (S5.12); never set from candidate performance"})

    # numeric_values_used is derived: sources cited by a numeric record, plus the atomic-weight source the evaluations use
    access = {s["id"]: s["access"] for s in d["sources"]}
    numeric_src = {r["source"] for r in records} | {d["atomic_weights"]["source"]}
    bad = sorted(sid for sid in numeric_src if access.get(sid) != "OPEN")
    if bad:
        raise ValueError(f"numeric records cite non-OPEN or unknown source(s) {bad}")
    sources = []
    for s in d["sources"]:
        o = dict(s)
        o["numeric_values_used"] = s["id"] in numeric_src
        sources.append(o)

    reg = {
        "id": "sputter_yields_v1",
        "version": "1.1",
        "date": d["date"],
        "base_commit": d["base_commit"],
        "generated_by": REL + "/build_sputter_yields_v1.py (--check reproduces JSON and MD exactly) from " + REL + "/sputter_yield_inputs_v1.json",
        "inputs_sha256": _sha256(INPUTS) if INPUTS.is_file() else None,
        "companion_document": REL + "/SPUTTER_YIELDS_V1.md",
        "test": "tests/test_sputter_yields_v1.py",
        "status": "EVIDENCE REGISTER ONLY. Not wired into any simulator module. No alloy or coating sputter yield exists in this register; no molecular-ion (N2+, O2+) number exists in this register. Every numeric yield is an elemental-target literature or semi-empirical value usable only as a prior bound / for test-matrix selection / comparison / model initialisation (S5.13), never as a candidate value, and never as a CR-04 recession or life input.",
        "evidence_policy": "docs/EVIDENCE.md (CLAUDE.md rules 6, 10): evidence_level = strength / proximity of the source (1-7); evidence_class = quantity type; evaluation of a published formula does not raise the level",
        "owner_decisions": decisions,
        "screening_guardbands": {
            "status": gb["status"], "E_screen_factor": e_screen, "F_worst": f_worst,
            "definition": f"E_screen = {e_screen:g} x E_threshold; F_worst = {f_worst:g}",
            "decision": gb["decision"], "use_in_this_register": gb["use_in_this_register"], "scope": gb["scope"],
            "provenance_history": gb["provenance_history"],
            "preregistration_status": "FIRST_BUILD_NOT_PREREGISTERED__THIS_REGENERATION_PROSPECTIVE",
            "first_build": {k: v for k, v in gb["first_build"].items() if k != "screening_outcomes"},
            "regenerated_vs_first_build": screening_comparison},
        "read_only_references": d["read_only_references"],
        "hard_statements": [
            "NO_SILENT_SUBSTITUTION: no record in this register is an alloy or coating value; coverage cells carry candidate_specific_value = null and status NO_CANDIDATE_SPECIFIC_DATA for every Q0 candidate and every required species (owner S5.13).",
            "NO_MOLECULAR_NUMBERS: N2+ and O2+ cells carry no prior number. The common mapping 'molecule = atoms at the same velocity' is not applied; the only located evidence on it (Dobes 2011 abstract, W) reports up to +25 % per-atom enhancement below 1 keV.",
            f"REACTIVE_PROJECTILES: for N and/or O on {', '.join(fit_els)} the source compilation had to refit the surface binding energy (best-fit Us {us_span} the Table 1 value); generic Table-1 evaluations for elements without N/O data ({', '.join(no_data_els)}) are unvalidated for these projectiles (evidence level 6).",
            "CHEMICAL_EROSION: for O on carbon (isotropic graphite control) physical-sputtering values are a lower bound only.",
            "NO_ENERGY_DOMAIN: the reporting grid is a tabulation grid, not a sheath energy; CR-04 'sheath_energy_range' is not registered.",
            "NO_ACCEPTANCE: thresholds are set at LOCK-2 (S5.12); this register sets none.",
            f"SCREENING_GUARDBANDS_ONLY: E_screen = {e_screen:g} x E_threshold and F_worst = {f_worst:g} are owner-defined screening / down-selection guardbands (A9.17, {gb['decision']['json']} sha256 {gb['decision']['json_sha256'][:12]}..., key {gb['decision']['decision_key']}); never P4 material-acceptance, lifetime or qualification thresholds (S5.12 governs those). The first build that used these values (commit {gb['first_build']['commit'][:7]}) chose them after seeing the data and is NOT pre-registered evidence; this regeneration applies them prospectively."],
        "species_required": list(REQUIRED_SPECIES),
        "species_context_not_assessed": d["species_context_not_assessed"],
        "reporting_energy_grid_eV": grid,
        "reporting_energy_grid_note": d["reporting_energy_grid_note"],
        "formula_reading_notes": {"alpha_branch": d["nifs_formula_reading"]["alpha_branch_note"],
                                  "threshold": d["nifs_formula_reading"]["threshold_note"],
                                  "W_inconsistency": d["nifs_caption_fits"]["w_inconsistency_note"],
                                  "worked_example": d["nifs_worked_example"]["note"]},
        "sources": sources,
        "atomic_weights": d["atomic_weights"],
        "records": records,
        "apid_fits_transcribed": apid_rows,
        "consistency_checks": checks,
        "q0_matrix": d["q0_matrix"],
        "coverage_matrix": coverage,
        "acquisition_requests": d["acquisition_requests"],
        "measurement_needed": measurement_needed,
        "search_log": d["search_log"],
        "access_log": d["access_log"],
        "scope_rules_followed": [
            "published / openly accessible sources only; no contact with any person, lab or supplier; no e-mail; nothing purchased",
            "LXCat not used",
            "no paywall or bot-challenge bypass (access_log); TLS settings unchanged",
            "numbers transcribed only from page images actually read; abstract-level statements carry no number",
            "downloaded PDFs kept in the session scratchpad only (not committed); sha256 recorded per source",
            "docs/experiments/hall_icp/p4_anode_materials/** read only"]}
    return reg

# ------------------------------------------------------------------------------------------------ markdown


def _fmt(x) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.3g}"
    return str(x)


def render_md(reg: dict) -> str:
    L = []
    a = L.append
    a("# Species-resolved sputter-yield evidence register, v1")
    a("")
    a(f"Generated by `{REL}/build_sputter_yields_v1.py` from `sputter_yield_inputs_v1.json`; do not edit by hand "
      "(`--check` reproduces this file and `sputter_yields_v1.json` exactly). Tests: `python -m pytest -q tests/test_sputter_yields_v1.py`.")
    a("")
    a("**Status:** " + reg["status"])
    a("")
    a("## 1. Owner decisions applied")
    a("")
    for dcs in reg["owner_decisions"]:
        a(f"- **{dcs['id']}** `{dcs['json']}` (sha256 `{dcs['json_sha256']}`), verbatim `{dcs['verbatim_md']}`; "
          f"questions: {', '.join(dcs['question_ids'])}.")
        for ap in dcs["applied"]:
            a(f"  - {ap}")
    a("")
    g = reg["screening_guardbands"]
    a(f"- **{g['decision']['id']}** `{g['decision']['json']}` (sha256 `{g['decision']['json_sha256']}`), verbatim "
      f"`{g['decision']['verbatim_md']}`; decision key {g['decision']['decision_key']} = {g['decision']['answer']}.")
    a(f"  - Owner-defined screening guardbands ({g['status']}): {g['definition']}.")
    for k, v in g["use_in_this_register"].items():
        a(f"  - {k}: {v}.")
    a(f"  - Scope: {g['scope']}")
    a(f"  - Pre-registration: {g['provenance_history']}")
    cmp_ = g["regenerated_vs_first_build"]
    a(f"  - Regenerated vs first build (`{cmp_['first_build_commit'][:7]}`): {cmp_['result']} over {cmp_['rows_compared']} "
      f"APID rows ({len(cmp_['differences'])} differences); {cmp_['note']}.")
    a("")
    a("Read-only references: " + "; ".join(f"`{r['path']}` (sha256 at base `{r['sha256_at_base_commit'][:12]}...`)"
                                         for r in reg["read_only_references"]) + ".")
    a("")
    a("## 2. Use restrictions")
    a("")
    for h in reg["hard_statements"]:
        k, _, v = h.partition(": ")
        a(f"- **{k}**: {v}")
    a("")
    a("Species outside this lane's authorisation (listed, not covered): " +
      "; ".join(f"{s['species']}: {s['why']}" for s in reg["species_context_not_assessed"]) + ".")
    a("")
    a("## 3. Coverage of the Q0 matrix (S5.11) by required species")
    a("")
    a("Every cell: candidate-specific value **none**; disposition always includes `MEASUREMENT_NEEDED:TP-04`.")
    a("")
    a("| Q0 row | candidate | species | elemental prior records | applicability | dispositions |")
    a("|---|---|---|---|---|---|")
    for c in reg["coverage_matrix"]:
        pri = ", ".join(c["elemental_prior_records"]) or ("context only: " + ", ".join(c["non_representative_context_records"])
                                                          if c["non_representative_context_records"] else "none")
        app = c["prior_applicability"].split(" (")[0]
        if c["bound_direction_note"]:
            app += " / see note"
        a(f"| {c['row']} | {c['p4_candidate']} {c['label']} | {c['species']} | {pri} | {app} | {', '.join(c['dispositions'])} |")
    a("")
    notes = {(c["p4_candidate"], c["bound_direction_note"]) for c in reg["coverage_matrix"] if c["bound_direction_note"]}
    for cand, n in sorted(notes):
        a(f"- Note {cand}: {n}")
    a("")
    a("## 4. Elemental prior values (atoms/ion, normal incidence)")
    a("")
    a(reg["reporting_energy_grid_note"])
    a("")
    grid = reg["reporting_energy_grid_eV"]
    a("### 4a. Semi-empirical, parameters fitted to measured elemental N / O data (NIFS-DATA-23 captions; level 5)")
    a("")
    a("| record | " + " | ".join(f"{e} eV" for e in grid) + " | measured data in figure |")
    a("|---|" + "---|" * len(grid) + "---|")
    for r in reg["records"]:
        if r["kind"] != "YAMAMURA_TAWARA_CAPTION_FIT":
            continue
        cells = []
        for v in r["values"]:
            cells.append("below Eth" if v["below_formula_threshold"] else
                         (_fmt(v["Y_max"]) if _fmt(v["Y_min"]) == _fmt(v["Y_max"]) else f"{_fmt(v['Y_min'])}-{_fmt(v['Y_max'])}"))
        a(f"| {r['id']} ({r['projectile']} -> {r['target_element']}) | " + " | ".join(cells) + " | " + "; ".join(r["measured_data_in_figure"]) + " |")
    a("")
    a("### 4b. TRIM.SP tables (IPP 9/132; level 4, calculated, low fluence)")
    a("")
    for r in reg["records"]:
        if r["kind"] != "TRIM_SP_TABLE":
            continue
        pts = [v for v in r["values"] if v["angle_deg"] == 0 and v["E_eV"] <= 1000 and v["E_eV"] >= 50]
        a(f"- **{r['id']}** ({r['projectile']} -> {r['target_element']}, 0 deg; {r['locator']}): " +
          ", ".join(f"{v['E_eV']} eV: {_fmt(v['Y_atoms_per_ion'])}" for v in pts) +
          (f". Flags: {'; '.join(r['flags'])}." if r["flags"] else "."))
    a("")
    a("### 4c. Generic Table-1 parameters (level 6; unvalidated for N / O where no data exist)")
    a("")
    a("| element | projectile | " + " | ".join(f"{e} eV" for e in grid) + " | N/O fit exists |")
    a("|---|---|" + "---|" * len(grid) + "---|")
    for r in reg["records"]:
        if r["kind"] != "YAMAMURA_TAWARA_GENERIC_TABLE1":
            continue
        cells = ["below Eth" if v["below_formula_threshold"] else _fmt(v["Y"]) for v in r["values"]]
        a(f"| {r['target_element']} | {r['projectile']} | " + " | ".join(cells) + f" | {'yes' if r['has_combination_specific_fit'] else ('identity (caption = Table 1)' if r['caption_uses_table1_parameters'] else 'no')} |")
    a("")
    a("## 5. Consistency checks")
    a("")
    for c in reg["consistency_checks"]:
        if c["id"] == "CHK-YT-WORKED-EXAMPLE":
            a(f"- **{c['id']}** ({c['what']}): printed {c['printed_yield']}, computed {c['computed_yield']} "
              f"(residual {c['relative_residual']:+.2%}, tolerance {c['tolerance']:.0%}); Eth printed {c['printed_Eth_eV']} eV, computed {c['computed_Eth_eV']} eV.")
        elif c["id"] == "CHK-MASS-RATIOS":
            a(f"- **{c['id']}** ({c['what']}): max |difference| {c['max_abs_difference']} (tolerance {c['tolerance']}).")
        elif c["id"] == "CHK-GENERIC-VS-FIT":
            n_ref = sum(1 for p in c["points"] if not p["identity_row"])
            a(f"- **{c['id']}**: generic / fit ratio {c['ratio_min']} to {c['ratio_max']} over {n_ref} points of the refitted "
              f"combinations ({', '.join(c['refitted_combinations'])}); identity combinations excluded: "
              f"{', '.join(c['identity_combinations_excluded']) or 'none'}. {c['reading']}.")
        elif c["id"] == "CHK-YT-FIT-VS-TRIM":
            a(f"- **{c['id']}**: " + "; ".join(f"{p['combo']} {p['E_eV']} eV: " + ("YT below its threshold, TRIM " + _fmt(p['TRIM_SP']) if p["YT_below_formula_threshold"] else f"YT/TRIM {p['YT_over_TRIM']}") for p in c["points"]) + f". {c['reading']}.")
        elif c["id"] == "CHK-APID-REPRODUCTION":
            a(f"- **{c['id']}** ({c['what']}): " + "; ".join(
                f"{r['id']} {r['reproduction']}, worst factor {_fmt(r['worst_factor_E_ge_1p1_Eth'])} for E >= {c['guardbands']['E_screen_factor']:g} Eth "
                f"({_fmt(r['worst_factor_all_points'])} incl. near-threshold points), {r['status']}" for r in c["rows"]) + f". {c['reading']}.")
    a("")
    a("IAEA APID 7B printed comments (qualitative evidence carried):")
    a("")
    for r in reg["apid_fits_transcribed"]:
        a(f"- {r['id']} {r['projectile']} + {r['target']}: " + " ".join(r["comments_as_printed"]))
    a("")
    a("## 6. Acquisition requests (for the owner / procurement; lawful routes only)")
    a("")
    a("Nothing was purchased and nobody was contacted. Each request is a bibliographic pointer.")
    a("")
    src = {s["id"]: s for s in reg["sources"]}
    for r in reg["acquisition_requests"]:
        s = src.get(r["source"]) if r["source"] else None
        cit = (s["citation"] + (f", doi:{s['doi']}" if s.get("doi") else "")) if s else "(no source located)"
        a(f"- **{r['id']}** - {cit}. Provides: {r['provides'].rstrip('.')}. Cells: {r['relevant_cells_text']}. Route: {r['lawful_route']}.")
    a("")
    a("## 7. Measurement needed (TP-04 ion-beam route)")
    a("")
    a("For every Q0 candidate that is down-selected for Q1, all four species are measured on the candidate itself "
      "(S5.13). Before any measurement, register:")
    a("")
    for v in reg["measurement_needed"][0]["variables_to_register_before_measurement"]:
        a(f"- {v}")
    a("")
    a("| candidate | specification prerequisite |")
    a("|---|---|")
    for m in reg["measurement_needed"]:
        a(f"| {m['p4_candidate']} {m['label']} | {m['exact_specification_prerequisite']} |")
    a("")
    a("Acceptance: " + reg["measurement_needed"][0]["acceptance"] + ".")
    a("")
    a("## 8. Sources")
    a("")
    a("| id | citation | access | level | numbers used | sha256 |")
    a("|---|---|---|---|---|---|")
    for s in reg["sources"]:
        a(f"| {s['id']} | {s['citation']}" + (f", doi:{s['doi']}" if s.get("doi") else "") + (f" ({s['url']})" if s.get("url") else "") +
          f" | {s['access']} | {s['evidence_level']} | {'yes' if s['numeric_values_used'] else 'no'} | {(s['sha256'] or '-')[:16]} |")
    a("")
    a("## 9. Search and access log")
    a("")
    for s in reg["search_log"]:
        a(f"- search: {s['query']} -> {s['result']}")
    for s in reg["access_log"]:
        a(f"- access: {s['url']} -> {s['result']}")
    a("")
    for s in reg["scope_rules_followed"]:
        a(f"- rule followed: {s}")
    a("")
    return "\n".join(L)

# ------------------------------------------------------------------------------------------------ entry points


def render_all(d: dict | None = None):
    d = load_inputs() if d is None else d
    reg = build(d)
    js = json.dumps(reg, indent=1, ensure_ascii=False) + "\n"
    md = render_md(reg)
    return reg, js, md


def check() -> int:
    _, js, md = render_all()
    ok = True
    for path, text in ((OUT_JSON, js), (OUT_MD, md)):
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            print(f"--check: {path.relative_to(ROOT)} is stale or missing")
            ok = False
    if ok:
        print("--check: OK (sputter_yields_v1.json and SPUTTER_YIELDS_V1.md reproduce exactly)")
    return 0 if ok else 1


def main(argv) -> int:
    if "--check" in argv:
        return check()
    _, js, md = render_all()
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
