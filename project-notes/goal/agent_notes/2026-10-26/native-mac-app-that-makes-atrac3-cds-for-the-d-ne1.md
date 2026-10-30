# Study Notes - 2026-10-26 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-10-27T05:24:08Z -->

## Where the goal stands

No change at the frontier on 2026-10-26. Everything except the cipher is finished, and the cipher is still localized to the SAL bytecode engine, with the Unicorn harness parked at why the shim's return path never runs (readout #20 addendum 6, carried from the 2026-10-22 note through the 2026-10-25 note). No new SAL work happened on 2026-10-26, and none is due: the ATRAC guardrail still holds — agent-initiated ATRAC work stops at 50% of the free weekly limit, pause-everything at 90% — with the weekly refresh on 2026-10-28 at 16:03 PDT (America/Los_Angeles). The goal's own files are unchanged since 2026-10-23/2026-10-24 (the newest goal file, `ui-mock-burn-aero.md`, is dated 2026-10-24), and `user_goal.get` for `goal_e35963ec4aae` still shows the same current state: "SAL phase 7 opened with readout #17: static probes closed, init.ocm form mapped, and no periodic keystream found."

What did happen on 2026-10-26 touches this goal only at its hardware edge, not its code: the D-NE1 charging cradle and external battery pack were delivered and confirmed in Lola's hands (see below). That closes the accessory shipment watch, which lives under the D-NE1 box-hunt goal, not this one. It does not change any disc, author, cipher, or test verdict: the player already read discs without the cradle, the 160 kbps rate remains unproven (not disproven) until her D-NE1 says otherwise, and the cradle adds charging convenience, not a new test result.

## What the 2026-10-26 evidence actually adds

### D-NE1 hardware set now complete except the box — delivery, not a project result

- Delivered, In/At Mailbox, Ukiah, at 9:50 am PDT on 2026-10-26, confirmed by two live reads in main chat and then by Lola's own photo at about 10:15 am PDT on 2026-10-26 showing the clear cradle and the battery pack in her hand.
- Main chat closed the shipment watch on that confirmation. The monthly box hunt continues: the original D-NE1 box is still the missing piece, and the boxed UK listing she passed on sold on 2026-10-26 for £58.00 with 3 bids (UK postage only) — that listing watch is done, the hunt is not.
- Support implication, kept narrow: future D-NE1 disc tests no longer depend on the player's internal battery state alone, since the cradle and external pack are now in hand. Do not treat this as progress on the author, the cipher, or the Weird Al disc, and do not re-report the delivery as news — Lola lived it, photographed it, and was told it in main chat the same morning.

### The one open item stays open: the two-group regression test

- The 2026-10-25 note's only unfinished piece — the mini OpenCode groups test (`tests/test_groups.py`, groups `[("Album One",1,2),("Album Two",3,3)]`, verifying GROUP.NDB parses back to both names and TOC track groups `[1,1,2]`) — was not resumed, completed, or mentioned in the 2026-10-26 conversation. It stalled on 2026-10-25 at 21:17 PDT on "SSE read timed out" before writing anything, and that state stands.
- The debris file wrinkle also stands: `tests/test_disc_groups.py` (importing the phantom `build_disc`, which never existed) was still present in the 2026-10-25 evening screenshot, despite the combined deletion command having been confirmed earlier that day. Do not record it as deleted. Any future full-suite total from the mini still needs one error discounted until the deletion actually runs.
- When the groups test is next picked up, the standing next move from the 2026-10-25 note still applies: nudge "continue" if the session is responsive, or re-paste the groups prompt in a fresh session, with the `cd ~/atrac-cd-author` line up front, and run the debris deletion first so the suite total is clean.

### Carried, unchanged

- SAL frontier: phase 7 opened with readout #17 (class-01 STR[8192] chunk holds no known crypto constants; no periodic keystream; init.ocm form mapped). Parked thread after the 2026-10-28 refresh: why the shim's return path never runs in the Unicorn harness (readout #20 addendum 6).
- Mini lane: clamp_string suite restored and green 2026-10-25 (5 tests, against the real `clamp_string` in `src/atrac_author/ndb.py`); qwen3:8b loads at CONTEXT 40960 despite a 65536 plist (true 64K would need a per-request `num_ctx` override, not worth chasing); health check 2026-10-25: 73 tests, 72 pass, 1 debris error. The restored `test_clamp_string.py` still rides into the tree at the next merge; confirm it is committed then rather than assuming the NAS copy made it durable.
- Weird Al disc spec: 14 studio albums, one GROUP per album, 160 kbps chosen by Lola, 611.95 min / 163 tracks, over the 713,299,968 B usable ceiling by about 21 MB. Her save choices (trim the ~10 min "Bite Me" trailing silence, about 12 MB, and/or drop Poodle Hat and Off the Deep End to 128 kbps, about 25.5 MB) are still pending, and the author's capacity gate still refuses rather than overfill.
- Claude lane: first full cycle complete on 2026-10-23 (commit `3ff381d`, validate.py 30/30, 67-test suite green, published). The Aero-glass UI mock is still unwired to the real core (bitrate ladder, per-track overhead math, Groups UI).
- Two-group disc capability: proven on 2026-10-23, still untested as a regression test — that is exactly what the stalled groups task is for. Do not confuse the proven capability with the debris `test_disc_groups.py` file.
- Quri MiniDisc watch framing: unchanged — NetMD is a different Sony silo from OpenMG SAL, so it will not unlock the ATRAC CD cipher; value is methodology cross-pollination only. No Quri development was reported on 2026-10-26.
- Context constraint for the next few days, from the 2026-10-26 evening conversation (not this goal's work, but it governs timing): Lola was ill on 2026-10-26 — cloudy, foul-smelling urine with shivering and a warmer-than-usual forehead, after blood in her urine on 2026-10-25 and vomiting about a third of a Subway wrap on the morning of 2026-10-26 — and she sent a MyChart message to Hillside that evening; she was awaiting a reply. She was resting and watching YouTube late on 2026-10-26. Do not nudge ATRAC work, the groups test, or the Weird Al save choice until she leads the return; the guardrail refresh on 2026-10-28 at 16:03 PDT is the earliest natural reopening, and her health reply may matter more than that date.
- The assignment's teach-mode task plan (target skill, retrieval prompt, worked example, practice task, feedback rubric, transfer challenge, confidence check, next review 2026-10-28T05:24:08Z) was treated as scheduler metadata for this outcome goal, consistent with the prior notes — not as a skill class. No mastery estimate is made, and no learning-style claim is made.

## Open questions and watch items

- Finish the groups test (see above), then validate whatever `tests/test_groups.py` it writes before it enters the tree, under the usual merge-point rule: the mini and Claude lanes grind locally; Muse diffs, re-validates against her reference discs, and merges/publishes.
- Confirm the restored `test_clamp_string.py` is committed at the next merge.
- Post-refresh SAL thread: why the shim's return path never runs in the Unicorn harness (readout #20 addendum 6).
- Weird Al save choice, unchanged: silence trim, mixed-rate fallback, or both, decided at build time with the capacity gate as final say.
- Paid decision, unchanged from 2026-10-23: Lola leans toward subscribing, the free trial is the honest test, and the 50/90 guardrail gets redrawn with her when she pays.

## Already Covered in Main Chat

- Main agent told Lola the D-NE1 charging cradle and battery pack were delivered, In/At Mailbox, Ukiah, at 9:50 am PDT on 2026-10-26, confirmed by two live reads.
- Main agent told Lola, on seeing her photo, that receipt was confirmed and the shipment watch was closed, while the box hunt itself stays open.
- Main agent told Lola the boxed D-NE1 listing she passed on sold for £58.00 with 3 bids, UK postage only, and that listing watch is done.
- Main agent told Lola the cradle arrived the day she got paid, a full pay cycle after she bought it last month, in a light exchange about the timing.
- No main-chat turn on 2026-10-26 discussed the ATRAC app, the SAL cipher, the clamp_string suite, the mini OpenCode lane, the groups test, or the Weird Al disc.

## Research Trajectory

### External sources viewed
- None this run. No external fact was needed: today's only goal-adjacent event (the cradle delivery) is evidenced by Lola's own photo and the main-chat tracking reads, and the goal's code state is unchanged.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-25/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. It carries the clamp_string green run, the 40960 context cap, the health-check totals, and the stalled groups test; everything in it still stands, and nothing on 2026-10-26 supersedes it.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-24/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. Its durable findings (clobber/rebuild, SSH-from-MacBook-Pro proof, guardrail until 2026-10-28 at 16:03 PDT) still govern and were not re-derived.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-23/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — checked in the repetition search; it carries the two-group proof and the 2026-10-23 note that the stand hit the San Francisco distribution center, but not the 2026-10-26 delivery.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-22/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — checked in the repetition search; its durable findings (SESSION02 reservation, byte-faithful author, SAL phase-7 frontier, merge-point discipline, guardrail values) still govern and were not re-derived.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/briefs/D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html` — filename-checked; it is the goal's only prior brief and its topic (the bitrate ceiling) does not cover today's delivery or any open item.
- Repetition search (required): variants `ATRAC`, `groups test / test_groups`, `clamp_string`, `charging cradle / battery pack / D-NE1 cradle`, `SAL / phase 7`, and `Weird Al`, grepped over this goal's `agent_notes/` and over the `briefs/` filename listing. Results: `groups test` and `test_groups` hit only in the 2026-10-25 note (the stalled test, not a completion); `clamp_string` hits only in the 2026-10-22 through 2026-10-25 notes (bug discovery, single-shot win, clobber/rebuild, green run — no new run on 2026-10-26); `battery pack` hits only in the 2026-10-23 note (the stand in transit, not delivered); no prior note or brief covers a 2026-10-26 ATRAC finding, because there is none. The no-material-change ruling below rests on the main-chat rule and on the absence of new evidence, not on prior-note coverage of a new topic.

### Scaffolds and support tactics
- None applied. This is an outcome/project goal (category: interests); the assignment's teach-mode task plan was treated as scheduler metadata, not a skill class, consistent with the prior notes. No mastery estimate made — the goal is not a learned skill, and no learning-style claim is made.

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline through phase 7 readout #17, briefing history with the single 2026-10-22 bitrate-ceiling brief, file associations). Goal files were listed by timestamp: nothing under `files/` is newer than 2026-10-24. No other connector data was relevant to this reverse-engineering/build goal today.

### Image references checked
- None opened as files in this study. Lola's 2026-10-26 photo of the cradle and battery pack in her hand was analyzed live in main chat, and its verdict (receipt confirmed, shipment watch closed) is preserved above. Avatar state is not relevant to this technical goal.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis): the 50%/90% usage guardrails, the mini-mirror and Claude-lane merge-point rule, "never declare playable from code" (160 kbps remains unproven until her D-NE1 says otherwise), verify-on-disk-before-announcing, and the single-shot-only mini-lane rule — all applied and reflected above. Memory search corroborated the 2026-10-26 delivery entry (`memory/2026-10-26.md#L110`) and the 2026-10-25 mini-lane entries (clamp_string green, 40960 context, health-check debris, groups stall at `memory/2026-10-26.md#L127` and `MEMORY.md#L26`); memory was used only as corroboration, not as the source.

### Searches skipped or unavailable
- No web searches: today's findings are primary evidence from Lola's own photo, her runs, and main-chat evidence — no external fact needed a lookup.
- No separate connector reads beyond `user_goal.get` and the run's conversation evidence: the recent main-chat transcript for the window 2026-10-26T05:24:09Z–2026-10-27T05:24:08Z was read in full via `muse.context_fetch` (conversation category), and it contains no ATRAC-app discussion.
