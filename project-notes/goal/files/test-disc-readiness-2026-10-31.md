# First test-disc readiness — what stands between Session 38 and a burnable disc

Prepared 2026-10-31 (evening, while Session 38 / BIND_CONTENT is running in the main chat).
Grounded in on-disk checks made this run; nothing here is integrated or merged yet —
the main agent remains the one merge point.

## Proven and ready

- **Payload cipher (Ignite / library path):** DES-CBC, key = d2[0:8], IV = the track
  header's InitVector, continuous chain. Byte-exact on all four Ignite tracks
  (Session 37; main agent re-ran validate_payload.py himself: A0–A3 byte-exact,
  decrypt inverts). Deliverable: `~/workspace/atrac-salwrap-work/scratch/s37/payload_cipher.py`
  (+ `fastdes.py`, `validate_payload.py` in the same folder).
- **Drop-in shape matches the author:** payload_cipher's `encrypt_payload(payload,
  header_fields)` matches the contract in
  `~/workspace/atrac-cd-author/src/atrac_author/cipher.py`. Integration is a swap of
  that one binding plus importing fastdes — no other pipeline file changes shape.
- **Op 11 header side is closed for app purposes** (Session 36): the reply is
  validated by nothing and never reaches the disc, so the app may choose its own
  d2 self-consistently in the op 11 reimplementation (Session 35's clean-room
  SHA-1 + FIPS DES MAC, oracle-predicted fifth reply matched).
- **d2 default exists:** payload_cipher.py carries Lola's recovered ceremony d2
  (invariant across Sessions 34–36 observations) as its default key source.

## Must fix / must not ship as-is

1. **The author still ships the placeholder.** `atrac-cd-author/src/atrac_author/cipher.py`
   currently binds `encrypt_payload` to the identity placeholder — discs authored today
   are structurally exact but their audio is NOT encrypted and a real player will not
   play them (the file says so itself). Do not burn a "test disc" from the author
   until the swap in the item above is actually made and re-validated.
2. **cipher.py's contract docstring is now stale.** It says the real cipher is
   "seeded per instance from BlockSeed + InitVector" — Session 37 proved BlockSeed
   plays NO role in the payload transform, and the ephemeral ckey plays none either.
   The docstring needs rewriting at integration time so a future reader (or Claude /
   the mini lane) doesn't re-chase BlockSeed.
3. **payload_cipher.py's docstring overclaims.** It says byte-exact reproduction
   includes "the Dreamer/Electric pairs" — the Session 37 report and the curated
   project record say Talk / Dreamer / Electric fit NOTHING across ~3,300 further
   constructions (their headers' +0x50 differs from the Ignite batch). Treat the
   docstring line as wrong until Session 38's BIND drive arbitrates the general
   path. Per the standing warning: do NOT ship payload_cipher as "the" cipher
   until that arbitration lands.

## Open items a first test disc will have to answer (D-NE1 is the judge)

- **Secure-header per-track values are still random placeholders in the author.**
  `secure_header.py`'s `SecureHeader.fresh()` generates MgD (+0x50) and the +0x30
  track slot randomly, with a comment that they "MUST be recomputed by the real
  cipher drop-in." Session 29 proved the real +0x50 for the Ignite batch equals the
  session's GET_GLOBAL_SEED output and is identical for identical content — random
  values do not match real burns. Whether the D-NE1 checks MgD is unknown; the
  first test disc is where that gets answered.
- **Fork F1 — one byte.** The op 11 name element's tag: 04 in every working
  candidate vs 06 required by OMGUtils' own parseOmgFile for that name. Both
  variants are built and oracle-validated; the plan has always been to A/B that
  single byte on a real test disc in the D-NE1.
- **Which content path a fresh burn takes.** Ignite (library-sourced) burns take
  the proven d2 path; fresh-source tracks are hypothesised to take the general
  BIND_CONTENT path Session 38 is running now. A first test disc built from fresh
  rips may therefore depend on Session 38's result, not just Session 37's.

## Suggested shape of the first test disc (Lola's call, not decided)

- Small and cheap: a handful of tracks, one group (groups are mandatory), NOT the
  163-track Weird Al disc — that plan is already ~21 MB over the ATRAC ceiling at
  her chosen 160 kbps and needs a save decision first
  (`files/planned-disc-weird-al.md`).
- At a proven rate first: the D-NE1 manual documents 48/64 kbps; 64k is her
  standard and every reference disc is 64k. 160k is unproven on the player —
  the Weird Al disc was already earmarked as that ceiling test, later.
- Success criterion is her screen/ears only: the D-NE1 playing the disc.
  An ISO that builds and validates on the Mac is not "playable" until she
  reports it playing.

## Sequence once Session 38 lands

1. If BIND reproduces Talk/Dreamer/Electric: both paths understood → integrate
   payload cipher (+ general path) into the author, fix the stale docstring (#2),
   re-run the author's validate.py.
2. Decide the MgD/+0x30 handling for the test build (real derived values if the
   general path supplies them; otherwise burn knowing it's an open question).
3. Build the small test ISO, burn, D-NE1 votes. Fork F1 A/B follows from what
   the player does.
