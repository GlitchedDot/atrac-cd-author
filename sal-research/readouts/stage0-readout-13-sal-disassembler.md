# Stage-0 readout #13 — SAL attack phase 3: the disassembler, and why there is no native dispatch to extract (2026-10-22)

Static analysis only; nothing was executed. Materials: `salwrap.dll`
(MD5 `8bb3f0258a178e099700d00acd444a98`) and the `.ocm` modules in
`~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG/`. New working
papers: `~/workspace/atrac-salwrap-work/sal_dis.py` (the disassembler),
`scripts/scan_dispatch.py` / `scan_dispatch2.py` / `scan_vm.py` /
`skeleton.py` / `fingerprint.py` / `dump_range.py`,
`scripts/SalPhase3.java` / `SalPhase3b.java`, and outputs in `out/`
(`phase3-refs.txt`, `phase3-decomp.c`, `phase3b-decomp.c`,
`vm-scan.txt`, `block-diff.txt`, `monkey-main.asm`, `gap1–3.asm`,
`fun_65127140.asm`, `apicall.asm`, `ctxpush.asm`).

## Verdict up front

**There is no bytecode fetch/decode/dispatch loop in salwrap.dll —
proven, not merely not-found.** Whole-`.text` capstone scans find
nine jump tables, every one identified (EKB parse switch, relocator
switch, zlib, the SalAsn writers, error printers); **none is in the
engine region and none dispatches opcodes**. The engine's 155 byte
loads are spread across 41+ functions at 2–10 apiece — the
self-relocation memmove boilerplate every worker carries — with no
concentration anywhere that a fetch loop would require. The 19
VM-cluster workers take their operands from continuation frames and
arg structs; **not one of them reads a byte stream**.

What the native code *does* fully specify is the **value layer**:
the SalAsn operand grammar, recovered byte-for-byte from the
host-side reader class (`SalBytecode`, C++ region) and the
runtime-lib writers. That grammar is now implemented in
`sal_dis.py`. Fed the on-disk bodies, it parses exactly the
universal 13-byte head of every class-01 module
(`INT1 1`, `STR[8] 6A35A21D8C3C2C0C`) and dies at body+0x12 in all
of them — the stored body is **not** the executed stream, for the
bootstrap module too. The transform therefore sits where readout
#12's candidate (a) put it: **in init.ocm's own bytecode**, with
candidate (b) (a per-value decode in a native fetch path) now
strongly disfavored because there is no native fetch path for it
to live in. **atpcd.ocm remains undecrypted**; §6 lists exactly
what remains.

## 1. Dispatch anatomy — what actually sequences execution

Execution in the engine is a **continuation machine**, not an
interpreter loop (all of this verified by direct reading this
phase, building on readout #12):

- **Entry**: manager `salexec` (FUN_6511B650) → FUN_65116360 →
  arena thunk FUN_651349F0/FUN_65134A10 → gatekeeper FUN_6512C840.
  (This also closes readout #12's open thread: FUN_65116360 *is*
  the C++ caller of the arena-2 thunk.)
- **Hop gate** FUN_65125AB0: pushes a {target, 0x900} frame onto
  the state stack at `state[0x6D]` (ctx-state +0x1B4), copies the
  0x100-byte gate stub to a randomized address, and uses it to
  relocate the next worker's 0x800-byte block before jumping in.
- **ctxpush** FUN_65125420 (raw asm in `out/ctxpush.asm`): pops
  12-byte continuation frames {f0, f1, f2} from the queue at
  ctx+0xC4 into ctx+0x9C/+0xA0/+0xA4, maintains a parallel saved
  stack at ctx+0xB4, and unmangles the current code pointer from
  ctx+0xC (`^ 0x7FFFFFFF`).
- **Workers are services, sequenced by frames.** Identified this
  phase: global init FUN_6512A630 (one-time: callback globals,
  16 critical sections at 0x6516E890, zeroing the 128-slot module
  registry at 0x6516B280); registry get/set workers FUN_65129AC0 /
  FUN_65129EF0 (error 0x14404021) and FUN_6512A320; API-trampoline
  builder FUN_65127140 (emits 16-byte `push target; call
  dispatcher; jmp [shadow]` stubs at 0x6516D495+, shadow table at
  0x6516E490, ≤256 entries — the protected twin of FUN_6512D5B0's
  job, with the call dispatcher inside FUN_651276C0); heap
  alloc/free twins FUN_6512FF30 / FUN_6512FAB0 (size-class buckets,
  bitmap double-free check — the workers readout #12 left
  unclassified); relays FUN_651261A0/FUN_65126970 (6 bytes different
  in the first 0x800 — one per arena). The remaining VM workers
  touch nothing but ctx+0x18: pure compute on frame-supplied values.
- **Cross-module calls are native.** API vector +0x28
  (FUN_65124B50 → FUN_65124B70): symbol index <0x80 resolves in the
  global registry table, 0x80–0xFF in the calling image's own
  24-byte-entry table; entry+0xC is called directly. API +0x2C
  (0x65124BF0): relocate the module, compute entry as
  `image + *(u32*)(image+0x4C)`, call it. A "bc" module's entry is
  therefore reached *through the engine*, never by a native jump
  into its stream — consistent with the stream being consumed by
  bytecode-side code, not by a native loop.

## 2. The recovered value grammar (the ISA layer that exists)

From the `SalBytecode` reader class (gap functions at
0x651175F0 `dataType()`, 0x65117800 readSeqEnd, 0x651178E0
readString, 0x65117990 readInteger; Ghidra functions FUN_65117400
readLength, FUN_651174C0, FUN_65117700 readSeqBegin) and the
writers FUN_65124CC0 (integer) / FUN_65125020 (octet string).
Object model for the reader: buffer object with cursor at +0x1C
and sequence depth at +0x20. **Confidence: proven** (handler code
+ error strings) for every row unless marked.

| Encoding | Meaning | Evidence |
|---|---|---|
| length byte < 0x80 | short length = the byte | FUN_65117400 |
| length byte > 0x80 | long length: (b & 0x7F) big-endian length bytes follow | FUN_65117400 |
| length byte = 0x80 | indefinite — legal only after a SEQUENCE tag; for operands it throws "indefinite ber length for OPERAND_S" | FUN_65117400 |
| `01 <1B>` | INT operand, 1 content byte, signed big-endian | readInteger switch @0x65117990 |
| `02 <2B>` | INT operand, 2 content bytes (operand level, depth 0) | readInteger switch |
| `03 <len> <B…>` | INT operand, DER length + content ("OPERAND_1,2,N") | readInteger switch |
| `02 <len> <B…>` | INTEGER (DER form) at depth ≥ 1 — the reader *requires* tag 0x02 + length inside a counted region ("ASN_TAG_INTEGER expected") | readInteger nesting branch |
| `04 <len> <B…>` | OCTET STRING; at depth 0 named OPERAND_S ("OPERAND_S expected" / "ASN_TAG_OCTETSTRING expected") | FUN_651174C0, FUN_65117700, writer FUN_65125020 |
| `30 80` | SEQUENCE begin (BER indefinite length) | FUN_65117700 ("ASN_TAG_SEQUENCE 0x80 expected") |
| `00 00` | SEQUENCE end (EOC) | readSeqEnd @0x65117800 ("0x00 0x00 expected", "bad SalAsnSeqEnd") |
| first-byte classes | dataType(): 1/2/3 → type 0 (int); 4 → type 1 (string); 0 → type 3 if depth>0 and next byte 0, else type 2; ≥5 → type 2 | dataType() @0x651175F0 |

Integer *values* are arbitrary-precision (limb array: sign byte,
u16 limb count, big-endian 32-bit limbs — FUN_65124CC0) serialized
as the minimal signed big-endian byte string above. The writer
emits the compact forms (`01`/`02` for 1–2 content bytes, else
`03` + DER length), matching the reader byte-for-byte.

**What is NOT in this grammar**: any opcode space. The reader
class knows values, sequences, and operands — no instruction
tags, no branch/call encodings. Whatever turns a value stream
into behavior (which operand sequence invokes which worker) is
defined by the executing program itself, i.e. by init.ocm's
bootstrap code, not by a native table this DLL contains.

## 3. The disassembler

`~/workspace/atrac-salwrap-work/sal_dis.py` implements §2 exactly
(context-sensitive integer forms tracked by sequence depth,
BER indefinite sequences, strict failure on overrun; unknown tags
fall back to generic BER TLV marked INFERRED). It strips the
10-byte .ocm header, and init.ocm's 5-byte wrapper, automatically.

### What it was fed, and what happened

Per the brief, the best available candidate stream is the raw
body (the manager hands raw bodies to the engine; no decoded
stream exists yet). Results:

- **init.ocm bootstrap region** (body at file offset 15): strict
  parse = `INT1 1`; `STR[8] 6a35a21d8c3c2c0c`; then tag 0x7E at
  body+0x0C has no strict form. Generic-BER fallback wanders 210
  bytes through chance-fitting lengths before dying at body+0xD2
  — noise, not coherence. **The bootstrap does not disassemble
  from its stored form.**
- **Class-01 family** (icv, restore, osss, omgtopcm2, device.sal):
  identical story — strict run of 2 elements / 12 bytes, failure
  at body+0x12 (tag 0xE1 under the fallback). This reproduces
  readout #11's offset-18 SalAsn failure, now with the *correct*
  grammar: the failure is not a grammar mismatch.
- **Variants tried**: stream starting at body+12 (dies at +6);
  stream starting at body+13 ("head is a plaintext body header"
  hypothesis — yields one STR[8192] blob of high-entropy content
  plus garbage TLVs, dying at +0x205C; a permissive-parser
  artifact, not structure).
- **Class-02 bodies** (atpcd etc.): no framing at byte 0 under
  any variant — transformed from the first byte, as established
  in readout #12.

### Cross-checks (brief §5)

- **Shared prefix**: icv/restore/osss share **8,211 body bytes**
  byte-for-byte (family figure 8,221 from readout #11 across all
  25); the disassembly of the parsed region is byte-identical
  across the three modules — the check passes in form, and its
  content is the finding: the coherent region is 12 bytes long.
- **Entry-point consistency (+0x4C)**: cannot be performed. The
  +0x4C entry offset belongs to the *formed image*, which does
  not exist until the transform falls. The on-disk body offset 0
  is the only candidate stream start, and it is the one tested.

## 4. Transform candidates — the evidence now favors (a)

**(a) A module linker/decryptor in SAL bytecode inside
init.ocm — FAVORED.** (i) Every native avenue for the transform
is now closed with receipts: no cipher (readout #12 §5), no
fetch loop, no dispatch (this readout §1). (ii) init.ocm is
fetched first by manager init, before any other module; at
582 KB it has room for the stdlib plus a linker. (iii) The
engine supplies exactly the services a bytecode linker needs —
image registration/expansion/relocation twins, heap twins,
registry workers, the continuation machine — and readout #12
already established that FUN_65132220's formed-image supplier
"is inside the VM/bytecode layer". (iv) Class-01 is the class
whose 13-byte head is shared with device.sal, the host-parsed
data container — the bootstrap family is the one a minimal
native hand-off can plausibly prime.

**(b) A per-value decode inside the VM's fetch path —
STRONGLY DISFAVORED.** There is no fetch path: VM workers
receive operands in frames/arg structs and never touch a byte
stream (§1). A decode "interleaved with SalAsn value
construction" (readout #12's phrasing) would still need code
that reads stored bytes and writes decoded values; the only
byte reads in the engine are the relocation copies, and the
only value constructors are the §2 writers, which encode —
they do not decode a stored stream. Not logically excluded for
a transform hidden inside an individual worker's operand
handling, but no worker examined handles stored-stream operands
at all.

One refinement to readout #12 §5: whether the class-01 13-byte
head is *plaintext framing* or *fixed-start ciphertext that
happens to parse* is still open — the disassembly cannot
distinguish them, because the head is identical under both
readings. It does not affect the verdict: from body+0x0C onward,
the stored form is not the executed form, for every module
including the bootstrap.

## 5. What remains unknown — exactly

1. **The transform algorithm** — now believed to be bytecode
   inside init.ocm. Reading it requires the *execution*
   semantics of the value stream (which operand sequences the
   bootstrap treats as instructions), which is defined by the
   bootstrap itself plus the continuation-frame contract — a
   bootstrap-recovery problem, not a table lookup.
2. **The bootstrap priming contract**: what frame(s) the
   manager/gatekeeper build from init.ocm's {data, len}
   descriptor, and what monkey main does with them beyond
   relaying (its hop segments copy arg fields; the semantic
   payload, if any, is inside the gate choreography).
3. **The continuation frame's f0 semantics**: worker address,
   table index (0x6516D490/0x6516E490), or SalAsn value — the
   frame format is known ({f0, f1, f2} → ctx+0x9C/A0/A4); the
   selector's encoding is not.
4. **The key's exact home** (unchanged from readout #12):
   bytecode-side — init.ocm's data, or unwrapped by the DNK ECC
   layer into a module-carried content key.
5. **Class-01 head**: plaintext vs fixed-start ciphertext
   (§4 refinement) — undecidable from stored bytes alone.

## 6. Validation

- Grammar cross-validated three ways: reader code (cursor
  class), writer code (FUN_65124CC0/FUN_65125020 emit exactly
  the forms the reader accepts), and the modules themselves
  (every class-01 body + device.sal opens with `INT1 1` /
  `STR[8]` under the grammar — 26 files, zero exceptions).
- **atpcd.ocm decrypted: NO.** The disassembler is built and
  the ISA's value layer is mapped, but the executed stream is
  behind a bytecode-side transform. The next step is
  bootstrap recovery: pin the priming contract (§5.2) and the
  frame selector (§5.3) from the gatekeeper/monkey-main asm,
  then read init.ocm's bootstrap as a program in the §2 grammar
  with those semantics — starting from the observation that its
  first values (`INT1 1`, `STR[8] 6A35A21D8C3C2C0C`) look like a
  version + fixed family key-check block, i.e. the bootstrap's
  own header, in stored form, may be the one part the native
  side consumes directly.
