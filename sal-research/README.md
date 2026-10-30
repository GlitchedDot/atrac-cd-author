# SAL / .ocm cipher research

Working papers and tooling for the one blocker between the disc
author (the Python package in this repo's root) and a playable disc:
the encryption SonicStage applies to ATRAC3+ audio at burn time.

Everything here is original analysis code and prose. It *reads* Sony
files from the analyst's own machine by path; it contains none.
Deliberately excluded from this repo: memory dumps (they contain
Sony code/data), Ghidra decompilation output of Sony binaries, the
staged Wine prefix, and run logs (summarized in the readouts).

## The short version

- The disc layout is fully solved and the author reproduces real
  SonicStage discs byte-for-byte. Only the payload cipher is missing.
- The cipher lives inside Sony's OpenMG "Secure Application Layer"
  (SAL) modules (`.ocm` files), which are transformed at load time by
  salwrap.dll's self-protecting engine. Static analysis of every
  purely static kind is exhausted (readouts #9–#17).
- Wine cannot run it in the analyst's sandbox (readout #18), so the
  current route is a Unicorn harness that emulates salwrap.dll +
  OMGUtils.dll with a hand-written Win32 HLE and walks the engine's
  exception-handler choreography toward the moment it forms the
  init.ocm image in memory (readouts #19–#20).

## Layout

- `readouts/` — the numbered stage-0 readout series, in order.
  #20 is the frontier: it ends with the current model of the
  bootstrap's fault/splice cycles and the next experiment.
- `unicorn/sal_emu.py` — the harness. Needs Python 3 + unicorn
  (2.1.4 used) + pefile + capstone, and a folder containing
  salwrap.dll, OMGUtils.dll, and the OpenMG module tree (paths are
  set near the top of the file). Success looks like: the manager
  constructor returns a real context and a CreateFile/ReadFile of
  init.ocm appears in the HLE trace.
- `host/` — the earlier native route: `salhost.c` (a Windows host
  that loads salwrap.dll and calls the manager getter directly),
  `sal_mine.py` (scans a memory dump for the formed module image:
  module name near a 'bc' marker).
- `tools/` — the static-analysis tools behind readouts #11–#17
  (SAL stream tests, frame skeleton recovery, block-pool census,
  phase-7 probes).
- `wine/` — the ptrace wrappers from the Wine attempt (readout
  #18); on an unrestricted machine they are the recipe to retry
  first, against a prefix staged like `host/` describes.

## Current state (2026-10-29)

The harness work after readout #20 is recorded in
`unicorn/SESSION-2026-10-28.md` (sessions through #25, runs to
165), with the per-run harness evolution kept as the numbered
`unicorn/sal_emuNN.py` files (sal_emu.py above remains the
original). Where the frontier stands:

- The SAL script engine (salexec) and the typed-stream driver
  protocol are decoded; the atpcd "Encrypt" operation has been
  entered, and the bulk transform sits downstream of a
  maclist-unwrapped key — but no ciphertext has been produced yet.
- The install's 20-byte global seed was recovered from
  maclist1.dat by the harness and validated by Sony's own
  checker — via a "gates-open" path that a faithful registry
  model then proved unreachable on a real install: gate #2 is
  two negative registry probes that fail on genuine hardware,
  so from a cold start the seed is never surfaced by salwrap.
- The seed's writer is therefore some component outside
  salwrap's init. Censuses of omginit.exe and of the SonicStage
  application layer found no writer; the remaining candidate
  architectures are logged at the end of the session note.
