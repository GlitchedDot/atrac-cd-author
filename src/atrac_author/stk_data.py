"""STK data access.

The 172-byte 0001000E.STK record is Sony EKB data extracted from
real discs in the author's private working tree. It is NOT
distributed with this repository.

The record is byte-identical on every SonicStage-burned ATRAC CD
verified so far, so any copy works. Supply your own, taken from a
disc you burned with SonicStage yourself:

  * set the environment variable ATRAC_STK_PATH to the file's
    location, or
  * place a file named 0001000E.STK in the repository root.

STK_BYTES loads lazily on first use and verifies the size
(172 bytes) and magic ("EKB ") before handing the record out, so
a wrong file fails loudly instead of authoring a corrupt disc.
"""

from __future__ import annotations

import os
from pathlib import Path

_STK_LEN = 172
_STK_MAGIC = b"EKB "
_cache: bytes | None = None


def _load() -> bytes:
    global _cache
    if _cache is not None:
        return _cache
    candidates: list[Path] = []
    env = os.environ.get("ATRAC_STK_PATH")
    if env:
        candidates.append(Path(env))
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "0001000E.STK")
    candidates.append(Path.cwd() / "0001000E.STK")
    for path in candidates:
        if path.is_file():
            data = path.read_bytes()
            if len(data) != _STK_LEN or not data.startswith(_STK_MAGIC):
                raise ValueError(
                    f"{path} is not a 0001000E.STK record "
                    f"(size {len(data)}, expected {_STK_LEN} bytes, "
                    f"magic {_STK_MAGIC!r})"
                )
            _cache = data
            return data
    raise FileNotFoundError(
        "0001000E.STK not found. Copy it from the root of an ATRAC "
        "CD you burned with SonicStage, then either set "
        "ATRAC_STK_PATH to its location or place it in the "
        "repository root. (The record is Sony data and is not "
        "distributed with this project.)"
    )


def __getattr__(name: str):
    if name == "STK_BYTES":
        return _load()
    raise AttributeError(name)
