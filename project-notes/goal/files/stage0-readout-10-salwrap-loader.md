# Stage-0 readout #10 — salwrap.dll: the .ocm module-load path (2026-10-22)

Static analysis only; nothing was executed. Target:
`Sony Shared/OpenMG/salwrap.dll` (307,200 B, PE32, image base
0x65100000; PDB name `salwrap2.pdb`, DailyBuild 5_0_00_200711280 —
the OpenMG 5.0.00.11280 build). Method: pefile triage, then Ghidra
12.1.4 headless (full auto-analysis + targeted decompilation +
reference mapping). Working papers (function list, string xrefs,
decompiler dumps) are in `~/workspace/atrac-salwrap-work/out/`.
Readout #9 is the prerequisite; readout #6's DLL triage was not
redone.

## Verdict up front

The loader is fully traced from file-open to "module ready", and
the headline is a negative with sharp edges: **in all of
salwrap's readable code there is no keyed cipher on module data
at all.** Files are read verbatim. The only bulk transform in the
native loader is zlib *decompression* of images flagged
compressed, followed by relocation. Whatever turns an on-disk
.ocm body into a module image happens in exactly one unread
place — a deliberately self-protecting native engine inside the
same DLL (it relocates its own code to randomized addresses and
calls through debug-register-mangled pointers) — or the body is
not ciphered at all but an ASN.1-framed stream that engine
decodes. No key material is needed from anywhere: everything the
traced path consumes is already in the Sony Shared tree Lola
sent, and the ominous `OMGKEY/omg_sal.dat` turns out to be a
legacy install-ID file, not key material (§5). As a bonus, the
sibling container `device.sal`'s integrity layer is completely
solved and verified against her files (§6).

## 1. The DLL in one map

salwrap.dll is three layers in one .text:

| Region (VA) | What it is |
|---|---|
| 0x65101000–0x6511FFFF | The C++ SAL manager (MSVC 7.1): the singleton context, EKB/service logic, device.sal handling, the OMG-ID manager, "salexec" profiling. |
| 0x65120000–0x65125330 | An unprotected C runtime-support library: error core, a per-thread heap, vendored **zlib 1.1.4**, the module-image manager, a SalAsn (ASN.1/DER) value codec, a global value store. Exposes a ~96-entry API vector table at 0x651423a0 (.rdata). |
| 0x65125490–0x65137FFF | The protected native execution engine ("monkey" — cf. the log strings `monkey main: 0x%x`, `monkey mt: 0x%x`): ~45 worker functions wrapped in a uniform anti-analysis trampoline (Get/SetThreadContext, Dr7 = 0x11110455, code pointers XOR 0x7FFFFFFF, VirtualProtect(PAGE_EXECUTE_READWRITE), rdtsc/rand-LCG randomized code placement, CPU-affinity pinning, physical self-copying of code blocks). |

Key inhabitants of the middle library:

- Error core: FUN_651200d0 (log), FUN_65120160 (raise; codes in
  the 0x14402xxx / 0x14404xxx families seen throughout).
- Heap: FUN_651203b0 (current thread's heap context, from a table
  at 0x6516B178 keyed by thread id), FUN_65120480 (size-classed
  free-list allocator; allocations tracked in a bitmap at
  heap+0x20, 8-byte units), FUN_6511FE90 (free).
- zlib 1.1.4, complete: inflateInit FUN_65121AF0, inflate
  FUN_65121C70, inflate_blocks FUN_65123700, huft_build
  FUN_651221C0, inflateEnd FUN_65121AA0; zalloc/zfree wrappers
  FUN_65124370 / FUN_65124390.
- ASN.1/DER codec ("SalAsn"): FUN_65124CC0 (INTEGER encode —
  minimal-length two's complement, DER length forms),
  FUN_65125020 (OCTET STRING encode).
- Global value store: FUN_65125230 — 128 slots × 0x44 bytes at
  0x6516B280, values ≤ 64 bytes, get/set under a critical
  section.

The three exports are trivial getters:

- `salwrap0` (0x65103940) → address of a host-services struct at
  0x65144F10 (.data). At init its tail is filled with host CRT/
  Win32 pointers (fopen, fread, fwrite, fseek, ftell, fclose,
  malloc, free, CoTaskMemAlloc/Free, LoadLibraryA,
  GetProcAddress, gmtime/asctime) — services offered *to*
  modules.
- `salwrap1` (0x65116670) → address of a cell at 0x651411DC
  holding the SAL API table pointer (table built at runtime;
  this is the pointer kdrmcom/pfcom/omgatpcd call through).
- `salwrap2` (0x6510E1E0) → address of a second cell at
  0x651411D4.

API-table entries observed in use from the C++ layer (offsets
from the table base): +0x3C load-module-by-name, +0x40 value/box
op (used around string handling everywhere), +0x44 release,
+0x64 call/apply, +0x6C/+0x70/+0x74 value constructors, +0x80
generate-ID (used for the OMG ID), +0x9C store.

## 2. The module-load path (phase-1 question 1)

Call sketch, file-open to "module ready":

1. **Init.** FUN_6511D680 (get-manager singleton) constructs the
   0x4D0-byte context via FUN_6511C8A0:
   - Registry reads (OpenMG key): `InitocmMemorySize2`,
     `SalMemorySize`, `SalMemorySize2` (arena sizes),
     `EnableSalExecLogging`, `logSalMessage`. **Sizes and
     logging only — no secrets.**
   - malloc 0x358040 B ("InitOcmMemory" arena) and the SAL
     memory arena (default 0x400000 B); both initialized into
     the protected engine via FUN_6512C7E0 / FUN_6512C810 →
     FUN_65125490 / FUN_6512C7B0 → FUN_651254C0 (which
     VirtualProtects the arenas executable and performs the
     engine's self-relocation setup).
   - Registers the error handler (FUN_65116480, "SAL INTERNAL
     ERROR:") and the log callback (FUN_65116590 →
     stderr/OutputDebugStringA) into engine globals via
     FUN_65125350 / FUN_65125370.
   - Loads **init.ocm** through API +0x3C; publishes the
     host-services table (salwrap0 struct); loads
     **region.ocm** through the API; then, if the flag at
     0x651411D8 is set, imports device.sal (step 5).
2. **File → buffer.** The manager's file cache FUN_6511B160
   resolves a repository-relative name with OMGUtils'
   `omgResolveRepositoryFile` and reads the whole file verbatim
   (`OmgString::readFromFile`), caching by name; callers get
   {data, length}. Every supporting file on the traced path
   (dnk.dat, EKB files, device.sal) is fetched exactly this
   way. Module bodies reach the kernel side through the
   salwrap1 API table.
3. **Image instantiation** (runtime library) — FUN_651243B0,
   API vector entry +0x20:
   - Registry scan: 128 slots × 24 bytes; a slot is
     {+0x00 flags/refcount, +0x04 image base, +0x08 image size,
     +0x0C entry point, +0x10 name (8 B)}. Match is a 7-char
     strncmp against the name at **image+0x3E**. A hit takes
     the refcount path and returns the existing image.
   - On a miss: if **image byte +0x47 == 1** and the name is
     not `wm` / `_wm` (the two exempt core modules), the image
     is first expanded in place (FUN_65124830, §3). Then a
     heap slot is allocated (FUN_651219B0), the image is
     memmove'd in, **relocated** (FUN_65121500, §2.1), its
     entry point computed (FUN_65124820: image +
     *(u32*)(image+0x4C)) and stored in the slot, and — unless
     the name starts with `bc` — its **symbol table is built**
     (FUN_651217B0: hash = sum of name bytes & 0x3FF, open
     addressing step 0xD, into a 1024-bucket table at
     0x6516EA10).
4. **Run / release.** FUN_65124B70 calls a slot's entry point
   with one argument; FUN_65124BF0 re-relocates and calls (the
   post-load init call); FUN_651249C0 → FUN_651249F0 release
   (refcount--; at zero FUN_65124AD0 removes the image's
   symbols and the image is heap-freed). The C++ orchestrator
   then loads the service modules the same way — device.sal
   import, l3.ocm (FUN_6511B7E0, which first reads the
   service's dnk.dat through the file cache), ekbman.ocm
   (FUN_6511BEE0), icv.ocm, kdrm.ocm, botamoti.ocm, maclist.ocm,
   mp4comp.ocm — all "load by name via the API table, then
   call entries", timed by the salexec wrapper FUN_6511B650
   when logging is on.

### 2.1 The in-memory image format (reconstructed)

All offsets from the image base; the header is 0x60 bytes
(FUN_65124830 copies exactly 0x60 bytes before the compressed
remainder):

| Offset | Field |
|---|---|
| +0x3E | Module name, 8 bytes (first 7 significant). Names starting `bc` = bytecode modules (no symbol table built). `wm`/`_wm` are exempt from expansion. |
| +0x46 | Type byte; value 's' observed — symbol values for such images get a +0x20 bias in FUN_651217B0. |
| +0x47 | Compression flag: 1 = remainder after the 0x60-byte header is zlib-compressed. |
| +0x4C | u32 entry-point offset (entry = image + this). |
| +0x50 | u32 symbol-section offset (entries: {name_off, value_off} pairs, offsets relative to the section). |
| +0x56 | u16 symbol count. |
| +0x58 | u32 relocation-table offset. |
| +0x5C | u32 relocation-table size in bytes; entries are 8 bytes: u8 type + 24-bit patch offset, then u32 value. |

Relocation types (FUN_65121500): 0x02 / 0x91 = image base +
value; 0x09 = absolute value; 0x34 = skip; 0x80 = API vector
table base (0x651423A0) + value — images link against the
runtime library; 0x81–0x88 and 0xCB–0xD1 = PC-relative
references to fixed salwrap addresses. After patching, the
loader calls FlushInstructionCache: **images contain native
code and are executed in place.** At the end of relocation, if
the 2 bytes at image+0x3E are not `bc`, the symbol-table build
runs — `bc` is the bytecode marker sitting in the name field.

## 3. The chunk transform (phase-1 question 2)

**What the readable code contains — the whole story:**
FUN_65124830 ("expand") is the only bulk transform on module
data in the unprotected regions. Given an image descriptor
{+4 size, +8 pointer} it:

- allocates a fresh heap slab (size × 6 bookkeeping via the
  bitmap heap; a per-slab bit guards against double-expansion,
  error 0x14402048),
- copies the first **0x60 bytes verbatim** (the image header),
- **zlib-inflates the rest**: input = image + 0x60, output
  continues after the copied header, using the vendored zlib
  1.1.4 (inflateInit with version string "1.1.4"),
- swaps the descriptor to the expanded slab.

Character: deterministic, keyless, single-stream (not
chunk-wise beyond zlib's own framing). **It is decompression,
not decryption** — no block size, no keystream, no key
schedule, no tables beyond zlib's Huffman machinery. A
protected twin, FUN_65133470, performs the identical operation
inside the engine region, calling inflate through the pointer
table at 0x65142500 (zalloc 0x65124370, zfree 0x65124390,
inflateInit/Inflate/InflateEnd) under the debug-register
trampoline — the engine guards even this mundane step.

**What the readable code does not contain:** any keyed cipher.
No XOR/rotate key loops, no S-boxes, no key schedule, no crypto
constants; file reads are verbatim (§2 step 2). Readouts #6/#9
found no CryptoAPI/bcrypt decryption in the loaders; this pass
extends that to the whole load path: the C++ layer never
transforms file bytes at all.

**Consequence.** The step that turns the on-disk body (first
bytes `01 01 04 08 6A 35 A2 1D…`, high entropy, no visible
image header) into a §2.1 image is in one of two places:

1. **The protected "monkey" kernel** — it implements the
   runtime side of the salwrap1 API table (load-by-name is
   +0x3C) and demonstrably hosts guarded copies of loader
   operations (the expand twin). If a decryption exists, it
   lives there.
2. **There is no cipher**: the body may be an ASN.1-framed,
   possibly compressed byte stream (the SalAsn layer; codec
   in §1, error string `bad SalAsnSeqEnd`) that the kernel
   decodes into an image. The body's leading bytes parse
   plausibly as TLV framing, and the format's data layer is
   ASN.1-shaped everywhere else we can see it.

Either way, the byte-identical 8,221-byte class-01 preamble
(readout #9) is consistent: both candidate transforms are
deterministic and IV-free, and the preamble argues against any
per-file-keyed cipher. If a key exists at all, it is fixed and
embedded on the kernel side. The DNK ECC material
(`ERR_SML_DNK_PRIV_ECC_DECRYPT`) belongs to the EKB/device-key
layer *inside* modules, not to the container load; no key
bytes, key files, or derivation code are referenced by the
load path.

## 4. Machine / install dependence (phase-1 question 3)

- **Registry**: sizes and logging switches only (§2 step 1).
  No secrets, no machine IDs.
- **OMGKEY/omg_sal.dat — resolved, and it is a red herring.**
  FUN_65119B20 (the ID manager): if `OMGKEY/omg_id.dat`
  exists, it is read as the install ID. Else if
  `OMGKEY/omg_sal.dat` exists, omg_id.dat is *derived from
  it* — first 0x16 bytes copied (FUN_65102040), two bytes
  zeroed — and written out. Else a fresh 16-byte ID is
  generated by executing icv.ocm through API +0x80 and
  logged (`omgid generated: %s`). FUN_6511A4A0, the getter
  the service code uses, throws an exception naming
  `OMGKEY/omg_sal.dat` when no ID is loaded — the filename
  in the error is historical, not a key reference. On Lola's
  install omg_id.dat is present (readout #9: OMGKEY holds
  only omg_id.dat), so this path is satisfied. **omg_sal.dat
  is not module key material; nothing needs fetching for
  it.**
- **No machine binding** (MAC, volume, CPU) appears anywhere
  in the traced load path. maclist.ocm is a SAL module loaded
  by name like the others, not a loader input.
- Caveat, stated plainly: the protected kernel is unread, so
  a binding inside it cannot be excluded from this phase
  alone. But every input the kernel receives on the traced
  path comes from files already in the Sony Shared tree.
  **Verdict: no additional Toshiba fetch is needed for
  phase 2.**

## 5. (Supporting result) device.sal — the sibling container, solved

FUN_65101000 is the .sal verifier (called from FUN_65118000,
FUN_65118120, and the import path FUN_65119F20):

- Header parse: **algorithm = BE u16 @2, version = BE u16
  @4** — different semantics from the .ocm header, whose @6
  dword is the OpenMG build stamp (11280); the CRC verifier
  is not applied to .ocm files on this path.
- Integrity: CRC-32 (polynomial 0xEDB88320, table built at
  runtime) over the whole file, except the four stored-CRC
  bytes @6 are replaced during the pass by the running CRC's
  low byte (a self-referential patch field); the file is
  valid iff ~CRC equals the LE u32 @6. A legacy form (the
  dwords @2 and @6 both equal to 0x01000000) short-circuits
  to version 1 / algorithm 1 without the CRC.
- **Verified in Python against both copies of her
  device.sal: stored 0x4BBC796 == computed. The scheme is
  exact.** Her file: algorithm 1, version field 0x1944.
- Import flow (FUN_65119F20): verify → extract version/
  algorithm → store the blob to the repository as both
  `device.sal` and `procfile/device.sal`; if the algorithm
  changed versus the running one, throw "restart required
  for new device.sal: (ver:%d, algo:%d)" (error 0x50B).
- The two containers share the 10-byte frame and the body
  blob family — device.sal's body begins with the same
  `01 01 04 08 6A 35 A2 1D 8C 3C 2C 0C 7E…` as class-01 .ocm
  bodies — which makes device.sal a second, CRC-pinned
  sample of the body format for phase 2.

## 6. The SAL VM — coarse map (phase-1 question 4)

- Two execution kinds share the §2 image manager: **native
  images**, relocated and executed in place inside the
  malloc'd arenas under the "monkey" engine; and **`bc`
  images**, which skip symbol-table construction — the
  SalBytecode modules.
- The bytecode's data layer is visible and in the runtime
  library: the SalAsn ASN.1/DER codec (FUN_65124CC0,
  FUN_65125020) and the global value store (FUN_65125230).
  `SalBytecode::dataType()` is a C++ method in the manager
  region; the manager's exec wrapper FUN_6511B650 resolves a
  module by name through FUN_65116360 and times the call
  (`salexec: %s: %d msec`).
- **The interpreter dispatch itself was not pinned this
  phase.** No readable switch/jump-table interpreter exists
  in the unprotected regions; the dispatch lives inside the
  protected engine, whose large workers (FUN_651261A0 —
  the "monkey main" entry called from arena init —
  FUN_65126970, FUN_651276C0, FUN_65127DD0, FUN_6512DA00,
  FUN_65130A70, FUN_651312C0, FUN_65132220, FUN_65133890)
  are the phase-2 starting points. That is as far as honest
  static reading goes without de-obfuscating the trampoline
  pattern first.

## 7. Known vs unknown

Known: the complete load path (init → file cache → image
manager → relocation → entry points); the in-memory image
format (§2.1) including the compression flag and the
relocation type system; the only native transform (zlib
expansion, FUN_65124830 + protected twin FUN_65133470); the
API vector table contents; the exports' semantics; the
OMG-ID file logic; the device.sal container completely
(header + CRC, verified).

Unknown: the on-disk body → image transform (inside the
protected kernel, or an ASN.1 stream decode); whether the
kernel's load-by-name performs any keyed step at all; the
SAL bytecode ISA / dispatch internals; the SalAsn framing of
the body (plausible, unproven).

## 8. Phase-2 plan (phase-1 question 5)

1. **Test the stream hypotheses against the oracle before
   touching the protected engine.** (a) Parse the class-01
   body as SalAsn TLV starting at offset 10: does the
   framing consume the file exactly, and do chunk boundaries
   land on the observed sharing offsets (8,221 B class-01
   preamble; 8,481 B atpcd/lgd)? (b) Try zlib / raw-deflate
   at every boundary the framing suggests. Oracles: the
   class-01 preamble must yield a valid §2.1 image header
   (plausible 7-char name at +0x3E, in-range entry/symbol/
   reloc fields; if +0x47 == 1 the remainder must inflate
   cleanly), and device.sal's body — same blob family,
   container already pinned by CRC — is the second sample.
2. **If framing alone doesn't open it, attack the kernel at
   its seams, not its trampolines.** Load-by-name (API
   +0x3C) must somewhere hand an already-formed image to
   FUN_651243B0. Trace references *from* the engine region
   *to* the API vector table (0x651423A0) and the
   image-manager entries, find the one function that makes
   that hand-off, and read what it does between the file
   cache and the call — the transform is there.
3. **De-obfuscate mechanically.** The trampoline pattern is
   uniform (GetThreadContext → mangle → SetThreadContext
   Dr7=0x11110455 → call (ptr ^ 0x7FFFFFFF) → restore). A
   Ghidra script that recognizes and strips the
   prologue/epilogue should collapse the ~45 engine workers
   into ordinary readable functions, the load transform
   among them.
4. **Validate, then build.** Any candidate transform is
   proven against the §8.1 oracles across all 25 class-01
   modules plus device.sal; then write the .ocm dumper
   (10-byte header → transform → expand → relocation map)
   and only then start the SAL disassembler, from the §2.1
   image format and the SalAsn codec semantics.

Difficulty, updated from readout #9: the container layer is
easier than feared in one way — the native loader holds no
cipher and the sibling container fell to a plain CRC — and
harder in another: the one unread region is deliberately
self-protecting. Step 1 is cheap and goes first; step 3 is
the fallback that cannot fail to pay off, only cost time.
