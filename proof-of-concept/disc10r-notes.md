# App test disc 10R — single-variable redo of disc 10 — working notes (incremental)

- Purpose: disc 10's design, rerun with the ONE defect fixed. Disc 10
  was built from plaintext sliced as raw[0:1163344] of
  wyg-true-plaintext.raw — but that file is a 376-byte ID3/EA3 header
  FOLLOWED by the genuine ATRAC3+ frames, so disc 10 encrypted tag
  text + content-shifted frames (frame parse at offset 0: 0/3094
  clean; at offset 376: 3094/3094 clean). Disc 10's silence is
  therefore not evidence about V.
- 10R spec: EVERYTHING identical to disc 10 (same DiscID, d2′, IV,
  BlockSeed, ICV, header feeding, tags/group) EXCEPT the plaintext
  slice: raw[376 : 376+1163344] — exactly 3,094 genuine frames,
  MD5 must equal f856fb224690306bab57b9b514a732a3.
- Values (carried over from disc 10 verbatim):
  - DiscID  = 638e145a10e5f51e0a25b0539099a41d
  - d2′     = c6751b034f3bfa91ad6ce2bb166b2527735dc304
  - IV      = 02c33151a116b048
  - BlockSeed = 286ca3de7b474b0c (bind_index 0)
  - ICV     = 9d63c274855b20bd
  - mgd     = 2ad14387ddfb4b86; connum 4f7e; track_slot b4f37fbb
- Mandatory gates: (1) FORM GATE — the plaintext slice parses
  3094/3094 frames with parse_at3p BEFORE encryption; (2) EDE
  positive controls (bb, genuine A0 @159); (3) .ATP size 1,164,464 B
  + payload round-trip byte-exact; (4) ISO-alone field readback;
  (5) player simulation from the ISO alone — recovered key decrypts
  payload to the frame block byte-exactly AND the decrypted output
  parses 3094/3094; (6) file set == twin's 9 files; (7) delta vs
  disc 10: .ATP header (first 1,120 B) byte-identical, payload
  differs.

## Build result — ALL GATES PASSED (build_disc10r.py)
- Plaintext slice: raw[376:1163720], 1,163,344 B, MD5
  f856fb224690306bab57b9b514a732a3 (asserted equal to the required
  value). FORM GATE: parses 3,094/3,094 frames with parse_at3p
  BEFORE encryption.
- Gate 2: EDE controls reproduce byte-exactly (bb → b4e56ea4874a6bb6;
  genuine A0 @ index 159 → d883bf8b4359d7c6).
- Payload (DES-CBC, d2′[0:8], IV 02c33151a116b048): 1,163,344 B,
  MD5 aa1c7aa2faeed898e9007975c545a7d9.
- BlockSeed = 286ca3de7b474b0c; ICV = 9d63c274855b20bd — identical to
  disc 10's, as required.
- Built .ATP: 1,164,464 B, MD5 9b5dabbc3ce83afac24c531da20682a4.
- Gate 3 round-trip, gate 4 ISO-readback fields, gate 5 player
  simulation (unseal under V → P′ afdebf0acf47ab93 → recovered d2 =
  c6751b034f3bfa91 → payload decrypts to the frame block byte-exact
  AND the decrypted output parses 3,094/3,094 frames), gate 6 file
  set (9 files) — all OK.
- Gate 7 delta vs disc 10: .ATP header (first 1,120 B) byte-identical
  to disc 10's; payload differs. The corrected plaintext slice is the
  ONLY change from disc 10.
- ISO: app-test-disc10r.iso — 1,230,848 B, 601 sectors,
  MD5 16dfad3880e57950e6d62537059d4e94. Burn route unchanged
  (session 1 only, unfinalized, open empty session 2).
- READING OF THE BURN: audio ⇒ V is universal, d2′ is free, and the
  app is solved end-to-end for new tracks. Silence like discs 7–9 ⇒
  V is install-bound and V's provenance (the wrapper machinery)
  becomes the target.
