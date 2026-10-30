# Stage-0 readout #5 — batch 2 complete; logs read; evidence set closed (2026-10-21)

## Batch 2: the whole Sony Shared tree

Lola sent the entire `Common Files\Sony Shared` folder (2,917 files,
14.7 MB zip) — every requested file verified present at the exact
listing size: CDRFormatter.dll, CDWalkman.dll, OpcAtp.dll,
AtpFringe.dll, OpcCd.dll, OpcCd2.dll, id3parser.dll,
SonyCDWriterSS/CdrHelperSS/OpdCdrSS, omgatpcd.dll, atpcd.ocm,
ekbman.ocm, kdrm.ocm, kdrmcom.dll, OpcKdr.dll, the full OpenMG\ekb
folder, OMGKEY\omg_id.dat. Local tree:
~/workspace/atrac-cd-stage0/batch2/. **The stage-0 evidence set is
complete.** Next phase is analysis: Ghidra on CDRFormatter.dll
(layout writer), omgatpcd.dll + OpcKdr.dll + the .ekb files
(encryption/EKB), against the on-disc ground truth.

## The two logs — not layout narrations, but useful

- **CDRFormatter.log**: drive-poll errors from her Sept-Oct 2026
  sessions only. Recurring `CdrFormatter::CheckAllDrives - Medium is
  Lost`, and on 2026-09-23 a 3-second-interval exception loop:
  `CDRDriveManager::CheckAllDrives - CdrDataWriter::GetDriveList()
  Failed [0x80004005]`, later `[0x8007000E]`. (Filed as evidence;
  belongs to the paused Toshiba crash thread's world — a background
  drive-poll thread failing hard in a loop. Not chased here.)
- **CdWalkman.log**: the CD checkout path. `PmCdWalkman::
  FullCheckOut` calls `WhetherAtpFileOrNot()` per library file and
  every attempt logged failed `OpdFormatIncompatible` — the files
  were AAC-format OMAs ("...128kbitAAC.OMA") from her library's
  `C:\Users\Glitched7\Music\SSC\Optimized Files\` folder, which the
  ATRAC CD checkout rejects without transcoding. Establishes:
  (1) her library audio lives in that Optimized Files folder;
  (2) checkout validates the source format per file (an ATP-file
  test) before any burn; (3) her successful ATRAC discs were burned
  from ATRAC-format library files (e.g. the 64 kbps ATRAC3+ OMA).

## GUI reference captured

Lola's screenshot of SonicStage 4.3's main window (My Library view,
crash dialog and all) is filed as
`files/gui-reference-sonicstage-main-window.jpg`. Design elements
for the app's SonicStage-like shell: top purple segmented control
(Music Source | My Library | Transfer) with DSEE + volume at left,
transport row under it, left sidebar (View / Sort by / Quick Search
with the A-Z initial grid), center album table (Album | Artist |
Genre | No. of tracks | Length | Date imported), free-space readout
top right, deep purple frame throughout.
