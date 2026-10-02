"""Build specification for the frozen intake response surface v2 (owner decision A9.9 S2.2 / F1Q-04).

STATUS: SPECIFICATION ONLY - THE v2 BUILD IS BLOCKED.
Owner decision A9.13 S6.2 (docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md) makes the v2
angular (incidence / relative-wind pointing) axis the REGISTERED spacecraft/AOCS relative-wind pointing envelope:
"first register the required relative-wind pointing envelope from the spacecraft/AOCS design; build the frozen surface over
that complete registered envelope". No such envelope is registered in the repository, so the angular axis is
`TBD_AOCS_POINTING_ENVELOPE` and `build_intake_surface_v2()` refuses to run (fail closed). The existing 0/2/5 deg of
intake_surface_v1 are a sensitivity set only (S6.2), never the v2 angular domain by default.

What this module fixes now (everything that does not need the envelope), from the verbatim S2.2 list:
  * species-resolved (O, N2, O2 rows; recombined by IntakeSurface from the physical definitions of A9.9 S2.1);
  * Maxwell and CLL as SEPARATE admitted scenarios (never mixed, never a fallback; intake_tpmc.SCATTERING_MODELS);
  * deterministic seeds (derived from the canonical grid-point key by SHA-256, independent of grid ordering);
  * the convergence criterion (the registered unresolved-particle criterion of intake_tpmc plus the gate-5 statistical
    tolerance of abep_sim.convergence) and retained unresolved-particle / convergence information per row;
  * full provenance, configuration and hashes;
  * direct-TPMC cross-check at selected build states AND at held-out states not on the build grid;
  * fail closed outside the frozen domain (IntakeSurface raises; no clamping, no extrapolation);
  * v1 (abep_sim/data/intake_surface_v1.*) retained unchanged; production references move to v2 only after verification.

Axes other than the angular one must also be registered before a build ("cover the intended altitude/atmosphere/incidence/
surface-state envelope used by the production model", S2.2). Their grid values are not invented here: they carry
`TBD_REGISTRATION` with the coverage requirement stated. The primary blocker reported by `v2_build_status()` is the AOCS
pointing envelope (A9.13 S6.2); the others are listed so nothing is silently defaulted when the envelope arrives.

This module performs no TPMC and writes no file. It never touches intake_surface_v1.
"""
from __future__ import annotations

import copy
import hashlib
import json

SPEC_ID = "intake_surface_v2_spec_v1"
TARGET_DATASET = "intake_surface_v2"           # abep_sim/data/intake_surface_v2.{csv,json} once built (rule 1)
RETAINED_DATASET = "intake_surface_v1"         # unchanged, kept for reproducibility of historical results

TBD_AOCS = "TBD_AOCS_POINTING_ENVELOPE"
TBD_REG = "TBD_REGISTRATION"
TBD_TOKENS = (TBD_AOCS, TBD_REG)

BLOCKED_STATUS = "BLOCKED_PENDING_AOCS_POINTING_ENVELOPE"
OWNER_DECISIONS = ("A9.9 S2.2 (F1Q-04)", "A9.9 S2.1 (F1Q-01, implemented before v2)", "A9.13 S6.2 (F1Q-03)")

# Axis registry. 'values' is either a registered list (with its source) or a TBD token. Nothing below is an invented
# physical value: the only concrete lists are categorical choices fixed by the owner text / existing code.
_AXES = {
    "theta_deg": {
        "role": "incidence of the relative wind on the intake axis (pointing error)",
        "values": TBD_AOCS,
        "requirement": "the complete REGISTERED spacecraft/AOCS relative-wind pointing envelope (A9.13 S6.2); "
                       "v1's 0/2/5 deg are a sensitivity set only and are not the v2 domain by default",
        "source": "A9.13 S6.2",
    },
    "atmosphere_state": {
        "role": "free-stream state (altitude, solar/geomagnetic activity, relative speed): sets the speed ratio and "
                "the build-mixture normalisation of the species C_D rows",
        "values": TBD_REG,
        "requirement": "the altitude/atmosphere envelope used by the production model (RFP 180-230 km and the solar "
                       "activity range); each state taken from the frozen atmosphere dataset (use_msis=False) and "
                       "recorded with its m_mean (IntakeSurface needs it per state)",
        "source": "A9.9 S2.2; RFP envelope as recorded in CLAUDE.md",
    },
    "L_over_d": {
        "role": "channel length / diameter",
        "values": TBD_REG,
        "requirement": "the geometry range used by the production model and the design searches",
        "source": "A9.9 S2.2",
    },
    "phi": {
        "role": "open-area fraction",
        "values": TBD_REG,
        "requirement": "the geometry range used by the production model and the design searches",
        "source": "A9.9 S2.2",
    },
    "alpha": {
        "role": "surface state: Maxwell diffuse fraction; CLL alpha_n = alpha_t (the existing intake.collection "
                "convention). A separate (alpha_n, alpha_t) grid would need its own registration",
        "values": TBD_REG,
        "requirement": "the surface-state envelope used by the production model (fresh .. AO-aged), within [0, 1]",
        "source": "A9.9 S2.2; intake_tpmc MCC-07 admitted interval",
    },
    "species": {
        "role": "species-resolved rows (never a mean-mass row)",
        "values": ["O", "N2", "O2"],
        "requirement": "species-resolved; mixture recombination by IntakeSurface (A9.9 S2.1 physical definitions)",
        "source": "A9.9 S2.2 'remain species-resolved'; v1 species set (intake_surface_v1.json)",
    },
    "scattering": {
        "role": "gas-surface scattering kernel: separate admitted physical scenarios, never mixed",
        "values": ["maxwell", "cll"],
        "requirement": "Maxwell and CLL retained as separate scenarios (one sub-table each, explicitly recorded)",
        "source": "A9.9 S2.2; intake_tpmc.SCATTERING_MODELS (MCC-06)",
    },
}

_REQUIREMENTS = {
    "species_resolved": True,
    "separate_scattering_scenarios": True,
    "deterministic_seeds": {
        "rule": "seed = int(sha256(canonical_json(point_key))[:16], 16) mod 2**63; point_key holds every axis value "
                "plus species and scattering, so seeds do not depend on grid ordering or chunking",
        "function": "abep_sim.intake_surface_v2_spec.point_seed",
    },
    "convergence_criterion": {
        "unresolved_particles": "intake_tpmc.intake_response 'converged' := unresolved_fraction <= 1e-3 "
                                "(trace_channel unresolved_tol, hit budget doubling to max_hits_cap); a row that is "
                                "not converged fails the build, it is never written as valid",
        "statistical": "direct-TPMC cross-check relative difference < abep_sim.convergence.TOL (gate 5, 2 %) for "
                       "eta_c and C_D; n_per_point is a build-configuration value recorded in the metadata and must "
                       "be registered with the axes (TBD_REGISTRATION)",
        "n_per_point": TBD_REG,
    },
    "retained_per_row": ["unresolved_fraction", "converged", "mean_wall_hits", "scattering", "K_back_scattering",
                         "seed", "n_per_point", "species", "atmosphere_state_id"],
    "provenance": ["spec_id and spec_sha256", "git commit of the build", "owner decision ids",
                   "frozen atmosphere dataset id + hash for every state", "IntakeGeometry fixed fields (T_wall, d_mm, "
                   "area, filter=False)", "csv sha256", "build command", "python/numpy versions"],
    "cross_check": {
        "build_states": "direct intake_response at selected on-grid points, every scenario and species, compared with "
                        "the stored rows",
        "held_out_states": "direct intake_response at points NOT on the build grid (interior of every axis incl. "
                           "theta and atmosphere state), compared with IntakeSurface interpolation; selected and "
                           "recorded before the build",
        "tolerance": "abep_sim.convergence.TOL (gate 5) unless a separate value is registered",
    },
    "fail_closed_outside_domain": "IntakeSurface raises outside the frozen axes (no clamping in intake.collection, no "
                                  "extrapolation, no NaN passed on)",
    "retain_v1_unchanged": True,
    "production_switch": "production references move from v1 to v2 only after the cross-check verification passes",
}


class IntakeSurfaceV2Blocked(RuntimeError):
    """Raised when the v2 build is requested while a required axis is not registered."""


def spec() -> dict:
    """A deep copy of the v2 build specification (axes, requirements, status)."""
    return {"spec_id": SPEC_ID, "target_dataset": TARGET_DATASET, "retained_dataset": RETAINED_DATASET,
            "owner_decisions": list(OWNER_DECISIONS), "axes": copy.deepcopy(_AXES),
            "requirements": copy.deepcopy(_REQUIREMENTS), "status": v2_build_status()}


def spec_sha256() -> str:
    """Hash of the specification content (recorded in the v2 provenance when it is eventually built)."""
    s = {"spec_id": SPEC_ID, "axes": _AXES, "requirements": _REQUIREMENTS}
    return hashlib.sha256(json.dumps(s, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def unregistered_axes() -> list[str]:
    """Axes whose values (or required build settings) are still a TBD token; the angular axis first."""
    out = [k for k, a in _AXES.items() if isinstance(a["values"], str) and a["values"] in TBD_TOKENS]
    out.sort(key=lambda k: (k != "theta_deg", k))
    if _REQUIREMENTS["convergence_criterion"]["n_per_point"] in TBD_TOKENS:
        out.append("convergence_criterion.n_per_point")
    return out


def v2_build_status() -> dict:
    tbd = unregistered_axes()
    if _AXES["theta_deg"]["values"] == TBD_AOCS:
        return {"status": BLOCKED_STATUS, "primary_blocker": "theta_deg = " + TBD_AOCS + " (A9.13 S6.2)",
                "unregistered": tbd}
    if tbd:
        return {"status": "BLOCKED_PENDING_AXIS_REGISTRATION", "primary_blocker": tbd[0], "unregistered": tbd}
    return {"status": "READY_TO_BUILD", "primary_blocker": None, "unregistered": []}


def point_seed(point_key: dict) -> int:
    """Deterministic, order-independent seed for one grid point (all axis values + species + scattering)."""
    if not isinstance(point_key, dict) or not point_key:
        raise ValueError("point_seed: point_key must be a non-empty dict of axis values")
    canon = json.dumps(point_key, sort_keys=True, separators=(",", ":"), default=str)
    return int(hashlib.sha256(canon.encode()).hexdigest()[:16], 16) % (2 ** 63)


def build_intake_surface_v2(*_args, **_kwargs):
    """Refuses while any required axis is unregistered (fail closed). There is no partial or provisional v2 build and
    no default angular range: in particular v1's 0-5 deg is never substituted for the AOCS envelope (A9.13 S6.2)."""
    st = v2_build_status()
    if st["status"] != "READY_TO_BUILD":
        raise IntakeSurfaceV2Blocked(
            f"intake surface v2 build refused: {st['status']} - {st['primary_blocker']}; unregistered: "
            f"{st['unregistered']}. Register the spacecraft/AOCS relative-wind pointing envelope (A9.13 S6.2) and the "
            f"remaining axes first; intake_surface_v1 stays the frozen reference meanwhile.")
    raise NotImplementedError("intake surface v2: all axes registered, but the build itself is not implemented yet; "
                              "implement it against this specification as a separate controlled change (rule 1)")
