# Stage-0 readout #18 — phase 7 dynamic stage: the Wine verdict, and the pivot

Date: 2026-10-22 (evening). Workstream: SAL/.ocm cipher, dynamic stage.
All experiments ran on Candy's sandbox VM against copies of Lola's Sony Shared
tree staged into a disposable Wine prefix (`~/workspace/atrac-salwrap-work/wp4`).
Lola's own files and machines were never touched.

## What we were trying to do

Run Sony's own `salwrap.dll` (the SAL loader) under Wine, call its manager
bootstrap (FUN_6511D680), let it fetch and form `init.ocm` in memory, and dump
the formed image — the one place the .ocm stored form must become plaintext.

## What the sandbox allows, and what it doesn't (measured, all decisive)

- `/proc/sys/vm/overcommit_memory = 0`, ratio 50, `/proc` read-only; `swapon`
  not permitted. Big anonymous reservations are rationed by the heuristic.
- **32-bit host syscalls are blocked wholesale**: a 32-bit process on this host
  gets EPERM on basic syscalls and is killed. A pure 32-bit Wine build is
  therefore unusable here — only the wow64 (64-bit host) build can run at all.
- `modify_ldt` works (the LDT theory for the wow64 fault is dead).

## The Wine wow64 saga, in order

1. **The reservation wall.** Wine 11's wow64 preloader reserves ~32 GiB RW in
   one `mmap`; the overcommit heuristic refuses it (ENOMEM) and the preloader
   segfaults. A 24 GiB PROT_NONE MAP_NORESERVE reservation succeeds first —
   NORESERVE skips accounting — which pointed at the fix shape.
2. **Ptrace wrappers.** Two wrappers were built (`~/workspace/tools/winewrap*.c`)
   that intercept huge mmaps and add MAP_NORESERVE. Seccomp-filter variant
   (v2/v3) patches *only* mmap events, everything else at full speed
   (`wine --version` in 51 ms). With the patch, wineboot created a prefix for
   the first time. Registry values (Repository, ContentRootDir — mirroring
   Lola's real Wow6432Node OpenMG key) were written and verified.
3. **Fault loop #1 (the NORESERVE curse).** Every 32-bit PE process — salhost,
   and as a control Wine's own 32-bit `whoami.exe` — fault-loops at startup:
   `c0000005` at a wild ASLR address, millions of times, before its first real
   instruction. Mechanism (from +seh traces): wow64 dispatches 32-bit syscalls
   through a deliberate fault that `handle_syscall_fault` should emulate; it
   returns `c0000005` to user mode instead, and the instruction retries
   forever. 64-bit processes in the same sessions all worked normally.
4. **The cap fix.** `winewrap3` gained a CAP mode: a huge RW reservation is
   capped to 6 GiB *with its flags unchanged* (real backing) instead of
   getting NORESERVE. Under CAP, the control `whoami.exe` produced **zero**
   faults — fault loop #1 is caused by the NORESERVE flag on the reservation
   the syscall-fault handler lives behind.
5. **Fault loop #2 (the CAP curse).** On a clean slate, salhost under CAP
   burned 2:47 CPU and ~22.6 M voluntary context switches (~95k patched
   syscalls/sec) for six minutes **without reaching its first printf** — a hot
   loop in the 32-bit init path, no exceptions, no module loads logged. The
   whoami control under CAP also never completed (it sat sleeping, peaceful
   but unfinished).

## Verdict

**Wine wow64 cannot run a 32-bit process to completion in this sandbox** —
two different startup curses depending on how its giant reservation is fed,
both in Wine's machinery, neither in Sony's code (the controls prove it: the
failing programs include Wine's own test binary; Sony's DLL was never even
loaded). The Wine route for the dynamic stage is **closed**. Tools, wrappers
and the staged prefix are kept on disk; if this work ever moves to a machine
without the sandbox's syscall/overcommit restrictions, the CAP-mode wrapper
plus the staged prefix is the recipe to retry first.

## The pivot: Unicorn emulation (fallback, now primary)

Emulate the loader instead of hosting it: Unicorn (2.1.4, already installed)
runs the 32-bit code of `salwrap.dll` + `OMGUtils.dll` in-process on the
64-bit host — no 32-bit host execution, no Wine. Their Win32 imports get
satisfied by loading Wine's own builtin 32-bit PEs (msvcrt/msvcp71/kernel32
from the Kron4ek tree) as images, with a thin host shim for the kernel32
surface (heap, files backed by the staged Sony tree, registry answers we
already know). Then call FUN_6511D680 and dump emulated memory when the
manager forms init.ocm. Every step is observable; nothing can loop invisibly.

## Session bookkeeping

- Phase-7 static readouts #11–#17 stand: static analysis is exhausted and
  closed; the cipher lives behind the .ocm stored form, and the formed image
  is still the target — only the road to it changed.
- Meter at close: 36% of the free weekly limit (Lola's guardrail: ATRAC work
  stops at 50%, everything pauses at 90%; resets Oct 28 16:03 PDT). The
  Unicorn harness is the next ATRAC work block, to start under that budget.
