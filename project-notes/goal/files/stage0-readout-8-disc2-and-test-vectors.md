# Stage-0 readout #8 — disc 2 compared; the STK is a constant; test-vector set complete (2026-10-21)

## Disc 2 (Lola's second ATRAC CD: 432 tracks, country — Alan Jackson, Big & Rich groups)

Root paperwork received and stored at ~/workspace/atrac-cd-stage0/disc2/.
Sizes scale as expected (TRACK/ALBUM/ARTIST.NDB = 256 + 432 x 128;
GROUP.NDB larger at 1,664 B — multiple groups vs disc 1's one).

**Headline: 0001000E.STK is BYTE-IDENTICAL on both discs (172/172
bytes).** The "disc key block" is not per-disc at all — it is a
fixed EKB record for EKB version 0x0001000E, stamped onto every
disc this install burns. Readout #6's "generated at burn time from
registry EKB + per-disc blobs" model is dead: for authoring, the
.STK is a solved copy — we hold the exact bytes. TOC00000.STI does
carry a per-disc 16-byte value in its header (offset ~0x18) — the
disc-individual data lives in the STI layer, not the STK.

## The test-vector set is complete

Lola sent the library file for Adikop - Ignite My Heart (five
copies in her library, all ATRAC3+ 64 kbps, 2:39.94, identical
audio). Extracted plaintext: exactly 1,294,944 bytes = 3,444 frames
of 376 B — byte-length-identical to the payloads of TRK000A0-A3.
**Banked set: ONE plaintext x FOUR ciphertexts**, the four
differing (per readout #7's map) only in BlockSeed (hdr 0x18) and
InitVector (hdr 0x58). Stored in ~/workspace/atrac-cd-stage0/pairs/
(ignite.raw, ignite-library.OMA, plus the Dreamer/Electric pairs).

Any candidate cipher/mode/key-derivation that the atpcd.ocm work
produces can now be verified or killed instantly against four
independent vectors. Passive analysis remains exhausted; the road
to naming the cipher is atpcd.ocm static analysis.
