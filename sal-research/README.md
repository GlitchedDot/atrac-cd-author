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

## Current state (2026-11-01)

The harness work after readout #20 is recorded in
`unicorn/SESSION-2026-10-28.md` (sessions through #45, runs to
259), with the per-run harness evolution kept as the numbered
`unicorn/sal_emuNN.py` files (sal_emu.py above remains the
original). Where the frontier stands:

- Op 11 is fully lifted (session 35): a keyed MAC built from
  textbook SHA-1 and FIPS DES, clean-room reimplemented and
  proven against the live oracle. Its reply is validated by
  nothing (session 36); d2, the value it depends on, is a
  constant of the install's ceremony state, so the author may
  choose its own d2 self-consistently. The header side is
  closed.
- The library-path payload cipher is byte-exact (session 37):
  DES-CBC encrypt with key = d2[0:8] and IV = the header
  InitVector, continuous chain — proven on all four Ignite
  tracks. It covers library/.OMA-sourced tracks only.
- The envelope gate is lifted (session 43): the check value
  is SHA-1(inner serialization || "ATRAC CD" || a constant
  16-byte trailer)[0:8], mintable for any inner document.
- BIND_CONTENT is a record bind, not the audio transform
  (session 44): its reply rewrites a binding ledger (bytes
  accumulated, bind count). omgatpcd.dll drives exactly three
  SAL selectors — key-blob, bind, media-info verify — and none
  transforms audio.
- The general (fresh-source) transform is NOT in the held
  corpus (session 45): 169 unique binaries fingerprinted with
  zero native cipher tables anywhere (all OpenMG crypto is
  SAL VM bytecode), and a ~46,000-key construction battery
  against the non-library tracks found nothing. The missing
  ingredient is the SAL program/component the real pipeline
  runs between EA3-encoding a fresh source and the pre-BIND
  .ATP — from a different SonicStage/OpenMG build than the two
  held copies, or a component never copied off the machine
  that burned the reference discs.
