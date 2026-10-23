"""Disc orchestration: track list in -> complete authored file tree ->
capacity-checked ISO image out.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime

from . import atp, capacity, iso as iso_mod, ndb, sti, stk
from .secure_header import SecureHeader

ROOT_FILES = ("TRACK.NDB", "ALBUM.NDB", "ARTIST.NDB", "GROUP.NDB",
              "PLLIST.NDB", "TOC00000.STI", "TOC00001.STI", stk.STK_FILENAME)


@dataclass
class TrackInput:
    payload: bytes        # clean ATRAC3+ frame stream
    frame_size: int       # bytes per frame at this track's bitrate
    title: str            # TRACK.NDB / TIT2 string
    artist: str
    album: str


def build_tree(tracks: list[TrackInput],
               groups: list[tuple[str, int, int]] | None = None,
               rng: random.Random | None = None) -> dict[str, bytes]:
    """groups: (name, first_track, last_track), 1-based inclusive.
    Default: one group named 'New Group' holding every track (disc 1's
    shape). Returns ISO path -> contents."""
    if not tracks:
        raise ValueError("no tracks")
    if groups is None:
        groups = [("New Group", 1, len(tracks))]
    rng = rng or random.Random()
    files: dict[str, bytes] = {}
    frame_counts = []
    for i, t in enumerate(tracks, start=1):
        header = SecureHeader.fresh(len(t.payload) // t.frame_size, rng)
        files[f"/HIFI/{atp.track_filename(i)}"] = atp.assemble_atp(
            t.payload, t.frame_size, header, t.title, t.artist, t.album)
        frame_counts.append(len(t.payload) // t.frame_size)
    files["/TRACK.NDB"] = ndb.write_ndb([t.title for t in tracks])
    files["/ALBUM.NDB"] = ndb.write_ndb([t.album for t in tracks])
    files["/ARTIST.NDB"] = ndb.write_ndb([t.artist for t in tracks])
    files["/GROUP.NDB"] = ndb.write_ndb([g[0] for g in groups])
    files["/PLLIST.NDB"] = ndb.write_ndb([])
    toc = sti.Toc.build(frame_counts, [(g[1], g[2]) for g in groups], rng)
    files["/TOC00000.STI"] = sti.write_toc(toc)
    files["/TOC00001.STI"] = sti.write_plf()
    files[f"/{stk.STK_FILENAME}"] = stk.write_stk()
    return files


def build_iso(tracks: list[TrackInput], out_path: str,
              capacity_sectors: int = 360000,
              groups: list[tuple[str, int, int]] | None = None,
              vol_ident: str = "",
              rng: random.Random | None = None,
              timestamp: datetime | None = None) -> dict:
    """Full pipeline with capacity enforcement. Refuses (raising
    capacity.CapacityError) before writing anything if the ISO plus
    the burn's session overhead is over the blank, and again after
    the build on the exact ISO size. vol_ident defaults to blank —
    real SonicStage discs carry an all-spaces volume identifier.
    timestamp (default: now) is stamped into the ISO; pass a fixed,
    tz-aware datetime together with a seeded rng for a byte-
    reproducible image. Returns a stats dict."""
    files = build_tree(tracks, groups=groups, rng=rng)
    sizes = {p: len(d) for p, d in files.items()}
    est_sectors = capacity.check_capacity(sizes, capacity_sectors)
    iso_bytes_written = iso_mod.write_iso(files, out_path, vol_ident,
                                          timestamp=timestamp)
    exact_sectors = -(-iso_bytes_written // capacity.SECTOR)
    if exact_sectors + capacity.SESSION_OVERHEAD_SECTORS > capacity_sectors:
        import os
        os.unlink(out_path)
        raise capacity.CapacityError(
            f"built ISO is {exact_sectors} sectors + "
            f"{capacity.SESSION_OVERHEAD_SECTORS} session overhead > "
            f"blank {capacity_sectors}; removed")
    return {
        "iso_path": out_path,
        "iso_bytes": iso_bytes_written,
        "iso_sectors": exact_sectors,
        "estimated_sectors": est_sectors,
        "session_overhead_sectors": capacity.SESSION_OVERHEAD_SECTORS,
        "capacity_sectors": capacity_sectors,
        "capacity_label": capacity.BLANKS.get(capacity_sectors, "custom"),
        "files": {p: (len(d), hashlib.sha256(d).hexdigest())
                  for p, d in sorted(files.items())},
    }
