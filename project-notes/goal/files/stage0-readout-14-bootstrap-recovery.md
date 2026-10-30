# Stage-0 readout #14 — SAL attack phase 4: bootstrap recovery — the priming contract, the f0 selector, and the class-01 skeleton (2026-10-22)

Static analysis only; nothing was executed. Materials: `salwrap.dll`
(MD5 `8bb3f0258a178e099700d00acd444a98`) and the module corpus in
`~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG/`. New working
papers: `~/workspace/atrac-salwrap-work/sal_skeleton.py` (the
framing-layer parser built this phase) and
`out/phase4-notes.txt` (primary-evidence notes). Prior papers used:
`out/phase3-decomp.c` (FUN_6511C8A0, FUN_6511B650, FUN_65116360,
thunks — read in full this phase), `out/engine-decomp.c`
(FUN_651254C0 incl. its tail, FUN_65125AB0, FUN_6512C840,
FUN_6512CBF0, FUN_6512BDB0), `out/monkey-main.asm` and
`out/ctxpush.asm` (read in full at assembly level).

## Verdict up front

**The priming contract is pinned, and it contains no parsing step.**
The manager builds two engine arenas, fetches init.ocm *verbatim*,
and hands the engine a `{data, len, out}` descriptor — no native
code reads a single field of the stored bytes (not the 5-byte
wrapper, not the 10-byte container header, not the class byte, not
the 13-byte head) before the first continuation frame runs. The
engine primes *itself*: arena setup makes the first engine call to
a hard-coded worker (monkey main, FUN_651261A0), whose priming run
creates the persistent engine context. Every request — init.ocm
included — then runs a **fixed, hard-coded native sequence**
(gatekeeper → relay → monkey main → FUN_6512BDB0 → FUN_65126970 →
continuation machine). **The frame selector f0 is a worker code
address**, in the same `^ 0x7FFFFFFF`-mangled pointer economy as
every other selector in the engine; the first frames are authored
inside the arena by the two phase workers, not derived from the
module bytes by any native reader. A whole-`.text` call-graph scan
proves **no native code anywhere walks a module body with the
SalAsn reader** — the first consumer of the stored stream is the
bytecode layer, full stop.

And the stored stream itself yielded structure this phase: a
class-01 body is **not** an opaque blob. Its first **8,214 bytes
are a plaintext SalAsn-framed skeleton** — head values, a section
marker, an 8,192-byte shared chunk carried as one OCTET STRING,
and a small element holding the body's **first per-module field**.
The family's famous 8,211-byte shared prefix is explained
*exactly* by this framing (12 + 1 + 4 + 8192 + 2 = 8211): prefix
sharing is a framing artifact, not a transform artifact. The
skeleton is implemented and corpus-validated in `sal_skeleton.py`
(25/25 family modules; init.ocm and device.sal share its 17-byte
head). **atpcd.ocm remains undecrypted** — class-02 bodies carry
no skeleton at all — and §7 lists exactly what remains.

## 1. The priming contract (mission 1)

Manager init FUN_6511C8A0, in execution order (decompiled in
`out/phase3-decomp.c`, read in full):

1. Zero the manager object's fields; read registry values
   (`InitocmMemorySize2`, default 0x2000; logging flags).
2. **Create arena 1**: malloc 0x358040; FUN_6512C7E0 →
   FUN_65125490 → FUN_651254C0 (ctx slot &DAT_6516D488, arena base
   +0x40, size 0x358000, scratch = BSS 0x65158050, 0x13000 B,
   arena index 0). This primes the *engine* (§1.1) — no module is
   involved yet.
3. Register the log/error callbacks (FUN_65125350/FUN_65125370).
4. Build the string `"init.ocm"`; **fetch it through host-table
   +0x3C** (FUN_6511C550 → file cache FUN_6511B160:
   `omgResolveRepositoryFile` + `OmgString::readFromFile`,
   verbatim, cached by name) → a `{data, length}` descriptor.
5. **Hand off**: FUN_65134A10(data, len, out[12 B]) → gatekeeper
   FUN_6512C840 with the arena-1 ctx. This is the first time
   init.ocm's bytes enter the engine — as an opaque descriptor.
6. Only *after* that call returns: create arena 2 (FUN_6512C810,
   0x400000 B arena, scratch at 0x65145010), import device.sal if
   the flag is set (FUN_6511B3B0), and load region.ocm through
   host-side SalAsn request construction + host calls.

**What the manager builds from init.ocm's stored bytes before the
first frame runs: nothing.** Buffers allocated beforehand: arena 1
(0x358000 B), its BSS scratch (0x13000 B), the state block (§1.1),
the file cache's verbatim copy of the file, and the gatekeeper's
stack arg struct `{0, ctx, data, len, out}`. No header field of
the file is read natively at any point in the traced path — the
descriptor covers the whole stored file as read, 5-byte wrapper
and container header included; if those are interpreted at all,
it happens bytecode-side. (One flagged inference: the exact stack
slots FUN_6511C8A0 passes to FUN_65134A10 are partially obscured
in the decompilation; the `(data, len, out)` reading follows from
FUN_6511C550's established signature and salexec's identical
triple in FUN_6511B650 → FUN_65116360 → FUN_651349F0.)

### 1.1 How the engine primes itself (arena setup, FUN_651254C0)

Arena setup is the bootstrap's native half:

- It lays out the **state block** at the top of the arena
  (`base + size − 0x1BC`): +0x00 = `rand() & 0xFFC` seed, +0x04 /
  +0x08 / +0x0C = the three region bases (gate-stub region,
  worker region, relocation base), +0x1B4 = gate return-stack
  cursor (initialised to state+0x24), +0x1B8 = saved affinity
  mask. VirtualProtects arena and scratch RWX; pins the thread
  to one CPU (the affinity dance).
- It **installs the hop gate**: FUN_65125AB0's 0x800-byte block is
  memmoved to a randomised region-C address; the address is kept
  mangled (`^ 0x7FFFFFFF`) in Dr3.
- It then **makes the first engine call itself**:
  `hop_gate(FUN_651261A0, proto_ctx)` with a Dr1 arg struct
  `{0, &proto_ctx, &arena_base, …}` — proto_ctx is a stack struct
  whose +0x18 field points at the state block; the remaining
  fields carry the arena base, the state offset, and the
  registry size parameter. **Monkey main is the initial worker of
  every fresh arena** (arena 2's setup is identical, index 1).
- Monkey main's priming run **creates the persistent engine
  ctx** (the object with the +0x9C frame registers and the
  +0xB4/+0xC4 frame queue): after the call, FUN_651254C0
  retrieves it via FUN_651203B0, flips its state field
  (ctx+8: 1 → 2, under the engine critical section), stores it
  in the global slot (DAT_6516D488 / DAT_6516D484), and saves
  the thread's debug registers into state+0x14..+0x20.

Two arenas = two independent engine instances. init.ocm executes
on **arena 1**; `salexec` requests run on **arena 2**
(FUN_6511B650 → FUN_65116360 → FUN_651349F0 → DAT_6516D484).
Arena 2 is primed by its own monkey-main run *without* init.ocm —
the module environment the bootstrap establishes must therefore
live in shared state (the 128-slot module registry at
0x6516B280, zeroed by the engine-side FUN_6512A630, is the
rendezvous the earlier phases already identified).

## 2. The f0 selector (mission 2)

### 2.1 The frame format (ctxpush FUN_65125420, raw asm)

`out/ctxpush.asm`, instruction by instruction: with Q =
`*(ctx+0xC4)` (frame-source pointer) and S = `*(ctx+0xB4)`
(saved-block cursor), a pop reads the triple **f0 = Q[0] →
ctx+0x9C, f1 = Q[1] → ctx+0xA0, f2 = Q[2] → ctx+0xA4**; then
takes `link = S[0]`, sets `*(ctx+0xC4) = S + 8` (the *next*
frame's triple lives at offset +8 in the block at S), sets
`*(ctx+0xB4) = link`, saves the outgoing worker's code pointer
`*(ctx+0xB8) = *(ctx+0xC) ^ 0x7FFFFFFF`, and writes 0x400 to
ctx+0x18. So continuation blocks are a linked chain:

```
block:  +0x00  link (enclosing block)
        +0x08  f0
        +0x0C  f1
        +0x10  f2
```

and the gate return stack (state block, §1.1) is a second,
simpler frame system: FUN_65125AB0 pushes `{target, 0x900}`
verbatim at the state+0x1B4 cursor.

### 2.2 Verdict: f0 is a worker address

- **Every selector ever observed is a literal code address.**
  Arena setup → FUN_651261A0; gatekeeper → FUN_6512CBF0
  (`(*(code *)(Dr3 ^ 0x7fffffff))(FUN_6512cbf0, ctx)`); monkey
  main → FUN_6512BDB0 and FUN_65126970 (both are `push imm32`
  in the raw asm, at 0x6512645A and 0x651266F0). The hop gate
  receives the target as a raw pointer and pushes it verbatim —
  no indexing arithmetic exists in FUN_65125AB0 or FUN_65125420.
- **f0 lives in the code-pointer economy.** ctxpush saves the
  *current* worker's code pointer from ctx+0xC — where it is
  stored mangled, `^ 0x7FFFFFFF`, exactly like Dr3's gate
  address — into ctx+0xB8 in the same motion that installs the
  incoming triple at ctx+0x9C..+0xA4. Frame selectors and code
  pointers are one currency in this engine.
- **Not a table index**: the DLL's only index/table mechanisms
  are the Win32 API trampoline tables (0x6516D490 / 0x6516E490,
  readout #12/#13) — neither ctxpush nor the hop gate touches
  them. **Not a SalAsn value**: frames are raw 12-byte native
  triples; no reader participates in frame handling (§3).

### 2.3 How the first frames for init.ocm get their selectors

They are not computed from the module at all — the request
sequence is **fixed native choreography**, identical for every
engine call:

1. **Gatekeeper** FUN_6512C840 builds `{0, ctx, a, b, c}` and
   hops to the **relay** FUN_6512CBF0, which self-relocates and
   rebuilds the identical 5-field struct onward.
2. **Monkey main** FUN_651261A0 reads **only fields [0], [4],
   [8]** of its Dr1 struct (asm 0x651261F2–0x6512620C) —
   `{f0=0, f1=ctx, f2=a}`; fields [0xC] (b = len) and [0x10]
   (c = out) are *not read by monkey main* (their path past
   this point is untraced — an open thread, §7). It
   self-relocates, then:
   - **hop 1 → FUN_6512BDB0** with `{f0, ctx}` (that worker
     reads exactly those two Dr1 fields). Its return value,
     delivered in Dr1 (unmangled if Dr0 = 1), **becomes the
     new f0 — a pointer** (asm 0x6512647F–0x6512649E).
   - **hop 2 → FUN_65126970** with `{f0, ctx, a}` — for
     init.ocm, `a` is the descriptor's data pointer, i.e. the
     stored file bytes enter the phase machinery here, as an
     argument value, still unparsed by any native reader.
   - Monkey main then installs **ctxpush (LAB_65125420) as its
     SEH handler**, publishes the final Dr1 value, sets the
     trap flag, self-relocates once more, and falls off its
     end — the continuation machine takes over from the frame
     blocks the phase workers built inside the arena.
3. The gatekeeper finally returns the last Dr1 value to C++
   (for salexec, the result descriptor pointer).

So the **initial workers for a freshly loaded module are
FUN_6512BDB0 and FUN_65126970, in that order, always** — and the
first continuation frames are authored by them (and the workers
below them) inside the arena. Honest boundary: the frame-*writing*
instructions inside those two workers were **not isolated** this
phase — their decompiled forms are dominated by the relocation
boilerplate, and no writes to ctx+0xB4/+0xC4-shaped fields were
located in the engine decompilation. Authorship is localised to
them by elimination (they are the only code that runs before the
continuation machine takes over); the pop side, the frame
format, and the selector economy are proven.

## 3. The first consumer of the body bytes (mission 3, native side)

A rel32 call-graph scan of the entire `.text` (this phase;
image base 0x65100000) settles who uses the recovered SalAsn
reader class (FUN_65117400 readLength, FUN_651174C0 octet read,
FUN_651175F0 dataType, FUN_65117700 readSeqBegin, FUN_65117800
readSeqEnd, FUN_651178E0 readString, FUN_65117990 readInteger):

- Reader entries are called **only** from inside the class
  itself and from three host-side stream helpers — FUN_6511A620
  (host-table +0x80), FUN_651176C0, FUN_6511D140 — all in the
  C++ region, all operating on host-built request/result
  streams (e.g. FUN_6511A620 extracts an OCTET STRING result
  from a reader over a returned stream).
- **No engine-region function calls any reader entry point.**
  The separate SalAsn helper block at 0x65134A30–0x65134CE0
  chains internally and is called from FUN_65116480 (the
  registered log callback) and FUN_65135000 — the host message
  path, not the engine.

Combined with §1–§2: the stored stream past the head is **never
walked by native code** — not by the manager, the seam, monkey
main, or any classified worker. Its first consumer is the
bytecode-side program the continuation machine runs (the loader
inside init.ocm), which receives the stream as the request
descriptor's bytes. There is no small unclassified native path
left for the transform to hide in on the consumption side.

## 4. The stored stream's own structure: the class-01 skeleton

Since the consumer is bytecode, the byte-level question becomes:
what does the stored stream *look like* to its consumer? This
phase's byte work (corpus: all 62 files in the OpenMG directory)
found that the class-01 stored form is **plaintext-framed** for
its first 8,214 bytes:

| Body offset | Bytes | Reading |
|---|---|---|
| +0 | `01 01` | INT1 1 — format/version value |
| +2 | `04 08 6A35A21D8C3C2C0C` | STR[8] — fixed family identifier |
| +12 | `7E` | section marker (universal) |
| +13 | `04 82 20 00` | OCTET STRING header, length 8192 |
| +17 | 8,192 bytes | **shared chunk** — byte-identical in all 25 family modules (SHA-256 `b580b1f4…88b7`); contents opaque (entropy ≈ 7.98) |
| +8209 | `74 02` | small element header |
| +8211 | 2 bytes | **first per-module field**: a u16 (BE) in [0x49E8, 0x4A02] |
| +8213 | `73` | section marker |

Verified for **25/25** family modules (every byte position in
the table asserted programmatically). init.ocm and device.sal
share the skeleton only through the head: at +13 they carry an
INT2 (init: 0x498E; device.sal: 0xA908) and the 0x73 marker at
+16 — a 17-byte skeleton.

**The oracle test (the brief's requirement) — the 8,211-byte
sharing is explained exactly:**

```
12 (head values) + 1 (0x7E) + 4 (STR header) + 8192 (chunk)
+ 2 (74 02 header) = 8211
```

The shared prefix ends at +8211 because +8211 is the first byte
of the first per-module field. The two modules whose u16 is
0x4A02 (restore.ocm, osss.ocm) diverge from icv.ocm at +8211
itself; the 23 whose u16 high byte is also 0x49 share 8,212
bytes. Prefix sharing is a **framing artifact** — the family is
one TLV skeleton with a shared chunk and per-module fields —
not evidence about any cipher's start state. (This refines
readout #12 §5: "one deterministic stream from body offset 0"
described the *contents*; the framing was never transformed.)

Three disciplined negatives accompany the skeleton:

- **Contents stay opaque.** The 8,192-byte chunk is
  high-entropy and does **not** occur anywhere inside init.ocm
  (substring search, negative): init is a different program
  sharing the head skeleton, not a container of the family
  chunk in stored form.
- **The flat framing does not extend past +8214.** Flat-TLV
  walks from +8209 survive 2–4 elements and break down within
  ~90 bytes — and they break at the *same* byte (+8297, tag
  0x12) in icv and maclist, whose bytes are identical until
  +12662. The breakdown is structural, not divergence noise:
  past the skeleton, either the framing becomes
  nested/constructed in a form the flat grammar doesn't
  capture, or headers cease to be plaintext. Not claimed
  either way.
- **Class-02 has no skeleton.** atpcd.ocm's body starts
  `4D 47 CA 99…` — no head, no framing at any tested offset.
  Class-02's pairwise sharing (atpcd/lgd 8,481 B; init2/region
  8,481 B; bot-dnk/hdd-dnk the whole file) is *not* explained
  by this framing and remains a separate stored-form question.

## 5. What the 13-byte head means (mission 4)

Reading the head + descriptor as a program, in the priming
contract's terms:

- **`INT1 1` — a version value.** The first value of every
  class-01-headed stream (25 family modules, init.ocm,
  device.sal; 27 files, zero exceptions). In the reader
  grammar it is the OPERAND_1 integer form with value 1: the
  stream-format version the consuming program checks first.
- **`STR[8] 6A35A21D8C3C2C0C` — a family/format identifier.**
  Not a registry key and not a native-checked magic: the byte
  string occurs **nowhere in salwrap.dll** (byte-searched this
  phase) and no native code compares it. Not per-module (it is
  identical across files of wildly different sizes and
  contents), not a file CRC (same reason). It is the
  identifier by which the *bytecode-side* loader recognises
  its module family — the class-01 SAL-module magic, carried
  as a SalAsn value rather than as raw header bytes.
- **`0x7E` — the section marker between stream header and
  stream body.** Universal at +12 in the same 27 files. In the
  reader's dataType() classification, first bytes ≥ 5 are
  "type 2" (generic/other): 0x7E and the recurring **0x73**
  (at +8213 in the family, at +16 in init.ocm and device.sal —
  always exactly where a section's first variable element
  ends) are type-2 marker values whose semantics belong to
  the consuming program, not to the grammar. Recorded as
  structural constants; their opcodes, if any, are
  bytecode-side.

Tests against the other classes, as required: **device.sal**
carries the identical 17-byte skeleton inside its own,
different container (readout #10: algorithm @2, version @4,
self-referential CRC over the stored bytes) — the head marks
the *SAL stream family*, independent of container. **Class-02**
modules carry none of it — different head entirely (in fact no
readable head), so the head is a class-01(+device.sal) stream
property, and class-02's priming, while it uses the same
native contract (§1), presents a differently-formed stream to
the bytecode layer.

In the priming contract itself the head's role is: **none.**
It is not consumed, checked, or stripped natively (§1, §3).
It is the module program's own header — the first thing the
bytecode-side loader sees when the continuation machine runs
the stream, and the anchor any future reading of init.ocm's
bootstrap must start from: *version 1; family
6A35A21D8C3C2C0C; section open; …*

## 6. Implemented and validated (mission 5)

**`~/workspace/atrac-salwrap-work/sal_skeleton.py`** implements
the identified first stage of the stored-form recovery — the
framing layer — and validates it over the corpus:

- All **25/25** family modules parse to a skeleton span of
  **8,214 bytes** (sal_dis.py's strict grammar dies at byte
  12): head values, 0x7E, the STR[8192] chunk (one distinct
  SHA-256 across all 25 — byte-identical), the 0x74 element
  with its per-module u16, the 0x73 marker.
- init.ocm and device.sal parse to their 17-byte skeleton.
- All 35 class-02 files and the stubs correctly report *no
  skeleton*.
- The oracle property holds by construction and is asserted
  in the run: the parse keeps the shared prefix shared
  through +8210 and stops at the first per-module byte,
  +8211, inside the skeleton — the transform's shared-prefix
  signature is reproduced as pure framing.

No *content* transform is claimed: the 8,192-byte chunk's
contents and everything from +8214 onward remain opaque, and
no byte of atpcd.ocm is recovered by this stage. Partial is
reported as partial: what fell this phase is the **frame** of
the class-01 stored form, not its contents.

## 7. What remains between here and reading atpcd.ocm — exactly

1. **The skeleton's continuation (class-01, past +8214).**
   The framing grammar for the rest of the stream — nested or
   constructed forms, or a second dialect. The oracle corpus
   supports the same byte-level method: icv/maclist share
   12,662 bytes, so their common structure extends 4,448 bytes
   past the skeleton's end.
2. **The contents transform.** The chunk contents and all
   later element contents are opaque. Identifying the
   transform still requires the *execution semantics* of
   init.ocm's loader program (readout #13's bootstrap-recovery
   problem) — but that problem now has a concrete input
   structure to start from (§4–§5) and a proven delivery
   contract (§1–§2): the loader is a bytecode program fed
   `{data, len}` descriptors by a fixed native sequencer.
3. **First-frame authorship.** The frame-writing code inside
   FUN_6512BDB0 / FUN_65126970 was localised but not isolated;
   nor was the path of the request's (len, out) fields past
   monkey main (it reads only fields [0], [4], [8] of its
   Dr1 struct). Both are native-side loose ends, closable by
   a focused asm read of the two workers' non-boilerplate
   segments.
4. **Class-02's stored form (atpcd.ocm).** No skeleton, no
   head: either a transform from byte 0 (making items 1–2
   prerequisites) or a framing not yet recognised. The
   class-02 pairwise spans (8,481 B) are the same style of
   oracle the class-01 skeleton fell to.
5. **The key's exact home** (unchanged from readouts
   #12–#13): bytecode-side — init.ocm's data, or unwrapped by
   the DNK ECC layer into a module-carried content key.

**atpcd.ocm decrypted: NO.** What this phase recovered is the
delivery contract end-to-end (manager → seam → fixed sequencer
→ continuation machine), the selector semantics (worker
addresses), the proof that no native code consumes the stream,
and the class-01 stored form's framing skeleton with its
oracle-exact explanation of the shared prefixes. The transform
of the *contents* — and with it atpcd.ocm — is now a
bytecode-execution-semantics problem with a known input
structure, no longer a search for a hidden native path.
