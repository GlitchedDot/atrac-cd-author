# Session 60 — CDWalkman.dll: the ICV computation + DiscID provenance (desk-only, 2026-11-03)

No builds, no burns, no harness drives. Binary dissection only.
(Written incrementally; sections land as each job completes.)

## Setup / verified anchors

- Target: CDWalkman.dll, 229,376 B, MD5 935c17e1fd9fa5efe89268c6b82d8365,
  from toshiba-trees-2026-11-02/sony-shared/Sony Shared/AVLib/.
  ImageBase 0x60400000, SizeOfImage 0x38000 (.text RVA 0x1000, .rdata 0x21000,
  .data 0x2e000). It is a COM server DLL: only 4 exports
  (DllCanUnloadNow, DllGetClassObject, DllRegisterServer, DllUnregisterServer).
- S59 call-site anchor to verify: CreateCDRFormatFiles call at VA 0x60419562
  (RVA 0x19562, inside .text).

## Sizes-vector semantics (from S59's decomp-cdrformatter.c — VERIFIED firsthand)

`CCDRFormatter::GetSizesOfAllAudioDataFiles(path, CVector<uint>*)` is a thin
wrapper over worker FUN_602205d2, which:

- iterates the formatter's track-object list (36-B-stride entries),
- per track calls vtable+0x2c to get the track's **file path**,
- opens that file (CreateFileA), takes **GetFileSize** (low DWORD),
- appends the size (as uint) to the out vector.

**So the sizes vector = the on-disk byte sizes of the audio data files
(.ATP files) in track order.** Input-convention variants for the ICV test
(full file size vs payload-only size vs frame count vs sectors) are
enumerated in the Job 2 section.

## Job 1 — pin the ICV method — SOLVED

Full Ghidra decompilation produced: `decomp-cdwalkman.c` (1,241 functions,
0 failures). Anchor VERIFIED firsthand against raw disassembly:

- The 0x60419562 call sits in **FUN_60419138 = `PmCdWalkman::CommitSuperTrans`**
  (log strings in-body). `esi = [ebp+8]` is the session object (members:
  formatter @+0xec, logger @+0xe4, DiscID @+0x204 in this frame).
- The ICV call (raw asm 0x6041950f–0x6041951e): `mov eax,[ebx]; push &icv;
  push &sizes; mov ecx,ebx; call [eax+0x30]` with **`ebx = esi − 4`** (set at
  0x60419332, same for the +0x34 and +0xbc calls). So the vtable object is the
  enclosing object at (esi−4); its vptr is the object's PRIMARY vtable.
- Vtable identification: a .rdata scan for code-pointer runs found twin
  49-slot tables whose [+0x30] is a `mov eax,0x80040e07; ret 8` STUB — a false
  trail (that's a secondary, mostly-stubbed interface vtable, stored at
  obj+0xc by the ctors). Constructor stores (capstone census) show the real
  layout: **[obj+0] = vtable 0x60421d80 (71 slots)**, [obj+0xc] = the stub
  table. The [+0xbc] cross-check agrees: via the primary table +0xbc is a
  distinct sibling method (the plain Commit, FUN_60415b11) that
  CommitSuperTrans delegates to when not in super-trans state; via the stub
  table it would be CommitSuperTrans itself (infinite self-delegation —
  implausible).
- **Primary vtable 0x60421d80: slot +0x30 = FUN_60414a7a = CreateIcv**;
  slot +0x34 = FUN_6040fe74 (512 B; the EKB-name getter — consistent with its
  (version, out-string) call shape); slot +0x3c = FUN_6040a6f7 (see Job 2).

## Job 2 — extract + test the ICV algorithm — ⭐ SOLVED, VERIFIED ON ALL 3 DISCS

`CreateIcv` (FUN_60414a7a, 322 B, decompiled in full) does:

1. Copies two 8-byte halves from the object itself — `this+0x208` and
   `this+0x210` — i.e. **the DiscID** ([esi+0x204] in CommitSuperTrans's
   frame = (esi−4)+0x208 here; same 16 bytes).
2. Passes each half through vtable+0x3c with length 8. That method,
   FUN_6040a6f7 (48 B, verified against raw disassembly), is a plain
   **in-place BYTE REVERSAL** of the buffer. So each half is read as a
   big-endian u64.
3. Rolling 64-bit polynomial over the sizes vector (CVector begin/end
   iteration, track order): with A = BE64(DiscID[0:8]), B = BE64(DiscID[8:16]):
   **X ← (X · sizeᵢ + B) mod 2⁶⁴**, X₀ = A (per iteration: `__allmul(size, X)`
   then a full 64-bit add of B; the result feeds back as the next X).
4. The final X is passed through the byte-reversal once more and copied to
   the out buffer: **ICV = BE64(X_final)**.

In Python:
```python
def icv(discid: bytes, sizes: list[int]) -> bytes:
    A = int.from_bytes(discid[0:8], 'big')
    B = int.from_bytes(discid[8:16], 'big')
    X = A
    for s in sizes:
        X = (X * s + B) & 0xFFFFFFFFFFFFFFFF
    return X.to_bytes(8, 'big')
```
with `sizes` = the full on-disk .ATP file sizes in track order (the
GetSizesOfAllAudioDataFiles semantics from the S59 decomp: per track object,
CreateFileA + GetFileSize, appended in list order).

**Test against the S58 corpora (id_b = DiscID, track sizes from the
genuine extracted file sets):**

| disc | tracks | computed ICV | genuine ICV | match |
|---|---|---|---|---|
| appliance | 1 | a8fb3de83fc4b6b5 | a8fb3de83fc4b6b5 | ✅ |
| disc 1 | 493 | 1c323bbee328c1f5 | 1c323bbee328c1f5 | ✅ |
| FavoriteDisc | 432 | 914b4bf7743c7fb9 | 914b4bf7743c7fb9 | ✅ |

**Exact on all three, first variant tried — no ambiguous conventions.**
There is NO key material, no sealing, no crypto anywhere in the ICV:
it is an unkeyed DiscID-and-sizes polynomial. This retroactively explains
every test burn: the twin played (genuine pair, genuine sizes); disc 5
died (random ICV ≠ f(random DiscID, sizes)); disc 6 died (disc 1's ICV was
computed over disc 1's 493 sizes, not the clone's single size); the clone
died (fresh pair). The player evidently recomputes this function from the
disc's DiscID + actual .ATP sizes and compares.

## Job 3 — DiscID provenance

(pending)

## Job 4 — verdict

(pending)

---

## JOB 3 — DiscID provenance

### The session object and its construction

- Class **CPmCdWalkman** (COM, `CdWalkman.PmCdWalkman`, CLSID
  {9B2F7308-3420-4CEF-B7C6-253CBA9085AC}). Its ctor FUN_60401325 installs six
  vptrs and calls the base ctor **FUN_60418d62** (also called by the second
  layout ctor FUN_604016d0 — the ATL contained/aggregated twin layout; both
  share all implementations).
- The DiscID field is at **object+0x208** (triple-confirmed: base ctor zeroes
  `[this+0x208]` for 16 B; CreateIcv reads `[this+0x208]`; CommitSuperTrans
  passes `[this+0x208]` — rendered `[esi+0x204]` in its frame because that
  method is entered through an adjustor thunk, `sub [esp+4],0x10`, at
  0x604017fb via its interface subobject).
- Base ctor facts: DiscID zeroed; a "DiscID valid" flag at +0x25c starts 0;
  the CCDRFormatter pointer (+0xf0) starts 0; the IOmgAtpcdMan pointer
  (+0x38) starts 0. No RNG/time/GUID import is used anywhere in CDWalkman for
  this field (imports checked: only KERNEL32 time getters for CRT/ATL).

### Every write to +0x208 — exhaustive

Method: Ghidra xref graph for the involved functions, PLUS capstone
displacement scans over the whole `.text` for `[reg+0x1e0..0x220]` with every
plausible interface-`this` offset (member offsets 0x1f4–0x208 for subobjects
at +0x00..+0x14), PLUS a decomp-wide grep for memcpy into the member. Result
— exactly three touch classes in CDWalkman.dll:

1. **Zero-init** in the base ctor (memset helper FUN_6041d9e4).
2. **Read-back from an existing medium**: famC vtable slot 11 =
   **FUN_60412854** (no direct callers; virtual only). If the valid flag is
   clear it: ensures a formatter exists (CoCreateInstance of
   CdrFormatter.CDRFormat), calls `CCDRFormatter::GetDiscID(path@+0x270,
   &DiscID)` — the read-existing-TOC path of S59 — and on success sets the
   valid flag. This is the resume/rewrite path for a disc that already has
   an ID.
3. **Reads only**: CreateIcv; CommitSuperTrans (passes it to
   CreateCDRFormatFiles); QuickCheckOut (FUN_604169d1) and FullCheckOut
   (FUN_60417324), which pass `&DiscID` to IOmgAtpcdMan::bindContent
   (interface at +0x38, vtable+0x10) once per track.

There is **no setter method and no generator in CDWalkman.dll**.

### The fresh-disc path — the DiscID is minted by atpcd.ocm selector 0

Inside FUN_60412854 there is a second branch: if `GetDiscID` returns **1**
(the formatter's medium-info dispatch says "this medium has no stored ID" —
see GetDiscID wrapper in the S59 decomp: medium-info flag 0 → return 1),
CDWalkman calls **IOmgAtpcdMan vtable+0x0c with (&DiscID)** and, if that
succeeds and the buffer passes a readability check, adopts the buffer as the
DiscID and sets the valid flag.

This session decompiled omgatpcd.dll in full (57,344 B, MD5
2207e2bf72607dc32d2cabf6f2d0fa91; 324 functions, 0 failures;
`decomp-omgatpcd.c` in this dir). The IOmgAtpcdMan vtable is at VA
0x6160875c; slot +0x10 = FUN_6160571e, confirmed as **bindContent** (it
references the string "ATPCD::BIND_CONTENT"); therefore **slot +0x0c =
FUN_616054cd** — the harness campaign's **"OP-A"**:

- Sole argument: a pointer to a 16-byte buffer. It builds a SAL stream —
  session record, int **0** (the selector), module "atpcd.ocm", and a
  buffer-reference element {ptr, 0x10} — executes it via salwrap, and reads
  back: a status byte, **16 bytes INTO the caller's buffer**, and two
  strings. It then resolves the type-4 repository file named by those 16
  bytes (omgResolveRepositoryFile(...,4,ptr) + omgMkdirHier) and writes
  string #2 into it (the repository/key-blob record for the new ID).
- **Empirical (harness campaign, runs 125/126 — from
  `~/workspace/atrac-salwrap-work/unicorn/SESSION-2026-10-28.md`):** OP-A
  executed live returned a **fresh** 16-byte value each run
  (run 125: `97 d2 b0 b4 02 73 18 bb 1f 8d 49 23 09 e4 20 0e`;
  run 126: `49 b2 ec 33 fc 69 28 b6 59 ee b8 fd c4 59 df 98`) — "OP-A
  mints fresh key material per run."

**So the fresh-burn DiscID is minted inside the OpenMG SAL ceremony by
atpcd.ocm selector 0**, written back into CPmCdWalkman's member, and only
then consumed by bindContent, CreateIcv and CreateCDRFormatFiles. The
minting is ceremony-side fresh randomness (the OMG_RAND_SEED world of
S35/S58): not a function of the disc's contents, and — consistent with S58's
30,665-construction negative battery — not derivable from disc-side data.

### Caller chain of CommitSuperTrans (0x60419562's function)

FUN_60419138 is reached only virtually: famB-interface slot +0xbc (via the
adjustor thunk at 0x604017fb) — i.e. the PAC-layer host calls it through the
COM interface. CDWalkman.dll is a pure COM server (4 exports); its host in a
real install is the app layer (Omgjbox.exe — **not in the held corpus**;
S59's boundary stands). The chain inside held code is:

    app/PAC host (not held)
      → CPmCdWalkman slot-11 refresh (FUN_60412854)
          → CDRFormatter::GetDiscID  (existing disc: adopt its DiscID)
          → or IOmgAtpcdMan+0x0c OP-A (fresh disc: atpcd.ocm sel 0 mints it)
      → Quick/FullCheckOut: IOmgAtpcdMan::bindContent per track (DiscID key)
      → CommitSuperTrans (FUN_60419138)
          → GetSizesOfAllAudioDataFiles → CreateIcv(DiscID, sizes) → ICV
          → CCDRFormatter::CreateCDRFormatFiles(path, DiscID, 0x1000E, ICV)

---

## JOB 4 — VERDICT

**The ICV is fully app-mintable.** Its algorithm is extracted from
CDWalkman.dll's CreateIcv (FUN_60414a7a) and reproduces the genuine ICV
byte-exactly on all three genuine discs (1, 493 and 432 tracks). It is an
unkeyed polynomial fold of two quantities the author already knows at
authoring time — the DiscID and the ordered .ATP file sizes. No key
material, no sealing, no ceremony, no per-install constant. Variants
(LE halves, swapped halves, alternate fold order) all fail on all three
discs; the solution is unique among them.

**The DiscID is app-CHOOSABLE as far as every held code path can tell —
with one honest unknown on the player side.** Specifically:

- Genuine DiscIDs are minted by atpcd.ocm selector 0 (OP-A) inside the
  OpenMG ceremony — fresh 16 bytes per disc, unrelated to disc contents.
  The app author cannot reproduce Sony's minting (it lives in the SAL
  ceremony), and does not need to: nothing in CDWalkman, CDRFormatter or
  omgatpcd validates a DiscID's provenance. Every consumer treats it as an
  opaque 16-byte value; the only checkable relation involving it anywhere
  in held code is the ICV fold.
- The TOC carries exactly three ID-ish quantities: ICV (8 B), DiscID
  (16 B) and the EKB version constant 0x0001000E. A bare random 16-byte
  value carries no internal structure a player could verify beyond the
  ICV relation (there is no MAC/signature field paired with it).
- **Retroactive explanation of the burn record:** the twin played because
  it carried the appliance disc's genuine (DiscID, ICV) pair over its own
  sizes; disc 5 died because random IDs broke ICV == f(DiscID, sizes);
  disc 6 died because disc 1's ICV was folded over 493 sizes, not the
  clone's one track; the clone died the same way. Every outcome is
  explained by the ICV check alone — no second DiscID validation is needed
  to explain any result so far (inference, labelled: the player's internal
  checks are not directly observable from held code).
- **What remains:** ONE decisive burn — an app disc with an arbitrary
  (app-chosen) DiscID, the ICV computed by the extracted algorithm over
  that DiscID and the disc's real .ATP sizes, and everything else as in
  the played twin. If it plays, the (ICV, DiscID) pair is fully
  app-mintable and the furniture wall is down; the payload-cipher question
  (BlockSeed sealing, S56's model) is a separate wall that this session
  does not touch. If it dies, the player validates the DiscID itself by
  some means not present in any held binary, and the hunt moves to the
  player's expectations.

### Minor labelled gaps

- The IOmgAtpcdMan pointer at +0x38 is assigned somewhere in CDWalkman
  outside the ctor (initialised 0); the assignment site was not traced —
  not load-bearing for any verdict above.
- CreateIcv consumes sizes as 64-bit multipliers; genuine files are all
  < 2^31, so sign/zero-extension of the 32-bit file size is
  indistinguishable in the test corpus.
- OP-A's internal minting inside atpcd.ocm (which SAL RNG it draws on) was
  not dissected — the harness campaign's live executions establish the
  freshness property, which is all the verdict needs.
