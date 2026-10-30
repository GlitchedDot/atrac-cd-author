# Stage 1 brief — the SESSION02 problem (two-session ATRAC CDs)

Prepared 2026-10-22 (background research). This is a research brief, not a
readout: facts, hypotheses and tooling notes are labelled as such. Nothing
here overrides a hardware verdict from Lola's D-NE1.

## What is established

- Lola burned the ladder-demo ISO and tested it in her D-NE1 on 2026-10-22:
  the player showed READING for about 2–3 seconds, then turned itself off.
  Verdict: REJECTED (goal update `goal_update_dbdb250df281`).
- On her official SonicStage-burned discs, the player's remote display
  reads **SESSION02** while reading — confirmed by Lola's photograph, not
  just her description (goal update `goal_update_ad4491401084`).
- Our disc author writes with pycdlib and produces a **single-session**
  ISO (stage1-disc-author-report.md). The same report flags the ISO
  volume identifier as unknown because no full-disc image has ever been
  in evidence — every readout so far worked from file subsets, which is
  exactly why the session layer stayed invisible.

## Two competing explanations for SESSION02 — the image decides

**H1 — structural two-session layout.** SonicStage always writes a
session 01 (contents unknown) and puts the ATRAC tree in session 02;
the firmware goes to session 02 for ATRAC content, didn't find that
shape on our single-session disc, and shut down. This is the leading
hypothesis in the live thread.

**H2 — append history.** Sony's own software supports adding tracks to
an already-recorded ATRAC CD in a later burn: the SonicStage Simple
Burner manual describes editing a disc image against a disc that
already has audio recorded on it, with the already-recorded tracks
masked and the remaining space shown. Each append is a new session.
Under H2, SESSION02 on Lola's discs could simply mean those discs were
burned in (at least) two passes — session 01 would hold the first
burn's full ATRAC tree — and a single-session disc would not be
inherently wrong.

**Discriminators, all readable from one full-disc image (.cdr / raw
sector stream) of an official disc:**

1. Session 01's file tree: a full ATRAC tree with its own track titles
   leans H2; a tiny, empty-ish or non-ATRAC session leans H1.
2. Whether session 02's directory tree references file extents located
   in session 01 (normal multisession ISO 9660 behaviour — operating
   systems mount the *last* session's volume descriptor, at block 16 of
   the first track of the latest session, and its tree can point back
   into earlier sessions), or is fully self-contained.
3. Per-session Primary Volume Descriptors: volume identifier (settles
   the author's open unknown either way), volume/sequence dates, and
   each session's start LBA and size, plus the lead-in/lead-out gaps
   between sessions.

Until the image is analysed, do **not** rebuild the ladder disc as
two-session just to test H1: the placeholder (unencrypted) payloads
remain a confound, and Disc A stays the discriminating test for the
payload variable. The image removes the session variable first, for
free.

## Authoring route, if a two-session output is what the image supports

- pycdlib writes a single session; a two-session disc cannot come out
  of the current `iso.py` path unchanged. This is a new writer/burner
  path, not a flag.
- The standard open-source route is the xorriso family (xorrecord
  man page, "Write multiple ISO 9660 sessions"): burn session 01 with
  `-multi`; read the medium's `-msinfo` numbers; build the session-02
  image with `xorrisofs -M <device-or-image> -C <msinfo>` so its tree
  is written at the correct offset and can reference session-01 files;
  burn session 02 (again `-multi` if a third session must stay
  possible, without it to close). On macOS this tooling is a separate
  install (e.g. via Homebrew) — presence on Lola's machines is
  **unverified**; check before promising it.
- Design consequence for the app: a two-session disc is a *burn-time
  process* (two passes over a real blank, or a specially built
  multi-session image file), not a single .iso the user burns with any
  tool. If H1 wins, the Mac app's burn step has to drive that process
  itself, or produce a .cue/.cdr-style multi-session image — a real
  fork in the Disc A plan, worth settling before Disc A is authored.
- Capacity consequence: each additional session costs roughly 11,400
  sectors (~22 MB) of lead-in/lead-out overhead on CD-R (cdrecord
  multisession logs). The author's capacity gate currently reasons
  about a single image size; a two-session build must budget the extra
  session overhead or near-full discs will silently overflow.

## Sources

- Goal updates `goal_update_dbdb250df281` (hardware rejection) and
  `goal_update_ad4491401084` (SESSION02 observation) on goal
  `goal_e35963ec4aae`.
- `stage1-disc-author-report.md` in this folder (pycdlib writer; volume
  identifier unknown; capacity gate).
- SonicStage Simple Burner manual (manualsdump.com): editing a disc
  image for an already-recorded ATRAC CD, recorded tracks masked,
  remaining space shown.
- xorrecord(1) man page (manpages.org): the multiple-session write
  procedure quoted above; ISO 9660 multisession reading rule (latest
  session's volume descriptor governs, trees may reference earlier
  sessions).
