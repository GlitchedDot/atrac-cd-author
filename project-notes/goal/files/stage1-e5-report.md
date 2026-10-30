# Stage 1 — E5 report: the full ATRAC3+ bitrate ladder, verified

Date: 2026-10-22. Tree: `~/workspace/atracdenc-test/` at pinned upstream commit cb17070, carrying E1+E2+E3. **E5 changed no source code** — every rung passed, so there was nothing to fix; the tree's `git status` still shows exactly the five E1–E3 files. Tree left built (`build/src/atracdenc`, Release/libsndfile); unit tests 23/23 pass.

## Method

- Test signal: synthesized 10 s 44.1 kHz stereo WAV in the same style as E1+E2/E3 (seeded, deterministic): detuned chord pad 0–3 s (with a quiet 9.5 kHz partial), pure sines 440/554 Hz 3–5 s, bass + arpeggio + highpassed-noise hats 5–8 s, broadband noise swell 8–10 s. A mono mix of the same material was used for the mono spot checks. (The E1/E2 and E3 stages' own WAV files were not retained on disk; see the regression section for how that was handled.)
- Per rung: encode to `.oma` and to `--container raw` under `timeout 120`; ffprobe the `.oma`; check the raw stream size is an exact multiple of the rung's frame size; run the E0 parser (`e0_profile/parse_at3p.py`) over the raw stream at the rung's frame size; ffmpeg-decode the `.oma` and check duration/sample count/RMS. Every encode in the matrix was run twice end-to-end with identical results (the encoder is deterministic).
- The ladder helper (`Atrac3PlusFrameSizeForBitrate`) exposes nine frame sizes; each was selected with the obvious `--bitrate` value (48/64/96/128/160/192/256/320, and no flag for 2048). The encoder's own info print confirmed the intended frame size at every rung.

## Results — stereo, all nine rungs

| Rung | Frame (B) | Expected bps | ffprobe bps | Encode rc | Frames parsed | Terminator `11` | Decode | Samples/ch | RMS |
|------|-----------|--------------|-------------|-----------|---------------|------------------|--------|-----------|-----|
| 48k  | 280  | 48,234  | 48,234  | 0 | 216/216 | 216/216 | clean | 442,368 | 0.100 |
| 64k  | 376  | 64,772  | 64,771  | 0 | 216/216 | 216/216 | clean | 442,368 | 0.102 |
| 96k  | 560  | 96,469  | 96,468  | 0 | 216/216 | 216/216 | clean | 442,368 | 0.096 |
| 128k | 744  | 128,166 | 128,165 | 0 | 216/216 | 216/216 | clean | 442,368 | 0.096 |
| 160k | 928  | 159,863 | 159,862 | 0 | 216/216 | 216/216 | clean | 442,368 | 0.097 |
| 192k | 1112 | 191,559 | 191,559 | 0 | 216/216 | 216/216 | clean | 442,368 | 0.097 |
| 256k | 1480 | 254,953 | 254,953 | 0 | 216/216 | 216/216 | clean | 442,368 | 0.098 |
| 320k | 1848 | 318,347 | 318,346 | 0 | 216/216 | 216/216 | clean | 442,368 | 0.100 |
| 352k | 2048 | 352,800 | 352,800 | 0 | 216/216 | 216/216 | clean | 442,368 | 0.101 |

ffprobe's stream bit rate is the EA3 header value; it lands within 1 bps of the grid value at every rung (64,771 vs 64,772 is the header's rounded nominal, the same value ffprobe reports for Sony's own 64k files). Raw stream size was an exact multiple of the frame size at every rung (216 frames each). No encode timed out, aborted, or printed an error; all exit codes 0, each encode a few seconds at most.

### Allocation sanity (E0 parser, per rung)

| Rung | Alloc budget (bits) | Bits used min / mean / max | Frames over alloc budget* | Frames over physical frame | num_quant_units distribution | Tones frames |
|------|--------------------|----------------------------|---------------------------|----------------------------|------------------------------|--------------|
| 48k  | 2,237  | 1,319 / 2,139.7 / 2,238 | 5 | 0 | 27 ×216 | 0 |
| 64k  | 3,005  | 1,319 / 2,682.0 / 3,006 | 1 | 0 | 27 ×216 | 0 |
| 96k  | 4,477  | 4,071 / 4,270.1 / 4,478 | 1 | 0 | 13–16 (215), 27 ×1 | 215 |
| 128k | 5,949  | 5,084 / 5,660.3 / 5,949 | 0 | 0 | 16–20 (215), 32 ×1 | 215 |
| 160k | 7,421  | 5,084 / 7,205.6 / 7,422 | 1 | 0 | 18–24 (215), 32 ×1 | 215 |
| 192k | 8,893  | 5,084 / 8,586.9 / 8,893 | 0 | 0 | 20–28 (215), 32 ×1 | 215 |
| 256k | 11,837 | 5,084 / 10,735.0 / 11,836 | 0 | 0 | 23–28 (88), 32 ×132 | 215 |
| 320k | 14,781 | 5,084 / 11,880.6 / 14,736 | 0 | 0 | 25–27 (73), 32 ×143 | 215 |
| 352k | 16,381 | 5,084 / 12,230.6 / 16,284 | 0 | 0 | 27–28 (73), 32 ×143 | 215 |

\* **The "over alloc budget" frames are an accounting artifact, not an overrun** — see below. No frame at any rung exceeds its physical frame size, and the terminator lands intact on all 1,944 stereo frames parsed.

Reading the distributions: at and below 376 B the E3 profile holds `num_quant_units` at exactly 27 on every frame (the deeper 48k shed shows up as lower mean word-length sums, 41.9/29.2 vs 56.4/46.2 at 64k — the ladder thins precision, never units, exactly as designed). Above 376 B the stock behaviour from E1+E2 is untouched: the legacy quant-unit shed against the static table, with the distribution rising monotonically with budget and reaching the full 32 on easy frames at the top rungs. Tones are present in 215/216 frames at every rung ≥ 96k (the one toneless frame is the lead-in), and E2's tonal-drop protection was never needed to rescue a parse — all frames walk cleanly to their terminators. This matches the plan's intent for E5: rungs above 64k get validation, not deep tuning.

### The one-bit question (budget accounting, settled)

At the saturated rungs the fullest frames measure **frame_bits − 2** on the E0 parser (e.g. 3,006 of 3,008 at 64k) — one bit above the encoder's nominal alloc budget of frame_bits − 3. This is a counting offset between the two implementations, verified in the source:

- The **parser's** `bits_consumed` counts from the very first bit of the frame — start bit (1) + unit type (2) included — and stops *before* the 2-bit terminator.
- The **encoder's** budget (`FrameSzToAllocBits = frameSz×8 − 3`, "3 bits is start bit and channel configuration") is checked in `CheckFrameDone` against a consumption count that *excludes* the 3 head bits (written directly by `WriteFrame`) but *includes* the terminator (inserted by the tonal stage before the check).

So a frame sitting exactly at the encoder's budget measures exactly frame_bits − 2 on the parser, at every rung — which is precisely the observed pattern (2,238 / 3,006 / 4,478 / 7,422). The encoder's hard invariant is separately asserted in `WriteFrame` (`GetSizeInBits() ≤ FrameSz × 8`), and the empirical evidence agrees: zero frames over the physical size, zero terminator misses, zero decode errors across 1,944 frames. The budget is respected at every rung.

## Mono spot checks

Channel count comes from the input WAV (the CLI has no separate channel-mode flag). Mono encodes at the smallest rung and at 64k:

| Rung | ffprobe | Encode rc | Raw size | Decode | Samples | RMS |
|------|---------|-----------|----------|--------|---------|-----|
| mono 48k | atrac3p, 1 ch, 48,234 bps | 0 | 216 × 280 B exact | clean | 442,368 | 0.090 |
| mono 64k | atrac3p, 1 ch, 64,771 bps | 0 | 216 × 376 B exact | clean | 442,368 | 0.091 |

The E0 parser cannot score mono frames — it is stereo-only by construction (it rejects unit type 0, which is what a mono frame carries; all 216 frames in each mono stream carry it, as expected). Mono correctness therefore rests on the frame-size exactness, the EA3 header values, and ffmpeg — a full decoder — walking both streams end-to-end without error. E3's mono 64k smoke test result is consistent with this.

## Regression gates

- **64k profile unchanged from E3.** On this stage's test material the parser measures: `num_quant_units` = 27 in 216/216 frames; median word-length profiles **exactly E3's tables** — ch0 `6 6 6 5 5 5 5 5 4 3 2 2 1×15` (median sum 69, max sum 69), ch1 `6 6 6 5 5 5 5 5 3 3 2 2 1×6 0×9` (median sum 59, max sum 59); base ch1 clones 1,944/1,944 (9 per frame × 216, QU18–26); tones in 0 frames. The E3 allocation shape is intact.
- **352.8k default: byte-identical, verified against a pristine build.** The E3 report's MD5 (`c9153a8ae94eb2068a01d6ad50af73fd`) was taken on E3's own test WAV, which was not retained, so that exact number cannot be re-compared. Instead, per the fallback: a fresh checkout of pristine cb17070 was built in a separate worktree (same CMake shape, libsndfile/Release) and encoded this stage's test WAV at the default rate. Its output and the current tree's output are **byte-identical — MD5 `915ce419e0f1e8d055473addde742a8a` for both**. Since E1 already established pristine ≡ E1+E2 at the default and E3 established E1+E2 ≡ E3 on its material, the chain pristine ≡ current tree now also holds on independent material. (The worktree was removed after the check.)
- **Unit tests:** 23/23 pass on the final tree.

## Verdict

The ladder is done: all nine rungs the helper exposes — 48k through 352.8k — plus mono at the two lowest rungs encode correctly, at the exact grid bitrate and frame size, with parseable frames, respected budgets, intact terminators, and clean decodes. No rung failed; no code fix was required, so none was made. What remains knowingly un-tuned above 64k is *quality shape* only (the legacy shed's narrower quant-unit counts at 96k–192k), which the plan explicitly scoped out of E5 — 64k, Lola's standard rate, is the rung with the deep Sony-profile work, and it is verified unchanged.
