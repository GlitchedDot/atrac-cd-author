# Study Notes - 2026-10-25 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-10-26T05:28:30Z -->

## Where the goal stands

Unchanged at the frontier: everything except the cipher is finished, and the cipher is still localized to the SAL bytecode engine, with the Unicorn harness parked at why the shim's return path never runs (readout #20 addendum 6, from the 2026-10-22 note). No new SAL work happened on 2026-10-25, and none is due: the ATRAC project guardrail from 2026-10-23 — agent-initiated ATRAC work stops at 50% of the free weekly limit, pause-everything at 90% — still refreshes on 2026-10-28 at 16:03 PDT.

What moved on 2026-10-25 was entirely the support lane around the project, and it moved at Lola's own lead, not by nudge: she said "lets go" on the clamp_string restore, then asked to "feed the mini with another command" and then for "a little bigger lane" after that. In one day the mini OpenCode lane went from a clobbered test file to a green clamp_string suite, a maxed-out model context, a clean health check with one known debris error, and a started-but-stalled two-group regression test. The groups test is the only unfinished piece, and it is unfinished for a mechanical reason (a stream stall), not a design question.

## Today's session (2026-10-25 PDT) — what changed

### Clamp_string restored and green: 5/5, the mini lane's first clean single-shot run

The 2026-10-24 note ended with the rebuilt 5-test file ready but unapplied, after the mini agent had clobbered the original with an 11-line mock (`return s[:29]`, slicing by code point). On 2026-10-25 morning PDT Lola ran the restore herself:

- She verified the mock first (11 lines), confirmed via empty `git log` that the original was never committed (so the rebuild was the only recovery), copied the rebuilt file in via the NAS share, and ran `python3 -m unittest tests.test_clamp_string` from `~/atrac-cd-author`.
- Result: 5 tests, all passing, OK — against the real `clamp_string` in `src/atrac_author/ndb.py`, not the mock.

This closes the 2026-10-24 open item and confirms, with a real run, that the code behavior matches Claude's merged fix. The test file now rides into the tree at the next merge; it is not yet committed on its own. Standing rule unchanged: any future claim about this file needs a disk check first (`wc -l` and the head of the file), not an agent summary.

### Ollama context on the mini: settled at 40960, not 65536 — and that is the max for this model

The morning also closed the post-outage context question, in stages, all from Lola's own terminal output on the mini:

- `launchctl getenv OLLAMA_CONTEXT_LENGTH` printed nothing, and `ollama ps` first showed no models loaded at all — so there was no context value to read yet, and nothing running at the wrong context either.
- After a model load, `ollama ps` showed CONTEXT 4096: the LaunchAgent had run fine at login, but the variable never reached the already-running server (most likely Ollama started before the setenv ran).
- Fix, applied by Lola: `launchctl setenv OLLAMA_CONTEXT_LENGTH 32768` plus `pkill -x Ollama`, from SSH — which worked, settling the earlier session question. Reload showed CONTEXT 32768 and the model size up from 5.9 GB to 10 GB, as expected for an 8x window.
- Lola then asked for a bigger context and chose 64K. The updated plist (only line changed: 32768 to 65536, verified by diff) was installed with unload/load, setenv 65536, and restart. The result was CONTEXT 40960, model size 11 GB — not 65536.
- Verdict given in main chat and accepted by Lola ("ok, that's perfectly fine, wanted to max out that qwen"): qwen3:8b caps at 40960 through the server default. The 64K plist stays in place — it asks for 65536 and the model takes its 40960 max — and a future model that supports more would get more from the same setup. True 64K on this model would need a per-request `num_ctx` override, and for the single-shot work the mini does, it is not worth chasing.

One correction to carry forward: earlier main-chat wording said "full 32K context" after the 32768 step; the durable number is now 40960, and the plist number (65536) is the request, not the served context. If a later login lands back at 4096, repeat setenv plus restart; that would confirm a startup-order problem, and then Ollama itself should carry the variable instead of relying on the login-time setenv.

Lola's own observation on the maxed context, preserved as her report: thinking seems a little longer, but responding seems a bit faster. The explanation given in main chat, and consistent with the numbers: with a 40K window each generated token attends over a much bigger pile of context, so on CPU each thinking token is slower, while the session stops tripping over the 4K ceiling that used to cause stalls and repair work mid-conversation. Trade-off, not contradiction: more room, slower words, fewer stalls.

### Health check: mini matches the published tree, 73 tests, 72 pass, 1 known debris error

After the clamp_string green run, Lola gave the mini a read-only health check (do not modify any files, `__pycache__` excepted): `git log --oneline -3`, `git status --short`, and `python3 -m unittest discover -s tests` from the repo root.

- First attempt failed on the wrong directory: a git fatal proved the session was not in the repo, and the unittest traceback followed from the same cause. Fix was the `cd ~/atrac-cd-author` line up front — a lesson already recorded in standing context (mini-lane prompts must name the directory up front), and the groups-test prompt below carries it.
- Corrected result, from Lola's screenshot on 2026-10-25 at 12:47 PDT: HEAD `3ff381d` (the Claude merge), so the mini matches the published tree; 73 tests ran, 72 passed, 1 error.
- The 1 error is `tests/test_disc_groups.py` importing `build_disc` — and `build_disc` never existed (verified by grep on 2026-10-23). That file is debris from the failed grind test, which invented `build_disc` and cycled it through three guessed modules. It tests a phantom API, not a real regression. The committed 67 tests all pass, and the restored clamp_string 5 all pass: 67 + 5 = 72.
- Cleanup command given and confirmed by Lola at 12:49 PDT: `cd ~/atrac-cd-author && rm tests/test_disc_groups.py && python3 -m unittest discover -s tests`, expected to land at 72 tests, all passing, OK. The other two untracked files were left alone: `src/__init__.py` is harmless, and `test_clamp_string.py` rides into the tree at the next merge.

Important nuance for the next study: the 21:17 PDT screenshot (below) still shows the debris file present, so the deletion did not land before the groups task ran, despite Lola confirming the combined command. Do not record the debris file as deleted. The groups task's full-suite total will still include that known error until the deletion actually runs — discount one error when it reports.

### Groups test: started, prepared correctly, stalled before writing anything — the one open item

Lola asked for a bigger lane after the health check, and the job lined up was a regression test for two-group disc support: a capability proven on 2026-10-23 in the publish tree (GROUP.NDB parses back to both names, TOC `[1,1,2]`) but never locked in as a test, and a step up because it makes Qwen read three modules instead of one. The prompt, given with the `cd` line up front:

- One job only: create `tests/test_groups.py`; do not modify any existing files, do not touch `src/`.
- Read how `build_iso` takes its groups parameter (`author.py`) and how GROUP.NDB and the TOC record group assignment (`ndb.py`, `sti.py`).
- Build with groups `[("Album One",1,2),("Album Two",3,3)]` using a dummy 172-byte STK (`b'EKB '` + 168 zero bytes), then verify the output parses back to both group names in GROUP.NDB and TOC track groups `[1,1,2]`, using `build_tree` or `build_iso` plus whatever extraction the repo already supports.
- Run the new tests, then the full suite, and report new-test results, full-suite totals, and any failures; if a new test fails, report whether the test or the code is at fault, changing only the test file, never `src/`.
- Same merge-point rule as before: whatever it writes comes back through Muse for validation before it enters the tree.

What actually happened, from Lola's screenshot on 2026-10-25 at 21:17 PDT (Build, Qwen3 8B, Ollama on the mini, context 28%):

- The agent first guessed `src/author.py`, which does not exist, then corrected itself via `find` to the real files `src/atrac_author/author.py`, `ndb.py`, and `sti.py`.
- Greps for literal phrases returned nothing — expected, not a failure, because the code does not contain the literal phrases "groups parameter" or "TOC record".
- It then read all three source files, which is the right preparation.
- Then it stalled: "SSE read timed out." That is the known stall signature, not the agent thinking — the stream died. No `test_groups.py` was written, no results reported.

Next move, already given in main chat: if the session is still responsive, a short "continue" nudge should pick it back up from the file reads; if it is dead, re-paste the same groups prompt in a fresh session. Carry the debris-file wrinkle with it: since the debris file is still present, the full-suite total it reports will include that known error.

### Carried, unchanged

- SAL frontier: phase 7 opened with readout #17 (class-01 STR[8192] chunk holds no known crypto constants; no periodic keystream; init.ocm form mapped). The shim-return-path question (readout #20 addendum 6) is still the parked thread for after the 2026-10-28 refresh.
- Weird Al disc spec: 14 studio albums, one GROUP per album, 160 kbps chosen by Lola, 611.95 min / 163 tracks, over the 713,299,968 B usable ceiling by about 21 MB. Her save choices (trim the ~10 min "Bite Me" trailing silence, about 12 MB, and/or drop Poodle Hat and Off the Deep End to 128 kbps, about 25.5 MB) are still pending, and the author's capacity gate still refuses rather than overfill. No new decision on 2026-10-25.
- Claude lane: first full cycle complete on 2026-10-23 (commit `3ff381d`, validate.py 30/30, 67-test suite green, published). The Aero-glass UI mock is still unwired to the real core (bitrate ladder, per-track overhead math, Groups UI).
- Two-group disc capability: proven on 2026-10-23, still untested as a regression test — that is exactly what the stalled groups task is for. Do not confuse the proven capability with the debris `test_disc_groups.py` file: the capability is real, the debris file's `build_disc` API is not.
- Quri MiniDisc watch: unchanged framing — NetMD is a different Sony silo from OpenMG SAL, so it will not unlock the ATRAC CD cipher; value is methodology cross-pollination only. No Quri development was reported on 2026-10-25.
- D-NE1 hardware verdicts: 160 kbps remains unproven, not disproven, until her D-NE1 says otherwise. Nothing on 2026-10-25 changes that.
- Mini lane discipline, strengthened twice today: prompts must name `~/atrac-cd-author` up front (wrong-directory stumble), and a session that stalls on "SSE read timed out" is a dead stream to nudge or restart, not a thinking agent to wait on indefinitely.

## Open questions and watch items

- Finish the groups test: nudge "continue" or re-paste the groups prompt in a fresh session, then validate whatever `tests/test_groups.py` it writes before it enters the tree — and run the debris deletion first, so the full-suite total is clean (72 plus the new tests, not 73 plus the new tests with one phantom error).
- Restore/merge hygiene: the restored `test_clamp_string.py` still rides into the tree at the next merge; confirm it is committed then, rather than assuming the NAS copy made it durable.
- Post-refresh SAL thread, unchanged: why the shim's return path never runs in the Unicorn harness (readout #20 addendum 6).
- Weird Al save choice, unchanged: silence trim, mixed-rate fallback, or both, decided at build time with the capacity gate as final say.
- Paid decision, unchanged from 2026-10-23: Lola leans toward subscribing, the free trial runs on Wonder and is the honest test, and the 50/90 guardrail gets redrawn with her when she pays.
- Next review for this study loop: 2026-10-27T05:28:30Z (from the assignment's study plan; the plan itself is scheduler metadata for this outcome goal, not a skill-class lesson — see Research Trajectory).

## Already Covered in Main Chat

- Main agent told Lola the clamp_string restore ran 5 tests, all passing, OK, and that this was the mini lane's first clean single-shot run.
- Main agent told Lola the empty `getenv` meant the LaunchAgent variable was not set in that session, and gave her the plist/load checks to distinguish a load problem from a missing file.
- Main agent told Lola the empty `ollama ps` meant no models were loaded yet, so no context value could be read and nothing was running at the wrong context.
- Main agent told Lola CONTEXT 4096 was definitive proof the server never got 32768, and gave her the setenv-plus-restart fix to run on the mini.
- Main agent told Lola CONTEXT 32768 after the restart was the win, with the model size up from 5.9 GB to 10 GB as corroboration.
- Main agent told Lola the 64K plist was verified with only the 32768 to 65536 line changed, and gave her the install, unload/load, setenv, and restart sequence.
- Main agent told Lola CONTEXT 40960, not 65536, means qwen3:8b caps there through the server default, the 64K plist stays, and true 64K would need a per-request override not worth chasing.
- Main agent told Lola the health check's 73 tests, 72 pass, 1 error breakdown, that `build_disc` never existed, and that the debris file is the failed grind test's phantom, not a real regression.
- Main agent told Lola the cleanup is one combined command deleting the debris file and re-running the suite, expecting 72 tests all passing.
- Main agent gave Lola the groups-test prompt with the `cd ~/atrac-cd-author` line up front, after the wrong-directory stumble showed why that line matters.
- Main agent told Lola the longer-thinking/faster-responding observation is both real: bigger window slows each token on CPU but stops the 4K-ceiling stalls.
- Main agent told Lola the groups task stalled on "SSE read timed out," no test file was written yet, and the next move is "continue" if responsive or a fresh re-paste, discounting one debris error in its full-suite total.
- Main agent told Lola the wrong-directory git fatal proved the health-check session was not in the repo, and that no restart was needed, only `cd` first.

## Research Trajectory

### External sources viewed
- None this run. No external fact was needed: the findings are Lola's own runs, her terminal output, her screenshots, and main-chat evidence from the window, plus the goal's own files. The only prior brief is the 2026-10-22 bitrate-ceiling brief, filename-checked below.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-24/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. It ends at the clobbered test file, the rebuilt file ready but unapplied, the SSH-from-MacBook-Pro proof, and the guardrail holding until 2026-10-28 at 16:03 PDT. Today's clamp_string green run, Ollama context saga, health check, and groups stall all postdate it.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-23/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — checked in the repetition search for clamp_string, groups, and context topics; it carries the single-shot win, the rerun pending, the two-group proof, and the 32K LaunchAgent, but not today's green run, 40960 cap, health-check totals, or groups stall.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-22/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — checked in the repetition search; its durable findings (SESSION02 reservation, byte-faithful author, SAL phase-7 frontier, merge-point discipline, guardrail values) still govern and were not re-derived.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/briefs/D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html` — filename-checked; it is the goal's only prior brief and its topic (the bitrate ceiling) does not cover today's clamp_string green run, Ollama context cap, health check, or groups stall.
- Repetition search (required): variants `clamp_string`, `test_groups / two-group / groups test`, `OLLAMA_CONTEXT / context 40960 / 65536`, and `health check / test_disc_groups`, grepped over this goal's `agent_notes/` and over the `briefs/` filename listing. Results: `clamp_string` hits only in the 2026-10-22, 2026-10-23, and 2026-10-24 notes (bug discovery, single-shot win, clobber/rebuild-ready — none of them the green run); groups hits in the 2026-10-23 and 2026-10-24 notes are the proven capability and the unrelated Aero UI mock, not the stalled regression test; context hits are the 2026-10-23 32K LaunchAgent only, not the 40960 cap; no prior note or brief covers the health-check totals or the groups stall. Against the notes alone, today's topics would be new — the no-material-change ruling below rests on the main-chat rule, not on prior-note coverage.

### Scaffolds and support tactics
- None applied. This is an outcome/project goal (category: interests); the assignment's teach-mode task plan (target skill, retrieval prompt, worked example, practice task, feedback rubric, transfer challenge, confidence check, next review at 2026-10-27T05:28:30Z) was treated as scheduler metadata, not a skill class, consistent with the prior notes. No mastery estimate made — the goal is not a learned skill, and no learning-style claim is made.

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline through phase 7 readout #17, briefing history with the single 2026-10-22 bitrate-ceiling brief, file associations). No other connector data was relevant to this reverse-engineering/build goal today.

### Image references checked
- None opened as files in this study. Lola's screenshots (clamp_string green run, Ollama context outputs, health-check output, groups-task stall screen) were analyzed live in main chat, and their verdicts are preserved above. Avatar state is not relevant to this technical goal.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis): the 50%/90% usage guardrails, the mini-mirror and Claude-lane merge-point rule, "never declare playable from code" (160 kbps remains unproven until her D-NE1 says otherwise), verify-on-disk-before-announcing, terminal labeling, and the single-shot-only mini-lane rule — all applied and reflected above. MEMORY.md's 2026-10-25 mini-lane entries (clamp_string green, 40960 context, health-check debris, groups stall) agree with the main-chat evidence and were used only as corroboration, not as the source.

### Searches skipped or unavailable
- No web searches: today's findings are primary evidence from Lola's hardware, her runs, and her disk checks — no external fact needed a lookup.
- No separate `muse.context_fetch` call was needed beyond the run's own conversation evidence, which already carried the full recent main-chat transcript for the window 2026-10-25T05:24:14Z–2026-10-26T05:28:35Z, read in full.
