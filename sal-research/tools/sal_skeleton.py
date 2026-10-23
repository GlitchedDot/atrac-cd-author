#!/usr/bin/env python3
"""sal_skeleton.py — SAL module framing-layer ("skeleton") parser.

Phase 4 (stage0-readout-14) established that a class-01 module body is
NOT an opaque transformed blob: its first 8,214 bytes are a plaintext
SalAsn-framed skeleton whose element CONTENTS are the opaque part:

  body+0    INT1 <v>                  format/version value (v = 1)
  body+2    STR[8] 6A35A21D8C3C2C0C   fixed family identifier
  body+12   0x7E                      section marker (universal)
  --- family modules (the 25 regular class-01 .ocm) ---
  body+13   04 82 20 00               OCTET STRING header, len 8192
  body+17   <8192 bytes>              shared chunk, byte-identical in
                                      all 25 modules (contents opaque)
  body+8209 74 02 <u16 BE>            small element; the u16 is the
                                      FIRST per-module field in the body
  body+8213 0x73                      section marker
  --- init.ocm / device.sal diverge right after the 0x7E ---
  body+13   INT2 <u16>                (02 <2 content bytes>)
  body+16   0x73                      section marker

Why the class-01 family shares exactly 8,211 body bytes (the oracle):
  12 (head values) + 1 (0x7E) + 4 (STR header) + 8192 (shared chunk)
  + 2 (74 02 header) = 8211. The next byte (+8211) is the first byte of
  the per-module u16; the 23 modules whose u16 high byte is also 0x49
  share 8,212 bytes instead. Prefix sharing is a framing artifact,
  not a transform artifact.

sal_dis.py's strict grammar dies at body+12 (family) / wanders ~210
bytes on init.ocm. This skeleton grammar parses 8,214 bytes of family
structure (17 bytes for init.ocm / device.sal) — the identified first
stage of the stored-form recovery. Everything past the skeleton
(the chunk contents, and all bytes from +8214 on) remains opaque:
no transform for the contents is claimed here.

Usage: sal_skeleton.py FILE...        parse specific files
       sal_skeleton.py --corpus DIR   validate over a directory of
                                      .ocm/.sal files
"""

import hashlib
import os
import sys

FAMILY_ID = bytes.fromhex("6a35a21d8c3c2c0c")
MARK_OPEN = 0x7E
MARK_NEXT = 0x73


class Fail(Exception):
    pass


def split_container(d):
    """Return (body, container_note). Mirrors sal_dis.body_of."""
    if d[:2] == b"\xff\xff" and len(d) <= 64:
        return d, "stub"
    if len(d) >= 5 and d[:5] == bytes([0x04, 0x83, 0x08, 0x47, 0x50]):
        return d[15:], "init.ocm wrapper + 10B header"
    if len(d) >= 10 and d[0] == 0x03:
        return d[10:], f"10B header, class {d[1]:#04x}"
    return d, "raw"


def parse_skeleton(body):
    """Parse the framing skeleton; return (events, structured_span)."""
    ev = []
    if len(body) < 13:
        raise Fail("body shorter than the 13-byte head")
    # +0 INT1
    if body[0] != 0x01:
        raise Fail(f"+0: expected INT1 tag 0x01, got {body[0]:#04x}")
    ev.append((0, f"INT1 {body[1]}"))
    # +2 STR[8] family id
    if body[2] != 0x04 or body[3] != 0x08:
        raise Fail(f"+2: expected STR[8] header 04 08, got "
                   f"{body[2]:#04x} {body[3]:#04x}")
    fid = body[4:12]
    ev.append((2, f"STR[8] {fid.hex()}" +
               (" (family id)" if fid == FAMILY_ID else " (NOT the family id)")))
    # +12 section marker
    if body[12] != MARK_OPEN:
        raise Fail(f"+12: expected 0x7E marker, got {body[12]:#04x}")
    ev.append((12, "MARK 0x7E"))
    # family path: 04 82 <u16> shared chunk
    if body[13:15] == b"\x04\x82":
        ln = int.from_bytes(body[15:17], "big")
        ev.append((13, f"STR[{ln}] shared chunk (contents opaque)"))
        p = 17 + ln
        if p + 5 > len(body):
            raise Fail("chunk overruns body")
        if body[p] != 0x74 or body[p + 1] != 0x02:
            raise Fail(f"+{p}: expected 74 02 element, got "
                       f"{body[p]:#04x} {body[p + 1]:#04x}")
        field = int.from_bytes(body[p + 2:p + 4], "big")
        ev.append((p, f"ELT 0x74 len2, per-module u16 = {field:#06x} ({field})"))
        p += 4
        if body[p] != MARK_NEXT:
            raise Fail(f"+{p}: expected 0x73 marker, got {body[p]:#04x}")
        ev.append((p, "MARK 0x73"))
        return ev, p + 1
    # init.ocm / device.sal path: INT2 then 0x73
    if body[13] == 0x02:
        val = int.from_bytes(body[14:16], "big", signed=True)
        ev.append((13, f"INT2 {val} ({body[14:16].hex()})"))
        if body[16] != MARK_NEXT:
            raise Fail(f"+16: expected 0x73 marker, got {body[16]:#04x}")
        ev.append((16, "MARK 0x73"))
        return ev, 17
    raise Fail(f"+13: no skeleton continuation (byte {body[13]:#04x})")


def parse_file(path, verbose=True):
    d = open(path, "rb").read()
    body, note = split_container(d)
    try:
        ev, span = parse_skeleton(body)
    except Fail as f:
        if verbose:
            print(f"{os.path.basename(path)}: NO SKELETON ({note}) — {f}")
        return None
    if verbose:
        print(f"{os.path.basename(path)}: skeleton span {span} B ({note})")
        for off, txt in ev:
            print(f"    body+{off:<6} {txt}")
        if span > 100:
            chunk = body[17:17 + 8192]
            print(f"    chunk sha256 = {hashlib.sha256(chunk).hexdigest()}")
    return body, ev, span


def corpus(dirpath):
    names = sorted(n for n in os.listdir(dirpath)
                   if n.endswith(".ocm") or n.endswith(".sal"))
    fam = []
    others = []
    for n in names:
        r = parse_file(os.path.join(dirpath, n), verbose=False)
        if r and r[2] > 100:
            fam.append((n, r))
        else:
            others.append((n, r))
    print(f"corpus: {len(names)} files; family skeleton in {len(fam)}, "
          f"other/no skeleton in {len(others)}")
    chunks = {hashlib.sha256(r[0][17:17 + 8192]).digest() for _, r in fam}
    print(f"family shared-chunk distinct sha256 count: {len(chunks)} "
          f"(1 = byte-identical in all)")
    fields = {}
    for n, r in fam:
        u16 = int.from_bytes(r[0][8211:8213], "big")
        fields.setdefault(u16, []).append(n)
    print("per-module u16 at +8211:",
          {hex(k): len(v) for k, v in sorted(fields.items())})
    for n, r in others:
        span = r[2] if r else 0
        print(f"  non-family: {n} (skeleton span {span})")
    # the oracle arithmetic
    assert 12 + 1 + 4 + 8192 + 2 == 8211
    print("oracle: 12 + 1 + 4 + 8192 + 2 = 8211 = the family's shared "
          "prefix length; first per-module byte is +8211 (the u16)")


# ---------------------------------------------------------------------
# Phase 5 extensions (stage0-readout-15): continuation + class-02 form.
#
# Class-01 continuation: past the skeleton (body+8214) there is NO
# further plaintext framing — strict SalAsn dies on the first byte and
# a generic BER walk dies within 0-5 chance elements on absurd length
# fields, in all 25 modules. The continuation is uniformly high
# entropy (~7.8 bits/byte in every 1 KiB window, head and tail), i.e.
# opaque contents in the same stored encoding as the STR[8192]
# chunk's contents. It is NOT one undifferentiated blob, though:
# modules sharing the skeleton u16 share long exact continuations
# (pairwise common prefixes of 8,553 / 10,538 / 12,662 bytes and
# near-whole-body matches), so the continuation is deterministic,
# template/block-shared stored content. parse_continuation() reports
# exactly that, and claims no elements past +8214.
#
# Class-02 stored form: no skeleton, no family identifier, and no
# substring of the shared chunk (>= 16 bytes, exact, constant-XOR, or
# constant-add) occurs at ANY offset in any class-02 body. Class-02
# bodies instead form head clusters sharing long opaque prefixes
# (~8,468-8,471 bytes; one pair is body-identical). class02_profile()
# and corpus_phase5() map that form.
# ---------------------------------------------------------------------

import math
from collections import Counter


def _entropy(data):
    if not data:
        return 0.0
    c = Counter(data)
    n = len(data)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def _common_prefix(a, b):
    i = 0
    for x, y in zip(a, b):
        if x != y:
            break
        i += 1
    return i


def parse_continuation(body):
    """Class-01: describe the post-skeleton continuation (+8214..EOF).

    Returns a dict, or None if the body has no family skeleton.
    No structure past +8214 is claimed — see the phase-5 note above.
    """
    try:
        _ev, span = parse_skeleton(body)
    except Fail:
        return None
    if span != 8214:
        return None
    cont = body[8214:]
    return {
        "skeleton_span": span,
        "u16": int.from_bytes(body[8211:8213], "big"),
        "continuation_off": 8214,
        "continuation_len": len(cont),
        "continuation_entropy": round(_entropy(cont), 3),
        "continuation_sha256": hashlib.sha256(cont).hexdigest(),
    }


def class02_profile(body):
    """Class-02: profile a body that carries no class-01 skeleton."""
    return {
        "length": len(body),
        "entropy": round(_entropy(body), 3),
        "head4": body[:4].hex(),
        "skeleton": False,
    }


def find_fingerprint_offsets(body, chunk, min_len=16):
    """Hypothesis-1 test as a reusable check: exact offsets of the
    family identifier or of any >= min_len substring of the shared
    chunk inside `body`. Empty on every class-02 body in the corpus.
    """
    hits = []
    i = body.find(FAMILY_ID)
    if i >= 0:
        hits.append(("family_id", i))
    kmers = {chunk[i:i + min_len] for i in range(len(chunk) - min_len + 1)}
    for j in range(len(body) - min_len + 1):
        if body[j:j + min_len] in kmers:
            hits.append(("chunk_substring", j))
            break
    return hits


def corpus_phase5(dirpath):
    names = sorted(n for n in os.listdir(dirpath)
                   if n.endswith(".ocm") or n.endswith(".sal"))
    fam, c2, other = [], [], []
    for n in names:
        d = open(os.path.join(dirpath, n), "rb").read()
        body, note = split_container(d)
        pc = parse_continuation(body)
        if pc:
            fam.append((n, body, pc))
        elif len(d) > 10 and d[0] == 0x03 and d[1] == 0x02:
            c2.append((n, body))
        else:
            other.append(n)
    print(f"phase5 corpus: {len(fam)} class-01 family, "
          f"{len(c2)} class-02, {len(other)} other/stub")
    print("\nclass-01 continuations (past the +8214 skeleton):")
    for n, body, pc in fam:
        best = max((_common_prefix(body, b2) for n2, b2, _ in fam
                    if n2 != n), default=0)
        print(f"  {n:16} u16={pc['u16']:#06x} body={len(body):6} "
              f"cont={pc['continuation_len']:6} H={pc['continuation_entropy']} "
              f"max pairwise common prefix={best}")
    print("\nclass-02 head clusters (bodies sharing a >=64 B prefix):")
    clustered = set()
    for i, (n1, b1) in enumerate(c2):
        for n2, b2 in c2[i + 1:]:
            c = _common_prefix(b1, b2)
            if c >= 64:
                print(f"  CP={c:6}  {n1} / {n2}  head4={b1[:4].hex()}")
                clustered.add(n1)
                clustered.add(n2)
    solo = [n for n, _ in c2 if n not in clustered]
    print(f"  class-02 bodies in no >=64 B prefix cluster: {len(solo)}")
    chunk = fam[0][1][17:17 + 8192] if fam else b""
    fp = {n: find_fingerprint_offsets(b, chunk) for n, b in c2}
    print("class-02 fingerprint hits (family id / chunk substring):",
          {n: h for n, h in fp.items() if h} or "none")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--corpus5":
        corpus_phase5(args[1])
    elif args and args[0] == "--corpus":
        corpus(args[1])
    else:
        for p in args:
            parse_file(p)
