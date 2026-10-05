"""Reference vectors for abep_types::pyjson (Python-compatible JSON float formatter / writer; RM-R06).

Runs the CPython reference (float.__repr__, json.dumps, repr(str), str.isprintable) on a seeded set of inputs and
writes the expected outputs; the Rust tests read them and never run Python.

  float_explicit   decimal-boundary cases (10^k and neighbours, the -4 < e <= 16 fixed/exponent switch, powers of
                   two, subnormal / normal / max boundaries, integers near 2^53), every float in config/**/*.json,
                   and SEED-drawn random bit patterns and short decimals: [bits hex, repr, json.dumps]
  float_streams    SEED-drawn streams too large to commit; only their sha256 (Rust regenerates them with the same
                   splitmix64 generator and compares the digest)
  strings          SEED-drawn strings (controls, quotes, backslashes, Latin-1, BMP, astral): json.dumps with
                   ensure_ascii True / False, and repr()
  non_printable    str.isprintable() == False code-point ranges of this interpreter's unicodedata
  word             re word-character ranges (str.isalnum() or '_') of this interpreter's unicodedata
  documents        json.dumps layouts (indent 1 / None, sort_keys, separators, allow_nan) of seeded nested values

It also writes crates/abep-types/src/pyjson_unicode.rs, the str.isprintable() and re word-character tables of this
interpreter (CPython 3.11, unicodedata 14.0.0) behind abep_types::pyjson::py_isprintable (repr) and py_isword (\b).

SEED is preregistered here (committed before the vectors were generated). --seed and --out exist for development
runs only; the committed file is generated with the defaults.

Usage: python scripts/rust_migration/gen_pyjson_vectors.py            write the vectors and the Rust table
       python scripts/rust_migration/gen_pyjson_vectors.py --check    regenerate in memory, compare byte for byte
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import struct
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_REL = "crates/abep-types/tests/data/pyjson_vectors_v1.json"
TABLE_REL = "crates/abep-types/src/pyjson_unicode.rs"
SEED = 202610052                      # preregistered (lane A2, 2026-10-05)
N_RANDOM_BITS = 4000
N_RANDOM_DECIMALS = 2000
N_STREAM_BITS = 1_000_000
N_STREAM_DECIMALS = 500_000
N_STRINGS = 1500
N_DOCUMENTS = 60
M64 = (1 << 64) - 1


class SplitMix64:
    """splitmix64 (Steele, Lea, Flood 2014); the Rust tests implement the same recurrence."""

    def __init__(self, seed: int):
        self.state = seed & M64

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & M64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        return z ^ (z >> 31)

    def below(self, n: int) -> int:
        return self.next() % n


def bits_of(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def float_of(b: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", b))[0]


def decimal_draw(r: SplitMix64) -> str:
    """A short decimal literal: 1-17 significant digits, exponent -340..319, random sign (same recurrence in Rust)."""
    a, b, c = r.next(), r.next(), r.next()
    ndig = 1 + a % 17
    mant = b % (10 ** ndig)
    exp = c % 660 - 340
    sign = "-" if (a >> 63) & 1 else ""
    return f"{sign}{mant}e{exp}"


def boundary_floats() -> list[float]:
    out = []
    for k in range(-330, 311):
        for lit in (f"1e{k}", f"9.999999999999999e{k}", f"5e{k}"):
            x = float(lit)
            out += [x, math.nextafter(x, math.inf), math.nextafter(x, -math.inf)]
    for e in range(-1074, 1024):
        x = math.ldexp(1.0, e)
        out += [x, math.nextafter(x, math.inf)]
    for n in range(-40, 41):
        out += [float(2 ** 53 + n), float(10 ** 16 + n), float(10 ** 15 + n)]
    out += [0.0, -0.0, 0.1, 0.2, 0.1 + 0.2, 1 / 3, 2 / 3, 0.0001, 0.00001, 0.00012, 1e16, 1e15, 123456789.0,
            1234567890123456789.0, sys.float_info.max, sys.float_info.min, 5e-324, 2.2250738585072009e-308,
            math.pi, math.e, 26280.0, 15000.0, 1500.0, 0.75, 0.8, 0.6, 0.7, 1e-3, 1e-12, 13.56e6,
            math.inf, -math.inf, math.nan]
    return out


def config_floats() -> list[float]:
    found = []

    def walk(v):
        if isinstance(v, float):
            found.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    for p in sorted((ROOT / "config").rglob("*.json")):
        walk(json.loads(p.read_text(encoding="utf-8")))
    return found


def float_row(x: float) -> list:
    return [f"{bits_of(x):016x}", repr(x), json.dumps(x)]


def stream_digest(lines) -> str:
    h = hashlib.sha256()
    for line in lines:
        h.update(line.encode("utf-8"))
    return h.hexdigest()


def bits_stream(seed: int, n: int):
    r = SplitMix64(seed)
    for _ in range(n):
        b = r.next()
        x = float_of(b)
        yield f"{b:016x} {repr(x)} {json.dumps(x)}\n"


def decimal_stream(seed: int, n: int):
    r = SplitMix64(seed)
    for _ in range(n):
        lit = decimal_draw(r)
        x = float(lit)
        yield f"{lit} {repr(x)} {json.dumps(x)}\n"


ALPHABET_POOLS = [
    [chr(i) for i in range(0x00, 0x20)] + ["\x7f"],
    list(" \"'\\/abcXYZ019_-:{}[],"),
    [chr(i) for i in range(0x80, 0x100)],
    ["é", " ", "­", " ", " ", "​", " ", "　", "﻿", "￾", "͸",
     "⁥", "\U0001F600", "\U000E0001", "\U0010FFFF", "\U00013439", "؀", " ", "₆", "K"],
]


def random_string(r: SplitMix64) -> str:
    n = r.below(12)
    out = []
    for _ in range(n):
        pool = r.below(5)
        if pool < 4:
            p = ALPHABET_POOLS[pool]
            out.append(p[r.below(len(p))])
        else:
            cp = r.below(0x110000)
            if 0xD800 <= cp <= 0xDFFF:
                cp = 0xFFFD
            out.append(chr(cp))
    return "".join(out)


def random_value(r: SplitMix64, depth: int):
    k = r.below(9 if depth < 3 else 6)
    if k == 0:
        return None
    if k == 1:
        return r.below(2) == 1
    if k == 2:
        return int(r.next()) - (1 << 63)
    if k == 3:
        return float_of(r.next())
    if k == 4:
        return float(decimal_draw(r))
    if k == 5:
        return random_string(r)
    if k in (6, 7):
        return [random_value(r, depth + 1) for _ in range(r.below(4))]
    return {random_string(r): random_value(r, depth + 1) for _ in range(r.below(4))}


DUMP_MODES = [
    {"indent": 1, "ensure_ascii": False},
    {"indent": 1, "ensure_ascii": False, "sort_keys": True},
    {"ensure_ascii": False, "sort_keys": True, "separators": [",", ":"]},
    {},
    {"indent": 2, "sort_keys": True},
    {"indent": 1, "ensure_ascii": True, "allow_nan": False},
]


def code_point_ranges(pred) -> list[list[int]]:
    ranges, start = [], None
    for cp in range(0x110000):
        hit = pred(chr(cp))
        if hit and start is None:
            start = cp
        if not hit and start is not None:
            ranges.append([start, cp - 1])
            start = None
    if start is not None:
        ranges.append([start, 0x10FFFF])
    return ranges


def non_printable_ranges() -> list[list[int]]:
    return code_point_ranges(lambda c: not c.isprintable())


def word_ranges() -> list[list[int]]:
    """re word characters of a str pattern (SRE_UNI_IS_WORD: str.isalnum() or '_'), for \\b."""
    return code_point_ranges(lambda c: c.isalnum() or c == "_")


def build(seed: int) -> dict:
    r = SplitMix64(seed)
    floats = boundary_floats() + config_floats()
    floats += [float_of(r.next()) for _ in range(N_RANDOM_BITS)]
    floats += [float(decimal_draw(r)) for _ in range(N_RANDOM_DECIMALS)]
    strings = [random_string(r) for _ in range(N_STRINGS)]
    docs = []
    for i in range(N_DOCUMENTS):
        v = random_value(r, 0)
        mode = DUMP_MODES[i % len(DUMP_MODES)]
        kw = dict(mode)
        if "separators" in kw:
            kw["separators"] = tuple(kw["separators"])
        try:
            out, err = json.dumps(v, **kw), None
        except ValueError as e:
            out, err = None, type(e).__name__
        docs.append({"value_canonical": json.dumps(v, ensure_ascii=True), "mode": mode, "dumps": out, "error": err})
    s_bits, s_dec = seed ^ 0x5F3759DF, seed ^ 0x1234ABCD
    return {
        "schema": "abep_pyjson_vectors_v1",
        "generator": "scripts/rust_migration/gen_pyjson_vectors.py",
        "seed": seed,
        "python": platform.python_version(),
        "float_repr_style": sys.float_repr_style,
        "unidata_version": unicodedata.unidata_version,
        "rng": "splitmix64 (state += 0x9E3779B97F4A7C15; xor-shift-multiply 30/27/31); below(n) = next() % n",
        "float_explicit": [float_row(x) for x in floats],
        "float_streams": [
            {"kind": "bits", "seed": s_bits, "n": N_STREAM_BITS,
             "line": "f'{bits:016x} {repr(x)} {json.dumps(x)}\\n'",
             "sha256": stream_digest(bits_stream(s_bits, N_STREAM_BITS))},
            {"kind": "decimal", "seed": s_dec, "n": N_STREAM_DECIMALS,
             "line": "f'{literal} {repr(float(literal))} {json.dumps(float(literal))}\\n'",
             "sha256": stream_digest(decimal_stream(s_dec, N_STREAM_DECIMALS))},
        ],
        "strings": [{"s": s, "json_ascii": json.dumps(s), "json_utf8": json.dumps(s, ensure_ascii=False),
                     "repr": repr(s)} for s in strings],
        "non_printable": non_printable_ranges(),
        "word": word_ranges(),
        "documents": docs,
    }


def render(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")


def render_table(non_printable: list[list[int]], word: list[list[int]]) -> bytes:
    def rows(ranges):
        return "".join(f"    (0x{lo:06x}, 0x{hi:06x}),\n" for lo, hi in ranges)
    return (f"""//! GENERATED by scripts/rust_migration/gen_pyjson_vectors.py - do not edit.
//!
//! Character classes of CPython {platform.python_version()} (unicodedata {unicodedata.unidata_version}), as inclusive
//! (first, last) code-point ranges in ascending order.

/// `str.isprintable()` is False: categories Cc, Cf, Cs, Co, Cn, Zl, Zp and Zs except U+0020 (`repr()` escapes them).
#[rustfmt::skip]
pub(crate) const NON_PRINTABLE: &[(u32, u32)] = &[
{rows(non_printable)}];

/// Word characters of `re` with a str pattern (`str.isalnum()` or `_`; the class behind `\\w` and `\\b`).
#[rustfmt::skip]
pub(crate) const WORD: &[(u32, u32)] = &[
{rows(word)}];
""").encode("utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED, help="development runs only")
    ap.add_argument("--out", default=None, help="development runs only")
    a = ap.parse_args(argv)
    doc = build(a.seed)
    files = {Path(a.out) if a.out else ROOT / OUT_REL: render(doc), ROOT / TABLE_REL: render_table(doc["non_printable"], doc["word"])}
    if a.check:
        stale = [str(p) for p, b in files.items() if not p.is_file() or p.read_bytes() != b]
        print(f"STALE: {stale}" if stale else "OK")
        return 1 if stale else 0
    for p, b in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
        print(f"wrote {p} ({len(b)} bytes, sha256 {hashlib.sha256(b).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
