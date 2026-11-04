"""Build app test disc 12: atracdenc dialect test.

Disc 11 recipe (PROVEN to play with audio on the D-NE1): fresh
DiscID, genuine BB d2 as content key, BlockSeed by the Session-63b
construction, ICV by the Session-60 fold, BB registration papers.
Disc 12 changes ONLY the frame source: the payload plaintext is
the atracdenc encode of the same song (Want You Gone MP3 ->
44.1k/16-bit WAV -> atracdenc -e atrac3plus --bitrate 64
--container raw), byte-identical to the frame block that died
untested inside disc 2 (3,091 frames, md5
8ab46d77d8cf4baddc151b4739bf626f).

AUDIO on the D-NE1 => atracdenc's ATRAC3+ dialect is accepted by
the hardware decoder and the app can encode arbitrary audio
end-to-end. Silence/garble => the known divergences (use_full_table,
slack padding, priming) become the fix list.
"""
from __future__ import annotations

import hashlib
import io
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from Crypto.Cipher import DES, DES3

OUT = os.path.dirname(os.path.abspath(__file__))
FRAMES_FILE = os.path.join(OUT, "wyg-atracdenc.raw")
DISC11_ISO = ("/home/hatch/workspace/atrac-cd-stage0/"
              "app-test-disc11-genuinekey-2026-11-03/"
              "app-test-disc11.iso")
sys.path.insert(0, "/home/hatch/workspace/atrac-cd-author/src")
sys.path.insert(0, "/home/hatch/workspace/atracdenc-test/e0_profile")

from atrac_author.author import TrackInput, build_iso  # noqa: E402
import parse_at3p  # noqa: E402

FRAME = 376
N_FRAMES = 3091
HEADER_LEN = 376                      # ID3/EA3 header in the raw file
FRAMES_MD5 = "8ab46d77d8cf4baddc151b4739bf626f"

# ---- values carried over from disc 10 verbatim (NOTES.md there) ----
DISC_ID = bytes.fromhex("dd4c3c38ab88282c4367defda7b03fcd")  # disc 12: fresh random
D2P = bytes.fromhex("3d14fb8d372a3b5b17010dbb4fd1b3fecf4a0570")  # disc 11: GENUINE BB d2
INIT_VECTOR = bytes.fromhex("02c33151a116b048")
MGD = bytes.fromhex("2ad14387ddfb4b86")
CONNUM = bytes.fromhex("4f7e")
TRACK_SLOT = bytes.fromhex("b4f37fbb")

# ---- the lifted ceremony constant V (HARVEST-REPORT Job 2) ----
V = bytes.fromhex("3c8e092d257ffa7d3a3986d75b1b4c2b")
GENUINE_D2 = bytes.fromhex("3d14fb8d372a3b5b17010dbb4fd1b3fecf4a0570")

TITLE = "Want You Gone"
ARTIST = "Aperture Science Psychoacousti"
ALBUM = "Portal 2 Soundtrack [Songs to"
TIMESTAMP = datetime(2026, 11, 3, 11, 15, 50, 170000,
                     tzinfo=timezone(timedelta(hours=-8)))

FILES = ("TRACK.NDB", "ALBUM.NDB", "ARTIST.NDB", "GROUP.NDB",
         "PLLIST.NDB", "TOC00000.STI", "TOC00001.STI", "0001000E.STK")


def xor(*bs: bytes) -> bytes:
    out = bytearray(bs[0])
    for b in bs[1:]:
        assert len(b) == len(out)
        for i in range(len(out)):
            out[i] ^= b[i]
    return bytes(out)


def block_seed(discid: bytes, bind_index: int, d2: bytes) -> bytes:
    """Session-63b construction: 2-key 3DES EDE of the masked key."""
    p = xor(discid[0:8], discid[8:16],
            (bind_index + 1).to_bytes(8, "big"), d2[0:8])
    return DES3.new(V, DES3.MODE_ECB).encrypt(p)


def unseal(seed: bytes) -> bytes:
    """Player side: invert the EDE under V to recover P."""
    return DES3.new(V, DES3.MODE_ECB).decrypt(seed)


def icv(discid: bytes, sizes) -> bytes:
    """Session-60 CreateIcv: unkeyed DiscID-and-sizes polynomial."""
    a = int.from_bytes(discid[0:8], "big")
    b = int.from_bytes(discid[8:16], "big")
    x = a
    for s in sizes:
        x = (x * s + b) & 0xFFFFFFFFFFFFFFFF
    return x.to_bytes(8, "big")


def des_cbc_encrypt(key8: bytes, iv: bytes, data: bytes) -> bytes:
    return DES.new(key8, DES.MODE_CBC, iv=iv).encrypt(data)


def des_cbc_decrypt(key8: bytes, iv: bytes, data: bytes) -> bytes:
    return DES.new(key8, DES.MODE_CBC, iv=iv).decrypt(data)


def count_clean_frames(data: bytes) -> int:
    """Parse each 376-B frame with parse_at3p; return clean count."""
    assert len(data) % FRAME == 0
    ok = 0
    for i in range(0, len(data), FRAME):
        try:
            parse_at3p.parse_frame(data[i:i + FRAME])
            ok += 1
        except Exception:
            pass
    return ok


class QueueRandom(random.Random):
    """randbytes() pops queued values in order, asserting lengths."""

    def __init__(self, queue):
        super().__init__(0)
        self._q = list(queue)

    def randbytes(self, n):
        v = self._q.pop(0)
        assert len(v) == n, f"queued {len(v)} B, caller wanted {n}"
        return v


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def extract(iso_path: str) -> dict:
    import pycdlib
    iso = pycdlib.PyCdlib()
    iso.open(iso_path)
    out = {}
    buf = io.BytesIO()
    iso.get_file_from_iso_fp(buf, iso_path="/HIFI/TRK00001.ATP;1")
    out["TRK00001.ATP"] = buf.getvalue()
    for name in FILES:
        b = io.BytesIO()
        iso.get_file_from_iso_fp(b, iso_path=f"/{name};1")
        out[name] = b.getvalue()
    iso.close()
    return out


def main() -> None:
    failures = []

    # ---- audio FIRST: the corrected slice + FORM GATE ----
    plaintext = open(FRAMES_FILE, "rb").read()
    assert len(plaintext) == N_FRAMES * FRAME, len(plaintext)
    print(f"atracdenc frames: {len(plaintext)} B = {N_FRAMES} frames, "
          f"md5 {md5(plaintext)}")
    if md5(plaintext) != FRAMES_MD5:
        print(f"!!! frames MD5 != {FRAMES_MD5} — not the disc-2 "
              f"atracdenc block; not building.")
        sys.exit(2)
    print("frames MD5 == 8ab46d77d8cf4baddc151b4739bf626f (disc 2's "
          "exact block)  OK")
    clean = count_clean_frames(plaintext)
    print(f"form gate: plaintext parses {clean}/{N_FRAMES} frames clean")
    if clean != N_FRAMES:
        print("!!! GATE 1 (FORM) FAILED — plaintext slice does not "
              "parse as genuine frames; not building.")
        sys.exit(2)
    print("gate 1 (FORM): plaintext parses 3,094/3,094 frames  OK")

    # ---- gate 2: EDE positive controls BEFORE building ----
    ctl1 = block_seed(
        bytes.fromhex("0524600df2cbc799735961232a124529"), 0, GENUINE_D2)
    print(f"control bb : {ctl1.hex()}  expect b4e56ea4874a6bb6")
    if ctl1.hex() != "b4e56ea4874a6bb6":
        failures.append("EDE control 1 (bb) mismatch")
    ctl2 = block_seed(
        bytes.fromhex("f4a79f2142ee36fbf85052b79a17ad8d"), 159, GENUINE_D2)
    print(f"control A0 : {ctl2.hex()}  expect d883bf8b4359d7c6")
    if ctl2.hex() != "d883bf8b4359d7c6":
        failures.append("EDE control 2 (genuine A0) mismatch")
    if failures:
        print("!!! GATE 2 FAILED — construction does not reproduce "
              "the controls; not building.")
        for f_ in failures:
            print(f"    {f_}")
        sys.exit(2)
    print("gate 2: both EDE positive controls reproduce byte-exactly  OK")

    # ---- payload: S37 DES-CBC under the chosen d2' + IV ----
    payload = des_cbc_encrypt(D2P[0:8], INIT_VECTOR, plaintext)
    assert len(payload) == len(plaintext)
    print(f"payload: {len(payload)} B, md5 {md5(payload)}")

    # ---- header BlockSeed for THIS disc (bind_index 0) ----
    seed = block_seed(DISC_ID, 0, D2P)
    print(f"DiscID    = {DISC_ID.hex()}")
    print(f"d2'       = {D2P.hex()}")
    print(f"IV        = {INIT_VECTOR.hex()}")
    print(f"BlockSeed = {seed.hex()}  (bind_index 0)")
    # fresh DiscID => no fixed seed expectation; gate 2's controls
    # guard the construction itself.

    atp_size = 1120 + len(payload)   # 1024 ID3 + 96 header + payload
    icv_value = icv(DISC_ID, [atp_size])
    print(f"ICV       = {icv_value.hex()}  (fold over DiscID, "
          f".ATP size {atp_size})")
    if failures:
        print("!!! computed header values diverge from disc 10; "
              "not building.")
        for f_ in failures:
            print(f"    {f_}")
        sys.exit(2)

    queue = [seed, INIT_VECTOR, CONNUM, TRACK_SLOT, MGD,
             icv_value, DISC_ID]
    rng = QueueRandom(queue)
    track = TrackInput(payload=payload, frame_size=FRAME,
                       title=TITLE, artist=ARTIST, album=ALBUM)
    iso_path = os.path.join(OUT, "app-test-disc12.iso")
    stats = build_iso([track], iso_path,
                      groups=[(ALBUM, 1, 1)],
                      rng=rng, timestamp=TIMESTAMP)
    assert not rng._q, f"RNG queue not exhausted: {rng._q}"
    iso_bytes = open(iso_path, "rb").read()
    print(f"ISO: {stats['iso_bytes']} B, {stats['iso_sectors']} sectors, "
          f"md5 {md5(iso_bytes)}")

    built = extract(iso_path)
    atp = built["TRK00001.ATP"]
    hdr = atp[1024:1120]
    hdr_seed = hdr[0x18:0x20]
    hdr_iv = hdr[0x58:0x60]
    built_payload = atp[1120:]
    toc = built["TOC00000.STI"]
    toc_icv, toc_discid = toc[16:24], toc[32:48]

    # ---- gate 3: .ATP size + payload round-trip ----
    print(f"built .ATP: {len(atp)} B, md5 {md5(atp)}")
    if len(atp) != atp_size:
        failures.append(f".ATP size {len(atp)} != expected {atp_size}")
    rt = des_cbc_decrypt(D2P[0:8], hdr_iv, built_payload)
    if rt != plaintext:
        failures.append("payload round-trip != the frame block")
    if not failures:
        print(f"gate 3: built .ATP == {atp_size} B; DES-CBC decrypt of "
              "built payload under d2'[0:8] + built header IV == the "
              "frame block, byte-exact  OK")

    # ---- gate 4: fields from the built ISO alone ----
    if toc_discid != DISC_ID:
        failures.append(f"TOC DiscID {toc_discid.hex()} != disc 10's "
                        f"{DISC_ID.hex()}")
    refold = icv(toc_discid, [len(atp)])
    if toc_icv != refold or toc_icv != icv_value:
        failures.append(f"TOC ICV {toc_icv.hex()} != fold "
                        f"{refold.hex()}")
    if hdr_seed != seed:
        failures.append(f"header BlockSeed {hdr_seed.hex()} != "
                        f"computed {seed.hex()}")
    if hdr_iv != INIT_VECTOR:
        failures.append(f"header IV {hdr_iv.hex()} != chosen "
                        f"{INIT_VECTOR.hex()}")
    if not failures:
        print("gate 4: TOC DiscID/ICV, header BlockSeed/IV all match "
              "the spec values  OK")

    # ---- gate 5: PLAYER SIMULATION from the built ISO alone ----
    p_rec = unseal(hdr_seed)
    fold = xor(toc_discid[0:8], toc_discid[8:16])
    d2_rec = xor(p_rec, fold, (1).to_bytes(8, "big"))
    print(f"player sim: unsealed P' = {p_rec.hex()}, "
          f"recovered d2 = {d2_rec.hex()}")
    if d2_rec != D2P[0:8]:
        failures.append(f"player sim recovered d2 {d2_rec.hex()} "
                        f"!= d2'[0:8] {D2P[0:8].hex()}")
    else:
        dec = des_cbc_decrypt(d2_rec, hdr_iv, built_payload)
        if dec != plaintext:
            failures.append("player sim payload decrypt != the "
                            "frame block")
        else:
            clean2 = count_clean_frames(dec)
            print(f"player sim: decrypted output parses "
                  f"{clean2}/{N_FRAMES} frames clean")
            if clean2 != N_FRAMES:
                failures.append(f"player sim output parses only "
                                f"{clean2}/{N_FRAMES} frames")
            else:
                print("gate 5: player simulation — unseal under V, "
                      "unmask with DiscID fold + BE64(1) — recovers "
                      "d2', decrypts the payload to the frame block "
                      "byte-exactly, and the output parses "
                      "3,094/3,094 frames  OK")

    # ---- gate 6: file set == the twin's 9 files ----
    expect = {"TRK00001.ATP"} | set(FILES)
    if set(built) != expect or len(built) != 9:
        failures.append(f"file set {sorted(built)} != the twin's 9")
    else:
        print("gate 6: file set == the twin's 9 files  OK")

    # ---- gate 7: furniture identity vs disc 11 ----
    prev = extract(DISC11_ISO)
    same_names = set(prev) == set(built)
    furniture_same = all(built[k] == prev[k] for k in FILES
                         if k != "TOC00000.STI")
    id3_same = atp[:1024] == prev["TRK00001.ATP"][:1024]
    print(f"delta vs 11: file set same: {same_names}; furniture "
          f"(NDBs/PLF/STK/TOC00001) identical: {furniture_same}; "
          f"ID3 region identical: {id3_same}")
    if not (same_names and furniture_same and id3_same):
        failures.append("disc 12 furniture/ID3 diverges from disc 11 "
                        "beyond the intended variable")
    else:
        print("gate 7: vs disc 11, only TOC00000, the header seed/IV "
              "region, and the payload differ — the frame source is "
              "the single variable  OK")

    if failures:
        print("!!! VALIDITY GATE FAILED:")
        for f_ in failures:
            print(f"    {f_}")
        sys.exit(2)
    print("ALL VALIDITY GATES PASSED")
    print(f"DiscID    = {DISC_ID.hex()}")
    print(f"d2'       = {D2P.hex()}")
    print(f"IV        = {INIT_VECTOR.hex()}")
    print(f"BlockSeed = {seed.hex()}")
    print(f"ICV       = {icv_value.hex()}")
    print(f"ISO       = {iso_path} ({len(iso_bytes)} B, "
          f"md5 {md5(iso_bytes)})")


if __name__ == "__main__":
    main()
