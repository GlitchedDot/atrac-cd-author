# Session 56 — DESK REPORT (2026-11-03)
Desk-only: STK parse, header census, S35/S36 re-mine. No builds, no burns.
(Written incrementally; sections land as each job completes.)

## Job 1 — the STK (0001000E.STK, 172 B)

- Byte-identical on every disc checked (appliance WYG disc, disc 1
  "CD stuff", disc 2): MD5 8eb1fe42505d0ea31c94fb972088a3db. Fixed EKB
  record for EKB version 0x0001000E, not per-disc material (matches the
  author's stk.py readout).
- Layout (offsets hex):
  - 0x00–0x1F: "EKB " + zeros (disc wrapper header)
  - 0x20: BE u32 = 0x0001000E (the EKB version; == .ATP header +0x10)
  - 0x24–0x37: zeros
  - 0x38–0x3F: 8 high-entropy bytes (88f5b6dd2a9e1570)
  - 0x40/0x44/0x48: BE u32 triple (12, 32, 52)
  - 0x4C: c9249204 (flags-like word; cf. sibling EKBs below)
  - 0x50: fe, then zeros to 0x57
  - 0x58–0x77: 32 high-entropy bytes
  - 0x78: BE u32 = 5; 0x7C: 01 00 00 00; 0x80: 01 00 00 28 (40)
  - 0x84–0xAB: 40 high-entropy bytes (to EOF)
- SAME FORMAT FAMILY as the PC-side .ekb files (repo-mirror/ekb/):
  siblings 0001000A.ekb / 00000002.ekb carry a BE version at +0, a random
  key block, then the same idiom — a BE triple (28,304,52) / (20,112,52)
  ending in 52, followed by a flags word containing 0x92 at the same
  byte position (a4924803 / a492491c vs STK c9249204). So the .STK body
  (from 0x38) is the version-0x0001000E EKB record in the standard EKB
  format, wrapped in a 0x38-B disc header. NOTE: the held repo mirror
  has NO 0001000E.ekb — the on-disc .STK is our only copy of this EKB
  version's record.
- Relation tests vs d2 (3d14fb8d…4a0570), all NEGATIVE:
  - d2 / d2[0:8] / d2[8:16] / d2[12:20] / any d2 4-byte chunk: absent raw
  - no offset where STK XOR d2 is (near-)constant
  - DES-decrypt and DES-encrypt of every aligned 8-B block (and sliding
    decrypt scan) with key d2[0:8]: no zero/ASCII/structured output

- Also negative: global seed (f1e9db56…) not present; SHA-1(STK) and
  SHA-1 of every plausible STK region != d2; self-key DES tests (each
  random block as key over the others, enc+dec) yield no structure.
  Entropy: wrapper 0.77 bits/B; the three random regions are at/near
  max entropy for their size. CONCLUSION (Job 1): the STK is a standard
  EKB key-block record whose key material is sealed in a form that does
  not expose d2 to any cheap transform — consistent with EKB design
  (the player firmware holds the EKB root; the record is data it
  consumes, not a key table readable from the disc side).


## Job 2 — secure-header census (35 genuine headers)

Sets: Ignite A0–A3 (scheme A), WYG (scheme B), Dreamer+Electric+28
disc-2 tracks (scheme "general", 30 headers).

CONSTANT ACROSS ALL 35: +0x00=0100282e, +0x08/+0x0c=0, +0x10=0001000e
(EKB version — names the STK), +0x14=0, +0x20..+0x27=010f500000040000,
+0x34..+0x3c=0, +0x40="ATX ", +0x44..+0x4c=0.
PER-TRACK RANDOM IN EVERY SCHEME: BlockSeed +0x18, IV +0x58 (all 35
distinct in both fields).
+0x04 = frame count (per-track, as known).
CID (+0x20..+0x33, the 20-B repository/content id = the .opf name):
+0x28 and +0x30 are constant across the 4 Ignite tracks (004f7e16 /
b4f37fbb — one import batch, the BB .opf) but near-per-track in disc 2
(26 distinct each over 28). +0x50 (mgd seed) likewise: constant across
Ignite's 4 (2ad14387ddfb4b86), near-per-track in disc 2 (26/28) — a
per-burn-batch value, not a per-install constant.
**+0x2c: A = 725f9be7, ALL 30 general = 725f9be7, B = 559ac07a.** The
only word that separates B from {A+general} — but A and general share
it, and A/general came from the same old-install lineage while B is a
fresh install: +0x2c tracks REPOSITORY IDENTITY, not payload scheme.
Cross-check with the twin: it played scheme B with +0x2c = 725f9be7
(the author's hardcoded old-repository word) in place of the
appliance's 559ac07a, and +0x28's last byte also wrong — so for scheme
B the player demonstrably ignores +0x2b..+0x2f when keying.
**NO scheme-selector byte exists in the header.** No offset separates
A from general at all; the header alone cannot tell the player which
scheme a track uses (unless whole-CID repository identity is the key
index — weakened for B by the twin result above).


## Job 3 — where BlockSeed / IV / +0x50 come from (S35/S36 re-mine)

Primary record: SESSION-2026-10-28.md runs ~126 (BIND anatomy),
~180-195 (op 11), S36 verdicts (~8695-8775), scratch/s36/ceremony.md,
scratch/s35/op11.py.

- **BlockSeed (+0x18) is an OUTPUT of the SAL key layer, minted per
  bind.** In omgatpcd's BIND_CONTENT (run ~126 record): the SAL op
  (selector 1) reply stream is read back as strings + an int + an
  8-byte SEED ("read-buf(sOut, desc{ptr,len=8}) -> SEED8"), and the
  host then does `memcpy(hdr+0x18, SEED8, 8)` and
  `setEkbVersion(hdr+0x10, 0x1000E)`. The note's verdict: "The SAL op
  (selector 1) is a key-management/binding op: it consumes the
  repository blob + the procfile-supplied string and returns binding
  strings + a fresh BlockSeed." BlockSeed is therefore NOT host RNG
  and NOT derived from the document by op 11 — the key module seals/
  mints it. S37 (burn side): "BlockSeed plays NO role in the payload
  transform."
- **+0x50 (mgd) is the same shape**: pfcom's FUN_6470fb49
  "GET_GLOBAL_SEED" runs a SAL op and reads back an 8-byte seed; the
  value equals the ceremony's Global\OMG_RAND_SEED content for the
  batch (constant across a burn batch's tracks, per the census —
  Ignite's 4 share it; disc 2's vary per batch).
- **IV (+0x58): writer never isolated in the note** (honest gap). It
  is per-track; the header is fully assembled host-side BEFORE op 11
  consumes it (run 180: the execute frame contains the raw 96-B
  header verbatim). Comparison batteries (runs ~193-195 era) found
  the IV is NOT the op-11 reply, NOT any ckey24 window, NOT the
  global seed. Hypothesis (labelled): a third SAL readback in the
  same header-mint flow (atpcd.ocm), i.e. key-module-minted per
  track like BlockSeed — consistent with everything observed, not
  proven.
- **ckey24 is NOT a BlockSeed/IV/key triple.** It is a per-RIP wrapped
  key minted by an nc.ocm execute (querycif op 6 derives it per call
  from stable ceremony state + wall clock — "fetched per rip from
  the key module"). Inside op 11 it is UNWRAPPED as
  W24 = DES-CBC-DECRYPT(ckey24, IV=SHA1(CID16 XOR (X8||X8))[0:8],
  key=digest1[8:16]) and W24 "does not feed the reply". No record of
  W24 equalling any header field; its consumer is the ripping path,
  not the disc header.
- **Concrete test (brief's question) — answered from primary
  records:** op 11's reply for Ignite A0's document is
  8150393f51e23848 (runs 193/194, deterministic across clocks; op11.py
  reproduces it as a pure function of (document, d2)). The run-193
  comparison table: reply vs BlockSeed d883bf8b4359d7c6 — NO match;
  vs IV 25a671276b529c02 — NO match; vs +0x50 2ad14387ddfb4b86 — NO
  match; vs all 17 8-B windows of ckey24 — NO match. The reply is a
  derived check value that appears NOWHERE on the disc, and S36
  proved its only consumer length-checks it (==8). The player cannot
  be recomputing it (it would need the whole ceremony). **The header
  fields are inputs minted by the key layer; op 11 generates none
  of them.**

## The model — how the player gets its key (ranked)

Established constraints: (i) payload key for Ignite = d2[0:8] on the
burn side (S37, byte-exact); (ii) d2 is a function of the installed
ceremony state on the PC — a standalone player cannot hold it per-
install; (iii) disc 3 (correct DES/d2 payload, self-consistent IV,
but RANDOM BlockSeed + mixed CID) died instantly; (iv) the twin
(genuine scheme-B header values copied faithfully except +0x2b..0x2f)
played; (v) the header carries NO scheme-selector byte (census);
(vi) BlockSeed is key-module output, per bind, with no burn-side
transform role — its only possible consumer is the player.

**Model 1 (leading): BlockSeed is the payload key SEALED under the
EKB; the player unseals it and DES-CBC-decrypts with the header IV.**
One player mechanism for both schemes: what differs is only which
key got sealed — the ceremony's current content key (== d2[0:8] for
the Ignite batch) for unprotected masters, the library master's own
content key for protected masters (scheme B). Fits (i)-(vi): disc 3
died because a random BlockSeed unseals to a garbage key; the twin
played because its BlockSeed was the genuine sealed one and the
unseal demonstrably ignores +0x2b..0x2f. The STK's role: it tells
the player which EKB version's ladder/record applies (+0x10 =
0x0001000E names it); the actual root lives in player firmware.
**Model 2: the player derives the key from (BlockSeed, CID, +0x50)
via a fixed SHA-1/DES derivation** whose burn-side fixed point is
d2. Weaker: S33-S36 batteries compared d2 against SHA-1 of every
ceremony value/combination to hand and found no derivation; and a
pure derivation would make BlockSeed's key-module minting pointless
— any host random would do.
**Model 3: d2 is a universal constant in player firmware too; header
fields are noise.** Nearly dead: disc 3 used the true d2 and a
self-consistent IV and still died. It survives only with a rider —
that the player keys its scheme/key choice off CID lineage (disc 3's
CID was appliance-flavoured: +0x28 head 0030fb.., +0x30 = the
appliance's 290e7f21, under an Ignite mgd) and applied the wrong
scheme. The experiment below controls for exactly this rider.

For scheme B specifically, Model 1's B-variant says the sealed key
is the library master's content key and the cipher is the same
DES-CBC/IV construction; the alternative B-variant (kept alive,
ranked second) is that B's payload uses the distinct OMA-library
cipher (the one ffmpeg implements), selected by repository lineage
in the CID head — the twin cannot distinguish these because it
copied every B-relevant field faithfully.

## Cheapest next experiment (ONE disc — described, not built)

**The genuine-track clone.** App-author ONE disc whose single track
is byte-for-byte a genuine scheme-A track: Ignite A0's secure header
VERBATIM (BlockSeed d883bf8b4359d7c6, IV 25a671276b529c02, +0x50
2ad14387ddfb4b86, CID 010f500000040000004f7e16725f9be7b4f37fbb) and
payload = S37 DES-CBC encryption of ignite.raw under (d2, A0's IV)
— S37 guarantees this equals A0's genuine .ATP payload byte-for-
byte; verify the whole .ATP against the genuine file before
burning. Tags/TOC inputs mirror A0's own (title/artist/album from
the genuine disc 1 set).
- PLAYS => a genuine (header, payload) pair is sufficient in an
  app-authored disc; disc 3's killer was its incoherent header
  (Model 1/2 confirmed in substance, Model 3's noise claim dead).
  The problem then becomes purely: minting NEW sealed BlockSeeds —
  a harness question (the SAL BIND op returns SEED8; S44 drove BIND
  to status-0), i.e. Session 57 territory.
- DIES => even perfect track bytes fail in app authoring; the
  missing piece is at DISC level (TOC/PLF content or an on-disc
  binding record the author doesn't reproduce for this content) —
  the cipher hunt redirects to the STI/TOC files, and every
  header-side theory is moot.
Either outcome eliminates half the model space for one blank.
(Runner-up, costlier: an appliance burn of a protection-OFF import
tests whether the appliance's burn-time key == d2_old — d2
universality — but needs a Toshiba session and SS settings work.)
