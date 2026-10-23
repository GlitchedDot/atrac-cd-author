# Stage-0 readout #11 — SAL container attack, phase 2 step 1: stream hypotheses vs the oracle (2026-10-22)

Tests run on the files in `~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG/`
(25 class-01 v5 modules, 20 class-02 v5 modules, 6 key containers,
init.ocm, both copies of device.sal). Working scripts:
`~/workspace/atrac-salwrap-work/sal_stream_tests.py` and
`sal_stream_tests2.py`. The oracle is the reconstructed formed-image
format (readout #10 §2.1): 0x60-byte header, name at +0x3E (`bc` =
bytecode marker), type byte +0x46, compression flag +0x47 ∈ {0,1},
entry offset +0x4C, symbol offset/count +0x50/+0x56, reloc offset/size
+0x58/+0x5C. Scorer awards up to 13 points across those fields.

## Verdict up front

**All stream hypotheses MISS.** The .ocm body is not a plain SalAsn
TLV stream under any convention the visible codec suggests, and it is
not a zlib/raw-deflate/gzip stream — whole or framed — at any tested
boundary. No decompression or parse anywhere produced anything
resembling a formed image (best image score 3/13, on periodic garbage).
This closes phase-2 step 1 as scoped and points exactly where readout
#10 said it would if the cheap tests failed: the transform lives
behind the protected kernel seam (step 2, out of scope here).

## Hypothesis 1 — SalAsn TLV stream from offset 10: MISS

Conventions tested (from the SalAsn encoders in salwrap:
FUN_65124CC0 writes tag 1/2 for 1/2-byte payloads and tag 3 + DER
length for integers; FUN_65125020 writes tag 4 + DER length for octet
strings):

- **SalAsn variant** (tags 1/2 implied-length, others DER length) and
  **strict DER**: the class-01 body and device.sal open with two
  elements that parse exactly — `01 01 [01]`, then `04 08` + 8 bytes
  (`6a 35 a2 1d 8c 3c 2c 0c`) — consuming precisely the 12 leading
  bytes that are byte-identical across all 25 class-01 modules and
  device.sal (their 13th shared byte is `0x7e`). Every continuation
  then dies almost immediately: SalAsn walk fails at body offset 18
  (icv.ocm), 126 (device.sal), 177 (ekbman.ocm); strict DER at 111.
  Class-02 bodies don't even open: atpcd.ocm's body
  (`4d 47 ca 99 6a b2 …`) yields one forced element (tag 0x4D,
  len 0x47) and a bad length at offset 73.
- **Fixed-length variants** (tag + 1-byte / u16le / u32le length):
  the 1-byte variant wanders far on random-looking steps (246
  elements in icv) but never consumes a file exactly and — the
  decisive check — **no element boundary in any variant lands on
  the sharing offsets** (body-relative 8211 for the class-01
  preamble, 8471 for atpcd/lgd). u16le/u32le variants die within
  0–2 elements.

So the shared 13-byte head is real framing of *something*
(deterministic, family-wide), but the body as stored is not a
walkable TLV stream: either a transform is applied before/within
decoding in the kernel, or the framing is schema-driven in a way
the encoder conventions don't reveal. TLV payloads (≥16 B) were
also inflation-tested individually: zero hits.

## Hypothesis 2 — deflate (body is / contains a compressed formed image): MISS

- **zlib framing (wbits 15) and gzip (wbits 31): zero streams** —
  at offsets 0–8192 of every file, and at *every* offset of
  atpcd.ocm, icv.ocm, init2.ocm, lgd.ocm and device.sal, under both
  lenient (≥0x60 B output) and strict (stream-end required) criteria.
  The only 0x78-magic candidates in any body are isolated chance
  bytes (icv: 2 in 31 KB).
- **Raw deflate (wbits −15): only the chance background.**
  Thousands of offsets contain a complete micro-stream by chance
  (1,874 strict stream-end hits in the scans) — every one consumes
  3–46 input bytes and outputs ≤525 B of periodic junk
  (`5w5w5w5w`, `eJeJeJ…`, `\xc8`×8, `\x1fV`×n). Best image score
  among all of them: 3/13, with garbage in the name field and an
  out-of-range compression flag. A real compressed formed image
  would have to produce ≥0x60 B scoring near 13 and, per the
  oracle, decode *identically through the 8,211-byte shared
  preamble in all 25 class-01 modules* — no candidate survived
  long enough for cross-validation to apply.
- **Direct check**: raw bodies scored as images score 0–1/13
  (atpcd body head: `4d 47 ca 99 6a b2 97 53 95 2d be 47 23 7f 42
  bf 67 83 47 00 10 70 2b af …`; body entropy 7.991–7.994
  bits/byte, no structure beyond the shared head).

## What the bytes did instead

- Class-01 + device.sal share the 13-byte head
  `01 01 04 08 6a 35 a2 1d 8c 3c 2c 0c 7e`, the first 12 bytes of
  which parse as two well-formed SalAsn values — then the parse
  dies within a few elements under every convention tried, and no
  framing boundary coincides with either sharing offset (8211 /
  8471 body-relative).
- Class-02 bodies diverge from byte 0 of the body and do not parse
  at all.
- No zlib/gzip stream exists anywhere tested; raw-deflate noise
  is uniformly microscopic and periodic.

## Consequence

Step 1's cheap doors are all closed, with receipts. The body →
image transform is not framing alone and not stock compression;
whatever it is sits behind the one unread seam readout #10
identified — the hand-off from the protected kernel's
load-by-name (API +0x3C) to the image manager FUN_651243B0.
That kernel-seam attack is phase-2 step 2 and was out of scope
for this step. No dumper was built (nothing to dump with yet);
no bytecode work was touched.
