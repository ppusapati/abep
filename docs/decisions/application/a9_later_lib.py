"""Owner decisions A9.17 .. A9.22 (after the A9.16 step-1 set): pins, item keys and verbatim excerpts.

Kept separate from a9_16_lib on purpose: a9_16_lib.DECISIONS / pins() feed the pins of every A9.16 integration builder
(H-1, F9, F6, RVM, M16, state v5, matrix); adding the later decisions there would silently re-pin all of them. This
module is read by the owner-question state v5 builder, the M16 v4 builder and the A9.16 application matrix.

  A9.17  data artifacts (winds / orbit / data size / sputter / RFP registration / dedicated performance baseline)
  A9.18  golden design point + dedicated-baseline rerun
  A9.19  flight architecture: one Hall + one RF/ICP neutralizer, two supply modes, Xe contingency / emergency, no hollow
         cathode (amends A9.15 on the ROLE of Xe; A9.14 S8.33 MPQ-01 / S8.17 OQ-A907-07; A9 C1 CONTROL_FALLBACK)
  A9.20  C1 = ground-only laboratory reference (never flight hardware, never in the flight budgets)
  A9.21  open items + hardware programme (AL-08 provisional, H2-6 frozen + CI, ICP go / no-go before LOCK-1 without
         numbers, bid close, programme order, external inputs stay TBD, RFQ dispatch by owner / procurement)
  A9.22  layer separation (requirements / configuration / physics / assessment), items G1-G9; G3 closes AG-15 and
         freezes the RFP-derived requirements snapshot (applied by the AG-15 closure lane; the other items are applied
         by their own governed migrations)

Every decision file is immutable: the companion json and the verbatim md are pinned by sha256 and the md path / sha
recorded inside the json must agree (fail closed). Excerpts are cut verbatim from the pinned md (the md governs; json
text is a recorder digest). stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEC = "docs/decisions"

# key -> (json, json sha256, md, md sha256, label)
DECISIONS = {
    "A9.17": (f"{DEC}/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json",
              "9fd77c95c2f3142bb3e2faf68145e1225a29b307d22f86bf93a8cd562914c3ad",
              f"{DEC}/OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md",
              "540212c0c8862528e549555244f0fd39f8f9c9272f84dfb450bfef9dc54eba13", "data artifacts / RFP / performance"),
    "A9.18": (f"{DEC}/OD_2026_10_01_A9_18_golden_and_baseline_owner_decisions.json",
              "7c170e1000ae039c1f032ccf38bcacf2c59825d5dab26b4d98658a96914a8c3a",
              f"{DEC}/OD_2026_10_01_A9_18_GOLDEN_AND_BASELINE_OWNER_DECISIONS.md",
              "b26b739244d87fb98001936688650c8b0cf307abeddb2ee4c494ff4f06c5951d", "golden + baseline rerun"),
    "A9.19": (f"{DEC}/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
              "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
              f"{DEC}/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md",
              "d3eae1d65f9b679a8538ce4a7c701a40a3f5d3b07d72baae944b685256931749",
              "flight architecture / Xe contingency role"),
    "A9.20": (f"{DEC}/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
              "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
              f"{DEC}/OD_2026_10_01_A9_20_C1_GROUND_ONLY_OWNER_DECISION.md",
              "2b90a7a7f851ac571791ea6ba2fbafac8cf69a086a4a3724e2f66196b6b4d60c", "C1 ground-only reference"),
    "A9.21": (f"{DEC}/OD_2026_10_02_A9_21_open_items_and_hardware_programme_owner_decisions.json",
              "78766d3adaaa6d38730ce82607a1cd0a03ae34186c911d4189e2fd9251db6549",
              f"{DEC}/OD_2026_10_02_A9_21_OPEN_ITEMS_AND_HARDWARE_PROGRAMME_OWNER_DECISIONS.md",
              "01f7796aa2ae03d7bc0319b191f004e0a1ba0214c2c982f34554ca52cf531440", "open items + hardware programme"),
    "A9.22": (f"{DEC}/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json",
              "245307aca27b8151d0ef31a6e92f932a95920e604847694481cba6731835dc49",
              f"{DEC}/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md",
              "749999db6926a2cdda85c7aab7677410b290df11fe4a7bac903a8a8fd6fcfc77", "layer separation G1-G9"),
}
_DECISION_ITEMS = ("A9.17", "A9.18", "A9.21", "A9.22")   # records whose items are the keys of 'decisions'
ORDER = tuple(DECISIONS)
FLIGHT_CONFIGURATION = "hall_icp_neutralizer"
GROUND_REFERENCE = "hall_c1_reference"
C1_ROLE = "GROUND_ONLY_LAB_REFERENCE"
_CODE = re.compile(r"^([A-Z0-9][A-Z0-9_]{5,})(?![a-z])")


class LaterDecisionError(SystemExit):
    pass


def sha256_file(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _norm(s: str) -> str:
    return " ".join(s.split())


def _load(decisions=None) -> dict:
    out = {}
    for key, (jp, jsha, mp, msha, label) in (decisions or DECISIONS).items():
        got = sha256_file(jp)
        if got != jsha:
            raise LaterDecisionError(f"{key}: decision json {jp} sha256 {got} != pinned {jsha} (decision files are "
                                     "immutable)")
        doc = json.loads((ROOT / jp).read_text(encoding="utf-8"))
        if doc.get("decided_by") != "owner":
            raise LaterDecisionError(f"{key}: {jp} is not an owner decision record")
        if doc["verbatim"]["path"] != mp or doc["verbatim"]["sha256"] != msha:
            raise LaterDecisionError(f"{key}: verbatim record in json {doc['verbatim']} != pinned ({mp}, {msha})")
        got = sha256_file(mp)
        if got != msha:
            raise LaterDecisionError(f"{key}: verbatim {mp} sha256 {got} != pinned {msha}")
        md = (ROOT / mp).read_text(encoding="utf-8")
        out[key] = {"json": jp, "json_sha256": jsha, "md": mp, "md_sha256": msha, "label": label, "doc": doc,
                    "md_text": md, "body": md.split("\n---\n", 1)[1].strip()}
    return out


LOADED = _load()


def pins() -> list:
    rows = []
    for key in ORDER:
        d = LOADED[key]
        rows.append({"key": f"{key}_json", "path": d["json"], "sha256": d["json_sha256"]})
        rows.append({"key": f"{key}_md", "path": d["md"], "sha256": d["md_sha256"]})
    return rows


def item_keys(key: str) -> list:
    """The decision items of one record (one application-matrix entry each)."""
    doc = LOADED[key]["doc"]
    if key in _DECISION_ITEMS:
        return list(doc["decisions"])
    if key == "A9.19":
        return ["architecture", "xenon_role"] + [f"amends/{k}" for k in doc["amends"]] + ["owner_request"]
    if key == "A9.20":
        return ["answer"]
    raise LaterDecisionError(f"unknown later decision {key}")


def pointer(key: str, item: str) -> str:
    doc = LOADED[key]["doc"]
    if key in _DECISION_ITEMS:
        if item not in doc["decisions"]:
            raise LaterDecisionError(f"{key}: no decision item {item}")
        return f"{LOADED[key]['json']}#/decisions/{item}"
    if item not in item_keys(key):
        raise LaterDecisionError(f"{key}: no decision item {item}")
    return f"{LOADED[key]['json']}#/{item}"


def digest(key: str, item: str):
    """The json (recorder digest) value at the item pointer."""
    doc = LOADED[key]["doc"]
    if key in _DECISION_ITEMS:
        return doc["decisions"][item]
    if item.startswith("amends/"):
        return doc["amends"][item.split("/", 1)[1]]
    return doc[item]


def decision_code(key: str, item: str):
    """The owner decision code of an item, or None when the record carries none for it."""
    doc = LOADED[key]["doc"]
    if key in ("A9.17", "A9.18"):
        return doc["decisions"][item]["answer"]
    if key in ("A9.19", "A9.20"):
        return doc["decision"]
    v = doc["decisions"][item]
    m = _CODE.match(v) if isinstance(v, str) else None
    return m.group(1) if m else None


def verbatim(key: str, text: str) -> str:
    """Return `text` after checking it occurs verbatim (whitespace-normalized) in the pinned md body."""
    if not _norm(text):
        raise LaterDecisionError(f"{key}: empty excerpt (a verbatim excerpt must carry text)")
    if _norm(text) not in _norm(LOADED[key]["body"]):
        raise LaterDecisionError(f"{key}: excerpt not found verbatim in {LOADED[key]['md']}: {text[:80]!r}")
    return text


def block(key: str, start: str, through: str = "Decision:", extra: int = 0) -> str:
    """Verbatim block of the md body: the line starting with `start` through the first later line starting with
    `through` (inclusive; the start line alone when none follows before the next numbered item), plus `extra` lines."""
    lines = LOADED[key]["body"].splitlines()
    hits = [i for i, ln in enumerate(lines) if ln.startswith(start)]
    if len(hits) != 1:
        raise LaterDecisionError(f"{key}: block start {start!r} found {len(hits)} times")
    i = hits[0]
    j = i
    for k in range(i + 1, len(lines)):
        if re.match(r"^\d+\.\s", lines[k]) or not lines[k].strip():
            break
        if lines[k].startswith(through):
            j = k
            break
    return "\n".join(ln.rstrip() for ln in lines[i:j + 1 + extra]).strip()


def body(key: str) -> str:
    """Whole verbatim body (A9.19 / A9.20 are a few lines)."""
    return LOADED[key]["body"]


def header_text(key: str, start: str, end: str) -> str:
    """Recorder context from the md header (above the '---'; e.g. the A9.20 question and the options offered), from
    `start` through `end` inclusive (whitespace-normalized)."""
    text = _norm(LOADED[key]["md_text"].split("\n---\n", 1)[0])
    i = text.find(start)
    j = text.find(end, i + 1) if i >= 0 else -1
    if i < 0 or j < 0:
        raise LaterDecisionError(f"{key}: header text {start!r} .. {end!r} not found")
    return text[i:j + len(end)]


def cite(key: str, item: str | None = None) -> str:
    d = LOADED[key]
    s = f"{key}{' ' + item if item else ''} ({d['json']} sha256 {d['json_sha256']}; verbatim {d['md']} sha256 " \
        f"{d['md_sha256']})"
    return s


def record(key: str, item: str, relation: str, excerpt: str, scope: str) -> dict:
    """One later-owner-decision record (pointer + json / md sha256 + verbatim excerpt + recorder digest)."""
    if relation not in RELATIONS:
        raise LaterDecisionError(f"relation {relation!r} not in {sorted(RELATIONS)}")
    d = LOADED[key]
    return {"decision": key, "item": item, "relation": relation, "decision_code": decision_code(key, item),
            "pointer": pointer(key, item), "decision_json": d["json"], "decision_json_sha256": d["json_sha256"],
            "decision_md": d["md"], "decision_md_sha256": d["md_sha256"], "verbatim_excerpt": verbatim(key, excerpt),
            "recorder_digest": digest(key, item), "scope": scope}


RELATIONS = {
    "SUPERSEDES": "the later decision replaces the earlier answer (the earlier text is history)",
    "AMENDS": "the later decision amends the earlier answer within the named scope; the rest of the answer stands",
    "ANSWERS": "the later decision answers a question that had no owner answer (in the named scope)",
    "CONFIRMS": "the later decision confirms / sequences the earlier answer; nothing in it changes",
    "INPUT_STAYS_TBD": "the later decision states that the external input the earlier answer requires cannot be "
                       "supplied from current evidence and stays TBD (no code default as mission truth)",
    "PERFORMS_OWNER_ACT": "the later decision performs an act the earlier answer reserved to the owner (e.g. closing a "
                          "gate on recorded evidence, A9.22 G3 closing AG-15); the earlier answer stands and the row "
                          "status is unchanged",
}
