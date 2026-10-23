# Stage-0 readout #6 — static triage of the Sony binaries (2026-10-21)

Method: pefile PE dump (imports/exports/sections) + `strings` ASCII and
UTF-16LE sweeps + a raw-byte scan for standard crypto constant tables.
Nothing was executed. All five binaries are OpenMG **5.0.00.11280**,
built 2007-11-28 (PDB paths `e:\DailyBuild\5_0_00_200711280\OpenMG\
src\omg\exe\Release\*.pdb`), MSVC 7.1 (MSVCR71/MSVCP71), 32-bit x86.
The four COM DLLs carry embedded type libraries, ATL registration
scripts, and Sony's `.orpc` section.

**Headline result: none of the five binaries contains the disc
encryption.** No advapi32 `Crypt*` / bcrypt imports anywhere, no
AES/DES/Blowfish/SHA/MD5 names in any string table, and no standard
crypto constant tables in the raw bytes (the scan does not even find
a CRC32 table). The cipher lives behind Sony's secure-module layer —
details and evidence in the closing assessment.

---

## 1. CDRFormatter.dll (360,448 B) — the layout writer. CONFIRMED, plus the secure-header anatomy

A plain (non-COM) C++ DLL exporting 195 functions from five classes:

- **CCDRFormatter** — the formatter/burner itself. Key exports
  (demangled): `CreateCDRFormatFiles`, `AddTrack`, `AddGroup`,
  `AddPlayList`, `BeginToCreateTrack(path, CFringe*, CAudioHeader*,
  CSecureAudioHeader* out, …)`, `SendAudioBlock(byte*, len)`,
  `EndToCreateTrack`, `Burn`, `BurnFile`, `FlushContents`,
  `GetDiscID(byte*)`, `GetICV(byte*)`, `CheckEKBVersion(path, id,
  int*)`, `GetEKBFile(path, id, wchar_t** out)`, `ReadAudioDataFile`,
  and a per-file size/version getter family that enumerates the
  whole disc layout by name: TrackNameDatabaseFile,
  AlbumNameDatabaseFile, ArtistNameDatabaseFile,
  GroupNameDatabaseFile, PlayListNameDatabaseFile, TrackIndexFile,
  PlayListFile, EKBFile, AudioDataFile.
- **CFringe** — per-track metadata ("fringe"): title/artist/album
  names with a `CharCode` (the UTF-16BE text in the NDBs).
- **CGroup / CPlayList** — name + track-id list; these generate
  GROUP.NDB / PLLIST.NDB.
- **CAudioHeader** — codec descriptor: `GetCodecID`,
  `GetCodecInfoForAtrac3(CodecMode*, Emphasis*, SamplingFreq*,
  FrameLength*)`, `GetCodecInfoForAtracX(SamplingFreq*,
  ChannelConfig*, FrameLengthIndex*)`, duration / total sound
  frames. The ATRAC3 vs ATRAC3+ ("AtracX") split and the
  FrameLength enums are where bitrate/frame-size tables resolve —
  in code, not in strings; no named constant table was found.
- **CSecureAudioHeader** — the plaintext header that precedes the
  encrypted payload in every .ATP (readout #1's
  `01 00 28 2e 00 00 0b 5f …`). Its complete field set, from the
  ctor `CSecureAudioHeader(uint, const byte* ×5)` and
  `SetSecureAudioHeader(uint, BlockID, const byte* ×5)` plus the
  getters/setters: **EKBVersion (uint), BlockID (enum), BlockSeed,
  Connum, MgCk, MgDUpper, MgDLower, InitVector** — five byte-array
  fields. This is the standard OpenMG secure-audio header; the
  formatter assembles and carries it but does not compute it.

Format strings prove the writer's file map (all present verbatim):
`\HIFI\TRK0%04X.ATP`, `\TRACK.NDB`, `\ALBUM.NDB`, `\ARTIST.NDB`,
`\GROUP.NDB`, `\PLLIST.NDB`, `\TOC00000.STI`, `\TOC00001.STI`,
`\????????.STK`, and the magics `NDB `, `TOC `, `PLF ` as string
constants — matching the cracked disc layout exactly.

Internals: classes CDRDriveManager / CDRFormatManager (the log
strings `<CDRDriveManager::Burn> CdrDataWriter::AddFile( %c )
Failed [0x%08X]` etc. are this DLL talking to the Primo
CdrDataWriter beneath it); temp dir `CdWalkman\Temp\`; log format
`** [%04d/%02d/%02d %02d:%02d:%02d] %s` (the CDRFormatter.log format
from readout #5). Registry: reads `SOFTWARE\Sony Corporation\
OpenMG` (value `Repository`) and the PD plug-in key
`Software\Sony Corporation\OpenMG\PD\{CB23CD64-FDE3-4AC8-BA08-
3E4457AAF50A}` ("OpenMG-ATRAC-CD-PD-Plug-in"). It instantiates COM
objects by CLSID string (ole32 CoCreateInstance + CLSIDFromString)
and **dynamically LoadLibrary's `OMGUtils.dll` to resolve the
entry point `omgutil9`** (log strings `LoadLibrary: %d`,
`GetProcAddress: %d` sit beside both names in .rdata).
ADVAPI32 use is registry-only. No crypto imports, no crypto
constants.

## 2. omgatpcd.dll (57,344 B) — the ATRAC-CD manager: EKB registry owner, "bind" operation

ATL COM server, one class: **OmgAtpcdMan Class**, ProgID
`Omgatpcd.OmgAtpcdMan.1`, CLSID
{4315938A-643E-495C-8675-30A3D54AF90D}, interface **IOmgAtpcdMan**.
Exports are only the four COM entry points; all function is behind
the interface.

Load-bearing strings:

- `ATPCDEKB`, `ATPCDEKB_V%d`, and the concrete value names
  **`ATPCDEKB_V21`** and **`ATPCDEKB_V65550`**. 65550 = 0x0001000E —
  **the disc's 0001000E.STK EKB id**. So the ATRAC-CD EKB is held
  as registry data under the OpenMG keys (there is no shipped
  `0001000E.ekb` file in OpenMG\ekb — checked), versioned by the
  same id that lands in the .STK filename and inside the .STK at
  offset 0x20. CDRFormatter's CheckEKBVersion/GetEKBFile are the
  read side of this.
- `ATPCD::BIND_CONTENT: 0x` — the operation that "binds" content
  (OpenMG-speak for the encrypt-and-attach-rights step) is named
  here. This DLL references its sibling module `atpcd.ocm` by name.
- Error string: `bad ATP media info file`.

Imports tell the delegation story: from **OMGUtils.dll** —
`Atp::getId3TagSize`, `Atp::SecureAudioHeader::setEkbVersion`,
`OmgMmap`, `omgResolveRepositoryFile`, OmgString file IO; from
**pfcom.DLL** — `procfile`; from **salwrap.dll** — `salwrap0`,
`salwrap1`. salwrap/pfcom are the bridge into the OpenMG secure
modules (.ocm). No crypto APIs, no crypto constants.

## 3. OpcKdr.dll (1,253,376 B) — CORRECTION to readout #4: KDRM *client*, not the key core

Readout #4 called this the "KDRM/key core" from its name and size.
Statically it is two things:

1. **A bundled media framework**: 2,583 of its 2,588 exports are
   the `mpf` namespace — a full H.264/AVC decoder (CABAC context
   tables, macroblock code), MPEG stream types, DirectDraw/
   DirectSound playback, `CreateVideoDecoder`. This bulk is why
   the file is 1.25 MB; it serves the KDR *player/converter*
   classes, not key management.
2. **The KDR-format COM component**: classes **OmgPcKdr**
   {AC714C2E-C3F2-4311-B6AD-D58F1E7795A5}, **OpcKdrConverter**,
   **OpcKdrFactory**, **OpcKdrItemList**, **OpcKdrPlayer**
   (ProgIDs `OpcKdr.*.1`); type-library interfaces **IOmgKdrm**,
   **IOmgKdrFile**, **IOmgKdrToOma**, **IOmgPcKdr**,
   IOmgPcKdrMigrate, IOmgKmfFringeEdit; internal class CKdrFringe.

Its own error strings name the crypto-adjacent methods — and show
they are *someone else's* implementations:
`IOmgKdrFile::decryptContent() fail %08X`,
**`IOmgKdrm::getDecryptorProcs() fail 0x%08X`**,
`IOmgKdrm::updateMetaDataMac() fail 0x%08X` (a MAC over metadata).
Even here: ADVAPI32 imports are registry-only, and the constant
scan finds no cipher tables. The KDRM interface *obtains decryptor
procedure tables* — from the secure layer (kdrm.ocm / kdrmcom.dll)
— rather than containing them. KDR is also a sibling format
(Sony's download format, convertible to OMA via IOmgKdrToOma), not
the ATRAC-CD path itself; its value to this project is as a
worked example of the architecture, and its `CKdrFringe` parallels
the ATP fringe.

## 4. OpcAtp.dll (69,632 B) — the PC-side .ATP format object (metadata, not crypto)

ATL COM server: **OmgPcAtp Class** {93F9EDDB-8F8A-4FD8-801C-
6BF3DB817EFF}, ProgID `OpcAtp.OmgPcAtp.1`; interfaces
**IOmgPcAtp**, **IOmgPcFile**, **IOmgPcObject**; type
`_OPC_FORMATINFO` and method `GetFormatInfo`. Member-name strings:
`m_FormatName`, `m_FormatId`, `m_checkOutRemain`,
`m_fringe_coverArt` — i.e. it describes an ATP file's format id,
checkout counter and fringe/cover art. It does no format work
itself: error strings `COmgPcAtp: OmgATPFormatChecker
CoCreateInstance fail %08X` and `COmgPcAtp: OmgPcATPFringe
CoCreateInstance fail %08X` show it delegating to AtpFringe.dll's
two classes. Also checks the OpenMG version via OmgSysInfo
(`spOmgSysInfo->getOmgVersion(&nOmgVersion) is failed %x`).
Registry + COM plumbing only; no file-format strings, no crypto.

## 5. AtpFringe.dll (69,632 B) — the .ATP fringe reader / format checker

ATL COM server with two classes: **OmgPcATPFringe Class**
{8DE9B44D-4FBB-456B-8AC9-14927DE552D6} and **OmgATPFormatChecker
Class** {927907A6-7387-48AC-B718-82A0407C38D9}; interfaces
**IOmgPcATPFringe**, **IOmgATPFormatChecker**; entry point name
`CheckATPFormat` (this is the `WhetherAtpFileOrNot` check the
CdWalkman.log showed failing with OpdFormatIncompatible in
readout #5). It imports 26 functions from **CDRFormatter.dll** —
CFringe name getters, CAudioHeader codec info, and
CSecureAudioHeader's `GetConnum`, `GetMgDUpper`, `GetMgDLower` —
i.e. it *reads and validates* the fringe + secure header of an
existing .ATP (members `m_checkOutRemain`, `m_formatId`,
`m_fringe_coverArt`). A verifier, not an encryptor: no crypto
imports or constants.

---

## Supporting evidence outside the five binaries

- The OpenMG folder's **.ocm files are not PE binaries** (`file`:
  "data") — they are Sony's encrypted secure-module blobs, loaded
  and decrypted at runtime by the SAL layer (salwrap.dll /
  pfcom `procfile` / kdrmcom.dll). Names on point: `atpcd.ocm`
  (21,564 B), `kdrm.ocm` (56,285 B), `ekbman.ocm` (13,278 B —
  EKB manager), `icv.ocm` (the ICV that CDRFormatter's GetICV
  returns), `hdwm_gpd_bind_ent.ocm` (another "bind").
- **.STK vs shipped .ekb**: the shipped `OpenMG\ekb\*.ekb` files
  open with their EKB id as a big-endian uint32 (00 01 00 01,
  00 01 00 02, 00 01 00 0A, 00 00 00 02) followed by length/offset
  record streams (a repeated record shape at offset 0x20 ending
  `…a4 92 48 03` / `…a4 92 49 1c`). The disc's 0001000E.STK is
  the same record family wrapped in an `EKB ` header: magic at 0,
  the id 0x0001000E at 0x20, matching record bytes at 0x40
  (`00 00 00 0c 00 00 00 20 00 00 00 34 c9 24 92 04`), plus
  disc-specific high-entropy blobs (offsets 0x38, 0x58, 0x80…)
  that no shipped .ekb contains. So the .STK is *generated* at
  burn time from the registry-held ATPCD EKB (V65550) plus
  per-disc key material — consistent with CDRFormatter's
  GetSizeOfEKBFile/GetEKBFile treating it as a formatter output.
- OMGUtils.dll is the hub every component converges on:
  CDRFormatter LoadLibrary's it for `omgutil9`; omgatpcd imports
  its `Atp::` helpers; OpcKdr imports its COM allocator. Its
  "Repository" (registry-configured) is where the .ocm modules
  and EKB data are resolved from.

## Closing assessment — where the encryption most likely lives

**In the .ocm secure modules, reached through the SAL — most
probably `atpcd.ocm` for the ATRAC-CD bind/encrypt operation,
with `ekbman.ocm` handling EKB processing and `kdrm.ocm` as the
sibling on the KDR side.** The five PE binaries are orchestration
and metadata only:

1. CDRFormatter *assembles* the disc — it writes every file,
  carries the CSecureAudioHeader fields (BlockSeed, Connum,
  MgCk, MgD, InitVector, EKBVersion), and burns via Primo — but
  contains no cipher and receives the header values from its
  caller (BeginToCreateTrack takes a CSecureAudioHeader*).
2. omgatpcd *owns the ATPCD EKB* (registry `ATPCDEKB_V65550` =
  the disc's EKB id) and names the operation (`ATPCD::
  BIND_CONTENT`), but its imports route all secure work through
  OMGUtils + salwrap + pfcom into `atpcd.ocm`.
3. OpcKdr proves the pattern from the KDR side: even the DLL
  literally named for the DRM only *requests* `getDecryptorProcs()`
  — the decryptor implementations are external procedure tables.
4. OpcAtp / AtpFringe only describe, read and validate ATP
  fringes and headers.

Implication for the next stage: Ghidra time on CDRFormatter.dll
remains the right spend for the *layout* writers (NDB/STI
semantics), but the encryption question will not be answered
inside these five binaries. The productive targets are
(a) OMGUtils.dll + salwrap.dll + kdrmcom.dll — the .ocm
loader/decryptor path; (b) the registry-side `ATPCDEKB_V65550`
data itself; and (c) black-box work on the disc corpus — the
.STK record format is already visibly kin to the shipped .ekb
files, and the .ATP secure header is fully enumerated above, so
known-plaintext comparison between a library .OMA and its burned
.ATP counterpart can characterize the cipher's block structure
without the .ocm layer ever being opened.
