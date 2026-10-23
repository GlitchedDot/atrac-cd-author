# Readout #17 — SAL phase 7 opening probes (2026-10-22)

Tool: `~/workspace/atrac-salwrap-work/sal_phase7.py`; evidence:
`~/workspace/atrac-salwrap-work/out/phase7-notes.txt`.
(First run's classifier diverged from the corpus standard and
reported a false "chunk not identical / 26 modules"; corrected to
sal_blockpool's exact classification and re-run — the results below
are the corrected run.)

## P7.1 — the STR[8192] chunk carries no plaintext crypto furniture

The chunk (body +17..+8209, byte-identical across all 25 class-01
modules, SHA-256 b580b1f40b2f09a2fb8f7903c95203f4492610e9035ae80cbe
211e24538588b7) was scanned for known cryptographic constants:
AES S-box and inverse S-box, SHA-256 initial state and round
constants, SHA-1 initial state, MD5 K, Blowfish P-array / hex
digits of pi, CRC-32 tables (both standard polynomials, both
endian forms), TEA/XTEA delta. **No hits anywhere** (8-byte minimum
match length). ASCII strings ≥6 chars are chance fragments at the
chunk's entropy (7.978 bits/byte, uniform ~7.5–7.65 per 512-byte
block). Lag-IC is flat at every tested lag. The chunk is encoded
content (or key material indistinguishable from it), not a
plaintext table of any standard primitive.

## P7.2 — continuations have no periodic keystream

Pooled index-of-coincidence over all 25 class-01 continuations at
lags 1..8192: **no lag exceeds the random baseline** (~0.0039;
spike threshold 0.0055 never met). A shared periodic keystream
(Vigenère-family, LFSR, short-period RC4 restart) of any period
≤ 8192 is excluded. Together with readout #16 (byte-granular
divergence, no block grid; per-byte transforms excluded), the
continuation transform sits in the remaining family: a block
cipher in a byte-granular chaining/stream mode, or an aperiodic
keystream.

## P7.3 — init.ocm's form, characterized at last

Through the proper container split, init.ocm's body (582,621 B;
its container header is 15 B, not the usual 10) opens with the
**same 13-byte universal head** as class-01 modules
(`01 01 04 08 <family id 6a35a21d8c3c2c0c> 7e`) and shares exactly
those 13 bytes with them. Then it diverges completely: no
STR[8192], no skeleton, no plaintext framing anywhere — entropy
7.975–8.000 from byte 13 to EOF. The bootstrap module is one
opaque span behind the family head.

That sharpens the bootstrap problem into a precise statement:
whatever decodes init.ocm's body needs **no** plaintext scaffolding
and **no** per-module data — it runs before any module's chunk or
skeleton exists. The decoder is therefore either inside the
self-protecting monkey engine's runtime behavior (its on-disk
form was fully scanned in readout #12 — no native bulk cipher —
but a self-protecting engine's running form is not necessarily
its on-disk form), or a fixed transform keyed entirely from
salwrap's static data.

## Where phase 7 stands

Static families now closed with receipts: framing/grammar
mismatch, deflate, fixed blocks/pool, per-byte transforms,
constant-XOR/ADD fingerprints, known-constant tables, periodic
keystreams. The stored-form problem has resisted every purely
static probe across readouts #11–#17.

The road not yet walked is **dynamic**: stand the SAL stack up
(salwrap.dll under a harness or Wine), let the monkey engine prime
itself on the real init.ocm, and dump the arena / formed images
from memory. That converts the question from "what is the
transform" (unanswerable statically so far) to "read the answer
out of RAM". It is a bigger build than any single readout so far
— the host-services surface must be implemented or stubbed — and
is scoped as its own phase-7 stage when Lola calls for it.
