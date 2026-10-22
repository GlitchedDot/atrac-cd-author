"""0001000E.STK — the EKB key block.

Readout #8 headline: the .STK is BYTE-IDENTICAL (172/172) on two
independently burned discs. It is a fixed EKB record for EKB version
0x0001000E, not per-disc material — authoring it is a solved copy.
The record itself is Sony data and is not distributed with this
repository: stk_data.py loads it from a copy you supply (taken from
a SonicStage disc you burned) the first time it is needed.
"""
from __future__ import annotations

from . import stk_data

STK_FILENAME = "0001000E.STK"


def write_stk() -> bytes:
    return stk_data.STK_BYTES
