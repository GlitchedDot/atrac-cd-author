# Session 59 — CDRFormatter.dll: where do the TOC disc-ID bytes come from? (desk-only, 2026-11-03)

No builds, no burns, no harness drives. Binary dissection only.
Full Ghidra decompilation produced this session: `decomp-cdrformatter.c`
(2,080 functions, 0 failures) in this directory; xref dumps in
`xrefs.txt` / `xrefs2.txt` / `xrefs3.txt`; bounded capstone passes quoted
inline below (raw bytes are the authority where Ghidra's SEH-frame
rendering loses arguments).

## HEADLINE VERDICT

**CDRFormatter.dll does not mint the disc IDs at all — it is a pure
conduit.** `CreateCDRFormatFiles` *receives* the pair from its caller as
plain buffer parameters, validates only that the pointers are readable
(16 B / 8 B), stores them verbatim in a small holder struct, and the TOC
writer copies them verbatim into TOC00000.STI. No computation, no
sealing, no COM, no clock touches them anywhere inside this DLL.

Sony's own names for the two fields (proven from the exported readers,
see Job 2): the 8-byte field at TOC+0x10 is the **ICV**; the 16-byte
field at TOC+0x20 is the **DiscID**. (S57/S58 notation: id_a = ICV,
id_b = DiscID.)

The one held caller of `CreateCDRFormatFiles` is **CDWalkman.dll**
(AVLib sibling), and inside CDWalkman the trail splits:
- the **DiscID** is passed from a member buffer of the CDWalkman
  session object (`this+0x204`) — who fills that member is NOT visible
  in CDWalkman .text (bounded sweep), so it is set by CDWalkman's own
  caller/construction path, one layer up;
- the **ICV** is computed immediately before the call by a virtual
  method (`vtable+0x30`) on an object inside CDWalkman, fed with the
  vector of audio-file sizes obtained from the formatter — the ICV
  minter is that method's class, inside or behind CDWalkman.dll.

**CDWalkman.dll is the next dissection target** (see "Ranked next step").

## Setup / verified anchors

- Target: CDRFormatter.dll, 360,448 B, MD5 3930a77040367bfc3dc36a8f50a583a1,
  from toshiba-trees-2026-11-02/sony-shared/Sony Shared/AVLib/.
  ImageBase 0x60200000, SizeOfImage 0x58000. (RVAs below are file RVAs;
  VA = 0x60200000 + RVA.)
- S58 anchor RVAs verified firsthand from the export table:
  - CreateCDRFormatFiles (ord 48) RVA 0x299bd —
    `long CCDRFormatter::CreateCDRFormatFiles(unsigned short* drive,
    unsigned char const* p2, unsigned int p3, unsigned char const* p4,
    CVector<unsigned short*>* p5)` (demangled from the export name).
  - CreateCDRFormatFilesForRetry (ord 49) RVA 0x29b94 — same signature.
  - GetDiscID (ord 83) RVA 0x29e4e — `long GetDiscID(unsigned short*, unsigned char*)`
  - GetICV (ord 96) RVA 0x29f84 — same signature shape.
  - Full export list (195) contains **no SetDiscID / SetICV export** —
    confirmed firsthand this session.

## Job 1 — TOC buffer assembly / ID source trace

### The ID-fill call graph (all RVAs; VA = RVA + 0x60200000)

```
CDWalkman.dll  (function containing VA 0x60419562)
  └─ CCDRFormatter::CreateCDRFormatFiles            RVA 0x299bd
       ├─ SelectDrive                               RVA 0x27ae1
       ├─ FUN_602099b3  (drive medium-info dispatch) RVA 0x99b3
       └─ worker FUN_6021d93f                       RVA 0x1d93f
            ├─ holder ctor FUN_60234a62             RVA 0x34a62
            ├─ holder operator= FUN_60234372        RVA 0x34372
            │    → formatter member holder (this+0x928)
            ├─ … track/group staging, size checks …
            └─ TOC writer FUN_6022d1b2              RVA 0x2d1b2
                 ├─ holder GetICV  FUN_60234611     RVA 0x34611 → TOC+0x10
                 └─ holder GetDiscID FUN_602344f1   RVA 0x344f1 → TOC+0x20
CreateCDRFormatFilesForRetry (0x29b94) → worker FUN_6021e3aa (0x1e3aa)
  → same ctor (xref 0x6021ea09) and same writer (xref 0x6021ec97).
```

### Step 1 — the exported entry takes the pair as parameters

Bounded capstone of the wrapper's call to the worker (VA 0x60229a89):

```asm
push dword ptr [ebp + 0x18]     ; param_5 (CVector of EKB file paths)
mov  ecx, dword ptr [edi]       ; ECX = CCDRFormatter this
push dword ptr [ebp + 0x14]     ; param_4  ── the 8-byte buffer
push dword ptr [ebp + 0x10]     ; param_3  ── uint
push dword ptr [ebp + 0x0c]     ; param_2  ── the 16-byte buffer
push dword ptr [ebp + 0x08]     ; param_1  ── drive path
push dword ptr [ebp - 0x14]     ; worker-local
push dword ptr [ebp - 0x18]     ; worker-local
call 0x6021d93f                 ; worker
```

So the worker's stack args are: (local, local, drivePath, **param_2**,
param_3, **param_4**, param_5).

### Step 2 — the worker validates sizes, then constructs the holder

Worker FUN_6021d93f entry validation (decompiled, cross-checked against
the disassembly at 0x6021d9d4–0x6021da0a): NULL checks on the param_2 /
param_4 / param_5 slots, then `IsBadReadPtr(param_2, 0x10)` and
`IsBadReadPtr(param_4, 8)` — a 16-byte and an 8-byte caller buffer,
exactly the DiscID and ICV sizes.

Mid-worker (capstone, VA 0x6021dd78–0x6021ddbd — the decisive block):

```asm
push 0x30
call 0x602394d6                 ; operator new(0x30)
mov  ecx, eax                   ; ECX = fresh holder
push dword ptr [ebp - 0x664]    ; arg4: EKB filename vector
push dword ptr [ebp + 0x1c]     ; arg3: param_4 (8 B)
push dword ptr [ebp + 0x18]     ; arg2: param_3 (uint)
push dword ptr [ebp + 0x14]     ; arg1: param_2 (16 B)
call 0x60234a62                 ; holder CONSTRUCTOR
mov  esi, eax
mov  ecx, dword ptr [ebx + 0x928]  ; ECX = formatter's member holder
push esi
call 0x60234372                 ; member_holder->operator=(temp)
; temp holder then destroyed (dtor FUN_60234cfb + free)
```

The constructor FUN_60234a62 (decompiled, quoted in substance):

```c
// this = _Dst (ECX); args: p1@[ebp+8], p2@[ebp+0xc], p3@[ebp+0x10], vec@[ebp+0x14]
flags(+0x20,+0x24,+0x28,+0x2c) = 0;  field(+0x1c) = 0;
if (p1 == 0 || p3 == 0 || vec == 0) throw 0x80070057;
if (IsBadReadPtr(p1, 0x10) || IsBadReadPtr(p3, 8)) throw 0x80004005;
this->+0x1c = new EKB-file-list vector;
for each name in vec: if (!FUN_60234748(name)) throw 0x80000202;  // EKB name check
memcpy(this + 0x00, p1, 0x10);            // DiscID[16]  = param_2
memcpy(this + 0x14, p3, 8);               // ICV[8]      = param_4
*(DWORD*)(this + 0x10) = p2;              // EKB version = param_3
flags(+0x20,+0x24,+0x28,+0x2c) = 1;
```

**The holder struct (0x30 B)** — the same layout is used by the ctor,
the copy-ctor (FUN_60234ba6), operator= (FUN_60234372: copies +0x00[16],
+0x10, +0x14[8], +0x20, +0x24, +0x28, +0x2c), and all accessors:

| offset | content | validity flag | setter | getter |
|---|---|---|---|---|
| +0x00 | DiscID[16] | +0x20 | FUN_60234470 (RVA 0x34470) | FUN_602344f1 (RVA 0x344f1) |
| +0x10 | EKB version (dword) | +0x24 | FUN_6023457a (RVA 0x3457a) | — (internal) |
| +0x14 | ICV[8] | +0x28 | FUN_6023458d (RVA 0x3458d) | FUN_60234611 (RVA 0x34611) |
| +0x1c | EKB-file-list vector* | +0x2c | ctor | — |

The getters return 0x203 when their flag is unset — they are pure
flag-gated memcpy-outs. A whole-.text E8 call-site census shows the
three setters are called **only** from the TOC parser FUN_60223635
(VAs 0x60223870 / 0x602238cf / 0x60223903) — inside this DLL the holder
is filled either by the ctor above (from CreateCDRFormatFiles params)
or by parsing an existing TOC. There is no third fill path and no
generation arithmetic anywhere.

### Step 3 — the writer copies holder → TOC buffer verbatim

TOC writer FUN_6022d1b2 (7,047 B; called by the worker with
ECX = [this+0x930] and the member holder [this+0x928] as a stack arg —
capstone at worker VA 0x6021df31/0x6021df44). It creates
`<dir>\TOC00000.STI`, allocates the TOC buffer as
`(0x90 + trackCount) * 0x10` bytes (= 2304 + 16/track, matching S58),
and fills the fixed header (decompiled, offsets relative to buffer):

```c
memcpy(buf, "TOC ", 4);
… version word @+4, zeros @+6, byte @+8, byte @+9,
  track count LE16 @+0x0a, total_seconds BE32 @+0x0c …
iVar11 = FUN_60234611();              // holder->GetICV(local_1c)
memcpy(buf + 0x10, local_1c, 8);      // ★ ICV  → TOC+0x10
memset(buf + 0x18, 0, 8);
iVar11 = FUN_602344f1();              // holder->GetDiscID(local_2c)
memcpy(buf + 0x20, local_2c, 0x10);   // ★ DiscID → TOC+0x20
memset(buf + 0x30, 0, 0xd0);
```

The two locals (−0x1c / −0x2c) form one 24-byte scratch block; the
getter call sites inside the writer (capstone VA 0x6022d407–0x6022d414
and 0x6022d457) load ECX from the writer's holder argument
(`mov ecx, [ebp+0x2c]`) and push those exact locals as out-buffers.
After the header, the writer proceeds to GROUP.NDB and the per-track
records — no other ID involvement.

### Step 4 — the caller: CDWalkman.dll supplies both buffers

Import census of the held corpus (targeted, this session): within
AVLib, **CDWalkman.dll is the only binary importing
CreateCDRFormatFiles** (it imports 84 CDRFormatter symbols, including
CreateCDRFormatFilesForRetry; AtpFringe.dll imports 26 but not this
one). No binary in the SonicStage app tree (incl. Omgjbox.exe) imports
CDRFormatter at all — the app reaches the formatter through CDWalkman.

CDWalkman's single call site (bounded capstone, VA 0x6041953f–0x60419562):

```asm
mov  ecx, dword ptr [esi + 0xec]  ; ECX = CDWalkman's CCDRFormatter member
lea  eax, [ebp - 0x1e4]  ; push eax   ; arg5: EKB filename vector (local)
lea  eax, [ebp - 0x1c]   ; push eax   ; arg4: ICV buffer = STACK LOCAL
push 0x1000e                          ; arg3: EKB version = 0x0001000E (constant)
lea  eax, [esi + 0x204]  ; push eax   ; arg2: DiscID = member of CDWalkman object
push dword ptr [ebp-0x160]            ; arg1: drive path
call dword ptr [0x6042114c]           ; CreateCDRFormatFiles
```

And immediately before it (VA 0x604194a0–0x6041951e):

```asm
mov byte ptr [ebp - 0x1c], 0  ; ICV local zeroed (8 B: stosd/stosw/stosb)
…
mov ecx, [esi+0xec]; call GetSizesOfAllAudioDataFiles   ; → sizes vector @[ebp-0x180]
…
mov eax, [ebx]
lea ecx, [ebp - 0x1c]   ; push   ; out: ICV local
lea ecx, [ebp - 0x180]  ; push   ; in:  sizes vector
mov ecx, ebx
call dword ptr [eax + 0x30]      ; ★ ebx->vtable[0x30](sizes, &icv)
```

So in CDWalkman: the **ICV is produced by a virtual call** on an object
(ebx — obtained earlier in the same function; its class is not pinned
by this bounded pass) whose inputs include the per-file audio sizes;
the **DiscID is read from the session object's own member at +0x204**,
which a .text sweep shows is *referenced* only at the two
CreateCDRFormatFiles call sites (0x60419555 and 0x604197b2, the retry
twin) and *written nowhere* in CDWalkman .text — it must be filled via
the object's construction or by CDWalkman's own caller through a
pointer/method. Both threads are inside CDWalkman.dll's layer and are
the next dissection (not dissected here, per brief).

## Job 2 — the ICV thread

The ICV and the DiscID are **two fields of one holder struct** and
share the entire path: caller buffers → ctor → formatter member holder
(+0x928) → writer getters → TOC+0x10 / TOC+0x20. Neither is derived
from the other inside this DLL.

The exported readers confirm the naming and the shared source:
- `GetDiscID` (0x29e4e): state check → SelectDrive → medium-info
  (FUN_602099b3) → FUN_60212ef1 (xref 0x60229f21) → holder getter
  FUN_602344f1 copies **holder+0x00[16]** out. The 16-byte field IS
  Sony's "DiscID".
- `GetICV` (0x29f84): mirror image → FUN_60212f97 (xref 0x6022a057) →
  holder getter FUN_60234611 copies **holder+0x14[8]** out. The 8-byte
  field at TOC+0x10 IS Sony's "ICV".

The read-back path: loader FUN_60226229 opens `<dir>\TOC00000.STI`
(requires 0x910 ≤ size; reads up to 0x4770 B) and calls the parser
**FUN_60223635**, which validates the "TOC " magic and fills the holder
from the file: ICV from file+0x10 via setter FUN_6023458d, DiscID from
file+0x20 via setter FUN_60234470, and the EKB-version dword from
file+0x1C via setter FUN_6023457a. (Asymmetry worth noting: the writer
always writes file+0x18..+0x1F as zero and the authoring chain carries
the EKB version in holder+0x10 from the caller's constant instead; the
parser nevertheless treats +0x1C — the upper half of that zeroed
field — as that dword's slot.) The loader's
only caller is FUN_6021f468, which also copy-assigns the holder
(FUN_60234372) — the load-existing-format-files flow (backup/compare
family). The medium-info helper FUN_602099b3 used by GetDiscID/GetICV
is a *drive* dispatch (vtable call with 12 out-params into a per-drive
object found in a map) — it refreshes drive/medium state; it does not
touch the holder's ID fields.

## Job 3 — time / RNG inputs to the ID path: NONE

Whole-DLL call-site census via the IAT slots (capstone sweep):
- `GetTickCount` — exactly one call site, VA 0x602399f5;
  `GetSystemTimeAsFileTime` — exactly one, VA 0x602399d9. Both sit in
  the MSVC CRT runtime block (adjacent to the security-cookie helpers
  around FUN_60239560) — CRT clock seeding, not formatter logic.
- `GetLocalTime` — exactly two call sites, VA 0x60238d7e / 0x602391cd,
  inside ATL time helpers FUN_60238b60 / FUN_60238fb0.
- No `rand`/`srand`/`CoCreateGuid`/`Crypt*` imports exist at all
  (import table verified firsthand).

None of these is reachable from CreateCDRFormatFiles, the workers, the
writer, the parser, or the holder accessors. **Time does not feed the
ID bytes anywhere in CDRFormatter.dll.** (This kills the "per-session
sealed mint inside the formatter" variant of S58's M1 — the formatter
never mints; if time/randomness enters, it enters in CDWalkman or
above, e.g. inside the ICV vtable method.)

## Job 4 — COM delegation: NOT in the ID path

The ID path (CreateCDRFormatFiles → worker → writer) contains **no COM
call at all**. The DLL's single `CoCreateInstance` (VA 0x6021126f, in
`CDRDriveManager::InitializeAPI`, FUN_60210e52) instantiates the
**burn** engine:

- Interface: **ICdrDataWriter**, IID **{6E353DBD-F2EB-410C-AC9A-872DEA231AE7}**
  (16 bytes at VA 0x6023d47c, read firsthand; the in-situ debug string
  reads "<CDRDriveManager::InitializeAPI> ::CoCreateInstance(
  IID_ICdrDataWriter ) Failed [0x%08X]").
- The CLSID is not a constant: helper FUN_60207d2d (called from
  FUN_60210e52) opens
  `HKLM\Software\Sony Corporation\OpenMG\PD\{CB23CD64-FDE3-4AC8-BA08-3E4457AAF50A}\<index as %X>`,
  enumerates its first subkey, and treats the subkey NAME as a CLSID
  string for the DLL's only `CLSIDFromString` call (VA 0x60207e60).
- AVLib contains `CdrDataWriterps.dll` (the proxy/stub), consistent
  with an out-of-proc sector writer. This engine writes the authored
  files to the medium during Burn — downstream of, and irrelevant to,
  ID minting. No corpus search for an implementing binary is needed:
  it is not the ID source.

## Job 5 — could a harness call anything in held code to mint a pair?

**No.** In CDRFormatter.dll:
- `CreateCDRFormatFiles` / `CreateCDRFormatFilesForRetry` are callable
  and will author a complete, genuine-shaped format-file set — but
  only with a DiscID[16] and ICV[8] the caller already possesses. The
  DLL performs zero minting and zero validation of the pair beyond
  pointer readability (IsBadReadPtr) — garbage in, garbage out. Its
  full input list: drive/target directory path (ushort*), DiscID
  buffer (16 B), EKB version (0x0001000E), ICV buffer (8 B), and the
  EKB filename list (CVector<ushort*>) whose names must pass the EKB
  filename check FUN_60234748.
- The holder setters are internal (not exported) and are themselves
  memcpy gates — calling them mints nothing.
- GetDiscID/GetICV only read back what the holder already holds.

The minting therefore lives strictly on the caller side:
**CDWalkman.dll**, in (a) the vtable+0x30 method that computes the ICV
from the audio-file sizes at the CreateCDRFormatFiles call site, and
(b) whatever fills the CDWalkman session object's DiscID member at
+0x204 (its own caller — the OpenMG PAC layer — or its constructor).
A harness that wants genuine pairs must drive *that* layer (or capture
it), not the formatter.

## Model update vs Session 58

S58's M1 ("ID pair is sealed/MACed key-layer output minted somewhere in
the authoring workflow") survives but is now precisely located: the
formatter layer contributes **no** key material and **no** transform —
the "key layer" is whatever CDWalkman consults. The ICV's dependence
on the audio-file size vector at the call site hints the ICV may be a
genuine content function (of sizes at least) computed by the vtable
object, while the DiscID behaves like session/installation state
carried in the CDWalkman object. Both remain hypotheses until
CDWalkman is opened. (Labelled as inference — the bounded CDWalkman
pass shows data flow, not the vtable method's internals.)

## Ranked next step

1. **Dissect CDWalkman.dll** (Ghidra, same recipe as this session).
   Anchors: the CreateCDRFormatFiles call site VA 0x60419562 and its
   containing function; identify (a) the object in `ebx` and its
   vtable+0x30 method — the ICV computation, its inputs and any key
   material; (b) every writer of the session object's +0x204 DiscID
   member (constructor, exported setters, or PAC-layer callers).
   CDWalkman imports 84 CDRFormatter symbols; its own export list will
   show what the layer above (PAC/OpenMG components such as
   PacPmItemAdapter.dll / OmgApDeliveryManagerComp.dll, or Omgjbox via
   an intermediary) calls into it.
2. Only if the DiscID writer turns out to live above CDWalkman, follow
   into that component next; the formatter side is closed.

## Artefacts in this directory

- `decomp-cdrformatter.c` — full Ghidra decompilation (2,080 functions).
- `xrefs.txt`, `xrefs2.txt`, `xrefs3.txt` — Ghidra xref dumps.
- `DecompileAll.java`, `Xrefs.java`, `Xrefs2.java`, `Xrefs3.java` — the
  headless scripts used. `CDRFormatter.dll` — the analysed copy.
- `ghidra-proj/` — the saved Ghidra project (reusable with -process).
