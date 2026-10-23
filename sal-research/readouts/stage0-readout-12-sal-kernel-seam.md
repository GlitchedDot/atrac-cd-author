# Stage-0 readout #12 — SAL container attack, phase 2 step 2: the kernel-seam attack on salwrap.dll (2026-10-22)

Static analysis only; nothing was executed. Materials: `salwrap.dll`
(MD5 `8bb3f0258a178e099700d00acd444a98`) and the `.ocm` modules in
`~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG/` (atpcd.ocm MD5
`e4ae53cc186dbde18dae8e57bd73dcb7`). New working papers this step:
`~/workspace/atrac-salwrap-work/out/engine-decomp.c` (Ghidra
decompilation of all 62 engine-region functions, 910 KB),
`out/kernel-seam-refs.txt` (per-function callees/data-refs),
`out/engine-stripped.c` (trampoline-stripped logic skeletons), and the
stripper `~/workspace/atrac-salwrap-work/scripts/strip_trampoline.py`
(+ the Ghidra script `scripts/SalKernelSeam.java` that produced the
decompilation).

## Verdict up front

**The caller chain is traced end to end, the trampoline is mechanically
stripped, and the engine workers are mapped — and the body transform is
NOT native code.** Exhaustive scans (receipts in §5) show salwrap.dll
contains no bulk cipher loop, no memory-operand XOR anywhere in the
file, and no native code that writes even one field of the formed-image
header. Raw file bytes travel verbatim from disk into the protected
engine. The transform therefore lives at the **SAL bytecode layer**:
either inside `init.ocm`'s bootstrap bytecode (a bytecode module
linker/decryptor run by the native VM), or in the VM interpreter's
per-value decode path in the engine's VM cluster. **atpcd.ocm was NOT
decrypted this step** — the gating item is now the SAL bytecode ISA
itself (readout #9's step 4), because the transform is bytecode-side.
§7 lists exactly what remains unknown.

One framing correction to readout #10 / the step-2 brief (§2): there
are **two** tables, and "+0x3C" means different things in each.

## 1. Method

1. Re-read readouts #10/#11; inventoried phase-1 papers
   (`out/functions.txt` — 1,576 functions, decomp dumps, xref lists).
2. Byte-scanned the whole DLL for dword immediates of the key addresses
   (API vector base 0x651423A0, image-manager slot 0x651423C0,
   FUN_651243B0, FUN_65124830, host-table cell 0x651411DC) to find every
   native touch point.
3. Dumped the host-services table at 0x65139FB8 (in `.data` at
   0x65139FB8; initial value of cell 0x651411DC) and identified its
   entries against the function list.
4. Wrote and ran a Ghidra headless script (`SalKernelSeam.java`) to
   decompile all 62 functions in the engine region
   0x65125490–0x65138000 and record their callees/data references.
5. Read the pivotal workers in full (FUN_65132220 image-manager twin,
   FUN_6512EDF0 relocator twin, FUN_6512CBF0 relay, FUN_6512C840
   engine-call gatekeeper — the last also from raw disassembly).
6. Wrote the trampoline stripper (§4) and ran it over the engine
   decompilation; fingerprinted every worker by error-code constants.
7. Capstone-scanned **all** of `.text` (C++ region, runtime library,
   engine, thunks) for byte/dword cipher idioms (XOR/ROL/ROR/ADD/SUB
   on byte or memory operands).
8. Byte-level module tests: common-substring analysis (≥48 B) across
   six module pairs; entropy of device.sal; init.ocm structure.

## 2. Two tables — a correction to the readout #10 framing

Readout #10's "+0x3C load-by-name API" conflates two distinct tables:

- **Runtime API vector at 0x651423A0** (~96 entries; module images link
  against it). **+0x20 = FUN_651243B0** (image manager). **+0x3C =
  FUN_651200D0**, which is the *log* function (vsnprintf + the
  callbacks registered by FUN_65125350/FUN_65125370) — not a loader.
- **Host-services table at 0x65139FB8** (`.rdata`; the cell
  **0x651411DC** holds its pointer and is what `salwrap1` returns).
  C++ code calls through `*(0x651411DC)+offset`. **Its +0x3C entry
  (@0x65139FF4) = FUN_6511C550**: a 27-byte wrapper that calls the
  **file cache FUN_6511B160** (cache object 0x6516B080) with
  (descriptor-out, name) — i.e. **+0x3C of the host table is
  "fetch file bytes by name"**, the exact seam the brief pointed at,
  one table over. FUN_6511B160 confirmed by decompilation: resolves
  via `omgResolveRepositoryFile`, reads with
  `OmgString::readFromFile` **verbatim**, caches by name, fills a
  {data ptr, length} descriptor. No transform in the fetch path.
  Other host entries identified: +0x00 FUN_6511D760, +0x08
  FUN_6511A4A0, +0x1C FUN_65118120 (device.sal import), +0x2C
  FUN_65116710, +0x30 FUN_651166A0, +0x40 FUN_6511AD50, +0x44
  FUN_6511A540, +0x48 FUN_6511A560, +0x58 FUN_65116F00, +0x5C
  FUN_6511D0E0, +0x64 FUN_6511C760, +0x68 FUN_6511C710, +0x6C
  FUN_6511D090, +0x70 FUN_6511D040, +0x74 FUN_6511C570 (SalAsn integer
  encode), +0x80 FUN_6511A620, +0x8C FUN_65117700, +0x98/+0x9C
  FUN_65116780. The FUN_6511D040/D090/D0E0 entries are SalAsn value
  constructors — the host table is the engine's host-services/SalAsn
  interface, also used by the C++ manager to build arguments.

## 3. The caller chain (raw file bytes → formed image)

1. **Clients** (omgatpcd.dll, kdrmcom.dll, pfcom.dll, …) call the
   `salwrap0/1/2` exports; `salwrap1` returns the host-table pointer
   (cell 0x651411DC).
2. **Manager init** — FUN_6511C8A0: reads registry sizes; creates
   **arena 1** via FUN_6512C7E0 → FUN_651254C0 (context stored in
   global 0x6516D488; 0x358000-byte arena; BSS scratch 0x65158050,
   0x13000 B); registers error/log callbacks via
   FUN_65125350/FUN_65125370 (globals 0x65170A18–0x65170A24); fetches
   **init.ocm** through host +0x3C (the verbatim file cache above);
   creates **arena 2** via FUN_6512C810 (context in 0x6516D484);
   imports device.sal via FUN_6511B3B0 if flag 0x651411D8 is set;
   loads region.ocm through further host-table calls.
3. **Engine hand-off** — the init.ocm descriptor is passed to
   **FUN_65134A10** (30-byte thunk) → **FUN_6512C840(ctx =
   \*(0x6516D488), a, b, c)**. FUN_6512C840 (934 B, unprotected,
   disassembled in full) is the engine-call gatekeeper: it does the
   bit-sliced CPU-affinity dance (popcount over the affinity mask,
   stored at ctx+0x1B8), saves the thread's debug registers from
   ctx+0x18 state, installs a CONTEXT whose Dr1 points at a 5-field
   stack arg struct {0, ctx, arg3, arg4, …} (pointer ~-mangled when
   negative, Dr0 recording which), and calls the relocated hop gate
   with target **FUN_6512CBF0**. A twin thunk **FUN_651349F0** does
   the same for arena 2 (ctx \*(0x6516D484)); no C++ caller of
   FUN_651349F0 appears in the phase-1 dumps (open thread, §7).
4. **Relay** — FUN_6512CBF0 (1,376 B) is a pure relay worker: it
   self-relocates (pattern P3, §4), rebuilds the 5-field arg struct
   {ctx, ?, a, b, c} from its Dr1 input, and hops onward through the
   gate. The chain C++ → gatekeeper → relay → VM is the seam across
   which raw descriptors enter the engine.
5. **Inside the engine**, everything is reached by gate hops with
   Dr1-carried arg structs and FUN_65125420 (ctxpush) continuation
   frames — the engine never references the host-table cell
   0x651411DC (143 references exist, **all** in the C++ region), and
   references the runtime API vector exactly once
   (FUN_6512EDF0, below).
6. **Image registration** — the protected twin of FUN_651243B0's
   miss path is **FUN_65132220** (2,528 B; verified by direct
   comparison): it checks the image's compression flag (+0x47),
   compares the name at +0x3E against `wm`/`_wm` (the DAT_651427D4/
   DAT_651427D8 strings), hops to the **expand twin FUN_65133470**
   (the protected zlib inflate; its only referencer in the DLL is
   FUN_65132220, as a DATA ref at 0x65132360), hops to the heap
   twin, memmoves the image into the arena allocation, hops to the
   relocator, and computes the entry point as
   `*(image+0x4C) + image`. **Whoever calls FUN_65132220 already
   holds a formed image** — header, name, entry/reloc offsets all
   populated. No native caller of it was found (§5: no native code
   writes those fields at all), so its caller is inside the VM
   cluster / bytecode layer.
7. **Relocation** — FUN_6512EDF0 (1,328 B) is the verified protected
   twin of FUN_65121500: identical relocation-type semantics,
   including type 0x80 = `&PTR_LAB_651423A0 + addend` (the DLL's
   only engine-region reference to the API vector base) and type
   0x81–0x88 = PC-relative forms against fixed .rdata/.text anchors;
   it calls `strncmp` through the vector slot 0x651424FC (+0x15C)
   and raises 0x14404030 on unknown types, exactly like its twin.

## 4. The trampoline pattern + stripper

Every protected worker is wrapped in the same self-protection
scaffolding (verified against FUN_651254C0, FUN_65125AB0,
FUN_65125420, FUN_6512C840, FUN_6512EDF0, FUN_65132220,
FUN_6512CBF0):

- **P1 prologue**: SEH frame; `GetThreadContext`; the arg-struct
  pointer is taken from `CONTEXT.Dr1`, bitwise-NOTed when `Dr0==1`
  (pointer mangling); fields are read from the struct by offset.
- **P2 hop-call**: build a small arg struct on the stack;
  GetThreadContext; `Dr1 = &args` (or `~&args` when the address is
  negative, Dr0 recording which); Dr2 = 0; `Dr7 = 0x11110455`;
  SetThreadContext; `Dr7 = 0x11110400`; SetThreadContext;
  `(*(code *)(Dr3 ^ 0x7FFFFFFF))()` — call the relocated hop gate;
  GetThreadContext — results return in Dr1.
- **P3 self-relocation**: `rdtsc` → MSVC LCG
  (`x*0x343FD + 0x269EC3 >> 16 & 0x7FFF`) → new address
  `f(rand) + *(int *)(*(int *)(ctx+0x18) + 0xC)`;
  `VirtualProtect(Dr3, 0x800, PAGE_EXECUTE_READWRITE)` and same for
  the destination; memmove the worker's 0x800-byte block; rewrite
  Dr2/Dr3 (both XOR 0x7FFFFFFF); Dr1 = 0, Dr0 = 0, Dr6 = 0;
  Dr7 choreography as P2. (FUN_65126030, the 0x100-byte stub the hop
  gate copies and calls, is itself just memmove(dest, src, 0x800).)
- **P4 error hop**: P2 with arg struct {0x144040xx error code, 0} —
  a raise, not a call (e.g. 0x14404010 bad slot count, 0x14404030
  bad reloc type — the same codes the unprotected twins raise via
  FUN_65120160).
- **P5 epilogue**: the frame's SEH handler field is set to
  `&LAB_65125420` (FUN_65125420, the ctxpush continuation
  primitive: it copies a frame {target^0x7FFFFFFF, argptr^0x7FFFFFFF,
  …} from the queue at ctx+0xC4 into the continuation context at
  ctx+0x9C/0xA0/0xA4/0xB4/0xB8) and the worker exits through P3/P2.

**Stripper**: `scripts/strip_trampoline.py` implements rules R1–R6
(drop RNG/address lines, VirtualProtect lines, CONTEXT field writes,
the stereotyped 0x800-byte self-copy loops, SEH bookkeeping; rewrite
gate calls as `HOP()` and the LAB_65125420 epilogue as
`RETURN_VIA(ctxpush)`). Run over `out/engine-decomp.c` it produces
`out/engine-stripped.c`: 28,735 → 21,976 lines, 166 HOP sites
marked. The output is a logic skeleton (not compilable); residual
noise is the workers' inlined library copies (memmove/strlen
expansions the decompiler inlined), which the line rules do not
remove.

## 5. Transform findings — the native layer is clean (receipts)

- **No bulk cipher in native code.** Capstone scan of the *entire*
  `.text` (C++ region 0x65110000–0x65125490, runtime library, engine
  0x65125490–0x65138000, thunk region): byte-wise XOR/ROL/ROR/ADD/SUB
  on byte or memory operands occur **only** as register-zeroing
  idioms (`xor reg,reg`, `xor al,al`, …). **Memory-operand XOR count
  in the whole file: 0.** The only byte-XOR cluster anywhere,
  FUN_6511DBD0 (C++ region), is an SEH/C++ string helper, not a
  cipher. There is no native byte or dword transform loop to find.
- **No native code builds a formed image.** Grep over the full
  engine decompilation and all phase-1 C++ dumps for writes to
  image-header offsets (+0x3C/+0x3E/+0x40/+0x44/+0x46/+0x47/+0x4C/
  +0x50/+0x54/+0x58/+0x5C): **zero writes.** (Reads exist — the
  manager/relocate twins consume headers.) The 0x60-byte header is
  therefore populated either inside the module plaintext (Sony
  link-time) or by bytecode — never by salwrap native code.
- **Bytes travel verbatim.** The file cache (FUN_6511B160) reads
  files byte-for-byte; the init.ocm descriptor goes straight into
  the engine (§3.3). device.sal is handled the same way: its CRC-32
  (readout #9's verified scheme) is over the **stored** bytes, and
  FUN_6511B3B0 passes the file to the engine — native code never
  parses a .sal/.ocm body. (Measured this step: device.sal's body
  entropy is 7.989 bits/byte — device.sal is transformed exactly
  like the modules; it is not a plaintext sibling.)
- **The transform is one deterministic stream from body offset 0.**
  Common substrings (≥48 B) between module pairs occur **only as
  common prefixes**, never mid-file: atpcd/lgd 8,481 B;
  icv/Omgtomp3 8,222 B; at3toomg/at3topcm 23,577 B; init2/region
  8,481 B; bot-dnk/hdd-dnk the whole 9,062 B file; the class-01
  family shares an 8,221 B body prefix; init.ocm (a standard
  class-01 module behind a 5-byte wrapper `04 83 08 47 50`) and
  device.sal share only the 13-byte head with the family. This
  **kills readout #9's strong chunk-pool model** (independently
  encrypted reusable chunks would recur at arbitrary offsets):
  shared library *content* recurs across modules, but it is
  streamed through a single transform whose state starts
  identically at offset 0 for every module. Equally consistent
  with readout #11: not zlib/deflate at any boundary, not walkable
  SalAsn as stored.
- **Per-module variation: none observed.** Same plaintext prefix →
  same ciphertext prefix, across classes and across the DNK key
  containers. The 8 bytes at body+5..12 (`6A 35 A2 1D 8C 3C 2C 0C`
  in class-01 plaintext terms) are family-shared framing under a
  fixed-start stream, **not** a per-module IV. No header field
  (class byte, version, build) selects a different native path —
  no native code reads the body before the engine hand-off at all.

## 6. Worker map (engine region, by cluster)

- **Boot/dispatch**: FUN_65125490 (41 B, ctx helper), FUN_651254C0
  (arena setup; error 0x14404022), FUN_65125AB0 (hop gate),
  FUN_65126030 (memmove stub), FUN_651261A0 ("monkey main" —
  the engine entry the gatekeeper/gate calls first).
- **VM core cluster** (the SAL interpreter + value machinery; no
  error-code fingerprints except as noted): FUN_651261A0,
  FUN_65126970, FUN_65127140, FUN_651276C0, FUN_65127DD0,
  FUN_65128420, FUN_65128A20, FUN_65129040, FUN_651294B0,
  FUN_65129AC0 / FUN_65129EF0 (0x14404021), FUN_6512A320,
  FUN_6512A630, FUN_6512AA30, FUN_6512AE30, FUN_6512B340,
  FUN_6512B880, FUN_6512BDB0, FUN_6512C2F0. **The transform, if it
  is a per-value decode, lives in this cluster** (§7).
- **Engine-call seam**: FUN_6512C840 (unprotected gatekeeper,
  §3.3), FUN_6512CBF0 (relay), FUN_6512D150 (anti-debug: checks
  ReadFile/CreateFileA/VirtualQuery entry points for 0xCC),
  FUN_6512D5B0 (builds the 256-entry API trampoline table at
  0x6516D490 targeting FUN_6512D9B6 — how workers call Win32 APIs
  without import references).
- **Relocate family** (errors 0x14402010/0x14402040, most also
  0x14404030): FUN_6512DA00 (2,144 B, contains the API-dispatch
  target FUN_6512D9B6), FUN_6512E260, FUN_6512E5C0, FUN_6512E910,
  FUN_6512EDF0 (verified twin, §3.7), FUN_6512F320, FUN_6512F5F0.
- **Image-manager family** (errors 0x14402049/0x14404010, some also
  0x14402030): FUN_65130A70 (2,128 B), FUN_651312C0, FUN_65131A70,
  FUN_65131DE0, FUN_65132220 (verified load-miss twin, §3.6). Each
  carries inlined copies of the expand-check + registry logic.
- **Expand twin**: FUN_65133470 (protected zlib inflate; referenced
  only by FUN_65132220).
- **Tail**: FUN_65132C00, FUN_65133090, FUN_65133890 (0x14404010/
  0x14404022), FUN_65133EF0, FUN_651341B0, FUN_651345A0; thunks
  FUN_651349F0/FUN_65134A10 (§3.3); SalAsn value helpers
  FUN_65134A30–FUN_65134CE0 (unprotected).

## 7. What remains unknown — exactly

1. **The transform itself.** Candidates, narrowed to two, both
   bytecode-layer: (a) a module linker/decryptor written in SAL
   bytecode inside init.ocm (582 KB bootstrap — it has room to be
   the whole stdlib + linker), executed by the native VM for every
   subsequent module; init.ocm's own body is then either consumed
   by the VM in stored form (making the stored encoding the VM's
   native bytecode encoding for the bootstrap) or decoded by the
   interpreter's fetch path. (b) A per-value/per-instruction
   inverse transform inside the VM cluster's decode path
   (FUN_651261A0–FUN_6512C2F0) — interleaved with SalAsn value
   construction, which is why no bulk loop exists. Distinguishing
   (a) from (b) requires reading the VM cluster's value-decode
   functions line by line (their stripped skeletons total ~5,000
   lines) or building the bytecode disassembler first.
2. **The SAL bytecode ISA** — opcode map and value encoding. This
   is now the gating item for both the transform and atpcd.ocm's
   content. The ISA spec is the VM cluster's dispatch; the value
   encoding spec is partly in hand (runtime-lib SalAsn codecs
   FUN_65124CC0 / FUN_65125020 and the host-table constructors).
3. **The key, if any.** Not in salwrap native code (no key
   material, no schedule, no body access). If a key exists it
   lives bytecode-side: in init.ocm's data, or unwrapped by the
   DNK ECC layer (EMDKEY private keys;
   `ERR_SML_DNK_PRIV_ECC_DECRYPT`) into a module-carried content
   key. Do not look for it in the registry or in OMGKEY (readouts
   #10/#11 already cleared both).
4. **Minor open threads**: no C++ caller of the arena-2 thunk
   FUN_651349F0 appears in the phase-1 dumps; FUN_65132220's caller
   (the formed-image supplier) is inside the VM/bytecode layer and
   unidentified by name; the 0x6516D490 trampoline table's full
   API coverage was not enumerated.

## 8. Validation

- Oracle direction check: every finding is consistent with the
  step-1 oracle (same input prefix → same output prefix; formed
  images match readout #10's format when the *manager twin*
  consumes them — FUN_65132220's field usage (+0x3E name, +0x46
  type, +0x47 compression flag, +0x4C entry, +0x58/+0x5C reloc)
  matches the unprotected FUN_651243B0/FUN_65121500 field-for-field.
- **atpcd.ocm decrypted: NO.** No Python implementation was
  written — the transform was not identified to implementable
  precision, and this readout does not speculate past the
  evidence. The next step is the bytecode layer: build the SAL
  disassembler from the VM cluster (starting at monkey main
  FUN_651261A0's request handling), then read init.ocm's bootstrap
  for the module linker.

