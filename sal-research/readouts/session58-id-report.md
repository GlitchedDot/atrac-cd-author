# Session 58 — HOW ARE THE TOC DISC IDs MINTED? (desk-only, 2026-11-03)

No builds, no burns, no harness drives. Analysis + computation only.
(Written incrementally; sections land as each job completes.)

## Established inputs

- Disc 5 (twin + fresh random TOC IDs, full-ISO diff = exactly 24 B) DIED;
  the twin with the appliance disc's genuine IDs PLAYED on a different
  physical burn. => The player verifies the ID pair (id_a 8 B @TOC+0x10,
  id_b 16 B @TOC+0x20) against the authored content somehow; IDs are not
  bound to the physical burn.
- S57: IDs occur ONLY at those two TOC slots; NOT an unkeyed MD5/SHA-1/
  SHA-256 of ~40 content constructions.
- Three genuine targets (all re-verified in this session's prep from the
  discs' own TOC00000.STI bytes):
  - appliance: a8fb3de83fc4b6b5 / fb23c921c0fce07e3f254e270dabe815 (1 track)
  - disc 1:    1c323bbee328c1f5 / f4a79f2142ee36fbf85052b79a17ad8d (493 tracks)
  - FavoriteDisc: 914b4bf7743c7fb9 / f59b0b4af42af1507142dc26191d97f1 (432 tracks)
- Prep note: disc 1's FULL file set was recovered for this session by
  de-interleaving the raw 2352-B/sector ImgBurn BIN
  (disc-image/imgburn/atrac-disc1.bin, Mode-1 sectors, user data @+16):
  all 493 .ATPs present, TOC IDs match the S57 census values exactly.
  (The 2048-B de-interleave was session scratch in ~/tmp-mega, deleted
  after the run; prep.py regenerates it.)
- DES: PyCryptodome, cross-validated block-for-block against the proven
  clean-room fastdes (50 random ECB enc/dec pairs + a 257-block CBC run,
  all identical). A construction counts ONLY if it reproduces id_a or
  id_b on ALL THREE discs.
- Useful structural facts used below: TOC00000.STI = 2304-B fixed part
  (IDs inside it) + 16 B/track records (verified arithmetically on all
  three discs: 2320 = 2304+16×1; 10192 = 2304+16×493; 9216 = 2304+16×432).
  Secure header layout (S56 census): frame count BE u32 @+0x04, BlockSeed
  @+0x18, CID 20 B @+0x20, mgd @+0x50, IV @+0x58. (Appliance header
  [4:8] = 0x00000c16 = 3094 ✓.)

## Job 1 — derivation battery v2

### Part 1 (battery1.py): 30,477 constructions — ZERO hits

Run identically on all three discs; hit = reproduction of id_a or id_b
(byte-reversed forms also accepted) on ALL THREE. Log: battery1-log.txt.
**Positive control:** a planted CBC-MAC value is correctly flagged by the
matcher on each disc (and the real id_a is confirmed ≠ that MAC), so the
zero is a true zero.

Key universe: 997 keys — d2 windows [0:8]/[4:12]/[8:16]/[12:20]; global-seed
windows; every aligned 8-B window of the STK plus sliding windows across
its three entropy regions (0x38…, 0x58…, 0x84…); every aligned window of
every sibling .ekb (00000002, 00010001, 00010002, 0001000A, 00010012-umd,
00010013-hdd, 00010017-hdd, 0001001D-bot, 00010021-hdd) plus sliding
windows over their first 64 B; SHA-1/MD5-derived keys sha1(d2)[0:8],
sha1(seed)[0:8], sha1(stk)[0:8], md5(d2)[0:8].

Inputs: TOC raw / IDs-zeroed / fixed part / fixed-zeroed / records region;
concatenated secure headers; track 1's header; concatenated BlockSeeds /
IVs / CIDs / mgds; the four string NDBs concatenated; TOC00001.STI;
PLLIST.NDB.

Constructions:
- DES CBC-MAC (zero IV, zero padding) under all 997 keys × 14 inputs;
  candidates = last block, last 16 B, first block.
- DES CBC *decrypt*-chain MAC, d2/seed keys.
- EMAC (the op-11 tail form E_k1(D_k2(mac))) for the d2 pair, the swapped
  d2 pair, the seed pair, and same-key — × 14 inputs.
- Single-block DES encrypt AND decrypt of 8 fixed plaintexts (zeros,
  toc[0:8], toc_z[0:8], toc_z[8:16], STK[0:8], ASCII "0001000E",
  header[0:8], id_a itself) under all 997 keys.
- Keyed digests MD5 / SHA-1 / SHA-256, key‖content and content‖key, for
  key ∈ {d2, seed, STK, STK[0x38:], 0001000A.ekb, 00000002.ekb} × 7 inputs;
  all digest windows scanned. (Plus unkeyed controls on the same inputs.)
- XOR folds: all BlockSeeds, all IVs, all CIDs (20 B), all mgds, all
  payload first-8 blocks, all headers (96 B).
- CRC32 / Adler-32 / CRC-16-CCITT (both inits) / 32-bit word sums (LE+BE)
  over 5 inputs — 4-B and 2-B candidates vs every window of the IDs.
- Scalar blocks (track count, total_seconds, total frames; u32/u64, LE/BE)
  raw and DES-encrypted/MACed under the d2/seed key heads.
- Relational: md5(id_a), sha1(id_a), md5(id_a‖d2), sha1(d2‖id_a),
  DES-enc/dec(id_a) under d2/seed heads — vs id_b.

### Part 3 (per-disc derived keys): 52 constructions — ZERO hits

Keys derived from each disc by a fixed rule (track 1's BlockSeed / IV /
mgd / CID windows, last track's BlockSeed, XOR of all BlockSeeds / IVs,
SHA-1(track-1 header)[0:8], track-1 header[0:8]) — DES CBC-MAC over
toc_z / toc_fixed_z / records / headers; plus MD5/SHA-1/SHA-256 of
header-material‖toc_z in both orders. All negative on all three discs.

### Part 2 (battery2.py + battery2b/2c + verify passes): 136 constructions — ZERO hits

Whole-disc-scale and remaining constructions:

- DES CBC-MAC (zero IV, zero padding) over the **whole file set in ISO
  extent order**, three variants — as-authored (FS-raw), TOC IDs zeroed
  (FS-ztoc), TOC00000 omitted (FS-notoc) — under the 14 head keys (d2 and
  seed windows, STK @0x38/0x58/0x84, SHA-1-derived keys). Candidates:
  last block / last 16 B / last 32 B windows.
- Same over **all .ATPs concatenated** (ATP-cat) and **all payloads
  concatenated** (PAY-cat), 14 keys each.
- EMAC (op-11 tail) over FS-raw and FS-ztoc under the d2 pair.
- CBC-MAC with **nonzero IVs** (STK@0x38, STK@0x58, d2[12:20],
  seed[12:20], ASCII "0001000E") × keys {d2[0:8], seed[0:8], STK@0x38} ×
  inputs {toc_z, headers, toc_fixed_z} — 45 constructions.
- CBC-encrypt of the TOC fixed part's first 64 B under all 14 head keys,
  every output block scanned — 14 constructions.
- **OP-11-shaped check (battery2c):** op11's reply tail reimplemented on
  PyCryptodome and *proven* against Session 35's four oracle vectors
  (candidate5/6/5-A1/7 → 8150393f…, ce898b93…, edea350d…, dce3d57d… — all
  reproduced exactly). Five TOC-shaped documents (raw toc_z; the SAL
  struct-serialisation idiom [30 80 + "fopenMG" + 20-B tag-04 chunks]
  over toc_z / fixed part / records; a fields+records serialisation)
  were run through it: no document yields any disc's id_a. (Expected in
  hindsight: S56 already established op 11's reply is a per-track header
  check value that appears nowhere on any disc.)

**Methods note (honest accounting):** battery2.py's first run hit its
900-s timeout mid-way and this environment's background-stdout delivery
proved unreliable, so its hit/miss outcomes were not trusted from that
run. Every part-2 construction was therefore **re-verified with outcomes
written to files** (verify-fs-results.txt, verify2-results.txt), the
second pass using appliance-first filtering: a construction must match
on all three discs, so each was evaluated on the 1.2-MB appliance disc
first — all 64 filter-pass constructions died on the appliance alone,
and the 8 head-key FS-raw constructions additionally hold full
three-disc written negatives. Final part-2 tally: 72 file-set/EMAC
constructions + 45 IV-variant + 14 block-read + 5 op-11 = 136, zero hits.

### Battery grand total

**30,665 constructions, ZERO hits** (30,477 part 1 + 52 part 3 +
136 part 2). Together with S57's unkeyed battery, the ID pair is not
derivable from disc-side data by any digest, MAC, fold, or
serialisation construction we can express with the key material in
evidence.

## Verdict — ranked model of what the player verifies

Established: the player verifies the 24 ID bytes against *something*
(disc 5); the verification is bound to the authored content, not the
physical burn (the twin transplant); the values are not a function of
disc-side data under any held key (this session); the furniture writer
(CDRFormatter.dll) contains no crypto and no ID setter, yet owns an
**ICV** concept (GetICV) and instantiates COM components.

1. **M1 (leading) — the ID pair is key-layer output, sealed/MACed under
   material the disc side does not hold — a sibling of BlockSeed.**
   id_a (8 B) and id_b (16 B) are one and two DES blocks respectively.
   The player unseals/decrypts them down the EKB ladder (the STK names
   v0x0001000E; the root is in player firmware, S56) and checks the
   recovered plaintext, which plausibly encodes a content digest — the
   disc's ICV — making the pair content-bound without being computable
   from the disc. This fits every observation: keyed minting invisible
   to 30k+ disc-side constructions; a crypto-free formatter that merely
   writes opaque values it is handed or generates via its COM engine;
   GetICV existing in exactly this component; and Sony's uniform pattern
   in this system (op 11's reply and BlockSeed are likewise key-layer
   values no consumer recomputes from disc data).
2. **M2 — a keyed MAC under a key not in evidence, most plausibly the
   minting install's own ceremony constant.** d2 is the OLD install's
   constant; disc 1 and FavoriteDisc are old-install lineage, so their
   negatives under d2 are meaningful. The appliance disc is a NEW
   install whose d2-analogue is unknown — for that disc, single-key
   MAC forms are formally untested, and the all-three-discs criterion
   is unsatisfiable by construction if keys are per-install. (Labelled
   gap in this battery, stated plainly.) The minting would still live
   on the authoring side, not in any SAL op we have driven.
3. **M3 — form-only verification: any genuinely minted pair would play
   on any content.** Weakened (it requires the player to check a
   self-contained blob, which the ICV/content framing argues against)
   but NOT discriminated by any burn yet: disc 5's random IDs die under
   all three models. S57's fork — the clone rebuilt with disc 1's
   genuine ID pair — is the discriminator, and it has not been burned.

**Class conclusion (as briefed):** under M1/M2 the IDs are
**unmintable from disc-side data** — the same locked room as BlockSeed
sealing (S56): the minting key path runs through the EKB/key layer
whose root sits in player firmware, and the authoring-side generator
lives in the CDRFormatter/COM-engine workflow that no held harness has
ever driven.

## What a harness would need to mint IDs

- **Drive the authoring path, not the rip/bind ceremony.** Concretely:
  an emulated or captured CDRFormatter session — CreateCDRFormatFiles /
  Burn fed with genuine CSecureAudioHeader inputs — or the COM burn
  engine it instantiates (ole32 CoCreateInstance + CLSIDFromString),
  watching where the 24 ID bytes first appear. This is S55's "remaining
  field (ii)" (a host-side act at real device/disc-write time) with a
  now-named target: CDRFormatter.dll (GetDiscID RVA 0x29e4e, GetICV RVA
  0x29f84 — both readers; CreateCDRFormatFiles RVA 0x299bd → internal
  worker RVA 0x1d93f; medium-info helper RVA 0x99b3).
- **Or capture a genuine authoring session on the appliance** (the
  working SonicStage install): an API/memory trace of one real burn,
  bracketing the moment TOC00000.STI is written — the same route (b)
  that has always been Lola-led.
- **If M2 is the truth:** recover the appliance install's ceremony
  constant the way d2 was recovered for the old install (oracle work
  against that install's OpenMG state), after which the MAC battery
  re-runs cheaply.
- **Before any of that:** burn S57's fork disc (clone + disc 1's
  genuine ID pair). It is one blank, it discriminates M3 from M1/M2,
  and under M3 the practical problem changes completely (one harvested
  genuine pair could, in principle, be carried by the app).

## Artefacts

- prep.py / <disc>.json / <disc>_headers.bin / <disc>_root/ — the three
  verified disc corpora (disc 1 completed from the ImgBurn BIN).
- battery1.py + battery1-log.txt (30,477 constructions);
  battery2.py / battery2b.py / battery2c.py + logs (136);
  verify_fs.py + verify-fs-results.txt, verify2.py + verify2-results.txt
  (written-outcome re-verification of all whole-disc constructions).
- Scratch streams (~7 GB under ~/tmp-mega/s58/ and the de-interleaved
  ~/tmp-mega/disc1-2048.iso) are regenerable from prep.py/battery2b.py
  and were deleted after the run.

## Job 2 — ceremony re-mine for an ID-minting operation

### The SESSION note / Ghidra corpus: CLEAN NEGATIVE for the SAL world

- SESSION-2026-10-28.md contains **zero** occurrences of "TOC" at all,
  and none of "disc id" / "DISC_ID" / "GetDiscId" / "discid". The entire
  S25–S55 harness campaign (querycif / omgatpcd / pfcom rip-and-bind
  path) never touched disc authoring or the TOC. No SAL op in the driven
  corpus ever returned ID-shaped (8+16 B) authoring output; the only
  per-item key-layer output ever observed is BIND's per-track SEED8
  (Session 56).
- No file in ~/workspace/atrac-salwrap-work/out/*.c mentions "TOC00000"
  or ".STI" (or "TOC" at all). The held Ghidra corpus has no
  furniture-writing function.
- String census of ALL held Toshiba-tree binaries: **"TOC00000" occurs
  in exactly ONE binary — CDRFormatter.dll** (Sony Shared/AVLib). No
  .ocm, no OpenMG DLL, no SonicStage app binary in the held trees
  contains it.

### The author is CDRFormatter.dll — and it has no crypto in it

CDRFormatter.dll (360,448 B, AVLib) is the ATRAC CD format/burn engine:
it owns every furniture filename (\TOC00000.STI, \TOC00001.STI, the five
NDBs, \HIFI\TRK0%04X.ATP, \????????.STK) and exports the full authoring
API (CreateCDRFormatFiles, Burn, AddTrack, BeginToCreateTrack taking a
CSecureAudioHeader, GetEKBFile, CheckEKBVersion…). Findings:

- It exports **GetDiscID** (ord 83) and **GetICV** (ord 96) — but bounded
  capstone disassembly shows both are **readers**: each requires the
  formatter initialised, calls SelectDrive(path), pulls a 13-field
  medium-info struct via an internal helper (RVA 0x99b3), then extracts
  one field through a helper returning 0x203 on success. They read an
  existing medium's DiscID / ICV (the retry/compare flows — cf.
  RetryBurn, CompareData, CreateCDRFormatFilesForRetry). Neither mints.
- There is **no SetDiscID / SetICV export**. CreateCDRFormatFiles itself
  is a 301-B wrapper (SelectDrive + medium-info + one internal worker at
  RVA 0x1d93f). So the ID pair is generated *inside* the formatter's
  workflow (or by the COM burn engine it instantiates — it imports
  ole32 CoCreateInstance + CLSIDFromString), from inputs the formatter
  holds: the tracks' secure headers, the EKB record, medium/registry
  state, and time (it imports GetTickCount / GetSystemTimeAsFileTime /
  GetLocalTime from KERNEL32).
- **No minting arithmetic is visible in the binary**: DES S-box bytes
  absent; SHA-1, MD5, SHA-256 and CRC32 constants all absent; ADVAPI32
  imports are registry functions only (no Crypt*); ole32 has no
  CoCreateGuid; MSVCR71 imports include no rand/srand/time. Whatever
  produces the 24 ID bytes inside this component is either table-free
  custom arithmetic over formatter-internal inputs, or delegated.
- Only two other held binaries even reference CDRFormatter by name:
  CDWalkman.dll and AtpFringe.dll (AVLib siblings).
