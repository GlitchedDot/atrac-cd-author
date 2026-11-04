# Session 62 — SEAL REPORT (2026-11-03)
DESK-ONLY construction battery against the BIND BlockSeed (buf8),
using Session 61's exact (record-state → seed) specimens plus the
S44-era drives. No harness drives, no builds, no burns.
(Written incrementally; sections land as results arrive.)

## ⚠ Correction to the brief's S43 trailer constant

The brief gave the blob8 trailer as the 20-B CID20
`010f500000040000004f7e16725f9be7b4f37fbb`. The S43 lift (campaign
note, result 14) is a **16-byte module constant**:
`01 0f 50 00 ‖ 00 04 00 00 ‖ 00 00 00 16 ‖ 72 5f 9b e7`
(its tail fields echo the CID family, but it is not the CID20).
All work below uses the lifted 16-B trailer.

## Positive control — PASSES

blob8 = SHA-1(inner ‖ "ATRAC CD" ‖ trailer16)[0:8] reproduced
byte-exactly in this session's own Python (hashlib) for 5 sample
inners: bb envelope (e225ac50f7b1195f), t2int doc
(7af96ae450de6963), genuine disc-1 record (ace078c1751647ba),
FavoriteDisc record (27b371c30e230160), cd4c… record
(aa59edfe0aa41d46). The hashing pipeline is trustworthy; negatives
below are real negatives. (Every specimen doc's own carried blob8
was likewise re-verified against its inner during oracle
assembly — all consistent.)

## Job 1 — the oracle set

Document format (from the artifacts): root container `30 80`
{ elem1 = `04 <len>` inner-serialization, elem2 = `04 08` blob8 }
`00 00`; inner = `30 80` { `04 10` key16, INTEGER int1, slot-2
element, `00 00` } with BER-minimal int encodings. Template for
all drives except gcdA1 is TRK000A0.ATP (1,296,064 B); gcdA1 used
TRK000A1.ATP (also 1,296,064 B; its 96-B secure header differs
from A0's ONLY at +0x18 BlockSeed and +0x58 IV).

| # | specimen | key16 | int1 | slot-2 | template | buf8 |
|---|---|---|---|---|---|---|
| 1 | bb1/bb2/bb3 | 0524600d… | 0 | int 0 | A0 | b4e56ea4874a6bb6 |
| 2 | t2int | 0524600d… | 1296064 | int 1 | A0 | a5bdf486982371dc |
| 3 | t2alt | 0524600d… | 1000 | int 7 | A0 | bf659c82e92be6ad |
| 4 | t3big | 0524600d… | 1296064 | BLOB04, 8192 B | A0 | 1c953066eb2406f4 |
| 5 | p3s2 | 0524600d… | 1296064 | STRING06, 8192 B (same bytes as #4) | A0 | 4ad3fd6b583bd844 |
| 6 | gcd0 | f4a79f21… | 0 | int 0 | A0 | 759ec28de11493d9 |
| 7 | gcdL | f4a79f21… | 704101184 | int 492 | A0 | dd8f6bb69b7021eb |
| 8 | gcdF | f4a79f21… | 705397248 | int 493 | A0 | 679994a2f5215379 |
| 9 | gcdA0 | f4a79f21… | 234127912 | int 159 | A0 | 096da854ae9e6320 |
| 10 | gcdA1 | f4a79f21… | 235423976 | int 160 | A1 | c6619cbd1f9d3f1f |

Exact doc serializations recovered from artifacts for all ten
(s61 `*-doc.bin`, s44 `*-doc.bin`); slot-2 payload bytes of #4/#5
are the identical 8,192 B beginning `3a64eaa03692ccbd…` (audio).
tail1 (t2int doc + ignored tail bytes) returned t2int's buf8 —
bytes after the root close are not inputs.

**What varies / what moves the seed** (controlled pairs):
- key16 only: #1 vs #6 → seed changes.
- ints only: #1 vs #2 vs #3; #7 vs #8 (one bind apart).
- slot-2 TAG only (#4 vs #5, identical content bytes) → seed
  changes ⇒ the seed sees the serialized element (tag/type),
  not merely content bytes.
- template + doc jointly: #9 vs #10 (confounded pair; S61).
Constants across the whole set: ceremony state (d2, global seed,
maclist), the 232-B .opf stream (reply string A byte-identical
across all A0 drives AND the A1 drive — md5 a6585df6…), template
size (1,296,064 for both templates), both templates' CID20.

Post-bind inner′ (reply string C) where the record path is
well-defined (slot-2 int): inner′ = (key16, int1 + 1,296,064,
int2 + 1) — S44 run 259 pinned int1′ = int1 + template size,
int2′ = int2 + 1.

## Battery A — hash constructions: ZERO HITS

SHA-1 / MD5 / SHA-256 × ~50 message assemblies × 7 extractions
([0:8], [8:16], [-8:], XOR folds of 8-B windows, per-word
byteswap, reversal), over components: inner, post-bind inner′,
full doc, post doc, element stream, key16, template hdr96
(with and without the genuine seed slot), the 232-B .opf stream,
template size (BE/LE/BER-serialized/ASCII), d2, the 20-B global
seed, CID20, IV, GET_GLOBAL_SEED readback, the template's
genuine BlockSeed and mgd — in the blob8 family framing
(inner ‖ "ATRAC CD" ‖ trailer) and permutations thereof.
No candidate matched even ONE specimen, let alone two.

## Battery B — DES constructions: ZERO HITS

(op11 control PASSES in the same code: A0's header document →
8150393f51e23848, byte-exact — the DES pipeline is trustworthy.)

- ECB cross-product: 17 key sources × 11 plaintext sources,
  encrypt and decrypt — no hit on any specimen.
- CBC first/last block over the inner under all key sources ×
  IVs {0, template IV, readback, blob8} — no hit.
- op11-exact CBC-MAC (CBC-enc k1 → DES-dec last block k2 →
  DES-enc k1) with (d2[0:8], d2[8:16]) in both orders, over
  document shapes {inner, doc, stream, inner′, doc′, .opf,
  hdr96, hdr-minus-seed, inner+hdr} — no hit. Plain CBC
  last-block MACs under d2 halves and under blob8/blob8′ keys
  likewise.
- The lifted op11.py run as-is over the .acd doc / inner / post
  doc as its document argument (CID = template CID) — no hit.
  (Consistent with S56's record: op 11's reply for A0's header
  document matches no header field; BIND's buf8 is not the
  querycif reply transplanted.)

## Battery C — widened constructions: ZERO HITS

- HMAC-SHA1 / HMAC-MD5 under keys {d2, gseed, ckey24, trailer,
  key16, blob8} over the base messages — none.
- Iterated hashes SHA-1(SHA-1(m)); SHA-1 over the gate digest
  and gate digest ‖/∘ components {key16, d2, IV, hdr, size};
  every 8-B window of the pre/post gate digests — none.
- Mixed-state gate variants (int1-post/int2-pre and vice versa)
  and the CID20-as-trailer variant (the brief's constant) —
  none.
- Full-template messages (inner ‖ full .ATP, SHA-1/MD5) — none.
- Reply-string relations for the 0524600d family (bb, t2int,
  p3s2; t3big's reply-string harvests are empty files): buf8 is
  not contained in str1/str3, not a SHA-1 window of str3 /
  str1‖str3 / str3‖inner, not a DES-ECB enc/dec of any str3
  window under {d2a, d2b, blob8}. str3 (32 B, per-drive) remains
  an unexplained sibling output — no simple relation to buf8.

## Structural probes — what IS established

- buf8 ≠ blob8(pre-bind inner) and ≠ blob8(post-bind inner′)
  for every int-slot specimen (bb: b4e56ea4… vs 7af96ae4…).
  buf8 ⊕ blob8 is not constant across specimens, so buf8 is
  not the gate value masked by a fixed pad either.
- buf8 appears raw nowhere in its own drive's doc, template
  file, or .opf stream.
- Serialization-sensitivity confirmed from the specimen set
  itself: t3big vs p3s2 differ ONLY in slot-2's tag (04 vs 06)
  over identical 8,192 content bytes, and their buf8s differ —
  the computation consumes the serialized element (or its
  type), not just parsed values.
- S43's gatewatch trace of the bb execute contains the gate
  digest (e225ac50f7b1195f7b0b858d005a63fa54d157b8) being
  copied out — and no buf8 dwords anywhere in the traced
  region. That trace was armed only around the gate SHA-1;
  the execute's other SHA-1 invocations (eight setups counted
  in S43) were never captured.

## Job 5 — forward search for A0: NOT RUNNABLE

The job was conditional on a construction matching ≥2
specimens. None did, so there is no validated function to
forward-search with. A0's genuine seed d883bf8b4359d7c6 and
A1's 25473cd2cc31046c remain unreproduced; S61's refutation of
the disc-order pre-states stands, unextended either way.

## Job 6 — verdict

**The construction was not found. The exhausted space is
large and precisely bounded:** every SHA-1/MD5/SHA-256 window
and fold over ~50 assemblies of all disc-side + known-ceremony
components, HMACs, iterated/gate-derived hashes, the full DES
ECB cross-product, CBC first/last-block relations, and the
exact op11 CBC-MAC dialect over 8 document shapes — with both
the lifted 16-B trailer and the CID20 trailer variant, and
positive controls (blob8 ×5 + ×10 carried values; op11 ×1)
passing throughout. **buf8 is therefore NOT a pure function of
(record bytes, template header/file, d2, global seed, CID, IV)
in any of these standard forms.** At least one input to the
seal sits outside the desk-visible set. The prime suspects,
in order:

1. **The frame's octet16 salwrap session record** — a 16-byte
   ceremony value the host feeds the selector-1 program
   (S61 Job 3 frame anatomy). It was never harvested as bytes,
   so no battery here could include it. If it enters a hash or
   a DES key, every construction above fails exactly as
   observed while the seal stays deterministic in-harness
   (the harness's record is stable) and state-drifting on the
   real system (cf. S61's ceremony-drift caveat on A0).
2. **An internal document assembly** — the program may build
   an op-11-style struct document from the template's .opf
   elements + record elements (querycif's document carries a
   "fopenMG" name element and tag-04 header blobs); the exact
   BIND-side serialization is not held, and MAC/hash over a
   wrong serialization fails silently.
3. **The .opf record's parsed element values** (its first
   key20 d9cedeed57908b33… is compared in the execute's
   compare #1 — the program demonstrably consumes .opf values
   my batteries only used as one opaque 232-B blob).

**Implication for Model 1:** neither confirmed nor refuted in
its keyed form — this battery cannot distinguish "sealed
capsule" from "MAC over unknown inputs", and it is important
not to overclaim either way. What IS excluded is the
*desk-reconstructible* space: buf8 is not a record-keyed DES
seal of d2[0:8] under any tested keying, not a blob8 sibling,
and not any tested verifier-style hash of the known inputs.
The practically decisive consequence stands regardless of
which suspect is real: **the app cannot mint BlockSeeds from
disc-side data + known constants; the ceremony (or the missing
input) is indispensable** — exactly the dependence discs 7–9
showed on hardware.

**Specimens a future harness session should harvest**
(surgical, one-input variations around the bb/t2int states):
1. The frame's octet16 session-record bytes in a BIND drive
   (single most valuable missing input).
2. A sha1in-style capture of ALL SHA-1 invocations of one bb
   execute — every message and digest, not just the gate's.
   If buf8 is any digest window, this names it outright.
3. A trace of the VM's DES-operator invocations in the same
   execute (key, input, output per call).
4. Template-sensitivity isolations under the bb doc:
   (a) A0 with header +0x18 pre-stamp zeroed vs genuine;
   (b) A0 with one payload byte flipped; (c) A2/A3 as template
   (different size + header) — separates size/header/payload.
5. Doc micro-variations under template A0: int1 ±1 at
   (1296064, 1); key16 with one byte flipped at the bb state.
6. The .opf record's element values for A0's content record,
   dumped as separate components for a follow-up battery.
