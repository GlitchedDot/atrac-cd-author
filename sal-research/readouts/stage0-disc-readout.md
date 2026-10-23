# Stage-0 disc readout #1 — from Lola's sample files (2026-10-21)

Source: `CD_stuff.zip` from Lola — a subset of one of her SonicStage-burned
ATRAC3+ CDs (5 audio files + all the small control files). Not the full disc;
enough to identify every file role and the protection shape.

## File inventory and roles

| File | Size | Role (evidence) |
|---|---|---|
| `HIFI/TRK0000A.ATP`, `TRK000A0`–`A3.ATP` | 1,095,656 / 4× 1,296,064 B | Audio tracks. ID3v2.4 tag (exactly 1,024 B: TIT2/TPE1/TALB, UTF-16) + payload. |
| `TRACK.NDB`, `ALBUM.NDB`, `ARTIST.NDB` | 63,360 B each | "NDB " magic databases, fixed-size records, UTF-16 names. All three the same allocated size. |
| `GROUP.NDB` | 384 B | Group database; contains "New Group" (UTF-16) at 0x100. |
| `PLLIST.NDB` | 256 B | Playlist database, same NDB format, empty here. |
| `TOC00000.STI` | 10,192 B | Starts "TOC " v1 — table of contents data. |
| `TOC00001.STI` | 2,176 B | Starts "PLF " v1 — playlist file. |
| `0001000E.STK` | 172 B | Starts "EKB " — key block (see below). |

Track naming: `HIFI/TRK` + 4 hex digits + a letter. The four identical
1,296,064-byte files suggest equal-length (or padded) encodes.

## The big finding: the audio is encrypted

- Byte entropy of the .ATP payload (after the 1,024-byte ID3 tag) is
  **8.000 bits/byte** in both files sampled — statistically pure noise,
  i.e. encrypted, not merely encoded. ffprobe rejects the files outright.
- The payload opens with a short plaintext header (`01 00 28 2e 00 00 0b 5f …`)
  before the noise begins — an OMG-style content header.
- `0001000E.STK` is the key material: "EKB " magic, a count (0x000E), then
  high-entropy blobs. EKB = the OpenMG key-block format the MiniDisc
  community (linux-minidisc) has partially documented for NetMD/Hi-MD.

**Consequence for the app:** authoring D-NE1-playable discs needs three
reproductions, not two: (1) the disc layout (NDB/STI/STK writers —
fixed-record formats, very tractable), (2) ATRAC3+ encoding (atracdenc —
round-trip already proven), and (3) **the OpenMG disc encryption + EKB
construction** — now the main RE unknown. Running start: the NetMD EKB
literature, these sample files as ground truth, and SonicStage's own
DLLs (still to come from Lola) in Ghidra.

## Still open after readout #1

- Codec flavor/bitrate of her burns (the plaintext header fields + her
  stated burn bitrate will pin it; the ID3 tags carry no bitrate frame).
- Whether a full-disc sample shows more file types (this was a subset).
- The D-NE1 acceptance test still decides everything, later, on hardware.

## Readout #2 — NDB structure + this disc's true size (2026-10-21, later)

From Lola's Finder photo of the full `HIFI` folder plus a record scan of
the NDBs she already sent:

- The photo shows a wall of `.ATP` files and nothing else — HIFI holds
  audio only, named by a strict counter pattern (`TRK0000A`, `TRK000A0`,
  `TRK000A1`, ...; exact rule to come from the TOC parse).
- **TRACK.NDB decoded:** 256-byte header ("NDB " + version + record
  count as big-endian field) followed by **128-byte fixed records**.
  Header count = 0x01ED = **493 tracks**; 256 + 493×128 = 63,360 =
  the exact file size. This sample disc is a FULL 64 kbps burn
  (493 tracks ≈ 610 MB of audio).
- Track titles are stored in the records as **UTF-16BE** strings in
  "ARTIST - TITLE | ..." form. TOC00000.STI's header carries the same
  0x01ED count. GROUP.NDB = 1 group ("New Group", also UTF-16BE).
- The NDB writer is therefore fully specified in shape already:
  fixed header + fixed records. Remaining layout unknowns are field
  semantics, which the .STI TOC + SonicStage DLLs will pin down.
