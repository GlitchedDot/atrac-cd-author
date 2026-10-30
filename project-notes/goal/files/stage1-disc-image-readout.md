# Stage 1 readout — the first full official-disc image (slice read)

Evidence: `~/workspace/atrac-cd-stage0/disc-image/atrac-slice.iso` —
706,480,128 B (344,961 sectors), MD5 4d69eb97959ab6c18fc04cdc2421bb2b.
Lola imaged disc 1 (the 493-track NCS compilation) on her MacBook Air
with dd from the slice device /dev/rdisk5s0 (the whole-device rdisk5
read returned zeros — every read EINVAL, zero-padded by conv=sync;
the slice probe at sector 16 returned a real PVD). dd reported I/O
errors only at the final 3 sectors (344,959–344,961, the track edge);
content checks below pass throughout the volume.

## The volume (proven by content scan, not counts)

- Exactly ONE Primary Volume Descriptor in the track, at sector 16,
  + terminator at 17. NO supplementary (Joliet) descriptor, NO Rock
  Ridge (directory-record system-use areas are empty). Plain
  ISO 9660, 8.3 names with ;1, exactly the shape the author writes.
- **Volume label = 32 spaces (blank). System ID = 32 spaces.
  Publisher / preparer / application ID / volume set = all blank.**
  The author report's "volume label unknown" is CLOSED: blank.
- Volume size 344,809 sectors (track extent 344,961; 152 sectors of
  trailing slack). Creation stamp in the PVD: 2026-09-20 21:13:55
  (Lola's burn of disc 1).
- Root: exactly the 9 known paperwork files + HIFI/ —
  0001000E.STK (172 B), TRACK/ALBUM/ARTIST.NDB (63,360 B each =
  256 + 493×128), GROUP.NDB 384, PLLIST.NDB 256, TOC00000.STI
  10,192, TOC00001.STI 2,176 — and 493 .ATP files. Nothing else.
- Spot checks: TRK000DC.ATP (Dreamer) 1,143,784 B and TRK000E1.ATP
  (Electric) 1,257,336 B present (the banked known-pairs);
  TRK00001.ATP starts with "ID3" and its secure header at +1024
  begins 01 00 28 2e — the known format magic. The image is real.

## Descriptor diff: real (Primo) vs our ladder ISO (pycdlib)

- Label/sysid: real BLANK vs ours "ATRAC_LADDER_DEMO" / "ATRAC CD
  AUTHOR" → author fix: blank both.
- Sector packing: real = PVD 16, terminator 17, L path table 18,
  M path table 19, root directory 20 (tight). Ours = root at 23,
  tables at 19/21 (gaps). Path table SIZE identical (22 B).
- PVD tail (offset 882..2048): real = all zeros; ours carries 512
  nonzero bytes → author fix: zero the tail.
- System area (sectors 0–15): identical (all zeros). Terminator:
  identical. Block size 2048, file-structure version 1: identical.
None of these diffs is individually proven to be the ladder disc's
rejection cause; together they are the complete visible descriptor
gap, and all are small, mechanical author fixes.

## SESSION02 — what the image does and does not settle

- The imaged track holds ONE complete, self-contained, one-shot
  volume. Its tree references nothing outside itself.
- H2 (append history): this volume shows no sign of being appended
  into — one descriptor pass, one creation stamp, self-contained.
  But a track-relative slice image cannot show whether a physical
  first session precedes this track on the disc, so H2 is weakened,
  not formally killed, and H1 (inherent two-session) is not
  confirmed either: there is no second ISO volume in this track.
- The player's SESSION02 therefore does not correspond to any
  second ISO volume inside the ATRAC track. The remaining decisive
  evidence is the disc's TOC (sessions / tracks / start LBAs),
  which ImgBurn's Read screen prints verbatim — one screenshot
  from a Windows machine settles the physical layout.

## SESSION VERDICT (2026-10-22 14:58 — ImgBurn screenshots, disc 1)

SOLVED. ImgBurn Disc Information: **Sessions: 2; Status: Incomplete;
State of Last Session: Empty; Next Writable Address: 356,361.**
TOC Information lists **Session 1 only: Track 01 (Mode 1, LBA 0,
length/LTS 344,959 sectors), LeadOut at LBA 344,961.**

The physical layout of a SonicStage ATRAC CD:
- **Session 1 = the complete ATRAC volume** (the slice image is its
  full content; LTS 344,959 + 2 lead-out sectors = the slice's
  344,961 — and the Mac dd's only I/O errors, at sectors
  344,959–344,961, were the lead-out itself, so **the slice image
  lost nothing**).
- **Session 2 = OPEN and EMPTY.** SonicStage/Primo leaves every
  ATRAC CD unfinalized with a dangling empty second session —
  the append point for later burns (the Simple Burner append
  feature writes into it). NWA 356,361 − lead-out 344,961 =
  **exactly 11,400 sectors of session-2 lead-in** — matching the
  per-session overhead figure from the two-session brief.
- The D-NE1's SESSION02 is its firmware naming the disc's last
  (open, empty) session while it plays session 1's ATRAC tree.
- H1 and H2 were each half right: two sessions ARE inherent to
  SonicStage's output (H1's shape), and the mechanism IS the
  append design (H2's explanation) — but this disc was never
  appended to; session 2 is simply born empty.
- Blank: Ritek CD-R, MID/ATIP 97m15s17f, ATIP last lead-out
  79:59:70 (80-min class).

**Author/burn consequence (banked):** the finished artifact stays
a session-1 ISO, but the BURN step must replicate the shape —
write session 1, do not finalize, leave an open empty session 2 —
and the capacity gate must reserve the 11,400-sector session-2
lead-in. An ISO burned the ordinary finalized way differs from a
real ATRAC CD in exactly this respect; it is now the leading
structural suspect (alongside the payload variable) for the
ladder disc's rejection. Disc A remains the discriminating test.

## ImgBurn BIN cross-verification (2026-10-22 15:44)

Lola also ripped disc 1 in ImgBurn: `imgburn/atrac-disc1.bin`,
811,343,568 B = exactly 344,959 raw 2352-byte sectors; file MD5
4d8daf11bf54105df18a90b5c7a6da65. Sector structure checks pass
(sync pattern, Mode 1, MSF headers matching LBA at 0 / 16 /
344,958). **The BIN's 2048-byte data payload, concatenated across
all 344,959 sectors, is MD5-identical to the slice image's data
(a8f5b3f3fc9fd72a12957e9bf2f37524 both ways)** — two independent
rips (Mac dd slice, Windows ImgBurn raw) agree byte-for-byte on
the entire data track. (The per-sector loop in the first check
script misreported mismatches from an unseeked file pointer; the
seek-corrected hash comparison supersedes it.) Disc 1's evidence
is now doubly anchored. The .cue was not sent; for a single-track
disc it is trivially reconstructible and its content is already
known from the TOC screenshots.
