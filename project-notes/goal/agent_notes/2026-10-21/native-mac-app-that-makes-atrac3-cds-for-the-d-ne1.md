# Study Notes - 2026-10-21 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-10-22T05:31:21Z -->

## What this goal is

Lola's own scoping, 2026-10-21 (America/Los_Angeles): "All I want is a native Mac app that makes Atrac3+ CDs for my NE1." One job only — author ATRAC3+ CDs her Sony D-NE1 plays, natively on her Intel Macs (daily driver: 2014 MacBook Pro on OCLP Tahoe), with no Windows machine and no SonicStage. Not a SonicStage clone, no library management, no NetMD. Two additions she made the same evening:

- The app converts ordinary audio files itself (MP3/WAV/FLAC in, ATRAC3+ CD out; decode → resample 44.1 kHz/16-bit → encode → encrypt → author), so there is no convert-then-import step in her life. Source tags carry into the disc data.
- The GUI should look and feel like the original SonicStage (pane layout, disc/groups view, transfer/burn flow, purple-era look) rebuilt on native Mac controls — at the app-shell stage, after the pipeline works.

Standing boundaries: RR3 Vita is the live focus; this project's stage-0 moves when Lola sends files. The SonicStage 4.3 Toshiba crash thread stays paused at her word since 2026-10-03 — this goal does not un-park it. All tooling named so far is free/open-source; flag any cost before it appears. Never declare a disc playable or unplayable from files or documents alone — her D-NE1 and her ears are the only verdict.

## Stage-0 state carried in (all established 2026-10-21 evening, in main chat and the goal's files/)

Three workstreams, in the order the evidence revealed them:

1. **Disc layout — largely mapped.** From `CD_stuff.zip` (a subset of one of her SonicStage-burned discs): audio in `HIFI/*.ATP` (ID3v2.4 tag, 1,024 B, UTF-16 TIT2/TPE1/TALB); databases `TRACK/ALBUM/ARTIST/GROUP/PLLIST.NDB` in a fixed-record "NDB " format; `TOC00000.STI` ("TOC ") / `TOC00001.STI` ("PLF "); `0001000E.STK` ("EKB ") key block. TRACK.NDB decoded: 256-byte header + 128-byte records, header count 493 tracks, arithmetic lands exactly on the 63,360-byte file size; titles are UTF-16BE "ARTIST - TITLE" strings. That disc is a full 64 kbps burn (~610 MB). Remaining layout unknowns are field semantics, which the .STI TOC parse and the SonicStage DLLs should pin down. (Goal files: `stage0-disc-readout.md`.)
2. **Encoder — atracdenc exists and round-trips.** Built from source on the Linux VM 2026-10-21: encoded a 44.1 kHz stereo WAV to an ATRAC3+ .oma at 352.8 kbps that ffprobe identifies as atrac3p and ffmpeg decodes back cleanly. Mac Intel build unverified (same CMake + libsndfile shape). (Goal files: `stage0-encoder-brief.md`.)
3. **Burn-time encryption — the main RE unknown.** The disc .ATP payload measures 8.000 bits/byte entropy (pure noise) and ffprobe rejects it, while her library file `1-07_It_s_Alright.OMA` is clean, unencrypted EA3/OMA ATRAC3+ at 64,771 bps that ffmpeg decodes fully. Conclusion: encryption is applied at the burn step only, and byte rates match across the boundary, consistent with a length-preserving cipher. The .STK is the OpenMG EKB key-block family the linux-minidisc community partially documented for NetMD/Hi-MD. (Goal files: `stage0-readout-3-oma-and-listing.md`.)

The binary map is complete and batch 2 is pending from Lola (one small zip): the layout writer `CDRFormatter.dll` + `CDWalkman.dll` + `OpcAtp.dll`/`AtpFringe.dll` in `Common Files\Sony Shared\AVLib` (plus the CdrSS burn engine and two burn logs from her own machine, `CDRFormatter.log`/`CdWalkman.log`), and the protection core `omgatpcd.dll` + kdrm/EKB stack + the whole `OpenMG\ekb` folder (real .ekb files of the same family as the disc's .STK) in `Common Files\Sony Shared\OpenMG`. Triage of the first four binaries she sent: `Omgjbox.exe` only orchestrates; the format/crypto internals live in those DLLs. Next step after batch 2 is Ghidra time on the formatter and the EKB path. (Goal files: `stage0-readout-4-avlib-openmg-map.md`.)

Bitrate spec (Lola, 2026-10-21): 64 kbps is her standard burn rate; she wants higher rates available too, "so I can fill more of the CD with smaller playlists." Main chat verified empirically that atracdenc's ATRAC3+ output is fixed at 352.8 kbps with `--bitrate` ignored for 3+.

## New finding 1: the D-NE1's own manual documents only 48 and 64 kbps for ATRAC3plus

This is the finding that changes the project's risk map, and it was not in tonight's conversation or any prior note.

Sony's D-NE1 Operating Instructions (© 2003 Sony Corporation, model D-NE1, page 6-GB, read in full this run) state, under "ATRAC3plus and ATRAC3": **"The available transfer bit rates are 64 kbps and 48 kbps"** for ATRAC3plus (ATRAC3: 132/105/66 kbps). No 256, no 352. The same manual caps ATRAC CDs at 255 groups / 999 files and ISO 9660 Level 1/2 + Joliet — consistent with what the stage-0 disc readout already assumes.

Contrast that must not be blurred: later models' manuals (D-NE300, D-NE319) list ATRAC3plus at 48/64/**256** kbps. That list belongs to those models, not to the D-NE1. And per Wikipedia's ATRAC article, the 320/352 kbps ATRAC3plus rates were only introduced with SonicStage 3.4 in February 2006 — years after the D-NE1 — with the explicit caveat that "the newer bitrates are not always compatible with all older hardware decoders."

Implications, stated carefully:

- **atracdenc's one and only output rate (352.8 kbps) is the rate *least* likely to be accepted by her specific player.** Tonight's framing treated 352.8k as "the top fill rate works today." For the D-NE1 specifically, it is outside the documented set entirely. It may still work — manuals describe the transfer rates on offer at the time, and some older hardware has accepted newer rates — but it cannot be assumed, and per Lola's standing rule only a test disc in her D-NE1 decides.
- **Her "higher bitrates" menu largely collapses for this player.** The documented ceiling for the D-NE1 is her own standard, 64 kbps. 256 kbps is plausible-but-undocumented for the NE1 (documented only for later models); everything above that is undocumented and post-dates the hardware. The app's honest rate menu for the D-NE1 is 48/64 by the book, with 256 as a test-first extra — not the 352.8k-first ladder tonight's chat implied.
- **The 64 kbps encoder workstream is promoted from "one workstream among three" to likely *the* encoder question.** If the D-NE1 rejects 352.8k streams, then without a working 64k (or 48k) encode there is no app at all for new rips, no matter how perfectly layout and encryption are reproduced. Sequencing should treat 64k encode as on the critical path, not as a later refinement of a working 352.8k pipeline.

## New finding 2: in atracdenc's source, 352.8 kbps is not a default — it is the only frame size the ATRAC3+ path can express

Tonight's chat established the behavior (flag ignored, byte-identical output). Reading the current master source this run shows *why*, and it sizes the fix:

- `src/main.cpp`, `PrepareAtrac3PEncoder`: the output frame size is hardcoded as the literal `2048` in both container paths — `CreateAt3POutput(outFile, numChannels, numFrames, 2048)` for RIFF and `2048` passed to `TOma(...)` for OMA — and `pcmFrameSz = 2048` for the encode loop. The parsed `--bitrate` value is never passed into this path at all (contrast the ATRAC3 path, which passes `bitrate * 1024` into `TAtrac3EncoderSettings`).
- `src/atrac3p.h`: `TAt3PEnc::TSettings` contains only GHA (generalized harmonic analysis) processing flags and a wideband-refine mode. There is no bitrate or frame-size member anywhere in the ATRAC3+ encoder's settings — there is nothing to wire a flag *to*.
- MultimediaWiki's ATRAC3plus technical documentation gives the fixed stereo frame size per rate: 48 kbps = 280 bytes, **64 kbps = 376 bytes**, 96 = 560, 128 = 744, 160 = 936, 192 = 1,120, 256 = 1,488, 320 = 1,864, **352 = 2,048 bytes**. So atracdenc's hardcoded 2048 is exactly the 352 kbps frame, and a 64 kbps mode means producing valid 376-byte frames.

So "build 64k support into the encoder" concretely means: parameterize the frame size through the container writers and the encoder, and retarget the encoder core's bit allocation/quantization to fill a 376-byte frame instead of a 2,048-byte one. That is bounded, real encoder work — not plumbing, and not a from-scratch encoder either, since the transform, GHA, and Huffman machinery are rate-independent in structure and ffmpeg's documented ATRAC3plus bitstream (MultimediaWiki carries a detailed, decoder-derived spec: 16 QMF subbands, 32 quantization units, canonical Huffman tables) defines what a valid 64k frame must contain. But any estimate that treated selectable rates as a small patch should be revised upward.

## What this changes about sequencing (support implication)

Tonight's stage plan had the D-NE1 acceptance test riding on an atracdenc-encoded track. Findings 1 and 2 together suggest a cleaner variable isolation for the first hardware test:

- **Test layout + encryption first, using streams that need no encoder at all.** Her SonicStage library already holds clean 64 kbps ATRAC3+ .oma files — the D-NE1's documented rate, in the exact form SonicStage burns from. Authoring a test disc from a library .oma (re-wrapped as .ATP, encrypted, laid out per the readout) tests the NDB/STI writers and the EKB/encryption reproduction with the encoder variable held at zero. If that disc plays, layout and crypto are proven and the only remaining unknown is the 64k encode. If it doesn't play, the fault is in layout/encryption, not in atracdenc.
- **Treat a 352.8k atracdenc test disc as a rate probe, not an encoder verdict.** If the D-NE1 rejects it, the rejection is ambiguous between "wrong rate for this player" and "atracdenc streams are bad" — exactly the confound the library-.oma test avoids.
- The Batch-2 DLL work (formatter + EKB in Ghidra) is unaffected and remains the next step on Muse's side once Lola sends the zip. The screenshot request (SonicStage main window; the ATRAC CD creation screen is behind the Toshiba crash, and Lola asked where `MtData.mdb` lives so she can rename it — main chat answered: standard home `C:\ProgramData\SonicStage\Packages\`, but both of her listings showed that folder empty, so a C: search comes first) is optional reference for the shell stage and not worth sinking her evening into the paused thread.

## Unknowns that remain

- Whether her D-NE1 in fact accepts 256 or 352 kbps ATRAC3plus despite the manual — only her hardware test answers this; do not pre-judge it either way in anything user-facing.
- EKB/disc-encryption reproduction: still the deepest RE unknown; the Batch-2 DLLs and the `OpenMG\ekb` reference files are the entry point.
- NDB/STI field semantics beyond the record shape; the TOC parse plus `CDRFormatter.dll` should close this.
- atracdenc's ATRAC3plus quality at any rate is thinly field-tested (community coverage focuses on ATRAC1/ATRAC3 for MiniDisc); irrelevant until a 64k mode exists and her ears judge it.
- Mac Intel build of atracdenc: unverified, expected fine (CMake + libsndfile).
- Side note belonging to the paused thread, not this goal: `MtData.mdb`'s current location on the Toshiba is unconfirmed (Packages listed empty twice). Noted, not chased.

## Already Covered in Main Chat

- Lola scoped the project herself: "All I want is a native Mac app that makes Atrac3+ CDs for my NE1" — one job, not a SonicStage clone or suite.
- Main agent corrected its own earlier claim: an open-source ATRAC3+ encoder does exist (atracdenc, LGPL), and its trial encode/decode round-trip at 352.8 kbps passed.
- Lola sent CD_stuff.zip; main agent reported the disc layout map and the discovery that .ATP audio is OpenMG-encrypted, with the .STK as the EKB key block.
- Lola set the bitrate spec: keep 64 kbps, with higher rates wanted to fill a disc under a small playlist; main agent verified atracdenc runs fixed at 352.8 kbps for ATRAC3+ (--bitrate ignored) and named 64k support as an encoder workstream.
- Lola's HIFI photo plus the TRACK.NDB parse established the full 493-track disc and the 128-byte fixed-record NDB structure.
- Lola sent sony-listing.txt and one library .oma; main agent reported the .oma is clean 64 kbps ATRAC3+ and that encryption happens at the burn step only.
- Lola sent Archive.zip (Omgjbox.exe, GenMediaKey.dll, SsBeSvc.exe, SSSsiSV.exe); main agent mapped the AVLib/OpenMG DLL locations from the second listing and gave her the Batch-2 send list.
- Lola added two requirements: GUI similar to the original SonicStage, and built-in conversion of other audio files so she never converts-then-imports.
- Main agent told Lola where MtData.mdb normally lives for the screenshot idea, while noting both listings showed Packages empty and that the crash survived a library reset before — screenshots are optional, main window alone suffices.

## Research Trajectory

### External sources viewed

- Sony D-NE1 Operating Instructions, Sony Corporation (© 2003), Internet Archive PDF, https://dn710001.ca.archive.org/0/items/manualsonline-id-3953a8f1-91d9-407b-877a-399b8dd3fbde/3953a8f1-91d9-407b-877a-399b8dd3fbde.pdf — page 6-GB lists ATRAC3plus transfer rates as 64 and 48 kbps only for the D-NE1; also 255 groups / 999 files, ISO 9660 Level 1/2 + Joliet.
- atracdenc repository, dcherednik, GitHub, https://github.com/dcherednik/atracdenc — repo title/README confirm ATRAC3PLUS encoding to OMA/RIFF/RAW, 44.1 kHz/16-bit input only.
- atracdenc src/main.cpp (master, raw), https://raw.githubusercontent.com/dcherednik/atracdenc/master/src/main.cpp — PrepareAtrac3PEncoder hardcodes frame size 2048 in both container paths; --bitrate parsed but never passed to the ATRAC3+ path.
- atracdenc src/atrac3p.h (master), https://github.com/dcherednik/atracdenc/blob/master/src/atrac3p.h — TAt3PEnc::TSettings holds only GHA flags; no bitrate/frame-size member exists.
- ATRAC3plus, MultimediaWiki, https://wiki.multimedia.cx/index.php?title=ATRAC3plus&diff=12782&oldid=prev — fixed frame-size table (64 kbps = 376 B stereo; 352 kbps = 2,048 B) and the decoder-derived bitstream spec.
- ATRAC, Wikipedia, https://en.wikipedia.org/wiki/ATRAC — 320/352 kbps ATRAC3plus rates introduced with SonicStage 3.4 (Feb 2006); newer bitrates not always compatible with older hardware decoders.
- Sony D-NE300 manual excerpts via manualsbase/manualmachine search results — later models list ATRAC3plus at 48/64/256 kbps, confirming the rate list is model-specific and the NE1 list must not be borrowed from them.

### Prior trajectories reviewed

- None — this goal has no prior agent notes; this is its first study pass. The goal's own stage-0 files served as the prior record instead: `files/stage0-disc-readout.md`, `files/stage0-encoder-brief.md`, `files/stage0-readout-3-oma-and-listing.md`, `files/stage0-readout-4-avlib-openmg-map.md`, and `GOAL.md` (all read in full this run).

### Scaffolds and support tactics

- None applied. This is an outcome/project goal (category: interests), not a learning goal; the study task plan's teach-mode scaffolding (retrieval prompt, worked example, practice task, rubric, transfer, confidence check) was treated as scheduler metadata per instructions and not preserved. No mastery estimate made.

### Connected user data

- Goal record `goal_e35963ec4aae` via user_goal.get: full timeline of 11 updates from creation 2026-10-22T03:12:56Z through the conversion-feature addition 2026-10-22T05:11:54Z, plus the four stage-0 file associations. Briefings list is empty — no prior brief for this goal.
- Repetition search (required): keyword variants "bitrate", "64 kbps", "352", "D-NE1 manual", "frame size", "48 kbps", "atracdenc" grepped over `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/` and `.../briefs/`, including the directory listings as a filename index — both directories are empty, zero hits. Today's topics (the D-NE1 manual rate list; atracdenc's hardcoded 2048-byte frame) appear in neither prior notes/briefs nor, per the conversation review below, in main chat.

### Image references checked

- None opened this run. Lola's HIFI-folder photo and Toshiba screenshots were already analyzed in main chat and are reflected in readout #2 / the goal timeline; avatar state was not relevant to this technical goal.

### User context and memory

- MEMORY.md and the 2026-10-21 / 2026-10-22 daily logs (via muse.memory_search): project scoping, stage-0 shopping list, .OMA readout, and the fixed-352.8k atracdenc fact — all consistent with the goal record; nothing in memory states the D-NE1's documented rate list.
- Standing user rules applied: never declare playable/unplayable from documents alone (the D-NE1 test decides); the Toshiba SonicStage crash thread stays paused; RR3 Vita outranks this goal; flag costs upfront (all tools here are free/open-source).

### Searches skipped or unavailable

- No attempt to fetch Sony's official D-NE1 support-page PDF directly; the Internet Archive copy of the same Operating Instructions (3-253-604-11 (1), © 2003) was complete and legible, so a second copy would not have changed the finding.
- Ghidra analysis of the Batch-2 DLLs was not attempted — those files have not been sent yet; that is main-agent work in the live project thread, not this study.
- ffmpeg's ATRAC3plus decoder source was not read line-by-line; MultimediaWiki's decoder-derived spec was sufficient to establish that a valid 64k frame format is documented.
