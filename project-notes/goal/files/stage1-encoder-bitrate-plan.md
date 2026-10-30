# Stage-1 plan — atracdenc ATRAC3+ bitrate extension (64 kbps first)

Source recon only, 2026-10-21. Tree: `~/workspace/atracdenc-test/`,
HEAD `cb170709f836cb43dc0312455188c791159d81dc` (the build verified
on this VM: ATRAC3+ out at a fixed 352.8 kbps, `--bitrate` ignored).

## Verdict up front

**The 352.8k rate is a parameter that was never plumbed, not a
design woven through the encoder.** In the whole ATRAC3+ path there
are exactly three places the number 2048 (bytes per frame) is
hardwired, and the core encoder already contains — and already
exercises at 352.8k — the mechanism that adapts a frame to a smaller
bit budget (shed quantization units until the frame fits). Adding
64 kbps is therefore:

1. **Plumbing: small.** One new settings field + three call sites.
2. **Bit allocation: the real work.** The encoder's word-length
   allocation is a single fixed table tuned (implicitly) for a
   16,381-bit budget. At 64 kbps the budget is 3,005 bits. A
   rate-aware allocation profile has to be designed and calibrated
   — against Sony's own 64 kbps streams, which we hold (Lola's
   library .OMA files are clean, unencrypted ATRAC3+ 64k).
3. **One landmine to defuse:** an `abort()` in the tonal-component
   path that a small frame budget can plausibly reach (below).

No new quantization/Huffman tables are needed: every table the
encoder uses (VLC spectra, word-length codebooks, mantissa tables,
QU→subband maps) comes vendored from ffmpeg's decoder data and is
bitrate-independent. Nothing in the PQF/MDCT/scaler/GHA analysis
chain depends on the output rate — all other "2048"s in the tree are
the spec-fixed 2048 *samples* per ATRAC3+ frame, true at every
bitrate.

## 1. Code map — where the rate is determined

| # | Location | What |
|---|----------|------|
| 1 | `src/atrac/at3p/at3p.cpp:40` | `TAt3PEnc::TImpl` ctor: `BitStream(out, 2048)` — the frame size in bytes, hardcoded. **The** rate decision. |
| 2 | `src/main.cpp`, `PrepareAtrac3PEncoder` | Container frame size hardcoded twice: `CreateAt3POutput(outFile, numChannels, numFrames, 2048)` (RIFF) and `new TOma(..., OMAC_ID_ATRAC3PLUS, 2048, false)` (OMA). The RAW branch passes no frame size (raw.cpp defaults 0 = pass-through). |
| 3 | `src/main.cpp` mode switch, `E_ENCODE \| E_ATRAC3PLUS` | The parsed `bitrate` variable is **never passed** to `PrepareAtrac3PEncoder` — this is why `--bitrate 64` produces byte-identical output. (ATRAC3 mode does pass it: `TAtrac3EncoderSettings(bitrate * 1024, ...)`.) |
| 4 | `src/atrac3p.h`, `TAt3PEnc::TSettings` | Has **no** bitrate/frame-size field at all — only GHA processing flags. The parameter has nowhere to live today. |

Downstream of those points everything is already parameterized:

- `src/atrac/at3p/at3p_bitstream.h/.cpp` — `TAt3PBitStream(container,
  frameSz)` stores `FrameSz` and derives the allocation budget
  `FrameSzToAllocBits = frameSz * 8 - 3`. `WriteFrame()` emits
  exactly `FrameSz` bytes per frame and asserts the encoded frame
  fits.
- `TTonalComponentEncoder::CheckFrameDone` (at3p_bitstream.cpp) —
  the budget enforcer: if a frame's total consumption exceeds
  `frame->SizeBits`, it **reduces NumQuantUnits (32 → 28, then
  −1 per retry) and re-runs the whole frame encode**
  (`EStatus::Repeat`). Fewer coded QUs = less bandwidth — this is
  the format's own legal rate-adaptation lever: `num_quant_units`
  is signaled per frame in the bitstream header
  (`TConfigure::Encode` writes `Insert(NumQuantUnits - 1, 5)`),
  so any decoder, ffmpeg and the D-NE1's firmware included, accepts
  any value 1–32.
- `TConfigure::Encode` — word lengths come from a **static
  `allocTable[32]`**: wordlen 7 for QU 0–16, tapering 6, 6, 5, 5,
  4, 3, 2, 1 to QU 31. Same table whatever the budget — fine at
  352.8k, wrong shape for 64k (see §4).
- Analysis chain (`at3p_gha.cpp` tonal/gain analysis,
  `at3p_mdct.cpp`, `Scaler.ScaleFrame` over the fixed 32-QU
  `TScaleTable` in at3p_tables.h) — rate-independent; scaled blocks
  for all 32 QUs are always produced, the bitstream layer decides
  how many get coded.

### The landmine

`TTonalComponentEncoder::Encode`, second pass: if the tonal block's
`NumToneBands` exceeds the (possibly budget-reduced)
`NumQuantUnits`, it prints "TODO" and calls **`abort()`**. At
352.8k the budget almost never forces NumQuantUnits that low; at
376 bytes it plausibly can. Any 64k work must clamp tone bands to
the frame's final NumQuantUnits (or gate tonal components off at
low rates as a first cut) before this can fire on real music.

## 2. Frame size ↔ bitrate: the facts

ATRAC3+ at 44.1 kHz: one frame = 2048 samples/channel, so

```
bitrate (bps) = frameSizeBytes × 8 × 44100 / 2048 = frameSize × 172.265625
```

The OMA/EA3 header stores the frame size as a 10-bit field
(framesz = (frameSize − 8) / 8) — see
`src/lib/liboma/src/liboma.c`, `oma_write_atrac3p_header` — so
legal frame sizes sit on the grid **8k + 8**. Two points on the
grid are anchored by hard evidence:

- **2048 B → 352,800 bps exactly.** atracdenc's current output;
  ffprobe-verified in the stage-0 trial.
- **376 B → 64,771.9 bps.** Lola's real discs: 376-byte frames
  everywhere (frame count × 376 = payload, readout #8), and her
  library .OMA probes at 64,771 bps in ffprobe. framesz = 46.

The ladder the header grid admits at 44.1 kHz stereo (the standard
SonicStage ATRAC3+ rates fall on these grid points; each rung
still needs its own decode/D-NE1 acceptance check):

| Frame (B) | framesz | Rate (bps) | Nominal |
|-----------|---------|------------|---------|
| 280 | 34 | 48,234 | 48k |
| **376** | **46** | **64,772** | **64k — target #1** |
| 560 | 69 | 96,469 | 96k |
| 744 | 92 | 128,166 | 128k |
| 928 | 115 | 159,863 | 160k |
| 1112 | 138 | 191,559 | 192k |
| 1480 | 184 | 254,953 | 256k |
| 1848 | 230 | 318,347 | 320k |
| 2048 | 255 | 352,800 | 352.8k — current |

Container side is a pure pass-through: liboma already writes
whatever `info.framesize` it is given ((framesize−8)/8, checked
≤ 0x3FF), and the RIFF writer takes the same parameter. No
container work beyond passing the new value.

## 3. What 64 kbps actually demands of the bit budget

- Budget: 376 × 8 − 3 = **3,005 bits/frame** (vs 16,381 at
  352.8k), for both channels plus all side info (header bits,
  word-length VLC, 6-bit scalefactor indices per coded QU per
  channel, code-table indices, tonal block if present).
- The QU→subband map (`atrac3p_qu_to_subband`, ff data): QUs 0–22
  cover PQF subbands 0–6 of 16; QUs 23–31 cover subbands 7–15 one
  each. Coding ~24 QUs reaches subband 8 (~half the subband
  count); the question is the trade the fixed allocTable makes:
  it spends wordlen 7 on the first 17 QUs, so at a 3,005-bit
  budget the repeat-loop will likely have to shed QUs down into
  the low 20s or below on dense content — legal, decodable, but
  audibly narrower than Sony's 64k, which spreads fewer bits over
  more QUs with smaller word lengths.
- Conclusion: a naive parameter-only 64k will *work* (valid
  frames, right size, ffmpeg-decodable) but is not yet the 64k
  Lola's discs represent. The allocation profile is the
  difference, and it's design + calibration work, not plumbing.

## 4. Borrowed vs invented

**Borrowed from ffmpeg's decoder knowledge (already in-tree):**

- The complete frame layout: the vendored `src/atrac/at3p/ff/`
  tables (VLC spectra codebooks, word-length Huffman tables,
  mantissa table, QU→subband and power-group maps) are
  rate-independent — the same tables decode a 64k frame and a
  352.8k frame. The bitstream writer built on them needs no new
  tables at any rung of the ladder.
- The proof that per-frame `num_quant_units` is the sanctioned
  bandwidth lever: decoders read it from the stream; there is no
  fixed QU count per bitrate in the format.

**Encoder-side invention (the actual project work):**

- A rate-aware word-length allocation to replace/augment the
  static `allocTable` — how many QUs to code and at what word
  lengths for a 3,005-bit stereo budget, including how much to
  reserve for tonal components (or whether to suppress them at
  64k initially).
- Gain-control / GHA behaviour at low budgets (the GHA path is
  actively developed upstream and tuned at 352.8k).

**The calibration asset that de-risks the invention:** Lola's
library .OMA files are *Sony's own* 64 kbps encodes, clean and
unencrypted. A small bit-parser following ffmpeg's documented
decode order can extract, per frame, Sony's actual choices —
num_quant_units distribution, word-length profile per QU,
scalefactor ranges, tonal usage — giving the allocation design a
measured target instead of a guess. (The .ATP files on her discs
are the same encodes but encrypted at burn; the library .OMAs are
the usable source.)

## 5. Staged work plan

- **E0 — Calibrate (desk, no encoder changes).** Parse a handful
  of frames from Sony 64k library .OMAs; record QU counts,
  wordlen profiles, tonal presence. Output: the target profile
  the 64k allocation should approximate.
- **E1 — Plumb the parameter.** Add `FrameSize` (or Bitrate) to
  `TAt3PEnc::TSettings`; pass it to the `TAt3PBitStream` ctor and
  to both container call sites in `PrepareAtrac3PEncoder`; wire
  `--bitrate` through for the ATRAC3PLUS mode (validate against
  the ladder, framesz grid). Add a unit test alongside the
  existing `at3p_*_ut.cpp` tests: encode 1 s of a test tone at
  376 B and assert every emitted frame is exactly 376 B and the
  .OMA header framesz reads 46.
- **E2 — Survive the budget.** Defuse the tonal `abort()` (clamp
  NumToneBands to final NumQuantUnits; if that proves fiddly,
  ship 64k initially with tonal components off via the existing
  GHA flags). Encode real music at 376 B; verify: no aborts,
  exact frame sizes, ffmpeg decodes cleanly end-to-end,
  duration/sample count exact.
- **E3 — Allocation profile for 64k.** Implement a rate-keyed
  word-length table (and QU ceiling) informed by E0's measured
  Sony profile. Compare against the naive E2 output by decoded
  listening + spectrum/bandwidth inspection. This is the quality
  stage; iterate here, not in E1/E2.
- **E4 — The D-NE1 verdict.** Feed the 64k encode into the disc
  pipeline as **Disc B** (already the project's planned test):
  burned, played, judged by Lola's ears and the D-NE1's screen —
  the only acceptance that counts.
- **E5 — Ladder.** Repeat E1's plumbing validation + a lighter
  E3 pass for 96k/128k/192k (and 48k if wanted) — each rung is the
  same mechanism with a bigger budget, so returns diminish fast
  after 64k; 64k gets the deep tuning because it's Lola's
  standard rate.

## 6. Mac Intel build notes (for the app stage)

- Same shape as this VM's verified build: CMake (C++17,
  `src/CMakeLists.txt`), PCM I/O via **libsndfile**
  (`ATRACDENC_PCM_IO_BACKEND=libsndfile`; Homebrew's libsndfile
  ships x86_64). No other external deps for encoding: liboma and
  libgha are vendored under `src/lib/` (libgha is the one git
  submodule — the app-stage source snapshot must include it
  checked out, as it is here).
- The encoder core sets the FP rounding mode at bitstream
  construction (`NEnv::SetRoundFloat`) — plain x87/SSE territory,
  fine on Intel Macs; nothing Apple-Silicon-specific anywhere in
  the tree, and no SIMD intrinsics in the ATRAC3+ path that would
  block an Intel build.
- Upstream is *actively* developing the GHA/tonal code (recent
  commits rework gain/harmonic handling) — the app should pin the
  commit it builds against (this recon: cb17070) rather than
  track HEAD, and carry the bitrate work as a small local patch
  series on top, since E1 touches main.cpp plumbing upstream
  might later adopt.
