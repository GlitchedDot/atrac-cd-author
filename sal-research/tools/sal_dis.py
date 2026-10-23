#!/usr/bin/env python3
"""sal_dis.py — SAL (Secure Application Layer) stream disassembler.

Grammar recovered from salwrap.dll (see stage0-readout-13):
  host-side reader class "SalBytecode" (C++ region) + runtime-lib
  writers FUN_65124cc0 (integer) / FUN_65125020 (octet string).

Value encoding (BER-flavoured, context-sensitive):
  length:  b < 0x80 -> b ; b == 0x80 -> indefinite (SEQUENCE only) ;
           b > 0x80 -> (b & 0x7f) big-endian length bytes follow.
  operand level (sequence depth 0):
    01 <1B>            INT  (1-byte signed content)      [OPERAND_1]
    02 <2B>            INT  (2-byte signed content)      [OPERAND_2]
    03 <len> <B...>    INT  (DER length + content)       [OPERAND_N]
    04 <len> <B...>    OCTET STRING ("OPERAND_S")
    30 80 ... 00 00    SEQUENCE (indefinite length, EOC-terminated)
  inside a sequence (depth >= 1):
    02 <len> <B...>    INTEGER (DER)
    04 <len> <B...>    OCTET STRING
    30 80 ... 00 00    SEQUENCE
    00 00              SEQ END (EOC)
  unknown tags fall back to generic BER TLV (tag + DER length +
  content) and are marked INFERRED; a length running past the end of
  the buffer is a hard failure.

Usage: sal_dis.py FILE [--offset N] [--limit N] [--quiet]
The .ocm container header (10 bytes, +5 wrapper for init.ocm) is
skipped automatically when detected.
"""

import sys

TAG_NAMES = {0x01: "INT1", 0x02: "INT", 0x03: "INTN", 0x04: "STR",
             0x30: "SEQ", 0x00: "EOC"}


class Fail(Exception):
    def __init__(self, off, msg):
        self.off = off
        self.msg = msg
        super().__init__(f"@{off:#x}: {msg}")


class Dis:
    def __init__(self, buf, base=0):
        self.b = buf
        self.base = base
        self.lines = []
        self.stats = {}
        self.max_depth = 0

    def emit(self, off, depth, text, kind):
        self.stats[kind] = self.stats.get(kind, 0) + 1
        self.lines.append(f"{self.base + off:08x}  {'  ' * depth}{text}")

    def read_length(self, pos):
        """DER length at pos -> (length or None for indefinite, newpos)."""
        if pos >= len(self.b):
            raise Fail(pos, "length past end of buffer")
        b = self.b[pos]
        if b < 0x80:
            return b, pos + 1
        if b == 0x80:
            return None, pos + 1
        n = b & 0x7F
        if n == 0 or pos + 1 + n > len(self.b):
            raise Fail(pos, "long length overruns buffer")
        v = int.from_bytes(self.b[pos + 1: pos + 1 + n], "big")
        return v, pos + 1 + n

    def value(self, pos, depth):
        """Parse one value at pos; return new pos."""
        self.max_depth = max(self.max_depth, depth)
        if pos >= len(self.b):
            raise Fail(pos, "value past end of buffer")
        tag = self.b[pos]
        start = pos

        # EOC / sequence end
        if tag == 0x00:
            if pos + 1 < len(self.b) and self.b[pos + 1] == 0x00:
                self.emit(start, depth, "SEQEND", "EOC")
                return pos + 2
            raise Fail(pos, "lone 0x00 byte")

        # SEQUENCE: 30 80 ... 00 00
        if tag == 0x30:
            if pos + 1 >= len(self.b) or self.b[pos + 1] != 0x80:
                raise Fail(pos, "SEQUENCE not followed by 0x80 indefinite marker")
            self.emit(start, depth, "SEQ {", "SEQ")
            pos += 2
            while True:
                if pos + 1 < len(self.b) and self.b[pos] == 0 and self.b[pos + 1] == 0:
                    self.emit(pos, depth, "} SEQEND", "EOC")
                    return pos + 2
                pos = self.value(pos, depth + 1)

        # operand-level compact integers
        if depth == 0 and tag in (0x01, 0x02, 0x03):
            if tag == 0x01:
                ln = 1
                hdr = 1
            elif tag == 0x02:
                ln = 2
                hdr = 1
            else:
                ln, np = self.read_length(pos + 1)
                if ln is None:
                    raise Fail(pos, "INTN with indefinite length")
                hdr = np - pos
            end = pos + hdr + ln
            if end > len(self.b):
                raise Fail(pos, f"INT content ({ln}B) overruns buffer")
            raw = self.b[pos + hdr: end]
            val = int.from_bytes(raw, "big", signed=True) if raw else 0
            self.emit(start, depth,
                      f"INT{ln if tag != 3 else 'N'} {val}  ; {raw.hex()}", "INT")
            return end

        # DER INTEGER / OCTET STRING (any depth for 04; depth>=1 for 02)
        if tag == 0x04 or (tag == 0x02 and depth >= 1):
            ln, np = self.read_length(pos + 1)
            if ln is None:
                raise Fail(pos, "indefinite length on non-sequence")
            end = np + ln
            if end > len(self.b):
                raise Fail(pos, f"tag {tag:#x} content ({ln}B) overruns buffer")
            raw = self.b[np:end]
            if tag == 0x02:
                val = int.from_bytes(raw, "big", signed=True) if raw else 0
                self.emit(start, depth, f"INTEGER {val}  ; {raw.hex()}", "INT")
            else:
                preview = raw[:24].hex()
                asc = "".join(chr(c) if 32 <= c < 127 else "." for c in raw[:24])
                self.emit(start, depth,
                          f"STR[{ln}] {preview}{'...' if ln > 24 else ''}  ; {asc}",
                          "STR")
            return end

        # generic BER TLV fallback (INFERRED)
        ln, np = self.read_length(pos + 1)
        if ln is None:
            raise Fail(pos, f"unknown tag {tag:#04x} with indefinite length")
        end = np + ln
        if end > len(self.b):
            raise Fail(pos, f"unknown tag {tag:#04x} content ({ln}B) overruns buffer")
        self.emit(start, depth,
                  f"TLV tag={tag:#04x} len={ln}  ; INFERRED generic BER", "TLV?")
        return end

    def run(self, limit=None):
        pos = 0
        end_limit = len(self.b) if limit is None else min(len(self.b), limit)
        try:
            while pos < end_limit:
                pos = self.value(pos, 0)
        except Fail as f:
            return pos, f
        return pos, None


def body_of(path):
    d = open(path, "rb").read()
    if d[:2] == b"\xff\xff" and len(d) <= 2:
        return d, 0, "stub file (FF FF)"
    if len(d) >= 5 and d[:5] == bytes([0x04, 0x83, 0x08, 0x47, 0x50]):
        return d[15:], 15, "init.ocm wrapper (+5) + 10B header"
    if len(d) >= 10 and d[0] == 0x03:
        return d[10:], 10, "10B .ocm header"
    return d, 0, "raw (no header detected)"


def main():
    args = sys.argv[1:]
    quiet = "--quiet" in args
    args = [a for a in args if a != "--quiet"]
    limit = None
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1], 0)
        del args[i:i + 2]
    path = args[0]
    body, off, note = body_of(path)
    print(f"# {path}: body {len(body)} bytes at file offset {off} ({note})")
    d = Dis(body, base=off)
    used, fail = d.run(limit)
    if not quiet:
        for l in d.lines[:400]:
            print(l)
        if len(d.lines) > 400:
            print(f"... [{len(d.lines) - 400} more lines suppressed]")
    print(f"# parsed {used} of {len(body)} body bytes "
          f"({100.0 * used / max(1, len(body)):.1f}%), elements={sum(d.stats.values())}, "
          f"maxdepth={d.max_depth}, stats={d.stats}")
    if fail:
        print(f"# FIRST FAILURE: {fail.msg} at body offset {fail.off:#x} "
              f"(file offset {off + fail.off:#x})")
    else:
        print("# stream consumed cleanly to the end/limit")


if __name__ == "__main__":
    main()
