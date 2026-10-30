# Stage-0 readout #3 — library .OMA + Toshiba install listing (2026-10-21)

## The library file: clean 64 kbps ATRAC3+, unencrypted

Lola sent `1-07_It_s_Alright.OMA` from her SonicStage library
("It's Alright" — My Little Pony: A New Generation, track 7):

- ffprobe: **codec atrac3p (ATRAC3+), 44,100 Hz, stereo, 64,771 bps**,
  duration 193.75 s, size 1,571,840 B. Exactly her stated 64 kbps spec.
- Container: **EA3 header** ("ea3" v3) with ID3-style frames plus Sony
  `OMG_*` tags (OMG_TRACK, OMG_TIT2S, OMG_TPE1S, OMG_ALBMS, TLEN).
- Entropy 7.984 bits/byte — normal compressed-audio entropy, and the
  file **fully decodes in ffmpeg**, unlike the disc .ATP (8.000,
  unparseable). **Conclusion: library files are clean standard OMA;
  the OpenMG encryption is applied at the burn step**, when SonicStage
  wraps the stream as HIFI/*.ATP (ID3v2.4 tag instead of EA3) and
  encrypts the payload. Byte rates match across the boundary
  (64 kbps in ≈ 64 kbps on disc) — consistent with a length-preserving
  cipher.
- atracdenc's output container (EA3 + atrac3p .oma) is therefore
  format-compatible with the library side today; only its fixed
  352.8 kbps rate differs from her 64 kbps.

## The Toshiba listing: app folder captured, core lives elsewhere

From `sony-listing.txt` (SonicStage 4.3, `C:\Program Files (x86)\Sony\`):

- Present and wanted for Ghidra: `Omgjbox.exe` (5,961,272 B — the app),
  `GenMediaKey.dll` (45,056 B — key generation, name says it),
  and from the installer module cache `AVLib\SsBeSvc.exe` (112,184 B)
  + `SSSsiSV.exe` (75,320 B — the SCSI/disc-writing services).
  Everything else in the app folder is UI/utilities/encoders for MP3/WMA.
- **Not in this listing:** the OpenMG core + ATRAC codec DLLs. For
  SonicStage 4.3 those live under `C:\Program Files (x86)\Common
  Files\Sony Shared\` — the first listing command didn't include that
  tree (asker's omission). Second listing requested for exactly
  `Common Files\Sony Shared` (+ the plain `Program Files` variant).
- `C:\ProgramData\SonicStage\Packages` listed EMPTY, but the live
  library DB (MtData.mdb) is known to live there — the first command's
  `2>nul` likely swallowed an access-denied. Second listing drops the
  redirect so any denial is visible.
