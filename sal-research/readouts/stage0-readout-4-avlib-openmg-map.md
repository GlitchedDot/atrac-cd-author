# Stage-0 readout #4 — AVLib/OpenMG map + binary triage (2026-10-21)

Sources: `sony-listing (2).txt` (Common Files\Sony Shared + Packages)
and the four binaries Lola sent in Archive.zip (sizes verified
byte-exact against the first listing).

## Where the ATRAC CD machine actually lives

**`Common Files\Sony Shared\AVLib\`** — the authoring layer:
- `CDRFormatter.dll` (360,448) — the disc formatter/layout writer.
  A `CDRFormatter.log` (22,373 B) sits in `AVLib\CdWalkman\` — a log
  from real burns on her machine; wanted.
- `CDWalkman.dll` (229,376) + `CdWalkman.log` (7,596) — CD Walkman
  component + its log; wanted.
- `OpcAtp.dll` (69,632), `AtpFringe.dll` (69,632) — the .ATP layer and
  its "fringe" (header/tag wrapper; cf. EA3FringeLib.dll, OmgEA3Frng).
- `OpcCd.dll` (94,208), `OpcCd2.dll` (131,072), `id3parser.dll`
  (135,168) — CD components + the ID3 writer for the .ATP tags.
- `CdrSS\` — the burn engine: `SonyCDWriterSS.dll`, `CdrHelperSS.dll`,
  `OpdCdrSS.dll`, `PrimoWriterSS.dll` + `primosdk.DLL` (Primo SDK).

**`Common Files\Sony Shared\OpenMG\`** — the protection layer:
- `omgatpcd.dll` (57,344) — OpenMG ATP-CD component. Top priority.
- `atpcd.ocm` (21,564), `ekbman.ocm` (13,278) — ATP-CD module, EKB mgr.
- `kdrm.ocm` (56,285), `kdrmcom.dll` (159,744), `OpcKdr.dll`
  (1,253,376) — the KDRM/key core.
- `ekb\` — REAL EKB data files: `00000002.ekb`, `00010001.ekb` (684 B),
  `00010002.ekb`, `0001000A.ekb`, plus per-device .EKB files and
  `ekb\kdrm\kdrm-rl-016B40800000.dat`. The disc's `0001000E.STK` is
  this family's on-disc form. All tiny; wanted as reference key data.
- `OMGKEY\omg_id.dat` (22 B), `OMGRIGHT\*.ICV` — install key material.

## Triage of the four binaries in hand

- `Omgjbox.exe`: ATRAC CD orchestration only (classes
  `CDlgCdrAtracConf`, `CSiItemSourceManagerPdATRACCD`, `*.atp`
  handling). No format internals — the DLLs do the work.
- `GenMediaKey.dll`: no informative strings; small — Ghidra later.
- `SsBeSvc.exe` / `SSSsiSV.exe`: generic service scaffolding;
  deprioritized (the SCSI service is a passthrough).

## Side note (parked thread, not this project)

`ProgramData\SonicStage\Packages` verified EMPTY in both listings —
the library DB is not there on this install as it currently stands.
That belongs to the paused Toshiba crash thread; noted, not chased.

## Batch-2 send list (given to Lola 2026-10-21)

One zip, all small: CDRFormatter.dll, CDWalkman.dll, OpcAtp.dll,
AtpFringe.dll, OpcCd.dll, OpcCd2.dll, id3parser.dll (AVLib);
SonyCDWriterSS.dll, CdrHelperSS.dll, OpdCdrSS.dll (CdrSS);
omgatpcd.dll, atpcd.ocm, ekbman.ocm, kdrm.ocm, kdrmcom.dll,
OpcKdr.dll (OpenMG); the whole OpenMG\ekb folder + OMGKEY\omg_id.dat;
CDRFormatter.log + CdWalkman.log (AVLib\CdWalkman).
