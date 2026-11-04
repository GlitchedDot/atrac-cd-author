"""Build app test disc 7: THE DECISIVE FURNITURE TEST.

The PLAYED twin (app-test-disc-2026-11-03) rebuilt EXACTLY — same
payload (the appliance track's genuine library ciphertext, fed through
the unmodified author's identity cipher), same RNG-queue header values
(SecureHeader.fresh / Toc.build call order: block_seed, init_vector,
connum, track_slot, mgd, disc_id_a, disc_id_b), same tags, same
one-group layout, same build timestamp — changing ONLY the TOC
(DiscID, ICV) pair:

  * DiscID (TOC @32-47, the id_b slot) = FRESH random 16 bytes,
    app-chosen.
  * ICV (TOC @16-23, the id_a slot) = computed with the Session-60
    algorithm over (that DiscID, the twin track's .ATP size):

        A = BE64(DiscID[0:8]); B = BE64(DiscID[8:16]); X = A
        for each .ATP size s: X = (X*s + B) mod 2^64
        ICV = BE64(X)

    (WALKMAN-REPORT.md Job 2: CPmCdWalkman::CreateIcv, verified
    byte-exact on all three genuine discs.)

VALIDITY GATES (any failure aborts with a report instead of shipping):
  1. Built .ATP byte-identical to the twin's .ATP (and 1,164,464 B —
     the size the ICV was folded over).
  2. File set vs the TWIN ISO: everything byte-identical EXCEPT
     TOC00000.STI, differing ONLY at @16-23 (== computed ICV) and
     @32-47 (== fresh DiscID); whole-image diff vs the twin ISO ==
     exactly 24 bytes.
  3. Independent re-check: from the BUILT ISO's own TOC00000.STI and
     .ATP, fold(DiscID_from_TOC, [ATP_size]) == ICV_from_TOC.
"""
from __future__ import annotations

import hashlib
import io
import os
import random
import sys
from datetime import datetime, timedelta, timezone

OUT = os.path.dirname(os.path.abspath(__file__))
GENUINE_ATP = ("/home/hatch/workspace/atrac-cd-stage0/"
               "appliance-test-burn-2026-11-03/TRK00001.ATP")
TWIN_ISO = ("/home/hatch/workspace/atrac-cd-stage0/"
            "app-test-disc-2026-11-03/app-test-disc.iso")
sys.path.insert(0, "/home/hatch/workspace/atrac-cd-author/src")

from atrac_author.author import TrackInput, build_iso  # noqa: E402

FRAME = 376

# The twin's genuine header values (twin NOTES.md are the authority).
BLOCK_SEED = bytes.fromhex("a2e39b5e80b925a4")
INIT_VECTOR = bytes.fromhex("5f231f406a2892ee")
CONNUM = bytes.fromhex("30fb")
TRACK_SLOT = bytes.fromhex("290e7f21")
MGD = bytes.fromhex("757b5fdd1d1129f7")


def icv(discid: bytes, sizes) -> bytes:
    """Session-60 CreateIcv: unkeyed DiscID-and-sizes polynomial."""
    assert len(discid) == 16
    a = int.from_bytes(discid[0:8], "big")
    b = int.from_bytes(discid[8:16], "big")
    x = a
    for s in sizes:
        x = (x * s + b) & 0xFFFFFFFFFFFFFFFF
    return x.to_bytes(8, "big")


# THE CHANGE: a fresh app-chosen DiscID, and the ICV folded over it.
DISC_ID = os.urandom(16)

TITLE = "Want You Gone"
ARTIST = "Aperture Science Psychoacousti"
ALBUM = "Portal 2 Soundtrack [Songs to"

# Same build timestamp as the twin's final build (twin NOTES.md).
TIMESTAMP = datetime(2026, 11, 3, 11, 15, 50, 170000,
                     tzinfo=timezone(timedelta(hours=-8)))

FILES = ("TRACK.NDB", "ALBUM.NDB", "ARTIST.NDB", "GROUP.NDB",
         "PLLIST.NDB", "TOC00000.STI", "TOC00001.STI", "0001000E.STK")


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


def diff_offsets(a: bytes, b: bytes) -> list:
    return [i for i in range(min(len(a), len(b))) if a[i] != b[i]]


def main() -> None:
    genuine = open(GENUINE_ATP, "rb").read()
    assert len(genuine) == 1_164_464, len(genuine)
    payload = genuine[1120:]
    assert len(payload) == 1_163_344 and len(payload) % FRAME == 0
    print(f"genuine appliance .ATP: {len(genuine)} B, md5 {md5(genuine)}")
    print(f"payload: {len(payload)} B = {len(payload)//FRAME} frames, "
          f"md5 {md5(payload)}")

    # Algorithm self-check against the genuine appliance pair before
    # trusting it for the fresh DiscID.
    chk = icv(bytes.fromhex("fb23c921c0fce07e3f254e270dabe815"),
              [len(genuine)])
    assert chk.hex() == "a8fb3de83fc4b6b5", chk.hex()
    print("ICV algorithm self-check on the genuine appliance disc: "
          "a8fb3de83fc4b6b5  OK")

    # The author's identity path is verbatim, so the built .ATP size
    # is the genuine size; the ICV is folded over exactly that size,
    # and gate 1 asserts the built .ATP really is that size.
    atp_size = len(genuine)
    icv_value = icv(DISC_ID, [atp_size])
    print(f"FRESH DiscID (id_b @32-47) = {DISC_ID.hex()}")
    print(f"computed ICV (id_a @16-23) = {icv_value.hex()}  "
          f"(fold over DiscID, ATP size {atp_size})")

    queue = [BLOCK_SEED, INIT_VECTOR, CONNUM, TRACK_SLOT, MGD,
             icv_value, DISC_ID]
    rng = QueueRandom(queue)
    track = TrackInput(payload=payload, frame_size=FRAME,
                       title=TITLE, artist=ARTIST, album=ALBUM)
    iso_path = os.path.join(OUT, "app-test-disc7-icv.iso")
    stats = build_iso([track], iso_path,
                      groups=[(ALBUM, 1, 1)],
                      rng=rng, timestamp=TIMESTAMP)
    assert not rng._q, f"RNG queue not exhausted: {rng._q}"
    iso_bytes = open(iso_path, "rb").read()
    print(f"ISO: {stats['iso_bytes']} B, {stats['iso_sectors']} sectors, "
          f"md5 {md5(iso_bytes)}")

    # ---- validity gates vs the twin ISO ----
    built = extract(iso_path)
    twin = extract(TWIN_ISO)
    failures = []

    # Gate 1: .ATP byte-identical to the twin's, and the folded size.
    atp_b, atp_t = built["TRK00001.ATP"], twin["TRK00001.ATP"]
    print(f"built .ATP: {len(atp_b)} B, md5 {md5(atp_b)}")
    print(f"twin  .ATP: {len(atp_t)} B, md5 {md5(atp_t)}")
    if len(atp_b) != atp_size:
        failures.append(f".ATP size {len(atp_b)} != {atp_size} "
                        f"(the size the ICV was folded over)")
    if atp_b != atp_t:
        d = diff_offsets(atp_b, atp_t)
        failures.append(f".ATP differs from twin at {len(d)} bytes, "
                        f"first {d[:16]}")
    else:
        print("gate 1: built .ATP byte-identical to the twin's  OK")

    # Gate 2 (file set): only TOC00000.STI, only the 24 pair bytes.
    for name in FILES:
        b, t = built[name], twin[name]
        if len(b) != len(t):
            failures.append(f"{name}: length {len(b)} vs twin {len(t)}")
            continue
        d = diff_offsets(b, t)
        if name == "TOC00000.STI":
            allowed = set(range(16, 24)) | set(range(32, 48))
            if set(d) != allowed or len(d) != 24:
                failures.append(
                    f"TOC00000.STI: differing offsets {d} "
                    f"(expected exactly 16-23 and 32-47, 24 bytes)")
            elif b[16:24] != icv_value or b[32:48] != DISC_ID:
                failures.append("TOC00000.STI: pair slots do not "
                                "contain the computed ICV / fresh DiscID")
            else:
                print("gate 2a: TOC00000.STI differs from twin at "
                      "EXACTLY @16-23 (== computed ICV) and @32-47 "
                      "(== fresh DiscID)  OK")
        elif d:
            failures.append(f"{name}: differs from twin at {len(d)} "
                            f"bytes, first {d[:16]}")
        else:
            print(f"{name}: identical to twin")

    # Gate 2 (image): whole-image diff vs the twin ISO == 24 bytes.
    twin_iso_bytes = open(TWIN_ISO, "rb").read()
    print(f"twin ISO: {len(twin_iso_bytes)} B, md5 {md5(twin_iso_bytes)}")
    if len(iso_bytes) != len(twin_iso_bytes):
        failures.append(f"ISO size {len(iso_bytes)} != twin "
                        f"{len(twin_iso_bytes)}")
    else:
        d = diff_offsets(iso_bytes, twin_iso_bytes)
        sectors = sorted({i // 2048 for i in d})
        print(f"ISO image diff vs twin: {len(d)} bytes in sectors "
              f"{sectors}")
        if len(d) != 24:
            failures.append(f"ISO image diff vs twin is {len(d)} "
                            f"bytes, expected exactly 24")
        else:
            print("gate 2b: whole-image diff vs twin == exactly 24 "
                  "bytes  OK")

    # Gate 3: independent re-check from the built ISO's own bytes.
    toc_b = built["TOC00000.STI"]
    discid_from_toc = toc_b[32:48]
    icv_from_toc = toc_b[16:24]
    refold = icv(discid_from_toc, [len(built["TRK00001.ATP"])])
    if discid_from_toc != DISC_ID:
        failures.append("gate 3: DiscID read back from built TOC "
                        "!= the chosen DiscID")
    if refold != icv_from_toc:
        failures.append(f"gate 3: re-fold from built ISO gives "
                        f"{refold.hex()}, TOC carries "
                        f"{icv_from_toc.hex()}")
    else:
        print(f"gate 3: fold(DiscID from built TOC, [built .ATP size "
              f"{len(built['TRK00001.ATP'])}]) = {refold.hex()} == ICV "
              f"in built TOC  OK")

    if failures:
        print("!!! VALIDITY GATE FAILED:")
        for f_ in failures:
            print(f"    {f_}")
        sys.exit(2)
    print("ALL VALIDITY GATES PASSED")
    print(f"DiscID = {DISC_ID.hex()}")
    print(f"ICV    = {icv_value.hex()}")
    print(f"ISO    = {iso_path} ({len(iso_bytes)} B, "
          f"md5 {md5(iso_bytes)})")


if __name__ == "__main__":
    main()
