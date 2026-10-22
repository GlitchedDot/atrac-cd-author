"""Capacity accountant: every byte of the ISO is budgeted against the
blank, and an over-capacity build is REFUSED (Lola's absolute-max rule).

Blank sizes in sectors (the app's dropdown set + custom):
  360000 = 12 cm 80 min (737,280,000 B)   333000 = 12 cm 74 min
  108000 = 8 cm pocket 24 min             94500 = 8 cm pocket 21 min
  405000 = 12 cm 90 min overburn          445500 = 12 cm 99 min overburn
A sector carries 2,048 user bytes. Each track costs payload + exactly
1,120 B (.ATP overhead law, readout #8) — accounted inside the file
sizes themselves; on top come the paperwork files and the ISO 9660
structures, estimated here and then verified exactly post-build.
"""
from __future__ import annotations

SECTOR = 2048

BLANKS = {
    360000: "12 cm 80 min",
    333000: "12 cm 74 min",
    108000: "8 cm pocket 24 min",
    94500: "8 cm pocket 21 min",
    405000: "12 cm 90 min (overburn)",
    445500: "12 cm 99 min (overburn)",
}


class CapacityError(Exception):
    pass


def _path_table_sectors(n_dirs: int, dir_name_lens: list[int]) -> int:
    size = 10  # root entry
    for ln in dir_name_lens:
        size += 8 + 1 + ln + (0 if ln % 2 else 1)
    import math
    return 2 * math.ceil(size / SECTOR)  # L + M tables


def estimate_iso_sectors(files: dict[str, int]) -> int:
    """files: ISO path ('/HIFI/TRK00001.ATP') -> size in bytes.
    Conservative ISO 9660 estimate (pycdlib layout shape)."""
    import math
    dirs: dict[str, list[int]] = {}
    for path, size in files.items():
        parent = path.rsplit("/", 1)[0] or "/"
        dirs.setdefault(parent, []).append(size)
    sectors = 16 + 2  # system area + PVD + terminator
    sectors += _path_table_sectors(len(dirs), [len(d.rsplit("/", 1)[-1]) for d in dirs if d != "/"])
    for parent, sizes in dirs.items():
        # directory data: '.' + '..' + one record per entry (files + subdirs)
        rec_bytes = 68
        for path in files:
            if (path.rsplit("/", 1)[0] or "/") == parent:
                name = path.rsplit("/", 1)[-1]
                rec_bytes += 33 + len(name) + (0 if len(name) % 2 else 1)
        subdirs = [d for d in dirs if d != parent and (d.rsplit("/", 1)[0] or "/") == parent]
        for sd in subdirs:
            name = sd.rsplit("/", 1)[-1]
            rec_bytes += 33 + len(name) + (0 if len(name) % 2 else 1)
        sectors += max(1, math.ceil(rec_bytes / SECTOR))
    for size in files.values():
        sectors += math.ceil(size / SECTOR)
    return sectors


def check_capacity(files: dict[str, int], capacity_sectors: int) -> int:
    """Returns the estimated sector total; raises CapacityError if over."""
    est = estimate_iso_sectors(files)
    if est > capacity_sectors:
        raise CapacityError(
            f"estimated {est} sectors exceeds blank capacity "
            f"{capacity_sectors} sectors ({BLANKS.get(capacity_sectors, 'custom')})")
    return est
