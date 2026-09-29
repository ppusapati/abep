"""RF registry: append-only, hash-locked, owner admission, withdrawal, tamper detection."""
import json
import os

import pytest

from abep_sim import rf_registry as reg
from abep_sim.mass_bom import validate_against_schema
from tests.parallel_fixtures import synthetic_rf_map

SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                     "schemas/parallel_architecture/rf_registry_v1.schema.json")))


def setup(tmp_path):
    root = str(tmp_path)
    synthetic_rf_map(os.path.join(root, "map.json"))
    return root, os.path.join(root, "registry")


def test_register_admit_withdraw(tmp_path):
    root, rd = setup(tmp_path)
    rec = reg.register(rd, root, "map.json")
    validate_against_schema(rec, SCHEMA)
    sha = rec["map_sha256"]
    assert reg.state(rd, sha) == "REGISTERED_NOT_ADMITTED"
    with pytest.raises(reg.RFRegistryError):
        reg.register(rd, root, "map.json")
    json.dump({"decided_by": "someone", "admits_rf_map_sha256": sha}, open(os.path.join(root, "bad.json"), "w"))
    with pytest.raises(reg.RFRegistryError, match="owner"):
        reg.admit(rd, root, sha, "bad.json")
    json.dump({"decided_by": "owner", "admits_rf_map_sha256": sha}, open(os.path.join(root, "dec.json"), "w"))
    reg.admit(rd, root, sha, "dec.json")
    assert reg.verify(rd, root) == {sha: "ADMITTED"}
    reg.withdraw(rd, sha, "superseded by re-measurement")
    assert reg.state(rd, sha) == "WITHDRAWN"
    for r in reg.records(rd):
        validate_against_schema(r, SCHEMA)


def test_tamper_detection(tmp_path):
    root, rd = setup(tmp_path)
    sha = reg.register(rd, root, "map.json")["map_sha256"]
    with open(os.path.join(root, "map.json"), "a") as f:
        f.write(" ")
    with pytest.raises(reg.RFRegistryError, match="modified"):
        reg.verify(rd, root)
    p = os.path.join(rd, "records", sorted(os.listdir(os.path.join(rd, "records")))[0])
    d = json.load(open(p)); d["map_id"] = "edited"; json.dump(d, open(p, "w"))
    with pytest.raises(reg.RFRegistryError, match="record_sha256"):
        reg.records(rd)
    assert sha


def test_outside_root_refused(tmp_path):
    root, rd = setup(tmp_path)
    with pytest.raises(reg.RFRegistryError):
        reg.register(rd, root, "../outside.json")
