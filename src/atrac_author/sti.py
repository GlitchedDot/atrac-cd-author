"""STI files: TOC00000.STI ("TOC ") and TOC00001.STI ("PLF ").

TOC00000.STI layout (measured on disc 1: 493 tracks/1 group and
disc 2: 432 tracks/11 groups; both sizes fit EXACTLY):

  0x000  "TOC " magic                                            [understood]
  0x004  u32 LE = 1 (version — little-endian, unlike the other
         fields in this header)                                  [understood]
  0x008  u8  = 1 (constant in both samples; role unknown)        [modeled: constant]
  0x009  u8  = group count                                       [understood]
  0x00A  u16 BE = track count                                    [understood]
  0x00C  u32 BE = 86,936 (disc1) / 84,305 (disc2). Scales like a
         total disc duration in seconds taken from source-file
         metadata: the frame-derived estimate sum(frames*2048/44100)
         gives 87,055 / 84,4xx — within 0.15% but NOT exact, so the
         value is not derivable from the audio alone.             [modeled]
  0x010  8 bytes per-disc random-looking material                [modeled: random]
  0x018  8 bytes zeros                                           [understood]
  0x020  16 bytes per-disc random-looking material (readout #8:
         the disc-individual value lives in this header region)   [modeled: random]
  0x030..0x100 zeros                                             [understood]
  0x100  group table, 8-byte slots, 256 slots (0x800 bytes):
           slot 0 is all zeros                                   [understood]
           slot k (k>=1): u16 BE first track (1-based),
                          u16 BE last track (1-based),
                          u16 BE group index (= k),
                          u16 BE 0                               [understood]
  0x900  track records, 16 bytes each, one per track:
           +0x00 u16 BE track number (1-based)                   [understood]
           +0x02 u16 BE second index, equal to the track number
                 in every record of both sample discs            [modeled: = track no]
           +0x04 u8  group number this track belongs to          [understood]
           +0x05 3 bytes zeros                                   [understood]
           +0x08 4 bytes format magic 01 00 28 2e (identical to
                 the secure-header preamble; constant across all
                 ground truth, which is all 64 kbps — any bitrate
                 dependence is unobservable in the samples)       [modeled: constant]
           +0x0C u32 BE ATRAC frame count of the track           [understood —
                 verified exactly against all 5 known tracks:
                 2911 / 3444 x4 / 3341 / 3039]

TOC00001.STI ("PLF ", playlist file): fixed 2,176 bytes in both
samples: "PLF " + version byte 01 + zeros. Both discs carry an empty
playlist, so the non-empty layout is unknown; we emit the empty form
byte-identically to the samples.                                  [modeled: empty form]
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

TOC_HEADER_LEN = 0x900
TOC_TRACK_RECORD_LEN = 16
GROUP_TABLE_OFFSET = 0x100
GROUP_SLOT_LEN = 8
FORMAT_MAGIC = bytes.fromhex("0100282e")
PLF_SIZE = 2176

# ATRAC3+ frame = 2048 samples at 44.1 kHz (verified: Ignite My Heart,
# 3,444 frames <-> 159.93 s against the library TLEN of 159.94 s).
SAMPLES_PER_FRAME = 2048
SAMPLE_RATE = 44100


def frames_to_seconds(frames: int) -> int:
    return int(frames * SAMPLES_PER_FRAME / SAMPLE_RATE)


@dataclass
class TocTrack:
    number: int          # 1-based
    group: int           # 1-based group index
    frame_count: int


@dataclass
class Toc:
    tracks: list[TocTrack]
    groups: list[tuple[int, int]]          # (first_track, last_track), 1-based
    total_seconds: int                     # modeled field @0x0C
    disc_id_a: bytes = field(default_factory=lambda: bytes(8))    # modeled @0x10
    disc_id_b: bytes = field(default_factory=lambda: bytes(16))   # modeled @0x20

    @classmethod
    def build(cls, frame_counts: list[int], group_ranges: list[tuple[int, int]],
              rng: random.Random) -> "Toc":
        tracks = []
        for i, fc in enumerate(frame_counts, start=1):
            g = next(k for k, (a, b) in enumerate(group_ranges, start=1) if a <= i <= b)
            tracks.append(TocTrack(i, g, fc))
        return cls(
            tracks=tracks,
            groups=list(group_ranges),
            total_seconds=sum(frames_to_seconds(fc) for fc in frame_counts),
            disc_id_a=rng.randbytes(8),
            disc_id_b=rng.randbytes(16),
        )


def write_toc(toc: Toc) -> bytes:
    out = bytearray(TOC_HEADER_LEN)
    out[0:4] = b"TOC "
    out[4:8] = (1).to_bytes(4, "little")
    out[8] = 1
    out[9] = len(toc.groups)
    out[10:12] = len(toc.tracks).to_bytes(2, "big")
    out[12:16] = toc.total_seconds.to_bytes(4, "big")
    out[0x10:0x18] = toc.disc_id_a
    out[0x20:0x30] = toc.disc_id_b
    for k, (first, last) in enumerate(toc.groups, start=1):
        off = GROUP_TABLE_OFFSET + k * GROUP_SLOT_LEN
        out[off:off + 8] = (first.to_bytes(2, "big") + last.to_bytes(2, "big")
                            + k.to_bytes(2, "big") + b"\x00\x00")
    for t in toc.tracks:
        out += (t.number.to_bytes(2, "big") + t.number.to_bytes(2, "big")
                + bytes([t.group]) + b"\x00\x00\x00" + FORMAT_MAGIC
                + t.frame_count.to_bytes(4, "big"))
    return bytes(out)


def parse_toc(data: bytes) -> Toc:
    if data[:4] != b"TOC ":
        raise ValueError("not a TOC file")
    ngroups = data[9]
    ntracks = int.from_bytes(data[10:12], "big")
    if len(data) != TOC_HEADER_LEN + ntracks * TOC_TRACK_RECORD_LEN:
        raise ValueError("TOC size mismatch")
    groups = []
    for k in range(1, ngroups + 1):
        off = GROUP_TABLE_OFFSET + k * GROUP_SLOT_LEN
        first = int.from_bytes(data[off:off + 2], "big")
        last = int.from_bytes(data[off + 2:off + 4], "big")
        idx = int.from_bytes(data[off + 4:off + 6], "big")
        if idx != k:
            raise ValueError(f"group slot {k}: index field {idx}")
        groups.append((first, last))
    tracks = []
    for i in range(ntracks):
        r = data[TOC_HEADER_LEN + i * 16: TOC_HEADER_LEN + (i + 1) * 16]
        tracks.append(TocTrack(
            number=int.from_bytes(r[0:2], "big"),
            group=r[4],
            frame_count=int.from_bytes(r[12:16], "big"),
        ))
    return Toc(tracks=tracks, groups=groups,
               total_seconds=int.from_bytes(data[12:16], "big"),
               disc_id_a=data[0x10:0x18], disc_id_b=data[0x20:0x30])


def write_plf() -> bytes:
    """Empty playlist file, byte-identical to both sample discs."""
    return b"PLF " + b"\x01" + bytes(PLF_SIZE - 5)
