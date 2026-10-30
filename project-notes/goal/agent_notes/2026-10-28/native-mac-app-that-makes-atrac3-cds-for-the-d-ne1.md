# Study Notes - 2026-10-28 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-10-29T05:31:17Z -->

## Where the goal stands

The frontier moved substantially on the evening of 2026-10-28 (America/Los_Angeles), and it moved in main chat, at Lola's direction — which is why this note preserves the findings but does not earn a new Letter (see the ruling note in Research Trajectory). Everything except the cipher was already finished: the disc layout is mapped and byte-faithful, the ATRAC3+ encoder workstream is closed, and the author is published to a private GitHub repo. The cipher, localized to the SAL bytecode engine, was parked at "why the shim's return path never runs in the Unicorn harness" (readout #20 addendum 6, from the 2026-10-22 note). On 2026-10-28 Lola restarted that thread herself, after the free weekly usage limit reset, and chose the Unicorn harness lane.

One record-lag warning for the next study: `user_goal.get` for `goal_e35963ec4aae` still shows the 2026-10-22 current state, "SAL phase 7 opened with readout #17: static probes closed, init.ocm form mapped, and no periodic keystream found." That state predates the 2026-10-28 harness sessions below and must not be read as the current frontier.

## What changed on 2026-10-28: the harness resumed and D680 returned

All times in this section are 2026-10-28, America/Los_Angeles (PDT), converted from the main-chat timestamps.

### The restart, and the guardrail that allowed it

- Lola said "start up that SonicStage once more," the main agent first answered with the paused Toshiba SonicStage 4.3 thread, and Lola corrected it: "Not that one" — she meant the ATRAC CD app project, "now the usage limit has reset." That correction is binding context: "SonicStage" on its own is ambiguous, and the Toshiba thread (paused since 2026-10-03, startup crash Omgjbox.exe 0xc0000005) is never the default.
- The main agent checked the meter at that point: 1% of the free weekly limit used, resetting 2026-11-04 at 5:48 PM PST — well under Lola's 50% ATRAC stop line (pause everything at 90%). The project therefore resumed at her word, not on a schedule.
- Lola chose the lane: "Unicorn harness: trace the shim's return path." She then said "Continue" at each step, through the encrypt attempt and the follow-up session.

### Runs 73–80: the init.ocm and device.sal fetches, observed for the first time

- The parked state was not run 66, as the main agent's brief had said: files showed runs 67–72 already existed, so the session continued from run 72's `_stat` stop. The `manager ctx = 0x1` seen in earlier logs was leftover register state, not a return value — D680 had never reached its return stub.
- Gaps were filled one at a time: `_stat`, then a CRT file layer (fopen/fread/fwrite and friends), then the time functions. Each unblocked run died on the next missing piece, the old plateau pattern.
- The engine then threw its own error, verbatim: `OMGException: init.ocm: not found`. It wants init.ocm at `C:\Windows\system32\init.ocm` and never looked in the OpenMG folder first. The session staged Lola's corpus init.ocm there (copy only, corpus untouched). Run 76 returned a heap buffer byte-identical to init.ocm, and run 77 traced the full fetch: CreateFileW, GetFileSize, ReadFile. That is the fetch, observed, not inferred.
- A single-step chain bug was fixed along the way (empty chain fallback, fired exactly once). The engine then threw for `device.sal`; staged the same way, run 79 observed the device.sal fetch too, byte-identical. The engine then created its own `procfile/device.sal` cache copy itself, so that path fills itself and is not a second file to stage.
- The session ended on a new crash, not the old one: an access violation at 0x651483b5, where a resumed continuation reads a pointer from `[ebp-8]` and finds garbage there. One caution established then: the engine patches its own .text at runtime, so static disassembly lies for these regions — the live bytes at resume time were valid code.

### Runs 82–86: D680 returns

- The "[ebp-8] garbage" framing turned out to be downstream noise. The real fault chain was a wild return from OMGUtils code to a stack address, causing an illegal instruction. The root cause was a one-line harness bug: `_set_se_translator` was registered as stdcall when it is actually cdecl (the mangled name itself says `@@YA`). The wrapper already cleans its own argument, so the stdcall stub cleaned it a second time, ESP ended up 4 bytes too high, and the return address got eaten.
- One-line fix in run 85: zero illegal-instruction faults in runs 85 and 86, HLE calls up to 3,690 and then 4,299.
- The engine then threw for a missing `region.ocm` — the same pattern as init.ocm and device.sal. Staged from the corpus (MD5s match, corpus untouched), and run 86 came back clean: SEH rounds 173, HLE 4,299, no "not found" errors, the engine uninstalled the SE translator itself in an orderly teardown, and then, verbatim from run86.txt: `D680: SEH rounds = 173; final stop = None` and `manager ctx = 0x100002e0`.
- Caveat, stated plainly and carried forward: "the manager context" is still an inference — from it being D680's return value, plus its structured, manager-plausible contents, plus the orderly teardown. The ultimate proof, actually performing cipher work through it, had not happened yet at that point. Heap addresses shift per run, so 0x100002e0 must be re-derived in each run, never hardcoded, even though it coincidentally recurred in the runs below.

### Run 88 (verified only): the first encrypt probe did not reach the SAL call

- Bootstrap still clean, no regression: fresh manager ctx re-derived from run 88's own return as 0x100002e0, SEH rounds 173, clean final stop.
- The first encrypt probe stopped inside supporting library code on an unhandled breakpoint exception, before the VM execution call. Output buffer stayed empty, no ciphertext was produced, and the manager's post-probe records were empty. The manager-context inference therefore stayed inferred, not proven, with nothing to compare against the known Ignite pairs yet.
- The session note was not updated with this run. The staged folder had grown since run 86: atpcd.ocm, ekbman.ocm, mp4comp.ocm, and mp4comp.dll now staged alongside init.ocm, device.sal, and region.ocm.
- Later work from that session (run 89 and beyond) could not be verified afterward and was explicitly left out of the main-chat report. Do not build on it, cite it, or treat it as evidence. The next session was briefed from run 88 only.

### Runs 94–98: the probe chain clears, then the search reframes

In order, each verified in the logs and hashes by the main agent:

- Run 94 diagnosed the EqualSid fault: the harness's `GetTokenInformation` stub ignored the class and always wrote TOKEN_USER-shaped data, even for TokenGroups — so the caller read a SID pointer as a group count and walked garbage heap as group entries. EqualSid itself was never the problem.
- Run 95 fixed that with a real TOKEN_GROUPS reply — past the fault, straight into an unimplemented `strtok`.
- Run 96 added strtok — past tokenizing, into a fatal `icv.ocm: not found`.
- Run 97 staged icv.ocm (MD5-verified against the corpus) — next fatal: `maclist.ocm: not found`.
- Run 98 staged maclist.ocm — past that into an EKB directory probe (absent, tolerated), two registry writes, and then a fatal throw: `poi poi poi`.
- That throw is not a harness gap. The session decoded its throw site from salwrap's own bytes: after one function returns 0, the engine deliberately throws with that static string. No missing file, no unimplemented import, no garbage pointer is left on this path. Do not file it as a bug to fix with another HLE stub.

### The reframe: b650 is salexec, not an encrypt entry

- From the Ghidra decompilations, b650 is the SAL script parser/compiler — this=ctx, spec struct, out, name struct. The probe's `'Encrypt'` spec was being fed to the parser as script text, and the engine's dispatch rejected it with "poi poi poi."
- The next step is therefore not another HLE fix. It is designing a valid salexec spec from device.sal's solved grammar, or finding the real encrypt entry point.
- Still true, stated plainly: no ciphertext in any run (the out buffer stayed 64 zero bytes), the manager ctx (re-derived fresh as 0x100002e0 in every run, bootstrap clean throughout) remains inferred, not proven, and there is nothing to compare against the Ignite pairs yet.
- The main agent's last message in the window asked Lola: "Want me to continue into the valid-spec work?" No answer appears in the window read. That question is pending at Lola's lead; do not assume she said yes, and do not start the valid-spec work unprompted.

## What did not change

- Encoder: done (all 9 bitrate rungs pass with atracdenc, no code changes needed). Author: built and validated (30/30 against her reference discs, two-group discs proven, Claude merge landed). The Aero-glass UI mock is still unwired to the real core.
- Mini lane: still half-done. Clamp_string suite restored and green on 2026-10-25 (5 tests); the groups test stalled on 2026-10-25 at 21:17 PDT on "SSE read timed out" with no test file written; the debris file `tests/test_disc_groups.py` (importing the phantom `build_disc`) was still present that evening. No 2026-10-28 turn mentions either, so neither is resolved.
- Weird Al disc spec: unchanged and still awaiting her save choice. Fourteen studio albums, one GROUP per album, 160 kbps chosen by Lola, 611.95 min / 163 tracks, about 21 MB over the 713,299,968 B usable ceiling. Saves pending: trim the ~10 min "Bite Me" trailing silence (~12 MB) and/or drop Poodle Hat (54.65 min) and Off the Deep End (51.56 min) to 128 kbps (~25.5 MB). The author's capacity gate refuses rather than overfills. The 160 kbps rate remains unproven, not disproven, until her D-NE1 says otherwise — never declare it playable from code or logs.
- Quri MiniDisc watch framing: unchanged. NetMD is a different Sony silo from OpenMG SAL, so it will not unlock the ATRAC CD cipher; its value is methodology cross-pollination only.
- The assignment's teach-mode task plan (target skill, retrieval prompt, worked example, practice task, feedback rubric, transfer challenge, confidence check, next review 2026-10-30T05:31:17Z) was treated as scheduler metadata for this outcome goal, consistent with the prior notes — not as a skill class. No mastery estimate is made, and no learning-style claim is made.

## Open questions and watch items

- Pending Lola's answer: continue into the valid-spec work — design a valid salexec spec from device.sal's solved grammar, or find the real encrypt entry point. This is the live frontier; everything else below is carried.
- When the valid-spec work runs: re-derive the manager ctx fresh in its own run (never reuse 0x100002e0 as a constant); prove the ctx by performing real cipher work through it and measuring output against the known Ignite pairs; treat any new "not found" file the same way as before (stage from the corpus, MD5-verified, corpus untouched).
- Do not build on the unverified run-89 work from the first encrypt session; the verified ground is run 88 plus runs 94–98.
- Finish the groups test (stalled since 2026-10-25 at 21:17 PDT), then validate whatever `tests/test_groups.py` it writes before it enters the tree, under the merge-point rule: the mini and Claude lanes grind locally; Muse diffs, re-validates against her reference discs, and merges/publishes. Confirm the restored `test_clamp_string.py` is committed at the next merge, and run the debris deletion for `tests/test_disc_groups.py` first.
- Weird Al save choice, unchanged: silence trim, mixed-rate fallback, or both, decided at build time with the capacity gate as final say.
- Paid decision, unchanged: Lola leans toward subscribing, the free trial is the honest test, and the 50/90 guardrail gets redrawn with her when she pays. The 2026-10-28 meter (1% used, resets 2026-11-04 at 5:48 PM PST) is the current guardrail baseline.

## Already Covered in Main Chat

- Lola told the main agent "start up that SonicStage once more," then corrected it with "Not that one" — she meant the ATRAC CD app project, now the usage limit has reset.
- Main agent told Lola the fresh meter showed 1% of the free weekly limit used, resetting Nov 4 at 5:48 PM PST, well under her 50% ATRAC stop line, so the project was clear to start up.
- Lola told the main agent to start with "Unicorn harness: trace the shim's return path," and said "Continue" at each subsequent step, including into the encrypt attempt.
- Main agent told Lola the init.ocm fetch was observed for the first time in runs 73–80, with run 76 byte-identical to init.ocm and run 77 tracing CreateFileW, GetFileSize, and ReadFile, and that device.sal was observed the same way in run 79.
- Main agent told Lola D680 had returned in runs 82–86, that the root cause was the _set_se_translator stdcall-versus-cdecl bug double-cleaning the stack, and that run 86 ended with SEH rounds 173 and manager ctx 0x100002e0, with the manager-context reading still an inference.
- Main agent told Lola run 88 verified a clean bootstrap with a fresh ctx of 0x100002e0, but the first encrypt probe stopped on an unhandled breakpoint before the SAL call, with no ciphertext and nothing to compare against the Ignite pairs.
- Main agent told Lola runs 94–98 cleared GetTokenInformation TokenGroups, strtok, icv.ocm, and maclist.ocm in turn, then ended in the deliberate engine throw "poi poi poi," which reframes b650 as salexec (the SAL script parser/compiler), not an encrypt entry.
- Main agent asked Lola whether to continue into the valid-spec work, and no answer to that question appears in the window read.

## Research Trajectory

### External sources viewed
- None this run. No external fact was needed: today's findings are primary evidence from Lola's own project sessions, reported and verified in main chat, and the goal's code state is otherwise unchanged.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-27/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. It carries the parked harness state, the stalled groups test, the debris file, the Weird Al spec, and the 50/90 guardrail; everything in it still stands except the parked harness state, which the 2026-10-28 sessions supersede.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-22/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — checked in the repetition search; its durable findings (SESSION02 reservation, byte-faithful author, SAL phase-7 frontier, merge-point discipline) still govern and were not re-derived.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/briefs/D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html` — filename-checked; it is the goal's only prior brief and its topic (the bitrate ceiling) does not cover the harness return, the salexec reframe, or the encrypt attempt.
- Repetition search (required): variants `salexec`, `D680`, `Unicorn harness`, `encrypt`, `salwrap`, and `manager ctx`, grepped over this goal's `agent_notes/` and over the `briefs/` filename listing. Results: `salexec`, `D680`, and `manager ctx` have zero hits in any prior note or brief — the reframe and the return are new to the preserved record; `Unicorn harness` hits only in the 2026-10-22 through 2026-10-27 notes as the parked "why the shim's return path never runs" thread, which the 2026-10-28 sessions close; `encrypt` hits are the long-standing burn-time-encryption unknown, not a prior encrypt attempt; `salwrap` hits are the static readouts #10–#17, not the dynamic harness results. The no-material-change ruling below therefore rests on the main-chat rule, not on prior-note coverage: the findings are new to the record but were already delivered to Lola in full in main chat on 2026-10-28.

### Scaffolds and support tactics
- None applied. This is an outcome/project goal (category: interests); the assignment's teach-mode task plan was treated as scheduler metadata, not a skill class, consistent with the prior notes. No mastery estimate made — the goal is not a learned skill, and no learning-style claim is made.

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline through phase 7 readout #17, briefing history with the single 2026-10-22 bitrate-ceiling brief, file associations). Goal files were listed: nothing under `files/` is newer than 2026-10-24. No other connector data was relevant to this reverse-engineering/build goal today. The goal record's current state lags the 2026-10-28 harness progress, as flagged above.

### Image references checked
- None opened as files in this study. No new image evidence bears on this goal in the window; the session evidence arrived as main-chat reports verified against logs and hashes by the main agent, not as screenshots for this study to re-read.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis): the 50%/90% usage guardrails, the mini-mirror and Claude-lane merge-point rule, "never declare playable from code" (160 kbps remains unproven until her D-NE1 says otherwise), verify-on-disk-before-announcing, the single-shot-only mini-lane rule, and the SonicStage fork rule (never default to the paused Toshiba thread) — all applied and reflected above. The 2026-10-28 conversation window was read in full via `muse.context_fetch` (conversation category); its ATRAC turns are the evidence for this note.

### Searches skipped or unavailable
- No web searches: today's findings are primary evidence from Lola's own sessions and main-chat evidence — no external fact needed a lookup.
- No separate connector reads beyond `user_goal.get` and the run's conversation evidence: the recent main-chat transcript for the window 2026-10-28T05:24:10Z–2026-10-29T05:31:21Z was read in full via `muse.context_fetch` (conversation category).
