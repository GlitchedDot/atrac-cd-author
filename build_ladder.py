#!/usr/bin/env python3
"""Build the nine-rung ladder demo disc: 'It's Alright' at every
ATRAC3+ bitrate, authored with the PLACEHOLDER identity cipher.

Output: out/ladder-demo-PLACEHOLDER-CIPHER.iso + out/ladder-demo-tree/
The ISO proves STRUCTURE ONLY — the payload cipher is a placeholder,
so a real player will NOT play it.
"""
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from atrac_author import capacity                       # noqa: E402
from atrac_author.author import TrackInput, build_iso, build_tree  # noqa: E402
from atrac_author.iso import read_iso_tree              # noqa: E402

ROOT = Path(__file__).parent
WORK = ROOT / "work"
OUT = ROOT / "out"
ENCODER = Path.home() / "workspace/atracdenc-test/build/src/atracdenc"
SONG_OMA = Path.home() / "workspace/user/files/1-07_It_s_Alright.OMA"
TITLE = "It's Alright"
ARTIST = "MY LITTLE PONY|Johnny Orlando"      # from the library file's tags
ALBUM = "My Little Pony: A New Generati"      # as tagged (30-char field)
RUNGS = [(48, 280), (64, 376), (96, 560), (128, 744), (160, 928),
         (192, 1112), (256, 1480), (320, 1848), (352, 2048)]
BLANK_80MIN = 360000

WORK.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

# 1. Decode the library song to 44.1 kHz / 16-bit WAV.
wav = WORK / "its_alright.wav"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(SONG_OMA),
                "-ar", "44100", "-ac", "2", "-sample_fmt", "s16", str(wav)],
               check=True)

# 2. Encode every rung to a raw ATRAC3+ frame stream.
tracks = []
stats = []
for kbps, frame_size in RUNGS:
    raw = WORK / f"its_alright_{kbps}k.raw"
    if not (raw.exists() and raw.stat().st_size % frame_size == 0):
        cmd = [str(ENCODER), "-e", "atrac3plus", "--container", "raw",
               "-i", str(wav), "-o", str(raw)]
        if kbps != 352:                  # 352.8k is the encoder default (E5 method)
            cmd += ["--bitrate", str(kbps)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    payload = raw.read_bytes()
    assert len(payload) % frame_size == 0, f"{kbps}k: raw size not frame-aligned"
    tracks.append(TrackInput(payload=payload, frame_size=frame_size,
                             title=f"{TITLE} [{kbps}k]", artist=ARTIST, album=ALBUM))
    stats.append((kbps, frame_size, len(payload) // frame_size, len(payload)))

# 3. Capacity gate must REFUSE an undersized blank. (The 9-rung ladder
#    totals only ~39 MB, so it would fit even a pocket CD; the refusal
#    is proven against a custom 10,000-sector blank = 20,480,000 B.)
try:
    build_iso(tracks, str(OUT / "should_not_exist.iso"), capacity_sectors=10000,
              groups=[("Bitrate Ladder", 1, 9)], rng=random.Random(1))
    print("!! capacity gate FAILED to refuse the undersized custom blank")
    sys.exit(1)
except capacity.CapacityError as e:
    print(f"capacity gate refusal (expected): {e}")

# 4. Author the disc against the 80-min blank + emit the tree alongside.
rng = random.Random(20261022)
tree = build_tree(tracks, groups=[("Bitrate Ladder", 1, 9)], rng=random.Random(20261022))
tree_dir = OUT / "ladder-demo-tree"
for path, data in tree.items():
    dest = tree_dir / path.lstrip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
result = build_iso(tracks, str(OUT / "ladder-demo-PLACEHOLDER-CIPHER.iso"),
                   capacity_sectors=BLANK_80MIN,
                   groups=[("Bitrate Ladder", 1, 9)],
                   vol_ident="", rng=rng)  # blank, like real discs

# 5. Verify the ISO with the independent reader.
iso_bytes = Path(result["iso_path"]).read_bytes()
readback = read_iso_tree(iso_bytes)
expected = result["files"]
mismatch = [p for p in expected
            if p not in readback or readback[p] != expected[p]]
print(f"ISO independent-reader verification: "
      f"{len(readback)} files read back, {len(mismatch)} mismatches")

# 6. Stats table.
print(f"\n{'rung':>6} {'frame B':>8} {'frames':>7} {'payload B':>11} {'.ATP B':>11}")
total_atp = 0
for (kbps, fs, frames, payload_len) in stats:
    atp_len = payload_len + 1120
    total_atp += atp_len
    print(f"{kbps:>5}k {fs:>8} {frames:>7} {payload_len:>11} {atp_len:>11}")
print(f"total .ATP bytes: {total_atp}")
print(f"ISO: {result['iso_bytes']} bytes = {result['iso_sectors']} sectors "
      f"(estimated {result['estimated_sectors']}) of {BLANK_80MIN} "
      f"({result['capacity_label']}) — headroom "
      f"{BLANK_80MIN - result['iso_sectors']} sectors")
if mismatch:
    sys.exit(1)
print("\nLadder demo built and verified.")
