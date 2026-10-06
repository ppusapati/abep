"""Capture the reference spacecraft drag register as Rust data (contracts C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY and
C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG).

abep_sim/spacecraft_reference_drag.py is a register (owner decisions, sources, reference records, declared cases,
findings, open items) plus a small evaluator. The Rust crate abep-mission reads the register from
crates/abep-mission/data/spacecraft_reference_register_v1.json (sha256-pinned in abep_mission::reference_drag) and
implements the evaluator, the density-free table, the document assembly and the builder itself.

This reads the reference module (no evaluation, no rounding, no density-free table); it writes the module constants
verbatim, in their order, with Python's float / int distinction kept by json. Run in the reference environment:

    python3 scripts/rust_migration/capture_reference_drag_register.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT)
from abep_sim import spacecraft_reference_drag as SRD  # noqa: E402

MODULE_REL = "abep_sim/spacecraft_reference_drag.py"
OUT = os.path.join(ROOT, "crates", "abep-mission", "data", "spacecraft_reference_register_v1.json")


def main() -> None:
    doc = SRD.build_document()
    module_sha = hashlib.sha256(open(os.path.join(ROOT, MODULE_REL), "rb").read()).hexdigest()
    register = {k: v for k, v in doc.items() if k != "density_free_table"}
    out = {
        "schema": "abep_mission_spacecraft_reference_register_v1",
        "captured_from": {"module": MODULE_REL, "module_sha256": module_sha,
                          "script": "scripts/rust_migration/capture_reference_drag_register.py",
                          "note": "module constants verbatim (build_document() without density_free_table) plus "
                                  "INTAKE_ACCOUNTING and the a_ref_scope vocabulary; no value is computed here"},
        "document_key_order": list(doc),
        "register": register,
        "intake_accounting": list(SRD.INTAKE_ACCOUNTING),
        "a_ref_scopes": list(SRD._SCOPES),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {os.path.relpath(OUT, ROOT)} sha256 {hashlib.sha256(open(OUT, 'rb').read()).hexdigest()}")


if __name__ == "__main__":
    main()
