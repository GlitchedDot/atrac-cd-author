# Readout #20 — Unicorn harness: the "hang" was a stack-commit walk (runs 32–39, 2026-10-22 evening)

## The verdict

The long silences (runs 31–33) were **not a wedge**. The SAL engine's
bootstrap performs a **stack-commit walk**: it probes downward from the
TEB stack limit, and every page is committed *through the exception
handler* (ctxpush, LAB_65125420), one page per fault/splice cycle.
Fed silently by the harness's old growth hook, the walk had no bottom
and crawled at ~9K instructions/s (per-page Python `mem_map`). With the
OS semantics emulated faithfully, the same phase runs in ~1.5 s and the
cycle turns over repeatedly.

## Evidence chain

- **Run 34** (500K-instruction chunk telemetry): samples land inside
  the patch-check function 0x65127680–0x6512769C (and its VM twin
  0x6516D770) while ESP descends ~2 MiB per 500K instructions, ~55 s
  per chunk — the cost was the growth hook's per-page `mem_map`, not
  guest work.
- **Run 35** (span pre-mapped): the march flew (80 chunks in ~3 s) and
  ESP **wrapped past zero** (fault writing 0xFFFFFFE8 at ESP
  0xFFFFFFEC) — proof the walk's termination is the *reserve bottom
  fault*, not a count.
- **Host PE (decisive)**: `Omgjbox.exe` SizeOfStackReserve = 0x100000,
  SizeOfStackCommit = 0x1000 — stock values. The walk's legitimate span
  below the stack limit is ≤ 1 MiB. Run 36/37 fielded the bottom fault
  at exactly limit − 0x100000 (write to 0xDEFFFFC, ESP = 0xDF00000).
- **ctxpush disassembled** (0x65125420): pops two chain links via the
  head node's link field (head pointer itself never changes), then
  splices: ctx.Eip := ctx.Dr2 ^ 0x7FFFFFFF; ctx.Ebp := [stream at old
  ctx.Ebp]; ctx.Esp := that stream + 8; ctx.Edi/Esi/Ebx := three words
  from the stream at old ctx.Esp; ctx.Dr7 := 0x400; returns 0.
  The march's descending pushes *are* the continuation streams being
  laid at the stack bottom.

## Harness changes that fell out of this

1. **Silent guard commits only inside the reserve** (touch ≥
   STACK_BASE − 0xFF000 commits and retries invisibly); a touch below
   the reserve floor is the dispatchable bottom fault.
2. **Bottom-page commit on delivery** (Windows stack-overflow
   semantics): when a 0xC0000005 fault within one page below the
   committed floor is dispatched, that page is committed first — the
   engine's continuation store targets exactly it (run 37:
   0x6516D775 → floor − 4).
3. **Handler cache per chain node**: after the first ctxpush cycle the
   head node's +4 field is overwritten by the VM context record
   (legitimate engine state — the record even carries the harness halt
   address as its exit continuation). The node's handler is a fixed
   installed property; the dispatcher now remembers it per node and
   reuses it when the field no longer holds an image address.
   With this, rounds 8 **and** 9 both fielded and spliced (run 39).
4. **Watchdog**: a (pc, address, access) fault repeating > 2000 times
   is named as a stuck fault instead of spinning silently (installed
   after run 33's 15-minute silent chunk).

## Current frontier (runs 40–42, refined same evening)

The zero-region landing was a misread: the splice targets are in
salwrap's **.data section** (RVA 0x41000, mostly BSS) — that is where
the engine generates its code. With an image-.data dump added
(`image-data.bin`), the round-8 bottom splice's target decodes as
real generated code (run 42, target 0x6515CD79; targets vary per run,
bump-allocated): a caller that pops pairs from a queue
(ctx+0x1B4 cursor against ctx+0x24 base) and calls through with
(popped1, popped2, 0x40, &local).

The fault is its `push eax` at +0x30: **ESP itself is garbage**
(run 42: ESP = 0x7455F8F8). The generated code's first instruction is
`add esp, [ebp-4]`; the splice set Esp = 0xF3FD7E8 (streamB+8) and
Ebp = 0xF3FD7D0 (streamB[0]), so **[ebp-4] held 0x709C2110** instead
of a small frame adjustment. Everything upstream of that add checks
out (the queue-pop logic read sane values and branched correctly).

Also settled: SetThreadContext is only ever called with flags
0x10010 in this flow — the Dr-clobber theory is dead (gating added
anyway, harmless). StreamA at the bottom splice carries small ints
([4, 64, ptr]) as continuation arguments, as designed.

## Addendum — runs 43–48 (same evening): the splice is RIGHT; cycle 2's frame is uninitialized

- The twin diff is settled: LAB_65126130 and ctxpush differ ONLY in
  the Eip source (streamB[1] vs Dr2 ^ 0x7FFFFFFF). Neither writes
  [ebp-4]. The twin theory is dead.
- An apparent contradiction (splice Ebp "wrong") was my own
  decimal→hex misreading of the logged stream values. Verified by
  logging the handler-edited context directly: **ctxpush's edits land
  exactly as disassembled** (Ebp := streamB[0], Esp := streamB + 8,
  Eip := Dr2 ^ 0x7FFFFFFF, Edi/Esi/Ebx := streamA). The dispatcher,
  snapshot, and apply are all correct.
- The continuation is a **chain**: the generated caller runs once per
  probe cycle, each time with the next native frame (Ebp walks
  0xF3FDB30 → 0xF3FDE70 → …). Cycle 1's frame is properly initialized
  ([ebp-0x18] = heap ctx pointer, [ebp-4] = 40) and its call succeeds
  — the popped work item is the probe itself, which descends one more
  page and faults (cycle 2).
- **Cycle 2's frame is NOT initialized**: [ebp-0x18] = 0 (null ctx),
  [ebp-4] = a code address; streamA at the cycle-2 fault ESP reads
  [0, 0, 0]. The generated caller then computes a wild ESP from the
  uninitialized slot and dies at its first push (ESP ≈ 0x7455xxxx,
  varying per run).
- Open question for the next session: who initializes the per-cycle
  continuation frames in the real flow, and what writes cycle 1's
  frame between the manager's native calls — i.e., compare the frame
  neighborhoods at both cycles and trace writes to the cycle-2 frame
  address range (0xF3FDE70 ± 0x20) during cycle 1's execution.
FUN_6511D680 has still not returned; no init.ocm fetch yet.
Meter at final write-up: 41% (ATRAC stop line 50%; resets Oct 28 16:03 PDT).

## Addendum 2 — run 49 (write trace, same evening)

A MEM_WRITE hook over the native frame band [0xF3FD000, 0xF3FE000)
during the whole D680 call recorded only 1,225 writes — attributed:

- **Cycle 1's frame is initialized by generated code at
  0x65166D12/0x65166D1A** (writes #533/#534, late — just before the
  bottom-fault splice): [ebp-0x18] := heap ctx pointer,
  [ebp-4] := 0x28. The initializer function lives at ~0x65166D00.
- **Cycle 2's frame [ebp-0x18] slot receives ZERO writes in the
  entire run.** Its [ebp-4] slot receives only VM arithmetic spill
  (0x81830092, 0x8317941D — encoded-pointer-looking intermediates)
  and, at write #485, a pointer to the initializer itself
  (0x65166D00) — the setup knows frame 2, but the initializer never
  runs for it.
- The hop phase interleaves ctxpush and splice-handler dispatches
  (four #DB faults before the bottom fault; two serviced by each
  handler family).

Next step: disassemble the initializer at 0x65166D00 and find its
callers — what decides which frame it initializes, and what in the
real flow invokes it per cycle that this emulation misses.
Meter: 41%.

## Addendum 3 — run 49 disassembly: the model recasts (same evening)

- The "initializer" at 0x65166D00 is a **runtime-generated native
  shim** (file bytes there are zero; no static callers): standard
  prologue, frame size 0x314 — matching the 0x340 spacing of the
  continuation-frame chain. It copies a descriptor's fields into its
  locals ([ebp-0x18] := [arg+0x18], [ebp-4] := first descriptor
  dword, etc.). The chain frames are successive invocations of
  shims like it, pre-built as records on the native stack.
- The "generated caller" (per-cycle splice target) is a
  **patch-applier**: it pops (address, value) pairs from the ctx
  queue (base ctx+0x24, cursor ctx+0x1B4) and calls
  **VirtualProtect via IAT slot 0x651390CC** with size 0x40 on each —
  the engine patching its own generated code pages in 64-byte units.
- The ctx pointer is also stored at [frame-0x10] by generated code
  at 0x651615B2 (write #159) — the descriptor layout is consistent;
  what never happens is a *second* shim prologue for cycle 2's frame.
- Refined open question: the splice enters cycle 2's shim frame
  directly, skipping its prologue. In the real flow, either the
  prologue runs (a call the emulation's dispatch short-circuits) or
  the frame's locals are pre-filled by the frame-builder — the
  write trace shows neither happens here. Next: trace who stores
  the 0x65166D00 pointer into frame 2's area (write #485, pc
  0x6516A854) and what that code path represents.

## Addendum 4 — run 49 node log: a wrong-handler suspect for cycle 2

The full dispatch log (run 49) shows the #DB hops walking fresh
nodes each time (healthy), and the bottom fault's head node
0xF3FD4C0 holding a genuine ctxpush registration. By cycle 2 that
node is the dead VM record, and the dispatch falls back to the
handler CACHE — which replays ctxpush. But cycle 2's streamB pair
is [0xF3FDE70, **0x65166DDE**]: its second slot holds a plausible
*return address* into the shim cluster — exactly what the SPLICE
handler (0x65126130, Eip := streamB[1]) consumes, while ctxpush
ignores it and reuses cycle 1's stale Dr2 target. Lead hypothesis
for the next session: **cycle 2 belongs to the splice handler, not
ctxpush** — the cache's assumption is the divergence. Test: when
the head node's field is dead and the fault is the patch
function's AV, dispatch to 0x65126130 and observe. (Also noted:
shims like the one at 0x6516A750 install the splice handler as
their own SEH handler and run the Dr mailbox — the two handler
families serve different shim types.)

## Addendum 5 — runs 50–53: splice-handler hypothesis CONFIRMED; march 3 clears the chain

- The experiment ran (run 50): cycle 2 dispatched to the splice
  handler instead of cached ctxpush → the resume re-entered a shim
  (Eip = streamB[1]) and the engine ran **two further full patch
  marches** (run time 1.4 s → 11 s; rounds still cap at the same
  final fault, but ~3x more guest work executed). The hypothesis
  holds: per-cycle handler selection matters, ctxpush serves the
  first bottom, the splice handler the follow-on cycles.
- Also fixed, independently correct: the harness TEB put the TLS
  array pointer at linear 0, aliasing TLS slots onto the TEB head.
  Moved to AUX+0x6000 (HLE TlsSetValue mirrors there too).
- The march-3 death is now precisely observed (runs 51–53): the
  final dispatch finds **fs:[0] = 0**. A write hook on [0, 0x10)
  caught the culprit: **guest code at 0x6516AA1D writes 0 to
  fs:[0]**, immediately after the splice into the shim continuation
  at 0x6516AA16 (ESP = the spliced 0xF3FDB38); a following write at
  0x6516AA56 stores the ctxpush address at linear +4 (a node being
  built at address 0, with EAX = 0). So a continuation in the
  cascade runs with a zeroed base register and dismantles/builds
  chain state at the wrong place — the cascade is off-rails by
  this point, one level deeper than the handler choice.
- Next: read the shim continuation at 0x6516AA16 from its start
  (it is streamB[1] of the march-2 bottom dispatch) and identify
  which register it expects to hold the node/ctx pointer, then
  check what the splice actually supplied in that register
  (streamA for that cycle read [0,0,0] — the likely gap).
FUN_6511D680 still has not returned; no init.ocm fetch yet.
