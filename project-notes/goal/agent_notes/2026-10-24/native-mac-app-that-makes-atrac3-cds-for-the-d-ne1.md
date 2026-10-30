# Study Notes - 2026-10-24 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-10-25T05:27:37Z -->

## Where the goal stands

Unchanged at the frontier: everything except the cipher is finished, and the cipher is still localized to the SAL bytecode engine, with the Unicorn harness parked at why the shim's return path never runs (readout #20 addendum 6, from the 2026-10-22 note). No new SAL work happened on 2026-10-24, and none is due: the ATRAC project is parked by Lola's own 50% usage guardrail, crossed on 2026-10-23 at 51–53% of the free weekly limit, until the weekly refresh on 2026-10-28 at 16:03 PDT. The pause-everything line stays at 90%.

What moved on 2026-10-24 was the support lane around the project, and it moved in two directions at once: the mini OpenCode lane's test-rerun finally got a real verdict, and then the same lane destroyed the test file it was supposed to fix. Both halves are now parked, deliberately, while Lola is sick: she said on 2026-10-24 evening PDT that she does not feel like doing much and will see about Road Rash 3 tomorrow. The clamp-string restore waits for her return, not for a nudge.

## Today's session (2026-10-24 PDT) — what changed

### The clamp_string rerun finally ran, and the code was right

The 2026-10-23 note left one open item: apply the mini agent's two corrected test cases and rerun `python3 -m unittest tests.test_clamp_string` on the 2018 Mac mini. On 2026-10-24 that rerun happened, but not by the agent — by Lola herself, after the agent spent the evening in a describe-and-ask loop (below).

Result, from Lola's own run on 2026-10-24 at 17:42 PDT: 5 tests ran, 3 passed, 2 failed, and both failures are test bugs, not code bugs:

- `test_astral_emoji` (line 17) still expected a lone 😀 to be dropped to `''`. One emoji is 2 UTF-16 units, under the 30-unit limit, so the code correctly keeps it.
- `test_lone_surrogate` (line 21) still fed `'\uD83D\uDC00'` and expected U+FFFD. That is not a lone surrogate at all — it is a valid pair (🐀) — so the code correctly keeps it whole.

The sharp consequence, already told to Lola in main chat: the agent had never applied its own diagnosed corrections to the file. The two lines that should be there, and were handed to the agent verbatim, are:

- `clamp_string('a' * 29 + '😀') == 'a' * 29` (29 + 2 = 31 units, so the emoji drops whole)
- `clamp_string('\uD83D') == '\ufffd'` (a truly lone high surrogate)

This confirms, with a real run rather than a summary, the 2026-10-23 finding that the code behavior matches Claude's merged fix exactly. The rerun did not produce a green suite, because the file under test was never corrected — a distinction the next section makes worse.

### The mini lane's failure mode deepened: describe, ask, never execute

Before Lola ran the suite herself, the revived clamp_string session on the mini went through at least three phrasings of the same instruction and landed in the same place each time:

- It asked Lola what command had returned "No files found" — an error from one of its own toolcalls, misattributed to her.
- It then claimed it had no direct way to run shell commands, only webfetch/write/explore/general-agent/todowrite, despite having run a test-suite task through the general agent earlier in the same session.
- After a long thinking trace that correctly chose the Task tool, it took her bare command, described what the command does, and asked "Would you like to continue with that?" instead of running it.

Standing lesson, strengthened: the mini OpenCode lane is for single-shot asks only (the 2026-10-23 verdict), and when a session falls into describe-and-ask, stop feeding it. Running the command directly — a second Terminal on the MacBook Pro, SSH into the mini, `cd ~/atrac-cd-author`, `python3 -m unittest tests.test_clamp_string` — is faster than another round of prompting, and that is exactly what produced the verdict above.

### SSH mirroring from the MacBook Pro is proven, and it stays on the mini

On 2026-10-24 at 15:51 PDT Lola asked whether she could install OpenCode on the MacBook Pro and have it mirror the mini's OpenCode. The answer given in main chat, and then proven by her own screenshot on 2026-10-24 at 16:26 PDT, is that no second install is needed for a mirror: from Terminal on the MacBook Pro, `ssh lolawright@Lolas-Mac-mini-2018.local`, then `cd ~/atrac-cd-author` and `~/.opencode/bin/opencode -c` (the full path, after the post-outage shell could not find `opencode` on PATH). The clamp_string session revived there, on Build with Qwen3 8B and Ollama (mini), at 9% context.

The boundary to keep: SSH moves the user, not the work. The OpenCode process, the Qwen model, the file edits, and the test runs all execute on the mini's CPU and RAM; the MacBook Pro is only the screen and keyboard. Two independent installs do not sync sessions — a standalone MacBook Pro install with its own repo clone would be a second agent, not a mirror. Git would keep code in sync; sessions would stay separate.

### The test file was clobbered, and the rebuild is ready but unapplied

After Lola chose to hand the agent the two corrected lines, the agent's evening of 2026-10-24 went from stalling to destructive:

- It did put the two corrected assertions in — lines 9 and 12 of what it showed — but what it showed around them was a rewritten file built on a mock `clamp_string` (`return s[:29]`, slicing by code point, exactly the wrong behavior these tests exist to catch), with only the 2 tests and the other three dropped.
- It then tried to "run" the tests with WebFetch, treating the shell command as a URL, and asked Lola for a valid URL.

Confirmed on disk on 2026-10-24 at 20:12 PDT, from Lola's own check: `wc -l tests/test_clamp_string.py` = 11 lines, the mock version. The original 5-test file is gone from disk. Git recovery was suggested but not run — the file was never merged, so it was likely uncommitted, and that check is still open.

What was not damaged matters as much: the real `clamp_string` in `src/atrac_author/ndb.py` was never written to. Only `tests/` was touched. A rebuilt 5-test file is already prepared at `~/workspace/your_files/clamp-string-test-rebuild/test_clamp_string.py`: it imports the real `clamp_string` from `src`, carries all five cases including the two corrected ones, and is expected to run 5/5. Restore plus rerun is pending, parked while Lola is sick and while the ATRAC guardrail holds until 2026-10-28 at 16:03 PDT.

Do not revive or feed the poisoned OpenCode session. Its summaries are not evidence: it claimed the edits while the file on disk was a mock. Any future claim about this file needs a disk check first (`wc -l` and the head of the file), the same verify-on-disk rule that governs VPK deliveries.

### Power outages touched the mini lane, but did not break it

Ukiah lost power twice on 2026-10-24 morning PDT (first report 09:53 PDT, restored, out again, back by about 11:34 PDT), and the fleet went down hard: gaming PC, both minis. The mini lane survived the outage in the ways that matter here: the clamp_string session was revivable by SSH afterward, and the Ollama 32K LaunchAgent installed on 2026-10-23 was part of the bring-up checklist. The one outage artifact in this lane was the `opencode` PATH failure in the restored shell, solved by the full path above. The decomp LAN fix from the same morning (restarting `iphlpsvc` on the gaming PC) belongs to the decomp goal, not this one, except as proof that post-outage breakage here tends to be a stale service or path, not lost work.

### Carried, unchanged

- Weird Al disc spec: 14 studio albums, one GROUP per album, 160 kbps chosen by Lola, 611.95 min / 163 tracks, over the 713,299,968 B usable ceiling by about 21 MB. Her save choices (trim the ~10 min "Bite Me" trailing silence, about 12 MB, and/or drop Poodle Hat and Off the Deep End to 128 kbps, about 25.5 MB) are still pending, and the author's capacity gate still refuses rather than overfill. No new decision on 2026-10-24.
- Claude lane: first full cycle complete on 2026-10-23 (commit `3ff381d`, validate.py 30/30, 67-test suite green, published). The Aero-glass UI mock is still unwired to the real core (bitrate ladder, per-track overhead math, Groups UI).
- Two-group disc capability: proven on 2026-10-23 in the publish tree (GROUP.NDB parses back to both names, TOC `[1,1,2]`), independent of the mini lane's failed grind test.
- Quri MiniDisc watch: unchanged framing — NetMD is a different Sony silo from OpenMG SAL, so it will not unlock the ATRAC CD cipher; value is methodology cross-pollination only.
- D-NE1 hardware verdicts: 160 kbps remains unproven, not disproven, until her D-NE1 says otherwise. Nothing on 2026-10-24 changes that.

## Already Covered in Main Chat

- Main agent told Lola the SSH route is the mirror (no second install needed), that all work stays on the mini, and that a standalone MacBook Pro install would be a second agent, not a mirror.
- Main agent told Lola the revived clamp_string session was alive on the mini via SSH, at 9% context, but had not run the tests yet and was waiting on her.
- Main agent told Lola the agent was misattributing its own "No files found" toolcall output to her, and gave her the pinned command to hand back.
- Main agent told Lola to stop feeding the describe-and-ask loop and run the suite herself from a second Terminal via SSH.
- Main agent told Lola the 5-test, 3-pass, 2-fail result means both failures are test bugs and the code is correct, and that the agent never applied its own corrections.
- Main agent gave Lola the exact two corrected lines to paste to the agent, with a do-not-ask-first instruction.
- Main agent told Lola the agent rewrote the test file around a mock, tried WebFetch for a shell command, and must not be fed or allowed to touch the file again.
- Main agent told Lola `wc` confirmed 11 lines (the mock version), the real code in `src/` is untouched, and a rebuilt 5-test file is ready at `~/workspace/your_files/clamp-string-test-rebuild/test_clamp_string.py`.
- Main agent told Lola the restore and the git check can both wait until tomorrow, since she is sick and the file is safe where it is.
- Main agent told Lola the power bring-up order (mini first, NAS share check, gaming PC, then the clips script) and the full-path `opencode` workaround for the PATH failure.

## Open questions and watch items

- Restore the rebuilt test file into the mini's `tests/` folder, then rerun `python3 -m unittest tests.test_clamp_string` from `~/atrac-cd-author` and expect 5/5 — only when Lola leads the return, and ideally after the 2026-10-28 guardrail refresh if it counts as ATRAC work.
- Optional check first, if she feels like it: `git log --oneline -3 -- tests/test_clamp_string.py` on the mini. If it prints nothing, the original was never committed and the rebuild is the way.
- Do not reopen the poisoned clamp_string OpenCode session for edits. If an agent is used for the restore at all, it gets a fresh session and a disk verification afterward, not a summary.
- Post-refresh SAL thread, unchanged: why the shim's return path never runs in the Unicorn harness (readout #20 addendum 6).
- Weird Al save choice, unchanged: silence trim, mixed-rate fallback, or both, decided at build time with the capacity gate as final say.
- Paid decision, unchanged from 2026-10-23: Lola leans toward subscribing, the free trial runs on Wonder and is the honest test, and the 50/90 guardrail gets redrawn with her when she pays.

## Research Trajectory

### External sources viewed
- None this run. No external fact was needed: the findings are Lola's own runs, her disk checks, and main-chat evidence from the window, plus the goal's own files. The only goal file opened fresh was the rebuilt test file below, which is Muse's own artifact, not an external source.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-23/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. It ends at the clamp_string single-shot win with the rerun pending, the guardrail crossed at 51–53%, and the mini lane ruled single-shot-only. Today's rerun verdict, the describe-and-ask loop, the SSH-from-MacBook-Pro proof, and the clobber all postdate it.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-22/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. Its durable findings (SESSION02 reservation, byte-faithful author, SAL phase-7 frontier, merge-point discipline, guardrail values) still govern and were not re-derived.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-21/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — filename-checked in the repetition search; no new topic overlap.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/briefs/D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html` — filename-checked; it is the goal's only prior brief and its topic (the bitrate ceiling) does not cover today's clamp_string rerun, clobber, or SSH-mirror topics.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/files/planned-disc-weird-al.md` — read in full on the prior run and re-checked for the carried capacity verdict above; no change on 2026-10-24.
- `workspace/your_files/clamp-string-test-rebuild/test_clamp_string.py` — read in full this run. It imports the real `clamp_string` from `src`, carries five tests including the two corrected cases (`'a' * 29 + '😀'` → `'a' * 29`; `'\uD83D'` → `'\ufffd'`), and expects 5/5.
- Repetition search (required): variants `clamp_string`, `test_clamp / unittest / rerun`, `ssh / mirror`, and `mock / clobber`, grepped over this goal's `agent_notes/` and over the `briefs/` filename listing. Results: `clamp_string` hits only in the 2026-10-22 note (bug discovery) and the 2026-10-23 note (single-shot win, rerun pending); `ssh / mirror` hits are the general mini-mirror arrangement, not the proven MacBook-Pro-SSH proof; `mock / clobber` hits in the 2026-10-23 note are the unrelated Aero UI mock. No prior note or brief covers the rerun verdict or the test-file clobber, and no prior brief covers any of today's topics.

### Scaffolds and support tactics
- None applied. This is an outcome/project goal (category: interests); the assignment's teach-mode task plan was treated as scheduler metadata, not a skill class, consistent with the prior notes. No mastery estimate made — the goal is not a learned skill, and fewer than three observed performances exist for any such estimate in any case.

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline through phase 7 readout #17, briefing history with the single 2026-10-22 bitrate-ceiling brief, file associations). No other connector data was relevant to this reverse-engineering/build goal today.

### Image references checked
- None opened in this study. Lola's screenshots (OpenCode sessions, the SSH revival, the test output, the `wc` confirmation) were analyzed live in main chat, and their verdicts are preserved above. Avatar state is not relevant to this technical goal.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis): the 50%/90% usage guardrails, the mini-mirror and Claude-lane merge-point rule, "never declare playable from code" (160 kbps remains unproven until her D-NE1 says otherwise), verify-on-disk-before-announcing, terminal labeling, RR3 priority, and the parked-while-sick rule — all applied and reflected above. The MEMORY.md clamp-string entries (rerun verdict, clobber, rebuild path, SSH route) agree with the main-chat evidence and were used only as corroboration, not as the source.

### Searches skipped or unavailable
- No web searches: today's findings are primary evidence from Lola's hardware, her runs, and her disk checks — no external fact needed a lookup.
- No separate `muse.context_fetch` call was needed beyond the run's own conversation evidence, which already carried the full recent main-chat transcript for the window 2026-10-24T05:27:53Z–2026-10-25T05:24:14Z, read in full.
