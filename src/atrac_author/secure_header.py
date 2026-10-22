"""The 96-byte secure header at .ATP offset 1024 (readout #7's map,
measured on 7 sample headers from disc 1).

  0x00  4   CONST    01 00 28 2e            format magic / version preamble
  0x04  4   per file BE u32 frame count     (= payload bytes / frame size)
  0x08  8   CONST    zeros                  reserved
  0x10  4   CONST    BE 00 01 00 0e         EKBVersion (= the .STK id)
  0x14  4   CONST    zeros                  reserved
  0x18  8   INSTANCE BlockSeed              fresh random per burn instance
  0x20  8   CONST    01 0f 50 00 00 04 00 00  format/block parameters
                                            (constant across all samples,
                                            which are all 64 kbps; any
                                            bitrate dependence unobservable)
  0x28  8   mixed    00 + Connum (2 B, per-TRACK) + 16 72 5f 9b e7
                                            (tail constant across all 7
                                            samples — one disc only, so
                                            disc-wide vs global format
                                            constant is undecidable)
  0x30  8   TRACK    4 varying bytes + 4 zeros (candidate content value)
  0x38  8   CONST    zeros                  reserved / padding
  0x40  16  CONST    "ATX " + zeros         codec tag slot
  0x50  8   TRACK    MgD                    content integrity value,
                                            identical for identical content
  0x58  8   INSTANCE InitVector             fresh random per burn instance

With the placeholder cipher, the per-TRACK crypto values (MgD, the
0x30 slot) cannot be computed — they are generated randomly here and
MUST be recomputed by the real cipher drop-in. Their variability
classes are preserved so the structure is faithful.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

HEADER_LEN = 96
FORMAT_MAGIC = bytes.fromhex("0100282e")
BLOCK_PARAMS = bytes.fromhex("010f500000040000")
CONNUM_TAIL = bytes.fromhex("16725f9be7")
EKB_VERSION = 0x0001000E


@dataclass
class SecureHeader:
    frame_count: int
    block_seed: bytes      # 8 B, per instance
    init_vector: bytes     # 8 B, per instance
    connum: bytes          # 2 B, per track
    track_slot: bytes      # 4 B, per track (stored at 0x30, followed by zeros)
    mgd: bytes             # 8 B, per track

    @classmethod
    def fresh(cls, frame_count: int, rng: random.Random) -> "SecureHeader":
        return cls(frame_count=frame_count,
                   block_seed=rng.randbytes(8),
                   init_vector=rng.randbytes(8),
                   connum=rng.randbytes(2),
                   track_slot=rng.randbytes(4),
                   mgd=rng.randbytes(8))

    def header_fields(self) -> dict:
        """The dict handed to the cipher interface."""
        return {"block_seed": self.block_seed, "init_vector": self.init_vector,
                "mgd": self.mgd, "connum": self.connum, "ekb_version": EKB_VERSION}

    def to_bytes(self) -> bytes:
        out = bytearray(HEADER_LEN)
        out[0x00:0x04] = FORMAT_MAGIC
        out[0x04:0x08] = self.frame_count.to_bytes(4, "big")
        out[0x10:0x14] = EKB_VERSION.to_bytes(4, "big")
        out[0x18:0x20] = self.block_seed
        out[0x20:0x28] = BLOCK_PARAMS
        out[0x28] = 0
        out[0x29:0x2B] = self.connum
        out[0x2B:0x30] = CONNUM_TAIL
        out[0x30:0x34] = self.track_slot
        out[0x40:0x44] = b"ATX "
        out[0x50:0x58] = self.mgd
        out[0x58:0x60] = self.init_vector
        return bytes(out)

    @classmethod
    def parse(cls, data: bytes) -> "SecureHeader":
        if len(data) != HEADER_LEN:
            raise ValueError("secure header must be 96 bytes")
        return cls(frame_count=int.from_bytes(data[0x04:0x08], "big"),
                   block_seed=data[0x18:0x20],
                   init_vector=data[0x58:0x60],
                   connum=data[0x29:0x2B],
                   track_slot=data[0x30:0x34],
                   mgd=data[0x50:0x58])
