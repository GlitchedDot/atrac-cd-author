"""ISO 9660 writing, hand-rolled to match the layout the original
burner (Primo, under SonicStage) writes on real ATRAC CDs — measured
on disc 1 (stage1-disc-image readout):

  sectors 0-15  system area, all zeros
  sector  16    Primary Volume Descriptor: system id, volume id,
                volume set, publisher, preparer and application id
                all spaces; copyright/abstract/bibliographic file
                identifiers spaces; the application-use tail zeroed
  sector  17    volume descriptor terminator
  sector  18    L path table, M path table immediately after
  then          root directory, subdirectory data, then file data —
                gapless, directories first in path-table order, files
                grouped by parent in directory-record order

Every directory record carries the same recording timestamp. The
four PVD timestamps share one instant; following the original, the
PVD digit strings are UTC while the directory records use local
time, both carrying the local GMT-offset byte.

Plus an INDEPENDENT minimal ISO reader used only for verification —
it shares no code with the writer, so a writer bug cannot hide
behind a matching reader bug.
"""
from __future__ import annotations

import hashlib
import struct
from datetime import datetime, timezone

SECTOR = 2048


def _le16(n): return struct.pack("<H", n)
def _be16(n): return struct.pack(">H", n)
def _both16(n): return _le16(n) + _be16(n)
def _le32(n): return struct.pack("<I", n)
def _be32(n): return struct.pack(">I", n)
def _both32(n): return _le32(n) + _be32(n)


def _timestamps(timestamp: datetime | None = None):
    """(dir-record 7-byte date [local], PVD 17-byte timestamp [UTC
    digits + local offset byte]) for one shared instant: now, or
    `timestamp`. A tz-aware `timestamp` is used as given (its own
    offset is the "local" offset), so the result doesn't depend on
    the machine's time zone; a naive one is read as local time."""
    if timestamp is None:
        now_local = datetime.now().astimezone()
    elif timestamp.utcoffset() is None:
        now_local = timestamp.astimezone()
    else:
        now_local = timestamp
    now_utc = now_local.astimezone(timezone.utc)
    offset = now_local.utcoffset()
    tz = int(offset.total_seconds() // 900) if offset else 0
    date7 = bytes([
        now_local.year - 1900, now_local.month, now_local.day,
        now_local.hour, now_local.minute, now_local.second,
        tz & 0xFF,
    ])
    pvd17 = (now_utc.strftime("%Y%m%d%H%M%S")
             + f"{now_utc.microsecond // 10000:02d}").encode("ascii") \
        + bytes([tz & 0xFF])
    return date7, pvd17


def _dir_record(extent: int, size: int, is_dir: bool,
                date7: bytes, name: bytes) -> bytes:
    nlen = len(name)
    total = 33 + nlen
    if total % 2:
        total += 1
    rec = bytearray(total)
    rec[0] = total
    rec[2:10] = _both32(extent)
    rec[10:18] = _both32(size)
    rec[18:25] = date7
    rec[25] = 2 if is_dir else 0
    rec[28:32] = _both16(1)
    rec[32] = nlen
    rec[33:33 + nlen] = name
    return bytes(rec)


class _Dir:
    __slots__ = ("path", "name", "parent", "files", "subdirs",
                 "extent", "size", "index")

    def __init__(self, path, name, parent):
        self.path = path          # '' for root, else '/HIFI' style
        self.name = name          # b''-ish display name; root: b'\x00'
        self.parent = parent      # _Dir or None (root)
        self.files = []           # (identifier bytes, full path, size)
        self.subdirs = []         # _Dir
        self.extent = 0
        self.size = 0
        self.index = 0            # 1-based path-table index


def _build_tree(sizes: dict[str, int]) -> _Dir:
    root = _Dir("", b"\x00", None)
    dirs: dict[str, _Dir] = {"": root}
    for path in sorted(sizes):
        parts = [p for p in path.split("/") if p]
        parent = root
        cur = ""
        for part in parts[:-1]:
            cur += "/" + part
            if cur not in dirs:
                d = _Dir(cur, part.encode("ascii"), parent)
                dirs[cur] = d
                parent.subdirs.append(d)
            parent = dirs[cur]
        ident = (parts[-1] + ";1").encode("ascii")
        parent.files.append((ident, path, sizes[path]))
    for d in dirs.values():
        d.files.sort(key=lambda t: t[0])
        d.subdirs.sort(key=lambda s: s.name)
    return root


def _dir_order(root: _Dir) -> list[_Dir]:
    """Path-table order: breadth-first, siblings sorted by name."""
    order = [root]
    i = 0
    while i < len(order):
        order.extend(sorted(order[i].subdirs, key=lambda s: s.name))
        i += 1
    for n, d in enumerate(order, start=1):
        d.index = n
    return order


def _dir_data_size(d: _Dir) -> int:
    """Padded size of a directory's data: records in order ('.',
    '..', then children sorted by identifier), no record crossing a
    sector boundary."""
    ordered = [b"\x00", b"\x01"] + sorted(
        [sd.name for sd in d.subdirs] + [t[0] for t in d.files])
    pos = 0
    for ident in ordered:
        ln = 33 + len(ident)
        if ln % 2:
            ln += 1
        if pos % SECTOR + ln > SECTOR:
            pos += SECTOR - pos % SECTOR
        pos += ln
    return -(-pos // SECTOR) * SECTOR


def _path_tables(order: list[_Dir]) -> tuple[bytes, bytes]:
    lt = bytearray()
    mt = bytearray()
    for d in order:
        name = b"\x00" if d.parent is None else d.name
        parent_idx = d.index if d.parent is None else d.parent.index
        pad = b"\x00" if len(name) % 2 else b""
        lt += bytes([len(name), 0]) + _le32(d.extent) \
            + _le16(parent_idx) + name + pad
        mt += bytes([len(name), 0]) + _be32(d.extent) \
            + _be16(parent_idx) + name + pad
    return bytes(lt), bytes(mt)


def _plan(sizes: dict[str, int]):
    """Full layout for a {path: size} set. Returns (order, tables,
    file_extents, total_sectors)."""
    root = _build_tree(sizes)
    order = _dir_order(root)
    # directory data sizes don't depend on extents; compute first
    for d in order:
        d.size = _dir_data_size(d)
    lt_len = mt_len = None
    # path table lengths depend only on names/depths, not extents
    lt, mt = _path_tables(order)  # extents are 0 here; lengths final
    lt_sec = -(-len(lt) // SECTOR)
    mt_sec = -(-len(mt) // SECTOR)
    nxt = 16 + 2 + lt_sec + mt_sec
    for d in order:
        d.extent = nxt
        nxt += d.size // SECTOR
    file_extents: dict[str, int] = {}
    for d in order:
        for ident, path, size in d.files:
            file_extents[path] = nxt
            nxt += -(-size // SECTOR)
    lt, mt = _path_tables(order)  # rebuild with real extents
    return order, (lt, mt), file_extents, nxt


def iso_sector_count(sizes: dict[str, int]) -> int:
    """Exact sector total of the ISO for a {path: size} set."""
    return _plan(sizes)[3]


def _dir_bytes(d: _Dir, file_extents: dict[str, int],
               date7: bytes) -> bytes:
    parent = d.parent if d.parent is not None else d
    out = bytearray()
    records = [(b"\x00", d.extent, d.size, True),
               (b"\x01", parent.extent, parent.size, True)]
    kids = [(sd.name, sd.extent, sd.size, True) for sd in d.subdirs]
    kids += [(t[0], file_extents[t[1]], t[2], False) for t in d.files]
    kids.sort(key=lambda t: t[0])
    records += kids
    for ident, ext, size, is_dir in records:
        rec = _dir_record(ext, size, is_dir, date7, ident)
        if len(out) % SECTOR + len(rec) > SECTOR:
            out += bytes(SECTOR - len(out) % SECTOR)
        out += rec
    out += bytes(d.size - len(out))
    return bytes(out)


def write_iso(files: dict[str, bytes], out_path: str,
              vol_ident: str = "", timestamp: datetime | None = None) -> int:
    """files: ISO path ('/TRACK.NDB', '/HIFI/TRK00001.ATP') ->
    contents. Layout mirrors the original burner's, per the module
    docstring. vol_ident defaults to blank — real discs carry a
    blank (all-spaces) volume identifier. timestamp (default: now) is
    the instant stamped into the PVD and directory records; pass a
    fixed, tz-aware datetime for a byte-reproducible image. Returns
    the ISO size."""
    sizes = {p: len(data) for p, data in files.items()}
    order, (lt, mt), file_extents, total = _plan(sizes)
    date7, pvd17 = _timestamps(timestamp)
    root = order[0]

    img = bytearray(total * SECTOR)

    # PVD (sector 16)
    pvd = bytearray(SECTOR)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b" " * 32                       # system id: blank
    ident = vol_ident.encode("ascii", "replace")[:32]
    pvd[40:72] = ident + b" " * (32 - len(ident))
    pvd[80:88] = _both32(total)
    pvd[120:124] = _both16(1)                   # volume set size
    pvd[124:128] = _both16(1)                   # volume sequence
    pvd[128:132] = _both16(SECTOR)              # logical block size
    pvd[132:140] = _both32(len(lt))             # path table size
    pvd[140:144] = _le32(18)                    # L table location
    pvd[148:152] = _be32(18 + -(-len(lt) // SECTOR))  # M location
    pvd[156:190] = _dir_record(root.extent, root.size, True,
                               date7, b"\x00")
    for off in (190, 318, 446, 574):            # set/publisher/
        pvd[off:off + 128] = b" " * 128         # preparer/app id
    for off in (702, 739, 776):                 # copyright/
        pvd[off:off + 37] = b" " * 37           # abstract/biblio
    for off in (813, 830, 847, 864):            # all four stamps
        pvd[off:off + 17] = pvd17
    pvd[881] = 1                                # file structure ver
    img[16 * SECTOR:17 * SECTOR] = pvd

    # terminator (sector 17)
    term = bytearray(SECTOR)
    term[0] = 255
    term[1:6] = b"CD001"
    term[6] = 1
    img[17 * SECTOR:18 * SECTOR] = term

    # path tables
    img[18 * SECTOR:18 * SECTOR + len(lt)] = lt
    m_off = (18 + -(-len(lt) // SECTOR)) * SECTOR
    img[m_off:m_off + len(mt)] = mt

    # directories, then file data
    for d in order:
        data = _dir_bytes(d, file_extents, date7)
        img[d.extent * SECTOR:d.extent * SECTOR + len(data)] = data
    for path, data in files.items():
        ext = file_extents[path]
        img[ext * SECTOR:ext * SECTOR + len(data)] = data

    with open(out_path, "wb") as fh:
        fh.write(img)
    return len(img)


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
