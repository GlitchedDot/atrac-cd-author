# Stage 1 — E3 report: Sony's 64 kbps allocation profile in atracdenc

Date: 2026-10-22. Tree: `~/workspace/atracdenc-test/` at pinned upstream commit cb17070 (not pulled/updated), carrying E1+E2 plus this stage. E3 diff: 2 files (`at3p_bitstream.cpp`, `at3p_bitstream_impl.h`). Tree left built (`build/src/atracdenc`, Release/libsndfile).

## What E3 installed

At the 376-byte rung only (gate: frame size ≤ 376, the same gate E2 uses for tones), the ATRAC3+ encoder now writes the allocation shape measured from Sony's own 64 kbps streams in stage E0, instead of shedding quant units against the 352.8k-shaped static table:

1. **Fixed 27 quant units.** `TAt3PBitStream::WriteFrame` starts low-rate frames at 27 QUs (all other frame sizes still start at 32), and the low-rate shed never reduces the count.
2. **Per-channel static word-length tables = Sony's medians** (`TConfigure::Encode`): ch0 `6 6 6 5 5 5 5 5 4 3 2 2 1×15` (sum 69), ch1 `6 6 6 5 5 5 5 5 3 3 2 2 1×6 0×9` (sum 59) — sums just under Sony's measured means (72.3 / 60.3).
3. **The ch1 high-band spectrum clone, exactly as the format defines it.** Ch1 QU18–26 carry word length 0; `TQuantUnitsEncoder` writes no spectrum for them, and `EncodeCodeTab` writes the one-bit clone flag (0) for those units — the field the decoder (FFmpeg grammar, per the E0 parser) reads for a zero-wordlen unit whose master channel is coded. The decoder copies ch0's spectrum into ch1: above ≈8.3 kHz the output is dual-mono, like Sony's discs. No approximation was needed; the writer's code-table section just had never had a reason to emit the flag.
4. **A three-rung shed ladder** replaces quant-unit dropping when a frame exceeds the 3,005-bit budget (`TTonalComponentEncoder::CheckFrameDone` raises `TSpecFrame::ShedLevel`; `TConfigure` / `TQuantUnitsEncoder` apply it on the repeat pass):
   - Levels 0–5: thin every coded word length by one per level toward its floor (1 for ch0 everywhere and ch1 through QU17; 0 in ch1's cloned band). Only precision thins; bandwidth and the 27-QU shape survive.
   - Levels 6–11: extend ch1's clone downward one QU per level (QU17 → QU12).
   - Levels 12–20: mute ch0's top QUs one per level (QU26 down) — the unit keeps its word length, scale factor and code-table entry; only its spectrum is encoded as all zeros, so every section count stays at 27.
   Past level 20 the frame is accepted (termination guarantee; never reached in testing — max level used was 14).
5. **A defensive fix in `TUnit::GetOrCompute`:** candidate code tables are now skipped when the table is *unsigned* and a mantissa cannot fit its coefficient field (unsigned packing is unmasked; an overflowing magnitude overlaps the neighbouring coefficient and can flip a zero/nonzero pattern, changing the sign-bit count and desyncing the frame). Signed tables truncate in place and consume identical bits, so they are not filtered. On all material tested here the filter never fires and changes no output (the 352.8k output is byte-identical with and without it); it removes a latent desync that low word lengths make plausible.

`TSpecFrame` learned the frame size (defaulted constructor argument, 2048) and the shed level; other frame sizes see neither the tables, the clone, nor the ladder — their code paths are the E1+E2 ones, unchanged.

## Why the ladder needs rungs 2 and 3 (the honest deviation)

The E0 shed spec assumed thinning word lengths toward the measured floors would fit the budget, the way Sony's frames do (mean 2,992 of 3,008 bits at word-length sums 72.3/60.3). It doesn't, on dense material: atracdenc's scaler peak-normalizes each quant unit, so at word length 1 a transient-dense 128-line unit still has most coefficients nonzero and costs 50–65 bits; Sony's quantizer evidently sparsifies the tail (their spectrum averages 2,544 bits at *higher* word-length sums). With thinning alone, this test file's floor-profile frames ran 3,028–3,470 bits — over budget, truncated by `WriteFrame`, and unparseable (19 of 216 frames). Rungs 2 and 3 are the format-native headroom that closes that gap without dropping quant units: on this deliberately hostile test signal (highpassed-noise hats + arpeggio transients + a broadband noise swell), 114 of 216 frames (53%) fit at level 0 with the exact Sony profile, 83 use thinning only, 16 extend the clone, and 3 mute one to three top ch0 units. `num_quant_units` is 27 in **100%** of frames and no coded ch0 unit ever goes below word length 1 — the spec's two hard requirements hold; what bends, on the densest few percent of frames, is only *where the clone boundary sits* and whether the top ch0 units carry content.

## Validation

Test signal: synthesized 10 s 44.1 kHz stereo WAV (detuned chord pad 0–3 s; 440/554 Hz sines 3–5 s; bass + arpeggio + highpassed-noise hats 5–8 s; broadband noise swell 8–10 s) — same shape as E1+E2's material, with deliberate energy above 8 kHz.

1. **Build/tests:** clean build; unit tests **23/23 pass** (`ctest`).
2. **64k encode** (`-e atrac3plus --bitrate 64`, under `timeout 120`, exit 0, seconds): ffprobe `atrac3p, 44100 Hz, stereo, 64 kb/s` (64,771 bps), 216 frames × 376 B. **E0 parser: 216/216 frames, terminator `11` on all.** Profile vs E0 targets:
   - `num_quant_units`: **27 in 216/216** (E1+E2 baseline: 10–14).
   - Median word-length profile: **exactly Sony's medians in both channels** (ch0 `6 6 6 5 5 5 5 5 4 3 2 2 1…`, ch1 same through QU17, then `0×9`).
   - Word-length sums: pre-shed table sums 69/59 (maxima observed in output); post-shed means 51.5 / 41.6 on this hostile signal (Sony music corpus means: 72.3 / 60.3 pre-shed-equivalent — the difference is shed depth on synthetic transients, not table shape).
   - Cloned QUs (ch1 wordlen 0 + clone flag, ch0 coded): **2,011** — the 1,944 base clones (9 per frame × 216) plus 67 from ladder rung 2; present in 216/216 frames.
   - Bits: spectrum mean 2,161; total mean 2,741, **max 3,005** (budget 3,005; Sony mean 2,992 — see "remaining gaps").
   - Tones present: 0 frames. Noise present: 0 frames. (E2's gates intact.)
3. **Decode + bandwidth:** ffmpeg decodes error-free, 442,368 samples/ch (10.03 s). Decoded band energy, E1+E2 baseline → E3 (input's own share in parentheses):
   - Full file > 3.4 kHz: 0.0000% → **13.9993%** (input 19.7189%); > 8.3 kHz: 0.0000% → **9.1108%** (input 15.7871%).
   - Hats/arpeggio segment > 8.3 kHz: 0.0000% → **6.5374%** (input 13.2251%).
   - Noise-swell segment > 8.3 kHz: 0.0004% → **41.8777%** (input 62.2618%).
   The ~3.4 kHz cap is gone; decoded content above 8.3 kHz is present throughout, carried in ch1 by the clone band exactly as on Sony's discs.
4. **Regression:** default encode (no `--bitrate`) is 352,800 bps / 2048-byte frames and **byte-identical** to the E1+E2 build's output on the same WAV (MD5 `c9153a8ae94eb2068a01d6ad50af73fd` before and after E3). The 128k rung (744 B) also verified unchanged in behaviour: encodes and parses 216/216 with the legacy quant-unit shed (num_qu 16–19), tones path untouched. A mono 64k encode also completes and decodes (it uses the ch0 table and the same ladder).
5. **No abort/hang:** every encode ran under `timeout 120` and finished in seconds with exit 0, including the tonal/transient stress segments. The E2 tonal-drop protection is untouched; at this rung no frame carries a tonal block at all.

## Remaining gaps (not E3's scope, recorded for later stages)

- **Side-info overhead:** atracdenc still writes scale factors in direct mode (27 × 6 bits × 2 ch = 324 bits vs Sony's 194 via VQ/delta modes) and code-table indexes against the full table (Sony uses the restricted table). Together ≈250 bits/frame that Sony spends on spectrum — the main reason our post-shed spectrum (2,161 mean) runs thinner than Sony's (2,544). Closing this is E5-class efficiency work; it would also shallow the shed ladder's use on dense frames.
- **Gain control** is still never written (Sony uses it in ~66% of frames); optional quality refinement, as noted in E0.
- **Inter-channel word-length prediction** (Sony codes ch1 word lengths by prediction from ch0) remains an efficiency item; atracdenc's mode-3/mode-1 writing is valid.
- E4 (the D-NE1 verdict via Disc B) is unchanged as the acceptance gate for the whole encoder line.

## Files changed (E3 only)

- `src/atrac/at3p/at3p_bitstream_impl.h` — `TSpecFrame`: frame-size member + `IsLowRate64k()` gate, `ShedLevel` state; `EncodeCodeTab` signature gains the word-length vector.
- `src/atrac/at3p/at3p_bitstream.cpp` — Sony per-channel tables + ladder application in `TConfigure`; clone-flag emission and word-length-aware index writing in `EncodeCodeTab`; zero-wordlen skip in `TQuantUnitsEncoder::Encode`; ch0 top-unit muting (ladder rung 3); low-rate ladder in `CheckFrameDone`; 27-QU start for low-rate frames in `WriteFrame`; unsigned-table fit filter in `TUnit::GetOrCompute`.
