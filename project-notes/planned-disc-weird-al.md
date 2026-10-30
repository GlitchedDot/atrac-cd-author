# Planned disc — Weird Al: all 14 studio albums

Decided by Lola 2026-10-22: **studio albums only** — no *Peter and the Wolf*
(1988, with Wendy Carlos), no *Medium Rarities* (2017). One GROUP per album,
release order, track order preserved inside each group (groups are mandatory;
every track belongs to exactly one group).

Runtimes and track counts below are the exact CD runtimes pulled from
MusicBrainz (checked 2026-10-23) — the standard releases, so they match her
rips unless her copies are unusual pressings. The author still computes
exact figures from her files at build time; these pin the plan down before
she rips.

| # | Album | Year | Tracks | Runtime |
|---|-------|------|--------|---------|
| 1 | "Weird Al" Yankovic | 1983 | 12 | 33.01 min |
| 2 | "Weird Al" Yankovic in 3-D | 1984 | 11 | 44.37 min |
| 3 | Dare to Be Stupid | 1985 | 11 | 37.01 min |
| 4 | Polka Party! | 1986 | 10 | 34.09 min |
| 5 | Even Worse | 1988 | 11 | 37.63 min |
| 6 | UHF — Original Motion Picture Soundtrack and Other Stuff | 1989 | 13 | 42.99 min |
| 7 | Off the Deep End | 1992 | 11 | 51.56 min (incl. hidden-track silence) |
| 8 | Alapalooza | 1993 | 12 | 44.88 min |
| 9 | Bad Hair Day | 1996 | 12 | 42.25 min |
| 10 | Running with Scissors | 1999 | 12 | 49.90 min |
| 11 | Poodle Hat | 2003 | 12 | 54.65 min |
| 12 | Straight Outta Lynwood | 2006 | 12 | 48.15 min |
| 13 | Alpocalypse | 2011 | 12 | 46.03 min |
| 14 | Mandatory Fun | 2014 | 12 | 45.43 min |
| | **Total** | | **163** | **611.95 min (10 h 11 m 57 s)** |

## Size math (80-minute blank, 737,280,000 B ceiling)

Audio bytes = runtime x bitrate; per-track overhead is exactly 1,120 B
(163 tracks = ~0.2 MB, negligible); ISO paperwork + the open-session-2
reservation cost ~24 MB of the ceiling.

| Bitrate | Audio size | Verdict |
|---------|-----------|---------|
| 64 kbps (her standard) | ~294 MB | Fits, ~41% of the blank |
| 96 kbps | ~441 MB | Fits easily |
| 128 kbps | ~587 MB | Fits comfortably, ~126 MB spare |
| 160 kbps | ~734 MB | **Does NOT fit** — ~21 MB over the usable ceiling (see below) |

**Bitrate CHOSEN by Lola 2026-10-22: 160 kbps for the whole disc.**
Correction (2026-10-23, verified against MusicBrainz CD runtimes): the
earlier "fits by ~3.5 MB" verdict rested on runtime estimates that ran
~20 minutes short of reality. The real total is 611.95 min = 36,717 s, so at
160 kbps (20,000 B/s) the set needs 734,340,000 B against the usable ceiling
of 713,299,968 B — over by ~21.0 MB, about 17.5 minutes of music. The 160k
plan needs one of the saves below; the choice is Lola's.

Safety, in order:
1. **The exact check is free and authoritative**: the author's capacity
   accountant computes byte-exact totals from her real files before anything
   is burned, and refuses rather than emit an over-capacity ISO. Worst case
   is a refusal message, never a wasted blank.
2. **Silence trim**: dropping the ~10 minutes of trailing silence from
   the Off the Deep End rip (the hidden "Bite Me" gap) recovers ~12 MB
   at 160k if her rip carries it.
3. **Mixed-rate fallback**: rates are per-track, so dropping just the two
   longest albums — Poodle Hat (54.65 min) and Off the Deep End
   (51.56 min) — to 128k recovers ~25.5 MB while everything else stays
   at 160k, landing ~4.5 MB inside the ceiling. Pairing the silence trim
   with Poodle Hat alone at 128k saves ~25.1 MB for the same result.
   Either way the byte-exact call comes from her real files at build
   time.

Also noted: 160 kbps is above the D-NE1's documented rates (manual lists
48/64 only) — unproven, not disproven. This disc doubles as a ceiling test;
if the player balks, the same build re-runs at 128k.
