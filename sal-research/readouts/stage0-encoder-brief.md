# Stage-0 encoder brief — ATRAC3+ encoding is NOT a greenfield problem

Researched 2026-10-21 evening (proactive pass), after the project was scoped.
Corrects the premise recorded at filing ("no open implementation exists").

## The correction

**atracdenc** (github.com/dcherednik/atracdenc, LGPL-2.1, public, active —
295 commits, 8 releases) describes itself in its repo title as an
"LGPL implementation of ATRAC1, ATRAC3 and ATRAC3Plus compatible encoder."

Its README usage section documents ATRAC3PLUS encoding explicitly:

- Valid combinations: `ATRAC3PLUS: OMA/RIFF/RAW`
- Example: `./atracdenc -e atrac3plus -i ~/01.wav -o /tmp/01.oma`
- Containers selectable via `--container {aea|oma|riff|rm|raw}`
- Build: C++17 + CMake + libsndfile (the documented Linux route; macOS build
  is the same CMake/libsndfile shape, unverified on her Intel Macs)
- Stated limitation: **only 44.1 kHz 16-bit WAV input** — which matches CD rips
  exactly, so it is not a practical constraint for this app.
- FreshPorts (audio/atracdenc 0.2.3) independently describes it as supporting
  "ATRAC1, ATRAC3 and ATRAC3PLUS formats."

Note the README body line "free LGPL implementation of ATRAC1, ATRAC3
encoders" omits ATRAC3Plus — the usage section and repo title include it.
Treat ATRAC3plus support as *claimed by the project*, not yet proven.

## What this does NOT settle

- **Quality/maturity of the ATRAC3plus encoder is unknown.** Community
  coverage (nytpu's MiniDisc guides) calls atracdenc's ATRAC3 support
  "experimental" and focuses on ATRAC1/ATRAC3 for NetMD LP2/LP4; the
  ATRAC3plus path gets little field testing because standard MiniDisc
  doesn't use it.
- **D-NE1 acceptance is the verdict, and only Lola's ears/hardware give it.**
  An encoder that produces a decodable .oma is not the same as one whose
  streams the D-NE1 firmware accepts on an authored ATRAC CD. This needs
  one test encode + one test disc — which folds neatly into stage-0 once
  she sends a SonicStage-burned disc for the layout readout.
- **The disc layout RE is unchanged.** Manual evidence confirms the shape:
  ATRAC CDs are ISO 9660 Level 1/2 + Joliet, files+groups (max 256 groups /
  999 files), ATRAC files played in the order selected in SonicStage, and
  Sony's manuals insist ATRAC CDs be made with "authorized software"
  (SonicStage 2.0+ / Simple Burner) — i.e. there is a specific on-disc
  structure beyond just .oma files sitting in folders. Her burned discs
  remain the ground truth for that.

## Revised stage-0 shape

1. Build atracdenc (Mac, CMake + libsndfile) and encode one known track to
   ATRAC3plus .oma; decode it back with ffmpeg as a sanity check.
2. Read one of Lola's SonicStage-burned ATRAC3+ CDs: full file tree,
   filenames, any non-audio control files, ISO/Joliet specifics.
3. Author a minimal test disc: one atracdenc-encoded track in the
   SonicStage layout; D-NE1 plays it or it doesn't — that single verdict
   sizes the whole encoder question with evidence.
4. Only if the D-NE1 rejects atracdenc streams does "write/borrow an
   encoder" become the long pole again.

## Sources

- https://github.com/dcherednik/atracdenc (repo title, README usage section,
  read 2026-10-22T03:2xZ)
- https://www.freshports.org/audio/atracdenc/ (port description, v0.2.3)
- Sony D-NE-series manual excerpts via search: ATRAC CD structure,
  ISO 9660/Joliet, 256 groups / 999 files, authorized-software note.
