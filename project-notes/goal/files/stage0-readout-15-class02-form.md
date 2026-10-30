# Stage-0 readout #15 — SAL attack phase 5: the class-01 skeleton's continuation, and the class-02 stored form (atpcd.ocm) (2026-10-22)

Static analysis only; nothing was executed. Materials: the module
corpus in `~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG/`
(25 class-01 family `.ocm`, init.ocm, device.sal, 26 class-02
`.ocm`, 9 `FF FF` stubs). Prior papers: readout #14 (priming
contract, skeleton anatomy), readout #13 (operand grammar).
New/extended tooling: `~/workspace/atrac-salwrap-work/sal_skeleton.py`
gained `parse_continuation()`, `class02_profile()`,
`find_fingerprint_offsets()`, and a `--corpus5` validation mode;
primary evidence in `out/phase5-notes.txt`. All offsets are
**body offsets** (file offset − 10) unless marked "file".

## Verdict up front

**Class-01 (target A): the skeleton is the whole plaintext
story.** Past body+8214 there is no further framing under either
the strict SalAsn grammar or a generic BER walk — in all 25
modules — and the continuation is uniformly high-entropy
(≈7.8–8.0 bits/byte in every window, head to tail). It is not an
undifferentiated blob, though: it is deterministic, block-shared
stored content in the same opaque encoding as the STR[8192]
chunk's contents, and modules that share the skeleton's u16
share long exact continuations (common prefixes of 8,553 /
10,538 / 12,662 bytes, up to near-whole-body). The complete
class-01 structural map is §1.

**Class-02 (target B): atpcd's form is not the class-01 skeleton
in disguise.** Hypothesis 1 (skeleton present, head transformed)
is **dead** — no class-01 fingerprint (family ID, chunk
substring ≥16 B, exact or under constant XOR/add) occurs at any
offset in any of the 26 class-02 bodies. Hypothesis 2
(byte-0 encryption under one fixed-start stream) is **dead in
its testable form** — bodies do not share a class-wide opening,
and the atpcd⊕lgd two-time-pad over the divergent region is
statistically indistinguishable from random controls while a
positive control separates decisively; its general form is
indistinguishable from stored bytes because the plaintext
contents are high-entropy even when known (class-01's chunk).
What the evidence supports is hypothesis 3 in a specific shape:
**class-02 bodies are assembled from cluster-shared opaque
leading blocks (≈8,468–8,471 B) plus per-module opaque tails** —
the same *kind* of construction as class-01, one level up:
shared opaque content first, per-module content after, no
plaintext framing anywhere. atpcd's region map is §3.
**atpcd.ocm remains undecrypted**; what fell is the shape of
its stored form and the exact boundaries of its two regions.

## 1. Class-01: the complete structural map

| Body offset | Span | Status |
|---|---|---|
| +0 | `01 01` INT1 1 | plaintext framing (phase 4) |
| +2 | `04 08` + family ID `6A35A21D8C3C2C0C` | plaintext framing |
| +12 | `0x7E` marker | plaintext framing |
| +13 | `04 82 20 00` STR header, len 8192 | plaintext framing |
| +17 .. +8208 | 8,192 B shared chunk | **opaque contents** (H ≈ 7.98), byte-identical in all 25 |
| +8209 | `74 02` element header | plaintext framing |
| +8211 | u16 (BE), per-module, 0x49E8–0x4A02 | **the only per-module field in the skeleton** |
| +8213 | `0x73` marker | last framing byte |
| +8214 .. EOF | per-module continuation | **opaque contents**, no framing (below) |

The continuation, in detail:

- **No framing.** Strict SalAsn from +8214 dies on the first
  byte (0 elements) in the sampled modules. A generic BER walk
  (any tag + DER length) from +8214 survives 0–5 chance elements
  and dies on absurd length fields (icv/maclist: 1 element to
  +8223; mgrms: 3 to +8413; migratepf: 5 to +8491). From +8213
  (reading `0x73` as a TLV) icv/maclist reproduce phase 4's
  death at +8297, tag `0x12`. There is no second plaintext
  dialect hiding here under either grammar.
- **Uniformly opaque.** Continuation entropy per module:
  7.787–7.997 bits/byte (the two lowest, restore 7.787 and
  omgtopcm2 7.804, are also the two shortest continuations —
  925 and 1,037 B — a window-size effect). 1 KiB windows from
  +8214 and the final 1 KiB sit at 7.76–7.84 throughout. The
  high-entropy region therefore starts at **+8214** and runs
  to EOF in every module (and, inside the skeleton, the chunk
  contents are already opaque from +17).
- **Deterministic and block-shared.** Pairwise common prefixes
  past the skeleton, grouped by the skeleton u16:

  | u16 | Modules | Longest common prefixes |
  |---|---|---|
  | 0x49f4 | at3toomg, at3topcm, mp3toomg2 | 23,567 / 23,562 (near-whole-body) |
  | 0x49f5 | mp3tovmc, msatoomg, msatopcm | 10,538; msatoomg/msatopcm 23,588 |
  | 0x49f6 | Omgtomp3, omgtomsa, omgtopcm2, pcmtoomg | 8,553 – 10,538; Omgtomp3/pcmtoomg 23,561 |
  | 0x49ee | vmc, vmc0conv, vmcconv | 10,538; vmc0conv/vmcconv 23,582 |
  | 0x49eb | migratepf, querycif | 8,553 |
  | 0x49e8 | icv, maclist | 12,662 |
  | 0x4a02 | osss, restore | 8,215 only |
  | unique | mgrms, mgsoft, netmd, omgii, wm2, wmimport2 | 8,212 vs everyone (skeleton only) |

  A longest-common-substring control (icv/maclist) returns
  12,662 at (0,0): the shared span is the prefix, not an
  interior block. So the continuation reads as stored content
  blocks drawn from a shared pool in the chunk's opaque
  encoding: functional near-variants share almost everything;
  unrelated modules share nothing past the skeleton. The u16
  correlates with which blocks follow but is **not a length**
  (u16 0x49f4 = 18,932 vs ≈15,385 B of continuation; restore's
  0x4a02 vs 925 B) and is **not claimed as a seed** — it remains
  the skeleton's one unexplained per-module field.

**Where the skeleton ends and the contents begin:** framing
ends at +8213 (the `0x73`); contents — opaque from the start —
occupy +17..+8208 (the shared chunk, inside the frame) and
+8214..EOF (the per-module continuation, outside any frame the
recovered grammars can see).

## 2. Class-02: hypothesis tests

Corpus facts first: 26 bodies, lengths 8,484–62,799 B,
whole-body entropy ≈7.99. No body opens with any plaintext
element (phase 3/4 result, re-verified by the searches below).

### Hypothesis 1 — skeleton present, head transformed: DEAD

- Family ID `6A35A21D8C3C2C0C`: **0 occurrences** in 26 bodies,
  at any offset.
- STR[8192] header `04 82 20 00`, the `01 01 04 08` head bytes:
  0 occurrences.
- Shared-chunk substrings of length 8192 / 1024 / 256 / 64 / 32 /
  **16**: 0 occurrences at any offset in any class-02 body.
- The same searches under a constant XOR difference and under a
  constant additive difference (32 B chunk prefix; 8 B family
  ID), any offset: 0 hits. (Null expectation: the 8-byte
  constant-difference condition holds for ~256⁻⁷ of random
  windows, so zero is the expected null, not a near-miss.)

No part of the class-01 skeleton survives in class-02 in exact
or single-byte-transformed form, at any offset.

### Hypothesis 2 — contents encrypted from byte 0, fixed-start stream: testable form DEAD, general form undecidable

- **No class-wide opening.** Under one fixed-start stream over
  a shared plaintext head, all class-02 bodies would share
  their opening bytes. They form five small head clusters
  instead (§2, hypothesis 3), and 15 of 26 bodies share <64 B
  of prefix with *any* other body.
- **Two-time-pad (atpcd ⊕ lgd, divergent region +8471..21553,
  n = 13,083):** zero bytes 0.44%, bytes <0x20 13.00%,
  printable 36.64%. Controls: atpcd ⊕ shuffled(lgd)
  0.37 / 11.79 / 37.32; atpcd ⊕ kdrm (unrelated class-02)
  0.50 / 12.69 / 36.87; atpcd ⊕ atpcd≫1: 0.38 / 12.47 / 36.89.
  The divergent XOR sits **inside the random band** on every
  metric.
- **Positive control:** the identical metric on a synthetic
  SalAsn-like plaintext pair under a shared keystream gives
  zero 33.99%, <0x20 100% — the test separates decisively when
  low-entropy framed plaintext is present. So: *shared
  keystream + low-entropy framed plaintext* is refuted.
- **Why the general form survives:** class-01's *known*
  plaintext contents are themselves high-entropy (chunk
  H ≈ 7.98). A shared-keystream pair of high-entropy
  plaintexts produces exactly the observed statistics. Stored
  bytes alone cannot distinguish "per-module keystream" from
  "shared keystream, high-entropy plaintexts" — stated as a
  limit of the method, not a gap in the tests.
- **Keystream-candidate test:** atpcd[0:8192] ⊕ the class-01
  chunk yields no family ID and no parse; body ⊕
  skeleton-plaintext is cluster-specific (identical only where
  the stored bytes already are). No borrowed-keystream reading
  works.

### Hypothesis 3 — a different framing entirely: SUPPORTED, in cluster-block form

All 325 class-02 pairs were compared (two independent
implementations — k-mer seed + extension, and a 32-mer set scan
+ numpy LCS — with identical results):

**Prefix clusters** (the only pairs sharing ≥64 B):

| Head (body+0..3) | Pair | Common prefix |
|---|---|---|
| `4D47CA99` | atpcd / lgd | **8,471** |
| `370BCE65` | bot-dnk / hdd-dnk | 9,052 = whole bodies (byte-identical) |
| `229BDC10` | botamoti / init2 | 8,468 |
| `229BDC10` | botamoti / region | 8,468 |
| `229BDC10` | init2 / region | 8,471 |
| `A35E9E58` | lgdimport / umd | 8,468 |
| `71B83369` | mss / updater | 8,470 |

**The shared span is always a prefix.** Exactly 7 of 325 pairs
share any substring ≥32 B anywhere, and in all 7 the longest
common substring *is* the common prefix, at (0,0). The best
non-cluster match in the whole class is 31 B (kdrm/nc) —
chance-scale, ~270× shorter than the cluster spans. There are
no interior shared blocks between clusters.

**Boundary anatomy mirrors class-01.** Within the `229BDC10`
cluster, botamoti diverges from init2/region at +8468 while
init2/region hold to +8471, and byte +8469 (`E5`) is shared by
botamoti/init2 even past their divergence; lgdimport/umd
diverge at +8468 with the second byte (`EC`) shared. A small
field straddling ≈+8468..+8471 whose value bytes partly
coincide — the same pattern as class-01's u16 at +8211, which
made pairwise prefix lengths differ by 1 within that family.
No field semantics are claimed for class-02's boundary bytes.

**Scale check:** init2.ocm's body is 8,484 B = 8,471 shared +
13 unique bytes. The smallest class-02 modules are almost
entirely cluster block (mss 8,608; updater 8,568; the
unclustered importer_key/ktunes_key 8,540 each) — the ≈8.5 KB
leading block is a real structural unit of the form, not an
artifact of two similar files.

**No wrap signature.** Body lengths mod 16 span every residue
0–15; no shared suffix ≥32 B exists at any offset (covered by
the LCS scan); there is no fixed trailer. The DNK/ECC-wrap
possibility from readout #12 leaves **no size or position
signature** in the stored bytes — it is neither supported nor
refuted by anything here, and no observation requires it.

## 3. atpcd.ocm region map

| Span | Size | Label |
|---|---|---|
| file +0 .. +9 | 10 B | container header (`03 02`, build stamp 11280) |
| body +0 .. +8470 | 8,471 B | **cluster-shared opaque region** — byte-identical with lgd.ocm; H ≈ 7.99; no framing; no class-01 fingerprint in any tested form |
| body +8471 .. +21553 | 13,083 B | **per-module opaque region** — unique to atpcd; ⊕ lgd is in the random band vs all controls |

Body length 21,554 B; file length 21,564 B. No trailer is
separable from the per-module region. For contrast, lgd.ocm:
body 26,428 B = the same 8,471 B shared region + 17,957 B
unique. Nothing in atpcd parses under the recovered grammar at
any offset, and no region of it is plaintext in any form
tested.

## 4. What this means, and what remains

The two classes now have parallel structural descriptions:

- **Class-01:** plaintext SalAsn *frame* (8,214 B skeleton)
  carrying opaque contents — one shared 8,192 B block inside
  the frame, then per-module opaque continuations built from
  pool-shared blocks.
- **Class-02:** no frame at all — the same construction
  (cluster-shared opaque block ≈8.47 KB, then per-module
  opaque content) with the framing layer absent, or encrypted
  along with everything else from byte 0.

The remaining unknown is unchanged in kind but sharper in
shape: **the contents encoding** — the transform that makes an
8,192 B chunk of presumably-SalAsn content read as 7.98-entropy
bytes, shared deterministically across modules. It is one
encoding for both classes (class-02's blocks are statistically
and structurally the same kind of object), it is deterministic
with identical start state across every module that shares a
block, and — per readouts #12–#14 — it is applied bytecode-side
by init.ocm's loader, not by any native code. Reading it still
requires the loader's execution semantics; but any future
decryption candidate can now be validated structurally against
*two* corpora: it must reproduce class-01's skeleton framing
*and* class-02's cluster boundaries (8,468–8,471 B, with the
partly-coinciding boundary field) from the same plaintext-side
construction.

**atpcd.ocm decrypted: NO.** Its stored form is mapped
completely at the structural level: two regions, exact
boundaries, no plaintext anywhere, and the class-01 skeleton
provably absent in every disguise tested.
