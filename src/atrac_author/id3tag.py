"""The ID3v2.4 tag at the head of every .ATP: exactly 1,024 bytes.

Measured on the sample .ATPs (readouts #1/#7 + direct parse):
  header: "ID3" 04 00 00 + syncsafe size 1014 (= 1024 - 10 header)
  frames, in order: TIT2, TPE1, TALB — flags 00 00, frame sizes
    syncsafe; text encoding byte 0x02 (UTF-16BE); text = the NDB
    string for that field (track display string / artist / album),
    truncated to 30 chars, followed by ONE NUL terminator unit.
  zero padding to 1,024 bytes total.

So TIT2 carries the same string as TRACK.NDB, TPE1 the ARTIST.NDB
string, TALB the ALBUM.NDB string (verified byte-for-byte on
TRK0000A and TRK000A0).
"""
from __future__ import annotations

from .ndb import clamp_string

TAG_LEN = 1024
FRAME_ORDER = ("TIT2", "TPE1", "TALB")


def _syncsafe(n: int) -> bytes:
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])


def _frame(fid: str, text: str) -> bytes:
    body = b"\x02" + clamp_string(text).encode("utf-16-be") + b"\x00\x00"
    return fid.encode("ascii") + _syncsafe(len(body)) + b"\x00\x00" + body


def write_tag(track: str, artist: str, album: str) -> bytes:
    frames = b"".join(_frame(fid, txt) for fid, txt in
                      zip(FRAME_ORDER, (track, artist, album)))
    tag = b"ID3\x04\x00\x00" + _syncsafe(TAG_LEN - 10) + frames
    if len(tag) > TAG_LEN:
        raise ValueError("tag overflow")
    return tag + bytes(TAG_LEN - len(tag))


def parse_tag(data: bytes) -> dict[str, str]:
    if len(data) != TAG_LEN or data[:3] != b"ID3":
        raise ValueError("not a 1024-byte ID3 tag")
    out = {}
    pos = 10
    while pos + 10 <= TAG_LEN and data[pos:pos + 4] != b"\x00" * 4:
        fid = data[pos:pos + 4].decode("ascii")
        sz = int.from_bytes(data[pos + 4:pos + 8], "big")  # <128 in practice: syncsafe == plain
        body = data[pos + 10:pos + 10 + sz]
        if body[:1] != b"\x02":
            raise ValueError(f"{fid}: unexpected encoding byte {body[:1].hex()}")
        out[fid] = body[1:].decode("utf-16-be").rstrip("\x00")
        pos += 10 + sz
    return out
