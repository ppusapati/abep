"""Exit status of `python -m abep_sim.golden check` (owner decision 2026-09-27; CI failure signalling only).

* unchanged tree   -> exit 0, last output line "OK";
* moved golden     -> exit 1, one line per deviation.

The perturbed case never touches the committed abep_sim/data/golden_v2.json (A9.18; golden_v1.json is history): it writes a COPY with one value changed to
pytest's tmp_path and, inside a subprocess, points the module attribute `GOLDEN_FILE` at that copy before executing the
module's own `if __name__ == "__main__":` block (read verbatim from abep_sim/golden.py). No production knob is added.
To keep CPU low that subprocess also restricts `CASES` to the cheap "atmosphere" case; the full CLI path is exercised by
the unchanged-tree test. Both tests assert the committed golden file is byte-identical before and after.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "abep_sim", "data", "golden_v2.json")     # A9.18: golden.GOLDEN_FILE (v1 is history)


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def test_golden_check_unchanged_tree_exits_zero():
    before = _sha(GOLDEN)
    r = subprocess.run([sys.executable, "-m", "abep_sim.golden", "check"], cwd=ROOT, env=_env(),
                       capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "OK"
    assert _sha(GOLDEN) == before


def test_golden_check_perturbed_copy_exits_nonzero(tmp_path):
    before = _sha(GOLDEN)
    with open(GOLDEN) as f:
        data = json.load(f)
    ref = data["cases"]["atmosphere"]["180_high"]["T"]
    data["cases"]["atmosphere"]["180_high"]["T"] = ref * 1.01          # one value moved by +1 %
    perturbed = tmp_path / "golden_perturbed.json"
    perturbed.write_text(json.dumps(data))

    code = textwrap.dedent(f"""
        import abep_sim.golden as g
        src = open(g.__file__).read()
        i = src.index('if __name__ == "__main__":')
        g.GOLDEN_FILE = {str(perturbed)!r}
        g.CASES = {{"atmosphere": g.CASES["atmosphere"]}}
        ns = vars(g); ns["__name__"] = "__main__"
        import sys; sys.argv = ["abep_sim.golden", "check"]
        exec(compile(src[i:], g.__file__, "exec"), ns)
    """)
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=_env(), capture_output=True, text=True, timeout=600)
    assert r.returncode == 1, r.stdout + r.stderr
    lines = r.stdout.strip().splitlines()
    assert "OK" not in lines
    assert any(l.startswith("atmosphere/180_high/T:") and repr(ref * 1.01) in l for l in lines), r.stdout
    assert _sha(GOLDEN) == before
