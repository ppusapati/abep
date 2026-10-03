"""Deterministic evidence archives (owner decision A9.22 item 9: generated outputs too large for ordinary Git history are
kept as a deterministic F<n>_<run-id>.tar.zst plus a committed manifest).

Determinism rules (the same input files give the same archive bytes for the same libzstd version; the uncompressed tar
is byte-identical for any version, and its sha256 is recorded as well):
  * tar: POSIX ustar, regular files only, entries sorted by archive path, mtime fixed (caller supplies the generating
    commit's epoch), uid = gid = 0, uname = gname = "", mode 0644; Python tarfile end-of-archive padding.
  * zstd: python-zstandard, single thread, fixed level, frame checksum on, content size on; library versions recorded.
Verification (``verify_archive``) runs before anything else is trusted: archive sha256 and size, decompression, the tar
sha256, then every member is re-extracted and its size and sha256 compared with the per-file manifest (and, when the
original files are given, with the originals byte for byte). No original is ever deleted here.
"""
from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

ZSTD_LEVEL = 19
TAR_MODE = 0o644
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _zstd():
    try:
        import zstandard
    except ImportError as e:  # pragma: no cover - environment dependent
        raise SystemExit("REFUSED: python-zstandard is required (pip install zstandard)") from e
    return zstandard


def zstd_versions() -> dict:
    z = _zstd()
    return {"python_zstandard": z.__version__, "libzstd": ".".join(str(x) for x in z.ZSTD_VERSION)}


def deterministic_tar(members: list[tuple[str, bytes]], mtime: int) -> bytes:
    """ustar bytes of (archive_path, data) members, sorted by path, with fixed metadata."""
    names = [n for n, _ in members]
    if len(set(names)) != len(names):
        raise ValueError("duplicate archive paths")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for name, data in sorted(members, key=lambda m: m[0]):
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            ti.mtime = int(mtime)
            ti.mode = TAR_MODE
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            ti.type = tarfile.REGTYPE
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def compress(tar_bytes: bytes, level: int = ZSTD_LEVEL) -> bytes:
    z = _zstd()
    return z.ZstdCompressor(level=level, write_checksum=True, write_content_size=True, threads=0).compress(tar_bytes)


def decompress(blob: bytes) -> bytes:
    return _zstd().ZstdDecompressor().decompress(blob)


def file_manifest(members: list[tuple[str, bytes]], sources: dict | None = None) -> list[dict]:
    out = []
    for name, data in sorted(members, key=lambda m: m[0]):
        row = {"path": name, "size_bytes": len(data), "sha256": sha256_bytes(data)}
        if sources and name in sources:
            row.update(sources[name])
        out.append(row)
    return out


def is_lfs_pointer(path: Path) -> bool:
    p = Path(path)
    if not p.is_file() or p.stat().st_size > 1024:
        return False
    return p.read_bytes().startswith(LFS_POINTER_PREFIX)


def verify_archive(blob: bytes, manifest: dict, originals: dict | None = None) -> list[str]:
    """Problems (empty = verified). manifest: the archive manifest dict; originals: {archive path: original bytes}."""
    errs = []
    a = manifest["archive"]
    if sha256_bytes(blob) != a["sha256"]:
        errs.append(f"archive sha256 {sha256_bytes(blob)} != manifest {a['sha256']}")
    if len(blob) != a["size_bytes"]:
        errs.append(f"archive size {len(blob)} != manifest {a['size_bytes']}")
    try:
        tar_bytes = decompress(blob)
    except Exception as e:  # noqa: BLE001 - any decoder failure is a verification failure
        return errs + [f"zstd decompression failed: {e}"]
    if sha256_bytes(tar_bytes) != a["tar_sha256"] or len(tar_bytes) != a["tar_size_bytes"]:
        errs.append("tar sha256 / size differ from the manifest")
    want = {f["path"]: f for f in manifest["files"]}
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tf:
        for ti in tf.getmembers():
            if not ti.isreg():
                errs.append(f"non-regular member {ti.name}")
                continue
            data = tf.extractfile(ti).read()
            seen.add(ti.name)
            f = want.get(ti.name)
            if f is None:
                errs.append(f"member not in manifest: {ti.name}")
                continue
            if len(data) != f["size_bytes"] or sha256_bytes(data) != f["sha256"]:
                errs.append(f"member differs from manifest: {ti.name}")
            if originals is not None and ti.name in originals and data != originals[ti.name]:
                errs.append(f"member differs byte-for-byte from the original: {ti.name}")
            if (ti.mtime, ti.uid, ti.gid, ti.mode) != (a["tar"]["mtime"], 0, 0, TAR_MODE):
                errs.append(f"member metadata not deterministic: {ti.name}")
    if seen != set(want):
        errs.append(f"manifest files missing from the archive: {sorted(set(want) - seen)}")
    if originals is not None and set(originals) != set(want):
        errs.append("originals and manifest name different file sets")
    return errs
