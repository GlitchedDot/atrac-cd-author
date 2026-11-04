# Disc 12 — atracdenc dialect test (2026-11-03)

Recipe: disc 11's proven envelope (fresh DiscID, genuine BB d2 key,
Session-63b BlockSeed, Session-60 ICV, BB registration papers).
Single variable: the payload frames are atracdenc's encode of the
same song — byte-identical to the block that died untested in disc 2.

- Source: 3-13_Want_You_Gone.mp3 (md5 294bb9535d1d6abe3bc3e6e527da0450)
  -> ffmpeg 44.1k/16-bit WAV -> atracdenc -e atrac3plus --bitrate 64
  --container raw (wyg-atracdenc.raw, kept alongside)
- Frames: 3,091 x 376 B, md5 8ab46d77d8cf4baddc151b4739bf626f
  (deterministic encode — exactly disc 2's block)
- DiscID dd4c3c38ab88282c4367defda7b03fcd; d2 = genuine BB
  3d14fb8d372a3b5b17010dbb4fd1b3fecf4a0570; IV 02c33151a116b048
- BlockSeed 2fe99beb2d719110; ICV adc6b39eaf088c2d
- .ATP 1,163,336 B (md5 b9209ff73cda719d58272675418d342e)
- ISO: app-test-disc12.iso, 1,230,848 B, md5 1cb4dd1b5ca3ef0f566dde9d27606ac6
- ALL 7 GATES PASSED (form 3091/3091; EDE controls; round-trip;
  ISO-field match; player sim recovers genuine d2 and output parses
  3091/3091; file set; furniture/ID3 byte-identical to disc 11)

READING: audio => atracdenc's dialect is accepted by the D-NE1
decoder; the app can encode arbitrary audio end-to-end.
Silence/garble/turn-off => the known divergences (use_full_table,
slack padding, no Sony priming) become the fix list.
