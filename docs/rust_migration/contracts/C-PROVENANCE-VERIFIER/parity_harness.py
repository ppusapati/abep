#!/usr/bin/env python3
"""Parity harness of C-PROVENANCE-VERIFIER v1 (parity_prereg_v1.json in this directory).

Runs the unmodified Python checks (each tree's own scripts/ci_checks.py, run_checks) and the Rust verifier
(abep-provenance-verify) on the same trees: the current tree, the deterministic edge trees DE-01..DE-24 and the seeded
corrupted trees of classes CC-01..CC-07, built exactly as the contract's corruption_procedure registers them. Compares
pass / fail and the failure identities (identity_schema, python_message_map).

  python3 -B parity_harness.py develop [--n N]    development seed, current tree + seeded trees; never a verdict;
                                                  output to --out (default: the system temp directory)
  python3 -B parity_harness.py score              the single scoring execution: writes parity_report_v1.json + .md

Migration tooling only (standard library). It never writes into the repository tree except the two report files of
the scoring run; corrupted trees are temporary hard-linked copies of a `git archive` extraction.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CONTRACT = os.path.join(HERE, "parity_prereg_v1.json")
REPORT_JSON = os.path.join(HERE, "parity_report_v1.json")
REPORT_MD = os.path.join(HERE, "parity_report_v1.md")
CHECKS = ["prereg_lock", "audit_manifest", "hallthruster_pin", "h2_6_live_sources"]
CLASSES = ["CC-01", "CC-02", "CC-03", "CC-04", "CC-05", "CC-06", "CC-07"]

BR = "hallthruster_bridge"
LOCK = f"{BR}/prereg/p5_n2_prereg_lock_v1.json"
CRIT = f"{BR}/prereg/p5_n2_validation_criteria_v1.json"
MAN = f"{BR}/audit/configs/MANIFEST.json"
PIN = f"{BR}/PINNED.toml"
JMAN = f"{BR}/Manifest.toml"
JPROJ = f"{BR}/Project.toml"
RECORD = "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json"
CONSTP = "abep_sim/constants.py"
A5P = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
W1P = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
W3P = "docs/experiments/hardware/hardware_requirements_v1.json"
W4P = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
L25P = "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"
SPEC = "docs/ci/provenance_specs/h2_6_live_sources_v1.json"
RUST_SOURCES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/abep-types/src/lib.rs",
                "crates/abep-provenance/Cargo.toml", "crates/abep-provenance/src/lib.rs",
                "crates/abep-provenance/src/bin/abep-provenance-verify.rs", SPEC]
FORBIDDEN = ["LaB6Cathode", "lab6_xe", "cathode_life", "XE_CATHODE", "hall_1stage", "mw_air", "rf_cathode",
             "CONTROL_FALLBACK", "keeper", "heater", "hollow", "cathode"]


# ------------------------------------------------------------------------------------------------------------- utilities
def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: str) -> str:
    with open(p, "rb") as f:
        return sha_bytes(f.read())


def load_json(p: str):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def run(cmd, cwd=REPO, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd} failed ({r.returncode}): {r.stderr[-2000:]}")
    return r


def U(master: int, tag: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{master}|{tag}".encode("utf-8")).digest()[:8], "big")


def pick(master: int, seq, tag: str):
    return seq[U(master, tag) % len(seq)]


class InputMismatch(Exception):
    """A registered operation is inapplicable or an input differs (INPUT_MISMATCH, not a verdict)."""


# ------------------------------------------------------------------------------------------------- Python identity mapping
class Mapper:
    def __init__(self, contract: dict):
        dom = contract["h2_6_value_check_domain"]["groups"]
        self.name_file = {n: g["source"] for g in dom for n in g["names"]}
        self.group_file = {g["label"]: g["source"] for g in dom}
        names = sorted(self.name_file, key=len, reverse=True)
        self.value_re = re.compile("(?P<name>" + "|".join(re.escape(n) for n in names) + "): live source .* != consumed .*",
                                   re.DOTALL)
        self.mm = contract["python_message_map"]

    @staticmethod
    def raised_class(exc: str, msg: str, tree: str):
        if exc in ("JSONDecodeError", "TOMLDecodeError", "UnicodeDecodeError"):
            return "", "DECODE_ERROR"
        if exc == "FileNotFoundError":
            m = re.search(r"No such file or directory: '(.*)'$", msg, re.DOTALL)
            f = ""
            if m:
                f = os.path.relpath(m.group(1), tree).replace(os.sep, "/")
            return f, "FILE_MISSING"
        if exc == "KeyError":
            try:
                k = str(ast.literal_eval(msg))
            except (ValueError, SyntaxError):
                k = msg
            return "", f"KEY_MISSING:{k}"
        if exc in ("TypeError", "AttributeError"):
            return "", "TYPE_ERROR"
        if exc == "ValueError":
            return "", "VALUE_ERROR"
        return "", f"OTHER:{exc}"

    def identity(self, check: str, msg: str, tree: str):
        m = re.fullmatch(r"check raised (?P<exc>[A-Za-z_][A-Za-z0-9_.]*): (?P<msg>.*)", msg, re.DOTALL)
        if m:
            f, k = self.raised_class(m.group("exc"), m.group("msg"), tree)
            return ["RAISED", f, k]
        rules = self.rules(check)
        for pattern, fn in rules:
            mm = re.fullmatch(pattern, msg, re.DOTALL)
            if mm:
                return fn(mm)
        return ["UNMAPPED", "", msg]

    def rules(self, check):
        J = posixpath.join
        N = posixpath.normpath
        sha_tail = r" sha256 [0-9a-f]{16}\.\.\. != pinned .{0,16}\.\.\."
        lab = r"(?P<label>prereg lock|criteria inputs_pinned\.(?:measurement_audit|cases|transport_candidates))"
        if check == "prereg_lock":
            return [
                (r"prereg lock lists no files", lambda m: ["EMPTY_PIN_SET", LOCK, "files"]),
                (lab + r": (?P<rel>.+) is missing", lambda m: ["MISSING", N(J(BR, m["rel"])), m["label"]]),
                (lab + r": (?P<rel>.+)" + sha_tail, lambda m: ["SHA256_MISMATCH", N(J(BR, m["rel"])), m["label"]]),
                (r"criteria chemistry_configs_sha256: (?P<rel>.+) is missing",
                 lambda m: ["MISSING", N(J(BR, "propellants", m["rel"])), "criteria chemistry_configs_sha256"]),
                (r"criteria chemistry_configs_sha256: (?P<rel>.+)" + sha_tail,
                 lambda m: ["SHA256_MISMATCH", N(J(BR, "propellants", m["rel"])), "criteria chemistry_configs_sha256"]),
                (r"mandatory chemistry (?P<c>.+) has no pinned sha256", lambda m: ["UNPINNED", CRIT, m["c"]]),
            ]
        if check == "audit_manifest":
            AD = f"{BR}/audit/configs"
            PR = f"{BR}/propellants"
            return [
                (r"MANIFEST lists no configs", lambda m: ["EMPTY_PIN_SET", MAN, "configs"]),
                (r"audit case snapshot: (?P<rel>.+) is missing", lambda m: ["MISSING", N(J(AD, m["rel"])), "audit case snapshot"]),
                (r"audit case snapshot: (?P<rel>.+)" + sha_tail, lambda m: ["SHA256_MISMATCH", N(J(AD, m["rel"])), "audit case snapshot"]),
                (r"audit snapshot: (?P<rel>.+) is missing", lambda m: ["MISSING", N(J(AD, m["rel"])), "audit snapshot"]),
                (r"audit snapshot: (?P<rel>.+)" + sha_tail, lambda m: ["SHA256_MISMATCH", N(J(AD, m["rel"])), "audit snapshot"]),
                (r"audit snapshot (?P<f>.+?) rate table: (?P<rel>.+) is missing",
                 lambda m: ["MISSING", N(J(PR, m["rel"])), f"audit snapshot {m['f']} rate table"]),
                (r"audit snapshot (?P<f>.+?) rate table: (?P<rel>.+)" + sha_tail,
                 lambda m: ["SHA256_MISMATCH", N(J(PR, m["rel"])), f"audit snapshot {m['f']} rate table"]),
                (r"audit snapshot (?P<f>.+?): rate files (?P<diff>\[.*\]) differ between snapshot and MANIFEST",
                 lambda m: ["SET_MISMATCH", N(J(AD, m["f"])),
                            json.dumps(ast.literal_eval(m["diff"]), separators=(",", ":"), ensure_ascii=False)]),
            ]
        if check == "hallthruster_pin":
            return [
                (r"Manifest\.toml has (?P<n>-?\d+) HallThruster entries \(expected 1\)",
                 lambda m: ["ENTRY_COUNT", JMAN, "deps.HallThruster"]),
                (r"Manifest\.toml HallThruster (?P<mkey>repo-rev|version|repo-url) .* != PINNED\.toml (?:commit|version|repository) .*",
                 lambda m: ["VALUE_MISMATCH", JMAN, m["mkey"]]),
                (r"Project\.toml compat HallThruster .* != '=.*'", lambda m: ["VALUE_MISMATCH", JPROJ, "compat.HallThruster"]),
            ]
        if check == "h2_6_live_sources":
            groups = r"(?P<group>A5|W1|W4|W3|lane 25|capability demo)"

            def keyerr(m):
                try:
                    k = str(ast.literal_eval(m["k"]))
                except (ValueError, SyntaxError):
                    k = m["k"]
                return ["SOURCE_KEY_MISSING", self.group_file[m["group"]], k]

            return [
                (r"pinned file missing: (?P<rel>.+)", lambda m: ["MISSING", N(m["rel"]), "h2_6 pin"]),
                (r"pinned file altered \(re-pin deliberately\): (?P<rel>.+)", lambda m: ["SHA256_MISMATCH", N(m["rel"]), "h2_6 pin"]),
                (self.value_re.pattern, lambda m: ["VALUE_MISMATCH", self.name_file[m["name"]], m["name"]]),
                (r"w_O2_range: A5 test_matrix no longer states 0\.42-0\.60", lambda m: ["VALUE_MISMATCH", A5P, "w_O2_range"]),
                (r"(?P<name>a5_thrust_target_mN|a5_pbus_allocation_W): A5 allocation text changed",
                 lambda m: ["VALUE_MISMATCH", A5P, m["name"]]),
                (r"source missing: .*", lambda m: ["SOURCE_MISSING", CONSTP, "constants"]),
                (groups + r" source: FileNotFoundError\(.*\)", lambda m: ["SOURCE_MISSING", self.group_file[m["group"]], m["group"]]),
                (groups + r" source: KeyError\((?P<k>.*)\)", keyerr),
            ]
        raise ValueError(check)


# ---------------------------------------------------------------------------------------------------------- the two runners
PY_DRIVER = (
    "import importlib.util, json, sys\n"
    "sys.dont_write_bytecode = True\n"
    "spec = importlib.util.spec_from_file_location('ci_checks_under_test', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(m)\n"
    "res = m.run_checks(sys.argv[2].split(','))\n"
    "print(json.dumps({k: {'problems': v[0], 'note': v[1]} for k, v in res.items()}))\n"
)


def run_python(tree: str):
    t0 = time.perf_counter()
    r = subprocess.run([sys.executable, "-I", "-B", "-c", PY_DRIVER, os.path.join(tree, "scripts", "ci_checks.py"),
                        ",".join(CHECKS)], cwd=tree, capture_output=True, text=True)
    dt = time.perf_counter() - t0
    try:
        out = json.loads(r.stdout)
        return {c: out[c]["problems"] for c in CHECKS}, dt, None
    except (ValueError, KeyError):
        err = f"python driver failed (exit {r.returncode}): {r.stderr[-500:]}"
        return {c: [f"PYTHON_DRIVER_FAILED: {err}"] for c in CHECKS}, dt, err


def run_rust(binary: str, tree: str):
    t0 = time.perf_counter()
    r = subprocess.run([binary, "--root", tree, "--only", ",".join(CHECKS), "--json"], capture_output=True, text=True)
    dt = time.perf_counter() - t0
    try:
        out = json.loads(r.stdout)
        res = {c["check"]: c for c in out["checks"]}
        return {c: res[c] for c in CHECKS}, dt, None, r.stdout, out
    except (ValueError, KeyError):
        err = f"rust verifier failed (exit {r.returncode}): {r.stderr[-500:]}"
        fake = {c: {"findings": [{"kind": "RUST_RUN_FAILED", "file": "", "key": err}]} for c in CHECKS}
        return fake, dt, err, r.stdout, None


def compare(mapper: Mapper, tree: str, py: dict, rs: dict):
    per = {}
    agree_all = True
    for c in CHECKS:
        py_ids = sorted(mapper.identity(c, p, tree) for p in py[c])
        rs_ids = sorted([f["kind"], f["file"], f["key"]] for f in rs[c]["findings"])
        py_pass, rs_pass = not py[c], not rs[c]["findings"]
        agree = py_pass == rs_pass and py_ids == rs_ids
        agree_all &= agree
        per[c] = {"python_pass": py_pass, "rust_pass": rs_pass, "agree": agree, "python_problems": py[c],
                  "python_identities": py_ids, "rust_identities": rs_ids}
    return per, agree_all


# --------------------------------------------------------------------------------------------------------- tree handling
def file_manifest_sha(root: str) -> dict:
    out = {}
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = sha_file(p)
    return out


def stat_manifest(root: str) -> list:
    out = []
    for d, dirs, files in os.walk(root):
        dirs.sort()
        rd = os.path.relpath(d, root)
        out.append([rd, "dir"])
        for f in sorted(files):
            st = os.lstat(os.path.join(d, f))
            out.append([os.path.join(rd, f), st.st_size, st.st_mtime_ns, st.st_ino])
    return out


def link_tree(t0: str, dst: str):
    for d, dirs, files in os.walk(t0):
        rd = os.path.relpath(d, t0)
        os.makedirs(os.path.join(dst, rd), exist_ok=True)
        for f in files:
            os.link(os.path.join(d, f), os.path.join(dst, rd, f))


def write_new(tree: str, rel: str, data: bytes):
    p = os.path.join(tree, rel)
    if not os.path.isfile(p):
        raise InputMismatch(f"{rel} is not a file in the tree")
    os.unlink(p)
    with open(p, "wb") as f:
        f.write(data)


def read(tree: str, rel: str) -> bytes:
    with open(os.path.join(tree, rel), "rb") as f:
        return f.read()


def json_rewrite(tree: str, rel: str, mutate) -> bytes:
    raw = read(tree, rel)
    obj = json.loads(raw.decode("utf-8"))
    mutate(obj)
    out = (json.dumps(obj, indent=1, ensure_ascii=False) + ("\n" if raw.endswith(b"\n") else "")).encode("utf-8")
    write_new(tree, rel, out)
    return out


def text_replace_once(tree: str, rel: str, old: str, new: str) -> bytes:
    s = read(tree, rel).decode("utf-8")
    if s.count(old) != 1:
        raise InputMismatch(f"{rel}: {old!r} occurs {s.count(old)} times, the operation needs exactly one")
    out = s.replace(old, new).encode("utf-8")
    write_new(tree, rel, out)
    return out


def regex_sub_once(tree: str, rel: str, pattern: str, repl_group: int, value: str, first=False) -> tuple[bytes, str]:
    s = read(tree, rel).decode("utf-8")
    ms = list(re.finditer(pattern, s))
    if not ms or (not first and len(ms) != 1):
        raise InputMismatch(f"{rel}: pattern {pattern!r} matches {len(ms)} times")
    m = ms[0]
    old = m.group(repl_group)
    out = (s[:m.start(repl_group)] + value + s[m.end(repl_group):]).encode("utf-8")
    write_new(tree, rel, out)
    return out, old


def last_with_id(lst: list, field: str, ident: str) -> dict:
    hits = [x for x in lst if isinstance(x, dict) and x.get(field) == ident]
    if not hits:
        raise InputMismatch(f"no element with {field} == {ident!r}")
    return hits[-1]


# ----------------------------------------------------------------------------------------------------------- populations
def populations(t0: str) -> dict:
    lock = load_json(os.path.join(t0, LOCK))
    crit = load_json(os.path.join(t0, CRIT))
    man = load_json(os.path.join(t0, MAN))
    rec = load_json(os.path.join(t0, RECORD))
    n = posixpath.normpath
    pin = crit["inputs_pinned"]
    chem = pin["chemistry_configs_sha256"]
    prl = {n(f"{BR}/{k}") for k in lock["files"]}
    prl |= {n(f"{BR}/{pin[k]['file']}") for k in ("measurement_audit", "cases", "transport_candidates")}
    prl |= {n(f"{BR}/propellants/{c}") for c in chem}
    aud = set()
    for f, m in man["configs"].items():
        aud.add(n(f"{BR}/audit/configs/{f}"))
        aud |= {n(f"{BR}/propellants/{r}") for r in m["rate_files"]}
    aud |= {n(f"{BR}/audit/configs/{c}") for c in man["case_files"]}
    h26 = sorted(p["path"] for p in rec["authority_pins"] + rec["deliverable_pins"])
    r_lock = [(LOCK, ["files", k]) for k in lock["files"]]
    r_crit = [(CRIT, ["inputs_pinned", k, "sha256"]) for k in ("measurement_audit", "cases", "transport_candidates")]
    r_crit += [(CRIT, ["inputs_pinned", "chemistry_configs_sha256", c]) for c in chem]
    r_man = []
    for f, m in man["configs"].items():
        r_man.append((MAN, ["configs", f, "sha256"]))
        r_man += [(MAN, ["configs", f, "rate_files", r]) for r in m["rate_files"]]
    r_man += [(MAN, ["case_files", c, "sha256"]) for c in man["case_files"]]
    return {
        "PIN_PRL": sorted(prl), "PIN_AUD": sorted(aud), "PIN_H26": h26,
        "R_LOCK": r_lock, "R_CRIT": r_crit, "R_MAN": r_man,
        "LOCKED": sorted(n(f"{BR}/{k}") for k in lock["files"]),
        "CHEM": sorted(n(f"{BR}/propellants/{c}") for c in chem),
        "SNAP": sorted([n(f"{BR}/audit/configs/{f}") for f in man["configs"]]
                       + [n(f"{BR}/audit/configs/{c}") for c in man["case_files"]]),
    }


# ------------------------------------------------------------------------------------------------- registered operations
def op_unlink(tree, rel):
    p = os.path.join(tree, rel)
    if not os.path.isfile(p):
        raise InputMismatch(f"{rel} is not a file in the tree")
    os.unlink(p)
    return {"op": "unlink", "file": rel, "expect": ("absent", None)}


def digit_edit(tree, rel, master, tag):
    data = bytearray(read(tree, rel))
    pos = [j for j, b in enumerate(data) if 0x30 <= b <= 0x39]
    if not pos:
        data += b"\n"
        detail = {"appended_newline": True}
    else:
        j = pos[U(master, f"{tag}|pos") % len(pos)]
        old = data[j]
        data[j] = 0x30 + ((old - 0x30 + 1) % 10)
        detail = {"offset": j, "old": chr(old), "new": chr(data[j])}
    write_new(tree, rel, bytes(data))
    return {"op": "digit_edit", "file": rel, **detail, "expect": ("sha", sha_bytes(bytes(data)))}


def set_path(obj, path, value):
    cur = obj
    for k in path[:-1]:
        cur = cur[k]
    if path[-1] not in cur:
        raise InputMismatch(f"path {path} absent")
    old = cur[path[-1]]
    cur[path[-1]] = value
    return old


def new_sha(master, cls, i, field, old, n=64):
    v = hashlib.sha256(f"{master}|{cls}|{i}|{field}".encode()).hexdigest()[:n]
    if v == old:
        v = hashlib.sha256(f"{master}|{cls}|{i}|{field}|retry".encode()).hexdigest()[:n]
    return v


CONST_RE = {
    "K_B": (r"(?m)^(K_B = )([^\s#]+)", 2),
    "AMU": (r"(?m)^(AMU = )([^\s#]+)", 2),
    "M_N2_u": (r'(?m)^(\s*"N2":\s*)([^\s*,]+)(\s*\*\s*AMU)', 2),
    "M_O2_u": (r'(?m)^(\s*"O2":\s*)([^\s*,]+)(\s*\*\s*AMU)', 2),
    "M_Xe_u": (r'(?m)^(\s*"Xe":\s*)([^\s*,]+)(\s*\*\s*AMU)', 2),
    "thrust_min_mN": (r"(?m)^(\s+thrust_min_mN: float = )([^\s#]+)", 2),
    "thrust_max_mN": (r"(?m)^(\s+thrust_max_mN: float = )([^\s#]+)", 2),
    "power_max_W": (r"(?m)^(\s+power_max_W: float = )([^\s#]+)", 2),
    "firing_hours_min_h": (r"(?m)^(\s+ignition_hours: float = )([^\s#]+)", 2),
}


def live_json_target(name):
    """(file, resolver(obj) -> (container, key)) of a CC-07 JSON value check, as verify_sources reads it."""
    def path(*ks):
        def res(obj):
            cur = obj
            for k in ks[:-1]:
                cur = cur[k]
            return cur, ks[-1]
        return res

    def idval(listkey, ident):
        return lambda obj: (last_with_id(obj[listkey], "id", ident), "value")

    t = {
        "mdot_anode_min_kgps": (W1P, path("mfc_range_requirement", "mdot_min_kgps")),
        "mdot_anode_max_kgps": (W1P, path("mfc_range_requirement", "mdot_max_kgps")),
        "mdot_anode_max_accum_kgps": (W1P, path("mfc_range_requirement", "mdot_max_with_accumulation_kgps")),
        "mdot_O2_max_W1_kgps": (W1P, path("mfc_range_requirement", "O2_max_kgps")),
        "k_one_sided": (W4P, path("derived", "k_one_sided", "value")),
        "u_abs_planning(T)": (W4P, idval("proposed_thresholds", "I-U-ABS-T")),
        "u_abs_planning(P)": (W4P, idval("proposed_thresholds", "I-U-ABS-P")),
        "I_d_noise_floor_frac": (W4P, idval("proposed_thresholds", "I-U-ID-FLOOR")),
        "mfc_accuracy_fs": (W4P, path("derived", "mfc_relative_u_by_setpoint_fraction", "1.0", "value")),
        "remount_K": (L25P, idval("thresholds", "T-S1-REMOUNT-CYCLES")),
        "remount_r": (L25P, idval("thresholds", "T-S1-READINGS-PER-CYCLE")),
        "pb_elev_factor": (L25P, idval("thresholds", "T-PB-ELEV-FACTOR")),
        "S_eff N2 1e-5 Torr cross-check": (L25P, path("derived_numbers", "S_eff_required_per_mgps", "N2", "1.0e-05 Torr", "value")),
    }
    for n in ("4", "6", "8"):
        t[f"u_T_max_by_n[{n}]"] = (W4P, path("requirement_basis", "lane25_by_n", n, "u_T_max", "value"))
        t[f"u_P_max_by_n[{n}]"] = (W4P, path("requirement_basis", "lane25_by_n", n, "u_P_max", "value"))
    return t[name]


def perturb(v, delta):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise InputMismatch(f"live value {v!r} is not a number")
    return v + 1 if isinstance(v, int) else v * (1.0 + delta)


def corrupt(cls: str, i: int, tree: str, master: int, pops: dict, contract: dict) -> dict:
    if cls in ("CC-01", "CC-02"):
        s = i % 3
        stratum = [pops["PIN_PRL"], pops["PIN_AUD"], pops["PIN_H26"]][s]
        rel = pick(master, stratum, f"{cls}|{i}|file")
        if cls == "CC-02":
            return {"stratum": ["PIN_PRL", "PIN_AUD", "PIN_H26"][s], **op_unlink(tree, rel)}
        data = bytearray(read(tree, rel))
        if not data:
            data = bytearray(b"\x01")
            detail = {"empty_file": True}
        else:
            off = U(master, f"{cls}|{i}|offset") % len(data)
            bit = U(master, f"{cls}|{i}|bit") % 8
            old = data[off]
            data[off] ^= 1 << bit
            detail = {"offset": off, "bit": bit, "old_byte": old, "new_byte": data[off]}
        write_new(tree, rel, bytes(data))
        return {"stratum": ["PIN_PRL", "PIN_AUD", "PIN_H26"][s], "op": "byte_flip", "file": rel, **detail,
                "expect": ("sha", sha_bytes(bytes(data)))}
    if cls == "CC-03":
        s = i % 3
        stratum = [pops["R_LOCK"], pops["R_CRIT"], pops["R_MAN"]][s]
        rel, path = pick(master, stratum, f"{cls}|{i}|record")
        info = {}

        def mut(obj):
            cur = obj
            for k in path[:-1]:
                cur = cur[k]
            old = cur[path[-1]]
            cur[path[-1]] = info.setdefault("new", new_sha(master, cls, i, "sha", old))
            info["old"] = old

        out = json_rewrite(tree, rel, mut)
        return {"stratum": ["R_LOCK", "R_CRIT", "R_MAN"][s], "op": "wrong_recorded_sha", "file": rel, "path": path,
                "old": info["old"], "new": info["new"], "expect": ("sha", sha_bytes(out))}
    if cls == "CC-04":
        s = i % 2
        rel = pick(master, [pops["LOCKED"], pops["CHEM"]][s], f"{cls}|{i}|file")
        return {"stratum": ["LOCKED", "CHEM"][s], **digit_edit(tree, rel, master, f"{cls}|{i}")}
    if cls == "CC-05":
        rel = pops["SNAP"][i % len(pops["SNAP"])]
        return {"stratum": "SNAP", **digit_edit(tree, rel, master, f"{cls}|{i}")}
    if cls == "CC-06":
        s = i % 2
        rel, pattern = [(PIN, r'(?m)^commit = "([0-9a-f]{40})"'), (JMAN, r'(?m)^repo-rev = "([0-9a-f]{40})"')][s]
        old = re.search(pattern, read(tree, rel).decode("utf-8"))
        if not old:
            raise InputMismatch(f"{rel}: no commit line")
        new = new_sha(master, cls, i, "commit", old.group(1), 40)
        out, old_v = regex_sub_once(tree, rel, pattern, 1, new, first=True)
        return {"stratum": ["PINNED.toml commit", "Manifest.toml repo-rev"][s], "op": "pin_commit", "file": rel,
                "old": old_v, "new": new, "expect": ("sha", sha_bytes(out))}
    if cls == "CC-07":
        s = i % 4
        labels = ["constants", "W1", "W4", "lane 25"]
        group = next(g for g in contract["h2_6_value_check_domain"]["groups"] if g["label"] == labels[s])
        name = pick(master, group["names"], f"{cls}|{i}|check")
        k = pick(master, [2, 4, 6, 8, 10, 12], f"{cls}|{i}|delta")
        delta = 10.0 ** -k
        base = {"stratum": labels[s], "op": "live_value_change", "check": name, "k": k}
        if labels[s] == "constants":
            pattern, grp = CONST_RE[name]
            s_text = read(tree, CONSTP).decode("utf-8")
            ms = list(re.finditer(pattern, s_text))
            if len(ms) != 1:
                raise InputMismatch(f"{name}: {len(ms)} matches")
            old_lit = ms[0].group(grp)
            new_lit = repr(perturb(ast.literal_eval(old_lit), delta))
            out, _ = regex_sub_once(tree, CONSTP, pattern, grp, new_lit)
            return {**base, "file": CONSTP, "old": old_lit, "new": new_lit, "expect": ("sha", sha_bytes(out))}
        if name == "u_abs_grid":
            info = {}

            def mut(obj):
                gate = obj["derived"]["absolute_thrust_gate"]
                keys = list(gate)
                old = pick(master, keys, f"{cls}|{i}|key")
                new = repr(float(old) * (1.0 + delta))
                if new in gate:
                    raise InputMismatch("perturbed key collides")
                items = [(new if kk == old else kk, vv) for kk, vv in gate.items()]
                gate.clear()
                gate.update(items)
                info.update(old=old, new=new)

            out = json_rewrite(tree, W4P, mut)
            return {**base, "file": W4P, **info, "expect": ("sha", sha_bytes(out))}
        rel, resolve = live_json_target(name)
        info = {}

        def mut(obj):
            cont, key = resolve(obj)
            if key not in cont:
                raise InputMismatch(f"{name}: key {key!r} absent")
            info["old"] = cont[key]
            cont[key] = info["new"] = perturb(cont[key], delta)

        out = json_rewrite(tree, rel, mut)
        return {**base, "file": rel, **info, "expect": ("sha", sha_bytes(out))}
    raise ValueError(cls)


def edge_case(de: str, tree: str) -> dict:
    def jr(rel, mut):
        out = json_rewrite(tree, rel, mut)
        return {"op": "json_rewrite", "file": rel, "expect": ("sha", sha_bytes(out))}

    def tr(rel, old, new):
        out = text_replace_once(tree, rel, old, new)
        return {"op": "text_replace", "file": rel, "old": old, "new": new, "expect": ("sha", sha_bytes(out))}

    def del_key(path):
        def f(obj):
            cur = obj
            for k in path[:-1]:
                cur = cur[k]
            if path[-1] not in cur:
                raise InputMismatch(f"{path} absent")
            del cur[path[-1]]
        return f

    def one_elem(lst, field, ident):
        hits = [x for x in lst if isinstance(x, dict) and x.get(field) == ident]
        if len(hits) != 1:
            raise InputMismatch(f"{len(hits)} elements with {field} == {ident!r}")
        return hits[0]

    if de == "DE-01":
        return op_unlink(tree, LOCK)
    if de == "DE-02":
        return jr(LOCK, lambda o: o.__setitem__("files", {}))
    if de == "DE-03":
        return jr(CRIT, lambda o: o["mandatory_chemistry"].append("n2_n_unpinned_de03.toml"))
    if de == "DE-04":
        return jr(CRIT, del_key(["inputs_pinned", "cases"]))
    if de == "DE-05":
        return op_unlink(tree, MAN)
    if de == "DE-06":
        return jr(MAN, lambda o: o.__setitem__("configs", {}))
    if de == "DE-07":
        rel = f"{BR}/audit/configs/n2_n_0p9_pre_rotation.toml"
        out, old = regex_sub_once(tree, rel, r'(?m)^rate_coeff_file = "([^"]+)"', 1, "de07_unlisted.dat", first=True)
        return {"op": "regex_sub", "file": rel, "old": old, "new": "de07_unlisted.dat", "expect": ("sha", sha_bytes(out))}
    if de == "DE-08":
        rel = f"{BR}/audit/configs/n2_n_0p10_nominal_pre_hms.toml"
        data = read(tree, rel)
        out = data[: len(data) // 2]
        write_new(tree, rel, out)
        return {"op": "truncate_half", "file": rel, "size": len(data), "expect": ("sha", sha_bytes(out))}
    if de == "DE-09":
        return op_unlink(tree, PIN)
    if de == "DE-10":
        s = read(tree, JMAN).decode("utf-8")
        if "deps.HallThruster" not in s:
            raise InputMismatch("no deps.HallThruster")
        out = s.replace("deps.HallThruster", "deps.HallThrusterX").encode("utf-8")
        write_new(tree, JMAN, out)
        return {"op": "rename_all", "file": JMAN, "count": s.count("deps.HallThruster"), "expect": ("sha", sha_bytes(out))}
    if de == "DE-11":
        return tr(JPROJ, 'HallThruster = "=0.23.1"', 'HallThruster = "0.23.1"')
    if de == "DE-12":
        out, old = regex_sub_once(tree, PIN, r'(?m)^(version = "0\.23\.1"\n)', 1, "", first=True)
        return {"op": "delete_line", "file": PIN, "old": old, "expect": ("sha", sha_bytes(out))}
    if de == "DE-13":
        return op_unlink(tree, W1P)
    if de == "DE-14":
        return jr(W1P, del_key(["mfc_range_requirement", "mdot_max_kgps"]))
    if de == "DE-15":
        return jr(W4P, lambda o: last_with_id(o["proposed_thresholds"], "id", "I-U-ID-FLOOR").pop("value"))
    if de == "DE-16":
        return jr(L25P, lambda o: last_with_id(o["thresholds"], "id", "T-PB-ELEV-FACTOR").pop("value"))
    if de == "DE-17":
        return op_unlink(tree, CONSTP)
    if de == "DE-18":
        return tr(CONSTP, "thrust_min_mN: float = 12.0", "thrust_min_mN: float = float(12.0)")
    if de == "DE-19":
        return tr(CONSTP, "K_B = 1.380649e-23", "K_B = (1.380649e-23)")
    if de == "DE-20":
        return tr(CONSTP, "AMU = 1.66053906660e-27", "AMU = 1.660_539_066_60e-27")
    if de == "DE-21":
        return jr(W4P, lambda o: o["derived"]["absolute_thrust_gate"].__setitem__("not-a-number", {}))
    if de == "DE-22":
        def mut(o):
            o["requirements"].remove(one_elem(o["requirements"], "id", "HW-ENV-01"))
        return jr(W3P, mut)
    if de == "DE-23":
        return jr(A5P, lambda o: one_elem(o["allocations_and_requirements"], "quantity",
                                          "thrust operating target").__setitem__("value", "15-23 mN"))
    if de == "DE-24":
        rel = "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json"
        op_unlink(tree, rel)
        os.mkdir(os.path.join(tree, rel))
        return {"op": "unlink_then_mkdir", "file": rel, "expect": ("dir", None)}
    raise ValueError(de)


def inv06(t0: str, tree: str, op: dict) -> tuple[bool, str]:
    """The tree differs from T0 only in the registered target."""
    target = op["file"]
    kind, val = op["expect"]
    p = os.path.join(tree, target)
    if kind == "absent" and os.path.lexists(p):
        return False, "target still present"
    if kind == "sha" and (not os.path.isfile(p) or sha_file(p) != val):
        return False, "target bytes differ from the operation result"
    if kind == "dir" and not os.path.isdir(p):
        return False, "target is not a directory"
    for d, dirs, files in os.walk(t0):
        rd = os.path.relpath(d, t0)
        for f in files:
            rel = os.path.normpath(os.path.join(rd, f)).replace(os.sep, "/")
            if rel == target:
                continue
            q = os.path.join(tree, rel)
            if not os.path.isfile(q) or os.stat(q).st_ino != os.stat(os.path.join(d, f)).st_ino:
                return False, f"{rel} is not the T0 file"
    n_tree = sum(len(fs) for _, _, fs in os.walk(tree))
    n_t0 = sum(len(fs) for _, _, fs in os.walk(t0))
    expect_n = n_t0 - (1 if kind in ("absent", "dir") else 0)
    if n_tree != expect_n:
        return False, f"{n_tree} files, expected {expect_n}"
    return True, ""


# ------------------------------------------------------------------------------------------------------------ campaign
def build_rust() -> str:
    env = dict(os.environ)
    env["PATH"] = "/root/.cargo/bin:" + env.get("PATH", "")
    run(["cargo", "build", "--release", "--locked", "-p", "abep-provenance", "--bin", "abep-provenance-verify"], env=env)
    return os.path.join(REPO, "target", "release", "abep-provenance-verify")


def git(*args):
    return run(["git", "-C", REPO, *args]).stdout


def evaluate(mapper, binary, t0, tree_id, cls, build, campaign):
    tree = tempfile.mkdtemp(prefix=f"abep-pv-{tree_id}-")
    try:
        link_tree(t0, tree)
        op = build(tree)
        ok6, why6 = inv06(t0, tree, op)
        before = stat_manifest(tree)
        py, tpy, pyerr = run_python(tree)
        rs, trs, rserr, _, _ = run_rust(binary, tree)
        ok2 = stat_manifest(tree) == before
        per, agree = compare(mapper, tree, py, rs)
        op = {k: v for k, v in op.items() if k != "expect"}
        rec = {"tree": tree_id, "class": cls, "operation": op, "agree": agree, "checks": per,
               "python_fails": any(not v["python_pass"] for v in per.values()),
               "inv02_no_write": ok2, "inv06_only_target": ok6, "inv06_detail": why6,
               "python_seconds": round(tpy, 4), "rust_seconds": round(trs, 4)}
        if pyerr or rserr:
            rec["runner_error"] = pyerr or rserr
        campaign.append(rec)
        return rec
    finally:
        shutil.rmtree(tree, ignore_errors=True)


def campaign(mode: str, master: int, n_per_class: int, with_edge: bool, out_path: str):
    contract = load_json(CONTRACT)
    contract_sha = sha_file(CONTRACT)
    mapper = Mapper(contract)
    refusals = []
    ref = []
    for f in contract["reference_implementation"]["files"]:
        got = sha_file(os.path.join(REPO, f["path"]))
        ref.append({"path": f["path"], "sha256_at_registration": f["sha256_at_registration"], "sha256_at_scoring": got,
                    "match": got == f["sha256_at_registration"]})
        if got != f["sha256_at_registration"]:
            refusals.append("REFUSED_REFERENCE_CHANGED")
    head = git("rev-parse", "HEAD").strip()
    dirty = git("status", "--porcelain=v1", "--", *RUST_SOURCES, "crates/abep-provenance/src/verifier",
                "scripts/ci_checks.py", "docs/hardware/h2/h2_6_diagnostics_fixture").strip()
    if mode == "score" and dirty:
        raise SystemExit(f"refusing to score: uncommitted changes in scored sources:\n{dirty}")
    status_before = git("status", "--porcelain=v1", "-uall")
    pinned_before = {p: sha_file(os.path.join(REPO, p)) for p in contract["pinned_inputs_sha256"]}
    binary = build_rust()
    work = tempfile.mkdtemp(prefix="abep-pv-t0-")
    t0 = os.path.join(work, "T0")
    os.makedirs(t0)
    tar = os.path.join(work, "t0.tar")
    run(["git", "-C", REPO, "archive", "--format=tar", "-o", tar, "HEAD"])
    with tarfile.open(tar) as tf:
        tf.extractall(t0, filter="data")
    os.unlink(tar)
    t0_sha_before = file_manifest_sha(t0)
    for p, want in contract["pinned_inputs_sha256"].items():
        if t0_sha_before.get(p) != want:
            refusals.append(f"INPUT_MISMATCH: {p} differs in T0")
    pops = populations(t0)
    results = []
    t_start = time.time()

    # CUR-00 and INV-01
    rs1 = run_rust(binary, REPO)
    rs2 = run_rust(binary, REPO)
    inv01 = rs1[3] == rs2[3] and rs1[2] is None
    spec_sha_embedded = (rs1[4] or {}).get("h2_6_spec_sha256")
    py, tpy, pyerr = run_python(REPO)
    per, agree = compare(mapper, REPO, py, rs1[0])
    results.append({"tree": "CUR-00", "class": "current", "operation": {"op": "none", "file": "(repository tree)"},
                    "agree": agree, "checks": per, "python_fails": any(not v["python_pass"] for v in per.values()),
                    "inv02_no_write": True, "inv06_only_target": True, "inv06_detail": "",
                    "python_seconds": round(tpy, 4), "rust_seconds": round(rs1[1], 4)})
    d1 = all(v["python_pass"] and v["rust_pass"] for v in per.values())

    input_errors = []
    if with_edge:
        for k in range(1, 25):
            de = f"DE-{k:02d}"
            try:
                evaluate(mapper, binary, t0, de, "edge", lambda tree, de=de: edge_case(de, tree), results)
            except InputMismatch as e:
                input_errors.append(f"{de}: {e}")
    for cls in CLASSES:
        for i in range(n_per_class):
            tid = f"{cls}-{i:02d}"
            try:
                evaluate(mapper, binary, t0, tid, cls,
                         lambda tree, cls=cls, i=i: corrupt(cls, i, tree, master, pops, contract), results)
            except InputMismatch as e:
                input_errors.append(f"{tid}: {e}")
    elapsed = time.time() - t_start
    t0_sha_after = file_manifest_sha(t0)
    shutil.rmtree(work, ignore_errors=True)
    status_after = git("status", "--porcelain=v1", "-uall")
    pinned_after = {p: sha_file(os.path.join(REPO, p)) for p in contract["pinned_inputs_sha256"]}

    spec_bytes = open(os.path.join(REPO, SPEC), "rb").read()
    spec = json.loads(spec_bytes)
    record_sha = contract["pinned_inputs_sha256"][RECORD]
    inv = {
        "INV-01": inv01,
        "INV-02": all(r["inv02_no_write"] for r in results),
        "INV-03": t0_sha_before == t0_sha_after,
        "INV-04": status_before == status_after and pinned_before == pinned_after,
        "INV-05": spec_sha_embedded == sha_bytes(spec_bytes) and spec["consumed_record"]["sha256"] == record_sha,
        "INV-06": all(r["inv06_only_target"] for r in results),
    }
    if input_errors:
        refusals.append("INPUT_MISMATCH: " + "; ".join(input_errors))
    d2 = all(r["agree"] for r in results)
    exercised = {c: sum(1 for r in results if r["class"] == c and r["python_fails"]) for c in CLASSES}
    d3 = all(exercised[c] >= 1 for c in CLASSES)
    if refusals:
        verdict = refusals[0].split(":")[0]
    else:
        verdict = "PARITY_PASS" if (d1 and d2 and d3 and all(inv.values())) else "PARITY_FAIL"
    summary = {
        "trees_evaluated": len(results),
        "check_decisions_compared": 4 * len(results),
        "trees_agreeing": sum(r["agree"] for r in results),
        "disagreements": [r["tree"] for r in results if not r["agree"]],
        "by_class": {c: {"trees": sum(1 for r in results if r["class"] == c),
                         "agree": sum(1 for r in results if r["class"] == c and r["agree"]),
                         "python_fail_trees": exercised.get(c, sum(1 for r in results if r["class"] == c and r["python_fails"])),
                         "rust_fail_trees": sum(1 for r in results if r["class"] == c
                                                and any(not v["rust_pass"] for v in r["checks"].values()))}
                     for c in ["current", "edge"] + CLASSES},
        "failing_check_decisions": {c: sum(1 for r in results if not r["checks"][c]["python_pass"]) for c in CHECKS},
        "D1_baseline": d1, "D2_all_trees_agree": d2, "D3_classes_exercised": d3,
    }
    out = {
        "mode": mode, "master_seed": master, "n_per_class": n_per_class, "edge_cases": with_edge,
        "contract_sha256": contract_sha, "head": head, "reference_files": ref, "refusals": refusals,
        "invariants": inv, "summary": summary, "verdict": verdict, "elapsed_seconds": round(elapsed, 1),
        "rust_binary_sha256": sha_file(binary), "spec_sha256_embedded": spec_sha_embedded,
        "populations": {k: (len(v), v) for k, v in pops.items()},
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out


# --------------------------------------------------------------------------------------------------------------- report
def forbidden_scan() -> dict:
    hits = {}
    for d, _, files in os.walk(os.path.join(REPO, "crates")):
        for f in files:
            p = os.path.join(d, f)
            text = open(p, encoding="utf-8", errors="replace").read()
            for tok in FORBIDDEN:
                found = tok.lower() in text.lower() if tok in ("keeper", "heater", "hollow", "cathode") else tok in text
                if found:
                    hits.setdefault(os.path.relpath(p, REPO), []).append(tok)
    return hits


def build_provenance(res: dict) -> dict:
    env = dict(os.environ)
    env["PATH"] = "/root/.cargo/bin:" + env.get("PATH", "")
    srcs = list(RUST_SOURCES)
    vdir = os.path.join(REPO, "crates", "abep-provenance", "src", "verifier")
    srcs += sorted(os.path.relpath(os.path.join(vdir, f), REPO) for f in os.listdir(vdir))
    return {
        "rust_commit": res["head"],
        "rustc": run(["rustc", "-V"], env=env).stdout.strip(),
        "cargo": run(["cargo", "-V"], env=env).stdout.strip(),
        "cargo_lock_sha256": sha_file(os.path.join(REPO, "Cargo.lock")),
        "source_sha256": {s: sha_file(os.path.join(REPO, s)) for s in srcs},
        "binary": "target/release/abep-provenance-verify (cargo build --release --locked)",
        "binary_sha256": res["rust_binary_sha256"],
        "h2_6_spec_sha256_embedded": res["spec_sha256_embedded"],
        "harness": {"path": os.path.relpath(os.path.abspath(__file__), REPO), "sha256": sha_file(os.path.abspath(__file__))},
    }


def environment() -> dict:
    def ver(mod):
        r = subprocess.run([sys.executable, "-c", f"import {mod}; print({mod}.__version__)"], capture_output=True,
                           text=True, cwd=tempfile.gettempdir())
        return r.stdout.strip() or "not importable"

    cpu = ""
    try:
        cpu = next((ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo") if ln.startswith("model name")), "")
    except OSError:
        pass
    return {
        "python": platform.python_version(), "numpy": ver("numpy"), "scipy": ver("scipy"), "pandas": ver("pandas"),
        "requirements_lock_sha256": sha_file(os.path.join(REPO, "requirements-lock.txt")),
        "blas": "not used by the checks (standard library only)",
        "thread_env": {k: os.environ.get(k, "unset") for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        "platform": platform.platform(), "cpu": cpu, "cpu_count": os.cpu_count(),
    }


def cargo_gate() -> dict:
    """The contract's admission gate at the scoring commit (workspace members only; never `cargo fmt --all`)."""
    env = dict(os.environ)
    env["PATH"] = "/root/.cargo/bin:" + env.get("PATH", "")
    out = {}
    for name, cmd in (("fmt", ["cargo", "fmt", "--", "--check"]),
                      ("clippy", ["cargo", "clippy", "--workspace", "--all-targets", "--locked", "--", "-D", "warnings"]),
                      ("test", ["cargo", "test", "--workspace", "--locked"])):
        r = run(cmd, env=env, check=False)
        out[name] = {"command": " ".join(cmd), "exit": r.returncode}
        if name == "test":
            counts = [list(map(int, m)) for m in re.findall(
                r"test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored", r.stdout)]
            out[name].update(passed=sum(c[0] for c in counts), failed=sum(c[1] for c in counts),
                             ignored=sum(c[2] for c in counts))
    out["pass"] = all(v["exit"] == 0 for k, v in out.items() if k != "pass") and out["test"]["ignored"] == 0
    return out


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2) if xs else None


def write_report(res: dict, contract: dict, dev_note: str):
    gate = cargo_gate()
    passed = res["verdict"] == "PARITY_PASS" and gate["pass"]
    tpy = [r["python_seconds"] for r in res["results"]]
    trs = [r["rust_seconds"] for r in res["results"]]
    rep = {
        "schema": "abep_rust_parity_report_v1",
        "id": "PARITY-REPORT-C-PROVENANCE-VERIFIER-V1",
        "contract": {"path": os.path.relpath(CONTRACT, REPO), "sha256": res["contract_sha256"],
                     "id": contract["id"], "registration_commit": git("log", "-1", "--format=%H", "--", CONTRACT).strip()},
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "python_commit": res["head"],
        "reference_files": res["reference_files"],
        "build_provenance": build_provenance(res),
        "environment": environment(),
        "campaign_seeds": {"scoring_master_seed": res["master_seed"], "n_per_class": res["n_per_class"],
                           "edge_cases": "DE-01..DE-24"},
        "populations": {k: {"size": v[0]} for k, v in res["populations"].items()},
        "interpretation_notes": [
            "SNAP is sorted over the union of the MANIFEST config and case-file paths (sorted(A + B))",
            "a tree whose registered operation is inapplicable would be INPUT_MISMATCH; none was"
            if not any(r.startswith("INPUT_MISMATCH") for r in res["refusals"]) else "see refusals",
        ],
        "refusals": res["refusals"],
        "decision": {
            "D1_baseline_current_tree_passes_in_both": res["summary"]["D1_baseline"],
            "D2_every_tree_and_check_agrees": res["summary"]["D2_all_trees_agree"],
            "D3_every_class_exercised": res["summary"]["D3_classes_exercised"],
            "invariants": res["invariants"],
        },
        "summary": res["summary"],
        "classification_gate": {
            "forbidden_identifier_scan_crates": forbidden_scan() or "no hit (CI_PLAN.md sec. 1 principle 6 tokens, plus "
                                                                 "keeper / heater / hollow / cathode case-insensitive)",
        },
        "conservation": "NOT_APPLICABLE (contract conservation_checks.applicable = false)",
        "schema_parity": "identity_schema compared per finding: (kind, file, key)",
        "performance": {
            "status": "reported, not a decision criterion",
            "trees": len(res["results"]),
            "python_seconds_total": round(sum(tpy), 3), "rust_seconds_total": round(sum(trs), 3),
            "python_seconds_median": median(tpy), "rust_seconds_median": median(trs),
            "speed_up_median": round(median(tpy) / median(trs), 2) if median(trs) else None,
            "campaign_wall_seconds": res["elapsed_seconds"],
        },
        "verdict": res["verdict"],
        "cargo_gate": gate,
        "admission": "ADMITTED" if passed else "NOT_ADMITTED",
        "campaign_history": [
            {"execution": "development", "seed": contract["campaign_seeds"]["development_master_seed"],
             "note": dev_note, "verdict": "none (development comparisons are never a verdict)"},
            {"execution": "scoring", "seed": res["master_seed"], "commit": res["head"],
             "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "verdict": res["verdict"]},
        ],
        "ledger_update_requested": [],
        "results": res["results"],
    }
    if passed:
        rep["ledger_update_requested"] = [
            {"component": "C-PROVENANCE-VERIFIER (C-SCRIPTS_CI_CHECKS_PY function subset verify_sha_map, check_prereg_lock, "
                          "check_audit_manifest, check_hallthruster_pin, check_h2_6_live_sources; "
                          "C-DOCS_HARDWARE_H2_H2_6_DIAGNOSTICS_FIXTURE verify_sources check semantics)",
             "status": "ADMITTED", "authoritative_implementation":
                 "rust: abep_provenance::verifier / abep-provenance-verify", "contract_sha256": res["contract_sha256"],
             "report": "docs/rust_migration/contracts/C-PROVENANCE-VERIFIER/parity_report_v1.json"},
            {"request": "ci_checks h2_6_live_sources (and prereg_lock, audit_manifest, hallthruster_pin) MAY be retired "
                        "from active CI in a separate later step, after normal CI is re-pointed to abep-provenance-verify "
                        "(SC-WP-12, RM-R29, CI_PLAN.md W16). This report changes no CI workflow and no Python check."},
            {"note": "the builder docs/hardware/h2/h2_6_diagnostics_fixture/ stays class G, not ported; the other seven "
                     "ci_checks checks stay PYTHON_REFERENCE"},
        ]
    else:
        rep["ledger_update_requested"] = [{"component": "C-PROVENANCE-VERIFIER", "status": "NOT_ADMITTED",
                                           "note": "PYTHON_REFERENCE stays authoritative; Python checks stay in active CI"}]
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        f.write(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    write_md(rep)


def write_md(rep: dict):
    s = rep["summary"]
    L = [
        "# C-PROVENANCE-VERIFIER parity report v1",
        "",
        f"Generated from `parity_report_v1.json` (contract `{rep['contract']['path']}`, sha256 "
        f"`{rep['contract']['sha256']}`, registered in `{rep['contract']['registration_commit'][:12]}`).",
        "",
        f"**Verdict: {rep['verdict']}. Admission: {rep['admission']}** (cargo fmt / clippy / test gate: "
        f"{'pass' if rep['cargo_gate']['pass'] else 'FAIL'}, {rep['cargo_gate']['test']['passed']} tests passed, "
        f"{rep['cargo_gate']['test']['ignored']} ignored).",
        "",
        "## What was compared",
        "",
        "The Python checks `prereg_lock`, `audit_manifest`, `hallthruster_pin` and `h2_6_live_sources` (each tree's own",
        "unmodified `scripts/ci_checks.py`, `run_checks`) and the Rust verifier `abep-provenance-verify` ran on the same",
        "trees. For every tree and check, the pass / fail decision and the sorted multiset of failure identities",
        "(kind, file, key) had to be equal.",
        "",
        f"* Commit: `{rep['python_commit']}` (Python reference and Rust).",
        f"* Trees: {s['trees_evaluated']} (current tree, 24 edge trees, 7 classes x {rep['campaign_seeds']['n_per_class']} "
        f"seeded trees, scoring seed {rep['campaign_seeds']['scoring_master_seed']}).",
        f"* Check decisions compared: {s['check_decisions_compared']}; trees agreeing: {s['trees_agreeing']}.",
        f"* Disagreements: {', '.join(s['disagreements']) or 'none'}.",
        "",
        "## Decision rule",
        "",
        "| rule | holds |",
        "|---|---|",
        f"| D1 current tree passes in both | {rep['decision']['D1_baseline_current_tree_passes_in_both']} |",
        f"| D2 every tree and check agrees | {rep['decision']['D2_every_tree_and_check_agrees']} |",
        f"| D3 every class exercised | {rep['decision']['D3_every_class_exercised']} |",
    ]
    for k, v in rep["decision"]["invariants"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "## By class", "", "| class | trees | agree | Python fails | Rust fails |", "|---|---|---|---|---|"]
    for c, v in s["by_class"].items():
        L.append(f"| {c} | {v['trees']} | {v['agree']} | {v['python_fail_trees']} | {v['rust_fail_trees']} |")
    L += ["", "Failing check decisions (Python, all trees): "
          + ", ".join(f"{k} {v}" for k, v in s["failing_check_decisions"].items()) + ".", ""]
    L += ["## Edge trees", "", "| tree | operation | failing checks (identities) | agree |", "|---|---|---|---|"]
    for r in rep["results"]:
        if r["class"] != "edge":
            continue
        fails = "; ".join(f"{c}: " + ", ".join("/".join(x for x in i if x) for i in v["python_identities"])
                          for c, v in r["checks"].items() if not v["python_pass"]) or "none"
        L.append(f"| {r['tree']} | {r['operation']['op']} `{r['operation']['file']}` | {fails} | {r['agree']} |")
    b = rep["build_provenance"]
    e = rep["environment"]
    p = rep["performance"]
    L += ["", "## Provenance", "",
          f"* Reference files: " + "; ".join(f"`{x['path']}` {x['sha256_at_scoring'][:16]} (match {x['match']})"
                                             for x in rep["reference_files"]) + ".",
          f"* Rust: {b['rustc']}; Cargo.lock sha256 `{b['cargo_lock_sha256']}`; binary sha256 `{b['binary_sha256']}`; "
          f"embedded H2-6 spec sha256 `{b['h2_6_spec_sha256_embedded']}`.",
          f"* Harness `{b['harness']['path']}` sha256 `{b['harness']['sha256']}`.",
          f"* Python {e['python']}, numpy {e['numpy']}, scipy {e['scipy']}, pandas {e['pandas']}; {e['platform']}; "
          f"{e['cpu']} x {e['cpu_count']}; thread env {e['thread_env']}.",
          f"* Forbidden-identifier scan of crates/**: {rep['classification_gate']['forbidden_identifier_scan_crates']}.",
          "", "## Performance (reported, not a criterion)", "",
          f"Per tree: Python median {p['python_seconds_median']} s, Rust median {p['rust_seconds_median']} s "
          f"(speed-up {p['speed_up_median']}x, process start included); campaign wall {p['campaign_wall_seconds']} s.",
          "", "## Ledger update requested", ""]
    for x in rep["ledger_update_requested"]:
        L.append("* " + "; ".join(f"{k}: {v}" for k, v in x.items()))
    L += ["", "## What this is not", "",
          "Not physics validation, not a CI change, not a port of the H2-6 builder. The Python checks stay in active CI",
          "until a separate step re-points CI (SC-WP-12, RM-R29).", ""]
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["develop", "score"])
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dev-note", default="")
    a = ap.parse_args(argv)
    contract = load_json(CONTRACT)
    seeds = contract["campaign_seeds"]
    if a.mode == "develop":
        n = a.n or contract["corruption_procedure"]["n_per_class"]
        out = a.out or os.path.join(tempfile.gettempdir(), "abep_pv_develop.json")
        res = campaign("develop", seeds["development_master_seed"], n, False, out)
        print(json.dumps({"verdict_not_reported": res["verdict"], "summary": res["summary"],
                          "invariants": res["invariants"], "refusals": res["refusals"]}, indent=1))
        print("development output (never a verdict):", out)
        return 0
    if os.path.exists(REPORT_JSON):
        print("refusing: parity_report_v1.json exists (the scoring seed is spent once)")
        return 2
    raw = os.path.join(tempfile.gettempdir(), "abep_pv_score_raw.json")
    res = campaign("score", seeds["scoring_master_seed"], contract["corruption_procedure"]["n_per_class"], True, raw)
    write_report(res, contract, a.dev_note)
    print(res["verdict"], json.dumps(res["summary"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
