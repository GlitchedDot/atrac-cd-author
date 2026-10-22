"""CIPHER INTERFACE — the pluggable hole in the authoring pipeline.

CONTRACT
--------
    encrypt_payload(payload: bytes, header_fields: dict) -> bytes

* `payload` is the clean ATRAC3+ frame stream of one track.
* `header_fields` carries the secure-header values the real cipher is
  known to consume (readout #7): block_seed (8 B), init_vector (8 B),
  mgd (8 B), connum (2 B), ekb_version (int).
* The real OpenMG cipher is LENGTH-PRESERVING (proven on the
  Dreamer/Electric/Ignite pairs: ciphertext length == plaintext
  length exactly), seeded per instance from BlockSeed + InitVector,
  with full history dependence from byte 0. Any implementation MUST
  preserve length; the .ATP assembler asserts it.

STATUS: the implementation below is a PLACEHOLDER. It returns the
payload UNCHANGED. Discs authored with it are structurally exact but
their audio is NOT encrypted, so a real player will not play them.
When the atpcd.ocm work names the real cipher, it drops in here —
one function, nothing else in the pipeline changes.
"""
from __future__ import annotations


def encrypt_payload_PLACEHOLDER_IDENTITY_NOT_THE_REAL_CIPHER(
        payload: bytes, header_fields: dict) -> bytes:
    """!!! PLACEHOLDER — NOT THE REAL CIPHER — RETURNS PAYLOAD UNCHANGED !!!"""
    return payload


# The pipeline calls this name. Swap the binding when the real cipher lands.
encrypt_payload = encrypt_payload_PLACEHOLDER_IDENTITY_NOT_THE_REAL_CIPHER
CIPHER_NAME = "PLACEHOLDER-IDENTITY (NOT THE REAL CIPHER)"
