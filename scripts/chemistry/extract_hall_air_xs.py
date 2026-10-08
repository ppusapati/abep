"""NP-HALL-CHEM-AIR build plan: extract the cross-section representations of the SONG2026 O2 tables for the Hall AIR set.

Reads (never edits) the immutable v0 DRAFT builder docs/chemistry/o_o2/v0/build_tables_song2026.py, whose module constants
hold the transcription of SONG2026 Tables V-VIII (accepted manuscript, sha256 32d163a3...; version of record NOT accessed),
calls its specs() and writes, for each table the Hall set uses, the exact (E [eV], sigma [m^2]) points that builder passes
to abep_sim/rate_tables.write_hallthruster_table, with the header, tail and a Hall-specific .source text. Nothing is
transcribed, fitted or computed here: the points are the v0 builder's arrays, serialized with shortest round-trip floats.

The Rust example `cargo run -p abep-chem --example build_hall_air_tables --locked` renders the HallThruster.jl tables from
these files with the admitted integrator (abep_chem::reference, contract C-ABEP_SIM_RATE_TABLES_PY); its test requires the
rendered .dat bytes to equal the v0 tables (sha256 recorded here), so the representation is checked twice.

Usage (repository root):
  python3 scripts/chemistry/extract_hall_air_xs.py            # write the xs files
  python3 scripts/chemistry/extract_hall_air_xs.py --check    # regenerate in memory, byte-compare (exit 1 on a difference)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
ROOT =os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
V0 = os.path.join(ROOT, "docs", "chemistry", "o_o2", "v0")
V0_BUILDER_SHA256 = "c9ff001987371f4ca2ab5e79a0d097c770a846da5ea71dae358832734078d3ac"
PREREG = "docs/rust_migration/new_physics/NP-HALL-CHEM-AIR/prereg_v1.json"
PREREG_LOCK_SHA256 = "1884e42ff98ee07a634500ce338eef9dc3749bf4e5c053b058aec9b764674518"
AIR = "hallthruster_bridge/propellants_air"
BOUND = "hallthruster_bridge/audit_air/bound_tables"

SONG = ("Song, Cho, Karwasz, Kokoouline, Tennyson & Bartschat, J. Phys. Chem. Ref. Data 55, 013102 (2026), "
        "doi:10.1063/5.0287254, accepted manuscript (UCL Discovery, sha256 32d163a3...), version of record NOT accessed "
        "(NP-HALL-CHEM-AIR status IN_REPO_PENDING_VERSION_OF_RECORD, OQ-HA-01)")

# v0 file -> (Hall file, output directory, process id, role, target gas, Hall-specific .source lead)
TABLES = {
    "ionization_O2_song2026.dat": (AIR, "HA-O2-ION-01", "NOMINAL", "O2", "e + O2 -> O2(+) + 2e"),
    "dissociative_ionization_O2_upper_song2026.dat": (AIR, "HA-O2-DI-01", "NOMINAL (upper member of the O+ / O2^2+ pair)", "O2",
                                                      "e + O2 -> O(+) + O + 2e (upper)"),
    "dissociative_ionization_O2_lower_song2026.dat": (AIR, "HA-O2-DI-01", "VARIANT (lower member of the O+ / O2^2+ pair)", "O2",
                                                      "e + O2 -> O(+) + O + 2e (lower)"),
    "dissociation_O2_song2026.dat": (AIR, "HA-O2-DIS-01", "NOMINAL (Cosby-only lower member: dissociation below 13.5 eV MISSING)",
                                     "O2", "e + O2 -> O + O + e"),
    "elastic_O2_song2026.dat": (AIR, "HA-O2-EL-01", "NOMINAL", "O2", "e + O2 elastic momentum transfer"),
    "dissociative_ionization_O2_to_O_Z2plus_song2026.dat": (BOUND, "HA-O2-DI-02", "AUDIT BOUND TABLE (not configured: L-06)", "O2",
                                                            "e + O2 -> O(2+) + O + 3e"),
    "attachment_O2_song2026.dat": (BOUND, "HA-O2-ATT-01", "AUDIT BOUND TABLE (not representable: L-04, L-05)", "O2",
                                   "e + O2 -> O(-) + O (dissociative attachment)"),
}


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_v0():
    path = os.path.join(V0, "build_tables_song2026.py")
    with open(path, "rb") as f:
        got = sha256(f.read())
    if got != V0_BUILDER_SHA256:
        raise SystemExit(f"v0 builder sha256 {got} != pinned {V0_BUILDER_SHA256}: the transcription changed; re-audit")
    sys.path.insert(0, V0)
    import build_tables_song2026 as b  # noqa: E402  (read-only import; its __main__ does not run)
    return b


def hall_source(spec, process, role, lead) -> str:
    m = spec["meta"]
    return (f"NP-HALL-CHEM-AIR {process} ({role}). {lead}. Cross section: {SONG}; {m['source_location']}; stated "
            f"uncertainty {m['stated_uncertainty']}. Points = the v0 DRAFT transcription (docs/chemistry/o_o2/v0/"
            f"build_tables_song2026.py, sha256 {V0_BUILDER_SHA256[:12]}...), extracted unchanged by "
            f"scripts/chemistry/extract_hall_air_xs.py. Choices: {'; '.join(m.get('choices', [])) or 'see the v0 manifest'}. "
            f"Header {spec['header_energy_eV']} eV: {m['header_basis']}. Maxwellian-integrated by the admitted Rust port of "
            f"abep_sim/rate_tables.py (abep_chem::reference; crates/abep-chem/examples/build_hall_air_tables.rs); byte-"
            f"identical to the v0 table. Energy column = mean electron energy 3/2 Te. Evidence level 4 (docs/EVIDENCE.md); "
            f"quantity type: {m['quantity_type']}.")


def render(b) -> dict[str, bytes]:
    out = {}
    manifest = json.load(open(os.path.join(V0, "manifest_song2026_v0.json"), encoding="utf-8"))
    v0_sha = {os.path.basename(t["file"]): t["sha256"] for t in manifest["tables"]}
    for spec in b.specs():
        name = spec["file"]
        if name not in TABLES:
            continue
        outdir, process, role, target, lead = TABLES[name]
        E = [float(x) for x in spec["E_eV"]]
        s = [float(x) for x in spec["sigma_m2"]]
        m = spec["meta"]
        doc = {
            "schema": "hall_air_xs_v1",
            "contract": "NP-HALL-CHEM-AIR",
            "prereg": PREREG,
            "prereg_lock_sha256": PREREG_LOCK_SHA256,
            "process": process,
            "role": role,
            "target": target,
            "reaction": m["reaction"],
            "table": f"{outdir}/{name}",
            "v0_table": f"docs/chemistry/o_o2/v0/tables/{name}",
            "v0_table_sha256": v0_sha[name],
            "header_label": spec["header_label"],
            "threshold_eV": float(spec["header_energy_eV"]),
            "tail": spec["tail"],
            "eps_max_eV": 300.0,
            "source_text": hall_source(spec, process, role, lead),
            "provenance": {
                "citation": SONG,
                "source_location": m["source_location"],
                "transformation_chain": m["transformation_chain"],
                "extraction": "v0 builder specs() arrays, unchanged (shortest round-trip floats)",
                "v0_builder": "docs/chemistry/o_o2/v0/build_tables_song2026.py",
                "v0_builder_sha256": V0_BUILDER_SHA256,
                "extracted_by": "scripts/chemistry/extract_hall_air_xs.py",
            },
            "stated_uncertainty": m["stated_uncertainty"],
            "evidence_level": m["evidence_level"],
            "quantity_type": m["quantity_type"],
            "header_basis": m["header_basis"],
            "units": {"E": "eV", "sigma": "m^2"},
            "n_points": len(E),
            "points": [[e, x] for e, x in zip(E, s)],
        }
        text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
        out[f"{outdir}/xs/{name[:-4]}.json"] = text.encode("utf-8")
    missing = sorted(set(f"{d}/xs/{n[:-4]}.json" for n, (d, *_r) in TABLES.items()) - set(out))
    if missing:
        raise SystemExit(f"v0 specs() did not produce {missing}")
    return out


def main(argv) -> int:
    b = load_v0()
    files = render(b)
    if "--check" in argv:
        bad = []
        for rel, data in sorted(files.items()):
            p = os.path.join(ROOT, rel)
            if not os.path.isfile(p) or open(p, "rb").read() != data:
                bad.append(rel)
        for rel in bad:
            print("MISMATCH", rel)
        print("check:", "OK" if not bad else f"FAILED ({len(bad)} file(s))")
        return 1 if bad else 0
    for rel, data in sorted(files.items()):
        p = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        print("wrote", rel, sha256(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
