# Session 63 — HARVEST REPORT (2026-11-03)
Harness harvest session: capture the inputs Session 62's desk
battery was missing, trace one BIND execute's crypto operators
end-to-end, re-run the battery with the new inputs in hand.
Driver: sal_emu311.py (sal_emu310.py + S63 blocks); artifacts in
~/workspace/atrac-salwrap-work/scratch/s63/.
(Written incrementally; sections land as results arrive.)

## Job 1 — the octet16 session record: CAPTURED (from the campaign's own logs)

The salwrap manager's vt+8 method returns a pointer to the
16-byte session record. The S38-era helper `_s38_sessionrec`
has logged those bytes on every call for the whole campaign.
Harvest of every run log in scratch/ (601 reads, all at the
same pointer 0x123e6f74, spanning S38–S61, many processes):

    octet16 = 01 0f 50 00 00 04 00 00 00 00 00 16 72 5f 9b e7
              (constant across all 601 reads — no variance)

**What it is:** byte-identical to the S43 blob8 trailer
constant — and that is not a coincidence: it is the Ignite
repository's **CID16** = A0's CID20 (`010f5000 00040000
004f7e16 725f9be7 b4f37fbb`) with bytes 9,10 zeroed — exactly
the CID16 derivation op 11 performs (S35 step 1). The salwrap
session in this ceremony is bound to the Ignite content
repository, and its "session record" is that repository
identity. It is NOT the 20-B global seed (no window matches),
NOT d2 (no window matches), NOT the GET_GLOBAL_SEED readback
2ad14387ddfb4b86. It is a fixed ceremony constant here — which
is why the seal is deterministic in-harness (S61) while the
battery that lacked it *as a frame element* still failed:
S62's battery did use these bytes as the "trailer" component
in blob8-style framings and as DES/HMAC keys, but not in the
frame's own element order/roles (see Job 3).

In-run confirmation via a hook on the real method's octet
write (FUN_616048a5, caller-classified) is part of the S63
run below — BIND (FUN_6160571e) and OP-A (FUN_616054cd) both
build the record element through FUN_616048d7, which calls
salwrap1 vt+8 and writes {ptr, 16} via vt+0x6c.

## Job 5 — the .opf record decomposed (desk, done pre-run)

A0's content record (mirror procfile/BB/010F50000004000000
4F7E16725F9BE7B4F37FBB.opf, 232 B, md5 21a07d832d170cdc9e
61bd3b58b9d34c) parses cleanly under the struct grammar.
Elements (root container, indefinite form):

- int **1002** (0x03ea)
- blob20 **K1 = d9cedeed57908b33089389edd1dd8eaa223e2054**
  (the value the execute's compare #1 checks, per S62)
- blob20 **K2 = daedf91e98113d3791971a2399bfa25c0eb21975**
- container C1 (the content/CIF record):
  int 107, int 0x6aadeeaf (timestamp-like), int 7,
  int 0x6ab04e20 (timestamp-like), int 109, int 0, int 101,
  blob20 **K3 = 33f9d634cfb78a017c565183ecca7ab91c17e7de**,
  int 0, blob20 **CID20 = 010f500000040000004f7e16725f9be7
  b4f37fbb**, int 104, int 0x3aa43d, int 6,
  string06 "raw content importing" (21 B), int 103,
  ints 2,1,3,8,3,5,4
- container C2: blob04 "_ESI" (5f455349),
  blob20 **ESI1 = 0a25c0da24d0194b98a3bc34ce5614a000000000**,
  blob04 "_OCS" (5f4f4353), blob04 01ae2c00

These elements (K1/K2/K3, ESI1, C1 and C2 serializations,
the frame-order stream) join the battery in Job 3 — S62
only ever used the 232-B stream as one opaque blob.

## Job 2 — full operator trace of one bb execute: **THE SEAL IS LIFTED**

Machinery (S63b): Insertion A found intact at /tmp/s63_insert_a.py; Insertion
B written this session — entry hooks on every operator-table address with the
S35 dispatch-caller filter ([esp]==0x1032047f, vsp from [esp+8], operands =
top-6 value-stack slots decoded via the handle-object layout, blob objects
snapshotted md5-deduped to scratch/s63/objs/; exit pairing at the dispatch
return with result handle r32(EAX−4)); spliced with Insertion A into
sal_emu311.py. Run 1 = bb (traced) + the real-method OP-A drive.

Traced drive result: bb doc + genuine TRK000A0.ATP, 230 dispatched operators
(scratch/s63/optrace-bb.txt). The drive reproduced the specimen exactly with
the trace armed: replyint=1, gate compare #10 → 0 (12 compares), raises=0,
**buf8 = b4e56ea4874a6bb6** ✓. Operator-table caveat: my validation constants
for idx 99/101 were miscalculated (true addresses 0x10302fc0 / 0x103031e0, as
the trace itself shows), so both the live-read table and the embedded
fallback "failed validation" and the fallback (identical content) was used —
the trace is unaffected.

### The construction (every step verified offline with hashlib + s35/des.py)

```
P    = (key16[0:8] XOR key16[8:16]) XOR BE64(ctr) XOR d2[0:8]
buf8 = E_K1( D_K2( E_K1( P ) ) )              -- 2-key triple-DES EDE, 1 block
K1   = V[0:8]  = 3c8e092d257ffa7d             (encrypt key, steps 1 and 3)
K2   = V[8:16] = 3a3986d75b1b4c2b             (decrypt key, step 2)
ctr  = int2 + 1 for bb (=1)                   (see Job 3 for the term's full
                                               behaviour across specimens)
```

Trace evidence chain (op numbers in optrace-bb.txt): P is built at ops
#117–125 — key16 halves XORed (#121–123: 0524600df2cbc799 ⊕ 735961232a124529
= 767d012ed8d982b0), ⊕ BE64(1) assembled by CONCAT at #120 (op #124 →
767d012ed8d982b1), ⊕ d2[0:8] (#125 → **4b69faa3eff3b9ea**). K2 =
SUBSTRING(V,8,8) at #153. DES-KEYEXP(K1) at #139 → E_K1(P) at #140 =
1f2f27861908a404; DES-KEYEXP(K2) at #154 → D_K2(·) at #155 =
13aea2c226d14543; E_K1(·) at #156 = **b4e56ea4874a6bb6** = the reply's buf8.
Offline re-computation of all three steps and of P's assembly reproduces the
specimen byte-exactly.

**What writes buf8: operator idx 114 (DES-ENCRYPT), the third step of a
2-key 3DES-EDE — not a hash window, not a MAC.** S62's negative result is
explained: the construction is a cipher, and its key pair V is not among the
desk constants S62 tried as DES keys in single-block form.

### The key pair V — provenance (partially open)

V = (a1⊕b1)‖(a2⊕b2) is computed at ops #2–4 from four 8-byte values
(a1=485da6a9ae829207, b1=74d3af848bfd687a, a2=382f12b4f08b6434,
b2=02169463ab90281f) already materialized on the program's locals page before
the first dispatched operator — they arrive with the session/stream state,
not from the document, template or .opf (none of the four values, nor V, nor
the related pre-trace values 3c1748eb8ef4b7671b208e41f30a8d4a (16 B) or the
24-B blob 1339ebad112bd3f4d079b467fa40506b8b6049370d462150 appears in the
.opf, the maclist snapshot, or any traced object other than as these inputs).
V behaves as a **constant of the ceremony state** — the same class of object
as d2: every bb-family drive S40–S63 reproduces its specimen under this one V
(see Job 3). Extracting V once from a live ceremony (as was done for d2)
suffices for the app; deriving V from deeper constants is the remaining
unknown, and the wrapper machinery below is the suspect path.

### The wrapper machinery (context, not on buf8's path)

The same execute also runs a SHA-1/DES-CBC wrapper three times (ops #1–17,
#126–150): M = (X8‖X8) ⊕ (3c1748eb8ef4b7671b208e41f30a8d4a ⊕ R), where R =
37a72988a08ff6f39c4a78d81c95cc84 is the result of op idx 121 (the ckey-class
operator of S35's op-11 lift); D = SHA-1(M) = 647bcb64d191e44a…; DES-CBC
under key D[8:16] with IV D[0:8] encrypts (phase 1) and decrypts (seal phase)
a 24-byte blob 1339ebad112bd3f4d079b467fa40506b8b6049370d462150 ↔
2625698517a8dc52856638c08ac0d5d68992ca3b156883e6. This wrapper does NOT feed
the EDE; it presumably maintains/validates the session's sealed key material
— and is the likely birthplace of V's four parent values. Also in the
execute: the gate SHA-1 (inner‖"ATRAC CD"‖trailer; digest
e225ac50f7b1195f7b0b858d005a63fa54d157b8; compare of [0:8] at ops #114–116),
the post-bind record build + blob8′ SHA-1 (#157–168; blob8′ =
7af96ae450de6963), d2-keyed SHA-1 MACs over the .opf C1 container and record
elements (#18–113), and a "secure-clock" SHA-1/DES-CBC sequence (#219–228 →
924af48d04f267ca08dc9273024d8db6) feeding the reply's sibling strings.

### OP-A through the real method (FUN_616054cd)

Driven directly (args (0, buf); the octet hook confirms the method builds the
same session-record element, SESREC #3): completes, EAX=0, buf16 =
**fd3eb0aa9322ec3b384c403ca49bf8dc** — NOT the 0524600d… repository id the
hand-built S38 OP-A stream produces — and it created a real record for that
id: procfile/DC/fd3eb0aa9322ec3b384c403ca49bf8dc.acd (44 B; inner
(fd3eb0aa…, 0, 0); blob8 78b480fc93a4e7b7; saved to
scratch/s63/opa-created-record.bin, mirror copy removed). So the C++ method
and the hand stream are NOT equivalent drives: the method's `this` (a zeroed
alloc here vs the genuine session object) or its extra native steps change
the minted id. Not pursued further — OP-A was context, not the seal.

## Job 4 — micro-variation specimens

Built docs (all 44 B, staged from the bb doc by the S61-grammar builder;
serializations preserved at scratch/s63/<tag>-doc.bin):

| tag | change vs bb | doc md5 | predicted buf8 (construction) |
|---|---|---|---|
| i1p | int1 0→+1 (int2 0) | 739264f6054b1df8067a02b39aed51b9 | b4e56ea4874a6bb6 |
| i1m | int1 0→−1 (int2 0) | d3d4dfa1cfbc6d4e455ec3886d36e0ac | b4e56ea4874a6bb6 |
| kflip | key16 byte0 05→04 (0424600d…) | 1fb7c811057ba0e4c897aba8d20943de | e2c714f25d65da2b |
| t2p | int1 1296064, int2 1→2 | f025ddba343191363076ce56c41b4d41 | 7bfde00446132aab |
| t2m | int1 1296064, int2 1→−1 (ctr term BE64(0)) | 16e74b8a7310e4329bc95ce747ba4be7 | 843456a7a7f7d603 |
| a0zero/a0flip/tplA2/tplA3 | template-side only (seed slot zeroed / payload byte flipped / A2 / A3 templates), bb doc unchanged | (bb doc) d42f03199e99444d251da808e2f67cfa | b4e56ea4874a6bb6 |

Predictions use P's proven independence of int1 and of the template (the
EDE input is key16 + ctr + d2[0:8] only).

**Empirical status — the variation drives did NOT land clean specimens, and
the reason is itself a finding.** Runs 2–6 (same env throughout) diverged
from run 1's behaviour after run 1 mutated shared ceremony state (maclist.dat
21440→21448 B; a new OMGRIGHT .ICV written): the pre-S63 gauntlet slowed
~3–4× (runs 2/3/4/6 hit the 900 s cap in or just past the S63 block; run 5
completed but its drive aborted on staging debris left by run 4's mid-drive
kill), and every BIND drive that did execute in runs 4/6 — a0zero (doctored
template) and i1p (genuine template, valid folded doc) alike — aborted early
with the same signature (SEH rounds 44, out-dword never written, no reply
frame), versus run 1's bb (SEH rounds 88, replyint=1, specimen reproduced).
The abort is therefore a session-regime effect, not a doc/template effect.
The micro-variation specimens remain worth re-driving in a fresh-state
session (predicted values above are the oracle); they are confirmatory only
— the construction is already genuine-validated (Job 3) and the variations'
discriminations are settled by battery_d's grid (int1 independence:
t2int/t2alt/gcdL/gcdF span int1 1000…705397248 under one form; template
independence: the genuine A0–A3 forward hits; key16 sensitivity: the two
key16 families both validate with their own halves folded into P).

## Job 3 — battery_d: the lifted construction vs all specimens + genuine discs

`battery_d.py` (this directory) supersedes the S62 hash battery: with the
construction lifted from the trace, the open ends were (i) the ctr term's
exact form, (ii) whether V is a per-drive or ceremony-wide constant, (iii)
the A0 forward search. (The brief's planned extensions — octet16 in frame
order, .opf elements as hash components — are moot for the seal: the trace
shows neither enters buf8's path. The .opf stream does enter the execute as
the frame's element 3 — byte-identical to the genuine .opf file, confirmed
in-run — and its K1/K2/K3/ESI1 elements appear in the execute's d2-keyed MAC
phases, not in the EDE.)

### (i)+(ii) EDE vs the 10 S62 specimens (V from the bb trace)

`buf8 == EDE_V( (key16[0:8]⊕key16[8:16]) ⊕ BE64(int2+1) ⊕ d2[0:8] )`:

- **6/10 byte-exact hits: bb, t2int, t2alt, gcd0, gcdL, gcdF** — every
  specimen driven in a clean session state, spanning both key16 families,
  int2 ∈ {0,1,7,492,493}, int1 ∈ {0, 1000, 1296064, 704101184, 705397248}.
  All variant forms score strictly worse (BE64(int2): 0/10; LE64: 0/10;
  d2[8:16]: 0/10; swapped key order: 0/10; no-d2: 0/10), so the form is
  unique: **ctr term = BE64(int2+1), key order (K1,K2) = (V[0:8], V[8:16]),
  d2 half = [0:8]**.
- gcdA0 / gcdA1 miss. Inverting the EDE under the same V, their needed ctr
  terms are BE64(int2+1) ⊕ 0xFF00 (both, exactly) — structured, not random:
  these two S61 drives ran AFTER gcdF, the only BIND that ever completed,
  whose completion rewrote the shared .opf and the session state. Their
  anomaly is a post-completion state effect on the counter term, isolated
  to that pair; it does not touch the construction.
- t3big / p3s2 miss (slot-2 = 8192-B blob/string instead of an int — a
  pathological record shape no genuine record has). Their needed ctr terms
  (0xB6C1 / 0xC231) match no simple checksum (sum/CRC16/CRC32/Adler) of the
  slot-2 element; left as an open corner, irrelevant to genuine records.

**Conclusion: V is a ceremony-state constant (one V validates six drives
across two record families and five sessions, S40–S63), in the same class
as d2.**

### (iii) A0 forward search — **SOLVED, genuine-validated**

Running the construction forward over disc 1's 493 disc-order prefix states
(key16 = disc-1 DiscID f4a79f2142ee36fbf85052b79a17ad8d, ctr = position+1)
with the harvested (V, d2):

- **TRK000A0: computed d883bf8b4359d7c6 == genuine d883bf8b4359d7c6 ✓**
- **TRK000A1: computed 25473cd2cc31046c == genuine 25473cd2cc31046c ✓**
  (the required consecutive-state cross-check)
- Also exact: TRK0009F (26a8b854d046b771), TRK000A2 (9b26d540b53de5f7),
  TRK000A3 (632ead771bde5879) — five consecutive positions, 158–162.
- The other 488 disc-1 tracks and all 432 FavoriteDisc tracks do NOT hit
  under this (V, state): they were bound under other ceremony states and/or
  in an order other than final disc order (compilations assembled from
  previously bound tracks). The appliance disc (fresh install) also misses,
  as expected — its state is its own.

**The BlockSeed construction is therefore fully lifted and genuine-proven:**

```
BlockSeed(track) = E_K1( D_K2( E_K1( P ) ) )
P = (DiscID[0:8] ⊕ DiscID[8:16]) ⊕ BE64(bind_index + 1) ⊕ d2[0:8]
K1 = 3c8e092d257ffa7d, K2 = 3a3986d75b1b4c2b   (V, ceremony-state constant)
```

where bind_index is the record's int2 at the moment of the bind (binds
already in the disc's ledger). S61's "A0 seed not reproduced" is resolved:
the harness drives that missed used final-state or post-completion-state
docs; at A0's true prefix state (234127912, 159) the construction lands
byte-exactly. This also retro-explains S56's Model 1: the player unseals
BlockSeed with the EKB-held V and recovers the payload key material in P
(d2[0:8] masked by the DiscID fold and the bind counter, both of which the
player knows from the TOC/ledger position).

## State hygiene — final verification (S63b, after run 6)

Pristine set, all verified byte-exact at session end:

- disc-1 .acd (mirror procfile/8D/f4a79f2142ee36fbf85052b79a17ad8d.acd):
  md5 **51d4b28707b0a0426722d61e7f789859** ✓
- BB .opf (mirror procfile/BB/010F500000040000004F7E16725F9BE7B4F37FBB.opf):
  md5 **21a07d832d170cdc9e61bd3b58b9d34c** ✓ (also re-verified in-driver
  after every S63 drive; no drive in S63b completed, so no rewrite occurred)
- bb doc (scratch/s41/bb-doc.bin): md5 **d42f03199e99444d251da808e2f67cfa** ✓

Staging discipline: root32 holds NO TRK files; mirror procfile/29 holds no
staged .acd (debris from runs killed mid-drive — S63-prime's a0flip staging,
run 4's a0flip, run 6's tplA2 — was removed by hand after each kill and
re-verified clean at the end). The OP-A-created record
procfile/DC/fd3eb0aa9322ec3b384c403ca49bf8dc.acd was saved to
scratch/s63/opa-created-record.bin and removed from the mirror.

Known ceremony-state drift (working state, not part of the pristine set):
run 1's drives appended to maclist.dat (21440→21448 B) and wrote an
OMGRIGHT .ICV file; post-run-1 copies are preserved at
scratch/s63/state-backup-run1/. This drift correlates with the slowed /
early-aborting behaviour of runs 2–6 documented in Job 4 — flagged for
whoever resumes the harness: restore ceremony state before further drives
if run-1 behaviour is needed.
