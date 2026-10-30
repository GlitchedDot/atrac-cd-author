# Stage E0 — Sony's 64 kbps ATRAC3+ bit-allocation profile

Calibration target for extending atracdenc (see `stage1-encoder-bitrate-plan.md`).
Measured from Lola's own Sony library encodes, not from documentation.

**Corpus:** the three banked clean Sony 64 kbps encodes in
`~/workspace/atrac-cd-stage0/pairs/` — Dreamer (Alan Walker), Electric
(Akacia), Ignite My Heart (Adikop) — 376-byte frames, 44.1 kHz stereo.
**9,824 frames total; 9,818 parsed bit-exactly and used** (see Validation).

**Parser:** `~/workspace/atracdenc-test/e0_profile/parse_at3p.py`
(aggregation: `aggregate.py`, raw stats: `profile_stats.json`, same folder).

---

## Headline numbers

| Fact | Value |
|---|---|
| Quant units signaled (`num_quant_units`) | **27 in 9,818 / 9,818 frames (100%)** |
| Quant units actually used | 27 in 99.7% of frames |
| Frame budget consumed | mean **2,992 of 3,008 bits (99.5%)**, max 3,006 |
| Word-length sum per frame | ch0 mean **72.3** (p10 58, p90 88); ch1 mean **60.3** (p10 45, p90 77) |
| Tones (GHA) section present | **0 frames** |
| Noise section present | **0 frames** |
| Gain control present | ≥1 channel in **65.8%** of frames (both channels 54.1%) |
| Word-length weights tables used | **never** (weight_idx = 0 in all frames, both channels) |
| Code-table section | mode 0 (direct), restricted table (`use_full_table` = 0) in 100% of non-silent frames |

Sony's 64k encoder is *far* more regular than the format allows: a fixed
27-QU frame, a two-plateau word-length shape, the second channel coded
only below ≈8.3 kHz, and two whole bitstream sections (tones, noise)
never touched.

---

## How this was measured (parsed vs inferred)

**Parsed bit-exactly** (values read from the bitstream and used below):
frame header (num_quant_units, mute), per-channel word lengths *after*
fill/weights processing (i.e. the values a decoder actually applies),
scale-factor indexes, code-table indexes, coding modes and fill modes
for every section, gain-control presence, tones/noise presence, total
bits consumed, and the frame terminator.

**Walked but not interpreted:** spectral coefficient values, gain-control
point values, tone wave parameters — the parser consumes their bits
exactly (verified by the terminator check) but does not decode them to
values. Nothing in this report depends on them.

**Not used / not needed:** no spectral values, no listening tests.

### Parser provenance — important

The parser is a function-by-function port of **FFmpeg's ATRAC3+ decoder**
(`libavcodec/atrac3plus.c`: `ff_atrac3p_decode_channel_unit` and helpers;
frame wrapper from `atrac3plusdec.c`), with all VLC tables rebuilt
mechanically from the FFmpeg data tables as vendored in atracdenc's tree
(`src/atrac/at3p/ff/atrac3plus_data.h`).

It is *not* modeled on atracdenc's bit-writer. That matters: atracdenc's
writer implements only a small subset of the syntax (wordlen mode 3 with
fill_mode 0, sf mode 0, code-table mode 0), and an earlier hypothesis
model built from it could not parse Sony's frames at all. Sony uses the
full syntax — wordlen fill modes, VQ-shape scale-factor coding,
inter-channel wordlen prediction — which only the decoder's grammar
describes completely. One extraction bug was found and fixed along the
way (a `static_cast<int8_t>(172)` literal in the vendored header's
spectra codebook 33); after the fix, **all 112 spectra codebooks have
Kraft sum exactly 1** and every VLC family consumes its symbol table
exactly, identically in the vendored and upstream FFmpeg headers.

### Validation

- **Terminator check:** after each frame's channel unit, the next two
  bits must be the frame terminator `11`. Hit on **9,818 / 9,824 Sony
  frames (99.94%)** and on **132 / 132 atracdenc frames** (silence, sine,
  noise at 352.8k). FFmpeg's own range checks (wordlen 0–7 after
  weights, scale factors 0–63 after weights, coded-count limits) never
  fired on the accepted frames.
- **Excluded (6 frames):** 4 frames land a few bits off in the
  gain-control tail (word-length/scale-factor data, which sits earlier
  in the frame, is unaffected); 1 frame overruns in the tail; 1 frame
  signals GHA amplitude mode 0 — a feature FFmpeg itself rejects as
  unsupported, so that frame is either a genuine Sony-only quirk or a
  1-in-3,444 anomaly. None of these move any statistic below.
- **Synthetic walk test** (`test_walk.py`): the spectrum walker was
  round-tripped against a synthetic encoder for all 112 code tables ×
  30 random cases — bit consumption exact in every case.

---

## The allocation profile

Per-quant-unit word lengths, 9,818 frames. "Median" is the typical
frame; the mean is pulled around by transients. QU width in spectral
lines: QU 0–7 = 16 lines each, 8–15 = 32, 16–21 = 64, 22–26 = 128
(2048 lines ≈ 10.8 Hz each, 22.05 kHz total; QU 18 starts at line 768
≈ 8.3 kHz).

### Channel 0

| QU | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| median | 6 | 6 | 6 | 5 | 5 | 5 | 5 | 5 | 4 | 3 | 2 | 2 | 1 | 1 |
| mean | 5.63 | 5.58 | 5.54 | 5.41 | 5.39 | 5.47 | 5.27 | 4.84 | 3.69 | 3.32 | 2.54 | 2.28 | 1.69 | 1.44 |

| QU | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| median | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| mean | 1.32 | 1.16 | 1.16 | 1.12 | 1.08 | 1.06 | 1.04 | 1.03 | 1.05 | 1.04 | 1.06 | 1.05 | 1.06 |

Shape: a **plateau at 5–6 for QU 0–6**, a step down through QU 7–11
(4, 3, 2.5, 2.3), then a **long flat tail at wordlen 1 from QU 12/15 to
QU 26**. The tail is not coded value-by-value: in 90.6% of frames ch0
uses wordlen fill_mode 2 — only ~10–16 values are VLC-coded
(`num_coded_vals` mean 14.8, mode 12) and the rest of the tail is filled
with 1s by rule. In the other 9.4% all 27 are coded explicitly.

### Channel 1

| QU | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| median | 6 | 6 | 6 | 5 | 5 | 5 | 5 | 5 | 3 | 3 | 2 | 2 | 1 | 1 |
| mean | 4.52 | 5.30 | 5.50 | 5.35 | 5.23 | 5.40 | 5.22 | 4.76 | 3.58 | 3.24 | 2.49 | 2.23 | 1.63 | 1.36 |

| QU | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| median | 1 | 1 | 1 | 1 | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| mean | 1.26 | 1.09 | 1.10 | 1.04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

Channel 1 is coded with **num_coded_vals = 18 in 93.6% of frames**
(fill_mode 1, no tail fill), and its word length at QU 18–26 is **0 in
≥99.9% of frames**. But it is *not silent* up there: in ≥99.9% of those
frames the code-table section carries the **clone flag** for QU 18–26,
so the decoder copies channel 0's spectrum into channel 1. **Above
≈8.3 kHz, Sony's 64k stereo is dual-mono** — one channel's spectrum,
duplicated. (Ch1 QU 0 is bimodal: median 6, but wordlen 0 — clone or
empty — in 18.7% of frames; use the median, not the mean, there.)

Channel relationship overall: identical word length in both channels for
43.3% of (frame, QU) pairs, within ±1 for 92.9%; ch1 averages 0.45
lower, almost entirely due to the QU ≥ 18 zero region. Ch1 word lengths
are coded by prediction from ch0 (mode 1 in 92.0% of frames, mode 2 in
8.0%) — never independently (mode 3) and never constant (mode 0).

### Scale factors (reference)

Mean scale-factor index declines smoothly from ≈47 at QU 0 to ≈30 at
QU 26, nearly identical in both channels (medians 52 → 34). Ch0 codes
them with a mix of modes 3 (43%), 2 (37%), 1 (20%) — i.e. mostly
VQ-shape/delta codings; ch1 mostly by delta from ch0 (mode 1, 91.5%),
with outright copy (mode 3) in 0.1%. atracdenc computes scale factors
from the signal, so this is a sanity reference, not a table to copy:
a correct 64k encode should land near this curve.

### Where the bits go (mean bits per frame, of 3,008)

| Section | Bits | Share |
|---|---|---|
| Spectrum | 2,544 | 84.6% |
| Scale factors | 194 | 6.5% |
| Code-table indexes | 107 | 3.6% |
| Word lengths | 87 | 2.9% |
| Tail (flags, window, gainc, tones, noise, terminator) | 54 | 1.8% |
| Header + padding slack | ~16 | 0.5% |

### Loud vs quiet frames

Using mean scale-factor index as a cheap energy/tilt proxy and
splitting frames into terciles, the per-QU word-length *shape* is
nearly identical in all three bands — the plateau height moves by
≈±0.5 and the word-length sum by ≈±8 (low-proxy band 78.7/66.0,
mid 69.9/58.2, high 68.3/56.6 for ch0/ch1). Two conclusions: (1) a
**static allocation table is a good model of Sony's encoder** — its
per-frame adaptation is second-order; (2) the proxy mostly tracks
spectral tilt rather than raw level (the lowest-proxy band actually
gets the *most* bits), so don't build a level-dependent table from it.
used_qu stays 27 in all bands; gain control is used more in the
mid/high bands (72–74%) than in the low band (52%).

---

## What atracdenc's 64k allocation should become (E3 spec)

Current atracdenc table (352.8k-shaped, shared by both channels,
from the stage-1 plan): wordlen 7 for QU 0–16, 6 for QU 17–25, then
5, 5, 4, 3, 2, 1. At 64k that shape is wrong in level, in shape, and
in channel symmetry. Replace it, at 376-byte frames, with:

1. **Cap `num_quant_units` at 27.** Sony signals 27 in 100% of frames;
   there is no 28–32-QU content at this rate. (Also keeps
   `TAt3PEnc::CheckFrameDone` shedding inside the legal range.)

2. **Per-channel static tables = Sony's median profile:**

   ```
   ch0: 6 6 6 5 5 5 5 5 4 3 2 2 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1   (sum 69)
   ch1: 6 6 6 5 5 5 5 5 3 3 2 2 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0   (sum 59)
   ```
   Sums sit just under Sony's measured means (72.3 / 60.3), so the
   existing budget-shed engages on busy frames about as often as
   Sony's own coded-count varies. If a single shared table must be
   kept temporarily, use the ch0 row for both channels — but the
   ch1 QU 18–26 zeros are worth real bits (≈9 QUs × 64–128 lines),
   so make the table per-channel; `TConfigure` already loops channels.

3. **Implement the spectrum-clone flag for ch1 QU 18–26.** With
   wordlen 0 there, atracdenc must write the clone-master flag (0)
   in the code-table section for those QUs (mode 0 already reads a
   1-bit flag per such QU on the decode side). Without it, ch1 is
   silent above 8.3 kHz instead of dual-mono like Sony's discs —
   a format-legal but audible difference. This is a small, isolated
   writer change in `TQuantUnitsEncoder`.

4. **Shed order (when over budget):** mirror Sony — thin the *coded
   count* (drop top coded QUs toward wordlen 1 in ch0, keep the
   fill-1 tail) rather than dropping whole top QUs below 27, and
   never shed ch0's QU ≤ 26 tail below wordlen 1. Sony's floor is
   wordlen 1 across the whole band in ch0; it never gives ch0 a
   zero-wordlen QU above the bass in this corpus (zero_pct ≤ 0.5%
   everywhere in ch0).

5. **Leave tones and noise OFF at 64k.** Sony uses them in 0 of
   9,818 frames. Keeping atracdenc's tonal component disabled at
   this rate both matches the reference encoder and sidesteps the
   `NumQuantUnits < NumToneBands` abort landmine flagged in the
   stage-1 plan (E2) for this rate. Gain control: Sony uses it in
   ~2/3 of frames, but it is optional in the format — atracdenc's
   current gainc-off output remains valid; adding gain control is
   a quality refinement for later, not an E3 requirement.

6. **Coding-mode note for later stages:** Sony codes ch0 word
   lengths with mode 3 (99.8% of frames; mode 0 in 0.2%) and ch1 by
   prediction from ch0 (modes 1/2). atracdenc already writes mode 3
   for both channels independently — valid, just less efficient.
   Matching Sony's inter-channel prediction is an E5-class
   optimization, not needed for a correct 64k encode.

**Expected check for E1/E2 output:** a 64k atracdenc encode parsed by
this parser should show num_qu = 27, wordlen sums near 69/59 before
shedding, spectrum ≈ 2,400–2,600 bits/frame, and total consumption
≈ 2,950–3,006 bits with terminator `11` — the same envelope as the
Sony frames measured here.
