# Stage-0 readout #9 — the .ocm secure-module format: recon (2026-10-21)

Static analysis only; nothing was executed. All files from the Sony
Shared tree at ~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG/.

## Verdict up front

**.ocm files are not packed PE code. They are encrypted SAL
bytecode modules** — SAL = Sony's Secure Application Layer, a custom
bytecode VM whose interpreter/runtime is `salwrap.dll`. The ATRAC-CD
cipher and the EKB logic therefore live in *bytecode* inside
atpcd.ocm / ekbman.ocm, behind a hand-rolled encryption layer in
salwrap. This is the hardest of the possible shapes — but the format
skeleton is now mapped, and the module family hands us a large
known-plaintext anchor (below).

## 1. Inventory

61 `.ocm` files in OpenMG\. Eleven are 2-byte stubs containing only
`FF FF` (keyinfo, mp3toomg, nwwm, omgtopcm, otk_*, querypf, wm) —
placeholders for absent/disabled modules. The other 50 are real
modules, 8.5 KB–64 KB, except `init.ocm` at 582,636 B (the SAL
bootstrap). All real modules are dated 2007-11-28 (OpenMG build
5.0.00.11280), except the `*_key.ocm` / `*-dnk.ocm` key containers
(2005/2007, see §3).

## 2. Container format (byte level)

Every real module starts with the same 10-byte plaintext header:

| Offset | Bytes | Meaning (evidence) |
|---|---|---|
| 0 | `03` | format marker/version — constant in all 50 modules and in device.sal |
| 1 | `01` or `02` | module class — splits the family in two (25 vs 26 modules) |
| 2–3 | `00 00` | constant |
| 4–5 | `05 00` LE | **5** — matches the OpenMG major version |
| 6–9 | `10 2C 00 00` LE = **11280** | **the OpenMG build number** (5.0.00.11280, the PDB stamp found in readout #6) |

After the header the body is at full entropy (7.99 bits/byte overall
and in every 2 KB window; ~0.4% zero bytes = chance). There are **no
plaintext strings anywhere** in any module, no low-entropy region
after byte 10, and file sizes are unaligned (kdrm.ocm is an odd
56,285 bytes; (size−10) mod 8/16 is inconsistent across modules) —
so the body is not one padded block-cipher stream; it is segmented/
chunked, consistent with the relocation structure the loader names
(§4).

## 3. Two families, one shared chunk pool

**Class 0x01 (25 modules** — icv, Omgtomp3, the *toomg/*topcm
converters, netmd, mgsoft, …): **all 25 share their first 8,221
bytes byte-for-byte** — header plus an identical ~8.2 KB encrypted
block — then diverge. The smallest members (omgtopcm2.ocm 9,261 B,
restore.ocm 9,149 B) are little more than this common block plus a
short unique tail. Two near-duplicates (at3toomg/at3topcm, both
23,609 B) differ only in their last ~32 bytes.

**Class 0x02 (26 modules** — atpcd, ekbman, kdrm, importer, l3, sc,
mss, umd, …): most diverge from each other immediately after the
10-byte header, but pairwise sharing is extensive — atpcd.ocm and
lgd.ocm share their first 8,481 bytes; init2.ocm and region.ocm
share ≥32. So class-02 modules are also assembled from shared
chunks, just with less uniform leading content.

Interpretation: modules are concatenations of encrypted chunks drawn
from a common library pool (a shared SAL runtime + shared library
routines), encrypted deterministically enough that identical chunks
produce identical ciphertext across modules. **The class-01 family's
8,221-byte common preamble is a gift: a long known-ciphertext anchor
present in 25 modules** — any candidate decryption can be validated
against it (the plaintext must come out as identical, well-formed
SAL bytecode in every module).

**Key-container subfamily**: `importer_key.ocm`, `ktunes_key.ocm`
(8,550 B each) and `bot-dnk.ocm`, `hdd-dnk.ocm`, `umd-dnk.ocm`
(9,062 B), `msa-dnk.ocm` (8,895 B) carry a variant header — u16@4 =
**1** (not 5) and u32@6 = **0** (no build stamp) — and diverge from
byte 4. These are the DNK ("device node key"?) containers; see the
ECC error string in §4.

**init.ocm** is its own thing: a 5-byte prefix (`04 83 08 47 50`),
then exactly one module header at offset 5, and no further module
headers anywhere in its 582 KB — a monolithic bootstrap module, not
a concatenation of the others.

**device.sal link**: `device.sal` (15,085 B, a SAL data file the
loader "imports" and verifies) has header `03 01 00 01 …` and at
offset 10 carries the same blob family as the class-01 preamble
(`01 01 04 08 6A 35 A2 1D 8C 3C 2C 0C 7E …`, shared for 13 bytes) —
the .sal and .ocm formats are the same container family.

## 4. The loader path (salwrap.dll and friends)

- **salwrap.dll** (307,200 B) is the SAL runtime. It exports exactly
  three functions — `salwrap0`, `salwrap1`, `salwrap2` — and
  contains the VM's own vocabulary in its strings:
  `SalBytecode::dataType(): buffer is empty`, `bad SalAsnSeqEnd`
  (an ASN.1-ish structure layer), `SalMemory`, `SalMemorySize`,
  `[%d] module<%s> has unknown reloc.type(%d)` (**modules carry
  relocations**), and exec-profiling strings `salexec: %s: %d msec`.
  It imports VirtualProtect/VirtualQueryEx (it manages executable
  memory), LoadLibraryA/GetProcAddress, and 33 functions from
  OMGUtils.dll including `omgResolveRepositoryFile`,
  `omgGetRepository`, `OmgMmap`, and `omgGetResourceData`.
- salwrap bootstraps core modules **by name** — its string table
  embeds: init.ocm, init2.ocm, icv.ocm, ekbman.ocm, kdrm.ocm,
  region.ocm, l3.ocm, maclist.ocm, mp4comp.ocm, botamoti.ocm — and
  the EKB file list itself: `*.ekb`, `/*.EKB`, `/newekb*.txt`, and
  every shipped .ekb filename. (atpcd.ocm is *not* in salwrap's
  bootstrap list; omgatpcd.dll names it — the ATPCD module is loaded
  on demand by the ATRAC-CD component.)
- **Embedded resource**: salwrap.dll carries a resource of custom
  type `SALWRAP`, name `NEWEKB_TXT` (128 B). Extracted: it is a
  plain-text CRLF list of the eight current .ekb filenames — an
  update manifest, not key material.
- **Keys**: salwrap references `OMGKEY/omg_sal.dat` (a SAL key file
  — **absent from this install**; OMGKEY holds only omg_id.dat) and
  `procfile/device.sal`. The EMDKEY folder holds ECC key pairs:
  `EMDKEY/001/{cert.dat, priv.dat}` (and siblings). The decisive
  string: **`ERR_SML_DNK_PRIV_ECC_DECRYPT`** — DNK private keys are
  used for **ECC decryption** somewhere in the SAL module layer
  (likely unwrapping module/EKB keys). Other error names:
  `ERR_LYR_SAL`, `ERR_SML_SINF_CONV_TSAL`, `ERR_SML_SINF_TSAL_VERSION`.
- **kdrmcom.dll / pfcom.dll** are COM plumbing: they import
  `salwrap0/1` and OMGUtils' `KdrFileRw` (the KDR file reader) and
  `parseOmgFile` — they feed files/content into the SAL layer; they
  contain no module decryption themselves.
- **Crypto in the loaders**: OMGUtils.dll implements SHA-1 (the
  `OmgSha` class; LE SHA-1 constants found) — the SINF/integrity
  hash. **No AES/DES/ECC constant tables were found in salwrap,
  kdrmcom, pfcom, or omgatpcd by raw scan, and no loader imports
  CryptoAPI/bcrypt for decryption** (ADVAPI32 usage is registry-only
  everywhere). The module cipher is therefore hand-rolled inside
  salwrap.dll and/or executed as SAL bytecode from init.ocm —
  constants may be computed at runtime rather than stored.

## 5. Known vs unknown

Known: the container skeleton (header fields, two classes, chunk
pool, key-container variant); where execution lives (salwrap VM);
the key-ecosystem shape (DNK ECC private keys, omg_sal.dat, EMDKEY
pairs, EKB file list); that the ATPCD cipher itself is SAL bytecode
inside atpcd.ocm, with ekbman.ocm as the EKB manager module.

Unknown: the module encryption algorithm and key derivation; the
SAL bytecode ISA (opcode map, the ASN.1-ish framing, relocation
semantics); whether the class-01 preamble decrypts under the same
key as class-02 bodies; what omg_sal.dat contained.

**On prior art**: this recon found no evidence — in the files or in
anything I can verify from them — of a public .ocm decrypter or a
published SAL bytecode specification. Any claim that one exists
should be treated as unverified until produced. Budget for this as
original reverse engineering.

## 6. Attack plan (next phase, in order)

1. **Ghidra on salwrap.dll first** — it is a normal PE and the only
   place the decrypt routine can live in native code. Start from
   the three exports, follow the module-load path: header parse
   (the 10-byte header gives the foothold — find the code that reads
   version 5 / build 11280), the repository-file open, then the
   chunk transform. Hand-rolled cipher tells: tight XOR/rotate
   loops, runtime-built S-boxes, SHA-1 (OmgSha) in key derivation.
2. **Use the class-01 preamble as the validation oracle**: the
   first candidate decrypt gets tested against the 8,221-byte block
   shared by 25 modules — correct decryption must yield identical,
   structured bytecode from all of them; the `01 01 04 08 6A 35…`
   blob that also appears in device.sal is a second anchor.
3. Map the chunk structure while decrypting: chunk boundaries
   should explain the unaligned file sizes, the relocation error
   string, and the pairwise chunk-sharing between class-02 modules
   (decrypted chunks should recur across modules in plaintext too).
4. Only then: **atpcd.ocm** — decrypt, then face the second project
   inside the first: a SAL bytecode disassembler (opcode map from
   salwrap's SalBytecode interpreter loop — the VM's dispatch table
   in salwrap *is* the ISA specification).
5. Noted but out of scope for the static phase: salwrap has an exec
   logging switch (`EnableSalExecLogging`, `logSalMessage`) that a
   dynamic run on the Toshiba could exploit — that means running
   the Sony stack, a separate decision for Lola, not a VM-side step.

Difficulty, honestly: the container layer looks like *days* of
Ghidra work, not weeks; the SAL bytecode layer after it is the real
unknown and could be substantially larger. But the encryption gate
is now a named target with a validation oracle, not a mystery.
