# Breakthrough — 2026-11-03: the ATRAC3+ CD format is fully authored end-to-end

On 2026-11-03 the D-NE1 played, with audio, two discs that SonicStage
never touched:

- **Disc 11** — a fully app-authored track (our DiscID, our computed
  BlockSeed, our folded ICV, our ISO) carrying genuine Sony-encoded
  frames under the genuine install content key. Verdict, in Lola's
  words: "WE HAVE SOUND."
- **Disc 12** — the same envelope carrying frames encoded by the
  open-source **atracdenc** encoder from an ordinary MP3. Verdict:
  "I'm listening to a beautiful song." The full chain — MP3 → ffmpeg
  PCM → atracdenc → encryption → authoring → hardware playback — now
  works with zero Sony software.

## The final recipe (all components verified on hardware)

- **DiscID**: free choice (fresh random 16 bytes). The player only
  folds/unmasks with it.
- **ICV** (Session 60, lifted from CDWalkman.dll's CreateIcv, unkeyed):
  `A = BE64(DiscID[0:8]); B = BE64(DiscID[8:16]); X = A; for each
  track's full .ATP byte size s in order: X = (X*s + B) mod 2^64;
  ICV = BE64(X)`. Verified byte-exact on all three genuine corpora.
- **BlockSeed** (Session 63b, lifted from the SAL BIND machinery):
  `P = (DiscID[0:8] ^ DiscID[8:16]) ^ BE64(bind_index+1) ^ d2[0:8]`;
  `BlockSeed = E_K1(D_K2(E_K1(P)))` — 2-key triple-DES EDE under
  `V = 3c8e092d257ffa7d3a3986d75b1b4c2b`, where bind_index is the
  track's position in the disc's bind order. Genuine-validated on
  six harness specimens and five consecutive genuine disc-1 tracks.
- **V is universal** (desk-proven 2026-11-03): unsealing the Toshiba
  appliance track's genuine BlockSeed under this V recovers that
  install's own content key, which decrypts its payload byte-exactly.
  Every install seals with the same V; every player unseals with it.
- **Payload cipher** (Session 37): DES-CBC over the frame stream,
  key = d2[0:8], IV = the header InitVector at +0x58, one continuous
  chain.
- **The content key must be genuine.** Discs authored under a novel,
  app-chosen key (discs 10/10R) were accepted but silent; disc 11,
  identical except for authoring under a real install's d2
  (3d14fb8d…), played. The app therefore authors with the held
  genuine key + its coherent registration papers (CID/mgd/connum/
  track_slot; Session 64 proved (CID, mgd) are per-registration
  minted state in perfect bijection across all 926 genuine headers).
- **Header IV**: honestly random (40 formula constructions, zero
  hits — Sessions 63b/64).
- **Structure/tags/NDB/TOC/STK**: the Python author reproduces
  genuine discs byte-identically; the "twin" disc proved it on
  hardware on 2026-11-03. Session 64's byte-level audit exhausted
  the disc surface: no field remains that an authored disc can
  miscompute; blob8 and all op-11 material are absent from the disc.

## How the day went

Sessions 56–64 (reports under `sal-research/readouts/`) closed the
remaining unknowns in order: the BlockSeed is a sealed key capsule
(S56); IDs are not derivable from disc data (S58, 30,665
constructions); CDRFormatter mints nothing — the ICV is computed in
CDWalkman (S59) and its formula fell in S60; the .acd files are
per-disc bind ledgers and the seed is a deterministic function of
ledger state (S61); the seal is a cipher, not a hash (S62's negative
battery), and S63b lifted it. The burn campaign (discs 1–12, build
scripts + notes under `proof-of-concept/`) arbitrated every model
on the D-NE1 itself — including two honest failures: disc 10's
payload was sliced from the wrong offset of its plaintext file
(a 376-byte ID3 header; caught by the project's own frame parser),
and the novel-key gate that discs 10/10R exposed and disc 11
answered.

Also on 2026-11-03: the SonicStage appliance (a fresh Windows 7
install on a spare Toshiba drive) burned its first real ATRAC CD,
which played — the belt-and-suspenders route works too.

## What remains

Engineering, not science: the web app (Wasm core, ISO out) and the
native Mac app on this recipe — playlists as groups, the capacity
gate, multi-track authoring at scale. The planned Weird Al disc
(14 studio albums) fits comfortably at 64 kbps.

Held back from this repository, as before: Ghidra decompilation
output of Sony binaries, raw run logs, the easter-eggs file
(publishing hold), all Sony binaries, and genuine track data.
