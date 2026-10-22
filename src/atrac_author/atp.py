""".ATP assembly: 1,024 B ID3v2.4 tag + 96 B secure header + payload.

Size law (readout #8, fingerprint-verified on real discs):
    len(.ATP) == len(payload) + 1,120      exactly, for every track.
Payload = clean ATRAC3+ frames passed through the cipher interface
(placeholder identity today — see cipher.py).
"""
from __future__ import annotations

from . import cipher, id3tag
from .secure_header import SecureHeader

OVERHEAD = 1120  # 1024 ID3 + 96 secure header


def assemble_atp(payload: bytes, frame_size: int, header: SecureHeader,
                 track: str, artist: str, album: str) -> bytes:
    if len(payload) % frame_size != 0:
        raise ValueError("payload is not a whole number of frames")
    if header.frame_count != len(payload) // frame_size:
        raise ValueError("secure header frame count disagrees with payload")
    encrypted = cipher.encrypt_payload(payload, header.header_fields())
    if len(encrypted) != len(payload):
        raise ValueError("cipher broke the length-preserving law")
    return id3tag.write_tag(track, artist, album) + header.to_bytes() + encrypted


def track_filename(number: int) -> str:
    """Track 10 -> TRK0000A.ATP, track 160 -> TRK000A0.ATP, track 220 ->
    TRK000DC.ATP, track 225 -> TRK000E1.ATP: filename is 'TRK' + %05X
    (FIVE uppercase hex digits) of the 1-based track number — verified
    against every sample filename and the TOC frame counts (the
    readout #1 shorthand 'TRK0%04X' undercounts the digits)."""
    if not 1 <= number <= 0xFFFFF:
        raise ValueError("track number out of range")
    return f"TRK{number:05X}.ATP"
