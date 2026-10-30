# Study Notes - 2026-10-22 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-10-23T05:24:17Z -->

## Where the goal stands

One line: *everything is finished except the cipher.* The disc layout is fully mapped and byte-faithful in code, the 64 kbps encoder workstream is closed, the author is published to a private GitHub repo, and the only open RE problem is the burn-time encryption, now localized to the SAL bytecode engine with a live emulator harness parked at a well-lit frontier. Lola's own framing from tonight (2026-10-22 ~16:05 PDT, America/Los_Angeles): the project order is Disc A (Sony-encoded track in our layout + cipher — if her D-NE1 plays it, format work is right), Disc B ladder (same track via atracdenc — if it plays, the free encoder is accepted), then full discs, then the native Swift/AppKit app for her Intel Macs. Web app first, native Mac second — both from one shared pipeline core.

Standing constraints, all reaffirmed tonight: ATRAC project work stops at 50% of the free weekly usage (meter ended tonight at ~41%); everything pauses at 90%; RR3 keeps the back half. The Toshiba SonicStage crash thread stays parked — tonight's registry read was file-gathering, not debugging. Only her D-NE1 decides playable/unplayable, never files or documents.

## Tonight's session (2026-10-22, ~10:37–22:22 PDT) — what changed

### SESSION02 solved (14:58 PDT; goal update `goal_update_05839d3f30ad`)
Lola's ImgBurn screenshots of disc 1 settled it: Sessions: 2, Status: Incomplete, State of Last Session: Empty, Next Writable Address 356,361 — while the TOC holds only Session 1 (Track 01, Mode 1, LBA 0, 344,959 sectors, lead-out at 344,961). Verdict: a SonicStage ATRAC CD is session 1 (the music) plus an **open, empty session 2** — the append slot SonicStage leaves so tracks can be added later, never closed on this disc. The D-NE1 displays SESSION02 because that is its name for the disc's last session. Both earlier theories were half right: the two-session shape is real, and the append feature is why it exists. The 11,400-sector gap (356,361 − 344,961) is session 2's reserved lead-in. Recorded in `files/stage1-two-session-brief.md`.

### Disc-1 imaging closed; the zeros lesson (13:46–15:45 PDT)
- The first whole-device image (846,358,528 B) was **all zeros**, MD5 d2e2550e5185db37bda391774c0e54c6 at both ends. Root cause, owned in main chat: `dd conv=noerror,sync` zero-pads failed EINVAL reads while still counting records — records-in==records-out proves nothing about content. Standing lesson now in `~/AGENTS.md`: content-verify every image before reporting success.
- The slice-device read worked: 344,961 × 2048 = 706,480,128 B in ~940 s (MD5 4d69eb97959ab6c18fc04cdc2421bb2b). Readout (`files/stage1-disc-image-readout.md`): one plain ISO 9660 volume, **blank volume label**, 493 tracks, tight-packed descriptors, zeroed 512-B descriptor tail, single-pass burn (2026-09-20 21:13). Only the 2 lead-out sectors were unreadable — the track image is complete.
- ImgBurn's raw BIN (2352-byte sectors) then **verified byte-identical** against the Mac slice: all 344,959 sectors' data payload hashed as one stream → identical MD5 a8f5b3f3… from both rips; BIN structurally sound (sync bytes, Mode 1 headers, exact sector addresses; file MD5 4d8daf11bf54105df18a90b5c7a6da65). Two rips, two machines, two OSes, one track. (One honesty note from main chat: the first comparison pass falsely reported all-mismatch because the check script forgot to rewind the file; the corrected hash pass is the verdict.)

### Cipher location closed; readouts #5–#9 (morning, in goal timeline + `files/`)
- Full 233 MB registry export from the Toshiba contained **no ATPCDEKB anywhere**; the `Contents` folder was empty. Verdict (recorded ~23:56 PDT prior evening): the key material lives **inside atpcd.ocm itself**, not in the registry.
- Pairs: every .ATP = audio + exactly 1,120 B; real cipher confirmed (no ECB, no keystream reuse, per-instance seeds); the 8-field plaintext header half-decoded. Disc-2's 172-B STK is byte-identical to disc 1's = a fixed Sony EKB record. Ignite .OMAs gave 1 plaintext vs 4 ciphertexts as test vectors.
- Readouts #10–#16 (all in `files/`): #10 salwrap loader has no cipher (zlib only, no machine binding); #12 no native cipher at all — the transform lives in the SAL bytecode layer (init.ocm bootstrap); #13 no opcode dispatch — a continuation machine with 12-byte work frames, value grammar recovered; #14 class-01 modules carry an 8,214-B plaintext skeleton (first per-module byte at +8211), atpcd is class-02; #15 class-02 cluster blocks (atpcd/lgd share identical 8,471 body bytes), shared-keystream theory killed; #16 block-pool analysis negative with controls.

### Encoder E0–E5 closed (in `files/stage1-e*.md`)
E0 measured Sony's 64k recipe (27 quant units, static profile, ch2 clone above 8.3 kHz, no tones); E1+E2 produced the first real 64k encodes (5/5 checks, 352.8k path byte-identical, −19 dB tone trap fixed); E3 installed the Sony profile (energy above 3.4 kHz 0→14%, above 8.3 kHz 0→9.1%, 23/23 tests); E5 verified all 9 rungs 48k–352.8k. Encoder workstream closed. (Context from the 2026-10-21 note still governs: the D-NE1 manual documents only 48/64 kbps ATRAC3plus, so 64k is the critical rate and a 352.8k test disc is a rate probe, not an encoder verdict.)

### Author: Step 1 — byte-faithful writer; repo published (15:55–16:05 PDT)
- pycdlib replaced with a **hand-written ISO 9660 writer** mirroring Primo's layout exactly. Proof: disc 1's real 502-entry file set reproduces the disc exactly — 344,809 sectors, every file extent, both path tables byte-identical; fresh descriptor matches the real disc except size/timestamps. Blank label, blank system ID, zeroed tail. Capacity gate now holds back **11,709 sectors** (post-gap, lead-outs, session-2 lead-in, closing allowance — each term measured off her disc) and refuses at the boundary. Validation 30/30; zero third-party dependencies (stdlib only). Commit `148c2c6`.
- Published to **github.com/GlitchedDot/atrac-cd-author** (private, her call), initial commit `179e2cc6`, 17 files. **Sony-data policy enforced:** the 172-B STK record was scrubbed to a loader (env var or repo-root file, size+magic checked, clear error when missing); `out/`+`work/` (145 MB of artifacts/audio) excluded. Lola's working tree is untouched and keeps the embedded STK for local use.
- `sal-research/` added (commit `c5ecca0`, 33 files): `unicorn/sal_emu.py`, `host/`, `tools/` (readouts #11–17 scripts), `wine/` (ptrace wrappers), full `readouts/` paper trail, and a README stating the frontier and success criteria. **Deliberately excluded:** memory dumps (contain Sony code/data) and Ghidra decompilations of Sony binaries. Final state pushed as `7c5265d` (sal_emu.py 85,244 B; readout #20 addenda 5–6).

### Claude as second reviewer — three real bugs (19:22 PDT)
Lola sent Claude the GitHub publish tree. Claude found three edge cases; all three were verified against the actual code in main chat:
1. `clamp_string` slices by code point, not UTF-16 unit — emoji titles overflow the 60-byte NDB field; lone surrogates crash outright. (Matters for the web app's messy libraries, not her ID3v1.1 workflow.)
2. Bare `StopIteration` in `sti.py` when groups don't cover every track — should fail with words.
3. `iso.py` wall-clock timestamps make seeded builds non-reproducible — testability, not a bug; add a `timestamp` parameter.
- Standing arrangement: **Claude does bounded fixes/tests on published trees; Muse diffs, re-validates against her reference discs, and merges/publishes — one tree, one merge point.** The exact reply text was given to Lola to paste back (fix all three + self-contained test suite, zip, minimal, don't touch stk_data.py). Claude's patched zip is expected after her free chat refreshes (~23:30 PDT); the merge is an open thread for tomorrow.
- Claude Pro advice given: $20/mo fits her usage pattern (headroom + Claude Code CLI, which runs on Intel Macs); skip Max; changes nothing hardware-gated.

### OpenCode live on the 2018 Mac mini (21:23–22:22 PDT)
- OpenCode 1.19.4 installed via the official curl installer (not Homebrew — refuses Intel Macs); repo cloned to `~/atrac-cd-author` on the mini.
- Git auth: fresh fine-grained PAT scoped to `atrac-cd-author`, Contents read/write (GitHub killed password auth years ago — the password prompt can never accept a real password).
- Config `~/.config/opencode/opencode.json`: provider "Ollama (gaming PC)" → `http://10.0.0.13:11434/v1`, qwen3:8b default, 32k window. Verified on screen: "Build · Qwen3 8B — Ollama (gaming PC)". Smoke test ("what does this project do?") was the last open step at bedtime.
- Same lane as Claude: the mini's copy carries the dummy-STK loader by design (no playable discs from there); **validation stays on Muse's side** — `validate.py` needs her reference discs, which live here, not in the repo.

### SAL phase 7: static spent, Wine dead end, Unicorn frontier (16:11–22:04 PDT)
- **Readout #17** (`files/stage0-readout-17-phase7-opening.md`): the class-01 8 KB chunk carries no AES/SHA/MD5/CRC/Blowfish/TEA fingerprints (encoded content, not a key table); no periodic keystream at any period ≤ 8,192 B; init.ocm = 13-byte family head + 582 KB fully opaque — the decoder primes inside salwrap's runtime before any module loads. Static tricks spent; the road left is dynamic.
- **Readout #18** (`files/stage0-readout-18-phase7-dynamic-wine-verdict.md`): Wine 11.20 runs, prefix staged with OpenMG keys + her real Sony tree, but Wine's **32-bit trap-door handler drops in this sandbox** — the no-reserve memory patch caused 4.6M faults (→0 with 6 GB real backing), and the fixed patch hit a second hot-syscall spin before the first instruction; 64-bit worked throughout. Wine road closed; fallback = Unicorn emulator driven directly.
- **Readouts #19–#20** (`files/stage0-readout-19-unicorn-seh-and-vm-stack.md`, `stage0-readout-20-unicorn-probe-cycle.md`): the harness loads both real Sony DLLs, runs all 40 startup constructors, and got deep into the SAL bootstrap. Model recast twice: the per-cycle code is a **patch-applier** (queues (address, value) pairs, VirtualProtect in 64-byte units); the 56-byte "frames" are continuation frames. The apparent "hang" was the bootstrap committing stack one page at a time via deliberate self-faults — with the real 1 MB reserve (read from Omgjbox.exe) the phase runs in ~1.5 s. The wrong-door hypothesis **tested and confirmed**: routing cycle 2 to the splice handler ran ~3× more real work. Current frontier (addendum 6): the engine's second march lays frames over its own exception-handler registration — zero registration writes between install and crash — so the shim's return path never runs here; next thread is why. Reserve-depth sweep (6 variants) came back negative, ruling out alignment. **Parked deliberately at 41% meter**; the full trail is in the repo for the mini.

### Meter discipline held
Session started at 31%, ended at ~41%. Lola's words (21:27 PDT): "continue and Ill get back to RR3 once this gets to 50%." CT (RR3 input-logging build) is waiting on her Vita whenever she wants the rematch.

### Web client upload failure (22:09–22:14 PDT)
Any file sent via the web client fails with "failed to attempt" — every file, not size/type specific; the iOS app works. Feedback filed with the Muse team as a private note at her "Send it" (wording quoted her report verbatim, no personal context). Route attachments through iOS until fixed.

### Side note (off-goal, informational)
`PHONE_PATCHES 2.zip` (159,234,887 B, SHA-256 77bb3783…dddcc26) was identified as **hatoving's Monument Valley Vita port conversion kit** (v1.0.1, 2022-12-17): 58 `.xdelta` patches; `executable.xdelta` = Android `libunity.so` → Vita `eboot.bin` (SCE/ELF header inside); data patches for level0–23, sharedassets, `Assembly-CSharp.dll` (Unity 2017.4.2f2); smoking-gun strings (`monumentvalleygame.com`, `ustwogames`, composer Stafford Bawler). It's the can't-ship-the-game distribution trick — inert without her own Android copy. Unpacked at `~/workspace/phone-patches-inspect/`.

## Already Covered in Main Chat
- Lola's ImgBurn screenshots proved disc 1 is two sessions (music + open empty append slot); main agent gave the full SESSION02 verdict and folded the 11,400-sector reservation into the capacity model.
- Main agent owned the all-zeros dd image and logged the `conv=noerror,sync` lesson; the slice image and the ImgBurn BIN were both verified byte-identical (MD5 a8f5b3f3…).
- Lola asked what "into the author" meant; main agent explained the author is the disc-assembly program and what folding the findings in changes.
- Lola chose a private repo with no Sony-risky material; main agent published `atrac-cd-author` (STK scrubbed to a loader) and reported each commit back with read-back verification.
- Main agent reported Step 1 done (hand-written Primo-faithful ISO writer, 148c2c6) and named SAL phase 7 as the remaining road to Disc A.
- Main agent verified all three of Claude's bugs against the code, ranked them, gave her the paste-back text, and advised Claude Pro ($20/mo, skip Max).
- Main agent walked Lola through the mini token/clone/OpenCode setup step by step, pushed the harness + readouts to the repo first, and verified the final screen.
- Main agent narrated the whole Wine fight (ptrace → seccomp → cap-mode → dead end) and the Unicorn harness's deepening runs, parking it at 41% per her 50% rule.
- Lola reported web uploads always fail with "failed to attempt"; main agent troubleshot, then drafted and sent the Muse-team feedback at her word.
- Main agent gave the honest CPU answer (2 cores visible, CT build pegs them, ~150 MB free during compiles) when she asked about headroom for both projects.

## Open questions and watch items
- **Claude's patched zip** (~23:30 PDT tonight): diff against the tree, re-run validate.py 30/30 against her reference discs, merge + push. Nothing in it may carry Sony bytes; `stk_data.py` stays the loader.
- **OpenCode smoke test** on the mini ("what does this project do?") — unconfirmed at bedtime; if qwen3:8b answers, the mini→gaming-PC loop is live.
- **SAL frontier**: why the shim's return path never runs in the harness (readout #20 addendum 6) — next session's thread, inside the ATRAC 50% budget.
- **Disc A** still needs the real cipher; the matched-pair route (clean library .OMA vs burned .ATP twin) and the registry-EKB export were the two live routes named before phase 7 — phase 7's dynamic path is the current bet.
- **D-NE1 acceptance of 256/352.8k**: still only answerable by her hardware; do not pre-judge in anything user-facing. The 64k-first sequencing from the 2026-10-21 note still holds.
- Chime dispute #23165421: window closed 2026-10-22; the Oct 18 follow-up draft is ready to paste if the $59 credit hasn't landed (off-goal, finance — noted only as a pending thread).

## Research Trajectory

### External sources viewed
- None this run. The substance came from the run's own conversation evidence (full main-chat transcript for 2026-10-22T05:24:38Z–2026-10-23T05:24:16Z, 207 conversation handles, read in full across both chunks) and the goal record below. No web research was needed: every finding was produced or verified inside the session.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-21/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. It ends at "Batch-2 DLLs pending"; everything in this note's findings section postdates it. Its two durable findings (D-NE1 manual 48/64 kbps only; atracdenc's hardcoded 2048-byte frame) still govern sequencing and were not re-derived.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/briefs/D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html` — filename-checked via repetition search; its topic (the bitrate ceiling) does not overlap tonight's topics.
- Goal record `goal_e35963ec4aae` via `user_goal.get` — full timeline read (49 updates); the updates from `goal_update_ad4491401084` (SESSION2 observation) through `goal_update_4956fa3fa937` (phase 7 #17) are the same session this note preserves. Goal files `files/stage0-readout-{3–20}*.md` and `files/stage1-*.md` confirmed present on disk as the canonical paper trail.
- Repetition search (required): keyword variants `SESSION02|session 2|two-session`, `github|atrac-cd-author|repo`, `pycdlib|iso writer|hand-written`, `claude|opencode|mac mini|ollama`, `wine|unicorn|init.ocm|phase 7|readout #17/#18/#20`, `imgburn|byte-identical`, `failed to attempt|upload fail|feedback` — grepped over `agent_notes/` and `briefs/` including filenames. Zero topical hits: the atracdenc-repo and byte-identical-output hits are the third-party encoder, not Lola's work. The single `github` hit in the brief is the atracdenc source link.

### Scaffolds and support tactics
- None applied. This is an outcome/project goal (category: interests); the study task plan's teach-mode scaffolding was treated as scheduler metadata per the step instructions, consistent with the 2026-10-21 note. No mastery estimate made (fewer than three observed performances, and the goal is not a skill).

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline, briefing history, file associations). No other connector data was relevant to this RE/build goal tonight.

### Image references checked
- None opened this run. Lola's ImgBurn screenshots, the OpenCode-on-mini photo, and the git-password photo were analyzed live in main chat and their verdicts are preserved above; avatar state is not relevant to this technical goal.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis): the 50%/90% usage guardrails, the mini-mirror + Claude-lane arrangements (already in MEMORY.md), the parked SonicStage thread, RR3 priority, "verify on disk before announcing," terminal labeling, and the never-declare-playable rule — all applied in the session and reflected above.

### Searches skipped or unavailable
- `muse.context_fetch` (conversation category) was not separately called: the run evidence already carried the complete recent main-chat transcript for the window, read in full, which is what that fetch would have returned.
- No web searches: the night's findings are primary evidence from Lola's hardware, discs, and the VM's own analysis — there was no external fact to look up.
