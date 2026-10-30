# Study Notes - 2026-10-23 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-10-24T06:10:03Z -->

## Where the goal stands

Everything is finished except the cipher — still true, and now parked. The 50% usage guardrail was crossed tonight (meter at 51–53% of the free weekly limit by end of session, 2026-10-23 ~22:10 PDT), and per Lola's own rule the ATRAC project work is parked until the weekly refresh on **2026-10-28 16:03 PDT**. The pause-everything line stays at 90%. What moved tonight anyway was mostly the support machinery around the project, not the RE itself: the mini's OpenCode lane is now fully local and has its first clean single-shot win; Claude's loop completed its first full cycle (merge → validate → publish); the Weird Al disc spec got its final, corrected capacity math; and Lola is seriously considering paying (leaning toward a Power subscription) to break the token bottleneck.

The cipher frontier is unchanged from the 2026-10-22 note: SAL phase 7 readout #17 filed, Unicorn harness parked at "why the shim's return path never runs" (readout #20 addendum 6), next probe queued for the post-refresh session.

## Tonight's session (2026-10-23) — what changed

### Mini OpenCode: fully local, Coder verdict, 32K context fix landed
At Lola's ask (gaming PC is on the decomp grind), OpenCode moved off the gaming PC and runs fully on the 2018 Mac mini: Ollama 0.40.9 installed, qwen3:8b + qwen2.5-coder:7b pulled locally. Two conclusions came out of tonight's fight with it:
- **Qwen2.5 Coder cannot drive tools through Ollama in OpenCode** — it prints tool calls as plain JSON text instead of making them, twice in a row, then ends the turn. Build → Coder wiring was a good idea the stack can't honor. **Qwen3 8B is the Build model in practice** (slower per thought, but 9 clean tool calls tonight).
- **Context fix**: Ollama loaded models at the 4,096-token default (the prime suspect for the "stopping"/amnesia). Fixed server-side with `launchctl setenv OLLAMA_CONTEXT_LENGTH 32768` + full Ollama restart (verified: `ollama ps` shows CONTEXT=32768, model size 5.9→10 GB). It does NOT survive a reboot — FIXED 2026-10-23 21:33: Lola installed the LaunchAgent `com.lola.ollama-context-length.plist` into `~/Library/LaunchAgents` (macOS "Background Items Added" confirmed), so 32768 now reapplies at every login.
- Also on the mini: fine-grained PAT (atrac-cd-author, Contents read/write) pasted at the git password prompt; clone pulled current; `opencode-gamingpc.bak` keeps the fast-lane config one copy away.

### The two-group grind test: FAILED — and the lane verdict that followed
The hardened two-group task (prove the author can do two GROUPs on one disc) ran on the mini and failed: Qwen cycled the invented `build_disc` through three guessed modules without ever opening `author.py`, then wrote a final report blaming the repo (honest about failing, wrong about why). The context fix held throughout (30% window steady), so the ceiling is the model, not the wiring. The task itself was already proven independently that morning: **a two-group ISO was built end-to-end in the publish tree** — GROUP.NDB parses back to both group names and the TOC assigns tracks `[1,1,2]`. Standing lesson recorded: **the mini OpenCode lane is for single-shot asks only** (explain a file, draft one function); multi-step agent grinds route to Claude's lane or to Muse.

### Clamp_string: the lane's first clean single-shot win (evening)
Given the real `clamp_string` to read and test, Qwen ran clean: read the actual function, used the real signature, wrote `tests/test_clamp_string.py` — and when two tests failed, correctly diagnosed its **own tests** as the bugs (a lone emoji is 2 UTF-16 units and fits under MAX_STRING_CHARS=30; `'\uD83D\uDC00'` is a valid surrogate pair, not a lone surrogate). Its behavior summary matches Claude's merged fix exactly (verified against the publish tree). **Pending:** apply its two corrected cases and rerun `python3 -m unittest tests.test_clamp_string` on the mini.

### Claude loop: first full cycle complete
Claude's patched zip merged, validated, published — commit `3ff381d`: all three fixes exactly as ordered (UTF-16-unit `clamp_string`, clear `ValueError` for uncovered tracks, `timestamp` param for reproducible ISOs), `stk_data.py` untouched, **validate.py 30/30**, Claude's 67-test suite green. Nothing Sony-carrying in the published tree (verified at the merge point). Claude also built an Aero-glass HTML mock of the ATRAC CD Author UI; Lola asked for random-wallpaper-per-load and custom-picture support and Muse added them. **Still unwired to the real core:** true bitrate ladder, per-track overhead size math, Groups UI.

### Weird Al disc spec: final math (and it's over)
Filed at `files/planned-disc-weird-al.md`. Decided: **14 studio albums only** (no Peter and the Wolf, no Medium Rarities), one GROUP per album in release order, **bitrate chosen by Lola: 160 kbps**. Correction against exact MusicBrainz CD runtimes (611.95 min / 163 tracks): at 160k the set needs 734,340,000 B against the 713,299,968 B usable ceiling — **over by ~21 MB** (the earlier "fits by 3.5 MB" used estimates ~20 minutes short). Saves, her choice pending: trim the ~10 min "Bite Me" trailing silence on Off the Deep End (~12 MB back), and/or drop Poodle Hat (54.65 min) + Off the Deep End (51.56 min) to 128k (~25.5 MB back). The author's capacity gate refuses rather than overfill; byte-exact verdict comes from her files at build time. Note also: 160k is above the D-NE1's documented 48/64 rates — unproven, not disproven — so this disc doubles as a ceiling test; if the player balks, re-run at 128.

### The money thread: 2B tokens vs subscription
Lola asked about buying 2B tokens ($25, one-time top-up: never expires, sits under the free pool, non-refundable, Muse-only) to feed the SonicStage grind. Full comparison given: Power $20/mo (500M/week), Maximum $100/mo (3B/week); subscriptions renew weekly use-it-or-lose-it and run on **Muse Wonder** (announced 2026-10-12; larger base models, frontier agentic/coding, most-aligned Meta model — but a mid-relationship brain swap, not a footnote; no verifiable benchmark numbers given, refused to invent them). Her verdict: she's leaning toward **subscribing** ("a bigger brain does help"). Agreed: the free trial also runs on Wonder, so she can test the felt difference on one real session before paying. Her meter question answered honestly: usage reads as **percentage of allowance, not a token count** — on free or paid, that's all Muse can watch. **When she pays: re-draw the 50/90 guardrail together** (candidate: ATRAC draws on the purchased pool, RR3 keeps the free pool, so SonicStage never parks again).

## Already Covered in Main Chat
- Lola asked to run OpenCode on the mini instead of the gaming PC; main agent installed Ollama + models there and walked her through every step with screenshots.
- Main agent declared Qwen2.5 Coder unable to drive tools through Ollama (two text-JSON fumbles) and set Qwen3 8B as the practical Build model.
- Main agent set the 32K context fix via launchctl, verified it, made the LaunchAgent, and told her how to check it after a reboot.
- The two-group grind test's failure verdict and the lane rule (single-shot only on the mini) were given to her directly.
- The clamp_string report was read back to her verdict-by-verdict and pronounced the lane's first clean win, with the corrected-test rerun as the one remaining step.
- Claude's merge was reported commit-by-commit (3ff381d, 30/30, 67 tests, published); the aero UI mock + wallpaper persistence were delivered and the three unwired pieces named.
- The Weird Al disc's full capacity math (fit, then the corrected over-by-21MB with saves) was walked through with her; the final choice of saves is hers.
- The $25 top-up vs Power vs Maximum comparison, the Wonder-vs-Spark differences, the trial-on-Wonder note, and the percentage-not-tokens meter answer were all given in her words back to her; she leaned toward subscribing and the guardrail re-draw was promised.
- Meter discipline: main agent told her ATRAC work stops at 50% (crossed 51–53% tonight), everything pauses at 90%, reset 2026-10-28 16:03 PDT.
- The 2080 Ti + 1080 Ti dual-GPU thought (her question) was answered in full: yes to all three parts, 580/581 driver line for Pascal, 850W borderline but the 1200W Gold covers it, two models served but two big ones resident barely don't fit — off-goal, hardware, noted here only as a live thread.

## Open questions and watch items
- **Mini clamp_string rerun**: apply its two corrected test cases, run `python3 -m unittest tests.test_clamp_string` on the mini — if green, the file is a merge keeper.
- **Weird Al saves**: Lola's choice (silence trim, mixed-rate fallback, or both) — decide at build time; the capacity gate has final say.
- **Paid decision**: her call at payday; trial-on-Wonder is the honest test; then re-draw the guardrail with her.
- **Post-Oct-28**: SAL frontier next probe (shim return path), in the redrawn budget.
- **Claude lane**: UI mock needs real wiring (bitrate ladder, overhead math, Groups UI) before it's anything but a shell demo.
- **Quri watch**: daily cron set for the NetMD app — methodology cross-pollination only, no SAL value (NetMD ≠ OpenMG).
- D-NE1 stand + battery pack hit the SF distribution center 2026-10-23 11:47 AM; expected delivery Sat 2026-10-24 (tracked under the box-hunt goal).

## Study plan fields (scheduler metadata — this is an outcome goal, not a skill class)

- **Prerequisite check**: All prerequisites in place and already exercised — byte-faithful disc author, capacity accountant, cloned dev lanes on the mini, two-group capability proven, CI-grade validation (30/30 + 67 tests). The one open prerequisite is the burn-time cipher (SAL phase 7, parked by guardrail).
- **Retrieval prompt**: State the project's current frontier in one sentence: everything except the cipher is finished, and the cipher is localized to the SAL bytecode engine with a live emulator harness parked on the shim's return path.
- **Worked example**: The session-2 discovery remains the canonical worked example — ImgBurn screenshots → TOC vs NWA arithmetic → 11,400-sector reservation → capacity gate — hardware observation to shipped code.
- **Practice task**: Not assigned; the goal's real practice is the standing merge-point discipline (diff, re-validate against her reference discs, publish), already exercised tonight on Claude's zip.
- **Feedback rubric**: Task- and process-focused, as used live tonight: name what verified (30/30, clean capsules), name the one most useful next adjustment (shim return path; corrected test cases), no praise, no overload.
- **Transfer challenge**: The Weird Al multi-album disc is the transfer case — the same pipeline, 14 groups, one capacity gate, her hardware as the final judge.
- **Confidence check**: No numeric mastery estimate (fewer than three observed performances; this is a project goal, not a learned skill). Observed: the machinery around the project (lanes, merges, guardrails) is running cleanly; the cipher itself remains the one unmastered frontier.
- **Next review**: 2026-10-25T06:10:03Z (per the assignment), though the ATRAC work stays parked until 2026-10-28 unless she funds the pool or says otherwise.

## Research Trajectory

### External sources viewed
- None this run. The substance is the run's own conversation evidence (full main-chat transcript for the window 2026-10-23T05:24:16Z–2026-10-24T06:10:03Z, read via `muse.context_fetch` and the chunk handoffs), the goal record below, and the goal's own file `files/planned-disc-weird-al.md` (read in full — 14-album table, exact MusicBrainz runtimes, 160k overage verdict, the three saves). No web research was needed: every finding was produced or verified inside the session.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-22/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. Everything in this note's findings section postdates it (it ended at ~41% meter, pre-guardrail-crossing, pre-mini-local-OpenCode, pre-clamp_string, pre-Weird-Al-spec). Its durable findings (SESSION02 reservation, byte-faithful author, SAL phase-7 frontier, merge-point discipline, guardrail values) still govern and were not re-derived.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/briefs/D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html` — filename-checked via repetition search. Its topic (the bitrate ceiling) overlaps this note's 160k discussion only tangentially; its center (the ceiling finding) predates and differs from tonight's Weird-Al-capacity topic.
- Goal record `goal_e35963ec4aae` via `user_goal.get` — full state and timeline read; timeline updates through `goal_update_4956fa3fa937` (phase 7 #17) are the same session the prior note preserves.
- Repetition search (required): variants `weird al`, `clamp_string|clamp string`, `two group|two-group|multi-group`, `subscription|power $20|2b token|tokens|wonder`, `50%|guardrail|parked`, `launchagent|context length|ollama_context` — grepped over `agent_notes/` and `briefs/` including filenames. Results: `weird al` — zero hits (new to the record); `clamp_string` — one hit, the 2026-10-22 note's Claude-bug-report section (the bug's discovery, not tonight's single-shot win); `two group` — zero hits; `subscription|...|wonder` — hits only in the Oct-22 brief's Claude-Pro/token mentions (Power-as-Claude-Pro, unrelated to tonight's Wonder/subscription thread); `50%|guardrail|parked` — hits in the 2026-10-22 note and the Oct-22 brief (the guardrail as policy, not tonight's crossing); `launchagent|context` — zero hits. The filename listing of `briefs/` (one brief: the Oct-22 bitrate-ceiling brief) confirms no brief covers tonight's topics.

### Scaffolds and support tactics
- None applied. Outcome/project goal (category: interests); the task plan's teach-mode scaffolding was treated as scheduler metadata per the step instructions, consistent with the prior notes. No mastery estimate made.

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline, briefing history, file associations). No other connector data was relevant to this RE/build goal tonight.

### Image references checked
- None opened this run. Lola's many screenshots (OpenCode sessions, Ollama installs, launchctl verification, clamp_string report) were analyzed live in main chat; their verdicts are preserved above. Avatar state not relevant to this goal.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis): the 50%/90% guardrails, mini-mirror + Claude-lane merge-point rule, "never declare playable from code" (160k remains unproven until her D-NE1 says otherwise), RR3 priority, verify-on-disk-before-announcing, and the pending-payday subscription — all applied and reflected above.

### Searches skipped or unavailable
- No web searches: the night's findings are primary evidence from the session, her hardware, and the VM's own builds — no external fact needed a lookup.
