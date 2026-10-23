"""Self-contained tests for atrac_author.

Nothing here needs reference discs, Sony data or external tools: every
input is synthetic. The STK record is replaced for the whole run by a
dummy 172-byte file ("EKB " + filler) served through ATRAC_STK_PATH, so
discs built here are structure tests only.

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""
import contextlib
import hashlib
import os
import random
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from atrac_author import (atp, capacity, cipher, id3tag, iso, ndb,  # noqa: E402
                          sti, stk, stk_data)
from atrac_author.author import TrackInput, build_iso, build_tree  # noqa: E402
from atrac_author.secure_header import SecureHeader  # noqa: E402

DUMMY_STK = b"EKB " + b"DUMMY-TEST-RECORD-NOT-SONY-DATA".ljust(168, b"\0")
FIXED_TS = datetime(2026, 10, 22, 12, 34, 56, 780000,
                    tzinfo=timezone(timedelta(hours=-7)))

# Characters are built with chr() so the source stays plain ASCII and no
# tool or editor can silently turn an escape into a different character.
EMOJI = chr(0x1F600)                      # outside the BMP: two UTF-16 units
REPLACEMENT = chr(0xFFFD)
LONE = chr(0xDCFF)                        # lone low surrogate (a bad filename byte)
LONE_PAIR = chr(0xD83D) + chr(0xDE00)     # a pair spelled as two separate code points
ACCENTED = "Caf" + chr(0xE9) + " " + chr(0xF1) + " " + "".join(
    chr(c) for c in (0x65E5, 0x672C, 0x8A9E))
UMLAUTS = chr(0xDC) + "n" + chr(0xEF)

_tmp = None
_saved = {}


def setUpModule():
    global _tmp
    _tmp = tempfile.TemporaryDirectory()
    path = Path(_tmp.name) / "0001000E.STK"
    path.write_bytes(DUMMY_STK)
    _saved["env"] = os.environ.get("ATRAC_STK_PATH")
    _saved["cache"] = stk_data._cache
    os.environ["ATRAC_STK_PATH"] = str(path)
    stk_data._cache = None


def tearDownModule():
    if _saved["env"] is None:
        os.environ.pop("ATRAC_STK_PATH", None)
    else:
        os.environ["ATRAC_STK_PATH"] = _saved["env"]
    stk_data._cache = _saved["cache"]
    _tmp.cleanup()


def tmp_path(name):
    return Path(_tmp.name) / name


def make_track(frames=20, frame_size=376, title="Title", artist="Artist",
               album="Album", seed=0):
    payload = random.Random(seed).randbytes(frames * frame_size)
    return TrackInput(payload=payload, frame_size=frame_size,
                      title=title, artist=artist, album=album)


@contextlib.contextmanager
def local_tz(tz, expect_offset_s):
    """Set the process time zone (a POSIX TZ string) or skip the test."""
    if not hasattr(time, "tzset"):
        raise unittest.SkipTest("time.tzset is not available here")
    old = os.environ.get("TZ")
    os.environ["TZ"] = tz
    time.tzset()
    try:
        if time.localtime(0).tm_gmtoff != expect_offset_s:
            raise unittest.SkipTest(f"platform ignored TZ={tz!r}")
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def utf16_units(s):
    return len(s.encode("utf-16-be")) // 2


class ClampStringTests(unittest.TestCase):
    def test_short_and_empty_untouched(self):
        self.assertEqual(ndb.clamp_string("Hello"), "Hello")
        self.assertEqual(ndb.clamp_string(""), "")

    def test_bmp_string_cut_at_30(self):
        self.assertEqual(ndb.clamp_string("x" * 45), "x" * 30)

    def test_bmp_strings_behave_like_a_plain_slice(self):
        # Compatibility guard: for ordinary text the result is exactly
        # what the original s[:30] gave, so validated discs don't change.
        rng = random.Random(5)
        pool = [chr(c) for c in range(0x20, 0xD800)]
        for _ in range(300):
            s = "".join(rng.choice(pool) for _ in range(rng.randint(0, 60)))
            self.assertEqual(ndb.clamp_string(s), s[:30])

    def test_cut_is_on_code_units_not_code_points(self):
        s = "A" * 28 + EMOJI * 2              # 30 code points, 32 units
        out = ndb.clamp_string(s)
        self.assertEqual(out, "A" * 28 + EMOJI)
        self.assertEqual(utf16_units(out), 30)

    def test_surrogate_pair_is_never_split(self):
        self.assertEqual(ndb.clamp_string("A" * 29 + EMOJI), "A" * 29)

    def test_all_non_bmp(self):
        out = ndb.clamp_string(EMOJI * 40)
        self.assertEqual(out, EMOJI * 15)
        self.assertEqual(utf16_units(out), 30)

    def test_lone_surrogates_become_replacement_char(self):
        self.assertEqual(ndb.clamp_string("bad" + LONE), "bad" + REPLACEMENT)
        self.assertEqual(ndb.clamp_string(LONE_PAIR), REPLACEMENT * 2)
        ndb.clamp_string(chr(0xDC80) * 5).encode("utf-16-be")   # must not raise

    def test_a_real_emoji_is_not_mistaken_for_surrogates(self):
        self.assertEqual(ndb.clamp_string(EMOJI), EMOJI)

    def test_idempotent(self):
        for s in ("x" * 45, "A" * 28 + EMOJI * 2, "bad" + LONE, ""):
            once = ndb.clamp_string(s)
            self.assertEqual(ndb.clamp_string(once), once)


class NdbTests(unittest.TestCase):
    def test_header_layout(self):
        data = ndb.write_ndb(["a", "b", "c"])
        self.assertEqual(data[:6], b"NDB \x01\x00")
        self.assertEqual(int.from_bytes(data[6:8], "big"), 3)
        self.assertEqual(len(data), ndb.HEADER_LEN + 3 * ndb.RECORD_LEN)
        self.assertFalse(any(data[8:ndb.HEADER_LEN]))

    def test_record_layout(self):
        rec = ndb.write_ndb(["Hi"])[ndb.HEADER_LEN:]
        self.assertEqual(rec[:2], b"\x02\x00")
        self.assertEqual(rec[2:6], "Hi".encode("utf-16-be"))
        self.assertFalse(any(rec[6:]))

    def test_empty_string_is_an_all_zero_record(self):
        data = ndb.write_ndb(["", "x"])
        self.assertFalse(any(data[256:256 + 128]))
        self.assertEqual(ndb.parse_ndb(data), ["", "x"])

    def test_empty_ndb(self):
        data = ndb.write_ndb([])
        self.assertEqual(len(data), ndb.HEADER_LEN)
        self.assertEqual(ndb.parse_ndb(data), [])

    def test_round_trip(self):
        strings = ["Plain", ACCENTED, "x" * 30, "A" * 28 + EMOJI, ""]
        self.assertEqual(ndb.parse_ndb(ndb.write_ndb(strings)), strings)

    def test_overlong_strings_are_clamped_and_still_parse(self):
        parsed = ndb.parse_ndb(ndb.write_ndb(["A" * 28 + EMOJI * 2, "y" * 99]))
        self.assertEqual(parsed, ["A" * 28 + EMOJI, "y" * 30])

    def test_lone_surrogate_is_written_as_replacement_char(self):
        self.assertEqual(ndb.parse_ndb(ndb.write_ndb(["bad" + LONE])),
                         ["bad" + REPLACEMENT])

    def test_string_of_only_surrogates_is_not_an_empty_record(self):
        data = ndb.write_ndb([LONE])
        self.assertTrue(any(data[256:]))
        self.assertEqual(ndb.parse_ndb(data), [REPLACEMENT])

    def test_parse_rejects_bad_input(self):
        good = ndb.write_ndb(["x"])
        bad_prefix = bytearray(good)
        bad_prefix[256] = 9
        dirty_tail = bytearray(good)
        dirty_tail[256 + 100] = 1
        for bad in (b"XXXX" + good[4:], good[:-1],
                    bytes(bad_prefix), bytes(dirty_tail)):
            with self.assertRaises(ValueError):
                ndb.parse_ndb(bad)


class Id3Tests(unittest.TestCase):
    def test_tag_is_1024_bytes_with_id3v24_header(self):
        tag = id3tag.write_tag("Song", "Artist", "Album")
        self.assertEqual(len(tag), 1024)
        self.assertEqual(tag[:6], b"ID3\x04\x00\x00")
        self.assertEqual(tag[6:10], bytes([0, 0, 7, 0x76]))   # syncsafe 1014

    def test_frames_in_order_and_round_trip(self):
        tag = id3tag.write_tag("Song", "Artist", "Album")
        self.assertEqual(id3tag.parse_tag(tag),
                         {"TIT2": "Song", "TPE1": "Artist", "TALB": "Album"})
        self.assertLess(tag.index(b"TIT2"), tag.index(b"TPE1"))
        self.assertLess(tag.index(b"TPE1"), tag.index(b"TALB"))

    def test_max_length_strings_fit(self):
        tag = id3tag.write_tag("t" * 30, "a" * 30, "b" * 30)
        self.assertEqual(len(tag), 1024)
        self.assertEqual(id3tag.parse_tag(tag),
                         {"TIT2": "t" * 30, "TPE1": "a" * 30, "TALB": "b" * 30})

    def test_empty_album(self):
        tag = id3tag.write_tag("Song", "Artist", "")
        self.assertEqual(id3tag.parse_tag(tag)["TALB"], "")

    def test_non_bmp_and_surrogate_strings(self):
        tag = id3tag.write_tag("A" * 28 + EMOJI * 2, "bad" + LONE, "z" * 99)
        self.assertEqual(len(tag), 1024)
        self.assertEqual(id3tag.parse_tag(tag),
                         {"TIT2": "A" * 28 + EMOJI,
                          "TPE1": "bad" + REPLACEMENT,
                          "TALB": "z" * 30})

    def test_parse_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            id3tag.parse_tag(b"ID3" + bytes(10))      # wrong length
        with self.assertRaises(ValueError):
            id3tag.parse_tag(bytes(1024))             # no magic


class SecureHeaderTests(unittest.TestCase):
    def test_round_trip_and_constants(self):
        h = SecureHeader.fresh(1234, random.Random(7))
        raw = h.to_bytes()
        self.assertEqual(len(raw), 96)
        self.assertEqual(SecureHeader.parse(raw), h)
        self.assertEqual(raw[0:4], bytes.fromhex("0100282e"))
        self.assertEqual(int.from_bytes(raw[4:8], "big"), 1234)
        self.assertEqual(int.from_bytes(raw[0x10:0x14], "big"), 0x0001000E)
        self.assertEqual(raw[0x20:0x28], bytes.fromhex("010f500000040000"))
        self.assertEqual(raw[0x40:0x44], b"ATX ")

    def test_seeded_rng_is_deterministic(self):
        a = SecureHeader.fresh(10, random.Random(1))
        b = SecureHeader.fresh(10, random.Random(1))
        c = SecureHeader.fresh(10, random.Random(2))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_header_fields_handed_to_the_cipher(self):
        f = SecureHeader.fresh(10, random.Random(1)).header_fields()
        self.assertEqual(set(f), {"block_seed", "init_vector", "mgd",
                                  "connum", "ekb_version"})
        self.assertEqual(f["ekb_version"], 0x0001000E)
        self.assertEqual([len(f[k]) for k in
                          ("block_seed", "init_vector", "mgd", "connum")],
                         [8, 8, 8, 2])

    def test_parse_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            SecureHeader.parse(bytes(95))


class AtpTests(unittest.TestCase):
    FRAME = 376

    def header(self, frames):
        return SecureHeader.fresh(frames, random.Random(3))

    def test_size_law_and_layout(self):
        payload = random.Random(1).randbytes(10 * self.FRAME)
        header = self.header(10)
        out = atp.assemble_atp(payload, self.FRAME, header, "T", "A", "B")
        self.assertEqual(atp.OVERHEAD, 1120)
        self.assertEqual(len(out), len(payload) + 1120)
        self.assertEqual(out[:1024], id3tag.write_tag("T", "A", "B"))
        self.assertEqual(out[1024:1120], header.to_bytes())

    def test_payload_goes_through_the_cipher_interface(self):
        payload = random.Random(1).randbytes(10 * self.FRAME)
        header = self.header(10)
        seen = {}

        def fake(p, fields):
            seen["payload"], seen["fields"] = p, fields
            return p[::-1]

        with mock.patch.object(cipher, "encrypt_payload", fake):
            out = atp.assemble_atp(payload, self.FRAME, header, "T", "A", "B")
        self.assertEqual(seen["payload"], payload)
        self.assertEqual(seen["fields"], header.header_fields())
        self.assertEqual(out[1120:], payload[::-1])

    def test_length_changing_cipher_is_rejected(self):
        payload = bytes(10 * self.FRAME)
        with mock.patch.object(cipher, "encrypt_payload", lambda p, f: p + b"x"):
            with self.assertRaises(ValueError):
                atp.assemble_atp(payload, self.FRAME, self.header(10),
                                 "T", "A", "B")

    def test_rejects_partial_frames_and_frame_count_mismatch(self):
        payload = bytes(10 * self.FRAME)
        with self.assertRaises(ValueError):
            atp.assemble_atp(payload[:-1], self.FRAME, self.header(10),
                             "T", "A", "B")
        with self.assertRaises(ValueError):
            atp.assemble_atp(payload, self.FRAME, self.header(11),
                             "T", "A", "B")

    def test_track_filename(self):
        for number, expect in ((1, "TRK00001.ATP"), (10, "TRK0000A.ATP"),
                               (160, "TRK000A0.ATP"), (220, "TRK000DC.ATP"),
                               (225, "TRK000E1.ATP"), (0xFFFFF, "TRKFFFFF.ATP")):
            self.assertEqual(atp.track_filename(number), expect)
        for bad in (0, -1, 0x100000):
            with self.assertRaises(ValueError):
                atp.track_filename(bad)


class CipherContractTests(unittest.TestCase):
    def test_encrypt_payload_preserves_length(self):
        header = SecureHeader.fresh(4, random.Random(1))
        payload = random.Random(2).randbytes(4 * 376)
        out = cipher.encrypt_payload(payload, header.header_fields())
        self.assertIsInstance(out, bytes)
        self.assertEqual(len(out), len(payload))


class StiTests(unittest.TestCase):
    def build(self, counts, groups, seed=5):
        return sti.Toc.build(counts, groups, random.Random(seed))

    def test_frames_to_seconds(self):
        self.assertEqual(sti.frames_to_seconds(0), 0)
        self.assertEqual(sti.frames_to_seconds(3444), 159)

    def test_round_trip(self):
        data = sti.write_toc(self.build([100, 200, 300], [(1, 2), (3, 3)]))
        parsed = sti.parse_toc(data)
        self.assertEqual(sti.write_toc(parsed), data)
        self.assertEqual(parsed.groups, [(1, 2), (3, 3)])
        self.assertEqual([(t.number, t.group, t.frame_count)
                          for t in parsed.tracks],
                         [(1, 1, 100), (2, 1, 200), (3, 2, 300)])

    def test_layout(self):
        counts = [100, 200, 300]
        data = sti.write_toc(self.build(counts, [(1, 2), (3, 3)]))
        self.assertEqual(len(data), 0x900 + 3 * 16)
        self.assertEqual(data[:4], b"TOC ")
        self.assertEqual(int.from_bytes(data[4:8], "little"), 1)
        self.assertEqual(data[9], 2)                               # groups
        self.assertEqual(int.from_bytes(data[10:12], "big"), 3)    # tracks
        self.assertEqual(int.from_bytes(data[12:16], "big"),
                         sum(sti.frames_to_seconds(c) for c in counts))
        self.assertFalse(any(data[0x100:0x108]))                   # slot 0
        self.assertEqual(data[0x108:0x110], bytes([0, 1, 0, 2, 0, 1, 0, 0]))
        self.assertEqual(data[0x110:0x118], bytes([0, 3, 0, 3, 0, 2, 0, 0]))
        rec2 = data[0x900 + 16:0x900 + 32]
        self.assertEqual(rec2, bytes([0, 2, 0, 2, 1, 0, 0, 0])
                         + bytes.fromhex("0100282e") + (200).to_bytes(4, "big"))

    def test_seeded_rng_makes_the_toc_reproducible(self):
        a = sti.write_toc(self.build([10, 20], [(1, 2)], seed=1))
        b = sti.write_toc(self.build([10, 20], [(1, 2)], seed=1))
        c = sti.write_toc(self.build([10, 20], [(1, 2)], seed=2))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_uncovered_track_is_a_clear_error(self):
        with self.assertRaises(ValueError) as cm:
            self.build([10, 20, 30], [(1, 1), (3, 3)])
        self.assertIn("track 2", str(cm.exception))
        with self.assertRaises(ValueError):
            self.build([10], [])

    def test_empty_playlist_file(self):
        plf = sti.write_plf()
        self.assertEqual(len(plf), 2176)
        self.assertEqual(plf[:5], b"PLF \x01")
        self.assertFalse(any(plf[5:]))

    def test_parse_rejects_bad_input(self):
        good = sti.write_toc(self.build([10], [(1, 1)]))
        with self.assertRaises(ValueError):
            sti.parse_toc(b"XXXX" + good[4:])
        with self.assertRaises(ValueError):
            sti.parse_toc(good[:-1])


class StkTests(unittest.TestCase):
    def test_dummy_record_is_served(self):
        self.assertEqual(stk.STK_FILENAME, "0001000E.STK")
        self.assertEqual(stk.write_stk(), DUMMY_STK)

    def test_wrong_size_or_magic_fails_loudly(self):
        bad_path = tmp_path("bad.STK")
        for blob in (DUMMY_STK[:-1], b"XXXX" + DUMMY_STK[4:]):
            bad_path.write_bytes(blob)
            with mock.patch.dict(os.environ, {"ATRAC_STK_PATH": str(bad_path)}):
                stk_data._cache = None
                try:
                    with self.assertRaises(ValueError):
                        stk.write_stk()
                finally:
                    stk_data._cache = None


def sample_iso_files():
    rng = random.Random(11)
    return {
        "/TRACK.NDB": rng.randbytes(300),
        "/0001000E.STK": DUMMY_STK,
        "/HIFI/TRK00001.ATP": rng.randbytes(5000),
        "/HIFI/TRK00002.ATP": rng.randbytes(2048),    # exactly one sector
        "/HIFI/TRK00003.ATP": rng.randbytes(1),
    }


def write_image(files, **kw):
    path = tmp_path("t.iso")
    size = iso.write_iso(files, str(path), **kw)
    data = path.read_bytes()
    assert size == len(data)
    return data


class IsoTests(unittest.TestCase):
    def test_independent_reader_sees_every_file(self):
        files = sample_iso_files()
        data = write_image(files, timestamp=FIXED_TS)
        self.assertEqual(iso.read_iso_tree(data),
                         {p: (len(d), hashlib.sha256(d).hexdigest())
                          for p, d in files.items()})

    def test_reader_rejects_non_iso(self):
        with self.assertRaises(ValueError):
            iso.read_iso_tree(bytes(40 * 2048))

    def test_primary_volume_descriptor(self):
        data = write_image(sample_iso_files(), timestamp=FIXED_TS)
        sectors = len(data) // 2048
        self.assertEqual(len(data) % 2048, 0)
        self.assertFalse(any(data[:16 * 2048]))                 # system area
        pvd = data[16 * 2048:17 * 2048]
        self.assertEqual(pvd[:7], b"\x01CD001\x01")
        self.assertEqual(pvd[8:72], b" " * 64)                  # blank ids
        self.assertEqual(int.from_bytes(pvd[80:84], "little"), sectors)
        self.assertEqual(int.from_bytes(pvd[84:88], "big"), sectors)
        self.assertEqual(int.from_bytes(pvd[128:130], "little"), 2048)
        self.assertEqual(pvd[881], 1)
        self.assertEqual(data[17 * 2048:17 * 2048 + 7], b"\xffCD001\x01")

    def test_volume_identifier(self):
        data = write_image(sample_iso_files(), vol_ident="ATRAC",
                           timestamp=FIXED_TS)
        self.assertEqual(data[16 * 2048 + 40:16 * 2048 + 72],
                         b"ATRAC" + b" " * 27)
        data = write_image(sample_iso_files(), vol_ident=UMLAUTS,
                           timestamp=FIXED_TS)
        self.assertEqual(data[16 * 2048 + 40:16 * 2048 + 72],
                         b"?n?" + b" " * 29)

    def test_layout_is_gapless_and_matches_the_planner(self):
        files = sample_iso_files()
        data = write_image(files, timestamp=FIXED_TS)
        sizes = {p: len(d) for p, d in files.items()}
        self.assertEqual(iso.iso_sector_count(sizes), len(data) // 2048)
        # 16 system + PVD + terminator + 2 path tables + 2 directories = 22
        # sectors, then file data packed back to back.
        self.assertEqual(len(data) // 2048,
                         22 + sum(-(-n // 2048) for n in sizes.values()))

    def test_fixed_timestamp_is_reproducible(self):
        files = sample_iso_files()
        self.assertEqual(write_image(files, timestamp=FIXED_TS),
                         write_image(files, timestamp=FIXED_TS))

    def test_timestamp_values(self):
        data = write_image(sample_iso_files(), timestamp=FIXED_TS)
        pvd = data[16 * 2048:17 * 2048]
        # PVD: UTC digits (19:34:56.78) + local offset byte (-7h = -28 x 15 min)
        stamp = b"2026102219345678" + bytes([0xE4])
        for off in (813, 830, 847, 864):
            self.assertEqual(pvd[off:off + 17], stamp)
        local = bytes([126, 10, 22, 12, 34, 56, 0xE4])       # directory records
        self.assertEqual(pvd[156 + 18:156 + 25], local)
        root_lba = int.from_bytes(pvd[156 + 2:156 + 6], "little")
        self.assertEqual(data[root_lba * 2048 + 18:root_lba * 2048 + 25], local)

    def test_different_timestamps_change_only_the_stamps(self):
        files = sample_iso_files()
        a = write_image(files, timestamp=FIXED_TS)
        b = write_image(files, timestamp=FIXED_TS + timedelta(seconds=5))
        self.assertEqual(len(a), len(b))
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        self.assertTrue(diff)
        self.assertLess(len(diff), 100)
        self.assertTrue(all(i < 22 * 2048 for i in diff))   # headers/dirs only

    def test_aware_timestamp_ignores_the_machine_time_zone(self):
        files = sample_iso_files()
        with local_tz("UTC0", 0):
            a = write_image(files, timestamp=FIXED_TS)
        with local_tz("XYZ-5:30", 19800):
            b = write_image(files, timestamp=FIXED_TS)
        self.assertEqual(a, b)

    def test_naive_timestamp_is_read_as_local_time(self):
        naive = datetime(2026, 10, 22, 12, 0, 0)
        with local_tz("XYZ-5:30", 19800):                    # UTC+05:30
            data = write_image(sample_iso_files(), timestamp=naive)
        pvd = data[16 * 2048:17 * 2048]
        self.assertEqual(pvd[813:829], b"2026102206300000")   # 06:30 UTC
        self.assertEqual(pvd[829], 22)                       # +5.5 h
        self.assertEqual(pvd[156 + 18:156 + 25],
                         bytes([126, 10, 22, 12, 0, 0, 22]))

    def test_default_timestamp_is_now(self):
        before = datetime.now(timezone.utc)
        data = write_image(sample_iso_files())
        after = datetime.now(timezone.utc)
        digits = data[16 * 2048 + 813:16 * 2048 + 827].decode("ascii")
        stamped = datetime.strptime(digits, "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc)
        self.assertLessEqual(before.replace(microsecond=0), stamped)
        self.assertLessEqual(stamped, after)


class CapacityTests(unittest.TestCase):
    def test_gate_boundary(self):
        sizes = {"/TRACK.NDB": 300, "/HIFI/TRK00001.ATP": 100000}
        est = capacity.estimate_iso_sectors(sizes)
        self.assertEqual(est, iso.iso_sector_count(sizes))
        need = est + capacity.SESSION_OVERHEAD_SECTORS
        self.assertEqual(capacity.check_capacity(sizes, need), est)   # fits
        with self.assertRaises(capacity.CapacityError):
            capacity.check_capacity(sizes, need - 1)                  # 1 short

    def test_known_blanks(self):
        self.assertEqual(capacity.SECTOR, 2048)
        self.assertEqual(capacity.BLANKS[360000], "12 cm 80 min")


class AuthorTests(unittest.TestCase):
    def tracks(self, n=3):
        return [make_track(frames=10 + i, title=f"Song {i + 1}", seed=i)
                for i in range(n)]

    def test_tree_contents_and_sizes(self):
        tracks = self.tracks(3)
        files = build_tree(tracks, rng=random.Random(1))
        self.assertEqual(set(files), {
            "/TRACK.NDB", "/ALBUM.NDB", "/ARTIST.NDB", "/GROUP.NDB",
            "/PLLIST.NDB", "/TOC00000.STI", "/TOC00001.STI", "/0001000E.STK",
            "/HIFI/TRK00001.ATP", "/HIFI/TRK00002.ATP", "/HIFI/TRK00003.ATP"})
        for i, t in enumerate(tracks, start=1):
            self.assertEqual(len(files[f"/HIFI/TRK{i:05X}.ATP"]),
                             len(t.payload) + 1120)
        for name in ("TRACK", "ALBUM", "ARTIST"):
            self.assertEqual(len(files[f"/{name}.NDB"]), 256 + 3 * 128)
        self.assertEqual(len(files["/PLLIST.NDB"]), 256)
        self.assertEqual(len(files["/TOC00000.STI"]), 0x900 + 3 * 16)
        self.assertEqual(len(files["/TOC00001.STI"]), 2176)
        self.assertEqual(files["/0001000E.STK"], DUMMY_STK)

    def test_metadata_reaches_ndb_and_id3(self):
        tracks = [make_track(title="One", artist="A1", album="Al1"),
                  make_track(title="Two", artist="A2", album="")]
        files = build_tree(tracks, rng=random.Random(1))
        self.assertEqual(ndb.parse_ndb(files["/TRACK.NDB"]), ["One", "Two"])
        self.assertEqual(ndb.parse_ndb(files["/ARTIST.NDB"]), ["A1", "A2"])
        self.assertEqual(ndb.parse_ndb(files["/ALBUM.NDB"]), ["Al1", ""])
        self.assertEqual(id3tag.parse_tag(files["/HIFI/TRK00002.ATP"][:1024]),
                         {"TIT2": "Two", "TPE1": "A2", "TALB": ""})

    def test_default_group_covers_every_track(self):
        files = build_tree(self.tracks(3), rng=random.Random(1))
        self.assertEqual(ndb.parse_ndb(files["/GROUP.NDB"]), ["New Group"])
        toc = sti.parse_toc(files["/TOC00000.STI"])
        self.assertEqual(toc.groups, [(1, 3)])
        self.assertEqual([t.group for t in toc.tracks], [1, 1, 1])

    def test_custom_groups(self):
        files = build_tree(self.tracks(3), groups=[("A", 1, 1), ("B", 2, 3)],
                           rng=random.Random(1))
        self.assertEqual(ndb.parse_ndb(files["/GROUP.NDB"]), ["A", "B"])
        toc = sti.parse_toc(files["/TOC00000.STI"])
        self.assertEqual([t.group for t in toc.tracks], [1, 2, 2])
        self.assertEqual([t.frame_count for t in toc.tracks], [10, 11, 12])

    def test_no_tracks_is_an_error(self):
        with self.assertRaises(ValueError):
            build_tree([])

    def test_uncovered_tracks_are_a_clear_error(self):
        with self.assertRaises(ValueError) as cm:
            build_tree(self.tracks(3), groups=[("A", 1, 2)],
                       rng=random.Random(1))
        self.assertIn("track 3", str(cm.exception))

    def test_unusual_titles_survive_end_to_end(self):
        track = make_track(title="A" * 28 + EMOJI * 2, artist="bad" + LONE)
        files = build_tree([track], rng=random.Random(1))
        self.assertEqual(ndb.parse_ndb(files["/TRACK.NDB"]),
                         ["A" * 28 + EMOJI])
        self.assertEqual(ndb.parse_ndb(files["/ARTIST.NDB"]),
                         ["bad" + REPLACEMENT])
        tag = id3tag.parse_tag(files["/HIFI/TRK00001.ATP"][:1024])
        self.assertEqual(tag["TIT2"], "A" * 28 + EMOJI)
        self.assertEqual(tag["TPE1"], "bad" + REPLACEMENT)

    def test_build_iso_end_to_end(self):
        out = tmp_path("disc.iso")
        stats = build_iso(self.tracks(3), str(out), rng=random.Random(1),
                          timestamp=FIXED_TS)
        data = out.read_bytes()
        self.assertEqual(stats["iso_bytes"], len(data))
        self.assertEqual(stats["iso_sectors"], len(data) // 2048)
        self.assertEqual(stats["estimated_sectors"], stats["iso_sectors"])
        self.assertEqual(stats["capacity_label"], "12 cm 80 min")
        self.assertEqual(iso.read_iso_tree(data), stats["files"])

    def test_seed_and_timestamp_make_the_image_reproducible(self):
        def build(seed, name):
            out = tmp_path(name)
            build_iso(self.tracks(2), str(out), rng=random.Random(seed),
                      timestamp=FIXED_TS)
            return out.read_bytes()

        self.assertEqual(build(1, "a.iso"), build(1, "b.iso"))
        self.assertNotEqual(build(1, "a.iso"), build(2, "c.iso"))

    def test_over_capacity_is_refused_before_anything_is_written(self):
        out = tmp_path("refused.iso")
        with self.assertRaises(capacity.CapacityError):
            build_iso(self.tracks(2), str(out), capacity_sectors=10000,
                      rng=random.Random(1))
        self.assertFalse(out.exists())

    def test_capacity_boundary_through_build_iso(self):
        tracks = self.tracks(2)
        sizes = {p: len(d) for p, d in
                 build_tree(tracks, rng=random.Random(1)).items()}
        need = (capacity.estimate_iso_sectors(sizes)
                + capacity.SESSION_OVERHEAD_SECTORS)
        stats = build_iso(tracks, str(tmp_path("fit.iso")),
                          capacity_sectors=need, rng=random.Random(1))
        self.assertEqual(stats["capacity_label"], "custom")
        with self.assertRaises(capacity.CapacityError):
            build_iso(tracks, str(tmp_path("short.iso")),
                      capacity_sectors=need - 1, rng=random.Random(1))


if __name__ == "__main__":
    unittest.main()
