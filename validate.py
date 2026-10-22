#!/usr/bin/env python3
"""Validation of the ATRAC CD author against Lola's ground-truth discs.
Run: python3 validate.py  (from ~/workspace/atrac-cd-author/)
Every check prints PASS/FAIL with the byte-diff detail on failure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from atrac_author import id3tag, ndb, sti, stk            # noqa: E402
from atrac_author.atp import OVERHEAD, assemble_atp       # noqa: E402
from atrac_author.secure_header import SecureHeader       # noqa: E402

STAGE0 = Path.home() / "workspace/atrac-cd-stage0"
DISCS = {"disc1": STAGE0 / "CD stuff", "disc2": STAGE0 / "disc2"}
results = []


def check(name: str, ok: bool, detail: str = ""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def first_diff(a: bytes, b: bytes) -> str:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"first diff at byte {i}: {x:02x} vs {y:02x} (len {len(a)} vs {len(b)})"
    return f"length differs: {len(a)} vs {len(b)}"


# --- 1. NDB regeneration, both discs, all five NDB files -----------------
for dname, dpath in DISCS.items():
    for fname in ("TRACK.NDB", "ALBUM.NDB", "ARTIST.NDB", "GROUP.NDB", "PLLIST.NDB"):
        orig = (dpath / fname).read_bytes()
        rebuilt = ndb.write_ndb(ndb.parse_ndb(orig))
        check(f"{dname} {fname} parse->write byte-identical",
              rebuilt == orig, "" if rebuilt == orig else first_diff(rebuilt, orig))

# --- 2. TOC00000.STI regeneration (modeled fields carried by parse) ------
for dname, dpath in DISCS.items():
    orig = (dpath / "TOC00000.STI").read_bytes()
    rebuilt = sti.write_toc(sti.parse_toc(orig))
    check(f"{dname} TOC00000.STI parse->write byte-identical",
          rebuilt == orig, "" if rebuilt == orig else first_diff(rebuilt, orig))
    orig_plf = (dpath / "TOC00001.STI").read_bytes()
    plf = sti.write_plf()
    check(f"{dname} TOC00001.STI generated empty-PLF byte-identical",
          plf == orig_plf, "" if plf == orig_plf else first_diff(plf, orig_plf))

# --- 3. STK ----------------------------------------------------------------
for dname, dpath in DISCS.items():
    orig = (dpath / "0001000E.STK").read_bytes()
    check(f"{dname} 0001000E.STK byte-identical copy", stk.write_stk() == orig)

# --- 4. Secure-header builder against all 7 sample headers ----------------
sample_atps = (sorted((DISCS["disc1"] / "HIFI").glob("*.ATP"))
               + [STAGE0 / "pairs/TRK000DC.ATP", STAGE0 / "pairs/TRK000E1.ATP"])
for p in sample_atps:
    orig = p.read_bytes()[1024:1120]
    rebuilt = SecureHeader.parse(orig).to_bytes()
    check(f"secure header {p.name} parse->build byte-identical", rebuilt == orig,
          "" if rebuilt == orig else first_diff(rebuilt, orig))

# --- 5. .ATP reassembly: Ignite My Heart (TRK000A0) -----------------------
orig_atp = (DISCS["disc1"] / "HIFI/TRK000A0.ATP").read_bytes()
plaintext = (STAGE0 / "pairs/ignite.raw").read_bytes()
tags = id3tag.parse_tag(orig_atp[:1024])
header = SecureHeader.parse(orig_atp[1024:1120])
rebuilt = assemble_atp(plaintext, 376, header, tags["TIT2"], tags["TPE1"], tags["TALB"])
check("Ignite .ATP size law: file == payload + 1120",
      len(rebuilt) == len(plaintext) + OVERHEAD == len(orig_atp),
      f"{len(rebuilt)} vs orig {len(orig_atp)}")
check("Ignite .ATP first 1120 bytes (ID3 + secure header) identical to original",
      rebuilt[:1120] == orig_atp[:1120],
      "" if rebuilt[:1120] == orig_atp[:1120] else first_diff(rebuilt[:1120], orig_atp[:1120]))
check("Ignite .ATP payload == plaintext via PLACEHOLDER identity cipher "
      "(differs from real ciphertext by design)", rebuilt[1120:] == plaintext)

# --- 6. Track filename law -------------------------------------------------
from atrac_author.atp import track_filename  # noqa: E402
for number, expect in ((10, "TRK0000A.ATP"), (160, "TRK000A0.ATP"),
                       (220, "TRK000DC.ATP"), (225, "TRK000E1.ATP")):
    check(f"track_filename({number}) == {expect}", track_filename(number) == expect)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
