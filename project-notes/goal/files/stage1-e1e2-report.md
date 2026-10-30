# Stage 1 — E1+E2 report: atracdenc ATRAC3+ bitrate plumbing + budget survival

Date: 2026-10-22. Tree: `~/workspace/atracdenc-test/` at pinned upstream commit cb17070 (not pulled/updated). Diff: 5 files, +131/−15. Tree left built (`build/src/atracdenc`, Release/libsndfile, same CMake shape as stage 0).

## E1 — the rate is plumbed

- **`src/atrac3p.h`** — `TAt3PEnc::TSettings` gains `uint32_t FrameSize` (default 2048). This is the only new settings field.
- **`src/atrac/at3p/at3p.cpp`** — TImpl now constructs `BitStream(out, settings.FrameSize)` instead of the hardwired 2048.
- **`src/main.cpp`**
  - New helper `Atrac3PlusFrameSizeForBitrate(kbps)`: snaps a requested `--bitrate` to the nearest rung of the standard ladder {280, 376, 560, 744, 928, 1112, 1480, 1848, 2048} bytes (bps = frameSize × 172.265625 at 44.1 kHz); 0 (no `--bitrate`) → 2048.
  - `PrepareAtrac3PEncoder` takes a `frameSize` parameter and uses it at **both** container call sites (`CreateAt3POutput` RIFF branch, `TOma` OMA branch) and assigns `settings.FrameSize`. The ATRAC3PLUS call site passes `Atrac3PlusFrameSizeForBitrate(bitrate)` — `--bitrate` is now honored for atrac3plus (it was silently ignored before; verified fixed: `--bitrate 64` output is no longer byte-identical to default).
  - The info block now prints the effective `Bitrate` and `FrameSize`.
  - EA3 header: nothing to do — liboma stores `(framesize−8)/8` and passes any grid value through (376 → 46, fits the field). Verified in the output: ffprobe reads exactly 64 kb/s.

Sanity anchors: 64→376 (64,771 bps), 48→280 (48,234), 128→744 (128,165), 352→2048, 384→2048, 32→280.

## E2 — survive the budget (three layers)

1. **Tones gate (the faithful behavior) — `at3p.cpp`.** `AdjustSettingsForFrameSize` clears `GHA_WRITE_TONAL` in the effective settings when `FrameSize <= 376`, and `EncodeFrame` now runs the GHA analysis only when that flag is set. **Why the analysis itself had to be gated — the surprise of this stage, see below.** With the flag cleared: no subtraction, no tonal block, `delay` never stores — spectrum codes the full signal, exactly Sony's 64k shape (E0: tones in 0/9,818 frames).
2. **Abort clamp (defense in depth) — `at3p_bitstream.cpp` + `at3p_bitstream_impl.h`.** The `std::cerr << "TODO"; abort();` in `TTonalComponentEncoder::Encode`'s repeat-pass branch is gone. On the NumToneBands > NumQuantUnits violation, the new `DropTonalBlock()` erases the buffered tonal segment from the stage's buffer (positions recorded on the first pass: `TonalFlagPos`/`AfterTonalPos`), inserts a single "no tonal component" flag, nulls `specFrame->TonalBlock`, refreshes `BitsUsed`, and falls through to `CheckFrameDone`. Unreachable at the gated rungs by construction; protects the mid/high rungs where tones stay on.
3. **Shed floor — `CheckFrameDone`.** Shedding stops at NumQuantUnits = 1 (accept the frame) instead of decrementing to 0 (which would corrupt `Insert(NumQuantUnits − 1, 5)` and could loop). Unreachable in practice (a 1-QU frame is a few hundred bits vs the 3,005-bit budget) but removes the pathological corner at 376 bytes.

**Re-encode storms:** none observed. The shed is inherent to the current allocation table (see Quality below) — each over-budget frame re-runs the pre-tonal stages once per shed step, but the full 10 s test file encodes in ~1.5 s at 64k. Not a practical problem; E3 reduces the shed depth itself.

## ⚠️ The surprise: tones are a subtraction, not an add-on

First implementation gated only the bitstream *write* (the design sketched in the E0/E-plan notes said the GHA processor "regenerates tones into the spectrum path" — close, but the direction matters). Result: frames were valid but decoded audio lost tonal energy — pure 440/554 Hz sines came back **−19 dB**, chord pad −2.3 dB, bass/arp −8 dB, noise least affected. Reading the vendored `ff_atrac3p_generate_tones` (ff/atrac3plusdsp.c) found the tail comment **"Overlap and subtract to get residual"** — `out[i] -= wavreg1[i] + wavreg2[i]`. The encoder's design: GHA synthesizes the tones, **subtracts** them from the signal, the MDCT codes the residual (`GHA_WRITE_RESIUDAL`), and the decoder restores the tones from the tonal block. Suppress the block but keep subtracting and the tonal energy is deleted permanently. The fix (layer 1 above) gates the whole mechanism on the one flag. After the fix, decode levels match the input to ~0.02 dB on tonal/transient content (table below). This also means the summary note "suppressing only the WriteFrame tonal block does NOT remove tones from the coded spectrum path" understates it: it removes them from the *decoded output* entirely.

## Validation (all five required checks)

Test signal: synthesized 10 s 44.1 kHz stereo WAV — detuned chord pad (0–3 s), pure sines 440/554 Hz (3–5 s), bass+arpeggio+noise hats (5–8 s), dense noise swell (8–10 s).

1. **Build:** clean with the existing CMake configuration (only pre-existing warnings in untouched quantizer code). **Unit tests: 23/23 pass** (`ctest`).
2. **64k encode** (`-e atrac3plus --bitrate 64`): encoder reports 64,771 bps / 376 B frames. ffprobe: `atrac3p, 44100 Hz, stereo, 64 kb/s`, duration 10.03 s. Raw stream = 216 frames × 376 B. **E0 parser: 216/216 frames parse, terminator `11` on all 216, total bits 2,576–3,004 (budget 3,005), tones_present in 0 frames** — the Sony 64k envelope on structure.
3. **Decode back:** ffmpeg decodes with zero errors, 442,368 samples/ch (10.03 s). Segment RMS in → out: chord pad 0.2462 → 0.2466; pure sines 0.3308 → 0.3303; bass/arp/hats 0.2312 → 0.2304; noise swell 0.2816 → 0.1958 (see Quality).
4. **No regression at default:** same WAV, no `--bitrate` → 352,800 bps / 2048 B frames, and the .oma is **byte-identical (MD5 `45f3f28c2818e7f923fd30e026ec4cc3`)** to the output of the pre-change build.
5. **No abort:** every encode ran under `timeout 120` and finished in seconds with exit 0, including the tonal stress segments. The `abort()` in the tonal encoder no longer exists.

## Quality note — what E3 still owns (expected, not a defect of E1/E2)

The naive parameter-only 64k lands **num_quant_units at 10–14** (distribution: 11×94, 14×60, 12×39, 13×20, 10×2, 22×1) because the stock allocTable spends wordlen 7 across the low QUs, so the shed cuts whole QUs — capping coded bandwidth at ~3.4 kHz. Sony's 64k holds **27 QUs on every frame** with spectrum ≈2,544 bits; ours spends 2,330–2,713 spectrum bits but across half the units. Audible consequence in the test: the noise-swell segment (energy above the cap) decodes −3.2 dB; everything below the cap is level-exact. This is precisely the E3 allocation profile's job (cap QU at 27, Sony-median wordlen tables, ch1 clone flag) — deliberately not touched here, per the plan.

## Files changed

- `src/atrac3p.h` — `TSettings::FrameSize` (+9)
- `src/atrac/at3p/at3p.cpp` — BitStream frame size from settings; tones gate + analysis guard (+40/−…)
- `src/main.cpp` — ladder helper, `frameSize` through PrepareAtrac3PEncoder + call site, info print (+43)
- `src/atrac/at3p/at3p_bitstream.cpp` — `DropTonalBlock`, abort removal, shed floor (+43)
- `src/atrac/at3p/at3p_bitstream_impl.h` — `DropTonalBlock` decl + segment-position members (+11)
