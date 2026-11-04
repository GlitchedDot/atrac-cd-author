# Session 61 — CEREMONY REPORT (2026-11-03)
Harness-only (Unicorn SAL emulator): OP-A + BIND in burn-session order;
what the BIND BlockSeed (buf8) depends on. No disc builds, no burns.
(Written incrementally; sections land as results arrive.)

## Anchors re-verified before driving (desk, this session)

- BIND_CONTENT = FUN_6160571e (omgatpcd.dll), FOUR stack args
  (0, id16, templatePathW, outDword) — arg0 is an unused leading slot
  (S40 run 221 prologue disassembly). On STATUS 0 the readback is
  4 strings (A,B,C,D) + int (-> *outDword) + 8-byte buffer (buf8),
  and buf8 is memcpy'd to the template header +0x18 = the BlockSeed
  (S40 desk read of the method; S44 frame harvest at the vt+0xc call
  site 0x61605d9e reads buf8 from ebp-0x54 — the value that would be
  stamped; the method's host tail dies in the harness at that
  salwrap0 vt+0xc call AFTER the full readback, a parked harness gap
  that does not touch any execute verdict).
- The id16 keys the type-4 repository namespace:
  procfile/<hex(id16[15])>/<id16 hex>.acd (omgResolveRepositoryFile).
  MEDIA-INFO proves the module's reply identity == the repo doc's
  inner key16 (S40 run 229/230).
- BIND is a RECORD BIND, not an audio transform (S44 run 258 harvest):
  the reply record inner' = [key16, int1 + bound-file size, int2 + 1];
  string C (47 B) is the updated .acd ledger written back over the
  repo file. blob8 = SHA-1(inner ‖ "ATRAC CD" ‖ 010f5000 00040000
  00000016 725f9be7)[0:8] (S43 lift; desk-verified again below).

## ⭐ DESK FINDING — the five genuine .acd records are DISC records

The repo mirror holds exactly five genuine .acd files. Parsed this
session (inner key16 == filename in all five; S43 gate verified for
all five):

| record (== DiscID) | int1 | int2 | identity |
|---|---|---|---|
| f4a79f2142ee36fbf85052b79a17ad8d | 705,397,248 | 493 | **disc 1** |
| f59b0b4af42af1507142dc26191d97f1 | 684,803,088 | 432 | **FavoriteDisc** |
| cd4c659312b4cbba88d2a35e9d33b726 | 49,100,512 | 25 | a 25-track burn |
| c1d68a5e8a393ee00753a9e06ed84189 | 455,668,624 | 252 | a 252-track burn |
| 39b36d091d121dbd5d8631e5832949d7 | 439,667,720 | 280 | a 280-track burn |

int2 == the disc's exact track count in both checkable cases, and
int1 == the EXACT sum of the disc's .ATP file sizes (verified
byte-for-byte against the S58 corpora: disc 1 sum = 705,397,248;
FavoriteDisc sum = 684,803,088). So on the real system:

**OP-A (selector 0) mints the DiscID AND creates its .acd key
record; BIND_CONTENT is then called once per track with
id16 = that DiscID, and the record accumulates (Σ .ATP sizes,
track count) over the burn.** This triangulates three ways:
CDWalkman's Quick/FullCheckOut passing &DiscID to bindContent
(S60), the S44 ledger arithmetic (int1 += file size, int2 += 1),
and these five records' contents.

Corollary for the harness record: the S38–S44 drives bound against
key16 0524600df2cbc799735961232a124529 — the record ID the harness
ceremony's OP-A returns deterministically for its session (runs
174/206 byte-identical buf16; see the OP-A determinism note in
Job 1). That is a *session/disc record of the emulated ceremony*,
not the Ignite content repository in the .opf sense — the .opf
namespace (by CID20) is separate (S40 run 229).

## Job 1 — session-order matrix (drives in sal_emu310.py)

Driver: sal_emu310.py = sal_emu251.py + an s61 block (blobcmp gate
capture, SAL-raise capture, and the S44-proven VT0C frame harvest:
buf8 from ebp-0x54, reply int from ebp-0x4a4, strings A–D from the
frame slots). All BIND drives go through the REAL FUN_6160571e with
template TRK000A0.ATP. Docs are staged as the type-4 repo file and
unstaged after each drive (staging verified pristine).

### Run A (S38='opa' — OP-A runs first in-process, burn order)

- OP-A control: buf16 = 0524600df2cbc799735961232a124529 —
  byte-identical to runs 174/206. In a correctly driven ceremony
  OP-A is DETERMINISTIC (see the note under Job 3 on runs 125/126).
- **bb1** (repo doc = the live OP-A envelope [key16, int 0, int 0],
  id16 = key16): STATUS 0 (gate cmp #10 → 0, accept-side cmp #11
  present, raises = 0). **buf8 = b4e56ea4874a6bb6**; reply int 1;
  str1 = 338e968b…(as S44); str3 = e0044f25daf916b3….
- **bb2** (the SAME envelope bytes driven again in the same
  session): STATUS 0. **buf8 = b4e56ea4874a6bb6 — identical.**
  str3 identical (e0044f25…). The same-doc-twice control the
  campaign never ran: **no per-call freshness in-harness.**
- **t2int** (doc [key16, int 1296064, int 1], S44's exact doc,
  md5 aa69850b…): STATUS 0. **buf8 = a5bdf486982371dc — byte-
  identical to S44 run 258's t2int buf8 in a different process on
  a different day**; reply int 2 (ledger: int2 1→2 ✓); str1 and
  str3 (9c0c3694…) also byte-identical to run 258's saved frame
  files (verified on disk this session).

### Run B (S38='' — NO OP-A drive anywhere in the process)

- **bb3** (repo doc = the saved bb-doc.bin, byte-identical to the
  live envelope, staged from disk; no OP-A ran in this process):
  STATUS 0. **buf8 = b4e56ea4874a6bb6 — identical again.**
  ⇒ Running OP-A in the session is NOT an input to BIND's seed.
  The "session-order" question collapses: BIND needs only the
  repo document (which OP-A would have created) + the template +
  the base ceremony state.
- **gcdF** (repo doc = disc 1's GENUINE record (705397248, 493),
  id16 = disc 1's DiscID f4a79f21…, template A0): STATUS 0,
  **buf8 = 679994a2f5215379**, reply int 494 (= int2′ ✓).
  Side observation: gcdF is the only drive in S40–S61 history
  whose method call ran PAST the parked vt+0xc tail to true
  completion (EAX=0, template view stamped — diff span exactly
  the 8 BlockSeed bytes at header+0x18 — and the repo file
  rewritten with the updated record (706693312, 494), desk-
  verified). Every other drive (incl. gcdL/gcd0 below, same key,
  near-identical docs) still dies at the tail. No pattern in the
  doc explains the flip; recorded as an anomaly, not chased —
  the harvest precedes the tail, so no verdict depends on it.
- **gcdL** (same record rolled back one A0-bind: (704101184,
  492)): STATUS 0, **buf8 = dd8f6bb69b7021eb**, reply int 493.
- **gcd0** (fresh record under disc 1's DiscID: (0, 0)): STATUS 0,
  **buf8 = 759ec28de11493d9**, reply int 1.
  (The genuine record was moved aside for the gcd drives and
  restored byte-identical afterwards — md5 51d4b287… verified.)

### Job 1 — final matrix (all STATUS 0, template TRK000A0.ATP)

| doc (key16; ints) | arrangement | buf8 |
|---|---|---|
| 0524600d…; (0,0) | S38 hand frame, run 206 | b4e56ea4874a6bb6 |
| 0524600d…; (0,0) | OP-A → BIND (Run A, bb1) | b4e56ea4874a6bb6 |
| 0524600d…; (0,0) | same session again (bb2) | b4e56ea4874a6bb6 |
| 0524600d…; (0,0) | no OP-A in process (bb3) | b4e56ea4874a6bb6 |
| 0524600d…; (1296064,1) | S44 run 258 | a5bdf486982371dc |
| 0524600d…; (1296064,1) | S61 Run A | a5bdf486982371dc |
| 0524600d…; (1000,7) | S44 run 259 (t2alt) | bf659c82e92be6ad |
| 0524600d…; (1296064, blob) | S44 run 258 (t3big) | 1c953066eb2406f4 |
| 0524600d…; (1296064, str) | S44 run 258 (p3s2) | 4ad3fd6b583bd844 |
| f4a79f21…; (0,0) | gcd0 | 759ec28de11493d9 |
| f4a79f21…; (704101184,492) | gcdL | dd8f6bb69b7021eb |
| f4a79f21…; (705397248,493) | gcdF, genuine record | 679994a2f5215379 |

**Job 1 verdict:** the BlockSeed is a **deterministic function of
the repo document's content** (identity key16 + both ints + the
slot-2 element) **under a fixed ceremony state**. It does NOT
depend on: call order within a session (bb1 == bb2), whether OP-A
ran in the process (bb3), the process/session instance (bb across
runs 206→A→B; t2int across S44→S61), or the frame arrangement
(S38 hand frame == real method). Every change to the doc's inner
bytes changes the seed; nothing else varied in-harness changes
it. (File-dependence: every drive above used the A0 template —
the seed's template-sensitivity is tested head-on by gcdA1 in
Run C2, which binds a different template under a neighbouring
record state; see Job 2.)

## Job 2 — the A0 reproduction test

Target: A0's genuine BlockSeed d883bf8b4359d7c6. Given Job 1
(buf8 is a deterministic function of the repo doc + ceremony
state), reproduction requires the exact doc state A0's burn saw.
Arrangements driven under A0's template (all STATUS 0 unless
noted): the fresh Ignite envelope (0,0) under key16 0524600d…
(b4e56ea4…); the genuine disc-1 record in final state (705397248,
493) → 679994a2…; rolled back one bind (704101184, 492) →
dd8f6bb6…; fresh under disc 1's DiscID (0,0) → 759ec28d…. **No
hit.** The remaining candidate arrangement: if SS bound disc 1's
tracks in disc order, A0 (position 160 of 493) saw the record at
(Σ sizes of tracks 1–159 = 234,127,912, 159) and A1 (position
161) at (235,423,976, 160) — computed exactly from the S58
corpus. Those two drives (gcdA0/gcdA1, the latter also varying
the template to TRK000A1.ATP, target 25473cd2cc31046c) ran as
Run C2 (after the .opf restore; the in-run t2int control returned
a5bdf486… a third time, and no MAC throw occurred):

- **gcdA0** (doc (234127912, 159), template A0): STATUS 0,
  **buf8 = 096da854ae9e6320 ≠ d883bf8b4359d7c6.**
- **gcdA1** (doc (235423976, 160), template A1): STATUS 0,
  **buf8 = c6619cbd1f9d3f1f ≠ 25473cd2cc31046c.**

**The disc-order hypothesis is refuted (in-harness):** binding
in disc order through the computed pre-states does not reproduce
either genuine seed. gcdA1 simultaneously settles Job 1's open
variable — the seed DOES depend on the template/session pairing
(a neighbouring doc + different template gives an unrelated
seed), though doc and template effects can't be separated from
this pair alone.

**Job 2 verdict: NO arrangement reproduces A0's genuine
BlockSeed.** Every driven seed is the same form (an 8-byte value
in the BIND reply's buf8, structurally indistinguishable from
the genuine one), so the seal's FORM is reproduced; its exact
inputs are not exhausted by (record state, template). What that
implies about missing state, in order of plausibility:

1. **Bind order ≠ disc order.** The record only pins the start
   (0,0) and end (705397248, 493) states; A0's true pre-state is
   one of 493 states along the actual bind order (checkout-queue
   / group / enumeration order — not recoverable from the disc).
   A search over all 493 prefix states of SOME order is not
   possible without knowing the order; but note int2 alone fixes
   which step it was, and int1 is then the sum of that step's
   predecessors — unknowable without the order itself.
2. **Ceremony-state drift.** The harness reproduces the BB
   install's ceremony as captured LATER (its .opf fields, the
   frozen clock 1793313847, the harness OMG_RAND_SEED). If any
   of those fed the original burn's seed and differs now, exact
   reproduction fails regardless of the doc. (The clock branch
   was tested directly — Run D2: t2int under
   ATRAC_S36_TSHIFT=86400 returned buf8 a5bdf486982371dc,
   **byte-identical** to the unshifted value. Wall-clock, as the
   harness supplies it, does NOT feed the seed.)
3. The .opf session's stamped fields (its time int was already
   rewritten by later real-system binds before the Toshiba
   capture) — same family as (2).

### ⚠ Run C (first attempt) — invalidated by a found side effect

Run C's three drives all died before the gate (cmps=2, no
harvest): the pfcom ProcessFile ctor threw the S11-era
**"bad ProcessFile MAC"** during session creation. Root cause
found in the log: **gcdF's completion in Run B rewrote the
shared Ignite .opf in the repo mirror** — BIND's status-0 tail
stores string A back through procfile vt+0x2c, and string A is
the .opf with two fields rewritten (blob #1 → b4d928e6…, one int
→ the ceremony time). The mirror .opf's MD5 had changed from
genuine 21a07d832d170cdc9e61bd3b58b9d34c to a6585df6…. With the
.opf mutated, the maclist MAC verification inside session
creation fails and every BIND in the process dies upstream of
the execute. (On the real system SS performs the same store;
that the verify then fails is a harness fidelity gap in the
store/verify pair — the S11 blocker family — not chased here.)
**Remediation: the mirror .opf was restored byte-identical from
the Toshiba corpus copy (MD5 21a07d83… verified) and the drives
re-run as Run C2.** Standing warning for future sessions: any
drive that completes the method mutates the template's .opf in
the mirror — restore it from the corpus afterwards, and never
trust a post-completion process's session creation.

## Job 3 — BIND's arguments, post-S60 (decomp trace, both DLLs)

**CDWalkman side (decomp-cdwalkman.c, FUN_604169d1 QuickCheckOut;
FullCheckOut FUN_60417324 is the same shape).** Per track, in a
retry loop (≤999, driven by CCDRFormatter::SetFileNumber
collisions), it calls IOmgAtpcdMan::bindContent (interface ptr at
session-obj +0x38, vtable +0x10) as:

    bindContent(this, session-obj + 0x208, track->field+0xc, &out)

i.e. **the first real argument is &DiscID** — the session object's
+0x208 member, the same 16 bytes OP-A minted (or that were adopted
from an existing disc). The second argument is a per-track record
field: the template (.ATP) path pointer the method mmaps. The
third is the out-dword that receives BIND's reply int.

**omgatpcd side (decomp-omgatpcd.c, FUN_6160571e).** The four
stack slots are ([ebp+8] unused, [ebp+0xc] = id16 ptr,
[ebp+0x10] = template wide path, [ebp+0x14] = out-dword ptr);
all three real args are null-checked (E_POINTER). The id16 is
used for exactly two things:

1. `omgResolveRepositoryFile(out, 4, id16)` — resolving WHICH
   repo file to open (procfile/<hex(id16[15])>/<id16>.acd);
2. the log line "ATPCD::BIND_CONTENT: 0x<id16 hex>".

**The id16 bytes never enter the SAL stream.** The selector-1
frame the method builds is, in order: [buffer-ref: the repo
file's bytes] [int: template file size] [octet16: the salwrap
session record — salwrap1 vt+8's pointer, 16 B] [octet: the
procfile session's vt+0x28 string = the template's serialized
.opf stream] [int 1 = selector] [module atpcd.ocm]. The procfile
session itself is created from the TEMPLATE's secure header
+0x20 (factory vt+8(hdr+0x20)) — content-keyed, from the file
being bound, not from the DiscID.

So DiscID-shaped data reaches the BIND op by exactly one channel:
**the repo document itself** — in a real burn the .acd named by
the DiscID, whose inner key16 IS the DiscID and whose blob8 gate
the program verifies (S43). The repository identity of the S38–S44
harness drives (0524600d…) played this same role: it is the record
ID the harness ceremony's OP-A returns for its session — the
emulated counterpart of a DiscID, not the .opf/CID namespace
(S40 run 229's correction stands).

**OP-A itself (FUN_616054cd, decomp read this session):** frame =
[octet16: salwrap1 vt+8 session record] [int 0] [module
atpcd.ocm]; readback = byte, **16 bytes INTO the caller's
buffer** (desc {ptr = caller arg, len 0x10}), two strings; then
omgResolveRepositoryFile(4, minted16) + omgMkdirHier +
writeToFile(string #2 — the envelope) creates the new record.
Its only input from the host is the salwrap session record; the
minted value is whatever the atpcd.ocm selector-0 program returns
for that session state.

**On runs 125/126 "fresh per run" vs runs 174/206 determinism:**
125/126 were the first correct-manager replays, executed before
the ceremony state was fully established in those early boots;
from run 174 onward, with the mature ceremony, OP-A returns
0524600d… byte-identically every time (174, 206, S61 Run A). The
deterministic result under the established ceremony is the
operative fact; the early variance tracks ceremony-state
differences, not a per-call RNG draw that survives into BIND
(cf. Job 1: BIND's outputs are likewise deterministic in the
mature harness).

## Job 4 — verdict for the app

Evidence levels: **[HW]** proven on the D-NE1 by Lola's burns;
**[H]** proven in the harness this session; **[D]** desk evidence
(decompilation/records); **[I]** inference.

**What a ceremony session must supply per disc for NEW tracks:**

1. **One DiscID per disc, minted by OP-A** [D+H]. OP-A creates
   the disc's repository record named by the DiscID, and every
   track bind for that disc runs against that record (Job 3).
   A random 16 bytes is NOT equivalent: discs 7/8/9 [HW] show
   the player binds payload decryption to the genuine
   configuration, and S60/S61 show the DiscID's only legitimate
   source is this mint (or adoption from an existing disc).
2. **Per-track BlockSeeds from BIND against the disc's own
   record, bound in order** [H]. The seed is a deterministic
   function of the record's state at bind time (Job 1 matrix):
   each bind consumes the record state left by the previous
   binds of the same disc. A seed minted against any other
   record state — even the same DiscID at a different count —
   is a different seed (gcd0/gcdL/gcdF all differ). So the app
   cannot precompute or transplant seeds; they must come out of
   the ceremony in bind order, exactly as SS does.
3. **The ICV folded over (DiscID, the disc's .ATP size list)**
   [D, S60; HW via disc 7 passing the furniture gate]. Already
   implemented desk-side; not a ceremony output.
4. Nothing else DiscID-shaped enters BIND [D, Job 3]: there is
   no second channel to keep coherent. The coherence the player
   demands is exactly (DiscID ↔ its record ↔ the sequence of
   seeds the record's binds produced ↔ ICV over the final
   layout).

**Is the payload key for harness-sealed tracks knowable?**

- The payload cipher for genuine Ignite tracks is DES-CBC with
  key d2[0:8] (S37, byte-exact) [D]. S56's Model 1 says the
  header BlockSeed is that key SEALED under the EKB; the player
  unseals it. If the sealed key were always d2[0:8], every
  genuine seed would unseal to the same key.
- This session adds one hard constraint [H]: the seed bytes are
  a deterministic function of the record state — they are NOT a
  constant seal of a constant key (bb/t2int/t2alt/gcd* all
  differ while d2 and the ceremony are fixed). Either the
  sealed plaintext varies per bind (e.g. the key is wrapped
  together with record-derived material), or the seal itself is
  keyed/keystreamed by record-derived input. **No evidence in
  this session supports "the sealed key is d2[0:8]" for
  harness-minted seeds, and the determinism result cuts against
  the naive version of it** (a fixed-key EKB seal of a fixed key
  would be constant across drives; a randomized seal would not
  be byte-stable across processes — the observed seeds are
  neither). What the sealed plaintext IS remains undetermined:
  the harness cannot unseal (no EKB key ladder), and no drive
  here decrypts a payload.
- Practical consequence [I]: for app-authored NEW tracks, the
  only currently-known route to a playable payload is to make
  the ceremony produce the seed AND know the corresponding
  plaintext key. Until the seal's plaintext is identified (the
  S56 open problem), a harness-minted (DiscID, BlockSeed) pair
  is coherent in FORM but the app cannot encrypt audio to match
  it. The alternative that side-steps the seal entirely —
  cloning genuine tracks with their exact genuine (DiscID, ICV,
  layout) — is [HW]-proven (the twin) but only replays existing
  genuine content.

**The remaining gap to a fully app-authored playable NEW-track
disc**, stated plainly: (a) run the real ceremony (OP-A + ordered
BINDs) at authoring time — the harness proves this is
mechanically possible PC-side, deterministic and reproducible;
(b) identify the payload key that a ceremony-minted BlockSeed
seals — i.e. break Model 1 open: either extract the unsealed key
for one harness bind by observing the player's side (not
available) or find the seal construction in the SAL/EKB code
and invert it for a known (record, seed) pair, of which this
session produced a dozen exact specimens; (c) A0's
non-reproduction warns that the harness ceremony may still
differ from a real burn in seed-relevant state — if (b) is
solved against harness specimens, a single real-burn comparison
(the appliance + a captured session) would be needed to confirm
the app-side ceremony is the same function.

## Appendix — run inventory

- sal_emu310.py = sal_emu251.py + the S61 block (env-gated
  ATRAC_S61_MODE='s61'); hooks: blobcmp gate capture @0x10302cc0
  / exit 0x10302d51, SAL-raise capture @0x65120160, VT0C frame
  harvest @0x61605d9e (buf8 at [ebp−0x54], reply int at
  [ebp−0x4a4], strings A–D at frame slots).
- Run A (S38='opa'): bb1, bb2, t2int. Run B (S38=''): bb3, gcdF,
  gcdL, gcd0. Run C: INVALID (mutated .opf). Run C2: gcdA0,
  gcdA1, t2int control. Run D: t2int under TSHIFT=86400 —
  timed out in ceremony under CPU contention, no data. Run D2
  (solo re-run of D): t2int buf8 a5bdf486982371dc — identical
  under +86400 s clock shift; the clock is exonerated as a seed
  input.
- Artifacts: ~/workspace/atrac-salwrap-work/scratch/s61/
  (frame-*.bin, bcmp-*.txt, *-doc.bin, run{A,B,C,C2,D,D2}.log,
  genuine-disc1.acd.bak).
- State hygiene verified after every run: mirror procfile/8D
  .acd restored (md5 51d4b28707b0a0426722d61e7f789859), system32
  staging empty of session files, .opf restored to genuine md5
  21a07d832d170cdc9e61bd3b58b9d34c after Run B's mutation.
