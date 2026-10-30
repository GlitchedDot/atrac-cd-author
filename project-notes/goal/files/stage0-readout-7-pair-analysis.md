# Stage-0 readout #7 — known-plaintext pair analysis + secure-header field map (2026-10-21)

Method: pure Python analysis of the data files (no Sony code executed).
Pairs: Dreamer (TRK000E1.ATP vs dreamer.raw) and Electric
(TRK000DC.ATP vs electric.raw) — ciphertext length equals plaintext
length exactly in both (1,256,216 and 1,142,664 bytes). Plus the four
Ignite My Heart copies (A0–A3, same unknown plaintext) and Talk About
(TRK0000A) for header comparison. All offsets below are measured
directly from the 7 secure headers (96 bytes at file offset 1024 in
every .ATP); two offsets circulating from earlier readouts are
corrected here: the EKB version sits at header offset **0x10**, and
the "ATX " tag at **0x40**.

## 1. Secure-header field map

Variability classes across the 7 samples do most of the work:
**CONST** = identical in all 7; **TRACK** = identical for the four
Ignite copies (same content), different per track; **INSTANCE** =
different in every file, including between Ignite copies.

| Offset | Size | Class | Bytes / values | Proposed field |
|---|---|---|---|---|
| 0x00–0x03 | 4 | CONST | `01 00 28 2e` | Format magic / version preamble |
| 0x04–0x07 | 4 | per file | BE u32 = 2911 / 3444 / 3341 / 3039 | **Frame count** — equals each file's exact ATRAC frame count (payload ÷ 376) in all 7 samples |
| 0x08–0x0F | 8 | CONST | zeros | Reserved |
| 0x10–0x13 | 4 | CONST | BE `00 01 00 0e` | **EKBVersion** = 0x0001000E — the disc's .STK id |
| 0x14–0x17 | 4 | CONST | zeros | Reserved |
| 0x18–0x1F | 8 | INSTANCE | random-looking, unique per file | **BlockSeed** — fresh seed material chosen at burn time |
| 0x20–0x27 | 8 | CONST | `010f5000 00040000` | Format/block parameters; **BlockID** lives here or at 0x00 (an enum, constant because every sample is the same ATRAC-CD block type) |
| 0x28–0x2F | 8 | mixed | `00 xx xx 16 72 5f 9b e7`; only bytes 0x29–0x2A vary, per TRACK (`209f` Talk, `7e4f` Ignite, `885c` Dreamer, `39e3` Electric) | **Connum** candidate (per-content number; arbitrary per track, stable across copies) — see timestamp note below |
| 0x30–0x37 | 8 | TRACK | 4 varying bytes (`a22c51e2` / `b4f37fbb` / `daa4f288` / `aac7701d`) + 4 zero bytes | Per-track value slot, candidate MgD half or a content check |
| 0x38–0x3F | 8 | CONST | zeros | Reserved / padding |
| 0x40–0x4F | 16 | CONST | `ATX ` + zeros | Codec tag slot ("ATX") — formatter metadata, not crypto |
| 0x50–0x57 | 8 | TRACK | `e6e765b5b7ff50d9` / `2ad14387ddfb4b86` / `eaa4d1e154d8fd20` / `025f5142ef8fc241` | **MgD** (MgDUpper+MgDLower) — the content integrity value: identical for identical content, per-track |
| 0x58–0x5F | 8 | INSTANCE | random-looking, unique per file | **InitVector** — fresh per burn; classic trailing placement |

**MgCk** is the one named field with no confident home: the 2
per-track bytes at 0x29–0x2A are the only unassigned varying bytes,
so either they are Connum and MgCk is folded into a constant region
(unlikely for a check value), or they are MgCk and Connum is not
stored here. Seven samples cannot separate them.

**The `16725f9be7` field is not a timestamp.** Every standard
reading of the 0x28–0x2F window fails: LE u32 @0x2C = 2093-02-17,
BE u32 @0x2C = 2030-10-22 (both future), LE u32 @0x2B = 2052-08-08,
BE u32 @0x28 = 1970-05-01, FILETIME u64 = year 1742 or out of range.
What it can be: a structured id whose tail (`16 72 5f 9b e7`) is
constant **disc-wide** — all 7 headers come from ONE disc, so
"disc/session id" and "global format constant" are indistinguishable
with current data. A single header from a second disc decides it.

## 2. Block-structure tests (both pairs)

**(a) Repeated plaintext frames → where does ciphertext diverge?**
Dreamer contains one repeated plaintext frame: the silent tail
frame at indices 3336–3340 (5 copies, 10 pairs), plus a 1,548-byte
repeated run (the same tail, ~4.1 frames — the longest repeated
substring in the track). For **every** pair, the ciphertext common
prefix is **0 bytes** — the ciphertexts differ from the very first
byte despite up to 1.5 KB of identical plaintext. Encryption state
at any point depends on the preceding history/position from byte 0;
nothing is processed independently in frame-sized (or larger) units.

**(b) History dependence at sub-frame granularity.** ECB tests on
aligned blocks, both tracks: Dreamer has 394 duplicate 8-byte, 186
duplicate 16-byte, and 85 duplicate 32-byte aligned plaintext
blocks; Electric has 106 / 45 / 19. **Zero** of them encrypt to the
same ciphertext block. Combined with (a): ECB is excluded at every
granularity from 8 bytes to whole frames, and (within-track only,
as cross-track keys differ) identical plaintext substrings at
unaligned offsets (the 1,548-byte match starts at frame offset 332
in both copies) also diverge at ciphertext byte 0.

**(c) Reset / periodicity.** Treating K = C⊕P as a putative
keystream: no duplicate aligned 16- or 32-byte K blocks in either
track; K self-match rates at frame lags 1, 2, 4, 8, 16, 32, 64,
128, 256, 512 and byte lags 1024, 4096, 16384, 65536 all sit at
0.34–0.44% — the random baseline (~0.39%). No reset interval and
no period exists anywhere up to 192 KB. Ciphertext itself: **zero**
duplicate aligned 8-byte blocks among 157,027 (Dreamer) and 142,833
(Electric) blocks, and zero duplicate 16-byte blocks.

**Ignite cross-copy check:** all 6 pairs of the four same-plaintext
copies differ from **payload byte 0**, with sampled byte agreement
0.31–0.62% (random). Per-instance seeding (BlockSeed + InitVector)
therefore affects the encryption from the first byte — there is no
shared prefix, no late-entering seed.

## 3. Plaintext frame structure vs ciphertext

The .raw streams have a rigid per-frame signature (Dreamer, 3,341
frames): **byte 0 = 0x3A in 3341/3341 frames**; byte 1 takes only 7
distinct values (0x64 in 2,585 frames, 0x65 in 476); the last byte
(offset 375) takes only 34 distinct values (entropy 2.67 bits);
entropy rises to ~7.9 bits by mid-frame. (Frame 0 is the encoder's
silent lead-in: header + 0x01 padding.) This is a gift for analysis
— 3,341 known plaintext bytes at known positions in Dreamer alone.

**The ciphertext preserves none of it.** At frame offsets 0, 1, and
375 the ciphertext takes all 256 distinct byte values across
frames; overall ciphertext entropy is 8.000 bits/byte vs the
plaintext's 7.985. Even the implied keystream byte at frame starts
(C ⊕ 0x3A) spans all 256 values with no repeats pattern. No
structural leakage at frame boundaries, block boundaries, or
anywhere else probed.

## 4. Assessment

**Ruled out by the data:** ECB at any block size 8–376 bytes;
repeating-key XOR at any period up to ~192 KB; per-frame or
per-block independent encryption under a fixed key; keystream reset
at any tested interval; a keystream shared between tracks; any
mode whose output preserves frame structure.

**Still consistent:** a keyed block cipher (block ≥ 8 bytes) in a
chaining or counter/feedback mode — CBC, CFB, OFB, CTR are all
compatible — or an equivalent dedicated stream construction, in
every case **seeded per instance** from the header's BlockSeed
(0x18) and InitVector (0x58) under the disc EKB key, with full
history dependence from byte 0. Passive black-box data cannot
separate CBC from CTR here: no two (state, plaintext) pairs ever
collide to exploit, and there is no decryption oracle. **The
generic-probe surface is exhausted** — every test returns the same
answer, "strong cipher, per-instance seeded." Naming the actual
algorithm now requires the code (atpcd.ocm, per readout #6) or a
far richer data set.

**Next decisive experiments, ranked:**

1. **The Ignite My Heart library .OMA** (one small file from Lola).
   It completes four same-plaintext ciphertexts whose headers
   differ in *exactly two fields* (BlockSeed, InitVector) — a
   controlled experiment no other sample offers. It isolates what
   each field controls, and the moment any candidate cipher is
   implemented from the .ocm work, these four pairs are the test
   vectors that confirm or kill it.
2. **One pair + header from a second burned disc.** Decides
   whether `16 72 5f 9b e7` is a disc/session id or a format
   constant, and whether the per-track fields (Connum/MgD
   candidates) are stable across independent burns.
3. **Static analysis of atpcd.ocm** (with ekbman.ocm) — the heavy
   lift, and now clearly the only route to naming the cipher.
   Readouts #6 + this one define exactly what to look for: an
   8+-byte block construction keyed via the EKB, consuming an
   8-byte seed and an 8-byte IV per file.
4. (Conditional) Chosen-plaintext burns — e.g., a track of pure
   digital silence — would give fully controlled plaintext. Only
   viable if SonicStage burns again; noted for completeness, not
   requested: the Toshiba install currently crashes.
