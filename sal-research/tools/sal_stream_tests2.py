#!/usr/bin/env python3
"""Phase 2 step 1, round 2: strict deflate criteria + more TLV variants.

Round 1 accepted partial raw-deflate fragments; every one produced short,
periodic garbage (96-525 B, image score <= 3). This round requires a REAL
stream end (decompressobj.eof) for a deflate hit, re-scans wider, tries
gzip framing too, inflates TLV payloads, and walks additional TLV
conventions (tag + 1-byte length, tag + u16le length, tag + u32le length),
checking whether any element boundary lands on the sharing offsets
(body-relative 8211 for class-01, 8471 for atpcd/lgd).
"""
import os, zlib, struct
import importlib.util
spec = importlib.util.spec_from_file_location(
    "t1", os.path.expanduser("~/workspace/atrac-salwrap-work/sal_stream_tests.py"))
t1 = importlib.util.module_from_spec(spec)
import sys; sys.modules["t1"] = t1
# avoid running main() of t1
src = open(os.path.expanduser("~/workspace/atrac-salwrap-work/sal_stream_tests.py")).read()
src = src.replace('if __name__ == "__main__":\n    main()', "")
exec(compile(src, "sal_stream_tests.py", "exec"), t1.__dict__)

files = t1.load_files()
real = {}
for name, data in files.items():
    if data != b"\xff\xff" and len(data) > 10 and data[0] == 0x03:
        real[name] = data

def strict_inflate(data, wbits):
    try:
        obj = zlib.decompressobj(wbits)
        out = obj.decompress(data, 1 << 24)
        out += obj.flush()
        if obj.eof and out:
            return out, len(data) - len(obj.unused_data)
        return None, 0
    except zlib.error:
        return None, 0

print("== strict deflate (eof required): offsets 0..8192, all files, zlib/raw/gzip ==")
hits = 0
for name, data in sorted(real.items()):
    top = min(len(data) - 2, 8192)
    for start in range(0, top):
        for wb, wn in ((15, "zlib"), (-15, "raw"), (31, "gzip")):
            out, consumed = strict_inflate(data[start:], wb)
            if out is not None:
                s, d = t1.score_image(out)
                hits += 1
                print("  EOF-HIT %s start=%d %s consumed=%d out=%d imgscore=%d name=%r" %
                      (name, start, wn, consumed, len(out), s, d.get("name")))
print("  strict hits:", hits)

print("\n== strict deflate (eof required): ALL offsets, representative set ==")
hits = 0
for name in ("atpcd.ocm", "icv.ocm", "device.sal", "init2.ocm", "lgd.ocm"):
    data = real.get(name) or files.get(name)
    if not data: continue
    for start in range(0, len(data) - 2):
        for wb, wn in ((15, "zlib"), (-15, "raw")):
            out, consumed = strict_inflate(data[start:], wb)
            if out is not None and len(out) >= 16:
                s, d = t1.score_image(out)
                hits += 1
                print("  EOF-HIT %s start=%d %s consumed=%d out=%d imgscore=%d name=%r" %
                      (name, start, wn, consumed, len(out), s, d.get("name")))
print("  strict hits (out>=16):", hits)

print("\n== TLV payload inflate attempts (salasn walk payloads >= 16 B) ==")
n = 0
for name in ("icv.ocm", "device.sal", "ekbman.ocm", "atpcd.ocm"):
    data = real.get(name) or files.get(name)
    if not data: continue
    body = data[10:]
    elems, endpos, status = t1.walk(body, "salasn")
    for (off, tag, poff, ln) in elems:
        if ln >= 16:
            for wb, wn in ((15, "zlib"), (-15, "raw")):
                out, consumed = strict_inflate(body[poff:poff+ln], wb)
                if out is not None:
                    n += 1
                    print("  payload hit %s elem@%d tag=%d %s out=%d" % (name, off, tag, wn, len(out)))
print("  payload hits:", n)

print("\n== extra TLV variants: element-boundary check vs sharing offsets ==")
def walk_fixed(buf, lenfmt):
    """tag byte + fixed-size length (1B, <H, <I). Returns (elems, endpos)."""
    elems = []; pos = 0
    while pos < len(buf):
        start = pos; tag = buf[pos]; pos += 1
        if lenfmt == "B":
            if pos + 1 > len(buf): break
            ln = buf[pos]; pos += 1
        elif lenfmt == "<H":
            if pos + 2 > len(buf): break
            ln = struct.unpack_from("<H", buf, pos)[0]; pos += 2
        else:
            if pos + 4 > len(buf): break
            ln = struct.unpack_from("<I", buf, pos)[0]; pos += 4
        if pos + ln > len(buf):
            return elems, start
        elems.append((start, tag, pos, ln)); pos += ln
    return elems, pos

for name, targets in (("icv.ocm", (8211,)), ("atpcd.ocm", (8471,)), ("device.sal", ())):
    data = real.get(name) or files.get(name)
    if not data: continue
    body = data[10:]
    for variant in ("B", "<H", "<I"):
        elems, endpos = walk_fixed(body, variant)
        ends = {p + l for (_, _, p, l) in elems}
        mark = " BOUNDARY-HIT %s" % (targets,) if any(t in ends for t in targets) else ""
        print("  %-12s lenfmt=%-3s elems=%d endpos=%d/%d%s" %
              (name, variant, len(elems), endpos, len(body), mark))
    elems, endpos, status = t1.walk(body, "salasn")
    ends = {p + l for (_, _, p, l) in elems}
    mark = " BOUNDARY-HIT %s" % (targets,) if any(t in ends for t in targets) else ""
    print("  %-12s salasn    elems=%d endpos=%d/%d %s%s" %
          (name, len(elems), endpos, len(body), status, mark))
    elems, endpos, status = t1.walk(body, "der")
    ends = {p + l for (_, _, p, l) in elems}
    mark = " BOUNDARY-HIT %s" % (targets,) if any(t in ends for t in targets) else ""
    print("  %-12s der       elems=%d endpos=%d/%d %s%s" %
          (name, len(elems), endpos, len(body), status, mark))
