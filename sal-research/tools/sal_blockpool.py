#!/usr/bin/env python3
"""sal_blockpool.py — SAL attack phase 6: block-pool analysis.

Question: are .ocm bodies built from shared blocks drawn from a pool,
and what distinguishes the plaintext-framed blocks (class-01 skeleton)
from the opaque ones? Builds on readouts #14 (skeleton anatomy) and
#15 (class-01 continuation groups by skeleton u16; class-02 prefix
clusters). All offsets are BODY offsets (file offset - 10), matching
sal_skeleton.py / the phase-4/5 notes.

Subcommands (each appends evidence to out/phase6-notes.txt and prints
a summary):
  inventory   block decomposition at B in {256,512,1024,2048,4096},
              several origins; sharing graph; shuffled-byte control;
              offset-agnostic 64-mer interior-sharing census.
  quantize    do pairwise divergence points quantize to a block grid?
  groups      construction hypothesis: class-01 u16 groups vs block
              sequences + permutation control; class-02 container
              headers vs clusters.
  transforms  framed-vs-opaque: cross-region block overlap (exact and
              under fixed byte transforms), parse-depth battery
              (sal_dis) on opaque regions under transforms, with
              shuffled controls.
  atpcd       atpcd.ocm's block sequence, labeled shared/unique.

Static analysis only; nothing is executed.
"""

import hashlib
import math
import os
import random
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sal_skeleton
import sal_dis

CORPUS = os.path.expanduser(
    "~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG")
NOTES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "out", "phase6-notes.txt")
BLOCK_SIZES = (256, 512, 1024, 2048, 4096)
SKEL_END = 8214          # class-01 skeleton span (readout #14)
CHUNK_OFF = 17           # class-01 STR[8192] contents start
C2_BOUND = 8471          # canonical class-02 cluster boundary

_logf = None


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    if _logf:
        _logf.write(s + "\n")
        _logf.flush()


def entropy(data):
    if not data:
        return 0.0
    c = Counter(data)
    n = len(data)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def common_prefix(a, b):
    i = 0
    for x, y in zip(a, b):
        if x != y:
            break
        i += 1
    return i


# ---------------------------------------------------------------- corpus

class Mod:
    def __init__(self, name, raw):
        self.name = name
        self.raw = raw
        body, note = sal_skeleton.split_container(raw)
        self.body = body
        self.note = note
        if raw[:2] == b"\xff\xff" and len(raw) <= 64:
            self.cls = "stub"
        elif name == "init.ocm":
            self.cls = "init"
        elif name == "device.sal":
            self.cls = "sal"
        elif len(raw) >= 10 and raw[0] == 0x03 and raw[1] == 0x01:
            self.cls = "c1"
        elif len(raw) >= 10 and raw[0] == 0x03 and raw[1] == 0x02:
            self.cls = "c2"
        else:
            self.cls = "other"
        self.u16 = None
        if self.cls == "c1" and len(body) >= 8213:
            self.u16 = int.from_bytes(body[8211:8213], "big")


def load_corpus():
    names = sorted(n for n in os.listdir(CORPUS)
                   if n.endswith(".ocm") or n.endswith(".sal"))
    mods = []
    for n in names:
        with open(os.path.join(CORPUS, n), "rb") as f:
            mods.append(Mod(n, f.read()))
    return mods


def shuffled(body, seed):
    b = bytearray(body)
    random.Random(seed).shuffle(b)
    return bytes(b)


# ---------------------------------------------------------------- blocks

def blocks_of(data, size, origin=0):
    """Yield (index, offset, bytes) for full blocks of `size` starting
    at `origin`; a trailing partial block is yielded with its real
    (shorter) length and flagged by length != size."""
    out = []
    i = 0
    off = origin
    while off + size <= len(data):
        out.append((i, off, data[off:off + size]))
        i += 1
        off += size
    if off < len(data):
        out.append((i, off, data[off:]))
    return out


def inventory(strings, size, origin=0, label=""):
    """strings: list of (name, bytes). Returns stats dict; logs the
    headline numbers. Block identity = sha256 of the block bytes."""
    occ = defaultdict(list)          # hash -> [(name, offset)]
    seqs = {}
    total_blocks = 0
    for name, data in strings:
        seq = []
        for idx, off, blk in blocks_of(data, size, origin):
            if len(blk) < size:
                seq.append(None)     # trailing partial: not pool-sized
                continue
            h = hashlib.sha256(blk).digest()
            occ[h].append((name, off))
            seq.append(h)
            total_blocks += 1
        seqs[name] = seq
    distinct = len(occ)
    shared = {h: v for h, v in occ.items() if len({n for n, _ in v}) >= 2}
    multi_off = {h: v for h, v in occ.items()
                 if len({o for _, o in v}) >= 2}
    shared_bytes = sum(size * len({n for n, _ in v})
                       for v in shared.values())
    log(f"  [{label}] B={size} origin={origin}: strings={len(strings)} "
        f"full blocks={total_blocks} distinct={distinct} "
        f"shared(>=2 strings)={len(shared)} "
        f"at >=2 distinct offsets={len(multi_off)} "
        f"shared block-instances cover {shared_bytes} B")
    return {"occ": occ, "seqs": seqs, "distinct": distinct,
            "shared": shared, "multi_off": multi_off,
            "total_blocks": total_blocks}


# ---------------------------------------------------------------- inventory

def cmd_inventory(mods):
    log("=" * 72)
    log("MISSION 1 — block decomposition and the sharing graph")
    c1 = [(m.name, m.body) for m in mods if m.cls == "c1"]
    c2 = [(m.name, m.body) for m in mods if m.cls == "c2"]
    c1cont = [(m.name, m.body[SKEL_END:]) for m in mods if m.cls == "c1"]
    # the shared chunk, from any class-01 module (identical in all 25)
    ref = next(m for m in mods if m.cls == "c1")
    chunk = ref.body[CHUNK_OFF:CHUNK_OFF + 8192]
    log(f"corpus: {len(c1)} class-01, {len(c2)} class-02, "
        f"{sum(1 for m in mods if m.cls == 'init')} init, "
        f"{sum(1 for m in mods if m.cls == 'sal')} device.sal, "
        f"{sum(1 for m in mods if m.cls == 'stub')} stubs")

    for label, strings, origin in (
            ("class-01 bodies ABS0", c1, 0),
            ("class-02 bodies ABS0", c2, 0),
            ("class-01 continuations @8214", c1cont, 0)):
        log(f"\n-- {label} --")
        for B in BLOCK_SIZES:
            inventory(strings, B, origin, label)
        # shuffled control at two sizes
        sh = [(n, shuffled(d, seed=hash(n) & 0xFFFF))
              for n, d in strings]
        for B in (256, 1024):
            inventory(sh, B, origin, label + " SHUFFLED-CONTROL")

    log("\n-- the STR[8192] chunk as a block string (origin +17) --")
    for B in BLOCK_SIZES:
        bl = blocks_of(chunk, B, 0)
        hs = [hashlib.sha256(b).hexdigest()[:12] for _, _, b in bl
              if len(b) == B]
        log(f"  B={B}: {len(hs)} full blocks, distinct={len(set(hs))} "
            f"(repeats inside the chunk itself: "
            f"{len(hs) - len(set(hs))})")

    log("\n-- offset-agnostic interior-sharing census (64-mers, "
        "all bodies incl. init.ocm) --")
    K = 64
    first = {}
    cross = Counter()
    prefix_consistent = 0
    bodies = {m.name: m.body for m in mods if m.cls in ("c1", "c2",
                                                        "init")}
    # pairwise common prefixes for the prefix-consistency test
    names = sorted(bodies)
    for name in names:
        d = bodies[name]
        for off in range(len(d) - K + 1):
            mer = d[off:off + K]
            if mer in first:
                n0, o0 = first[mer]
                if n0 != name:
                    if o0 == off:
                        prefix_consistent += 1
                    else:
                        cross[(n0, name)] += 1
            else:
                first[mer] = (name, off)
    log(f"  64-mers occurring in >=2 bodies at DIFFERENT offsets: "
        f"{sum(cross.values())} occurrences across "
        f"{len(cross)} body pairs")
    for (a, b), c in cross.most_common(10):
        log(f"    cross-offset pair {a}/{b}: {c}")
    log(f"  same-offset cross-body 64-mer occurrences (prefix "
        f"sharing): {prefix_consistent}")
    log("  (a shared span >= 64+2*256 B anywhere contains a full "
        "256-block at some alignment; the block inventories above "
        "plus this census bound interior sharing)")


# ---------------------------------------------------------------- quantize

def cmd_quantize(mods):
    log("\n" + "=" * 72)
    log("MISSION 1b — do divergence points quantize to a block grid?")
    c1 = [m for m in mods if m.cls == "c1"]
    groups = defaultdict(list)
    for m in c1:
        groups[m.u16].append(m)
    divs = []   # (pair, CP, CP-8214)
    for u, ms in groups.items():
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                cp = common_prefix(ms[i].body, ms[j].body)
                if cp > SKEL_END:
                    divs.append((f"{ms[i].name}/{ms[j].name}", cp,
                                 cp - SKEL_END))
    log(f"class-01 within-u16-group divergence points "
        f"(continuation-relative, CP-8214): "
        f"{sorted({d[2] for d in divs})}")
    for B in BLOCK_SIZES:
        res = Counter(d[2] % B for d in divs)
        at0 = res.get(0, 0)
        near = sum(v for r, v in res.items()
                   if min(r, B - r) <= 4)
        log(f"  B={B}: residues {dict(sorted(res.items()))} — "
            f"exactly on-grid {at0}/{len(divs)}, within 4 B of grid "
            f"{near}/{len(divs)}")
    c2 = [m for m in mods if m.cls == "c2"]
    divs2 = []
    for i in range(len(c2)):
        for j in range(i + 1, len(c2)):
            cp = common_prefix(c2[i].body, c2[j].body)
            if cp >= 64:
                divs2.append((f"{c2[i].name}/{c2[j].name}", cp))
    log(f"class-02 cluster divergence points (body-relative): "
        f"{sorted({d[1] for d in divs2})}")
    for B in BLOCK_SIZES:
        res = Counter(d[1] % B for d in divs2)
        log(f"  B={B}: residues {dict(sorted(res.items()))}")


# ---------------------------------------------------------------- groups

def _spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    return cov / math.sqrt(vx * vy) if vx and vy else 0.0


def cmd_groups(mods):
    log("\n" + "=" * 72)
    log("MISSION 2 — construction hypothesis: descriptor-driven "
        "sequences?")
    c1 = [m for m in mods if m.cls == "c1"]
    # --- partition check: CP >= 8215  <=>  same u16 ?
    same, diff = [], []
    for i in range(len(c1)):
        for j in range(i + 1, len(c1)):
            cp = common_prefix(c1[i].body, c1[j].body)
            (same if c1[i].u16 == c1[j].u16 else diff).append(
                (cp, c1[i].name, c1[j].name))
    log(f"class-01 pairs: {len(same) + len(diff)} total; "
        f"same-u16 pairs={len(same)}, different-u16 pairs={len(diff)}")
    log(f"  same-u16 CP range: {min(s[0] for s in same)}.."
        f"{max(s[0] for s in same)}")
    log(f"  diff-u16 CP range: {min(d[0] for d in diff)}.."
        f"{max(d[0] for d in diff)}")
    log(f"  min same-u16 pair: {min(same)}")
    log(f"  => partition is EXACT if min(same) > max(diff): "
        f"{min(s[0] for s in same) > max(d[0] for d in diff)}")

    groups = defaultdict(list)
    for m in c1:
        groups[m.u16].append(m)
    log("\nclass-01 u16 groups — internal structure "
        "(CP' = continuation-relative divergence):")
    stat_rows = []
    for u in sorted(groups):
        ms = groups[u]
        internal = []
        nested = 0
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                cp = common_prefix(ms[i].body, ms[j].body)
                internal.append(cp - SKEL_END)
                if cp == min(len(ms[i].body), len(ms[j].body)):
                    nested += 1
        branches = sorted({c for c in internal
                           if c < min(len(m.body) for m in ms)
                           - SKEL_END - 16})
        log(f"  u16={u:#06x} ({u}): {[m.name for m in ms]}")
        log(f"    body lens={[len(m.body) for m in ms]} "
            f"cont lens={[len(m.body) - SKEL_END for m in ms]}")
        log(f"    pairwise CP'={sorted(internal)} "
            f"prefix-nested pairs={nested} "
            f"internal branch depths={branches}")
        stat_rows.append((u, [len(m.body) - SKEL_END for m in ms],
                          internal))
    # u16 correlations
    xs, ys = [], []
    for m in c1:
        xs.append(m.u16)
        ys.append(len(m.body) - SKEL_END)
    log(f"\n  Spearman(u16, continuation length) over 25 modules: "
        f"{_spearman(xs, ys):.3f}")
    gx, gy = [], []
    for u, clens, internal in stat_rows:
        if internal:
            gx.append(u)
            gy.append(max(internal))
    log(f"  Spearman(u16, group's max internal CP') over "
        f"{len(gx)} multi-module groups: {_spearman(gx, gy):.3f}")
    # u16 as checksum? quick refutations
    def crc16(data, poly, init=0):
        crc = init
        for b in data:
            crc ^= b << 8
            for _ in range(8):
                crc = ((crc << 1) ^ poly) & 0xFFFF if crc & 0x8000 \
                    else (crc << 1) & 0xFFFF
        return crc
    hits = Counter()
    for m in c1:
        cont = m.body[SKEL_END:]
        cands = {
            "crc16-ccitt(cont)": crc16(cont, 0x1021),
            "crc16-ibm(cont)": crc16(cont, 0x8005),
            "sum16(cont)": sum(cont) & 0xFFFF,
            "sum16(body)": sum(m.body) & 0xFFFF,
            "cont[0:2]BE": int.from_bytes(cont[:2], "big"),
            "len(cont)": len(cont),
        }
        for k, v in cands.items():
            if v == m.u16:
                hits[k] += 1
    log(f"  u16 == derived-value hits over 25 modules: "
        f"{dict(hits) or 'none'} (crc16/sum16/first-bytes/length "
        f"all refuted as the u16's source if empty)")
    # permutation control: mean internal CP' within labelled groups
    real_stat = (sum(max(r[2]) for r in stat_rows if r[2])
                 / max(1, sum(1 for r in stat_rows if r[2])))
    rng = random.Random(20261022)
    labels = [m.u16 for m in c1]
    bodies = [m.body for m in c1]
    perm_stats = []
    for _ in range(300):
        lab = labels[:]
        rng.shuffle(lab)
        g = defaultdict(list)
        for L, b in zip(lab, bodies):
            g[L].append(b)
        vals = []
        for L, bs in g.items():
            if len(bs) >= 2:
                vals.append(max(common_prefix(bs[i], bs[j]) - SKEL_END
                                for i in range(len(bs))
                                for j in range(i + 1, len(bs))))
        perm_stats.append(sum(vals) / len(vals) if vals else 0)
    perm_stats.sort()
    log(f"  permutation control (300 label shuffles): real mean "
        f"max-internal-CP' = {real_stat:.0f}; shuffled median = "
        f"{perm_stats[150]:.0f}, p95 = {perm_stats[285]:.0f}, "
        f"max = {perm_stats[-1]:.0f} -> real grouping is not a "
        f"labelling accident")

    # block-sequence nesting at B=1024 and B=256 (continuation origin)
    for B in (1024, 256):
        inv = inventory([(m.name, m.body[SKEL_END:]) for m in c1],
                        B, 0, f"seq-check B={B}")
        seqs = inv["seqs"]
        log(f"  block sequences (continuation, B={B}):")
        for u in sorted(groups):
            ms = groups[u]
            if len(ms) < 2:
                continue
            ss = [seqs[m.name] for m in ms]
            depth = 0
            for col in zip(*ss):
                if all(c == col[0] and c is not None for c in col):
                    depth += 1
                else:
                    break
            log(f"    u16={u:#06x}: common block-sequence prefix "
                f"= {depth} blocks "
                f"(byte CP' range {min(r[2]) if False else ''}"
                f"{sorted({common_prefix(a.body, b.body) - SKEL_END for i, a in enumerate(ms) for b in ms[i + 1:]})})")

    # --- class-02: container headers vs clusters
    log("\nclass-02 container headers (10 B) vs prefix clusters:")
    c2 = [m for m in mods if m.cls == "c2"]
    clusters = {}
    for i in range(len(c2)):
        for j in range(i + 1, len(c2)):
            if common_prefix(c2[i].body, c2[j].body) >= 64:
                clusters.setdefault(c2[i].name, c2[i].body[:4].hex())
                clusters.setdefault(c2[j].name, c2[j].body[:4].hex())
    hdr_patterns = Counter(m.raw[:10].hex() for m in c2)
    log(f"  distinct 10-byte header patterns over 26 class-02 "
        f"files: {len(hdr_patterns)}")
    for p, c in hdr_patterns.items():
        log(f"    {p}  x{c}")
    for m in c2:
        log(f"    {m.name:18} hdr={m.raw[:10].hex()} "
            f"cluster={clusters.get(m.name, '-')}")
    varying = [k for k in range(10)
               if len({m.raw[k] for m in c2}) > 1]
    log(f"  header byte positions that vary across class-02: "
        f"{varying or 'none'} -> no descriptor field distinguishes "
        f"clusters if empty apart from none")


# ---------------------------------------------------------------- transforms

_BITREV = bytes(int(f"{b:08b}"[::-1], 2) for b in range(256))
_NIBSWAP = bytes(((b & 0x0F) << 4) | (b >> 4) for b in range(256))


def t_identity(d):
    return d


def t_nibble(d):
    return d.translate(_NIBSWAP)


def t_bitrev(d):
    return d.translate(_BITREV)


def t_pairswap(d):
    b = bytearray(d)
    for i in range(0, len(b) - 1, 2):
        b[i], b[i + 1] = b[i + 1], b[i]
    return bytes(b)


def t_xor(c):
    return lambda d: d.translate(bytes(b ^ c for b in range(256)))


def t_add(c):
    return lambda d: d.translate(bytes((b + c) & 0xFF
                                       for b in range(256)))


STRUCT_TRANSFORMS = {"identity": t_identity, "nibble_swap": t_nibble,
                     "bit_reverse": t_bitrev, "pair_swap": t_pairswap}


def parse_depth(data):
    """(bytes consumed, element count) of sal_dis strict parse."""
    d = sal_dis.Dis(data)
    try:
        used, _fail = d.run()
    except RecursionError:
        return -1, -1
    return used, sum(d.stats.values())


def _mers(data, k=16):
    return {data[i:i + k] for i in range(len(data) - k + 1)}


def cmd_transforms(mods):
    log("\n" + "=" * 72)
    log("MISSION 3 — framed vs opaque: transforms, cross-region "
        "overlap, parse depth")
    sys.setrecursionlimit(100000)
    c1 = [m for m in mods if m.cls == "c1"]
    c2 = [m for m in mods if m.cls == "c2"]
    init = next(m for m in mods if m.cls == "init")
    ref = c1[0]
    chunk = ref.body[CHUNK_OFF:CHUNK_OFF + 8192]
    conts = {m.name: m.body[SKEL_END:] for m in c1}
    bodies2 = {m.name: m.body for m in c2}
    atpcd = bodies2["atpcd.ocm"]
    lgd = bodies2["lgd.ocm"]
    lead = atpcd[:C2_BOUND]

    # --- cross-region exact block overlap
    log("\ncross-region EXACT block overlap (does an opaque block "
        "occur inside the framed chunk, or vice versa?):")
    regions = {"chunk": [("chunk", chunk)],
               "c1-continuations": list(conts.items()),
               "c2-bodies": list(bodies2.items()),
               "init-tail": [("init.ocm", init.body[17:])]}
    for B in (256, 1024):
        seen = {}
        cross = Counter()
        for rname, strs in regions.items():
            for nm, data in strs:
                for _i, _o, blk in blocks_of(data, B, 0):
                    if len(blk) < B:
                        continue
                    h = hashlib.sha256(blk).digest()
                    if h in seen and seen[h] != rname:
                        cross[(seen[h], rname)] += 1
                    seen.setdefault(h, rname)
        log(f"  B={B}: cross-region shared full blocks: "
            f"{dict(cross) or 'none'}")

    # --- fingerprint search under the structural transforms
    log("\nfingerprint search under transforms (16-mers): does "
        "T(chunk) material occur in continuations / class-02 / "
        "init, or T(atpcd lead) in class-01 regions?")
    targets = {"c1-continuations": list(conts.values()),
               "c2-bodies": list(bodies2.values()),
               "init-body": [init.body]}
    for tname, T in STRUCT_TRANSFORMS.items():
        src = _mers(T(chunk))
        line = []
        for tn, tlist in targets.items():
            hits = sum(1 for d in tlist if _mers(d) & src)
            line.append(f"{tn}:{hits}")
        log(f"  T(chunk) {tname:12} -> bodies containing a "
            f"16-mer: {' '.join(line)}")
    targets2 = {"chunk": [chunk], "c1-continuations":
                list(conts.values())}
    for tname, T in STRUCT_TRANSFORMS.items():
        if tname == "identity":
            continue
        src = _mers(T(lead))
        line = []
        for tn, tlist in targets2.items():
            hits = sum(1 for d in tlist if _mers(d) & src)
            line.append(f"{tn}:{hits}")
        # odd alignment for pair_swap
        src2 = _mers(T(lead)[1:])
        line2 = sum(1 for d in targets2["c1-continuations"]
                    if _mers(d) & src2)
        log(f"  T(atpcd-lead) {tname:12} -> {' '.join(line)} "
            f"(odd-align continuations:{line2})")

    # --- xor/add via difference-invariant 16-mer keys (all constants
    # at once). key_xor(m) kills a constant XOR; key_add(m) a
    # constant ADD.
    def key_xor(m):
        return bytes(x ^ m[0] for x in m[1:])

    def key_add(m):
        return bytes((x - m[0]) & 0xFF for x in m[1:])

    for kname, keyf in (("xor-invariant", key_xor),
                        ("add-invariant", key_add)):
        src_keys = {keyf(chunk[i:i + 16])
                    for i in range(len(chunk) - 15)}
        found = []
        for tn, tlist in (("c1-continuations", list(conts.values())),
                          ("c2-bodies", list(bodies2.values())),
                          ("init-body", [init.body])):
            hit = 0
            for d in tlist:
                if any(keyf(d[i:i + 16]) in src_keys
                       for i in range(len(d) - 15)):
                    hit += 1
            found.append(f"{tn}:{hit}")
        log(f"  chunk under ANY constant byte ({kname}): bodies "
            f"with a matching 16-mer: {' '.join(found)}")
        src_keys2 = {keyf(lead[i:i + 16])
                     for i in range(len(lead) - 15)}
        found2 = []
        for tn, tlist in (("chunk", [chunk]),
                          ("c1-continuations", list(conts.values()))):
            hit = sum(1 for d in tlist
                      if any(keyf(d[i:i + 16]) in src_keys2
                             for i in range(len(d) - 15)))
            found2.append(f"{tn}:{hit}")
        log(f"  atpcd-lead under ANY constant byte ({kname}): "
            f"{' '.join(found2)}")

    # --- parse-depth battery
    log("\nparse depth (sal_dis strict grammar; bytes consumed "
        "before failure / elements):")
    log(f"  reference — class-01 body[0:8214] identity: "
        f"{parse_depth(ref.body[:SKEL_END])} (skeleton framing "
        f"region; sal_skeleton parses 8214)")
    region_sets = {"chunk": [chunk],
                   "c1-continuations": list(conts.values()),
                   "c2-bodies": list(bodies2.values())}
    for tname, T in STRUCT_TRANSFORMS.items():
        for rname, rlist in region_sets.items():
            depths = [parse_depth(T(d)) for d in rlist]
            used = sorted(u for u, _e in depths)
            log(f"  {tname:12} {rname:18} max used="
                f"{used[-1]} median used={used[len(used) // 2]} "
                f"regions used>=512: "
                f"{sum(1 for u in used if u >= 512)}/{len(used)}")
    # xor/add full sweep on representative regions
    reps = {"chunk": chunk, "atpcd": atpcd, "lgd": lgd,
            "icv-cont": conts["icv.ocm"],
            "Omgtomp3-cont": conts["Omgtomp3.ocm"]}
    for rname, data in reps.items():
        best = []
        for fam, mk in (("xor", t_xor), ("add", t_add)):
            for c in range(1, 256):
                u, e = parse_depth(mk(c)(data))
                best.append((u, fam, c, e))
        best.sort(reverse=True)
        log(f"  xor/add sweep {rname:14} best 3 (used, fam, const, "
            f"elements): {best[:3]}")
    # shuffled controls for parse depth
    sh_chunk = shuffled(chunk, 1234)
    sh_atpcd = shuffled(atpcd, 987)
    for tname, T in STRUCT_TRANSFORMS.items():
        log(f"  SHUFFLED-CONTROL {tname:12} chunk used="
            f"{parse_depth(T(sh_chunk))[0]} atpcd used="
            f"{parse_depth(T(sh_atpcd))[0]}")


# ---------------------------------------------------------------- atpcd

def cmd_atpcd(mods):
    log("\n" + "=" * 72)
    log("MISSION 4 — atpcd.ocm block map")
    by_name = {m.name: m for m in mods}
    atpcd = by_name["atpcd.ocm"]
    lgd = by_name["lgd.ocm"]
    others = {m.name: m.body for m in mods
              if m.cls in ("c1", "c2", "init")
              and m.name != "atpcd.ocm"}
    for B in (1024, 256):
        log(f"\n-- atpcd at B={B} (ABS0) --")
        occ = {}
        for nm, data in others.items():
            for _i, off, blk in blocks_of(data, B, 0):
                if len(blk) == B:
                    occ.setdefault(hashlib.sha256(blk).digest(),
                                   []).append((nm, off))
        lgd_blocks = {off: hashlib.sha256(blk).digest()
                      for _i, off, blk in blocks_of(lgd.body, B, 0)
                      if len(blk) == B}
        n_shared = n_partial = n_unique = 0
        shared_bytes = 0
        for idx, off, blk in blocks_of(atpcd.body, B, 0):
            h = hashlib.sha256(blk).digest()
            if len(blk) < B:
                log(f"  blk {idx:3} @{off:6}..{off + len(blk):6} "
                    f"len={len(blk)} TRAILING PARTIAL "
                    f"sha={h.hex()[:10]}")
                continue
            if lgd_blocks.get(off) == h:
                lab = "SHARED lgd @same offset"
                n_shared += 1
                shared_bytes += B
            elif h in occ:
                lab = f"SHARED {occ[h][:3]}"
                n_shared += 1
                shared_bytes += B
            elif off < C2_BOUND < off + B:
                k = common_prefix(atpcd.body[off:], lgd.body[off:])
                lab = (f"STRADDLE: first {C2_BOUND - off} B shared "
                       f"with lgd, rest unique (block-internal CP "
                       f"from block start = {k})")
                n_partial += 1
                shared_bytes += C2_BOUND - off
            else:
                lab = "unique"
                n_unique += 1
            log(f"  blk {idx:3} @{off:6}..{off + B:6} "
                f"sha={h.hex()[:10]} {lab}")
        log(f"  totals B={B}: full blocks shared={n_shared} "
            f"straddle={n_partial} unique={n_unique}; "
            f"bytes identical with lgd at same offsets = "
            f"{shared_bytes} of {len(atpcd.body)} body bytes "
            f"({100.0 * shared_bytes / len(atpcd.body):.1f}%); "
            f"cluster boundary at +{C2_BOUND}")


if __name__ == "__main__":
    _logf = open(NOTES, "a")
    mods = load_corpus()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    {"inventory": cmd_inventory,
     "quantize": cmd_quantize,
     "groups": cmd_groups,
     "transforms": cmd_transforms,
     "atpcd": cmd_atpcd}[cmd](mods)
    _logf.close()
