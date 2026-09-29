"""golden_parallel_v1 reproduces (software regression only; not physical validation). Existing goldens untouched."""
import json

from abep_sim.golden_parallel import GOLDEN_FILE, check


def test_golden_parallel_reproduces():
    assert check() == []


def test_golden_parallel_declares_it_is_not_validation():
    d = json.load(open(GOLDEN_FILE))
    assert "NOT physical validation" in d["purpose"]
