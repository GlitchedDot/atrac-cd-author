# ATRAC CD Author

A byte-faithful authoring library for Sony ATRAC3plus CDs — the
disc format SonicStage writes for ATRAC CD Walkmans such as the
D-NE1. Given ATRAC3plus audio payloads, it produces the complete
disc structure: `.ATP` track files (ID3v2.4 tag + secure header +
payload), the `TRACK/ALBUM/ARTIST/GROUP/PLLIST.NDB` databases,
`TOC00000.STI` / `TOC00001.STI`, the `0001000E.STK` EKB record, and
an ISO 9660 image laid out the way the original burner lays it out.

This is the pipeline core of a larger project: a one-step
drop-audio-get-a-disc tool (web app and native Mac app) for making
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
- **Encryption: NOT included.** Payload encryption happens inside
  Sony's OpenMG secure modules and has not been reproduced yet.
  `src/atrac_author/cipher.py` is a loudly named placeholder that
  passes payloads through unencrypted — discs built today are
  structure tests only and will not play.
- **The STK record is not distributed.** `0001000E.STK` is Sony
  EKB data. Supply your own copy from a SonicStage disc you
  burned; `stk_data.py` documents how it is loaded.

## Layout

- `src/atrac_author/` — the library: `ndb.py`, `sti.py`, `stk.py`
  (+ `stk_data.py`, the STK loader), `id3tag.py`,
  `secure_header.py`, `atp.py`, `cipher.py`, `iso.py`,
  `capacity.py`, `author.py` (orchestration: track list in,
  finished ISO out).
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
