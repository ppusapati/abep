#!/usr/bin/env python3
"""Deterministic sha256 pins for the W5 held-out Hall-transport validation pre-registration DRAFT.

Usage (from the repository root):
    python docs/validation/hall_transport_v2_prereg/pin_inputs.py --check    # verify recorded pins
    python docs/validation/hall_transport_v2_prereg/pin_inputs.py --print    # print current digests

The script never rewrites the draft: a changed pin means the draft must be re-reviewed by a person before any lock.
It reads only repository files listed in the draft's ``pinned_inputs.files``; it runs no simulation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DRAFT = HERE / "hall_transport_v2_prereg_DRAFT.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_draft() -> dict:
    with open(DRAFT, encoding="utf-8") as f:
        return json.load(f)


def check_pins(draft: dict | None = None) -> list[str]:
    """Return a list of problems (empty when every pinned file exists and matches)."""
    draft = draft if draft is not None else load_draft()
    problems = []
    for rel, expected in draft["pinned_inputs"]["files"].items():
        p = REPO / rel
        if not p.is_file():
            problems.append(f"missing: {rel}")
            continue
        got = sha256(p)
        if got != expected:
            problems.append(f"sha256 mismatch: {rel} recorded {expected} now {got}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--print", action="store_true")
    a = ap.parse_args(argv)
    draft = load_draft()
    if a.print:
        for rel in draft["pinned_inputs"]["files"]:
            p = REPO / rel
            print(f"{sha256(p) if p.is_file() else 'MISSING':64s}  {rel}")
        return 0
    problems = check_pins(draft)
    for p in problems:
        print(p, file=sys.stderr)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
