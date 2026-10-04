"""A9.24 item 11: the committed F1 evidence-archive manifest carries every required repository field, the upload is
recorded as authorized but not yet authoritative, and `verify-download` fails closed on a copy that does not match.
Run: python -m pytest -q tests/test_f1_archive_a9_24.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "evidence" / "f1_archive.py"
MANIFEST = REPO / "docs" / "evidence_archives" / "f1_intake" / "F1_INTAKE_SYNTHESIS_v1_405296e.manifest.json"


@pytest.fixture(scope="module")
def fa():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("f1_archive_t", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def man():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_required_fields_present(fa, man):
    got = fa.a924_checklist(man)
    assert [x["field"] for x in got] == [f for f, _ in fa.A924_REQUIRED]
    assert all(x["status"] == "PRESENT" for x in got)
    assert man["a9_24_item_11_checklist"] == got
    assert len(man["files"]) == 2 and all(len(f["sha256"]) == 64 for f in man["files"])
    assert len(man["model_set"]["sha256"]) == 64 and man["model_set"]["model_set_id"].startswith("NOT_REGISTERED")


def test_checklist_fails_closed(fa, man):
    bad = json.loads(json.dumps(man))
    del bad["model_set"]["sha256"]
    bad["files"][0]["sha256"] = ""
    st = {x["field"]: x["status"] for x in fa.a924_checklist(bad)}
    assert st["model-set hash"] == "MISSING" and st["per-file hashes"] == "MISSING"


def test_upload_authorized_not_authoritative(fa, man):
    pref = man["storage"]["preferred"]
    assert pref["status"].startswith("AUTHORIZED_TO_UPLOAD") and pref["authoritative"] is False
    assert pref["tag"] == "evidence-f1-intake-synthesis-v1-405296e"
    assert pref["download_url"].endswith(f"/releases/download/{pref['tag']}/{man['archive']['file_name']}")
    ua = man["upload_authorization"]
    assert ua["item"] == 11 and ua["md_sha256"] == fa.A924["md_sha256"]
    md = fa._norm((REPO / ua["md"]).read_text(encoding="utf-8"))
    assert all(fa._norm(q) in md for q in ua["quotes"])
    assert (REPO / fa.UPLOAD_STEPS_REL).is_file()
    # archive identity unchanged by the A9.24 fields
    assert man["archive"]["sha256"] == "c29623c08099c688584439b881c07c7a59b14fba3645642e652e3a2c7ce04dd2"
    assert man["archive"]["size_bytes"] == 2011661


def test_verify_download_fails_closed(fa, tmp_path, capsys):
    import zstandard  # noqa: F401  locked (requirements-lock.txt): a missing dep fails, never adds a skip (rule 9)
    f = tmp_path / "F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst"
    f.write_bytes(b"not an archive" * 10)
    assert fa.verify_download(str(f), str(tmp_path / "rec.json")) == 1
    rec = json.loads((tmp_path / "rec.json").read_text(encoding="utf-8"))
    assert rec["result"] == "FAILED" and rec["authoritative"] is False and rec["mismatches"]
    with pytest.raises(SystemExit):
        fa.verify_download(str(tmp_path / "missing.tar.zst"))
