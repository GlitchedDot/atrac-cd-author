# Study Notes - 2026-10-27 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-10-28T05:24:11Z -->

## Where the goal stands

No change at the frontier on 2026-10-27. The goal's current state in `user_goal.get` for `goal_e35963ec4aae` is unchanged from the 2026-10-26 note: "SAL phase 7 opened with readout #17: static probes closed, init.ocm form mapped, and no periodic keystream found." No goal file under `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/files/` is newer than 2026-10-24 (newest remains `ui-mock-burn-aero.md`, dated 2026-10-24), and no new SAL work, mini-lane run, groups-test result, or Weird Al decision appears in the 2026-10-27 conversation window.

The one goal-adjacent statement in main chat on 2026-10-27 restates the existing guardrail rather than advancing the work: the main agent told Lola the ATRAC work is parked until the free limit resets on 2026-10-28 at 16:03 PDT (America/Los_Angeles), matching the refresh date carried from the 2026-10-26 note. The 50% stop / 90% pause-everything guardrail therefore still governs, and the earliest natural reopening for agent-initiated ATRAC work remains that 2026-10-28 refresh — subject, as below, to Lola leading the return after a health day.

## What the 2026-10-27 evidence actually adds

### Nothing new on the code, the cipher, or the disc

- SAL frontier, unchanged: phase 7 opened with readout #17 (class-01 STR[8192] chunk holds no known crypto constants; no periodic keystream; init.ocm form mapped). The parked thread after the refresh remains why the shim's return path never runs in the Unicorn harness (readout #20 addendum 6, carried from the 2026-10-22 note through the 2026-10-26 note).
- Mini lane, unchanged: clamp_string suite restored and green on 2026-10-25 (5 tests, against the real `clamp_string` in `src/atrac_author/ndb.py`); qwen3:8b loads at CONTEXT 40960 despite a 65536 plist; health check 2026-10-25: 73 tests, 72 pass, 1 debris error. The restored `test_clamp_string.py` still rides into the tree at the next merge; confirm it is committed then rather than assuming the NAS copy made it durable.
- Two-group regression test, still stalled, not resumed: the mini OpenCode groups test (`tests/test_groups.py`, groups `[("Album One",1,2),("Album Two",3,3)]`, verifying GROUP.NDB parses back to both names and TOC track groups `[1,1,2]`) stalled on 2026-10-25 at 21:17 PDT on "SSE read timed out" before writing anything, and no 2026-10-27 turn mentions it. The debris file wrinkle also stands: `tests/test_disc_groups.py` (importing the phantom `build_disc`, which never existed) was still present in the 2026-10-25 evening screenshot despite the combined deletion command having been confirmed earlier that day. Do not record it as deleted. Any future full-suite total from the mini still needs one error discounted until the deletion actually runs.
- Weird Al disc spec, unchanged: 14 studio albums, one GROUP per album, 160 kbps chosen by Lola, 611.95 min / 163 tracks, over the 713,299,968 B usable ceiling by about 21 MB. Her save choices (trim the ~10 min "Bite Me" trailing silence, about 12 MB, and/or drop Poodle Hat and Off the Deep End to 128 kbps, about 25.5 MB) are still pending, and the author's capacity gate still refuses rather than overfill.
- The 160 kbps rate remains unproven, not disproven, until her D-NE1 says otherwise. The D-NE1 charging cradle and external battery pack delivered on 2026-10-26 are already in hand, so future disc tests no longer depend on the player's internal battery state alone; that is a carried convenience, not a new test result, and it was already reported to Lola in main chat on 2026-10-26.
- Claude lane, unchanged: first full cycle complete on 2026-10-23 (commit `3ff381d`, validate.py 30/30, 67-test suite green, published). The Aero-glass UI mock is still unwired to the real core (bitrate ladder, per-track overhead math, Groups UI).
- Quri MiniDisc watch framing, unchanged: NetMD is a different Sony silo from OpenMG SAL, so it will not unlock the ATRAC CD cipher; value is methodology cross-pollination only. No Quri development was reported on 2026-10-27.

### Adjacent context from 2026-10-27 main chat, not ATRAC progress

- On 2026-10-27 at 18:43 UTC (11:43 PDT), Lola asked how much better the GTX 950 is than her 2018 Mac mini for OpenCode, and the main agent answered that for the 8B models she runs, the gaming PC wins mostly on CPU strength (5950X, 16 cores) rather than the 2GB 950, which cannot hold a ~5.2 GB qwen3:8b model, and that pointing OpenCode back at the gaming PC would contend with the decomp job — which is why OpenCode runs only on the mini. This reinforces the standing mini-lane choice; it is not an ATRAC result, it produced no measured token-per-second figure, and it does not change the groups-test plan (nudge "continue" if the session is responsive, or re-paste the groups prompt in a fresh session with the `cd ~/atrac-cd-author` line up front, running the debris deletion first).
- The payday discussion on 2026-10-27 (Muse Power at $20/mo vs a $25 one-time top-up, Claude Pro at $20/mo still only being considered, the 512GB Touch ID MacBook Neo savings target corrected to $799 new / $679 refurb) touches the paid-decision context for this goal only in that Lola still leans toward subscribing, the free trial remains the honest test, and the 50/90 guardrail gets redrawn with her when she pays. No payment decision was made on 2026-10-27.

### Timing context that governs the next move: Lola's 2026-10-27 health day

- Hillside called back on the morning of 2026-10-27 (reported by Lola at 17:52 UTC, 10:52 PDT) and booked her to see a doctor that day at 2:30 PM PDT. The visit was with a different doctor, not her usual doctor Lilly, per Lola at 18:25 UTC (11:25 PDT).
- Visit outcome, reported by Lola at 22:11 UTC (15:11 PDT) on 2026-10-27: UTI confirmed. Treatment: Cefpodoxime Proxetil 200mg, listed as being filled / should be ready soon, per the prescription screenshot she shared at 22:13 UTC (15:13 PDT) and the main agent's read of it.
- This resolves the escalation that began with blood in her urine on 2026-10-25 and cloudy, foul-smelling urine with shivering and a warmer-than-usual forehead on the evening of 2026-10-26, for which she had sent a MyChart message to Hillside that evening. It does not, in the window read, answer the open question the main agent put to her after the visit — whether the November 2 follow-up is still needed or whether the 2026-10-27 visit replaces it. Do not assume November 2 is cancelled; that question is still open.
- Support implication, kept narrow: do not nudge ATRAC work, the groups test, or the Weird Al save choice. The guardrail refresh on 2026-10-28 at 16:03 PDT is the earliest mechanical reopening, but her recovery and her lead matter more than that date; she leads the return. A post-visit check is already scheduled for 2026-10-28 at 10:22 PDT under the Hillside goal, which is the natural place for the November 2 question to be settled, not this goal.
- The assignment's teach-mode task plan (target skill, retrieval prompt, worked example, practice task, feedback rubric, transfer challenge, confidence check, next review 2026-10-29T05:24:11Z) was treated as scheduler metadata for this outcome goal, consistent with the prior notes — not as a skill class. No mastery estimate is made, and no learning-style claim is made.

## Open questions and watch items

- Finish the groups test (stalled since 2026-10-25 at 21:17 PDT), then validate whatever `tests/test_groups.py` it writes before it enters the tree, under the usual merge-point rule: the mini and Claude lanes grind locally; Muse diffs, re-validates against her reference discs, and merges/publishes.
- Confirm the restored `test_clamp_string.py` is committed at the next merge, and run the debris deletion for `tests/test_disc_groups.py` first so the suite total is clean.
- Post-refresh SAL thread: why the shim's return path never runs in the Unicorn harness (readout #20 addendum 6).
- Weird Al save choice, unchanged: silence trim, mixed-rate fallback, or both, decided at build time with the capacity gate as final say.
- Paid decision, unchanged: Lola leans toward subscribing, the free trial is the honest test, and the 50/90 guardrail gets redrawn with her when she pays.
- November 2 Hillside follow-up: still on, replaced by the 2026-10-27 visit, or something else — unanswered in this window; settle via the Hillside post-visit check, not by assumption here.

## Already Covered in Main Chat

- Main agent told Lola the ATRAC work is parked until the free limit resets on 2026-10-28 at 16:03 PDT, and that no decision on Muse Power vs top-up was needed on 2026-10-27, especially with the doctor visit at 2:30 PM PDT.
- Main agent told Lola, in the payday list, that the ATRAC work is parked until the free-limit reset, alongside Muse Power ($20/mo, leaning that way) vs the $25 one-time top-up, Claude Pro ($20/mo, still considering), and the longer saves.
- Main agent told Lola the gaming PC is faster than the mini for 8B OpenCode work mostly on CPU strength, not the GTX 950, and that switching back would put OpenCode on the same CPU as the decomp job.
- Lola told the main agent Hillside called and she would see a doctor at 2:30 PM PDT on 2026-10-27, that it is a different doctor and not Lilly, and later that the UTI was confirmed with Cefpodoxime Proxetil 200mg being filled.
- No main-chat turn on 2026-10-27 discussed the SAL cipher, the clamp_string suite, the groups test, the Weird Al disc spec, or any new ATRAC finding.

## Research Trajectory

### External sources viewed
- None this run. No external fact was needed: today's only goal-adjacent statements are restatements of the existing guardrail and Lola's own health reports, and the goal's code state is unchanged.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-26/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. It carries the cradle delivery, the stalled groups test, the debris file, the SAL phase-7 frontier, and the 2026-10-28 at 16:03 PDT refresh; everything in it still stands, and nothing on 2026-10-27 supersedes it.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-25/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — checked in the repetition search; it carries the clamp_string green run, the 40960 context cap, the health-check totals, and the groups-test stall.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-22/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — checked in the repetition search; its durable findings (SESSION02 reservation, byte-faithful author, SAL phase-7 frontier, merge-point discipline, guardrail values) still govern and were not re-derived.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/briefs/D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html` — filename-checked; it is the goal's only prior brief and its topic (the bitrate ceiling) does not cover today's guardrail restatement, the OpenCode hardware discussion, or the health-day timing context.
- Repetition search (required): variants `ATRAC`, `groups test`, `test_groups`, `clamp_string`, `Weird Al`, `SAL phase`, `bitrate ceiling`, `Cefpodoxime`, and `guardrail`, grepped over this goal's `agent_notes/` and over the `briefs/` filename listing. Results: `groups test` and `test_groups` hit only in the 2026-10-25 and 2026-10-26 notes (the stalled test, not a completion); `clamp_string` hits in the 2026-10-22 through 2026-10-26 notes (no new run on 2026-10-27); `Weird Al` and `bitrate ceiling` hit in the 2026-10-22 through 2026-10-26 notes (spec and ceiling unchanged); `Cefpodoxime` has no hits in this goal's notes (it is new health context from main chat, not an ATRAC finding); `guardrail` hits in the 2026-10-22 through 2026-10-26 notes (the same 50/90 rule restated on 2026-10-27). The no-material-change ruling below rests on the absence of new ATRAC evidence and on the main-chat rule for the guardrail restatement, not on prior-note coverage of a new topic.

### Scaffolds and support tactics
- None applied. This is an outcome/project goal (category: interests); the assignment's teach-mode task plan was treated as scheduler metadata, not a skill class, consistent with the prior notes. No mastery estimate made — the goal is not a learned skill, and no learning-style claim is made.

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline through phase 7 readout #17, briefing history with the single 2026-10-22 bitrate-ceiling brief, file associations). Goal files were listed by timestamp: nothing under `files/` is newer than 2026-10-24. No other connector data was relevant to this reverse-engineering/build goal today.

### Image references checked
- None opened as files in this study. Lola's 2026-10-27 prescription screenshot was read live in main chat (Cefpodoxime Proxetil 200mg, being filled), and its verdict is preserved above as health timing context only. Avatar state is not relevant to this technical goal.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis): the 50%/90% usage guardrails, the mini-mirror and Claude-lane merge-point rule, "never declare playable from code" (160 kbps remains unproven until her D-NE1 says otherwise), verify-on-disk-before-announcing, and the single-shot-only mini-lane rule — all applied and reflected above. The 2026-10-27 conversation window was read in full via `muse.context_fetch` (conversation category); it contains no new ATRAC-app discussion beyond the guardrail restatement.

### Searches skipped or unavailable
- No web searches: today's findings are primary evidence from Lola's own reports, main-chat evidence, and the goal record — no external fact needed a lookup.
- No separate connector reads beyond `user_goal.get` and the run's conversation evidence: the recent main-chat transcript for the window 2026-10-27T05:24:07Z–2026-10-28T05:24:10Z was read in full via `muse.context_fetch` (conversation category).
