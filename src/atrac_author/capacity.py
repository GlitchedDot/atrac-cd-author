"""Capacity accountant: every byte of the ISO is budgeted against the
blank, and an over-capacity build is REFUSED (Lola's absolute-max rule).

Blank sizes in sectors (the app's dropdown set + custom):
  360000 = 12 cm 80 min (737,280,000 B)   333000 = 12 cm 74 min
  108000 = 8 cm pocket 24 min             94500 = 8 cm pocket 21 min
  405000 = 12 cm 90 min overburn          445500 = 12 cm 99 min overburn
A sector carries 2,048 user bytes. Each track costs payload + exactly
1,120 B (.ATP overhead law, readout #8) — accounted inside the file
sizes themselves; on top come the paperwork files and the ISO 9660
structures. The ISO layout is computed exactly (iso.py's planner is
the same code that writes the image), and the gate additionally
reserves the space a real burn consumes beyond session 1's ISO —
a SonicStage disc is left unfinalized with an open, empty session
2 (see SESSION_OVERHEAD_SECTORS).
"""
from __future__ import annotations

from . import iso as _iso

SECTOR = 2048

# Sectors a finished burn consumes beyond the session-1 ISO itself,
# measured on disc 1 (ImgBurn panel + slice image):
#   150   track post-gap (track length 344,959 - ISO size 344,809)
#     2   to the session-1 lead-out start (LBA 344,961)
# 11400   lead-out start -> next writable address 356,361 (the
#         session-1 lead-out plus session 2's reserved lead-in)
#   157   closing allowance (blank 360,000 - (356,361 + 3,482 free))
SESSION_OVERHEAD_SECTORS = 150 + 2 + 11400 + 157

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


def estimate_iso_sectors(files: dict[str, int]) -> int:
    """Exact sector total of the ISO for a {path: size} set — the
    writer's own layout planner, so the estimate cannot drift from
    what build_iso will actually emit."""
    return _iso.iso_sector_count(files)


def check_capacity(files: dict[str, int], capacity_sectors: int) -> int:
    """Returns the ISO's exact sector total; raises CapacityError if
    the ISO plus the burn's session overhead exceeds the blank."""
    est = estimate_iso_sectors(files)
    if est + SESSION_OVERHEAD_SECTORS > capacity_sectors:
        raise CapacityError(
            f"ISO needs {est} sectors + {SESSION_OVERHEAD_SECTORS} "
            f"session overhead = {est + SESSION_OVERHEAD_SECTORS}, "
            f"exceeds blank capacity {capacity_sectors} sectors "
            f"({BLANKS.get(capacity_sectors, 'custom')})")
    return est
