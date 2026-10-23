"""Phase 7 opening probes (readout #17):
P7.1  STR[8192] chunk forensics: known-constant scan + structure.
P7.2  Continuation lag-IC scan: is there a periodic keystream?
P7.3  init.ocm body profile (it is neither class-01 nor class-02).
"""
import hashlib
import math
import os
import struct

CORPUS = os.path.expanduser(
    "~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG")


import sal_skeleton


def load():
    out = {}
    for n in sorted(os.listdir(CORPUS)):
        if n.endswith(".ocm") or n.endswith(".sal"):
            with open(os.path.join(CORPUS, n), "rb") as f:
                out[n] = f.read()
    return out


def body(data):
    b, _note = sal_skeleton.split_container(data)
    return b


def classify(name, raw):
    """Mirrors sal_blockpool.Mod exactly."""
    if raw[:2] == b"\xff\xff" and len(raw) <= 64:
        return "stub"
    if name == "init.ocm":
        return "init"
    if name == "device.sal":
        return "sal"
    if len(raw) >= 10 and raw[0] == 0x03 and raw[1] == 0x01:
        return "c1"
    if len(raw) >= 10 and raw[0] == 0x03 and raw[1] == 0x02:
        return "c2"
    return "other"


def entropy(data):
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts if c)


# ---------------------------------------------------------------- P7.1
AES_SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf")
AES_INV_SBOX = bytes.fromhex(
    "52096ad53036a538bf40a39e81f3d7fb7ce339829e2f2c87964a4c68b4224a")
SHA256_H = struct.pack(">8I", 0x6a09e667, 0xbb67ae85, 0x3c6ef372,
                       0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
                       0x5be0cd19)
SHA256_K = struct.pack(">4I", 0x428a2f98, 0x71374491, 0xb5c0fbcf,
                       0xe9b5dba5)
SHA1_H = struct.pack(">5I", 0x67452301, 0xEFCDAB89, 0x98BADCFE,
                     0x10325476, 0xC3D2E1F0)
MD5_K0 = struct.pack("<I", 0xd76aa478)
BLOWFISH_P = bytes.fromhex("243f6a8885a308d313198a2e03707344")
TEA_DELTA = struct.pack(">I", 0x9E3779B9)
PI_HEX = bytes.fromhex("243f6a8885a308d313198a2e03707344"
                       "a4093822299f31d0082efa98ec4e6c89")


def crc32_table(poly, refin):
    tab = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ poly if (c & 1) else c >> 1
        tab.append(c)
    fmt = "<256I" if refin else ">256I"
    return struct.pack(fmt, *tab)


CONSTANTS = {
    "AES S-box[0:64]": AES_SBOX[:64],
    "AES inv S-box[0:32]": AES_INV_SBOX,
    "SHA-256 H": SHA256_H,
    "SHA-256 K[0:4]": SHA256_K,
    "SHA-1 H": SHA1_H,
    "MD5 K[0] (LE)": MD5_K0,
    "Blowfish P (pi hex)": BLOWFISH_P,
    "pi hex 32B": PI_HEX,
    "CRC32 table LE (0xEDB88320)[0:8w]": crc32_table(0xEDB88320, True)[:32],
    "CRC32 table BE (0x04C11DB7)[0:8w]": crc32_table(0x04C11DB7, False)[:32],
}


def scan_constants(chunk):
    hits = []
    for name, pat in CONSTANTS.items():
        for plen in (len(pat), 16, 8):
            if plen > len(pat):
                continue
            idx = chunk.find(pat[:plen])
            if idx >= 0:
                hits.append((name, plen, idx))
                break
    # TEA delta repeated would still be a single 4-byte pattern: too
    # weak alone; count occurrences instead
    n_delta = chunk.count(TEA_DELTA) + chunk.count(
        struct.pack("<I", 0x9E3779B9))
    return hits, n_delta


def lag_ic(data, lags):
    """Fraction of equal byte pairs at each lag."""
    res = {}
    for lag in lags:
        n = len(data) - lag
        if n <= 0:
            continue
        eq = sum(1 for i in range(n) if data[i] == data[i + lag])
        res[lag] = eq / n
    return res


def main():
    files = load()
    c01 = {n: d for n, d in files.items() if classify(n, d) == "c1"}
    others = [(n, classify(n, d)) for n, d in files.items()
              if classify(n, d) not in ("c1", "c2")]
    print(f"class-01 modules: {len(c01)}; non-c1/c2: {others}")

    chunks = {}
    for n, d in c01.items():
        b = body(d)
        chunks[n] = b[17:17 + 8192]
    first = next(iter(chunks.values()))
    print("chunk identical across all class-01:",
          all(c == first for c in chunks.values()))
    chunk = first
    print(f"chunk sha256: {hashlib.sha256(chunk).hexdigest()}")
    print(f"chunk entropy: {entropy(chunk):.3f} bits/byte")
    per = [entropy(chunk[i:i + 512]) for i in range(0, 8192, 512)]
    print("chunk entropy per 512B block:",
          " ".join(f"{e:.2f}" for e in per))
    hits, n_delta = scan_constants(chunk)
    print("constant hits:", hits if hits else "NONE")
    print(f"TEA delta occurrences (BE+LE): {n_delta}")
    strings = []
    cur = bytearray()
    for b in chunk:
        if 32 <= b < 127:
            cur.append(b)
        else:
            if len(cur) >= 6:
                strings.append(bytes(cur).decode())
            cur = bytearray()
    print("ASCII strings >=6 in chunk:", strings[:10] if strings else "NONE")
    ic = lag_ic(chunk, [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024,
                        2048, 4096])
    print("chunk lag-IC:", {k: round(v, 4) for k, v in ic.items()},
          "(random ~= 0.0039)")

    # ------------------------------------------------------------ P7.2
    conts = [body(d)[8214:] for d in c01.values()]
    pooled = b"\x00".join(conts)  # separator breaks cross-file lags
    lags = [1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 24, 32, 48, 64, 96, 128,
            192, 256, 384, 512, 768, 1024, 2048, 4096, 8192]
    ic = lag_ic(pooled, lags[0:0])  # placeholder
    # per-file averaged IC (avoids separator artifacts)
    agg = {}
    for lag in lags:
        tot_eq = tot_n = 0
        for c in conts:
            n = len(c) - lag
            if n <= 0:
                continue
            tot_eq += sum(1 for i in range(n) if c[i] == c[i + lag])
            tot_n += n
        agg[lag] = tot_eq / tot_n if tot_n else 0
    spikes = {k: round(v, 4) for k, v in agg.items() if v > 0.0055}
    print("continuation lag-IC spikes (>0.0055):",
          spikes if spikes else "NONE")
    print("continuation lag-IC sample:",
          {k: round(agg[k], 4) for k in (1, 8, 64, 256, 1024, 4096)})

    # ------------------------------------------------------------ P7.3
    init = files.get("init.ocm")
    if init:
        b = body(init)
        print(f"\ninit.ocm: file {len(init)} B, split body {len(b)} B, "
              f"body[:32] = {b[:32].hex()}")
        print(f"  body[12] = {b[12]:#04x} (0x7e = class-01 marker), "
              f"entropy(body) = {entropy(b):.3f}")
        print(f"  entropy first 8KB: {entropy(b[:8192]):.3f}, "
              f"rest: {entropy(b[8192:]):.3f}")
        # how far does init share a prefix with a class-01 body?
        ref = body(next(iter(c01.values())))
        cp = 0
        for x, y in zip(b, ref):
            if x != y:
                break
            cp += 1
        print(f"  common prefix with a class-01 body: {cp} B")


if __name__ == "__main__":
    main()
