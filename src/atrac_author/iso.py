"""ISO 9660 writing (pycdlib) + an INDEPENDENT minimal ISO reader used
only for verification — it shares no code with pycdlib's reader, so a
writer bug cannot hide behind a matching reader bug.
"""
from __future__ import annotations

import hashlib
import io
import struct

import pycdlib


def write_iso(files: dict[str, bytes], out_path: str, vol_ident: str) -> int:
    """files: ISO path ('/TRACK.NDB', '/HIFI/TRK00001.ATP') -> contents.
    Returns the ISO size in bytes."""
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, vol_ident=vol_ident, sys_ident="ATRAC CD AUTHOR")
    dirs = sorted({p.rsplit("/", 1)[0] for p in files if p.rsplit("/", 1)[0]})
    for d in dirs:
        iso.add_directory(d)
    for path in sorted(files):
        data = files[path]
        iso.add_fp(io.BytesIO(data), len(data), path + ";1")
    with open(out_path, "wb") as fh:
        iso.write_fp(fh)
    iso.close()
    import os
    return os.path.getsize(out_path)


def _dir_records(iso_bytes: bytes, lba: int, size: int):
    off = lba * 2048
    end = off + size
    while off < end:
        ln = iso_bytes[off]
        if ln == 0:
            off = (off // 2048 + 1) * 2048
            continue
        rec = iso_bytes[off:off + ln]
        extent = struct.unpack("<I", rec[2:6])[0]
        dlen = struct.unpack("<I", rec[10:14])[0]
        flags = rec[25]
        nlen = rec[32]
        name = rec[33:33 + nlen]
        yield name, extent, dlen, flags
        off += ln


def read_iso_tree(iso_bytes: bytes) -> dict[str, tuple[int, str]]:
    """Independent reader: returns ISO path -> (size, sha256 hex)."""
    pvd = iso_bytes[16 * 2048:17 * 2048]
    if pvd[0] != 1 or pvd[1:6] != b"CD001":
        raise ValueError("no primary volume descriptor")
    root = pvd[156:190]
    root_lba = struct.unpack("<I", root[2:6])[0]
    root_len = struct.unpack("<I", root[10:14])[0]
    out: dict[str, tuple[int, str]] = {}

    def walk(lba: int, size: int, prefix: str):
        for name, extent, dlen, flags in _dir_records(iso_bytes, lba, size):
            if name in (b"\x00", b"\x01"):
                continue
            nm = name.decode("ascii")
            if nm.endswith(";1"):
                nm = nm[:-2]
            path = prefix + "/" + nm
            if flags & 2:
                walk(extent, dlen, path)
            else:
                content = iso_bytes[extent * 2048: extent * 2048 + dlen]
                out[path] = (dlen, hashlib.sha256(content).hexdigest())

    walk(root_lba, root_len, "")
    return out
