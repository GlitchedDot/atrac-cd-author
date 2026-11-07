# ATRAC CD Author

A byte-faithful authoring library for Sony ATRAC3plus CDs — the
disc format SonicStage writes for ATRAC CD Walkmans such as the
D-NE1. Given ATRAC3plus audio payloads, it produces the complete
disc structure: `.ATP` track files (ID3v2.4 tag + secure header +
payload), the `TRACK/ALBUM/ARTIST/GROUP/PLLIST.NDB` databases,
`TOC00000.STI` / `TOC00001.STI`, the `0001000E.STK` EKB record, and
an ISO 9660 image laid out the way the original burner lays it out.

This is the pipeline core of a larger project: a one-step
drop-audio-get-a-disc tool (web app, native Mac app, native Windows app) for making
ATRAC CDs without SonicStage.

## Status

- **Disc format: fully mapped and validated.** Every paperwork
  file regenerates byte-identically from parsed records of two
  real SonicStage-burned discs (493 and 432 tracks); see
  `validate.py`. The physical layout is confirmed against a full
  disc image: one ISO 9660 volume (blank volume label, tight
  descriptor packing), written as session 1 of an unfinalized
  disc with an open, empty session 2 left for appends.
- **Capacity: exact, not estimated.** Every byte is budgeted
  (audio + a measured 1,120 bytes per track + paperwork + ISO
  structures); the author refuses to emit an over-capacity image.
- **Encryption: SOLVED (2026-11-03).** The payload cipher
  (DES-CBC under the install's content key), the per-track
  BlockSeed seal (two-key triple-DES over the disc ID, the
  track's bind index, and the content key), and the TOC
  integrity value (an unkeyed fold over the track sizes and
  the disc ID) were all lifted from Sony's OpenMG modules and
  validated byte-for-byte against genuine discs — see
  `project-notes/breakthrough-2026-11-03.md` and the session
  reports under `sal-research/`. The working implementation
  currently lives in the proof-of-concept build scripts
  (`proof-of-concept/`); folding it into
  `src/atrac_author/cipher.py` is the next step.
- **Proof of concept: playing on real hardware.** App-authored
  discs were burned and played with audio on a D-NE1: a
  single-track disc carrying atracdenc-encoded audio with no
  Sony software anywhere in the chain, and a five-track,
  two-group disc exercising the full recipe at scale. Both
  ISOs are attached to the release `poc-disc12-2026-11-03`.
- **Native apps: complete and hardware-proven.** `native-pure/`
  is the native Mac app (Swift core byte-identical to the
  reference fixture; AVFoundation decode, bundled atracdenc,
  ISO, burn) — its full encode-to-playing-disc chain was proven
  on a D-NE1 on 2026-11-05. `native-win/` is the native Windows
  app (C# core passing the same byte-parity gate; WinUI 3 face;
  IMAPI2 burn) — encode, import, burn, and D-NE1 playback all
  proven on 2026-11-06. Both are ports of this repository's
  authoring recipe, with their designs and build notes in-tree.
- **What remains:** folding the encryption recipe into
  `src/atrac_author/cipher.py` (see above), packaging polish
  for the native apps, and the public release of the
  user-facing tool (DiscWright), whose web version will be
  supply-your-own-STK like this repository.
- **The STK record is not distributed.** `0001000E.STK` is Sony
  EKB data. Supply your own copy from a SonicStage disc you
  burned; `stk_data.py` documents how it is loaded.

## Layout

- `src/atrac_author/` — the library: `ndb.py`, `sti.py`, `stk.py`
  (+ `stk_data.py`, the STK loader), `id3tag.py`,
  `secure_header.py`, `atp.py`, `cipher.py`, `iso.py`,
  `capacity.py`, `author.py` (orchestration: track list in,
  finished ISO out).
- `proof-of-concept/` — the build scripts and notes for the
  hardware-proven test discs (the encryption recipe lives here
  until it is folded into the library).
- `validate.py` — regenerates both reference discs' paperwork and
  compares byte-for-byte (needs the reference files locally).
- `build_ladder.py` — builds a nine-bitrate ladder test disc
  (48–352 kbps) using the open-source atracdenc encoder.
- `tests/` — self-contained unit tests; no reference discs or Sony
  data needed. Run: `python3 -m unittest discover -s tests -v`

## Notes

Developed with AI assistance; every format claim in the code is
backed by measurements against real discs, and the validation
suite compares output byte-for-byte against them. No Sony code or
data is included in this repository.
