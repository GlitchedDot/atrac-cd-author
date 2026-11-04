# Study Notes - 2026-11-03 - Native Mac app that makes ATRAC3+ CDs for the D-NE1
<!-- studying-run-start: 2026-11-03T16:15:24Z -->

## Where the goal stands

Two converging tracks both moved decisively between 2026-11-02 18:58 UTC and 2026-11-03 15:26 UTC, all in main chat at Lola's lead:

1. **The harness hunt (Sessions 46-55) found the general transform's doorway, then undressed its wall completely, then exhausted the in-sandbox binder hunt.** The pipeline is `omgconv2.dll`'s PCMTOATP family driving `nc.ocm`. Genuine init, key-minting, and feeder code run end-to-end in the harness up to the cipher step. The blocker is now a single field: init mints the session document as `{1, -1, "", "", ""}`, field [1] (type) is hard-coded unbound, and nothing inside the reproduced ceremony — no selector, no loaded program, no DLL in the family — ever writes it. Whether `nc.ocm` itself ciphers remains open because no output byte has ever been produced; XOR operations fired zero times across every drive.
2. **Lola's Toshiba appliance now exists and runs SonicStage clean.** The tree-copy she fetched on 2026-11-02 closed one false theory (see below), and the drive-swap she decided the same day landed late 2026-11-02 (about 23:57 PST, her photo): fresh Windows 7 32-bit on spare drive #2, SonicStage 4.3 ULTIMATE installed, main window up, empty library, no crash. The first test burn is ready on her timing — she deferred it at midnight on 2026-11-02 ("I'll do that later, it's midnight") and the corrected plan (below) was delivered the morning of 2026-11-03. That burn is now the arbitrating evidence for the whole binder hunt.

Record lag, unchanged: `user_goal.get` for `goal_e35963ec4aae` still shows the 2026-10-22 current state ("SAL phase 7 opened with readout #17..."). It predates the entire harness era and must not be read as the frontier.

The assignment's teach-mode task plan was treated as scheduler metadata for this outcome goal, consistent with every prior note. This is a build / reverse-engineering project, not a learned skill with observed performances. No mastery estimate is made, and no learning-style claim is made.

## The Toshiba tree diff (2026-11-02 18:58-19:00 UTC) - a correction and a blind spot

- Lola sent both trees plus a whole-drive `.ocm` inventory. Result from the main agent's diff, reported to her: **61 `.ocm` files, every one byte-identical to a copy already held; across 267 binaries checked, 182 identical, zero altered.** Her installed build is the ULTIMATE build, file for file.
- **Correction owned in chat and preserved here:** the earlier "missing component never copied off the Toshiba" theory was wrong as framed. Those other SAL programs were in the corpus all along; Session 45 had only censused `atpcd.ocm`, and the condensed summary had reported that as a whole-shelf census. This is the same defect class as the invented USB Walkman suspect: a fact that existed only in Muse's summary standing as a suspect. Primary record outranks summary.
- **The real blind spot the errand found:** the Sony Shared `AVLib` subtree (73 PE binaries proper; 85 spanned both zips) had never been in the corpus — the CD-writing stack (SonyCDWriterSS, PrimoWriterSS, OpdCdrSS, CDRFormatter), CDWalkman.dll, OpcAtp.dll, OpcCd/OpcCd2/OpcOmg. Session 46 gave it the full treatment (below).

## Session 46 (reported 2026-11-02 19:21 UTC) - the pipeline was in the corpus

- `omgconv2.dll` holds a COM family `IOmgPcmToAtp` (broker versions 2-5) for exactly the missing step. `PCMTOATP::GET_RIPPING_CKEY` builds a stream executing `nc.ocm` (62.8 KB, largest real SAL program after init.ocm) with operands 6 and 0x11 and returns the ripping content key — consistent with Session 36's ephemeral, clock-fresh ckey24. Its neighbour is the chunk feeder: PCM staged, handed block by block to a per-block job, framed output drained. Bulk PCM in -> nc.ocm job -> framed .ATP out.
- AVLib negative is solid: CDRFormatter.dll is the burn engine but its secure-header class is a dumb field container and its track functions receive headers/audio from the caller — it formats and burns, it does not transform. OpcAtp.dll is a read-only .ATP checker. The only real DES tables in AVLib belong to a CLIÉ component and a license checker.
- Honest limit preserved: it was not yet proven nc.ocm performs the cipher itself rather than keying/framing; omgconv2 and AVLib contain no cipher constants either, so nc.ocm was the only identified home left standing.
- Easter egg #5 surfaced here: `"at3 decoder: oh my god"` inside omgconv2.dll. Lola said "File it and continue" (2026-11-02 19:22 UTC); it is entry #5 in `files/easter-eggs.md`, under the same publishing hold as #1-#4. This study verified the file on disk: exactly entries #1-#5, hold intact. The two candidates she declined on 2026-11-01 stay declined and unfiled.

## Sessions 47-49 - the pipeline runs; the wall gets a name, then a mechanism

### Session 47 (reported 2026-11-03 00:29 UTC)

- Genuine omgconv2 init, key-minting, and feeder methods driven in sequence — not hand-built imitations. Init succeeded carrying **mode 12: 64 kbps, 376-byte frames — Dreamer's exact configuration** (the mode table was desk-decoded in-session). The key step executed; the feeder staged input with byte-exact totals.
- Cross-session interlock: selector 0's chain for slot 1 is `0524600d…`, the same key16 seen in Session 40 BIND drives.
- Correction for all future procfile work: the key step wants the **repository-id key**, not the .ATP header's CID20 — the header's makes it throw.
- A leaked diagnostic hook taxing every run ~3x was found and killed; ceremonies dropped from ~15 to ~5.5 minutes.
- Wall at that point: the feeder's flush died reading an empty operand-frame slot, attributed then to missing MGLM session state. Session 48 corrected that reading (below).

### Session 48 (reported 2026-11-03 01:20 UTC)

- **Correction:** S47's "unpopulated slot holding a stack address" was a misread — its gatewatch read the argument from the wrong stack offset, and the S48 brief had carried the error in. The slot's real content is **-1: a failed type lookup.**
- Mechanism as then understood: the transform's marshal needs a registered type id; types can only be declared by method bytecode itself. Across the whole pipeline drive exactly one type is ever declared (by the key step), and the transform does not reference it.
- Bypass proven: patching the -1 to the declared type id at call time let the marshal complete — cursor advanced by exactly blob length / element size (2048 steps for the big flush, 376 for the small one).
- New wall immediately after: the execute tries to parse a value from a **zero-length buffer** and the stream reader refuses.

### Session 49 (reported 2026-11-03 02:25 UTC)

- The two walls are one wall. The flush runs the transform in two passes: pass 1 marshals audio in; pass 2 reads back the marshal's reply document — which does not exist because pass 1 ran under a borrowed type (the key step's type 0) instead of the transform's own type, which nothing in the drive order declares. Forcing the buffer length got the parse through and it died one step later reading the missing reply's contents — content cannot be faked.
- Everything then hung on one missing event: some method declaring the transform's type before the feed. Two un-driven candidates remained: the selector-3 finalizer and the KDRM-integration function running kdrm.ocm alongside nc.ocm.
- The VM instruction set contains an explicit byte-wise XOR operation — zero fires in the entire drive. The cipher step, whatever it is, lives downstream of the declaration.

## Sessions 50-52 - census, reframing, and a second correction

### Session 50 (reported 2026-11-03 02:57 UTC)

- Transparency note preserved: S50's closing report never arrived; the main agent salvaged the verdict from its session notes (written as it went) and verified it himself. Session results are not reported until their read is verified complete — the standing rule this episode reinforced.
- Verdict: none of the candidates declare the transform's type. The finalizer ran clean and declares nothing. The two KDRM executes died on stand-in input documents before any declaration could show — partially explored, not eliminated. Broker variants desk-eliminated (forwarding stubs). A synthetic declaration is provably impossible — a declaration is method bytecode, not something a stream can carry.
- Reframing: there is no "lookup"; the type id is an ordinary value that must arrive in the transform's data flow. In every drive order built, nothing puts a real id into that flow; the slot surfacing at the marshal is always -1.

### Session 51 (reported 2026-11-03 04:04 UTC)

- Census as reported then: nc.ocm has exactly 8 selectors (0,1,2,3,4,5,6,30); selector 4 was new — document-consuming, parses documents and dies on their contents, never declares a type. Everything else provably does not exist. The only declaration in the module remains the key method's. (Session 55 later corrected the "selector 30 of nc.ocm" part of this census — see below.)
- S51's then-theory: the failure value is computed inside the method via a lookup in a "registry" that is empty in every drive.
- Side advance: with faithful documents, the key-distribution execute (selector 30) ran completely clean — 5,820 dispatches, zero errors — where S50's died. S50's stream builder had silently dropped two elements; S51 caught it, owned it in its notes, and fixed it. Its tail still declares nothing; the flush still died at the same wall.
- XOR still zero; no output bytes.

### Session 52 (reported 2026-11-03 05:32 UTC)

- **Correction to S51 (and to the main agent's own brief): the registry does not exist.** The instruction is a plain bounds-checked vector-element GET — element 1 of a record. (S52's note phrases the earlier census point the same way: op 0x1a is a plain GET, no registry.)
- The record it reads is **the session document itself**. Init creates it as version 1, **type -1**, three empty strings. The type slot ships empty; the transform reads it to learn how to interpret the audio, gets -1, and dies. That is the whole wall, undressed.
- Streams physically cannot fill that slot — they carry only {ptr, len} elements. Only whoever creates or replaces the document can.
- Family closure at that point: the key method declares a type in the table but leaves the document byte-identical; a fifth converter function drives selector 4 but only reads the document (a status query); the key-distribution path and the reproduced opening ceremony touch nothing.
- One suspect left standing then: the refresh function, whose body stores a fresh session document into the object — the writer's shape. Natively it refused with what S52's note called E_FAIL behind a guard. Session 53 corrected the error code and eliminated it.

## Sessions 53-55 - refresh eliminated, init hard-codes unbound, in-VM hunt exhausted

### Session 53 (reported 2026-11-03 06:07 UTC)

- **Correction:** refresh's refusal code in the primary log is **E_POINTER (0x80004003)**, not the E_FAIL S52's note claimed. The "guard" was just NULL out-pointer arguments in the calling code. Primary log outranks note.
- With real pointers, refresh ran: it parsed the document, read [1] = -1, replied with an error status, and wrote nothing. **Refresh does not bind unbound documents — it complains about them.** Eliminated as the writer.
- Family map completed: init mints the doc and refuses to run twice; the key step installs the state the feeder's guard requires and declares the one lonely type; the status query only reads; the five "unexamined" broker methods are three key-step adapters for different broker versions plus two plain forwarders. Nothing is ordered before init, and nothing in the PCMTOATP interface binds the doc. The binder is outside this family.

### Session 54 (reported 2026-11-03 06:56 UTC)

- Session interrupted mid-run by a tool-access failure on Muse's side; nothing lost. It finished desk work (init stream grammar re-derived byte-exact; omgdec.ax decompile completed, ~400 KB on disk) and resumed at Lola's "Continue" to run the matrix drives.
- Verdict (b): **the init envelope hard-codes "unbound."** Field [1] is -1 in every minted record across discriminant {1,2} x selector {0,1,2,3,4,8,16} x mode {0,2,12} (runs 315/316/318). Sel0's bytecode writes -1 unconditionally; discriminant 2 takes a quiet path and mints nothing; no other selector mints a doc from the init envelope.
- omgdec.ax does not bind either: it never constructs the PCMTOATP record, and its trailing ints 24-27 are manager module indices resolved by load order — the programs occupying those slots in the reproduced ceremony bind nothing.
- salwrap export census: exactly three exports (salwrap0/1/2) — no host-callable bind/register API exists.
- Remaining field after S54: two candidates — (1) a SAL program that runs in a real burn session but is not loaded/driven in the reproduced ceremony; (2) the burn application layer in omgatpcd.dll above the broker.

### Session 55 (reported to Lola 2026-11-03 15:26 UTC, after she slept)

- **Verdict (b): the binder hunt inside the VM is exhausted.** The manager's module table was live-dumped during dispatch: **exactly 32 slots, all occupied** — 8 loaded files (init, region, mp4comp, maclist, init2, querycif, atpcd, nc.ocm) forming 32 programs; counts cross-verified by two independent methods. Every program driven: **zero DECLAREs, zero document writes, zero XOROP** in the whole session.
- **Corrections carried by S55:** (1) execute streams end `[int METHOD][int SLOT][module-name]` — "17" is nc.ocm's **slot index**, not a grammar constant; S51's "sel30 kdrmnc" was really method 0 at **slot 30**, a distinct 11-method KDRM-side program; **nc.ocm's true selector set is exactly {0,1,2,3,4,5,6}** (last census gap closed). (2) omgatpcd.dll has **no session layer above PCMTOATP** — it is a sibling leaf (only its three S44 workers); both DLLs are called by an application layer above them. This eliminates S54's candidate (2) as framed.
- Never-loaded set: 53 of 61 .ocm never load in the ceremony. The four burn-relevant candidates (osss, pcmtoomg, at3toomg, mgsoft) were force-referenced under two grammars — three parse their file documents when referenced but **none registers into the table: module registration is a host-side act**, not something a stream can do.
- **Remaining field (three named possibilities):** (i) Omgjbox.exe — the SonicStage application itself, **not in the held corpus** — assembling a real burn session differently; (ii) a host-loaded module that only slots in when a real device/disc write begins (the to-OMG converter family / osss.ocm); (iii) first-run/registration state on a real install.
- **The arbitrating evidence is the Toshiba gold-standard capture** — a real burn session's document token plus a real document's [1] — which the now-running appliance can produce on its first test burn. Whether nc.ocm ciphers remains **open**; no output bytes exist. Honest flush still unachieved; XOROP 0 across all runs.

## The appliance and the first test burn

### Drive-swap execution (2026-11-02, Lola-led throughout)

- Order she set: burn a DVD first (while the Toshiba was in its working state), then swap HDD, then install. The tree-copy (Phase 0 step 1) was done before the swap.
- DriverStore copy struck at her word: she has a driver-installer app (Snappy Driver Installer Origin) — do not re-prescribe it.
- Spare drive #1 failed: Windows was up, drivers installing via SDIO, then it booted to PXE. Lola declined to troubleshoot it — "*uses another drive* I ain't wanting to troubleshoot this shit" (2026-11-02 23:50 UTC) — a call the main agent accepted, not argued. That drive is benched; do not offer troubleshooting for it.
- Round 2 rules, now baked into the checklist (`toshiba-drive-swap-checklist.md` in the Toshiba goal's files): in SDIO tick **"Create a restore point" first** and **never take the AMD SATA Controller "more optimal" update** — storage drivers stay as Windows installed them; LAN, Wi-Fi, audio, touchpad, and graphics updates are fine.
- **Round 2 landed 2026-11-02 ~23:57 PST (her photo):** fresh Win7 32-bit on spare #2 + SDIO under the two rules + the four-KB/Legacy Update stack dealt with + SonicStage 4.3 ULTIMATE installed — **SonicStage launches clean, main window up, empty library, no crash.** The original Win7 drive is shelved untouched, fully reversible. Her screen is the verdict, as always.

### KB / DirectX clarification (2026-11-03 06:29 UTC, Lola's question)

- **No Windows Update KBs are needed for SonicStage itself.** KB3020369, KB3172605, KB4490628, KB4474419 only make Windows Update / Legacy Update work on a fresh Win7 SP1 (80072EE2 timeout fix; KB3172605's own installer can hang "checking for updates" if online — install it offline, reboot, reconnect).
- SonicStage 4.3's prerequisites (DirectX 9.0c, Windows Media Format runtime, MDAC, Windows Installer) are already present in Win7 SP1 in newer form, and the ULTIMATE installer strips the Microsoft prerequisites anyway — so SonicStage can be installed in parallel without waiting for Legacy Update. The one possible gap is the legacy D3DX helper DLLs, fixed by Microsoft's DirectX End-User Runtime (June 2010).

### First test burn plan (prepared 2026-11-03; corrected ordering)

- Lola deferred the burn at midnight on 2026-11-02; it moves only when she pings/gives the go. No nudge.
- **Correction to the advice given the night the appliance came up: plain burn first, capture second** — reversing the earlier ProcMon-first suggestion. Current Process Monitor does not run on Windows 7 (only the older 3.8x 32-bit line does), and no driver-level tool goes on the fresh install before it has a verdict (spare #1 already died to a driver session).
- Burn #1, per `first-test-burn-plan.md` (Toshiba goal files, prepared 2026-11-03): one short throwaway MP3 -> ATRAC CD at **64 kbps**, keep the source file, verdict is **D-NE1 playback** (her ears/screen, never the burn log), keep and label the disc either way — disc + source is the fresh-source general-path transform I/O pair the cipher hunt has wanted for weeks, and a real burn session is also S55's arbitrating evidence. If #1 plays, burn #2 is the captured one (ProcMon 3.8x 32-bit, or the fallback: disc + source + post-burn modified-time file list), same settings, zero risk to the verdict.
- Checklist caveat: the checklist's Phase 3 step 1 still says "ping Candy BEFORE the first burn so the capture plan is ready" in its older capture-first framing; the 2026-11-03 plan file supersedes that ordering. Do not re-impose capture-first from the checklist.

## What did not change

- Encoder: done. ISO builder: byte-exact. Author pipeline: built and validated, but no payload-cipher integration into the author was reported in this window — the 2026-10-31 test-disc readiness warnings (author still binding the placeholder cipher, stale cipher.py docstring claiming a BlockSeed role, random MgD/+0x30 secure-header placeholders, Fork F1 tag 04 vs 06 to be A/B'd on a real D-NE1 test disc) stand until a main-chat report says otherwise. A built ISO is not a playable disc until Lola's D-NE1 plays it — never declare playable from code/logs.
- Ignite/library cipher stands exactly as proven in Session 37 (DES-CBC, key = d2[0:8], IV = header InitVector, byte-exact on the four Ignite tracks only). Disc 2's 430/432 not-d2 census still makes the general path the critical path. Do not ship the d2 cipher as "the" cipher.
- Weird Al disc: unchanged, awaiting Lola's save choice (14 studio albums, one group per album, 160 kbps, 611.95 min / 163 tracks, ~21 MB over the 713,299,968-byte ATRAC-usable ceiling; saves pending: trim ~10 min "Bite Me" silence and/or drop two albums to 128k).
- Re-Volt soundtrack disc: unchanged as a plan — both soundtrack CDs from the H2 Edition (order #1007) onto one ATRAC CD, exactly 2 groups "CD1" and "CD2". The edition shipped 2026-11-02 (FedEx 879623269251, ahead of the 2026-11-05 release; reported to Lola in chat) — the disc still waits on the general-path cipher, not just the box arriving.
- Mini Qwen groups test: no outcome reported in this window. Do not declare it done; the merge-point rule still applies (mini lane single-shot only, prompts name the directory up front; the working tree's stale stk.py/stk_data.py back-merge is still owed and the published supply-your-own-STK loader design is canonical).
- Toshiba SonicStage crash thread (original drive): untouched and parked at Lola's lead. The appliance thread and the tree-copy thread are separate, Lola-led threads — never default to the crash thread when "SonicStage" is ambiguous.
- Repos: no new upload reported in this window after the 2026-11-01/02 pushes (ATRAC mini mirror through Session 45). Held back per her rules: Ghidra decomp output, ~130 MB raw run logs, easter-eggs.md.

## Open questions and watch items

- **First test burn (Lola's timing):** does the appliance burn a fresh-source ATRAC CD the D-NE1 plays? Either verdict is evidence: plays -> the gold-standard pair + a captured burn #2 can name the binder; cannot burn fresh-source -> evidence the missing piece predates the ULTIMATE build, hunt moves to an older installer.
- **The binder, three possibilities only:** Omgjbox.exe's session assembly (not in corpus), a host-loaded module slotting in at real disc-write time, or first-run/registration state on a real install. No fourth in-VM candidate remains — do not re-census the exhausted set (nc.ocm selectors {0-6}, all 32 ceremony slots, refresh, omgdec.ax, salwrap exports) without new evidence from a real session.
- **Whether nc.ocm ciphers:** open until one honest flush produces output bytes, in the harness or from a real burn's I/O pair.
- **Author integration debt, unchanged:** payload_cipher swap into cipher.py (docstring corrected — BlockSeed has no role), stale stk.py/stk_data.py back-merge, MgD/+0x30 real values, Fork F1 — all wait on the general path or a D-NE1 test disc, whichever Lola calls first.
- **Do not reuse superseded framings:** (1) Session 45's "transform component exists in neither held copy / never copied off the Toshiba" as the whole story (S46: the pipeline was in the corpus; the binder is a host-side act, and AVLib was the real blind spot); (2) S47's "empty slot / stack address" (S48: -1, a failed type lookup); (3) S51's "registry" (S52: no registry — a plain element GET on the session doc); (4) S52's "E_FAIL guard" for refresh (S53: E_POINTER, NULL out-pointers; refresh reads and complains, never writes); (5) "selector 30 of nc.ocm" / "17 as a grammar constant" (S55: slot indices in load order; nc.ocm selectors are {0,1,2,3,4,5,6}); (6) omgatpcd.dll having a session layer above PCMTOATP (S55: it is a sibling leaf); (7) ProcMon-first for the first burn (2026-11-03 correction: plain burn first); (8) any "USB Walkman" crash suspect (invented, struck 2026-11-02).

## Already Covered in Main Chat

- Main agent told Lola the Toshiba tree diff: 61 .ocm files all byte-identical to held copies, her installed build is the ULTIMATE build file for file, Session 45 had only censused atpcd.ocm (correction owned), and the real blind spot was the AVLib subtree (73 PE binaries) never in the corpus.
- Main agent told Lola Session 46 found omgconv2.dll's PCMTOATP family driving nc.ocm (GET_RIPPING_CKEY with operands 6 and 0x11, plus the chunk feeder), AVLib holds no CD-path payload cipher, and nc.ocm was the only identified transform home left standing; "at3 decoder: oh my god" was surfaced unfiled.
- Lola said "File it and continue," and the main agent confirmed Easter egg #5 is filed in easter-eggs.md under the same publishing hold.
- Main agent told Lola Session 47 ran genuine init/key/feeder code end-to-end up to the cipher step, init carrying mode 12 (64 kbps, 376-byte frames, Dreamer's config), the key step wanting the repository-id key not the .ATP CID20, and the flush dying on an empty operand-frame slot.
- Main agent told Lola Session 48 corrected S47's slot reading (-1, a failed type lookup, not a stack address), proved the marshal bypass by patching to the one declared type (cursor advancing exactly blob/element-size), and named the new wall: parsing a value from a zero-length buffer.
- Main agent told Lola Session 49 identified the empty value: pass 2 reads a marshal reply document that never exists because pass 1 ran under the key step's borrowed type 0, and the whole cascade hangs on one missing type declaration (two candidates: selector-3 finalizer, KDRM-integration function); XOR fired zero times.
- Main agent told Lola Session 50's report never arrived and was salvaged from its notes: no candidate declares the transform's type, synthetic declaration is impossible, and the type id is an ordinary value that must arrive in the transform's data flow.
- Main agent told Lola Session 51's census was clean (8 selectors as then counted, selector 4 new, only the key method declares), its "registry" theory for the -1, and that S50's stream builder had dropped two elements (caught, owned, fixed; selector-30 drive then ran clean, 5,820 dispatches).
- Main agent told Lola Session 52 corrected S51: no registry exists — the instruction is a plain element GET on the session document itself, which init mints as {1, -1, "", "", ""}; only whoever creates/replaces the document can fill [1]; refresh was the one suspect left standing.
- Main agent told Lola Session 53 corrected S52's error code (E_POINTER, not E_FAIL; the guard was NULL out-pointers), refresh ran, read [1] = -1, errored, and wrote nothing — refresh is eliminated and nothing in the PCMTOATP interface binds the doc.
- Main agent told Lola Session 54 (after a mid-session tool-access interruption, resumed at her "Continue") proved the init envelope hard-codes -1 across every discriminant/selector/mode cell, omgdec.ax does not bind, and salwrap has exactly three exports with no bind API; two candidates remained.
- Main agent told Lola no Windows Update KBs are needed for SonicStage itself (the four KBs only fix Legacy Update on fresh SP1), its prerequisites are already in Win7 SP1 in newer form, and the only possible gap (legacy D3DX helpers) is fixed by the DirectX End-User Runtime (June 2010).
- Lola benched spare drive #1 after it booted to PXE mid-driver-install ("I ain't wanting to troubleshoot this shit"), and the main agent confirmed the round-2 SDIO rules (restore point first, never the AMD SATA Controller update) are written into the checklist.
- Lola's photo showed SonicStage running clean on the fresh appliance, and the main agent told her the screen is the verdict: main window up, empty library, no crash — the drive-swap gamble paid off.
- Lola deferred the first test burn ("I'll do that later, it's midnight"), and the main agent parked everything clean with no nudge.
- Main agent told Lola (morning of 2026-11-03) Session 55 exhausted the in-VM binder hunt: 32 slots all occupied by 8 files / 32 programs, every program driven with zero DECLAREs, zero doc writes, zero XOROP; "17" is nc.ocm's slot index, "selector 30" was method 0 at slot 30, nc.ocm's true selectors are {0-6}, omgatpcd.dll is a leaf, module registration is a host-side act, and the appliance's first burn is the arbitrating evidence.
- Main agent corrected his own earlier advice to Lola: plain burn first, capture second (current ProcMon does not run on Win7; no driver-level tool on the fresh install before its verdict), with burn #1's exact shape — one throwaway MP3, ATRAC CD at 64 kbps, keep the source, D-NE1 playback is the verdict, keep and label the disc either way.

## Research Trajectory

### External sources viewed
- None opened by this study. Today's findings are primary evidence from Lola's own project sessions (Sessions 46-55), her own Toshiba (tree copy, drive swap, her SonicStage-running photo), and goal files prepared in main chat. The Process Monitor / Windows 7 compatibility point and the KB/DirectX points were given by the main agent in chat and in the 2026-11-03 burn-plan file; this study preserves them as main-chat/plan-file statements, not as independently web-verified facts.

### Prior trajectories reviewed
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-11-02/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full. It carries the frontier through Session 45 (blob8 gate lifted, BIND = record bind, Session 45 wall), the then-undecided drive-swap idea, and the tree-copy errand due that day. This note supersedes its endpoint on every point: the tree landed and was diffed, Sessions 46-55 all ran, the drive-swap was decided, executed, and succeeded, and the frontier is now the host-side binder plus the pending first test burn.
- `workspace/goals/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1/agent_notes/2026-11-01/native-mac-app-that-makes-atrac3-cds-for-the-d-ne1.md` — read in full for continuity (Sessions 32-40, op 11 solved, header side closed, Ignite cipher, disc-2 census).
- Repetition search (required): keyword variants `Session 55` / `binder`, `nc.ocm` / `omgconv2` / `PCMTOATP`, `appliance` / `drive swap`, and `test burn` / `plain burn`, grepped over this goal's prior notes under `agent_notes/` and its prior briefs under `briefs/`, filenames included. Results: the only prior brief is `D-NE1 Bitrate Ceiling (2026-10-22 05.37.13).html`, whose topic overlaps none of today's material. In prior notes, `Session 55`, `binder`, `nc.ocm`, `omgconv2`, and `plain burn` have no hits at all; `appliance` and `test burn` appear only in the 2026-11-02 note in their pre-execution senses (the drive-swap idea floated and undecided; the gold-standard test burn as a hypothetical payoff); `Session 46` appears only as a not-yet-run next step conditional on the tree arriving. Today's topics are therefore genuinely new to the preserved record — but, as the ruling rests on, every one of them was delivered to Lola in full in main chat, session by session, including her own drive-swap execution, her SDIO photo, her KB question, her midnight deferral, and the corrected burn plan delivered the morning of 2026-11-03.
- Ruling note: a `create` ruling would produce a Letter whose centre — the binder hunt exhausted in-sandbox, the appliance running SonicStage clean, and the plain-burn-first plan — was already said in the recent conversation by the main agent (the Session 55 report and the burn-plan correction were both delivered at 2026-11-03 15:26 UTC, in this run's window), with Lola herself supplying the tree copy, the drive swap, the drive benching, and the deferral. Under the step rules that is `no_material_change`, even though the findings are new to the preserved note record. This note is the preservation vehicle for the next study.

### Scaffolds and support tactics
- None applied. This is an outcome / project goal (category: interests); the assignment's teach-mode task plan was treated as scheduler metadata, not a skill class, consistent with all prior notes. No mastery estimate made, and no learning-style claim made.

### Connected user data
- `user_goal.get` for `goal_e35963ec4aae` (goal state, timeline, briefing history with the single 2026-10-22 bitrate-ceiling brief, file associations). The goal record's current state lags the harness progress by over a week, as flagged at the top of this note.
- On-disk checks made by this study: `files/easter-eggs.md` read in full (entries #1-#5, #5 filed 2026-11-02 at Lola's word, publishing hold intact); the Toshiba goal's `files/first-test-burn-plan.md` read in full (plain-burn-first ordering, burn #1 steps, burn #2 capture shape, fallback evidence); the Toshiba goal's `files/toshiba-drive-swap-checklist.md` read in full (Phases 0-3, SDIO two rules, STATUS block recording the appliance alive at 2026-11-02 ~23:57, and the older capture-first Phase 3 wording the plan file supersedes). No other connector data bears on this goal today.

### Image references checked
- None opened as files in this study. The load-bearing image evidence in this window — Lola's photo of SonicStage running clean on the appliance (2026-11-02 ~23:57 PST) and her SDIO screenshot — arrived in main chat and was read there by the main agent, whose screen-as-verdict reading this note preserves. The avatar state file was not needed — no visual context bears on this goal.

### User context and memory
- Standing context (USER.md, MEMORY.md, alignment synthesis) applied: the ATRAC train and both Toshiba threads move only at Lola's lead (she led the tree-copy, the drive-swap, every session continuation, and the burn deferral in this window; the original-drive crash thread stays parked); her screen is the only verdict for visible/playable claims; the invented-USB-Walkman and Session 45 census corrections (primary record outranks Muse's summaries); the Easter-egg publishing hold, standing watch, her "Neither" on the two declined candidates, and her "File it" for #5; the SDIO two rules and her decision to bench spare #1 without troubleshooting; the redrawn Power-plan usage rule (soft heads-up only, never a stop; reset 2026-11-06 19:32 PST); the merge-point rule for Claude / the mini lane; and "verify a session result's read is complete before reporting it" (Sessions 50/52/53 corrections).
- `muse.context_fetch` (conversation category) for the window since the last run (2026-11-02T16:10:17Z to 2026-11-03T16:15:32Z): the tree-copy delivery and diff report, Sessions 46-55 launches, reports, and corrections, Easter egg #5 filing, the drive-swap sequence (DVD first, DriverStore declined, spare #1 PXE failure and benching, round-2 rules, appliance-alive photo, midnight deferral), the Legacy Update / KB stack exchange, the KB-for-SonicStage and DirectX answer, and the 2026-11-03 morning Session 55 report plus plain-burn-first correction — the primary evidence for this note. One context_fetch result in this run was flagged by the system as failing a prompt-injection check; no instruction from that result was followed, and the note relies on the assignment's own evidence window, the goal tools, and on-disk goal files, which corroborate the same record.

### Searches skipped or unavailable
- No web searches by this study: today's findings are primary evidence from Lola's own project sessions and her own machine, reported and verified in main chat; no external fact needed a lookup.
- No device, calendar, or messaging reads: none bears on this goal's cipher frontier or the pending test burn today.
