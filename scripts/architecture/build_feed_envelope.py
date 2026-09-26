#!/usr/bin/env python3
"""Thruster feed-envelope definition v1 (architecture-comparison lane 16, FEED).

Defines the common feed state delivered to the ionization/discharge block, i.e. the thruster boundary of the upstream
gas chain (ICD IF-A5 for the atmospheric port, IF-X2 for the Xe port; `schemas/interfaces/upstream_icd_v1.json`):

    ambient -> intake -> filter -> compressor -> atmospheric gas chamber -> valve -> [IF-A5] -> ionization/discharge
    Xe chamber -> Xe valve -> [IF-X2] -> ionization/discharge

for 180 / 200 / 230 km and the low / mean / high atmosphere levels of the frozen NRLMSIS 2.1 dataset, so that the
three candidate thrust architectures ('hall_only', 'rf_hall', 'ecr_hall') are compared at IDENTICAL feed conditions.
The RF/ECR arms only change the pre-ionization method, which sits downstream of IF-A5, so no quantity in this file
depends on the architecture id.

Rules this script follows (CLAUDE.md rules 1, 3, 5, 6, 10; docs/EVIDENCE.md):
  * Only the existing frozen chain is used: abep_sim.atmosphere (frozen NRLMSIS 2.1 scenario dataset, forced with
    use_msis=False and checked through the returned `source`), abep_sim.intake / intake_tpmc (frozen TPMC surface),
    abep_sim.compressor, abep_sim.reservoir. archengine.py / system.py are only read (their chaining is mirrored, see
    `run_chain`); they are never imported, so no Hall / plasma module is loaded.
  * No hidden design defaults. Every design input of the chain (intake area and geometry, surface state, plenum,
    compressor, chamber, valve) is an explicit named input supplied through --design-inputs, each with a source and
    an evidence class. A missing input raises MissingDesignInput. Without design inputs the design-dependent feed
    quantities are emitted as TBD with the names of the missing inputs: the repository documents no design baseline
    with provenance for them (see `not_adopted`).
  * No silent fallback. Non-frozen atmosphere, out-of-grid intake inputs, a compressor that cannot sustain the chamber
    pressure, an orifice sizing that ends on its bracket, or an unconverged balance give an explicit refusal or a case
    status INFEASIBLE / MODEL_ERROR with null values; never a half-converged state.
  * No Hall transport closure, ensemble member or P5 calibration-nuisance variable enters any field.

Deterministic, no Julia, a few seconds (the design-independent envelope ~1 s; with --design-inputs the nine cases x two
composition conventions ~1-2 s with single-threaded BLAS, which the command line sets by default).

Usage:
  python scripts/architecture/build_feed_envelope.py                  # (re)write the committed envelope
  python scripts/architecture/build_feed_envelope.py --check          # verify the committed files are reproduced
  python scripts/architecture/build_feed_envelope.py --design-inputs D.json --out-dir DIR
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SCRIPT_REL = "scripts/architecture/build_feed_envelope.py"
OUT_DIR_REL = "docs/architecture_comparison/feed_envelope"
JSON_NAME = "feed_envelope_v1.json"
MD_NAME = "FEED_ENVELOPE.md"
SCHEMA_REL = "schemas/architecture_comparison/feed_envelope_v1.schema.json"
ICD_SCHEMA_REL = "schemas/interfaces/upstream_icd_v1.json"
DESIGN_INPUTS_FORMAT = "feed_design_inputs_v1"

ENVELOPE_NAME = "feed_envelope"
ENVELOPE_VERSION = "1.0.0"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
ALTITUDES_KM = (180.0, 200.0, 230.0)
LEVELS = ("low", "mean", "high")
AIR_SPECIES = ("O", "N2", "O2")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
SIG_DIGITS = 12                      # output rounding (significant digits) so the committed JSON is platform-stable
FROZEN_NODE_RTOL = 1e-12             # atmosphere() at a grid node must equal the CSV row (no interpolation)
MASS_FRACTION_CLOSURE_TOL = 1e-8     # CSV stores fractions with 9 significant digits (float_format %.8e)

# case statuses
ST_MISSING = "DESIGN_INPUTS_MISSING"
ST_OK = "OK"
ST_INFEASIBLE = "INFEASIBLE"
ST_MODEL_ERROR = "MODEL_ERROR"

# chain-convention tokens accepted as design-input values
TOKEN_T_FROM_COMPRESSOR = "system_evaluate_compressor_machine_T_clamped_300_500K"
TOKEN_UPSTREAM_COLLISIONS = "system_evaluate_heuristic_10_per_turbo_row_plus_50_per_drag_stage"

# module-internal constants mirrored only to CHECK module results (never to produce a value)
ORIFICE_BRACKET_M2 = (1e-8, 3e-2)    # abep_sim/reservoir.py:size_orifice_for_pressure (lo, hi)
COMP_RECIRC_RTOL = 1e-4              # abep_sim/compressor.py:DragCompressor.run fixed-point stopping criterion
RES_BALANCE_RTOL = 1e-6              # abep_sim/reservoir.py:Reservoir.steady_state stopping criterion

INPUT_FILES = (
    ("abep_sim/data/atmosphere_msis21_v1.csv", "frozen NRLMSIS 2.1 scenario values (every free-stream number)"),
    ("abep_sim/data/atmosphere_msis21_v1.json", "frozen atmosphere metadata (grid, ap, epoch, sha256_16)"),
    ("abep_sim/data/intake_surface_v1.csv", "frozen TPMC response surface (design-conditional chain only)"),
    ("abep_sim/data/intake_surface_v1.json", "frozen TPMC surface metadata (grid bounds, n_per_point, max_unresolved)"),
    ("abep_sim/atmosphere.py", "atmosphere(), _SOLAR_F107 level mapping, FROZEN_EPOCH, orbital_velocity()"),
    ("abep_sim/constants.py", "M_SPECIES (mole-fraction derivation), MU_EARTH, R_EARTH, K_B"),
)
# Read (imported or parsed) but not hashed: their content enters the envelope only through code defaults listed in the
# design-input contract and through the design-conditional chain, both of which the reproduction test compares
# directly. docs/HISTORY.md is append-only project history; its quoted tokens are checked by the test.
FILES_READ = (
    ("abep_sim/intake.py", "IntakeParams, CompressorParams, collection(), compress(), _tpmc_surface()"),
    ("abep_sim/intake_tpmc.py", "IntakeSurface (frozen TPMC ROM)"),
    ("abep_sim/compressor.py", "DragCompressor.run(), size_for()"),
    ("abep_sim/reservoir.py", "Reservoir.steady_state(), size_orifice_for_pressure()"),
    ("abep_sim/materials.py", "DB (wall materials, gamma_O recombination priors)"),
    ("abep_sim/system.py", "read only (ast): Config defaults and the gas-path chaining mirrored in run_chain()"),
    ("abep_sim/archengine.py", "read only (ast): gas_path_state defaults"),
    ("abep_sim/uq_modular.py", "read only (ast): PRIORS['accommodation'] (the only upstream uncertainty prior in code)"),
    ("docs/HISTORY.md", "historical reference values quoted in `not_adopted` (token-checked by the test)"),
)

VALIDITY_DOMAINS = {
    "D-ATM-FROZEN": ("Frozen NRLMSIS 2.1 scenario dataset abep_sim/data/atmosphere_msis21_v1.{csv,json}: altitude "
                     "150-300 km (2 km grid), F10.7 = F10.7A in {70, 100, 150, 190, 230}, ap 15, orbit-averaged "
                     "(lat -60..60 x lon 0..270 at fixed UT), epoch 2028-03-21T12:00, species O/N2/O2 only "
                     "(He, H, Ar, N dropped per the dataset metadata: '<2 % by mass at 180-230 km; rho includes "
                     "them': verify). ICD id reused (schemas/interfaces/upstream_icd_v1.json)."),
    "D-ORBIT-CIRCULAR": ("Circular Keplerian orbital speed sqrt(MU_EARTH / (R_EARTH + h)) with constants.py values "
                         "(spherical Earth radius 6371 km). Relative speed (co-rotation, winds) is not produced "
                         "on the frozen path (ICD G-10)."),
    "D-TPMC-FROZEN": ("Frozen TPMC response surface abep_sim/data/intake_surface_v1.{csv,json}: grid in the "
                      "metadata (L/d, phi, alpha, theta), species O/N2/O2, scattering maxwell|cll, built at 200 km, "
                      "F10.7 150, orbit-averaged. IntakeSurface raises outside the grid; this script refuses "
                      "out-of-grid inputs before intake.collection() can clamp them. ICD id reused."),
    "D-DRAGCOMP": "compressor.DragCompressor (free-molecular turbo rows + Holweck/Gaede drag stages). ICD id reused.",
    "D-RESERVOIR": ("reservoir.Reservoir (isothermal lumped volume, O/O2/N2, molecular-flow orifice, O wall "
                    "recombination gamma(T) from materials.DB). ICD id reused."),
    "D-DESIGN-TBD": "No design baseline with provenance: the quantity is TBD until the named design inputs are supplied.",
    "D-XE-TBD": "No Xe storage / regulator / valve model in the repository (ICD G-12).",
}


class FeedEnvelopeError(RuntimeError):
    """The chain could not be evaluated as required (never silently degraded)."""


class FrozenAtmosphereRequired(FeedEnvelopeError):
    """atmosphere() did not return the frozen NRLMSIS 2.1 scenario (live MSIS or the approximate table)."""


class MissingDesignInput(ValueError):
    """A required design input is missing from the design-input file."""


class InvalidDesignInput(ValueError):
    """A design input is malformed, unknown, lacks provenance or lies outside the model's domain."""


# ----------------------------------------------------------------------------------------------------------- helpers
def rnd(x):
    """Round to SIG_DIGITS significant digits (floats only); keeps the committed JSON platform-stable."""
    if isinstance(x, bool) or x is None or isinstance(x, (str, int)):
        return x
    if isinstance(x, float):
        if not math.isfinite(x):
            raise FeedEnvelopeError(f"non-finite value {x!r} reached the output")
        return 0.0 if x == 0.0 else float(f"{x:.{SIG_DIGITS}g}")
    if isinstance(x, dict):
        return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v) for v in x]
    return x


def sha256_file(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _ast_class_defaults(rel: str, cls: str) -> dict:
    """Literal defaults of a (dataclass) class body, read from source without importing the module."""
    tree = ast.parse((REPO / rel).read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            out = {}
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
                    try:
                        out[st.target.id] = ast.literal_eval(st.value)
                    except ValueError:
                        pass
            return out
    raise FeedEnvelopeError(f"class {cls} not found in {rel}")


def _ast_function_defaults(rel: str, func: str, cls: str | None = None) -> dict:
    """Literal argument defaults of a module-level function (or of method `func` of class `cls`), from source."""
    tree = ast.parse((REPO / rel).read_text())
    body = tree.body
    if cls is not None:
        body = next((n.body for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls), [])
    for node in body:
        if isinstance(node, ast.FunctionDef) and node.name == func:
            args = node.args.args
            defs = node.args.defaults
            out = {}
            for a, d in zip(args[len(args) - len(defs):], defs):
                try:
                    out[a.arg] = ast.literal_eval(d)
                except ValueError:
                    pass
            return out
    raise FeedEnvelopeError(f"function {func} not found in {rel}")


def _ast_dict_entry(rel: str, name: str, key: str):
    tree = ast.parse((REPO / rel).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)[key]
    raise FeedEnvelopeError(f"{name} not found in {rel}")


def _finite_or_none(x):
    """Diagnostics only: non-finite floats (overflow in an unconverged module state) become None."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _finite_or_none(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_finite_or_none(v) for v in x]
    return x


def mole_fractions(w: dict, M: dict) -> dict:
    """x_s = (w_s / M_s) / sum_k (w_k / M_k)."""
    z = {s: w[s] / M[s] for s in w}
    tot = sum(z.values())
    return {s: z[s] / tot for s in z}


def uncertainty_tbd(basis: str) -> dict:
    return {"kind": "TBD", "basis": basis}


def quantity(value, unit, *, evidence_class, uncertainty, source, validity_domain, in_domain, producer,
             requires=None, requires_design_inputs=None) -> dict:
    q = {"value": value, "unit": unit, "evidence_class": evidence_class, "uncertainty": uncertainty,
         "source": source, "validity_domain": validity_domain, "in_domain": in_domain, "producer": producer}
    if value is None:
        q["evidence_class"] = "TBD"
        q["requires"] = requires or "TBD"
        if requires_design_inputs:
            q["requires_design_inputs"] = list(requires_design_inputs)
    return q


def species_quantity(values: dict, unit, *, evidence_class, uncertainty, source, validity_domain, in_domain,
                     producer) -> dict:
    """Species-resolved quantity with every value numeric (ICD species_quantity shape + producer)."""
    if not values or any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in values.values()):
        raise FeedEnvelopeError(f"species quantity needs numeric values for every species, got {values!r}")
    return {"values": dict(values), "unit": unit, "evidence_class": evidence_class, "uncertainty": uncertainty,
            "source": source, "validity_domain": validity_domain, "in_domain": in_domain, "producer": producer}


def tbd_species(species, unit, **kw) -> dict:
    """Species-resolved TBD quantity: every value null, evidence class TBD, with 'requires'."""
    q = quantity(None, unit, **kw)
    q.pop("value")
    return {"values": {s: None for s in species}, **q}


# ----------------------------------------------------------------------------------------------- frozen atmosphere
def frozen_atmosphere_meta() -> dict:
    meta = json.loads((REPO / "abep_sim/data/atmosphere_msis21_v1.json").read_text())
    full = sha256_file("abep_sim/data/atmosphere_msis21_v1.csv")
    if not full.startswith(meta["sha256_16"]):
        raise FrozenAtmosphereRequired(f"frozen atmosphere CSV sha256 {full[:16]} != metadata sha256_16 {meta['sha256_16']}")
    return meta


def level_mapping() -> dict:
    """low/mean/high -> F10.7 from abep_sim.atmosphere._SOLAR_F107; every level must be a node of the frozen grid."""
    from abep_sim import atmosphere as A
    meta = frozen_atmosphere_meta()
    out = {}
    for lvl in LEVELS:
        f = float(A._SOLAR_F107[lvl])
        if f not in [float(v) for v in meta["f107"]]:
            raise FrozenAtmosphereRequired(f"level {lvl} F10.7 {f} is not a node of the frozen grid {meta['f107']}")
        out[lvl] = f
    return out


def frozen_state(alt_km: float, level: str) -> tuple[dict, dict]:
    """atmosphere() forced onto the frozen dataset; refuses anything else and checks the value is a grid node."""
    from abep_sim import atmosphere as A
    import pandas as pd
    meta = frozen_atmosphere_meta()
    call = {"module": "abep_sim.atmosphere", "function": "atmosphere",
            "inputs": {"alt_km": float(alt_km), "solar": level, "ap": float(meta["ap"]), "date": A.FROZEN_EPOCH,
                       "orbit_average": True, "use_msis": False}}
    if A.FROZEN_EPOCH != meta["epoch"]:
        raise FrozenAtmosphereRequired(f"atmosphere.FROZEN_EPOCH {A.FROZEN_EPOCH} != dataset epoch {meta['epoch']}")
    r = A.atmosphere(float(alt_km), level, ap=float(meta["ap"]), date=A.FROZEN_EPOCH, orbit_average=True,
                     use_msis=False)
    expected = f"NRLMSIS 2.1 frozen scenario {meta['sha256_16']}"
    if r.get("source") != expected:
        raise FrozenAtmosphereRequired(
            f"atmosphere({alt_km}, {level!r}) returned source {r.get('source')!r}, not {expected!r}: the feed envelope "
            "uses only the frozen NRLMSIS dataset (check ABEP_ATMOSPHERE / ABEP_ALLOW_TABLE_ATMOSPHERE and the "
            "atmosphere cache)")
    df = pd.read_csv(REPO / "abep_sim/data/atmosphere_msis21_v1.csv")
    f107 = level_mapping()[level]
    row = df[(df.alt_km == float(alt_km)) & (df.f107 == f107)]
    if len(row) != 1:
        raise FrozenAtmosphereRequired(f"{alt_km} km / F10.7 {f107} is not a node of the frozen dataset")
    row = row.iloc[0]
    for k_out, k_csv in (("rho", "rho"), ("fO", "fO"), ("fN2", "fN2"), ("fO2", "fO2"), ("T", "T")):
        if abs(r[k_out] / float(row[k_csv]) - 1.0) > FROZEN_NODE_RTOL:
            raise FrozenAtmosphereRequired(f"atmosphere() {k_out} at {alt_km} km/{level} differs from the frozen node")
    return r, call


# ------------------------------------------------------------------------------------------------ design inputs
def _surface_meta() -> dict:
    return json.loads((REPO / "abep_sim/data/intake_surface_v1.json").read_text())


def _material_names() -> list[str]:
    from abep_sim.materials import DB
    return sorted(DB)


def _dragcompressor_fields() -> list[str]:
    from abep_sim.compressor import DragCompressor
    return [f.name for f in dataclasses.fields(DragCompressor)]


COMP_SIZED_FIELDS = ("turbo_rows", "n_stages", "rpm")
COMP_INT_FIELDS = ("turbo_rows", "n_stages")
COMP_NONNEG_FIELDS = ("turbo_rows", "n_stages", "leak_conductance_m3_s", "k_bear_W_per_rads", "P_ctrl_W")
COMP_STR_FIELDS = ("rotor_material",)


def design_input_catalog() -> list[dict]:
    """Every design input the chain needs, with its consumer and when it is required. Code defaults and chain
    conventions are listed for transparency with adopted=False: none is a documented design baseline."""
    sm = _surface_meta()
    g = sm["grid"]
    ip = _ast_class_defaults("abep_sim/intake.py", "IntakeParams")
    cp = _ast_class_defaults("abep_sim/intake.py", "CompressorParams")
    dc = _ast_class_defaults("abep_sim/compressor.py", "DragCompressor")
    rv = _ast_class_defaults("abep_sim/reservoir.py", "Reservoir")
    gps = _ast_function_defaults("abep_sim/archengine.py", "gas_path_state")
    sfd = _ast_function_defaults("abep_sim/compressor.py", "size_for", cls="DragCompressor")
    cfg = _ast_class_defaults("abep_sim/system.py", "Config")

    def cd(value, source):
        return {"value": value, "source": source, "evidence_class": "assumed", "adopted": False}

    cat = []

    def add(name, kind, unit, consumer, description, required_when="always", code_defaults=(), domain=None,
            note=None):
        e = {"name": name, "kind": kind, "unit": unit, "consumer": consumer, "description": description,
             "required_when": required_when, "status": "TBD", "documented_baseline": None,
             "code_defaults": list(code_defaults)}
        if domain is not None:
            e["domain"] = domain
        if note:
            e["note"] = note
        cat.append(e)

    add("intake.area_m2", "positive_number", "m^2", "abep_sim.intake.IntakeParams.area_m2 -> abep_sim.intake.collection "
        "(mdot_collected = eta_c x flux_kg_m2_s x area_m2)", "ram capture area of the intake",
        code_defaults=[cd(ip["area_m2"], "abep_sim/intake.py IntakeParams.area_m2 (dataclass default)"),
                       cd(gps["area_m2"], "abep_sim/archengine.py gas_path_state(area_m2=...) (argument default)")])
    add("intake.L_over_d", "grid_number", "-", "IntakeParams.L_over_d -> intake_tpmc.IntakeSurface (frozen TPMC)",
        "honeycomb channel length / diameter", domain=[min(g["L_over_d"]), max(g["L_over_d"])],
        code_defaults=[cd(ip["L_over_d"], "abep_sim/intake.py IntakeParams.L_over_d (dataclass default)"),
                       cd(gps["L_over_d"], "abep_sim/archengine.py gas_path_state(L_over_d=...) (argument default)")])
    add("intake.phi", "grid_number", "-", "IntakeParams.phi -> intake_tpmc.IntakeSurface", "honeycomb open-area fraction",
        domain=[min(g["phi"]), max(g["phi"])],
        code_defaults=[cd(ip["phi"], "abep_sim/intake.py IntakeParams.phi (dataclass default)")])
    add("intake.accommodation", "grid_number", "-", "IntakeParams.accommodation -> intake_tpmc.IntakeSurface (alpha)",
        "gas-surface accommodation (surface state; 0 specular .. 1 diffuse). Physically an uncertain surface property "
        "(epistemic prior in abep_sim/uq_modular.py PRIORS['accommodation']), supplied here as an explicit input",
        domain=[min(g["alpha"]), max(g["alpha"])],
        code_defaults=[cd(ip["accommodation"], "abep_sim/intake.py IntakeParams.accommodation (dataclass default)"),
                       cd(gps["alpha"], "abep_sim/archengine.py gas_path_state(alpha=...) (argument default)")],
        note="intake.collection() clamps accommodation to [0, 1] before the ROM bounds check; this script refuses "
             "values outside the surface grid instead")
    add("intake.off_axis_deg", "grid_number", "deg", "IntakeParams.off_axis_deg -> intake_tpmc.IntakeSurface (theta)",
        "intake pointing error (angle of attack of the ram flow)", domain=[min(g["theta_deg"]), max(g["theta_deg"])],
        code_defaults=[cd(ip["off_axis_deg"], "abep_sim/intake.py IntakeParams.off_axis_deg (dataclass default)")],
        note="intake.collection() silently clamps off_axis_deg to <= 5 deg; this script refuses values outside the "
             "surface grid instead")
    add("intake.scattering", "enum", "-", "IntakeParams.scattering -> intake._tpmc_surface (surface subset)",
        "gas-surface scattering kernel of the frozen surface", domain=list(sm["scattering"]),
        code_defaults=[cd(ip["scattering"], "abep_sim/intake.py IntakeParams.scattering (dataclass default)")])
    add("plenum.T_gas_K", "positive_number", "K", "abep_sim.intake.CompressorParams.T_out_K -> intake.compress "
        "(p_passive_Pa = n x CR_passive x k_B x T)", "gas temperature of the passively compressed plenum",
        code_defaults=[cd(cp["T_out_K"], "abep_sim/intake.py CompressorParams.T_out_K (dataclass default)")],
        note="the frozen TPMC CR_passive was computed with the IntakeGeometry wall temperature, a separate parameter "
             "(ICD G-07); the surface metadata does not record it: verify")
    add("plenum.backflow_frac", "fraction", "-", "CompressorParams.backflow_frac -> intake.compress (mdot_net)",
        "fraction of the collected flow lost to leakage/backflow before the compressor",
        code_defaults=[cd(cp["backflow_frac"], "abep_sim/intake.py CompressorParams.backflow_frac (dataclass default)")])
    add("compressor.mode", "enum", "-", "run_chain(): DragCompressor.run (fixed) or DragCompressor.size_for (size_for)",
        "fixed = the compressor design is given (turbo_rows, n_stages, rpm); size_for = searched as system.evaluate "
        "does, for the valve pressure setpoint", domain=["fixed", "size_for"],
        note="the parametric total compression ratio (intake.CompressorParams.ratio) is not an input of the "
             "gas-path-physics chain mirrored here: system.evaluate overrides its p_out, and the active compression "
             "ratio is a compressor output (CR_active)")
    for f in _dragcompressor_fields():
        kind = ("nonneg_integer" if f in COMP_INT_FIELDS else "material" if f in COMP_STR_FIELDS
                else "nonneg_number" if f in COMP_NONNEG_FIELDS else "positive_number")
        req = "compressor.mode == fixed" if f in COMP_SIZED_FIELDS else "always"
        defaults = [cd(dc[f], f"abep_sim/compressor.py DragCompressor.{f} (dataclass default)")] if f in dc else []
        if f == "rotor_material":
            defaults.append(cd(cfg["rotor_material"], "abep_sim/system.py Config.rotor_material (dataclass default)"))
        add(f"compressor.{f}", kind, "", f"abep_sim.compressor.DragCompressor.{f}", f"DragCompressor field {f}",
            required_when=req, code_defaults=defaults,
            domain=_material_names() if f in COMP_STR_FIELDS else None,
            note=("system.evaluate overrides it with min(0.45, 0.9 x intake area x phi)" if f == "turbo_area_m2" else
                  "system.evaluate overrides it with min(0.45, sqrt(intake area / pi))" if f == "turbo_radius_m" else
                  "output of size_for (must not be supplied in size_for mode)" if f in COMP_SIZED_FIELDS else None))
    for f, desc in (("rpm_max", "upper rpm bound of the size_for search (further capped by the rotor stress limit)"),
                    ("max_turbo_rows", "largest turbo row count searched"),
                    ("max_drag_stages", "largest drag-stage count searched")):
        add(f"compressor.size_for.{f}", "positive_integer" if f != "rpm_max" else "positive_number", "",
            f"abep_sim.compressor.DragCompressor.size_for({f}=...)", desc, required_when="compressor.mode == size_for",
            code_defaults=[cd(sfd[f], f"abep_sim/compressor.py DragCompressor.size_for({f}=...) (argument default)")],
            note="size_for also hard-codes its objective (mass + 0.02 x electrical power) and a 2500 rpm search step")
    add("chamber.volume_m3", "positive_number", "m^3", "abep_sim.reservoir.Reservoir.volume_m3",
        "atmospheric gas chamber (buffer) volume; sets inventory and residence time, not the steady feed state",
        code_defaults=[cd(rv["volume_m3"], "abep_sim/reservoir.py Reservoir.volume_m3 (dataclass default)")])
    add("chamber.wall_area_m2", "positive_number", "m^2", "Reservoir.wall_area_m2", "chamber wall area (O recombination)",
        code_defaults=[cd(rv["wall_area_m2"], "abep_sim/reservoir.py Reservoir.wall_area_m2 (dataclass default)")])
    add("chamber.wall_material", "material", "-", "Reservoir.wall_material -> materials.DB gamma_O(T)",
        "chamber wall material", domain=_material_names(),
        code_defaults=[cd(rv["wall_material"], "abep_sim/reservoir.py Reservoir.wall_material (dataclass default)"),
                       cd(cfg["reservoir_material"], "abep_sim/system.py Config.reservoir_material (dataclass default)")])
    add("chamber.T_K", "positive_number_or_token", "K", "Reservoir.T_K", "chamber gas temperature (= delivered gas "
        f"temperature). Token '{TOKEN_T_FROM_COMPRESSOR}' applies the system.evaluate convention "
        "min(max(T_comp_K, 300), 500)", domain=[TOKEN_T_FROM_COMPRESSOR],
        code_defaults=[cd(rv["T_K"], "abep_sim/reservoir.py Reservoir.T_K (dataclass default)")])
    add("chamber.anode_orifice_K", "positive_number", "-", "Reservoir.anode_orifice_K",
        "Clausing factor of the lumped valve + feed-line + anode-distributor restriction (ICD G-06)",
        code_defaults=[cd(rv["anode_orifice_K"], "abep_sim/reservoir.py Reservoir.anode_orifice_K (dataclass default)")])
    add("chamber.leak_area_m2", "nonneg_number", "m^2", "Reservoir.leak_area_m2", "chamber leak area",
        code_defaults=[cd(rv["leak_area_m2"], "abep_sim/reservoir.py Reservoir.leak_area_m2 (dataclass default)")])
    add("chamber.upstream_collisions", "nonneg_number_or_token", "-", "Reservoir.upstream_collisions",
        f"O wall collisions inside the compressor. Token '{TOKEN_UPSTREAM_COLLISIONS}' applies the system.evaluate "
        "heuristic (no cited source; ICD G-16)", domain=[TOKEN_UPSTREAM_COLLISIONS],
        code_defaults=[cd(rv["upstream_collisions"], "abep_sim/reservoir.py Reservoir.upstream_collisions (dataclass default)")])
    add("chamber.upstream_material", "material", "-", "Reservoir.upstream_material -> materials.DB gamma_O(T)",
        "compressor wall material for upstream O recombination", domain=_material_names(),
        code_defaults=[cd(rv["upstream_material"], "abep_sim/reservoir.py Reservoir.upstream_material (dataclass default)")],
        note="system.evaluate derives it from the rotor material (Ti6Al4V/Al6061 kept, anything else -> Al2O3_anodised)")
    add("valve.mode", "enum", "-", "run_chain(): size_orifice_for_pressure (pressure_setpoint) or a given orifice "
        "area (orifice_area)", "how the valve setting is specified", domain=["pressure_setpoint", "orifice_area"],
        note="compressor.mode == size_for requires valve.mode == pressure_setpoint (the size_for target)")
    add("valve.p_feed_setpoint_Pa", "positive_number", "Pa", "reservoir.size_orifice_for_pressure(p_target_Pa=...)",
        "architecture-neutral feed (chamber) pressure setpoint", required_when="valve.mode == pressure_setpoint",
        note=f"system.evaluate uses Config.p_margin_over_pmin ({cfg['p_margin_over_pmin']}, dataclass default) x the "
             "thruster card p_min, which is architecture-dependent and a card prior (thruster.py); no "
             "architecture-neutral value is documented (see not_adopted)")
    add("valve.anode_orifice_area_m2", "positive_number", "m^2", "Reservoir.anode_orifice_area_m2",
        "open area of the lumped valve / feed restriction (valve setting)", required_when="valve.mode == orifice_area",
        code_defaults=[cd(rv["anode_orifice_area_m2"], "abep_sim/reservoir.py Reservoir.anode_orifice_area_m2 "
                          "(dataclass default)")])
    for e in cat:
        if e["unit"] == "" and e["name"].startswith("compressor."):
            e["unit"] = _COMP_UNITS.get(e["name"].split(".")[-1], "-")
    return cat


_COMP_UNITS = {"turbo_area_m2": "m^2", "turbo_radius_m": "m", "turbo_disc_thickness_m": "m", "rotor_radius_m": "m",
               "rpm": "rpm", "h_mm": "mm", "w_mm": "mm", "L_per_stage_m": "m", "T_gas_K": "K",
               "leak_conductance_m3_s": "m^3 s^-1", "k_bear_W_per_rads": "W s rad^-1", "P_ctrl_W": "W",
               "rotor_disc_thickness_m": "m", "motor_kg_per_Nm": "kg N^-1 m^-1", "bearing_kg": "kg",
               "conductance_to_sink_W_K": "W K^-1", "T_sink_K": "K", "rpm_max": "rpm"}


def required_design_inputs(inputs: dict) -> list[str]:
    """Names required for the given modes (modes themselves are always required)."""
    cmode = _entry_value(inputs, "compressor.mode")
    vmode = _entry_value(inputs, "valve.mode")
    req = []
    for e in design_input_catalog():
        rw = e["required_when"]
        if rw == "always":
            req.append(e["name"])
        elif rw == "compressor.mode == fixed" and cmode == "fixed":
            req.append(e["name"])
        elif rw == "compressor.mode == size_for" and cmode == "size_for":
            req.append(e["name"])
        elif rw == "valve.mode == pressure_setpoint" and vmode == "pressure_setpoint":
            req.append(e["name"])
        elif rw == "valve.mode == orifice_area" and vmode == "orifice_area":
            req.append(e["name"])
    return req


def _entry_value(inputs: dict, name: str):
    e = inputs.get(name)
    return e.get("value") if isinstance(e, dict) else None


def validate_design_inputs(doc: dict) -> dict:
    """Validate a design-input document; return {name: value}. Raises MissingDesignInput / InvalidDesignInput."""
    if not isinstance(doc, dict) or doc.get("format") != DESIGN_INPUTS_FORMAT:
        raise InvalidDesignInput(f"design-input document must have format '{DESIGN_INPUTS_FORMAT}'")
    for k in ("label", "inputs"):
        if k not in doc:
            raise InvalidDesignInput(f"design-input document lacks '{k}'")
    extra = sorted(set(doc) - {"format", "label", "inputs", "notes"})
    if extra:
        raise InvalidDesignInput(f"unknown top-level keys {extra}")
    inputs = doc["inputs"]
    if not isinstance(inputs, dict):
        raise InvalidDesignInput("'inputs' must be an object {name: {value, source, evidence_class}}")
    catalog = {e["name"]: e for e in design_input_catalog()}
    for mode_name in ("compressor.mode", "valve.mode"):
        v = _entry_value(inputs, mode_name)
        if mode_name in inputs and v not in catalog[mode_name]["domain"]:
            raise InvalidDesignInput(f"{mode_name} = {v!r} not in {catalog[mode_name]['domain']}")
    required = required_design_inputs(inputs)
    missing = [n for n in required if n not in inputs]
    if missing:
        raise MissingDesignInput("missing required design inputs (no hidden defaults; supply each with a source and "
                                 "an evidence class): " + ", ".join(missing))
    problems = []
    unknown = sorted(set(inputs) - set(catalog))
    if unknown:
        problems.append(f"unknown design inputs {unknown}")
    not_applicable = sorted(set(inputs) & set(catalog) - set(required))
    if not_applicable:
        problems.append(f"design inputs not used in the selected modes (remove them): {not_applicable}")
    if _entry_value(inputs, "compressor.mode") == "size_for" and _entry_value(inputs, "valve.mode") != "pressure_setpoint":
        problems.append("compressor.mode == size_for requires valve.mode == pressure_setpoint")
    values = {}
    for n in required:
        e = inputs[n]
        if not isinstance(e, dict) or set(e) - {"value", "source", "evidence_class", "note"}:
            problems.append(f"{n}: entry must be {{value, source, evidence_class[, note]}}")
            continue
        for k in ("value", "source", "evidence_class"):
            if k not in e:
                problems.append(f"{n}: lacks '{k}'")
        if not isinstance(e.get("source"), str) or not e.get("source", "").strip():
            problems.append(f"{n}: source must be a non-empty string")
        if e.get("evidence_class") not in EVIDENCE_CLASSES:
            problems.append(f"{n}: evidence_class must be one of {list(EVIDENCE_CLASSES)}")
        v = e.get("value")
        err = _check_kind(catalog[n], v)
        if err:
            problems.append(f"{n}: {err}")
        values[n] = v
    if problems:
        raise InvalidDesignInput("; ".join(problems))
    return values


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _check_kind(entry: dict, v) -> str | None:
    k = entry["kind"]
    if k == "enum" or k == "material":
        return None if v in entry["domain"] else f"{v!r} not in {entry['domain']}"
    if k == "positive_number_or_token" or k == "nonneg_number_or_token":
        if isinstance(v, str):
            return None if v in entry["domain"] else f"token {v!r} not in {entry['domain']}"
        k = k.replace("_or_token", "")
    if not _is_num(v):
        return f"{v!r} is not a finite number"
    if k == "positive_number":
        return None if v > 0 else f"{v} must be > 0"
    if k == "nonneg_number":
        return None if v >= 0 else f"{v} must be >= 0"
    if k == "fraction":
        return None if 0 <= v < 1 else f"{v} must be in [0, 1)"
    if k in ("nonneg_integer", "positive_integer"):
        if float(v) != int(v):
            return f"{v} must be an integer"
        return None if (v >= 0 if k == "nonneg_integer" else v >= 1) else f"{v} out of range"
    if k == "grid_number":
        lo, hi = entry["domain"]
        return None if lo <= v <= hi else f"{v} outside the frozen TPMC surface grid [{lo}, {hi}] (no extrapolation)"
    raise FeedEnvelopeError(f"unknown kind {k}")


# ------------------------------------------------------------------------------------------ design-conditional chain
def run_chain(atm: dict, dv: dict, convention: str) -> dict:
    """Evaluate the gas path for one free-stream state with explicit design inputs `dv`.

    Mirrors the gas-path branch of abep_sim/system.py:evaluate (gaspath_physics=True) and hence
    archengine.gas_path_state, with three deliberate differences: (1) every design input is explicit (no dataclass or
    card default); (2) the chamber pressure target is an architecture-neutral valve setpoint, not a thruster card p_min;
    (3) conditions system.evaluate passes silently (setpoint above the compressor outlet, orifice bracket hit,
    unconverged balances) give INFEASIBLE / MODEL_ERROR here.

    convention: 'chain_freestream_split' (system.evaluate: collected flow split by free-stream mass fractions) or
                'species_resolved_surface' (per-species eta_c of the same frozen surface; ICD G-02).
    """
    from abep_sim.intake import IntakeParams, CompressorParams, collection, compress, _tpmc_surface
    from abep_sim.compressor import DragCompressor
    from abep_sim.reservoir import Reservoir, size_orifice_for_pressure
    from abep_sim.constants import M_SPECIES

    detail: dict = {"convention": convention}
    ip = IntakeParams(area_m2=float(dv["intake.area_m2"]), accommodation=float(dv["intake.accommodation"]),
                      off_axis_deg=float(dv["intake.off_axis_deg"]), scattering=dv["intake.scattering"],
                      L_over_d=float(dv["intake.L_over_d"]), phi=float(dv["intake.phi"]), use_tpmc=True)
    col = collection(ip, atm)
    cp = CompressorParams(T_out_K=float(dv["plenum.T_gas_K"]), backflow_frac=float(dv["plenum.backflow_frac"]))
    cmp_ = compress(cp, atm, col["mdot_collected"], col["eta_c"], col["passive_override"])
    mdot_net = cmp_["mdot_net"]
    p_passive = cmp_["p_passive_Pa"]
    w_fs = {"O": atm["fO"], "N2": atm["fN2"], "O2": atm["fO2"]}
    if convention == "chain_freestream_split":
        md_in = {s: mdot_net * w_fs[s] for s in AIR_SPECIES}
    elif convention == "species_resolved_surface":
        surf = _tpmc_surface(atm, ip.scattering)
        tot = sum(w_fs.values())
        eta_s = {s: float(surf.f[s]["eta_c"](ip.L_over_d, ip.phi, ip.accommodation, ip.off_axis_deg)) for s in AIR_SPECIES}
        md_in = {s: eta_s[s] * (w_fs[s] / tot) * atm["flux_kg_m2_s"] * ip.area_m2 * (1.0 - cp.backflow_frac)
                 for s in AIR_SPECIES}
        detail["eta_c_s"] = eta_s
        if abs(sum(md_in.values()) / mdot_net - 1.0) > 1e-9:
            raise FeedEnvelopeError("species-resolved collection does not reproduce the mass-weighted total")
    else:
        raise FeedEnvelopeError(f"unknown convention {convention}")
    detail.update({"eta_c": col["eta_c"], "CR_passive": col["passive_override"], "mdot_collected_kgps": col["mdot_collected"],
                   "mdot_to_compressor_kgps": mdot_net, "p_plenum_Pa": p_passive,
                   "w_s_to_compressor": {s: md_in[s] / sum(md_in.values()) for s in AIR_SPECIES}})

    comp_kw = {}
    for f in _dragcompressor_fields():
        if dv.get("compressor.mode") == "size_for" and f in COMP_SIZED_FIELDS:
            continue
        v = dv[f"compressor.{f}"]
        comp_kw[f] = int(v) if f in COMP_INT_FIELDS else v
    comp = DragCompressor(**comp_kw)
    if dv["compressor.mode"] == "fixed":
        cres = comp.run(p_passive, md_in)
        cres.update({"turbo_rows": comp.turbo_rows, "n_stages": comp.n_stages, "rpm": comp.rpm, "sized": None})
    else:
        p_set = float(dv["valve.p_feed_setpoint_Pa"])
        cres = comp.size_for(p_passive, md_in, CR_target=max(p_set / max(p_passive, 1e-9), 1.0),
                             rpm_max=float(dv["compressor.size_for.rpm_max"]),
                             max_turbo_rows=int(dv["compressor.size_for.max_turbo_rows"]),
                             max_drag_stages=int(dv["compressor.size_for.max_drag_stages"]))
    # fixed-point residual of the leak recirculation (DragCompressor.run reports no convergence; ICD G-03)
    through = {s: md_in[s] + cres["recirculated_kgps"][s] for s in md_in}
    again = comp._run_once(p_passive, through)
    recirc_resid = max(abs(max(again["leak_kgps"][s], 0.0) - cres["recirculated_kgps"][s]) / max(md_in[s], 1e-15)
                       for s in md_in)
    detail["compressor"] = {"mode": dv["compressor.mode"], "turbo_rows": cres["turbo_rows"], "n_stages": cres["n_stages"],
                            "rpm": float(cres["rpm"]), "sized": cres["sized"], "rotor_ok": bool(cres["rotor_ok"]),
                            "p_out_Pa": cres["p_out_Pa"], "CR_active": cres["CR_active"],
                            "CR_by_species": dict(cres["CR_by_species"]), "T_comp_K": cres["T_comp_K"],
                            "P_el_W": cres["P_el_W"], "recirculation_fixed_point_residual": recirc_resid}

    T_K = dv["chamber.T_K"]
    if T_K == TOKEN_T_FROM_COMPRESSOR:
        T_K = min(max(cres["T_comp_K"], 300.0), 500.0)
    ucoll = dv["chamber.upstream_collisions"]
    if ucoll == TOKEN_UPSTREAM_COLLISIONS:
        ucoll = 10.0 * cres["turbo_rows"] + 50.0 * cres["n_stages"]
    orifice = (float(dv["valve.anode_orifice_area_m2"]) if dv["valve.mode"] == "orifice_area" else float("nan"))
    res = Reservoir(volume_m3=float(dv["chamber.volume_m3"]), wall_area_m2=float(dv["chamber.wall_area_m2"]),
                    wall_material=dv["chamber.wall_material"], T_K=float(T_K), anode_orifice_area_m2=orifice,
                    anode_orifice_K=float(dv["chamber.anode_orifice_K"]), leak_area_m2=float(dv["chamber.leak_area_m2"]),
                    upstream_collisions=float(ucoll), upstream_material=dv["chamber.upstream_material"])
    delivered = cres["delivered_kgps"]
    model_errors: list[str] = []      # numerical non-convergence: the state is not a model answer at all
    infeasible: list[str] = []        # converged, but the design cannot deliver the requested state
    if not all(math.isfinite(v) for v in (cres["p_out_Pa"], cres["T_comp_K"], recirc_resid)):
        model_errors.append("non-finite compressor state (overflow in DragCompressor.run)")
        recirc_resid = None
        detail["compressor"]["recirculation_fixed_point_residual"] = None
    elif recirc_resid > COMP_RECIRC_RTOL:
        model_errors.append("compressor leak recirculation not converged (fixed-point residual above the module's "
                            "own tolerance)")
    if cres["sized"] is False:
        infeasible.append("DragCompressor.size_for found no design reaching the setpoint")
    if not cres["rotor_ok"]:
        infeasible.append("rotor tip speed above the material stress limit (rotor_ok False)")
    bracket_hit = None
    p_resid = None
    if dv["valve.mode"] == "pressure_setpoint" and not model_errors:
        p_set = float(dv["valve.p_feed_setpoint_Pa"])
        if p_set > cres["p_out_Pa"]:
            infeasible.append("valve setpoint above the compressor outlet pressure (system.evaluate would silently "
                              "cap the target at p_out)")
        else:
            area = size_orifice_for_pressure(res, delivered, p_set)
            lo, hi = ORIFICE_BRACKET_M2
            bracket_hit = bool(abs(area / hi - 1.0) < 1e-6 or abs(area / lo - 1.0) < 1e-6)
            if bracket_hit:
                model_errors.append("size_orifice_for_pressure ended on its bracket (setpoint not reachable inside "
                                    "[1e-8, 3e-2] m^2; ICD G-05)")
    rs = None if (model_errors and not bracket_hit) or math.isnan(res.anode_orifice_area_m2) else res.steady_state(delivered)
    chamber = None
    if rs is not None:
        if dv["valve.mode"] == "pressure_setpoint":
            p_resid = rs["p_total_Pa"] / float(dv["valve.p_feed_setpoint_Pa"]) - 1.0
        elif rs["p_total_Pa"] > cres["p_out_Pa"]:
            infeasible.append("chamber pressure set by the valve orifice exceeds the compressor outlet pressure")
        m_in = sum(delivered.values())
        m_out = sum(rs["mdot_anode"].values()) + sum(rs["mdot_leak"].values())
        bal = abs(m_out / m_in - 1.0)
        if bal > RES_BALANCE_RTOL:
            model_errors.append("chamber mass balance not closed (Reservoir.steady_state reports no convergence; "
                                "ICD G-04)")
        chamber = {"T_K": rs["T_K"], "p_total_Pa": rs["p_total_Pa"], "anode_orifice_area_m2": res.anode_orifice_area_m2,
                   "upstream_collisions": float(ucoll), "gamma_wall": rs["gamma_wall"], "gamma_upstream": rs["gamma_upstream"],
                   "O_survival": rs["O_survival"], "residence_time_s": rs["residence_time_s"],
                   "x_s_chamber": {s: rs["n_species"][s] / sum(rs["n_species"].values()) for s in AIR_SPECIES},
                   "mdot_leak_kgps": sum(rs["mdot_leak"].values()), "mass_balance_residual": bal,
                   "orifice_bracket_hit": bracket_hit, "setpoint_relative_residual": p_resid}
    detail["chamber"] = chamber
    status = ST_MODEL_ERROR if model_errors else ST_INFEASIBLE if infeasible else ST_OK
    reasons = model_errors + infeasible
    detail["status"] = status
    detail["reasons"] = reasons
    if status == ST_OK:
        mdot_s = {s: rs["mdot_anode"][s] for s in AIR_SPECIES}
        tot = sum(mdot_s.values())
        w = {s: mdot_s[s] / tot for s in AIR_SPECIES}
        detail["feed"] = {"mdot_s_kgps": mdot_s, "mdot_total_kgps": tot, "p_feed_Pa": rs["p_total_Pa"],
                          "T_gas_K": rs["T_K"], "w_s": w, "x_s": mole_fractions(w, M_SPECIES),
                          "A_eff_m2": tot / atm["flux_kg_m2_s"]}
    else:
        detail["feed"] = None
    return detail


# ------------------------------------------------------------------------------------------------- case assembly
def _fs_unc() -> dict:
    return uncertainty_tbd("abep_sim.atmosphere.atmosphere exposes no uncertainty; the frozen NRLMSIS 2.1 scenario "
                           "carries no error model. TBD - requires a published NRLMSIS 2.1 density/composition/"
                           "temperature error characterisation at 180-230 km. The spread over solar levels is a "
                           "scenario set (envelope_ranges), not an uncertainty")


FEED_DEPS = {
    "mdot_total_kgps": ["intake.*", "plenum.backflow_frac", "compressor.*", "chamber.*", "valve.*"],
    "mdot_s_kgps": ["intake.*", "plenum.backflow_frac", "compressor.*", "chamber.*", "valve.*"],
    "p_feed_Pa": ["intake.*", "plenum.*", "compressor.*", "chamber.*", "valve.*"],
    "T_gas_K": ["chamber.T_K", "compressor.* (when chamber.T_K is the system.evaluate token)"],
    "w_s": ["intake.*", "plenum.backflow_frac", "compressor.*", "chamber.*", "valve.*"],
    "x_s": ["intake.*", "plenum.backflow_frac", "compressor.*", "chamber.*", "valve.*"],
    "A_eff_m2": ["intake.*", "plenum.backflow_frac", "chamber.*", "valve.*"],
}
FEED_DEP_REASON = {
    "mdot_total_kgps": "the delivered flow is eta_c(L/d, phi, alpha, theta) x mass flux x intake area x (1 - backflow) "
                       "minus the chamber leak; a design must also be feasible (compressor, valve)",
    "mdot_s_kgps": "species split additionally depends on species-selective collection (ICD G-02) and O wall "
                   "recombination in compressor and chamber (materials, collisions, temperature)",
    "p_feed_Pa": "set by the valve setting (setpoint or orifice area) and bounded by the compressor outlet",
    "T_gas_K": "no energy balance propagates gas temperature (ICD G-07): the chamber temperature is a design input or "
               "the system.evaluate compressor-temperature convention",
    "w_s": "species-selective collection and O recombination (O -> O2) change the composition",
    "x_s": "derived from w_s (flow basis)",
    "A_eff_m2": "effective capture area eta_c x area x (1 - backflow) x anode share",
}
FEED_UNITS = {"mdot_total_kgps": "kg s^-1", "mdot_s_kgps": "kg s^-1", "p_feed_Pa": "Pa", "T_gas_K": "K", "w_s": "-",
              "x_s": "-", "A_eff_m2": "m^2"}
FEED_PRODUCERS = {
    "mdot_total_kgps": {"call": "chain", "module": "abep_sim.reservoir", "function": "Reservoir.steady_state",
                        "output_key": "mdot_anode", "derivation": "sum over species of mdot_anode"},
    "mdot_s_kgps": {"call": "chain", "module": "abep_sim.reservoir", "function": "Reservoir.steady_state",
                    "output_key": "mdot_anode"},
    "p_feed_Pa": {"call": "chain", "module": "abep_sim.reservoir", "function": "Reservoir.steady_state",
                  "output_key": "p_total_Pa"},
    "T_gas_K": {"call": "chain", "module": "abep_sim.reservoir", "function": "Reservoir.steady_state", "output_key": "T_K"},
    "w_s": {"call": "chain", "module": "abep_sim.reservoir", "function": "Reservoir.steady_state",
            "output_key": "mdot_anode", "derivation": "w_s = mdot_anode_s / sum_k mdot_anode_k"},
    "x_s": {"call": "chain", "module": "abep_sim.constants", "function": "M_SPECIES",
            "derivation": "x_s = (w_s / M_s) / sum_k (w_k / M_k) (flow basis)"},
    "A_eff_m2": {"call": "chain", "derivation": "A_eff = mdot_total_kgps / free_stream.mass_flux_kgpm2ps"},
}


def _feed_tbd(name: str) -> dict:
    kw = dict(evidence_class="TBD",
              uncertainty=uncertainty_tbd("not evaluated: design inputs missing"),
              source=f"{SCRIPT_REL}:run_chain (not run: no documented design baseline)",
              validity_domain="D-DESIGN-TBD", in_domain=None, producer=FEED_PRODUCERS[name],
              requires=f"TBD - requires the design inputs {', '.join(FEED_DEPS[name])} with provenance: "
                       f"{FEED_DEP_REASON[name]}",
              requires_design_inputs=FEED_DEPS[name])
    if name in ("mdot_s_kgps", "w_s", "x_s"):
        return tbd_species(AIR_SPECIES, FEED_UNITS[name], **kw)
    return quantity(None, FEED_UNITS[name], **kw)


def _feed_null(name: str, status: str, reasons: list[str]) -> dict:
    kw = dict(evidence_class="TBD",
              uncertainty=uncertainty_tbd(f"not evaluated: case status {status}"),
              source=f"{SCRIPT_REL}:run_chain", validity_domain="D-DESIGN-TBD", in_domain=False,
              producer=FEED_PRODUCERS[name],
              requires=f"TBD - requires a feasible, converged design ({'; '.join(reasons)})")
    if name in ("mdot_s_kgps", "w_s", "x_s"):
        return tbd_species(AIR_SPECIES, FEED_UNITS[name], **kw)
    return quantity(None, FEED_UNITS[name], **kw)


def _feed_value(name: str, primary: dict, alt: dict | None, design_label: str) -> dict:
    v = primary["feed"][name]
    alt_v = alt["feed"][name] if alt and alt.get("feed") else None
    scen = [{"convention": "chain_freestream_split", "value": v},
            {"convention": "species_resolved_surface", "value": alt_v,
             "status": alt["status"] if alt else "not_run"}]
    unc = {"kind": "scenario_set", "scenarios": scen,
           "basis": "structural: collected-flow composition convention (ICD G-02). Not propagated: accommodation "
                    "prior (uq_modular.PRIORS['accommodation']), TPMC sampling error, NRLMSIS error (none exposed)"}
    kw = dict(evidence_class="model-derived", uncertainty=unc,
              source=f"{SCRIPT_REL}:run_chain with design inputs '{design_label}' (evidence classes in design_inputs)",
              validity_domain="D-RESERVOIR", in_domain=True, producer=FEED_PRODUCERS[name])
    if isinstance(v, dict):
        return species_quantity(v, FEED_UNITS[name], **kw)
    return quantity(v, FEED_UNITS[name], **kw)


def build_case(alt_km: float, level: str, dv: dict | None, design_label: str | None) -> dict:
    from abep_sim.constants import M_SPECIES
    atm, call = frozen_state(alt_km, level)
    lm = level_mapping()
    meta = frozen_atmosphere_meta()
    case_id = f"alt{int(alt_km)}_{level}_orbit_averaged"
    src = f"frozen NRLMSIS 2.1 scenario {meta['sha256_16']} via abep_sim.atmosphere.atmosphere"
    unc = _fs_unc()

    def fq(key, unit, out_key, domain="D-ATM-FROZEN", derivation=None, value=None):
        prod = {"call": "atmosphere", "module": "abep_sim.atmosphere", "function": "atmosphere"}
        if out_key:
            prod["output_key"] = out_key
        if derivation:
            prod["derivation"] = derivation
        return quantity(atm[out_key] if value is None else value, unit, evidence_class="model-derived",
                        uncertainty=unc if key != "V_mps" else uncertainty_tbd(
                            "deterministic circular-orbit speed; the relative speed (co-rotation, winds) that the "
                            "intake sees is not produced on the frozen path (ICD G-10). TBD - requires a relative-"
                            "velocity producer"),
                        source=src if key != "V_mps" else "abep_sim.atmosphere.orbital_velocity (constants.py MU_EARTH, R_EARTH)",
                        validity_domain=domain, in_domain=True, producer=prod)

    w = {"O": atm["fO"], "N2": atm["fN2"], "O2": atm["fO2"]}
    x = mole_fractions(w, M_SPECIES)
    closure_w = sum(w.values()) - 1.0
    if abs(closure_w) > MASS_FRACTION_CLOSURE_TOL:
        raise FeedEnvelopeError(f"{case_id}: free-stream mass fractions do not close ({closure_w:+.3e})")
    sp_prod = {"call": "atmosphere", "module": "abep_sim.atmosphere", "function": "atmosphere",
               "output_key": "fO, fN2, fO2"}
    free_stream = {
        "rho_kgpm3": fq("rho_kgpm3", "kg m^-3", "rho"),
        "n_total_m3": fq("n_total_m3", "m^-3", "n"),
        "T_ambient_K": fq("T_ambient_K", "K", "T"),
        "V_mps": fq("V_mps", "m s^-1", "V", domain="D-ORBIT-CIRCULAR"),
        "mass_flux_kgpm2ps": fq("mass_flux_kgpm2ps", "kg m^-2 s^-1", "flux_kg_m2_s"),
        "p_ambient_Pa": fq("p_ambient_Pa", "Pa", "p_ambient_Pa"),
        "m_mean_kg": fq("m_mean_kg", "kg", "m_mean"),
        "w_s": species_quantity(w, "-", evidence_class="model-derived", uncertainty=unc, source=src,
                                validity_domain="D-ATM-FROZEN", in_domain=True, producer=sp_prod),
        "x_s": species_quantity(x, "-", evidence_class="model-derived", uncertainty=unc, source=src,
                                validity_domain="D-ATM-FROZEN", in_domain=True,
                                producer={"call": "atmosphere", "module": "abep_sim.constants", "function": "M_SPECIES",
                                          "derivation": "x_s = (w_s / M_s) / sum_k (w_k / M_k)"}),
        "species_mass_flux_kgpm2ps": species_quantity(
            {s: w[s] * atm["flux_kg_m2_s"] for s in AIR_SPECIES}, "kg m^-2 s^-1", evidence_class="model-derived",
            uncertainty=unc, source=src, validity_domain="D-ATM-FROZEN", in_domain=True,
            producer={"call": "atmosphere", "module": "abep_sim.atmosphere", "function": "atmosphere",
                      "output_key": "flux_kg_m2_s, fO, fN2, fO2", "derivation": "w_s x flux_kg_m2_s"}),
        "atmosphere_source": {"value": atm["source"], "unit": "-", "source": "abep_sim.atmosphere.atmosphere -> source"},
        "atmosphere_in_domain": {"value": True, "unit": "-", "source": f"{SCRIPT_REL}:frozen_state",
                                 "reason": "frozen grid node (altitude and F10.7 are nodes; value equals the CSV row "
                                           f"within {FROZEN_NODE_RTOL:g} relative, i.e. no interpolation)"},
    }
    # sums rounded to 12 decimals: sub-1e-12 floating-point noise is not a closure defect and must not make the
    # committed JSON platform-dependent
    closures = {"free_stream_w_s_sum": round(sum(w.values()), 12), "free_stream_x_s_sum": round(sum(x.values()), 12)}

    calls = {"atmosphere": call}
    chain_detail = None
    if dv is None:
        status = ST_MISSING
        feed = {k: _feed_tbd(k) for k in ("mdot_total_kgps", "mdot_s_kgps", "p_feed_Pa", "T_gas_K", "w_s", "x_s")}
        a_eff = _feed_tbd("A_eff_m2")
        reasons = ["no documented design baseline with provenance (see design_input_contract and not_adopted)"]
    else:
        primary = run_chain(atm, dv, "chain_freestream_split")
        alt = run_chain(atm, dv, "species_resolved_surface")
        calls["chain"] = {"module": SCRIPT_REL, "function": "run_chain",
                          "inputs": {"design_inputs": design_label, "conventions": ["chain_freestream_split",
                                                                                    "species_resolved_surface"]}}
        status = primary["status"]
        reasons = primary["reasons"]
        chain_detail = _finite_or_none({"chain_freestream_split": primary, "species_resolved_surface": alt})
        if status == ST_OK:
            feed = {k: _feed_value(k, primary, alt, design_label)
                    for k in ("mdot_total_kgps", "mdot_s_kgps", "p_feed_Pa", "T_gas_K", "w_s", "x_s")}
            a_eff = _feed_value("A_eff_m2", primary, alt, design_label)
            closures["feed_w_s_sum"] = round(sum(primary["feed"]["w_s"].values()), 12)
            closures["feed_x_s_sum"] = round(sum(primary["feed"]["x_s"].values()), 12)
        else:
            feed = {k: _feed_null(k, status, reasons)
                    for k in ("mdot_total_kgps", "mdot_s_kgps", "p_feed_Pa", "T_gas_K", "w_s", "x_s")}
            a_eff = _feed_null("A_eff_m2", status, reasons)
    return {
        "case_id": case_id, "alt_km": float(alt_km), "atmosphere_level": level, "averaging": "orbit_averaged",
        "f107": lm[level], "f107a": lm[level], "ap": float(meta["ap"]), "status": status, "status_reasons": reasons,
        "architecture_dependent": False, "calls": calls, "free_stream": free_stream, "feed_state": feed,
        "feed_scaling": {
            "relation": "mdot_total_kgps = A_eff_m2 x free_stream.mass_flux_kgpm2ps (steady state; the compressor "
                        "returns all captured gas, so only intake collection, plenum backflow and the chamber leak "
                        "enter A_eff)",
            "A_eff_m2": a_eff},
        "closures": closures, "chain_detail": chain_detail,
    }


# --------------------------------------------------------------------------------------------------- envelope ranges
RANGE_SCALARS = ("rho_kgpm3", "n_total_m3", "T_ambient_K", "V_mps", "mass_flux_kgpm2ps", "p_ambient_Pa", "m_mean_kg")
RANGE_SPECIES = ("w_s", "x_s", "species_mass_flux_kgpm2ps")


def _range_entry(pairs: list[tuple[str, float]], unit: str) -> dict:
    vals = [v for _, v in pairs]
    lo = min(pairs, key=lambda p: p[1])
    hi = max(pairs, key=lambda p: p[1])
    return {"unit": unit, "min": lo[1], "max": hi[1], "min_at": lo[0], "max_at": hi[0],
            "max_over_min": (hi[1] / lo[1]) if lo[1] > 0 else None, "n": len(vals)}


def envelope_ranges(cases: list[dict]) -> dict:
    def collect(block, getter, unit, scope_cases, label_of):
        return _range_entry([(label_of(c), getter(c)) for c in scope_cases], unit)

    out = {"kind": "scenario_set",
           "basis": "min / max over the frozen solar-activity levels (by_altitude) and over altitudes and levels "
                    "(overall). A scenario envelope of the orbit-averaged frozen states, not an uncertainty interval",
           "free_stream": {}, "feed_state": None}
    for key in RANGE_SCALARS + RANGE_SPECIES:
        species = key in RANGE_SPECIES
        keys = [(key, s) for s in AIR_SPECIES] if species else [(key, None)]
        for k, s in keys:
            name = f"{k}.{s}" if s else k
            unit = cases[0]["free_stream"][k]["unit"]
            get = (lambda c, k=k, s=s: c["free_stream"][k]["values"][s]) if s else (
                lambda c, k=k: c["free_stream"][k]["value"])
            by_alt = {}
            for alt in sorted({c["alt_km"] for c in cases}):
                sc = [c for c in cases if c["alt_km"] == alt]
                by_alt[str(int(alt))] = collect(None, get, unit, sc, lambda c: c["atmosphere_level"])
            out["free_stream"][name] = {"overall": collect(None, get, unit, cases, lambda c: c["case_id"]),
                                        "by_altitude": by_alt}
    ok = [c for c in cases if c["status"] == ST_OK]
    if not ok and all(c["status"] == ST_MISSING for c in cases):
        out["feed_state"] = {"status": "TBD", "requires": "TBD - requires evaluated feed states (design inputs with "
                             "provenance; no documented design baseline exists in the repository)"}
    elif not ok:
        out["feed_state"] = {"status": "TBD", "requires": "TBD - requires at least one feasible, converged case: the "
                             "supplied design inputs give INFEASIBLE / MODEL_ERROR in every case (see status_reasons)"}
    else:
        fs = {}
        for key in ("mdot_total_kgps", "p_feed_Pa", "T_gas_K"):
            fs[key] = {"overall": _range_entry([(c["case_id"], c["feed_state"][key]["value"]) for c in ok],
                                               FEED_UNITS[key])}
        for key in ("w_s", "x_s"):
            for s in AIR_SPECIES:
                fs[f"{key}.{s}"] = {"overall": _range_entry([(c["case_id"], c["feed_state"][key]["values"][s])
                                                             for c in ok], "-")}
        out["feed_state"] = {"status": "evaluated", "n_ok_cases": len(ok), "n_cases": len(cases), "ranges": fs}
    return out


# ------------------------------------------------------------------------------------------------------ static blocks
def milestones() -> dict:
    return {
        "supports": ["A"],
        "statement": ("Supports milestone A (conditional selection): it fixes ONE architecture-independent feed "
                      "definition at the thruster boundary (IF-A5 / IF-X2) and the orbit-averaged free-stream "
                      "envelope over 180/200/230 km x low/mean/high from the frozen NRLMSIS 2.1 dataset, so that "
                      "'architecture X is baseline provided ...' conditions can be written against identical feed "
                      "conditions and the named design inputs. It does not need Physics Baseline 1.0 and contains no "
                      "Hall prediction."),
        "to_reach_B": [
            "a documented Vyovrinda design baseline with provenance for every design input in design_input_contract, "
            "so the valve-outlet feed state (mdot, p, T, x_s) is evaluated instead of TBD",
            "upstream convergence reporting in the modules (ICD G-03, G-04, G-05); this script only checks residuals "
            "from outside",
            "a decision on the collected-flow composition convention (ICD G-02) and on gas-temperature propagation "
            "(ICD G-07)",
            "an NRLMSIS 2.1 error characterisation (no uncertainty is exposed today) and orbit-resolved extremes from "
            "a frozen orbit-resolved dataset (rebuild under CLAUDE.md rule 1)",
            "on the Hall side (other track): an admitted Hall transport closure; the feed state here is what its "
            "design Hall maps would be queried with",
        ],
        "to_reach_C": [
            "a Xe storage / regulator / valve model and a Xe flow-setpoint policy (ICD G-12)",
            "feed dynamics for start-up and throttling (ICD G-09), filter model (ICD G-01), contamination transport "
            "(ICD G-11)",
            "integration of the chain's mass, power and heat (compressor heat split ICD G-17) into the PDR budgets",
        ],
    }


def not_adopted() -> list[dict]:
    return [
        {"quantity": "intake.area_m2", "value": 0.7, "unit": "m^2", "file": "docs/HISTORY.md",
         "evidence_token": "with **0.7 m²** it holds all 26,000 h", "evidence_class": "model-derived",
         "reason": "v0.2 mission-transient finding (transient.py with the thruster-card model; drag against the 25 mN "
                   "cap), later the reference design '0.7 m² / 20 cm / 275 V' of Phases 4-6, whose Hall performance "
                   "comes from the 0-D Hall model now marked superseded (CLAUDE.md: plasma_devices.py '0-D Hall - "
                   "superseded'; 'Superseded / withdrawn'); a study result, not a design baseline with provenance"},
        {"quantity": "valve.p_feed_setpoint_Pa", "value": 0.05, "unit": "Pa", "file": "docs/HISTORY.md",
         "evidence_token": "reference gas state (200 km, 0.7 m², CFRP turbo, 0.05 Pa, 0.98 mg/s",
         "evidence_class": "model-derived",
         "reason": "v1.0 'reference gas state' of the architecture trade; HISTORY records no derivation or source "
                   "for it as a design input. On the chain a chamber target comes from a thruster-card minimum "
                   "pressure x margin (system.evaluate, archengine.make_gas_fn), which is architecture-dependent and a "
                   "card prior (thruster.py), not an architecture-neutral feed setpoint"},
        {"quantity": "feed_state.mdot_total_kgps", "value": 9.8e-07, "unit": "kg s^-1", "file": "docs/HISTORY.md",
         "evidence_token": "reference gas state (200 km, 0.7 m², CFRP turbo, 0.05 Pa, 0.98 mg/s",
         "evidence_class": "model-derived",
         "reason": "output of the historical chain at the non-adopted inputs above (0.98 mg/s as printed); not "
                   "reproduced here and not a feed-envelope value"},
        {"quantity": "all design inputs", "value": None, "unit": "-", "file": "abep_sim/*.py",
         "evidence_token": None, "evidence_class": "assumed",
         "reason": "dataclass / argument defaults of IntakeParams, CompressorParams, DragCompressor, Reservoir, "
                   "system.Config and archengine.gas_path_state carry no cited source (listed per input under "
                   "design_input_contract[*].code_defaults with adopted=false); two different defaults exist for "
                   "the intake area, L/d and accommodation, so none is a single documented baseline"},
    ]


def chain_findings() -> list[dict]:
    return [
        {"id": "FE-01", "icd_gap": None, "where": "abep_sim/intake.py:collection",
         "finding": "off_axis_deg is clamped to <= 5 deg and accommodation to [0, 1] before the frozen-surface bounds "
                    "check, so an out-of-grid pointing error is silently evaluated at 5 deg",
         "handling": "build_feed_envelope refuses out-of-grid intake inputs (InvalidDesignInput)"},
        {"id": "FE-02", "icd_gap": None, "where": "abep_sim/system.py:evaluate",
         "finding": "the chamber-pressure target is capped at the compressor outlet, min(p_target, p_out), without a "
                    "flag",
         "handling": "a setpoint above the compressor outlet gives status INFEASIBLE with null feed values"},
        {"id": "FE-03", "icd_gap": "G-05", "where": "abep_sim/reservoir.py:size_orifice_for_pressure",
         "finding": "returns the bracket end [1e-8, 3e-2] m^2 without a flag when the setpoint is unreachable",
         "handling": "bracket hit is detected and reported; status MODEL_ERROR"},
        {"id": "FE-04", "icd_gap": "G-03, G-04", "where": "abep_sim/compressor.py:DragCompressor.run; "
                                                          "abep_sim/reservoir.py:Reservoir.steady_state",
         "finding": "no convergence flags",
         "handling": "the script recomputes the recirculation fixed-point residual and the chamber mass-balance "
                     "residual against each module's own stopping tolerance; failure gives MODEL_ERROR"},
        {"id": "FE-05", "icd_gap": "G-02", "where": "abep_sim/system.py:evaluate (md_in)",
         "finding": "the collected flow is split by free-stream mass fractions although the frozen surface is "
                    "species-resolved",
         "handling": "both conventions are evaluated; the chain convention is primary, the species-resolved one is "
                     "carried as a scenario in every feed-state uncertainty"},
        {"id": "FE-06", "icd_gap": None, "where": "abep_sim/atmosphere.py:atmosphere (_MSIS_CACHE)",
         "finding": "the cache key omits the ABEP_ALLOW_TABLE_ATMOSPHERE environment switch (ABEP_ATMOSPHERE enters "
                    "only through the resolved use_msis flag), so a table-fallback state cached with the switch set is "
                    "returned later without it, and vice versa (CLAUDE.md rule 5: caches must be pure functions of "
                    "their keys)",
         "handling": "every call's returned `source` is checked against the frozen dataset hash and the value against "
                     "the CSV grid node; anything else raises FrozenAtmosphereRequired"},
        {"id": "FE-07", "icd_gap": "G-07", "where": "abep_sim/intake.py:compress; abep_sim/intake_tpmc.py",
         "finding": "two unrelated temperatures: plenum T_out_K for p_passive and the TPMC wall temperature of the "
                    "frozen surface build for CR_passive (not recorded in the surface metadata: verify)",
         "handling": "plenum.T_gas_K is an explicit design input; the inconsistency is listed, not resolved"},
        {"id": "FE-08", "icd_gap": None, "where": "abep_sim/intake.py:_tpmc_surface (docstring)",
         "finding": "the frozen TPMC surface was built at 200 km / F10.7 150 only; the docstring says eta_c, C_D and "
                    "K_back depend on the speed ratio through sqrt(T/m), 'which varies < 10 % across 180-230 km and "
                    "the solar cycle' (no cited source). The frozen free-stream states of this envelope give a larger "
                    "spread of sqrt(T/m_mean) relative to the build point (exposed_uncertainty, computed here)",
         "handling": "recorded under exposed_uncertainty with the computed spread; the effect on eta_c is not "
                     "quantified or propagated (TBD - requires TPMC surfaces at the other atmospheric states)"},
    ]


def _speed_ratio_spread(cases: list[dict]) -> dict:
    """sqrt(T / m_mean) of every case relative to the TPMC build point (200 km, F10.7 150 = the 'mean' level)."""
    ref, _ = frozen_state(200.0, "mean")
    r0 = math.sqrt(ref["T"] / ref["m_mean"])
    rel = {c["case_id"]: math.sqrt(c["free_stream"]["T_ambient_K"]["value"] / c["free_stream"]["m_mean_kg"]["value"]) / r0
           for c in cases}
    lo = min(rel, key=rel.get)
    hi = max(rel, key=rel.get)
    return {"statement_in_code": "< 10 %", "computed_min_relative_change": rel[lo] - 1.0, "computed_min_at": lo,
            "computed_max_relative_change": rel[hi] - 1.0, "computed_max_at": hi}


def exposed_uncertainty(cases: list[dict]) -> list[dict]:
    sm = _surface_meta()
    acc = _ast_dict_entry("abep_sim/uq_modular.py", "PRIORS", "accommodation")
    n = int(sm["n_per_point"])
    return [
        {"module": "abep_sim.atmosphere", "quantity": "free-stream state", "exposed": None,
         "note": "none exposed (frozen scenario values only). TBD - requires a published NRLMSIS 2.1 error "
                 "characterisation"},
        {"module": "abep_sim.intake_tpmc (frozen surface metadata)", "quantity": "TPMC sampling of eta_open",
         "exposed": {"n_per_point": n, "max_unresolved": sm["max_unresolved"],
                     "binomial_standard_error_bound": 0.5 / math.sqrt(n)},
         "evidence_class": "model-derived",
         "note": "bound = max_p sqrt(p (1 - p) / n_per_point) = 0.5 / sqrt(n_per_point), derived here from the "
                 "metadata; interpolation error of the ROM is not characterised; not propagated"},
        {"module": "abep_sim.intake (code comment)",
         "quantity": "speed-ratio variation sqrt(T/m) away from the TPMC build point (drives eta_c, C_D, K_back)",
         "exposed": _speed_ratio_spread(cases), "evidence_class": "model-derived",
         "note": "statement from the abep_sim/intake.py _tpmc_surface docstring (no cited source: verify); the "
                 "computed values are sqrt(T_ambient / m_mean) of each case divided by that of the frozen 200 km / "
                 "F10.7 150 state, minus 1 (relative change). Effect on eta_c not quantified; not propagated"},
        {"module": "abep_sim.uq_modular", "quantity": "intake accommodation (epistemic prior)",
         "exposed": {"distribution": "triangular", "low": acc[0], "mode": acc[1], "high": acc[2], "kind": acc[3]},
         "evidence_class": "assumed",
         "note": "read from source (PRIORS['accommodation']); code prior without cited source; the only upstream "
                 "uncertainty prior in code (ICD G-13); not propagated here"},
        {"module": "abep_sim.compressor / abep_sim.reservoir / abep_sim.materials", "quantity": "all outputs",
         "exposed": None,
         "note": "none exposed; material recombination coefficients are literature-class priors (materials.py)"},
    ]


def xe_path() -> dict:
    def tbd(unit, requires):
        return quantity(None, unit, evidence_class="TBD", uncertainty=uncertainty_tbd("no producer"),
                        source="no Xe feed model in the repository (ICD G-12)", validity_domain="D-XE-TBD",
                        in_domain=None, producer={"call": "none", "derivation": "no producer"}, requires=requires)
    pure = {"Xe": 1.0}
    kw = dict(evidence_class="assumed", uncertainty=uncertainty_tbd(
        "nominal pure-xenon feed; TBD - requires a propellant purity specification (ICD IF-X1 xe_purity gap)"),
        source="definition of the Xe path (CLAUDE.md RFP architecture: Xe chamber -> valve)",
        validity_domain="D-XE-TBD", in_domain=None,
        producer={"call": "none", "derivation": "definition (single-species path)"})
    return {
        "interface": "IF-X2", "altitude_dependent": False, "architecture_dependent": False,
        "status": ST_MISSING,
        "feed_state": {
            "mdot_xe_anode_kgps": tbd("kg s^-1", "TBD - requires a Xe flow-setpoint policy and a Xe valve/regulator "
                                                 "design (ICD G-12); thruster.xe_for_thrust is a card-model demand, not "
                                                 "a feed state"),
            "mdot_xe_cathode_kgps": tbd("kg s^-1", "TBD - requires the cathode design (docs/evidence/cathode/, other "
                                                   "lane)"),
            "p_feed_Pa": tbd("Pa", "TBD - requires a regulator/valve model (ICD G-12)"),
            "T_gas_K": tbd("K", "TBD - requires a feed thermal state (ICD G-12)"),
            "w_s": species_quantity(pure, "-", **kw),
            "x_s": species_quantity(pure, "-", **kw),
        },
        "mixed_air_xe_feed": {"status": "TBD",
                              "requires": "TBD - requires the Xe flow-setpoint policy; intake-delivered mixtures are "
                                          "gated behind CLAUDE.md Next work 1-3 (Next work 4)"},
    }


def open_questions() -> list[str]:
    return [
        "Design baseline: which intake area and geometry (L/d, phi), surface-state value, plenum temperature, "
        "compressor design (fixed or sized), chamber and valve setting should be the documented baseline, and from "
        "which sources? Until supplied, the valve-outlet feed state stays TBD.",
        "Common feed pressure: one architecture-neutral valve setpoint for all three architectures, or a common feed "
        "state with each architecture's ionizer pressure window checked downstream? (The thruster.py stage cards "
        "carry different minimum-pressure priors; those cards are not adopted.)",
        "Composition convention (ICD G-02): keep the system.evaluate free-stream split as primary, or switch to the "
        "species-resolved frozen surface (a model change for the chain; goldens may move)?",
        "Extremes: authorize a frozen, orbit-resolved NRLMSIS dataset (CLAUDE.md rule 1 rebuild) so along-track "
        "density/composition extremes can be added; which geomagnetic levels beyond ap 15?",
        "Atmosphere levels: confirm low/mean/high = F10.7 = F10.7A 70/150/230 at ap 15 (repository convention "
        "atmosphere._SOLAR_F107) against the mission's solar-cycle specification.",
        "Species scope: the frozen dataset drops He, H, Ar and N; is O/N2/O2 sufficient for the feed definition?",
        "Composition basis at the Hall boundary (ICD open question 3): mass or mole fraction for a composition axis?",
    ]


# --------------------------------------------------------------------------------------------------------- document
def build_document(design_doc: dict | None = None, altitudes=ALTITUDES_KM, levels=LEVELS) -> dict:
    dv = validate_design_inputs(design_doc) if design_doc is not None else None
    label = design_doc["label"] if design_doc is not None else None
    meta = frozen_atmosphere_meta()
    sm = _surface_meta()
    lm = level_mapping()
    cases = [build_case(a, l, dv, label) for a in altitudes for l in levels]
    catalog = design_input_catalog()
    if dv is not None:
        for e in catalog:
            if e["name"] in design_doc["inputs"]:
                e["status"] = "supplied"
                e["documented_baseline"] = None
            else:
                e["status"] = "not_required_in_selected_modes"
    doc = {
        "envelope": ENVELOPE_NAME,
        "envelope_version": ENVELOPE_VERSION,
        "schema": SCHEMA_REL,
        "status": "DRAFT for owner review",
        "generated_by": {"script": SCRIPT_REL,
                         "command": f"python {SCRIPT_REL}" + (" --design-inputs <file> --out-dir <dir>" if dv else ""),
                         "deterministic": True, "output_rounding_significant_digits": SIG_DIGITS},
        "what_it_is": ("The common feed state delivered to the ionization/discharge block (valve outlet, ICD IF-A5; Xe "
                       "port IF-X2) per altitude and atmosphere level, plus the orbit-averaged free-stream state that "
                       "feeds the chain (ICD IF-A0), with producer, evidence class and uncertainty per value."),
        "what_it_is_not": ("Not a design, not a Hall prediction, not an architecture ranking, not a model change: no "
                           "module is modified or wired, no frozen dataset is rebuilt, and no value depends on a Hall "
                           "transport closure, an ensemble member or a P5 calibration-nuisance variable."),
        "milestones": milestones(),
        "architectures": {
            "ids": list(ARCHITECTURES),
            "common_feed_rule": ("All three architectures receive the identical feed record for a given case. The "
                                 "RF/ECR arms change only the pre-ionization method, which is downstream of IF-A5; "
                                 "no field is keyed by, parameterised by or produced for an architecture id."),
            "architecture_dependent_fields": [],
        },
        "interface_alignment": {
            "icd_schema": ICD_SCHEMA_REL, "icd_version": "1.0.0", "icd_status": "DRAFT (other lane; read-only)",
            "free_stream": "IF-A0", "feed_state": "IF-A5", "xe_feed_state": "IF-X2",
            "shared_field_names": ["rho_kgpm3", "n_total_m3", "T_ambient_K", "V_mps", "mass_flux_kgpm2ps",
                                   "p_ambient_Pa", "m_mean_kg", "w_s", "x_s", "atmosphere_source",
                                   "atmosphere_in_domain", "mdot_total_kgps", "mdot_s_kgps", "p_feed_Pa", "T_gas_K",
                                   "mdot_xe_anode_kgps", "mdot_xe_cathode_kgps"],
            "added_fields": ["species_mass_flux_kgpm2ps", "feed_scaling.A_eff_m2",
                             "xe_path.feed_state.w_s / x_s (ICD IF-X2 has xe_purity, a gap, instead)"],
            "quantity_shape": ("ICD scalar_quantity / species_quantity (value|values, unit, evidence_class, "
                               "uncertainty, source, validity_domain, in_domain) plus 'producer' and, for TBD values, "
                               "'requires' / 'requires_design_inputs'. Drop those keys to form an ICD record."),
            "composition_basis": "w_s = mass fraction, x_s = mole fraction (flow basis at IF-A5)",
        },
        "provenance": {
            "input_files": [{"path": p, "sha256": sha256_file(p), "role": r} for p, r in INPUT_FILES],
            "files_read": [{"path": p, "role": r} for p, r in FILES_READ],
            "frozen_atmosphere": {"model": meta["model"], "pymsis": meta["pymsis"], "epoch": meta["epoch"],
                                  "ap": meta["ap"], "f107_grid": meta["f107"], "alt_km_grid": meta["alt_km"],
                                  "averaging": meta["averaging"], "sha256_16": meta["sha256_16"],
                                  "species_dropped": meta["species_dropped"]},
            "frozen_intake_surface": {"sha256_16": sm["sha256_16"], "atmosphere": sm["atmosphere"],
                                      "species": sm["species"], "scattering": sm["scattering"], "grid": sm["grid"],
                                      "n_per_point": sm["n_per_point"], "max_unresolved": sm["max_unresolved"]},
            "chain_mirrored": ("abep_sim/archengine.py:gas_path_state -> abep_sim/system.py:evaluate "
                               "(gaspath_physics=True): atmosphere -> intake.collection (TPMC) -> intake.compress "
                               "(passive plenum) -> compressor.DragCompressor.size_for/run -> reservoir.Reservoir + "
                               "size_orifice_for_pressure -> Reservoir.steady_state (mdot_anode, p_total_Pa, T_K, "
                               "composition_anode_mass)"),
        },
        "validity_domains": VALIDITY_DOMAINS,
        "atmosphere_levels": {
            "mapping": {lvl: {"f107": lm[lvl], "f107a": lm[lvl], "ap": float(meta["ap"])} for lvl in LEVELS},
            "source": "abep_sim/atmosphere.py _SOLAR_F107 (low/mean/high -> F10.7 70/150/230; module docstring "
                      "'F10.7 ~ 70 / 150 / 230'); F10.7A = F10.7 and ap from the frozen dataset metadata",
            "evidence_class": "assumed",
            "note": ("The level labels are a repository convention with no external source cited in the repository "
                     "(verify against the mission solar-cycle specification). Each level is an exact node of the "
                     "frozen F10.7 grid, so no F10.7 interpolation is involved (the grid also holds F10.7 100 and 190, "
                     "which no level uses). Geomagnetic activity: only ap = 15 is "
                     "in the frozen dataset (no storm levels). Single epoch (equinox), so seasonal variation is not "
                     "covered."),
        },
        "extremes": {
            "status": "TBD",
            "requires": ("TBD - requires a frozen orbit-resolved NRLMSIS dataset (built under CLAUDE.md rule 1). The "
                         "frozen dataset is orbit-averaged by construction; abep_sim/orbit_atm.orbit_atmosphere "
                         "computes along-track min/max only with live pymsis, which the frozen chain does not use "
                         "(CLAUDE.md rule 3)"),
            "covered_here": "orbit-averaged states only (averaging = 'orbit_averaged' in every case)",
        },
        "design_inputs": ({"supplied": False, "label": None, "entries": {},
                           "note": "no design-input file supplied: the repository documents no design baseline with "
                                   "provenance for the chain's design inputs (see not_adopted)"}
                          if dv is None else
                          {"supplied": True, "label": label, "entries": design_doc["inputs"]}),
        "design_input_contract": catalog,
        "cases": cases,
        "envelope_ranges": envelope_ranges(cases),
        "xe_path": xe_path(),
        "exposed_uncertainty": exposed_uncertainty(cases),
        "not_adopted": not_adopted(),
        "chain_findings": chain_findings(),
        "open_questions": open_questions(),
    }
    return rnd(doc)


# ----------------------------------------------------------------------------------------------- schema validation
SUPPORTED_SCHEMA_KEYWORDS = {"$ref", "type", "properties", "required", "additionalProperties", "enum", "const", "items",
                             "minItems", "anyOf", "allOf", "propertyNames", "pattern", "minimum", "maximum",
                             "minLength", "minProperties"}
ANNOTATION_KEYWORDS = {"$schema", "$id", "$defs", "title", "description", "$comment", "examples"}


def _type_ok(v, t) -> bool:
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "null":
        return v is None
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    raise FeedEnvelopeError(f"unsupported type {t}")


def validate(instance, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """Minimal JSON-Schema (Draft 2020-12 subset) validator: the keyword set in SUPPORTED_SCHEMA_KEYWORDS.
    jsonschema is not a project dependency; the test also runs jsonschema when it is installed."""
    root = root if root is not None else schema
    errs: list[str] = []
    if schema is True:
        return errs
    if schema is False:
        return [f"{path}: not allowed"]
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise FeedEnvelopeError(f"unsupported $ref {ref}")
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
        errs += validate(instance, node, root, path)
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(instance, t) for t in ts):
            return errs + [f"{path}: type {type(instance).__name__} not in {ts}"]
    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: {instance!r} != const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in enum {schema['enum']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{path}: {instance} > maximum {schema['maximum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: {instance!r} does not match {schema['pattern']}")
    if isinstance(instance, dict):
        for k in schema.get("required", []):
            if k not in instance:
                errs.append(f"{path}: missing required '{k}'")
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errs.append(f"{path}: fewer than {schema['minProperties']} properties")
        props = schema.get("properties", {})
        for k, v in instance.items():
            if "propertyNames" in schema:
                errs += validate(k, schema["propertyNames"], root, f"{path}.<name {k}>")
            if k in props:
                errs += validate(v, props[k], root, f"{path}.{k}")
            elif "additionalProperties" in schema:
                ap = schema["additionalProperties"]
                if ap is False:
                    errs.append(f"{path}: additional property '{k}' not allowed")
                elif isinstance(ap, dict):
                    errs += validate(v, ap, root, f"{path}.{k}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, v in enumerate(instance):
                errs += validate(v, schema["items"], root, f"{path}[{i}]")
    for sub in schema.get("allOf", []):
        errs += validate(instance, sub, root, path)
    if "anyOf" in schema:
        branch_errs = [validate(instance, sub, root, path) for sub in schema["anyOf"]]
        if all(branch_errs):
            errs.append(f"{path}: no anyOf branch matches (first branch: {branch_errs[0][:2]}; "
                        f"last branch: {branch_errs[-1][:2]})")
    return errs


def schema_keywords(schema, found=None) -> set:
    """Every keyword used in the schema (walks subschemas)."""
    found = set() if found is None else found
    if isinstance(schema, dict):
        for k, v in schema.items():
            found.add(k)
            if k in ("properties", "$defs"):
                for sub in v.values():
                    schema_keywords(sub, found)
            elif k in ("items", "additionalProperties", "propertyNames") and isinstance(v, dict):
                schema_keywords(v, found)
            elif k in ("anyOf", "allOf"):
                for sub in v:
                    schema_keywords(sub, found)
    return found


def load_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text())


def validate_document(doc: dict) -> None:
    errs = validate(doc, load_schema())
    if errs:
        raise FeedEnvelopeError("feed envelope fails its schema:\n  " + "\n  ".join(errs[:40]))
    # closure (cannot be expressed in JSON Schema)
    for c in doc["cases"]:
        for blk in ("free_stream", "feed_state"):
            for key in ("w_s", "x_s"):
                vals = c[blk][key]["values"]
                if vals and all(v is not None for v in vals.values()):
                    if abs(sum(vals.values()) - 1.0) > MASS_FRACTION_CLOSURE_TOL:
                        raise FeedEnvelopeError(f"{c['case_id']}.{blk}.{key} does not sum to 1")


# ------------------------------------------------------------------------------------------------------- markdown
def _f(v, d=4) -> str:
    if v is None:
        return "TBD"
    if isinstance(v, str):
        return v
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    return f"{v:.{d}g}"


def render_markdown(doc: dict) -> str:
    L: list[str] = []
    a = L.append
    ms = doc["milestones"]
    a("# Thruster feed envelope v1 — common feed state for hall_only / rf_hall / ecr_hall")
    a("")
    a("> Generated by `" + SCRIPT_REL + "` from `" + JSON_NAME + "`. Do not edit by hand; rerun the script.")
    a("")
    a("| | |")
    a("|---|---|")
    a(f"| machine-readable | [`{JSON_NAME}`]({JSON_NAME}), validated by [`{SCHEMA_REL}`](../../../{SCHEMA_REL}) |")
    a(f"| status | **{doc['status']}** (envelope version {doc['envelope_version']}) |")
    a(f"| milestone | supports **{', '.join(ms['supports'])}** (conditional selection); what is needed for B and C is "
      f"listed in section 9 |")
    a(f"| architectures | {', '.join('`' + x + '`' for x in doc['architectures']['ids'])}: identical feed record per "
      f"case; no field depends on the architecture id |")
    a(f"| interface | ICD `{doc['interface_alignment']['icd_schema']}` v{doc['interface_alignment']['icd_version']} "
      f"(other lane, draft): free stream = IF-A0, feed state = IF-A5 (air), IF-X2 (Xe) |")
    a(f"| test | `tests/test_feed_envelope.py` |")
    a("")
    a("**What it is.** " + doc["what_it_is"])
    a("")
    a("**What it is not.** " + doc["what_it_is_not"])
    a("")
    a("## 1. Chain and boundary")
    a("")
    a("```")
    a("ambient -IF-A0-> intake -> filter -> compressor -> atmospheric gas chamber -> valve -IF-A5-+")
    a("                                                                                          +-> ionization/discharge")
    a("                                        Xe chamber (tank) -> Xe valve --------------IF-X2-+    (pre-ionizer: RF / ECR / none)")
    a("```")
    a("")
    a("The feed state is defined at IF-A5 / IF-X2, upstream of any pre-ionizer, so the three architectures are compared "
      "at the same record. Chain mirrored (read, not imported or modified): " + doc["provenance"]["chain_mirrored"] + ".")
    a("")
    a("## 2. Atmosphere levels (mapping and provenance)")
    a("")
    al = doc["atmosphere_levels"]
    a("| level | F10.7 | F10.7A | ap |")
    a("|---|---|---|---|")
    for lvl, m in al["mapping"].items():
        a(f"| {lvl} | {_f(m['f107'])} | {_f(m['f107a'])} | {_f(m['ap'])} |")
    a("")
    a(f"Source: {al['source']}. Evidence class of the mapping: **{al['evidence_class']}**. {al['note']}")
    a("")
    fa = doc["provenance"]["frozen_atmosphere"]
    a(f"Frozen dataset: {fa['model']} (pymsis {fa['pymsis']}), epoch {fa['epoch']}, {fa['averaging']}, sha256_16 "
      f"`{fa['sha256_16']}`; species dropped: {fa['species_dropped']} (verify).")
    a("")
    a("## 3. Free-stream state per case (orbit-averaged; ICD IF-A0; evidence class model-derived)")
    a("")
    a("| case | ρ [kg m⁻³] | n [m⁻³] | T [K] | V [m s⁻¹] | ρV [kg m⁻² s⁻¹] | p_amb [Pa] | w_O | w_N2 | w_O2 | x_O | x_N2 | x_O2 |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in doc["cases"]:
        fs = c["free_stream"]
        w = fs["w_s"]["values"]
        x = fs["x_s"]["values"]
        a(f"| {c['alt_km']:.0f} km {c['atmosphere_level']} | {_f(fs['rho_kgpm3']['value'])} | "
          f"{_f(fs['n_total_m3']['value'])} | {_f(fs['T_ambient_K']['value'])} | {_f(fs['V_mps']['value'])} | "
          f"{_f(fs['mass_flux_kgpm2ps']['value'])} | {_f(fs['p_ambient_Pa']['value'])} | "
          f"{_f(w['O'])} | {_f(w['N2'])} | {_f(w['O2'])} | {_f(x['O'])} | {_f(x['N2'])} | {_f(x['O2'])} |")
    a("")
    a("Producer: `abep_sim.atmosphere.atmosphere(alt_km, level, ap=15.0, date='2028-03-21T12:00', "
      "orbit_average=True, use_msis=False)`; x_s = (w_s/M_s)/Σ(w_k/M_k) with `constants.M_SPECIES`; ρV is the "
      "incident mass flux (`flux_kg_m2_s`). Each value is an exact node of the frozen dataset (checked against the "
      "CSV row). Uncertainty: none exposed by the module (TBD, see section 7). Full precision, producer and "
      "per-value metadata are in the JSON.")
    a("")
    a("## 4. Envelope ranges (scenario set, not uncertainty)")
    a("")
    er = doc["envelope_ranges"]
    a(er["basis"] + ".")
    a("")
    a("| quantity | unit | 180 km min–max | 200 km min–max | 230 km min–max | overall min–max | overall max/min |")
    a("|---|---|---|---|---|---|---|")
    for name, r in er["free_stream"].items():
        ba = r["by_altitude"]
        o = r["overall"]
        a(f"| {name} | {o['unit']} | " + " | ".join(
            f"{_f(ba[k]['min'])}–{_f(ba[k]['max'])}" if k in ba else "—" for k in ("180", "200", "230"))
          + f" | {_f(o['min'])}–{_f(o['max'])} | {_f(o['max_over_min'], 3)} |")
    a("")
    a("## 5. Feed state at the valve outlet (ICD IF-A5)")
    a("")
    fsr = er["feed_state"]
    if not doc["design_inputs"]["supplied"]:
        a("| case | status | mdot [kg s⁻¹] | p_feed [Pa] | T_gas [K] | w_s / x_s |")
        a("|---|---|---|---|---|---|")
        for c in doc["cases"]:
            a(f"| {c['case_id']} | {c['status']} | TBD | TBD | TBD | TBD |")
        a("")
        a("Every valve-outlet quantity is **TBD**; it " + fsr["requires"].replace("TBD - ", "", 1) + ". Each TBD "
          "value in the JSON names the "
          "design inputs it needs (`requires_design_inputs`) and why. The design-independent factor of the delivered "
          "flow is known now:")
        a("")
        a("    mdot_total_kgps = A_eff_m2 × free_stream.mass_flux_kgpm2ps,   A_eff = η_c(L/d, φ, α, θ) × A_intake × "
          "(1 − backflow) × anode share")
        a("")
        a("so, for any design, the delivered flow follows the ρV values of section 3 through one design factor A_eff "
          "(TBD), and that factor is the same for all three architectures.")
    else:
        n_ok = sum(c["status"] == ST_OK for c in doc["cases"])
        a(f"Design inputs: `{doc['design_inputs']['label']}` ({n_ok} of {len(doc['cases'])} cases OK; evidence classes "
          "of the inputs in `design_inputs`). Values are model-derived and conditional on those inputs; a case that is "
          "INFEASIBLE or MODEL_ERROR has no feed state (—).")
        a("")
        a("| case | status | mdot [kg s⁻¹] | p_feed [Pa] | T_gas [K] | x_O | x_N2 | x_O2 | reasons |")
        a("|---|---|---|---|---|---|---|---|---|")

        def g(v):
            return "—" if v is None else _f(v)
        for c in doc["cases"]:
            fs = c["feed_state"]
            xv = fs["x_s"]["values"]
            a(f"| {c['case_id']} | {c['status']} | {g(fs['mdot_total_kgps']['value'])} | {g(fs['p_feed_Pa']['value'])} | "
              f"{g(fs['T_gas_K']['value'])} | {g(xv.get('O'))} | {g(xv.get('N2'))} | {g(xv.get('O2'))} | "
              f"{'; '.join(c['status_reasons']) or '—'} |")
    a("")
    a("## 6. Xe path (ICD IF-X2) and extremes")
    a("")
    xp = doc["xe_path"]
    a(f"Status {xp['status']}; altitude- and architecture-independent. x_Xe = w_Xe = 1 is **assumed** (definition of "
      "the Xe path; purity specification TBD). Anode and cathode Xe flow, feed pressure and temperature are TBD: no Xe "
      "storage/regulator/valve model exists (ICD G-12). Mixed air + Xe feed: " + xp["mixed_air_xe_feed"]["requires"] + ".")
    a("")
    a("Orbit-averaged vs extremes: " + doc["extremes"]["covered_here"] + ". Extremes: " + doc["extremes"]["requires"] + ".")
    a("")
    a("## 7. Uncertainty the modules expose")
    a("")
    a("| module | quantity | exposed | note |")
    a("|---|---|---|---|")
    for u in doc["exposed_uncertainty"]:
        ex = u["exposed"]
        exs = "none" if ex is None else ", ".join(f"{k} = {_f(v) if not isinstance(v, str) else v}" for k, v in ex.items())
        a(f"| {u['module']} | {u['quantity']} | {exs} | {u['note']} |")
    a("")
    a("## 8. Design-input contract (explicit, no hidden defaults)")
    a("")
    a("Supply every input below in a `" + DESIGN_INPUTS_FORMAT + "` file (`{format, label, inputs: {name: {value, "
      "source, evidence_class}}}`) and run with `--design-inputs FILE --out-dir DIR`. A missing input raises "
      "`MissingDesignInput`; an input without source or evidence class, an unknown input, or an out-of-grid intake "
      "value raises `InvalidDesignInput`. Code defaults are listed for transparency only; **none is adopted**.")
    a("")
    a("| input | unit | required when | consumer | status | code defaults (not adopted) |")
    a("|---|---|---|---|---|---|")
    for e in doc["design_input_contract"]:
        cds = "; ".join(f"{cd_['value']!r} ({cd_['source'].split(' (')[0]})" for cd_ in e["code_defaults"]) or "—"
        a(f"| `{e['name']}` | {e['unit']} | {e['required_when']} | {e['consumer']} | {e['status']} | {cds} |")
    a("")
    a("Repository values seen but not adopted:")
    a("")
    for n in doc["not_adopted"]:
        val = "" if n["value"] is None else f" = {_f(n['value'])} {n['unit']}"
        a(f"- `{n['quantity']}`{val} ({n['file']}): {n['reason']}.")
    a("")
    a("## 9. Milestones")
    a("")
    a(ms["statement"])
    a("")
    a("To reach **B** (physics-backed selection):")
    a("")
    for s in ms["to_reach_B"]:
        a(f"- {s}")
    a("")
    a("To reach **C** (proposal/PDR freeze):")
    a("")
    for s in ms["to_reach_C"]:
        a(f"- {s}")
    a("")
    a("## 10. Chain findings (stated, not fixed; fixing them is outside this lane)")
    a("")
    a("| id | ICD gap | where | finding | handling here |")
    a("|---|---|---|---|---|")
    for f_ in doc["chain_findings"]:
        a(f"| {f_['id']} | {f_['icd_gap'] or '—'} | `{f_['where']}` | {f_['finding']} | {f_['handling']} |")
    a("")
    a("## 11. Open questions for the owner")
    a("")
    for i, q in enumerate(doc["open_questions"], 1):
        a(f"{i}. {q}")
    a("")
    a("## 12. Reproduce / verify")
    a("")
    a("```")
    a(f"python {SCRIPT_REL}            # rewrite {OUT_DIR_REL}/{{{JSON_NAME},{MD_NAME}}}")
    a(f"python {SCRIPT_REL} --check    # exit 1 unless the committed files are reproduced")
    a("python -m pytest -q tests/test_feed_envelope.py")
    a("```")
    a("")
    a("The frozen data files and the atmosphere/constants modules are recorded with their sha256 "
      "(`provenance.input_files`); a change to any of them changes the envelope and the test asks for regeneration. "
      "Other modules read are listed in `provenance.files_read`.")
    a("")
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------------------ main
def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def write_outputs(doc: dict, out_dir: Path) -> tuple[Path, Path]:
    validate_document(doc)
    out_dir.mkdir(parents=True, exist_ok=True)
    pj, pm = out_dir / JSON_NAME, out_dir / MD_NAME
    pj.write_text(dumps(doc))
    pm.write_text(render_markdown(doc))
    return pj, pm


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--design-inputs", type=Path, default=None,
                    help=f"design-input file ({DESIGN_INPUTS_FORMAT}); without it design-dependent values are TBD")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help=f"output directory (default {OUT_DIR_REL} only when no design inputs are given)")
    ap.add_argument("--check", action="store_true", help="verify the committed files are reproduced; write nothing")
    a = ap.parse_args(argv)
    design_doc = json.loads(a.design_inputs.read_text()) if a.design_inputs else None
    if design_doc is not None and a.out_dir is None and not a.check:
        ap.error("--design-inputs requires an explicit --out-dir (the committed envelope is baseline-free)")
    doc = build_document(design_doc)
    validate_document(doc)
    out_dir = a.out_dir or (REPO / OUT_DIR_REL)
    if a.check:
        pj, pm = out_dir / JSON_NAME, out_dir / MD_NAME
        ok = pj.exists() and pj.read_text() == dumps(doc) and pm.exists() and pm.read_text() == render_markdown(doc)
        print(("OK: " if ok else "MISMATCH: ") + f"{pj} / {pm}")
        return 0 if ok else 1
    pj, pm = write_outputs(doc, out_dir)
    print(f"wrote {pj}\nwrote {pm}")
    return 0


if __name__ == "__main__":
    # Performance only (results do not depend on it): the chain does tiny linear algebra, and multi-threaded OpenBLAS
    # makes the first evaluation of the frozen TPMC interpolant very slow on a loaded machine. Set before numpy loads;
    # an explicit user setting wins.
    for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(_var, "1")
    sys.exit(main())
