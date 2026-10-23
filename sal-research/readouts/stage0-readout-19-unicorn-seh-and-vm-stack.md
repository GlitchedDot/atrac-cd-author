# Readout #19 — Unicorn harness: SEH dispatch works; blocker is now the VM-stack trap protocol

Date: 2026-10-22 (evening). Harness: `~/workspace/atrac-salwrap-work/unicorn/sal_emu.py`, runs 17–27.
Meter at pause: 38% of free weekly limit (ATRAC work stops at 50% per Lola's rule).

## What got built since readout #18

- A real SEH dispatcher in the harness: builds EXCEPTION_RECORD + CONTEXT, walks the
  fs:[0] chain, calls each handler as a guest call at the current stack, honors
  ContinueExecution (resume under the edited context) / ContinueSearch.
- Two correctness fixes that each unblocked a phase:
  1. **TF cleared in live EFLAGS when a handler is entered** (the OS does this; the
     trap flag survives only inside the saved context). Without it the handler
     single-stepped itself to death on its second instruction.
  2. **The true x86 CONTEXT layout** (SegDs +0x98, Edi +0x9C, Ebp +0xB4, Eip +0xB8,
     EFlags +0xC0, Esp +0xC4). My first map had the GP block shifted by 4. With the
     true layout, Sony's handler at 0x65126130 decodes perfectly: it is a **manual
     unwind** — it pops {saved Ebp, return addr} plus callee-saved registers from the
     frame streams and fabricates a return. It also writes Dr7 = 0x400.
  3. TF also cleared on splice-resume (one trap per trampoline arming; the hop
     trampolines re-arm TF themselves with pushf/or 0x100/popf).
- Growable stack: the engine probes/commits downward from the TEB StackLimit;
  the harness now commits pages on touch (growth fault census below).

## How far the bootstrap now gets (runs 24–27, deterministic)

- All 40 static ctors, manager init, the debug-register mailbox dance, table
  VirtualProtects — then a long phase of **~502 iterations** of a patch-check
  function at 0x65127680: `if (*(BYTE*)p == 0xCC) VirtualProtect(p, 4,
  PAGE_EXECUTE_READWRITE, &old)` (IAT slot 0x651390CC = VirtualProtect), executed
  while ESP descends what appears to be the VM's private stack in 64 KiB strides,
  ending at **ESP = 0x410000**. Growth-fault census (run 26): pcs 0x65127696
  ×2012, 0x6512769B ×503, 0x65127697 ×502, 0x6516D770 ×502 (3,519 total).
- **244 HLE calls** total; **FUN_6511D680 has NOT returned** and **no init.ocm
  file fetch has been observed yet**. No claim otherwise.

## The current blocker (run 27, precisely characterized)

After the patch phase, a debug-register single-step trap fires at 0x65127697
(ESP = 0x410000, VM stack). The ctxpush "handler" (0x65125420) fields it and
returns ContinueExecution; execution resumes at 0x651276A4 and traps again
immediately. At that point **fs:[0] no longer heads an SEH chain** — it points at
a VM context record on the native stack (dumped from 0xF3FD4C0):

    +0x00 0x00000040   +0x04 0x0F3FD4C8   +0x08 0xFFFFFFFF   +0x10 0x00010010
    +0x24 0x6516D77A (arena code)         +0x2C 0x651276AA (patch fn continuation)

So the OS-style SEH walk is the wrong dispatch model for traps that occur on the
VM's own stack. The VM consumes those traps through its own context record /
frame stream (ctx+0xC4 of the manager ctx, per readout #13), not through fs:[0].

## Next steps (desk work first, then harness)

1. Find the native caller loop of the patch function 0x65127680 and what the
   ~502 iterations correspond to (one per module? per patch site?).
   ADDENDUM (same evening, desk check): Ghidra has no FUN_65127680 — the patch
   block is interior code of **FUN_65127140** (0x27140, size 0x57A, spans to
   0x276BA); the instructions just above it are the SetThreadContext(-2, &ctx)
   mailbox sequence with the resting sentinel 0x11110400, i.e. FUN_65127140 is
   a sibling of the zlib wrapper in the context-mailbox family. No static call
   sites to the 0x27680 entry exist, so the ~502 iterations are driven from
   VM-translated code (the 0x6516D770 twin pushes) — the patch/VirtualProtect
   step is a per-hop VM operation, not a native loop.
2. Determine how a VM-stack DR trap is meant to be consumed — likely resume at
   the continuation stored in the VM context record, or field it via ctxpush
   against the manager ctx's frame stream rather than the fs:[0] chain.
3. Only then: D680 returns a real manager ctx → init.ocm fetch observed →
   dump memory → mine for the formed image ('bc' marker) → cipher work.

Fallback still on file: on an unrestricted machine, retry the CAP-mode
winewrap3 + staged wp4 Wine prefix first (readout #18).
