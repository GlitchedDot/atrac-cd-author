#!/usr/bin/env python3
"""Mine salhost memory dumps for the formed init.ocm image.

Looks for: the universal 13-byte SalAsn head, printable module-name
markers near a 'bc' tag, and low-entropy (structured) spans inside
otherwise high-entropy regions -- a decoded bytecode image should
stand out from encrypted blobs.
"""
import math
import os
import sys

HEAD = bytes([0x01, 0x01, 0x04, 0x08, 0x6A, 0x35, 0xA2, 0x1D,
              0x8C, 0x3C, 0x2C, 0x0C, 0x7E])


def entropy(block):
    if not block:
        return 0.0
    counts = [0] * 256
    for b in block:
        counts[b] += 1
    n = len(block)
    return -sum((c / n) * math.log2(c / n) for c in counts if c)


def scan(path):
    data = open(path, 'rb').read()
    print(f"== {path} ({len(data)} bytes)")
    # universal head (raw init.ocm body start, if copied verbatim)
    i = data.find(HEAD)
    while i != -1:
        print(f"  HEAD at 0x{i:x}")
        i = data.find(HEAD, i + 1)
    # ASCII names of interest
    for needle in (b'init.ocm', b'atpcd', b'.ocm', b'bc\x00'):
        i = data.find(needle)
        while i != -1:
            ctx = data[max(0, i - 16):i + 32]
            print(f"  {needle!r} at 0x{i:x}: {ctx!r}")
            i = data.find(needle, i + 1)
            break  # first occurrence per needle is enough signal
    # entropy profile: 4 KiB blocks, report runs of <7.0 bits
    low = []
    for off in range(0, len(data) - 4095, 4096):
        e = entropy(data[off:off + 4096])
        if e < 7.0:
            low.append((off, round(e, 2)))
    if low:
        print(f"  low-entropy 4K blocks (<7.0 bits): {len(low)}")
        for off, e in low[:20]:
            print(f"    0x{off:x}: {e}")


if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else 'dump'
    for name in sorted(os.listdir(d)):
        if name.endswith('.bin'):
            scan(os.path.join(d, name))
