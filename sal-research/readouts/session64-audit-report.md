# Session 64 — byte-level header/TOC field audit (2026-11-03)

**Question:** the D-NE1 plays genuine tracks and the app-authored twin
with audio, but stays SILENT on disc 10R — a fully app-authored new
track whose known constructions all verify at the desk (BlockSeed
seal, ICV fold, payload cipher, frame-parse 3094/3094). Find the
surface difference, or exhaust the surface provably.

Corpus: BB family A0–A3 (`CD stuff/HIFI/`), appliance track + ISO,
twin (played), 10R (silent), S58 corpora (926 genuine headers:
disc 1 = 493, FavoriteDisc = 432, appliance = 1). Author source read
read-only. Scripts alongside this report.

---

## Job 1 — header field map (DONE)

The 96-byte secure header (.ATP offset 1024) across A0, A1, A2, A3,
appliance, twin, 10R. **100% of bytes accounted for** — the field map
is exactly the author's (`secure_header.py`, readout #7); no hidden
fields exist. 60 of 96 bytes are constant across all seven headers.

| Offset | Len | Field | Class | Values / notes |
|---|---|---|---|---|
| 0x00 | 4 | magic `0100282e` | CONST | identical everywhere |
| 0x04 | 4 | frame_count (BE) | known-derived | = payload bytes / 376; A0–A3 3444, APP/TWIN/10R 3094 |
| 0x08 | 8 | zeros | CONST | |
| 0x10 | 4 | EKBVersion `0001000e` | CONST | = the .STK id |
| 0x14 | 4 | zeros | CONST | |
| 0x18 | 8 | BlockSeed | known-fed / construction | S63b EDE seal; §controls below |
| 0x20 | 8 | block params `010f500000040000` | CONST | = CID20[0:8] |
| 0x28 | 1 | `00` | CONST | = CID20[8] |
| 0x29 | 2 | connum | **varying — registration** | BB-Ignite `4f7e`; appliance `30fb` |
| 0x2B | 5 | CID tail | CONST per install | BB `16725f9be7` (all 925 BB-family headers); appliance `4a559ac07a` |
| 0x30 | 4 | track_slot | **varying — registration** | BB-Ignite `b4f37fbb`; appliance `290e7f21` |
| 0x34 | 4 | zeros | CONST | |
| 0x38 | 8 | zeros | CONST | |
| 0x40 | 4 | `"ATX "` | CONST | |
| 0x44 | 12 | zeros | CONST | |
| 0x50 | 8 | mgd | **varying — registration** | BB-Ignite `2ad14387ddfb4b86`; appliance `757b5fdd1d1129f7` |
| 0x58 | 8 | InitVector | per-instance random | prior 21-formula battery: no relation found |

Header bytes 0x20–0x33 are one object: the 20-byte registration CID
(CID20) laid out as prefix(8) ‖ 00 ‖ connum(2) ‖ install tail(5) ‖
slot(4). Twin vs its genuine source differed ONLY at 0x2B–0x2F
(author's hardcoded BB tail) and the twin PLAYED — the tail is
playback-irrelevant.

**ID3 region (1024 B):** fully modeled by the author and verified:
`ID3` v2.4 header (syncsafe size 1014), frames TIT2/TPE1/TALB in
order, UTF-16BE text = the NDB strings clamped to 30 chars, zero
padding (zero nonzero pad bytes in all seven). Twin and 10R ID3
regions are byte-identical to the genuine appliance track's. A0–A3
carry the same song with different TALB strings (four album rips).
No unmodeled bytes.

### Corpus statistics over 926 genuine headers (job1b)

- **(CID, mgd) are in perfect bijection** on both genuine discs:
  disc 1: 173 distinct CIDs, 173 distinct mgds, 173 pairs, **zero**
  exceptions (no CID with 2 mgds, no mgd with 2 CIDs). FavoriteDisc:
  422/422/422, zero exceptions. → mgd is a per-**registration**
  value, not per-disc and not per-burn (one disc carries 173 of
  them). S56's "mgd = GET_GLOBAL_SEED readback" is true only of the
  Ignite registration, whose ceremony the harness reproduced.
- connum/slot are likewise per-registration: disc 1 has 173 distinct
  connums and slots (clusters of ~1–5 tracks); FavoriteDisc 420
  connums / 422 slots over 432 tracks (connum collisions are
  birthday-expected for a 16-bit value).
- A "registration cluster" = one library content item: within every
  multi-track cluster on both discs the .ATP **size is constant**
  while the ciphertext head (pf16) **varies** — the same content
  re-encrypted per burn with fresh IV/seed.
- A0–A3 are one cluster (same CID/mgd): **all four decrypt under
  BB d2 to the identical plaintext** (ignite.raw, MD5
  021ccc37356b5444d99051befc12e9a6) despite four different IVs and
  four different ciphertexts. → mgd is NOT a function of the
  ciphertext or the IV. (Still open after Job 1: function of the
  plaintext frames / registration key d2 / CID — Job 2 battery.)
- Seeds and IVs: unique per track (493/493, 432/432).

### Positive controls (job2_controls) — all pass

- BlockSeed construction re-derives A0's seed byte-exactly;
  appliance seed unseals under V → d2_app[0:8] =
  76131c8aea09c082, and DES-CBC under it decrypts the appliance
  payload to the genuine frames byte-exactly.
- ICV fold reproduces all three genuine discs' ICVs from S58 sizes.
- blob8 = SHA-1(inner ‖ "ATRAC CD" ‖ CID16-trailer)[0:8] reproduces
  all 7 S43 samples byte-exactly (+ the negative-control value).

### Explicit statement — blob8 / op-11 material on-disc

**blob8 does NOT appear on-disc.** Searched byte-exactly: the disc-1
final-record blob8 (ace078c1751647ba), the FavoriteDisc final
(27b371c30e230160), the bb record states (e225ac50f7b1195f,
7af96ae450de6963), and A0's computed pre-bind blob8
(fda7b1cdb000119b) — in the A0, appliance and 10R .ATP files
(full), the 926-header corpus, and all three genuine TOC sets:
**zero hits anywhere.** The same holds for the op-11 replies
(8150393f51e23848, ce898b93fe607592, edea350d30f3ff63) and for the
ASCII string "fopenMG". The op-11 document and its elements
(inner, blob8, reply) live only in the PC-side SAL ceremony; no
element of them is written to the disc surface. The header's only
key-bearing field is the BlockSeed at 0x18.

### Job 2 — formula hunt on the varying fields (DONE)

**mgd battery (job2b): ZERO hits — not even a one-family near-miss —
across ~700 constructions**: SHA-1/MD5/SHA-256 (4 slice positions
incl. XOR-folds) over 27 inputs (frames, ciphertext, d2, CID20,
CID16, connum+slot, DiscID, seed, IV, frame count, TIT2/TPE1
strings, the 3,168-B .OMA head, and pairwise concatenations);
DES ECB (enc+dec) and EDE under d2[0:8] / K1 / K2 over 14
structured blocks; DES CBC-MAC over frames/ciphertext/.OMA-head;
CRC32/Adler32 combos. A formula had to fit BOTH the BB-Ignite mgd
and the appliance mgd; none fit either one alone.

Combined with Job 1's facts — mgd in perfect bijection with the
registration CID over 925 headers, invariant under re-encryption
of the same content, underivable from every player-visible
quantity — the conclusion is that **mgd is opaque per-registration
state**, minted with the registration exactly like connum and
track_slot (random-looking identifiers in bijection; connum even
shows birthday collisions on FavoriteDisc). There is no desk
formula because there is no formula: the three fields are a
registration's identity papers, carried in the header itself.

**IV battery extension (job2c):** Job 1's only genuinely new input
class was the registration identity; A0–A3 share (d2, DiscID, CID,
mgd, frame count, plaintext) yet carry 4 distinct IVs, so an IV
formula must involve a per-instance input. 19 further constructions
mixing seed / P / ciphertext with mgd / CID under DES, EDE and
hashes: **0/5 on every one** (40 constructions total across both
batteries). The IV is honestly random per burn instance — unique
across all 925 genuine headers — and the author's random IV is
class-correct.

## Job 3 — TOC audit (DONE)

TOC00000.STI and TOC00001.STI across appliance, disc 1,
FavoriteDisc, twin, 10R — parsed field-by-field (job3_toc):

- Fixed part: magic, version LE 1, byte 0x08 = 1, group/track
  counts, **total_seconds == sum(frames_to_seconds) EXACTLY on all
  three genuine discs** (143 / 86,936 / 84,305) — the author's
  modeled field is byte-exact, not approximate. Zero regions
  0x18–0x20 and 0x30–0x100 are zero everywhere.
- Group table: 256 slots; slot 0 zero; used slots well-formed
  (first/last/index, zero tail); counts match (1 / 1 / 11 groups).
- All 926 genuine track records are anomaly-free: number ==
  position, **second index == track number in every record**,
  group in range, zero mid-field, format magic, and frame counts
  identical to the secure-header frame counts.
- TOC00001.STI is the empty PLF form ("PLF " + 01 + zeros,
  2,176 B) on every disc, including 11-group FavoriteDisc.
- Twin TOC == genuine appliance TOC **byte-exact**. 10R's TOC
  differs from the twin's in exactly 23 bytes, **all inside the
  ICV (+0x10) and DiscID (+0x20) regions** — both of which are
  construction-proven for 10R's chosen DiscID and .ATP size.

Genuine DiscID samples (3 genuine burns + OP-A real-method mint +
5 mirror record key16s) show no constant byte, prefix, or internal
structure — uniformly random-looking 16-B values; and disc 7
proved the player *accepts* a foreign DiscID with a correctly
folded ICV (it played, silently). DiscID form is not gated.

## Job 4 — author cross-read (DONE)

Per field: what the author writes (10R build) vs what Sony writes.

| Field | Author (10R) | Genuine | Verdict |
|---|---|---|---|
| frame_count | computed from payload | same | ✓ exact |
| BlockSeed | fed the S63b construction value | SAL-minted, same construction | ✓ byte-provable |
| IV | fed random | random per instance (no formula exists) | ✓ class-correct |
| block params / magic / EKBVer / zeros / "ATX " | constants | constants | ✓ |
| CID tail 0x2B–0x2F | hardcoded BB tail | per-install tail | ⚠ wrong for a novel install — **but the twin PLAYED carrying this exact wrong tail** → playback-irrelevant, exonerated |
| connum / track_slot / mgd | fed BB-Ignite registration's genuine triple | opaque per-registration state | ⚠ **the one graft**: 10R's header claims the track is BB's "Ignite My Heart" registration while the content is "Want You Gone". For a genuinely novel track no Sony value exists — a new registration's papers can only be self-minted — but 10R did not self-mint; it borrowed another content item's identity, coherently (a real CID↔mgd pair) |
| TOC all fields | modeled | — | ✓ byte-exact (Job 3) |
| ID3 / NDBs / STK / PLF | modeled | — | ✓ byte-identical to genuine for the same strings (twin proof; 10R file set differs from the twin ONLY in TOC IDs + .ATP) |

So the author has exactly one field class it cannot produce the
"Sony value" for — registration identity (connum/slot/mgd) — and
that is not an author defect: the value is minted state, not a
computation. Every computable field it computes correctly.

## Job 5 — VERDICT

**The header/TOC surface is exhausted.** Every byte of the
96-byte secure header, the 1,024-byte ID3 region, both TOCs, the
NDBs, the PLF and the STK is classified; every varying field is
either construction-proven (seed, ICV, frame_count), honestly
random in genuine discs too (IV, DiscID), or opaque registration
state with no desk-computable formula (connum, track_slot, mgd —
~700 constructions, zero hits, bijection-proven). blob8 and all
op-11 material are proven absent from the disc. The complete
twin→10R delta is: TOC (ICV+DiscID), header (seed, IV, and the
registration triple), and the payload — each individually
desk-verified. No field exists that 10R "carries wrong" in the
sense of a miscomputed formula.

What remains is player-side, ranked:

1. **The registration triple is checked player-side under a
   player-held key.** The player cannot recompute mgd from
   disc-visible data under any standard construction (this
   audit) — but it holds the EKB ladder (the .STK's key material),
   so it *could* verify e.g. a MAC over (CID, recovered key,
   DiscID) against mgd. 10R's graft (Ignite's papers on WYG's
   content, under a third key and a fourth DiscID) would fail any
   such binding; the twin (all-genuine appliance papers) passes.
   **Convicting experiment:** burn X = 10R with ONLY the
   registration triple + tail swapped to the appliance track's
   own genuine values (connum 30fb, slot 290e7f21, mgd
   757b5fdd1d1129f7, tail 4a559ac07a), keeping 10R's DiscID, d2′,
   seed, IV, payload. Audio ⇒ the graft was the fault. Silence ⇒
   suspect 1 is dead and the key itself is gated (suspect 2).
2. **The recovered content key is validated against the EKB
   ladder.** Genuine d2 values are 20-byte ceremony artifacts;
   the seed may transport not the payload key but a ladder
   intermediate, with genuine d2[0:8] passing because it *is* the
   ladder's output for a registered content item, while a random
   d2′ is not a ladder output for anything. Desk evidence is
   consistent but not decisive (payloads open with d2[0:8]
   simpliciter on both families — the ladder step, if any, is
   identity on genuine keys). **Convicting experiment:** burn Y =
   10R with d2′ replaced by the genuine BB d2 (payload re-encrypted
   under 3d14fb8d…, seed recomputed over 10R's DiscID at ctr 0,
   BB registration triple kept). Audio ⇒ novel keys are what's
   gated, and the app must author with a real install's d2 (which
   we hold). Silence ⇒ even a genuine key fails on a foreign
   disc, and the binding sits in the DiscID/registration layer.
3. **mgd as a player-side key-derivation input.** Weakest: two
   desk facts cut against it (payload opens with d2[0:8] alone on
   both families; the seed unseal ignores mgd). It survives only
   as a special case of suspect 1. Burn X discriminates it too:
   X carries the genuine mgd for the content.

Note the acceptance pattern across discs 7–10R: the player loads
every one of these discs, lists the track, and runs — it withholds
audio. That is the signature of a key-path/check failure at
decode time, not a furniture rejection — consistent with all
three suspects and with the desk finding that the furniture
(TOC/NDB/STK/PLF/ISO) is byte-perfect.

---
