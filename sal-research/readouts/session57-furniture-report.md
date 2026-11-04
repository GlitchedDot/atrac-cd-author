# Session 57 — FURNITURE FORENSICS (desk-only, 2026-11-03)

Question: the app-authored TWIN played; discs 2, 3 and the CLONE (track file
byte-identical to genuine Ignite A0) died. The track is exonerated — what at
disc/furniture level decides playability?

Corpora (all byte-read in this session): genuine appliance disc (from
newiso.iso), genuine "CD stuff" disc-1 set (493-track TOC, HIFI subset),
genuine FavoriteDisc (432 tracks, ISO), twin, clone, discs 2/3.

## Q1 — Disc-ID cross-reference census

Each disc's two IDs (TOC00000.STI @0x10–0x17 "id_a", 8 B; @0x20–0x2F "id_b",
16 B) were searched — as-is, byte-reversed, and in 4/8-byte fragments —
across EVERY file of the disc's own file set:

| disc | id_a | id_b | occurrences anywhere |
|---|---|---|---|
| genuine appliance | a8fb3de83fc4b6b5 | fb23c921c0fce07e3f254e270dabe815 | TOC @16, @32 ONLY |
| genuine disc 1 | 1c323bbee328c1f5 | f4a79f2142ee36fbf85052b79a17ad8d | TOC @16, @32 ONLY |
| genuine FavoriteDisc | 914b4bf7743c7fb9 | f59b0b4af42af1507142dc26191d97f1 | (root furniture read; same slots) |
| twin (PLAYED) | = appliance's | = appliance's | TOC @16, @32 ONLY |
| clone (DIED) | 4cd99dbdd3f5bea1 | a80e8435063fae52d8a1ed5e48adaf7f | TOC @16, @32 ONLY |
| disc 3 (DIED) | 1313b531a93caa9e | 2ccf35fd16d68a9d867be6d032533322 | TOC @16, @32 ONLY |
| disc 2 (DIED) | 5ac7aa2f96a7a3b0 | 796d6a7101f6ff032d1360f16cad21c6 | TOC @16, @32 ONLY |

**Verdict on the naive form of the hypothesis: DEAD.** Genuine discs also
carry their IDs in exactly ONE place — the author writes them everywhere a
genuine disc does. There is no second furniture location whose consistency
the clone could be failing. If the player validates the IDs at all, it must
validate them against a value it computes itself from other on-disc data
(the digest-derivation question — see Q3) or not at all.

## Q2 — How genuine furniture references track A0 (and what the clone says instead)

A0's home: the "CD stuff" disc. Slot mapping proven by content, not assumed:
file suffixes are hex track numbers — TRACK.NDB record #160 (0xA0) reads
"Adikop - Ignite My Heart (feat" / album "NCS ; Copyright Free Music For" /
artist "NCS Arcade" = A0's exact tags, and TRK0000A's record #10 matches its
own title. So on its home disc A0 is **track 160 of 493, in the disc's only
group ("New Group", tracks 1–493)**.

Searched all of disc 1's furniture (TOC00000, TOC00001, TRACK/ALBUM/ARTIST/
GROUP/PLLIST NDBs, STK) for every A0 identity byte-string:

| A0 identity value | in genuine furniture |
|---|---|
| connum 4f7e (either endianness) | ABSENT |
| track_slot b4f37fbb (either endianness) | ABSENT |
| BlockSeed d883bf8b4359d7c6 | ABSENT |
| InitVector 25a671276b529c02 | ABSENT |
| mgd @+0x50 2ad14387ddfb4b86 | ABSENT |
| full CID / CID head | ABSENT |
| filename "TRK000A0" (ASCII / UTF-16BE) | ABSENT |
| frame count 3444 as u32 BE | TOC00000 @4844/4860/4876/4892/4908 — the five 3444-frame track records (159–163) |

**Genuine furniture references a track ONLY by position**: TOC record index
(= track number = hex file slot), its group byte, and its frame count. No
furniture byte anywhere cross-checks the .ATP header's connum, track_slot,
BlockSeed, IV, mgd or CID. The same holds on the appliance disc for WYG's
identity values (checked in Q1/Q3 searches: nothing outside the ATP).

Clone audit: the clone's furniture is internally consistent as a one-track
disc — TOC record #1 {num 1, second 1, group 1, magic 0100282e, 3444
frames}, NDB strings = A0's tags, group 1 = the album string, range 1–1.
Every location where genuine furniture encodes anything about a track, the
clone encodes the analogous thing for "A0 as track 1". The ONLY genuine-
furniture fact about A0 the clone does not reproduce is its POSITION
(160th of 493 in group "New Group") — and position is not encoded in the
track file itself, so no on-disc cross-check between position and header
exists for the player to fail. Position remapping alone cannot be the
killer via any furniture-visible mechanism. (Hypothesis, labelled: a
player-internal rule keyed to position is conceivable but has no byte
evidence and no plausible function.)

## Q4 — ISO/session geometry: RULED OUT

Twin ISO vs clone ISO, parsed at the sector level:
- PVD: identical in every field except volume_space_size (601 vs 665 —
  follows from the larger .ATP). Volume id = 32 spaces in both; app id
  blank in both; path-table size 22, L table @18, M table @19, root
  record extent 20 — all identical.
- Path tables (L and M): byte-identical.
- Directory records: identical file order and IDENTICAL extents for every
  file (STK @22, NDBs @23–26/31, HIFI dir @21, TOC00000 @27, TOC00001 @29,
  .ATP @32 in both). Only the .ATP's size (and the total) differs.
- Both were burned via the same route (session 1, unfinalized, open empty
  session 2) as the genuine appliance burn.

Nothing ISO-level distinguishes the played twin from the dead clone.

## Q3 — Field-by-field annotation; hunting unmodelled/checksum fields

TOC00000.STI, genuine appliance vs clone (both 2,320 B): the ONLY differing
ranges are @15 (low byte of total_seconds, 143 vs 159), @16–23 (id_a),
@32–47 (id_b), @2318–19 (low bytes of the track record's frame count,
3094 vs 3444). TOC00001.STI and PLLIST.NDB are byte-identical across ALL
six corpora (fixed empty forms). GROUP.NDB differs only in the group-name
string. Verified genuine header regions the author leaves zero ARE zero on
genuine discs (@0x18–0x1F, @0x30–0x100, unused group slots). The track
record's "second index" equals the track number in all 493 genuine disc-1
records (author's model exact). The .ATP ID3 tags carry only
TIT2/TPE1/TALB — no track-number frame exists to mismatch.

**total_seconds (@0x0C): EXONERATED — and the author's model is better than
its own docstring claims.** The field equals sum-over-tracks of
int(frames × 2048 / 44100) EXACTLY on all three genuine discs (86,936 over
493 tracks; 84,305 over 432; 143 over 1). The clone's 159 is precisely what
that formula yields for A0, i.e. what SS would write. Not a suspect.

That leaves exactly ONE furniture field-pair that is (a) different between
the played twin and every dead app disc, (b) not determined by the disc's
content under any author model, and (c) not content-legit like tags/frame
counts: **the TOC disc IDs themselves** — genuine on the twin, fresh-random
on discs 2, 3 and the clone. For the player to distinguish them, SS must
mint them as a FUNCTION of something (content or ceremony state) that the
player can recompute or verify. Digest-derivation tests follow in Q3b.

## Q3b — Are the genuine disc IDs a digest of the disc's content? NO (unkeyed)

Battery run against BOTH complete genuine discs (appliance, FavoriteDisc),
every construction required to match id_a (8 B) or id_b (16 B) in any window:

- MD5 / SHA-1 of: each individual file; TOC with id_a zeroed / id_b zeroed /
  both zeroed; TOC00001; STK; PLLIST; the five NDBs concatenated; ALL files
  concatenated in ISO order (with and without zeroed IDs); all .ATP files
  concatenated; all payloads concatenated; track 1's .ATP / payload / secure
  header alone; concatenation of per-file MD5s; id_a and id_b themselves.
- MD5 / SHA-1 / SHA-256 of: all secure headers concatenated; CIDs,
  BlockSeeds, IVs, mgds concatenated separately; (CID‖BlockSeed) per track
  concatenated; the TOC track-records region; the TOC header with IDs
  zeroed; the NDB string files.
- MD5 / SHA-1 / SHA-256 of d2-involved inputs: d2 alone, SHA-1(d2),
  d2‖TOC(no IDs), TOC(no IDs)‖d2, d2‖id_a, id_a‖d2.
- Byte-reversed digest windows included throughout.

**Result: NONE — zero hits on either disc.** The genuine IDs are NOT an
unkeyed digest of any on-disc content construction tested. ( FavoriteDisc
census addendum: its IDs likewise occur ONLY at TOC @16/@32 — full
furniture searched, and none of its 432 .ATPs contains either ID in either
orientation.)

Interpretation: if the player validates the IDs, the minting must involve
material NOT recoverable from the disc — ceremony state (a keyed hash /
sealed value, the same locked room as BlockSeed per Session 56) or the
burn session itself. A keyed/sealed minting is consistent with everything
Sony-side in this project: the IDs would be key-layer output, and the
author's RNG impersonation produces bytes of the right shape but the wrong
provenance. (Hypothesis, labelled — the battery cannot distinguish "keyed
content derivation" from "IDs bound to the minting install/session".)

## Ranked suspect list

1. **TOC disc-ID provenance (id_a @0x10, id_b @0x20).** By exhaustive
   elimination this is the only non-content furniture delta between the
   played twin and the dead clone: the twin is the sole app disc carrying
   genuine SS-minted IDs, and they are genuine *for its exact content*.
   Simple content-digest forms are disproven (Q3b); the surviving forms
   are keyed/ceremony mintings the author cannot reproduce by feeding
   random bytes. PRIME SUSPECT.
2. **Header↔disc lineage coherence** (Session 56's Model-3 rider): the
   player may require a disc's tracks to issue from the same install/
   repository ceremony as the disc furniture — the clone marries disc-1
   (BB) headers to a foreign one-track disc, while the twin is the
   appliance install's own track on its own disc, IDs included. No
   furniture byte encodes lineage (Q2), so if this is the mechanism it is
   enforced player-side, plausibly via the same key layer as #1. The two
   suspects may be one mechanism wearing two descriptions.
3. **RULED OUT, with byte evidence**: ISO/session geometry (Q4 — twin and
   clone ISOs structurally identical, same extents); track-position and
   header-identity cross-references (Q2 — genuine furniture contains
   none); total_seconds (Q3 — author's formula reproduces SS exactly on
   926 genuine tracks); every other TOC/NDB/PLF/STK field (byte-exact
   author models); extra ID copies elsewhere in the furniture (Q1 —
   none exist); the .ATP/track itself (the clone control); ID3
   track-number mismatch (no TRCK frame exists in either genuine tag).

Note on discs 2/3: their deaths remain independently explained (plaintext
payload; Frankenstein header per S56) — they are confounded and are NOT
counted as evidence for suspect #1. The clone is the only unconfounded
death, and #1/#2 are what it isolates.

## The single-variable next disc (spec only — NOT built)

**"Twin-minus-genuine-IDs."** Rebuild the played twin EXACTLY — same
payload (appliance .OMA frames, identity class), same fed header values
(block_seed a2e39b5e80b925a4, IV 5f231f406a2892ee, connum 30fb,
track_slot 290e7f21, mgd 757b5fdd1d1129f7), same tags/group, same build
inputs in every other respect — changing ONE variable: the TOC disc IDs.
Feed disc_id_a / disc_id_b as FRESH author-RNG values instead of the
genuine appliance pair (a8fb3de83fc4b6b5 / fb23c921c0fce07e3f254e270dabe815).

- **It DIES** ⇒ the 24 ID bytes are the discriminator: genuine, content-
  bound ID provenance is necessary for playback, suspect #1 convicted.
  Follow-up fork: the clone rebuilt with DISC 1's genuine ID pair
  (1c323bbee328c1f5 / f4a79f2142ee36fbf85052b79a17ad8d — the only genuine
  IDs sharing the clone headers' BB lineage) separates "IDs must be
  genuine for this content" from "IDs must share the headers' lineage".
- **It PLAYS** ⇒ IDs are exonerated entirely; suspect #2 (lineage)
  becomes prime, and the follow-up is that same clone + disc-1-IDs build.

Either outcome halves the remaining space for one blank, and the build
differs from a proven-playable disc in exactly 24 known bytes.
