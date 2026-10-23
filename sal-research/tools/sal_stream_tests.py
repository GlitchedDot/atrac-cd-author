#!/usr/bin/env python3
"""SAL container attack, phase 2 step 1: stream-hypothesis tests.

Tests, per the phase-2 plan in readout #10 section 8.1:
  (1) SalAsn TLV parse of .ocm bodies from offset 10
      - conventions from the SalAsn encoders in salwrap (FUN_65124cc0
        INTEGER: first byte 1/2 = implied 1/2-byte payload, 3 = DER-length
        integer; FUN_65125020 OCTET STRING: first byte 4 = DER-length
        octet string). Generic DER fallback for other tag bytes.
  (2) zlib / raw-deflate decompression attempts at plausible start
      boundaries (offsets 10..1033 of every file; ALL offsets for a
      representative set), plus inside TLV payloads found by (1).
  (3) Direct image-format scoring of bodies / decompressed outputs
      against the reconstructed image format (readout #10 section 2.1):
      0x60-byte header, name at +0x3E (8 B, 'bc' = bytecode marker),
      type byte +0x46, compression flag +0x47 in {0,1}, u32le entry
      offset +0x4C, u32le symbol offset +0x50, u16le symbol count
      +0x56, u32le reloc offset +0x58, u32le reloc size +0x5C
      (multiple of 8, in range).
"""
import os, sys, zlib, math, collections

ROOT = os.path.expanduser("~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG")

def load_files():
    files = {}
    for name in sorted(os.listdir(ROOT)):
        if name.lower().endswith(".ocm") or name.lower() == "device.sal":
            with open(os.path.join(ROOT, name), "rb") as f:
                files[name] = f.read()
    pdir = os.path.join(ROOT, "procfile")
    if os.path.isdir(pdir):
        for name in sorted(os.listdir(pdir)):
            if name.lower() == "device.sal":
                with open(os.path.join(pdir, name), "rb") as f:
                    files["procfile/device.sal"] = f.read()
    return files

def shannon(b):
    if not b: return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

# ---------- image-format scorer (readout #10 section 2.1) ----------
def score_image(buf):
    """Return (score, details) for buf as a candidate formed module image."""
    d = {}
    if len(buf) < 0x60:
        return 0, {"reason": "shorter than 0x60-byte header"}
    name = buf[0x3E:0x46]
    printable = all(0x20 <= c < 0x7F for c in name.rstrip(b"\x00")[:7]) and name[0] != 0
    d["name"] = name
    d["name_printable"] = printable
    d["is_bc"] = name[:2] == b"bc"
    d["type_byte"] = buf[0x46]
    d["cflag"] = buf[0x47]
    import struct
    d["entry"] = struct.unpack_from("<I", buf, 0x4C)[0]
    d["sym_off"] = struct.unpack_from("<I", buf, 0x50)[0]
    d["sym_count"] = struct.unpack_from("<H", buf, 0x56)[0]
    d["reloc_off"] = struct.unpack_from("<I", buf, 0x58)[0]
    d["reloc_size"] = struct.unpack_from("<I", buf, 0x5C)[0]
    s = 0
    if printable: s += 2
    if d["is_bc"]: s += 2
    if buf[0x46] in (0x73, 0x00) or 0x20 <= buf[0x46] < 0x7F: s += 1  # 's' observed
    if d["cflag"] in (0, 1): s += 2
    if 0 < d["entry"] < len(buf): s += 2
    if d["sym_off"] == 0 or d["sym_off"] < len(buf): s += 1
    if d["reloc_off"] == 0 or d["reloc_off"] < len(buf): s += 1
    if d["reloc_size"] % 8 == 0 and d["reloc_off"] + d["reloc_size"] <= len(buf): s += 2
    d["score"] = s
    return s, d

# ---------- SalAsn / DER TLV walking ----------
def der_length(buf, pos):
    """DER length at pos -> (length, next_pos) or (None, pos)."""
    if pos >= len(buf): return None, pos
    b0 = buf[pos]
    if b0 < 0x80:
        return b0, pos + 1
    n = b0 & 0x7F
    if n == 0 or n > 4 or pos + 1 + n > len(buf):
        return None, pos
    ln = int.from_bytes(buf[pos+1:pos+1+n], "big")
    return ln, pos + 1 + n

def walk(buf, variant="salasn", max_elems=100000):
    """Walk a TLV stream. Returns list of (offset, tag, payload_off, len)."""
    elems = []
    pos = 0
    while pos < len(buf) and len(elems) < max_elems:
        start = pos
        tag = buf[pos]; pos += 1
        if variant == "salasn" and tag == 1:
            ln = 1; poff = pos; pos += 1
        elif variant == "salasn" and tag == 2:
            ln = 2; poff = pos; pos += 2
        else:
            ln, pos2 = der_length(buf, pos)
            if ln is None:
                return elems, start, "bad DER length at %d" % start
            poff = pos2; pos = pos2
        if poff + ln > len(buf):
            return elems, start, "payload overruns end (tag %d len %d at %d, %d left)" % (
                tag, ln, start, len(buf) - poff)
        elems.append((start, tag, poff, ln))
        pos = poff + ln
    return elems, pos, ("consumed-exact" if pos == len(buf) else "stopped at %d/%d" % (pos, len(buf)))

# ---------- deflate attempts ----------
def try_inflate(data, wbits):
    """Return output bytes if a stream produces output and ends or nearly
    ends cleanly; else None. Accepts obj.eof, or a long output whose tail
    consumes almost all input."""
    try:
        obj = zlib.decompressobj(wbits)
        out = obj.decompress(data, 1 << 22)
        out += obj.flush()
        if not out:
            return None
        if obj.eof:
            return out
        # partial: keep only if we got a substantial, header-sized output
        if len(out) >= 0x60 and len(obj.unused_data) == 0 and len(obj.unconsumed_tail) == 0:
            return out
        return None
    except zlib.error:
        return None

def main():
    files = load_files()
    print("== inventory ==")
    classes = collections.Counter()
    real = {}
    for name, data in files.items():
        if data == b"\xff\xff":
            classes["stub"] += 1; continue
        if len(data) >= 10 and data[0] == 0x03:
            import struct
            major = struct.unpack_from("<H", data, 4)[0]
            build = struct.unpack_from("<I", data, 6)[0]
            key = (data[1], major, build)
            classes[key] += 1
            real[name] = data
        else:
            classes[("other", name)] += 1
    for k, v in sorted(classes.items(), key=lambda kv: str(kv[0])):
        print("  ", k, v)
    c01 = {n: d for n, d in real.items() if d[1] == 1 and len(d) > 10 and
           __import__("struct").unpack_from("<H", d, 4)[0] == 5}
    c02 = {n: d for n, d in real.items() if d[1] == 2}
    print("class-01 (hdr v5) count:", len(c01))
    # shared preamble length among class-01
    if c01:
        ref = next(iter(c01.values()))
        shared = len(ref)
        for d in c01.values():
            i = 0
            while i < min(len(d), shared) and i < len(ref) and d[i] == ref[i]:
                i += 1
            shared = min(shared, i)
        print("class-01 common prefix (file bytes, incl 10B header):", shared)
    if "atpcd.ocm" in real and "lgd.ocm" in real:
        a, b = real["atpcd.ocm"], real["lgd.ocm"]
        i = 0
        while i < min(len(a), len(b)) and a[i] == b[i]: i += 1
        print("atpcd/lgd common prefix (file bytes):", i)
    print("device.sal size / body head:", len(files.get("device.sal", b"")),
          files.get("device.sal", b"")[10:26].hex())

    print("\n== direct image scoring of raw bodies (offset 10) and whole files ==")
    for name in ("atpcd.ocm", "icv.ocm", "init2.ocm", "region.ocm"):
        if name in real:
            for off in (0, 10):
                s, d = score_image(real[name][off:])
                print("  %-14s off=%2d score=%2d name=%r cflag=%s entry=%s reloc=%s+%s" %
                      (name, off, s, d.get("name"), d.get("cflag"), d.get("entry"),
                       d.get("reloc_off"), d.get("reloc_size")))
    ds = files.get("device.sal")
    if ds:
        s, d = score_image(ds[10:])
        print("  device.sal body score=%d name=%r" % (s, d.get("name")))

    print("\n== SalAsn TLV walk (variant salasn) ==")
    for name in ("atpcd.ocm", "icv.ocm", "ekbman.ocm", "init2.ocm"):
        if name not in real: continue
        body = real[name][10:]
        elems, endpos, status = walk(body, "salasn")
        print("  %-14s elems=%d endpos=%d/%d %s" % (name, len(elems), endpos, len(body), status))
        for (off, tag, poff, ln) in elems[:12]:
            print("     @%-6d tag=%-3d len=%-6d payload[:12]=%s" %
                  (off, tag, ln, body[poff:poff+12].hex()))
        ends = {poff + ln for (_, _, poff, ln) in elems}
        for target, label in ((8211, "class-01 shared body len 8211"),
                              (8471, "atpcd/lgd shared body len 8471")):
            if target in ends:
                print("     ** element boundary lands on", label)
    if ds:
        body = ds[10:]
        elems, endpos, status = walk(body, "salasn")
        print("  %-14s elems=%d endpos=%d/%d %s" % ("device.sal", len(elems), endpos, len(body), status))
        for (off, tag, poff, ln) in elems[:12]:
            print("     @%-6d tag=%-3d len=%-6d payload[:12]=%s" %
                  (off, tag, ln, body[poff:poff+12].hex()))

    print("\n== strict DER walk (variant der) ==")
    for name in ("atpcd.ocm", "icv.ocm"):
        if name not in real: continue
        body = real[name][10:]
        elems, endpos, status = walk(body, "der")
        print("  %-14s elems=%d endpos=%d/%d %s" % (name, len(elems), endpos, len(body), status))

    print("\n== deflate scan: offsets 10..1033, all real modules + device.sal ==")
    hits = []
    pool = dict(real)
    if ds: pool["device.sal"] = ds
    for name, data in sorted(pool.items()):
        for start in range(10, min(len(data), 1034)):
            for wb, wname in ((15, "zlib"), (-15, "raw")):
                out = try_inflate(data[start:], wb)
                if out is not None and len(out) >= 0x60:
                    s, d = score_image(out)
                    hits.append((name, start, wname, len(out), s, d))
                    print("  HIT? %s start=%d %s out=%d imgscore=%d name=%r" %
                          (name, start, wname, len(out), s, d.get("name")))
    if not hits:
        print("  no decompressions >= 0x60 bytes in scanned window")

    print("\n== deflate scan: ALL offsets, representative set ==")
    reps = [n for n in ("atpcd.ocm", "icv.ocm", "init2.ocm", "lgd.ocm", "device.sal") if n in pool]
    hits2 = []
    for name in reps:
        data = pool[name]
        for start in range(10, len(data) - 2):
            for wb, wname in ((15, "zlib"), (-15, "raw")):
                out = try_inflate(data[start:], wb)
                if out is not None and len(out) >= 0x60:
                    s, d = score_image(out)
                    hits2.append((name, start, wname, len(out), s))
                    print("  HIT? %s start=%d %s out=%d imgscore=%d name=%r cflag=%s" %
                          (name, start, wname, len(out), s, d.get("name"), d.get("cflag")))
    if not hits2:
        print("  no decompressions >= 0x60 bytes at any offset in representative set")

    print("\n== body byte structure ==")
    for name in ("atpcd.ocm", "icv.ocm"):
        if name in real:
            body = real[name][10:]
            print("  %s body[:32]=%s entropy=%.3f" % (name, body[:32].hex(), shannon(body)))
            # zlib magic scan
            zm = [i for i in range(len(body) - 1) if body[i] == 0x78 and body[i+1] in (0x01, 0x5E, 0x9C, 0xDA)]
            print("    0x78?? zlib-magic candidates in body:", zm[:20], "count", len(zm))

if __name__ == "__main__":
    main()
