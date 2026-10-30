# Stage 1 — disc author report: the full authoring pipeline, cipher hole and all

Date: 2026-10-22. Tree: `~/workspace/atrac-cd-author/` (Python 3,
stdlib-first; pycdlib for ISO writing). Lola approved this build —
including the ladder content — on 2026-10-22.

**Headline: the whole disc-making machine now exists and is validated
byte-for-byte against both of Lola's real SonicStage discs everywhere
the format is understood. The one remaining hole is exactly the one
we knew about: the payload cipher, which sits behind a single
documented interface function.**

## What was built

Package `src/atrac_author/`:

| Module | Job |
|---|---|
| `ndb.py` | TRACK / ALBUM / ARTIST / GROUP / PLLIST .NDB parse + write |
| `sti.py` | TOC00000.STI + TOC00001.STI ("PLF") parse + write, field-annotated |
| `stk.py` + `stk_data.py` | 0001000E.STK as the verified byte-identical copy |
| `id3tag.py` | the 1,024-byte ID3v2.4 tag at the head of every .ATP |
| `secure_header.py` | the 96-byte secure header, per readout #7's map |
| `atp.py` | .ATP assembly + the track-filename law |
| `cipher.py` | **the cipher interface + placeholder (see contract below)** |
| `capacity.py` | the byte-exact capacity accountant with refusal |
| `iso.py` | ISO 9660 writer (pycdlib) + an independent verification reader |
| `author.py` | orchestration: track list → file tree → capacity-checked ISO |

Driver scripts: `validate.py` (the ground-truth suite) and
`build_ladder.py` (the demo disc).

## Validation verdicts — 30/30 checks pass

Suite: `cd ~/workspace/atrac-cd-author && python3 validate.py`.

**Byte-exact against ground truth:**

- **All ten NDB files** (TRACK/ALBUM/ARTIST/GROUP/PLLIST × disc 1 +
  disc 2): parse → rewrite is **byte-identical**, including disc 1
  ALBUM.NDB's 39 all-zero empty records (tracks with no album string —
  an empty string is stored as an all-zero record; modeled and
  round-tripped).
- **TOC00000.STI, both discs**: parse → rewrite is **byte-identical**
  (with the modeled fields carried through parse — see the
  understood/modeled split below; the layout, group table, and track
  records are exact).
- **TOC00001.STI, both discs**: the generated empty-playlist file is
  **byte-identical** (2,176 B: "PLF " + version byte + zeros).
- **0001000E.STK, both discs**: byte-identical copy (172/172),
  confirming readout #8 once more.
- **All 7 sample secure headers**: parse → rebuild **byte-identical**
  — every constant, offset, and variability class in readout #7's map
  reproduced exactly.
- **Ignite My Heart .ATP reassembly**: from the parsed ID3 tag +
  secure header of the real TRK000A0 and the banked plaintext, the
  rebuilt file's first 1,120 bytes are **byte-identical to the
  original**, and the size law holds exactly (1,296,064 = 1,294,944 +
  1,120).
- **Track-filename law**: `TRK` + **%05X** of the 1-based track
  number — regression-checked against TRK0000A / TRK000A0 / TRK000DC /
  TRK000E1. (Caught during this build: the filenames carry FIVE hex
  digits; readout #1's "TRK0%04X" shorthand undercounts. Disc 1's
  TOC frame-count field had already proven the number↔track mapping:
  2,911 / 3,444×4 / 3,341 / 3,039 for the five known tracks.)
- **ISO read-back**: the ladder ISO was re-read with an **independent
  minimal ISO 9660 reader written for this purpose** (no shared code
  with pycdlib): 17/17 files, sizes and SHA-256 hashes all match the
  authored tree.
- **Capacity refusal**: proven live — the ladder tree budgeted
  against a custom 10,000-sector blank is refused with
  `estimated 19141 sectors exceeds blank capacity 10000 sectors`
  before anything is written, and a post-build exact check unlinks
  any ISO that comes out over.

## Understood vs modeled — the honest split

**Understood** (measured, cross-validated on two discs): NDB header +
records + the 30-char string law + empty-record form; TOC group table
(0x100, 8-byte slots, first/last track + group index) and track
records (number, group, frame count — frame counts verified exactly
against all five known tracks); the PLF empty form; the STK (a pure
copy); the ID3 tag (frame order TIT2/TPE1/TALB, encoding 0x02
UTF-16BE, string + one NUL terminator, tag strings identical to the
NDB strings); every secure-header constant and offset.

**Modeled** (shape known, value not derivable — each is marked
`[modeled]` in the source):

- TOC header **@0x0C total-seconds field** (86,936 / 84,305 on the
  samples). It scales like total duration taken from source-file
  metadata; the frame-derived estimate lands within ~0.15% but is not
  exact, so the true provenance is SonicStage's library data. The
  author writes the frame-derived estimate.
- TOC header **disc-id material** @0x10 (8 B) + @0x20 (16 B):
  per-disc random-looking bytes (readout #8 located the per-disc
  individuality here). The author generates random bytes; the ladder
  build seeds its RNG so the demo is reproducible.
- TOC header byte @0x08 (= 1 in both samples; role unknown) and the
  track record's **second index** @+0x02 (equal to the track number
  in all 925 sample records; written as such).
- TOC track record **format magic** `01 00 28 2e` @+0x08 and the
  secure header's **block-params** @0x20 (`010f500000040000`) and
  **Connum-tail** (`16725f9be7`): constant across all ground truth —
  but all ground truth is 64 kbps from one install, so any bitrate or
  install dependence is *unobservable in the samples*. Written as
  constants; **the real-cipher phase must revisit these if the code
  shows them varying.**
- Secure-header per-track crypto values (**MgD** @0x50, the @0x30
  slot, Connum @0x29): variability classes are known (per-track,
  identical for identical content) but the values are outputs of the
  real cipher machinery. With the placeholder they are generated
  randomly, classes preserved. The real drop-in recomputes them.
- **ISO volume identifier**: no full-disc image exists in the
  evidence set, so SonicStage's volume label is unknown; the author
  takes it as a parameter (the ladder uses `ATRAC_LADDER_DEMO`).

## The cipher interface contract

One function, in `cipher.py`:

```python
encrypt_payload(payload: bytes, header_fields: dict) -> bytes
```

`header_fields` carries what readout #7 proved the real cipher
consumes: `block_seed` (8 B), `init_vector` (8 B), `mgd` (8 B),
`connum` (2 B), `ekb_version`. The implementation **must be
length-preserving** (proven on all pairs); the .ATP assembler asserts
it on every track. Today's binding is
`encrypt_payload_PLACEHOLDER_IDENTITY_NOT_THE_REAL_CIPHER` — loudly
named, returns the payload unchanged. When the atpcd.ocm work names
the cipher, it drops into this one function (plus the MgD/Connum
computation in `secure_header.py`); nothing else in the pipeline
changes.

## The ladder demo disc

`build_ladder.py`: "It's Alright" (the library .OMA Lola sent —
MY LITTLE PONY | Johnny Orlando, *My Little Pony: A New Generation*)
decoded to 44.1 kHz/16-bit WAV, encoded with the patched atracdenc at
all nine rungs, authored as a nine-track disc in one group
("Bitrate Ladder"), titles carrying the rung (`It's Alright [64k]`),
artist/album from the source tags. Every track: 4,172 frames.

| Rung | Frame B | Frames | Payload B | .ATP B |
|------|---------|--------|-----------|--------|
| 48k  | 280  | 4,172 | 1,168,160 | 1,169,280 |
| 64k  | 376  | 4,172 | 1,568,672 | 1,569,792 |
| 96k  | 560  | 4,172 | 2,336,320 | 2,337,440 |
| 128k | 744  | 4,172 | 3,103,968 | 3,105,088 |
| 160k | 928  | 4,172 | 3,871,616 | 3,872,736 |
| 192k | 1112 | 4,172 | 4,639,264 | 4,640,384 |
| 256k | 1480 | 4,172 | 6,174,560 | 6,175,680 |
| 320k | 1848 | 4,172 | 7,709,856 | 7,710,976 |
| 352k | 2048 | 4,172 | 8,544,256 | 8,545,376 |

Total .ATP bytes: 39,126,752. **ISO: 39,206,912 bytes = 19,144
sectors of the 80-min blank's 360,000 (5.3%) — headroom 340,856
sectors.** (One honest wart: the pre-build capacity *estimate* was
19,141 sectors, 3 under the exact 19,144 — path-table rounding in the
estimator. The binding gate is the post-build exact check, which is
exact; the estimator is a fast pre-filter and is now known to sit
within 3 sectors on a disc of this shape.)

Outputs:

- `~/workspace/atrac-cd-author/out/ladder-demo-PLACEHOLDER-CIPHER.iso`
- `~/workspace/atrac-cd-author/out/ladder-demo-tree/` — the same disc
  as a loose file tree (8 root paperwork files + HIFI/TRK00001–
  TRK00009.ATP).

**The filename carries the warning because it is one: this ISO
proves structure only. Its payloads are UNENCRYPTED (placeholder
identity cipher) — a real D-NE1 will not play it. It is NOT Disc B.**

## What remains

Exactly one thing: **the real cipher drop-in.** When the SAL/atpcd
work names the algorithm and its key derivation from BlockSeed +
InitVector under the EKB, it lands in `cipher.py` (+ MgD/Connum in
`secure_header.py`), gets verified against the banked Ignite test
vectors (one plaintext × four ciphertexts — instant verdict), and
Disc A can then be authored by this same pipeline in one run. Two
watch-items for that phase, recorded above: the constant-looking
format fields that might vary with bitrate in ways the 64 kbps-only
ground truth cannot show, and the TOC @0x0C total-seconds provenance.
