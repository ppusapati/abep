"""O/O2 v0 DRAFT rate tables (fo_o_o2_chemistry_v0): determinism, format, provenance, and 'unused' guarantees.

No network: the SONG2026 tables are rebuilt from the transcription in the build script; the NIST SRD 107 tables (raw
input not committed) are checked against their manifest hashes and the HallThruster.jl table format only.
"""
import glob
import importlib.util
import json
import os

import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
V0 = os.path.join(ROOT, "docs", "chemistry", "o_o2", "v0")
MANIFESTS = ["manifest_song2026_v0.json", "manifest_nist107_o_v0.json"]
EVIDENCE_TYPES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(V0, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _records():
    out = []
    for m in MANIFESTS:
        with open(os.path.join(V0, m)) as f:
            out += json.load(f)["tables"]
    return out


def _read_table(path):
    with open(path) as f:
        lines = f.read().splitlines()
    return lines[0], lines[1], [tuple(float(x) for x in l.split("\t")) for l in lines[2:]]


def test_song2026_tables_rebuild_byte_identical():
    b = _load("build_tables_song2026")
    assert b.main(["--check"]) == 0


def test_table_vii_partials_sum_to_total_within_rounding():
    b = _load("build_tables_song2026")
    assert b.table_vii_row_sums() < 0.01


def test_manifest_hashes_and_hallthruster_format():
    common = _load("o_o2_v0_common")
    recs = _records()
    assert len(recs) == 9
    for r in recs:
        p = os.path.join(V0, r["file"])
        assert common.sha256_file(p) == r["sha256"], r["file"]
        assert common.sha256_file(os.path.join(V0, r["source_file"])) == r["source_file_sha256"]
        head, cols, rows = _read_table(p)
        assert head == r["header"] and "(eV):" in head
        float(head.split(":", 1)[1])                      # HallThruster.jl reads the number after ':'
        assert cols == "Energy (eV)\tRate coefficient (m^3/s)"
        assert [e for e, _ in rows] == [float(i) for i in range(301)]
        assert rows[0][1] == 0.0 and all(k >= 0.0 for _, k in rows)


def test_every_table_is_listed_and_carries_provenance():
    recs = _records()
    files = {r["file"] for r in recs}
    on_disk = {os.path.relpath(p, V0) for p in glob.glob(os.path.join(V0, "tables", "*.dat"))}
    assert on_disk == files
    for r in recs:
        assert r["status"] == "DRAFT_UNUSED"
        assert r["sources"] and all(s.get("doi") for s in r["sources"])
        assert r["evidence_level"] == 4
        assert any(t in r["quantity_type"] for t in EVIDENCE_TYPES)
        for key in ("stated_uncertainty", "transformation_chain", "header_basis", "extraction_method", "reaction",
                    "cross_section_energy_range_eV", "tail_share_hold_vs_zero", "milestones_supported"):
            assert r.get(key), (r["file"], key)
        assert r["draft_validity_limit_mean_energy_eV"] <= 45.0
        assert r["rfp_thresholds_used"] == "none"
    status = json.load(open(os.path.join(V0, "channel_status_v0.json")))
    listed = {f for b in status["built_tables"] for f in b["files"]}
    assert listed == files


def test_dissociation_support_limit_and_attachment_zero_tail():
    recs = {r["file"]: r for r in _records()}
    d = recs["tables/dissociation_O2_song2026.dat"]
    assert 45.0 <= d["source_support_limit_mean_energy_eV"] < 100.0     # Table VI ends at 198.5 eV
    a = recs["tables/attachment_O2_song2026.dat"]
    assert a["tail_beyond_last_point"] == "zero" and a["source_support_limit_mean_energy_eV"] is None
    _, _, rows = _read_table(os.path.join(V0, a["file"]))
    assert rows[-1][1] < rows[10][1]                                     # resonance does not plateau


def test_tables_are_unused_by_solver_configs_and_code():
    names = [os.path.basename(r["file"]) for r in _records()]
    scan = glob.glob(os.path.join(ROOT, "hallthruster_bridge", "**", "*.toml"), recursive=True) + \
        glob.glob(os.path.join(ROOT, "abep_sim", "*.py"))
    for p in scan:
        text = open(p, encoding="utf-8", errors="ignore").read()
        assert "o_o2/v0" not in text, p
        for n in names:
            assert n not in text, (p, n)


def test_missing_spec_field_raises_no_defaults(tmp_path):
    common = _load("o_o2_v0_common")
    spec = {"file": "x.dat", "E_eV": [1.0, 2.0], "sigma_m2": [0.0, 1e-20], "header_label": "Ionization energy",
            "tail": "hold", "source_text": "t", "meta": {}}                         # header_energy_eV missing
    with pytest.raises(KeyError):
        common.build_table(spec, str(tmp_path))


def test_nist_loader_rejects_changed_source(tmp_path):
    b = _load("build_tables_nist107_o")
    p = tmp_path / "raw.txt"
    p.write_bytes(b"T (eV)\tTotal{kim02}\t{thomp95}\n14.0\t0.1\t0.1\n")
    with pytest.raises(SystemExit):
        b.load_raw(str(p))
