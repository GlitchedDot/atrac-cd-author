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
