# Study Notes - 2026-11-01 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-11-01T16:15:57Z -->

## Where the goal stands

Between 2026-10-31 18:55 UTC and 2026-11-01 08:22 UTC, in main chat at Lola's repeated direction, Sessions 32-40 transformed this project. The prior study note (2026-10-31) ended with exactly one unknown - op 11's input contract - and no ciphertext. That is no longer true:

- **Op 11 is solved completely** (Session 35): a keyed MAC built from textbook SHA-1 and FIPS DES, clean-room reimplemented, and proven by predicting a fifth reply the oracle then matched byte-for-byte.
- **The header side is closed** (Session 36): nothing validates op 11's reply, it is stored nowhere and never reaches a disc, so the app may choose its own d2 self-consistently.
- **One payload cipher is proven byte-exact** (Session 37): DES-CBC, key = d2[0:8], IV = each track's header InitVector, continuous chain, on all four Ignite tracks. BlockSeed plays no role.
- **Disc 2 proved that proven path is the minority path** (2026-11-01 03:21 UTC report): 430 of 432 tracks on Lola's most-listened disc are decisively NOT the d2 path, so the general BIND_CONTENT path is the critical path.
- **BIND_CONTENT is driven end-to-end but its audio-carrying work document is still not constructible** (Session 40): envelope-only documents return STATUS 0; every audio-carrying variant returns STATUS 1 INVALID_DATA. The one remaining unknown is how the never-delivered burn host assembles that document at burn time from library parts - the same missing host that consumes op 11's reply.

**The ATRAC train is PAUSED at Lola's word** (2026-11-01 07:14 UTC: "Finish this run and post a report for me to read in the morning and then pause this"). Session 40 finished, the morning report was posted at 2026-11-01 08:22 UTC, and no Session 41 has started. Do not start one, and do not nudge the pause; she leads any return. The Toshiba SonicStage thread remains separately parked, also at her lead only - Session 41 option (b) below touches it and is therefore not a harness-only route.

Record lag, unchanged: `user_goal.get` for `goal_e35963ec4aae` still shows the 2026-10-22 current state ("SAL phase 7 opened with readout #17..."). That predates the entire harness era and must not be read as the frontier.

The assignment's teach-mode task plan (target skill, retrieval prompt, worked example, practice task, feedback rubric, transfer challenge, confidence check, next review 2026-11-02T16:15:57Z) was treated as scheduler metadata for this outcome goal, consistent with every prior note. This is a build / reverse-engineering project, not a learned skill with observed performances. No mastery estimate is made, and no learning-style claim is made.

## Sessions 32-34 - op 11 opens

### Session 32 (reported 2026-10-31 18:55 UTC) - byte 1

Op 11's first read is the first field of the 96-byte header. It expects the VM's struct-form serialization, where field 1 begins `[type 01][form 01][flag]`. Since run 174 the harness had fed it the raw disk form - the literal .ATP bytes `01 00 28 2e...` - where byte 1 is `00`. It read that one byte, judged the input malformed, and stopped; key record, content ID, and session state were never looked at. The fix is not flipping the byte (the two forms are different layouts of the same fields), it is producing the struct form - by finding Sony's serializer in pfcom/OMGUtils (the writer twin of a field reader already in hand) or rebuilding the grammar from the reader's dispatch table.

### Session 33 (reported 2026-10-31 20:42 UTC) - grammar recovered, empty reply

The reader's whole grammar was mapped (bools, text, blobs, dates, containers), proven against Lola's own track .opf - a genuine Sony-produced document in this format, parsing perfectly, all 232 bytes. Wrapping the header as a container of eight blob segments (the disk header's pieces, in order) made op 11 run to completion for the first time, no ERR_MALFORMED_INPUT. It returned an empty answer, which pfcom rejected downstream ("Invalid OMG Header" - wants 8 bytes, got 0): the segmentation was type-correct but not yet the real caller's segmentation.

### Session 34 (reported 2026-10-31 21:55 UTC) - the gate is a name: "fopenMG"

The program's only input check compares the header document's first element against the 7-byte string `fopenMG` - the OpenMG file-open function's name, sitting in OMGUtils.dll beside "OMGF: bad version". With the name in place the gate opened and op 11 returned its first non-empty reply: for track A0, `81 50 39 3f 51 e2 38 48`, reproducibly byte-for-byte. It is NOT the BlockSeed; flipping one IV byte avalanches the whole reply, and a different track gives a completely different answer. "fopenMG" was flagged to Lola as an Easter egg candidate (see below - still unfiled at this study).

## Session 35 (reported 2026-10-31 23:27 UTC) - op 11 solved

- The supposed custom table cipher is a keyed MAC built from textbook SHA-1 and FIPS DES. The 92-byte "EKB workspace" was a SHA-1 context (its "NIST test pattern" was the SHA-1 initial value); the byte tables were bit-sliced DES, proven FIPS-identical.
- Proof standard: the clean-room Python (no Sony code) reproduced all four known replies and **predicted a fifth reply for a document the oracle had never seen, wrote it down first, and the oracle returned exactly those bytes**. The main agent re-ran the implementation himself before reporting: all four match.
- Document shape pinned: the program reads only element zero (the name) by index; everything else is eaten as raw bytes in candidate order.
- **Fork F1 survives, one byte:** the name element's tag is 04 in everything that works, but Sony's own parser (OMGUtils parseOmgFile) insists on 06 for that name. Both variants are built and oracle-validated. Plan, unchanged: A/B that byte on a real D-NE1 test disc; the player gets the final vote.

## Session 36 (reported 2026-11-01 00:34 UTC) - nothing validates the reply; header side closed

- All five known reply values are absent from every file in the reference tree, with a structural proof: the four real track headers differ only at BlockSeed and IV, so an avalanching stored value would have left fingerprints. The reply is transient, passed hand-to-hand inside the burn process.
- Its only consumer is the never-delivered burn host, whose interface only checks the reply is 8 bytes long and copies it verbatim - no comparison, no storage, no content validation. The D-NE1 cannot be checking it either: it never reaches the disc.
- Ceremony inputs sorted: ckey (24 bytes) is ephemeral, mixing the live clock at one-second granularity, and feeds only a dead-end value anyway; X8 is clock data; **d2 (20 bytes) - the one value the reply actually depends on - is a proven constant** of Lola's installed OpenMG state, identical across 15 sessions, clock shifts, and swapping the maclist pair generation.
- Punchline for the app: since nothing validates the reply, the app does not need Sony's d2. It can pick its own and be self-consistent.

## Session 37 (reported 2026-11-01 00:53 UTC) - the Ignite payload cipher, byte-exact

- **DES-CBC-ENCRYPT(payload, key = d2[0:8], IV = header InitVector @ +0x58), continuous chain.** Byte-exact on all four Ignite tracks; the main agent re-ran validation himself before reporting. It fell to the first battery: 2,703 candidate constructions screened, exactly one family standing.
- BlockSeed plays **no role** in encrypting the audio, and the ephemeral ckey plays none either - no time bomb in the design. Given d2, this path is fully self-contained, and the clean-room `encrypt_payload` matches the author's cipher contract shape.
- **Caveat, load-bearing:** Talk, Dreamer, and Electric - three other tracks from the same reference disc - fit **nothing** across ~3,300 further constructions. Their headers carry a different +0x50 value than the Ignite batch. Working hypothesis, still a hypothesis: library-sourced (.OMA) burns take the d2 path; fresh-source tracks take the general BIND_CONTENT / atpcd.ocm path. Do NOT ship the d2 cipher as "the" cipher until the general path arbitrates it.

## Test-disc readiness checklist (filed 2026-10-31 evening, goal files)

`files/test-disc-readiness-2026-10-31.md` - prepared while Session 38 ran, grounded in on-disk checks, nothing integrated yet, main agent remains the one merge point. Key preserved warnings:

1. **The author still ships the placeholder.** `atrac-cd-author/src/atrac_author/cipher.py` binds `encrypt_payload` to the identity placeholder - discs authored today are structurally exact but their audio is NOT encrypted and will not play. Do not burn a "test disc" from the author until the payload_cipher swap (`scratch/s37/payload_cipher.py` + `fastdes.py`) is actually made and re-validated; its function shape already matches the author's contract, so integration is a one-binding swap.
2. **cipher.py's docstring is stale** - it says the cipher is "seeded per instance from BlockSeed + InitVector"; Session 37 proved BlockSeed plays no role. Rewrite it at integration time so a future reader (or Claude / the mini lane) does not re-chase BlockSeed.
3. **payload_cipher.py's docstring overclaims** - it says byte-exact reproduction includes "the Dreamer/Electric pairs"; Session 37 says Talk/Dreamer/Electric fit nothing. Treat that docstring line as wrong until the general path arbitrates.
4. **Secure-header per-track values are still random placeholders** in the author (`SecureHeader.fresh()` generates MgD (+0x50) and the +0x30 slot randomly). Session 29 proved the real +0x50 for the Ignite batch equals GET_GLOBAL_SEED and is identical for identical content. Whether the D-NE1 checks MgD is unknown; the first test disc answers it.
5. Suggested first test disc (Lola's call, not decided): small, a handful of tracks, one group, at a proven rate first (64k - her standard, every reference disc is 64k). Not the 163-track Weird Al disc. Success criterion is her ears/screen only - an ISO that builds is not "playable" until she reports the D-NE1 playing it.

## Session 38 (reported 2026-11-01 02:02 UTC) - BIND_CONTENT runs; the page-pool fence

- Grammar transcribed and verified from omgatpcd.dll's COM methods (FUN_6160571e, selector int 1); OP-A reproduces its old runs byte-for-byte, so the drive mechanics are proven.
- On the envelope document BIND executes with STATUS 0 and does its full ceremony: stamps the track's .opf, updates the key envelope, returns two 32-byte key strings plus a module BlockSeed, no host file I/O. The audio blob rides **inside** the envelope's inner container, after the key blob and two integers.
- Fence at that point: the SAL VM's private page pool ran dry at full track size. Slices up to 600 KB sailed through; a full 1.29 MB track died with a no-free-pages error. Read at the time (correctly) as a harness ceiling, not a module limit.

## Disc 2 lands (2026-11-01 02:18-03:21 UTC) - the census that reordered priorities

- Lola offered the ISO of "the second disc, the one I listen to most" (02:18 UTC), chose to make the full ISO anyway after the main agent narrowed the ask to just the HIFI folder (the root paperwork - STK, NDBs, both STIs - was already banked from 2026-10-22), and uploaded it via MEGA (02:50 UTC). First download died at exactly 512 MB when the scratch sliver filled; restarted onto the big disk, it landed.
- **FavoriteDisc.iso, 685,572,096 bytes** (`~/workspace/atrac-cd-stage0/disc2-iso/`): content-verified as ISO 9660 (not just size), and every root file is byte-identical to the disc-2 paperwork held since 2026-10-22 - provably her 432-track country disc.
- All 432 .ATPs extracted (`disc2-iso/extracted/HIFI/`) and screened (`disc2-census.csv`): **430/432 decisively NOT the d2 path** (the 2 flickers are a first-byte coincidence at the rate chance predicts), 422 distinct +0x50 values, EKB 65550 uniform.
- Consequence, stated in the morning synthesis and still the priority: the proven cipher covers the Ignite batch, but the disc Lola actually lives with runs essentially end-to-end on the general BIND path. That path is THE critical path, not a side case.

## Session 39 (reported 2026-11-01 04:59 UTC) - page pool cracked; S38's frame was an approximation

- **Page pool cracked:** its size is the registry value `SalMemorySize` (REG_DWORD, default 0x400000) under `HKLM\SOFTWARE\Sony Corporation\OpenMG`. The harness now seeds 32 MiB and full-size BINDs run with NO NOMEM. (Curated record adds: the per-instruction EIP-ring hook - the old time wall - is now off.)
- With memory fixed the bind still refused tracks, and transcribing the real BIND_CONTENT method showed why: Session 38's drive approximated its call frame. Per the S39 report, the real method mmaps a template .ATP, looks up source audio in a repository by a 16-byte ID, reads the whole .OMA, and writes transformed audio back into the staged files.
- **Correction carried by Session 40 (do not reuse S39's feeding picture):** "feed the real .OMA" was REFUTED - the module parser raises on raw EA3. What survives from S39 is the page-pool fix and the conclusion that S38's hand-rolled documents were being judged in the wrong slot.

## Session 40 (reported 2026-11-01 08:22 UTC, runs 221-238) - the drive is solved, the transform is not

- The real BIND_CONTENT is driven end-to-end for the first time: **four stack args** (not three), and **repository identity = the OP-A key16 buf16, NOT the CID16** - proven via the sibling MEDIA-INFO method, which returns 0 with that identity staged.
- S38's frame was verified operand-by-operand IDENTICAL to the real frame - so the remaining failure is not a harness gap.
- Verdict matrix: envelope-only document -> STATUS 0; **EVERY audio-carrying variant -> STATUS 1 INVALID_DATA**, repository unchanged, template never stamped. Variants tried: different wrappings, sizes, key choices, and even the module's own freshly-stamped envelope.
- **The one remaining unknown:** the burn host assembles the BIND work document at burn time from library parts. No audio-carrying repository record exists anywhere in the delivered corpus. That host is the same missing piece that consumes op 11's reply.
- **Session 41 options, recorded and NOT started (pause stands):** (a) reader-walk diff of accepted-vs-rejected documents - harness-only, needs nothing from Lola; (b) real-host capture from the Toshiba - PARKED thread, Lola's lead only; (c) static lift of atpcd.ocm selector-1 to read its document schema directly.
- No new Easter eggs in Session 40.

## Smaller threads in this window

- **Easter egg candidates #5 and #6 - still unfiled, awaiting Lola's call.** On 2026-11-01 15:24 UTC the main agent asked: #5 "!!" (omginit's -reset message box, entire text "!!", no caption - first reported 2026-10-29, Session 24) and #6 "fopenMG" (Session 34's gate name). This study verified on disk: `files/easter-eggs.md` still holds only #1-#4. No answer from Lola appears in this window. Publishing hold stands either way: filed eggs stay local until the project officially ships, then are appended to the project README.
- **Walkman Studio sighting (2026-11-01 05:38 UTC) - tangential, not a lead.** Lola shared a Reddit r/walkman post ("Huh"). Reddit blocked the fetch; from the redirect title and the project itself, the main agent identified Walkman Studio, a native macOS manager for flash-based non-Android Walkmans (NW-A55 family) - ID3/FLAC tagging, lyrics, FFmpeg transcoding, M3U8, safe eject. It is NOT for the D-NE1, has no ATRAC CD / OpenMG anywhere in it (a different Sony silo), and is Apple Silicon only - her Intel Macs cannot run it, though a future Neo could. No follow-up was requested or promised.
- **iPad burning (2026-11-01 04:57 UTC).** Lola: "Be awesome if the iPad could burn a cd". Answer given, and it matches the app's existing design: iPadOS offers apps no CD-burner command path (no driver / burn API), so the iPad cannot write a disc itself - but the web app runs in Safari on the iPad, so authoring (tracks, groups, finished ISO) can happen entirely on the iPad, with the Mac's only job being writing that ISO to a blank.
- **Usage:** Lola noted 6% at 2026-11-01 05:03 UTC after a heavy parallel night (seven harness sessions, two Vita builds, a 432-track screening, an ISO download rescue) - "On free we'd already used up 30-50%". The Power-plan rule stands as redrawn on 2026-10-30: soft heads-up near the top of the week only, never a stop; weekly reset 2026-11-06 19:32 PST. Do not revive the old 50%/90% lines.

## What did not change

- Encoder: done. ISO builder: byte-exact. Author pipeline: built and validated, but still binding the placeholder cipher (see readiness checklist) - no integration of payload_cipher happened in this window.
- Weird Al disc: unchanged, still awaiting Lola's save choice (14 studio albums, one GROUP per album, 160 kbps, 611.95 min / 163 tracks, ~21 MB over the 713,299,968-byte usable ceiling; saves pending: trim ~10 min "Bite Me" silence and/or drop two albums to 128k). Capacity gate refuses rather than overfills. 160 kbps remains unproven, not disproven, until her D-NE1 says otherwise.
- Re-Volt soundtrack disc: unchanged - both soundtrack CDs from the pre-ordered H2 Edition (order #1007, releases 2026-11-05) onto one ATRAC CD, exactly 2 groups "CD1" and "CD2", capacity a non-issue. Waits on the H2 Edition arriving plus the (general-path) cipher.
- Mini Qwen groups test: no outcome was reported in this window either. Do not declare it done; the merge-point rule still applies to whatever it eventually writes.
- Toshiba SonicStage: untouched, parked at Lola's lead. Never default to it when "SonicStage" is ambiguous.

## Open questions and watch items

- Paused frontier, exactly one unknown: how does the burn host assemble the BIND work document at burn time? Session 41 options (a) reader-walk diff, (b) Toshiba real-host capture (her lead only), (c) selector-1 static lift - all wait for Lola to unpause.
- Fork F1 (tag 04 vs 06) can only be settled by a real test disc in the D-NE1, which itself waits on: payload-cipher integration into the author, the MgD/+0x30 question, and a decision on which content path a fresh burn takes (a fresh-source test disc may depend on the general path, not just the proven d2 path).
- Easter eggs #5/#6: file one, both, or neither - Lola's call, asked 2026-11-01 15:24 UTC, unanswered in this window. Standing watch for further dev traces continues under the same publishing hold.
- Do not reuse superseded framings: (1) BlockSeed keys the payload (Session 37: no role); (2) payload_cipher is "the" cipher (it is the library/.OMA path only); (3) S39's "feed the real .OMA" (Session 40: parser raises on raw EA3); (4) S38's approximated BIND frame as the real method's contract (Session 40 drove the real method, 4 args, key16 identity).

## Already Covered in Main Chat

- Main agent told Lola Session 32 found op 11's failing check is byte 1: struct-form `[type 01][form 01][flag]` expected, raw disk form `01 00...` fed since run 174.
- Main agent told Lola Session 33 recovered the struct-form grammar, validated on her track's 232-byte .opf, and op 11 ran to completion returning an empty reply pfcom rejected.
- Main agent told Lola Session 34 found the gate name "fopenMG", op 11 returned its first non-empty reply (`81 50 39 3f 51 e2 38 48` for A0), and it is not the BlockSeed.
- Main agent told Lola Session 35 lifted op 11 completely - textbook SHA-1 + FIPS DES MAC, clean-room reimplementation, fifth reply predicted then oracle-matched - with Fork F1 (tag 04 vs 06) the one surviving byte.
- Main agent told Lola Session 36 proved nothing validates the reply, it never reaches a disc, ckey/X8 are ephemeral clock material, d2 is a proven constant, and the app may choose its own d2 - header side closed.
- Main agent told Lola Session 37 found the payload cipher byte-exact on all four Ignite tracks (DES-CBC, key d2[0:8], IV = header InitVector, BlockSeed no role), and Talk/Dreamer/Electric fit nothing.
- Main agent told Lola Session 38 ran BIND_CONTENT end-to-end with STATUS 0 on the envelope document, located the audio slot inside the envelope, and hit the SAL page-pool ceiling at full track size.
- Lola offered disc 2's ISO, made and uploaded it via MEGA despite the HIFI-only narrowing, and the main agent told her it content-verified as her 432-track country disc with all root files byte-identical to the 2026-10-22 paperwork.
- Main agent told Lola the disc-2 census is decisive: 430/432 tracks are NOT the d2 path, so the general BIND path - not the proven cipher - covers the disc she listens to most.
- Main agent told Lola Session 39 cracked the page pool (registry SalMemorySize, harness seeds 32 MiB, no more NOMEM) and exposed that Session 38's BIND frame was an approximation of the real method.
- Lola told the main agent to finish the current run, post a morning report, and then pause; the main agent posted the Session 40 report (drive solved - 4 args, key16 repository identity, raw-.OMA feeding refuted; every audio-carrying document STATUS 1 INVALID_DATA; one unknown = burn-host document assembly; Session 41 options a/b/c) and parked the train.
- Main agent told Lola Walkman Studio (from her Reddit link) manages flash-based non-Android Walkmans only, is Apple Silicon only, and has no ATRAC CD / OpenMG relevance to the D-NE1.
- Main agent told Lola the iPad cannot command a CD burner under iPadOS, but can do all the authoring in Safari with the Mac only writing the finished ISO.
- Main agent asked Lola whether to file Easter egg candidates #5 ("!!") and #6 ("fopenMG"); the eggs file still holds #1-#4 and no answer appears in this window.

## Research Trajectory

### External sources viewed
- None opened by this study. The Walkman Studio identification in this window was made by the main agent in chat (Reddit itself blocked the fetch; the redirect leaked the title) - this study preserves that main-chat reading and claims no independent web verification of Walkman Studio's feature list beyond it.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-31/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` - read in full. It carries the frontier through Sessions 26-31 (door (b) closed, armed road, generation verify rule, live pfcom session, GET_GLOBAL_SEED byte match, op 11 narrowed to its input contract, Session 32 specced but not started). This note supersedes its endpoint on every point: Sessions 32-40 all ran in this window.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-10-30/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` - read in full for continuity (Sessions 21-25, OP-A, BIND as key-binding in its phase-2 reading - a framing later sessions substantially revised; do not reuse its "BIND_CONTENT is key-binding only / audio never passes through it" as the current contract).
- Repetition search (required): keyword variants `op 11`, `BIND_CONTENT`, `payload cipher` / `DES-CBC`, `SalMemorySize` / `page pool`, `FavoriteDisc` / `disc 2 census` / `430`, `fopenMG`, `INVALID_DATA`, `Session 40` / `Session 41`, `test-disc`, and `Walkman Studio`, grepped over this goal's prior notes under `agent_notes/` and its prior briefs under `briefs/`, filenames included. Results: the only prior brief is `D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html`, whose topic overlaps none of today's material. In prior notes, `op 11` and `BIND_CONTENT` appear only in the 2026-10-30/31 notes in their pre-solution senses (op 11 as the open input-contract unknown, Session 32 "next and not started"; BIND as key-binding only). `DES-CBC`, `payload cipher`, `SalMemorySize`, `FavoriteDisc`, `fopenMG`, `INVALID_DATA`, `Session 40`, `Session 41`, `test-disc`, and `Walkman Studio` have zero hits in any prior note. Today's topics are therefore genuinely new to the preserved record - but, as the ruling rests on, every one of them was delivered to Lola in full in main chat, session by session, ending with the 2026-11-01 08:22 UTC morning report she explicitly requested before the pause.
- Ruling note: a `create` ruling would produce a Letter whose centre - op 11 solved, header side closed, the Ignite payload cipher, the disc-2 census, and Session 40's one-remaining-unknown verdict plus the pause - was already said in the recent conversation by the main agent, with Lola herself supplying disc 2, directing each continuation, and ordering the pause and the morning report. Under the step rules that is `no_material_change`, even though the findings are new to the preserved note record. This note is the preservation vehicle for the next study.

### Scaffolds and support tactics
- None applied. This is an outcome / project goal (category: interests); the assignment's teach-mode task plan was treated as scheduler metadata, not a skill class, consistent with all prior notes. No mastery estimate made, and no learning-style claim made.

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline, briefing history with the single 2026-10-22 bitrate-ceiling brief, file associations). The goal record's current state lags the harness progress by over a week, as flagged at the top of this note.
- On-disk checks made by this study: `files/test-disc-readiness-2026-10-31.md` read in full (placeholder warning, stale docstrings, MgD question, Fork F1, suggested test-disc shape); `files/easter-eggs.md` read in full (still entries #1-#4 only, publishing hold intact); disc-2 census header and first rows at `~/workspace/atrac-cd-stage0/disc2-iso/disc2-census.csv` spot-checked (class `not-d2`, EKB 65550), with the full 430/432 verdict taken from the main-chat report and the curated record, not from a recount by this study. No other connector data bears on this goal today.

### Image references checked
- None opened as files in this study. No new image evidence bears on this goal in the window; the session evidence arrived as main-chat reports the main agent verified against harness logs and his own re-runs (Sessions 35 and 37) before reporting. The avatar state file was not needed - no visual context bears on this goal.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis) applied: the ATRAC pause at Lola's word (2026-11-01, after the Session 40 report - no Session 41 until she says go), the redrawn Power-plan usage rule (soft heads-up only, never a stop; reset 2026-11-06 19:32 PST), the Easter-egg publishing hold and standing watch, "never declare playable from code" (a built ISO is not a playable disc until her D-NE1 plays it), the SonicStage fork rule, the merge-point rule for Claude / the mini lane, and her build-test / screen-as-verdict conventions.
- `muse.context_fetch` (conversation category) for the window since the last run (2026-10-31T16:10:17Z to 2026-11-01T16:16:05Z): Sessions 32-40 launches and reports, the test-disc readiness filing, Lola's disc-2 offer / ISO upload / download rescue / census report, the iPad-burning exchange, the Walkman Studio sighting, the usage remark, her pause instruction, the Session 40 morning report, and the unfiled Easter egg question - the primary evidence for this note.

### Searches skipped or unavailable
- No web searches by this study: today's findings are primary evidence from Lola's own project sessions and her own disc, reported and re-verified in main chat; no external fact needed a lookup. Walkman Studio was identified by the main agent in chat after Reddit blocked the direct fetch - noted above as a preserved main-chat reading, not independently verified here.
- No device, calendar, or messaging reads: none bears on this goal's paused cipher frontier today.
