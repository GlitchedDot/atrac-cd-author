# Stage-0 readout #16 — SAL attack phase 6: block-pool analysis — there is no block grid; bodies are branching stems, and the u16 is an exact template key (2026-10-22)

Static analysis only; nothing was executed. Materials: the module
corpus in `~/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG/`
(25 class-01 family `.ocm`, init.ocm, device.sal, 26 class-02
`.ocm`, 9 `FF FF` stubs). Prior papers: readout #15 (class-01
skeleton map, u16 continuation groups, class-02 prefix clusters),
readout #14 (skeleton anatomy, priming contract). New tooling:
`~/workspace/atrac-salwrap-work/sal_blockpool.py` (subcommands
`inventory`, `quantize`, `groups`, `transforms`, `atpcd`);
primary evidence in `out/phase6-notes.txt` (including the
continuation cross-check and the sweep null-control appended
there). All offsets are **body offsets** (file offset − 10).

## Verdict up front

**There is no natural fixed block size.** Bodies are not
concatenations of pool blocks on any grid: at every block size
from 256 to 4096 and every origin tested, (a) the byte coverage
of shared material is constant — sharing does not sharpen at any
size, (b) **zero blocks recur at a different offset, anywhere in
the corpus**, and (c) divergence points quantize to no grid
(0 of 18 class-01 branch points on-grid at any size). An
offset-agnostic 64-mer census over all bodies (init.ocm
included) finds **0 cross-offset shared 64-mers** against
335,510 same-offset ones: every shared byte in the corpus sits
at the same offset in both bodies. The "blocks" of phases 4–5
are variable-length units of the opaque contents encoding;
sharing is by **whole stems** — bodies form prefix tries that
branch at content-determined depths (§1).

**The construction hypothesis survives in descriptor form for
class-01 only.** The skeleton u16 is an *exact* template key:
across all 300 class-01 pairs, same-u16 ⟺ share past the
skeleton (CP ≥ 8,215) and different-u16 ⟺ skeleton only
(CP ≤ 8,212), no exceptions; measured on the continuations
directly, different-u16 pairs differ at continuation byte 0
(CP′ = 0, all 282 pairs). A label-permutation control puts the
real grouping far outside chance (mean max-internal CP′ 9,461
vs shuffled p95 2,573). The u16 is not a length, not a checksum
(CRC-16/CCITT, CRC-16/IBM, sum-16, first-bytes all refuted),
and shows no monotone relation to stem depth (Spearman −0.04).
Within a u16 group the sequences are **not** nested chains —
0 prefix-nested pairs — they are a branching trie whose
internal branch depths concentrate at {339, 2,324, 4,448}
(plus near-end effects ~15,350). For class-02, cluster
membership is **content-defined**: the only varying container
fields (a version-ish u16 at header+4: 5 vs 1, and the build
stamp at +6: 11280 vs 0) mark a sub-family (the six
`-dnk`/`_key` modules) but predict no cluster (§2).

**Framed vs opaque: the two layers share no material, under any
simple transform.** No opaque block occurs inside the framed
chunk and no chunk block occurs in any continuation, class-02
body, or init.ocm (exact, B = 256/1024, four region sets).
Fingerprint searches (16-mers) under identity, nibble swap, bit
reversal, byte-pair swap, and *every* constant XOR/ADD (via a
difference-invariant key that tests all 255 constants at once),
in both directions (chunk → all bodies; atpcd's lead →
class-01), return **zero hits**. A parse-depth battery
(sal_dis strict grammar) over all 52 opaque regions under the
structural transforms, plus a full 510-constant XOR/ADD sweep
on five representative regions, produces **no element-dense
parse**: the largest "deep" parses are single-length-field
accidents of the generic BER fallback (16,842 B consumed by 7
elements), and byte-shuffled controls produce *larger* maxima
(22,960 B / 2 elements) than any real region. No transform
anywhere reached 20 elements. The class-02 leading block
(~8,471 B) is **not** the class-01 STR[8192] chunk under any
tested transform — the ~279 B length difference needs no
framing explanation, because there is no byte-level relation
to explain (§3).

**atpcd.ocm**: 8,471 of 21,554 body bytes (39.3%) are a stem
shared with lgd.ocm only, at identical offsets; the remaining
13,083 B (60.7%) occur nowhere else in the corpus. Full block
map in §4. **atpcd.ocm remains undecrypted** — what this phase
settles is the *shape* of the sharing economy the contents
encoding lives in, and it eliminates the fixed-block and
simple-transform families from all future attempts.

## 1. Block decomposition: no grid, no positional reuse

Inventories (full blocks only; shared = occurs in ≥2 strings;
controls = per-body byte shuffle, which preserves each body's
byte histogram):

| Region set | B | Instances | Distinct | Shared | Shared coverage |
|---|---|---|---|---|---|
| class-01 bodies | 256 | 2,917 | 1,803 | 290 | 359,424 B |
| class-01 bodies | 1024 | 723 | 446 | 72 | 357,376 B |
| class-01 bodies | 4096 | 169 | 105 | 15 | 323,584 B |
| class-02 bodies | 256 | 2,120 | 1,920 | 167 | 93,952 B |
| class-02 bodies | 1024 | 519 | 471 | 40 | 90,112 B |
| class-01 continuations | 256 | 2,114 | 1,771 | 256 | 153,344 B |
| class-01 continuations | 1024 | 522 | 440 | 62 | 147,456 B |

Shuffled controls at B = 256/1024: **0 shared blocks** in every
region set — the sharing is real, not a histogram artifact.
Three structural facts decide the mission:

- **Positional reuse is zero.** At every B, the number of
  blocks occurring at ≥2 *distinct offsets* is 0 — in both
  classes, in bodies and in continuations. A pool construction
  (blocks drawn and concatenated in varying order/position)
  necessarily produces such recurrences; none exist. The
  64-mer census makes this alignment-independent: 0
  cross-offset shared 64-mers corpus-wide vs 335,510
  same-offset ones, so no choice of origin or block size can
  manufacture a pool reading.
- **Coverage does not sharpen.** Shared coverage is ~constant
  in B (class-01: 359 KB at 256, 357 KB at 1024, falling only
  at 4096 from edge loss; class-02: ~90–94 KB throughout).
  Shared material is byte *spans* with arbitrary boundaries,
  captured equally by any grid — the opposite of a block
  construction, where one B would align with the spans and
  dominate.
- **Divergence quantizes to nothing.** Class-01 within-group
  branch points (continuation-relative) are
  {1, 339, 2,324, 4,448, 15,347…15,374}: residues mod 256 are
  {1, 83, 20, 96, 243–249…} — 0/18 on-grid at every B, 1/18
  within 4 B of a grid line. Class-02 cluster divergences
  {8,468, 8,470, 8,471, 9,052} give mod-256 residues
  {20, 22, 23, 92}. (The ~15,35x class-01 values are end-of-body
  effects among near-equal-length siblings, not internal
  boundaries; the internal set is {1, 339, 2,324, 4,448}.)

The STR[8192] chunk decomposed alone: 32/16/8/4/2 blocks at
B = 256…4096, **all distinct at every size** — the chunk has no
internal block repetition either. It is one opaque span, not a
tiling.

**What the units are, then:** variable-length elements of the
opaque contents encoding (the same encoding inside the chunk,
in continuations, and throughout class-02). Modules that carry
the same program share a *stem* of whole elements; variants
branch where their element sequences first differ — which is
why branch depths are byte-exact but grid-free, and why the
same depths (339, 2,324, 4,448) recur across u16 groups: the
underlying programs share a common layout rhythm (prologue-like
element sequences of similar cumulative length), encoded
element-by-element, while their actual bytes differ from
continuation byte 0 across groups.

## 2. Construction: the u16 is the class-01 template key; class-02 clusters are content-defined

**Class-01 partition (all 300 pairs).** Same-u16 pairs:
CP ∈ [8,215, 23,588]. Different-u16 pairs: CP ∈ [8,211,
8,212] — i.e. they diverge *inside the skeleton, at the u16
field itself*. The partition is exact with a 3-byte gap
(8,212 < 8,215); the minimum same-u16 pair is osss/restore
(8,215: skeleton + marker + a single continuation byte).
Measured directly on continuations (body[8214:]), all 282
different-u16 pairs have CP′ = 0 — **the first continuation
byte already differs** — so the partition is a property of the
contents, not an artifact of measuring prefixes from byte 0
past an earlier per-module field. Permutation control (300
shuffles of the u16 labels): real mean of groups' max internal
CP′ = 9,461; shuffled median 330, p95 2,573, max 6,579. The
u16 selects the continuation's stem completely: it is a
categorical key (template/program-family identifier), with 13
distinct values over 25 modules in [0x49E8, 0x4A02].

Within-group shape (block sequences at B = 256/1024 confirm
the byte picture): groups share a common stem, then branch —
never nest. Group stems and branches:

| u16 | Modules | Internal branch depths (CP′) |
|---|---|---|
| 0x49e8 | icv, maclist | 4,448 |
| 0x49eb | migratepf, querycif | 339 |
| 0x49ee | vmc, vmc0conv, vmcconv | 2,324 (stem); pair to 15,368 |
| 0x49f4 | at3toomg, at3topcm, mp3toomg2 | ~15,348 (near-whole-body) |
| 0x49f5 | mp3tovmc, msatoomg, msatopcm | 2,324; pair to 15,374 |
| 0x49f6 | Omgtomp3, omgtomsa, omgtopcm2, pcmtoomg | 339, 2,324; pair to 15,347 |
| 0x4a02 | osss, restore | 1 |
| unique | mgrms, mgsoft, netmd, omgii, wm2, wmimport2 | — (share skeleton only) |

So a module's continuation = its u16-group's stem, branched at
one of the shared waypoints, plus its own tail. The block
sequence *is* descriptor-determined — one level up from blocks:
descriptor (u16) → stem (trie path) → module.

**Class-02.** Container headers take exactly 2 patterns over
26 files: `03 02 0000 05 00 102c0000` (×20) and
`03 02 0000 01 00 00000000` (×6; the `-dnk`/`_key` files:
bot-dnk, hdd-dnk, msa-dnk, umd-dnk, importer_key, ktunes_key).
Varying positions: header+4 (u16: 5 vs 1) and +6..+7 (build
stamp 11280 vs 0). Cross-tabulated against the five prefix
clusters: the atpcd/lgd cluster and three others sit in
pattern A alongside 11 unclustered bodies; the bot-dnk/hdd-dnk
cluster sits in pattern B alongside 4 unclustered bodies.
**No header field predicts cluster membership** — clusters are
defined purely by shared content (sibling builds sharing a
stem), exactly as in class-01 but without a descriptor field
recording the family. (Class-02's stems also differ from
class-01's in kind: there is no class-wide stem — the largest
cluster has 3 members, and 15 of 26 bodies share <64 B with
anyone.)

## 3. Framed vs opaque: no shared material, no simple transform

The framed layer's only substantial content is the STR[8192]
chunk; the question was whether opaque blocks elsewhere are
the same blocks unframed, or either layer is a fixed byte
transform of the other. All answers are negative, corpus-wide:

- **Exact block overlap across region sets** {chunk,
  class-01 continuations, class-02 bodies, init.ocm tail}:
  none at B = 256 or B = 1024.
- **16-mer fingerprint searches under transforms.** For
  T ∈ {identity, nibble swap, bit reversal, byte-pair swap}:
  T(chunk) 16-mers occur in 0 continuations, 0 class-02
  bodies, 0 init.ocm bodies; T(atpcd lead) 16-mers occur in
  0 chunk/continuation targets (pair-swap checked at both
  alignments). For constant XOR/ADD, a difference-invariant
  16-mer key (`m[i] ⊕ m[0]`, resp. `m[i] − m[0]`) tests all
  255 constants in one pass: chunk-under-any-constant occurs
  in 0 target bodies; atpcd-lead-under-any-constant occurs in
  0 class-01 targets. (Phase 5 had shown this for exact/XOR/
  ADD chunk→class-02; phase 6 adds the remaining transforms,
  the reverse direction, continuations, and init.ocm.)
- **Parse-depth battery (sal_dis).** Structural transforms on
  all 52 opaque regions: median bytes-consumed 0–36, maxima
  261–583 — the chance band (untransformed maxima: 277
  continuations, 379 class-02; shuffled chunk/atpcd: 0–226).
  XOR/ADD sweep (510 transforms × chunk, atpcd, lgd, and two
  continuations): best results are all giant-single-element
  accidents — e.g. icv continuation under ADD 63 consumes
  16,842 B in 7 elements; atpcd under XOR 197 consumes
  3,936 B in **1** element. The null is *stronger* than the
  signal: the same sweep on byte-shuffled chunk / icv
  continuation / atpcd yields maxima of 6,353 B / 22,960 B /
  18,211 B used. Judged by element density — the property a
  real SalAsn stream has (the genuine framing parses
  element-dense; cf. sal_skeleton over the skeleton) — no
  transform of any region reaches 20 elements, real or
  shuffled. **The opaque encoding is not a per-byte
  substitution, swap, or reversal of the framed encoding.**

For the atpcd-vs-chunk question specifically: the class-02
leading block (8,468–8,471 B) and the class-01 chunk
(8,192 B) are the same *kind* of object — an opaque stem in
the one contents encoding — but share no material in any
tested relation, so the ~279 B length difference is just the
difference between two stems, not framing overhead on a
shared payload. What distinguishes framed from opaque blocks
is therefore not a transform and not a shared pool: framing is
a separate plaintext layer that exists only in class-01's
skeleton (and the init.ocm/device.sal heads); its single
content block is opaque-encoded like everything else, and no
opaque block anywhere is a framed block in disguise.

## 4. atpcd.ocm block map

Body 21,554 B (file 21,564 B). At B = 1024 (ABS0), block IDs =
sha256 prefixes from sal_blockpool:

| Blocks | Body span | Label |
|---|---|---|
| 0–7 (`c4cf18b9e1` … `8b83719bde`) | +0 .. +8192 | shared with lgd, same offsets |
| 8 (`1660716742`) | +8192 .. +9216 | straddle: first 279 B shared with lgd, rest unique |
| 9–20 (`fa5a2f00a6` … `35d0443ca5`) | +9216 .. +21504 | unique to atpcd |
| 21 (partial, 50 B) | +21504 .. +21554 | unique trailing partial |

At B = 256 the same boundary reads: blocks 0–32 shared with
lgd at the same offsets, block 33 straddling (first 23 B
shared), blocks 34–83 unique, block 84 the 50 B partial. No
atpcd block at either size occurs in any other module of the
corpus (the shared-with-whom label fires only for lgd, only
at the same offset).

**Composition.** atpcd = an 8,471 B stem (39.3%) shared with
exactly one sibling + 13,083 B (60.7%) of its own. Read as a
program: the stem is the common prologue/library portion of a
two-module family (atpcd and lgd carry the same container
pattern, the same stem, and diverge at the same boundary
field anatomy as every class-02 cluster), and the unique
majority is atpcd's own logic — the ATRAC-CD binding whose
plaintext-side counterpart the earlier phases are hunting.
The stem is *not* a class-wide runtime: the other class-02
clusters have their own stems (8,468–9,052 B), 15 bodies have
none, and init2.ocm (8,471 shared + 13 unique bytes) shows a
module can be almost pure stem — the stem is a per-family
unit, closer to a linked library snapshot than to a shared
header.

## 5. What this means, and what remains

Phase 6 closes the stored-form's *combinatorics*. Bodies in
both classes are single stems-plus-tails in one opaque
contents encoding: no fixed block grid, no positional reuse,
no per-byte transform between any two regions, and (class-01)
an exact descriptor key — the skeleton u16 — that names the
stem family. Any future decryption candidate must reproduce
all of it: stems branching at {339, 2,324, 4,448} within u16
groups whose continuations differ from byte 0 across groups;
class-02 sibling stems of 8,468–8,471 B with their partly
coinciding boundary field; and a chunk that shares nothing
with anything. Conversely, the search space shrinks again:
whatever the contents transform is, it acts on variable-length
elements (its boundaries are the branch points), preserves
exact equality of equal plaintext elements (deterministic,
same start state), and is not a byte-wise map — consistent
with the bytecode-side, element-level encoding that readouts
#12–#14 placed inside init.ocm's loader, and inconsistent
with every stream/block-cipher-over-bytes reading that the
prefix evidence once suggested.

**atpcd.ocm decrypted: NO.** Its block composition is now
fully mapped (shared stem 8,471 B with lgd only; unique tail
13,083 B; no block shared with any other module), and the
pool/grid/transform families of hypotheses are closed with
controls. The remaining unknown is unchanged in kind and
narrower in shape: the element-level contents encoding
itself, whose semantics live in init.ocm's loader program
(readouts #13–#14), now with a precise structural spec —
stems, branch depths, and the u16 key — to validate any
candidate against.
