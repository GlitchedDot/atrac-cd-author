"""NDB databases: TRACK.NDB / ALBUM.NDB / ARTIST.NDB / GROUP.NDB / PLLIST.NDB.

Format (measured on disc 1 + disc 2, readouts #1/#2/#8):
  header: 256 bytes = "NDB " + version bytes 01 00 + BE u16 record count
          at offset 6, zeros elsewhere.
  record: 128 bytes = constant byte pair 02 00 (LE u16 value 2) +
          UTF-16BE string occupying
          bytes 2..61 (max 30 code units, zero padded), zeros to 128.
TRACK/ALBUM/ARTIST hold one record per track; GROUP holds one record per
group; PLLIST is an empty NDB (count 0, header only).
An empty string is stored as an ALL-ZERO record (disc 1's ALBUM.NDB has
39 of them — tracks with no album string in the library).
"""
from __future__ import annotations

HEADER_LEN = 256
RECORD_LEN = 128
STRING_FIELD_LEN = 60          # bytes 2..61 of the record
MAX_STRING_CHARS = STRING_FIELD_LEN // 2   # 30 UTF-16 code units


def clamp_string(s: str) -> str:
    """The format stores at most 30 UTF-16 code units per string."""
    return s[:MAX_STRING_CHARS]


def write_ndb(strings: list[str]) -> bytes:
    out = bytearray()
    out += b"NDB " + b"\x01\x00" + len(strings).to_bytes(2, "big")
    out += bytes(HEADER_LEN - len(out))
    for s in strings:
        if s == "":
            out += bytes(RECORD_LEN)   # empty string = all-zero record
            continue
        enc = clamp_string(s).encode("utf-16-be")
        rec = b"\x02\x00" + enc + bytes(RECORD_LEN - 2 - len(enc))
        out += rec
    return bytes(out)


def parse_ndb(data: bytes) -> list[str]:
    if data[:4] != b"NDB ":
        raise ValueError("not an NDB file")
    count = int.from_bytes(data[6:8], "big")
    if len(data) != HEADER_LEN + count * RECORD_LEN:
        raise ValueError(f"NDB size {len(data)} != header + {count} records")
    strings = []
    for i in range(count):
        rec = data[HEADER_LEN + i * RECORD_LEN: HEADER_LEN + (i + 1) * RECORD_LEN]
        if not any(rec):
            strings.append("")
            continue
        if rec[:2] != b"\x02\x00":
            raise ValueError(f"record {i}: bad prefix {rec[:2].hex()}")
        if any(rec[62:]):
            raise ValueError(f"record {i}: nonzero data past byte 62")
        strings.append(rec[2:62].decode("utf-16-be").rstrip("\x00"))
    return strings
