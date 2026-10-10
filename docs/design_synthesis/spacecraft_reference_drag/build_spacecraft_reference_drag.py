#!/usr/bin/env python3
"""Reference spacecraft drag basis (owner decision A9.13 S6.18 / OQ-F78-04): REFERENCE/PARAMETRIC, never the flight
spacecraft. Builds spacecraft_reference_drag_v1.json from abep_sim/spacecraft_reference_drag.py and generates
SPACECRAFT_REFERENCE_DRAG.md from that JSON. No atmosphere is evaluated (rho, v_rel are caller inputs); the build is
pure data and takes well under a second.

Usage:
  python docs/design_synthesis/spacecraft_reference_drag/build_spacecraft_reference_drag.py          # write outputs
  python docs/design_synthesis/spacecraft_reference_drag/build_spacecraft_reference_drag.py --check  # exit 1 unless
                                                                                                     # reproduced
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim import spacecraft_reference_drag as SRD  # noqa: E402

OUT_DIR = REPO / "docs/design_synthesis/spacecraft_reference_drag"
JSON_NAME = "spacecraft_reference_drag_v1.json"
MD_NAME = "SPACECRAFT_REFERENCE_DRAG.md"
MODULE_REL = "abep_sim/spacecraft_reference_drag.py"


def _sha(rel: str) -> str:
    p = REPO / rel
    if not p.exists():
        raise FileNotFoundError(f"pinned input missing: {rel}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_decisions() -> None:
    for d in SRD.DECISIONS:
        for key_path, key_sha in (("path", "md_sha256"), ("json_path", "json_sha256")):
            got = _sha(d[key_path])
            if got != d[key_sha]:
                raise RuntimeError(f"decision record changed: {d[key_path]} sha256 {got} != {d[key_sha]}")


def build_json() -> dict:
    verify_decisions()
    doc = SRD.build_document()
    doc["provenance"] = {"builder": "docs/design_synthesis/spacecraft_reference_drag/build_spacecraft_reference_drag.py",
                         "module": MODULE_REL, "module_sha256": _sha(MODULE_REL)}
    return doc


def _fmt(v):
    if v is None:
        return "TBD"
    if isinstance(v, list):
        return "–".join(_fmt(x) for x in v) if len(v) == 2 and all(isinstance(x, (int, float)) for x in v) \
            else ", ".join(_fmt(x) for x in v)
    if isinstance(v, float):
        return f"{v:g}"
    return str(v).replace("|", "/")


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# Reference spacecraft drag basis (REFERENCE/PARAMETRIC — not the flight spacecraft)")
    a("")
    a(f"Generated from `{JSON_NAME}` by `build_spacecraft_reference_drag.py`; do not edit by hand. "
      f"Status **{doc['status']}**, freeze status **{doc['freeze_status']}**.")
    a("")
    a("## Owner basis")
    for d in doc["decisions"]:
        q = "; ".join(d["question_ids"]) if d["question_ids"] else "(no drag question)"
        a(f"- `{d['path']}` (json `{d['json_path']}` sha256 `{d['json_sha256']}`): {q}. {d['used_for']}.")
    a("")
    a("S6.18: sourced geometry is for interim parametric studies only and is labelled `REFERENCE/PARAMETRIC`. AG-13 "
      "closure needs the host-spacecraft ICD; until then `D_spacecraft` and `T - D` remain `NOT_EVALUATED` for freeze "
      "purposes. S6.15: `T_available(state) - D_spacecraft(state) >= 0` statewise, thrust and drag at the same state.")
    a("")
    a("## Scope")
    for k, v in doc["scope"].items():
        a(f"- **{k}**: {v}")
    b = doc["rfp_thrust_band"]
    a(f"- **thrust band**: {b['min_mN']:g}–{b['max_mN']:g} mN, `{b['requirement_status']}`. {b['note']}")
    a("")
    a("## Declared reference cases (same-source (A_ref, C_D) pairs only)")
    a("")
    a("| case | record | C_D | A_ref (m²) | C_D·A (m²) | A_ref scope | q at 12 mN (Pa) | q at 25 mN (Pa) | level | type |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for r in doc["density_free_table"]:
        a(f"| {r['case_id']} | {r['record_id']} | {r['cd']:g} | {r['a_ref_m2']:g} | {r['cd_a_m2']:g} | "
          f"{r['a_ref_scope']} | {r['q_at_12mN_Pa']:.6g} | {r['q_at_25mN_Pa']:.6g} | {r['evidence_level']} | "
          f"{r['quantity_type']} |")
    a("")
    a("`q = ½ρv²` at which the reference term alone equals a band edge (intake term excluded). This is density-free; "
      "statewise values need the orbit-resolved atmosphere (caller input).")
    a("")
    a("## Reference records")
    a("")
    a("| id | name | altitude (km) | mass (kg) | frontal area (m²) | C_D | C_D basis | A_ref scope |")
    a("|---|---|---|---|---|---|---|---|")
    for r in doc["records"]:
        a(f"| {r['id']} | {r['name']} | {_fmt(r['altitude_km']['value'])} | {_fmt(r['mass_kg']['value'])} | "
          f"{_fmt(r['frontal_area_m2']['value'])} | {_fmt(r['cd']['value'])} | "
          f"{_fmt(r['cd_model_basis']['value'])} | {_fmt(r['a_ref_scope'])} |")
    a("")
    a("Per-value source, evidence level, quantity type and verbatim notes are in the JSON (`records[*].*`).")
    a("")
    a("## Sources read")
    for k, s in doc["sources"].items():
        a(f"- **{k}** — {s['citation']}. <{s['url']}>. Access: {s['access']}. Retrieved sha256: "
          f"`{s['retrieved_sha256'] or 'n/a'}`. {s['verbatim_check']}.")
    a("")
    a("## Cited but not accessed")
    for n in doc["not_accessed"]:
        a(f"- {n['ref']} — {n['why']}; {n['consequence']}.")
    a("")
    a("## Findings")
    for f in doc["findings"]:
        a(f"- **{f['id']}** {f['finding']}. Action: {f['action']}.")
    a("")
    a("## Open items")
    for o in doc["open_items"]:
        a(f"- {o}")
    a("")
    return "\n".join(L)


def render_json(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    doc = build_json()
    outs = {OUT_DIR / JSON_NAME: render_json(doc), OUT_DIR / MD_NAME: render_md(doc)}
    if args.check:
        bad = [p.name for p, txt in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != txt]
        if bad:
            print("CHECK FAILED (not reproduced): " + ", ".join(bad))
            return 1
        print("OK: spacecraft reference drag outputs reproduced")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p, txt in outs.items():
        p.write_text(txt, encoding="utf-8")
        print(f"wrote {p.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
